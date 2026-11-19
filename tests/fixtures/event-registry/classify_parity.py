"""The registry readings the page must make as the run makes them. The page
flags a listed row that carries no plan when its ticker is in the record's
ARCHIVED event registry (`docs/app.js` registryMatch()), which mirrors
`src/event_risk.py` classify(); this corpus carries classify()'s own answer for
a SYNTHETIC registry (no real issuer, no real filing) on every boundary day of
every entry, read under its own symbol: the day before, the day and the day
after each active_from, active_until, review_due, source date and resolution
date. The browser suite
(`tools/page_text_cases.mjs`) runs the page's registryMatch() over every case
and `tests/test_page_text.py` holds this file to the generator and to the
module. Usage: python classify_parity.py [--check]"""
import json, sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from src import event_risk  # noqa: E402

OUT = Path(__file__).resolve().parent / "classify-parity.json"


def _source(title, day, n):
    return {"title": title, "published_on": day, "url": f"https://example.invalid/synthetic/{n}",
            "sha256": f"{n:064x}", "quote": f"Synthetic quote {n}; not a real filing."}


def _event(ident, symbol, sources, active_from, reviewed_on, review_due, *, active_until=None, resolution=None):
    days = sorted(s["published_on"] for s in sources)
    event = {"id": ident, "symbol": symbol, "issuer": f"Synthetic issuer {symbol}", "kind": "cash_acquisition",
             "announced_on": days[0], "active_from": active_from, "active_until": active_until,
             "evidence_as_of": days[-1], "reviewed_on": reviewed_on, "review_due": review_due,
             "reason": f"Synthetic entry {ident}: a pending cash deal invented for this corpus.", "sources": sources}
    if resolution is not None:
        event["resolution"] = resolution
    return event


#: A synthetic registry in the module's own shape (validate_registry() accepts
#: it): an open entry with a later source, an entry that starts after its
#: announcement, a resolved entry, a symbol with two entries whose intervals
#: overlap, a dotted symbol, and an entry whose review is due the day it was
#: reviewed.
REGISTRY = event_risk.validate_registry({
    "version": event_risk.VERSION, "coverage": event_risk.COVERAGE, "reviewed_on": "2026-04-30",
    "coverage_note": "A synthetic registry for the page's parity corpus; no entry is a real event.",
    "events": [
        _event("synthetic-open", "AAA", [_source("Open deal announced", "2026-03-02", 1),
                                         _source("Open deal update", "2026-03-10", 2)],
               "2026-03-02", "2026-03-12", "2026-03-20"),
        _event("synthetic-late-start", "BBB", [_source("Late start announced", "2026-03-03", 3),
                                               _source("Late start update", "2026-03-06", 11)],
               "2026-03-05", "2026-03-12", "2026-03-19"),
        _event("synthetic-resolved", "CCC", [_source("Resolved deal announced", "2026-03-04", 4)],
               "2026-03-04", "2026-03-27", "2026-03-27", active_until="2026-03-25",
               resolution=_source("Resolved deal completed", "2026-03-24", 5)),
        _event("synthetic-twin-first", "DDD", [_source("Twin first announced", "2026-03-06", 6)],
               "2026-03-06", "2026-03-13", "2026-03-16"),
        _event("synthetic-twin-second", "DDD", [_source("Twin second announced", "2026-03-11", 7),
                                                _source("Twin second update", "2026-03-17", 8)],
               "2026-03-11", "2026-03-18", "2026-03-26"),
        _event("synthetic-dotted", "EE.F", [_source("Dotted symbol announced", "2026-03-09", 9)],
               "2026-03-09", "2026-03-12", "2026-03-23"),
        _event("synthetic-due-at-review", "GGG", [_source("Due at review announced", "2026-03-12", 10)],
               "2026-03-12", "2026-03-12", "2026-03-12"),
    ],
})
#: Symbols as a record could spell them, and ones classify() must not match.
EXTRA_SYMBOLS = ["aaa", " AAA ", "AAAA", "AA", "ZZZ", "ee.f", "EE-F"]


def _boundaries(symbol):
    """The day before, the day and the day after every date an entry for this
    symbol carries; a symbol with no entry is read on every entry's start."""
    events = [e for e in REGISTRY["events"] if e["symbol"] == symbol.strip().upper()]
    days = set()
    for event in events or REGISTRY["events"]:
        marks = [event["active_from"]]
        if events:
            marks += [event["review_due"], event["announced_on"], event["reviewed_on"]]
            marks += [s["published_on"] for s in event["sources"]]
            if event.get("active_until"):
                marks += [event["active_until"], event["resolution"]["published_on"]]
        for mark in marks:
            day = date.fromisoformat(mark)
            days.update((day + timedelta(days=step)).isoformat() for step in ((-1, 0, 1) if events else (0,)))
    return sorted(days)


def _expect(symbol, session):
    result = event_risk.classify(symbol, session, registry=REGISTRY)
    return {"symbol": result["symbol"], "status": result["status"], "blocked": result["blocked"],
            "reason": result["reason"], "registry_reviewed_on": result["registry_reviewed_on"],
            "matches": [{"id": m["id"], "review_overdue": m["review_overdue"], "evidence_as_of": m["evidence_as_of"],
                         "active_until": m.get("active_until"), "sources": [s["published_on"] for s in m["sources"]],
                         "resolution": bool(m.get("resolution"))} for m in result["matches"]]}


def cases():
    symbols = sorted({e["symbol"] for e in REGISTRY["events"]}) + EXTRA_SYMBOLS
    return [{"symbol": symbol, "session": session, "expect": _expect(symbol, session)}
            for symbol in symbols for session in _boundaries(symbol)]


def render():
    return json.dumps({"generator": "tests/fixtures/event-registry/classify_parity.py",
                       "note": "Synthetic registry and sessions; no entry is a real issuer, deal or filing.",
                       "registry": REGISTRY, "cases": cases()}, indent=1, ensure_ascii=True) + "\n"


if __name__ == "__main__":
    text = render()
    if "--check" in sys.argv[1:]:
        current = OUT.read_text() if OUT.exists() else None
        print("event-registry parity corpus " + ("current" if current == text else "STALE"))
        sys.exit(0 if current == text else 1)
    OUT.write_text(text)
    print(f"wrote {len(json.loads(text)['cases'])} cases")
