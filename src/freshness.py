"""src.freshness -- what a record says about the NEXT publication, for a reader with its own clock.

A record knows which session it measured. It does not know whether a newer
record exists, and a file derived from it must not pretend to: a "built at"
or an "is newest" field would be stale the moment it was written. What the
record can say is when the next session completes, when the evening service
is scheduled to publish it, and the instant after which the service's own
guard will not publish it at all. An outside reader compares those instants
with its own clock and gets one of five answers, the same five steps the
page's ``status()`` walks:

1. before the next session's completion: this is the newest record that can exist;
2. before the primary slot: the next session has completed, its run is not yet due;
3. before the retry slot: pending;
4. before the recovery limit (the open of the session after the next): late, it can still publish;
5. otherwise: missing; the next session will not be published.

Everything here is read off the record: the dates and hours from
``run.calendar.schedule`` (written by ``src/sessions.py``), the two slot
times and the recovery rule from ``run.delivery.policy`` (``src/delivery.py``),
the entry window from ``run.timing`` (``src/timing.py``). Standard library
only, and no clock of its own: ``state()`` takes the reader's instant. A field
the record cannot give is None and its reason is written beside it, never
guessed from today's constants.
"""
from __future__ import annotations

from datetime import date, datetime, time as time_of_day, timedelta
from zoneinfo import ZoneInfo

VERSION = 1

NEWEST, NOT_DUE, PENDING, LATE, MISSING = "newest", "not_due", "pending", "late", "missing"
#: The five answers, in the order the steps are asked.
STATES = (NEWEST, NOT_DUE, PENDING, LATE, MISSING)
#: What ``state()`` answers when the record cannot give the instant a step needs.
UNKNOWN = "unknown"

#: The recovery rule this code knows (``delivery.RECOVERY_NEXT_OPEN``): a delayed
#: or retried run may publish a missed session until the next session opens.
RECOVERY_NEXT_OPEN = "next_session_open"

#: How long before the entry window opens the morning collector starts reading
#: (``morning.POLICY["preopen_minutes"]``; tests/test_freshness.py holds the two equal).
PREOPEN_MINUTES = 30

EXPECTED_FIELDS = ("next_session", "completion_at", "primary_slot_at", "retry_slot_at", "recovery_until")

#: The rule as an outside reader applies it, with its own clock. Fixed text:
#: the field names are ``expected()``'s, the state words are ``STATES``.
RULE = (
    "Freshness is the reader's own computation: this file carries no clock. Compare your own clock, as an instant "
    "with its UTC offset, with the instants in `service.expected`, in this order, and stop at the first that holds.",
    "1. Before `completion_at`: `newest`. The next session has not completed, so no newer record can exist yet.",
    "2. Before `primary_slot_at`: `not_due`. The next session has completed and its evening run is not yet due.",
    "3. Before `retry_slot_at`: `pending`. The first scheduled slot has passed and the retry slot has not.",
    "4. Before `recovery_until`: `late`. Both scheduled slots have passed; a delayed run can still publish the next "
    "session until that instant.",
    "5. Otherwise: `missing`. The service does not publish a session after the session that follows it has opened. "
    "If this is still the newest file the site serves, the next session was not published and every ticket in this "
    "file is expired.",
    "From step 2 on, fetch the file again before relying on it: a newer one may exist. A field that is null has its "
    "reason in `service.expected.unknown`; without the instant a step needs, freshness is unknown and the file is "
    "research only.",
)


def _instant(value) -> datetime | None:
    """An ISO-8601 instant WITH an offset, or None: a naive time decides nothing here."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None and parsed.utcoffset() is not None else None


def _day(value) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _clock(value) -> time_of_day | None:
    """The policy's HH:MM wall-clock words."""
    if not isinstance(value, str) or len(value) != 5 or value[2] != ":":
        return None
    try:
        return time_of_day(int(value[:2]), int(value[3:]))
    except ValueError:
        return None


