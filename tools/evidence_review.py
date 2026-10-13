"""An explicit evidence review before any strategy change is promoted (#109).

A reader over committed evidence and nothing else: the frozen signal-outcome
study (``signal_outcomes.py``'s rows under the extended spec), the findings
file ``build_historical_findings.py`` writes (which already holds the owner's
pasted backtest summaries under the tool's own grammar), the funnel and
feasibility history readings, and retained copies of the registered research
companions used for the 12 October review. It re-derives the study's strata from its rows and refuses a file
whose summary is not its rows'; splits the admitted stratum by phase, month,
halves of its nights and mechanical grade (``separate evaluation periods``);
walks the cumulative-R path of each stratum's settled counterfactual tickets
in the study's own order and reports its deepest drawdown; copies the
backtest, funnel, feasibility and research numbers off their files with each
file's digest; and evaluates a fixed ledger of the strategy changes this
repository has floated against criteria it states and archives. No provider,
model or network call; nothing here changes a threshold, a rule, a record or
the account. A verdict is a reading of evidence sufficiency, never a
recommendation to trade, and ``supported`` is a label no change earns today.

``--check`` compares the two files it writes and exits 1 on a difference, the
way ``make_fixture.py --check`` holds the fixtures.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import pipeline, record  # noqa: E402
from tools import build_historical_findings as bf  # noqa: E402
from tools import signal_outcomes as so  # noqa: E402

VERSION = "evidence-review-v1"
TRUTH = Path("docs/input-truthfulness")
OUT_DIR = ROOT / TRUTH / "2026-10-12-evidence-review-evidence"   # absolute: a test may run from elsewhere
OUTPUT_JSON = OUT_DIR / "review.json"
OUTPUT_MD = OUT_DIR / "review.md"
FINDINGS = Path("docs/historical-findings.json")
STUDY = bf.STUDY
STUDY_SPEC = bf.STUDY_SPEC
FUNNEL = TRUTH / "2026-10-11-candidate-funnel-evidence" / "history.json"
FEASIBILITY = {"archived": TRUTH / "2026-10-11-whole-share-feasibility-evidence" / "history-archived.json",
               "account_2000": TRUTH / "2026-10-11-whole-share-feasibility-evidence" / "history-account-2000.json"}
RESEARCH = {"cohort": TRUTH / "2026-10-12-evidence-review-evidence" / "inputs" / "stop-research.json",
            "journal": TRUTH / "2026-10-12-evidence-review-evidence" / "inputs" / "research-outcomes.json"}
# These are the exact bytes used by the dated review, not the rolling companions.
RESEARCH_ORIGIN = {
    "commit": "c759a1e671227717cae8d0bf1d50a4121d167396",
    "cohort": {"path": "docs/stop-research.json",
               "sha256": "98cc1b85b04aa3b570c777576d7d49f55edfe2bab5fe4e804362c5be7e2eeb22"},
    "journal": {"path": "docs/research-outcomes.json",
                "sha256": "15de998bec9ac4862b1e5b4d480b1a7cd0a69cabbcaab77d24b36e2a7c970db2"},
}

#: the record's own floor for reading a rate rather than a count (record.SCORECARD_MIN_PLANS)
MIN_SETTLED = record.SCORECARD_MIN_PLANS
STRATA = so.STRATA
ADMITTED = so.ADMITTED
#: the four signs a population can establish, in the words the ledger uses
SIGNS = ("positive", "negative", "unresolved", "unreadable")
VERDICTS = ("supported", "not_supported", "mixed", "insufficient")
CRITERIA = {
    "version": VERSION,
    "min_settled": MIN_SETTLED,
    "sign": {
        "unreadable": f"fewer than {MIN_SETTLED} settled tickets: a count, never a rate",
        "unresolved": "enough settled tickets but no night-bootstrap interval, or one that straddles zero",
        "negative": "the 95% night-bootstrap interval of the mean of night means lies below zero",
        "positive": "the 95% night-bootstrap interval of the mean of night means lies above zero",
    },
    "verdict": {
        "supported": "every direct source establishes a positive sign and every evaluation period of the change agrees",
        "not_supported": "a direct source establishes a negative sign and none establishes a positive one",
        "mixed": "direct sources establish both signs",
        "insufficient": "no direct source establishes a sign",
    },
    "scope": {
        "direct": "the source's population is the one the change would trade",
        "adjacent": "the source speaks to a neighbouring population (another regime, no reader, mixed regimes) and is shown, never counted",
    },
}


class ReviewError(ValueError):
    """Evidence that does not reconcile; the review refuses rather than guesses."""


# ------------------------------------------------------------ arithmetic ----


def settled_block(rows: list[dict]) -> dict:
    """Counts, one rounding of the sum and the mean, the median at two places:
    the study's own conventions, written again here."""
    rs = [r["r"] for r in rows if r.get("bucket") == "settled"]
    if not rs:
        return {"n": 0, "wins": 0, "losses": 0, "breakeven": 0, "sum_r": None, "mean_r": None, "median_r": None}
    return {"n": len(rs), "wins": sum(1 for r in rs if r > 0), "losses": sum(1 for r in rs if r < 0),
            "breakeven": sum(1 for r in rs if r == 0), "sum_r": round(math.fsum(rs), 2),
            "mean_r": round(math.fsum(rs) / len(rs), 3), "median_r": round(statistics.median(rs), 2)}


