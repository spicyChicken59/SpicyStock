"""The model's own record, read for what it does and does not establish.

``record.scorecard()`` counts the retained tickets and sums their R. Three
things it does not say, and a reader who weighs the record needs (the daily
brief carries this block verbatim):

* **How many setups the tickets are.** A setup the list offers again on a
  later night is a new pick and is counted again. ``setups()`` chains a
  ticket to the previous ticket of the same ticker and kind when it was
  issued inside that one's ``record.OPEN_PLAN_SESSIONS`` sessions and that
  one has no fill known (``REISSUE_AFTER``); the counts are given by ticket
  and by setup.
* **Which model account each ticket was sized against.** R counts every
  ticket as one unit whatever its size, and the account has changed inside
  the window, so a sum of R is not a sum of dollars. ``account_of()`` reads
  the publishing record's own account for a ticket this publication issued,
  else what the previous brief carried for that evidence id, else
  ``SEED_ACCOUNTS`` (read off the publications in git, by the context digest
  each pick carries), else it is unknown and is not guessed.
* **What a stop booked at exactly the stop price leaves out.**
  ``plan.follow()`` books a stop first reached inside a session at the stop.
  ``stop_bounds()`` puts the same exit at that session's close and at its
  low beside the booked figure, and, where that session's minute bars are
  retained, at the low of the first minute that reached the stop.

Beside those three: what a one-share ticket that sold whole at the half-sale
step reads at two shares (``one_share()``), what an uncertain ticket would
read had it filled at its limit or its trigger (``uncertain_bounds()``, bounds
and never results), and the counted tickets a later run of their own session
withdrew (``withdrawn_by_ledger()``, off the quality ledger).

Every walk is the scorecard's own: ``record.later_bars()``,
``record.replay()`` and ``record.r_multiple()`` over the same bars and
minute evidence, bucketed as ``record.scorecard_rows()`` buckets. A ticket
whose bucket or R differs from the scorecard's row, or totals that are not
the published scorecard's, make the block ``unreconciled`` with the reason,
and its sentences are withheld.

Nothing here is a strategy number and nothing here changes a record: the
block is derived, deterministic for its inputs and reads no clock.
``python -m src.model_record --docs docs`` builds it from the record's own
observations block, without market data; a ticket whose bars the record no
longer carries is marked and takes its bucket and R from the publication's
quality-ledger row.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import sys
import zlib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from src import intraday, plan, quality_ledger, record
from src import sessions as exchange_sessions

VERSION = 1
COMPUTED, UNRECONCILED = "computed", "unreconciled"

#: the scorecard's bucket names this module reads by name (``record.SCORECARD_BUCKETS``)
SETTLED, OPEN, PENDING, UNMEASURED, UNSCORED = "settled", "open", "pending", "unmeasured", "unscored"
#: a later ticket of the same ticker and kind is the same setup issued again
#: when the ticket before it is in one of these: no fill of it is known
REISSUE_AFTER = (record.NOT_FILLED, PENDING, UNMEASURED)
#: the levels and the size compared between one issue of a setup and the next
ISSUE_FIELDS = ("trigger", "limit", "stop", "shares")

#: where the bars came from
FRAMES, OBSERVATIONS = "frames", "record_observations"
#: how one ticket's bars were read
WALKED, NOT_CARRIED = "walked", "not_carried"

#: where a ticket's account came from
RECORD, CARRIED, SEED, UNKNOWN = "record", "carried", "seed", "unknown"
BRIEF_FILE = "brief.json"          # the daily brief; the previous one is read for its carried accounts
BRIEF_BLOCK = "model_record"       # this block's name inside it
BRIEF_MAX_BYTES = 32 * 1024 * 1024  # a previous brief past this is not read
SEED_PREFIX_CHARS = 16
#: The account of each publication that issued one of the 22 tickets retained
#: on 17 November 2026, by the first ``SEED_PREFIX_CHARS`` characters of the
#: context digest its picks carry (``evidence_ref.context_sha256``): (equity,
#: risk percent). Read off ``account`` in the one ``docs/data.json`` commit
#: whose ``run.evidence.context_sha256`` is that digest, on 19 November 2026.
#: The 8 October session was published twice: its retained picks are the first
#: run's, at $10,000, and its second run was the first at $2,000.
SEED_ACCOUNTS: dict[str, tuple[float, float]] = {
    "d8f6c9d7874b52ef": (10000.0, 0.5),   # session 2026-10-08, commit 1e1ffe9c
    "a04403d17c33a22e": (2000.0, 0.5),    # session 2026-10-09, commit 62bce72d
    "4a009a56628d0d24": (2000.0, 0.5),    # session 2026-10-27, commit 36ce7ef9
    "186e2c8facab9f5b": (2000.0, 0.5),    # session 2026-10-28, commit dbb8358c
    "23bffad9b461c69f": (2000.0, 0.5),    # session 2026-10-29, commit cd6418f1
    "b7e165b5b93ea068": (2000.0, 0.5),    # session 2026-11-02, commit 3cd890ec
    "0a59de7d0e6e8635": (30000.0, 0.5),   # session 2026-11-04, commit a0d9172e
    "47d32156da80daca": (30000.0, 0.5),   # session 2026-11-09, commit 6331513e
    "a2aaa5851ec5f14c": (30000.0, 0.5),   # session 2026-11-10, commit f34cfb79
    "be355016afb76432": (30000.0, 0.5),   # session 2026-11-11, commit ca642303
    "184474cde2ce0617": (30000.0, 0.5),   # session 2026-11-13, commit 3a27d70c
}

#: the events that end a walk on a stop (``plan.follow()``)
STOPPED = "stopped"                # the walk's status when a stop ended it
STOP_AT_LEVEL, STOP_AT_OPEN = "stopped", "stopped_at_open"
STOP_EVENTS = (STOP_AT_LEVEL, STOP_AT_OPEN)
HALF_SALE = "sell_half"
ONE_SHARE = 1                      # a position that cannot be halved
SENSITIVITY_SHARES = 2             # the smallest position that can: the size the same bars are walked at

#: where a withdrawn ticket was found
LEDGER, SCANNED, SKIPPED = "quality_ledger", "scanned", "skipped"
#: (P) the ledger is scanned whole or not at all: past this many entries it is
#: skipped and said so. Measured on 19 November 2026 over 45 entries (45 MB
#: expanded): each entry is expanded and its publication block read, and only
#: the entries of a ticket's session are parsed whole.
LEDGER_SCAN_MAX_ENTRIES = 1024
LEDGER_SUFFIX = ".json.gz"
RECONCILE_REASONS_MAX = 5          # the reasons an unreconciled block names; the rest are counted
PUBLICATION_MARKER = '"publication":'

BUCKET_WORDS = {
    SETTLED: "settled", OPEN: "open", PENDING: "awaiting first session", record.UNCERTAIN: "uncertain",
    record.NOT_FILLED: "not filled", UNMEASURED: "missing or stale bars", record.UNREADABLE: "unreadable",
    UNSCORED: "ended without a reconciled result",
}
STOP_LABELS = {
    "booked": "what the model books: a stop first reached inside a session at exactly the stop price, and a "
              "session that opens at or under the stop at its open",
    "at_close": "the same exit at that session's close: what holding to the close would have been, and not "
                "a fill estimate",
    "at_low": "the same exit at that session's low: a worst-case bound for a stop order filled that day",
    "minute": "where that session's minute bars are retained, the first minute at or under the stop: a stop "
              "order filled inside that minute would be between its low and the stop",
}
UNCERTAIN_LABEL = ("bounds, not results: the bars cannot say whether the ticket filled, so each is the whole "
                   "daily bars walked as if it had filled at that price, and neither is in any sum")
ONE_SHARE_LABEL = (f"a sensitivity, not a result: the same bars and minute evidence walked at "
                   f"{SENSITIVITY_SHARES} shares, the smallest position the half-sale step can halve")
DEFINITIONS = [
    "A ticket is one night's order for one stock. The scorecard counts every retained ticket once.",
    (f"A setup is a chain of tickets of one ticker and kind: a ticket continues the chain when it was issued "
     f"within {record.OPEN_PLAN_SESSIONS} sessions after the ticket before it and that one has no fill known "
     f"(not filled, awaiting its first session, or without bars). A setup's bucket is its last ticket's."),
    "An era is the tickets sized against one model account (equity and risk percent).",
    ("R is a settled ticket's model result over its risk at the model entry (the entry less the published "
     "stop, on the whole position), every sale weighted by the whole shares it sold. It counts each ticket as "
     "one unit whatever its size."),
    "Model dollars are a settled ticket's sale prices less its model entry, times the shares sold.",
]


# ---------------------------------------------------------------- helpers ----

def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _positive(value: Any) -> bool:
    return _finite(value) and value > 0


def _money(value: float) -> float:
    return plan._money(value)


def _usd(value: float) -> str:
    """Signed dollars, the sign before the symbol."""
    return f"{'-' if value < 0 else '+'}${abs(value):,.2f}"


def _r(value: float) -> str:
    return f"{value:+.2f}R"


def _n(count: int, word: str, many: str | None = None) -> str:
    return f"{count} {word if count == 1 else many or word + 's'}"


def _sum_r(values: list[float]) -> float | None:
    """A sum of R as ``record.summarize_scorecard()`` sums it: None of nothing."""
    return round(math.fsum(values), 2) if values else None


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    """One ticket: its ticker, kind and signal session (what ``record.append()`` keys a pick by)."""
    return row["ticker"], row["kind"], row.get("picked") or row.get("date")


def _name(row: Mapping[str, Any]) -> str:
    return f"{row['ticker']} {row['picked']}"


def _evidence(pick: Mapping[str, Any]) -> tuple[str | None, str | None]:
    """The pick's evidence id and context digest, each a string or None."""
    ref = _dict(pick.get("evidence_ref"))
    return (ref.get("id") if isinstance(ref.get("id"), str) else None,
            ref.get("context_sha256") if isinstance(ref.get("context_sha256"), str) else None)


