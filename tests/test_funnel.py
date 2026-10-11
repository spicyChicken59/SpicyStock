"""src.funnel: one terminal stage per discovered candidate, counted by the run.

Every fixture the generator writes carries the block the record re-derives;
the stage counts sum to the discovered count; every row's stage is one the
module names and reads off a field the run wrote; the validator refuses a
block the record does not re-derive; and a publication made under older rules
is read for what it recorded, with no block demanded of it. One real
publication is read out of git by commit (fetched into a shallow checkout
exactly once, as the findings tests do) so the funnel over the retained
9 October record is held, not described.
"""
from __future__ import annotations

import copy
import gzip
import json
from pathlib import Path
import subprocess

import pytest

from src import allocation, funnel, grader, reader_authority, reader_coverage, report

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "tests" / "fixtures" / "page"
FIXTURES = sorted(p for p in PAGE.glob("*.json") if p.name != "full-picks.json")
LEGACY = {"2026-09-25": ROOT / "tests/fixtures/wait-explanations/2026-09-25.json.gz",
          "2026-09-24": ROOT / "tests/fixtures/chart-keyboard/2026-09-24.json.gz"}
#: the retained 9 October publication: commit and the blob docs/data.json had there
PRODUCTION_COMMIT = "43dcb8d7c6eb0d63c1825198aa161fc4d4caec80"
PRODUCTION_BLOB = "58211b2d32343a2caf811d2d1af906acbef942ca"


def load(path: Path) -> dict:
    """A page fixture as the record the page reads: the generator's own
    ``fixture`` marker is not a record key, so the contract check is run without it."""
    data = json.loads(path.read_text())
    data.pop("fixture", None)
    return data


def load_gz(path: Path) -> dict:
    return json.loads(gzip.decompress(path.read_bytes()))


def accepted_reader(grade):
    return {"source": grader.SOURCE_CLAUDE, "grade": grade, "error": None}


def selected(**blockers):
    return {"policy": "account_feasible_first_research_v1", "selected": True, "blockers": [], **blockers}


def unselected(*blockers):
    return {"policy": "account_feasible_first_research_v1", "selected": False, "blockers": list(blockers)}


def planned(reason=None, admitted=False, blocked=False, **extra):
    p = {"ticker": "X", "kind": "burst", "action": "place_buy_stop", "eligible": True, "shares": 2,
         "allocation": {"policy": allocation.POLICY, "admitted": admitted, "reason": reason},
         "event_risk": {"blocked": blocked}}
    p.update(extra)
    return p


GREEN = ("A+", "A")


