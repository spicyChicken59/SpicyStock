"""Minute bars for the one fill a daily bar cannot place (#111).

A daily bar establishes a fill only at the open (``record.fill()``). A day that
opened under the trigger and reached it later is ``uncertain``: the plan's
entry is the first 30 minutes, and the bar cannot say when the crossing came.
Every anticipation ticket is a buy stop above its coil, so that is its usual
first day, and a scorecard that never settles one never says anything.

This module reads that session's regular-hours minute bars, retained once,
and asks them the same question in order:

- the first minute of the entry window whose high reaches the trigger is the
  crossing; no minute of the window reaching it means the plan's day order was
  cancelled at the window's end: **not filled**, however far the day went later;
- the fill is at the trigger, or at that minute's open when it opened at or
  over it; a fill price over the ticket's limit, or a crossing minute (that did
  not open over the trigger) whose low reaches the stop, cannot be ordered by
  the minute's own bar and stays **uncertain** (``minute_order``);
- otherwise the ticket **filled** at that minute, and the entry day the walk
  reads is rebuilt from the fill on: the fill price, the high and low of the
  crossing minute and every minute after it, the session's close, and the
  session's own low for the stop the plan raises to at day 1's close.

Only ``RESOLVABLE`` reasons are read again; an open past the limit or under the
skip line keeps the daily answer. Minutes that do not show the day reaching the
trigger at all disagree with the daily bar and are not used.

Evidence is content-addressed JSON under ``docs/intraday/``, one object per
pick, bounded and append-only: an object is written once, read back, and never
replaced by a different one for the same pick. A fetch that fails, a session
whose minutes are not yet complete behind the feed's hold-back, or an archive
at capacity leaves the plan uncertain and is named in ``run.intraday``.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from src import plan
from src import sessions as exchange_sessions

VERSION = 1
POLICY = "first_window_minute_v1"
PROVIDER = "Alpaca"
FEED = "sip"
ADJUSTMENT = "split"
TIMEFRAME = "1Min"
#: the daily uncertainty reasons whose session these minutes read again
RESOLVABLE = ("trigger_timing", "stop_sequence")
#: the one reason a minute walk leaves: the crossing minute's own bar cannot order it
MINUTE_ORDER = "minute_order"
MINUTE_ORDER_WORDS = ("reached the trigger in a minute whose own bar cannot order the fill against the limit "
                      "or the stop")
#: (P) the picks a run asks the provider for, newest first; the rest wait a night
MAX_PICKS_PER_RUN = 8
#: (P) a regular session is 390 minutes; an object claiming more is refused
MAX_MINUTES = 400
#: (P) the archive's bounds; at capacity nothing new is written and the plan stays uncertain
ARCHIVE_MAX_OBJECTS = 512
ARCHIVE_MAX_BYTES = 16 * 1024 * 1024
OBJECT_MAX_BYTES = 64 * 1024
PRICE_DECIMALS = 4
#: the feed's own hold-back behind the clock; a session's minutes are complete only past it
HOLDBACK_MINUTES = 16
DIR_NAME = "intraday"

FILLED, NOT_FILLED, UNCERTAIN = "filled", "not_filled", "uncertain"

RULES: dict[str, Any] = {
    "intraday.version": VERSION,
    "intraday.policy": POLICY,
    "intraday.timeframe": TIMEFRAME,
    "intraday.feed": FEED,
    "intraday.adjustment": ADJUSTMENT,
    "intraday.resolvable": list(RESOLVABLE),
    "intraday.window_minutes": plan.ENTRY_WINDOW_MINUTES,
    "intraday.max_picks_per_run": MAX_PICKS_PER_RUN,
    "intraday.archive_max_objects": ARCHIVE_MAX_OBJECTS,
}


class IntradayError(ValueError):
    """An object or a block the reading cannot use whole."""


# ------------------------------------------------------------------ keys ----

def key(pick: Mapping[str, Any]) -> str:
    """One pick's evidence key: its kind, ticker and signal session."""
    return f"{pick.get('kind', 'burst')}:{pick['ticker']}:{pick['date']}"


def entry_session(pick: Mapping[str, Any]) -> date:
    """The session the ticket was for: the one after its signal session."""
    return exchange_sessions.next_sessions(date.fromisoformat(pick["date"]), 1)[0]


def _iso(at: datetime) -> str:
    return at.astimezone(timezone.utc).isoformat()


# --------------------------------------------------------------- objects ----

