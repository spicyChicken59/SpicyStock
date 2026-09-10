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

#: How much history each check READS -- and, since round 11, each of
#: extra_context()'s measurements too -- as against the thresholds above,
#: which are what a measurement is compared AGAINST. Two different kinds of
#: number, and the difference is load-bearing twice over.
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
#:
#: Round 8 named six of them and MISSED THE SEVENTH, which is `C`'s: it
#: divided by `pre["Volume"].iloc[-51:-1].mean()`, so the 50 sessions the
#: calm-day rule averages over were spelled as a bare 51 in a slice bound.
#: Reproduced rather than argued -- changing that 50 to 30 left
#: rules_fingerprint() BYTE-IDENTICAL and tests/test_lynch.py,
#: tests/test_scanner.py and tests/test_docs_are_true.py all green, while C's
#: verdict moved. A round that names six of seven is how a class gets
#: declared closed on the instance nobody looked at, so
#: test_no_check_reads_a_window_left_as_a_bare_number reads the numeric
#: literals out of the module's own AST rather than trusting this list.
#:
#: AND THE ROUND THAT NAMED THE SEVENTH DECLARED THE CLASS CLOSED ON ONE
#: FUNCTION. That guard read `evaluate_2lynch` alone, and `extra_context()`
#: -- four of the metrics payload's own fields, archived in every row's
#: `context` -- went on spelling 252, 126, 63 and 60. Reproduced the same
#: way: `iloc[-63]` and its `len(df) > 63` guard changed to 45 left the
#: fingerprint byte-identical and the whole suite green, while
#: `perf_3mo_pct` moved under a key still called `3mo` and
#: knowledge/strategy.md went on naming it as one of the two
#: relative-strength measures the model has. They are the last four below,
#: and the guard walks every function in this module now.
WINDOWS = {
    "prior_burst_lookback": 20,   # 2: sessions searched for earlier bursts
    "linear_fit_sessions": 30,    # L: sessions of prior move the log-price fit covers
    "sma_sessions": 20,           # Y: the moving average the extension is measured against
    "run_up_sessions": 20,        # Y: sessions the month's run-up spans
    "tight_sessions": 7,          # N: the recent window called "the consolidation"
    "norm_sessions": 60,          # N: the range norm, ending where that window starts
    # C: the volume average the day before the burst is called quiet against,
    # ending the session before that day. Named HERE and not read off
    # ScanConfig.rvol_lookback, which holds the same 50 for rule 3 -- and that
    # is the decision, not an oversight. src.lynch imports numpy and pandas
    # and nothing of this project's, which is what lets tools/make_fixture.py
    # and the checklist's own tests take the thresholds without dragging the
    # scanner's config in; and the two numbers answer two questions ("was the
    # day before quiet" against "is today's volume unusual for this name"),
    # so one of them moving is not automatically the other moving. They are
    # held equal by a test that says so out loud rather than by a shared name,
    # because the equality is a judgement -- ScanConfig's own comment argues
    # it -- and a judgement with a guard on it can be revisited, while one
    # spelled as an import cannot even be seen.
    "volume_norm_sessions": 50,
    # extra_context()'s four. No rule reads them and nothing is compared
    # against them -- they are measurements the scoring model weighs, which
    # is why they are windows and not thresholds -- but a window that moves
    # moves every number the model saw, and round 11 put what produced the
    # SCORE into the fingerprint for exactly that reason.
    "high_low_sessions": 252,      # the 52-week high and low the burst is placed against
    "high_low_min_sessions": 60,   # ...below which that window is not attempted and the whole frame is used
    "perf_6mo_sessions": 126,      # perf_6mo_pct: the close this one is measured from
    "perf_3mo_sessions": 63,       # perf_3mo_pct: likewise, and strategy.md names it to the model
}
MIN_LINEAR_R2 = 0.55        # L: fit quality of the prior move
MIN_LINEAR_SLOPE = 0.0      # L: ...and it must be an advance, not a collapse
MAX_RUN_UP_1MO = 25.0       # Y: % run-up over the past month, through the burst
MAX_EXT_VS_SMA20 = 15.0     # Y: % above the 20-day average, through the burst
MAX_TIGHTNESS = 1.0         # N: pre-burst range vs the stock's own 60-day norm
MAX_D1_MOVE = 2.0           # C: prior day's absolute move, %
MAX_D1_VOL_RATIO = 1.2      # C: prior day's volume vs its own volume_norm_sessions average
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
# names a different window for the base, this is the one place the CODE reads
# it from. It is NOT the only place the number is written, and this comment
# said it was: knowledge/strategy.md tells the model "three or more is refused
# before it reaches you", "anything you are scoring is 0, 1 or 2" and "the
# difference between the three you do see", and README states the rule in the
# pipeline diagram. Editing this constant alone leaves the rulebook -- the
# system prompt, a surface a reader never sees -- asserting a rule the code no
# longer applies. What makes the sentence true is a guard rather than a
# promise, and it is two guards over four sentences rather than one over all
# of them: test_the_rulebook_states_the_numbers_the_checklist_applies reads
# the rulebook's three, and test_the_documented_thresholds_are_the_ones_the_
# code_applies reads README's. This comment said "all four" of one test that
# reads three, and the third of the three was read by neither -- so sweeping
# the two that were guarded left the system prompt saying "the difference
# between the three you do see" over a veto admitting four counts, with the
# value pin as the only red and a deliberate change updating that.
#: Every absolute rule, named once, here beside the rules themselves. The
#: reason word an unscored burst carries is DERIVED from the name by
#: veto_reason(), so nothing anywhere holds a second copy of this list that a
#: new rule could be added without. It used to: src.pipeline kept its own
#: tuple, and an audit added a realistic second veto to evaluate_2lynch alone
#: and got a green suite plus an evening run that died on KeyError after the
#: scan -- with the comment above that tuple claiming the arrangement made
#: exactly that impossible.
VETO_RULES = ("up_days",)

