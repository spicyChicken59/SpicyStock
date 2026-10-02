"""Every archived signal, ticketed and walked: the production mechanics over the
public records, with no reader, no gate and no slot.

The published scorecard has never held a plan, because every real night since
11 September 2026 was RED. The records those nights wrote still carry two
things: every burst the scan found, graded by the checklist, and -- from 16
September on -- the later bars of every public signal (``observations``). That
is enough to ask a narrower question than "did the strategy make money": IF
the ticket the rules would write for a mechanically admitted burst had been
placed, what would the fill rule and the five-session walk have done?

This tool answers it the way the run would, calling the run's own functions:

* the population is every burst row in the FIRST publication of each session
  (a re-publication of the same session is a revision, not new signals), in
  strata by the checklist's verdict -- ``admitted`` (``pipeline.TRADE_GRADES``
  with no veto, what GREEN would admit before the reader), then B, C and skip
  without a veto, and the vetoed rows of any grade -- so the admitted stratum
  can be read against the rest of the same nights;
* the ticket is ``plan.burst_plan()`` with the record's own account, at
  ``breadth.SIZE_MULTIPLIER["green"]``: the regime gate removed, the slot cap
  and the budget not applied, every ticket on its own;
* the bars are the records' own published observations and series, one bar
  per symbol and session, the newest publication winning and every change to
  a bar it replaces counted as a revision; a signal whose own close the bars
  do not reproduce is set aside as ``basis_mismatch`` and never walked;
* the walk is ``record.replay()`` over ``plan.FINAL_EXIT_DAY`` sessions, then
  ``record.r_multiple()``, bucketed exactly as ``record.scorecard_rows()``
  buckets, and summed by ``record.summarize_scorecard()``.

What it is NOT. It is a counterfactual: every one of these tickets was refused
by the RED gate, and the reader -- which has accepted one of 183 usable
judgements -- is not run, so the admitted stratum is a ceiling of what the
live policy could have ticketed, not the policy. It is a daily-bar model
(a fill only at the next open inside the ticket, uncertain days scored
nowhere) with no fee or slippage, so three per-side cost levels are printed
beside it and the uncertain tickets are bounded by a second, labelled walk
from the trigger. Signals on one night are dependent, so every statistic is
given by night and the interval is over nights. Signals published up to the
spec's freeze are EXPLORATORY: their next closes were public before the spec
was written. Only signals published after it are confirmatory. Nothing here
is an edge claim, nothing changes a rule, and nothing it prints is
actionable: every ticket it walks is in the past.

    python tools/signal_outcomes.py --spec <spec.json> --output <dir>

The spec names the publication commits and their record blobs, the strata,
the estimands and the freeze; a commit the checkout cannot produce, or a
record whose blob differs, is a refusal and never a smaller population.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import breadth, pipeline, plan, record, sessions  # noqa: E402

VERSION = "signal-outcomes-v1"
SPEC_SCHEMA = "signal-outcomes-spec-v1"
#: the checklist strata, in the order the summary prints them
ADMITTED, VETOED = "admitted", "vetoed"
STRATA = (ADMITTED, "B", "C", "skip", VETOED)
#: rows a ticket could not be walked for, kept in the denominator by name
NO_TICKET, PLAN_ERROR, BASIS_MISMATCH = "no_ticket", "plan_error", "basis_mismatch"
#: the walk's buckets plus this tool's own, so every row lands in exactly one
BUCKETS = record.SCORECARD_BUCKETS + (NO_TICKET, PLAN_ERROR, BASIS_MISMATCH)
#: the regime handed to the planner: the gate removed, nothing else
UNGATED = {"verdict": "green", "size_multiplier": breadth.SIZE_MULTIPLIER["green"]}
#: a bar's close must reproduce the signal row's own close to the cent
BASIS_TOLERANCE = 0.005
BAR_KEYS = ("o", "h", "l", "c")
SOURCE_HISTORY, SOURCE_LATEST, SOURCE_SERIES = "observation_history", "observation_latest", "burst_series"


class StudyError(RuntimeError):
    """A refusal, named; never a smaller population."""


# ----------------------------------------------------------------- spec ----


def load_spec(path: Path) -> dict:
    raw = Path(path).read_bytes()
    spec = json.loads(raw)
    if spec.get("schema") != SPEC_SCHEMA:
        raise StudyError("not a signal-outcomes spec")
    for key in ("publications", "frozen_through_session", "bootstrap", "cost_bps_per_side"):
        if key not in spec:
            raise StudyError(f"spec lacks {key}")
    date.fromisoformat(spec["frozen_through_session"])
    spec["_sha256"] = hashlib.sha256(raw).hexdigest()
    return spec


def _git(*args: str) -> bytes:
    done = subprocess.run(["git", *args], cwd=ROOT, capture_output=True)
    if done.returncode != 0:
        raise StudyError("git could not produce " + " ".join(args[-1:]))
    return done.stdout


def load_publications(spec: dict) -> list[dict]:
    """Every record the spec names, read from this checkout's objects and
    held to the blob the spec recorded. A missing object or a different blob
    is a refusal: the population is the spec's, never what the clone has."""
    out = []
    for entry in spec["publications"]:
        commit, blob, session = entry["commit"], entry["blob"], entry["session"]
        actual = _git("rev-parse", f"{commit}:docs/data.json").decode().strip()
        if actual != blob:
            raise StudyError(f"{commit[:8]}: docs/data.json is {actual[:8]}, the spec recorded {blob[:8]}")
        data = json.loads(_git("cat-file", "-p", f"{commit}:docs/data.json"))
        if data.get("run", {}).get("session") != session or data.get("fixture"):
            raise StudyError(f"{commit[:8]}: not the real {session} publication")
        out.append({"commit": commit, "blob": blob, "session": session, "data": data})
    return out


