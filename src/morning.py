"""Dated observations of admitted orders. Never an order or a new judgement.

The publication remains immutable. IEX prices are single-venue observations;
delayed SIP daily volume is a separate, delayed measurement, not live pace.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile

from src import event_risk, market_data, morning_halts, plan, provenance, sessions, timing

VERSION = 1
MAX_PUBLICATION_BYTES = 32 * 1024 * 1024
MAX_OBSERVATION_BYTES = 512 * 1024
MAX_ROWS = 64
MAX_CONDITIONS = 32
MAX_NUMERIC_VALUE = 1e15
POLICY = {
    "version": VERSION, "quote_max_age_seconds": 60, "trade_max_age_seconds": 60,
    "snapshot_max_age_seconds": 300, "max_future_skew_seconds": 5,
    "delayed_sip_min_delay_seconds": 900, "preopen_minutes": 30,
    "max_collection_seconds": 180, "max_numeric_value": MAX_NUMERIC_VALUE,
    "market_timezone": "America/New_York",
    "halts": deepcopy(morning_halts.RULES),
}
LIMITS = ["dated_best_effort_snapshot", "iex_single_venue_not_consolidated",
          "delayed_volume_not_live_pace", "daily_bar_time_is_session_label_not_data_through",
          "no_order_or_fill_authority", "broker_verification_required"]
STATUSES = ("observed", "partial", "provider_unavailable", "no_tickets", "inapplicable")
PRICE_STATES = ("below_stop", "below_entry_floor", "below_trigger", "within_published_band",
                "above_limit", "above_day2_extension", "unknown")
SOURCE_ERRORS = (None, "missing_credentials", "authentication", "entitlement", "rate_limit", "timeout", "provider_error")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _number(value, *, zero=False):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value <= MAX_NUMERIC_VALUE
            and (value >= 0 if zero else value > 0))


def _instant(value):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
    else:
        return None
    return parsed if parsed.tzinfo is not None and parsed.utcoffset() is not None else None


def _iso(value):
    parsed = _instant(value)
    return parsed.isoformat() if parsed else None


def _get(value, key):
    return value.get(key) if isinstance(value, dict) else getattr(value, key, None)


def _text(value, maximum=32):
    value = getattr(value, "value", value)
    return value if isinstance(value, str) and 0 < len(value) <= maximum else None


def _conditions(value):
    if not isinstance(value, list) or len(value) > MAX_CONDITIONS:
        return None
    return value if all(_text(v, 16) is not None for v in value) else None


def _json(raw):
    def invalid(_):
        raise ValueError("nonfinite JSON constant")
    return json.loads(raw, parse_constant=invalid)


def _publication(raw, *, allow_fixture=False):
    _require(isinstance(raw, bytes) and len(raw) <= MAX_PUBLICATION_BYTES, "publication bytes exceed bound")
    data = _json(raw)
    _require(isinstance(data, dict), "publication must be an object")
    _require(allow_fixture or (not data.get("fixture") and data.get("run", {}).get("dry_run") is False),
             "production observations require a real publication")
    result = provenance.verify(data, require_sources=False)
    _require(result["status"] == "PASS", "publication integrity is not verified")
    run = data["run"]
    _require(run.get("status") in ("ok", "degraded", "closed"), "publication is not usable")
    _require(not timing._instant(run.get("timing"), "opens_at") is None, "publication timing is missing")
    _require(_instant(run.get("published_at")) is not None, "publication time is invalid")
    _require((allow_fixture and run.get("run_id") is None) or _text(run.get("run_id"), 128) is not None,
             "publication run identity is missing")
    binding = {"data_sha256": hashlib.sha256(raw).hexdigest(),
               "context_sha256": run["evidence"]["context_sha256"], "run_id": run["run_id"],
               "rules_version": data["app"]["rules_version"], "measured_session": run["session"],
               "applicable_session": run["timing"]["applicable_session"], "published_at": run["published_at"]}
    return data, binding


def bind_record(raw, *, allow_fixture=False):
    return _publication(raw, allow_fixture=allow_fixture)[1]


def admitted_rows(data):
    """Read admission from the original record; never derive a new ticket."""
    rows = []
    identities = set()
    candidates = [("burst", r) for r in data["bursts"]]
    candidates += [("anticipation", r) for r in data.get("watchlist", {}).get("top", [])]
    for kind, row in candidates:
        p, evidence = row.get("plan"), row.get("evidence") or {}
        if not evidence.get("gate", {}).get("ticket"):
            continue
        _require(isinstance(p, dict) and p.get("kind") == kind and p.get("ticker") == row["ticker"],
                 "admitted candidate identity differs")
        _require(p.get("eligible") is True and p.get("action") in plan.ORDER_ACTIONS
                 and p.get("allocation", {}).get("admitted") is True and isinstance(p.get("order_json"), dict),
                 "admitted candidate lacks executable allocation")
        _require(kind != "burst" or row["ticker"] in data["trades"], "burst admission differs")
        identity = (kind, row["ticker"])
        _require(identity not in identities, "duplicate admitted candidate")
        identities.add(identity)
        levels = {"trigger": p["entry_ref"] if kind == "burst" else p["trigger"],
                  "limit": p["limit"], "stop": p["stop"],
                  "entry_low": p.get("entry_low") if kind == "burst" else p["trigger"],
                  "day2_spent_above": p.get("day2_spent_above") if kind == "burst" else None}
        _require(all(_number(levels[k]) for k in ("trigger", "limit", "stop", "entry_low")), "invalid plan geometry")
        _require(levels["stop"] < levels["trigger"] <= levels["limit"], "invalid plan price ordering")
        _require(p["order_json"].get("stop_price") == levels["trigger"]
                 and p["order_json"].get("limit_price") == levels["limit"], "order prices differ from plan")
        rows.append({"ticker": row["ticker"], "kind": kind, "evidence_id": evidence["id"],
                     "plan_sha256": p["evidence_ref"]["plan_sha256"], "levels": levels})
    _require(len(rows) <= MAX_ROWS, "too many admitted candidates")
    return rows


def _age(timestamp, now, session, max_age, observed_at=None):
    at = _instant(timestamp)
    if at is None:
        return "invalid", None
    age = (now - at).total_seconds()
    if ((observed_at or now) - at).total_seconds() < -POLICY["max_future_skew_seconds"]:
        return "invalid", age
    state = "stale" if at.astimezone(sessions.MARKET_TZ).date().isoformat() != session or age > max_age else "recent"
    return state, age


def trade_observation(raw, now, session, available=True, *, observed_at=None):
    out = {"status": "missing" if available else "unavailable", "timestamp": None, "age_seconds": None,
           "price": None, "exchange": None, "conditions": None}
    if raw is None or not available:
        return out
    out.update(timestamp=_iso(_get(raw, "timestamp")), price=_get(raw, "price"),
               exchange=_text(_get(raw, "exchange")), conditions=_conditions(_get(raw, "conditions")))
    out["status"], out["age_seconds"] = _age(out["timestamp"], now, session, POLICY["trade_max_age_seconds"], observed_at)
    if not _number(out["price"]) or out["exchange"] is None or out["conditions"] is None:
        out.update(status="invalid", price=out["price"] if _number(out["price"]) else None)
    return out


def quote_observation(raw, now, session, available=True, *, observed_at=None):
    out = {"status": "missing" if available else "unavailable", "timestamp": None, "age_seconds": None,
           "bid": None, "ask": None, "bid_size": None, "ask_size": None,
           "bid_exchange": None, "ask_exchange": None, "conditions": None,
           "spread_usd": None, "spread_pct": None}
    if raw is None or not available:
        return out
    out["timestamp"] = _iso(_get(raw, "timestamp"))
    for target, source in (("bid", "bid_price"), ("ask", "ask_price"), ("bid_size", "bid_size"), ("ask_size", "ask_size")):
        value = _get(raw, source)
        out[target] = value if _number(value) else None
    for name in ("bid_exchange", "ask_exchange"):
        out[name] = _text(_get(raw, name))
    out["conditions"] = _conditions(_get(raw, "conditions"))
    out["status"], out["age_seconds"] = _age(out["timestamp"], now, session, POLICY["quote_max_age_seconds"], observed_at)
    if any(out[k] is None for k in ("bid", "ask", "bid_size", "ask_size", "bid_exchange", "ask_exchange", "conditions")) or out["ask"] < out["bid"]:
        out["status"] = "invalid"
    else:
        delta = out["ask"] - out["bid"]
        percentage = delta / (out["bid"] / 2 + out["ask"] / 2) * 100
        if not math.isfinite(delta) or not math.isfinite(percentage):
            out["status"] = "invalid"
        else:
            out["spread_usd"], out["spread_pct"] = round(delta, 8), round(percentage, 8)
    return out


def price_state(price, levels, status):
    if status != "recent" or not _number(price):
        return "unknown"
    if price <= levels["stop"]:
        return "below_stop"
    if price < levels["entry_low"]:
        return "below_entry_floor"
    if levels["day2_spent_above"] is not None and price > levels["day2_spent_above"]:
        return "above_day2_extension"
    if price > levels["limit"]:
        return "above_limit"
    if price < levels["trigger"]:
        return "below_trigger"
    return "within_published_band"


def volume_observation(raw, now, session, previous, available=True, *, observed_at=None):
    if not available:
        raw = None
    daily, prior = _get(raw, "daily_bar"), _get(raw, "previous_daily_bar")
    latest = _get(raw, "latest_trade")
    out = {"status": "missing" if available else "unavailable", "daily_timestamp": _iso(_get(daily, "timestamp")),
           "previous_timestamp": _iso(_get(prior, "timestamp")), "latest_trade_timestamp": _iso(_get(latest, "timestamp")),
           "session": None, "partial_volume": None, "previous_volume": None,
           "comparison": "unknown", "data_through": None}
    if raw is None:
        return out
    partial, previous_volume = _get(daily, "volume"), _get(prior, "volume")
    out["partial_volume"] = partial if _number(partial, zero=True) else None
    out["previous_volume"] = previous_volume if _number(previous_volume) else None
    stamp, prev_stamp, trade_stamp = (_instant(out[k]) for k in ("daily_timestamp", "previous_timestamp", "latest_trade_timestamp"))
    if not stamp or not prev_stamp or out["partial_volume"] is None or out["previous_volume"] is None:
        out["status"] = "invalid"
        return out
    out["session"] = stamp.astimezone(sessions.MARKET_TZ).date().isoformat()
    observed_at = observed_at or now
    if stamp > observed_at or prev_stamp > observed_at or (trade_stamp and (observed_at - trade_stamp).total_seconds() < POLICY["delayed_sip_min_delay_seconds"] - POLICY["max_future_skew_seconds"]):
        out["status"] = "invalid"
    elif out["session"] != session or prev_stamp.astimezone(sessions.MARKET_TZ).date().isoformat() != previous:
        out["status"] = "prior_session"
    else:
        out["status"] = "delayed"
        out["comparison"] = "above_prior_total" if partial > previous_volume else "not_above_prior_total"
    return out


def _source(feed):
    return {"status": "not_requested", "feed": feed,
            "scope": "single_venue" if feed == "iex" else "consolidated_delayed",
            "entitlement": "not_requested", "checked_at": None, "error_kind": None,
            "minimum_delay_seconds": 0 if feed == "iex" else POLICY["delayed_sip_min_delay_seconds"]}


def _error(exc):
    code = getattr(exc, "status_code", None)
    if code is None:
        code = getattr(getattr(exc, "response", None), "status_code", None)
    return {401: "authentication", 403: "entitlement", 429: "rate_limit"}.get(code,
            "timeout" if "timeout" in type(exc).__name__.lower() else "provider_error")


def _fetch(client, symbols, feed, clock):
    from alpaca.data.enums import DataFeed
    from alpaca.data.requests import StockSnapshotRequest
    source = _source(feed)
    try:
        response = client.get_stock_snapshot(StockSnapshotRequest(symbol_or_symbols=symbols, feed=DataFeed(feed)))
        _require(isinstance(response, dict), "snapshot response must be a mapping")
        source.update(status="ok", entitlement="request_succeeded")
    except Exception as exc:
        response = {}
        source.update(status="unavailable", entitlement="unavailable", error_kind=_error(exc))
    source["checked_at"] = clock().isoformat()
    return response, source


def _reason(data, now):
    tm = data["run"]["timing"]
    if sessions.market_time(now).date().isoformat() != tm["applicable_session"]:
        return "wrong_session"
    if timing.phase(tm, now) not in (timing.PHASE_UPCOMING, timing.PHASE_OPEN):
        return "entry_window_ended"
    if now < timing._instant(tm, "opens_at") - timedelta(minutes=POLICY["preopen_minutes"]):
        return "before_collection_window"
    if data["run"]["session"] != sessions.completed_session(now).isoformat():
        return "stale_publication"
    if _instant(data["run"]["published_at"]) > now + timedelta(seconds=POLICY["max_future_skew_seconds"]):
        return "future_publication"
    return None


def _status(rows, sources, reason):
    return ("inapplicable" if reason else "no_tickets" if not rows else
            "provider_unavailable" if all(s["status"] == "unavailable" for s in sources.values()) else
            "observed" if all(r["trade"]["status"] == r["quote"]["status"] == "recent"
                              and r["delayed_volume"]["status"] == "delayed" for r in rows) else "partial")


def _halt_result(observation):
    return {"coverage": observation["coverage"],
            "symbols": {r["ticker"]: {"halt": r["events"]["halt"]} for r in observation["rows"]},
            "retained": observation["halt_memory"]}


def _validate_corporate_memory(memory, now):
    _require(isinstance(memory, dict), "invalid corporate memory")
    count = 0
    for symbol, facts in memory.items():
        _require(isinstance(symbol, str) and re.fullmatch(r"[A-Z][A-Z0-9.\-]*", symbol)
                 and isinstance(facts, list) and facts, "invalid retained corporate symbol")
        ids = set()
        for fact in facts:
            count += 1
            _require(count <= event_risk.MAX_EVENTS and isinstance(fact, dict)
                     and set(fact) == {"event", "registry_sha256", "registry_reviewed_on", "observed_at"}, "invalid corporate fact")
            observed = _instant(fact["observed_at"])
            _require(observed is not None and observed <= now + timedelta(seconds=POLICY["max_future_skew_seconds"]), "invalid corporate observation time")
            _require(isinstance(fact["registry_sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", fact["registry_sha256"]), "invalid corporate registry identity")
            event = deepcopy(fact["event"])
            _require(isinstance(event, dict) and event.get("symbol") == symbol
                     and event.get("id") not in ids and type(event.get("review_overdue")) is bool, "invalid retained corporate event")
            ids.add(event["id"])
            event.pop("review_overdue")
            event_risk.validate_registry({"version": event_risk.VERSION, "coverage": event_risk.COVERAGE,
                                         "coverage_note": "Retained source-backed morning exclusion.",
                                         "reviewed_on": fact["registry_reviewed_on"], "events": [event]})
            day = observed.astimezone(sessions.MARKET_TZ).date().isoformat()
            _require(event["active_from"] <= day and (not event.get("active_until") or day < event["active_until"]),
                     "corporate event was inactive when retained")


def _corporate_fact(current, event, observed_at):
    return {"event": deepcopy(event), "registry_sha256": current["registry_sha256"],
            "registry_reviewed_on": current["registry_reviewed_on"], "observed_at": observed_at.isoformat()}


def _validate_corporate(current, symbol, session, now):
    _require(isinstance(current, dict) and set(current) == {"version", "coverage", "registry_sha256",
                 "registry_reviewed_on", "session", "symbol", "blocked", "status", "reason", "matches"}, "invalid current corporate classification")
    _require(current["version"] == event_risk.VERSION and current["coverage"] == event_risk.COVERAGE
             and current["symbol"] == symbol and current["session"] == session
             and type(current["blocked"]) is bool and isinstance(current["matches"], list)
             and current["blocked"] == bool(current["matches"]), "corporate classification identity differs")
    _require(isinstance(current["registry_sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", current["registry_sha256"])
             and _text(current["reason"], event_risk.MAX_TEXT_LENGTH * event_risk.MAX_EVENTS), "invalid corporate metadata")
    event_risk._day(current["registry_reviewed_on"])
    expected = "review_required" if any(e.get("review_overdue") for e in current["matches"]) else "known_event" if current["matches"] else "not_in_registry"
    _require(current["status"] == expected, "corporate status contradicts evidence")
    if current["matches"]:
        _validate_corporate_memory({symbol: [_corporate_fact(current, event, now) for event in current["matches"]]}, now)


def _validate_corporate_resolutions(resolutions, now):
    _require(isinstance(resolutions, list) and len(resolutions) <= event_risk.MAX_EVENTS,
             "invalid corporate resolution list")
    identities = set()
    for proof in resolutions:
        _require(isinstance(proof, dict) and set(proof) == {"event_id", "symbol", "active_from", "active_until",
                  "resolution", "registry_sha256", "registry_reviewed_on", "observed_at"}, "invalid corporate resolution fact")
        _require(_text(proof["event_id"], event_risk.MAX_TEXT_LENGTH) is not None and isinstance(proof["symbol"], str)
                 and re.fullmatch(r"[A-Z][A-Z0-9.\-]*", proof["symbol"]), "invalid resolved event identity")
        start, end = event_risk._day(proof["active_from"]), event_risk._day(proof["active_until"])
        source_day = event_risk._source(proof["resolution"])
        reviewed = event_risk._day(proof["registry_reviewed_on"])
        observed = _instant(proof["observed_at"])
        _require(observed is not None and observed <= now + timedelta(seconds=POLICY["max_future_skew_seconds"])
                 and start < end and source_day <= end <= reviewed <= observed.astimezone(sessions.MARKET_TZ).date(),
                 "corporate resolution dates differ")
        _require(isinstance(proof["registry_sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", proof["registry_sha256"]),
                 "invalid corporate resolution registry identity")
        identity = (proof["symbol"], proof["event_id"], proof["active_from"])
        _require(identity not in identities, "duplicate corporate resolution")
        identities.add(identity)


def _new_corporate_resolutions(previous, now, session):
    """Only explicit current-registry evidence can resolve a retained event."""
    current_events = {e["id"]: e for e in event_risk.REGISTRY["events"]}
    proofs = []
    for symbol, facts in (previous or {}).items():
        for fact in facts:
            current = current_events.get(fact["event"]["id"])
            if (current and current["symbol"] == symbol and current["active_from"] == fact["event"]["active_from"]
                    and current.get("active_until") and current.get("resolution")
                    and current["active_until"] <= session and current["resolution"]["published_on"] <= session
                    and fact["registry_reviewed_on"] <= event_risk.REGISTRY["reviewed_on"]
                    <= now.astimezone(sessions.MARKET_TZ).date().isoformat()
                    and now >= _instant(fact["observed_at"])):
                proofs.append({"event_id": current["id"], "symbol": symbol, "active_from": current["active_from"],
                               "active_until": current["active_until"], "resolution": deepcopy(current["resolution"]),
                               "registry_sha256": event_risk.registry_digest(event_risk.REGISTRY),
                               "registry_reviewed_on": event_risk.REGISTRY["reviewed_on"], "observed_at": now.isoformat()})
    _validate_corporate_resolutions(proofs, now)
    return proofs


def _corporate_resolutions(previous_proofs, previous_memory, now, session):
    """Keep bounded resolution sources for a browser that missed their first receipt."""
    _validate_corporate_resolutions(previous_proofs, now)
    proofs = {(p["symbol"], p["event_id"], p["active_from"]): deepcopy(p) for p in previous_proofs}
    for proof in _new_corporate_resolutions(previous_memory, now, session):
        identity = (proof["symbol"], proof["event_id"], proof["active_from"])
        if identity not in proofs or any(proofs[identity][k] != proof[k] for k in proof if k != "observed_at"):
            proofs[identity] = proof
    result = list(proofs.values())
    _validate_corporate_resolutions(result, now)
    return result


def _corporate_memory(previous, classifications, now, session):
    memory = deepcopy(previous or {})
    _validate_corporate_memory(memory, now)
    resolved = {(p["symbol"], p["event_id"], p["active_from"]) for p in _new_corporate_resolutions(memory, now, session)}
    for symbol, facts in list(memory.items()):
        kept = [fact for fact in facts if (symbol, fact["event"]["id"], fact["event"]["active_from"]) not in resolved]
        if kept:
            memory[symbol] = kept
        else:
            del memory[symbol]
    for symbol, current in classifications.items():
        _validate_corporate(current, symbol, session, now)
        prior = {f["event"]["id"]: f for f in memory.get(symbol, [])}
        for event in current["matches"]:
            fact = _corporate_fact(current, event, now)
            # Keep the first actual observation of unchanged evidence.
            if event["id"] not in prior or any(prior[event["id"]][k] != fact[k] for k in ("event", "registry_sha256", "registry_reviewed_on")):
                prior[event["id"]] = fact
        if prior:
            memory[symbol] = list(prior.values())
    _validate_corporate_memory(memory, now)
    return memory


def _previous_halts(previous_raw, publication_raw, binding):
    if previous_raw is None:
        return None
    from src import morning_halts
    _require(isinstance(previous_raw, bytes) and len(previous_raw) <= MAX_OBSERVATION_BYTES, "prior receipt exceeds size bound")
    previous = _json(previous_raw)
    _require(isinstance(previous, dict) and previous.get("schema_version") == VERSION,
             "prior receipt is unsupported")
    if previous.get("publication", {}).get("data_sha256") == binding["data_sha256"]:
        validate_observation(previous, publication_raw)
    # Across publications, carry independently validated halt facts only.
    # Quotes, grades, levels, receipt state and plan authority never migrate.
    facts = _halt_result(previous)
    morning_halts.validate(facts, list(facts["symbols"]), previous["generated_at"])
    _validate_corporate_memory(previous["corporate_memory"], _instant(previous["generated_at"]))
    _validate_corporate_resolutions(previous["corporate_resolutions"], _instant(previous["generated_at"]))
    return facts


def collect(raw, *, client=None, clock=None, event_observer=None, dry_run=False, observation_run_id=None,
            previous_raw=None):
    """Collect bounded observations using an injectable clock/provider for tests."""
    from src import morning_halts
    clock = clock or (lambda: datetime.now(timezone.utc))
    event_observer = event_observer or morning_halts.observe
    started = clock()
    _require(_instant(started) is not None, "collection requires an aware clock")
    data, binding = _publication(raw, allow_fixture=dry_run)
    previous_halts = _previous_halts(previous_raw, raw, binding)
    base_rows = admitted_rows(data)
    reason = _reason(data, started)
    requested = [] if reason else sorted({r["ticker"] for r in base_rows})
    sources = {feed: _source(feed) for feed in ("iex", "delayed_sip")}
    responses = {feed: {} for feed in sources}
    if requested:
        if client is None and any(not os.environ.get(k, "").strip() for k in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY")):
            for source in sources.values():
                source.update(status="unavailable", entitlement="unavailable", checked_at=clock().isoformat(), error_kind="missing_credentials")
        else:
            client = client or market_data.get_clients()
            for feed in sources:
                responses[feed], sources[feed] = _fetch(client, requested, feed, clock)
    events = event_observer(requested, clock, previous=previous_halts)
    completed = clock()
    _require(_instant(completed) is not None and completed >= started, "collection clock moved backwards")
    # A delayed provider call can outlive the window. Retain the observations,
    # with the actual completion phase; no result grants an entry permission.
    rows = []
    classifications = {symbol: event_risk.classify(symbol, binding["applicable_session"]) for symbol in requested}
    prior_corporate = _json(previous_raw)["corporate_memory"] if previous_raw is not None else {}
    prior_resolutions = _json(previous_raw)["corporate_resolutions"] if previous_raw is not None else []
    corporate_memory = _corporate_memory(prior_corporate, classifications, completed, binding["applicable_session"])
    corporate_resolutions = _corporate_resolutions(prior_resolutions, prior_corporate, completed, binding["applicable_session"])
    for base in base_rows if requested else []:
        ticker = base["ticker"]
        live, delayed = responses["iex"].get(ticker), responses["delayed_sip"].get(ticker)
        trade = trade_observation(_get(live, "latest_trade"), completed, binding["applicable_session"], sources["iex"]["status"] == "ok", observed_at=_instant(sources["iex"]["checked_at"]))
        quote = quote_observation(_get(live, "latest_quote"), completed, binding["applicable_session"], sources["iex"]["status"] == "ok", observed_at=_instant(sources["iex"]["checked_at"]))
        rows.append({**base, "trade": trade, "quote": quote,
                     "price_checks": {"trade": price_state(trade["price"], base["levels"], trade["status"]),
                                      "ask": price_state(quote["ask"], base["levels"], quote["status"])},
                     "delayed_volume": volume_observation(delayed, completed, binding["applicable_session"], binding["measured_session"], sources["delayed_sip"]["status"] == "ok", observed_at=_instant(sources["delayed_sip"]["checked_at"])),
                     "events": {**events["symbols"][ticker], "corporate_action": classifications[ticker],
                                "retained_corporate_actions": [f for f in corporate_memory.get(ticker, [])
                                     if f["event"]["id"] not in {e["id"] for e in classifications[ticker]["matches"]}]}})
    out = {"schema_version": VERSION, "collection_started_at": started.isoformat(),
           "generated_at": completed.isoformat(), "expires_at": (completed + timedelta(seconds=POLICY["snapshot_max_age_seconds"])).isoformat(),
           "observation_run_id": str(observation_run_id or os.environ.get("GITHUB_RUN_ID") or "local"),
           "previous_observation_sha256": hashlib.sha256(previous_raw).hexdigest() if previous_raw is not None else None,
           "dry_run": bool(dry_run), "publication": binding, "policy": deepcopy(POLICY),
           "status": _status(rows, sources, reason), "reason": reason, "entry_phase": timing.phase(data["run"]["timing"], completed),
           "sources": sources, "coverage": events["coverage"], "halt_memory": events["retained"], "corporate_memory": corporate_memory,
           "corporate_resolutions": corporate_resolutions,
           "rows": rows, "limits": list(LIMITS)}
    validate_observation(out, raw, previous_raw=previous_raw, require_continuity=True)
    return out


def validate_observation(out, raw, *, previous_raw=None, require_continuity=False):
    """Strict offline gate for persistence and archived observation fixtures."""
    try:
        _validate_observation(out, raw, previous_raw=previous_raw, require_continuity=require_continuity)
    except (KeyError, TypeError, AttributeError, IndexError, OverflowError) as exc:
        raise ValueError("malformed observation structure") from None


def _validate_observation(out, raw, *, previous_raw=None, require_continuity=False):
    _require(isinstance(out, dict) and type(out.get("schema_version")) is int
             and out.get("schema_version") == VERSION and type(out.get("dry_run")) is bool,
             "unsupported observation envelope")
    _require(set(out) == {"schema_version", "collection_started_at", "generated_at", "expires_at",
                         "observation_run_id", "previous_observation_sha256", "dry_run", "publication", "policy",
                         "status", "reason", "entry_phase", "sources", "coverage", "halt_memory", "corporate_memory", "corporate_resolutions", "rows", "limits"},
             "observation envelope fields differ")
    previous_sha = out["previous_observation_sha256"]
    _require(previous_sha is None or isinstance(previous_sha, str) and re.fullmatch(r"[0-9a-f]{64}", previous_sha), "invalid prior receipt binding")
    data, binding = _publication(raw, allow_fixture=out["dry_run"])
    _require(out.get("publication") == binding, "observation publication binding differs")
    _require(provenance.digest(out.get("policy")) == provenance.digest(POLICY)
             and out.get("limits") == LIMITS, "observation policy differs")
    _require(_text(out.get("observation_run_id"), 128) is not None, "invalid observation run identity")
    started, generated, expires = (_instant(out.get(k)) for k in ("collection_started_at", "generated_at", "expires_at"))
    _require(all((started, generated, expires)) and started <= generated and expires == generated + timedelta(seconds=POLICY["snapshot_max_age_seconds"]), "invalid collection time ordering")
    _require((generated - started).total_seconds() <= POLICY["max_collection_seconds"], "collection exceeded duration bound")
    _require(out.get("status") in STATUSES and out.get("reason") == _reason(data, started), "invalid observation outcome")
    _require(out.get("entry_phase") == timing.phase(data["run"]["timing"], generated), "observation phase differs")
    admitted = admitted_rows(data)
    expected = [] if out["reason"] else admitted
    rows = out.get("rows")
    _validate_corporate_memory(out["corporate_memory"], generated)
    _validate_corporate_resolutions(out["corporate_resolutions"], generated)
    _require(isinstance(rows, list) and len(rows) == len(expected), "observation row membership differs")
    sources = out.get("sources")
    _require(isinstance(sources, dict) and set(sources) == {"iex", "delayed_sip"}, "invalid source coverage")
    for feed, source in sources.items():
        reference = _source(feed)
        _require(isinstance(source, dict) and set(source) == set(reference), "invalid feed metadata")
        for key in ("feed", "scope", "minimum_delay_seconds"):
            _require(source[key] == reference[key], "feed scope differs")
        _require(source["error_kind"] in SOURCE_ERRORS, "unknown provider error")
        if not expected:
            _require(source == reference, "inapplicable run requested a provider")
        else:
            checked = _instant(source["checked_at"])
            _require(checked is not None and started <= checked <= generated, "invalid provider check time")
            _require((source["status"], source["entitlement"]) in (("ok", "request_succeeded"), ("unavailable", "unavailable")), "invalid entitlement observation")
            _require((source["error_kind"] is None) == (source["status"] == "ok"), "provider status contradicts error")
    for row, base in zip(rows, expected, strict=True):
        _require(isinstance(row, dict) and set(row) == set(base) | {"trade", "quote", "price_checks", "delayed_volume", "events"}
                 and all(row.get(k) == v for k, v in base.items()), "candidate identity or levels differ")
        trade, quote, volume = row.get("trade"), row.get("quote"), row.get("delayed_volume")
        _require(isinstance(trade, dict) and isinstance(quote, dict) and isinstance(volume, dict), "missing quote observations")
        for datum in (trade, quote):
            _require(datum.get("status") in ("recent", "stale", "missing", "invalid", "unavailable"), "unknown quote state")
            _require(datum.get("conditions") is None or _conditions(datum["conditions"]) is not None, "invalid quote conditions")
        replay_trade = trade_observation(trade if trade["status"] not in ("missing", "unavailable") else None, generated, binding["applicable_session"], sources["iex"]["status"] == "ok", observed_at=_instant(sources["iex"]["checked_at"]))
        quote_raw = {**quote, "bid_price": quote.get("bid"), "ask_price": quote.get("ask")}
        replay_quote = quote_observation(quote_raw if quote["status"] not in ("missing", "unavailable") else None, generated, binding["applicable_session"], sources["iex"]["status"] == "ok", observed_at=_instant(sources["iex"]["checked_at"]))
        _require(trade == replay_trade and quote == replay_quote, "quote observation cannot be reproduced")
        _require(row.get("price_checks") == {"trade": price_state(trade["price"], base["levels"], trade["status"]), "ask": price_state(quote["ask"], base["levels"], quote["status"])}, "price comparison differs")
        volume_raw = {"daily_bar": {"timestamp": volume.get("daily_timestamp"), "volume": volume.get("partial_volume")},
                      "previous_daily_bar": {"timestamp": volume.get("previous_timestamp"), "volume": volume.get("previous_volume")},
                      "latest_trade": {"timestamp": volume.get("latest_trade_timestamp")}}
        replay_volume = volume_observation(volume_raw if volume.get("status") not in ("missing", "unavailable") else None, generated, binding["applicable_session"], binding["measured_session"], sources["delayed_sip"]["status"] == "ok", observed_at=_instant(sources["delayed_sip"]["checked_at"]))
        _require(volume == replay_volume, "delayed volume cannot be reproduced")
        _require(isinstance(row.get("events"), dict) and set(row["events"]) == {"halt", "corporate_action", "retained_corporate_actions"}
                 and isinstance(row["events"].get("halt"), dict)
                 and isinstance(row["events"].get("corporate_action"), dict), "missing event coverage")
        corporate = row["events"]["corporate_action"]
        _validate_corporate(corporate, row["ticker"], binding["applicable_session"], generated)
        memory = out["corporate_memory"].get(row["ticker"], [])
        current_ids = {e["id"] for e in corporate["matches"]}
        _require(row["events"]["retained_corporate_actions"] == [f for f in memory if f["event"]["id"] not in current_ids],
                 "retained corporate evidence differs")
        _require(current_ids <= {f["event"]["id"] for f in memory}, "current corporate exclusion is not retained")
    _require(out["status"] == _status(rows, sources, out["reason"]), "observation status contradicts its measurements")
    # Event source validation belongs to the source adapter, including stale
    # absence and the distinction between quote and trading resumptions.
    from src import morning_halts
    event_result = _halt_result(out)
    morning_halts.validate(event_result, [r["ticker"] for r in expected], generated)
    if require_continuity or previous_raw is not None:
        prior_sha = hashlib.sha256(previous_raw).hexdigest() if previous_raw is not None else None
        _require(out["previous_observation_sha256"] == prior_sha, "prior observation bytes differ")
        previous_events = _previous_halts(previous_raw, raw, binding)
        if previous_events is not None:
            morning_halts.validate_continuity(event_result, previous_events)
        prior_corporate = _json(previous_raw)["corporate_memory"] if previous_raw is not None else {}
        classifications = {r["ticker"]: r["events"]["corporate_action"] for r in rows}
        _require(out["corporate_memory"] == _corporate_memory(prior_corporate, classifications, generated, binding["applicable_session"]),
                 "corporate exclusion continuity differs")
        prior_resolutions = _json(previous_raw)["corporate_resolutions"] if previous_raw is not None else []
        _require(out["corporate_resolutions"] == _corporate_resolutions(prior_resolutions, prior_corporate, generated, binding["applicable_session"]),
                 "corporate resolution continuity differs")
    encoded = json.dumps(out, allow_nan=False, separators=(",", ":")).encode()
    _require(len(encoded) <= MAX_OBSERVATION_BYTES, "observation exceeds size bound")


def run(*, docs=Path("docs"), output=None, dry_run=False, client=None, clock=None, event_observer=None):
    docs = Path(docs)
    output = Path(output) if output is not None else docs / "morning.json"
    _require(output.resolve() == (docs / "morning.json").resolve()
             or not output.resolve().is_relative_to(docs.resolve()), "output must not overwrite publication files")
    raw = (docs / "data.json").read_bytes()
    previous_path = docs / "morning.json"
    previous_raw = previous_path.read_bytes() if previous_path.exists() else None
    observation = collect(raw, client=client, clock=clock, event_observer=event_observer, dry_run=dry_run,
                          previous_raw=previous_raw)
    _require((docs / "data.json").read_bytes() == raw, "publication changed during collection")
    _require((previous_path.read_bytes() if previous_path.exists() else None) == previous_raw,
             "previous observation changed during collection")
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(observation, allow_nan=False, indent=2).encode() + b"\n"
    with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".morning-", delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            os.replace(temporary, output)
        finally:
            temporary.unlink(missing_ok=True)
    return observation


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--docs", type=Path, default=Path("docs"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = run(docs=args.docs, output=args.output, dry_run=args.dry_run)
    except Exception:
        print("Morning observation refused: invalid publication or collection; no receipt replaced.")
        return 1
    print(json.dumps({"status": result["status"], "reason": result["reason"], "rows": len(result["rows"]),
                      "generated_at": result["generated_at"], "data_sha256": result["publication"]["data_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