def _bucket_counts(rows: list[Mapping[str, Any]]) -> dict[str, int]:
    return {name: sum(r["bucket"] == name for r in rows) for name in record.SCORECARD_BUCKETS}


def _bucket_words(counts: Mapping[str, int]) -> str:
    said = [f"{counts[name]} {BUCKET_WORDS[name]}" for name in record.SCORECARD_BUCKETS if counts.get(name)]
    return ", ".join(said) if said else "none"


def _sales(walk: Mapping[str, Any]) -> list[dict]:
    """The walk's sale events: the ones that sold whole shares at a price."""
    return [e for e in walk.get("events", []) if isinstance(e, dict) and _finite(e.get("shares"))
            and e["shares"] > 0 and _finite(e.get("price"))]


def _walk_usd(walk: Mapping[str, Any]) -> float:
    """Model dollars of a walk: each sale's price less the model entry, times the shares it sold."""
    entry = walk["entry_ref"]
    return _money(math.fsum(e["shares"] * (e["price"] - entry) for e in _sales(walk)))


# ------------------------------------------------------------- the walks -----

def measure(pick: Mapping[str, Any], frames: Mapping[str, Any], minutes: Mapping[str, Any],
            session: str) -> dict:
    """One ticket walked as ``record.scorecard_rows()`` walks it: the same
    horizon, bars, replay and R, bucketed by the same rule. Returns the bucket
    beside the walk and the bars it read, which the scorecard row drops."""
    horizon = [str(d) for d in exchange_sessions.next_sessions(date.fromisoformat(pick["date"]),
                                                               record.OPEN_PLAN_SESSIONS)]
    through = min(session, horizon[-1])
    bars = record.later_bars(frames.get(pick["ticker"]), pick["date"], through)
    out = {"horizon": horizon[-1], "bars": bars, "walk": None, "status": None, "r": None, "uncertainty": None,
           "filled": False, "through": bars[-1]["date"] if bars else None,
           "complete": [b["date"] for b in bars] == [d for d in horizon if d <= through]}
    if pick["date"] == session:
        out["bucket"] = PENDING
    elif not bars:
        out["bucket"] = UNMEASURED
    else:
        walk = out["walk"] = record.replay(pick, bars, "green", minutes.get(intraday.key(pick)))
        status = out["status"] = walk["status"]
        out["uncertainty"] = walk.get("uncertainty")
        if status in (record.UNCERTAIN, record.NOT_FILLED, record.UNREADABLE):
            out["bucket"] = status
        else:
            out["filled"] = True
            if status in record.SETTLED:
                out["r"] = record.r_multiple(walk, pick["stop"])
                out["bucket"] = SETTLED if out["r"] is not None else UNSCORED
            else:
                out["bucket"] = OPEN if bars[-1]["date"] == through else UNMEASURED
    return out


def _plan_row(pick: Mapping[str, Any], read: Mapping[str, Any]) -> dict:
    """One ticket's public row: its levels and size, its bucket and R, and
    what the walk booked."""
    levels = record.ticket_levels(pick)
    limit = float(levels["limit"]) if _finite(levels["limit"]) else None
    shares = pick["shares"]
    walk = read["walk"]
    filled = bool(read["filled"]) and walk is not None
    sales = _sales(walk) if filled else []
    evidence_id, _ = _evidence(pick)
    return {
        "ticker": pick["ticker"], "kind": pick["kind"], "picked": pick["date"], "evidence_id": evidence_id,
        "grade": pick.get("grade"), "regime": pick.get("regime"), "shares": shares,
        "trigger": levels["trigger"], "limit": limit, "stop": levels["stop"],
        "planned_risk_usd": None if limit is None else _money(shares * (limit - levels["stop"])),
        "bucket": read["bucket"], "status": read["status"], "r": read["r"], "uncertainty": read["uncertainty"],
        "bars": WALKED if walk is not None else None, "through": read["through"], "horizon": read["horizon"],
        "fill": walk.get("fill") if walk is not None else None,
        "entry": walk["entry_ref"] if filled else None,
        "exit_price": walk.get("exit_price") if filled else None,
        "sales": [{k: e.get(k) for k in ("day", "date", "event", "price", "shares", "remaining")} for e in sales],
        "model_usd": _walk_usd(walk) if filled and read["bucket"] == SETTLED else None,
        "risk_at_fill_usd": (_money(shares * (walk["entry_ref"] - levels["stop"]))
                             if filled and read["bucket"] == SETTLED else None),
        "minute_evidence": walk.get("minute_evidence") if walk is not None else None,
        "minute_fill": bool(filled and walk.get("minute_evidence")),
    }


