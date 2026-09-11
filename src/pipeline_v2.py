"""The evening run and the intraday check: preflight, fetch, scan, grade,
plan, record, publish, mail. Exit codes are the workflow's contract:
0 ok, 1 failed before publishing, 2 degraded but published, 3 failed after
publishing (the record is on disk; only delivery failed)."""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from src import breadth, charts, clock, grader, market_data, plan, quality, record, report, scans
from src import universe_v2 as universe
from src import watchlist

log = logging.getLogger("spicystock.pipeline")

# ------------------------------------------------------------------ rules ---
MAX_READS = 12                 # Claude reads per night, by mechanical grade (P)
FETCH_BUDGET_SECONDS = 900     # past this the run continues with what it has (P)
FETCH_CHUNK = 500              # symbols per timed fetch step (plumbing)
LOOKBACK_DAYS = 260            # sessions: Double Trouble needs 252 (B)
MIN_COVERAGE_FRACTION = 0.5    # fewer names answering than this is a feed outage (P)
CLOSED_FRACTION = 0.05         # fewer names on the expected session than this is a closed market (P)
MAX_ERROR_FRACTION = 0.05      # more names raising than this is a code fault, not a market (P)
SERIES_BARS = 120              # bars the page chart carries per trade (plumbing)
NIGHTS_KEPT = record.NIGHTS_KEPT
TRADE_GRADES = ("A+", "A")     # what gets an order (B: "don't settle for marginal setups")
YELLOW_GRADES = ("A+",)        # what a yellow night admits (P)
GRADE_ORDER = {"A+": 0, "A": 1, "B": 2, "C": 3, "skip": 4}
GRADE_KEYS = {"a_plus": "A+", "a": "A", "b": "B", "c": "C", "skip": "skip"}   # run.graded, as the page reads it
BENCHMARK_SYMBOL = "SPY"       # one extra symbol for the scorecard's comparison line
RULES_VERSION_NOTE = "v2.0"

EXIT_OK, EXIT_FAILED, EXIT_DEGRADED, EXIT_FAILED_AFTER_PUBLISH = 0, 1, 2, 3
MODES = ("evening", "intraday")
DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
CHARTS_DIR_NAME = "charts"
DATA_FILE = "data.json"
LIVE_FILE = "live.json"
MARKET_TZ = ZoneInfo("America/New_York")

RULES = {
    "pipeline.max_reads": MAX_READS,
    "pipeline.fetch_budget_seconds": FETCH_BUDGET_SECONDS,
    "pipeline.lookback_days": LOOKBACK_DAYS,
    "pipeline.min_coverage_fraction": MIN_COVERAGE_FRACTION,
    "pipeline.closed_fraction": CLOSED_FRACTION,
    "pipeline.max_error_fraction": MAX_ERROR_FRACTION,
    "pipeline.trade_grades": list(TRADE_GRADES),
    "pipeline.yellow_grades": list(YELLOW_GRADES),
    "pipeline.series_bars": SERIES_BARS,
}


class PreflightError(RuntimeError):
    """A required environment variable is missing; nothing was spent."""


@dataclass
class RunReport:
    """Everything the run would otherwise only whisper into a log."""

    stage: str = "startup"
    problems: list[dict] = field(default_factory=list)
    published: bool = False
    failed: bool = False
    failure: str | None = None

    def problem(self, kind: str, message: Any) -> None:
        self.problems.append(report.problem(self.stage, kind, message))
        log.warning("%s: %s", kind, message)

    def fail(self, exc: BaseException) -> None:
        self.failed = True
        self.failure = f"{type(exc).__name__}: {exc}"
        log.error("run failed at %s: %s", self.stage, self.failure)

    @property
    def status(self) -> str:
        if self.failed and not self.published:
            return "failed"
        return "degraded" if self.problems or self.failed else "ok"

    def exit_code(self) -> int:
        if self.failed:
            return EXIT_FAILED_AFTER_PUBLISH if self.published else EXIT_FAILED
        return EXIT_DEGRADED if self.problems else EXIT_OK


# -------------------------------------------------------------- preflight ---
def delivery_enabled() -> bool:
    value = os.getenv("SCAN_SEND_EMAIL", "true").strip().lower() or "true"
    if value not in {"true", "false"}:
        raise ValueError("SCAN_SEND_EMAIL must be true or false")
    return value == "true"


def missing_env(run_type: str = "evening", dry_run: bool = False) -> list[str]:
    """Which required variables are unset or empty, composed per mode."""
    required = list(market_data.REQUIRED_ENV)
    if run_type == "evening":
        required += list(grader.REQUIRED_ENV)
    if not dry_run and delivery_enabled():
        required += list(report.REQUIRED_ENV)
    return [name for name in required if not os.environ.get(name, "").strip()]


