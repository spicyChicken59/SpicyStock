"""What alpaca-py actually does, checked without a socket.

CLAUDE.md names this the standing hole in the regression net: "the real SDK
wire shapes -- the boundaries are doubles, so an SDK change passes here". Every
other test of Layer 1 talks to tests/fakes.py, which was written by reading the
SDK rather than by running it. If the two ever disagree, the suite believes the
double.

Three claims are checkable offline, and all three are load-bearing:

1. THE REQUEST. `StockBarsRequest` is a pydantic model, so the six fields
   _download_batch() names are validated at construction. A field alpaca-py
   renames or drops raises here, in the same way `temperature` became a
   TypeError in anthropic 1.x -- the failure step 8 caught the same way, in
   tests/test_scorer.py's signature bind.

2. THE RESPONSE. `BarSet` needs no network: it is built from the decoded body,
   so a genuine one can be assembled from a synthetic frame and handed to the
   code that reads it. Its `.df` is the only thing _download_batch() knows
   about the SDK -- a MultiIndex of (symbol, timestamp), lower-case OHLCV
   columns, and tz-aware UTC timestamps the freshness check reads a session
   date out of.

3. THE DOUBLE. The last test runs one scan twice over identical inputs, once
   through FakeBarSet and once through a real BarSet, and requires the same
   candidates with the same metrics. That is the assertion the rest of the
   suite rests on: it is what makes "the fake said so" mean "the SDK would
   have said so". It is also the one test here that would notice the fake and
   the SDK drifting apart, whichever of the two moved.

The prices are still synthetic. This file pins the SHAPE of a response, never
its contents -- no test here can tell you what Alpaca would really return for
a symbol, and the frames it builds are the same made-up ones as everywhere
else.
"""

from __future__ import annotations

import inspect
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest
from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.models import BarSet
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from src.scanner import (
    ScanConfig,
    _download_batch,
    _last_bar_date,
    current_session,
    detect_setup,
    run_scan,
)

SESSION = date(2026, 6, 24)


# --------------------------------------------------------------------------
# 1. The request _download_batch() builds
# --------------------------------------------------------------------------


def _request_kwargs(cfg: ScanConfig | None = None, session: date = SESSION,
                    end: datetime | None = None) -> dict:
    """The kwargs _download_batch() passes, rebuilt from its own arithmetic.

    Written out rather than captured so this test still says what the request
    IS when the module changes; the capture test below then proves the module
    really sends these.

    `end` is the session's own day-end for a session behind the clock. On the
    sip feed on the session's own evening it is sixteen minutes behind the
    clock instead -- the free plan's rule -- and the capture test states that
    instant in digits and proves it too, since a description of the backfill
    request alone said nothing about the one the cron sends.
    """
    cfg = cfg or ScanConfig()
    day_start = datetime(session.year, session.month, session.day, tzinfo=timezone.utc)
    return {
        "symbol_or_symbols": ["NVDA", "AMD"],
        "timeframe": TimeFrame.Day,
        "start": day_start - timedelta(days=int(cfg.lookback_days * 1.6)),
        "end": end or day_start + timedelta(hours=23, minutes=59, seconds=59),
        "adjustment": Adjustment.SPLIT,
        "feed": cfg.feed,
    }


def test_the_bars_request_is_a_shape_the_installed_sdk_accepts():
    """Construction is the validation: StockBarsRequest is a pydantic model,
    so a renamed or removed field raises before any request is made."""
    request = StockBarsRequest(**_request_kwargs())
    assert isinstance(request, StockBarsRequest)


def test_every_field_the_scanner_names_is_a_field_this_sdk_has():
    """The complement of the test above, which a model configured to ignore
    extras would pass silently: each name has to exist on the model."""
    missing = set(_request_kwargs()) - set(StockBarsRequest.model_fields)
    assert not missing, (
        f"src.scanner sets {sorted(missing)} on the bars request and alpaca-py "
        f"{_sdk_version()} has no such field"
    )


def test_the_request_the_scanner_really_builds_is_that_request():
    """The two tests above describe a request; this one proves _download_batch
    builds it. A drift between the description and the code would otherwise
    leave both green while the scan sent something else."""
    captured: list[StockBarsRequest] = []

    class Capturing:
        def get_stock_bars(self, request):
            captured.append(request)
            return BarSet({})

    def same(sent: dict, expected: dict) -> None:
        # TimeFrame has no __eq__, so two equal timeframes are different
        # objects. Compare it by the string the SDK would put on the wire, and
        # the rest of the query field by field.
        assert sent.pop("timeframe").value == expected.pop("timeframe").value == "1Day"
        assert sent == expected

    # A session behind the clock: the window is the session's own day.
    _download_batch(Capturing(), ["NVDA", "AMD"], ScanConfig(), SESSION)
    assert len(captured) == 1
    same(captured[0].to_request_fields(), StockBarsRequest(**_request_kwargs()).to_request_fields())

    # The session's own evening, the request the cron sends: 22:16 UTC is
    # 18:16 ET in June, and on sip the window ends sixteen minutes earlier.
    _download_batch(Capturing(), ["NVDA", "AMD"], ScanConfig(), SESSION,
                    now=datetime(2026, 6, 24, 22, 16, tzinfo=timezone.utc))
    assert len(captured) == 2
    same(captured[1].to_request_fields(),
         StockBarsRequest(**_request_kwargs(end=datetime(2026, 6, 24, 22, 0, tzinfo=timezone.utc))).to_request_fields())


