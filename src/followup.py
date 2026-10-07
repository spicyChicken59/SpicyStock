"""The next night's read of the previous night's stale stocks.

A stock the evening fetch returned without a bar for its session is stale:
its inputs that night are unknown, never a measured non-match. The run that
follows reads each of last night's stale stocks again, from the frames it
fetched for its OWN session, with no extra provider call: did the previous
session's bar arrive since, how much volume does it carry, and measured at
that session by the evening's own rules (the session rules, the price
policy, ``scans.scan_all``), would it have matched a scan?

It is accounting about a previous publication, never a signal: the previous
session's entry window has passed, so a late bar never becomes a burst, an
observation, a plan or a ticket, and the previous record, its history and its
ledger entry are never touched. A late bar that WOULD have matched a scan is
named, and makes the night that finds it degraded. A stock that left tonight's
selection is not re-requested; its bar stays unknown. No sentence states a
cause (a halt, a delisting, a name that did not trade): the bar is what the
provider served at tonight's check, and nothing more is known.

``night()`` never raises: a defect anywhere in it is a ``failed`` block with
the error's class, and the night publishes as it would have without it.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import logging
import math

import pandas as pd

from src import market_data, scans, sessions, universe

log = logging.getLogger("spicystock.followup")

VERSION = 1
APPLIED, NOT_APPLICABLE, FAILED = "applied", "not_applicable", "failed"
STATUSES = (APPLIED, NOT_APPLICABLE, FAILED)
#: what became of each of last night's stale stocks
OUTCOMES = ("no_match", "match", "unmeasurable", "price_excluded", "still_missing", "no_frame", "not_selected")
#: the outcomes of a stock whose bar for the previous session has arrived
ARRIVED = ("no_match", "match", "unmeasurable", "price_excluded")
#: why a block is not applied, or why it failed
REASONS = ("none_missing", "closed_session", "no_previous_record", "previous_not_open",
           "previous_not_adjacent", "rerun_without_block", "membership_not_recorded",
           "membership_over_bound", "membership_mismatch", "error", "invalid_block")
ROUTES = ("both", "burst", "dollar")
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


def _block(status: str, reason: str | None, for_session: str | None, rows: list[dict]) -> dict:
    rows = sorted(rows, key=lambda r: r["ticker"])
    arrived = [r for r in rows if r["outcome"] in ARRIVED]
    block = {
        "version": VERSION, "status": status, "reason": reason, "for_session": for_session,
        "count": len(rows), "outcomes": {o: sum(1 for r in rows if r["outcome"] == o) for o in OUTCOMES},
        "zero_volume": sum(1 for r in arrived if r["volume"] == 0),
        "flat": sum(1 for r in arrived if r["flat"] is True),
        "matched": sorted(r["ticker"] for r in rows if r["outcome"] == "match"),
        "rows": rows,
    }
    block["sentence"] = sentence_of(block)
    return block


def _membership(previous_run: dict, benchmark: str) -> tuple[str | None, list[str]]:
    """Last night's full stale membership, checked against its own ledger;
    a reason when it cannot be read, the stocks otherwise."""
    tol = previous_run.get("input_tolerance")
    if not isinstance(tol, dict) or "names" not in tol:
        return "membership_not_recorded", []
    names = tol["names"]
    if names is None:
        return "membership_over_bound", []
    stale = ((previous_run.get("coverage") or {}).get("reasons") or {}).get("stale") or {}
    if (not isinstance(names, list) or not all(isinstance(n, str) for n in names)
            or len(names) != stale.get("count") or universe.identity(names) != stale.get("identity")):
        return "membership_mismatch", []
    stocks = sorted(set(names) - {benchmark})
    return (None, stocks) if stocks else ("none_missing", [])


def _read(stocks: list[str], frames: dict, day: date, uni, benchmark: str, feed: str) -> list[dict]:
    """Each stock's outcome at ``day``, read from tonight's frames by the
    evening's own rules for that session."""
    rows, arrived = {}, {}
    for t in stocks:
        if t not in uni.symbols:
            rows[t] = {"ticker": t, "outcome": "not_selected", "volume": None, "flat": None, "route": None}
        elif t not in frames:
            rows[t] = {"ticker": t, "outcome": "no_frame", "volume": None, "flat": None, "route": None}
        else:
            upto = _through(frames[t], day)
            if upto is None:
                rows[t] = {"ticker": t, "outcome": "still_missing", "volume": None, "flat": None, "route": None}
            else:
                arrived[t] = upto
    ready = market_data.apply_session_rules(arrived, day, market_data.DownloadStats(session=day, feed=feed))
    eligible, excluded = universe.session_eligible(ready, uni, exempt=(benchmark,))
    for t, upto in arrived.items():
        volume, flat = _bar_facts(upto)
        row = {"ticker": t, "outcome": "unmeasurable", "volume": volume, "flat": flat, "route": None}
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
                row.update(outcome="match" if route else "no_match", route=route)
        rows[t] = row
    return list(rows.values())


