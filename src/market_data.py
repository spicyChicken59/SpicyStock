"""Alpaca daily bars, asked for the way the live runs proved they have to be.

Everything here is transport: the client and its timeouts, the feed, the
request window, split adjustment, batching with one retry, the order and
duplication of what comes back, and which names carry a bar for the session
and for the session before it. No strategy number lives in this module; the
counts it hands back are the inputs to whatever guards the caller applies.

ENV
---
ALPACA_API_KEY, ALPACA_SECRET_KEY  read at call time by get_clients(); an
                                   empty value is missing (Actions passes an
                                   unset secret as '').
SCAN_FEED          optional: 'sip' or 'iex'. An unknown value raises.
"""

from __future__ import annotations

import logging
import math
import os
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from requests.adapters import HTTPAdapter

from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from src.clock import previous_session
from src import sessions

log = logging.getLogger(__name__)

#: Environment this layer cannot run without, collected by the preflight so a
#: run fails before it spends a request rather than as a 401 from Alpaca.
REQUIRED_ENV: tuple[str, ...] = ("ALPACA_API_KEY", "ALPACA_SECRET_KEY")

#: The consolidated tape. `delayed_sip`, the default for nine rounds, is a
#: name alpaca-py lists and the bars endpoint refuses ({"message":"invalid
#: feed: delayed_sip"} on every batch, Actions run 34013173587, 6 Sep 2026).
#: A free plan reads `sip` with the window held back SIP_HOLDBACK_MINUTES.
DEFAULT_FEED = DataFeed.SIP
BAR_ADJUSTMENT = Adjustment.SPLIT

#: Alpaca documents fifteen minutes for a SIP query's `end` on a plan without
#: a real-time subscription; one more is margin between the two clocks.
#: Applied to `sip` alone, since no other feed was observed to need it.
SIP_HOLDBACK_MINUTES = 16

#: Requests has no default timeout. Connect and read-inactivity limits per
#: HTTP request, not a deadline for a whole paginated download.
ALPACA_CONNECT_TIMEOUT_SECONDS = 5
ALPACA_READ_TIMEOUT_SECONDS = 30

#: Sessions of history a scan asks for, and the calendar-day multiple that
#: covers them (weekends and holidays included).
DEFAULT_LOOKBACK_DAYS = 260
LOOKBACK_CALENDAR_RATIO = 1.6

#: Symbols per get_stock_bars() call. Request count is governed by total
#: bars (the SDK pages at 10,000), so a larger batch buys almost nothing.
DEFAULT_BATCH_SIZE = 100

#: The pause before a failed batch is asked for again.
RETRY_WAIT_SECONDS = 3

#: Below this many frames the closure vote does not run and the weekend
#: arithmetic stands: a `--tickers` scan of two names is not a market.
DEFAULT_MIN_SYMBOLS = 10

#: The reviewed fallback list; the universe module owns discovery.
SYMBOLS_FILE = Path(__file__).resolve().parent.parent / "data" / "symbols.txt"

# One ticker per line, A-Z, 1-5 characters. Class shares spelled with
# punctuation (BRK.B) are rejected on purpose.
_SYMBOL_RE = re.compile(r"^[A-Z]{1,5}$")