def _finite_positive(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def validate(obj: Any) -> dict:
    """The object whole, or a refusal naming what it lacks."""
    if not isinstance(obj, dict) or obj.get("version") != VERSION or obj.get("policy") != POLICY:
        raise IntradayError("not an intraday object of this version")
    expected_keys = {"version", "policy", "key", "ticker", "signal_session", "session", "basis", "opens_at",
                     "closes_at", "minutes", "fetched_at"}
    if set(obj) != expected_keys:
        raise IntradayError(f"intraday object keys {sorted(set(obj) ^ expected_keys)} differ")
    if obj["basis"] != basis():
        raise IntradayError(f"intraday basis {obj['basis']!r} is not {basis()!r}")
    try:
        signal = date.fromisoformat(obj["signal_session"])
        session = date.fromisoformat(obj["session"])
    except (TypeError, ValueError) as exc:
        raise IntradayError(f"intraday sessions unreadable: {exc}") from exc
    if exchange_sessions.next_sessions(signal, 1)[0] != session:
        raise IntradayError(f"{obj['session']} is not the session after {obj['signal_session']}")
    if not isinstance(obj["ticker"], str) or not obj["ticker"]:
        raise IntradayError("intraday object names no ticker")
    if not isinstance(obj["key"], str) or not obj["key"].endswith(f":{obj['ticker']}:{obj['signal_session']}"):
        raise IntradayError(f"intraday key {obj['key']!r} is not this ticker's and session's")
    opens, closes, _ = exchange_sessions.hours(session)
    if obj["opens_at"] != _iso(opens) or obj["closes_at"] != _iso(closes):
        raise IntradayError("intraday hours are not the exchange's for that session")
    try:
        datetime.fromisoformat(obj["fetched_at"])
    except (TypeError, ValueError) as exc:
        raise IntradayError("intraday fetch time unreadable") from exc
    length = int((closes - opens).total_seconds() // 60)
    minutes = obj["minutes"]
    if not isinstance(minutes, list) or len(minutes) > MAX_MINUTES:
        raise IntradayError("intraday minutes are not a bounded list")
    last = -1
    for row in minutes:
        if (not isinstance(row, list) or len(row) != 5 or not isinstance(row[0], int) or isinstance(row[0], bool)
                or not all(_finite_positive(v) for v in row[1:])):
            raise IntradayError(f"intraday minute {row!r} is not [offset, o, h, l, c]")
        offset, o, h, low, c = row
        if not (last < offset < length):
            raise IntradayError(f"intraday minute offset {offset} is out of order or outside the session")
        if not (low <= min(o, c) and max(o, c) <= h):
            raise IntradayError(f"intraday minute {row!r}: open and close must sit inside its range")
        last = offset
    return obj


def basis() -> dict:
    return {"provider": PROVIDER, "feed": FEED, "adjustment": ADJUSTMENT, "timeframe": TIMEFRAME}


def canonical(obj: Mapping[str, Any]) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def name_of(obj: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest() + ".json"


def build(pick: Mapping[str, Any], frame_rows: list[tuple[datetime, float, float, float, float]],
          fetched_at: datetime) -> dict:
    """An object from one pick's minute rows ``(start, o, h, l, c)``, kept to
    the session's regular hours and rounded once."""
    session = entry_session(pick)
    opens, closes, _ = exchange_sessions.hours(session)
    minutes = []
    for start, o, h, low, c in sorted(frame_rows, key=lambda r: r[0]):
        offset = int((start - opens).total_seconds() // 60)
        if not (opens <= start < closes):
            continue
        row = [offset] + [round(float(v), PRICE_DECIMALS) for v in (o, h, low, c)]
        if minutes and minutes[-1][0] == offset:
            minutes[-1] = row       # a minute sent twice: the copy the feed sent last
        else:
            minutes.append(row)
    return validate({"version": VERSION, "policy": POLICY, "key": key(pick), "ticker": pick["ticker"],
                     "signal_session": pick["date"], "session": session.isoformat(), "basis": basis(),
                     "opens_at": _iso(opens), "closes_at": _iso(closes), "minutes": minutes,
                     "fetched_at": _iso(fetched_at)})


# ----------------------------------------------------------------- archive ----

def load_archive(docs: Path) -> tuple[dict[str, dict], list[str]]:
    """Every readable object under ``docs/intraday/`` by pick key. An object
    whose bytes are not its name, that does not validate, or whose key two
    objects claim is named and not used."""
    folder = Path(docs) / DIR_NAME
    found: dict[str, list[dict]] = {}
    problems: list[str] = []
    if not folder.is_dir():
        return {}, problems
    for path in sorted(folder.glob("*.json")):
        try:
            raw = path.read_bytes()
            obj = validate(json.loads(raw))
        except (OSError, ValueError) as exc:
            problems.append(f"{path.name}: {exc}"[:200])
            continue
        if canonical(obj) != raw or name_of(obj) != path.name:
            problems.append(f"{path.name}: bytes are not the object its name gives")
            continue
        found.setdefault(obj["key"], []).append(obj)
    evidence = {}
    for k, objs in sorted(found.items()):
        if len(objs) > 1:
            problems.append(f"{k}: {len(objs)} objects claim it; none is used")
            continue
        evidence[k] = objs[0]
    return evidence, problems


def _write(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".intraday-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def store(docs: Path, objects: list[dict]) -> tuple[list[str], list[str]]:
    """Write each new object once and read it back. Returns the keys stored and
    the problems named; at capacity nothing new is written."""
    folder = Path(docs) / DIR_NAME
    folder.mkdir(parents=True, exist_ok=True)
    existing = sorted(folder.glob("*.json"))
    count, size = len(existing), sum(p.stat().st_size for p in existing)
    stored, problems = [], []
    for obj in objects:
        data = canonical(validate(obj))
        path = folder / name_of(obj)
        if path.exists():
            if path.read_bytes() == data:
                stored.append(obj["key"])
            else:
                problems.append(f"{path.name}: a different file holds this object's name; left as it is")
            continue
        if len(data) > OBJECT_MAX_BYTES:
            problems.append(f"{obj['key']}: {len(data)} bytes is over the {OBJECT_MAX_BYTES}-byte object bound")
            continue
        if count + 1 > ARCHIVE_MAX_OBJECTS or size + len(data) > ARCHIVE_MAX_BYTES:
            problems.append(f"{obj['key']}: the archive is at capacity ({count} objects, {size} bytes)")
            continue
        _write(path, data)
        if path.read_bytes() != data:
            problems.append(f"{path.name}: read back differently")
            continue
        count, size = count + 1, size + len(data)
        stored.append(obj["key"])
    return stored, problems


# ------------------------------------------------------------------- fetch ----

def complete(session: date, now: datetime) -> bool:
    """Whether a session's regular-hours minutes are all behind the feed's hold-back."""
    return now - timedelta(minutes=HOLDBACK_MINUTES) >= exchange_sessions.hours(session)[1]


def fetch(client, picks: list[Mapping[str, Any]], now: datetime) -> tuple[list[dict], list[dict]]:
    """One minute-bar request per entry session for these picks. Returns the
    objects built and the failures, one per pick, by error kind; a pick whose
    name the reply did not carry is a failure of kind ``no_minutes``."""
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    from src import market_data

    by_session: dict[date, list[Mapping[str, Any]]] = {}
    for pick in picks:
        by_session.setdefault(entry_session(pick), []).append(pick)
    objects, failures = [], []
    for session, group in sorted(by_session.items()):
        opens, closes, _ = exchange_sessions.hours(session)
        tickers = sorted({p["ticker"] for p in group})
        request = StockBarsRequest(symbol_or_symbols=tickers, timeframe=TimeFrame.Minute,
                                   start=opens.astimezone(timezone.utc),
                                   end=(closes - timedelta(seconds=1)).astimezone(timezone.utc),
                                   adjustment=market_data.BAR_ADJUSTMENT, feed=market_data.DataFeed.SIP)
        try:
            df = client.get_stock_bars(request).df
        except Exception as exc:  # noqa: BLE001 -- named by kind, never by its text
            failures += [{"key": key(p), "kind": type(exc).__name__} for p in group]
            continue
        for pick in group:
            rows = _rows(df, pick["ticker"])
            if not rows:
                failures.append({"key": key(pick), "kind": "no_minutes"})
                continue
            try:
                obj = build(pick, rows, now)
            except IntradayError:
                failures.append({"key": key(pick), "kind": "unreadable_minutes"})
                continue
            if not obj["minutes"]:
                # rows, but none inside the session's regular hours
                failures.append({"key": key(pick), "kind": "no_minutes"})
                continue
            objects.append(obj)
    return objects, failures


def _rows(df, ticker: str) -> list[tuple[datetime, float, float, float, float]]:
    if df is None or getattr(df, "empty", True):
        return []
    try:
        frame = df.loc[ticker]
    except KeyError:
        return []
    rows = []
    for stamp, row in frame.iterrows():
        try:
            start = stamp.to_pydatetime() if hasattr(stamp, "to_pydatetime") else stamp
            values = tuple(float(row[c]) for c in ("open", "high", "low", "close"))
        except (KeyError, TypeError, ValueError):
            continue
        if start.tzinfo is None or not all(math.isfinite(v) for v in values):
            continue
        rows.append((start.astimezone(timezone.utc), *values))
    return rows


def gather(client, docs: Path, picks: list[Mapping[str, Any]], *, now: datetime, write: bool,
           fetcher: Callable | None = None) -> tuple[dict[str, dict], dict]:
    """The evidence a run walks with: every retained object, and minutes
    fetched tonight for ``picks`` (the ones a daily bar left uncertain on a
    resolvable reason) that have none, at most ``MAX_PICKS_PER_RUN`` of them,
    newest first, each only once its session's minutes are complete. Returns
    the evidence by key and the ``run.intraday`` block."""
    evidence, problems = load_archive(docs)
    wanted = [p for p in picks if key(p) not in evidence]
    ready = [p for p in wanted if complete(entry_session(p), now)]
    ready.sort(key=lambda p: (p["date"], p["ticker"]), reverse=True)
    asked, waiting = ready[:MAX_PICKS_PER_RUN], len(wanted) - len(ready)
    objects, failures = ((fetcher or fetch)(client, asked, now) if asked and client is not None else ([], []))
    if asked and client is None:
        failures = [{"key": key(p), "kind": "no_client"} for p in asked]
    stored: list[str] = []
    if write and objects:
        stored, store_problems = store(docs, objects)
        problems += store_problems
    for obj in objects:
        evidence.setdefault(obj["key"], obj)
    return evidence, block(wanted=len(wanted), asked=len(asked), fetched=len(objects), stored=len(stored),
                           retained=len(evidence), waiting=waiting,
                           beyond_cap=max(0, len(ready) - MAX_PICKS_PER_RUN), failures=failures,
                           problems=problems)


def block(*, wanted: int, asked: int, fetched: int, stored: int, retained: int, waiting: int,
          beyond_cap: int, failures: list[dict], problems: list[str]) -> dict:
    out = {"version": VERSION, "policy": POLICY, "basis": basis(), "wanted": wanted, "asked": asked,
           "fetched": fetched, "stored": stored, "retained": retained, "waiting": waiting,
           "beyond_cap": beyond_cap, "failures": sorted(failures, key=lambda f: f["key"]),
           "problems": problems[:20]}
    out["sentence"] = sentence(out)
    return out


def _retained_words(n: int) -> str:
    return f"minute bars are retained for {n} plan{'s' if n != 1 else ''}' first day{'s' if n != 1 else ''}"


def sentence(b: Mapping[str, Any]) -> str:
    """The block in words: what tonight needed, asked for, fetched and
    stored, and how many first days the archive holds."""
    if not b["wanted"] and not b["asked"]:
        return f"No plan's first day needed its minute bars tonight; {_retained_words(b['retained'])}."
    parts = [f"{b['wanted']} plan{'s' if b['wanted'] != 1 else ''} had a first day the daily bar could not place "
             f"without minute bars; {b['asked']} asked for, {b['fetched']} fetched, {b['stored']} stored"]
    if b["waiting"]:
        parts.append(f"{b['waiting']} waiting for the feed's hold-back")
    if b["beyond_cap"]:
        parts.append(f"{b['beyond_cap']} past the run's {MAX_PICKS_PER_RUN}")
    if b["failures"]:
        parts.append(f"{len(b['failures'])} not fetched ({', '.join(sorted({f['kind'] for f in b['failures']}))})")
    if b["problems"]:
        parts.append(f"{len(b['problems'])} archive problem{'s' if len(b['problems']) != 1 else ''} named")
    return "; ".join(parts) + f"; {_retained_words(b['retained'])}."


def faults(b: Any) -> list[str]:
    """The block whole, or what is wrong with it, one level in."""
    if not isinstance(b, dict):
        return ["run.intraday is not a block"]
    out = []
    counts = ("wanted", "asked", "fetched", "stored", "retained", "waiting", "beyond_cap")
    for name in counts:
        v = b.get(name)
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            out.append(f"run.intraday.{name} is not a count")
    if out:
        return out
    if b.get("version") != VERSION or b.get("policy") != POLICY or b.get("basis") != basis():
        out.append("run.intraday is not this version's")
    if not isinstance(b.get("failures"), list) or not isinstance(b.get("problems"), list):
        out.append("run.intraday.failures and .problems must be lists")
        return out
    if b["asked"] > MAX_PICKS_PER_RUN or b["asked"] > b["wanted"]:
        out.append("run.intraday asked more than its bound or its wants")
    if b["fetched"] + len(b["failures"]) != b["asked"]:
        out.append("run.intraday's fetched and failed do not add up to what it asked")
    if b["stored"] > b["fetched"]:
        out.append("run.intraday stored more than it fetched")
    if any(not isinstance(f, dict) or not isinstance(f.get("key"), str) or not isinstance(f.get("kind"), str)
           for f in b["failures"]):
        out.append("run.intraday.failures are not {key, kind} pairs")
        return out
    if any(not isinstance(p, str) for p in b["problems"]):
        out.append("run.intraday.problems are not sentences")
        return out
    if b.get("sentence") != sentence(b):
        out.append("run.intraday.sentence is not its own")
    return out


def record_faults(data: Mapping[str, Any]) -> list[str]:
    """``run.intraday`` held one level in, under the rules the record
    archived: a record made under rules that read minute bars carries the
    block whole; one made before them carries none and is asked for none."""
    rules = (data.get("rules") or {}).get("intraday") if isinstance(data.get("rules"), dict) else None
    if not isinstance(rules, dict) or "version" not in rules:
        return []
    if rules["version"] != VERSION:
        return [f"rules.intraday.version {rules['version']!r} is not one this code reads"]
    run = data.get("run") if isinstance(data.get("run"), dict) else {}
    if "intraday" not in run:
        return ["run.intraday is missing under rules that read minute bars"]
    return faults(run["intraday"])


# ----------------------------------------------------------------- resolve ----

def resolve(levels: Mapping[str, Any], obj: Mapping[str, Any] | None, day: Mapping[str, Any]
            ) -> tuple[str, float | None, str, str | None, dict | None] | None:
    """The first session read again from its minutes. ``levels`` carries
    ``trigger``, ``limit`` (None for no limit) and ``stop``; ``day`` is the
    session's daily bar. Returns ``(status, price, note, reason, entry_day)``,
    ``entry_day`` the walk's day-1 bar rebuilt from the fill on, or None when
    the minutes cannot be used (absent, another session's, or not showing the
    day reaching the trigger at all)."""
    if obj is None or obj.get("session") != day.get("date"):
        return None
    trigger, stop = float(levels["trigger"]), float(levels["stop"])
    limit = None if levels.get("limit") is None else float(levels["limit"])
    minutes = obj["minutes"]
    if not minutes or max(m[2] for m in minutes) < trigger:
        return None
    usd = plan._usd
    opens = datetime.fromisoformat(obj["opens_at"]).astimezone(exchange_sessions.MARKET_TZ)

    def at(offset: int) -> str:
        return (opens + timedelta(minutes=offset)).strftime("%H:%M ET")

    window = [m for m in minutes if m[0] < plan.ENTRY_WINDOW_MINUTES]
    crossing = next((m for m in window if m[2] >= trigger), None)
    if crossing is None:
        later = next(m for m in minutes if m[2] >= trigger)
        high = max((m[2] for m in window), default=None)
        within = f"its high in them {usd(high)}" if high is not None else "no trade in them"
        return NOT_FILLED, None, (f"minute bars: the {usd(trigger)} trigger was not reached in the {plan.ENTRY_WINDOW} "
                                  f"({within}); the day reached it at {at(later[0])}, after the plan cancels the "
                                  f"day order"), None, None
    offset, o, h, low, c = crossing
    price = max(trigger, o)
    if limit is not None and price > limit:
        return UNCERTAIN, None, (f"minute bars: the minute at {at(offset)} reached the {usd(trigger)} trigger "
                                 f"opening at {usd(o)}, above the {usd(limit)} limit; its bar cannot say whether "
                                 f"the resting limit then filled"), MINUTE_ORDER, None
    if o < trigger and low <= stop:
        return UNCERTAIN, None, (f"minute bars: the minute at {at(offset)} reached the {usd(trigger)} trigger and "
                                 f"traded down to {usd(low)}, at or under the {usd(stop)} stop: fill and stop in "
                                 f"an order its bar cannot give"), MINUTE_ORDER, None
    after = [m for m in minutes if m[0] >= offset]
    close = float(day["c"])
    post_h = max([price, close] + [m[2] for m in after])
    post_l = min([price, close] + [m[3] for m in after])
    entry_day = {"date": day["date"], "o": price, "h": post_h, "l": post_l, "c": close,
                 "day_low": min(float(day["l"]), post_l)}
    how = "at the minute's open" if o > trigger else "at the trigger"
    return FILLED, price, (f"filled at {at(offset)}, inside the {plan.ENTRY_WINDOW}, {how}, {usd(price)} "
                           f"(minute bars)"), None, entry_day
