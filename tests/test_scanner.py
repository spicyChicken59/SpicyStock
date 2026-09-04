"""Layer 1 -- the burst detector, the Alpaca request, and freshness.

The scan filter's thresholds ARE asserted now (step 4). Every boundary is
read off ScanConfig rather than written out as a number, so retuning one does
not silently rewrite what is under test, and every rejection test first proves
that the rule it names is the only one failing -- see _only_failing().
"""

from __future__ import annotations

import json
import pathlib
import re
import time
from datetime import date, datetime, time as time_of_day, timedelta, timezone

import pytest
import requests
from alpaca.common.exceptions import APIError
from alpaca.data.enums import Adjustment, DataFeed
from requests.exceptions import HTTPError

from src.scanner import (
    MARKET_TZ,
    SESSION_COMPLETE_ET,
    Candidate,
    CredentialsRejectedError,
    FeedNotAuthorizedError,
    IncompleteScanError,
    ScanConfig,
    StaleDataError,
    SymbolFileError,
    apply_liquidity_gate,
    current_session,
    detect_setup,
    get_clients,
    get_universe,
    liquidity_floor,
    run_scan,
    session_dollar_volume,
    session_has_closed,
    trailing_volume_mean,
)
from src.scanner import _SYMBOL_RE


def test_flat_series_is_not_a_setup(ohlcv):
    assert detect_setup(ohlcv("flat"), ScanConfig()) is None


def test_obvious_burst_is_detected(ohlcv):
    result = detect_setup(ohlcv("burst"), ScanConfig())
    assert isinstance(result, dict)


def test_detected_setup_has_the_fields_candidate_needs(ohlcv):
    """detect_setup()'s dict is splatted straight into Candidate(**m)."""
    result = detect_setup(ohlcv("burst"), ScanConfig())
    cand = Candidate(ticker="AAA", history=ohlcv("burst"), **result)
    assert cand.ticker == "AAA"
    assert cand.gain_pct > 0
    assert cand.volume > 0
    assert cand.close > 0
    assert isinstance(cand.date, str)


@pytest.mark.parametrize("kind", ["flat", "base", "choppy"])
def test_quiet_kinds_are_never_setups(kind, ohlcv):
    assert detect_setup(ohlcv(kind), ScanConfig()) is None


def test_too_short_a_history_is_not_a_setup(ohlcv):
    assert detect_setup(ohlcv("burst").iloc[-1:], ScanConfig()) is None


def test_get_clients_needs_no_key_and_no_network(fake_alpaca):
    """The real client raises ValueError on empty credentials; the double is
    what lets the rest of the suite run with an empty environment."""
    get_clients()
    assert len(fake_alpaca.data_clients) == 1


def test_run_scan_over_a_given_universe(fake_alpaca, ohlcv):
    fake_alpaca.add_history("BURST", ohlcv("burst"))
    fake_alpaca.add_history("QUIET", ohlcv("flat"))
    fake_alpaca.add_history("WALK", ohlcv("base"))

    candidates = run_scan(ScanConfig(), universe=["BURST", "QUIET", "WALK"])

    assert fake_alpaca.bar_requests, "the mocked data client was never asked for bars"
    assert [c.ticker for c in candidates] == ["BURST"]
    assert candidates[0].history is not None
    assert list(candidates[0].history.columns[:5]) == ["Open", "High", "Low", "Close", "Volume"]


def test_run_scan_survives_a_symbol_with_no_bars(fake_alpaca, ohlcv):
    """A delisted ticker returns nothing from Alpaca; it must be skipped, not
    crash the scan."""
    fake_alpaca.add_history("BURST", ohlcv("burst"))
    candidates = run_scan(ScanConfig(), universe=["BURST", "GONE"])
    assert [c.ticker for c in candidates] == ["BURST"]


# --- the rejection paths ----------------------------------------------------
#
# Rewritten twice. The first version set today's volume to prev-1, which was
# also below the old 5,000,000-share floor, so the rejection it observed was
# rule 3's and not rule 2's -- rule 1, the 4% gain the product is named after,
# could be deleted with the suite green. The second version asserted a couple
# of hand-picked inequalities per test, which is the same discipline done by
# eye.
#
# _only_failing() now recomputes every per-symbol rule from ScanConfig and
# names the ones that fail. Each test asserts EXACTLY the rule it is about is
# failing before asserting the rejection, so a test cannot pass on a rule it
# did not intend to break. The helper is a precondition, never the assertion
# under test: the thing under test is always detect_setup()'s own verdict.

RULES = ("1_gain", "2_vs_prev_day", "3_rvol", "5_price")


def _rule_status(frame, cfg: ScanConfig) -> dict[str, bool]:
    """Which of detect_setup's per-symbol rules does this frame pass?"""
    df = frame.dropna(subset=["Close", "Volume"])
    close, prev_close = float(df["Close"].iloc[-1]), float(df["Close"].iloc[-2])
    vol, prev_vol = float(df["Volume"].iloc[-1]), float(df["Volume"].iloc[-2])
    avg = trailing_volume_mean(df, cfg)
    return {
        "1_gain": (close / prev_close - 1) * 100 >= cfg.min_gain_pct,
        "2_vs_prev_day": vol >= prev_vol,
        "3_rvol": avg is not None and vol / avg >= cfg.min_rvol,
        "5_price": close > cfg.min_price,
    }


def _only_failing(frame, cfg: ScanConfig) -> set[str]:
    return {name for name, ok in _rule_status(frame, cfg).items() if not ok}


def _passing(ohlcv, **kwargs):
    """A frame that clears every per-symbol rule, for a test to break one of."""
    frame = ohlcv("burst", **kwargs).copy()
    cfg = ScanConfig()
    assert _only_failing(frame, cfg) == set(), "the baseline frame must pass every rule"
    assert detect_setup(frame, cfg) is not None, "the baseline frame must pass every rule"
    return frame


def _set_volume(frame, *, today=None, prev=None):
    """Set the last and/or second-to-last bar's volume, in place, returning it."""
    col = frame.columns.get_loc("Volume")
    if prev is not None:
        frame.iloc[-2, col] = float(prev)
    if today is not None:
        frame.iloc[-1, col] = float(today)
    return frame


def _set_rvol(frame, cfg: ScanConfig, rvol: float):
    """Make today's volume exactly `rvol` x the trailing average.

    Yesterday is pulled down with it, because rule 2 rejects a day below the
    previous one and would otherwise be the rule that fires. Yesterday is set
    first: it sits INSIDE the trailing window, so the average has to be read
    after it moves, not before.
    """
    _set_volume(frame, prev=1.0)
    avg = trailing_volume_mean(frame, cfg)
    _set_volume(frame, today=rvol * avg)
    return frame


def _scale(frame, *, price=1.0, volume=1.0):
    """Rescale the whole frame's prices and/or volumes.

    Every rule except the price floor is a ratio, so scaling either axis
    uniformly is exactly what a different feed, or a different share count for
    the same company, looks like.
    """
    out = frame.copy()
    for col in ("Open", "High", "Low", "Close"):
        out[col] = out[col] * price
    out["Volume"] = out["Volume"] * volume
    return out


def test_rule1_a_gain_below_the_threshold_is_rejected(ohlcv):
    """The 4% gain. Deleting this rule used to leave the suite green."""
    cfg = ScanConfig()
    frame = _passing(ohlcv)
    prev_close = float(frame["Close"].iloc[-2])
    # A quarter of the threshold, with the price still clear of the floor.
    frame.iloc[-1, frame.columns.get_loc("Close")] = prev_close * (1 + cfg.min_gain_pct / 400)
    assert _only_failing(frame, cfg) == {"1_gain"}
    assert detect_setup(frame, cfg) is None


def test_rule2_volume_below_the_previous_day_is_rejected(ohlcv):
    cfg = ScanConfig()
    frame = _passing(ohlcv)
    # Yesterday lifted above today, both far above the trailing average so the
    # relative-volume rule cannot be the one that fires.
    today = float(frame["Volume"].iloc[-1])
    _set_volume(frame, prev=today * 1.01)
    assert _only_failing(frame, cfg) == {"2_vs_prev_day"}
    assert detect_setup(frame, cfg) is None


def test_rule5_price_at_or_below_the_floor_is_rejected(ohlcv):
    cfg = ScanConfig()
    frame = _passing(ohlcv)
    frame = _scale(frame, price=cfg.min_price / float(frame["Close"].iloc[-1]))
    assert _only_failing(frame, cfg) == {"5_price"}
    assert detect_setup(frame, cfg) is None


def test_a_zero_previous_close_cannot_divide(ohlcv):
    frame = _passing(ohlcv)
    frame.iloc[-2, frame.columns.get_loc("Close")] = 0.0
    assert detect_setup(frame, ScanConfig()) is None


