"""Bonde's published scans as pure functions over one symbol's daily frame.

Every scan takes a frame (DatetimeIndex oldest first, one bar per session,
Open/High/Low/Close/Volume) and ``at``, the positional index of the session
being judged, and returns None -- not a match, or not measurable -- or a dict
of the values it measured, for the caller to archive and render. A value that
cannot be read (NaN, a missing bar, fewer sessions than the window needs)
makes the scan None, never a false match.

The formulas are quoted in Telechart's notation: c/c1/c2 are the closes today,
one and two sessions ago; o is today's open; v/v1 today's and yesterday's
volume; minl252 the lowest LOW over the 252 sessions ending today; minv3.1 the
lowest volume over the 3 sessions ending YESTERDAY; avgc7/avgc65/avgc126 simple
averages of the close ending today; avgv50.1 the 50-session average volume
ending yesterday. Windows are counted in bars. A hole in the index is not
detected here: whether the bar before ``at`` is the previous session is the
transport's stale/gap check, which needs a calendar this module does not carry.

ONE NUMBER PER MEASUREMENT. Prices are read to the cent and volumes to the
share, ratios are rounded to RATIO_DECIMALS and percentages to PCT_DECIMALS,
once, and every rule decides on the number the dict carries -- so a bar the
record prints at 4.0% is never one the scan refused at 3.996%. The dollar move
is the worked example: 23.90 - 23.00 is 0.8999999999999986 in binary, and an
unrounded compare refuses a ninety-cent body beside an archived $0.90.

Strict and inclusive comparisons are kept exactly as Bonde writes them, and
RULES says which is which: a ``min_``/``max_`` key is inclusive unless its
name ends in ``_exclusive``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# 4% breakout: c/c1 >= 1.04 and v > v1 and v >= 100000. Bonde's momentum
# burst scan, the 2015 100,000-share version; the mirror is the breakdown the
# breadth counts and the quality checks read.
BURST_RATIO = 1.04
BREAKDOWN_RATIO = 0.96
# The one liquidity floor every scan below shares, in shares.
MIN_VOLUME = 100_000
# $ breakout: c - o >= 0.90 and v > 100000. Close minus OPEN -- the day's own
# body, so the overnight gap is excluded -- and absolute, so a $4 day on a
# $200 stock is 2%. The community TradingView variant measures c - c1 and
# requires the close within 30% of the high; this is Bonde's.
DOLLAR_MOVE = 0.90
# Double Trouble: c/minl252 >= 1.8 and minv3.1 >= 100000, read with the
# +-1% quiet-day filter for anticipation.
DT_RATIO = 1.8
# Trend Intensity: avgc7/avgc65 > 1.05 and minv3.1 > 100000.
TI65_RATIO = 1.05
# Modified Double Trouble: c/avgc126 > 1.19 and minv3.1 > 100000.
MDT_RATIO = 1.19
# The quiet day: 100*(c/c1 - 1) between -1 and 1, inclusive.
QUIET_PCT = 1.0
# The $3 floor the EP 9M and the TI65 low-risk entry both carry.
MIN_PRICE = 3.0
# TI65 low-risk entry: the session before must not itself have run: c1/c2 < 1.02.
LRE_MAX_PRIOR_RATIO = 1.02
# Episodic pivot: c/c1 > 1.04 and v > 3*avgv50.1 and v >= 300000. The same
# 1.04 as the burst, but Bonde writes this one strict, so it is its own number.
EP_RATIO = 1.04
EP_VOLUME_MULT = 3
EP_MIN_VOLUME = 300_000
# EP "9 million": v >= 9,000,000 and c >= 3.
EP9M_MIN_VOLUME = 9_000_000
# Windows, in sessions.
LOW_LOOKBACK = 252
PRIOR_VOLUME_SESSIONS = 3
TI_SHORT_SESSIONS = 7
TI_LONG_SESSIONS = 65
MDT_SESSIONS = 126
EP_VOLUME_SESSIONS = 50
# Anticipation's "series of narrow range days": how many of the last
# NARROW_LOOKBACK sessions range less than the median range of the
# RANGE_NORM_SESSIONS before them. A stated proxy, not a rule of Bonde's.
NARROW_LOOKBACK = 7
RANGE_NORM_SESSIONS = 20
# Precision. Ratios at four places are percentages at two -- one grid, so the
# archived gain and the archived ratio are one number in two units.
RATIO_DECIMALS = 4
PCT_DECIMALS = 2
CENTS = 2

#: The archived constants. Every upper-case number this module names is read
#: here (a test derives that from the source), so a threshold added later
#: cannot escape the record in silence.
RULES = {
    "burst.min_ratio": BURST_RATIO,
    "burst.volume_above_prior": True,
    "burst.min_volume": MIN_VOLUME,
    "breakdown.max_ratio": BREAKDOWN_RATIO,
    "breakdown.volume_above_prior": True,
    "breakdown.min_volume": MIN_VOLUME,
    "dollar.min_move": DOLLAR_MOVE,
    "dollar.min_volume_exclusive": MIN_VOLUME,
    "dt.min_ratio": DT_RATIO,
    "dt.low_sessions": LOW_LOOKBACK,
    "dt.min_prior_volume": MIN_VOLUME,
    "ti65.min_ratio_exclusive": TI65_RATIO,
    "ti65.short_sessions": TI_SHORT_SESSIONS,
    "ti65.long_sessions": TI_LONG_SESSIONS,
    "ti65.min_prior_volume_exclusive": MIN_VOLUME,
    "mdt.min_ratio_exclusive": MDT_RATIO,
    "mdt.avg_sessions": MDT_SESSIONS,
    "mdt.min_prior_volume_exclusive": MIN_VOLUME,
    "quiet.max_abs_pct": QUIET_PCT,
    "prior_volume.sessions": PRIOR_VOLUME_SESSIONS,
    "lre.min_prior_volume": MIN_VOLUME,
    "lre.min_price": MIN_PRICE,
    "lre.min_ti65": TI65_RATIO,
    "lre.max_prior_ratio_exclusive": LRE_MAX_PRIOR_RATIO,
    "ep.min_ratio_exclusive": EP_RATIO,
    "ep.volume_mult_exclusive": EP_VOLUME_MULT,
    "ep.avg_volume_sessions": EP_VOLUME_SESSIONS,
    "ep.min_volume": EP_MIN_VOLUME,
    "ep_9m.min_volume": EP9M_MIN_VOLUME,
    "ep_9m.min_price": MIN_PRICE,
    "anticipation.narrow_lookback": NARROW_LOOKBACK,
    "anticipation.range_norm_sessions": RANGE_NORM_SESSIONS,
    "precision.ratio_decimals": RATIO_DECIMALS,
    "precision.pct_decimals": PCT_DECIMALS,
    "precision.price_decimals": CENTS,
}

COLUMNS = ("Open", "High", "Low", "Close", "Volume")
SCAN_KEYS = ("burst", "dollar", "anticipation", "ep", "ep_9m")
SETUP_LABELS = {"dt": "DT", "ti65": "TI65", "mdt": "MDT"}
_PRICES = ("Open", "High", "Low", "Close")


class _Bars:
    """One frame read once: cent prices, whole-share volumes, NaN where unreadable."""

    __slots__ = ("_values", "pos")

    def __init__(self, values: dict[str, np.ndarray], pos: int) -> None:
        self._values = values
        self.pos = pos

    def value(self, column: str, back: int = 0) -> float | None:
        """The column ``back`` sessions before the judged one, or None."""
        window = self.window(column, 1, back)
        return None if window is None else float(window[0])

    def window(self, column: str, sessions: int, back: int = 0) -> np.ndarray | None:
        """``sessions`` values ending ``back`` sessions before the judged one.

        None unless every value is readable: positive for a price, non-negative
        for a volume. A NaN -- which is what _bars() made of every non-finite or
        non-numeric value -- fails either comparison, so nothing else is checked.
        """
        stop = self.pos - back
        start = stop - sessions + 1
        if start < 0:
            return None
        window = self._values[column][start:stop + 1]
        readable = (window > 0).all() if column in _PRICES else (window >= 0).all()
        return window if readable else None


def _bars(df: pd.DataFrame, at: int) -> _Bars | None:
    if not isinstance(df, pd.DataFrame) or len(df) == 0:
        return None
    if isinstance(at, bool) or not isinstance(at, (int, np.integer)):
        return None
    pos = int(at) if at >= 0 else len(df) + int(at)
    if not 0 <= pos < len(df):
        return None
    values = {}
    for column in COLUMNS:
        if column not in df.columns or not isinstance(df[column], pd.Series):
            return None
        try:
            numbers = pd.to_numeric(df[column], errors="coerce").to_numpy(dtype=float, na_value=np.nan)
        except (TypeError, ValueError):
            return None
        numbers = np.where(np.isfinite(numbers), numbers, np.nan)
        values[column] = np.round(numbers, CENTS if column in _PRICES else 0)
    return _Bars(values, pos)


def _ratio(top: float | None, bottom: float | None) -> float | None:
    if top is None or bottom is None or bottom <= 0:
        return None
    return float(round(top / bottom, RATIO_DECIMALS))


def _pct(ratio: float | None) -> float | None:
    return None if ratio is None else float(round((ratio - 1) * 100, PCT_DECIMALS))


def _day_change(b: _Bars) -> tuple[float | None, bool | None]:
    """Today's close-to-close change in percent, and whether it is a quiet day."""
    pct = _pct(_ratio(b.value("Close"), b.value("Close", 1)))
    return pct, (None if pct is None else abs(pct) <= QUIET_PCT)


