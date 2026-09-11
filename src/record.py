"""The record: what the published plans did, from bars alone.

``docs/picks.json`` holds every plan the evening run published -- the ticker,
the session, the entry zone, the stop, the shares and the ticket -- and
nothing about what the reader did with it. Two things are read back off it
every night, both computed from the bars the run already fetched:

* ``open_plans()``: every pick from the last ``OPEN_PLAN_SESSIONS`` sessions
  walked through ``plan.follow()`` -- the fill rule the ticket implies, then
  his exit rules in order -- so the page can say "day 3: sell half" without
  a human having typed a fill.
* ``scorecard()``: the same walk over the last ``SCORECARD_SESSIONS`` sessions
  of picks, settled at day 5, in R (the published stop is one R) with the
  halves weighted, beside SPY over the same days as one comparison line. It
  is the rules' record, not the reader's, and it is unreadable as a rate
  below ``SCORECARD_MIN_PLANS`` -- the page prints the count and says so.

Nothing here is a strategy number except ``OPEN_PLAN_SESSIONS``, which is
his five-session hold. Every price a walk reads is the plan's own.
"""
from __future__ import annotations

import calendar
import json
import logging
import math
import os
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from src import plan

log = logging.getLogger("spicystock.record")

PICKS_FILE = "picks.json"
SCHEMA_VERSION = 1
OPEN_PLAN_SESSIONS = plan.FINAL_EXIT_DAY   # (B) a pick is followed for his five-session hold
SCORECARD_SESSIONS = 60                    # (P) picks older than this leave the scorecard
SCORECARD_MIN_PLANS = 20                   # (P) below this the page prints the count, never a rate
NIGHTS_KEPT = 20                           # (P) evenings kept for the reliability row (the page shows 14)
MAX_PICKS = 260                            # (P) picks kept in the file, newest first: a year of nights
BENCHMARK = "SPY"                          # the one comparison line
KINDS = plan.KINDS
SETTLED = ("stopped", "exit", "expired")   # the walk ended; the plan has a result
NOT_FILLED = "not_filled"                  # the ticket never filled: no result, no R
UNREADABLE = "unreadable"                  # a later bar the walk refused

RULES: dict[str, Any] = {
    "record.open_plan_sessions": OPEN_PLAN_SESSIONS,
    "record.scorecard_sessions": SCORECARD_SESSIONS,
    "record.scorecard_min_plans": SCORECARD_MIN_PLANS,
    "record.nights_kept": NIGHTS_KEPT,
    "record.max_picks": MAX_PICKS,
    "record.benchmark": BENCHMARK,
}

SCORECARD_NOTE = ("from bars alone: filled at the next open inside the zone (or at the trigger when the "
                  "day reaches it), the published stop is one R, halves weighted, settled by day "
                  f"{plan.FINAL_EXIT_DAY}")

#: The keys a pick must carry to be walked; anything else it carries is kept.
PICK_KEYS = ("ticker", "date", "kind", "entry_ref", "stop", "shares")


# ------------------------------------------------------------------ file ----
def empty() -> dict:
    return {"schema_version": SCHEMA_VERSION, "picks": []}


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def pick_problem(pick: Any) -> str | None:
    """Why a stored pick cannot be walked, or None. Shape-checked one level
    in: every key the walk indexes into is held to the type it reads."""
    if not isinstance(pick, dict):
        return "a pick is not an object"
    missing = [k for k in PICK_KEYS if k not in pick]
    if missing:
        return f"a pick lacks {', '.join(missing)}"
    if not isinstance(pick["ticker"], str) or not pick["ticker"]:
        return "a pick's ticker is not a symbol"
    if not isinstance(pick["date"], str) or _parse_date(pick["date"]) is None:
        return f"{pick['ticker']}: the pick's date is not YYYY-MM-DD"
    if pick["kind"] not in KINDS:
        return f"{pick['ticker']}: kind {pick['kind']!r} is not one of {KINDS}"
    for key in ("entry_ref", "stop"):
        if not _finite(pick[key]) or pick[key] <= 0:
            return f"{pick['ticker']}: {key} is not a positive price"
    if pick["entry_ref"] <= pick["stop"]:
        return f"{pick['ticker']}: entry_ref {pick['entry_ref']} is not above the stop {pick['stop']}"
    shares = pick["shares"]
    if isinstance(shares, bool) or not isinstance(shares, int) or shares < 0:
        return f"{pick['ticker']}: shares is not a whole number"
    for key in ("entry_low", "entry_high", "limit", "trigger"):
        if key in pick and pick[key] is not None and not _finite(pick[key]):
            return f"{pick['ticker']}: {key} is not a number"
    return None