#: WHICH BARS THE CHECKS COUNT, as a number, because that question has no
#: other way into the record. rules_fingerprint() derives the strategy from
#: every number this module names -- and the change that gave `2`, `L`, `Y`
#: and `C` a close-only series left it BYTE-IDENTICAL while the same frame
#: read "+4.0% past month" on one side of the commit and "+7.7%" on the
#: other. A record spanning that change carries both screeners under one
#: label, which is the exact state round 8 built the fingerprint to prevent,
#: arriving through the one door a walk of numbers cannot see.
#:
#: BUMP IT IN THE SAME COMMIT as any change to what a check READS -- which
#: bars a measurement counts, which bar it is anchored on, which session it
#: names -- as against what a check is compared AGAINST, which is a threshold
#: and moves the fingerprint by itself. It is read by no rule: there is
#: nothing to compare it with, and the two structural guards over this
#: module's constants exempt a `*_REVISION` name for that reason and for no
#: other. 1 is every screener up to and including round 11's burst-bar
#: commit; 2 is the close-only series and the anchors that came with it;
#: 3 is L stepping past the consolidation to fit the prior move, which
#: changes WHICH BARS that check reads and nothing it is compared against.
RULES_REVISION = 3

MAX_CONSECUTIVE_UP_DAYS = 2   # veto at 3+, counted BEFORE the burst day
BREAKDOWN_PCT = -4.0          # a single day this bad is a break, not a pullback
BREAKDOWN_LOOKBACK = 20       # sessions of base examined for one, before the burst


def _series(df: pd.DataFrame, column: str) -> pd.Series:
    """`column`, from every bar that carries it.

    The one rule a single-column measurement follows, so that no caller can
    hand it a frame pruned for somebody else's fields and get a differently
    shaped answer. A bar whose High the feed dropped still has a real close
    and still happened: throwing it away does not merely lose a reading, it
    MERGES the two sessions either side of it and slides every reading past
    it. Reproduced on a base whose largest session was +2.5%, where two
    missing Highs made check 2 report two prior 4% bursts that never
    happened and slid Y's month reading from +45.2% to +52.6%.
    """
    return df.dropna(subset=[column])[column]


def _carrying(df: pd.DataFrame, columns) -> np.ndarray:
    """The POSITIONS of the bars in `df` that carry every one of `columns`.

    Positions rather than timestamps, and that is the whole point. The first
    version of this rule looked the anchor bar up by its stamp
    (`df.index == stamp`) and handed back the WHOLE FRAME when it found
    nothing -- every bar after the anchor included, which is the merge the
    anchor exists to prevent, arriving by the other door. It finds nothing
    for a NaT in the index (`NaT == NaT` is False; round 9's L2 found that
    shape reaching this module) and it finds two rows for a stamp the feed
    sent twice. A position cannot be ambiguous and cannot be absent.
    """
    return np.flatnonzero(df[list(columns)].notna().all(axis=1).to_numpy())


def _through(df: pd.DataFrame, upto: int) -> pd.DataFrame:
    """`df` up to and including position `upto`: nothing after the bar the
    checklist is grading.

    `evaluate_2lynch()` drops every bar missing one of CHECKLIST_COLUMNS and
    calls the last row LEFT the burst, so on a frame whose newest bar has no
    Open the burst is the session BEFORE it -- and a close-only reading, which
    keeps that bar, would otherwise measure "through today's burst" on a bar
    `H` is not grading. One request, one bar: the same rule burst_bar_shape()
    states for its three measurements, applied everywhere this module reads a
    series rather than a bar.
    """
    return df.iloc[:upto + 1]


def graded_bar_at(df: pd.DataFrame) -> int | None:
    """Where in `df` the bar `evaluate_2lynch()` grades as the burst sits, or
    None when no bar in it carries all five of CHECKLIST_COLUMNS.

    Public because the CHART is the third surface in the same request, and
    "one request, one bar" is a rule about the request rather than about this
    module: src.scorer.render_chart() ends the picture here, so the rightmost
    candle is the bar `H` graded and the metrics block describes.
    """
    if any(name not in df.columns for name in CHECKLIST_COLUMNS):
        return None
    at = _carrying(df, CHECKLIST_COLUMNS)
    return int(at[-1]) if len(at) else None