def night_bootstrap(rows: list[dict], spec: dict) -> dict | None:
    return so.bootstrap_nights(so._night_means(rows), int(spec["bootstrap"]["reps"]), int(spec["bootstrap"]["seed"]))


def sign_of(settled: dict, bootstrap: dict | None) -> str:
    """What a population establishes under CRITERIA['sign']."""
    if settled["n"] < MIN_SETTLED:
        return "unreadable"
    if not bootstrap:
        return "unresolved"
    low, high = bootstrap["ci95"]
    if high < 0:
        return "negative"
    if low > 0:
        return "positive"
    return "unresolved"


def population(label: str, rows: list[dict], spec: dict, **extra) -> dict:
    settled = settled_block(rows)
    bootstrap = night_bootstrap(rows, spec)
    sessions = sorted({r["session"] for r in rows})
    return {"label": label, "rows": len(rows), "nights": len(sessions),
            "settled_nights": len({r["session"] for r in rows if r.get("bucket") == "settled"}),
            "from": sessions[0] if sessions else None, "through": sessions[-1] if sessions else None,
            "settled": settled, "night_bootstrap": bootstrap, "sign": sign_of(settled, bootstrap), **extra}


def halves(nights: list[str]) -> tuple[list[str], list[str]]:
    """The first ceil(n/2) nights and the rest, in session order."""
    cut = (len(nights) + 1) // 2
    return nights[:cut], nights[cut:]


def periods(rows: list[dict], spec: dict) -> dict:
    """The admitted stratum read over separate evaluation periods: by phase,
    by calendar month, by halves of its exploratory nights, and by the
    mechanical grade inside the band."""
    admitted = [r for r in rows if r["stratum"] == ADMITTED]
    exploratory = [r for r in admitted if r["phase"] == "exploratory"]
    nights = sorted({r["session"] for r in exploratory})
    first, second = halves(nights)
    out = {
        "by_phase": {phase: population(f"admitted · {phase}", [r for r in admitted if r["phase"] == phase], spec)
                     for phase in ("exploratory", "confirmatory")},
        "by_month": {month: population(f"admitted · exploratory · {month}",
                                       [r for r in exploratory if r["session"][:7] == month], spec)
                     for month in sorted({r["session"][:7] for r in exploratory})},
        "by_half": {"first": population("admitted · exploratory · first half of its nights",
                                        [r for r in exploratory if r["session"] in first], spec),
                    "second": population("admitted · exploratory · second half of its nights",
                                         [r for r in exploratory if r["session"] in second], spec)},
        "by_mechanical_grade": {grade: population(f"admitted · exploratory · mechanical {grade}",
                                                  [r for r in exploratory if r["grade_mechanical"] == grade], spec)
                                for grade in ("A+", "A")},
        "all_strata_by_phase": {phase: population(f"every stratum · {phase}", [r for r in rows if r["phase"] == phase], spec)
                                for phase in ("exploratory", "confirmatory")},
    }
    return out


def drawdown(rows: list[dict]) -> dict:
    """The cumulative-R path of a stratum's settled tickets in the study's own
    order (session, then the file's row order) and its deepest peak-to-trough
    fall. A stream of counterfactual tickets with no slot cap held them, so
    this is the path of the R they would have paid, not an equity curve."""
    settled = [r for r in rows if r["bucket"] == "settled"]
    sessions = [r["session"] for r in settled]
    if sessions != sorted(sessions):
        raise ReviewError("the study's rows are not in session order")
    cum = peak = worst = 0.0
    start = settled[0]["session"] if settled else None
    peak_at = trough_at = None
    for r in settled:
        cum += r["r"]
        if cum > peak:
            peak, start = cum, r["session"]
        fall = peak - cum
        if fall > worst:
            worst, peak_at, trough_at = fall, start, r["session"]
    means = so._night_means(settled)
    path = cum_n = peak_n = worst_n = 0.0
    for session in sorted(means):
        path += means[session]
        peak_n = max(peak_n, path)
        worst_n = max(worst_n, peak_n - path)
    return {"settled": len(settled), "final_r": round(cum, 2), "max_drawdown_r": round(worst, 2),
            "drawdown_from": peak_at, "drawdown_to": trough_at,
            "night_means": {"nights": len(means), "final_r": round(path, 2), "max_drawdown_r": round(worst_n, 2)}}


