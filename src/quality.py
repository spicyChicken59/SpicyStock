"""Bonde's A-quality checklist: 2LYNCH with his letters and his numbers.

One symbol's daily frame in (DatetimeIndex oldest first, Open/High/Low/Close/
Volume, NaNs allowed) and the position of the burst bar being judged; one
Assessment out: the six letters, then range expansion and volume -- the
scan's own conditions, re-read here so the record says how strongly they
held -- the vetoes, a score, a grade, the anticipation reclassification and
the notes that vote for nothing.

ONE NUMBER PER MEASUREMENT. Every ratio this module measures is rounded to
RATIO_DECIMALS, every percentage to PCT_DECIMALS and every price to CENTS,
once, and every rule decides on the rounded number the Check carries, so
what the model reads is what was decided. Close-to-close changes are the one
exception, deliberately: they are read on src.scans's own grid, so a bar
this module counts as an earlier burst or a breakdown is one the scan would
have printed on its price clause, and the burst's gain is the scan's number.

Sources are cited beside each constant: VERBATIM is his words, MEASURED was
read off a file, DERIVED is an inference (ours or a third party's), each
with the confidence the research lens gave it.
"""

from __future__ import annotations

import math

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from src import scans
from src.grader import GRADE_BANDS, SKIP, grade_for

# ----------------------------------------------------------- the base ----
# leg_high = the highest High over the BASE_SEARCH_SESSIONS before the burst,
# the session before the burst excluded so the base is never empty; the base
# runs from the session after it through the session before the burst.
# DERIVED: his lengths are "3 to 20" (2014), "3 to 10" (2015), "5-40" (2018).
BASE_SEARCH_SESSIONS = 40
# The leg starts at the lowest close in the LEG_SEARCH_SESSIONS before the
# base begins. DERIVED from his 60-day efficiency-ratio window (2009).
LEG_SEARCH_SESSIONS = 60
# Fewer bars than this is no leg to fit: L is unmeasured, never a veto.
MIN_LEG_SESSIONS = 5

# --------------------------------------------- 2: not up two days in a row ----
# "not up two days in a row on breakout day (a small up day of less than 1%
# before b/o is fine)" -- VERBATIM, 2LYNCH thread. A day above UP_DAY_PCT
# counts, a day from 0 to it is flat and neither counts nor breaks the run,
# a negative day breaks it. High confidence.
UP_DAY_PCT = 1.0
MAX_UP_RUN = 1
# "stock should not be up 3 days in a row" -- VERBATIM, 2014-2018 text; the
# video's "3% three days in a row -> should not even look at it". Both of
# his statements agree three is out, so three up closes of ANY size veto.
VETO_UP_DAYS = 3

# ------------------------------------------------------- L: linearity ----
# ER is his own formula (2009): net move over the sum of the daily moves.
# R2 is a log-close OLS. The thresholds are DERIVED, low confidence: a
# straight line is 1.0 by his example and a random walk sits near 0.1-0.2;
# 0.55 is the R2 the previous checklist used. "If a stock does not have
# relative linearity, I do not even look at rest of the criteria" (2011),
# so failing L is a veto.
MIN_ER = 0.40
MIN_R2 = 0.55

# ------------------------------------------------------ Y: young trend ----
# "first or second b/o from consolidation is low risk" -- VERBATIM, 2LYNCH.
# The start of the move is DERIVED (he never defines it): the lowest close
# of the last MOVE_SEARCH_SESSIONS, preferring one under its own SMA.
MOVE_SEARCH_SESSIONS = 60
MOVE_SMA_SESSIONS = 50
# A breakout is a bar his scan printed that closed strong: the community's
# 0.70 close strength, used for COUNTING earlier bars and not for grading H.
BREAKOUT_MIN_CLOSE_POS = 0.70
MAX_PRIOR_BREAKOUTS = 1

# ------------------------------------- N: narrow or negative day before ----
# "a negative day or a narrow range day of less than 2% pre breakout day"
# -- VERBATIM as transcribed from the 2018 video; a 2.1% day refused at
# 10:11. An OR, as he states it. Medium-high confidence.
NARROW_RANGE_PCT = 2.0
# A+ asks the prior bar to be under the median range of the sessions before
# it as well: DERIVED (the pre-registered study's relative reading).
NARROW_NORM_SESSIONS = 20

# --------------------------------------------- C: consolidation quality ----
# "The stock will have 3 to 20 days consolidation" -- VERBATIM, 2014. A base
# of PARTIAL_BASE_MIN, or longer than BASE_MAX inside the search window, is
# a partial: "5-40" (2018) and "3 to 10" (2015) are both his.
BASE_MIN = 3
BASE_MAX = 20
PARTIAL_BASE_MIN = 2
# "no more than one 4% b/d in consolidation" -- VERBATIM, 2LYNCH; the 2014
# ideal "did not have a 4% breakdown" is the A+.
MAX_BREAKDOWNS = 1
# Depth: the webinar's "not more than 1/3 of the first leg" (secondary), the
# unsourced "upper third" for A+. Low confidence; no Bonde number.
MAX_GIVEBACK = 0.34
A_PLUS_MAX_GIVEBACK = 0.25
# Tightness: base range over the range of the sessions before it. The
# concept is his ("narrow range bars", "low volatility"); the ratio is
# DERIVED, the previous checklist's own. Medium / low confidence.
MAX_TIGHTNESS = 1.0
A_PLUS_MAX_TIGHTNESS = 0.70
TIGHTNESS_NORM_SESSIONS = 60
# "volume during consolidation should be preferably orderly and lower"
# (2016): the A+ asks the base's mean volume under the leg's and under the
# VOLUME_AVG_SESSIONS average ending the session before the burst.
VOLUME_AVG_SESSIONS = 50

# ------------------------------------------------- H: close near the high ----
# "close near high or within 20% of high" -- VERBATIM as transcribed, video
# 03:50; and his C - O sort at 06:30, so the close must be above the open.
# The community's 0.70 is looser than his and is the partial band here.
MIN_CLOSE_POS = 0.80
A_PLUS_CLOSE_POS = 0.90
PARTIAL_CLOSE_POS = 0.70

