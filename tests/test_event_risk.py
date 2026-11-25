"""Known cash deals cannot yield orders; no match is not news clearance."""
from copy import deepcopy
from datetime import date, datetime, timedelta
import hashlib
import copy
import json
from pathlib import Path

import pytest

from src import event_risk, plan

ROOT = Path(__file__).resolve().parent.parent


def registry():
    return deepcopy(event_risk.REGISTRY)


def burst(ticker="MG"):
    return plan.burst_plan(ticker=ticker, close=20, low=19.85, high=20.10,
                           open_=19.90, prev_close=19, gain_pct=5.26,
                           account=plan.Account())


@pytest.mark.parametrize("symbol,announced", [
    ("MG", "2026-09-18"), ("PRTH", "2026-09-21"), ("ARX", "2026-08-13"),
    ("BWIN", "2026-09-14"), ("ACVA", "2026-09-10"), ("ZIM", "2026-02-16"),
    ("CCC", "2026-10-15"),
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


def test_zim_cash_deal_refuses_oct9_anticipation_ticket_for_monday_without_rewriting_geometry():
    # Inputs from the real 2026-10-09 publication at commit 62bce72d. The
    # source ticket was executable before the missing known event was added.
    original = plan.anticipation_plan(ticker="ZIM", close=29.99, box_high=30.35,
        box_low=29.66, lows_last3=[29.66, 29.9717, 29.91],
        account=plan.Account(equity=2000, risk_pct=0.5), size_multiplier=0.5)
    assert original["eligible"] and original["order_json"]
    assert (original["shares"], original["position_usd"], original["risk_usd"]) == (2, 61.36, 2.04)
    for session in ("2026-10-09", "2026-10-12", "2026-10-17"):
        rejected = event_risk.apply(original, "ZIM", session)
        assert rejected["eligible"] is False and rejected["action"] == "refused"
        assert {name: rejected[name] for name in plan.NO_ORDER} == plan.NO_ORDER
        assert "35.00" in rejected["reason"] and "Hapag-Lloyd" in rejected["reason"]
        assert rejected["event_risk"]["blocked"] is True
        for field in ("trigger", "limit", "stop", "shares", "position_usd", "risk_usd"):
            assert rejected[field] == original[field]
    assert original["eligible"] and original["order_json"]


def test_zim_cash_deal_also_refuses_reaction_but_not_unlisted_control():
    original = burst("ZIM")
    assert original["eligible"] and original["order_json"]
    rejected = event_risk.apply(original, "ZIM", "2026-10-09")
    assert rejected["eligible"] is False and rejected["order_json"] is None
    control = burst("NVDA")
    kept = event_risk.apply(control, "NVDA", "2026-10-09")
    assert {k: v for k, v in kept.items() if k != "event_risk"} == control


def test_zim_historical_evidence_does_not_borrow_later_merger_updates():
    before = event_risk.classify("ZIM", "2026-09-29")["matches"][0]
    setback = event_risk.classify("ZIM", "2026-09-30")["matches"][0]
    latest = event_risk.classify("ZIM", "2026-10-09")["matches"][0]
    assert [s["published_on"] for s in before["sources"]] == ["2026-02-16"]
    assert [s["published_on"] for s in setback["sources"]] == ["2026-02-16", "2026-09-30"]
    assert [s["published_on"] for s in latest["sources"]] == ["2026-02-16", "2026-09-30", "2026-10-06"]
    assert before["reason"] == setback["reason"] == latest["reason"]
    assert not any(word in before["reason"] for word in ("GCA", "revised proposal", "guidance"))
    assert latest["active_until"] is None


@pytest.mark.parametrize("kind", ["burst", "anticipation"])
def test_ccc_cash_deal_refuses_otherwise_executable_plans_without_changing_geometry(kind):
    # Synthetic mechanically eligible controls isolate the existing event gate.
    original = burst("CCC") if kind == "burst" else plan.anticipation_plan(
        ticker="CCC", close=20, box_high=20.05, box_low=19.70,
        lows_last3=[19.90, 19.85, 19.95], account=plan.Account())
    assert original["eligible"] and original["order_json"]
    kept = deepcopy(original)
    rejected = event_risk.apply(original, "CCC", "2026-10-20")
    assert rejected["eligible"] is False and rejected["action"] == "refused"
    assert {name: rejected[name] for name in plan.NO_ORDER} == plan.NO_ORDER
    assert "$7.75" in rejected["reason"] and "GTCR" in rejected["reason"] and "Elliott" in rejected["reason"]
    assert rejected["event_risk"]["matches"][0]["sources"][0]["url"].startswith("https://ir.cccis.com/")
    for field in ("entry_ref", "limit", "stop", "shares", "position_usd", "risk_usd"):
        assert rejected[field] == kept[field]
    assert original == kept


def test_ccc_oct19_existing_stop_and_market_refusals_remain_after_event_correction():
    # Retained real-publication inputs at 8fe55c28; this is a replay of its
    # refusal, not a rewritten historical record or a newly executable plan.
    original = plan.anticipation_plan(ticker="CCC", close=7.63, box_high=7.85,
        box_low=7.52, lows_last3=[7.59, 7.61, 7.61],
        account=plan.Account(equity=2000, risk_pct=0.5), size_multiplier=0)
    assert original["eligible"] is False and original["order_json"] is None
    assert "wide_stop" in original["flags"] and original["shares"] == 0
    rejected = event_risk.apply(original, "CCC", "2026-10-19")
    assert rejected["event_risk"]["blocked"] is True
    assert {name: rejected[name] for name in plan.NO_ORDER} == plan.NO_ORDER
    assert "wide_stop" in rejected["flags"] and rejected["shares"] == 0
    assert original["reason"] in rejected["notes"]
    assert all(note in rejected["notes"] for note in original["notes"])


def test_ccc_review_and_expected_closing_dates_never_resolve_the_pending_event():
    reviewed = event_risk.classify("CCC", "2026-10-20")
    assert reviewed["blocked"] is True and reviewed["status"] == "known_event"
    assert reviewed["matches"][0]["active_until"] is None
    assert reviewed["matches"][0]["evidence_as_of"] == "2026-10-15"
    for session in ("2026-12-18", "2027-04-01"):
        overdue = event_risk.classify("CCC", session)
        assert overdue["blocked"] is True and overdue["status"] == "review_required"
        assert overdue["matches"][0]["active_until"] is None


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
    # the entry's own due date, so a later review moves this test with the registry
    due = date.fromisoformat(next(e for e in event_risk.REGISTRY["events"] if e["symbol"] == "MG")["review_due"])
    assert event_risk.classify("MG", due.isoformat())["status"] == "known_event"
    overdue = event_risk.classify("MG", (due + timedelta(days=1)).isoformat())
    assert overdue["blocked"] is True and overdue["status"] == "review_required"
    assert overdue["matches"][0]["review_overdue"] is True
    assert "review is overdue" in overdue["reason"]


def test_the_november_review_adds_one_dated_source_and_resolves_nothing():
    """The 19 November 2026 review: MISTRAS's 28 October release is evidence only
    from its own date on, every entry is still unresolved, and the one deal a
    search excerpt says has closed (ACVA) stays blocked, because no bytes were
    captured to resolve it with (release-evidence/2026-11-19-event-review)."""
    before = event_risk.classify("MG", "2026-10-27")["matches"][0]
    after = event_risk.classify("MG", "2026-10-28")["matches"][0]
    assert [s["published_on"] for s in before["sources"]] == ["2026-09-18"] and before["evidence_as_of"] == "2026-09-18"
    assert [s["published_on"] for s in after["sources"]] == ["2026-09-18", "2026-10-28"]
    assert after["evidence_as_of"] == "2026-10-28"
    # the reason a ticket prints names the announcement alone, at every session
    assert before["reason"] == after["reason"] and "2026-10-28" not in after["reason"]
    # the 25 November review moved MG's two dates and the registry's own, and nothing else; ACVA's
    # resolution came after it, so the registry is read as it stood before that
    standing = _before_the_acva_resolution()
    assert standing["reviewed_on"] == "2026-11-25"
    events = {event["symbol"]: event for event in standing["events"]}
    assert all(event["active_until"] is None and "resolution" not in event for event in events.values())
    assert {symbol: (event["reviewed_on"], event["review_due"]) for symbol, event in events.items()} == {
        "MG": ("2026-11-25", "2026-12-17"), "ZIM": ("2026-11-19", "2026-12-02"),
        "PRTH": ("2026-11-19", "2026-12-17"), "ARX": ("2026-11-19", "2026-12-17"),
        "BWIN": ("2026-11-19", "2026-12-17"), "CCC": ("2026-11-19", "2026-12-17"),
        "ACVA": ("2026-10-09", "2026-10-15")}
    closed = event_risk.classify("ACVA", "2026-11-18", registry=standing)
    assert closed["blocked"] is True and closed["status"] == "review_required"


def _acva_resolution():
    return json.loads((ROOT / "release-evidence" / "2026-11-25-acva-resolution" / "manifest.json").read_text())


def _before_the_acva_resolution():
    """The registry with ACVA's resolution undone: no end, no resolution, its review dates of
    9 October and the review note of 19 November it carried."""
    before = copy.deepcopy(event_risk.REGISTRY)
    acva = next(e for e in before["events"] if e["symbol"] == "ACVA")
    del acva["resolution"]
    acva.update(active_until=None, reviewed_on="2026-10-09", review_due="2026-10-15")
    note = json.loads((ROOT / "release-evidence" / "2026-11-19-acva-review-note" / "manifest.json").read_text())
    acva["review_note"] = note["note"]
    return event_risk.validate_registry(before)


def _review_of_25_november():
    return json.loads((ROOT / "release-evidence" / "2026-11-25-event-review" / "manifest.json").read_text())


def _before_the_review_of_25_november():
    """The registry with the 25 November review of MG undone: its own date, and MG's two."""
    before = _before_the_acva_resolution()
    before["reviewed_on"] = "2026-11-19"
    mg = next(e for e in before["events"] if e["symbol"] == "MG")
    mg["reviewed_on"], mg["review_due"] = "2026-11-19", "2026-11-25"
    return event_risk.validate_registry(before)


def test_the_review_of_25_november_moved_dates_and_added_no_source():
    """MG's review fell due the day after its special meeting. The finding is a search-result
    summary, so it is no source: the entry keeps the two sources it had, stays unresolved and
    blocked, and the manifest names every entry it did not look at."""
    manifest = _review_of_25_november()
    assert manifest["reviewed_on"] == _before_the_acva_resolution()["reviewed_on"] == "2026-11-25"
    assert [entry["symbol"] for entry in manifest["entries"]] == ["MG"]
    entry = manifest["entries"][0]
    assert entry["basis"] == "read as a search-result summary on 2026-11-25; page bytes not captured"
    assert "source" not in entry and "quote" not in entry and "excerpt" not in entry
    assert entry["registry_action"] == "review dates moved; no source added"
    assert "no page bytes were captured" in manifest["how_read"]
    symbols = [event["symbol"] for event in event_risk.REGISTRY["events"]]
    assert sorted(manifest["not_reviewed_on_this_date"]["symbols"] + ["MG"]) == sorted(symbols)
    now = next(e for e in event_risk.REGISTRY["events"] if e["symbol"] == "MG")
    was = next(e for e in _before_the_review_of_25_november()["events"] if e["symbol"] == "MG")
    assert {k: v for k, v in now.items() if k not in ("reviewed_on", "review_due")} == \
        {k: v for k, v in was.items() if k not in ("reviewed_on", "review_due")}
    assert [s["published_on"] for s in now["sources"]] == ["2026-09-18", "2026-10-28"]
    # every other entry is byte for byte what it was
    others = lambda registry: [e for e in registry["events"] if e["symbol"] != "MG"]  # noqa: E731
    assert others(_before_the_acva_resolution()) == others(_before_the_review_of_25_november())
    # still blocked after the vote, at its new review date and past it
    for session, status in (("2026-11-25", "known_event"), ("2026-12-17", "known_event"),
                            ("2026-12-18", "review_required")):
        read = event_risk.classify("MG", session)
        assert read["blocked"] is True and read["status"] == status, session
    # CI's own rule: nothing lapses on the review's date, and MG's next date is the first to pass
    assert event_risk.lapsed_reviews(event_risk.REGISTRY, "2026-11-26") == []
    assert event_risk.lapsed_reviews(event_risk.REGISTRY, "2026-12-03") == ["ZIM"]


def test_the_review_manifest_says_how_each_entry_was_read():
    manifest = json.loads((ROOT / "release-evidence" / "2026-11-19-event-review" / "manifest.json").read_text())
    assert manifest["reviewed_on"] == "2026-11-19"
    # the registry has moved three times since: by ACVA's review note, by the 25 November review of
    # MG, then by ACVA's resolution. Each change's own manifest names the registry it began from,
    # and undoing exactly what a manifest says it changed gives the registry the one before it ended on
    note = json.loads((ROOT / "release-evidence" / "2026-11-19-acva-review-note" / "manifest.json").read_text())
    later = _review_of_25_november()
    assert note["registry_before"] == manifest["registry_after"]
    assert later["registry_before"] == note["registry_after"]
    resolved = _acva_resolution()
    assert resolved["registry_before"] == later["registry_after"] == {
        "reviewed_on": _before_the_acva_resolution()["reviewed_on"],
        "sha256": event_risk.registry_digest(_before_the_acva_resolution())}
    assert resolved["registry_after"] == {"reviewed_on": event_risk.REGISTRY["reviewed_on"],
                                          "sha256": event_risk.registry_digest(event_risk.REGISTRY)}
    before = _before_the_review_of_25_november()
    assert note["registry_after"] == {"reviewed_on": before["reviewed_on"],
                                      "sha256": event_risk.registry_digest(before)}
    acva = next(e for e in before["events"] if e["symbol"] == "ACVA")
    assert note["note"] == acva.pop("review_note")
    assert manifest["registry_after"]["sha256"] == event_risk.registry_digest(before)
    entries = {entry["symbol"]: entry for entry in manifest["entries"]}
    assert set(entries) == {event["symbol"] for event in event_risk.REGISTRY["events"]}
    # one entry rests on captured bytes, and they are the source the registry now carries
    captured = [symbol for symbol, entry in entries.items() if "captured bytes" in entry["basis"]]
    assert captured == ["MG"]
    added = next(event for event in event_risk.REGISTRY["events"] if event["symbol"] == "MG")["sources"][-1]
    assert {name: entries["MG"]["source"][name] for name in ("url", "published_on", "sha256", "quote")} == {
        name: added[name] for name in ("url", "published_on", "sha256", "quote")}
    # every other finding says it is a search excerpt, and none of them added a source
    for symbol, entry in entries.items():
        if symbol != "MG":
            assert entry["basis"] == "read as a search-result excerpt on 2026-11-19; page bytes not captured"
            assert "source" not in entry
    assert entries["ACVA"]["registry_action"] == "none"


def test_the_captured_source_behind_the_review_is_retained_outside_the_rolling_archive():
    """MG's added source rests on a capture the issuer-evidence collector made. The bundle that
    carries it was published under docs/issuer-evidence/, which removes a superseded bundle after
    21 days, so a byte-for-byte copy is kept beside the manifest and must be what the manifest says."""
    folder = ROOT / "release-evidence" / "2026-11-19-event-review"
    manifest = json.loads((folder / "manifest.json").read_text())
    entry = next(entry for entry in manifest["entries"] if entry["symbol"] == "MG")
    source = entry["source"]
    retained = ROOT / source["retained_in"]
    assert retained.parent == folder and not retained.is_symlink()
    raw = retained.read_bytes()
    # the copy is the published bundle: its name is its digest, as the collector names it
    assert retained.name == f"issuer-evidence-{hashlib.sha256(raw).hexdigest()}.json"
    assert source["retained_document"]["first_published_at"].startswith(
        f"docs/issuer-evidence/{hashlib.sha256(raw).hexdigest()}.json")
    bundle = json.loads(raw)
    issuer = next(issuer for issuer in bundle["issuers"] if issuer["ticker"] == source["retained_document"]["issuer"])
    pointer = source["retained_document"]
    document = next(document for document in issuer["documents"]
                    if document["accession"] == pointer["accession"] and document["role"] == pointer["role"])
    # the digest the registry carries is the collector's digest of that response, and its size
    assert document["source"]["url"] == source["url"]
    assert document["source"]["raw_sha256"] == source["sha256"]
    assert document["source"]["bytes"] == source["bytes"]
    assert document["source"]["fetched_at"] == source["fetched_at"]
    # the text is whole and is what its own digest says; every quoted sentence is in it
    excerpt = document["excerpt"]
    assert excerpt["truncated"] is False and excerpt["characters"] == len(excerpt["text"])
    assert excerpt["sha256"] == hashlib.sha256(excerpt["text"].encode("utf-8")).hexdigest()
    for sentence in [source["quote"], *entry["also_in_that_capture"]]:
        assert sentence in excerpt["text"], sentence
    registry_source = next(event for event in event_risk.REGISTRY["events"] if event["symbol"] == "MG")["sources"][-1]
    assert registry_source["quote"] in excerpt["text"] and registry_source["sha256"] == document["source"]["raw_sha256"]
    # the manifest does not claim the response bytes themselves are kept
    assert "were not retained" in manifest["how_read"]


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


def test_acva_is_resolved_by_the_release_captured_from_a_runner():
    """Copart's 16 October release, captured on 25 November 2026 from a runner that reaches sec.gov,
    ends ACVA's interval on its own date: every session before it stays inside, none from it on."""
    manifest = _acva_resolution()
    acva = next(e for e in event_risk.REGISTRY["events"] if e["symbol"] == "ACVA")
    entry = manifest["entries"][0]
    assert [e["symbol"] for e in manifest["entries"]] == ["ACVA"]
    assert acva["active_until"] == acva["resolution"]["published_on"] == "2026-10-16"
    assert "review_note" not in acva and acva["reviewed_on"] == manifest["reviewed_on"] == "2026-11-25"
    # the registry carries exactly the source the manifest names, with the capture's digest
    assert {k: entry["source"][k] for k in ("title", "url", "published_on", "sha256", "quote")} == acva["resolution"]
    assert entry["basis"].startswith("captured bytes") and entry["source"]["sha256"] in entry["basis"]
    assert entry["source"]["url"].startswith("https://www.sec.gov/Archives/edgar/data/")
    # undoing exactly what the manifest says it changed gives the registry before it
    before = _before_the_acva_resolution()
    assert [e for e in before["events"] if e["symbol"] != "ACVA"] == \
        [e for e in event_risk.REGISTRY["events"] if e["symbol"] != "ACVA"]
    # inside the interval it still blocks, and an older session shows no resolution it could not have known
    inside = event_risk.classify("ACVA", "2026-10-15")
    assert inside["blocked"] is True and inside["status"] == "known_event"
    assert "resolution" not in inside["matches"][0] and inside["matches"][0]["active_until"] is None
    for session in ("2026-10-16", "2026-11-18", "2026-11-25"):
        read = event_risk.classify("ACVA", session)
        assert read["blocked"] is False and read["status"] == "not_in_registry", session
    # before the resolution, the same session was blocked for an overdue review
    assert event_risk.classify("ACVA", "2026-11-18", registry=before)["status"] == "review_required"
    # a resolved entry is never lapsed, whatever its review date
    assert "ACVA" not in event_risk.lapsed_reviews(event_risk.REGISTRY, "2027-01-01")
