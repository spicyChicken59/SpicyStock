"""src.plan: sizing, the burst and anticipation plans, follow-through, notes.

Every expected number below is hand arithmetic from the constants the
module names, written out in the docstring or beside the assertion, so a
constant that moves fails here for the number and not for the name.
"""
from __future__ import annotations

import ast
import json
from datetime import date
import math
from pathlib import Path

import pytest
from unittest import mock

from src import plan, report
from src.plan import Account, size

SOURCE = Path(plan.__file__)

#: close 20.00, low 19.85, high 20.10: the ticket's limit (+4%) is 20.80, the
#: highest fill it permits. The burst low is 4.57% under it, past his line;
#: the bar's midpoint, 19.975 -> 19.98 to cents, is 3.94% under it and under
#: the 20.00 buy stop: that is the stop. Between his ideal 2% and his 4%, so
#: the risk is halved to $25: $25 / $0.82 = 30 shares, $624.00 at the limit.
TIGHT = dict(ticker="XYZ", close=20.00, low=19.85, high=20.10, open_=19.90, prev_close=19.00, gain_pct=5.26)
#: close 20.00, low 18.00, high 20.10: the low caps the limit at 18.75 and
#: the midpoint 19.05 caps it at 19.84, both at or under the 20.00 buy stop,
#: so no limit exists that this bar can hold a stop under. The ticket is
#: withheld and the setup kept. (A bar reaching more than about 4.2% under
#: its close, with the close near the high, is this case.)
WIDE = dict(ticker="XYZ", close=20.00, low=18.00, high=20.10, open_=18.50, prev_close=19.00, gain_pct=5.26)


def burst(**overrides):
    return plan.burst_plan(**{**TIGHT, "account": Account(), **overrides})


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
    """Four prices, four rules, never one field: the 50.00 trigger, the 51.56
    ticket limit (49.50 / 0.96, under the +4% line), the 52.00 outer
    threshold where day 2 is spent, and the 50.50 indicative entry."""
    p = burst(close=50.00, low=49.50, high=50.20, open_=49.60, prev_close=47.00)
    assert p["entry_ref"] == 50.00                                 # the trigger
    assert p["entry_low"] == 49.00 == p["skip_if_open_below"]      # -2%
    assert p["limit"] == 51.56 == p["entry_high"]                  # the ticket's own limit
    assert p["day2_spent_above"] == 52.00 == p["skip_if_open_above"]   # +4%, the OUTER threshold
    assert p["limit"] < p["day2_spent_above"] and p["limit_basis"] == "stop_line"
    assert p["extended_above"] == 54.00                            # +8%
    assert p["planned_entry"] == 50.50                             # +1%, under the limit
    assert p["entry_window"] == "first 30 minutes"
    assert "$49.00" in p["pre_open_check"] and "$52.00" in p["pre_open_check"] and "$54.00" in p["pre_open_check"]
    assert "$51.56" in p["pre_open_check"] and "under that day-2 line" in p["pre_open_check"]


def test_the_stop_cascade_takes_the_burst_low_when_it_is_within_four_percent_of_the_limit():
    """Close 100, limit 104: the low 99.90 is 4.10 / 104 = 3.94% under it."""
    p = burst(close=100.0, low=99.90, high=100.60, open_=99.95, prev_close=95.0)
    assert p["stop_basis"] == "burst_low"
    assert p["stop"] == 99.90
    assert p["stop_pct"] == 3.94
    assert p["stop_note"] is None
    assert p["eligible"] and p["reason"] is None
    assert p["sizing_price"] == 104.0 and p["limit"] == 104.0 == p["order_json"]["limit_price"]


def test_the_stop_cascade_falls_to_the_range_midpoint_when_the_lows_ceiling_is_under_the_trigger():
    """Low 47.00 would cap the limit at 47 / 0.96 = 48.95, under the 50.00
    buy stop: no ticket can be written on it. The midpoint 49.00 caps it at
    51.04, which clears the trigger, so that is the limit and the stop."""
    p = burst(close=50.0, low=47.0, high=51.0, open_=47.5, prev_close=46.0)
    assert p["stop_basis"] == "half_range" and p["stop"] == 49.00
    assert p["limit"] == 51.04 and p["stop_pct"] == 4.0
    tried = plan.burst_limit(50.0, 47.0, 51.0)["tried"]
    assert [(t["basis"], t["ceiling"], t["room_above_trigger"]) for t in tried] \
        == [("burst_low", 48.95, False), ("half_range", 51.04, True)]
    assert p["eligible"] and p["action"] == "buy_at_open"


def test_a_narrowed_limit_brings_the_burst_low_back_inside_his_line():
    """The same bar the old fixed ceiling pushed onto the midpoint: at 104
    the 99.70 low was 4.13% away, past his line. At the limit its own
    ceiling names, 103.85, it is 4.00% and it is the stop."""
    p = burst(close=100.0, low=99.70, high=100.10, open_=99.80, prev_close=95.0)
    assert p["limit"] == 103.85 == plan.stop_line_ceiling(99.70)
    assert p["stop_basis"] == "burst_low" and p["stop"] == 99.70 and p["stop_pct"] == 4.0
    assert plan._pct(100 * (100.0 * 1.04 - 99.70) / (100.0 * 1.04)) == 4.13    # what it was at +4%
    assert p["eligible"]


def test_the_ticket_is_withheld_when_no_structural_stop_leaves_a_limit_above_the_trigger():
    """Low 90 caps the limit at 93.75 and the midpoint 95 caps it at 98.95,
    both under the 100.00 buy stop: no limit exists that this bar can hold a
    stop under, so the ticket is withheld and the setup kept. The reported
    limit falls back to the day-2 ceiling, which is not a price to buy at."""
    p = burst(close=100.0, low=90.0, high=100.0, open_=91.0, prev_close=95.0)
    assert p["eligible"] is False and p["ticket_refusal"] == "no_room_above_the_trigger"
    assert p["limit"] == 104.0 == p["day2_spent_above"] and p["limit_basis"] == "outer_ceiling"
    assert "not a limit this setup can be bought at" in p["limit_note"]
    assert p["stop_basis"] == "max_stop" and p["stop"] == 99.84 and p["stop_pct"] == 4.0
    assert p["reason"].startswith("ticket withheld: no limit above the $100.00 buy stop")
    assert "caps the limit at $93.75" in p["reason"] and "caps the limit at $98.95" in p["reason"] \
        and "the setup stands, the ticket does not" in p["reason"]
    assert p["action"] == "refused"
    assert p["order_line"] is None and p["order_json"] is None and p["order_readback"] is None
    assert p["order_terms"] is None
    assert "no_ticket_band" in p["flags"] and "There is no ticket to place" in p["pre_open_check"]
    assert p["shares"] == 6        # the card still shows a size: $25 / $4.16 at the 104 ceiling