# ----------------------------------------------------------------- bars ----


def _bar(row: dict) -> dict | None:
    try:
        bar = {k: float(row[k]) for k in BAR_KEYS}
    except (KeyError, TypeError, ValueError):
        return None
    if not all(math.isfinite(v) and v > 0 for v in bar.values()):
        return None
    try:
        date.fromisoformat(row["date"])
    except (KeyError, TypeError, ValueError):
        return None
    return {"date": row["date"], **bar}


def gather_bars(publications: list[dict]) -> tuple[dict, list[dict]]:
    """One bar per symbol and session from every publication's observation
    histories, latest observations and candidate series, oldest publication
    first so the newest wins. A later publication's bar that differs from the
    one it replaces is a REVISION, counted with both values; a bar no later
    publication touches stands."""
    bars: dict[str, dict[str, dict]] = defaultdict(dict)
    revisions: list[dict] = []

    def put(symbol: str, raw: dict, source: str, publication: dict) -> None:
        bar = _bar(raw)
        if bar is None:
            return
        old = bars[symbol].get(bar["date"])
        if old is not None and any(abs(old[k] - bar[k]) > BASIS_TOLERANCE for k in BAR_KEYS):
            revisions.append({"symbol": symbol, "date": bar["date"], "earlier": {k: old[k] for k in BAR_KEYS},
                              "later": {k: bar[k] for k in BAR_KEYS}, "later_publication": publication["commit"][:8],
                              "later_source": source})
        bars[symbol][bar["date"]] = bar

    for publication in sorted(publications, key=lambda p: (p["session"], p["data"]["run"].get("published_at", ""))):
        data = publication["data"]
        for burst in data.get("bursts", []):
            for raw in burst.get("series") or []:
                put(burst["ticker"], raw, SOURCE_SERIES, publication)
        symbols = (data.get("observations") or {}).get("symbols") or {}
        for symbol, obs in symbols.items():
            if not isinstance(obs, dict):
                continue
            for raw in obs.get("history") or []:
                put(symbol, raw, SOURCE_HISTORY, publication)
            put(symbol, obs, SOURCE_LATEST, publication)
    return bars, revisions


