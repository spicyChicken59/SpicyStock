"""Bonde's scans over hand-built frames: both sides of every threshold.

Every frame here is small enough to check by hand, and every boundary is
pinned on the side Bonde writes it -- inclusive where his formula says >= and
strict where it says >. A test that only exercised the comfortable middle
would pass with the comparison flipped, which is the shape this project's
notes call a test that cannot fail.
"""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src import scans
from src.scans import COLUMNS

END = "2026-09-10"
SOURCE = Path(__file__).resolve().parent.parent / "src" / "scans.py"


# ------------------------------------------------------------- builders ----


def bar(c: float = 100.0, *, o: float | None = None, h: float | None = None,
        l: float | None = None, v: float = 200_000) -> tuple:
    """One (Open, High, Low, Close, Volume) bar; the envelope defaults to half a
    dollar either side of the body so every bar is well formed."""
    o = c if o is None else o
    h = max(o, c) + 0.5 if h is None else h
    l = min(o, c) - 0.5 if l is None else l
    return (o, h, l, c, v)


def frame(bars: list[tuple]) -> pd.DataFrame:
    """Oldest first, one business day per bar, ending on END."""
    index = pd.bdate_range(end=END, periods=len(bars), name="timestamp")
    return pd.DataFrame(bars, index=index, columns=list(COLUMNS), dtype=float)


def flat(n: int, c: float = 100.0, v: float = 200_000) -> list[tuple]:
    return [bar(c, v=v)] * n


def burst_frame(*, c: float = 104.0, c1: float = 100.0, v: float = 200_000,
                v1: float = 150_000) -> pd.DataFrame:
    """Two flat sessions at c1 on v1, then a session closing at c on v."""
    return frame([bar(c1, v=v1)] * 2 + [bar(c, o=c1, v=v)])


def ti65_frame(b: float, *, v: float = 200_000, v_today: float | None = None) -> pd.DataFrame:
    """58 sessions at 99.40 then 7 at b: the 65-session average sits within
    0.003 of 100 and the basis-point rounding absorbs it, so avgc7/avgc65
    reads b/100 to four places. Volumes are v throughout, v_today today."""
    bars = flat(58, 99.40, v) + flat(7, b, v)
    if v_today is not None:
        bars[-1] = bar(b, v=v_today)
    return frame(bars)


def mdt_frame(c: float) -> pd.DataFrame:
    """125 sessions at 99.85 then one at c: the 126-session average sits within
    0.002 of 100, so c/avgc126 reads c/100 to four places."""
    return frame(flat(125, 99.85) + [bar(c, o=99.85)])


def dt_frame(*, c: float = 90.0, c1: float = 90.5, low_at: int = 100, low: float = 50.0,
             n: int = 252) -> pd.DataFrame:
    """n flat sessions at 100 with one low pulled down to `low` at position
    low_at, closing c1 then c: c/minl252 is c/low."""
    bars = flat(n)
    bars[low_at] = bar(100.0, l=low)
    bars[-2] = bar(c1)
    bars[-1] = bar(c, o=c1)
    return frame(bars)


def lre_frame(*, y: float = 95.0, x: float = 100.0, c2: float = 100.0, c1: float = 101.0,
              c: float = 103.0, o: float = 102.0, v: float = 200_000) -> pd.DataFrame:
    """58 sessions at y, four at x, then c2, c1 and a session opening o
    closing c. With the defaults avgc7 = 704/7 = 100.5714, avgc65 = 95.6,
    ti65 = 1.052, c/c1 = 1.0198 and c1/c2 = 1.01."""
    return frame(flat(58, y, v) + flat(4, x, v) + [bar(c2, v=v), bar(c1, v=v), bar(c, o=o, v=v)])


def ep_frame(*, c: float = 104.01, c1: float = 100.0, v: float = 300_010,
             prior_v: float = 100_000, prior: int = 50) -> pd.DataFrame:
    """`prior` sessions at c1 on prior_v, then a session closing c on v."""
    return frame(flat(prior, c1, prior_v) + [bar(c, o=c1, v=v)])