def test_the_reviewers_ticket_is_narrowed_rather_than_published_as_safe():
    """Close 100, low 99.50, high 100.50. Sized at the old +1% fill the ticket
    read 24 shares (the cap) with $36 at risk; at a fixed 104 limit those
    shares risked $108 against a $50 budget with the 99.50 stop 4.33% away,
    and the closeout withheld it. The limit is now the highest price that
    stop is inside his line at -- 99.50 / 0.96 = 103.64 -- so the ticket
    exists and every fill it permits keeps the budget and the line."""
    p = burst(close=100.0, low=99.50, high=100.50, open_=99.60, prev_close=95.0)
    assert p["action"] == "buy_at_open" and p["eligible"] is True
    assert p["limit"] == 103.64 and p["day2_spent_above"] == 104.0 and p["limit_narrowed"] is True
    assert p["stop"] == 99.50 and p["stop_basis"] == "burst_low" and p["stop_pct"] == 3.99
    assert p["sizing_price"] == 103.64 and p["shares"] == 6 and p["risk_usd"] == 24.84   # inside the $25 half-budget
    assert p["order_json"]["limit_price"] == 103.64 and p["order_json"]["stop_price"] == 100.0
    assert p["stop_candidates"][1]["under_trigger"] is False      # the midpoint 100.00 is still no stop
    assert p["reason"] is None and any("multiplied by 0.5" in n for n in p["notes"])
    assert plan._pct(100 * (104.0 - 99.50) / 104.0) == 4.33      # what it was at the fixed ceiling


def test_an_eligible_ticket_keeps_the_budget_and_the_cap_at_the_limit():
    """Close 100, low 99.90: stop 99.90, 3.94% under the 104 limit, halved
    budget $25 / $4.10 = 6 shares. 6 x 4.10 = $24.60 <= $25 and 6 x 104 =
    $624 <= $2,500; a seventh share would break the budget."""
    p = burst(close=100.0, low=99.90, high=100.60, open_=99.95, prev_close=95.0)
    assert p["action"] == "buy_at_open" and p["shares"] == 6
    o = p["order_json"]
    assert o["quantity"] == o["then"]["quantity"] == 6 and o["limit_price"] == 104.0 and o["then"]["stop_price"] == 99.90
    assert p["risk_per_share"] == 4.10 and p["risk_usd"] == 24.60 and p["position_usd"] == 624.0
    assert p["shares"] * (o["limit_price"] - p["stop"]) <= p["sizing"]["budget_usd"] == 25.0
    assert (p["shares"] + 1) * (o["limit_price"] - p["stop"]) > p["sizing"]["budget_usd"]
    assert p["shares"] * o["limit_price"] <= p["sizing"]["cap_usd"] == 2500.0
    assert "Buy 6 XYZ" in p["order_line"] and p["sizing_basis"] == "order_limit" == plan.SIZING_BASIS
    assert "sized at the $104.00 limit" in p["sizing_note"] and "not a maximum loss" in p["sizing_note"]


def test_the_sizing_is_at_the_limit_and_the_resize_rule_carries_the_numbers():
    p = burst()     # TIGHT: limit 20.67 (19.85 / 0.96), stop 19.85, 3.97% -> risk halved to $25
    assert p["sizing_price"] == 20.67 == p["limit"] and p["planned_entry"] == 20.20
    assert "indicative" in p["planned_entry_note"] and "not a fill" in p["planned_entry_note"]
    assert p["risk_per_share"] == 0.82
    assert p["multipliers"] == {"regime": 1.0, "hazard": 1.0, "stop_risk": 0.5, "total": 0.5}
    assert p["stop_risk_multiplier"] == 0.5
    assert p["shares"] == 30                     # $25 / $0.82
    assert p["position_usd"] == 620.10           # 30 x 20.67, the most the ticket can commit
    assert p["risk_usd"] == 24.60                # 30 x 0.82, the most a permitted fill puts at risk
    assert "risk_halved" in p["flags"]
    assert "wider than his ideal 2%" in p["stop_risk_reason"] and "ticket's limit" in p["stop_risk_reason"]
    assert p["resize_rule"] == "if your fill differs, shares = $25.00 / (fill - $19.85), and no more than $2,500.00 of stock"


def test_every_eligible_burst_is_sized_at_half_risk_and_the_cap_can_bind_inside_a_plan():
    """The stop sits under the buy stop and the limit over it, so an eligible
    burst's stop is never inside his ideal 2% of the limit -- whether the
    limit is the day-2 ceiling (over 2% by the +4% alone) or the stop's own
    ceiling (4% by construction): the halving always applies. The position
    cap binds only with a larger risk budget: 3% risk is $300, halved
    $150 / $0.82 = 182 shares, over $2,500 / 20.67 = 120."""
    p = burst(account=Account(risk_pct=3))
    assert p["stop_pct"] == 3.97 and p["multipliers"]["stop_risk"] == 0.5
    assert p["shares"] == 120 and p["capped_by"] == "position_cap"
    assert p["position_usd"] == 2480.40 and p["risk_usd"] == 98.40
    assert "position_capped" in p["flags"] and "risk_halved" in p["flags"]
    assert p["shares"] * p["sizing_price"] <= 2500.0 < (p["shares"] + 1) * p["sizing_price"]
    for kw in (dict(), dict(close=50.00, low=49.95, high=50.20, open_=49.98, prev_close=47.00),
               dict(close=100.0, low=99.50, high=100.50, open_=99.60, prev_close=95.0),
               dict(close=50.0, low=47.0, high=51.0, open_=47.5, prev_close=46.0)):
        q = burst(**kw)
        assert q["eligible"] and q["stop_pct"] > plan.IDEAL_STOP_PCT, (kw, q["stop_pct"])


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


def test_the_plans_exits_are_from_the_indicative_entry():
    p = burst()
    assert [r["price"] for r in p["exits"][:3]] == [21.82, 22.22, 24.24]   # 20.20 x 1.08 / 1.10 / 1.20
    assert p["exits"] == plan.exit_schedule(20.20, 19.85)
    assert p["targets"] == plan.targets(20.20, 20.00)
    assert p["planned_entry"] == 20.20 <= p["limit"] and p["planned_entry_capped"] is False