def _prior_min_volume(b: _Bars) -> float | None:
    """minv3.1: the lowest volume of the sessions ending yesterday."""
    window = b.window("Volume", PRIOR_VOLUME_SESSIONS, back=1)
    return None if window is None else float(window.min())


def _ti65(b: _Bars) -> float | None:
    short = b.window("Close", TI_SHORT_SESSIONS)
    slow = b.window("Close", TI_LONG_SESSIONS)
    if short is None or slow is None:
        return None
    return _ratio(float(short.mean()), float(slow.mean()))


def _close_position(c: float, high: float | None, low: float | None) -> float | None:
    """Where the close sits in the day's range, 0..1; None for no range or a bad bar."""
    if high is None or low is None or high <= low or not low <= c <= high:
        return None
    return float(round((c - low) / (high - low), RATIO_DECIMALS))


def _range_pcts(b: _Bars, sessions: int) -> np.ndarray | None:
    highs, lows, closes = (b.window(column, sessions) for column in ("High", "Low", "Close"))
    if highs is None or lows is None or closes is None or (highs < lows).any():
        return None
    return np.round(100 * (highs - lows) / closes, PCT_DECIMALS)


def _narrow_range_days(b: _Bars) -> int | None:
    ranges = _range_pcts(b, NARROW_LOOKBACK + RANGE_NORM_SESSIONS)
    if ranges is None:
        return None
    norm = float(np.median(ranges[:RANGE_NORM_SESSIONS]))
    return int((ranges[RANGE_NORM_SESSIONS:] < norm).sum())


