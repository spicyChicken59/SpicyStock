"""The execution handoff: ``docs/orders.json``, ``docs/orders-morning.json`` and
``docs/positions-template.json``.

An outside execution agent decides and places the owner's orders. These files
are what it reads, and nothing in them is a new decision: every ticket is one
the record already published (``morning.admitted_rows()``, the same rows the
morning receipt quotes), every price is the plan's, and every rule number is a
``plan`` constant.

``orders.json`` (``build()``), written by the evening after the brief:

* one entry per published ticket: its identity, the order as the record wrote
  it (a day buy stop-limit with a one-triggers-the-other GTC sell stop), its
  entry window, the exit plan as machine-readable rules in the order
  ``plan.follow()`` applies them, its risk in dollars and in R, the position
  cap and the slot count checked again, the ticket's own flags, a status
  (``go``, ``human_review`` or ``blocked``) and a content hash;
* the night's checks, each ``pass``, ``fail`` or ``not_evaluated`` with a
  reason code, and ``trade_allowed``: true only when every night check passes
  and at least one ticket's status is ``go``;
* ``mode``, ``paper`` until the go-live gate (``live_ready``) says otherwise.

``orders-morning.json`` (``build_morning()``), written by the morning's persist
job from the ``orders.json`` and the morning receipt on ``main``: each ticket
re-read against the receipt's pre-open observation and marked ``go`` or
``cancel`` with its reasons. It reads no clock of its own, so the same two
files give the same bytes.

``positions-template.json`` (``positions_template()``): one blank position per
ticket, the shape the execution agent fills with real orders, fills and
exits. A filled copy is the owner's and is never committed to this public
repository.

The schema of all three is ``docs/operations/orders-schema.json``;
``src/schema_check.py`` holds every file written here to it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import schema_check  # noqa: E402  (stdlib only: the publication gate imports this module)

VERSION = 1
FILE = "orders.json"
MORNING_FILE = "orders-morning.json"
POSITIONS_FILE = "positions-template.json"
DATA_FILE = "data.json"
PICKS_FILE = "picks.json"
MORNING_RECEIPT = "morning.json"
SCHEMA = ROOT / "docs" / "operations" / "orders-schema.json"
MAX_BYTES = 512 * 1024
MAX_SOURCE_BYTES = 48 * 1024 * 1024

#: until the go-live gate says otherwise, every file here is paper only
MODE = "paper"
LIVE_READY_REASON = "go_live_gate_not_evaluated"
ENTRY_TYPE = "buy_stop_limit"
STOP_TYPE = "sell_stop"

PASS, FAIL, NOT_EVALUATED = "pass", "fail", "not_evaluated"
CHECK_STATUSES = (PASS, FAIL, NOT_EVALUATED)
GO, HUMAN_REVIEW, BLOCKED = "go", "human_review", "blocked"
TICKET_STATUSES = (GO, HUMAN_REVIEW, BLOCKED)
CANCEL = "cancel"
DECISIONS = (GO, CANCEL)

#: the night's checks, in the order they are reported
NIGHT_CHECKS = ("light", "data", "publication_time", "cross_check", "account")
#: each ticket's own checks, in the order they are reported
TICKET_CHECKS = ("event_registry", "sec_flags", "position_cap", "risk_budget")
#: every reason a night or a ticket can carry
REASONS = {
    "light_red": "the market light is red: no new longs",
    "light_unknown": "the record names no market light",
    "data_degraded": "the run's status is not ok",
    "late_publish": "the record was published after the applicable session opened",
    "publication_time_unknown": "the record carries no delivery block to say when it was published",
    "cross_check_not_run": "no second-source cross-check of the tickets' signal-day bars was run",
    "account_limit": "the night's commitments or slots are over the account's limits",
    "no_tickets": "the record published no ticket",
    "event_blocked": "the manual event registry refuses this ticket",
    "sec_flag": "an SEC filing flag needs a person's review",
    "position_cap": "shares at the limit cost more than the position cap",
    "risk_budget": "shares at the limit risk more than the night's risk budget",
}
MORNING_REASONS = {
    "gap_above_limit": "a recent price is over the ticket's limit",
    "gap_below_floor": "a recent price is at or under the ticket's skip-under line or its stop",
    "trigger_crossed": "a recent price is at or over the buy stop: the stop-limit as written cannot be entered",
    "news_or_sec_flag": "an event flag (the manual registry, or an SEC filing orders.json holds for review) "
                        "refuses or holds this ticket",
    "halted": "the halt source reports a halt without a trading resumption",
    "stale_data": "no recent price was observed for this ticket",
    "not_checked": "the morning receipt has no row for this ticket",
    "no_morning_check": "the morning receipt on main is not bound to this record",
    "night_not_allowed": "orders.json does not allow trading tonight",
    "ticket_not_go": "orders.json did not mark this ticket go",
}
#: a price state the morning receipt names, and what it does to a ticket
STATE_REASON = {
    "below_stop": "gap_below_floor", "below_entry_floor": "gap_below_floor", "below_trigger": None,
    "within_published_band": "trigger_crossed", "above_limit": "gap_above_limit",
    "above_day2_extension": "gap_above_limit",
}
POSITION_STATUSES = ("not_submitted", "submitted", "partially_filled", "filled", "cancelled", "closed")
EXIT_REASONS = ("protective_stop", "stopped_at_open", "gap_20pct", "sell_half_8pct", "abnormal_10pct",
                "day3_no_progress", "day3_sell_half", "day5_exit", "manual")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value) -> list:
    return value if isinstance(value, list) else []


def _num(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def encode(value) -> bytes:
    return json.dumps(value, sort_keys=True, indent=1, ensure_ascii=False, allow_nan=False).encode() + b"\n"


def sealed(value: dict) -> dict:
    """``value`` with ``content_sha256``: the SHA-256 of its canonical JSON without that field."""
    body = {k: v for k, v in value.items() if k != "content_sha256"}
    return {**body, "content_sha256": hashlib.sha256(canonical(body)).hexdigest()}


def seal_holds(value: dict) -> bool:
    return isinstance(value, dict) and sealed(value).get("content_sha256") == value.get("content_sha256")


# --------------------------------------------------------------- exits -----
def exit_plan(trigger: float, shares: int, days: list[str]) -> dict:
    """The hold as rules in ``plan.follow()``'s order, numbers from ``plan``.

    ``entry`` is the position's average fill. The model's own walk prices the
    levels from the buy stop (``record.replay()`` reads ``entry_ref``), so each
    percentage level carries its price at the trigger; a fill elsewhere moves
    it by the same percentage."""
    from src import plan
    half = shares - shares // 2
    at_trigger = plan.exit_levels(trigger)
    sources = {r["key"]: r["source"] for r in plan.EXIT_RULES}

    def span(first, last):
        return {"from_day": first, "to_day": last, "from_date": days[first - 1], "to_date": days[last - 1]}

    last = plan.FINAL_EXIT_DAY
    rules = [
        {"key": "stopped_at_open", "source": sources["stop"], **span(plan.ENTRY_DAY, last),
         "when": {"price": "open", "op": "at_or_below", "level": "stop"},
         "then": {"action": "sell", "quantity": "all", "at": "open"}},
        {"key": "gap_20pct", "source": sources["gap_20pct"], **span(plan.ENTRY_DAY, last),
         "when": {"price": "open", "op": "at_or_above", "level": "entry_pct", "pct": plan.GAP_EXIT_PCT,
                  "price_at_trigger": at_trigger["gap_exit"]},
         "then": {"action": "sell", "quantity": "all", "at": "open"}},
        {"key": "protective_stop", "source": sources["stop"], **span(plan.ENTRY_DAY, last),
         "when": {"price": "low", "op": "at_or_below", "level": "stop"},
         "then": {"action": "sell", "quantity": "all", "at": "stop", "order_type": "stop_market"}},
        {"key": "sell_half_8pct", "source": sources["sell_half_8pct"], **span(plan.ENTRY_DAY, last), "once": True,
         "when": {"price": "high", "op": "at_or_above", "level": "entry_pct", "pct": plan.SELL_HALF_PCT,
                  "price_at_trigger": at_trigger["sell_half"]},
         "then": {"action": "sell", "quantity": "half", "shares": half, "at": "the_higher_of_open_and_level",
                  "stop_to": "day_high_minus", "cents": plan.TRAIL_CENTS, "cents_max": plan.TRAIL_CENTS_MAX}},
        {"key": "abnormal_10pct", "source": sources["abnormal_10pct"], **span(plan.ENTRY_DAY, last),
         "when": {"price": "close", "op": "at_or_above", "level": "entry_pct", "pct": plan.ABNORMAL_DAY_PCT,
                  "price_at_trigger": at_trigger["abnormal"]},
         "then": {"action": "raise_stop", "stop_to": "day_high_minus", "cents": plan.TRAIL_CENTS,
                  "take": "partial_profit"}},
        {"key": "day3_no_progress", "source": sources["day3_no_progress"],
         **span(plan.NO_PROGRESS_DAY, plan.NO_PROGRESS_DAY),
         "when": {"price": "close", "op": "at_or_below", "level": "entry"},
         "then": {"action": "sell", "quantity": "all", "at": "close"}},
        {"key": "day3_sell_half", "source": sources["day3_sell_half"], **span(plan.SELL_HALF_DAY, plan.SELL_HALF_DAY),
         "when": {"price": "close", "op": "session_close", "unless": "sell_half_8pct"},
         "then": {"action": "sell", "quantity": "half", "shares": half, "at": "close"}},
        {"key": "entry_day_low", "source": sources["entry_day_low"], **span(plan.ENTRY_DAY, plan.ENTRY_DAY),
         "when": {"price": "close", "op": "session_close"},
         "then": {"action": "raise_stop", "stop_to": "entry_day_low", "only_up": True}},
        {"key": "trail_after_day3", "source": sources["trail_after_day3"], **span(plan.TRAIL_FROM_DAY, last),
         "when": {"price": "close", "op": "session_close"},
         "then": {"action": "raise_stop", "stop_to": "day_low", "only_up": True}},
        {"key": "day5_exit", "source": sources["day5_exit"], **span(last, last),
         "when": {"price": "close", "op": "session_close"},
         "then": {"action": "sell", "quantity": "remainder", "at": "close"}},
        {"key": "no_breakeven", "source": sources["no_breakeven"],
         **span(plan.ENTRY_DAY + 1, plan.NO_BREAKEVEN_BEFORE_DAY - 1),
         "when": {"price": "close", "op": "session_close"},
         "then": {"action": "hold_stop", "do_not": "move_stop_to_breakeven"}},
    ]
    for i, rule in enumerate(rules, 1):
        rule["sequence"] = i
    return {"entry_basis": "average_fill_price", "shares": shares, "half_shares": half,
            "within_a_session": "open first, then the low against the stop, then the high, then the close: "
                                "the order of a bar's high and low is unknown, so the stop wins",
            "rules": rules}


# ------------------------------------------------------------- orders ------
def _night(data: dict, tickets: list) -> list:
    run = _dict(data.get("run"))
    regime = _dict(_dict(data.get("breadth")).get("regime"))
    verdict = regime.get("verdict")
    checks = []

    def add(key, status, reason=None, detail=None):
        checks.append({"key": key, "status": status, "reason": reason, "detail": detail})

    if verdict not in ("green", "yellow", "red"):
        add("light", NOT_EVALUATED, "light_unknown")
    else:
        add("light", FAIL if verdict == "red" else PASS, "light_red" if verdict == "red" else None, verdict)
    status = run.get("status")
    add("data", PASS if status == "ok" else FAIL, None if status == "ok" else "data_degraded",
        status if isinstance(status, str) else None)
    before = _dict(run.get("delivery")).get("before_next_open")
    if before is None or not isinstance(before, bool):
        add("publication_time", NOT_EVALUATED, "publication_time_unknown")
    else:
        add("publication_time", PASS if before else FAIL, None if before else "late_publish",
            _dict(run.get("delivery")).get("published_at"))
    add("cross_check", NOT_EVALUATED, "cross_check_not_run")
    budget, account = _dict(data.get("cash_budget")), _dict(data.get("account"))
    committed = budget.get("committed_usd")
    reserved = budget.get("reserved_usd", 0.0)
    equity = account.get("equity")
    slots, slots_max = budget.get("slots_used"), budget.get("slots_max", account.get("max_open_positions"))
    if not all(_num(v) for v in (committed, reserved, equity, slots, slots_max)):
        add("account", NOT_EVALUATED, "account_limit", "the record carries no cash budget to check")
    else:
        within = committed + reserved <= equity and slots <= slots_max
        add("account", PASS if within else FAIL, None if within else "account_limit",
            f"{slots} of {slots_max} slots; ${committed + reserved:,.2f} committed and reserved of ${equity:,.2f}")
    return checks


def _sec_flagged(data: dict, kind: str, ticker: str) -> str | None:
    stage = "burst" if kind == "burst" else "anticipation"
    for row in _list(_dict(_dict(data.get("run")).get("earnings")).get("rows")):
        if isinstance(row, dict) and row.get("ticker") == ticker and row.get("stage") in (stage, kind):
            items = _dict(row.get("items"))
            if items.get("status") == "material":
                return items.get("sentence") or "a current report carries a material 8-K item"
    return None


def _ticket(data: dict, admitted: dict, days: list[str]) -> dict:
    from src import plan
    kind, ticker = admitted["kind"], admitted["ticker"]
    rows = _list(data.get("bursts")) if kind == "burst" else _list(_dict(data.get("watchlist")).get("top"))
    row = next(r for r in rows if isinstance(r, dict) and r.get("ticker") == ticker)
    p = row["plan"]
    run, account = _dict(data.get("run")), _dict(data.get("account"))
    timing = _dict(run.get("timing"))
    regime = _dict(_dict(data.get("breadth")).get("regime"))
    levels = admitted["levels"]
    trigger, limit, stop, shares = levels["trigger"], levels["limit"], levels["stop"], p["shares"]
    per_share = plan._money(limit - stop)
    equity = account.get("equity")
    cap = plan._money(equity * account.get("max_position_pct") / 100) if _num(equity) else None
    budget = (plan._money(equity * account.get("risk_pct") / 100 * float(p.get("size_multiplier") or 0))
              if _num(equity) else None)
    position = plan._money(shares * limit)
    risk = plan._money(shares * per_share)
    checks, flags = [], []

    def add(key, ok, reason, detail):
        checks.append({"key": key, "status": PASS if ok else FAIL, "reason": None if ok else reason,
                       "detail": detail})

    event = _dict(p.get("event_risk"))
    add("event_registry", not event.get("blocked"), "event_blocked", event.get("status"))
    sec = _sec_flagged(data, kind, ticker)
    add("sec_flags", sec is None, "sec_flag", sec)
    add("position_cap", cap is not None and position <= cap, "position_cap",
        f"${position:,.2f} at the limit against a ${cap:,.2f} cap" if cap is not None else None)
    add("risk_budget", budget is not None and risk <= budget + 0.005, "risk_budget",
        f"${risk:,.2f} at the limit against a ${budget:,.2f} budget" if budget is not None else None)
    failed = [c["reason"] for c in checks if c["status"] == FAIL]
    status = BLOCKED if set(failed) - {"sec_flag"} else HUMAN_REVIEW if failed else GO
    entry = {"type": ENTRY_TYPE, "stop_price": trigger, "limit_price": limit, "time_in_force": "day",
             "valid_from": timing.get("opens_at"), "valid_until": timing.get("cutoff_at"),
             "prepare_by": timing.get("prepare_by"), "cancel_if_unfilled_at": timing.get("cutoff_at"),
             "skip_if_open_below": p.get("skip_if_open_below") if kind == "burst" else None,
             "skip_if_open_above": p.get("skip_if_open_above") if kind == "burst" else None,
             "trigger_rule": p.get("trigger_rule", plan.LEGACY_BURST_TRIGGER_RULE) if kind == "burst" else None}
    return sealed({
        "id": f"{run.get('session')}:{kind}:{ticker}",
        "session": run.get("session"), "applicable_session": timing.get("applicable_session"),
        "symbol": ticker, "setup_type": kind,
        "grade": row.get("grade") if kind == "burst" else None,
        "rules_version": _dict(data.get("app")).get("rules_version"),
        "light": regime.get("verdict"), "size_multiplier": p.get("size_multiplier"),
        "shares": shares,
        "entry": entry,
        "protective_stop": {"type": STOP_TYPE, "stop_price": stop, "quantity": shares, "time_in_force": "gtc",
                            "attached": "one_triggers_the_other",
                            "note": "Fidelity releases an OTO's sell stop only when the buy fills in full; on a "
                                    "partial fill place a separate sell stop for the shares that filled"},
        "order_as_written": p["order_json"],
        "exit_plan": exit_plan(trigger, shares, days),
        "risk": {"r_per_share": per_share, "r_basis": "the limit less the stop: the highest fill the ticket "
                 "permits, which is the price the plan is sized at", "risk_usd": risk,
                 "plan_risk_usd": p.get("risk_usd"), "risk_budget_usd": budget,
                 "position_usd": position, "position_cap_usd": cap},
        "checks": checks,
        "status": status,
        "reasons": failed,
        "evidence": {"evidence_id": admitted["evidence_id"], "plan_sha256": admitted["plan_sha256"]},
    })


def build(canonical_raw: bytes, picks_raw: bytes | None = None) -> dict:
    """``orders.json`` for one installed record. Raises when the record's
    tickets cannot be read as the morning receipt reads them."""
    from src import morning, plan
    data, binding = morning._publication(canonical_raw, allow_fixture=True)
    run = _dict(data.get("run"))
    timing = _dict(run.get("timing"))
    session = run.get("session")
    days = [d.isoformat() for d in plan.next_sessions(date.fromisoformat(session), plan.FINAL_EXIT_DAY)]
    tickets = [_ticket(data, admitted, days) for admitted in morning.admitted_rows(data)]
    night = _night(data, tickets)
    reasons = [{"scope": "night", "code": c["reason"]} for c in night if c["status"] != PASS]
    if not tickets:
        reasons.append({"scope": "night", "code": "no_tickets"})
    reasons += [{"scope": t["symbol"], "code": code} for t in tickets for code in t["reasons"]]
    allowed = all(c["status"] == PASS for c in night) and any(t["status"] == GO for t in tickets)
    budget, account = _dict(data.get("cash_budget")), _dict(data.get("account"))
    return sealed({
        "schema": "docs/operations/orders-schema.json", "version": VERSION, "kind": "orders",
        "mode": MODE, "live_ready": {"value": False, "reasons": [LIVE_READY_REASON]},
        "source": {"data_sha256": hashlib.sha256(canonical_raw).hexdigest(),
                   "picks_sha256": hashlib.sha256(picks_raw).hexdigest() if picks_raw is not None else None,
                   "rules_version": binding["rules_version"], "context_sha256": binding["context_sha256"],
                   "run_id": run.get("run_id"),
                   "session": session, "applicable_session": timing.get("applicable_session"),
                   "published_at": run.get("published_at"), "fixture": bool(data.get("fixture")),
                   "dry_run": bool(run.get("dry_run"))},
        "account": {"equity": account.get("equity"), "risk_pct": account.get("risk_pct"),
                    "max_position_pct": account.get("max_position_pct"),
                    "max_open_positions": account.get("max_open_positions"),
                    "slots_used": budget.get("slots_used"), "committed_usd": budget.get("committed_usd"),
                    "reserved_usd": budget.get("reserved_usd")},
        "entry_window": {"opens_at": timing.get("opens_at"), "cutoff_at": timing.get("cutoff_at"),
                         "prepare_by": timing.get("prepare_by"), "timezone": timing.get("timezone")},
        "night_checks": night,
        "trade_allowed": allowed,
        "reasons": reasons,
        "tickets": tickets,
        "summary": {"tickets": len(tickets), "go": sum(t["status"] == GO for t in tickets),
                    "human_review": sum(t["status"] == HUMAN_REVIEW for t in tickets),
                    "blocked": sum(t["status"] == BLOCKED for t in tickets)},
    })


def positions_template(orders: dict, orders_raw: bytes) -> dict:
    """One blank position per ticket, bound to ``orders.json``'s bytes. The
    agent fills a private copy; nothing in a filled copy belongs here."""
    return sealed({
        "schema": "docs/operations/orders-schema.json#/$defs/positions", "version": VERSION, "kind": "positions",
        "orders_sha256": hashlib.sha256(orders_raw).hexdigest(), "session": orders["source"]["session"],
        "applicable_session": orders["source"]["applicable_session"], "mode": orders["mode"],
        "privacy": "a filled copy holds the owner's real orders and fills: keep it private and never commit it "
                   "to the public repository",
        "positions": [{"ticket_id": t["id"], "ticket_sha256": t["content_sha256"], "symbol": t["symbol"],
                       "planned": {"shares": t["shares"], "stop_price": t["entry"]["stop_price"],
                                   "limit_price": t["entry"]["limit_price"],
                                   "protective_stop": t["protective_stop"]["stop_price"]},
                       "broker": {"account_label": None, "entry_order_id": None, "stop_order_id": None},
                       "status": "not_submitted", "submitted_at": None, "submitted_shares": None,
                       "cancelled_shares": None, "fills": [], "exits": [], "fees_usd": None, "notes": None}
                      for t in orders["tickets"]],
    })


# ------------------------------------------------------------- morning -----
def _observed(row: dict) -> dict:
    trade, quote = _dict(row.get("trade")), _dict(row.get("quote"))
    return {"trade_status": trade.get("status"), "trade_price": trade.get("price"),
            "trade_at": trade.get("timestamp"), "quote_status": quote.get("status"),
            "bid": quote.get("bid"), "ask": quote.get("ask"), "quote_at": quote.get("timestamp"),
            "price_checks": _dict(row.get("price_checks"))}


def build_morning(orders_raw: bytes, receipt_raw: bytes | None, data_raw: bytes | None = None) -> dict:
    """``orders-morning.json``: each ticket of ``orders.json`` re-read against
    the morning receipt, ``go`` or ``cancel`` with every reason that applies.

    With ``data_raw`` (the persist job passes main's record) the orders must be
    bound to it and a receipt bound to it must pass ``morning``'s own
    validation; without it the receipt is read as given."""
    from src import morning
    orders = validate(orders_raw)
    receipt = json.loads(receipt_raw) if receipt_raw is not None else None
    if data_raw is not None:
        _require(orders["source"]["data_sha256"] == hashlib.sha256(data_raw).hexdigest(),
                 "orders.json is not bound to the record given")
        if isinstance(receipt, dict) and _dict(receipt.get("publication")).get("data_sha256") == \
                orders["source"]["data_sha256"]:
            morning.validate_observation(receipt, data_raw)
    bound = (isinstance(receipt, dict)
             and _dict(receipt.get("publication")).get("data_sha256") == orders["source"]["data_sha256"])
    by_key = {(r.get("kind"), r.get("ticker"), r.get("evidence_id"), r.get("plan_sha256")): r
              for r in (_list(receipt.get("rows")) if bound else []) if isinstance(r, dict)}
    out = []
    for t in orders["tickets"]:
        reasons = []
        if not orders["trade_allowed"]:
            reasons.append("night_not_allowed")
        if t["status"] != GO:
            reasons.append("news_or_sec_flag" if t["status"] == HUMAN_REVIEW else "ticket_not_go")
        row = by_key.get((t["setup_type"], t["symbol"], t["evidence"]["evidence_id"], t["evidence"]["plan_sha256"]))
        observed = None
        if not bound:
            reasons.append("no_morning_check")
        elif row is None:
            reasons.append("not_checked")
        else:
            observed = _observed(row)
            events = _dict(row.get("events"))
            if _dict(events.get("halt")).get("blocks_entry") is True:
                reasons.append("halted")
            if _dict(events.get("corporate_action")).get("blocked") is True and "news_or_sec_flag" not in reasons:
                reasons.append("news_or_sec_flag")
            states = [observed["price_checks"].get(k) for k, status in
                      (("trade", observed["trade_status"]), ("ask", observed["quote_status"])) if status == "recent"]
            if not states:
                reasons.append("stale_data")
            for code in dict.fromkeys(STATE_REASON.get(s) for s in states if STATE_REASON.get(s)):
                reasons.append(code)
        out.append({"ticket_id": t["id"], "ticket_sha256": t["content_sha256"], "symbol": t["symbol"],
                    "decision": CANCEL if reasons else GO, "reasons": reasons, "observed": observed})
    return sealed({
        "schema": "docs/operations/orders-schema.json#/$defs/orders_morning", "version": VERSION,
        "kind": "orders_morning", "mode": orders["mode"],
        "orders_sha256": hashlib.sha256(orders_raw).hexdigest(),
        "data_sha256": orders["source"]["data_sha256"],
        "morning_sha256": hashlib.sha256(receipt_raw).hexdigest() if receipt_raw is not None else None,
        "morning_bound": bound,
        "morning_status": receipt.get("status") if bound else None,
        "morning_generated_at": receipt.get("generated_at") if bound else None,
        "observation_run_id": receipt.get("observation_run_id") if bound else None,
        "session": orders["source"]["session"], "applicable_session": orders["source"]["applicable_session"],
        "tickets": out,
        "summary": {"tickets": len(out), "go": sum(o["decision"] == GO for o in out),
                    "cancel": sum(o["decision"] == CANCEL for o in out)},
    })


# ------------------------------------------------------------ the schema ---
def schema() -> dict:
    root = json.loads(SCHEMA.read_text())
    schema_check.check_definitions(root)
    return root


def problems(value: dict, kind: str = "orders") -> list[str]:
    """Where ``value`` does not meet its schema, and whether it holds its hash."""
    root = schema()
    target = root if kind == "orders" else {"$ref": f"#/$defs/{kind}"}
    found = schema_check.errors(value, target, root)
    if not seal_holds(value):
        found.append("$: content_sha256 is not the hash of the rest")
    for t in _list(value.get("tickets")) if kind == "orders" else []:
        if isinstance(t, dict) and not seal_holds(t):
            found.append(f"$.tickets[{t.get('symbol')}]: content_sha256 is not the hash of the rest")
    return found


def validate(raw: bytes, kind: str = "orders") -> dict:
    _require(0 < len(raw) <= MAX_BYTES, f"{kind} is not within {MAX_BYTES} bytes")
    value = json.loads(raw)
    found = problems(value, kind)
    _require(not found, f"{kind} fails its schema: " + "; ".join(found[:5]))
    return value


# ----------------------------------------------------------- installing ----
def _install(docs: Path, files: dict[str, bytes]) -> None:
    """Stage, read back and replace each file; a failed rename restores the earlier bytes."""
    docs = Path(docs)
    with tempfile.TemporaryDirectory(prefix=".orders-", dir=docs) as tmp:
        stage = Path(tmp)
        previous, installed = {}, []
        for name, raw in files.items():
            _require(not (docs / name).is_symlink(), f"{name} must not be a symlink")
            (stage / name).write_bytes(raw)
            _require((stage / name).read_bytes() == raw, f"{name} did not read back")
            previous[name] = (docs / name).read_bytes() if (docs / name).exists() else None
        try:
            for name in files:
                os.replace(stage / name, docs / name)
                installed.append(name)
        except OSError:
            for name in reversed(installed):
                if previous[name] is None:
                    (docs / name).unlink()
                else:
                    (stage / name).write_bytes(previous[name])
                    os.replace(stage / name, docs / name)
            raise


def write_publication(docs) -> dict:
    """``orders.json`` and ``positions-template.json`` for the installed record."""
    docs = Path(docs)
    canonical_raw = (docs / DATA_FILE).read_bytes()
    picks_raw = (docs / PICKS_FILE).read_bytes() if (docs / PICKS_FILE).exists() else None
    orders_raw = encode(build(canonical_raw, picks_raw))
    orders = validate(orders_raw)
    positions_raw = encode(positions_template(orders, orders_raw))
    validate(positions_raw, "positions")
    _install(docs, {POSITIONS_FILE: positions_raw, FILE: orders_raw})
    stale = docs / MORNING_FILE
    if stale.exists() and not stale.is_symlink():
        try:
            bound = json.loads(stale.read_bytes()).get("orders_sha256") == hashlib.sha256(orders_raw).hexdigest()
        except (OSError, ValueError, AttributeError):
            bound = False
        if not bound:
            stale.unlink()      # the morning's go/cancel belongs to an earlier night's tickets
    return {"tickets": orders["summary"]["tickets"], "trade_allowed": orders["trade_allowed"],
            "reasons": [r["code"] for r in orders["reasons"]], "bytes": len(orders_raw)}


def discard_unbound(docs) -> list[str]:
    """Remove an ``orders.json`` (and its template) not bound to the installed
    record: an earlier night's tickets must never read as tonight's."""
    docs = Path(docs)
    removed = []
    try:
        data_sha = hashlib.sha256((docs / DATA_FILE).read_bytes()).hexdigest()
        bound = json.loads((docs / FILE).read_bytes())["source"]["data_sha256"] == data_sha
    except (OSError, ValueError, KeyError, TypeError):
        bound = False
    if not bound:
        for name in (FILE, POSITIONS_FILE, MORNING_FILE):
            if (docs / name).exists() and not (docs / name).is_symlink():
                (docs / name).unlink()
                removed.append(name)
    return removed


def check(docs) -> list[str]:
    """Every way the files on disk are not this record's or not their schema's."""
    docs = Path(docs)
    out = []
    data_sha = hashlib.sha256((docs / DATA_FILE).read_bytes()).hexdigest()
    try:
        orders_raw = (docs / FILE).read_bytes()
        orders = validate(orders_raw)
        if orders["source"]["data_sha256"] != data_sha:
            out.append("orders.json is not bound to data.json")
    except (OSError, ValueError) as exc:
        return [f"orders.json: {exc}"]
    for name, kind in ((POSITIONS_FILE, "positions"), (MORNING_FILE, "orders_morning")):
        if not (docs / name).exists():
            continue
        try:
            value = validate((docs / name).read_bytes(), kind)
        except ValueError as exc:
            out.append(f"{name}: {exc}")
            continue
        if value["orders_sha256"] != hashlib.sha256(orders_raw).hexdigest():
            out.append(f"{name} is not bound to orders.json")
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("evening", "check"):
        sub.add_parser(name).add_argument("--docs", type=Path, default=ROOT / "docs")
    m = sub.add_parser("morning", help="write orders-morning.json from the orders.json and morning.json given")
    m.add_argument("--orders", type=Path, required=True)
    m.add_argument("--receipt", type=Path, default=None)
    m.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "evening":
        print(json.dumps(write_publication(args.docs)))
        return 0
    if args.command == "check":
        found = check(args.docs)
        for line in found:
            print(line)
        return 1 if found else 0
    raw = encode(build_morning(args.orders.read_bytes(),
                               args.receipt.read_bytes() if args.receipt and args.receipt.exists() else None))
    validate(raw, "orders_morning")
    args.output.write_bytes(raw)
    return 0


if __name__ == "__main__":
    sys.exit(main())