# The inclusive edges of rules 1 and 2 (step 6b). Rule 3's is asserted below
# and rule 5's is asserted above -- the price floor is the one rule of the
# five that is deliberately exclusive, and only a test that lands exactly on
# each line can tell the two kinds apart.


def test_rule1_a_gain_exactly_at_the_threshold_is_kept(ohlcv):
    """4.0% up IS a 4% burst. The strategy is named after this number, and
    `>=` quietly becoming `>` would drop every name that printed it exactly.
    """
    cfg = ScanConfig()
    frame = _passing(ohlcv)
    prev_close = float(frame["Close"].iloc[-2])
    frame.iloc[-1, frame.columns.get_loc("Close")] = prev_close * (1 + cfg.min_gain_pct / 100)
    assert _only_failing(frame, cfg) == set()

    result = detect_setup(frame, cfg)
    assert result is not None
    assert result["gain_pct"] == pytest.approx(cfg.min_gain_pct, abs=0.01)


def test_rule2_volume_exactly_equal_to_the_previous_day_is_kept(ohlcv):
    """Rule 2 asks for volume that did not FALL. Equal is not a fall.

    Yesterday is lifted to today rather than today dropped to yesterday: the
    burst day carries the volume rule 3 needs, and levelling down would put
    the frame under the relative-volume threshold instead, which is the
    substitution `_only_failing` exists to catch.
    """
    cfg = ScanConfig()
    frame = _passing(ohlcv)
    _set_volume(frame, prev=float(frame["Volume"].iloc[-1]))
    assert _only_failing(frame, cfg) == set()

    result = detect_setup(frame, cfg)
    assert result is not None
    assert result["volume"] == result["prev_volume"]


# =====================================================================
# Step 4, rule 3 -- volume against the stock's own norm
#
# The rule this replaced was `volume > 5,000,000 shares`, which measures the
# feed and the share count rather than the stock: a $180 leader doing 4.9M
# shares (~$880M) failed it and a $4.50 laggard doing 6M (~$27M) passed. Every
# test here reads its boundary off ScanConfig rather than naming a number, so
# retuning min_rvol does not silently rewrite what is asserted.
# =====================================================================


def test_rule3_volume_below_the_relative_threshold_is_rejected(ohlcv):
    cfg = ScanConfig()
    frame = _set_rvol(_passing(ohlcv), cfg, cfg.min_rvol * 0.5)
    assert _only_failing(frame, cfg) == {"3_rvol"}
    assert detect_setup(frame, cfg) is None


def test_rule3_volume_exactly_at_the_relative_threshold_is_kept(ohlcv):
    """The boundary is inclusive; a name is not dropped for landing on it."""
    cfg = ScanConfig()
    frame = _set_rvol(_passing(ohlcv), cfg, cfg.min_rvol)
    assert _only_failing(frame, cfg) == set()
    result = detect_setup(frame, cfg)
    assert result is not None
    assert result["volume_ratio"] == pytest.approx(cfg.min_rvol, abs=0.01)


def test_rule3_measures_the_trailing_average_and_not_yesterday(ohlcv):
    """The two ratios disagree, and only one of them may decide.

    Yesterday was itself a quiet day, so today is comfortably above it while
    being ordinary against the stock's own norm. Under the vs-yesterday
    reading this is a 4x volume expansion; under the rule it is below average
    participation, which is what strategy.md calls a kill.
    """
    cfg = ScanConfig()
    frame = _passing(ohlcv)
    _set_volume(frame, prev=trailing_volume_mean(frame, cfg) * 0.2)
    _set_volume(frame, today=trailing_volume_mean(frame, cfg) * 0.8)

    assert float(frame["Volume"].iloc[-1]) / float(frame["Volume"].iloc[-2]) > 3.5, (
        "vs yesterday this is a large expansion; vs its own norm it is a quiet day")
    assert _only_failing(frame, cfg) == {"3_rvol"}
    assert detect_setup(frame, cfg) is None


def test_a_liquid_leader_under_five_million_shares_is_now_a_candidate(ohlcv):
    """The headline case. ~$180 a share on 4.9M shares -- about $880M traded,
    among the most liquid names in any US universe -- was rejected outright by
    the absolute floor for being 100,000 shares short of it."""
    cfg = ScanConfig()
    frame = _passing(ohlcv)
    frame = _scale(frame, price=180.0 / float(frame["Close"].iloc[-1]),
                   volume=4_900_000 / float(frame["Volume"].iloc[-1]))

    assert float(frame["Volume"].iloc[-1]) < 5_000_000
    result = detect_setup(frame, cfg)
    assert result is not None, "a leader trading $880M/day is not an illiquid name"
    assert result["dollar_volume"] > 800_000_000


def test_a_cheap_name_on_a_big_share_count_no_longer_passes_on_the_count(ohlcv):
    """The other half of the inversion: $4.50 on 6M shares is ~$27M traded and
    an unremarkable day for the stock, and the share count alone used to admit
    it."""
    cfg = ScanConfig()
    frame = _passing(ohlcv)
    frame = _scale(frame, price=4.50 / float(frame["Close"].iloc[-1]))
    # A stock that normally trades ~5.5M shares, doing 6M today.
    frame["Volume"] = 5_500_000.0
    _set_volume(frame, prev=5_000_000, today=6_000_000)
    # 6M shares is over the old floor, and the day is still ordinary for it.
    assert float(frame["Volume"].iloc[-1]) > 5_000_000
    assert float(frame["Close"].iloc[-1]) * 6_000_000 < 30_000_000
    assert _only_failing(frame, cfg) == {"3_rvol"}
    assert detect_setup(frame, cfg) is None


def test_rule3_is_unchanged_by_a_feed_that_reports_a_fraction_of_the_tape(ohlcv):
    """Why the rule is a ratio at all.

    The free plan's IEX feed carries a few percent of consolidated volume. An
    absolute floor turns that into a different strategy; a ratio does not
    notice, because the same fraction is in the numerator and the denominator.
    """
    cfg = ScanConfig()
    frame = _passing(ohlcv)
    full_tape = detect_setup(frame, cfg)
    one_venue = detect_setup(_scale(frame, volume=0.03), cfg)

    assert full_tape is not None and one_venue is not None
    assert one_venue["volume_ratio"] == pytest.approx(full_tape["volume_ratio"], abs=0.01)
    assert one_venue["volume"] < 5_000_000 < full_tape["volume"]


# --- what the trailing average is, exactly ----------------------------------


def test_the_trailing_average_excludes_the_day_being_measured(ohlcv):
    """A burst inside its own denominator understates itself, by more the
    shorter the window -- so the ratio would mean a different thing at every
    lookback. Flat history, one spike: the average must be the flat value."""
    cfg = ScanConfig()
    frame = _passing(ohlcv)
    frame["Volume"] = 1_000_000.0
    _set_volume(frame, today=10_000_000.0)

    assert trailing_volume_mean(frame, cfg) == pytest.approx(1_000_000.0)
    assert detect_setup(frame, cfg)["volume_ratio"] == pytest.approx(10.0)


def test_the_trailing_window_is_the_one_src_lynch_already_uses(ohlcv):
    """src.lynch's C check divides the pre-burst day by
    `pre["Volume"].iloc[-51:-1].mean()`. Two layers of one pipeline reporting
    "volume vs average" against different windows is how a metric stops
    meaning anything, so this pins them to the same arithmetic."""
    cfg = ScanConfig()
    frame = _passing(ohlcv)
    assert cfg.rvol_lookback == 50
    lynch_window = frame["Volume"].iloc[-(cfg.rvol_lookback + 1):-1].mean()
    assert trailing_volume_mean(frame, cfg) == pytest.approx(float(lynch_window))


def test_a_name_with_no_usable_history_has_no_average_and_is_not_a_setup(ohlcv):
    """Three weeks of listing is volume without a norm. Averaging four
    sessions would let the thinnest baseline manufacture the biggest ratio."""
    cfg = ScanConfig()
    frame = _passing(ohlcv)
    short = frame.iloc[-(cfg.min_rvol_sessions):]      # one short of a window
    assert trailing_volume_mean(short, cfg) is None
    assert detect_setup(short, cfg) is None
    just_enough = frame.iloc[-(cfg.min_rvol_sessions + 1):]
    assert trailing_volume_mean(just_enough, cfg) is not None
    assert detect_setup(just_enough, cfg) is not None


