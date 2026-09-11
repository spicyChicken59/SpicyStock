"""Bonde's checklist over hand-built frames: both sides of every threshold.

The IDEAL frame is the field guide's A-quality shape built by hand -- a
linear leg, a quiet shallow base, a negative narrow day, a wide-range burst
on the move's highest volume closing near its high -- and every other frame
here is that one with exactly one rule flipped. Each flip asserts the OTHER
checks still pass, so a different rule can never be the one rejecting, and
each boundary is pinned on the rounded number the check carries, asserted
as a precondition before the verdict is read.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src import grader, quality, scans
from src.quality import COLUMNS, LETTERS, Check, assess, grade_of, metrics_for_model, score_of

END = "2026-09-10"
SOURCE = Path(__file__).resolve().parent.parent / "src" / "quality.py"


# ------------------------------------------------------------- builders ----


def frame(bars: list[list[float]]) -> pd.DataFrame:
    index = pd.bdate_range(end=END, periods=len(bars), name="timestamp")
    return pd.DataFrame(bars, index=index, columns=list(COLUMNS), dtype=float)


def bar(o: float, h: float, l: float, c: float, v: float) -> list[float]:
    return [round(o, 2), round(h, 2), round(l, 2), round(c, 2), float(v)]


def quiet(c: float, prev: float, v: float, range_pct: float) -> list[float]:
    """A bar opening at ``prev`` and closing at ``c`` whose envelope adds
    ``range_pct`` of the close around the body."""
    half = c * range_pct / 200
    return bar(prev, max(c, prev) + half, min(c, prev) - half, c, v)


def high_for(low: float, close: float, pos: float) -> float:
    """The cent-rounded high at which (close - low) / (high - low) reads ``pos``."""
    guess = low + (close - low) / pos
    for cents in range(-30, 31):
        h = round(guess + cents / 100, 2)
        if h > close and round((close - low) / (h - low), 2) == pos:
            return h
    raise AssertionError(f"no cent high reads close_pos {pos}")


def burst_bar(prev: float, gain: float, pos: float, vol: float,
              range_pct: float | None = None) -> list[float]:
    """The burst: close ``gain`` percent over ``prev``, closing at ``pos`` of
    its range. With ``range_pct`` the bar is that wide and gaps to fit."""
    c = round(prev * (1 + gain / 100), 2)
    if range_pct is None:
        low = round(prev * 1.01, 2)
        high = high_for(low, c, pos)
    else:
        total = c * range_pct / 100
        low = round(c - pos * total, 2)
        high = round(low + total, 2)
    o = round(low + (high - low) / 10, 2)
    return bar(o, high, low, c, vol)


def ideal_bars(*, pre: int = 80, leg_steps: list[float] | None = None, leg_vols: list[float] | None = None,
               base_closes: list[float] | None = None, base_quiet: int = 16, base_range: float = 0.8,
               base_wobble: float = 0.1, base_vol: float = 600_000, leg_vol: float = 1_500_000,
               pre_vol: float = 1_000_000, prior_drop: float = 0.2, prior_range: float = 0.6,
               burst_gain: float = 6.0, close_pos: float = 0.95, burst_vol: float = 3_000_000,
               burst_range_pct: float | None = None) -> list[list[float]]:
    """The field guide's A-quality shape: ``pre`` flat sessions at 100, a
    linear leg (fifteen +1.25% steps by default), a quiet base 2.5% under
    the peak, a negative narrow day, then the burst. The burst is the last
    bar; the base runs from the bar after the leg's last through the day
    before the burst."""
    bars = [bar(100, 100.8, 99.2, 100, pre_vol) for _ in range(pre)]
    prev = 100.0
    steps = [1.25] * 15 if leg_steps is None else leg_steps
    vols = [leg_vol] * len(steps) if leg_vols is None else leg_vols
    for step, vol in zip(steps, vols):
        c = round(prev * (1 + step / 100), 2)
        bars.append(bar(prev, max(prev, c) * 1.005, min(prev, c) * 0.995, c, vol))
        prev = c
    mid = round(prev * 0.975, 2)
    closes = base_closes if base_closes is not None else \
        [round(mid + (base_wobble if i % 2 == 0 else -base_wobble), 2) for i in range(base_quiet)]
    for c in closes:
        bars.append(quiet(c, prev, base_vol, base_range))
        prev = c
    c = round(prev - prior_drop, 2)
    bars.append(quiet(c, prev, base_vol, prior_range))
    prev = c
    bars.append(burst_bar(prev, burst_gain, close_pos, burst_vol, burst_range_pct))
    return bars


def run(bars: list[list[float]]) -> quality.Assessment:
    return assess(frame(bars))


def check(a: quality.Assessment, letter: str) -> Check:
    found = a.check(letter)
    assert found is not None, letter
    return found


def others_pass(a: quality.Assessment, *exempt: str) -> None:
    """Every check not named passes outright, so the flipped rule is the
    only one deciding."""
    for c in a.checks:
        if c.letter not in exempt:
            assert c.passed is True and not c.partial, c.line()


#: Leg shapes with known linearity, measured before they were written down.
ZIGZAG_R2_ONLY = [100, 105, 102, 107, 104, 109, 106, 111, 108, 113, 110, 115, 112, 117, 114, 119]
SHELF_ER_ONLY = [100, 100.5, 101, 101.5, 102, 102.5, 103, 125]
CHOP_BOTH_FAIL = [100, 108, 101, 109, 102, 110, 103, 111]


def steps_from(closes: list[float]) -> list[float]:
    """Percent steps that reproduce ``closes`` from the 100 the pre sits at."""
    out, prev = [], 100.0
    for c in closes[1:]:
        out.append((c / prev - 1) * 100)
        prev = c
    return out


# ---------------------------------------------------------------- ideal ----


def test_the_ideal_frame_passes_every_letter_at_a_plus_with_no_veto():
    a = run(ideal_bars())
    for c in a.checks:
        assert c.passed is True and c.a_plus and not c.partial, c.line()
    assert a.vetoes == [] and a.reclass is None and a.unreadable is None
    assert (a.passes, a.of, a.a_plus_count, a.score, a.grade) == (6, 6, 8, 10.0, "A+")
    assert a.base["length"] == 17 and a.leg["er"] == 1.0 and a.leg["r2"] == 1.0
    assert a.burst["gain_pct"] == 6.0 and a.burst["close_pos"] == 0.95
    assert a.burst["volume_vs_prior"] == 5.0 and a.burst["volume_rank_60"] == 1


def test_the_ideal_frame_by_hand():
    """The two ratios whose windows are easiest to shift by one: each is
    recomputed here from the bars, so a window that quietly took in the
    burst bar itself would print a different number."""
    bars = ideal_bars()
    a = run(bars)
    ranges = [round(100 * (b[1] - b[2]) / b[3], 1) for b in bars]
    re = check(a, "RE")
    assert ranges[-1] > 4 and max(ranges[-6:-1]) == 1.0
    assert re.value["bar_range_pct"] == ranges[-1]
    assert re.value["vs_prior_5"] == round(ranges[-1] / max(ranges[-6:-1]), 2)
    assert re.value["vs_prior_10"] == round(ranges[-1] / max(ranges[-11:-1]), 2)
    vols = [b[4] for b in bars]
    assert a.burst["volume_vs_avg50"] == round(vols[-1] / np.mean(vols[-51:-1]), 2)


def test_the_burst_bar_is_the_scans_own_number():
    df = frame(ideal_bars())
    a = assess(df)
    match = scans.burst_4pct(df)
    assert match is not None
    assert a.burst["gain_pct"] == match["gain_pct"]
    assert a.burst["volume_vs_prior"] == round(match["volume_vs_prior"], quality.RATIO_DECIMALS)


# -------------------------------------------------------------------- H ----


@pytest.mark.parametrize("pos, status, a_plus", [
    (0.90, "PASS", True), (0.89, "PASS", False), (0.80, "PASS", False),
    (0.79, "PARTIAL", False), (0.70, "PARTIAL", False), (0.69, "FAIL", False),
])
def test_h_on_both_sides_of_every_boundary(pos, status, a_plus):
    a = run(ideal_bars(close_pos=pos))
    h = check(a, "H")
    assert h.value["close_pos"] == pos, "precondition: the rounded number is the one named"
    assert h.status == status and h.a_plus is a_plus, h.line()
    others_pass(a, "H")


def test_h_needs_the_close_above_the_open():
    bars = ideal_bars()
    o, h, l, c, v = bars[-1]
    bars[-1] = bar(c, h, l, c, v)
    a = run(bars)
    hh = check(a, "H")
    assert hh.value["close_pos"] == 0.95 and hh.value["close_above_open"] is False
    assert hh.passed is False and not hh.partial and "open" in hh.note
    others_pass(a, "H")


def test_h_rounds_once_and_decides_on_the_rounded_number():
    bars = ideal_bars()
    o, h, l, c, v = bars[-1]
    raw = None
    for cents in range(0, 400):
        hh = round(l + (c - l) / 0.80 + cents / 100, 2)
        raw = (c - l) / (hh - l)
        if 0.795 < raw < 0.7999:
            break
    assert 0.795 < raw < 0.7999, "precondition: a raw position under 0.80 that prints 0.80"
    bars[-1] = bar(o, hh, l, c, v)
    hc = check(run(bars), "H")
    assert hc.value["close_pos"] == 0.80 and hc.passed is True


@pytest.mark.parametrize("problem, edit", [
    ("no range", lambda b: bar(b[3], b[3], b[3], b[3], b[4])),
    ("inverted", lambda b: bar(b[0], b[2], b[1], b[3], b[4])),
    ("close outside", lambda b: bar(b[0], b[1], b[2], b[1] + 1, b[4])),
    ("open outside", lambda b: bar(b[1] + 1, b[1], b[2], b[3], b[4])),
    ("missing close", lambda b: [b[0], b[1], b[2], np.nan, b[4]]),
])
def test_an_unreadable_burst_bar_is_refused_not_graded(problem, edit):
    bars = ideal_bars()
    bars[-1] = edit(bars[-1])
    a = run(bars)
    assert a.unreadable, problem
    assert a.grade == grader.SKIP and a.reclass is None
    assert check(a, "H").passed is None and check(a, "RE").passed is None
    assert a.burst["close_pos"] is None and a.burst["bar_range_pct"] is None
    assert a.to_dict()["unreadable"] == a.unreadable


# -------------------------------------------------------------------- N ----


def prior_day(bars: list[list[float]], c: float, range_pct: float) -> None:
    """Rewrite the day before the burst to close at ``c`` with ``range_pct``."""
    prev = bars[-3][3]
    h = round(c + c * range_pct / 200, 2)
    l = round(c - c * range_pct / 200, 2)
    assert l <= prev <= h, "precondition: the open sits inside the bar"
    bars[-2] = bar(prev, h, l, c, bars[-2][4])
    o, hh, ll, cc, v = bars[-1]
    bars[-1] = burst_bar(c, 6.0, 0.95, v)


def test_n_two_percent_is_not_narrow_and_one_point_nine_is():
    for range_pct, narrow in ((2.0, False), (1.9, True)):
        bars = ideal_bars()
        prior_day(bars, round(bars[-3][3] + 0.2, 2), range_pct)
        a = run(bars)
        n = check(a, "N")
        assert n.value["negative"] is False and n.value["prior_range_pct"] == range_pct, "precondition"
        assert n.value["narrow"] is narrow and n.passed is narrow, n.line()
        others_pass(a, "N")


def test_n_rounds_the_range_once_and_decides_on_the_rounded_number():
    bars = ideal_bars()
    prior_day(bars, round(bars[-3][3] + 0.2, 2), 1.96)
    n = check(run(bars), "N")
    assert n.value["prior_range_pct"] == 2.0 and n.value["narrow"] is False and n.passed is False


def test_n_is_an_or_a_negative_wide_day_passes_without_a_plus():
    bars = ideal_bars()
    prior_day(bars, round(bars[-3][3] - 0.2, 2), 2.5)
    a = run(bars)
    n = check(a, "N")
    assert n.value["negative"] is True and n.value["narrow"] is False
    assert n.passed is True and n.a_plus is False
    others_pass(a, "N")


def test_n_a_plus_needs_the_range_under_the_median_of_the_twenty_before():
    bars = ideal_bars()
    prior_day(bars, round(bars[-3][3] - 0.2, 2), 1.5)
    n = check(run(bars), "N")
    assert n.value["negative"] is True and n.value["narrow"] is True
    assert n.value["median_range_pct"] < 1.5 <= quality.NARROW_RANGE_PCT
    assert n.passed is True and n.a_plus is False
    ideal = check(run(ideal_bars()), "N")
    assert ideal.value["prior_range_pct"] < ideal.value["median_range_pct"] and ideal.a_plus


# -------------------------------------------------------------------- 2 ----


def up_days(bars: list[list[float]], pcts: list[float], range_pct: float = 0.6) -> None:
    """Rewrite the last len(pcts) sessions before the burst as up days of
    those sizes, each a quiet bar, and rebuild the burst on the new close."""
    n = len(pcts)
    # The session before the run closes DOWN, so the run is exactly the
    # sessions named and not one longer by the base's own wobble.
    anchor = round(bars[-3 - n][3] - 0.2, 2)
    bars[-2 - n] = quiet(anchor, bars[-3 - n][3], bars[-2][4], range_pct)
    prev = anchor
    for i, pct in enumerate(pcts):
        c = round(prev * (1 + pct / 100), 2)
        bars[-1 - n + i] = quiet(c, prev, bars[-2][4], range_pct)
        prev = c
    bars[-1] = burst_bar(prev, 6.0, 0.95, bars[-1][4])


def test_two_a_one_percent_day_is_flat_and_one_point_one_counts():
    bars = ideal_bars()
    up_days(bars, [1.0])
    a = run(bars)
    two = check(a, "2")
    assert two.value["prior_day_pct"] == 1.0, "precondition"
    assert two.value["up_run"] == 0 and two.passed and two.a_plus
    others_pass(a, "2")
    bars = ideal_bars()
    up_days(bars, [1.1])
    a = run(bars)
    two = check(a, "2")
    assert two.value["prior_day_pct"] == 1.1, "precondition"
    assert two.value["up_run"] == 1 and two.passed and not two.a_plus
    others_pass(a, "2")


def test_two_fails_at_two_counting_days_and_a_flat_day_neither_counts_nor_breaks():
    bars = ideal_bars()
    up_days(bars, [1.1, 1.1])
    a = run(bars)
    two = check(a, "2")
    assert two.value["up_run"] == 2 and two.passed is False and two.value["up_closes"] == 2
    assert quality.VETO_UP_DAYS_NAME not in a.vetoes
    others_pass(a, "2")
    bars = ideal_bars()
    up_days(bars, [1.1, 1.1, 0.5])
    two = check(run(bars), "2")
    assert two.value["prior_day_pct"] == 0.5 and two.value["up_run"] == 2 and two.passed is False


def test_the_veto_at_three_up_closes_of_any_size():
    bars = ideal_bars()
    up_days(bars, [0.2, 0.2, 0.2])
    a = run(bars)
    two = check(a, "2")
    assert two.value["up_closes"] == 3 and two.value["up_run"] == 0 and two.passed is True
    assert a.vetoes == [quality.VETO_UP_DAYS_NAME] and a.grade == grader.SKIP
    assert a.score == 10.0, "the score is kept for display"
    others_pass(a, "2")
    bars = ideal_bars()
    up_days(bars, [0.2, 0.2])
    a = run(bars)
    assert check(a, "2").value["up_closes"] == 2 and a.vetoes == [] and a.grade == "A+"


# -------------------------------------------------------------------- L ----


def test_l_passes_on_r_squared_alone():
    a = run(ideal_bars(leg_steps=steps_from(ZIGZAG_R2_ONLY)))
    l = check(a, "L")
    assert l.value["er"] < quality.MIN_ER <= 0.40 and l.value["r2"] >= quality.MIN_R2, l.line()
    assert l.passed is True and l.a_plus is False and a.vetoes == []
    others_pass(a, "L")


def test_l_passes_on_the_efficiency_ratio_alone():
    a = run(ideal_bars(leg_steps=steps_from(SHELF_ER_ONLY)))
    l = check(a, "L")
    assert l.value["er"] >= quality.MIN_ER and l.value["r2"] < quality.MIN_R2, l.line()
    assert l.passed is True and l.a_plus is False and a.vetoes == []
    others_pass(a, "L")


def test_l_failure_is_a_veto():
    a = run(ideal_bars(leg_steps=steps_from(CHOP_BOTH_FAIL)))
    l = check(a, "L")
    assert l.value["er"] < quality.MIN_ER and l.value["r2"] < quality.MIN_R2, l.line()
    assert l.passed is False and a.vetoes == [quality.VETO_NOT_LINEAR] and a.grade == grader.SKIP
    others_pass(a, "L")


def test_l_thresholds_are_read_on_the_rounded_number():
    a = run(ideal_bars(leg_steps=steps_from(ZIGZAG_R2_ONLY)))
    l = check(a, "L")
    assert (l.value["er"], l.value["r2"]) == (0.31, 0.85)
    a = run(ideal_bars(leg_steps=steps_from(SHELF_ER_ONLY)))
    assert (check(a, "L").value["er"], check(a, "L").value["r2"]) == (1.0, 0.46)


def test_no_leg_leaves_l_unmeasured_and_does_not_veto():
    a = run(ideal_bars(leg_steps=[20.0], leg_vols=[1_000_000]))
    l = check(a, "L")
    assert a.leg["length"] == 2 and l.value["er"] is None and l.value["r2"] is None
    assert l.passed is None and "no leg" in l.note and a.vetoes == []
    others_pass(a, "L")
    assert a.grade == "A"


# -------------------------------------------------------------------- Y ----


def breakout_leg(count: int) -> tuple[list[float], list[float]]:
    steps = [1.25] * 15
    vols = [1_500_000.0] * 15
    for i in (4, 9)[:count]:
        steps[i] = 4.5
        vols[i] = 3_000_000.0
    return steps, vols


def test_y_counts_prior_breakouts_since_the_move_started():
    for count, passed, a_plus in ((1, True, False), (2, False, False)):
        steps, vols = breakout_leg(count)
        a = run(ideal_bars(leg_steps=steps, leg_vols=vols))
        y = check(a, "Y")
        assert y.value["breakouts_in_move"] == count and y.passed is passed and y.a_plus is a_plus
        others_pass(a, "Y")


def test_y_a_breakout_needs_volume_over_the_prior_session_and_a_strong_close():
    steps, _ = breakout_leg(2)
    a = run(ideal_bars(leg_steps=steps))
    assert check(a, "Y").value["breakouts_in_move"] == 0, "same volume as the session before"
    steps, vols = breakout_leg(1)
    bars = ideal_bars(leg_steps=steps, leg_vols=vols)
    i = 80 + 4
    o, h, l, c, v = bars[i]
    bars[i] = bar(o, round(l + (c - l) / 0.69, 2), l, c, v)
    assert check(run(bars), "Y").value["breakouts_in_move"] == 0, "closed at 0.69 of its range"


def test_y_publishes_the_move_start_and_prefers_a_close_under_its_sma():
    bars = ideal_bars()
    a = run(bars)
    y = check(a, "Y")
    assert y.value["sessions_since_move_start"] == 33
    assert y.value["gain_since_move_start_pct"] == round(bars[-1][3] - 100, 1)
    # The window's lowest close (95, after forty-nine sessions at 94) sits
    # ABOVE its own 50-SMA; the dip to 96 after seventeen sessions at 101
    # sits under its SMA, so it is the move's start and the lower close is not.
    closes = [94.0] * 52 + [95.0] + [101.0] * 17 + [96.0] + [101.0] * 9
    assert len(closes) == 80
    for i, c in enumerate(closes):
        bars[i] = bar(c, c + 0.8, c - 0.8, c, bars[i][4])
    y = check(run(bars), "Y")
    assert y.value["sessions_since_move_start"] == len(bars) - 1 - 70
    assert y.value["sessions_since_move_start"] != len(bars) - 1 - 52


# -------------------------------------------------------------------- C ----


def peak_close(steps: list[float] | None = None) -> float:
    prev = 100.0
    for step in ([1.25] * 15 if steps is None else steps):
        prev = round(prev * (1 + step / 100), 2)
    return prev


def test_c_base_length_band():
    for quiet_days, status in ((19, "PASS"), (20, "PARTIAL"), (1, "PARTIAL"), (0, "FAIL")):
        # A two-session base is one quiet bar and the prior day; that bar
        # steps down 0.5% rather than the builder's 2.5%, so its own width
        # cannot be what decides a test about LENGTH.
        closes = [round(peak_close() * 0.995, 2)] if quiet_days == 1 else None
        a = run(ideal_bars(base_quiet=quiet_days, base_closes=closes))
        c = check(a, "C")
        assert c.value["base_sessions"] == quiet_days + 1 and a.base["length"] == quiet_days + 1
        assert c.status == status, c.line()
        if status != "PASS":
            assert f"base of {quiet_days + 1} sessions is outside Bonde's 3-20" in c.note
        others_pass(a, "C")


def base_with_breakdowns(count: int) -> list[float]:
    """A base at 2.5% under a +55.8% leg with ``count`` consecutive -4% days
    after three quiet sessions; the deep leg keeps the giveback under the
    floor so the breakdowns are the only clause that can fail."""
    peak = 100.0
    for _ in range(15):
        peak = round(peak * 1.03, 2)
    mid = round(peak * 0.975, 2)
    closes = [round(mid + 0.1, 2), round(mid - 0.1, 2), round(mid + 0.1, 2)]
    for _ in range(count):
        closes.append(round(closes[-1] * 0.96, 2))
    level = closes[-1]
    while len(closes) < 16:
        closes.append(round(level + (0.1 if len(closes) % 2 == 0 else -0.1), 2))
    return closes


def test_c_one_breakdown_passes_and_two_fail():
    for count, passed in ((1, True), (2, False)):
        a = run(ideal_bars(leg_steps=[3.0] * 15, base_closes=base_with_breakdowns(count)))
        c = check(a, "C")
        assert c.value["breakdowns"] == count, c.line()
        assert c.value["giveback"] <= quality.MAX_GIVEBACK and c.value["tightness"] <= quality.MAX_TIGHTNESS
        assert quality.BASE_MIN <= c.value["base_sessions"] <= quality.BASE_MAX
        assert c.passed is passed and c.a_plus is False, c.line()
        others_pass(a, "C")


def test_c_breakdowns_are_the_scans_own_rule():
    bars = ideal_bars(leg_steps=[3.0] * 15, base_closes=base_with_breakdowns(1))
    df = frame(bars)
    drop = 80 + 15 + 3
    assert scans.pct_change(df, at=drop) <= round(100 * (scans.BREAKDOWN_RATIO - 1), scans.PCT_DECIMALS)
    assert check(assess(df), "C").value["breakdowns"] == 1
    bars[drop][3] = round(bars[drop - 1][3] * 0.9605, 2)
    assert check(assess(frame(bars)), "C").value["breakdowns"] == 0


def spike_low(bars: list[list[float]], giveback: float) -> None:
    """Put one base bar's low where the giveback reads exactly ``giveback``."""
    a = run(bars)
    high, low = a.leg["high"], a.leg["low"]
    i = len(bars) - 15
    for cents in range(-40, 41):
        candidate = round(high - giveback * (high - low) + cents / 100, 2)
        if round((high - candidate) / (high - low), 2) == giveback:
            bars[i][2] = candidate
            assert candidate < bars[i][0] and candidate < bars[i][3]
            return
    raise AssertionError("no cent low reads that giveback")


