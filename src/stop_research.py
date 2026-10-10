"""Registered, source-bound anticipation sensitivity. Never an order authority.

The production planner remains at its archived cap. This optional producer
changes one explicit pure-helper input, preserves baseline allocation first,
and emits no executable order fields. No network or model calls occur here.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile

from src import reader

VERSION = 1
POLICY_ID = "anticipation_stop_width_4_to_5_v1"
BASELINE_STOP_PCT = 4.0
RESEARCH_STOP_PCT = 5.0
START_SESSION = "2026-10-12"
END_SESSION = "2026-11-06"
ACCOUNT = {"equity": 2000, "risk_pct": 0.5, "max_position_pct": 25, "max_open_positions": 4}
MAX_ROWS = 5
MAX_BUNDLES = 128
MAX_ARCHIVE_BYTES = 16 * 1024 * 1024
MAX_RECEIPT_BYTES = 16 * 1024
MAX_BUNDLE_BYTES = 128 * 1024
MAX_INDEX_BYTES = 64 * 1024
MAX_PUBLICATION_BYTES = reader.MAX_PUBLICATION_BYTES
MAX_FUTURE_SECONDS = 5
RECEIPT_FILE = "stop-research.json"
BUNDLE_DIR = "stop-research"
INDEX_FILE = BUNDLE_DIR + "/index.json"
HEX = re.compile(r"[a-f0-9]{64}\Z")
BUNDLE_PATH = re.compile(r"stop-research/[a-f0-9]{64}\.json\Z")
POLICY = {"version": VERSION, "id": POLICY_ID, "applicable_start": START_SESSION,
          "applicable_end": END_SESSION, "baseline_stop_pct": BASELINE_STOP_PCT,
          "research_stop_pct": RESEARCH_STOP_PCT, "account": ACCOUNT,
          "allocation": "baseline_first_then_original_watchlist_rank",
          "geometry": "unchanged_anticipation_trigger_limit_structural_stop",
          "review": "existing_anticipation_policy_no_new_chart_review"}
BLOCKERS = ("outside_band", "watchlist_ineligible", "market_gate", "known_event",
            "invalid_inputs", "no_whole_share", "occupied_model_symbol",
            "baseline_symbol_reserved", "slot_cap", "equity", "duplicate")
LIMITS = ["research_only_no_orders", "manual_known_events_not_news_clearance",
          "no_new_chart_review", "no_live_quote_or_earnings_check",
          "principal_excludes_actual_fees", "price_to_stop_risk_excludes_gaps_slippage",
          "model_reservations_not_broker_cash", "no_returns_or_strategy_edge_established"]
BINDING_KEYS = {"data_sha256", "context_sha256", "run_id", "rules_version", "measured_session",
                "applicable_session", "published_at", "reader_projection_version", "reader_sha256"}
COMMON_KEYS = {"schema_version", "policy", "publication", "timing", "status", "reason", "counts"}
ROW_KEYS = {"rank", "ticker", "evidence", "in_band", "baseline", "levels", "research", "event", "quality"}
RESEARCH_KEYS = {"mechanical_fit", "allocation_fit", "shares", "principal_usd", "risk_usd",
                 "risk_per_share", "effective_risk_budget_usd", "multipliers", "blockers", "projection_sha256"}
RESERVATION_KEYS = {"equity_usd", "position_cap_usd", "max_slots", "open_model_principal_usd",
                    "open_model_slots", "open_symbols", "baseline_principal_usd", "baseline_risk_usd",
                    "baseline_slots", "baseline_symbols", "available_principal_usd_before_research",
                    "research_principal_usd", "research_risk_usd", "research_slots", "slots_used",
                    "remaining_model_principal_usd"}


def _require(condition, reason):
    if not condition:
        raise ValueError("stop research: " + reason)


def _encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _decode(raw, maximum):
    _require(isinstance(raw, bytes) and 0 < len(raw) <= maximum, "bytes exceed bound")
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    def invalid(_):
        raise ValueError("stop research: nonfinite JSON")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid)


def _keys(value, keys):
    return isinstance(value, dict) and set(value) == set(keys)


def _number(value, positive=False):
    return type(value) in (int, float) and math.isfinite(value) and (value > 0 if positive else value >= 0) and value <= 1e15


def _integer(value, maximum=1000000):
    return type(value) is int and 0 <= value <= maximum


def _cents(value):
    """Validate published money without a planner/calendar import."""
    _require(_number(value), "invalid cents amount")
    scaled = Decimal(str(value)) * 100
    _require(scaled == scaled.to_integral_value(), "money has subcent precision")
    return int(scaled)


def _instant(value):
    _require(isinstance(value, (str, datetime)), "missing aware timestamp")
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    _require(parsed.tzinfo is not None and parsed.utcoffset() is not None, "naive timestamp")
    return parsed.astimezone(timezone.utc)


def _day(value):
    _require(isinstance(value, str) and date.fromisoformat(value).isoformat() == value, "invalid session")
    return value


def _timing(data, generated_at):
    generated = _instant(generated_at)
    opens = _instant(data["run"]["timing"]["opens_at"])
    cutoff = _instant(data["run"]["timing"]["cutoff_at"])
    _require(opens < cutoff, "invalid entry window")
    _require(_instant(data["run"]["published_at"]) <= generated + timedelta(seconds=MAX_FUTURE_SECONDS), "publication is in the future")
    return {"generated_at": generated.isoformat(), "entry_opens_at": opens.isoformat(),
            "entry_cutoff_at": cutoff.isoformat(), "classification": "before_entry" if generated < opens else "during_entry" if generated < cutoff else "after_entry"}


def _counts(rows, top_count):
    return {"top_count": top_count, "considered": len(rows), "in_band": sum(row["in_band"] for row in rows),
            "mechanical_fit": sum(row["research"]["mechanical_fit"] for row in rows),
            "allocation_fit": sum(row["research"]["allocation_fit"] for row in rows),
            "by_blocker": {key: sum(key in row["research"]["blockers"] for row in rows) for key in BLOCKERS}}


def _projection(row):
    return {"evidence": row["evidence"], "levels": row["levels"], "policy": POLICY,
            "research": {k: v for k, v in row["research"].items() if k != "projection_sha256"}}


def build(canonical_raw, *, objects=None, picks=None, generated_at=None, allow_fixture=False, require_sources=True):
    """Pure for explicit inputs/clock; source verification is mandatory by default.

    Integrity-only replay is restricted to validator use with an already
    recorded receipt. Production integration always supplies retained sources.
    """
    from src import allocation, event_risk, morning, plan, provenance

    data = _decode(canonical_raw, MAX_PUBLICATION_BYTES)
    data, binding = morning._publication(canonical_raw, allow_fixture=allow_fixture)
    _require(all(_number(data["account"].get(k), True) and data["account"][k] == v for k, v in ACCOUNT.items()), "unsupported account")
    _require(data["rules"]["plan"] == {k.partition(".")[2]: v for k, v in plan.RULES.items()}, "unsupported planner rules")
    _require(data["rules"]["plan"]["max_stop_pct"] == BASELINE_STOP_PCT, "unsupported baseline cap")
    _require(data["rules"].get("event_risk", {}).get("coverage") == event_risk.COVERAGE, "missing archived event coverage")
    checked = provenance.verify(data, picks, objects, require_sources=require_sources, require_picks=picks is not None)
    _require(checked["status"] == "PASS", "publication sources or provenance are not verified")
    top = data.get("watchlist", {}).get("top", [])
    _require(isinstance(top, list) and len(top) <= MAX_ROWS, "top cohort exceeds bound")
    timing = _timing(data, datetime.now(timezone.utc) if generated_at is None else generated_at)
    in_period = START_SESSION <= binding["applicable_session"] <= END_SESSION
    status = "recorded" if in_period else "outside_period"
    reason = None if in_period else "The applicable session is outside the registered experiment period."
    account = plan.Account(**ACCOUNT)
    original_rows = data["bursts"] + top
    baseline_plans = [deepcopy(row["plan"]) for row in original_rows if (row.get("evidence", {}).get("gate") or {}).get("ticket")]
    baseline_keys = {(p["kind"], p["ticker"]) for p in baseline_plans}
    baseline_symbols = sorted({p["ticker"] for p in baseline_plans})
    baseline_budget = allocation.budget(baseline_plans, account, data.get("open_plans", []))
    _require(baseline_keys == {(r["setup_kind"], r["ticker"]) for r in data["cash_budget"]["admitted"]}, "baseline membership differs")
    _require(baseline_budget["committed_usd"] == data["cash_budget"]["committed_usd"], "baseline commitment differs")
    rows, research_plans = [], []
    for rank, original in enumerate(top if in_period else [], 1):
        evidence = original["evidence"]
        inputs = deepcopy(evidence["planning"]["inputs"])
        event = event_risk.classify(original["ticker"], data["run"]["session"], registry=data["rules"]["event_risk"]["registry"])
        old = original.get("plan")
        blockers = []
        candidate = baseline = None
        if isinstance(inputs, dict):
            inputs["account"] = account
            try:
                baseline = plan.anticipation_plan(**inputs)
                candidate = plan._anticipation_plan(**inputs, max_stop_pct=RESEARCH_STOP_PCT)
            except (ValueError, TypeError):
                blockers.append("invalid_inputs")
        else:
            blockers.append("invalid_inputs")
        levels = None
        if candidate is not None:
            _require(old is not None, "original plan missing for valid inputs")
            comparable = ("entry_ref", "trigger", "limit", "stop", "stop_pct", "shares", "position_usd", "risk_usd", "multipliers")
            _require(all(baseline[k] == old[k] for k in comparable), "baseline plan differs from archived inputs")
            _require(all(candidate[k] == baseline[k] for k in ("entry_ref", "trigger", "limit", "stop")), "research moved structural levels")
            levels = {"trigger": candidate["trigger"], "limit": candidate["limit"], "stop": candidate["stop"], "stop_pct": candidate["stop_pct"]}
        in_band = levels is not None and BASELINE_STOP_PCT < levels["stop_pct"] <= RESEARCH_STOP_PCT
        if not in_band: blockers.append("outside_band")
        if original.get("eligible") is not True: blockers.append("watchlist_ineligible")
        if data["breadth"]["regime"]["size_multiplier"] <= 0 or data["breadth"]["regime"]["verdict"] == "red": blockers.append("market_gate")
        if event["blocked"]: blockers.append("known_event")
        if candidate is not None and candidate["shares"] <= 0: blockers.append("no_whole_share")
        mechanical_fit = not blockers and candidate is not None and candidate["eligible"] and candidate["action"] in plan.ORDER_ACTIONS
        if mechanical_fit: research_plans.append(candidate)
        if original["ticker"] in baseline_budget["open_symbols"]: blockers.append("occupied_model_symbol")
        if original["ticker"] in baseline_symbols: blockers.append("baseline_symbol_reserved")
        research = {"mechanical_fit": bool(mechanical_fit), "allocation_fit": False,
                    "shares": candidate["shares"] if candidate else None,
                    "principal_usd": candidate["position_usd"] if candidate else None,
                    "risk_usd": candidate["risk_usd"] if candidate else None,
                    "risk_per_share": candidate["risk_per_share"] if candidate else None,
                    "effective_risk_budget_usd": candidate["sizing"]["budget_usd"] if candidate else None,
                    "multipliers": candidate["multipliers"] if candidate else None,
                    "blockers": blockers, "projection_sha256": None}
        rows.append({"rank": rank, "ticker": original["ticker"],
            "evidence": {"id": evidence["id"], "plan_sha256": evidence["planning"]["output_sha256"],
                         "source_sha256": evidence["source"]["sha256"], "inputs_sha256": provenance.digest(evidence["planning"]["inputs"])},
            "in_band": in_band, "baseline": {"admitted": ("anticipation", original["ticker"]) in baseline_keys,
                "eligible": old.get("eligible") if old else None, "action": old.get("action") if old else None,
                "reason": old.get("reason") if old else evidence["planning"].get("error"), "shares": old.get("shares") if old else None},
            "levels": levels, "research": research,
            "event": {"blocked": event["blocked"], "status": event["status"], "registry_sha256": event["registry_sha256"], "event_ids": [e["id"] for e in event["matches"]]},
            "quality": {"watchlist_eligible": original.get("eligible") is True, "source_session": data["run"]["session"], "review": "not_required_by_anticipation"}})
    combined = allocation.budget(baseline_plans + research_plans, account, data.get("open_plans", []))
    admitted = {(p["setup_kind"], p["ticker"]) for p in combined["admitted"]}
    _require(baseline_keys <= admitted, "research displaced a baseline ticket")
    for row in rows:
        row["research"]["allocation_fit"] = row["research"]["mechanical_fit"] and ("anticipation", row["ticker"]) in admitted and ("anticipation", row["ticker"]) not in baseline_keys
        cut = next((r for r in combined["cut"] if r["ticker"] == row["ticker"] and r.get("setup_kind") == "anticipation"), None)
        if cut and cut["kind"] in ("slot_cap", "equity", "duplicate") and cut["kind"] not in row["research"]["blockers"]:
            row["research"]["blockers"].append(cut["kind"])
        row["research"]["projection_sha256"] = _sha(_encode(_projection(row)))
    reservations = {"equity_usd": account.equity, "position_cap_usd": account.max_position_usd, "max_slots": account.max_open_positions,
        "open_model_principal_usd": baseline_budget["reserved_usd"], "open_model_slots": baseline_budget["open_positions"], "open_symbols": baseline_budget["open_symbols"],
        "baseline_principal_usd": baseline_budget["committed_usd"], "baseline_risk_usd": baseline_budget["at_risk_usd"], "baseline_slots": len(baseline_keys), "baseline_symbols": baseline_symbols,
        "available_principal_usd_before_research": plan._money(max(0, baseline_budget["available_usd"] - baseline_budget["committed_usd"])),
        "research_principal_usd": plan._money(combined["committed_usd"] - baseline_budget["committed_usd"]),
        "research_risk_usd": plan._money(combined["at_risk_usd"] - baseline_budget["at_risk_usd"]), "research_slots": len(admitted - baseline_keys),
        "slots_used": combined["slots_used"], "remaining_model_principal_usd": plan._money(max(0, combined["available_usd"] - combined["committed_usd"]))}
    common = {"schema_version": VERSION, "policy": deepcopy(POLICY), "publication": binding, "timing": timing,
              "status": status, "reason": reason, "counts": _counts(rows, len(top))}
    bundle = {**common, "reservations": reservations, "rows": rows, "limits": LIMITS}
    bundle_raw = _encode(bundle)
    _require(len(bundle_raw) <= MAX_BUNDLE_BYTES, "bundle exceeds bound")
    digest = _sha(bundle_raw)
    receipt = {**common, "bundle": {"path": BUNDLE_DIR + "/" + digest + ".json", "sha256": digest, "bytes": len(bundle_raw)}}
    receipt_raw = _encode(receipt)
    _require(len(receipt_raw) <= MAX_RECEIPT_BYTES, "receipt exceeds bound")
    validate_bundle(receipt_raw, bundle_raw)
    return {"receipt": receipt, "receipt_bytes": receipt_raw, "bundle": bundle, "bundle_bytes": bundle_raw}


def _validate_common(value):
    _require(type(value["schema_version"]) is int and value["schema_version"] == VERSION and _encode(value["policy"]) == _encode(POLICY), "unsupported research policy")
    binding = value["publication"]
    _require(_keys(binding, BINDING_KEYS), "publication binding fields differ")
    for key in ("data_sha256", "context_sha256", "reader_sha256"):
        _require(isinstance(binding[key], str) and HEX.fullmatch(binding[key]), "invalid binding digest")
    _require(type(binding["reader_projection_version"]) is int and binding["reader_projection_version"] == reader.VERSION, "unsupported reader binding")
    _require(isinstance(binding["rules_version"], str) and re.fullmatch(r"[a-f0-9]{12}", binding["rules_version"]), "invalid rules identity")
    _require(binding["run_id"] is None or isinstance(binding["run_id"], str) and 0 < len(binding["run_id"]) <= 128, "invalid run identity")
    _day(binding["measured_session"]); _day(binding["applicable_session"]); _instant(binding["published_at"])
    timing = value["timing"]
    _require(_keys(timing, {"generated_at", "entry_opens_at", "entry_cutoff_at", "classification"}), "timing fields differ")
    generated, opens, cutoff = (_instant(timing[k]) for k in ("generated_at", "entry_opens_at", "entry_cutoff_at"))
    _require(opens < cutoff and _instant(binding["published_at"]) <= generated + timedelta(seconds=MAX_FUTURE_SECONDS), "timing clocks differ")
    phase = "before_entry" if generated < opens else "during_entry" if generated < cutoff else "after_entry"
    _require(timing["classification"] == phase, "collection phase differs")
    in_period = START_SESSION <= binding["applicable_session"] <= END_SESSION
    _require(value["status"] == ("recorded" if in_period else "outside_period"), "registration status differs")
    _require(value["reason"] == (None if in_period else "The applicable session is outside the registered experiment period."), "registration reason differs")
    counts = value["counts"]
    _require(_keys(counts, {"top_count", "considered", "in_band", "mechanical_fit", "allocation_fit", "by_blocker"}), "count fields differ")
    _require(all(_integer(counts[k], MAX_ROWS) for k in counts if k != "by_blocker"), "invalid counts")
    _require(_keys(counts["by_blocker"], BLOCKERS) and all(_integer(n, MAX_ROWS) for n in counts["by_blocker"].values()), "invalid blocker counts")


def parse_receipt(raw):
    receipt = _decode(raw, MAX_RECEIPT_BYTES)
    _require(_keys(receipt, COMMON_KEYS | {"bundle"}), "receipt fields differ")
    _validate_common(receipt)
    ref = receipt["bundle"]
    _require(_keys(ref, {"path", "sha256", "bytes"}) and isinstance(ref["sha256"], str) and HEX.fullmatch(ref["sha256"]), "invalid bundle identity")
    _require(ref["path"] == BUNDLE_DIR + "/" + ref["sha256"] + ".json" and _integer(ref["bytes"], MAX_BUNDLE_BYTES) and ref["bytes"] > 0, "invalid bundle path or length")
    return receipt


def validate_bundle(receipt_raw, bundle_raw):
    """Strict bounded self-integrity; older publication binding is permissible."""
    receipt = parse_receipt(receipt_raw)
    _require(isinstance(bundle_raw, bytes) and len(bundle_raw) == receipt["bundle"]["bytes"] and _sha(bundle_raw) == receipt["bundle"]["sha256"], "bundle bytes differ")
    bundle = _decode(bundle_raw, MAX_BUNDLE_BYTES)
    _require(_keys(bundle, COMMON_KEYS | {"reservations", "rows", "limits"}), "bundle fields differ")
    _require(all(_encode(bundle[k]) == _encode(receipt[k]) for k in COMMON_KEYS), "receipt metadata differs")
    _require(bundle["limits"] == LIMITS, "coverage limits differ")
    rows = bundle["rows"]
    _require(isinstance(rows, list) and len(rows) <= MAX_ROWS and len({row.get("ticker") for row in rows if isinstance(row, dict)}) == len(rows), "invalid cohort rows")
    for rank, row in enumerate(rows, 1):
        _require(_keys(row, ROW_KEYS) and row["rank"] == rank and type(row["rank"]) is int, "row fields or rank differ")
        _require(isinstance(row["ticker"], str) and re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,14}", row["ticker"]), "invalid row ticker")
        _require(_keys(row["evidence"], {"id", "plan_sha256", "source_sha256", "inputs_sha256"}) and all(isinstance(x, str) and HEX.fullmatch(x) for x in row["evidence"].values()), "invalid evidence identity")
        baseline = row["baseline"]
        _require(_keys(baseline, {"admitted", "eligible", "action", "reason", "shares"}) and type(baseline["admitted"]) is bool and (baseline["eligible"] is None or type(baseline["eligible"]) is bool), "invalid baseline")
        _require(baseline["shares"] is None or _integer(baseline["shares"]), "invalid baseline shares")
        _require(baseline["reason"] is None or isinstance(baseline["reason"], str) and len(baseline["reason"]) <= 3000, "invalid baseline reason")
        _require(baseline["action"] is None or baseline["action"] in ("buy_at_open", "place_buy_stop", "refused", "no_order", "no_new_longs"), "invalid baseline action")
        research = row["research"]
        _require(_keys(research, RESEARCH_KEYS) and all(type(research[k]) is bool for k in ("mechanical_fit", "allocation_fit")), "invalid research projection")
        _require(isinstance(research["blockers"], list) and all(isinstance(b, str) and b in BLOCKERS for b in research["blockers"]) and len(set(research["blockers"])) == len(research["blockers"]), "invalid research blockers")
        _require(research["shares"] is None or _integer(research["shares"]), "invalid research shares")
        for key in ("principal_usd", "risk_usd", "risk_per_share", "effective_risk_budget_usd"):
            _require(research[key] is None or _number(research[key]), "invalid research amount")
        levels = row["levels"]
        if levels is not None:
            _require(_keys(levels, {"trigger", "limit", "stop", "stop_pct"}) and all(_number(n, True) for n in levels.values()), "invalid structural levels")
            _require(levels["stop"] < levels["trigger"] <= levels["limit"], "invalid entry geometry")
            _require(_keys(research["multipliers"], {"regime", "hazard", "stop_risk", "total"}) and all(_number(n) and n <= 1 for n in research["multipliers"].values()), "invalid risk multipliers")
            _require(all(research[k] is not None for k in ("shares", "principal_usd", "risk_usd", "risk_per_share", "effective_risk_budget_usd")), "missing sizing projection")
            limit, stop = _cents(levels["limit"]), _cents(levels["stop"])
            _cents(levels["trigger"])
            rps = limit - stop
            _require(_cents(research["risk_per_share"]) == rps, "risk per share differs")
            _require(_cents(research["principal_usd"]) == research["shares"] * limit and _cents(research["risk_usd"]) == research["shares"] * rps, "share amounts differ")
            _require(_cents(research["principal_usd"]) <= 50000 and _cents(research["risk_usd"]) <= _cents(research["effective_risk_budget_usd"]), "sizing exceeds account limits")
            multipliers = research["multipliers"]
            _require(multipliers["hazard"] == 1 and multipliers["total"] == multipliers["regime"] * multipliers["stop_risk"], "anticipation multipliers differ")
            budget = int((Decimal(str(multipliers["total"])) * 1000).quantize(Decimal(1), rounding=ROUND_HALF_UP))
            _require(_cents(research["effective_risk_budget_usd"]) == budget, "effective risk budget differs")
            _require(research["shares"] == min(budget // rps, 50000 // limit), "whole share sizing differs")
        else:
            _require(all(research[k] is None for k in ("shares", "principal_usd", "risk_usd", "risk_per_share", "effective_risk_budget_usd", "multipliers")) and "invalid_inputs" in research["blockers"], "unknown geometry gained sizing")
        _require(type(row["in_band"]) is bool and row["in_band"] == (levels is not None and BASELINE_STOP_PCT < levels["stop_pct"] <= RESEARCH_STOP_PCT), "band membership differs")
        _require(research["projection_sha256"] == _sha(_encode(_projection(row))), "research projection digest differs")
        event = row["event"]
        _require(_keys(event, {"blocked", "status", "registry_sha256", "event_ids"}) and type(event["blocked"]) is bool and event["status"] in ("known_event", "review_required", "not_in_registry"), "invalid event projection")
        _require(isinstance(event["registry_sha256"], str) and HEX.fullmatch(event["registry_sha256"]), "invalid event registry digest")
        _require(isinstance(event["event_ids"], list) and len(event["event_ids"]) <= 128 and all(isinstance(e, str) and 0 < len(e) <= 2000 for e in event["event_ids"]) and len(set(event["event_ids"])) == len(event["event_ids"]), "invalid event IDs")
        _require(event["blocked"] == bool(event["event_ids"]) == (event["status"] in ("known_event", "review_required")), "event state differs")
        _require(_keys(row["quality"], {"watchlist_eligible", "source_session", "review"}) and type(row["quality"]["watchlist_eligible"]) is bool and row["quality"]["source_session"] == bundle["publication"]["measured_session"] and row["quality"]["review"] == "not_required_by_anticipation", "invalid source quality")
        _require(not research["allocation_fit"] or research["mechanical_fit"] and not research["blockers"], "allocation contradicts blockers")
        _require(not research["mechanical_fit"] or row["in_band"] and research["shares"] > 0 and not event["blocked"] and row["quality"]["watchlist_eligible"], "mechanical fit contradicts evidence")
    _require(bundle["counts"] == _counts(rows, bundle["counts"]["top_count"]), "cohort counts differ")
    _require(len(rows) == (bundle["counts"]["top_count"] if bundle["status"] == "recorded" else 0), "cohort membership count differs")
    reserves = bundle["reservations"]
    _require(_keys(reserves, RESERVATION_KEYS), "reservation fields differ")
    for key, value in reserves.items():
        if key in ("open_symbols", "baseline_symbols"):
            _require(isinstance(value, list) and len(value) <= 64 and all(isinstance(t, str) and re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,14}", t) for t in value) and value == sorted(set(value)), "invalid reserved symbols")
        else:
            _require(_number(value), "invalid reservation amount")
    _require(reserves["research_slots"] == bundle["counts"]["allocation_fit"], "research allocation count differs")
    _require(reserves["equity_usd"] == 2000 and reserves["position_cap_usd"] == 500 and reserves["max_slots"] == 4, "reservation account differs")
    for key in ("open_model_slots", "baseline_slots", "research_slots", "slots_used"):
        _require(_integer(reserves[key], 64), "invalid reservation slots")
    _require(reserves["baseline_slots"] == len(reserves["baseline_symbols"]) and reserves["open_model_slots"] >= len(reserves["open_symbols"]), "reservation symbols differ")
    _require(not set(reserves["open_symbols"]) & set(reserves["baseline_symbols"]), "baseline repeats occupied symbol")
    fits = [r for r in rows if r["research"]["allocation_fit"]]
    _require(not ({r["ticker"] for r in fits} & set(reserves["open_symbols"] + reserves["baseline_symbols"])), "research repeats reserved symbol")
    _require(_cents(reserves["research_principal_usd"]) == sum(_cents(r["research"]["principal_usd"]) for r in fits) and _cents(reserves["research_risk_usd"]) == sum(_cents(r["research"]["risk_usd"]) for r in fits), "research totals differ")
    available = max(0, 200000 - _cents(reserves["open_model_principal_usd"]))
    baseline = _cents(reserves["baseline_principal_usd"])
    _cents(reserves["baseline_risk_usd"])
    _require(baseline <= available, "baseline exceeds model principal")
    _require(_cents(reserves["available_principal_usd_before_research"]) == available - baseline, "available principal differs")
    research = _cents(reserves["research_principal_usd"])
    _require(research <= available - baseline and _cents(reserves["remaining_model_principal_usd"]) == available - baseline - research, "remaining model principal differs")
    _require(reserves["slots_used"] == reserves["open_model_slots"] + reserves["baseline_slots"] + reserves["research_slots"], "total slots differ")
    _require(reserves["baseline_slots"] + reserves["research_slots"] <= max(0, 4 - reserves["open_model_slots"]), "new allocation exceeds slots")
    return bundle


def validate_for_publication(canonical_raw, receipt_raw, bundle_raw, *, objects=None, picks=None, allow_fixture=False):
    bundle = validate_bundle(receipt_raw, bundle_raw)
    rebuilt = build(canonical_raw, objects=objects, picks=picks, generated_at=bundle["timing"]["generated_at"], allow_fixture=allow_fixture, require_sources=objects is not None)
    _require(rebuilt["receipt_bytes"] == receipt_raw and rebuilt["bundle_bytes"] == bundle_raw, "comparison differs from actual publication replay")
    return bundle


def _safe_read(docs, name, maximum):
    path = Path(docs)
    _require(path.is_dir() and not path.is_symlink(), "docs root is not a real directory")
    for part in Path(name).parts:
        _require(part not in (".", "..") and not Path(name).is_absolute(), "unsafe artifact path")
        path = path / part
        _require(not path.is_symlink(), "artifact cannot follow symlinks")
    _require(path.is_file() and path.stat().st_size <= maximum, "artifact missing or oversized")
    return path.read_bytes()


def _atomic(path, raw):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name); handle.write(raw); handle.flush()
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def write_publication(canonical_raw, docs, *, objects, picks=None, allow_fixture=False, generated_at=None):
    """Keep bounded immutable cohorts; install the latest receipt last.

    No cohort is pruned. An exhausted/invalid archive leaves the prior receipt
    and every original record intact; the optional caller reports unavailability.
    """
    result = build(canonical_raw, objects=objects, picks=picks, allow_fixture=allow_fixture, generated_at=generated_at)
    docs = Path(docs)
    _require(docs.is_dir() and not docs.is_symlink(), "docs root is not a real directory")
    directory = docs / BUNDLE_DIR
    _require(not directory.is_symlink(), "archive cannot be a symlink")
    if directory.exists(): _require(directory.is_dir(), "archive must be a directory")
    latest_path = docs / RECEIPT_FILE
    _require(not latest_path.is_symlink(), "receipt cannot be a symlink")
    previous = None
    if latest_path.exists():
        previous_raw = _safe_read(docs, RECEIPT_FILE, MAX_RECEIPT_BYTES)
        previous = parse_receipt(previous_raw)
        previous_bundle = _safe_read(docs, previous["bundle"]["path"], MAX_BUNDLE_BYTES)
        validate_bundle(previous_raw, previous_bundle)
    index_path = docs / INDEX_FILE
    entries = []
    if index_path.exists() or index_path.is_symlink():
        index = _decode(_safe_read(docs, INDEX_FILE, MAX_INDEX_BYTES), MAX_INDEX_BYTES)
        _require(_keys(index, {"schema_version", "policy_id", "objects"}) and type(index["schema_version"]) is int and index["schema_version"] == VERSION and index["policy_id"] == POLICY_ID and isinstance(index["objects"], list), "invalid cohort index")
        entries = index["objects"]
    total = 0; seen = set(); publications = set()
    for entry in entries:
        _require(_keys(entry, {"sha256", "bytes", "publication_sha256", "applicable_session", "generated_at"}) and isinstance(entry["sha256"], str) and HEX.fullmatch(entry["sha256"]) and entry["sha256"] not in seen, "invalid retained cohort")
        seen.add(entry["sha256"])
        _require(_integer(entry["bytes"], MAX_BUNDLE_BYTES) and entry["bytes"] > 0 and isinstance(entry["publication_sha256"], str) and HEX.fullmatch(entry["publication_sha256"]), "invalid retained identity")
        _require(entry["publication_sha256"] not in publications, "publication has more than one retained first cohort")
        publications.add(entry["publication_sha256"])
        _day(entry["applicable_session"]); _instant(entry["generated_at"])
        raw = _safe_read(docs, BUNDLE_DIR + "/" + entry["sha256"] + ".json", MAX_BUNDLE_BYTES)
        _require(len(raw) == entry["bytes"] and _sha(raw) == entry["sha256"], "retained cohort bytes changed")
        retained = _decode(raw, MAX_BUNDLE_BYTES)
        receipt = {k: retained.get(k) for k in COMMON_KEYS}
        receipt["bundle"] = {"sha256": entry["sha256"], "bytes": entry["bytes"], "path": BUNDLE_DIR + "/" + entry["sha256"] + ".json"}
        validate_bundle(_encode(receipt), raw)
        _require(entry["publication_sha256"] == retained["publication"]["data_sha256"] and entry["applicable_session"] == retained["publication"]["applicable_session"] and entry["generated_at"] == retained["timing"]["generated_at"], "retained cohort index differs")
        total += len(raw)
    _require(len(entries) <= MAX_BUNDLES and total <= MAX_ARCHIVE_BYTES, "cohort archive capacity exceeded")
    if previous is not None:
        _require(previous["bundle"]["sha256"] in seen, "latest cohort missing from retained index")
    # Count every archived file, including an orphan left by a failed atomic
    # update. Unknown files are preserved and refused, never silently pruned.
    disk_total = 0; disk_count = 0
    if directory.exists():
        files = list(directory.iterdir())
        _require(len(files) <= MAX_BUNDLES + 1, "archive file count exceeds bound")
        for path in files:
            _require(path.is_file() and not path.is_symlink(), "unsafe archive entry")
            if path.name == "index.json": continue
            _require(re.fullmatch(r"[a-f0-9]{64}\.json", path.name) and path.stat().st_size <= MAX_BUNDLE_BYTES, "unknown archive entry")
            disk_total += path.stat().st_size
            disk_count += 1
        _require(disk_total <= MAX_ARCHIVE_BYTES, "archive disk bytes exceed bound")
    if previous is not None and previous["publication"] == result["receipt"]["publication"]:
        validate_for_publication(canonical_raw, previous_raw, previous_bundle, objects=objects, picks=picks, allow_fixture=allow_fixture)
        return previous
    # Revisiting any earlier publication retains its first cohort and clock.
    old = next((e for e in entries if e["publication_sha256"] == result["receipt"]["publication"]["data_sha256"]), None)
    if old:
        old_raw = _safe_read(docs, BUNDLE_DIR + "/" + old["sha256"] + ".json", MAX_BUNDLE_BYTES)
        retained = _decode(old_raw, MAX_BUNDLE_BYTES)
        old_receipt = {k: retained[k] for k in COMMON_KEYS}
        old_receipt["bundle"] = {"sha256": old["sha256"], "bytes": old["bytes"], "path": BUNDLE_DIR + "/" + old["sha256"] + ".json"}
        old_receipt_raw = _encode(old_receipt)
        validate_for_publication(canonical_raw, old_receipt_raw, old_raw, objects=objects, picks=picks, allow_fixture=allow_fixture)
        _atomic(latest_path, old_receipt_raw)
        return old_receipt
    ref = result["receipt"]["bundle"]
    target = docs / ref["path"]
    _require(disk_count + int(not target.exists()) <= MAX_BUNDLES and disk_total + (0 if target.exists() else ref["bytes"]) <= MAX_ARCHIVE_BYTES, "archive disk capacity exceeded")
    if ref["sha256"] not in seen:
        entries.append({"sha256": ref["sha256"], "bytes": ref["bytes"], "publication_sha256": result["receipt"]["publication"]["data_sha256"], "applicable_session": result["receipt"]["publication"]["applicable_session"], "generated_at": result["receipt"]["timing"]["generated_at"]})
        total += ref["bytes"]
    _require(len(entries) <= MAX_BUNDLES and total <= MAX_ARCHIVE_BYTES, "cohort archive capacity exceeded")
    index_raw = _encode({"schema_version": VERSION, "policy_id": POLICY_ID, "objects": entries})
    _require(len(index_raw) <= MAX_INDEX_BYTES, "cohort index exceeds bound")
    directory.mkdir(exist_ok=True)
    if target.exists() or target.is_symlink():
        _require(_safe_read(docs, ref["path"], MAX_BUNDLE_BYTES) == result["bundle_bytes"], "immutable cohort already differs")
    else:
        _atomic(target, result["bundle_bytes"])
    _atomic(index_path, index_raw)
    _atomic(latest_path, result["receipt_bytes"])
    return result["receipt"]