def test_a_window_full_of_holes_does_not_count_as_history(ohlcv):
    """The guard counts sessions that reported a volume, not rows in the
    slice. Counting rows would let a window that is mostly gaps satisfy a
    check about how much history there is."""
    cfg = ScanConfig()
    frame = _passing(ohlcv)
    holes = frame.copy()
    col = holes.columns.get_loc("Volume")
    # Blank all but a handful of the trailing window, leaving the row count
    # untouched.
    holes.iloc[-(cfg.rvol_lookback + 1):-4, col] = float("nan")
    assert len(holes["Volume"].iloc[-(cfg.rvol_lookback + 1):-1]) > cfg.min_rvol_sessions
    assert trailing_volume_mean(holes, cfg) is None


def test_a_history_of_zero_volume_is_not_an_infinite_ratio(ohlcv):
    cfg = ScanConfig()
    frame = _passing(ohlcv)
    frame["Volume"] = 0.0
    _set_volume(frame, today=10_000_000.0)
    assert trailing_volume_mean(frame, cfg) is None
    assert detect_setup(frame, cfg) is None


# --- the field src.scorer sends to Claude -----------------------------------


def test_volume_ratio_is_the_trailing_average_ratio_not_the_previous_days(ohlcv):
    """src.scorer sends this number to Claude as volume-vs-50-day-average. It
    was vol/prev_volume, so every metrics block stated something about the
    candidate that was not true. The two must be far apart here, and the
    reported one must be the average."""
    cfg = ScanConfig()
    frame = _passing(ohlcv)
    # Yesterday moves first: it sits inside the trailing window, so the
    # average has to be read after it, not before.
    _set_volume(frame, prev=trailing_volume_mean(frame, cfg) * 0.25)
    avg = trailing_volume_mean(frame, cfg)
    _set_volume(frame, today=avg * 3.0)

    result = detect_setup(frame, cfg)
    assert result["volume_ratio"] == pytest.approx(3.0, abs=0.01)
    vs_yesterday = float(frame["Volume"].iloc[-1]) / float(frame["Volume"].iloc[-2])
    assert vs_yesterday > 10, "the two readings must be far apart for this to prove anything"
    assert result["volume_ratio"] != pytest.approx(vs_yesterday, abs=1.0)


def test_volume_ratio_carries_its_own_denominator(ohlcv):
    """avg_volume is the number volume_ratio was divided by, so the claim can
    be checked without the frame -- in the CSV, or in an email."""
    cfg = ScanConfig()
    result = detect_setup(_passing(ohlcv), cfg)
    assert result["volume"] / result["avg_volume"] == pytest.approx(result["volume_ratio"], abs=0.01)


def test_the_candidate_carries_the_ratio_and_its_denominator(ohlcv):
    """detect_setup()'s dict is splatted straight into Candidate(**m); a field
    added to one and not the other is a TypeError at scan time."""
    frame = _passing(ohlcv)
    cand = Candidate(ticker="AAA", history=frame, **detect_setup(frame, ScanConfig()))
    assert cand.volume_ratio > 1
    assert cand.avg_volume > 0


# =====================================================================
# Step 4, rule 6 -- dollar volume against the universe, not against a number
#
# Cross-sectional, so it cannot live in detect_setup(), which is handed one
# frame and cannot know what the rest of the market did. run_scan() is the
# only place that sees the whole scan.
# =====================================================================


def _thin(ohlcv, kind, *, price, volume, variant=0):
    """A frame at a chosen price and last-bar volume, for stocking a universe."""
    frame = ohlcv(kind, variant=variant).copy()
    return _scale(frame, price=price / float(frame["Close"].iloc[-1]),
                  volume=volume / float(frame["Volume"].iloc[-1]))


def test_the_liquidity_gate_drops_the_thinnest_burst_of_the_session(fake_alpaca, ohlcv):
    """Two bursts, identical but for the money that changes hands in them."""
    fake_alpaca.add_history("BIG", _thin(ohlcv, "burst", price=200.0, volume=5_000_000))
    fake_alpaca.add_history("TINY", _thin(ohlcv, "burst", price=5.0, volume=200_000, variant=1))
    for i in range(8):  # a universe to be ranked against
        fake_alpaca.add_history(f"Q{i}", _thin(ohlcv, "flat", price=80.0,
                                               volume=2_000_000, variant=i + 2))

    found = run_scan(ScanConfig(), universe=["BIG", "TINY"] + [f"Q{i}" for i in range(8)])

    assert [c.ticker for c in found] == ["BIG"]


def test_the_gate_ranks_a_candidate_against_the_universe_not_against_the_bursts(ohlcv):
    """The denominator is the whole scan, and it has to be.

    One candidate, unchanged, judged twice. Among thin names it is a liquid
    leader; among liquid ones it is the tail. Ranking bursts against each
    other instead would make the verdict depend on how many other names
    happened to burst that day -- on a one-burst day the bottom X% of one name
    is either everything or nothing.
    """
    cfg = ScanConfig()
    frame = _thin(ohlcv, "burst", price=50.0, volume=1_000_000)   # $50M/day
    cand = Candidate(ticker="MID", history=frame, **detect_setup(frame, cfg))

    thin_universe = [1e6 * (i + 1) for i in range(20)]            # $1M-$20M/day
    fat_universe = [1e9 * (i + 1) for i in range(20)]             # $1B-$20B/day

    assert [c.ticker for c in apply_liquidity_gate([cand], thin_universe, cfg)] == ["MID"]
    assert apply_liquidity_gate([cand], fat_universe, cfg) == []


def test_the_gate_survives_a_feed_that_reports_a_fraction_of_the_tape(ohlcv):
    """Why a percentile and not `$3M/day`. A feed carrying 3% of consolidated
    volume moves every dollar figure by the same factor and does not move the
    ranking, so the same names survive. An absolute floor would have to be
    retuned for every feed, and silently means a different strategy until it
    is."""
    cfg = ScanConfig()
    frame = _thin(ohlcv, "burst", price=50.0, volume=1_000_000)
    cand = Candidate(ticker="MID", history=frame, **detect_setup(frame, cfg))
    universe = [1e6 * (i + 1) for i in range(20)]

    full_tape = apply_liquidity_gate([cand], universe, cfg)
    one_venue = apply_liquidity_gate(
        [Candidate(ticker="MID", history=frame,
                   **detect_setup(_scale(frame, volume=0.03), cfg))],
        [v * 0.03 for v in universe], cfg,
    )
    assert [c.ticker for c in full_tape] == [c.ticker for c in one_venue] == ["MID"]


def test_the_gate_keeps_the_share_of_the_universe_it_says_it_keeps(ohlcv):
    """`min_dollar_volume_pctile` is read as "drop below this percentile", so
    a uniform spread of 100 names should lose about that many."""
    cfg = ScanConfig(min_dollar_volume_pctile=30.0)
    universe = [float(i + 1) * 1e6 for i in range(100)]
    cands = []
    for i, dv in enumerate(universe):
        frame = _thin(ohlcv, "burst", price=50.0, volume=dv / 50.0, variant=i)
        cands.append(Candidate(ticker=f"T{i}", history=frame, **detect_setup(frame, cfg)))
    kept = apply_liquidity_gate(cands, universe, cfg)
    assert 68 <= len(kept) <= 72


def test_the_gate_measures_a_name_against_the_same_number_it_reports(ohlcv):
    """The floor is built from session_dollar_volume() and compared against
    Candidate.dollar_volume, so those two have to BE the same number.

    They were not: the floor was unrounded and the candidate rounded, which
    put any name whose product rounded DOWN a fraction of a cent under its own
    percentile. Parametrised over many frames because a single frame passed
    this on whichever way its own rounding happened to go -- 53 of 400
    synthetic tickers were evicted from their own one-symbol scan.

    THE SWEEP HAS TO BE A SWEEP. Every ohlcv("burst") variant carries the same
    last bar by construction -- $44.80 on exactly 25,000,000 shares, see
    tests/synthetic.py -- and $44.80 rounds to itself, so forty variants of it
    are forty copies of one arithmetic that cannot disagree with itself. Run
    that way this test could not tell the two roundings apart, which was
    measured rather than argued: re-introducing the second rounding left it
    green. The prices and volumes are moved off those round numbers here so
    that a cent of disagreement is worth thousands of dollars of product.
    """
    cfg = ScanConfig()
    checked = 0
    for variant in range(40):
        frame = _scale(ohlcv("burst", variant=variant),
                       price=1.7391 * (1.0 + variant * 0.0137),
                       volume=0.7137 * (1.0 + variant * 0.0219))
        assert round(float(frame["Close"].iloc[-1]), 2) != float(frame["Close"].iloc[-1]), (
            "a close that is already exact to the cent cannot show a rounding disagreement")
        m = detect_setup(frame, cfg)
        if m is None:
            continue
        checked += 1
        assert session_dollar_volume(frame) == m["dollar_volume"]
        cand = Candidate(ticker="X", history=frame, **m)
        assert apply_liquidity_gate([cand], [session_dollar_volume(frame)], cfg) != []
    assert checked >= 20, "not enough frames exercised to say anything"