# ---------------------------------------------------- RE: range expansion ----
# "a day which is up bigger than the last 5 to 10 days bars" -- VERBATIM
# (2013); "5 to 7" (2014). Today's range over the largest of the prior
# RE_WINDOW ranges must reach MIN_RANGE_EXPANSION; A+ over RE_WINDOW_LONG
# too. High confidence on the window, medium on range against move.
RE_WINDOW = 5
RE_WINDOW_LONG = 10
MIN_RANGE_EXPANSION = 1.0

# ------------------------------------------------------------ VOL: volume ----
# v > v1 is the scan's; "one of the highest volume in this entire move of
# last 2-3 months" (video 05:58) is the A+: top A_PLUS_MAX_VOLUME_RANK of
# the last VOLUME_RANK_SESSIONS. +CV: a base longer than CV_BASE_SESSIONS
# needs volume at CV_MIN_VOLUME times the average and a catalyst (tikamalma
# and F4VS, secondary and agreeing; medium confidence).
VOLUME_RANK_SESSIONS = 60
A_PLUS_MAX_VOLUME_RANK = 3
CV_BASE_SESSIONS = 21
CV_MIN_VOLUME = 1.5

# ---------------------------------------------------------- notes only ----
# Extension against the 20-SMA and the 20-session run-up: the previous
# checklist's Y, in no source of his, kept as a note.
EXTENSION_SMA_SESSIONS = 20
RUN_UP_SESSIONS = 20
# "Low priced stocks (below 5 dollar) tend to make very explosive moves"
# -- VERBATIM, 2014.
LOW_PRICE = 5.0
# MEASURED: the only event study's worst cell is the 15%-plus movers, a 36%
# win rate and -9.3% at 20 sessions over 587 events.
HIGH_GAIN_PCT = 15.0
# "always check last three or four breakouts" (video 11:21): of the last
# HISTORY_MAX_BREAKOUTS prior 4% days in HISTORY_SESSIONS, how many closed
# higher HISTORY_FOLLOW_SESSIONS later.
HISTORY_SESSIONS = 60
HISTORY_MAX_BREAKOUTS = 4
HISTORY_FOLLOW_SESSIONS = 3
# "a first leg of 15% plus in 10 days or less" -- VERBATIM, his 2026
# anticipation thread; noted, not graded.
FAST_LEG_MIN_GAIN_PCT = 15.0
FAST_LEG_MAX_SESSIONS = 10

# -------------------------------------------------------- score and grade ----
# Ten points over the six letters; L and C carry the most because L is his
# veto and C is the base the whole checklist describes. RE and VOL add
# nothing to the score and count in the A+ tally. DERIVED: he publishes no
# weighting or pass count.
WEIGHT_L = 2.0
WEIGHT_C = 2.0
WEIGHT_2 = 1.5
WEIGHT_Y = 1.5
WEIGHT_N = 1.5
WEIGHT_H = 1.5
# A+ (the top band of src.grader's GRADE_BANDS) also needs this many checks
# at their A+ standard.
MIN_A_PLUS_LETTERS = 4
# The two bands above GATE_CAP also need every letter in GRADE_GATE_LETTERS
# passed outright -- 2 and H, the two he states as conditions of the
# breakout day itself -- and a name that scores into them with either
# failed, partial or unmeasured is capped at GATE_CAP with a note naming the
# letter. DERIVED: the design panel's rule, not his.
GRADE_GATE_LETTERS = ("2", "H")
GATED_GRADES = tuple(grade for _, grade in GRADE_BANDS[:2])
GATE_CAP = GRADE_BANDS[2][1]

# --------------------------------------------------------------- precision ----
RATIO_DECIMALS = 2
PCT_DECIMALS = 1
CENTS = 2

#: The archived constants: every upper-case number this module names is read
#: here (a test derives that from the source).
RULES = {
    "quality.base_search_sessions": BASE_SEARCH_SESSIONS,
    "quality.leg_search_sessions": LEG_SEARCH_SESSIONS,
    "quality.min_leg_sessions": MIN_LEG_SESSIONS,
    "quality.up_day_pct_exclusive": UP_DAY_PCT,
    "quality.max_up_run": MAX_UP_RUN,
    "quality.veto_up_days": VETO_UP_DAYS,
    "quality.min_er": MIN_ER,
    "quality.min_r2": MIN_R2,
    "quality.move_search_sessions": MOVE_SEARCH_SESSIONS,
    "quality.move_sma_sessions": MOVE_SMA_SESSIONS,
    "quality.breakout_min_close_pos": BREAKOUT_MIN_CLOSE_POS,
    "quality.max_prior_breakouts": MAX_PRIOR_BREAKOUTS,
    "quality.narrow_range_pct_exclusive": NARROW_RANGE_PCT,
    "quality.narrow_norm_sessions": NARROW_NORM_SESSIONS,
    "quality.base_min": BASE_MIN,
    "quality.base_max": BASE_MAX,
    "quality.partial_base_min": PARTIAL_BASE_MIN,
    "quality.max_breakdowns": MAX_BREAKDOWNS,
    "quality.max_giveback": MAX_GIVEBACK,
    "quality.a_plus_max_giveback": A_PLUS_MAX_GIVEBACK,
    "quality.max_tightness": MAX_TIGHTNESS,
    "quality.a_plus_max_tightness": A_PLUS_MAX_TIGHTNESS,
    "quality.tightness_norm_sessions": TIGHTNESS_NORM_SESSIONS,
    "quality.volume_avg_sessions": VOLUME_AVG_SESSIONS,
    "quality.min_close_pos": MIN_CLOSE_POS,
    "quality.a_plus_close_pos": A_PLUS_CLOSE_POS,
    "quality.partial_close_pos": PARTIAL_CLOSE_POS,
    "quality.re_window": RE_WINDOW,
    "quality.re_window_long": RE_WINDOW_LONG,
    "quality.min_range_expansion": MIN_RANGE_EXPANSION,
    "quality.volume_rank_sessions": VOLUME_RANK_SESSIONS,
    "quality.a_plus_max_volume_rank": A_PLUS_MAX_VOLUME_RANK,
    "quality.cv_base_sessions_exclusive": CV_BASE_SESSIONS,
    "quality.cv_min_volume": CV_MIN_VOLUME,
    "quality.extension_sma_sessions": EXTENSION_SMA_SESSIONS,
    "quality.run_up_sessions": RUN_UP_SESSIONS,
    "quality.low_price_exclusive": LOW_PRICE,
    "quality.high_gain_pct": HIGH_GAIN_PCT,
    "quality.history_sessions": HISTORY_SESSIONS,
    "quality.history_max_breakouts": HISTORY_MAX_BREAKOUTS,
    "quality.history_follow_sessions": HISTORY_FOLLOW_SESSIONS,
    "quality.fast_leg_min_gain_pct": FAST_LEG_MIN_GAIN_PCT,
    "quality.fast_leg_max_sessions": FAST_LEG_MAX_SESSIONS,
    "quality.weight_l": WEIGHT_L,
    "quality.weight_c": WEIGHT_C,
    "quality.weight_2": WEIGHT_2,
    "quality.weight_y": WEIGHT_Y,
    "quality.weight_n": WEIGHT_N,
    "quality.weight_h": WEIGHT_H,
    "quality.min_a_plus_letters": MIN_A_PLUS_LETTERS,
    "quality.precision.ratio_decimals": RATIO_DECIMALS,
    "quality.precision.pct_decimals": PCT_DECIMALS,
    "quality.precision.price_decimals": CENTS,
    "quality.burst_ratio": scans.BURST_RATIO,
    "quality.breakdown_ratio": scans.BREAKDOWN_RATIO,
}

