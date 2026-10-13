"""tools.evidence_review: the two files under
docs/input-truthfulness/2026-10-12-evidence-review-evidence/ are what the tool
writes, and every number in them is the evidence's own. The arithmetic -- the
settled block, the sign a population establishes, the period splits, the
cumulative-R drawdown, the verdict rule -- is driven here on hand-sized rows
with hand-computed answers; the committed review is re-derived from the
study's rows without the tool's helpers; the copied blocks are held equal to
their files; the refusals are driven with evidence that does not reconcile;
and ``--check`` is pointed at copies in tmp_path."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
import statistics

import pytest

from src import pipeline, record
from tools import build_historical_findings as bf
from tools import evidence_review as er
from tools import signal_outcomes as so

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "docs/input-truthfulness/2026-10-12-evidence-review.md"
SPEC = {"bootstrap": {"reps": 200, "seed": 7}}


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


def row(session, r, stratum="admitted", grade="A", phase="exploratory", bucket="settled", **extra):
    return {"session": session, "r": r, "stratum": stratum, "grade_mechanical": grade, "phase": phase,
            "bucket": bucket, "night_regime": "red", "reader_accepted": False, "final_grade": grade, **extra}


# ------------------------------------------------------------ arithmetic ----


def test_the_settled_block_is_counted_by_hand():
    rows = [row("2026-09-11", 1.5), row("2026-09-11", -1.0), row("2026-09-14", 0.0),
            row("2026-09-14", -0.25), row("2026-09-15", 9.0, bucket="pending")]
    assert er.settled_block(rows) == {"n": 4, "wins": 1, "losses": 2, "breakeven": 1, "sum_r": 0.25,
                                      "mean_r": 0.062, "median_r": -0.12}
    assert er.settled_block([]) == {"n": 0, "wins": 0, "losses": 0, "breakeven": 0,
                                    "sum_r": None, "mean_r": None, "median_r": None}


def test_the_sign_a_population_establishes_follows_the_criteria():
    few = {"n": er.MIN_SETTLED - 1}
    enough = {"n": er.MIN_SETTLED}
    assert er.sign_of(few, {"ci95": [-0.9, -0.1]}) == "unreadable"      # a count, never a rate
    assert er.sign_of(enough, None) == "unresolved"                      # no interval to read
    assert er.sign_of(enough, {"ci95": [-0.9, -0.1]}) == "negative"
    assert er.sign_of(enough, {"ci95": [0.1, 0.9]}) == "positive"
    assert er.sign_of(enough, {"ci95": [-0.1, 0.9]}) == "unresolved"     # straddles zero
    assert er.sign_of(enough, {"ci95": [-0.1, 0.0]}) == "unresolved"     # touching zero is not below it
    assert er.MIN_SETTLED == record.SCORECARD_MIN_PLANS
    # a pasted summary carries a count and a sum, no rows: readable at most, never a sign
    pasted = er.pasted_row("backtest", "direct", "p", er.MIN_SETTLED, 12.5, "pasted")
    assert (pasted["settled"], pasted["mean_r"], pasted["ci95"], pasted["sign"]) == (er.MIN_SETTLED, 0.625, None, "unresolved")
    assert er.pasted_row("backtest", "direct", "p", er.MIN_SETTLED - 1, 12.5, "pasted")["sign"] == "unreadable"
    assert er.pasted_row("journal", "direct", "p", 0, 0.0, "pasted")["mean_r"] is None


def test_the_periods_are_split_by_hand():
    nights = ["2026-09-01", "2026-09-02", "2026-09-03", "2026-10-01", "2026-10-02"]
    rows = [row(nights[0], 1.0, grade="A+"), row(nights[0], -1.0), row(nights[1], 0.5), row(nights[2], -0.5),
            row(nights[3], 2.0), row(nights[4], -2.0),
            row("2026-10-05", -1.0, phase="confirmatory"), row("2026-10-05", 3.0, phase="confirmatory", bucket="open"),
            row(nights[0], 7.0, stratum="B"), row(nights[1], -7.0, stratum="vetoed")]
    split = er.periods(rows, SPEC)
    assert split["by_phase"]["exploratory"]["settled"]["n"] == 6 and split["by_phase"]["confirmatory"]["settled"]["n"] == 1
    assert split["by_phase"]["confirmatory"]["rows"] == 2 and split["by_phase"]["confirmatory"]["settled_nights"] == 1
    assert [p["settled"]["n"] for p in split["by_month"].values()] == [4, 2] and list(split["by_month"]) == ["2026-09", "2026-10"]
    # the halves split the exploratory NIGHTS, three and two, not the rows
    assert (split["by_half"]["first"]["from"], split["by_half"]["first"]["through"]) == (nights[0], nights[2])
    assert (split["by_half"]["second"]["from"], split["by_half"]["second"]["through"]) == (nights[3], nights[4])
    assert split["by_half"]["first"]["settled"]["n"] == 4 and split["by_half"]["second"]["settled"]["n"] == 2
    assert split["by_mechanical_grade"]["A+"]["settled"] == er.settled_block([row(nights[0], 1.0)])
    assert split["by_mechanical_grade"]["A"]["settled"]["n"] == 5
    assert split["all_strata_by_phase"]["exploratory"]["settled"]["n"] == 8
    assert er.halves(["a", "b", "c", "d"]) == (["a", "b"], ["c", "d"]) and er.halves(["a"]) == (["a"], [])


def test_the_drawdown_is_walked_by_hand():
    rows = [row("2026-09-11", 1.0), row("2026-09-11", -0.5), row("2026-09-14", -1.0), row("2026-09-15", 2.0),
            row("2026-09-16", 4.0, bucket="uncertain")]
    d = er.drawdown(rows)
    # path 1.0, 0.5, -0.5, 1.5: the peak 1.0 on the 11th, the trough -0.5 on the 14th
    assert (d["settled"], d["final_r"], d["max_drawdown_r"]) == (4, 1.5, 1.5)
    assert (d["drawdown_from"], d["drawdown_to"]) == ("2026-09-11", "2026-09-14")
    # night means 0.25, -1.0, 2.0: path 0.25, -0.75, 1.25, the fall 1.0
    assert d["night_means"] == {"nights": 3, "final_r": 1.25, "max_drawdown_r": 1.0}
    # a path that never rises falls from its start
    down = er.drawdown([row("2026-09-11", -1.0), row("2026-09-14", -0.5)])
    assert (down["max_drawdown_r"], down["drawdown_from"], down["drawdown_to"]) == (1.5, "2026-09-11", "2026-09-14")
    assert er.drawdown([])["settled"] == 0 and er.drawdown([])["drawdown_from"] is None
    with pytest.raises(er.ReviewError, match="session order"):
        er.drawdown([row("2026-09-14", 1.0), row("2026-09-11", 1.0)])


def test_every_verdict_is_reachable_by_its_criteria():
    pos = {"scope": "direct", "sign": "positive", "source": "s", "population": "p", "settled": 30}
    neg = {**pos, "sign": "negative"}
    unresolved = {**pos, "sign": "unresolved"}
    adjacent_neg = {**neg, "scope": "adjacent"}
    assert er.verdict_of([pos], True)[0] == "supported"
    assert er.verdict_of([pos], False)[0] == "insufficient"           # the periods disagree
    assert er.verdict_of([pos, neg], True)[0] == "mixed"
    assert er.verdict_of([neg, unresolved], True)[0] == "not_supported"
    assert er.verdict_of([unresolved], True)[0] == "insufficient"
    assert er.verdict_of([], True) == ("insufficient", ["no direct source"])
    # an adjacent source is shown and never counted
    assert er.verdict_of([pos, adjacent_neg], True)[0] == "supported"
    assert set(er.CRITERIA["verdict"]) == set(er.VERDICTS) and set(er.CRITERIA["sign"]) == set(er.SIGNS)


# ------------------------------------------------------ the committed review ----


def test_the_review_files_are_what_the_tool_writes(built, tmp_path, capsys):
    assert er.render_json(built) == (ROOT / er.OUTPUT_JSON).read_text(encoding="utf-8")
    assert er.render_md(built) == (ROOT / er.OUTPUT_MD).read_text(encoding="utf-8")
    assert er.main(["--check"]) == 0 and "current" in capsys.readouterr().out
    out = tmp_path / "review"
    assert er.main(["--output-dir", str(out)]) == 0
    assert (out / "review.json").read_text(encoding="utf-8") == er.render_json(built)
    assert er.main(["--check", "--output-dir", str(out)]) == 0
    text = (out / "review.json").read_text(encoding="utf-8")
    (out / "review.json").write_text(text.replace('"version": "evidence-review-v1"', '"version": "evidence-review-v2"', 1),
                                     encoding="utf-8")
    assert er.main(["--check", "--output-dir", str(out)]) == 1 and "stale" in capsys.readouterr().out
    assert er.main(["--check", "--output-dir", str(tmp_path / "missing")]) == 1


def test_the_committed_review_is_rederived_from_the_studys_rows(committed, study, spec):
    rows = study["rows"]

    def block(rs):
        settled = [r["r"] for r in rs if r["bucket"] == "settled"]
        return {"n": len(settled), "wins": len([r for r in settled if r > 0]), "losses": len([r for r in settled if r < 0]),
                "breakeven": len([r for r in settled if r == 0]), "sum_r": round(sum(settled), 2),
                "mean_r": round(sum(settled) / len(settled), 3), "median_r": round(statistics.median(settled), 2)}

    admitted = [r for r in rows if r["stratum"] == "admitted" and r["phase"] == "exploratory"]
    assert committed["periods"]["by_phase"]["exploratory"]["settled"] == block(admitted)
    for grade in ("A+", "A"):
        assert committed["periods"]["by_mechanical_grade"][grade]["settled"] == block([r for r in admitted if r["grade_mechanical"] == grade])
    months = sorted({r["session"][:7] for r in admitted})
    assert list(committed["periods"]["by_month"]) == months
    for month in months:
        assert committed["periods"]["by_month"][month]["settled"] == block([r for r in admitted if r["session"].startswith(month)])
    nights = sorted({r["session"] for r in admitted})
    cut = math.ceil(len(nights) / 2)
    assert committed["periods"]["by_half"]["first"]["settled"] == block([r for r in admitted if r["session"] in nights[:cut]])
    assert committed["periods"]["by_half"]["second"]["settled"] == block([r for r in admitted if r["session"] in nights[cut:]])
    # the night bootstrap is the study's own, at the spec's reps and seed
    means = {s: statistics.fmean([r["r"] for r in admitted if r["session"] == s and r["bucket"] == "settled"])
             for s in nights if any(r["session"] == s and r["bucket"] == "settled" for r in admitted)}
    assert committed["periods"]["by_phase"]["exploratory"]["night_bootstrap"] == so.bootstrap_nights(
        means, spec["bootstrap"]["reps"], spec["bootstrap"]["seed"])
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
        assert committed["study"]["costs_per_side_bps"][stratum] == study["summary"]["strata"][stratum]["costs_per_side_bps"]
    assert committed["study"]["night_regimes"] == ["red"] and committed["study"]["rows"] == len(rows)
    assert committed["evidence_through"]["study_newest_session"] == study["newest_session"]


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
    funnel = json.loads((ROOT / er.FUNNEL).read_text(encoding="utf-8"))["totals"]
    assert committed["funnel"]["discovered"] == funnel["discovered"] and committed["funnel"]["potentially_usable"] == funnel["potentially_usable"]
    assert committed["funnel"]["reaction"]["grade"] == funnel["reaction"]["grade"] and committed["funnel"]["regimes"] == funnel["regimes"]
    for name, path in er.FEASIBILITY.items():
        history = json.loads((ROOT / path).read_text(encoding="utf-8"))
        for band in ("tonight", "yellow", "green"):
            theirs = history["totals"]["bands"][band]["in_band"]
            assert committed["feasibility"][name]["bands"][band] == {
                "in_band": theirs["candidates"], "past_stop_rule": theirs["eligible"], "whole_share": theirs["whole_share"]}
        assert committed["feasibility"][name]["candidates"] == sum(r["candidates"] for r in history["readings"])
    cohort = json.loads((ROOT / er.RESEARCH["cohort"]).read_text(encoding="utf-8"))
    journal = json.loads((ROOT / er.RESEARCH["journal"]).read_text(encoding="utf-8"))
    assert committed["research"]["policy"] == cohort["policy"]["id"] == journal["policy"]["cohort_policy_id"]
    assert committed["research"]["journal"]["by_status"] == journal["counts"]["by_status"]
    assert committed["research"]["cohort_counts"] == cohort["counts"]


def test_dated_research_sources_retain_original_bytes_and_provenance(committed):
    expected = {
        "cohort": ("stop-research.json", "98cc1b85b04aa3b570c777576d7d49f55edfe2bab5fe4e804362c5be7e2eeb22"),
        "journal": ("research-outcomes.json", "15de998bec9ac4862b1e5b4d480b1a7cd0a69cabbcaab77d24b36e2a7c970db2"),
    }
    for name, (filename, digest) in expected.items():
        source = committed["sources"]["research"][name]
        assert source == {
            "path": f"docs/input-truthfulness/2026-10-12-evidence-review-evidence/inputs/{filename}",
            "sha256": digest, "kind": "retained_companion",
            "origin": {"commit": "c759a1e671227717cae8d0bf1d50a4121d167396", "path": f"docs/{filename}"},
        }
        assert hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest() == digest
        payload, observed_source = er.load_research(name)
        assert payload == json.loads((ROOT / source["path"]).read_bytes())
        assert observed_source == source


@pytest.mark.parametrize("replacement", [b'{"applicable_session":"2099-01-02","counts":{"resolved":42}}', b"not JSON"])
def test_dated_review_ignores_rolling_companion_replacement(replacement, committed, monkeypatch):
    """A new night's companions, including unreadable ones, cannot revise this review."""
    rolling = {ROOT / "docs/stop-research.json", ROOT / "docs/research-outcomes.json"}
    original_bytes, original_text = Path.read_bytes, Path.read_text
    reads = []

    def read_bytes(path):
        if path in rolling:
            reads.append(path)
            return replacement
        return original_bytes(path)

    def read_text(path, *args, **kwargs):
        if path in rolling:
            reads.append(path)
            return replacement.decode("utf-8")
        return original_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    monkeypatch.setattr(Path, "read_text", read_text)
    assert er.build() == committed
    assert reads == []