def test_a_bar_that_moved_no_money_never_reaches_the_gate(ohlcv):
    """dollar_volume feeds a numeric comparison in apply_liquidity_gate(); a
    None there is a TypeError mid-scan. Only reachable with the relative
    volume gate opened all the way, which is a legitimate setting."""
    cfg = ScanConfig(min_rvol=0.0)
    frame = _passing(ohlcv)
    _set_volume(frame, today=0.0, prev=0.0)
    assert detect_setup(frame, cfg) is None


@pytest.mark.parametrize("variant", [0, 1, 2, 3, 4])
def test_a_single_symbol_scan_is_not_gated_out_by_its_own_percentile(
    variant, fake_alpaca, ohlcv
):
    """`--tickers NVDA` is the smoke-test path. Any percentile of one value is
    that value, so a name must not be dropped for equalling its own floor."""
    fake_alpaca.add_history("SOLO", _thin(ohlcv, "burst", price=6.0,
                                          volume=300_000, variant=variant))
    assert [c.ticker for c in run_scan(ScanConfig(), universe=["SOLO"])] == ["SOLO"]


def test_the_liquidity_gate_can_be_turned_off(ohlcv):
    cfg = ScanConfig(min_dollar_volume_pctile=0.0)
    frame = _thin(ohlcv, "burst", price=50.0, volume=1_000)
    cand = Candidate(ticker="TINY", history=frame, **detect_setup(frame, cfg))
    assert liquidity_floor([1e9] * 10, cfg) is None
    assert [c.ticker for c in apply_liquidity_gate([cand], [1e9] * 10, cfg)] == ["TINY"]


def test_the_gate_ranks_against_every_symbol_that_traded_not_only_the_bursts(
    fake_alpaca, ohlcv
):
    """End to end, through run_scan: the quiet names in the universe are what
    the one burst is measured against. Nine quiet names at $1.6B/day put a
    $10M burst below the 30th percentile of the session -- and that burst is
    the only candidate, so a bursts-only denominator would have kept it."""
    fake_alpaca.add_history("BURST", _thin(ohlcv, "burst", price=10.0, volume=1_000_000))
    for i in range(9):
        fake_alpaca.add_history(f"Q{i}", _thin(ohlcv, "flat", price=800.0,
                                               volume=2_000_000, variant=i + 1))
    universe = ["BURST"] + [f"Q{i}" for i in range(9)]

    assert run_scan(ScanConfig(), universe=universe) == []
    # ...and with nothing else in the scan, the same burst is the whole market.
    fake_alpaca_only = run_scan(ScanConfig(), universe=["BURST"])
    assert [c.ticker for c in fake_alpaca_only] == ["BURST"]


def test_the_production_path_reads_the_symbol_file(fake_alpaca, ohlcv, tmp_path, monkeypatch):
    """run_scan(universe=None) -- the path the cron takes. Uses symbols that are
    NOT in the real data/symbols.txt, so the test fails if the argument is
    ignored and the default file is read instead."""
    symbols = tmp_path / "symbols.txt"
    symbols.write_text("# a comment\n\nZZZA\nZZZB\n")
    fake_alpaca.add_history("ZZZA", ohlcv("burst"))
    fake_alpaca.add_history("ZZZB", ohlcv("flat"))
    real = (pathlib.Path(__file__).resolve().parent.parent / "data" / "symbols.txt").read_text()
    assert "ZZZA" not in real, "the fixture symbols must not exist in the real file"
    found = run_scan(ScanConfig(), symbols_file=str(symbols))
    assert [c.ticker for c in found] == ["ZZZA"]


# =====================================================================
# Step 3 -- the data request
#
# Everything below asserts on what Alpaca is actually asked for. The double
# records the SDK's own to_request_fields(), which is the query string the
# client would send; asserting on the request object's attributes instead
# would pass even for a field alpaca-py silently drops.
# =====================================================================


def _wire_fields(fake_alpaca, ohlcv, cfg: ScanConfig | None = None) -> dict:
    """Run one scan and return the request fields it put on the wire."""
    fake_alpaca.add_history("AAA", ohlcv("base"))
    run_scan(cfg or ScanConfig(), universe=["AAA"])
    assert fake_alpaca.request_fields, "the data client was never asked for bars"
    return fake_alpaca.request_fields[-1]


def test_the_bars_request_asks_for_split_adjusted_prices(fake_alpaca, ohlcv):
    """Alpaca's default is `raw`. Unadjusted history puts every bar before a
    split on a different scale from the ones after it."""
    assert _wire_fields(fake_alpaca, ohlcv)["adjustment"] == Adjustment.SPLIT


def test_the_bars_request_names_a_feed_instead_of_taking_the_plan_default(fake_alpaca, ohlcv):
    """Unset, the feed is whatever the account happens to have -- IEX on the
    free plan, a single venue's slice of consolidated volume."""
    assert _wire_fields(fake_alpaca, ohlcv)["feed"] == DataFeed.DELAYED_SIP


def test_the_feed_is_overridable_for_an_account_that_carries_full_sip(fake_alpaca, ohlcv):
    fields = _wire_fields(fake_alpaca, ohlcv, ScanConfig(feed=DataFeed.SIP))
    assert fields["feed"] == DataFeed.SIP


def test_the_request_window_ends_at_the_session_being_scanned(fake_alpaca, ohlcv):
    """Without an end bound the response runs to `now`, so a scan of an
    earlier session would collect bars printed after it."""
    session = date(2026, 6, 24)
    fields = _wire_fields(fake_alpaca, ohlcv, ScanConfig(session_date=session))
    assert datetime.fromisoformat(fields["end"]).date() == session


def test_the_request_window_starts_a_lookback_before_the_session_not_before_now(
    fake_alpaca, ohlcv
):
    cfg = ScanConfig(session_date=date(2026, 6, 24))
    fields = _wire_fields(fake_alpaca, ohlcv, cfg)
    start = datetime.fromisoformat(fields["start"]).date()
    assert start == cfg.session_date - timedelta(days=int(cfg.lookback_days * 1.6))


# --- why the adjustment matters --------------------------------------------


def _lower_to_ohlcv(df):
    """The double returns alpaca-py's lower-case columns; detect_setup wants
    the capitalised ones the rest of the codebase uses."""
    return df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                              "close": "Close", "volume": "Volume"})


def test_a_forward_split_read_raw_erases_the_burst_it_lands_on(fake_alpaca, ohlcv):
    """Same symbol, same day, two adjustments -- and only one of them is real.

    The registered history is the adjusted one: a 12% burst on the newest bar.
    Give that bar a 4-for-1 ex-date and the raw prints put the previous 200
    bars at four times the price, so the burst reads as a ~72% collapse and
    the trailing windows every later layer computes are drawn across the step.
    """
    fake_alpaca.add_history("SPLT", ohlcv("burst"))
    fake_alpaca.add_split("SPLT", 4.0)
    end = datetime(2026, 6, 24, tzinfo=timezone.utc)

    adjusted = _lower_to_ohlcv(
        fake_alpaca.bars_frame(["SPLT"], end=end, adjustment=Adjustment.SPLIT).loc["SPLT"]
    )
    raw = _lower_to_ohlcv(
        fake_alpaca.bars_frame(["SPLT"], end=end, adjustment=Adjustment.RAW).loc["SPLT"]
    )

    def one_day_move(df):
        return (float(df["Close"].iloc[-1]) / float(df["Close"].iloc[-2]) - 1) * 100

    assert one_day_move(adjusted) > 10, "the adjusted frame is the burst it is meant to be"
    assert one_day_move(raw) < -70, "the raw frame reads the split as a crash"
    assert detect_setup(adjusted, ScanConfig()) is not None
    assert detect_setup(raw, ScanConfig()) is None


def test_the_scan_sees_the_split_adjusted_frame(fake_alpaca, ohlcv):
    """End to end: the double serves raw prints unless the request asks for
    split adjustment, so this candidate exists only because it does."""
    fake_alpaca.add_history("SPLT", ohlcv("burst"))
    fake_alpaca.add_split("SPLT", 4.0)
    assert [c.ticker for c in run_scan(ScanConfig(), universe=["SPLT"])] == ["SPLT"]


# --- which session a run is scanning ---------------------------------------


def test_the_session_is_todays_once_the_close_has_passed():
    """The evening cron fires at 18:16 ET."""
    assert current_session(datetime(2026, 9, 1, 18, 30, tzinfo=MARKET_TZ)) == date(2026, 9, 1)