def anticipation_frame(kind: str) -> pd.DataFrame:
    """252 sessions built so exactly the named setups match on a quiet day.

    dt_ti65: closes 100 with one low at 50, the last seven closes at 106 --
      DT 106/50 = 2.12, TI65 = 106 / ((58*100 + 7*106)/65) = 1.0532, MDT
      106 / ((119*100 + 7*106)/126) = 1.0565 (under 1.19), today unchanged.
    ti65_mdt: closes 100, the last three at 121 -- avgc7 = 109, avgc65 = 101,
      TI65 1.0792; avgc126 = 100.5, MDT 1.204; lows never far below the
      close, so DT is 121/99.5 = 1.2161 (under 1.8).
    dt: closes 100 with one low at 50 -- DT 2.0, TI65 1.0, MDT 1.0.
    """
    bars = flat(252)
    if kind in ("dt_ti65", "dt"):
        bars[100] = bar(100.0, l=50.0)
    if kind == "dt_ti65":
        bars[-7:] = flat(7, 106.0)
    if kind == "ti65_mdt":
        bars[-3:] = flat(3, 121.0)
    return frame(bars)


# --------------------------------------------------------------- burst ----


def test_burst_measures_an_exact_four_percent_day_on_higher_volume():
    got = scans.burst_4pct(burst_frame())
    assert got == {"gain_pct": 4.0, "close": 104.0, "prev_close": 100.0, "volume": 200_000,
                   "prev_volume": 150_000, "volume_vs_prior": 1.3333, "dollar_volume": 20_800_000}


@pytest.mark.parametrize("c,v,v1,matches", [
    (104.0, 200_000, 150_000, True),    # c/c1 = 1.04 exactly: Bonde writes >=
    (103.99, 200_000, 150_000, False),  # 1.0399
    (104.0, 150_000, 150_000, False),   # v == v1: strict
    (104.0, 150_001, 150_000, True),
    (104.0, 100_000, 99_999, True),     # v == 100000: inclusive
    (104.0, 99_999, 50_000, False),
    (120.0, 100_000, 100_000, False),   # both volume terms, not one of them
])
def test_burst_boundaries_are_the_sides_bonde_writes(c, v, v1, matches):
    assert (scans.burst_4pct(burst_frame(c=c, v=v, v1=v1)) is not None) is matches


def test_a_close_that_prints_four_percent_is_admitted_and_one_that_prints_less_is_not():
    """259.99 / 250 is 1.03996 in the raw float, which an unrounded compare
    refuses under an archived gain of 4.0. The ratio is rounded to a basis
    point once and the rule reads that number."""
    admitted = scans.burst_4pct(burst_frame(c=259.99, c1=250.0))
    assert admitted is not None and admitted["gain_pct"] == 4.0
    refused = scans.burst_4pct(burst_frame(c=259.98, c1=250.0))
    assert refused is None and scans.pct_change(burst_frame(c=259.98, c1=250.0)) == 3.99


def test_prices_are_read_to_the_cent_and_volumes_to_the_share():
    """A split-adjusted 103.996 is the cent price 104.00 -- what the record
    prints is what the rule decided on -- and 103.994 is 103.99."""
    got = scans.burst_4pct(burst_frame(c=103.996, v=200_000.4, v1=150_000.6))
    assert got is not None and got["close"] == 104.0 and got["volume"] == 200_000
    assert got["prev_volume"] == 150_001
    assert scans.burst_4pct(burst_frame(c=103.994)) is None


def test_a_previous_session_that_printed_nothing_is_readable_and_the_ratio_is_none():
    """A zero-volume bar is a bar (a halt): v > 0 holds, and volume_vs_prior
    is None rather than a division by zero. dollar_volume is a whole dollar."""
    got = scans.burst_4pct(burst_frame(c=103.99 * 1.0001, v=200_001, v1=0))
    assert got is not None and got["volume_vs_prior"] is None and got["prev_volume"] == 0
    assert got["dollar_volume"] == 20_800_104     # 104.00 * 200,001 = 20,800,104
    half = scans.burst_4pct(burst_frame(c=104.25, v=200_003, v1=0))   # 20,850,312.75
    assert half["dollar_volume"] == 20_850_313
    assert scans.burst_4pct(burst_frame(v1=-1)) is None