def test_the_order_line_is_a_fidelity_buy_stop_limit_with_the_stop_attached():
    p = burst()
    assert p["action"] == "buy_at_open"
    assert p["order_line"] == ("Buy 30 XYZ stop-limit: stop $20.00 limit $20.67, day · "
                               "OTO sell 30 XYZ stop-loss $19.85 GTC")
    assert p["order_readback"] == ("Buy 30 XYZ stop limit 20.00 / 20.67 day, "
                                   "one-triggers-the-other sell 30 XYZ stop loss 19.85 GTC")
    assert p["order_json"] == {
        "symbol": "XYZ", "action": "buy", "quantity": 30, "order_type": "stop_limit",
        "stop_price": 20.00, "limit_price": 20.67, "time_in_force": "day",
        "conditional": "one_triggers_the_other",
        "then": {"action": "sell", "quantity": 30, "order_type": "stop", "stop_price": 19.85,
                 "time_in_force": "gtc"},
    }
    assert p["order_json"]["limit_price"] < p["day2_spent_above"]   # the ticket is not the +4% line


def test_no_plain_limit_fallback_is_published():
    """A limit order has no trigger and is not this ticket: nothing offers it."""
    assert "fallback_line" not in burst() and "fallback_line" not in plan.NO_ORDER
    assert "fallback" not in " ".join(burst()["order_terms"]).lower()


def test_the_ticket_states_what_it_enforces_and_what_it_leaves_to_the_reader():
    terms = burst()["order_terms"]
    assert len(terms) == 4
    assert terms[0].startswith("A day order rests until the close unless you cancel it.")
    assert "first 30 minutes" in terms[0] and "cancel it yourself" in terms[0] and "SpicyStock places and cancels nothing" in terms[0]
    assert terms[1].startswith("An open above the $20.67 limit does not fill at the open") and "cancel it" in terms[1]
    assert terms[2].startswith("An open under $19.60 is the burst failing") and "$20.00" in terms[2]
    assert terms[3].startswith("The sell stop at $19.85 is attached the moment the buy fills")
    assert "$20.80" not in " ".join(terms)     # the outer +4% line is not a ticket term
    assert "30 minutes" not in terms[1] + terms[2] + terms[3]      # DAY is never said to expire with the window
    anticipation = plan.anticipation_plan(ticker="ABC", close=5.00, box_high=5.10, box_low=4.90,
                                          lows_last3=[5.00, 5.02, 5.05], account=Account())
    assert len(anticipation["order_terms"]) == 3 and "skip line" not in " ".join(anticipation["order_terms"])
    assert "cancel the day order yourself" in plan.dated_schedule(burst(), __import__("datetime").date(2026, 9, 10))[0]["instruction"]


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
    yellow = burst(size_multiplier=0.5)   # $50 x 0.5 x 0.5 = $12.50 / $0.82 = 15
    assert yellow["shares"] == 15 and yellow["action"] == "buy_at_open"
    assert yellow["multipliers"] == {"regime": 0.5, "hazard": 1.0, "stop_risk": 0.5, "total": 0.25}


def test_hazards_halve_the_size_with_the_reason_and_never_veto():
    hot = burst(gain_pct=15.0)
    assert hot["hazards"] == [{"kind": "gain_over_15", "multiplier": 0.5,
                               "detail": hot["hazards"][0]["detail"]}]
    assert "worst cell in the only event study" in hot["hazards"][0]["detail"]
    assert hot["hazard_multiplier"] == 0.5
    assert hot["multipliers"]["total"] == 0.25 and hot["shares"] == 15     # $12.50 / $0.82
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
    p = burst(**WIDE)
    assert p["burst"] == {"close": 20.0, "low": 18.0, "high": 20.1, "open": 18.5, "prev_close": 19.0,
                          "gain_pct": 5.26, "gap_pct": -2.63, "dollar_move": 1.50, "close_in_range_pct": 95.24}
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
    """Cheap: trigger 5.10 + 0.02 = 5.12, limit 5.12 x 1.01 = 5.1712 -> 5.17;
    the stop 5.00 is 0.17 / 5.17 = 3.29% under the limit, halved budget
    $25 / $0.17 = 147. Dear: trigger 81.00 + 0.08 = 81.08, limit 81.89; the
    stop 80.00 is 1.89 / 81.89 = 2.31% under it, halved: $25 / $1.89 = 13,
    under the $2,500 / 81.89 = 30 the cap allows."""
    cheap = plan.anticipation_plan(ticker="ABC", close=5.00, box_high=5.10, box_low=4.90,
                                   lows_last3=[5.00, 5.02, 5.05], account=Account())
    assert cheap["trigger_cushion"] == 0.02 and cheap["trigger"] == 5.12
    assert cheap["limit"] == 5.17
    assert cheap["stop"] == 5.00 and cheap["stop_alt"] == 5.05
    assert cheap["stop_pct"] == 3.29 and cheap["sizing_price"] == 5.17
    assert cheap["eligible"] and cheap["action"] == "place_buy_stop"
    assert cheap["multipliers"]["stop_risk"] == 0.5 and cheap["shares"] == 147
    assert cheap["risk_usd"] == 24.99 and cheap["position_usd"] == 759.99
    assert cheap["order_line"] == ("Buy 147 ABC stop-limit: stop $5.12 limit $5.17, day · "
                                   "OTO sell 147 ABC stop-loss $5.00 GTC")
    assert cheap["order_json"]["order_type"] == "stop_limit" and cheap["order_json"]["stop_price"] == 5.12
    assert cheap["planned_entry"] == 5.12 and "sized at the $5.17 limit" in cheap["planned_entry_note"]
    dear = plan.anticipation_plan(ticker="DEF", close=80.0, box_high=81.0, box_low=78.0,
                                  lows_last3=[80.0, 80.2, 80.5], account=Account())
    assert dear["trigger_cushion"] == 0.08 and dear["trigger"] == 81.08
    assert dear["limit"] == 81.89
    assert dear["stop"] == 80.0 and dear["stop_pct"] == 2.31
    assert dear["multipliers"]["stop_risk"] == 0.5
    assert dear["shares"] == 13 and dear["capped_by"] == "risk"
    assert dear["shares"] * (dear["limit"] - dear["stop"]) <= 25.0 < (dear["shares"] + 1) * (dear["limit"] - dear["stop"])
    assert dear["entry_ref"] == 81.08 and dear["kind"] == "anticipation"


