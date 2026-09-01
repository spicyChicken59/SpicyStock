"""Layer 1 -- the burst detector and the Alpaca boundary.

Deliberately no threshold assertions: step 4 replaces the absolute
5,000,000-share floor with a relative one. What is asserted here is that a
flat series is not a setup, an unmistakable burst is, and the scan wires
through a mocked Alpaca client without a key or a socket.
"""

from __future__ import annotations

import pathlib

import pytest

from src.scanner import Candidate, ScanConfig, detect_setup, get_clients, run_scan


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


# --- the rejection paths. Rewritten after mutation testing showed the first
# version was not load-bearing: it set today's volume to prev-1, which was also
# below the 5,000,000 floor, so the rejection it observed was rule 3's, not
# rule 2's. Deleting rule 2 -- or rule 1, the 4% gain the product is named
# after -- left the suite green.
#
# Each test below now fails EXACTLY ONE rule and asserts that the frame it
# started from still passes, so the rejection can only be the named rule's.
# Still threshold-agnostic: every boundary is read off ScanConfig.

FLOOR_HEADROOM = 1_500_000


def _passing(ohlcv):
    frame = ohlcv("burst").copy()
    cfg = ScanConfig()
    # Lift both volumes clear of the floor so a rule-2 violation cannot also
    # trip rule 3, which is exactly how the first version of this test failed.
    vol = frame.columns.get_loc("Volume")
    frame.iloc[-1, vol] = cfg.min_today_volume + 2 * FLOOR_HEADROOM
    frame.iloc[-2, vol] = cfg.min_today_volume + FLOOR_HEADROOM
    assert detect_setup(frame, cfg) is not None, "the baseline frame must pass every rule"
    return frame


def test_rule1_a_gain_below_the_threshold_is_rejected(ohlcv):
    """The 4% gain. Deleting this rule used to leave the suite green."""
    cfg = ScanConfig()
    frame = _passing(ohlcv)
    close = frame.columns.get_loc("Close")
    prev_close = float(frame["Close"].iloc[-2])
    # A gain of a quarter the threshold, with the price still clear of the floor.
    frame.iloc[-1, close] = prev_close * (1 + cfg.min_gain_pct / 400)
    assert float(frame["Close"].iloc[-1]) > cfg.min_price
    assert float(frame["Volume"].iloc[-1]) > cfg.min_today_volume
    assert float(frame["Volume"].iloc[-1]) >= float(frame["Volume"].iloc[-2])
    assert detect_setup(frame, cfg) is None


def test_rule2_volume_below_the_previous_day_is_rejected(ohlcv):
    cfg = ScanConfig()
    frame = _passing(ohlcv)
    vol = frame.columns.get_loc("Volume")
    # Below yesterday, but still clear of the floor, so only rule 2 can fire.
    frame.iloc[-1, vol] = float(frame["Volume"].iloc[-2]) - 1
    assert float(frame["Volume"].iloc[-1]) > cfg.min_today_volume
    assert detect_setup(frame, cfg) is None


def test_rule3_volume_at_or_below_the_floor_is_rejected(ohlcv):
    cfg = ScanConfig()
    frame = _passing(ohlcv)
    vol = frame.columns.get_loc("Volume")
    # At the floor, and still >= yesterday, so only rule 3 can fire.
    frame.iloc[-1, vol] = cfg.min_today_volume
    frame.iloc[-2, vol] = cfg.min_today_volume - 1
    assert detect_setup(frame, cfg) is None


def test_rule5_price_at_or_below_the_floor_is_rejected(ohlcv):
    cfg = ScanConfig()
    frame = _passing(ohlcv)
    # Scale the whole OHLC band so the gain percentage is untouched and only
    # the price floor can reject it.
    scale = cfg.min_price / float(frame["Close"].iloc[-1])
    for col in ("Open", "High", "Low", "Close"):
        frame[col] = frame[col] * scale
    assert detect_setup(frame, cfg) is None


def test_a_zero_previous_close_cannot_divide(ohlcv):
    frame = _passing(ohlcv)
    frame.iloc[-2, frame.columns.get_loc("Close")] = 0.0
    assert detect_setup(frame, ScanConfig()) is None


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
