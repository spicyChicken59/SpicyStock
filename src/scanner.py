"""
Layer 1 — Simplified Alpaca-based market scanner.

Per-symbol conditions, all checked by detect_setup() on one frame:
  1. Price % change >= 4% vs. yesterday's close
  2. Today's volume >= yesterday's volume
  3. Today's volume >= min_rvol x the stock's OWN trailing volume average
  4. Not a biotech stock
  5. Price > $4.00

And one cross-sectional condition, applied by run_scan() over the whole batch:
  6. Dollar volume at or above the min_dollar_volume_pctile percentile of
     every symbol that traded the session.

WHY 3 AND 6 ARE RELATIVE. Both used to be absolute, and an absolute number
only means something against consolidated tape volume. The old rule 3 was a
flat 5,000,000-share floor, which is (a) feed-dependent — IEX prints a few
percent of the tape, so the floor rejected almost everything on the free plan
— and (b) price-blind: it rejected a $180 leader trading 4.9M shares
(~$880M) and admitted a $4.50 stock trading 6M shares (~$27M), which inverts
knowledge/strategy.md's "higher-priced, liquid leaders over cheap laggards"
and its "barely-liquid names where slippage eats the edge" kill criterion.

A ratio is feed-invariant in a way a share count is not: whatever fraction of
the tape the feed reports, the same fraction appears in the numerator and the
denominator and largely cancels. A percentile is invariant the same way — it
ranks names against each other, and a feed that halves everyone's volume does
not change the ranking. `$3M/day` would have to be re-tuned per feed; "top
70% of what we scanned" does not.

UNIVERSE: get_universe() reads a checked-in symbol file (data/symbols.txt),
not Alpaca's ~11,000-name asset list — no asset-list API call is made. Pass
run_scan(universe=[...]) to override the file entirely; that is the path
`python -m src.pipeline ... --tickers NVDA,PLTR` takes.

THE DATA REQUEST: _download_batch() names four things Alpaca would otherwise
default for us — the adjustment, the feed, and both ends of the window. See
that function for why each one is a correctness matter rather than a
preference.

FRESHNESS AND COVERAGE: every scan targets one session (current_session(), or
an explicit ScanConfig.session_date). Bars are requested only up to that
session's end, and a symbol whose newest bar is not that session is dropped
rather than compared as if it were today. A few of those is a normal day.
Past ScanConfig's max_stale_fraction it is not: the scan raises StaleDataError
rather than emailing a shortlist drawn from whichever minority of the market
did update. Two failures of arrival raise IncompleteScanError the same way —
no symbol returning any bar at all, and more than max_dropped_fraction of the
universe lost to failed batches. What all four have in common is that the
alternative is `[]`, and `[]` is also what a quiet market looks like.

Everything short of raising is reported rather than swallowed: run_scan
fills an optional `stats` dict with the counts behind the shortlist, and
src.pipeline decides from those whether the run was clean.

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

import numpy as np
import pandas as pd

from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

log = logging.getLogger(__name__)

#: Environment this layer cannot run without. Declared here, next to the code
#: that reads it, and collected by src.pipeline's preflight so a run fails
#: before it spends an API call rather than after — see missing_env() there.
#: An empty string counts as missing: GitHub Actions passes an unset secret as
#: '' rather than leaving it out, so `os.environ[...]` succeeds on one and the
#: failure surfaces later as a 401 from someone else's server.
REQUIRED_ENV: tuple[str, ...] = ("ALPACA_API_KEY", "ALPACA_SECRET_KEY")

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
# IEX feed is one venue's slice of consolidated volume — roughly a few percent.
# delayed_sip is consolidated tape on a delay the scan does not care about.
# Since step 4 both volume gates are ratios rather than absolute counts, so a
# thin feed no longer empties the shortlist on its own; a fuller feed is still
# the better input, because a few percent of the tape is a noisier estimate of
# a stock's own average than the whole of it.
#
# UNVERIFIED AGAINST A LIVE ACCOUNT: the sandbox cannot reach Alpaca, so which
# feeds this account may query has not been checked. If delayed_sip is refused,
# the scan aborts with FeedNotAuthorizedError naming the feed (see run_scan) —
# it does not degrade into an empty shortlist. Override with SCAN_FEED, or
# ScanConfig(feed=...), for a plan that carries full SIP. A rejected KEY is the
# sibling case and aborts with CredentialsRejectedError; the two have opposite
# fixes and _refusal_error() is where they are told apart.
DEFAULT_FEED = DataFeed.DELAYED_SIP



class SymbolFileError(ValueError):
    """The symbol file is unreadable, empty, or has a line that is not a ticker."""


class StaleDataError(RuntimeError):
    """No symbol carried a bar for the session this run set out to scan."""


class FeedNotAuthorizedError(RuntimeError):
    """Alpaca refused the requested data feed for these credentials."""


class CredentialsRejectedError(RuntimeError):
    """Alpaca would not authenticate these credentials at all.

    A SIBLING of FeedNotAuthorizedError, and the distinction is the whole
    reason it exists: one means the key is wrong, the other means the key is
    right and the plan does not carry the feed. They have opposite fixes, and
    until this class existed both arrived as FeedNotAuthorizedError telling the
    operator to "set SCAN_FEED to a feed this account carries -- or subscribe".
    A typo in ALPACA_API_KEY therefore sent them shopping for a data plan.

    The exception's own NAME reaches the failure email (src.emailer renders the
    type), so this is not cosmetic: it is the first word the operator reads at
    6:16pm about why nothing arrived.
    """


class IncompleteScanError(RuntimeError):
    """Too little of the universe came back for the result to describe a market.

    Sibling of StaleDataError, and the distinction is what went wrong rather
    than how bad it was: StaleDataError means bars arrived but belong to the
    wrong session, this means they did not arrive. Both replace a shortlist
    that would otherwise be indistinguishable from a quiet market.
    """


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


def session_has_closed(now: datetime | None = None) -> bool:
    """Is TODAY's session already over, in market time?

    The one fact that separates this pipeline's two modes, and the reason it
    is a function rather than a comparison written out at each call site:
    src.pipeline asks it to decide whether the mode it was given matches the
    clock it is running on. An evening run is a scan of the session that
    closed today, so it belongs on the True side; a morning run is a
    follow-through before the open, so it belongs on the False side. Nothing
    used to check either, and a `python -m src.pipeline evening` at lunchtime
    scanned YESTERDAY and mailed it as tonight's candidates.

    Equivalent to `current_session(now) == today in ET`, and deliberately the
    same arithmetic: weekends are subtracted, holidays are not. A run on
    Thanksgiving afternoon is told the session closed, targets a session the
    market never held and fails loudly in run_scan() — which is the behaviour
    current_session()'s docstring already argues for, not a second opinion
    about the calendar.
    """
    now_et = (now or datetime.now(timezone.utc)).astimezone(MARKET_TZ)
    return now_et.weekday() < 5 and now_et.time() >= SESSION_COMPLETE_ET


@dataclass
class ScanConfig:
    min_price: float = 4.0            # price > $4
    min_gain_pct: float = 4.0         # >= 4% up from yesterday

    # --- rule 3: volume against the stock's own norm -----------------------
    # `min_rvol` is where a burst stops being ordinary. knowledge/strategy.md
    # wants "volume clearly above average (ideally 2x+)" for an A+ and kills
    # "volume barely above average — no institutional participation". Those
    # are two different numbers and this gate is deliberately the lower one:
    # set at 2.0 the scan would hand Claude a shortlist on which every name
    # already met the A+ volume bar, and the kill criterion could never fire
    # — the same defect, from the other side, as the old vs-yesterday ratio
    # that was structurally floored at 1.0. At 1.5 the 1.5x-2.0x band still
    # reaches the scorer, so "barely above average" remains a verdict Claude
    # can reach on evidence.
    min_rvol: float = 1.5
    # Sessions in the trailing average, EXCLUDING the burst day itself. 50 is
    # not a fresh guess: src.lynch's C check already measures the pre-burst
    # day against `pre["Volume"].iloc[-51:-1].mean()`, and two layers of one
    # pipeline disagreeing about what "average volume" means is how a metric
    # ends up meaning nothing. ~10 weeks is long enough that one earnings
    # spike cannot set the baseline, short enough to follow a name whose
    # liquidity regime has changed.
    rvol_lookback: int = 50
    # Below this many prior sessions there is no average worth dividing by, so
    # the name is dropped rather than measured against three days of history.
    min_rvol_sessions: int = 20

    # --- rule 6: cross-sectional liquidity, applied in run_scan() ----------
    # Keep the top (100 - this)% of the session's scanned names by dollar
    # volume. A percentile, not a dollar figure, because a dollar figure is a
    # statement about the feed as much as about the stock. Sized to cut the
    # illiquid tail rather than to select megacaps: on today's hand-curated
    # large/mid-cap universe it removes very little, and that is correct —
    # there is barely a tail to cut. It starts doing real work when the
    # universe widens past data/symbols.txt, which is when "barely-liquid
    # names where slippage eats the edge" becomes a live risk.
    min_dollar_volume_pctile: float = 30.0

    # NOT A STRATEGY THRESHOLD, and not read by detect_setup() any more: step
    # 4 replaced the absolute 5,000,000-share floor with min_rvol above. The
    # field survives only because tools/make_fixture.py still reads it to lift
    # its hand-authored rows over the old floor, and regenerating that fixture
    # with a different value rewrites docs/data.json. Delete it together with
    # that use — nothing in the scan will notice.

    # --- how much of the universe may go missing before this is not a scan --
    # Both are fractions of what was asked for, and both are deliberately
    # generous: a handful of halted or delisted names is a normal day, and a
    # scan must not die because one symbol was flaky. Half is the point where
    # the answer stops being about the market and starts being about the feed
    # — the cross-sectional percentile (rule 6) is then drawn from a minority
    # of the universe, and "no bursts today" no longer means the market was
    # quiet. Above these the scan raises instead of returning a shortlist that
    # reads exactly like a clean one.
    #
    # NOT the line at which a run is called degraded. That is a lower bar, it
    # is judged over the whole run rather than over the scan alone, and it
    # lives in src.pipeline — this module reports what it saw, the
    # orchestrator decides what the run was worth.
    max_stale_fraction: float = 0.5
    max_dropped_fraction: float = 0.5
    # Below this many symbols the two fractions above are not applied at all.
    # `--tickers NVDA,PLTR` is a scan of two, where one halted name is 50% of
    # the universe and would abort a run that in fact found what it was asked
    # for. A fraction needs a population to be a fraction of. The degenerate
    # case is still covered from the other side: NOTHING carrying the session,
    # and nothing returning a bar at all, raise at any size.
    coverage_guard_min_symbols: int = 10

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
    #: today's volume over `avg_volume` — the stock's own trailing norm, NOT
    #: over prev_volume. It used to be the vs-yesterday ratio while src.scorer
    #: sent it to Claude labelled "volume_ratio_vs_50d_avg", so every metrics
    #: block stated something about the candidate that was not true. Rule 2
    #: rejects any day below the previous one, so that ratio could not print
    #: below 1.00 and "volume barely above average" was unreachable by
    #: construction.
    volume_ratio: float
    #: the denominator, so the ratio can be audited without the frame.
    avg_volume: float
    dollar_volume: float
    history: pd.DataFrame = field(repr=False, default=None)


# ---------------------------------------------------------------------
# Alpaca client + universe
# ---------------------------------------------------------------------

def get_clients() -> StockHistoricalDataClient:
    """The only Alpaca client this pipeline needs: daily bars.

    There is no TradingClient any more. The asset-list call it existed for is
    gone, so nothing in this module is pinned to a paper account.

    The keys are read HERE, not into module globals at import time. Import-time
    capture made the preflight check a lie whenever the two disagreed: it reads
    os.environ, so it would pass on credentials this function had already
    replaced with the empty strings that were there when the module loaded.
    A check that validates a different value from the one used is not a check.
    Empty keys still raise ValueError("You must supply a method of
    authentication") from the SDK constructor.
    """
    return StockHistoricalDataClient(
        os.environ.get("ALPACA_API_KEY", ""),
        os.environ.get("ALPACA_SECRET_KEY", ""),
    )


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

        `end` is the END of the target session, so on an evening run scanning
        today it is HOURS IN THE FUTURE -- measured at 18:30 UTC, the request
        asks for data up to 23:59 UTC. That is deliberate and left alone.
        Alpaca documents that a SIP query's `end` must be at least 15 minutes
        old on a plan without a real-time subscription, and clamping `end` back
        to now-16min was tried: it is unnecessary if the rule applies to the
        `sip` feed rather than the `delayed_sip` one this scan names, and it
        breaks any run whose target session is not yet over. The sandbox cannot
        reach Alpaca, so which of those is true is UNVERIFIED -- and a
        behavioural change to the data request on an unverified lead is exactly
        what this project's notes warn against. If the first live run dies with
        FeedNotAuthorizedError naming delayed_sip, this window is the first
        suspect and SCAN_FEED=iex is the immediate workaround; evening.yml
        forwards it now for that reason.
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


def _is_permanent_refusal(exc: Exception) -> bool:
    """Does this look like Alpaca refusing us outright rather than a hiccup?

    The distinction matters because a refusal is a property of the RUN, not of
    the batch: if we are refused once we are refused every time, so retrying
    and dropping turns a configuration error into an empty shortlist that looks
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


def _refusal_error(feed: DataFeed, exc: Exception) -> RuntimeError:
    """WHICH refusal it was — the key, or the plan. They have opposite fixes.

    This used to be one function returning one error, and 401 and 403 both
    became "Alpaca refused the {feed} data feed ... set SCAN_FEED, or
    subscribe". 401 does not mean that. It means Alpaca did not authenticate
    the request at all, which on a first-time setup is overwhelmingly a wrong
    or half-set key -- and the message sent that operator to buy a data plan.

    The status is still a heuristic and this file has never seen a live
    refusal, so NEITHER message asserts one cause and denies the other: each
    leads with what the status says and names the alternative second. Being
    approximately right in the right order beats being confidently wrong.
    """
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


# ---------------------------------------------------------------------
# Core setup detector
# ---------------------------------------------------------------------

def trailing_volume_mean(df: pd.DataFrame, cfg: ScanConfig) -> float | None:
    """Mean volume over the sessions BEFORE the last bar, or None.

    Exclusive of the bar being measured, matching src.lynch's C check, which
    divides the pre-burst day by `pre["Volume"].iloc[-51:-1].mean()`. The
    exclusion is not a detail: a burst day inside its own denominator drags
    the average up by roughly its own excess, so a genuine 10x day reports
    about 8.5x on a 50-session window and about 5x on a 20-session one. The
    ratio would then mean something different at every window length, which
    is the opposite of what a normalised measure is for.

    None when there is not enough history to have an average at all. A name
    that listed three weeks ago has volume but no norm, and inventing one
    from four sessions would let the thinnest possible baseline manufacture
    the largest possible ratio.
    """
    # dropna AFTER the slice, never before: the window stays the last
    # rvol_lookback sessions, and the count is of sessions that actually
    # reported a volume. Counting rows instead would let a window that is
    # mostly holes satisfy a guard about how much history there is — the same
    # shape of mistake as measuring a burst against a two-day baseline.
    prior = df["Volume"].iloc[-(cfg.rvol_lookback + 1):-1].dropna()
    if len(prior) < cfg.min_rvol_sessions:
        return None
    mean = float(prior.mean())
    if not (mean > 0):  # all-zero, or NaN
        return None
    return mean


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

    # 3. today's volume >= min_rvol x its own trailing average. This replaced
    #    an absolute 5,000,000-share floor, which measured the feed rather
    #    than the stock — see the module docstring.
    avg_vol = trailing_volume_mean(df, cfg)
    if avg_vol is None:
        return None
    rvol = vol / avg_vol
    if rvol < cfg.min_rvol:
        return None

    # 5. price > $4.00 (rule 4, no biotech, is curation — see module docstring)
    if close <= cfg.min_price:
        return None

    # A bar that moved no money is not a candidate, and must not reach the
    # gate as a None in a numeric field. Unreachable while min_rvol > 0, which
    # is why it is written down rather than assumed.
    dollar_volume = session_dollar_volume(df)
    if dollar_volume is None:
        return None

    # Rule 6, the dollar-volume percentile, is NOT here: it is a fact about
    # this name relative to every other name that traded today, and this
    # function is handed one frame. run_scan() applies it.
    return {
        "date": str(pd.Timestamp(df.index[-1]).date()),
        "close": round(close, 2),
        "gain_pct": round(gain_pct, 2),
        "volume": int(vol),
        "prev_volume": int(prev_vol),
        "volume_ratio": round(rvol, 2),
        "avg_volume": round(avg_vol),
        # One definition, shared with the gate that ranks it — see
        # session_dollar_volume() for what two roundings cost.
        "dollar_volume": dollar_volume,
    }


# ---------------------------------------------------------------------
# Rule 6 — cross-sectional liquidity
# ---------------------------------------------------------------------

def session_dollar_volume(df: pd.DataFrame) -> float | None:
    """Last bar's close x volume, or None if the bar cannot supply one.

    THE candidate's `dollar_volume`, not a second opinion about it:
    detect_setup() reports this exact call. That matters because this value
    builds the session's percentile floor and Candidate.dollar_volume is
    compared against it, so two roundings of "the same" product put a name a
    fraction of a cent under its own percentile. Computed unrounded here
    against a rounded candidate, that emptied 53 of 400 synthetic single-symbol
    scans; the obvious repair — rounding here too, but from the rounded close —
    disagreed by about $24 instead of about $1. One function, called by both.
    """
    tail = df.dropna(subset=["Close", "Volume"])
    if tail.empty:
        return None
    value = round(float(tail["Close"].iloc[-1]) * float(tail["Volume"].iloc[-1]))
    return float(value) if value > 0 else None


def liquidity_floor(dollar_volumes: list[float], cfg: ScanConfig) -> float | None:
    """The dollar-volume cutoff for this session, or None for "no gate".

    The distribution is EVERY symbol that traded the session, not the bursting
    ones. The bursts are a handful of names selected for having just done
    something unusual to their volume; ranking them against each other asks
    "was this the thinnest of today's three bursts", which on a quiet day
    throws away a perfectly liquid name and on a wild one keeps a thin one.
    Ranking them against the universe asks the question strategy.md actually
    poses — is this a liquid leader or a name whose spread will eat the edge —
    and gives an answer that does not move with how many bursts printed.
    """
    if cfg.min_dollar_volume_pctile <= 0 or not dollar_volumes:
        return None
    return float(np.percentile(dollar_volumes, cfg.min_dollar_volume_pctile))


def apply_liquidity_gate(candidates: list["Candidate"],
                         dollar_volumes: list[float],
                         cfg: ScanConfig) -> list["Candidate"]:
    """Drop candidates below the session's dollar-volume percentile.

    Inclusive at the floor, which is what makes a one-symbol scan
    (`--tickers NVDA`) still a scan: any percentile of a single value is that
    value, and a strict comparison would reject the only name it was given.
    """
    floor = liquidity_floor(dollar_volumes, cfg)
    if floor is None:
        return candidates
    kept = [c for c in candidates if c.dollar_volume >= floor]
    dropped = [c for c in candidates if c.dollar_volume < floor]
    if dropped:
        log.info(
            "Liquidity gate: dropped %d of %d bursts below the %gth percentile "
            "of the %d names that traded (floor $%s/day): %s",
            len(dropped), len(candidates), cfg.min_dollar_volume_pctile,
            len(dollar_volumes), f"{floor:,.0f}",
            ", ".join(f"{c.ticker} (${c.dollar_volume:,.0f})" for c in dropped[:8])
            + ("..." if len(dropped) > 8 else ""),
        )
    return kept


# ---------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------

def run_scan(cfg: ScanConfig | None = None, universe: list[str] | None = None,
             symbols_file: str | Path | None = None,
             stats: dict | None = None) -> list[Candidate]:
    """Scan `universe` if given, else every symbol in the checked-in file.

    An explicit `universe` wins outright — the file is not read at all — which
    is how --tickers stays a self-contained smoke test.

    `stats`, if given, is filled with what the returned list cannot show: how
    many symbols were asked for, how many came back with bars, which ones were
    behind the session, how many were dropped after a failed batch, and which
    session was scanned. The same idiom as score_all(stats=...), and for the
    same reason — a caller cannot tell a clean empty shortlist from a scan
    that lost half the market by looking at `[]`. It is filled BEFORE the
    guards below raise, so an operator (and the failure email) can still see
    the shape of the scan that failed.
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
    session_dollar_volumes: list[float] = []

    for i in range(0, len(tickers), cfg.batch_size):
        batch = tickers[i: i + cfg.batch_size]
        try:
            histories = _download_batch(data_client, batch, cfg, session)
        except Exception as e:
            # A refused feed is not transient and is not this batch's problem:
            # every batch will be refused, and retrying each of them ends in a
            # complete scan that found nothing. Stop on the first one.
            if _is_permanent_refusal(e):
                raise _refusal_error(cfg.feed, e) from e
            log.warning("Batch %d failed (%s); retrying once", i, e)
            time.sleep(3)
            try:
                histories = _download_batch(data_client, batch, cfg, session)
            except Exception as e2:
                if _is_permanent_refusal(e2):
                    raise _refusal_error(cfg.feed, e2) from e2
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
            # Every symbol that traded, burst or not, is part of the
            # distribution rule 6 ranks against — see liquidity_floor().
            dv = session_dollar_volume(df)
            if dv is not None:
                session_dollar_volumes.append(dv)
            try:
                m = detect_setup(df, cfg)
            except Exception:
                continue
            if m:
                candidates.append(Candidate(ticker=t, history=df, **m))

        log.info("Scanned %d/%d — %d candidates so far",
                  min(i + cfg.batch_size, len(tickers)), len(tickers), len(candidates))

    # Everything the caller cannot read off the returned list. Set before the
    # guards so a raise still leaves the numbers behind it visible.
    if stats is not None:
        stats.update({
            "session": session,
            "feed": cfg.feed.value,
            "requested": len(tickers),
            "with_bars": with_bars,
            "fresh": with_bars - len(stale),
            "stale": dict(stale),
            "no_bars": len(tickers) - with_bars - dropped,
            "dropped": dropped,
            "candidates": len(candidates),
        })

    if stale:
        # Normal in small numbers: halts, delistings, a name that did not trade.
        log.warning("%d of %d symbols had no bar for %s and were skipped: %s",
                    len(stale), with_bars, session,
                    ", ".join(f"{t} (last {d})" for t, d in list(stale.items())[:8])
                    + ("..." if len(stale) > 8 else ""))

    # Three ways a scan can come back too empty to mean anything, in the order
    # a diagnosis would take them: nothing arrived, most of it arrived stale,
    # or the requests themselves failed. Each one otherwise returns [] and is
    # read as "no bursts today".
    if tickers and not with_bars and dropped < len(tickers):
        raise IncompleteScanError(
            f"not one of {len(tickers)} symbols returned a bar for {session}. "
            "The credentials, the feed or the symbol list is wrong — an empty "
            "shortlist here is not a quiet market."
        )
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
    if (with_bars >= cfg.coverage_guard_min_symbols
            and len(stale) / with_bars >= cfg.max_stale_fraction):
        # Step 3 raised only when EVERY symbol was behind the session, so a
        # feed updating 40% of the tape warned once and scanned on. What comes
        # out of that is a real shortlist of the names that did update, ranked
        # by rule 6 against a percentile drawn from the same minority — a
        # plausible email about a market nobody looked at.
        raise StaleDataError(
            f"{len(stale)} of {with_bars} symbols with data ({len(stale) / with_bars:.0%}) "
            f"carry no bar for {session}, at or above the {cfg.max_stale_fraction:.0%} "
            f"this scan will tolerate (newest seen {max(stale.values())}). The "
            "shortlist would describe the minority that did update. Pin the "
            "session with SCAN_SESSION_DATE=YYYY-MM-DD to scan a past one."
        )
    if (len(tickers) >= cfg.coverage_guard_min_symbols
            and dropped / len(tickers) >= cfg.max_dropped_fraction):
        raise IncompleteScanError(
            f"{dropped} of {len(tickers)} symbols ({dropped / len(tickers):.0%}) were "
            f"dropped after their batch failed twice, at or above the "
            f"{cfg.max_dropped_fraction:.0%} this scan will tolerate. Most of the "
            "universe was never examined, so neither the shortlist nor the "
            "dollar-volume percentile it was ranked against describes the market."
        )

    # Rule 6, last, because it is the only rule that needs the whole scan.
    # Dropped symbols are missing from the distribution as well as from the
    # shortlist, which biases the floor by however many they were; the error
    # below already says the shortlist is incomplete on that path.
    candidates = apply_liquidity_gate(candidates, session_dollar_volumes, cfg)

    candidates.sort(key=lambda c: c.gain_pct, reverse=True)
    if dropped:
        log.error("Scan complete with %d of %d symbols DROPPED — the shortlist is "
                  "incomplete and an empty result does not mean a quiet market",
                  dropped, len(tickers))
    if stats is not None:
        stats["candidates"] = len(candidates)
    log.info("Scan complete: %d candidates from %d symbols", len(candidates), len(tickers))
    return candidates


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = run_scan()
    for c in results[:20]:
        print(f"{c.ticker}: +{c.gain_pct}% | vol {c.volume:,} = {c.volume_ratio}x its "
              f"{ScanConfig().rvol_lookback}-session average ({c.avg_volume:,.0f}) "
              f"| ${c.dollar_volume:,.0f}/day | close ${c.close}")
