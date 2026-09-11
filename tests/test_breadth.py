"""src.breadth: every Market Monitor formula on numbers checked by hand.

Frames are built explicitly (``frame()``), never from a random walk, so each
threshold is pinned on both sides and each window on both edges. The
per-symbol reference implementation at the bottom is a SECOND arithmetic
for the vectorised one to disagree with.
"""
from __future__ import annotations

import ast
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src import breadth
from src.breadth import BreadthDay

END = "2026-09-10"
#: Big enough that a $1+ close clears MIN_DOLLAR_VOLUME_20 on every window.
LIQUID = 1_000_000.0


def frame(closes, volumes=None, *, end: str = END, index=None) -> pd.DataFrame:
    """N sessions of bars, newest on ``end``, in the transport's column case."""
    closes = np.asarray(closes, dtype=float)
    n = len(closes)
    if index is None:
        index = pd.bdate_range(end=end, periods=n)
    volumes = np.full(n, LIQUID) if volumes is None else np.asarray(volumes, dtype=float)
    return pd.DataFrame({"Open": closes, "High": closes, "Low": closes,
                         "Close": closes, "Volume": volumes}, index=index)


def last(frames: dict) -> BreadthDay:
    """The newest observed session's counts."""
    return breadth.daily_counts(frames, breadth.observed_sessions(frames)[-1:])[0]


def one(closes, volumes=None) -> BreadthDay:
    return last({"A": frame(closes, volumes)})


def day(d: date, up4: int = 0, down4: int = 0, **kw) -> BreadthDay:
    fields = dict(up25_quarter=0, down25_quarter=0, up25_month=0, down25_month=0,
                  up50_month=0, down50_month=0, up13_34d=0, down13_34d=0,
                  pct_above_40ma=50.0, universe=1000)
    fields.update(kw)
    return BreadthDay(date=d, up4=up4, down4=down4, **fields)


def days(up4, down4, **today) -> list[BreadthDay]:
    """Ten days, oldest first; ``up4``/``down4`` an int for all or a list per
    day; ``today`` overrides the newest day's other columns."""
    n = 10
    ups = [up4] * n if isinstance(up4, int) else list(up4)
    downs = [down4] * n if isinstance(down4, int) else list(down4)
    start = date(2026, 8, 28)
    out = [day(start + timedelta(days=i), ups[i], downs[i]) for i in range(n)]
    out[-1] = day(out[-1].date, ups[-1], downs[-1], **today)
    return out


# ------------------------------------------------------- the constants ----


def test_every_numeric_constant_is_strategy_or_plumbing_and_the_strategy_ones_are_archived():
    """A number added later cannot arrive unclassified, and every strategy
    number reaches the rules block data.json carries."""
    tree = ast.parse(Path(breadth.__file__).read_text())
    numeric = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, (int, float)) \
                and node.targets[0].id.isupper():
            numeric.add(node.targets[0].id)
    strategy, plumbing = set(breadth.STRATEGY_CONSTANTS), set(breadth.PLUMBING_CONSTANTS)
    assert numeric == strategy | plumbing
    assert not strategy & plumbing
    assert {name.lower() for name in strategy} <= set(breadth.RULES)
    for name in strategy:
        assert breadth.RULES[name.lower()] == getattr(breadth, name)
    assert breadth.RULES["size_multiplier"] == breadth.SIZE_MULTIPLIER
    assert set(breadth.SIZE_MULTIPLIER) == set(breadth.VERDICTS)


# ---------------------------------------------------------- calendar ----


def test_observed_sessions_excludes_a_date_only_a_fifth_of_frames_carry():
    """One frame prints on a Saturday; four do not. Not a session."""
    weekdays = pd.bdate_range(end=END, periods=3)
    saturday = pd.Timestamp("2026-09-12")
    frames = {f"S{i}": frame([1, 2, 3], index=weekdays) for i in range(4)}
    frames["odd"] = frame([1, 2, 3, 4], index=weekdays.append(pd.DatetimeIndex([saturday])))
    got = breadth.observed_sessions(frames)
    assert got == [d.date() for d in weekdays]
    assert saturday.date() not in got


def test_observed_sessions_fraction_is_inclusive_at_the_boundary():
    """Two of four frames is exactly half, and half is in."""
    weekdays = pd.bdate_range(end=END, periods=3)
    frames = {"a": frame([1, 2, 3], index=weekdays), "b": frame([1, 2, 3], index=weekdays),
              "c": frame([1, 2], index=weekdays[:2]), "d": frame([1, 2], index=weekdays[:2])}
    assert weekdays[-1].date() in breadth.observed_sessions(frames)
    assert weekdays[-1].date() not in breadth.observed_sessions(frames, min_fraction=0.51)


