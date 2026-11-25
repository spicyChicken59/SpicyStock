"""tools/service_watch.py -- a watch on the service, not a reading of it.

GitHub starts this repository's scheduled runs hours after their slots (the
13 October 2026 schedule reading, and every night since), and until now
nothing said so when a night had not arrived: a publication that never came
looked exactly like one that was late. This asks five questions of the files
on main, a clock and (with a token) GitHub's own list of the workflows' runs,
and answers each in one word and one sentence:

``evening``
    Has the session after the one ``docs/data.json`` covers been published?
    The answer is ``src/freshness.py``'s -- the five steps the page's own
    status chip walks, read off the record's calendar and delivery policy --
    and the watch adds one judgement to it: a publication still absent from
    the earlier of ``ALERT_WITHIN_HOURS`` before its recovery limit (the next
    session's open) and ``NOT_PUBLISHED_AFTER_PRIMARY_HOURS`` after its primary
    slot is ``not_published`` -- on an ordinary night that is 3:30 AM ET, over
    a weekend Saturday morning -- and from ``EVENING_PUBLISHED_BY_ET`` when the
    run listing shows the on-time dispatcher started it; one absent past the
    limit is ``missing``; a record more than one completed session behind is
    judged by its newest session.

``start``
    Did the evening run that wrote the record start within
    ``LATE_START_MINUTES`` of its primary slot? Read off the record's own
    ``run.delivery.after_primary_minutes``; a start an hour late was not the
    on-time dispatcher's (``tools/dispatch_schedule.py``, 6:20 PM ET).

``morning``
    From ``MORNING_ALERT_CT`` (8:25 AM Chicago, five minutes before the 8:30
    open) on the applicable session: did a morning check for THIS record land
    inside its collection window, and is ``orders-morning.json`` ``checked``
    for this exact ``orders.json``? The same answer stands under the same key
    through ``MORNING_DUE_CT`` (8:45, the go-live gate's line), so nothing more
    is mailed for it.

``handoff``
    Do ``orders.json``, ``positions-template.json`` and ``orders-morning.json``
    pass ``src/orders.check()`` against this record? Each problem is said in a
    fixed phrase, never with a path or an exception's text.

``scheduler``
    Did the scheduler run? Read off the Actions run listing of ``evening.yml``,
    ``morning.yml`` and this watch's own ``service-watch.yml`` (``GitHub.runs()``,
    the workflow's read-only token): ``on_time`` (the on-time dispatcher's
    ``workflow_dispatch``, by its run name, inside its due window),
    ``started_late``, ``not_started``, ``failed`` or ``unknown``. The runs are tied
    to the files by ``run.run_id`` and the receipt's ``observation_run_id``. The
    watch reports a gap in its own previous slot after the fact. Without a token,
    or with a listing that cannot be read whole, every scheduler answer is
    ``unknown`` and the file answers still stand: ``unknown`` is never an alert.

Every alert has a key (``family:word:scope``). One about a session carries the
session; a standing one about the scheduler carries none; an unreadable record
carries the SHA-256 of its bytes (or ``absent``). The judgement word is part of
the key, so a change of state mails once. With ``--ledger FILE`` the watch keeps
the keys it has mailed and when, and mails a key it holds again only after
``REPEAT_DAYS``; it holds keys and instants only, is written only after a mail
was accepted, and reads as empty -- so every alert mails again -- when it is
absent, corrupt, of another version or dated after the clock.

It reads files and decides nothing about them. It calls no provider, and it
mails only with ``--mail``, through the evening's own transport
(``report.deliver``). A watch that runs on GitHub's scheduler is itself late by
hours, so the same answers are printed for anything else with a clock:
``python tools/service_watch.py --docs docs``. Nothing outside GitHub watches
this watch: the on-time dispatcher on Railway, once deployed, is that clock.

Exit codes: 0 nothing to flag, 1 an alert, 2 the record could not answer. With
``--mail``, 1 only when an alert was mailed now or its mail failed: a run whose
every alert was dropped as a repeat exits 0.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import urllib.error
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import freshness, orders  # noqa: E402  (both standard library only at import)
from tools import dispatch_schedule as ds  # noqa: E402  (the dispatcher's slots and its GitHub client)

VERSION = 2
DATA_FILE = "data.json"
MORNING_FILE = "morning.json"
ORDERS_FILE = orders.FILE
ORDERS_MORNING_FILE = orders.MORNING_FILE
#: The files this reads are the publication's own; a larger one is not read at all.
MAX_RECORD_BYTES = 48 * 1024 * 1024        # reader.MAX_PUBLICATION_BYTES; tests hold the two equal
MAX_MORNING_BYTES = 512 * 1024             # morning.MAX_OBSERVATION_BYTES; tests hold the two equal

#: A publication still absent this many hours before its recovery limit is flagged.
#: Read off the landing commits on 19 November 2026: every first publication from
#: 19 October to 18 November landed more than nine hours before the next open, so
#: no night of that month would have been flagged.
ALERT_WITHIN_HOURS = 6
#: ... or this many hours after its primary slot, whichever is earlier: on an
#: ordinary night the limit rule is earlier (3:30 AM ET against 4:16 AM ET); over a
#: weekend or a holiday this one is, so a missed Friday is said on Saturday morning
#: and not six hours before Monday's open.
NOT_PUBLISHED_AFTER_PRIMARY_HOURS = 10
#: When the run listing shows the on-time dispatcher started the session's evening,
#: a publication still absent at this New York time is flagged as well: an on-time
#: start publishes within minutes of 6:20 PM ET, and the dispatcher's last evening
#: start is at 9:20 PM ET. The 9:50 PM ET watch slot mails it.
EVENING_PUBLISHED_BY_ET = "21:45"
#: No evening run listed for a completed session by this New York time is
#: ``not_started``: the dispatcher's first evening slot plus its due window
#: (tools/dispatch_schedule.SLOTS, DUE_MINUTES; tests hold the two equal).
EVENING_STARTED_BY_ET = "18:50"
#: A missing publication is flagged for this long after its limit, then left: the
#: next evening's run replaces the record, and a watch that repeated itself until
#: then would say nothing new.
MISSING_ALERT_HOURS = 12
#: The same bound for a morning check that did not land.
MORNING_ALERT_HOURS = 12
#: A morning check is judged from this local time on the applicable session: the
#: dispatcher starts it at 8:20 AM CT (tools/dispatch_schedule.SLOTS), a run lands
#: in about 90 seconds, and the dispatcher starts this watch at this minute, five
#: minutes before the 8:30 AM CT open.
MORNING_ALERT_CT = "08:25"
#: The go-live gate's own line for a morning check (go_live.MORNING_DUE_CT, an
#: archived rule; tests hold the two equal). The answer judged from
#: MORNING_ALERT_CT stands under the same key through it, so it mails nothing more.
MORNING_DUE_CT = "08:45"
CHICAGO = ZoneInfo("America/Chicago")
#: An evening run that started more than this many minutes after its primary
#: slot (6:16 PM ET) was not started by the dispatcher, whose first evening slot
#: is 6:20 PM ET; GitHub's own cron created every such run of 2 to 18 November
#: 2026 3.56 to 7.99 hours late.
LATE_START_MINUTES = 60
#: Flagged for this long after the late run started: the 6:00 AM CT watch the
#: next morning is about twelve hours after a 6:20 PM ET start.
LATE_START_ALERT_HOURS = 14
#: With a ledger, a key already mailed is mailed again only after this many days:
#: a standing condition is repeated weekly while it stands.
REPEAT_DAYS = 7
LEDGER_VERSION = 1
#: A ledger larger than this is not read: it is not one this watch wrote.
MAX_LEDGER_BYTES = 64 * 1024
#: How far back the watch looks for its own previous slot: past the longest run of
#: days with no XNYS session.
WATCH_LOOKBACK_DAYS = 10

# evening judgements
OK, NOT_PUBLISHED, MISSING, UNKNOWN = "ok", "not_published", "missing", "unknown"
# morning judgements
NOT_DUE, LANDED, NOT_LANDED, NOT_CHECKED = "not_due", "landed", "not_landed", "not_checked"
# start and scheduler judgements
ON_TIME, STARTED_LATE, NOT_STARTED, FAILED = "on_time", "started_late", "not_started", "failed"
# handoff judgements
BOUND, UNBOUND = "bound", "unbound"

EXIT_OK, EXIT_ALERT, EXIT_UNKNOWN = 0, 1, 2

EVENING_WORKFLOW, MORNING_WORKFLOW, WATCH_WORKFLOW = "evening.yml", "morning.yml", "service-watch.yml"
#: The run names the three workflows give themselves (their ``run-name:``; tests hold them to the files).
DISPATCH_EVENT = "workflow_dispatch"
EVENING_DISPATCH_TITLE = "Evening dispatch (only if unpublished)"
EVENING_REHEARSAL_TITLE = "Evening rehearsal"
EVENING_BACKFILL_PREFIX = "Evening backfill "
MORNING_DISPATCH_TITLE = "Morning publication"
MORNING_REHEARSAL_TITLE = "Morning rehearsal"
WATCH_DISPATCH_TITLE = "Service watch (manual)"
#: A completed run with one of these conclusions did not do its work.
FAILED_CONCLUSIONS = ("failure", "cancelled", "timed_out", "startup_failure")
MAIN = "main"
NO_TOKEN = f"no {ds.TOKEN_ENV} was given, so the Actions run listing was not read"

#: An alert's key: ``family:word:scope``. A scheduler key carries no session.
KEY_PATTERN = re.compile(r"(?:(?:evening|morning|handoff):[a-z_]+:(?:\d{4}-\d{2}-\d{2}|[0-9a-f]{64})"
                         r"|scheduler:(?:evening|morning|watch):[a-z_]+"
                         r"|record:unreadable:(?:[0-9a-f]{64}|absent))")

DISPATCH_HINT = ("Start it by hand: GitHub, Actions, Evening scan, Run workflow, branch main, with only_if_unpublished "
                 "ticked. From the session's primary slot (6:16 PM ET) on, it publishes the newest completed session "
                 "if it is still unpublished, and it does nothing otherwise.")
MISSING_HINT = ("The scheduled slots and a dispatch with only_if_unpublished ticked will not publish that session now. "
                "A plain dispatch of the Evening scan with the session box filled still can, and the tickets it writes "
                "would be for an entry window that may have ended. Read the evening workflow's runs for that evening, "
                "and treat every ticket in the record on the site as expired.")
BEHIND_HINT = ("More than one session has completed since the record on main. Read the Evening scan's runs: this is "
               "an outage, not a late night.")
RUN_FAILED_HINT = ("Read the failed run's log (GitHub, Actions, Evening scan, the run named above) before starting it "
                   "again. " + DISPATCH_HINT)
UNREADABLE_SUBJECT = "SpicyStock watch: the record on main could not be read"
#: What a morning receipt's status must be for the check to count as one that ran for the record's tickets.
#: ``provider_unavailable`` and ``inapplicable`` (``src/morning.STATUSES``) quoted nothing and say so themselves.
RAN_STATUSES = ("observed", "partial", "no_tickets")
RECENT = "recent"
MORNING_HINT = ("The morning check is started from outside GitHub's scheduler, by the on-time dispatcher "
                "(tools/dispatch_schedule.py) at 8:20 AM CT. Read its log for that morning, and morning.yml's runs.")
NOT_CHECKED_HINT = ("The morning run writes orders-morning.json after its receipt lands (python -m tools.publish_morning "
                    "orders). Until it is checked for this orders.json an execution agent cancels every ticket: read "
                    "morning.yml's run for that morning.")
HANDOFF_HINT = ("The evening run writes orders.json, positions-template.json and orders-morning.json after the brief "
                "(pipeline.publish_orders()), and removes them when it cannot write them. Read that night's Evening "
                "scan log. Until a bound orders.json and orders-morning.json are on main an execution agent enters "
                "nothing.")
SCHEDULER_HINT = ("The on-time dispatcher (tools/dispatch_schedule.py, docs/operations/external-scheduler.md) starts the "
                  "evening at 6:20 PM ET, the morning check at 8:20 AM CT and this watch at its slots, once it is "
                  "deployed on Railway; until then, or while it is down, GitHub's own crons start them hours late. "
                  f"Read the dispatcher's log for that day. This is mailed once, and again after {REPEAT_DAYS} days "
                  "while it stands.")
START_HINT = SCHEDULER_HINT
LATE_ITSELF = ("This watch may itself have been started late by GitHub's scheduler, which starts scheduled runs hours "
               "late: read the clock it names.")
SUBJECTS = {
    ("evening", NOT_PUBLISHED): "SpicyStock watch: {scope} is not published",
    ("evening", MISSING): "SpicyStock watch: {scope} was not published before the next open",
    ("evening", NOT_STARTED): "SpicyStock watch: the {scope} evening run has not started",
    ("evening", FAILED): "SpicyStock watch: the {scope} evening run failed",
    ("morning", NOT_LANDED): "SpicyStock watch: no morning check landed for {scope}",
    ("morning", NOT_CHECKED): "SpicyStock watch: orders-morning.json is not checked for {scope}",
    ("handoff", UNBOUND): "SpicyStock watch: the {scope} handoff files do not pass their check",
    ("scheduler:evening", STARTED_LATE): "SpicyStock watch: the evening was not started by the on-time dispatcher",
    ("scheduler:morning", STARTED_LATE): "SpicyStock watch: the morning check was not started by the on-time dispatcher",
    ("scheduler:watch", NOT_STARTED): "SpicyStock watch: the watch was not started at its slot",
}
#: ``orders.check()``'s own sentences that name no path and quote nothing; any other is said by the file it names.
HANDOFF_PHRASES = (
    "orders.json is not bound to data.json",
    "orders.json written under an earlier version is not paper",
    "orders.json's live_ready is not the committed record's gate",
    "orders.json is live while the committed protocol record is not passed",
    f"{orders.MORNING_FILE} is missing beside orders.json: every ticket is cancelled until it is written",
    f"{orders.POSITIONS_FILE} is not bound to orders.json",
    f"{orders.MORNING_FILE} is not bound to orders.json",
    f"{orders.POSITIONS_FILE} does not carry orders.json's mode",
    f"{orders.MORNING_FILE} does not carry orders.json's mode",
)
HANDOFF_MISSING = "orders.json is missing"
HANDOFF_UNCHECKABLE = "the handoff files could not be checked"


class Unreadable(ValueError):
    """A file the watch needs is absent, too large or not the JSON object it should be."""


def _instant(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None and parsed.utcoffset() is not None else None


def _dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _hours(delta: timedelta) -> float:
    return round(delta.total_seconds() / 3600, 2)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def read_bytes(path: Path, maximum: int) -> bytes:
    try:
        if path.is_symlink() or not path.is_file():
            raise Unreadable(f"{path.name} is not a regular file")
        size = path.stat().st_size
        if size > maximum:
            raise Unreadable(f"{path.name} is {size} bytes, over the {maximum} this watch reads")
        return path.read_bytes()
    except OSError as exc:
        raise Unreadable(f"{path.name} could not be read ({type(exc).__name__})") from exc


def _optional(path: Path, maximum: int) -> bytes | None:
    """A companion file's bytes, or None when it is absent or cannot be read."""
    try:
        return read_bytes(path, maximum)
    except Unreadable:
        return None


