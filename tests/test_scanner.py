"""Layer 1 -- the burst detector, the Alpaca request, and freshness.

Deliberately no threshold assertions: step 4 replaces the absolute
5,000,000-share floor with a relative one. What is asserted here is that a
flat series is not a setup, an unmistakable burst is, the scan wires through a
mocked Alpaca client without a key or a socket, and the request that goes on
the wire names the adjustment, the feed and both ends of its window.
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
    current_session,
    detect_setup,
    get_clients,
    run_scan,
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