def test_anticipation_withholds_the_ticket_when_the_stop_is_past_four_percent_of_the_limit():
    """Trigger 5.12, limit 5.17, stop 4.80: 0.37 / 5.17 = 7.16%."""
    p = plan.anticipation_plan(ticker="ABC", close=5.00, box_high=5.10, box_low=4.70,
                               lows_last3=[4.80, 4.85, 4.90], account=Account())
    assert p["stop_pct"] == 7.16
    assert not p["eligible"] and p["action"] == "refused"
    assert p["reason"].startswith("ticket withheld: at the $5.17 limit") and "7.16%" in p["reason"]
    assert p["order_line"] is None and p["order_terms"] is None and "wide_stop" in p["flags"]
    assert p["shares"] > 0 and p["exits"]                                    # the setup is kept
    # the old rule measured the stop from the trigger: 4.95 is 3.43% under 5.12 and
    # was eligible; at the 5.17 limit it is 0.22 / 5.17 = 4.26%, past the line
    old = plan.anticipation_plan(ticker="ABC", close=5.00, box_high=5.10, box_low=4.90,
                                 lows_last3=[4.95, 4.98, 5.00], account=Account())
    assert old["stop_pct"] == 4.26 and old["action"] == "refused"


def test_anticipation_publishes_the_gap_rule_the_open_entry_and_the_exits():
    p = plan.anticipation_plan(ticker="ABC", close=5.00, box_high=5.10, box_low=4.90,
                               lows_last3=[5.00, 5.02, 5.05], account=Account())
    assert p["gap_ok_above"] == 5.10
    assert p["gap_rule"] == "an open more than 2% above $5.00 (over $5.10) is gapped: catalyst check before buying"
    assert p["open_entry"].startswith("MOO/OPG at the open only for the top 2 names")
    assert p["exits"] == plan.exit_schedule(5.12, 5.00)
    assert p["targets"]["low"] == 5.53 and p["targets"]["note"] is None     # $5.00 is not under $5
    cheap = plan.anticipation_plan(ticker="ABC", close=4.99, box_high=5.10, box_low=4.90,
                                   lows_last3=[4.99, 5.02, 5.05], account=Account())
    assert cheap["targets"]["note"] == "under $5 bursts can run 20-40%"
    assert p["stop_basis"] == "lowest low of the last 3 sessions"
    one = plan.anticipation_plan(ticker="ABC", close=5.00, box_high=5.10, box_low=4.90,
                                 lows_last3=[5.00], account=Account())
    assert one["stop"] == 5.00 and one["stop_basis"] == "lowest low of the last 1 sessions"
    assert plan.anticipation_plan(ticker="ABC", close=5.00, box_high=5.10, box_low=4.90,
                                  lows_last3=[5.00], account=Account(), size_multiplier=0)["action"] == "no_new_longs"


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
    assert f["current_stop"] == 96.0 and f["remaining"] == 20 and f["sold"] == 0
    assert "If you take this plan, buy 20 XYZ per the ticket" in f["instruction"] and "$96.00" in f["instruction"]


def test_follow_stops_on_a_day_one_low_at_the_stop():
    f = plan.follow(PICK, [bar(100, 101, 95.5, 97)])
    assert f["status"] == "stopped" and f["day"] == 1
    assert f["events"] == [{"day": 1, "date": "2026-09-11", "event": "stopped", "price": 96.0, "shares": 20, "remaining": 0}]
    assert f["exit_price"] == 96.0 and f["result_pct"] == -4.0 and f["remaining"] == 0 and f["sold"] == 20
    assert f["instruction"] == "Day 1: 20 XYZ stopped at $96.00 (-4.0%)."


def test_follow_stops_at_the_open_on_a_gap_below_the_stop():
    f = plan.follow(PICK, [bar(94, 95, 93, 94.5)])
    assert f["status"] == "stopped"
    assert f["events"][0]["event"] == "stopped_at_open" and f["events"][0]["price"] == 94.0
    assert (f["events"][0]["shares"], f["events"][0]["remaining"]) == (20, 0)
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
    assert f["events"][-1] == {"day": 3, "date": "2026-09-11", "event": "no_progress", "price": 100.0, "shares": 20, "remaining": 0}
    assert f["exit_price"] == 100.0 and f["result_pct"] == 0.0
    assert "at or below the $100.00 entry: no follow-through, exit 20 XYZ" in f["instruction"]


FIVE = [bar(101, 102, 100.5, 101.5), bar(101.5, 103, 101, 102.5), bar(102.5, 104, 102, 103.5),
        bar(103.5, 105, 103, 104.5), bar(104.5, 106, 104, 105.5)]


def test_follow_trails_after_day_three_then_exits_on_day_five():
    four = plan.follow(PICK, FIVE[:4])
    assert four["status"] == "sell_into_strength" and four["day"] == 4
    assert four["current_stop"] == 103.0
    assert four["events"][-1] == {"day": 4, "date": "2026-09-11", "event": "stop_trailed", "price": 103.0}
    assert "10 of 20 XYZ sold, sell the remaining 10 into strength by day 5 with the stop at $103.00" in four["instruction"]
    assert four["sold"] == 10 and four["remaining"] == 10
    five = plan.follow(PICK, FIVE)
    assert five["status"] == "exit" and five["day"] == 5
    assert five["events"][-1] == {"day": 5, "date": "2026-09-11", "event": "day5_exit", "price": 105.5, "shares": 10, "remaining": 0}
    assert five["result_pct"] == 5.5 and five["current_stop"] == 104.0 and five["remaining"] == 0
    assert five["instruction"] == "Day 5: closed at $105.50 (+5.5%): exit the remainder (10 of 20 XYZ) into strength."


def test_follow_expires_past_the_window():
    f = plan.follow(PICK, FIVE + [bar(105, 107, 104.5, 106)])
    assert f["status"] == "expired" and f["day"] == 6 and f["sessions"] == 6
    assert "5-session window is over" in f["instruction"]


def test_follow_exits_at_the_open_on_a_twenty_percent_gap():
    f = plan.follow(PICK, [bar(121, 125, 120, 123)])
    assert f["status"] == "exit"
    assert f["events"] == [{"day": 1, "date": "2026-09-11", "event": "gap_exit", "price": 121.0, "shares": 20, "remaining": 0}]
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
    assert b["sentence"] == "Model allocation: tomorrow's tickets would commit $9,600.00 of the configured $10,000.00; 4 of 4 slots"
    kinds = {(c["ticker"], c["kind"]) for c in b["cut"]}
    assert kinds == {("T5", "slot_cap"), ("T1", "withheld")} and all(c["kind"] in plan.CUT_KINDS for c in b["cut"])
    withheld = next(c for c in b["cut"] if c["kind"] == "withheld")
    assert withheld["reason"].startswith("ticket withheld")      # the sixth plan is the refused one, looked up by rank


