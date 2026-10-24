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
import re
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


def test_a_block_written_under_other_stages_is_read_for_what_it_recorded_and_held_to_nothing():
    """Every publication before 24 Oct 2026 archived funnel version 1, whose
    stages had no word for a request the API refused: it is not asked for
    version 2's block, and its own block is never compared against stages it
    could not write. A record under the current version is held as before."""
    data = load(FIXTURES[0])
    assert funnel.faults(data) == []
    older = json.loads(json.dumps(data))
    older["rules"]["funnel"]["version"] = funnel.VERSION - 1
    assert funnel.faults(older) == [], "a record archived under older stages is not held to these"
    del older["funnel"]
    assert funnel.faults(older) == []
    current = json.loads(json.dumps(data))
    del current["funnel"]
    assert funnel.faults(current) == ["funnel block missing"]
    current = json.loads(json.dumps(data))
    current["funnel"]["reaction"]["stages"]["review_request"] += 1
    assert funnel.faults(current) == ["funnel is not the record's own"]


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


def test_a_holiday_run_preserves_the_previous_publication_with_its_block():
    """The closed fixture is the Labor Day run over the 4 September docs, which
    the known-holiday rule preserves byte for byte: the record it carries is the
    open night's own, block included, and nothing is re-derived under the
    holiday. (The pipeline's carried-night branch, which would re-derive a
    block over the previous night's bursts, is not what a known holiday takes.)"""
    closed = load(PAGE / "closed.json")
    assert closed["run"]["session"] == "2026-09-04" and closed["run"]["session_state"] == "open"
    assert closed["run"]["expected_session"] == closed["run"]["session"]
    assert closed["funnel"] == funnel.build(closed) and funnel.faults(closed) == []


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
    # the grader's own "not graded" row is a name it was handed and never read: unselected, not a transport failure
    row["claude"] = {"source": grader.SOURCE_NOT_GRADED, "grade": None, "error": None}
    assert reader_coverage.state(row) == reader_coverage.NOT_SELECTED
    assert funnel.reaction_stage(row, GREEN, {}, []) == "review_unselected"


