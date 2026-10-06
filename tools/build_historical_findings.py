"""Build ``docs/historical-findings.json``: the October 2026 validation
findings, reduced to what the Record view prints, every number read off
a committed evidence file and bound to that file's digest.

This is a READER, not a study and not a check. It changes no production
number, no record, no rule and no historical ticket. It reads four kinds
of committed evidence and nothing else:

* the signal-outcome study's own output (``signal-outcomes.json.gz``,
  written by ``tools/signal_outcomes.py`` under its frozen spec), from
  which the per-night, per-stratum outcomes and the headline strata are
  taken; the first read of 2 October is read beside the 6 October re-run
  so the page can show how a night's number moved as its sessions
  completed;
* the publication records the study's spec names, read from this
  checkout's git objects by commit and held to the blob the spec
  recorded (``signal_outcomes.load_publications``), for the market the
  gate read each night -- the 10-session ratio, the verdict, the counts
  and the thirty sessions of history each record carries;
* the owner's two pasted backtest summaries, parsed by the exact line
  grammar ``historical_backtest.summary_text()`` emits (a line the
  grammar does not know is a refusal, never a skipped number);
* the owner's pasted run-6 summary and the public run receipt.

A number the evidence does not carry is not derived here: the page
prints this file verbatim and computes nothing of the market. The
builder's only arithmetic is the per-night, per-stratum count, sum and
mean of settled R over the study's own rows, and ``tests/
test_historical_findings.py`` re-derives every one of those from the
same rows.

``python tools/build_historical_findings.py`` writes the file;
``--check`` compares and exits 1 on a difference, the way
``make_fixture.py --check`` holds the fixtures.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import signal_outcomes as so  # noqa: E402

VERSION = "historical-findings-v1"
OUTPUT = ROOT / "docs" / "historical-findings.json"
TRUTH = Path("docs/input-truthfulness")
STUDY = TRUTH / "2026-10-06-signal-outcomes-confirmatory-evidence" / "signal-outcomes.json.gz"
STUDY_SPEC = TRUTH / "2026-10-06-signal-outcomes-spec-extended.json"
FIRST_STUDY = TRUTH / "2026-10-02-signal-outcomes-evidence" / "signal-outcomes.json.gz"
FIRST_SPEC = TRUTH / "2026-10-02-signal-outcomes-spec.json"
BACKTEST_DIR = TRUTH / "2026-10-06-backtest-results-evidence"
BACKTESTS = {"lookback_130": BACKTEST_DIR / "lookback-130-summary.txt",
             "lookback_260": BACKTEST_DIR / "lookback-260-summary.txt"}
RUN6_DIR = TRUTH / "2026-10-02-historical-run6-evidence"
STUDY_RUN_RECORD = STUDY.parent / "run-record.txt"
RUN6_SUMMARY = RUN6_DIR / "owner-summary.txt"
RUN6_PUBLIC = RUN6_DIR / "public-run.json"
REPORTS = (
    ("The first real-bar outcomes (2 October)", TRUTH / "2026-10-02-signal-outcomes.md"),
    ("The confirmatory read (6 October)", TRUTH / "2026-10-06-signal-outcomes-confirmatory.md"),
    ("The owner's backtest over the run-6 archive (6 October)", TRUTH / "2026-10-06-backtest-results.md"),
    ("The mechanical backtest tool (2 October)", TRUTH / "2026-10-02-mechanical-backtest.md"),
    ("Run 6: the RED reading on fresh bars (2 October)", TRUTH / "2026-10-02-historical-run6-result.md"),
    ("The 28 September validation review", TRUTH / "2026-09-28-validation-review.md"),
)
STRATA = ("admitted", "B", "C", "skip", "vetoed")
BUCKETS = ("settled", "open", "pending", "uncertain", "not_filled", "unmeasured",
           "no_ticket", "basis_mismatch", "plan_error", "unreadable", "unscored")
# A stratum's settled R, as the study wrote it (two decimals), is kept in
# full so the page can draw every ticket; its sum and mean are rounded ONCE,
# the way the study rounds its own by-night mean.
SUM_DECIMALS, MEAN_DECIMALS = 2, 3
# Field names gitleaks' generic-api-key rule reads as a credential's name;
# nothing this file writes may be called one (the test holds it).
CREDENTIAL_WORDS = re.compile(r"(api|key|token|secret|auth|access|credential|passw)", re.I)


class FindingsError(RuntimeError):
    """A line the grammar does not know, or evidence that does not reconcile."""


# ------------------------------------------------------------ evidence ----


def sha256_of(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def load_study(path: Path) -> tuple[dict, str]:
    raw = gzip.decompress((ROOT / path).read_bytes())
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def source(path: Path, **extra) -> dict:
    return {"path": str(path), "sha256": sha256_of(path), **extra}


# --------------------------------------------------------------- market ----


def market_series(pubs: list[dict], nights: dict[str, dict]) -> dict:
    """One row per session the records know, oldest first. A session the
    gate read (a publication night) carries what THAT night's own first
    publication read; a session no publication measured carries the newest
    publication's history of it. Each row names its source, and a night
    whose later histories re-measured it says so."""
    ordered = sorted(pubs, key=lambda p: (p["session"], p["data"]["run"].get("published_at") or ""))
    thresholds = None
    history: dict[str, dict] = {}
    for p in ordered:
        b = p["data"]["breadth"]
        t = {k: b["regime"]["thresholds"][k] for k in ("ratio_10d_red", "ratio_10d_yellow")}
        if thresholds not in (None, t):
            raise FindingsError(f"{p['commit'][:8]}: the ratio thresholds moved: {t} after {thresholds}")
        thresholds = t
        for row in b["history"]:
            history[row["date"]] = {"date": row["date"], "up4": row["up4"], "down4": row["down4"],
                                    "ratio_10d": row["ratio_10d"], "source": p["commit"][:8], "basis": "history"}
    sessions = []
    for day in sorted(set(history) | set(nights)):
        night = nights.get(day)
        later = history.get(day)
        if night:
            row = {"date": day, "up4": night["regime"]["up4"], "down4": night["regime"]["down4"],
                   "ratio_10d": night["regime"]["ratio_10d"], "source": night["commit"][:8],
                   "basis": "publication", "verdict": night["regime"]["verdict"]}
            if later and later["ratio_10d"] != row["ratio_10d"]:
                row["later_ratio_10d"] = later["ratio_10d"]
                row["later_source"] = later["source"]
        else:
            row = dict(later, verdict=None)
        sessions.append(row)
    return {"from": sessions[0]["date"], "through": sessions[-1]["date"], "thresholds": thresholds,
            "sessions": sessions,
            "basis": "A publication night carries the ratio and counts its own first publication read; "
                     "any other session carries the newest publication's history of it, and a night a later "
                     "history re-measured names the later value beside its own."}


# --------------------------------------------------------------- nights ----


def settled_block(rs: list[float]) -> dict:
    if not rs:
        return {"n": 0, "wins": 0, "losses": 0, "breakeven": 0, "sum_r": None, "mean_r": None, "median_r": None}
    return {"n": len(rs), "wins": sum(1 for r in rs if r > 0), "losses": sum(1 for r in rs if r < 0),
            "breakeven": sum(1 for r in rs if r == 0), "sum_r": round(math.fsum(rs), SUM_DECIMALS),
            "mean_r": round(math.fsum(rs) / len(rs), MEAN_DECIMALS),
            "median_r": round(statistics.median(rs), SUM_DECIMALS)}


def stratum_of_night(rows: list[dict]) -> dict:
    buckets = Counter(r["bucket"] for r in rows)
    rs = sorted(r["r"] for r in rows if r["bucket"] == "settled")
    return {"rows": len(rows), "buckets": {b: buckets.get(b, 0) for b in BUCKETS},
            "settled": settled_block(rs), "r": rs}


def night_rows(study: dict) -> dict[str, list[dict]]:
    by = defaultdict(list)
    for r in study["rows"]:
        by[r["session"]].append(r)
    return by


def nights_of(pubs: list[dict], study: dict, first: dict) -> list[dict]:
    rows_now, rows_first = night_rows(study), night_rows(first)
    firsts = {p["commit"] for p in study["publications"] if p["first"]}
    out = []
    for p in sorted((p for p in pubs if p["commit"] in firsts), key=lambda p: p["session"]):
        d, b, reg = p["data"], p["data"]["breadth"], p["data"]["breadth"]["regime"]
        rows = rows_now.get(p["session"], [])
        if len(rows) != len(d["bursts"]):
            raise FindingsError(f"{p['session']}: the study carries {len(rows)} rows for {len(d['bursts'])} bursts")
        grades = Counter(x.get("grade_mechanical") for x in d["bursts"])
        final = Counter(x.get("grade") for x in d["bursts"])
        horizon = next((r["horizon"] for r in rows if r.get("horizon")), None)
        phases = {r["phase"] for r in rows}
        if len(phases) != 1:
            raise FindingsError(f"{p['session']}: one night, {len(phases)} phases")
        strata = {s: stratum_of_night([r for r in rows if r["stratum"] == s]) for s in STRATA}
        night = {
            "session": p["session"], "commit": p["commit"], "blob": p["blob"],
            "published_at": d["run"].get("published_at"), "status": d["run"].get("status"),
            "regime": {"verdict": reg["verdict"], "size_multiplier": reg["size_multiplier"],
                       "reasons": list(reg["reasons"]), "ratio_10d": b["ratio_10d"], "ratio_5d": b["ratio_5d"],
                       "up4": b["up4"], "down4": b["down4"], "up4_10d": b["up4_10d"], "down4_10d": b["down4_10d"],
                       "universe": b["universe"]},
            "bursts": len(d["bursts"]),
            "grades_mechanical": {g: grades.get(g, 0) for g in ("A+", "A", "B", "C", "skip")},
            "grades_final": {g: final.get(g, 0) for g in ("A+", "A", "B", "C", "skip")},
            "vetoed": sum(1 for x in d["bursts"] if x.get("vetoes")),
            "reads": d["run"].get("reads"),
            "tickets_published": len(d.get("trades") or []),
            "phase": phases.pop(), "horizon": horizon,
            "complete": bool(horizon) and horizon <= study["newest_session"],
            "strata": strata, "all": stratum_of_night(rows),
        }
        if p["session"] in rows_first:
            night["first_read"] = {"as_of": first["newest_session"],
                                   "admitted": stratum_of_night([r for r in rows_first[p["session"]]
                                                                 if r["stratum"] == "admitted"])["settled"],
                                   "all": stratum_of_night(rows_first[p["session"]])["settled"]}
        out.append(night)
    return out


RULE_FIELDS = (("record", "open_plan_sessions"), ("record", "scorecard_min_plans"), ("pipeline", "trade_grades"),
               ("pipeline", "yellow_grades"), ("pipeline", "max_reads"), ("breadth", "size_multiplier"),
               ("breadth", "red_ratio_10d"), ("breadth", "yellow_ratio_10d"), ("breadth", "burst_pct"),
               ("breadth", "ratio_long_sessions"), ("breadth", "ratio_short_sessions"))


def rules_of(pubs: list[dict]) -> dict:
    """The few rule numbers the page's captions name, read off the records'
    own archived rules and held equal across every publication the study
    read: a caption never types a strategy number."""
    out: dict = {}
    for p in pubs:
        for module, name in RULE_FIELDS:
            value = p["data"]["rules"][module][name]
            found = out.setdefault(module, {})
            if name in found and found[name] != value:
                raise FindingsError(f"{p['commit'][:8]}: rules.{module}.{name} moved: {value} after {found[name]}")
            found[name] = value
    return out


def strata_summary(study: dict) -> dict:
    def reduced(block: dict) -> dict:
        if not block or block.get("rows") in (None, 0) or "settled" not in block:
            return {"rows": (block or {}).get("rows", 0)}
        sc = block["scorecard"]
        return {"rows": block["rows"], "buckets": block["buckets"], "settled": block["settled"],
                "night_bootstrap": block["night_bootstrap"], "uncertain_bound": block["uncertain_bound"],
                "costs_per_side_bps": block["costs_per_side_bps"],
                "scorecard": {k: sc.get(k) for k in ("readable", "min_read", "win_rate", "avg_r", "median_r",
                                                      "plans", "filled")}}
    s = study["summary"]
    return {"all": reduced(s["all"]), "strata": {k: reduced(s["strata"][k]) for k in STRATA},
            "phases": {k: reduced(v) for k, v in s["phases"].items()},
            "reader_accepted": reduced(s["reader_accepted"])}


# -------------------------------------------------------------- backtest ----

_NUM = r"(—|-?\d+(?:\.\d+)?)"
BT = {
    "head": re.compile(r"^SpicyStock mechanical backtest \((.+)\) — no price in this summary$"),
    "archive": re.compile(r"^archive: (\d+) symbols with bars of (\d+) intended; sessions (\S+) \.\. (\S+) \((\d+)\); statuses (\{.*\})$"),
    "evaluated": re.compile(r"^evaluated: (\d+) sessions (\S+) \.\. (\S+) in (\d+(?:\.\d+)?) s; lookback (\d+) of the run's (\d+); rules (\w+)$"),
    "equivalence": re.compile(r"^lookback equivalence: (.+) \((\d+) sessions compared, (\d+) differences\)$"),
    "account": re.compile(r"^account \(configured, not a balance\): (\{.*\})$"),
    "reader": re.compile(r"^reader: (.+)$"),
    "regimes": re.compile(r"^regimes: (\{.*\}); 10-session ratio min/median/max " + _NUM + "/" + _NUM + "/" + _NUM + r" over (\d+) defined$"),
    "candidates": re.compile(r"^candidates: (\d+) bursts over (\d+) sessions; mechanical grades (\{.*\})$"),
    "gate": re.compile(r"^\[(PRODUCTION POLICY|COUNTERFACTUAL — regime gate removed \(not a policy\))\]$"),
    "tickets": re.compile(r"^tickets (\d+), by the night's regime (\{.*\})$"),
    "plans": re.compile(r"^plans (\d+): settled (\d+), open (\d+), pending (\d+), uncertain (\d+) (\[.*\]), not filled (\d+), unmeasured (\d+), unreadable (\d+), unscored (\d+)$"),
    "settled": re.compile(r"^settled (\d+): wins (\d+), losses (\d+), breakeven (\d+); sum R " + _NUM + "; avg R " + _NUM
                          + "; median R " + _NUM + "; win rate " + _NUM + r" \(rates read only at (\d+)\+ settled: readable=(True|False)\); SPY avg % over (\d+) pairs " + _NUM + "$"),
    "by": re.compile(r"^  by (grade|regime) (\S+): plans (\d+), settled (\d+), wins (\d+), losses (\d+), sum R " + _NUM + "$"),
    "limitations": re.compile(r"^limitations:$"),
    "limitation": re.compile(r"^- (.+)$"),
    "progress": re.compile(r"^(\d{4}-\d{2}-\d{2}) (\w+) ratio " + _NUM + r" counted (\d+) bursts (\d+) tickets (\d+)$"),
    "helper": re.compile(r"^3/4 Exact-lookback replay saved to .+$"),
}
GATE_NAMES = {"PRODUCTION POLICY": "production",
              "COUNTERFACTUAL — regime gate removed (not a policy)": "no_regime_gate"}


def _num(s: str):
    if s == "—":
        return None
    return int(s) if re.fullmatch(r"-?\d+", s) else float(s)


def _literal(s: str):
    return ast.literal_eval(s)


def parse_backtest_summary(text: str) -> dict:
    """The pasted summary back into the counts ``summary_text`` printed.
    Every line must match one grammar line; '—' stays None and is never a
    number; the six progress lines a run prints before its summary and the
    owner's helper line after it are kept, named, and nothing else is."""
    out: dict = {"progress": [], "gates": {}, "limitations": []}
    gate = None
    mode = "head"
    for raw in text.splitlines():
        line = raw.rstrip("\r")
        if not line.strip():
            continue
        if mode == "limitations":
            m = BT["limitation"].match(line)
            if m:
                out["limitations"].append(m.group(1))
                continue
            m = BT["helper"].match(line)
            if m:
                out["helper_line"] = line
                mode = "done"
                continue
            raise FindingsError(f"backtest summary: unexpected line after limitations: {line!r}")
        if mode == "done":
            raise FindingsError(f"backtest summary: unexpected line after the helper: {line!r}")
        if (m := BT["progress"].match(line)) and mode == "head" and "version" not in out:
            out["progress"].append({"session": m.group(1), "verdict": m.group(2), "ratio_10d": _num(m.group(3)),
                                    "counted": int(m.group(4)), "bursts": int(m.group(5)), "tickets": int(m.group(6))})
        elif m := BT["head"].match(line):
            out["version"] = m.group(1)
        elif m := BT["archive"].match(line):
            out["archive"] = {"symbols": int(m.group(1)), "intended": int(m.group(2)),
                              "sessions": {"from": m.group(3), "through": m.group(4), "count": int(m.group(5))},
                              "statuses": _literal(m.group(6))}
        elif m := BT["evaluated"].match(line):
            out["evaluated"] = {"count": int(m.group(1)), "from": m.group(2), "through": m.group(3),
                                "seconds": _num(m.group(4))}
            out["lookback"] = {"sessions": int(m.group(5)), "production": int(m.group(6))}
            out["rules_version"] = m.group(7)
        elif m := BT["equivalence"].match(line):
            out["lookback"]["equivalence"] = {"status": m.group(1), "compared": int(m.group(2)),
                                              "differences": int(m.group(3))}
        elif m := BT["account"].match(line):
            out["account"] = _literal(m.group(1))
        elif m := BT["reader"].match(line):
            out["reader"] = m.group(1)
        elif m := BT["regimes"].match(line):
            out["regimes"] = {"verdicts": _literal(m.group(1)),
                              "ratio_10d": {"min": _num(m.group(2)), "median": _num(m.group(3)),
                                            "max": _num(m.group(4)), "defined": int(m.group(5))}}
        elif m := BT["candidates"].match(line):
            out["candidates"] = {"bursts": int(m.group(1)), "sessions": int(m.group(2)),
                                 "grades_mechanical": _literal(m.group(3))}
        elif m := BT["gate"].match(line):
            gate = GATE_NAMES[m.group(1)]
            out["gates"][gate] = {"label": m.group(1), "by_grade": {}, "by_regime": {}}
        elif m := BT["tickets"].match(line):
            out["gates"][gate]["tickets"] = int(m.group(1))
            out["gates"][gate]["tickets_by_regime"] = _literal(m.group(2))
        elif m := BT["plans"].match(line):
            out["gates"][gate]["plans"] = {
                "plans": int(m.group(1)), "settled": int(m.group(2)), "open": int(m.group(3)),
                "pending": int(m.group(4)), "uncertain": int(m.group(5)),
                "uncertain_reasons": [{"kind": k, "count": n} for k, n in _literal(m.group(6))],
                "not_filled": int(m.group(7)), "unmeasured": int(m.group(8)), "unreadable": int(m.group(9)),
                "unscored": int(m.group(10))}
        elif m := BT["settled"].match(line):
            out["gates"][gate]["settled"] = {
                "n": int(m.group(1)), "wins": int(m.group(2)), "losses": int(m.group(3)), "breakeven": int(m.group(4)),
                "sum_r": _num(m.group(5)), "avg_r": _num(m.group(6)), "median_r": _num(m.group(7)),
                "win_rate": _num(m.group(8)), "min_read": int(m.group(9)), "readable": m.group(10) == "True",
                "spy_pairs": int(m.group(11)), "spy_avg_pct": _num(m.group(12))}
        elif m := BT["by"].match(line):
            out["gates"][gate]["by_" + m.group(1)][m.group(2)] = {
                "plans": int(m.group(3)), "settled": int(m.group(4)), "wins": int(m.group(5)),
                "losses": int(m.group(6)), "sum_r": _num(m.group(7))}
        elif BT["limitations"].match(line):
            mode = "limitations"
        else:
            raise FindingsError(f"backtest summary: a line the grammar does not know: {line!r}")
    for needed in ("version", "archive", "evaluated", "lookback", "account", "reader", "regimes", "candidates"):
        if needed not in out:
            raise FindingsError(f"backtest summary: no {needed} line")
    if set(out["gates"]) != set(GATE_NAMES.values()):
        raise FindingsError(f"backtest summary: gates {sorted(out['gates'])}")
    for g in out["gates"].values():
        for needed in ("tickets", "plans", "settled"):
            if needed not in g:
                raise FindingsError(f"backtest summary: a gate without its {needed} line")
    return out