#: The column names every downstream layer reads, in alpaca-py's order.
OHLCV = ("Open", "High", "Low", "Close", "Volume")
_RENAME = {"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}


# ---------------------------------------------------------------- errors ----


class SymbolFileError(ValueError):
    """The symbol file is unreadable, empty, or has a line that is not a ticker."""


class FeedNotAuthorizedError(RuntimeError):
    """Alpaca refused the requested data feed for these credentials."""


class CredentialsRejectedError(RuntimeError):
    """Alpaca would not authenticate these credentials at all.

    A sibling of FeedNotAuthorizedError with the opposite fix: one means the
    key is wrong, the other that the key is right and the plan lacks the
    feed. Both used to arrive as one message that sent a typo shopping for a
    data plan. The class name reaches the failure email.
    """


# ---------------------------------------------------------------- client ----


class _MarketDataTimeoutAdapter(HTTPAdapter):
    """Bound this client's transport without changing the SDK's retries.

    StockHistoricalDataClient exposes no timeout and its RESTClient calls
    requests.Session.request without one; mounting an adapter keeps the
    SDK's headers, pagination and rate-limit retries while making sure a
    silent connection cannot consume the runner's whole lifetime. An explicit
    timeout from a future SDK is respected.
    """

    def send(self, request, **kwargs):
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = (ALPACA_CONNECT_TIMEOUT_SECONDS, ALPACA_READ_TIMEOUT_SECONDS)
        return super().send(request, **kwargs)


def get_clients() -> StockHistoricalDataClient:
    """The one Alpaca client this pipeline needs: daily bars.

    The keys are read HERE, not at import: an import-time capture made the
    preflight validate a different value from the one used. Empty keys still
    raise ValueError("You must supply a method of authentication") from the
    SDK constructor.
    """
    client = StockHistoricalDataClient(
        os.environ.get("ALPACA_API_KEY", ""),
        os.environ.get("ALPACA_SECRET_KEY", ""),
    )
    # The SDK's private session is the one integration point; the real-SDK
    # transport tests exercise it so a changed SDK cannot silently lose it.
    for protocol in ("https://", "http://"):
        client._session.mount(protocol, _MarketDataTimeoutAdapter())
    return client


def feed_from_env() -> DataFeed:
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


def read_symbol_file(path: str | Path) -> list[str]:
    """The tickers in a symbol file, in file order.

    Blank lines and `#` comments (whole-line or trailing) are ignored. Any
    other line, and any duplicate, raises SymbolFileError: a typo must fail
    the run rather than quietly shrink the list. File order is kept so the
    file can stay grouped by sector for a human reader.
    """
    path = Path(path)
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
    log.info("Symbol file: %d symbols from %s", len(tickers), path)
    return tickers


# -------------------------------------------------------------- download ----


def _download_batch(client, tickers: list[str], session: date, lookback_days: int,
                    feed: DataFeed, now: datetime | None = None,
                    duplicates: dict[str, int] | None = None) -> dict[str, pd.DataFrame]:
    """One get_stock_bars() call for the window ending at `session`.

    One SDK call is several HTTP requests: the SDK pages at 10,000 bars and
    loops on next_page_token. What is named on the request, and why:

    adjustment=SPLIT -- the server default is raw, and raw prints put every
        bar before a split on a different scale from the ones after it (a
        4-for-1 reads as a 75% loss). Dividend adjustment is not asked for:
        it restates closes for payouts.
    feed -- see DEFAULT_FEED; the server default on a free account is IEX.
    start/end -- anchored to the session rather than to `now`, so the window
        is the same whenever the run happens and a bar newer than the session
        is never returned. On `sip`, `end` is held back SIP_HOLDBACK_MINUTES
        behind `now` once the clock has reached the session's day, which is
        the free plan's consolidated route (a dispatch on 6 Sep 2026 showed
        Alpaca serving it). Before the clock reaches that day the window goes
        out as written: the offline suite pins sessions ahead of the wall
        clock, and holding those back would end the window on the day before
        the session.

    `duplicates`, if given, receives per symbol the EXTRA copies of a repeated
    timestamp that were dropped (a bar sent three times counts 2); symbols
    with none are absent. Keyed on the timestamp, which is all the index can
    see: one session sent under two timestamps is neither counted nor dropped.
    """
    day_start = datetime(session.year, session.month, session.day, tzinfo=timezone.utc)
    start = day_start - timedelta(days=int(lookback_days * LOOKBACK_CALENDAR_RATIO))
    end = day_start + timedelta(hours=23, minutes=59, seconds=59)
    if feed is DataFeed.SIP:
        latest = (now or datetime.now(timezone.utc)) - timedelta(minutes=SIP_HOLDBACK_MINUTES)
        if latest >= day_start:
            end = min(end, latest)
    request = StockBarsRequest(
        symbol_or_symbols=tickers,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        adjustment=BAR_ADJUSTMENT,
        feed=feed,
    )
    bars = client.get_stock_bars(request)
    df_all = bars.df
    out: dict[str, pd.DataFrame] = {}
    if df_all is None or df_all.empty:
        return out
    for t in tickers:
        try:
            df = df_all.loc[t]
        except KeyError:
            continue
        # BarSet.df keeps the response's order and the request pins no sort:
        # a newest-first reply once made every symbol read as stale, and a
        # bar sent twice hid a burst behind a 0% gain. Sorted here rather
        # than on the wire. STABLE, because keep="last" means "the copy the
        # feed sent last" only if equal timestamps keep their wire order;
        # pandas' default quicksort kept a preliminary copy over the
        # corrected one at 17 or more wire elements (numpy's introsort is
        # insertion sort, and stable, at 16 and under).
        df = df.sort_index(kind="stable")
        dupes = int(df.index.duplicated().sum())
        if dupes and duplicates is not None:
            duplicates[t] = dupes
        df = df[~df.index.duplicated(keep="last")]
        df = df.dropna(how="all")
        if not df.empty:
            out[t] = df.rename(columns=_RENAME)
    return out


@dataclass
class DownloadStats:
    """What a download's returned frames cannot show: the inputs to every
    coverage guard, and -- once apply_session_rules() has run -- which names
    the session rules set aside and what they read the session before as."""

    session: date
    feed: str
    requested: int = 0
    #: symbols that answered with at least one bar
    with_bars: int = 0
    #: symbols lost because their batch failed twice
    dropped: int = 0
    dropped_symbols: list[str] = field(default_factory=list)
    unfetched: list[str] = field(default_factory=list)
    refused: list[str] = field(default_factory=list)
    unrequested: list[str] = field(default_factory=list)
    batch_attempts: int = 0
    #: symbols the feed answered with nothing, sorted
    no_bars: list[str] = field(default_factory=list)
    #: symbol -> extra copies of a repeated timestamp dropped
    duplicates: dict[str, int] = field(default_factory=dict)
    #: symbol -> its newest bar's date (None when unreadable), for names with
    #: no bar for the session
    stale: dict[str, date | None] = field(default_factory=dict)
    #: symbol -> the bar it has before the session (None when it has none),
    #: for names whose bar before the session is not the session before
    gapped: dict[str, date | None] = field(default_factory=dict)
    unreadable: list[str] = field(default_factory=list)
    previous_session: date | None = None
    previous_session_observed: bool = False
    #: frames that carried a bar on `previous_session`
    previous_session_printed: int = 0
    closure_voters: int | None = None
    closure_agreed: int | None = None
    closure_day: date | None = None
    closure_min_symbols: int | None = None

    @property
    def duplicate_bars(self) -> int:
        """Extra bars dropped as duplicates, across every symbol."""
        return sum(self.duplicates.values())

    @property
    def fresh(self) -> int:
        return self.with_bars - len(self.stale)

    @property
    def ready(self) -> int:
        """Frames that carried the session and the session before it."""
        return self.with_bars - len(self.stale) - len(self.gapped) - len(self.unreadable)


def _names(symbols: list[str], limit: int = 8) -> str:
    return ", ".join(symbols[:limit]) + ("..." if len(symbols) > limit else "")


def download_bars(client, tickers: list[str], session: date,
                  lookback_days: int = DEFAULT_LOOKBACK_DAYS,
                  feed: DataFeed | None = None,
                  batch_size: int = DEFAULT_BATCH_SIZE,
                  now: datetime | None = None) -> tuple[dict[str, pd.DataFrame], DownloadStats]:
    """Every frame the feed returned for `tickers`, keyed by symbol, and the
    counts behind it. No session rule is applied here: the frames come back
    as the feed sent them (sorted, de-duplicated, capitalised), stale ones
    included, so a caller measuring earlier sessions sees every name.

    A batch that fails is retried once after RETRY_WAIT_SECONDS; failing
    twice drops the whole batch and counts it. A permanent refusal -- a
    rejected key, a feed this plan lacks, a feed name the endpoint does not
    take -- raises on the first batch it reaches, because it is a property of
    the run and retrying every batch would end in a complete scan of nothing.
    `feed` defaults to SCAN_FEED, then DEFAULT_FEED.
    """
    feed = feed_from_env() if feed is None else feed
    tickers = list(tickers)
    stats = DownloadStats(session=session, feed=feed.value)
    frames: dict[str, pd.DataFrame] = {}
    no_bars: list[str] = []

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i: i + batch_size]
        stats.requested += len(batch)

        def abort(exc):
            # Preserve successful earlier batches without pretending that later
            # names were requested or that a permanent refusal was retried.
            stats.refused.extend(batch)
            stats.unrequested = tickers[i + len(batch):]
            stats.no_bars = sorted(no_bars)
            error = _refusal_error(feed, exc)
            error.download_stats, error.frames = stats, frames
            raise error from exc

        try:
            stats.batch_attempts += 1
            histories = _download_batch(client, batch, session, lookback_days, feed,
                                        now=now, duplicates=stats.duplicates)
        except Exception as e:  # noqa: BLE001 -- classified below
            if _is_permanent_refusal(e):
                abort(e)
            log.warning("Batch %d failed (%s); retrying once", i, e)
            time.sleep(RETRY_WAIT_SECONDS)
            try:
                stats.batch_attempts += 1
                histories = _download_batch(client, batch, session, lookback_days, feed,
                                            now=now, duplicates=stats.duplicates)
            except Exception as e2:  # noqa: BLE001
                if _is_permanent_refusal(e2):
                    abort(e2)
                # A hand-typed, sector-grouped list loses a contiguous block.
                stats.dropped += len(batch)
                stats.dropped_symbols.extend(batch)
                log.error("Batch %d failed twice (%s) -- dropping %d symbols: %s",
                          i, e2, len(batch), _names(batch))
                continue
        # A name the feed answers with nothing is in no frame and so in no
        # later count; named here so it reaches a log line and the record.
        no_bars.extend(t for t in batch if t not in histories)
        stats.with_bars += len(histories)
        frames.update(histories)
        log.info("Downloaded %d/%d symbols", min(i + batch_size, len(tickers)), len(tickers))

    stats.no_bars = sorted(no_bars)
    if stats.no_bars:
        log.warning("%d of %d symbols returned no bar at all in the window asked for and "
                    "were skipped -- the response does not establish why: %s",
                    len(stats.no_bars), len(tickers), _names(stats.no_bars))
    if stats.duplicates:
        worst = sorted(stats.duplicates.items(), key=lambda kv: (-kv[1], kv[0]))
        # "of the N that answered": the population a duplicate can come from.
        log.warning("%d of the %d symbols that answered carried a timestamp the response had "
                    "already sent (%d extra bar(s) dropped), keeping the copy that arrived "
                    "last: %s",
                    len(stats.duplicates), stats.with_bars, stats.duplicate_bars,
                    _names([f"{t} ({n})" for t, n in worst]))
    return frames, stats


