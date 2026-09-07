"""Layer 2 -- the 2LYNCH checklist's shape, invariants and verdicts.

Two groups of tests live here, and they are deliberately different in kind.

The first group asserts the contract every other layer depends on: six
checks, a consistent count, one detail line each, and an input frame that
comes back unmodified. It uses the shared `ohlcv` fixture and asserts no
measurement.

The second group (`step 7`) asserts verdicts, because step 7 fixed maths
that inverted two checks' meaning: L scored a smooth collapse as a perfect
setup, and Y measured the extension of yesterday's price instead of the
burst-day price a trader would pay. Those tests build their own arithmetic
frames rather than using tests/synthetic.py, whose kinds come from
hard-clipped random returns and cannot express "an orderly 45% collapse"
without disturbing the other five checks at the same time.
"""

from __future__ import annotations

import math
import pathlib
import re

import numpy as np
import pandas as pd
import pytest

from src.lynch import (
    BREAKDOWN_LOOKBACK,
    BURST_BAR_KEYS,
    VETO_RULES,
    BREAKDOWN_PCT,
    MAX_CONSECUTIVE_UP_DAYS,
    MAX_D1_MOVE,
    MAX_D1_RANGE_RATIO,
    MAX_D1_VOL_RATIO,
    MAX_EXT_VS_SMA20,
    MAX_PRIOR_BURSTS,
    PRIOR_BURST_PCT,
    MAX_RUN_UP_1MO,
    MAX_TIGHTNESS,
    MIN_CLOSE_POS,
    MIN_LINEAR_R2,
    MIN_LINEAR_SLOPE,
    WINDOWS,
    _bar_width,
    consecutive_up_days,
    evaluate_2lynch,
    extra_context,
    failed_vetoes,
    veto_reason,
    worst_base_day,
)
from tests.synthetic import KINDS, frame_digest, make_ohlcv

CHECK_LETTERS = ["2", "C", "H", "L", "N", "Y"]


@pytest.fixture
def lynch(ohlcv):
    return evaluate_2lynch(ohlcv("burst"))


def test_result_has_the_documented_keys(lynch):
    assert set(lynch) == {"checks", "passes", "total", "summary", "detail_lines",
                          "vetoes", "context_checks"}


def test_there_are_exactly_six_checks(lynch):
    assert lynch["total"] == 6
    assert len(lynch["checks"]) == 6
    # Names carry the strategy letter as a prefix (2, L, Y, N, C, H); step 7
    # may reword the rest of a name, so only the letter is asserted.
    assert sorted(name[0] for name in lynch["checks"]) == CHECK_LETTERS


def test_every_check_reports_a_verdict_and_a_measurement(lynch):
    for name, check in lynch["checks"].items():
        assert set(check) == {"pass", "value"}, name
        assert isinstance(bool(check["pass"]), bool), name
        assert isinstance(check["value"], str) and check["value"], name


def test_passes_count_matches_the_checks(lynch):
    assert lynch["passes"] == sum(1 for c in lynch["checks"].values() if c["pass"])
    assert 0 <= lynch["passes"] <= 6
    assert lynch["summary"] == f"{lynch['passes']}/6"


def test_detail_lines_cover_every_check(lynch):
    lines = lynch["detail_lines"]
    assert len(lines) == 6
    for name, check in lynch["checks"].items():
        matching = [line for line in lines if name in line]
        assert len(matching) == 1, f"{name} should appear in exactly one detail line"
        assert matching[0].startswith("PASS" if check["pass"] else "FAIL")
        assert check["value"] in matching[0]


@pytest.mark.parametrize("kind", KINDS)
def test_checklist_runs_on_every_shape_of_history(kind, ohlcv):
    """Whatever the last bar looks like, the checklist must return a result
    rather than raise -- the pipeline calls it on every candidate."""
    result = evaluate_2lynch(ohlcv(kind))
    assert result["total"] == 6
    assert 0 <= result["passes"] <= 6


def test_checklist_does_not_mutate_the_caller_frame(ohlcv):
    """The same frame is handed to the chart renderer afterwards."""
    df = ohlcv("burst")
    before = frame_digest(df)
    evaluate_2lynch(df)
    assert frame_digest(df) == before


def test_extra_context_shape(ohlcv):
    ctx = extra_context(ohlcv("burst"))
    assert set(ctx) == {
        "pct_off_52w_high",
        "pct_above_52w_low",
        "perf_3mo_pct",
        "perf_6mo_pct",
        "consecutive_up_days",
        "worst_base_day_pct",
        # Spread rather than typed out, which is what holds the constant and
        # the function to each other: BURST_BAR_KEYS is what
        # knowledge/strategy.md is required to explain and what the archive is
        # asserted to keep, so a key renamed in one place and not the other is
        # a rulebook instructing on a field nothing sends.
        *BURST_BAR_KEYS,
    }
    assert all(isinstance(v, (int, float)) for v in ctx.values())


def test_extra_context_degrades_on_a_short_history(ohlcv):
    """Fewer than 63 sessions: the performance fields report 'n/a' instead of
    raising, because a freshly-listed ticker still has to be scoreable."""
    ctx = extra_context(ohlcv("base").iloc[-40:])
    assert ctx["perf_3mo_pct"] is None
    assert ctx["perf_6mo_pct"] is None


# ------------------------------------------------- step 7: the verdicts ----
#
# Every bar below is arithmetic, not random, so when a check flips it flips
# because of the keyword that changed and nothing else. `_reference()` is
# shaped to pass all six checks; each rejection test changes exactly one
# keyword and asserts that exactly one check went red.


def _frame(
    *,
    trend_pct: float = 9.0,
    trend_days: int = 23,
    shelf_days: int | None = None,
    burst_pct: float = 8.0,
    wide_range: float = 0.040,
    tight_range: float = 0.020,
    shelf_ranges: tuple[float, ...] | None = None,
    d1_range: float | None = None,
    burst_zero_range: bool = False,
    burst_close_pos: float = 0.98,
    burst_gap_pct: float | None = None,
    burst_low_pct: float | None = None,
    d1_move_pct: float = 0.0,
    d1_volume_mult: float = 1.0,
    wave_pct: float = 0.0,
    wave_period: float = 14.0,
    prior_burst_pct: float = 4.2,
    prior_burst_offsets: tuple[int, ...] = (),
    old_volume_mult: float = 1.0,
    up_run_days: int = 0,
    up_run_pct: float = 0.4,
    base_drop_pct: float = 0.0,
    base_drop_offset: int = 5,
    days: int = 200,
) -> pd.DataFrame:
    """One candidate's daily history, built from the parameters alone.

    A long flat stretch, then `trend_days` sessions travelling `trend_pct` in
    a straight line on log closes, then a quiet shelf out to the burst day,
    then a `burst_pct` up-day closing near its high on 8x volume. Ranges are
    `wide_range` per day except across the shelf, so N sees a real
    consolidation. Volume is flat, so C's volume ratio is exactly 1.00x.

    The rest of the keywords each disturb ONE measurement, so a check can be
    pushed over its own threshold without moving any other check's input:

      shelf_days           length of the quiet shelf, independently of how
                           long the advance ran. Defaults to the original
                           `30 - trend_days`, so every frame built before this
                           keyword existed is byte-identical.
      shelf_ranges         the widths of the last N sessions before the
                           burst, oldest first, overriding `tight_range` over
                           those sessions and no others. None keeps the flat
                           shelf every frame built before this keyword
                           existed had -- and a flat shelf is a frame on
                           which the mean of the rounded widths, the rounded
                           mean of them, and the width of any ONE of them are
                           all the same number, so it can tell no two of
                           those denominators apart.
      burst_close_pos      where in its own range the burst day closes (H).
      burst_gap_pct        where the burst bar OPENED, as a % from the prior
                           close. None keeps the +0.5% every frame built
                           before this keyword existed opened on, so those
                           frames stay byte-identical.
      burst_low_pct        where its low sat, as a % from the prior close
                           (None keeps the -0.1% it has always had). The high
                           follows from the low and `burst_close_pos`, so
                           this widens or narrows the bar without moving its
                           close, its gain, its volume or where in its own
                           range it closed -- the four things two bars of
                           very different shape can share.
      d1_move_pct          how far the last pre-burst day moved (C).
      d1_volume_mult       that day's volume, against a flat history (C).
      wave_pct/_period     a slow sine ride superimposed on the advance, so
                           the fit stays UP but stops being a straight line
                           (L's R², with L's slope left positive).
      prior_burst_offsets  sessions before the burst that spike `prior_burst_pct`
                           and give it straight back, each one a prior 4% day
                           for check 2 and nothing else: closes only, never
                           ranges or volume, and never the day the other
                           checks read.
      old_volume_mult      volume before the trailing window C averages over,
                           for pinning which sessions that window contains.
      up_run_days/_pct     a run of `up_run_days` sessions each closing
                           `up_run_pct` higher, ending the day BEFORE the
                           burst — the run src.lynch's up-days veto counts.
                           Written onto the flat shelf, so nothing before the
                           run moves and the six checks see the same shelf
                           they always did.
      base_drop_pct/_offset  one session `base_drop_offset` days before the
                           burst that falls `base_drop_pct`, given straight
                           back over the TWO sessions after it: one written
                           here, one free because the shelf is already at its
                           old level. Two, not one, because a single give-back
                           of 4%+ is a prior burst and would move check 2
                           instead — which also bounds the knob at about -7.7%,
                           past which each half is itself a 4% day. The default
                           offset sits inside the flat shelf, so the drop day's
                           own move IS `base_drop_pct` and not that plus a
                           session of the advance.
    """
    burst_i = days - 1
    shelf = 30 - trend_days if shelf_days is None else shelf_days
    trend_start = burst_i - trend_days - shelf

    close = np.full(days, 40.0)
    step = (1.0 + trend_pct / 100.0) ** (1.0 / (trend_days - 1))
    for i in range(trend_start + 1, trend_start + trend_days):
        close[i] = close[i - 1] * step
    close[trend_start + trend_days : burst_i] = close[trend_start + trend_days - 1]
    if wave_pct:
        for k, i in enumerate(range(trend_start + 1, trend_start + trend_days)):
            close[i] *= 1.0 + (wave_pct / 100.0) * np.sin(2 * np.pi * k / wave_period)
    if base_drop_pct:
        drop = close[burst_i - base_drop_offset] * (1.0 + base_drop_pct / 100.0)
        back = (close[burst_i - base_drop_offset] / drop) ** 0.5
        close[burst_i - base_drop_offset] = drop
        close[burst_i - base_drop_offset + 1] = drop * back
    if up_run_days:
        for i in range(up_run_days, 0, -1):
            close[burst_i - i] = close[burst_i - i - 1] * (1.0 + up_run_pct / 100.0)
    for offset in prior_burst_offsets:
        close[burst_i - offset] *= 1.0 + prior_burst_pct / 100.0
    if d1_move_pct:
        close[burst_i - 1] *= 1.0 + d1_move_pct / 100.0
    close[burst_i] = close[burst_i - 1] * (1.0 + burst_pct / 100.0)

    span = np.full(days, wide_range)
    span[burst_i - shelf : burst_i] = tight_range
    if shelf_ranges is not None:
        span[burst_i - len(shelf_ranges) : burst_i] = shelf_ranges
    if d1_range is not None:
        span[burst_i - 1] = d1_range

    high = close * (1.0 + span / 2.0)
    low = close * (1.0 - span / 2.0)
    open_ = close.copy()

    prev = close[burst_i - 1]
    if burst_zero_range:
        high[burst_i] = low[burst_i] = open_[burst_i] = close[burst_i]
    else:
        low[burst_i] = prev * (0.999 if burst_low_pct is None
                               else 1.0 + burst_low_pct / 100.0)
        high[burst_i] = low[burst_i] + (close[burst_i] - low[burst_i]) / burst_close_pos
        open_[burst_i] = prev * (1.005 if burst_gap_pct is None
                                 else 1.0 + burst_gap_pct / 100.0)

    volume = np.full(days, 3_000_000.0)
    # Everything older than the sessions C averages over. Flat at 1.0x, so
    # this is invisible unless a test asks which sessions that window holds.
    # Read off WINDOWS rather than spelled 51, so this stays the boundary it
    # describes; the window's VALUE is pinned by a test of its own, which is
    # what stops the fixture from moving with a mutant and hiding it.
    volume[: burst_i - (WINDOWS["volume_norm_sessions"] + 1)] *= old_volume_mult
    volume[burst_i] = 24_000_000.0
    volume[burst_i - 1] *= d1_volume_mult
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=pd.bdate_range(end="2026-07-01", periods=days, name="timestamp"),
    )[["Open", "High", "Low", "Close", "Volume"]]