def test_get_stock_bars_still_takes_the_request_object():
    """alpaca-py's client methods take a request model rather than kwargs.
    Binding against the real signature catches a change of calling convention
    without a socket -- the check step 8 used on the Anthropic side."""
    method = StockHistoricalDataClient.get_stock_bars
    inspect.signature(method).bind(object(), StockBarsRequest(**_request_kwargs()))


def test_the_enum_values_the_scanner_and_its_double_compare_strings_against():
    """Not decoration. `SCAN_FEED=delayed_sip` is parsed as `DataFeed(raw)`,
    the FeedNotAuthorizedError text lists `f.value` for every feed, and
    tests/fakes.py decides whether to un-adjust a split by testing
    `adjustment.value in ("split", "all")`.

    That last one is why this is here rather than nowhere: if the SDK renamed
    the enum's value, the double would stop un-adjusting, and the tests that
    prove the scan asks for split-adjusted prices would keep passing while
    comparing a frame against itself.
    """
    assert DataFeed.DELAYED_SIP.value == "delayed_sip"
    assert DataFeed.SIP.value == "sip"
    assert DataFeed.IEX.value == "iex"
    assert Adjustment.SPLIT.value == "split"
    assert Adjustment.ALL.value == "all"
    assert Adjustment.RAW.value == "raw"


def _sdk_version() -> str:
    import alpaca

    return getattr(alpaca, "__version__", "unknown")


# --------------------------------------------------------------------------
# 2. The response _download_batch() reads
# --------------------------------------------------------------------------


def _raw_bars(frame: pd.DataFrame, session: date, hour: int = 4) -> list[dict]:
    """One symbol's frame as the wire rows a real BarSet is decoded from.

    Timestamps are UTC at `hour`, which is what a daily bar's timestamp is:
    midnight ET, 04:00Z under EDT and 05:00Z under EST. The double dates its
    bars naively, so this is the one place the suite sees the tz-aware index
    the SDK really returns.
    """
    index = pd.bdate_range(end=pd.Timestamp(session), periods=len(frame))
    rows = []
    for stamp, (_, bar) in zip(index, frame.iterrows()):
        rows.append({
            "t": (stamp.normalize() + pd.Timedelta(hours=hour)).tz_localize("UTC").isoformat(),
            "o": float(bar["Open"]),
            "h": float(bar["High"]),
            "l": float(bar["Low"]),
            "c": float(bar["Close"]),
            "v": float(bar["Volume"]),
            "n": float(bar["Volume"]) / 100.0,
            "vw": float(bar["Close"]),
        })
    return rows


def _barset(frames: dict[str, pd.DataFrame], session: date = SESSION, hour: int = 4) -> BarSet:
    return BarSet({t: _raw_bars(df, session, hour) for t, df in frames.items()})


def test_a_real_barset_carries_the_index_and_columns_the_scanner_reads(ohlcv):
    """`df_all.loc[t]` and the lower-case-to-capitalised rename are the whole
    of _download_batch()'s knowledge of the SDK. Both are asserted against an
    object alpaca-py built."""
    df = _barset({"NVDA": ohlcv("burst"), "AMD": ohlcv("flat")}).df

    assert list(df.index.names) == ["symbol", "timestamp"]
    assert {"open", "high", "low", "close", "volume"} <= set(df.columns)
    assert sorted(df.index.get_level_values("symbol").unique()) == ["AMD", "NVDA"]
    assert isinstance(df.loc["NVDA"].index, pd.DatetimeIndex)


def test_a_real_barset_dates_its_bars_in_utc_and_the_session_survives_the_round_trip(ohlcv):
    """_last_bar_date() claims it works on "the tz-aware UTC index alpaca-py
    returns". Nothing had ever handed it one: the double's index is naive.

    Both offsets a US daily bar is stamped with are checked, because the one
    that could go wrong is the winter one -- 05:00Z is still the same calendar
    day, but only just, and a bar stamped at 23:00Z would not be.
    """
    for hour in (4, 5):
        df = _barset({"NVDA": ohlcv("burst")}, hour=hour).df.loc["NVDA"]
        assert df.index.tz is not None, "alpaca-py returns tz-aware timestamps"
        assert _last_bar_date(df) == SESSION, f"a bar stamped {hour:02d}:00Z is that session"


