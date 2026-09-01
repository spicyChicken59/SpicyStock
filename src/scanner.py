"""
Layer 1 — Simplified Alpaca-based market scanner.

Conditions (all must pass):
  1. Price % change >= 4% vs. yesterday's close
  2. Today's volume >= yesterday's volume
  3. Today's volume > 5,000,000 shares
  4. Not a biotech stock
  5. Price > $4.00

UNIVERSE: get_universe() reads a checked-in symbol file (data/symbols.txt),
not Alpaca's ~11,000-name asset list — no asset-list API call is made. Pass
run_scan(universe=[...]) to override the file entirely; that is the path
`python -m src.pipeline ... --tickers NVDA,PLTR` takes.

RULE 4 IS ENFORCED BY CURATION, NOT BY CODE. Alpaca's asset data has no
sector field, and nothing in this module tests one. Biotech is kept out by
leaving those names out of the symbol file. To change what is eligible,
edit that file — not detect_setup().

INSTALL
-------
pip install alpaca-py numpy pandas

ENV VARS
--------
ALPACA_API_KEY, ALPACA_SECRET_KEY  (this module builds only a
                                    StockHistoricalDataClient, which has no
                                    paper/live flag, so nothing here requires
                                    PAPER keys any more. Empty keys still
                                    raise ValueError("You must supply a method
                                    of authentication") from get_clients().)
"""

from __future__ import annotations

import os
import re
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

log = logging.getLogger(__name__)

API_KEY = os.environ.get("ALPACA_API_KEY", "")
SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY", "")

# The scan universe, checked in rather than fetched. That file's header says
# what is in it, what is deliberately left out, and why it should eventually
# be generated instead of hand-written.
SYMBOLS_FILE = Path(__file__).resolve().parent.parent / "data" / "symbols.txt"

# One ticker per line, A-Z, 1-5 characters. Class shares spelled with
# punctuation (BRK.B) are rejected on purpose — see the symbol file header.
_SYMBOL_RE = re.compile(r"^[A-Z]{1,5}$")


class SymbolFileError(ValueError):
    """The symbol file is unreadable, empty, or has a line that is not a ticker."""


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
# Alpaca client + universe
# ---------------------------------------------------------------------

def get_clients() -> StockHistoricalDataClient:
    """The only Alpaca client this pipeline needs: daily bars.

    There is no TradingClient any more. The asset-list call it existed for is
    gone, so nothing in this module is pinned to a paper account.
    """
    return StockHistoricalDataClient(API_KEY, SECRET_KEY)


def get_universe(symbols_file: str | Path | None = None) -> list[str]:
    """Read the scan universe from the checked-in symbol file.

    Blank lines and `#` comments — whole-line or trailing — are ignored. Any
    other line raises SymbolFileError: a typo must fail the run, not quietly
    shrink the universe. File order is preserved so the file can stay grouped
    by sector for human reading.
    """
    path = Path(symbols_file) if symbols_file is not None else SYMBOLS_FILE
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise SymbolFileError(f"cannot read symbol file {path}: {e}") from e

    tickers: list[str] = []
    first_seen: dict[str, int] = {}
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if not _SYMBOL_RE.match(line):
            raise SymbolFileError(
                f"{path} line {lineno}: {line!r} is not a ticker "
                "(expected one A-Z symbol of 1-5 characters per line)"
            )
        if line in first_seen:
            raise SymbolFileError(
                f"{path} line {lineno}: {line} is already listed on line {first_seen[line]}"
            )
        first_seen[line] = lineno
        tickers.append(line)

    if not tickers:
        raise SymbolFileError(f"{path}: no symbols found")

    log.info("Universe: %d symbols from %s", len(tickers), path)
    return tickers


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

    # 5. price > $4.00 (rule 4, no biotech, is curation — see module docstring)
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
# Orchestration
# ---------------------------------------------------------------------

def run_scan(cfg: ScanConfig | None = None, universe: list[str] | None = None,
             symbols_file: str | Path | None = None) -> list[Candidate]:
    """Scan `universe` if given, else every symbol in the checked-in file.

    An explicit `universe` wins outright — the file is not read at all — which
    is how --tickers stays a self-contained smoke test.
    """
    cfg = cfg or ScanConfig()
    data_client = get_clients()
    tickers = universe if universe is not None else get_universe(symbols_file)
    candidates: list[Candidate] = []
    dropped = 0

    for i in range(0, len(tickers), cfg.batch_size):
        batch = tickers[i: i + cfg.batch_size]
        try:
            histories = _download_batch(data_client, batch, cfg)
        except Exception as e:
            log.warning("Batch %d failed (%s); retrying once", i, e)
            time.sleep(3)
            try:
                histories = _download_batch(data_client, batch, cfg)
            except Exception as e2:
                # The symbol list is hand-typed and sector-grouped, so one bad
                # ticker can drop a contiguous block of names. Say so.
                dropped += len(batch)
                log.error("Batch %d failed twice (%s) — dropping %d symbols: %s",
                          i, e2, len(batch), ", ".join(batch[:8]) + ("..." if len(batch) > 8 else ""))
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
    if dropped:
        log.error("Scan complete with %d of %d symbols DROPPED — the shortlist is "
                  "incomplete and an empty result does not mean a quiet market",
                  dropped, len(tickers))
    log.info("Scan complete: %d candidates from %d symbols", len(candidates), len(tickers))
    return candidates


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = run_scan()
    for c in results[:20]:
        print(f"{c.ticker}: +{c.gain_pct}% | vol {c.volume:,} (prev {c.prev_volume:,}, {c.volume_ratio}x) | close ${c.close}")
