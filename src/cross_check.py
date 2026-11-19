"""A second-source check of each ticket's signal-day bar (``run.cross_check``).

The night's bars are Alpaca's consolidated ``sip`` feed. For every ticket the
record publishes (at most ``MAX_NAMES``), this asks the same provider's
``iex`` feed for the signal session and the one before it, and compares:

* each of the open, high, low and close: a difference over ``PRICE_PCT`` of
  the ``sip`` price fails the ticket;
* the volume. IEX is one exchange: its daily volume is that venue's share of
  the consolidated tape, a few percent of it, so the two volumes are never
  within ``VOLUME_PCT`` of each other and an absolute comparison would fail
  every ticket. Under ``VOLUME_BASIS = "ratio_to_prior_session"`` each feed's
  signal-day volume is read against its own previous session, and the two
  ratios must agree within ``VOLUME_PCT``: the same question the scans ask of
  volume (``v > v1``), asked of both feeds. ``VOLUME_BASIS = "absolute"`` is
  the literal comparison, kept so the choice is one constant.

A failed ticket is blocked in ``orders.json``; a ticket IEX has no bar for,
a bar with a value that is not a finite number, or a previous session either
feed does not carry (the XNYS session before the signal, the same in both),
is ``unknown``, which is never a pass. The differences are compared
unrounded and stored unrounded, so the validator re-derives each row's
result from them exactly. It reads the provider and decides nothing about the
night: the record's own bars, plans and tickets do not move. The IEX request
is one batch, retried once on failure as every bars request is.
"""
from __future__ import annotations

import math
from datetime import date
from typing import Any

VERSION = 1
FEED = "iex"
#: (owner's decision, 19 November 2026) a price more than this far from the sip price fails the ticket
PRICE_PCT = 0.5
#: (owner's decision) a volume reading more than this far from the sip one fails the ticket
VOLUME_PCT = 10.0
VOLUME_BASES = ("ratio_to_prior_session", "absolute")
#: (P) see the module docstring: IEX's volume is one venue's, so the ratios are compared
VOLUME_BASIS = "ratio_to_prior_session"
MAX_NAMES = 20
#: the lookback asked of the iex feed, in sessions: the signal day and the one before it
LOOKBACK_DAYS = 10
PRICES = ("Open", "High", "Low", "Close")
PASS, FAIL, UNKNOWN = "pass", "fail", "unknown"
RESULTS = (PASS, FAIL, UNKNOWN)
RULES = {"cross_check.version": VERSION, "cross_check.feed": FEED, "cross_check.price_pct": PRICE_PCT,
         "cross_check.volume_pct": VOLUME_PCT, "cross_check.volume_basis": VOLUME_BASIS,
         "cross_check.max_names": MAX_NAMES}


def _pct(a: float, b: float) -> float | None:
    """The difference as a percentage of ``b``, unrounded: compared and stored exactly."""
    return None if b == 0 else abs(a - b) / abs(b) * 100


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _two(frame, session: date):
    """The signal session's bar, the volume of the row before it and that row's date, as plain
    numbers, or None when the frame has no signal-session row with one before it."""
    if frame is None or len(frame) == 0:
        return None
    dates = [d.date() if hasattr(d, "date") else d for d in frame.index]
    if session not in dates:
        return None
    i = dates.index(session)
    if i == 0:
        return None
    row, prev = frame.iloc[i], frame.iloc[i - 1]
    try:
        today = {k: float(row[k]) for k in (*PRICES, "Volume")}
        return today, float(prev["Volume"]), dates[i - 1]
    except (KeyError, TypeError, ValueError):
        return None


def judge(diffs: dict, price_pct: float, volume_pct: float) -> list[str]:
    """The fields over their tolerance; a difference that is not a finite number is over it."""
    over = [k for k in ("open", "high", "low", "close") if not _finite(diffs.get(k)) or diffs[k] > price_pct]
    if not _finite(diffs.get("volume")) or diffs["volume"] > volume_pct:
        over.append("volume")
    return over


def compare(sip, iex, session: date, basis: str = VOLUME_BASIS) -> dict:
    """One ticket's comparison of the two feeds' signal-day bars."""
    a, b = _two(sip, session), _two(iex, session)
    if a is None or b is None:
        return {"result": UNKNOWN, "reason": "no_sip_bar" if a is None else "no_iex_bar", "differences": None}
    (s, s_prior, s_date), (x, x_prior, x_date) = a, b
    if not all(_finite(v) and v > 0 for v in (*s.values(), *x.values())):
        return {"result": UNKNOWN, "reason": "bar_not_finite", "differences": None}
    diffs: dict[str, Any] = {k.lower(): _pct(x[k], s[k]) for k in PRICES}
    if basis == "absolute":
        diffs["volume"] = _pct(x["Volume"], s["Volume"])
    else:
        from src import sessions
        if s_date != x_date or s_date != sessions.previous_session(session):
            return {"result": UNKNOWN, "reason": "no_prior_session", "differences": None}
        if not (_finite(s_prior) and _finite(x_prior)) or s_prior <= 0 or x_prior <= 0:
            return {"result": UNKNOWN, "reason": "no_prior_volume", "differences": None}
        diffs["volume"] = _pct(x["Volume"] / x_prior, s["Volume"] / s_prior)
    over = judge(diffs, PRICE_PCT, VOLUME_PCT)
    return {"result": FAIL if over else PASS, "reason": ("differ: " + ", ".join(over)) if over else None,
            "differences": diffs}