# ----------------------------------------------------------- the sources ----


def load_json(path: Path) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def load_research(name: str) -> tuple[dict, dict]:
    """Read the dated companion once; missing or changed bytes cannot fall back
    to a newer night's state or silently change this historical review."""
    path = RESEARCH[name]
    origin = RESEARCH_ORIGIN[name]
    try:
        raw = (ROOT / path).read_bytes()
    except OSError as exc:
        raise ReviewError(f"retained research {name}: cannot read {path}") from exc
    digest = hashlib.sha256(raw).hexdigest()
    if digest != origin["sha256"]:
        raise ReviewError(f"retained research {name}: SHA-256 does not match the dated input")
    return json.loads(raw), {"path": str(path), "sha256": digest, "kind": "retained_companion",
                             "origin": {"commit": RESEARCH_ORIGIN["commit"], "path": origin["path"]}}


def crosscheck(study: dict) -> dict:
    """The study file's headline blocks re-derived from its own rows; a
    summary that is not its rows' is refused."""
    rows = study["rows"]
    out = {}
    for stratum in STRATA:
        mine = settled_block([r for r in rows if r["stratum"] == stratum])
        theirs = study["summary"]["strata"][stratum]["settled"]
        if mine != theirs:
            raise ReviewError(f"stratum {stratum}: the study's summary is not its rows'")
        out[stratum] = mine
    for phase in ("exploratory", "confirmatory"):
        mine = settled_block([r for r in rows if r["stratum"] == ADMITTED and r["phase"] == phase])
        theirs = study["summary"]["phases"][phase]
        if theirs.get("rows", 0) and mine != theirs["settled"]:
            raise ReviewError(f"admitted · {phase}: the study's summary is not its rows'")
        out[f"admitted · {phase}"] = mine
    return out


def costs(study: dict) -> dict:
    """Mean settled R per stratum at each cost assumption the spec names,
    copied from the study's summary (its arithmetic is held by its own tests)."""
    return {stratum: study["summary"]["strata"][stratum]["costs_per_side_bps"] for stratum in STRATA}


def _mean(sum_r, n) -> float | None:
    return round(sum_r / n, 3) if n else None


def backtest_sources(findings: dict) -> dict:
    """The owner's 158-session backtest as the findings file parsed it: the
    production policy and the counterfactual without the gate, each with its
    settled count and mean, and the counterfactual's split by grade and by
    regime. No per-row file was pasted, so no night bootstrap exists."""
    bt = findings["backtest"]["lookback_130"]
    out = {"evaluated": bt["evaluated"], "account": bt["account"], "reader": "NOT RUN",
           "means": "mean_r is sum_r over settled at three places; mean_r_pasted is the summary's own two-place figure", "gates": {}}
    for gate in ("production", "no_regime_gate"):
        g = bt["gates"][gate]
        s = g["settled"]
        out["gates"][gate] = {
            "label": g["label"], "tickets": g["tickets"], "settled": s["n"], "wins": s["wins"], "losses": s["losses"],
            "breakeven": s["breakeven"], "sum_r": s["sum_r"], "mean_r": _mean(s["sum_r"], s["n"]),
            "mean_r_pasted": s["avg_r"], "median_r": s["median_r"],
            "win_rate": s["win_rate"], "spy_avg_pct": s["spy_avg_pct"],
            "by_grade": {k: {**v, "mean_r": _mean(v["sum_r"], v["settled"])} for k, v in g["by_grade"].items()},
            "by_regime": {k: {**v, "mean_r": _mean(v["sum_r"], v["settled"])} for k, v in g["by_regime"].items()},
        }
    return out


def funnel_source(history: dict) -> dict:
    t = history["totals"]
    return {"publications": t["publications"], "sessions": t["sessions"], "regimes": t["regimes"],
            "discovered": t["discovered"], "listed": t["listed"], "potentially_usable": t["potentially_usable"],
            "reaction": {k: t["reaction"][k] for k in ("market", "grade", "review_refused", "review_downgraded", "ticket")},
            "anticipation": {k: t["anticipation"][k] for k in ("market", "event", "geometry", "sizing", "ticket")}}