def _dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _schedule(record) -> tuple[list, str | None, str | None]:
    """(rows in session order, start, through) of ``run.calendar.schedule``; a row
    the code cannot read whole (a date, and an opening and a completion instant
    with their offsets) makes the whole schedule unreadable, so no step is
    answered from half a calendar."""
    schedule = _dict(_dict(_dict(_dict(record).get("run")).get("calendar")).get("schedule"))
    raw = schedule.get("sessions")
    if not isinstance(raw, list) or not raw:
        return [], None, None
    rows = []
    for row in raw:
        if not isinstance(row, dict) or _day(row.get("session")) is None \
                or _instant(row.get("opens_at")) is None or _instant(row.get("completion_at")) is None:
            return [], None, None
        rows.append(row)
    rows.sort(key=lambda row: row["session"])
    start = schedule.get("start") if _day(schedule.get("start")) else rows[0]["session"]
    through = schedule.get("through") if _day(schedule.get("through")) else rows[-1]["session"]
    return rows, start, through


def covers_through(record) -> str | None:
    """The date this record answers for: the expected session of the run that
    wrote it (on a closed night, the day nobody traded), else its measured
    session. The page's ``status()`` reads the same two fields in this order."""
    run = _dict(_dict(record).get("run"))
    for name in ("expected_session", "session"):
        if _day(run.get(name)) is not None:
            return run[name]
    return None


def expected(record) -> dict:
    """The next session after the one this record covers, its completion
    instant, the evening service's two slot instants for it and the recovery
    limit (the open of the session after it). Each is an ISO-8601 instant with
    its offset, or None with its reason under ``unknown``."""
    out: dict = {"version": VERSION, "covers_through": covers_through(record),
                 **{name: None for name in EXPECTED_FIELDS}, "timezone": None, "policy": None, "unknown": {}}
    unknown = out["unknown"]

    def cannot(names, reason):
        for name in names:
            if out[name] is None:
                unknown[name] = reason

    covered = out["covers_through"]
    if covered is None:
        cannot(EXPECTED_FIELDS, "the record names no session")
        return out
    rows, start, through = _schedule(record)
    if not rows:
        cannot(EXPECTED_FIELDS, "the record carries no readable exchange schedule (run.calendar.schedule)")
        return out
    if covered < start or covered > through:
        cannot(EXPECTED_FIELDS, "the record's exchange schedule does not cover its own session")
        return out
    later = [row for row in rows if row["session"] > covered]
    if not later:
        cannot(EXPECTED_FIELDS, "the record's exchange schedule ends before the next session")
        return out
    following = later[0]
    out["next_session"] = following["session"]
    out["completion_at"] = following["completion_at"]

    run = _dict(_dict(record).get("run"))
    delivery = run.get("delivery")
    policy = _dict(_dict(delivery).get("policy"))
    if not policy:
        cannot(("primary_slot_at", "retry_slot_at"),
               "this record does not carry the evening service's schedule (run.delivery.policy)")
    else:
        primary, retry = _clock(policy.get("primary_et")), _clock(policy.get("retry_et"))
        try:
            zone = ZoneInfo(policy["timezone"]) if isinstance(policy.get("timezone"), str) else None
        except (KeyError, ValueError, OSError):
            zone = None
        if zone is None or primary is None or retry is None or not primary < retry:
            cannot(("primary_slot_at", "retry_slot_at"),
                   "the record's delivery policy does not give two slot times and a time zone this code can read")
        else:
            day = _day(following["session"])
            # the slot on the session's own date in the policy's zone: the offset is the tz database's answer
            out["primary_slot_at"] = datetime.combine(day, primary, tzinfo=zone).isoformat()
            out["retry_slot_at"] = datetime.combine(day, retry, tzinfo=zone).isoformat()
            out["timezone"] = policy["timezone"]
            out["policy"] = {"primary_et": policy["primary_et"], "retry_et": policy["retry_et"],
                             "recovery_until": policy.get("recovery_until")}

    if policy and policy.get("recovery_until") != RECOVERY_NEXT_OPEN:
        cannot(("recovery_until",), "the record's delivery policy names a recovery rule this code does not know")
    elif len(later) < 2:
        cannot(("recovery_until",), "the record's exchange schedule ends before the session after the next")
    else:
        out["recovery_until"] = later[1]["opens_at"]

    # the steps are asked in order, so the instants must be in order; a record whose are not answers nothing
    known = [_instant(out[name]) for name in ("completion_at", "primary_slot_at", "retry_slot_at", "recovery_until")
             if out[name] is not None]
    if any(a >= b for a, b in zip(known, known[1:])):
        for name in EXPECTED_FIELDS:
            out[name] = None
        unknown.clear()
        cannot(EXPECTED_FIELDS, "the record's schedule instants are not in order")
    return out


