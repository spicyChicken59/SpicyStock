"""Bonde's Market Monitor: daily breadth counts, ratios and the regime gate.

Formulas are the Telechart v12.4 PCFs he publishes, in his notation: C is
today's close, C1 yesterday's, C20 the close twenty sessions ago, V and V1
the volumes, MINC65/MAXC65 the lowest/highest close over the last 65
sessions INCLUDING today, MINC34/MAXC34 likewise, AVGC20/AVGV20 the
20-session simple averages including today.

Sessions are the calendar ``observed_sessions()`` reads across the frames, so
every window counts sessions rather than bars: a symbol with a hole inside a
window is not measured for that column, never a shorter window under the
same name. A NaN or missing input makes a symbol "not measured" for the
columns that need it and nothing else; it is never a False that counts as a
healthy day.

The count thresholds (DOWN4_ALARM, UP50_MONTH_HOT, DOWN25_QUARTER_OVERSOLD)
are his readings over a ~6,500-name common-stock universe; ``regime()``
scales each by today's measured universe over REFERENCE_UNIVERSE and compares
the count to the scaled number it prints. The ratios are scale-free.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

# --- the breadth scans (Telechart v12.4) -----------------------------------
#: 100*(C-C1)/C1 >= 4 counts as up 4%; <= -4 as down 4%.
BURST_PCT = 4.0
#: V >= 100000 on both 4% scans (v7 used 1,000).
MIN_VOLUME = 100_000
#: AVGC20*AVGV20 >= 250000 on every quarter/month/34-day scan.
MIN_DOLLAR_VOLUME_20 = 250_000
#: C20, AVGC20, AVGV20.
MONTH_SESSIONS = 20
#: MINC65 / MAXC65.
QUARTER_SESSIONS = 65
#: MINC34 / MAXC34.
SESSIONS_34 = 34
#: T2108's moving average: the share of stocks closing above their 40-session SMA.
MA_SESSIONS = 40
#: C20 >= 5 on the month scans.
MIN_MONTH_PRICE = 5.0
QUARTER_MOVE_PCT = 25.0
MONTH_MOVE_PCT = 25.0
MONTH_BIG_MOVE_PCT = 50.0
MOVE_13_PCT = 13.0
#: The (C+.01) guard in the quarter and 34-day formulas.
PENNY = 0.01
# --- the primary indicator -------------------------------------------------
RATIO_SHORT_SESSIONS = 5
RATIO_LONG_SESSIONS = 10
# --- the regime gate (field guide, section (g)) ----------------------------
#: The universe Bonde's count thresholds are stated over (his Market Monitor
#: sheet reads 6,481-6,546 common stocks). Each count below is scaled by
#: today's measured universe over this before it is compared.
REFERENCE_UNIVERSE = 6500
#: "A series of days with 700+ stocks down 4% signals major deterioration."
DOWN4_ALARM = 700
#: More 4% breakdowns than breakouts over ten sessions (scale-free).
RED_RATIO_10D = 1.0
#: A fast selling phase: the 5-session ratio under this while today's
#: down-4% count exceeds its up-4% count (scale-free).
RED_RATIO_5D = 0.5
#: "A 10-day ratio below ~2 ... may not be an ideal time for swing longs."
YELLOW_RATIO_10D = 2.0
#: "Readings of the 50%-plus-month indicator above 20 = high bullishness /
#: likely pullback."
UP50_MONTH_HOT = 20
#: "Quarter counts below ~200 (down 25% in a quarter) mark oversold
#: extremes" -- informational, never a verdict input. The guide's wording;
#: not yet checked against Bonde's own.
DOWN25_QUARTER_OVERSOLD = 200
SIZE_MULTIPLIER = {"green": 1.0, "yellow": 0.5, "red": 0.0}
# --- plumbing --------------------------------------------------------------
#: How many sessions snapshot() carries in ``history``.
HISTORY_SESSIONS = 30
#: A date is a session when at least this fraction of frames carry a bar on it.
MIN_SESSION_FRACTION = 0.5
#: Ratios and pct_above_40ma are rounded ONCE, here, and every comparison
#: reads the rounded number a surface prints.
RATIO_DECIMALS = 2
PCT_DECIMALS = 1
#: A scaled count threshold is rounded ONCE, here, and compared as printed.
THRESHOLD_DECIMALS = 1

#: Which numbers decide what a count or a verdict IS (archived in ``RULES``)
#: and which only shape the output. A test holds every upper-case numeric
#: constant in this module to exactly one list.
STRATEGY_CONSTANTS = (
    "BURST_PCT", "MIN_VOLUME", "MIN_DOLLAR_VOLUME_20", "MONTH_SESSIONS",
    "QUARTER_SESSIONS", "SESSIONS_34", "MA_SESSIONS", "MIN_MONTH_PRICE",
    "QUARTER_MOVE_PCT", "MONTH_MOVE_PCT", "MONTH_BIG_MOVE_PCT", "MOVE_13_PCT",
    "PENNY", "RATIO_SHORT_SESSIONS", "RATIO_LONG_SESSIONS", "REFERENCE_UNIVERSE",
    "DOWN4_ALARM", "RED_RATIO_10D", "RED_RATIO_5D", "YELLOW_RATIO_10D",
    "UP50_MONTH_HOT", "DOWN25_QUARTER_OVERSOLD",
)
PLUMBING_CONSTANTS = ("HISTORY_SESSIONS", "MIN_SESSION_FRACTION",
                      "RATIO_DECIMALS", "PCT_DECIMALS", "THRESHOLD_DECIMALS")
#: The strategy numbers, keyed by their lower-case names, for data.json.
RULES = {name.lower(): globals()[name] for name in STRATEGY_CONSTANTS}
RULES["size_multiplier"] = dict(SIZE_MULTIPLIER)

VERDICTS = ("green", "yellow", "red")


@dataclass
class BreadthDay:
    """One session's Market Monitor counts; ``universe`` is how many symbols
    were measurable for up4/down4 (valid C, C1, V, V1)."""

    date: date
    up4: int
    down4: int
    up25_quarter: int
    down25_quarter: int
    up25_month: int
    down25_month: int
    up50_month: int
    down50_month: int
    up13_34d: int
    down13_34d: int
    pct_above_40ma: float | None
    universe: int

    def to_dict(self) -> dict:
        """JSON-ready copy, the date as ISO text."""
        block = asdict(self)
        block["date"] = self.date.isoformat()
        return block


# ----------------------------------------------------------- calendar ----


def _bar_dates(index) -> np.ndarray:
    """A frame's bar dates as datetime64[D] (wall-clock date, the way
    Timestamp.date() reads them); NaT stays NaT."""
    idx = index if isinstance(index, pd.DatetimeIndex) else pd.DatetimeIndex(index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    return idx.to_numpy().astype("datetime64[D]")


def observed_sessions(frames: Mapping[str, pd.DataFrame],
                      min_fraction: float = MIN_SESSION_FRACTION) -> list[date]:
    """Dates at least ``min_fraction`` of the frames carry a bar on, oldest
    first. A date one frame prints on (a phantom, a holiday) is not a session."""
    if not 0 < min_fraction <= 1:
        raise ValueError(f"min_fraction must be in (0, 1], got {min_fraction}")
    if not frames:
        return []
    stamped = [np.unique(_bar_dates(df.index)) for df in frames.values()]
    stamps = np.concatenate(stamped)
    stamps = stamps[~np.isnat(stamps)]
    dates, counts = np.unique(stamps, return_counts=True)
    kept = dates[counts >= min_fraction * len(frames)]
    return kept.astype(object).tolist()


# --------------------------------------------------------- wide matrix ----


def _column(df: pd.DataFrame, name: str) -> np.ndarray:
    series = df[name]
    if series.dtype == "float64":
        return series.to_numpy()
    return series.to_numpy(dtype="float64", na_value=np.nan)


def _wide(frames: Mapping[str, pd.DataFrame],
          calendar: Sequence[date]) -> tuple[np.ndarray, np.ndarray]:
    """Close and volume matrices, sessions x symbols, built once.

    NaN where a symbol has no bar on a session, where a value is missing or
    not finite, where a close is not positive or a volume negative. A bar on
    a date that is not a session is dropped.
    """
    cal = np.array(list(calendar), dtype="datetime64[D]").astype("int64")
    n, m = len(cal), len(frames)
    closes = np.full((n, m), np.nan)
    volumes = np.full((n, m), np.nan)
    if n == 0:
        return closes, volumes
    for j, df in enumerate(frames.values()):
        stamps = _bar_dates(df.index).astype("int64")
        pos = np.minimum(np.searchsorted(cal, stamps), n - 1)
        keep = cal[pos] == stamps
        if not keep.any():
            continue
        rows = pos[keep]
        closes[rows, j] = _column(df, "Close")[keep]
        volumes[rows, j] = _column(df, "Volume")[keep]
    closes = np.where(np.isfinite(closes) & (closes > 0), closes, np.nan)
    volumes = np.where(np.isfinite(volumes) & (volumes >= 0), volumes, np.nan)
    return closes, volumes


def _lag(values: np.ndarray, sessions: int) -> np.ndarray:
    """The value ``sessions`` rows earlier; NaN where there is none."""
    out = np.full(values.shape, np.nan)
    if sessions < values.shape[0]:
        out[sessions:] = values[:-sessions]
    return out


def _trailing(values: np.ndarray, window: int,
              reduce: Callable[..., np.ndarray]) -> np.ndarray:
    """``reduce`` over the last ``window`` rows including the current one.

    NaN until a full window exists and wherever the window holds a NaN, so a
    hole is "not measured" rather than a shorter window.
    """
    out = np.full(values.shape, np.nan)
    if values.shape[0] >= window:
        view = sliding_window_view(values, window, axis=0)
        out[window - 1:] = reduce(view, axis=-1)
    return out


# ------------------------------------------------------------ measure ----


def _measure(closes: np.ndarray, volumes: np.ndarray) -> dict[str, np.ndarray]:
    """Every column for every session of the matrix, as per-session totals."""
    c, v = closes, volumes
    c1, v1 = _lag(c, 1), _lag(v, 1)
    c20 = _lag(c, MONTH_SESSIONS)
    minc65 = _trailing(c, QUARTER_SESSIONS, np.min)
    maxc65 = _trailing(c, QUARTER_SESSIONS, np.max)
    minc34 = _trailing(c, SESSIONS_34, np.min)
    maxc34 = _trailing(c, SESSIONS_34, np.max)
    avgc20 = _trailing(c, MONTH_SESSIONS, np.mean)
    avgv20 = _trailing(v, MONTH_SESSIONS, np.mean)
    avgc40 = _trailing(c, MA_SESSIONS, np.mean)

    finite = np.isfinite
    with np.errstate(divide="ignore", invalid="ignore"):
        measured_4 = finite(c) & finite(c1) & finite(v) & finite(v1)
        change = 100.0 * (c - c1) / c1
        volume_ok = (v >= MIN_VOLUME) & (v > v1)
        up4 = measured_4 & (change >= BURST_PCT) & volume_ok
        down4 = measured_4 & (change <= -BURST_PCT) & volume_ok

        liquid = finite(avgc20) & finite(avgv20) & (avgc20 * avgv20 >= MIN_DOLLAR_VOLUME_20)

        quarter = finite(c) & finite(minc65) & finite(maxc65) & liquid
        up_q = 100.0 * ((c + PENNY) - (minc65 + PENNY)) / (minc65 + PENNY)
        down_q = 100.0 * ((c + PENNY) - (maxc65 + PENNY)) / (maxc65 + PENNY)
        up25_quarter = quarter & (up_q >= QUARTER_MOVE_PCT)
        down25_quarter = quarter & (down_q <= -QUARTER_MOVE_PCT)

        month = finite(c) & finite(c20) & liquid & (c20 >= MIN_MONTH_PRICE)
        move_m = 100.0 * (c - c20) / c20
        up25_month = month & (move_m >= MONTH_MOVE_PCT)
        down25_month = month & (move_m <= -MONTH_MOVE_PCT)
        up50_month = month & (move_m >= MONTH_BIG_MOVE_PCT)
        down50_month = month & (move_m <= -MONTH_BIG_MOVE_PCT)

        d34 = finite(c) & finite(minc34) & finite(maxc34) & liquid
        up_34 = 100.0 * ((c + PENNY) - (minc34 + PENNY)) / (minc34 + PENNY)
        down_34 = 100.0 * ((c + PENNY) - (maxc34 + PENNY)) / (maxc34 + PENNY)
        up13_34d = d34 & (up_34 >= MOVE_13_PCT)
        down13_34d = d34 & (down_34 <= -MOVE_13_PCT)

        ma_measured = finite(c) & finite(avgc40)
        above_ma = ma_measured & (c > avgc40)

    count = lambda flags: flags.sum(axis=1).astype(int)  # noqa: E731
    return {
        "up4": count(up4), "down4": count(down4),
        "up25_quarter": count(up25_quarter), "down25_quarter": count(down25_quarter),
        "up25_month": count(up25_month), "down25_month": count(down25_month),
        "up50_month": count(up50_month), "down50_month": count(down50_month),
        "up13_34d": count(up13_34d), "down13_34d": count(down13_34d),
        "above_ma": count(above_ma), "ma_measured": count(ma_measured),
        "universe": count(measured_4),
    }


def daily_counts(frames: Mapping[str, pd.DataFrame], sessions: Sequence[date],
                 *, min_fraction: float = MIN_SESSION_FRACTION) -> list[BreadthDay]:
    """The Market Monitor columns for each of ``sessions``, in that order.

    The matrix spans every observed session so the windows behind a requested
    session are there; a session the calendar does not hold is refused.
    """
    sessions = list(sessions)
    if not sessions:
        return []
    calendar = observed_sessions(frames, min_fraction)
    position = {day: i for i, day in enumerate(calendar)}
    missing = [day for day in sessions if day not in position]
    if missing:
        raise ValueError(f"not a session the frames carry: {missing[0].isoformat()}")
    closes, volumes = _wide(frames, calendar)
    table = _measure(closes, volumes)
    days = []
    for day in sessions:
        i = position[day]
        measured = int(table["ma_measured"][i])
        pct = (round(100.0 * int(table["above_ma"][i]) / measured, PCT_DECIMALS)
               if measured else None)
        days.append(BreadthDay(
            date=day,
            up4=int(table["up4"][i]), down4=int(table["down4"][i]),
            up25_quarter=int(table["up25_quarter"][i]),
            down25_quarter=int(table["down25_quarter"][i]),
            up25_month=int(table["up25_month"][i]),
            down25_month=int(table["down25_month"][i]),
            up50_month=int(table["up50_month"][i]),
            down50_month=int(table["down50_month"][i]),
            up13_34d=int(table["up13_34d"][i]),
            down13_34d=int(table["down13_34d"][i]),
            pct_above_40ma=pct,
            universe=int(table["universe"][i]),
        ))
    return days


# ------------------------------------------------------------- ratios ----


def ratios(days: Sequence[BreadthDay], window: int) -> tuple[int, int, float | None]:
    """(sum of up4, sum of down4, up/down) over the last ``window`` days,
    oldest first; the ratio is None when nothing broke down. Fewer days than
    the window is refused rather than read as a shorter window."""
    if window < 1:
        raise ValueError(f"window must be at least 1, got {window}")
    if len(days) < window:
        raise ValueError(f"a {window}-session ratio needs {window} days, got {len(days)}")
    tail = days[-window:]
    up = sum(day.up4 for day in tail)
    down = sum(day.down4 for day in tail)
    ratio = None if down == 0 else round(up / down, RATIO_DECIMALS)
    return up, down, ratio


# ------------------------------------------------------------- regime ----


def scaled_threshold(reference: float, universe: int) -> float:
    """Bonde's count over REFERENCE_UNIVERSE names, scaled to the names
    measured today and rounded once; the comparison reads this number."""
    if universe < 0:
        raise ValueError(f"universe must be non-negative, got {universe}")
    return round(reference * universe / REFERENCE_UNIVERSE, THRESHOLD_DECIMALS)


def _ratio_words(label: str, up: int, down: int, ratio: float | None) -> str:
    if ratio is None:
        return f"{label} undefined ({up} up, {down} down)"
    return f"{label} {ratio} ({up} up, {down} down)"


def regime(days: Sequence[BreadthDay]) -> dict:
    """The verdict for the newest day, its size multiplier, and why.

    RED on any of: today's down-4% count at or over the scaled DOWN4_ALARM;
    the 10-session ratio under RED_RATIO_10D; the 5-session ratio under
    RED_RATIO_5D while today's down-4% count exceeds its up-4% count. YELLOW
    on the 10-session ratio under YELLOW_RATIO_10D or the 50%-in-a-month
    count over the scaled UP50_MONTH_HOT. GREEN otherwise. Count thresholds
    are scaled by today's ``universe`` over REFERENCE_UNIVERSE; ratios are
    not. ``reasons`` name the value and the threshold of every rule that
    fired, or of every rule cleared on green; ``thresholds`` carries the
    scaled numbers the page prints.
    """
    if not days:
        raise ValueError("regime needs at least one breadth day")
    today = days[-1]
    if today.universe == 0:
        raise ValueError(f"no symbol was measurable on {today.date.isoformat()}")
    up10, down10, r10 = ratios(days, RATIO_LONG_SESSIONS)
    up5, down5, r5 = ratios(days, RATIO_SHORT_SESSIONS)
    long_words = _ratio_words(f"{RATIO_LONG_SESSIONS}-session ratio", up10, down10, r10)
    short_words = _ratio_words(f"{RATIO_SHORT_SESSIONS}-session ratio", up5, down5, r5)
    alarm = scaled_threshold(DOWN4_ALARM, today.universe)
    hot = scaled_threshold(UP50_MONTH_HOT, today.universe)
    oversold = scaled_threshold(DOWN25_QUARTER_OVERSOLD, today.universe)
    of = f"of {REFERENCE_UNIVERSE:,}"

    rules: list[tuple[str, bool, str]] = []

    fired = today.down4 >= alarm
    rules.append(("red", fired,
                  f"down 4%: {today.down4} {'>=' if fired else '<'} the scaled alarm of "
                  f"{alarm:g} ({DOWN4_ALARM} {of})"
                  + (": major deterioration" if fired else "")))

    fired = r10 is not None and r10 < RED_RATIO_10D
    if fired:
        sentence = f"{long_words} < {RED_RATIO_10D}: more breakdowns than breakouts"
    elif r10 is None:
        sentence = long_words
    else:
        sentence = f"{long_words} >= {RED_RATIO_10D}"
    rules.append(("red", fired, sentence))

    selling = today.down4 > today.up4
    fired = r5 is not None and r5 < RED_RATIO_5D and selling
    if fired:
        sentence = (f"{short_words} < {RED_RATIO_5D} with {today.down4} down vs "
                    f"{today.up4} up today: a fast selling phase")
    elif r5 is None:
        sentence = short_words
    elif r5 < RED_RATIO_5D:
        sentence = (f"{short_words} < {RED_RATIO_5D} but {today.up4} up vs "
                    f"{today.down4} down today")
    else:
        sentence = f"{short_words} >= {RED_RATIO_5D}"
    rules.append(("red", fired, sentence))

    fired = r10 is not None and r10 < YELLOW_RATIO_10D
    if fired:
        sentence = f"{long_words} < {YELLOW_RATIO_10D}: not an ideal time for swing longs"
    elif r10 is None:
        sentence = long_words
    else:
        sentence = f"{long_words} >= {YELLOW_RATIO_10D}"
    rules.append(("yellow", fired, sentence))

    fired = today.up50_month > hot
    rules.append(("yellow", fired,
                  f"up 50% in a month: {today.up50_month} {'>' if fired else '<='} the scaled "
                  f"hot mark of {hot:g} ({UP50_MONTH_HOT} {of})"
                  + (": high bullishness, a pullback is likely" if fired else "")))

    red = [s for tier, fired, s in rules if tier == "red" and fired]
    yellow = [s for tier, fired, s in rules if tier == "yellow" and fired]
    if red:
        verdict, reasons = "red", red
    elif yellow:
        verdict, reasons = "yellow", yellow
    else:
        verdict, reasons = "green", list(dict.fromkeys(s for _, _, s in rules))

    return {
        "verdict": verdict,
        "size_multiplier": SIZE_MULTIPLIER[verdict],
        "reasons": reasons,
        "oversold_extreme": today.down25_quarter < oversold,
        "thresholds": {
            "universe": today.universe,
            "reference_universe": REFERENCE_UNIVERSE,
            "down4_alarm": alarm,
            "up50_month_hot": hot,
            "down25_quarter_oversold": oversold,
            "ratio_10d_red": RED_RATIO_10D,
            "ratio_5d_red": RED_RATIO_5D,
            "ratio_10d_yellow": YELLOW_RATIO_10D,
        },
        "inputs": {
            "date": today.date.isoformat(),
            "ratio_10d": r10, "ratio_5d": r5,
            "up4_10d": up10, "down4_10d": down10,
            "up4_5d": up5, "down4_5d": down5,
            "up4": today.up4, "down4": today.down4,
            "up50_month": today.up50_month,
            "down25_quarter": today.down25_quarter,
        },
    }


# ----------------------------------------------------------- snapshot ----


def snapshot(frames: Mapping[str, pd.DataFrame], session: date,
             history_sessions: int = HISTORY_SESSIONS) -> dict:
    """The ``breadth`` block data.json carries for ``session``: today's
    columns, both ratios with their sums, the regime, the rules, and
    ``history`` -- the last ``history_sessions`` days that have a full
    10-session window, oldest first. ``start`` is the one bound on the
    history's length: the days handed to daily_counts() are exactly the
    history plus the window the first history day needs."""
    if history_sessions < 1:
        raise ValueError(f"history_sessions must be at least 1, got {history_sessions}")
    calendar = observed_sessions(frames)
    if session not in calendar:
        raise ValueError(f"not a session the frames carry: {session.isoformat()}")
    end = calendar.index(session) + 1
    start = max(0, end - (history_sessions + RATIO_LONG_SESSIONS - 1))
    days = daily_counts(frames, calendar[start:end])
    today = days[-1]
    up5, down5, r5 = ratios(days, RATIO_SHORT_SESSIONS)
    up10, down10, r10 = ratios(days, RATIO_LONG_SESSIONS)
    history = []
    for i in range(RATIO_LONG_SESSIONS - 1, len(days)):
        _, _, ratio = ratios(days[:i + 1], RATIO_LONG_SESSIONS)
        history.append({"date": days[i].date.isoformat(), "up4": days[i].up4,
                        "down4": days[i].down4, "ratio_10d": ratio})
    block = today.to_dict()
    block.update({
        "ratio_5d": r5, "ratio_10d": r10,
        "up4_5d": up5, "down4_5d": down5,
        "up4_10d": up10, "down4_10d": down10,
        "regime": regime(days),
        "history": history,
        "rules": {k: (dict(v) if isinstance(v, dict) else v) for k, v in RULES.items()},
    })
    return block
