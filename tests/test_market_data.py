"""src.market_data -- the Alpaca transport, offline.

The boundary is tests/fakes.py's Alpaca double, patched where THIS module
looks the client up, and for the wire shapes a genuine alpaca-py
StockBarsRequest and BarSet built without a socket. Every instant the SIP
hold-back turns on is written out in digits; nothing here reads the wall
clock to decide an answer.
"""

from __future__ import annotations

import inspect
import json
import logging
import time
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import numpy as np
import pandas as pd
import pytest
import requests
from alpaca.common.exceptions import APIError
from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.models import BarSet
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from requests.exceptions import HTTPError

from src import market_data
from src.clock import previous_session
from src.market_data import (
    ALPACA_CONNECT_TIMEOUT_SECONDS,
    ALPACA_READ_TIMEOUT_SECONDS,
    DEFAULT_BATCH_SIZE,
    DEFAULT_FEED,
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_MIN_SYMBOLS,
    LOOKBACK_CALENDAR_RATIO,
    OHLCV,
    REQUIRED_ENV,
    RETRY_WAIT_SECONDS,
    SIP_HOLDBACK_MINUTES,
    SYMBOLS_FILE,
    CredentialsRejectedError,
    DownloadStats,
    FeedNotAuthorizedError,
    SymbolFileError,
    _as_date,
    _download_batch,
    _is_permanent_refusal,
    _SYMBOL_RE,
    apply_session_rules,
    download_bars,
    drop_gapped,
    drop_stale,
    feed_from_env,
    get_clients,
    last_bar_date,
    newest_stale,
    observed_previous_session,
    read_symbol_file,
    session_calendar,
)
from tests.fakes import FakeAlpaca, FakeDataClient

#: A Wednesday behind the wall clock, so a no-`now` request keeps its own
#: day's end whatever the hour the suite runs at.
SESSION = date(2026, 6, 24)
SCAN_DAY = date(2026, 9, 9)
TUESDAY_AFTER_LABOR_DAY = date(2026, 9, 8)
LABOR_DAY = date(2026, 9, 7)
DENIAL = "subscription does not permit querying recent SIP data"


# ------------------------------------------------------------ fixtures ----


