"""Dated Stockbee research measurements from the bars the scan already fetched.

This sidecar does not select the production shortlist or call a data service.
The canonical scan follows Stockbee's 2015 >=100,000-share version
(MIN_SHARE_VOLUME); anticipation is an explicit SpicyStock numeric proxy for
the chart study in his process.
"""
from __future__ import annotations

from datetime import date, timedelta
from math import isfinite
import re

import pandas as pd

SCAN_LIMIT = 40
DOLLAR_LIMIT = 40
ANTICIPATION_LIMIT = 25
#: Bonde's OTHER daily scan, and the one his own words point at a universe
#: like this repo's. "Dollar breakout is another way to find range expansion on
#: higher priced stocks that move in 5 to 50 dollar move but may not have 4%
#: b/o on first day of momentum burst"; the scan "looks for a stock up 90 cents
#: plus ... more useful on high priced stocks above 40 as they do not often
#: breakout with 4% move" ("My process loop to trade 4% b/o and $ b/o", 2017).
#:
#: THREE THINGS THAT ARE NOT THE 4% SCAN, each deliberate on his part:
#:   * the move is CLOSE MINUS OPEN -- the day's own body -- so the overnight
#:     gap is excluded, where the 4% scan measures close against the previous
#:     close and includes it;
#:   * there is no volume-versus-yesterday term, only the same 100,000-share
#:     floor;
#:   * it is an ABSOLUTE move in dollars, so it does not scale with price,
#:     which is the whole point: a $4 move on a $200 stock is 2%.
#: The "above 40" is his guidance on where it is useful, not a term of the
#: scan, and neither rendering of the formula carries a price floor -- so
#: none is applied here and every row archives its close, which is what lets
#: a reader split the population later without the rule having guessed.
DOLLAR_BREAKOUT_MOVE = 0.90
MIN_SHARE_VOLUME = 100000
#: The 4% scan's own two numbers, named rather than spelled inside _scan():
#: `c/c1 >= 1.04` and the mirror `c/c1 <= 0.96` the breadth count reads.
#: Named because the record averages this section's rows across runs
#: (evidence.stockbee), so a threshold moved here is a second scan under one
#: label unless the rules fingerprint can see it -- and because the validator
#: below reads a row against the numbers ITS RECORD archived, which have to
#: be a value the record can carry and not a literal inside a predicate.
SCAN_GAIN_RATIO = 1.04
SCAN_DROP_RATIO = 0.96
#: Which of this module's numbers are STRATEGY (they decide what a row is,
#: and so which population a setup lands in) and which are PLUMBING (how many
#: rows a section archives, how many bars a series keeps). The fingerprint in
#: src.pipeline carries the first list and not the second, for the reason
#: ScanConfig keeps the same split: a cap moved from 40 to 60 changes no
#: verdict about any name, and a threshold moved by a cent changes every
#: mean the record publishes over this section. A test asserts every
#: upper-case numeric constant here is in exactly one list, so a number
#: added later cannot arrive uncategorised and escape the fingerprint in
#: silence.
STRATEGY_CONSTANTS = ("SCAN_GAIN_RATIO", "SCAN_DROP_RATIO", "MIN_SHARE_VOLUME",
                      "DOLLAR_BREAKOUT_MOVE")
PLUMBING_CONSTANTS = ("SCAN_LIMIT", "DOLLAR_LIMIT", "ANTICIPATION_LIMIT", "SERIES_LIMIT")
#: Every row-bearing section and how many rows it archives. ONE list, because
#: a hand-kept copy of it went stale three separate ways on the commit that
#: added the third section: the ledger's slimmer stopped dropping `series`
#: from it (which alone put 29 MB on the projected year), the contract
#: walker's numeric exemption stopped covering it, and this validator had to
#: name it twice. src.ledger derives SIDECAR_SECTIONS from these keys.
SECTION_LIMITS = {"scan": SCAN_LIMIT, "dollar": DOLLAR_LIMIT,
                  "anticipation": ANTICIPATION_LIMIT}
#: Sections a record written before them will not carry, and whose absence is
#: therefore not a fault. `scan` and `anticipation` have been in every record
#: the sidecar ever wrote.
OPTIONAL_SECTIONS = frozenset({"dollar"})
SERIES_LIMIT = 30
FIELDS = ("open", "high", "low", "close", "volume")
#: The archived rule numbers each section's rows are re-derived under by
#: problem(). Anticipation is deliberately absent: its predicate reads seven
#: measurements a row carries only in part (the prior three sessions' volume
#: and the day's own change are read off the series, which an archived row
#: no longer holds), so re-deriving it would check a different rule from the
#: one that ran.
RULE_NUMBERS = {"scan": ("min_gain_ratio", "min_volume"),
                "dollar": ("min_dollar_move", "min_volume")}
