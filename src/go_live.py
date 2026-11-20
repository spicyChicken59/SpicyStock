"""The go-live gate (``run.go_live``): whether an execution agent may treat
``orders.json`` as live rather than paper.

It is true only when all four criteria hold:

* ``fidelity_protocol``: the owner has recorded the one-sitting Fidelity
  protocol (``PROTOCOL_NAME``) as passed in
  ``knowledge/go-live/fidelity-protocol.json``, dated no later than
  tonight's session. Nothing here can pass it.
* ``on_time_sessions``: the ``ON_TIME_SESSIONS`` XNYS sessions up to the one
  before tonight's, consecutive and with none missing before tonight, were
  each published by ``PUBLISH_BY_ET`` on the session's own date, started
  automatically and checked by a morning check that ran.
  The publication clock is the run's finish: its start clock plus
  ``run.finish_seconds``, stamped at the record's final write after delivery
  (``pipeline.restamp()``); the commit follows within seconds.
  Automatic is a scheduled run, or the external dispatcher's
  ``only_if_unpublished`` dispatch; a hand-run publish does not count.
  The morning check is the newest receipt on main the evening after: bound
  to that publication, a status of ``MORNING_RAN``, not a rehearsal, inside
  its collection window and by ``MORNING_DUE_CT`` on the session its plans
  were for. How that check was started is not read.
  The ledger closes a session the evening after, from a real publication
  only (``PUBLISHED_STATUSES``, not a rehearsal). Its first row is the last
  record made before ``run.trigger``, which is not counted.
* ``settled_forward_plans``: at least ``MIN_SETTLED_FORWARD`` model plans
  settled in the scorecard's window, each picked on or after the session
  from which the archived rules have stood unchanged, and each from a
  forward publication. The digest leaves out only ``NON_STRATEGY_RULES``
  (the nightly universe membership and the event registry), so any other
  archived rule restarts the count. A publication is forward when it is of a
  session no older than the newest already published and was made before
  the open its plans are for; a backfill's session, or a late run's, is kept
  in ``strategy.not_forward`` and its picks never count. The count is the
  night's own walk of the pick ledger over that night's bars.
* ``ablation_report``: the pre-registered ablation's results are committed,
  under the committed spec they name.

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
#: the sessions kept whose publication was not forward (a backfill, or a run at or after the open
#: its plans were for): more than the scorecard's window, so no row it can still read is forgotten
NOT_FORWARD_MAX = 120
#: a record counts as a publication under the evening guard's own definition: not a rehearsal,
#: and a status the guard reads as published
PUBLISHED_STATUSES = ("ok", "degraded")
#: the protocol the owner's record must name, and the record's own version
PROTOCOL_NAME = "knowledge/broker-fidelity-protocol.md"
PROTOCOL_RECORD_VERSION = 1
ABLATION_VERSION = "ablation-v1"
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
    if run.get("dry_run") is not False or run.get("status") not in PUBLISHED_STATUSES:
        return None                                 # a rehearsal, or a night that published nothing new
    from src import freshness
    on_time = None
    elapsed = run.get("finish_seconds")
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


def newest_published(previous: dict, standing: dict) -> str | None:
    """The newest session any record in the chain has published: the record on
    disk's own, or the newest its gate remembers (after a backfill the record
    on disk is the older one)."""
    days = [d for d in (_dict(previous.get("run")).get("session"), standing.get("newest")) if _day(d) is not None]
    return max(days) if days else None


def forward(session: str, newest: str | None, published_at: str | None, opens_at: str | None) -> bool:
    """Whether tonight's publication is forward: of a session no older than the
    newest already published, and made before the open its plans are for. A
    backfill, and a run at or after that open, writes picks after the fact;
    a run whose own clock or open cannot be read is not shown to be forward."""
    made, opens = _instant(published_at), _instant(opens_at)
    if made is None or opens is None or made >= opens:
        return False
    return newest is None or session >= newest


def first_forward_session(session: str, newest: str | None, is_forward: bool) -> str:
    """The session from which a change of the strategy's rules stands: tonight's
    when tonight's publication is forward, else the session after the newest
    one published (tonight's included), so picks written after the fact never
    count as forward plans."""
    from src import sessions
    if is_forward:
        return session
    last = max(d for d in (session, newest) if _day(d) is not None)
    return sessions.next_sessions(date.fromisoformat(last), 1)[0].isoformat()


def protocol(session: str | None = None) -> dict:
    """The owner's record of the Fidelity protocol, or an unpassed one. It
    passes only as this record's own version, naming the protocol, recorded by
    the owner on a date that is not after tonight's session."""
    try:
        value = json.loads(PROTOCOL_FILE.read_text())
    except (OSError, ValueError, RecursionError):
        value = None
    if not isinstance(value, dict):
        return {"passed": False, "recorded_on": None, "detail": "no readable record of the protocol"}
    recorded = _day(value.get("recorded_on"))
    tonight = _day(session)
    passed = (value.get("passed") is True and value.get("recorded_by") == "owner"
              and value.get("version") == PROTOCOL_RECORD_VERSION and type(value.get("version")) is int
              and value.get("protocol") == PROTOCOL_NAME
              and recorded is not None and (session is None or (tonight is not None and recorded <= tonight)))
    return {"passed": passed, "recorded_on": recorded.isoformat() if recorded else None,
            "detail": "recorded as passed by the owner" if passed else "not recorded as passed by the owner"}


def ablation() -> bool:
    """The pre-registered ablation is committed: its results name this
    version, carry variants, and name a spec whose committed bytes are the
    ones they were computed under."""
    try:
        value = json.loads(ABLATION_FILE.read_text())
        if not isinstance(value, dict) or value.get("version") != ABLATION_VERSION:
            return False
        spec = value.get("spec")
        if not isinstance(spec, str) or not isinstance(value.get("variants"), dict) or not value["variants"]:
            return False
        path = (ROOT / spec).resolve()
        if ROOT not in path.parents:
            return False
        return hashlib.sha256(path.read_bytes()).hexdigest() == value.get("spec_sha256")
    except (OSError, ValueError, RecursionError):
        return False


def not_forward_of(standing: dict, session: str, is_forward: bool) -> list[str]:
    kept = standing.get("not_forward")
    days = {d for d in (kept if isinstance(kept, list) else []) if _day(d) is not None}
    if not is_forward:
        days.add(session)
    return sorted(days)[-NOT_FORWARD_MAX:]


def build(*, session: str, rules: dict, previous: dict, previous_sha256: str | None, morning: dict | None,
          scorecard_rows: list[dict], published_at: str | None = None, opens_at: str | None = None) -> dict:
    """``run.go_live`` for one evening."""
    previous_block = _dict(_dict(previous.get("run")).get("go_live"))
    entry = None if _dict(previous.get("run")).get("session") == session else close_session(previous, previous_sha256, morning)
    ledger = ledger_of(previous_block, entry)
    digest = strategy_digest(rules)
    standing = _dict(previous_block.get("strategy"))
    newest = newest_published(previous, standing)
    is_forward = forward(session, newest, published_at, opens_at)
    if standing.get("digest") == digest and _day(standing.get("since")) is not None:
        since = standing["since"]
    else:
        since = first_forward_session(session, newest, is_forward)
    not_forward = not_forward_of(standing, session, is_forward)
    settled = sum(1 for r in scorecard_rows if isinstance(r, dict) and r.get("bucket") == "settled"
                  and isinstance(r.get("picked"), str) and r["picked"] >= since and r["picked"] not in not_forward)
    held = consecutive(ledger, session)
    fid = protocol(session)
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
             "strategy": {"digest": digest, "since": since,
                          "newest": max(d for d in (session, newest) if d is not None),
                          "not_forward": not_forward},
             "ledger": ledger}
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
    standing = block.get("strategy")
    if not (isinstance(standing, dict) and isinstance(standing.get("digest"), str)
            and _day(standing.get("since")) is not None and _day(standing.get("newest")) is not None
            and isinstance(standing.get("not_forward"), list)
            and all(_day(d) is not None for d in standing["not_forward"])
            and standing["not_forward"] == sorted(set(standing["not_forward"]))
            and len(standing["not_forward"]) <= NOT_FORWARD_MAX):
        out.append("run.go_live strategy is not readable")
    elif standing["digest"] != strategy_digest(_dict(data.get("rules"))):
        out.append("run.go_live strategy digest is not the record's own rules'")
    by_key = {c["key"]: c for c in crit}
    for key, need in (("on_time_sessions", _dict(archived).get("on_time_sessions")),
                      ("settled_forward_plans", _dict(archived).get("min_settled_forward"))):
        c = by_key[key]
        have = c.get("have")
        if not (type(have) is int and type(need) is int and c.get("need") == need) or c.get("met") is not (have >= need):
            out.append(f"run.go_live {key} is not its count against the archived need")
    # every forward plan is one of the scorecard's settled plans: the count is the night's own walk of
    # the pick ledger over that night's bars, which the record summarises and does not carry
    total, forward_have = _dict(data.get("scorecard")).get("settled"), by_key["settled_forward_plans"].get("have")
    if type(total) is int and type(forward_have) is int and forward_have > total:
        out.append("run.go_live settled_forward_plans is more than the scorecard's settled plans")
    session = _dict(data.get("run")).get("session")
    ledger = [r for r in block["ledger"] if isinstance(r, dict) and _day(r.get("session")) is not None]
    if len(ledger) != len(block["ledger"]) or _day(session) is None:
        out.append("run.go_live ledger rows are not readable")
    elif by_key["on_time_sessions"].get("have") != consecutive(ledger, session):
        out.append("run.go_live on_time_sessions is not the run its own ledger ends on before tonight")
    return out