@pytest.mark.parametrize("column,row", [("Close", -1), ("Close", -2), ("Volume", -1), ("Volume", -2)])
def test_a_nan_in_any_input_the_burst_reads_is_not_a_match(column, row):
    df = burst_frame()
    df.iloc[row, list(COLUMNS).index(column)] = np.nan
    assert scans.burst_4pct(df) is None


def test_a_frame_too_short_for_the_previous_close_is_not_a_match():
    assert scans.burst_4pct(burst_frame().iloc[-1:]) is None
    assert scans.burst_4pct(pd.DataFrame(columns=list(COLUMNS))) is None


def test_at_judges_an_earlier_bar_and_refuses_one_the_frame_does_not_hold():
    df = frame([bar(100.0, v=150_000), bar(104.0, o=100, v=200_000), bar(104.0, v=100_000),
                bar(104.0, v=90_000)])
    assert scans.burst_4pct(df) is None                  # tonight: 90,000 shares
    assert scans.burst_4pct(df, at=1)["gain_pct"] == 4.0
    assert scans.burst_4pct(df, at=-3)["gain_pct"] == 4.0
    assert scans.burst_4pct(df, at=0) is None            # no previous close
    assert scans.burst_4pct(df, at=4) is None and scans.burst_4pct(df, at=-5) is None
    assert scans.burst_4pct(df, at=True) is None and scans.burst_4pct(df, at=1.0) is None


@pytest.mark.parametrize("damage", ["missing_column", "duplicate_column", "text", "negative_close"])
def test_a_frame_the_scan_cannot_read_is_not_a_match(damage):
    df = burst_frame()
    if damage == "missing_column":
        df = df.drop(columns=["Volume"])
    elif damage == "duplicate_column":
        df = pd.concat([df, df[["Close"]]], axis=1)
    elif damage == "text":
        df = df.astype(object)
        df.iloc[-1, 3] = "104"
        df.iloc[-2, 3] = "n/a"
    else:
        df.iloc[-2, 3] = -100.0
    assert scans.burst_4pct(df) is None


def test_the_synthetic_burst_frame_is_a_burst_and_the_flat_one_matches_nothing(ohlcv):
    burst = scans.burst_4pct(ohlcv("burst"))
    assert burst is not None and burst["gain_pct"] == 12.0 and burst["volume_vs_prior"] > 1
    assert scans.scan_all(ohlcv("flat")) == {key: None for key in scans.SCAN_KEYS}


# ----------------------------------------------------------- breakdown ----


@pytest.mark.parametrize("c,v,v1,matches", [
    (96.0, 200_000, 150_000, True),     # c/c1 = 0.96 exactly: <=
    (96.01, 200_000, 150_000, False),
    (96.0, 150_000, 150_000, False),    # v == v1
    (96.0, 100_000, 99_999, True),
    (96.0, 99_999, 50_000, False),
])
def test_breakdown_is_the_mirror_with_the_same_volume_terms(c, v, v1, matches):
    got = scans.breakdown_4pct(burst_frame(c=c, v=v, v1=v1))
    assert (got is not None) is matches
    if matches:
        assert got["gain_pct"] == -4.0 and got["close"] == 96.0


def test_a_burst_is_never_a_breakdown_and_the_reverse():
    assert scans.breakdown_4pct(burst_frame(c=104.0)) is None
    assert scans.burst_4pct(burst_frame(c=96.0)) is None


# -------------------------------------------------------------- dollar ----


def dollar_frame(*, c: float, o: float = 23.0, v: float = 100_001, **envelope) -> pd.DataFrame:
    return frame([bar(o)] * 2 + [bar(c, o=o, v=v, **envelope)])


