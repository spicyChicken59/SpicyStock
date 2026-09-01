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

THE DATA REQUEST: _download_batch() names four things Alpaca would otherwise
default for us — the adjustment, the feed, and both ends of the window. See
that function for why each one is a correctness matter rather than a
preference.

FRESHNESS: every scan targets one session (current_session(), or an explicit
ScanConfig.session_date). Bars are requested only up to that session's end,
and a symbol whose newest bar is not that session is dropped rather than
compared as if it were today. A scan in which nothing carries the session
raises StaleDataError instead of returning a quiet, plausible empty list —
that is what a market holiday, a wrong-day cron and a dead feed all look
like.

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
SCAN_FEED          optional. Overrides ScanConfig.feed for a run that has a
                   different Alpaca subscription — 'sip' on a paid plan,
                   'iex' to force the free single-venue feed. An unknown
                   value raises rather than silently falling back.
SCAN_SESSION_DATE  optional, YYYY-MM-DD. Pins the session the scan targets
                   instead of deriving it from the clock. This is the escape
                   hatch for re-running a past session, and for a manual run
                   on a day the market did not trade.
"""

from __future__ import annotations

import os
import re
import time
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time as time_of_day, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from alpaca.data.enums import Adjustment, DataFeed
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


# US equity sessions, for deciding which one a run can honestly scan. Nothing
# here is a market calendar: weekends are arithmetic, but holidays are not, and
# a holiday is meant to surface as a loud StaleDataError rather than as a scan
# that quietly re-reads the previous session as "today".
try:
    MARKET_TZ = ZoneInfo("America/New_York")
except Exception as e:  # pragma: no cover - depends on the host's tz database
    raise RuntimeError(
        "the America/New_York time zone is unavailable, so this module cannot "
        "tell which session a run targets; `pip install tzdata`"
    ) from e

# The regular session closes at 16:00 ET. The margin is for the last prints to
# settle into the daily bar. Before this time, today's daily bar is still being
# written, so the most recent session a scan can treat as finished is yesterday.
#
# UNVERIFIED AGAINST A LIVE ACCOUNT: if Alpaca's daily bars aggregate the
# extended session as well, a bar is not final until 20:00 ET and an evening
# run at 18:16 ET reads one that is still accumulating post-market volume. The
# regular close is used here because moving the cutoff to 20:15 ET would make
# the 18:16 ET cron scan *yesterday*, which is a product change, not a fix.
SESSION_COMPLETE_ET = time_of_day(16, 15)

# A daily end-of-day scan has no use for real-time data, and the free plan's
# IEX feed is one venue's slice of consolidated volume — roughly a few percent
# — which is why the 5,000,000-share floor currently matches almost nothing.
# delayed_sip is consolidated tape on a delay the scan does not care about.
#
# UNVERIFIED AGAINST A LIVE ACCOUNT: the sandbox cannot reach Alpaca, so which
# feeds this account may query has not been checked. If delayed_sip is refused,
# the scan aborts with FeedNotAuthorizedError naming the feed (see run_scan) —
# it does not degrade into an empty shortlist. Override with SCAN_FEED, or
# ScanConfig(feed=...), for a plan that carries full SIP.
DEFAULT_FEED = DataFeed.DELAYED_SIP


class SymbolFileError(ValueError):
    """The symbol file is unreadable, empty, or has a line that is not a ticker."""


class StaleDataError(RuntimeError):
    """No symbol carried a bar for the session this run set out to scan."""


class FeedNotAuthorizedError(RuntimeError):
    """Alpaca refused the requested data feed for these credentials."""


def _feed_from_env() -> DataFeed:
    """SCAN_FEED, or DEFAULT_FEED. A typo raises; it does not fall back."""
    raw = os.environ.get("SCAN_FEED", "").strip()
    if not raw:
        return DEFAULT_FEED
    try:
        return DataFeed(raw.lower())
    except ValueError as e:
        raise ValueError(
            f"SCAN_FEED={raw!r} is not an Alpaca data feed; expected one of: "
            + ", ".join(f.value for f in DataFeed)
        ) from e


def _session_date_from_env() -> date | None:
    """SCAN_SESSION_DATE, or None for "derive it from the clock"."""
    raw = os.environ.get("SCAN_SESSION_DATE", "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as e:
        raise ValueError(
            f"SCAN_SESSION_DATE={raw!r} is not a YYYY-MM-DD date"
        ) from e


def current_session(now: datetime | None = None) -> date:
    """The most recent session whose daily bar is finished.

    Deliberately calendar-free. Weekends are subtracted because they are
    arithmetic; holidays are not, so a run on Thanksgiving targets a session
    the market never held, finds no bar carrying it, and fails loudly. That is
    the intended outcome — the alternative is emailing the previous session's
    bursts under today's date.
    """
    now_et = (now or datetime.now(timezone.utc)).astimezone(MARKET_TZ)
    session = now_et.date()
    if now_et.time() < SESSION_COMPLETE_ET:
        session -= timedelta(days=1)
    while session.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
        session -= timedelta(days=1)
    return session


@dataclass
class ScanConfig:
    min_price: float = 4.0            # price > $4
    min_gain_pct: float = 4.0         # >= 4% up from yesterday
    min_today_volume: int = 5_000_000 # volume > 5,000,000
    lookback_days: int = 260
    batch_size: int = 100
    # Which Alpaca feed to read. See DEFAULT_FEED for the reasoning and for
    # what is still unconfirmed about it.
    feed: DataFeed = field(default_factory=_feed_from_env)
    # The session this scan targets. None means current_session().
    session_date: date | None = field(default_factory=_session_date_from_env)


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


def _download_batch(data_client, tickers, cfg: ScanConfig,
                    session: date) -> dict[str, pd.DataFrame]:
    """One /stocks/bars call, for the window ending at `session`.

    Four fields Alpaca would otherwise default for us, and why each is set:

    adjustment=SPLIT — the server default is `raw`. Unadjusted bars put every
        price and volume before a split on a different scale from the ones
        after it, so a 4-for-1 forward split reads as a 75% one-day loss and a
        reverse split reads as a burst the market never printed. It is not
        only rule 1's gain that reads wrong: every trailing window downstream
        (the 52-week high, 3- and 6-month performance, the 20SMA extension,
        the log-price fit) is computed across the discontinuity, and the chart
        image the scorer tells Claude to trust over the numbers draws it.
        DIVIDEND adjustment is deliberately not requested: it would restate
        historical closes for payouts, moving a burst-day gain that a trader
        could actually have taken.

    feed — see DEFAULT_FEED. The server default is whatever the plan gives,
        which on a free account is IEX.

    start/end — anchored to the session rather than to `now`, so the window is
        the same whenever the run happens, and so a bar newer than the session
        (this morning's partial one, on a scan targeting yesterday) is never
        returned in the first place. The end bound stops the frame going
        forward; _drop_stale_symbols() stops it lagging behind.
    """
    day_start = datetime(session.year, session.month, session.day, tzinfo=timezone.utc)
    start = day_start - timedelta(days=int(cfg.lookback_days * 1.6))
    end = day_start + timedelta(hours=23, minutes=59, seconds=59)
    request = StockBarsRequest(
        symbol_or_symbols=tickers,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        adjustment=Adjustment.SPLIT,
        feed=cfg.feed,
    )
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


def _last_bar_date(df: pd.DataFrame) -> date:
    """The session a frame's newest bar belongs to.

    Works for the tz-aware UTC index alpaca-py returns and for a naive one:
    a daily bar's timestamp sits inside its own session in either case, since
    the US session neither starts before nor ends after the UTC day it falls
    in.
    """
    return pd.Timestamp(df.index[-1]).date()


def _drop_stale_symbols(histories: dict[str, pd.DataFrame],
                        session: date) -> tuple[dict[str, pd.DataFrame], dict[str, date]]:
    """Split a batch into symbols that traded `session` and symbols that did not.

    A halted, delisted or simply untraded name keeps returning its last good
    bar. detect_setup() reads iloc[-1] as "today" and iloc[-2] as "yesterday",
    so without this a name that stopped printing weeks ago is measured across
    whatever two bars it has left and can be published as one of today's
    bursts.
    """
    fresh: dict[str, pd.DataFrame] = {}
    stale: dict[str, date] = {}
    for ticker, df in histories.items():
        last = _last_bar_date(df)
        if last == session:
            fresh[ticker] = df
        else:
            stale[ticker] = last
    return fresh, stale


def _is_feed_denied(exc: Exception) -> bool:
    """Does this look like Alpaca refusing the feed rather than a hiccup?

    The distinction matters because the feed is a property of the run, not of
    the batch: if it is refused once it is refused every time, so retrying and
    dropping turns a configuration error into an empty shortlist that looks
    exactly like a quiet market.

    Two signals, because only one of them is always present: the HTTP status
    (alpaca-py's APIError carries it only when it was built from an HTTPError)
    and the message body, which reads "subscription does not permit querying
    recent SIP data". Heuristic, and unconfirmed against a live refusal.
    """
    if getattr(exc, "status_code", None) in (401, 403):
        return True
    text = str(exc).lower()
    return "subscription" in text or "not permitted" in text


def _feed_denied_error(feed: DataFeed, exc: Exception) -> FeedNotAuthorizedError:
    return FeedNotAuthorizedError(
        f"Alpaca refused the {feed.value!r} data feed for these credentials "
        f"({exc}). Set SCAN_FEED to a feed this account carries — "
        f"{', '.join(f.value for f in DataFeed)} — or subscribe. Refusing to "
        "continue: every batch would be refused the same way, and a scan that "
        "dropped them all would report an empty market."
    )


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
    session = cfg.session_date or current_session()
    log.info("Scanning session %s from the %s feed", session, cfg.feed.value)
    candidates: list[Candidate] = []
    dropped = 0
    with_bars = 0
    stale: dict[str, date] = {}

    for i in range(0, len(tickers), cfg.batch_size):
        batch = tickers[i: i + cfg.batch_size]
        try:
            histories = _download_batch(data_client, batch, cfg, session)
        except Exception as e:
            # A refused feed is not transient and is not this batch's problem:
            # every batch will be refused, and retrying each of them ends in a
            # complete scan that found nothing. Stop on the first one.
            if _is_feed_denied(e):
                raise _feed_denied_error(cfg.feed, e) from e
            log.warning("Batch %d failed (%s); retrying once", i, e)
            time.sleep(3)
            try:
                histories = _download_batch(data_client, batch, cfg, session)
            except Exception as e2:
                if _is_feed_denied(e2):
                    raise _feed_denied_error(cfg.feed, e2) from e2
                # The symbol list is hand-typed and sector-grouped, so one bad
                # ticker can drop a contiguous block of names. Say so.
                dropped += len(batch)
                log.error("Batch %d failed twice (%s) — dropping %d symbols: %s",
                          i, e2, len(batch), ", ".join(batch[:8]) + ("..." if len(batch) > 8 else ""))
                continue

        with_bars += len(histories)
        histories, batch_stale = _drop_stale_symbols(histories, session)
        stale.update(batch_stale)

        for t, df in histories.items():
            try:
                m = detect_setup(df, cfg)
            except Exception:
                continue
            if m:
                candidates.append(Candidate(ticker=t, history=df, **m))

        log.info("Scanned %d/%d — %d candidates so far",
                  min(i + cfg.batch_size, len(tickers)), len(tickers), len(candidates))

    if stale:
        # Normal in small numbers: halts, delistings, a name that did not trade.
        log.warning("%d of %d symbols had no bar for %s and were skipped: %s",
                    len(stale), with_bars, session,
                    ", ".join(f"{t} (last {d})" for t, d in list(stale.items())[:8])
                    + ("..." if len(stale) > 8 else ""))
    if with_bars and len(stale) == with_bars:
        # Every symbol that returned data is behind the session this run set
        # out to scan. That is a market holiday, a cron on the wrong day, a
        # feed that stopped updating, or a session that has not closed yet —
        # never a quiet market. Returning [] here would be indistinguishable
        # from "nothing burst today".
        raise StaleDataError(
            f"no symbol carried a bar for {session}: all {with_bars} symbols with "
            f"data are behind it (newest seen {max(stale.values())}). The market "
            "may not have traded that day, or the session may still be open. Pin "
            "the session with SCAN_SESSION_DATE=YYYY-MM-DD to scan it deliberately."
        )

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
