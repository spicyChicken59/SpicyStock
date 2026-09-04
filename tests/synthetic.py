"""Deterministic synthetic OHLCV frames for the offline test suite.

Every frame is produced from an explicit seed, and the seed a test gets is
derived from that test's node id (see ``seed_for``). Nothing here reads or
advances a module-level RNG, so a frame depends only on *which* test asked
for it -- never on how many tests ran first.

The shapes are deliberately extreme rather than realistic. A ``burst`` frame
clears every plausible burst threshold (percentage gain, share volume,
volume ratio, dollar volume, price floor) by a wide margin, and a ``flat``
frame fails all of them by a wide margin, so these fixtures survive the
threshold changes scheduled for steps 4 and 7.
"""

from __future__ import annotations

import hashlib
import zlib

import numpy as np
import pandas as pd

KINDS = ("flat", "base", "choppy", "burst")

# Column order the scanner, lynch and scorer layers all expect.
COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


def seed_for(nodeid: str) -> int:
    """Stable per-test seed derived from a pytest node id.

    crc32, not hash(): the builtin string hash is salted per interpreter run
    (PYTHONHASHSEED), which would make fixtures differ between runs.
    """
    return zlib.crc32(nodeid.encode("utf-8")) & 0x7FFF_FFFF


def frame_digest(df: pd.DataFrame) -> str:
    """Content hash of a frame, for proving two frames are identical."""
    return hashlib.sha256(
        df.to_csv(float_format="%.10f").encode("utf-8")
    ).hexdigest()


def _returns(rng: np.random.Generator, n: int, sigma: float, cap: float) -> np.ndarray:
    """Daily log-ish returns, hard-clipped so a kind can never drift into
    another kind's territory (a 'flat' series can never accidentally print a
    burst day)."""
    return np.clip(rng.normal(0.0, sigma, n), -cap, cap)


def make_ohlcv(
    kind: str = "base",
    *,
    seed,
    days: int = 200,
    end: str = "2026-07-01",
    start_price: float = 25.0,
    base_volume: float = 3_000_000.0,
    up_run: int = 1,
) -> pd.DataFrame:
    """Build one synthetic daily OHLCV frame.

    kind:
      flat   -- sideways, moves capped at +/-0.5%/day, near-constant volume.
                No burst detector with any sane threshold should fire on it.
      base   -- ordinary random walk, moves capped at +/-2.5%/day, no burst.
      choppy -- high-volatility walk, moves capped at +/-3.1%/day, no burst.
      burst  -- a `base` walk whose final bar is a +12% day on 8x the recent
                average volume (>=25M shares, >$40 close after the step-up),
                closing in the top 3% of its range.

    `up_run` is how many sessions in a row close up ENDING THE DAY BEFORE the
    burst, and it applies to `burst` frames only. It is a parameter and not
    whatever the walk happened to do, because src.lynch vetoes a burst that
    follows three or more up days: measured over 200 seeds, the walk produced
    three or more on 8.5% of them, so without this every end-to-end test in
    the suite held an undeclared one-in-twelve chance of scanning a universe
    whose only candidate was refused -- five of them really did, and they
    failed by finding zero candidates, which reads as a broken scan and not as
    a rule doing its job. Pass `up_run=3` to build the vetoed case on purpose.
    The default is 1 rather than 0 so that a consumer reading the count back
    cannot pass on a hard-coded zero.

    A TRAP IN `burst`, WORTH KNOWING BEFORE SWEEPING VARIANTS. The burst bar is
    written OVER the walk rather than drawn from it, and the `lift` below puts
    the day before it on exactly $40.00. Every burst frame therefore closes at
    exactly $44.80 whatever its seed, and most of them do it on exactly
    25,000,000 shares -- the variants differ in the history behind the burst,
    almost never in the burst itself.

    That is deliberate (the bar has to clear every gate by a wide margin) and
    it is fine for anything reading the history. But a test that sweeps
    variants to vary the LAST bar is sweeping one arithmetic many times, and
    such a test has already reported safety it did not have: the two roundings
    of close x volume that step 4's percentile gate depends on were compared
    over forty variants of $44.80 x 25,000,000, where the two roundings cannot
    disagree, and re-introducing the bug left it green. Scale the frame
    yourself when the burst bar's own numbers are the thing under test.
    """
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r}; expected one of {KINDS}")

    rng = np.random.default_rng(seed)
    index = pd.bdate_range(end=end, periods=days, name="timestamp")

    if kind == "flat":
        rets = _returns(rng, days, sigma=0.002, cap=0.005)
        vol_noise = 1.0 + _returns(rng, days, sigma=0.01, cap=0.02)
    elif kind == "choppy":
        rets = _returns(rng, days, sigma=0.020, cap=0.030)
        vol_noise = np.exp(_returns(rng, days, sigma=0.35, cap=0.9))
    else:  # base, and the pre-burst body of a burst frame
        rets = _returns(rng, days, sigma=0.012, cap=0.025)
        vol_noise = np.exp(_returns(rng, days, sigma=0.20, cap=0.6))

    close = start_price * np.exp(np.cumsum(rets))
    volume = base_volume * vol_noise

    if kind != "burst" and up_run != 1:
        # Silently ignored for every other kind before this, including values
        # no frame could hold: a test writing make_ohlcv("base", up_run=3) got
        # whatever the walk did and nothing said so, which is a way to build
        # exactly the shaped test this project's own rule forbids.
        raise ValueError(f"up_run applies to burst frames only, not {kind!r}")
    if kind == "burst":
        # The run of up days into the burst, made exact. Written before the
        # lift and the burst bar because both are computed from close[-2],
        # which this moves. `anchor` is forced DOWN so the run stops there:
        # setting only the run itself would leave its length at the mercy of
        # the walk again, one day further back.
        if up_run < 0 or up_run > days - 3:
            raise ValueError(f"up_run must be between 0 and {days - 3}")
        anchor = days - 2 - up_run
        close[anchor] = min(close[anchor], float(close[anchor - 1]) * 0.997)
        for i in range(1, up_run + 1):
            # 0.4%/day: quiet enough that `C` still calls the prior day calm,
            # which is the tired-drift case the up-days rule is about.
            close[anchor + i] = close[anchor + i - 1] * 1.004

        # Put the final bar far beyond every gate: a 12% gain on 8x the
        # trailing 50-day average volume, at least 25M shares, above $40.
        lift = max(1.0, 40.0 / float(close[-2]))
        close[:-1] *= lift
        close[-1] = close[-2] * 1.12
        volume[-1] = max(8.0 * float(volume[-51:-1].mean()), 25_000_000.0)

    # Intraday envelope, built so Low <= Open, Close <= High always holds.
    open_ = close * (1.0 + _returns(rng, days, sigma=0.004, cap=0.01))
    open_[0] = close[0]
    wick = np.abs(rng.normal(0.006, 0.002, days))
    upper = np.maximum(open_, close)
    lower = np.minimum(open_, close)
    high = upper * (1.0 + wick)
    low = lower * (1.0 - wick)

    if kind == "burst":
        # Burst day closes in the top 3% of its range.
        low[-1] = close[-2] * 0.999
        high[-1] = close[-1] * 1.003
        open_[-1] = close[-2] * 1.01

    frame = pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        },
        index=index,
    )
    return frame[COLUMNS]