# ------------------------------------------------------------------ run 6 ----

R6 = {
    "status": re.compile(r"^overall status (\S+)\s+reason (.+)$"),
    "download": re.compile(r"^download: status (\S+)\s+queries completed (\d+) of (\d+)\s+reason (.+)$"),
    "ledger": re.compile(r"^ledger: (\{.*\})$"),
    "session": re.compile(r"^=== (\d{4}-\d{2}-\d{2}) ===$"),
    "s_status": re.compile(r"^\s+status (\S+)\s+formula check (\S+)\s+regime established (\S+)$"),
    "stocks": re.compile(r"^\s+stock statuses: (\{.*\})$"),
    "window": re.compile(r"^\s+every stock has its full required window: (\S+)$"),
    "partial": re.compile(r"^\s+partial \((\d+)\): (.+)$"),
    "missing": re.compile(r"^\s+stocks missing some required sessions \((\d+)\): (.+)$"),
    "policy": re.compile(r"^\s+([CD])\s+(.+): (PASS|FAIL|BLOCKED)$"),
    "calc": re.compile(r"^\s+independent calculator: (\S+)\s+\(rules that fired: (.+)\)$"),
    "ratios": re.compile(r"^\s+10-day up/down (\d+) / (\d+) -> ratio " + _NUM + r"\s+\|\s+5-day (\d+) / (\d+) -> " + _NUM + "$"),
    "day": re.compile(r"^\s+that day up/down (\d+) / (\d+)\s+counted universe (\d+)$"),
    "own": re.compile(r"^\s+app's own code: (\S+)$"),
    "established": re.compile(r"^\s+regime established: (\S+)$"),
    "unknown_events": re.compile(r"^\s+unknown event counts on (\d{4}-\d{2}-\d{2}): (\{.*\})$"),
    "unknown_4pct": re.compile(r"^\s+counted stocks with an unknown 4% event in the 10 days \((\d+)\): (.+)$"),
    "unknown_up50": re.compile(r"^\s+counted stocks with unknown up-50%-month on (\d{4}-\d{2}-\d{2}) \((\d+)\): (.+)$"),
    "bounds": re.compile(r"^\s+10-day ratio could be anywhere in \[" + _NUM + ", " + _NUM + r"\] given (\d+) unknown contributors$"),
    "population": re.compile(r"^\s+population reasons on (\d{4}-\d{2}-\d{2}): (\{.*\})$"),
    "matches": re.compile(r"^\s+diagnostic scan matches \(no grading, no tickets\): (\d+)$"),
}


