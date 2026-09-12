"""The entry-limit study reads; it never rescues a ticket with a level the
bar does not support, never widens the ceiling, never rounds a stop past the
line, and never writes. Every number it uses is the production module's.

The study itself changes no rule: `src/plan.py` is untouched by it, and
these tests assert that too, so a future edit that quietly moved the
production ceiling would be caught here as well as in test_plan.py.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest

from src import pipeline, plan
from tools import entry_limit_study as study

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "page"


def bar(close: float, low: float, high: float) -> dict:
    """A burst bar as a record row carries one."""
    return {"ticker": "TEST", "close": close, "low": low, "high": high,
            "open": low, "prev_close": close * 0.95, "gain_pct": 5.0, "scan": "4pct"}


# ------------------------------------------------------- the ceiling ------
def test_the_ceiling_is_rounded_down_to_cents_never_up():
    for raw in (1.005, 2.6700000000000004, 99.999, 10.101, 0.019):
        rounded = study.floor_to_cents(raw)
        assert rounded <= raw + 1e-12, (raw, rounded)
        assert round(rounded * 100) == pytest.approx(rounded * 100, abs=1e-6)
        assert rounded > raw - 0.01


def test_the_rounded_ceiling_keeps_the_stop_inside_his_line():
    """Rounding DOWN is what makes this true: a ceiling rounded up would put
    the stop further than MAX_STOP_PCT under the price the order can fill at."""
    for close, low, high in ((100.0, 97.0, 101.0), (12.34, 12.01, 12.40),
                             (546.78, 531.56, 568.65), (3.21, 3.15, 3.30)):
        got = study.constrained_ceiling(close, low, high)
        if not got["basis"]:
            continue
        at_limit = plan._pct(100 * (got["limit"] - got["stop"]) / got["limit"])
        assert at_limit <= plan.MAX_STOP_PCT, (close, low, high, at_limit)


def test_the_proposal_never_widens_the_current_ceiling():
    for close, low, high in ((100.0, 99.5, 100.5), (100.0, 97.0, 101.0), (50.0, 49.9, 50.1)):
        got = study.constrained_ceiling(close, low, high)
        fixed = plan._at_pct(close, plan.ENTRY_ABOVE_PCT)
        assert got["fixed_limit"] == fixed
        if got["basis"]:
            assert got["limit"] <= fixed


def test_a_stop_already_inside_the_line_keeps_the_fixed_ceiling():
    """A bar tight enough that the low is within 0.16% of the close is the one
    shape the current rule admits at burst_low; the proposal must leave it
    where it is rather than narrow a ticket that already holds."""
    close = 100.0
    low = plan._money(plan._at_pct(close, plan.ENTRY_ABOVE_PCT) * (1 - plan.MAX_STOP_PCT / 100) + 0.01)
    got = study.constrained_ceiling(close, low, close + 0.02)
    assert got["basis"] == "burst_low"
    assert got["narrowed"] is False
    assert got["limit"] == plan._at_pct(close, plan.ENTRY_ABOVE_PCT)


# ------------------------------------------- the candidates, in order -----
def test_the_candidates_are_read_in_the_cascades_own_order():
    """burst_low is priority 1 in plan.burst_stop, so it is priority 1 here
    even though half_range sits higher and would permit a wider limit."""
    assert study.STRUCTURAL_BASES == tuple(b for b in plan.STOP_BASES if b != study.SYNTHETIC_BASIS)
    assert study.STRUCTURAL_BASES[0] == "burst_low"
    close, low, high = 100.0, 98.0, 104.0     # both candidates admit
    mid = plan._money((low + high) / 2)
    assert study.floor_to_cents(mid / 0.96) > study.floor_to_cents(low / 0.96) >= close
    got = study.constrained_ceiling(close, low, high)
    assert got["basis"] == "burst_low" and got["stop"] == low


def test_the_second_candidate_is_reached_only_when_the_first_cannot_hold():
    close, low, high = 100.0, 90.0, 104.0     # the low is 10% under: no ceiling of its own reaches the trigger
    assert study.floor_to_cents(low / 0.96) < close
    got = study.constrained_ceiling(close, low, high)
    assert got["basis"] == "half_range"
    assert [t["basis"] for t in got["tried"]] == ["burst_low", "half_range"]
    assert got["tried"][0]["admitted"] is False


def test_a_candidate_at_or_over_the_buy_stop_is_no_stop():
    """plan.burst_stop refuses a candidate that is not strictly under the
    trigger; so does this, or the order would be stopped out at its own fill."""
    close = 100.0
    got = study.constrained_ceiling(close, close, close)     # low == high == close
    assert got["basis"] is None
    assert all(t["admitted"] is False for t in got["tried"])


def test_the_synthetic_fallback_never_creates_eligibility():
    """The bar the current rule refuses: neither structural level can carry a
    ceiling that still reaches the trigger. plan.burst_stop answers max_stop
    and withholds; the study must answer 'no proposal', not borrow that level."""
    close, low, high = 100.0, 80.0, 101.0
    withheld = plan.burst_stop(plan._at_pct(close, plan.ENTRY_ABOVE_PCT), low, high, trigger=close)
    assert withheld["stop_basis"] == study.SYNTHETIC_BASIS
    got = study.constrained_ceiling(close, low, high)
    assert got["basis"] is None
    assert study.SYNTHETIC_BASIS not in [t["basis"] for t in got["tried"]]


def test_a_structural_basis_the_study_cannot_price_is_refused_out_loud(monkeypatch):
    """A basis added to plan.STOP_BASES that this has no price for must fail,
    not be skipped: a silently shorter cascade would answer the wrong question."""
    monkeypatch.setattr(study, "STRUCTURAL_BASES", ("burst_low", "gap_fill"))
    with pytest.raises(ValueError, match="gap_fill"):
        study.structural_candidates(98.0, 104.0)


# ------------------------------------------------- the order's own test ---
def test_every_proposal_satisfies_the_order_the_ticket_would_carry():
    """plan.fidelity_orders asserts stop < trigger <= limit. Every admitted
    proposal must pass that same assertion, or it is not a ticket."""
    data = json.loads((FIXTURES / "full.json").read_text())
    seen = 0
    for row in data["bursts"]:
        got = study.constrained_ceiling(row["close"], row["low"], row["high"])
        if not got["basis"]:
            continue
        seen += 1
        assert got["stop"] < got["trigger"] <= got["limit"]
        order = plan.fidelity_orders(row["ticker"], 1, trigger=got["trigger"], limit=got["limit"],
                                     stop=got["stop"], skip_below=plan._at_pct(row["close"], -plan.ENTRY_BELOW_PCT))
        assert order["order_json"]
    assert seen, "the full fixture should propose at least one ticket"


def test_the_oracle_and_production_reach_the_same_ticket_on_every_bar():
    """The oracle re-derives the constrained ceiling from the spec; the rule
    it derives must be the limit, the stop and the basis plan.burst_limit
    names and plan.burst_plan wrote. Over every record here, every bar."""
    for name in ("full", "degraded", "red", "yellow", "notrade"):
        data = json.loads((FIXTURES / f"{name}.json").read_text())
        seen = 0
        for row in data.get("bursts") or []:
            if study.usable_bar(row):
                continue
            got = study.constrained_ceiling(row["close"], row["low"], row["high"])
            now = study.current_plan(row, study.regime_multiplier(data))
            assert study.production_matches(got, row, now) is None, (name, row["ticker"], got)
            if got["basis"]:
                seen += 1
                assert now["limit"] == got["limit"] and now["stop"] == got["stop"]
        assert seen or not (data.get("bursts") or []), name


def test_the_oracle_is_held_to_the_band_rule_on_the_bars_the_fixtures_lack():
    """The fixtures happen to carry no bar whose ceiling lands EXACTLY on the
    buy stop, and that is where the oracle and production can part: the rule
    as proposed admitted ``trigger <= limit`` and production requires
    ``trigger < limit``. A mutant that loosens the oracle back survived a
    sweep of the fixtures alone, so the sweep carries those bars itself --
    one where production falls through to the other candidate, one where it
    refuses outright -- and asserts it reached both."""
    reached = set()
    for close, low, high in ((100.0, 96.00, 100.0), (100.0, 96.00, 104.0),
                             (100.0, 96.01, 100.0), (100.0, 99.50, 100.50),
                             (50.0, 47.0, 51.0), (1.10, 1.09, 1.15),
                             (100.0, 90.0, 100.0), (100.0, 100.0, 105.0)):
        row = bar(close, low, high)
        got = study.constrained_ceiling(close, low, high)
        now = study.current_plan(row, 1.0)
        assert study.production_matches(got, row, now) is None, (close, low, high, got)
        first = plan.burst_limit(close, low, high)["tried"][0]
        if first["under_trigger"] and not first["room_above_trigger"] \
                and first["ceiling"] == plan._price(close, "close"):
            reached.add("ceiling on the trigger: " + ("fell through" if now["eligible"] else "refused"))
    assert reached == {"ceiling on the trigger: fell through", "ceiling on the trigger: refused"}, reached


def test_the_bar_is_cent_rounded_once_as_the_production_path_rounds_it():
    """Some records carry raw four-decimal lows; burst_plan rounds the bar on
    the way in. A candidate priced off the unrounded value proposes a stop a
    cent from the one the run would write, and the cascade then disagrees."""
    close, raw_low, high = 546.78, 531.5625, 568.65
    got = study.constrained_ceiling(close, raw_low, high)
    assert got["basis"] == "burst_low"
    assert got["stop"] == plan._price(raw_low, "low") == 531.56
    assert got["stop"] != raw_low
    assert plan.burst_limit(close, raw_low, high)["stop"] == got["stop"] == 531.56
    # priced off the raw low the ceiling is a cent higher, and a limit there
    # puts the stop the run would actually write past his line
    assert study.floor_to_cents(raw_low / 0.96) == 553.71 != study.floor_to_cents(531.56 / 0.96) == 553.70
    assert got["limit"] == 553.70 and plan.burst_limit(close, raw_low, high)["limit"] == 553.70


def test_an_oracle_that_drifts_from_production_is_raised_not_reported(monkeypatch):
    """The invariant is checked while the study runs, not asserted in prose:
    if the oracle's arithmetic ever stops being production's, the reading
    stops rather than reporting a comparison of two different rules."""
    monkeypatch.setattr(study, "floor_to_cents", lambda v: math.ceil(v * 100) / 100 + 1.0)
    data = json.loads((FIXTURES / "full.json").read_text())
    with pytest.raises(AssertionError, match="the adopted rule is not the rule"):
        study.study(data)


# -------------------------------------------------------- the report ------
def test_the_study_separates_the_stop_rule_from_the_other_gates():
    """Not just that the classes partition -- count(X) + count(not X) == total
    holds for any predicate at all -- but that they carry the record's own
    answers, so swapping the current column for the proposed one goes red."""
    data = json.loads((FIXTURES / "full.json").read_text())
    out = study.study(data)
    c, x = out["counts"], out["exclusions"]
    assert c["candidate_coverage"] + c["missing_inputs"] == c["bursts"]
    assert c["fixed_eligible"] + c["fixed_stop_rule_rejections"] == c["candidate_coverage"]
    assert c["production_eligible"] + c["production_rejections"] == c["candidate_coverage"]
    # the values, read off the record's own plans
    carried = {b["ticker"]: b["plan"] for b in data["bursts"] if b.get("plan")}
    assert carried, "the full fixture should carry plans"
    assert c["production_eligible"] == sum(1 for pl in carried.values() if pl["eligible"]) + \
        sum(1 for b in data["bursts"] if not b.get("plan")
            and study.current_plan(b, study.regime_multiplier(data))["eligible"])
    assert c["fixed_eligible"] != c["production_eligible"], "the two ceilings must not agree on this fixture"
    for r in out["rows"]:
        if r["ticker"] in carried:
            assert r["production"]["eligible"] == carried[r["ticker"]]["eligible"], r["ticker"]
            assert r["production"]["limit"] == carried[r["ticker"]]["limit"], r["ticker"]
            # and the retired column is NOT the record's: it is the arithmetic
            # that is no longer in src/, so it must be able to differ
            assert r["fixed"]["limit"] == plan._at_pct(plan._price(r["close"], "c"), plan.ENTRY_ABOVE_PCT)
    assert x["grades_admitted"] == list(pipeline.TRADE_GRADES)
    assert x["excluded_by_grade"] == sum(1 for b in data["bursts"] if b["grade"] not in pipeline.TRADE_GRADES)
    assert c["green_night"]["population"] == x["would_reach_the_stop_rule_on_a_green_night"]


def test_the_budget_line_does_not_re_report_the_stop_rules_own_refusal():
    """`withheld` is burst_plan's refusal, carrying its reason verbatim; it is
    already counted in the stop-rule block, and counting it under the budget
    too would report one burst under two gates."""
    assert study.BUDGET_CUT_KINDS == ("slot_cap", "equity")
    assert set(study.BUDGET_CUT_KINDS) < set(plan.CUT_KINDS)
    assert "withheld" not in study.BUDGET_CUT_KINDS
    data = json.loads((FIXTURES / "degraded.json").read_text())
    kinds = [c["kind"] for c in data["cash_budget"]["cut"]]
    assert "withheld" in kinds and "slot_cap" in kinds, kinds
    x = study.study(data)["exclusions"]
    assert set(x["excluded_by_budget"]) <= set(study.BUDGET_CUT_KINDS)
    assert x["excluded_by_budget"]["slot_cap"] == kinds.count("slot_cap")
    assert x["cut_as_withheld_by_the_stop_rule"] == kinds.count("withheld")
    assert "withheld" not in x["excluded_by_budget"]


def test_a_row_the_pipeline_would_log_and_skip_is_a_missing_input_not_a_traceback():
    """make_plans() catches ValueError and moves on; a study that died on the
    same row would answer nothing at all after reading the whole record."""
    data = json.loads((FIXTURES / "full.json").read_text())
    data["bursts"][0]["gain_pct"] = "nope"
    data["bursts"][1]["extension_pct"] = float("nan")
    data["bursts"][2]["ticker"] = ""
    out = study.study(data)
    assert out["counts"]["missing_inputs"] == 3
    assert out["counts"]["candidate_coverage"] == len(data["bursts"]) - 3


def test_a_share_count_that_is_not_the_runs_is_a_drift_and_an_exit_code(tmp_path):
    """The share count depends on the regime's multiplier, so the study sizes
    at the record's own; verify() holds it, and main() says so in its code."""
    data = json.loads((FIXTURES / "yellow.json").read_text())
    assert study.regime_multiplier(data) != 1.0, "the yellow fixture should size at less than full"
    assert study.verify(data) == []
    for b in data["bursts"]:
        if b.get("plan"):
            b["plan"]["shares"] = b["plan"]["shares"] + 1
            break
    bad = study.verify(data)
    assert any(".shares:" in m for m in bad), bad
    drifted = tmp_path / "drifted.json"
    drifted.write_text(json.dumps(data))
    assert study.main([str(drifted)]) == 1
    clean = tmp_path / "clean.json"
    clean.write_text((FIXTURES / "yellow.json").read_text())
    assert study.main([str(clean)]) == 0