def test_dollar_breakout_rounds_the_move_to_cents_once():
    """23.90 - 23.00 is 0.8999999999999986 in binary; the rule reads $0.90."""
    got = scans.dollar_breakout(dollar_frame(c=23.90, h=24.0, l=22.9))
    assert got == {"move": 0.9, "close": 23.9, "open": 23.0, "volume": 100_001,
                   "close_pos_in_range": 0.9091}   # (23.9 - 22.9) / (24.0 - 22.9)


@pytest.mark.parametrize("c,v,matches", [
    (23.8999, 100_001, True),    # 89.99 cents prints $0.90 and is admitted
    (23.8949, 100_001, False),   # 89.49 cents prints $0.89
    (23.89, 100_001, False),
    (23.90, 100_000, False),     # v > 100000 is strict in this formula
    (23.90, 100_001, True),
    (22.10, 100_001, False),     # a $0.90 move DOWN
])
def test_dollar_boundaries(c, v, matches):
    assert (scans.dollar_breakout(dollar_frame(c=c, v=v)) is not None) is matches


def test_dollar_breakout_reads_the_body_and_not_the_gap():
    """Gap from 23.00 to 30.00 and close 30.50: the day's body is fifty cents."""
    assert scans.dollar_breakout(dollar_frame(c=30.50, o=30.0)) is None
    df = frame([bar(23.0)] * 2 + [bar(30.50, o=30.0, v=300_000)])
    assert scans.burst_4pct(df) is not None, "the 4% scan is the one that sees the gap"


@pytest.mark.parametrize("h,l,expected", [
    (24.0, 22.9, 0.9091),
    (23.9, 23.0, 1.0),      # closed on the high
    (23.9, 23.9, None),     # no range
    (23.0, 23.9, None),     # inverted bar
    (23.8, 23.0, None),     # close above its own high
    (np.nan, 22.9, None),
])
def test_close_position_in_range_is_none_when_the_range_cannot_be_read(h, l, expected):
    got = scans.dollar_breakout(dollar_frame(c=23.90, h=h, l=l))
    assert got is not None and got["close_pos_in_range"] == expected


@pytest.mark.parametrize("column", ["Open", "Close", "Volume"])
def test_dollar_breakout_with_an_unreadable_input_is_not_a_match(column):
    df = dollar_frame(c=23.90)
    df.iloc[-1, list(COLUMNS).index(column)] = np.nan
    assert scans.dollar_breakout(df) is None


# ------------------------------------------------------- double trouble ----


def test_double_trouble_at_exactly_one_point_eight_is_admitted():
    got = scans.double_trouble(dt_frame(c=90.0, c1=90.5))
    assert got == {"ratio": 1.8, "min_low": 50.0, "min_volume_prior": 200_000, "quiet": True,
                   "pct_change_today": -0.55}
    assert scans.double_trouble(dt_frame(c=89.99, c1=90.5)) is None


def test_the_252_low_includes_today_and_excludes_the_session_before_the_window():
    included = dt_frame(c=72.0, c1=72.5)
    included.iloc[-1, 2] = 40.0                      # today's low: 72/40 = 1.8
    assert scans.double_trouble(included)["min_low"] == 40.0
    beyond = dt_frame(c=90.0, c1=90.5, low_at=0, low=10.0, n=253)   # 253 back: out
    assert scans.double_trouble(beyond) is None
    inside = dt_frame(c=90.0, c1=90.5, low_at=1, low=10.0, n=253)   # 252 back: in
    assert scans.double_trouble(inside)["ratio"] == 9.0


@pytest.mark.parametrize("back,volume,matches", [
    (0, 1, True),          # today's own volume is not in minv3.1
    (1, 99_999, False),
    (3, 99_999, False),    # the third session back is the last one counted
    (3, 100_000, True),    # inclusive for DT
    (4, 1, True),          # the fourth is not
])
def test_the_prior_volume_window_is_three_sessions_ending_yesterday(back, volume, matches):
    df = dt_frame()
    df.iloc[-1 - back, 4] = volume
    assert (scans.double_trouble(df) is not None) is matches