#: Sections whose rows a record declares disjoint from another section, and
#: from which. problem() holds an archived row to the declaration ITS OWN
#: record made -- never to today's chain -- for the reason the scan's rules
#: are read that way. Anticipation's own predicate cannot be re-derived from
#: an archived row (it reads the prior three sessions' volume and 67 sessions
#: of range off a series the ledger drops), but the section it is declared
#: disjoint FROM can be, so the declaration is checkable even where the
#: predicate is not.
DISJOINT_DECLARATIONS = {"anticipation": [("excludes_current_dollar_matches", "dollar"),
                                          ("excludes_current_4pct_scan_matches", "scan")]}
#: What the scan section's rows were selected BY, archived with them. The
#: validator reads a row against these -- the numbers its own record carries
#: -- and never against the module's constants, because a record checked
#: against today's constants is a record that stops loading the day a
#: constant moves: reproduced on the committed ledger, where raising
#: MIN_SHARE_VOLUME set every run aside as unreadable and left docs/data.json
#: refused, after nothing about the record had changed. A record from before
#: this block existed carries none and is not re-derived at all, since a
#: rule the record did not archive is not one the validator can know.
SCAN_RULES = {
    "kind": "Stockbee 4% breakout, the 2015 >=100,000-share version",
    "min_gain_ratio": SCAN_GAIN_RATIO,
    "measured": "close / previous session close",
    "volume_above_previous": True,
    "min_volume": MIN_SHARE_VOLUME,
    "min_price": None,
}
#: ONE DRIFT FROM THE QUOTED FORMULA, stated here the way the 4% scan's is.
#: The source writes `c-o >= .90 and v > 100000` -- strict on volume -- and
#: this reads it inclusive, so a bar on exactly 100,000 shares is admitted.
#: The same inclusive reading is applied to the 4% scan's own floor, and the
#: two must agree or the sections would disagree about one number; a bar on
#: the boundary is pinned in tests beside the 89.99/89.49-cent cases.
DOLLAR_RULES = {
    "kind": "Stockbee $ breakout, his companion scan for higher-priced names",
    "min_dollar_move": DOLLAR_BREAKOUT_MOVE,
    "measured": "close - open",
    "min_volume": MIN_SHARE_VOLUME,
    "min_price": None,
    "his_guidance": "more useful on high priced stocks above 40, which do not often break out 4%",
    "excludes_current_4pct_scan_matches": True,
}
ANTICIPATION_RULES = {
    "kind": "SpicyStock numeric proxy; manual chart review required",
    "min_price": 3,
    "min_prior_three_volume": 100000,
    "min_trend_intensity": 1.05,
    "max_abs_day_change_pct": 1,
    "max_compression_ratio": 0.75,
    "min_contiguous_sessions": 67,
    "excludes_current_4pct_scan_matches": True,
    # AND the $ breakout, since round 14 put that section ahead of this one in
    # build()'s chain. It is a real exclusion and not a tidy-up: a high-priced
    # name can gap down and close inside the +-1% band on a $0.90 body, which
    # satisfies both predicates, and that is exactly the cohort the $ scan was
    # built for. Reproduced rather than argued -- a 6-session tight shelf on a
    # $200 name, gapping down $1.20 and closing +0.5%, passes _anticipates()
    # and _dollar_breakout() together and build() files it under `dollar`
    # alone. The section moved 200 rows to 191 on the history fixture the day
    # that landed and nothing said so; a record written before this key is
    # absent it, which is how a reader tells the two definitions apart.
    "excludes_current_dollar_matches": True,
}
#: Bonde's OWN qualifying checklist, letter by letter, as five independent
#: sources render it -- his 27 Sep 2024 thread, contemporaneous bootcamp notes
#: taken in his own class, two third-party reimplementations and a paid course
#: that translates it. It is reproduced here because `src/lynch.py` implements
#: a checklist under the SAME six letters that means different things by three
#: of them, and a comparison needs both statements written down in one repo.
#:
#: Bonde                                    what src/lynch.py calls it
#:   2  not up two days in a row            a VETO at three or more
#:   L  linearity of the prior move         L (the same rule)
#:   Y  young trend: first or second        `2`
#:      breakout from consolidation
#:   N  narrow range OR negative day        `C`
#:      immediately before the breakout
#:   C  consolidation quality: shallow,     `N`, plus the non-voting
#:      orderly, compact, low volume,       base-breakdown criterion
#:      no more than ONE 4% breakdown
#:   H  close near the high of the day      H (the same rule)
#:
#: `src/lynch.py`'s `Y` -- distance above the 20-day average and the month's
#: run-up -- has no counterpart in this list at all. It is a real risk measure
#: and it is this repo's, not his.
#:
#: TWO SCOPES THAT ARE EASY TO LOSE. He states 2LYNCH for CONTINUATION setups
#: only ("2LYNCH is for only continuation setups. Every setup I trade has its
#: own qualifying checklist"), and he adds "+CV" -- Catalyst, and Volume at
#: 1.5-2x the 50-day average -- when the consolidation runs beyond about a
#: month. That second one matters here: `ScanConfig.min_rvol` is 1.5x a
#: 50-session average, which is his V, applied by this repo as an
#: unconditional SCAN gate rather than as a criterion for one kind of base.
#:
#: UNVERIFIED AGAINST THE PRIMARY SOURCE, like every other number in this
#: repo's reading of Bonde: stockbee.blogspot.com is refused by this sandbox's
#: egress proxy, so the wording above comes from the sources named and not from
#: his blog.
QUALIFYING_RULES = {
    "name": "2LYNCH",
    "scope": "continuation setups; every other setup he trades has its own checklist",
    "2": "not up two days in a row into the breakout; a small up day under 1% before it is fine",
    "L": "linearity of the prior move",
    "Y": "young trend: the first or second breakout out of the consolidation",
    "N": "a narrow-range day or a negative day immediately before the breakout",
    "C": "consolidation quality: shallow, orderly, compact, low volume, no more than one 4% breakdown",
    "H": "the close near the high of the day",
    "extension": "+CV for a consolidation beyond about a month: a Catalyst, and Volume at 1.5-2x the 50-day average",
}

