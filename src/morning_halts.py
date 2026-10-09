"""Bounded Nasdaq halt observations; absence is never a trading clearance.

Nasdaq publishes its free current-halts RSS about once per minute. Channel
pubDate is the feed clock; item pubDate is only a date. Namespaced halt and
resumption fields use Eastern Time. A quote restart is not a trading restart.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
import re
import time
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

VERSION = 1
SOURCE_URL = "https://www.nasdaqtrader.com/rss.aspx?feed=tradehalts"
HELP_URL = "https://www.nasdaqtrader.com/Trader.aspx?id=TradeHaltRSS"
CODES_URL = "https://www.nasdaqtrader.com/Trader.aspx?id=TradeHaltCodes"
SOURCE_NAME = "Nasdaq Trader current trade halts RSS"
SCOPE = "Nasdaq and other exchange-listed securities reported in this RSS snapshot; absence is not clearance."
MAX_FEED_BYTES = 1_000_000
MAX_ITEMS = 2_000
MAX_SYMBOLS = 100
MAX_FIELD_LENGTH = 256
MAX_SYMBOL_LENGTH = 32
TIMEOUT_SECONDS = 10
MIN_POLL_INTERVAL_SECONDS = 60
SOURCE_MAX_AGE_SECONDS = 180
RECEIPT_MAX_AGE_SECONDS = 300
FUTURE_SKEW_SECONDS = 5
NAMESPACE = "{http://www.nasdaqtrader.com/}"
EASTERN = ZoneInfo("America/New_York")
UTC = timezone.utc
KNOWN_CODES = frozenset("T1 T2 T3 T5 T6 T7 T8 T12 H4 H9 H10 H11 O1 IPO1 IPOQ IPOE M1 M2 LUDP LUDS MWC1 MWC2 MWC3 MWC0 MWCQ R4 R9 C3 C4 C9 C11 R1 R2 M D".split())
RULES = {
    "morning_halts.version": VERSION,
    "morning_halts.source_url": SOURCE_URL,
    "morning_halts.source_max_age_seconds": SOURCE_MAX_AGE_SECONDS,
    "morning_halts.receipt_max_age_seconds": RECEIPT_MAX_AGE_SECONDS,
    "morning_halts.future_skew_seconds": FUTURE_SKEW_SECONDS,
    "morning_halts.max_feed_bytes": MAX_FEED_BYTES,
    "morning_halts.max_items": MAX_ITEMS,
    "morning_halts.max_symbols": MAX_SYMBOLS,
    "morning_halts.max_field_length": MAX_FIELD_LENGTH,
    "morning_halts.max_symbol_length": MAX_SYMBOL_LENGTH,
    "morning_halts.timeout_seconds": TIMEOUT_SECONDS,
    "morning_halts.min_poll_interval_seconds": MIN_POLL_INTERVAL_SECONDS,
    "morning_halts.known_codes": sorted(KNOWN_CODES),
}
_last_attempt = None
_last_response = None


def _instant(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("offset-aware instant required")
    return value.astimezone(UTC)


def _iso(value):
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(req.full_url, code, "halt source redirects are refused", headers, fp)


def fetch():
    """One fixed public source, no credentials; cache requests within a minute."""
    global _last_attempt, _last_response
    tick = time.monotonic()
    if _last_attempt is not None and tick - _last_attempt < MIN_POLL_INTERVAL_SECONDS:
        if _last_response is None:
            raise ValueError("halt source retry interval has not elapsed")
        return deepcopy(_last_response)
    _last_attempt, _last_response = tick, None
    request = Request(SOURCE_URL, headers={"User-Agent": "SpicyStock/1.0 (public halt observations)",
                                          "Accept": "application/rss+xml, text/xml", "Accept-Encoding": "identity"})
    with build_opener(_NoRedirect()).open(request, timeout=TIMEOUT_SECONDS) as response:
        body = response.read(MAX_FEED_BYTES + 1)
        if len(body) > MAX_FEED_BYTES:
            raise ValueError("halt source exceeds byte limit")
        result = {"body": body, "fetched_at": _iso(datetime.now(UTC)),
                  "http_date": response.headers.get("Date")}
    _last_response = result
    return deepcopy(result)


def _field(item, name, *, required=False):
    nodes = item.findall(NAMESPACE + name)
    if len(nodes) != 1:
        raise ValueError("missing or duplicate halt field")
    value = (nodes[0].text or "").strip()
    if (required and not value) or len(value) > MAX_FIELD_LENGTH:
        raise ValueError("invalid halt field")
    return value


def _eastern(day, clock):
    if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", day) or not re.fullmatch(r"\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?", clock):
        raise ValueError("invalid Eastern halt time")
    pattern = "%m/%d/%Y %H:%M:%S.%f" if "." in clock else "%m/%d/%Y %H:%M:%S"
    naive = datetime.strptime(day + " " + clock, pattern)
    local = naive.replace(tzinfo=EASTERN)
    if local.utcoffset() != local.replace(fold=1).utcoffset() or local.astimezone(UTC).astimezone(EASTERN).replace(tzinfo=None) != naive:
        raise ValueError("ambiguous or nonexistent Eastern halt time")
    return local.astimezone(UTC)


def parse(body):
    """Strictly parse the RSS data fields, never its HTML description."""
    if not isinstance(body, bytes) or not body or len(body) > MAX_FEED_BYTES:
        raise ValueError("invalid halt response bytes")
    text = body.decode("utf-8-sig")
    if "\x00" in text or re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", text, re.IGNORECASE):
        raise ValueError("DTD and entities are prohibited")
    root = ET.fromstring(text)
    channels = root.findall("channel")
    if root.tag != "rss" or root.get("version") != "2.0" or len(channels) != 1:
        raise ValueError("invalid halt RSS root")
    channel = channels[0]
    publications = channel.findall("pubDate")
    if len(publications) != 1:
        raise ValueError("missing or duplicate halt publication clock")
    published = _instant(parsedate_to_datetime(publications[0].text or ""))
    items = channel.findall("item")
    count = _field(channel, "numItems", required=True)
    if not count.isdecimal() or int(count) != len(items) or len(items) > MAX_ITEMS:
        raise ValueError("halt item count mismatch or limit exceeded")
    events, identities = [], set()
    for item in items:
        fields = {name: _field(item, name, required=name in {"HaltDate", "HaltTime", "IssueSymbol", "Market"})
                  for name in ("HaltDate", "HaltTime", "IssueSymbol", "IssueName", "Market", "ReasonCode",
                               "ResumptionDate", "ResumptionQuoteTime", "ResumptionTradeTime")}
        symbol = fields["IssueSymbol"]
        if len(symbol) > MAX_SYMBOL_LENGTH or not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-/$]*", symbol):
            raise ValueError("invalid source halt symbol")
        halted = _eastern(fields["HaltDate"], fields["HaltTime"])
        if halted > published + timedelta(seconds=FUTURE_SKEW_SECONDS):
            raise ValueError("halt occurs after source clock")
        identity = (symbol, halted)
        if identity in identities:
            raise ValueError("duplicate halt identity")
        identities.add(identity)
        resumed = fields["ResumptionDate"]
        if resumed:
            if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", resumed):
                raise ValueError("invalid resumption date")
            datetime.strptime(resumed, "%m/%d/%Y")
        quote = _eastern(resumed, fields["ResumptionQuoteTime"]) if fields["ResumptionQuoteTime"] else None
        trade = _eastern(resumed, fields["ResumptionTradeTime"]) if fields["ResumptionTradeTime"] else None
        if trade is not None and trade < halted:
            raise ValueError("trade resumption precedes halt")
        events.append({"symbol": symbol, "issue_name": fields["IssueName"], "market": fields["Market"],
                       "reason_code": fields["ReasonCode"], "halted_at": _iso(halted),
                       "quote_resumption_at": _iso(quote) if quote else None,
                       "trade_resumption_at": _iso(trade) if trade else None,
                       "source_fields": fields})
    return {"source_published_at": _iso(published), "item_count": len(items), "events": events}


def _halt(events, now, status, published=None):
    if not events:
        return {"status": "not_listed" if status == "fresh" else "unknown", "blocks_entry": None,
                "reason": "No matching halt in this snapshot; absence is not trading clearance." if status == "fresh"
                          else "Current halt coverage is unavailable or stale; verify with the broker and exchange.",
                "events": [], "event_count": 0, "source_url": SOURCE_URL, "retained_source": None}
    latest = max(events, key=lambda event: _instant(event["halted_at"]))
    code = latest["reason_code"]
    trade = _instant(latest["trade_resumption_at"]) if latest["trade_resumption_at"] else None
    if code == "D":
        state, blocked, reason = "security_deleted", True, "Nasdaq reports security deletion; a displayed resumption time does not establish eligibility."
    elif trade is None:
        state, blocked, reason = "halt_reported", True, "The source reports a halt without a trading resumption. Quote resumption alone does not resume trading."
        if code not in KNOWN_CODES:
            reason += " Its reason code is unrecognized."
    elif code not in KNOWN_CODES:
        state, blocked, reason = "unknown", None, "The source reports an unrecognized halt reason; verify its current status."
    elif trade > now or published is None or trade > published:
        state, blocked, reason = "resumption_scheduled", True, "The source was published before the trading resumption time; await a source update after resumption."
    elif status != "fresh":
        state, blocked, reason = "unknown", None, "A resumption was reported, but this snapshot is stale; verify the current halt status."
    else:
        state, blocked, reason = "resumption_reported", None, "The reported trading resumption time has passed; this is not confirmation of a live tradable market."
    if status != "fresh" and blocked:
        reason += " This source snapshot is stale; the last reported exclusion remains in force."
    return {"status": state, "blocks_entry": blocked, "reason": reason, "events": [deepcopy(latest)],
            "event_count": len(events), "source_url": SOURCE_URL, "retained_source": None}


def _retain(result, previous):
    """Carry at most one unresolved event and its original, non-nested source."""
    memory = deepcopy(previous["retained"]) if previous is not None else {}
    current_source = result["coverage"]["halts"]
    now = _instant(current_source["checked_at"])
    for symbol, row in result["symbols"].items():
        prior = memory.get(symbol, {})
        old = prior.get("halt", {})
        if old.get("blocks_entry") is not True or not old.get("events"):
            continue
        current = row["halt"]
        old_event = old["events"][0]
        current_event = current["events"][0] if current["events"] else None
        deletion = old_event["reason_code"] == "D"
        old_published = _instant(prior["source"]["source_published_at"])
        current_published = _instant(current_source["source_published_at"]) if current_source["source_published_at"] else None
        newer_source = current_published is not None and current_published > old_published
        same_source = current_published == old_published and current_source["source_sha256"] == prior["source"]["source_sha256"]
        if not deletion and current_event and _instant(current_event["halted_at"]) >= _instant(old_event["halted_at"]):
            if (current["blocks_entry"] is True and (newer_source or same_source)) or (newer_source and current_source["status"] == "fresh" and current["status"] == "resumption_reported"):
                continue
        retained_source = deepcopy(prior["source"])
        retained = _halt([old_event], now, _source_status_at(retained_source, now), _instant(retained_source["source_published_at"]))
        retained["event_count"] = old["event_count"]
        retained["retained_source"] = retained_source
        retained["reason"] += " Retained from an earlier checked source; the new snapshot does not explicitly resolve this exclusion."
        row["halt"] = retained
    for symbol, row in result["symbols"].items():
        halt = row["halt"]
        if halt["blocks_entry"] is True:
            source = deepcopy(halt["retained_source"] or current_source)
            original = _halt(halt["events"], _instant(source["checked_at"]), source["status"], _instant(source["source_published_at"]))
            original["event_count"] = halt["event_count"]
            memory[symbol] = {"source": source, "halt": original}
        elif halt["status"] == "resumption_reported":
            memory.pop(symbol, None)
    if len(memory) > MAX_SYMBOLS:
        raise ValueError("retained halt memory exceeds symbol limit")
    result["retained"] = memory
    return result


def _source_status_at(source, now):
    age = (now - _instant(source["source_published_at"])).total_seconds()
    receipt = (now - _instant(source["fetched_at"])).total_seconds()
    return "fresh" if age <= SOURCE_MAX_AGE_SECONDS and receipt <= RECEIPT_MAX_AGE_SECONDS else "stale"


def _validate_source(source, now):
    fields = {"provider", "source_url", "scope", "status", "checked_at", "fetched_at", "source_published_at",
              "expires_at", "source_sha256", "http_date", "item_count", "source_age_seconds", "receipt_age_seconds", "reason"}
    if not isinstance(source, dict) or set(source) != fields or source["provider"] != SOURCE_NAME or source["source_url"] != SOURCE_URL or source["scope"] != SCOPE:
        raise ValueError("invalid halt source identity or shape")
    checked = _instant(source["checked_at"])
    if checked > now + timedelta(seconds=FUTURE_SKEW_SECONDS) or not isinstance(source["reason"], str) or len(source["reason"]) > MAX_FIELD_LENGTH:
        raise ValueError("invalid halt checked time or reason")
    if source["status"] in {"unavailable", "not_requested"}:
        if any(source[field] is not None for field in ("fetched_at", "source_published_at", "expires_at", "source_sha256", "http_date", "item_count", "source_age_seconds", "receipt_age_seconds")):
            raise ValueError("unavailable halt source cannot claim evidence")
        return
    if source["status"] not in {"fresh", "stale"}:
        raise ValueError("invalid halt source status")
    if any(type(source[field]) not in {int, float} for field in ("source_age_seconds", "receipt_age_seconds")):
        raise ValueError("invalid halt source age")
    fetched, published = _instant(source["fetched_at"]), _instant(source["source_published_at"])
    source_age, receipt_age = (checked - published).total_seconds(), (checked - fetched).total_seconds()
    if source_age < -FUTURE_SKEW_SECONDS or receipt_age < -FUTURE_SKEW_SECONDS or published > fetched + timedelta(seconds=FUTURE_SKEW_SECONDS):
        raise ValueError("future halt source clock")
    fresh = source_age <= SOURCE_MAX_AGE_SECONDS and receipt_age <= RECEIPT_MAX_AGE_SECONDS
    expiry = min(published + timedelta(seconds=SOURCE_MAX_AGE_SECONDS), fetched + timedelta(seconds=RECEIPT_MAX_AGE_SECONDS))
    if source["status"] != ("fresh" if fresh else "stale") or _instant(source["expires_at"]) != expiry or source["source_age_seconds"] != source_age or source["receipt_age_seconds"] != receipt_age:
        raise ValueError("halt freshness disagrees with source clocks")
    if not isinstance(source["source_sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", source["source_sha256"]):
        raise ValueError("invalid halt source digest")
    if type(source["item_count"]) is not int or not 0 <= source["item_count"] <= MAX_ITEMS:
        raise ValueError("invalid halt item count")
    if source["http_date"] is not None and (not isinstance(source["http_date"], str) or len(source["http_date"]) > MAX_FIELD_LENGTH):
        raise ValueError("invalid HTTP date")


def validate(result, symbols, now, *, _memory_entry=False):
    """Validate a published observation, including replay of each source event."""
    now = _instant(now)
    symbols = list(dict.fromkeys(symbols))
    if len(symbols) > MAX_SYMBOLS or not isinstance(result, dict) or set(result) != {"coverage", "symbols", "retained"}:
        raise ValueError("invalid halt observation")
    coverage = result["coverage"]
    if not isinstance(coverage, dict) or set(coverage) != {"halts", "issuer_news", "earnings"}:
        raise ValueError("invalid event coverage shape")
    for field, wording in (("issuer_news", "Comprehensive current issuer news has not been checked."),
                           ("earnings", "The current earnings calendar has not been checked.")):
        if coverage[field] != {"status": "not_checked", "reason": wording}:
            raise ValueError("unsupported event coverage claim")
    source = coverage["halts"]
    _validate_source(source, now)
    if bool(symbols) == (source["status"] == "not_requested") or not isinstance(result["symbols"], dict) or set(result["symbols"]) != set(symbols):
        raise ValueError("halt symbol coverage mismatch")
    for symbol, row in result["symbols"].items():
        if not isinstance(row, dict) or set(row) != {"halt"}:
            raise ValueError("invalid halt row")
        halt = row["halt"]
        if not isinstance(halt, dict) or set(halt) != {"status", "blocks_entry", "reason", "events", "event_count", "source_url", "retained_source"} or halt["source_url"] != SOURCE_URL:
            raise ValueError("invalid halt result shape")
        if halt["blocks_entry"] is not True and halt["blocks_entry"] is not None:
            raise ValueError("halt observation cannot grant entry clearance")
        evidence_source = halt["retained_source"] or source
        if halt["retained_source"] is not None:
            _validate_source(evidence_source, now)
            if halt["blocks_entry"] is not True or evidence_source["status"] not in {"fresh", "stale"}:
                raise ValueError("invalid retained halt exclusion")
        events = halt["events"]
        if not isinstance(events, list) or len(events) > 1 or type(halt["event_count"]) is not int or not len(events) <= halt["event_count"] <= (evidence_source["item_count"] or 0):
            raise ValueError("invalid retained halt event count")
        published = _instant(evidence_source["source_published_at"]) if evidence_source["source_published_at"] else None
        for event in events:
            if not isinstance(event, dict) or event.get("symbol") != symbol or published is None or not isinstance(event.get("source_fields"), dict):
                raise ValueError("invalid retained halt event")
            rss = ET.Element("rss", version="2.0")
            channel = ET.SubElement(rss, "channel")
            ET.SubElement(channel, "pubDate").text = published.strftime("%a, %d %b %Y %H:%M:%S GMT")
            ET.SubElement(channel, NAMESPACE + "numItems").text = "1"
            item = ET.SubElement(channel, "item")
            for field, value in event["source_fields"].items():
                if not isinstance(field, str) or not isinstance(value, str):
                    raise ValueError("invalid halt source field")
                ET.SubElement(item, NAMESPACE + field).text = value
            replay = parse(ET.tostring(rss))["events"][0]
            if replay != event or _instant(event["halted_at"]) > _instant(source["checked_at"]) + timedelta(seconds=FUTURE_SKEW_SECONDS):
                raise ValueError("halt event disagrees with retained source fields")
        at = _instant(source["checked_at"])
        expected = _halt(events, at, _source_status_at(evidence_source, at) if halt["retained_source"] else source["status"], published)
        expected["event_count"] = halt["event_count"]
        if halt["retained_source"]:
            expected["retained_source"] = halt["retained_source"]
            expected["reason"] += " Retained from an earlier checked source; the new snapshot does not explicitly resolve this exclusion."
        if halt != expected:
            raise ValueError("halt classification disagrees with source evidence")
        if not events and halt["event_count"]:
            raise ValueError("halt count without event")
    memory = result["retained"]
    if not isinstance(memory, dict) or len(memory) > MAX_SYMBOLS:
        raise ValueError("invalid retained halt memory")
    for symbol, entry in memory.items():
        if not isinstance(symbol, str) or len(symbol) > MAX_SYMBOL_LENGTH or not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-/$]*", symbol) or not isinstance(entry, dict) or set(entry) != {"source", "halt"}:
            raise ValueError("invalid retained halt memory entry")
        halt = entry["halt"]
        if not isinstance(halt, dict) or halt.get("blocks_entry") is not True or halt.get("retained_source") is not None:
            raise ValueError("memory must be a positive, non-nested halt observation")
        # The nested validation has empty memory; its source and raw fields are
        # checked by exactly the same rules as an original provider observation.
        validate({"coverage": {**coverage, "halts": entry["source"]},
                  "symbols": {symbol: {"halt": halt}}, "retained": {}}, [symbol], now, _memory_entry=True)
    if not _memory_entry:
        for symbol, row in result["symbols"].items():
            halt = row["halt"]
            entry = memory.get(symbol)
            if halt["blocks_entry"] is True:
                effective_source = halt["retained_source"] or source
                if entry is None or entry["halt"]["events"] != halt["events"] or entry["halt"]["event_count"] != halt["event_count"] or entry["source"] != effective_source:
                    raise ValueError("positive halt row disagrees with retained memory")
            elif entry is not None:
                raise ValueError("unresolved memory cannot coexist with an unblocked current row")


def validate_continuity(current, previous):
    """Prove a receipt retained prior exclusions or sourced their resolution.

