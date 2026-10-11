"""How many of a night's candidates the account could buy one whole share of.

A reading, not a check and not a rule. For every reaction candidate a
publication archived it sizes the production ticket again -- ``plan.burst_plan``
through ``entry_limit_study.current_plan``, the same cascade the run writes --
at the account the record archived, or at one given on the command line and
labelled a counterfactual, under three regimes: the record's own (``tonight``),
YELLOW and GREEN, each with the grade band that regime admits and the size
multiplier it applies. Per band it counts the mechanical A-band names without
a veto (the funnel's "potentially usable"), how many pass the stop rule and how
many size to at least one whole share, by mechanical grade beside the band, and
it prints the limit price under which one share fits a stop-constrained ticket
at that multiplier. Anticipation setups are read off their recorded plans
alone. It changes no record, decides nothing and fetches nothing; a YELLOW or
GREEN column on a RED night is a counterfactual, never a ticket, and a
whole-share count is not a trade, a fill or an edge.

    python tools/whole_share_feasibility.py docs/data.json
    python tools/whole_share_feasibility.py --git 43dcb8d7 --equity 2000 --risk-pct 0.5
    python tools/whole_share_feasibility.py --history --ref origin/main --limit 64 --json out.json --markdown out.md
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import breadth, pipeline, plan, reader_coverage  # noqa: E402
from tools import candidate_funnel as funnel_tool  # noqa: E402
from tools import entry_limit_study as study  # noqa: E402

VERSION = 1
POLICY = "whole_share_feasibility_v1"
#: the regimes a night is read under: its own, then the two that admit a ticket
BANDS = ("tonight", "yellow", "green")
GRADES = ("A+", "A", "B", "C", "skip")
#: the account's fields, in the order the reading prints them
ACCOUNT_FIELDS = ("equity", "risk_pct", "max_position_pct", "max_open_positions")


class FeasibilityError(RuntimeError):
    """The reading could not be made; nothing was printed as if it had."""


def publication(data: Any, source: str) -> dict:
    """A real schema-2 publication, or a refusal naming the source."""
    if (not isinstance(data, dict) or data.get("fixture") or data.get("schema_version") != 2
            or not isinstance(data.get("run"), dict) or not isinstance(data.get("app"), dict)
            or not isinstance(data.get("bursts"), list)):
        raise FeasibilityError(f"{source}: not a real schema-2 publication")
    return data


def account_for(record: dict, overrides: dict[str, Any] | None = None) -> tuple[plan.Account, str, dict | None]:
    """The account the reading sizes at, where it came from, and the record's
    own: ``archived`` when the record carries one and nothing overrides it,
    ``counterfactual`` when a command-line value replaces any field, and
    ``library_defaults`` for a record from before the account was archived."""
    recorded = record.get("account") if isinstance(record.get("account"), dict) else None
    archived = {k: recorded[k] for k in ACCOUNT_FIELDS} if recorded and all(k in recorded for k in ACCOUNT_FIELDS) else None
    base = dict(archived) if archived else plan.Account().to_dict()
    given = {k: v for k, v in (overrides or {}).items() if v is not None}
    if any(k not in ACCOUNT_FIELDS for k in given):
        raise FeasibilityError("an account override names a field the account does not have")
    try:
        account = plan.Account(**{**base, **given})
    except (TypeError, ValueError) as exc:
        raise FeasibilityError(f"account: {exc}") from exc
    source = "counterfactual" if given else ("archived" if archived else "library_defaults")
    return account, source, archived


def band_rules(record: dict, band: str) -> tuple[str | None, tuple[str, ...] | None, float]:
    """A band's verdict, the grades it admits to a plan and its size
    multiplier. ``tonight`` is the record's own regime read off its archived
    grade bands; YELLOW and GREEN are the module's regimes over those same
    archived bands -- counterfactual on a night that was not that colour."""
    rules = (record.get("rules") or {}).get("pipeline") if isinstance(record.get("rules"), dict) else None
    rules = rules if isinstance(rules, dict) else {}
    trade = rules["trade_grades"] if isinstance(rules.get("trade_grades"), list) else list(pipeline.TRADE_GRADES)
    yellow = rules["yellow_grades"] if isinstance(rules.get("yellow_grades"), list) else list(pipeline.YELLOW_GRADES)
    if band == "tonight":
        verdict = ((record.get("breadth") or {}).get("regime") or {}).get("verdict")
        multiplier = study.regime_multiplier(record)
    else:
        verdict, multiplier = band, breadth.SIZE_MULTIPLIER[band]
    admitted = tuple(reader_coverage.admitted(verdict, trade, yellow)) if verdict in breadth.SIZE_MULTIPLIER else None
    return verdict, admitted, multiplier


def one_share_ceilings(account: plan.Account, multiplier: float) -> dict[str, float]:
    """The limit price under which one whole share fits, floored to the cent:
    for a ticket whose stop sits on his MAX_STOP_PCT line (the risk halved by
    plan.STOP_RISK_MULTIPLIER, as every stop-constrained ticket is) and for one
    whose stop sits at his IDEAL_STOP_PCT (full risk). plan.size() needs the
    risk per share, in cents, no more than the budget, in cents."""
    budget = plan._money(account.equity * account.risk_pct / 100 * multiplier)
    halved = plan._money(budget * plan.STOP_RISK_MULTIPLIER)
    return {"risk_budget": budget, "risk_budget_at_stop_line": halved,
            "stop_line": study.floor_to_cents(halved / (plan.MAX_STOP_PCT / 100)),
            "ideal_stop": study.floor_to_cents(budget / (plan.IDEAL_STOP_PCT / 100))}


def _sized(row: dict, account: plan.Account, multipliers: set[float]) -> dict[float, dict] | str:
    """The production ticket at each multiplier, or why the row cannot be sized."""
    why = study.usable_bar(row)
    if why:
        return why
    out = {}
    for m in multipliers:
        try:
            p = study.current_plan(row, m, account)
        except (ValueError, KeyError) as exc:   # the pipeline logs and skips; so does this
            return str(exc)[:80]
        out[m] = {"eligible": bool(p["eligible"]), "shares": int(p["shares"]), "limit": p["limit"],
                  "stop_pct": p["stop_pct"], "risk_per_share": p["risk_per_share"],
                  "total_multiplier": p["multipliers"]["total"], "capped_by": p["capped_by"]}
    return out


def _tally() -> dict[str, int]:
    return {"candidates": 0, "eligible": 0, "whole_share": 0, "no_share": 0}


def _count(tally: dict[str, int], sized: dict) -> None:
    tally["candidates"] += 1
    if sized["eligible"]:
        tally["eligible"] += 1
        tally["whole_share" if sized["shares"] >= 1 else "no_share"] += 1


def reading(data: dict, *, source: str, identity: str, overrides: dict[str, Any] | None = None) -> dict:
    """One publication's whole-share feasibility under the three bands."""
    record = publication(data, source)
    run = record["run"]
    account, account_source, archived = account_for(record, overrides)
    bands = {b: band_rules(record, b) for b in BANDS}
    multipliers = {m for _, _, m in bands.values()}
    tallies = {b: {"in_band": _tally(), "by_mechanical_grade": {g: _tally() for g in GRADES}} for b in BANDS}
    missing: list[dict[str, str]] = []
    rows = 0
    for row in record["bursts"]:
        if not isinstance(row, dict):
            missing.append({"ticker": None, "why": "row is not an object"})
            continue
        sized = _sized(row, account, multipliers)
        if isinstance(sized, str):
            missing.append({"ticker": row.get("ticker"), "why": sized})
            continue
        rows += 1
        grade = row.get("grade_mechanical")
        vetoed = bool(row.get("vetoes"))
        for band, (_, admitted, m) in bands.items():
            at = sized[m]
            if grade in GRADES:
                _count(tallies[band]["by_mechanical_grade"][grade], at)
            if admitted is not None and grade in admitted and not vetoed:
                _count(tallies[band]["in_band"], at)
    anticipation = {"listed": 0, "eligible": 0, "whole_share": 0, "unreadable": 0}
    for row in ((record.get("watchlist") or {}).get("top") or []) if isinstance(record.get("watchlist"), dict) else []:
        anticipation["listed"] += 1
        p = row.get("plan") if isinstance(row, dict) else None
        if not isinstance(p, dict) or not isinstance(p.get("shares"), int) or isinstance(p.get("shares"), bool):
            anticipation["unreadable"] += 1
            continue
        if p.get("eligible") is True:
            anticipation["eligible"] += 1
            if p["shares"] >= 1:
                anticipation["whole_share"] += 1
    return {
        "source": source, "identity": identity,
        "session": run.get("session"), "session_state": run.get("session_state"),
        "published_at": run.get("published_at"), "rules_version": record["app"].get("rules_version"),
        "regime": bands["tonight"][0],
        "account": {"used": account.to_dict(), "source": account_source, "archived": archived},
        "candidates": rows, "missing_inputs": missing,
        "bands": {b: {"verdict": v, "admitted": list(a) if a is not None else None, "multiplier": m,
                      "ceilings": one_share_ceilings(account, m), **tallies[b]}
                  for b, (v, a, m) in bands.items()},
        # the recorded plans only: the account and regime they were sized at
        # are the record's own, whatever account this reading sized the bursts at
        "anticipation": {**anticipation, "basis": "recorded plans at the record's own account and regime"},
    }


