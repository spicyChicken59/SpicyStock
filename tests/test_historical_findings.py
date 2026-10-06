"""tools.build_historical_findings: docs/historical-findings.json is what the
builder writes, and every number in it is the evidence's own. The per-night
blocks are re-derived here from the study's rows without the builder's
helpers; the market, the counts and the rules are read off the publication
records through the study's spec; the headline strata are held equal to the
study file's; the two pasted backtest summaries and the owner's run-6
summary are re-read under the tools' own line grammars and by independent
regexes; and the builder's refusals are driven, each with the evidence that
does not reconcile. Nothing here writes inside the checkout: ``--check``
compares, and the copies it is pointed at live in tmp_path."""
from __future__ import annotations

from collections import Counter, defaultdict
import copy
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import statistics

import pytest

from src import breadth
from tools import build_historical_findings as bf
from tools import historical_backtest as backtest
from tools import signal_outcomes as so

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = "docs/historical-findings.json"
TRUTH = "docs/input-truthfulness"
STUDY = f"{TRUTH}/2026-10-06-signal-outcomes-confirmatory-evidence/signal-outcomes.json.gz"
STUDY_SPEC = f"{TRUTH}/2026-10-06-signal-outcomes-spec-extended.json"
STUDY_RUN_RECORD = f"{TRUTH}/2026-10-06-signal-outcomes-confirmatory-evidence/run-record.txt"
FIRST_STUDY = f"{TRUTH}/2026-10-02-signal-outcomes-evidence/signal-outcomes.json.gz"
FIRST_SPEC = f"{TRUTH}/2026-10-02-signal-outcomes-spec.json"
BACKTESTS = {"lookback_130": f"{TRUTH}/2026-10-06-backtest-results-evidence/lookback-130-summary.txt",
             "lookback_260": f"{TRUTH}/2026-10-06-backtest-results-evidence/lookback-260-summary.txt"}
RUN6_SUMMARY = f"{TRUTH}/2026-10-02-historical-run6-evidence/owner-summary.txt"
RUN6_PUBLIC = f"{TRUTH}/2026-10-02-historical-run6-evidence/public-run.json"
#: the frozen spec's digest and the first study's uncompressed digest, as the
#: 2 October checkpoint names them: a freeze is a number, not a file name
FROZEN_SPEC_SHA = "d93ad856b69ad48aa7a32708ed7f0501b86baf955057080e86d8c874469a2770"
FIRST_STUDY_UNCOMPRESSED_SHA = "cc67f25ef2f9963426e807e2085b12323fa2fbea3d0183dc909fbac3983a4341"
STRATA = ("admitted", "B", "C", "skip", "vetoed")
BUCKETS = ("settled", "open", "pending", "uncertain", "not_filled", "unmeasured",
           "no_ticket", "basis_mismatch", "plan_error", "unreadable", "unscored")
GRADES = ("A+", "A", "B", "C", "skip")
REGIME_FIELDS = ("ratio_10d", "ratio_5d", "up4", "down4", "up4_10d", "down4_10d", "universe")
#: the rule numbers the page's captions name, read off every record's archived rules
RULE_FIELDS = {"record": ("open_plan_sessions", "scorecard_min_plans"),
               "pipeline": ("trade_grades", "yellow_grades", "max_reads"),
               "breadth": ("size_multiplier", "red_ratio_10d", "yellow_ratio_10d", "burst_pct",
                           "ratio_long_sessions", "ratio_short_sessions")}
CREDENTIAL = re.compile(r"(api|key|token|secret|auth|access|credential|passw)", re.I)
BLOCKING_NAMES = ["ETRA", "GIXI", "OIG", "TEVA", "TRBG", "WCCB"]