def test_the_session_is_yesterdays_while_the_market_is_still_open():
    """Today's daily bar is still being written at 11am; scanning it would
    compare a partial volume against yesterday's full one."""
    assert current_session(datetime(2026, 9, 1, 11, 0, tzinfo=MARKET_TZ)) == date(2026, 8, 31)


def test_the_session_is_read_in_market_time_not_utc():
    """19:00 UTC is 15:00 ET: an hour of trading left, and today's daily bar
    still being written.

    An earlier version of this test used 00:00 UTC on the 2nd -- which a UTC
    clock and a market clock happen to answer identically, so it passed with
    the conversion deleted. This instant is one they disagree about: read as
    UTC it looks like a finished evening, and the scan would take a partial
    bar for a closed session.
    """
    assert current_session(datetime(2026, 9, 1, 19, 0, tzinfo=timezone.utc)) == date(2026, 8, 31)


def test_the_session_is_never_a_weekend():
    """Sunday evening: the most recent finished session is Friday's."""
    assert current_session(datetime(2026, 9, 6, 18, 30, tzinfo=MARKET_TZ)) == date(2026, 9, 4)


def test_the_weekend_rewind_steps_back_one_day_at_a_time():
    """Saturday, which is the only day of the week that can tell.

    The rewind walks back a day at a time until it lands on a weekday. From
    SUNDAY, one step lands on Saturday and loops to Friday, and TWO steps land
    on Friday directly -- so the Sunday case above passes either way, and
    `days=1` could be changed to `days=2` with the whole suite green, verified
    by mutation. From Saturday the two differ: one step is Friday, two is
    Thursday, and Thursday is a session whose bars this scan would then read
    as "today".
    """
    assert current_session(datetime(2026, 9, 5, 18, 30, tzinfo=MARKET_TZ)) == date(2026, 9, 4)


# --- freshness -------------------------------------------------------------


def test_only_the_current_copy_of_a_burst_is_scanned(fake_alpaca, ohlcv):
    """One frame, registered twice: once current, once as a halted name whose
    last print was that same spike five sessions ago. Only the date differs,
    and detect_setup would read either one as "today vs yesterday"."""
    frame = ohlcv("burst")
    fake_alpaca.add_history("NOW", frame)
    fake_alpaca.add_history("HALT", frame, stale_sessions=5)

    found = run_scan(ScanConfig(), universe=["NOW", "HALT"])

    assert [c.ticker for c in found] == ["NOW"]


def test_a_scan_where_nothing_traded_the_session_raises_rather_than_returning_empty(
    fake_alpaca, ohlcv
):
    """The market-holiday shape, and the wrong-day-cron shape, and the
    dead-feed shape: every symbol's newest bar is an earlier session. An empty
    shortlist here would be indistinguishable from a quiet market."""
    for ticker in ("AAA", "BBB"):
        fake_alpaca.add_history(ticker, ohlcv("burst"), stale_sessions=1)

    with pytest.raises(StaleDataError, match="no symbol carried a bar"):
        run_scan(ScanConfig(), universe=["AAA", "BBB"])


def test_the_session_can_be_pinned_through_the_environment(monkeypatch, fake_alpaca, ohlcv):
    """SCAN_SESSION_DATE is the escape hatch: re-run a past session, or scan
    deliberately on a day current_session() would guess wrong about."""
    monkeypatch.setenv("SCAN_SESSION_DATE", "2026-06-24")
    fields = _wire_fields(fake_alpaca, ohlcv)
    assert datetime.fromisoformat(fields["end"]).date() == date(2026, 6, 24)


def test_a_session_date_that_is_not_a_date_raises(monkeypatch):
    monkeypatch.setenv("SCAN_SESSION_DATE", "yesterday")
    with pytest.raises(ValueError, match="SCAN_SESSION_DATE"):
        ScanConfig()


def test_the_feed_can_be_pinned_through_the_environment(monkeypatch, fake_alpaca, ohlcv):
    monkeypatch.setenv("SCAN_FEED", "sip")
    assert _wire_fields(fake_alpaca, ohlcv)["feed"] == DataFeed.SIP


def test_a_feed_the_sdk_does_not_know_raises_instead_of_falling_back(monkeypatch):
    """A typo must not silently leave the scan on a feed nobody chose."""
    monkeypatch.setenv("SCAN_FEED", "delayed-sip")
    with pytest.raises(ValueError, match="SCAN_FEED"):
        ScanConfig()


# --- a feed this account cannot use ----------------------------------------


def _alpaca_error(status: int | None, message: str) -> APIError:
    """An APIError shaped the way alpaca-py builds one. The HTTP status is
    only present when the SDK had an HTTPError to build from, which is why
    the message is worth reading too."""
    body = json.dumps({"message": message})
    if status is None:
        return APIError(body)
    response = requests.Response()
    response.status_code = status
    return APIError(body, HTTPError(response=response))


DENIAL = "subscription does not permit querying recent SIP data"


def test_a_refused_feed_aborts_the_scan_instead_of_emptying_it(fake_alpaca, ohlcv):
    """403 on every batch, retried and dropped, is a completed scan that found
    nothing -- the same output as a quiet market."""
    fake_alpaca.add_history("AAA", ohlcv("burst"))
    fake_alpaca.raise_on_bars = _alpaca_error(403, DENIAL)

    with pytest.raises(FeedNotAuthorizedError, match="delayed_sip"):
        run_scan(ScanConfig(), universe=["AAA"])

    assert len(fake_alpaca.bar_requests) == 1, "a refusal is not transient; do not retry it"


def test_a_rejected_key_is_not_reported_as_a_feed_this_plan_lacks(fake_alpaca, ohlcv):
    """401 and 403 have OPPOSITE fixes and used to produce one message.

    Both statuses were classified as a feed denial, so a wrong or half-set
    ALPACA_API_KEY aborted with "Alpaca refused the 'delayed_sip' data feed ...
    set SCAN_FEED to a feed this account carries — or subscribe": the operator
    was sent to change a feed or buy a data plan over a typo. The exception's
    own name reaches the failure email, so the FIRST WORD they read at 6:16pm
    about why nothing arrived was the wrong one.

    No test built a 401 before this one — every refusal case in this file used
    403 or a status-less error — which is exactly why the conflation survived.
    """
    fake_alpaca.add_history("AAA", ohlcv("burst"))
    fake_alpaca.raise_on_bars = _alpaca_error(401, "request is not authorized")

    with pytest.raises(CredentialsRejectedError) as caught:
        run_scan(ScanConfig(), universe=["AAA"])

    said = str(caught.value)
    assert "ALPACA_API_KEY" in said and "ALPACA_SECRET_KEY" in said
    assert "subscribe" not in said, "a rejected key is not something you fix by subscribing"
    # Still a refusal, so still not retried: a bad key is no more transient
    # than a refused feed, and retrying it costs a second wrong answer.
    assert len(fake_alpaca.bar_requests) == 1


def test_a_refused_feed_still_says_feed_and_not_credentials(fake_alpaca, ohlcv):
    """The control for the test above, and the half that must not regress.

    Splitting the classifier is only worth anything if it splits: a 403 has to
    keep naming the feed, or the fix has moved the wrong report rather than
    removed it.
    """
    fake_alpaca.add_history("AAA", ohlcv("burst"))
    fake_alpaca.raise_on_bars = _alpaca_error(403, DENIAL)

    with pytest.raises(FeedNotAuthorizedError) as caught:
        run_scan(ScanConfig(), universe=["AAA"])

    assert "delayed_sip" in str(caught.value)
    assert not isinstance(caught.value, CredentialsRejectedError)


def test_neither_refusal_asserts_a_cause_it_cannot_know(fake_alpaca, ohlcv):
    """This file has never seen a live refusal — its own DEFAULT_FEED comment
    says so — so the status-to-cause mapping is inferred from the SDK and not
    confirmed. Each message therefore leads with what the status says and names
    the OTHER possibility second, rather than asserting one and denying it.

    Without this, the fix would have replaced one confidently wrong sentence
    with another, which is the defect class CLAUDE.md names twice.
    """
    fake_alpaca.add_history("AAA", ohlcv("burst"))

    fake_alpaca.raise_on_bars = _alpaca_error(401, "request is not authorized")
    with pytest.raises(CredentialsRejectedError) as unauth:
        run_scan(ScanConfig(), universe=["AAA"])

    fake_alpaca.bar_requests.clear()
    fake_alpaca.raise_on_bars = _alpaca_error(403, DENIAL)
    with pytest.raises(FeedNotAuthorizedError) as forbidden:
        run_scan(ScanConfig(), universe=["AAA"])

    assert "SCAN_FEED" in str(unauth.value), "the 401 message names the feed possibility too"
    assert "ALPACA_API_KEY" in str(forbidden.value), "and the 403 names the credential one"