def test_cash_budget_cuts_on_the_equity_and_counts_positions_already_open():
    b = plan.cash_budget(_plans(2500, 2500, 2500, 2500, 2500), Account(max_open_positions=5))
    assert b["committed_usd"] == 10_000.0 and b["within"] == ["T1", "T2", "T3", "T4"]
    assert b["beyond"][0]["reason"] == "equity"
    two_open = plan.cash_budget(_plans(2400, 2400, 2400), Account(), open_positions=2)
    assert two_open["within"] == ["T1", "T2"] and two_open["beyond"][0]["reason"] == "slot_cap"
    assert two_open["sentence"] == "Model allocation: tomorrow's tickets would commit $4,800.00 of the configured $10,000.00; 4 of 4 slots (2 open model plans)"
    assert "(1 open model plan)" in plan.cash_budget(_plans(2400), Account(), open_positions=1)["sentence"]
    assert plan.cash_budget([], Account())["sentence"] == "Model allocation: tomorrow's tickets would commit $0.00 of the configured $10,000.00; 0 of 4 slots"
    assert plan.cash_budget(_plans(0, action="no_new_longs"), Account())["skipped"][0]["reason"] == "no_order"
    with pytest.raises(ValueError):
        plan.cash_budget([], Account(), open_positions=-1)


def test_cash_budget_reads_real_plans():
    """XYZ: 30 x 20.67 = $620.10. ABC: close 50, low 49.95 caps the limit at
    52.03, over the 52.00 day-2 ceiling, so the ceiling stands; 2.05 / 52 =
    3.94% under it, halved $25 / $2.05 = 12 shares, $624.00. RED is sized at
    zero by breadth; WIDE's ticket is withheld by the stop rule."""
    plans = [burst(), burst(ticker="ABC", close=50.00, low=49.95, high=50.20, open_=49.98, prev_close=47.00),
             burst(ticker="RED", size_multiplier=0), burst(ticker="WID", **{k: v for k, v in WIDE.items() if k != "ticker"})]
    assert plans[1]["limit_basis"] == "outer_ceiling" and plans[1]["limit"] == 52.00
    b = plan.cash_budget(plans, Account())
    assert b["within"] == ["XYZ", "ABC"] and b["committed_usd"] == 620.10 + 624.0
    assert [(c["ticker"], c["kind"]) for c in b["cut"]] == [("RED", "no_new_longs"), ("WID", "withheld")]
    assert b["cut"][1]["reason"] == plans[3]["reason"]


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


def test_a_ceiling_exactly_at_the_buy_stop_leaves_the_ticket_no_band():
    """96.00 / 0.96 is 100.00 to the cent, the buy stop itself: a limit there
    is a ticket with no band to fill in, so the low is passed over and the
    midpoint's ceiling is taken. One cent higher, 96.01 / 0.96 = 100.0104 ->
    100.01, clears the trigger and the low is the stop."""
    assert plan.stop_line_ceiling(96.00) == 100.00 and plan.stop_line_ceiling(96.01) == 100.01
    at = plan.burst_limit(100.0, 96.00, 100.0)
    assert at["tried"][0]["ceiling"] == 100.00 and at["tried"][0]["room_above_trigger"] is False
    assert at["stop_basis"] == "half_range" and at["limit"] == 102.08
    over = plan.burst_limit(100.0, 96.01, 100.0)
    assert over["stop_basis"] == "burst_low" and over["limit"] == 100.01
    p = burst(close=100.0, low=96.01, high=100.0, open_=97.0, prev_close=95.0)
    assert p["limit"] == 100.01 and p["stop"] == 96.01 and p["eligible"] and p["stop_pct"] == 4.0


def test_a_candidate_stop_at_or_over_the_buy_stop_is_no_stop():
    """A bar whose midpoint sits at its close: the low is past the line and
    the midpoint is not under the 100.00 buy stop, so nothing the bar
    supports is a stop, whatever its distance from the limit."""
    p = burst(close=100.0, low=100.0, high=105.0, open_=101.0, prev_close=95.0)
    assert [c["under_trigger"] for c in plan.burst_limit(100.0, 100.0, 105.0)["tried"]] == [False, False]
    assert p["ticket_refusal"] == "no_structural_stop" and not p["eligible"] and "wide_stop" in p["flags"]
    assert "is not under the $100.00 buy stop" in p["reason"]
    assert p["stop_basis"] == "max_stop"
    q = burst(close=100.0, low=99.50, high=100.50, open_=99.60, prev_close=95.0)
    assert q["stop_candidates"][1]["price"] == 100.0 and q["stop_candidates"][1]["under_trigger"] is False
    assert q["stop_basis"] == "burst_low"        # the midpoint is excluded, so the low carries it
    assert plan.burst_stop(104.0, 99.5, 100.5)["stop_basis"] == "half_range"     # with no trigger the guard is off


def test_an_anticipation_stop_exactly_four_percent_under_the_limit_is_eligible():
    """Trigger 10.38 + 0.02 = 10.40, limit 10.40 x 1.01 = 10.504 -> 10.50;
    the stop 10.08 is 0.42 / 10.50 = 4.0% under it. A cent lower is 4.1%."""
    p = plan.anticipation_plan(ticker="ABC", close=10.30, box_high=10.38, box_low=9.90,
                               lows_last3=[10.08, 10.10, 10.20], account=Account())
    assert p["trigger"] == 10.40 and p["limit"] == 10.50 and p["stop"] == 10.08 and p["stop_pct"] == 4.0
    assert p["eligible"] and p["action"] == "place_buy_stop"
    q = plan.anticipation_plan(ticker="ABC", close=10.30, box_high=10.38, box_low=9.90,
                               lows_last3=[10.07, 10.10, 10.20], account=Account())
    assert q["stop_pct"] == 4.1 and not q["eligible"] and q["action"] == "refused"


def test_a_low_at_the_box_high_is_still_a_consolidation():
    p = plan.anticipation_plan(ticker="ABC", close=5.00, box_high=5.10, box_low=4.90,
                               lows_last3=[5.10], account=Account())
    assert p["stop"] == 5.10 and p["trigger"] == 5.12