@pytest.mark.parametrize("name", ["cohort", "journal"])
@pytest.mark.parametrize("damage", ["missing", "whitespace", "changed_counts"])
def test_dated_review_refuses_missing_or_changed_input_without_writing(name, damage, tmp_path, monkeypatch, capsys):
    copied = tmp_path / "input.json"
    raw = (ROOT / er.RESEARCH[name]).read_bytes()
    if damage == "whitespace":
        copied.write_bytes(raw + b"\n")  # same parsed value, different retained bytes
    elif damage == "changed_counts":
        data = json.loads(raw)
        data["counts"] = {"resolved": 999}
        copied.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setitem(er.RESEARCH, name, copied)
    out = tmp_path / "review"
    out.mkdir()
    original = {filename: b"previous dated evidence\n" for filename in ("review.json", "review.md")}
    for filename, body in original.items():
        (out / filename).write_bytes(body)
    assert er.main(["--output-dir", str(out)]) == 2
    refusal = capsys.readouterr().out
    assert f"retained research {name}:" in refusal
    assert ("cannot read" if damage == "missing" else "SHA-256 does not match") in refusal
    assert {filename: (out / filename).read_bytes() for filename in original} == original


def test_dated_input_digest_and_payload_use_the_same_read(monkeypatch):
    path = ROOT / er.RESEARCH["cohort"]
    raw = path.read_bytes()
    original_read = Path.read_bytes
    reads = []

    def changing_file(candidate):
        if candidate == path:
            reads.append(candidate)
            return raw if len(reads) == 1 else b'{"counts":{"resolved":999}}'
        return original_read(candidate)

    monkeypatch.setattr(Path, "read_bytes", changing_file)
    payload, source = er.load_research("cohort")
    assert len(reads) == 1
    assert payload == json.loads(raw)
    assert source["sha256"] == hashlib.sha256(raw).hexdigest()


