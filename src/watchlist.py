"""Bonde's nightly anticipation watchlist: quiet, coiled names in established
momentum, each with a box, a trigger and a stop.

Stages A and B -- established momentum (DT, TI65 or MDT) on a quiet day --
are ``scans.anticipation()`` and are not restated here. Stage C is the
range-contraction read Bonde gives as a chart checklist and never as a
formula ("series of narrow range days", "low volume pullback", "no 4% b/d
during the pullback or consolidation", "not up 3 days in a row", "avoid
extended"), so most of its numbers are proxies. Every constant below says
whose it is: (B) is a number Bonde states, (P) is this module's proxy for a
shape he describes in words. Both kinds are archived in RULES under
``watchlist.`` and PROVENANCE says which is which, because a proxy that
ships unmarked becomes a rule nobody wrote down.

ONE NUMBER PER MEASUREMENT: prices to the cent, volumes to the share,
percentages to PCT_DECIMALS and ratios to RATIO_DECIMALS, rounded once, and
every rule decides on the number the dict carries. A derived ratio divides
the PRINTED inputs -- ``compress`` is the printed recent range over the
printed base range, ``extension`` the close over the printed average -- so a
reader recomputing it from the record gets the record's number.

The frame is one symbol's daily bars, DatetimeIndex oldest first, one bar
per session, Open/High/Low/Close/Volume; ``at`` is the positional index of
the session being judged. A window that cannot be read (a NaN, a
non-positive price, fewer sessions than it needs) makes the measurement
None, never a confident number. A hole in the index is not detected here;
that is the transport's stale/gap check.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src import scans

# --- Stage C, the narrow-range days -------------------------------------
# ADR20 is the mean of (H-L)/C over the ADR_SESSIONS ending YESTERDAY, so the
# session being judged is measured against the ranges it came out of.
ADR_SESSIONS = 20          # (P) the window every "days tight" port averages over
TIGHT_LOOKBACK = 10        # (B) "series of low range bars in last 5 to 10 days", the upper end
TIGHT_FRACTION = 0.70      # (P) a tight day ranges under 70% of ADR20: the useThinkScript port's number, not his
TTT_SESSIONS = 3           # (B) "TTT", three tight days in a row
TT_SESSIONS = 2            # (B) "TT"
MIN_TIGHT = 3              # (P) tight days needed in the lookback when they are not consecutive
# --- compression: the last COMPRESS_RECENT ranges against the COMPRESS_BASE before them
COMPRESS_RECENT = 7        # (P) SpicyStock's existing compression proxy, kept for continuity of the record
COMPRESS_BASE = 60         # (P)
MAX_COMPRESS = 0.75        # (P)
# --- volume: "low volume pullback" (B); the two windows are this module's
VOL_DRY_RECENT = 5         # (P)
VOL_DRY_BASE = 50          # (P)
# --- breakdowns: scans.breakdown_4pct over the consolidation
BREAKDOWN_LOOKBACK = 10    # (P) the window the 4% breakdowns are counted over
MAX_BREAKDOWNS = 1         # (B) "no 4% b/d during the pullback", later "no more than one"
# --- up run
MAX_UP_RUN = 2             # (B) "not up 3 days in a row" on his anticipation list; 2LYNCH's burst rule says two
# --- extension
EXTENSION_SESSIONS = 20    # (P)
MAX_EXTENSION = 1.10       # (P) "avoid anticipation setups on extended stocks", made numeric
# --- the box: the longest run of sessions ending today whose highs sit together
BOX_MIN = 3                # (B) "3 to 10 days consolidation"
BOX_MAX = 10               # (B)
BOX_SPREAD_ADRS = 1.0      # (P) the box's highs lie within this many ADR20s (in dollars, of today's close) of each other
# --- trigger and stop
TRIGGER_CENTS = 0.02       # (P) "order few cents above the consolidation" (B); how many cents is this module's
TRIGGER_FRACTION = 0.001   # (P) the bump is a tenth of a percent on a name too dear for two cents to mean anything
STOP_SESSIONS = 3          # (B) "stop near low of the day or low of last 2 to 3 days"
MAX_RISK_PCT = 4.0         # (B) "stops are in most cases less than 4% or so"
# --- the list
TOP_N = 5                  # (B) "narrow them down to 1 to 5 for next day action"
ALSO_N = 10                # (P) how many of the names the cut left to show
# --- precision: rounded once, decided on the rounded number
RATIO_DECIMALS = 2         # (P)
PCT_DECIMALS = 1           # (P)
PRICE_DECIMALS = scans.CENTS  # the cent, the grid the scans read prices on

#: The archived constants: every upper-case number this module names is read
#: here (a test derives that from the source), so a threshold added later
#: cannot escape the record in silence.
RULES = {
    "watchlist.adr_sessions": ADR_SESSIONS,
    "watchlist.tight_lookback": TIGHT_LOOKBACK,
    "watchlist.tight_fraction_exclusive": TIGHT_FRACTION,
    "watchlist.ttt_sessions": TTT_SESSIONS,
    "watchlist.tt_sessions": TT_SESSIONS,
    "watchlist.min_tight": MIN_TIGHT,
    "watchlist.compress_recent_sessions": COMPRESS_RECENT,
    "watchlist.compress_base_sessions": COMPRESS_BASE,
    "watchlist.max_compress": MAX_COMPRESS,
    "watchlist.vol_dry_recent_sessions": VOL_DRY_RECENT,
    "watchlist.vol_dry_base_sessions": VOL_DRY_BASE,
    "watchlist.breakdown_lookback": BREAKDOWN_LOOKBACK,
    "watchlist.max_breakdowns": MAX_BREAKDOWNS,
    "watchlist.max_up_run": MAX_UP_RUN,
    "watchlist.extension_sessions": EXTENSION_SESSIONS,
    "watchlist.max_extension": MAX_EXTENSION,
    "watchlist.box_min_sessions": BOX_MIN,
    "watchlist.box_max_sessions": BOX_MAX,
    "watchlist.box_spread_adrs": BOX_SPREAD_ADRS,
    "watchlist.trigger_cents": TRIGGER_CENTS,
    "watchlist.trigger_fraction": TRIGGER_FRACTION,
    "watchlist.stop_sessions": STOP_SESSIONS,
    "watchlist.max_risk_pct": MAX_RISK_PCT,
    "watchlist.top_n": TOP_N,
    "watchlist.also_n": ALSO_N,
    "watchlist.ratio_decimals": RATIO_DECIMALS,
    "watchlist.pct_decimals": PCT_DECIMALS,
    "watchlist.price_decimals": PRICE_DECIMALS,
}

#: Whose number each rule is: "B" Bonde states it, "P" this module's proxy.
PROVENANCE = {
    "watchlist.adr_sessions": "P",
    "watchlist.tight_lookback": "B",
    "watchlist.tight_fraction_exclusive": "P",
    "watchlist.ttt_sessions": "B",
    "watchlist.tt_sessions": "B",
    "watchlist.min_tight": "P",
    "watchlist.compress_recent_sessions": "P",
    "watchlist.compress_base_sessions": "P",
    "watchlist.max_compress": "P",
    "watchlist.vol_dry_recent_sessions": "P",
    "watchlist.vol_dry_base_sessions": "P",
    "watchlist.breakdown_lookback": "P",
    "watchlist.max_breakdowns": "B",
    "watchlist.max_up_run": "B",
    "watchlist.extension_sessions": "P",
    "watchlist.max_extension": "P",
    "watchlist.box_min_sessions": "B",
    "watchlist.box_max_sessions": "B",
    "watchlist.box_spread_adrs": "P",
    "watchlist.trigger_cents": "P",
    "watchlist.trigger_fraction": "P",
    "watchlist.stop_sessions": "B",
    "watchlist.max_risk_pct": "B",
    "watchlist.top_n": "B",
    "watchlist.also_n": "P",
    "watchlist.ratio_decimals": "P",
    "watchlist.pct_decimals": "P",
    "watchlist.price_decimals": "P",
}

#: The Stage C rules, in the order ``reasons_failed`` names them. ``vol_dry``
#: is measured and published beside them and decides nothing: the admission
#: line the spec gives does not carry it, and a column is not a filter.
STAGE_C = ("tight", "compress", "breakdowns", "up_run", "extension", "box")
#: The also-quiet reason for an admitted name whose stop is too wide.
STOP_WIDER = f"stop wider than {MAX_RISK_PCT:g}%"

COLUMNS = scans.COLUMNS
_PRICES = ("Open", "High", "Low", "Close")


class _Frame:
    """One frame read once: cent prices, whole-share volumes, NaN where unreadable."""

    __slots__ = ("_values", "_index", "pos")

    def __init__(self, values: dict[str, np.ndarray], index: pd.Index, pos: int) -> None:
        self._values = values
        self._index = index
        self.pos = pos

    def value(self, column: str, back: int = 0) -> float | None:
        """The column ``back`` sessions before the judged one, or None."""
        window = self.window(column, 1, back)
        return None if window is None else float(window[0])

    def window(self, column: str, sessions: int, back: int = 0) -> np.ndarray | None:
        """``sessions`` values ending ``back`` sessions before the judged one,
        oldest first; None unless every value is readable (a positive price, a
        non-negative volume -- a NaN fails either test)."""
        stop = self.pos - back
        start = stop - sessions + 1
        if start < 0 or stop < 0:
            return None
        window = self._values[column][start:stop + 1]
        readable = (window > 0).all() if column in _PRICES else (window >= 0).all()
        return window if readable else None

    def date(self, pos: int) -> str | None:
        """The session date at ``pos`` as ISO text, or None when it is not a date."""
        try:
            stamp = pd.Timestamp(self._index[pos])
        except (TypeError, ValueError):
            return None
        return None if pd.isna(stamp) else stamp.date().isoformat()


def _read(df: pd.DataFrame, at: int) -> _Frame | None:
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
        values[column] = np.round(numbers, PRICE_DECIMALS if column in _PRICES else 0)
    return _Frame(values, df.index, pos)


def _pct(value: float) -> float:
    return float(round(float(value), PCT_DECIMALS))


def _ratio(top: float, bottom: float) -> float | None:
    return None if bottom <= 0 else float(round(top / bottom, RATIO_DECIMALS))


def _price(value: float) -> float:
    return float(round(float(value), PRICE_DECIMALS))


def _shares(value: float) -> int:
    return int(round(float(value)))


def _range_pcts(f: _Frame, sessions: int, back: int = 0) -> np.ndarray | None:
    """100*(H-L)/C per session, raw; None for an unreadable or inverted bar."""
    highs, lows, closes = (f.window(column, sessions, back) for column in ("High", "Low", "Close"))
    if highs is None or lows is None or closes is None or (highs < lows).any():
        return None
    return 100 * (highs - lows) / closes


def _up_run(f: _Frame) -> int:
    """Consecutive strictly-up closes ending on the judged session."""
    run = 0
    while True:
        newer, older = f.value("Close", run), f.value("Close", run + 1)
        if newer is None or older is None or not newer > older:
            return run
        run += 1


def _box(f: _Frame, adr20_pct: float, close: float) -> dict | None:
    """The longest run of BOX_MIN..BOX_MAX sessions ending today whose highs
    lie within BOX_SPREAD_ADRS ADR20s of each other, in dollars of today's
    close. A run's highs are a superset of any shorter run's, so the first
    length that qualifies counting down is the longest."""
    limit = _price(BOX_SPREAD_ADRS * adr20_pct / 100 * close)
    for length in range(BOX_MAX, BOX_MIN - 1, -1):
        highs, lows = f.window("High", length), f.window("Low", length)
        if highs is None or lows is None:
            continue
        spread = _price(highs.max() - highs.min())
        if spread <= limit:
            return {"high": float(highs.max()), "low": float(lows.min()), "length": length,
                    "spread": spread, "spread_limit": limit,
                    "start": f.date(f.pos - length + 1), "end": f.date(f.pos)}
    return None


def _stage_c(f: _Frame, df: pd.DataFrame, ant: dict) -> dict | None:
    """Stage C over a frame Stage A+B already matched; None when a window is unreadable."""
    close = f.value("Close")
    adr = _range_pcts(f, ADR_SESSIONS, back=1)
    recent = _range_pcts(f, TIGHT_LOOKBACK)
    compress_recent = _range_pcts(f, COMPRESS_RECENT)
    compress_base = _range_pcts(f, COMPRESS_BASE, back=COMPRESS_RECENT)
    volume_recent = f.window("Volume", VOL_DRY_RECENT)
    volume_base = f.window("Volume", VOL_DRY_BASE)
    closes = f.window("Close", EXTENSION_SESSIONS)
    stop_lows = f.window("Low", STOP_SESSIONS)
    windows = (close, adr, recent, compress_recent, compress_base, volume_recent,
               volume_base, closes, stop_lows)
    if any(window is None for window in windows) or f.pos < BREAKDOWN_LOOKBACK:
        return None

    adr20_pct = _pct(adr.mean())
    tight_limit_pct = _pct(TIGHT_FRACTION * adr20_pct)
    tight = [_pct(r) < tight_limit_pct for r in recent]
    tight_n = int(sum(tight))
    ttt = all(tight[-TTT_SESSIONS:])
    tt = all(tight[-TT_SESSIONS:])
    range_recent_pct = _pct(compress_recent.mean())
    range_base_pct = _pct(compress_base.mean())
    compress = _ratio(range_recent_pct, range_base_pct)
    volume_ratio = _ratio(_shares(volume_recent.mean()), _shares(volume_base.mean()))
    if compress is None or volume_ratio is None:
        return None
    breakdowns = sum(scans.breakdown_4pct(df, at=f.pos - back) is not None
                     for back in range(BREAKDOWN_LOOKBACK))
    up_run = _up_run(f)
    close_avg = _price(closes.mean())
    extension = _ratio(close, close_avg)
    box = _box(f, adr20_pct, close)

    trigger = None if box is None else _price(box["high"] + max(TRIGGER_CENTS, TRIGGER_FRACTION * close))
    stop_primary = float(stop_lows.min())
    stop_alt = f.value("Low")
    risk_pct = None if trigger is None else _pct(100 * (trigger / stop_primary - 1))
    eligible = risk_pct is not None and risk_pct <= MAX_RISK_PCT

    failed = []
    if not (ttt or tight_n >= MIN_TIGHT):
        failed.append("tight")
    if compress > MAX_COMPRESS:
        failed.append("compress")
    if breakdowns > MAX_BREAKDOWNS:
        failed.append("breakdowns")
    if up_run > MAX_UP_RUN:
        failed.append("up_run")
    if extension > MAX_EXTENSION:
        failed.append("extension")
    if box is None:
        failed.append("box")

    return {
        "setups": list(ant["setups"]),
        "ti65": None if ant["ti65"] is None else ant["ti65"]["ti65"],
        "dt": None if ant["dt"] is None else ant["dt"]["ratio"],
        "mdt": None if ant["mdt"] is None else ant["mdt"]["ratio"],
        "pct_change_today": ant["pct_change_today"],
        "narrow_range_days": ant["narrow_range_days"],
        "close": close,
        "adr20_pct": adr20_pct,
        "tight_limit_pct": tight_limit_pct,
        "range_pct_today": _pct(recent[-1]),
        "tight_today": bool(tight[-1]),
        "tight_n": tight_n,
        "ttt": bool(ttt),
        "tt": bool(tt),
        "range_recent_pct": range_recent_pct,
        "range_base_pct": range_base_pct,
        "compress": compress,
        "volume_ratio": volume_ratio,
        "vol_dry": volume_ratio < 1,
        "breakdowns": int(breakdowns),
        "up_run": int(up_run),
        "close_avg": close_avg,
        "extension": extension,
        "box": box,
        "trigger": trigger,
        "stop_primary": stop_primary,
        "stop_alt": stop_alt,
        "risk_pct": risk_pct,
        "eligible": bool(eligible),
        "admitted": not failed,
        "reasons_failed": failed,
    }


# ------------------------------------------------------------ public API ----


def measure(df: pd.DataFrame, at: int = -1) -> dict | None:
    """Stage C over one frame, or None when Stage A+B do not match or a
    Stage C window cannot be read.

    The dict carries every measurement, ``admitted`` (every Stage C rule
    passed), ``reasons_failed`` (the STAGE_C names that did not), the box,
    and the trigger, both stops, the risk and ``eligible`` (the risk within
    MAX_RISK_PCT). Trigger and risk are None without a box.
    """
    f = _read(df, at)
    if f is None:
        return None
    ant = scans.anticipation(df, at)
    return None if ant is None else _stage_c(f, df, ant)


def rank_key(row: dict) -> tuple:
    """TTT first, then TI65 descending (None as 0), then compress ascending."""
    return (0 if row["ttt"] else 1, -(row["ti65"] or 0.0), row["compress"], row.get("ticker", ""))


def build(frames: dict[str, pd.DataFrame], top_n: int = TOP_N, also_n: int = ALSO_N) -> dict:
    """The night's list over every frame: ``top`` (admitted and eligible,
    ranked, at most ``top_n``), ``also_quiet`` (what the cut left, ranked
    within three tiers: eligible names past ``top_n``, admitted names whose
    stop is wider than MAX_RISK_PCT, and Stage A+B matches short by exactly
    one Stage C rule; at most ``also_n``, each with ``why``), ``counts``
    (momentum: Stage A; quiet: Stage A+B; admitted; eligible: admitted and
    within the risk) and ``rules``."""
    counts = {"momentum": 0, "quiet": 0, "admitted": 0, "eligible": 0}
    rows = []
    for ticker, df in frames.items():
        f = _read(df, -1)
        if f is None:
            continue
        if any(scan(df) is not None for scan in
               (scans.double_trouble, scans.trend_intensity, scans.modified_double_trouble)):
            counts["momentum"] += 1
        ant = scans.anticipation(df)
        if ant is None:
            continue
        counts["quiet"] += 1
        measured = _stage_c(f, df, ant)
        if measured is None:
            continue
        counts["admitted"] += int(measured["admitted"])
        counts["eligible"] += int(measured["admitted"] and measured["eligible"])
        rows.append({"ticker": str(ticker), **measured})
    rows.sort(key=rank_key)
    picked = [row for row in rows if row["admitted"] and row["eligible"]]
    also = [{**row, "why": f"outside the top {top_n}"} for row in picked[top_n:]]
    also += [{**row, "why": STOP_WIDER} for row in rows if row["admitted"] and not row["eligible"]]
    also += [{**row, "why": "failed " + row["reasons_failed"][0]}
             for row in rows if not row["admitted"] and len(row["reasons_failed"]) == 1]
    return {"top": picked[:top_n], "also_quiet": also[:also_n], "counts": counts, "rules": dict(RULES)}
