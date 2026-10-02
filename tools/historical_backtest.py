"""Mechanical replay of the nightly decision over a recovered historical archive.

The question this answers is the one every prospective night postpones: what
would THIS build's rules have decided, and what would those decisions have
done, over the sessions a recovered acquisition package holds. It is the
run's own stages called the way ``pipeline.run_evening()`` calls them, one
session at a time, over the bars of one archive:

* the session rules (``market_data.apply_session_rules``) and the $3 policy
  (``universe.session_eligible``) over the names that printed that session;
* the Market Monitor (``breadth.snapshot``) and its regime;
* the two reaction scans and the checklist grade (``pipeline.scan_frames``),
  ranked as the run ranks them;
* the constrained ticket, the slot cap and the cash budget
  (``pipeline._make_plans`` with the open model plans of the sessions before
  it counted against the slots, as the run counts them);
* the record (``record.append``), the fill rule, the five-session walk and
  the quantity-weighted R (``record.scorecard_rows``, the same function the
  published scorecard reads, over the whole archive instead of its
  sixty-session window), and the same denominators
  (``record.summarize_scorecard``).

Every number is the module's; this file holds none of its own. It makes no
provider, model or network call: the socket guard ``historical_reconcile``
uses is held for the whole run.

What it is NOT, said once here and again in its output:

* **The reader is NOT RUN.** The chart reader can only lower a mechanical
  grade, so every name's mechanical grade is the CEILING of its final grade
  and every ticket here is one the reader could still have refused. The
  ticket SET is not a superset of the live run's: a reader downgrade frees a
  slot the next-ranked name takes, so the live run can hold a ticket this
  replay's slot cap cut.
* **The universe is the archive's.** A recovered package carries the names
  the acquisition was frozen over -- a later directory's membership -- so a
  name that left the market before the archive was cut is not in it.
  Survivorship flatters both the regime (its decliners are under-counted)
  and the candidates; neither bias is measured here, only named.
* **It is not the original information set** on any session but the ones
  the archive was acquired for, and not even those (see the reconciliation).
* **It is a model of daily bars**: a fill is booked only at the next open
  inside the ticket; a day the bar cannot read is ``uncertain`` and scored
  nowhere, exactly as the published scorecard does.
* **A second block removes the regime gate** and is labelled a
  counterfactual. It exists to show what the gate refused, never as a
  policy; the production block is the strategy's own answer.

A lookback shorter than the run's own (``pipeline.LOOKBACK_DAYS``) makes
more sessions evaluable, because every session needs that many sessions of
history before it. A shortened lookback is admitted only with its
equivalence check: on every evaluable session that also has the full
lookback, both are run and compared -- regime, every candidate's grade and
score, every plan's prices and shares -- and a single difference is a FAIL
printed first, because a grade read off a shorter history is not the run's.

    python tools/historical_backtest.py --manifest <acquisition-manifest.json>
        --storage <recovered package> --output <private directory>
        [--lookback N] [--sessions N]

``--output`` receives ``backtest.json`` (every row, with prices: private)
and ``summary.txt`` (counts, R and verdicts only, no price: pasteable).
Both the storage and the output must sit outside any Git checkout.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
import json
import logging
import math
from pathlib import Path
import statistics
import sys
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import breadth, market_data, pipeline, plan, record, report, sessions, universe  # noqa: E402
from tools.historical_acquisition import cached_pages, resolved_query, validate_manifest  # noqa: E402
from tools.historical_normalization import COMPACT_PROJECTION, frames_for_replay, normalize_pages  # noqa: E402
from tools.historical_reconcile import network_blocked  # noqa: E402

VERSION = "historical-backtest-v1"
#: the run's own lookback: what every production frame carries before its session
PRODUCTION_LOOKBACK = pipeline.LOOKBACK_DAYS
BENCHMARK = pipeline.BENCHMARK_SYMBOL
#: a universe source that is neither the seed nor an explicit list, so the
#: $3 policy applies to every name as it does on a directory night
ARCHIVE_SOURCE = "historical_archive"
#: the two blocks every run reports; the second is a counterfactual
PRODUCTION, NO_GATE = "production", "no_regime_gate"
GATES = (PRODUCTION, NO_GATE)
#: the regime handed to the counterfactual block: the gate removed, nothing else
UNGATED_REGIME = {"verdict": "green", "size_multiplier": breadth.SIZE_MULTIPLIER["green"],
                  "reasons": ["counterfactual: the regime gate is removed; sizing at the full multiplier"]}
READER = "NOT RUN: the mechanical grade is the ceiling of what the reader could have admitted"
LIMITATIONS = (
    "The reader is not run; every ticket here is one the reader could still have refused.",
    "The universe is the archive's later membership; names that left the market are absent "
    "(survivorship), so the regime's decliners and the candidates are both under-counted.",
    "The bars are a later retrieval, not the original information set, and partial names stay partial.",
    "Fills, exits and R are the daily-bar model of the published scorecard: a fill only at the next "
    "open inside the ticket, uncertain days scored nowhere, no fee, spread or slippage.",
    "The counterfactual block removes the regime gate to show what it refused; it is not a policy.",
    "Counts are not an edge claim; the public scorecard reads no rate under its own minimum.",
)


class BacktestError(RuntimeError):
    """A refusal, named; never a guess."""


# -------------------------------------------------------------- archive ----


@dataclass
class Archive:
    frames: dict[str, pd.DataFrame]
    intended: list[str]
    price_exempt: tuple[str, ...]
    statuses: dict[str, str]
    manifest_sha256: str
    queries: list[str]
    non_terminal: list[str]
    #: every symbol's bar dates, read once, for ``as_of()``
    dates: dict[str, np.ndarray] = field(default_factory=dict)
    #: every XNYS session from the earliest bar to the latest, holes included
    calendar: list[date] = field(default_factory=list)


def _outside_git(path: Path, what: str) -> Path:
    path = Path(path).resolve()
    if path == ROOT or ROOT in path.parents or any((p / ".git").exists() for p in [path, *path.parents]):
        raise BacktestError(f"{what} must stay outside any Git checkout")
    return path


def load_archive(manifest: dict, storage: Path) -> Archive:
    """Every canonical bulk query's frames, read through the acquisition's own
    cache and normalization, newest target session first; a symbol two
    targets both carried keeps the newer target's frame. The access probe is
    never a frame source. Nothing is fetched."""
    identity = validate_manifest(manifest)
    storage = _outside_git(storage, "the recovered package")
    queries = [q for q in manifest["queries"] if q.get("purpose") == "canonical" and q.get("scope") != "probe"]
    if not queries:
        raise BacktestError("the manifest has no canonical bulk query")
    queries.sort(key=lambda q: q["target_session"], reverse=True)
    frames: dict[str, pd.DataFrame] = {}
    statuses: dict[str, str] = {}
    non_terminal: list[str] = []
    with network_blocked():
        for q in queries:
            cached = cached_pages(manifest, storage, q["id"])
            resolved = resolved_query(manifest, q["id"])
            if not cached["terminal"]:
                non_terminal.append(q["id"])
            normalized = normalize_pages(cached["pages"], query=resolved, terminal=cached["terminal"],
                                         target_session=resolved["target_session"],
                                         required_sessions=resolved.get("required_sessions"))
            subset, _ = frames_for_replay(normalized, projection_contract=COMPACT_PROJECTION)
            for symbol, df in subset.items():
                frames.setdefault(symbol, df)
            for symbol, row in normalized["symbols"].items():
                statuses.setdefault(symbol, row["status"])
    intended = sorted({s for pop in manifest["populations"].values() for s in pop["symbols"]})
    exempt = tuple(sorted({s for pop in manifest["populations"].values() for s in pop.get("price_exempt", [])}))
    archive = Archive(frames=frames, intended=intended, price_exempt=exempt, statuses=statuses,
                      manifest_sha256=identity, queries=[q["id"] for q in queries], non_terminal=non_terminal)
    archive.dates = {s: breadth._bar_dates(df.index) for s, df in frames.items()}
    archive.calendar = market_data.session_calendar(frames)
    return archive


def as_of(archive: Archive, session: date, lookback: int) -> dict[str, pd.DataFrame]:
    """The frames a run on ``session`` would have fetched: the ``lookback``
    sessions before it and the session itself, nothing later. A name with no
    bar in that span is absent, as an unanswered name is on a live night."""
    first = np.datetime64(sessions.sessions_before(session, lookback)[0], "D")
    last = np.datetime64(session, "D")
    out = {}
    for symbol, df in archive.frames.items():
        dates = archive.dates[symbol]
        start, stop = int(np.searchsorted(dates, first)), int(np.searchsorted(dates, last, side="right"))
        if stop > start:
            out[symbol] = df.iloc[start:stop]
    return out


# ------------------------------------------------------------- a session ----


def _universe(archive: Archive) -> universe.Universe:
    return universe.Universe(symbols=list(archive.intended), names={}, flags={}, source=ARCHIVE_SOURCE,
                             fetched_at=None, counts={"archive": len(archive.intended)},
                             label=f"recovered archive {archive.manifest_sha256[:12]}",
                             price_exempt=archive.price_exempt)


def _slim(b: dict) -> dict:
    p = b.get("plan") or {}
    return {"ticker": b["ticker"], "scan": b["scan"], "grade": b["grade_mechanical"], "score": b["score"],
            "vetoes": list(b["vetoes"]), "gain_pct": b["gain_pct"],
            "plan": {k: p.get(k) for k in ("eligible", "action", "entry_ref", "limit", "stop", "shares",
                                            "position_usd", "reason")} if p else None}


@dataclass
class Measurement:
    """What one session's market says before any decision: the frames the
    session rules admit, the regime, and the scanned, graded, ranked bursts.
    The same measurement serves both blocks, because the gate changes no
    measurement -- only what is done with it."""
    session: date
    frames: dict[str, pd.DataFrame]
    fresh: dict[str, pd.DataFrame]
    regime: dict | None
    bursts: list[dict]
    row: dict


def measure(frames: dict[str, pd.DataFrame], session: date, uni: universe.Universe) -> Measurement:
    """The run's own reading of one session over as-of frames: the session
    rules, the price policy, the Market Monitor and its regime, the two
    scans, the checklist grade and the rank."""
    stats = market_data.DownloadStats(session=session, feed="sip", requested=len(frames), with_bars=len(frames))
    ready = market_data.apply_session_rules(frames, session, stats)
    fresh, price_excluded = universe.session_eligible(ready, uni, exempt=(BENCHMARK,))
    counted = {t: df for t, df in fresh.items() if t != BENCHMARK}
    row = {"session": session.isoformat(), "with_bars": len(frames), "stale": len(stats.stale),
           "gapped": len(stats.gapped), "unreadable": len(stats.unreadable), "price_excluded": len(price_excluded),
           "counted": len(counted), "regime": None, "measured": 0, "scan_errors": 0, "bursts": 0, "grades": {}}
    if not counted:
        row["regime"] = {"verdict": None, "reason": "no name printed on the session"}
        return Measurement(session, frames, fresh, None, [], row)
    regime = breadth.snapshot(counted, session)["regime"]
    row["regime"] = {"verdict": regime["verdict"], **{k: regime["inputs"][k] for k in
                     ("ratio_10d", "ratio_5d", "up4_10d", "down4_10d", "up4", "down4", "up50_month")},
                     "universe": regime["thresholds"]["universe"], "reasons": list(regime["reasons"])}
    bursts, measured, errors = pipeline.scan_frames(fresh, uni, pipeline.RunReport())
    for b in bursts:
        b["grade"] = b["grade_mechanical"]
        b["claude"] = None
    pipeline.rank(bursts)
    row.update(measured=measured, scan_errors=errors, bursts=len(bursts),
               grades=dict(Counter(b["grade_mechanical"] for b in bursts)))
    return Measurement(session, frames, fresh, regime, bursts, row)


def decide(m: Measurement, account: plan.Account, rec: dict, *, gate: bool,
           max_picks: int | None = None) -> tuple[dict, dict]:
    """One block's decision over a measurement: the open model plans of the
    sessions before counted against the slots, the plans, the cash budget,
    and the picks appended to the record. Returns the record with tonight's
    picks and the night's row. With ``gate`` false the regime handed to the
    planner is ``UNGATED_REGIME``; the night's own regime is still recorded.
    ``max_picks`` is the record's retention: the replay passes a bound its
    picks cannot reach, so the file's ``MAX_PICKS`` never drops a plan it
    made (see ``retention_bound()``)."""
    row = {**m.row, "gate": gate, "eligible_plans": 0, "trades": [], "cut": {}, "slots_held": 0, "candidates": []}
    if m.regime is None:
        return rec, row
    verdict = m.regime["verdict"]
    held = pipeline.slots_held(record.open_plans(rec, m.frames, m.session.isoformat(), verdict))
    trades, cut, budget = pipeline._make_plans(m.bursts, account, m.regime if gate else UNGATED_REGIME, held,
                                               m.session, require_reader=False)
    picks = [pipeline.pick_of(b["plan"], "burst", b["grade"], b["score"]) for b in m.bursts if b["ticker"] in trades]
    rec = record.append(rec, m.session.isoformat(), picks, verdict, max_picks=max_picks)
    row.update(eligible_plans=sum(1 for b in m.bursts if (b.get("plan") or {}).get("eligible")
                                  and b["plan"].get("action") in plan.ORDER_ACTIONS),
               trades=list(trades), cut=dict(Counter(c["kind"] for c in budget.get("cut", []))),
               slots_held=held, candidates=[_slim(b) for b in m.bursts])
    return rec, row


def retention_bound(sessions_evaluated: int, account: plan.Account) -> int:
    """A record retention no replay can reach: a night issues at most one
    ticket per free slot, so ``sessions * max_open_positions`` is over every
    ticket the run could write. The record's own ``MAX_PICKS`` is a file
    policy for a nightly product, not a limit on an offline replay, and a
    replay that lost its oldest plans to it would score a different
    population than it issued -- ``run()`` refuses that outright."""
    return max(record.MAX_PICKS, sessions_evaluated * account.max_open_positions)


def fingerprint(row: dict) -> dict:
    """What the equivalence check compares between two lookbacks: the regime
    and its ratios, every candidate's mechanical grade, score and vetoes,
    and every plan's prices, shares and action."""
    regime = row["regime"] or {}
    return {"regime": [regime.get(k) for k in ("verdict", "ratio_10d", "up4_10d", "down4_10d")],
            "candidates": sorted([c["ticker"], c["grade"], c["score"], tuple(c["vetoes"])] for c in row["candidates"]),
            "plans": sorted([c["ticker"], *(c["plan"][k] for k in ("entry_ref", "limit", "stop", "shares", "action"))]
                            for c in row["candidates"] if c["plan"])}