# -------------------------------------------------------------- signals ----


def first_publications(publications: list[dict]) -> list[dict]:
    """The first publication of each session, by its ``published_at``; the
    rest are revisions of a night and contribute bars, never signals."""
    first: dict[str, dict] = {}
    for p in publications:
        stamp = p["data"]["run"].get("published_at", "")
        if p["session"] not in first or stamp < first[p["session"]]["data"]["run"].get("published_at", ""):
            first[p["session"]] = p
    return [first[s] for s in sorted(first)]


def stratum(row: dict) -> str:
    if row.get("vetoes"):
        return VETOED
    grade = row.get("grade_mechanical")
    return ADMITTED if grade in pipeline.TRADE_GRADES else grade if grade in ("B", "C", "skip") else VETOED


def ticket(row: dict, account: plan.Account) -> tuple[dict | None, str | None, str | None]:
    """The production ticket for one burst row, gate and slots removed: the
    plan, or the bucket and reason it has none. The inputs are the ones
    ``pipeline._make_plans`` hands ``plan.burst_plan``."""
    try:
        p = plan.burst_plan(ticker=row["ticker"], close=row["close"], low=row["low"], high=row["high"],
                            open_=row["open"], prev_close=row["prev_close"], gain_pct=row.get("gain_pct") or 0.0,
                            account=account, size_multiplier=UNGATED["size_multiplier"],
                            scan="dollar" if row.get("scan") == "dollar" else "4pct",
                            extension_pct=row.get("extension_pct"))
    except (ValueError, TypeError, KeyError) as exc:
        return None, PLAN_ERROR, f"{type(exc).__name__}: {exc}"
    if not p.get("eligible") or p.get("action") not in plan.ORDER_ACTIONS or not p.get("shares"):
        return None, NO_TICKET, p.get("reason") or p.get("action")
    return p, None, None


def _cost_r(walk: dict, stop: float, bps: float) -> float | None:
    """R after a per-side cost of ``bps`` on the fill and on every sale, in
    the walk's own units: the published stop is one R on the whole position."""
    entry, shares = walk.get("entry_ref"), walk.get("shares")
    if not isinstance(shares, int) or shares <= 0 or entry is None or entry <= stop:
        return None
    sales = [e for e in walk.get("events", []) if isinstance(e, dict) and e.get("shares", 0) > 0 and e.get("price")]
    if sum(e["shares"] for e in sales) != shares:
        return None
    rate = bps / 10_000
    cost = shares * entry * rate + math.fsum(e["shares"] * e["price"] * rate for e in sales)
    return round(cost / (shares * (entry - stop)), 4)


def walk_signal(pick: dict, bars_for: dict[str, dict], newest: str) -> tuple[dict, dict | None]:
    """One ticket over its later bars, bucketed as ``record.scorecard_rows``
    buckets a plan, and the walk itself when there was one. An uncertain
    ticket also carries the BOUND walk's R: the same ticket filled at its
    trigger on the uncertain day, labelled and kept apart from the result."""
    session = pick["date"]
    horizon = str(sessions.next_sessions(date.fromisoformat(session), record.OPEN_PLAN_SESSIONS)[-1])
    through = min(newest, horizon)
    later = sorted((b for d, b in bars_for.items() if session < d <= through), key=lambda b: b["date"])
    row = {"horizon": horizon, "through": later[-1]["date"] if later else None, "r": None, "spy_pct": None,
           "filled": False, "uncertainty": None, "status": None, "events": None, "bound_r": None, "cost_r": {}}
    if session == newest:
        row["bucket"] = "pending"
        return row, None
    if not later:
        row["bucket"] = "unmeasured"
        return row, None
    walk = record.replay(pick, later, "green")
    status = row["status"] = walk["status"]
    row["uncertainty"] = walk.get("uncertainty")
    row["events"] = [{k: e.get(k) for k in ("day", "date", "event", "price", "shares")} for e in walk.get("events", [])]
    if status in (record.UNCERTAIN, record.NOT_FILLED, record.UNREADABLE):
        row["bucket"] = status
        if status == record.UNCERTAIN:
            # the bound: had the uncertain day filled at the trigger
            bound = plan.follow({**pick, "entry_ref": float(pick["entry_ref"])}, later, "green")
            if bound["status"] in record.SETTLED:
                row["bound_r"] = record.r_multiple(bound, pick["stop"])
        return row, walk
    row["filled"] = True
    if status in record.SETTLED:
        row["r"] = record.r_multiple(walk, pick["stop"])
        row["bucket"] = "settled" if row["r"] is not None else "unscored"
    else:
        row["bucket"] = "open" if later[-1]["date"] == through else "unmeasured"
    return row, walk