def decode(raw: bytes, name: str) -> dict:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise Unreadable(f"{name} is not JSON ({type(exc).__name__})") from exc
    if not isinstance(value, dict):
        raise Unreadable(f"{name} is not a JSON object")
    return value


def record_key(path: Path) -> str:
    """The scope of an unreadable record's key: the SHA-256 of its bytes, or ``absent``."""
    try:
        if path.is_symlink() or not path.is_file():
            return "absent"
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return "absent"


def ticket_count(record: dict) -> int | None:
    """How many model tickets the record published, off its own funnel block
    (``src/funnel.py``); None when the record carries no readable count."""
    funnel = record.get("funnel")
    if not isinstance(funnel, dict):
        return None
    total = 0
    for family in ("reaction", "anticipation"):
        block = funnel.get(family)
        stages = block.get("stages") if isinstance(block, dict) else None
        count = stages.get("ticket") if isinstance(stages, dict) else None
        if type(count) is not int or count < 0:
            return None
        total += count
    return total


# ------------------------------------------------------ the record's clock ---
def _sessions(record: dict) -> list[tuple[str, datetime, datetime]] | None:
    """(session, completion, open) for every row of ``run.calendar.schedule``, in
    order; None when a row cannot be read whole."""
    schedule = _dict(_dict(_dict(record.get("run")).get("calendar")).get("schedule"))
    rows = schedule.get("sessions")
    if not isinstance(rows, list):
        return None
    out = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("session"), str):
            return None
        done, opens = _instant(row.get("completion_at")), _instant(row.get("opens_at"))
        if done is None or opens is None:
            return None
        out.append((row["session"], done, opens))
    return sorted(out)