def test_observed_sessions_is_oldest_first_and_empty_without_frames():
    idx = pd.bdate_range(end=END, periods=5)
    frames = {"a": frame([1] * 5, index=idx[::-1])}  # newest-first on the wire
    got = breadth.observed_sessions(frames)
    assert got == sorted(got) == [d.date() for d in idx]
    assert breadth.observed_sessions({}) == []
    with pytest.raises(ValueError):
        breadth.observed_sessions(frames, min_fraction=0)


def test_a_tz_aware_index_reads_the_same_dates_as_a_naive_one():
    """Alpaca stamps daily bars at midnight ET; the date is the wall-clock
    date the way Timestamp.date() reads it, in any zone."""
    naive = pd.bdate_range(end=END, periods=3)
    utc = naive.tz_localize("UTC") + pd.Timedelta(hours=4)
    eastern = naive.tz_localize("America/New_York")
    evening = eastern + pd.Timedelta(hours=20)  # still that date in ET, tomorrow in UTC
    a = breadth.observed_sessions({"a": frame([1, 2, 3], index=naive)})
    b = breadth.observed_sessions({"b": frame([1, 2, 3], index=utc)})
    c = breadth.observed_sessions({"c": frame([1, 2, 3], index=eastern)})
    d = breadth.observed_sessions({"d": frame([1, 2, 3], index=evening)})
    assert a == b == c == d


def test_daily_counts_refuses_a_session_the_calendar_does_not_hold():
    frames = {"a": frame([100, 104], [50_000, 200_000]),
              "b": frame([100, 104], [50_000, 200_000]),
              "c": frame([100, 104], [50_000, 200_000])}
    phantom = date(2026, 9, 12)  # one frame of three carries it: under half
    frames["a"] = frame([100, 104, 105], [50_000, 200_000, 300_000],
                        index=pd.bdate_range(end=END, periods=2).append(pd.DatetimeIndex([pd.Timestamp(phantom)])))
    with pytest.raises(ValueError, match="2026-09-12"):
        breadth.daily_counts(frames, [phantom])
    assert breadth.daily_counts(frames, []) == []


def test_a_bar_on_a_date_that_is_not_a_session_is_dropped_not_read():
    """The phantom bar must not become yesterday's close for the next scan."""
    weekdays = pd.bdate_range(end=END, periods=3)
    saturday = pd.DatetimeIndex([pd.Timestamp("2026-09-12")])
    monday = pd.DatetimeIndex([pd.Timestamp("2026-09-14")])
    idx = weekdays.append(saturday).append(monday)
    # odd: 100 on Thursday, 50 on the phantom Saturday, 104 on Monday.
    frames = {"odd": frame([100, 100, 100, 50, 104], [LIQUID] * 4 + [2 * LIQUID], index=idx)}
    for i in range(4):
        frames[f"S{i}"] = frame([1, 1, 1, 1], index=weekdays.append(monday))
    got = breadth.daily_counts(frames, [monday[0].date()])[0]
    assert got.up4 == 1  # 104 against Thursday's 100, not against 50


# ------------------------------------------------------- the 4% scans ----


@pytest.mark.parametrize("close, expected", [(104.0, 1), (103.99, 0)])
def test_up4_is_inclusive_at_four_percent(close, expected):
    assert 100.0 * (104.0 - 100.0) / 100.0 == 4.0  # the boundary is exact
    assert one([100, close], [50_000, 200_000]).up4 == expected


@pytest.mark.parametrize("close, expected", [(96.0, 1), (96.01, 0)])
def test_down4_is_inclusive_at_minus_four_percent(close, expected):
    assert 100.0 * (96.0 - 100.0) / 100.0 == -4.0
    assert one([100, close], [50_000, 200_000]).down4 == expected


@pytest.mark.parametrize("volume, expected", [(100_000, 1), (99_999, 0)])
def test_the_4pct_share_floor_is_inclusive(volume, expected):
    assert one([100, 110], [50_000, volume]).up4 == expected
    assert one([100, 90], [50_000, volume]).down4 == expected


@pytest.mark.parametrize("previous, expected", [(199_999, 1), (200_000, 0), (200_001, 0)])
def test_the_4pct_scan_needs_volume_strictly_above_the_previous_session(previous, expected):
    assert one([100, 110], [previous, 200_000]).up4 == expected
    assert one([100, 90], [previous, 200_000]).down4 == expected


