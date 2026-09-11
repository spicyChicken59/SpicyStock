"""src.clock -- which session a run can scan, pinned on real instants.

Every instant below is written out and never read off the wall clock: a test
whose answer depends on the hour it runs is green all evening and red all
morning, which is the worst kind there is. The one no-argument call made
here asserts only what is true at every hour.
"""

from __future__ import annotations

from datetime import date, datetime, time as time_of_day, timedelta, timezone

import pytest

from src.clock import (
    MARKET_TZ,
    SESSION_COMPLETE_ET,
    current_session,
    is_trading_weekday,
    pinned_session,
    previous_session,
    session_has_closed,
)


# --- which session a run is scanning ---------------------------------------


def test_the_session_is_todays_once_the_close_has_passed():
    """The evening cron fires at 18:16 ET."""
    assert current_session(datetime(2026, 9, 1, 18, 30, tzinfo=MARKET_TZ)) == date(2026, 9, 1)


def test_the_session_is_yesterdays_while_the_market_is_still_open():
    """Today's daily bar is still being written at 11am."""
    assert current_session(datetime(2026, 9, 1, 11, 0, tzinfo=MARKET_TZ)) == date(2026, 8, 31)


def test_the_session_is_read_in_market_time_not_utc():
    """19:00 UTC is 15:00 ET with an hour of trading left. Read as UTC it
    looks like a finished evening -- an instant the two clocks disagree
    about, unlike midnight UTC, which passed with the conversion deleted."""
    assert current_session(datetime(2026, 9, 1, 19, 0, tzinfo=timezone.utc)) == date(2026, 8, 31)


def test_the_session_is_never_a_weekend():
    """Sunday evening: the most recent finished session is Friday's."""
    assert current_session(datetime(2026, 9, 6, 18, 30, tzinfo=MARKET_TZ)) == date(2026, 9, 4)


def test_the_weekend_rewind_steps_back_one_day_at_a_time():
    """Saturday, the only day of the week that can tell. From Sunday one
    step lands on Saturday and loops to Friday, and two steps land on Friday
    directly, so the Sunday case passes either way -- `days=2` survived the
    suite until this instant existed. From Saturday one step is Friday and
    two is Thursday, a session whose bars would then be read as today's."""
    assert current_session(datetime(2026, 9, 5, 18, 30, tzinfo=MARKET_TZ)) == date(2026, 9, 4)


def test_a_session_is_finished_the_moment_the_settling_margin_has_passed():
    """Both sides of SESSION_COMPLETE_ET, read off the constant, so moving
    it fails here rather than silently making the evening cron scan
    yesterday."""
    close = datetime.combine(date(2026, 9, 1), SESSION_COMPLETE_ET, tzinfo=MARKET_TZ)
    assert current_session(close) == date(2026, 9, 1)
    assert current_session(close - timedelta(minutes=1)) == date(2026, 8, 31)


def test_the_settling_margin_is_the_number_the_schedule_was_built_around():
    """16:15 ET. The crons are placed after it; the two move together."""
    assert SESSION_COMPLETE_ET == time_of_day(16, 15)


def test_a_call_with_no_instant_reads_the_wall_clock_and_is_still_a_weekday():
    """The no-argument path is the one production takes. What is true of
    its answer at every hour: a weekday, no later than today in market time."""
    today_et = datetime.now(timezone.utc).astimezone(MARKET_TZ).date()
    session = current_session()
    assert session.weekday() < 5
    assert session <= today_et
    assert isinstance(session_has_closed(), bool)
    assert isinstance(is_trading_weekday(), bool)


# --- which side of the close a run is on -----------------------------------


def test_the_session_has_closed_after_the_settling_margin_and_not_before():
    close = datetime.combine(date(2026, 9, 1), SESSION_COMPLETE_ET, tzinfo=MARKET_TZ)
    assert session_has_closed(close) is True
    assert session_has_closed(close - timedelta(minutes=1)) is False