def _hhmm(value) -> time | None:
    if not isinstance(value, str) or len(value) != 5 or value[2] != ":":
        return None
    try:
        return time(int(value[:2]), int(value[3:]))
    except ValueError:
        return None


def _local(record: dict, session: str | None, clock: str | None = None) -> datetime | None:
    """``clock`` (HH:MM; the policy's primary slot when None) on ``session``, in the
    zone of the record's own delivery policy; None when the record cannot give it."""
    policy = _dict(_dict(_dict(record.get("run")).get("delivery")).get("policy"))
    try:
        zone = ZoneInfo(policy["timezone"]) if isinstance(policy.get("timezone"), str) else None
        day = date.fromisoformat(session) if isinstance(session, str) else None
    except (KeyError, ValueError, OSError):
        return None
    wall = _hhmm(policy.get("primary_et") if clock is None else clock)
    if zone is None or day is None or wall is None:
        return None
    return datetime.combine(day, wall, tzinfo=zone)


def not_published_from(record: dict, session: str | None, limit: datetime | None) -> datetime | None:
    """The first instant an unpublished ``session`` is ``not_published``: the earlier
    of ``ALERT_WITHIN_HOURS`` before its limit and ``NOT_PUBLISHED_AFTER_PRIMARY_HOURS``
    after its primary slot (elapsed hours, in UTC)."""
    candidates = []
    if limit is not None:
        candidates.append(limit.astimezone(timezone.utc) - timedelta(hours=ALERT_WITHIN_HOURS))
    primary = _local(record, session)
    if primary is not None:
        candidates.append(primary.astimezone(timezone.utc) + timedelta(hours=NOT_PUBLISHED_AFTER_PRIMARY_HOURS))
    return min(candidates) if candidates else None


def sessions_behind(record: dict, covers_through, now: datetime) -> dict | None:
    """The sessions after the one the record covers that have completed by ``now``, read off the record's own
    calendar (``run.calendar.schedule.sessions``, each with its ``completion_at``): how many, the newest of them,
    and that one's own recovery limit (the open of the session after it). None when the record does not carry a
    schedule this can be read from."""
    rows = _sessions(record)
    if rows is None or not isinstance(covers_through, str):
        return None
    later = [row for row in rows if row[0] > covers_through]
    completed = [index for index, (_, done, _) in enumerate(later) if done <= now]
    if not completed:
        return {"count": 0, "newest": None, "newest_limit": None}
    newest = completed[-1]
    limit = later[newest + 1][2] if newest + 1 < len(later) else None
    return {"count": len(completed), "newest": later[newest][0],
            "newest_limit": limit.isoformat() if limit is not None else None}


def evening_target(record: dict, now: datetime) -> dict | None:
    """The unpublished session whose evening is current at ``now``: the session after the one the record
    covers whose primary slot has passed and whose limit (the next session's open) has not. None when there is
    none, or when the record cannot give the instants."""
    covered = freshness.covers_through(record)
    rows = _sessions(record)
    if rows is None or covered is None:
        return None
    later = [row for row in rows if row[0] > covered]
    for index, (session, done, _) in enumerate(later):
        primary = _local(record, session)
        limit = later[index + 1][2] if index + 1 < len(later) else None
        if primary is not None and limit is not None and primary <= now < limit:
            first = dispatcher_slot(EVENING_WORKFLOW, session)
            return {"session": session, "completion_at": done.isoformat(), "primary_slot_at": primary.isoformat(),
                    "limit_at": limit.isoformat(), "first_slot_at": _iso(first),
                    "started_by_at": _iso(_local(record, session, EVENING_STARTED_BY_ET))}
    return None


def dispatcher_slot(workflow: str, session: str | None, index: int = 0) -> datetime | None:
    """The on-time dispatcher's ``index``-th slot for ``workflow`` on ``session``'s date (tools/dispatch_schedule)."""
    try:
        day = date.fromisoformat(session) if isinstance(session, str) else None
    except ValueError:
        return None
    for name, _, zone, times in ds.SLOTS:
        if name == workflow and day is not None:
            return datetime.combine(day, time.fromisoformat(times[index]), tzinfo=zone)
    return None


# ----------------------------------------------------------------- evening ---
def evening(record: dict, now: datetime, on_time_start: bool = False) -> dict:
    """The freshness answer for the session after the one the record covers,
    and whether its absence is worth an alert. ``on_time_start`` says the run
    listing shows the on-time dispatcher started that session's evening."""
    expected = freshness.expected(record)
    answer = freshness.state(expected, now)
    session = expected.get("next_session")
    limit = _instant(expected.get("recovery_until"))
    hours = _hours(limit - now) if limit is not None else None
    behind = sessions_behind(record, expected.get("covers_through"), now)
    deadline = not_published_from(record, session, limit) if session else None
    published_by = _local(record, session, EVENING_PUBLISHED_BY_ET) if session and on_time_start else None
    out = {"covers_through": expected.get("covers_through"), "next_session": session,
           "state": answer["state"], "state_sentence": answer["sentence"],
           "recovery_until": expected.get("recovery_until"), "hours_to_limit": hours,
           "not_published_from": _iso(deadline), "published_by": _iso(published_by),
           "sessions_behind": behind,
           "judgement": OK, "sentence": answer["sentence"], "alert": False, "action": None, "key": None}
    if answer["state"] == freshness.UNKNOWN:
        out["judgement"] = UNKNOWN
    elif answer["state"] == freshness.MISSING:
        out["judgement"] = MISSING
        out["sentence"] = (f"The {session} session was not published before the session after it opened "
                           f"({expected.get('recovery_until')}), and the service will not publish it now. The record "
                           f"on main still covers {out['covers_through']}.")
        # the limit is known here: state() answers missing only past it
        if limit is not None and now - limit < timedelta(hours=MISSING_ALERT_HOURS):
            out["alert"], out["key"] = True, f"evening:{MISSING}:{session}"
        out["action"] = MISSING_HINT
        if behind is not None and behind["count"] > 1:
            # A second night in a row never gets its own "missing": the record still names the first one. The
            # newest completed session is judged by the first night's own rule, under its own key.
            out["sentence"] += (f" {behind['count']} sessions have completed since {out['covers_through']} and none "
                                f"of them is published; the newest is {behind['newest']}.")
            newest, newest_limit = behind["newest"], _instant(behind["newest_limit"])
            newest_deadline = not_published_from(record, newest, newest_limit)
            if newest_limit is not None and newest_deadline is not None and newest_deadline <= now < newest_limit:
                out["alert"], out["key"] = True, f"evening:{NOT_PUBLISHED}:{newest}"
            elif newest_limit is not None and timedelta(0) <= now - newest_limit < timedelta(hours=MISSING_ALERT_HOURS):
                out["alert"], out["key"] = True, f"evening:{MISSING}:{newest}"
            # MISSING_HINT is about the first missed session; the newest can still be published until its limit
            if newest_limit is not None and now < newest_limit:
                out["action"] = (f"{BEHIND_HINT} The newest, {newest}, can still be published: "
                                 f"{DISPATCH_HINT} The first, {session}: {MISSING_HINT}")
            else:
                out["action"] = f"{BEHIND_HINT} The first, {session}: {MISSING_HINT}"
    elif answer["state"] in (freshness.PENDING, freshness.LATE) and (
            (deadline is not None and now >= deadline) or (published_by is not None and now >= published_by)):
        # the deadline decides, not the state word: a record with no readable delivery policy stays `pending`
        # until its limit, and is as unpublished as a late one
        out["judgement"] = NOT_PUBLISHED
        slots = ("Both scheduled slots have passed" if answer["state"] == freshness.LATE
                 else "It completed and its publication is still pending")
        out["sentence"] = (f"The {session} session is not published yet. {slots} and the "
                           f"session after it opens at {expected.get('recovery_until')}, {hours:g} hours after this "
                           "watch's clock; after that the scheduled service will not publish it.")
        if published_by is not None and now >= published_by and not (deadline is not None and now >= deadline):
            out["sentence"] += (f" The on-time dispatcher started its evening, and it was still not on main at "
                                f"{published_by.isoformat()}.")
        out["alert"], out["key"] = True, f"evening:{NOT_PUBLISHED}:{session}"
        out["action"] = DISPATCH_HINT
    return out