COLUMNS = ("Open", "High", "Low", "Close", "Volume")
_PRICES = ("Open", "High", "Low", "Close")
#: The six letters, in the order the checks are listed, and their weights.
LETTERS = ("2", "L", "Y", "N", "C", "H")
WEIGHTS = {"2": WEIGHT_2, "L": WEIGHT_L, "Y": WEIGHT_Y, "N": WEIGHT_N, "C": WEIGHT_C, "H": WEIGHT_H}
#: The two checks that are the scan's own conditions: no score, an A+ tally.
EXTRA_CHECKS = ("RE", "VOL")
#: The absolute rules, by name, in the order they are reported.
VETO_UP_DAYS_NAME = "up_days"
VETO_NOT_LINEAR = "not_linear"
VETO_NAMES = (VETO_UP_DAYS_NAME, VETO_NOT_LINEAR)
#: Where a burst that meets everything but H is routed (bootcamp: "if it
#: meets 2lynch but not H its an anticipation setup").
RECLASS_ANTICIPATION = "anticipation"
STATUS_PASS, STATUS_PARTIAL, STATUS_FAIL, STATUS_UNMEASURED = "PASS", "PARTIAL", "FAIL", "UNMEASURED"


@dataclass
class Check:
    """One criterion: what was measured, what it was held to, and the verdict.

    ``passed`` is True, False, or None when the measurement could not be
    made. A partial is a False with ``partial`` set: it is not a pass, it
    earns half its weight, and it is never an A+.
    """

    key: str
    letter: str
    label: str
    value: dict
    threshold: str
    passed: bool | None
    a_plus: bool
    note: str
    partial: bool = False

    @property
    def status(self) -> str:
        if self.partial:
            return STATUS_PARTIAL
        if self.passed is None:
            return STATUS_UNMEASURED
        return STATUS_PASS if self.passed else STATUS_FAIL

    def line(self) -> str:
        """``letter: STATUS -- values vs threshold -- note``, for the model."""
        values = " ".join(f"{k}={v}" for k, v in self.value.items()) or "no measurement"
        parts = [f"{self.letter}: {self.status}", f"{values} vs {self.threshold}"]
        if self.note:
            parts.append(self.note)
        return " -- ".join(parts)

    @property
    def primary(self) -> float | int | bool | None:
        """The one number a chart or a cell reads off this check: the first
        finite measurement in ``value``, in the order the check names them."""
        for v in self.value.values():
            if isinstance(v, bool) or v is None:
                continue
            if isinstance(v, (int, float)) and math.isfinite(v):
                return v
        return None

    def display(self) -> str:
        """The measurements as one short string, ``k=v`` each."""
        return " ".join(f"{k}={v}" for k, v in self.value.items() if v is not None) or "not measured"

    def to_dict(self) -> dict:
        """The archived row. ``values`` is every measurement; ``value`` the
        primary one; ``pass``/``marginal``/``status`` are the verdict in the
        three shapes the page and the model read."""
        return {"key": self.key, "letter": self.letter, "label": self.label,
                "values": dict(self.value), "value": self.primary, "display": self.display(),
                "threshold": self.threshold, "passed": self.passed, "pass": self.passed is True,
                "marginal": bool(self.partial), "a_plus": self.a_plus, "note": self.note,
                "partial": self.partial, "status": self.status}


@dataclass
class Assessment:
    """The whole checklist over one burst bar."""

    checks: list[Check]
    vetoes: list[str]
    passes: int
    of: int
    a_plus_count: int
    score: float
    grade: str
    reclass: str | None
    notes: list[str]
    base: dict | None
    leg: dict | None
    burst: dict
    unreadable: str | None = None
    weights: dict = field(default_factory=lambda: dict(WEIGHTS))

    def check(self, letter: str) -> Check | None:
        return next((c for c in self.checks if c.letter == letter), None)

    def to_dict(self) -> dict:
        return {
            "checks": [c.to_dict() for c in self.checks],
            "vetoes": list(self.vetoes),
            "passes": self.passes,
            "of": self.of,
            "a_plus_count": self.a_plus_count,
            "score": self.score,
            "grade": self.grade,
            "reclass": self.reclass,
            "notes": list(self.notes),
            "base": None if self.base is None else dict(self.base),
            "leg": None if self.leg is None else dict(self.leg),
            "burst": dict(self.burst),
            "unreadable": self.unreadable,
            "weights": dict(self.weights),
        }


# ------------------------------------------------------------ reading ----