def _recorded(pick: Mapping[str, Any], read: Mapping[str, Any], recorded: Mapping[str, Any]
              ) -> tuple[dict, dict]:
    """A ticket whose bars these frames no longer carry: its bucket and R are
    the recorded row's, and nothing of a walk is claimed. Returns the reading
    with no walk and the ticket's row."""
    read = {**read, "walk": None,
            **{name: recorded.get(name) for name in ("bucket", "status", "r", "uncertainty", "through")}}
    row = _plan_row(pick, read)
    row.update(bars=NOT_CARRIED, minute_evidence=recorded.get("minute_evidence"),
               minute_fill=bool(recorded.get("filled") and recorded.get("minute_evidence")))
    return read, row


# ------------------------------------------------------------ the setups -----

def setups(plans: list[dict]) -> list[dict]:
    """The tickets chained into setups, oldest first; each ticket's row gains
    its setup, its place in it and what changed against the issue before."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in sorted(plans, key=lambda r: (r["picked"], r["ticker"], r["kind"])):
        groups.setdefault((row["ticker"], row["kind"]), []).append(row)
    chains: list[list[dict]] = []
    for group in groups.values():
        chain = [group[0]]
        for row in group[1:]:
            before = chain[-1]
            reach = {str(d) for d in exchange_sessions.next_sessions(date.fromisoformat(before["picked"]),
                                                                     record.OPEN_PLAN_SESSIONS)}
            if row["picked"] in reach and before["bucket"] in REISSUE_AFTER:
                chain.append(row)
            else:
                chains.append(chain)
                chain = [row]
        chains.append(chain)
    chains.sort(key=lambda c: (c[0]["picked"], c[0]["ticker"], c[0]["kind"]))
    out = []
    for chain in chains:
        first, last = chain[0], chain[-1]
        name = intraday.key({"kind": first["kind"], "ticker": first["ticker"], "date": first["picked"]})
        for number, row in enumerate(chain, 1):
            before = chain[number - 2] if number > 1 else None
            row.update(setup=name, issue_no=number, issues=len(chain),
                       changed=[] if before is None else [f for f in ISSUE_FIELDS if row[f] != before[f]])
        out.append({"setup": name, "ticker": first["ticker"], "kind": first["kind"], "first": first["picked"],
                    "last": last["picked"], "issues": len(chain), "tickets": [r["picked"] for r in chain],
                    "bucket": last["bucket"], "r": last["r"],
                    "changed": [r["changed"] for r in chain[1:]]})
    return out


# ----------------------------------------------------------- the accounts ----

def carried_accounts(docs: Path | None) -> tuple[dict[str, tuple[float, float, str]], str | None]:
    """What the previous brief recorded, by evidence id: (equity, risk
    percent, basis). The second value says why nothing could be read."""
    if docs is None:
        return {}, "no docs directory was given"
    path = Path(docs) / BRIEF_FILE
    try:
        if not path.is_file():
            return {}, "no previous brief"
        if path.stat().st_size > BRIEF_MAX_BYTES:
            return {}, "the previous brief is over its read bound"
        brief = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}, "the previous brief could not be read"
    block = _dict(_dict(brief).get(BRIEF_BLOCK))
    if block.get("version") != VERSION or not isinstance(block.get("plans"), list):
        return {}, "the previous brief carries no model record of this version"
    out = {}
    for row in block["plans"]:
        row = _dict(row)
        evidence_id, basis = row.get("evidence_id"), row.get("account_basis")
        if (isinstance(evidence_id, str) and evidence_id and _positive(row.get("issued_equity"))
                and _positive(row.get("risk_pct")) and basis in (RECORD, CARRIED, SEED)):
            out[evidence_id] = (float(row["issued_equity"]), float(row["risk_pct"]),
                                SEED if basis == SEED else CARRIED)
    return out, None


def own_account(data: Mapping[str, Any]) -> tuple[float, float] | None:
    """The record's own model account, or None when it does not carry one."""
    account = _dict(data.get("account"))
    if _positive(account.get("equity")) and _positive(account.get("risk_pct")):
        return float(account["equity"]), float(account["risk_pct"])
    return None


def issued_here(pick: Mapping[str, Any], data: Mapping[str, Any], session: str) -> bool | None:
    """Whether this publication issued the ticket. A ticket of another
    session: no. A ticket of this session whose context digest is the
    publication's own (``provenance.finish()``), or where either digest is
    absent: yes. One of this session carrying another context was issued by
    an earlier run of the session that this run did not issue again: None."""
    if pick["date"] != session:
        return False
    _, context = _evidence(pick)
    own = _dict(_dict(data.get("run")).get("evidence")).get("context_sha256")
    if context is None or not isinstance(own, str) or context == own:
        return True
    return None


def fits(planned_risk_usd: float | None, equity: float, risk_pct: float) -> bool:
    """Whether a ticket can have been sized against this account: its planned
    risk at the limit is never over the account's full risk budget
    (``plan.size()`` floors the shares inside the budget)."""
    if planned_risk_usd is None:
        return True
    try:
        return planned_risk_usd <= plan.Account(equity=equity, risk_pct=risk_pct).risk_usd
    except ValueError:
        return False


def account_of(pick: Mapping[str, Any], row: Mapping[str, Any], data: Mapping[str, Any], session: str,
               carried: Mapping[str, tuple[float, float, str]]) -> tuple[float | None, float | None, str]:
    """The account one ticket was sized against and where that was read:
    the record's own for a ticket this publication issued, else the previous
    brief's by evidence id, else the seed by context digest, else unknown.
    An account the ticket's own planned risk does not fit is not taken."""
    evidence_id, context = _evidence(pick)
    found: list[tuple[float, float, str]] = []
    own = own_account(data)
    if issued_here(pick, data, session) and own is not None:
        found.append((*own, RECORD))
    if evidence_id in carried:
        found.append(carried[evidence_id])
    if context is not None and context[:SEED_PREFIX_CHARS] in SEED_ACCOUNTS:
        found.append((*SEED_ACCOUNTS[context[:SEED_PREFIX_CHARS]], SEED))
    for equity, risk_pct, basis in found:
        if fits(row["planned_risk_usd"], equity, risk_pct):
            return equity, risk_pct, basis
    return None, None, UNKNOWN


def eras(plans: list[dict]) -> list[dict]:
    """The tickets by the model account they were sized against, in the order
    the accounts first appear; the tickets with no known account last. A
    setup is counted in the era of its first ticket."""
    groups: dict[tuple[float | None, float | None], list[dict]] = {}
    for row in sorted(plans, key=lambda r: (r["picked"], r["ticker"], r["kind"])):
        groups.setdefault((row["issued_equity"], row["risk_pct"]), []).append(row)
    out = []
    for (equity, risk_pct), rows in sorted(groups.items(), key=lambda kv: (kv[0][0] is None, kv[1][0]["picked"])):
        settled = [r for r in rows if r["bucket"] == SETTLED]
        rs = [r["r"] for r in settled]
        dollars = [r["model_usd"] for r in settled if r["model_usd"] is not None]
        at_fill = [r["risk_at_fill_usd"] for r in settled if r["risk_at_fill_usd"] is not None]
        planned = [r["planned_risk_usd"] for r in rows if r["planned_risk_usd"] is not None]
        out.append({
            "issued_equity": equity, "risk_pct": risk_pct,
            "label": "account not recorded" if equity is None else f"${equity:,.0f} at {risk_pct:g}% risk",
            "from": rows[0]["picked"], "through": rows[-1]["picked"], "tickets": len(rows),
            "setups": sum(r["issue_no"] == 1 for r in rows),
            "buckets": _bucket_counts(rows), "settled": len(settled),
            "wins": sum(r > 0 for r in rs), "losses": sum(r < 0 for r in rs), "breakeven": sum(r == 0 for r in rs),
            "sum_r": _sum_r(rs),
            "model_usd": _money(math.fsum(dollars)) if dollars else None,
            "model_usd_missing": len(settled) - len(dollars),
            "risk_at_fill_usd": _money(math.fsum(at_fill)) if at_fill else None,
            "planned_risk_usd": ({"min": min(planned), "max": max(planned), "sum": _money(math.fsum(planned))}
                                 if planned else None),
        })
    return out


