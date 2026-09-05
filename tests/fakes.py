"""Test doubles for the three external boundaries the pipeline touches.

  Alpaca    -- StockHistoricalDataClient (daily bars)
  Anthropic -- anthropic.Anthropic (scoring)
  Resend    -- resend.Emails.send (delivery)

Nothing in here opens a socket or reads an API key, and the doubles record
what they were called with so tests can assert on the wiring rather than on
strategy thresholds.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

# --------------------------------------------------------------- Alpaca ----


class FakeBarSet:
    """Stands in for alpaca's BarSet; the scanner only reads `.df`."""

    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df


class FakeAlpaca:
    """Registry + factories for the Alpaca data client.

    `history` maps ticker -> OHLCV frame (capitalised columns, as the rest of
    the codebase uses them). `get_stock_bars` re-shapes them into the
    (symbol, timestamp) MultiIndex frame with lower-case columns that
    alpaca-py actually returns, so the scanner's own renaming is exercised.

    Two things this double does that the previous version did not:

    * It records `request_fields` -- the SDK's own `to_request_fields()` dict,
      i.e. the query the client would actually put on the wire. Asserting on
      the request object's attributes would pass even for a field the SDK
      drops; this is as close to the wire as an offline test gets.

    * Its bars end where the request asked them to end. A registered frame is
      shifted so its newest bar lands on the request's `end` date, the way a
      live API returns bars up to the moment you asked for. Without that the
      fixtures would be permanently months stale and every freshness check
      would fire. `add_history(..., stale_sessions=n)` then holds a symbol n
      sessions further back, which is what a halted or delisted name looks
      like: its data simply stops.

    * It honours `adjustment`. `add_split()` registers a corporate action;
      the frame handed to `add_history` is taken to be the split-adjusted one,
      and a request that does not ask for split adjustment gets the raw prints
      -- pre-split bars at their as-traded price and share count -- exactly as
      Alpaca's `raw` default would return them.
    """

    def __init__(self) -> None:
        self.history: dict[str, pd.DataFrame] = {}
        self.stale_sessions: dict[str, int] = {}
        self.splits: dict[str, tuple[float, int]] = {}
        self.bar_requests: list[Any] = []
        self.request_fields: list[dict] = []
        self.data_clients: list["FakeDataClient"] = []
        self.raise_on_bars: Exception | None = None
        #: When set, only batches containing one of these symbols raise
        #: `raise_on_bars`; every other batch is served normally. A whole-scan
        #: outage and one bad ticker are different failures -- the scanner
        #: drops a fraction of the universe for the second and refuses to
        #: report the scan at all for the first -- and a double that can only
        #: fail everything cannot tell the two apart.
        self.fail_symbols: set[str] = set()
        #: symbols whose bar before the newest one is missing -- see add_history
        self.gapped: set[str] = set()

    # -- registration -------------------------------------------------
    def add_history(self, ticker: str, df: pd.DataFrame, *, stale_sessions: int = 0,
                    gap_before_session: bool = False) -> None:
        """Register bars for `ticker`, whose newest bar is `stale_sessions` old.

        `gap_before_session` removes the bar BEFORE the newest one after the
        frame has been re-dated -- a full-day halt, or a bar the feed dropped.
        It has to be an option here rather than a row deleted from the frame
        handed in, because _align_to_end rebuilds the index as contiguous
        business days: a hole in the input is closed on the way out, which is
        right for every other test and wrong for the one about holes.
        """
        self.history[ticker] = df
        self.stale_sessions[ticker] = stale_sessions
        if gap_before_session:
            self.gapped.add(ticker)
        else:
            self.gapped.discard(ticker)

    def add_split(self, ticker: str, ratio: float, *, sessions_ago: int = 0) -> None:
        """Record a forward split of `ratio`-for-1 with this ex-date.

        `sessions_ago=0` puts the ex-date on the newest bar. The registered
        history is the adjusted one; see `_unadjust` for what a raw request
        gets instead.
        """
        self.splits[ticker] = (float(ratio), int(sessions_ago))

    # -- the shape alpaca-py returns ----------------------------------
    def bars_frame(self, symbols: list[str], end: Any = None,
                   adjustment: Any = None) -> pd.DataFrame:
        frames, keys = [], []
        for sym in symbols:
            df = self.history.get(sym)
            if df is None:
                continue
            lower = df.rename(columns=str.lower).copy()
            lower["trade_count"] = (lower["volume"] / 100.0).round()
            lower["vwap"] = (lower["high"] + lower["low"] + lower["close"]) / 3.0
            if sym in self.splits and not self._splits_applied(adjustment):
                lower = self._unadjust(lower, *self.splits[sym])
            lower = self._align_to_end(lower, end, self.stale_sessions.get(sym, 0))
            if sym in self.gapped and len(lower) >= 2:
                lower = pd.concat([lower.iloc[:-2], lower.iloc[-1:]])
            if lower.empty:
                continue
            frames.append(lower)
            keys.append(sym)
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, keys=keys, names=["symbol", "timestamp"])

    @staticmethod
    def _splits_applied(adjustment: Any) -> bool:
        """Does this adjustment restate history across a split?

        Alpaca's `split` and `all` do; `raw` (the server default when the
        field is omitted) and `dividend` do not.
        """
        value = getattr(adjustment, "value", adjustment)
        return value in ("split", "all")

    @staticmethod
    def _unadjust(df: pd.DataFrame, ratio: float, sessions_ago: int) -> pd.DataFrame:
        """Turn a split-adjusted frame back into the prints of the day.

        Everything before the ex-date traded at `ratio` times the adjusted
        price, in `1/ratio` of the adjusted share count. That discontinuity is
        the whole reason the scanner names an adjustment.
        """
        raw = df.copy()
        split_at = len(raw) - 1 - sessions_ago
        before = raw.index[:split_at]
        for col in ("open", "high", "low", "close", "vwap"):
            raw.loc[before, col] = raw.loc[before, col] * ratio
        for col in ("volume", "trade_count"):
            raw.loc[before, col] = raw.loc[before, col] / ratio
        return raw

    @staticmethod
    def _align_to_end(df: pd.DataFrame, end: Any, stale_sessions: int) -> pd.DataFrame:
        """Re-date a frame so its newest bar is the session `end` asked for.

        Rebuilt as business days rather than slid by a fixed offset: a shift
        of an arbitrary number of calendar days would leave the fixtures'
        bars sitting on Saturdays, and `stale_sessions` would count weekend
        days as sessions. Weekends only, no holidays -- the same simplification
        the scanner makes, so the double is wrong in the same places the code
        under test is, and no test can pass on a disagreement between them.

        `end` of None means the request set no upper bound: the frame comes
        back as registered, which is how stale a real response would look if
        the scanner stopped bounding its window.
        """
        if end is None or df.empty:
            return df
        target = pd.Timestamp(getattr(end, "date", lambda: end)())
        span = pd.bdate_range(end=target.normalize(), periods=len(df) + stale_sessions)
        aligned = df.copy()
        aligned.index = pd.DatetimeIndex(span[:len(df)], name=df.index.name)
        return aligned