def preflight(run_type: str = "evening", dry_run: bool = False) -> None:
    missing = missing_env(run_type, dry_run)
    if missing:
        raise PreflightError("missing or empty required environment: " + ", ".join(missing)
                             + ". Nothing has been spent. See .env.example.")
    log.info("Preflight OK%s", " (dry run: delivery keys not required)" if dry_run else "")


# ---------------------------------------------------------------- session ---
def expected_session(now: datetime | None = None) -> date:
    """The session tonight's run is expected to publish: a pin wins, else the
    session the market clock says (today on a weekday, Friday on a weekend)."""
    pinned = clock.pinned_session()
    return pinned if pinned else clock.current_session(now)


def session_state(frames: dict[str, pd.DataFrame], expected: date) -> tuple[str, float]:
    """'open', 'closed' or 'outage' from the bars alone, with the fraction of
    answered frames whose newest bar is the expected session."""
    if not frames:
        return "outage", 0.0
    newest = [market_data.last_bar_date(df) for df in frames.values()]
    have = sum(1 for d in newest if d == expected) / len(newest)
    if have >= MIN_COVERAGE_FRACTION:
        return "open", have
    previous = clock.previous_session(expected)
    carry_previous = sum(1 for d in newest if d == previous) / len(newest)
    if have < CLOSED_FRACTION and carry_previous >= MIN_COVERAGE_FRACTION:
        return "closed", have
    return "outage", have


def newest_common_session(frames: dict[str, pd.DataFrame]) -> date | None:
    """The newest date at least half the frames carry (the session a closed
    night re-presents)."""
    calendar = market_data.session_calendar(frames)
    return calendar[-1] if calendar else None


# ------------------------------------------------------------------ fetch ---
def fetch_universe(client, symbols: list[str], session: date, feed, rep: RunReport,
                   *, budget_seconds: float = FETCH_BUDGET_SECONDS,
                   now: datetime | None = None) -> tuple[dict[str, pd.DataFrame], market_data.DownloadStats, float]:
    """Every frame the feed returns for `symbols`, in timed chunks; past the
    budget the rest is left unfetched and recorded as coverage_thin."""
    frames: dict[str, pd.DataFrame] = {}
    merged = market_data.DownloadStats(session=session, feed=getattr(feed, "value", str(feed)))
    started = time.monotonic()
    fetched = 0
    for start in range(0, len(symbols), FETCH_CHUNK):
        chunk = symbols[start:start + FETCH_CHUNK]
        got, stats = market_data.download_bars(client, chunk, session, LOOKBACK_DAYS, feed, now=now)
        frames.update(got)
        merged.requested += stats.requested
        merged.with_bars += stats.with_bars
        merged.dropped += stats.dropped
        merged.no_bars.extend(stats.no_bars)
        merged.duplicates.update(stats.duplicates)
        fetched += len(chunk)
        elapsed = time.monotonic() - started
        if elapsed > budget_seconds and fetched < len(symbols):
            rep.problem("coverage_thin",
                        f"the bars fetch passed its {int(budget_seconds)}s budget after {fetched} of "
                        f"{len(symbols)} names; the rest were not read tonight")
            merged.requested += len(symbols) - fetched
            break
    merged.no_bars.sort()
    return frames, merged, time.monotonic() - started


# ------------------------------------------------------------------ scans ---
def series_of(df: pd.DataFrame, bars: int = SERIES_BARS) -> list[dict]:
    rows = []
    for stamp, row in df.iloc[-bars:].iterrows():
        d = market_data._as_date(stamp)
        if d is None:
            continue
        rows.append({"date": d.isoformat(), "o": _num(row.get("Open")), "h": _num(row.get("High")),
                     "l": _num(row.get("Low")), "c": _num(row.get("Close")), "v": _num(row.get("Volume"))})
    return rows


def _num(value) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return round(f, 4) if math.isfinite(f) else None


def extension_pct(df: pd.DataFrame, sessions: int = quality.EXTENSION_SMA_SESSIONS) -> float | None:
    closes = pd.to_numeric(df["Close"], errors="coerce").dropna()
    if len(closes) < sessions + 1:
        return None
    avg = float(closes.iloc[-sessions:].mean())
    return round(100 * (float(closes.iloc[-1]) / avg - 1), 1) if avg > 0 else None