#: What `qualify()` compares each measurement against. Three of these are
#: Bonde's own numbers (the 1% up day, the one 4% breakdown, first-or-second);
#: `close_near_high` and `compact_base` are the same bars `src/lynch.py`
#: already applies, so promoting this checklist later cannot move them by
#: accident; and `narrow_range_ratio` is the one number NOBODY states, which
#: is why it is named here and called a proxy rather than buried in a
#: comparison.
QUALIFYING_THRESHOLDS = {
    "small_up_day_pct": 1.0,       # Bonde: "a small up day of less than 1% before b/o is fine"
    "max_prior_bursts": 1,         # Bonde: first or second breakout
    "max_base_breakdowns": 1,      # Bonde: "no more than one 4% breakdown"
    "close_near_high": 0.70,       # top 30% of the day's range
    "compact_base": 1.0,           # the base tighter than the 60 sessions before it
    "narrow_range_ratio": 1.0,     # PROXY: the prior day no wider than the base's own mean bar
}

MEASUREMENT_RULES = {
    "scan": (f"close / previous session close >= {SCAN_GAIN_RATIO}; volume > previous session volume; "
             f"volume >= {MIN_SHARE_VOLUME}"),
    "dollar": (f"close - open >= {DOLLAR_BREAKOUT_MOVE:.2f} dollars; volume >= {MIN_SHARE_VOLUME}; "
               "no volume-versus-previous term and no price floor; disjoint from scan, so a name "
               "the 4% scan matched is not here"),
    "dollar_move": "close - open, in dollars rounded to cents, on every row and not only the dollar section's; the dollar scan compares this same rounded number",
    "breadth": (f"same volume rules as scan; up: close / previous close >= {SCAN_GAIN_RATIO}; "
                f"down: close / previous close <= {SCAN_DROP_RATIO}"),
    "breadth_ratios": "sum(up4) / sum(down4), only for a full 5 or 10 dated sessions with nonzero coverage on every day and a nonzero denominator; coverage may vary",
    "volume_vs_average": "current volume / mean volume of previous 20 contiguous sessions",
    "range_expansion": "current (high-low)/close / mean((high-low)/close) over previous 7 contiguous sessions",
    "compression_ratio": "mean((high-low)/close) over latest 7 sessions / mean((high-low)/close) over the preceding 60; 67 contiguous sessions required",
    "close_position": "(close-low)/(high-low), from 0 to 1; null for a zero range",
    "prior_up_days": "consecutive higher closes ending on the previous session; null if available history ends before the streak does",
    "trend_intensity": "mean(close) over latest 7 / mean(close) over latest 65, including current session",
    "prior_bursts_20": "canonical scan matches over previous 20 sessions; not the discretionary count of setups since a trend began",
    "base_down4_count": "close-to-close declines of at least 4% over previous 7 sessions, regardless of volume",
    "extension_sma20_pct": "100 * (current close / mean(close over latest 20 sessions) - 1)",
    "base_range_pct": "100 * (highest high - lowest low over previous 7 sessions) / previous close",
    "prior_day_move_pct": "previous session close-to-close change in percent",
    "prior_day_range_pct": "100 * (previous high - previous low) / previous close",
    "calendar": "scanner previous-session decision for current day; cross-frame observed calendar for history, with any printed immediately preceding weekday retained; missing bars are not bridged",
}


def _day(value) -> date | None:
    if isinstance(value, (int, float, bool)) or value is None:
        return None
    try:
        stamp = pd.Timestamp(value)
        return None if pd.isna(stamp) else stamp.date()
    except (TypeError, ValueError, OverflowError):
        return None