def _reference() -> pd.DataFrame:
    """A clean setup: orderly advance, quiet shelf, ordinary burst."""
    return _frame()


def _only_failure_is(result: dict, letter: str) -> None:
    """Assert `letter` is the one check that failed.

    This is the guard the rejection tests are worthless without. A frame
    built to probe L that happens to fail C as well proves nothing about L,
    and this project has already shipped three tests that watched a different
    rule fail than the one they named.
    """
    failed = sorted(name for name, check in result["checks"].items() if not check["pass"])
    detail = "\n    ".join(result["detail_lines"])
    assert len(failed) == 1 and failed[0].startswith(letter), (
        f"expected {letter} to be the only failing check, got {failed}\n    {detail}"
    )


def _signed_numbers(value: str) -> list[float]:
    """The explicitly-signed measurements in a check's value string.

    Signed, so an unsigned R² is not mistaken for a direction.
    """
    return [float(n) for n in re.findall(r"[-+]\d+(?:\.\d+)?", value)]


def test_the_reference_frame_passes_every_check():
    """The baseline the rejection tests are measured against. If this stops
    being 6/6 the tests below stop meaning what they say."""
    result = evaluate_2lynch(_reference())
    assert result["passes"] == 6, "\n".join(result["detail_lines"])


# ---- L: orderly is not enough; the prior move has to be orderly UP --------


def test_a_smooth_downtrend_fails_the_linear_prior_move_check():
    """A 45% slide in a straight line is the dead-cat bounce
    knowledge/strategy.md lists as an automatic skip. Judged on R² alone it
    scored a flawless R²=1.00 and passed."""
    result = evaluate_2lynch(_frame(trend_pct=-45.0))
    _only_failure_is(result, "L")


def test_the_same_shape_upward_passes_the_linear_prior_move_check():
    """The control for the test above: same frame, opposite sign. Only the
    direction of the prior move separates the two, so a FAIL there is about
    direction and not about tightness, volume or the burst bar."""
    result = evaluate_2lynch(_frame(trend_pct=+9.0))
    assert result["checks"]["L_linear_prior_move"]["pass"]


def test_the_linear_prior_move_detail_states_which_way_the_move_went():
    """The value string goes verbatim into Claude's prompt. 'R²=1.00 over
    prior 30 days' told the model the structure was orderly and left out that
    it was orderly downwards."""
    down = evaluate_2lynch(_frame(trend_pct=-45.0))["checks"]["L_linear_prior_move"]["value"]
    up = evaluate_2lynch(_frame(trend_pct=+9.0))["checks"]["L_linear_prior_move"]["value"]
    assert any(n < 0 for n in _signed_numbers(down)), f"no falling trend reported in {down!r}"
    assert _signed_numbers(up) and all(n > 0 for n in _signed_numbers(up)), up


# ---- Y: extension is a fact about the price you would pay -----------------


def test_a_large_gap_up_fails_the_young_trend_check():
    """A +35% burst is 30%+ above its own 20-day base the moment it prints.
    Measured on the frame with the burst day removed it read as barely
    extended and passed."""
    result = evaluate_2lynch(_frame(burst_pct=35.0))
    _only_failure_is(result, "Y")


def test_an_ordinary_burst_from_the_same_base_passes_the_young_trend_check():
    """The control: same base, a burst of the size this strategy is built to
    catch. The gap-up above fails on its size, not on the base beneath it."""
    result = evaluate_2lynch(_frame(burst_pct=8.0))
    assert result["checks"]["Y_young_trend"]["pass"]


def test_the_young_trend_check_can_see_the_burst_day():
    """The sharpest statement of the bug: both halves of Y ran off the frame
    with the burst removed, so a +6% day and a +35% gap on an identical base
    produced byte-identical measurements."""
    small = evaluate_2lynch(_frame(burst_pct=6.0))["checks"]["Y_young_trend"]["value"]
    large = evaluate_2lynch(_frame(burst_pct=35.0))["checks"]["Y_young_trend"]["value"]
    assert small != large, f"Y reports {small!r} whatever the burst day did"


# ---- C and H: measurements that were taken and then thrown away ----------


def test_a_wild_swing_the_day_before_is_not_a_calm_day():
    """C measured the prior day's range, printed it to Claude, then left it
    out of the verdict: a day that closed unchanged after a 15%-wide swing
    counted as 'the quiet before the move'."""
    result = evaluate_2lynch(_frame(d1_range=0.15, tight_range=0.005))
    _only_failure_is(result, "C")


def test_a_zero_range_burst_bar_does_not_get_a_free_pass():
    """`close_pos = ... if rng else 1.0` handed a bar with no high-low range
    a PASS and told Claude it 'closed at 100% of day's range'."""
    result = evaluate_2lynch(_frame(burst_zero_range=True))
    _only_failure_is(result, "H")
    assert "100%" not in result["checks"]["H_close_near_high"]["value"]


# --- the fixture generator applies these same rules to hand-authored
# measurements. It used to hold its own copies of the thresholds and fell
# silently behind the step-7 fixes, so docs/data.json -- and the per-check pass
# rates the dashboard aggregates from it -- described a checklist that no longer
# existed. Nothing pinned the two together, which is why it was invisible.

def test_the_fixture_generator_imports_the_thresholds_rather_than_copying_them():
    import pathlib
    import re

    import src.lynch as lynch_mod

    generator = (pathlib.Path(__file__).resolve().parent.parent
                 / "tools" / "make_fixture.py").read_text()

    names = [n for n in dir(lynch_mod)
             if n.isupper() and isinstance(getattr(lynch_mod, n), (int, float))]
    assert names, "src.lynch exposes no threshold constants to import"

    missing = [n for n in names if n not in generator]
    assert not missing, (
        f"tools/make_fixture.py does not reference {missing}. If it re-declares a "
        "threshold instead of importing it, the fixture can drift from the real "
        "checklist without anything failing -- which has already happened once."
    )

    # And no bare numeric threshold left in the mirror's verdicts.
    verdicts = re.findall(r'"pass":\s*([^,\n]+(?:\n[^,\n]+)?)', generator)
    literals = [v for v in verdicts if re.search(r"\b\d+\.\d+\b", v)]
    assert not literals, (
        f"these verdicts still compare against a hard-coded number: {literals}"
    )


# ============================ step 6b: one canary per threshold ============
#
# Step 7 fixed four checks and pinned the four verdicts it changed. It left
# the other thresholds unasserted: MAX_PRIOR_BURSTS, MIN_LINEAR_R2, both
# halves of Y, MAX_TIGHTNESS, two of C's three clauses and MIN_CLOSE_POS
# could all be deleted or retuned with this file green.
#
# Each test below moves ONE input of ONE check across ONE threshold and
# asserts, through `_only_failure_is`, that no other check moved with it. A
# check with two or three clauses gets one test per clause, plus an assertion
# that the clauses it is NOT about are still satisfied -- otherwise a canary
# for the run-up half of Y would keep passing after the run-up half was
# deleted, because the extension half was over its own line too.


def _reported(value: str, pattern: str) -> float:
    """One measurement out of a check's value string.

    The strings are what src.scorer puts in front of Claude, so pinning a
    measurement here pins the number the model is told as well as the verdict
    the pipeline computes from it.
    """
    match = re.search(pattern, value)
    assert match, f"{pattern!r} found no measurement in {value!r}"
    return float(match.group(1))


# ---- 2: how many bursts the leg has already had --------------------------


def test_one_earlier_burst_is_still_a_first_or_second_burst():
    """The boundary is inclusive: MAX_PRIOR_BURSTS is the count still allowed,
    not the count that fails. The rejection test below is only about the
    threshold if this frame is on the passing side of it."""
    result = evaluate_2lynch(_frame(prior_burst_offsets=(3,)))
    assert result["passes"] == 6, "\n".join(result["detail_lines"])
    assert _reported(result["checks"]["2_first_or_second_burst"]["value"],
                     r"^(\d+) prior") == MAX_PRIOR_BURSTS


def test_a_leg_that_has_already_burst_twice_fails_the_first_or_second_check():
    """The fifth burst of a leg is what this check exists to reject. Nothing
    asserted it: the whole check could be deleted with the suite green."""
    result = evaluate_2lynch(_frame(prior_burst_offsets=(3, 5)))
    _only_failure_is(result, "2")
    assert _reported(result["checks"]["2_first_or_second_burst"]["value"],
                     r"^(\d+) prior") > MAX_PRIOR_BURSTS


def test_a_day_short_of_the_burst_size_is_not_counted_as_a_prior_burst():
    """What counts as an EARLIER burst is its own number, and it used to be a
    bare 4.0 inside evaluate_2lynch -- the only copy of the scanner's
    min_gain_pct that no other layer could see, and invisible to the rules
    fingerprint. It is PRIOR_BURST_PCT now, and this is its canary: two days
    just under it are the same shape of frame as the rejection above and must
    still be a first burst, while two days ON it are not. The check reports
    the threshold it applied, so the number the model is told moves with it."""
    under = evaluate_2lynch(_frame(prior_burst_pct=PRIOR_BURST_PCT - 0.5,
                                   prior_burst_offsets=(3, 5)))
    assert under["passes"] == 6, "\n".join(under["detail_lines"])
    assert _reported(under["checks"]["2_first_or_second_burst"]["value"],
                     r"^(\d+) prior") == 0
    assert f"{PRIOR_BURST_PCT:g}% bursts" in under["checks"]["2_first_or_second_burst"]["value"]

    on_it = evaluate_2lynch(_frame(prior_burst_pct=PRIOR_BURST_PCT,
                                   prior_burst_offsets=(3, 5)))
    _only_failure_is(on_it, "2")
    assert _reported(on_it["checks"]["2_first_or_second_burst"]["value"],
                     r"^(\d+) prior") > MAX_PRIOR_BURSTS, "inclusive at the threshold"


def test_a_burst_older_than_the_lookback_is_not_held_against_the_leg():
    """The window is the last 20 sessions before the burst. Two frames that
    differ only in whether the second spike lands inside it."""
    inside = evaluate_2lynch(_frame(prior_burst_offsets=(3, 20)))
    outside = evaluate_2lynch(_frame(prior_burst_offsets=(3, 21)))
    _only_failure_is(inside, "2")
    assert outside["passes"] == 6, "\n".join(outside["detail_lines"])


# ---- L: the fit has to be tight as well as rising ------------------------


def test_a_choppy_advance_fails_the_linear_check_although_it_ends_higher():
    """The R² half of L. Step 7 pinned the slope half -- a smooth collapse --
    and left this one unasserted, so `r2 >= MIN_LINEAR_R2` could be dropped
    and the check would accept any advance of any shape.

    This ride ends up, so the slope clause is satisfied and cannot be what
    fails. Only the fit quality is over its line.
    """
    result = evaluate_2lynch(_frame(wave_pct=5.0))
    _only_failure_is(result, "L")
    value = result["checks"]["L_linear_prior_move"]["value"]
    assert _reported(value, r"R²=([\d.]+)") < MIN_LINEAR_R2
    fitted = _signed_numbers(value)
    assert fitted and fitted[0] > MIN_LINEAR_SLOPE, (
        f"the prior move must still be rising, or this is the slope test again: {value!r}")


# ---- Y: two clauses, and a canary for each -------------------------------


def _young_trend(result: dict) -> tuple[float, float]:
    """(% run-up over the past month, % above the 20-day average)."""
    run_up, ext = _signed_numbers(result["checks"]["Y_young_trend"]["value"])
    return run_up, ext