def _names(s: str) -> list[str]:
    return [] if s.strip() == "none" else [n.strip() for n in re.sub(r"\s*\(\+\d+ more\)$", "", s).split(",")]


def parse_run6_summary(text: str) -> dict:
    out: dict = {"sessions": {}}
    session = policy = None
    lines = text.splitlines()
    if not lines or not lines[0].startswith("SpicyStock run 6 evidence summary"):
        raise FindingsError("run-6 summary: not the owner's summary")
    for raw in lines[1:]:
        line = raw.rstrip("\r")
        if not line.strip():
            continue
        if m := R6["status"].match(line):
            out["status"] = m.group(1)
        elif m := R6["download"].match(line):
            out["download"] = {"status": m.group(1), "queries_completed": int(m.group(2)),
                               "queries_total": int(m.group(3))}
        elif m := R6["ledger"].match(line):
            out["ledger"] = _literal(m.group(1))
        elif m := R6["session"].match(line):
            session = out["sessions"][m.group(1)] = {"date": m.group(1), "policies": {}}
            policy = None
        elif m := R6["s_status"].match(line):
            session.update(status=m.group(1), formula_check=m.group(2), regime_established=m.group(3) == "True")
        elif m := R6["stocks"].match(line):
            session["stock_statuses"] = _literal(m.group(1))
        elif m := R6["window"].match(line):
            session["full_window_every_stock"] = m.group(1) == "True"
        elif m := R6["partial"].match(line):
            session["partial"] = int(m.group(1))
            session["partial_sample"] = _names(m.group(2))
        elif m := R6["missing"].match(line):
            session["missing_sessions"] = int(m.group(1))
        elif m := R6["policy"].match(line):
            policy = session["policies"][m.group(1)] = {"label": m.group(2), "check": m.group(3)}
        elif m := R6["calc"].match(line):
            policy["independent_verdict"] = m.group(1).lower()
            policy["rules_fired"] = [r.strip() for r in m.group(2).split(",")]
        elif m := R6["ratios"].match(line):
            policy.update(up4_10d=int(m.group(1)), down4_10d=int(m.group(2)), ratio_10d=_num(m.group(3)),
                          up4_5d=int(m.group(4)), down4_5d=int(m.group(5)), ratio_5d=_num(m.group(6)))
        elif m := R6["day"].match(line):
            policy.update(up4=int(m.group(1)), down4=int(m.group(2)), counted_universe=int(m.group(3)))
        elif m := R6["own"].match(line):
            policy["production_verdict"] = m.group(1).lower()
        elif m := R6["established"].match(line):
            policy["regime_established"] = m.group(1) == "True"
        elif m := R6["unknown_events"].match(line):
            policy["unknown_event_counts"] = _literal(m.group(2))
        elif m := R6["unknown_4pct"].match(line):
            policy["unknown_4pct_names"] = _names(m.group(2))
            if len(policy["unknown_4pct_names"]) != int(m.group(1)):
                raise FindingsError("run-6 summary: the unknown-4% count and its names disagree")
        elif m := R6["unknown_up50"].match(line):
            policy["unknown_up50_names"] = _names(m.group(3))
            if len(policy["unknown_up50_names"]) != int(m.group(2)):
                raise FindingsError("run-6 summary: the unknown-up-50% count and its names disagree")
        elif m := R6["bounds"].match(line):
            policy["ratio_10d_bounds"] = [_num(m.group(1)), _num(m.group(2))]
            policy["unknown_contributors"] = int(m.group(3))
        elif m := R6["population"].match(line):
            policy["population"] = _literal(m.group(2))
        elif m := R6["matches"].match(line):
            session["diagnostic_scan_matches"] = int(m.group(1))
        else:
            raise FindingsError(f"run-6 summary: a line the grammar does not know: {line!r}")
    if not out["sessions"] or "download" not in out:
        raise FindingsError("run-6 summary: no session block")
    names = set()
    for s in out["sessions"].values():
        for pol in s["policies"].values():
            names.update(pol.get("unknown_up50_names", []))
    out["blocking_names"] = sorted(names)
    return out