def _number(value) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
        return number if isfinite(number) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _valid_bar(values) -> bool:
    return (all(values.get(k) is not None for k in FIELDS)
            and all(values[k] > 0 for k in ("open", "high", "low", "close"))
            and values["volume"] >= 0
            and values["low"] <= min(values["open"], values["close"])
            and values["high"] >= max(values["open"], values["close"]))


def _bars(frame, through: date) -> dict:
    """Retain invalid dates as holes; never silently shift a lookback over one."""
    if not isinstance(frame, pd.DataFrame):
        return {}
    # scanner._download_batch supplies title-case OHLCV. Also accept lowercase
    # frames at the pure measurement boundary, but never choose between two
    # columns that claim to be the same field.
    aliases = {}
    for column in frame.columns:
        key = str(column).lower()
        if key in FIELDS:
            if key in aliases:
                return {}
            aliases[key] = column
    if not set(FIELDS).issubset(aliases):
        return {}
    columns = [aliases[key] for key in FIELDS]
    out = {}
    for stamp, values in zip(frame.index, frame.loc[:, columns].itertuples(index=False, name=None)):
        day = _day(stamp)
        if day is None or day > through or day.weekday() >= 5:
            continue
        if day in out:
            out[day] = None  # A second daily bar is ambiguous; the scanner normally deduplicates first.
            continue
        bar = dict(zip(FIELDS, (_number(value) for value in values)))
        out[day] = {"date": day.isoformat(), **bar} if _valid_bar(bar) else None
    return out


def _weekday_before(day: date) -> date:
    day -= timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def _scan(bar, previous, *, down=False, min_ratio=None, max_ratio=None,
          min_volume=None) -> bool:
    """Bonde's 4% scan over one bar and the one before it.

    The thresholds are parameters so the validator can apply the numbers a
    RECORD archived rather than the ones this module holds tonight; the
    defaults are read at call time, not bound at definition, so a constant
    patched in a test is the constant every default caller applies.
    """
    min_ratio = SCAN_GAIN_RATIO if min_ratio is None else min_ratio
    max_ratio = SCAN_DROP_RATIO if max_ratio is None else max_ratio
    min_volume = MIN_SHARE_VOLUME if min_volume is None else min_volume
    ratio = bar["close"] / previous["close"]
    return ((ratio <= max_ratio if down else ratio >= min_ratio)
            and bar["volume"] > previous["volume"] and bar["volume"] >= min_volume)


def _dollar_move(bar) -> float:
    """The day's body in dollars, ROUNDED TO CENTS exactly once.

    A price difference is a number of cents, and Bonde's scan is written for
    a platform whose prices are quoted in them. Rounding here is not
    cosmetic: 23.90 - 23.00 is 0.8999999999999986 in binary floating point,
    so an unrounded compare refuses a bar whose body is ninety cents by every
    reading a person can make of it -- and `dollar_move` is archived on every
    row and printed, so the record would show $0.90 beside a refusal.

    That is the rounding class this project has already closed twice, in
    worst_base_day() and in burst_bar_shape(): round ONCE, and let the
    verdict and the line read the same number. Rounding a second time
    downstream is the other half of it, so nothing else rounds this.
    """
    return round(bar["close"] - bar["open"], 2)


def _dollar_breakout(bar, *, min_move=None, min_volume=None) -> bool:
    """Bonde's $ breakout: the day's own body, in dollars, on 100k shares.

    One bar and no previous one, because there is no volume-versus-yesterday
    term in this scan and the move is measured inside the session. See
    DOLLAR_BREAKOUT_MOVE for why each of those differs from the 4% scan. The
    thresholds are parameters for the reason _scan()'s are.
    """
    min_move = DOLLAR_BREAKOUT_MOVE if min_move is None else min_move
    min_volume = MIN_SHARE_VOLUME if min_volume is None else min_volume
    return _dollar_move(bar) >= min_move and bar["volume"] >= min_volume


def _mean(values) -> float:
    return sum(values) / len(values)


def _divide(top, bottom):
    return top / bottom if bottom else None


