"""An explicit evidence review before any strategy change is promoted (#109).

A reader over committed evidence and nothing else, dated: this file writes the
7 November 2026 review (``evidence-review-v2``); the 12 October review it
supersedes stays under its own directory, frozen to its git blobs by the tests,
and is never re-derived. The inputs are the frozen signal-outcome study
(``signal_outcomes.py``'s rows under the 7 November extended spec), the
findings file ``build_historical_findings.py`` wrote over that study (which
holds the owner's pasted backtest summaries under the tool's own grammar), the
candidate-funnel and whole-share-feasibility history readings dated 7 November,
and four inputs retained under this review's ``inputs/`` as the commit named
in ``ORIGIN_COMMIT`` carried them: the findings file, the registered research
cohort and its journal, an extract of the live record's own model scorecard,
and the join of every study row to its publication's discovery admission
(``src/admission.py``, re-derived from each publication's rows off git). The
retained bytes are held to pinned digests before anything is read; a changed
byte refuses rather than reads the rolling file.

It re-derives the study's strata from its rows and refuses a file whose
summary is not its rows'; splits the admitted stratum by phase, by regime, by
calendar month, by halves of each phase's nights, by mechanical grade, by the
account each publication archived and by the admission route; walks the
cumulative-R path of each stratum's settled counterfactual tickets in the
study's own order and reports its deepest drawdown; copies the backtest,
funnel, feasibility, research and live-scorecard numbers off their files with
each file's digest; and evaluates a fixed ledger of the strategy changes this
repository has floated -- and one it promoted on 4 November -- against
criteria it states and archives. No provider, model or network call; nothing
here changes a threshold, a rule, a record or the account. A verdict is a
reading of evidence sufficiency, never a recommendation to trade, and
``supported`` is a label no change earns today.

``--check`` compares the two files it writes and exits 1 on a difference, the
way ``make_fixture.py --check`` holds the fixtures. ``--retain`` writes the
four retained inputs from git once, refusing to overwrite any that exist.
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
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import admission, pipeline, record  # noqa: E402
from tools import build_historical_findings as bf  # noqa: E402
from tools import signal_outcomes as so  # noqa: E402

VERSION = "evidence-review-v2"
REVIEW_DATE = "2026-11-07"
TRUTH = Path("docs/input-truthfulness")
EVIDENCE = TRUTH / f"{REVIEW_DATE}-evidence-review-evidence"
OUT_DIR = ROOT / EVIDENCE   # absolute: a test may run from elsewhere
OUTPUT_JSON = OUT_DIR / "review.json"
OUTPUT_MD = OUT_DIR / "review.md"
INPUTS = EVIDENCE / "inputs"
# the study this dated review read, named here rather than borrowed from the
# findings builder, whose study moves forward as publications are appended
STUDY = TRUTH / "2026-11-07-signal-outcomes-confirmatory-evidence" / "signal-outcomes.json.gz"
STUDY_SPEC = TRUTH / "2026-11-07-signal-outcomes-spec-extended.json"
FUNNEL = TRUTH / "2026-11-07-candidate-funnel-evidence" / "history.json"
FEASIBILITY = {"archived": TRUTH / "2026-11-07-whole-share-feasibility-evidence" / "history-archived.json",
               "account_30000": TRUTH / "2026-11-07-whole-share-feasibility-evidence" / "history-account-30000.json"}
FINDINGS = INPUTS / "historical-findings.json"
RESEARCH = {"cohort": INPUTS / "stop-research.json", "journal": INPUTS / "research-outcomes.json"}
SCORECARD = INPUTS / "scorecard.json"
ADMISSION = INPUTS / "admission-join.json.gz"
#: the commit on main every retained input was read from (the merge of PR #216)
ORIGIN_COMMIT = "af21693ce5cd5e0df91fb23ac58972ee542af5ed"
# The exact bytes used by this dated review, not the rolling files: each is
# held to its digest before it is read, and the origin names where it came from.
RESEARCH_ORIGIN = {
    "commit": ORIGIN_COMMIT,
    "cohort": {"path": "docs/stop-research.json",
               "sha256": "d019374e1d539e4c7d44bcf1ab04d468cc78787956043ab8037b6bde704f996b"},
    "journal": {"path": "docs/research-outcomes.json",
                "sha256": "58e45f6df3207624faafc584ef7e661f84d22b3e6f939a32df688ff3c63f6622"},
}
FINDINGS_ORIGIN = {"commit": ORIGIN_COMMIT, "path": "docs/historical-findings.json",
                   "sha256": "992e9195b7d084bbbe9f1265aa900e58e561c349dc969ff2012f68b0cc9008de"}
#: the live record's scorecard, extracted (not copied whole: the record is 15 MB) from docs/data.json at the origin
SCORECARD_ORIGIN = {"commit": ORIGIN_COMMIT, "path": "docs/data.json",
                    "record_sha256": "ea082b34e2b5d8ea7b7229f7b74b2cbff8207b89d5a1f7eef26b598b9b555390",
                    "sha256": "0beaca657cc968dd4101e8d9e3e9736ca2c6ccd10e6b41574f8b50516169d34d"}
#: every study row joined to its publication's admission block, re-derived from the publication's own rows off git
ADMISSION_ORIGIN = {"spec": str(STUDY_SPEC), "policy": admission.POLICY, "version": admission.VERSION,
                    "sha256": "9d3b24b531e7b4e112a3bb3131426f5ff1b766e231d14e98f050ab34c5a1c15b"}
EXTRACT_VERSION = "scorecard-extract-v1"
JOIN_VERSION = "admission-join-v1"

#: the record's own floor for reading a rate rather than a count (record.SCORECARD_MIN_PLANS)
MIN_SETTLED = record.SCORECARD_MIN_PLANS
STRATA = so.STRATA
ADMITTED = so.ADMITTED
REGIMES = ("red", "yellow", "green")
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
    "interval": "An interval is the study's own night-block bootstrap at the spec's reps and seed; it exists only over two or "
                "more nights with settled tickets, and the night count is printed beside every interval",
    "verdict": {
        "supported": "every direct source establishes a positive sign and every evaluation period of the change agrees",
        "not_supported": "a direct source establishes a negative sign and none establishes a positive one",
        "mixed": "direct sources establish both signs",
        "insufficient": "no direct source establishes a sign",
    },
    "scope": {
        "direct": "the source's population is the one the change would trade",
        "adjacent": "the source speaks to a neighbouring population (another regime, no reader, mixed regimes) and is shown, never counted",
        "removed": "the population the change stops trading, shown beside the one it keeps and never counted",
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


def is_admitted_route(row: dict) -> bool:
    """The discovery admission the review joined to the row (``admission.admitted``
    re-derived from the publication's own row): a row without a join is a refusal
    one level up, never read as admitted here."""
    return bool(row["admission"]["admitted"])


def periods(rows: list[dict], spec: dict, accounts: dict[str, float]) -> dict:
    """The admitted stratum read over separate evaluation periods: by phase, by
    regime, by calendar month, by halves of each phase's nights, by the
    mechanical grade inside the band, by the account each publication archived
    and by the discovery admission route; the reader-accepted population and
    every stratum by phase beside them. Each group is a dict of populations."""
    admitted = [r for r in rows if r["stratum"] == ADMITTED]
    by_phase = {phase: [r for r in admitted if r["phase"] == phase] for phase in ("exploratory", "confirmatory")}
    out: dict[str, dict] = {}
    out["by_phase"] = {phase: population(f"admitted · {phase}", rs, spec) for phase, rs in by_phase.items()}
    out["by_regime"] = {}
    for phase, rs in by_phase.items():
        for regime in REGIMES:
            sel = [r for r in rs if r["night_regime"] == regime]
            if sel:
                out["by_regime"][f"{phase} {regime}"] = population(f"admitted · {phase} · {regime.upper()} nights", sel, spec)
    for regime in REGIMES:
        sel = [r for r in admitted if r["night_regime"] == regime]
        if sel:
            out["by_regime"][f"both phases {regime}"] = population(f"admitted · both phases · {regime.upper()} nights", sel, spec)
    out["by_month"] = {month: population(f"admitted · {month}", [r for r in admitted if r["session"][:7] == month], spec)
                       for month in sorted({r["session"][:7] for r in admitted})}
    out["by_half"] = {}
    for phase, rs in by_phase.items():
        first, second = halves(sorted({r["session"] for r in rs}))
        out["by_half"][f"{phase} first"] = population(f"admitted · {phase} · first half of its nights",
                                                      [r for r in rs if r["session"] in first], spec)
        out["by_half"][f"{phase} second"] = population(f"admitted · {phase} · second half of its nights",
                                                       [r for r in rs if r["session"] in second], spec)
    out["by_mechanical_grade"] = {f"{phase} {grade}": population(f"admitted · {phase} · mechanical {grade}",
                                                                 [r for r in rs if r["grade_mechanical"] == grade], spec)
                                  for phase, rs in by_phase.items() for grade in ("A+", "A")}
    out["by_account"] = {}
    for equity in sorted({accounts[r["publication"]] for r in admitted}):
        sel = [r for r in admitted if accounts[r["publication"]] == equity]
        out["by_account"][f"${equity:,.0f}"] = population(f"admitted · publications sized at ${equity:,.0f}", sel, spec,
                                                           account_equity=equity)
    out["by_route"] = {}
    for scope, sel in (("all nights", admitted), *((f"{regime} nights", [r for r in admitted if r["night_regime"] == regime])
                                                   for regime in REGIMES)):
        if not sel:
            continue
        for word, keep in (("admitted", True), ("stopped", False)):
            out["by_route"][f"{scope} route-{word}"] = population(
                f"admitted stratum · {scope} · discovery route {word}", [r for r in sel if is_admitted_route(r) == keep], spec)
    out["reader_accepted"] = {"all": population("reader-accepted A/A+ (the live policy's own admissions)",
                                                [r for r in rows if r["reader_accepted"] and r["final_grade"] in pipeline.TRADE_GRADES], spec)}
    out["all_strata_by_phase"] = {phase: population(f"every stratum · {phase}", [r for r in rows if r["phase"] == phase], spec)
                                  for phase in ("exploratory", "confirmatory")}
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


# ----------------------------------------------------------- the inputs ----


def _git(*args: str) -> bytes:
    done = subprocess.run(["git", *args], cwd=ROOT, capture_output=True)
    if done.returncode != 0:
        raise ReviewError("git could not produce " + " ".join(args))
    return done.stdout


def _read_pinned(path: Path, digest: str, what: str) -> bytes:
    """One read of a retained input, held to its pinned digest: missing or
    changed bytes refuse rather than fall back to a rolling file."""
    try:
        raw = (ROOT / path).read_bytes()
    except OSError as exc:
        raise ReviewError(f"retained {what}: cannot read {path}") from exc
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ReviewError(f"retained {what}: SHA-256 does not match the dated input")
    return raw


def load_json(path: Path) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def load_research(name: str) -> tuple[dict, dict]:
    """Read the dated companion once; missing or changed bytes cannot fall back
    to a newer night's state or silently change this historical review."""
    path = RESEARCH[name]
    origin = RESEARCH_ORIGIN[name]
    raw = _read_pinned(path, origin["sha256"], f"research {name}")
    return json.loads(raw), {"path": str(path), "sha256": origin["sha256"], "kind": "retained_companion",
                             "origin": {"commit": RESEARCH_ORIGIN["commit"], "path": origin["path"]}}


def load_findings() -> tuple[dict, dict]:
    """Read the retained findings file once, as ``load_research`` reads a
    companion: missing or changed bytes refuse rather than fall back to the
    rolling file, which a later study rebuilds."""
    raw = _read_pinned(FINDINGS, FINDINGS_ORIGIN["sha256"], "findings")
    return json.loads(raw), {"path": str(FINDINGS), "sha256": FINDINGS_ORIGIN["sha256"], "kind": "retained_builder_output",
                             "origin": {"commit": FINDINGS_ORIGIN["commit"], "path": FINDINGS_ORIGIN["path"]}}


def load_scorecard() -> tuple[dict, dict]:
    """The live record's own scorecard as the origin commit carried it, an
    extract this tool wrote (``scorecard_extract``) and pinned."""
    raw = _read_pinned(SCORECARD, SCORECARD_ORIGIN["sha256"], "scorecard extract")
    data = json.loads(raw)
    if data.get("version") != EXTRACT_VERSION or data.get("origin") != {k: SCORECARD_ORIGIN[k] for k in ("commit", "path", "record_sha256")}:
        raise ReviewError("retained scorecard extract: not this review's extract of the origin record")
    return data, {"path": str(SCORECARD), "sha256": SCORECARD_ORIGIN["sha256"], "kind": "retained_record_extract",
                  "origin": {"commit": SCORECARD_ORIGIN["commit"], "path": SCORECARD_ORIGIN["path"],
                             "record_sha256": SCORECARD_ORIGIN["record_sha256"]}}


def load_admission(spec: dict) -> tuple[dict, dict]:
    """The retained join, pinned, and held to the spec this review reads."""
    raw = _read_pinned(ADMISSION, ADMISSION_ORIGIN["sha256"], "admission join")
    data = json.loads(gzip.decompress(raw))
    if data.get("version") != JOIN_VERSION or data.get("spec_sha256") != spec["_sha256"]:
        raise ReviewError("retained admission join: not this review's join over the committed extended spec")
    if data.get("policy") != admission.POLICY or data.get("admission_version") != admission.VERSION:
        raise ReviewError("retained admission join: not the admission rule this checkout carries")
    return data, {"path": str(ADMISSION), "sha256": ADMISSION_ORIGIN["sha256"], "kind": "retained_join",
                  "origin": {"spec": ADMISSION_ORIGIN["spec"], "policy": admission.POLICY, "version": admission.VERSION}}


def scorecard_extract(raw_record: bytes, commit: str) -> dict:
    """What this review keeps of a 15 MB record: its session, rules identity,
    account, the whole scorecard block and the open model plans."""
    data = json.loads(raw_record)
    run, app = data.get("run") or {}, data.get("app") or {}
    if data.get("schema_version") != 2 or data.get("fixture") or not isinstance(data.get("scorecard"), dict):
        raise ReviewError(f"{commit[:8]}: docs/data.json is not a real schema-2 publication with a scorecard")
    return {"version": EXTRACT_VERSION,
            "origin": {"commit": commit, "path": "docs/data.json", "record_sha256": hashlib.sha256(raw_record).hexdigest()},
            "session": run.get("session"), "published_at": run.get("published_at"), "rules_version": app.get("rules_version"),
            "account": data.get("account"), "scorecard": data["scorecard"], "open_plans": data.get("open_plans") or []}


def admission_join(spec: dict) -> dict:
    """Every burst row of every publication the spec names, read off git and
    held to the spec's blob, joined to its re-derived admission block by the
    publication's eight-character commit and the ticker (the study's own row
    key). A ticker listed twice in one publication is a refusal."""
    pubs = so.load_publications(spec)
    rows: dict[str, dict] = {}
    publications = []
    for p in pubs:
        data = p["data"]
        account = (data.get("account") or {}).get("equity")
        publications.append({"commit": p["commit"], "blob": p["blob"], "session": p["session"],
                             "account_equity": account, "bursts": len(data.get("bursts") or [])})
        for row in data.get("bursts") or []:
            key = f"{p['commit'][:8]}:{row['ticker']}"
            if key in rows:
                raise ReviewError(f"{key}: listed twice in one publication")
            block = admission.block(row)
            rows[key] = {"route": block["route"], "basis": block["basis"], "admitted": block["admitted"],
                         "archived": isinstance(row.get("admission"), dict), "scan": row.get("scan")}
    return {"version": JOIN_VERSION, "spec_sha256": spec["_sha256"], "policy": admission.POLICY,
            "admission_version": admission.VERSION, "publications": publications, "rows": rows}


def _canonical_bytes(obj: dict) -> bytes:
    return (json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _gzip_bytes(payload: bytes) -> bytes:
    import io
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
        gz.write(payload)
    return buf.getvalue()


def retain_inputs(out_dir: Path, commit: str = ORIGIN_COMMIT) -> dict[str, str]:
    """Write the retained inputs once from git: the findings file, the
    research cohort and journal as the commit carried them (byte for byte),
    the scorecard extract of that commit's record, and the admission join over
    the study's spec. Refuses to overwrite a file that exists. Returns each
    file's SHA-256, for pinning."""
    out_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, bytes] = {}
    for name in ("historical-findings.json", "stop-research.json", "research-outcomes.json"):
        files[name] = _git("cat-file", "-p", f"{commit}:docs/{name}")
    files["scorecard.json"] = _canonical_bytes(scorecard_extract(_git("cat-file", "-p", f"{commit}:docs/data.json"), commit))
    spec = so.load_spec(ROOT / STUDY_SPEC)
    files["admission-join.json.gz"] = _gzip_bytes(_canonical_bytes(admission_join(spec)))
    existing = [name for name in files if (out_dir / name).exists()]
    if existing:
        raise ReviewError("inputs already retained, not overwritten: " + ", ".join(existing))
    digests = {}
    for name, raw in files.items():
        (out_dir / name).write_bytes(raw)
        digests[name] = hashlib.sha256(raw).hexdigest()
    return digests


# ----------------------------------------------------------- the sources ----


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
    return {stratum: {str(bps): {"mean_r": study["summary"]["strata"][stratum]["costs_per_side_bps"][str(bps)]["mean_r"]}
                      for bps in (0, 5, 20)}
            for stratum in STRATA}


def _mean(sum_r, n) -> float | None:
    return None if not n else round(sum_r / n, 3)


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


FUNNEL_REGIME_STAGES = ("grade", "route", "review_refused", "review_downgraded", "preview_sizing", "ticket")


def funnel_source(history: dict) -> dict:
    t = history["totals"]
    by_regime: dict[str, dict] = {}
    for r in history["readings"]:
        stages = by_regime.setdefault(r["regime"] or "unknown", {s: 0 for s in FUNNEL_REGIME_STAGES})
        for s in FUNNEL_REGIME_STAGES:
            stages[s] += r["reaction"]["stages"].get(s, 0)
    return {"publications": t["publications"], "sessions": t["sessions"], "regimes": t["regimes"],
            "discovered": t["discovered"], "listed": t["listed"], "potentially_usable": t["potentially_usable"],
            "reaction": {k: t["reaction"][k] for k in ("market", "grade", "route", "preview_sizing", "review_refused",
                                                        "review_downgraded", "ticket")},
            "anticipation": {k: t["anticipation"][k] for k in ("market", "event", "geometry", "sizing", "ticket")},
            "reaction_by_regime": by_regime, "ref": history["ref"]}


def feasibility_source(history: dict) -> dict:
    t = history["totals"]
    bands = {}
    for band in ("tonight", "yellow", "green"):
        b = t["bands"][band]["in_band"]
        bands[band] = {"in_band": b["candidates"], "past_stop_rule": b["eligible"], "whole_share": b["whole_share"]}
    return {"accounts": t["accounts"], "candidates": sum(r["candidates"] for r in history["readings"]),
            "overrides": history["overrides"], "bands": bands, "anticipation": t["anticipation"], "ref": history["ref"]}


def research_source(cohort: dict, journal: dict) -> dict:
    return {"policy": cohort["policy"]["id"], "status": cohort["status"],
            "applicable": {"from": cohort["policy"]["applicable_start"], "through": cohort["policy"]["applicable_end"]},
            "measured_session": cohort["publication"]["measured_session"],
            "applicable_session": cohort["publication"]["applicable_session"],
            "stop_pct": {"baseline": cohort["policy"]["baseline_stop_pct"], "research": cohort["policy"]["research_stop_pct"]},
            "cohort_counts": cohort["counts"],
            "journal": {"policy": journal["policy"]["id"], "rows": journal["counts"]["rows"], "cohorts": journal["counts"]["cohorts"],
                        "eligible": journal["counts"]["eligible"], "by_status": journal["counts"]["by_status"],
                        "generated_at": journal["generated_at"]}}


def scorecard_source(extract: dict) -> dict:
    """The live policy's own model scorecard: the plans the published record
    actually issued, replayed by the record's own daily-bar rule. Counts, never
    an edge; readable only at the record's own floor."""
    sc = extract["scorecard"]
    plans = [{"ticker": p.get("ticker"), "kind": p.get("kind"), "status": p.get("status"), "shares": p.get("shares"),
              "result_pct": p.get("result_pct")} for p in extract["open_plans"]]
    return {"session": extract["session"], "rules_version": extract["rules_version"], "account": extract["account"],
            "plans": sc["plans"], "settled": sc["settled"], "wins": sc["wins"], "losses": sc["losses"], "breakeven": sc["breakeven"],
            "sum_r": sc["sum_r"], "mean_r": _mean(sc["sum_r"], sc["settled"]), "readable": sc["readable"], "min_read": sc["min_read"],
            "not_filled": sc["not_filled"], "uncertain": sc["uncertain"], "open": sc["open"], "pending": sc["pending"],
            "population": sc["population"], "open_plans": plans}


# ------------------------------------------------------------- the ledger ----


def source_row(name: str, scope: str, label: str, settled: dict, bootstrap: dict | None, basis: str, **extra) -> dict:
    return {"source": name, "scope": scope, "population": label, "settled": settled["n"], "mean_r": settled["mean_r"],
            "sum_r": settled["sum_r"], "nights": bootstrap["nights"] if bootstrap else None,
            "ci95": bootstrap["ci95"] if bootstrap else None, "sign": sign_of(settled, bootstrap), "basis": basis, **extra}


def study_row(name: str, scope: str, label: str, rows: list[dict], spec: dict, basis: str, **extra) -> dict:
    return source_row(name, scope, label, settled_block(rows), night_bootstrap(rows, spec), basis, **extra)


def pasted_row(name: str, scope: str, label: str, settled: int, sum_r: float, basis: str, **extra) -> dict:
    """A source the owner pasted as a summary, or a scorecard's counts: a
    count and a sum, no rows, so no interval can be drawn and its sign is
    unresolved once readable."""
    block = {"n": settled, "sum_r": sum_r, "mean_r": _mean(sum_r, settled)}
    return {"source": name, "scope": scope, "population": label, "settled": settled, "mean_r": block["mean_r"],
            "sum_r": sum_r, "nights": None, "ci95": None, "sign": sign_of(block, None), "basis": basis, **extra}


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


def _settled(rows: list[dict], session: str) -> int:
    return sum(1 for r in rows if r["session"] == session and r["bucket"] == "settled")


def ledger(study: dict, spec: dict, split: dict, backtest: dict, funnel: dict, feasibility: dict, research: dict,
           live: dict, accounts: dict[str, float]) -> list[dict]:
    rows = study["rows"]
    admitted = [r for r in rows if r["stratum"] == ADMITTED]
    expl = [r for r in admitted if r["phase"] == "exploratory"]
    conf = [r for r in admitted if r["phase"] == "confirmatory"]
    red = [r for r in admitted if r["night_regime"] == "red"]
    conf_red = [r for r in conf if r["night_regime"] == "red"]
    yellow = [r for r in conf if r["night_regime"] == "yellow"]
    yellow_a = [r for r in yellow if r["grade_mechanical"] == "A"]
    yellow_a_route = [r for r in yellow_a if is_admitted_route(r)]
    yellow_a_plus_unaccepted = [r for r in yellow if r["grade_mechanical"] == "A+" and not r["reader_accepted"]]
    expl_a = [r for r in expl if r["grade_mechanical"] == "A"]
    accepted = [r for r in rows if r["reader_accepted"] and r["final_grade"] in pipeline.TRADE_GRADES]
    big = [r for r in admitted if accounts[r["publication"]] == 30000]
    big_nights = sorted({r["session"] for r in big})
    yellow_means = so._night_means(yellow_a)
    worst_night = min(yellow_means.items(), key=lambda kv: (kv[1], kv[0]))[0] if yellow_means else None
    others = [r for r in yellow_a if r["session"] != worst_night]
    others_pop = population("the other YELLOW nights", others, spec)
    gate = backtest["gates"]
    red_bt = gate["no_regime_gate"]["by_regime"]["red"]
    a_bt = gate["no_regime_gate"]["by_grade"]["A"]
    production = gate["production"]
    expl_words = "exploratory nights, all RED: tickets the market gate refused, every next close public before the spec froze"
    conf_words = "confirmatory nights, signalled after the freeze: the reader was not consulted for these tickets"
    changes = []

    def change(ident: str, title: str, would: str, status: str, sources: list[dict], period_signs: list[str], notes: list[str]) -> None:
        agree = bool(period_signs) and all(s == "positive" for s in period_signs)
        verdict, because = verdict_of(sources, agree)
        changes.append({"id": ident, "title": title, "would": would, "status": status, "sources": sources,
                        "period_signs": period_signs, "verdict": verdict, "because": because, "notes": notes})

    fy = funnel["reaction_by_regime"].get("yellow", {})
    change("yellow_admits_a", "Admit mechanical A under YELLOW beside A+",
           "widen pipeline.YELLOW_GRADES; a YELLOW night would plan reviewed A names at half size", "floated, not promoted",
           [study_row("study", "direct", "admitted · confirmatory · YELLOW nights · mechanical A", yellow_a, spec,
                      conf_words + "; the population the change would plan, before any review"),
            study_row("study", "direct", "admitted · confirmatory · YELLOW nights · mechanical A · discovery route admitted",
                      yellow_a_route, spec, conf_words + "; the same under the admission rule in force since 4 November"),
            study_row("study", "adjacent", "admitted · exploratory · mechanical A on RED nights", expl_a, spec,
                      expl_words + "; another regime"),
            pasted_row("backtest", "adjacent", "no regime gate · mechanical A · YELLOW and RED nights mixed",
                       a_bt["settled"], a_bt["sum_r"], "owner-pasted summary over 158 sessions; grade not split by regime; reader not run; no rows, so no interval")],
           [split["by_half"]["confirmatory first"]["sign"], split["by_half"]["confirmatory second"]["sign"]],
           [f"the YELLOW A tickets are {len(yellow_means)} nights' and the worst night, {worst_night}, holds {_settled(yellow_a, worst_night)} of their "
            f"{settled_block(yellow_a)['n']} settled (mean {yellow_means[worst_night]:+.3f}R a ticket that night); without it the other "
            f"{others_pop['settled_nights']} nights' {others_pop['settled']['n']} settled read {_r(others_pop['settled']['mean_r'])}R a ticket, "
            f"interval {_ci(others_pop['night_bootstrap'] and others_pop['night_bootstrap']['ci95'])}: {others_pop['sign']}",
            f"the funnel over {funnel['regimes'].get('yellow', 0)} YELLOW publications: {fy.get('grade', 0)} reaction candidates stopped at the "
            f"band's A+ gate, {fy.get('route', 0)} at the discovery route, {fy.get('review_refused', 0)} refused and {fy.get('review_downgraded', 0)} "
            f"lowered by the reader, {fy.get('ticket', 0)} tickets; what the reader would have done with the A names is NOT RUN",
            "a YELLOW night with a reviewed A name has never been published, so the reader's own verdict on this population does not exist"])

    change("trade_red_nights", "Trade on RED nights (remove or relax the market gate)",
           "breadth's RED verdict would stop refusing new longs", "floated, not promoted",
           [study_row("study", "direct", "admitted · exploratory · every night RED", expl, spec, expl_words),
            study_row("study", "direct", "admitted · confirmatory · RED nights", conf_red, spec, conf_words),
            study_row("study", "direct", "admitted · both phases · RED nights", red, spec, "the two phases pooled over RED nights"),
            study_row("study", "direct", "every stratum · both phases · RED nights",
                      [r for r in rows if r["night_regime"] == "red"], spec, "every burst ticketed, whatever its grade"),
            pasted_row("backtest", "direct", "no regime gate · RED nights", red_bt["settled"], red_bt["sum_r"],
                       "owner-pasted summary; reader not run; no rows, so no interval")],
           [split["by_phase"]["exploratory"]["sign"], split["by_regime"]["confirmatory red"]["sign"]],
           ["the exploratory sign held as the study grew (negative at 267 settled on 12 October, at 303 now); the confirmatory RED nights, "
            "read for the first time, straddle zero",
            "the backtest's RED-night counterfactual is a positive sum over 25 settled tickets with no interval; its period (Feb-Sep) and "
            "universe differ from the study's"])

    journal = research["journal"]
    change("anticipation_stop_5pct", "Widen the anticipation stop cap from 4% to 5%",
           "the registered research version anticipation_stop_width_4_to_5_v1, prospective from 12 October to 6 November",
           "floated, not promoted; the registered period has ended",
           [pasted_row("research_journal", "direct", f"registered cohort · {journal['eligible']} eligible rows over {journal['cohorts']} cohorts",
                       journal["by_status"]["resolved"], 0.0,
                       "frozen prospective journal; resolved rows carry the only R; none resolved inside the registered period")],
           [], [f"journal status counts: {json.dumps(journal['by_status'], sort_keys=True)}",
                f"the registered period ran to {research['applicable']['through']} and the cohort for {research['applicable_session']} reads "
                f"{research['status']}; the experiment ended with no resolved row, so it is a design that produced no result, and a new "
                "registration would be a new experiment",
                "the $30,000 account from 4 November was refused inside the period (a changed account is not the registered experiment), "
                "so its last two sessions carry no cohort"])

    change("ticket_without_accepted_review", "Write an A+ ticket on the checklist alone when the reader refuses or fails",
           "drop the accepted-review requirement in pipeline._make_plans for A+ names", "floated, not promoted",
           [study_row("study", "direct", "admitted · confirmatory · YELLOW nights · mechanical A+ without an accepted review",
                      yellow_a_plus_unaccepted, spec, conf_words + "; the rows the change would admit"),
            pasted_row("backtest", "direct", "production policy · YELLOW A+ · reader not run",
                       production["settled"], production["sum_r"],
                       "owner-pasted summary over 158 sessions: the mechanical policy's own first readable rate, no interval"),
            study_row("study", "adjacent", "reader-accepted A/A+ (the live policy's own admissions)", accepted, spec,
                      "the only rows the reader admitted: the population the change would keep, not the one it would add"),
            pasted_row("live_scorecard", "adjacent", f"the published record's own model plans through {live['session']}",
                       live["settled"], live["sum_r"],
                       "the record's daily-bar replay of the plans it issued, burst and anticipation together; a count under its own floor")],
           [], [f"the backtest's production policy: {production['settled']} settled, win rate {production['win_rate']}, "
                f"mean {production['mean_r']}R, median {production['median_r']}R, SPY {production['spy_avg_pct']}% over the same windows",
                f"the live policy wrote its first burst tickets on 4 November (three A+ names with accepted reviews) and every one reads "
                f"stopped on its first day; the scorecard reads {live['settled']} settled of {live['plans']} plans, {live['sum_r']:+.2f}R in sum",
                "the retained HAE reply (8 October) is the case this change would admit: a mechanical A+ whose reply cited paths "
                "outside the authority contract and was refused; tests/fixtures/grading/reader-hae/ holds it rejected"])

    change("account_or_risk_increase", "Raise the base risk or the account so more names size to a whole share",
           "a sizing change, not a strategy change: the same tickets at more shares",
           "promoted in part on 4 November: the production account is $30,000 / 0.5% from that session (the owner's decision)",
           [study_row("study", "direct", f"admitted · publications sized at $30,000 ({', '.join(big_nights)})", big, spec,
                      "the nights published at the new account; a sizing change moves no ticket's sign"),
            pasted_row("live_scorecard", "direct",
                       f"the published record's own model plans through {live['session']} "
                       f"({sum(1 for p in live['open_plans'] if p['status'] == 'stopped')} of its open plans the $30,000 burst tickets, each stopped)",
                       live["settled"], live["sum_r"],
                       "the record's daily-bar replay of the plans it issued at every account it archived; it does not split its R by "
                       "account, and a stopped plan's R is the fill against the planned risk, not a fixed -1R; a count under its own floor")],
           [],
           [f"the feasibility reading: under YELLOW, {feasibility['account_30000']['bands']['yellow']['whole_share']} of "
            f"{feasibility['account_30000']['bands']['yellow']['in_band']} in-band names size to a whole share at $30,000 against "
            f"{feasibility['archived']['bands']['yellow']['whole_share']} of {feasibility['archived']['bands']['yellow']['in_band']} at the archived "
            "accounts ($10,000 for 22 publications, $2,000 for 22, $30,000 for 3)",
            "the price ceiling decides which names can be bought, not whether they win; a larger risk fraction multiplies the R of the "
            "same tickets and changes nothing about their sign",
            f"the $30,000 nights are {len(big_nights)}; one of them, {big_nights[0] if big_nights else '—'}, carries every settled ticket so far, "
            "so no interval exists"])

    route_kept = [r for r in admitted if is_admitted_route(r)]
    route_stopped = [r for r in admitted if not is_admitted_route(r)]
    change("dollar_only_admission", "Admit a dollar-only discovery only on a range-expansion, higher-volume day",
           "src/admission.py, burst_route_or_dollar_expansion_v1: a name the dollar scan alone found is planned and read only "
           "when its burst day passed the checklist's RE and VOL checks",
           "promoted on 4 November (the owner chose it among three options); this is the evidence read after the fact",
           [study_row("study", "direct", "admitted stratum · every night · discovery route admitted", route_kept, spec,
                      "the population the rule keeps, re-derived from each publication's own rows"),
            study_row("study", "direct", "admitted stratum · YELLOW nights · discovery route admitted",
                      [r for r in route_kept if r["night_regime"] == "yellow"], spec, "the kept population on the nights a ticket is possible"),
            study_row("study", "direct", "admitted stratum · RED nights · discovery route admitted",
                      [r for r in route_kept if r["night_regime"] == "red"], spec, "the kept population on nights the gate refused"),
            study_row("study", "removed", "admitted stratum · every night · discovery route stopped", route_stopped, spec,
                      "the population the rule stops: dollar-only names without a range-expansion, higher-volume day"),
            study_row("study", "removed", "admitted stratum · YELLOW nights · discovery route stopped",
                      [r for r in route_stopped if r["night_regime"] == "yellow"], spec, "the stopped population on YELLOW nights")],
           [split["by_route"]["red nights route-admitted"]["sign"], split["by_route"]["yellow nights route-admitted"]["sign"]],
           [f"the rule was promoted without an outcome reading; this one finds no sign either way: the kept population's mean a ticket "
            f"({settled_block(route_kept)['mean_r']:+.3f}R over {settled_block(route_kept)['n']} settled) is worse than the stopped one's "
            f"({settled_block(route_stopped)['mean_r']:+.3f}R over {settled_block(route_stopped)['n']}), the 4 November burst-route tickets carrying it, "
            "and neither interval is clear of zero",
            f"the funnel: {funnel['reaction']['route']} in-band names stopped at the discovery route since the rule (every one on 4 November, "
            "the only YELLOW night since), none read",
            "the study rows are not the rule's own population: it stops a name before its chart is read, and the reader's effect on the kept names is NOT RUN"])
    return changes


# ----------------------------------------------------------------- build ----


def build() -> dict:
    study, study_sha = bf.load_study(STUDY)
    if study.get("version") != so.VERSION:
        raise ReviewError("the study is not a signal-outcomes-v1 file")
    spec = so.load_spec(ROOT / STUDY_SPEC)
    if spec["_sha256"] != study["spec_sha256"]:
        raise ReviewError("the study was not run under the committed extended spec")
    findings, findings_source = load_findings()
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
    extract, scorecard_src = load_scorecard()
    join, join_source = load_admission(spec)

    rows = study["rows"]
    accounts: dict[str, float] = {}
    for p in join["publications"]:
        if not isinstance(p.get("account_equity"), (int, float)):
            raise ReviewError(f"{p['commit'][:8]}: the join carries no account for this publication")
        accounts[p["commit"][:8]] = float(p["account_equity"])
    spec_commits = {e["commit"][:8] for e in spec["publications"]}
    if set(accounts) != spec_commits:
        raise ReviewError("the admission join does not cover the spec's publications")
    for r in rows:
        key = f"{r['publication']}:{r['ticker']}"
        entry = join["rows"].get(key)
        if entry is None:
            raise ReviewError(f"{key}: no admission join for this study row")
        if entry["scan"] != r["scan"]:
            raise ReviewError(f"{key}: the join's scan differs from the study row's")
        r["admission"] = {"admitted": bool(entry["admitted"]), "basis": entry["basis"]}
    regimes = {r["night_regime"] for r in rows}
    if not regimes <= set(REGIMES):
        raise ReviewError(f"the study holds nights the review does not describe: {sorted(regimes - set(REGIMES))}")
    nights_by_regime = {regime: len({r["session"] for r in rows if r["night_regime"] == regime}) for regime in sorted(regimes)}
    split = periods(rows, spec, accounts)
    backtest = backtest_sources(findings)
    funnel = funnel_source(funnel_history)
    feasibility = {k: feasibility_source(h) for k, h in feasibility_history.items()}
    research = research_source(cohort, journal)
    live = scorecard_source(extract)
    bases = defaultdict(int)
    for r in rows:
        bases[r["admission"]["basis"]] += 1
    return {
        "version": VERSION,
        "review_date": REVIEW_DATE,
        "supersedes": "2026-10-12-evidence-review-evidence (evidence-review-v1), frozen as written",
        "criteria": CRITERIA,
        "sources": {
            "study": bf.source(STUDY, kind="tool_output", uncompressed_sha256=study_sha, spec=bf.source(STUDY_SPEC)),
            "findings": findings_source,
            "funnel": bf.source(FUNNEL, kind="tool_output"),
            "feasibility": {k: bf.source(p, kind="tool_output") for k, p in FEASIBILITY.items()},
            "research": {"cohort": cohort_source, "journal": journal_source},
            "scorecard": scorecard_src,
            "admission": join_source,
        },
        "evidence_through": {"study_newest_session": study["newest_session"],
                             "study_frozen_through": study["frozen_through_session"],
                             "backtest_through": backtest["evaluated"]["through"],
                             "funnel_sessions": funnel["sessions"],
                             "research_applicable_session": research["applicable_session"],
                             "scorecard_session": live["session"]},
        "study": {"rows": len(rows), "publications": len(study["publications"]), "night_regimes": sorted(regimes),
                  "nights_by_regime": nights_by_regime, "admission_bases": dict(sorted(bases.items())),
                  "crosscheck": crosscheck(study), "costs_per_side_bps": costs(study),
                  "drawdown": {stratum: drawdown([r for r in rows if r["stratum"] == stratum]) for stratum in STRATA}
                  | {"all": drawdown(rows)}},
        "periods": split,
        "backtest": backtest,
        "funnel": funnel,
        "feasibility": feasibility,
        "research": research,
        "live_scorecard": live,
        "ledger": ledger(study, spec, split, backtest, funnel, feasibility, research, live, accounts),
        "limits": [
            "The study tickets every burst without the reader, the gate or a slot cap and walks it on daily bars; its exploratory "
            "nights were all RED and every next close was public before the spec froze; its confirmatory nights are RED and YELLOW.",
            "The admission join re-derives src/admission.py over each publication's rows, which the study never applied: the reader's "
            "effect on the kept names is NOT RUN, and the rule stops a name before any chart is read.",
            "The backtest's universe is the archive's later membership, its fills daily-bar, its reader not run, and it was pasted as "
            "a summary: no interval can be drawn from it.",
            "GREEN has never been published or observed in 158 backtest sessions; nothing here speaks to a GREEN night.",
            "The registered research period ended on 6 November with no resolved row.",
            "The live scorecard is the record's own replay of the plans it issued, under its own floor of "
            f"{MIN_SETTLED} settled; it is a count, never an edge.",
            "A verdict here reads evidence sufficiency under the criteria above; it is not a recommendation, and no change is "
            "promoted by this file. The two changes marked promoted were the owner's decisions, read here after the fact.",
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
    lines = [f"# Evidence review ({review['version']}, {review['review_date']})", "",
             "Generated by `python tools/evidence_review.py` from the committed evidence named below; "
             "`--check` holds this file and `review.json` beside it. A reading, not a rule: no number here "
             "changes a threshold, a record or the account, and no change is promoted by it. "
             f"Supersedes {review['supersedes']}.", ""]
    lines += ["## Sources", "", "| source | path | SHA-256 |", "|---|---|---|"]
    flat = []
    for name, src in review["sources"].items():
        if "path" in src:
            flat.append((name, src))
        else:
            flat += [(f"{name} · {k}", v) for k, v in src.items()]
    for name, src in flat:
        lines.append(f"| {name} | `{src['path']}` | `{src['sha256'][:16]}…` |")
    lines += ["", f"The findings, research, scorecard and admission inputs retain the exact bytes used on {review['review_date']}; "
              "their digests are checked before reading. The rolling findings file and companions may advance without revising "
              "this dated review. Original sources:", ""]
    retained = [("findings", review["sources"]["findings"]), *review["sources"]["research"].items(),
                ("scorecard", review["sources"]["scorecard"])]
    for name, src in retained:
        origin = src["origin"]
        lines.append(f"- {name}: `{origin['path']}` at commit `{origin['commit']}`.")
    adm = review["sources"]["admission"]["origin"]
    lines.append(f"- admission join: `{adm['policy']}` (version {adm['version']}) re-derived over every publication of `{adm['spec']}`.")
    et = review["evidence_through"]
    lines += ["", f"Evidence through: study newest session {et['study_newest_session']} (frozen through "
              f"{et['study_frozen_through']}); backtest through {et['backtest_through']}; funnel over "
              f"{et['funnel_sessions']} sessions; research applicable session {et['research_applicable_session']}; "
              f"live scorecard at the {et['scorecard_session']} publication.", ""]
    lines += ["## Criteria", "", f"A rate is read at {review['criteria']['min_settled']} settled tickets or more "
              "(`record.SCORECARD_MIN_PLANS`); below it a population is a count. " + review["criteria"]["interval"] + ".", ""]
    for kind in ("sign", "verdict", "scope"):
        lines += [f"**{kind}**", ""] + [f"- `{k}`: {v}" for k, v in review["criteria"][kind].items()] + [""]
    st = review["study"]
    regimes = ", ".join(f"{n} {regime.upper()}" for regime, n in st["nights_by_regime"].items())
    bases = ", ".join(f"{n} {basis}" for basis, n in st["admission_bases"].items())
    lines += ["## The study, re-derived from its rows", "",
              f"{st['rows']} rows over {st['publications']} publications; nights {regimes}; discovery bases {bases}.", "",
              "| population | settled | wins / losses / even | sum R | mean R | median R |", "|---|---:|---:|---:|---:|---:|"]
    for name, s in st["crosscheck"].items():
        lines.append(f"| {name} | {s['n']} | {s['wins']} / {s['losses']} / {s['breakeven']} | {_r(s['sum_r'], 2)} | {_r(s['mean_r'])} | {_r(s['median_r'], 2)} |")
    lines += ["", "### Costs per side (mean settled R)", "", "| stratum | 0 bps | 5 bps | 20 bps |", "|---|---:|---:|---:|"]
    for stratum, c in st["costs_per_side_bps"].items():
        lines.append(f"| {stratum} | {_r(c['0']['mean_r'])} | {_r(c['5']['mean_r'])} | {_r(c['20']['mean_r'])} |")
    lines += ["", "### Drawdown of the cumulative-R path", "",
              "Settled tickets in the study's own order (session, then row order); a stream no slot cap held, so a "
              "path of R paid and not an equity curve. The night-means path sums each night's mean R once.", "",
              "| stratum | settled | final R | deepest fall (R) | from | to | night-means final R | night-means deepest fall |",
              "|---|---:|---:|---:|---|---|---:|---:|"]
    for stratum, d in st["drawdown"].items():
        n = d["night_means"]
        lines.append(f"| {stratum} | {d['settled']} | {_r(d['final_r'], 2)} | {d['max_drawdown_r']:.2f} | {d['drawdown_from'] or '—'} | "
                     f"{d['drawdown_to'] or '—'} | {_r(n['final_r'], 2)} | {n['max_drawdown_r']:.2f} |")
    lines += ["", "## Separate evaluation periods (admitted stratum unless named)", "",
              "| population | sessions | nights | nights settled | settled | wins / losses / even | mean R | 95% night CI | sign |",
              "|---|---|---:|---:|---:|---:|---:|---|---|"]
    for group in review["periods"].values():
        for pop in group.values():
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
              f"Funnel (at `{f['ref']}`): {f['publications']} publications over {f['sessions']} sessions ({json.dumps(f['regimes'], sort_keys=True)}); "
              f"{f['discovered']} reaction candidates discovered, {f['reaction']['market']} stopped at the market, "
              f"{f['reaction']['grade']} at the grade, {f['reaction']['route']} at the discovery route, "
              f"{f['reaction']['preview_sizing']} at the preview's sizing, {f['potentially_usable']} potentially usable, "
              f"{f['reaction']['review_refused']} refused by reader authority, {f['reaction']['review_downgraded']} lowered, "
              f"{f['reaction']['ticket']} tickets; {f['listed']} anticipation setups listed, {f['anticipation']['ticket']} tickets.", "",
              "| regime | grade | route | review refused | review lowered | preview sizing | ticket |", "|---|---:|---:|---:|---:|---:|---:|"]
    for regime, stages in sorted(f["reaction_by_regime"].items()):
        lines.append(f"| {regime} | {stages['grade']} | {stages['route']} | {stages['review_refused']} | {stages['review_downgraded']} | "
                     f"{stages['preview_sizing']} | {stages['ticket']} |")
    lines += ["", "| account | tonight: in band / stop rule / whole share | YELLOW | GREEN |", "|---|---:|---:|---:|"]
    for name, fe in review["feasibility"].items():
        b = fe["bands"]
        cell = lambda band: f"{b[band]['in_band']} / {b[band]['past_stop_rule']} / {b[band]['whole_share']}"  # noqa: E731
        accounts = ", ".join(f"{n} × {label}" for label, n in sorted(fe["accounts"].items()))
        lines.append(f"| {name} ({accounts}) | {cell('tonight')} | {cell('yellow')} | {cell('green')} |")
    r = review["research"]
    lines += ["", "## The registered research", "",
              f"`{r['policy']}` ({r['status']}): stop cap {r['stop_pct']['baseline']}% → {r['stop_pct']['research']}%, applicable "
              f"{r['applicable']['from']} → {r['applicable']['through']}; the cohort for {r['applicable_session']} considered "
              f"{r['cohort_counts']['considered']} with {r['cohort_counts']['allocation_fit']} allocation-fit rows; journal "
              f"`{r['journal']['policy']}`: {r['journal']['rows']} rows over {r['journal']['cohorts']} cohorts, {r['journal']['eligible']} "
              f"eligible, by status {json.dumps(r['journal']['by_status'], sort_keys=True)}.", ""]
    lv = review["live_scorecard"]
    plans = "; ".join(f"{p['ticker']} ({p['kind']}, {p['shares']} shares, {p['status']})" for p in lv["open_plans"]) or "none"
    lines += ["## The live policy's own scorecard", "",
              f"The {lv['session']} publication (rules `{lv['rules_version']}`, account ${lv['account']['equity']:,.0f} / "
              f"{lv['account']['risk_pct']}%): {lv['plans']} model plans over its {lv['population']['from']} → {lv['population']['through']} "
              f"window, {lv['settled']} settled ({lv['wins']} wins, {lv['losses']} losses, {lv['breakeven']} even, {_r(lv['sum_r'], 2)}R in sum), "
              f"{lv['not_filled']} not filled, {lv['uncertain']} uncertain, {lv['open']} open, {lv['pending']} pending; readable "
              f"{str(lv['readable']).lower()} under its floor of {lv['min_read']}. Open model plans: {plans}.", ""]
    lines += ["## The ledger", ""]
    for c in review["ledger"]:
        lines += [f"### {c['title']} — **{c['verdict']}**", "", f"Would: {c['would']}.", "", f"Status: {c['status']}.", ""]
        if c["sources"]:
            lines += ["| source | scope | population | settled | nights | mean R | 95% night CI | sign |", "|---|---|---|---:|---:|---:|---|---|"]
            for s in c["sources"]:
                lines.append(f"| {s['source']} | {s['scope']} | {s['population']} | {s['settled']} | {s['nights'] if s['nights'] is not None else '—'} | "
                             f"{_r(s['mean_r'])} | {_ci(s['ci95'])} | {s['sign']} |")
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
    parser.add_argument("--retain", action="store_true",
                        help=f"write the retained inputs under {INPUTS} from git at {ORIGIN_COMMIT[:8]} once, then exit")
    parser.add_argument("--output-dir", type=Path, default=OUT_DIR, help=f"where to write (default {OUT_DIR})")
    args = parser.parse_args(argv)
    if args.retain:
        try:
            digests = retain_inputs(ROOT / INPUTS)
        except (ReviewError, so.StudyError, OSError, KeyError, ValueError) as exc:
            print(f"evidence review: {exc}")
            return 2
        for name, digest in digests.items():
            print(f"retained {name} {digest}")
        return 0
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
