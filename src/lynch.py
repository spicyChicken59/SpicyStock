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

Each check returns pass/fail plus the raw measurement so Claude (Layer 4)
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
PRIOR_BURST_PCT = 4.0       # 2: what counts as an earlier burst — the scan's gain rule, applied to history

#: How much history each check READS, as against the thresholds above, which
#: are what a measurement is compared AGAINST. Two different kinds of number,
#: and the difference is load-bearing twice over.
#:
#: These were bare literals inside evaluate_2lynch -- iloc[-20:], iloc[-30:],
#: iloc[-21], iloc[-7:], iloc[-60:-7] -- so they were invisible to anything
#: reasoning about this strategy's numbers: rules_fingerprint() walks what
#: this module names, and a window left as a literal would let the record say
#: "same rules" across a change that altered them. They are grouped rather
#: than left as module scalars because tools/make_fixture.py starts from
#: hand-authored MEASUREMENTS and never slices a frame, so it can carry a
#: threshold and cannot carry a window -- and two guards in tests/test_lynch.py
#: are written against the scalars for exactly that reason. Putting the
#: distinction in the code beats adding an exemption list to the guards.
WINDOWS = {
    "prior_burst_lookback": 20,   # 2: sessions searched for earlier bursts
    "linear_fit_sessions": 30,    # L: sessions of prior move the log-price fit covers
    "sma_sessions": 20,           # Y: the moving average the extension is measured against
    "run_up_sessions": 20,        # Y: sessions the month's run-up spans
    "tight_sessions": 7,          # N: the recent window called "the consolidation"
    "norm_sessions": 60,          # N: the range norm, ending where that window starts
}
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
#   MIN_LYNCH_PASSES is 3 of the 6 checks -- HALF of them. (This said "a
#   majority" in three files until an audit did the arithmetic: a majority of
#   six is four. The argument is unharmed and the word was wrong.) Adding two
#   more checks would silently make it 3 of 8, weakening the gate everywhere
#   while looking like a strengthening. The six-check structure is also what
#   tools/make_fixture.py, the email, the page and every archived row's
#   `lynch_total` are built on.
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
#   The threshold is here and not in knowledge/strategy.md: a second copy of a
#   GATE number in the rulebook is how the two copies of this project's
#   checklist came to disagree. strategy.md names the criterion; the line it
#   reads carries the figure the code actually applied.
#
#   That rule is about the numbers the CODE acts on. strategy.md does state two
#   bars of its own -- top 25% of range for an A+, 20% extension for an
#   automatic kill -- against MIN_CLOSE_POS's top 30% and MAX_EXT_VS_SMA20's
#   15%. Those are deliberate and now say so where they are written: a check
#   answers "does this pass", the rulebook answers "how good is it", and an A+
#   bar stricter than a passing one is the point rather than a drift. They are
#   not second copies of these constants, and this comment claimed a blanket
#   absence of second copies until a prose audit found them.
#
# Both measurements are archived on EVERY burst the scan found, scored or
# refused, and survive into docs/ledger.json beside the forward returns -- so
# the evidence views can one day ask whether either separates the winners, and
# in particular whether the bursts the veto refused really did do worse than
# the ones it let through. That sentence claimed all of this before it was
# true: the vetoed row carried no `context` at all, and slim_row() dropped the
# block on its way into the only file that outlives a run, so the question was
# unanswerable by construction. Neither can answer it YET -- no run has ever
# had its secrets -- but the record will now hold what an answer needs.
#
# UNVERIFIED AGAINST THE PRIMARY SOURCE. stockbee.blogspot.com and
# qullamaggie.net are both blocked by this sandbox's egress proxy -- checked
# with curl, not assumed -- so the numbers below come from the brief that
# specified this work and NOT from Bonde's own words. They are named constants
# for exactly that reason: if the source says four days rather than three, or
# names a different window for the base, this is the one place to change.
#: Every absolute rule, named once, here beside the rules themselves. The
#: reason word an unscored burst carries is DERIVED from the name by
#: veto_reason(), so nothing anywhere holds a second copy of this list that a
#: new rule could be added without. It used to: src.pipeline kept its own
#: tuple, and an audit added a realistic second veto to evaluate_2lynch alone
#: and got a green suite plus an evening run that died on KeyError after the
#: scan -- with the comment above that tuple claiming the arrangement made
#: exactly that impossible.
VETO_RULES = ("up_days",)

MAX_CONSECUTIVE_UP_DAYS = 2   # veto at 3+, counted BEFORE the burst day
BREAKDOWN_PCT = -4.0          # a single day this bad is a break, not a pullback
BREAKDOWN_LOOKBACK = 20       # sessions of base examined for one, before the burst