@pytest.fixture(scope="module")
def production() -> dict:
    """The 9 October publication, read out of git by commit and held to its
    blob. A shallow checkout -- CI's -- carries only its tip, so the commit is
    fetched when it is missing, exactly that one; when it cannot be had the
    module fails with the reason, and is never skipped."""
    def present() -> bool:
        return subprocess.run(["git", "cat-file", "-e", f"{PRODUCTION_COMMIT}^{{commit}}"],
                              cwd=ROOT, capture_output=True).returncode == 0
    if not present():
        done = subprocess.run(["git", "fetch", "--quiet", "--no-tags", "--depth=1", "origin", PRODUCTION_COMMIT],
                              cwd=ROOT, capture_output=True, text=True)
        assert done.returncode == 0 and present(), \
            f"the 9 October publication is not in this checkout and could not be fetched: {done.stderr.strip()}"
    blob = subprocess.run(["git", "rev-parse", f"{PRODUCTION_COMMIT}:docs/data.json"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout.strip()
    assert blob == PRODUCTION_BLOB, blob
    raw = subprocess.run(["git", "cat-file", "-p", f"{PRODUCTION_COMMIT}:docs/data.json"], cwd=ROOT,
                         capture_output=True, check=True).stdout
    return json.loads(raw)


# ------------------------------------------------------------ the fixtures ----
@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_every_fixture_carries_the_block_its_record_re_derives(path):
    data = load(path)
    assert data["rules"]["funnel"] == {"version": funnel.VERSION, "policy": funnel.POLICY}
    assert data["funnel"]["version"] == funnel.VERSION and data["funnel"]["policy"] == funnel.POLICY
    assert funnel.build(data) == data["funnel"]
    assert funnel.faults(data) == []
    report.validate(data)


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_the_stage_counts_are_a_partition_of_the_discovered_candidates(path):
    data = load(path)
    block = data["funnel"]
    r, a = block["reaction"], block["anticipation"]
    assert set(r["stages"]) == set(funnel.REACTION_STAGES)
    assert set(a["stages"]) == set(funnel.ANTICIPATION_STAGES)
    assert sum(r["stages"].values()) == r["discovered"] == len(data["bursts"]) == len(r["rows"])
    assert sum(a["stages"].values()) == a["listed"] == len(data["watchlist"]["top"]) == len(a["rows"])
    assert [row["ticker"] for row in r["rows"]] == [b["ticker"] for b in data["bursts"]]
    assert [row["ticker"] for row in a["rows"]] == [t["ticker"] for t in data["watchlist"]["top"]]
    assert all(row["stage"] in funnel.REACTION_STAGES for row in r["rows"])
    assert all(row["stage"] in funnel.ANTICIPATION_STAGES for row in a["rows"])
    assert sum(r["by_mechanical_grade"].values()) == r["discovered"]
    assert set(r["by_mechanical_grade"]) == set(grader.GRADES)
    assert 0 <= r["potentially_usable"] <= r["discovered"]
    # a ticket in the funnel is a ticket in the record, and the other way round
    assert sorted(row["ticker"] for row in r["rows"] if row["stage"] == "ticket") == sorted(data["trades"])
    assert sorted(row["ticker"] for row in a["rows"] if row["stage"] == "ticket") == sorted(
        t["ticker"] for t in data["watchlist"]["top"] if (t.get("plan") or {}).get("allocation", {}).get("admitted") is True)
    assert set(block["labels"]) == set(block["groups"]) == set(funnel.REACTION_STAGES) | set(funnel.ANTICIPATION_STAGES)
    assert block["sentence"] == funnel.sentence(block)
    for key in ("discovered", "potentially_usable"):
        assert str(r[key]) in block["sentence"]


def test_the_fixtures_between_them_reach_the_stages_the_record_can_write():
    reached = set()
    for path in FIXTURES:
        block = load(path)["funnel"]
        reached |= {s for s, n in block["reaction"]["stages"].items() if n}
        reached |= {"anticipation:" + s for s, n in block["anticipation"]["stages"].items() if n}
    assert {"market", "grade", "geometry", "allocation_slot", "ticket", "review_transport", "review_downgraded"} <= reached, reached
    assert {"anticipation:market", "anticipation:allocation_slot", "anticipation:ticket"} <= reached, reached


def test_a_closed_night_carries_the_previous_sessions_funnel_verbatim():
    closed, full = load(PAGE / "closed.json"), load(PAGE / "full.json")
    assert closed["run"]["session_state"] == "closed" or closed["bursts"], "the closed fixture carries no night"
    assert closed["funnel"]["reaction"]["stages"] == full["funnel"]["reaction"]["stages"]


# ------------------------------------------------------ the stage rules ----
def test_a_red_regime_stops_every_candidate_at_the_market_before_any_other_gate():
    row = {"ticker": "X", "grade_mechanical": "A+", "grade": "A+", "vetoes": [], "claude": accepted_reader("A+"),
           "review_selection": selected(), "plan": planned(admitted=True)}
    assert funnel.reaction_stage(row, (), {}, ["X"]) == "market"
    assert funnel.anticipation_stage({"ticker": "Y", "plan": planned(admitted=True)}, (), {}) == "market"
    assert funnel.anticipation_stage({"ticker": "Y", "plan": planned(reason="withheld")}, (), {}) == "market"


def test_the_grade_then_the_veto_are_read_off_the_mechanical_fields():
    assert funnel.reaction_stage({"grade_mechanical": "B", "grade": "B", "vetoes": []}, GREEN, {}, []) == "grade"
    assert funnel.reaction_stage({"grade_mechanical": "A+", "grade": "A+", "vetoes": ["up_days"]}, GREEN, {}, []) == "veto"
    # a vetoed name is a veto whatever the reader said of it
    assert funnel.reaction_stage({"grade_mechanical": "A", "grade": "A", "vetoes": ["not_linear"],
                                  "claude": accepted_reader("A"), "review_selection": selected()}, GREEN, {}, []) == "veto"


@pytest.mark.parametrize("blockers, stage", [
    (["known_event"], "preview_event"), (["plan_withheld"], "preview_geometry"),
    (["plan_withheld", "no_whole_share"], "preview_geometry"), (["no_whole_share"], "preview_sizing"),
    (["known_event", "no_whole_share"], "preview_event"),
    (["no_order"], "preview_no_order"), (["preview_unavailable"], "preview_unavailable"),
    ([], "review_budget"), (["something_new"], "review_unknown"),
])
def test_an_unreviewed_candidate_is_placed_by_the_selections_recorded_blockers(blockers, stage):
    row = {"ticker": "X", "grade_mechanical": "A", "grade": "A", "vetoes": [], "claude": None,
           "review_selection": unselected(*blockers)}
    assert funnel.reaction_stage(row, GREEN, {}, []) == stage


def test_a_record_without_a_selection_block_says_the_reasons_were_not_archived():
    row = {"ticker": "X", "grade_mechanical": "A", "grade": "A", "vetoes": [], "claude": None}
    assert funnel.reaction_stage(row, GREEN, {}, []) == "review_unselected"


def test_a_reviewed_candidate_without_an_accepted_reading_is_placed_by_the_readers_cause():
    base = {"ticker": "X", "grade_mechanical": "A", "grade": "A", "vetoes": [], "review_selection": selected()}
    cases = {
        grader.error_label(reader_authority.ReaderAuthorityError) + ": evidence outside criterion authority": "review_refused",
        grader.error_label(grader.DiscoveryConflict) + ": contradicts the discovery contract": "review_refused",
        grader.error_label(grader.ScoreFormatError) + ": no score": "review_format",
        "anthropic.AuthenticationError: " + grader.FATAL_AUTH_MARKERS[0]: "review_account",
        "anthropic.BadRequestError: " + grader.FATAL_CREDIT_MARKERS[0]: "review_credit",
        "anthropic.APIConnectionError: connection reset": "review_transport",
    }
    for error, stage in cases.items():
        row = {**base, "claude": {"source": grader.SOURCE_FALLBACK, "grade": None, "error": error}}
        assert reader_coverage.state(row) == reader_coverage.FALLBACK
        assert funnel.reaction_stage(row, GREEN, {}, []) == stage, error
    # a legacy record whose selected name carries no reader block at all
    assert funnel.reaction_stage({**base, "claude": None}, GREEN, {}, []) == "review_unknown"
    # a reader block that claims the model's source but does not agree with the row's grade is not accepted
    assert funnel.reaction_stage({**base, "claude": {"source": grader.SOURCE_CLAUDE, "grade": "B", "error": None}},
                                 GREEN, {}, []) == "review_unknown"


def test_an_accepted_reading_below_the_band_is_a_downgrade_and_above_it_reaches_the_plan():
    lowered = {"ticker": "X", "grade_mechanical": "A", "grade": "B", "vetoes": [], "review_selection": selected(),
               "claude": accepted_reader("B")}
    assert funnel.reaction_stage(lowered, GREEN, {}, []) == "review_downgraded"
    kept = {**lowered, "grade": "A", "claude": accepted_reader("A"), "plan": None,
            "evidence": {"planning": {"error": "ValueError: no stop candidate"}}}
    assert funnel.reaction_stage(kept, GREEN, {}, []) == "plan_error"
    assert funnel.reaction_stage({**kept, "evidence": {"planning": {"error": None}}}, GREEN, {}, []) == "plan_unavailable"


@pytest.mark.parametrize("plan_, stage", [
    (planned(admitted=True), "ticket"),
    (planned(reason="withheld"), "geometry"),
    (planned(reason="withheld", blocked=True), "event"),
    (planned(reason="no_shares", shares=0), "sizing"),
    (planned(reason="slot_cap"), "allocation_slot"),
    (planned(reason="equity"), "allocation_cash"),
    (planned(reason="existing_position"), "allocation_occupied"),
    (planned(reason="duplicate"), "allocation_occupied"),
    (planned(reason="no_new_longs"), "market"),
    (planned(reason=None), "allocation_unknown"),
])
def test_a_constructed_plan_is_placed_by_the_combined_allocations_own_answer(plan_, stage):
    row = {"ticker": "X", "grade_mechanical": "A", "grade": "A", "vetoes": [], "review_selection": selected(),
           "claude": accepted_reader("A"), "plan": plan_}
    assert funnel.reaction_stage(row, GREEN, {}, []) == stage
    assert funnel.anticipation_stage({"ticker": "X", "plan": plan_}, GREEN, {}) == stage


def test_a_plan_from_before_the_allocation_block_is_placed_by_the_cash_budget_and_the_trade_list():
    row = {"ticker": "X", "grade_mechanical": "A", "grade": "A", "vetoes": [], "review_selection": selected(),
           "claude": accepted_reader("A")}
    legacy = {k: v for k, v in planned().items() if k != "allocation"}
    budget = {"cut": [{"ticker": "X", "setup_kind": "burst", "kind": "slot_cap", "reason": "the cap"}]}
    assert funnel.reaction_stage({**row, "plan": legacy}, GREEN, budget, []) == "allocation_slot"
    withheld = {"cut": [{"ticker": "X", "setup_kind": "burst", "kind": "withheld", "reason": "the stop rule"}]}
    assert funnel.reaction_stage({**row, "plan": legacy}, GREEN, withheld, []) == "geometry"
    assert funnel.reaction_stage({**row, "plan": {**legacy, "event_risk": {"blocked": True}}}, GREEN, withheld, []) == "event"
    # a cut filed under the other setup kind is not this plan's
    other = {"cut": [{"ticker": "X", "setup_kind": "anticipation", "kind": "slot_cap", "reason": "the cap"}]}
    assert funnel.reaction_stage({**row, "plan": legacy}, GREEN, other, ["X"]) == "ticket"
    assert funnel.reaction_stage({**row, "plan": legacy}, GREEN, {}, []) == "allocation_unknown"
    assert funnel.reaction_stage({**row, "plan": {**legacy, "eligible": False}}, GREEN, {}, []) == "geometry"
    assert funnel.reaction_stage({**row, "plan": {**legacy, "shares": 0}}, GREEN, {}, []) == "sizing"
    assert funnel.reaction_stage({**row, "plan": {**legacy, "action": "no_new_longs"}}, GREEN, {}, []) == "market"
    # and an anticipation plan from before the block is a ticket by the record's own old
    # definition -- eligible, an order action, a whole share -- never by the trade list
    assert funnel.anticipation_stage({"ticker": "X", "plan": legacy}, GREEN, {}) == "ticket"
    assert funnel.anticipation_stage({"ticker": "X", "plan": {**legacy, "shares": 0}}, GREEN, {}) == "sizing"
    assert funnel.anticipation_stage({"ticker": "X", "plan": {**legacy, "eligible": False}}, GREEN, {}) == "geometry"
    assert funnel.anticipation_stage({"ticker": "X", "plan": legacy}, GREEN, other) == "allocation_slot"


def test_a_record_whose_rules_name_no_grades_is_unknown_never_guessed():
    data = {"rules": {"pipeline": {}}, "breadth": {"regime": {"verdict": "green"}},
            "bursts": [{"ticker": "X", "grade_mechanical": "A+", "grade": "A+", "vetoes": []}],
            "watchlist": {"top": [{"ticker": "Y", "plan": planned(admitted=True)}], "counts": {}},
            "cash_budget": {}, "trades": ["X"]}
    assert funnel.admitted_grades(data) is None
    block = funnel.build(data)
    assert block["admitted_grades"] is None
    assert block["reaction"]["stages"]["unknown"] == 1 and block["anticipation"]["stages"]["unknown"] == 1
    assert block["anticipation"]["counts"] == {k: None for k in funnel.WATCH_COUNTS}
    assert "Anticipation: 1 listed, 0 tickets." in block["sentence"]


def test_potentially_usable_counts_the_names_past_the_grade_and_the_veto_and_nothing_later():
    """A vetoed name in the band is not usable; a name past both gates is,
    whatever the review or the plan then did to it."""
    rules = {"pipeline": {"trade_grades": ["A+", "A"], "yellow_grades": ["A+"]}, "funnel": dict(funnel.RULES)}
    data = {"rules": rules, "breadth": {"regime": {"verdict": "green"}}, "cash_budget": {}, "trades": [],
            "watchlist": {"top": [], "counts": {"momentum": 1, "quiet": 1, "admitted": 0, "top": 0, "also_quiet": 0}},
            "bursts": [
                {"ticker": "VET", "grade_mechanical": "A", "grade": "A", "vetoes": ["up_days"], "claude": None,
                 "review_selection": unselected("grade_not_admitted", "quality_veto")},
                {"ticker": "LOW", "grade_mechanical": "B", "grade": "B", "vetoes": [], "claude": None,
                 "review_selection": unselected("grade_not_admitted")},
                {"ticker": "DWN", "grade_mechanical": "A+", "grade": "C", "vetoes": [], "claude": accepted_reader("C"),
                 "review_selection": selected()},
                {"ticker": "BUD", "grade_mechanical": "A", "grade": "A", "vetoes": [], "claude": None,
                 "review_selection": unselected()},
            ]}
    block = funnel.build(data)
    assert block["reaction"]["potentially_usable"] == 2
    assert [r["stage"] for r in block["reaction"]["rows"]] == ["veto", "grade", "review_downgraded", "review_budget"]
    assert block["reaction"]["stages"]["veto"] == 1 and block["reaction"]["stages"]["grade"] == 1
    # the veto is read after the grade: a vetoed name below the band is a grade stop
    data["bursts"][0]["grade_mechanical"] = data["bursts"][0]["grade"] = "B"
    assert funnel.build(data)["reaction"]["rows"][0]["stage"] == "grade"
    assert funnel.faults({**data, "funnel": funnel.build(data)}) == []


def test_the_admitted_grades_are_the_regimes_through_the_one_shared_rule():
    rules = {"rules": {"pipeline": {"trade_grades": ["A+", "A"], "yellow_grades": ["A+"]}}}
    for verdict, expected in (("green", ("A+", "A")), ("yellow", ("A+",)), ("red", ())):
        data = {**rules, "breadth": {"regime": {"verdict": verdict}}}
        assert funnel.admitted_grades(data) == reader_coverage.admitted(verdict, ["A+", "A"], ["A+"]) == expected


def test_the_sentence_is_counts_and_labels_alone():
    block = funnel.build(load(PAGE / "full.json"))
    s = block["sentence"]
    assert s.startswith("Candidate funnel under a GREEN market: 6 reaction candidates discovered, 4 potentially usable")
    assert "1 reaction ticket." in s and "1 ticket withheld: stop rule at the limit" in s and "2 slot cap" in s
    assert "Listed setups stopped at: 1 slot cap." in s
    assert s.endswith("establishes no entry.")
    one = copy.deepcopy(block)
    one["reaction"]["discovered"] = 1
    assert "1 reaction candidate discovered" in funnel.sentence(one)
    # nothing but the block's own words reaches the sentence: every label it uses is the module's
    for stage, n in block["reaction"]["stages"].items():
        assert (funnel.LABELS[stage] in s) == bool(n) or stage == "ticket", stage


# ---------------------------------------------------------- the validator ----
def test_the_validator_refuses_a_block_the_record_does_not_re_derive():
    data = load(PAGE / "full.json")
    for mutate, fault in (
        (lambda d: d["funnel"]["reaction"]["stages"].__setitem__("ticket", 2), "funnel is not the record's own"),
        (lambda d: d["funnel"]["reaction"]["rows"].pop(), "funnel is not the record's own"),
        (lambda d: d["funnel"]["anticipation"]["rows"][0].__setitem__("stage", "ticket"), "funnel is not the record's own"),
        (lambda d: d["funnel"].__setitem__("sentence", "all clear"), "funnel is not the record's own"),
        (lambda d: d["funnel"]["labels"].__setitem__("ticket", "order"), "funnel is not the record's own"),
        (lambda d: d["funnel"]["reaction"].__setitem__("potentially_usable", 6), "funnel is not the record's own"),
        (lambda d: d.__setitem__("funnel", None), "funnel block missing"),
    ):
        forged = copy.deepcopy(data)
        mutate(forged)
        assert funnel.faults(forged) == [fault], fault
        with pytest.raises(ValueError, match=fault.replace("'", ".")):
            report.validate(forged)
    # the record's own block passes, and so does a block whose record moved WITH it
    moved = copy.deepcopy(data)
    moved["trades"] = []
    for b in moved["bursts"]:
        if b.get("plan") and b["plan"]["allocation"]["admitted"]:
            b["plan"]["allocation"] = {**b["plan"]["allocation"], "admitted": False, "reason": "slot_cap"}
    moved["funnel"] = funnel.build(moved)
    assert funnel.faults(moved) == []


def test_a_record_under_older_rules_is_not_asked_for_a_block():
    for path in LEGACY.values():
        data = load_gz(path)
        assert "funnel" not in data["rules"] and "funnel" not in data
        assert funnel.faults(data) == []
    # and a block an older record happens to carry is checked only once its rules write one
    data = load(PAGE / "full.json")
    del data["rules"]["funnel"]
    data["funnel"]["sentence"] = "anything"
    assert funnel.faults(data) == []


def test_the_block_is_composed_last_off_the_cleaned_record_by_the_report_builder():
    from tools import make_fixture
    data = load(PAGE / "full.json")
    again = report.build(data["run"], data["account"], data["rules"], data["breadth"], data["bursts"], data["trades"],
                         data["beyond_cap"], data["cash_budget"], data["watchlist"], data["open_plans"],
                         data["scorecard"], data["nights"], data["generated"], observations=data["observations"])
    assert again["funnel"] == data["funnel"]
    assert "funnel" in report.CONTRACT and set(again["_contract"]) == set(again)
    assert make_fixture.VARIANTS  # the generator is what wrote the fixtures this file reads


def test_the_mail_prints_the_records_own_sentence_and_nothing_else_of_it():
    data = load(PAGE / "full.json")
    html = report.digest_html(data)
    assert report.esc(data["funnel"]["sentence"]) in html
    assert "where the candidates stopped" in html
    without = copy.deepcopy(data)
    del without["funnel"]
    assert "where the candidates stopped" not in report.digest_html(without)


# ------------------------------------------------------- real publications ----
@pytest.mark.parametrize("session", sorted(LEGACY))
def test_a_retained_red_publication_stops_every_name_at_the_market(session):
    data = load_gz(LEGACY[session])
    assert data["run"]["session"] == session and data["breadth"]["regime"]["verdict"] == "red"
    block = funnel.build(data)
    assert block["admitted_grades"] == []
    assert block["reaction"]["stages"]["market"] == block["reaction"]["discovered"] == len(data["bursts"]) > 400
    assert block["anticipation"]["stages"]["market"] == block["anticipation"]["listed"] == len(data["watchlist"]["top"]) == 5
    assert block["reaction"]["potentially_usable"] == 0
    assert "stopped at: " + str(len(data["bursts"])) + " " + funnel.LABELS["market"] in block["sentence"]


def test_the_retained_9_october_publication_is_read_for_what_it_recorded(production):
    data = production
    assert data["run"]["session"] == "2026-10-09" and data["breadth"]["regime"]["verdict"] == "yellow"
    assert "funnel" not in data["rules"] and funnel.faults(data) == []
    block = funnel.build(data)
    assert block["admitted_grades"] == ["A+"]
    r = block["reaction"]
    assert r["discovered"] == 479 and r["potentially_usable"] == 0
    assert r["by_mechanical_grade"] == {"A+": 0, "A": 53, "B": 112, "C": 89, "skip": 225}
    assert r["stages"]["grade"] == 479 and sum(r["stages"].values()) == 479
    a = block["anticipation"]
    assert {row["ticker"]: row["stage"] for row in a["rows"]} == \
        {"MG": "event", "KE": "geometry", "ZIM": "event", "SN": "geometry", "PSNL": "geometry"}
    assert a["counts"] == {"momentum": 768, "quiet": 239, "admitted": 16, "top": 5, "also_quiet": 10}
    assert "479 reaction candidates discovered, 0 potentially usable" in block["sentence"]
    assert "2 known corporate event, 3 ticket withheld: stop rule at the limit" in block["sentence"]