# ------------------------------------------------------- reading a frame ----


def _as_date(stamp) -> date | None:
    """The session a bar's timestamp belongs to, or None for NaT.

    Works for the tz-aware UTC index alpaca-py returns and for a naive one: a
    daily bar's timestamp sits inside its own UTC day either way. NaT is
    refused because pd.Timestamp(NaT).date() is NaT again, and a NaT compared
    with a date is a TypeError in place of the message an operator needs.
    """
    stamp = pd.Timestamp(stamp)
    return None if stamp is pd.NaT else stamp.date()


def last_bar_date(df: pd.DataFrame) -> date | None:
    """The session a frame's newest bar belongs to, or None if unreadable."""
    return _as_date(df.index[-1])


def _measurable(df: pd.DataFrame) -> pd.DataFrame:
    """The bars a detector can read: those with a close and a volume.

    The gap rule reads this frame rather than the index, because a bar that
    is present but carries no readable close or volume is dropped by any
    detector before it reads iloc[-2], and an index-based check once let a
    two-session move through as one day's. Tolerant of a frame without those
    columns, since this sits outside any per-symbol try.
    """
    subset = [c for c in ("Close", "Volume") if c in df.columns]
    return df.dropna(subset=subset) if subset else df


def _printed_on(df: pd.DataFrame, day: date) -> bool:
    """Did this frame carry a bar on `day`? Presence, not readability: a bar
    with a broken field is still the feed saying the name traded."""
    return any(_as_date(stamp) == day for stamp in df.index)