def night(previous_run, frames: dict, session: date, uni, *, closed: bool, benchmark: str,
          names_max: int, feed: str) -> dict:
    """Last night's stale stocks read again from tonight's fetch. Never raises."""
    day = None
    try:
        if closed:
            return _block(NOT_APPLICABLE, "closed_session", None, [])
        if not isinstance(previous_run, dict):
            return _block(NOT_APPLICABLE, "no_previous_record", None, [])
        if previous_run.get("session_state") != "open":
            return _block(NOT_APPLICABLE, "previous_not_open", None, [])
        if previous_run.get("session") == session.isoformat():
            # a re-run of the same session: the record it replaces carries the
            # follow-up of the session before, which this run cannot re-read
            carried = previous_run.get("stale_followup")
            if isinstance(carried, dict) and not shape_faults(carried, session, names_max):
                return deepcopy(carried)
            return _block(NOT_APPLICABLE, "rerun_without_block", None, [])
        day = sessions.previous_session(session)
        if previous_run.get("session") != day.isoformat():
            return _block(NOT_APPLICABLE, "previous_not_adjacent", None, [])
        reason, stocks = _membership(previous_run, benchmark)
        if reason:
            return _block(NOT_APPLICABLE, reason, day.isoformat(), [])
        block = _block(APPLIED, None, day.isoformat(), _read(stocks, frames, day, uni, benchmark, feed))
        if shape_faults(block, session, names_max):
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


def sentence_of(block: dict) -> str | None:
    """The block in words, composed from its counts and tickers only; it
    names no cause for a missing bar and never calls a late bar a signal."""
    status, reason, day = block.get("status"), block.get("reason"), block.get("for_session")
    if status == FAILED:
        what = f"without a {day} bar" if day else "without a bar"
        why = f"the check stopped on an error ({block['error_class']})" if block.get("error_class") \
            else "the check's own result was malformed"
        return f"Last night's stocks {what} could not be checked tonight; {why}."
    if status == NOT_APPLICABLE:
        return {
            "membership_not_recorded": "Last night's run did not record which stocks lacked a bar, so none was checked tonight.",
            "membership_over_bound": "Last night's stocks without a bar were more than this check reads, so none was checked tonight.",
            "membership_mismatch": "Last night's list of stocks without a bar did not match its own count and digest, so none was checked tonight.",
        }.get(reason)
    o = block["outcomes"]
    arrived = sum(o[k] for k in ARRIVED)
    parts = []
    if arrived:
        parts.append(f"{_n(arrived, 'now carries', 'now carry')} a {day} bar ({block['zero_volume']} with zero volume)")
        if block["matched"]:
            routes = {r["ticker"]: r["route"] for r in block["rows"] if r["outcome"] == "match"}
            named = ", ".join(f"{t} ({routes[t]})" for t in block["matched"])
            parts.append(f"{named} {'matches' if len(block['matched']) == 1 else 'match'} a scan on it, "
                         f"which the {day} publication did not include")
        elif o["no_match"] == arrived:
            parts.append("none of them matches a scan")
        elif o["no_match"]:
            parts.append(f"{_n(o['no_match'], 'matches', 'match')} no scan on it")
        if o["unmeasurable"]:
            parts.append(f"{_n(o['unmeasurable'], 'cannot', 'cannot')} be measured on it (a missing or unreadable bar beside it)")
        if o["price_excluded"]:
            parts.append(f"{_n(o['price_excluded'], 'falls', 'fall')} under the ${universe.MIN_PRICE:g} session-close policy")
    if o["still_missing"]:
        parts.append(f"{_n(o['still_missing'], 'still has', 'still have')} no {day} bar")
    if o["no_frame"]:
        parts.append(f"{_n(o['no_frame'], 'returned', 'returned')} no frame tonight")
    if o["not_selected"]:
        parts.append(f"{_n(o['not_selected'], 'is', 'are')} not in tonight's selection, so "
                     f"{'its' if o['not_selected'] == 1 else 'their'} {day} bar is unknown")
    return (f"Last night's {_n(block['count'], 'stock', 'stocks')} without a {day} bar, read again from "
            f"tonight's fetch: " + "; ".join(parts) + ". A late bar is the bar the provider served at "
            "tonight's check; it never becomes a signal, plan or ticket.")