def test_a_symbol_missing_any_4pct_input_is_not_measured_and_not_counted():
    """universe counts the measurable; a hole is never a healthy day."""
    frames = {
        "ok": frame([100, 110], [50_000, 200_000]),
        "nan_close": frame([100, np.nan], [50_000, 200_000]),
        "nan_prev_close": frame([np.nan, 150], [50_000, 200_000]),
        "nan_volume": frame([100, 110], [50_000, np.nan]),
        "nan_prev_volume": frame([100, 110], [np.nan, 200_000]),
        "inf_close": frame([100, np.inf], [50_000, 200_000]),
        "zero_prev_close": frame([0, 110], [50_000, 200_000]),
        "negative_volume": frame([100, 110], [50_000, -1]),
        "one_bar": frame([110], [200_000]),
    }
    got = last(frames)
    assert got.universe == 1
    assert got.up4 == 1 and got.down4 == 0


def test_the_bar_before_a_hole_is_not_yesterday():
    """A has no bar yesterday; its last two bars are 100 then 110, which a
    positional read would call +10%."""
    idx = pd.bdate_range(end=END, periods=3)
    frames = {"A": frame([100, 110], [50_000, 200_000], index=idx[[0, 2]]),
              "B": frame([1, 1, 1], index=idx), "C": frame([1, 1, 1], index=idx)}
    got = breadth.daily_counts(frames, [idx[-1].date()])[0]
    assert got.up4 == 0
    assert got.universe == 2


# ------------------------------------------------------- the windows ----


def test_up25_quarter_window_is_65_sessions_including_today():
    """66 bars: the oldest is outside a 65-window that includes today."""
    inside = [80, 90] + [100] * 63 + [124.5]    # min 90 -> +38%; a 64-window sees 100 -> +24.5%
    outside = [80] + [100] * 64 + [124.5]       # min 100 -> +24.5%; a 66-window sees 80
    assert len(inside) == len(outside) == breadth.QUARTER_SESSIONS + 1
    assert one(inside).up25_quarter == 1
    assert one(outside).up25_quarter == 0


def test_down25_quarter_window_is_65_sessions_including_today():
    inside = [130, 120] + [100] * 63 + [88]     # max 120 -> -26.7%; a 64-window sees 100 -> -12%
    outside = [140] + [100] * 64 + [76]         # max 100 -> -24%; a 66-window sees 140
    assert one(inside).down25_quarter == 1
    assert one(outside).down25_quarter == 0


def test_quarter_threshold_is_inclusive_under_the_penny_guard():
    minimum, close = 99.99, 124.99
    pct = 100.0 * ((close + breadth.PENNY) - (minimum + breadth.PENNY)) / (minimum + breadth.PENNY)
    assert pct == 25.0  # exact in float64, so >= and > differ here
    assert one([minimum] * 64 + [close]).up25_quarter == 1
    assert one([minimum] * 64 + [close - 0.01]).up25_quarter == 0
    high, close = 99.99, 74.99
    pct = 100.0 * ((close + breadth.PENNY) - (high + breadth.PENNY)) / (high + breadth.PENNY)
    assert pct == -25.0
    assert one([high] * 64 + [close]).down25_quarter == 1
    assert one([high] * 64 + [close + 0.01]).down25_quarter == 0


def test_the_penny_guard_is_applied_as_published():
    """At two cents the guard is a third of the denominator: a move that is
    exactly 25% unguarded is 16.7% guarded, and the count says so."""
    volumes = [20_000_000.0] * 65  # keeps AVGC20*AVGV20 over the floor at 2 cents
    assert 100.0 * (0.025 - 0.02) / 0.02 == pytest.approx(25.0)
    assert one([0.02] * 64 + [0.025], volumes).up25_quarter == 0
    assert 100.0 * (0.015 - 0.02) / 0.02 == pytest.approx(-25.0)
    assert one([0.02] * 64 + [0.015], volumes).down25_quarter == 0
    assert one([0.02] * 64 + [0.03], volumes).up25_quarter == 1  # +33% guarded


def test_up25_month_reads_the_close_exactly_twenty_sessions_back():
    """C20 is the bar 20 sessions before today: 22 bars, closes[-21]."""
    assert 100.0 * (125.0 - 100.0) / 100.0 == 25.0
    exactly = [90, 100] + [125] * 20          # C20 = 100 -> 25%; C19 = 125 -> 0%
    under = [90, 100] + [124.9] * 20          # C20 = 100 -> 24.9%; C21 = 90 -> 38.8%
    assert one(exactly).up25_month == 1
    assert one(under).up25_month == 0


def test_down25_month_is_inclusive_at_minus_25():
    assert 100.0 * (75.0 - 100.0) / 100.0 == -25.0
    assert one([110, 100] + [75] * 20).down25_month == 1
    assert one([110, 100] + [75.1] * 20).down25_month == 0
    assert one([60, 100] + [75] * 20).down25_month == 1  # C21 = 60 must not be read