def test_an_empty_real_response_has_no_columns_at_all():
    """A BarSet built from nothing gives a DataFrame with no columns and no
    index names -- so `df_all.empty` has to be tested BEFORE anything touches
    `.loc` or a column. _download_batch() does; this pins why it must."""
    empty = BarSet({}).df

    assert empty.empty
    assert list(empty.columns) == []
    with pytest.raises(KeyError):
        empty.loc["NVDA"]

    assert _download_batch(_client_returning(empty_barset=True), ["NVDA"],
                           ScanConfig(), SESSION) == {}


def test_download_batch_parses_a_real_barset_into_the_frames_the_rules_read(ohlcv):
    """End of the contract: a genuine BarSet in, the capitalised frames every
    downstream layer expects out, and a burst the rules still recognise."""
    burst, flat = ohlcv("burst"), ohlcv("flat")
    client = _client_returning(barset=_barset({"NVDA": burst, "AMD": flat}))

    out = _download_batch(client, ["NVDA", "AMD", "GONE"], ScanConfig(), SESSION)

    assert sorted(out) == ["AMD", "NVDA"], "a symbol with no bars is skipped, not an error"
    assert list(out["NVDA"].columns[:5]) == ["Open", "High", "Low", "Close", "Volume"]
    assert len(out["NVDA"]) == len(burst)
    assert detect_setup(out["NVDA"], ScanConfig()) is not None
    assert detect_setup(out["AMD"], ScanConfig()) is None


class _StaticClient:
    def __init__(self, barset: BarSet) -> None:
        self._barset = barset
        self.requests: list[StockBarsRequest] = []

    def get_stock_bars(self, request):
        self.requests.append(request)
        return self._barset


def _client_returning(barset: BarSet | None = None, *, empty_barset: bool = False):
    return _StaticClient(BarSet({}) if empty_barset else barset)


# --------------------------------------------------------------------------
# 3. The double, measured against the thing it stands in for
# --------------------------------------------------------------------------


def test_a_scan_reaches_the_same_verdict_through_a_real_barset_as_through_the_double(
    fake_alpaca, ohlcv, monkeypatch
):
    """The assertion the rest of the Layer 1 suite rests on.

    One scan, run twice over byte-identical frames: once through FakeBarSet,
    once through a BarSet alpaca-py assembled from the same numbers. Same
    candidates, same metrics, or the double is not standing in for the SDK and
    every other test of this module is measuring the double.

    The two responses are NOT identical objects -- the real one is tz-aware
    UTC and carries the SDK's own dtypes -- which is the point: the scan has
    to be indifferent to exactly those differences.
    """
    session = current_session()
    frames = {"NVDA": ohlcv("burst"), "AMD": ohlcv("flat"), "PLTR": ohlcv("base")}
    for ticker, frame in frames.items():
        fake_alpaca.add_history(ticker, frame)
    universe = list(frames)

    through_the_double = run_scan(ScanConfig(), universe=universe)

    from tests.fakes import FakeDataClient

    monkeypatch.setattr(
        FakeDataClient, "get_stock_bars",
        lambda self, request: _barset(frames, session=session),
    )
    through_the_sdk = run_scan(ScanConfig(), universe=universe)

    assert [c.ticker for c in through_the_sdk] == [c.ticker for c in through_the_double] == ["NVDA"]
    for real, double in zip(through_the_sdk, through_the_double):
        assert (real.gain_pct, real.volume, real.prev_volume) == (
            double.gain_pct, double.volume, double.prev_volume)
        assert (real.volume_ratio, real.avg_volume, real.dollar_volume) == (
            double.volume_ratio, double.avg_volume, double.dollar_volume)
        assert real.date == double.date == str(session)


def test_a_stale_symbol_is_recognised_as_stale_through_a_real_barset(
    fake_alpaca, ohlcv, monkeypatch
):
    """Freshness, the one rule that reads the SDK's timestamps rather than its
    numbers, over the real tz-aware index. A halted name whose last print is
    an earlier session must still be dropped."""
    from tests.fakes import FakeDataClient

    session = current_session()
    frames = {"NOW": ohlcv("burst"), "HALT": ohlcv("burst", variant=1)}
    for ticker, frame in frames.items():
        fake_alpaca.add_history(ticker, frame)

    monkeypatch.setattr(FakeDataClient, "get_stock_bars", lambda self, request: BarSet({
        "NOW": _raw_bars(frames["NOW"], session),
        "HALT": _raw_bars(frames["HALT"], session - timedelta(days=7)),
    }))

    assert [c.ticker for c in run_scan(ScanConfig(), universe=list(frames))] == ["NOW"]
