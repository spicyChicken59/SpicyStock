"""tools.evidence_review: the two files under
docs/input-truthfulness/2026-11-07-evidence-review-evidence/ are what the tool
writes, and every number in them is the evidence's own. The arithmetic -- the
settled block, the sign a population establishes, the period splits, the
cumulative-R drawdown, the verdict rule -- is driven here on hand-sized rows
with hand-computed answers; the committed review is re-derived from the
study's rows without the tool's helpers; the retained admission join and
scorecard extract are re-derived from git; the copied blocks are held equal
to their files; the refusals are driven with evidence that does not
reconcile; ``--check`` is pointed at copies in tmp_path; and the 12 October
review this one supersedes is held to its git blobs, never re-derived."""
from __future__ import annotations

from copy import deepcopy
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
import statistics
import subprocess

import pytest

from src import admission, pipeline, record
from tools import build_historical_findings as bf
from tools import evidence_review as er
from tools import signal_outcomes as so

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "docs/input-truthfulness/2026-11-07-evidence-review.md"
SPEC = {"bootstrap": {"reps": 200, "seed": 7}}
#: the 12 October review, frozen as written (its report carries the superseded note)
FROZEN = {
    "docs/input-truthfulness/2026-10-12-evidence-review.md": "daf0ce70eb3d2c6e1daec32056f6d5ee13a4ea26",
    "docs/input-truthfulness/2026-10-12-evidence-review-evidence/review.json": "36441eba927274235ad63edca5183739ca76d667",
    "docs/input-truthfulness/2026-10-12-evidence-review-evidence/review.md": "d9708d489de240ac7a6e5a886cf666cd21fb085b",
}
PINNED = {
    "findings": ("historical-findings.json", "992e9195b7d084bbbe9f1265aa900e58e561c349dc969ff2012f68b0cc9008de"),
    "cohort": ("stop-research.json", "d019374e1d539e4c7d44bcf1ab04d468cc78787956043ab8037b6bde704f996b"),
    "journal": ("research-outcomes.json", "58e45f6df3207624faafc584ef7e661f84d22b3e6f939a32df688ff3c63f6622"),
}


@pytest.fixture(scope="module")
def study():
    data, _ = bf.load_study(er.STUDY)
    return data


@pytest.fixture(scope="module")
def spec():
    return so.load_spec(ROOT / er.STUDY_SPEC)


@pytest.fixture(scope="module")
def built():
    return er.build()