def test_double_trouble_carries_the_quiet_flag_without_requiring_it():
    loud = scans.double_trouble(dt_frame(c=90.0, c1=88.0))   # +2.27%
    assert loud is not None and loud["quiet"] is False and loud["pct_change_today"] == 2.27


@pytest.mark.parametrize("damage", ["short", "nan_low", "nan_prev_close", "nan_prior_volume"])
def test_double_trouble_that_cannot_be_measured_is_not_a_match(damage):
    df = dt_frame()
    if damage == "short":
        df = df.iloc[-251:]
    elif damage == "nan_low":
        df.iloc[-200, 2] = np.nan
    elif damage == "nan_prev_close":
        df.iloc[-2, 3] = np.nan
    else:
        df.iloc[-3, 4] = np.nan
    assert scans.double_trouble(df) is None


# ------------------------------------------------------ trend intensity ----


@pytest.mark.parametrize("b,matches", [(105.01, True), (105.0, False), (104.99, False)])
def test_ti65_is_strict_at_one_point_oh_five(b, matches):
    got = scans.trend_intensity(ti65_frame(b))
    assert (got is not None) is matches
    if matches:
        assert got == {"ti65": 1.0501, "min_volume_prior": 200_000, "quiet": True,
                       "pct_change_today": 0.0}


@pytest.mark.parametrize("v,matches", [(100_000, False), (100_001, True)])
def test_ti65_prior_volume_is_strict(v, matches):
    assert (scans.trend_intensity(ti65_frame(105.01, v=v, v_today=1)) is not None) is matches


def test_ti65_needs_sixty_five_readable_closes():
    assert scans.trend_intensity(ti65_frame(105.01).iloc[-64:]) is None
    df = ti65_frame(105.01)
    df.iloc[0, 3] = np.nan
    assert scans.trend_intensity(df) is None


# -------------------------------------------------- modified double trouble ----


@pytest.mark.parametrize("c,matches", [(119.01, True), (119.0, False), (118.99, False)])
def test_mdt_is_strict_at_one_point_one_nine(c, matches):
    got = scans.modified_double_trouble(mdt_frame(c))
    assert (got is not None) is matches
    if matches:
        assert got["ratio"] == 1.1901 and got["quiet"] is False and got["pct_change_today"] == 19.19


@pytest.mark.parametrize("v,matches", [(100_000, False), (100_001, True)])
def test_mdt_prior_volume_is_strict(v, matches):
    df = mdt_frame(119.01)
    df.iloc[-4:-1, 4] = v
    assert (scans.modified_double_trouble(df) is not None) is matches


def test_mdt_needs_one_hundred_twenty_six_readable_closes():
    assert scans.modified_double_trouble(mdt_frame(119.01).iloc[-125:]) is None


# --------------------------------------------------- ti65 low-risk entry ----


def test_low_risk_entry_measures_the_expansion_off_a_quiet_day():
    got = scans.ti65_low_risk_entry(lre_frame())
    assert got == {"ti65": 1.052, "close": 103.0, "open": 102.0, "prev_close": 101.0,
                   "pct_change_today": 1.98, "prior_pct_change": 1.0, "min_volume_prior": 200_000}


@pytest.mark.parametrize("change,matches", [
    (dict(c1=102.0, c=104.05), False),   # c1/c2 = 1.02 exactly: strict <
    (dict(c1=101.99, c=104.05), True),   # 1.0199, and today 1.0202 above it
    (dict(c=102.01), False),             # c/c1 = 1.01 == c1/c2: strict >
    (dict(c=102.02), True),              # 1.0101
    (dict(o=103.0), False),              # c == o
    (dict(o=103.5), False),              # c < o
    (dict(c1=95.0, c=94.0, o=93.0), False),   # c/c1 above c1/c2 yet c < c1
    (dict(y=95.20), True),               # ti65 reads 1.05 exactly: inclusive
    (dict(y=95.21), False),              # 1.0499
    (dict(v=100_000), True),             # minv3.1 inclusive
    (dict(v=99_999), False),
])
def test_low_risk_entry_boundaries(change, matches):
    assert (scans.ti65_low_risk_entry(lre_frame(**change)) is not None) is matches


