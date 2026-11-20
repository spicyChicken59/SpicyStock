"""The go-live gate (``run.go_live``): whether an execution agent may treat
``orders.json`` as live rather than paper.

It is true only when all four criteria hold, each read from committed bytes:

* ``fidelity_protocol``: the owner has recorded the one-sitting Fidelity
  protocol (``knowledge/broker-fidelity-protocol.md``) as passed in
  ``knowledge/go-live/fidelity-protocol.json``. Nothing here can pass it.
* ``on_time_sessions``: the ``ON_TIME_SESSIONS`` XNYS sessions up to the one
  before tonight's, consecutive and with none missing before tonight, were
  each published by ``PUBLISH_BY_ET`` on the session's own date (measured at
  the run's finish: its start clock plus its own elapsed seconds, the record
  installed then and committed a few minutes later), started automatically (a
  scheduled run, or the external dispatcher's ``only_if_unpublished``
  dispatch; a hand-run publish does not count) and had a morning check bound
  to that publication that ran (``MORNING_RAN``, not a rehearsal) inside its
  collection window and by ``MORNING_DUE_CT`` on the session its plans were
  for. The ledger closes a session the evening after, when its morning file
  exists, and starts with the first record that archives how its run was
  started (``run.trigger``).
* ``settled_forward_plans``: at least ``MIN_SETTLED_FORWARD`` model plans
  settled in the scorecard's window, each picked on or after the session
  from which the strategy's rules have stood unchanged (the rules digest
  without ``NON_STRATEGY_RULES``: the nightly universe membership and the
  event registry's entries and review dates, which are data the run reads,
  not strategy rules). A change first seen on a backfill of an older session
  stands from the session after the newest one already published, so a
  backfill's picks are never forward plans.
* ``ablation_report``: the pre-registered ablation's results are committed.

Until it is true, ``orders.json`` is paper only. It recommends nothing and
places nothing; it says whether the owner's own conditions for trusting the
file have been met.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

VERSION = 1
ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_FILE = ROOT / "knowledge" / "go-live" / "fidelity-protocol.json"
#: the unpassed copy the tests and the fixture generators read, so the owner's record moves no fixture
PINNED_PROTOCOL_FILE = ROOT / "tests" / "fixtures" / "go-live" / "fidelity-protocol.json"
ABLATION_FILE = ROOT / "docs" / "input-truthfulness" / "2026-11-19-ablation" / "ablation.json"
#: (owner's decision, 19 November 2026) the consecutive sessions the service must hold
ON_TIME_SESSIONS = 10
#: (owner's decision) a publication counts on time at or before this New York time on its session's date
PUBLISH_BY_ET = "19:00"
#: (owner's decision) the morning file is on time at or before this Chicago time on the applicable session
MORNING_DUE_CT = "08:45"
#: (owner's decision) the settled forward plans the gate needs under the standing rules
MIN_SETTLED_FORWARD = 20
#: the ledger keeps this many closed sessions
LEDGER_MAX = 30
#: the rules a strategy digest leaves out: the night's universe membership moves every night, and
#: the event registry (its entries, review dates and notes, and its digest) is reviewed on a calendar
NON_STRATEGY_RULES = (("universe", "identity"), ("event_risk", "registry"), ("event_risk", "registry_sha256"))
#: a morning check counts only when it ran: the statuses tools/service_watch.py reads as a check that ran
MORNING_RAN = ("observed", "partial", "no_tickets")
CRITERIA = ("fidelity_protocol", "on_time_sessions", "settled_forward_plans", "ablation_report")
REASONS = {
    "fidelity_protocol": "the owner has not recorded the Fidelity protocol as passed",
    "on_time_sessions": "fewer consecutive sessions than the gate needs were published and checked on time",
    "settled_forward_plans": "fewer model plans than the gate needs have settled under the standing rules",
    "ablation_report": "the pre-registered ablation's results are not committed",
}
NEW_YORK, CHICAGO = ZoneInfo("America/New_York"), ZoneInfo("America/Chicago")
RULES = {"go_live.version": VERSION, "go_live.on_time_sessions": ON_TIME_SESSIONS,
         "go_live.publish_by_et": PUBLISH_BY_ET, "go_live.morning_due_ct": MORNING_DUE_CT,
         "go_live.min_settled_forward": MIN_SETTLED_FORWARD}


def _dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _instant(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        out = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return out if out.tzinfo else None


def _day(value) -> date | None:
    """An ISO date a row names, or None: a ledger read off disk is never trusted to parse."""
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _clock(text: str) -> time:
    hour, minute = text.split(":")
    return time(int(hour), int(minute))


def strategy_digest(rules: dict) -> str:
    """The rules digest without what is not a strategy rule (``NON_STRATEGY_RULES``)."""
    kept = {family: {k: v for k, v in block.items() if (family, k) not in NON_STRATEGY_RULES}
            for family, block in (rules or {}).items() if isinstance(block, dict)}
    return hashlib.sha256(json.dumps(kept, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def trigger_from(env: dict) -> dict:
    """How the evening run was started, as the workflow tells it."""
    event = env.get("SCAN_TRIGGER_EVENT") or None
    flag = env.get("SCAN_TRIGGER_ONLY_IF_UNPUBLISHED")
    return {"event": event, "only_if_unpublished": None if flag is None else flag == "true"}


def automatic(trigger) -> bool | None:
    """A scheduled run, or the dispatcher's guarded dispatch, counts as
    automatic; a hand-run dispatch does not; an unrecorded trigger is unknown."""
    t = _dict(trigger)
    if t.get("event") is None:
        return None
    return t["event"] == "schedule" or (t["event"] == "workflow_dispatch" and t.get("only_if_unpublished") is True)


def close_session(previous: dict, previous_sha256: str | None, morning: dict | None) -> dict | None:
    """The ledger entry for the publication before this run: was it on time,
    automatic, and checked by a morning file in time. None when there is no
    real previous publication to close."""
    run = _dict(previous.get("run"))
    session, published = run.get("session"), _instant(run.get("published_at"))
    if _day(session) is None or previous.get("fixture"):
        return None
    from src import freshness
    on_time = None
    elapsed = run.get("elapsed_seconds")
    if published is not None and isinstance(elapsed, (int, float)) and not isinstance(elapsed, bool) and elapsed >= 0:
        try:
            local = (published + timedelta(seconds=elapsed)).astimezone(NEW_YORK)
        except (OverflowError, ValueError):      # an elapsed time no clock can hold is no finish
            local = None
        if local is not None:
            on_time = local.date().isoformat() == session and local.time() <= _clock(PUBLISH_BY_ET)
    applicable = _dict(run.get("timing")).get("applicable_session")
    receipt = _dict(morning)
    bound = previous_sha256 is not None and _dict(receipt.get("publication")).get("data_sha256") == previous_sha256
    generated = _instant(receipt.get("generated_at")) if bound else None
    window_start = _instant(freshness.morning_window(previous).get("collection_starts_at"))
    ran = receipt.get("status") in MORNING_RAN and receipt.get("dry_run") is False
    morning_on_time = None if not isinstance(applicable, str) else bool(
        generated is not None and ran and window_start is not None and generated >= window_start
        and generated.astimezone(CHICAGO).date().isoformat() == applicable
        and generated.astimezone(CHICAGO).time() <= _clock(MORNING_DUE_CT))
    auto = automatic(run.get("trigger"))
    return {"session": session, "published_at": run.get("published_at"), "on_time": on_time,
            "automatic": auto, "applicable_session": applicable,
            "morning_generated_at": receipt.get("generated_at") if bound else None,
            "morning_status": receipt.get("status") if bound and isinstance(receipt.get("status"), str) else None,
            "morning_on_time": morning_on_time,
            "counted": on_time is True and auto is True and morning_on_time is True}


def ledger_of(previous_block, entry: dict | None) -> list[dict]:
    kept = _dict(previous_block).get("ledger")
    rows = [r for r in (kept if isinstance(kept, list) else []) if isinstance(r, dict) and _day(r.get("session")) is not None]
    if entry is not None:
        rows = [r for r in rows if r["session"] != entry["session"]] + [entry]
    return sorted(rows, key=lambda r: r["session"])[-LEDGER_MAX:]


def consecutive(ledger: list[dict], session: str | None = None) -> int:
    """The counted sessions at the ledger's end, each the XNYS session before
    the next: a session not counted, or one missing between two, ends it.
    Given tonight's ``session``, the run must end on the XNYS session before
    it: a session never published before tonight leaves no row, so a run that
    ends earlier is broken by it and counts nothing."""
    from src import sessions
    n, later = 0, None
    if session is not None:
        tonight = _day(session)
        if tonight is None or not ledger or ledger[-1].get("session") != sessions.previous_session(tonight).isoformat():
            return 0
    for row in reversed(ledger):
        day = _day(row.get("session"))
        if row.get("counted") is not True or day is None:
            break
        if later is not None and sessions.next_sessions(day, 1)[0] != later:
            break
        n, later = n + 1, day
    return n


def first_forward_session(session: str, published: str | None) -> str:
    """The session from which a change of the strategy's rules stands: tonight's,
    or, when tonight is a backfill of a session older than the newest one
    already published, the session after that one, so a backfill's picks (made
    after the fact) never count as forward plans."""
    from src import sessions
    newest = _day(published)
    if newest is not None and published >= session:
        return sessions.next_sessions(newest, 1)[0].isoformat()
    return session


def protocol() -> dict:
    """The owner's record of the Fidelity protocol, or an unpassed one."""
    try:
        value = json.loads(PROTOCOL_FILE.read_text())
    except (OSError, ValueError):
        value = None
    if not isinstance(value, dict):
        return {"passed": False, "recorded_on": None, "detail": "no readable record of the protocol"}
    try:
        recorded = date.fromisoformat(value["recorded_on"]).isoformat() if isinstance(value.get("recorded_on"), str) else None
    except ValueError:
        recorded = None
    passed = value.get("passed") is True and recorded is not None and value.get("recorded_by") == "owner"
    return {"passed": passed, "recorded_on": recorded,
            "detail": "recorded as passed by the owner" if passed else "not recorded as passed by the owner"}