def study(publications: list[dict], spec: dict) -> dict:
    """The whole study over loaded publications: bars, signals, tickets,
    walks, strata, nights, bounds, costs."""
    if not publications:
        raise StudyError("no publications")
    bars, revisions = gather_bars(publications)
    firsts = first_publications(publications)
    newest = max(p["session"] for p in publications)
    freeze = spec["frozen_through_session"]
    costs = [float(b) for b in spec["cost_bps_per_side"]]
    rows: list[dict] = []
    for p in firsts:
        data, session = p["data"], p["session"]
        account = plan.Account(**{k: data["account"][k] for k in ("equity", "risk_pct", "max_position_pct", "max_open_positions")})
        verdict = data["breadth"]["regime"]["verdict"]
        for b in data.get("bursts", []):
            row = {"session": session, "ticker": b["ticker"], "publication": p["commit"][:8], "stratum": stratum(b),
                   "grade_mechanical": b.get("grade_mechanical"), "score": b.get("score"), "vetoes": list(b.get("vetoes") or []),
                   "scan": b.get("scan"), "night_regime": verdict, "reader_accepted": b.get("reader_coverage") == "accepted",
                   "final_grade": b.get("grade"), "phase": "exploratory" if session <= freeze else "confirmatory",
                   "ticket": None, "bucket": None, "reason": None}
            p_, bucket, reason = ticket(b, account)
            if p_ is None:
                row.update(bucket=bucket, reason=reason)
                rows.append(row)
                continue
            # the basis: later bars are walked only when the published bars
            # reproduce the signal's own close, so a re-priced series (a
            # split, a correction) cannot be read against the row's prices
            symbol_bars = bars.get(b["ticker"], {})
            own = symbol_bars.get(session)
            if own is None and any(d > session for d in symbol_bars):
                row.update(bucket=BASIS_MISMATCH, reason="later bars exist but the signal's own session is not among them")
                rows.append(row)
                continue
            if own is not None and abs(own["c"] - float(b["close"])) > BASIS_TOLERANCE:
                row.update(bucket=BASIS_MISMATCH, reason=f"published bar close {own['c']} against the row's {b['close']}")
                rows.append(row)
                continue
            pick = {**pipeline.pick_of(p_, "burst", b.get("grade_mechanical"), b.get("score")), "date": session, "regime": verdict}
            pick.pop("evidence_ref", None)  # the row's receipt belongs to its night, not to this counterfactual ticket
            problem = record.pick_problem(pick)
            if problem:
                row.update(bucket=PLAN_ERROR, reason=problem)
                rows.append(row)
                continue
            row["ticket"] = {k: pick.get(k) for k in ("entry_ref", "entry_low", "entry_high", "limit", "stop", "shares", "day2_spent_above")}
            result, walk = walk_signal(pick, symbol_bars, newest)
            if result["r"] is not None:
                result["cost_r"] = {str(int(c)): round(result["r"] - (_cost_r(walk, pick["stop"], c) or 0.0), 2) for c in costs}
            row.update(result)
            rows.append(row)
    return {"version": VERSION, "spec_sha256": spec["_sha256"], "frozen_through_session": freeze, "newest_session": newest,
            "publications": [{"commit": p["commit"], "session": p["session"], "first": p in firsts} for p in publications],
            "bars": {"symbols": len(bars), "observations": sum(len(v) for v in bars.values()), "revisions": len(revisions),
                     "revision_rows": revisions},
            "rows": rows, "summary": summarize(rows, spec)}