def _base(df: pd.DataFrame) -> pd.Series:
    """The closes of the base: everything before the burst day, Close only.

    The single slicing rule both measurements below apply, so that no caller
    can hand them a differently-pruned frame and get a differently-shaped
    answer. Close only, because a bar whose High the feed dropped still has a
    real close and still happened -- discarding it would shorten the series
    and move a run of up days that really occurred.
    """
    return df.dropna(subset=["Close"])["Close"].iloc[:-1]


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
    a rule start to disagree. They did: evaluate_2lynch() had already dropped
    every bar missing ANY of the five OHLCV fields while extra_context() had
    dropped only those missing Close or Volume, so one bar with no High made
    the veto count 2 and the number sent to the scoring model 3 -- a run that
    told the model it had refused something it had allowed. _base() is the one
    rule now, and it is the rule this measurement is about: closes.
    """
    closes = _base(df).to_numpy(dtype=float)
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
    moves = _base(df).pct_change().iloc[-lookback:].dropna() * 100
    if not len(moves):
        return None
    # `+ 0.0` collapses -0.0, which a base whose worst day is between 0 and
    # -0.05% produces: it is archived as -0.0 and printed "-0.0%", a minus sign
    # in front of nothing.
    return round(float(moves.min()), 1) + 0.0


def veto_reason(name: str) -> str:
    """The reason word for an absolute rule, computed rather than looked up.

    A lookup would raise on a rule whose word nobody remembered to add, and it
    would raise in the pipeline's archive step -- after the scan, and on a
    burst that was correctly refused. Deriving it means the worst a forgotten
    rule can do is publish a word no surface has prose for, which the tests
    below catch at development time rather than the run catching at midnight.
    """
    return f"veto_{name}"


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
    # One level in, not one level short. The container was checked and its
    # entries were not, so a `vetoes` block holding anything but dicts raised
    # AttributeError inside the pipeline's gate -- the same shape this project
    # has now found six times, and the reason the check above exists at all.
    # A non-string name is refused too: the word is built from it, and a run
    # must not publish `veto_7` as a reason no surface has prose for.
    return [name for name, v in vetoes.items()
            if isinstance(name, str) and isinstance(v, dict) and not v.get("pass", True)]


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
    # The six checks read intraday ranges and volume, so they need a bar with
    # all five fields. Bonde's two measurements read closes and must NOT: they
    # are handed `raw`, and _base() applies their own single rule to it. When
    # both read `df` the two disagreed on any frame with a partial bar in it,
    # and the run reported one answer to the reader and the other to the model.
    raw = df
    df = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"]).copy()
    burst = df.iloc[-1]
    pre = df.iloc[:-1]  # everything before the burst day

    checks: dict[str, dict] = {}

    # EVERY measurement below is rounded to the precision it is PRINTED at,
    # once, and both the verdict and the line read that same rounded number.
    # An audit found the class this closes: `worst_base_day()` was rounded for
    # exactly this reason and the sweep stopped there, while four other checks
    # went on displaying one number and deciding on another. Measured over 600
    # synthetic bursts, the printed value sat exactly on its own threshold for
    # N's tightness on 3.2% of frames and L's R² on 0.8% -- so roughly one
    # burst in thirty showed the reader "1.00x its norm" under a rule stating
    # 1.00 and was refused, or shown it and passed, with nothing to tell the
    # two apart. Rounding here rather than in the f-strings is deliberate: two
    # format strings that must agree is the arrangement that produced this.
    def shown(value: float, places: int) -> float:
        return round(float(value), places)

    # ---- 2: how many 4%+ up days in the last 20 sessions before today? ----
    rets = pre["Close"].pct_change().iloc[-WINDOWS["prior_burst_lookback"]:] * 100
    prior_bursts = int((rets >= PRIOR_BURST_PCT).sum())
    checks["2_first_or_second_burst"] = {
        "pass": prior_bursts <= MAX_PRIOR_BURSTS,
        "value": (f"{prior_bursts} prior {PRIOR_BURST_PCT:g}% bursts in last "
                  f"{WINDOWS['prior_burst_lookback']} days"),
    }

    # ---- L: shape AND direction of the prior 30-day move (log-price fit) ----
    # The slope is half the answer. Judged on R² alone this check passed a
    # smooth 45% collapse with R²=1.00 and reported "R²=1.00 over prior 30
    # days" to the scorer, telling Claude the structure was orderly without
    # telling it the structure was orderly *downwards*.
    log_closes = np.log(pre["Close"].iloc[-WINDOWS["linear_fit_sessions"]:].to_numpy(dtype=float))
    slope, r2 = _log_trend(log_closes)
    r2 = shown(r2, 2)
    fitted_move = shown((float(np.exp(slope * max(len(log_closes) - 1, 0))) - 1) * 100, 1)
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
    sma20 = closes.iloc[-WINDOWS["sma_sessions"]:].mean()
    ext_vs_sma20 = shown((closes.iloc[-1] / sma20 - 1) * 100, 1)
    if len(closes) >= WINDOWS["run_up_sessions"] + 1:
        run_up_1mo = shown((closes.iloc[-1] / closes.iloc[-(WINDOWS["run_up_sessions"] + 1)] - 1) * 100, 1)
        run_up_text = f"{run_up_1mo:+.1f}% past month"
        run_up_ok = run_up_1mo < MAX_RUN_UP_1MO
    else:
        # Fewer than 21 closes survive the cleaning, so there is no month to
        # measure over. This used to substitute 0.0 -- and print "+0.0% past
        # month" to the scoring model as if it had been measured, on a frame
        # whose real run-up over the sessions it did have was +16.9%. A number
        # that was not measured is not 0; it is not a number. The same rule C
        # already applies to a range norm it cannot compute: say so, and let
        # the half that WAS measured decide on its own.
        run_up_1mo = None
        run_up_text = (f"no {WINDOWS['run_up_sessions']}-session history "
                       "to measure a month over")
        run_up_ok = True
    checks["Y_young_trend"] = {
        "pass": bool(run_up_ok and ext_vs_sma20 < MAX_EXT_VS_SMA20),
        # Spell out the frame of reference: the scorer reads this line, and
        # the same number means very different things before and after the
        # burst. (The old format hard-coded a "+", printing "+-33.8%".)
        "value": (
            f"{run_up_text}, {ext_vs_sma20:+.1f}% vs 20SMA"
            " (through today's burst)"
        ),
    }

    # ---- N: narrow consolidation over the 5-10 days pre-burst ----
    daily_range = ((pre["High"] - pre["Low"]) / pre["Close"]) * 100
    recent_range = daily_range.iloc[-WINDOWS["tight_sessions"]:].mean()
    norm_range = (daily_range.iloc[-WINDOWS["norm_sessions"]:-WINDOWS["tight_sessions"]].mean()
                  if len(pre) > WINDOWS["norm_sessions"] + WINDOWS["tight_sessions"]
                  else daily_range.mean())
    recent_range = shown(recent_range, 1)
    tightness = shown(recent_range / norm_range, 2) if norm_range else 9.9
    checks["N_narrow_consolidation"] = {
        "pass": tightness <= MAX_TIGHTNESS,
        "value": f"pre-burst range {recent_range:.1f}%/day = {tightness:.2f}x its norm",
    }

    # ---- C: calm day immediately before the burst ----
    d1 = pre.iloc[-1]
    d1_range = shown((d1["High"] - d1["Low"]) / d1["Close"] * 100, 1)
    d1_vol_ratio = shown(d1["Volume"] / pre["Volume"].iloc[-51:-1].mean(), 2)
    d1_move = shown(abs(pre["Close"].pct_change().iloc[-1]) * 100, 1)
    # The range was measured and printed but left out of the verdict, so a
    # day that closed unchanged after a 15%-wide swing counted as "calm".
    # Judged against the stock's own norm, reusing N's baseline and multiple
    # rather than inventing a second constant. When there is no usable norm
    # the line says so: N's `else 9.9` sentinel prints "9.90x its norm" for a
    # range it never managed to measure, and that string goes to Claude.
    if norm_range:
        d1_range_ratio = shown(d1_range / norm_range, 2)
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
        # .0% is two decimal places on the ratio, so the reader's "70%" and
        # MIN_CLOSE_POS's 0.70 are one number. Measured at 0% ambiguity on the
        # synthetic frames, but only because make_ohlcv pins close_pos at one
        # value for every seed -- the check nearest its own threshold is the
        # one the suite never exercises near it, which is an artefact of the
        # fixture and not a property of the code.
        close_pos = shown((float(burst["Close"]) - float(burst["Low"])) / rng, 2)
        if 0.0 <= close_pos <= 1.0:
            checks["H_close_near_high"] = {
                "pass": bool(close_pos >= MIN_CLOSE_POS),
                "value": f"closed at {close_pos:.0%} of day's range",
            }
        else:
            # A close OUTSIDE its own day's range is the same class of bad bar
            # as an inverted one, and used to print "closed at 145% of day's
            # range" and PASS -- the branch below caught rng <= 0 and nothing
            # caught a close the range does not contain.
            checks["H_close_near_high"] = {
                "pass": False,
                "value": f"close outside its own range ({close_pos:.0%}); no usable bar",
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
    up_run = consecutive_up_days(raw)
    vetoes = {
        # Keyed by the names in VETO_RULES; a test asserts the two agree, so a
        # rule added here without a name there fails at development time.
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
    worst = worst_base_day(raw)
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
    """Additional metrics Claude uses for relative strength / setup scoring.

    `raw` is kept for the same reason evaluate_2lynch() keeps one: Bonde's two
    measurements have their own rule about which bars count, and handing them
    a frame this function pruned for its own purposes made the number sent to
    the model disagree with the verdict the veto reached from it.
    """
    raw = df
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
    worst = worst_base_day(raw)
    return {
        "pct_off_52w_high": round((close / hi_52w - 1) * 100, 1),
        "pct_above_52w_low": round((close / lo_52w - 1) * 100, 1),
        "consecutive_up_days": consecutive_up_days(raw),
        "worst_base_day_pct": worst,
        # None, not "n/a": these land in docs/data.json, whose contract is
        # "numbers are numbers or null" — a string sentinel in a numeric field
        # forces every consumer to special-case it.
        "perf_3mo_pct": round(perf_3mo, 1) if perf_3mo is not None else None,
        "perf_6mo_pct": round(perf_6mo, 1) if perf_6mo is not None else None,
    }