# ------------------------------------------------------------------- start ---
def start(record: dict, now: datetime) -> dict:
    """Whether the evening run that wrote the record started within
    LATE_START_MINUTES of its primary slot, off the record's own delivery block."""
    run = _dict(record.get("run"))
    delivery = _dict(run.get("delivery"))
    minutes, slot = delivery.get("after_primary_minutes"), _instant(delivery.get("primary_slot_at"))
    out = {"session": delivery.get("session"), "primary_slot_at": delivery.get("primary_slot_at"),
           "after_primary_minutes": None, "judgement": UNKNOWN, "sentence": None, "alert": False, "action": None,
           "key": None}
    if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or slot is None:
        out["sentence"] = "The record carries no delivery block to say when its run started."
        return out
    out["after_primary_minutes"] = minutes
    if minutes <= LATE_START_MINUTES:
        out["judgement"] = ON_TIME
        out["sentence"] = (f"The {out['session']} evening run started {minutes:g} minutes after its primary slot "
                           f"({delivery['primary_slot_at']}).")
        return out
    out["judgement"] = STARTED_LATE
    out["sentence"] = (f"The {out['session']} evening run started {minutes:g} minutes after its primary slot "
                       f"({delivery['primary_slot_at']}), more than {LATE_START_MINUTES} minutes late.")
    out["alert"] = now - (slot + timedelta(minutes=minutes)) < timedelta(hours=LATE_START_ALERT_HOURS)
    out["action"] = START_HINT if out["alert"] else None
    out["key"] = f"scheduler:evening:{STARTED_LATE}" if out["alert"] else None
    return out


# ----------------------------------------------------------------- morning ---
def _morning_at(session: str | None, clock: str) -> datetime | None:
    try:
        return datetime.combine(date.fromisoformat(session), time.fromisoformat(clock), tzinfo=CHICAGO)
    except (TypeError, ValueError):
        return None


def morning_due(session: str | None) -> datetime | None:
    """MORNING_DUE_CT (the go-live gate's line) on the applicable session, in Chicago."""
    return _morning_at(session, MORNING_DUE_CT)


def morning_alert(session: str | None) -> datetime | None:
    """MORNING_ALERT_CT on the applicable session, in Chicago: the morning is judged from here."""
    return _morning_at(session, MORNING_ALERT_CT)


def _measured(record: dict):
    return _dict(record.get("run")).get("session")


def orders_morning_problem(record_raw: bytes, orders_raw: bytes | None, orders_morning_raw: bytes | None) -> str | None:
    """None when ``orders-morning.json`` is ``checked`` for the exact ``orders.json`` bound to this record;
    otherwise what is not, in a fixed phrase."""
    if orders_raw is None:
        return "there is no orders.json beside the record"
    try:
        source = _dict(json.loads(orders_raw).get("source"))
    except (ValueError, UnicodeDecodeError, RecursionError, AttributeError):
        return "orders.json cannot be read"
    if source.get("data_sha256") != hashlib.sha256(record_raw).hexdigest():
        return "orders.json is not bound to this record"
    if orders_morning_raw is None:
        return "there is no orders-morning.json beside orders.json"
    if orders.earlier_version(orders_morning_raw) is not None:
        return "orders-morning.json was written under an earlier version of this code"
    try:
        value = orders.validate(orders_morning_raw, "orders_morning")
    except (ValueError, RecursionError):
        return "orders-morning.json does not meet its schema or hold its hash"
    if value["orders_sha256"] != hashlib.sha256(orders_raw).hexdigest():
        return "orders-morning.json is bound to another orders.json"
    if value["status"] != orders.CHECKED:
        # the schema allows pending and no_check besides checked: a fixed word
        return f"orders-morning.json says {value['status']}: no morning check was applied to these orders"
    return None