# -------------------------------------------------------------- the stops ----

def _at(obj: Mapping[str, Any], offset: int) -> str:
    opens = datetime.fromisoformat(obj["opens_at"]).astimezone(exchange_sessions.MARKET_TZ)
    return (opens + timedelta(minutes=offset)).strftime("%H:%M ET")


def stop_bounds(pick: Mapping[str, Any], read: Mapping[str, Any], minute_obj: Mapping[str, Any] | None
                ) -> dict | None:
    """A walk that ended on a stop, read three ways: as booked, with that
    exit at the session's close, and at its low. Only the stop event's price
    moves, so shares sold before it keep their own prices and the R keeps its
    whole-share weights. Where the session's minute bars are retained, the
    first minute at or under the stop from the fill on is named as well."""
    walk = read["walk"]
    if walk is None:
        return None
    index = next((i for i, e in enumerate(walk["events"]) if e.get("event") in STOP_EVENTS
                  and _finite(e.get("shares")) and e["shares"] > 0), None)
    day = None if index is None else next((b for b in read["bars"]
                                           if b["date"] == walk["events"][index]["date"]), None)
    if day is None:
        return None
    event = walk["events"][index]

    def reading(price: float) -> tuple[float | None, float]:
        moved = {**walk, "events": [dict(e, price=price) if i == index else e
                                    for i, e in enumerate(walk["events"])]}
        return record.r_multiple(moved, pick["stop"]), _walk_usd(moved)

    close, low = _money(day["c"]), _money(day["l"])
    (r_close, usd_close), (r_low, usd_low) = reading(close), reading(low)
    out = {"ticker": pick["ticker"], "kind": pick["kind"], "picked": pick["date"], "shares": pick["shares"],
           "date": event["date"], "day": event["day"], "event": event["event"], "stopped_shares": event["shares"],
           "entry": walk["entry_ref"], "stop_price": event["price"], "close": close, "low": low,
           "r": {"booked": read["r"], "at_close": r_close, "at_low": r_low},
           "usd": {"booked": _walk_usd(walk), "at_close": usd_close, "at_low": usd_low},
           "minute": None}
    if (minute_obj is not None and event["event"] == STOP_AT_LEVEL and minute_obj.get("session") == event["date"]
            and isinstance(minute_obj.get("minutes"), list)):
        rows = minute_obj["minutes"]
        # from the fill on: the crossing minute, as intraday.resolve() finds it (the first minute, for a
        # fill at the open)
        trigger = record.ticket_levels(pick)["trigger"]
        start = next((m[0] for m in rows if m[0] < plan.ENTRY_WINDOW_MINUTES and m[2] >= trigger), 0)
        touch = next((m for m in rows if m[0] >= start and m[3] <= event["price"]), None)
        if touch is not None:
            r_minute, usd_minute = reading(_money(touch[3]))
            out["minute"] = {"offset": touch[0], "at": _at(minute_obj, touch[0]), "open": touch[1],
                             "low": touch[3], "opened_at_or_under_stop": touch[1] <= event["price"],
                             "r_at_low": r_minute, "usd_at_low": usd_minute,
                             "evidence": intraday.name_of(minute_obj)}
    return out


def _stops_block(reads: list[tuple[Mapping[str, Any], Mapping[str, Any]]], minutes: Mapping[str, Any],
                 plans: list[dict]) -> dict:
    rows = [b for pick, read in reads
            if (b := stop_bounds(pick, read, minutes.get(intraday.key(pick)))) is not None]
    by_ticket = {_key(b): b for b in rows}
    settled = [p for p in plans if p["bucket"] == SETTLED]
    names = ("booked", "at_close", "at_low")
    # a settled stop whose bars these frames do not carry cannot be read again: no sum without it
    unexamined = sum(p["bucket"] == SETTLED and p["status"] == STOPPED and _key(p) not in by_ticket for p in plans)
    complete = not unexamined and all(b["r"][n] is not None for b in rows for n in names)
    return {
        "labels": dict(STOP_LABELS), "count": len(rows), "unexamined": unexamined, "rows": rows,
        "sum_r": {n: _sum_r([b["r"][n] for b in rows]) if rows and complete else None for n in names},
        "sum_usd": {n: _money(math.fsum(b["usd"][n] for b in rows)) if rows and complete else None for n in names},
        # the settled sum with every stopped ticket read at its close, and at its low
        "settled_sum_r": {n: _sum_r([by_ticket[_key(p)]["r"][n] if _key(p) in by_ticket else p["r"]
                                     for p in settled]) if complete else None for n in names},
    }


# --------------------------------------------------- one share, uncertain ----

def one_share(pick: Mapping[str, Any], read: Mapping[str, Any], minute_obj: Mapping[str, Any] | None
              ) -> dict | None:
    """A ticket whose whole position left at the half-sale step, which only
    a position of ``ONE_SHARE`` can do (``plan.follow()`` sells at least half
    in whole shares), walked again over the same bars and minutes at
    ``SENSITIVITY_SHARES``. None for any other ticket."""
    walk = read["walk"]
    if walk is None or read["bucket"] != SETTLED:
        return None
    sales = _sales(walk)
    if not sales or sales[-1].get("event") != HALF_SALE:
        return None
    again = record.replay({**pick, "shares": SENSITIVITY_SHARES}, read["bars"], "green", minute_obj)
    return {"ticker": pick["ticker"], "kind": pick["kind"], "picked": pick["date"], "r": read["r"],
            "shares": SENSITIVITY_SHARES, "status_at_two": again["status"],
            "r_at_two": record.r_multiple(again, pick["stop"]) if again["status"] in record.SETTLED else None}


def uncertain_bounds(pick: Mapping[str, Any], read: Mapping[str, Any]) -> dict | None:
    """An uncertain ticket walked as if it had filled at its limit, and at
    its trigger. Bounds for a reader, never results. None for any other
    ticket, and for one whose bars are not there to walk."""
    if read["bucket"] != record.UNCERTAIN or read["walk"] is None:
        return None
    levels = record.ticket_levels(pick)
    out = {"ticker": pick["ticker"], "kind": pick["kind"], "picked": pick["date"],
           "reason": read["uncertainty"], "trigger": levels["trigger"],
           "limit": float(levels["limit"]) if _finite(levels["limit"]) else None}
    for name in ("limit", "trigger"):
        status = r = None
        if out[name] is not None:
            try:
                walk = plan.follow({**pick, "entry_ref": out[name]}, read["bars"])
            except ValueError:
                walk = None
            if walk is not None:
                status = walk["status"]
                r = record.r_multiple(walk, pick["stop"]) if status in record.SETTLED else None
        out[f"status_if_filled_at_{name}"] = status
        out[f"r_if_filled_at_{name}"] = r
    return out