def feasibility_source(history: dict) -> dict:
    t = history["totals"]
    bands = {}
    for band in ("tonight", "yellow", "green"):
        b = t["bands"][band]["in_band"]
        bands[band] = {"in_band": b["candidates"], "past_stop_rule": b["eligible"], "whole_share": b["whole_share"]}
    return {"accounts": t["accounts"], "candidates": sum(r["candidates"] for r in history["readings"]),
            "bands": bands, "anticipation": t["anticipation"]}


def research_source(cohort: dict, journal: dict) -> dict:
    return {"policy": cohort["policy"]["id"], "status": cohort["status"],
            "applicable": {"from": cohort["policy"]["applicable_start"], "through": cohort["policy"]["applicable_end"]},
            "measured_session": cohort["publication"]["measured_session"],
            "applicable_session": cohort["publication"]["applicable_session"],
            "stop_pct": {"baseline": cohort["policy"]["baseline_stop_pct"], "research": cohort["policy"]["research_stop_pct"]},
            "cohort_counts": cohort["counts"],
            "journal": {"policy": journal["policy"]["id"], "rows": journal["counts"]["rows"],
                        "eligible": journal["counts"]["eligible"], "by_status": journal["counts"]["by_status"],
                        "generated_at": journal["generated_at"]}}


# ------------------------------------------------------------- the ledger ----


def source_row(name: str, scope: str, label: str, settled: dict, bootstrap: dict | None, basis: str, **extra) -> dict:
    return {"source": name, "scope": scope, "population": label, "settled": settled["n"], "mean_r": settled["mean_r"],
            "sum_r": settled["sum_r"], "ci95": bootstrap["ci95"] if bootstrap else None,
            "sign": sign_of(settled, bootstrap), "basis": basis, **extra}


def pasted_row(name: str, scope: str, label: str, settled: int, sum_r: float, basis: str, **extra) -> dict:
    """A source the owner pasted as a summary: a count and a sum, no rows, so
    no interval can be drawn and its sign is unresolved once readable."""
    block = {"n": settled, "sum_r": sum_r, "mean_r": _mean(sum_r, settled)}
    return {"source": name, "scope": scope, "population": label, "settled": settled, "mean_r": block["mean_r"],
            "sum_r": sum_r, "ci95": None, "sign": sign_of(block, None), "basis": basis, **extra}


def verdict_of(sources: list[dict], periods_agree: bool) -> tuple[str, list[str]]:
    """CRITERIA['verdict'] applied to the direct sources of one change."""
    direct = [s for s in sources if s["scope"] == "direct"]
    signs = {s["sign"] for s in direct}
    because = [f"{s['source']} · {s['population']}: {s['sign']} ({s['settled']} settled)" for s in direct]
    if "positive" in signs and "negative" in signs:
        return "mixed", because
    if "negative" in signs:
        return "not_supported", because
    if "positive" in signs:
        if periods_agree:
            return "supported", because + ["every evaluation period agrees in sign"]
        return "insufficient", because + ["the evaluation periods do not agree in sign"]
    return "insufficient", because or ["no direct source"]