def load(docs: Path) -> dict:
    """The record off disk. A missing file is an empty record; an unreadable
    one is set aside beside itself (never overwritten) and reported in
    ``problem``; a malformed pick is dropped and counted there too."""
    path = Path(docs) / PICKS_FILE
    if not path.exists():
        return empty()
    try:
        raw = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        aside = set_aside(path)
        rec = empty()
        rec["problem"] = f"{PICKS_FILE} could not be read ({type(exc).__name__}); set aside as {aside.name}"
        return rec
    if not isinstance(raw, dict) or not isinstance(raw.get("picks"), list):
        aside = set_aside(path)
        rec = empty()
        rec["problem"] = f"{PICKS_FILE} is not a record with a picks list; set aside as {aside.name}"
        return rec
    kept, dropped = [], []
    for pick in raw["picks"]:
        problem = pick_problem(pick)
        if problem is None:
            kept.append(pick)
        else:
            dropped.append(problem)
    rec = {"schema_version": SCHEMA_VERSION, "picks": kept}
    if dropped:
        rec["problem"] = f"{len(dropped)} malformed pick(s) dropped: {dropped[0]}"
    return rec


def set_aside(path: Path) -> Path:
    """Rename an unreadable file to ``<name>.<stamp>.unreadable`` so the
    night can go on without destroying what it could not read."""
    aside = path.with_name(f"{path.name}.{time.strftime('%Y%m%dT%H%M%S')}.unreadable")
    os.replace(path, aside)
    log.error("%s could not be read; set aside as %s", path.name, aside.name)
    return aside


def save(rec: dict, docs: Path) -> Path:
    """Write the record atomically; ``problem`` is a fact about the load and
    is not stored."""
    path = Path(docs) / PICKS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"schema_version": SCHEMA_VERSION, "picks": list(rec.get("picks", []))}
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(json.dumps(body, indent=1, allow_nan=False) + "\n")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()
    return path


def append(rec: dict, session: str, picks: list[dict], regime: str = "green") -> dict:
    """The record with tonight's picks added, each stamped with the session
    and the regime. A pick for the same session and ticker replaces the
    earlier one (a re-run of one night is one night). The newest
    ``MAX_PICKS`` are kept."""
    if _parse_date(session) is None:
        raise ValueError(f"session must be YYYY-MM-DD, got {session!r}")
    stamped = []
    for pick in picks:
        row = {**pick, "date": session, "regime": regime}
        problem = pick_problem(row)
        if problem:
            raise ValueError(f"refusing to record a pick the walk could not read: {problem}")
        stamped.append(row)
    tonight = {(p["date"], p["ticker"]) for p in stamped}
    kept = [p for p in rec.get("picks", []) if (p["date"], p["ticker"]) not in tonight] + stamped
    kept.sort(key=lambda p: (p["date"], p["ticker"]))
    return {"schema_version": SCHEMA_VERSION, "picks": kept[-MAX_PICKS:]}


# ------------------------------------------------------------ the walk -----
def _parse_date(text: Any) -> date | None:
    if not isinstance(text, str):
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _bar_date(stamp: Any) -> date | None:
    try:
        ts = pd.Timestamp(stamp)
    except (TypeError, ValueError):
        return None
    if pd.isna(ts):
        return None
    return ts.date()