def test_a_plan_whose_budget_cannot_buy_one_share_places_no_order():
    """Close 5,000, limit 5,200, low 4,995 is 205 / 5,200 = 3.94% under it:
    eligible, but the halved $25 cannot buy one share at $205 of risk."""
    p = burst(close=5000.0, low=4995.0, high=5010.0, open_=4998.0, prev_close=4800.0)
    assert p["shares"] == 0 and p["capped_by"] == "none"
    assert p["action"] == "no_order" and p["order_line"] is None and p["eligible"]
    assert any("cannot buy one share" in n for n in p["notes"])
    b = plan.cash_budget([p], Account())
    assert b["cut"] == [{"ticker": "XYZ", "kind": "no_shares", "reason": ("the configured account cannot size it: $205.00 at risk "
                                                                          "per share against a $50.00 risk budget comes to no whole share")}]


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
    assert f["events"][0] == {"day": 1, "date": "2026-09-11", "event": "sell_half", "price": 108.0, "shares": 11, "remaining": 10}
    assert f["sold"] == 11 and f["remaining"] == 10


def test_a_three_share_plan_sells_two_then_one_and_the_quantities_reconcile():
    """The reviewer's case: 3 shares at 100, stop 99; day 1 reaches +8%, so
    2 of 3 go at 108 and the stop rises to 108.75; day 2 opens at 102 under
    it, so the remaining 1 goes at the open. 2 + 1 = 3, nothing negative."""
    three = {**PICK, "shares": 3, "stop": 99.0}
    f = plan.follow(three, [bar(101, 109, 100.5, 107), bar(102, 103, 101, 102.5)])
    sales = [(e["event"], e["price"], e["shares"], e["remaining"]) for e in f["events"] if "shares" in e]
    assert sales == [("sell_half", 108.0, 2, 1), ("stopped_at_open", 102.0, 1, 0)]
    assert f["status"] == "stopped" and f["exit_price"] == 102.0 and f["remaining"] == 0 and f["sold"] == 3
    assert "sell half (2 of 3 XYZ)" in plan.follow(three, [bar(101, 109, 100.5, 107)])["instruction"]
    assert "1 XYZ stopped at the open" in f["instruction"]
    assert sum(e["shares"] for e in f["events"] if "shares" in e) == 3
    assert all(e["remaining"] >= 0 for e in f["events"] if "remaining" in e)


def test_a_one_share_plan_sells_whole_and_settles_with_no_phantom_half():
    """A single share cannot be halved: the +8% rule sells it and the model
    holds nothing after, so a later bar under the raised stop books no exit."""
    one = {**PICK, "shares": 1, "stop": 99.0}
    f = plan.follow(one, [bar(101, 109, 100.5, 107), bar(102, 103, 101, 102.5)])
    assert f["events"] == [{"day": 1, "date": "2026-09-11", "event": "sell_half", "price": 108.0, "shares": 1, "remaining": 0}]
    assert f["status"] == "exit" and f["exit_price"] == 108.0 and f["day"] == 1
    assert f["remaining"] == 0 and f["sold"] == 1 and f["half_sold"]
    assert "sell all 1 XYZ (a position of 1 cannot be halved)" in f["instruction"] and "the +8% rule closes it" in f["instruction"]
    at_close = plan.follow(one, [bar(101, 102, 100.5, 101.5), bar(101.5, 103, 101, 102.5), bar(102.5, 104, 102, 103.5)])
    assert at_close["status"] == "exit" and at_close["exit_price"] == 103.5
    assert at_close["events"][-1] == {"day": 3, "date": "2026-09-11", "event": "sell_half", "price": 103.5, "shares": 1, "remaining": 0}
    assert "the day-3 rule closes it" in at_close["instruction"]


def test_an_even_count_sells_exactly_half_then_the_rest():
    """Half (10 of 20) at 108 on day 1, the stop raised to 108.75; every
    later bar opens and holds above it and closes under the +10% abnormal
    line, so the other 10 leave at the day-5 close."""
    f = plan.follow(PICK, [bar(101, 109, 100.5, 107), bar(109, 109.5, 108.9, 109.2), bar(109.2, 109.8, 109.0, 109.5),
                           bar(109.5, 109.9, 109.3, 109.7), bar(109.7, 109.95, 109.5, 109.8)])
    sales = [(e["event"], e["shares"], e["remaining"]) for e in f["events"] if "shares" in e]
    assert sales == [("sell_half", 10, 10), ("day5_exit", 10, 0)]
    assert f["status"] == "exit" and f["remaining"] == 0 and f["sold"] == 20 and f["exit_price"] == 109.8


def test_the_budget_counts_dollars_at_risk_over_the_plans_within_the_slots_alone():
    """Three plans, two free slots: the third is cut and its risk is not in
    the total, and the cut carries a sentence naming the cap."""
    account = plan.Account(equity=10_000, risk_pct=0.5, max_position_pct=25, max_open_positions=4)
    rows = [{"ticker": t, "action": "buy_at_open", "shares": 10, "position_usd": 1_000.0, "risk_usd": 50.0 + i}
            for i, t in enumerate(("AAA", "BBB", "CCC"))]
    budget = plan.cash_budget(rows, account, open_positions=2)
    assert budget["within"] == ["AAA", "BBB"] and [c["ticker"] for c in budget["cut"]] == ["CCC"]
    assert budget["at_risk_usd"] == 101.0
    assert "4-slot model cap" in budget["cut"][0]["reason"] and "AAA, BBB" in budget["cut"][0]["reason"]
    assert "2 open model plans" in budget["cut"][0]["reason"] and budget["cut"][0]["kind"] == "slot_cap"
    over = plan.cash_budget([{**rows[0], "position_usd": 9_000.0}, {**rows[1], "position_usd": 2_000.0}], account)
    assert over["within"] == ["AAA"] and over["cut"][0]["reason"].startswith("the configured equity") and over["cut"][0]["kind"] == "equity"


def test_a_plan_the_account_cannot_size_is_cut_and_says_why():
    account = plan.Account(equity=100, risk_pct=0.5, max_position_pct=25, max_open_positions=4)
    rows = [{"ticker": "BIG", "action": "no_order", "shares": 0, "position_usd": 0.0, "risk_usd": 0.0, "risk_per_share": 4.03},
            {"ticker": "RED", "action": "no_new_longs", "shares": 0, "position_usd": 0.0, "risk_usd": 0.0}]
    budget = plan.cash_budget(rows, account)
    assert budget["within"] == [] and budget["at_risk_usd"] == 0.0
    cut = {c["ticker"]: c["reason"] for c in budget["cut"]}
    assert cut["BIG"] == "the configured account cannot size it: $4.03 at risk per share against a $0.50 risk budget comes to no whole share"
    assert cut["RED"] == "breadth sizes new positions at zero tonight"
    assert {c["ticker"]: c["kind"] for c in budget["cut"]} == {"BIG": "no_shares", "RED": "no_new_longs"}