def ledger(study: dict, spec: dict, split: dict, backtest: dict, funnel: dict, feasibility: dict, research: dict) -> list[dict]:
    rows = study["rows"]
    expl = [r for r in rows if r["phase"] == "exploratory"]
    admitted = [r for r in expl if r["stratum"] == ADMITTED]
    a_grade = [r for r in admitted if r["grade_mechanical"] == "A"]
    a_plus = [r for r in admitted if r["grade_mechanical"] == "A+"]
    accepted = [r for r in rows if r["reader_accepted"] and r["final_grade"] in pipeline.TRADE_GRADES]
    gate = backtest["gates"]
    red_bt = gate["no_regime_gate"]["by_regime"]["red"]
    a_bt = gate["no_regime_gate"]["by_grade"]["A"]
    production = gate["production"]
    red_nights = "every night the study holds was RED, so its tickets are ones the market gate refused"
    changes = []

    def change(ident: str, title: str, would: str, sources: list[dict], period_signs: list[str], notes: list[str]) -> None:
        agree = bool(period_signs) and all(s == "positive" for s in period_signs)
        verdict, because = verdict_of(sources, agree)
        changes.append({"id": ident, "title": title, "would": would, "sources": sources,
                        "period_signs": period_signs, "verdict": verdict, "because": because, "notes": notes})

    change("yellow_admits_a", "Admit mechanical A under YELLOW beside A+",
           "widen pipeline.YELLOW_GRADES; a YELLOW night would plan reviewed A names at half size",
           [source_row("study", "adjacent", "admitted · exploratory · mechanical A on RED nights",
                       settled_block(a_grade), night_bootstrap(a_grade, spec),
                       f"{red_nights}; the reader was not consulted, so the mechanical grade is the ceiling"),
            pasted_row("backtest", "adjacent", "no regime gate · mechanical A · YELLOW and RED nights mixed",
                       a_bt["settled"], a_bt["sum_r"], "owner-pasted summary over 158 sessions; grade not split by regime; reader not run; no rows, so no interval")],
           [], [f"the funnel: {funnel['reaction']['grade']} reaction candidates stopped at the YELLOW band's A+ gate over "
                f"{funnel['regimes'].get('yellow', 0)} YELLOW publications, none of them reviewed; what the reader would have done with them is NOT RUN",
                "no retained publication has carried a YELLOW night with a reviewed A name, so no direct evidence exists"])

    change("trade_red_nights", "Trade on RED nights (remove or relax the market gate)",
           "breadth's RED verdict would stop refusing new longs",
           [source_row("study", "direct", "admitted · exploratory · every night RED", settled_block(admitted),
                       night_bootstrap(admitted, spec), red_nights + "; the reader was not consulted"),
            source_row("study", "direct", "every stratum · exploratory · every night RED",
                       settled_block(expl), night_bootstrap(expl, spec), red_nights),
            pasted_row("backtest", "direct", "no regime gate · RED nights", red_bt["settled"], red_bt["sum_r"],
                       "owner-pasted summary; reader not run; no rows, so no interval")],
           [split["by_half"]["first"]["sign"], split["by_half"]["second"]["sign"]],
           ["the backtest's RED-night counterfactual is a positive sum over 25 settled tickets with no interval; the study's "
            "RED nights are a negative interval over 267; the two populations differ in period (Feb-Sep against Sep-Oct) and universe"])

    change("anticipation_stop_5pct", "Widen the anticipation stop cap from 4% to 5%",
           "the registered research version anticipation_stop_width_4_to_5_v1, prospective from 12 October to 6 November",
           [pasted_row("research_journal", "direct",
                       f"registered cohort · {research['journal']['eligible']} eligible rows",
                       research["journal"]["by_status"]["resolved"], 0.0,
                       "frozen prospective journal; resolved rows carry the only R; nothing has resolved yet")],
           [], [f"journal status counts: {json.dumps(research['journal']['by_status'], sort_keys=True)}",
                "a registered experiment is evidence only once its rows resolve; today it is a design, not a result"])

    change("ticket_without_accepted_review", "Write an A+ ticket on the checklist alone when the reader refuses or fails",
           "drop the accepted-review requirement in pipeline._make_plans for A+ names",
           [pasted_row("backtest", "direct", "production policy · YELLOW A+ · reader not run",
                       production["settled"], production["sum_r"],
                       "owner-pasted summary over 158 sessions: the mechanical policy's own first readable rate, no interval"),
            source_row("study", "direct", "reader-accepted A/A+ (the live policy's own admissions)",
                       settled_block(accepted), night_bootstrap(accepted, spec), "the only rows the reader admitted"),
            source_row("study", "adjacent", "admitted · exploratory · mechanical A+ on RED nights",
                       settled_block(a_plus), night_bootstrap(a_plus, spec), red_nights)],
           [], [f"the backtest's production policy: {production['settled']} settled, win rate {production['win_rate']}, "
                f"mean {production['mean_r']}R, median {production['median_r']}R, SPY {production['spy_avg_pct']}% over the same windows",
                "the retained HAE reply (8 October) is the case this change would admit: a mechanical A+ whose reply cited paths "
                "outside the authority contract and was refused; tests/fixtures/grading/reader-hae/ holds it rejected"])

    change("account_or_risk_increase", "Raise the base risk or the account so more names size to a whole share",
           "a sizing change, not a strategy change: the same tickets at more shares",
           [], [],
           [f"the feasibility reading: under YELLOW at $2,000, {feasibility['account_2000']['bands']['yellow']['whole_share']} of "
            f"{feasibility['account_2000']['bands']['yellow']['in_band']} in-band names size to a whole share; at the archived "
            f"accounts {feasibility['archived']['bands']['yellow']['whole_share']} of {feasibility['archived']['bands']['yellow']['in_band']}",
            "no outcome evidence exists at either size: the price ceiling decides which names can be bought, not whether they win",
            "a larger risk fraction multiplies the R of the same tickets; it changes nothing about their sign"])
    return changes


# ----------------------------------------------------------------- build ----


