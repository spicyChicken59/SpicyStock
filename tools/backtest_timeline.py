"""A price-free, ticker-free timeline read off the owner's private backtest.

``tools/historical_backtest.py`` writes two things: ``backtest.json``, every
night and every walked plan with its prices and its tickers, which stays on
the owner's computer, and ``summary.txt``, the totals, which is what has
been pasted and committed. So the site can draw the February--September
market only as two numbers, while the published nights it replays
(``docs/historical-findings.json``) are drawn night by night. This tool is
the row between the two: the owner runs it over the private file and gets
one row per night per gate that carries what the night's market read, what
the policy did with it and how its plans came out -- counts, ratios,
verdicts and R -- and nothing that could name a stock or quote a price, so
the page can draw the backtest's nights the way it draws the published
ones.

It is a READER. It changes no number of the backtest's: every value is
copied off the night row ``historical_backtest.measure()`` and ``decide()``
wrote, or counted and summed over the rows ``record.scorecard_rows()``
walked for that night, joined on the session the plan was picked on. Its
only arithmetic is a night's wins, losses, breakeven, the ``math.fsum`` of
its settled R, their mean and their median, rounded once.

What it never carries, checked before a byte is written: no key named
``ticker``, ``entry_ref``, ``entry_low``, ``entry_high``, ``limit``,
``stop``, ``trigger``, ``position_usd``, ``order_json``, ``targets``,
``day2_spent_above``, ``evidence_ref`` or ``candidates`` anywhere in the
output (``PRIVATE_KEYS``), and no string value equal to a ticker the
private file names, in a night's ``trades``, its ``candidates``, a walked
row or a pick. A leak is a refusal, not a warning. The one block of the
private file that can carry both by another name -- a shortened lookback's
equivalence ``differences``, which are fingerprints of candidates and
plans -- is reduced to its count.

It refuses, with a sentence and exit code 2: a file whose ``version`` is
not the backtest's own; a file missing either gate's nights or outcomes; a
walked plan picked on a session no night row evaluated; and a night whose
walked plans are not its tickets, because a timeline that said "2 tickets"
over one walked plan would be the lie the backtest's own conservation
check exists to refuse.

    python tools/backtest_timeline.py --backtest <private backtest.json> --output <file>

writes the timeline and prints one line of counts; without ``--output``
the timeline goes to stdout. The output may go anywhere -- it is public by
construction -- and the private file is read where it is and never copied.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import record  # noqa: E402
from tools.historical_backtest import GATES, VERSION as BACKTEST_VERSION  # noqa: E402

VERSION = "backtest-timeline-v1"
#: the keys of the private file that carry a price, a name or the block that
#: carries both; none may appear anywhere in the output, under any parent
PRIVATE_KEYS = frozenset({"ticker", "entry_ref", "entry_low", "entry_high", "limit", "stop", "trigger",
                          "position_usd", "order_json", "targets", "day2_spent_above", "evidence_ref", "candidates"})
#: where the private file names a ticker: every string here is a name the
#: output may not carry as a value
TICKER_FIELDS = ("trades", "candidates", "rows", "picks")
#: the Market Monitor's reading of the night, copied off the night's regime
REGIME_FIELDS = ("verdict", "ratio_10d", "ratio_5d", "up4", "down4", "up4_10d", "down4_10d", "universe")
#: the night's counts, copied off the night row as the backtest wrote them
COPIED = ("counted", "measured", "bursts", "grades", "eligible_plans", "cut", "slots_held")
#: the run's own context, copied into ``source`` (``lookback`` with its
#: equivalence differences reduced to a count, see ``lookback_of()``)
SOURCE_FIELDS = ("evaluated", "regimes", "account")
#: decimals of a night's summed and median R, as ``record.summarize_scorecard`` rounds them
R_DECIMALS = 2
#: decimals of a night's mean R: a night holds a handful of plans, so the
#: mean is kept one place finer than the sum it is read from
MEAN_DECIMALS = 3
SETTLED = "settled"


class TimelineError(RuntimeError):
    """A refusal, named; never a guess."""


# ------------------------------------------------------------- the rows ----


def settled_block(rs: list[float]) -> dict:
    """Wins, losses, breakeven and the three R figures over one night's
    settled R values; the sums are None on a night that settled nothing."""
    n = len(rs)
    return {"n": n, "wins": sum(r > 0 for r in rs), "losses": sum(r < 0 for r in rs),
            "breakeven": sum(r == 0 for r in rs),
            "sum_r": round(math.fsum(rs), R_DECIMALS) if rs else None,
            "mean_r": round(math.fsum(rs) / n, MEAN_DECIMALS) if rs else None,
            "median_r": round(statistics.median(rs), R_DECIMALS) if rs else None}


def night_row(night: dict, rows: list[dict]) -> dict:
    """One timeline row: the night's regime and counts copied, the number of
    its tickets (never their names), and its walked plans counted by bucket
    and by the kind of uncertainty, its settled R listed sorted and summed."""
    regime = night.get("regime") or {}
    out = {"session": night["session"], **{k: regime.get(k) for k in REGIME_FIELDS},
           "reason": regime.get("reason"), **{k: night[k] for k in COPIED},
           "tickets": len(night["trades"])}
    if len(rows) != out["tickets"]:
        raise TimelineError(f"{night['session']}: {out['tickets']} tickets but {len(rows)} walked plans; "
                            "the timeline refuses to describe a population the night did not issue")
    rs = sorted(r["r"] for r in rows if r["bucket"] == SETTLED)
    out["buckets"] = {bucket: sum(r["bucket"] == bucket for r in rows) for bucket in record.SCORECARD_BUCKETS}
    out["settled"] = settled_block(rs)
    out["r"] = rs
    kinds = [r["uncertainty"] for r in rows if r["bucket"] == record.UNCERTAIN]
    out["uncertainty"] = {kind: kinds.count(kind) for kind in record.UNCERTAIN_REASONS if kind in kinds}
    return out


def gate_rows(private: dict, gate: str) -> list[dict]:
    """Every night of one gate in the file's own order, each joined to the
    walked plans picked on its session; a plan on a session no night
    evaluated is refused by name."""
    nights = private["nights"][gate]
    by_session: dict[str, list[dict]] = defaultdict(list)
    for row in private["outcomes"][gate]["rows"]:
        by_session[row["picked"]].append(row)
    unknown = sorted(set(by_session) - {n["session"] for n in nights})
    if unknown:
        raise TimelineError(f"{gate}: walked plans picked on {', '.join(unknown)}, sessions no night row evaluated")
    return [night_row(n, by_session.get(n["session"], [])) for n in nights]


# ------------------------------------------------------------ the output ----


def tickers_of(private: dict) -> frozenset[str]:
    """Every name the private file carries, wherever it carries one."""
    names: set[str] = set()
    for gate in GATES:
        for night in private["nights"][gate]:
            names.update(night.get("trades", []))
            names.update(c["ticker"] for c in night.get("candidates", []) if c.get("ticker"))
        for field in ("rows", "picks"):
            names.update(r["ticker"] for r in private["outcomes"][gate].get(field, []) if r.get("ticker"))
    return frozenset(names)


def private_leaks(value, tickers: frozenset[str], path: str = "timeline") -> list[str]:
    """Every place a private key or a ticker value sits in ``value``, by path."""
    leaks = []
    if isinstance(value, dict):
        for key, inner in value.items():
            here = f"{path}.{key}"
            if key in PRIVATE_KEYS:
                leaks.append(f"{here} (private key)")
            leaks += private_leaks(inner, tickers, here)
    elif isinstance(value, list):
        for i, inner in enumerate(value):
            leaks += private_leaks(inner, tickers, f"{path}[{i}]")
    elif isinstance(value, str) and value in tickers:
        leaks.append(f"{path} (a ticker)")
    return leaks


def lookback_of(private: dict) -> dict:
    """The lookback block with its equivalence differences, which are
    fingerprints of candidates and plans, reduced to how many there were."""
    lookback = dict(private["lookback"])
    equivalence = dict(lookback.get("equivalence") or {})
    equivalence["differences"] = len(equivalence.get("differences") or [])
    lookback["equivalence"] = equivalence
    return lookback


def validate(private: dict) -> None:
    if private.get("version") != BACKTEST_VERSION:
        raise TimelineError(f"not a {BACKTEST_VERSION} file: version {private.get('version')!r}")
    for block in ("nights", "outcomes"):
        missing = [gate for gate in GATES if gate not in (private.get(block) or {})]
        if missing:
            raise TimelineError(f"{block} missing the {', '.join(missing)} gate")


def build(private: dict, *, path: Path, digest: str) -> dict:
    """The timeline over one private file, swept for a private key or a
    ticker before it is returned; a leak is a refusal."""
    validate(private)
    out = {"version": VERSION, "reader": private["reader"], "limitations": list(private["limitations"]),
           "source": {"path": Path(path).name, "sha256": digest, "backtest_version": private["version"],
                      "rules_version": private["rules_version"], "lookback": lookback_of(private),
                      **{k: private[k] for k in SOURCE_FIELDS}},
           "gates": {gate: gate_rows(private, gate) for gate in GATES}}
    leaks = private_leaks(out, tickers_of(private))
    if leaks:
        raise TimelineError("the timeline would carry what the private file keeps private: " + "; ".join(leaks))
    return out


def read(path: Path) -> dict:
    """The timeline of the private file at ``path``, read where it is."""
    data = Path(path).read_bytes()
    return build(json.loads(data), path=path, digest=hashlib.sha256(data).hexdigest())


def encode(timeline: dict) -> str:
    return json.dumps(timeline, indent=1, sort_keys=True) + "\n"


def counts_line(timeline: dict, written: Path | None) -> str:
    parts = []
    for gate in GATES:
        rows = timeline["gates"][gate]
        parts.append(f"{gate}: {len(rows)} sessions, {sum(r['tickets'] for r in rows)} tickets, "
                     f"{sum(r['settled']['n'] for r in rows)} settled")
    where = f"; written {written}" if written else ""
    return f"timeline {timeline['version']} over {timeline['source']['path']}: " + "; ".join(parts) + where


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backtest", type=Path, required=True, help="the private backtest.json, read where it is")
    parser.add_argument("--output", type=Path, default=None,
                        help="where to write the timeline (anywhere: it carries no price and no ticker); stdout if omitted")
    args = parser.parse_args(argv)
    try:
        timeline = read(args.backtest)
        text = encode(timeline)
        if args.output is None:
            print(text, end="")
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding="utf-8")
            print(counts_line(timeline, args.output))
        return 0
    except (TimelineError, ValueError, KeyError, TypeError, OSError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
