"""src.plan: sizing, the burst and anticipation plans, follow-through, notes.

Every expected number below is hand arithmetic from the constants the
module names, written out in the docstring or beside the assertion, so a
constant that moves fails here for the number and not for the name.
"""
from __future__ import annotations

import ast
import json
import math
from pathlib import Path

import pytest

from src import plan
from src.plan import Account, size

SOURCE = Path(plan.__file__)

#: close 20.00, low 19.85: the stop is 1.73% under the planned fill of 20.20,
#: inside his ideal 2%, so the risk budget is the full $50.
TIGHT = dict(ticker="XYZ", close=20.00, low=19.85, high=20.10, open_=19.90, prev_close=19.00, gain_pct=5.26)
#: close 20.00, low 19.40: 3.96% under the fill, between the ideal and the
#: maximum, so the risk is halved to $25.
MID = dict(ticker="XYZ", close=20.00, low=19.40, high=20.10, open_=19.60, prev_close=19.00, gain_pct=5.26)


def burst(**overrides):
    return plan.burst_plan(**{**MID, "account": Account(), **overrides})


def bar(o, h, l, c, date="2026-09-11"):
    return {"date": date, "o": o, "h": h, "l": l, "c": c}


PICK = {"ticker": "XYZ", "date": "2026-09-10", "entry_ref": 100.0, "stop": 96.0, "shares": 20, "kind": "burst"}


# ------------------------------------------------------------- account -----


def test_the_default_account_is_the_briefs():
    acct = Account()
    assert (acct.equity, acct.risk_pct, acct.max_position_pct, acct.max_open_positions) == (10_000, 0.5, 25, 4)
    assert acct.risk_usd == 50.0
    assert acct.max_position_usd == 2500.0
    assert acct.within_bonde_band
    assert not Account(risk_pct=3).within_bonde_band
    assert not Account(risk_pct=0.2).within_bonde_band
    assert acct.to_dict() == {"equity": 10_000, "risk_pct": 0.5, "max_position_pct": 25, "max_open_positions": 4}


def test_from_env_reads_the_four_variables_and_blank_means_default():
    env = {"ACCOUNT_EQUITY": "25000", "RISK_PCT": "1", "MAX_POSITION_PCT": "30", "MAX_OPEN_POSITIONS": "3"}
    acct = Account.from_env(env)
    assert (acct.equity, acct.risk_pct, acct.max_position_pct, acct.max_open_positions) == (25_000, 1.0, 30.0, 3)
    assert Account.from_env({}) == Account()
    assert Account.from_env({"ACCOUNT_EQUITY": "  ", "RISK_PCT": ""}) == Account()


def test_from_env_reads_the_process_environment_by_default(monkeypatch):
    monkeypatch.setenv("ACCOUNT_EQUITY", "5000")
    monkeypatch.delenv("RISK_PCT", raising=False)
    assert Account.from_env().equity == 5000.0


@pytest.mark.parametrize("var, value", [
    ("RISK_PCT", "abc"), ("MAX_OPEN_POSITIONS", "3.5"), ("ACCOUNT_EQUITY", "-5"),
    ("MAX_OPEN_POSITIONS", "0"), ("MAX_POSITION_PCT", "nan"),
])
def test_from_env_names_the_variable_it_refuses(var, value):
    with pytest.raises(ValueError) as err:
        Account.from_env({var: value})
    assert var in str(err.value)


# ------------------------------------------------------------- sizing ------


def test_sizing_by_hand_equity_10000_risk_half_percent_entry_2020_stop_1940():
    """$50 / $0.80 = 62.5 -> 62 shares; 62 x 20.20 = $1,252.40 = 12.52%."""
    s = size(20.20, 19.40, Account())
    assert s.shares == 62
    assert s.position_usd == 1252.40
    assert s.position_pct == 12.52
    assert s.risk_usd == 49.60
    assert s.risk_per_share == 0.80
    assert s.stop_pct == 3.96
    assert s.capped_by == "risk"
    assert s.note is None
    assert (s.budget_usd, s.cap_usd, s.multiplier) == (50.0, 2500.0, 1.0)


def test_bondes_rh_example_166_shares_at_a_quarter_percent_of_100k():
    """Entry ~$83, stop $81.50, 0.25% of $100,000 = $250 / $1.50 -> 166."""
    s = size(83.0, 81.50, Account(equity=100_000, risk_pct=0.25))
    assert s.shares == 166
    assert s.risk_usd == 249.0
    assert s.capped_by == "risk"


def test_the_position_cap_binds_on_a_half_percent_stop():
    """$50 / $0.10 = 500 shares = $10,000; the 25% cap allows $2,500 / $20 = 125."""
    s = size(20.00, 19.90, Account())
    assert s.shares == 125
    assert s.capped_by == "position_cap"
    assert s.position_usd == 2500.0
    assert s.position_pct == 25.0
    assert s.risk_usd == 12.50
    assert "500 shares" in s.note and "25% cap" in s.note


def test_the_multiplier_scales_the_risk_budget_and_zero_means_no_shares():
    half = size(20.20, 19.40, Account(), multiplier=0.5)
    assert (half.shares, half.budget_usd, half.capped_by) == (31, 25.0, "risk")
    none = size(20.20, 19.40, Account(), multiplier=0)
    assert (none.shares, none.position_usd, none.risk_usd, none.capped_by) == (0, 0.0, 0.0, "multiplier")
    assert "multiplier is 0" in none.note


def test_shares_are_whole_and_the_division_is_in_cents():
    assert size(10.00, 9.70, Account()).shares == 166      # 50 / 0.30 = 166.67
    assert size(10.00, 9.95, Account()).shares == 250      # 50 / 0.05 = 1000, cap 2500 / 10 = 250
    assert size(20.20, 19.40, Account()).shares == 62      # 20.20 - 19.40 is 0.8000000000000007 in floats


def test_zero_shares_carry_a_note_when_the_budget_cannot_buy_one():
    s = size(500.0, 400.0, Account())
    assert s.shares == 0
    assert s.capped_by == "none"
    assert "cannot buy one share" in s.note and "$100.00" in s.note


