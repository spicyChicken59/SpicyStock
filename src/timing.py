"""When a published plan's entry window opens and when it is over.

The run serializes this once, into ``run.timing``, so the page never has to
read a deadline out of an English instruction. Two facts about a record are
different things and this module exists to keep them apart:

* which session was MEASURED and when the record was PUBLISHED -- already in
  ``run.session`` and ``run.published_at``, and the page's own staleness
  arithmetic reads them;
* which session the published plans are FOR, and the window inside it during
  which the method's entry is scheduled -- this block, and nothing else.

The applicable session is ``plan.next_sessions(session, 1)[0]``, the same
call ``plan.dated_schedule()`` makes for day 1, so the timing block and every
plan's dated schedule cannot disagree; ``tests/test_timing.py`` holds them
equal. The instants are built with ``zoneinfo`` from the named policy times
below, so a spring-forward or fall-back session is the tz database's answer
and no UTC offset is ever written by hand.

What this module does NOT know, it says, in ``limits``:

``no_holiday_calendar``
    Nothing in this repository is a market calendar -- ``clock.py`` says so of
    its own arithmetic and ``plan.next_sessions()`` of its own. The applicable
    session is therefore the next WEEKDAY, which a holiday moves. The window
    is described as SCHEDULED for that date, never as open, and a reader is
    told the date so the mistake is visible rather than hidden.

``regular_hours_assumed``
    The open and the cutoff are the regular session's. A shortened session
    (the half days around Thanksgiving and Christmas) closes early; no early
    close calendar exists here either, and the opening bell -- which is what
    the entry window hangs off -- does not move on those days.

Nothing here reads a provider, a calendar service or the network.
"""

from __future__ import annotations

from datetime import date, datetime, time as time_of_day, timedelta
from typing import Any, Mapping

from src.clock import MARKET_TZ, MARKET_TZ_NAME

#: The regular session's opening bell in market time. The entry window hangs
#: off it: ``plan.ENTRY_WINDOW_MINUTES`` after this instant the window is over.
#: Not a strategy number -- the exchange's hours -- and it does not move on a
#: shortened session, which closes early and still opens at 9:30.
REGULAR_OPEN_ET = time_of_day(9, 30)

#: The regular session's close, for the page to say "still today" against.
REGULAR_CLOSE_ET = time_of_day(16, 0)

#: The desk's own preparation reminder: have the orders keyed in before this.
#: It is NOT the entry cutoff and never gates an action -- two minutes before
#: the bell is when a reader wants to be ready, and the window itself runs to
#: ``cutoff_at``. The page used to hold this string and now prints this field.
PREPARE_BEFORE_ET = time_of_day(9, 28)

#: How the applicable session was chosen. ``weekday_after_session`` is the
#: ordinary night; ``weekday_after_closed_session`` is the one holiday this
#: repository does detect -- a night whose expected session printed no bars, so
#: the plans that stood for it apply to the weekday after THAT. Named constants
#: so a record written under a real calendar is told apart from one written here.
BASIS_WEEKDAY_AFTER = "weekday_after_session"
BASIS_AFTER_CLOSED = "weekday_after_closed_session"
BASES: tuple[str, ...] = (BASIS_WEEKDAY_AFTER, BASIS_AFTER_CLOSED)

#: What the timing block cannot answer, in the record's own words. The page
#: keeps one sentence per key and `tests/test_docs.py` holds the two lists
#: equal, as it does the problem words and the no-ticket leads.
LIMIT_NO_HOLIDAY_CALENDAR = "no_holiday_calendar"
LIMIT_REGULAR_HOURS = "regular_hours_assumed"
LIMITS: tuple[str, ...] = (LIMIT_NO_HOLIDAY_CALENDAR, LIMIT_REGULAR_HOURS)

#: The four answers to "is the entry window applicable now?". `unknown` is for
#: a record that carries no timing block at all -- every record published
#: before this field existed -- and means research only, never permission.
PHASE_UPCOMING = "upcoming"
PHASE_OPEN = "open"
PHASE_ENDED = "ended"
PHASE_UNKNOWN = "unknown"
PHASES: tuple[str, ...] = (PHASE_UPCOMING, PHASE_OPEN, PHASE_ENDED, PHASE_UNKNOWN)

RULES: dict[str, Any] = {
    "timing.regular_open_et": REGULAR_OPEN_ET.isoformat(timespec="minutes"),
    "timing.regular_close_et": REGULAR_CLOSE_ET.isoformat(timespec="minutes"),
    "timing.prepare_before_et": PREPARE_BEFORE_ET.isoformat(timespec="minutes"),
    "timing.bases": list(BASES),
    "timing.limits": list(LIMITS),
}