def morning(record: dict, record_raw: bytes, receipt: dict | None, receipt_problem: str | None, now: datetime, *,
            orders_raw: bytes | None, orders_morning_raw: bytes | None) -> dict:
    """Whether a morning check for this record landed inside its collection
    window and orders-morning.json is checked for this orders.json, from
    MORNING_ALERT_CT on the applicable session."""
    window = freshness.morning_window(record)
    session = window.get("applicable_session")
    tickets = ticket_count(record)
    out = {"applicable_session": session, "collection_starts_at": window.get("collection_starts_at"),
           "window_cutoff_at": window.get("window_cutoff_at"), "tickets": tickets,
           "judgement": UNKNOWN, "sentence": None, "alert": False, "action": None, "receipt": None, "key": None,
           "orders_morning": None}
    start_at, cutoff = _instant(window.get("collection_starts_at")), _instant(window.get("window_cutoff_at"))
    due, alert_at = morning_due(session), morning_alert(session)
    if window.get("unknown") or start_at is None or cutoff is None or due is None or alert_at is None:
        out["sentence"] = f"The morning check cannot be judged: {window.get('unknown') or 'the record gives no entry window'}."
        return out
    out["due_at"], out["alert_at"] = due.isoformat(), alert_at.isoformat()
    if now < alert_at:
        out["judgement"] = NOT_DUE
        out["sentence"] = (f"A morning check for {session} is started at 8:20 AM CT and judged from "
                           f"{alert_at.isoformat()}; this watch's clock is before that.")
        return out
    judged_by = due if now >= due else alert_at
    wanted = hashlib.sha256(record_raw).hexdigest()
    problem = receipt_problem
    generated = None
    if receipt is not None:
        publication = receipt.get("publication")
        bound = publication.get("data_sha256") if isinstance(publication, dict) else None
        generated = _instant(receipt.get("generated_at"))
        status = receipt.get("status") if isinstance(receipt.get("status"), str) else None
        rows = [r for r in receipt.get("rows", []) if isinstance(r, dict)] if isinstance(receipt.get("rows"), list) else []
        recent = sum(1 for r in rows if any(isinstance(r.get(side), dict) and r[side].get("status") == RECENT
                                            for side in ("trade", "quote")))
        opens = _instant(window.get("window_opens_at"))
        same_session = (isinstance(publication, dict)
                        and publication.get("measured_session") == _measured(record)
                        and publication.get("applicable_session") == session)
        out["receipt"] = {"generated_at": receipt.get("generated_at") if generated else None,
                          "status": status, "bound_to_this_record": bound == wanted,
                          "same_session_other_publication": bound != wanted and bool(same_session),
                          "before_window_opened": bool(generated and opens and generated < opens),
                          "ticket_rows": len(rows), "rows_with_recent_price": recent,
                          "observation_run_id": receipt.get("observation_run_id")
                          if isinstance(receipt.get("observation_run_id"), (str, int))
                          and not isinstance(receipt.get("observation_run_id"), bool) else None}
        if bound != wanted and same_session and generated is not None and start_at <= generated <= cutoff \
                and receipt.get("dry_run") is False and status in RAN_STATUSES:
            # the session was published again after the morning: the check that landed was for the earlier
            # publication of the same session, and saying none landed would be false. Its orders-morning.json
            # was the earlier orders' too, so it is not asked of this one.
            out["judgement"] = LANDED
            out["sentence"] = (f"A morning check for {session} landed inside its collection window, generated "
                               f"{receipt['generated_at']} (status {status}), for an earlier publication of this "
                               "session: the record on main was published again after it.")
            return out
        if bound != wanted:
            problem = "the morning file on disk is bound to another publication"
        elif generated is None:
            problem = "the morning file names no generation instant"
        elif generated < start_at:
            problem = f"the morning file was generated at {receipt['generated_at']}, before the collection window opened"
        elif generated > cutoff:
            problem = f"the morning file was generated at {receipt['generated_at']}, after the entry window closed"
        elif receipt.get("dry_run") is not False:
            problem = "the morning file is a rehearsal"
        elif status not in RAN_STATUSES:
            problem = f"the morning file says status {status!r}: it quoted nothing"
    counted = ("the record does not say how many tickets it published" if tickets is None
               else f"the record published {tickets} ticket{'' if tickets == 1 else 's'}")
    # every session's morning check is the service's, ticket or not: flagged for MORNING_ALERT_HOURS from alert_at
    flagged = now - alert_at < timedelta(hours=MORNING_ALERT_HOURS)
    if problem is None:
        seen = out["receipt"]
        landed = (f"A morning check for {session} landed inside its collection window, generated "
                  f"{receipt['generated_at']} (status {seen['status']})")
        if tickets:
            landed += (f"; it was generated {'before' if seen['before_window_opened'] else 'after'} the entry "
                       f"window opened, and {seen['rows_with_recent_price']} of its {seen['ticket_rows']} ticket "
                       f"row{'' if seen['ticket_rows'] == 1 else 's'} carried a recent price")
        checked = orders_morning_problem(record_raw, orders_raw, orders_morning_raw)
        out["orders_morning"] = checked or orders.CHECKED
        if checked is None:
            out["judgement"] = LANDED
            out["sentence"] = landed + "; orders-morning.json is checked for this orders.json."
            return out
        out["judgement"] = NOT_CHECKED
        out["sentence"] = f"{landed}, but by {judged_by.isoformat()} {checked}; {counted}."
        out["alert"] = flagged
        out["action"] = NOT_CHECKED_HINT if flagged else None
        out["key"] = f"morning:{NOT_CHECKED}:{session}" if flagged else None
        return out
    out["judgement"] = NOT_LANDED
    out["sentence"] = (f"No morning check for {session} landed by {judged_by.isoformat()} inside its collection window: "
                       f"{problem}; {counted}.")
    out["alert"] = flagged
    out["action"] = MORNING_HINT if flagged else None
    out["key"] = f"morning:{NOT_LANDED}:{session}" if flagged else None
    return out


# ----------------------------------------------------------------- handoff ---
def handoff_phrase(problem: str) -> str:
    """One of ``orders.check()``'s problems as a fixed phrase: its own sentence when it names no path and
    quotes nothing, else the file it is about."""
    if problem in HANDOFF_PHRASES:
        return problem
    for name in (orders.FILE, orders.POSITIONS_FILE, orders.MORNING_FILE):
        if problem.startswith(name + ":") or problem.startswith(name + " "):
            return f"{name} cannot be read or does not meet its schema"
    return HANDOFF_UNCHECKABLE


def handoff(docs: Path, record: dict, record_raw: bytes) -> dict:
    """Whether the handoff files beside the record pass ``src/orders.check()``."""
    scope = freshness.covers_through(record) or hashlib.sha256(record_raw).hexdigest()
    target = docs / orders.FILE
    if target.is_symlink() or not target.is_file():
        problems = [HANDOFF_MISSING]
    else:
        try:
            problems = [handoff_phrase(str(problem)) for problem in orders.check(docs)]
        except Exception:                          # anything check() raises is a check that could not be made
            problems = [HANDOFF_UNCHECKABLE]
    problems = list(dict.fromkeys(problems))
    out = {"session": scope, "problems": problems, "judgement": BOUND, "alert": False, "action": None, "key": None}
    if not problems:
        out["sentence"] = ("orders.json, positions-template.json and orders-morning.json are bound to this record and "
                           "pass their check.")
        return out
    out["judgement"] = UNBOUND
    out["sentence"] = f"The handoff files beside the {scope} record do not pass their check: {'; '.join(problems)}."
    out["alert"], out["action"], out["key"] = True, HANDOFF_HINT, f"handoff:{UNBOUND}:{scope}"
    return out


# --------------------------------------------------------------- scheduler ---
def _created(run: dict) -> datetime | None:
    return ds._created(run.get("created_at"))


def _on_time(run: dict, title: str, slot: datetime | None) -> bool:
    """A ``workflow_dispatch`` by the dispatcher's run name created inside the slot's due window."""
    created = _created(run)
    return (slot is not None and created is not None and run.get("event") == DISPATCH_EVENT
            and run.get("display_title") == title
            and slot <= created < slot + timedelta(minutes=ds.DUE_MINUTES))


def _failed(runs: list[dict]) -> bool:
    return bool(runs) and all(r.get("status") == "completed" and r.get("conclusion") in FAILED_CONCLUSIONS
                              for r in runs)


def _summary(runs: list[dict]) -> list[dict]:
    return [{name: r.get(name) for name in ("id", "event", "display_title", "created_at", "status", "conclusion")}
            for r in runs]


def _named(runs: list[dict]) -> str:
    return "; ".join(f"run {r['id']} ({r.get('display_title')}, {r.get('event')}, created {r.get('created_at')}, "
                     f"{r.get('conclusion') or r.get('status')})" for r in runs)


def _block(workflow: str, **fields) -> dict:
    out = {"workflow": workflow, "judgement": UNKNOWN, "sentence": None, "alert": False, "action": None,
           "key": None, "runs": []}
    out.update(fields)
    return out


def evening_since(record: dict, now: datetime) -> datetime | None:
    """Where the evening listing starts: the completion of the current unpublished session, else of the
    session the record covers (the run that wrote it is listed after it)."""
    target = evening_target(record, now)
    if target is not None:
        return _instant(target["completion_at"])
    return _instant(_dict(_dict(record.get("run")).get("delivery")).get("completion_at"))