@pytest.mark.parametrize("entry, stop, multiplier", [
    (19.40, 20.20, 1.0), (20.20, 20.20, 1.0), (-1.0, 0.5, 1.0), (20.0, -1.0, 1.0),
    (math.nan, 19.0, 1.0), (20.0, math.inf, 1.0), (20.0, 19.0, -0.5), (20.0, 19.0, math.nan),
    ("20", 19.0, 1.0), (20.004, 20.001, 1.0),
])
def test_size_refuses_an_entry_at_or_below_the_stop_and_non_prices(entry, stop, multiplier):
    with pytest.raises(ValueError):
        size(entry, stop, Account(), multiplier)


def test_size_names_the_rule_when_the_entry_is_at_the_stop():
    """The message, not just the exception: a weakened `<=` would let the
    equal case through to a different refusal, which is the shape the
    rejection-path tests once had."""
    with pytest.raises(ValueError, match="must be above stop"):
        size(20.20, 20.20, Account())
    with pytest.raises(ValueError, match="must be above stop"):
        size(20.004, 20.001, Account())   # both round to 20.00: a cent is the finest the rule sees


def test_the_stop_risk_multiplier_halves_between_the_ideal_and_the_maximum():
    assert plan.stop_risk(2.0) == (1.0, None)
    assert plan.stop_risk(2.01)[0] == 0.5
    assert "wider than his ideal 2%" in plan.stop_risk(3.0)[1]
    assert plan.stop_risk(4.0)[0] == 0.5
    assert plan.stop_risk(4.01) == (1.0, None)   # refused on eligibility, not sized down


# ------------------------------------------------------------- burst plan --


def test_the_buy_zone_and_the_skip_thresholds():
    p = burst(close=50.00, low=49.50, high=50.20, open_=49.60, prev_close=47.00)
    assert p["entry_ref"] == 50.00
    assert p["entry_low"] == 49.00 == p["skip_if_open_below"]      # -2%
    assert p["entry_high"] == 52.00 == p["skip_if_open_above"]     # +4%
    assert p["extended_above"] == 54.00                            # +8%
    assert p["planned_entry"] == 50.50                             # +1%
    assert p["entry_window"] == "first 30 minutes"
    assert "$49.00" in p["pre_open_check"] and "$52.00" in p["pre_open_check"] and "$54.00" in p["pre_open_check"]


def test_the_stop_cascade_takes_the_burst_low_when_it_is_within_four_percent():
    p = burst(close=100.0, low=97.50, high=101.0, open_=98.0, prev_close=95.0)
    assert p["stop_basis"] == "burst_low"
    assert p["stop"] == 97.50
    assert p["stop_pct"] == 3.47          # (101.00 - 97.50) / 101.00
    assert p["stop_note"] is None
    assert p["eligible"] and p["reason"] is None


def test_the_stop_cascade_falls_to_the_range_midpoint_when_the_low_is_wide():
    """Low 95 is 5.94% under the 101.00 fill; the midpoint 98.00 is 2.97%."""
    p = burst(close=100.0, low=95.0, high=101.0, open_=96.0, prev_close=95.0)
    assert p["stop_basis"] == "half_range"
    assert p["stop"] == 98.00
    assert p["stop_pct"] == 2.97
    assert [c["within_max"] for c in p["stop_candidates"]] == [False, True]
    assert p["eligible"]


def test_the_stop_cascade_sets_four_percent_and_refuses_when_both_are_wide():
    """Low 90 is 10.89% under 101.00, the midpoint 95 is 5.94%: 4% = 96.96."""
    p = burst(close=100.0, low=90.0, high=100.0, open_=91.0, prev_close=95.0)
    assert p["stop_basis"] == "max_stop"
    assert p["stop"] == 96.96
    assert p["stop_pct"] == 4.0
    assert "10.89%" in p["stop_note"] and "5.94%" in p["stop_note"] and "$96.96" in p["stop_note"]
    assert not p["eligible"]
    assert p["reason"].startswith("stop wider than 4%") and "10.89%" in p["reason"]
    assert p["action"] == "refused"
    assert p["order_line"] is None and p["order_json"] is None and p["order_readback"] is None
    assert "wide_stop" in p["flags"]
    assert p["shares"] > 0        # the card still shows a size


def test_the_sizing_is_at_the_planned_fill_and_the_resize_rule_carries_the_numbers():
    p = burst()     # MID: fill 20.20, stop 19.40, 3.96% -> risk halved to $25
    assert p["planned_entry"] == 20.20
    assert p["risk_per_share"] == 0.80
    assert p["multipliers"] == {"regime": 1.0, "hazard": 1.0, "stop_risk": 0.5, "total": 0.5}
    assert p["stop_risk_multiplier"] == 0.5
    assert p["shares"] == 31                     # $25 / $0.80
    assert p["position_usd"] == 626.20
    assert p["risk_usd"] == 24.80
    assert "risk_halved" in p["flags"]
    assert "wider than his ideal 2%" in p["stop_risk_reason"]
    assert p["resize_rule"] == "if your fill differs, shares = $25.00 / (fill - $19.40), and no more than $2,500.00 of stock"


def test_a_tight_stop_keeps_the_full_budget_and_the_cap_can_bind_inside_a_plan():
    p = burst(**TIGHT)   # fill 20.20, stop 19.85 = 1.73%: $50 / $0.35 = 142 -> cap $2,500 / 20.20 = 123
    assert p["stop_pct"] == 1.73
    assert p["multipliers"]["stop_risk"] == 1.0 and p["stop_risk_reason"] is None
    assert p["shares"] == 123
    assert p["capped_by"] == "position_cap"
    assert "position_capped" in p["flags"] and "risk_halved" not in p["flags"]