@pytest.fixture
def fake_alpaca(monkeypatch) -> FakeAlpaca:
    """tests/fakes.py's Alpaca double, patched where this module looks the
    client up. conftest's fixture of the same name patches src.market_data, which
    this module never imports, so it is overridden here rather than copied."""
    monkeypatch.setenv("ALPACA_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "test-not-a-real-secret")
    parent = FakeAlpaca()
    monkeypatch.setattr(market_data, "StockHistoricalDataClient",
                        lambda *a, **k: FakeDataClient(parent, *a, **k))
    return parent


@pytest.fixture
def credentials(monkeypatch):
    """Throwaway keys for the tests that build the REAL SDK client."""
    monkeypatch.setenv("ALPACA_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "test-not-a-real-secret")


# ------------------------------------------------------------- helpers ----


def _fetch(universe: list[str], session: date = SCAN_DAY, **kw):
    """download_bars through the double: (frames, stats)."""
    return download_bars(get_clients(), universe, session, **kw)


def _scan(universe: list[str], session: date = SCAN_DAY, *,
          min_symbols: int = DEFAULT_MIN_SYMBOLS, **kw):
    """download_bars then apply_session_rules: (fresh, stats)."""
    frames, stats = _fetch(universe, session, **kw)
    return apply_session_rules(frames, session, stats, min_symbols=min_symbols), stats


def _gain(df: pd.DataFrame) -> float:
    """The one-day move over the frame's last two bars, in percent -- the
    hand replacement for a burst detector, which this module does not have."""
    return (float(df["Close"].iloc[-1]) / float(df["Close"].iloc[-2]) - 1) * 100


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


def _wire_fields(fake_alpaca, ohlcv, **kw) -> dict:
    """Run one download and return the request fields it put on the wire --
    the SDK's own to_request_fields(), not the request object's attributes."""
    fake_alpaca.add_history("AAA", ohlcv("base"))
    _fetch(["AAA"], **kw)
    assert fake_alpaca.request_fields, "the data client was never asked for bars"
    return fake_alpaca.request_fields[-1]


def _raw_bars(frame: pd.DataFrame, session: date, hour: int = 4) -> list[dict]:
    """One symbol's frame as the wire rows a real BarSet is decoded from,
    oldest first, ending on `session`. Timestamps are UTC at `hour`: a daily
    bar's timestamp is midnight ET, 04:00Z under EDT and 05:00Z under EST."""
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


class _StaticClient:
    def __init__(self, barset: BarSet) -> None:
        self._barset = barset
        self.requests: list[StockBarsRequest] = []

    def get_stock_bars(self, request):
        self.requests.append(request)
        return self._barset


def _genuine_barset(symbol: str, rows: list[dict]) -> _StaticClient:
    """A client answering with a real alpaca-py BarSet built from `rows`."""
    return _StaticClient(BarSet({symbol: rows}))


def _batch(client, tickers: list[str], session: date = SESSION, *, feed: DataFeed = DEFAULT_FEED,
           **kw) -> dict[str, pd.DataFrame]:
    return _download_batch(client, tickers, session, DEFAULT_LOOKBACK_DAYS, feed, **kw)


def _alpaca_error(status: int | None, message: str) -> APIError:
    """An APIError shaped the way alpaca-py builds one: the HTTP status is
    present only when the SDK had an HTTPError to build from."""
    body = json.dumps({"message": message})
    if status is None:
        return APIError(body)
    response = requests.Response()
    response.status_code = status
    return APIError(body, HTTPError(response=response))


def _attempt_recorder(monkeypatch, failures: dict[int, Exception]) -> list[list[str]]:
    """Record every get_stock_bars attempt's symbols; raise on the attempts
    named in `failures` (keyed by attempt number), so a batch can fail once
    and succeed on the retry."""
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


def _response(request, payload, status=200):
    response = requests.Response()
    response.status_code = status
    response.request = request
    response.url = request.url
    response._content = json.dumps(payload).encode()
    response.headers["Content-Type"] = "application/json"
    return response


def _warned(caplog, phrase: str) -> str:
    """The one WARNING carrying `phrase`, or a failure naming what was logged."""
    hits = [r.getMessage() for r in caplog.records
            if r.levelno == logging.WARNING and phrase in r.getMessage()]
    assert len(hits) == 1, [r.getMessage() for r in caplog.records]
    return hits[0]


# ================================================================ constants ==


def test_the_transport_still_holds_the_numbers_it_was_tuned_to():
    """Each of these was settled on a live run or a measured reproduction;
    a change has to be deliberate enough to edit a test."""
    assert REQUIRED_ENV == ("ALPACA_API_KEY", "ALPACA_SECRET_KEY")
    assert DEFAULT_FEED is DataFeed.SIP
    assert SIP_HOLDBACK_MINUTES == 16
    assert (ALPACA_CONNECT_TIMEOUT_SECONDS, ALPACA_READ_TIMEOUT_SECONDS) == (5, 30)
    assert (DEFAULT_LOOKBACK_DAYS, LOOKBACK_CALENDAR_RATIO) == (260, 1.6)
    assert DEFAULT_BATCH_SIZE == 100
    assert RETRY_WAIT_SECONDS == 3
    assert DEFAULT_MIN_SYMBOLS == 10


def test_the_default_feed_is_the_consolidated_tape_and_not_the_name_the_endpoint_refused():
    assert DEFAULT_FEED is DataFeed.SIP
    assert DEFAULT_FEED is not DataFeed.DELAYED_SIP


# ================================================================== client ==


def test_get_clients_needs_no_key_and_no_network(fake_alpaca):
    get_clients()
    assert len(fake_alpaca.data_clients) == 1


def test_get_clients_reads_the_keys_at_call_time_not_import_time(fake_alpaca, monkeypatch):
    """An import-time capture made the preflight validate a different value
    from the one the client used."""
    monkeypatch.setenv("ALPACA_API_KEY", "second-key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "second-secret")
    get_clients()
    assert fake_alpaca.data_clients[-1].init_args[0] == ("second-key", "second-secret")


def test_the_feed_can_be_pinned_through_the_environment(monkeypatch):
    monkeypatch.setenv("SCAN_FEED", "sip")
    assert feed_from_env() is DataFeed.SIP
    monkeypatch.setenv("SCAN_FEED", "IEX")
    assert feed_from_env() is DataFeed.IEX
    monkeypatch.setenv("SCAN_FEED", "")
    assert feed_from_env() is DEFAULT_FEED
    monkeypatch.delenv("SCAN_FEED", raising=False)
    assert feed_from_env() is DEFAULT_FEED


def test_a_feed_the_sdk_does_not_know_raises_instead_of_falling_back(monkeypatch):
    """A typo must not silently leave the scan on a feed nobody chose."""
    monkeypatch.setenv("SCAN_FEED", "delayed-sip")
    with pytest.raises(ValueError, match="SCAN_FEED"):
        feed_from_env()


def test_download_bars_reads_the_feed_from_the_environment_when_none_is_given(
    fake_alpaca, ohlcv, monkeypatch
):
    monkeypatch.setenv("SCAN_FEED", "iex")
    assert _wire_fields(fake_alpaca, ohlcv)["feed"] == DataFeed.IEX


# ============================================== the request, against the SDK ==


def _request_kwargs(session: date = SESSION, end: datetime | None = None) -> dict:
    """The kwargs _download_batch() passes, rebuilt from its own arithmetic
    so this file still says what the request IS when the module changes."""
    day_start = datetime(session.year, session.month, session.day, tzinfo=timezone.utc)
    return {
        "symbol_or_symbols": ["NVDA", "AMD"],
        "timeframe": TimeFrame.Day,
        "start": day_start - timedelta(days=int(DEFAULT_LOOKBACK_DAYS * LOOKBACK_CALENDAR_RATIO)),
        "end": end or day_start + timedelta(hours=23, minutes=59, seconds=59),
        "adjustment": Adjustment.SPLIT,
        "feed": DEFAULT_FEED,
    }


def test_the_bars_request_is_a_shape_the_installed_sdk_accepts():
    """StockBarsRequest is a pydantic model: a renamed or removed field
    raises at construction, before any request is made."""
    assert isinstance(StockBarsRequest(**_request_kwargs()), StockBarsRequest)


def test_every_field_the_downloader_names_is_a_field_this_sdk_has():
    """A model configured to ignore extras would pass the test above silently."""
    missing = set(_request_kwargs()) - set(StockBarsRequest.model_fields)
    assert not missing, f"src.market_data sets {sorted(missing)} and this alpaca-py has no such field"


def test_the_request_the_downloader_really_builds_is_that_request():
    """The description above, proved against the code: both the backfill
    request and the one the cron sends on the session's own evening."""
    captured: list[StockBarsRequest] = []

    class Capturing:
        def get_stock_bars(self, request):
            captured.append(request)
            return BarSet({})

    def same(sent: dict, expected: dict) -> None:
        # TimeFrame has no __eq__; compare it by the string that goes on the wire.
        assert sent.pop("timeframe").value == expected.pop("timeframe").value == "1Day"
        assert sent == expected

    _batch(Capturing(), ["NVDA", "AMD"])
    assert len(captured) == 1
    same(captured[0].to_request_fields(), StockBarsRequest(**_request_kwargs()).to_request_fields())

    # 22:16 UTC is 18:16 ET in June; on sip the window ends sixteen minutes earlier.
    _batch(Capturing(), ["NVDA", "AMD"], now=datetime(2026, 6, 24, 22, 16, tzinfo=timezone.utc))
    assert len(captured) == 2
    same(captured[1].to_request_fields(),
         StockBarsRequest(**_request_kwargs(end=datetime(2026, 6, 24, 22, 0, tzinfo=timezone.utc))).to_request_fields())


def test_get_stock_bars_still_takes_the_request_object():
    """A change of calling convention fails here without a socket."""
    inspect.signature(StockHistoricalDataClient.get_stock_bars).bind(
        object(), StockBarsRequest(**_request_kwargs()))


def test_the_enum_values_this_module_and_its_double_compare_strings_against():
    """SCAN_FEED is parsed as DataFeed(raw), the refusal text lists f.value,
    and tests/fakes.py un-adjusts a split on `adjustment.value in ("split",
    "all")` -- a renamed value would make the double stop un-adjusting and the
    split tests compare a frame against itself."""
    assert DataFeed.DELAYED_SIP.value == "delayed_sip"
    assert DataFeed.SIP.value == "sip"
    assert DataFeed.IEX.value == "iex"
    assert Adjustment.SPLIT.value == "split"
    assert Adjustment.ALL.value == "all"
    assert Adjustment.RAW.value == "raw"


# ================================================ the request, on the wire ==


def test_the_bars_request_asks_for_split_adjusted_prices(fake_alpaca, ohlcv):
    """Alpaca's default is raw, which puts every bar before a split on a
    different scale from the ones after it."""
    assert _wire_fields(fake_alpaca, ohlcv)["adjustment"] == Adjustment.SPLIT


def test_the_bars_request_names_a_feed_instead_of_taking_the_plan_default(fake_alpaca, ohlcv):
    assert _wire_fields(fake_alpaca, ohlcv)["feed"] == DataFeed.SIP


def test_the_feed_is_overridable_to_the_single_venue_fallback(fake_alpaca, ohlcv):
    assert _wire_fields(fake_alpaca, ohlcv, feed=DataFeed.IEX)["feed"] == DataFeed.IEX


def test_the_request_window_ends_at_the_session_being_scanned(fake_alpaca, ohlcv):
    """Without an end bound the response runs to now, so a scan of an
    earlier session would collect bars printed after it."""
    fields = _wire_fields(fake_alpaca, ohlcv, session=SESSION)
    assert datetime.fromisoformat(fields["end"]).date() == SESSION


def test_the_request_window_starts_a_lookback_before_the_session_not_before_now(fake_alpaca, ohlcv):
    fields = _wire_fields(fake_alpaca, ohlcv, session=SESSION, lookback_days=DEFAULT_LOOKBACK_DAYS)
    start = datetime.fromisoformat(fields["start"]).date()
    assert start == SESSION - timedelta(days=int(DEFAULT_LOOKBACK_DAYS * LOOKBACK_CALENDAR_RATIO))
    # And the lookback is the caller's, not a constant the wrapper ignores.
    fields = _wire_fields(fake_alpaca, ohlcv, session=SESSION, lookback_days=10)
    assert datetime.fromisoformat(fields["start"]).date() == SESSION - timedelta(days=16)


def test_the_download_sees_the_split_adjusted_frame(fake_alpaca, ohlcv):
    """The double serves raw prints unless the request asks for split
    adjustment: a 4-for-1 ex-date on the burst bar turns a +12% day into a
    ~72% collapse when read raw, so the burst below exists only because the
    request names the adjustment."""
    fake_alpaca.add_history("SPLT", ohlcv("burst"))
    fake_alpaca.add_split("SPLT", 4.0)
    end = datetime(2026, 6, 24, tzinfo=timezone.utc)
    raw = fake_alpaca.bars_frame(["SPLT"], end=end, adjustment=Adjustment.RAW).loc["SPLT"]
    raw = raw.rename(columns=str.capitalize)
    assert _gain(raw) < -70, "precondition: the raw frame reads the split as a crash"

    frames, _ = _fetch(["SPLT"], SESSION)
    assert _gain(frames["SPLT"]) > 10


# ------------------------------------------ the free plan's SIP hold-back --


def test_a_sip_request_for_todays_session_is_held_back_behind_the_clock(fake_alpaca, ohlcv):
    """Alpaca's rule for a plan without a real-time subscription: a SIP
    query's end must be at least fifteen minutes old. On the session's own
    evening the window ends SIP_HOLDBACK_MINUTES before now; a backfill of an
    older session keeps its day's end, and so does every other feed."""
    fake_alpaca.add_history("AAA", ohlcv("burst"))
    client = get_clients()
    evening = datetime(2026, 6, 24, 22, 16, tzinfo=timezone.utc)          # 18:16 ET, the cron
    wire_end = lambda: datetime.fromisoformat(fake_alpaca.request_fields[-1]["end"])   # noqa: E731

    _batch(client, ["AAA"], SESSION, feed=DataFeed.SIP, now=evening)
    # The instant in digits, not `evening - SIP_HOLDBACK_MINUTES`: that
    # compares the value against the name it came from and passes at 0.
    assert wire_end() == datetime(2026, 6, 24, 22, 0, tzinfo=timezone.utc), wire_end()
    assert wire_end() > datetime(2026, 6, 24, 20, 0, tzinfo=timezone.utc), "still after the 16:00 ET close"

    _batch(client, ["AAA"], date(2026, 6, 17), feed=DataFeed.SIP, now=evening)
    assert wire_end() == datetime(2026, 6, 17, 23, 59, 59, tzinfo=timezone.utc), (
        "a session already behind the clock keeps its own day's end")

    # Every feed alpaca-py names except sip: a check that sampled one other
    # member let a mutant holding back every feed but IEX through.
    for other in (f for f in DataFeed if f is not DataFeed.SIP):
        _batch(client, ["AAA"], SESSION, feed=other, now=evening)
        assert wire_end() == datetime(2026, 6, 24, 23, 59, 59, tzinfo=timezone.utc), (
            f"{other.value}: no other feed was observed to need the hold-back")


def test_a_sip_request_for_a_session_the_clock_has_not_reached_goes_out_as_written(fake_alpaca, ohlcv):
    """No schedule produces a session pinned AHEAD of the clock, but the
    offline suite does on purpose, and a hold-back that read the real clock
    there ended the window on the day before the session -- the
    clock-dependent test this project names as the worst kind."""
    fake_alpaca.add_history("AAA", ohlcv("burst"))
    client = get_clients()
    evening = datetime(2026, 6, 24, 22, 16, tzinfo=timezone.utc)
    wire_end = lambda: datetime.fromisoformat(fake_alpaca.request_fields[-1]["end"])   # noqa: E731

    _batch(client, ["AAA"], date(2026, 6, 25), feed=DataFeed.SIP, now=evening)
    assert wire_end() == datetime(2026, 6, 25, 23, 59, 59, tzinfo=timezone.utc), wire_end()

    # The first sixteen minutes of the session's UTC day: the raw clock has
    # reached the day and the held-back one has not, and a guard on the raw
    # clock would clamp the window onto the day BEFORE the session.
    _batch(client, ["AAA"], date(2026, 6, 25), feed=DataFeed.SIP,
           now=datetime(2026, 6, 25, 0, 5, tzinfo=timezone.utc))
    assert wire_end() == datetime(2026, 6, 25, 23, 59, 59, tzinfo=timezone.utc), wire_end()

    # The day itself, reached: held back like any other.
    _batch(client, ["AAA"], date(2026, 6, 25), feed=DataFeed.SIP,
           now=datetime(2026, 6, 25, 22, 16, tzinfo=timezone.utc))
    assert wire_end() == datetime(2026, 6, 25, 22, 0, tzinfo=timezone.utc), wire_end()


def test_download_bars_hands_the_clock_through_to_every_batch(fake_alpaca, ohlcv):
    """The wrapper's `now` is what the hold-back reads, on every batch."""
    universe = _coverage(fake_alpaca, ohlcv, fresh=3)
    _fetch(universe, SESSION, feed=DataFeed.SIP, batch_size=2,
           now=datetime(2026, 6, 24, 22, 16, tzinfo=timezone.utc))
    ends = {datetime.fromisoformat(f["end"]) for f in fake_alpaca.request_fields}
    assert len(fake_alpaca.request_fields) == 2
    assert ends == {datetime(2026, 6, 24, 22, 0, tzinfo=timezone.utc)}


# ============================================ the response, against the SDK ==


def test_a_real_barset_carries_the_index_and_columns_this_module_reads(ohlcv):
    """`df_all.loc[t]` and the lower-case-to-capitalised rename are the whole
    of _download_batch()'s knowledge of the SDK."""
    df = _barset({"NVDA": ohlcv("burst"), "AMD": ohlcv("flat")}).df
    assert list(df.index.names) == ["symbol", "timestamp"]
    assert {"open", "high", "low", "close", "volume"} <= set(df.columns)
    assert sorted(df.index.get_level_values("symbol").unique()) == ["AMD", "NVDA"]
    assert isinstance(df.loc["NVDA"].index, pd.DatetimeIndex)


def test_a_real_barset_dates_its_bars_in_utc_and_the_session_survives_the_round_trip(ohlcv):
    """Both offsets a US daily bar is stamped with; 05:00Z is the same
    calendar day, but only just."""
    for hour in (4, 5):
        df = _barset({"NVDA": ohlcv("burst")}, hour=hour).df.loc["NVDA"]
        assert df.index.tz is not None, "alpaca-py returns tz-aware timestamps"
        assert last_bar_date(df) == SESSION, f"a bar stamped {hour:02d}:00Z is that session"


def test_a_nat_stamp_is_no_date_rather_than_a_nat_that_cannot_be_compared():
    """pd.Timestamp(NaT).date() is NaT again, and a NaT compared with a date
    is a TypeError in place of the message an operator needs."""
    assert _as_date(pd.NaT) is None
    assert _as_date(pd.Timestamp("2026-06-24 04:00", tz="UTC")) == SESSION
    assert _as_date(pd.Timestamp("2026-06-24")) == SESSION
    frame = pd.DataFrame({"Close": [1.0, 2.0]}, index=pd.DatetimeIndex([pd.Timestamp(SESSION), pd.NaT]))
    assert last_bar_date(frame) is None


def test_an_empty_real_response_has_no_columns_at_all():
    """A BarSet built from nothing has no columns and no index names, so
    `df_all.empty` has to be tested before anything touches `.loc`."""
    empty = BarSet({}).df
    assert empty.empty and list(empty.columns) == []
    with pytest.raises(KeyError):
        empty.loc["NVDA"]
    assert _batch(_StaticClient(BarSet({})), ["NVDA"]) == {}


def test_download_batch_parses_a_real_barset_into_the_frames_the_rules_read(ohlcv):
    burst, flat = ohlcv("burst"), ohlcv("flat")
    out = _batch(_StaticClient(_barset({"NVDA": burst, "AMD": flat})), ["NVDA", "AMD", "GONE"])

    assert sorted(out) == ["AMD", "NVDA"], "a symbol with no bars is skipped, not an error"
    assert tuple(out["NVDA"].columns[:5]) == OHLCV
    assert len(out["NVDA"]) == len(burst)
    assert last_bar_date(out["NVDA"]) == SESSION
    assert _gain(out["NVDA"]) > 4 and abs(_gain(out["AMD"])) < 1


def test_a_real_barset_keeps_the_response_order_and_both_copies_of_a_repeated_bar(ohlcv):
    """The two SDK facts the sort and de-dup rest on: BarSet.df hands over
    rows in wire order, and both copies of a repeated timestamp."""
    rows = _raw_bars(ohlcv("burst"), SESSION)
    prelim, corrected = dict(rows[-1], v=1.0), dict(rows[-1], v=2.0)

    df = BarSet({"NVDA": [prelim, corrected] + list(reversed(rows[:-1]))}).df.loc["NVDA"]

    assert not df.index.is_monotonic_increasing, "the SDK does not sort; this module does"
    assert list(df["volume"][:2]) == [1.0, 2.0], "and it keeps both copies, in wire order"
    assert len(df) == len(rows) + 1


def test_download_bars_reads_the_same_frames_through_a_real_barset_as_through_the_double(
    fake_alpaca, ohlcv, monkeypatch
):
    """The assertion the rest of this file rests on: byte-identical frames
    through FakeBarSet and through a BarSet alpaca-py assembled from the same
    numbers read the same, though one is tz-aware with the SDK's dtypes."""
    frames = {"NVDA": ohlcv("burst"), "AMD": ohlcv("flat"), "PLTR": ohlcv("base")}
    for ticker, frame in frames.items():
        fake_alpaca.add_history(ticker, frame)

    through_the_double, _ = _fetch(list(frames), SCAN_DAY)
    monkeypatch.setattr(FakeDataClient, "get_stock_bars",
                        lambda self, request: _barset(frames, session=SCAN_DAY))
    through_the_sdk, _ = _fetch(list(frames), SCAN_DAY)

    assert sorted(through_the_sdk) == sorted(through_the_double) == ["AMD", "NVDA", "PLTR"]
    for ticker in frames:
        real, double = through_the_sdk[ticker], through_the_double[ticker]
        assert real.index.tz is not None and double.index.tz is None, "the point: they differ in shape"
        assert list(real.index.date) == list(double.index.date)
        assert last_bar_date(real) == last_bar_date(double) == SCAN_DAY
        for column in OHLCV:
            assert np.allclose(real[column].to_numpy(dtype=float), double[column].to_numpy(dtype=float))


def test_the_day_after_a_closure_is_read_through_a_real_barset_newest_first(
    fake_alpaca, ohlcv, monkeypatch
):
    """Twelve names, none with a bar on Monday 7 Sep 2026, served newest
    first the way the wire may: the session before Tuesday's is read off the
    batch as Friday and every name is measurable. Before the closure rule
    every one of them was a hole -- reproduced on exactly this BarSet."""
    frames = {f"G{i}": ohlcv("burst", variant=i) for i in range(12)}
    rows = {t: [bar for bar in _raw_bars(f, TUESDAY_AFTER_LABOR_DAY) if not bar["t"].startswith("2026-09-07")]
            for t, f in frames.items()}
    assert all(len(r) == len(frames[t]) - 1 for t, r in rows.items()), "precondition: the Monday bar is gone"
    monkeypatch.setattr(FakeDataClient, "get_stock_bars",
                        lambda self, request: BarSet({t: list(reversed(r)) for t, r in rows.items()}))

    fresh, stats = _scan(list(frames), TUESDAY_AFTER_LABOR_DAY)

    assert sorted(fresh) == sorted(frames)
    assert stats.gapped == {} and stats.stale == {}
    assert stats.previous_session == date(2026, 9, 4) and stats.previous_session_observed is True


def test_a_stale_symbol_is_recognised_as_stale_through_a_real_barset(fake_alpaca, ohlcv, monkeypatch):
    """Freshness reads the SDK's timestamps rather than its numbers, over the
    real tz-aware index."""
    frames = {"NOW": ohlcv("burst"), "HALT": ohlcv("burst", variant=1)}
    monkeypatch.setattr(FakeDataClient, "get_stock_bars", lambda self, request: BarSet({
        "NOW": _raw_bars(frames["NOW"], SCAN_DAY),
        "HALT": _raw_bars(frames["HALT"], SCAN_DAY - timedelta(days=7)),
    }))

    fresh, stats = _scan(list(frames), SCAN_DAY)

    assert list(fresh) == ["NOW"]
    assert stats.stale == {"HALT": SCAN_DAY - timedelta(days=7)}


# ================================================ order and duplication ==


def test_a_newest_first_response_is_not_read_as_a_stale_symbol(ohlcv):
    """BarSet.df keeps the response's order and the request pins no sort: a
    newest-first reply made the freshness check read the OLDEST bar, every
    symbol read as stale, and the run died blaming a holiday."""
    rows = _raw_bars(ohlcv("burst"), SESSION)

    df = _batch(_genuine_barset("X", list(reversed(rows))), ["X"])["X"]

    assert last_bar_date(df) == SESSION
    assert df.index.is_monotonic_increasing
    assert _gain(df) > 4, "and the burst on the newest bar is still there"


def test_a_bar_the_feed_sent_twice_does_not_hide_the_burst(ohlcv):
    """A duplicated newest bar made the last two bars one session, so the
    day's gain read as 0% and a real burst was silently missed."""
    rows = _raw_bars(ohlcv("burst"), SESSION)

    df = _batch(_genuine_barset("X", rows + [rows[-1]]), ["X"])["X"]

    assert not df.index.has_duplicates
    assert len(df) == len(rows)
    assert _gain(df) > 4


@pytest.mark.parametrize("bars", [16, 20, 60, 250])
def test_the_copy_the_feed_sent_last_is_the_one_kept_whatever_order_it_arrived_in(ohlcv, bars):
    """`keep="last"` means "the last copy on the wire" only if the sort in
    front of it is stable, and sort_index() defaults to quicksort: at 17 or
    more WIRE elements a newest-first response kept the preliminary copy.
    numpy sorts 16 and under stably by accident (insertion sort), so the
    smallest frame that can fail is 16 bars plus its extra copy -- the first
    case here."""
    rows = _raw_bars(ohlcv("burst", days=bars), SESSION)
    prelim = dict(rows[-1], v=1.0)
    corrected = dict(rows[-1], v=rows[-1]["v"] + 7.0)
    wire = [prelim, corrected] + list(reversed(rows[:-1]))
    assert len(wire) >= 17, "at 16 elements and under numpy sorts stably by accident"

    df = _batch(_genuine_barset("X", wire), ["X"])["X"]

    assert df.index.is_monotonic_increasing, "oldest first, whatever order it arrived in"
    assert not df.index.has_duplicates and len(df) == len(rows)
    assert df["Volume"].iloc[-1] == corrected["v"], "the copy the feed sent LAST is the one kept"


def test_the_bars_the_feed_sent_twice_are_counted_for_the_caller(ohlcv):
    """A duplicate is resolved silently, so nothing downstream could say a
    night had one; counted per symbol as the EXTRA copies dropped."""
    rows = _raw_bars(ohlcv("burst"), SESSION)

    clean: dict[str, int] = {}
    _batch(_genuine_barset("X", rows), ["X"], duplicates=clean)
    assert clean == {}, "a clean batch names no symbol"

    twice: dict[str, int] = {}
    _batch(_genuine_barset("X", rows + [rows[-1], rows[-1], rows[-3]]), ["X"], duplicates=twice)
    assert twice == {"X": 3}, "every bar dropped as a duplicate is counted, not just the sessions"


def test_a_bar_with_every_field_empty_is_not_a_bar(ohlcv):
    """A row the feed sends with nothing in it is dropped before the frame
    is read, so the newest bar is the newest bar WITH something in it and
    the stale rule cannot call a name fresh on an empty row; a row with one
    empty field stays, since the rules that read it decide what it means.
    Found by mutation: removing the drop left the whole suite green."""
    from tests.fakes import FakeBarSet

    frame = ohlcv("burst", days=10)
    lower = frame.rename(columns=str.lower).copy()
    lower.index = pd.DatetimeIndex(pd.bdate_range(end=pd.Timestamp(SESSION), periods=len(frame)),
                                   name="timestamp")
    lower.iloc[-1, lower.columns.get_loc("open")] = float("nan")   # one empty field on the session bar
    nothing = pd.DataFrame([[float("nan")] * len(lower.columns)], columns=lower.columns,
                           index=pd.DatetimeIndex([pd.Timestamp(SESSION) + pd.offsets.BDay(1)],
                                                  name="timestamp"))
    lower = pd.concat([lower, nothing])                      # a bar of nothing, after the session
    assert len(lower) == len(frame) + 1 and lower.iloc[-1].isna().all(), "precondition: the empty row is there"
    wire = pd.concat([lower, lower * float("nan")], keys=["X", "EMPTY"], names=["symbol", "timestamp"])

    class Client:
        def get_stock_bars(self, request):
            return FakeBarSet(wire)

    out = _batch(Client(), ["X", "EMPTY"], SESSION)

    assert list(out) == ["X"], "a symbol whose every bar is empty answered with nothing"
    assert last_bar_date(out["X"]) == SESSION, "the empty row after the session is not the newest bar"
    assert len(out["X"]) == len(frame)
    assert pd.isna(out["X"]["Open"].iloc[-1]) and not pd.isna(out["X"]["Close"].iloc[-1]), (
        "a bar with one empty field is kept as it came")


def test_a_session_sent_twice_under_two_timestamps_is_a_shape_this_does_not_count(ohlcv):
    """`duplicated()` sees the index: the same SESSION under two different
    timestamps (04:00 and 05:00 on one date) is neither counted nor dropped,
    and the last two bars then read as one session with no gain -- the very
    defect the de-dup exists to prevent, arriving by another door. No wire
    has been seen doing it, so this pins what IS measured rather than
    inventing a session-level de-dup; a round that adds one turns this red."""
    rows = _raw_bars(ohlcv("burst"), SESSION)
    restated = dict(rows[-1], v=rows[-1]["v"] + 7.0)

    same_stamp: dict[str, int] = {}
    df = _batch(_genuine_barset("X", rows + [restated]), ["X"], duplicates=same_stamp)["X"]
    assert same_stamp == {"X": 1} and _gain(df) > 4, "the shape that IS counted"

    two_stamps: dict[str, int] = {}
    later = dict(restated, t=restated["t"].replace("T04:00", "T05:00"))
    df = _batch(_genuine_barset("X", rows + [later]), ["X"], duplicates=two_stamps)["X"]

    assert two_stamps == {}, "not counted -- the timestamps differ"
    assert len(df) == len(rows) + 1 and df.index[-1].date() == df.index[-2].date(), "and not dropped"
    assert abs(_gain(df)) < 1e-9, "and the burst is missed, silently, as it was before"


# ========================================== batching, retry and refusal ==


def test_download_bars_over_a_given_universe(fake_alpaca, ohlcv):
    fake_alpaca.add_history("BURST", ohlcv("burst"))
    fake_alpaca.add_history("QUIET", ohlcv("flat"))

    frames, stats = _fetch(["BURST", "QUIET"])

    assert fake_alpaca.bar_requests, "the mocked data client was never asked for bars"
    assert sorted(frames) == ["BURST", "QUIET"]
    assert all(tuple(df.columns[:5]) == OHLCV for df in frames.values())
    assert (stats.requested, stats.with_bars, stats.dropped, stats.no_bars) == (2, 2, 0, [])
    assert stats.session == SCAN_DAY and stats.feed == "sip"


def test_download_bars_survives_a_symbol_with_no_bars(fake_alpaca, ohlcv):
    """A delisted ticker returns nothing from Alpaca; it is named, not fatal."""
    fake_alpaca.add_history("BURST", ohlcv("burst"))
    frames, stats = _fetch(["BURST", "GONE"])
    assert list(frames) == ["BURST"]
    assert stats.no_bars == ["GONE"] and stats.with_bars == 1


def test_the_universe_is_requested_in_batches_that_lose_no_symbol(fake_alpaca, ohlcv, monkeypatch):
    """The batches must partition the universe: a name in none of them is
    never scanned, a name in two is measured twice."""
    universe = _coverage(fake_alpaca, ohlcv, fresh=25)
    attempts = _attempt_recorder(monkeypatch, {})

    _fetch(universe, batch_size=10)

    assert [len(a) for a in attempts] == [10, 10, 5]
    assert [t for batch in attempts for t in batch] == universe


def test_a_universe_smaller_than_one_batch_is_one_request(fake_alpaca, ohlcv, monkeypatch):
    universe = _coverage(fake_alpaca, ohlcv, fresh=2)
    attempts = _attempt_recorder(monkeypatch, {})
    _fetch(universe)
    assert attempts == [universe]


def test_a_batch_that_fails_once_is_retried_and_keeps_its_symbols(fake_alpaca, ohlcv, monkeypatch):
    """The successful-retry path: a transient reset costs nothing, and every
    out-parameter the first attempt would have filled is filled by the retry
    -- dropping `duplicates=` from the retry once left the suite green."""
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    universe = _coverage(fake_alpaca, ohlcv, fresh=12)
    fake_alpaca.send_session_bar_twice(universe[0], copies=2)
    attempts = _attempt_recorder(monkeypatch, {0: ConnectionError("connection reset by peer")})

    frames, stats = _fetch(universe)

    assert attempts == [universe, universe], "the retry must re-ask for the whole batch"
    assert stats.dropped == 0 and stats.with_bars == 12
    assert set(frames) == set(universe), "a retried batch loses nothing"
    assert stats.duplicate_bars == 2, "a batch that failed once still counts its duplicates"


def test_the_retry_waits_before_asking_again(fake_alpaca, ohlcv, monkeypatch):
    """Without a pause the retry is a second request into whatever rate
    limit or outage refused the first one, microseconds later."""
    slept: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda seconds: slept.append(seconds))
    _coverage(fake_alpaca, ohlcv, fresh=2)
    _attempt_recorder(monkeypatch, {0: ConnectionError("connection reset by peer")})

    _fetch(["SF0", "SF1"])

    assert slept == [RETRY_WAIT_SECONDS] and slept[0] > 0


def test_a_batch_that_fails_twice_drops_every_symbol_in_it(fake_alpaca, ohlcv, monkeypatch):
    """The cost of a permanent failure is the batch, not the symbol."""
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    universe = _coverage(fake_alpaca, ohlcv, fresh=12)
    reset = ConnectionError("connection reset by peer")
    _attempt_recorder(monkeypatch, {0: reset, 1: reset})

    frames, stats = _fetch(universe, batch_size=3)

    assert stats.dropped == 3, "the whole batch, not the one symbol that failed"
    assert stats.with_bars == 9
    assert set(frames).isdisjoint(universe[:3]) and len(frames) == 9


def test_a_transient_failure_is_still_retried_and_dropped(fake_alpaca, ohlcv, monkeypatch):
    """A reset connection keeps the retry-then-drop behaviour and is not
    mistaken for a refused feed."""
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    fake_alpaca.add_history("AAA", ohlcv("burst"))
    fake_alpaca.raise_on_bars = ConnectionError("connection reset by peer")

    frames, stats = _fetch(["AAA"])

    assert frames == {} and stats.dropped == 1
    assert len(fake_alpaca.bar_requests) == 2, "one retry, then the batch is dropped"


def test_a_few_dropped_symbols_are_counted_and_do_not_stop_the_download(fake_alpaca, ohlcv, monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    universe = _coverage(fake_alpaca, ohlcv, fresh=12)
    fake_alpaca.raise_on_bars = ConnectionError("connection reset by peer")
    fake_alpaca.fail_symbols = {"SF0"}

    frames, stats = _fetch(universe, batch_size=1)

    assert stats.dropped == 1 and "SF0" not in frames and len(frames) == 11


def test_half_the_universe_dropped_is_counted_and_left_for_the_caller_to_judge(
    fake_alpaca, ohlcv, monkeypatch
):
    """The guards are the caller's; what this module owes them is the count,
    with nothing else confused into it."""
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    universe = _coverage(fake_alpaca, ohlcv, fresh=12)
    fake_alpaca.raise_on_bars = ConnectionError("connection reset by peer")
    fake_alpaca.fail_symbols = {"SF0", "SF1", "SF2", "SF3", "SF4", "SF5"}

    frames, stats = _fetch(universe, batch_size=1)

    assert stats.dropped == 6 and stats.no_bars == [] and stats.with_bars == 6


def test_the_counts_partition_what_was_asked_for(fake_alpaca, ohlcv, monkeypatch):
    """requested == with_bars + dropped + no_bars, on a universe with all
    three kinds in it -- so no name is on two lines and none on none."""
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    universe = _coverage(fake_alpaca, ohlcv, fresh=12) + ["NOSUCH"]
    fake_alpaca.raise_on_bars = ConnectionError("connection reset by peer")
    fake_alpaca.fail_symbols = {"SF0"}

    _, stats = _fetch(universe, batch_size=1)

    assert (stats.requested, stats.with_bars, stats.dropped, stats.no_bars) == (13, 11, 1, ["NOSUCH"])
    assert stats.requested == stats.with_bars + stats.dropped + len(stats.no_bars)


# --- a feed this account cannot use ----------------------------------------


def test_a_refused_feed_aborts_the_download_instead_of_emptying_it(fake_alpaca, ohlcv):
    """403 on every batch, retried and dropped, is a completed download that
    found nothing -- the same output as a quiet market."""
    fake_alpaca.add_history("AAA", ohlcv("burst"))
    fake_alpaca.raise_on_bars = _alpaca_error(403, DENIAL)

    # The phrase, not the bare feed name: the notice lists EVERY feed.
    with pytest.raises(FeedNotAuthorizedError, match=f"refused the {DEFAULT_FEED.value!r} data feed"):
        _fetch(["AAA"])

    assert len(fake_alpaca.bar_requests) == 1, "a refusal is not transient; do not retry it"


def test_a_rejected_key_is_not_reported_as_a_feed_this_plan_lacks(fake_alpaca, ohlcv):
    """401 and 403 have opposite fixes and used to produce one message that
    sent a typo shopping for a data plan. The class name reaches the failure
    email, so it is the first word the operator reads."""
    fake_alpaca.add_history("AAA", ohlcv("burst"))
    fake_alpaca.raise_on_bars = _alpaca_error(401, "request is not authorized")

    with pytest.raises(CredentialsRejectedError) as caught:
        _fetch(["AAA"])

    said = str(caught.value)
    assert "ALPACA_API_KEY" in said and "ALPACA_SECRET_KEY" in said
    assert "subscribe" not in said, "a rejected key is not something you fix by subscribing"
    assert len(fake_alpaca.bar_requests) == 1


def test_a_refused_feed_still_says_feed_and_not_credentials(fake_alpaca, ohlcv):
    """The control: a 403 has to keep naming the feed."""
    fake_alpaca.add_history("AAA", ohlcv("burst"))
    fake_alpaca.raise_on_bars = _alpaca_error(403, DENIAL)

    with pytest.raises(FeedNotAuthorizedError) as caught:
        _fetch(["AAA"])

    assert f"refused the {DEFAULT_FEED.value!r} data feed" in str(caught.value)
    assert not isinstance(caught.value, CredentialsRejectedError)


def test_neither_refusal_asserts_a_cause_it_cannot_know(fake_alpaca, ohlcv):
    """The status-to-cause mapping is inferred from the SDK, so each message
    leads with what the status says and names the other possibility second."""
    fake_alpaca.add_history("AAA", ohlcv("burst"))

    fake_alpaca.raise_on_bars = _alpaca_error(401, "request is not authorized")
    with pytest.raises(CredentialsRejectedError) as unauth:
        _fetch(["AAA"])

    fake_alpaca.bar_requests.clear()
    fake_alpaca.raise_on_bars = _alpaca_error(403, DENIAL)
    with pytest.raises(FeedNotAuthorizedError) as forbidden:
        _fetch(["AAA"])

    assert "SCAN_FEED" in str(unauth.value), "the 401 message names the feed possibility too"
    assert "ALPACA_API_KEY" in str(forbidden.value), "and the 403 names the credential one"


def test_a_refusal_is_recognised_from_the_message_when_no_status_survives(fake_alpaca, ohlcv):
    fake_alpaca.add_history("AAA", ohlcv("burst"))
    fake_alpaca.raise_on_bars = _alpaca_error(None, DENIAL)
    with pytest.raises(FeedNotAuthorizedError):
        _fetch(["AAA"])
    assert len(fake_alpaca.bar_requests) == 1


def test_a_status_less_refusal_whose_body_says_not_permitted_is_permanent():
    assert _is_permanent_refusal(_alpaca_error(None, "this endpoint is not permitted for your plan"))
    assert _is_permanent_refusal(_alpaca_error(None, DENIAL))
    assert _is_permanent_refusal(_alpaca_error(None, "invalid feed: delayed_sip"))
    assert _is_permanent_refusal(_alpaca_error(403, "forbidden"))
    assert _is_permanent_refusal(_alpaca_error(401, "unauthorized"))
    assert not _is_permanent_refusal(_alpaca_error(None, "internal server error"))
    assert not _is_permanent_refusal(_alpaca_error(500, "internal server error"))
    assert not _is_permanent_refusal(ConnectionError("connection reset by peer"))


def test_a_feed_refusal_that_only_arrives_on_the_retry_still_aborts_the_download(
    fake_alpaca, ohlcv, monkeypatch
):
    """A reset first, then the 403: handled on the first attempt only, every
    batch would retry, be refused and be dropped, ending in nothing."""
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    universe = _coverage(fake_alpaca, ohlcv, fresh=12)
    _attempt_recorder(monkeypatch, {
        0: ConnectionError("connection reset by peer"),
        1: _alpaca_error(403, DENIAL),
    })

    with pytest.raises(FeedNotAuthorizedError, match=f"refused the {DEFAULT_FEED.value!r} data feed"):
        _fetch(universe)


def test_a_feed_name_the_endpoint_does_not_take_is_refused_on_the_first_batch(fake_alpaca, ohlcv):
    """Observed on Actions on 6 Sep 2026: {"message":"invalid feed:
    delayed_sip"} on every batch, both attempts, with no status the
    classifier knew, so it was retried and dropped six times over and the
    result read as an empty market."""
    fake_alpaca.add_history("AAA", ohlcv("burst"))
    fake_alpaca.raise_on_bars = _alpaca_error(None, "invalid feed: delayed_sip")

    with pytest.raises(FeedNotAuthorizedError) as caught:
        _fetch(["AAA"], feed=DataFeed.DELAYED_SIP)

    said = str(caught.value)
    assert "delayed_sip" in said and "does not take the feed name" in said
    assert "'sip'" in said and "'iex'" in said, "both routes that are known to exist"
    assert "subscribe" not in said, "no plan carries a name the endpoint refuses"
    assert len(fake_alpaca.bar_requests) == 1, "not retried, not dropped: refused once"


# ====================================== the real SDK's transport, bounded ==


def test_real_sdk_bounds_every_page_and_preserves_the_request(credentials, monkeypatch, ohlcv):
    """Only HTTPAdapter.send is replaced; everything above it is the real
    SDK and Requests session, including pagination."""
    calls = []
    session = date(2026, 9, 8)
    bars = _raw_bars(ohlcv("burst"), session)

    def send(adapter, request, **kwargs):
        calls.append((request, kwargs))
        payload = ({"bars": {"BURST": bars[:-1]}, "next_page_token": "page-two"}
                   if len(calls) == 1 else {"bars": {"BURST": bars[-1:]}})
        return _response(request, payload)

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    frames = _batch(get_clients(), ["BURST"], session)

    assert len(calls) == 2 and len(frames["BURST"]) == len(bars)
    assert all(options["timeout"] == (5, 30) for _, options in calls)
    first, second = [parse_qs(urlsplit(request.url).query) for request, _ in calls]
    assert first["adjustment"] == ["split"] and first["feed"] == ["sip"]
    assert first["timeframe"] == ["1Day"] and first["symbols"] == ["BURST"]
    assert "page_token" not in first and second["page_token"] == ["page-two"]
    assert all(request.headers["APCA-API-KEY-ID"] == "test-not-a-real-key" for request, _ in calls)


def test_timeout_is_client_scoped_and_explicit_overrides_are_preserved(credentials, monkeypatch):
    seen = []

    def send(adapter, request, **kwargs):
        seen.append(kwargs["timeout"])
        return _response(request, {})

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    client = get_clients()
    client._session.get("https://example.test/data")
    client._session.get("http://example.test/data", timeout=(2, 4))
    client._session.get("http://example.test/data", timeout=None)
    with requests.Session() as unrelated:
        unrelated.get("https://example.test/unrelated")

    assert seen == [(5, 30), (2, 4), (5, 30), None]


def test_a_timeout_uses_the_single_batch_retry(credentials, monkeypatch, ohlcv):
    calls, sleeps = [], []
    session = date(2026, 9, 8)
    bars = _raw_bars(ohlcv("burst"), session)

    def send(adapter, request, **kwargs):
        calls.append(kwargs["timeout"])
        if len(calls) == 1:
            raise requests.ReadTimeout("synthetic stalled market-data response")
        return _response(request, {"bars": {"BURST": bars}})

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    monkeypatch.setattr(market_data.time, "sleep", sleeps.append)

    frames, stats = download_bars(get_clients(), ["BURST"], session)

    assert list(frames) == ["BURST"] and len(frames["BURST"]) == len(bars)
    assert calls == [(5, 30), (5, 30)] and sleeps == [3]
    assert stats.dropped == 0


def test_repeated_timeouts_drop_the_batch_after_two_attempts(credentials, monkeypatch):
    calls = []

    def send(adapter, request, **kwargs):
        calls.append(kwargs["timeout"])
        raise requests.ConnectTimeout("synthetic stalled connection")

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    monkeypatch.setattr(market_data.time, "sleep", lambda seconds: None)

    frames, stats = download_bars(get_clients(), [f"Q{letter}" for letter in "ABCDEFGHIJ"], date(2026, 9, 8))

    assert frames == {} and calls == [(5, 30), (5, 30)]
    assert stats.dropped == 10 and stats.with_bars == 0


def test_sdk_rate_limit_retry_keeps_its_own_policy_and_timeout(credentials, monkeypatch):
    calls, sleeps = [], []

    def send(adapter, request, **kwargs):
        calls.append(kwargs["timeout"])
        if len(calls) == 1:
            return _response(request, {"message": "synthetic rate limit"}, status=429)
        return _response(request, {"bars": {}})

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    monkeypatch.setattr(market_data.time, "sleep", sleeps.append)
    client = get_clients()

    assert _batch(client, ["BURST"], date(2026, 9, 8)) == {}
    assert calls == [(5, 30), (5, 30)]
    assert sleeps == [client._retry_wait]


# ================================================= what the log says ==


def test_download_bars_names_the_symbols_the_feed_returned_nothing_for(fake_alpaca, ohlcv, caplog):
    """A symbol the feed answers with NOTHING is in no frame and so in no
    later count; it reaches a warning with the names and the stats."""
    universe = _coverage(fake_alpaca, ohlcv, fresh=8, stale=1) + ["NOSUCH", "ALSOGONE"]
    with caplog.at_level(logging.INFO, logger="src.market_data"):
        _, stats = _fetch(universe)

    assert stats.no_bars == ["ALSOGONE", "NOSUCH"]
    warned = _warned(caplog, "no bar at all")
    assert "2 of 11 symbols" in warned and "ALSOGONE, NOSUCH" in warned
    progress = [r.getMessage() for r in caplog.records if r.getMessage().startswith("Downloaded ")]
    assert progress == ["Downloaded 11/11 symbols"]


def test_download_bars_counts_the_bars_the_feed_sent_twice_and_names_them(fake_alpaca, ohlcv, caplog):
    """Named in a warning, most-repeated first, with the extra copies as the
    number -- the denominator is the names that ANSWERED."""
    universe = _coverage(fake_alpaca, ohlcv, fresh=8, stale=1)
    fake_alpaca.send_session_bar_twice(universe[0])
    fake_alpaca.send_session_bar_twice(universe[1], copies=2)
    with caplog.at_level(logging.INFO, logger="src.market_data"):
        _, stats = _fetch(universe)

    assert stats.duplicate_bars == 3, "the EXTRA copies: one name sent one, the other two"
    assert stats.duplicates == {universe[0]: 1, universe[1]: 2}
    warned = _warned(caplog, "already sent")
    assert ("2 of the 9 symbols that answered carried a timestamp the response had already "
            "sent (3 extra bar(s) dropped), keeping the copy that arrived last") in warned
    assert warned.index(f"{universe[1]} (2)") < warned.index(f"{universe[0]} (1)"), "most-repeated first"


def test_a_download_with_no_duplicate_bars_counts_zero_and_warns_of_nothing(fake_alpaca, ohlcv, caplog):
    universe = _coverage(fake_alpaca, ohlcv, fresh=8, stale=1)
    with caplog.at_level(logging.INFO, logger="src.market_data"):
        _, stats = _fetch(universe)
    assert stats.duplicate_bars == 0 and stats.duplicates == {}
    assert not [r for r in caplog.records if "already sent" in r.getMessage()]


@pytest.mark.parametrize("names, ellipsis", [(8, False), (9, True)])
def test_a_warning_that_caps_its_list_of_names_says_so_only_when_it_capped(
    fake_alpaca, ohlcv, caplog, names, ellipsis
):
    """Both name-listing warnings print at most eight and mark the cut with
    "..." -- eight names print all eight with no marker, nine print eight
    and the marker."""
    universe = _coverage(fake_alpaca, ohlcv, fresh=12) + [f"NOSUCH{i}" for i in range(names)]
    for symbol in universe[:names]:
        fake_alpaca.send_session_bar_twice(symbol)
    with caplog.at_level(logging.INFO, logger="src.market_data"):
        _fetch(universe)

    for message, named in ((_warned(caplog, "already sent"), "SF"),
                           (_warned(caplog, "no bar at all"), "NOSUCH")):
        assert message.endswith("...") is ellipsis, message
        assert message.count(named) == min(names, 8), message


def test_the_stale_names_are_warned_with_their_last_dates(fake_alpaca, ohlcv, caplog):
    universe = _coverage(fake_alpaca, ohlcv, fresh=8, stale=1)
    with caplog.at_level(logging.INFO, logger="src.market_data"):
        _, stats = _scan(universe)
    warned = _warned(caplog, "had no bar for")
    assert f"1 of 9 symbols had no bar for {SCAN_DAY}" in warned
    assert f"SS0 (last {previous_session(SCAN_DAY)})" in warned
    assert stats.stale == {"SS0": previous_session(SCAN_DAY)}


# ================================================ stale, gapped, closure ==


def test_only_the_current_copy_of_a_name_is_kept(fake_alpaca, ohlcv):
    """One frame registered twice: once current, once as a halted name whose
    last print was five sessions ago. Only the date differs."""
    frame = ohlcv("burst")
    fake_alpaca.add_history("NOW", frame)
    fake_alpaca.add_history("HALT", frame, stale_sessions=5)

    fresh, stats = _scan(["NOW", "HALT"])

    assert list(fresh) == ["NOW"] and list(stats.stale) == ["HALT"]


def test_a_download_where_nothing_traded_the_session_is_all_stale_with_a_newest_date(fake_alpaca, ohlcv):
    """The market-holiday shape, the wrong-day-cron shape and the dead-feed
    shape: every newest bar is an earlier session. The guard that refuses to
    call it a quiet market is the caller's; what it needs is here."""
    for ticker in ("AAA", "BBB"):
        fake_alpaca.add_history(ticker, ohlcv("burst"), stale_sessions=1)

    fresh, stats = _scan(["AAA", "BBB"])

    assert fresh == {} and stats.with_bars == 2 and len(stats.stale) == 2
    assert newest_stale(stats.stale) == previous_session(SCAN_DAY)
    assert stats.fresh == 0 and stats.ready == 0


def test_download_bars_reports_the_shape_of_the_download_it_ran(fake_alpaca, ohlcv):
    universe = _coverage(fake_alpaca, ohlcv, fresh=8, stale=1) + ["NOSUCH"]

    fresh, stats = _scan(universe)

    assert stats.requested == 10
    assert stats.with_bars == 9, "NOSUCH registered no history at all"
    assert stats.fresh == 8 and len(fresh) == 8
    assert list(stats.stale) == ["SS0"]
    assert stats.no_bars == ["NOSUCH"]
    assert stats.dropped == 0
    assert stats.session == SCAN_DAY and stats.feed == "sip"
    assert stats.previous_session == previous_session(SCAN_DAY)
    assert stats.previous_session_observed is False
    assert stats.closure_min_symbols == DEFAULT_MIN_SYMBOLS


def test_the_frames_handed_back_include_the_names_the_session_rules_dropped(fake_alpaca, ohlcv):
    """download_bars returns every frame with bars in it, stale or holed:
    the rules are about tonight, and a name halted tonight traded the
    earlier sessions a later measurement needs."""
    names = [f"F{i}" for i in range(12)]
    for i, name in enumerate(names):
        fake_alpaca.add_history(name, ohlcv("burst", variant=i))
    fake_alpaca.add_history("STALE", ohlcv("base", variant=90), stale_sessions=3)
    fake_alpaca.add_history("HOLE", ohlcv("base", variant=91), gap_before_session=True)

    frames, stats = _fetch(names + ["STALE", "HOLE"])
    fresh = apply_session_rules(frames, SCAN_DAY, stats)

    assert set(frames) == set(names) | {"STALE", "HOLE"}, "every frame with bars, dropped or not"
    assert set(fresh) == set(names)
    assert "STALE" in stats.stale and "HOLE" in stats.gapped
    assert stats.ready == 12


def test_a_hole_before_the_session_is_refused_rather_than_measured_across(ohlcv):
    """Freshness checks only the newest bar. A dropped bar the session before
    leaves the second-newest two sessions old, and a genuine BarSet once
    printed a 12.0% one-day move as a 12.45% two-day one."""
    rows = _raw_bars(ohlcv("burst"), SESSION)
    whole = _batch(_genuine_barset("X", rows), ["X"])
    holed = _batch(_genuine_barset("X", rows[:-2] + rows[-1:]), ["X"])
    assert last_bar_date(holed["X"]) == SESSION, "precondition: the hole passes freshness"
    assert _gain(holed["X"]) != _gain(whole["X"]), "precondition: the two-day move is a different number"

    kept, gapped = drop_gapped(holed, SESSION)
    assert kept == {} and gapped == {"X": pd.Timestamp(rows[-3]["t"]).date()}
    kept, gapped = drop_gapped(whole, SESSION)
    assert list(kept) == ["X"] and gapped == {}


def test_a_gapped_symbol_is_counted_and_not_kept(fake_alpaca, ohlcv):
    names = [f"G{i}" for i in range(12)]
    for i, name in enumerate(names):
        fake_alpaca.add_history(name, ohlcv("burst", variant=i))
    fake_alpaca.add_history("HOLE", ohlcv("burst", variant=99), gap_before_session=True)

    fresh, stats = _scan(names + ["HOLE"])

    assert "HOLE" in stats.gapped and "HOLE" not in fresh and len(fresh) == 12
    # An ordinary day: agreeing with the arithmetic is not "observed".
    assert stats.previous_session == previous_session(SCAN_DAY)
    assert stats.previous_session_observed is False


def _closed_market(fake_alpaca, ohlcv, n: int, *, prefix: str = "G", variant0: int = 0) -> list[str]:
    names = [f"{prefix}{i}" for i in range(n)]
    for i, name in enumerate(names):
        fake_alpaca.add_history(name, ohlcv("burst", variant=variant0 + i))
    fake_alpaca.close_session(LABOR_DAY)
    return names


def test_a_business_day_no_name_printed_is_a_closure_not_a_hole_on_every_name(fake_alpaca, ohlcv, caplog):
    """Every frame lacks Monday 7 Sep. The session before Tuesday's is Friday
    4 Sep, read off the night's frames, and all twelve are measurable."""
    names = _closed_market(fake_alpaca, ohlcv, 12)
    with caplog.at_level(logging.INFO, logger="src.market_data"):
        fresh, stats = _scan(names, TUESDAY_AFTER_LABOR_DAY)

    assert stats.gapped == {} and len(fresh) == 12
    assert stats.previous_session == date(2026, 9, 4)
    assert stats.previous_session_observed is True
    assert (stats.closure_voters, stats.closure_agreed, stats.closure_day) == (12, 12, date(2026, 9, 4))
    assert stats.previous_session_printed == 12
    warned = _warned(caplog, "market closure")
    assert "12 of 12 fresh frames carry 2026-09-04" in warned and "measures against 2026-09-04" in warned


def test_a_closure_read_off_the_batch_does_not_excuse_one_names_own_hole(fake_alpaca, ohlcv):
    """A name halted on Friday 4 Sep, on the week of the closure, is still a
    hole: its bar before the session is Thursday."""
    names = _closed_market(fake_alpaca, ohlcv, 12)
    fake_alpaca.add_history("HOLE", ohlcv("burst", variant=99), gap_before_session=True)

    fresh, stats = _scan(names + ["HOLE"], TUESDAY_AFTER_LABOR_DAY)

    assert stats.gapped == {"HOLE": date(2026, 9, 3)}
    assert "HOLE" not in fresh and len(fresh) == 12


def test_a_closure_is_read_only_from_the_minimum_of_voting_names(fake_alpaca, ohlcv):
    """Below the minimum the arithmetic stands -- every `--tickers` smoke
    test -- so one fewer than the minimum stays gapped and exactly the
    minimum votes it through; `>=` and `>` are one character apart."""
    n = DEFAULT_MIN_SYMBOLS
    names = _closed_market(fake_alpaca, ohlcv, n)

    fresh, stats = _scan(names[:n - 1], TUESDAY_AFTER_LABOR_DAY)
    assert len(stats.gapped) == n - 1 and fresh == {}
    assert stats.previous_session == LABOR_DAY and stats.previous_session_observed is False

    fresh, stats = _scan(names, TUESDAY_AFTER_LABOR_DAY)
    assert stats.gapped == {} and len(fresh) == n
    assert stats.previous_session_observed is True


def test_a_split_vote_moves_the_previous_session_nowhere(fake_alpaca, ohlcv):
    """MORE than half: ten on Friday and ten on Thursday agree on nothing,
    so every one of them is a hole; one more on Friday's side and it is a
    closure with nine holes."""
    friday = _closed_market(fake_alpaca, ohlcv, 10, prefix="F")
    thursday = [f"T{i}" for i in range(10)]
    for i, name in enumerate(thursday):
        fake_alpaca.add_history(name, ohlcv("burst", variant=20 + i), gap_before_session=True)

    fresh, stats = _scan(friday + thursday, TUESDAY_AFTER_LABOR_DAY)
    assert fresh == {} and len(stats.gapped) == 20
    assert stats.previous_session_observed is False

    fake_alpaca.add_history("F10", ohlcv("burst", variant=40))
    fresh, stats = _scan(friday + ["F10"] + thursday, TUESDAY_AFTER_LABOR_DAY)
    assert sorted(fresh) == sorted(friday + ["F10"])
    assert set(stats.gapped) == set(thursday)


def test_the_vote_is_over_the_whole_download_and_not_each_batch(fake_alpaca, ohlcv):
    """The last batch of a universe -- three names when the list is 13 long
    at a batch of 10 -- must not fall below the minimum and read as holes."""
    names = _closed_market(fake_alpaca, ohlcv, 13)
    fresh, stats = _scan(names, TUESDAY_AFTER_LABOR_DAY, batch_size=10)
    assert stats.gapped == {} and len(fresh) == 13


def _frames_whose_bar_before_the_session_is(days: list[date], session: date, n: int) -> dict:
    """`n` frames indexed on `days` then `session`, one row each."""
    out = {}
    for i in range(n):
        index = pd.DatetimeIndex([pd.Timestamp(d) for d in days] + [pd.Timestamp(session)])
        out[f"P{i}"] = pd.DataFrame({"Close": 10.0, "Volume": 1e6}, index=index)
    return out


def test_a_majority_can_move_the_previous_session_back_and_never_forward():
    """A phantom Saturday every frame carries is LATER than the arithmetic
    and must not become the previous session; the same frames with an
    earlier shared bar do move it -- and the gap rule then refuses the
    phantom's frames, which is the half that keeps `>=` out of the guard."""
    monday, saturday, friday, thursday = (date(2026, 9, 14), date(2026, 9, 12),
                                          date(2026, 9, 11), date(2026, 9, 10))
    phantom = _frames_whose_bar_before_the_session_is([friday, saturday], monday, 12)
    assert observed_previous_session(phantom, monday) == (friday, False)
    kept, gapped = drop_gapped(phantom, monday, friday)
    assert kept == {} and sorted(gapped) == sorted(f"P{i}" for i in range(12))
    assert set(gapped.values()) == {saturday}

    earlier = _frames_whose_bar_before_the_session_is([thursday], monday, 12)
    assert observed_previous_session(earlier, monday) == (thursday, True)
    assert previous_session(monday) == friday, "precondition: the arithmetic says Friday"


def test_a_frame_with_one_bar_has_no_vote_and_stays_a_hole():
    """Ten single-bar frames beside ten that agree on Thursday are ten of
    ten voting, not ten of twenty; each is still refused by the gap rule."""
    monday, thursday = date(2026, 9, 14), date(2026, 9, 10)
    frames = _frames_whose_bar_before_the_session_is([thursday], monday, 10)
    for i in range(10):
        frames[f"S{i}"] = pd.DataFrame({"Close": 10.0, "Volume": 1e6},
                                       index=pd.DatetimeIndex([pd.Timestamp(monday)]))

    assert observed_previous_session(frames, monday) == (thursday, True)
    kept, gapped = drop_gapped(frames, monday, thursday)
    assert sorted(kept) == sorted(f"P{i}" for i in range(10))
    assert sorted(gapped) == sorted(f"S{i}" for i in range(10))
    assert set(gapped.values()) == {monday}, "a frame with no bar before the session is filed under its newest"
    # With NO voter at all and the minimum switched off, the arithmetic
    # stands rather than max() raising over an empty vote.
    alone = {k: v for k, v in frames.items() if k.startswith("S")}
    assert observed_previous_session(alone, monday, min_symbols=0) == (previous_session(monday), False)


def test_a_nat_in_a_frames_index_neither_votes_nor_takes_the_download_down():
    """As many NaT frames as voters: a NaT that counted would be half the
    electorate and turn ten of ten into ten of twenty."""
    monday, thursday = date(2026, 9, 14), date(2026, 9, 10)
    frames = _frames_whose_bar_before_the_session_is([thursday], monday, 10)
    for i in range(10):
        frames[f"NAT{i}"] = pd.DataFrame({"Close": 10.0, "Volume": 1e6},
                                         index=pd.DatetimeIndex([pd.NaT, pd.Timestamp(monday)]))

    assert observed_previous_session(frames, monday) == (thursday, True)
    kept, gapped = drop_gapped(frames, monday, thursday)
    assert sorted(gapped) == sorted(f"NAT{i}" for i in range(10))
    assert not any(k.startswith("NAT") for k in kept)


def test_a_name_that_printed_the_session_before_is_the_disproof_of_a_closure(fake_alpaca, ohlcv):
    """Seven names halted on Tuesday and five that traded it used to give the
    seven a bare majority: the answer moved back to Monday, the five healthy
    names became holes and the seven were measured across theirs. One frame
    carrying a bar for the session before is decisive."""
    healthy = [f"H{i}" for i in range(5)]
    holed = [f"K{i}" for i in range(7)]
    for i, name in enumerate(healthy):
        fake_alpaca.add_history(name, ohlcv("burst", variant=i))
    for i, name in enumerate(holed):
        fake_alpaca.add_history(name, ohlcv("burst", variant=20 + i), gap_before_session=True)

    fresh, stats = _scan(healthy + holed, SCAN_DAY)

    assert stats.previous_session == date(2026, 9, 8)
    assert stats.previous_session_observed is False
    assert sorted(stats.gapped) == sorted(holed)
    assert sorted(fresh) == sorted(healthy)


def test_the_disproof_is_read_off_every_frame_downloaded_and_not_only_the_voters(fake_alpaca, ohlcv):
    """A name that stopped printing ON the session before still printed on
    it, so it says the market traded that day -- and it is not a voter."""
    holed = [f"K{i}" for i in range(12)]
    quit_on_tuesday = [f"S{i}" for i in range(10)]
    for i, name in enumerate(holed):
        fake_alpaca.add_history(name, ohlcv("burst", variant=i), gap_before_session=True)
    for i, name in enumerate(quit_on_tuesday):
        fake_alpaca.add_history(name, ohlcv("flat", variant=i), stale_sessions=1)

    fresh, stats = _scan(holed + quit_on_tuesday, SCAN_DAY)

    assert stats.previous_session == date(2026, 9, 8)
    assert stats.previous_session_observed is False
    assert stats.previous_session_printed == 10
    assert sorted(stats.gapped) == sorted(holed) and fresh == {}


def test_only_the_fresh_frames_vote_on_what_the_session_before_was(fake_alpaca, ohlcv):
    """A stale frame's evidence is about an earlier week. Four names that
    traded Tuesday after the Monday closure carry Friday; five that stopped
    printing on Thursday carry Thursday, and would outvote them 5-4."""
    fresh_names = [f"F{i}" for i in range(4)]
    for i, name in enumerate(fresh_names):
        fake_alpaca.add_history(name, ohlcv("burst", variant=i))
    dead = [f"D{i}" for i in range(5)]
    for i, name in enumerate(dead):
        fake_alpaca.add_history(name, ohlcv("flat", variant=i), stale_sessions=3)
    fake_alpaca.close_session(LABOR_DAY)

    fresh, stats = _scan(fresh_names + dead, TUESDAY_AFTER_LABOR_DAY, min_symbols=3)

    assert stats.previous_session == date(2026, 9, 4)
    assert stats.previous_session_observed is True
    assert sorted(fresh) == sorted(fresh_names) and stats.gapped == {}
    assert stats.closure_min_symbols == 3, "the minimum recorded is the one this run applied"


def test_a_weekend_phantom_earlier_than_the_arithmetic_is_not_the_session_before():
    """The day after a weekday holiday opens a window of non-session dates
    EARLIER than the arithmetic: twelve frames whose bar before Tuesday 8
    Sep is a phantom Sunday 6 Sep used to elect the Sunday."""
    tuesday, sunday, friday = date(2026, 9, 8), date(2026, 9, 6), date(2026, 9, 4)
    frames = _frames_whose_bar_before_the_session_is([friday, sunday], tuesday, 12)

    assert previous_session(tuesday) == date(2026, 9, 7), "precondition: the arithmetic says Monday"
    assert observed_previous_session(frames, tuesday) == (date(2026, 9, 7), False)
    real = _frames_whose_bar_before_the_session_is([friday], tuesday, 12)
    assert observed_previous_session(real, tuesday) == (friday, True)


def _nan_on_the_bar_before_the_session(ohlcv, column: str) -> pd.DataFrame:
    frame = ohlcv("burst").copy()
    frame.iloc[-2, frame.columns.get_loc(column)] = float("nan")
    return frame


@pytest.mark.parametrize("column", ["Volume", "Close"])
def test_a_nan_on_the_bar_before_the_session_is_a_hole_and_not_a_two_session_move(
    fake_alpaca, ohlcv, column
):
    """The gap rule reads the frame a detector will measure, not the index:
    a bar that is present but carries no readable close or volume is a hole,
    and the session cannot be measured against the one two back."""
    fake_alpaca.add_history("NANB", _nan_on_the_bar_before_the_session(ohlcv, column))
    quiet = [f"Q{i}" for i in range(11)]
    for i, name in enumerate(quiet):
        fake_alpaca.add_history(name, ohlcv("flat", variant=i))
    served = fake_alpaca.bars_frame(["NANB"], end=SCAN_DAY).loc["NANB"]
    assert previous_session(SCAN_DAY) in {pd.Timestamp(t).date() for t in served.index}, (
        "precondition: the bar IS there -- it is the reading of it that fails")

    fresh, stats = _scan(["NANB"] + quiet, SCAN_DAY)

    assert "NANB" not in fresh and len(fresh) == 11
    assert stats.gapped == {"NANB": date(2026, 9, 7)}
    assert stats.stale == {}, "the session's own bar is readable"


def test_a_nat_on_the_newest_bar_is_a_stale_name_without_a_date_and_not_a_TypeError(fake_alpaca, ohlcv):
    """As many NaT frames as dated ones, so a max() that compared them could
    not pass by accident: the name is stale with no date, and newest_stale()
    still answers with the date the others carry."""
    names = [f"N{i}" for i in range(20)]
    for i, name in enumerate(names):
        fake_alpaca.add_history(name, ohlcv("flat", variant=i), stale_sessions=3)
    frames, stats = _fetch(names, SCAN_DAY)
    for ticker in names[:10]:
        index = list(frames[ticker].index[:-1]) + [pd.NaT]
        frames[ticker] = frames[ticker].set_axis(pd.DatetimeIndex(index))

    fresh = apply_session_rules(frames, SCAN_DAY, stats)

    assert fresh == {} and len(stats.stale) == 20
    assert sum(1 for last in stats.stale.values() if last is None) == 10
    assert newest_stale(stats.stale) == date(2026, 9, 4)
    assert newest_stale({"A": None}) is None


def test_a_blind_night_is_answered_but_nothing_is_ready(fake_alpaca, ohlcv):
    """Every name that carried the session has a hole on the session before
    and one halted name proves the market traded it: twelve answered, none
    can be measured, and `ready` says so where `with_bars` cannot."""
    names = []
    for i in range(11):
        name = f"H{'ABCDEFGHIJK'[i]}"
        fake_alpaca.add_history(name, ohlcv("burst", variant=i), gap_before_session=True)
        names.append(name)
    fake_alpaca.add_history("HALT", ohlcv("flat", variant=90), stale_sessions=1)

    fresh, stats = _scan(names + ["HALT"], SCAN_DAY)

    assert fresh == {}
    assert stats.with_bars == 12 and len(stats.gapped) == 11 and len(stats.stale) == 1
    assert stats.fresh == 11 and stats.ready == 0
    assert stats.previous_session_printed == 1, "the halted name is the disproof"


# ============================================================ the calendar ==


def _dated(closes, dates: list[str]) -> pd.DataFrame:
    """A frame on the exact dates given, so a hole can be put where the test
    wants it rather than where bdate_range would close it."""
    index = pd.DatetimeIndex(pd.to_datetime(dates), name="timestamp")
    return pd.DataFrame({"Close": [float(c) for c in closes], "Volume": [1_000_000] * len(dates)}, index=index)


_WEEK = ["2026-08-24", "2026-08-25", "2026-08-26", "2026-08-27", "2026-08-28",
         "2026-08-31", "2026-09-01"]


def test_the_session_calendar_is_read_across_frames_by_majority():
    """One frame's hole does not remove a session; one frame's phantom bar
    does not add one; a lone frame is no calendar."""
    whole = _dated(range(7), _WEEK)
    holed = _dated(range(6), _WEEK[:3] + _WEEK[4:])                        # 27 Aug missing
    phantom = _dated(range(8), _WEEK[:5] + ["2026-08-29"] + _WEEK[5:])     # a Saturday bar, mid-frame
    late = _dated(range(2), ["2026-09-01", "2026-09-02"])                   # spans only the end

    days = [d.isoformat() for d in session_calendar({"A": whole, "B": holed, "C": phantom})]

    assert days == _WEEK, "the majority rule settles both"
    assert "2026-08-27" in days, "two of three frames carry the session the third lacks"
    assert "2026-08-29" not in days, "one of three spanning frames carries the Saturday"
    # A phantom that is the LAST bar of one frame, on a Saturday two other
    # frames run past: the spanning test is inclusive of a frame's own first
    # and last bar, or 1 of 2 would keep it.
    ends_on_saturday = _dated(range(6), _WEEK[:5] + ["2026-08-29"])
    past = [d.isoformat() for d in session_calendar({"E": ends_on_saturday, "A": whole, "B": holed})]
    assert "2026-08-29" not in past and past == _WEEK
    assert session_calendar({"B": holed}) == [], "one frame is no calendar: it cannot vote against its own hole"
    # A frame that does not span a date has no vote on it.
    assert "2026-08-27" in [d.isoformat() for d in session_calendar({"B": holed, "A": whole, "L": late})]
    assert session_calendar({}) == [] and session_calendar({"X": None}) == []
    assert session_calendar({"X": whole, "Y": whole.iloc[:0]}) == [], "an empty frame is not a second frame"


def test_the_calendars_majority_is_the_fraction_it_is_given():
    """At the default half, 27 Aug is carried by two of three spanning frames
    and is in; asked for unanimity it is out. Pinned so the parameter is read
    rather than decoration over a hard-coded half."""
    whole = _dated(range(7), _WEEK)
    holed = _dated(range(6), _WEEK[:3] + _WEEK[4:])
    frames = {"A": whole, "B": holed, "C": whole}
    assert "2026-08-27" in [d.isoformat() for d in session_calendar(frames)]
    assert "2026-08-27" in [d.isoformat() for d in session_calendar(frames, min_fraction=0.5)]
    assert "2026-08-27" not in [d.isoformat() for d in session_calendar(frames, min_fraction=1.0)]
    # Exactly half carries it: in at 0.5 (a session missing from half the
    # frames is still a session), out at anything stricter.
    two = {"A": whole, "B": holed}
    assert "2026-08-27" in [d.isoformat() for d in session_calendar(two)]
    assert "2026-08-27" not in [d.isoformat() for d in session_calendar(two, min_fraction=0.51)]


def test_a_nat_in_a_frames_index_is_not_a_session_in_the_calendar():
    """One NaT in a frame's index once took the calendar down on "Cannot
    compare NaT with date"."""
    nat = _dated([100, 101, 102, 103, 104, 110, 111], _WEEK)
    nat.index = pd.DatetimeIndex([pd.NaT if i == 3 else stamp for i, stamp in enumerate(nat.index)])
    whole = _dated([50, 51, 52, 53, 54, 55, 56], _WEEK)
    assert [d.isoformat() for d in session_calendar({"N": nat, "W": whole})] == _WEEK


def test_the_calendar_reads_a_tz_aware_index_the_way_the_sdk_returns_one(ohlcv):
    """The frames the calendar is handed come out of download_bars, whose
    index from a real BarSet is tz-aware UTC at 04:00 or 05:00."""
    rows = _raw_bars(ohlcv("burst", days=7), SESSION)
    a = _batch(_genuine_barset("A", rows), ["A"])["A"]
    b = _batch(_genuine_barset("B", rows[:3] + rows[4:]), ["B"])["B"]
    days = session_calendar({"A": a, "B": b})
    assert days == [pd.Timestamp(r["t"]).date() for r in rows]
    assert days[-1] == SESSION


# ========================================================== the symbol file ==


def _symbol_file(tmp_path, text: str, name: str = "symbols.txt"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_the_symbol_file_is_read_in_file_order(tmp_path):
    """Order is preserved so the file can stay grouped by sector for a human."""
    assert read_symbol_file(_symbol_file(tmp_path, "NVDA\nAAPL\nMSFT\n")) == ["NVDA", "AAPL", "MSFT"]


def test_comments_and_blank_lines_are_not_symbols(tmp_path):
    path = _symbol_file(tmp_path, """
# --- semis ---
NVDA
AMD    # trailing comments too

  MSFT

# --- and nothing else ---
""")
    assert read_symbol_file(path) == ["NVDA", "AMD", "MSFT"]


@pytest.mark.parametrize("line, why", [
    ("nvda", "lower case is not how a ticker is written"),
    ("BRK.B", "class shares are rejected on purpose"),
    ("ABCDEF", "six characters is not a US ticker"),
    ("NVDA AMD", "two symbols on one line"),
    ("NVDA,AMD", "a comma-separated list"),
    ("BF-B", "punctuation of any kind"),
    ("N3VDA", "digits"),
])
def test_a_line_that_is_not_a_ticker_stops_the_run(line, why, tmp_path):
    """A typo must fail the run, not quietly shrink the list."""
    with pytest.raises(SymbolFileError) as excinfo:
        read_symbol_file(_symbol_file(tmp_path, f"NVDA\n{line}\nMSFT\n"))
    message = str(excinfo.value)
    assert "line 2" in message, f"{why}: the operator needs the line number"
    assert line in message, f"{why}: the operator needs the offending text"


def test_a_duplicate_symbol_stops_the_run_and_names_both_lines(tmp_path):
    with pytest.raises(SymbolFileError, match=r"line 4: NVDA is already listed on line 1"):
        read_symbol_file(_symbol_file(tmp_path, "NVDA\nMSFT\n# --- again ---\nNVDA\n"))


def test_an_empty_file_is_not_a_symbol_list(tmp_path):
    with pytest.raises(SymbolFileError, match="no symbols found"):
        read_symbol_file(_symbol_file(tmp_path, ""))


def test_a_file_of_nothing_but_comments_is_not_a_symbol_list(tmp_path):
    with pytest.raises(SymbolFileError, match="no symbols found"):
        read_symbol_file(_symbol_file(tmp_path, "# NVDA\n# MSFT\n\n   \n"))


def test_a_missing_file_raises_the_symbol_file_error_not_an_oserror(tmp_path):
    with pytest.raises(SymbolFileError, match="cannot read symbol file"):
        read_symbol_file(tmp_path / "does-not-exist.txt")


def test_a_byte_order_mark_fails_loudly_rather_than_eating_the_first_symbol(tmp_path):
    """The file is read as plain utf-8, so a BOM stays on the first ticker
    and that line stops the run, reported with !r so it is diagnosable."""
    with pytest.raises(SymbolFileError) as excinfo:
        read_symbol_file(_symbol_file(tmp_path, "﻿NVDA\nMSFT\n"))
    message = str(excinfo.value)
    assert "line 1" in message and "\\ufeff" in message


def test_surrounding_whitespace_is_not_part_of_a_ticker(tmp_path):
    assert read_symbol_file(_symbol_file(tmp_path, "  NVDA\t\n\tMSFT  \n")) == ["NVDA", "MSFT"]


def test_the_checked_in_fallback_symbol_file_parses():
    """data/symbols.txt stays as the reviewed fallback list."""
    symbols = read_symbol_file(SYMBOLS_FILE)
    assert len(symbols) > 100
    assert len(set(symbols)) == len(symbols)
    assert all(_SYMBOL_RE.match(t) for t in symbols)


# ================================================================ the stats ==


def test_download_stats_derived_counts_are_the_arithmetic_the_guards_read():
    stats = DownloadStats(session=SESSION, feed="sip", requested=10, with_bars=8,
                          dropped=1, no_bars=["Z"], duplicates={"A": 2, "B": 1},
                          stale={"S": None}, gapped={"G": SESSION})
    assert stats.duplicate_bars == 3
    assert stats.fresh == 7
    assert stats.ready == 6
    assert stats.previous_session is None and stats.previous_session_observed is False