def _triple(t: dict[str, int]) -> str:
    return f"{t['candidates']} / {t['eligible']} / {t['whole_share']}"


def table(readings: list[dict]) -> str:
    head = ("| session | regime | account | sized | tonight: in band / stop ok / 1+ share | yellow (A+) | green (A+/A) | "
            "one-share ceiling at the stop line, yellow / green | anticipation listed / 1+ share |",
            "|---|---|---|---:|---|---|---|---|---|")
    rows = []
    for r in readings:
        acct = r["account"]["used"]
        rows.append("| {session} | {regime} | ${equity:,.0f} / {risk:g}% ({src}) | {sized} | {t} | {y} | {g} | ${cy:,.2f} / ${cg:,.2f} | {al} / {aw} |".format(
            session=r["session"], regime=r["regime"] or "unknown", equity=acct["equity"], risk=acct["risk_pct"],
            src=r["account"]["source"], sized=r["candidates"], t=_triple(r["bands"]["tonight"]["in_band"]),
            y=_triple(r["bands"]["yellow"]["in_band"]), g=_triple(r["bands"]["green"]["in_band"]),
            cy=r["bands"]["yellow"]["ceilings"]["stop_line"], cg=r["bands"]["green"]["ceilings"]["stop_line"],
            al=r["anticipation"]["listed"], aw=r["anticipation"]["whole_share"]))
    return "\n".join(head + tuple(rows))


