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
  over it. A crossing minute that opened over the ticket's limit leaves a
  resting limit order: **not filled** when no minute of the window from it on
  trades back to the limit, otherwise **uncertain** (``minute_order``: the fill
  is somewhere in a minute whose bar cannot give its price). A crossing minute
  that did not open over the trigger and whose low reaches the stop cannot
  order fill and stop either, and stays **uncertain**;
- otherwise the ticket **filled** at that minute, and the entry day the walk
  reads is rebuilt from the fill on: the fill price, the high and low of the
  crossing minute and every minute after it, the session's close, and the
  session's own low for the stop the plan raises to at day 1's close.

The minutes establish the fill and nothing after it: the walk from the fill is
``plan.follow()``'s daily model, convention and all -- a day-1 bar reaching both
the stop and the +8% level books the stop, as a daily bar filled at the open
would, even where the minutes would order them the other way.

Only ``RESOLVABLE`` reasons are read again; an open past the limit or under the
skip line keeps the daily answer. Minutes must reproduce the daily bar to be
used: they must reach the trigger it reached, no minute may trade outside its
range, and when its low reached the stop a minute must show where. Minutes that
do not are another feed's account of the day and are not used.

Evidence is content-addressed JSON under ``docs/intraday/``, one object per
pick, a pure function of the pick and its minutes, bounded and append-only: an
object is written once, read back, and never replaced by a different one for
the same pick. A walk reads only what is retained (a dry run reads what it
fetched and writes nothing). A fetch that fails, a session whose minutes are not
yet complete behind the feed's hold-back, an archive at capacity, or a pick the
archive sets aside leaves the plan uncertain and is named in ``run.intraday``.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

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
#: (P) the picks a run asks the provider for: never-failed first, newest first; the rest wait
MAX_PICKS_PER_RUN = 8
#: (P) a regular session is 390 minutes; an object claiming more is refused
MAX_MINUTES = 400
#: (P) the archive's bounds; at capacity nothing new is written and the plan stays uncertain
ARCHIVE_MAX_OBJECTS = 512
ARCHIVE_MAX_BYTES = 16 * 1024 * 1024
OBJECT_MAX_BYTES = 64 * 1024
#: (P) prices are rounded once, on the way in
PRICE_DECIMALS = 4
#: the feed's own hold-back behind the clock; a session's minutes are complete only past it
HOLDBACK_MINUTES = 16
DIR_NAME = "intraday"
#: how an archive object is named: its SHA-256 and .json
NAME_PATTERN = re.compile(r"[0-9a-f]{64}\.json")

FILLED, NOT_FILLED, UNCERTAIN = "filled", "not_filled", "uncertain"
GATHERED, FAILED = "gathered", "failed"

RULES: dict[str, Any] = {
    "intraday.version": VERSION,
    "intraday.policy": POLICY,
    "intraday.timeframe": TIMEFRAME,
    "intraday.feed": FEED,
    "intraday.adjustment": ADJUSTMENT,
    "intraday.resolvable": list(RESOLVABLE),
    "intraday.window_minutes": plan.ENTRY_WINDOW_MINUTES,
    "intraday.max_picks_per_run": MAX_PICKS_PER_RUN,
    "intraday.max_minutes": MAX_MINUTES,
    "intraday.archive_max_objects": ARCHIVE_MAX_OBJECTS,
    "intraday.archive_max_bytes": ARCHIVE_MAX_BYTES,
    "intraday.object_max_bytes": OBJECT_MAX_BYTES,
    "intraday.price_decimals": PRICE_DECIMALS,
    "intraday.holdback_minutes": HOLDBACK_MINUTES,
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
                     "closes_at", "minutes"}
    if set(obj) != expected_keys:
        raise IntradayError(f"intraday object keys {sorted(set(obj) ^ expected_keys)} differ")
    if obj["basis"] != basis():
        raise IntradayError(f"intraday basis {obj['basis']!r} is not {basis()!r}")
    try:
        signal = date.fromisoformat(obj["signal_session"])
        session = date.fromisoformat(obj["session"])
        after = exchange_sessions.next_sessions(signal, 1)[0]
    except (TypeError, ValueError) as exc:
        raise IntradayError(f"intraday sessions unreadable: {exc}") from exc
    if after != session:
        raise IntradayError(f"{obj['session']} is not the session after {obj['signal_session']}")
    if not isinstance(obj["ticker"], str) or not obj["ticker"]:
        raise IntradayError("intraday object names no ticker")
    if not isinstance(obj["key"], str) or not obj["key"].endswith(f":{obj['ticker']}:{obj['signal_session']}"):
        raise IntradayError(f"intraday key {obj['key']!r} is not this ticker's and session's")
    opens, closes, _ = exchange_sessions.hours(session)
    if obj["opens_at"] != _iso(opens) or obj["closes_at"] != _iso(closes):
        raise IntradayError("intraday hours are not the exchange's for that session")
    length = int((closes - opens).total_seconds() // 60)
    minutes = obj["minutes"]
    if not isinstance(minutes, list) or not minutes or len(minutes) > MAX_MINUTES:
        raise IntradayError("intraday minutes are not a bounded, non-empty list")
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


def build(pick: Mapping[str, Any], frame_rows: list[tuple[datetime, float, float, float, float]]) -> dict:
    """An object from one pick's minute rows ``(start, o, h, l, c)``, kept to
    the session's regular hours and rounded once. It carries no clock of its
    own, so the same minutes are the same object and the same name."""
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
                     "opens_at": _iso(opens), "closes_at": _iso(closes), "minutes": minutes})


