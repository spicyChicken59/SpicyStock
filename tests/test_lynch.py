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

import pathlib
import re

import numpy as np
import pandas as pd
import pytest

from src.lynch import (
    MAX_D1_MOVE,
    MAX_D1_RANGE_RATIO,
    MAX_D1_VOL_RATIO,
    MAX_EXT_VS_SMA20,
    MAX_PRIOR_BURSTS,
    MAX_RUN_UP_1MO,
    MAX_TIGHTNESS,
    MIN_CLOSE_POS,
    MIN_LINEAR_R2,
    MIN_LINEAR_SLOPE,
    evaluate_2lynch,
    extra_context,
)
from tests.synthetic import KINDS, frame_digest

CHECK_LETTERS = ["2", "C", "H", "L", "N", "Y"]


@pytest.fixture
def lynch(ohlcv):
    return evaluate_2lynch(ohlcv("burst"))


def test_result_has_the_documented_keys(lynch):
    assert set(lynch) == {"checks", "passes", "total", "summary", "detail_lines"}


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
    d1_range: float | None = None,
    burst_zero_range: bool = False,
    burst_close_pos: float = 0.98,
    d1_move_pct: float = 0.0,
    d1_volume_mult: float = 1.0,
    wave_pct: float = 0.0,
    wave_period: float = 14.0,
    prior_burst_pct: float = 4.2,
    prior_burst_offsets: tuple[int, ...] = (),
    old_volume_mult: float = 1.0,
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
      burst_close_pos      where in its own range the burst day closes (H).
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
    for offset in prior_burst_offsets:
        close[burst_i - offset] *= 1.0 + prior_burst_pct / 100.0
    if d1_move_pct:
        close[burst_i - 1] *= 1.0 + d1_move_pct / 100.0
    close[burst_i] = close[burst_i - 1] * (1.0 + burst_pct / 100.0)

    span = np.full(days, wide_range)
    span[burst_i - shelf : burst_i] = tight_range
    if d1_range is not None:
        span[burst_i - 1] = d1_range

    high = close * (1.0 + span / 2.0)
    low = close * (1.0 - span / 2.0)
    open_ = close.copy()

    prev = close[burst_i - 1]
    if burst_zero_range:
        high[burst_i] = low[burst_i] = open_[burst_i] = close[burst_i]
    else:
        low[burst_i] = prev * 0.999
        high[burst_i] = low[burst_i] + (close[burst_i] - low[burst_i]) / burst_close_pos
        open_[burst_i] = prev * 1.005

    volume = np.full(days, 3_000_000.0)
    # Everything older than the 50 sessions C averages over. Flat at 1.0x, so
    # this is invisible unless a test asks which sessions that window holds.
    volume[: burst_i - 51] *= old_volume_mult
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
    """The 4% in `rets >= 4.0` is a bare literal inside evaluate_2lynch, not
    one of the named constants -- the only copy of the scanner's min_gain_pct
    that no other layer can see. Two 3.5% days are the same shape of frame as
    the rejection above and must still be a first burst."""
    result = evaluate_2lynch(_frame(prior_burst_pct=3.5, prior_burst_offsets=(3, 5)))
    assert result["passes"] == 6, "\n".join(result["detail_lines"])
    assert _reported(result["checks"]["2_first_or_second_burst"]["value"],
                     r"^(\d+) prior") == 0


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
    """Which sessions `pre["Volume"].iloc[-51:-1]` holds, pinned from both ends.

    src.scanner's trailing_volume_mean() is 50 sessions excluding the day it
    measures, and tests/test_scanner.py asserts the two windows agree -- but
    it asserts that against arithmetic it writes out itself, so this half of
    the claim was never checked. Volume older than the window is 10x here, so
    a longer window drags the ratio down; the measured day is 20x, so
    including it in its own denominator drags the ratio down too.

    Deliberately not a calm day: this pins the measurement, not the verdict.
    """
    result = evaluate_2lynch(_frame(old_volume_mult=10.0, d1_volume_mult=20.0))
    ratio = _reported(result["checks"]["C_calm_preburst_day"]["value"], r"([\d.]+)x volume")
    assert ratio == pytest.approx(20.0, abs=0.01)


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