def test_targets_by_price_band():
    t = burst()["targets"]
    assert (t["low_pct"], t["high_pct"]) == (8, 20)
    assert (t["low"], t["high"]) == (21.82, 24.24)          # from the 20.20 fill
    assert t["note"] is None and t["dollar_low"] is None
    mid = burst(close=50.00, low=49.50, high=50.20, open_=49.60, prev_close=47.00)["targets"]
    assert (mid["low"], mid["high"]) == (54.54, 60.60) and (mid["dollar_low"], mid["dollar_high"]) == (55.50, 75.50)
    cheap = burst(close=4.00, low=3.95, high=4.05, open_=3.98, prev_close=3.80)["targets"]
    assert cheap["note"] == "under $5 bursts can run 20-40%"
    dear = burst(close=60.00, low=59.50, high=60.30, open_=59.60, prev_close=57.00)["targets"]
    assert dear["note"] == "above $40 he measures the move in dollars: $5-25"
    assert (dear["dollar_low"], dear["dollar_high"]) == (65.60, 85.60)   # 60.60 + 5 / + 25
    assert plan.targets(10.0, 5.0)["note"] is None        # exactly $5 is not under it
    assert plan.targets(10.0, 40.0)["note"] is None       # exactly $40 is not above it


def test_every_exit_rule_is_present_with_the_right_prices():
    rules = {r["key"]: r for r in plan.exit_schedule(50.50, 48.50)}
    assert list(rules) == ["sell_half_8pct", "abnormal_10pct", "gap_20pct", "entry_day_low", "day3_sell_half",
                           "day3_no_progress", "trail_after_day3", "day5_exit", "stop", "no_breakeven"]
    assert rules["sell_half_8pct"]["price"] == 54.54 and "$54.54" in rules["sell_half_8pct"]["when"]
    assert "sell half" in rules["sell_half_8pct"]["rule"] and "25-50 cents" in rules["sell_half_8pct"]["rule"]
    assert rules["abnormal_10pct"]["price"] == 55.55 and "+10%" in rules["abnormal_10pct"]["when"]
    assert rules["gap_20pct"]["price"] == 60.60 and "at the open" in rules["gap_20pct"]["rule"]
    assert rules["entry_day_low"]["when"] == "the close of day 1" and "$48.50" in rules["entry_day_low"]["rule"]
    assert rules["day3_sell_half"]["when"] == "day 3 close" and "at least half" in rules["day3_sell_half"]["rule"]
    assert rules["day3_no_progress"]["price"] == 50.50 and "$50.50" in rules["day3_no_progress"]["when"]
    assert rules["trail_after_day3"]["when"] == "from the close of day 3" and "each day's low" in rules["trail_after_day3"]["rule"]
    assert rules["day5_exit"]["when"] == "day 5 close" and "into strength" in rules["day5_exit"]["rule"]
    assert rules["stop"]["price"] == 48.50 and "$48.50" in rules["stop"]["when"] and "stop-market" in rules["stop"]["when"]
    assert "before day 5" in rules["no_breakeven"]["rule"] and rules["no_breakeven"]["source"] == "T"
    assert {r["source"] for r in rules.values()} <= {"B", "P", "T"}
    assert "the stop" in {r["key"]: r for r in plan.exit_schedule(50.50)}["stop"]["when"]


def test_the_plans_exits_are_from_the_planned_fill():
    p = burst()
    assert [r["price"] for r in p["exits"][:3]] == [21.82, 22.22, 24.24]   # 20.20 x 1.08 / 1.10 / 1.20
    assert p["exits"] == plan.exit_schedule(20.20, 19.40)


def test_the_order_line_is_a_fidelity_buy_stop_limit_with_the_stop_attached():
    p = burst()
    assert p["action"] == "buy_at_open"
    assert p["order_line"] == ("Buy 31 XYZ stop-limit: stop $20.00 limit $20.80, day · "
                               "OTO sell 31 XYZ stop-loss $19.40 GTC")
    assert p["order_readback"] == ("Buy 31 XYZ stop limit 20.00 / 20.80 day, "
                                   "one-triggers-the-other sell 31 XYZ stop loss 19.40 GTC")
    assert p["fallback_line"] == ("If your app has no stop-limit: buy 31 XYZ limit $20.80 (day) "
                                  "with the same sell stop attached.")
    assert p["order_json"] == {
        "symbol": "XYZ", "action": "buy", "quantity": 31, "order_type": "stop_limit",
        "stop_price": 20.00, "limit_price": 20.80, "time_in_force": "day",
        "conditional": "one_triggers_the_other",
        "then": {"action": "sell", "quantity": 31, "order_type": "stop", "stop_price": 19.40,
                 "time_in_force": "gtc"},
    }


def test_fidelity_orders_refuse_a_shape_that_cannot_be_placed():
    with pytest.raises(ValueError):
        plan.fidelity_orders("XYZ", 10, trigger=20.0, limit=19.0, stop=18.0)   # limit under the trigger
    with pytest.raises(ValueError):
        plan.fidelity_orders("XYZ", 10, trigger=20.0, limit=21.0, stop=20.0)   # stop at the trigger
    with pytest.raises(ValueError):
        plan.fidelity_orders("XYZ", 0, trigger=20.0, limit=21.0, stop=19.0)


def test_the_regime_multiplier_zero_means_no_new_longs_and_half_halves():
    red = burst(size_multiplier=0)
    assert red["shares"] == 0 and red["action"] == "no_new_longs"
    assert red["order_line"] is None and red["capped_by"] == "multiplier"
    assert red["multipliers"]["total"] == 0
    yellow = burst(**TIGHT, size_multiplier=0.5)   # $25 / $0.35 = 71
    assert yellow["shares"] == 71 and yellow["action"] == "buy_at_open"
    assert yellow["multipliers"] == {"regime": 0.5, "hazard": 1.0, "stop_risk": 1.0, "total": 0.5}


def test_hazards_halve_the_size_with_the_reason_and_never_veto():
    hot = burst(gain_pct=15.0)
    assert hot["hazards"] == [{"kind": "gain_over_15", "multiplier": 0.5,
                               "detail": hot["hazards"][0]["detail"]}]
    assert "worst cell in the only event study" in hot["hazards"][0]["detail"]
    assert hot["hazard_multiplier"] == 0.5
    assert hot["multipliers"]["total"] == 0.25 and hot["shares"] == 15     # $12.50 / $0.80
    assert hot["eligible"] and hot["action"] == "buy_at_open" and "gain_over_15" in hot["flags"]
    assert burst(gain_pct=14.99)["hazards"] == []
    extended = burst(extension_pct=20.01)
    assert [h["kind"] for h in extended["hazards"]] == ["extended"]
    assert "20-session average" in extended["hazards"][0]["detail"] and "past 20%" in extended["hazards"][0]["detail"]
    assert extended["extension_pct"] == 20.01
    assert burst(extension_pct=20.0)["hazards"] == []
    both = burst(gain_pct=16.0, extension_pct=25.0)
    assert [h["kind"] for h in both["hazards"]] == ["gain_over_15", "extended"]
    assert both["hazard_multiplier"] == 0.5 and both["multipliers"]["total"] == 0.25