def study_run_record(path: Path) -> dict:
    """The commit and the tool blob the study was run from, off its run record."""
    text = (ROOT / path).read_text(encoding="utf-8")
    m = re.search(r"^code: ([0-9a-f]{40}) \(tools/signal_outcomes\.py blob ([0-9a-f]{40})\)$", text, re.M)
    if not m:
        raise FindingsError("run-record.txt: no code line")
    return {"commit": m.group(1), "code_blob": m.group(2)}


def run6_public(path: Path) -> dict:
    p = json.loads((ROOT / path).read_text())
    if p.get("schema") != "historical-run6-public-record-v1":
        raise FindingsError("public-run.json: not the run-6 public record")
    return {"run_id": p["run"]["id"], "run_number": p["run"]["run_number"], "run_attempt": p["run"]["run_attempt"],
            "workflow_sha": p["run"]["head_sha"], "execution_checkout_sha": p["execution_checkout_sha"]["value"],
            "dispatched_at": p["run"]["created_at"], "dispatched_by": p["run"]["triggering_actor"],
            "job_id": p["job"]["id"],
            "artifact": {"id": p["artifact"]["id"], "size_in_bytes": p["artifact"]["size_in_bytes"],
                         "digest": p["artifact"]["digest"], "expires_at": p["artifact"]["expires_at"]}}