def at(session: date, when: time_of_day) -> datetime:
    """``when`` on ``session`` in market time, offset and all.

    The offset comes from the tz database, so 8 March 2026 -- the Sunday the
    clocks go forward -- and the sessions either side of it each get their own,
    and a record written in December carries -05:00 where one written in
    September carries -04:00.
    """
    return datetime.combine(session, when, tzinfo=MARKET_TZ)


def entry_window(session: date, window_minutes: int) -> tuple[datetime, datetime]:
    """The scheduled entry window on ``session``: the bell, and ``window_minutes``
    after it. The cutoff is arithmetic on an aware instant, so a window that
    crossed a DST boundary would be the wall clock's answer and not 30 minutes
    of UTC -- it cannot, at 9:30 in the morning, but the arithmetic says which
    one it is."""
    if not isinstance(window_minutes, int) or window_minutes <= 0:
        raise ValueError(f"window_minutes must be a positive whole number, not {window_minutes!r}")
    opens = at(session, REGULAR_OPEN_ET)
    return opens, opens + timedelta(minutes=window_minutes)


def plan_timing(measured_session: date, applicable: date, *, window: str,
                window_minutes: int, basis: str = BASIS_WEEKDAY_AFTER,
                closed_session: date | None = None) -> dict[str, Any]:
    """The serialized block: which session the plans are for, and when its
    entry window opens and is over.

    ``applicable`` is passed in rather than derived here, because the caller
    has already asked ``plan.next_sessions()`` for the dated schedule and the
    two must be the same date. It is checked against ``measured_session``
    instead of trusted: a plan cannot be for a session at or before the one it
    was measured on. ``closed_session`` is the session that printed no bars on
    a closed night -- the date the standing plans were dated for and which the
    market did not hold -- so the page can name it rather than leave a plan's
    own day 1 unexplained.
    """
    if applicable <= measured_session:
        raise ValueError(
            f"the applicable session {applicable} is not after the measured one "
            f"{measured_session}; a plan cannot be for a session already read"
        )
    if basis not in BASES:
        raise ValueError(f"basis {basis!r} is not one of {BASES}")
    opens, cutoff = entry_window(applicable, window_minutes)
    return {
        "applicable_session": applicable.isoformat(),
        "measured_session": measured_session.isoformat(),
        "closed_session": closed_session.isoformat() if closed_session else None,
        "timezone": MARKET_TZ_NAME,
        "opens_at": opens.isoformat(),
        "cutoff_at": cutoff.isoformat(),
        "prepare_by": at(applicable, PREPARE_BEFORE_ET).isoformat(),
        "closes_at": at(applicable, REGULAR_CLOSE_ET).isoformat(),
        # the same two policy times as wall clock, so a reader comparing a DATE
        # it has (a saved setup's own session) needs no offset arithmetic of
        # its own: the browser reads `now` in market time and compares hours
        "opens_et": REGULAR_OPEN_ET.isoformat(timespec="minutes"),
        "cutoff_et": (datetime.combine(date(2000, 1, 1), REGULAR_OPEN_ET)
                      + timedelta(minutes=window_minutes)).time().isoformat(timespec="minutes"),
        "prepare_by_et": PREPARE_BEFORE_ET.isoformat(timespec="minutes"),
        "window": window,
        "window_minutes": window_minutes,
        "basis": basis,
        "limits": list(LIMITS),
    }


def phase(timing: Mapping[str, Any] | None, now: datetime) -> str:
    """Which of ``PHASES`` ``now`` falls in, from the serialized instants.

    The page makes the same comparison in the browser off the same two fields;
    this is where the rule is pinned by a test, and where a record that
    carries no timing block is answered ``unknown`` rather than guessed at.
    A window is OPEN from its opening instant up to but not including its
    cutoff: at the cutoff it has ended, because the method's window is the
    first ``window_minutes`` and the last of them is over.
    """
    opens = _instant(timing, "opens_at")
    cutoff = _instant(timing, "cutoff_at")
    if opens is None or cutoff is None or cutoff <= opens:
        return PHASE_UNKNOWN
    if now < opens:
        return PHASE_UPCOMING
    return PHASE_OPEN if now < cutoff else PHASE_ENDED


def _instant(timing: Mapping[str, Any] | None, key: str) -> datetime | None:
    """One serialized instant as an aware datetime, or None if it is missing,
    not a string, not ISO-8601, or carries no offset. An instant without an
    offset is refused rather than read as the reader's own zone."""
    if not isinstance(timing, Mapping):
        return None
    raw = timing.get(key)
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None