def test_low_risk_entry_price_floor_is_three_dollars_inclusive():
    cheap = lre_frame(y=2.75, x=2.90, c2=2.90, c1=2.93, c=2.99, o=2.96)
    assert scans.ti65_low_risk_entry(cheap) is None
    floor = lre_frame(y=2.75, x=2.90, c2=2.90, c1=2.93, c=3.00, o=2.96)
    assert scans.ti65_low_risk_entry(floor)["close"] == 3.0


def test_low_risk_entry_needs_two_previous_closes_and_the_ti65_window():
    assert scans.ti65_low_risk_entry(lre_frame().iloc[-64:]) is None
    df = lre_frame()
    df.iloc[-3, 3] = np.nan
    assert scans.ti65_low_risk_entry(df) is None


# ------------------------------------------------------ episodic pivot ----


def test_episodic_pivot_measures_the_gain_and_the_volume_against_the_prior_average():
    assert scans.episodic_pivot(ep_frame()) == {
        "gain_pct": 4.01, "close": 104.01, "prev_close": 100.0, "volume": 300_010,
        "volume_vs_avg": 3.0001}


@pytest.mark.parametrize("change,matches", [
    (dict(v=300_000), False),                       # 3x exactly: strict
    (dict(v=300_010), True),                        # 3.0001x
    (dict(c=104.0), False),                         # c/c1 = 1.04 exactly: strict here
    (dict(c=104.01), True),
    (dict(prior_v=50_000, v=299_999), False),       # 6x but under 300,000 shares
    (dict(prior_v=50_000, v=300_000), True),
])
def test_episodic_pivot_boundaries(change, matches):
    assert (scans.episodic_pivot(ep_frame(**change)) is not None) is matches


def test_the_fifty_session_volume_average_ends_yesterday():
    """With today's 300,010 shares wrongly averaged in, the mean is 103,922 and
    the ratio 2.887x; and the 51st session back is out of the window."""
    assert scans.episodic_pivot(ep_frame()) is not None
    df = ep_frame(prior=51)
    df.iloc[0, 4] = 90_000_000            # 51 back: must not raise the average
    assert scans.episodic_pivot(df)["volume_vs_avg"] == 3.0001
    df.iloc[1, 4] = 90_000_000            # 50 back: in the window
    assert scans.episodic_pivot(df) is None


def test_episodic_pivot_that_cannot_be_measured_is_not_a_match():
    assert scans.episodic_pivot(ep_frame(prior=49)) is None
    df = ep_frame()
    df.iloc[-20, 4] = np.nan
    assert scans.episodic_pivot(df) is None


@pytest.mark.parametrize("v,c,matches", [
    (9_000_000, 3.0, True), (8_999_999, 3.0, False), (9_000_000, 2.99, False),
])
def test_ep_9m_boundaries(v, c, matches):
    got = scans.ep_9m(frame([bar(c, v=v)]))
    assert (got is not None) is matches
    if matches:
        assert got == {"volume": 9_000_000, "close": 3.0}


# ------------------------------------------------------------ helpers ----


def test_pct_change_is_rounded_once_to_two_places():
    assert scans.pct_change(frame([bar(100.0), bar(102.35)])) == 2.35
    assert scans.pct_change(frame([bar(100.0), bar(96.0)])) == -4.0
    assert scans.pct_change(frame([bar(100.0)])) is None
    df = frame([bar(100.0), bar(102.35)])
    df.iloc[0, 3] = np.nan
    assert scans.pct_change(df) is None


@pytest.mark.parametrize("c,quiet", [
    (101.0, True), (101.01, False), (99.0, True), (98.99, False), (100.0, True),
])
def test_quiet_day_is_inclusive_at_one_percent_either_side(c, quiet):
    assert scans.quiet_day(frame([bar(100.0), bar(c)])) is quiet