def judge_evening(record: dict, now: datetime, runs: list[dict] | None, reason: str | None) -> dict:
    """The evening's scheduler answer: about the current unpublished session's runs, or, when the record covers
    the newest session due, about the run that wrote it (``run.run_id``)."""
    target = evening_target(record, now)
    if target is None:
        return _judge_record_run(record, now, runs, reason)
    session = target["session"]
    first = _instant(target["first_slot_at"])
    started_by = _instant(target["started_by_at"])
    out = _block(EVENING_WORKFLOW, about="session", session=session, since=target["completion_at"],
                 first_slot_at=target["first_slot_at"], started_by_at=target["started_by_at"], on_time_run=None)
    if runs is None:
        out["sentence"] = f"The {session} evening's runs cannot be judged: {reason}."
        return out
    since = _instant(target["completion_at"])
    relevant = []
    for r in runs:
        created, title = _created(r), r.get("display_title") or ""
        if r.get("head_branch") != MAIN or created is None or created < since or title == EVENING_REHEARSAL_TITLE:
            continue
        if title.startswith(EVENING_BACKFILL_PREFIX) and title[len(EVENING_BACKFILL_PREFIX):] != session:
            continue                                   # a backfill of another session is that session's
        relevant.append(r)
    out["runs"] = _summary(relevant)
    on_time = [r for r in relevant if _on_time(r, EVENING_DISPATCH_TITLE, first)]
    window = f"{target['first_slot_at']} to {_iso(first + timedelta(minutes=ds.DUE_MINUTES)) if first else None}"
    if not relevant:
        if started_by is not None and now >= started_by:
            out.update(judgement=NOT_STARTED, alert=True, action=DISPATCH_HINT, key=f"evening:{NOT_STARTED}:{session}",
                       sentence=(f"No evening run for {session} is listed on main since it completed "
                                 f"({target['completion_at']}): the on-time dispatcher's first start is due at "
                                 f"{target['first_slot_at']}, and none had been created by {target['started_by_at']}."))
        else:
            out.update(judgement=NOT_DUE,
                       sentence=(f"No evening run for {session} is listed yet; the on-time dispatcher's first start "
                                 f"is due at {target['first_slot_at']}, and one is expected by "
                                 f"{target['started_by_at']}."))
        return out
    if _failed(relevant):
        out.update(judgement=FAILED, alert=True, action=RUN_FAILED_HINT, key=f"evening:{FAILED}:{session}",
                   sentence=f"Every evening run for {session} listed on main has ended without publishing it: "
                            f"{_named(relevant)}.")
        return out
    if on_time:
        out.update(judgement=ON_TIME, on_time_run=on_time[0]["id"],
                   sentence=f"The {session} evening was started on time by the dispatcher: {_named(on_time[:1])}.")
        return out
    out.update(judgement=STARTED_LATE, alert=True, action=SCHEDULER_HINT, key=f"scheduler:evening:{STARTED_LATE}",
               sentence=(f"The {session} evening was not started by the on-time dispatcher in its due window "
                         f"({window}): the runs listed are {_named(relevant)}."))
    return out


def _judge_record_run(record: dict, now: datetime, runs: list[dict] | None, reason: str | None) -> dict:
    run = _dict(record.get("run"))
    session, run_id = run.get("session"), run.get("run_id")
    since = _instant(_dict(run.get("delivery")).get("completion_at"))
    first = dispatcher_slot(EVENING_WORKFLOW, session)
    out = _block(EVENING_WORKFLOW, about="record_run", session=session, since=_iso(since), run_id=run_id,
                 first_slot_at=_iso(first), on_time_run=None)
    if not isinstance(session, str) or not isinstance(run_id, (str, int)) or isinstance(run_id, bool) \
            or since is None or first is None:
        out["sentence"] = "The record does not name the run that wrote it, so its start cannot be read off the listing."
        return out
    if runs is None:
        out["sentence"] = f"The start of the run that wrote the {session} record cannot be judged: {reason}."
        return out
    listed = [r for r in runs if str(r.get("id")) == str(run_id)]
    if not listed:
        out["sentence"] = f"The run that wrote the {session} record (run {run_id}) is not in the listing since {since.isoformat()}."
        return out
    out["runs"] = _summary(listed)
    window = f"{first.isoformat()} to {(first + timedelta(minutes=ds.DUE_MINUTES)).isoformat()}"
    if _on_time(listed[0], EVENING_DISPATCH_TITLE, first):
        out.update(judgement=ON_TIME, on_time_run=listed[0]["id"],
                   sentence=f"The run that wrote the {session} record was the on-time dispatcher's: {_named(listed)}.")
        return out
    created = _created(listed[0])
    alert = created is not None and now - created < timedelta(hours=LATE_START_ALERT_HOURS)
    out.update(judgement=STARTED_LATE, alert=alert, action=SCHEDULER_HINT if alert else None,
               key=f"scheduler:evening:{STARTED_LATE}" if alert else None,
               sentence=(f"The run that wrote the {session} record was not the on-time dispatcher's start in its due "
                         f"window ({window}): {_named(listed)}."))
    return out


def judge_morning(record: dict, receipt: dict | None, record_raw: bytes, now: datetime, runs: list[dict] | None,
                  reason: str | None) -> dict:
    """The morning check's scheduler answer on the record's applicable session, from MORNING_ALERT_CT."""
    window = freshness.morning_window(record)
    session = window.get("applicable_session")
    alert_at, collection = morning_alert(session), _instant(window.get("collection_starts_at"))
    slot = dispatcher_slot(MORNING_WORKFLOW, session)
    out = _block(MORNING_WORKFLOW, about="session", session=session, since=_iso(collection),
                 slot_at=_iso(slot), on_time_run=None, receipt_run=None)
    if window.get("unknown") or alert_at is None or collection is None or slot is None:
        out["sentence"] = "The record gives no entry window, so its morning runs cannot be judged."
        return out
    if now < alert_at:
        out.update(judgement=NOT_DUE, sentence=f"The {session} morning's runs are judged from {alert_at.isoformat()}.")
        return out
    if runs is None:
        out["sentence"] = f"The {session} morning's runs cannot be judged: {reason}."
        return out
    relevant = [r for r in runs if r.get("head_branch") == MAIN and r.get("display_title") != MORNING_REHEARSAL_TITLE
                and _created(r) is not None and _created(r) >= collection
                and _created(r).astimezone(CHICAGO).date().isoformat() == session]
    out["runs"] = _summary(relevant)
    bound = (isinstance(receipt, dict) and _dict(receipt.get("publication")).get("data_sha256")
             == hashlib.sha256(record_raw).hexdigest())
    writer = [r for r in relevant if bound and str(r.get("id")) == str(receipt.get("observation_run_id"))]
    if writer:
        out["receipt_run"] = writer[0]["id"]
    wrote = f" The receipt on main was written by run {writer[0]['id']}." if writer else ""
    on_time = [r for r in relevant if _on_time(r, MORNING_DISPATCH_TITLE, slot)]
    end = slot + timedelta(minutes=ds.DUE_MINUTES)
    if not relevant:
        out.update(judgement=NOT_STARTED,
                   sentence=(f"No morning run for {session} is listed on main from the collection window's start "
                             f"({collection.isoformat()}) by this watch's clock; the dispatcher starts it at "
                             f"{slot.isoformat()}."))
        return out
    if _failed(relevant):
        out.update(judgement=FAILED, sentence=f"Every morning run for {session} listed on main ended without its work: "
                                               f"{_named(relevant)}.{wrote}")
        return out
    if on_time:
        out.update(judgement=ON_TIME, on_time_run=on_time[0]["id"],
                   sentence=f"The {session} morning check was started on time by the dispatcher: "
                            f"{_named(on_time[:1])}.{wrote}")
        return out
    alert = now - alert_at < timedelta(hours=MORNING_ALERT_HOURS)
    out.update(judgement=STARTED_LATE, alert=alert, action=SCHEDULER_HINT if alert else None,
               key=f"scheduler:morning:{STARTED_LATE}" if alert else None,
               sentence=(f"The {session} morning check was not started by the on-time dispatcher in its due window "
                         f"({slot.isoformat()} to {end.isoformat()}): the runs listed are {_named(relevant)}.{wrote}"))
    return out