def test_the_ledger_verdicts_follow_from_their_sources(committed, built):
    assert [c["id"] for c in committed["ledger"]] == ["yellow_admits_a", "trade_red_nights", "anticipation_stop_5pct",
                                                      "ticket_without_accepted_review", "account_or_risk_increase"]
    # the live build's ledger is held to the same rules, so a changed tool fails here and not only on the file comparison
    for change in committed["ledger"] + built["ledger"]:
        agree = bool(change["period_signs"]) and all(s == "positive" for s in change["period_signs"])
        verdict, because = er.verdict_of(change["sources"], agree)
        assert (change["verdict"], change["because"]) == (verdict, because), change["id"]
        assert change["verdict"] in er.VERDICTS
        for s in change["sources"]:
            assert s["scope"] in er.CRITERIA["scope"] and s["sign"] in er.SIGNS
            assert s["sign"] == er.sign_of({"n": s["settled"]}, {"ci95": s["ci95"]} if s["ci95"] else None)
            if s["ci95"] is None:
                assert s["sign"] in ("unreadable", "unresolved")   # a pasted summary cannot establish a sign
        # dropping the adjacent sources changes no verdict
        direct = [s for s in change["sources"] if s["scope"] == "direct"]
        assert er.verdict_of(direct, agree)[0] == change["verdict"]
    red = next(c for c in committed["ledger"] if c["id"] == "trade_red_nights")
    assert red["verdict"] == "not_supported" and {s["sign"] for s in red["sources"] if s["source"] == "study"} == {"negative"}
    accepted = next(s for c in committed["ledger"] for s in c["sources"] if s["population"].startswith("reader-accepted"))
    assert accepted["settled"] == 0 and accepted["sign"] == "unreadable"   # the live policy's own admissions: none settled
    assert not any(c["verdict"] == "supported" for c in committed["ledger"])


