"""The record: what the published plans did, from bars alone.

``docs/picks.json`` holds every plan the evening run published -- the ticker,
the session, the entry zone, the stop, the shares and the ticket -- and
nothing about what the reader did with it. Two things are read back off it
every night, both computed from the bars the run already fetched:

* ``open_plans()``: every pick from the last ``OPEN_PLAN_SESSIONS`` sessions
  walked through ``plan.follow()`` -- the fill rule the ticket implies, then
  his exit rules in order -- so the page can say "day 3: sell half" without
  a human having typed a fill. It is a model of the published plan; nothing
  here knows what the reader holds.
* ``scorecard()``: the same walk over the last ``SCORECARD_SESSIONS`` sessions
  of picks, settled at day 5, in R (the published stop is one R on the whole
  position, every sale weighted by the whole shares it sold), beside SPY over
  the same days as one comparison line. It is the rules' record, not the
  reader's, and it is unreadable as a rate below ``SCORECARD_MIN_PLANS`` --
  the page prints the count and says so.

What a daily bar can and cannot establish is the whole fill rule
(``fill()``). It CAN say a stop-limit filled when the open sits at or over
the trigger and at or under the limit: the fill is the open, inside the
plan's window. It CANNOT say when a day that opened under the trigger
crossed it, whether an open past the limit or under the skip line later
filled the resting order, or whether a fill-day low under the stop came
before or after the fill. Those are ``UNCERTAIN`` with a reason code from
``UNCERTAIN_REASONS``: no fill is booked, no R is scored, the plan is not
read as held, not held, or freed, and the scorecard counts it by reason.

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
NOT_FILLED = "not_filled"                  # the ticket could not have filled: no result, no R
UNREADABLE = "unreadable"                  # a later bar the walk refused
UNCERTAIN = "uncertain"                    # the bars cannot say whether, when or in what order the ticket filled
#: (P) the one fill a daily bar can establish: the open, at or over the trigger
#: and at or under the limit. Everything else the bar suggests is uncertain.
KNOWN_FILL = "open_inside_zone"
#: Why a fill is uncertain, one code each; ``UNCERTAIN_WORDS`` is the short
#: phrase the page and the mail print beside a count.
UNCERTAIN_REASONS = ("trigger_timing", "stop_sequence", "open_above_limit", "open_below_skip")
UNCERTAIN_WORDS = {
    "trigger_timing": "reached the trigger after the open, at a time the bar cannot give",
    "stop_sequence": "reached the trigger with the day's low under the stop: fill and stop in unknown order",
    "open_above_limit": "opened above the limit, which the plan skips, then traded back under it",
    "open_below_skip": "opened under the skip line, which the plan skips, then recovered through the trigger",
}

RULES: dict[str, Any] = {
    "record.open_plan_sessions": OPEN_PLAN_SESSIONS,
    "record.scorecard_sessions": SCORECARD_SESSIONS,
    "record.scorecard_min_plans": SCORECARD_MIN_PLANS,
    "record.nights_kept": NIGHTS_KEPT,
    "record.max_picks": MAX_PICKS,
    "record.benchmark": BENCHMARK,
    "record.known_fill": KNOWN_FILL,
}

SCORECARD_NOTE = ("from bars alone, a model and not a brokerage record: a fill is booked only at the next "
                  "open at or over the trigger and at or under the limit; a day that reaches the trigger after "
                  "the open, an open past the limit or under the skip line that could still have filled, and a "
                  "fill-day low under the stop are uncertain, counted here and in no rate; the published stop "
                  "is one R on the whole position, every sale weighted by the whole shares it sold, settled by "
                  f"day {plan.FINAL_EXIT_DAY}")

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
    low, high = pick.get("entry_low"), pick.get("entry_high")
    if low is not None and high is not None and not low <= pick["entry_ref"] <= high:
        return f"{pick['ticker']}: entry_ref {pick['entry_ref']} is outside its zone {low}-{high}"
    trigger, limit = pick.get("trigger"), pick.get("limit")
    if trigger is not None and trigger <= pick["stop"]:
        return f"{pick['ticker']}: trigger {trigger} is not above the stop {pick['stop']}"
    if trigger is not None and limit is not None and limit < trigger:
        return f"{pick['ticker']}: limit {limit} is under the trigger {trigger}"
    return None


def load(docs: Path) -> dict:
    """The record off disk. A missing file is an empty record, and so is the
    committed fixture (a fresh clone's placeholder, marked ``fixture``); an
    unreadable one is set aside beside itself (never overwritten) and
    reported in ``problem``; a malformed pick is dropped and counted there too."""
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
    if raw.get("fixture"):
        # the committed placeholder a fresh clone carries: invented picks that
        # must never be walked as history. Not set aside -- save() replaces it.
        log.info("%s is the %s fixture; starting a fresh record", PICKS_FILE, raw["fixture"])
        return empty()
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


def fill(pick: dict, bar: dict) -> tuple[str, float | None, str, str | None]:
    """What the ticket did on its first session, as far as that daily bar
    can say.

    A burst ticket is a buy stop-limit: trigger ``entry_ref`` (the burst
    close), limit ``entry_high``; the plan says to skip an open under
    ``entry_low``. An anticipation ticket is the same shape with ``trigger``
    and ``limit`` and no skip line. The bar establishes exactly one fill,
    ``KNOWN_FILL``: an open at or over the trigger and at or under the limit
    fills at the open, inside the plan's window. It rules a fill out when
    the day never reached the trigger, or opened above the limit and never
    traded back under it. Everything else is ``UNCERTAIN`` with a reason
    from ``UNCERTAIN_REASONS``: a day that opened under the trigger and
    reached it (the crossing time is unknown, and the plan's entry is the
    first 30 minutes), the same with the low at or under the stop (the order
    of fill and stop is unknown), an open above the limit that traded back
    under it (a resting order does not fill at that open but stays live),
    and an open under the skip line that recovered through the trigger (the
    plan skips it; a resting order would still have triggered). The
    strategy's "would skip" is stated as the plan's, never as a broker's
    rejection.
    Returns ``(status, price, note, reason)``; ``price`` and ``reason`` are
    each None unless the status calls for them.
    """
    o, h, l = bar["o"], bar["h"], bar["l"]
    stop = float(pick["stop"])
    if pick.get("kind") == "anticipation":
        trigger, limit, skip = float(pick.get("trigger") or pick["entry_ref"]), pick.get("limit"), None
    else:
        trigger, limit, skip = float(pick["entry_ref"]), pick.get("entry_high"), pick.get("entry_low")
    usd = plan._usd
    if limit is not None and o > float(limit):
        limit = float(limit)
        if l <= limit:
            return UNCERTAIN, None, (f"opened at {usd(o)}, above the {usd(limit)} limit, which the plan says to "
                                     f"skip; a resting stop-limit does not fill at that open but stays live, and "
                                     f"the day traded back under {usd(limit)} (low {usd(l)}), so it may have filled "
                                     f"later at a time the bar cannot give"), "open_above_limit"
        return NOT_FILLED, None, (f"opened at {usd(o)}, above the {usd(limit)} limit, and never traded back under "
                                  f"it (low {usd(l)}): the limit could not fill"), None
    if skip is not None and o < float(skip):
        skip = float(skip)
        if h >= trigger:
            return UNCERTAIN, None, (f"opened at {usd(o)}, under the {usd(skip)} skip line: the plan calls the burst "
                                     f"failing and places no order, but a resting order would still have triggered "
                                     f"when the day recovered through {usd(trigger)} (high {usd(h)}), at a time the "
                                     f"bar cannot give"), "open_below_skip"
        return NOT_FILLED, None, (f"opened at {usd(o)}, under the {usd(skip)} skip line, and never reached the "
                                  f"{usd(trigger)} trigger (high {usd(h)}): not filled"), None
    if o >= trigger:
        return "filled", o, f"filled at the open, {usd(o)}", None
    if h >= trigger:
        if l <= stop:
            return UNCERTAIN, None, (f"opened at {usd(o)}, under the {usd(trigger)} trigger; the day reached it "
                                     f"(high {usd(h)}) and its low {usd(l)} sat at or under the {usd(stop)} stop: "
                                     f"the bar cannot say whether the fill came inside the {plan.ENTRY_WINDOW}, "
                                     f"nor whether the low came before or after it"), "stop_sequence"
        return UNCERTAIN, None, (f"opened at {usd(o)}, under the {usd(trigger)} trigger; the day reached it "
                                 f"(high {usd(h)}) at a time the bar cannot give, and the plan's entry is the "
                                 f"{plan.ENTRY_WINDOW}"), "trigger_timing"
    return NOT_FILLED, None, (f"never reached the {usd(trigger)} trigger (high {usd(h)}): the day order "
                              "expired"), None


def _no_walk(base: dict, pick: dict, first: dict | None, *, day: int, status: str, fill_note: str | None,
             instruction: str, events: list[dict], regime: str, uncertainty: str | None = None) -> dict:
    """A row for a plan the model did not walk: not filled, uncertain, or a
    bar it could not read. The published numbers are carried; nothing is
    booked."""
    return {**base, "day": day, "status": status, "fill": fill_note, "uncertainty": uncertainty,
            "instruction": instruction, "events": events, "regime": regime,
            "entry_ref": pick["entry_ref"], "shares": pick.get("shares", 0), "current_stop": pick["stop"],
            "last_close": first["c"] if first else None, "last_date": first["date"] if first else None,
            "unrealised_pct": None, "exit_price": None, "result_pct": None, "half_sold": False,
            "sold": 0, "remaining": pick.get("shares", 0)}


#: What an uncertain plan's row tells a reader who took it: the plan's own
#: stop and the two dated exits, since the model books nothing for it.
IF_TAKEN = ("The model books no fill. If you took this plan: the sell stop is {stop}; sell at least half by "
            "day {sell_half_day}'s close and be out by day {final_day}'s close.")


def replay(pick: dict, bars: list[dict], regime: str = "green") -> dict:
    """One pick walked over its later bars: the fill rule, then
    ``plan.follow()`` from the open fill over whole bars. The row carries the
    published stop and targets beside the walk's own numbers, so the page
    can draw stop, entry and aim on one scale. A first bar the walk could
    not read is ``unreadable``, the way a later one is; a fill the bar
    cannot establish is ``uncertain`` with its reason, and is never walked."""
    base = {"ticker": pick["ticker"], "kind": pick.get("kind", "burst"), "picked": pick["date"],
            "grade": pick.get("grade"), "stop": pick["stop"], "targets": pick.get("targets"),
            "fill": None, "uncertainty": None, "sessions": len(bars)}
    if not bars:
        walk = plan.follow(pick, [], regime)
        return {**walk, **base, "day": 0}
    first = bars[0]
    if not (first["l"] <= min(first["o"], first["c"]) and max(first["o"], first["c"]) <= first["h"]):
        return _no_walk(base, pick, None, day=1, status=UNREADABLE, fill_note=None,
                        instruction=(f"Day 1 ({first['date']}): the bar could not be read (open {first['o']}, close "
                                     f"{first['c']} outside {first['l']}-{first['h']}); follow the plan's own stop."),
                        events=[], regime=regime)
    status, price, note, why = fill(pick, first)
    if status == NOT_FILLED:
        return _no_walk(base, pick, first, day=1, status=NOT_FILLED, fill_note=note,
                        instruction=f"Day 1 ({first['date']}): {note}. Nothing to hold.",
                        events=[{"day": 1, "date": first["date"], "event": NOT_FILLED, "price": first["o"]}],
                        regime=regime)
    if status == UNCERTAIN:
        taken = IF_TAKEN.format(stop=plan._usd(float(pick["stop"])), sell_half_day=plan.SELL_HALF_DAY,
                                final_day=plan.FINAL_EXIT_DAY)
        day = min(len(bars), plan.FINAL_EXIT_DAY)
        over = (f" The {plan.FINAL_EXIT_DAY}-session window is over: if you still hold it, exit."
                if len(bars) > plan.FINAL_EXIT_DAY else "")
        return _no_walk(base, pick, bars[-1], day=day, status=UNCERTAIN, fill_note=note,
                        instruction=f"Day 1 ({first['date']}): {note}. {taken}{over}",
                        events=[{"day": 1, "date": first["date"], "event": UNCERTAIN, "price": None}],
                        regime=regime, uncertainty=why)
    filled = {**pick, "entry_ref": price}
    try:
        walk = plan.follow(filled, bars, regime)
    except ValueError as exc:
        return _no_walk({**base, "entry_ref": price}, {**pick, "entry_ref": price}, None, day=len(bars),
                        status=UNREADABLE, fill_note=note,
                        instruction=f"A later bar could not be read ({exc}); follow the plan's own stop.",
                        events=[], regime=regime)
    return {**walk, **base, "fill": note}


def r_multiple(row: dict, stop: float) -> float | None:
    """The result in R, weighted by the whole shares each sale event sold:
    ``sum(shares_sold * (price - entry)) / (shares * (entry - stop))``, the
    published stop being one R on the whole position. None until every share
    the model held has been sold (an open walk, an expired one, an uncertain
    one), or when the sales do not reconcile to the share count. A walk with
    no shares has no partial exits and is read on prices alone."""
    entry, shares = row.get("entry_ref"), row.get("shares")
    if not _finite(entry) or not _finite(stop) or entry <= stop:
        return None
    risk = entry - stop
    sales = [e for e in row.get("events", []) if isinstance(e, dict) and _finite(e.get("shares"))
             and e["shares"] > 0 and _finite(e.get("price"))]
    if isinstance(shares, int) and not isinstance(shares, bool) and shares > 0:
        if sum(e["shares"] for e in sales) != shares:
            return None
        return round(math.fsum(e["shares"] * (e["price"] - entry) for e in sales) / (shares * risk), 2)
    exit_price = row.get("exit_price")
    if not _finite(exit_price):
        return None
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
    from src import market_data
    window = set(sessions_before(frames, session, OPEN_PLAN_SESSIONS))
    calendar_dates = [d.isoformat() for d in market_data.session_calendar(frames)] if frames else []
    rows = []
    for pick in rec.get("picks", []):
        if pick["date"] not in window:
            continue
        df = frames.get(pick["ticker"])
        bars = later_bars(df, pick["date"], session)
        row = replay(pick, bars, regime)
        passed = [d for d in calendar_dates if pick["date"] < d <= session]
        if df is None or (not bars and passed):
            # the night did not fetch the name, or the market printed sessions
            # this name did not: a ticket that "has not had a session yet" is
            # the wrong sentence for a name that has stopped printing
            why = "No bars for" if df is None else f"No bar since the pick for"
            row["instruction"] = (f"{why} {pick['ticker']} tonight; follow the plan's own stop at "
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
    picks: how many plans, how many the bars can say filled, how many are
    uncertain (by reason) or could not have filled, wins and losses among
    the settled ones, average and summed R, and SPY over the same days.
    Every count is a count; the rates are over the settled plans alone, None
    until ``SCORECARD_MIN_PLANS`` have settled -- an uncertain plan never
    counts toward that -- and the page prints the counts either way."""
    window = set(sessions_before(frames, session, SCORECARD_SESSIONS))
    spy = frames.get(BENCHMARK)
    plans = filled = wins = losses = settled = open_now = uncertain = not_filled = unreadable = unscored = 0
    reasons: dict[str, int] = {}
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
        if row["status"] == UNCERTAIN:
            uncertain += 1
            reasons[row["uncertainty"]] = reasons.get(row["uncertainty"], 0) + 1
            continue
        if row["status"] == NOT_FILLED:
            not_filled += 1
            continue
        if row["status"] == UNREADABLE:
            unreadable += 1
            continue
        filled += 1
        if row["status"] not in SETTLED:
            open_now += 1
            continue
        r = r_multiple(row, pick["stop"])
        if r is None:
            unscored += 1
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
        "uncertain": uncertain,
        "uncertain_reasons": [{"kind": k, "count": reasons[k], "words": UNCERTAIN_WORDS[k]}
                              for k in UNCERTAIN_REASONS if reasons.get(k)],
        "not_filled": not_filled, "unreadable": unreadable, "unscored": unscored,
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
