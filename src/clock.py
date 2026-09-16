"""Clock/override adapter for the single XNYS session authority."""
from __future__ import annotations

import os
from datetime import date, datetime, time as time_of_day

from src import sessions
from src.sessions import MARKET_TZ, MARKET_TZ_NAME, previous_session

# Compatibility/documentation only: a regular close plus the completion buffer.
# Real decisions read the dated exchange close, including shortened sessions.
SESSION_COMPLETE_ET = time_of_day(16, 15)


def _market_time(now: datetime | None) -> datetime:
    return sessions.market_time(now)


def pinned_session() -> date | None:
    """An explicitly requested exchange session; never silently substitute."""
    raw = os.environ.get('SCAN_SESSION_DATE', '').strip()
    if not raw:
        return None
    try:
        day = date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f'SCAN_SESSION_DATE={raw!r} is not a YYYY-MM-DD date') from exc
    return sessions.require_session(day)


def current_session(now: datetime | None = None) -> date:
    """Most recent scheduled session past its close plus completion buffer."""
    return sessions.completed_session(now)


def session_has_closed(now: datetime | None = None) -> bool:
    at = _market_time(now)
    return sessions.is_session(at.date()) and at >= sessions.completion_at(at.date())


def is_trading_weekday(now: datetime | None = None) -> bool:
    """Compatibility name: now answers actual XNYS session membership."""
    return sessions.is_session(_market_time(now).date())