def _row(ticker: str, history: list[dict]) -> dict:
    current, previous = history[-1], history[-2]
    close = current["close"]
    normalized = [(bar["high"] - bar["low"]) / bar["close"] for bar in history]
    range_expansion = (_divide(normalized[-1], _mean(normalized[-8:-1]))
                       if len(history) >= 8 else None)
    compression = (_divide(_mean(normalized[-7:]), _mean(normalized[-67:-7]))
                   if len(history) >= 67 else None)
    streak = 0
    for at in range(len(history) - 2, 0, -1):
        if history[at]["close"] <= history[at - 1]["close"]:
            break
        streak += 1
    else:
        streak = None
    base = history[-8:-1] if len(history) >= 8 else None
    return {
        "ticker": ticker, **current, "prev_close": previous["close"],
        "prev_volume": previous["volume"],
        "gain_pct": (close / previous["close"] - 1) * 100,
        # The $ scan's own measurement, on EVERY row and not only the ones it
        # matched: it is what lets a reader ask "how much of the day's move
        # was the body?" of a 4% match, and it is the number the dollar
        # section sorts on. close - open, so the overnight gap is out, and
        # it is the SAME rounded number _dollar_breakout() decided on.
        "dollar_move": _dollar_move(current),
        "volume_vs_previous": _divide(current["volume"], previous["volume"]),
        "volume_vs_average": (_divide(current["volume"], _mean([b["volume"] for b in history[-21:-1]]))
                              if len(history) >= 21 else None),
        "range_expansion": range_expansion,
        "compression_ratio": compression,
        "close_position": _divide(close - current["low"], current["high"] - current["low"]),
        "prior_up_days": streak,
        "trend_intensity": (_mean([b["close"] for b in history[-7:]]) /
                            _mean([b["close"] for b in history[-65:]]) if len(history) >= 65 else None),
        "prior_bursts_20": (sum(_scan(history[at], history[at - 1])
                                for at in range(len(history) - 21, len(history) - 1))
                            if len(history) >= 22 else None),
        "base_down4_count": (sum(history[at]["close"] / history[at - 1]["close"] <= 0.96
                                 for at in range(len(history) - 8, len(history) - 1))
                             if len(history) >= 9 else None),
        "extension_sma20_pct": ((close / _mean([b["close"] for b in history[-20:]]) - 1) * 100
                                if len(history) >= 20 else None),
        "base_range_pct": ((max(b["high"] for b in base) - min(b["low"] for b in base)) /
                           previous["close"] * 100 if base else None),
        "prior_day_move_pct": ((previous["close"] / history[-3]["close"] - 1) * 100
                               if len(history) >= 3 else None),
        "prior_day_range_pct": normalized[-2] * 100,
        "series": history[-SERIES_LIMIT:],
    }


def qualify(row) -> dict:
    """Bonde's 2LYNCH over one canonical scan row.

    Five of the six are computable from a row `_row()` produced. **`L` is not,
    and it returns None rather than a guess**: linearity is a fit over the
    prior move, the row carries no fit, and `trend_intensity` is a different
    measurement (where price sits, not how straight the path was). Reporting
    five and saying so beats reporting six with one invented, which is the
    shape this repo's notes call a confidently false sentence.

    Every verdict is `True`, `False`, or None for "this row cannot say", and
    the caller is expected to keep those three apart -- a null is not a fail.
    `passes` and `measured` are returned beside the letters so a caller never
    has to decide what None counts as.

    The one number here that nobody states is the narrow arm of `N`. Bonde
    says "narrow range day OR negative day"; negative is unambiguous and
    narrow is not, so narrow is measured against the base's own mean bar width
    -- the same shape of comparison `src/lynch.py` makes for its own tightness
    rule -- and `QUALIFYING_THRESHOLDS` names it a proxy.
    """
    def verdict(value, test):
        return None if value is None else bool(test(value))

    t = QUALIFYING_THRESHOLDS
    ups, prior_move = row.get("prior_up_days"), row.get("prior_day_move_pct")
    # "Not up two days in a row", with his own exception for a trivial up day.
    # A run this row could not measure (the series ends inside the streak) is
    # None, because a streak that ran off the end of the history is unknown
    # and not zero.
    if ups is None:
        two = None
    elif ups < 2:
        two = True
    else:
        two = (prior_move is not None and prior_move < t["small_up_day_pct"])

    # N and C combine two arms each, and an arm can be unknown, so both follow
    # three-valued logic rather than treating None as a fail. The two shapes
    # are NOT symmetric and writing them the same way is wrong both times:
    #   N is an OR -- an arm that failed while the other is unknown leaves the
    #     whole check unknown, because the unknown arm could still carry it.
    #   C is an AND -- an arm that failed decides the check, whatever the
    #     other one says, so an unknown beside a fail is still a fail.
    # The first version of this function had both backwards, which asserted a
    # failed `N` it could not establish and withheld a `C` it could.
    narrow = _narrow_prior_day(row)
    negative = None if prior_move is None else prior_move <= 0
    if negative is True or narrow is True:
        n = True
    elif negative is False and narrow is False:
        n = False
    else:
        n = None

    breakdowns, compression = row.get("base_down4_count"), row.get("compression_ratio")
    arms = [None if breakdowns is None else breakdowns <= t["max_base_breakdowns"],
            None if compression is None else compression <= t["compact_base"]]
    if False in arms:
        c = False
    elif None in arms:
        c = None
    else:
        c = True

    checks = {
        "2": two,
        "L": None,
        "Y": verdict(row.get("prior_bursts_20"), lambda v: v <= t["max_prior_bursts"]),
        "N": n,
        "C": c,
        "H": verdict(row.get("close_position"), lambda v: v >= t["close_near_high"]),
    }
    return {"checks": checks,
            "passes": sum(1 for v in checks.values() if v is True),
            "measured": sum(1 for v in checks.values() if v is not None),
            "unmeasured": sorted(k for k, v in checks.items() if v is None)}