def _one_share_block(reads, minutes: Mapping[str, Any], plans: list[dict]) -> dict:
    rows = [o for pick, read in reads if (o := one_share(pick, read, minutes.get(intraday.key(pick)))) is not None]
    at_two = {_key(o): o["r_at_two"] for o in rows}
    settled = [p for p in plans if p["bucket"] == SETTLED]
    # a settled one-share ticket whose bars these frames do not carry cannot be walked again
    unexamined = sum(p["shares"] == ONE_SHARE and p["bars"] != WALKED for p in settled)
    whole = bool(rows) and not unexamined and all(r is not None for r in at_two.values())
    return {"label": ONE_SHARE_LABEL, "count": len(rows), "unexamined": unexamined, "rows": rows,
            "settled_sum_r": _sum_r([at_two.get(_key(p), p["r"]) for p in settled]) if whole else None}


def _uncertain_block(reads, plans: list[dict]) -> dict:
    rows = [u for pick, read in reads if (u := uncertain_bounds(pick, read)) is not None]
    count = sum(p["bucket"] == record.UNCERTAIN for p in plans)
    return {"label": UNCERTAIN_LABEL, "count": count, "unexamined": count - len(rows), "rows": rows}


# ---------------------------------------------------------- the withdrawn ----

def _expand(path: Path) -> str | None:
    """One ledger entry's JSON text, or None when it cannot be read inside the entry bound."""
    try:
        with gzip.open(path) as handle:
            raw = handle.read(quality_ledger.MAX_ENTRY_BYTES + 1)
        return raw.decode("utf-8") if len(raw) <= quality_ledger.MAX_ENTRY_BYTES else None
    except (OSError, EOFError, ValueError, zlib.error):
        return None


def _publication_block(text: str, name: str) -> dict | None:
    """The entry's publication block read without parsing the entry whole:
    the object after a ``"publication":`` whose ``sha256`` is the file's own
    name. None when no such object is found, and the caller parses it whole."""
    decoder, start = json.JSONDecoder(), 0
    while True:
        at = text.find(PUBLICATION_MARKER, start)
        if at < 0:
            return None
        try:
            block, _ = decoder.raw_decode(text, at + len(PUBLICATION_MARKER))
        except ValueError:
            block = None
        if isinstance(block, dict) and block.get("sha256") == name:
            return block
        start = at + 1


def _published(block: Mapping[str, Any]) -> datetime | None:
    try:
        at = datetime.fromisoformat(block.get("published_at"))
    except (TypeError, ValueError):
        return None
    return at.astimezone(timezone.utc) if at.tzinfo is not None else None


def ledger_sessions(docs: Path, wanted: set[str]) -> dict:
    """The quality-ledger entries of the wanted sessions, each session's
    oldest publication first, with each listed ticker's evidence id and gate.
    Every entry is expanded and its publication block read; only a wanted
    session's entries are parsed whole. The scan is all or nothing."""
    folder = Path(docs) / quality_ledger.DIRECTORY
    out = {"status": SKIPPED, "reason": None, "entries": 0, "unread": 0, "parsed": 0, "expanded_bytes": 0,
           "sessions": {}}
    try:
        files = sorted(folder.glob("*" + LEDGER_SUFFIX)) if folder.is_dir() else None
    except OSError:
        files = None
    if files is None:
        return {**out, "reason": "docs carries no quality ledger"}
    out["entries"] = len(files)
    if len(files) > LEDGER_SCAN_MAX_ENTRIES:
        return {**out, "reason": f"the quality ledger holds {len(files)} entries, over the scan's bound of "
                                 f"{LEDGER_SCAN_MAX_ENTRIES}"}
    found: dict[str, list[tuple[datetime, str, list[dict]]]] = {}
    for path in files:
        name = path.name[:-len(LEDGER_SUFFIX)]
        text = _expand(path)
        if text is None:
            out["unread"] += 1
            continue
        out["expanded_bytes"] += len(text)
        entry = None
        block = _publication_block(text, name)
        if block is None:
            try:
                entry = _dict(json.loads(text))
            except ValueError:
                entry = {}
            block = _dict(entry.get("publication"))
        session, at = block.get("session"), _published(block)
        if not isinstance(session, str) or at is None or block.get("sha256") != name:
            out["unread"] += 1
            continue
        if session not in wanted:
            continue
        if entry is None:
            try:
                entry = _dict(json.loads(text))
            except ValueError:
                out["unread"] += 1
                continue
        out["parsed"] += 1
        signal = _dict(entry.get("signal"))
        rows = []
        for kind, name_ in (("burst", "candidates"), ("anticipation", "anticipation")):
            for item in signal.get(name_) if isinstance(signal.get(name_), list) else []:
                item = _dict(item)
                if isinstance(item.get("ticker"), str):
                    gate, evidence_id = _dict(item.get("gate")), item.get("evidence_id")
                    rows.append({"kind": kind, "ticker": item["ticker"],
                                 "evidence_id": evidence_id if isinstance(evidence_id, str) else None,
                                 "ticket": gate.get("ticket") if isinstance(gate.get("ticket"), bool) else None,
                                 "reason": gate.get("reason") if isinstance(gate.get("reason"), str) else None})
        found.setdefault(session, []).append((at, name, rows))
    out["sessions"] = {s: [{"published_at": at.isoformat(), "sha256": name, "rows": rows}
                           for at, name, rows in sorted(group, key=lambda g: (g[0], g[1]))]
                       for s, group in found.items()}
    return {**out, "status": SCANNED}


def withdrawn_by_ledger(row: Mapping[str, Any], scan: Mapping[str, Any]) -> tuple[bool | None, dict | None]:
    """Whether a later run of the ticket's own session withdrew it, from that
    session's ledger entries: the ticket was issued by the last entry that
    carries its evidence id, and it is withdrawn when the session has a later
    entry. Returns the answer (None when the ledger cannot say) and what the
    session's last entry says of the ticker."""
    if scan.get("status") != SCANNED or row["evidence_id"] is None:
        return None, None
    entries = scan["sessions"].get(row["picked"], [])
    issued = [i for i, entry in enumerate(entries)
              if any(r["evidence_id"] == row["evidence_id"] for r in entry["rows"])]
    if not issued:
        return None, None
    if issued[-1] == len(entries) - 1:
        return (False if not scan.get("unread") else None), None
    last = entries[-1]
    said = next((r for r in last["rows"] if r["kind"] == row["kind"] and r["ticker"] == row["ticker"]), None)
    return True, {"published_at": last["published_at"], "listed": said is not None,
                  "ticket": said["ticket"] if said else None, "reason": said["reason"] if said else None}


def _own_gate(row: Mapping[str, Any], data: Mapping[str, Any]) -> dict:
    """What the record being published says of a ticker an earlier run of its
    session ticketed and this run did not."""
    rows = (_dict(data.get("watchlist")).get("top") if row["kind"] == "anticipation" else data.get("bursts"))
    said = next((r for r in rows if isinstance(r, dict) and r.get("ticker") == row["ticker"]), None) \
        if isinstance(rows, list) else None
    gate = _dict(_dict(_dict(said).get("evidence")).get("gate"))
    at = _dict(data.get("run")).get("published_at")
    return {"published_at": at if isinstance(at, str) else None, "listed": said is not None,
            "ticket": gate.get("ticket") if isinstance(gate.get("ticket"), bool) else None,
            "reason": gate.get("reason") if isinstance(gate.get("reason"), str) else None}