def test_the_burst_block_records_the_bar_it_was_planned_from():
    p = burst()
    assert p["burst"] == {"close": 20.0, "low": 19.4, "high": 20.1, "open": 19.6, "prev_close": 19.0,
                          "gain_pct": 5.26, "gap_pct": 3.16, "dollar_move": 0.40, "close_in_range_pct": 85.71}
    assert p["kind"] == "burst" and p["scan"] == "4pct"
    assert burst(scan="dollar")["scan"] == "dollar"


@pytest.mark.parametrize("bad", [
    {"close": math.nan}, {"prev_close": 0}, {"close": "20"}, {"low": 21.0}, {"open_": 25.0},
    {"high": 19.0}, {"gain_pct": math.inf}, {"ticker": ""}, {"extension_pct": math.nan},
])
def test_burst_plan_refuses_unreadable_inputs(bad):
    with pytest.raises(ValueError):
        burst(**bad)


# ------------------------------------------------------------- anticipation


def test_anticipation_trigger_is_cents_on_a_cheap_name_and_a_fraction_on_a_dear_one():
    cheap = plan.anticipation_plan(ticker="ABC", close=5.00, box_high=5.10, box_low=4.90,
                                   lows_last3=[4.95, 4.98, 5.00], account=Account())
    assert cheap["trigger_cushion"] == 0.02 and cheap["trigger"] == 5.12
    assert cheap["limit"] == 5.17                       # 5.12 x 1.01 = 5.1712
    assert cheap["stop"] == 4.95 and cheap["stop_alt"] == 5.00
    assert cheap["stop_pct"] == 3.43                    # 5.12 / 4.95 - 1
    assert cheap["eligible"] and cheap["action"] == "place_buy_stop"
    assert cheap["multipliers"]["stop_risk"] == 0.5 and cheap["shares"] == 147   # $25 / $0.17
    assert cheap["order_line"] == ("Buy 147 ABC stop-limit: stop $5.12 limit $5.17, day · "
                                   "OTO sell 147 ABC stop-loss $4.95 GTC")
    assert cheap["order_json"]["order_type"] == "stop_limit" and cheap["order_json"]["stop_price"] == 5.12
    dear = plan.anticipation_plan(ticker="DEF", close=80.0, box_high=81.0, box_low=78.0,
                                  lows_last3=[80.0, 80.2, 80.5], account=Account())
    assert dear["trigger_cushion"] == 0.08 and dear["trigger"] == 81.08
    assert dear["limit"] == 81.89
    assert dear["stop"] == 80.0 and dear["stop_pct"] == 1.35
    assert dear["multipliers"]["stop_risk"] == 1.0
    assert dear["shares"] == 30 and dear["capped_by"] == "position_cap"    # 46 by risk, $2,500 / 81.08 = 30
    assert dear["entry_ref"] == 81.08 and dear["kind"] == "anticipation"


def test_anticipation_refuses_a_stop_past_four_percent():
    p = plan.anticipation_plan(ticker="ABC", close=5.00, box_high=5.10, box_low=4.70,
                               lows_last3=[4.80, 4.85, 4.90], account=Account())
    assert p["stop_pct"] == 6.67
    assert not p["eligible"] and p["action"] == "refused"
    assert p["reason"].startswith("stop wider than 4%") and "6.67%" in p["reason"]
    assert p["order_line"] is None and "wide_stop" in p["flags"]


def test_anticipation_publishes_the_gap_rule_the_open_entry_and_the_exits():
    p = plan.anticipation_plan(ticker="ABC", close=5.00, box_high=5.10, box_low=4.90,
                               lows_last3=[4.95, 4.98, 5.00], account=Account())
    assert p["gap_ok_above"] == 5.10
    assert p["gap_rule"] == "an open more than 2% above $5.00 (over $5.10) is gapped: catalyst check before buying"
    assert p["open_entry"].startswith("MOO/OPG at the open only for the top 2 names")
    assert p["exits"] == plan.exit_schedule(5.12, 4.95)
    assert p["targets"]["low"] == 5.53 and p["targets"]["note"] is None     # $5.00 is not under $5
    cheap = plan.anticipation_plan(ticker="ABC", close=4.99, box_high=5.10, box_low=4.90,
                                   lows_last3=[4.95, 4.98, 4.99], account=Account())
    assert cheap["targets"]["note"] == "under $5 bursts can run 20-40%"
    assert p["stop_basis"] == "lowest low of the last 3 sessions"
    one = plan.anticipation_plan(ticker="ABC", close=5.00, box_high=5.10, box_low=4.90,
                                 lows_last3=[5.00], account=Account())
    assert one["stop"] == 5.00 and one["stop_basis"] == "lowest low of the last 1 sessions"
    assert plan.anticipation_plan(ticker="ABC", close=5.00, box_high=5.10, box_low=4.90,
                                  lows_last3=[4.95], account=Account(), size_multiplier=0)["action"] == "no_new_longs"


@pytest.mark.parametrize("bad", [
    {"lows_last3": []}, {"lows_last3": [4.9, 4.9, 4.9, 4.9]}, {"lows_last3": [5.2]}, {"box_low": 5.2},
    {"close": math.nan}, {"lows_last3": [math.nan]}, {"ticker": ""},
])
def test_anticipation_plan_refuses_a_malformed_box(bad):
    with pytest.raises(ValueError):
        plan.anticipation_plan(**{**dict(ticker="ABC", close=5.00, box_high=5.10, box_low=4.90,
                                         lows_last3=[4.95, 4.98, 5.00], account=Account()), **bad})


# ------------------------------------------------------------- follow ------