# -------------------------------------------------------------- summary ----


def _night_means(rows: list[dict]) -> dict[str, float]:
    by_night: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        if r["bucket"] == "settled":
            by_night[r["session"]].append(r["r"])
    return {s: statistics.fmean(v) for s, v in by_night.items()}


def bootstrap_nights(night_means: dict[str, float], reps: int, seed: int) -> dict | None:
    """A night-block bootstrap of the mean of per-night mean R: nights are
    resampled with replacement, because tickets on one night are dependent."""
    values = np.array(list(night_means.values()), dtype=float)
    if len(values) < 2:
        return None
    rng = np.random.default_rng(seed)
    draws = rng.choice(values, size=(reps, len(values)), replace=True).mean(axis=1)
    return {"nights": len(values), "mean_of_night_means": round(float(values.mean()), 3),
            "ci95": [round(float(np.percentile(draws, 2.5)), 3), round(float(np.percentile(draws, 97.5)), 3)],
            "reps": reps, "seed": seed}


def _stratum_summary(rows: list[dict], spec: dict) -> dict:
    counts = {b: sum(r["bucket"] == b for r in rows) for b in BUCKETS}
    walked = [r for r in rows if r["bucket"] in record.SCORECARD_BUCKETS]
    scorecard = record.summarize_scorecard([{**r, "r": r.get("r"), "spy_pct": None, "filled": r.get("filled", False),
                                             "uncertainty": r.get("uncertainty")} for r in walked])
    settled = [r["r"] for r in rows if r["bucket"] == "settled"]
    bound = [r["bound_r"] for r in rows if r["bucket"] == record.UNCERTAIN and r.get("bound_r") is not None]
    night_means = _night_means(rows)
    costs = {}
    for c in spec["cost_bps_per_side"]:
        values = [r["cost_r"][str(int(c))] for r in rows if r["bucket"] == "settled" and r.get("cost_r", {}).get(str(int(c))) is not None]
        costs[str(int(c))] = {"n": len(values), "sum_r": round(math.fsum(values), 2) if values else None,
                              "mean_r": round(math.fsum(values) / len(values), 3) if values else None}
    return {"rows": len(rows), "buckets": counts, "scorecard": scorecard,
            "settled": {"n": len(settled), "sum_r": round(math.fsum(settled), 2) if settled else None,
                        "mean_r": round(math.fsum(settled) / len(settled), 3) if settled else None,
                        "median_r": round(statistics.median(settled), 2) if settled else None,
                        "wins": sum(r > 0 for r in settled), "losses": sum(r < 0 for r in settled),
                        "breakeven": sum(r == 0 for r in settled)},
            "by_night": {s: {"settled": sum(1 for r in rows if r["session"] == s and r["bucket"] == "settled"),
                             "rows": sum(1 for r in rows if r["session"] == s), "mean_r": round(m, 3)}
                         for s, m in sorted(night_means.items())},
            "night_bootstrap": bootstrap_nights(night_means, int(spec["bootstrap"]["reps"]), int(spec["bootstrap"]["seed"])),
            "uncertain_bound": {"uncertain": counts[record.UNCERTAIN], "bounded": len(bound),
                                "sum_r_if_filled_at_trigger": round(math.fsum(bound), 2) if bound else None,
                                "pooled_mean_r_with_bound": (round(math.fsum(settled + bound) / len(settled + bound), 3)
                                                             if settled + bound else None)},
            "costs_per_side_bps": costs}