def _move_into(closes: pd.Series, at: int) -> float:
    """The fractional move into `closes`' position `at`, along a close-only
    series.

    The session BEFORE it is the one before it in `closes` -- the last
    session that printed a close -- and not the bar before it in whatever
    frame the caller pruned for its own fields. A hole between the two makes
    those different sessions, and the difference is two sessions' drift
    reported as one day's.

    NaN when there is no session before it to have moved from, which is what
    `pct_change()` returned in the same position and which every comparison
    against it is false for. NaN too when that session closed at or below
    zero: `pct_change()` answered inf there and dividing answers
    ZeroDivisionError, which would come out of evaluate_2lynch() inside
    src.pipeline's gate loop -- no try around it, so the evening run dies
    after the scan and every earlier Claude call are paid for.
    src.scanner._session_bar_problem() refuses a non-positive close on the
    SESSION bar and nothing validates the rest of the frame.
    """
    if at <= 0:
        return float("nan")
    prev = float(closes.iloc[at - 1])
    if prev <= 0:
        return float("nan")
    return float(closes.iloc[at]) / prev - 1.0


#: The three fields a daily range is made of. `N`'s consolidation and its
#: norm, and `C`'s range, are high-minus-low over the close -- so they count
#: the bars carrying those three, by the same rule the closes follow, and not
#: the bars that also carry an Open and a Volume they never read. Measured
#: before this was true: two shelf bars losing ONLY their Open moved `N` from
#: "1.7%/day = 0.43x its norm" to "2.3%/day = 0.58x", because the 60-session
#: norm slid two sessions back.
RANGE_COLUMNS: tuple[str, ...] = ("High", "Low", "Close")


def _ranges(df: pd.DataFrame) -> pd.Series:
    """Each bar's high-low span as a percentage of its own close, for the
    bars that carry all three."""
    kept = df.dropna(subset=list(RANGE_COLUMNS))
    return (kept["High"] - kept["Low"]) / kept["Close"] * 100


def _base(df: pd.DataFrame) -> pd.Series:
    """The closes of the base: everything before the burst day, Close only.

    The single slicing rule both measurements below apply, so that no caller
    can hand them a differently-pruned frame and get a differently-shaped
    answer. Close only, because a bar whose High the feed dropped still has a
    real close and still happened -- discarding it would shorten the series
    and move a run of up days that really occurred.
    """
    return _series(df, "Close").iloc[:-1]


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


#: The burst bar's own geometry, under the names the scoring request carries.
#: Named here so that nothing hand-keeps a second copy of the list: a docs
#: test holds knowledge/strategy.md to explaining every one of them, and
#: extra_context() is asserted to produce exactly these.
#:
#: NOT thresholds and NOT windows. No rule reads them, nothing is compared
#: against them, and they are strings, so rules_fingerprint() -- which walks
#: this module's upper-case NUMBERS and its WINDOWS -- does not record them.
#: That is right rather than an omission: the fingerprint says which screener
#: produced a row, and a measurement that refuses nothing changes no burst.
#: (What DOES change is the rulebook that tells the model how to read them,
#: and that is in the fingerprint already, through `score.prompt`.)
BURST_BAR_KEYS: tuple[str, ...] = ("gap_pct", "bar_range_pct", "range_expansion")


