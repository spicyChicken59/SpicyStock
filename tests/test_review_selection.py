"""Review capacity is useful coverage and bounded research, never permission."""
from copy import deepcopy
import hashlib
import gzip
import json
from pathlib import Path

import pytest

from src import pipeline, plan, provenance, reader_coverage, review_selection as selection
from tests.test_pipeline import market, claude, evening, a_plus_frame

SESSION = "2026-09-10"


def candidate(ticker, *, grade="A+", score=9, shares=1, eligible=True, action="buy_at_open"):
    return {"ticker": ticker, "grade": grade, "grade_mechanical": grade, "score": score,
            "vetoes": [], "plan": {"eligible": eligible, "shares": shares, "action": action}}


def choose(rows, *, admitted=("A+", "A"), budget=12, session=SESSION):
    return selection.select(rows, session, max_reads=budget, admitted=admitted, research_grades=("A+", "A"))


def test_feasible_lower_rank_precedes_impossible_higher_rank_without_changing_either():
    impossible = candidate("IMP", score=10, shares=0)
    feasible = candidate("FIT", grade="A", score=8)
    before = deepcopy([impossible, feasible])
    decisions, selected = choose([impossible, feasible], budget=1)
    assert selected == ["FIT"]
    assert decisions["FIT"]["purpose"] == "opportunity"
    assert decisions["IMP"]["blockers"] == ["no_whole_share"]
    assert [impossible, feasible] == before


@pytest.mark.parametrize("count", [1, 10, 11, 12, 15])
def test_research_never_displaces_feasible_coverage_and_does_not_fill_the_budget(count):
    feasible = [candidate(f"F{i:02}", score=9) for i in range(count)]
    research = [candidate(f"R{i:02}", score=10, shares=0) for i in range(15)]
    decisions, selected = choose(research + list(reversed(feasible)))
    assert selected[:min(count, 12)] == [r["ticker"] for r in feasible[:12]]
    assert len(selected) == min(count, 12) + min(2, max(0, 12 - count))
    assert sum(d["selected"] and d["feasible"] for d in decisions.values()) == min(count, 12)


@pytest.mark.parametrize("admitted", [(), ("A+",)])
def test_zero_feasible_uses_two_near_admission_research_reads_in_red_or_yellow(admitted):
    rows = [candidate(f"R{i:02}", grade="A") for i in range(20)]
    decisions, selected = choose(rows, admitted=admitted)
    assert len(selected) == 2 and selected[0] == "R00"
    assert {decisions[t]["purpose"] for t in selected} == {"research_ranked", "research_rotating"}
    assert all(d["blockers"] == ["grade_not_admitted"] for d in decisions.values())


def test_empty_research_pool_does_not_consume_capacity():
    decisions, selected = choose([candidate("LOW", grade="B")])
    assert selected == [] and decisions["LOW"]["purpose"] == "outside_research_pool"
    assert choose([]) == ({}, [])


@pytest.mark.parametrize("mutation,reason", [
    (lambda r: r.update(grade_mechanical="B"), "grade_not_admitted"),
    (lambda r: r.update(vetoes=["thin"]), "quality_veto"),
    (lambda r: r.update(plan=None), "preview_unavailable"),
    (lambda r: r["plan"].update(event_risk={"blocked": True}), "known_event"),
    (lambda r: r["plan"].update(eligible=False), "plan_withheld"),
    (lambda r: r["plan"].update(shares=0), "no_whole_share"),
    (lambda r: r["plan"].update(shares=True), "no_whole_share"),
    (lambda r: r["plan"].update(action="no_order"), "no_order"),
])
def test_each_independent_blocker_prevents_opportunity_selection(mutation, reason):
    row = candidate("CHECK")
    mutation(row)
    decisions, _ = choose([row])
    assert decisions["CHECK"]["feasible"] is False
    assert decisions["CHECK"]["blockers"] == [reason]
    assert decisions["CHECK"]["purpose"] != "opportunity"


def test_one_whole_share_boundary_is_not_rounded_up_and_positive_shares_are_feasible():
    rows = [candidate("ZERO", shares=0), candidate("ONE", shares=1)]
    decisions, selected = choose(rows)
    assert selected[0] == "ONE" and decisions["ONE"]["feasible"]
    assert decisions["ZERO"]["blockers"] == ["no_whole_share"]


