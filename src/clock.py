"""Which US session a run can honestly scan, read off the clock alone.

Weekends are arithmetic here and holidays are not: nothing in this module is
a market calendar. A run on a holiday therefore targets a session the market
never held, finds no bar carrying it, and fails loudly downstream. That is the
intended outcome -- the alternative is re-reading the previous session as
"today" and mailing its bursts under tonight's date.
"""

from __future__ import annotations

import os
from datetime import date, datetime, time as time_of_day, timedelta, timezone
from zoneinfo import ZoneInfo

try:
    MARKET_TZ = ZoneInfo("America/New_York")
except Exception as e:  # pragma: no cover - depends on the host's tz database
    raise RuntimeError(
        "the America/New_York time zone is unavailable, so this module cannot "
        "tell which session a run targets; `pip install tzdata`"
    ) from e

#: The regular session closes at 16:00 ET. This cutoff selects the session's
#: DATE; it promises nothing about the daily bar's fields being final, since
#: Alpaca's daily volume goes on including extended-hours prints after it.
#: The evening cron fires after this instant, so moving the cutoff later would
#: make that cron scan yesterday: the schedule and the cutoff move together.
SESSION_COMPLETE_ET = time_of_day(16, 15)


def _market_time(now: datetime | None) -> datetime:
    """`now` in market time, reading the wall clock when none is given."""
    return (now or datetime.now(timezone.utc)).astimezone(MARKET_TZ)


def pinned_session() -> date | None:
    """SCAN_SESSION_DATE as a date, or None for "derive it from the clock".

    An empty string is unset: a GitHub Actions dispatch with no `session` box
    filled in sends '' rather than leaving the variable out. A value that is
    not a YYYY-MM-DD date raises rather than falling back to the clock.
    """
    raw = os.environ.get("SCAN_SESSION_DATE", "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as e:
        raise ValueError(f"SCAN_SESSION_DATE={raw!r} is not a YYYY-MM-DD date") from e


def current_session(now: datetime | None = None) -> date:
    """The most recent session whose daily bar is finished.

    Before SESSION_COMPLETE_ET the day's bar is still being written, so the
    answer is the day before; weekends are stepped back one day at a time
    (from a Saturday one step lands on Friday and two would land on Thursday,
    which is why the step is one day and not two).
    """
    now_et = _market_time(now)
    session = now_et.date()
    if now_et.time() < SESSION_COMPLETE_ET:
        session -= timedelta(days=1)
    while session.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
        session -= timedelta(days=1)
    return session


def session_has_closed(now: datetime | None = None) -> bool:
    """Is TODAY's session already over, in market time?

    Equivalent to `current_session(now) == today in ET`, by the same
    arithmetic: weekends are subtracted and holidays are not. An evening run
    belongs on the True side and a pre-open pass on the False side; without
    this check a `evening` run at lunchtime once scanned yesterday and mailed
    it as tonight's candidates.
    """
    now_et = _market_time(now)
    return is_trading_weekday(now) and now_et.time() >= SESSION_COMPLETE_ET


def is_trading_weekday(now: datetime | None = None) -> bool:
    """Monday to Friday in market time -- the weekday half of session_has_closed().

    Its own function so a caller that needs the weekday ALONE reads the same
    clock: a Saturday dispatch used to be told "today's session has not closed
    yet" when there was no session today to close. Labor Day is a trading
    weekday to this arithmetic; the scan is what finds no bar for it. Market
    time, not UTC: Friday 23:30 ET is Saturday in UTC and still a weekday.
    """
    return _market_time(now).weekday() < 5


def previous_session(session: date) -> date:
    """The business day before `session` -- the same weekend-only arithmetic
    current_session() makes, so the two cannot disagree. The day after a
    weekday holiday is the one case this gets wrong, which is why the scan
    reads the session before off the night's frames instead."""
    prior = session - timedelta(days=1)
    while prior.weekday() >= 5:
        prior -= timedelta(days=1)
    return prior