# -------------------------------------------------------------- the run ----


def _partition(rows: list[dict], key) -> dict:
    groups = sorted({key(r) for r in rows}, key=str)
    return {str(g): record.summarize_scorecard([r for r in rows if key(r) == g]) for g in groups}


def run(archive: Archive, *, lookback: int = PRODUCTION_LOOKBACK, account: plan.Account | None = None,
        limit: int | None = None, progress=None) -> dict:
    """Every evaluable session in order, both blocks, then the outcomes over
    the whole archive. ``limit`` keeps the last that many evaluable sessions
    (a smoke run). ``progress`` is called with each session's row."""
    if lookback < 1 or lookback > PRODUCTION_LOOKBACK:
        raise BacktestError(f"lookback must be between 1 and the run's own {PRODUCTION_LOOKBACK}")
    account = account or plan.Account()
    calendar = archive.calendar
    if len(calendar) <= lookback:
        raise BacktestError(f"the archive holds {len(calendar)} sessions; {lookback + 1} are needed")
    evaluable = calendar[lookback:]
    if limit is not None:
        evaluable = evaluable[-limit:]
    uni = _universe(archive)
    rules = pipeline.build_rules(uni)
    recs = {gate: record.empty() for gate in GATES}
    nights = {gate: [] for gate in GATES}
    equivalence = {"required": lookback < PRODUCTION_LOOKBACK, "compared": 0, "differences": []}
    retention = retention_bound(len(evaluable), account)
    started = time.monotonic()
    for session in evaluable:
        m = measure(as_of(archive, session, lookback), session, uni)
        # the gate changes no measurement: one reading, two decisions, the
        # production block last so its candidates carry its plans
        for gate in reversed(GATES):
            recs[gate], row = decide(m, account, recs[gate], gate=gate == PRODUCTION, max_picks=retention)
            nights[gate].append(row)
        if equivalence["required"] and calendar.index(session) >= PRODUCTION_LOOKBACK:
            # both lookbacks over an empty record, so the slots cannot differ
            _, short = decide(m, account, record.empty(), gate=True)
            _, full = decide(measure(as_of(archive, session, PRODUCTION_LOOKBACK), session, uni), account,
                             record.empty(), gate=True)
            equivalence["compared"] += 1
            if fingerprint(short) != fingerprint(full):
                equivalence["differences"].append({"session": session.isoformat(),
                                                   "shortened": fingerprint(short), "production": fingerprint(full)})
        if progress:
            progress(nights[PRODUCTION][-1])
    equivalence["status"] = ("not required" if not equivalence["required"] else
                             "FAIL" if equivalence["differences"] else
                             "PASS" if equivalence["compared"] else "BLOCKED: no session carries the full lookback")
    last = evaluable[-1].isoformat()
    outcomes = {}
    for gate in GATES:
        # conservation: every ticket a night issued is a plan the walk scores
        issued = sum(len(r["trades"]) for r in nights[gate])
        if issued != len(recs[gate]["picks"]):
            raise BacktestError(f"{gate}: {issued} tickets issued but {len(recs[gate]['picks'])} plans recorded; "
                                "the replay refuses to score a population it did not issue")
        rows = record.scorecard_rows(recs[gate], archive.frames, last, window_sessions=len(calendar))
        if len(rows) != issued:
            raise BacktestError(f"{gate}: {issued} tickets issued but {len(rows)} plans walked")
        outcomes[gate] = {"tickets_issued": issued, "summary": record.summarize_scorecard(rows), "rows": rows,
                          "by_grade": _partition(rows, lambda r: r.get("grade")),
                          "by_regime": _partition(rows, lambda r: r.get("regime")),
                          "by_month": _partition(rows, lambda r: r["picked"][:7]),
                          "picks": recs[gate]["picks"]}
    verdicts = Counter((r["regime"] or {}).get("verdict") for r in nights[PRODUCTION])
    ratios = [r["regime"]["ratio_10d"] for r in nights[PRODUCTION] if r["regime"] and r["regime"].get("ratio_10d") is not None]
    return {
        "version": VERSION, "reader": READER, "limitations": list(LIMITATIONS),
        "archive": {"manifest_sha256": archive.manifest_sha256, "symbols": len(archive.frames),
                    "intended": len(archive.intended), "price_exempt": len(archive.price_exempt),
                    "statuses": dict(Counter(archive.statuses.values())), "queries": archive.queries,
                    "non_terminal_queries": archive.non_terminal,
                    "sessions": {"from": calendar[0].isoformat(), "through": calendar[-1].isoformat(),
                                 "count": len(calendar)}},
        "lookback": {"sessions": lookback, "production": PRODUCTION_LOOKBACK, "equivalence": equivalence},
        "account": account.to_dict(), "rules_version": report.rules_version(rules),
        "evaluated": {"from": evaluable[0].isoformat(), "through": last, "count": len(evaluable),
                      "seconds": round(time.monotonic() - started, 1)},
        "regimes": {"verdicts": dict(verdicts),
                    "ratio_10d": {"min": min(ratios) if ratios else None, "max": max(ratios) if ratios else None,
                                  "median": round(statistics.median(ratios), 2) if ratios else None,
                                  "defined": len(ratios)}},
        "nights": nights,
        "outcomes": outcomes,
    }