def build() -> dict:
    study, study_sha = bf.load_study(STUDY)
    if study.get("version") != so.VERSION:
        raise ReviewError("the study is not a signal-outcomes-v1 file")
    spec = so.load_spec(ROOT / STUDY_SPEC)
    if spec["_sha256"] != study["spec_sha256"]:
        raise ReviewError("the study was not run under the committed extended spec")
    findings = load_json(FINDINGS)
    if findings.get("version") != bf.VERSION:
        raise ReviewError("the findings file is not the builder's")
    if findings["sources"]["study"]["uncompressed_sha256"] != study_sha:
        raise ReviewError("the findings file was built over a different study")
    funnel_history = load_json(FUNNEL)
    feasibility_history = {k: load_json(p) for k, p in FEASIBILITY.items()}
    cohort, cohort_source = load_research("cohort")
    journal, journal_source = load_research("journal")
    if cohort["policy"]["id"] != journal["policy"]["cohort_policy_id"]:
        raise ReviewError("the research journal does not follow the registered cohort")

    rows = study["rows"]
    regimes = {r["night_regime"] for r in rows}
    if regimes != {"red"}:
        raise ReviewError(f"the study holds nights the review does not describe: {sorted(regimes)}")
    split = periods(rows, spec)
    backtest = backtest_sources(findings)
    funnel = funnel_source(funnel_history)
    feasibility = {k: feasibility_source(h) for k, h in feasibility_history.items()}
    research = research_source(cohort, journal)
    return {
        "version": VERSION,
        "criteria": CRITERIA,
        "sources": {
            "study": bf.source(STUDY, kind="tool_output", uncompressed_sha256=study_sha, spec=bf.source(STUDY_SPEC)),
            "findings": bf.source(FINDINGS, kind="builder_output"),
            "funnel": bf.source(FUNNEL, kind="tool_output"),
            "feasibility": {k: bf.source(p, kind="tool_output") for k, p in FEASIBILITY.items()},
            "research": {"cohort": cohort_source, "journal": journal_source},
        },
        "evidence_through": {"study_newest_session": study["newest_session"],
                             "study_frozen_through": study["frozen_through_session"],
                             "backtest_through": backtest["evaluated"]["through"],
                             "funnel_sessions": funnel["sessions"],
                             "research_applicable_session": research["applicable_session"]},
        "study": {"rows": len(rows), "publications": len(study["publications"]), "night_regimes": sorted(regimes),
                  "crosscheck": crosscheck(study), "costs_per_side_bps": costs(study),
                  "drawdown": {stratum: drawdown([r for r in rows if r["stratum"] == stratum]) for stratum in STRATA}
                  | {"all": drawdown(rows)}},
        "periods": split,
        "backtest": backtest,
        "funnel": funnel,
        "feasibility": feasibility,
        "research": research,
        "ledger": ledger(study, spec, split, backtest, funnel, feasibility, research),
        "limits": [
            "Every study night was RED: its tickets are ones the market gate refused, walked on daily bars with the reader not consulted.",
            "The backtest's universe is the archive's later membership, its fills daily-bar, its reader not run, and it was pasted as a summary: no interval can be drawn from it.",
            "GREEN has never been published or observed in 158 backtest sessions; nothing here speaks to a GREEN night.",
            "The registered research cohort has no resolved row yet; its first can exist five sessions after 12 October.",
            "A verdict here reads evidence sufficiency under the criteria above; it is not a recommendation, and no change is promoted by this file.",
        ],
    }


# ---------------------------------------------------------------- render ----


def _r(value, places: int = 3) -> str:
    return "—" if value is None else f"{value:+.{places}f}" if isinstance(value, (int, float)) and not isinstance(value, bool) else str(value)


def _ci(ci) -> str:
    return "—" if not ci else f"[{ci[0]:+.3f}, {ci[1]:+.3f}]"


def _pop_row(p: dict) -> str:
    s = p["settled"]
    return (f"| {p['label']} | {p['from'] or '—'} → {p['through'] or '—'} | {p['nights']} | {p['settled_nights']} | {s['n']} | "
            f"{s['wins']} / {s['losses']} / {s['breakeven']} | {_r(s['mean_r'])} | {_ci(p['night_bootstrap'] and p['night_bootstrap']['ci95'])} | {p['sign']} |")