@pytest.mark.parametrize("c20, expected", [(5.0, 1), (4.99, 0)])
def test_month_scans_need_a_five_dollar_close_twenty_back(c20, expected):
    assert one([c20] + [c20 * 1.6] * 20).up25_month == expected
    assert one([c20] + [c20 * 1.6] * 20).up50_month == expected
    assert one([c20] + [c20 * 0.4] * 20).down25_month == expected
    assert one([c20] + [c20 * 0.4] * 20).down50_month == expected


def test_fifty_percent_month_is_inclusive_and_nested_inside_25():
    assert 100.0 * (150.0 - 100.0) / 100.0 == 50.0
    up = one([100] + [150] * 20)
    assert (up.up50_month, up.up25_month) == (1, 1)
    up = one([100] + [149.9] * 20)
    assert (up.up50_month, up.up25_month) == (0, 1)
    down = one([100] + [50] * 20)
    assert (down.down50_month, down.down25_month) == (1, 1)
    down = one([100] + [50.1] * 20)
    assert (down.down50_month, down.down25_month) == (0, 1)


def test_up13_34d_window_is_34_sessions_including_today():
    inside = [80, 90] + [100] * 32 + [112.9]    # min 90 -> +25%; a 33-window sees 100 -> +12.9%
    outside = [80] + [100] * 33 + [112.9]       # min 100 -> +12.9%; a 35-window sees 80
    assert len(inside) == len(outside) == breadth.SESSIONS_34 + 1
    assert one(inside).up13_34d == 1
    assert one(outside).up13_34d == 0


def test_down13_34d_window_is_34_sessions_including_today():
    inside = [130, 110] + [100] * 32 + [95]     # max 110 -> -13.6%; a 33-window sees 100 -> -5%
    outside = [130] + [100] * 33 + [88]         # max 100 -> -12%; a 35-window sees 130
    assert one(inside).down13_34d == 1
    assert one(outside).down13_34d == 0


def test_13_pct_threshold_is_inclusive_under_the_penny_guard():
    minimum, close = 99.99, 112.99
    pct = 100.0 * ((close + breadth.PENNY) - (minimum + breadth.PENNY)) / (minimum + breadth.PENNY)
    assert pct == 13.0
    assert one([minimum] * 33 + [close]).up13_34d == 1
    assert one([minimum] * 33 + [close - 0.01]).up13_34d == 0
    high, close = 99.99, 86.99
    pct = 100.0 * ((close + breadth.PENNY) - (high + breadth.PENNY)) / (high + breadth.PENNY)
    assert pct == -13.0
    assert one([high] * 33 + [close]).down13_34d == 1
    assert one([high] * 33 + [close + 0.01]).down13_34d == 0


def test_the_dollar_volume_floor_is_the_product_of_two_averages_inclusive():
    """AVGC20*AVGV20, not the average of C*V: anti-correlated closes and
    volumes pass the published form and fail the other."""
    closes = [100] + [100] * 10 + [200] * 10          # C20 = 100, C = 200, avgc20 = 150
    volumes = [LIQUID] + [3000] * 10 + [500] * 10       # avgv20 = 1750 -> 262,500
    assert np.mean(closes[-20:]) * np.mean(volumes[-20:]) == 262_500
    assert np.mean(np.array(closes[-20:]) * np.array(volumes[-20:])) == 200_000
    assert one(closes, volumes).up50_month == 1
    flat = [100] + [125] * 20                            # avgc20 = 125
    assert one(flat, [LIQUID] + [2000] * 20).up25_month == 1     # 250,000 exactly
    assert one(flat, [LIQUID] + [1999.99] * 20).up25_month == 0


def test_the_liquidity_floor_gates_every_window_column():
    """Each case's volumes sit a hair under and exactly on its own floor,
    which is MIN_DOLLAR_VOLUME_20 over that case's 20-session mean close."""
    cases = (([100] + [160] * 20, "up50_month"), ([100] + [50] * 20, "down50_month"),
             ([100] + [125] * 20, "up25_month"), ([200] + [125] * 20, "down25_month"),
             ([100] * 45 + [160] * 20, "up25_quarter"), ([200] * 45 + [125] * 20, "down25_quarter"),
             ([100] * 14 + [125] * 20, "up13_34d"), ([200] * 14 + [160] * 20, "down13_34d"))
    for closes, column in cases:
        n = len(closes)
        on_floor = breadth.MIN_DOLLAR_VOLUME_20 / np.mean(closes[-20:])
        assert np.mean(closes[-20:]) * on_floor == breadth.MIN_DOLLAR_VOLUME_20  # exact
        liquid = [LIQUID] * (n - 20) + [on_floor] * 20
        thin = [LIQUID] * (n - 20) + [on_floor * 0.999] * 20
        assert getattr(one(closes, thin), column) == 0, column
        assert getattr(one(closes, liquid), column) == 1, column


