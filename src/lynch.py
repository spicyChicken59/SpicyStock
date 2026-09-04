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


# --- thresholds -------------------------------------------------------------
# Named because tools/make_fixture.py applies the same rules to hand-authored
# measurements. When those two disagreed silently, the dashboard reported pass
# rates the real checklist would never produce. Importing these makes a numeric
# drift impossible; tests/test_lynch.py pins the predicates themselves.
MAX_PRIOR_BURSTS = 1        # 2: first or second burst of the leg
MIN_LINEAR_R2 = 0.55        # L: fit quality of the prior move
MIN_LINEAR_SLOPE = 0.0      # L: ...and it must be an advance, not a collapse
MAX_RUN_UP_1MO = 25.0       # Y: % run-up over the past month, through the burst
MAX_EXT_VS_SMA20 = 15.0     # Y: % above the 20-day average, through the burst
MAX_TIGHTNESS = 1.0         # N: pre-burst range vs the stock's own 60-day norm
MAX_D1_MOVE = 2.0           # C: prior day's absolute move, %
MAX_D1_VOL_RATIO = 1.2      # C: prior day's volume vs its 50-day average
MAX_D1_RANGE_RATIO = 1.0    # C: prior day's range vs the same 60-day norm
MIN_CLOSE_POS = 0.70        # H: where in the day's range the burst closed

# --- Bonde's two stated rules, which this screener did not have -------------
# Both were missing from the checklist AND from knowledge/strategy.md, so the
# tool did not hold them anywhere. Neither becomes a seventh and eighth
# checklist item, and that is the decision rather than an omission:
#
#   MIN_LYNCH_PASSES is 3 of the 6 checks -- a majority. Adding two more would
#   silently make it 3 of 8, weakening the gate everywhere while looking like
#   a strengthening. The six-check structure is also what tools/make_fixture.py,
#   the email, the page and every archived row's `lynch_total` are built on.
#
# So each rule goes where the way BONDE states it puts it:
#
#   UP DAYS is cardinal -- "never buy after 3+ consecutive up days" -- and is
#   pure arithmetic on closes, needing no judgement. An absolute rule is a
#   VETO, not one vote of eight: it rejects the burst outright, before the
#   pass count is consulted, and the archived row names the rule that did it.
#
#   A 4% BREAKDOWN in the base is a quality criterion, not an absolute. It says
#   the consolidation was not orderly, which is a judgement the checklist and
#   the scoring model already make from several angles, and one deep day inside
#   an otherwise clean base is a different thing from a broken one. So it is
#   MEASURED, judged against BREAKDOWN_PCT, and both the number and the verdict
#   go to the model as a `quality_notes` line, which knowledge/strategy.md
#   tells it how to weigh. It rejects nothing on its own.
#
#   The threshold is here and not in knowledge/strategy.md for the same reason
#   every other threshold is: the rulebook would then hold a second copy of a
#   number, and the two copies of this project's checklist have disagreed
#   before. strategy.md names the criterion; the line it reads carries the
#   figure the code actually applied.
#
# Both measurements are archived per candidate (they land in the `context`
# block of docs/data.json), so a later run of the evidence views can ask
# whether either actually separates the winners. Neither can answer that yet.
#
# UNVERIFIED AGAINST THE PRIMARY SOURCE. stockbee.blogspot.com and
# qullamaggie.net are both blocked by this sandbox's egress proxy -- checked
# with curl, not assumed -- so the numbers below come from the brief that
# specified this work and NOT from Bonde's own words. They are named constants
# for exactly that reason: if the source says four days rather than three, or
# names a different window for the base, this is the one place to change.
MAX_CONSECUTIVE_UP_DAYS = 2   # veto at 3+, counted BEFORE the burst day
BREAKDOWN_PCT = -4.0          # a single day this bad is a break, not a pullback
BREAKDOWN_LOOKBACK = 20       # sessions of base examined for one, before the burst


def consecutive_up_days(df: pd.DataFrame) -> int:
    """How many sessions in a row closed up, ending the day BEFORE the burst.

    The burst day itself is excluded on purpose: the rule is about what you are
    buying INTO. "Never buy after three up days" is a statement about the run
    that preceded the entry, and counting the entry as one of them would refuse
    every burst that followed two up days rather than three.

    Note what this catches that the checklist does not. `C` already asks the
    prior day to be calm, and calm is not the same as down -- three quiet
    +0.8% sessions pass `C` comfortably and are exactly the tired drift this
    rule exists to refuse.

    Takes the WHOLE frame, burst day last, and drops it here rather than at
    each call site: this and worst_base_day() are called from two places, and
    two callers slicing the burst day off separately is how the two copies of
    a rule start to disagree.
    """
    closes = df.dropna(subset=["Close"])["Close"].iloc[:-1].to_numpy(dtype=float)
    run = 0
    # Down to 1 and not to 0: index 0 has no day before it. Widening the range
    # is the one mutation of this function the suite cannot kill, and it is
    # provably equivalent rather than a gap -- i reaches 0 only if every step
    # back was an up day, which makes the series strictly increasing, and the
    # comparison there would be closes[0] > closes[-1], its own minimum against
    # its own maximum. That breaks, and the count is unchanged.
    for i in range(len(closes) - 1, 0, -1):
        if closes[i] > closes[i - 1]:
            run += 1
        else:
            break
    return run