# -------------------------------------------------------------- summary ----


def _fmt(value) -> str:
    return "—" if value is None else (f"{value:.2f}" if isinstance(value, float) else str(value))


def summary_text(result: dict) -> str:
    """Counts, verdicts and R only. No price, no ticker: safe to paste."""
    a, e, lb = result["archive"], result["evaluated"], result["lookback"]
    lines = [f"SpicyStock mechanical backtest ({result['version']}) — no price in this summary",
             f"archive: {a['symbols']} symbols with bars of {a['intended']} intended; sessions {a['sessions']['from']}"
             f" .. {a['sessions']['through']} ({a['sessions']['count']}); statuses {a['statuses']}",
             f"evaluated: {e['count']} sessions {e['from']} .. {e['through']} in {e['seconds']} s; "
             f"lookback {lb['sessions']} of the run's {lb['production']}; rules {result['rules_version']}",
             f"lookback equivalence: {lb['equivalence']['status']} ({lb['equivalence']['compared']} sessions compared, "
             f"{len(lb['equivalence']['differences'])} differences)",
             f"account (configured, not a balance): {result['account']}",
             f"reader: {result['reader']}",
             f"regimes: {result['regimes']['verdicts']}; 10-session ratio min/median/max "
             f"{_fmt(result['regimes']['ratio_10d']['min'])}/{_fmt(result['regimes']['ratio_10d']['median'])}/"
             f"{_fmt(result['regimes']['ratio_10d']['max'])} over {result['regimes']['ratio_10d']['defined']} defined"]
    nights = result["nights"][PRODUCTION]
    lines.append(f"candidates: {sum(r['bursts'] for r in nights)} bursts over {len(nights)} sessions; mechanical grades "
                 f"{dict(sum((Counter(r['grades']) for r in nights), Counter()))}")
    for gate in GATES:
        s = result["outcomes"][gate]["summary"]
        tickets = sum(len(r["trades"]) for r in result["nights"][gate])
        by_regime = Counter(p.get("regime") for p in result["outcomes"][gate]["picks"])
        label = "PRODUCTION POLICY" if gate == PRODUCTION else "COUNTERFACTUAL — regime gate removed (not a policy)"
        lines += [f"", f"[{label}]",
                  f"tickets {tickets}, by the night's regime {dict(by_regime)}",
                  f"plans {s['plans']}: settled {s['settled']}, open {s['open']}, pending {s['pending']}, uncertain "
                  f"{s['uncertain']} {[(u['kind'], u['count']) for u in s['uncertain_reasons']]}, not filled "
                  f"{s['not_filled']}, unmeasured {s['unmeasured']}, unreadable {s['unreadable']}, unscored {s['unscored']}",
                  f"settled {s['settled']}: wins {s['wins']}, losses {s['losses']}, breakeven {s['breakeven']}; "
                  f"sum R {_fmt(s['sum_r'])}; avg R {_fmt(s['avg_r'])}; median R {_fmt(s['median_r'])}; "
                  f"win rate {_fmt(s['win_rate'])} (rates read only at {s['min_read']}+ settled: readable={s['readable']}); "
                  f"SPY avg % over {s['benchmark_pairs']} pairs {_fmt(s['spy_avg_pct'])}"]
        for name, part in (("grade", result["outcomes"][gate]["by_grade"]), ("regime", result["outcomes"][gate]["by_regime"])):
            for key, v in part.items():
                lines.append(f"  by {name} {key}: plans {v['plans']}, settled {v['settled']}, wins {v['wins']}, "
                             f"losses {v['losses']}, sum R {_fmt(v['sum_r'])}")
    lines += ["", "limitations:"] + [f"- {l}" for l in result["limitations"]]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ CLI ----