def test_the_reader_accepted_population_is_the_studys_own(study, spec):
    """The ledger's reader-accepted rows are the study's definition -- an
    accepted reply AND a final grade in the trade band -- not every row the
    reader answered, most of which it lowered out of the band."""
    rows = study["rows"]
    answered = [r for r in rows if r["reader_accepted"]]
    admitted = [r for r in answered if r["final_grade"] in pipeline.TRADE_GRADES]
    assert len(admitted) < len(answered)
    change = next(c for c in er.ledger(study, spec, er.periods(rows, spec), er.backtest_sources(
        json.loads((ROOT / er.FINDINGS).read_text(encoding="utf-8"))), er.funnel_source(
        json.loads((ROOT / er.FUNNEL).read_text(encoding="utf-8"))),
        {k: er.feasibility_source(json.loads((ROOT / p).read_text(encoding="utf-8"))) for k, p in er.FEASIBILITY.items()},
        er.research_source(*(json.loads((ROOT / er.RESEARCH[k]).read_text(encoding="utf-8")) for k in ("cohort", "journal"))))
        if c["id"] == "ticket_without_accepted_review")
    source = next(s for s in change["sources"] if s["population"].startswith("reader-accepted"))
    assert source["settled"] == er.settled_block(admitted)["n"] == study["summary"]["reader_accepted"]["settled"]["n"]