# ---------------------------------------------- the constrained ticket -----
# The limit is the day-2 ceiling narrowed to the highest price at which the
# structural stop is still inside his 4% line. These hold it to the contract
# over a sweep of bar shapes rather than one fixture, and each sweep asserts
# it reached every branch, so a sweep that quietly stopped exercising a case
# would go red rather than pass on the ones that remain.


def bars_across_the_range():
    """Bars covering every shape the cascade can meet: six price decades, the
    low from touching the close to 12% under it, the close from the top of
    the bar to well inside it."""
    for close in (1.10, 4.99, 20.00, 63.45, 128.31, 499.99):
        for low_pct in (0.0, 0.05, 0.16, 0.5, 1.0, 2.0, 3.0, 3.5, 3.9, 4.0, 4.2, 5.0, 8.0, 12.0):
            low = round(close * (1 - low_pct / 100), 2)
            for high_pct in (0.0, 0.3, 1.5, 4.0):
                high = round(close * (1 + high_pct / 100), 2)
                if not low <= close <= high:
                    continue
                yield dict(ticker="BAR", close=close, low=low, high=high, open_=low,
                           prev_close=round(close / 1.05, 2), gain_pct=5.0)


def test_the_dated_schedule_skips_at_the_day_two_line_and_buys_up_to_the_limit():
    """The entry instruction the page quotes and Following saves: the range's
    top is the ticket's limit, the SKIP price is the day-2 threshold. An open
    between them is not a skip the plan asked for -- it is an open the resting
    order cannot fill at, which the ticket's own terms already cover."""
    p = burst(close=100.0, low=99.50, high=100.50, open_=99.60, prev_close=95.0)
    assert p["limit"] == 103.64 and p["skip_if_open_above"] == 104.0
    line = plan.dated_schedule(p, date(2026, 9, 10))[0]["instruction"]
    assert "inside $98.00\u2013$103.64" in line          # buy up to the ticket's limit
    assert "Skip it if it opens above $104.00" in line   # skip at the day-2 line
    assert "above $103.64" not in line
    # a plan from before the two were told apart carries only entry_high, and
    # nothing invents a second price for it
    older = {k: v for k, v in p.items() if k != "skip_if_open_above"}
    assert "Skip it if it opens above $103.64" in plan.dated_schedule(older, date(2026, 9, 10))[0]["instruction"]


def test_the_limit_rule_is_archived_so_two_records_cannot_be_read_as_one():
    """A record written under the fixed ceiling and one written under the
    constrained limit carry the same field names and different prices. The
    rule itself is archived, so ``app.rules_version`` separates them."""
    assert plan.LIMIT_RULE == "stop_constrained"
    assert plan.RULES["plan.limit_rule"] == plan.LIMIT_RULE
    assert plan.RULES["plan.entry_above_pct"] == plan.ENTRY_ABOVE_PCT    # the outer line is still archived
    assert plan.RULES["plan.precision.cent_floor_epsilon"] == plan.CENT_FLOOR_EPSILON
    fixture = json.loads((Path(__file__).resolve().parent / "fixtures" / "page" / "full.json").read_text())
    assert fixture["rules"]["plan"]["limit_rule"] == plan.LIMIT_RULE


def test_the_ticket_limit_is_never_over_the_day_two_ceiling():
    """The +4% line is an upper bound the narrowing can only come under, and
    ``entry_high`` -- the top of the zone the page and the walk read -- is the
    ticket's limit and not that line."""
    seen = set()
    for case in bars_across_the_range():
        p = burst(**case)
        close = plan._price(case["close"], "close")
        assert p["day2_spent_above"] == plan._at_pct(close, plan.ENTRY_ABOVE_PCT), case
        assert p["limit"] <= p["day2_spent_above"], case
        assert p["entry_high"] == p["limit"], case
        assert p["limit_basis"] in plan.LIMIT_BASES, case
        seen.add(p["limit_basis"] if p["eligible"] else "refused")
    assert seen == {"outer_ceiling", "stop_line", "refused"}, seen


def test_every_emitted_order_keeps_the_stop_under_the_trigger_and_inside_his_line():
    """``stop < trigger < limit`` on the ticket itself, and the stop inside
    MAX_STOP_PCT measured at that limit -- the highest fill it permits -- after
    the cent rounding, not before it."""
    emitted = 0
    for case in bars_across_the_range():
        p = burst(**case)
        if not p["order_json"]:
            continue
        emitted += 1
        o = p["order_json"]
        stop, trigger, limit = o["then"]["stop_price"], o["stop_price"], o["limit_price"]
        assert stop < trigger < limit, (case, stop, trigger, limit)
        assert plan._pct(100 * (limit - stop) / limit) <= plan.MAX_STOP_PCT, (case, stop, limit)
        assert limit == p["limit"] == p["sizing_price"] and trigger == p["entry_ref"], case
    assert emitted > 50, emitted


def test_the_synthetic_stop_can_never_buy_a_ticket():
    """``max_stop`` is a level the bar does not support: where the cascade
    reaches it there is no order, and every ticket's stop is a price the bar
    itself names."""
    synthetic = 0
    for case in bars_across_the_range():
        p = burst(**case)
        low = plan._price(case["low"], "low")
        mid = plan._money((low + plan._price(case["high"], "high")) / 2)
        if p["stop_basis"] == "max_stop":
            synthetic += 1
            assert not p["eligible"] and p["order_json"] is None and p["action"] == "refused", case
        if p["eligible"]:
            assert p["stop_basis"] in ("burst_low", "half_range"), case
            assert p["stop"] in (low, mid), case
    assert synthetic > 10, synthetic


