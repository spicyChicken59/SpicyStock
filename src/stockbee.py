"""Dated Stockbee research measurements from the bars the scan already fetched.

This sidecar does not select the production shortlist or call a data service.
The canonical scan follows Stockbee's 2015 >=100,000-share version; anticipation
is an explicit SpicyStock numeric proxy for the chart study in his process.
"""
from __future__ import annotations

from datetime import date, timedelta
from math import isfinite
import re

import pandas as pd

SCAN_LIMIT = 40
ANTICIPATION_LIMIT = 25
SERIES_LIMIT = 30
FIELDS = ("open", "high", "low", "close", "volume")
ANTICIPATION_RULES = {
    "kind": "SpicyStock numeric proxy; manual chart review required",
    "min_price": 3,
    "min_prior_three_volume": 100000,
    "min_trend_intensity": 1.05,
    "max_abs_day_change_pct": 1,
    "max_compression_ratio": 0.75,
    "min_contiguous_sessions": 67,
    "excludes_current_4pct_scan_matches": True,
}
MEASUREMENT_RULES = {
    "scan": "close / previous session close >= 1.04; volume > previous session volume; volume >= 100000",
    "breadth": "same volume rules as scan; up: close / previous close >= 1.04; down: close / previous close <= 0.96",
    "breadth_ratios": "sum(up4) / sum(down4), only for a full 5 or 10 dated sessions with nonzero coverage on every day and a nonzero denominator; coverage may vary",
    "volume_vs_average": "current volume / mean volume of previous 20 contiguous sessions",
    "range_expansion": "current (high-low)/close / mean((high-low)/close) over previous 7 contiguous sessions",
    "compression_ratio": "mean((high-low)/close) over latest 7 sessions / mean((high-low)/close) over the preceding 60; 67 contiguous sessions required",
    "close_position": "(close-low)/(high-low), from 0 to 1; null for a zero range",
    "prior_up_days": "consecutive higher closes ending on the previous session; null if available history ends before the streak does",
    "trend_intensity": "mean(close) over latest 7 / mean(close) over latest 65, including current session",
    "prior_bursts_20": "canonical scan matches over previous 20 sessions; not the discretionary count of setups since a trend began",
    "base_down4_count": "close-to-close declines of at least 4% over previous 7 sessions, regardless of volume",
    "extension_sma20_pct": "100 * (current close / mean(close over latest 20 sessions) - 1)",
    "base_range_pct": "100 * (highest high - lowest low over previous 7 sessions) / previous close",
    "prior_day_move_pct": "previous session close-to-close change in percent",
    "prior_day_range_pct": "100 * (previous high - previous low) / previous close",
    "calendar": "scanner previous-session decision for current day; cross-frame observed calendar for history, with any printed immediately preceding weekday retained; missing bars are not bridged",
}


def _day(value) -> date | None:
    if isinstance(value, (int, float, bool)) or value is None:
        return None
    try:
        stamp = pd.Timestamp(value)
        return None if pd.isna(stamp) else stamp.date()
    except (TypeError, ValueError, OverflowError):
        return None


def _number(value) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
        return number if isfinite(number) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _valid_bar(values) -> bool:
    return (all(values.get(k) is not None for k in FIELDS)
            and all(values[k] > 0 for k in ("open", "high", "low", "close"))
            and values["volume"] >= 0
            and values["low"] <= min(values["open"], values["close"])
            and values["high"] >= max(values["open"], values["close"]))