def previous_watch_slot(now: datetime) -> datetime | None:
    """The latest of the dispatcher's watch slots whose due window has closed by ``now``; None when there is
    none in ``WATCH_LOOKBACK_DAYS``, or the calendar cannot say."""
    days = {(now - timedelta(days=back)).astimezone(zone).date()
            for back in range(WATCH_LOOKBACK_DAYS + 1) for zone in (ds.ET, ds.CT)}
    found = []
    try:
        for day in days:
            found += [s.at for s in ds.slots_on(day) if s.workflow == WATCH_WORKFLOW
                      and s.at + timedelta(minutes=ds.DUE_MINUTES) <= now]
    except ValueError:
        return None
    return max(found) if found else None


_UNSET = object()


def judge_watch(now: datetime, runs: list[dict] | None, reason: str | None, previous=_UNSET) -> dict:
    """Whether the on-time dispatcher started this watch at its own previous slot: said after the fact."""
    previous = previous_watch_slot(now) if previous is _UNSET else previous
    out = _block(WATCH_WORKFLOW, about="slot", slot_at=_iso(previous), on_time_run=None)
    if previous is None:
        out.update(judgement=NOT_DUE, sentence="The dispatcher has no earlier watch slot to judge.")
        return out
    if runs is None:
        out["sentence"] = f"The watch's previous slot ({previous.isoformat()}) cannot be judged: {reason}."
        return out
    end = previous + timedelta(minutes=ds.DUE_MINUTES)
    in_window = [r for r in runs if r.get("head_branch") == MAIN and _created(r) is not None
                 and previous <= _created(r) < end]
    out["runs"] = _summary(in_window)
    on_time = [r for r in in_window if _on_time(r, WATCH_DISPATCH_TITLE, previous)]
    if on_time:
        out.update(judgement=ON_TIME, on_time_run=on_time[0]["id"],
                   sentence=f"The watch's previous slot ({previous.isoformat()}) was started by the dispatcher: "
                            f"{_named(on_time[:1])}.")
        return out
    out.update(judgement=NOT_STARTED, alert=True, action=SCHEDULER_HINT, key=f"scheduler:watch:{NOT_STARTED}",
               sentence=(f"No watch was started by the on-time dispatcher in its slot at {previous.isoformat()} (the "
                         f"{ds.DUE_MINUTES} minutes from it); a later watch says so after the fact."))
    return out


def _listing(github, workflow: str, since: datetime | None) -> tuple[list[dict] | None, str | None]:
    if since is None:
        return None, "the record gives no instant to list the runs from"
    if github is None:
        return None, NO_TOKEN
    try:
        return github.runs(workflow, since), None
    except ds.HTTPFailure as exc:
        return None, f"the run listing answered HTTP {exc.status}"
    except ds.Incomplete:
        return None, "the run listing could not be read whole"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return None, f"the run listing could not be read ({type(exc).__name__})"


def scheduler(record: dict, receipt: dict | None, record_raw: bytes, now: datetime, github=None) -> dict:
    """The three scheduler answers. ``github`` is a ``tools/dispatch_schedule.GitHub`` (or a double); without one
    every answer is ``unknown`` and nothing is asked."""
    runs, why = _listing(github, EVENING_WORKFLOW, evening_since(record, now))
    first = judge_evening(record, now, runs, why)
    window = freshness.morning_window(record)
    alert_at = morning_alert(window.get("applicable_session"))
    if alert_at is not None and now >= alert_at:
        runs, why = _listing(github, MORNING_WORKFLOW, _instant(window.get("collection_starts_at")))
    else:
        runs, why = None, None
    second = judge_morning(record, receipt, record_raw, now, runs, why)
    previous = previous_watch_slot(now)
    runs, why = _listing(github, WATCH_WORKFLOW, previous) if previous is not None else (None, None)
    third = judge_watch(now, runs, why, previous)
    read = github is not None
    return {"listing": "read" if read else UNKNOWN, "reason": None if read else NO_TOKEN,
            "evening": first, "morning": second, "watch": third}


# ------------------------------------------------------------------- watch ---
def _alert(key: str, sentence: str, action: str | None, detail: str | None = None) -> dict:
    family, rest = key.split(":", 1)
    if family == "scheduler":
        name, word = rest.split(":", 1)
        subject = SUBJECTS[(f"scheduler:{name}", word)]
        scope = None
    elif family == "record":
        subject, scope = UNREADABLE_SUBJECT, rest.split(":", 1)[1]
    else:
        word, scope = rest.split(":", 1)
        subject = SUBJECTS[(family, word)].format(scope=scope)
    return {"key": key, "subject": subject, "sentence": sentence, "action": action, "detail": detail,
            "standing": family == "scheduler", "scope": scope}


def alerts_of(result: dict) -> list[dict]:
    """Every alert the result carries, once per key, in a fixed order."""
    out, seen = [], set()

    def add(block, detail=None):
        if block.get("alert") and block.get("key") and block["key"] not in seen:
            seen.add(block["key"])
            out.append(_alert(block["key"], block["sentence"], block.get("action"), detail))
    sched = result.get("scheduler") or {}
    add(result["evening"])
    add(sched.get("evening") or {})
    start_block = result.get("start") or {}
    record_run = sched.get("evening") or {}
    if not (record_run.get("about") == "record_run" and record_run.get("judgement") in (ON_TIME, STARTED_LATE)):
        add(start_block)                               # the listing, when it read the same run, answers instead
    morning_sched = sched.get("morning") or {}
    detail = morning_sched.get("sentence") if morning_sched.get("judgement") in (NOT_STARTED, FAILED, STARTED_LATE) \
        else None
    add(result["morning"], detail)
    add(morning_sched)
    add(result.get("handoff") or {})
    add(sched.get("watch") or {})
    return out


def watch(docs: Path, now: datetime, github=None) -> dict:
    """Every answer for the files under ``docs`` at ``now`` (an aware instant); ``github`` reads the run listing."""
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("the watch needs its clock as an instant with an offset")
    record_raw = read_bytes(docs / DATA_FILE, MAX_RECORD_BYTES)
    record = decode(record_raw, DATA_FILE)
    receipt, receipt_problem = None, None
    try:
        receipt = decode(read_bytes(docs / MORNING_FILE, MAX_MORNING_BYTES), MORNING_FILE)
    except Unreadable as exc:
        receipt_problem = str(exc)
    orders_raw = _optional(docs / ORDERS_FILE, orders.MAX_BYTES)
    orders_morning_raw = _optional(docs / ORDERS_MORNING_FILE, orders.MAX_BYTES)
    sched = scheduler(record, receipt, record_raw, now, github)
    next_session = freshness.expected(record).get("next_session")
    on_time_start = (sched["evening"].get("about") == "session" and sched["evening"].get("session") == next_session
                     and sched["evening"].get("on_time_run") is not None)
    first = evening(record, now, on_time_start=on_time_start)
    second = morning(record, record_raw, receipt, receipt_problem, now, orders_raw=orders_raw,
                     orders_morning_raw=orders_morning_raw)
    third = start(record, now)
    fourth = handoff(docs, record, record_raw)
    result = {"version": VERSION, "clock": now.astimezone(timezone.utc).isoformat(),
              "record_sha256": hashlib.sha256(record_raw).hexdigest(),
              "evening": first, "morning": second, "start": third, "handoff": fourth, "scheduler": sched}
    result["alerts"] = alerts_of(result)
    result["alert"] = bool(result["alerts"])
    result["exit_code"] = (EXIT_ALERT if result["alert"] else EXIT_UNKNOWN if first["judgement"] == UNKNOWN
                           else EXIT_OK)
    return result