def test_follow_is_pending_with_no_sessions():
    f = plan.follow(PICK, [])
    assert f["status"] == "pending" and f["day"] == 0 and f["sessions"] == 0
    assert f["events"] == [] and f["last_close"] is None and f["unrealised_pct"] is None
    assert f["current_stop"] == 96.0
    assert "buy 20 XYZ per the plan" in f["instruction"] and "$96.00" in f["instruction"]


def test_follow_stops_on_a_day_one_low_at_the_stop():
    f = plan.follow(PICK, [bar(100, 101, 95.5, 97)])
    assert f["status"] == "stopped" and f["day"] == 1
    assert f["events"] == [{"day": 1, "date": "2026-09-11", "event": "stopped", "price": 96.0}]
    assert f["exit_price"] == 96.0 and f["result_pct"] == -4.0
    assert f["instruction"] == "Day 1: stopped at $96.00 (-4.0%)."


def test_follow_stops_at_the_open_on_a_gap_below_the_stop():
    f = plan.follow(PICK, [bar(94, 95, 93, 94.5)])
    assert f["status"] == "stopped"
    assert f["events"][0]["event"] == "stopped_at_open" and f["events"][0]["price"] == 94.0
    assert f["result_pct"] == -6.0
    assert "opened at $94.00" in f["instruction"]


def test_follow_sells_half_on_an_eight_percent_high_and_raises_the_stop():
    f = plan.follow(PICK, [bar(101, 109, 100.5, 107)])
    assert f["status"] == "sell_half" and f["half_sold"]
    assert [e["event"] for e in f["events"]] == ["sell_half", "stop_raised"]
    assert f["events"][0]["price"] == 108.0            # the +8% limit fills at the level
    assert f["events"][1]["price"] == 108.75           # the high 109 less 25 cents
    assert f["current_stop"] == 108.75
    assert "sell half (10 of 20 XYZ) at $108.00 (+8.0%)" in f["instruction"]
    assert "raise the stop to $108.75 (25 cents under the day's high $109.00)" in f["instruction"]
    assert f["instruction"].endswith("The stop is $108.75.")
    assert f["unrealised_pct"] == 7.0


def test_follow_fills_the_half_at_the_open_when_it_gaps_over_the_level_and_marks_an_abnormal_day():
    f = plan.follow(PICK, [bar(110, 112, 109, 111)])
    assert f["status"] == "sell_half"
    assert [(e["event"], e["price"]) for e in f["events"]] == [
        ("sell_half", 110.0), ("stop_raised", 111.75), ("abnormal_day", 111.0)]
    assert f["current_stop"] == 111.75


def test_follow_raises_the_stop_to_the_entry_days_low_once_day_one_closes():
    f = plan.follow(PICK, [bar(101, 103, 100.2, 102)])
    assert f["status"] == "hold"
    assert f["events"] == [{"day": 1, "date": "2026-09-11", "event": "stop_raised_to_entry_low", "price": 100.2}]
    assert f["current_stop"] == 100.2
    assert f["instruction"] == "Day 1: hold 20 XYZ with the stop at $100.20 (closed $102.00, +2.0%)."
    # And that raise is load-bearing: day 2 dips a dime under it.
    g = plan.follow(PICK, [bar(101, 103, 100.2, 102), bar(101, 102, 100.1, 101.5, "2026-09-14")])
    assert g["status"] == "stopped" and g["day"] == 2 and g["exit_price"] == 100.2
    assert g["result_pct"] == 0.2


def test_follow_does_not_trail_on_day_two():
    f = plan.follow(PICK, [bar(101, 103, 100.5, 102), bar(102, 104, 101, 103)])
    assert f["status"] == "hold" and f["day"] == 2
    assert f["current_stop"] == 100.5
    assert [e["event"] for e in f["events"]] == ["stop_raised_to_entry_low"]


def test_follow_sells_half_at_the_day_three_close_and_starts_trailing():
    f = plan.follow(PICK, [bar(101, 103, 100.5, 102), bar(102, 104, 101, 103), bar(103, 105, 102, 104)])
    assert f["status"] == "sell_half" and f["day"] == 3
    assert [(e["day"], e["event"], e["price"]) for e in f["events"]] == [
        (1, "stop_raised_to_entry_low", 100.5), (3, "sell_half", 104.0), (3, "stop_trailed", 102.0)]
    assert f["current_stop"] == 102.0
    assert "sell at least half (10 of 20 XYZ) at the close" in f["instruction"]
    assert f["instruction"].endswith("The stop is $102.00.")


def test_follow_exits_on_day_three_with_no_progress():
    f = plan.follow(PICK, [bar(101, 102, 99, 100.5), bar(100.5, 101, 99.5, 100.2), bar(100.2, 101, 99.2, 100.0)])
    assert f["status"] == "exit" and f["day"] == 3
    assert f["events"][-1] == {"day": 3, "date": "2026-09-11", "event": "no_progress", "price": 100.0}
    assert f["exit_price"] == 100.0 and f["result_pct"] == 0.0
    assert "at or below the $100.00 entry: no follow-through, exit 20 XYZ" in f["instruction"]


FIVE = [bar(101, 102, 100.5, 101.5), bar(101.5, 103, 101, 102.5), bar(102.5, 104, 102, 103.5),
        bar(103.5, 105, 103, 104.5), bar(104.5, 106, 104, 105.5)]


def test_follow_trails_after_day_three_then_exits_on_day_five():
    four = plan.follow(PICK, FIVE[:4])
    assert four["status"] == "sell_into_strength" and four["day"] == 4
    assert four["current_stop"] == 103.0
    assert four["events"][-1] == {"day": 4, "date": "2026-09-11", "event": "stop_trailed", "price": 103.0}
    assert "sell the rest into strength by day 5 with the stop at $103.00" in four["instruction"]
    five = plan.follow(PICK, FIVE)
    assert five["status"] == "exit" and five["day"] == 5
    assert five["events"][-1]["event"] == "day5_exit" and five["exit_price"] == 105.5
    assert five["result_pct"] == 5.5 and five["current_stop"] == 104.0
    assert five["instruction"] == "Day 5: closed at $105.50 (+5.5%): exit the remainder of 20 XYZ into strength."