def test_the_json_is_keyed_by_the_path_as_given(tmp_path):
    """Two records with the same basename is the natural comparison -- tonight's
    data.json against an archived one -- and keying by basename collapses them."""
    a, b = tmp_path / "one" / "data.json", tmp_path / "two" / "data.json"
    for q in (a, b):
        q.parent.mkdir(parents=True)
        q.write_text((FIXTURES / "full.json").read_text())
    out = tmp_path / "study.json"
    study.main([str(a), str(b), "--json", str(out)])
    assert set(json.loads(out.read_text())) == {str(a), str(b)}


def test_the_degenerate_band_is_a_refusal_and_not_a_thin_ticket():
    """limit == stop is excluded by the admission rule, so counting it would
    report a constant zero; limit == trigger is a buy stop-limit with no room
    above its own trigger, which production refuses outright -- so it appears
    under by_refusal and can never appear as an eligible thin band."""
    data = json.loads((FIXTURES / "full.json").read_text())
    out = study.study(data)
    d, rows = out["adopted"], out["rows"]
    assert "band_under_half_a_percent" in d
    assert set(out["counts"]["by_refusal"]) == set(plan.TICKET_REFUSALS)
    for r in rows:
        if r["production"]["eligible"]:
            assert r["production"]["limit"] > plan._price(r["close"], "close")   # a real band
            assert r["production"]["limit"] != r["production"]["stop"]           # never possible
        else:
            assert r["production"]["refusal"] in plan.TICKET_REFUSALS
    assert sum(out["counts"]["by_refusal"].values()) == out["counts"]["production_rejections"]


