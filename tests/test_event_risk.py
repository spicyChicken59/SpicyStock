"""Known cash deals cannot yield orders; no match is not news clearance."""
from copy import deepcopy
from datetime import date, datetime, timedelta
import hashlib
import json

import pytest

from src import event_risk, plan


def registry():
    return deepcopy(event_risk.REGISTRY)


def burst(ticker="MG"):
    return plan.burst_plan(ticker=ticker, close=20, low=19.85, high=20.10,
                           open_=19.90, prev_close=19, gain_pct=5.26,
                           account=plan.Account())


@pytest.mark.parametrize("symbol,announced", [
    ("MG", "2026-09-18"), ("PRTH", "2026-09-21"), ("ARX", "2026-08-13"),
    ("BWIN", "2026-09-14"), ("ACVA", "2026-09-10"),
])
def test_public_announcement_is_first_blocked_session(symbol, announced):
    start = date.fromisoformat(announced)
    before = event_risk.classify(symbol, start - timedelta(days=1))
    assert before["blocked"] is False and before["status"] == "not_in_registry"
    on = event_risk.classify(symbol, start)
    assert on["blocked"] is True and on["status"] == "known_event"
    assert all(source["published_on"] <= announced for source in on["matches"][0]["sources"])


def test_mg_cash_deal_refuses_otherwise_executable_burst_without_changing_geometry():
    original = burst()
    assert original["eligible"] and original["order_json"]
    kept = deepcopy(original)
    rejected = event_risk.apply(original, "MG", "2026-10-09")
    assert original == kept
    assert rejected["eligible"] is False and rejected["action"] == "refused"
    assert "20.35" in rejected["reason"] and rejected["flags"].count("event_risk") == 1
    assert {name: rejected[name] for name in plan.NO_ORDER} == plan.NO_ORDER
    assert rejected["event_risk"]["matches"][0]["sources"][0]["url"].startswith("https://www.sec.gov/")
    for field in ("entry_ref", "limit", "stop", "shares", "position_usd"):
        assert rejected[field] == kept[field]


def test_same_deal_refuses_otherwise_executable_anticipation():
    original = plan.anticipation_plan(ticker="MG", close=20, box_high=20.05,
        box_low=19.70, lows_last3=[19.90, 19.85, 19.95], account=plan.Account())
    assert original["eligible"] and original["order_json"]
    rejected = event_risk.apply(original, "MG", date(2026, 10, 9))
    assert rejected["action"] == "refused" and rejected["eligible"] is False
    assert rejected["order_json"] is None and rejected["order_readback"] is None


def test_unlisted_stock_keeps_its_ticket_and_does_not_claim_news_clearance():
    original = burst("NVDA")
    result = event_risk.apply(original, "NVDA", "2026-10-09")
    assert {k: v for k, v in result.items() if k != "event_risk"} == original
    assert result["event_risk"]["blocked"] is False
    assert result["event_risk"]["coverage"] == "manual_known_events_only"
    assert "have not been cleared" in result["event_risk"]["reason"]


def test_unlisted_stock_does_not_restore_an_existing_refusal():
    original = burst("NVDA")
    original.update(eligible=False, action="refused", reason="A different gate withheld this plan", **plan.NO_ORDER)
    result = event_risk.apply(original, "NVDA", "2026-10-09")
    assert result["eligible"] is False and result["order_json"] is None
    assert result["reason"] == original["reason"]


def test_review_expiry_retains_block_and_names_uncertainty():
    assert event_risk.classify("MG", "2026-10-16")["status"] == "known_event"
    overdue = event_risk.classify("MG", "2026-10-17")
    assert overdue["blocked"] is True and overdue["status"] == "review_required"
    assert overdue["matches"][0]["review_overdue"] is True
    assert "review is overdue" in overdue["reason"]


def test_future_updates_are_not_claimed_as_earlier_session_evidence():
    before = event_risk.classify("ACVA", "2026-10-07")["matches"][0]
    after = event_risk.classify("ACVA", "2026-10-08")["matches"][0]
    assert [s["published_on"] for s in before["sources"]] == ["2026-09-10"]
    assert before["evidence_as_of"] == "2026-09-10"
    assert after["evidence_as_of"] == "2026-10-08" and len(after["sources"]) == 2


def test_sourced_resolution_ends_active_interval_but_never_clears_a_different_event():
    archived = registry()
    event = archived["events"][0]
    event["active_until"] = "2026-10-08"
    event["resolution"] = {**event["sources"][0], "published_on": "2026-10-08",
                           "title": "Synthetic termination for boundary test", "quote": "Agreement terminated."}
    before = event_risk.classify("MG", "2026-10-07", registry=archived)
    assert before["blocked"] is True
    assert before["matches"][0]["active_until"] is None
    assert "resolution" not in before["matches"][0]
    assert event_risk.classify("MG", "2026-10-08", registry=archived)["blocked"] is False
    assert event_risk.classify("PRTH", "2026-10-08", registry=archived)["blocked"] is True
    del event["resolution"]
    with pytest.raises(ValueError, match="source"):
        event_risk.classify("MG", "2026-10-08", registry=archived)


def test_archived_registry_replays_independently_of_current_registry(monkeypatch):
    archived = registry()
    before = event_risk.apply(burst(), "MG", "2026-10-09", registry=archived)
    current = registry()
    current["events"] = []
    monkeypatch.setattr(event_risk, "REGISTRY", current)
    assert event_risk.classify("MG", "2026-10-09")["blocked"] is False
    assert event_risk.apply(burst(), "MG", "2026-10-09", registry=archived) == before


def test_rules_archive_complete_evidence_with_a_digest_that_changes_with_source():
    archived = event_risk.RULES["event_risk.registry"]
    raw = json.dumps(archived, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    assert hashlib.sha256(raw).hexdigest() == event_risk.RULES["event_risk.registry_sha256"]
    changed = deepcopy(archived)
    changed["events"][0]["sources"][0]["quote"] += " A source correction."
    assert event_risk.registry_digest(changed) != event_risk.RULES["event_risk.registry_sha256"]


@pytest.mark.parametrize("field,value", [
    ("symbol", None), ("announced_on", "not a date"), ("review_due", "2026-09-01"),
    ("evidence_as_of", "2026-10-09"), ("sources", []), ("active_until", "2026-10-08"),
])
def test_malformed_evidence_fails_instead_of_clearing_stock(field, value):
    broken = registry()
    broken["events"][0][field] = value
    with pytest.raises(ValueError):
        event_risk.classify("MG", "2026-10-09", registry=broken)


@pytest.mark.parametrize("session", ["bad", "20261009", "2026-02-30", None, datetime(2026, 10, 9)])
def test_invalid_session_fails_closed(session):
    with pytest.raises(ValueError):
        event_risk.classify("MG", session)


def test_no_substring_match_or_shared_mutable_evidence():
    assert event_risk.classify("MGM", "2026-10-09")["blocked"] is False
    result = event_risk.classify(" mg ", "2026-10-09")
    assert result["symbol"] == "MG" and result["blocked"] is True
    result["matches"][0]["sources"].clear()
    assert event_risk.classify("MG", "2026-10-09")["matches"][0]["sources"]