def test_follow_expires_past_the_window():
    f = plan.follow(PICK, FIVE + [bar(105, 107, 104.5, 106)])
    assert f["status"] == "expired" and f["day"] == 6 and f["sessions"] == 6
    assert "5-session window is over" in f["instruction"]


def test_follow_exits_at_the_open_on_a_twenty_percent_gap():
    f = plan.follow(PICK, [bar(121, 125, 120, 123)])
    assert f["status"] == "exit"
    assert f["events"] == [{"day": 1, "date": "2026-09-11", "event": "gap_exit", "price": 121.0}]
    assert f["result_pct"] == 21.0
    assert "a +20% gap): sell 20 XYZ at the open" in f["instruction"]
    assert plan.follow(PICK, [bar(119.99, 125, 119, 123)])["status"] == "sell_half"


def test_follow_reads_the_stop_before_the_high_within_one_bar():
    f = plan.follow(PICK, [bar(100, 109, 95, 107)])
    assert f["status"] == "stopped" and f["result_pct"] == -4.0


def test_follow_expires_an_anticipation_pick_that_never_triggered():
    pick = {**PICK, "kind": "anticipation", "entry_ref": 50.0, "stop": 48.5}
    f = plan.follow(pick, [bar(49, 49.9, 48.6, 49.5)])
    assert f["status"] == "expired"
    assert f["events"] == [{"day": 1, "date": "2026-09-11", "event": "not_triggered", "price": 49.9}]
    assert "was never reached (high $49.90)" in f["instruction"]
    assert plan.follow(pick, [bar(49, 50.5, 48.6, 50.2)])["status"] == "hold"


def test_follow_under_a_red_regime_adds_the_clause_to_held_plans_only():
    held = plan.follow(PICK, [bar(101, 103, 100.2, 102)], regime="red")
    assert held["status"] == "hold" and held["regime"] == "red"
    assert held["instruction"].endswith(" Breadth is red: sell into any strength; do not add.")
    assert plan.follow(PICK, [bar(101, 109, 100.5, 107)], regime="red")["instruction"].endswith(plan.RED_CLAUSE)
    assert plan.follow(PICK, FIVE[:4], regime="red")["instruction"].endswith(plan.RED_CLAUSE)
    assert plan.follow(PICK, [], regime="red")["instruction"].endswith("Breadth is red: do not open it.")
    stopped = plan.follow(PICK, [bar(100, 101, 95.5, 97)], regime="red")
    assert "Breadth" not in stopped["instruction"]
    assert "Breadth" not in plan.follow(PICK, FIVE, regime="red")["instruction"]
    assert "Breadth" not in plan.follow(PICK, [bar(101, 103, 100.2, 102)])["instruction"]
    assert "Breadth" not in plan.follow(PICK, [bar(101, 103, 100.2, 102)], regime="yellow")["instruction"]


@pytest.mark.parametrize("pick, later", [
    (PICK, [bar(100, 101, 99, 102)]),                    # close above the high
    (PICK, [bar(98, 101, 99, 100)]),                     # open under the low
    ({**PICK, "stop": 100.0}, []),                       # stop at the entry
    ({**PICK, "kind": "swing"}, []),
    ({**PICK, "shares": 2.5}, []),
    ({**PICK, "entry_ref": "100"}, []),
    (PICK, [{"date": "2026-09-11", "o": 100, "h": 101, "l": 99}]),   # no close
    (PICK, ["not a bar"]),
])
def test_follow_refuses_a_pick_or_a_bar_it_cannot_read(pick, later):
    with pytest.raises(ValueError):
        plan.follow(pick, later)


def test_follow_refuses_a_regime_that_is_not_a_word():
    with pytest.raises(ValueError):
        plan.follow(PICK, [], regime=None)


# ------------------------------------------------------------- budget ------


def _plans(*positions, action="buy_at_open"):
    return [{"ticker": f"T{i}", "shares": 10, "position_usd": p, "action": action}
            for i, p in enumerate(positions, 1)]


def test_cash_budget_counts_slots_and_dollars_in_rank_order():
    b = plan.cash_budget(_plans(2400, 2400, 2400, 2400, 2400) + _plans(2400, action="refused"), Account())
    assert b["committed_usd"] == 9600.0
    assert (b["slots_used"], b["slots_max"]) == (4, 4)
    assert b["within"] == ["T1", "T2", "T3", "T4"]
    assert b["beyond"] == [{"ticker": "T5", "rank": 5, "reason": "slot_cap", "position_usd": 2400.0}]
    assert b["skipped"] == [{"ticker": "T1", "rank": 6, "reason": "no_order"}]
    assert b["sentence"] == "Tomorrow's plans commit $9,600.00 of $10,000.00; 4 of 4 slots"


def test_cash_budget_cuts_on_the_equity_and_counts_positions_already_open():
    b = plan.cash_budget(_plans(2500, 2500, 2500, 2500, 2500), Account(max_open_positions=5))
    assert b["committed_usd"] == 10_000.0 and b["within"] == ["T1", "T2", "T3", "T4"]
    assert b["beyond"][0]["reason"] == "equity"
    two_open = plan.cash_budget(_plans(2400, 2400, 2400), Account(), open_positions=2)
    assert two_open["within"] == ["T1", "T2"] and two_open["beyond"][0]["reason"] == "slot_cap"
    assert two_open["sentence"] == "Tomorrow's plans commit $4,800.00 of $10,000.00; 4 of 4 slots (2 already open)"
    assert plan.cash_budget([], Account())["sentence"] == "Tomorrow's plans commit $0.00 of $10,000.00; 0 of 4 slots"
    assert plan.cash_budget(_plans(0, action="no_new_longs"), Account())["skipped"][0]["reason"] == "no_order"
    with pytest.raises(ValueError):
        plan.cash_budget([], Account(), open_positions=-1)


def test_cash_budget_reads_real_plans():
    plans = [burst(**TIGHT), burst(), burst(size_multiplier=0)]
    b = plan.cash_budget(plans, Account())
    assert b["within"] == ["XYZ", "XYZ"] and b["committed_usd"] == 2484.60 + 626.20
    assert b["skipped"][0]["reason"] == "no_order"


# ------------------------------------------------------------- notes -------