def test_a_rescue_the_account_cannot_size_is_counted_apart():
    """A plan with no whole share is not a ticket: production writes no_order
    and the budget cuts it as no_shares."""
    data = json.loads((FIXTURES / "full.json").read_text())
    out = study.study(data)
    c, rows = out["counts"], out["rows"]
    with_order = sum(1 for r in rows if r["production"]["eligible"] and not r["fixed"]["eligible"]
                     and r["production"]["shares_at_full_size"] >= 1)
    assert c["rescued_with_an_order_at_full_size"] == with_order
    assert c["rescued_with_an_order_at_full_size"] <= c["rescued"]
    # a refused plan still carries a share count: it must never be counted
    refused = [r for r in rows if not r["production"]["eligible"]]
    assert all(r["production"]["shares_at_full_size"] >= 0 for r in refused)
    green = [r for r in rows if r["grade"] in pipeline.TRADE_GRADES and not r["vetoed"]]
    assert c["green_night"]["production_with_an_order_at_full_size"] == sum(
        1 for r in green if r["production"]["eligible"] and r["production"]["shares_at_full_size"] >= 1)


def test_a_yellow_night_counts_its_own_narrower_grade_line_as_well():
    """The regime's admitted set is not always the standing trade grades, so
    the report carries both numbers and says which is which."""
    green = study.study(json.loads((FIXTURES / "full.json").read_text()))
    assert green["exclusions"]["grades_admitted"] == list(pipeline.TRADE_GRADES)
    assert green["exclusions"]["excluded_by_grade_tonight"] is None
    data = json.loads((FIXTURES / "yellow.json").read_text())
    # yellow.json carries only A+ and C bursts, so "not in (A+,)" and
    # "not in (A+, A)" would select the same rows and either computation
    # would pass. A grade-A burst is what makes the two numbers differ.
    assert not any(b["grade"] == "A" for b in data["bursts"])
    data["bursts"][-1]["grade"] = "A"
    yellow = study.study(data)
    assert yellow["exclusions"]["grades_admitted"] == list(pipeline.YELLOW_GRADES)
    rows = yellow["rows"]
    tonight = yellow["exclusions"]["excluded_by_grade_tonight"]
    standing = yellow["exclusions"]["excluded_by_grade"]
    assert tonight == sum(1 for r in rows if r["grade"] not in pipeline.YELLOW_GRADES)
    assert standing == sum(1 for r in rows if r["grade"] not in pipeline.TRADE_GRADES)
    assert tonight > standing, (tonight, standing)   # the A burst is excluded tonight and not by the standing line
    assert set(pipeline.YELLOW_GRADES) < set(pipeline.TRADE_GRADES)