def test_research_rotation_uses_archived_session_seed_and_survives_input_permutation():
    rows = [candidate(f"R{i:02}", shares=0) for i in range(20)]
    decisions, selected = choose(rows)
    expected = min((r["ticker"] for r in rows[1:]), key=lambda t:
                   (hashlib.sha256(f"{selection.POLICY}|{SESSION}|{t}".encode()).hexdigest(), t))
    assert selected == ["R00", expected]
    assert choose(list(reversed(rows))) == (decisions, selected)
    assert len(set(selected)) == len(selected)
    # the seed is the POLICY the selection runs under, so a version-1 record replayed
    # under its own policy rotates as it did: the pick the 14 Sep session had on 10 Oct
    v1 = selection.select(rows, "2026-09-14", max_reads=12, admitted=("A+", "A"), research_grades=("A+", "A"),
                          policy=selection.POLICY_V1)
    assert v1[1] == ["R00", "R11"]
    assert all(d["policy"] == selection.POLICY_V1 for d in v1[0].values())
    assert choose(rows, session="2026-09-14")[1][0] == "R00"
    with pytest.raises(ValueError, match="unknown review selection policy"):
        selection.select(rows, SESSION, max_reads=12, admitted=("A+", "A"), research_grades=("A+", "A"), policy="other")


@pytest.mark.parametrize("budget", [0, 1, 2])
def test_research_respects_even_a_budget_smaller_than_its_cap(budget):
    _, selected = choose([candidate(str(i), shares=0) for i in range(5)], budget=budget)
    assert len(selected) == budget


def test_duplicate_symbol_cannot_consume_two_reviews():
    with pytest.raises(ValueError, match="duplicate review candidate"):
        choose([candidate("DUP"), candidate("DUP")])


def test_receipt_reconciles_actual_attempts_and_smaller_sample_refusal_under_the_archived_floor():
    rows = [candidate("AAA", grade="A"), candidate("BBB", grade="A")]
    rows[0]["claude"] = {"source": "claude", "grade": "A", "attempts": [{}, {}]}
    from src import grader, reader_authority
    rows[1]["claude"] = {"source": "fallback", "error": grader._error_text(reader_authority.ReaderAuthorityError("refused")),
                         "attempts": [{}]}
    decisions, selected = choose(rows, admitted=("A+",))
    receipt = selection.receipt(rows, decisions, selected, SESSION, max_reads=12)
    assert (receipt["requested"], receipt["attempts"], receipt["unused_capacity"]) == (2, 3, 10)
    assert receipt["by_purpose"]["research_ranked"] == {
        "requested": 1, "accepted": 1, "unaccepted": 0, "refused": 0, "attempts": 2}
    assert receipt["by_purpose"]["research_rotating"] == {
        "requested": 1, "accepted": 0, "unaccepted": 1, "refused": 1, "attempts": 1}
    # the run's own rule: one refused research read of two is within the owner's floor
    reads = reader_coverage.reads(rows, admitted_grades=("A+",), refusal_fraction=pipeline.READER_REFUSAL_FRACTION,
                                  refusal_min=pipeline.READER_REFUSAL_MIN)
    assert (reads["refusal_limit"], reads["verdict"]) == (1, "tolerated"), reads
    # the fraction alone, as a record made before the floor reads it: the old partial night
    reads = reader_coverage.reads(rows, admitted_grades=("A+",), refusal_fraction=pipeline.READER_REFUSAL_FRACTION)
    assert (reads["refusal_limit"], reads["verdict"]) == (0, "partial"), reads


