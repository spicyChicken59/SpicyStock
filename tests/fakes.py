"""Test doubles for the three external boundaries the pipeline touches.

  Alpaca    -- StockHistoricalDataClient / TradingClient (market data, universe)
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


@dataclass
class FakeAsset:
    """Shape of the alpaca-py asset objects get_universe() reads."""

    symbol: str
    tradable: bool = True
    exchange: str = "NASDAQ"


class FakeBarSet:
    """Stands in for alpaca's BarSet; the scanner only reads `.df`."""

    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df


class FakeAlpaca:
    """Registry + factories for the two Alpaca clients.

    `history` maps ticker -> OHLCV frame (capitalised columns, as the rest of
    the codebase uses them). `get_stock_bars` re-shapes them into the
    (symbol, timestamp) MultiIndex frame with lower-case columns that
    alpaca-py actually returns, so the scanner's own renaming is exercised.
    """

    def __init__(self) -> None:
        self.history: dict[str, pd.DataFrame] = {}
        self.assets: list[FakeAsset] = []
        self.bar_requests: list[Any] = []
        self.asset_requests: list[Any] = []
        self.data_clients: list["FakeDataClient"] = []
        self.trading_clients: list["FakeTradingClient"] = []

    # -- registration -------------------------------------------------
    def add_history(self, ticker: str, df: pd.DataFrame) -> None:
        self.history[ticker] = df
        if ticker not in {a.symbol for a in self.assets}:
            self.assets.append(FakeAsset(symbol=ticker))

    def add_assets(self, *assets: FakeAsset) -> None:
        self.assets.extend(assets)

    # -- the shape alpaca-py returns ----------------------------------
    def bars_frame(self, symbols: list[str]) -> pd.DataFrame:
        frames, keys = [], []
        for sym in symbols:
            df = self.history.get(sym)
            if df is None:
                continue
            lower = df.rename(columns=str.lower).copy()
            lower["trade_count"] = (lower["volume"] / 100.0).round()
            lower["vwap"] = (lower["high"] + lower["low"] + lower["close"]) / 3.0
            frames.append(lower)
            keys.append(sym)
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, keys=keys, names=["symbol", "timestamp"])


class FakeDataClient:
    def __init__(self, parent: FakeAlpaca, *args: Any, **kwargs: Any) -> None:
        self._parent = parent
        self.init_args = (args, kwargs)
        parent.data_clients.append(self)

    def get_stock_bars(self, request: Any) -> FakeBarSet:
        self._parent.bar_requests.append(request)
        symbols = getattr(request, "symbol_or_symbols", None)
        if symbols is None:
            symbols = list(self._parent.history)
        elif isinstance(symbols, str):
            symbols = [symbols]
        return FakeBarSet(self._parent.bars_frame(list(symbols)))


class FakeTradingClient:
    def __init__(self, parent: FakeAlpaca, *args: Any, **kwargs: Any) -> None:
        self._parent = parent
        self.init_args = (args, kwargs)
        parent.trading_clients.append(self)

    def get_all_assets(self, request: Any = None) -> list[FakeAsset]:
        self._parent.asset_requests.append(request)
        return list(self._parent.assets)


# ------------------------------------------------------------ Anthropic ----


@dataclass
class FakeTextBlock:
    text: str
    type: str = "text"


@dataclass
class FakeMessage:
    content: list[FakeTextBlock]


class FakeAnthropic:
    """Stands in for `anthropic.Anthropic`.

    Constructed with no API key on purpose -- the real client raises when
    ANTHROPIC_API_KEY is unset, which is exactly what this replaces.
    """

    #: mutated by the fake_anthropic fixture, shared by every instance
    payload: dict = {"score": 7.5, "reason": "synthetic", "verdict": "B+", "key_risk": "synthetic"}
    raw: str | None = None          # verbatim reply text, overrides `payload`
    raises: Exception | None = None
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
        return FakeMessage(content=[FakeTextBlock(text=text)])


# --------------------------------------------------------------- Resend ----


@dataclass
class FakeResend:
    """Captures the payload `resend.Emails.send` was handed."""

    sent: list[dict] = field(default_factory=list)
    response: dict = field(default_factory=lambda: {"id": "fake-email-id"})

    def send(self, params: dict, options: Any = None) -> dict:
        self.sent.append(params)
        return dict(self.response)