def test_a_red_night_is_counted_as_a_regime_exclusion_not_a_stop_rejection():
    data = json.loads((FIXTURES / "red.json").read_text())
    out = study.study(data)
    assert out["exclusions"]["regime_verdict"] == "red"
    assert out["exclusions"]["grades_admitted"] == []
    assert out["exclusions"]["excluded_by_regime"] == out["counts"]["candidate_coverage"]
    # the stop rule is still counted over the same bars, separately
    assert out["counts"]["fixed_stop_rule_rejections"] + out["counts"]["fixed_eligible"] \
        == out["counts"]["candidate_coverage"]


def test_a_row_without_a_readable_bar_is_counted_as_a_missing_input():
    data = json.loads((FIXTURES / "full.json").read_text())
    data["bursts"][0]["low"] = data["bursts"][0]["high"] + 1     # not a bar
    data["bursts"][1]["close"] = None
    out = study.study(data)
    assert out["counts"]["missing_inputs"] == 2
    assert {m["ticker"] for m in out["missing"]} == {data["bursts"][0]["ticker"], data["bursts"][1]["ticker"]}
    assert out["counts"]["candidate_coverage"] == len(data["bursts"]) - 2


def test_the_production_column_is_the_production_path_not_a_second_reading():
    """Every plan a record already carries is reproduced exactly, so the
    comparison's 'today' column is the run's own answer."""
    data = json.loads((FIXTURES / "degraded.json").read_text())
    carried = [b for b in data["bursts"] if b.get("plan")]
    assert carried, "the degraded fixture should carry plans"
    assert study.verify(data) == []


