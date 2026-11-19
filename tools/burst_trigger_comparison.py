#!/usr/bin/env python3
"""The burst trigger rule, read both ways over the retained publications.

A reading, not a check and not a rule. It changes no production number, no
record, no regime and no scorecard; it writes nothing but its own output
file; and it is not a backtest of the live policy. It answers the question
the owner's decision of 19 November 2026 (``plan.burst_trigger_rule``)
leaves: what moving a burst ticket's buy stop from the close
(``close``, the legacy rule) to the close plus ``plan.trigger_cushion()``
(``close_plus_cushion``) does to the tickets the mechanics write, and to
how they come out on daily bars.

The method is the frozen signal-outcome study (``tools/signal_outcomes.py``)
run twice over one population, unchanged except for the rule each ticket is
built under: its loading (every publication held to its blob), its bar
gathering (the newest publication wins), its basis check, its walk
(``record.replay``) and its summary. Nothing is gated, there is no slot cap
and no reader, as in the study. The population is the 7 November
extension's publications plus every later publication of ``docs/data.json``
on the pinned ref, the first of each session ticketed.

Beside the study's own summary, each ticket's first day is placed against
its own lines (``open_position()``): under the stop, under the skip-below
line, under the buy stop, exactly at it, between it and the limit, over the
limit up to the day-2 line, and over that. An open under the buy stop is the
case a buy stop can still be entered for as written before the open
(Fidelity's stated rule takes a buy stop only above the current price:
``knowledge/broker-fidelity.md``).

    python tools/burst_trigger_comparison.py --ref <commit>     # write
    python tools/burst_trigger_comparison.py --ref <commit> --check
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import plan, record  # noqa: E402
from tools import signal_outcomes as so  # noqa: E402

VERSION = "burst-trigger-comparison-v1"
BASE_SPEC = ROOT / "docs" / "input-truthfulness" / "2026-11-07-signal-outcomes-spec-extended.json"
OUT = ROOT / "docs" / "input-truthfulness" / "2026-11-19-burst-trigger-comparison" / "comparison.json"
#: the first day's open against a ticket's own lines, low to high
POSITIONS = ("at_or_under_stop", "under_skip_line", "under_buy_stop", "at_buy_stop", "in_band",
             "over_limit_to_day2", "over_day2", "no_first_day")


class ComparisonError(RuntimeError):
    """The population or a publication could not be read as it must be."""


def _git(*args: str) -> bytes:
    done = subprocess.run(["git", *args], cwd=ROOT, capture_output=True)
    if done.returncode != 0:
        raise ComparisonError("git could not produce " + " ".join(args[-2:]))
    return done.stdout


def population(ref: str, base_spec: dict) -> list[dict]:
    """The base spec's publications, then every commit on ``ref``'s first
    parent that changed ``docs/data.json`` after the base spec's newest, held
    to the blob it carries; a commit whose record is not a real schema-2
    publication is skipped by name (the first build's records among them)."""
    entries = [dict(e) for e in base_spec["publications"]]
    known = {e["commit"] for e in entries}
    newest = entries[-1]["commit"]
    log = _git("log", "--first-parent", "--reverse", "--format=%H", f"{newest}..{ref}", "--", "docs/data.json")
    for commit in log.decode().split():
        if commit in known:
            continue
        blob = _git("rev-parse", f"{commit}:docs/data.json").decode().strip()
        data = json.loads(_git("cat-file", "-p", f"{commit}:docs/data.json"))
        session = (data.get("run") or {}).get("session")
        if data.get("fixture") or data.get("schema_version") != 2 or not session:
            continue
        entries.append({"commit": commit, "session": session, "blob": blob})
    return entries


def spec_of(base_spec: dict, entries: list[dict]) -> dict:
    """The study's spec over this population: the base spec's rules
    verbatim, its publication list replaced, its digest over the bytes."""
    spec = {k: v for k, v in base_spec.items() if not k.startswith("_")}
    spec["publications"] = entries
    raw = json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()
    return {**spec, "_sha256": hashlib.sha256(raw).hexdigest()}


def ticket_under(rule: str):
    """``signal_outcomes.ticket`` with the trigger rule named, its inputs
    otherwise the study's own."""
    def ticket(row: dict, account: plan.Account):
        try:
            p = plan.burst_plan(ticker=row["ticker"], close=row["close"], low=row["low"], high=row["high"],
                                open_=row["open"], prev_close=row["prev_close"], gain_pct=row.get("gain_pct") or 0.0,
                                account=account, size_multiplier=so.UNGATED["size_multiplier"],
                                scan="dollar" if row.get("scan") == "dollar" else "4pct",
                                extension_pct=row.get("extension_pct"), trigger_rule=rule)
        except (ValueError, TypeError, KeyError) as exc:
            return None, so.PLAN_ERROR, f"{type(exc).__name__}: {exc}"
        if not p.get("eligible") or p.get("action") not in plan.ORDER_ACTIONS or not p.get("shares"):
            return None, so.NO_TICKET, p.get("reason") or p.get("action")
        return p, None, None
    return ticket


def open_position(ticket: dict, first: dict | None) -> str:
    """Where the first day's open sits against the ticket's own lines."""
    if first is None:
        return "no_first_day"
    o = float(first["o"])
    if o <= ticket["stop"]:
        return "at_or_under_stop"
    if o < ticket["entry_low"]:
        return "under_skip_line"
    if o < ticket["entry_ref"]:
        return "under_buy_stop"
    if o == ticket["entry_ref"]:
        return "at_buy_stop"
    if o <= ticket["limit"]:
        return "in_band"
    if o <= ticket["day2_spent_above"]:
        return "over_limit_to_day2"
    return "over_day2"


def read(publications: list[dict], spec: dict, rule: str) -> dict:
    """The study under one rule, and the first-day open of each ticket."""
    with mock.patch.object(so, "ticket", ticket_under(rule)):
        result = so.study(publications, spec)
    bars, _ = so.gather_bars(publications)
    positions: Counter = Counter()
    admitted: Counter = Counter()
    withheld: Counter = Counter()
    for row in result["rows"]:
        if row["bucket"] == so.NO_TICKET:
            withheld[(row.get("reason") or "")[:len("ticket withheld")] == "ticket withheld"] += 1
        if row["ticket"] is None:
            continue
        after = sorted(d for d in bars.get(row["ticker"], {}) if d > row["session"])
        first = bars[row["ticker"]][after[0]] if after else None
        where = open_position(row["ticket"], first)
        positions[where] += 1
        if row["stratum"] == so.ADMITTED:
            admitted[where] += 1
    summary = result["summary"]
    keep = ("rows", "buckets", "settled", "night_bootstrap", "uncertain_bound", "costs_per_side_bps")
    return {"rule": rule,
            "all": {k: summary["all"][k] for k in keep},
            "admitted": {k: summary["strata"][so.ADMITTED][k] for k in keep},
            "uncertainty": dict(sorted(Counter(r["uncertainty"] for r in result["rows"]
                                               if r["bucket"] == record.UNCERTAIN).items())),
            "withheld_by_the_stop_rule": withheld[True],
            "first_day_open": {p: positions[p] for p in POSITIONS},
            "first_day_open_admitted": {p: admitted[p] for p in POSITIONS}}


def build(ref: str) -> dict:
    base = json.loads(BASE_SPEC.read_text())
    entries = population(ref, base)
    spec = spec_of(base, entries)
    publications = so.load_publications(spec)
    firsts = so.first_publications(publications)
    return {"version": VERSION, "ref": _git("rev-parse", ref).decode().strip(),
            "base_spec": BASE_SPEC.relative_to(ROOT).as_posix(),
            "base_spec_sha256": hashlib.sha256(BASE_SPEC.read_bytes()).hexdigest(),
            "spec_sha256": spec["_sha256"],
            "publications": len(publications), "nights": len(firsts),
            "first_session": firsts[0]["session"], "newest_session": max(p["session"] for p in publications),
            "cushion": {"cents": plan.TRIGGER_CENTS, "fraction": plan.TRIGGER_FRACTION},
            "rules": {rule: read(publications, spec, rule) for rule in plan.BURST_TRIGGER_RULES}}


def encoded(result: dict) -> str:
    return json.dumps(result, indent=1, sort_keys=True) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ref", required=True, help="the commit whose first-parent history is read")
    parser.add_argument("--check", action="store_true", help="refuse unless the committed file is what this writes")
    args = parser.parse_args(argv)
    try:
        text = encoded(build(args.ref))
    except (ComparisonError, so.StudyError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    if args.check:
        if not OUT.exists() or OUT.read_text() != text:
            print(f"stale: {OUT.relative_to(ROOT)} is not what the comparison writes", file=sys.stderr)
            return 1
        print(f"current: {OUT.relative_to(ROOT)}")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
