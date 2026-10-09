"""Real Nasdaq capture boundaries plus isolated failure and retention cases."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from src import morning_halts as halts

CAPTURE = Path(__file__).parent / "fixtures" / "morning_halts"
RAW = (CAPTURE / "nasdaq-current.xml").read_bytes()
META = json.loads((CAPTURE / "capture.json").read_text())
NOW = datetime(2026, 10, 9, 15, 26, 22, tzinfo=timezone.utc)


def response(raw=RAW, fetched_at=META["captured_at"]):
    return {"body": raw, "fetched_at": fetched_at, "http_date": META["http_date"]}


def observe(symbols=("QETA", "AIOK", "BKKT.W", "MAMK", "NVDA"), *, raw=RAW, now=NOW, previous=None):
    result = halts.observe(symbols, now, fetcher=lambda: response(raw), previous=previous)
    halts.validate(result, symbols, now)
    return result


def edit_feed(*, keep=None, publication=None, edit=None):
    root = ET.fromstring(RAW)
    channel = root.find("channel")
    if publication is not None:
        channel.find("pubDate").text = publication
    for item in list(channel.findall("item")):
        symbol = item.findtext(halts.NAMESPACE + "IssueSymbol")
        if keep is not None and symbol not in keep:
            channel.remove(item)
        elif edit is not None:
            edit(item)
    channel.find(halts.NAMESPACE + "numItems").text = str(len(channel.findall("item")))
    return ET.tostring(root)


def test_capture_is_unchanged_and_uses_channel_clock_not_midnight_item_clock():
    assert hashlib.sha256(RAW).hexdigest() == META["sha256"]
    parsed = halts.parse(RAW)
    assert parsed["item_count"] == 35 and parsed["source_published_at"] == "2026-10-09T15:25:51Z"
    source = observe()["coverage"]["halts"]
    assert source["status"] == "fresh" and source["source_age_seconds"] == 31
    assert source["expires_at"] == "2026-10-09T15:28:51Z"


def test_latest_qeta_halt_wins_over_multiple_resumptions_and_quote_only_is_blocked():
    row = observe()["symbols"]["QETA"]["halt"]
    assert row["status"] == "halt_reported" and row["blocks_entry"] is True
    assert row["event_count"] == 5
    assert row["events"][0]["halted_at"] == "2026-10-09T15:22:07.920000Z"
    assert row["events"][0]["quote_resumption_at"] == "2026-10-09T15:22:07Z"
    assert row["events"][0]["trade_resumption_at"] is None
    root = ET.fromstring(RAW)
    channel = root.find("channel")
    items = channel.findall("item")
    for item in items:
        channel.remove(item)
    channel.extend(reversed(items))
    assert observe(raw=ET.tostring(root))["symbols"]["QETA"] == observe()["symbols"]["QETA"]


def test_resumption_reports_evidence_without_granting_clearance_or_unhalting_deletion():
    rows = observe()["symbols"]
    assert rows["AIOK"]["halt"]["status"] == "resumption_reported"
    assert rows["AIOK"]["halt"]["blocks_entry"] is None
    assert rows["MAMK"]["halt"]["status"] == "security_deleted"
    assert rows["MAMK"]["halt"]["blocks_entry"] is True
    assert rows["BKKT.W"]["halt"]["blocks_entry"] is True
    assert rows["NVDA"]["halt"]["status"] == "not_listed"
    assert rows["NVDA"]["halt"]["blocks_entry"] is None


def test_old_unresolved_halts_still_block_when_the_channel_is_stale():
    result = observe(now=NOW + timedelta(minutes=10))
    assert result["coverage"]["halts"]["status"] == "stale"
    assert result["symbols"]["BKKT.W"]["halt"]["blocks_entry"] is True
    assert result["symbols"]["NVDA"]["halt"]["status"] == "unknown"
    assert result["symbols"]["AIOK"]["halt"]["status"] == "unknown"


def test_clock_passing_scheduled_resumption_does_not_confirm_it_without_source_update():
    def schedule(item):
        if item.findtext(halts.NAMESPACE + "HaltTime") == "11:22:07.920":
            item.find(halts.NAMESPACE + "ResumptionTradeTime").text = "11:26:00"
    raw = edit_feed(keep={"QETA"}, edit=schedule)
    row = observe(("QETA",), raw=raw)["symbols"]["QETA"]["halt"]
    assert row["status"] == "resumption_scheduled" and row["blocks_entry"] is True


@pytest.mark.parametrize("raw", [b"", b"<html>provider down</html>", b'<!DOCTYPE rss [<!ENTITY bad "yes">]><rss/>',
                                b"<rss/>\x00", b"x" * (halts.MAX_FEED_BYTES + 1)])
def test_bad_or_oversized_source_is_unknown_not_an_empty_success(raw):
    result = observe(raw=raw)
    assert result["coverage"]["halts"]["status"] == "unavailable"
    assert result["symbols"]["QETA"]["halt"]["status"] == "unknown"


def test_future_source_clock_and_mismatched_count_are_unknown():
    future = edit_feed(publication="Fri, 09 Oct 2026 15:27:00 GMT")
    assert observe(raw=future)["coverage"]["halts"]["status"] == "unavailable"
    bad = RAW.replace(b"<ndaq:numItems>35</ndaq:numItems>", b"<ndaq:numItems>34</ndaq:numItems>")
    assert bad != RAW
    assert observe(raw=bad)["coverage"]["halts"]["status"] == "unavailable"


def test_callable_clock_evaluates_after_slow_fetch():
    final = NOW + timedelta(seconds=8)
    times = iter([NOW, final])
    result = halts.observe(["QETA"], lambda: next(times), fetcher=lambda: response(fetched_at=final))
    assert result["coverage"]["halts"]["status"] == "fresh"
    assert result["coverage"]["halts"]["receipt_age_seconds"] == 0
    halts.validate(result, ["QETA"], final)


def test_no_candidates_do_not_fetch_and_do_not_claim_news_or_earnings_coverage():
    def forbidden():
        raise AssertionError("should not fetch")
    result = halts.observe([], NOW, fetcher=forbidden)
    assert result["coverage"]["halts"]["status"] == "not_requested"
    assert result["coverage"]["issuer_news"]["status"] == "not_checked"
    assert result["coverage"]["earnings"]["status"] == "not_checked"
    halts.validate(result, [], NOW)


def test_outage_exception_is_not_public_and_known_halt_survives():
    previous = observe(("QETA",))
    def failing():
        raise OSError("private provider exception text")
    result = halts.observe(["QETA"], NOW, fetcher=failing, previous=previous)
    assert result["coverage"]["halts"]["status"] == "unavailable"
    assert result["symbols"]["QETA"]["halt"]["blocks_entry"] is True
    assert "private provider" not in json.dumps(result)
    halts.validate(result, ["QETA"], NOW)


def test_omission_carries_original_source_once_and_never_clears_deletion():
    previous = observe(("QETA", "MAMK"))
    omitted = edit_feed(keep=set())
    current = observe(("QETA", "MAMK"), raw=omitted, previous=previous)
    again = observe(("QETA", "MAMK"), raw=omitted, previous=current)
    assert current == again
    for row in current["symbols"].values():
        assert row["halt"]["blocks_entry"] is True
        assert row["halt"]["retained_source"]["source_sha256"] == META["sha256"]
        assert "retained_source" not in row["halt"]["retained_source"]


def test_only_explicit_source_after_resumption_can_resolve_previous_halt():
    previous = observe(("QETA",))
    def resume(item):
        if item.findtext(halts.NAMESPACE + "HaltTime") == "11:22:07.920":
            item.find(halts.NAMESPACE + "ResumptionTradeTime").text = "11:25:00"
    resolved = observe(("QETA",), raw=edit_feed(keep={"QETA"}, publication="Fri, 09 Oct 2026 15:26:00 GMT", edit=resume), previous=previous)
    assert resolved["symbols"]["QETA"]["halt"]["status"] == "resumption_reported"
    assert resolved["symbols"]["QETA"]["halt"]["retained_source"] is None
    assert "QETA" not in resolved["retained"]


def test_empty_candidate_refresh_preserves_halt_memory_for_later_candidates():
    previous = observe(("QETA",))
    no_tickets = observe((), previous=previous)
    assert no_tickets["symbols"] == {}
    assert no_tickets["retained"] == previous["retained"]
    later = observe(("QETA",), raw=edit_feed(keep=set()), previous=no_tickets)
    assert later["symbols"]["QETA"]["halt"]["blocks_entry"] is True
    assert later["retained"] == previous["retained"]
    halts.validate_continuity(no_tickets, previous)
    halts.validate_continuity(later, no_tickets)


def test_continuity_rejects_dropping_memory_when_there_are_no_candidate_rows():
    previous = observe(("QETA",))
    invented_empty = observe(())
    halts.validate(invented_empty, [], NOW)
    with pytest.raises(ValueError, match="continuity"):
        halts.validate_continuity(invented_empty, previous)


def test_continuity_accepts_explicit_newer_source_resolution_and_rejects_regression():
    previous = observe(("QETA",))
    def resume(item):
        if item.findtext(halts.NAMESPACE + "HaltTime") == "11:22:07.920":
            item.find(halts.NAMESPACE + "ResumptionTradeTime").text = "11:24:59"
    good = observe(("QETA",), raw=edit_feed(keep={"QETA"}, publication="Fri, 09 Oct 2026 15:26:00 GMT", edit=resume), previous=previous)
    halts.validate_continuity(good, previous)
    old = observe(("QETA",), raw=edit_feed(keep={"QETA"}, publication="Fri, 09 Oct 2026 15:25:00 GMT", edit=resume))
    with pytest.raises(ValueError, match="continuity"):
        halts.validate_continuity(old, previous)


def test_positive_memory_cannot_be_erased_or_fabricated_and_bad_prior_precedes_network():
    previous = observe(("QETA",))
    previous["retained"] = {}
    def forbidden():
        raise AssertionError("malformed prior should precede network")
    with pytest.raises(ValueError, match="memory"):
        halts.observe(["QETA"], NOW, fetcher=forbidden, previous=previous)
    previous = observe(("QETA",))
    previous["retained"]["QETA"]["halt"]["blocks_entry"] = None
    with pytest.raises(ValueError, match="positive"):
        halts.observe([], NOW, fetcher=forbidden, previous=previous)


def test_regressed_source_cannot_resolve_or_replace_newer_known_halt_evidence():
    previous = observe(("QETA",))
    def resume(item):
        if item.findtext(halts.NAMESPACE + "HaltTime") == "11:22:07.920":
            item.find(halts.NAMESPACE + "ResumptionTradeTime").text = "11:24:59"
    older = edit_feed(keep={"QETA"}, publication="Fri, 09 Oct 2026 15:25:00 GMT", edit=resume)
    direct = observe(("QETA",), raw=older, previous=previous)
    assert direct["symbols"]["QETA"]["halt"]["blocks_entry"] is True
    assert direct["retained"] == previous["retained"]
    rollback = observe(("QETA",), raw=edit_feed(keep={"QETA"}, publication="Fri, 09 Oct 2026 15:25:00 GMT"), previous=previous)
    middle = edit_feed(keep={"QETA"}, publication="Fri, 09 Oct 2026 15:25:30 GMT", edit=resume)
    assert observe(("QETA",), raw=middle, previous=rollback)["retained"] == previous["retained"]


def test_halt_memory_limit_refuses_to_silently_discard_existing_exclusions():
    previous = observe(("QETA",))
    sample = previous["retained"].pop("QETA")
    previous["symbols"] = {}
    previous["coverage"] = observe(())["coverage"]
    for index in range(halts.MAX_SYMBOLS):
        symbol = f"HALT{index}"
        entry = deepcopy(sample)
        entry["halt"]["events"][0]["symbol"] = symbol
        entry["halt"]["events"][0]["source_fields"]["IssueSymbol"] = symbol
        previous["retained"][symbol] = entry
    halts.validate(previous, [], NOW)
    with pytest.raises(ValueError, match="exceeds"):
        observe(("QETA",), previous=previous)


def test_unknown_reason_without_resumption_remains_a_reported_halt():
    def unknown(item):
        item.find(halts.NAMESPACE + "ReasonCode").text = "NEWCODE"
    result = observe(("QETA",), raw=edit_feed(keep={"QETA"}, edit=unknown))
    assert result["symbols"]["QETA"]["halt"]["blocks_entry"] is True
    assert "unrecognized" in result["symbols"]["QETA"]["halt"]["reason"]


def test_source_freshness_boundary_and_symbol_suffix_match_are_exact():
    boundary = datetime(2026, 10, 9, 15, 28, 51, tzinfo=timezone.utc)
    assert observe(now=boundary)["coverage"]["halts"]["status"] == "fresh"
    assert observe(now=boundary + timedelta(microseconds=1))["coverage"]["halts"]["status"] == "stale"
    rows = observe(("BKKT", "BKKT.W"))["symbols"]
    assert rows["BKKT"]["halt"]["status"] == "not_listed"
    assert rows["BKKT.W"]["halt"]["blocks_entry"] is True


def test_duplicate_source_events_and_malformed_resumption_are_unknown():
    root = ET.fromstring(RAW)
    channel = root.find("channel")
    channel.append(deepcopy(channel.find("item")))
    channel.find(halts.NAMESPACE + "numItems").text = "36"
    assert observe(raw=ET.tostring(root))["coverage"]["halts"]["status"] == "unavailable"
    def invalid(item):
        item.find(halts.NAMESPACE + "ResumptionDate").text = ""
    assert observe(raw=edit_feed(keep={"AIOK"}, edit=invalid))["coverage"]["halts"]["status"] == "unavailable"


def test_production_fetch_bounds_timeout_bytes_and_one_minute_polling(monkeypatch):
    calls = []
    class Response:
        headers = {"Date": META["http_date"]}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, count):
            assert count == 1_000_001
            return RAW
    class Opener:
        def open(self, request, timeout):
            calls.append(request.full_url)
            assert request.full_url == "https://www.nasdaqtrader.com/rss.aspx?feed=tradehalts"
            assert timeout == 10
            return Response()
    monkeypatch.setattr(halts, "build_opener", lambda *args: Opener())
    monkeypatch.setattr(halts, "_last_attempt", None)
    monkeypatch.setattr(halts, "_last_response", None)
    ticks = iter([10, 69, 70])
    monkeypatch.setattr(halts.time, "monotonic", lambda: next(ticks))
    halts.fetch()
    halts.fetch()
    assert len(calls) == 1
    halts.fetch()
    assert len(calls) == 2


@pytest.mark.parametrize("change", ["status", "clearance", "clock", "url", "source_field", "coverage", "digest", "retained"])
def test_validator_rejects_malformed_or_invented_trusted_evidence(change):
    result = observe(("QETA",))
    source = result["coverage"]["halts"]
    halt = result["symbols"]["QETA"]["halt"]
    if change == "status": source["status"] = "stale"
    elif change == "clearance": halt["blocks_entry"] = False
    elif change == "clock": source["fetched_at"] = "2026-10-09T15:26:22"
    elif change == "url": halt["source_url"] = "https://unknown.example/"
    elif change == "source_field": halt["events"][0]["source_fields"]["IssueSymbol"] = "AIOK"
    elif change == "coverage": result["coverage"]["issuer_news"]["status"] = "clear"
    elif change == "digest": source["source_sha256"] = "not-a-digest"
    elif change == "retained": halt["retained_source"] = {"status": "fresh"}
    with pytest.raises(ValueError):
        halts.validate(result, ["QETA"], NOW)