def _close_to_close(b: _Bars, *, down: bool) -> dict | None:
    c, c1 = b.value("Close"), b.value("Close", 1)
    v, v1 = b.value("Volume"), b.value("Volume", 1)
    ratio = _ratio(c, c1)
    if ratio is None or v is None or v1 is None:
        return None
    moved = ratio <= BREAKDOWN_RATIO if down else ratio >= BURST_RATIO
    if not (moved and v > v1 and v >= MIN_VOLUME):
        return None
    return {
        "gain_pct": _pct(ratio),
        "close": c,
        "prev_close": c1,
        "volume": int(v),
        "prev_volume": int(v1),
        "volume_vs_prior": _ratio(v, v1),
        "dollar_volume": int(round(c * v)),
    }


def _burst(b: _Bars) -> dict | None:
    return _close_to_close(b, down=False)


def _breakdown(b: _Bars) -> dict | None:
    return _close_to_close(b, down=True)


def _dollar(b: _Bars) -> dict | None:
    c, o, v = b.value("Close"), b.value("Open"), b.value("Volume")
    if c is None or o is None or v is None:
        return None
    move = float(round(c - o, CENTS))
    if not (move >= DOLLAR_MOVE and v > MIN_VOLUME):
        return None
    return {
        "move": move,
        "close": c,
        "open": o,
        "volume": int(v),
        "close_pos_in_range": _close_position(c, b.value("High"), b.value("Low")),
    }