class _Bars:
    """One frame read once: cent prices, whole-share volumes, NaN where unreadable."""

    __slots__ = ("o", "h", "l", "c", "v", "t", "n")

    def __init__(self, values: dict[str, np.ndarray], t: int) -> None:
        self.o, self.h, self.l, self.c, self.v = (values[k] for k in COLUMNS)
        self.t = t
        self.n = len(self.c)


def _arrays(df: pd.DataFrame, at: int) -> _Bars | None:
    if not isinstance(df, pd.DataFrame) or len(df) == 0:
        return None
    if isinstance(at, bool) or not isinstance(at, (int, np.integer)):
        return None
    t = int(at) if at >= 0 else len(df) + int(at)
    if not 0 <= t < len(df):
        return None
    values = {}
    for column in COLUMNS:
        if column not in df.columns or not isinstance(df[column], pd.Series):
            return None
        try:
            numbers = pd.to_numeric(df[column], errors="coerce").to_numpy(dtype=float, na_value=np.nan)
        except (TypeError, ValueError):
            return None
        readable = numbers > 0 if column in _PRICES else numbers >= 0
        numbers = np.where(np.isfinite(numbers) & readable, numbers, np.nan)
        values[column] = np.round(numbers, CENTS if column in _PRICES else 0)
    return _Bars(values, t)


def _r(value, decimals: int) -> float | None:
    """Rounded once, ``-0.0`` collapsed; None for anything not finite."""
    if value is None or not np.isfinite(value):
        return None
    return float(round(float(value), decimals)) + 0.0


def _ratio(top, bottom) -> float | None:
    if top is None or bottom is None or not np.isfinite(top) or not np.isfinite(bottom) or bottom <= 0:
        return None
    return _r(top / bottom, RATIO_DECIMALS)


def _pct_of(part, whole) -> float | None:
    if part is None or whole is None or not np.isfinite(part) or not np.isfinite(whole) or whole <= 0:
        return None
    return _r(100 * part / whole, PCT_DECIMALS)


def _scan_ratio(b: _Bars, i: int) -> float | None:
    """c/c1 on the scan's own grid: the number scans.burst_4pct decides on."""
    if i < 1 or not (np.isfinite(b.c[i]) and np.isfinite(b.c[i - 1])):
        return None
    return float(round(b.c[i] / b.c[i - 1], scans.RATIO_DECIMALS))


def _day_pct(b: _Bars, i: int) -> float | None:
    ratio = _scan_ratio(b, i)
    return None if ratio is None else float(round((ratio - 1) * 100, scans.PCT_DECIMALS)) + 0.0


def _is_burst_day(b: _Bars, i: int) -> bool:
    ratio = _scan_ratio(b, i)
    return ratio is not None and ratio >= scans.BURST_RATIO


def _is_breakdown_day(b: _Bars, i: int) -> bool:
    ratio = _scan_ratio(b, i)
    return ratio is not None and ratio <= scans.BREAKDOWN_RATIO


def _range_pct(b: _Bars, i: int) -> float | None:
    """100 * (h - l) / c for one bar; None when unreadable or inverted."""
    h, l, c = b.h[i], b.l[i], b.c[i]
    if not (np.isfinite(h) and np.isfinite(l) and np.isfinite(c)) or h < l:
        return None
    return _pct_of(h - l, c)


def _close_pos(b: _Bars, i: int) -> float | None:
    """(c - l) / (h - l); None for no range, an inverted bar or a close outside it."""
    h, l, c = b.h[i], b.l[i], b.c[i]
    if not (np.isfinite(h) and np.isfinite(l) and np.isfinite(c)) or h <= l or not l <= c <= h:
        return None
    return _ratio(c - l, h - l)


def _range_pcts(b: _Bars, start: int, stop: int) -> list[float]:
    """The readable range percentages over positions start..stop inclusive."""
    return [p for p in (_range_pct(b, i) for i in range(max(start, 0), stop + 1)) if p is not None]


def _mean(values) -> float | None:
    values = [v for v in values if v is not None and np.isfinite(v)]
    return None if not values else float(np.mean(values))


def _bar_problem(b: _Bars, i: int) -> str | None:
    """Why the bar at ``i`` cannot be graded, or None: a bad bar is refused, not read."""
    o, h, l, c, v = b.o[i], b.h[i], b.l[i], b.c[i], b.v[i]
    if not all(np.isfinite(x) for x in (o, h, l, c, v)):
        return "the burst bar is missing a readable open, high, low, close or volume"
    if h < l:
        return "the burst bar is inverted (high below low)"
    if h == l:
        return "the burst bar has no range (high equals low)"
    if not l <= c <= h:
        return "the burst bar closed outside its own high-low"
    if not l <= o <= h:
        return "the burst bar opened outside its own high-low"
    return None


# ------------------------------------------------------- base and leg ----


def _log_trend(x: np.ndarray, y: np.ndarray) -> float:
    """R-squared of a straight-line fit of ``y`` on ``x``."""
    if len(y) < MIN_LEG_SESSIONS or np.allclose(y, y[0]):
        return 0.0
    coeffs = np.polyfit(x, y, 1)
    pred = np.polyval(coeffs, x)
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    return 1 - ss_res / ss_tot if ss_tot else 0.0


def _find_base(b: _Bars) -> dict | None:
    """The consolidation: after the highest High of the search window, through
    the session before the burst. The FIRST print of that high starts it, so
    a base that re-tests its top is one base and not several short ones."""
    t = b.t
    lo, hi = max(t - BASE_SEARCH_SESSIONS, 0), t - 2
    if hi < lo:
        return None
    highs = b.h[lo:hi + 1]
    if not np.isfinite(highs).any():
        return None
    peak = lo + int(np.nanargmax(highs))
    start, end = peak + 1, t - 1
    lows = b.l[start:end + 1]
    low = float(np.nanmin(lows)) if np.isfinite(lows).any() else None
    return {"start": start, "end": end, "length": end - start + 1,
            "high": float(b.h[peak]), "low": low, "peak": peak}