def test_c_giveback_on_both_sides_of_the_floor():
    for target, passed in ((0.34, True), (0.35, False)):
        bars = ideal_bars()
        spike_low(bars, target)
        a = run(bars)
        c = check(a, "C")
        assert c.value["giveback"] == target, c.line()
        assert c.value["breakdowns"] == 0 and c.value["tightness"] <= quality.MAX_TIGHTNESS
        assert c.passed is passed, c.line()
        others_pass(a, "C")


def test_c_a_plus_giveback_boundary():
    for target, a_plus in ((0.25, True), (0.26, False)):
        bars = ideal_bars()
        spike_low(bars, target)
        c = check(run(bars), "C")
        assert c.value["giveback"] == target and c.passed is True and c.a_plus is a_plus, c.line()


def bars_with_tightness(tightness: float) -> list[list[float]]:
    """Every base bar at one width moves the ratio in steps too coarse to
    land on a hundredth, so one base bar is widened on its own until the
    ratio reads exactly ``tightness``."""
    for r0 in np.arange(0.6, 2.4, 0.1):
        for extra in np.arange(0.0, 3.0, 0.05):
            bars = ideal_bars(base_range=float(r0))
            o, h, l, c, v = bars[-10]
            half = c * (r0 + extra) / 200
            bars[-10] = bar(o, max(o, c) + half, min(o, c) - half, c, v)
            if check(run(bars), "C").value["tightness"] == tightness:
                return bars
    raise AssertionError(f"no base reads tightness {tightness}")