def _bar_before_session(df: pd.DataFrame, session: date) -> date | None:
    """The newest readable session in this frame EARLIER than `session`, or
    None. By date and over the measurable bars, so the gap rule asks the
    question a detector answers; a NaT stamp belongs to no session."""
    best: date | None = None
    for stamp in _measurable(df).index:
        day = _as_date(stamp)
        if day is not None and day < session and (best is None or day > best):
            best = day
    return best


def newest_stale(stale: dict[str, date | None]) -> date | None:
    """The newest date among names that carried no bar for the session; a
    max over the ones that have a date, since None cannot be compared."""
    dates = [d for d in stale.values() if d is not None]
    return max(dates) if dates else None


# ---------------------------------------------------------- session rules ----


def drop_stale(histories: dict[str, pd.DataFrame],
               session: date) -> tuple[dict[str, pd.DataFrame], dict[str, date | None]]:
    """Split frames into those whose newest bar is `session` and those behind
    it, the latter with their newest date (absence does not establish why) --
    None when the stamp is unreadable rather than a NaT every later reader
    compares. Without this a name that stopped printing weeks ago is measured
    across whatever two bars it has left."""
    fresh: dict[str, pd.DataFrame] = {}
    stale: dict[str, date | None] = {}
    for ticker, df in histories.items():
        last = last_bar_date(df)
        if last is not None and last == session:
            fresh[ticker] = df
        else:
            stale[ticker] = last
    return fresh, stale