def _dt(b: _Bars) -> dict | None:
    lows = b.window("Low", LOW_LOOKBACK)
    prior_volume = _prior_min_volume(b)
    pct, quiet = _day_change(b)
    if lows is None or prior_volume is None or pct is None:
        return None
    min_low = float(lows.min())
    ratio = _ratio(b.value("Close"), min_low)
    if ratio is None or not (ratio >= DT_RATIO and prior_volume >= MIN_VOLUME):
        return None
    return {"ratio": ratio, "min_low": min_low, "min_volume_prior": int(prior_volume),
            "quiet": quiet, "pct_change_today": pct}


def _trend_intensity(b: _Bars) -> dict | None:
    ti65 = _ti65(b)
    prior_volume = _prior_min_volume(b)
    pct, quiet = _day_change(b)
    if ti65 is None or prior_volume is None or pct is None:
        return None
    if not (ti65 > TI65_RATIO and prior_volume > MIN_VOLUME):
        return None
    return {"ti65": ti65, "min_volume_prior": int(prior_volume), "quiet": quiet,
            "pct_change_today": pct}


def _mdt(b: _Bars) -> dict | None:
    closes = b.window("Close", MDT_SESSIONS)
    prior_volume = _prior_min_volume(b)
    pct, quiet = _day_change(b)
    if closes is None or prior_volume is None or pct is None:
        return None
    ratio = _ratio(b.value("Close"), float(closes.mean()))
    if ratio is None or not (ratio > MDT_RATIO and prior_volume > MIN_VOLUME):
        return None
    return {"ratio": ratio, "min_volume_prior": int(prior_volume), "quiet": quiet,
            "pct_change_today": pct}


def _low_risk_entry(b: _Bars) -> dict | None:
    c, c1, c2, o = (b.value("Close"), b.value("Close", 1), b.value("Close", 2), b.value("Open"))
    prior_volume = _prior_min_volume(b)
    ti65 = _ti65(b)
    today, prior = _ratio(c, c1), _ratio(c1, c2)
    if None in (o, prior_volume, ti65, today, prior):
        return None
    if not (prior_volume >= MIN_VOLUME and c >= MIN_PRICE and ti65 >= TI65_RATIO
            and c > o and c > c1 and today > prior and prior < LRE_MAX_PRIOR_RATIO):
        return None
    return {"ti65": ti65, "close": c, "open": o, "prev_close": c1,
            "pct_change_today": _pct(today), "prior_pct_change": _pct(prior),
            "min_volume_prior": int(prior_volume)}


def _ep(b: _Bars) -> dict | None:
    c, c1, v = b.value("Close"), b.value("Close", 1), b.value("Volume")
    prior = b.window("Volume", EP_VOLUME_SESSIONS, back=1)
    ratio = _ratio(c, c1)
    if ratio is None or v is None or prior is None:
        return None
    vs_avg = _ratio(v, float(prior.mean()))
    if vs_avg is None or not (ratio > EP_RATIO and vs_avg > EP_VOLUME_MULT and v >= EP_MIN_VOLUME):
        return None
    return {"gain_pct": _pct(ratio), "close": c, "prev_close": c1, "volume": int(v),
            "volume_vs_avg": vs_avg}


def _ep_9m(b: _Bars) -> dict | None:
    c, v = b.value("Close"), b.value("Volume")
    if c is None or v is None or not (v >= EP9M_MIN_VOLUME and c >= MIN_PRICE):
        return None
    return {"volume": int(v), "close": c}


def _anticipation(b: _Bars) -> dict | None:
    pct, quiet = _day_change(b)
    if not quiet:
        return None
    matches = {"dt": _dt(b), "ti65": _trend_intensity(b), "mdt": _mdt(b)}
    setups = [SETUP_LABELS[key] for key, match in matches.items() if match is not None]
    if not setups:
        return None
    today = _range_pcts(b, 1)
    return {"setups": setups, **matches, "pct_change_today": pct,
            "narrow_range_days": _narrow_range_days(b),
            "range_pct_today": None if today is None else float(today[0])}