def test_c_tightness_on_both_sides_of_the_ceiling():
    for target, passed in ((1.0, True), (1.01, False)):
        a = run(bars_with_tightness(target))
        c = check(a, "C")
        assert c.value["tightness"] == target and c.value["giveback"] <= quality.MAX_GIVEBACK
        assert c.value["breakdowns"] == 0 and quality.BASE_MIN <= c.value["base_sessions"] <= quality.BASE_MAX
        assert c.passed is passed, c.line()
        others_pass(a, "C")


def test_c_a_plus_tightness_boundary():
    for target, a_plus in ((0.70, True), (0.71, False)):
        c = check(run(bars_with_tightness(target)), "C")
        assert c.value["tightness"] == target and c.passed is True and c.a_plus is a_plus, c.line()


def test_c_a_plus_needs_no_burst_inside_the_base():
    closes = base_with_breakdowns(0)
    closes[5] = round(closes[4] * 0.97, 2)
    closes[6] = round(closes[5] * 1.042, 2)
    for i in range(7, 16):
        closes[i] = round(closes[6] + (0.1 if i % 2 else -0.1), 2)
    a = run(ideal_bars(leg_steps=[3.0] * 15, base_closes=closes))
    c = check(a, "C")
    assert c.value["bursts_in_base"] == 1 and c.value["breakdowns"] == 0
    assert c.value["giveback"] <= quality.A_PLUS_MAX_GIVEBACK and c.value["tightness"] <= quality.A_PLUS_MAX_TIGHTNESS
    assert c.passed is True and c.a_plus is False
    others_pass(a, "C")


