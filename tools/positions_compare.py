#!/usr/bin/env python3
"""Real against model, on the owner's computer: a filled positions file beside
the published record.

An execution agent fills a private copy of ``docs/positions-template.json``
with the owner's real orders, fills, exits and fees. This reads that copy and
the public ``docs/`` (``model_record.offline()``: the record, the pick ledger,
the retained minute evidence and the record's own observations as bars), and
prints, for each position, its real R beside the model's R for the same
ticket. It writes nothing but an explicit ``--json`` outside the repository,
and sends nothing anywhere: a filled positions file is the owner's and never
belongs in this public repository.

Real R is the model's convention applied to the real trade: the per-share
risk is the average fill less the protective stop the ticket planned, and
each exit is weighted by its shares (``record.r_multiple()``'s rule). It is
given only for a position whose exits account for every filled share; an
open one is said to be open. Fees are reported beside, never folded into R.
The two Rs are never added: the model's walk is daily bars from the trigger,
the real trade is whatever was actually filled.

    python tools/positions_compare.py --positions ~/private/positions-2026-11-20.json --docs docs
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import orders  # noqa: E402

CLOSED, OPEN, NOT_FILLED = "closed", "open", "not_filled"


def _avg(rows: list[dict]) -> tuple[int, float | None]:
    shares = sum(r["shares"] for r in rows)
    return shares, (math.fsum(r["shares"] * r["price"] for r in rows) / shares) if shares else None


def real(position: dict) -> dict:
    """One position's real result, in the model's R convention."""
    filled, fill = _avg(position.get("fills") or [])
    exited, _ = _avg(position.get("exits") or [])
    stop = position["planned"]["protective_stop"]
    out = {"filled": filled, "exited": exited, "average_fill": None if fill is None else round(fill, 4),
           "fees_usd": position.get("fees_usd"), "r": None, "usd": None}
    if not filled:
        return {**out, "state": NOT_FILLED}
    if exited != filled:
        return {**out, "state": OPEN}
    usd = math.fsum(e["shares"] * (e["price"] - fill) for e in position["exits"])
    risk = filled * (fill - stop)
    return {**out, "state": CLOSED, "usd": round(usd, 2), "r": round(usd / risk, 2) if risk > 0 else None}


def compare(positions: dict, model_block: dict) -> list[dict]:
    """Each position beside the model's own row for its ticket: same symbol,
    same setup kind, picked on the ticket's measured session."""
    by_key = {(p["ticker"], p["kind"], p["picked"]): p for p in model_block.get("plans") or []}
    out = []
    for position in positions["positions"]:
        session, kind, symbol = position["ticket_id"].split(":", 2)
        model = by_key.get((symbol, kind, session))
        out.append({"ticket_id": position["ticket_id"], "symbol": symbol, "status": position["status"],
                    "real": real(position),
                    "model": ({"bucket": model["bucket"], "r": model["r"], "status": model["status"]}
                              if model else None)})
    return out


def lines(rows: list[dict]) -> list[str]:
    said = []
    for row in rows:
        r = row["real"]
        real_words = ({CLOSED: f"real {r['r']:+.2f}R (${r['usd']:,.2f} before fees)" if r["r"] is not None
                       else "real R not given: the fill was at or under the planned stop",
                       OPEN: f"real open: {r['exited']} of {r['filled']} filled shares exited",
                       NOT_FILLED: "real not filled"}[r["state"]])
        m = row["model"]
        model_words = ("model ticket not in the published window" if m is None else
                       f"model {m['bucket']}" + (f" {m['r']:+.2f}R" if m["r"] is not None else ""))
        said.append(f"{row['ticket_id']}: {real_words}; {model_words}.")
    return said


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--positions", type=Path, required=True, help="a filled private copy of the template")
    parser.add_argument("--docs", type=Path, default=ROOT / "docs")
    parser.add_argument("--json", type=Path, default=None, help="write the comparison here (outside the repository)")
    args = parser.parse_args(argv)
    raw = args.positions.read_bytes()
    value = json.loads(raw)
    found = orders.schema_check.errors(value, {"$ref": "#/$defs/positions"}, orders.schema())
    if found:
        print("refused: the positions file does not meet its schema: " + "; ".join(found[:5]), file=sys.stderr)
        return 2
    from src import model_record
    rows = compare(value, model_record.offline(args.docs))
    for line in lines(rows):
        print(line)
    if args.json is not None:
        if args.json.resolve().is_relative_to(ROOT):
            print("refused: --json must be outside the repository", file=sys.stderr)
            return 2
        args.json.write_text(json.dumps(rows, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