def test_the_adopted_block_counts_the_indicative_entries_the_limit_capped():
    data = json.loads((FIXTURES / "full.json").read_text())
    out = study.study(data)
    d = out["adopted"]
    assert d["production_eligible"] == out["counts"]["production_eligible"]
    # every example named really is a case the close +1% would have overshot,
    # and the published plan says so in its own field
    named = {e["ticker"] for e in d["indicative_entry_examples"]}
    assert named, "the full fixture should carry a capped indicative entry"
    by_ticker = {r["ticker"]: r for r in out["rows"]}
    for t in named:
        r = by_ticker[t]
        assert plan._at_pct(plan._price(r["close"], "c"), plan.ASSUMED_SLIPPAGE_PCT) > r["production"]["limit"], t
        assert r["production"]["planned_entry"] == r["production"]["limit"], t
    counted = sum(1 for r in out["rows"] if r["production"]["eligible"]
                  and r["production"]["planned_entry_capped"])
    assert d["indicative_entry_capped_at_the_limit"] == counted
    assert any("planned_entry" in f for f in d["fields_settled"])


# ------------------------------------------------------- read-only --------
def test_the_study_writes_nothing_into_the_record_it_reads(tmp_path):
    src = FIXTURES / "full.json"
    copy = tmp_path / "record.json"
    copy.write_text(src.read_text())
    before = hashlib.sha256(copy.read_bytes()).hexdigest()
    study.main([str(copy)])
    assert hashlib.sha256(copy.read_bytes()).hexdigest() == before
    assert json.loads(src.read_text())["bursts"][0].get("plan") == \
        json.loads(copy.read_text())["bursts"][0].get("plan")