def test_a_weekend_evening_is_not_a_session_that_closed_today():
    """Saturday at 6pm: a session did close recently, but not today's."""
    assert session_has_closed(datetime(2026, 9, 5, 18, 30, tzinfo=MARKET_TZ)) is False


def test_the_close_is_read_in_market_time_not_utc():
    assert session_has_closed(datetime(2026, 9, 1, 19, 0, tzinfo=timezone.utc)) is False


@pytest.mark.parametrize("hour", [0, 6, 9, 13, 16, 17, 21, 23])
@pytest.mark.parametrize("day", [31, 1, 2, 3, 4, 5, 6])   # Mon 2026-08-31 .. Sun
def test_the_two_clock_functions_can_never_disagree(day, hour):
    """"today's session has closed" and "the newest completed session is
    today" are one fact computed twice; a week of hours pins them together."""
    month = 8 if day == 31 else 9
    now = datetime(2026, month, day, hour, 30, tzinfo=MARKET_TZ)
    assert session_has_closed(now) == (current_session(now) == now.date())


def test_a_trading_weekday_is_monday_to_friday_in_market_time():
    """Market time, not UTC: Friday 23:30 ET is Saturday in UTC and still a
    trading weekday. Labor Day is a Monday and a weekday to this arithmetic;
    the scan is what finds no bar for it."""
    assert is_trading_weekday(datetime(2026, 9, 5, 22, 16, tzinfo=timezone.utc)) is False   # Saturday
    assert is_trading_weekday(datetime(2026, 9, 6, 5, 34, tzinfo=timezone.utc)) is False    # Sunday
    assert is_trading_weekday(datetime(2026, 9, 7, 22, 16, tzinfo=timezone.utc)) is True    # Labor Day
    assert is_trading_weekday(datetime(2026, 9, 5, 3, 30, tzinfo=timezone.utc)) is True     # Fri 23:30 ET
    assert session_has_closed(datetime(2026, 9, 5, 3, 30, tzinfo=timezone.utc)) is True
    assert session_has_closed(datetime(2026, 9, 5, 22, 16, tzinfo=timezone.utc)) is False


# --- the session before ----------------------------------------------------


def test_previous_session_is_weekend_only_arithmetic_like_current_session():
    assert previous_session(date(2026, 6, 24)) == date(2026, 6, 23)   # Wed -> Tue
    assert previous_session(date(2026, 6, 22)) == date(2026, 6, 19)   # Mon -> Fri
    assert previous_session(date(2026, 6, 20)) == date(2026, 6, 19)   # Sat -> Fri
    assert previous_session(date(2026, 6, 21)) == date(2026, 6, 19)   # Sun -> Fri
    assert previous_session(date(2026, 9, 8)) == date(2026, 9, 7), (
        "Labor Day: the arithmetic does not know, which is why the scan reads the frames")


# --- the pinned session ----------------------------------------------------


def test_a_pinned_session_is_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("SCAN_SESSION_DATE", "2026-06-24")
    assert pinned_session() == date(2026, 6, 24)
    monkeypatch.setenv("SCAN_SESSION_DATE", "  2026-06-24 \n")
    assert pinned_session() == date(2026, 6, 24), "surrounding whitespace is not part of a date"


def test_an_empty_or_absent_pin_means_derive_it_from_the_clock(monkeypatch):
    """A dispatch with the session box left blank sends '' rather than
    leaving the variable out."""
    monkeypatch.setenv("SCAN_SESSION_DATE", "")
    assert pinned_session() is None
    monkeypatch.setenv("SCAN_SESSION_DATE", "   ")
    assert pinned_session() is None
    monkeypatch.delenv("SCAN_SESSION_DATE", raising=False)
    assert pinned_session() is None


@pytest.mark.parametrize("raw", ["yesterday", "2026/06/24", "24-06-2026", "2026-13-01"])
def test_a_pin_that_is_not_a_date_raises_rather_than_falling_back(monkeypatch, raw):
    monkeypatch.setenv("SCAN_SESSION_DATE", raw)
    with pytest.raises(ValueError, match="SCAN_SESSION_DATE"):
        pinned_session()