def observed_previous_session(histories: dict[str, pd.DataFrame], session: date,
                              min_symbols: int = DEFAULT_MIN_SYMBOLS,
                              downloaded: dict[str, pd.DataFrame] | None = None,
                              tally: dict | None = None) -> tuple[date, bool]:
    """Calendar-owned previous session; bar votes remain diagnostics only.

    Agreement that an expected-open day is absent cannot prove a holiday.
    A single-symbol scan gets the same adjacency as a full-universe scan.
    """
    want = previous_session(session)
    votes: dict[date, int] = {}
    for df in histories.values():
        before = _bar_before_session(df, session)
        if before is not None:
            votes[before] = votes.get(before, 0) + 1
    day, count = max(votes.items(), key=lambda item: item[1]) if votes else (None, 0)
    if tally is not None:
        tally.update({"voters": sum(votes.values()), "agreed": count, "day": day})
    return want, False


def drop_gapped(histories: dict[str, pd.DataFrame], session: date,
                previous: date | None = None) -> tuple[dict[str, pd.DataFrame], dict[str, date | None]]:
    """Split fresh frames into those whose readable bar BEFORE the session is
    `previous` (the exchange calendar's answer when none is given) and those with a hole there, the latter with the bar they
    have instead (their newest date when they have none before the session).

    Freshness checks only the newest bar. A halt or a dropped bar the session
    before leaves iloc[-2] two sessions old, and a genuine BarSet once
    printed a 12.0% one-day move as a 12.45% two-day one. A frame with a
    hole cannot say what the session before did, so it is set aside and
    counted rather than measured across the hole.
    """
    ok: dict[str, pd.DataFrame] = {}
    gapped: dict[str, date | None] = {}
    expected_previous = previous_session(session)
    if previous is not None and previous != expected_previous:
        raise ValueError("previous session must agree with the XNYS calendar")
    previous = expected_previous
    for ticker, df in histories.items():
        before = _bar_before_session(df, session)
        if before is None:
            gapped[ticker] = last_bar_date(df)
            continue
        if before == previous:
            ok[ticker] = df
        else:
            gapped[ticker] = before
    return ok, gapped


def apply_session_rules(frames: dict[str, pd.DataFrame], session: date,
                        stats: DownloadStats, *,
                        min_symbols: int = DEFAULT_MIN_SYMBOLS) -> dict[str, pd.DataFrame]:
    """The frames a scan of `session` may measure, with `stats` filled in.

    Freshness and adjacency are checked against XNYS expected dates. Bar
    votes are diagnostics only: even unanimous missing bars cannot prove closure.
    """
    fresh, stale = drop_stale(frames, session)
    stats.stale = stale
    if stale:
        # Normal in small numbers: halts, delistings, a name that did not trade.
        log.warning("%d of %d symbols had no bar for %s and were skipped: %s",
                    len(stale), stats.with_bars, session,
                    _names([f"{t} (last {d if d else 'unreadable'})" for t, d in stale.items()]))
    tally: dict = {}
    before, observed = observed_previous_session(fresh, session, min_symbols,
                                                 downloaded=frames, tally=tally)
    printed = sum(1 for df in frames.values() if _printed_on(df, before))
    fresh, gapped = drop_gapped(fresh, session, before)
    stats.gapped = gapped
    stats.previous_session = before
    stats.previous_session_observed = observed
    stats.previous_session_printed = printed
    stats.closure_voters = tally.get("voters")
    stats.closure_agreed = tally.get("agreed")
    stats.closure_day = tally.get("day")
    stats.closure_min_symbols = min_symbols
    # Both bars must be readable by the actual OHLCV consumers. Presence of a
    # timestamp alone must not turn NaN/non-finite prices into a non-match.
    stats.unreadable = sorted(t for t, df in fresh.items() if not readable_pair(df))
    return {t: df for t, df in fresh.items() if t not in stats.unreadable}