def _find_leg(b: _Bars, base: dict) -> dict | None:
    """The advance before the base: from the LAST print of the lowest close in
    the search window before the base to the FIRST print of its high (the
    base's peak session) -- the shortest interval that spans the move, so a
    flat floor before the leg is not fitted as part of it."""
    peak = base["peak"]
    lo = max(base["start"] - LEG_SEARCH_SESSIONS, 0)
    closes = b.c[lo:peak + 1]
    if not np.isfinite(closes).any():
        return None
    start = lo + int(np.flatnonzero(closes == np.nanmin(closes))[-1])
    end = peak
    positions = np.arange(start, end + 1)
    finite = positions[np.isfinite(b.c[start:end + 1])]
    values = b.c[finite]
    length = end - start + 1
    lows = b.l[start:end + 1]
    leg = {"start": int(start), "end": int(end), "length": int(length),
           "gain_pct": _pct_of(values[-1] - values[0], values[0]),
           "high": base["high"],
           "low": float(np.nanmin(lows)) if np.isfinite(lows).any() else None,
           "er": None, "r2": None}
    if len(values) < MIN_LEG_SESSIONS:
        return leg
    total = float(np.sum(np.abs(np.diff(values))))
    leg["er"] = _ratio(abs(values[-1] - values[0]), total) if total > 0 else None
    leg["r2"] = _r(_log_trend(finite.astype(float), np.log(values)), RATIO_DECIMALS)
    return leg


# -------------------------------------------------------------- checks ----


def _check_two(b: _Bars) -> Check:
    t = b.t
    prior = _day_pct(b, t - 1)
    threshold = (f"up_run <= {MAX_UP_RUN}, counting days above +{UP_DAY_PCT}%; "
                 f"veto at {VETO_UP_DAYS}+ up closes of any size")
    if prior is None:
        return Check("two_days", "2", "not up two days in a row", {"up_run": None, "up_closes": None,
                     "prior_day_pct": None}, threshold, None, False,
                     "the session before the burst could not be read")
    run, i = 0, t - 1
    while i >= 1:
        pct = _day_pct(b, i)
        if pct is None or pct < 0:
            break
        if pct > UP_DAY_PCT:
            run += 1
        i -= 1
    closes, i = 0, t - 1
    while i >= 1 and np.isfinite(b.c[i]) and np.isfinite(b.c[i - 1]) and b.c[i] > b.c[i - 1]:
        closes += 1
        i -= 1
    passed = run <= MAX_UP_RUN
    # A+ is "up_run == 0 or the prior day negative": a negative prior day
    # breaks the run before it starts, so the second clause is inside the first.
    a_plus = run == 0
    note = ""
    if closes >= VETO_UP_DAYS:
        note = f"up {closes} closes in a row into the burst: refused outright"
    elif not passed:
        note = f"up {run} sessions of more than {UP_DAY_PCT}% in a row before the burst"
    return Check("two_days", "2", "not up two days in a row",
                 {"up_run": run, "up_closes": closes, "prior_day_pct": prior},
                 threshold, passed, a_plus, note)


def _check_l(leg: dict | None) -> Check:
    threshold = f"ER >= {MIN_ER} or R2 >= {MIN_R2} (both for A+); failing is a veto"
    label = "linearity of the prior leg"
    if leg is None or (leg["er"] is None and leg["r2"] is None):
        length = None if leg is None else leg["length"]
        return Check("linearity", "L", label,
                     {"er": None, "r2": None, "leg_sessions": length, "leg_gain_pct": None if leg is None else leg["gain_pct"]},
                     threshold, None, False,
                     f"no leg to measure: fewer than {MIN_LEG_SESSIONS} sessions from the low to the high before the base")
    er, r2 = leg["er"], leg["r2"]
    er_ok = er is not None and er >= MIN_ER
    r2_ok = r2 is not None and r2 >= MIN_R2
    passed = er_ok or r2_ok
    note = "" if passed else "the leg into the base is not linear: refused outright"
    return Check("linearity", "L", label,
                 {"er": er, "r2": r2, "leg_sessions": leg["length"], "leg_gain_pct": leg["gain_pct"]},
                 threshold, passed, er_ok and r2_ok, note)


def _is_breakout_bar(b: _Bars, i: int) -> bool:
    if i < 1 or not _is_burst_day(b, i):
        return False
    v, v1 = b.v[i], b.v[i - 1]
    if not (np.isfinite(v) and np.isfinite(v1) and v > v1):
        return False
    pos = _close_pos(b, i)
    return pos is not None and pos >= BREAKOUT_MIN_CLOSE_POS


def _move_start(b: _Bars) -> int | None:
    """The lowest close of the search window before the burst, preferring a
    session that closed under its own SMA; the LAST such print on a tie."""
    t = b.t
    lo, hi = max(t - MOVE_SEARCH_SESSIONS, 0), t - 1
    if hi < lo:
        return None
    sma = pd.Series(b.c).rolling(MOVE_SMA_SESSIONS).mean().to_numpy()
    closes = b.c[lo:hi + 1]
    if not np.isfinite(closes).any():
        return None
    under = np.isfinite(closes) & np.isfinite(sma[lo:hi + 1]) & (closes < sma[lo:hi + 1])
    pool = np.where(under, closes, np.nan) if under.any() else closes
    return lo + int(np.flatnonzero(pool == np.nanmin(pool))[-1])


def _check_y(b: _Bars) -> Check:
    t = b.t
    threshold = f"prior breakouts since the move started <= {MAX_PRIOR_BREAKOUTS} (0 for A+)"
    label = "young trend: first or second breakout"
    start = _move_start(b)
    if start is None:
        return Check("young_trend", "Y", label, {"breakouts_in_move": None, "sessions_since_move_start": None,
                     "gain_since_move_start_pct": None}, threshold, None, False,
                     "no session before the burst could be read")
    count = sum(1 for i in range(start + 1, t) if _is_breakout_bar(b, i))
    value = {"breakouts_in_move": count, "sessions_since_move_start": t - start,
             "gain_since_move_start_pct": _pct_of(b.c[t] - b.c[start], b.c[start])}
    passed = count <= MAX_PRIOR_BREAKOUTS
    note = "" if passed else f"today would be breakout {count + 1} of this move"
    return Check("young_trend", "Y", label, value, threshold, passed, count == 0, note)