def totals(readings: list[dict]) -> dict:
    out: dict[str, Any] = {"publications": len(readings), "sessions": len({r["session"] for r in readings}),
                           "regimes": {}, "candidates": 0, "missing_inputs": 0,
                           "accounts": {}, "bands": {b: {"in_band": _tally(), "by_mechanical_grade": {g: _tally() for g in GRADES}} for b in BANDS},
                           "anticipation": {"listed": 0, "eligible": 0, "whole_share": 0, "unreadable": 0}}
    for r in readings:
        key = r["regime"] or "unknown"
        out["regimes"][key] = out["regimes"].get(key, 0) + 1
        out["candidates"] += r["candidates"]
        out["missing_inputs"] += len(r["missing_inputs"])
        acct = r["account"]["used"]
        label = f"${acct['equity']:,.0f} / {acct['risk_pct']:g}% ({r['account']['source']})"
        out["accounts"][label] = out["accounts"].get(label, 0) + 1
        for b in BANDS:
            for k in out["bands"][b]["in_band"]:
                out["bands"][b]["in_band"][k] += r["bands"][b]["in_band"][k]
            for g in GRADES:
                for k in out["bands"][b]["by_mechanical_grade"][g]:
                    out["bands"][b]["by_mechanical_grade"][g][k] += r["bands"][b]["by_mechanical_grade"][g][k]
        for k in out["anticipation"]:
            out["anticipation"][k] += r["anticipation"][k]
    return out