def test_the_stop_line_ceiling_rounds_down_and_the_cent_above_it_would_break_the_line():
    """The ceiling is derived from a stop, so it rounds DOWN: at the rounded
    price the stop is still inside his line, and for a real share of stops one
    cent higher is not."""
    would_break = 0
    for cents in range(50, 60_000, 7):
        stop = cents / 100
        ceiling = plan.stop_line_ceiling(stop)
        assert ceiling <= stop / (1 - plan.MAX_STOP_PCT / 100) + 1e-9, stop
        assert plan._pct(100 * (ceiling - stop) / ceiling) <= plan.MAX_STOP_PCT, (stop, ceiling)
        up = plan._money(ceiling + 0.01)
        if plan._pct(100 * (up - stop) / up) > plan.MAX_STOP_PCT:
            would_break += 1
    assert would_break > 100, would_break
    # end to end: a $1.09 stop's exact ceiling is $1.135417, and a ticket at
    # the rounded-up $1.14 puts that stop 4.39% away -- past his line
    p = burst(close=1.10, low=1.09, high=1.15, open_=1.09, prev_close=1.02)
    assert p["limit"] == 1.13 and p["stop"] == 1.09 and p["stop_pct"] == 3.54 and p["eligible"]
    assert plan._pct(100 * (1.14 - 1.09) / 1.14) > plan.MAX_STOP_PCT


def test_the_indicative_entry_is_never_over_the_price_the_ticket_can_fill_at():
    capped = 0
    for case in bars_across_the_range():
        p = burst(**case)
        uncapped = plan._at_pct(plan._price(case["close"], "close"), plan.ASSUMED_SLIPPAGE_PCT)
        assert p["planned_entry"] == min(uncapped, p["limit"]) <= p["limit"], case
        if p["planned_entry_capped"]:
            capped += 1
            assert p["planned_entry"] == p["limit"] < uncapped, case
            assert "capped at the" in p["planned_entry_note"], case
        else:
            assert p["planned_entry"] == uncapped and "capped at" not in p["planned_entry_note"], case
    assert capped > 10, capped


def test_the_targets_and_the_exit_levels_are_quoted_from_the_capped_entry():
    """A bar whose limit lands under the close +1%: the aim and the exit
    ladder come off the limit, not off a price the ticket could never fill."""
    p = burst(close=126.88, low=122.57, high=127.45, open_=123.0, prev_close=120.0)
    assert p["planned_entry_capped"] and p["planned_entry"] == p["limit"] == 127.67
    assert p["targets"] == plan.targets(127.67, 126.88) and p["targets"]["low"] == 137.88
    assert p["exits"] == plan.exit_schedule(127.67, p["stop"])
    uncapped = plan._at_pct(126.88, plan.ASSUMED_SLIPPAGE_PCT)
    assert uncapped == 128.15 > p["limit"]
    assert p["targets"] != plan.targets(uncapped, 126.88)          # never the impossible entry
    assert p["exits"] != plan.exit_schedule(uncapped, p["stop"])


def test_the_day_two_threshold_is_carried_on_its_own_whatever_the_limit_does():
    """The outer extension rule survives the narrowing as its own price and
    its own sentence: it is the skip rule and it is never the order's limit."""
    for case in bars_across_the_range():
        p = burst(**case)
        close = plan._price(case["close"], "close")
        assert p["day2_spent_above"] == plan._at_pct(close, plan.ENTRY_ABOVE_PCT) == p["skip_if_open_above"]
        assert p["day2_spent_pct"] == plan.ENTRY_ABOVE_PCT
        assert f"over {plan._usd(p['day2_spent_above'])} (+{plan.ENTRY_ABOVE_PCT:g}%) day 2 is spent" \
            in p["pre_open_check"], case
        if p["order_terms"]:
            assert plan._usd(p["day2_spent_above"]) not in " ".join(p["order_terms"]) \
                or p["limit"] == p["day2_spent_above"], case


def test_the_pre_open_check_tells_the_outer_threshold_from_the_ticket_limit():
    narrowed = burst(close=100.0, low=99.50, high=100.50, open_=99.60, prev_close=95.0)
    assert "over $104.00 (+4%) day 2 is spent" in narrowed["pre_open_check"]
    assert "The ticket's own limit is $103.64, under that day-2 line" in narrowed["pre_open_check"]
    at_ceiling = burst(close=100.0, low=99.90, high=100.0, open_=99.95, prev_close=95.0)
    assert at_ceiling["limit"] == at_ceiling["day2_spent_above"] == 104.0
    assert "The ticket's own limit is $104.00, the day-2 line itself" in at_ceiling["pre_open_check"]
    withheld = burst(close=100.0, low=90.0, high=100.0, open_=91.0, prev_close=95.0)
    assert "over $104.00 (+4%) day 2 is spent" in withheld["pre_open_check"]
    assert "There is no ticket to place" in withheld["pre_open_check"]
    assert "limit is" not in withheld["pre_open_check"]


def test_a_limit_that_lands_on_the_buy_stop_emits_no_order_at_all():
    """Cent rounding can put the ceiling exactly on the trigger. A buy
    stop-limit with no band above its own trigger is not written: the setup
    stands, the ticket does not, and nothing invalid reaches fidelity_orders."""
    seen = 0
    for case in bars_across_the_range():
        got = plan.burst_limit(case["close"], case["low"], case["high"])
        for cand in got["tried"]:
            if cand["under_trigger"] and cand["limit"] <= plan._price(case["close"], "close"):
                seen += 1
                assert not cand["taken"], (case, cand)
        p = burst(**case)
        if not p["eligible"]:
            assert p["order_json"] is None and p["order_line"] is None and p["order_terms"] is None
            assert p["ticket_refusal"] in plan.TICKET_REFUSALS
            assert p["reason"].startswith(report.NO_TICKET_LEADS[1])
    assert seen > 10, seen
    with pytest.raises(ValueError, match="stop < trigger <= limit"):
        plan.fidelity_orders("XYZ", 1, trigger=100.0, limit=99.99, stop=96.0)


def test_the_plan_refuses_to_publish_a_limit_its_own_cascade_would_not_hold():
    """The ceiling is derived from a stop the cascade must reach AT it. The
    two are one rule: if they ever part, nothing is published for that name
    (make_plans logs and skips a ValueError) rather than a ticket whose stop
    the run does not stand behind."""
    for case in bars_across_the_range():
        p = burst(**case)
        if not p["eligible"]:
            continue
        got = plan.burst_stop(p["limit"], case["low"], case["high"], trigger=plan._price(case["close"], "close"))
        assert (got["stop_basis"], got["stop"]) == (p["stop_basis"], p["stop"]), case
    with mock.patch.object(plan, "burst_stop", lambda *a, **k: {
            "stop": 1.0, "stop_basis": "max_stop", "stop_pct": 4.0, "stop_note": None, "stop_candidates": []}):
        with pytest.raises(ValueError, match="but the cascade reaches"):
            burst()