def lines(result: dict) -> list[str]:
    """The result as the run log prints it."""
    first, second = result["evening"], result["morning"]
    out = [f"Service watch at {result['clock']}.",
           f"Evening: {first['judgement']} ({first['state']}). {first['sentence']}"]
    if first["action"]:
        out.append(f"  {first['action']}")
    out.append(f"Morning: {second['judgement']}. {second['sentence']}")
    if second["action"]:
        out.append(f"  {second['action']}")
    third = result.get("start") or {}
    if third:
        out.append(f"Start: {third['judgement']}. {third['sentence']}")
    fourth = result.get("handoff") or {}
    if fourth:
        out.append(f"Handoff: {fourth['judgement']}. {fourth['sentence']}")
    for name in ("evening", "morning", "watch"):
        block = (result.get("scheduler") or {}).get(name)
        if block:
            out.append(f"Scheduler {name}: {block['judgement']}. {block['sentence']}")
    for entry in result.get("alerts") or []:
        out.append(f"Alert {entry['key']}: {entry['subject']}")
    out.append("Alert." if result["alert"] else "Nothing to flag.")
    return out


def body(alert: dict, clock: str) -> str:
    paragraphs = [alert["sentence"], alert["action"], alert.get("detail"), f"Watch clock: {clock}. {LATE_ITSELF}",
                  f"Alert key: {alert['key']}. With its ledger the watch mails a key once, and again only after "
                  f"{REPEAT_DAYS} days."]
    return "".join(f"<p>{html.escape(text)}</p>" for text in paragraphs if text)


def messages(result: dict) -> list[dict]:
    """(key, subject, HTML body) for each alert the result carries; none otherwise."""
    return [{"key": a["key"], "subject": a["subject"], "body": body(a, result["clock"])} for a in result["alerts"]]


# ------------------------------------------------------------------ ledger ---
def read_ledger(path: Path | None, now: datetime) -> dict[str, datetime]:
    """The keys mailed and when. Empty -- so every alert mails again -- when there is no ledger, or it is not a
    regular file this watch wrote: too large, not JSON, another version, a key or an instant it cannot read, or
    an instant after ``now``."""
    if path is None:
        return {}
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_LEDGER_BYTES:
            return {}
        value = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, RecursionError):
        return {}
    if not isinstance(value, dict) or set(value) != {"version", "sent"} \
            or type(value["version"]) is not int or value["version"] != LEDGER_VERSION \
            or not isinstance(value["sent"], dict):
        return {}
    out = {}
    for key, at in value["sent"].items():
        when = _instant(at)
        if not isinstance(key, str) or not KEY_PATTERN.fullmatch(key) or when is None or when > now:
            return {}
        out[key] = when
    return out


def write_ledger(path: Path, sent: dict[str, datetime], now: datetime) -> None:
    """The keys and instants alone, the ones older than ``REPEAT_DAYS`` dropped, written whole or not at all."""
    keep = {key: at for key, at in sent.items() if now - at < timedelta(days=REPEAT_DAYS)}
    payload = {"version": LEDGER_VERSION,
               "sent": {key: keep[key].astimezone(timezone.utc).isoformat() for key in sorted(keep)}}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def send(alerts: list[dict], now: datetime, ledger: Path | None, clock: str | None = None) -> dict:
    """Mail each alert whose key the ledger does not hold from the last ``REPEAT_DAYS``, through the evening's
    transport; remember a key only once its mail was accepted, and write the ledger only then."""
    clock = clock or now.astimezone(timezone.utc).isoformat()
    sent = read_ledger(ledger, now)
    outcome = {"mailed": [], "dropped": [], "failed": [], "ledger_written": False, "ledger_error": None}
    for alert in alerts:
        before = sent.get(alert["key"])
        if before is not None and now - before < timedelta(days=REPEAT_DAYS):
            outcome["dropped"].append({"key": alert["key"], "mailed_at": before.astimezone(timezone.utc).isoformat()})
            continue
        from src import report  # the one send path; imported only when a message is owed
        try:
            report.deliver(alert["subject"], body(alert, clock))
        except Exception as exc:                       # a refused or failed send is not remembered
            outcome["failed"].append({"key": alert["key"], "error": type(exc).__name__})
            continue
        sent[alert["key"]] = now
        outcome["mailed"].append(alert["key"])
    if outcome["mailed"] and ledger is not None:
        try:
            write_ledger(ledger, sent, now)
            outcome["ledger_written"] = True
        except OSError as exc:
            outcome["ledger_error"] = type(exc).__name__
    return outcome


def outcome_lines(outcome: dict) -> list[str]:
    out = [f"Mailed {key}." for key in outcome["mailed"]]
    out += [f"Not mailed again: {d['key']} was mailed at {d['mailed_at']}." for d in outcome["dropped"]]
    out += [f"Mail failed for {f['key']} ({f['error']}); it is not remembered, so the next run mails it." for f in
            outcome["failed"]]
    if outcome["ledger_error"]:
        out.append(f"The ledger could not be written ({outcome['ledger_error']}): the next run mails these again.")
    sent = len(outcome["mailed"])
    out.append(f"Mailed {sent} alert{'' if sent == 1 else 's'}.")
    return out


def github_output(env, outcome: dict) -> None:
    """Tell the workflow the ledger changed, so it saves it: ``ledger=written`` in ``$GITHUB_OUTPUT``."""
    target = (env or {}).get("GITHUB_OUTPUT")
    if target and outcome.get("ledger_written"):
        with open(target, "a", encoding="utf-8") as handle:
            handle.write("ledger=written\n")


def github_from(env) -> ds.GitHub | None:
    """The run listing's client, when the environment carries a token; else None and the scheduler is unknown."""
    token = ((env or {}).get(ds.TOKEN_ENV) or "").strip()
    return ds.GitHub(token) if token else None


def main(argv: list[str] | None = None, env=None) -> int:
    env = os.environ if env is None else env
    parser = argparse.ArgumentParser(description="Is the evening publication late or missing, did the morning check "
                                                 "land, are the handoff files bound, and did the scheduler run?")
    parser.add_argument("--docs", type=Path, default=ROOT / "docs")
    parser.add_argument("--now", help="the clock to judge by, ISO-8601 with an offset (default: this machine's clock)")
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    parser.add_argument("--mail", action="store_true", help="mail each alert through the evening's transport")
    parser.add_argument("--ledger", type=Path, default=None,
                        help="the sent-alert ledger: a key it holds is not mailed again for REPEAT_DAYS")
    args = parser.parse_args(argv)
    now = _instant(args.now) if args.now else datetime.now(timezone.utc)
    if now is None:
        print("--now is not an instant with an offset", file=sys.stderr)
        return EXIT_UNKNOWN
    try:
        result = watch(args.docs, now, github_from(env))
    except Unreadable as exc:
        print(f"Service watch: {exc}.", file=sys.stderr)
        if not args.mail:
            return EXIT_UNKNOWN
        # the state in which the site itself can show no record: a person should hear of it, once per bytes
        alert = _alert(f"record:unreadable:{record_key(args.docs / DATA_FILE)}",
                       f"The record on main could not be read: {exc}.", None)
        outcome = send([alert], now, args.ledger)
        print("\n".join(outcome_lines(outcome)), file=sys.stderr)
        github_output(env, outcome)
        return EXIT_UNKNOWN if outcome["mailed"] or outcome["failed"] else EXIT_OK
    print(json.dumps(result, indent=1, sort_keys=True) if args.json else "\n".join(lines(result)))
    if not args.mail or not result["alert"]:
        return result["exit_code"]
    outcome = send(result["alerts"], now, args.ledger, result["clock"])
    print("\n".join(outcome_lines(outcome)), file=sys.stderr)
    github_output(env, outcome)
    return EXIT_ALERT if outcome["mailed"] or outcome["failed"] else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