def test_the_review_refuses_evidence_that_does_not_reconcile(study, monkeypatch):
    original_load = er.load_json

    def load_with(overrides):
        def load(path):
            data = original_load(path)
            return overrides.get(str(path), lambda d: d)(data)
        return load

    def wrong_digest(findings):
        findings = deepcopy(findings)
        findings["sources"]["study"]["uncompressed_sha256"] = "0" * 64
        return findings
    monkeypatch.setattr(er, "load_json", load_with({str(er.FINDINGS): wrong_digest}))
    with pytest.raises(er.ReviewError, match="different study"):
        er.build()

    def other_cohort(journal):
        journal = deepcopy(journal)
        journal["policy"]["cohort_policy_id"] = "another_cohort_v9"
        return journal
    monkeypatch.setattr(er, "load_json", original_load)
    original_research = er.load_research

    def research_with_other_cohort(name):
        data, source = original_research(name)
        return (other_cohort(data) if name == "journal" else data), source

    monkeypatch.setattr(er, "load_research", research_with_other_cohort)
    with pytest.raises(er.ReviewError, match="registered cohort"):
        er.build()
    monkeypatch.setattr(er, "load_research", original_research)

    # a summary that is not its rows'
    forged = deepcopy(study)
    forged["summary"]["strata"]["B"]["settled"]["n"] += 1
    with pytest.raises(er.ReviewError, match="stratum B"):
        er.crosscheck(forged)
    forged = deepcopy(study)
    forged["summary"]["phases"]["exploratory"]["settled"]["mean_r"] = 0.0
    with pytest.raises(er.ReviewError, match="exploratory"):
        er.crosscheck(forged)
    # a night the review does not describe
    green = deepcopy(study)
    green["rows"][0]["night_regime"] = "green"
    monkeypatch.setattr(bf, "load_study", lambda path: (green, json.loads((ROOT / er.FINDINGS).read_text())["sources"]["study"]["uncompressed_sha256"]))
    with pytest.raises(er.ReviewError, match="nights the review does not describe"):
        er.build()