class FakeDataClient:
    def __init__(self, parent: FakeAlpaca, *args: Any, **kwargs: Any) -> None:
        self._parent = parent
        self.init_args = (args, kwargs)
        parent.data_clients.append(self)

    def get_stock_bars(self, request: Any) -> FakeBarSet:
        self._parent.bar_requests.append(request)
        fields = request.to_request_fields() if hasattr(request, "to_request_fields") else {}
        self._parent.request_fields.append(fields)
        symbols = getattr(request, "symbol_or_symbols", None)
        if symbols is None:
            symbols = list(self._parent.history)
        elif isinstance(symbols, str):
            symbols = [symbols]
        if self._parent.raise_on_bars is not None and (
            not self._parent.fail_symbols
            or set(symbols) & self._parent.fail_symbols
        ):
            raise self._parent.raise_on_bars
        return FakeBarSet(
            self._parent.bars_frame(
                list(symbols),
                end=getattr(request, "end", None),
                adjustment=getattr(request, "adjustment", None),
            )
        )




@dataclass
class FakeTextBlock:
    text: str
    type: str = "text"


def billed_usage(kwargs: dict, calls: list, uncached: int = 1109) -> "FakeUsage":
    """The token counts a reply to `kwargs` would carry, billed as the API does.

    ONE rule, used by both doubles in this suite: the first call of a run
    writes the cached prefix and every call after reads it, and the prefix is
    only whatever carries a cache_control block. A request that stops asking
    for caching therefore gets a reply reporting none, which is what makes the
    test that totals them able to fail.

    `calls` is the double's own log INCLUDING the call being answered, so the
    first one sees a length of 1.
    """
    prefix = sum(len(str(block.get("text", ""))) // 4
                 for block in kwargs.get("system") or []
                 if isinstance(block, dict) and block.get("cache_control"))
    first = sum(1 for c in calls if c.get("system") == kwargs.get("system")) <= 1
    return FakeUsage(
        cache_creation_input_tokens=prefix if first else 0,
        cache_read_input_tokens=0 if first else prefix,
        input_tokens=uncached,
        output_tokens=90,
    )


@dataclass
class FakeUsage:
    """The token counts a real reply carries, modelled the way the API bills.

    The FIRST call of a run writes the cached prefix and the rest read it,
    which is the whole shape of the saving prompt caching buys -- so a double
    that reported one flat number per call could not tell a working cache from
    a broken one, and the test that totals them would pass either way.
    """

    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class FakeMessage:
    content: list[FakeTextBlock]
    usage: FakeUsage | None = None


class FakeAnthropic:
    """Stands in for `anthropic.Anthropic`.

    Constructed with no API key on purpose -- the real client raises when
    ANTHROPIC_API_KEY is unset, which is exactly what this replaces.
    """

    #: mutated by the fake_anthropic fixture, shared by every instance
    payload: dict = {"score": 7.5, "reason": "synthetic", "verdict": "B+", "key_risk": "synthetic"}
    raw: str | None = None          # verbatim reply text, overrides `payload`
    raises: Exception | None = None
    #: what a request costs beyond the cached prefix -- the metrics text and
    #: the chart image, which are different for every candidate
    uncached_tokens: int = 1109
    calls: list[dict] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.init_args = (args, kwargs)
        self.messages = _FakeMessages(type(self))


class _FakeMessages:
    def __init__(self, owner: type[FakeAnthropic]) -> None:
        self._owner = owner

    def create(self, **kwargs: Any) -> FakeMessage:
        self._owner.calls.append(kwargs)
        if self._owner.raises is not None:
            raise self._owner.raises
        text = self._owner.raw
        if text is None:
            text = json.dumps(self._owner.payload)
        return FakeMessage(content=[FakeTextBlock(text=text)],
                           usage=billed_usage(kwargs, self._owner.calls,
                                              self._owner.uncached_tokens))


# --------------------------------------------------------------- Resend ----


@dataclass
class FakeResend:
    """Captures the payload `resend.Emails.send` was handed."""

    sent: list[dict] = field(default_factory=list)
    response: dict = field(default_factory=lambda: {"id": "fake-email-id"})

    def send(self, params: dict, options: Any = None) -> dict:
        self.sent.append(params)
        return dict(self.response)