def summary_text(t: dict) -> str:
    def band(b: str) -> str:
        i = t["bands"][b]["in_band"]
        return f"{b}: {i['candidates']} in band, {i['eligible']} past the stop rule, {i['whole_share']} sizing to a whole share"
    return (f"{t['publications']} publications over {t['sessions']} sessions; regimes {t['regimes']}; "
            f"{t['candidates']} candidates sized, {t['missing_inputs']} with unusable inputs; accounts {t['accounts']}. "
            + "; ".join(band(b) for b in BANDS)
            + f". Anticipation: {t['anticipation']['listed']} listed, {t['anticipation']['eligible']} eligible, "
            f"{t['anticipation']['whole_share']} with a whole share, as recorded.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("records", nargs="*", type=Path, help="publication files (.json or .json.gz)")
    parser.add_argument("--git", nargs="+", default=[], metavar="COMMIT", help="read docs/data.json at these commits")
    parser.add_argument("--history", action="store_true", help="every commit on --ref that changed docs/data.json")
    parser.add_argument("--ref", default="origin/main")
    parser.add_argument("--limit", type=int, default=funnel_tool.HISTORY_LIMIT)
    parser.add_argument("--equity", type=float, help="size at this equity instead of the archived account (a counterfactual)")
    parser.add_argument("--risk-pct", type=float, help="size at this risk per trade instead of the archived account")
    parser.add_argument("--max-position-pct", type=float, help="cap a position at this share of equity instead of the archived account")
    parser.add_argument("--json", type=Path, help="write the readings and totals here")
    parser.add_argument("--markdown", type=Path, help="write the table here")
    args = parser.parse_args(argv)
    overrides = {"equity": args.equity, "risk_pct": args.risk_pct, "max_position_pct": args.max_position_pct}
    try:
        readings = []
        for path in args.records:
            data, sha = funnel_tool.read_file(path)
            readings.append(reading(data, source=str(path), identity=f"sha256:{sha}", overrides=overrides))
        for commit in args.git:
            data, blob, full = funnel_tool.read_commit(commit)
            readings.append(reading(data, source=f"{full[:8]}:{funnel_tool.RECORD_PATH}", identity=f"blob:{blob}", overrides=overrides))
        skipped = []
        for commit in (funnel_tool.history_commits(args.ref, args.limit) if args.history else []):
            try:
                data, blob, full = funnel_tool.read_commit(commit)
                readings.append(reading(data, source=f"{full[:8]}:{funnel_tool.RECORD_PATH}", identity=f"blob:{blob}", overrides=overrides))
            except (ValueError, KeyError, TypeError, AttributeError, FeasibilityError, funnel_tool.FunnelError) as exc:
                skipped.append({"commit": commit, "reason": str(exc)})
    except (OSError, ValueError, KeyError, TypeError, FeasibilityError, funnel_tool.FunnelError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    if not readings:
        parser.error("give a record, --git commits or --history")
    readings.sort(key=lambda r: ((r["session"] or ""), (r["published_at"] or "")))
    summary = totals(readings)
    print(table(readings))
    print()
    print(summary_text(summary))
    for row in skipped:
        print(f"skipped {row['commit'][:8]}: {row['reason']}")
    if args.markdown:
        args.markdown.write_text(table(readings) + "\n")
    if args.json:
        args.json.write_text(json.dumps({"version": VERSION, "policy": POLICY, "ref": args.ref if args.history else None,
                                         "overrides": {k: v for k, v in overrides.items() if v is not None},
                                         "readings": readings, "skipped": skipped, "totals": summary},
                                        indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