# ----------------------------------------------------------------- build ----


def build() -> dict:
    study, study_sha = load_study(STUDY)
    first, first_sha = load_study(FIRST_STUDY)
    for name, s in (("study", study), ("first study", first)):
        if s.get("version") != "signal-outcomes-v1":
            raise FindingsError(f"{name}: not a signal-outcomes-v1 file")
    spec = so.load_spec(ROOT / STUDY_SPEC)
    if spec["_sha256"] != study["spec_sha256"]:
        raise FindingsError("the study was not run under the committed extended spec")
    first_spec = so.load_spec(ROOT / FIRST_SPEC)
    if first_spec["_sha256"] != first["spec_sha256"]:
        raise FindingsError("the first study was not run under the committed frozen spec")
    pubs = so.load_publications(spec)
    nights = nights_of(pubs, study, first)
    market = market_series(pubs, {n["session"]: n for n in nights})
    backtests = {}
    for name, path in BACKTESTS.items():
        text = (ROOT / path).read_text(encoding="utf-8")
        backtests[name] = {"source": source(path, kind="owner_pasted"), **parse_backtest_summary(text)}
    run6 = {"source": source(RUN6_SUMMARY, kind="owner_pasted"),
            "public": {"source": source(RUN6_PUBLIC, kind="public_receipt"), **run6_public(RUN6_PUBLIC)},
            **parse_run6_summary((ROOT / RUN6_SUMMARY).read_text(encoding="utf-8"))}
    originals = {n["session"]: n for n in nights}
    for day, s in run6["sessions"].items():
        if day not in originals:
            raise FindingsError(f"run 6 measured {day}, a session no publication carries")
        o = originals[day]["regime"]
        s["original"] = {"ratio_10d": o["ratio_10d"], "up4_10d": o["up4_10d"], "down4_10d": o["down4_10d"],
                         "verdict": o["verdict"], "universe": o["universe"], "source": originals[day]["commit"][:8]}
    return {
        "version": VERSION,
        "sources": {
            "study": source(STUDY, kind="tool_output", uncompressed_sha256=study_sha, spec=source(STUDY_SPEC),
                            run=source(STUDY_RUN_RECORD, **study_run_record(STUDY_RUN_RECORD))),
            "first_study": source(FIRST_STUDY, kind="tool_output", uncompressed_sha256=first_sha,
                                  spec=source(FIRST_SPEC)),
        },
        "study": {"frozen_through_session": study["frozen_through_session"], "newest_session": study["newest_session"],
                  "first_read_newest_session": first["newest_session"],
                  "publications": len(study["publications"]),
                  "first_of_session": sum(1 for p in study["publications"] if p["first"]),
                  "bars": study["bars"]["observations"], "symbols": study["bars"]["symbols"],
                  "revisions": study["bars"]["revisions"], "rows": len(study["rows"]),
                  "account": pubs[0]["data"]["account"] and {k: pubs[0]["data"]["account"][k] for k in
                                                              ("equity", "risk_pct", "max_position_pct",
                                                               "max_open_positions")},
                  "ticket_multiplier": so.UNGATED["size_multiplier"],
                  "cost_bps_per_side": spec["cost_bps_per_side"],
                  "summary": strata_summary(study),
                  "first_read_summary": strata_summary(first)},
        "rules": rules_of(pubs),
        "market": market,
        "nights": nights,
        # what the gate said over every published night, counted here once so the
        # page can say it without counting: a yellow night will change this line
        "nights_summary": {"nights": len(nights), "from": nights[0]["session"], "through": nights[-1]["session"],
                           "verdicts": dict(Counter(n["regime"]["verdict"] for n in nights)),
                           "tickets_published": sum(n["tickets_published"] for n in nights),
                           "bursts": sum(n["bursts"] for n in nights)},
        "backtest": backtests,
        "run6": run6,
        "reports": [{"title": t, "path": str(p)} for t, p in REPORTS],
        "read_as": backtests["lookback_130"]["limitations"],
    }