def _encode(value) -> str:
    def default(o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, (date, pd.Timestamp)):
            return str(o)
        if isinstance(o, tuple):
            return list(o)
        raise TypeError(type(o).__name__)
    return json.dumps(value, indent=1, sort_keys=True, default=default, allow_nan=False)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=Path, required=True, help="the frozen acquisition manifest")
    parser.add_argument("--storage", type=Path, required=True, help="the recovered package (ledger and pages)")
    parser.add_argument("--output", type=Path, required=True, help="a private directory for backtest.json and summary.txt")
    parser.add_argument("--lookback", type=int, default=PRODUCTION_LOOKBACK,
                        help=f"sessions of history before each evaluated session (default and maximum {PRODUCTION_LOOKBACK})")
    parser.add_argument("--sessions", type=int, default=None, help="evaluate only the last N evaluable sessions")
    args = parser.parse_args(argv)
    logging.getLogger("src").setLevel(logging.ERROR)
    try:
        output = _outside_git(args.output, "the output directory")
        manifest = json.loads(Path(args.manifest).read_bytes())
        archive = load_archive(manifest, args.storage)
        print(f"archive: {len(archive.frames)} symbols; {len(archive.calendar)} sessions", file=sys.stderr)

        def progress(row):
            r = row["regime"] or {}
            print(f"{row['session']} {r.get('verdict')} ratio {r.get('ratio_10d')} counted {row['counted']} "
                  f"bursts {row['bursts']} tickets {len(row['trades'])}", file=sys.stderr)

        result = run(archive, lookback=args.lookback, account=plan.Account.from_env(),
                     limit=args.sessions, progress=progress)
        output.mkdir(parents=True, exist_ok=True)
        (output / "backtest.json").write_text(_encode(result), encoding="utf-8")
        text = summary_text(result)
        (output / "summary.txt").write_text(text, encoding="utf-8")
        print(text, end="")
        return 0 if result["lookback"]["equivalence"]["status"] != "FAIL" else 2
    except (BacktestError, ValueError, OSError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