def test_a_month_long_run_up_fails_the_young_trend_check_on_its_own():
    """A 35% advance into a 2% burst. Extended by the month it has had, not
    by today -- the extension clause is comfortably inside its own limit, so
    deleting `run_up_1mo < MAX_RUN_UP_1MO` makes this frame pass."""
    result = evaluate_2lynch(_frame(trend_days=14, shelf_days=7, trend_pct=35.0, burst_pct=2.0))
    _only_failure_is(result, "Y")
    run_up, ext = _young_trend(result)
    assert run_up > MAX_RUN_UP_1MO
    assert ext < MAX_EXT_VS_SMA20, "the extension clause must not be what failed"


def test_extension_above_the_20_day_base_fails_the_young_trend_check_on_its_own():
    """The mirror image: a flat month and an 18% burst off the base. The
    run-up clause is inside its limit, so deleting `ext_vs_sma20 <
    MAX_EXT_VS_SMA20` makes this frame pass."""
    result = evaluate_2lynch(_frame(trend_pct=0.5, burst_pct=18.0))
    _only_failure_is(result, "Y")
    run_up, ext = _young_trend(result)
    assert ext > MAX_EXT_VS_SMA20
    assert run_up < MAX_RUN_UP_1MO, "the run-up clause must not be what failed"


def test_a_run_up_exactly_on_the_young_trend_limit_is_already_too_extended():
    """Y's clauses are strict, and this frame is the only one that can say so.

    A month that travelled exactly MAX_RUN_UP_1MO fails. Reachable only by
    construction: `(close[-1] / close[-21] - 1) * 100` lands on 25.0 exactly
    when the ratio is 1.25, a number binary floating point holds exactly --
    which the 4% gain in src.scanner, by contrast, cannot reach at all. A ramp
    from 40 to 50 over the 21 sessions is that ratio.

    The extension clause is left at +10.5%, so this is Y's run-up boundary and
    nothing else.
    """
    frame = _frame(trend_pct=0.5)
    last = len(frame) - 1
    closes = frame["Close"].to_numpy().copy()
    spans = ((frame["High"] - frame["Low"]) / frame["Close"]).to_numpy()
    closes[last - 20:] = np.linspace(40.0, 40.0 * (1 + MAX_RUN_UP_1MO / 100.0), 21)
    high, low, open_ = (closes * (1 + spans / 2), closes * (1 - spans / 2), closes.copy())
    low[last] = closes[last] - 0.98 * 10.0
    high[last], open_[last] = low[last] + 10.0, low[last] + 1.0
    for column, values in (("Close", closes), ("High", high), ("Low", low), ("Open", open_)):
        frame[column] = values
    assert (closes[last] / closes[last - 20] - 1) * 100 == MAX_RUN_UP_1MO, (
        "this frame has to land ON the threshold, not near it")

    result = evaluate_2lynch(frame)

    _only_failure_is(result, "Y")
    run_up, ext = _young_trend(result)
    assert run_up == MAX_RUN_UP_1MO
    assert ext < MAX_EXT_VS_SMA20, "the extension clause must not be what failed"


# ---- N: the shelf has to be quieter than the stock's own norm -------------


def test_a_shelf_no_quieter_than_the_stock_itself_is_not_a_consolidation():
    """MAX_TIGHTNESS was unasserted: N could be deleted outright, and a name
    that had done nothing but chop at its usual amplitude would be reported
    to Claude as a narrow base. The prior day is left tight so that C, which
    reuses this baseline, is not the check that fails."""
    result = evaluate_2lynch(_frame(tight_range=0.050, d1_range=0.020))
    _only_failure_is(result, "N")
    assert _reported(result["checks"]["N_narrow_consolidation"]["value"],
                     r"= ([\d.]+)x its norm") > MAX_TIGHTNESS


def test_a_shelf_exactly_as_quiet_as_its_norm_is_still_a_consolidation():
    """Both range thresholds are inclusive, and both are asserted here.

    A shelf AT the norm passes N, and a prior day whose range is AT the norm
    passes C's range clause -- `<=` in both, and this is the only frame in the
    suite that can tell either from `<`. Landing exactly on 1.00x is not
    something the builder can be asked for: every span it is given comes back
    as 0.9999999999999992 or 1.0000000000000004, because the daily range is a
    division by a close that moves. Constant bars over the whole pre-burst
    window make the two means bit-identical instead of merely equal to two
    decimal places.

    L is the one failure, and it is not incidental: a prior move that is
    perfectly flat has no trend to fit, which is L's business and not N's.
    """
    frame = _frame()
    last = len(frame) - 1
    for column, value in (("Close", 40.0), ("High", 41.0), ("Low", 39.0), ("Open", 40.0)):
        frame.iloc[:last, frame.columns.get_loc(column)] = value
    burst_close = 40.0 * 1.08
    low = burst_close - 0.98 * 10.0
    for column, value in (("Close", burst_close), ("Low", low),
                          ("High", low + 10.0), ("Open", low + 1.0)):
        frame.iloc[last, frame.columns.get_loc(column)] = value

    pre = frame.iloc[:-1]
    ranges = ((pre["High"] - pre["Low"]) / pre["Close"]) * 100
    assert ranges.iloc[-7:].mean() / ranges.iloc[-60:-7].mean() == MAX_TIGHTNESS, (
        "this frame has to land ON the threshold, not near it")

    result = evaluate_2lynch(frame)

    _only_failure_is(result, "L")
    assert _reported(result["checks"]["N_narrow_consolidation"]["value"],
                     r"= ([\d.]+)x its norm") == MAX_TIGHTNESS
    assert _reported(result["checks"]["C_calm_preburst_day"]["value"],
                     r"= ([\d.]+)x its norm") == MAX_D1_RANGE_RATIO


# ---- C: three clauses, and step 7 pinned only the third ------------------


def test_a_move_the_day_before_the_burst_is_not_a_calm_day():
    """MAX_D1_MOVE. A 3% day before the burst is not "the quiet before the
    move"; the range and volume clauses are untouched, so this frame passes
    every other clause of C."""
    result = evaluate_2lynch(_frame(d1_move_pct=3.0))
    _only_failure_is(result, "C")
    value = result["checks"]["C_calm_preburst_day"]["value"]
    assert _reported(value, r"prior day ([\d.]+)% move") > MAX_D1_MOVE
    assert _reported(value, r"([\d.]+)x volume") < MAX_D1_VOL_RATIO
    assert _reported(value, r"= ([\d.]+)x its norm") <= MAX_D1_RANGE_RATIO


def test_volume_arriving_the_day_before_the_burst_is_not_a_calm_day():
    """MAX_D1_VOL_RATIO. Volume showing up the day before is the setup being
    front-run; the price clauses stay clean, so only this one can fail."""
    result = evaluate_2lynch(_frame(d1_volume_mult=1.3))
    _only_failure_is(result, "C")
    value = result["checks"]["C_calm_preburst_day"]["value"]
    assert _reported(value, r"([\d.]+)x volume") > MAX_D1_VOL_RATIO
    assert _reported(value, r"prior day ([\d.]+)% move") < MAX_D1_MOVE


def test_volume_exactly_on_the_calm_days_limit_is_already_too_much():
    """C's clauses are strict where N's and H's are inclusive, and this is the
    frame that says so: a prior day at exactly MAX_D1_VOL_RATIO fails.

    Asserted rather than assumed because the asymmetry is real and invisible.
    `d1_vol_ratio < MAX_D1_VOL_RATIO` and `d1_range_ratio <=
    MAX_D1_RANGE_RATIO` sit in one boolean, one line apart. Whichever
    convention is meant, changing this one has to be a decision.
    """
    result = evaluate_2lynch(_frame(d1_volume_mult=MAX_D1_VOL_RATIO))
    _only_failure_is(result, "C")
    assert _reported(result["checks"]["C_calm_preburst_day"]["value"],
                     r"([\d.]+)x volume") == MAX_D1_VOL_RATIO


def test_the_calm_days_volume_is_measured_over_the_fifty_sessions_before_it():
    """Which sessions C's volume norm holds, pinned from both ends.

    src.scanner's trailing_volume_mean() is 50 sessions excluding the day it
    measures, and tests/test_scanner.py asserts the two windows agree -- but
    it asserts that against arithmetic it writes out itself, so this half of
    the claim was never checked. Volume older than the window is 10x here, so
    a longer window drags the ratio down; the measured day is 20x, so
    including it in its own denominator drags the ratio down too.

    What this CANNOT see is a SHORTER window, because everything inside the
    window is flat: at 30 sessions the ratio is the same 20.0x. That is how
    the bare `iloc[-51:-1]` survived round 8's sweep and stayed invisible to
    rules_fingerprint() -- the test below is the one that sits on the number.

    Deliberately not a calm day: this pins the measurement, not the verdict.
    """
    result = evaluate_2lynch(_frame(old_volume_mult=10.0, d1_volume_mult=20.0))
    ratio = _reported(result["checks"]["C_calm_preburst_day"]["value"], r"([\d.]+)x volume")
    assert ratio == pytest.approx(20.0, abs=0.01)


def test_the_calm_days_volume_norm_spans_exactly_the_window_this_module_names():
    """C's denominator is `volume_norm_sessions` sessions ending before d1.

    THE SEVENTH BARE LITERAL. Round 8 named six windows and left this one as
    `pre["Volume"].iloc[-51:-1]`, so 50 was a strategy number no other layer
    could see: changing it to 30 left rules_fingerprint() byte-identical and
    tests/test_lynch.py, tests/test_scanner.py and tests/test_docs_are_true.py
    all green while C's verdict moved. Reproduced that way before the window
    was named.

    Both edges are load-bearing here and the preconditions say so: one session
    inside the window carries 30x volume and the session just outside it 10x,
    so a window one shorter and a window one longer each give a different
    ratio at the two decimals the line prints. The expected value is computed
    from the frame THROUGH the named window, so this dies when the code slices
    a length the dict does not name -- and the value of the window itself is
    pinned separately, since a test that reads the constant cannot fail on it.
    """
    df = _reference()
    window = WINDOWS["volume_norm_sessions"]
    volume = df["Volume"].to_numpy(dtype=float).copy()
    volume[-(window + 2)] *= 30.0   # the OLDEST session the window should hold
    volume[-(window + 3)] *= 10.0   # the newest session it should not
    df = df.assign(Volume=volume)

    def ratio_over(sessions: int) -> float:
        # d1 is df.iloc[-2]; its norm is the `sessions` bars before it.
        norm = df["Volume"].iloc[-(sessions + 2):-2].mean()
        return round(float(df["Volume"].iloc[-2] / norm), 2)

    assert ratio_over(window - 1) != ratio_over(window) != ratio_over(window + 1), (
        "the frame cannot tell the neighbouring windows apart, so this test "
        "would pass whatever length the code sliced")
    reported = _reported(evaluate_2lynch(df)["checks"]["C_calm_preburst_day"]["value"],
                         r"([\d.]+)x volume")
    assert reported == ratio_over(window)


def test_the_volume_norm_and_the_scans_own_volume_window_are_one_number():
    """50, in two layers, held equal on purpose.

    src.scanner.ScanConfig's comment argues the equality ("two layers of one
    pipeline disagreeing about what 'average volume' means is how a metric
    ends up meaning nothing") and nothing enforced it, because the checklist's
    half was a bare literal. Both are named now and neither imports the other,
    so this is where the judgement is written down: change one and this asks
    whether the other was meant to move too.
    """
    from src.scanner import ScanConfig

    assert WINDOWS["volume_norm_sessions"] == 50
    assert WINDOWS["volume_norm_sessions"] == ScanConfig().rvol_lookback