# ------------------------------------------------------------ public API ----


def pct_change(df: pd.DataFrame, at: int = -1) -> float | None:
    """100 * (c/c1 - 1), rounded once; None when either close is unreadable."""
    b = _bars(df, at)
    return None if b is None else _day_change(b)[0]


def quiet_day(df: pd.DataFrame, at: int = -1) -> bool | None:
    """Bonde's anticipation filter: the day's change within +-QUIET_PCT, inclusive."""
    b = _bars(df, at)
    return None if b is None else _day_change(b)[1]


def burst_4pct(df: pd.DataFrame, at: int = -1) -> dict | None:
    """c/c1 >= 1.04 and v > v1 and v >= 100000: the momentum burst scan."""
    b = _bars(df, at)
    return None if b is None else _burst(b)


def breakdown_4pct(df: pd.DataFrame, at: int = -1) -> dict | None:
    """c/c1 <= 0.96 and v > v1 and v >= 100000: the burst's mirror, one definition."""
    b = _bars(df, at)
    return None if b is None else _breakdown(b)


def dollar_breakout(df: pd.DataFrame, at: int = -1) -> dict | None:
    """c - o >= 0.90 and v > 100000, the move rounded to cents once.

    Bonde's formula: the day's body, in dollars, so a gap is excluded and a
    high-priced name that moved $4 qualifies without a 4% day. The community
    TradingView variant measures c - c1 and requires the close within 30% of
    the high with no volume term; that one is not implemented.
    """
    b = _bars(df, at)
    return None if b is None else _dollar(b)


def double_trouble(df: pd.DataFrame, at: int = -1) -> dict | None:
    """c/minl252 >= 1.8 and minv3.1 >= 100000, with the quiet-day flag beside it."""
    b = _bars(df, at)
    return None if b is None else _dt(b)


def trend_intensity(df: pd.DataFrame, at: int = -1) -> dict | None:
    """avgc7/avgc65 > 1.05 and minv3.1 > 100000, with the quiet-day flag beside it."""
    b = _bars(df, at)
    return None if b is None else _trend_intensity(b)


def modified_double_trouble(df: pd.DataFrame, at: int = -1) -> dict | None:
    """c/avgc126 > 1.19 and minv3.1 > 100000, with the quiet-day flag beside it."""
    b = _bars(df, at)
    return None if b is None else _mdt(b)


def ti65_low_risk_entry(df: pd.DataFrame, at: int = -1) -> dict | None:
    """minv3.1 >= 100000, c >= 3, avgc7/avgc65 >= 1.05, c > o, c > c1, c/c1 > c1/c2, c1/c2 < 1.02."""
    b = _bars(df, at)
    return None if b is None else _low_risk_entry(b)


def episodic_pivot(df: pd.DataFrame, at: int = -1) -> dict | None:
    """c/c1 > 1.04 and v > 3*avgv50.1 and v >= 300000."""
    b = _bars(df, at)
    return None if b is None else _ep(b)


def ep_9m(df: pd.DataFrame, at: int = -1) -> dict | None:
    """v >= 9,000,000 and c >= 3: the volume-first EP discovery filter."""
    b = _bars(df, at)
    return None if b is None else _ep_9m(b)


def anticipation(df: pd.DataFrame, at: int = -1) -> dict | None:
    """The nightly watchlist: a quiet day on which DT, TI65 or MDT matches.

    Returns which setups matched and their values, ``narrow_range_days`` (how
    many of the last NARROW_LOOKBACK sessions ranged less than the median of
    the RANGE_NORM_SESSIONS before them, None when those bars cannot be read)
    and ``range_pct_today`` = 100*(h-l)/c. The count describes the base; it
    decides nothing.
    """
    b = _bars(df, at)
    return None if b is None else _anticipation(b)


def scan_all(df: pd.DataFrame, at: int = -1) -> dict:
    """Every nightly scan over one frame, each None or its measured values."""
    b = _bars(df, at)
    if b is None:
        return {key: None for key in SCAN_KEYS}
    return {"burst": _burst(b), "dollar": _dollar(b), "anticipation": _anticipation(b),
            "ep": _ep(b), "ep_9m": _ep_9m(b)}
