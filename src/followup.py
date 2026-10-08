"""The next session's read of the previous session's stale stocks.

A stock the evening fetch returned without a bar for its session is stale:
its inputs that night are unknown, never a measured non-match. The run for
the next session reads each of the previous publication's stale stocks again,
from the frames it fetched for its OWN session, with no extra provider call,
at EVERY session the stock missed -- from the session after its last bar up to
the previous publication's own, at most ``sessions_max`` of them, one reading
per stock and session: did that session's bar arrive since, how much volume
does it carry, and measured at that session by the evening's own rules (the
session rules, the price policy, ``scans.scan_all`` for the 4% and $ scans,
``watchlist.build`` for the setting-up list), would the publication for that
session have listed it?

It is accounting about previous publications, never a signal: those sessions'
entry windows have passed, so a late bar never becomes a burst, an
observation, a plan or a ticket, and the previous record, its history and its
ledger entry are never touched. A late bar that WOULD have been listed is
named with its session, and makes the night that finds it degraded. A stock
that left tonight's selection is not re-requested; its bars stay unknown. The
bars are this run's, split-adjusted as of this run, which is what the sentence
says. No sentence states a cause (a halt, a delisting, a name that did not
trade): the bar is what the provider served at this run's check, and nothing
more is known. A previous publication that recorded only which stocks were
stale and not where each frame ended (the tolerance's version 1) is read at
its own session alone.

``night()`` never raises: a defect anywhere in it is a ``failed`` block with
the error's class, and the night publishes as it would have without it.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import logging
import math

import pandas as pd

from src import market_data, scans, sessions, universe, watchlist

log = logging.getLogger("spicystock.followup")

VERSION = 2
APPLIED, NOT_APPLICABLE, FAILED = "applied", "not_applicable", "failed"
STATUSES = (APPLIED, NOT_APPLICABLE, FAILED)
#: what became of each of the previous publication's stale stocks at each session it missed
OUTCOMES = ("no_match", "match", "unmeasurable", "price_excluded", "still_missing", "no_frame", "not_selected")
#: the outcomes of a stock whose bar for the session read has arrived
ARRIVED = ("no_match", "match", "unmeasurable", "price_excluded")
#: why a block is not applied, or why it failed
REASONS = ("none_missing", "closed_session", "no_previous_record", "previous_not_open",
           "previous_not_adjacent", "rerun_without_block", "membership_not_recorded",
           "membership_over_bound", "membership_mismatch", "error", "invalid_block")
ROUTES = ("both", "burst", "dollar", "setting_up")
#: each route in the sentence's words
ROUTE_WORDS = {"both": "4% and $ scans", "burst": "4% scan", "dollar": "$ scan", "setting_up": "setting up"}
#: a late bar's prices compared at cents, as a published price is
CENTS = 2


def _through(df: pd.DataFrame, day: date) -> pd.DataFrame | None:
    """The frame's bars dated on or before ``day``, when it carries a bar ON
    ``day``; None when it does not (its bar for that session never arrived)."""
    keep = [d is not None and d <= day for d in (market_data._as_date(s) for s in df.index)]
    upto = df[keep]
    if upto.empty or market_data.last_bar_date(upto) != day:
        return None
    return upto


def _bar_facts(df: pd.DataFrame) -> tuple[int | None, bool | None]:
    """The arrived bar's volume, and whether it is flat (open, high, low and
    close the same at cents), each None when the bar does not carry it."""
    last = df.iloc[-1]
    try:
        v = float(last["Volume"])
        volume = int(v) if math.isfinite(v) and v >= 0 else None
    except (KeyError, TypeError, ValueError):
        volume = None
    try:
        prices = [round(float(last[k]), CENTS) for k in ("Open", "High", "Low", "Close")]
        flat = len(set(prices)) == 1 if all(math.isfinite(p) for p in prices) else None
    except (KeyError, TypeError, ValueError):
        flat = None
    return volume, flat


def _row_key(row: dict) -> tuple:
    return (row["ticker"], row["session"])


def _block(status: str, reason: str | None, for_session: str | None, rows: list[dict]) -> dict:
    rows = sorted(rows, key=_row_key)
    arrived = [r for r in rows if r["outcome"] in ARRIVED]
    block = {
        "version": VERSION, "status": status, "reason": reason, "for_session": for_session,
        "sessions": sorted({r["session"] for r in rows}),
        "stocks": len({r["ticker"] for r in rows}),
        "count": len(rows), "outcomes": {o: sum(1 for r in rows if r["outcome"] == o) for o in OUTCOMES},
        "zero_volume": sum(1 for r in arrived if r["volume"] == 0),
        "flat": sum(1 for r in arrived if r["flat"] is True),
        "matched": sorted({r["ticker"] for r in rows if r["outcome"] == "match"}),
        "rows": rows,
    }
    block["sentence"] = sentence_of(block)
    return block


def _membership(previous_run: dict, benchmark: str) -> tuple[str | None, list[str], dict[str, date | None]]:
    """The previous publication's full stale membership, checked against its own ledger,
    and where each frame ended when the publication recorded it; a reason when
    the membership cannot be read, the stocks and their endings otherwise."""
    tol = previous_run.get("input_tolerance")
    if not isinstance(tol, dict) or "names" not in tol:
        return "membership_not_recorded", [], {}
    names = tol["names"]
    if names is None:
        return "membership_over_bound", [], {}
    stale = ((previous_run.get("coverage") or {}).get("reasons") or {}).get("stale") or {}
    if (not isinstance(names, list) or not all(isinstance(n, str) for n in names)
            or len(names) != stale.get("count") or universe.identity(names) != stale.get("identity")):
        return "membership_mismatch", [], {}
    stocks = sorted(set(names) - {benchmark})
    endings: dict[str, date | None] = {}
    recorded = tol.get("endings")
    if isinstance(recorded, dict):
        for t in stocks:
            try:
                endings[t] = date.fromisoformat(recorded[t]) if isinstance(recorded.get(t), str) else None
            except ValueError:
                endings[t] = None
    return (None, stocks, endings) if stocks else ("none_missing", [], {})


def missed_sessions(ending: date | None, previous: date, sessions_max: int) -> list[date]:
    """The sessions a stale stock missed: after its last recorded bar, up to and
    including the previous publication's session, the most recent
    ``sessions_max`` of them. A stock whose ending is unknown (an unreadable
    stamp, or a publication that recorded none) is read at the previous
    session alone, as the first version of this check read every stock."""
    bound = max(int(sessions_max or 0), 1)
    window = sessions.sessions_before(previous + timedelta(days=1), bound)
    if ending is None or ending >= previous:
        return [previous]
    return [d for d in window if d > ending] or [previous]


def _read(stocks: list[str], frames: dict, day: date, uni, benchmark: str, feed: str) -> list[dict]:
    """Each stock's outcome at ``day``, read from tonight's frames by the
    evening's own rules for that session."""
    stamp = day.isoformat()
    rows, arrived = {}, {}
    for t in stocks:
        if t not in uni.symbols:
            rows[t] = {"ticker": t, "session": stamp, "outcome": "not_selected", "volume": None, "flat": None, "route": None}
        elif t not in frames:
            rows[t] = {"ticker": t, "session": stamp, "outcome": "no_frame", "volume": None, "flat": None, "route": None}
        else:
            upto = _through(frames[t], day)
            if upto is None:
                rows[t] = {"ticker": t, "session": stamp, "outcome": "still_missing", "volume": None, "flat": None, "route": None}
            else:
                arrived[t] = upto
    ready = market_data.apply_session_rules(arrived, day, market_data.DownloadStats(session=day, feed=feed))
    eligible, excluded = universe.session_eligible(ready, uni, exempt=(benchmark,))
    for t, upto in arrived.items():
        volume, flat = _bar_facts(upto)
        row = {"ticker": t, "session": stamp, "outcome": "unmeasurable", "volume": volume, "flat": flat, "route": None}
        if t in excluded:
            row["outcome"] = "price_excluded"
        elif t in eligible:
            try:
                found = scans.scan_all(eligible[t])
            except Exception as exc:  # noqa: BLE001 -- one stock's defect is that stock's outcome
                log.debug("follow-up scan raised for %s: %s", t, exc)
                found = None
            if found is not None:
                burst, dollar = found.get("burst"), found.get("dollar")
                route = "both" if burst and dollar else "burst" if burst else "dollar" if dollar else None
                if route is None:
                    # the setting-up list as the evening builds it: the one frame,
                    # listed among its names or among the also-quiet ones
                    try:
                        lists = watchlist.build({t: eligible[t]})
                        listed = {r["ticker"] for r in lists.get("top", []) + lists.get("also_quiet", [])}
                        route = "setting_up" if t in listed else None
                    except Exception as exc:  # noqa: BLE001 -- one stock's defect is that stock's outcome
                        log.debug("follow-up setting-up read raised for %s: %s", t, exc)
                        rows[t] = row
                        continue
                row.update(outcome="match" if route else "no_match", route=route)
        rows[t] = row
    return list(rows.values())


