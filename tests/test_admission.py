"""src.admission: which discovered candidates the trade band and the chart reads
may consider, read off the route and the checklist's own checks.

The rule is the owner's of 4 November 2026: a 4%-route name is admitted; a
dollar-only name only on a range-expansion, higher-volume day (the
checklist's RE and VOL both passing). Every test here breaks one rule and
watches its own assertion go red: the block re-derived from a row, a row
from before the rule read as admitted, a half-written block earning
nothing, the summary over the band, the sentence from its counts alone, and
the validator refusing a forged block, a missing one, one beside rules that
archive none, and an unknown version.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src import admission, pipeline, report

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "tests" / "fixtures" / "page"


def check(letter, passed):
    return {"letter": letter, "key": letter.lower(), "passed": passed, "pass": passed}


def row(scan, *, re=True, vol=True, grade="A", vetoes=(), ticker="X"):
    checks = [check("2", True), check("L", True), check("Y", True), check("N", True), check("C", False),
              check("H", True), check("RE", re), check("VOL", vol)]
    return {"ticker": ticker, "scan": scan, "grade_mechanical": grade, "grade": grade, "vetoes": list(vetoes),
            "quality": {"checks": checks}}


# ------------------------------------------------------------- the block ----
@pytest.mark.parametrize("scan, re, vol, basis, admitted", [
    ("burst", True, True, "burst_route", True),
    ("burst", False, False, "burst_route", True),      # the 4% scan's own conditions carry its day
    ("both", False, None, "burst_route", True),
    ("dollar", True, True, "dollar_expansion", True),
    ("dollar", False, True, "dollar_no_expansion", False),
    ("dollar", True, False, "dollar_no_expansion", False),
    ("dollar", False, False, "dollar_no_expansion", False),
    ("dollar", None, True, "dollar_no_expansion", False),   # a check that could not be read is not a pass
    ("dollar", True, None, "dollar_no_expansion", False),
])
def test_the_block_is_the_route_and_the_two_expansion_checks(scan, re, vol, basis, admitted):
    b = admission.block(row(scan, re=re, vol=vol))
    assert b == {"version": 1, "policy": admission.POLICY, "route": scan, "basis": basis, "admitted": admitted,
                 "expansion": {"range_expansion": re, "higher_volume": vol}, "reason": admission.LABELS[basis]}
    assert admission.admitted({**row(scan), "admission": b}) is admitted


def test_a_route_the_scanner_never_writes_is_refused_by_name():
    with pytest.raises(ValueError, match="unknown discovery route"):
        admission.block(row("4pct"))
    with pytest.raises(ValueError, match="unknown discovery route"):
        admission.block({"ticker": "X", "quality": {"checks": []}})


def test_the_expansion_is_read_off_the_recorded_checks_and_nothing_else():
    r = row("dollar", re=True, vol=True)
    assert admission.expansion(r) == {"range_expansion": True, "higher_volume": True}
    # a non-boolean verdict, a missing check and a malformed checks list each read as unknown
    r["quality"]["checks"][6]["passed"] = "yes"
    assert admission.expansion(r)["range_expansion"] is None
    del r["quality"]["checks"][7]
    assert admission.expansion(r)["higher_volume"] is None
    assert admission.expansion({"quality": {"checks": "none"}}) == {"range_expansion": None, "higher_volume": None}
    assert admission.expansion({"quality": None}) == {"range_expansion": None, "higher_volume": None}
    # the first RE and the first VOL decide; a duplicate later in the list does not
    r = row("dollar", re=False, vol=True)
    r["quality"]["checks"].append(check("RE", True))
    assert admission.expansion(r)["range_expansion"] is False


def test_the_block_reads_the_checklists_passed_field_not_the_display_copy():
    """The record writes both `passed` and `pass`; the block reads `passed`,
    the field the checklist decides on, so a display copy alone admits nothing."""
    r = row("dollar", re=True, vol=True)
    for c in r["quality"]["checks"]:
        if c["letter"] in ("RE", "VOL"):
            c["passed"] = False
    assert admission.block(r)["basis"] == "dollar_no_expansion"


# ------------------------------------------------------------- admitted() ----
def test_a_row_from_before_the_rule_is_admitted_and_a_half_written_block_earns_nothing():
    assert admission.admitted(row("dollar", re=False, vol=False)) is True, "no block: a record from before the rule"
    assert admission.admitted({**row("dollar"), "admission": None}) is True
    for bad in ({}, {"admitted": "yes"}, {"admitted": 1}, "admitted", [], {"basis": "burst_route"}):
        assert admission.admitted({**row("burst"), "admission": bad}) is False, bad
    assert admission.admitted("not a row") is True   # nothing to read: never a crash in a consumer


# -------------------------------------------------------------- summary ----
def rows_for_summary():
    rows = [row("burst", ticker="B1"), row("both", ticker="B2", grade="A+"),
            row("dollar", re=True, vol=True, ticker="D1"), row("dollar", re=False, vol=True, ticker="D2"),
            row("dollar", re=False, vol=False, ticker="D3", grade="B"),
            row("dollar", re=False, vol=False, ticker="D4", vetoes=["up_days"]),
            row("burst", ticker="B3", grade="skip")]
    for r in rows:
        r["admission"] = admission.block(r)
    return rows


def test_the_summary_counts_every_basis_and_the_band_without_a_veto():
    s = admission.summary(rows_for_summary(), ("A+", "A"))
    assert s["candidates"] == 7 and s["admitted"] == 4
    assert s["by_basis"] == {"burst_route": 3, "dollar_expansion": 1, "dollar_no_expansion": 3}
    # the band: mechanical A+/A without a veto -- B1, B2, D1, D2; D3 is a B, D4 is vetoed, B3 a skip
    assert s["in_band"] == {"total": 4, "burst_route": 2, "dollar_expansion": 1, "dollar_no_expansion": 1}
    assert s["version"] == 1 and s["policy"] == admission.POLICY
    assert s["sentence"] == admission.sentence(s)
    assert s["sentence"].startswith("Admission: 7 reaction candidates, 4 admitted to the trade band and the chart reads "
                                    "(3 by the 4% scan, 1 by the dollar scan on a range-expansion, higher-volume day); "
                                    "3 came through the dollar scan alone without one and are research only. "
                                    "Of the 4 mechanical A-band names without a veto, 3 are admitted and 1 is not.")
    assert s["sentence"].endswith("it is never a grade, and the chart reader never sees a name it stops.")


def test_the_band_is_counted_by_the_mechanical_grade_whatever_the_reader_made_of_it():
    """The band is the names the grade gate and the veto let through BEFORE the
    reader: a dollar-expansion A the reader lowered to C still counts, so the
    summary says how many names the admission reached, not how many the reader
    kept (a mutant counting by the final grade survived the summary test, whose
    rows all carry one grade)."""
    rows = rows_for_summary()
    lowered = row("dollar", re=True, vol=True, ticker="D5")
    lowered["grade"] = "C"   # grade_mechanical stays A
    lowered["admission"] = admission.block(lowered)
    s = admission.summary(rows + [lowered], ("A+", "A"))
    assert s["in_band"] == {"total": 5, "burst_route": 2, "dollar_expansion": 2, "dollar_no_expansion": 1}
    assert s["by_basis"] == {"burst_route": 3, "dollar_expansion": 2, "dollar_no_expansion": 3}
    assert "Of the 5 mechanical A-band names without a veto, 4 are admitted and 1 is not." in s["sentence"]


def test_the_sentence_is_the_counts_alone_in_their_singular_and_plural_forms():
    one = admission.summary([dict(rows_for_summary()[3])], ("A+", "A"))
    assert one["sentence"].startswith("Admission: 1 reaction candidate, 0 admitted to the trade band and the chart reads "
                                      "(0 by the 4% scan, 0 by the dollar scan on a range-expansion, higher-volume day); "
                                      "1 came through the dollar scan alone without one and is research only. "
                                      "Of the 1 mechanical A-band name without a veto, 0 are admitted and 1 is not.")
    none = admission.summary([], ("A+", "A"))
    assert none["sentence"] == "Admission: no reaction candidate was discovered."
    assert none["in_band"] == {"total": 0, "burst_route": 0, "dollar_expansion": 0, "dollar_no_expansion": 0}
    below = admission.summary([dict(rows_for_summary()[4])], ("A+", "A"))
    assert "No mechanical A-band name without a veto tonight." in below["sentence"]
    # a row without a block is counted among the candidates and under no basis
    bare = admission.summary([row("burst")], ("A+", "A"))
    assert bare["candidates"] == 1 and bare["admitted"] == 0 and bare["in_band"] == {"total": 1, "burst_route": 0, "dollar_expansion": 0, "dollar_no_expansion": 0}


# ----------------------------------------------------------- the validator ----
def record(rows, trade=("A+", "A"), *, archived=True):
    data = {"rules": {"pipeline": {"trade_grades": list(trade)}}, "bursts": copy.deepcopy(rows),
            "run": {"admission": admission.summary(rows, trade)}}
    if archived:
        data["rules"]["admission"] = {k.partition(".")[2]: v for k, v in admission.RULES.items()}
    return data


def test_the_validator_holds_every_row_and_the_run_block_to_their_own_re_derivation():
    data = record(rows_for_summary())
    assert admission.faults(data) == []
    forged = copy.deepcopy(data)
    forged["bursts"][3]["admission"]["admitted"] = True
    assert admission.faults(forged) == ["D2: admission is not the row's own"]   # the summary counts by basis, which stands
    forged = copy.deepcopy(data)
    forged["bursts"][3]["admission"]["basis"] = "dollar_expansion"
    assert admission.faults(forged) == ["D2: admission is not the row's own"]   # the run block is held to the re-derived rows, so it stands
    forged = copy.deepcopy(data)
    forged["bursts"][0]["admission"]["expansion"]["range_expansion"] = None
    assert admission.faults(forged) == ["B1: admission is not the row's own"]
    forged = copy.deepcopy(data)
    del forged["bursts"][2]["admission"]
    assert admission.faults(forged) == ["D1: admission block missing"]
    forged = copy.deepcopy(data)
    forged["bursts"][2]["scan"] = "4pct"
    assert admission.faults(forged) == ["D1: admission cannot be re-derived from its route"]
    forged = copy.deepcopy(data)
    forged["run"]["admission"]["in_band"]["dollar_no_expansion"] = 0
    assert admission.faults(forged) == ["run.admission is not the record's own"]
    forged = copy.deepcopy(data)
    forged["run"]["admission"]["sentence"] = "every name admitted"
    assert admission.faults(forged) == ["run.admission is not the record's own"]
    forged = copy.deepcopy(data)
    del forged["run"]["admission"]
    assert admission.faults(forged) == ["run.admission missing"]


def test_the_validator_compares_canonical_bytes_so_a_type_cannot_slip_through():
    data = record(rows_for_summary())
    forged = copy.deepcopy(data)
    forged["bursts"][0]["admission"]["version"] = 1.0
    assert admission.faults(forged) == ["B1: admission is not the row's own"]
    forged = copy.deepcopy(data)
    forged["run"]["admission"]["candidates"] = True
    assert admission.faults(forged) == ["run.admission is not the record's own"]
    forged = copy.deepcopy(data)
    forged["run"]["admission"]["candidates"] = float("nan")
    assert admission.faults(forged) == ["run.admission is not the record's own"]


def test_the_validator_names_the_first_rows_and_counts_the_rest():
    rows = [row("dollar", re=False, vol=False, ticker=f"D{i}") for i in range(8)]
    for r in rows:
        r["admission"] = admission.block(r)
        r["admission"]["admitted"] = True
    data = record(rows)
    data["run"]["admission"] = admission.summary(rows, ("A+", "A"))
    faults = admission.faults(data)
    assert faults[:5] == [f"D{i}: admission is not the row's own" for i in range(5)]
    assert faults[5] == "3 more rows' admission blocks are not the record's own"
    assert len(faults) == 6, faults   # the run block IS the summary over the forged rows


def test_the_validator_needs_the_archived_trade_grades_to_re_derive_the_run_block():
    data = record(rows_for_summary())
    del data["rules"]["pipeline"]["trade_grades"]
    assert admission.faults(data) == ["admission needs the archived pipeline.trade_grades"]
    data["rules"]["pipeline"]["trade_grades"] = "A"
    assert admission.faults(data) == ["admission needs the archived pipeline.trade_grades"]
    # the summary is held under the ARCHIVED grades, not the module's
    data = record(rows_for_summary(), trade=("A+",))
    assert admission.faults(data) == []
    data["run"]["admission"] = admission.summary(data["bursts"], ("A+", "A"))
    assert admission.faults(data) == ["run.admission is not the record's own"]


def test_a_record_from_before_the_rule_is_asked_for_nothing_and_refused_a_block():
    before = record([row("dollar", re=False, vol=False)], archived=False)
    del before["run"]["admission"]
    assert admission.faults(before) == []
    with_rows = copy.deepcopy(before)
    with_rows["bursts"][0]["admission"] = admission.block(with_rows["bursts"][0])
    assert admission.faults(with_rows) == ["admission block beside rules that archive no admission rule"]
    with_run = copy.deepcopy(before)
    with_run["run"]["admission"] = admission.summary([], ("A+", "A"))
    assert admission.faults(with_run) == ["run.admission beside rules that archive no admission rule"]
    for bad in (2, 0, True, "1", None):
        unknown = record(rows_for_summary())
        unknown["rules"]["admission"]["version"] = bad
        assert admission.faults(unknown) == ["admission archived version is unknown"], bad


def test_the_validator_takes_malformed_shapes_as_faults_never_as_a_crash():
    data = record(rows_for_summary())
    data["bursts"].append("not a row")
    assert admission.faults(data) == ["run.admission is not the record's own"] or admission.faults(data) == []
    odd = {"rules": "none", "bursts": None, "run": None}
    assert admission.faults(odd) == []
    odd = {"rules": {"admission": {"version": 1}, "pipeline": {"trade_grades": ["A"]}}, "bursts": [{"ticker": "Q", "scan": "burst", "admission": "x"}], "run": "x"}
    assert admission.faults(odd) == ["Q: admission is not the row's own", "run.admission missing"]


# -------------------------------------------------- the record and the rules ----
def test_the_rules_are_archived_under_their_own_family_and_the_fixtures_carry_the_block():
    from src import universe
    rules = pipeline.build_rules(universe.Universe(["AAA"], {}, {}, "explicit", None, {}, "test"))
    assert rules["admission"] == {"version": 1, "policy": "burst_route_or_dollar_expansion_v1",
                                  "burst_routes": ["burst", "both"], "dollar_checks": ["RE", "VOL"]}
    full = json.loads((PAGE / "full.json").read_text())
    full.pop("fixture", None)
    assert admission.faults(full) == []
    by_ticker = {b["ticker"]: b for b in full["bursts"]}
    assert by_ticker["MSFT"]["admission"]["basis"] == "dollar_no_expansion" and by_ticker["MSFT"]["grade_mechanical"] == "A"
    assert by_ticker["AAPL"]["admission"]["basis"] == "burst_route"
    assert full["run"]["admission"]["in_band"]["dollar_no_expansion"] == 1
    # the validator is wired into the report's own
    forged = copy.deepcopy(full)
    forged["bursts"][0]["admission"]["admitted"] = not forged["bursts"][0]["admission"]["admitted"]
    with pytest.raises(ValueError, match="admission is not the row's own"):
        report.validate(forged)


def test_the_funnels_route_label_is_the_admissions_own_words():
    from src import funnel
    assert funnel.LABELS["route"] == admission.NOT_ADMITTED_WORDS
    assert admission.LABELS["dollar_no_expansion"].startswith(admission.NOT_ADMITTED_WORDS)