# ----------------------------------------------------------------- archive ----

def load_archive(docs: Path) -> tuple[dict[str, dict], list[str], set[str]]:
    """Every readable object under ``docs/intraday/`` by pick key, the
    problems named, and the keys set aside. An object whose bytes are not its
    name, or that does not validate, is named and not used; a key two objects
    claim is named, not used and set aside, so no run asks for it again."""
    folder = Path(docs) / DIR_NAME
    found: dict[str, list[dict]] = {}
    problems: list[str] = []
    if not folder.is_dir():
        return {}, problems, set()
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
    evidence, set_aside = {}, set()
    for k, objs in sorted(found.items()):
        if len(objs) > 1:
            problems.append(f"{k}: {len(objs)} objects claim it; none is used")
            set_aside.add(k)
            continue
        evidence[k] = objs[0]
    return evidence, problems, set_aside


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
    """Write each new object once and read it back. Returns the keys stored
    (or already there, byte for byte) and the problems named; at capacity, or
    when the disk refuses, nothing new is written and it is named."""
    folder = Path(docs) / DIR_NAME
    stored, problems = [], []
    try:
        folder.mkdir(parents=True, exist_ok=True)
        existing = sorted(folder.glob("*.json"))
        count, size = len(existing), sum(p.stat().st_size for p in existing)
    except OSError as exc:
        return [], [f"the archive could not be opened: {type(exc).__name__}"]
    for obj in objects:
        data = canonical(validate(obj))
        path = folder / name_of(obj)
        try:
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
        except OSError as exc:
            problems.append(f"{obj['key']}: not written ({type(exc).__name__})")
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
    name the reply did not carry, or carried only outside regular hours, is a
    failure of kind ``no_minutes``."""
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
            if not any(opens <= start < closes for start, *_ in rows):
                # nothing, or rows only outside the session's regular hours
                failures.append({"key": key(pick), "kind": "no_minutes"})
                continue
            try:
                objects.append(build(pick, rows))
            except IntradayError:
                failures.append({"key": key(pick), "kind": "unreadable_minutes"})
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
           failed_before: Iterable[str] = (), fetcher: Callable | None = None) -> tuple[dict[str, dict], dict]:
    """The evidence a run walks with: every retained object, and minutes
    fetched tonight for ``picks`` (the ones a daily bar left uncertain on a
    resolvable reason) that have none, each only once its session's minutes are
    complete, at most ``MAX_PICKS_PER_RUN`` of them: those that did not fail the
    night before first (``failed_before``, last night's failure keys), newest
    first within each, so a pick that keeps failing cannot hold the cap. A pick
    the archive sets aside is never asked again. A walk reads what was stored;
    a dry run (``write`` false) reads what it fetched. Returns the evidence by
    key and the ``run.intraday`` block."""
    evidence, problems, set_aside_keys = load_archive(docs)
    retained = len(evidence)
    failed = set(failed_before)
    needed = [p for p in picks if key(p) not in evidence]
    set_aside = [p for p in needed if key(p) in set_aside_keys]
    wanted = [p for p in needed if key(p) not in set_aside_keys]
    ready = [p for p in wanted if complete(entry_session(p), now)]
    ready.sort(key=lambda p: (key(p) not in failed, p["date"], p["ticker"]), reverse=True)
    asked, waiting = ready[:MAX_PICKS_PER_RUN], len(wanted) - len(ready)
    objects, failures = ((fetcher or fetch)(client, asked, now) if asked and client is not None else ([], []))
    if asked and client is None:
        failures = [{"key": key(p), "kind": "no_client"} for p in asked]
    stored: list[str] = []
    if write and objects:
        stored, store_problems = store(docs, objects)
        problems += store_problems
    usable = {obj["key"]: obj for obj in objects if not write or obj["key"] in stored}
    for k, obj in usable.items():
        evidence.setdefault(k, obj)
    return evidence, block(wanted=len(needed), set_aside=len(set_aside), asked=len(asked), fetched=len(objects),
                           stored=len(stored), retained=retained + len(stored), waiting=waiting,
                           beyond_cap=max(0, len(ready) - MAX_PICKS_PER_RUN), failures=failures, problems=problems)


def failed_block(*, wanted: int, retained: int, kind: str, problems: list[str]) -> dict:
    """The block of a night whose minute evidence could not be gathered at all:
    nothing asked, the retained archive still read, the failure named."""
    out = {"version": VERSION, "policy": POLICY, "basis": basis(), "status": FAILED, "wanted": wanted,
           "set_aside": 0, "asked": 0, "fetched": 0, "stored": 0, "retained": retained, "waiting": 0,
           "beyond_cap": 0, "failures": [],
           "problems": ([f"the minute evidence could not be gathered: {kind}"] + list(problems))[:20]}
    out["sentence"] = sentence(out)
    return out


def block(*, wanted: int, set_aside: int, asked: int, fetched: int, stored: int, retained: int, waiting: int,
          beyond_cap: int, failures: list[dict], problems: list[str]) -> dict:
    out = {"version": VERSION, "policy": POLICY, "basis": basis(), "status": GATHERED, "wanted": wanted,
           "set_aside": set_aside, "asked": asked, "fetched": fetched, "stored": stored, "retained": retained,
           "waiting": waiting, "beyond_cap": beyond_cap, "failures": sorted(failures, key=lambda f: f["key"]),
           "problems": problems[:20]}
    out["sentence"] = sentence(out)
    return out


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'s' if n != 1 else ''}"


def _retained_words(n: int) -> str:
    return (f"minute bars are retained for 1 plan's first day" if n == 1
            else f"minute bars are retained for {n} plans' first days")


def sentence(b: Mapping[str, Any]) -> str:
    """The block in words: what tonight needed, asked for, fetched and
    stored, what it could not, and how many first days the archive holds."""
    problems = (f"; {_plural(len(b['problems']), 'problem')} named" if b["problems"] else "")
    if b.get("status") == FAILED:
        return (f"The minute evidence could not be gathered tonight: {_plural(b['wanted'], 'plan')} needing it "
                f"read only what was retained{problems}; {_retained_words(b['retained'])}.")
    if not b["wanted"]:
        return f"No plan's first day needed its minute bars tonight{problems}; {_retained_words(b['retained'])}."
    parts = [f"{_plural(b['wanted'], 'plan')} had a first day the daily bar could not place without minute bars; "
             f"{b['asked']} asked for, {b['fetched']} fetched, {b['stored']} stored"]
    if b["set_aside"]:
        parts.append(f"{b['set_aside']} set aside by the archive")
    if b["waiting"]:
        parts.append(f"{b['waiting']} waiting for the feed's hold-back")
    if b["beyond_cap"]:
        parts.append(f"{b['beyond_cap']} past the run's {MAX_PICKS_PER_RUN}")
    if b["failures"]:
        parts.append(f"{len(b['failures'])} not fetched ({', '.join(sorted({f['kind'] for f in b['failures']}))})")
    if b["problems"]:
        parts.append(f"{_plural(len(b['problems']), 'problem')} named")
    return "; ".join(parts) + f"; {_retained_words(b['retained'])}."


def faults(b: Any) -> list[str]:
    """The block whole, or what is wrong with it, one level in."""
    if not isinstance(b, dict):
        return ["run.intraday is not a block"]
    out = []
    counts = ("wanted", "set_aside", "asked", "fetched", "stored", "retained", "waiting", "beyond_cap")
    for name in counts:
        v = b.get(name)
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            out.append(f"run.intraday.{name} is not a count")
    if out:
        return out
    if b.get("version") != VERSION or b.get("policy") != POLICY or b.get("basis") != basis():
        out.append("run.intraday is not this version's")
    if b.get("status") not in (GATHERED, FAILED):
        out.append("run.intraday.status is neither gathered nor failed")
        return out
    if not isinstance(b.get("failures"), list) or not isinstance(b.get("problems"), list):
        out.append("run.intraday.failures and .problems must be lists")
        return out
    if any(not isinstance(f, dict) or not isinstance(f.get("key"), str) or not isinstance(f.get("kind"), str)
           for f in b["failures"]):
        out.append("run.intraday.failures are not {key, kind} pairs")
        return out
    if len({f["key"] for f in b["failures"]}) != len(b["failures"]):
        out.append("run.intraday names a failure twice")
    if any(not isinstance(p, str) for p in b["problems"]):
        out.append("run.intraday.problems are not sentences")
        return out
    if b["status"] == FAILED:
        if any(b[n] for n in ("set_aside", "asked", "fetched", "stored", "waiting", "beyond_cap")) or b["failures"]:
            out.append("run.intraday failed but counts work done")
        if not b["problems"]:
            out.append("run.intraday failed without naming why")
    else:
        if b["wanted"] != b["set_aside"] + b["waiting"] + b["asked"] + b["beyond_cap"]:
            out.append("run.intraday's wanted is not its set-aside, waiting, asked and past-the-cap plans")
        if b["asked"] > MAX_PICKS_PER_RUN:
            out.append("run.intraday asked more than its bound")
        if b["beyond_cap"] and b["asked"] != MAX_PICKS_PER_RUN:
            out.append("run.intraday left plans past a cap it did not reach")
        if b["fetched"] + len(b["failures"]) != b["asked"]:
            out.append("run.intraday's fetched and failed do not add up to what it asked")
        if b["stored"] > b["fetched"]:
            out.append("run.intraday stored more than it fetched")
        if b["retained"] < b["stored"]:
            out.append("run.intraday retains fewer than it stored")
    if b.get("sentence") != sentence(b):
        out.append("run.intraday.sentence is not its own")
    return out


def record_faults(data: Mapping[str, Any]) -> list[str]:
    """``run.intraday`` held one level in, under the rules the record
    archived: a record made under rules that read minute bars carries the
    block whole, and every open plan it walked from minutes names an archive
    object, no more of them than the walks could read -- what the archive
    retains, and on a dry run what it fetched and did not store; one made
    before them carries none and is asked for none."""
    rules = (data.get("rules") or {}).get("intraday") if isinstance(data.get("rules"), dict) else None
    if not isinstance(rules, dict) or "version" not in rules:
        return []
    if rules["version"] != VERSION:
        return [f"rules.intraday.version {rules['version']!r} is not one this code reads"]
    run = data.get("run") if isinstance(data.get("run"), dict) else {}
    if "intraday" not in run:
        return ["run.intraday is missing under rules that read minute bars"]
    out = faults(run["intraday"])
    if out:
        return out
    plans = data.get("open_plans") if isinstance(data.get("open_plans"), list) else []
    names = [p.get("minute_evidence") for p in plans if isinstance(p, dict) and "minute_evidence" in p]
    if any(not isinstance(n, str) or not NAME_PATTERN.fullmatch(n) for n in names):
        out.append("an open plan's minute_evidence is not an archive object's name")
    else:
        readable = run["intraday"]["retained"] + (run["intraday"]["fetched"] if run.get("dry_run") is True else 0)
        if len(set(names)) > readable:
            out.append("open plans name more minute objects than the walks could read")
    return out


# ----------------------------------------------------------------- resolve ----

def _disagrees(minutes: list[list], day: Mapping[str, Any], trigger: float, stop: float) -> bool:
    """Whether the minutes are another account of the day than its daily bar:
    a minute outside the bar's range, no minute reaching the trigger it reached,
    or a low at or under the stop that no minute shows."""
    low, high = round(float(day["l"]), PRICE_DECIMALS), round(float(day["h"]), PRICE_DECIMALS)
    if min(m[3] for m in minutes) < low or max(m[2] for m in minutes) > high:
        return True
    if max(m[2] for m in minutes) < trigger:
        return True
    return low <= stop and not any(m[3] <= stop for m in minutes)


def resolve(levels: Mapping[str, Any], obj: Mapping[str, Any] | None, day: Mapping[str, Any]
            ) -> tuple[str, float | None, str, str | None, dict | None] | None:
    """The first session read again from its minutes. ``levels`` carries
    ``trigger``, ``limit`` (None for no limit) and ``stop``; ``day`` is the
    session's daily bar. Returns ``(status, price, note, reason, entry_day)``,
    ``entry_day`` the walk's day-1 bar rebuilt from the fill on, or None when
    the minutes cannot be used: absent, another session's, or not reproducing
    the daily bar (``_disagrees``)."""
    if obj is None or obj.get("session") != day.get("date"):
        return None
    trigger, stop = float(levels["trigger"]), float(levels["stop"])
    limit = None if levels.get("limit") is None else float(levels["limit"])
    minutes = obj["minutes"]
    if not minutes or _disagrees(minutes, day, trigger, stop):
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
        rest = [m for m in window if m[0] >= offset]
        if not any(m[3] <= limit for m in rest):
            return NOT_FILLED, None, (f"minute bars: the minute at {at(offset)} reached the {usd(trigger)} trigger "
                                      f"opening at {usd(o)}, above the {usd(limit)} limit, and no minute of the "
                                      f"{plan.ENTRY_WINDOW} traded back to it: the limit could not fill"), None, None
        return UNCERTAIN, None, (f"minute bars: the minute at {at(offset)} reached the {usd(trigger)} trigger "
                                 f"opening at {usd(o)}, above the {usd(limit)} limit; the day traded back to it "
                                 f"inside the {plan.ENTRY_WINDOW}, at a price its minute bar cannot give"), MINUTE_ORDER, None
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