def _say(value: str | None) -> str:
    return value if value is not None else "an instant the record does not give"


def state(expected_block, now: datetime) -> dict:
    """One of ``STATES`` (or ``UNKNOWN``) and one sentence, for a reader whose
    clock reads ``now`` (an aware instant; a naive one is refused). The steps
    and their boundaries are the page's: an instant exactly at a boundary has
    passed it."""
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("freshness needs the reader's clock as an instant with an offset")
    block = _dict(expected_block)
    unknown = _dict(block.get("unknown"))
    session = block.get("next_session")
    completion, primary, retry, recovery = (_instant(block.get(name)) for name in
                                            ("completion_at", "primary_slot_at", "retry_slot_at", "recovery_until"))

    def cannot(name):
        return {"state": UNKNOWN,
                "sentence": f"Freshness is unknown: {unknown.get(name) or 'the record does not give ' + name}. "
                            "Treat this file as research only."}

    if completion is None:
        return cannot("completion_at")
    if now < completion:
        return {"state": NEWEST,
                "sentence": f"This is the newest record that can exist: the next session ({session}) does not "
                            f"complete until {block['completion_at']}."}
    if primary is None or retry is None:
        # a record from before the service archived its schedule: the page names no slot either
        if recovery is None:
            return cannot("recovery_until")
        if now < recovery:
            return {"state": PENDING,
                    "sentence": f"The next session ({session}) has completed and a run can still publish it until "
                                f"{block['recovery_until']}. This record does not carry the service's schedule, so "
                                "no slot is named. Fetch the file again before relying on it."}
    else:
        if now < primary:
            return {"state": NOT_DUE,
                    "sentence": f"The next session ({session}) has completed; its evening run is not due until "
                                f"{block['primary_slot_at']}. Fetch the file again after that."}
        if now < retry:
            return {"state": PENDING,
                    "sentence": f"The first scheduled slot for {session} ({block['primary_slot_at']}) has passed; "
                                f"the retry slot is {block['retry_slot_at']}. Fetch the file again before relying "
                                "on it."}
        if recovery is None:
            return cannot("recovery_until")
        if now < recovery:
            return {"state": LATE,
                    "sentence": f"Both scheduled slots for {session} have passed; a delayed run can still publish "
                                f"it until {block['recovery_until']}. Fetch the file again before relying on it."}
    return {"state": MISSING,
            "sentence": f"The recovery limit for {session} ({_say(block.get('recovery_until'))}) has passed. If this "
                        "is still the newest file the site serves, that session was not published and will not be, "
                        "and every ticket in this file is expired."}


def morning_window(record) -> dict:
    """The session the published plans are for, its entry window and the
    instant the morning collection starts, off ``run.timing``. The collection
    start is ``PREOPEN_MINUTES`` before the window opens."""
    timing = _dict(_dict(_dict(record).get("run")).get("timing"))
    opens, cutoff = _instant(timing.get("opens_at")), _instant(timing.get("cutoff_at"))
    out = {"applicable_session": timing.get("applicable_session") if _day(timing.get("applicable_session")) else None,
           "window_opens_at": timing.get("opens_at") if opens else None,
           "window_cutoff_at": timing.get("cutoff_at") if cutoff else None,
           "prepare_by": timing.get("prepare_by") if _instant(timing.get("prepare_by")) else None,
           "session_closes_at": timing.get("closes_at") if _instant(timing.get("closes_at")) else None,
           "timezone": timing.get("timezone") if isinstance(timing.get("timezone"), str) else None,
           "collection_starts_at": (opens - timedelta(minutes=PREOPEN_MINUTES)).isoformat() if opens else None,
           "collection_starts_minutes_before_open": PREOPEN_MINUTES,
           "unknown": None}
    if not timing:
        out["unknown"] = "this record carries no entry-window timing (run.timing)"
    elif opens is None or cutoff is None or out["applicable_session"] is None:
        out["unknown"] = "the record's entry-window timing is not complete"
    return out