def test_account_notes_state_the_dollar_risk_the_cap_the_slots_and_the_broker_rules():
    notes = plan.account_notes(Account())
    assert notes[0] == "Risk per trade: $50.00 (0.5% of $10,000.00; his band is 0.25-1%)."
    assert notes[1] == "Position cap: $2,500.00 (25% of equity) in any one name."
    assert notes[2] == "Max 4 open positions (100% of equity if all are at the cap)."
    pdt = notes[3]
    for phrase in ("2026-06-04", "2027-10-20", "as if the old rule binds", "at most 3 same-day round trips",
                   "rolling 5 business days", "margin account under $25,000.00", "a same-day stop-out counts",
                   "a position held overnight never counts"):
        assert phrase in pdt, phrase
    assert notes[4] == ("Account type: margin with debt protection (no borrowing, no good-faith violations). "
                        "In a cash account buy only against settled cash (T+1); 3 good-faith violations in "
                        "12 months means 90 days of settled-cash-only.")
    assert notes[5] == ("Attach the protective stop the moment the buy fills, as a stop-MARKET order and "
                        "never a stop-limit (Fidelity mobile: \"Market + Stop Loss Protection\"; Active "
                        "Trader Pro: OTO/OTOCO).")
    assert len(notes) == len(plan.NOTE_TEMPLATES) == 6


def test_account_notes_say_when_the_risk_is_outside_his_band():
    assert plan.account_notes(Account(risk_pct=3))[0].endswith("his band is 0.25-1%, and this is outside it).")
    assert "$300.00" in plan.account_notes(Account(risk_pct=3))[0]


# ------------------------------------------------------------- the record --


def test_every_plan_and_follow_result_is_json_and_carries_the_contract_keys():
    for value in (burst(), burst(**TIGHT, size_multiplier=0), burst(close=100.0, low=90.0, high=100.0, open_=91.0, prev_close=95.0),
                  plan.anticipation_plan(ticker="ABC", close=5.00, box_high=5.10, box_low=4.90,
                                         lows_last3=[4.95, 4.98, 5.00], account=Account()),
                  plan.follow(PICK, FIVE), plan.follow(PICK, []), plan.cash_budget([burst()], Account()),
                  plan.RULES, plan.account_notes(Account())):
        json.dumps(value)
    p = burst()
    for key in ("entry_low", "entry_high", "stop", "risk_per_share", "shares", "position_usd", "risk_usd",
                "targets", "exits", "order_line", "skip_if_open_above", "eligible", "hazards", "multipliers"):
        assert key in p
    assert p["targets"]["low_pct"] == 8 and p["targets"]["high_pct"] == 20
    f = plan.follow(PICK, FIVE[:2])
    for key in ("ticker", "picked", "day", "entry_ref", "stop" if False else "current_stop", "last_close",
                "status", "instruction", "events", "unrealised_pct"):
        assert key in f
    assert f["status"] in plan.FOLLOW_STATUSES
    assert p["action"] in plan.ACTIONS and p["capped_by"] in plan.CAPPED_BY and p["stop_basis"] in plan.STOP_BASES


# ------------------------------------------------------------- RULES -------


def _module_ast() -> ast.Module:
    return ast.parse(SOURCE.read_text())


def _named_constants() -> dict[str, float]:
    """Every upper-case module-level name bound to a number."""
    found = {}
    for node in _module_ast().body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id.isupper() \
                and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, (int, float)) \
                and not isinstance(node.value.value, bool):
            found[node.targets[0].id] = node.value.value
    return found


def test_every_upper_case_number_in_the_module_is_archived_in_rules():
    """RULES is read off the source: the names its values are bound to must
    be every upper-case number the module names, so a number added later
    cannot escape the record in silence."""
    constants = _named_constants()
    assert len(constants) >= 40
    rules_node = next(node for node in _module_ast().body
                      if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                      and node.target.id == "RULES")
    names_in_rules = {v.id for v in rules_node.value.values if isinstance(v, ast.Name)}
    assert set(constants) == names_in_rules & set(constants), set(constants) - names_in_rules
    assert all(key.startswith("plan.") for key in plan.RULES)
    for name, value in constants.items():
        assert value in plan.RULES.values() and getattr(plan, name) == value
    assert all(isinstance(v, (int, float, str)) and not isinstance(v, bool) for v in plan.RULES.values())
    assert plan.RULES["plan.entry_window"] == plan.ENTRY_WINDOW


def test_no_function_spells_a_threshold_as_a_bare_literal():
    """Every number a function compares against is a named constant; the
    only literals allowed inside a body are 0, 1, 2 and 100."""
    literals = {}
    for node in ast.walk(_module_ast()):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for inner in ast.walk(ast.Module(body=node.body, type_ignores=[])):
                if isinstance(inner, ast.Constant) and isinstance(inner.value, (int, float)) \
                        and not isinstance(inner.value, bool) and inner.value not in (0, 1, 2, 100):
                    literals.setdefault(node.name, []).append(inner.value)
    assert not literals, literals