def ablation() -> bool:
    try:
        value = json.loads(ABLATION_FILE.read_text())
    except (OSError, ValueError):
        return False
    return isinstance(value, dict) and value.get("version") == "ablation-v1"


def build(*, session: str, rules: dict, previous: dict, previous_sha256: str | None, morning: dict | None,
          scorecard_rows: list[dict]) -> dict:
    """``run.go_live`` for one evening."""
    previous_block = _dict(_dict(previous.get("run")).get("go_live"))
    entry = None if _dict(previous.get("run")).get("session") == session else close_session(previous, previous_sha256, morning)
    ledger = ledger_of(previous_block, entry)
    digest = strategy_digest(rules)
    standing = _dict(previous_block.get("strategy"))
    if standing.get("digest") == digest and isinstance(standing.get("since"), str):
        since = standing["since"]
    else:
        since = first_forward_session(session, _dict(previous.get("run")).get("session"))
    settled = sum(1 for r in scorecard_rows if isinstance(r, dict) and r.get("bucket") == "settled"
                  and isinstance(r.get("picked"), str) and r["picked"] >= since)
    held = consecutive(ledger, session)
    fid = protocol()
    criteria = [
        {"key": "fidelity_protocol", "met": fid["passed"], "have": fid["recorded_on"], "need": None, "detail": fid["detail"]},
        {"key": "on_time_sessions", "met": held >= ON_TIME_SESSIONS, "have": held, "need": ON_TIME_SESSIONS,
         "detail": f"{held} consecutive of {ON_TIME_SESSIONS}"},
        {"key": "settled_forward_plans", "met": settled >= MIN_SETTLED_FORWARD, "have": settled,
         "need": MIN_SETTLED_FORWARD, "detail": f"{settled} settled since {since} of {MIN_SETTLED_FORWARD}"},
        {"key": "ablation_report", "met": ablation(), "have": None, "need": None,
         "detail": ABLATION_FILE.relative_to(ROOT).as_posix()},
    ]
    ready = all(c["met"] for c in criteria)
    block = {"version": VERSION, "ready": ready, "criteria": criteria,
             "reasons": [c["key"] for c in criteria if not c["met"]],
             "strategy": {"digest": digest, "since": since}, "ledger": ledger}
    block["sentence"] = sentence(block)
    return block