def scan_frames(frames: dict[str, pd.DataFrame], uni: universe.Universe,
                rep: RunReport) -> tuple[list[dict], int, int]:
    """Every burst tonight (4% or $ breakout) with its measurements and its
    checklist assessment; plus how many names were measured and how many raised."""
    bursts: list[dict] = []
    measured = errors = 0
    for ticker, df in frames.items():
        if ticker == BENCHMARK_SYMBOL:
            continue
        try:
            found = scans.scan_all(df)
            measured += 1
        except Exception as exc:  # noqa: BLE001 -- counted, never fatal per symbol
            errors += 1
            log.debug("scan raised for %s: %s", ticker, exc)
            continue
        burst, dollar = found.get("burst"), found.get("dollar")
        if not burst and not dollar:
            continue
        try:
            assessment = quality.assess(df)
        except Exception as exc:  # noqa: BLE001
            errors += 1
            log.debug("quality raised for %s: %s", ticker, exc)
            continue
        last, prev = df.iloc[-1], df.iloc[-2]
        source = burst or {}
        row = {
            "ticker": ticker,
            "name": uni.names.get(ticker, ""),
            "flags": sorted(uni.flags.get(ticker, set())),
            "scan": "both" if burst and dollar else ("burst" if burst else "dollar"),
            "close": _num(last["Close"]), "prev_close": _num(prev["Close"]),
            "open": _num(last["Open"]), "high": _num(last["High"]), "low": _num(last["Low"]),
            "gain_pct": source.get("gain_pct", _gain(last, prev)),
            "volume": _num(last["Volume"]), "volume_vs_prior": source.get("volume_vs_prior"),
            "dollar_volume": source.get("dollar_volume", _num(float(last["Close"]) * float(last["Volume"]))),
            "dollar_move": (dollar or {}).get("move"),
            "extension_pct": extension_pct(df),
            "quality": {**assessment.to_dict(), "base": base_block(assessment.base, df)},
            "grade_mechanical": assessment.grade,
            "score": assessment.score,
            "vetoes": list(assessment.vetoes),
            "reclass": assessment.reclass,
            "_assessment": assessment,
        }
        bursts.append(row)
    if measured and errors / max(measured + errors, 1) > MAX_ERROR_FRACTION:
        raise RuntimeError(f"{errors} of {measured + errors} names raised inside the scan: "
                           "a code fault, not a market")
    if errors:
        rep.problem("coverage_thin", f"{errors} names raised inside the scan and were skipped")
    return bursts, measured, errors


def base_block(base: dict | None, df: pd.DataFrame) -> dict | None:
    """The checklist's base with its positions turned into dates, its length
    named ``sessions``, its depth in percent of the high, and the sessions
    inside it that closed down a breakdown's worth (the 4% the scan uses).
    ``start``/``end`` positions are kept beside them for the chart renderer."""
    if not base:
        return None
    start, end = int(base["start"]), int(base["end"])
    dates = [market_data._as_date(stamp) for stamp in df.index]
    closes = pd.to_numeric(df["Close"], errors="coerce").to_numpy(dtype=float)
    breakdowns = []
    for i in range(max(start, 1), min(end, len(df) - 1) + 1):
        prev, cur = closes[i - 1], closes[i]
        if prev > 0 and math.isfinite(cur) and cur / prev <= scans.BREAKDOWN_RATIO and dates[i] is not None:
            breakdowns.append(dates[i].isoformat())
    high, low = base.get("high"), base.get("low")
    depth = round(100 * (high - low) / high, 1) if high and low is not None and high > 0 else None
    return {"start": dates[start].isoformat() if dates[start] else None,
            "end": dates[end].isoformat() if dates[end] else None,
            "start_index": start, "end_index": end, "sessions": int(base.get("length") or end - start + 1),
            "high": high, "low": low, "depth_pct": depth, "breakdown_dates": breakdowns}


def _gain(last, prev) -> float | None:
    try:
        return round(100 * (float(last["Close"]) / float(prev["Close"]) - 1), 2)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def rank(bursts: list[dict]) -> list[dict]:
    bursts.sort(key=lambda b: (GRADE_ORDER.get(b["grade"], 9), -(b["score"] or 0), b["ticker"]))
    for i, b in enumerate(bursts, 1):
        b["rank"] = i
    return bursts