def test_c_a_plus_needs_base_volume_under_the_leg_and_the_average():
    c = check(run(ideal_bars(base_vol=1_600_000)), "C")
    assert c.value["base_volume_vs_leg"] >= 1 and c.passed and not c.a_plus
    c = check(run(ideal_bars(base_vol=1_300_000)), "C")
    assert c.value["base_volume_vs_leg"] < 1 <= c.value["base_volume_vs_avg"]
    assert c.passed and not c.a_plus
    c = check(run(ideal_bars(base_vol=1_200_000)), "C")
    assert c.value["base_volume_vs_leg"] < 1 and c.value["base_volume_vs_avg"] < 1 and c.a_plus
    # The leg starts on the last pre session, so its mean volume is the
    # pre's and the leg's together: both at 1.5M puts the base exactly AT
    # the leg's mean and at the 50-session average, and at is not under.
    c = check(run(ideal_bars(base_vol=1_500_000, pre_vol=1_500_000)), "C")
    assert c.value["base_volume_vs_leg"] == 1.0 and c.value["base_volume_vs_avg"] == 1.0
    assert c.passed and not c.a_plus, "under, not at"


def test_the_base_starts_after_the_peak_and_the_prior_day_is_never_the_peak():
    """The search for the leg's high stops two sessions before the burst:
    a spike high on the day before would otherwise make it the peak and
    leave no base at all."""
    bars = ideal_bars()
    o, h, l, c, v = bars[-2]
    bars[-2] = bar(o, round(bars[-18][1] + 1, 2), l, c, v)
    a = run(bars)
    assert bars[-2][1] > a.base["high"]
    assert a.base["length"] == 17 and check(a, "C").passed is True


