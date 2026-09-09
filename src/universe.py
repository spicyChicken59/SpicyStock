"""A dated, bounded research universe; never a broker order permission.

Nasdaq supplies security classification, not the prices used for ranking.
Alpaca's split-adjusted, delayed SIP daily bars supply that evidence. Unknown
classification is excluded. The original curated file is a labelled fallback.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import time
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path

import requests

from src import scanner

log = logging.getLogger(__name__)
LABEL = "adaptive US common stocks (Nasdaq + Alpaca)"
VERSION = "nasdaq-sip-rotation-v1"
SOURCE_URL = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=10000&download=true"
CAPACITY = 500
MIN_DOLLARS = 20_000_000
LOOKBACK = 20
MAX_DISCOVERY = 6000
_NAME = re.compile(r"\b(common stock|common shares|ordinary shares?)\b", re.I)
_REJECT = re.compile(r"\b(depositary|depository|ADR|ADS|preferred|preference|warrants?|rights?|units?|notes?|ETF|ETN|funds?)\b", re.I)
_BIOTECH = re.compile(r"biotech|pharma|medicinal", re.I)


def enabled() -> bool:
    value = os.getenv("SCAN_UNIVERSE", "seed").strip().lower() or "seed"
    if value not in {"adaptive", "seed"}:
        raise ValueError("SCAN_UNIVERSE must be 'adaptive' or 'seed'")
    return value == "adaptive"


def fetch_directory() -> list[dict]:
    # No Alpaca header is sent to a different provider. A failed directory
    # refresh never silently approves an unclassified company.
    # The first production refresh timed out downloading this ~2 MB response.
    # Retry only transient transport/server failures, with a bounded wait;
    # access refusals and incomplete classifications still fail immediately.
    for attempt in range(3):
        try:
            response = requests.get(SOURCE_URL, headers={
                "User-Agent": "SpicyStock/1.0 (https://github.com/spicyChicken59/SpicyStock)",
                "Accept": "application/json",
            }, timeout=(5, 45))
            response.raise_for_status()
            break
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
            if isinstance(exc, requests.HTTPError) and (
                exc.response is None or exc.response.status_code not in {500, 502, 503, 504}
            ):
                raise
            if attempt == 2:
                raise
            log.warning("Directory request %s/3 failed (%s); retrying", attempt + 1, type(exc).__name__)
            time.sleep((1, 3)[attempt])
    rows = response.json().get("data", {}).get("rows")
    if not isinstance(rows, list) or len(rows) < 500:
        raise ValueError("Nasdaq returned an incomplete stock directory")
    return rows


def classification(row: dict, seeds: set[str]) -> str | None:
    """Return the explicit exclusion, or None for a known eligible security."""
    symbol = row.get("symbol", "")
    if not isinstance(symbol, str) or not re.fullmatch(r"[A-Z]{1,5}", symbol):
        return "symbol format"
    # The checked-in names are individually reviewed exceptions (including
    # diversified pharma). They do not approve any other security by name.
    if symbol in seeds:
        return None
    name = str(row.get("name") or "")
    if not _NAME.search(name) or _REJECT.search(name):
        return "not verified common stock"
    if row.get("country") != "United States":
        return "foreign or unknown issuer"
    sector, industry = row.get("sector"), row.get("industry")
    if not sector or not industry:
        return "unknown industry"
    if sector == "Health Care" or _BIOTECH.search(str(industry)):
        return "healthcare or biotech exclusion"
    if str(industry).lower() == "blank checks":
        return "blank check company"
    return None


def _number(raw) -> float | None:
    try:
        value = float(str(raw).replace("$", "").replace(",", ""))
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def directory_pool(rows: list[dict], seeds: list[str]) -> tuple[list[str], dict]:
    approved, reasons = {}, {}
    seed_set = set(seeds)
    for row in rows:
        if not isinstance(row, dict):
            continue
        reason = classification(row, seed_set)
        price, volume = _number(row.get("lastsale")), _number(row.get("volume"))
        if reason is None and (price is None or price <= 4 or volume is None or volume <= 0):
            reason = "no recent trading above $4"
        if reason:
            reasons[reason] = reasons.get(reason, 0) + 1
        else:
            approved[row["symbol"]] = price * volume
    # A future endpoint expansion cannot create an unbounded market-data job.
    # This cap is reported; prices here only bound discovery, never rank picks.
    ordered = sorted(approved, key=lambda symbol: (-approved[symbol], symbol))
    if len(ordered) > MAX_DISCOVERY:
        reasons["discovery capacity"] = len(ordered) - MAX_DISCOVERY
    return sorted(ordered[:MAX_DISCOVERY]), reasons


def measure(frame, session: date) -> dict | None:
    """Twenty settled prior sessions plus the target day's participation."""
    if frame is None or len(frame) < LOOKBACK + 1:
        return None
    if scanner._last_bar_date(frame) != session or scanner._session_bar_problem(frame):
        return None
    tail = frame.tail(LOOKBACK + 1)
    if tail[["Close", "Volume"]].isna().any().any():
        return None
    closes, volumes = tail["Close"].astype(float), tail["Volume"].astype(float)
    if not all(math.isfinite(x) and x > 0 for x in [*closes, *volumes]):
        return None
    close = float(closes.iloc[-1])
    average = float((closes.iloc[:-1] * volumes.iloc[:-1]).median())
    today = close * float(volumes.iloc[-1])
    # Absolute consolidated-tape protection is necessary: a percentile alone
    # becomes easier when thousands of illiquid names are added to its pool.
    if close <= 4 or average < MIN_DOLLARS or today < MIN_DOLLARS:
        return None
    return {
        "momentum": close / float(closes.iloc[0]) - 1,
        "gain": close / float(closes.iloc[-2]) - 1,
        "participation": float(volumes.iloc[-1]) / float(volumes.iloc[:-1].mean()),
        "liquidity": average,
    }


