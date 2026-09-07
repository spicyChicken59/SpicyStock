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

import numpy as np
import pandas as pd
import logging

import pytest
import requests
from alpaca.common.exceptions import APIError
from alpaca.data.enums import Adjustment, DataFeed
from requests.exceptions import HTTPError

from src.scanner import (
    DEFAULT_FEED,
    SIP_HOLDBACK_MINUTES,
    previous_session,
    _drop_gapped_symbols,
    _download_batch,
    _last_bar_date,
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
    liquidity_split,
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


def test_every_config_field_is_either_strategy_or_plumbing():
    """A field that is in neither list escapes the rules fingerprint in
    silence: the run would record "these are the rules" over a number that
    changed what a burst is and was never written down. Both lists are
    checked against the dataclass rather than against each other, so a field
    added later cannot arrive uncategorised, and neither can a list keep
    naming a field that was deleted."""
    import dataclasses

    fields = {f.name for f in dataclasses.fields(ScanConfig)}
    strategy, operational = set(ScanConfig.STRATEGY_FIELDS), set(ScanConfig.OPERATIONAL_FIELDS)

    assert not (strategy & operational), sorted(strategy & operational)
    assert strategy | operational == fields, (
        f"uncategorised: {sorted(fields - strategy - operational)}; "
        f"named but not fields: {sorted((strategy | operational) - fields)}")
    assert "STRATEGY_FIELDS" not in fields, "the lists are class attributes, not fields"


def test_the_scan_hands_back_what_the_floor_refused_and_the_floor_itself(fake_alpaca, ohlcv):
    """A burst rule 6 refused used to leave through a log line and nothing
    else: apply_liquidity_gate() built `dropped`, printed it at INFO and
    returned `kept`, so the thinner of two genuine 12% bursts on a two-name
    --tickers run was in no count, no row and no line of the email --
    reproduced twice independently. run_scan() hands the refused bursts to
    the caller now, the same way it hands back stats, and records the floor
    it applied so the run can say what the bar was that night."""
    fake_alpaca.add_history("BIG", _thin(ohlcv, "burst", price=200.0, volume=5_000_000))
    fake_alpaca.add_history("TINY", _thin(ohlcv, "burst", price=5.0, volume=200_000, variant=1))
    for i in range(8):
        fake_alpaca.add_history(f"Q{i}", _thin(ohlcv, "flat", price=80.0,
                                               volume=2_000_000, variant=i + 2))
    stats, refused = {}, []

    found = run_scan(ScanConfig(), universe=["BIG", "TINY"] + [f"Q{i}" for i in range(8)],
                     stats=stats, refused=refused)

    assert [c.ticker for c in found] == ["BIG"]
    assert [c.ticker for c in refused] == ["TINY"], "the refused burst reaches the caller"
    assert refused[0].history is not None, "with its frame, so the checklist can still run on it"
    assert stats["liquidity_refused"] == 1 and stats["candidates"] == 1
    assert refused[0].dollar_volume < stats["liquidity_floor"] <= found[0].dollar_volume, (
        "the floor recorded is the number the split was made on")


def test_liquidity_split_is_the_gate_with_its_other_half(ohlcv):
    """The kept list is apply_liquidity_gate()'s answer exactly; the refused
    list is everything it dropped, and the floor is the percentile both were
    judged against. With the rule off, nothing is refused and there is no
    floor to report."""
    cfg = ScanConfig()
    cands = []
    for i, dv in enumerate([2e6, 8e6, 30e6, 90e6]):
        frame = _thin(ohlcv, "burst", price=50.0, volume=dv / 50.0, variant=i)
        cands.append(Candidate(ticker=f"T{i}", history=frame, **detect_setup(frame, cfg)))
    universe = [float(i + 1) * 1e6 for i in range(100)]

    kept, refused, floor = liquidity_split(cands, universe, cfg)

    assert kept == apply_liquidity_gate(cands, universe, cfg)
    assert {c.ticker for c in kept} | {c.ticker for c in refused} == {c.ticker for c in cands}
    assert not ({c.ticker for c in kept} & {c.ticker for c in refused})
    assert floor == liquidity_floor(universe, cfg)
    assert all(c.dollar_volume < floor for c in refused) and all(c.dollar_volume >= floor for c in kept)
    assert liquidity_split(cands, [1e9] * 10, ScanConfig(min_dollar_volume_pctile=0)) == (cands, [], None)


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


def test_the_liquidity_floor_is_not_universe_invariant():
    """A percentile is feed-invariant. It is NOT universe-invariant, and the
    scanner's own comment claimed the opposite of what it does.

    That comment said the gate "starts doing real work when the universe widens
    past data/symbols.txt, which is when barely-liquid names where slippage
    eats the edge becomes a live risk". A percentile keeps a fixed FRACTION, so
    widening the universe with the illiquid names curation removes moves the
    absolute bar DOWN. This is the second thing the open decision has to answer
    for, beside rule 4: widening does not merely cost more, it silently
    rewrites a strategy rule unless the gate gains an absolute floor.

    Two log-normal populations of the shape US dollar volume really has —
    parameters stated here rather than fitted, because no live data reaches
    this sandbox and an invented distribution asserted as measured would be
    worse than one declared as invented. The DIRECTION and the ORDER OF
    MAGNITUDE are what this pins; the exact figure is a property of the model.
    """
    rng = np.random.default_rng(20260904)
    curated = np.exp(rng.normal(np.log(600e6), 1.0, 230))     # large/mid caps
    widened = np.concatenate([                                # plus the tail
        curated, np.exp(rng.normal(np.log(8e6), 1.6, 2770))])
    cfg = ScanConfig()

    tight = liquidity_floor(list(curated), cfg)
    loose = liquidity_floor(list(widened), cfg)

    # The fraction kept is fixed by construction on BOTH — that is the whole
    # mechanism, and asserting it is what makes the floor comparison mean
    # something rather than being an artefact of two different populations.
    kept = cfg.min_dollar_volume_pctile / 100
    assert abs((curated >= tight).mean() - (1 - kept)) < 0.02
    assert abs((widened >= loose).mean() - (1 - kept)) < 0.02

    assert loose < tight / 10, (
        f"widening the universe should collapse the absolute floor; "
        f"${tight/1e6:.0f}M -> ${loose/1e6:.0f}M")

    # And the consequence, which is the part that costs money: a burst that is
    # too thin to trade is refused today and admitted after the widening.
    slippage_eats_the_edge = 20e6
    assert slippage_eats_the_edge < tight, "refused while the universe is curated"
    assert slippage_eats_the_edge > loose, "and admitted once it widens"


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
    assert _wire_fields(fake_alpaca, ohlcv)["feed"] == DataFeed.SIP


def test_the_feed_is_overridable_to_the_single_venue_fallback(fake_alpaca, ohlcv):
    """This used to override to SIP, which is the default now, so it proved
    nothing; IEX is the fallback README and .env.example name for a plan that
    cannot query SIP, and it is the one feed the free plan is known to carry."""
    fields = _wire_fields(fake_alpaca, ohlcv, ScanConfig(feed=DataFeed.IEX))
    assert fields["feed"] == DataFeed.IEX


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

    # The phrase, not the bare feed name: the notice also lists EVERY feed the
    # SDK knows, so `match="sip"` was satisfied with the refused feed dropped
    # from the sentence.
    with pytest.raises(FeedNotAuthorizedError, match=f"refused the {DEFAULT_FEED.value!r} data feed"):
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

    assert f"refused the {DEFAULT_FEED.value!r} data feed" in str(caught.value)
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


def test_run_scan_names_the_symbols_the_feed_returned_nothing_for_and_states_its_coverage(
    fake_alpaca, ohlcv, caplog
):
    """A symbol the feed answers with NOTHING -- unknown to it, or purged after
    a ticker change -- is in no frame, so it was not stale (that needs a bar),
    not dropped (that is a failed batch), and below DEGRADED_NO_BARS_FRACTION
    it reached no log line, no record, no email and no page. Found trying to
    read a replacement symbol's coverage off a rehearsal's log, which could
    only say nothing. The scan warns with the names now and states the
    coverage as positive counts, because no warning is also what a scan that
    never asked prints."""
    universe = _coverage(fake_alpaca, ohlcv, fresh=8, stale=1) + ["NOSUCH", "ALSOGONE"]
    stats: dict = {}
    with caplog.at_level(logging.INFO, logger="src.scanner"):
        run_scan(ScanConfig(), universe=universe, stats=stats)

    assert stats["no_bars_names"] == ["ALSOGONE", "NOSUCH"] and stats["no_bars"] == 2
    messages = [r.getMessage() for r in caplog.records]
    warned = [r.getMessage() for r in caplog.records
              if r.levelno == logging.WARNING and "no bar at all" in r.getMessage()]
    assert len(warned) == 1 and "2 of 11 symbols" in warned[0] and "ALSOGONE, NOSUCH" in warned[0], messages
    assert [m for m in messages if m.startswith("Coverage for ")] == [
        f"Coverage for {stats['session']}: 11 requested; 9 answered with bars, 1 of those with no bar "
        "for the session; 2 answered with no bar at all; 0 dropped after their batch failed twice; "
        "0 duplicate bar(s) dropped"], messages


def test_run_scan_counts_the_bars_the_feed_sent_twice_and_states_them_in_its_coverage(
    fake_alpaca, ohlcv, caplog
):
    """A duplicate is resolved inside _download_batch and the frame that comes
    out cannot show it ever happened, so a feed sending a preliminary bar and
    a corrected one was visible on no surface and in no log line -- the same
    silence `no_bars_names` was added to end. Counted per symbol, named in a
    warning, and stated in the coverage line as a positive count, because no
    warning is also what a scan with nothing to say prints."""
    universe = _coverage(fake_alpaca, ohlcv, fresh=8, stale=1)
    fake_alpaca.send_session_bar_twice(universe[0])
    fake_alpaca.send_session_bar_twice(universe[1], copies=2)
    stats: dict = {}
    with caplog.at_level(logging.INFO, logger="src.scanner"):
        run_scan(ScanConfig(), universe=universe, stats=stats)

    assert stats["duplicate_bars"] == 3
    messages = [r.getMessage() for r in caplog.records]
    warned = [r.getMessage() for r in caplog.records
              if r.levelno == logging.WARNING and "sent twice" in r.getMessage()]
    assert len(warned) == 1 and f"{universe[1]} (2)" in warned[0] and f"{universe[0]} (1)" in warned[0], messages
    assert warned[0].index(f"{universe[1]} (2)") < warned[0].index(f"{universe[0]} (1)"), (
        "most-repeated first, the order stopped_printing's names use", warned[0])
    assert [m for m in messages if m.startswith("Coverage for ")] == [
        f"Coverage for {stats['session']}: 9 requested; 9 answered with bars, 1 of those with no bar "
        "for the session; 0 answered with no bar at all; 0 dropped after their batch failed twice; "
        "3 duplicate bar(s) dropped"], messages


def test_a_scan_with_no_duplicate_bars_says_so_rather_than_saying_nothing(fake_alpaca, ohlcv, caplog):
    """The inverse, and the state every night so far has been in: the count is
    0, the warning is absent, and the coverage line still carries the clause --
    so an operator reading the first live duplicate off an Actions log can tell
    it from a run that never counted."""
    universe = _coverage(fake_alpaca, ohlcv, fresh=8, stale=1)
    stats: dict = {}
    with caplog.at_level(logging.INFO, logger="src.scanner"):
        run_scan(ScanConfig(), universe=universe, stats=stats)

    assert stats["duplicate_bars"] == 0
    assert not [r for r in caplog.records if "sent twice" in r.getMessage()]
    assert [m for m in (r.getMessage() for r in caplog.records) if m.startswith("Coverage for ")] == [
        f"Coverage for {stats['session']}: 9 requested; 9 answered with bars, 1 of those with no bar "
        "for the session; 0 answered with no bar at all; 0 dropped after their batch failed twice; "
        "0 duplicate bar(s) dropped"]


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
    assert stats["no_bars_names"] == ["NOSUCH"] and len(stats["no_bars_names"]) == stats["no_bars"], \
        "the arithmetic count and the named list are one fact"
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

    with pytest.raises(FeedNotAuthorizedError, match=f"refused the {DEFAULT_FEED.value!r} data feed"):
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
    assert cfg.feed == DataFeed.SIP
    assert SIP_HOLDBACK_MINUTES == 16
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




def _genuine_barset(symbol: str, rows: list[dict]):
    """A real alpaca-py BarSet, the shape the SDK hands _download_batch."""
    from alpaca.data.models import BarSet

    class Client:
        def get_stock_bars(self, request):
            return BarSet({symbol: rows})

    return Client()


def _bar_rows(frame, session: date) -> list[dict]:
    """The wire rows for `frame`, ending on `session`, oldest first."""
    idx = pd.bdate_range(end=pd.Timestamp(session), periods=len(frame))
    return [{"t": (t.normalize() + pd.Timedelta(hours=4)).tz_localize("UTC").isoformat(),
             "o": float(r.Open), "h": float(r.High), "l": float(r.Low), "c": float(r.Close),
             "v": float(r.Volume), "n": 1.0, "vw": float(r.Close)}
            for t, (_, r) in zip(idx, frame.iterrows())]


def test_a_newest_first_response_is_not_read_as_a_stale_symbol(ohlcv):
    """BarSet.df keeps the response's order and the request pins no `sort`, so
    this was an assumption: a newest-first reply made _last_bar_date() read the
    OLDEST bar, every symbol read as stale, and the run died blaming a market
    holiday. Reproduced with a genuine BarSet, fixed by sorting what came back
    rather than by changing what is asked for."""
    session = date(2026, 6, 24)
    rows = _bar_rows(ohlcv("burst"), session)

    df = _download_batch(_genuine_barset("X", list(reversed(rows))), ["X"], ScanConfig(), session)["X"]

    assert _last_bar_date(df) == session
    assert df.index.is_monotonic_increasing
    assert detect_setup(df, ScanConfig()) is not None, "and the burst on the newest bar is still found"


def test_a_bar_the_feed_sent_twice_does_not_hide_the_burst(ohlcv):
    """A duplicated newest bar made iloc[-1] and iloc[-2] the same session, so
    the day's gain read as 0% and a real 4% burst was silently missed."""
    session = date(2026, 6, 24)
    rows = _bar_rows(ohlcv("burst"), session)

    df = _download_batch(_genuine_barset("X", rows + [rows[-1]]), ["X"], ScanConfig(), session)["X"]

    assert not df.index.has_duplicates
    assert len(df) == len(rows)
    assert detect_setup(df, ScanConfig()) is not None


@pytest.mark.parametrize("bars", [20, 60, 250])
def test_the_copy_the_feed_sent_last_is_the_one_kept_whatever_order_it_arrived_in(ohlcv, bars):
    """`keep="last"` means "the last copy on the wire" only if the sort in
    front of it is stable, and `sort_index()` defaults to quicksort.

    Reproduced here on pandas 3.0.5 with a genuine BarSet: a newest-first
    response whose PRELIMINARY copy of the session bar sat earlier on the wire
    than the corrected one kept the preliminary -- the volume the feed had
    already restated -- and no surface said which copy it had read.

    The length is load-bearing, which is why it is swept rather than picked.
    numpy's introsort runs insertion sort below 16 elements and insertion sort
    IS stable, so a short frame keeps the corrected copy under either sort:
    measured here, 16 bars cannot fail and 17 can.
    """
    session = date(2026, 6, 24)
    rows = _bar_rows(ohlcv("burst", days=bars), session)
    prelim = dict(rows[-1], v=1.0)
    corrected = dict(rows[-1], v=rows[-1]["v"] + 7.0)
    wire = [prelim, corrected] + list(reversed(rows[:-1]))
    assert len(wire) >= 17, "under 16 elements numpy sorts stably by accident"

    df = _download_batch(_genuine_barset("X", wire), ["X"], ScanConfig(), session)["X"]

    assert df.index.is_monotonic_increasing, "oldest first, whatever order it arrived in"
    assert not df.index.has_duplicates and len(df) == len(rows)
    assert df["Volume"].iloc[-1] == corrected["v"], (
        "the copy the feed sent LAST is the one kept; this is the preliminary one"
    )


def test_the_bars_the_feed_sent_twice_are_counted_for_the_caller(ohlcv):
    """A duplicate is resolved silently -- one of the two copies is simply
    gone -- so nothing downstream could ever say a night had had one. Counted
    per symbol, so the run can print the number and an operator can read the
    first live one off an Actions log; no other policy, because no duplicate
    has been seen yet."""
    session = date(2026, 6, 24)
    rows = _bar_rows(ohlcv("burst"), session)
    cfg = ScanConfig()

    clean: dict[str, int] = {}
    _download_batch(_genuine_barset("X", rows), ["X"], cfg, session, duplicates=clean)
    assert clean == {}, "a clean batch names no symbol"

    twice: dict[str, int] = {}
    _download_batch(_genuine_barset("X", rows + [rows[-1], rows[-1], rows[-3]]),
                    ["X"], cfg, session, duplicates=twice)
    assert twice == {"X": 3}, "every bar dropped as a duplicate is counted, not just the sessions"



def test_a_hole_before_the_session_does_not_publish_a_two_day_move_as_a_burst(ohlcv):
    """_drop_stale_symbols checks only the newest bar. A halt or a dropped bar
    the session before leaves iloc[-2] two sessions old while the frame passes
    freshness, and detect_setup() then reads the TWO-day move as the day's 4%
    burst. Reproduced with a genuine BarSet: 12.0% printed as 12.45%."""
    session = date(2026, 6, 24)
    rows = _bar_rows(ohlcv("burst"), session)
    cfg = ScanConfig()
    whole = _download_batch(_genuine_barset("X", rows), ["X"], cfg, session)
    holed = _download_batch(_genuine_barset("X", rows[:-2] + rows[-1:]), ["X"], cfg, session)
    assert _last_bar_date(holed["X"]) == session, "precondition: the hole passes freshness"

    kept, gapped = _drop_gapped_symbols(holed, session)
    assert kept == {} and gapped == {"X": pd.Timestamp(rows[-3]["t"]).date()}
    kept, gapped = _drop_gapped_symbols(whole, session)
    assert list(kept) == ["X"] and gapped == {}


def test_previous_session_is_weekend_only_arithmetic_like_current_session():
    assert previous_session(date(2026, 6, 24)) == date(2026, 6, 23)   # Wed -> Tue
    assert previous_session(date(2026, 6, 22)) == date(2026, 6, 19)   # Mon -> Fri
    assert previous_session(date(2026, 6, 20)) == date(2026, 6, 19)   # Sat -> Fri


def test_a_gapped_symbol_is_counted_and_not_scanned(fake_alpaca, ohlcv):
    """Through run_scan: the name is reported under `gapped`, not published as
    a burst and not silently dropped."""
    names = [f"G{i}" for i in range(12)]
    for i, name in enumerate(names):
        fake_alpaca.add_history(name, ohlcv("burst", variant=i))
    # The double re-dates every frame contiguously, so a hole has to be asked
    # for by name rather than cut out of the frame handed in.
    fake_alpaca.add_history("HOLE", ohlcv("burst", variant=99), gap_before_session=True)
    stats: dict = {}

    found = run_scan(ScanConfig(), universe=names + ["HOLE"], stats=stats)

    assert "HOLE" in stats["gapped"]
    assert "HOLE" not in [c.ticker for c in found]
    assert len(found) == 12
    # An ordinary day: twelve frames agree with the arithmetic, and agreeing
    # with it is not "observed" -- `<=` on the guard below called it that.
    assert stats["previous_session"] == previous_session(stats["session"])
    assert stats["previous_session_observed"] is False


def test_a_session_bar_the_feed_left_none_in_is_no_dollar_volume_and_no_crash():
    """The old dropna tolerated a None where a number belongs; a float() on
    the session's own bar would not, and that call sits outside the
    detector's try in run_scan(), so the fix for the NaN case would have
    made a None the one shape that ends the scan."""
    frame = pd.DataFrame({"Close": [10.0, None], "Volume": [1e6, None]},
                         index=pd.DatetimeIndex(["2026-09-08", "2026-09-09"]), dtype=object)
    assert frame["Close"].iloc[-1] is None, "precondition: a real None, not the NaN pandas coerces it to"
    assert session_dollar_volume(frame) is None
    frame = pd.DataFrame({"Close": [10.0, "n/a"], "Volume": [1e6, 2e6]},
                         index=pd.DatetimeIndex(["2026-09-08", "2026-09-09"])).astype(object)
    assert session_dollar_volume(frame) is None
    # And a frame with no bar at all: unreachable while _frames_by_symbol
    # drops the empty ones, and the guard is not decorative -- .iloc[-1] on
    # an empty column raises IndexError, which the clause above does not
    # catch and this call is outside the detector's try.
    assert session_dollar_volume(pd.DataFrame(columns=["Close", "Volume"])) is None


# --- the session before is read off the night's frames ---------------------
#
# A business day NO name printed is a market closure, not a hole on every
# name. Before observed_previous_session() existed the gap rule compared
# every frame against weekend-only arithmetic, so the session after every
# weekday holiday -- Tuesday 8 Sep 2026, the first scheduled night, the day
# after Labor Day -- gapped the whole universe, scanned nothing, and
# published DEGRADED with 0 bursts. Reproduced with the double and with a
# genuine BarSet before it was touched (tests/test_sdk_contract.py holds the
# BarSet one).

TUESDAY_AFTER_LABOR_DAY = date(2026, 9, 8)
LABOR_DAY = date(2026, 9, 7)


def _closed_market(fake_alpaca, ohlcv, n: int, *, prefix: str = "G", variant0: int = 0) -> list[str]:
    names = [f"{prefix}{i}" for i in range(n)]
    for i, name in enumerate(names):
        fake_alpaca.add_history(name, ohlcv("burst", variant=variant0 + i))
    fake_alpaca.close_session(LABOR_DAY)
    return names


def test_a_business_day_no_name_printed_is_a_closure_not_a_hole_on_every_name(fake_alpaca, ohlcv):
    """Every frame lacks Monday 7 Sep. The session before Tuesday's is Friday
    4 Sep, read off the night's frames, and the twelve bursts are found."""
    names = _closed_market(fake_alpaca, ohlcv, 12)
    stats: dict = {}

    found = run_scan(ScanConfig(session_date=TUESDAY_AFTER_LABOR_DAY), universe=names, stats=stats)

    assert stats["gapped"] == {}
    assert len(found) == 12
    assert stats["previous_session"] == date(2026, 9, 4)
    assert stats["previous_session_observed"] is True
    assert stats["liquidity_floor"] is not None, "the floor is drawn from names that were measured"
    assert all(c.date == "2026-09-08" for c in found)


def test_a_closure_read_off_the_batch_does_not_excuse_one_names_own_hole(fake_alpaca, ohlcv):
    """The inverse: a name halted on Friday 4 Sep, on the week of the
    closure, is still a hole -- its bar before the session is Thursday, and
    the batch says the session before was Friday."""
    names = _closed_market(fake_alpaca, ohlcv, 12)
    fake_alpaca.add_history("HOLE", ohlcv("burst", variant=99), gap_before_session=True)
    stats: dict = {}

    found = run_scan(ScanConfig(session_date=TUESDAY_AFTER_LABOR_DAY), universe=names + ["HOLE"], stats=stats)

    assert stats["gapped"] == {"HOLE": date(2026, 9, 3)}
    assert "HOLE" not in [c.ticker for c in found]
    assert len(found) == 12


def test_a_closure_is_read_only_from_the_coverage_minimum_of_voting_names(fake_alpaca, ohlcv):
    """Below coverage_guard_min_symbols the arithmetic stands unchanged --
    every `--tickers` smoke test -- so exactly one fewer than the minimum
    stays gapped on a closure and exactly the minimum votes it through.
    Pinned on the boundary because `>=` and `>` are one character apart."""
    n = ScanConfig().coverage_guard_min_symbols
    names = _closed_market(fake_alpaca, ohlcv, n)
    stats: dict = {}

    found = run_scan(ScanConfig(session_date=TUESDAY_AFTER_LABOR_DAY), universe=names[:n - 1], stats=stats)
    assert len(stats["gapped"]) == n - 1 and found == []
    assert stats["previous_session"] == LABOR_DAY and stats["previous_session_observed"] is False

    found = run_scan(ScanConfig(session_date=TUESDAY_AFTER_LABOR_DAY), universe=names, stats=stats)
    assert stats["gapped"] == {} and len(found) == n
    assert stats["previous_session_observed"] is True


def test_a_split_vote_moves_the_previous_session_nowhere(fake_alpaca, ohlcv):
    """MORE than half, not half: ten names whose bar before the session is
    Friday and ten whose is Thursday (halted Friday) agree on nothing, so the
    arithmetic stands and every one of them is a hole. One more on Friday's
    side and it is a closure with nine holes."""
    friday = _closed_market(fake_alpaca, ohlcv, 10, prefix="F")
    thursday = [f"T{i}" for i in range(10)]
    for i, name in enumerate(thursday):
        fake_alpaca.add_history(name, ohlcv("burst", variant=20 + i), gap_before_session=True)
    cfg = ScanConfig(session_date=TUESDAY_AFTER_LABOR_DAY)
    stats: dict = {}

    found = run_scan(cfg, universe=friday + thursday, stats=stats)
    assert found == [] and len(stats["gapped"]) == 20
    assert stats["previous_session_observed"] is False

    fake_alpaca.add_history("F10", ohlcv("burst", variant=40))
    found = run_scan(cfg, universe=friday + ["F10"] + thursday, stats=stats)
    assert sorted(c.ticker for c in found) == sorted(friday + ["F10"])
    assert set(stats["gapped"]) == set(thursday)


def test_the_vote_is_over_the_whole_scan_and_not_each_batch(fake_alpaca, ohlcv):
    """A closure is a fact about the market, so the last batch of a universe
    -- three names when the file is 103 long -- must not fall below the
    minimum and be read as three holes while the batches before it read the
    closure."""
    names = _closed_market(fake_alpaca, ohlcv, 13)
    stats: dict = {}

    found = run_scan(ScanConfig(session_date=TUESDAY_AFTER_LABOR_DAY, batch_size=10),
                     universe=names, stats=stats)

    assert stats["gapped"] == {} and len(found) == 13


def _frames_whose_bar_before_the_session_is(days: list[date], session: date, n: int) -> dict:
    """`n` frames indexed on `days` then `session`, one row each."""
    out = {}
    for i in range(n):
        index = pd.DatetimeIndex([pd.Timestamp(d) for d in days] + [pd.Timestamp(session)])
        out[f"P{i}"] = pd.DataFrame({"Close": 10.0, "Volume": 1e6}, index=index)
    return out


def test_a_majority_can_move_the_previous_session_back_and_never_forward():
    """A phantom bar -- a Saturday every frame carries -- is LATER than the
    arithmetic, and must not become the previous session: a majority can
    only push the answer back, so a phantom can never manufacture one. The
    same frames with an earlier shared bar do move it."""
    from src.scanner import observed_previous_session

    monday, saturday, friday, thursday = (date(2026, 9, 14), date(2026, 9, 12),
                                          date(2026, 9, 11), date(2026, 9, 10))
    cfg = ScanConfig()
    phantom = _frames_whose_bar_before_the_session_is([friday, saturday], monday, 12)
    assert observed_previous_session(phantom, monday, cfg) == (friday, False)
    # And the gap rule then refuses all twelve, which is the half this test
    # was missing: it built the frames that expose `before >= want` and never
    # ran them through the rule, so the phantom protection the round rests on
    # could be widened to `>=` -- keeping every frame and measuring each burst
    # against the Saturday -- with the whole suite green.
    kept, gapped = _drop_gapped_symbols(phantom, monday, friday)
    assert kept == {} and sorted(gapped) == sorted(f"P{i}" for i in range(12))
    assert set(gapped.values()) == {saturday}

    earlier = _frames_whose_bar_before_the_session_is([thursday], monday, 12)
    assert observed_previous_session(earlier, monday, cfg) == (thursday, True)
    assert previous_session(monday) == friday, "precondition: the arithmetic says Friday"


def test_a_frame_with_one_bar_has_no_vote_and_stays_a_hole():
    """A single-bar frame carries no bar before the session, so it says
    nothing about what that session was: ten such frames beside ten that
    agree on Thursday are ten of ten voting, not ten of twenty. And each of
    them is still refused by the gap rule, as before."""
    from src.scanner import observed_previous_session

    monday, thursday = date(2026, 9, 14), date(2026, 9, 10)
    cfg = ScanConfig()
    frames = _frames_whose_bar_before_the_session_is([thursday], monday, 10)
    for i in range(10):
        frames[f"S{i}"] = pd.DataFrame({"Close": 10.0, "Volume": 1e6},
                                       index=pd.DatetimeIndex([pd.Timestamp(monday)]))

    assert observed_previous_session(frames, monday, cfg) == (thursday, True)
    kept, gapped = _drop_gapped_symbols(frames, monday, thursday)
    assert sorted(kept) == sorted(f"P{i}" for i in range(10))
    assert sorted(gapped) == sorted(f"S{i}" for i in range(10))
    # And with NO voter at all and the minimum switched off, the arithmetic
    # stands rather than max() raising over an empty vote.
    alone = {k: v for k, v in frames.items() if k.startswith("S")}
    assert observed_previous_session(alone, monday, ScanConfig(coverage_guard_min_symbols=0)) == (
        previous_session(monday), False)


def test_a_nat_in_a_frames_index_neither_votes_nor_takes_the_scan_down():
    """pd.Timestamp(NaT).date() is NaT again and cannot be compared with a
    date -- the L2 shape from round 9, one function over."""
    from src.scanner import observed_previous_session

    monday, thursday = date(2026, 9, 14), date(2026, 9, 10)
    frames = _frames_whose_bar_before_the_session_is([thursday], monday, 10)
    # As many NaT frames as voters: a NaT that counted would be half the
    # electorate and turn ten of ten into ten of twenty, which is how the
    # first version of this test, with one NaT frame, let the check be
    # deleted green -- the NaT was never compared and never tipped a vote.
    for i in range(10):
        frames[f"NAT{i}"] = pd.DataFrame({"Close": 10.0, "Volume": 1e6},
                                         index=pd.DatetimeIndex([pd.NaT, pd.Timestamp(monday)]))

    assert observed_previous_session(frames, monday, ScanConfig()) == (thursday, True)
    kept, gapped = _drop_gapped_symbols(frames, monday, thursday)
    assert sorted(gapped) == sorted(f"NAT{i}" for i in range(10)) and not any(k.startswith("NAT") for k in kept)


def test_a_name_that_printed_the_session_before_is_the_disproof_of_a_closure(fake_alpaca, ohlcv):
    """A closure is a business day NO name printed, and the batch already
    holds the answer. Seven names halted on Tuesday and five that traded it
    used to give the seven a bare majority: the arithmetic moved back to
    Monday, the FIVE healthy names became holes and the seven broken ones
    were measured across theirs -- seven Monday-to-Wednesday moves published
    as the day's 4% burst, which is the defect the gap rule exists to
    prevent, produced by its own vote. One frame carrying a bar for the
    session before is the disproof, and it is decisive."""
    session = date(2026, 9, 9)
    healthy = [f"H{i}" for i in range(5)]
    holed = [f"K{i}" for i in range(7)]
    for i, name in enumerate(healthy):
        fake_alpaca.add_history(name, ohlcv("burst", variant=i))
    for i, name in enumerate(holed):
        fake_alpaca.add_history(name, ohlcv("burst", variant=20 + i), gap_before_session=True)
    stats: dict = {}

    found = run_scan(ScanConfig(session_date=session), universe=healthy + holed, stats=stats)

    assert stats["previous_session"] == date(2026, 9, 8)
    assert stats["previous_session_observed"] is False
    assert sorted(stats["gapped"]) == sorted(holed)
    assert sorted(c.ticker for c in found) == sorted(healthy)


def test_the_disproof_is_read_off_every_frame_the_scan_downloaded_and_not_only_the_voters(
    fake_alpaca, ohlcv
):
    """A name that stopped printing ON the session before still printed on
    it, so it says the market traded that day -- and it is not a voter,
    because a stale frame's newest bar is not the bar before the session.
    Twelve names halted on Tuesday agree on Monday among themselves; ten
    names whose last bar IS Tuesday are the evidence that Tuesday was a
    session, and they are in the batch."""
    session = date(2026, 9, 9)
    holed = [f"K{i}" for i in range(12)]
    quit_on_tuesday = [f"S{i}" for i in range(10)]
    for i, name in enumerate(holed):
        fake_alpaca.add_history(name, ohlcv("burst", variant=i), gap_before_session=True)
    for i, name in enumerate(quit_on_tuesday):
        fake_alpaca.add_history(name, ohlcv("flat", variant=i), stale_sessions=1)
    stats: dict = {}

    found = run_scan(ScanConfig(session_date=session), universe=holed + quit_on_tuesday, stats=stats)

    assert stats["previous_session"] == date(2026, 9, 8)
    assert stats["previous_session_observed"] is False
    assert stats["previous_session_printed"] == 10
    assert sorted(stats["gapped"]) == sorted(holed) and found == []


def test_only_the_fresh_frames_vote_on_what_the_session_before_was(fake_alpaca, ohlcv):
    """The population is the whole rule: a stale frame's evidence is about an
    earlier week, so it cannot say what the session before THIS one was.
    Four names that traded Tuesday after the Monday closure carry Friday as
    the bar before it; five that stopped printing on Thursday carry Thursday.
    Voting over every frame gives Thursday a 5-4 majority and turns the four
    names that actually traded into holes. The two coverage fractions are
    relaxed so the scan reports rather than raises: what is under test is
    who votes."""
    fresh = [f"F{i}" for i in range(4)]
    for i, name in enumerate(fresh):
        fake_alpaca.add_history(name, ohlcv("burst", variant=i))
    for i, name in enumerate([f"D{i}" for i in range(5)]):
        fake_alpaca.add_history(name, ohlcv("flat", variant=i), stale_sessions=3)
    fake_alpaca.close_session(LABOR_DAY)
    cfg = ScanConfig(session_date=TUESDAY_AFTER_LABOR_DAY, coverage_guard_min_symbols=3,
                     max_stale_fraction=0.9)
    stats: dict = {}

    found = run_scan(cfg, universe=fresh + [f"D{i}" for i in range(5)], stats=stats)

    assert stats["previous_session"] == date(2026, 9, 4)
    assert stats["previous_session_observed"] is True
    assert sorted(c.ticker for c in found) == sorted(fresh) and stats["gapped"] == {}
    # And the minimum the run's own report cites is the one this run applied,
    # not the default it happens to equal on most nights.
    assert stats["closure_min_symbols"] == cfg.coverage_guard_min_symbols == 3


def test_a_weekend_phantom_earlier_than_the_arithmetic_is_not_the_session_before():
    """"A majority can only move the answer back, so a phantom can never
    manufacture a session" is true only of a phantom LATER than the
    arithmetic. The day after a weekday holiday opens a window of non-session
    dates EARLIER than it: twelve frames whose bar before Tuesday 8 Sep is a
    phantom Sunday 6 Sep used to elect the Sunday, and every burst was then
    measured against a bar the market never printed. The winner has to be a
    business day -- weekends are the only calendar this file has."""
    from src.scanner import observed_previous_session

    tuesday, sunday, friday = date(2026, 9, 8), date(2026, 9, 6), date(2026, 9, 4)
    frames = _frames_whose_bar_before_the_session_is([friday, sunday], tuesday, 12)

    assert previous_session(tuesday) == date(2026, 9, 7), "precondition: the arithmetic says Monday"
    assert observed_previous_session(frames, tuesday, ScanConfig()) == (date(2026, 9, 7), False)
    # The same frames with a business day in the phantom's place DO move it.
    real = _frames_whose_bar_before_the_session_is([friday], tuesday, 12)
    assert observed_previous_session(real, tuesday, ScanConfig()) == (friday, True)


# --- the bar the detector measured has to be the session's ------------------


def _nan_on_the_session_bar(ohlcv, column: str) -> pd.DataFrame:
    """A 12% burst, then one more ordinary bar whose `column` is NaN."""
    burst = ohlcv("burst")
    after = burst.iloc[[-1]].copy()
    after.index = pd.DatetimeIndex([burst.index[-1] + pd.offsets.BDay(1)], name=burst.index.name)
    after[column] = float("nan")
    return pd.concat([burst, after])


@pytest.mark.parametrize("column", ["Volume", "Close"])
def test_a_nan_on_the_session_bar_does_not_publish_the_previous_sessions_burst_as_tonights(
    fake_alpaca, ohlcv, column
):
    """detect_setup() drops the NaN bar and measures the one before it, so
    the burst of 8 Sep came back dated 8 Sep on a scan of 9 Sep, with stale
    and gapped both empty, and the pipeline published it under the session
    with status ok. The scan refuses and counts the unreadable current bar
    before detection, and session_dollar_volume() reads the
    session's own bar rather than the last one it can read."""
    session = date(2026, 9, 9)
    fake_alpaca.add_history("NANV", _nan_on_the_session_bar(ohlcv, column))
    quiet = [f"Q{i}" for i in range(11)]
    for i, name in enumerate(quiet):
        fake_alpaca.add_history(name, ohlcv("flat", variant=i))
    stats: dict = {}

    found = run_scan(ScanConfig(session_date=session), universe=["NANV"] + quiet, stats=stats)

    assert found == []
    assert stats["off_session"] == {}
    assert list(stats["invalid_bars"]) == ["NANV"]
    assert stats["stale"] == {} and stats["gapped"] == {}, "neither rule sees it: the session bar is there"
    served = fake_alpaca.bars_frame(["NANV"], end=session).loc["NANV"].rename(columns=str.capitalize)
    assert session_dollar_volume(served) is None, "no readable session bar, no place in the distribution"


def _nan_on_the_bar_before_the_session(ohlcv, column: str) -> pd.DataFrame:
    """A 12% burst whose PREVIOUS bar carries no readable `column`."""
    frame = ohlcv("burst").copy()
    frame.iloc[-2, frame.columns.get_loc(column)] = float("nan")
    return frame


@pytest.mark.parametrize("column", ["Volume", "Close"])
def test_a_nan_on_the_bar_before_the_session_is_a_hole_and_not_a_two_session_burst(
    fake_alpaca, ohlcv, column
):
    """The sibling one bar over. The gap rule read the RAW index, so a bar
    that is present but carries no readable close or volume passed it as a
    bar -- while detect_setup() drops exactly those bars before reading
    iloc[-2], and measured the session against the one TWO back. A
    two-session move was published as the day's 4%, dated to the session,
    with stale, gapped and off_session all empty and status ok. The rule
    reads the frame the detector will measure now: a bar it cannot read is
    a hole, and a frame with a hole cannot say what the session before did."""
    session = date(2026, 9, 9)
    fake_alpaca.add_history("NANB", _nan_on_the_bar_before_the_session(ohlcv, column))
    quiet = [f"Q{i}" for i in range(11)]
    for i, name in enumerate(quiet):
        fake_alpaca.add_history(name, ohlcv("flat", variant=i))
    stats: dict = {}
    served = fake_alpaca.bars_frame(["NANB"], end=session).loc["NANB"]
    assert previous_session(session) in {pd.Timestamp(t).date() for t in served.index}, (
        "precondition: the bar IS there -- it is the reading of it that fails, "
        "which is why an index-based hole check could not see it")

    found = run_scan(ScanConfig(session_date=session), universe=["NANB"] + quiet, stats=stats)

    assert found == []
    assert stats["gapped"] == {"NANB": date(2026, 9, 7)}
    assert stats["stale"] == {} and stats["off_session"] == {}, "the session's own bar is readable"


def test_a_nat_on_the_newest_bar_is_a_stale_name_without_a_date_and_not_a_TypeError(
    fake_alpaca, ohlcv, monkeypatch
):
    """pd.Timestamp(NaT).date() is NaT again and cannot be compared with a
    date. _bar_before_session() refuses it and _last_bar_date() did not, so
    a NaT on the newest bar was filed as a stale name whose date is NaT and
    the all-stale guard's max() raised TypeError -- in place of the
    StaleDataError whose message tells the operator the market may not have
    traded or the session may still be open. The same shape as the guarded
    case, one function over, on the night the guarded one fires."""
    import src.scanner as scanner_mod

    session = date(2026, 9, 9)
    names = [f"N{i}" for i in range(20)]
    for i, name in enumerate(names):
        fake_alpaca.add_history(name, ohlcv("flat", variant=i), stale_sessions=3)
    real = scanner_mod._download_batch

    def _with_nat(client, tickers, cfg, session_, **kw):
        out = real(client, tickers, cfg, session_, **kw)
        # As many NaT frames as dated ones, so a guard that never compares
        # them cannot pass by accident.
        for ticker in list(out)[:10]:
            index = list(out[ticker].index[:-1]) + [pd.NaT]
            out[ticker] = out[ticker].set_axis(pd.DatetimeIndex(index))
        return out

    monkeypatch.setattr(scanner_mod, "_download_batch", _with_nat)
    stats: dict = {}

    with pytest.raises(StaleDataError) as raised:
        run_scan(ScanConfig(session_date=session), universe=names, stats=stats)

    assert "newest seen" in str(raised.value)
    assert len(stats["stale"]) == 20
    assert sum(1 for last in stats["stale"].values() if last is None) == 10, (
        "an unreadable stamp is stale with no date, not a NaT in the record")


def test_a_detector_that_raises_on_every_symbol_is_not_a_quiet_market(fake_alpaca, ohlcv, monkeypatch):
    """The one path the coverage guards did not cover. A pandas API change
    that makes detect_setup raise on every frame used to be swallowed per
    symbol with no count, so the scan returned [] and raised nothing -- the
    exact shape every guard in this module exists to prevent."""
    import src.scanner as scanner_mod

    names = [f"B{i}" for i in range(12)]
    for i, name in enumerate(names):
        fake_alpaca.add_history(name, ohlcv("burst", variant=i))
    stats: dict = {}
    assert len(run_scan(ScanConfig(), universe=names, stats=stats)) == 12, "precondition: healthy"

    def boom(df, cfg):
        raise AttributeError("'Series' object has no attribute 'iloc'")
    monkeypatch.setattr(scanner_mod, "detect_setup", boom)

    with pytest.raises(IncompleteScanError, match="raised on every one"):
        run_scan(ScanConfig(), universe=names, stats=stats)
    assert len(stats["detector_errors"]) == 12


def test_one_symbol_the_detector_cannot_read_is_counted_and_the_scan_goes_on(fake_alpaca, ohlcv, monkeypatch):
    """The other half: a single bad frame is one symbol's problem, reported
    in the stats and not fatal."""
    import src.scanner as scanner_mod

    names = [f"B{i}" for i in range(12)]
    for i, name in enumerate(names):
        fake_alpaca.add_history(name, ohlcv("burst", variant=i))
    real = scanner_mod.detect_setup
    calls = []

    # The FIRST frame only. Not "the frame whose close is B3's": the synthetic
    # burst pins the same final close on every seed, so that raised on ten of
    # twelve and the test asserted a number the harness had invented.
    def one_bad(df, cfg):
        calls.append(1)
        if len(calls) == 1:
            raise ValueError("a dtype surprise")
        return real(df, cfg)
    monkeypatch.setattr(scanner_mod, "detect_setup", one_bad)
    stats: dict = {}

    found = run_scan(ScanConfig(), universe=names, stats=stats)

    assert len(found) == 11
    assert len(stats["detector_errors"]) == 1
    assert "ValueError: a dtype surprise" in next(iter(stats["detector_errors"].values()))


# --- the two boundaries the last audit found unpinned --------------------

def test_the_coverage_guard_fires_at_exactly_its_minimum_universe(fake_alpaca, ohlcv):
    """`>=` on coverage_guard_min_symbols, and no test sat on the boundary:
    changing it to `>` left the whole suite green, so a scan of exactly the
    minimum that was half stale would silently have stopped raising."""
    cfg = ScanConfig()
    n = cfg.coverage_guard_min_symbols
    names = [f"S{i}" for i in range(n)]
    for i, name in enumerate(names):
        fake_alpaca.add_history(name, ohlcv("burst", variant=i),
                                stale_sessions=1 if i < n // 2 else 0)

    with pytest.raises(StaleDataError):
        run_scan(cfg, universe=names)


def test_a_status_less_refusal_whose_body_says_not_permitted_is_permanent():
    """The `or "not permitted" in text` clause was exercised by no test, so
    it was a claim about Alpaca's wording nobody had checked and nothing
    would notice being deleted."""
    from src.scanner import _is_permanent_refusal

    assert _is_permanent_refusal(_alpaca_error(None, "this endpoint is not permitted for your plan"))
    assert not _is_permanent_refusal(_alpaca_error(None, "internal server error"))


def test_the_frames_handed_back_include_the_names_the_session_rules_dropped(fake_alpaca, ohlcv):
    """`frames=` used to receive the frames AFTER the stale and gap rules,
    so the universe benchmark five sessions later was "the names that traded
    cleanly tonight" wearing the universe's name: a name halted today, or
    with a hole before today's session, traded the earlier session like any
    other and was left out of its alternative. The rules are about tonight;
    the frames are handed back before them, and the ledger reads each
    horizon by its session so a hole there is null rather than borrowed."""
    names = [f"F{i}" for i in range(12)]
    for i, name in enumerate(names):
        fake_alpaca.add_history(name, ohlcv("burst", variant=i))
    fake_alpaca.add_history("STALE", ohlcv("base", variant=90), stale_sessions=3)
    fake_alpaca.add_history("HOLE", ohlcv("base", variant=91), gap_before_session=True)
    stats: dict = {}
    frames: dict = {}

    found = run_scan(ScanConfig(), universe=names + ["STALE", "HOLE"], stats=stats, frames=frames)

    assert "STALE" in stats["stale"] and "HOLE" in stats["gapped"], "precondition: both were dropped tonight"
    assert {c.ticker for c in found} == set(names)
    assert set(frames) == set(names) | {"STALE", "HOLE"}, "every frame with bars, dropped or not"
    assert len(frames["STALE"]) > 0 and len(frames["HOLE"]) > 0


# --- the first live run: the feed name, and the free plan's hold-back --------


def test_a_feed_name_the_endpoint_does_not_take_is_refused_on_the_first_batch(fake_alpaca, ohlcv):
    """Observed on Actions on 6 Sep 2026, the first run ever past preflight:
    {"message":"invalid feed: delayed_sip"} on every batch, both attempts,
    for a key the endpoint had just accepted. It carried no status the
    classifier knew, so it was retried and dropped six times over and the
    coverage guard then called the result an empty market. A feed NAME the
    endpoint refuses is a property of the run, like a plan that lacks it."""
    fake_alpaca.add_history("AAA", ohlcv("burst"))
    fake_alpaca.raise_on_bars = _alpaca_error(None, "invalid feed: delayed_sip")

    with pytest.raises(FeedNotAuthorizedError) as caught:
        run_scan(ScanConfig(feed=DataFeed.DELAYED_SIP), universe=["AAA"])

    said = str(caught.value)
    assert "delayed_sip" in said and "does not take the feed name" in said
    assert "'sip'" in said and "'iex'" in said, "both routes that are known to exist"
    assert "subscribe" not in said, "no plan carries a name the endpoint refuses"
    assert len(fake_alpaca.bar_requests) == 1, "not retried, not dropped: refused once"


def test_the_default_feed_is_the_consolidated_tape_and_not_the_name_the_endpoint_refused():
    assert DEFAULT_FEED is DataFeed.SIP
    assert ScanConfig().feed is DataFeed.SIP


def test_a_sip_request_for_todays_session_is_held_back_behind_the_clock(fake_alpaca, ohlcv):
    """Alpaca's rule for a plan without a real-time subscription: a SIP
    query's end must be at least fifteen minutes old. An evening run at
    18:16 ET used to ask through 23:59 UTC, hours in the future; on `sip`
    it asks through SIP_HOLDBACK_MINUTES before now. A backfill of an older
    session is untouched, and so is every other feed."""
    fake_alpaca.add_history("AAA", ohlcv("burst"))
    client = get_clients()
    session = date(2026, 6, 24)
    evening = datetime(2026, 6, 24, 22, 16, tzinfo=timezone.utc)          # 18:16 ET, the cron
    # The double records the SDK's own to_request_fields(), where `end` is
    # the ISO string that goes on the wire.
    wire_end = lambda: datetime.fromisoformat(fake_alpaca.request_fields[-1]["end"])   # noqa: E731

    _download_batch(client, ["AAA"], ScanConfig(feed=DataFeed.SIP), session, now=evening)
    # The instant in digits, not `evening - SIP_HOLDBACK_MINUTES`: that compared
    # the value against the name it came from, and passed with the constant
    # at 0. The constant itself is pinned beside the other thresholds.
    assert wire_end() == datetime(2026, 6, 24, 22, 0, tzinfo=timezone.utc), wire_end()
    assert wire_end() > datetime(2026, 6, 24, 20, 0, tzinfo=timezone.utc), "still after the 16:00 ET close"

    _download_batch(client, ["AAA"], ScanConfig(feed=DataFeed.SIP), date(2026, 6, 17), now=evening)
    assert wire_end() == datetime(2026, 6, 17, 23, 59, 59, tzinfo=timezone.utc), (
        "a session already behind the clock keeps its own day's end")

    # Every feed alpaca-py names except sip, not IEX alone: the rule is "sip
    # alone", and a check that sampled one other member let a mutant holding
    # back every feed but IEX through the whole file green.
    for other in (f for f in DataFeed if f is not DataFeed.SIP):
        _download_batch(client, ["AAA"], ScanConfig(feed=other), session, now=evening)
        assert wire_end() == datetime(2026, 6, 24, 23, 59, 59, tzinfo=timezone.utc), (
            f"{other.value}: no other feed was observed to need the hold-back, so none gets it")


def test_a_sip_request_for_a_session_the_clock_has_not_reached_goes_out_as_written(fake_alpaca, ohlcv):
    """No schedule produces this -- a session pinned AHEAD of the clock -- but
    the offline suite does, on purpose: every end-to-end test that stands in
    for a later night pins a session days ahead of the wall clock, and the
    double re-dates each frame to the request's `end`. A hold-back that read
    the real clock there ended the window on the day before the session and
    five pipeline tests failed on any date before the one they pinned, which
    is the clock-dependent test this project names as the worst kind. So the
    window is held back only once the clock has reached the session's day;
    before it, the request goes out as written -- what the endpoint then
    says is _download_batch's docstring's business, and it is not flattering."""
    fake_alpaca.add_history("AAA", ohlcv("burst"))
    client = get_clients()
    evening = datetime(2026, 6, 24, 22, 16, tzinfo=timezone.utc)
    wire_end = lambda: datetime.fromisoformat(fake_alpaca.request_fields[-1]["end"])   # noqa: E731

    _download_batch(client, ["AAA"], ScanConfig(feed=DataFeed.SIP), date(2026, 6, 25), now=evening)
    assert wire_end() == datetime(2026, 6, 25, 23, 59, 59, tzinfo=timezone.utc), wire_end()

    # The first sixteen minutes of the session's UTC day -- 20:00 to 20:16 ET
    # the evening before: the raw clock has reached the day and the held-back
    # one has not, and a guard on the raw clock would clamp the window onto
    # the day BEFORE the session. A test in this suite that pins the next
    # session would then flicker for those minutes every night.
    _download_batch(client, ["AAA"], ScanConfig(feed=DataFeed.SIP), date(2026, 6, 25),
                    now=datetime(2026, 6, 25, 0, 5, tzinfo=timezone.utc))
    assert wire_end() == datetime(2026, 6, 25, 23, 59, 59, tzinfo=timezone.utc), wire_end()

    # The day itself, reached: held back like any other.
    _download_batch(client, ["AAA"], ScanConfig(feed=DataFeed.SIP), date(2026, 6, 25),
                    now=datetime(2026, 6, 25, 22, 16, tzinfo=timezone.utc))
    assert wire_end() == datetime(2026, 6, 25, 22, 0, tzinfo=timezone.utc), wire_end()


def test_a_trading_weekday_is_monday_to_friday_in_market_time():
    """The weekday half of session_has_closed(), pinned on real instants the
    way the close is. Market time, not UTC: Friday 23:30 ET is Saturday in
    UTC and is still a trading weekday. Labor Day is a Monday and a trading
    weekday to this arithmetic; the scan is what finds no bar for it."""
    from src.scanner import is_trading_weekday, session_has_closed

    assert is_trading_weekday(datetime(2026, 9, 5, 22, 16, tzinfo=timezone.utc)) is False   # Saturday
    assert is_trading_weekday(datetime(2026, 9, 6, 5, 34, tzinfo=timezone.utc)) is False    # Sunday
    assert is_trading_weekday(datetime(2026, 9, 7, 22, 16, tzinfo=timezone.utc)) is True    # Labor Day
    assert is_trading_weekday(datetime(2026, 9, 5, 3, 30, tzinfo=timezone.utc)) is True     # Fri 23:30 ET
    assert session_has_closed(datetime(2026, 9, 5, 3, 30, tzinfo=timezone.utc)) is True
    assert session_has_closed(datetime(2026, 9, 5, 22, 16, tzinfo=timezone.utc)) is False