def test_a_reviewed_candidate_without_an_accepted_reading_is_placed_by_the_readers_cause():
    base = {"ticker": "X", "grade_mechanical": "A", "grade": "A", "vetoes": [], "review_selection": selected()}
    cases = {
        grader.error_label(reader_authority.ReaderAuthorityError) + ": evidence outside criterion authority": "review_refused",
        grader.error_label(grader.DiscoveryConflict) + ": contradicts the discovery contract": "review_refused",
        grader.error_label(grader.ScoreFormatError) + ": no score": "review_format",
        "anthropic.AuthenticationError: " + grader.FATAL_AUTH_MARKERS[0]: "review_account",
        "anthropic.BadRequestError: " + grader.FATAL_CREDIT_MARKERS[0]: "review_credit",
        "anthropic.BadRequestError: Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', "
        "'message': 'temperature: Extra inputs are not permitted'}, 'request_id': 'req_1'}": "review_request",
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
    # an empty error string names no error
    assert funnel.reaction_stage({**kept, "evidence": {"planning": {"error": ""}}}, GREEN, {}, []) == "plan_unavailable"


def test_a_listed_setup_without_a_plan_names_the_planners_error_or_the_missing_plan():
    """``make_watchlist`` writes ``plan: None`` beside the planner's error when
    a listed name's plan raised; the funnel names that, after the market gate."""
    assert funnel.anticipation_stage({"ticker": "Y", "plan": None, "evidence": {"planning": {"error": "KeyError: 'Low'"}}}, GREEN, {}) == "plan_error"
    assert funnel.anticipation_stage({"ticker": "Y", "plan": None}, GREEN, {}) == "plan_unavailable"
    assert funnel.anticipation_stage({"ticker": "Y", "plan": None, "evidence": {"planning": {"error": ""}}}, GREEN, {}) == "plan_unavailable"
    assert funnel.anticipation_stage({"ticker": "Y", "plan": None, "evidence": {"planning": {"error": "KeyError: 'Low'"}}}, (), {}) == "market"


def test_a_burst_row_without_a_mechanical_grade_is_unknown_never_placed_at_the_grade():
    for mechanical in (None, 7, ["A"], {"grade": "A"}):
        row = {"ticker": "X", "grade": "A", "vetoes": [], "claude": accepted_reader("A"), "review_selection": selected(),
               "plan": planned(admitted=True)}
        if mechanical is not None:
            row["grade_mechanical"] = mechanical
        assert funnel.reaction_stage(row, GREEN, {}, ["X"]) == "unknown", mechanical
        assert funnel.reaction_stage(row, (), {}, ["X"]) == "market", mechanical
    block = funnel.build({"rules": {"pipeline": {"trade_grades": ["A+", "A"], "yellow_grades": ["A+"]}},
                          "breadth": {"regime": {"verdict": "green"}}, "cash_budget": {}, "trades": [],
                          "watchlist": {"top": [], "counts": {}},
                          "bursts": [{"ticker": "X", "grade": "A", "vetoes": []}]})
    assert block["reaction"]["stages"]["unknown"] == 1 and block["reaction"]["potentially_usable"] == 0
    assert block["reaction"]["by_mechanical_grade"] == {g: 0 for g in grader.GRADES}


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
    # a cut kind the module does not know is an allocation outcome it cannot read, never a guess
    strange = {"cut": [{"ticker": "X", "setup_kind": "burst", "kind": "something_new", "reason": "?"}]}
    assert funnel.reaction_stage({**row, "plan": legacy}, GREEN, strange, []) == "allocation_unknown"
    # a legacy name in the trade list is a ticket only with an order action on its own plan
    assert funnel.reaction_stage({**row, "plan": {**legacy, "action": "refused"}}, GREEN, {}, ["X"]) == "geometry"
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


def test_a_record_whose_regime_is_not_a_verdict_is_unknown_never_green():
    """``reader_coverage.admitted`` answers the trade grades for any verdict it
    does not know; the funnel asks it only for a verdict the record names, so a
    missing or unreadable regime is unknown and never read as GREEN."""
    rules = {"pipeline": {"trade_grades": ["A+", "A"], "yellow_grades": ["A+"]}}
    row = {"ticker": "X", "grade_mechanical": "A+", "grade": "A+", "vetoes": [], "claude": accepted_reader("A+"),
           "review_selection": selected(), "plan": planned(admitted=True)}
    for breadth in ({}, {"regime": {}}, {"regime": {"verdict": None}}, {"regime": {"verdict": "purple"}},
                    {"regime": {"verdict": 5}}, {"regime": "red"}, None):
        data = {"rules": rules, "breadth": breadth, "bursts": [row], "cash_budget": {}, "trades": ["X"],
                "watchlist": {"top": [{"ticker": "Y", "plan": planned(admitted=True)}], "counts": {}}}
        assert funnel.admitted_grades(data) is None, breadth
        block = funnel.build(data)
        assert block["admitted_grades"] is None and block["reaction"]["potentially_usable"] == 0, breadth
        assert [r["stage"] for r in block["reaction"]["rows"]] == ["unknown"], breadth
        assert [r["stage"] for r in block["anticipation"]["rows"]] == ["unknown"], breadth
        assert funnel.faults({**data, "rules": {**rules, "funnel": dict(funnel.RULES)}, "funnel": block}) == []
    # the same record under a verdict the rules name is the shared rule's answer
    data["breadth"] = {"regime": {"verdict": "green"}}
    assert funnel.build(data)["reaction"]["rows"][0]["stage"] == "ticket"


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


def stopped_segments(sentence, lead, tail):
    """The "N label" segments of one stopped-at clause, split only where a
    count follows the comma: a label may itself carry a comma."""
    m = re.search(re.escape(lead) + r" (.*?)\. " + re.escape(tail), sentence)
    return re.split(r", (?=\d+ )", m.group(1)) if m else []


def expected_segments(stages):
    return [f"{n} {funnel.LABELS[k]}" for k, n in stages.items() if n and k != "ticket"]


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
    # nothing but the block's own words reaches the sentence: each stopped-at clause is
    # exactly the block's nonzero stages, each "N label", in stage order -- read as
    # segments, because one label is a prefix of another ("known corporate event")
    assert stopped_segments(s, "Reaction candidates stopped at:", "Anticipation:") == expected_segments(block["reaction"]["stages"])
    assert stopped_segments(s, "Listed setups stopped at:", "A stage is") == expected_segments(block["anticipation"]["stages"])
    preview = copy.deepcopy(block)
    preview["reaction"]["stages"].update(allocation_slot=0, preview_event=1, event=1)
    preview["anticipation"]["stages"].update(allocation_slot=0, review_unknown=0, unknown=1)
    s2 = funnel.sentence(preview)
    assert stopped_segments(s2, "Reaction candidates stopped at:", "Anticipation:") == expected_segments(preview["reaction"]["stages"])
    assert stopped_segments(s2, "Listed setups stopped at:", "A stage is") == expected_segments(preview["anticipation"]["stages"])
    # a block with nothing stopped carries no stopped-at clause at all
    quiet = copy.deepcopy(block)
    for family in ("reaction", "anticipation"):
        quiet[family]["stages"] = {k: 0 for k in quiet[family]["stages"]}
    assert "stopped at:" not in funnel.sentence(quiet)


def test_the_sentence_names_the_watchlists_counts_only_when_every_one_is_recorded():
    block = funnel.build(load(PAGE / "full.json"))
    c, listed = block["anticipation"]["counts"], block["anticipation"]["listed"]
    assert f"Anticipation: {c['momentum']} momentum names, {c['quiet']} quiet, {c['admitted']} passing the coil checks, {listed} listed, " in block["sentence"]
    partial = copy.deepcopy(block)
    partial["anticipation"]["counts"]["quiet"] = None
    assert "momentum" not in funnel.sentence(partial) and f"Anticipation: {listed} listed, " in funnel.sentence(partial)
    flagged = copy.deepcopy(block)
    flagged["anticipation"]["counts"]["admitted"] = True
    assert "momentum" not in funnel.sentence(flagged)
    one = copy.deepcopy(block)
    one["anticipation"]["counts"].update(momentum=1, quiet=1, admitted=1)
    one["anticipation"]["stages"] = {k: 0 for k in one["anticipation"]["stages"]}
    one["anticipation"]["stages"]["ticket"] = 1
    assert f"Anticipation: 1 momentum name, 1 quiet, 1 passing the coil checks, {listed} listed, 1 ticket." in funnel.sentence(one)
    # a regime the record does not name is said so, never raised on
    for regime in (None, "", 5):
        unnamed = copy.deepcopy(block)
        unnamed["regime"] = regime
        assert funnel.sentence(unnamed).startswith("Candidate funnel under a market this record does not name: 6 reaction"), regime


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


def test_the_validator_names_a_block_it_cannot_re_derive_rather_than_raising(monkeypatch):
    data = load(PAGE / "full.json")

    def broken(_):
        raise KeyError("a field the record lacks")
    monkeypatch.setattr(funnel, "build", broken)
    assert funnel.faults(data) == ["funnel cannot be re-derived from this record"]
    with pytest.raises(ValueError, match="cannot be re-derived"):
        report.validate(data)


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