def _bars(frame, through: date) -> dict:
    """Retain invalid dates as holes; never silently shift a lookback over one."""
    if not isinstance(frame, pd.DataFrame):
        return {}
    # scanner._download_batch supplies title-case OHLCV. Also accept lowercase
    # frames at the pure measurement boundary, but never choose between two
    # columns that claim to be the same field.
    aliases = {}
    for column in frame.columns:
        key = str(column).lower()
        if key in FIELDS:
            if key in aliases:
                return {}
            aliases[key] = column
    if not set(FIELDS).issubset(aliases):
        return {}
    columns = [aliases[key] for key in FIELDS]
    out = {}
    for stamp, values in zip(frame.index, frame.loc[:, columns].itertuples(index=False, name=None)):
        day = _day(stamp)
        if day is None or day > through or day.weekday() >= 5:
            continue
        if day in out:
            out[day] = None  # A second daily bar is ambiguous; the scanner normally deduplicates first.
            continue
        bar = dict(zip(FIELDS, (_number(value) for value in values)))
        out[day] = {"date": day.isoformat(), **bar} if _valid_bar(bar) else None
    return out


def _weekday_before(day: date) -> date:
    day -= timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def _scan(bar, previous, *, down=False) -> bool:
    ratio = bar["close"] / previous["close"]
    return ((ratio <= 0.96 if down else ratio >= 1.04)
            and bar["volume"] > previous["volume"] and bar["volume"] >= 100000)


def _mean(values) -> float:
    return sum(values) / len(values)


def _divide(top, bottom):
    return top / bottom if bottom else None


def _row(ticker: str, history: list[dict]) -> dict:
    current, previous = history[-1], history[-2]
    close = current["close"]
    normalized = [(bar["high"] - bar["low"]) / bar["close"] for bar in history]
    range_expansion = (_divide(normalized[-1], _mean(normalized[-8:-1]))
                       if len(history) >= 8 else None)
    compression = (_divide(_mean(normalized[-7:]), _mean(normalized[-67:-7]))
                   if len(history) >= 67 else None)
    streak = 0
    for at in range(len(history) - 2, 0, -1):
        if history[at]["close"] <= history[at - 1]["close"]:
            break
        streak += 1
    else:
        streak = None
    base = history[-8:-1] if len(history) >= 8 else None
    return {
        "ticker": ticker, **current, "prev_close": previous["close"],
        "prev_volume": previous["volume"],
        "gain_pct": (close / previous["close"] - 1) * 100,
        "volume_vs_previous": _divide(current["volume"], previous["volume"]),
        "volume_vs_average": (_divide(current["volume"], _mean([b["volume"] for b in history[-21:-1]]))
                              if len(history) >= 21 else None),
        "range_expansion": range_expansion,
        "compression_ratio": compression,
        "close_position": _divide(close - current["low"], current["high"] - current["low"]),
        "prior_up_days": streak,
        "trend_intensity": (_mean([b["close"] for b in history[-7:]]) /
                            _mean([b["close"] for b in history[-65:]]) if len(history) >= 65 else None),
        "prior_bursts_20": (sum(_scan(history[at], history[at - 1])
                                for at in range(len(history) - 21, len(history) - 1))
                            if len(history) >= 22 else None),
        "base_down4_count": (sum(history[at]["close"] / history[at - 1]["close"] <= 0.96
                                 for at in range(len(history) - 8, len(history) - 1))
                             if len(history) >= 9 else None),
        "extension_sma20_pct": ((close / _mean([b["close"] for b in history[-20:]]) - 1) * 100
                                if len(history) >= 20 else None),
        "base_range_pct": ((max(b["high"] for b in base) - min(b["low"] for b in base)) /
                           previous["close"] * 100 if base else None),
        "prior_day_move_pct": ((previous["close"] / history[-3]["close"] - 1) * 100
                               if len(history) >= 3 else None),
        "prior_day_range_pct": normalized[-2] * 100,
        "series": history[-SERIES_LIMIT:],
    }


def _anticipates(row, history) -> bool:
    return (len(history) >= 67 and row["close"] >= 3
            and min(b["volume"] for b in history[-4:-1]) >= 100000
            and row["trend_intensity"] >= 1.05
            and 0.99 <= history[-1]["close"] / history[-2]["close"] <= 1.01
            and row["compression_ratio"] is not None and row["compression_ratio"] <= 0.75)