def _check_n(b: _Bars) -> Check:
    t = b.t
    threshold = (f"prior day negative or range < {NARROW_RANGE_PCT}% "
                 f"(A+: negative and under its {NARROW_NORM_SESSIONS}-session median range)")
    label = "narrow or negative day before"
    i = t - 1
    rng = _range_pct(b, i) if i >= 0 else None
    if rng is None:
        return Check("narrow_or_negative", "N", label, {"prior_day_pct": None, "prior_range_pct": None,
                     "negative": None, "narrow": None, "median_range_pct": None},
                     threshold, None, False, "the session before the burst could not be read")
    negative = None
    if i >= 1 and np.isfinite(b.c[i - 1]):
        negative = bool(b.c[i] < b.c[i - 1])
    narrow = rng < NARROW_RANGE_PCT
    median = _r(np.median(_range_pcts(b, i - NARROW_NORM_SESSIONS, i - 1)), PCT_DECIMALS) \
        if _range_pcts(b, i - NARROW_NORM_SESSIONS, i - 1) else None
    passed = bool(negative) or narrow
    a_plus = bool(negative) and median is not None and rng < median
    note = "" if passed else "the session before the burst was up and not narrow"
    return Check("narrow_or_negative", "N", label,
                 {"prior_day_pct": _day_pct(b, i), "prior_range_pct": rng, "negative": negative,
                  "narrow": narrow, "median_range_pct": median},
                 threshold, passed, a_plus, note)


def _check_c(b: _Bars, base: dict | None, leg: dict | None) -> Check:
    t = b.t
    threshold = (f"base {BASE_MIN}-{BASE_MAX} sessions, breakdowns <= {MAX_BREAKDOWNS}, "
                 f"giveback <= {MAX_GIVEBACK}, tightness <= {MAX_TIGHTNESS} "
                 f"(A+: 0 breakdowns, 0 bursts inside, giveback <= {A_PLUS_MAX_GIVEBACK}, "
                 f"tightness <= {A_PLUS_MAX_TIGHTNESS}, base volume under the leg's and the "
                 f"{VOLUME_AVG_SESSIONS}-session average)")
    label = "consolidation quality"
    empty = {"base_sessions": None, "breakdowns": None, "bursts_in_base": None, "giveback": None,
             "tightness": None, "base_volume_vs_leg": None, "base_volume_vs_avg": None}
    if base is None:
        return Check("consolidation", "C", label, empty, threshold, None, False,
                     "no base could be located before the burst")
    start, end, length = base["start"], base["end"], base["length"]
    breakdowns = sum(1 for i in range(start, end + 1) if _is_breakdown_day(b, i))
    bursts = sum(1 for i in range(start, end + 1) if _is_burst_day(b, i))
    giveback = None
    if leg is not None and base["low"] is not None and leg["low"] is not None:
        giveback = _ratio(base["high"] - base["low"], base["high"] - leg["low"])
    base_range = _mean(_range_pcts(b, start, end))
    norm_range = _mean(_range_pcts(b, start - TIGHTNESS_NORM_SESSIONS, start - 1))
    tightness = _ratio(base_range, norm_range)
    base_vol = _mean(b.v[start:end + 1])
    leg_vol = None if leg is None else _mean(b.v[leg["start"]:leg["end"] + 1])
    avg_vol = _mean(b.v[max(t - VOLUME_AVG_SESSIONS, 0):t])
    value = {"base_sessions": length, "breakdowns": breakdowns, "bursts_in_base": bursts,
             "giveback": giveback, "tightness": tightness,
             "base_volume_vs_leg": _ratio(base_vol, leg_vol), "base_volume_vs_avg": _ratio(base_vol, avg_vol)}
    if giveback is None or tightness is None:
        return Check("consolidation", "C", label, value, threshold, None, False,
                     "the base's depth or tightness could not be measured against the sessions before it")
    core = breakdowns <= MAX_BREAKDOWNS and giveback <= MAX_GIVEBACK and tightness <= MAX_TIGHTNESS
    in_band = BASE_MIN <= length <= BASE_MAX
    passed = core and in_band
    partial = core and not in_band and length >= PARTIAL_BASE_MIN
    a_plus = (passed and breakdowns == 0 and bursts == 0 and giveback <= A_PLUS_MAX_GIVEBACK
              and tightness <= A_PLUS_MAX_TIGHTNESS and value["base_volume_vs_leg"] is not None
              and value["base_volume_vs_leg"] < 1 and value["base_volume_vs_avg"] is not None
              and value["base_volume_vs_avg"] < 1)
    notes = []
    if not in_band:
        notes.append(f"base of {length} sessions is outside Bonde's {BASE_MIN}-{BASE_MAX}")
    if breakdowns > MAX_BREAKDOWNS:
        notes.append(f"{breakdowns} 4% breakdowns inside the base")
    if giveback > MAX_GIVEBACK:
        notes.append(f"the base gave back {giveback} of the leg")
    if tightness > MAX_TIGHTNESS:
        notes.append("the base ranged wider than the sessions before it")
    return Check("consolidation", "C", label, value, threshold, passed, a_plus,
                 "; ".join(notes), partial)


def _check_h(b: _Bars, problem: str | None) -> Check:
    t = b.t
    threshold = (f"close_pos >= {MIN_CLOSE_POS} and close > open "
                 f"(A+ >= {A_PLUS_CLOSE_POS}; partial from {PARTIAL_CLOSE_POS})")
    label = "close near the high"
    if problem is not None:
        return Check("close_near_high", "H", label, {"close_pos": None, "close_above_open": None},
                     threshold, None, False, problem)
    pos = _close_pos(b, t)
    up = bool(b.c[t] > b.o[t])
    passed = up and pos >= MIN_CLOSE_POS
    partial = up and not passed and pos >= PARTIAL_CLOSE_POS
    a_plus = up and pos >= A_PLUS_CLOSE_POS
    note = ""
    if not up:
        note = "closed at or below its open: not near the high by his C - O sort"
    elif partial:
        note = f"closed in the community's {PARTIAL_CLOSE_POS} band, under his {MIN_CLOSE_POS}"
    elif not passed:
        note = "closed well off the high"
    return Check("close_near_high", "H", label, {"close_pos": pos, "close_above_open": up},
                 threshold, passed, a_plus, note, partial)