def _withdrawn_block(reads, plans: list[dict], data: Mapping[str, Any], session: str | None,
                     docs: Path | None) -> dict:
    """Every ticket's ``withdrawn`` answer and the block that lists the
    withdrawn ones. A ticket of this session is read off the record itself:
    issued by this run it is not withdrawn, and issued by an earlier run and
    not by this one it is. The tickets of other sessions are read off the
    ledger."""
    direct = {_key(row): issued_here(pick, data, session) is None
              for (pick, _), row in zip(reads, plans) if issued_here(pick, data, session) is not False}
    wanted = {row["picked"] for row in plans if _key(row) not in direct and row["evidence_id"] is not None}
    scan = {"status": SKIPPED, "reason": None, "entries": 0, "unread": 0, "parsed": 0, "expanded_bytes": 0,
            "sessions": {}}
    if docs is None:
        scan["reason"] = "no docs directory was given"
    elif wanted:
        scan = ledger_sessions(docs, wanted)
    listed = []
    for row in plans:
        if _key(row) in direct:
            answer, basis = direct[_key(row)], RECORD
            later = _own_gate(row, data) if answer else None
        else:
            answer, later = withdrawn_by_ledger(row, scan)
            basis = LEDGER if answer is not None else None
        row["withdrawn"] = answer
        if answer:
            listed.append({"ticker": row["ticker"], "kind": row["kind"], "picked": row["picked"],
                           "evidence_id": row["evidence_id"], "basis": basis, "bucket": row["bucket"],
                           "r": row["r"], "later": later})
    return {"status": scan["status"], "reason": scan["reason"], "count": len(listed),
            "settled": sum(r["bucket"] == SETTLED for r in listed),
            "unknown": sum(row["withdrawn"] is None for row in plans), "tickets": listed,
            "ledger": {k: scan[k] for k in ("entries", "unread", "parsed", "expanded_bytes")}}


# --------------------------------------------------------- reconciliation ----

def _reconcile(plans: list[dict], reference: Mapping[tuple, Mapping[str, Any]], summary: Mapping[str, Any],
               data: Mapping[str, Any]) -> list[str]:
    """Why these figures are not the record's own, one reason each: a ticket
    whose bucket or R is not the reference row's, a ticket with no reference
    row or a row with no ticket, and totals that are not the published
    scorecard's."""
    said = []
    for row in plans:
        ref = reference.get(_key(row))
        if ref is None:
            said.append(f"{_name(row)} has no scorecard row")
        elif (row["bucket"], row["r"]) != (ref.get("bucket"), ref.get("r")):
            said.append(f"{_name(row)} reads {row['bucket']} at R {row['r']} here and {ref.get('bucket')} at R "
                        f"{ref.get('r')} in the scorecard's own row")
    extra = set(reference) - {_key(row) for row in plans}
    if extra:
        said.append(f"{_n(len(extra), 'scorecard row')} {'has' if len(extra) == 1 else 'have'} no ticket here")
    card = data.get("scorecard")
    if not isinstance(card, dict):
        said.append("the record carries no scorecard to hold these counts to")
        return said
    for name in (*record.SCORECARD_BUCKETS, "plans", "sum_r"):
        if summary[name] != card.get(name):
            said.append(f"{name} is {summary[name]} here and {card.get(name)} in the published scorecard")
    return said


# -------------------------------------------------------------- sentences ----

def _era_words(era: Mapping[str, Any]) -> str:
    inner = [_n(era["tickets"], "ticket")]
    if era["settled"]:
        inner.append(f"{era['settled']} settled, {_r(era['sum_r'])}")
        if era["model_usd"] is not None and not era["model_usd_missing"]:
            inner.append(f"{_usd(era['model_usd'])} in model dollars")
    else:
        inner.append("none settled")
    return f"{era['label']} ({', '.join(inner)})"


def _stop_sentences(stops: Mapping[str, Any]) -> list[str]:
    said = []
    if stops["count"] and stops["sum_r"]["booked"] is not None:
        r, usd, total = stops["sum_r"], stops["sum_usd"], stops["settled_sum_r"]
        said.append(f"{_n(stops['count'], 'settled ticket')} ended on a stop. As the model books "
                    f"{'it' if stops['count'] == 1 else 'them'}, a stop first reached inside a session at exactly "
                    f"the stop price, the sum is {_r(r['booked'])} ({_usd(usd['booked'])}). With the same "
                    f"{'exit' if stops['count'] == 1 else 'exits'} at the stop day's close it is {_r(r['at_close'])} "
                    f"({_usd(usd['at_close'])}): what holding to the close would have been, not a fill estimate. "
                    f"At the stop day's low, a worst-case bound, it is {_r(r['at_low'])} ({_usd(usd['at_low'])}).")
        said.append(f"Under those readings the settled sum is {_r(total['booked'])} as booked, "
                    f"{_r(total['at_close'])} at the closes and {_r(total['at_low'])} at the lows.")
    elif stops["unexamined"]:
        said.append(f"{_n(stops['unexamined'], 'settled ticket')} ended on a stop whose bars are not carried here, "
                    f"so the stop readings are not summed.")
    for b in stops["rows"]:
        m = b["minute"]
        if m is not None and m["r_at_low"] is not None:
            said.append(f"{b['ticker']} {b['picked']}: the retained minute bars first reach the stop at {m['at']}, "
                        f"in a minute that opened at {plan._usd(m['open'])} with a low of {plan._usd(m['low'])}; "
                        f"at that low the ticket reads {_r(m['r_at_low'])}.")
    return said