def _narrow_prior_day(row):
    """Was the session before the breakout a narrow bar for this name?

    Measured against the base's OWN mean width rather than an absolute
    percentage, because "narrow" for a name that ranges 8% a day is not narrow
    for one that ranges 1%. The base is the bars before the previous session,
    read off the row's own `series`; too short a series answers None.
    """
    series = row.get("series")
    if not isinstance(series, list) or len(series) < 4:
        return None
    widths = []
    for bar in series[:-1]:            # everything before the breakout bar
        try:
            width = (bar["high"] - bar["low"]) / bar["close"]
        except (KeyError, TypeError, ZeroDivisionError):
            return None
        if not isfinite(width):
            return None
        widths.append(width)
    prior, base = widths[-1], widths[:-1]
    if not base:
        return None
    norm = _mean(base)
    if not isfinite(norm) or norm <= 0:
        return None
    return prior / norm <= QUALIFYING_THRESHOLDS["narrow_range_ratio"]


def _anticipates(row, history) -> bool:
    """SpicyStock's numeric proxy for the anticipation chart study.

    Every number here is read off ANTICIPATION_RULES, which the record
    archives with the section: the same dict spelled its thresholds and this
    function spelled them again as literals until the post-merge audit of
    round 14, which is the two-spellings class round 11 closed for the
    checklist's windows -- a rule the record states and the code applies
    from a second copy can disagree without any test noticing.
    """
    r = ANTICIPATION_RULES
    band = r["max_abs_day_change_pct"] / 100
    return (len(history) >= r["min_contiguous_sessions"] and row["close"] >= r["min_price"]
            and min(b["volume"] for b in history[-4:-1]) >= r["min_prior_three_volume"]
            and row["trend_intensity"] >= r["min_trend_intensity"]
            and 1 - band <= history[-1]["close"] / history[-2]["close"] <= 1 + band
            and row["compression_ratio"] is not None
            and row["compression_ratio"] <= r["max_compression_ratio"])


def build(frames: dict, session, *, requested: int, label: str,
          previous_session=None, calendar=None) -> dict | None:
    """Build optional research metadata without network or production-rule changes.

    Calendar dates are inferred from the basket, not an exchange calendar. The
    existing scanner decides the current prior session, including its holiday
    consensus. Historical holes reduce coverage instead of becoming two-day moves.
    """
    session = _day(session)
    if not frames or session is None:
        return None
    histories = {str(ticker): _bars(frame, session) for ticker, frame in frames.items()}
    if not any(histories.values()):
        return None
    printed = {day for history in histories.values() for day in history}
    supplied = {_day(day) for day in (calendar or [])}
    sessions = sorted(day for day in (supplied or printed) if day is not None and day <= session and day.weekday() < 5)
    if session not in sessions:
        sessions.append(session)
    prior = {}
    for day in sessions:
        arithmetic = _weekday_before(day)
        observed = [value for value in sessions if value < day]
        prior[day] = arithmetic if arithmetic in printed or not observed else observed[-1]
    current_previous = _day(previous_session)
    if current_previous is not None and current_previous < session:
        prior[session] = current_previous
    elif not calendar:
        prior[session] = _weekday_before(session)

    # Without cross-frame agreement, weekdays remain conservative: a lone name
    # cannot establish a closure using the very hole we are trying to detect.
    if not calendar:
        prior.update({day: _weekday_before(day) for day in sessions if day != session})
    scan_rows, dollar_rows, anticipation_rows = [], [], []
    measured = 0
    for ticker, bars in histories.items():
        history, day = [], session
        while bars.get(day):
            history.append(bars[day])
            day = prior.get(day, _weekday_before(day))
        history.reverse()
        if len(history) < 2:
            continue
        measured += 1
        row = _row(ticker, history)
        if _scan(history[-1], history[-2]):
            scan_rows.append(row)
        elif _dollar_breakout(history[-1]):
            # DISJOINT FROM THE 4% SCAN, and that is the question rather than
            # tidiness: the two overlap on any high-priced name that moved 4%,
            # and a row archived in both would be one event counted twice in a
            # control that compares populations. What this section holds is
            # therefore "$ breakouts the 4% scan did not already match" --
            # which is exactly the cohort Bonde built the $ scan FOR -- and
            # `matched` counts that disjoint set, not his raw $ b/o count.
            dollar_rows.append(row)
        elif _anticipates(row, history):
            anticipation_rows.append(row)
    scan_rows.sort(key=lambda row: (-row["gain_pct"], row["ticker"]))
    dollar_rows.sort(key=lambda row: (-row["dollar_move"], row["ticker"]))
    anticipation_rows.sort(key=lambda row: (row["compression_ratio"], -row["trend_intensity"], row["ticker"]))
    days = []
    for day in sessions[-10:]:
        pairs = [(bars[day], bars[prior[day]]) for bars in histories.values()
                 if bars.get(day) and bars.get(prior[day])]
        days.append({"date": day.isoformat(), "measured": len(pairs),
                     "up4": sum(_scan(bar, previous) for bar, previous in pairs),
                     "down4": sum(_scan(bar, previous, down=True) for bar, previous in pairs)})
    ratios = {}
    for window in (5, 10):
        rows = days[-window:]
        ratios[f"d{window}"] = (_divide(sum(day["up4"] for day in rows), sum(day["down4"] for day in rows))
                                  if len(rows) == window and all(day["measured"] > 0 for day in rows) else None)
    return {
        "version": 1, "date": session.isoformat(),
        "scope": {"label": label, "requested": requested, "measured": measured, "whole_market": False},
        "scan": {"matched": len(scan_rows), "shown": min(SCAN_LIMIT, len(scan_rows)),
                 "rows": scan_rows[:SCAN_LIMIT], "rules": dict(SCAN_RULES)},
        "dollar": {"matched": len(dollar_rows), "shown": min(DOLLAR_LIMIT, len(dollar_rows)),
                   "rows": dollar_rows[:DOLLAR_LIMIT], "rules": dict(DOLLAR_RULES)},
        "anticipation": {"matched": len(anticipation_rows), "shown": min(ANTICIPATION_LIMIT, len(anticipation_rows)),
                         "rows": anticipation_rows[:ANTICIPATION_LIMIT], "rules": dict(ANTICIPATION_RULES)},
        "breadth": {"days": days, "ratios": ratios},
        "measurement_rules": dict(MEASUREMENT_RULES),
    }