def _expansion(b: _Bars, sessions: int) -> float | None:
    t = b.t
    if t - sessions < 0:
        return None
    prior = [_range_pct(b, i) for i in range(t - sessions, t)]
    if any(p is None for p in prior):
        return None
    return _ratio(_range_pct(b, t), max(prior))


def _check_re(b: _Bars, problem: str | None) -> Check:
    threshold = (f"today's range over the largest of the prior {RE_WINDOW} >= {MIN_RANGE_EXPANSION} "
                 f"(A+: also over the prior {RE_WINDOW_LONG})")
    label = "range expansion"
    short = None if problem else _expansion(b, RE_WINDOW)
    long = None if problem else _expansion(b, RE_WINDOW_LONG)
    value = {"vs_prior_5": short, "vs_prior_10": long, "bar_range_pct": None if problem else _range_pct(b, b.t)}
    if short is None:
        note = problem or f"the prior {RE_WINDOW} sessions' ranges could not all be read"
        return Check("range_expansion", "RE", label, value, threshold, None, False, note)
    passed = short >= MIN_RANGE_EXPANSION
    a_plus = passed and long is not None and long >= MIN_RANGE_EXPANSION
    note = "" if passed else "the burst bar is not the widest of the last five"
    return Check("range_expansion", "RE", label, value, threshold, passed, a_plus, note)


def _volume_block(b: _Bars) -> dict:
    t = b.t
    v, v1 = b.v[t], b.v[t - 1] if t >= 1 else np.nan
    avg = _mean(b.v[max(t - VOLUME_AVG_SESSIONS, 0):t])
    window = b.v[max(t - VOLUME_RANK_SESSIONS + 1, 0):t + 1]
    rank = None
    if np.isfinite(v):
        rank = 1 + int(np.nansum(window > v))
    return {"volume_vs_prior": _ratio(v, v1), "volume_vs_avg50": _ratio(v, avg),
            "volume_rank_60": rank}


def _check_vol(b: _Bars, base: dict | None) -> Check:
    t = b.t
    threshold = (f"volume > prior session (A+: rank <= {A_PLUS_MAX_VOLUME_RANK} of the last "
                 f"{VOLUME_RANK_SESSIONS}); a base over {CV_BASE_SESSIONS} sessions also needs "
                 f">= {CV_MIN_VOLUME}x the {VOLUME_AVG_SESSIONS}-session average")
    label = "higher volume"
    block = _volume_block(b)
    cv_required = base is not None and base["length"] > CV_BASE_SESSIONS
    value = {**block, "cv_required": cv_required}
    v, v1 = b.v[t], b.v[t - 1] if t >= 1 else np.nan
    if not (np.isfinite(v) and np.isfinite(v1)):
        return Check("volume", "VOL", label, value, threshold, None, False,
                     "today's or the prior session's volume could not be read")
    passed = bool(v > v1)
    note = "" if passed else "volume did not exceed the prior session's"
    if cv_required:
        vs_avg = block["volume_vs_avg50"]
        if vs_avg is None:
            return Check("volume", "VOL", label, value, threshold, None, False,
                         f"base over {CV_BASE_SESSIONS} sessions and no {VOLUME_AVG_SESSIONS}-session average to hold it to")
        passed = passed and vs_avg >= CV_MIN_VOLUME
        note = (f"base over {CV_BASE_SESSIONS} sessions: +CV applies, volume must be "
                f">= {CV_MIN_VOLUME}x average and a catalyst is needed, which bars cannot show")
    rank = block["volume_rank_60"]
    a_plus = passed and rank is not None and rank <= A_PLUS_MAX_VOLUME_RANK
    return Check("volume", "VOL", label, value, threshold, passed, a_plus, note)


# --------------------------------------------------------------- notes ----


def _notes(b: _Bars, base: dict | None, leg: dict | None, burst: dict) -> list[str]:
    t = b.t
    notes = []
    sma_from = t - EXTENSION_SMA_SESSIONS + 1
    sma = _mean(b.c[sma_from:t + 1]) if sma_from >= 0 and np.isfinite(b.c[sma_from:t + 1]).all() else None
    ext = _pct_of(b.c[t] - sma, sma) if sma is not None else None
    run_up = _pct_of(b.c[t] - b.c[t - RUN_UP_SESSIONS], b.c[t - RUN_UP_SESSIONS]) \
        if t - RUN_UP_SESSIONS >= 0 else None
    if ext is not None or run_up is not None:
        notes.append(f"extension: close {ext}% vs its {EXTENSION_SMA_SESSIONS}-SMA, "
                     f"{run_up}% over {RUN_UP_SESSIONS} sessions")
    if np.isfinite(b.c[t]) and b.c[t] < LOW_PRICE:
        notes.append(f"price under ${LOW_PRICE:.0f}: explosive, wider stops")
    gain = burst.get("gain_pct")
    if gain is not None and gain >= HIGH_GAIN_PCT:
        notes.append(f"gain of {gain}% is {HIGH_GAIN_PCT:.0f}% or more: the worst cell in the only "
                     "event study, a 36% win rate and -9.3% at 20 sessions")
    prior = [i for i in range(max(t - HISTORY_SESSIONS, 1), t) if _is_burst_day(b, i)]
    judged = [i for i in prior[-HISTORY_MAX_BREAKOUTS:] if i + HISTORY_FOLLOW_SESSIONS <= t
              and np.isfinite(b.c[i + HISTORY_FOLLOW_SESSIONS])]
    if judged:
        worked = sum(1 for i in judged if b.c[i + HISTORY_FOLLOW_SESSIONS] > b.c[i])
        notes.append(f"prior breakouts worked {worked} of {len(judged)} (closed higher "
                     f"{HISTORY_FOLLOW_SESSIONS} sessions later, last {HISTORY_MAX_BREAKOUTS} in "
                     f"{HISTORY_SESSIONS} sessions)")
    if leg is not None and leg["gain_pct"] is not None and leg["gain_pct"] >= FAST_LEG_MIN_GAIN_PCT \
            and leg["length"] <= FAST_LEG_MAX_SESSIONS:
        notes.append(f"first leg of {leg['gain_pct']}% in {leg['length']} sessions: his "
                     f"'{FAST_LEG_MIN_GAIN_PCT:.0f}% plus in {FAST_LEG_MAX_SESSIONS} days or less'")
    return notes


