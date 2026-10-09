"""Combined-stage cash and slot boundaries, including uncertain old plans."""
from copy import deepcopy
from datetime import datetime, timezone
import json

import pytest

from src import allocation, pipeline, plan, provenance, record
from tests.test_pipeline import market, claude, evening


def ticket(ticker, kind, dollars, risk=10):
    return {"ticker": ticker, "kind": kind, "eligible": True,
            "action": "buy_at_open" if kind == "burst" else "place_buy_stop",
            "shares": 10, "position_usd": dollars, "risk_usd": risk,
            "order_line": "synthetic ticket", "order_json": {"symbol": ticker},
            "order_terms": [], "order_readback": "synthetic readback"}


def test_reaction_and_anticipation_share_the_same_slots_and_cut_orders():
    bursts = [{"ticker": "AAA", "plan": ticket("AAA", "burst", 400)}]
    watches = {"top": [{"ticker": "BBB", "plan": ticket("BBB", "anticipation", 300)}]}
    trades, beyond, budget = pipeline.allocate_plans(bursts, watches, plan.Account(equity=2000, max_open_positions=1), [])
    assert trades == ["AAA"] and beyond == []
    assert budget["within"] == ["AAA"] and budget["committed_usd"] == 400
    assert budget["slots_used"] == 1 and budget["cut"][0]["kind"] == "slot_cap"
    cut = watches["top"][0]["plan"]
    assert cut["eligible"] is True and cut["action"] == "refused"
    assert all(cut[name] is None for name in plan.NO_ORDER)
    assert cut["position_usd"] == 300  # Setup sizing stays visible for research.


def test_reserved_original_principal_limits_new_tickets_after_partial_sales():
    held = [{"ticker": "HELD", "status": "sell_half", "shares": 50, "remaining": 25,
             "entry_ref": 10, "limit": 12}]
    account = plan.Account(equity=2000, max_open_positions=10)
    budget = allocation.budget([ticket("AAA", "burst", 600), ticket("BBB", "anticipation", 900),
                                ticket("CCC", "anticipation", 500)], account, held)
    assert budget["committed_usd"] == 1100 and budget["within"] == ["AAA", "CCC"]
    assert budget["reserved_usd"] == 600 and budget["available_usd"] == 1400
    assert budget["cut"] == [{"ticker": "BBB", "setup_kind": "anticipation", "kind": "equity",
                              "reason": budget["cut"][0]["reason"]}]
    assert "$600.00 reserved" in budget["cut"][0]["reason"]


@pytest.mark.parametrize("status", ["pending", "uncertain", "unmeasured", "unreadable"])
def test_unknown_fill_and_missing_bars_do_not_free_money_or_symbols(status):
    account = plan.Account(equity=2000)
    held = [{"ticker": "HELD", "status": status, "shares": 50, "entry_ref": 10, "limit": 12}]
    budget = allocation.budget([ticket("HELD", "anticipation", 100)], account, held)
    assert budget["reserved_usd"] == 600 and budget["open_positions"] == 1
    assert budget["within"] == [] and budget["cut"][0]["kind"] == "existing_position"


def test_unknown_commitment_reserves_account_and_settled_rows_reserve_nothing():
    account = plan.Account(equity=2000)
    missing = allocation.budget([ticket("NEW", "burst", 1)], account, [{"ticker": "OLD", "status": "unmeasured"}])
    assert missing["reserved_usd"] == 2000 and missing["within"] == []
    resolved = [{"ticker": "OLD", "status": status, "shares": 50, "entry_ref": 10}
                for status in ("stopped", "exit", "expired", record.NOT_FILLED)]
    clear = allocation.budget([ticket("NEW", "burst", 500)], account, resolved)
    assert clear["reserved_usd"] == 0 and clear["open_positions"] == 0 and clear["within"] == ["NEW"]