def _read_plan(plan: dict[date, list[str]], frames: dict, uni, benchmark: str, feed: str) -> list[dict]:
    """Every (stock, session) pair the plan names, read session by session."""
    rows: list[dict] = []
    for day in sorted(plan):
        rows.extend(_read(sorted(set(plan[day])), frames, day, uni, benchmark, feed))
    return rows


def night(previous_run, frames: dict, session: date, uni, *, closed: bool, benchmark: str,
          names_max: int, feed: str, sessions_max: int) -> dict:
    """The previous publication's stale stocks read again from this run's fetch,
    at every session each one missed. Never raises."""
    day = None
    try:
        if closed:
            return _block(NOT_APPLICABLE, "closed_session", None, [])
        if not isinstance(previous_run, dict):
            return _block(NOT_APPLICABLE, "no_previous_record", None, [])
        if previous_run.get("session_state") != "open":
            return _block(NOT_APPLICABLE, "previous_not_open", None, [])
        if previous_run.get("session") == session.isoformat():
            # a re-run of the same session: the record it replaces read the
            # sessions before; its stock-sessions are read again from THIS
            # fetch, so a late bar that arrived since is seen. A block it did
            # not apply is carried as it stands: there was nothing to read.
            carried = previous_run.get("stale_followup")
            if not isinstance(carried, dict) or shape_faults(carried, session, names_max, sessions_max):
                return _block(NOT_APPLICABLE, "rerun_without_block", None, [])
            if carried["status"] != APPLIED:
                return deepcopy(carried)
            day = sessions.previous_session(session)
            plan: dict[date, list[str]] = {}
            for r in carried["rows"]:
                plan.setdefault(date.fromisoformat(r["session"]), []).append(r["ticker"])
            block = _block(APPLIED, None, day.isoformat(), _read_plan(plan, frames, uni, benchmark, feed))
            return _block(FAILED, "invalid_block", day.isoformat(), []) if shape_faults(block, session, names_max, sessions_max) else block
        day = sessions.previous_session(session)
        if previous_run.get("session") != day.isoformat():
            return _block(NOT_APPLICABLE, "previous_not_adjacent", None, [])
        reason, stocks, endings = _membership(previous_run, benchmark)
        if reason:
            return _block(NOT_APPLICABLE, reason, day.isoformat(), [])
        plan = {}
        for t in stocks:
            for d in missed_sessions(endings.get(t), day, sessions_max):
                plan.setdefault(d, []).append(t)
        block = _block(APPLIED, None, day.isoformat(), _read_plan(plan, frames, uni, benchmark, feed))
        if shape_faults(block, session, names_max, sessions_max):
            return _block(FAILED, "invalid_block", day.isoformat(), [])
        return block
    except Exception as exc:  # noqa: BLE001 -- accounting about a previous night never stops this one
        log.error("the stale follow-up stopped on %s: %s", type(exc).__name__, exc)
        block = _block(FAILED, "error", day.isoformat() if day else None, [])
        block["error_class"] = type(exc).__name__
        block["sentence"] = sentence_of(block)
        return block