def sha256(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def load_gz(path: str) -> tuple[dict, str]:
    raw = gzip.decompress((ROOT / path).read_bytes())
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def settled_of(rs: list[float]) -> dict:
    """The builder's one piece of arithmetic, written again: counts, one
    rounding of the sum and the mean, the median at two places."""
    if not rs:
        return {"n": 0, "wins": 0, "losses": 0, "breakeven": 0, "sum_r": None, "mean_r": None, "median_r": None}
    return {"n": len(rs), "wins": sum(1 for r in rs if r > 0), "losses": sum(1 for r in rs if r < 0),
            "breakeven": sum(1 for r in rs if r == 0), "sum_r": round(math.fsum(rs), 2),
            "mean_r": round(math.fsum(rs) / len(rs), 3), "median_r": round(statistics.median(rs), 2)}


def check_stratum(block: dict, rows: list[dict], where: str) -> None:
    counts = Counter(r["bucket"] for r in rows)
    assert set(counts) <= set(BUCKETS), (where, sorted(counts))
    assert set(block) == {"rows", "buckets", "settled", "r"}, (where, sorted(block))
    assert block["rows"] == len(rows), (where, block["rows"], len(rows))
    assert block["buckets"] == {b: counts.get(b, 0) for b in BUCKETS}, (where, block["buckets"], dict(counts))
    assert sum(block["buckets"].values()) == block["rows"], (where, block["buckets"])
    rs = sorted(r["r"] for r in rows if r["bucket"] == "settled")
    assert block["r"] == rs, (where, block["r"], rs)
    assert block["settled"] == settled_of(rs), (where, block["settled"], settled_of(rs))


def by_session(doc: dict) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in doc["rows"]:
        grouped[row["session"]].append(row)
    return grouped


# ------------------------------------------------------------ fixtures ----
@pytest.fixture(scope="module")
def committed() -> dict:
    return json.loads((ROOT / OUTPUT).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def study() -> tuple[dict, str]:
    return load_gz(STUDY)


@pytest.fixture(scope="module")
def first() -> tuple[dict, str]:
    return load_gz(FIRST_STUDY)


@pytest.fixture(scope="module")
def pubs() -> list[dict]:
    return so.load_publications(so.load_spec(ROOT / STUDY_SPEC))


@pytest.fixture(scope="module")
def built() -> dict:
    return bf.build()


# ------------------------------------------------------------ the file ----
def test_the_findings_file_is_what_the_builder_writes(built, tmp_path, capsys, monkeypatch):
    assert bf.OUTPUT == ROOT / OUTPUT
    text = (ROOT / OUTPUT).read_text(encoding="utf-8")
    rendered = bf.render(built)
    assert rendered == text, "docs/historical-findings.json is not what build() renders: run python tools/build_historical_findings.py"
    assert rendered == json.dumps(built, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    assert built["version"] == "historical-findings-v1" == json.loads(text)["version"]
    # the check mode, for real: build, compare, exit 0
    assert bf.main(["--check"]) == 0
    out = capsys.readouterr().out
    assert "current" in out and f"{len(built['nights'])} nights" in out, out
    # the comparison is byte-for-byte: the build is the one above, cached, and
    # only the comparison is under test from here
    monkeypatch.setattr(bf, "build", lambda: built)
    same = tmp_path / "same.json"
    same.write_text(text, encoding="utf-8")
    assert bf.main(["--check", "--output", str(same)]) == 0
    i = text.index("historical-findings-v1") + len("historical-findings-v")
    altered = text[:i] + "2" + text[i + 1:]
    assert len(altered) == len(text) and sum(a != b for a, b in zip(altered, text)) == 1
    copy_path = tmp_path / "altered.json"
    copy_path.write_text(altered, encoding="utf-8")
    assert bf.main(["--check", "--output", str(copy_path)]) == 1
    assert "stale" in capsys.readouterr().out
    assert copy_path.read_text(encoding="utf-8") == altered, "--check wrote"
    missing = tmp_path / "missing.json"
    assert bf.main(["--check", "--output", str(missing)]) == 1
    assert not missing.exists(), "--check wrote"


# ----------------------------------------------------------- the nights ----
def test_every_night_is_rederived_from_the_studys_own_rows(committed, study, first):
    study_doc, _ = study
    first_doc, _ = first
    assert set(bf.BUCKETS) == set(so.BUCKETS) == set(BUCKETS), (bf.BUCKETS, so.BUCKETS)
    assert tuple(bf.STRATA) == tuple(so.STRATA) == STRATA
    rows_now, rows_first = by_session(study_doc), by_session(first_doc)
    nights = committed["nights"]
    assert [n["session"] for n in nights] == sorted(rows_now), [n["session"] for n in nights]
    assert len(nights) == 17
    empty_strata = 0
    for night in nights:
        rows = rows_now[night["session"]]
        where = night["session"]
        assert {r["stratum"] for r in rows} <= set(STRATA), (where, {r["stratum"] for r in rows})
        assert set(night["strata"]) == set(STRATA), (where, sorted(night["strata"]))
        for name in STRATA:
            subset = [r for r in rows if r["stratum"] == name]
            check_stratum(night["strata"][name], subset, f"{where} {name}")
            empty_strata += night["strata"][name]["settled"]["n"] == 0
        check_stratum(night["all"], rows, f"{where} all")
        assert sum(night["strata"][s]["rows"] for s in STRATA) == night["all"]["rows"] == len(rows), where
        phases = {r["phase"] for r in rows}
        assert len(phases) == 1 and night["phase"] == phases.pop(), (where, night["phase"], phases)
        horizons = {r.get("horizon") for r in rows} - {None}
        assert len(horizons) == 1, (where, horizons)
        horizon = horizons.pop()
        assert night["horizon"] == horizon, (where, night["horizon"], horizon)
        assert night["complete"] is (horizon <= study_doc["newest_session"]), (where, night["complete"], horizon)
        if night["session"] in rows_first:
            frows = rows_first[night["session"]]
            read = night["first_read"]
            assert set(read) == {"as_of", "admitted", "all"}, (where, sorted(read))
            assert read["as_of"] == first_doc["newest_session"] == "2026-10-01"
            admitted = sorted(r["r"] for r in frows if r["stratum"] == "admitted" and r["bucket"] == "settled")
            everything = sorted(r["r"] for r in frows if r["bucket"] == "settled")
            assert read["admitted"] == settled_of(admitted), (where, read["admitted"], settled_of(admitted))
            assert read["all"] == settled_of(everything), (where, read["all"], settled_of(everything))
        else:
            assert "first_read" not in night, where
    assert {n["session"] for n in nights if "first_read" not in n} == {"2026-10-02", "2026-10-05"}
    assert empty_strata, "no empty stratum: the None branch of the settled block was never read"
    assert {n["phase"] for n in nights} == {"exploratory", "confirmatory"}
    assert [n["session"] for n in nights if not n["complete"]] == ["2026-09-29", "2026-09-30", "2026-10-01",
                                                                   "2026-10-02", "2026-10-05"]
    # a night read again after its sessions completed moved: the first read
    # is kept beside the re-read and is not a copy of it
    moved = [n["session"] for n in nights if "first_read" in n
             and n["first_read"]["admitted"] != n["strata"]["admitted"]["settled"]]
    assert moved, "no night's admitted block moved between the two reads"


# ----------------------------------------------------------- the market ----
def test_the_market_and_the_counts_are_the_records_own(committed, pubs, study):
    study_doc, _ = study
    ordered = sorted(pubs, key=lambda p: (p["session"], p["data"]["run"].get("published_at") or ""))
    firsts: dict[str, dict] = {}
    for p in ordered:
        firsts.setdefault(p["session"], p)
    assert {p["commit"] for p in firsts.values()} == {p["commit"] for p in study_doc["publications"] if p["first"]}
    nights = {n["session"]: n for n in committed["nights"]}
    assert set(nights) == set(firsts), (sorted(nights), sorted(firsts))
    for session, p in firsts.items():
        n, d = nights[session], p["data"]
        b, reg = d["breadth"], d["breadth"]["regime"]
        assert (n["commit"], n["blob"]) == (p["commit"], p["blob"]), session
        assert (n["published_at"], n["status"]) == (d["run"]["published_at"], d["run"]["status"]), session
        assert set(n["regime"]) == set(REGIME_FIELDS) | {"verdict", "size_multiplier", "reasons"}, sorted(n["regime"])
        for k in REGIME_FIELDS:
            assert n["regime"][k] == b[k], (session, k, n["regime"][k], b[k])
        for k in ("verdict", "size_multiplier", "reasons"):
            assert n["regime"][k] == reg[k], (session, k, n["regime"][k], reg[k])
        assert n["bursts"] == len(d["bursts"]), (session, n["bursts"], len(d["bursts"]))
        mechanical = Counter(x["grade_mechanical"] for x in d["bursts"])
        final = Counter(x["grade"] for x in d["bursts"])
        assert set(mechanical) | set(final) <= set(GRADES), (session, sorted(mechanical), sorted(final))
        assert n["grades_mechanical"] == {g: mechanical.get(g, 0) for g in GRADES}, (session, n["grades_mechanical"], mechanical)
        assert n["grades_final"] == {g: final.get(g, 0) for g in GRADES}, (session, n["grades_final"], final)
        assert sum(n["grades_mechanical"].values()) == sum(n["grades_final"].values()) == n["bursts"], session
        vetoed = sum(1 for x in d["bursts"] if x.get("vetoes"))
        assert n["vetoed"] == vetoed, (session, n["vetoed"], vetoed)
        assert n["tickets_published"] == len(d.get("trades") or []), (session, n["tickets_published"])
        assert n["reads"] == d["run"]["reads"], (session, n["reads"], d["run"]["reads"])
    assert all(n["tickets_published"] == 0 and n["regime"]["verdict"] == "red" for n in nights.values()), \
        "a night with a ticket or not red: the checkpoint says every real night was RED with no ticket"
    # the one-line count over every published night is the records' own too
    records = [p["data"] for _, p in sorted(firsts.items())]
    assert committed["nights_summary"] == {
        "nights": len(records), "from": min(firsts), "through": max(firsts),
        "verdicts": dict(Counter(d["breadth"]["regime"]["verdict"] for d in records)),
        "tickets_published": sum(len(d.get("trades") or []) for d in records),
        "bursts": sum(len(d["bursts"]) for d in records)}, committed["nights_summary"]
    assert committed["nights_summary"]["verdicts"] == {"red": 17}
    # the rules the captions name are every record's own, and the same in every record
    assert {(m, k) for m, ks in RULE_FIELDS.items() for k in ks} == set(bf.RULE_FIELDS), sorted(bf.RULE_FIELDS)
    rules = committed["rules"]
    assert {m: set(ks) for m, ks in rules.items()} == {m: set(ks) for m, ks in RULE_FIELDS.items()}, rules
    for module, names in RULE_FIELDS.items():
        for name in names:
            for p in pubs:
                assert rules[module][name] == p["data"]["rules"][module][name], \
                    (module, name, rules[module][name], p["commit"][:8], p["data"]["rules"][module][name])
    assert rules["breadth"]["red_ratio_10d"] == breadth.RED_RATIO_10D == 1.0
    assert rules["breadth"]["yellow_ratio_10d"] == breadth.YELLOW_RATIO_10D == 2.0
    assert rules["breadth"]["size_multiplier"] == breadth.SIZE_MULTIPLIER
    # the market: thresholds, then one row per session the records know
    market = committed["market"]
    thresholds = {json.dumps({k: p["data"]["breadth"]["regime"]["thresholds"][k] for k in ("ratio_10d_red", "ratio_10d_yellow")},
                             sort_keys=True) for p in pubs}
    assert len(thresholds) == 1, thresholds
    assert market["thresholds"] == json.loads(thresholds.pop()) == {"ratio_10d_red": 1.0, "ratio_10d_yellow": 2.0}
    newest: dict[str, tuple[dict, dict]] = {}
    for p in ordered:                                   # the newest publication carrying a date wins
        for row in p["data"]["breadth"]["history"]:
            newest[row["date"]] = (p, row)
    dates = [s["date"] for s in market["sessions"]]
    assert dates == sorted(set(newest) | set(nights)), (dates[:3], dates[-3:], len(dates))
    assert (market["from"], market["through"]) == (dates[0], dates[-1]) == ("2026-07-31", "2026-10-05")
    assert set(nights) < set(dates)
    re_measured = []
    for row in market["sessions"]:
        day = row["date"]
        if day in nights:
            b = firsts[day]["data"]["breadth"]
            assert row["basis"] == "publication", row
            assert (row["up4"], row["down4"], row["ratio_10d"]) == (b["up4"], b["down4"], b["ratio_10d"]), row
            assert (row["source"], row["verdict"]) == (firsts[day]["commit"][:8], b["regime"]["verdict"]), row
            p, later = newest.get(day, (None, None))
            if later and later["ratio_10d"] != b["ratio_10d"]:
                assert (row["later_ratio_10d"], row["later_source"]) == (later["ratio_10d"], p["commit"][:8]), row
                re_measured.append(day)
                assert set(row) == {"date", "up4", "down4", "ratio_10d", "source", "basis", "verdict",
                                    "later_ratio_10d", "later_source"}, sorted(row)
            else:
                assert set(row) == {"date", "up4", "down4", "ratio_10d", "source", "basis", "verdict"}, sorted(row)
        else:
            p, later = newest[day]
            assert row == {"date": day, "up4": later["up4"], "down4": later["down4"], "ratio_10d": later["ratio_10d"],
                           "source": p["commit"][:8], "basis": "history", "verdict": None}, (row, later, p["commit"][:8])
    assert re_measured, "no publication night was re-measured by a later history: the later_ratio_10d branch was never read"


# ------------------------------------------------------- the headlines ----
def test_the_study_headline_blocks_are_copied_not_recomputed(committed, study, first):
    study_doc, study_sha = study
    first_doc, first_sha = first
    s = committed["study"]
    for which, doc, summary in (("summary", study_doc, s["summary"]),
                                ("first_read_summary", first_doc, s["first_read_summary"])):
        own = doc["summary"]
        assert set(summary["phases"]) == set(own["phases"]) == {"exploratory", "confirmatory"}, which
        assert set(summary["strata"]) == set(own["strata"]) == set(STRATA), which
        blocks = [("all", summary["all"], own["all"]), ("reader_accepted", summary["reader_accepted"], own["reader_accepted"])]
        blocks += [(f"strata.{k}", summary["strata"][k], own["strata"][k]) for k in STRATA]
        blocks += [(f"phases.{k}", summary["phases"][k], own["phases"][k]) for k in ("exploratory", "confirmatory")]
        for name, got, expected in blocks:
            if expected["rows"] == 0:
                assert got == {"rows": 0}, (which, name, got)
                continue
            for k in ("rows", "buckets", "settled", "night_bootstrap", "uncertain_bound", "costs_per_side_bps"):
                assert got[k] == expected[k], (which, name, k, got[k], expected[k])
            scorecard = {k: expected["scorecard"].get(k) for k in ("readable", "min_read", "win_rate", "avg_r",
                                                                   "median_r", "plans", "filled")}
            assert got["scorecard"] == scorecard, (which, name, got["scorecard"], scorecard)
            assert set(got) == {"rows", "buckets", "settled", "night_bootstrap", "uncertain_bound",
                                "costs_per_side_bps", "scorecard"}, (which, name, sorted(got))
    assert s["first_read_summary"]["phases"]["confirmatory"] == {"rows": 0}
    assert s["summary"]["phases"]["confirmatory"]["rows"] > 0
    # the numbers the 6 October checkpoint quotes for the exploratory admitted read
    exploratory = s["summary"]["phases"]["exploratory"]["settled"]
    assert (exploratory["n"], exploratory["mean_r"]) == (267, -0.189), exploratory
    assert (s["newest_session"], s["frozen_through_session"]) == \
        (study_doc["newest_session"], study_doc["frozen_through_session"]) == ("2026-10-05", "2026-10-01")
    assert s["first_read_newest_session"] == first_doc["newest_session"] == "2026-10-01"
    assert s["rows"] == len(study_doc["rows"]), (s["rows"], len(study_doc["rows"]))
    assert (s["bars"], s["symbols"], s["revisions"]) == \
        (study_doc["bars"]["observations"], study_doc["bars"]["symbols"], study_doc["bars"]["revisions"])
    assert s["publications"] == len(study_doc["publications"]) == 19
    assert s["first_of_session"] == sum(1 for p in study_doc["publications"] if p["first"]) == 17
    assert s["ticket_multiplier"] == breadth.SIZE_MULTIPLIER["green"] == 1.0
    spec = json.loads((ROOT / STUDY_SPEC).read_bytes())
    assert s["cost_bps_per_side"] == spec["cost_bps_per_side"] == [0, 5, 20]
    assert set(s["account"]) == {"equity", "risk_pct", "max_position_pct", "max_open_positions"}
    # the sources: the file, the bytes inside it, the spec it was run under
    sources = committed["sources"]
    assert set(sources) == {"study", "first_study"}
    for name, path, spec_path, doc, raw_sha in (("study", STUDY, STUDY_SPEC, study_doc, study_sha),
                                                ("first_study", FIRST_STUDY, FIRST_SPEC, first_doc, first_sha)):
        block = sources[name]
        assert (block["path"], block["kind"]) == (path, "tool_output"), block
        assert block["sha256"] == sha256(path), (name, block["sha256"], sha256(path))
        assert block["uncompressed_sha256"] == raw_sha, (name, block["uncompressed_sha256"], raw_sha)
        assert block["spec"] == {"path": spec_path, "sha256": sha256(spec_path)}, (name, block["spec"])
        assert block["spec"]["sha256"] == doc["spec_sha256"], (name, block["spec"]["sha256"], doc["spec_sha256"])
    assert sources["first_study"]["spec"]["sha256"] == FROZEN_SPEC_SHA
    assert sources["first_study"]["uncompressed_sha256"] == FIRST_STUDY_UNCOMPRESSED_SHA
    assert sources["study"]["spec"]["sha256"] != FROZEN_SPEC_SHA, "the extended spec is the frozen one"
    run = sources["study"]["run"]
    assert run["path"] == STUDY_RUN_RECORD and run["sha256"] == sha256(STUDY_RUN_RECORD)
    found = re.search(r"^code: ([0-9a-f]{40}) \(tools/signal_outcomes\.py blob ([0-9a-f]{40})\)$",
                      (ROOT / STUDY_RUN_RECORD).read_text(encoding="utf-8"), re.M)
    assert (run["commit"], run["code_blob"]) == found.groups(), (run, found.groups())


# --------------------------------------------------------- the backtest ----
def backtest_result() -> dict:
    """A result in the shape ``summary_text`` prints: two gates that differ
    in every count, a None avg R, two by-grade rows, one int among floats."""
    def gate(plans, settled, open_, pending, uncertain, reasons, not_filled, wins, losses, breakeven,
             sum_r, avg_r, median_r, win_rate, readable, pairs, spy, picks, by_grade, by_regime):
        return {"summary": {"plans": plans, "settled": settled, "open": open_, "pending": pending,
                            "uncertain": uncertain, "uncertain_reasons": [{"kind": k, "count": n} for k, n in reasons],
                            "not_filled": not_filled, "unmeasured": 0, "unreadable": 0, "unscored": 0,
                            "wins": wins, "losses": losses, "breakeven": breakeven, "sum_r": sum_r, "avg_r": avg_r,
                            "median_r": median_r, "win_rate": win_rate, "min_read": 20, "readable": readable,
                            "benchmark_pairs": pairs, "spy_avg_pct": spy},
                "picks": picks, "by_grade": by_grade, "by_regime": by_regime}
    row = lambda plans, settled, wins, losses, sum_r: {"plans": plans, "settled": settled, "wins": wins,  # noqa: E731
                                                       "losses": losses, "sum_r": sum_r}
    return {
        "version": "historical-backtest-v1",
        "archive": {"symbols": 5, "intended": 4, "sessions": {"from": "2025-08-05", "through": "2026-09-25", "count": 288},
                    "statuses": {"returned_with_bars": 3, "partial": 2}},
        "evaluated": {"count": 2, "from": "2026-09-24", "through": "2026-09-25", "seconds": 12.5},
        "lookback": {"sessions": 130, "production": 260,
                     "equivalence": {"status": "PASS", "compared": 2, "differences": ["2026-09-25"]}},
        "rules_version": "17da26751760",
        "account": {"equity": 10000.0, "risk_pct": 0.5, "max_position_pct": 25.0, "max_open_positions": 4},
        "reader": "NOT RUN: the mechanical grade is the ceiling of what the reader could have admitted",
        "regimes": {"verdicts": {"yellow": 1, "red": 1},
                    "ratio_10d": {"min": None, "median": 1.06, "max": 1.56, "defined": 1}},
        "nights": {"production": [{"bursts": 10, "grades": {"A+": 1, "A": 2, "B": 3, "C": 1, "skip": 3}, "trades": [1, 2]},
                                  {"bursts": 4, "grades": {"A+": 1, "B": 1, "skip": 2}, "trades": [3]}],
                   "no_regime_gate": [{"bursts": 10, "grades": {"A+": 1, "A": 2, "B": 3, "C": 1, "skip": 3}, "trades": [1, 2, 3]},
                                      {"bursts": 4, "grades": {"A+": 1, "B": 1, "skip": 2}, "trades": [4, 5]}]},
        "outcomes": {
            "production": gate(7, 3, 1, 1, 2, [("trigger_timing", 1), ("stop_sequence", 1)], 0, 2, 1, 0,
                               1.25, None, 0.4, None, False, 3, -0.12,
                               [{"regime": "yellow"}] * 3,
                               {"A+": row(5, 2, 1, 1, 0.75), "A": row(2, 1, 1, 0, 0.5)},
                               {"yellow": row(7, 3, 2, 1, 1.25)}),
            "no_regime_gate": gate(12, 5, 0, 2, 3, [("open_above_limit", 3)], 2, 3, 1, 1,
                                   -0.5, -0.1, 0.0, 0.6, True, 5, 0.31,
                                   [{"regime": "yellow"}] * 3 + [{"regime": "red"}] * 2,
                                   {"A+": row(8, 3, 2, 1, 2), "A": row(4, 2, 1, 0, -2.5)},
                                   {"yellow": row(7, 3, 2, 1, 1.25), "red": row(5, 2, 1, 0, -1.75)}),
        },
        "limitations": ["The reader is not run.", "Counts are not an edge claim."],
    }


def test_the_backtest_block_is_the_pasted_summary_under_the_tools_own_grammar(committed):
    # (a) the two pasted files, parsed again, are the JSON's blocks
    assert set(committed["backtest"]) == set(BACKTESTS) == set(bf.BACKTESTS)
    for name, path in BACKTESTS.items():
        text = (ROOT / path).read_text(encoding="utf-8")
        block = dict(committed["backtest"][name])
        source = block.pop("source")
        assert source == {"path": path, "sha256": sha256(path), "kind": "owner_pasted"}, (name, source)
        parsed = bf.parse_backtest_summary(text)
        assert parsed == block, (name, {k: (parsed.get(k), block.get(k)) for k in set(parsed) | set(block)
                                        if parsed.get(k) != block.get(k)})
    p130, p260 = committed["backtest"]["lookback_130"], committed["backtest"]["lookback_260"]
    assert p130["gates"]["production"]["settled"] == {
        "n": 44, "wins": 16, "losses": 27, "breakeven": 1, "sum_r": 3.72, "avg_r": 0.08, "median_r": -0.09,
        "win_rate": 0.36, "min_read": 20, "readable": True, "spy_pairs": 44, "spy_avg_pct": 0.37}, p130["gates"]["production"]
    assert (p130["regimes"]["verdicts"], p130["evaluated"]["count"]) == ({"red": 58, "yellow": 100}, 158)
    assert p130["lookback"] == {"sessions": 130, "production": 260,
                                "equivalence": {"status": "PASS", "compared": 28, "differences": 0}}
    assert p130["gates"]["no_regime_gate"]["by_regime"]["red"] == {"plans": 58, "settled": 25, "wins": 7, "losses": 18, "sum_r": 1.14}
    assert (p130["progress"], "helper_line" in p130) == ([], False)
    assert p260["gates"]["production"]["settled"]["sum_r"] == 1.94
    for k in ("avg_r", "median_r", "win_rate", "spy_avg_pct"):
        assert p260["gates"]["production"]["settled"][k] is None, (k, p260["gates"]["production"]["settled"][k])
    assert p260["gates"]["production"]["settled"]["readable"] is False
    assert [p["session"] for p in p260["progress"]] == ["2026-09-18", "2026-09-21", "2026-09-22", "2026-09-23",
                                                        "2026-09-24", "2026-09-25"]
    assert p260["progress"][4] == {"session": "2026-09-24", "verdict": "red", "ratio_10d": 0.93, "counted": 3739,
                                   "bursts": 418, "tickets": 0}
    assert p260["helper_line"].startswith("3/4 Exact-lookback replay saved to ")
    assert committed["read_as"] == p130["limitations"] == p260["limitations"] and len(p130["limitations"]) == 6
    # (b) the grammar is summary_text's own: what the tool prints, the parser reads back whole
    assert tuple(bf.GATE_NAMES.values()) == backtest.GATES == ("production", "no_regime_gate")
    result = backtest_result()
    text = backtest.summary_text(result)
    assert "avg R —" in text and "min/median/max —/1.06/1.56" in text
    parsed = bf.parse_backtest_summary(text)
    assert parsed["version"] == result["version"]
    assert parsed["archive"] == result["archive"], (parsed["archive"], result["archive"])
    assert parsed["evaluated"] == result["evaluated"], (parsed["evaluated"], result["evaluated"])
    assert parsed["lookback"] == {"sessions": 130, "production": 260,
                                  "equivalence": {"status": "PASS", "compared": 2, "differences": 1}}, parsed["lookback"]
    assert (parsed["rules_version"], parsed["account"], parsed["reader"]) == \
        (result["rules_version"], result["account"], result["reader"])
    assert parsed["regimes"] == result["regimes"], (parsed["regimes"], result["regimes"])
    assert parsed["regimes"]["ratio_10d"]["min"] is None
    production_nights = result["nights"]["production"]
    assert parsed["candidates"] == {"bursts": 14, "sessions": 2,
                                    "grades_mechanical": dict(sum((Counter(n["grades"]) for n in production_nights), Counter()))}
    assert set(parsed["gates"]) == set(backtest.GATES)
    for name in backtest.GATES:
        g, o, s = parsed["gates"][name], result["outcomes"][name], result["outcomes"][name]["summary"]
        assert g["tickets"] == sum(len(n["trades"]) for n in result["nights"][name]), (name, g["tickets"])
        assert g["tickets_by_regime"] == dict(Counter(p["regime"] for p in o["picks"])), (name, g["tickets_by_regime"])
        assert g["plans"] == {k: s[k] for k in ("plans", "settled", "open", "pending", "uncertain", "uncertain_reasons",
                                                "not_filled", "unmeasured", "unreadable", "unscored")}, (name, g["plans"])
        assert g["settled"] == {"n": s["settled"], "wins": s["wins"], "losses": s["losses"], "breakeven": s["breakeven"],
                                "sum_r": s["sum_r"], "avg_r": s["avg_r"], "median_r": s["median_r"],
                                "win_rate": s["win_rate"], "min_read": s["min_read"], "readable": s["readable"],
                                "spy_pairs": s["benchmark_pairs"], "spy_avg_pct": s["spy_avg_pct"]}, (name, g["settled"])
        assert g["by_grade"] == o["by_grade"], (name, g["by_grade"], o["by_grade"])
        assert g["by_regime"] == o["by_regime"], (name, g["by_regime"], o["by_regime"])
    assert (parsed["gates"]["production"]["tickets"], parsed["gates"]["no_regime_gate"]["tickets"]) == (3, 5)
    assert parsed["gates"]["production"]["settled"]["avg_r"] is None
    assert parsed["gates"]["production"]["settled"]["win_rate"] is None
    assert parsed["gates"]["no_regime_gate"]["settled"]["avg_r"] == -0.1
    assert parsed["gates"]["no_regime_gate"]["by_grade"]["A+"]["sum_r"] == 2
    assert parsed["limitations"] == result["limitations"] and parsed["progress"] == [] and "helper_line" not in parsed
    # the six progress lines a run prints before its summary, and the owner's helper line after it
    progress = "2026-09-24 red ratio 0.93 counted 3739 bursts 418 tickets 0\n"
    helper = "3/4 Exact-lookback replay saved to <private folder>\\lookback-260\\summary.txt\n"
    wrapped = bf.parse_backtest_summary(progress + text + helper)
    assert wrapped["progress"] == [{"session": "2026-09-24", "verdict": "red", "ratio_10d": 0.93, "counted": 3739,
                                    "bursts": 418, "tickets": 0}]
    assert wrapped["helper_line"] == helper.rstrip("\n")
    assert {k: v for k, v in wrapped.items() if k not in ("progress", "helper_line")} == \
        {k: v for k, v in parsed.items() if k != "progress"}
    # (c) the parser refuses: a line the grammar does not know, in any position
    assert "settled 3: wins 2" in text
    truncated = text.replace("\n[PRODUCTION POLICY]", "\nsettled 44: wins 16\n[PRODUCTION POLICY]", 1)
    with pytest.raises(bf.FindingsError, match="a line the grammar does not know: 'settled 44: wins 16'"):
        bf.parse_backtest_summary(truncated)
    with pytest.raises(bf.FindingsError, match="unexpected line after limitations"):
        bf.parse_backtest_summary(text + "settled 44: wins 16\n")
    with pytest.raises(bf.FindingsError, match="unexpected line after the helper"):
        bf.parse_backtest_summary(text + helper + "settled 44: wins 16\n")
    assert text.count("avg R ") == 2
    with pytest.raises(bf.FindingsError, match="a line the grammar does not know"):
        bf.parse_backtest_summary(text.replace("avg R ", "avg r ", 1))
    with pytest.raises(bf.FindingsError, match="no reader line"):
        bf.parse_backtest_summary("\n".join(l for l in text.splitlines() if not l.startswith("reader: ")) + "\n")
    with pytest.raises(bf.FindingsError, match=r"gates \['production'\]"):
        bf.parse_backtest_summary(text.split("\n[COUNTERFACTUAL")[0] + "\n\nlimitations:\n")
    with pytest.raises(bf.FindingsError, match="a gate without its tickets line"):
        bf.parse_backtest_summary("\n".join(l for l in text.splitlines() if not l.startswith("tickets ")) + "\n")
    # and '—' is never a number
    assert bf._num("—") is None and bf._num("3.72") == 3.72 and bf._num("-0.09") == -0.09 and bf._num("44") == 44
    assert isinstance(bf._num("44"), int)
    with pytest.raises(ValueError):
        bf._num("None")


# -------------------------------------------------------------- run 6 ----
def test_the_run6_block_is_the_owners_summary_and_the_public_receipt(committed):
    text = (ROOT / RUN6_SUMMARY).read_text(encoding="utf-8")
    run6 = committed["run6"]
    assert run6["source"] == {"path": RUN6_SUMMARY, "sha256": sha256(RUN6_SUMMARY), "kind": "owner_pasted"}, run6["source"]
    assert run6["status"] == re.search(r"^overall status (\S+)", text, re.M).group(1) == "BLOCKED"
    assert re.search(r"queries completed (\d+) of (\d+)", text).groups() == ("97", "97")
    assert run6["download"] == {"status": "PASS", "queries_completed": 97, "queries_total": 97}, run6["download"]
    assert run6["ledger"] == {"request_slots_charged": 289, "uncompressed_retained_bytes_charged": 275899601,
                              "unresolved_byte_reservations": 0}, run6["ledger"]
    sessions = re.findall(r"^=== (\d{4}-\d{2}-\d{2}) ===$", text, re.M)
    assert sessions == ["2026-09-24", "2026-09-25"] == sorted(run6["sessions"])
    blocks = re.split(r"^=== \d{4}-\d{2}-\d{2} ===$", text, flags=re.M)[1:]
    for day, block in zip(sessions, blocks):
        s = run6["sessions"][day]
        assert s["date"] == day and set(s["policies"]) == {"C", "D"}
        status = re.search(r"^\s+status (\S+)\s+formula check (\S+)\s+regime established (\S+)$", block, re.M).groups()
        assert status == ("BLOCKED", "PASS", "False") == (s["status"], s["formula_check"], str(s["regime_established"]))
        assert s["partial"] == int(re.search(r"^\s+partial \((\d+)\):", block, re.M).group(1)) == 263, (day, s["partial"])
        assert s["missing_sessions"] == int(re.search(r"missing some required sessions \((\d+)\)", block).group(1)) == 263
        assert len(s["partial_sample"]) == 25 and s["partial_sample"][:2] == ["AADX", "ACCL"], s["partial_sample"]
        assert s["stock_statuses"] == {"partial": 263, "returned_with_bars": 4517 + (day == "2026-09-25")}, (day, s["stock_statuses"])
        assert s["diagnostic_scan_matches"] == int(re.search(r"diagnostic scan matches \(no grading, no tickets\): (\d+)", block).group(1))
        ratios = re.findall(r"^\s+10-day up/down (\d+) / (\d+) -> ratio (\S+)\s+\|\s+5-day (\d+) / (\d+) -> (\S+)$", block, re.M)
        days = re.findall(r"^\s+that day up/down (\d+) / (\d+)\s+counted universe (\d+)$", block, re.M)
        bounds = re.findall(r"10-day ratio could be anywhere in \[(\S+), (\S+)\] given (\d+) unknown contributors", block)
        owns = re.findall(r"^\s+app's own code: (\S+)$", block, re.M)
        independent = re.findall(r"independent calculator: (\S+)\s+\(rules that fired: (.+)\)", block)
        blocking = re.findall(r"counted stocks with unknown up-50%-month on \d{4}-\d{2}-\d{2} \((\d+)\): (.+)$", block, re.M)
        assert len(ratios) == len(days) == len(bounds) == len(owns) == len(independent) == len(blocking) == 2, day
        for i, key in enumerate(("C", "D")):
            pol = s["policies"][key]
            up, down, ratio, up5, down5, ratio5 = ratios[i]
            assert (pol["up4_10d"], pol["down4_10d"], pol["ratio_10d"]) == (int(up), int(down), float(ratio)), (day, key, pol)
            assert (pol["up4_5d"], pol["down4_5d"], pol["ratio_5d"]) == (int(up5), int(down5), float(ratio5)), (day, key, pol)
            assert (pol["up4"], pol["down4"], pol["counted_universe"]) == tuple(int(x) for x in days[i]), (day, key, pol)
            assert (pol["ratio_10d_bounds"], pol["unknown_contributors"]) == \
                ([float(bounds[i][0]), float(bounds[i][1])], int(bounds[i][2])), (day, key, pol)
            assert (pol["production_verdict"], pol["independent_verdict"]) == (owns[i].lower(), independent[i][0].lower()) == ("red", "red")
            assert pol["rules_fired"] == independent[i][1].split(", ") == ["red_ratio_10d", "yellow_ratio_10d", "yellow_up50_month_hot"]
            assert (blocking[i][0], blocking[i][1].split(", ")) == ("6", BLOCKING_NAMES) and pol["unknown_up50_names"] == BLOCKING_NAMES
            assert pol["regime_established"] is False and pol["check"] == "PASS"
        assert s["policies"]["D"]["unknown_4pct_names"] == [] and s["policies"]["D"]["unknown_contributors"] == 0
        assert s["policies"]["C"]["unknown_4pct_names"] == ["ETRA", "OIG", "TEVA", "WCCB"]
    assert [run6["sessions"][d]["policies"]["C"]["ratio_10d"] for d in sessions] == [0.93, 0.89]
    assert [run6["sessions"][d]["policies"]["C"]["ratio_10d_bounds"] for d in sessions] == [[0.92, 0.95], [0.88, 0.9]]
    assert [run6["sessions"][d]["policies"]["C"]["counted_universe"] for d in sessions] == [3738, 3729]
    assert run6["blocking_names"] == BLOCKING_NAMES
    # the original: the night's own regime block, from the publication the gate read
    nights = {n["session"]: n for n in committed["nights"]}
    for day, s in run6["sessions"].items():
        reg = nights[day]["regime"]
        assert s["original"] == {"ratio_10d": reg["ratio_10d"], "up4_10d": reg["up4_10d"], "down4_10d": reg["down4_10d"],
                                 "verdict": reg["verdict"], "universe": reg["universe"],
                                 "source": nights[day]["commit"][:8]}, (day, s["original"], reg)
    assert [run6["sessions"][d]["original"]["ratio_10d"] for d in sessions] == [0.94, 0.89]
    assert [run6["sessions"][d]["original"]["universe"] for d in sessions] == [3716, 3700]
    # the public receipt
    receipt = json.loads((ROOT / RUN6_PUBLIC).read_text(encoding="utf-8"))
    public = run6["public"]
    assert public["source"] == {"path": RUN6_PUBLIC, "sha256": sha256(RUN6_PUBLIC), "kind": "public_receipt"}
    assert public["run_id"] == receipt["run"]["id"] == 36815689950
    assert public["job_id"] == receipt["job"]["id"] == 110220126196
    assert (public["run_number"], public["run_attempt"]) == (receipt["run"]["run_number"], receipt["run"]["run_attempt"]) == (6, 1)
    assert public["artifact"] == {k: receipt["artifact"][k] for k in ("id", "size_in_bytes", "digest", "expires_at")}
    assert public["artifact"]["id"] == 11142297138 and public["artifact"]["digest"].startswith("sha256:043af0b3")
    assert public["workflow_sha"] == receipt["run"]["head_sha"] and public["workflow_sha"].startswith("a900236")
    assert public["execution_checkout_sha"] == receipt["execution_checkout_sha"]["value"] and public["execution_checkout_sha"].startswith("d6d7743")
    assert (public["dispatched_at"], public["dispatched_by"]) == (receipt["run"]["created_at"], receipt["run"]["triggering_actor"])
    # the parser refuses a line it does not know, a count that disagrees with its names, another file
    with pytest.raises(bf.FindingsError, match="a line the grammar does not know: '  regime guessed: GREEN'"):
        bf.parse_run6_summary(text + "  regime guessed: GREEN\n")
    with pytest.raises(bf.FindingsError, match="the unknown-up-50% count and its names disagree"):
        bf.parse_run6_summary(text.replace("(6): ETRA, GIXI, OIG, TEVA, TRBG, WCCB", "(5): ETRA, GIXI, OIG, TEVA, TRBG, WCCB", 1))
    with pytest.raises(bf.FindingsError, match="not the owner's summary"):
        bf.parse_run6_summary("a summary\n" + text)
    with pytest.raises(bf.FindingsError, match="not the run-6 public record"):
        bf.run6_public(Path(STUDY_SPEC))


# ------------------------------------------------------------- the scan ----
def test_no_field_name_reads_as_a_credential(committed, monkeypatch, capsys):
    def keys(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                here = f"{path}.{k}" if path else str(k)
                yield here, str(k)
                yield from keys(v, here)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                yield from keys(v, f"{path}[{i}]")
    seen = list(keys(committed))
    assert len(seen) > 1000, len(seen)
    named = [path for path, key in seen if CREDENTIAL.search(key)]
    assert named == [], named
    assert bf.credential_like_fields(committed) == []
    # the guard itself: a nested name, a name under a list, the case
    assert bf.credential_like_fields({"a": {"api_version": 1}}) == ["a.api_version"]
    assert bf.credential_like_fields({"rows": [{"ok": 1}, {"access_count": 2}]}) == ["rows[1].access_count"]
    assert bf.credential_like_fields({"KEY": {"ok": 1}, "Token": 2}) == ["KEY", "Token"]
    assert bf.credential_like_fields({"readable": True, "basis_mismatch": 0, "up4_10d": 1}) == []
    # and main refuses to write or compare a file that carries one
    monkeypatch.setattr(bf, "build", lambda: {"nights": [], "market": {"sessions": []}, "auth_note": "x"})
    assert bf.main(["--check"]) == 2
    assert "a field name the secret scan reads as a credential: auth_note" in capsys.readouterr().out


# ---------------------------------------------------------- the refusals ----
def test_the_builder_refuses_evidence_that_does_not_reconcile(pubs, study, first, monkeypatch, tmp_path, capsys):
    study_doc, _ = study
    first_doc, _ = first
    # the study carries one row per burst of the night's first publication, or nothing
    gone = study_doc["rows"][0]["session"]
    dropped = {**study_doc, "rows": study_doc["rows"][1:]}
    with pytest.raises(bf.FindingsError, match=f"{gone}: the study carries \\d+ rows for \\d+ bursts"):
        bf.nights_of(pubs, dropped, first_doc)
    # one night, one phase
    rows = [dict(r) for r in study_doc["rows"]]
    assert rows[0]["phase"] == "exploratory"
    rows[0]["phase"] = "confirmatory"
    with pytest.raises(bf.FindingsError, match=f"{gone}: one night, 2 phases"):
        bf.nights_of(pubs, {**study_doc, "rows": rows}, first_doc)
    # the ratio thresholds, and the rules the captions name, cannot move between publications
    moved = copy.deepcopy(pubs[-1])
    moved["data"]["breadth"]["regime"]["thresholds"]["ratio_10d_red"] = 1.5
    with pytest.raises(bf.FindingsError, match="the ratio thresholds moved"):
        bf.market_series(pubs[:-1] + [moved], {})
    moved = copy.deepcopy(pubs[-1])
    moved["data"]["rules"]["breadth"]["burst_pct"] = 5.0
    with pytest.raises(bf.FindingsError, match=r"rules\.breadth\.burst_pct moved: 5\.0 after 4\.0"):
        bf.rules_of(pubs[:-1] + [moved])
    assert bf.rules_of(pubs)["breadth"]["burst_pct"] == 4.0
    # a study not run under the committed spec is refused before any record is read, and main says so with exit 2
    def not_this_spec(path):
        return ({**study_doc, "spec_sha256": "0" * 64}, "0" * 64) if path == bf.STUDY else (first_doc, "1" * 64)
    monkeypatch.setattr(bf, "load_study", not_this_spec)
    with pytest.raises(bf.FindingsError, match="not run under the committed extended spec"):
        bf.build()
    assert bf.main(["--check"]) == 2
    assert "historical findings: the study was not run under the committed extended spec" in capsys.readouterr().out
    monkeypatch.undo()
    # the run-6 join: build() is the one function that performs it (the parser accepts any date)
    text = (ROOT / RUN6_SUMMARY).read_text(encoding="utf-8")
    elsewhere = text.replace("2026-09-25", "2026-01-02")
    parsed = bf.parse_run6_summary(elsewhere)
    assert sorted(parsed["sessions"]) == ["2026-01-02", "2026-09-24"]
    summary = tmp_path / "owner-summary.txt"
    summary.write_text(elsewhere, encoding="utf-8")
    monkeypatch.setattr(bf, "RUN6_SUMMARY", summary)          # ROOT / an absolute path is that path
    with pytest.raises(bf.FindingsError, match="run 6 measured 2026-01-02, a session no publication carries"):
        bf.build()