# ---------------------------------------------------------------- grading ---
def read_charts_and_grade(bursts: list[dict], frames: dict[str, pd.DataFrame], rep: RunReport,
                          charts_dir: Path, system_prompt: str, dry_run: bool) -> dict:
    """Render a chart and ask Claude for the top MAX_READS bursts by mechanical
    grade; clamp the reply to at most the mechanical grade."""
    ordered = sorted(bursts, key=lambda b: (GRADE_ORDER.get(b["grade_mechanical"], 9),
                                            -(b["score"] or 0), b["ticker"]))
    candidates = []
    for b in ordered[:MAX_READS]:
        assessment: quality.Assessment = b["_assessment"]
        df = frames[b["ticker"]]
        chart_path = None
        try:
            base = assessment.base or {}
            box = (base["start"], base["end"], base["low"], base["high"]) if base else None
            chart_path = charts.render_chart(b["ticker"], df, str(charts_dir), box=box,
                                             stop=(b.get("plan") or {}).get("stop"),
                                             title=f"{b['ticker']} — daily, burst {b['gain_pct']}%")
        except Exception as exc:  # noqa: BLE001
            rep.problem("chart_missing", f"{b['ticker']}: {type(exc).__name__}")
        b["chart"] = f"{CHARTS_DIR_NAME}/{b['ticker']}.png" if chart_path else None
        extra = {"scan": b["scan"], "flags": b["flags"], "gain_pct": b["gain_pct"],
                 "volume_vs_prior": b["volume_vs_prior"], "dollar_volume": b["dollar_volume"]}
        candidates.append({"ticker": b["ticker"],
                           "metrics": quality.metrics_for_model(assessment, b["ticker"], b["close"], extra),
                           "chart": chart_path})
    usage: dict = {}
    rows = grader.grade_all(candidates, system_prompt, MAX_READS, usage) if candidates else []
    by_ticker = {r["ticker"]: r for r in rows}
    done = unavailable = 0
    for b in bursts:
        r = by_ticker.get(b["ticker"])
        if r is None:
            b["claude"] = None
            b["grade"] = b["grade_mechanical"]
            continue
        prov = r.get("provenance", {})
        if prov.get("source") == grader.SOURCE_CLAUDE:
            done += 1
            claude_grade = r.get("grade")
            clamped = claude_grade if GRADE_ORDER.get(claude_grade, 9) >= GRADE_ORDER.get(b["grade_mechanical"], 9) \
                else b["grade_mechanical"]
            b["claude"] = {"agree": clamped == b["grade_mechanical"], "grade": clamped,
                           "score": r.get("score"), "reason": r.get("reason"), "key_risk": r.get("key_risk"),
                           "entry_note": r.get("entry_note"), "source": "claude",
                           "chart_seen": bool(prov.get("chart_seen")), "error": None}
            b["grade"] = clamped
        else:
            unavailable += 1
            b["claude"] = {"agree": None, "grade": None, "score": None, "reason": None, "key_risk": None,
                           "entry_note": None, "source": prov.get("source", "fallback"),
                           "chart_seen": False, "error": prov.get("error")}
            b["grade"] = b["grade_mechanical"]
    if candidates and done == 0:
        rep.problem("claude_unavailable", f"no reply for any of {len(candidates)} names")
    elif unavailable:
        rep.problem("claude_partial", f"{unavailable} of {len(candidates)} names not read")
    if usage:
        log.info("Claude usage: %s", usage)
    return {"requested": len(candidates), "done": done,
            "unavailable_reason": None if done == len(candidates) else "see problems"}


# ------------------------------------------------------------------ plans ---
def make_plans(bursts: list[dict], frames: dict[str, pd.DataFrame], account: plan.Account,
               regime: dict, open_count: int, session: date | None = None) -> tuple[list[str], list[str], dict]:
    """A plan for every A-grade burst the regime admits; the trades list in
    rank order and the cash budget over them."""
    verdict = regime.get("verdict", "green")
    multiplier = float(regime.get("size_multiplier", 1.0))
    admitted = () if verdict == "red" else (YELLOW_GRADES if verdict == "yellow" else TRADE_GRADES)
    plans = []
    for b in bursts:
        b.setdefault("plan", None)
        if b["grade"] not in admitted or b["vetoes"]:
            continue
        try:
            p = plan.burst_plan(ticker=b["ticker"], close=b["close"], low=b["low"], high=b["high"],
                                open_=b["open"], prev_close=b["prev_close"], gain_pct=b["gain_pct"] or 0.0,
                                account=account, size_multiplier=multiplier,
                                scan="dollar" if b["scan"] == "dollar" else "4pct",
                                extension_pct=b.get("extension_pct"))
        except ValueError as exc:
            log.warning("no plan for %s: %s", b["ticker"], exc)
            continue
        if session is not None:
            p["exit_schedule"] = plan.dated_schedule(p, session)
        b["plan"] = p
        plans.append(p)
    budget = plan.cash_budget(plans, account, open_positions=open_count)
    beyond = {row["ticker"] for row in budget.get("beyond", [])}
    trades = [p["ticker"] for p in plans if p.get("eligible") and p["ticker"] not in beyond]
    return trades, sorted(beyond), budget