def test_no_check_reads_a_window_left_as_a_bare_number():
    """The structural half: the numbers this module is allowed to spell.

    A named threshold is in the fingerprint the moment it is named, and a
    window left as a literal is not -- which is the one thing rules_fingerprint()
    cannot catch, said in its own docstring. Round 8 answered that by naming
    six windows and declaring the class closed; C's 50 was the seventh and
    stayed a literal for three rounds. So this reads the constants out of the
    module's own AST rather than trusting a list somebody remembered to
    update: anything outside the set below is an index, a rounding place, a
    percent conversion or a documented sentinel -- or it is a strategy number,
    and belongs in WINDOWS or beside the thresholds.

    EVERY FUNCTION, not evaluate_2lynch alone. The guard that first closed
    this was scoped by name to one function while `extra_context()` -- four
    fields of the same metrics payload, archived in every row's `context` --
    spelled 252, 126, 63 and 60, and three audit lenses found it
    independently. A guard whose scope is narrower than the class it names is
    how a class gets declared closed on the instance nobody looked at, twice
    over the same numbers.

    WHAT THIS STILL CANNOT SEE, said here rather than implied by its silence:
    the set is keyed on VALUE, so a window of 2 sessions or a threshold of
    100% spelled bare would pass. The two sides of that are covered by the
    guards either side of this one --
    test_every_window_this_module_names_is_one_it_actually_measures_over reads
    the WINDOWS subscripts out of the AST, and
    test_every_threshold_this_module_names_is_one_its_own_code_reads asserts
    each named threshold is read -- so what is left uncovered is a number that
    was NEVER named, at one of five values. A number written in words inside
    an f-string is not an ast.Constant numeric either, which is why the L and
    Y lines are rendered under a patched WINDOWS above rather than read.
    """
    import ast
    import inspect

    import src.lynch as lynch_mod

    allowed = {
        0: "list/series indices and the zero comparisons",
        1: "iloc[-1], the +1 that turns a window into a slice, and 1.0 ratios",
        2: "iloc[-2] and the two decimal places every ratio is shown at",
        3: "_log_trend's minimum points: two fit a line exactly and have no R²",
        100: "ratio -> percent",
        9.9: "N's documented no-usable-norm sentinel, which prints as 9.90x",
    }
    tree = ast.parse(inspect.getsource(lynch_mod))
    spelled: dict[float, list[str]] = {}
    for func in ast.walk(tree):
        if not isinstance(func, ast.FunctionDef):
            continue
        for node in ast.walk(func):
            if (isinstance(node, ast.Constant) and not isinstance(node.value, bool)
                    and isinstance(node.value, (int, float))):
                spelled.setdefault(node.value, []).append(func.name)
    unnamed = sorted(((v, sorted(set(where))) for v, where in spelled.items()
                      if v not in allowed), key=str)
    assert not unnamed, (
        f"src.lynch spells {unnamed} as a bare number; a window belongs in "
        "WINDOWS and a threshold beside the other thresholds, or rules_fingerprint() "
        "cannot see it")


# ---- H: where in the day's range the burst closed ------------------------


def test_a_burst_that_closed_mid_range_fails_the_high_close_check():
    """MIN_CLOSE_POS. Step 7 pinned only the zero-range bar, so the threshold
    itself could be deleted and every burst would pass H whatever it did
    after lunch."""
    result = evaluate_2lynch(_frame(burst_close_pos=0.55))
    _only_failure_is(result, "H")
    assert _reported(result["checks"]["H_close_near_high"]["value"],
                     r"closed at (\d+)% ") < MIN_CLOSE_POS * 100


def test_a_burst_closing_exactly_on_the_threshold_is_kept():
    """Inclusive, like the scanner's relative-volume boundary: a name is not
    dropped for landing on the line.

    The bar is written directly rather than asked for through
    `burst_close_pos`, and that is the whole difficulty of this test. The
    builder's high is derived by DIVIDING by the position it was asked for, so
    `close_pos` comes back as 0.7000000000000002 -- over the line rather than
    on it, and a suite that accepted that could not tell `>=` from `>`
    (measured: flipping the operator left this file green). Ten dollars wide
    with the close 0.7 x 10 above the low keeps every subtraction exact in
    binary, so the position really is the constant.
    """
    frame = _frame()
    close = float(frame["Close"].iloc[-1])
    low = close - MIN_CLOSE_POS * 10.0
    for column, value in (("Low", low), ("High", low + 10.0), ("Open", low + 1.0)):
        frame.iloc[-1, frame.columns.get_loc(column)] = value
    assert (close - low) / (low + 10.0 - low) == MIN_CLOSE_POS, (
        "this frame has to land ON the threshold, not near it")

    result = evaluate_2lynch(frame)

    assert result["checks"]["H_close_near_high"]["pass"], (
        result["checks"]["H_close_near_high"]["value"])
    assert result["passes"] == 6, "\n".join(result["detail_lines"])


# ---- Bonde's two rules, which are not checks -----------------------------
# Both are measured on the same frames as the checklist and neither is a vote.
# The tests below are written to fail if either ever becomes one: the six-check
# structure is what MIN_LYNCH_PASSES is a majority OF, and what the email, the
# page, tools/make_fixture.py and every archived `lynch_total` are built on.


def test_neither_new_rule_became_a_seventh_or_eighth_check():
    """The structural half, asserted on a frame where BOTH rules fire.

    A frame that broke the veto AND failed the breakdown criterion would, if
    either had been added to `checks`, report 6/8 here. MIN_LYNCH_PASSES is 3
    of 6 -- a majority -- and 3 of 8 is a weaker gate wearing the same number.
    """
    result = evaluate_2lynch(_frame(up_run_days=3, base_drop_pct=-5.0))

    assert result["passes"] == 6 and result["total"] == 6
    assert len(result["checks"]) == 6 and len(result["detail_lines"]) == 6
    assert result["summary"] == "6/6"
    assert failed_vetoes(result) == ["up_days"]
    assert not result["context_checks"]["base_breakdown"]["pass"]


def test_a_burst_after_three_up_days_is_refused_though_it_passes_every_check():
    """MAX_CONSECUTIVE_UP_DAYS, and the whole reason it is a veto.

    This is the case the rule exists for: a 6/6 setup that Bonde refuses
    anyway. If the rule were a seventh checklist item this frame would score
    6/7, clear the 3-of-N gate comfortably, and be scored.
    """
    result = evaluate_2lynch(_frame(up_run_days=MAX_CONSECUTIVE_UP_DAYS + 1))

    assert result["passes"] == 6, "\n".join(result["detail_lines"])
    assert failed_vetoes(result) == ["up_days"]
    assert not result["vetoes"]["up_days"]["pass"]


def test_a_burst_after_exactly_the_allowed_run_is_not_refused():
    """The control, ON the boundary rather than near it. Without this the test
    above passes for any threshold at all, including one that refuses every
    burst that follows a single up day."""
    result = evaluate_2lynch(_frame(up_run_days=MAX_CONSECUTIVE_UP_DAYS))

    assert result["passes"] == 6, "\n".join(result["detail_lines"])
    assert failed_vetoes(result) == []
    assert result["vetoes"]["up_days"]["pass"]


def test_the_run_counted_is_the_one_before_the_burst_not_including_it():
    """The burst day is a big up day by construction, so a count that included
    it would read 1 on a frame whose shelf is flat -- and would refuse every
    burst that followed two up days rather than three."""
    assert consecutive_up_days(_frame()) == 0
    assert consecutive_up_days(_frame(up_run_days=1)) == 1
    # The rule's own arithmetic, stated the other way round: N up days before
    # the burst is N, whatever the burst day did.
    for n in range(4):
        assert consecutive_up_days(_frame(up_run_days=n, burst_pct=12.0)) == n


def test_the_up_day_count_reaches_the_model_and_the_archive():
    """extra_context() is spread into the metrics block src.scorer sends and is
    archived as the row's `context`. A number the model is told to weigh has to
    be the measured one -- knowledge/strategy.md distinguishes 0 from 2."""
    for n in range(MAX_CONSECUTIVE_UP_DAYS + 1):
        assert extra_context(_frame(up_run_days=n))["consecutive_up_days"] == n


def test_a_four_percent_down_day_in_the_base_fails_the_criterion_and_rejects_nothing():
    """BREAKDOWN_PCT, on the boundary and one tenth clear of it.

    The second half of the assertion is the decision, not a detail: this rule
    is a quality criterion, so a base that broke down still passes 6/6, is
    still not vetoed, and still reaches the scoring model. Only the note it
    carries changes.
    """
    broke = evaluate_2lynch(_frame(base_drop_pct=BREAKDOWN_PCT))
    intact = evaluate_2lynch(_frame(base_drop_pct=BREAKDOWN_PCT + 0.1))

    # ON the threshold, not past it. worst_base_day() rounds to the tenth the
    # reader is shown precisely so this comparison can land on the boundary:
    # against the raw pct_change no frame can, and 8,000 adjacent close ratios
    # were tried to establish that before the rounding went in.
    assert worst_base_day(_frame(base_drop_pct=BREAKDOWN_PCT)) == BREAKDOWN_PCT
    assert not broke["context_checks"]["base_breakdown"]["pass"]
    assert intact["context_checks"]["base_breakdown"]["pass"]
    for result in (broke, intact):
        assert result["passes"] == 6, "\n".join(result["detail_lines"])
        assert failed_vetoes(result) == []


def test_a_base_day_that_rounds_onto_the_threshold_is_refused_like_one_on_it():
    """The number the reader sees and the number the rule applies are the same.

    They were not: the predicate read the raw percentage and every surface
    printed it to a tenth, so -4.04% was refused while displaying "-4.0%" and
    -3.96% passed while displaying "-4.0%" too -- two rows showing the
    threshold value, one refused and one not, under a note stating the
    threshold. Found by mutation: nothing could tell `>` from `>=` here,
    because no frame could put the raw value on the boundary at all.
    """
    just_under = evaluate_2lynch(_frame(base_drop_pct=BREAKDOWN_PCT + 0.04))
    just_over = evaluate_2lynch(_frame(base_drop_pct=BREAKDOWN_PCT - 0.04))

    shown = [r["context_checks"]["base_breakdown"]["value"] for r in (just_under, just_over)]
    assert shown[0] == shown[1], "these two rows print the same measurement"
    assert f"{BREAKDOWN_PCT:+.1f}%" in shown[0], shown[0]
    assert not just_under["context_checks"]["base_breakdown"]["pass"]
    assert not just_over["context_checks"]["base_breakdown"]["pass"]


def test_no_check_decides_on_a_number_different_from_the_one_it_prints():
    """The class the base-breakdown fix closed, swept across the checklist.

    That fix rounded ONE measurement so the archive, the note and the predicate
    were one number, and the round was declared closed — on the one criterion
    whose ambiguity rate is zero. An audit measured the others: over 600
    synthetic bursts the printed value sat exactly on its own threshold for N's
    tightness on 3.2% of frames and L's R² on 0.8%, so roughly one burst in
    thirty showed a reader "1.00x its norm" under a rule stating 1.00 and was
    refused by it, beside another shown the same string and passed.

    The value strings go verbatim into the email, the page and the scoring
    model's prompt, so this is not cosmetic: it is whether a stated rule and a
    published measurement can contradict each other.

    Asserted by SIMULATING THE READER — parse the printed numbers back out and
    apply the rule to them — rather than by re-deriving the measurement, which
    would only prove the arithmetic agrees with itself.
    """
    # 400 variants, not 120. At L's measured 0.8% ambiguity a short sweep hits
    # the boundary without hitting a DISAGREEMENT, and the first version of
    # this test passed with L's rounding deleted for exactly that reason. The
    # earliest variants that separate them under this seed are 191 and 226.
    seen = {"N": 0, "L": 0, "H": 0, "C": 0}
    for variant in range(400):
        result = evaluate_2lynch(make_ohlcv("burst", seed=[4071, variant], up_run=1))

        tight = result["checks"]["N_narrow_consolidation"]
        shown = float(re.search(r"= ([\d.]+)x its norm", tight["value"]).group(1))
        assert (shown <= MAX_TIGHTNESS) == tight["pass"], tight["value"]
        seen["N"] += abs(shown - MAX_TIGHTNESS) < 1e-9

        linear = result["checks"]["L_linear_prior_move"]
        r2, trend = re.search(r"R²=([\d.]+), fitted trend ([+-][\d.]+)%", linear["value"]).groups()
        assert (float(r2) >= MIN_LINEAR_R2 and float(trend) >= 0) == linear["pass"], linear["value"]
        seen["L"] += abs(float(r2) - MIN_LINEAR_R2) < 1e-9

        high = result["checks"]["H_close_near_high"]
        pos = float(re.search(r"closed at (\d+)% ", high["value"]).group(1)) / 100
        assert (pos >= MIN_CLOSE_POS) == high["pass"], high["value"]

        calm = result["checks"]["C_calm_preburst_day"]
        vol = float(re.search(r"([\d.]+)x volume", calm["value"]).group(1))
        if vol > MAX_D1_VOL_RATIO:
            assert not calm["pass"], calm["value"]
        seen["C"] += abs(vol - MAX_D1_VOL_RATIO) < 1e-9

    # And the sweep really did visit the boundary, rather than passing because
    # no frame came near one. N and L are the two it reaches: delete either
    # one's rounding and this test goes red. C's and H's rounding is asserted
    # on every frame above and pinned by none of them, because make_ohlcv's
    # burst bar pins close_pos at one value for every seed and its volume
    # profile never lands the ratio on 1.20 — so for those two this test is
    # documentation and not a canary, which is worth knowing before trusting
    # it. Closing that would take a frame builder that varies the burst bar,
    # which is a change to the fixture and not to this rule.
    assert seen["N"] or seen["L"], (
        f"no frame printed a value ON its threshold ({seen}), so this run "
        "proves nothing about the case the rounding exists for")