def test_pipeline_retains_selection_counts_and_binding(market, claude, fake_resend, tmp_path):
    rep, data, docs = evening(tmp_path, market)
    assert rep.published, rep.failure
    decisions, replayed = selection.replay(data)
    receipt = data["run"]["review_selection"]
    assert receipt == replayed
    assert receipt["selected"] == [{"ticker": "AAA", "purpose": "opportunity"}]
    assert receipt["attempts"] == len(claude.calls) == 1
    assert data["bursts"][0]["review_selection"] == decisions["AAA"]
    assert data["bursts"][0]["evidence"]["review_selection"] == decisions["AAA"]
    assert provenance.verify(data, objects=docs / "evidence")["status"] == "PASS"
    ledger, = (docs / "quality-ledger/v1").glob("*.json.gz")
    retained = json.loads(gzip.decompress(ledger.read_bytes()))["signal"]
    assert retained["review_selection"] == receipt
    assert retained["candidates"][0]["review_selection"] == decisions["AAA"]


def test_evening_spends_on_the_feasible_name_below_twelve_zero_share_names(market, claude,
        fake_alpaca, fake_resend, tmp_path):
    expensive = a_plus_frame()
    expensive.loc[:, ["Open", "High", "Low", "Close"]] *= 100
    symbols = [f"A{chr(65 + i)}X" for i in range(12)]
    for ticker in symbols:
        fake_alpaca.add_history(ticker, expensive)
    fake_alpaca.add_history("ZZZ", a_plus_frame())
    rep, data, _ = evening(tmp_path, [t for t in market if t != "AAA"] + symbols + ["ZZZ"])
    assert rep.published, rep.failure
    receipt = data["run"]["review_selection"]
    assert (receipt["feasible"], receipt["requested"], receipt["attempts"]) == (1, 3, 3)
    assert receipt["selected"][0] == {"ticker": "ZZZ", "purpose": "opportunity"}
    assert receipt["feasible_unselected"] == 0 and data["trades"] == ["ZZZ"]
    by_ticker = {r["ticker"]: r for r in data["bursts"]}
    assert all("no_whole_share" in by_ticker[t]["review_selection"]["blockers"] for t in symbols)
    assert sum(r["claude"] is not None for r in data["bursts"]) == len(claude.calls) == 3


def test_a_zero_research_pool_makes_no_chart_or_model_requests(market, claude, fake_alpaca,
                                                             fake_resend, tmp_path, monkeypatch):
    from tests.test_quality import frame, ideal_bars
    fake_alpaca.add_history("AAA", frame(ideal_bars(close_pos=0.55)))
    def no_chart(*args, **kwargs):
        raise AssertionError("unselected candidate rendered for the reader")
    monkeypatch.setattr(pipeline.charts, "render_chart", no_chart)
    rep, data, _ = evening(tmp_path, market)
    assert rep.published, rep.failure
    assert data["bursts"][0]["grade_mechanical"] == "B"
    assert claude.calls == [] and data["run"]["reads"]["verdict"] == "not_asked"
    assert data["run"]["review_selection"]["requested"] == 0 and not data["trades"]
    assert not any(p["kind"] == "chart_missing" for p in rep.problems)
    row = data["bursts"][0]
    assert row["evidence"]["review_selection"] == row["review_selection"]
    assert row["review_selection"]["selected"] is False and "reader_input" not in row["evidence"]
    assert provenance.verify(data, require_sources=False)["status"] == "PASS"


@pytest.mark.parametrize("layer", ["row", "evidence", "run", "resealed_decision", "resealed_counts"])
def test_selection_tampering_is_rejected_even_when_consistently_resealed(layer, market, claude,
                                                                       fake_resend, tmp_path):
    rep, data, _ = evening(tmp_path, market)
    assert rep.published, rep.failure
    row = data["bursts"][0]
    if layer in ("row", "resealed_decision"):
        row["review_selection"]["blockers"] = ["no_whole_share"]
    elif layer == "evidence":
        row["evidence"]["review_selection"]["selected"] = False
    else:
        data["run"]["review_selection"]["attempts"] += 1
    if layer == "resealed_decision":
        row["evidence"]["review_selection"] = deepcopy(row["review_selection"])
        from tests.test_provenance import reseal
        reseal(row)
    if layer == "resealed_counts":
        context = provenance.digest(provenance.context(data))
        data["run"]["evidence"]["context_sha256"] = context
        from tests.test_provenance import reseal
        for candidate_row in data["bursts"] + data["watchlist"]["top"]:
            candidate_row["evidence"]["context_sha256"] = context
            reseal(candidate_row)
    result = provenance.verify(data, require_sources=False)
    assert result["status"] == "FAIL", result