def test_the_study_does_not_move_the_production_ceiling_or_the_stop_line():
    """The comparison is read-only in the sense that matters: the numbers the
    run writes tickets with are still the ones the rulebook archives."""
    assert plan.ENTRY_ABOVE_PCT == 4.0 and plan.MAX_STOP_PCT == 4.0
    assert plan.RULES["plan.entry_above_pct"] == plan.ENTRY_ABOVE_PCT
    assert plan.RULES["plan.max_stop_pct"] == plan.MAX_STOP_PCT
    assert plan.SIZING_BASIS == "order_limit"
    got = plan.burst_plan(ticker="T", close=100.0, low=80.0, high=101.0, open_=99.0,
                          prev_close=95.0, gain_pct=5.0, account=plan.Account())
    assert got["limit"] == plan._at_pct(100.0, plan.ENTRY_ABOVE_PCT)
    assert got["eligible"] is False and got["stop_basis"] == study.SYNTHETIC_BASIS


def test_the_sizing_is_at_the_effective_limit_in_both_columns():
    row = bar(100.0, 98.0, 104.0)
    got = study.constrained_ceiling(row["close"], row["low"], row["high"])
    now = study.current_plan(row, 1.0)
    assert now["sizing_price"] == now["limit"] == got["limit"]
    assert now["risk_per_share"] == plan._money(got["limit"] - got["stop"])
    # and the regime's multiplier is carried through, not quietly dropped
    assert study.current_plan(row, 0.0)["shares"] == 0
    assert study.current_plan(row, 0.5)["shares"] <= now["shares"]
    # the retired column sizes at ITS limit, which is a different price here
    fixed = study.fixed_ceiling_plan(row, 1.0)
    assert fixed["limit"] == plan._at_pct(100.0, plan.ENTRY_ABOVE_PCT) > now["limit"]