@pytest.mark.parametrize("ceiling", [{"limit": 12}, {"entry_high": 12}])
def test_open_plan_replay_preserves_maximum_original_commitment(ceiling):
    replay = record.replay({"ticker": "OLD", "kind": "burst", "date": "2026-10-08",
                            "entry_ref": 10, "stop": 9.8, "shares": 50, **ceiling}, [])
    reserved = allocation.reservation([replay], plan.Account(equity=2000))
    assert replay["status"] == "pending" and replay["limit"] == 12
    assert reserved["open_committed_usd"] == 600


def test_one_symbol_cannot_receive_a_ticket_in_both_stages_or_double_risk():
    burst = ticket("SAME", "burst", 200, risk=4)
    watch = ticket("SAME", "anticipation", 300, risk=9)
    budget = allocation.budget([burst, watch], plan.Account(equity=2000), [])
    assert budget["within"] == ["SAME"] and budget["at_risk_usd"] == 4
    assert budget["admitted"] == [{"ticker": "SAME", "setup_kind": "burst"}]
    assert allocation.apply(burst, budget)["order_json"]
    assert allocation.apply(watch, budget)["order_json"] is None
    assert allocation.apply(watch, budget)["allocation"]["reason"] == "duplicate"


@pytest.mark.parametrize("value", [-1, float("inf"), float("nan"), True, "10"])
def test_invalid_reserved_money_is_rejected(value):
    with pytest.raises(ValueError):
        plan.cash_budget([], plan.Account(), open_committed_usd=value)


def test_money_comparison_uses_cents_at_the_exact_available_boundary():
    budget = plan.cash_budget([ticket("AAA", "burst", 0.1), ticket("BBB", "anticipation", 0.2)],
                              plan.Account(equity=1), open_committed_usd=0.7)
    assert budget["within"] == ["AAA", "BBB"] and budget["committed_usd"] == 0.3


def test_pipeline_retains_only_combined_admissions_and_verifies_them(market, claude, fake_resend, tmp_path, monkeypatch):
    monkeypatch.setenv("MAX_OPEN_POSITIONS", "1")
    rep, data, docs = evening(tmp_path, market)
    assert rep.exit_code() == 0, rep.failure
    picks = json.loads((docs / record.PICKS_FILE).read_text())
    assert [p["ticker"] for p in picks["picks"]] == ["AAA"]
    assert data["watchlist"]["top"][0]["plan"]["order_json"] is None
    assert data["cash_budget"]["slots_used"] == 1
    assert provenance.verify(data, picks, docs / provenance.OBJECT_DIR)["status"] == "PASS"
    tampered = deepcopy(data)
    tampered["cash_budget"]["reserved_usd"] += 1
    assert provenance.verify(tampered, picks, docs / provenance.OBJECT_DIR)["status"] == "FAIL"


def test_known_cash_deals_never_enter_either_stage_or_retained_picks(market, fake_alpaca, claude, fake_resend, tmp_path):
    """Same eligible synthetic shapes, official deal symbols and applicable dates."""
    fake_alpaca.add_history("MG", fake_alpaca.history["AAA"])
    fake_alpaca.add_history("PRTH", fake_alpaca.history["COIL"])
    symbols = [{"AAA": "MG", "COIL": "PRTH"}.get(t, t) for t in market]
    rep, data, docs = evening(tmp_path, symbols, now=datetime(2026, 10, 8, 22, 30, tzinfo=timezone.utc))
    assert rep.exit_code() == 0, rep.failure
    burst = next(row for row in data["bursts"] if row["ticker"] == "MG")
    watch = next(row for row in data["watchlist"]["top"] if row["ticker"] == "PRTH")
    for row in (burst, watch):
        assert row["plan"]["event_risk"]["blocked"] is True
        assert row["plan"]["order_json"] is None and row["plan"]["action"] == "refused"
    assert data["trades"] == [] and data["cash_budget"]["committed_usd"] == 0
    picks = json.loads((docs / record.PICKS_FILE).read_text())
    assert picks["picks"] == []
    assert provenance.verify(data, picks, docs / provenance.OBJECT_DIR)["status"] == "PASS"