def test_legacy_publication_keeps_its_original_provenance_contract():
    root = Path(__file__).resolve().parents[1]
    data = json.loads((root / "tests/fixtures/morning/full-publication.json").read_bytes())
    assert "review_selection" not in data["rules"]
    assert provenance.verify(data, require_sources=False)["status"] == "PASS"


@pytest.mark.parametrize("changed_module", ["planner", "selector"])
def test_archived_policy_integrity_remains_readable_when_current_implementation_cannot_replay(
        changed_module, market, claude, fake_resend, tmp_path, monkeypatch):
    rep, data, docs = evening(tmp_path, market)
    assert rep.published, rep.failure
    if changed_module == "planner":
        monkeypatch.setitem(plan.RULES, "plan.max_stop_pct", 99)
    else:
        monkeypatch.setitem(selection.RULES, "review_selection.policy", "future_implementation_v2")
    for options in ({"require_sources": False}, {"objects": docs / "evidence"}):
        result = provenance.verify(data, **options)
        assert result["status"] == "PARTIAL" and result["breaks"] == [], result
        assert any("archived rules need a compatible verifier" in reason for reason in result["missing"])
        assert len(result["checked"]) == len(data["bursts"]) + len(data["watchlist"]["top"])
    data["bursts"][0]["review_selection"]["selected"] = False
    result = provenance.verify(data, require_sources=False)
    assert result["status"] == "FAIL" and any("review selection evidence mismatch" in r for r in result["breaks"])


def test_selection_rules_are_archived_and_keep_existing_budget_and_grade_authority():
    from src import universe
    rules = pipeline.build_rules(universe.Universe(["AAA"], {}, {}, "explicit", None, {}, "test"))
    assert rules["review_selection"]["research_max"] == 2
    assert rules["review_selection"]["policy"] == "account_feasible_first_research_v2" == selection.POLICY
    assert rules["review_selection"]["version"] == 2
    assert rules["review_selection"]["research_pool"] == "infeasible mechanical pipeline.trade_grades, discovery admitted"
    assert rules["pipeline"]["max_reads"] == 12
    assert rules["pipeline"]["reader_policy"] == "accepted_required_v1"
    assert rules["pipeline"]["trade_grades"] == ["A+", "A"]
    assert rules["pipeline"]["yellow_grades"] == ["A+"]


def test_documents_name_the_archived_research_budget_and_selection_boundary():
    root = Path(__file__).resolve().parents[1]
    for name in ("README.md", ".env.example", "knowledge/method.md"):
        content = (root / name).read_text()
        assert f"at most {selection.RESEARCH_MAX}" in content.lower()
    assert selection.POLICY in (root / "README.md").read_text()
    assert selection.POLICY in (root / "knowledge/method.md").read_text()


# ------------------------------------------------- the discovery admission ----
def dollar_only(ticker, *, expansion, grade="A", score=8):
    """A dollar-only candidate as the pipeline writes it: its admission block
    read off the route and the checklist's RE and VOL (src/admission.py)."""
    from src import admission
    checks = [{"letter": "RE", "passed": expansion, "pass": expansion}, {"letter": "VOL", "passed": expansion, "pass": expansion}]
    row = {**candidate(ticker, grade=grade, score=score), "scan": "dollar", "quality": {"checks": checks}}
    row["admission"] = admission.block(row)
    return row