def test_a_base_with_nothing_in_it_reports_no_break_rather_than_one():
    """`worst_base_day` returns None when there is no move to measure -- a
    frame one session long, or a history that arrives as a single bar.

    Absence of evidence is not evidence of a break, so the criterion passes
    and the value says which of the two it is. The alternative reads as a
    stock that collapsed, off a frame that recorded nothing at all.
    """
    one_day = _frame().iloc[-2:]

    assert worst_base_day(one_day) is None
    note = evaluate_2lynch(one_day)["context_checks"]["base_breakdown"]
    assert note["pass"], note
    assert "no usable base" in note["value"], note["value"]


def test_the_breakdown_looks_back_exactly_the_sessions_it_says_it_does():
    """BREAKDOWN_LOOKBACK. A window one session too wide or too narrow is
    invisible to every other assertion here, because the drop is still in the
    frame either way -- only its distance from the burst changes.

    `trend_days` is shortened so the whole window sits on the flat shelf: on
    the default frame the far end of it is still climbing, and a drop written
    there would move L as well.
    """
    def worst(offset):
        return worst_base_day(_frame(base_drop_pct=-6.0, base_drop_offset=offset,
                                     trend_days=10, shelf_days=40))

    assert worst(BREAKDOWN_LOOKBACK) == pytest.approx(-6.0)
    assert worst(BREAKDOWN_LOOKBACK + 1) == pytest.approx(0.0)


def test_the_worst_base_day_reaches_the_model_and_the_archive():
    ctx = extra_context(_frame(base_drop_pct=-5.0))
    assert ctx["worst_base_day_pct"] == pytest.approx(-5.0, abs=0.05)
    assert extra_context(_frame())["worst_base_day_pct"] == pytest.approx(0.0)


def test_the_quality_note_carries_the_threshold_the_code_applied():
    """knowledge/strategy.md names this criterion and deliberately does NOT
    repeat its number, so the figure the model reads has to come from the line
    itself. Two copies of one threshold is how the fixture generator's
    checklist silently fell a step behind src/lynch.py once already."""
    value = evaluate_2lynch(_frame(base_drop_pct=-5.0))["context_checks"]["base_breakdown"]["value"]

    assert f"{BREAKDOWN_PCT:+.1f}%" in value, value
    assert str(BREAKDOWN_LOOKBACK) in value, value
    rulebook = (pathlib.Path(__file__).resolve().parent.parent
                / "knowledge" / "strategy.md").read_text()
    assert f"{BREAKDOWN_PCT:.0f}%" not in rulebook, (
        "the rulebook has grown its own copy of BREAKDOWN_PCT; it should name "
        "the criterion and let quality_notes carry the figure")


# ------------------------------- round 11: the burst bar reaches the model --
#
# The metrics block carried the burst bar's close, its gain, its volume and
# where in its own range it closed, and nothing about the bar's own geometry
# -- while knowledge/strategy.md asked the model for a "powerful burst bar"
# with a big range and named a huge GAP as the Episodic Pivot signal. Both
# questions were answerable only from the chart image, and on a night the
# render fails there is no image.


def _off_its_own_high(frame: pd.DataFrame) -> pd.DataFrame:
    """One early bar reaching above and below everything the burst bar does.

    An ordinary name bursting somewhere below its own 52-week high, which is
    what makes the pair below differ on the burst bar's shape ALONE: the two
    variants' own highs and lows differ (that is what a wide bar is), and
    without a historical extreme dominating them, `pct_off_52w_high` and
    `pct_above_52w_low` would differ too and the "exactly three keys" claim
    would be about four or five. Bar 5 of 200 sits far outside every window
    the checklist reads, so it moves nothing else.
    """
    frame = frame.copy()
    frame.iloc[5, frame.columns.get_loc("High")] = 60.0
    frame.iloc[5, frame.columns.get_loc("Low")] = 20.0
    return frame


def _payload_for(frame: pd.DataFrame) -> dict:
    """One candidate's scoring request, built the way src.pipeline builds it."""
    from src.scanner import Candidate, ScanConfig, detect_setup
    from src.scorer import metrics_payload

    setup = detect_setup(frame, ScanConfig())
    assert setup, "this frame does not carry a burst, so there is no payload"
    cand = Candidate(ticker="AAA", history=frame, **setup)
    return metrics_payload(cand, evaluate_2lynch(frame), extra_context(frame))


def test_two_burst_bars_a_trader_would_never_confuse_reach_the_model_as_one():
    """A +7.5% gap into a bar under 1% wide, against a flat open with a 9%+
    range: same close, same gain, same volume, same `H`.

    Those are two different setups -- the first has already made its move
    before anyone could act on it, the second spent the whole session making
    it -- and before this round the two produced BYTE-IDENTICAL requests.
    Reproduced through the real Candidate path, which is the point: the
    difference is not one this pipeline hid in a corner, it is one the
    scoring model was never given.

    The preconditions are executed rather than described, so this cannot
    quietly become a test of two identical bars.
    """
    gapped = _off_its_own_high(_frame(burst_gap_pct=7.5, burst_low_pct=7.0))
    wide = _off_its_own_high(_frame(burst_gap_pct=0.0, burst_low_pct=-2.0))

    for name, frame in (("gapped", gapped), ("wide", wide)):
        bar = frame.iloc[-1]
        assert bar["Low"] <= bar["Open"] <= bar["High"], f"{name}: not a bar"
    assert gapped.iloc[-1]["Open"] > wide.iloc[-1]["Open"], "the opens do not differ"

    left, right = _payload_for(gapped), _payload_for(wide)
    shared = ("close", "gain_pct", "volume", "volume_ratio", "dollar_volume",
              "2lynch_summary", "2lynch_detail")
    for key in shared:
        assert left[key] == right[key], f"the pair was built to share {key}"
    assert "of day's range" in left["2lynch_detail"][-1], "H is not the last line"

    differ = {key for key in set(left) | set(right) if left.get(key) != right.get(key)}
    assert differ == set(BURST_BAR_KEYS), (
        "the two bars reach the model as one request but for "
        f"{sorted(differ)}")


def test_the_gap_and_the_width_are_the_burst_bar_s_own_arithmetic():
    """Hand-computed off the frame's parameters, not off the code.

    The burst opens 3% above the prior close P and closes 8% above it, its
    low sits 1% below P and `burst_close_pos` puts the close at 98% of the
    range, so the high is 0.99P + 0.09P/0.98 = 1.08184P and the bar is
    0.09184P wide -- 8.5% of a 1.08P close. The shelf it came out of is
    `tight_range` wide every session, which is 2.0%/day, so the bar is 4.25
    times the width of its own consolidation.
    """
    ctx = extra_context(_frame(burst_gap_pct=3.0, burst_low_pct=-1.0))
    assert ctx["gap_pct"] == 3.0
    assert ctx["bar_range_pct"] == 8.5
    assert ctx["range_expansion"] == 4.25
    # The width is a share of the CLOSE, and on a bar closing at 98% of its
    # range the close and the high are so nearly one number that both
    # denominators round to 8.5. This one closes at 60% of a range running
    # from 0.99P to 1.14P: 0.15P over a 1.08P close is 13.9%, and over the
    # high it would be 13.2%.
    mid = extra_context(_frame(burst_gap_pct=3.0, burst_low_pct=-1.0, burst_close_pos=0.6))
    assert mid["bar_range_pct"] == 13.9
    # And the width is rounded ONCE, from the raw span. A bar 8.2501% wide
    # is 8.3; rounded to a hundredth first it is 8.25, which round-half-even
    # then takes DOWN to 8.2 -- the double-rounding half of the class
    # worst_base_day() closed, on the number the rulebook tells the model to
    # read beside `H`.
    boundary = extra_context(_frame(burst_low_pct=-0.7319))
    assert boundary["bar_range_pct"] == 8.3

    # The gap is published at the tenth of a percent `bar_range_pct` beside
    # it is, and not at `gain_pct`'s two decimals: an open 3.26% above the
    # previous close reads 3.3. Pinned because nothing did -- every earlier
    # test used a +3.0% open, where the two roundings are one number.
    assert extra_context(_frame(burst_gap_pct=3.26))["gap_pct"] == 3.3

    # And the same numbers reach the request, since src.scorer spreads the
    # context into it -- the archive gets them from src.ledger the same way.
    payload = _payload_for(_off_its_own_high(_frame(burst_gap_pct=3.0, burst_low_pct=-1.0)))
    assert all(payload[key] == ctx[key] for key in BURST_BAR_KEYS), payload


def test_the_expansion_is_measured_against_the_consolidation_the_checklist_names():
    """WINDOWS["tight_sessions"], `N`'s own window, and deliberately not a
    second one: a strategy number invented here would be invisible to
    rules_fingerprint() and unfalsifiable against `N`.

    The precondition is what makes this test able to fail: on this frame the
    seven shelf sessions are 2.0%/day and everything before them is 4.0%/day,
    so a denominator taken over `norm_sessions` instead would halve the
    answer. The two windows have to disagree, or the assertion below passes
    whichever one the code reads.
    """
    frame = _frame()
    widths = ((frame["High"] - frame["Low"]) / frame["Close"] * 100)
    shelf = widths.iloc[-(WINDOWS["tight_sessions"] + 1):-1]
    before = widths.iloc[-WINDOWS["norm_sessions"]:-WINDOWS["tight_sessions"] - 1]
    assert round(shelf.mean(), 1) == 2.0 and round(before.mean(), 1) == 4.0, (
        "the two windows agree on this frame, so this cannot tell them apart")

    ctx = extra_context(frame)
    assert ctx["range_expansion"] == round(ctx["bar_range_pct"] / 2.0, 2)
    assert ctx["range_expansion"] != round(ctx["bar_range_pct"] / 4.0, 2)
    # And published at two decimals, the precision `N` prints its own
    # tightness at, so the two ratios a reader sees are one kind of number.
    # 2.0%/day divides the burst bar exactly, so the precision is invisible
    # on the frame above; 2.1%/day is 3.6666... and shows it.
    assert extra_context(_frame(tight_range=0.021))["range_expansion"] == 3.67