def later_bars(df: pd.DataFrame | None, after: str, through: str | None = None) -> list[dict]:
    """The sessions after ``after`` (and through ``through``, if given) as
    the ``{date, o, h, l, c}`` rows the walk reads, oldest first. A bar with
    a missing price is left out, which the walk then reports as a hole
    rather than reading the next bar in its place."""
    start, end = _parse_date(after), _parse_date(through) if through else None
    if df is None or start is None or not len(df):
        return []
    rows: list[dict] = []
    for stamp, row in df.iterrows():
        d = _bar_date(stamp)
        if d is None or d <= start or (end is not None and d > end):
            continue
        bar = {}
        for key, col in (("o", "Open"), ("h", "High"), ("l", "Low"), ("c", "Close")):
            try:
                value = float(row[col])
            except (KeyError, TypeError, ValueError):
                value = math.nan
            bar[key] = value
        if not all(math.isfinite(v) for v in bar.values()):
            continue
        bar["date"] = d.isoformat()
        rows.append(bar)
    rows.sort(key=lambda b: b["date"])
    return rows


def fill(pick: dict, bar: dict) -> tuple[str, float | None, str]:
    """What the ticket does on its first session, from that bar alone.

    A burst ticket is a buy stop-limit: trigger ``entry_ref`` (the burst
    close), limit ``entry_high``; the plan says to skip an open under
    ``entry_low``. So: an open above the limit never fills (the gap ate it);
    an open under the skip line is skipped; an open at or above the trigger
    fills at the open; an open between the skip line and the trigger fills
    at the trigger if the day trades up through it, else the day order
    expires. An anticipation ticket is the same shape with ``trigger`` and
    ``limit``, and no skip line.
    Returns ``(status, price, note)``: ``filled`` with the price, or
    ``not_filled`` with why.
    """
    o, h = bar["o"], bar["h"]
    if pick.get("kind") == "anticipation":
        trigger, limit = float(pick.get("trigger") or pick["entry_ref"]), pick.get("limit")
        if limit is not None and o > float(limit):
            return NOT_FILLED, None, f"opened at {plan._usd(o)}, above the {plan._usd(float(limit))} limit: not filled"
        if o >= trigger:
            return "filled", o, f"filled at the open, {plan._usd(o)}"
        if h >= trigger:
            return "filled", trigger, f"filled at the trigger, {plan._usd(trigger)}"
        return NOT_FILLED, None, (f"never reached the {plan._usd(trigger)} trigger (high {plan._usd(h)}): "
                                  "the day order expired")
    trigger = float(pick["entry_ref"])
    low, high = pick.get("entry_low"), pick.get("entry_high")
    if high is not None and o > float(high):
        return NOT_FILLED, None, f"opened at {plan._usd(o)}, above the {plan._usd(float(high))} limit: the gap ate the trade"
    if low is not None and o < float(low):
        return NOT_FILLED, None, f"opened at {plan._usd(o)}, under the {plan._usd(float(low))} skip line: the burst was failing"
    if o >= trigger:
        return "filled", o, f"filled at the open, {plan._usd(o)}"
    if h >= trigger:
        return "filled", trigger, f"filled at the trigger, {plan._usd(trigger)}"
    return NOT_FILLED, None, (f"never reached the {plan._usd(trigger)} trigger (high {plan._usd(h)}): "
                              "the day order expired")


