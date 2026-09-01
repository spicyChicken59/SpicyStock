"""Layer 1 -- the burst detector, the Alpaca request, and freshness.

The scan filter's thresholds ARE asserted now (step 4). Every boundary is
read off ScanConfig rather than written out as a number, so retuning one does
not silently rewrite what is under test, and every rejection test first proves
that the rule it names is the only one failing -- see _only_failing().
"""

from __future__ import annotations

import json
import pathlib
import time
from datetime import date, datetime, timedelta, timezone

import pytest
import requests
from alpaca.common.exceptions import APIError
from alpaca.data.enums import Adjustment, DataFeed
from requests.exceptions import HTTPError

from src.scanner import (
    MARKET_TZ,
    Candidate,
    FeedNotAuthorizedError,
    ScanConfig,
    StaleDataError,
    apply_liquidity_gate,
    current_session,
    detect_setup,
    get_clients,
    liquidity_floor,
    run_scan,
    session_dollar_volume,
    trailing_volume_mean,
)


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
    """
    cfg = ScanConfig()
    checked = 0
    for variant in range(40):
        frame = ohlcv("burst", variant=variant)
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
