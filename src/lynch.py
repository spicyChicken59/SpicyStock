"""
Layer 2 — The 2LYNCH quality checklist (Stockbee), computed from price data.

Each test answers one question about the burst candidate:

  2  — First/second burst? The trend should be young: this should be roughly
       the first or second 4%+ burst in the recent leg, not the fifth.
  L  — Linear prior move: the advance before consolidation was orderly and
       UP, not a choppy whipsaw and not an orderly collapse. A linear fit on
       log closes has to be both tight (R²) and non-falling (slope): an
       R² test on its own scores a smooth 45% slide as a perfect setup,
       which is the dead-cat bounce knowledge/strategy.md tells us to skip.
  Y  — Young trend: price isn't wildly extended above its own base
       (distance from the 20-day base and % run-up over the past month),
       measured THROUGH the burst day, because the burst-day close is the
       price a trader would actually pay.
  N  — Narrow consolidation: the days before the burst were quiet and tight
       (low realized range vs the stock's own norm).
  C  — Calm pre-breakout day: the day immediately before the burst was a
       low-range, low-volume day (the "quiet before the move").
  H  — High close: the burst day closed in the top portion of its range.

Each check returns pass/fail plus the raw measurement so Claude (Layer 3)
can weigh borderline cases with full context.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _log_trend(y: np.ndarray) -> tuple[float, float]:
    """Least-squares fit of a straight line to `y`, returned as (slope, R²).

    Both halves matter and the caller needs them together. R² alone says the
    move was orderly; only the slope says which way it was orderly, and a
    caller handed R² on its own cannot tell a stair-step advance from a
    stair-step collapse.
    """
    x = np.arange(len(y), dtype=float)
    if len(y) < 3 or np.allclose(y, y[0]):
        return 0.0, 0.0
    coeffs = np.polyfit(x, y, 1)
    pred = np.polyval(coeffs, x)
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot else 0.0
    return float(coeffs[0]), r2


def evaluate_2lynch(df: pd.DataFrame) -> dict:
    """Run all six checks on a candidate's daily OHLCV history.

    The last row of `df` must be the burst day.
    Returns {checks: {...}, passes: int, summary: "4/6", detail_lines: [...]}
    """
    df = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"]).copy()
    burst = df.iloc[-1]
    pre = df.iloc[:-1]  # everything before the burst day

    checks: dict[str, dict] = {}

    # ---- 2: how many 4%+ up days in the last 20 sessions before today? ----
    rets = pre["Close"].pct_change().iloc[-20:] * 100
    prior_bursts = int((rets >= 4.0).sum())
    checks["2_first_or_second_burst"] = {
        "pass": prior_bursts <= 1,
        "value": f"{prior_bursts} prior 4% bursts in last 20 days",
    }

    # ---- L: shape AND direction of the prior 30-day move (log-price fit) ----
    # The slope is half the answer. Judged on R² alone this check passed a
    # smooth 45% collapse with R²=1.00 and reported "R²=1.00 over prior 30
    # days" to the scorer, telling Claude the structure was orderly without
    # telling it the structure was orderly *downwards*.
    log_closes = np.log(pre["Close"].iloc[-30:].to_numpy(dtype=float))
    slope, r2 = _log_trend(log_closes)
    fitted_move = (float(np.exp(slope * max(len(log_closes) - 1, 0))) - 1) * 100
    checks["L_linear_prior_move"] = {
        "pass": bool(r2 >= 0.55 and slope >= 0.0),
        "value": f"R²={r2:.2f}, fitted trend {fitted_move:+.1f}% over prior 30 days",
    }

    # ---- Y: young trend — not extended, measured through the burst day ----
    # Both halves used to run off `pre`, so the burst was invisible to the
    # only risk/reward guardrail in the checklist: a +35% gap-up scored the
    # same "-0.5% vs 20SMA" as the quiet day it gapped away from. Extension
    # is a fact about the price you would pay, which is today's close.
    closes = df["Close"]
    run_up_1mo = (closes.iloc[-1] / closes.iloc[-21] - 1) * 100 if len(closes) >= 21 else 0.0
    sma20 = closes.iloc[-20:].mean()
    ext_vs_sma20 = (closes.iloc[-1] / sma20 - 1) * 100
    checks["Y_young_trend"] = {
        "pass": bool(run_up_1mo < 25.0 and ext_vs_sma20 < 15.0),
        # Spell out the frame of reference: the scorer reads this line, and
        # the same number means very different things before and after the
        # burst. (The old format hard-coded a "+", printing "+-33.8%".)
        "value": (
            f"{run_up_1mo:+.1f}% past month, {ext_vs_sma20:+.1f}% vs 20SMA"
            " (through today's burst)"
        ),
    }

    # ---- N: narrow consolidation over the 5-10 days pre-burst ----
    daily_range = ((pre["High"] - pre["Low"]) / pre["Close"]) * 100
    recent_range = daily_range.iloc[-7:].mean()
    norm_range = daily_range.iloc[-60:-7].mean() if len(pre) > 67 else daily_range.mean()
    tightness = recent_range / norm_range if norm_range else 9.9
    checks["N_narrow_consolidation"] = {
        "pass": tightness <= 1.0,
        "value": f"pre-burst range {recent_range:.1f}%/day = {tightness:.2f}x its norm",
    }

    # ---- C: calm day immediately before the burst ----
    d1 = pre.iloc[-1]
    d1_range = (d1["High"] - d1["Low"]) / d1["Close"] * 100
    d1_vol_ratio = d1["Volume"] / pre["Volume"].iloc[-51:-1].mean()
    d1_move = abs(pre["Close"].pct_change().iloc[-1]) * 100
    # The range was measured and printed but left out of the verdict, so a
    # day that closed unchanged after a 15%-wide swing counted as "calm".
    # Judged against the stock's own norm, reusing N's baseline and multiple
    # rather than inventing a second constant. When there is no usable norm
    # the line says so: N's `else 9.9` sentinel prints "9.90x its norm" for a
    # range it never managed to measure, and that string goes to Claude.
    if norm_range:
        d1_range_ratio = d1_range / norm_range
        norm_text = f" = {d1_range_ratio:.2f}x its norm"
    else:
        d1_range_ratio = float("inf")
        norm_text = " (no usable range norm)"
    checks["C_calm_preburst_day"] = {
        "pass": bool(d1_move < 2.0 and d1_vol_ratio < 1.2 and d1_range_ratio <= 1.0),
        "value": (
            f"prior day {d1_move:.1f}% move, {d1_range:.1f}% range{norm_text}"
            f", {d1_vol_ratio:.2f}x volume"
        ),
    }

    # ---- H: burst day closed near its high ----
    rng = float(burst["High"]) - float(burst["Low"])
    if rng > 0:
        close_pos = (float(burst["Close"]) - float(burst["Low"])) / rng
        checks["H_close_near_high"] = {
            "pass": bool(close_pos >= 0.70),
            "value": f"closed at {close_pos:.0%} of day's range",
        }
    else:
        # A bar with no high-low separation (or an inverted one, which
        # `if rng else 1.0` also let through) demonstrates no intraday demand
        # and is nearly always bad data. The old expression awarded it a free
        # PASS and reported a fabricated "closed at 100% of day's range".
        checks["H_close_near_high"] = {
            "pass": False,
            "value": "burst bar has no usable high-low range; close position undefined",
        }

    passes = sum(1 for c in checks.values() if c["pass"])
    return {
        "checks": checks,
        "passes": passes,
        "total": len(checks),
        "summary": f"{passes}/{len(checks)}",
        "detail_lines": [
            f"{'PASS' if c['pass'] else 'FAIL'}  {name}: {c['value']}"
            for name, c in checks.items()
        ],
    }


def extra_context(df: pd.DataFrame) -> dict:
    """Additional metrics Claude uses for relative strength / setup scoring."""
    df = df.dropna(subset=["Close", "Volume"])
    close = float(df["Close"].iloc[-1])
    hi_52w = float(df["High"].iloc[-252:].max()) if len(df) >= 60 else float(df["High"].max())
    lo_52w = float(df["Low"].iloc[-252:].min()) if len(df) >= 60 else float(df["Low"].min())
    perf_3mo = (close / float(df["Close"].iloc[-63]) - 1) * 100 if len(df) > 63 else None
    perf_6mo = (close / float(df["Close"].iloc[-126]) - 1) * 100 if len(df) > 126 else None
    return {
        "pct_off_52w_high": round((close / hi_52w - 1) * 100, 1),
        "pct_above_52w_low": round((close / lo_52w - 1) * 100, 1),
        # None, not "n/a": these land in docs/data.json, whose contract is
        # "numbers are numbers or null" — a string sentinel in a numeric field
        # forces every consumer to special-case it.
        "perf_3mo_pct": round(perf_3mo, 1) if perf_3mo is not None else None,
        "perf_6mo_pct": round(perf_6mo, 1) if perf_6mo is not None else None,
    }
