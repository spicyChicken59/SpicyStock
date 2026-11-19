"""Dated, source-backed exclusions for manually reviewed corporate events.

This bounded registry is not a live news feed or an exhaustive event screen.
No match means only that this registry has no applicable entry. An unresolved
event never becomes tradable merely because its review date has passed.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from src.plan import NO_ORDER

VERSION = 1
MAX_EVENTS = 128
MAX_SOURCES = 8
MAX_TEXT_LENGTH = 2000
COVERAGE = "manual_known_events_only"
POLICY = "unresolved_cash_acquisitions_withhold_new_entries"
REGISTRY_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "event-risk.json"


def _day(value):
    if isinstance(value, datetime):
        raise ValueError("event-risk session must be a date, not a timestamp")
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError("event-risk date must be YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ValueError("event-risk date must be YYYY-MM-DD") from None
    if parsed.isoformat() != value:
        raise ValueError("event-risk date must be YYYY-MM-DD")
    return parsed


def _text(value, field):
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_TEXT_LENGTH:
        raise ValueError(f"event-risk invalid {field}")


def _source(source):
    if not isinstance(source, dict):
        raise ValueError("event-risk source must be an object")
    for field in ("title", "quote", "url"):
        _text(source.get(field), field)
    url = urlsplit(source["url"])
    if url.scheme != "https" or not url.hostname or url.username or url.password:
        raise ValueError("event-risk source must use an HTTPS URL without credentials")
    if not isinstance(source.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", source["sha256"]):
        raise ValueError("event-risk source requires a SHA-256 digest")
    return _day(source.get("published_on"))


def validate_registry(registry):
    """Reject malformed evidence before it can silently turn into no match."""
    if not isinstance(registry, dict) or type(registry.get("version")) is not int or registry["version"] != VERSION:
        raise ValueError("event-risk unsupported registry version")
    if registry.get("coverage") != COVERAGE:
        raise ValueError("event-risk coverage must identify manual known events")
    reviewed = _day(registry.get("reviewed_on"))
    _text(registry.get("coverage_note"), "coverage_note")
    entries = registry.get("events")
    if not isinstance(entries, list) or len(entries) > MAX_EVENTS:
        raise ValueError("event-risk invalid events list")
    identities = set()
    for event in entries:
        if not isinstance(event, dict):
            raise ValueError("event-risk event must be an object")
        for field in ("id", "issuer", "reason"):
            _text(event.get(field), field)
        if event["id"] in identities:
            raise ValueError("event-risk duplicate event id")
        identities.add(event["id"])
        if not isinstance(event.get("symbol"), str) or not re.fullmatch(r"[A-Z][A-Z0-9.\-]*", event["symbol"]):
            raise ValueError("event-risk invalid symbol")
        if event.get("kind") != "cash_acquisition":
            raise ValueError("event-risk unsupported event kind")
        announced = _day(event.get("announced_on"))
        start = _day(event.get("active_from"))
        as_of = _day(event.get("evidence_as_of"))
        checked = _day(event.get("reviewed_on"))
        due = _day(event.get("review_due"))
        if not announced <= start <= as_of <= checked <= reviewed or due < checked:
            raise ValueError("event-risk inconsistent event dates")
        sources = event.get("sources")
        if not isinstance(sources, list) or not sources or len(sources) > MAX_SOURCES:
            raise ValueError("event-risk invalid sources list")
        source_days = [_source(source) for source in sources]
        if min(source_days) != announced or max(source_days) != as_of:
            raise ValueError("event-risk evidence dates do not match sources")
        if event.get("active_until") is not None:
            end = _day(event["active_until"])
            resolution_day = _source(event.get("resolution"))
            if not start < end or not resolution_day <= end <= checked:
                raise ValueError("event-risk ending requires a dated, reviewed resolution")
        if "review_note" in event:
            note = event["review_note"]
            if not isinstance(note, dict) or set(note) != {"noted_on", "text"}:
                raise ValueError("event-risk review note must be an object of noted_on and text")
            _text(note.get("text"), "review_note")
            if not due < _day(note.get("noted_on")) <= reviewed:
                raise ValueError("event-risk review note must be dated after the review it answers")
    return registry


#: (P) a review note answers for this many calendar days after it is written; past them the
#: entry is due again, so a note never silences an entry for good
REVIEW_NOTE_DAYS = 14


def lapsed_reviews(registry, today):
    """The unresolved entries whose review date has passed with no note in force.

    A note is written after an overdue review and says why the entry stands as
    it is; it never clears a stock (``classify()`` still withholds an overdue
    entry), and it answers for ``REVIEW_NOTE_DAYS`` after its ``noted_on``:
    past that, the entry is due again until it is reviewed, resolved or noted
    anew. ``today`` is the caller's date: ``tools/check_event_reviews.py``
    passes the real one, so CI goes red the day after a review or a note lapses."""
    registry = validate_registry(registry)
    day = _day(today)

    def answered(event):
        note = event.get("review_note")
        return note is not None and day <= _day(note["noted_on"]) + timedelta(days=REVIEW_NOTE_DAYS)
    return [event["symbol"] for event in registry["events"]
            if event.get("active_until") is None and _day(event["review_due"]) < day and not answered(event)]


def registry_digest(registry):
    """Stable evidence identity; source text, dates and review changes all count."""
    return hashlib.sha256(json.dumps(registry, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


REGISTRY = validate_registry(json.loads(REGISTRY_PATH.read_text(encoding="utf-8")))
RULES = {
    "event_risk.version": VERSION,
    "event_risk.policy": POLICY,
    "event_risk.coverage": COVERAGE,
    "event_risk.max_events": MAX_EVENTS,
    "event_risk.max_sources": MAX_SOURCES,
    "event_risk.max_text_length": MAX_TEXT_LENGTH,
    "event_risk.registry_sha256": registry_digest(REGISTRY),
    "event_risk.registry": deepcopy(REGISTRY),
}


def classify(symbol, session, *, registry=None):
    """Classify one session using only the supplied, optionally archived registry.

