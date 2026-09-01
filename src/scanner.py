"""
Layer 1 — Simplified Alpaca-based market scanner.

Conditions (all must pass):
  1. Price % change >= 4% vs. yesterday's close
  2. Today's volume >= yesterday's volume
  3. Today's volume > 5,000,000 shares
  4. Not a biotech stock
  5. Price > $4.00

NOTE ON BIOTECH EXCLUSION: Alpaca's asset data does not include sector.
This script still exposes `fundamentals_filter()` as a second pass — you
run it against a `fundamentals` dict you build yourself (e.g. from
yfinance's `.info['sector']`) to drop biotech names. If you skip that
step, biotech names will NOT be filtered out, since Alpaca alone can't
tell you a ticker's sector.

INSTALL
-------
pip install alpaca-py numpy pandas

ENV VARS
--------
ALPACA_API_KEY, ALPACA_SECRET_KEY  (PAPER keys — get_clients() pins only the
                                    TradingClient to paper=True, and
                                    get_universe() is its sole consumer, so
                                    live keys fail the full-universe scan. The
                                    data client has no paper flag, so --tickers
                                    — which skips get_universe() — works on
                                    live keys.)
"""

from __future__ import annotations

import os
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import pandas as pd

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetClass, AssetStatus

log = logging.getLogger(__name__)

API_KEY = os.environ.get("ALPACA_API_KEY", "")
SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY", "")


@dataclass
class ScanConfig:
    min_price: float = 4.0            # price > $4
    min_gain_pct: float = 4.0         # >= 4% up from yesterday
    min_today_volume: int = 5_000_000 # volume > 5,000,000
    lookback_days: int = 260
    batch_size: int = 100


@dataclass
class Candidate:
    ticker: str
    date: str
    close: float
    gain_pct: float
    volume: int
    prev_volume: int
    volume_ratio: float
    dollar_volume: float
    history: pd.DataFrame = field(repr=False, default=None)


# ---------------------------------------------------------------------
# Alpaca clients + universe
# ---------------------------------------------------------------------

def get_clients():
    data_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)
    trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)
    return data_client, trading_client


def get_universe(trading_client: TradingClient) -> list[str]:
    """Tradable US common-stock universe from Alpaca's asset list."""
    req = GetAssetsRequest(status=AssetStatus.ACTIVE, asset_class=AssetClass.US_EQUITY)
    assets = trading_client.get_all_assets(req)
    excluded_exchanges = {"OTC"}
    tickers = [
        a.symbol for a in assets
        if a.tradable
        and str(a.exchange) not in excluded_exchanges
        and "." not in a.symbol and "/" not in a.symbol  # drop units/warrants/classes
    ]
    log.info("Universe size: %d symbols", len(tickers))
    return sorted(tickers)


def _download_batch(data_client, tickers, cfg: ScanConfig) -> dict[str, pd.DataFrame]:
    start = datetime.utcnow() - timedelta(days=int(cfg.lookback_days * 1.6))
    request = StockBarsRequest(symbol_or_symbols=tickers, timeframe=TimeFrame.Day, start=start)
    bars = data_client.get_stock_bars(request)
    df_all = bars.df
    out: dict[str, pd.DataFrame] = {}
    if df_all is None or df_all.empty:
        return out
    for t in tickers:
        try:
            df = df_all.loc[t]
        except KeyError:
            continue
        df = df.dropna(how="all")
        if not df.empty:
            df = df.rename(columns={
                "open": "Open", "high": "High", "low": "Low",
                "close": "Close", "volume": "Volume",
            })
            out[t] = df
    return out


# ---------------------------------------------------------------------
# Core setup detector
# ---------------------------------------------------------------------

def detect_setup(df: pd.DataFrame, cfg: ScanConfig) -> dict | None:
    df = df.dropna(subset=["Close", "Volume"])
    if len(df) < 2:
        return None

    today, yday = df.iloc[-1], df.iloc[-2]
    close, prev_close = float(today["Close"]), float(yday["Close"])
    if prev_close <= 0:
        return None

    gain_pct = (close / prev_close - 1) * 100
    vol, prev_vol = float(today["Volume"]), float(yday["Volume"])

    # 1. price % change >= 4% up from yesterday
    if gain_pct < cfg.min_gain_pct:
        return None

    # 2. today's volume >= yesterday's volume
    if vol < prev_vol:
        return None

    # 3. today's volume > 5,000,000
    if vol <= cfg.min_today_volume:
        return None

    # 5. price > $4.00 (biotech exclusion, rule 4, is handled in fundamentals_filter)
    if close <= cfg.min_price:
        return None

    return {
        "date": str(pd.Timestamp(df.index[-1]).date()),
        "close": round(close, 2),
        "gain_pct": round(gain_pct, 2),
        "volume": int(vol),
        "prev_volume": int(prev_vol),
        "volume_ratio": round(vol / prev_vol, 2) if prev_vol else 0.0,
        "dollar_volume": round(close * vol),
    }


# ---------------------------------------------------------------------
# Biotech exclusion — external sector pass (Alpaca has no sector data)
# ---------------------------------------------------------------------

def fundamentals_filter(candidates: list[Candidate], fundamentals: dict) -> list[Candidate]:
    """
    fundamentals[ticker] = {"sector": str}

    Populate this dict yourself, e.g.:
        import yfinance as yf
        fundamentals = {t: {"sector": yf.Ticker(t).info.get("sector", "")}
                         for t in [c.ticker for c in candidates]}

    Drops any candidate whose sector contains "biotech" (case-insensitive).
    If a ticker has no entry in `fundamentals`, it is kept by default —
    change the `continue` below to `pass` if you'd rather exclude unknowns.
    """
    out = []
    for c in candidates:
        f = fundamentals.get(c.ticker)
        if f and "biotech" in str(f.get("sector", "")).lower():
            continue
        out.append(c)
    return out


# ---------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------

def run_scan(cfg: ScanConfig | None = None, universe: list[str] | None = None) -> list[Candidate]:
    cfg = cfg or ScanConfig()
    data_client, trading_client = get_clients()
    tickers = universe if universe is not None else get_universe(trading_client)
    candidates: list[Candidate] = []

    for i in range(0, len(tickers), cfg.batch_size):
        batch = tickers[i: i + cfg.batch_size]
        try:
            histories = _download_batch(data_client, batch, cfg)
        except Exception as e:
            log.warning("Batch %d failed (%s); retrying once", i, e)
            time.sleep(3)
            try:
                histories = _download_batch(data_client, batch, cfg)
            except Exception:
                continue

        for t, df in histories.items():
            try:
                m = detect_setup(df, cfg)
            except Exception:
                continue
            if m:
                candidates.append(Candidate(ticker=t, history=df, **m))

        log.info("Scanned %d/%d — %d candidates so far",
                  min(i + cfg.batch_size, len(tickers)), len(tickers), len(candidates))

    candidates.sort(key=lambda c: c.gain_pct, reverse=True)
    log.info("Scan complete: %d candidates (biotech NOT yet excluded — "
              "run fundamentals_filter() to apply that)", len(candidates))
    return candidates


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = run_scan()
    for c in results[:20]:
        print(f"{c.ticker}: +{c.gain_pct}% | vol {c.volume:,} (prev {c.prev_volume:,}, {c.volume_ratio}x) | close ${c.close}")