def readable_pair(df: pd.DataFrame) -> bool:
    """Current and required prior bars, without inventing missing values."""
    try:
        if len(df) < 2:
            return False
        for _, row in df.iloc[-2:].iterrows():
            values = {key: float(row[key]) for key in OHLCV}
            if not all(math.isfinite(v) for v in values.values()):
                return False
            if values['Volume'] < 0 or min(values[k] for k in OHLCV if k != 'Volume') <= 0:
                return False
            if not values['Low'] <= min(values['Open'], values['Close']) <= max(values['Open'], values['Close']) <= values['High']:
                return False
        return True
    except (KeyError, TypeError, ValueError):
        return False


def session_calendar(frames: dict, min_fraction: float = 0.5) -> list[date]:
    """Expected exchange sessions across the frames' span, including holes.

    Frames bound the dates available for analysis; they never vote an expected
    session out of the calendar. Missing bars remain missing observations.
    ``min_fraction`` is retained for caller compatibility, not used as a vote.
    """
    days = [d for df in (frames or {}).values() if df is not None
            for stamp in df.index if (d := _as_date(stamp)) is not None]
    return sessions.dates(min(days), max(days)) if days else []


# --------------------------------------------------------------- refusals ----


def _is_permanent_refusal(exc: Exception) -> bool:
    """Alpaca refusing us outright, as against a hiccup.

    A refusal is a property of the run, not the batch: retrying and dropping
    turns a configuration error into an empty result that reads as a quiet
    market. Two signals, since only one is ever present: the HTTP status
    (alpaca-py's APIError carries it only when built from an HTTPError) and
    the body. The one live refusal met so far -- `invalid feed: delayed_sip`
    -- carried no status and matched neither of the first two phrases, which
    is why the third exists. The subscription wording is still unconfirmed
    against a live refusal.
    """
    if getattr(exc, "status_code", None) in (401, 403):
        return True
    text = str(exc).lower()
    return "subscription" in text or "not permitted" in text or "invalid feed" in text


def _refusal_error(feed: DataFeed, exc: Exception) -> RuntimeError:
    """WHICH refusal it was -- the key, the plan, or a feed name the endpoint
    does not take. The first two have opposite fixes and used to share one
    message that sent a typo shopping for a data plan. The status is a
    heuristic, so each of those two leads with what it says and names the
    other cause second; `invalid feed` is asserted, since the endpoint said it
    in words."""
    if "invalid feed" in str(exc).lower():
        return FeedNotAuthorizedError(
            f"Alpaca's historical-bars endpoint does not take the feed name "
            f"{feed.value!r} at all ({exc}) -- alpaca-py's DataFeed lists it, the "
            "endpoint refuses it, whatever the plan. Set SCAN_FEED to 'sip' (the "
            f"consolidated tape; a free plan's request window is held back "
            f"{SIP_HOLDBACK_MINUTES} minutes for it, which the scan does) or to 'iex' "
            "(one venue, no hold-back). Refusing to continue: every batch would be "
            "refused the same way, and a scan that dropped them all would report an "
            "empty market."
        )
    if getattr(exc, "status_code", None) == 401:
        return CredentialsRejectedError(
            f"Alpaca would not authenticate this request ({exc}). Check "
            "ALPACA_API_KEY and ALPACA_SECRET_KEY: a 401 is what a wrong, "
            "revoked or half-set pair looks like, and an unset GitHub secret "
            "arrives as an empty string rather than as absent. If the pair is "
            f"definitely right, a 401 can also mean this account may not query "
            f"the {feed.value!r} feed — try SCAN_FEED=iex. Refusing to "
            "continue: every batch would be refused the same way, and a scan "
            "that dropped them all would report an empty market."
        )
    return FeedNotAuthorizedError(
        f"Alpaca refused the {feed.value!r} data feed for these credentials "
        f"({exc}). Set SCAN_FEED to a feed this account carries — "
        f"{', '.join(f.value for f in DataFeed)} — or subscribe. If the feed "
        "is definitely one this plan carries, check ALPACA_API_KEY and "
        "ALPACA_SECRET_KEY instead. Refusing to continue: every batch would "
        "be refused the same way, and a scan that dropped them all would "
        "report an empty market."
    )