@pytest.mark.parametrize("how", ["nan", "missing_row"])
def test_a_hole_inside_a_window_leaves_that_column_unmeasured(how):
    """The 4% columns still read (today and yesterday are fine); the quarter
    column needs all 65 and is silent rather than a shorter window."""
    closes = [100.0] * 64 + [130.0]
    volumes = [LIQUID] * 63 + [LIQUID, 2 * LIQUID]
    idx = pd.bdate_range(end=END, periods=65)
    a = frame(closes, volumes, index=idx)
    if how == "nan":
        a.iloc[10, a.columns.get_loc("Close")] = np.nan
    else:
        a = a.drop(idx[10])
    frames = {"A": a, "B": frame([1.0] * 65, index=idx), "C": frame([1.0] * 65, index=idx)}
    got = breadth.daily_counts(frames, [idx[-1].date()])[0]
    assert got.up4 == 1 and got.universe == 3
    assert got.up25_quarter == 0
    assert got.up13_34d == 1  # the hole is outside the 34-window


# ---------------------------------------------------------- the MA ----


def test_pct_above_40ma_counts_only_symbols_with_a_full_window():
    """A above, B below, C exactly on it (not above), D rising but 39 bars."""
    frames = {
        "A": frame([100] * 39 + [105]),
        "B": frame([100] * 39 + [95]),
        "C": frame([100] * 40),
        "D": frame([100] * 38 + [105]),
    }
    got = last(frames)
    assert got.pct_above_40ma == pytest.approx(33.3)
    assert last({"D": frames["D"], "E": frame([1] * 39)}).pct_above_40ma is None


def test_pct_above_40ma_uses_a_40_session_average():
    """41 bars whose oldest is 1000: in a 41-window the average is over 105."""
    got = one([1000] + [100] * 39 + [105])
    assert got.pct_above_40ma == 100.0


# ------------------------------------------------------------ ratios ----