def test_c_and_l_are_unmeasured_on_a_frame_with_no_base():
    a = run(ideal_bars()[-2:])
    assert a.base is None and check(a, "C").passed is None and check(a, "L").passed is None
    assert a.vetoes == [] and a.grade != "A+"


# ------------------------------------------------------------------- RE ----


def test_re_passes_at_one_and_fails_under_it():
    # The quiet bars' envelope adds their 0.2 body, so they read 1.4%.
    bars = ideal_bars(base_range=1.2, prior_range=1.2, burst_range_pct=1.4)
    a = run(bars)
    re = check(a, "RE")
    assert re.value["bar_range_pct"] == 1.4 and re.value["vs_prior_5"] == 1.0, re.line()
    assert re.passed is True and re.a_plus is True
    others_pass(a, "RE")
    a = run(ideal_bars(base_range=1.2, prior_range=1.2, burst_range_pct=1.3))
    re = check(a, "RE")
    assert re.value["bar_range_pct"] == 1.3 and re.value["vs_prior_5"] < 1.0 and re.passed is False, re.line()
    others_pass(a, "RE")


def test_re_a_plus_needs_the_ten_session_window_too():
    bars = ideal_bars(burst_range_pct=1.5)
    c = bars[-9][3]
    bars[-9] = bar(bars[-10][3], round(c * 1.01, 2), round(c * 0.99, 2), c, bars[-9][4])
    re = check(run(bars), "RE")
    assert re.value["vs_prior_5"] >= 1.0 > re.value["vs_prior_10"], re.line()
    assert re.passed is True and re.a_plus is False


# ------------------------------------------------------------------ VOL ----


