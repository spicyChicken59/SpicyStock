"""The fixture factory itself: deterministic, per-test, order-independent.

If these fail, no other assertion in the suite means anything -- every other
test is reading data this module produced.
"""

from __future__ import annotations

import numpy as np
import pytest

from tests.synthetic import KINDS, frame_digest, make_ohlcv, seed_for


def test_seed_depends_only_on_the_node_id():
    assert seed_for("tests/a.py::test_one") == seed_for("tests/a.py::test_one")
    assert seed_for("tests/a.py::test_one") != seed_for("tests/a.py::test_two")


def test_seed_is_stable_across_interpreter_runs():
    # A literal, not a re-derivation: this catches anyone swapping crc32 for
    # the builtin hash(), which is salted per process by PYTHONHASHSEED and
    # would silently make every fixture differ run to run.
    assert seed_for("tests/example.py::test_case") == 89608592


def test_frames_ignore_global_rng_state(ohlcv):
    """The order-independence proof, done inside a single test.

    Whatever a previously-run test did to numpy's global RNG -- seeding it,
    drawing from it -- cannot reach this frame.
    """
    np.random.seed(0)
    first = ohlcv("base")

    np.random.seed(12345)
    np.random.random(10_000)
    second = ohlcv("base")

    assert frame_digest(first) == frame_digest(second)


def test_variants_differ_but_each_is_reproducible(ohlcv):
    a1, a2 = ohlcv("base"), ohlcv("base")
    b1, b2 = ohlcv("base", variant=1), ohlcv("base", variant=1)
    assert frame_digest(a1) == frame_digest(a2)
    assert frame_digest(b1) == frame_digest(b2)
    assert frame_digest(a1) != frame_digest(b1)


def test_two_tests_get_different_data(ohlcv, seed):
    # This test's seed is its own; the sibling above cannot have produced it.
    assert seed == seed_for("tests/test_synthetic.py::test_two_tests_get_different_data")
    assert frame_digest(ohlcv("base")) != frame_digest(
        make_ohlcv("base", seed=[seed_for("tests/test_synthetic.py::test_frames_ignore_global_rng_state"), 0])
    )


@pytest.mark.parametrize("kind", KINDS)
def test_every_kind_is_a_well_formed_ohlcv_frame(kind, ohlcv):
    df = ohlcv(kind)
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert len(df) == 200
    assert df.index.is_monotonic_increasing
    assert not df.isna().any().any()
    assert (df["High"] >= df[["Open", "Close"]].max(axis=1)).all()
    assert (df["Low"] <= df[["Open", "Close"]].min(axis=1)).all()
    assert (df["Close"] > 0).all()
    assert (df["Volume"] > 0).all()


def test_flat_and_burst_sit_on_opposite_sides_of_any_sane_threshold(ohlcv):
    """These two frames are what makes the suite threshold-agnostic.

    Steps 4 and 7 will move the burst thresholds. They stay on the same side
    of both frames as long as this test holds.
    """
    flat = ohlcv("flat")
    assert flat["Close"].pct_change().abs().max() * 100 < 1.0

    burst = ohlcv("burst")
    today, yday = burst.iloc[-1], burst.iloc[-2]
    gain_pct = (today["Close"] / yday["Close"] - 1) * 100
    assert gain_pct > 10.0
    assert today["Volume"] >= 25_000_000
    assert today["Volume"] > 5 * burst["Volume"].iloc[-51:-1].mean()
    assert today["Close"] > 40.0
    assert today["Close"] * today["Volume"] > 1e9
