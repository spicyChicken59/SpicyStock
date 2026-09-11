"""Bonde's universe: every US common stock the directory lists, at a price and
a volume floor, and nothing narrower.

TC2000's "Common Stock" list is what Bonde scans -- about 6,500 names, with no
float, market-cap or sector exclusion and a stated preference for the low-float,
low-priced end. This module builds the closest thing the Nasdaq stock directory
can supply: classified common stock (the name says it is a common share and not
a depositary receipt, a preferred, a warrant, a note, a fund or a trust; it is
not a blank-check shell), at `MIN_PRICE` and `MIN_VOLUME`. Healthcare and
biotech are ADMITTED and flagged, and so are US-listed shares of
foreign-domiciled companies -- his list excludes neither -- so the page can
warn about binary-event and domicile risk without the screener deciding on the
owner's behalf.

Nasdaq supplies the classification and the last session's price and volume; it
never supplies the bars the scans read. The transport -- the browser headers,
the bounded retry, the dated gzip cache and the fallback to the checked-in seed
-- is carried over unchanged from the module this replaces, because every one
of those rules was established by execution on a GitHub runner.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import logging
import math
import os
import re
import tempfile
import time
import zlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

log = logging.getLogger(__name__)

SOURCE_URL = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=10000&download=true"
#: The reviewed seed: Bonde's rules are bypassed for a name listed here, and a
#: name listed here is in the universe even when the directory has no row for
#: it. The seed is also the whole universe under SCAN_UNIVERSE=seed and the
#: fallback when neither a live directory nor a valid cache can be had.
SEED_FILE = Path(__file__).resolve().parent.parent / "data" / "symbols.txt"
#: Bonde's floors, from his own scan (`c/c1>=1.04 and v>v1 and v>=100000`) and
#: the field guide's "typically price >= $3". Both are read off the directory
#: row: `lastsale` is the last print and `volume` is the LAST SESSION's share
#: volume, not an average -- so a name that was quiet yesterday and bursts
#: today is refused tonight and admitted tomorrow. That is the cost of a
#: floor read from a listing rather than from bars, and it is stated here
#: rather than hidden. A price exactly at the floor and a volume exactly at
#: the floor are admitted, as `v>=100000` says.
MIN_PRICE = 3.0
MIN_VOLUME = 100_000
#: A safety bound on how many names one scan may ask for, NOT a selection
#: rule: Bonde's list runs to ~6,500 and the 10 Sep 2026 directory admits
#: 3,027 under the floors above, so this binds only if the endpoint expands
#: past anything seen. When it does, the least-liquid tail is cut, the cut is
#: counted under "discovery capacity" and the warning says so.
MAX_DISCOVERY = 8000

DIRECTORY_CACHE = "universe-directory.json.gz"
DIRECTORY_CACHE_SCHEMA = 1
DIRECTORY_MAX_AGE = timedelta(days=7)
DIRECTORY_MAX_BYTES = 10 * 1024 * 1024
DIRECTORY_MIN_ROWS = 500
DIRECTORY_MAX_ROWS = 10_000
DIRECTORY_FIELDS = ("symbol", "name", "country", "sector", "industry", "lastsale", "volume")
DIRECTORY_TIMEOUT = (5, 45)
DIRECTORY_ATTEMPTS = 3
DIRECTORY_RETRY_PAUSES = (1, 3)
TRANSIENT_STATUSES = frozenset({500, 502, 503, 504})
#: What api.nasdaq.com is asked with. A BROWSER's User-Agent, on purpose and on
#: evidence: from a GitHub-hosted runner the endpoint holds every non-browser
#: string open, unanswered, until the read times out -- the pipeline's own
#: "SpicyStock/1.0 (...)", python-requests' default, and the honest
#: "Mozilla/5.0 (compatible; SpicyStock/1.0; +url)" form all did -- while this
#: string, from the same kind of runner IP, returned 7,139 listings in 1.2 s.
#: Read off probe run 34414747241 (9 Sep 2026): one header set per fresh
#: runner, each asked with requests and again with curl. Seven runners, five
#: timeouts, and the two that answered were the two that named a browser. Not
#: the size of the reply (a limit=25 request hung too), not the runner's
#: network (the same runners read nasdaqtrader.com in 0.3 s), not the TLS
#: client (requests and curl agreed on every row). The five evening runs that
#: timed out before it, on Linux and on macOS, were this and nothing else.
#: No Alpaca header is sent to a different provider.
DIRECTORY_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
}

_SYMBOL = re.compile(r"[A-Z]{1,5}")
#: What a directory name must say before the row is read as a common share.
#: Wider than "common stock" because NYSE rows carry whatever suffix the
#: listing agent typed -- "Class C Capital Stock", "Common New", "Class A
#: Subordinate Voting Shares" -- and a class pattern is safe only because
#: `_REJECT` still refuses the preferreds and depositary shares it also
#: matches. A name with no security wording at all ("Yum! Brands Inc.",
#: "Visa Inc.") is still refused and belongs in the seed if wanted: 60 such
#: otherwise-admissible US names on the 10 Sep 2026 directory.
_NAME = re.compile(r"\b(common stock|common shares|ordinary shares?|capital stock|common new"
                   r"|class [abc]\b.*\b(?:stock|shares))\b", re.I)
_REJECT = re.compile(r"\b(depositary|depository|ADR|ADS|preferred|preference|warrants?|rights?|units?|notes?|ETF|ETN|funds?)\b", re.I)
#: A trust, whatever else the name says: REITs and closed-end trusts list
#: "Common Shares of Beneficial Interest", which `_NAME` alone reads as common
#: stock. Refused; 25 previously admitted names on the 10 Sep 2026 directory.
_BENEFICIAL = re.compile(r"\bshares of beneficial interest\b", re.I)
_BIOTECH = re.compile(r"biotech|pharma|medicinal", re.I)
UNITED_STATES = "United States"
HEALTH_CARE_SECTOR = "Health Care"
BLANK_CHECK_INDUSTRY = "blank checks"
#: The two flags this module raises; a flag is a warning for the reader and
#: never a verdict. Nasdaq prefixes "Biotechnology:" onto several industries
#: that are not biotech at all (Agilent's is "Biotechnology: Laboratory
#: Analytical Instruments"). `foreign` is any row whose country is not
#: "United States", a BLANK country included, since the directory then does
#: not vouch for a US domicile either. On the 10 Sep 2026 directory, of the
#: 3,027 admitted names, 538 carry `biotech` and 481 carry `foreign`, 74 of
#: those with no country stated.
BIOTECH_FLAG = "biotech"
FOREIGN_FLAG = "foreign"

#: SCAN_UNIVERSE's spellings. "adaptive" is what the workflow variable has
#: said since the selector this replaces; it means the directory now.
MODES = {"directory": "directory", "adaptive": "directory", "seed": "seed"}
DEFAULT_MODE = "directory"

SOURCE_LIVE = "nasdaq directory live"
SOURCE_CACHE = "nasdaq directory cache"
SOURCE_SEED = "seed file"
SOURCE_EXPLICIT = "explicit"

SEED_EXCEPTION = "seed exception"
CAPACITY_REASON = "discovery capacity"


class SymbolFileError(ValueError):
    """The seed file holds something that is not a ticker."""


@dataclass(frozen=True)
class Universe:
    """What one run scans, and where the list came from.

    `names` holds a company name only for a symbol the directory listed; a
    seed or explicit name the directory lacks has no entry. `flags` holds a
    set for every symbol -- `biotech`, `foreign`, both or neither. `counts`
    is every exclusion reason with its count, plus `listed` (directory rows
    seen) and `admitted` (symbols kept); `warning` names a fallback or a
    bound that bit, and is None on a clean directory build.
    """
    symbols: list[str]
    names: dict[str, str]
    flags: dict[str, set[str]]
    source: str
    fetched_at: str | None
    counts: dict[str, int]
    label: str
    warning: str | None = None

    @property
    def identity(self) -> str:
        return identity(self.symbols)


def mode() -> str:
    """'directory' or 'seed', from SCAN_UNIVERSE; both old spellings accepted."""
    value = os.getenv("SCAN_UNIVERSE", DEFAULT_MODE).strip().lower() or DEFAULT_MODE
    if value not in MODES:
        raise ValueError("SCAN_UNIVERSE must be 'directory' (or its old spelling 'adaptive') or 'seed'")
    return MODES[value]


def enabled() -> bool:
    """True when the directory is the universe; False for the seed alone."""
    return mode() == "directory"


def read_seed(path: Path | None = None) -> list[str]:
    """The checked-in symbol file, in file order.

    Blank lines and `#` comments are ignored; any other line that is not one
    A-Z ticker of one to five characters, or is a repeat, raises -- a typo must
    fail the run rather than quietly shrink the universe.
    """
    path = SEED_FILE if path is None else Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SymbolFileError(f"cannot read symbol file {path}: {exc}") from exc
    tickers: list[str] = []
    first_seen: dict[str, int] = {}
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if not _SYMBOL.fullmatch(line):
            raise SymbolFileError(f"{path} line {lineno}: {line!r} is not a ticker "
                                  "(expected one A-Z symbol of 1-5 characters per line)")
        if line in first_seen:
            raise SymbolFileError(f"{path} line {lineno}: {line} is already listed on line {first_seen[line]}")
        first_seen[line] = lineno
        tickers.append(line)
    if not tickers:
        raise SymbolFileError(f"{path}: no symbols found")
    return tickers


# ------------------------------------------------------------- transport ----


def fetch_directory() -> list[dict]:
    """The live directory, or an exception; never a partial answer.

    The retry is for a genuinely transient transport or server failure, with
    a bounded wait. An access refusal (any status outside TRANSIENT_STATUSES)
    raises on the first attempt, and a reply short of DIRECTORY_MIN_ROWS is
    refused rather than scanned, because a failed refresh must never quietly
    approve an unclassified company.
    """
    for attempt in range(DIRECTORY_ATTEMPTS):
        try:
            log.info("Refreshing Nasdaq stock directory (attempt %s/%s)", attempt + 1, DIRECTORY_ATTEMPTS)
            response = requests.get(SOURCE_URL, headers=dict(DIRECTORY_HEADERS), timeout=DIRECTORY_TIMEOUT)
            response.raise_for_status()
            break
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
            if isinstance(exc, requests.HTTPError) and (
                exc.response is None or exc.response.status_code not in TRANSIENT_STATUSES
            ):
                raise
            if attempt == DIRECTORY_ATTEMPTS - 1:
                raise
            log.warning("Directory request %s/%s failed (%s); retrying",
                        attempt + 1, DIRECTORY_ATTEMPTS, type(exc).__name__)
            time.sleep(DIRECTORY_RETRY_PAUSES[attempt])
    rows = response.json().get("data", {}).get("rows")
    if not isinstance(rows, list) or len(rows) < DIRECTORY_MIN_ROWS:
        raise ValueError("Nasdaq returned an incomplete stock directory")
    log.info("Nasdaq directory returned %s listings", len(rows))
    return rows


def _transient_directory_error(exc: Exception) -> bool:
    return isinstance(exc, (requests.Timeout, requests.ConnectionError)) or (
        isinstance(exc, requests.HTTPError) and exc.response is not None
        and exc.response.status_code in TRANSIENT_STATUSES)


def _read_directory_cache(docs: Path, now: datetime) -> tuple[list[dict], datetime]:
    """A captured directory, while it is younger than DIRECTORY_MAX_AGE."""
    try:
        path = docs / DIRECTORY_CACHE
        if path.stat().st_size > DIRECTORY_MAX_BYTES:
            raise ValueError
        with gzip.open(path, "rb") as file:
            raw = file.read(DIRECTORY_MAX_BYTES + 1)
        if len(raw) > DIRECTORY_MAX_BYTES:
            raise ValueError
        cached = json.loads(raw)
        if (not isinstance(cached, dict)
                or type(cached.get("schema_version")) is not int
                or cached["schema_version"] != DIRECTORY_CACHE_SCHEMA
                or cached.get("source_url") != SOURCE_URL):
            raise ValueError
        captured = datetime.fromisoformat(cached["fetched_at"])
        if captured.tzinfo is None or captured.utcoffset() != timedelta(0):
            raise ValueError
        age = now - captured
        if not timedelta(0) <= age <= DIRECTORY_MAX_AGE:
            raise ValueError
        rows = cached["rows"]
        if (not isinstance(rows, list) or not DIRECTORY_MIN_ROWS <= len(rows) <= DIRECTORY_MAX_ROWS
                or not all(isinstance(row, dict) and all(key in row for key in DIRECTORY_FIELDS)
                           for row in rows)):
            raise ValueError
    except (OSError, ValueError, TypeError, KeyError, OverflowError, EOFError, zlib.error):
        raise ValueError("Live directory unavailable and no valid Nasdaq directory captured "
                         "within seven days; using the curated seed") from None
    return rows, captured


def _save_directory_cache(docs: Path, rows: list[dict], fetched_at: str) -> None:
    """Atomically retain only the official fields the rules inspect."""
    payload = {"schema_version": DIRECTORY_CACHE_SCHEMA, "source_url": SOURCE_URL,
               "fetched_at": fetched_at,
               "rows": [{key: row.get(key) for key in DIRECTORY_FIELDS} for row in rows
                        if isinstance(row, dict)]}
    raw = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    if len(raw) > DIRECTORY_MAX_BYTES:
        raise ValueError("Directory cache exceeds the size limit")
    compressed = gzip.compress(raw, mtime=0)
    if len(compressed) > DIRECTORY_MAX_BYTES:
        raise ValueError("Compressed directory cache exceeds the size limit")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=docs,
                                         prefix=".universe-directory-", suffix=".tmp", delete=False) as file:
            temporary = Path(file.name)
            file.write(compressed)
        temporary.replace(docs / DIRECTORY_CACHE)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


# -------------------------------------------------------- classification ----


def _number(raw) -> float | None:
    try:
        value = float(str(raw).replace("$", "").replace(",", ""))
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def flags_for(row: dict) -> set[str]:
    """What the page should warn about; never a reason to refuse."""
    flagged: set[str] = set()
    if row.get("sector") == HEALTH_CARE_SECTOR or _BIOTECH.search(str(row.get("industry") or "")):
        flagged.add(BIOTECH_FLAG)
    if row.get("country") != UNITED_STATES:
        flagged.add(FOREIGN_FLAG)
    return flagged


def classify(row: dict, seeds: set[str]) -> str | None:
    """The reason a directory row is refused, or None when it is admitted.

    A seed name bypasses every rule below by design: the file is the owner's
    reviewed list. A row whose sector or industry is blank is refused as
    unknown because the blank-check rule cannot be applied to it -- on the
    10 Sep 2026 directory 67 of the 102 such rows were acquisition shells
    by name.
    """
    symbol = row.get("symbol", "")
    if not isinstance(symbol, str) or not _SYMBOL.fullmatch(symbol):
        return "symbol format"
    if symbol in seeds:
        return None
    name = str(row.get("name") or "")
    if not _NAME.search(name) or _REJECT.search(name) or _BENEFICIAL.search(name):
        return "not verified common stock"
    sector, industry = row.get("sector"), row.get("industry")
    if not sector or not industry:
        return "unknown industry"
    if str(industry).lower() == BLANK_CHECK_INDUSTRY:
        return "blank check company"
    price, volume = _number(row.get("lastsale")), _number(row.get("volume"))
    if price is None or price < MIN_PRICE:
        return f"price under ${MIN_PRICE:g}"
    if volume is None or volume < MIN_VOLUME:
        return f"volume under {MIN_VOLUME:,} shares"
    return None


def admit(rows: list[dict], seeds: list[str]) -> tuple[list[str], dict[str, str], dict[str, set[str]], dict[str, int]]:
    """Every admitted symbol with its name, flags and the exclusion counts.

    Seeds are admitted whether or not the directory carries them, and counted
    under SEED_EXCEPTION when the rules alone would not have admitted them.
    Past MAX_DISCOVERY the least-liquid tail (last price times last volume) is
    cut and counted under CAPACITY_REASON; seeds are never cut.
    """
    seed_set = set(seeds)
    names: dict[str, str] = {}
    flags: dict[str, set[str]] = {}
    dollars: dict[str, float] = {}
    counts: dict[str, int] = {"listed": 0}
    exceptions = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        counts["listed"] += 1
        reason = classify(row, seed_set)
        if reason is not None:
            counts[reason] = counts.get(reason, 0) + 1
            continue
        symbol = row["symbol"]
        if symbol in seed_set and classify(row, set()) is not None:
            exceptions += 1
        if isinstance(row.get("name"), str) and row["name"].strip():
            names[symbol] = row["name"].strip()
        flags[symbol] = flags.get(symbol, set()) | flags_for(row)
        price, volume = _number(row.get("lastsale")), _number(row.get("volume"))
        dollars[symbol] = max(dollars.get(symbol, 0.0), (price or 0.0) * (volume or 0.0))
    for symbol in seed_set - set(dollars):
        exceptions += 1
        flags.setdefault(symbol, set())
        dollars[symbol] = math.inf
    if exceptions:
        counts[SEED_EXCEPTION] = exceptions
    ranked = sorted(dollars, key=lambda symbol: (symbol not in seed_set, -dollars[symbol], symbol))
    if len(ranked) > MAX_DISCOVERY:
        counts[CAPACITY_REASON] = len(ranked) - MAX_DISCOVERY
        for symbol in ranked[MAX_DISCOVERY:]:
            flags.pop(symbol, None)
            names.pop(symbol, None)
        ranked = ranked[:MAX_DISCOVERY]
    symbols = sorted(ranked)
    counts["admitted"] = len(symbols)
    return symbols, names, flags, counts


# ------------------------------------------------------------------ build ----


def identity(symbols: list[str]) -> str:
    """A short, order-independent digest of a symbol list."""
    return hashlib.sha256("\n".join(sorted(symbols)).encode()).hexdigest()[:16]


def _floors() -> str:
    return f"${MIN_PRICE:g}+ and {MIN_VOLUME:,}+ shares last session"


def _seed_universe(seeds: list[str], warning: str | None) -> Universe:
    symbols = sorted(seeds)
    return Universe(symbols=symbols, names={}, flags={s: set() for s in symbols}, source=SOURCE_SEED,
                    fetched_at=None, counts={"admitted": len(symbols)},
                    label=f"{len(symbols)} checked-in US common stocks (data/symbols.txt)", warning=warning)


def _explicit_universe(explicit: list[str]) -> Universe:
    symbols = sorted({s.strip().upper() for s in explicit})
    bad = [s for s in symbols if not _SYMBOL.fullmatch(s)]
    if bad or not symbols:
        raise ValueError(f"explicit tickers must be A-Z symbols of 1-5 characters; refused {bad or 'an empty list'}")
    return Universe(symbols=symbols, names={}, flags={s: set() for s in symbols}, source=SOURCE_EXPLICIT,
                    fetched_at=None, counts={"admitted": len(symbols)},
                    label=f"{len(symbols)} named on the command line (--tickers)")


def _directory(docs: Path, now: datetime) -> tuple[list[dict], str, datetime]:
    """Rows, source and capture time: live, else the cache, else an error.

    The cache is borrowed only for a transient transport failure. An access
    refusal or an incomplete live reply is not an outage, and raises through
    to the seed fallback instead -- the rule the previous module set.
    """
    try:
        rows = fetch_directory()
    except Exception as exc:
        if not _transient_directory_error(exc):
            raise
        rows, captured = _read_directory_cache(docs, now)
        return rows, SOURCE_CACHE, captured
    try:
        _save_directory_cache(docs, rows, now.isoformat())
    except Exception as exc:
        # A storage problem must not discard a valid live directory.
        log.warning("Directory cache could not be saved (%s)", type(exc).__name__)
    return rows, SOURCE_LIVE, now


def build(docs: Path, *, explicit: list[str] | None = None, now: datetime | None = None) -> Universe:
    """The universe for one run.

    `explicit` (the --tickers override) wins over everything and asks nothing
    of the network. Otherwise SCAN_UNIVERSE decides: the seed file alone, or
    the directory -- live, then the gzip cache under `docs`, then the seed
    with a warning that says which fallback was taken and why, in a
    controlled sentence that never quotes a provider's reply.
    """
    if explicit is not None:
        return _explicit_universe(explicit)
    seeds = read_seed()
    if mode() == "seed":
        return _seed_universe(seeds, None)
    now = datetime.now(timezone.utc) if now is None else now
    try:
        rows, source, captured = _directory(docs, now)
    except Exception as exc:
        warning = (str(exc) if isinstance(exc, ValueError) else
                   f"Universe refresh unavailable ({type(exc).__name__}); using the curated seed")
        log.warning("%s", warning)
        return _seed_universe(seeds, warning)
    symbols, names, flags, counts = admit(rows, seeds)
    age_days = (now - captured).total_seconds() / 86400
    if source == SOURCE_CACHE:
        source = f"{SOURCE_CACHE} {age_days:.1f} days old"
        provenance = f"Nasdaq directory captured {captured.date().isoformat()}"
        warning = (f"Live listings refresh unavailable; using Nasdaq listings captured "
                   f"{captured.date().isoformat()} (maximum age seven days).")
    else:
        provenance = f"Nasdaq directory {captured.date().isoformat()}"
        warning = None
    if CAPACITY_REASON in counts:
        cut = f"MAX_DISCOVERY bound: {counts[CAPACITY_REASON]} least-liquid names cut at {MAX_DISCOVERY}."
        warning = cut if warning is None else f"{warning} {cut}"
        log.warning("%s", cut)
    biotech = sum(BIOTECH_FLAG in flagged for flagged in flags.values())
    foreign = sum(FOREIGN_FLAG in flagged for flagged in flags.values())
    label = (f"{len(symbols)} US-listed common stocks from the {provenance}, {_floors()}"
             f" ({biotech} flagged {BIOTECH_FLAG}, {foreign} flagged {FOREIGN_FLAG})")
    log.info("Universe: %s", label)
    return Universe(symbols=symbols, names=names, flags=flags, source=source,
                    fetched_at=captured.isoformat(), counts=counts, label=label, warning=warning)