def test_quiet_day_is_none_when_the_change_cannot_be_read():
    assert scans.quiet_day(frame([bar(100.0)])) is None


# -------------------------------------------------------- anticipation ----


@pytest.mark.parametrize("kind,setups", [
    ("dt_ti65", ["DT", "TI65"]), ("ti65_mdt", ["TI65", "MDT"]), ("dt", ["DT"]),
])
def test_anticipation_is_the_union_of_the_three_setups_on_a_quiet_day(kind, setups):
    got = scans.anticipation(anticipation_frame(kind))
    assert got["setups"] == setups
    for key, label in scans.SETUP_LABELS.items():
        assert (got[key] is not None) is (label in setups)
    assert got["pct_change_today"] == 0.0 and got["range_pct_today"] is not None


@pytest.mark.parametrize("c,matches", [(107.06, True), (107.07, False), (104.94, True), (104.93, False)])
def test_anticipation_requires_the_quiet_day_on_both_sides(c, matches):
    """The previous close is 106, so 107.06 is +1.0% and 107.07 is +1.01%."""
    df = anticipation_frame("dt_ti65")
    df.iloc[-1] = bar(c, o=106.0)
    got = scans.anticipation(df)
    assert (got is not None) is matches
    if matches:
        assert abs(got["pct_change_today"]) == 1.0


def test_a_quiet_day_with_no_setup_is_not_on_the_watchlist():
    assert scans.anticipation(frame(flat(252))) is None


def test_narrow_range_days_counts_the_last_seven_against_the_median_of_the_twenty_before():
    """The twenty sessions before the last seven alternate 3% and 5% ranges
    (median 4%); the last seven range 1, 1, 1, 3.5, 4, 6 and 6 percent, so
    four are below the median and the one AT it is not counted."""
    df = anticipation_frame("dt_ti65")
    for k, pct in enumerate([3.0, 5.0] * 10):
        row = len(df) - 27 + k
        df.iloc[row, 1] = 100.0 + pct / 2
        df.iloc[row, 2] = 100.0 - pct / 2
    for k, pct in enumerate([1.0, 1.0, 1.0, 3.5, 4.0, 6.0, 6.0]):
        row = len(df) - 7 + k
        df.iloc[row, 1] = 106.0 + 106.0 * pct / 200
        df.iloc[row, 2] = 106.0 - 106.0 * pct / 200
    got = scans.anticipation(df)
    assert got["narrow_range_days"] == 4 and got["range_pct_today"] == 6.0
    # The session before the twenty is not in the norm: a huge range there
    # does not move the median.
    df.iloc[len(df) - 28, 1] = 200.0
    assert scans.anticipation(df)["narrow_range_days"] == 4


def test_narrow_range_days_is_none_when_a_range_bar_cannot_be_read_and_the_setup_still_matches():
    df = anticipation_frame("dt_ti65")
    df.iloc[-10, 1] = np.nan          # a High the low window does not read
    got = scans.anticipation(df)
    assert got is not None and got["setups"] == ["DT", "TI65"]
    assert got["narrow_range_days"] is None
    inverted = anticipation_frame("dt_ti65")
    inverted.iloc[-1, 1], inverted.iloc[-1, 2] = 105.0, 107.0
    assert scans.anticipation(inverted)["range_pct_today"] is None


# ------------------------------------------------------------ scan_all ----


def test_scan_all_reports_every_nightly_scan_under_its_own_key():
    burst = scan = scans.scan_all(burst_frame())
    assert set(scan) == set(scans.SCAN_KEYS) == {"burst", "dollar", "anticipation", "ep", "ep_9m"}
    assert burst["burst"] == scans.burst_4pct(burst_frame())
    assert burst["dollar"] == scans.dollar_breakout(burst_frame())   # a $4 body on 200,000 shares
    assert burst["anticipation"] is None and burst["ep"] is None and burst["ep_9m"] is None
    watch = scans.scan_all(anticipation_frame("dt_ti65"))
    assert watch["anticipation"] == scans.anticipation(anticipation_frame("dt_ti65"))
    assert watch["burst"] is None
    assert scans.scan_all(pd.DataFrame()) == {key: None for key in scans.SCAN_KEYS}