def make_watchlist(frames: dict[str, pd.DataFrame], account: plan.Account, regime: dict,
                   uni: universe.Universe, session: date | None = None) -> dict:
    """The anticipation list with a plan per top name, in the fields the page
    prints: the company name, the quiet-day count, today's range, the box
    with its session count, and the ticket."""
    lists = watchlist.build({t: df for t, df in frames.items() if t != BENCHMARK_SYMBOL})
    multiplier = float(regime.get("size_multiplier", 1.0))
    for row in lists.get("top", []) + lists.get("also_quiet", []):
        row["name"] = uni.names.get(row["ticker"], "")
        row["quiet_days"] = row.get("narrow_range_days")
        row["range_pct"] = row.get("range_pct_today")
        box = row.get("box")
        if isinstance(box, dict) and "length" in box:
            box["sessions"] = box["length"]
    for row in lists.get("top", []):
        df = frames.get(row["ticker"])
        lows = [float(x) for x in df["Low"].iloc[-plan.STOP_LOOKBACK_SESSIONS:]] if df is not None else []
        box = row.get("box") or {}
        try:
            row["plan"] = plan.anticipation_plan(ticker=row["ticker"], close=row["close"],
                                                 box_high=box["high"], box_low=box["low"],
                                                 lows_last3=lows, account=account,
                                                 size_multiplier=multiplier)
            if session is not None:
                row["plan"]["exit_schedule"] = plan.dated_schedule(row["plan"], session)
        except (KeyError, ValueError) as exc:
            row["plan"] = None
            log.warning("no anticipation plan for %s: %s", row["ticker"], exc)
        if df is not None:
            row["series"] = series_of(df)
    counts = lists.get("counts") or {}
    counts["coiled"] = counts.get("admitted", 0)
    counts["top"], counts["also_quiet"] = len(lists.get("top", [])), len(lists.get("also_quiet", []))
    lists["counts"] = counts
    lists["instruction"] = plan.ANTICIPATION_INSTRUCTION
    return lists