def rotate(metrics: dict[str, dict], session: date, retained=(), capacity=CAPACITY) -> tuple[list[str], dict]:
    """Separate room for breakouts, building momentum, liquidity and discovery."""
    selected, reasons = [], {}
    def take(names, limit, reason, ceiling=None):
        count = 0
        for symbol in names:
            if symbol not in metrics or symbol in reasons:
                continue
            ceiling = capacity if ceiling is None else ceiling
            if len(selected) >= ceiling or count >= limit:
                break
            selected.append(symbol)
            reasons[symbol] = reason
            count += 1
    primary_capacity = max(0, capacity - min(50, capacity))
    take(retained, min(100, capacity), "recent setup", primary_capacity)
    breakout = sorted((s for s in metrics if metrics[s]["gain"] >= .04),
                      key=lambda s: (-metrics[s]["participation"], -metrics[s]["liquidity"], s))
    take(breakout, min(150, capacity), "4% move", primary_capacity)
    leaders = sorted(metrics, key=lambda s: (-metrics[s]["momentum"], -metrics[s]["participation"], s))
    take(leaders, min(150, capacity), "20-session momentum", primary_capacity)
    liquid = sorted(metrics, key=lambda s: (-metrics[s]["liquidity"], s))
    take(liquid, min(100, capacity), "liquid leader", primary_capacity)
    # Stable per session, changes between sessions, not biased by ticker order.
    exploration = sorted(metrics, key=lambda s: hashlib.sha256(f"{session}:{s}".encode()).hexdigest())
    take(exploration, 50, "rotating discovery")
    take(leaders, capacity, "20-session momentum")
    return sorted(selected), {r: sum(v == r for v in reasons.values()) for r in sorted(set(reasons.values()))}


def _previous(docs: Path) -> dict:
    try:
        snapshot = json.loads((docs / "data.json").read_text())
        return snapshot if isinstance(snapshot, dict) and not snapshot.get("run", {}).get("fixture") else {}
    except (OSError, ValueError, TypeError):
        return {}


def _recent_symbols(docs: Path, session: date) -> list[str]:
    try:
        book = json.loads((docs / "ledger.json").read_text())
        rows = []
        for run in book.get("runs", []):
            age = (session - date.fromisoformat(run["date"])).days
            if 0 < age <= 8:
                rows.extend(row["ticker"] for key in ("candidates", "gated")
                            for row in run.get(key, []) if isinstance(row.get("ticker"), str))
        return list(dict.fromkeys(rows))
    except (OSError, ValueError, KeyError, TypeError):
        return []