def test_vol_needs_volume_over_the_prior_session():
    a = run(ideal_bars(burst_vol=600_000))
    v = check(a, "VOL")
    assert v.value["volume_vs_prior"] == 1.0 and v.passed is False
    others_pass(a, "VOL")


def test_vol_a_plus_is_the_top_three_of_the_last_sixty():
    for loud, a_plus in ((2, True), (3, False)):
        vols = [1_500_000.0] * 15
        for i in range(loud):
            vols[i] = 5_000_000.0
        v = check(run(ideal_bars(leg_vols=vols)), "VOL")
        assert v.value["volume_rank_60"] == loud + 1 and v.passed and v.a_plus is a_plus
    vols = [5_000_000.0, 5_000_000.0] + [1_500_000.0] * 13
    for back, rank in ((60, 3), (59, 4)):
        bars = ideal_bars(leg_vols=vols)
        bars[len(bars) - 1 - back][4] = 5_000_000.0
        v = check(run(bars), "VOL")
        assert v.value["volume_rank_60"] == rank and v.a_plus is (rank <= 3), f"a loud bar {back} back"


def test_vol_over_a_long_base_needs_one_and_a_half_times_the_average_and_a_catalyst():
    a = run(ideal_bars(base_quiet=21, burst_vol=700_000))
    v = check(a, "VOL")
    assert v.value["cv_required"] is True and v.value["volume_vs_avg50"] < quality.CV_MIN_VOLUME
    assert v.value["volume_vs_prior"] > 1 and v.passed is False and "catalyst" in v.note
    assert check(run(ideal_bars(base_quiet=20, burst_vol=700_000)), "VOL").passed is True
    v = check(run(ideal_bars(base_quiet=21)), "VOL")
    assert v.value["volume_vs_avg50"] >= quality.CV_MIN_VOLUME and v.passed is True and "catalyst" in v.note


# -------------------------------------------------------- reclassification ----


def test_h_only_failure_is_an_anticipation_setup():
    for pos in (0.60, 0.75):
        a = run(ideal_bars(close_pos=pos))
        assert check(a, "H").passed is False and a.reclass == quality.RECLASS_ANTICIPATION
    a = run(ideal_bars())
    assert a.reclass is None
    bars = ideal_bars(close_pos=0.60)
    up_days(bars, [1.1, 1.1])
    bars[-1] = burst_bar(bars[-2][3], 6.0, 0.60, bars[-1][4])
    a = run(bars)
    assert check(a, "H").passed is False and check(a, "2").passed is False and a.reclass is None
    bars = ideal_bars(close_pos=0.60)
    up_days(bars, [0.2, 0.2, 0.2])
    bars[-1] = burst_bar(bars[-2][3], 6.0, 0.60, bars[-1][4])
    a = run(bars)
    assert a.vetoes == [quality.VETO_UP_DAYS_NAME] and check(a, "H").passed is False
    others_pass(a, "H")
    assert a.reclass is None, "a vetoed name is refused, not routed"


# --------------------------------------------------------------- notes ----


def test_the_extension_note_carries_the_two_numbers_by_hand():
    bars = ideal_bars()
    closes = [b[3] for b in bars]
    ext = round(100 * (closes[-1] / np.mean(closes[-20:]) - 1), 1)
    run_up = round(100 * (closes[-1] / closes[-21] - 1), 1)
    a = run(bars)
    assert f"extension: close {ext}% vs its 20-SMA, {run_up}% over 20 sessions" in a.notes


def test_the_high_gain_note_on_both_sides_of_fifteen():
    a = run(ideal_bars(burst_gain=15.0))
    assert a.burst["gain_pct"] == 15.0 and any("worst cell" in n for n in a.notes)
    a = run(ideal_bars(burst_gain=14.9))
    assert a.burst["gain_pct"] == 14.9 and not any("worst cell" in n for n in a.notes)


def test_the_low_price_note():
    bars = [[round(x * 0.03, 2) if i < 4 else x for i, x in enumerate(b)] for b in ideal_bars()]
    a = run(bars)
    assert any("explosive" in n for n in a.notes)
    assert not any("explosive" in n for n in run(ideal_bars()).notes)


def test_the_prior_breakout_history_note():
    steps, vols = breakout_leg(2)
    a = run(ideal_bars(leg_steps=steps, leg_vols=vols))
    assert any(n.startswith("prior breakouts worked 2 of 2") for n in a.notes)
    bars = ideal_bars()
    bars[len(bars) - 50] = bar(100, 105, 99.5, 104.5, bars[0][4])
    a = run(bars)
    assert any(n.startswith("prior breakouts worked 0 of 1") for n in a.notes)
    assert not any(n.startswith("prior breakouts") for n in run(ideal_bars()).notes)


def test_the_fast_leg_note():
    a = run(ideal_bars(leg_steps=[2.2] * 8))
    assert a.leg["length"] == 9 and a.leg["gain_pct"] >= 15
    assert any("first leg of" in n for n in a.notes)
    a = run(ideal_bars(leg_steps=[2.2] * 10))
    assert a.leg["length"] == 11 and a.leg["gain_pct"] >= 15
    assert not any("first leg of" in n for n in a.notes)
    a = run(ideal_bars(leg_steps=[2.0] * 9))
    assert a.leg["length"] == 10 and a.leg["gain_pct"] >= 15 and any("first leg of" in n for n in a.notes)
    a = run(ideal_bars(leg_steps=[1.5] * 9))
    assert a.leg["length"] == 10 and a.leg["gain_pct"] < 15 and not any("first leg of" in n for n in a.notes)


# ----------------------------------------------------- score and grade ----


def _check(letter: str, passed, a_plus: bool = False, partial: bool = False) -> Check:
    return Check(letter.lower(), letter, letter, {}, "", passed, a_plus, "", partial)


def test_score_arithmetic_weights_partials_at_half_and_ignores_re_and_vol():
    checks = [_check("2", True, True), _check("L", True), _check("Y", False), _check("N", True),
              _check("C", False, partial=True), _check("H", True, True),
              _check("RE", True, True), _check("VOL", False)]
    score, passes, a_plus = score_of(checks)
    assert score == 1.5 + 2.0 + 1.5 + 1.0 + 1.5 and passes == 4 and a_plus == 3
    assert sum(quality.WEIGHTS.values()) == 10.0 and set(quality.WEIGHTS) == set(LETTERS)
    assert score_of([_check(l, True) for l in LETTERS] + [_check("RE", True), _check("VOL", True)])[0] == 10.0


