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

import re

import numpy as np
import pandas as pd
import pytest

from src.lynch import evaluate_2lynch, extra_context
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
    burst_pct: float = 8.0,
    wide_range: float = 0.040,
    tight_range: float = 0.020,
    d1_range: float | None = None,
    burst_zero_range: bool = False,
    days: int = 200,
) -> pd.DataFrame:
    """One candidate's daily history, built from the parameters alone.

    A long flat stretch, then `trend_days` sessions travelling `trend_pct` in
    a straight line on log closes, then a quiet shelf out to the burst day,
    then a `burst_pct` up-day closing near its high on 8x volume. Ranges are
    `wide_range` per day except across the shelf, so N sees a real
    consolidation. Volume is flat, so C's volume ratio is exactly 1.00x.
    """
    burst_i = days - 1
    trend_start = burst_i - 30
    shelf = 30 - trend_days

    close = np.full(days, 40.0)
    step = (1.0 + trend_pct / 100.0) ** (1.0 / (trend_days - 1))
    for i in range(trend_start + 1, trend_start + trend_days):
        close[i] = close[i - 1] * step
    close[trend_start + trend_days : burst_i] = close[trend_start + trend_days - 1]
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
        high[burst_i] = low[burst_i] + (close[burst_i] - low[burst_i]) / 0.98
        open_[burst_i] = prev * 1.005

    volume = np.full(days, 3_000_000.0)
    volume[burst_i] = 24_000_000.0
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