# ------------------------------------------------------- score and grade ----


def score_of(checks: list[Check]) -> tuple[float, int, int]:
    """(score, passes, a_plus_count): passed letters earn their weight, a
    partial half of it; the A+ tally runs over every check."""
    score = 0.0
    passes = 0
    for check in checks:
        weight = WEIGHTS.get(check.letter)
        if weight is None:
            continue
        if check.passed:
            score += weight
            passes += 1
        elif check.partial:
            score += weight / 2
    a_plus = sum(1 for c in checks if c.a_plus)
    return _r(score, RATIO_DECIMALS), passes, a_plus


def grade_of(score: float, a_plus_count: int, refused: bool, gates_passed: bool = True) -> str:
    """The band src.grader assigns: A+ demoted to the next band without
    MIN_A_PLUS_LETTERS checks at their A+ standard, the two top bands capped
    at GATE_CAP unless the gate letters passed outright, any refusal skip."""
    if refused:
        return SKIP
    grade = grade_for(score)
    if grade == GRADE_BANDS[0][1] and a_plus_count < MIN_A_PLUS_LETTERS:
        grade = GRADE_BANDS[1][1]
    if grade in GATED_GRADES and not gates_passed:
        return GATE_CAP
    return grade


def _cap_note(check: Check) -> str:
    """Why a gate letter keeps the grade under the top bands, naming it."""
    if check.letter == "H":
        pos = check.value.get("close_pos")
        if check.value.get("close_above_open") is False:
            return f"capped at {GATE_CAP}: closed at or below its open"
        if pos is not None:
            return f"capped at {GATE_CAP}: closed at {int(round(pos * 100))}% of its range"
    if check.letter == "2" and check.value.get("up_run") is not None:
        return (f"capped at {GATE_CAP}: up {check.value['up_run']} sessions of more than "
                f"{UP_DAY_PCT}% in a row before the burst")
    return f"capped at {GATE_CAP}: {check.letter} is {check.status.lower()} -- {check.note}"


# ------------------------------------------------------------ public API ----


def _empty(reason: str) -> Assessment:
    return Assessment(checks=[], vetoes=[], passes=0, of=len(LETTERS), a_plus_count=0, score=0.0,
                      grade=SKIP, reclass=None, notes=[], base=None, leg=None, burst={},
                      unreadable=reason)


def assess(df: pd.DataFrame, at: int = -1) -> Assessment:
    """Bonde's checklist over the bar at ``at``, every number rounded once."""
    b = _arrays(df, at)
    if b is None:
        return _empty("the frame or the bar position could not be read")
    t = b.t
    problem = _bar_problem(b, t)
    base = _find_base(b)
    leg = None if base is None else _find_leg(b, base)
    volume = _volume_block(b)
    burst = {
        "gain_pct": _day_pct(b, t),
        "gap_pct": None if problem else _pct_of(b.o[t] - b.c[t - 1], b.c[t - 1]) if t >= 1 else None,
        "bar_range_pct": None if problem else _range_pct(b, t),
        "close_pos": None if problem else _close_pos(b, t),
        **volume,
    }
    checks = [_check_two(b), _check_l(leg), _check_y(b), _check_n(b), _check_c(b, base, leg),
              _check_h(b, problem), _check_re(b, problem), _check_vol(b, base)]
    by_letter = {c.letter: c for c in checks}
    vetoes = []
    up_closes = by_letter["2"].value["up_closes"]
    if up_closes is not None and up_closes >= VETO_UP_DAYS:
        vetoes.append(VETO_UP_DAYS_NAME)
    if by_letter["L"].passed is False:
        vetoes.append(VETO_NOT_LINEAR)
    score, passes, a_plus = score_of(checks)
    gates = [by_letter[letter] for letter in GRADE_GATE_LETTERS]
    gates_passed = all(c.passed for c in gates)
    grade = grade_of(score, a_plus, bool(vetoes) or problem is not None, gates_passed)
    others = [by_letter[letter] for letter in LETTERS if letter != "H"]
    reclass = None
    if by_letter["H"].passed is False and not vetoes and all(c.passed for c in others):
        reclass = RECLASS_ANTICIPATION
    public_base = None if base is None else {k: v for k, v in base.items() if k != "peak"}
    notes = _notes(b, base, leg, burst)
    if grade == GATE_CAP and not gates_passed:
        notes.extend(_cap_note(c) for c in gates if not c.passed)
    return Assessment(checks=checks, vetoes=vetoes, passes=passes, of=len(LETTERS),
                      a_plus_count=a_plus, score=score, grade=grade, reclass=reclass,
                      notes=notes, base=public_base, leg=leg,
                      burst=burst, unreadable=problem)


def _summary(block: dict | None, keys: tuple[str, ...]) -> str:
    if block is None:
        return "none"
    return " ".join(f"{k}={block.get(k)}" for k in keys)


def metrics_for_model(assessment: Assessment, ticker: str, close: float,
                      extra: dict | None = None) -> dict:
    """A flat, sorted-key dict for src.grader.user_text: every check as one
    line, the vetoes, the notes and the base/leg summaries. ``extra`` is
    merged last, so a caller's key wins."""
    metrics = {
        "ticker": ticker,
        "close": close,
        "quality_grade": assessment.grade,
        "quality_score": assessment.score,
        "quality_passes": f"{assessment.passes}/{assessment.of}",
        "quality_a_plus_checks": assessment.a_plus_count,
        "checklist": [c.line() for c in assessment.checks],
        "vetoes": list(assessment.vetoes),
        "notes": list(assessment.notes),
        "reclass": assessment.reclass,
        "unreadable": assessment.unreadable,
        "base": _summary(assessment.base, ("length", "high", "low")),
        "leg": _summary(assessment.leg, ("length", "gain_pct", "er", "r2")),
        "burst": dict(assessment.burst),
    }
    if extra:
        metrics.update(extra)
    return dict(sorted(metrics.items()))