def test_ratios_sums_exactly_the_last_window_days():
    seq = days([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 1)
    assert breadth.ratios(seq, 5) == (40, 5, 8.0)
    assert breadth.ratios(seq, 6) == (45, 6, 7.5)
    assert breadth.ratios(seq, 10) == (55, 10, 5.5)


def test_ratio_is_none_on_a_zero_denominator_and_the_sums_are_kept():
    assert breadth.ratios(days(3, 0), 5) == (15, 0, None)
    assert breadth.ratios(days(0, 0), 10) == (0, 0, None)


def test_ratio_is_rounded_once_to_two_decimals():
    assert breadth.ratios(days(10, 3), 1) == (10, 3, 3.33)
    assert breadth.RATIO_DECIMALS == 2


def test_ratios_refuses_a_short_history_or_a_bad_window():
    with pytest.raises(ValueError, match="needs 10 days"):
        breadth.ratios(days(1, 1)[:9], 10)
    with pytest.raises(ValueError):
        breadth.ratios(days(1, 1), 0)


# ------------------------------------------------------------ regime ----


def test_green_states_every_rule_it_cleared_with_value_and_threshold():
    got = breadth.regime(days(30, 10, up50_month=5))
    assert got["verdict"] == "green"
    assert got["size_multiplier"] == 1.0
    text = " | ".join(got["reasons"])
    assert "10-session ratio 3.0" in text and ">= 2.0" in text and ">= 1.0" in text
    assert "5-session ratio 3.0" in text and ">= 0.5" in text
    assert "10 stocks down 4% today < 700" in text
    assert "5 stocks up 50% in a month <= 20" in text
    assert len(got["reasons"]) == len(set(got["reasons"]))


@pytest.mark.parametrize("up4, verdict", [(15, "yellow"), (20, "green")])
def test_yellow_when_the_10_session_ratio_is_under_2(up4, verdict):
    got = breadth.regime(days(up4, 10))
    assert got["verdict"] == verdict
    if verdict == "yellow":
        assert got["size_multiplier"] == 0.5
        assert any("10-session ratio 1.5" in r and "< 2.0" in r for r in got["reasons"])


@pytest.mark.parametrize("up50, verdict", [(21, "yellow"), (20, "green")])
def test_yellow_when_more_than_20_names_are_up_50_in_a_month(up50, verdict):
    got = breadth.regime(days(30, 10, up50_month=up50))
    assert got["verdict"] == verdict
    if verdict == "yellow":
        assert any(f"{up50} stocks up 50% in a month > 20" in r for r in got["reasons"])


@pytest.mark.parametrize("down4, verdict", [(700, "red"), (699, "green")])
def test_red_on_700_stocks_down_4_pct_today(down4, verdict):
    seq = days([30] * 9 + [3000], [10] * 9 + [down4])
    up10, down10, r10 = breadth.ratios(seq, 10)
    assert r10 >= breadth.YELLOW_RATIO_10D  # the ratio rules stay clear
    got = breadth.regime(seq)
    assert got["verdict"] == verdict
    if verdict == "red":
        assert got["size_multiplier"] == 0.0
        assert any("700 stocks down 4% today >= 700" in r for r in got["reasons"])


@pytest.mark.parametrize("up4, verdict", [(9, "red"), (10, "yellow")])
def test_red_when_the_10_session_ratio_is_under_1(up4, verdict):
    got = breadth.regime(days(up4, 10))
    assert got["verdict"] == verdict
    if verdict == "red":
        assert any("10-session ratio 0.9" in r and "< 1.0" in r for r in got["reasons"])


def test_red_on_a_fast_selling_phase_needs_both_halves():
    """5-session ratio under 0.5 AND more down than up today."""
    selling = days([100] * 5 + [4] * 5, 10)
    up10, down10, r10 = breadth.ratios(selling, 10)
    up5, down5, r5 = breadth.ratios(selling, 5)
    assert r10 >= breadth.YELLOW_RATIO_10D and r5 == 0.4
    got = breadth.regime(selling)
    assert got["verdict"] == "red"
    assert any("5-session ratio 0.4" in r and "< 0.5" in r and "10 down vs 4 up" in r
               for r in got["reasons"])
    # today's up equals its down: not a selling phase, so green
    balanced = days([100] * 5 + [0] * 4 + [10], 10)
    assert breadth.ratios(balanced, 5)[2] == 0.2
    got = breadth.regime(balanced)
    assert got["verdict"] == "green"
    assert any("< 0.5 but 10 up vs 10 down today" in r for r in got["reasons"])
    # ratio exactly 0.5 with more down than up: not under, so green
    edge = days([100] * 5 + [5] * 5, 10)
    assert breadth.ratios(edge, 5)[2] == 0.5
    assert breadth.regime(edge)["verdict"] == "green"


def test_red_wins_over_yellow_and_reasons_are_the_red_ones():
    got = breadth.regime(days(9, 10, up50_month=50))
    assert got["verdict"] == "red"
    assert all("< 1.0" in r for r in got["reasons"])


def test_an_undefined_ratio_fires_no_rule_and_is_said_in_words():
    got = breadth.regime(days(3, 0))
    assert got["verdict"] == "green"
    assert got["inputs"]["ratio_10d"] is None and got["inputs"]["ratio_5d"] is None
    assert any("10-session ratio undefined (30 up, 0 down)" in r for r in got["reasons"])


@pytest.mark.parametrize("down25, flag", [(199, True), (200, False)])
def test_oversold_extreme_is_a_flag_and_not_a_verdict_input(down25, flag):
    got = breadth.regime(days(30, 10, down25_quarter=down25))
    assert got["oversold_extreme"] is flag
    assert got["verdict"] == "green"
    assert got["inputs"]["down25_quarter"] == down25


def test_regime_refuses_no_days_and_a_day_that_measured_nothing():
    with pytest.raises(ValueError):
        breadth.regime([])
    with pytest.raises(ValueError, match="no symbol was measurable"):
        breadth.regime(days(30, 10, universe=0))


def test_regime_echoes_the_inputs_it_read():
    got = breadth.regime(days(30, 10, up50_month=7, down25_quarter=150))
    assert got["inputs"] == {
        "date": "2026-09-06", "ratio_10d": 3.0, "ratio_5d": 3.0,
        "up4_10d": 300, "down4_10d": 100, "up4_5d": 150, "down4_5d": 50,
        "up4": 30, "down4": 10, "up50_month": 7, "down25_quarter": 150,
    }
    assert breadth.SIZE_MULTIPLIER == {"green": 1.0, "yellow": 0.5, "red": 0.0}


# ---------------------------------------------------------- snapshot ----


def _market(sessions: int, symbols: int = 3) -> dict:
    """Small deterministic market: closes drift, one symbol bursts often."""
    idx = pd.bdate_range(end=END, periods=sessions)
    frames = {}
    for j in range(symbols):
        closes = 100.0 + np.arange(sessions) * (0.1 * (j + 1))
        volumes = np.full(sessions, LIQUID)
        if j == 0:
            closes[::3] *= 1.05
            volumes[::3] *= 2
        frames[f"S{j}"] = frame(closes, volumes, index=idx)
    return frames


def test_snapshot_history_is_the_last_30_full_window_days_oldest_first():
    frames = _market(60)
    session = breadth.observed_sessions(frames)[-1]
    snap = breadth.snapshot(frames, session)
    history = snap["history"]
    assert len(history) == breadth.HISTORY_SESSIONS == 30
    dates = [h["date"] for h in history]
    assert dates == sorted(dates) and dates[-1] == session.isoformat()
    assert set(history[0]) == {"date", "up4", "down4", "ratio_10d"}
    # every history ratio is the 10-session ratio over daily_counts, by hand
    calendar = breadth.observed_sessions(frames)
    counts = breadth.daily_counts(frames, calendar)
    by_date = {d.date.isoformat(): d for d in counts}
    for h in history:
        i = calendar.index(date.fromisoformat(h["date"]))
        window = counts[i - 9:i + 1]
        up, down = sum(d.up4 for d in window), sum(d.down4 for d in window)
        assert (h["up4"], h["down4"]) == (by_date[h["date"]].up4, by_date[h["date"]].down4)
        assert h["ratio_10d"] == (None if down == 0 else round(up / down, 2))


def test_snapshot_history_shrinks_to_the_days_with_a_full_window():
    frames = _market(25)
    snap = breadth.snapshot(frames, breadth.observed_sessions(frames)[-1])
    assert len(snap["history"]) == 25 - breadth.RATIO_LONG_SESSIONS + 1
    assert len(breadth.snapshot(frames, breadth.observed_sessions(frames)[-1], history_sessions=4)["history"]) == 4


def test_snapshot_carries_todays_columns_ratios_regime_and_rules():
    frames = _market(60)
    session = breadth.observed_sessions(frames)[-1]
    snap = breadth.snapshot(frames, session)
    today = breadth.daily_counts(frames, [session])[0]
    for key, value in today.to_dict().items():
        assert snap[key] == value
    calendar = breadth.observed_sessions(frames)
    counts = breadth.daily_counts(frames, calendar[-10:])
    assert (snap["up4_10d"], snap["down4_10d"], snap["ratio_10d"]) == breadth.ratios(counts, 10)
    assert (snap["up4_5d"], snap["down4_5d"], snap["ratio_5d"]) == breadth.ratios(counts, 5)
    assert snap["regime"] == breadth.regime(counts)
    assert snap["rules"] == breadth.RULES and snap["rules"] is not breadth.RULES
    assert snap["regime"]["verdict"] in breadth.VERDICTS


def test_snapshot_refuses_a_session_off_the_calendar_and_a_bad_history_length():
    frames = _market(30)
    with pytest.raises(ValueError, match="2026-09-12"):
        breadth.snapshot(frames, date(2026, 9, 12))
    with pytest.raises(ValueError):
        breadth.snapshot(frames, breadth.observed_sessions(frames)[-1], history_sessions=0)


def test_to_dict_is_json_ready():
    d = day(date(2026, 9, 10), 3, 1).to_dict()
    assert d["date"] == "2026-09-10" and d["up4"] == 3 and d["universe"] == 1000
    assert set(d) == {f.name for f in BreadthDay.__dataclass_fields__.values()}


# --------------------------------------------- a second arithmetic ----


def _reference(frames: dict, calendar: list[date], session: date) -> dict:
    """Bonde's formulas per symbol, on the calendar-aligned series, with
    pandas rolling windows. Slow and independent of src.breadth."""
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in calendar])
    i = calendar.index(session)
    out = {k: 0 for k in ("up4", "down4", "up25_quarter", "down25_quarter", "up25_month",
                          "down25_month", "up50_month", "down50_month", "up13_34d",
                          "down13_34d", "universe")}
    above = measured_ma = 0
    for df in frames.values():
        s = df.copy()
        s.index = s.index.tz_localize(None) if s.index.tz is not None else s.index
        s.index = s.index.normalize()
        s = s[~s.index.duplicated(keep="last")].reindex(idx)
        c = s["Close"].where(s["Close"] > 0)
        v = s["Volume"].where(s["Volume"] >= 0)
        C, C1, V, V1 = c.iloc[i], c.shift(1).iloc[i], v.iloc[i], v.shift(1).iloc[i]
        if all(np.isfinite(x) for x in (C, C1, V, V1)):
            out["universe"] += 1
            chg = 100 * (C - C1) / C1
            if chg >= 4 and V >= 100000 and V > V1:
                out["up4"] += 1
            if chg <= -4 and V >= 100000 and V > V1:
                out["down4"] += 1
        avgc20 = c.rolling(20, min_periods=20).mean().iloc[i]
        avgv20 = v.rolling(20, min_periods=20).mean().iloc[i]
        liquid = np.isfinite(avgc20) and np.isfinite(avgv20) and avgc20 * avgv20 >= 250000
        minc65 = c.rolling(65, min_periods=65).min().iloc[i]
        maxc65 = c.rolling(65, min_periods=65).max().iloc[i]
        if np.isfinite(C) and np.isfinite(minc65) and liquid:
            if 100 * ((C + .01) - (minc65 + .01)) / (minc65 + .01) >= 25:
                out["up25_quarter"] += 1
            if 100 * ((C + .01) - (maxc65 + .01)) / (maxc65 + .01) <= -25:
                out["down25_quarter"] += 1
        C20 = c.shift(20).iloc[i]
        if np.isfinite(C) and np.isfinite(C20) and liquid and C20 >= 5:
            move = 100 * (C - C20) / C20
            out["up25_month"] += move >= 25
            out["down25_month"] += move <= -25
            out["up50_month"] += move >= 50
            out["down50_month"] += move <= -50
        minc34 = c.rolling(34, min_periods=34).min().iloc[i]
        maxc34 = c.rolling(34, min_periods=34).max().iloc[i]
        if np.isfinite(C) and np.isfinite(minc34) and liquid:
            out["up13_34d"] += 100 * ((C + .01) - (minc34 + .01)) / (minc34 + .01) >= 13
            out["down13_34d"] += 100 * ((C + .01) - (maxc34 + .01)) / (maxc34 + .01) <= -13
        avgc40 = c.rolling(40, min_periods=40).mean().iloc[i]
        if np.isfinite(C) and np.isfinite(avgc40):
            measured_ma += 1
            above += C > avgc40
    out["pct_above_40ma"] = round(100 * above / measured_ma, 1) if measured_ma else None
    return {k: int(v) if k != "pct_above_40ma" else v for k, v in out.items()}