# ------------------------------------------------------------- sentences ----

def _n(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


def _match_rows(block: dict) -> list[dict]:
    return [r for r in block["rows"] if r["outcome"] == "match"]


def matches_named(block: dict) -> str:
    """Every late bar that would have been listed, as ticker (session, route),
    in row order: the problem's words and the sentence's."""
    return ", ".join(f"{r['ticker']} ({r['session']}, {ROUTE_WORDS[r['route']]})" for r in _match_rows(block))


def sentence_of(block: dict) -> str | None:
    """The block in words, composed from its counts, sessions and tickers only;
    it names no cause for a missing bar and never calls a late bar a signal.
    One session read keeps the words of the first version; more than one says
    the span and counts readings, one per stock and session."""
    status, reason, day = block.get("status"), block.get("reason"), block.get("for_session")
    if status == FAILED:
        what = f"without a {day} bar" if day else "without a bar"
        why = f"the check stopped on an error ({block['error_class']})" if block.get("error_class") \
            else "the check's own result was malformed"
        return f"The previous publication's stocks {what} could not be read again by this run; {why}."
    if status == NOT_APPLICABLE:
        return {
            "membership_not_recorded": "The previous publication did not record which stocks lacked a bar, so none was read again.",
            "membership_over_bound": "The previous publication's stocks without a bar were more than this check reads, so none was read again.",
            "membership_mismatch": "The previous publication's list of stocks without a bar did not match its own count and digest, so none was read again.",
        }.get(reason)
    o = block["outcomes"]
    read = block.get("sessions") or []
    single = len(read) <= 1
    arrived = sum(o[k] for k in ARRIVED)
    parts = []
    if arrived:
        if single:
            parts.append(f"{_n(arrived, 'now carries', 'now carry')} a {day} bar ({block['zero_volume']} with zero volume)")
        else:
            parts.append(f"{_n(arrived, 'reading now carries', 'readings now carry')} the session's bar "
                         f"({block['zero_volume']} with zero volume)")
        matches = _match_rows(block)
        if matches:
            if single:
                named = ", ".join(f"{r['ticker']} ({ROUTE_WORDS[r['route']]})" for r in matches)
                parts.append(f"{named} would have been listed in that publication, which did not include "
                             f"{'it' if len(matches) == 1 else 'them'}")
            else:
                parts.append(f"{matches_named(block)} would have been listed in the publication for that session, "
                             f"which did not include {'it' if len(matches) == 1 else 'them'}")
        if o["no_match"] == arrived:
            parts.append("none of them would have been listed")
        elif o["no_match"]:
            parts.append(f"{_n(o['no_match'], 'would', 'would')} not have been listed")
        if o["unmeasurable"]:
            parts.append(f"{_n(o['unmeasurable'], 'cannot', 'cannot')} be measured on it (a missing or unreadable bar beside it)")
        if o["price_excluded"]:
            parts.append(f"{_n(o['price_excluded'], 'falls', 'fall')} under the ${universe.MIN_PRICE:g} session-close policy")
    if o["still_missing"]:
        parts.append(f"{_n(o['still_missing'], 'still has', 'still have')} no {day} bar" if single
                     else f"{_n(o['still_missing'], 'reading still finds', 'readings still find')} no bar for the session")
    if o["no_frame"]:
        parts.append(f"{_n(o['no_frame'], 'returned', 'returned')} no frame this run")
    if o["not_selected"]:
        parts.append(f"{_n(o['not_selected'], 'is', 'are')} not in this run's selection, so "
                     f"{'its' if o['not_selected'] == 1 else 'their'} {day if single else 'missed'} "
                     f"bar{'' if single and o['not_selected'] == 1 else 's'} {'is' if single and o['not_selected'] == 1 else 'are'} unknown")
    if single:
        head = (f"The {day} publication's {_n(block['count'], 'stock', 'stocks')} without a {day} bar, read again "
                f"from this run's split-adjusted fetch: ")
    else:
        head = (f"The {day} publication's {_n(block['stocks'], 'stock', 'stocks')} without a bar, read again from this "
                f"run's split-adjusted fetch at each of the {_n(len(read), 'session', 'sessions')} missed "
                f"({read[0]} to {read[-1]}), one reading per stock and session, {_n(block['count'], 'reading', 'readings')} in all: ")
    return head + "; ".join(parts) + (". A late bar is the bar the provider served at this run's check; it never "
                                       "becomes a signal, plan or ticket.")


# ------------------------------------------------------------ validation ----

def shape_faults(block, session: date, names_max: int, sessions_max: int) -> list[str]:
    """The block's own shape, one level in: its words, its counts, its rows,
    and that every session it read lies within the bound before this one."""
    try:
        if block.get("version") != VERSION or block.get("status") not in STATUSES:
            return ["stale follow-up version or status unknown"]
        if block.get("reason") is not None and block["reason"] not in REASONS:
            return ["stale follow-up reason unknown"]
        if (block["status"] == APPLIED) != (block["reason"] is None):
            return ["stale follow-up status and reason disagree"]
        o, rows = block["outcomes"], block["rows"]
        if set(o) != set(OUTCOMES) or any(type(v) is not int or v < 0 for v in o.values()):
            return ["stale follow-up outcomes are malformed"]
        if not (sum(o.values()) == block["count"] == len(rows)) or block["count"] > names_max * max(int(sessions_max or 0), 1):
            return ["stale follow-up counts do not reconcile"]
        keys = [_row_key(r) for r in rows]
        if keys != sorted(set(keys)) or not all(isinstance(t, str) and isinstance(s, str) for t, s in keys):
            return ["stale follow-up rows are not sorted and unique"]
        if block["stocks"] != len({t for t, _ in keys}):
            return ["stale follow-up stock count is not its rows'"]
        if block["sessions"] != sorted({s for _, s in keys}):
            return ["stale follow-up sessions are not its rows'"]
        for r in rows:
            if r["outcome"] not in OUTCOMES or (r["route"] in ROUTES) != (r["outcome"] == "match"):
                return ["stale follow-up row outcome or route is malformed"]
            if not (r["volume"] is None or (type(r["volume"]) is int and r["volume"] >= 0)) or r["flat"] not in (None, True, False):
                return ["stale follow-up row volume or flat is malformed"]
            if r["outcome"] not in ARRIVED and (r["volume"] is not None or r["flat"] is not None):
                return ["stale follow-up row reads a bar that did not arrive"]
            if o[r["outcome"]] != sum(1 for x in rows if x["outcome"] == r["outcome"]):
                return ["stale follow-up outcomes are not its rows'"]
        if block["matched"] != sorted({r["ticker"] for r in rows if r["outcome"] == "match"}):
            return ["stale follow-up matched is not its matching rows"]
        arrived_rows = [r for r in rows if r["outcome"] in ARRIVED]
        if (block["zero_volume"] != sum(1 for r in arrived_rows if r["volume"] == 0)
                or block["flat"] != sum(1 for r in arrived_rows if r["flat"] is True)):
            return ["stale follow-up zero-volume or flat counts are not its rows'"]
        if block["status"] == APPLIED:
            previous = sessions.previous_session(session)
            if block["for_session"] != previous.isoformat():
                return ["stale follow-up is not for the session before this one"]
            allowed = {d.isoformat() for d in sessions.sessions_before(previous + timedelta(days=1), max(int(sessions_max or 0), 1))}
            if not set(block["sessions"]) <= allowed:
                return ["stale follow-up reads a session outside the bound before this one"]
        if block["status"] != APPLIED and rows:
            return ["stale follow-up carries rows it did not apply"]
        if block.get("sentence") != sentence_of(block):
            return ["stale follow-up sentence is not its own"]
        return []
    except (KeyError, TypeError, ValueError, AttributeError):
        return ["stale follow-up block is malformed"]


def faults(run: dict, pipeline_rules) -> list[str]:
    """The follow-up held to the record it sits in: present under rules that
    write it, well formed, and a late bar that would have been listed named
    coverage_thin. A record made under older rules is not asked for one."""
    if (not isinstance(pipeline_rules, dict) or "stale_tolerance_fraction" not in pipeline_rules
            or "stale_sessions_max" not in pipeline_rules):
        return []
    cov = run.get("coverage")
    if not isinstance(cov, dict) or "version" not in cov:
        return []
    block = run.get("stale_followup")
    if block is None:
        return ["stale follow-up block missing"]
    try:
        session = date.fromisoformat(run["session"])
        found = shape_faults(block, session, pipeline_rules["stale_names_max"], pipeline_rules["stale_sessions_max"])
    except (KeyError, TypeError, ValueError, AttributeError):
        return ["stale follow-up block is malformed"]
    if found:
        return found
    kinds = {p.get("kind") for p in run.get("problems") or [] if isinstance(p, dict)}
    if block["matched"] and "coverage_thin" not in kinds:
        return ["a late bar that would have been listed is not named coverage_thin"]
    return []
