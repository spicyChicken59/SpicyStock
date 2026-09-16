"""One offline exchange-session authority: XNYS via pinned exchange_calendars.

The schedule describes expected regular equity sessions, not feed health or
extended-hours bar finality. Future schedules can change; every record keeps
the version and a bounded schedule for readers that cannot run Python.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

import exchange_calendars as xcals

EXCHANGE = 'XNYS'
EXCHANGE_NAME = 'New York Stock Exchange'
LIBRARY = 'exchange_calendars'
LIBRARY_VERSION = '4.13.2'
VERSION = 1
MARKET_TZ_NAME = 'America/New_York'
MARKET_TZ = ZoneInfo(MARKET_TZ_NAME)
SUPPORTED_START = date(1990, 1, 1)
SUPPORTED_END = date(2035, 12, 31)
COMPLETION_BUFFER_MINUTES = 15
SCHEDULE_PAST_DAYS = 45
SCHEDULE_FUTURE_DAYS = 45
LIMIT_SCHEDULE_CHANGES = 'exchange_schedule_may_change'

RULES = {
    'calendar.version': VERSION, 'calendar.exchange': EXCHANGE,
    'calendar.library': LIBRARY, 'calendar.library_version': LIBRARY_VERSION,
    'calendar.timezone': MARKET_TZ_NAME,
    'calendar.supported_start': SUPPORTED_START.isoformat(),
    'calendar.supported_end': SUPPORTED_END.isoformat(),
    'calendar.completion_buffer_minutes': COMPLETION_BUFFER_MINUTES,
    'calendar.schedule_past_days': SCHEDULE_PAST_DAYS,
    'calendar.schedule_future_days': SCHEDULE_FUTURE_DAYS,
}


@lru_cache(maxsize=1)
def calendar():
    if xcals.__version__ != LIBRARY_VERSION:
        raise ValueError(f'{LIBRARY} {LIBRARY_VERSION} is required; installed {xcals.__version__}')
    return xcals.get_calendar(EXCHANGE, start=SUPPORTED_START.isoformat(), end=SUPPORTED_END.isoformat())


def _bounded(day: date) -> date:
    if not isinstance(day, date) or isinstance(day, datetime) or not SUPPORTED_START <= day <= SUPPORTED_END:
        raise ValueError(f'{EXCHANGE} calendar date {day} is outside supported {SUPPORTED_START} through {SUPPORTED_END}')
    return day


def is_session(day: date) -> bool:
    return bool(calendar().is_session(_bounded(day).isoformat()))


def require_session(day: date) -> date:
    if not is_session(day):
        raise ValueError(f'{day} is not an {EXCHANGE} trading session ({EXCHANGE_NAME}); no date was substituted')
    return day


def previous_session(day: date) -> date:
    """Strictly before the supplied calendar date, even when it is a holiday."""
    before = _bounded(_bounded(day) - timedelta(days=1))
    return calendar().date_to_session(before.isoformat(), direction='previous').date()


def next_sessions(day: date, count: int) -> list[date]:
    if type(count) is not int or count < 0:
        raise ValueError('session count must be a nonnegative integer')
    if not count:
        return []
    after = _bounded(_bounded(day) + timedelta(days=1))
    first = calendar().date_to_session(after.isoformat(), direction='next')
    return [d.date() for d in calendar().sessions_window(first, count)]


def sessions_before(day: date, count: int) -> list[date]:
    if type(count) is not int or count < 0:
        raise ValueError('session count must be a nonnegative integer')
    if not count:
        return []
    last = previous_session(day)
    found = [d.date() for d in calendar().sessions[calendar().sessions <= last.isoformat()][-count:]]
    if len(found) != count:
        raise ValueError(f"{count} prior sessions exceed the supported {EXCHANGE} schedule")
    return found


def dates(start: date, end: date) -> list[date]:
    return [d.date() for d in calendar().sessions_in_range(_bounded(start).isoformat(), _bounded(end).isoformat())]


@lru_cache(maxsize=4096)
def hours(day: date) -> tuple[datetime, datetime, bool]:
    require_session(day)
    cal = calendar()
    key = day.isoformat()
    opens = cal.session_open(key).to_pydatetime().astimezone(MARKET_TZ)
    closes = cal.session_close(key).to_pydatetime().astimezone(MARKET_TZ)
    return opens, closes, key in cal.early_closes


def completion_at(day: date) -> datetime:
    return hours(day)[1] + timedelta(minutes=COMPLETION_BUFFER_MINUTES)


def market_time(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('market clock requires an offset-aware instant')
    return now.astimezone(MARKET_TZ)


def completed_session(now: datetime | None = None) -> date:
    at = market_time(now)
    day = at.date()
    return day if is_session(day) and at >= completion_at(day) else previous_session(day)


def authority() -> dict:
    calendar()  # refuse version/range failure before any provider work
    return {'version': VERSION, 'exchange': EXCHANGE, 'exchange_name': EXCHANGE_NAME,
            'library': LIBRARY, 'library_version': LIBRARY_VERSION, 'timezone': MARKET_TZ_NAME,
            'supported_start': str(SUPPORTED_START), 'supported_end': str(SUPPORTED_END),
            'completion_policy': 'scheduled close plus buffer; daily extended-hours fields may still change',
            'completion_buffer_minutes': COMPLETION_BUFFER_MINUTES,
            'limits': [LIMIT_SCHEDULE_CHANGES]}


def session_info(day: date) -> dict:
    opens, closes, shortened = hours(day)
    return {'session': str(day), 'opens_at': opens.isoformat(), 'closes_at': closes.isoformat(),
            'completion_at': completion_at(day).isoformat(), 'shortened': shortened}


def publication(measured: date) -> dict:
    require_session(measured)
    following = next_sessions(measured, 1)[0]
    start = max(SUPPORTED_START, measured - timedelta(days=SCHEDULE_PAST_DAYS))
    through = min(SUPPORTED_END, measured + timedelta(days=SCHEDULE_FUTURE_DAYS))
    return {**authority(), 'measured_session': str(measured),
            'previous_session': str(previous_session(measured)), 'applicable_session': str(following),
            'measured': session_info(measured), 'applicable': session_info(following),
            'schedule': {'start': str(start), 'through': str(through),
                         'sessions': [session_info(d) for d in dates(start, through)]}}


def run_decision(now: datetime | None, pinned: date | None) -> dict:
    at = market_time(now)
    target = require_session(pinned) if pinned else at.date()
    known_open = is_session(target)
    outcome = ('no_session' if not known_open else
               'session_incomplete' if at < completion_at(target) else 'ready')
    return {'outcome': outcome, 'requested_session': str(pinned) if pinned else None,
            'market_date': str(at.date()), 'target_date': str(target),
            'most_recent_completed': str(completed_session(at)),
            'calendar': authority(), 'published': False}


def record_faults(run: dict) -> list[str]:
    """New records must agree with their calendar and their entry-window dates."""
    block = run.get('calendar')
    if block is None:
        return []  # historical bytes retain their original, limited timing
    try:
        day = date.fromisoformat(run['session'])
        if block != publication(day):
            return ['run.calendar differs from the versioned XNYS schedule']
        tm = run['timing']
        if tm.get('calendar') != authority() or tm['applicable_session'] != block['applicable_session']:
            return ['run timing and calendar applicability disagree']
        if any(tm[k] != block['applicable'][k] for k in ('opens_at', 'closes_at', 'shortened')):
            return ['run timing and scheduled exchange hours disagree']
        return []
    except (KeyError, TypeError, ValueError):
        return ['run.calendar is incomplete or outside the supported schedule']