def replay(pick: dict, bars: list[dict], regime: str = "green") -> dict:
    """One pick walked over its later bars: the fill rule, then
    ``plan.follow()`` from the fill price. The row carries the published
    stop and targets beside the walk's own numbers, so the page can draw
    stop, entry and aim on one scale."""
    base = {"ticker": pick["ticker"], "kind": pick.get("kind", "burst"), "picked": pick["date"],
            "grade": pick.get("grade"), "stop": pick["stop"], "targets": pick.get("targets"),
            "fill": None, "sessions": len(bars)}
    if not bars:
        walk = plan.follow(pick, [], regime)
        return {**walk, **base, "day": 0}
    status, price, note = fill(pick, bars[0])
    if status == NOT_FILLED:
        first = bars[0]
        return {**base, "day": 1, "status": NOT_FILLED, "fill": note,
                "instruction": f"Day 1 ({first['date']}): {note}. Nothing to hold.",
                "events": [{"day": 1, "date": first["date"], "event": NOT_FILLED, "price": first["o"]}],
                "regime": regime, "entry_ref": pick["entry_ref"], "shares": pick.get("shares", 0),
                "current_stop": pick["stop"], "last_close": first["c"], "last_date": first["date"],
                "unrealised_pct": None, "exit_price": None, "result_pct": None, "half_sold": False}
    filled = {**pick, "entry_ref": price}
    try:
        walk = plan.follow(filled, bars, regime)
    except ValueError as exc:
        return {**base, "day": len(bars), "status": UNREADABLE, "fill": note,
                "instruction": f"A later bar could not be read ({exc}); follow the plan's own stop.",
                "events": [], "regime": regime, "entry_ref": price, "shares": pick.get("shares", 0),
                "current_stop": pick["stop"], "last_close": None, "last_date": None,
                "unrealised_pct": None, "exit_price": None, "result_pct": None, "half_sold": False}
    return {**walk, **base, "fill": note}


def r_multiple(row: dict, stop: float) -> float | None:
    """The result in R: the published stop is one R, and a half sold at
    +8% (or at day 3) is half the position at that price. None until the
    walk has an exit price."""
    entry, exit_price = row.get("entry_ref"), row.get("exit_price")
    if not _finite(entry) or not _finite(exit_price) or not _finite(stop) or entry <= stop:
        return None
    risk = entry - stop
    if row.get("half_sold"):
        half = next((e.get("price") for e in row.get("events", []) if e.get("event") == "sell_half"), None)
        if _finite(half):
            return round(0.5 * (half - entry) / risk + 0.5 * (exit_price - entry) / risk, 2)
    return round((exit_price - entry) / risk, 2)


# ------------------------------------------------------------- sessions ----
def sessions_before(frames: dict[str, pd.DataFrame], session: str, n: int) -> list[str]:
    """The ``n`` sessions before ``session`` (exclusive), oldest first: off
    the frames' own calendar when they carry one, else weekdays."""
    from src import market_data
    end = _parse_date(session)
    if end is None:
        return []
    observed = [d for d in market_data.session_calendar(frames) if d < end] if frames else []
    if len(observed) >= n:
        return [d.isoformat() for d in observed[-n:]]
    out: list[date] = []
    d = end
    while len(out) < n:
        d = d - timedelta(days=1)
        if d.weekday() < calendar.SATURDAY:
            out.insert(0, d)
    return [d.isoformat() for d in out]


def open_plans(rec: dict, frames: dict[str, pd.DataFrame], session: str, regime: str = "green") -> list[dict]:
    """Every pick from the last ``OPEN_PLAN_SESSIONS`` sessions before
    ``session``, walked through ``session``'s bars, oldest pick first (the
    one nearest its day-5 exit is the most urgent). A pick whose name the
    night did not fetch is returned with no bars and says so."""
    window = set(sessions_before(frames, session, OPEN_PLAN_SESSIONS))
    rows = []
    for pick in rec.get("picks", []):
        if pick["date"] not in window:
            continue
        df = frames.get(pick["ticker"])
        bars = later_bars(df, pick["date"], session)
        row = replay(pick, bars, regime)
        if df is None:
            row["instruction"] = (f"No bars for {pick['ticker']} tonight; follow the plan's own stop at "
                                  f"{plan._usd(pick['stop'])} and its day-{plan.FINAL_EXIT_DAY} exit.")
            row["status"] = "unmeasured"
        rows.append(row)
    rows.sort(key=lambda r: (r["picked"], r["ticker"]))
    return rows