@pytest.mark.parametrize("column", ["Open", "High", "Low"])
def test_a_bar_that_cannot_be_read_measures_null_and_never_zero(column):
    """The rule round 9 settled for the open basis (F1/L4), one layer over.

    Zero would be a fabricated measurement, and the most confident one
    available: 0.0% is "it opened exactly where it closed yesterday", which
    is a claim about the market.

    ALL THREE, on any of the three columns, and the Open case is why this
    test exists rather than the two that follow. A bar with no Open still
    has a perfectly readable width -- the precondition below executes that
    rather than describing it -- but `evaluate_2lynch()` has dropped that bar
    before choosing the burst, so `H` is describing the session BEFORE. The
    round that added these measured the width anyway, and the model was sent
    `bar_range_pct 9.4` beside "closed at 50% of day's range" for a bar that
    closed at 98% of its own, under a rulebook sentence telling it to read
    the two together.
    """
    frame = _frame()
    frame.iloc[-1, frame.columns.get_loc(column)] = float("nan")
    if column == "Open":
        assert _bar_width(frame.iloc[-1]) is not None, (
            "this bar's width cannot be read either, so a null below says "
            "nothing about the bar the checklist is reading")
    checklist = evaluate_2lynch(frame)
    clean = evaluate_2lynch(_frame())
    assert (checklist["checks"]["H_close_near_high"]["value"]
            != clean["checks"]["H_close_near_high"]["value"]), (
        "the checklist is reading the same bar it reads on a clean frame, so "
        "these three cannot describe a different one")

    ctx = extra_context(frame)
    for key in BURST_BAR_KEYS:
        assert ctx[key] is None, (
            f"{key} describes the burst bar while `H` describes the session "
            f"before it, because the bar has no {column}")


@pytest.mark.parametrize("column", ["Close", "Volume"])
def test_the_two_layers_step_back_onto_one_bar_together(column):
    """The other half of the rule above, and the reason it is a rule about
    the CHECKLIST's bar rather than about the Open.

    A burst bar with no Close (or no Volume) is dropped by everything --
    src.scanner.detect_setup(), extra_context()'s own cleaning and
    evaluate_2lynch() -- so all three layers call the SAME earlier bar the
    burst and the three measurements are measurements of the bar `H` grades.
    Null would be wrong here: nothing disagrees.
    """
    frame = _frame()
    frame.iloc[-1, frame.columns.get_loc(column)] = float("nan")
    ctx = extra_context(frame)
    for key in BURST_BAR_KEYS:
        assert ctx[key] is not None, key
    # And they are that earlier bar's own numbers, not the dropped bar's.
    assert ctx == extra_context(frame.iloc[:-1])


def test_an_open_outside_its_own_bar_is_not_a_gap():
    """src.ledger._open_within_its_bar() refuses an entry price outside the
    day's low and high, and `H` refuses a close above its own high, for one
    reason: a price outside the bar is one nobody paid. A gap measured from
    it would be the same fabrication with a different name.

    Reproduced on the bar's own numbers -- the open is put a hair above the
    high the frame built, everything else untouched -- so the width and the
    expansion still measure and only the gap goes null.
    """
    frame = _frame()
    high = float(frame["High"].iloc[-1])
    frame.iloc[-1, frame.columns.get_loc("Open")] = high * 1.001
    ctx = extra_context(frame)

    assert ctx["gap_pct"] is None
    assert ctx["bar_range_pct"] == extra_context(_frame())["bar_range_pct"]
    assert ctx["range_expansion"] == extra_context(_frame())["range_expansion"]
    # And the boundary is inclusive: an open exactly AT its own high is a
    # print, not a bad bar.
    frame.iloc[-1, frame.columns.get_loc("Open")] = high
    assert extra_context(frame)["gap_pct"] is not None


def test_an_inverted_bar_has_no_width_at_all():
    """A High below its own Low is not a bar, and a negative width is a
    fabricated measurement rather than a small one -- the same class as the
    close above its own high that `H` refuses. The gap goes with it: there is
    no envelope for the open to be inside.
    """
    frame = _frame()
    high = frame.columns.get_loc("High")
    frame.iloc[-1, high] = float(frame["Low"].iloc[-1]) * 0.99
    ctx = extra_context(frame)
    assert [ctx[key] for key in BURST_BAR_KEYS] == [None, None, None]


def test_a_base_with_no_width_has_no_norm_to_expand_against():
    """Every session before the burst is a zero-width bar, so the mean the
    expansion divides by is 0. The answer is null: an expansion against
    nothing is not infinite, it is unmeasured, and dividing anyway raises
    inside publish() -- after the scan and every Claude call.
    """
    ctx = extra_context(_frame(wide_range=0.0, tight_range=0.0))
    assert ctx["bar_range_pct"] > 0, "the burst bar itself still has a width"
    assert ctx["range_expansion"] is None


def test_a_bool_where_a_price_belongs_is_not_a_price():
    """The rule src.ledger._num() applies, for the reason it applies it: a
    True read as $1.00 is a fabricated measurement, and this one is not
    small -- a $40 bar's width over a $1 close is 43,000%.

    CLOSE and not Open, deliberately. A True in the Open column reads as
    $1.00, which is nowhere near a $40 bar, so the containment rule refuses
    it whatever this guard does: a test planted there would pass with the
    guard deleted, which is this project's third shape of shaped test. The
    column is made object-typed because a float column cannot hold a bool to
    begin with, which is also the only way one arrives.
    """
    frame = _frame()
    frame["Close"] = frame["Close"].astype(object)
    frame.iloc[-1, frame.columns.get_loc("Close")] = True
    ctx = extra_context(frame)
    assert ctx["bar_range_pct"] is None and ctx["range_expansion"] is None


def test_a_flat_bar_has_no_width_rather_than_no_measurement():
    """`H` refuses a bar with no high-low separation because it is being
    asked whether the close was strong and such a bar cannot say. This is
    being asked how WIDE the bar was, and 0.0% is that answer rather than a
    failure to reach one -- the same distinction as a measured 0 up days
    against a null one.
    """
    ctx = extra_context(_frame(burst_zero_range=True))
    assert ctx["bar_range_pct"] == 0.0
    assert ctx["range_expansion"] == 0.0
    # The gap is still measurable: the open equals the close equals the high
    # equals the low, which is inside its own (degenerate) bar.
    assert ctx["gap_pct"] is not None



def _printed_pre_burst_range(frame: pd.DataFrame) -> float:
    """The %/day `N` prints, parsed back out of the line the model reads."""
    line = evaluate_2lynch(frame)["checks"]["N_narrow_consolidation"]["value"]
    return float(line.split("range ")[1].split("%")[0])


#: Seven pre-burst sessions of DIFFERENT widths, oldest first. Every frame in
#: this file had a flat 2.0%/day shelf, on which the mean of the rounded
#: widths, the rounded mean of them and the width of any one of them are the
#: same number -- so no test could tell those three denominators apart, and
#: the ratio the pipeline published disagreed with the `N` line beside it on
#: 8 of the 9 rows it had written.
UNEVEN_SHELF = (0.0283, 0.0112, 0.0061, 0.0281, 0.0063, 0.0270, 0.0088)


def _shelf_widths(frame: pd.DataFrame) -> list[float]:
    """The pre-burst widths, as `N` measures them: raw, most recent last."""
    widths = (frame["High"] - frame["Low"]) / frame["Close"] * 100
    return [float(w) for w in widths.iloc[-(WINDOWS["tight_sessions"] + 1):-1]]


def test_the_expansion_is_the_ratio_the_N_line_lets_a_reader_recompute():
    """One number, printed once, in the request the model reads.

    `N` prints the pre-burst range as the mean of the raw widths, rounded
    once to the tenth. This divided by the mean of the widths each already
    ROUNDED -- a different number, and never shown anywhere -- so the request
    said "pre-burst range 1.0%/day" beside a 9.5% bar and called it 9.37x,
    where the reader recomputing it from the two numbers in front of him gets
    9.5x. 8 of the 9 rows the real pipeline had written into
    tests/fixtures/history/ disagreed that way, and the canonical fixture
    asserted the identity the pipeline did not hold.

    The preconditions are executed: the shelf is uneven (a flat one cannot
    tell the two arithmetics apart), the two arithmetics really do give
    different ratios on it, and so does every shorter window -- which is what
    holds the divisor to WINDOWS["tight_sessions"], `N`'s own window, rather
    than to any prefix of it.
    """
    frame = _frame(shelf_ranges=UNEVEN_SHELF)
    widths = _shelf_widths(frame)
    assert len(set(round(w, 1) for w in widths)) > 1, "the shelf is flat"

    ctx = extra_context(frame)
    printed = _printed_pre_burst_range(frame)
    assert ctx["range_expansion"] == round(ctx["bar_range_pct"] / printed, 2), (
        f"{ctx['bar_range_pct']}% over a {printed}%/day base is not "
        f"{ctx['range_expansion']}x -- the two numbers in one request do not "
        "reconcile")

    for mean_of_rounded in (sum(round(w, 1) for w in widths) / len(widths),
                            round(sum(round(w, 1) for w in widths) / len(widths), 1)):
        assert round(ctx["bar_range_pct"] / mean_of_rounded, 2) != ctx["range_expansion"], (
            "rounding each width first gives the same answer on this frame, "
            "so this test cannot tell the two denominators apart -- and it "
            "has to separate BOTH forms of it, the unrounded mean this "
            "divided by and the rounded one that looks like the fix")
    for shorter in (1, 3):
        norm = round(sum(widths[-shorter:]) / shorter, 1)
        assert round(ctx["bar_range_pct"] / norm, 2) != ctx["range_expansion"], (
            f"a divisor over the last {shorter} sessions gives the same "
            "answer, so the window is not pinned")


#: Seven lows, on the frame's own shelf bars (one High and one Close across
#: all seven), whose widths average to 2.3499999999999992 -- a mean sitting
#: an ULP either side of `round(x, 1)`'s boundary. Found by search over 4,847
#: candidate shelves, because this is the one shape that tells three ways of
#: averaging seven floats apart: pandas answers 2.4, math.fsum 2.3, and the
#: builtin sum() 2.4 on CI's 3.12 and 2.3 on this sandbox's 3.11.
FSUM_SHELF_LOWS = (43.17865131892043, 42.81060259359148, 42.95613495891439,
                   42.915183372965885, 42.82071494887865, 43.13299173820462,
                   43.26552106852392)


def test_the_base_is_averaged_by_the_one_thing_that_prints_it():
    """The denominator is `N`'s number, so it is averaged `N`'s way.

    math.fsum is what src.ledger.mean_returns() uses and the argument for it
    is real -- CPython 3.12 made the builtin sum() compensated, so one frame
    published 0.87 here and 0.88 on CI -- but it is an argument about a mean
    NOTHING ELSE COMPUTES. This one is computed twice: once here and once by
    `N`, with pandas, into a line the same request carries. On the shelf
    below the two disagree by an ULP, and the more accurate answer is the one
    that contradicts the printed number.

    The interpreter half of that finding is closed either way: no builtin
    sum() is left, so nothing here can answer 2.4 on 3.12 and 2.3 on 3.11.
    """
    frame = _frame()
    low = frame.columns.get_loc("Low")
    for k, value in enumerate(FSUM_SHELF_LOWS):
        frame.iloc[len(frame) - 1 - len(FSUM_SHELF_LOWS) + k, low] = value
    widths = _shelf_widths(frame)
    printed = _printed_pre_burst_range(frame)

    ctx = extra_context(frame)
    assert ctx["range_expansion"] == round(ctx["bar_range_pct"] / printed, 2)
    # And this frame really is the one that separates them: if it stops
    # being, the assertion above is satisfied by every mean and says nothing.
    fsum_norm = round(math.fsum(widths) / len(widths), 1)
    assert fsum_norm != printed, (
        "fsum and the printed mean agree on this shelf, so it can no longer "
        "tell them apart -- the search that found it is in CLAUDE.md")
    assert ctx["range_expansion"] != round(ctx["bar_range_pct"] / fsum_norm, 2)
    if sum(widths) != math.fsum(widths):     # true on 3.11, false on 3.12
        assert round(sum(widths) / len(widths), 1) != fsum_norm, (
            "the builtin sum and fsum agree here, so the interpreter half of "
            "this is not exercised")