@pytest.mark.parametrize("score, a_plus, refused, gates, grade", [
    (9.0, 4, False, True, "A+"), (9.0, 3, False, True, "A"), (10.0, 8, False, True, "A+"),
    (8.75, 8, False, True, "A"), (8.0, 8, False, True, "A"), (7.75, 8, False, True, "B"),
    (6.5, 0, False, True, "B"), (6.25, 0, False, True, "C"), (5.0, 0, False, True, "C"),
    (4.75, 0, False, True, grader.SKIP), (10.0, 8, True, True, grader.SKIP),
    (10.0, 8, False, False, "B"), (8.0, 8, False, False, "B"), (7.0, 8, False, False, "B"),
    (5.0, 8, False, False, "C"),
])
def test_grade_bands_and_the_two_gates(score, a_plus, refused, gates, grade):
    assert grade_of(score, a_plus, refused, gates) == grade


def test_grade_bands_are_the_graders_own():
    assert quality.GATED_GRADES == ("A+", "A") and quality.GATE_CAP == "B"
    assert [g for _, g in grader.GRADE_BANDS] == ["A+", "A", "B", "C"]
    assert grader.GRADE_BANDS[0][0] == 9.0 and grader.GRADE_BANDS[1][0] == 8.0
    assert grader.GRADE_BANDS[2][0] == 6.5 and grader.GRADE_BANDS[3][0] == 5.0


def test_a_nine_point_frame_with_h_partial_is_capped_at_b_and_says_why():
    a = run(ideal_bars(close_pos=0.75))
    assert check(a, "H").status == "PARTIAL" and a.score == 9.25
    assert a.grade == "B" and a.reclass == quality.RECLASS_ANTICIPATION
    assert "capped at B: closed at 75% of its range" in a.notes


def test_a_nine_point_frame_with_two_failing_is_capped_at_b_and_says_why():
    bars = ideal_bars()
    up_days(bars, [1.1, 1.1])
    a = run(bars)
    assert check(a, "2").passed is False and a.score == 8.5 and a.vetoes == []
    assert a.grade == "B"
    assert "capped at B: up 2 sessions of more than 1.0% in a row before the burst" in a.notes


def test_a_without_the_gates_touched_and_a_plus_demoted_without_four_a_plus_letters():
    steps, vols = breakout_leg(2)
    a = run(ideal_bars(leg_steps=steps, leg_vols=vols))
    assert a.score == 8.5 and a.grade == "A" and not any("capped" in n for n in a.notes)
    bars = ideal_bars(base_quiet=20, close_pos=0.85, burst_vol=1_400_000, burst_range_pct=1.5)
    up_days(bars, [1.1])
    bars[-1] = burst_bar(bars[-2][3], 6.0, 0.85, 1_400_000, 1.5)
    c = bars[-9][3]
    bars[-9] = bar(bars[-10][3], round(c * 1.01, 2), round(c * 0.99, 2), c, bars[-9][4])
    a = run(bars)
    assert a.score == 9.0 and a.a_plus_count < quality.MIN_A_PLUS_LETTERS, [c.line() for c in a.checks]
    assert check(a, "2").passed and check(a, "H").passed and a.grade == "A"


def test_the_score_is_kept_for_display_under_a_veto():
    a = run(ideal_bars(leg_steps=steps_from(CHOP_BOTH_FAIL)))
    assert a.grade == grader.SKIP and a.score == 8.0 and a.passes == 5


# ------------------------------------------------------------- reading ----


def test_bars_after_the_judged_one_are_never_read():
    bars = ideal_bars()
    t = len(bars) - 1
    later = bars + [bar(50, 51, 49, 50, 1) for _ in range(5)]
    assert assess(frame(later), at=t).to_dict() == assess(frame(bars)).to_dict()
    assert assess(frame(bars), at=-1).to_dict() == assess(frame(bars), at=t).to_dict()


def test_a_nan_in_history_is_skipped_and_a_nan_on_the_prior_day_unmeasures_two_and_n():
    bars = ideal_bars()
    bars[10][1] = np.nan
    assert run(bars).grade == "A+"
    bars = ideal_bars()
    bars[-2][3] = np.nan
    a = run(bars)
    assert check(a, "2").passed is None and check(a, "N").passed is None
    assert a.grade == "B" and any("capped at B" in n for n in a.notes)


def test_an_unreadable_frame_is_an_empty_skip():
    for bad in (pd.DataFrame(), "no", frame(ideal_bars()).drop(columns=["Volume"])):
        a = assess(bad)
        assert a.grade == grader.SKIP and a.checks == [] and a.unreadable
    assert assess(frame(ideal_bars()), at=999).unreadable
    assert assess(frame(ideal_bars()), at=True).unreadable


# ---------------------------------------------------------------- output ----


def plain(value) -> bool:
    if value is None or isinstance(value, (bool, int, float, str)):
        return type(value) in (bool, int, float, str, type(None))
    if isinstance(value, list):
        return all(plain(v) for v in value)
    return isinstance(value, dict) and all(plain(v) for v in value.values())


def test_to_dict_and_rules_hold_only_what_the_record_can_hold():
    for bars in (ideal_bars(), ideal_bars(leg_steps=[20.0]), ideal_bars()[-2:]):
        d = run(bars).to_dict()
        assert plain(d), d
        json.dumps(d)
    assert plain(quality.RULES)