def test_a_refusal_is_recognised_from_the_message_when_no_status_survives(fake_alpaca, ohlcv):
    fake_alpaca.add_history("AAA", ohlcv("burst"))
    fake_alpaca.raise_on_bars = _alpaca_error(None, DENIAL)

    with pytest.raises(FeedNotAuthorizedError):
        run_scan(ScanConfig(), universe=["AAA"])


def test_a_transient_failure_is_still_retried_and_dropped(fake_alpaca, ohlcv, monkeypatch):
    """The other half of the classification: a reset connection must keep the
    old retry-then-drop behaviour, not be mistaken for a refused feed."""
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    fake_alpaca.add_history("AAA", ohlcv("burst"))
    fake_alpaca.raise_on_bars = ConnectionError("connection reset by peer")

    assert run_scan(ScanConfig(), universe=["AAA"]) == []
    assert len(fake_alpaca.bar_requests) == 2, "one retry, then the batch is dropped"


# --- coverage: how much of a scan may be missing ---------------------------
# Step 3 raised only when EVERY symbol was behind the session; 60% stale warned
# once and scanned on. These fix where the line is. Each one asserts the state
# it is about -- how much of the universe arrived -- before asserting the
# verdict, so a test cannot pass because a different shortfall raised.


def _coverage(fake_alpaca, ohlcv, *, fresh: int, stale: int = 0, prefix: str = "S") -> list[str]:
    """A universe of `fresh` current names and `stale` names a session behind."""
    universe = []
    for i in range(fresh):
        name = f"{prefix}F{i}"
        fake_alpaca.add_history(name, ohlcv("burst", variant=i))
        universe.append(name)
    for i in range(stale):
        name = f"{prefix}S{i}"
        fake_alpaca.add_history(name, ohlcv("burst", variant=100 + i), stale_sessions=1)
        universe.append(name)
    return universe


def _scan_shape(universe, fake_alpaca, cfg=None) -> dict:
    """What the scan saw, without asserting anything about it."""
    stats: dict = {}
    try:
        run_scan(cfg or ScanConfig(), universe=universe, stats=stats)
    except (StaleDataError, IncompleteScanError):
        pass
    return stats


def test_run_scan_reports_the_shape_of_the_scan_it_ran(fake_alpaca, ohlcv):
    """The counts a caller cannot read off the returned list."""
    universe = _coverage(fake_alpaca, ohlcv, fresh=8, stale=1) + ["NOSUCH"]
    stats: dict = {}

    found = run_scan(ScanConfig(), universe=universe, stats=stats)

    assert stats["requested"] == 10
    assert stats["with_bars"] == 9, "NOSUCH registered no history at all"
    assert stats["fresh"] == 8
    assert list(stats["stale"]) == ["SS0"]
    assert stats["no_bars"] == 1
    assert stats["dropped"] == 0
    assert stats["candidates"] == len(found)
    assert stats["session"] == current_session()


def test_a_scan_mostly_behind_the_session_raises_rather_than_reporting_a_minority(
    fake_alpaca, ohlcv
):
    """The escalation step 3 left open: 50% stale is not a shortlist.

    The names that DID update are real bursts, so this cannot pass by finding
    nothing -- without the guard the scan returns them, ranked against a
    dollar-volume percentile drawn from the same minority.
    """
    universe = _coverage(fake_alpaca, ohlcv, fresh=6, stale=6)
    shape = _scan_shape(universe, fake_alpaca)
    assert shape["with_bars"] == 12 and len(shape["stale"]) == 6, "half the scan, no more"
    assert shape["dropped"] == 0 and shape["no_bars"] == 0, "nothing else went wrong"

    with pytest.raises(StaleDataError, match="50%"):
        run_scan(ScanConfig(), universe=universe)


def test_a_scan_a_little_behind_the_session_still_returns_its_shortlist(fake_alpaca, ohlcv):
    """The inverse: halts and delistings are a normal day, not a failure."""
    universe = _coverage(fake_alpaca, ohlcv, fresh=11, stale=1)
    stats: dict = {}

    found = run_scan(ScanConfig(), universe=universe, stats=stats)

    assert len(stats["stale"]) / stats["with_bars"] < ScanConfig().max_stale_fraction
    assert found, "the fresh names still burst"
    assert "SS0" not in {c.ticker for c in found}, "the halted name is skipped, not scanned"


def test_the_stale_fraction_is_not_applied_to_a_handful_of_tickers(fake_alpaca, ohlcv):
    """`--tickers NVDA,PLTR` with one halted name is 50% stale and must still
    scan: a fraction of two symbols is not a measurement of a market."""
    universe = _coverage(fake_alpaca, ohlcv, fresh=1, stale=1)
    shape = _scan_shape(universe, fake_alpaca)
    assert len(shape["stale"]) / shape["with_bars"] >= ScanConfig().max_stale_fraction

    assert [c.ticker for c in run_scan(ScanConfig(), universe=universe)] == ["SF0"]


def test_a_scan_where_no_symbol_returned_a_bar_raises(fake_alpaca, ohlcv):
    """The silent death: the feed answers every request with nothing.

    Nothing is dropped, nothing is stale, no exception is raised anywhere --
    the old scan simply returned [] and the email said the market was quiet.
    """
    shape = _scan_shape(["AAA", "BBB"], fake_alpaca)
    assert shape["dropped"] == 0 and shape["with_bars"] == 0

    with pytest.raises(IncompleteScanError, match="not one of 2 symbols"):
        run_scan(ScanConfig(), universe=["AAA", "BBB"])


def test_most_of_the_universe_dropped_raises_rather_than_ranking_the_rest(
    fake_alpaca, ohlcv, monkeypatch
):
    """Half the batches failing is not a scan of the market, it is a scan of
    whichever half the network liked."""
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    universe = _coverage(fake_alpaca, ohlcv, fresh=12)
    fake_alpaca.raise_on_bars = ConnectionError("connection reset by peer")
    fake_alpaca.fail_symbols = {"SF0", "SF1", "SF2", "SF3", "SF4", "SF5"}
    cfg = ScanConfig(batch_size=1)

    shape = _scan_shape(universe, fake_alpaca, cfg)
    assert shape["dropped"] == 6, "exactly half the universe, and nothing else"
    assert not shape["stale"] and shape["no_bars"] == 0

    with pytest.raises(IncompleteScanError, match="50%"):
        run_scan(cfg, universe=universe)


def test_a_few_dropped_symbols_are_reported_but_do_not_stop_the_scan(
    fake_alpaca, ohlcv, monkeypatch
):
    """The inverse, and the brittleness guard: one flaky symbol must not kill
    a run. It must still be counted -- src.pipeline degrades the run on it."""
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    universe = _coverage(fake_alpaca, ohlcv, fresh=12)
    fake_alpaca.raise_on_bars = ConnectionError("connection reset by peer")
    fake_alpaca.fail_symbols = {"SF0"}
    stats: dict = {}

    found = run_scan(ScanConfig(batch_size=1), universe=universe, stats=stats)

    assert stats["dropped"] == 1
    assert found and "SF0" not in [c.ticker for c in found]


# =====================================================================
# Step 6b -- get_universe() and the symbol-file parser
#
# Step 6a listed this as a hole and it is the widest one in the module: the
# universe is the input to every other rule, and until now nothing exercised
# the parser at all. A typo that silently shrank the scan by one name -- or by
# a whole sector-grouped block -- would have looked exactly like a quiet day.
# Every malformed input below must RAISE. None of them may be skipped.
# =====================================================================