def _random_market(seed: int, symbols: int, sessions: int) -> dict:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end=END, periods=sessions)
    frames = {}
    for j in range(symbols):
        closes = np.exp(np.cumsum(rng.normal(0, 0.08, sessions))) * rng.choice([0.5, 3, 30, 300])
        volumes = rng.integers(500, 3_000_000, sessions).astype(float)
        df = frame(closes, volumes, index=idx)
        if j % 4 == 0:
            df = df.drop(idx[rng.integers(0, sessions, 2)])
        if j % 5 == 0:
            df.iloc[rng.integers(0, len(df)), df.columns.get_loc("Close")] = np.nan
        if j % 6 == 0:
            df.iloc[rng.integers(0, len(df)), df.columns.get_loc("Volume")] = np.nan
        if j % 7 == 0:
            df = df.iloc[rng.integers(0, sessions // 2):]
        frames[f"S{j}"] = df
    return frames


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_the_vectorised_columns_match_a_per_symbol_reference(seed):
    frames = _random_market(seed, symbols=60, sessions=120)
    calendar = breadth.observed_sessions(frames)
    sessions = calendar[-25:]
    got = breadth.daily_counts(frames, sessions)
    assert [d.date for d in got] == sessions
    nonzero = set()
    for d in got:
        expected = _reference(frames, calendar, d.date)
        actual = d.to_dict()
        actual.pop("date")
        assert actual == expected, d.date
        nonzero |= {k for k, v in expected.items() if v}
    assert {"up4", "down4", "up25_quarter", "down25_quarter", "up25_month", "down25_month",
            "up50_month", "down50_month", "up13_34d", "down13_34d"} <= nonzero


def test_daily_counts_is_built_once_for_a_full_universe():
    """6,500 symbols x 110 sessions inside the budget the strip needs; a
    per-frame rolling loop is an order of magnitude over it."""
    rng = np.random.default_rng(7)
    idx = pd.bdate_range(end=END, periods=110)
    frames = {}
    for j in range(6500):
        closes = 20 * np.exp(np.cumsum(rng.normal(0, 0.03, 110)))
        frames[f"S{j}"] = frame(closes, rng.integers(50_000, 5_000_000, 110), index=idx)
    calendar = breadth.observed_sessions(frames)
    started = time.perf_counter()
    got = breadth.daily_counts(frames, calendar[-30:])
    elapsed = time.perf_counter() - started
    assert len(got) == 30 and got[-1].universe == 6500
    assert elapsed < 10.0, f"daily_counts took {elapsed:.1f}s"