Active intervals include the public announcement date and exclude a sourced
resolution date. Evidence published after the evaluated date is not presented
as evidence available on that date. Review expiry continues to withhold orders
and reports uncertainty; it is never an automatic clearance.
"""
    registry = validate_registry(REGISTRY if registry is None else registry)
    evaluated = _day(session)
    if not isinstance(symbol, str) or not re.fullmatch(r"[A-Z][A-Z0-9.\-]*", symbol.strip().upper()):
        raise ValueError("event-risk invalid symbol")
    symbol = symbol.strip().upper()
    matches = []
    for event in registry["events"]:
        if event["symbol"] != symbol or evaluated < _day(event["active_from"]):
            continue
        if event.get("active_until") is not None and evaluated >= _day(event["active_until"]):
            continue
        matched = deepcopy(event)
        # the note is the registry's own record of an overdue review: a match
        # carries the event as a classification reads it, and the note clears nothing
        matched.pop("review_note", None)
        matched["sources"] = [source for source in matched["sources"]
                              if _day(source["published_on"]) <= evaluated]
        matched["evidence_as_of"] = max(source["published_on"] for source in matched["sources"])
        if matched.get("resolution") and _day(matched["resolution"]["published_on"]) > evaluated:
            del matched["resolution"]
            matched["active_until"] = None
        matched["review_overdue"] = evaluated > _day(event["review_due"])
        matches.append(matched)
    overdue = any(event["review_overdue"] for event in matches)
    status = "review_required" if overdue else "known_event" if matches else "not_in_registry"
    reason = ("Known cash-acquisition event: " + " ".join(event["reason"] for event in matches)
              + (" The manual review is overdue; new entries remain withheld pending a source review." if overdue else "")
              if matches else "No applicable entry in the manual event registry; live news and other corporate events have not been cleared.")
    return {"version": VERSION, "coverage": COVERAGE, "registry_sha256": registry_digest(registry),
            "registry_reviewed_on": registry["reviewed_on"], "session": evaluated.isoformat(),
            "symbol": symbol, "blocked": bool(matches), "status": status,
            "reason": reason, "matches": matches}


def apply(planned, ticker, session, *, registry=None):
    """Return a plan with evidence; a known event removes every executable order.

The original plan and its geometry remain available for research. Existing
refusals can only be narrowed, and an unmatched entry never restores an order.
"""
    result = deepcopy(planned)
    evidence = classify(ticker, session, registry=registry)
    result["event_risk"] = evidence
    if evidence["blocked"]:
        original_reason = result.get("reason")
        result.update(eligible=False, action="refused", reason=evidence["reason"], **NO_ORDER)
        result["flags"] = list(dict.fromkeys([*(result.get("flags") or []), "event_risk"]))
        if original_reason and original_reason != evidence["reason"]:
            result["notes"] = [*(result.get("notes") or []), original_reason]
    return result