def test_the_constants_carry_the_briefs_values_and_their_source_marks():
    assert (plan.ENTRY_BELOW_PCT, plan.ENTRY_ABOVE_PCT, plan.SKIP_GAP_PCT, plan.ASSUMED_SLIPPAGE_PCT) == (2, 4, 8, 1)
    assert (plan.MAX_STOP_PCT, plan.IDEAL_STOP_PCT, plan.STOP_RISK_MULTIPLIER) == (4, 2, 0.5)
    assert (plan.TARGET_LOW_PCT, plan.TARGET_HIGH_PCT) == (8, 20)
    assert (plan.SELL_HALF_PCT, plan.ABNORMAL_DAY_PCT, plan.GAP_EXIT_PCT) == (8, 10, 20)
    assert (plan.TRAIL_CENTS, plan.TRAIL_CENTS_MAX) == (0.25, 0.50)
    assert (plan.SELL_HALF_DAY, plan.NO_PROGRESS_DAY, plan.TRAIL_FROM_DAY, plan.FINAL_EXIT_DAY, plan.ENTRY_DAY) == (3, 3, 3, 5, 1)
    assert (plan.TRIGGER_CENTS, plan.TRIGGER_FRACTION, plan.TRIGGER_LIMIT_PCT, plan.GAP_OK_PCT) == (0.02, 0.001, 1, 2)
    assert (plan.GAIN_CEILING_PCT, plan.EXTENSION_HAZARD_PCT, plan.HAZARD_MULTIPLIER) == (15, 20, 0.5)
    assert (plan.PDT_EQUITY_USD, plan.PDT_MAX_DAY_TRADES, plan.PDT_WINDOW_DAYS, plan.SETTLEMENT_DAYS) == (25_000, 3, 5, 1)
    assert (plan.GFV_LIMIT, plan.GFV_WINDOW_MONTHS, plan.GFV_RESTRICTION_DAYS) == (3, 12, 90)
    assert (plan.PDT_RULE_DELETED_ON, plan.PDT_PHASE_IN_ENDS) == ("2026-06-04", "2027-10-20")
    source = SOURCE.read_text()
    for name in _named_constants():
        block = source[:source.index(f"\n{name} = ")]
        comment = block[block.rfind("#:"):] if "#:" in block else ""
        assert any(mark in comment or mark in block[-600:] for mark in ("(B)", "(P)", "(T)", "(R)")) \
            or name in ("CENTS", "PCT_DECIMALS"), f"{name} has no source mark"


# ------------------------------------------------------------- boundaries --
# Each of these sits exactly on a comparison, so the `<=` / `<` choice is
# load-bearing rather than incidental (the mutation harness asked for them).


def test_a_risk_count_that_exactly_meets_the_cap_is_the_risk_budgets_decision():
    """$50 / $0.40 = 125 and $2,500 / $20 = 125: the cap did not cut."""
    s = size(20.00, 19.60, Account())
    assert s.shares == 125 and s.capped_by == "risk" and s.note is None


def test_a_burst_low_exactly_four_percent_under_the_fill_is_within_the_line():
    p = burst(close=100.0, low=96.96, high=101.0, open_=97.0, prev_close=95.0)   # 101.00 x 0.96
    assert p["stop_basis"] == "burst_low" and p["stop_pct"] == 4.0 and p["eligible"]


def test_an_anticipation_stop_exactly_four_percent_under_the_trigger_is_eligible():
    p = plan.anticipation_plan(ticker="ABC", close=10.30, box_high=10.38, box_low=9.90,
                               lows_last3=[10.00, 10.10, 10.20], account=Account())
    assert p["trigger"] == 10.40 and p["stop"] == 10.00 and p["stop_pct"] == 4.0
    assert p["eligible"] and p["action"] == "place_buy_stop"


def test_a_low_at_the_box_high_is_still_a_consolidation():
    p = plan.anticipation_plan(ticker="ABC", close=5.00, box_high=5.10, box_low=4.90,
                               lows_last3=[5.10], account=Account())
    assert p["stop"] == 5.10 and p["trigger"] == 5.12


def test_a_plan_whose_budget_cannot_buy_one_share_places_no_order():
    p = burst(close=5000.0, low=4990.0, high=5010.0, open_=4995.0, prev_close=4800.0)
    assert p["shares"] == 0 and p["capped_by"] == "none"
    assert p["action"] == "no_order" and p["order_line"] is None and p["eligible"]
    assert any("cannot buy one share" in n for n in p["notes"])


def test_follow_boundaries_sit_on_the_exact_prices():
    assert plan.follow(PICK, [bar(96.0, 97, 95.5, 96.5)])["events"][0]["event"] == "stopped_at_open"
    assert plan.follow(PICK, [bar(100, 101, 96.0, 97)])["status"] == "stopped"
    assert plan.follow(PICK, [bar(120.0, 125, 119, 123)])["events"][0]["event"] == "gap_exit"
    exact = plan.follow(PICK, [bar(101, 108.0, 100.5, 107)])
    assert exact["status"] == "sell_half" and exact["events"][0]["price"] == 108.0
    abnormal = plan.follow(PICK, [bar(101, 110.5, 100.5, 110.0)])
    assert [e["event"] for e in abnormal["events"]] == ["sell_half", "stop_raised", "abnormal_day"]
    assert plan.follow(PICK, [bar(101, 110.5, 100.5, 109.99)])["events"][-1]["event"] != "abnormal_day"


def test_follow_never_lowers_the_stop():
    """Half sold on day 1 at a high of 115 (stop 114.75); day 2 is an abnormal
    close whose high less 25 cents is BELOW that stop, and it stays put."""
    f = plan.follow(PICK, [bar(101, 115, 100.5, 114), bar(114.8, 114.9, 114.8, 114.85)])
    assert f["current_stop"] == 114.75
    assert f["events"][-1] == {"day": 2, "date": "2026-09-11", "event": "abnormal_day", "price": 114.85}


def test_follow_sells_at_least_half_of_an_odd_count():
    f = plan.follow({**PICK, "shares": 21}, [bar(101, 109, 100.5, 107)])
    assert "sell half (11 of 21 XYZ)" in f["instruction"]


def test_the_budget_counts_dollars_at_risk_over_the_plans_within_the_slots_alone():
    """Three plans, two free slots: the third is cut and its risk is not in
    the total, and the cut carries a sentence naming the cap."""
    account = plan.Account(equity=10_000, risk_pct=0.5, max_position_pct=25, max_open_positions=4)
    rows = [{"ticker": t, "action": "buy_at_open", "shares": 10, "position_usd": 1_000.0, "risk_usd": 50.0 + i}
            for i, t in enumerate(("AAA", "BBB", "CCC"))]
    budget = plan.cash_budget(rows, account, open_positions=2)
    assert budget["within"] == ["AAA", "BBB"] and [c["ticker"] for c in budget["cut"]] == ["CCC"]
    assert budget["at_risk_usd"] == 101.0
    assert "4-slot cap" in budget["cut"][0]["reason"] and "AAA, BBB" in budget["cut"][0]["reason"]
    over = plan.cash_budget([{**rows[0], "position_usd": 9_000.0}, {**rows[1], "position_usd": 2_000.0}], account)
    assert over["within"] == ["AAA"] and over["cut"][0]["reason"].startswith("the equity")