def problem(block, *, session=None, archived=False) -> str | None:
    """Validate the bounded optional metadata before a persisted record is read."""
    def number(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)

    def count(value):
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0

    if not isinstance(block, dict) or type(block.get("version")) is not int or block["version"] != 1:
        return "stockbee.version must be 1"
    day = _day(block.get("date"))
    run_day = _day(session)
    # Legacy run dates can be unreadable without invalidating the record; the
    # existing history layer reports that uncertainty. Require agreement when
    # the run has a readable date, and keep the sidecar's own date strict.
    if day is None or block["date"] != day.isoformat() or (run_day is not None and run_day != day):
        return "stockbee.date must match its run"
    scope = block.get("scope")
    if (not isinstance(scope, dict) or not isinstance(scope.get("label"), str)
            or scope.get("whole_market") is not False
            or not count(scope.get("requested")) or not count(scope.get("measured"))
            or scope["measured"] > scope["requested"]):
        return "stockbee.scope must identify the measured basket"
    # THE NUMBERS A ROW IS CHECKED AGAINST ARE THE RECORD'S OWN. Each section
    # archives the rules that selected its rows, and a row is re-derived
    # under those -- never under this module's constants, which describe
    # tonight's scan and not the one that wrote the record. Reproduced on
    # the committed ledger before this changed: MIN_SHARE_VOLUME raised to
    # 1,000,000 set every run aside as unreadable and refused docs/data.json,
    # with nothing about either file changed. A section from before its
    # rules were archived carries none and its rows are not re-derived at
    # all; a `rules` block that is present and does not name its numbers is a
    # shape no writer produces and is refused.
    archived_rules = {}
    for key, names in RULE_NUMBERS.items():
        section = block.get(key)
        if not isinstance(section, dict) or "rules" not in section:
            continue
        rules = section["rules"]
        if not isinstance(rules, dict) or not all(number(rules.get(name)) for name in names):
            return f"stockbee.{key} rules must name the numbers its rows were selected by"
        archived_rules[key] = {name: rules[name] for name in names}
    scan_rules, dollar_rules = archived_rules.get("scan"), archived_rules.get("dollar")
    for key, limit in SECTION_LIMITS.items():
        if key not in block and key in OPTIONAL_SECTIONS:
            continue  # a record from before that section was measured
        section = block.get(key)
        if (not isinstance(section, dict) or not isinstance(section.get("rows"), list)
                or not count(section.get("matched")) or not count(section.get("shown"))
                or section["shown"] != len(section["rows"]) or section["shown"] > limit
                or not section["shown"] <= section["matched"] <= scope["measured"]):
            return f"stockbee.{key} must contain bounded rows and matching counts"
        tickers = set()
        for row in section["rows"]:
            if (not isinstance(row, dict) or not isinstance(row.get("ticker"), str)
                    or not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]{0,14}", row["ticker"])
                    or row["ticker"] in tickers or row.get("date") != block["date"]):
                return f"stockbee.{key} row identity is invalid"
            tickers.add(row["ticker"])
            if any(value is not None and not number(value) for name, value in row.items()
                   if name not in ("ticker", "date", "series", "forward_returns")):
                return f"stockbee.{key} row metrics must be numbers or null"
            # A measured row carries the same forward_returns block a pick
            # does, filled by the same Ledger.fill_forward_returns() off the
            # same bars, and is checked by the SAME rule rather than a second
            # copy of it: a shape rule stated twice is how this project has
            # repeatedly found one surface checking a level the other does
            # not. Absent is a row from before the sidecar was measured.
            # Imported here because src.ledger imports this module.
            from .ledger import returns_shape_problem
            if "forward_returns" in row and not isinstance(row["forward_returns"], dict):
                return f"stockbee.{key} row forward_returns must be an object"
            if returns_shape_problem(row.get("forward_returns")):
                return f"stockbee.{key} row forward_returns must be a measured block"
            values = {key: _number(row.get(key)) for key in FIELDS}
            previous = {"close": _number(row.get("prev_close")), "volume": _number(row.get("prev_volume"))}
            if (not _valid_bar(values) or previous["close"] is None or previous["close"] <= 0
                    or previous["volume"] is None or previous["volume"] < 0):
                return f"stockbee.{key} row has invalid OHLCV"
            if key == "scan" and scan_rules and not _scan(
                    values, previous, min_ratio=scan_rules["min_gain_ratio"],
                    min_volume=scan_rules["min_volume"]):
                return "stockbee.scan row does not meet the rules its record archived"
            if key == "dollar" and dollar_rules and not _dollar_breakout(
                    values, min_move=dollar_rules["min_dollar_move"],
                    min_volume=dollar_rules["min_volume"]):
                return "stockbee.dollar row does not meet the rules its record archived"
            # Disjoint from the 4% scan AS THAT RECORD RAN IT: a dollar row
            # the archived scan rules would have matched is a row moved
            # between the two populations the control compares. Not checked
            # when the record archived no scan rules, for the reason above.
            if key == "dollar" and scan_rules and _scan(
                    values, previous, min_ratio=scan_rules["min_gain_ratio"],
                    min_volume=scan_rules["min_volume"]):
                return "stockbee.dollar row is a match of the 4% scan its record archived"
            # And the declarations a section makes about what it excludes. A
            # record that says its anticipation rows hold no $ breakout is
            # held to that; one that never said it is not re-derived at all.
            for flag, other in DISJOINT_DECLARATIONS.get(key, []):
                rules = section.get("rules")
                if not isinstance(rules, dict) or rules.get(flag) is not True:
                    continue
                if other == "dollar" and dollar_rules and _dollar_breakout(
                        values, min_move=dollar_rules["min_dollar_move"],
                        min_volume=dollar_rules["min_volume"]):
                    return f"stockbee.{key} row is a $ breakout its record declared excluded"
                if other == "scan" and scan_rules and _scan(
                        values, previous, min_ratio=scan_rules["min_gain_ratio"],
                        min_volume=scan_rules["min_volume"]):
                    return f"stockbee.{key} row is a 4% match its record declared excluded"
            series = row.get("series")
            if series is None and archived:
                continue
            if not isinstance(series, list) or not 2 <= len(series) <= SERIES_LIMIT:
                return f"stockbee.{key} series must contain bounded daily bars"
            dates = []
            for bar in series:
                if not isinstance(bar, dict) or not _valid_bar({k: _number(bar.get(k)) for k in FIELDS}):
                    return f"stockbee.{key} series has invalid OHLCV"
                stamp = _day(bar.get("date"))
                if stamp is None or stamp > day:
                    return f"stockbee.{key} series has invalid dates"
                dates.append(stamp)
            if dates != sorted(set(dates)) or dates[-1] != day:
                return f"stockbee.{key} series must end on its recorded session"
    breadth = block.get("breadth")
    if not isinstance(breadth, dict) or not isinstance(breadth.get("days"), list) or len(breadth["days"]) > 10:
        return "stockbee.breadth must contain at most 10 dated counts"
    dates = []
    for row in breadth["days"]:
        if not isinstance(row, dict):
            return "stockbee.breadth day must be an object"
        stamp = _day(row.get("date"))
        if (stamp is None or stamp > day or any(not count(row.get(k)) for k in ("measured", "up4", "down4"))
                or row["up4"] + row["down4"] > row["measured"] or row["measured"] > scope["requested"]):
            return "stockbee.breadth day must contain measured counts"
        dates.append(stamp)
    if dates != sorted(set(dates)):
        return "stockbee.breadth days must be unique and ordered"
    ratios = breadth.get("ratios")
    if not isinstance(ratios, dict) or any(ratios.get(k) is not None and (not number(ratios[k]) or ratios[k] < 0) for k in ("d5", "d10")):
        return "stockbee.breadth ratios must be nonnegative numbers or null"
    if not isinstance(block["anticipation"].get("rules"), dict) or not isinstance(block.get("measurement_rules"), dict):
        return "stockbee measurement rules must be recorded"
    if "dollar" in block and not isinstance(block["dollar"].get("rules"), dict):
        return "stockbee measurement rules must be recorded"
    return None