def sentence(block: dict) -> str:
    if block["ready"]:
        return "Live ready: every go-live condition holds; orders.json is no longer paper only."
    return ("Paper only: " + "; ".join(f"{c['key'].replace('_', ' ')} not met ({c['detail']})"
                                       for c in block["criteria"] if not c["met"]) + ".")


def faults(data: dict) -> list[str]:
    """The block's shape, under the rules that write it."""
    archived = _dict(data.get("rules")).get("go_live")
    block = _dict(data.get("run")).get("go_live")
    if archived is None:
        return [] if block is None else ["run.go_live present under rules that do not write it"]
    if not isinstance(block, dict) or block.get("version") != VERSION:
        return ["run.go_live is missing or not this version"]
    crit = block.get("criteria")
    if not isinstance(crit, list) or [c.get("key") if isinstance(c, dict) else None for c in crit] != list(CRITERIA):
        return ["run.go_live criteria are not the gate's"]
    out = []
    if block.get("ready") is not all(c.get("met") is True for c in crit):
        out.append("run.go_live ready is not its criteria's")
    if block.get("reasons") != [c["key"] for c in crit if c.get("met") is not True]:
        out.append("run.go_live reasons are not its unmet criteria")
    if not isinstance(block.get("ledger"), list) or not isinstance(block.get("sentence"), str):
        out.append("run.go_live ledger or sentence is not readable")
        return out
    by_key = {c["key"]: c for c in crit}
    for key, need in (("on_time_sessions", _dict(archived).get("on_time_sessions")),
                      ("settled_forward_plans", _dict(archived).get("min_settled_forward"))):
        c = by_key[key]
        have = c.get("have")
        if not (type(have) is int and type(need) is int and c.get("need") == need) or c.get("met") is not (have >= need):
            out.append(f"run.go_live {key} is not its count against the archived need")
    session = _dict(data.get("run")).get("session")
    ledger = [r for r in block["ledger"] if isinstance(r, dict) and _day(r.get("session")) is not None]
    if len(ledger) != len(block["ledger"]) or _day(session) is None:
        out.append("run.go_live ledger rows are not readable")
    elif by_key["on_time_sessions"].get("have") != consecutive(ledger, session):
        out.append("run.go_live on_time_sessions is not the run its own ledger ends on before tonight")
    return out