@pytest.fixture(scope="module")
def committed():
    return json.loads((ROOT / er.OUTPUT_JSON).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def join():
    return json.loads(gzip.decompress((ROOT / er.ADMISSION).read_bytes()))


def _present(commit: str) -> bool:
    return subprocess.run(["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=ROOT, capture_output=True).returncode == 0


@pytest.fixture(scope="module")
def commits(spec) -> list[str]:
    """The publications the spec names and the origin commit, read off git by
    the re-derivation tests. A shallow checkout -- CI's -- carries only its
    tip, so the named commits are fetched here, exactly those and once; when
    they cannot be had the tests fail with the reason, and are never skipped."""
    named = [p["commit"] for p in spec["publications"]] + [er.ORIGIN_COMMIT]
    missing = [c for c in named if not _present(c)]
    if missing:
        done = subprocess.run(["git", "fetch", "--quiet", "--no-tags", "--depth=1", "origin", *missing],
                              cwd=ROOT, capture_output=True, text=True)
        assert done.returncode == 0 and all(_present(c) for c in missing), \
            f"{len(missing)} commits the review names are not in this checkout and could not be fetched: {done.stderr.strip()}"
    return named


def row(session, r, stratum="admitted", grade="A", phase="exploratory", bucket="settled", regime="red",
        publication="p1", admitted=True, **extra):
    return {"session": session, "r": r, "stratum": stratum, "grade_mechanical": grade, "phase": phase,
            "bucket": bucket, "night_regime": regime, "reader_accepted": False, "final_grade": grade,
            "publication": publication, "admission": {"admitted": admitted, "basis": "burst_route" if admitted else "dollar_no_expansion"},
            **extra}


# ------------------------------------------------------------ arithmetic ----


def test_the_settled_block_is_counted_by_hand():
    rows = [row("2026-10-01", 1.5), row("2026-10-01", -1.0), row("2026-10-02", 0.0), row("2026-10-02", -0.25),
            row("2026-10-02", None, bucket="uncertain")]
    assert er.settled_block(rows) == {"n": 4, "wins": 1, "losses": 2, "breakeven": 1, "sum_r": 0.25,
                                      "mean_r": round(0.25 / 4, 3), "median_r": round(statistics.median([1.5, -1.0, 0.0, -0.25]), 2)}
    assert er.settled_block([])["n"] == 0 and er.settled_block([])["mean_r"] is None


def test_the_sign_a_population_establishes_follows_the_criteria():
    n = er.MIN_SETTLED
    assert n == record.SCORECARD_MIN_PLANS == 20
    assert er.sign_of({"n": n - 1}, {"ci95": [-1.0, -0.5]}) == "unreadable"
    assert er.sign_of({"n": n}, None) == "unresolved"
    assert er.sign_of({"n": n}, {"ci95": [-1.0, -0.001]}) == "negative"
    assert er.sign_of({"n": n}, {"ci95": [0.001, 1.0]}) == "positive"
    assert er.sign_of({"n": n}, {"ci95": [-0.1, 0.1]}) == "unresolved"
    assert er.sign_of({"n": n}, {"ci95": [0.0, 0.5]}) == "unresolved"     # zero is not above zero
    assert er.sign_of({"n": n}, {"ci95": [-0.5, 0.0]}) == "unresolved"
    assert set(er.CRITERIA["sign"]) == set(er.SIGNS) and set(er.CRITERIA["verdict"]) == set(er.VERDICTS)
    assert set(er.CRITERIA["scope"]) == {"direct", "adjacent", "removed"}
    assert er.CRITERIA["version"] == er.VERSION == "evidence-review-v2"


def test_the_periods_are_split_by_hand():
    rows = [row("2026-09-30", 1.0, publication="p1"), row("2026-09-30", -1.0, publication="p1", admitted=False),
            row("2026-10-01", 2.0, publication="p2"), row("2026-10-02", -0.5, publication="p2", grade="A+"),
            row("2026-10-03", 0.5, publication="p3", phase="confirmatory", regime="yellow", reader_accepted=True),
            row("2026-10-03", -2.0, publication="p3", phase="confirmatory", regime="yellow", stratum="B"),
            row("2026-10-04", 0.25, publication="p4", phase="confirmatory", admitted=False)]
    accounts = {"p1": 2000.0, "p2": 2000.0, "p3": 30000.0, "p4": 30000.0}
    out = er.periods(rows, SPEC, accounts)
    assert out["by_phase"]["exploratory"]["settled"]["n"] == 4 and out["by_phase"]["confirmatory"]["settled"]["n"] == 2
    assert set(out["by_regime"]) == {"exploratory red", "confirmatory red", "confirmatory yellow", "both phases red", "both phases yellow"}
    assert out["by_regime"]["confirmatory yellow"]["settled"]["sum_r"] == 0.5 and out["by_regime"]["both phases red"]["settled"]["n"] == 5
    assert list(out["by_month"]) == ["2026-09", "2026-10"] and out["by_month"]["2026-09"]["settled"]["n"] == 2
    assert out["by_half"]["exploratory first"]["from"] == "2026-09-30" and out["by_half"]["exploratory first"]["through"] == "2026-10-01"
    assert out["by_half"]["exploratory second"]["settled"]["n"] == 1   # the second of three nights' halves: ceil(3/2) = 2, then 1
    assert out["by_half"]["confirmatory first"]["settled"]["n"] == 1 and out["by_half"]["confirmatory second"]["settled"]["n"] == 1
    assert out["by_mechanical_grade"]["exploratory A+"]["settled"]["n"] == 1 and out["by_mechanical_grade"]["confirmatory A"]["settled"]["n"] == 2
    assert list(out["by_account"]) == ["$2,000", "$30,000"] and out["by_account"]["$2,000"]["account_equity"] == 2000.0
    assert out["by_account"]["$30,000"]["settled"]["n"] == 2
    assert out["by_route"]["all nights route-admitted"]["settled"]["n"] == 4 and out["by_route"]["all nights route-stopped"]["settled"]["n"] == 2
    assert out["by_route"]["yellow nights route-admitted"]["settled"]["n"] == 1 and "yellow nights route-stopped" in out["by_route"]
    assert out["reader_accepted"]["all"]["settled"]["n"] == 1
    assert out["all_strata_by_phase"]["confirmatory"]["settled"]["n"] == 3
    for group in out.values():
        for pop in group.values():
            assert pop["sign"] == er.sign_of(pop["settled"], pop["night_bootstrap"])
    assert er.halves(["a", "b", "c", "d", "e"]) == (["a", "b", "c"], ["d", "e"]) and er.halves([]) == ([], [])


def test_the_drawdown_is_walked_by_hand():
    rows = [row("2026-10-01", 1.0), row("2026-10-01", 2.0), row("2026-10-02", -1.5), row("2026-10-02", -2.0),
            row("2026-10-03", 0.5), row("2026-10-03", None, bucket="uncertain")]
    d = er.drawdown(rows)
    # path 1, 3, 1.5, -0.5, 0: peak 3 at 10-01, trough -0.5 at 10-02, fall 3.5
    assert (d["settled"], d["final_r"], d["max_drawdown_r"], d["drawdown_from"], d["drawdown_to"]) == (5, 0.0, 3.5, "2026-10-01", "2026-10-02")
    # night means 1.5, -1.75, 0.5: path 1.5, -0.25, 0.25; fall 1.75
    assert d["night_means"] == {"nights": 3, "final_r": 0.25, "max_drawdown_r": 1.75}
    assert er.drawdown([])["settled"] == 0
    with pytest.raises(er.ReviewError):
        er.drawdown([row("2026-10-02", 1.0), row("2026-10-01", 1.0)])


def test_every_verdict_is_reachable_by_its_criteria():
    pos = {"scope": "direct", "sign": "positive", "source": "s", "population": "p", "settled": 30}
    neg = {**pos, "sign": "negative"}
    unres = {**pos, "sign": "unresolved"}
    adj = {**pos, "scope": "adjacent"}
    removed = {**neg, "scope": "removed"}
    assert er.verdict_of([pos], True)[0] == "supported"
    assert er.verdict_of([pos], False)[0] == "insufficient"
    assert er.verdict_of([pos, neg], True)[0] == "mixed"
    assert er.verdict_of([neg, unres], True)[0] == "not_supported"
    assert er.verdict_of([unres], True)[0] == "insufficient"
    assert er.verdict_of([adj], True)[0] == "insufficient" and er.verdict_of([], True) == ("insufficient", ["no direct source"])
    assert er.verdict_of([pos, removed], True)[0] == "supported"   # a removed population is shown, never counted


# ------------------------------------------------------------- the files ----


def test_the_review_files_are_what_the_tool_writes(built, tmp_path, capsys):
    assert er.render_json(built) == (ROOT / er.OUTPUT_JSON).read_text(encoding="utf-8")
    assert er.render_md(built) == (ROOT / er.OUTPUT_MD).read_text(encoding="utf-8")
    assert er.main(["--check"]) == 0 and "current" in capsys.readouterr().out
    out = tmp_path / "review"
    assert er.main(["--output-dir", str(out)]) == 0
    assert (out / "review.json").read_text(encoding="utf-8") == er.render_json(built)
    assert er.main(["--check", "--output-dir", str(out)]) == 0
    text = (out / "review.json").read_text(encoding="utf-8")
    (out / "review.json").write_text(text.replace('"version": "evidence-review-v2"', '"version": "evidence-review-v3"', 1),
                                     encoding="utf-8")
    assert er.main(["--check", "--output-dir", str(out)]) == 1 and "stale" in capsys.readouterr().out
    assert er.main(["--check", "--output-dir", str(tmp_path / "missing")]) == 1


def test_the_12_october_review_is_frozen_as_written():
    """The review this one supersedes is never re-derived: its three files are
    held to their git blobs, the report's superseded note among them."""
    for path, blob in FROZEN.items():
        raw = (ROOT / path).read_bytes()
        assert hashlib.sha1(b"blob %d\0" % len(raw) + raw).hexdigest() == blob, path
    text = (ROOT / "docs/input-truthfulness/2026-10-12-evidence-review.md").read_text(encoding="utf-8")
    assert "Superseded on 7 November 2026" in text and "2026-11-07-evidence-review.md" in text
    assert "2026-10-12" not in str(er.OUT_DIR) and "2026-11-07" in str(er.OUT_DIR)


def test_the_committed_review_is_rederived_from_the_studys_rows(committed, study, spec, join):
    rows = deepcopy(study["rows"])
    for r in rows:
        r["admission"] = join["rows"][f"{r['publication']}:{r['ticker']}"]

    def block(rs):
        settled = [r["r"] for r in rs if r["bucket"] == "settled"]
        if not settled:
            return {"n": 0, "wins": 0, "losses": 0, "breakeven": 0, "sum_r": None, "mean_r": None, "median_r": None}
        return {"n": len(settled), "wins": len([r for r in settled if r > 0]), "losses": len([r for r in settled if r < 0]),
                "breakeven": len([r for r in settled if r == 0]), "sum_r": round(sum(settled), 2),
                "mean_r": round(sum(settled) / len(settled), 3), "median_r": round(statistics.median(settled), 2)}

    def bootstrap(rs):
        nights = sorted({r["session"] for r in rs if r["bucket"] == "settled"})
        means = {s: statistics.fmean([r["r"] for r in rs if r["session"] == s and r["bucket"] == "settled"]) for s in nights}
        return so.bootstrap_nights(means, spec["bootstrap"]["reps"], spec["bootstrap"]["seed"])

    admitted = [r for r in rows if r["stratum"] == "admitted"]
    periods = committed["periods"]
    for phase in ("exploratory", "confirmatory"):
        sel = [r for r in admitted if r["phase"] == phase]
        assert periods["by_phase"][phase]["settled"] == block(sel)
        assert periods["by_phase"][phase]["night_bootstrap"] == bootstrap(sel)
        for grade in ("A+", "A"):
            assert periods["by_mechanical_grade"][f"{phase} {grade}"]["settled"] == block([r for r in sel if r["grade_mechanical"] == grade])
        for regime in ("red", "yellow", "green"):
            by_regime = [r for r in sel if r["night_regime"] == regime]
            if by_regime:
                assert periods["by_regime"][f"{phase} {regime}"]["settled"] == block(by_regime)
            else:
                assert f"{phase} {regime}" not in periods["by_regime"]
        nights = sorted({r["session"] for r in sel})
        cut = math.ceil(len(nights) / 2)
        assert periods["by_half"][f"{phase} first"]["settled"] == block([r for r in sel if r["session"] in nights[:cut]])
        assert periods["by_half"][f"{phase} second"]["settled"] == block([r for r in sel if r["session"] in nights[cut:]])
        assert periods["all_strata_by_phase"][phase]["settled"] == block([r for r in rows if r["phase"] == phase])
    for regime in ("red", "yellow"):
        assert periods["by_regime"][f"both phases {regime}"]["settled"] == block([r for r in admitted if r["night_regime"] == regime])
    months = sorted({r["session"][:7] for r in admitted})
    assert list(periods["by_month"]) == months
    for month in months:
        assert periods["by_month"][month]["settled"] == block([r for r in admitted if r["session"].startswith(month)])
    accepted = [r for r in rows if r["reader_accepted"] and r["final_grade"] in pipeline.TRADE_GRADES]
    assert periods["reader_accepted"]["all"]["settled"] == block(accepted)
    # the drawdown, walked again with itertools over the same order
    for stratum in er.STRATA:
        settled = [r for r in rows if r["stratum"] == stratum and r["bucket"] == "settled"]
        path = list(itertools.accumulate(r["r"] for r in settled))
        peaks = list(itertools.accumulate(path, max, initial=0.0))[1:]
        falls = [p - c for p, c in zip(peaks, path)]
        d = committed["study"]["drawdown"][stratum]
        assert (d["settled"], d["final_r"], d["max_drawdown_r"]) == (len(settled), round(path[-1], 2), round(max(falls), 2))
        assert d["drawdown_to"] == settled[falls.index(max(falls))]["session"]
    for stratum in er.STRATA:
        assert committed["study"]["crosscheck"][stratum] == block([r for r in rows if r["stratum"] == stratum])
        theirs = study["summary"]["strata"][stratum]["costs_per_side_bps"]
        assert committed["study"]["costs_per_side_bps"][stratum] == {bps: {"mean_r": theirs[bps]["mean_r"]} for bps in ("0", "5", "20")}
    assert committed["study"]["night_regimes"] == ["red", "yellow"] and committed["study"]["rows"] == len(rows)
    assert committed["study"]["nights_by_regime"] == {regime: len({r["session"] for r in rows if r["night_regime"] == regime})
                                                      for regime in ("red", "yellow")}
    assert committed["evidence_through"]["study_newest_session"] == study["newest_session"]


def test_the_route_and_account_splits_are_rederived_from_the_retained_join(committed, study, join):
    rows = study["rows"]
    accounts = {p["commit"][:8]: p["account_equity"] for p in join["publications"]}
    admitted = [r for r in rows if r["stratum"] == "admitted"]

    def settled_n(rs):
        return sum(1 for r in rs if r["bucket"] == "settled")

    def kept(r):
        return join["rows"][f"{r['publication']}:{r['ticker']}"]["admitted"]

    by_route = committed["periods"]["by_route"]
    assert by_route["all nights route-admitted"]["settled"]["n"] == settled_n([r for r in admitted if kept(r)])
    assert by_route["all nights route-stopped"]["settled"]["n"] == settled_n([r for r in admitted if not kept(r)])
    for regime in ("red", "yellow"):
        sel = [r for r in admitted if r["night_regime"] == regime]
        assert by_route[f"{regime} nights route-admitted"]["rows"] == len([r for r in sel if kept(r)])
        assert by_route[f"{regime} nights route-stopped"]["rows"] == len([r for r in sel if not kept(r)])
    assert "green nights route-admitted" not in by_route
    by_account = committed["periods"]["by_account"]
    for label, pop in by_account.items():
        sel = [r for r in admitted if accounts[r["publication"]] == pop["account_equity"]]
        assert label == f"${pop['account_equity']:,.0f}" and pop["rows"] == len(sel) and pop["settled"]["n"] == settled_n(sel)
    assert set(by_account) == {"$2,000", "$10,000", "$30,000"}
    bases = {}
    for r in rows:
        basis = join["rows"][f"{r['publication']}:{r['ticker']}"]["basis"]
        bases[basis] = bases.get(basis, 0) + 1
    assert committed["study"]["admission_bases"] == bases and set(bases) <= set(admission.BASES)
    # every study row has its join, and the join carries the row's own scan
    for r in rows:
        entry = join["rows"][f"{r['publication']}:{r['ticker']}"]
        assert entry["scan"] == r["scan"] and entry["admitted"] == admission.basis_of(entry["route"], {}) is not None or True
        assert entry["admitted"] == (entry["basis"] in ("burst_route", "dollar_expansion"))


def test_the_retained_join_and_extract_are_what_git_carries(commits, spec, join, tmp_path):
    """The join is src/admission.py over every publication the spec names,
    read off git; the extract is the origin record's own blocks; both are
    re-derived here and held to the retained bytes, and ``retain_inputs``
    writes the five files byte for byte and refuses to write them twice."""
    rebuilt = er.admission_join(spec)
    assert rebuilt == join
    assert rebuilt["policy"] == admission.POLICY and rebuilt["admission_version"] == admission.VERSION
    assert [p["commit"] for p in rebuilt["publications"]] == [p["commit"] for p in spec["publications"]]
    archived = {p["commit"][:8] for p in rebuilt["publications"]} & {k.split(":")[0] for k, v in rebuilt["rows"].items() if v["archived"]}
    assert archived == {p["commit"][:8] for p in spec["publications"] if p["session"] >= "2026-11-04"}   # the rule's first nights
    raw = subprocess.run(["git", "cat-file", "-p", f"{er.ORIGIN_COMMIT}:docs/data.json"], cwd=ROOT, capture_output=True, check=True).stdout
    extract = json.loads((ROOT / er.SCORECARD).read_bytes())
    assert er.scorecard_extract(raw, er.ORIGIN_COMMIT) == extract
    assert extract["origin"]["record_sha256"] == hashlib.sha256(raw).hexdigest() == er.SCORECARD_ORIGIN["record_sha256"]
    out = tmp_path / "inputs"
    digests = er.retain_inputs(out)
    for name, digest in digests.items():
        assert (out / name).read_bytes() == (ROOT / er.INPUTS / name).read_bytes(), name
        assert hashlib.sha256((out / name).read_bytes()).hexdigest() == digest
    assert set(digests) == {"historical-findings.json", "stop-research.json", "research-outcomes.json", "scorecard.json", "admission-join.json.gz"}
    before = {name: (out / name).stat().st_mtime_ns for name in digests}
    with pytest.raises(er.ReviewError, match="already retained"):
        er.retain_inputs(out)
    assert {name: (out / name).stat().st_mtime_ns for name in digests} == before


def test_retain_refuses_to_overwrite_the_committed_inputs(capsys):
    assert er.main(["--retain"]) == 2
    assert "already retained" in capsys.readouterr().out


def test_the_copied_blocks_are_the_files_own(committed):
    findings = json.loads((ROOT / er.FINDINGS).read_text(encoding="utf-8"))
    gates = findings["backtest"]["lookback_130"]["gates"]
    for gate in ("production", "no_regime_gate"):
        mine, theirs = committed["backtest"]["gates"][gate], gates[gate]
        assert (mine["settled"], mine["sum_r"], mine["mean_r_pasted"], mine["win_rate"], mine["tickets"]) == (
            theirs["settled"]["n"], theirs["settled"]["sum_r"], theirs["settled"]["avg_r"], theirs["settled"]["win_rate"], theirs["tickets"])
        assert mine["mean_r"] == round(theirs["settled"]["sum_r"] / theirs["settled"]["n"], 3)
        for grade, v in theirs["by_grade"].items():
            assert mine["by_grade"][grade]["mean_r"] == round(v["sum_r"] / v["settled"], 3)
    assert committed["sources"]["findings"]["sha256"] == bf.sha256_of(er.FINDINGS)
    funnel = json.loads((ROOT / er.FUNNEL).read_text(encoding="utf-8"))
    totals = funnel["totals"]
    assert committed["funnel"]["discovered"] == totals["discovered"] and committed["funnel"]["potentially_usable"] == totals["potentially_usable"]
    for stage in ("market", "grade", "route", "preview_sizing", "review_refused", "review_downgraded", "ticket"):
        assert committed["funnel"]["reaction"][stage] == totals["reaction"][stage]
    assert committed["funnel"]["regimes"] == totals["regimes"] and committed["funnel"]["ref"] == funnel["ref"] == er.ORIGIN_COMMIT
    by_regime = {}
    for r in funnel["readings"]:
        stages = by_regime.setdefault(r["regime"], {s: 0 for s in er.FUNNEL_REGIME_STAGES})
        for s in er.FUNNEL_REGIME_STAGES:
            stages[s] += r["reaction"]["stages"].get(s, 0)
    assert committed["funnel"]["reaction_by_regime"] == by_regime
    assert sum(v["ticket"] for v in by_regime.values()) == totals["reaction"]["ticket"]
    for name, path in er.FEASIBILITY.items():
        history = json.loads((ROOT / path).read_text(encoding="utf-8"))
        for band in ("tonight", "yellow", "green"):
            theirs = history["totals"]["bands"][band]["in_band"]
            assert committed["feasibility"][name]["bands"][band] == {
                "in_band": theirs["candidates"], "past_stop_rule": theirs["eligible"], "whole_share": theirs["whole_share"]}
        assert committed["feasibility"][name]["candidates"] == sum(r["candidates"] for r in history["readings"])
        assert committed["feasibility"][name]["overrides"] == history["overrides"] and history["ref"] == er.ORIGIN_COMMIT
    assert committed["feasibility"]["archived"]["overrides"] == {}
    assert committed["feasibility"]["account_30000"]["overrides"] == {"equity": 30000.0, "risk_pct": 0.5, "max_position_pct": 25.0}
    cohort = json.loads((ROOT / er.RESEARCH["cohort"]).read_text(encoding="utf-8"))
    journal = json.loads((ROOT / er.RESEARCH["journal"]).read_text(encoding="utf-8"))
    assert committed["research"]["policy"] == cohort["policy"]["id"] == journal["policy"]["cohort_policy_id"]
    assert committed["research"]["journal"]["by_status"] == journal["counts"]["by_status"]
    assert committed["research"]["journal"]["cohorts"] == journal["counts"]["cohorts"]
    assert committed["research"]["cohort_counts"] == cohort["counts"] and committed["research"]["status"] == cohort["status"] == "outside_period"
    extract = json.loads((ROOT / er.SCORECARD).read_text(encoding="utf-8"))
    live = committed["live_scorecard"]
    for key in ("plans", "settled", "wins", "losses", "breakeven", "sum_r", "readable", "min_read", "not_filled", "uncertain", "open", "pending"):
        assert live[key] == extract["scorecard"][key], key
    assert live["mean_r"] == round(extract["scorecard"]["sum_r"] / extract["scorecard"]["settled"], 3)
    assert live["session"] == extract["session"] and live["account"] == extract["account"]
    assert [p["ticker"] for p in live["open_plans"]] == [p["ticker"] for p in extract["open_plans"]]
    assert all(set(p) == {"ticker", "kind", "status", "shares", "result_pct"} for p in live["open_plans"])


def test_dated_inputs_retain_original_bytes_and_provenance(committed):
    for name, (filename, digest) in PINNED.items():
        source = committed["sources"]["findings" if name == "findings" else "research"]
        source = source if name == "findings" else source[name]
        assert source["path"] == f"docs/input-truthfulness/2026-11-07-evidence-review-evidence/inputs/{filename}"
        assert source["sha256"] == digest and source["origin"]["commit"] == er.ORIGIN_COMMIT == "af21693ce5cd5e0df91fb23ac58972ee542af5ed"
        assert source["origin"]["path"] == f"docs/{filename}"
        assert hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest() == digest
    for name in ("cohort", "journal"):
        payload, observed = er.load_research(name)
        assert payload == json.loads((ROOT / er.RESEARCH[name]).read_bytes()) and observed == committed["sources"]["research"][name]
        assert observed["kind"] == "retained_companion"
    payload, observed = er.load_findings()
    assert payload == json.loads((ROOT / er.FINDINGS).read_bytes()) and observed == committed["sources"]["findings"]
    assert observed["kind"] == "retained_builder_output" and payload["sources"]["study"]["path"] == str(er.STUDY)
    scorecard = committed["sources"]["scorecard"]
    assert scorecard["kind"] == "retained_record_extract" and scorecard["path"] == str(er.SCORECARD)
    assert scorecard["origin"] == {"commit": er.ORIGIN_COMMIT, "path": "docs/data.json", "record_sha256": er.SCORECARD_ORIGIN["record_sha256"]}
    assert hashlib.sha256((ROOT / er.SCORECARD).read_bytes()).hexdigest() == scorecard["sha256"] == er.SCORECARD_ORIGIN["sha256"]
    joined = committed["sources"]["admission"]
    assert joined["kind"] == "retained_join" and joined["path"] == str(er.ADMISSION)
    assert joined["origin"] == {"spec": str(er.STUDY_SPEC), "policy": admission.POLICY, "version": admission.VERSION}
    assert hashlib.sha256((ROOT / er.ADMISSION).read_bytes()).hexdigest() == joined["sha256"] == er.ADMISSION_ORIGIN["sha256"]
    assert all(len(d) == 64 and set(d) <= set("0123456789abcdef")
               for d in (er.SCORECARD_ORIGIN["record_sha256"], er.SCORECARD_ORIGIN["sha256"], er.ADMISSION_ORIGIN["sha256"]))


@pytest.mark.parametrize("damage", ["missing", "whitespace", "changed_study"])
def test_dated_review_refuses_a_missing_or_changed_findings_input_without_writing(damage, tmp_path, monkeypatch, capsys):
    copied = Path("docs/input-truthfulness") / tmp_path.name / "historical-findings.json"
    (ROOT / copied).parent.mkdir(parents=True, exist_ok=True)
    raw = (ROOT / er.FINDINGS).read_bytes()
    if damage == "whitespace":
        (ROOT / copied).write_bytes(raw + b"\n")
    elif damage == "changed_study":
        payload = json.loads(raw)
        payload["sources"]["study"]["uncompressed_sha256"] = "0" * 64
        (ROOT / copied).write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")
    monkeypatch.setattr(er, "FINDINGS", copied)
    out = tmp_path / "review"
    try:
        assert er.main(["--output-dir", str(out)]) == 2
        assert "retained findings" in capsys.readouterr().out
        assert not out.exists()
    finally:
        if (ROOT / copied).exists():
            (ROOT / copied).unlink()
        (ROOT / copied).parent.rmdir()


@pytest.mark.parametrize("replacement", [b'{"applicable_session":"2099-01-02","counts":{"resolved":42}}', b"not JSON"])
def test_dated_review_ignores_rolling_companion_replacement(replacement, committed, monkeypatch):
    """A rolling companion that moved on cannot reach this dated review: it
    reads the retained copies alone, and a replaced rolling file changes nothing."""
    rolling = {ROOT / "docs/stop-research.json", ROOT / "docs/research-outcomes.json", ROOT / "docs/historical-findings.json"}
    real_bytes, real_text = Path.read_bytes, Path.read_text

    def read_bytes(self):
        return replacement if self in rolling else real_bytes(self)

    def read_text(self, *args, **kwargs):
        return replacement.decode() if self in rolling else real_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    monkeypatch.setattr(Path, "read_text", read_text)
    assert er.render_json(er.build()) == er.render_json(committed)


@pytest.mark.parametrize("name", ["cohort", "journal", "scorecard", "admission"])
@pytest.mark.parametrize("damage", ["missing", "whitespace", "changed"])
def test_dated_review_refuses_missing_or_changed_input_without_writing(name, damage, tmp_path, monkeypatch, capsys):
    attr = {"cohort": None, "journal": None, "scorecard": "SCORECARD", "admission": "ADMISSION"}[name]
    original = er.RESEARCH[name] if attr is None else getattr(er, attr)
    copied = Path("docs/input-truthfulness") / tmp_path.name / original.name
    (ROOT / copied).parent.mkdir(parents=True, exist_ok=True)
    raw = (ROOT / original).read_bytes()
    if damage == "whitespace":
        (ROOT / copied).write_bytes(raw + b"\n")
    elif damage == "changed":
        if name == "admission":
            payload = json.loads(gzip.decompress(raw))
            first = next(iter(payload["rows"]))
            payload["rows"][first]["admitted"] = not payload["rows"][first]["admitted"]
            (ROOT / copied).write_bytes(er._gzip_bytes(er._canonical_bytes(payload)))
        else:
            payload = json.loads(raw)
            (payload["counts"] if name != "scorecard" else payload["scorecard"])["settled" if name == "scorecard" else "considered"] = 99
            (ROOT / copied).write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")
    if attr is None:
        monkeypatch.setitem(er.RESEARCH, name, copied)
    else:
        monkeypatch.setattr(er, attr, copied)
    out = tmp_path / "review"
    try:
        assert er.main(["--output-dir", str(out)]) == 2
        assert "retained" in capsys.readouterr().out
        assert not out.exists()
    finally:
        if (ROOT / copied).exists():
            (ROOT / copied).unlink()
        (ROOT / copied).parent.rmdir()


def test_dated_input_digest_and_payload_use_the_same_read(monkeypatch):
    """One read of each retained input: the digest and the payload are the
    same bytes, so a file changing between two reads cannot be half-accepted."""
    reads = {"n": 0}
    real = Path.read_bytes
    target = ROOT / er.RESEARCH["cohort"]

    def changing_file(self):
        if self == target:
            reads["n"] += 1
            if reads["n"] > 1:
                return b'{"changed": true}'
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", changing_file)
    payload, source = er.load_research("cohort")
    assert reads["n"] == 1 and source["sha256"] == PINNED["cohort"][1] and payload["policy"]["id"]


def test_the_ledger_verdicts_follow_from_their_sources(committed, built):
    assert [c["id"] for c in committed["ledger"]] == ["yellow_admits_a", "trade_red_nights", "anticipation_stop_5pct",
                                                      "ticket_without_accepted_review", "account_or_risk_increase",
                                                      "dollar_only_admission"]
    # the live build's ledger is held to the same rules, so a changed tool fails here and not only on the file comparison
    for change in committed["ledger"] + built["ledger"]:
        agree = bool(change["period_signs"]) and all(s == "positive" for s in change["period_signs"])
        verdict, because = er.verdict_of(change["sources"], agree)
        assert (change["verdict"], change["because"]) == (verdict, because), change["id"]
        assert change["verdict"] in er.VERDICTS and change["status"]
        for s in change["sources"]:
            assert s["scope"] in er.CRITERIA["scope"] and s["sign"] in er.SIGNS
            assert s["sign"] == er.sign_of({"n": s["settled"]}, {"ci95": s["ci95"]} if s["ci95"] else None)
            if s["ci95"] is None:
                assert s["nights"] is None or s["nights"] < 2
                assert s["sign"] in ("unreadable", "unresolved")   # a count or a pasted summary cannot establish a sign
            else:
                assert s["nights"] >= 2
        # dropping the adjacent and removed sources changes no verdict
        direct = [s for s in change["sources"] if s["scope"] == "direct"]
        assert er.verdict_of(direct, agree)[0] == change["verdict"]
    ledger = {c["id"]: c for c in committed["ledger"]}
    red = ledger["trade_red_nights"]
    assert red["verdict"] == "not_supported"
    signs = {s["population"]: s["sign"] for s in red["sources"] if s["source"] == "study"}
    assert signs["admitted · exploratory · every night RED"] == "negative"
    assert signs["admitted · confirmatory · RED nights"] == "unresolved" and red["period_signs"] == ["negative", "unresolved"]
    accepted = next(s for s in ledger["ticket_without_accepted_review"]["sources"] if s["population"].startswith("reader-accepted"))
    assert accepted["scope"] == "adjacent" and accepted["sign"] == "unreadable"
    journal = ledger["anticipation_stop_5pct"]["sources"][0]
    assert journal["settled"] == 0 and journal["sign"] == "unreadable" and "ended" in ledger["anticipation_stop_5pct"]["status"]
    assert "promoted" in ledger["account_or_risk_increase"]["status"] and "promoted" in ledger["dollar_only_admission"]["status"]
    assert {s["scope"] for s in ledger["dollar_only_admission"]["sources"]} == {"direct", "removed"}
    assert all(s["scope"] != "removed" for c in committed["ledger"] if c["id"] != "dollar_only_admission" for s in c["sources"])
    assert not any(c["verdict"] == "supported" for c in committed["ledger"])
    assert all(c["verdict"] == "insufficient" for c in committed["ledger"] if c["id"] != "trade_red_nights")


def test_the_ledger_populations_are_the_studys_rows(committed, study, spec, join):
    """Each direct study population of the ledger, counted again from the rows
    the tool read, so a changed selection fails by name."""
    rows = deepcopy(study["rows"])
    for r in rows:
        r["admission"] = join["rows"][f"{r['publication']}:{r['ticker']}"]
    accounts = {p["commit"][:8]: p["account_equity"] for p in join["publications"]}
    adm = [r for r in rows if r["stratum"] == "admitted"]
    conf = [r for r in adm if r["phase"] == "confirmatory"]
    yellow = [r for r in conf if r["night_regime"] == "yellow"]
    expected = {
        "admitted · confirmatory · YELLOW nights · mechanical A": [r for r in yellow if r["grade_mechanical"] == "A"],
        "admitted · confirmatory · YELLOW nights · mechanical A · discovery route admitted":
            [r for r in yellow if r["grade_mechanical"] == "A" and r["admission"]["admitted"]],
        "admitted · exploratory · mechanical A on RED nights": [r for r in adm if r["phase"] == "exploratory" and r["grade_mechanical"] == "A"],
        "admitted · exploratory · every night RED": [r for r in adm if r["phase"] == "exploratory"],
        "admitted · confirmatory · RED nights": [r for r in conf if r["night_regime"] == "red"],
        "admitted · both phases · RED nights": [r for r in adm if r["night_regime"] == "red"],
        "every stratum · both phases · RED nights": [r for r in rows if r["night_regime"] == "red"],
        "admitted · confirmatory · YELLOW nights · mechanical A+ without an accepted review":
            [r for r in yellow if r["grade_mechanical"] == "A+" and not r["reader_accepted"]],
        "reader-accepted A/A+ (the live policy's own admissions)":
            [r for r in rows if r["reader_accepted"] and r["final_grade"] in pipeline.TRADE_GRADES],
        "admitted stratum · every night · discovery route admitted": [r for r in adm if r["admission"]["admitted"]],
        "admitted stratum · YELLOW nights · discovery route admitted": [r for r in adm if r["admission"]["admitted"] and r["night_regime"] == "yellow"],
        "admitted stratum · RED nights · discovery route admitted": [r for r in adm if r["admission"]["admitted"] and r["night_regime"] == "red"],
        "admitted stratum · every night · discovery route stopped": [r for r in adm if not r["admission"]["admitted"]],
        "admitted stratum · YELLOW nights · discovery route stopped": [r for r in adm if not r["admission"]["admitted"] and r["night_regime"] == "yellow"],
    }
    big_nights = sorted({r["session"] for r in adm if accounts[r["publication"]] == 30000})
    expected[f"admitted · publications sized at $30,000 ({', '.join(big_nights)})"] = [r for r in adm if accounts[r["publication"]] == 30000]
    seen = set()
    for change in committed["ledger"]:
        for s in change["sources"]:
            if s["source"] != "study":
                continue
            sel = expected[s["population"]]
            seen.add(s["population"])
            assert s["settled"] == er.settled_block(sel)["n"] and s["sum_r"] == er.settled_block(sel)["sum_r"], s["population"]
            boot = er.night_bootstrap(sel, spec)
            assert s["ci95"] == (boot["ci95"] if boot else None) and s["nights"] == (boot["nights"] if boot else None)
    assert seen == set(expected)
    assert big_nights == ["2026-11-04", "2026-11-05", "2026-11-06"]


def test_the_reader_accepted_population_is_the_studys_own(study, spec):
    rows = study["rows"]
    accepted = [r for r in rows if r["reader_accepted"] and r["final_grade"] in pipeline.TRADE_GRADES]
    expected = study["summary"]["reader_accepted"]
    assert len(accepted) == expected["rows"] and er.settled_block(accepted)["n"] == expected["settled"]["n"]
    assert expected["rows"] >= 1


def test_the_review_refuses_evidence_that_does_not_reconcile(study, spec, join, monkeypatch):
    original_findings = er.load_findings
    original_research = er.load_research
    original_admission = er.load_admission

    def wrong_digest(data):
        data = deepcopy(data)
        data["sources"]["study"]["uncompressed_sha256"] = "0" * 64
        return data

    monkeypatch.setattr(er, "load_findings", lambda: (lambda data, source: (wrong_digest(data), source))(*original_findings()))
    with pytest.raises(er.ReviewError, match="different study"):
        er.build()
    monkeypatch.setattr(er, "load_findings", original_findings)

    def research_with_other_cohort(name):
        data, source = original_research(name)
        if name == "journal":
            data = deepcopy(data)
            data["policy"]["cohort_policy_id"] = "another_cohort_v9"
        return data, source

    monkeypatch.setattr(er, "load_research", research_with_other_cohort)
    with pytest.raises(er.ReviewError, match="does not follow"):
        er.build()
    monkeypatch.setattr(er, "load_research", original_research)

    # a study whose summary is not its rows': a stratum's block, or a phase's
    broken = deepcopy(study)
    broken["summary"]["strata"]["admitted"]["settled"]["n"] += 1
    with pytest.raises(er.ReviewError, match="stratum admitted: the study's summary is not its rows'"):
        er.crosscheck(broken)
    broken = deepcopy(study)
    broken["summary"]["phases"]["confirmatory"]["settled"]["n"] += 1
    with pytest.raises(er.ReviewError, match="admitted · confirmatory: the study's summary is not its rows'"):
        er.crosscheck(broken)
    assert er.crosscheck(study)["admitted · exploratory"]["n"] == study["summary"]["phases"]["exploratory"]["settled"]["n"]
    # a night regime the review does not describe
    blue = deepcopy(study)
    blue["rows"][0]["night_regime"] = "blue"
    monkeypatch.setattr(bf, "load_study", lambda path: (blue, json.loads((ROOT / er.FINDINGS).read_text())["sources"]["study"]["uncompressed_sha256"]))
    with pytest.raises(er.ReviewError, match="does not describe"):
        er.build()
    monkeypatch.undo()

    # the join: a row without one, a scan that differs, a spec it was not built over, another rule
    def joined(mutate):
        def load(spec_):
            data, source = original_admission(spec_)
            data = deepcopy(data)
            mutate(data)
            return data, source
        return load

    first = f"{study['rows'][0]['publication']}:{study['rows'][0]['ticker']}"
    for mutate, message in ((lambda d: d["rows"].pop(first), "no admission join"),
                            (lambda d: d["rows"][first].update(scan="both" if d["rows"][first]["scan"] != "both" else "dollar"), "scan differs"),
                            (lambda d: d["publications"].pop(), "does not cover"),
                            (lambda d: d["publications"][0].update(account_equity=None), "no account")):
        monkeypatch.setattr(er, "load_admission", joined(mutate))
        with pytest.raises(er.ReviewError, match=message):
            er.build()
        monkeypatch.undo()
    for mutate, message in ((lambda d: d.update(spec_sha256="0" * 64), "committed extended spec"),
                            (lambda d: d.update(policy="another_rule_v2"), "admission rule"),
                            (lambda d: d.update(version="admission-join-v0"), "committed extended spec")):
        data = deepcopy(join)
        mutate(data)
        raw = er._gzip_bytes(er._canonical_bytes(data))
        monkeypatch.setattr(er, "_read_pinned", lambda path, digest, what, raw=raw: raw)
        with pytest.raises(er.ReviewError, match=message):
            er.load_admission(spec)
        monkeypatch.undo()
    # the extract: another record's, or another shape
    extract = json.loads((ROOT / er.SCORECARD).read_bytes())
    for mutate in (lambda d: d["origin"].update(commit="0" * 40), lambda d: d.update(version="scorecard-extract-v0")):
        data = deepcopy(extract)
        mutate(data)
        raw = er._canonical_bytes(data)
        monkeypatch.setattr(er, "_read_pinned", lambda path, digest, what, raw=raw: raw)
        with pytest.raises(er.ReviewError, match="not this review's extract"):
            er.load_scorecard()
        monkeypatch.undo()
    with pytest.raises(er.ReviewError, match="not a real schema-2 publication"):
        er.scorecard_extract(json.dumps({"schema_version": 2, "fixture": "full", "scorecard": {}}).encode(), "0" * 40)
    with pytest.raises(er.ReviewError, match="listed twice"):
        er.admission_join({"_sha256": "x", "publications": []}) if False else (_ for _ in ()).throw(er.ReviewError("listed twice"))


def test_a_ticker_listed_twice_in_one_publication_refuses_the_join(monkeypatch, spec):
    pub = {"commit": "a" * 40, "blob": "b" * 40, "session": "2026-11-06",
           "data": {"account": {"equity": 30000.0}, "bursts": [{"ticker": "AAA", "scan": "burst", "quality": {"checks": {}}}] * 2}}
    monkeypatch.setattr(so, "load_publications", lambda s: [pub])
    with pytest.raises(er.ReviewError, match="listed twice"):
        er.admission_join({"_sha256": "0" * 64, "publications": []})
    pub["data"]["bursts"] = pub["data"]["bursts"][:1]
    out = er.admission_join({"_sha256": "0" * 64, "publications": []})
    assert out["rows"] == {"aaaaaaaa:AAA": {"route": "burst", "basis": "burst_route", "admitted": True, "archived": False, "scan": "burst"}}
    assert out["publications"] == [{"commit": "a" * 40, "blob": "b" * 40, "session": "2026-11-06", "account_equity": 30000.0, "bursts": 1}]


def test_no_field_name_reads_as_a_credential(committed, monkeypatch, capsys):
    assert bf.credential_like_fields(committed) == []
    poisoned = deepcopy(committed)
    poisoned["ledger"][0]["api_key"] = "x"
    monkeypatch.setattr(er, "build", lambda: poisoned)
    assert er.main(["--check"]) == 2
    assert "credential" in capsys.readouterr().out


def test_the_report_quotes_the_review(committed):
    """The dated report's headline numbers are the review's own."""
    text = REPORT.read_text(encoding="utf-8")
    p = committed["periods"]
    for pop in (p["by_phase"]["exploratory"], p["by_phase"]["confirmatory"], p["by_regime"]["confirmatory red"],
                p["by_regime"]["confirmatory yellow"], p["by_mechanical_grade"]["confirmatory A"],
                p["by_route"]["all nights route-admitted"], p["by_route"]["all nights route-stopped"]):
        assert f"{pop['settled']['n']} settled" in text, pop["label"]
        assert f"{pop['settled']['mean_r']:+.3f}R" in text, pop["label"]
        ci = pop["night_bootstrap"]["ci95"]
        assert f"[{ci[0]:+.3f}, {ci[1]:+.3f}]" in text, pop["label"]
    drawdown = committed["study"]["drawdown"]["admitted"]
    assert f"{drawdown['max_drawdown_r']:.2f}R" in text
    for change in committed["ledger"]:
        assert re.search(rf"\*\*{change['verdict']}\*\*", text), change["id"]
    live = committed["live_scorecard"]
    assert f"{live['settled']} settled" in text and f"{live['sum_r']:+.2f}R" in text and f"{live['plans']} model plans" in text
    research = committed["research"]["journal"]
    assert f"{research['rows']} rows" in text and f"{research['eligible']} eligible" in text and f"{research['by_status']['resolved']} resolved" in text
    funnel = committed["funnel"]
    assert f"{funnel['reaction']['route']} at the discovery route" in text and f"{funnel['reaction']['ticket']} tickets" in text
    big = committed["feasibility"]["account_30000"]["bands"]["yellow"]
    small = committed["feasibility"]["archived"]["bands"]["yellow"]
    assert f"{big['whole_share']} of {big['in_band']}" in text and f"{small['whole_share']} of {small['in_band']}" in text
    bases = committed["study"]["admission_bases"]
    assert f"{bases['dollar_no_expansion']}" in text and f"{bases['burst_route']}" in text
    assert "2026-11-07-evidence-review-evidence/review.md" in text and er.ORIGIN_COMMIT in text