def test_a_dollar_only_name_without_expansion_is_blocked_at_the_route_and_is_not_research():
    """The second policy: a name the discovery admission stopped is blocked as
    route_not_admitted -- never feasible, never research -- so no read is
    spent on a name that cannot be planned; the same name on a
    range-expansion, higher-volume day is as feasible as any 4% burst."""
    stopped = dollar_only("DNO", expansion=False, score=10)
    shown = dollar_only("DEX", expansion=True, score=9)
    decisions, selected = choose([stopped, shown, candidate("FIT", grade="A", score=8)])
    assert decisions["DNO"] == {"policy": selection.POLICY, "feasible": False, "blockers": ["route_not_admitted"],
                                "research_pool": False, "selected": False, "purpose": "outside_research_pool"}
    assert decisions["DEX"]["feasible"] is True and decisions["DEX"]["blockers"] == []
    assert selected == ["DEX", "FIT"], selected
    # with every other name infeasible, the stopped A+ is still not a research read
    decisions, selected = choose([stopped, candidate("R00", grade="A", shares=0)], admitted=())
    assert selected == ["R00"] and decisions["DNO"]["purpose"] == "outside_research_pool"
    # the route blocker sits after the grade and the veto, in the receipt's order
    vetoed = {**stopped, "vetoes": ["up_days"]}
    assert selection.blockers(vetoed, ("A+",)) == ["grade_not_admitted", "quality_veto", "route_not_admitted"]
    assert selection.BLOCKERS.index("route_not_admitted") == selection.BLOCKERS.index("quality_veto") + 1
    receipt = selection.receipt([stopped, shown], *choose([stopped, shown]), SESSION, max_reads=12)
    assert receipt["version"] == 2 and receipt["policy"] == selection.POLICY
    assert receipt["blockers"]["route_not_admitted"] == 1 and set(receipt["blockers"]) == set(selection.BLOCKERS)


def test_version_one_is_replayed_under_its_own_policy_with_no_route_blocker():
    """A record from 10 Oct to 3 Nov 2026 archived version 1: its rows carry no
    admission block and its receipt counted seven blockers. Replayed under its
    own policy it reproduces exactly; a row that does carry a block is read as
    version 1 read it, by its grade and veto alone."""
    stopped = dollar_only("DNO", expansion=False)
    decisions, selected = selection.select([stopped], SESSION, max_reads=12, admitted=("A+", "A"),
                                           research_grades=("A+", "A"), policy=selection.POLICY_V1)
    assert decisions["DNO"]["blockers"] == [] and decisions["DNO"]["feasible"] is True and selected == ["DNO"]
    receipt = selection.receipt([stopped], decisions, selected, SESSION, max_reads=12, policy=selection.POLICY_V1)
    assert receipt["version"] == 1 and receipt["policy"] == selection.POLICY_V1
    assert list(receipt["blockers"]) == list(selection.BLOCKERS_BY_POLICY[selection.POLICY_V1]) and "route_not_admitted" not in receipt["blockers"]
    with pytest.raises(ValueError, match="unknown review selection policy"):
        selection.receipt([stopped], decisions, selected, SESSION, max_reads=12, policy="other")
    # the frozen version-1 rules are what every such record archived, and nothing else is replayable
    assert selection.supported(selection.RULES_V1) and selection.supported({k.partition(".")[2]: v for k, v in selection.RULES.items()})
    assert not selection.supported({**selection.RULES_V1, "research_max": 3}) and not selection.supported("rules") and not selection.supported(None)
    assert selection.RULES_V1["policy"] == selection.POLICY_V1 and selection.RULES_V1["version"] == 1
    assert selection.RULES_V1["research_pool"] == "infeasible mechanical pipeline.trade_grades"


def test_the_retained_version_one_publication_replays_exactly_and_still_verifies():
    """The 9 October 2026 publication (the stop-research fixture, its exact
    bytes) archived version 1: the current module replays every decision and
    the receipt byte for byte under the frozen rules, and the verifier keeps
    its PASS -- a record is never read under a policy it did not archive."""
    root = Path(__file__).resolve().parents[1]
    data = json.loads(gzip.decompress((root / "tests/fixtures/stop-research/current-publication.json.gz").read_bytes()))
    assert data["rules"]["review_selection"] == selection.RULES_V1
    decisions, receipt = selection.replay(data)
    assert receipt == data["run"]["review_selection"]
    assert all(decisions[b["ticker"]] == b["review_selection"] for b in data["bursts"])
    assert provenance.verify(data, require_sources=False)["status"] == "PASS"
    # a record archiving rules this module does not replay is refused by name, never guessed at
    foreign = deepcopy(data)
    foreign["rules"]["review_selection"]["policy"] = "future_implementation_v3"
    with pytest.raises(ValueError, match="not ones this module replays"):
        selection.replay(foreign)