def render(findings: dict) -> str:
    return json.dumps(findings, indent=1, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"


def credential_like_fields(obj, path="") -> list[str]:
    """Every field name gitleaks would read as a credential's, with its path."""
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if CREDENTIAL_WORDS.search(str(k)):
                found.append(f"{path}.{k}" if path else str(k))
            found += credential_like_fields(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found += credential_like_fields(v, f"{path}[{i}]")
    return found


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="compare rather than write; exit 1 on a difference")
    parser.add_argument("--output", type=Path, default=OUTPUT, help=f"where to write (default {OUTPUT})")
    args = parser.parse_args(argv)
    try:
        findings = build()
    except (FindingsError, so.StudyError, OSError, KeyError, ValueError) as exc:
        print(f"historical findings: {exc}")
        return 2
    bad = credential_like_fields(findings)
    if bad:
        print("historical findings: a field name the secret scan reads as a credential: " + ", ".join(bad))
        return 2
    text = render(findings)
    if args.check:
        current = args.output.read_text(encoding="utf-8") if args.output.exists() else None
        if current != text:
            print(f"stale: {args.output} differs from what the evidence builds -- run python tools/build_historical_findings.py")
            return 1
        print(f"{args.output} current: {len(findings['nights'])} nights, {len(findings['market']['sessions'])} sessions")
        return 0
    args.output.write_text(text, encoding="utf-8")
    print(f"wrote {args.output}: {len(findings['nights'])} nights, {len(findings['market']['sessions'])} sessions, {len(text):,} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