def render_md(review: dict) -> str:
    lines = [f"# Evidence review ({review['version']})", "",
             "Generated by `python tools/evidence_review.py` from the committed evidence named below; "
             "`--check` holds this file and `review.json` beside it. A reading, not a rule: no number here "
             "changes a threshold, a record or the account, and no change is promoted by it.", ""]
    lines += ["## Sources", "", "| source | path | SHA-256 |", "|---|---|---|"]
    flat = []
    for name, src in review["sources"].items():
        if "path" in src:
            flat.append((name, src))
        else:
            flat += [(f"{name} · {k}", v) for k, v in src.items()]
    for name, src in flat:
        lines.append(f"| {name} | `{src['path']}` | `{src['sha256'][:16]}…` |")
    lines += ["", "The research inputs retain the exact companion bytes used on 12 October; their digests are checked before reading.",
              "The rolling companions may advance without revising this dated review. Original sources:", ""]
    for name, src in review["sources"]["research"].items():
        origin = src["origin"]
        lines.append(f"- {name}: `{origin['path']}` at commit `{origin['commit']}`.")
    et = review["evidence_through"]
    lines += ["", f"Evidence through: study newest session {et['study_newest_session']} (frozen through "
              f"{et['study_frozen_through']}); backtest through {et['backtest_through']}; funnel over "
              f"{et['funnel_sessions']} sessions; research applicable session {et['research_applicable_session']}.", ""]
    lines += ["## Criteria", "", f"A rate is read at {review['criteria']['min_settled']} settled tickets or more "
              "(`record.SCORECARD_MIN_PLANS`); below it a population is a count.", ""]
    for kind in ("sign", "verdict", "scope"):
        lines += [f"**{kind}**", ""] + [f"- `{k}`: {v}" for k, v in review["criteria"][kind].items()] + [""]
    lines += ["## The study, re-derived from its rows", "",
              f"{review['study']['rows']} rows over {review['study']['publications']} publications; every night "
              f"{', '.join(review['study']['night_regimes']).upper()}.", "",
              "| population | settled | wins / losses / even | sum R | mean R | median R |", "|---|---:|---:|---:|---:|---:|"]
    for name, s in review["study"]["crosscheck"].items():
        lines.append(f"| {name} | {s['n']} | {s['wins']} / {s['losses']} / {s['breakeven']} | {_r(s['sum_r'], 2)} | {_r(s['mean_r'])} | {_r(s['median_r'], 2)} |")
    lines += ["", "### Costs per side (mean settled R)", "", "| stratum | 0 bps | 5 bps | 20 bps |", "|---|---:|---:|---:|"]
    for stratum, c in review["study"]["costs_per_side_bps"].items():
        lines.append(f"| {stratum} | {_r(c['0']['mean_r'])} | {_r(c['5']['mean_r'])} | {_r(c['20']['mean_r'])} |")
    lines += ["", "### Drawdown of the cumulative-R path", "",
              "Settled tickets in the study's own order (session, then row order); a stream no slot cap held, so a "
              "path of R paid and not an equity curve. The night-means path sums each night's mean R once.", "",
              "| stratum | settled | final R | deepest fall (R) | from | to | night-means final R | night-means deepest fall |",
              "|---|---:|---:|---:|---|---|---:|---:|"]
    for stratum, d in review["study"]["drawdown"].items():
        n = d["night_means"]
        lines.append(f"| {stratum} | {d['settled']} | {_r(d['final_r'], 2)} | {d['max_drawdown_r']:.2f} | {d['drawdown_from'] or '—'} | "
                     f"{d['drawdown_to'] or '—'} | {_r(n['final_r'], 2)} | {n['max_drawdown_r']:.2f} |")
    lines += ["", "## Separate evaluation periods (admitted stratum unless named)", "",
              "| population | sessions | nights | nights settled | settled | wins / losses / even | mean R | 95% night CI | sign |",
              "|---|---|---:|---:|---:|---:|---:|---|---|"]
    p = review["periods"]
    for group in ("by_phase", "by_month", "by_half", "by_mechanical_grade", "all_strata_by_phase"):
        for pop in p[group].values():
            lines.append(_pop_row(pop))
    bt = review["backtest"]
    lines += ["", "## The owner's backtest, as the findings file parsed it", "",
              f"{bt['evaluated']['count']} sessions, {bt['evaluated']['from']} → {bt['evaluated']['through']}; account "
              f"${bt['account']['equity']:,.0f} / {bt['account']['risk_pct']}%; reader {bt['reader']}.", "",
              "| gate | tickets | settled | wins / losses / even | sum R | mean R | median R | win rate | SPY % |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for gate, g in bt["gates"].items():
        lines.append(f"| {g['label']} | {g['tickets']} | {g['settled']} | {g['wins']} / {g['losses']} / {g['breakeven']} | "
                     f"{_r(g['sum_r'], 2)} | {_r(g['mean_r'])} | {_r(g['median_r'], 2)} | {g['win_rate']} | {g['spy_avg_pct']} |")
    cf = bt["gates"]["no_regime_gate"]
    lines += ["", "Counterfactual splits (settled · sum R · mean R): " + "; ".join(
        f"{k} {v['settled']} · {_r(v['sum_r'], 2)} · {_r(v['mean_r'])}" for k, v in {**{f"grade {g}": v for g, v in cf["by_grade"].items()},
                                                                                    **{f"regime {g}": v for g, v in cf["by_regime"].items()}}.items()) + ".", ""]
    f = review["funnel"]
    lines += ["## The funnel and the feasibility reading", "",
              f"Funnel: {f['publications']} publications over {f['sessions']} sessions ({json.dumps(f['regimes'], sort_keys=True)}); "
              f"{f['discovered']} reaction candidates discovered, {f['reaction']['market']} stopped at the market, "
              f"{f['reaction']['grade']} at the grade, {f['potentially_usable']} potentially usable, "
              f"{f['reaction']['review_refused']} refused by reader authority, {f['reaction']['review_downgraded']} lowered, "
              f"{f['reaction']['ticket']} tickets; {f['listed']} anticipation setups listed, {f['anticipation']['ticket']} tickets.", "",
              "| account | tonight: in band / stop rule / whole share | YELLOW | GREEN |", "|---|---:|---:|---:|"]
    for name, fe in review["feasibility"].items():
        b = fe["bands"]
        cell = lambda band: f"{b[band]['in_band']} / {b[band]['past_stop_rule']} / {b[band]['whole_share']}"  # noqa: E731
        accounts = ", ".join(f"{n} × {label}" for label, n in sorted(fe["accounts"].items()))
        lines.append(f"| {name} ({accounts}) | {cell('tonight')} | {cell('yellow')} | {cell('green')} |")
    r = review["research"]
    lines += ["", "## The registered research", "",
              f"`{r['policy']}` ({r['status']}): stop cap {r['stop_pct']['baseline']}% → {r['stop_pct']['research']}%, applicable "
              f"{r['applicable']['from']} → {r['applicable']['through']}; cohort of {r['cohort_counts']['considered']} with "
              f"{r['cohort_counts']['allocation_fit']} allocation-fit rows; journal `{r['journal']['policy']}`: "
              f"{r['journal']['rows']} rows, {r['journal']['eligible']} eligible, by status "
              f"{json.dumps(r['journal']['by_status'], sort_keys=True)}.", ""]
    lines += ["## The ledger", ""]
    for c in review["ledger"]:
        lines += [f"### {c['title']} — **{c['verdict']}**", "", f"Would: {c['would']}.", ""]
        if c["sources"]:
            lines += ["| source | scope | population | settled | mean R | 95% night CI | sign |", "|---|---|---|---:|---:|---|---|"]
            for s in c["sources"]:
                lines.append(f"| {s['source']} | {s['scope']} | {s['population']} | {s['settled']} | {_r(s['mean_r'])} | {_ci(s['ci95'])} | {s['sign']} |")
            lines.append("")
        if c["period_signs"]:
            lines += ["Period signs: " + ", ".join(c["period_signs"]) + ".", ""]
        lines += ["Because: " + "; ".join(c["because"]) + ".", ""]
        lines += [f"- {n}" for n in c["notes"]] + [""]
    lines += ["## What this does not establish", ""] + [f"- {s}" for s in review["limits"]] + [""]
    return "\n".join(lines)


def render_json(review: dict) -> str:
    return json.dumps(review, indent=1, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="compare rather than write; exit 1 on a difference")
    parser.add_argument("--output-dir", type=Path, default=OUT_DIR, help=f"where to write (default {OUT_DIR})")
    args = parser.parse_args(argv)
    try:
        review = build()
    except (ReviewError, so.StudyError, bf.FindingsError, OSError, KeyError, ValueError) as exc:
        print(f"evidence review: {exc}")
        return 2
    bad = bf.credential_like_fields(review)
    if bad:
        print("evidence review: a field name the secret scan reads as a credential: " + ", ".join(bad))
        return 2
    outputs = {args.output_dir / OUTPUT_JSON.name: render_json(review), args.output_dir / OUTPUT_MD.name: render_md(review)}
    if args.check:
        stale = [str(p) for p, text in outputs.items()
                 if not p.exists() or p.read_text(encoding="utf-8") != text]
        if stale:
            print("stale: " + ", ".join(stale) + " differ from what the evidence builds -- run python tools/evidence_review.py")
            return 1
        print(f"{args.output_dir} current: {len(review['ledger'])} changes reviewed, "
              f"{sum(1 for c in review['ledger'] if c['verdict'] == 'supported')} supported")
        return 0
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for p, text in outputs.items():
        p.write_text(text, encoding="utf-8")
    print(f"wrote {args.output_dir}: {len(review['ledger'])} changes reviewed, "
          f"{sum(1 for c in review['ledger'] if c['verdict'] == 'supported')} supported")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