def summarize(rows: list[dict], spec: dict) -> dict:
    out = {"all": _stratum_summary(rows, spec), "strata": {}, "phases": {}, "reader_accepted": None}
    for s in STRATA:
        out["strata"][s] = _stratum_summary([r for r in rows if r["stratum"] == s], spec)
    for phase in ("exploratory", "confirmatory"):
        subset = [r for r in rows if r["phase"] == phase and r["stratum"] == ADMITTED]
        out["phases"][phase] = _stratum_summary(subset, spec) if subset else {"rows": 0}
    accepted = [r for r in rows if r["reader_accepted"] and r["final_grade"] in pipeline.TRADE_GRADES]
    out["reader_accepted"] = _stratum_summary(accepted, spec) if accepted else {"rows": 0}
    return out


def summary_text(result: dict) -> str:
    s = result["summary"]
    lines = [f"SpicyStock signal-outcome study ({result['version']}) — counterfactual: no reader, no regime gate, no slot",
             f"spec {result['spec_sha256'][:12]}; frozen through {result['frozen_through_session']}; newest session {result['newest_session']}",
             f"publications {len(result['publications'])} ({sum(1 for p in result['publications'] if p['first'])} first-of-session); "
             f"bars {result['bars']['observations']} over {result['bars']['symbols']} symbols; revisions {result['bars']['revisions']}"]

    def block(name: str, v: dict) -> None:
        if not v or v.get("rows", 0) == 0:
            lines.append(f"[{name}] no rows")
            return
        b, st, sc = v["buckets"], v["settled"], v["scorecard"]
        lines.append(f"[{name}] rows {v['rows']}: settled {b['settled']}, open {b['open']}, pending {b['pending']}, "
                     f"uncertain {b['uncertain']}, not_filled {b['not_filled']}, unmeasured {b['unmeasured']}, "
                     f"unreadable {b['unreadable']}, unscored {b['unscored']}, no_ticket {b['no_ticket']}, "
                     f"plan_error {b['plan_error']}, basis_mismatch {b['basis_mismatch']}")
        lines.append(f"  settled {st['n']}: wins {st['wins']} losses {st['losses']} breakeven {st['breakeven']}; "
                     f"sum R {st['sum_r']}; mean R {st['mean_r']}; median R {st['median_r']}; "
                     f"scorecard rate readable={sc['readable']} (min {sc['min_read']})")
        nb = v["night_bootstrap"]
        if nb:
            lines.append(f"  nights {nb['nights']}: mean of night means {nb['mean_of_night_means']}, 95% night-bootstrap CI {nb['ci95']}")
        ub = v["uncertain_bound"]
        lines.append(f"  uncertain {ub['uncertain']} (bounded {ub['bounded']}): if every uncertain day had filled at the trigger, "
                     f"sum R {ub['sum_r_if_filled_at_trigger']}, pooled mean R {ub['pooled_mean_r_with_bound']}")
        lines.append("  costs per side: " + "; ".join(f"{k} bps mean R {c['mean_r']} (n {c['n']})" for k, c in v["costs_per_side_bps"].items()))

    block("ALL ROWS", s["all"])
    for name in STRATA:
        block(f"stratum {name}", s["strata"][name])
    for phase in ("exploratory", "confirmatory"):
        block(f"admitted · {phase}", s["phases"][phase])
    block("reader-accepted A/A+ (the live policy's own admissions)", s["reader_accepted"])
    lines += ["", "Every ticket above was refused by the RED gate and most by the reader; this is a ceiling of the",
              "mechanical policy on daily bars, not the strategy's performance and not an edge claim."]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="directory for signal-outcomes.json and summary.txt")
    args = parser.parse_args(argv)
    try:
        spec = load_spec(args.spec)
        result = study(load_publications(spec), spec)
    except StudyError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "signal-outcomes.json").write_text(json.dumps(result, indent=1, sort_keys=True, allow_nan=False), encoding="utf-8")
    text = summary_text(result)
    (args.output / "summary.txt").write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