def _sentences(block: Mapping[str, Any]) -> list[str]:
    """The block in plain sentences, every number the block's own. An
    unreconciled block says only that it is not to be quoted."""
    if block["status"] != COMPUTED:
        return [f"The model record's figures do not reconcile with the record's own scorecard and are not to "
                f"be quoted: {block['reason']}."]
    plans, tickets = block["plans"], block["tickets"]
    if not tickets:
        return ["The model record holds no ticket in its window."]
    one = tickets == 1
    said = [f"The model record counts {_n(tickets, 'ticket')} issued from {plans[0]['picked']} through "
            f"{plans[-1]['picked']}: {_n(block['distinct_setups'], 'distinct setup')}, and "
            f"{_n(block['reissued_tickets'], 'ticket')} that issued a setup again on a later night.",
            f"By ticket: {_bucket_words(block['buckets'])}. By setup: {_bucket_words(block['buckets_by_setup'])}."]
    again = [s for s in block["setups"] if s["issues"] > 1]
    if again:
        said.append("Issued more than once: " + "; ".join(
            f"{s['ticker']} {s['kind']} {s['issues']} times ({s['first']} to {s['last']})" for s in again)
            + ". No ticket that was later issued again has a fill known, so re-issues raise the ticket counts "
              "and add nothing to the sum of R.")
    settled = block["buckets"][SETTLED]
    if settled:
        rs = [p["r"] for p in plans if p["bucket"] == SETTLED]
        said.append(f"The {_n(settled, 'settled ticket')} {'sums' if settled == 1 else 'sum'} to "
                    f"{_r(block['sum_r'])} ({_n(sum(r > 0 for r in rs), 'win')}, "
                    f"{_n(sum(r < 0 for r in rs), 'loss', 'losses')}, {sum(r == 0 for r in rs)} breakeven)."
                    + (f" Below {record.SCORECARD_MIN_PLANS} settled tickets the record prints no rate."
                       if settled < record.SCORECARD_MIN_PLANS else ""))
    else:
        said.append("No ticket has settled, so there is no R to sum.")
    known = [e for e in block["eras"] if e["issued_equity"] is not None]
    unknown = sum(e["tickets"] for e in block["eras"] if e["issued_equity"] is None)
    if len(known) == 1 and not unknown:
        said.append(f"{'The ticket' if one else 'Every ticket'} was sized against one model account: "
                    f"{_era_words(known[0])}.")
    elif known:
        said.append(f"The tickets were sized against {_n(len(known), 'model account')}: "
                    + "; ".join(_era_words(e) for e in known) + "."
                    + (f" No account is recorded for {_n(unknown, 'more ticket')}." if unknown else ""))
    else:
        said.append(f"No account is recorded for the {_n(unknown, 'ticket')}.")
    if settled:
        said.append("A sum of R is not a sum of dollars: R counts each ticket as one unit whatever its size."
                    + (f" The settled tickets sum to {_r(block['sum_r'])} and to {_usd(block['model_usd'])} in "
                       f"model dollars." if block["model_usd"] is not None and not block["model_usd_missing"]
                       else ""))
    said += _stop_sentences(block["stops"])
    ones = block["one_share"]
    if ones["count"]:
        rows = ones["rows"]
        again_at_two = [f"{o['ticker']} {_r(o['r_at_two'])}" for o in rows if o["r_at_two"] is not None]
        after = (f" Walked over the same bars at {SENSITIVITY_SHARES} shares: " + ", ".join(again_at_two) + "."
                 if again_at_two else "")
        if ones["settled_sum_r"] is not None:
            after += f" With those readings the settled sum is {_r(ones['settled_sum_r'])}."
        elif ones["unexamined"]:
            after += (f" The settled sum at {SENSITIVITY_SHARES} shares is not given: "
                      f"{_n(ones['unexamined'], 'settled 1-share ticket')} "
                      f"{'has' if ones['unexamined'] == 1 else 'have'} no bars here.")
        else:
            after += (f" The settled sum at {SENSITIVITY_SHARES} shares is not given: not every one of them has "
                      f"settled at that size in these bars.")
        said.append(f"{_n(ones['count'], 'settled ticket')} held {ONE_SHARE} share and sold it whole at the "
                    f"half-sale step, because {ONE_SHARE} share cannot be halved: "
                    + ", ".join(f"{o['ticker']} {_r(o['r'])}" for o in rows) + "." + after)
    unc = block["uncertain"]
    if unc["count"]:
        single, parts = unc["count"] == 1, []
        for u in unc["rows"]:
            bits = [f"{_r(u[f'r_if_filled_at_{n}'])} if filled at its {plan._usd(u[n])} {n}"
                    for n in ("limit", "trigger") if u[f"r_if_filled_at_{n}"] is not None]
            if bits:
                parts.append(f"{u['ticker']} {u['picked']} reads " + " and ".join(bits))
        said.append(f"{_n(unc['count'], 'ticket')} {'is' if single else 'are'} uncertain: the bars cannot say "
                    f"whether {'it' if single else 'each'} filled, and {'it is' if single else 'they are'} in no "
                    f"sum." + (" " + "; ".join(parts) + ". These are bounds, not results." if parts else ""))
    gone = block["withdrawn"]
    if gone["count"]:
        single = gone["count"] == 1
        said.append(f"{_n(gone['count'], 'counted ticket')} {'was' if single else 'were'} withdrawn by a later "
                    f"run of {'its' if single else 'their'} own session and {'stays' if single else 'stay'} in "
                    f"the record and in these counts: "
                    + ", ".join(f"{w['ticker']} {w['picked']}"
                                + (f" (settled, {_r(w['r'])})" if w["bucket"] == SETTLED and w["r"] is not None
                                   else "") for w in gone["tickets"]) + ".")
    return said


def _limits(block: Mapping[str, Any]) -> list[str]:
    """What the block does not establish, in sentences."""
    said = [
        "A model from bars alone, not a brokerage record: no fees, spread, slippage, tax or real execution is "
        "measured, and nothing here knows what anyone holds.",
        "Minute bars are retained only for a first day the daily bar could not place, so a stop day usually "
        "has its daily bar alone and its range stays between that day's low and the stop.",
        "A ticket's account is the publishing record's own, the previous brief's for the same evidence id, or "
        "the seed read off the publications in git; an account none of them gives is not guessed.",
    ]
    lost = sum(p["bars"] == NOT_CARRIED for p in block["plans"])
    if block["bars_source"] == OBSERVATIONS:
        said.append(f"Built from the record's own observations block, without market data: {_n(lost, 'ticket')} "
                    f"{'has' if lost == 1 else 'have'} bars the record no longer carries and "
                    f"{'takes its' if lost == 1 else 'take their'} bucket and R from the publication's "
                    f"quality-ledger row, with no walk details and no model dollars.")
    gone = block["withdrawn"]
    if gone["status"] == SKIPPED and gone["reason"]:
        said.append(f"The quality ledger was not read for withdrawn tickets: {gone['reason']}.")
    elif gone["ledger"]["unread"]:
        said.append(f"{_n(gone['ledger']['unread'], 'quality-ledger entry', 'quality-ledger entries')} could not "
                    f"be read, so a ticket not found withdrawn is unknown, not cleared.")
    if gone["unknown"]:
        said.append(f"Whether a later run of its session withdrew it is not known for "
                    f"{_n(gone['unknown'], 'ticket')}.")
    return said


# ------------------------------------------------------------------ build ----

def build(rec: Mapping[str, Any] | None, frames: Mapping[str, Any] | None, minutes: Mapping[str, Any] | None,
          data: Mapping[str, Any], docs: Path | None = None) -> dict:
    """The block from what a run holds: its picks record, its per-ticker
    daily bars, its retained minute evidence and the record being published.
    ``docs`` (optional) gives the previous brief, for carried accounts, and
    the quality ledger, for withdrawn tickets. A ticket with no frame is
    counted unmeasured, as the scorecard counts it."""
    return _build(rec, frames, minutes, data, docs, recorded=None, bars_source=FRAMES)