# ------------------------------------------------------------ validation ----

def shape_faults(block, session: date, names_max: int) -> list[str]:
    """The block's own shape, one level in: its words, its counts, its rows."""
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
        if not (sum(o.values()) == block["count"] == len(rows)) or block["count"] > names_max:
            return ["stale follow-up counts do not reconcile"]
        tickers = [r["ticker"] for r in rows]
        if tickers != sorted(set(tickers)) or not all(isinstance(t, str) for t in tickers):
            return ["stale follow-up rows are not sorted and unique"]
        for r in rows:
            if r["outcome"] not in OUTCOMES or (r["route"] in ROUTES) != (r["outcome"] == "match"):
                return ["stale follow-up row outcome or route is malformed"]
            if not (r["volume"] is None or (type(r["volume"]) is int and r["volume"] >= 0)) or r["flat"] not in (None, True, False):
                return ["stale follow-up row volume or flat is malformed"]
            if r["outcome"] not in ARRIVED and (r["volume"] is not None or r["flat"] is not None):
                return ["stale follow-up row reads a bar that did not arrive"]
            if o[r["outcome"]] != sum(1 for x in rows if x["outcome"] == r["outcome"]):
                return ["stale follow-up outcomes are not its rows'"]
        arrived = sum(o[k] for k in ARRIVED)
        if block["matched"] != sorted(r["ticker"] for r in rows if r["outcome"] == "match"):
            return ["stale follow-up matched is not its matching rows"]
        if block["zero_volume"] > arrived or block["flat"] > arrived:
            return ["stale follow-up counts more late bars than arrived"]
        if block["status"] == APPLIED and block["for_session"] != sessions.previous_session(session).isoformat():
            return ["stale follow-up is not for the session before this one"]
        if block["status"] != APPLIED and rows:
            return ["stale follow-up carries rows it did not apply"]
        if block.get("sentence") != sentence_of(block):
            return ["stale follow-up sentence is not its own"]
        return []
    except (KeyError, TypeError, ValueError, AttributeError):
        return ["stale follow-up block is malformed"]


def faults(run: dict, pipeline_rules) -> list[str]:
    """The follow-up held to the record it sits in: present under rules that
    write it, well formed, and a late bar that matched a scan named
    coverage_thin. A record made under older rules is not asked for one."""
    if not isinstance(pipeline_rules, dict) or "stale_tolerance_fraction" not in pipeline_rules:
        return []
    cov = run.get("coverage")
    if not isinstance(cov, dict) or "version" not in cov:
        return []
    block = run.get("stale_followup")
    if block is None:
        return ["stale follow-up block missing"]
    try:
        session = date.fromisoformat(run["session"])
        found = shape_faults(block, session, pipeline_rules["stale_names_max"])
    except (KeyError, TypeError, ValueError, AttributeError):
        return ["stale follow-up block is malformed"]
    if found:
        return found
    kinds = {p.get("kind") for p in run.get("problems") or [] if isinstance(p, dict)}
    if block["matched"] and "coverage_thin" not in kinds:
        return ["a late bar that matched a scan is not named coverage_thin"]
    return []