The publisher still owns the compare-and-swap identity of the prior receipt.
This check supplies the separate semantic guarantee: replacing that receipt
cannot silently erase a known halt, including when there are no current rows.
"""
    checked = _instant(current["coverage"]["halts"]["checked_at"])
    validate(current, list(current["symbols"]), checked)
    if previous is not None:
        validate(previous, list(previous["symbols"]), checked)
    if _retain(deepcopy(current), previous) != current:
        raise ValueError("halt continuity would lose or alter retained exclusions")


def observe(symbols, now, *, fetcher=None, previous=None):
    """One shared source fetch for bounded symbols, with explicit unknown coverage.

``fetcher`` is a test boundary returning bytes at ``body``, an offset-aware
``fetched_at`` and optional HTTP ``http_date``. Errors are reduced to fixed
public wording, never exception text, response markup or request headers.
"""
    evaluated = _instant(now() if callable(now) else now)
    if previous is not None:
        validate(previous, list(previous.get("symbols", {})), evaluated)
    symbols = list(dict.fromkeys(symbols))
    if len(symbols) > MAX_SYMBOLS or any(not isinstance(s, str) or len(s) > MAX_SYMBOL_LENGTH or not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-/$]*", s) for s in symbols):
        raise ValueError("invalid morning halt symbols")
    source = {"provider": SOURCE_NAME, "source_url": SOURCE_URL, "scope": SCOPE,
              "status": "not_requested" if not symbols else "unavailable", "checked_at": _iso(evaluated),
              "fetched_at": None, "source_published_at": None, "expires_at": None,
              "source_sha256": None, "http_date": None, "item_count": None,
              "source_age_seconds": None, "receipt_age_seconds": None,
              "reason": "No admitted candidates required a halt lookup." if not symbols else "The halt source could not be verified; current coverage is unknown."}
    events = []
    if symbols:
        try:
            received = (fetcher or fetch)()
            evaluated = _instant(now() if callable(now) else now)
            source["checked_at"] = _iso(evaluated)
            fetched = _instant(received["fetched_at"])
            parsed = parse(received["body"])
            published = _instant(parsed["source_published_at"])
            source_age = (evaluated - published).total_seconds()
            receipt_age = (evaluated - fetched).total_seconds()
            if source_age < -FUTURE_SKEW_SECONDS or receipt_age < -FUTURE_SKEW_SECONDS or published > fetched + timedelta(seconds=FUTURE_SKEW_SECONDS):
                raise ValueError("future halt source clock")
            if any(_instant(event["halted_at"]) > evaluated + timedelta(seconds=FUTURE_SKEW_SECONDS) for event in parsed["events"]):
                raise ValueError("future reported halt")
            fresh = source_age <= SOURCE_MAX_AGE_SECONDS and receipt_age <= RECEIPT_MAX_AGE_SECONDS
            expiry = min(published + timedelta(seconds=SOURCE_MAX_AGE_SECONDS),
                         fetched + timedelta(seconds=RECEIPT_MAX_AGE_SECONDS))
            source.update(status="fresh" if fresh else "stale", fetched_at=_iso(fetched),
                          source_published_at=_iso(published), expires_at=_iso(expiry),
                          source_sha256=hashlib.sha256(received["body"]).hexdigest(),
                          item_count=parsed["item_count"], source_age_seconds=source_age,
                          receipt_age_seconds=receipt_age,
                          http_date=received.get("http_date") if isinstance(received.get("http_date"), str) and len(received["http_date"]) <= MAX_FIELD_LENGTH else None,
                          reason="Snapshot retrieved; unmatched names are not cleared." if fresh else "The halt snapshot is stale; unresolved reported halts remain exclusions.")
            events = parsed["events"]
        except (ValueError, TypeError, KeyError, UnicodeError, ET.ParseError, OSError):
            pass
    result = {"coverage": {"halts": source,
                         "issuer_news": {"status": "not_checked", "reason": "Comprehensive current issuer news has not been checked."},
                         "earnings": {"status": "not_checked", "reason": "The current earnings calendar has not been checked."}},
            "symbols": {symbol: {"halt": _halt([event for event in events if event["symbol"] == symbol], evaluated, source["status"],
                                                  _instant(source["source_published_at"]) if source["source_published_at"] else None)} for symbol in symbols}}
    return _retain(result, previous)