# ---------------------------------------------------------------- publish ---
def et_now(now: datetime | None = None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(MARKET_TZ)


def build_rules(uni: universe.Universe) -> dict:
    """Every module's RULES, nested by family (``rules.plan.final_exit_day``),
    plus the universe's floors and identity. The digest of this block is
    ``app.rules_version``."""
    flat: dict = {}
    for block in (scans.RULES, quality.RULES, plan.RULES, watchlist.RULES, record.RULES, RULES):
        flat.update(block)
    flat.update({(k if k.startswith("breadth.") else "breadth." + k): v for k, v in breadth_rules().items()})
    flat.update({"universe.min_price": universe.MIN_PRICE, "universe.min_volume": universe.MIN_VOLUME,
                 "universe.max_discovery": universe.MAX_DISCOVERY, "universe.identity": uni.identity})
    nested: dict = {}
    for key, value in flat.items():
        family, _, name = key.partition(".")
        nested.setdefault(family, {})[name] = value
    return nested


def breadth_rules() -> dict:
    return dict(getattr(breadth, "RULES", {}))


def _strip_private(b: dict) -> dict:
    return {k: v for k, v in b.items() if not k.startswith("_")}


def load_previous(docs: Path) -> dict:
    try:
        return json.loads((docs / DATA_FILE).read_text())
    except (OSError, ValueError):
        return {}


def run_evening(*, dry_run: bool = False, tickers: list[str] | None = None,
                docs: Path = DOCS_DIR, now: datetime | None = None,
                fetch_budget: float = FETCH_BUDGET_SECONDS) -> RunReport:
    """The whole evening, start to finish. Never raises past preflight; the
    report carries the exit code."""
    rep = RunReport()
    started = time.monotonic()
    rep.stage = "preflight"
    preflight("evening", dry_run)
    account = plan.Account.from_env()
    previous = load_previous(docs)
    docs.mkdir(parents=True, exist_ok=True)
    generated = (now or datetime.now(timezone.utc)).isoformat()
    try:
        rep.stage = "universe"
        uni = universe.build(docs, explicit=tickers, now=now)
        if uni.warning:
            rep.problem("universe_cached", uni.warning)
        symbols = list(uni.symbols)
        if BENCHMARK_SYMBOL not in symbols:
            symbols.append(BENCHMARK_SYMBOL)

        rep.stage = "fetch"
        expected = expected_session(now)
        client = market_data.get_clients()
        feed = market_data.feed_from_env()
        frames, stats, fetch_seconds = fetch_universe(client, symbols, expected, feed, rep,
                                                      budget_seconds=fetch_budget, now=now)
        answered = len(frames)
        if not frames or answered / max(len(symbols), 1) < MIN_COVERAGE_FRACTION:
            raise RuntimeError(f"only {answered} of {len(symbols)} names answered: a feed outage, not a market")

        rep.stage = "session"
        state, have = session_state(frames, expected)
        if state == "outage":
            if have < MIN_COVERAGE_FRACTION and have >= CLOSED_FRACTION:
                rep.problem("coverage_thin", f"only {have:.0%} of names carry a bar for {expected}")
            elif have < CLOSED_FRACTION:
                raise RuntimeError(f"no bars for {expected} and the previous session is not carried "
                                   "either: the feed answered stale frames")
        closed = state == "closed"
        session = newest_common_session(frames) if closed else expected
        if session is None:
            raise RuntimeError("the frames carry no common session")
        stats.session = session
        fresh = market_data.apply_session_rules(frames, session, stats) if not closed else {}

        rep.stage = "breadth"
        breadth_block = breadth.snapshot({t: df for t, df in frames.items() if t != BENCHMARK_SYMBOL}, session)
        breadth_block["notes"] = breadth_notes(breadth_block)
        regime = breadth_block.get("regime", {"verdict": "green", "size_multiplier": 1.0, "reasons": []})

        rep.stage = "scan"
        bursts, measured, errors = ([], 0, 0) if closed else scan_frames(fresh, uni, rep)
        for b in bursts:
            b["grade"] = b["grade_mechanical"]

        rep.stage = "plan"
        rec = record.load(docs)
        if rec.get("problem"):
            log.warning("picks.json: %s", rec["problem"])
        open_now = record.open_plans(rec, frames, session.isoformat(), regime.get("verdict", "green"))
        held = sum(1 for o in open_now if o.get("status") in ("hold", "sell_half", "sell_into_strength", "pending"))
        # a first pass of plans sizes the stop the chart draws; the final plans come after Claude
        make_plans(bursts, fresh, account, regime, held, session)

        rep.stage = "grade"
        charts_dir = docs / CHARTS_DIR_NAME
        reads = {"requested": 0, "done": 0, "unavailable_reason": None}
        if bursts:
            system_prompt = grader_prompt()
            reads = read_charts_and_grade(bursts, fresh, rep, charts_dir, system_prompt, dry_run)
        rank(bursts)
        trades, beyond_cap, budget = make_plans(bursts, fresh, account, regime, held, session)

        rep.stage = "watchlist"
        lists = (make_watchlist(fresh, account, regime, uni, session) if not closed
                 else {"top": [], "also_quiet": [], "counts": {}, "instruction": plan.ANTICIPATION_INSTRUCTION})

        rep.stage = "record"
        if not closed and not dry_run:
            picks = [pick_of(b["plan"], "burst", b["grade"], b["score"]) for b in bursts if b["ticker"] in trades]
            picks += [pick_of(row["plan"], "anticipation", "watch", row.get("ti65"))
                      for row in lists.get("top", []) if row.get("plan") and row["plan"].get("eligible")]
            rec = record.append(rec, session.isoformat(), picks, regime.get("verdict", "green"))
        open_plans = record.open_plans(rec, frames, session.isoformat(), regime.get("verdict", "green"))
        scorecard = record.scorecard(rec, frames, session.isoformat())

        rep.stage = "publish"
        miss = report.closest_miss([_strip_private(b) for b in bursts], trades)
        keep_series = set(trades) | ({miss["ticker"]} if miss else set())
        published_bursts = []
        for b in bursts:
            row = _strip_private(b)
            row["series"] = series_of(fresh[b["ticker"]]) if b["ticker"] in keep_series else []
            row["summary"] = report.summary(row)
            published_bursts.append(row)
        graded = {key: sum(1 for b in bursts if b["grade"] == g) for key, g in GRADE_KEYS.items()}
        coverage = {"requested": stats.requested, "with_bars": stats.with_bars, "on_session": len(fresh),
                    "measured": measured, "stale": len(stats.stale), "gapped": len(stats.gapped),
                    "no_bars": len(stats.no_bars), "dropped": stats.dropped, "errors": errors,
                    "duplicate_bars": sum(stats.duplicates.values())}
        elapsed = round(time.monotonic() - started, 1)
        run_block = {
            "session": session.isoformat(), "session_state": "closed" if closed else "open",
            "expected_session": expected.isoformat(),
            "status": "closed" if closed and rep.status == "ok" else rep.status, "problems": list(rep.problems),
            "dry_run": dry_run, "model": grader.MODEL, "feed": getattr(feed, "value", str(feed)),
            "universe": {"label": uni.label, "size": len(uni.symbols), "source": uni.source,
                         "fetched_at": uni.fetched_at, "identity": uni.identity},
            "coverage": coverage, "bursts": len(bursts), "graded": graded, "reads": reads,
            "email": "skipped", "published_at": generated,
            "run_id": os.environ.get("GITHUB_RUN_ID_FOR_RECORD") or None,
            "elapsed_seconds": elapsed, "fetch_seconds": round(fetch_seconds, 1),
            "rules_version": RULES_VERSION_NOTE, "type": "evening",
        }
        nights = record.nights(previous.get("nights"), {"session": session.isoformat(),
                                                        "status": "closed" if closed else rep.status,
                                                        "published_at": generated})
        account_block = account.to_dict() | {"notes": plan.account_notes(account)}
        data = report.build(run_block, account_block, build_rules(uni), breadth_block, published_bursts,
                            trades, beyond_cap, budget, lists, open_plans, scorecard, nights, generated)
        report.write(data, docs / DATA_FILE)
        if not dry_run:
            record.save(rec, docs)
        rep.published = True
        log.info("published %s: %s", session, data["cover"]["h1"])

        rep.stage = "email"
        if dry_run or not delivery_enabled():
            data["run"]["email"] = "skipped"
        else:
            try:
                report.send_digest(data)
                data["run"]["email"] = "delivered"
            except Exception as exc:  # noqa: BLE001
                rep.problem("email_failed", f"{type(exc).__name__}: {exc}")
                data["run"]["email"] = "failed"
                data["run"]["problems"] = list(rep.problems)
                data["run"]["status"] = rep.status
                report.write(data, docs / DATA_FILE)
                rep.fail(exc)
                return rep
        data["run"]["status"] = "closed" if closed and rep.status == "ok" else rep.status
        data["run"]["problems"] = list(rep.problems)
        report.write(data, docs / DATA_FILE)
        return rep
    except PreflightError:
        raise
    except Exception as exc:  # noqa: BLE001
        rep.fail(exc)
        if not rep.published:
            notify_failure(rep, dry_run, expected_session(now))
        return rep


def pick_of(p: dict, kind: str, grade: str, score) -> dict:
    """The slim pick the record keeps for a published plan: what the walk
    reads (the zone or the trigger, the stop, the shares) and what the page
    draws beside it (the targets, the ticket)."""
    return {"ticker": p["ticker"], "kind": kind, "grade": grade, "score": score,
            "entry_ref": p["entry_ref"], "entry_low": p.get("entry_low"), "entry_high": p.get("entry_high"),
            "trigger": p.get("trigger"), "limit": p.get("limit"),
            "stop": p["stop"], "shares": p["shares"], "targets": p.get("targets"),
            "order_json": p.get("order_json")}


def breadth_notes(block: dict) -> list[dict]:
    """His readings of the Market Monitor columns, keyed the way the page's
    fact cards look them up; every number is the archived, scaled threshold."""
    notes = []
    thresholds = (block.get("regime") or {}).get("thresholds", {})
    hot, oversold = thresholds.get("up50_month_hot"), thresholds.get("down25_quarter_oversold")
    yellow = thresholds.get("ratio_10d_yellow")
    if yellow is not None:
        notes.append({"key": "ratio_10d", "text": f"a 10-day ratio below {yellow:g} is not an ideal time for swing longs"})
    if hot is not None:
        notes.append({"key": "up50_month", "text": f"more than {hot:g} names up 50% in a month is froth; a pullback usually follows"})
    if oversold is not None:
        notes.append({"key": "down25_quarter", "text": f"fewer than {oversold:g} names down 25% in a quarter is an oversold extreme; bounces follow in one to six weeks"})
    notes.append({"key": "pct_above_40ma", "text": "T2108: under 20% is washed out, over 80% is stretched"})
    return notes


def grader_prompt() -> str:
    return (Path(__file__).resolve().parent.parent / "knowledge" / "strategy.md").read_text()


def notify_failure(rep: RunReport, dry_run: bool, expected: date) -> None:
    if dry_run or not delivery_enabled():
        log.error("DRY RUN or delivery off -- not mailing the failure notice")
        return
    if [n for n in report.REQUIRED_ENV if not os.environ.get(n, "").strip()]:
        log.error("cannot mail the failure notice: delivery keys are missing")
        return
    try:
        problems = list(rep.problems) + [report.problem(rep.stage, "coverage_thin", rep.failure or "run failed")]
        report.send_failure_notice("evening", problems, None, expected_session=expected.isoformat())
    except Exception as exc:  # noqa: BLE001
        log.error("the failure notice could not be sent either: %s", exc)


# --------------------------------------------------------------- intraday ---
def snapshot_rows(client, symbols: list[str]) -> dict[str, dict]:
    """Price from IEX (real time on the free plan) and the consolidated
    partial-day bar from the delayed SIP feed, keyed by symbol."""
    from alpaca.data.enums import DataFeed
    from alpaca.data.requests import StockSnapshotRequest

    out: dict[str, dict] = {}
    if not symbols:
        return out
    live = client.get_stock_snapshot(StockSnapshotRequest(symbol_or_symbols=symbols, feed=DataFeed.IEX))
    delayed = client.get_stock_snapshot(StockSnapshotRequest(symbol_or_symbols=symbols, feed=DataFeed.DELAYED_SIP))
    for symbol in symbols:
        a, b = live.get(symbol), delayed.get(symbol)
        trade = getattr(a, "latest_trade", None) if a else None
        daily = getattr(b, "daily_bar", None) if b else None
        prev = getattr(b, "previous_daily_bar", None) if b else None
        out[symbol] = {
            "last": _num(getattr(trade, "price", None)),
            "open": _num(getattr(daily, "open", None)), "high": _num(getattr(daily, "high", None)),
            "low": _num(getattr(daily, "low", None)), "partial_volume": _num(getattr(daily, "volume", None)),
            "prev_close": _num(getattr(prev, "close", None)), "prev_volume": _num(getattr(prev, "volume", None)),
        }
    return out


def intraday_rows(data: dict, snaps: dict[str, dict]) -> list[dict]:
    rows = []
    watch = {row["ticker"]: row for row in (data.get("watchlist") or {}).get("top", [])}
    bursts = {b["ticker"]: b for b in data.get("bursts", [])}
    for ticker in list(watch) + [t for t in data.get("trades", []) if t not in watch]:
        snap = snaps.get(ticker) or {}
        src = watch.get(ticker) or bursts.get(ticker) or {}
        p = src.get("plan") or {}
        level = p.get("trigger") if ticker in watch else p.get("entry_high")
        last, prev_close = snap.get("last"), snap.get("prev_close")
        pv, prev_v = snap.get("partial_volume"), snap.get("prev_volume")
        pct = round(100 * (last / prev_close - 1), 2) if last and prev_close else None
        if pv is not None and prev_v:
            volume_state = "confirmed" if pv > prev_v else "not_yet"
        else:
            volume_state = "unknown"
        rows.append({"ticker": ticker, "kind": "anticipation" if ticker in watch else "burst",
                     "last": last, "prev_close": prev_close, "pct_from_prev_close": pct,
                     "level": level, "above_level": bool(last and level and last >= level),
                     "partial_volume": pv, "prev_volume": prev_v, "volume_state": volume_state})
    return rows


def run_intraday(*, docs: Path = DOCS_DIR, now: datetime | None = None, client=None) -> RunReport:
    rep = RunReport()
    rep.stage = "preflight"
    preflight("intraday", dry_run=False)
    data = load_previous(docs)
    if not data:
        rep.fail(RuntimeError("docs/data.json is missing: nothing to check"))
        return rep
    try:
        rep.stage = "snapshots"
        client = client or market_data.get_clients()
        symbols = [r["ticker"] for r in (data.get("watchlist") or {}).get("top", [])] + \
                  [t for t in data.get("trades", [])]
        symbols = list(dict.fromkeys(symbols))
        rows = intraday_rows(data, snapshot_rows(client, symbols))
        live = {"as_of": (now or datetime.now(timezone.utc)).isoformat(), "session": data.get("run", {}).get("session"),
                "rows": rows}
        (docs / LIVE_FILE).write_text(json.dumps(live, indent=1))
        rep.published = True
        rep.stage = "email"
        confirmed = [r for r in rows if r["above_level"] and r["volume_state"] == "confirmed"]
        if confirmed and delivery_enabled():
            body = "".join(f"<p><b>{report.esc(r['ticker'])}</b> {report.esc(r['pct_from_prev_close'])}% "
                           f"above its level {report.esc(r['level'])} on volume already past yesterday's.</p>"
                           for r in confirmed)
            report.deliver(f"Breakout in progress — {', '.join(r['ticker'] for r in confirmed)}", body)
        return rep
    except Exception as exc:  # noqa: BLE001
        rep.fail(exc)
        return rep


# ------------------------------------------------------------------- main ---
def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(description="SpicyStock: the evening run or the intraday check")
    p.add_argument("run_type", choices=MODES)
    p.add_argument("--dry-run", action="store_true", help="mail nothing (the record is still written)")
    p.add_argument("--tickers", help="comma-separated symbols instead of the directory (smoke tests)")
    args = p.parse_args(argv)
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()] if args.tickers else None
    try:
        rep = run_evening(dry_run=args.dry_run, tickers=tickers) if args.run_type == "evening" \
            else run_intraday()
    except PreflightError as exc:
        log.error("%s", exc)
        return EXIT_FAILED
    code = rep.exit_code()
    log.info("exit %d (%s)", code, rep.status)
    return code


if __name__ == "__main__":
    sys.exit(main())