def collect(client, tickets: list[dict], frames: dict, session: date, *, fetch=None) -> dict:
    """The night's cross-check. ``fetch(client, symbols, session)`` returns
    the iex frames by symbol; None asks the provider through ``market_data``."""
    block: dict[str, Any] = {"version": VERSION, "feed": FEED, "session": session.isoformat(),
                             "price_pct": PRICE_PCT, "volume_pct": VOLUME_PCT, "volume_basis": VOLUME_BASIS,
                             "rows": [], "status": "not_applicable"}
    names = [t for t in tickets][:MAX_NAMES]
    if names:
        try:
            iex = (fetch or _fetch)(client, sorted({t["ticker"] for t in names}), session)
            error = None
        except Exception as exc:  # noqa: BLE001 -- the provider's failure is every row unknown, never the night's
            iex, error = {}, type(exc).__name__
        for t in names:
            if error:
                row = {"result": UNKNOWN, "reason": f"iex_unavailable ({error})", "differences": None}
            else:
                row = compare(frames.get(t["ticker"]), iex.get(t["ticker"]), session)
            block["rows"].append({"stage": t["stage"], "ticker": t["ticker"], **row})
        for t in tickets[MAX_NAMES:]:
            block["rows"].append({"stage": t["stage"], "ticker": t["ticker"], "result": UNKNOWN,
                                  "reason": "not_checked", "differences": None})
    block["status"] = status_of(block["rows"])
    block["sentence"] = sentence(block)
    return block


def _fetch(client, symbols: list[str], session: date) -> dict:
    from alpaca.data.enums import DataFeed
    from src import market_data
    frames, _ = market_data.download_bars(client, symbols, session, LOOKBACK_DAYS, DataFeed.IEX)
    return frames


def status_of(rows: list[dict]) -> str:
    if not rows:
        return "not_applicable"
    return "fail" if any(r["result"] == FAIL for r in rows) else \
        "unknown" if any(r["result"] == UNKNOWN for r in rows) else "pass"


def sentence(block: dict) -> str:
    rows = block["rows"]
    if not rows:
        return "No ticket to cross-check."
    basis = ("each feed's volume against its own previous session" if block["volume_basis"] != "absolute"
             else "the two volumes")
    head = (f"Each ticket's signal-day bar was read again from the {block['feed']} feed: prices within "
            f"{block['price_pct']:g}% and {basis} within {block['volume_pct']:g}%.")
    failed = [r for r in rows if r["result"] == FAIL]
    unknown = [r for r in rows if r["result"] == UNKNOWN]
    tail = []
    if failed:
        tail.append("blocked: " + "; ".join(f"{r['ticker']} ({r['reason']})" for r in failed))
    if unknown:
        tail.append("not checked: " + "; ".join(f"{r['ticker']} ({r['reason']})" for r in unknown))
    passed = len(rows) - len(failed) - len(unknown)
    return head + f" {passed} of {len(rows)} agree" + ("; " + "; ".join(tail) if tail else "") + "."


def safe_collect(client, tickets: list[dict], frames: dict, session: date, **kwargs) -> dict:
    try:
        return collect(client, tickets, frames, session, **kwargs)
    except Exception:  # noqa: BLE001 -- the check never fails a night
        rows = [{"stage": t["stage"], "ticker": t["ticker"], "result": UNKNOWN, "reason": "not_checked",
                 "differences": None} for t in tickets]
        block = {"version": VERSION, "feed": FEED, "session": session.isoformat(), "price_pct": PRICE_PCT,
                 "volume_pct": VOLUME_PCT, "volume_basis": VOLUME_BASIS, "rows": rows}
        block["status"] = status_of(rows)
        block["sentence"] = sentence(block)
        return block


def faults(data: dict) -> list[str]:
    archived = (data.get("rules") or {}).get("cross_check") if isinstance(data.get("rules"), dict) else None
    run = data.get("run") if isinstance(data.get("run"), dict) else {}
    block = run.get("cross_check")
    if archived is None:
        return [] if block is None else ["run.cross_check present under rules that do not write it"]
    if not isinstance(archived, dict):
        return ["rules.cross_check is not an object"]
    if not isinstance(block, dict) or block.get("version") != VERSION:
        return ["run.cross_check is missing or not this version"]
    rows = block.get("rows")
    if not isinstance(rows, list) or not all(isinstance(r, dict) and r.get("result") in RESULTS
                                             and isinstance(r.get("ticker"), str) for r in rows):
        return ["run.cross_check rows are not readable"]
    if not (_finite(archived.get("price_pct")) and _finite(archived.get("volume_pct"))):
        return ["rules.cross_check tolerances are not numbers"]
    out = []
    for r in rows:
        if r["result"] == UNKNOWN:
            continue
        diffs = r.get("differences")
        if not isinstance(diffs, dict) or not all(_finite(diffs.get(k)) for k in ("open", "high", "low", "close", "volume")):
            out.append(f"run.cross_check {r['ticker']}: a {r['result']} row carries no finite differences")
        elif (FAIL if judge(diffs, archived.get("price_pct"), archived.get("volume_pct")) else PASS) != r["result"]:
            out.append(f"run.cross_check {r['ticker']}: its result is not what its differences give")
    if block.get("status") != status_of(rows):
        out.append("run.cross_check status is not its rows'")
    if (block.get("price_pct"), block.get("volume_pct"), block.get("volume_basis")) != \
            (archived.get("price_pct"), archived.get("volume_pct"), archived.get("volume_basis")):
        out.append("run.cross_check tolerances are not the rules it archived")
    if not isinstance(block.get("sentence"), str):
        out.append("run.cross_check sentence is not text")
    return out