def test_the_expansion_averages_the_bars_the_checklist_averages():
    """The window is `N`'s window, so it holds `N`'s bars.

    A bar with no Open has a perfectly readable width and is one
    `evaluate_2lynch()` drops before it measures anything -- so counting it
    here would put a bar in the divisor that is in no `N` line, and the two
    printed numbers would stop reconciling on exactly the frames a feed with
    a hole in it produces.
    """
    frame = _frame(shelf_ranges=UNEVEN_SHELF)
    hole = len(frame) - 3
    frame.iloc[hole, frame.columns.get_loc("Open")] = float("nan")
    assert _bar_width(frame.iloc[hole]) is not None, (
        "this bar's width cannot be read at all, so skipping it says nothing "
        "about the checklist's window")

    ctx = extra_context(frame)
    printed = _printed_pre_burst_range(frame)
    assert ctx["range_expansion"] == round(ctx["bar_range_pct"] / printed, 2)
    # And the hole really did move the answer: a window that counted it would
    # publish a different ratio, so this is not two readings of one number.
    counted = _shelf_widths(frame)
    assert round(ctx["bar_range_pct"] / round(sum(counted) / len(counted), 1), 2) \
        != ctx["range_expansion"], "counting the hole gives the same ratio"


def test_the_gap_is_measured_off_the_close_the_gain_was_measured_against():
    """One denominator for the two numbers in the payload.

    `detect_setup()` measures gain_pct after dropping every bar with no
    readable close or volume (src.scanner._measurable), and extra_context()
    hands burst_bar_shape() that same cleaning -- so a readable close under
    an unreadable volume is a session NEITHER number is measured against.
    Handed the frame as received instead, the request reads gain 8.0% beside
    gap 21.7%: two non-null numbers naming two different previous sessions,
    which is what the comment above the divide promises cannot happen.

    Three distinct closes sit in the three places a reading could take one
    from, asserted before anything else, so this cannot pass because two of
    them happen to be the same number -- which is why the shelf's own closes
    are moved: they are identical session to session, and a divisor one bar
    further back was indistinguishable.
    """
    from src.scanner import ScanConfig, detect_setup

    frame = _frame()
    close_col, volume_col = frame.columns.get_loc("Close"), frame.columns.get_loc("Volume")
    frame.iloc[-2, close_col] = 36.0
    frame.iloc[-2, volume_col] = float("nan")
    frame.iloc[-3, close_col] = 41.0
    cleaned = frame.dropna(subset=["Close", "Volume"])
    unreadable = float(frame["Close"].iloc[-2])
    measured = float(cleaned["Close"].iloc[-2])
    one_further = float(cleaned["Close"].iloc[-3])
    assert len({unreadable, measured, one_further}) == 3, (
        "two of the three candidate denominators are the same number")

    setup = detect_setup(frame, ScanConfig())
    assert setup, "this frame carries no burst, so there is no gain to agree with"
    assert setup["gain_pct"] == round(
        (float(cleaned["Close"].iloc[-1]) / measured - 1) * 100, 2), (
        "the scan is not measuring its gain against the close this test "
        "expects, so the agreement below would be an accident")

    open_ = float(frame["Open"].iloc[-1])
    ctx = extra_context(frame)
    assert ctx["gap_pct"] == round((open_ / measured - 1) * 100, 1)
    for other in (unreadable, one_further):
        assert ctx["gap_pct"] != round((open_ / other - 1) * 100, 1)


def test_a_base_bar_whose_width_cannot_be_read_is_skipped_and_never_raises():
    """A close of 0.0 is not a small price, it is no price -- and the
    division is why this is a guard rather than a preference: weakened to
    `close < 0`, one zero close anywhere in a name's history raises
    ZeroDivisionError out of extra_context(), which src.pipeline calls per
    candidate inside publish() -- after the scan and every Claude call.

    Reachable: src.scanner._session_bar_problem() reads the SESSION bar and
    _measurable() drops NaN rather than 0.0, so a zero close four sessions
    back reaches here with nothing in front of it.
    """
    frame = _frame(shelf_ranges=UNEVEN_SHELF)
    zero = len(frame) - 5
    frame.iloc[zero, frame.columns.get_loc("Close")] = 0.0

    # The seven readable widths, walked back from the bar before the burst
    # the way the code walks them -- so the window reaches an eighth session
    # back rather than counting the hole as a flat day.
    widths, i = [], len(frame) - 2
    while len(widths) < WINDOWS["tight_sessions"]:
        bar = frame.iloc[i]
        if _bar_width(bar) is not None:
            widths.append(_bar_width(bar))
        i -= 1
    assert _bar_width(frame.iloc[zero]) is None, "the planted bar is readable"

    ctx = extra_context(frame)
    norm = round(sum(widths) / len(widths), 1)
    assert ctx["range_expansion"] == round(ctx["bar_range_pct"] / norm, 2), (
        "the unreadable bar was counted rather than skipped")
    assert i < zero - 1, "the window never reached past the hole"

    # And in the burst position, where the guard is the difference between a
    # null width and the same raise. (The gap is untouched: it is measured
    # from the open and the previous close, and this bar has both.)
    burst_zero = _frame()
    burst_zero.iloc[-1, burst_zero.columns.get_loc("Close")] = 0.0
    shape = extra_context(burst_zero)
    assert shape["bar_range_pct"] is None and shape["range_expansion"] is None


def test_a_frame_of_one_bar_has_a_width_and_no_gap_rather_than_an_index_error():
    """The guard on `prev_close` is the only thing between a one-bar frame
    and an IndexError two lines further down, and nothing else in this suite
    hands one over. There is no session before it to have gapped from and no
    base to have expanded against; the width is still the width.

    The empty-frame return above it is deliberately NOT pinned here: it
    cannot be reached through extra_context(), which reads
    `df["Close"].iloc[-1]` first and raises on an empty frame, so a test of
    it would be a test of burst_bar_shape's own direct callers, of which
    there are none.
    """
    ctx = extra_context(_frame().iloc[-1:])
    assert ctx["gap_pct"] is None
    assert ctx["range_expansion"] is None
    assert isinstance(ctx["bar_range_pct"], float) and ctx["bar_range_pct"] > 0


#: Close is deliberately absent: _base() drops a bar with no Close too, so on
#: that one column all three rules coincide and the gap cannot tell any two
#: readings apart. The precondition inside the test says so if this list ever
#: grows it back.
@pytest.mark.parametrize("column", ["Open", "High", "Low", "Volume"])
def test_a_bar_missing_one_field_cannot_make_the_two_surfaces_disagree(column):
    """The verdict and the number must come off the same bars.

    They did not. evaluate_2lynch() drops every bar missing ANY of the five
    OHLCV fields, because the six checks read intraday ranges and volume;
    extra_context() drops only bars missing Close or Volume. Both then called
    these measurements with their own already-pruned frame, so ONE bar with no
    High made the veto count two up days and allow the burst while the metrics
    block told the scoring model there had been three -- the run reporting that
    it had refused something it had scored. Reproduced on every one of the five
    columns before the fix; zero disagreements across 140 frames after it.

    Both callers hand these measurements the frame as received now, and _base()
    is the one rule that decides which bars they count.
    """
    frame = _frame(up_run_days=2)
    # INSIDE the run, not beside it. The first version of this test put the gap
    # on the flat shelf day that ends the run, where dropping the bar changes
    # nothing -- so it passed with the defect deliberately restored, which is
    # the shaped-test pattern this file's own docstring warns about. The
    # precondition below is what makes the position load-bearing instead of
    # chosen by eye: it fails if the gap stops discriminating.
    frame.iloc[-3, frame.columns.get_loc(column)] = float("nan")
    pruned = frame.dropna(subset=["Open", "High", "Low", "Close", "Volume"])
    assert consecutive_up_days(pruned) != consecutive_up_days(frame), (
        "this gap does not change the count off a pruned frame, so the test "
        "cannot tell the two readings apart")

    result = evaluate_2lynch(frame)
    context = extra_context(frame)

    reported = int(result["vetoes"]["up_days"]["value"].split()[0])
    assert reported == context["consecutive_up_days"], result["vetoes"]["up_days"]["value"]
    assert f"{context['worst_base_day_pct']:+.1f}%" in (
        result["context_checks"]["base_breakdown"]["value"])
    # And the answer is the one the intact frame gives: a bar the feed served
    # with a gap in it still happened, and dropping it would move a real run.
    assert reported == consecutive_up_days(_frame(up_run_days=2))


def test_every_rule_evaluate_2lynch_vetoes_on_is_named_in_VETO_RULES():
    """The two must agree, and nothing else makes them.

    src.pipeline builds its reason vocabulary from VETO_RULES. It used to keep
    a hand-written tuple of the same names, and an audit added a realistic
    second veto to evaluate_2lynch alone: the whole suite stayed green and the
    evening run died on KeyError after the scan, inside the archive step, on a
    burst that had been correctly refused. The lookup is gone -- veto_reason()
    computes the word -- so a forgotten rule can no longer kill a run. This is
    the other half: it catches the omission here instead, where it is free.
    """
    produced = set(evaluate_2lynch(_reference())["vetoes"])

    assert produced == set(VETO_RULES), (
        f"evaluate_2lynch vetoes on {sorted(produced)} and VETO_RULES names "
        f"{sorted(VETO_RULES)}; src.pipeline's reason words come from the "
        "second, so anything only in the first publishes no word and anything "
        "only in the second names a rule that never runs")
    assert all(veto_reason(name).startswith("veto_") for name in VETO_RULES)


def test_a_result_from_before_the_rule_existed_reports_no_vetoes():
    """failed_vetoes() is read by the pipeline's gate against whatever
    evaluate_2lynch returned, and a hand-built double in a test or an older
    archived result carries no `vetoes` key at all. The answer for those is
    the answer the code gave before the rule existed: nothing was refused."""
    assert failed_vetoes({"passes": 6}) == []
    assert failed_vetoes({"vetoes": None}) == []
    assert failed_vetoes({"vetoes": {}}) == []
    # And an entry that does not say whether it passed refuses nothing. A veto
    # is a refusal, and a structure that states no refusal has not made one --
    # inventing it from silence would drop a candidate and be unable to say
    # why. Nothing this project writes produces that shape; the pipeline's
    # gate reads whatever evaluate_2lynch returned, and a double in a test can.
    assert failed_vetoes({"vetoes": {"up_days": {}}}) == []
    assert failed_vetoes({"vetoes": {"up_days": {"value": "measured, no verdict"}}}) == []
    # And one level in, which is where this stopped. The container was checked
    # and its entries were not, so a `vetoes` block of the wrong shape raised
    # AttributeError inside the pipeline's gate -- the sixth time this project
    # has shipped a check that stops a level short of what a caller indexes.
    for entry in (None, "x", 1, [1], True):
        assert failed_vetoes({"vetoes": {"up_days": entry}}) == [], entry
    # A non-string name is refused too: veto_reason() builds the published word
    # out of it, and `veto_7` is a reason no surface has prose for.
    assert failed_vetoes({"vetoes": {7: {"pass": False}}}) == []
    assert failed_vetoes({"vetoes": {None: {"pass": False}}}) == []


# ---- the numbers themselves ----------------------------------------------


def test_every_threshold_still_holds_the_value_it_was_tuned_to():
    """The canaries above all read their boundary off the constant, so they
    keep passing when a constant MOVES -- which is the property that makes
    them survive a retune, and the reason none of them notices one.

    This is the other half. knowledge/strategy.md and README describe these
    numbers; changing one is a strategy change and has to be deliberate
    enough to edit a test that says so.
    """
    assert (MAX_PRIOR_BURSTS, MIN_LINEAR_R2, MIN_LINEAR_SLOPE) == (1, 0.55, 0.0)
    assert (MAX_RUN_UP_1MO, MAX_EXT_VS_SMA20) == (25.0, 15.0)
    assert MAX_TIGHTNESS == 1.0
    assert (MAX_D1_MOVE, MAX_D1_VOL_RATIO, MAX_D1_RANGE_RATIO) == (2.0, 1.2, 1.0)
    assert MIN_CLOSE_POS == 0.70
    # Bonde's two rules. Neither is a check, and both are still strategy: the
    # first refuses a burst outright and the second is handed to the model.
    assert MAX_CONSECUTIVE_UP_DAYS == 2
    assert (BREAKDOWN_PCT, BREAKDOWN_LOOKBACK) == (-4.0, 20)