def _finite(value) -> float | None:
    """`value` as a float, or None when it is not a finite number.

    Bools are refused rather than read as 1.0 and 0.0, the same rule
    src.ledger._num() applies for the same reason: a True in a price column
    is a shape no feed produces and reading it as a dollar is worse than
    refusing it.
    """
    if isinstance(value, (bool, np.bool_)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def _missing(value) -> bool:
    """Is this the absence `evaluate_2lynch()`'s dropna would remove a bar for?

    Not the same question as _finite(): a bool is not missing, and neither is
    a string. dropna removes NaN and None, so that is what this answers, and
    a value it cannot answer for is present.
    """
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


#: The five fields a bar must carry to BE a bar the checklist grades --
#: the burst, and the prior day `C` judges. `evaluate_2lynch()` drops the
#: rest and calls the last row LEFT the burst.
#:
#: NOT "the five fields it needs of every bar it reads", which is what this
#: said until an audit read it against the code beside it: the close-only
#: readings (`2`, `L`, `Y`, `C`'s move, the up-days veto, the base breakdown)
#: count every bar carrying a close, and `N`'s ranges count every bar
#: carrying a high, a low and a close. Which bars a MEASUREMENT counts is the
#: fields that measurement reads; this is which bars can be the SUBJECT.
CHECKLIST_COLUMNS: tuple[str, ...] = ("Open", "High", "Low", "Close", "Volume")


def _read_by_the_checklist(bar, columns) -> bool:
    """Could `evaluate_2lynch()` grade this bar, or is it one the prune drops
    before choosing a burst?"""
    return all(name in columns and not _missing(bar.get(name))
               for name in CHECKLIST_COLUMNS)


def _bar_width(bar) -> float | None:
    """One bar's high-low span as a percentage of its close, unrounded, or None.

    None -- never 0 -- when the envelope cannot be read: a missing High or
    Low, a close that is not a positive number, or a High below its own Low,
    which is not a bar at all. That is the rule `H` applies to a close
    outside its own range and the one src.ledger._open_within_its_bar()
    applies to an entry price, and the reason is the same in all three
    places: a number computed from a bar that cannot be read is a fabricated
    measurement, and 0.0 is the most confident fabrication available.

    A bar whose High EQUALS its Low is 0.0% here and not null. `H` refuses
    such a bar because it is being asked whether the close was strong and a
    bar with no range cannot say; this is being asked how wide the bar was,
    and "no width" is the answer rather than a failure to measure one.

    UNROUNDED, unlike everything else in this module, and it is the one
    measurement that may be: nobody is shown this number. It is shown as
    `bar_range_pct` (rounded once, below) and averaged into the expansion's
    denominator (rounded once, there). Rounding here would round twice on
    the second path -- which is exactly the defect that made 8 of 9 rows the
    pipeline had written disagree with the `N` line beside them.
    """
    high, low = _finite(bar.get("High")), _finite(bar.get("Low"))
    close = _finite(bar.get("Close"))
    if high is None or low is None or close is None or close <= 0 or high < low:
        return None
    return (high - low) / close * 100


def _bar_range_pct(bar) -> float | None:
    """`_bar_width()` at the tenth of a percent it is printed at.

    Rounded once, for the reason every measurement in this module is: a
    number decided at one precision and shown at another is how -4.04% came
    to be refused under a note stating -4.0%.
    """
    width = _bar_width(bar)
    return None if width is None else round(width, 1)


def burst_bar_shape(df: pd.DataFrame) -> dict:
    """The burst bar itself: the gap it opened on, how wide it was, and how
    that width compares with the base it came out of.

    THE MODEL WAS ASKED TO JUDGE A BAR IT COULD NOT SEE. knowledge/strategy.md
    asks for a "powerful burst bar" with a big range and names a huge gap as
    the Episodic Pivot signal, and the metrics block carried no open, no high
    and no low -- only the close, the gain, the volume and where in its range
    the bar closed. Reproduced through the real Candidate path before this
    existed: a +7.5% gap into a bar 0.9% wide, and a flat open with a 9.4%
    intraday range, on the same close, the same gain, the same volume and the
    same `H`, produced BYTE-IDENTICAL requests. (Those are the two frames
    tests/test_lynch.py builds; the numbers here are what they publish.) The difference lived in the
    chart image alone -- and on a night the render fails, `chart_seen` is
    False and it lived nowhere.

    Three measurements and no rule. Nothing here refuses a burst, moves the
    pass count or enters the fingerprint (see BURST_BAR_KEYS); the archive
    keeps them beside the forward returns so the record can one day be asked
    whether a gapped burst and a wide-range burst pay differently.

      gap_pct          the open against the previous session's close -- the
                       overnight move a reader of an 18:16 ET email has
                       already missed, measured off the same two closes the
                       scan's own gain_pct is measured off.
      bar_range_pct    high minus low over the close: how wide the day was.
      range_expansion  that width over the mean width of the consolidation
                       the checklist already names -- WINDOWS["tight_sessions"]
                       sessions, `N`'s own window, deliberately not a second
                       one, and `N`'s own arithmetic: the ratio is the width
                       over the %/day the `N` line in the same request
                       prints, so a reader cannot recompute it from the two
                       numbers in front of him and get a third. A burst bar
                       three times the width of the shelf it came out of is
                       the "big range" the rulebook asks for, stated relative
                       to the stock rather than in absolute percent, which is
                       the same move step 4 made for volume.

    NULL, NEVER 0, wherever a measurement could not be made -- the rule round 9
    settled for the open basis (F1/L4). An open outside its own bar's high and
    low is not a print anybody paid, so it is not a gap either; a bar whose
    envelope cannot be read has no width; and a base with no readable bar
    behind it has no norm to expand against.

    ALL THREE ARE NULL WHEN THE LAST BAR HANDED OVER IS NOT ONE THE CHECKLIST
    COULD GRADE. `evaluate_2lynch()` drops every bar missing any of
    CHECKLIST_COLUMNS and calls the last row left the burst, so on a frame
    whose last bar has no Open it grades the session BEFORE -- and these three
    would have described the session after it, in the same request, under a
    rulebook sentence telling the model to read the width beside `H`.
    Reproduced: a bar closing at 98% of its own range reached the model as
    `bar_range_pct 9.4` beside "closed at 50% of day's range", which is the
    previous day.

    The CALLER does not reach that branch any more, and what it does instead
    is the better answer: extra_context() anchors on the graded bar and hands
    over the frame cut there, so these three describe the bar `H` describes
    and step back with it rather than going null. The rule stays stated here
    because it is this function's own contract -- a caller handing over an
    unanchored frame must not be given a measurement of a bar nobody graded --
    and a test plants exactly that frame.
    """
    out: dict = {key: None for key in BURST_BAR_KEYS}
    if len(df) == 0:
        return out
    burst = df.iloc[-1]
    if not _read_by_the_checklist(burst, df.columns):
        return out

    # The gap is measured off the bar BEFORE the burst in the frame this was
    # handed, which is the bar src.scanner.detect_setup() measures gain_pct
    # against -- one denominator, so the two numbers in the payload cannot
    # describe two different previous sessions. That holds because
    # extra_context() hands over the Close/Volume-cleaned frame, which is
    # detect_setup()'s own cleaning (src.scanner._measurable): handed `raw`
    # instead, a readable close under an unreadable volume becomes the
    # denominator and the payload reads gain 8.0% beside gap 21.7%.
    prev_close = _finite(df["Close"].iloc[-2]) if len(df) >= 2 and "Close" in df else None
    open_ = _finite(burst.get("Open"))
    high, low = _finite(burst.get("High")), _finite(burst.get("Low"))
    if (open_ is not None and open_ > 0 and prev_close is not None and prev_close > 0
            and high is not None and low is not None and low <= open_ <= high):
        out["gap_pct"] = round((open_ / prev_close - 1) * 100, 1)

    bar_range = _bar_range_pct(burst)
    out["bar_range_pct"] = bar_range
    if bar_range is not None:
        # The last `tight_sessions` bars before the burst this can measure a
        # width from, which is `N`'s window and not the last
        # `tight_sessions` ROWS: `N` averages the bars carrying a high, a low
        # and a close, and reaching past a bar it skipped would make the
        # denominator a different set from the number printed beside it.
        # (A bar with no Open used to be excluded HERE and included by `N`,
        # under a comment claiming the opposite, until `N`'s own window
        # started counting the fields it reads.) Walked backwards so a long
        # history costs seven rows rather than all of them.
        base: list[float] = []
        for i in range(len(df) - 2, -1, -1):
            measured = _bar_width(df.iloc[i])
            if measured is not None:
                base.append(measured)
                if len(base) == WINDOWS["tight_sessions"]:
                    break
        # THE NUMBER `N` PRINTS, arrived at `N`'s way: the mean of the raw
        # widths, rounded once, to the tenth it is shown at. This was the
        # mean of the widths each already rounded -- a different number, and
        # 8 of the 9 rows the pipeline had written disagreed with the `N`
        # line in the same request: "pre-burst range 1.0%/day" beside a 9.5%
        # bar published as 9.37x, where the reader recomputing it gets 9.5x.
        #
        # A pandas mean, and NOT math.fsum, which is the one place in this
        # repo that argument does not hold. src.ledger.mean_returns() uses
        # fsum because nothing else computes that mean and the two
        # interpreters disagreed on it; here `N` computes the same mean --
        # `.mean()` over a float64 Series of the same seven widths -- and
        # that is the copy the reader is shown. fsum is the more accurate of
        # the two and differs from it by an ULP on frames that exist: the
        # seven lows in tests/test_lynch.py's FSUM_SHELF_LOWS put the exact
        # mean at 2.3499999999999992, which `N` prints as 2.4 and fsum rounds
        # to 2.3. Being right by an ULP while disagreeing with the printed
        # number is the defect this whole change is about. The builtin sum()
        # is out for the reason mean_returns() names: CPython 3.12 made it
        # compensated, so it answers 2.4 there and 2.3 on this sandbox's
        # 3.11, and a published number must not depend on which interpreter
        # measured it.
        # OLDEST FIRST, the order `N`'s own slice is in: a float mean is
        # order-dependent, and reversed this walk answers 2.3 on the shelf
        # above where `N` prints 2.4 -- the same disagreement by another
        # door.
        norm = (round(float(pd.Series(base[::-1], dtype=float).mean()), 1)
                if base else 0.0)
        if norm > 0:
            # The ratio is taken from the number the model is SHOWN, the same
            # rule `N` follows for its own tightness, so a reader cannot
            # recompute the ratio from the printed width and get another
            # answer -- whenever the two windows hold the same bars, which is
            # every frame but one whose base carries a bar `N` reads and this
            # cannot measure (a High under its own Low, a non-positive
            # close), where `N` averages the fabricated width and this skips
            # the bar.
            out["range_expansion"] = round(bar_range / norm, 2)
    return out


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
    # WHICH BARS A MEASUREMENT COUNTS IS DECIDED BY THE FIELDS THAT
    # MEASUREMENT READS, and by nothing else. The closes (2, L, Y, C's move,
    # and Bonde's two below) count every bar carrying a close; the ranges (N,
    # and C's own width) count every bar carrying a high, a low and a close;
    # all five fields are needed only to BE the bar graded -- the burst H
    # judges and the prior day C judges, which are asked for a whole bar's
    # geometry and its volume.
    #
    # All six used to read one five-field frame, and on a base whose largest
    # single session was +2.5% two missing Highs made check 2 report "2 prior
    # 4% bursts" -- the rule this product is named after, refusing a candidate
    # on days that do not exist -- while Y measured 22 sessions under the name
    # of 20 and read +52.6% for +45.2%. The round that fixed those three left
    # the RANGES pruned on five fields, and two shelf bars losing only their
    # Open moved N from "1.7%/day = 0.43x its norm" to "2.3%/day = 0.58x".
    # This is the rule _base() has applied to Bonde's two measurements since
    # the 3.3 audit found the same disagreement between two functions; it is
    # every reading in this one now.
    raw = df
    graded = _carrying(raw, CHECKLIST_COLUMNS)
    df = raw.iloc[graded]
    burst = df.iloc[-1]
    # ...and every series is read up to and including THAT bar, so the six
    # checks, the veto and the base breakdown never describe two different
    # sessions in one request: the prune can take the NEWEST bar, and then H
    # grades the session before it while an unanchored close-only reading
    # measures "through today's burst" on the bar after.
    through = _through(raw, graded[-1])
    closes = _series(through, "Close")
    base = closes.iloc[:-1]
    # Every bar before the burst, holes included -- the frame the range
    # windows below are measured over, each pruned for what it reads.
    pre = through.iloc[:-1]

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
    rets = base.pct_change().iloc[-WINDOWS["prior_burst_lookback"]:] * 100
    prior_bursts = int((rets >= PRIOR_BURST_PCT).sum())
    checks["2_first_or_second_burst"] = {
        "pass": prior_bursts <= MAX_PRIOR_BURSTS,
        "value": (f"{prior_bursts} prior {PRIOR_BURST_PCT:g}% bursts in last "
                  f"{WINDOWS['prior_burst_lookback']} days"),
    }

    # ---- L: shape AND direction of the prior move (log-price fit) ----
    # The slope is half the answer. Judged on R² alone this check passed a
    # smooth 45% collapse with R²=1.00 and reported "R²=1.00 over prior 30
    # days" to the scorer, telling Claude the structure was orderly without
    # telling it the structure was orderly *downwards*.
    #
    # THE FIT STOPS WHERE THE CONSOLIDATION STARTS, and it did not used to.
    # Bonde's L is the linearity of the PRIOR MOVE -- "first leg is consistent
    # and persistent buying" -- which is the advance INTO the base, not the
    # base. The window ended on the session before the burst, so for any
    # consolidation longer than about ten sessions the fit was mostly the
    # consolidation, and this check was measuring the one stretch of chart it
    # is not about. Reproduced on the textbook shape rather than argued: a
    # clean +0.6%/day advance followed by a shallow orderly pullback and a 4%
    # burst passed L at a 10-session base and failed it at 15, at 17 (which is
    # the base length in Bonde's own worked example: "preceding the breakout
    # for 17 days the stock did not have a momentum burst, did not have a 4%
    # breakdown, had a series of narrow range days"), and at every length
    # beyond. At a 30-session base it failed with R²=1.00 -- a perfect fit of
    # the base, reported as a non-linear prior move. The better and longer the
    # consolidation, the more certainly L refused it, which is backwards.
    #
    # The skip is `tight_sessions` and NOT a number of its own, because it is
    # the same question that window already answers -- which sessions are the
    # consolidation -- and two names for one question is how this file's own
    # notes describe a mechanism growing two vocabularies. (Where two windows
    # answer DIFFERENT questions, as `volume_norm_sessions` and
    # ScanConfig.rvol_lookback do, they are named apart and held equal by a
    # test. That is the opposite case and this is not it.)
    #
    # KNOWN LIMIT, written down rather than hidden: a consolidation longer
    # than the skip still bleeds into the window. On the same shape the fit
    # recovers a 17-session base and still fails a 25-session one. Detecting
    # the base's real length is the fix for that, and it is not this change.
    skip = WINDOWS["tight_sessions"]
    stepped_past = len(base) >= skip + 3      # 3 points is the least _log_trend can fit
    prior_move = base.iloc[:-skip] if stepped_past else base
    log_closes = np.log(prior_move.iloc[-WINDOWS["linear_fit_sessions"]:].to_numpy(dtype=float))
    slope, r2 = _log_trend(log_closes)
    r2 = shown(r2, 2)
    fitted_move = shown((float(np.exp(slope * max(len(log_closes) - 1, 0))) - 1) * 100, 1)
    checks["L_linear_prior_move"] = {
        "pass": bool(r2 >= MIN_LINEAR_R2 and slope >= MIN_LINEAR_SLOPE),
        # The window is INTERPOLATED, not typed: it was spelled "30 days" here
        # and 30 in WINDOWS, so a change to one told the model the other. The
        # second clause says which sessions were fitted, because "over prior
        # 30 days" is what the old line said while it was fitting the base,
        # and a reader could not have told.
        "value": (f"R²={r2:.2f}, fitted trend {fitted_move:+.1f}% over "
                  f"{WINDOWS['linear_fit_sessions']} days ending "
                  + (f"{skip} sessions before the burst" if stepped_past
                     else "the day before the burst (too little history to step past the base)")),
    }

    # ---- Y: young trend — not extended, measured through the burst day ----
    # Both halves used to run off `pre`, so the burst was invisible to the
    # only risk/reward guardrail in the checklist: a +35% gap-up scored the
    # same "-0.5% vs 20SMA" as the quiet day it gapped away from. Extension
    # is a fact about the price you would pay, which is today's close.
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
            f"{run_up_text}, {ext_vs_sma20:+.1f}% vs {WINDOWS['sma_sessions']}SMA"
            " (through today's burst)"
        ),
    }

    # ---- N: narrow consolidation over the 5-10 days pre-burst ----
    # Every bar with a high, a low and a close, by RANGE_COLUMNS' rule: a bar
    # whose Open or Volume the feed dropped has a range N can measure, and
    # dropping it slid both windows a session back.
    daily_range = _ranges(pre)
    recent_range = daily_range.iloc[-WINDOWS["tight_sessions"]:].mean()
    norm_range = (daily_range.iloc[-WINDOWS["norm_sessions"]:-WINDOWS["tight_sessions"]].mean()
                  if len(daily_range) > WINDOWS["norm_sessions"] + WINDOWS["tight_sessions"]
                  else daily_range.mean())
    recent_range = shown(recent_range, 1)
    tightness = shown(recent_range / norm_range, 2) if norm_range else 9.9
    checks["N_narrow_consolidation"] = {
        "pass": tightness <= MAX_TIGHTNESS,
        "value": f"pre-burst range {recent_range:.1f}%/day = {tightness:.2f}x its norm",
    }

    # ---- C: calm day immediately before the burst ----
    # C NAMES ONE SESSION, so it needs that session's bar. `pre.iloc[-1]` off
    # the five-field frame is the newest bar the prune LEFT, which is a
    # different session whenever the day before the burst carried a close and
    # a volume and lost its Open, its High or its Low -- and the scan lets
    # that through, since src.scanner._measurable() prunes on Close and
    # Volume alone, so _drop_gapped_symbols() sees that bar as the previous
    # session and detect_setup() measures the gain against it. Reproduced
    # through those gates: a 3.5% prior day on 3x volume with a NaN High was
    # thrown away and C reported "prior day 0.0% move ... 1.00x volume" about
    # the quiet day before it, turning a FAIL into a PASS on 51% of 600
    # frames, in a row whose `prev_volume` is the real prior day's.
    #
    # The session before the burst is the one before it in the CLOSES -- the
    # last session that printed one, which is the session detect_setup()
    # measured its gain against. When that session is not a bar this check
    # can grade, C says so, the way `H` does for a burst bar it cannot read,
    # rather than silently grading an older day under the words "prior day".
    d1_at = len(closes) - 2
    printed_a_close = _carrying(through, ("Close",))
    judgeable = (len(graded) >= 2 and d1_at >= 0
                 and graded[-2] == printed_a_close[d1_at])
    if not judgeable:
        checks["C_calm_preburst_day"] = {
            "pass": False,
            "value": ("no usable bar for the session before the burst; "
                      "nothing to judge as the calm day"),
        }
    else:
        d1 = through.iloc[graded[-2]]
        d1_range = shown((d1["High"] - d1["Low"]) / d1["Close"] * 100, 1)
        # The sessions before d1, not counting d1: a day cannot be quiet
        # against a baseline it is itself part of. Every bar that printed a
        # volume, by _series()'s rule -- the average is a volume reading, so
        # it counts the bars carrying a volume.
        d1_norm = _series(_through(through, graded[-2] - 1), "Volume").iloc[
            -WINDOWS["volume_norm_sessions"]:].mean()
        d1_vol_ratio = shown(d1["Volume"] / d1_norm, 2)
        # d1's own move is a close-to-close reading, so it comes off the
        # closes and not off the bars: the BAR C judges has to carry all five
        # fields, but the session it moved FROM need not, and a pct_change()
        # over the pruned frame spanned any hole between the two and called
        # two sessions of drift one quiet day -- the same merge as check 2's,
        # on the check whose threshold is 2%.
        d1_move = shown(abs(_move_into(closes, d1_at)) * 100, 1)
        # The range was measured and printed but left out of the verdict, so a
        # day that closed unchanged after a 15%-wide swing counted as "calm".
        # Judged against the stock's own norm, reusing N's baseline and
        # multiple rather than inventing a second constant. When there is no
        # usable norm the line says so: N's `else 9.9` sentinel prints "9.90x
        # its norm" for a range it never managed to measure, and that string
        # goes to Claude.
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
    #
    # Anchored, like every other reading here. Handed the whole frame it
    # counted the graded burst itself as one of the up days the rule refuses
    # buying INTO -- the one thing consecutive_up_days()'s own docstring says
    # this must not do -- whenever the newest bar was one the checklist could
    # not grade: reproduced on a candidate two up days into a burst, refused
    # by an absolute rule for a run of three, one of which was the bar being
    # judged.
    up_run = consecutive_up_days(through)
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
    # Anchored for the same reason, and it moved a verdict the same way: on a
    # frame whose newest bar the checklist could not grade, the 20-session
    # window slid one session past a -5.6% day and told the model "worst base
    # day +0.0% ... no break" through quality_notes.
    worst = worst_base_day(through)
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

    `raw` is kept for the same reason evaluate_2lynch() keeps one: every
    measurement here has its own rule about which bars count, and handing
    them a frame this function pruned for its own purposes made the number
    sent to the model disagree with the verdict the veto reached from it.
    """
    raw = df
    # THE BAR THE CHECKLIST GRADES, not this function's own newest bar.
    # evaluate_2lynch() prunes on all five fields and calls the last row left
    # the burst; this prunes on Close and Volume, because burst_bar_shape()
    # needs the gain's own denominator -- so a newest bar carrying a close
    # and a volume and missing an Open, a High or a Low was graded by none of
    # the six checks and was still the anchor for the four readings below and
    # for Bonde's two, while burst_bar_shape(), three keys further down this
    # same dict, correctly refused to describe it. Reproduced: -0.6% off the
    # year's high for a bar the checklist never read, beside a null gap
    # saying it had not read it. One request, one bar.
    priced_at = _carrying(raw, ("Close", "Volume"))
    graded = graded_bar_at(raw)
    # No bar carries all five, so there is no bar the checklist grades and
    # nothing to anchor on but this function's own newest readable bar --
    # which is what every reading here came off before the anchor existed.
    anchor = graded if graded is not None else int(priced_at[-1])
    through = _through(raw, anchor)
    # ...and the frame burst_bar_shape() reads is that same cleaning, cut at
    # the same bar: its last row is the bar the checklist grades and the row
    # before it is the close detect_setup() measured the gain against.
    priced = raw.iloc[priced_at[priced_at <= anchor]]
    close = float(priced["Close"].iloc[-1])
    # Every window here is read from WINDOWS, and each length guard from the
    # same key as the slice it guards: 63 was spelled twice with two meanings
    # (the index, and the history it needs), so moving the window alone left
    # its own guard stale.
    # ...and every window here counts the bars that carry the field IT reads,
    # by _series()'s rule, not the bars that carry Close AND Volume. This
    # function prunes on both because burst_bar_shape() needs both; the two
    # performance readings are one close over another and the 52-week
    # extremes are a high and a low, so a bar whose Volume the feed dropped
    # was slid out of all four windows by a field none of them reads.
    # Reproduced on a steadily rising frame: one missing Volume moved
    # perf_3mo_pct from +28.1% to +28.6% and perf_6mo_pct from +64.7% to
    # +65.4%, under the keys knowledge/strategy.md names to the model as this
    # name's relative strength.
    highs, lows, all_closes = (_series(through, "High"), _series(through, "Low"),
                               _series(through, "Close"))
    high_low = WINDOWS["high_low_sessions"]
    hi_52w = (float(highs.iloc[-high_low:].max())
              if len(highs) >= WINDOWS["high_low_min_sessions"] else float(highs.max()))
    lo_52w = (float(lows.iloc[-high_low:].min())
              if len(lows) >= WINDOWS["high_low_min_sessions"] else float(lows.min()))
    three, six = WINDOWS["perf_3mo_sessions"], WINDOWS["perf_6mo_sessions"]
    perf_3mo = ((close / float(all_closes.iloc[-three]) - 1) * 100
                if len(all_closes) > three else None)
    perf_6mo = ((close / float(all_closes.iloc[-six]) - 1) * 100
                if len(all_closes) > six else None)
    # The NUMBERS behind Bonde's two rules. Their verdicts travel separately --
    # the veto through failed_vetoes(), the base breakdown through
    # evaluate_2lynch()'s context_checks -- and these are the measurements
    # themselves, which the archive keeps. `consecutive_up_days` is
    # the veto's own measurement, reported for the same reason a passed check
    # reports its value -- 0 up days and 2 are both allowed and are not the
    # same setup -- and because the archive keeps this block, so the evidence
    # views can one day ask whether either number separates the winners.
    worst = worst_base_day(through)
    return {
        "pct_off_52w_high": round((close / hi_52w - 1) * 100, 1),
        "pct_above_52w_low": round((close / lo_52w - 1) * 100, 1),
        "consecutive_up_days": consecutive_up_days(through),
        "worst_base_day_pct": worst,
        # None, not "n/a": these land in docs/data.json, whose contract is
        # "numbers are numbers or null" — a string sentinel in a numeric field
        # forces every consumer to special-case it.
        "perf_3mo_pct": round(perf_3mo, 1) if perf_3mo is not None else None,
        "perf_6mo_pct": round(perf_6mo, 1) if perf_6mo is not None else None,
        # The burst bar's own shape -- the one thing in the metrics block the
        # model was asked to judge and given no number for. Measured off the
        # Close-and-Volume cleaning rather than `raw` so the gap's denominator
        # is the previous close the scan's gain_pct used; see
        # burst_bar_shape().
        **burst_bar_shape(priced),
    }