def test_metrics_for_model_is_flat_sorted_and_serialisable_by_the_grader():
    a = run(ideal_bars(close_pos=0.75))
    m = metrics_for_model(a, "IDL", 124.02, {"volume_ratio": 5.0})
    assert list(m) == sorted(m) and m["ticker"] == "IDL" and m["volume_ratio"] == 5.0
    assert m["quality_grade"] == "B" and m["quality_passes"] == "5/6" and m["reclass"] == "anticipation"
    lines = m["checklist"]
    assert lines[5].startswith("H: PARTIAL -- close_pos=0.75") and " vs close_pos >= 0.8" in lines[5]
    assert lines[0].startswith("2: PASS -- ") and any(l.startswith("L: PASS") for l in lines)
    assert "capped at B: closed at 75% of its range" in m["notes"]
    assert m["base"].startswith("length=17") and m["leg"].startswith("length=16")
    text = grader.user_text(m)
    assert "IDL" in text and "H: PARTIAL" in text
    veto = run(ideal_bars(leg_steps=steps_from(CHOP_BOTH_FAIL)))
    assert metrics_for_model(veto, "V", 1.0)["vetoes"] == ["not_linear"]
    assert any(l.startswith("L: FAIL") for l in metrics_for_model(veto, "V", 1.0)["checklist"])


def test_check_lines_name_every_status():
    assert _check("H", True).status == "PASS" and _check("H", False).status == "FAIL"
    assert _check("H", False, partial=True).status == "PARTIAL" and _check("H", None).status == "UNMEASURED"
    assert _check("H", None).line() == "H: UNMEASURED -- no measurement vs "


# ---------------------------------------------------------------- rules ----


def _module_ast() -> ast.Module:
    return ast.parse(SOURCE.read_text())


def _named_constants() -> dict[str, float]:
    found = {}
    for node in _module_ast().body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id.isupper() \
                and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, (int, float)) \
                and not isinstance(node.value.value, bool):
            found[node.targets[0].id] = node.value.value
    return found


def test_every_named_number_is_archived_in_rules():
    constants = _named_constants()
    assert len(constants) >= 40
    rules_node = next(node for node in _module_ast().body
                      if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                      and node.targets[0].id == "RULES")
    read = {value.id for value in rules_node.value.values if isinstance(value, ast.Name)}
    assert set(constants) <= read, f"named but not archived: {set(constants) - read}"
    assert all(k.startswith("quality.") for k in quality.RULES)
    assert len(quality.RULES) >= len(constants) + 2


def test_the_numbers_are_bondes_where_he_gave_them():
    r = quality.RULES
    assert r["quality.min_close_pos"] == 0.80 and r["quality.a_plus_close_pos"] == 0.90
    assert r["quality.partial_close_pos"] == 0.70
    assert r["quality.narrow_range_pct_exclusive"] == 2.0 and r["quality.narrow_norm_sessions"] == 20
    assert r["quality.up_day_pct_exclusive"] == 1.0 and r["quality.max_up_run"] == 1
    assert r["quality.veto_up_days"] == 3
    assert r["quality.min_er"] == 0.40 and r["quality.min_r2"] == 0.55 and r["quality.min_leg_sessions"] == 5
    assert r["quality.max_prior_breakouts"] == 1 and r["quality.breakout_min_close_pos"] == 0.70
    assert r["quality.move_search_sessions"] == 60 and r["quality.move_sma_sessions"] == 50
    assert (r["quality.base_min"], r["quality.base_max"], r["quality.partial_base_min"]) == (3, 20, 2)
    assert r["quality.max_breakdowns"] == 1 and r["quality.max_giveback"] == 0.34
    assert r["quality.a_plus_max_giveback"] == 0.25 and r["quality.max_tightness"] == 1.0
    assert r["quality.a_plus_max_tightness"] == 0.70 and r["quality.tightness_norm_sessions"] == 60
    assert r["quality.base_search_sessions"] == 40 and r["quality.leg_search_sessions"] == 60
    assert r["quality.re_window"] == 5 and r["quality.re_window_long"] == 10
    assert r["quality.min_range_expansion"] == 1.0
    assert r["quality.volume_rank_sessions"] == 60 and r["quality.a_plus_max_volume_rank"] == 3
    assert r["quality.volume_avg_sessions"] == 50
    assert r["quality.cv_base_sessions_exclusive"] == 21 and r["quality.cv_min_volume"] == 1.5
    assert r["quality.low_price_exclusive"] == 5.0 and r["quality.high_gain_pct"] == 15.0
    assert r["quality.history_sessions"] == 60 and r["quality.history_max_breakouts"] == 4
    assert r["quality.history_follow_sessions"] == 3
    assert r["quality.fast_leg_min_gain_pct"] == 15.0 and r["quality.fast_leg_max_sessions"] == 10
    assert r["quality.extension_sma_sessions"] == 20 and r["quality.run_up_sessions"] == 20
    assert (r["quality.weight_l"], r["quality.weight_c"]) == (2.0, 2.0)
    assert (r["quality.weight_2"], r["quality.weight_y"], r["quality.weight_n"], r["quality.weight_h"]) \
        == (1.5, 1.5, 1.5, 1.5)
    assert r["quality.min_a_plus_letters"] == 4
    assert r["quality.burst_ratio"] == scans.BURST_RATIO == 1.04
    assert r["quality.breakdown_ratio"] == scans.BREAKDOWN_RATIO == 0.96
    assert (r["quality.precision.ratio_decimals"], r["quality.precision.pct_decimals"],
            r["quality.precision.price_decimals"]) == (2, 1, 2)


def test_no_function_spells_a_threshold_as_a_literal():
    """0, 1, 2 and 100 are arithmetic; anything else inside a function body
    is a threshold that should have been a named constant."""
    literals = {}
    for node in ast.walk(_module_ast()):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for inner in ast.walk(ast.Module(body=node.body, type_ignores=[])):
                if isinstance(inner, ast.Constant) and isinstance(inner.value, (int, float)) \
                        and not isinstance(inner.value, bool) and inner.value not in (0, 1, 2, 100):
                    literals.setdefault(node.name, []).append(inner.value)
    assert not literals, literals


def test_the_gate_letters_and_the_vocabulary():
    assert quality.GRADE_GATE_LETTERS == ("2", "H")
    assert set(quality.GRADE_GATE_LETTERS) <= set(LETTERS)
    assert quality.VETO_NAMES == ("up_days", "not_linear")
    assert [c.letter for c in run(ideal_bars()).checks] == list(LETTERS) + list(quality.EXTRA_CHECKS)