def test_scan_all_honours_at():
    df = frame([bar(100.0, v=150_000), bar(104.0, o=100, v=200_000), bar(104.0, v=90_000)])
    assert scans.scan_all(df)["burst"] is None
    assert scans.scan_all(df, at=1)["burst"]["gain_pct"] == 4.0


# --------------------------------------------------------------- rules ----


def _module_ast() -> ast.Module:
    return ast.parse(SOURCE.read_text())


def _named_constants() -> dict[str, float]:
    """Every upper-case module-level name bound to a number."""
    found = {}
    for node in _module_ast().body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id.isupper() \
                and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, (int, float)) \
                and not isinstance(node.value.value, bool):
            found[node.targets[0].id] = node.value.value
    return found


def test_every_named_number_is_archived_in_rules_and_rules_holds_only_archivable_values():
    """RULES is read off the source: the names its values are bound to must
    be every upper-case number the module names, so a threshold added later
    cannot escape the record in silence. Values are numbers or booleans,
    because the record is JSON and a rule is a number."""
    constants = _named_constants()
    assert len(constants) >= 20
    rules_node = next(node for node in _module_ast().body
                      if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                      and node.targets[0].id == "RULES")
    read = {value.id for value in rules_node.value.values if isinstance(value, ast.Name)}
    assert set(constants) <= read, f"named but not archived: {set(constants) - read}"
    assert all(isinstance(v, (int, float, bool)) for v in scans.RULES.values())
    assert scans.RULES["burst.min_ratio"] == 1.04 and scans.RULES["burst.min_volume"] == 100_000
    assert scans.RULES["dollar.min_move"] == 0.90 and scans.RULES["dt.min_ratio"] == 1.8
    assert scans.RULES["ti65.min_ratio_exclusive"] == 1.05 and scans.RULES["mdt.min_ratio_exclusive"] == 1.19
    assert scans.RULES["ep.volume_mult_exclusive"] == 3 and scans.RULES["ep.min_volume"] == 300_000
    assert scans.RULES["ep_9m.min_volume"] == 9_000_000 and scans.RULES["quiet.max_abs_pct"] == 1.0


def test_no_function_spells_a_threshold_as_a_literal():
    """A number inside a function body is arithmetic (0, 1, 100), a session
    offset in Telechart's own notation (1 for c1, 2 for c2), or a threshold
    that should have been a named constant. The guard reads the source because
    a value check cannot tell a literal from a name that agrees with it
    tonight. The residual -- a threshold never named, at one of those four
    values -- is stated here rather than left to the guard's silence."""
    literals = {}
    for node in ast.walk(_module_ast()):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for inner in ast.walk(ast.Module(body=node.body, type_ignores=[])):
                if isinstance(inner, ast.Constant) and isinstance(inner.value, (int, float)) \
                        and not isinstance(inner.value, bool) and inner.value not in (0, 1, 2, 100):
                    literals.setdefault(node.name, []).append(inner.value)
    assert not literals, literals


def test_every_scan_returns_values_the_record_can_hold():
    """Floats, ints, bools, strings, lists of strings, nested dicts of the
    same, or None -- never a numpy scalar, which json refuses."""
    def plain(value) -> bool:
        if value is None or isinstance(value, (bool, int, float, str)):
            return type(value) in (bool, int, float, str, type(None))
        if isinstance(value, list):
            return all(plain(v) for v in value)
        return isinstance(value, dict) and all(plain(v) for v in value.values())

    for df in (burst_frame(), dollar_frame(c=23.90), anticipation_frame("dt_ti65"),
               anticipation_frame("ti65_mdt"), ep_frame(), frame([bar(3.0, v=9_000_000)])):
        assert plain(scans.scan_all(df))
    assert plain(scans.ti65_low_risk_entry(lre_frame()))
    assert plain(scans.breakdown_4pct(burst_frame(c=96.0)))