def _symbol_file(tmp_path, text: str, name: str = "symbols.txt"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_the_universe_is_the_file_in_file_order(tmp_path):
    """Order is preserved so the file can stay grouped by sector for a human
    reader; sorting it here would make the grouping unreadable in review."""
    path = _symbol_file(tmp_path, "NVDA\nAAPL\nMSFT\n")
    assert get_universe(path) == ["NVDA", "AAPL", "MSFT"]


def test_comments_and_blank_lines_are_not_symbols(tmp_path):
    """The real file is a commented, sector-grouped document."""
    path = _symbol_file(tmp_path, """
# --- semis ---
NVDA
AMD    # trailing comments too

  MSFT

# --- and nothing else ---
""")
    assert get_universe(path) == ["NVDA", "AMD", "MSFT"]


@pytest.mark.parametrize("line, why", [
    ("nvda", "lower case is not how a ticker is written"),
    ("BRK.B", "class shares are rejected on purpose -- see the file header"),
    ("ABCDEF", "six characters is not a US ticker"),
    ("NVDA AMD", "two symbols on one line"),
    ("NVDA,AMD", "a comma-separated list"),
    ("BF-B", "punctuation of any kind"),
    ("N3VDA", "digits"),
])
def test_a_line_that_is_not_a_ticker_stops_the_run(line, why, tmp_path):
    """A typo must fail the run, not quietly shrink the universe. The scan's
    only defence against that is this raise -- an unparsed name is
    indistinguishable downstream from a name that did not burst."""
    path = _symbol_file(tmp_path, f"NVDA\n{line}\nMSFT\n")
    with pytest.raises(SymbolFileError) as excinfo:
        get_universe(path)
    message = str(excinfo.value)
    assert "line 2" in message, f"{why}: the operator needs the line number"
    assert line in message, f"{why}: the operator needs the offending text"


def test_a_duplicate_symbol_stops_the_run_and_names_both_lines(tmp_path):
    """A duplicate is scanned twice, counted twice in the coverage fractions,
    and ranked twice in the dollar-volume distribution rule 6 draws its floor
    from. In a hand-typed, sector-grouped file it is the likeliest mistake of
    all: one name filed under two sectors."""
    path = _symbol_file(tmp_path, "NVDA\nMSFT\n# --- again ---\nNVDA\n")
    with pytest.raises(SymbolFileError, match=r"line 4: NVDA is already listed on line 1"):
        get_universe(path)


def test_an_empty_file_is_not_a_universe(tmp_path):
    """`[]` from here is a scan of nothing, which returns no candidates and
    raises nothing -- the empty shortlist that reads like a quiet market."""
    with pytest.raises(SymbolFileError, match="no symbols found"):
        get_universe(_symbol_file(tmp_path, ""))


def test_a_file_of_nothing_but_comments_is_not_a_universe(tmp_path):
    """The same failure, one edit away: a file whose symbols were all
    commented out still parses cleanly line by line."""
    with pytest.raises(SymbolFileError, match="no symbols found"):
        get_universe(_symbol_file(tmp_path, "# NVDA\n# MSFT\n\n   \n"))


def test_a_missing_file_raises_the_symbol_file_error_not_an_oserror(tmp_path):
    """src.pipeline catches SymbolFileError to fail the run loudly with a
    message about the symbol file. A bare OSError escaping here would be
    reported as an unknown crash instead."""
    with pytest.raises(SymbolFileError, match="cannot read symbol file"):
        get_universe(tmp_path / "does-not-exist.txt")


def test_a_byte_order_mark_fails_loudly_rather_than_eating_the_first_symbol(tmp_path):
    """An editor that writes UTF-8 with a BOM prefixes an invisible character
    to line 1. The file is read as plain utf-8, so the BOM stays on the first
    ticker and that line stops the run.

    Loud is the right outcome and the reason this is asserted: the quiet
    alternative -- skipping an unparseable line -- would drop whichever symbol
    happened to be first in the file, on some machines and not others, with
    nothing in the log.

    The message reports the line with !r, which is what makes this diagnosable
    rather than merely loud: an operator staring at a file that looks correct
    gets `'\ufeffNVDA' is not a ticker` instead of `'NVDA' is not a ticker`.
    """
    path = _symbol_file(tmp_path, "﻿NVDA\nMSFT\n")
    with pytest.raises(SymbolFileError) as excinfo:
        get_universe(path)
    message = str(excinfo.value)
    assert "line 1" in message
    assert "\\ufeff" in message, (
        f"the byte-order mark has to survive into the message to be diagnosable: {message}")


def test_surrounding_whitespace_is_not_part_of_a_ticker(tmp_path):
    path = _symbol_file(tmp_path, "  NVDA\t\n\tMSFT  \n")
    assert get_universe(path) == ["NVDA", "MSFT"]


def test_the_checked_in_symbol_file_parses(fake_alpaca):
    """get_universe() with no argument -- the production default, and the one
    path that reads data/symbols.txt itself. A file that stopped parsing would
    otherwise only be discovered by the cron."""
    universe = get_universe()
    assert len(universe) > 100
    assert len(set(universe)) == len(universe)
    assert all(_SYMBOL_RE.match(t) for t in universe)


# =====================================================================
# Step 6b -- batching, and the retry the scan is built around
#
# The retry is the reason a flaky symbol does not kill a run, and the reason a
# permanently-broken one costs a hundred names instead of one. Step 6a covered
# only the branch where both attempts fail; the successful retry, the size of
# the loss when both do, and a refusal that only arrives on the second attempt
# were all untested.
# =====================================================================


def _attempt_recorder(monkeypatch, failures: dict[int, Exception]) -> list[list[str]]:
    """Record every get_stock_bars attempt; raise on the ones named.

    `failures` is keyed by attempt number, so a batch can fail once and
    succeed on the retry -- something a single `raise_on_bars` cannot express.
    The returned list holds the symbols each attempt asked for, which is how
    the batching itself is checked.
    """
    from tests.fakes import FakeDataClient

    served = FakeDataClient.get_stock_bars
    attempts: list[list[str]] = []

    def recording(self, request):
        symbols = getattr(request, "symbol_or_symbols", [])
        attempts.append([symbols] if isinstance(symbols, str) else list(symbols))
        exc = failures.get(len(attempts) - 1)
        if exc is not None:
            raise exc
        return served(self, request)

    monkeypatch.setattr(FakeDataClient, "get_stock_bars", recording)
    return attempts


def test_the_universe_is_requested_in_batches_that_lose_no_symbol(
    fake_alpaca, ohlcv, monkeypatch
):
    """cfg.batch_size splits the universe into requests. The batches must
    partition it -- a name in none of them is never scanned, and a name in two
    is scanned twice and counted twice in the percentile rule 6 draws its
    floor from."""
    universe = _coverage(fake_alpaca, ohlcv, fresh=25)
    attempts = _attempt_recorder(monkeypatch, {})

    run_scan(ScanConfig(batch_size=10), universe=universe)

    assert [len(a) for a in attempts] == [10, 10, 5]
    assert [t for batch in attempts for t in batch] == universe


def test_a_universe_smaller_than_one_batch_is_one_request(fake_alpaca, ohlcv, monkeypatch):
    """`--tickers NVDA,PLTR` must not fan out into a request per name."""
    universe = _coverage(fake_alpaca, ohlcv, fresh=2)
    attempts = _attempt_recorder(monkeypatch, {})
    run_scan(ScanConfig(), universe=universe)
    assert attempts == [universe]


def test_a_batch_that_fails_once_is_retried_and_keeps_its_symbols(
    fake_alpaca, ohlcv, monkeypatch
):
    """The successful-retry path -- the entire reason the retry exists, and
    the branch step 6a did not cover. A transient reset must cost nothing at
    all: the same batch is asked for again, its candidates arrive, and the
    coverage counters record no loss for src.pipeline to degrade the run on.
    """
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    universe = _coverage(fake_alpaca, ohlcv, fresh=12)
    attempts = _attempt_recorder(monkeypatch, {0: ConnectionError("connection reset by peer")})
    stats: dict = {}

    found = run_scan(ScanConfig(), universe=universe, stats=stats)

    assert attempts == [universe, universe], "the retry must re-ask for the whole batch"
    assert stats["dropped"] == 0 and stats["with_bars"] == 12
    assert {c.ticker for c in found} == set(universe), "a retried batch loses nothing"


def test_the_retry_waits_before_asking_again(fake_alpaca, ohlcv, monkeypatch):
    """Without a pause the retry is a second request into whatever rate limit
    or outage refused the first one, microseconds later."""
    slept: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda seconds: slept.append(seconds))
    _coverage(fake_alpaca, ohlcv, fresh=2)
    _attempt_recorder(monkeypatch, {0: ConnectionError("connection reset by peer")})

    run_scan(ScanConfig(), universe=["SF0", "SF1"])

    assert slept and all(s > 0 for s in slept), f"the retry did not wait: {slept}"


def test_a_batch_that_fails_twice_drops_every_symbol_in_it(fake_alpaca, ohlcv, monkeypatch):
    """The cost of a permanent failure is the batch, not the symbol.

    The symbol file is hand-typed and sector-grouped, so one bad ticker takes
    a contiguous block of its neighbours down with it. The scan says so in the
    log and counts all of them; a test that only ever failed one-symbol
    batches would never have seen the difference.
    """
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    universe = _coverage(fake_alpaca, ohlcv, fresh=12)
    reset = ConnectionError("connection reset by peer")
    _attempt_recorder(monkeypatch, {0: reset, 1: reset})
    stats: dict = {}

    found = run_scan(ScanConfig(batch_size=3), universe=universe, stats=stats)

    assert stats["dropped"] == 3, "the whole batch, not the one symbol that failed"
    assert stats["with_bars"] == 9
    assert {c.ticker for c in found}.isdisjoint(universe[:3])