def build(frames: dict, session, *, requested: int, label: str,
          previous_session=None, calendar=None) -> dict | None:
    """Build optional research metadata without network or production-rule changes.

    Calendar dates are inferred from the basket, not an exchange calendar. The
    existing scanner decides the current prior session, including its holiday
    consensus. Historical holes reduce coverage instead of becoming two-day moves.
    """
    session = _day(session)
    if not frames or session is None:
        return None
    histories = {str(ticker): _bars(frame, session) for ticker, frame in frames.items()}
    if not any(histories.values()):
        return None
    printed = {day for history in histories.values() for day in history}
    supplied = {_day(day) for day in (calendar or [])}
    sessions = sorted(day for day in (supplied or printed) if day is not None and day <= session and day.weekday() < 5)
    if session not in sessions:
        sessions.append(session)
    prior = {}
    for day in sessions:
        arithmetic = _weekday_before(day)
        observed = [value for value in sessions if value < day]
        prior[day] = arithmetic if arithmetic in printed or not observed else observed[-1]
    current_previous = _day(previous_session)
    if current_previous is not None and current_previous < session:
        prior[session] = current_previous
    elif not calendar:
        prior[session] = _weekday_before(session)

    # Without cross-frame agreement, weekdays remain conservative: a lone name
    # cannot establish a closure using the very hole we are trying to detect.
    if not calendar:
        prior.update({day: _weekday_before(day) for day in sessions if day != session})
    scan_rows, anticipation_rows = [], []
    measured = 0
    for ticker, bars in histories.items():
        history, day = [], session
        while bars.get(day):
            history.append(bars[day])
            day = prior.get(day, _weekday_before(day))
        history.reverse()
        if len(history) < 2:
            continue
        measured += 1
        row = _row(ticker, history)
        if _scan(history[-1], history[-2]):
            scan_rows.append(row)
        elif _anticipates(row, history):
            anticipation_rows.append(row)
    scan_rows.sort(key=lambda row: (-row["gain_pct"], row["ticker"]))
    anticipation_rows.sort(key=lambda row: (row["compression_ratio"], -row["trend_intensity"], row["ticker"]))
    days = []
    for day in sessions[-10:]:
        pairs = [(bars[day], bars[prior[day]]) for bars in histories.values()
                 if bars.get(day) and bars.get(prior[day])]
        days.append({"date": day.isoformat(), "measured": len(pairs),
                     "up4": sum(_scan(bar, previous) for bar, previous in pairs),
                     "down4": sum(_scan(bar, previous, down=True) for bar, previous in pairs)})
    ratios = {}
    for window in (5, 10):
        rows = days[-window:]
        ratios[f"d{window}"] = (_divide(sum(day["up4"] for day in rows), sum(day["down4"] for day in rows))
                                  if len(rows) == window and all(day["measured"] > 0 for day in rows) else None)
    return {
        "version": 1, "date": session.isoformat(),
        "scope": {"label": label, "requested": requested, "measured": measured, "whole_market": False},
        "scan": {"matched": len(scan_rows), "shown": min(SCAN_LIMIT, len(scan_rows)), "rows": scan_rows[:SCAN_LIMIT]},
        "anticipation": {"matched": len(anticipation_rows), "shown": min(ANTICIPATION_LIMIT, len(anticipation_rows)),
                         "rows": anticipation_rows[:ANTICIPATION_LIMIT], "rules": dict(ANTICIPATION_RULES)},
        "breadth": {"days": days, "ratios": ratios},
        "measurement_rules": dict(MEASUREMENT_RULES),
    }