def select(cfg: scanner.ScanConfig, docs: Path, *, data_client=None) -> tuple[list[str], dict]:
    """Refresh production discovery, with an honest bounded fallback."""
    seeds = scanner.get_universe()
    session = cfg.session_date or scanner.current_session()
    previous = _previous(docs)
    prior = previous.get("run", {}).get("universe", {})
    old = prior.get("tickers", seeds)
    if not isinstance(old, list) or not all(isinstance(s, str) for s in old):
        old = seeds
    meta = {"version": VERSION, "mode": "adaptive", "source": "Nasdaq stock screener + Alpaca daily bars",
            "source_url": SOURCE_URL, "refreshed_at": datetime.now(timezone.utc).isoformat(),
            "source_date": None, "session": session.isoformat(), "discovered": 0, "eligible": 0,
            "screened": 0, "selected": 0, "capacity": CAPACITY, "lookback_sessions": LOOKBACK,
            "liquidity_min_dollars": MIN_DOLLARS, "warning": None,
            "classification": "US common stock; new healthcare, biotech and pharma excluded; curated exceptions",
            "reason_counts": {}, "exclusions": {}}
    try:
        if cfg.feed != scanner.DataFeed.SIP:
            raise ValueError("Adaptive selection needs consolidated SIP volume; using the curated seed on this feed")
        # Never apply today's directory to a genuinely historical session.
        if cfg.session_date is not None and cfg.session_date != scanner.current_session():
            raise ValueError("Historical backfill uses the curated seed; today's membership is not historical evidence")
        rows = fetch_directory()
        pool, excluded = directory_pool(rows, seeds)
        meta.update(discovered=len(rows), eligible=len(pool), exclusions=excluded)
        if len(pool) < 100:
            raise ValueError("Too few securities had verified US common-stock classification")
        client = data_client or scanner.get_clients()
        short_cfg = replace(cfg, lookback_days=35)
        metrics, returned, fresh = {}, 0, 0
        for start in range(0, len(pool), cfg.batch_size):
            frames = scanner._download_batch(client, pool[start:start + cfg.batch_size], short_cfg, session)
            returned += len(frames)
            for symbol, frame in frames.items():
                fresh += scanner._last_bar_date(frame) == session
                values = measure(frame, session)
                if values is not None:
                    metrics[symbol] = values
        meta["screened"] = returned
        meta["fresh"] = fresh
        if returned < len(pool) * .8 or fresh < returned * .8 or len(metrics) < 50:
            raise ValueError("Broad liquidity screen was incomplete; keeping a known classified basket")
        chosen, reasons = rotate(metrics, session, _recent_symbols(docs, session))
        meta["reason_counts"] = reasons
    except Exception as exc:
        # Do not mask market-data auth failures: the actual scan below still
        # uses the normal loud failure guards. Exception bodies can contain
        # provider details, so publish only a controlled type and explanation.
        meta["mode"] = "fallback"
        meta["warning"] = (str(exc) if isinstance(exc, ValueError) else
                           f"Universe refresh unavailable ({type(exc).__name__}); using the curated seed")
        chosen = seeds
        log.warning("%s", meta["warning"])
    meta.update(selected=len(chosen), added=sorted(set(chosen) - set(old)),
                removed=sorted(set(old) - set(chosen)), retained=len(set(chosen) & set(old)))
    return chosen, meta


def identity(symbols: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(symbols)).encode()).hexdigest()[:16]


def benchmark_history(book, cfg, through, available):
    """Short windows for original rotating baskets; no survivor substitution."""
    needed = set()
    seed = None
    for run in book._fill_window():
        block = run.get("universe") or {}
        legacy_seed = block.get("label") == "data/symbols.txt (checked in)"
        if not isinstance(block.get("selection"), dict) and not legacy_seed:
            continue
        benchmark = run.get("benchmark") or {}
        if all(benchmark.get(f"d{h}") is not None and
               (benchmark.get("from_open") or {}).get(f"d{h}") is not None for h in (1, 3, 5)):
            continue
        day = date.fromisoformat(run["date"])
        # An old failed fill stays pending; a short window cannot recreate it.
        if not 0 < (through - day).days <= 14:
            continue
        if legacy_seed:
            seed = seed if seed is not None else scanner.get_universe()
        members = seed if legacy_seed else block.get("tickers", [])
        needed.update(t for t in members if t not in available)
    result = dict(available)
    if needed:
        client = scanner.get_clients()
        short_cfg = replace(cfg, lookback_days=15)
        symbols = sorted(needed)
        for start in range(0, len(symbols), cfg.batch_size):
            result.update(scanner._download_batch(client, symbols[start:start + cfg.batch_size], short_cfg, through))
    return result