def test_the_rules_fingerprint_covers_every_number_this_module_names():
    """THE TRAP this fingerprint exists to avoid, made checkable.

    A fingerprint that misses a number reports "same rules" across a change
    that altered them -- worse than no fingerprint, because the record then
    states agreement it never checked. It is derived rather than listed for
    that reason, and this asserts the derivation actually reaches all three
    sources: every upper-case numeric constant src.lynch names, every window
    it groups, and the vetoes in force. A threshold added later is covered
    the moment it is named; the one thing neither can catch is a number left
    as a bare literal, which is why the windows were named at all.
    """
    import src.lynch as lynch_mod
    from src.pipeline import rules_fingerprint

    fingerprint = rules_fingerprint()
    scalars = {n for n in dir(lynch_mod)
               if n.isupper() and isinstance(getattr(lynch_mod, n), (int, float))
               and not isinstance(getattr(lynch_mod, n), bool)}
    assert scalars, "src.lynch exposes no threshold constants"
    missing = sorted(n for n in scalars if f"check.{n.lower()}" not in fingerprint)
    assert not missing, f"the fingerprint does not carry {missing}"
    assert all(fingerprint[f"check.{n.lower()}"] == getattr(lynch_mod, n) for n in scalars), (
        "a value in the fingerprint is not the value the module holds")

    missing_windows = sorted(k for k in lynch_mod.WINDOWS if f"window.{k}" not in fingerprint)
    assert not missing_windows, f"the fingerprint does not carry the windows {missing_windows}"
    assert fingerprint["check.vetoes"] == sorted(lynch_mod.VETO_RULES)


def test_the_record_can_see_a_change_to_the_calm_days_volume_norm():
    """The property the whole naming exercise is for, asserted directly.

    A window left as a literal lets docs/ledger.json say "same rules" across a
    change that altered them, which is worse than no fingerprint at all --
    rules_fingerprint()'s own docstring says so. This was reproduced before
    the window was named: C's 50 changed to 30 left the fingerprint
    BYTE-IDENTICAL. It moves the dict at run time rather than editing a file,
    so the assertion is about the fingerprint's reach and not about a value.
    """
    import src.lynch as lynch_mod
    from src.pipeline import rules_fingerprint

    before = rules_fingerprint()
    original = lynch_mod.WINDOWS["volume_norm_sessions"]
    try:
        lynch_mod.WINDOWS["volume_norm_sessions"] = original + 10
        assert rules_fingerprint() != before, (
            "the sessions C's volume norm spans are invisible to the record")
    finally:
        lynch_mod.WINDOWS["volume_norm_sessions"] = original
    assert rules_fingerprint() == before, "the fingerprint did not come back"


def test_the_lines_the_model_reads_name_the_window_the_code_applied():
    """Two of the six windows round 8 named were spelled a second time, as
    DIGITS inside the strings the scoring model reads.

    `L` printed "over prior 30 days" and `Y` "vs 20SMA" as literal text, so
    with WINDOWS["linear_fit_sessions"] at 10 and ["sma_sessions"] at 5 the
    lines still said 30 and 20 -- on the request the model scores from, in
    the email's checklist lines and in the ledger's archived `lynch_detail`.
    tools/make_fixture.py had already built both lines FROM WINDOWS (round 8
    swept the generator and not the source), so the generator and the module
    would have printed two different sentences under a patched window while
    tools/check_fixture_fresh.py called both current.

    The AST guard below cannot see this: a number written in words is not an
    ast.Constant numeric. This is the string half, and it is asserted by
    rendering the lines under a patched WINDOWS rather than by reading them.
    """
    import src.lynch as lynch_mod

    frame = make_ohlcv("burst", seed=7, up_run=1)
    real = evaluate_2lynch(frame)["checks"]
    assert f"over prior {WINDOWS['linear_fit_sessions']} days" in real["L_linear_prior_move"]["value"]
    assert f"vs {WINDOWS['sma_sessions']}SMA" in real["Y_young_trend"]["value"]

    patched = dict(lynch_mod.WINDOWS, linear_fit_sessions=10, sma_sessions=5)
    original = lynch_mod.WINDOWS
    try:
        lynch_mod.WINDOWS = patched
        moved = evaluate_2lynch(frame)["checks"]
    finally:
        lynch_mod.WINDOWS = original

    assert "over prior 10 days" in moved["L_linear_prior_move"]["value"], (
        "L tells the model a window it did not fit over")
    assert "vs 5SMA" in moved["Y_young_trend"]["value"], (
        "Y tells the model an average it did not measure against")


def test_the_context_measurements_read_the_windows_this_module_names():
    """The eighth, ninth, tenth and eleventh bare literals, one function over.

    Round 8 named six windows inside `evaluate_2lynch` and round 11 the
    seventh; `extra_context()` went on spelling 252, 126, 63 and 60 -- the
    52-week high/low lookback, the six- and three-month performance windows,
    and the history a 52-week reading needs before it is attempted.
    Reproduced before they were named: `iloc[-63]` and `len(df) > 63` changed
    to 45 left rules_fingerprint() BYTE-IDENTICAL and the whole suite green,
    while `perf_3mo_pct` -- which knowledge/strategy.md names as one of the
    two relative-strength measures the model has -- moved on the same frame,
    under a key still called `3mo`, and was archived in every row's `context`.
    """
    import src.lynch as lynch_mod

    frame = make_ohlcv("burst", seed=3, up_run=1)
    assert len(frame) > 130, "precondition: a frame long enough to hold every window"

    patched = dict(lynch_mod.WINDOWS, perf_3mo_sessions=45, perf_6mo_sessions=90,
                   high_low_sessions=30)
    original = lynch_mod.WINDOWS
    try:
        lynch_mod.WINDOWS = patched
        ctx = extra_context(frame)
        close = float(frame["Close"].iloc[-1])
        assert ctx["perf_3mo_pct"] == round((close / float(frame["Close"].iloc[-45]) - 1) * 100, 1)
        assert ctx["perf_6mo_pct"] == round((close / float(frame["Close"].iloc[-90]) - 1) * 100, 1)
        assert ctx["pct_off_52w_high"] == round(
            (close / float(frame["High"].iloc[-30:].max()) - 1) * 100, 1)
        assert ctx["pct_above_52w_low"] == round(
            (close / float(frame["Low"].iloc[-30:].min()) - 1) * 100, 1)

        # And the sentinel beside each window, from both sides: a frame
        # exactly the window long has no earlier close to measure against.
        # The two spellings of 63 -- the index and the length guard -- were
        # one number written twice, so moving the window alone left its own
        # guard stale.
        assert extra_context(frame.iloc[-45:])["perf_3mo_pct"] is None
        assert extra_context(frame.iloc[-46:])["perf_3mo_pct"] is not None
    finally:
        lynch_mod.WINDOWS = original


def test_every_threshold_this_module_names_is_one_its_own_code_reads():
    """A threshold inlined at its own value is invisible to the AST guard.

    `found - set(allowed)` compares by numeric VALUE, and 2.0 == 2 and
    1.0 == 1 in Python -- so `d1_move < 2.0` for MAX_D1_MOVE and
    `d1_range_ratio <= 1.0` for MAX_D1_RANGE_RATIO both survived that guard
    (verified: each left tests/test_lynch.py, tests/test_scanner.py and
    tests/test_docs_are_true.py green). The state that produces is the one
    the fingerprint exists to prevent: editing the constant then moves
    rules_fingerprint() and not the rule, so the record states a threshold
    the code does not apply.

    Keying the allowed set on the literal's type does not close it --
    `0.0 <= close_pos <= 1.0` legitimately spells 1.0 -- so this asserts the
    other direction, which does not depend on the literal's value at all:
    every threshold this module NAMES is read by its own code.
    """
    import ast
    import inspect

    import src.lynch as lynch_mod

    tree = ast.parse(inspect.getsource(lynch_mod))
    read = {n.id for f in ast.walk(tree) if isinstance(f, ast.FunctionDef)
            for n in ast.walk(f) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    named = {n for n in dir(lynch_mod)
             if n.isupper() and isinstance(getattr(lynch_mod, n), (int, float))
             and not isinstance(getattr(lynch_mod, n), bool)}
    assert named, "src.lynch exposes no threshold constants"
    unread = sorted(named - read)
    assert not unread, (
        f"{unread} is named as a threshold and read by no code in this module. "
        "A threshold the checklist spells out as a literal instead moves the "
        "rules fingerprint without moving the rule.")


def test_every_window_this_module_names_is_one_it_actually_measures_over():
    """The inverse: a window in the dict that no check reads is a number the
    fingerprint would report as part of the strategy while nothing applied
    it.

    Read off the AST, not the source text. Grepping the file satisfied this
    with a MENTION: a decoy `"decoy_sessions": 99` under a comment reading
    `nothing slices WINDOWS["decoy_sessions"]` passed the whole file, so a
    number the record publishes as part of the strategy and nothing applies
    was one prose sentence away from being green. (One real key,
    `tight_sessions`, is discussed in a docstring as well as sliced, which is
    what made that hole reachable without inventing anything.) Subscripts of
    the WINDOWS name are what "measures over" means, and that is what this
    counts.
    """
    import ast
    import inspect

    import src.lynch as lynch_mod

    tree = ast.parse(inspect.getsource(lynch_mod))
    read = {node.slice.value for node in ast.walk(tree)
            if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
            and node.value.id == "WINDOWS" and isinstance(node.slice, ast.Constant)}
    unused = sorted(set(lynch_mod.WINDOWS) - read)
    assert not unused, f"{unused} is named as a window and never measured over"


def test_no_threshold_constant_is_left_without_a_canary():
    """A structural guard, not a style check.

    Step 7 added MIN_LINEAR_SLOPE and MAX_D1_RANGE_RATIO with tests; the
    seven constants beside them had none, and nothing said so. A threshold
    added later must not be able to arrive unguarded in the same silence.
    """
    import src.lynch as lynch_mod

    constants = [n for n in dir(lynch_mod)
                 if n.isupper() and isinstance(getattr(lynch_mod, n), (int, float))]
    assert constants, "src.lynch exposes no threshold constants"
    source = pathlib.Path(__file__).read_text()
    # Three mentions is the floor for a guarded threshold: the import, the
    # value pin above, and at least one frame that crosses it. A constant with
    # only the first two has a pin and no canary, which is the state every
    # threshold on this list was in before this step.
    unguarded = [n for n in constants if source.count(n) < 3]
    assert not unguarded, (
        f"{unguarded} is imported and pinned but never crossed -- a pin is not a "
        "canary. Add a frame that puts it over its line and asserts, through "
        "_only_failure_is(), that exactly one check changed verdict."
    )



def test_a_month_that_cannot_be_measured_is_not_reported_as_a_flat_one():
    """Fewer than 21 closes survive the cleaning, so there is no month to
    measure over -- and the Y line used to print "+0.0% past month" to the
    scoring model as if it had been measured, on a frame whose run-up over the
    sessions it DID have was well into double digits. A number that was not
    measured is not zero; the line says it could not measure, and the half
    that was measured decides alone."""
    frame = make_ohlcv("burst", seed=7).iloc[-20:]      # one short of a month
    real_run_up = (frame["Close"].iloc[-1] / frame["Close"].iloc[0] - 1) * 100
    assert real_run_up > 5, "precondition: the sessions it has are not flat"

    check = evaluate_2lynch(frame)["checks"]["Y_young_trend"]

    assert "+0.0% past month" not in check["value"]
    assert "no 20-session history" in check["value"]
    assert "vs 20SMA" in check["value"], "the half that was measured is still there"


def test_a_close_outside_its_own_range_fails_h_instead_of_passing_at_145_percent():
    """The rng <= 0 branch caught an inverted bar; nothing caught a close the
    range does not contain, which printed "closed at 145% of day's range"
    and PASSED. Same class of bad bar, same verdict now."""
    frame = make_ohlcv("burst", seed=7).copy()
    frame.iloc[-1, frame.columns.get_loc("Close")] = frame["High"].iloc[-1] * 1.05

    check = evaluate_2lynch(frame)["checks"]["H_close_near_high"]

    assert check["pass"] is False
    assert "outside its own range" in check["value"]
    assert "145%" in check["value"] or "%" in check["value"], "and it still says what it saw"