def test_no_field_name_reads_as_a_credential(committed, monkeypatch, capsys):
    assert bf.credential_like_fields(committed) == []
    poisoned = deepcopy(committed)
    poisoned["ledger"][0]["api_token"] = "not one"
    monkeypatch.setattr(er, "build", lambda: poisoned)
    assert er.main(["--check"]) == 2 and "credential" in capsys.readouterr().out


def test_the_report_quotes_the_review(committed):
    """The dated report's headline numbers are the review's own."""
    text = REPORT.read_text(encoding="utf-8")
    expl = committed["periods"]["by_phase"]["exploratory"]
    assert f"{expl['settled']['n']} settled" in text and f"{expl['settled']['mean_r']:+.3f}" in text
    ci = expl["night_bootstrap"]["ci95"]
    assert f"[{ci[0]:+.3f}, {ci[1]:+.3f}]" in text
    drawdown = committed["study"]["drawdown"]["admitted"]
    assert f"{drawdown['max_drawdown_r']:.2f}R" in text
    for change in committed["ledger"]:
        assert re.search(rf"\*\*{change['verdict']}\*\*", text), change["id"]
    production = committed["backtest"]["gates"]["production"]
    assert f"{production['settled']} settled" in text and f"{production['mean_r']:+.3f}" in text
    assert "2026-10-12-evidence-review-evidence/review.md" in text