def _spy_move(spy: pd.DataFrame | None, entry_date: str, exit_date: str) -> float | None:
    """SPY from the open of ``entry_date`` to the close of ``exit_date``, in
    percent, when both bars are there."""
    if spy is None:
        return None
    bars = {b["date"]: b for b in later_bars(spy, "1900-01-01", exit_date)}
    a, b = bars.get(entry_date), bars.get(exit_date)
    if not a or not b or a["o"] <= 0:
        return None
    return 100 * (b["c"] / a["o"] - 1)


def scorecard(rec: dict, frames: dict[str, pd.DataFrame], session: str) -> dict:
    """The rules' record over the last ``SCORECARD_SESSIONS`` sessions of
    picks: how many plans, how many filled, wins and losses among the
    settled ones, average and summed R, and SPY over the same days. Every
    count is a count; the rate is None until ``SCORECARD_MIN_PLANS`` plans
    have settled, and the page prints the count either way."""
    window = set(sessions_before(frames, session, SCORECARD_SESSIONS))
    spy = frames.get(BENCHMARK)
    plans = filled = wins = losses = settled = open_now = 0
    rs: list[float] = []
    spy_moves: list[float] = []
    for pick in rec.get("picks", []):
        if pick["date"] not in window:
            continue
        df = frames.get(pick["ticker"])
        if df is None:
            continue
        bars = later_bars(df, pick["date"], session)
        if not bars:
            continue
        row = replay(pick, bars, "green")
        plans += 1
        if row["status"] in (NOT_FILLED, UNREADABLE):
            continue
        filled += 1
        if row["status"] not in SETTLED:
            open_now += 1
            continue
        r = r_multiple(row, pick["stop"])
        if r is None:
            continue
        settled += 1
        rs.append(r)
        if r > 0:
            wins += 1
        elif r < 0:
            losses += 1
        exit_date = next((e["date"] for e in reversed(row.get("events", [])) if e.get("price") is not None), None)
        move = _spy_move(spy, bars[0]["date"], exit_date or bars[-1]["date"])
        if move is not None:
            spy_moves.append(move)
    readable = settled >= SCORECARD_MIN_PLANS
    return {
        "plans": plans, "filled": filled, "settled": settled, "open": open_now,
        "wins": wins, "losses": losses,
        "win_rate": round(wins / settled, 3) if readable and settled else None,
        "avg_r": round(math.fsum(rs) / settled, 2) if readable and settled else None,
        "sum_r": round(math.fsum(rs), 2) if settled else None,
        "spy_avg_pct": round(math.fsum(spy_moves) / len(spy_moves), 2) if readable and spy_moves else None,
        "min_read": SCORECARD_MIN_PLANS, "readable": readable,
        "sessions": SCORECARD_SESSIONS, "note": SCORECARD_NOTE,
    }


# --------------------------------------------------------------- nights ----
def nights(previous: Any, entry: dict) -> list[dict]:
    """The reliability row: the last ``NIGHTS_KEPT`` evenings by session,
    each ``{session, status, published_at}``. Tonight replaces an earlier
    entry for the same session; a malformed earlier entry is dropped."""
    kept: dict[str, dict] = {}
    for row in previous if isinstance(previous, list) else []:
        if isinstance(row, dict) and _parse_date(row.get("session")) and isinstance(row.get("status"), str):
            kept[row["session"]] = {"session": row["session"], "status": row["status"],
                                    "published_at": row.get("published_at")}
    if not _parse_date(entry.get("session")):
        raise ValueError(f"a night needs a session, got {entry!r}")
    kept[entry["session"]] = {"session": entry["session"], "status": entry.get("status", "ok"),
                              "published_at": entry.get("published_at")}
    rows = [kept[k] for k in sorted(kept)]
    return rows[-NIGHTS_KEPT:]
