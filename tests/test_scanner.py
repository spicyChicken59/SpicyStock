"""Layer 1 -- the burst detector and the Alpaca boundary.

Deliberately no threshold assertions: step 4 replaces the absolute
5,000,000-share floor with a relative one. What is asserted here is that a
flat series is not a setup, an unmistakable burst is, and the scan wires
through a mocked Alpaca client without a key or a socket.
"""

from __future__ import annotations

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


# --- the rejection paths, added after the batch-1 audit found detect_setup was
# tested on one of its five rules: every fixture bailed at rule 1 (gain < 4%),
# so rules 2, 3 and 5 and the prev_close guard had no coverage at all.
# Still threshold-agnostic: each case mutates a frame that otherwise passes,
# and reads the boundary off ScanConfig rather than hard-coding a number.

def _passing(ohlcv):
    frame = ohlcv("burst")
    assert detect_setup(frame, ScanConfig()) is not None, "fixture must pass first"
    return frame


def test_rule2_volume_below_the_previous_day_is_rejected(ohlcv):
    frame = _passing(ohlcv).copy()
    frame.iloc[-1, frame.columns.get_loc("Volume")] = frame["Volume"].iloc[-2] - 1
    assert detect_setup(frame, ScanConfig()) is None


def test_rule3_volume_at_or_below_the_floor_is_rejected(ohlcv):
    cfg = ScanConfig()
    frame = _passing(ohlcv).copy()
    frame.iloc[-1, frame.columns.get_loc("Volume")] = cfg.min_today_volume
    frame.iloc[-2, frame.columns.get_loc("Volume")] = cfg.min_today_volume - 1
    assert detect_setup(frame, cfg) is None


def test_rule5_price_at_or_below_the_floor_is_rejected(ohlcv):
    cfg = ScanConfig()
    frame = _passing(ohlcv).copy()
    scale = cfg.min_price / float(frame["Close"].iloc[-1])
    for col in ("Open", "High", "Low", "Close"):
        frame[col] = frame[col] * scale
    assert detect_setup(frame, cfg) is None


def test_a_zero_previous_close_cannot_divide(ohlcv):
    frame = _passing(ohlcv).copy()
    frame.iloc[-2, frame.columns.get_loc("Close")] = 0.0
    assert detect_setup(frame, ScanConfig()) is None


def test_the_production_path_reads_the_symbol_file(fake_alpaca, ohlcv, tmp_path):
    """Every other end-to-end test passes tickers=, so run_scan(universe=None)
    -- the path the cron actually takes -- was never executed."""
    symbols = tmp_path / "symbols.txt"
    symbols.write_text("# a comment\n\nAAPL\nMSFT\n")
    fake_alpaca.add_history("AAPL", ohlcv("burst"))
    fake_alpaca.add_history("MSFT", ohlcv("flat"))
    found = run_scan(ScanConfig(), symbols_file=str(symbols))
    assert [c.ticker for c in found] == ["AAPL"]