def worst_base_day(df: pd.DataFrame, lookback: int = BREAKDOWN_LOOKBACK) -> float | None:
    """The worst single-session % change in the base, or None if there is none.

    One deep down day is what separates a pullback from a break: a base that
    dropped 4% in a session was not resting, it was being sold, and the burst
    is a bounce inside a broken structure rather than a breakout from a quiet
    one. The burst day is excluded for the same reason as above -- it is a big
    UP day by construction, so including it could only ever dilute the window.

    Rounded to the tenth of a percent the reader is shown, and compared at that
    precision too. Unrounded, a base day of -4.04% failed the criterion while
    every surface printed it as "-4.0%" beside a note saying -4.0% or worse is
    a break: a row displaying the threshold value and refused by it, and its
    -3.96% neighbour displaying the same value and passing. One number reaches
    the archive, the note and the predicate now, and it is this one.
    """
    closes = df.dropna(subset=["Close"])["Close"].iloc[:-1]
    moves = closes.pct_change().iloc[-lookback:].dropna() * 100
    return round(float(moves.min()), 1) if len(moves) else None


def failed_vetoes(lynch_result: dict) -> list[str]:
    """The names of the absolute rules this candidate broke, in order.

    Kept here beside the rules themselves rather than inlined into the
    pipeline's gate, so that adding a second veto is one edit and not two.
    A caller that does not know about vetoes at all (an older archived result
    read back, a hand-built double in a test) reports none, which is the same
    answer the code gave before this rule existed.
    """
    vetoes = lynch_result.get("vetoes")
    if not isinstance(vetoes, dict):
        return []
    return [name for name, v in vetoes.items() if not v.get("pass", True)]


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
    Returns {checks: {...}, passes: int, summary: "4/6", detail_lines: [...],
    vetoes: {...}, context_checks: {...}}. Neither of the last two is counted
    in `passes`. `vetoes` is absolute -- the gate reads it through
    failed_vetoes() before it looks at the pass count at all -- and
    `context_checks` is the opposite: measured, judged, and left to the
    scoring model to weigh, refusing nothing on its own.
    """
    df = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"]).copy()
    burst = df.iloc[-1]
    pre = df.iloc[:-1]  # everything before the burst day

    checks: dict[str, dict] = {}

    # ---- 2: how many 4%+ up days in the last 20 sessions before today? ----
    rets = pre["Close"].pct_change().iloc[-20:] * 100
    prior_bursts = int((rets >= 4.0).sum())
    checks["2_first_or_second_burst"] = {
        "pass": prior_bursts <= MAX_PRIOR_BURSTS,
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
        "pass": bool(r2 >= MIN_LINEAR_R2 and slope >= MIN_LINEAR_SLOPE),
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
        "pass": bool(run_up_1mo < MAX_RUN_UP_1MO and ext_vs_sma20 < MAX_EXT_VS_SMA20),
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
        "pass": tightness <= MAX_TIGHTNESS,
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
        "pass": bool(d1_move < MAX_D1_MOVE and d1_vol_ratio < MAX_D1_VOL_RATIO and d1_range_ratio <= MAX_D1_RANGE_RATIO),
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
            "pass": bool(close_pos >= MIN_CLOSE_POS),
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

    # Bonde's cardinal rule, measured beside the checklist and deliberately
    # not in it -- see MAX_CONSECUTIVE_UP_DAYS for why it is a veto and not a
    # seventh vote. `checks`, `passes`, `total`, `summary` and `detail_lines`
    # are untouched, so every consumer of the six-check structure sees exactly
    # what it saw before this rule existed.
    up_run = consecutive_up_days(df)
    vetoes = {
        "up_days": {
            "pass": up_run <= MAX_CONSECUTIVE_UP_DAYS,
            "value": (f"{up_run} consecutive up day{'' if up_run == 1 else 's'} "
                      f"into the burst; the rule refuses "
                      f"{MAX_CONSECUTIVE_UP_DAYS + 1} or more"),
        },
    }

    # Measured, judged, and handed to the model rather than acted on here.
    # Separate from `checks` because it is not a vote, and separate from
    # `vetoes` because it refuses nothing: src.scorer sends these as
    # `quality_notes`, which knowledge/strategy.md tells the model to weigh.
    worst = worst_base_day(df)
    context_checks = {
        "base_breakdown": {
            "pass": worst is None or worst > BREAKDOWN_PCT,
            "value": (f"worst base day {worst:+.1f}% in the prior "
                      f"{BREAKDOWN_LOOKBACK} sessions; {BREAKDOWN_PCT:+.1f}% or "
                      f"worse is a break, not a pullback"
                      if worst is not None
                      else f"no usable base in the prior {BREAKDOWN_LOOKBACK} sessions"),
        },
    }

    passes = sum(1 for c in checks.values() if c["pass"])
    return {
        "checks": checks,
        "passes": passes,
        "total": len(checks),
        "summary": f"{passes}/{len(checks)}",
        "vetoes": vetoes,
        "context_checks": context_checks,
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
    # The NUMBERS behind Bonde's two rules. Their verdicts travel separately --
    # the veto through failed_vetoes(), the base breakdown through
    # evaluate_2lynch()'s context_checks -- and these are the measurements
    # themselves, which the archive keeps. `consecutive_up_days` is
    # the veto's own measurement, reported for the same reason a passed check
    # reports its value -- 0 up days and 2 are both allowed and are not the
    # same setup -- and because the archive keeps this block, so the evidence
    # views can one day ask whether either number separates the winners.
    worst = worst_base_day(df)
    return {
        "pct_off_52w_high": round((close / hi_52w - 1) * 100, 1),
        "pct_above_52w_low": round((close / lo_52w - 1) * 100, 1),
        "consecutive_up_days": consecutive_up_days(df),
        "worst_base_day_pct": worst,
        # None, not "n/a": these land in docs/data.json, whose contract is
        # "numbers are numbers or null" — a string sentinel in a numeric field
        # forces every consumer to special-case it.
        "perf_3mo_pct": round(perf_3mo, 1) if perf_3mo is not None else None,
        "perf_6mo_pct": round(perf_6mo, 1) if perf_6mo is not None else None,
    }