def _build(rec, frames, minutes, data, docs, *, recorded, bars_source) -> dict:
    """``recorded`` None reads every ticket off ``frames`` and holds it to
    ``record.scorecard_rows()`` over the same inputs. A list is the
    publication's own retained outcome rows: a ticket whose bars ``frames``
    carries whole is walked and held to its row, and one whose bars it does
    not carry takes its row's bucket and R and claims no walk."""
    rec, frames, minutes, data = _dict(rec), frames or {}, minutes or {}, _dict(data)
    rec = {**rec, "picks": rec["picks"] if isinstance(rec.get("picks"), list) else []}
    session = _dict(data.get("run")).get("session")
    try:
        date.fromisoformat(session)
    except (TypeError, ValueError):
        session = None
    picks, reference, sessions = [], {}, []
    if session is not None:
        sessions = record.sessions_before(frames, session, record.SCORECARD_SESSIONS)
        window = {*sessions, session}
        picks = sorted((p for p in rec["picks"] if p["date"] in window),
                       key=lambda p: (p["date"], p["ticker"], p["kind"]))
        rows = record.scorecard_rows(rec, frames, session, minutes=minutes) if recorded is None else recorded
        reference = {_key(r): r for r in rows}
    reads, plans = [], []
    for pick in picks:
        read = measure(pick, frames, minutes, session)
        kept = reference.get((pick["ticker"], pick["kind"], pick["date"]))
        if recorded is not None and not read["complete"] and kept is not None:
            read, row = _recorded(pick, read, kept)
        else:
            row = _plan_row(pick, read)
            if recorded is not None and not read["complete"]:
                row["bars"] = NOT_CARRIED
        reads.append((pick, read))
        plans.append(row)
    carried, unread_brief = carried_accounts(docs)
    for (pick, _), row in zip(reads, plans):
        row["issued_equity"], row["risk_pct"], row["account_basis"] = account_of(pick, row, data, session, carried)
    chains = setups(plans)
    settled = [p for p in plans if p["bucket"] == SETTLED]
    dollars = [p["model_usd"] for p in settled if p["model_usd"] is not None]
    summary = {**_bucket_counts(plans), "plans": len(plans), "sum_r": _sum_r([p["r"] for p in settled])}
    problems = (["the record names no session"] if session is None
                else _reconcile(plans, reference, summary, data))
    block: dict[str, Any] = {
        "version": VERSION, "status": UNRECONCILED if problems else COMPUTED,
        "reason": ("; ".join(problems[:RECONCILE_REASONS_MAX])
                   + (f"; and {len(problems) - RECONCILE_REASONS_MAX} more"
                      if len(problems) > RECONCILE_REASONS_MAX else "")) if problems else None,
        "session": session, "bars_source": bars_source,
        "window": None if session is None else {"from": min(sessions) if sessions else session, "through": session,
                                                "sessions": record.SCORECARD_SESSIONS, "includes_current": True},
        "tickets": len(plans), "distinct_setups": len(chains), "reissued_tickets": len(plans) - len(chains),
        "buckets": _bucket_counts(plans), "buckets_by_setup": _bucket_counts(chains), "sum_r": summary["sum_r"],
        "model_usd": _money(math.fsum(dollars)) if dollars else None,
        "model_usd_missing": len(settled) - len(dollars),
        "plans": plans, "setups": chains, "eras": eras(plans),
        "accounts": {"previous_brief": unread_brief or "read",
                     **{basis: sum(p["account_basis"] == basis for p in plans)
                        for basis in (RECORD, CARRIED, SEED, UNKNOWN)}},
        "stops": _stops_block(reads, minutes, plans),
        "one_share": _one_share_block(reads, minutes, plans),
        "uncertain": _uncertain_block(reads, plans),
        "withdrawn": _withdrawn_block(reads, plans, data, session, docs),
        "definitions": list(DEFINITIONS),
    }
    block["sentences"], block["limits"] = _sentences(block), _limits(block)
    return block


# ---------------------------------------------------------------- offline ----

def frames_from_observations(data: Mapping[str, Any], tickers: set[str]) -> dict[str, pd.DataFrame]:
    """Per-ticker daily frames from the record's own ``observations`` block:
    each symbol's retained history and its newest bar, one row a date. A
    symbol the block does not carry has no frame."""
    symbols = _dict(_dict(data.get("observations")).get("symbols"))
    frames = {}
    for ticker in sorted(tickers):
        seen = _dict(symbols.get(ticker))
        bars = {}
        for bar in [*(seen.get("history") if isinstance(seen.get("history"), list) else []), seen]:
            if (isinstance(bar, dict) and isinstance(bar.get("date"), str)
                    and all(_finite(bar.get(k)) for k in ("o", "h", "l", "c"))):
                bars[bar["date"]] = bar
        if bars:
            dates = sorted(bars)
            frames[ticker] = pd.DataFrame(
                {column: [float(bars[d][k]) for d in dates]
                 for column, k in (("Open", "o"), ("High", "h"), ("Low", "l"), ("Close", "c"))},
                index=pd.to_datetime(dates))
    return frames


def recorded_rows(docs: Path, raw: bytes) -> list[dict] | None:
    """The outcome rows the quality ledger retained for exactly these
    publication bytes, or None when it holds no entry for them."""
    name = hashlib.sha256(raw).hexdigest()
    text = _expand(Path(docs) / quality_ledger.DIRECTORY / (name + LEDGER_SUFFIX))
    if text is None:
        return None
    try:
        entry = _dict(json.loads(text))
    except ValueError:
        return None
    rows = _dict(entry.get("outcome")).get("rows")
    if _dict(entry.get("publication")).get("sha256") != name or not isinstance(rows, list):
        return None
    return [r for r in rows if isinstance(r, dict) and isinstance(r.get("ticker"), str)
            and isinstance(r.get("kind"), str) and isinstance(r.get("picked"), str)]


def offline(docs: Path) -> dict:
    """The block from ``docs`` alone, read-only: ``data.json``, ``picks.json``
    (a pick the walk could not read is left out, as ``record.load()`` leaves
    it out), the retained minute evidence and the record's own observations
    as the bars. A ticket whose bars the record no longer carries takes its
    bucket and R from the publication's quality-ledger row and is marked."""
    docs = Path(docs)
    raw = (docs / "data.json").read_bytes()
    data = _dict(json.loads(raw))
    try:
        stored = _dict(json.loads((docs / record.PICKS_FILE).read_text())).get("picks")
    except (OSError, ValueError):
        stored = None
    picks = [p for p in stored if record.pick_problem(p) is None] if isinstance(stored, list) else []
    minutes, _, _ = intraday.load_archive(docs)
    frames = frames_from_observations(data, {p["ticker"] for p in picks})
    return _build({"picks": picks}, frames, minutes, data, docs, recorded=recorded_rows(docs, raw) or [],
                  bars_source=OBSERVATIONS)


def _table(block: Mapping[str, Any]) -> list[str]:
    lines = []
    for p in block["plans"]:
        account = ("account unknown" if p["issued_equity"] is None
                   else f"${p['issued_equity']:,.0f} ({p['account_basis']})")
        result = "" if p["r"] is None else f" {_r(p['r'])}"
        dollars = "" if p["model_usd"] is None else f" {_usd(p['model_usd'])}"
        marks = "".join([" [bars not carried]" if p["bars"] == NOT_CARRIED else "",
                         " [withdrawn]" if p.get("withdrawn") else "",
                         " [minute fill]" if p["minute_fill"] else ""])
        lines.append(f"{p['picked']} {p['ticker']:<6}{p['kind']:<13}{p['shares']:>4} sh  issue {p['issue_no']} of "
                     f"{p['issues']}  {account:<24}{p['bucket']}{result}{dollars}{marks}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The model's own record, from docs alone (no market data).")
    parser.add_argument("--docs", default="docs", help="the docs directory to read (never written)")
    parser.add_argument("--json", action="store_true", help="print the block as JSON")
    args = parser.parse_args(argv)
    try:
        block = offline(Path(args.docs))
    except (OSError, ValueError) as exc:
        print(f"model record: {args.docs} could not be read ({type(exc).__name__})", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(block, indent=1, allow_nan=False))
    else:
        for line in [*_table(block), "", *block["sentences"], "", *block["limits"]]:
            print(line)
    return 0 if block["status"] == COMPUTED else 1


if __name__ == "__main__":
    sys.exit(main())