def test_a_feed_refusal_that_only_arrives_on_the_retry_still_aborts_the_scan(
    fake_alpaca, ohlcv, monkeypatch
):
    """The second half of the refusal classification. A refusal reaching the
    retry -- a reset first, then the 403 -- must abort the run exactly as one
    on the first attempt does. Handled on the first attempt only, every batch
    would retry, be refused, and be dropped, ending in a complete scan of
    nothing."""
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    universe = _coverage(fake_alpaca, ohlcv, fresh=12)
    _attempt_recorder(monkeypatch, {
        0: ConnectionError("connection reset by peer"),
        1: _alpaca_error(403, DENIAL),
    })

    with pytest.raises(FeedNotAuthorizedError, match="delayed_sip"):
        run_scan(ScanConfig(), universe=universe)


# --- the coverage limits, pinned from BELOW as well as above ---------------
#
# The tests step 6a wrote put exactly half a universe out of action and
# asserted the raise, which kills a limit RAISED above 50% and says nothing
# about one lowered to 10%. These two frames sit just under each limit and
# must still produce a shortlist.


def test_a_scan_just_inside_the_stale_limit_still_returns_its_shortlist(fake_alpaca, ohlcv):
    """Five of twelve behind the session is 42% -- a bad day for the feed, not
    a reason to throw away the ten bursts that did update."""
    universe = _coverage(fake_alpaca, ohlcv, fresh=7, stale=5)
    shape = _scan_shape(universe, fake_alpaca)
    assert len(shape["stale"]) / shape["with_bars"] < ScanConfig().max_stale_fraction
    assert shape["dropped"] == 0 and shape["no_bars"] == 0, "nothing else went wrong"

    found = run_scan(ScanConfig(), universe=universe)

    assert len(found) == 7, "the fresh names still burst"


def test_a_scan_just_inside_the_dropped_limit_still_returns_its_shortlist(
    fake_alpaca, ohlcv, monkeypatch
):
    """The same boundary for the other counter: five failed batches of twelve
    is a flaky network, and the run is degraded by src.pipeline rather than
    abandoned here."""
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    universe = _coverage(fake_alpaca, ohlcv, fresh=12)
    fake_alpaca.raise_on_bars = ConnectionError("connection reset by peer")
    fake_alpaca.fail_symbols = {"SF0", "SF1", "SF2", "SF3", "SF4"}
    cfg = ScanConfig(batch_size=1)

    shape = _scan_shape(universe, fake_alpaca, cfg)
    assert shape["dropped"] / len(universe) < cfg.max_dropped_fraction
    assert not shape["stale"] and shape["no_bars"] == 0

    found = run_scan(cfg, universe=universe)

    assert len(found) == 7


# --- when a session's bar is finished --------------------------------------


def test_a_session_is_finished_the_moment_the_settling_margin_has_passed():
    """SESSION_COMPLETE_ET is the line, and both sides of it are asserted so
    that moving it -- to 20:15 for the extended session, say -- fails here
    rather than silently making the evening cron scan yesterday.

    Read off the constant: a minute either side of whatever it is set to.
    """
    close = datetime.combine(date(2026, 9, 1), SESSION_COMPLETE_ET, tzinfo=MARKET_TZ)
    assert current_session(close) == date(2026, 9, 1)
    assert current_session(close - timedelta(minutes=1)) == date(2026, 8, 31)


# --- which side of the close a run is on -----------------------------------
# Step 10. src.pipeline asks this one question to decide whether the run type
# it was given matches the clock it is running on: an evening run is a scan of
# the session that closed today, a morning run is a pass before today's open,
# and nothing used to check either. These pin the predicate itself; the
# consequences are in tests/test_pipeline.py.


def test_the_session_has_closed_after_the_settling_margin_and_not_before():
    """The same line current_session() turns on, asserted from both sides so
    that moving SESSION_COMPLETE_ET fails here too rather than quietly putting
    the evening cron on the wrong side of its own check."""
    close = datetime.combine(date(2026, 9, 1), SESSION_COMPLETE_ET, tzinfo=MARKET_TZ)
    assert session_has_closed(close) is True
    assert session_has_closed(close - timedelta(minutes=1)) is False


def test_a_weekend_evening_is_not_a_session_that_closed_today():
    """Saturday at 6pm: a session did close recently, but not today's -- there
    was none. An evening run then is scanning Friday and should say so."""
    assert session_has_closed(datetime(2026, 9, 5, 18, 30, tzinfo=MARKET_TZ)) is False


def test_the_close_is_read_in_market_time_not_utc():
    """19:00 UTC is 15:00 ET, an hour of trading left. Read as UTC it looks
    like a finished evening -- the same instant that catches a dropped
    timezone conversion in current_session()."""
    assert session_has_closed(datetime(2026, 9, 1, 19, 0, tzinfo=timezone.utc)) is False


@pytest.mark.parametrize("hour", [0, 6, 9, 13, 16, 17, 21, 23])
@pytest.mark.parametrize("day", [31, 1, 2, 3, 4, 5, 6])   # Mon 2026-08-31 .. Sun
def test_the_two_clock_functions_can_never_disagree(day, hour):
    """"today's session has closed" and "the newest completed session is today"
    are the same fact, and they are computed twice, in two functions.

    Sweeping a week of hours pins them together: an edit that moves one
    without the other -- a weekend rule dropped from the predicate, say --
    fails here instead of producing a run that scans yesterday while insisting
    the session closed today.
    """
    month = 8 if day == 31 else 9
    now = datetime(2026, month, day, hour, 30, tzinfo=MARKET_TZ)
    assert session_has_closed(now) == (current_session(now) == now.date())


# =====================================================================
# Step 6b -- the numbers themselves
#
# Every rejection test above reads its boundary off ScanConfig, which is what
# lets it keep testing the rule after a retune instead of testing the old
# number. The cost is that not one of them notices a retune: set min_gain_pct
# to 1.0 and the 4% momentum burst becomes a 1% momentum burst with the suite
# green. These two tests are the other half.
# =====================================================================


def test_the_scan_filter_still_holds_the_thresholds_it_was_tuned_to():
    """A strategy change has to be deliberate enough to edit a test.

    Every number here is a claim knowledge/strategy.md or README makes about
    what this scanner is. The coverage limits are in the same list because
    lowering one turns an ordinary day's halts into a failed run, and raising
    one lets a scan of a third of the market be emailed as the market.
    """
    cfg = ScanConfig()
    assert (cfg.min_gain_pct, cfg.min_price) == (4.0, 4.0)
    assert (cfg.min_rvol, cfg.rvol_lookback, cfg.min_rvol_sessions) == (1.5, 50, 20)
    assert cfg.min_dollar_volume_pctile == 30.0
    assert (cfg.max_stale_fraction, cfg.max_dropped_fraction) == (0.5, 0.5)
    assert cfg.coverage_guard_min_symbols == 10
    assert (cfg.lookback_days, cfg.batch_size) == (260, 100)
    assert cfg.feed == DataFeed.DELAYED_SIP
    assert SESSION_COMPLETE_ET == time_of_day(16, 15)


def test_the_readme_describes_the_filter_the_code_applies():
    """CLAUDE.md's standing rule, for the one paragraph that states all five
    per-scan thresholds as numbers.

    The rule has already failed on three consecutive commits by relying on
    someone remembering, and step 4 rewrote every number in this line. A
    retune that sweeps ScanConfig and leaves the README describing the old
    strategy is the same defect as leaving the absolute share floor documented
    after it was deleted.
    """
    readme = (pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text()
    layer1 = readme.split("Layer 1", 1)[-1].split("Layer 2", 1)[0]
    cfg = ScanConfig()
    claims = {
        r"≥\s*([\d.]+)%\s*gain": cfg.min_gain_pct,
        r"≥\s*([\d.]+)x its own": cfg.min_rvol,
        r"([\d.]+)-session average": float(cfg.rvol_lookback),
        r"price > \$([\d.]+)": cfg.min_price,
        r"top ([\d.]+)% of the day's dollar volume": 100.0 - cfg.min_dollar_volume_pctile,
    }
    for pattern, expected in claims.items():
        found = re.search(pattern, layer1)
        assert found, (
            f"README's Layer 1 paragraph no longer states {pattern!r}. Either the "
            "filter description was reworded -- re-point this test at it -- or a "
            "threshold stopped being documented at all."
        )
        assert float(found.group(1)) == expected, (
            f"README says {found.group(0)!r}; ScanConfig says {expected}. "
            "Sweep the docs (CLAUDE.md: a step is not done until they are true)."
        )