def problem(block, *, session=None, archived=False) -> str | None:
    """Validate the bounded optional metadata before a persisted record is read."""
    def number(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)

    def count(value):
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0

    if not isinstance(block, dict) or type(block.get("version")) is not int or block["version"] != 1:
        return "stockbee.version must be 1"
    day = _day(block.get("date"))
    if day is None or block["date"] != day.isoformat() or (session is not None and _day(session) != day):
        return "stockbee.date must match its run"
    scope = block.get("scope")
    if (not isinstance(scope, dict) or not isinstance(scope.get("label"), str)
            or scope.get("whole_market") is not False
            or not count(scope.get("requested")) or not count(scope.get("measured"))
            or scope["measured"] > scope["requested"]):
        return "stockbee.scope must identify the measured basket"
    for key, limit in (("scan", SCAN_LIMIT), ("anticipation", ANTICIPATION_LIMIT)):
        section = block.get(key)
        if (not isinstance(section, dict) or not isinstance(section.get("rows"), list)
                or not count(section.get("matched")) or not count(section.get("shown"))
                or section["shown"] != len(section["rows"]) or section["shown"] > limit
                or not section["shown"] <= section["matched"] <= scope["measured"]):
            return f"stockbee.{key} must contain bounded rows and matching counts"
        tickers = set()
        for row in section["rows"]:
            if (not isinstance(row, dict) or not isinstance(row.get("ticker"), str)
                    or not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]{0,14}", row["ticker"])
                    or row["ticker"] in tickers or row.get("date") != block["date"]):
                return f"stockbee.{key} row identity is invalid"
            tickers.add(row["ticker"])
            if any(value is not None and not number(value) for name, value in row.items()
                   if name not in ("ticker", "date", "series")):
                return f"stockbee.{key} row metrics must be numbers or null"
            values = {key: _number(row.get(key)) for key in FIELDS}
            previous = {"close": _number(row.get("prev_close")), "volume": _number(row.get("prev_volume"))}
            if (not _valid_bar(values) or previous["close"] is None or previous["close"] <= 0
                    or previous["volume"] is None or previous["volume"] < 0):
                return f"stockbee.{key} row has invalid OHLCV"
            if key == "scan" and not _scan(values, previous):
                return "stockbee.scan row does not meet the recorded scan"
            series = row.get("series")
            if series is None and archived:
                continue
            if not isinstance(series, list) or not 2 <= len(series) <= SERIES_LIMIT:
                return f"stockbee.{key} series must contain bounded daily bars"
            dates = []
            for bar in series:
                if not isinstance(bar, dict) or not _valid_bar({k: _number(bar.get(k)) for k in FIELDS}):
                    return f"stockbee.{key} series has invalid OHLCV"
                stamp = _day(bar.get("date"))
                if stamp is None or stamp > day:
                    return f"stockbee.{key} series has invalid dates"
                dates.append(stamp)
            if dates != sorted(set(dates)) or dates[-1] != day:
                return f"stockbee.{key} series must end on its recorded session"
    breadth = block.get("breadth")
    if not isinstance(breadth, dict) or not isinstance(breadth.get("days"), list) or len(breadth["days"]) > 10:
        return "stockbee.breadth must contain at most 10 dated counts"
    dates = []
    for row in breadth["days"]:
        if not isinstance(row, dict):
            return "stockbee.breadth day must be an object"
        stamp = _day(row.get("date"))
        if (stamp is None or stamp > day or any(not count(row.get(k)) for k in ("measured", "up4", "down4"))
                or row["up4"] + row["down4"] > row["measured"] or row["measured"] > scope["requested"]):
            return "stockbee.breadth day must contain measured counts"
        dates.append(stamp)
    if dates != sorted(set(dates)):
        return "stockbee.breadth days must be unique and ordered"
    ratios = breadth.get("ratios")
    if not isinstance(ratios, dict) or any(ratios.get(k) is not None and (not number(ratios[k]) or ratios[k] < 0) for k in ("d5", "d10")):
        return "stockbee.breadth ratios must be nonnegative numbers or null"
    if not isinstance(block["anticipation"].get("rules"), dict) or not isinstance(block.get("measurement_rules"), dict):
        return "stockbee measurement rules must be recorded"
    return None
