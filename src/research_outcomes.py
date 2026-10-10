"""Frozen research cohorts, observed from retained daily bars. No network/orders.

Transport validation imports only the standard library. Full derivation lazily
uses the existing provenance, calendar and conditional replay authorities.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import time

from src import stop_research as cohort

VERSION = 1
POLICY_ID = "anticipation_stop_width_follow_through_v1"
RECEIPT_FILE = "research-outcomes.json"
BUNDLE_DIR = "research-outcomes"
INDEX_FILE = BUNDLE_DIR + "/index.json"
MAX_RECEIPT_BYTES = 16 * 1024
MAX_BUNDLE_BYTES = 2 * 1024 * 1024
MAX_INDEX_BYTES = 64 * 1024
MAX_COHORTS = 128
MAX_ROWS = MAX_COHORTS * cohort.MAX_ROWS
MAX_SNAPSHOTS = 128
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_ORIGINAL_BYTES = 128 * 1024 * 1024
MAX_PROCESS_SECONDS = 60
HORIZON_SESSIONS = 5
MAX_EVENTS = 20
MAX_FUTURE_SECONDS = 5
PUBLIC_PRICE_DECIMALS = 4
HEX = re.compile(r"[a-f0-9]{64}\Z")
STATUSES = ("pending", "missing", "uncertain", "not_filled", "open", "resolved",
            "excluded", "origin_unavailable", "basis_conflict", "unsupported", "unreadable")
BASIS_KEYS = {"provider", "feed", "adjustment", "timeframe"}
PLAN_RULES = {"sell_half_pct": 8.0, "abnormal_day_pct": 10.0, "gap_exit_pct": 20.0,
              "trail_cents": .25, "sell_half_day": 3, "no_progress_day": 3,
              "trail_from_day": 3, "final_exit_day": 5, "entry_day": 1,
              "precision.cents": 2, "precision.pct_decimals": 2}
REPLAY_RULES = {"version": 1, "fill": "open_inside_zone", "same_bar": "stop_first",
                "whole_shares": "ceil_half", "r": "original_stop_weighted_complete_sales_v1",
                "plan": PLAN_RULES, "record": {"open_plan_sessions": 5, "known_fill": "open_inside_zone"},
                "calendar": {"version": 1, "exchange": "XNYS", "library": "exchange_calendars",
                             "library_version": "4.13.2", "timezone": "America/New_York",
                             "completion_buffer_minutes": 15}}
POLICY = {"version": VERSION, "id": POLICY_ID, "cohort_policy_id": cohort.POLICY_ID,
          "horizon_sessions": HORIZON_SESSIONS, "population": "frozen_allocation_fit_only",
          "primary": "first_actual_before_entry_per_applicable_session",
          "observation_price_decimals": PUBLIC_PRICE_DECIMALS,
          "basis": "same_provider_feed_adjustment_daily_and_fresh_matching_anchor",
          "replay_rules": REPLAY_RULES, "costs": "unspecified_actual_fees_and_slippage_excluded",
          "aggregation": "counts_only_no_portfolio_performance"}
LIMITS = ["conditional_daily_bar_model_not_actual_execution", "no_orders_or_personal_results",
          "no_new_provider_or_model_calls", "first_30_minutes_and_intraday_order_unknown",
          "known_open_fill_uses_stop_first_daily_bar_convention", "whole_share_model_exits",
          "actual_fees_and_slippage_unspecified", "no_cross_cohort_portfolio_reservations",
          "retained_observation_coverage_may_be_missing", "revisions_do_not_rewrite_prior_snapshots"]
COMMON_KEYS = {"schema_version", "policy", "publication", "generated_at", "cohort_set_sha256", "counts"}
MODEL_KEYS = {"status", "reason", "day", "sessions", "entry", "original_shares", "sold_shares",
              "remaining_shares", "current_stop", "events", "r", "uncertainty", "expected_sessions", "missing_sessions"}
OBSERVATION_KEYS = {"publication", "basis", "anchor", "bars", "bars_sha256", "carried", "revision_of", "changed_dates"}
BAR_KEYS = {"date", "o", "h", "l", "c", "v", "from_session"}
EVENTS = {"not_filled", "uncertain", "stopped_at_open", "gap_exit", "stopped", "sell_half",
          "stop_raised", "abnormal_day", "no_progress", "stop_raised_to_entry_low", "stop_trailed", "day5_exit"}


def _require(value, message):
    if not value:
        raise ValueError("research outcomes: " + message)


def _encode(value):
    return cohort._encode(value)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _digest(value):
    return _sha(_encode(value))


def _keys(value, names):
    return isinstance(value, dict) and set(value) == set(names)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _integer(value, maximum=1000000):
    return type(value) is int and 0 <= value <= maximum


def _text(value, maximum=400):
    return isinstance(value, str) and 0 < len(value) <= maximum


def _day(value):
    return cohort._day(value)


def _instant(value):
    return cohort._instant(value)


def _binding(value):
    _require(_keys(value, cohort.BINDING_KEYS), "binding fields differ")
    for k in ("data_sha256", "reader_sha256", "context_sha256"):
        _require(isinstance(value[k], str) and HEX.fullmatch(value[k]), "binding digest invalid")
    _require(type(value["reader_projection_version"]) is int and value["reader_projection_version"] == 1,
             "reader version unsupported")
    _require(isinstance(value["rules_version"], str) and re.fullmatch(r"[a-f0-9]{12}", value["rules_version"]), "rules identity invalid")
    _require(value["run_id"] is None or _text(value["run_id"], 128), "run identity invalid")
    _day(value["measured_session"]); _day(value["applicable_session"]); _instant(value["published_at"])


def _basis(value):
    _require(_keys(value, BASIS_KEYS) and all(_text(v, 64) for v in value.values()), "basis invalid")
    _require(value["timeframe"] == "1Day", "timeframe unsupported")


def _cohort_raw(raw):
    parsed = cohort._decode(raw, cohort.MAX_BUNDLE_BYTES)
    ref = {"sha256": _sha(raw), "bytes": len(raw), "path": f"stop-research/{_sha(raw)}.json"}
    receipt = {**{k: parsed.get(k) for k in cohort.COMMON_KEYS}, "bundle": ref}
    cohort.validate_bundle(_encode(receipt), raw)
    return parsed


def _supported(data):
    rules = data.get("rules", {})
    return all(all(rules.get(group, {}).get(k) == v for k, v in expected.items())
               for group, expected in (("plan", PLAN_RULES), ("record", REPLAY_RULES["record"]),
                                       ("calendar", REPLAY_RULES["calendar"])))


def _basis_of(data):
    basis = data.get("run", {}).get("input_basis", {})
    return {k: basis.get(k) for k in sorted(BASIS_KEYS)}


def _anchor(frame, session, source_sha):
    _require(frame.get("type") == "frame" and "Close" in frame.get("columns", []), "original frame invalid")
    index = frame["dates"].index(session)
    close = frame["values"][frame["columns"].index("Close")][index]
    _require(_number(close) and close > 0, "original close invalid")
    return {"date": session, "close": close, "source_sha256": source_sha}


def _origin(source, data, objects):
    from src import provenance
    basis = _basis_of(data)
    try:
        _basis(basis)
    except ValueError:
        return None
    anchors = {}
    for row in source["rows"]:
        if not row["research"]["allocation_fit"]:
            continue
        sha = row["evidence"]["source_sha256"]
        anchors[row["evidence"]["id"]] = _anchor(provenance._object(objects, sha), source["publication"]["measured_session"], sha)
    return {"basis": basis, "replay_rules": deepcopy(REPLAY_RULES) if _supported(data) else None, "anchors": anchors}


def _empty_model(row, expected, status, reason):
    return {"status": status, "reason": reason, "day": 0, "sessions": 0, "entry": None,
            "original_shares": row["research"]["shares"], "sold_shares": None, "remaining_shares": None,
            "current_stop": None, "events": [], "r": None, "uncertainty": None,
            "expected_sessions": expected, "missing_sessions": expected.copy()}


def _bar(value):
    _require(isinstance(value, dict), "observation bar is not an object")
    bar = {k: value.get(k) for k in BAR_KEYS}
    _day(bar["date"]); _day(bar["from_session"])
    _require(all(_number(bar[k]) and bar[k] > 0 for k in ("o", "h", "l", "c")), "invalid OHLC")
    _require(bar["v"] is None or _number(bar["v"]) and bar["v"] >= 0, "invalid volume")
    _require(bar["l"] <= min(bar["o"], bar["c"]) <= max(bar["o"], bar["c"]) <= bar["h"], "inconsistent OHLC")
    return bar


def _observe(data, binding, row, origin, horizon, prior):
    """Never attach today's basis to older carried history rows."""
    if prior is not None and (prior["publication"]["measured_session"] > binding["measured_session"] or
                              _instant(prior["publication"]["published_at"]) > _instant(binding["published_at"])):
        prior = None  # A historical revisit cannot borrow observations from its future.
    basis = _basis_of(data)
    if basis != origin["basis"]:
        return None, "basis_conflict", "Observation provider, feed, adjustment or timeframe differs from the frozen origin."
    hist = data.get("observations", {}).get("symbols", {}).get(row["ticker"], {}).get("history", [])
    _require(isinstance(hist, list) and len(hist) <= 20, "retained history exceeds bound")
    anchor = origin["anchors"][row["evidence"]["id"]]
    raw_anchor = next((b for b in hist if b.get("date") == anchor["date"]), None)
    candidates = [b for b in hist if b.get("date") in horizon and b.get("date") <= binding["measured_session"]]
    if raw_anchor is not None and raw_anchor.get("from_session") == binding["measured_session"] and raw_anchor.get("c") != round(float(anchor["close"]), PUBLIC_PRICE_DECIMALS):
        return None, "basis_conflict", "The freshly retained original-date close differs; adjustment or correction needs review."
    if not candidates:
        if prior is not None:
            kept = deepcopy(prior); kept["carried"] = True
            return kept, None, None
        # Before entry an empty fresh clip still captures the original source basis.
        if raw_anchor is not None and raw_anchor.get("from_session") == binding["measured_session"]:
            return {"publication": deepcopy(binding), "basis": basis, "anchor": deepcopy(anchor),
                    "bars": [], "bars_sha256": _digest([]), "carried": False,
                    "revision_of": None, "changed_dates": []}, None, None
        return None, None, None
    if raw_anchor is None or raw_anchor.get("from_session") != binding["measured_session"] or any(b.get("from_session") != binding["measured_session"] for b in candidates):
        # A previously bound clip remains old evidence, but unfamiliar/mixed bars
        # cannot acquire a new basis just by appearing in another publication.
        if prior is not None and all(any(_same_ohlcv(b, old) for old in prior["bars"]) for b in candidates):
            kept = deepcopy(prior); kept["carried"] = True
            return kept, None, None
        return None, "basis_conflict", "Carried or mixed history lacks a fresh matching anchor and source basis."
    try:
        bars = [_bar(b) for b in candidates]
    except (ValueError, TypeError):
        return None, "unreadable", "Retained daily OHLC values are inconsistent or incomplete."
    _require(len({b["date"] for b in bars}) == len(bars), "duplicate daily observation")
    bars.sort(key=lambda b: b["date"])
    changed = []
    if prior:
        old = {b["date"]: b for b in prior["bars"]}
        changed = [b["date"] for b in bars if b["date"] in old and not _same_ohlcv(b, old[b["date"]])]
        omitted = set(old) - {b["date"] for b in bars}
        if omitted and not changed:
            original = {"publication": {"measured_session": anchor["date"], "applicable_session": horizon[0]}}
            prior_model = _model(original, row, prior, [d for d in horizon if d <= binding["measured_session"]])
            if prior_model["status"] in {"resolved", "not_filled", "uncertain"}:
                kept = deepcopy(prior); kept["carried"] = True
                return kept, None, None
    return {"publication": deepcopy(binding), "basis": basis, "anchor": deepcopy(anchor), "bars": bars,
            "bars_sha256": _digest(bars), "carried": False,
            "revision_of": prior["bars_sha256"] if changed else None, "changed_dates": changed}, None, None


def _same_ohlcv(a, b):
    return all(a.get(k) == b.get(k) for k in ("date", "o", "h", "l", "c", "v"))


def _model(source, row, observation, expected):
    from src import record
    result = _empty_model(row, expected, "pending", f"Awaiting {source['publication']['applicable_session']} entry-session observations.")
    bars = observation["bars"] if observation else []
    result["missing_sessions"] = [d for d in expected if d not in {b["date"] for b in bars}]
    if not bars:
        if expected:
            result.update(status="missing", reason="The completed observation publication lacks an expected daily session.")
        return result
    levels = row["levels"]
    pick = {"ticker": row["ticker"], "date": source["publication"]["measured_session"], "kind": "anticipation",
            "entry_ref": levels["trigger"], "trigger": levels["trigger"], "limit": levels["limit"],
            "stop": levels["stop"], "shares": row["research"]["shares"]}
    # Clip at the first hole. An earlier conclusive model does not depend on
    # missing bars after its exit; an unfinished one remains missing.
    from src import sessions
    horizon = [str(d) for d in sessions.next_sessions(date.fromisoformat(pick["date"]), HORIZON_SESSIONS)]
    by_date = {b["date"]: b for b in bars}
    prefix = []
    for day in horizon:
        if day not in by_date: break
        prefix.append(by_date[day])
    walk = record.replay(pick, prefix)
    result.update(day=walk.get("day", 0), sessions=len(prefix), uncertainty=walk.get("uncertainty"), events=deepcopy(walk.get("events", [])))
    status = walk["status"]
    if status == record.UNCERTAIN:
        result.update(status="uncertain", reason=record.UNCERTAIN_WORDS[result["uncertainty"]] + "; no model fill or R is established.")
    elif status == record.NOT_FILLED:
        result.update(status="not_filled", reason="The entry-session daily bar does not establish a model fill under the frozen entry rule.")
    elif status == record.UNREADABLE:
        result.update(status="unreadable", reason="Daily bars cannot be replayed under the supported session and OHLC rules.")
    elif prefix:
        result.update(entry=walk["entry_ref"], sold_shares=walk["sold"], remaining_shares=walk["remaining"], current_stop=walk["current_stop"])
        result["r"] = record.r_multiple(walk, levels["stop"])
        if status in record.SETTLED and result["r"] is not None:
            result.update(status="resolved", reason="All hypothetical whole shares exited in the conditional daily-bar model; actual costs are unspecified.")
        elif result["missing_sessions"]:
            result.update(status="missing", reason="An unfinished conditional model lacks an expected completed daily session.")
        else:
            result.update(status="open", reason="The conditional daily-bar model has hypothetical shares remaining; this is not an actual holding.")
    else:
        result.update(status="missing", reason="The entry-session bar is missing; later daily bars cannot establish an entry.")
    return result


def _counts(entries):
    rows = [r for entry in entries for r in entry["rows"]]
    return {"cohorts": len(entries), "primary_cohorts": sum(c["primary"] for c in entries), "rows": len(rows),
            "eligible": sum(r["model"]["status"] != "excluded" for r in rows),
            "by_status": {s: sum(r["model"]["status"] == s for r in rows) for s in STATUSES}}


def build(canonical_raw, *, cohorts, objects, previous=None, publications=None, generated_at=None, allow_fixture=False):
    """Deterministic for supplied bytes and clock; no provider/model access."""
    from src import morning, provenance, sessions
    started = time.monotonic()
    def deadline():
        _require(time.monotonic() - started <= MAX_PROCESS_SECONDS, "processing deadline exceeded")
    data, binding = morning._publication(canonical_raw, allow_fixture=allow_fixture)
    generated = _instant(datetime.now(timezone.utc).isoformat() if generated_at is None else generated_at.isoformat() if isinstance(generated_at, datetime) else generated_at)
    _require(_instant(binding["published_at"]) <= generated + timedelta(seconds=MAX_FUTURE_SECONDS), "publication is in future")
    _require(_instant(binding["published_at"]) >= sessions.completion_at(date.fromisoformat(binding["measured_session"])), "observation session is not completed at publication")
    _require(provenance.verify(data, objects=objects, require_sources=True)["status"] == "PASS", "current source integrity is not verified")
    _require(isinstance(cohorts, (list, tuple)) and len(cohorts) <= MAX_COHORTS and sum(len(b) for b in cohorts) <= cohort.MAX_ARCHIVE_BYTES, "source cohort capacity exceeded")
    old = validate_bundle(*previous) if previous is not None else None
    old_by = {e["source"]["sha256"]: e for e in old["cohorts"]} if old else {}
    parsed = [(_sha(raw), raw, _cohort_raw(raw)) for raw in cohorts]
    _require(len({sha for sha, _, _ in parsed}) == len(parsed), "duplicate cohort")
    _require(set(old_by) <= {sha for sha, _, _ in parsed}, "previously retained cohort is missing")
    parsed.sort(key=lambda x: (x[2]["publication"]["applicable_session"], _instant(x[2]["timing"]["generated_at"]), x[0]))
    consumed = len(canonical_raw); entries = []; first = set(); sequence = {}
    for sha, raw, source in parsed:
        deadline()
        _require(_instant(source["timing"]["generated_at"]) <= generated + timedelta(seconds=MAX_FUTURE_SECONDS), "cohort is in future")
        before = source["timing"]["classification"] == "before_entry"
        applicable = source["publication"]["applicable_session"]
        primary = before and applicable not in first
        if primary: first.add(applicable)
        sequence[applicable] = sequence.get(applicable, 0) + 1
        prior = old_by.get(sha)
        origin = deepcopy(prior["origin"]) if prior else None
        original_raw = canonical_raw if source["publication"]["data_sha256"] == binding["data_sha256"] else None
        if origin is None and original_raw is None and publications is not None:
            _require(callable(publications), "original publications require a bounded local resolver")
            original_raw = publications(source["publication"]["data_sha256"])
            if original_raw is not None:
                consumed += len(original_raw)
                _require(consumed <= MAX_ORIGINAL_BYTES, "original publication byte budget exceeded")
        if original_raw is not None:
            original_data, original_binding = (data, binding) if original_raw is canonical_raw else morning._publication(original_raw, allow_fixture=allow_fixture)
            _require(original_binding == source["publication"], "original publication binding differs")
            source_receipt = _encode({**{k: source[k] for k in cohort.COMMON_KEYS}, "bundle": {
                "sha256": sha, "bytes": len(raw), "path": f"stop-research/{sha}.json"}})
            cohort.validate_for_publication(original_raw, source_receipt, raw, objects=objects, allow_fixture=allow_fixture)
            # Exact original row identity and source objects bind the compact seed.
            originals = {r["evidence"]["id"]: r for r in original_data.get("watchlist", {}).get("top", [])}
            for row in source["rows"]:
                real = originals.get(row["evidence"]["id"])
                _require(real is not None and real["ticker"] == row["ticker"] and real["evidence"]["source"]["sha256"] == row["evidence"]["source_sha256"] and real["evidence"]["planning"]["output_sha256"] == row["evidence"]["plan_sha256"], "frozen row differs from original")
            origin = _origin(source, original_data, objects)
            del original_data, original_raw
        if origin:
            for anchor in origin["anchors"].values():
                _require(_anchor(provenance._object(objects, anchor["source_sha256"]), anchor["date"], anchor["source_sha256"]) == anchor, "retained origin anchor changed")
        horizon = [str(d) for d in sessions.next_sessions(date.fromisoformat(source["publication"]["measured_session"]), HORIZON_SESSIONS)]
        expected = [d for d in horizon if d <= binding["measured_session"]]
        previous_rows = {r["evidence_id"]: r for r in prior["rows"]} if prior else {}
        rows = []
        for row in source["rows"]:
            obs = None
            if not row["research"]["allocation_fit"]:
                model = _empty_model(row, expected, "excluded", "Not an allocated research idea in the frozen cohort: " + ", ".join(row["research"]["blockers"]))
            elif origin is None:
                model = _empty_model(row, expected, "origin_unavailable", "The exact original publication basis and replay-rule seed are unavailable.")
            elif origin["replay_rules"] != REPLAY_RULES or not _supported(data):
                model = _empty_model(row, expected, "unsupported", "The original or observation publication uses unsupported replay or calendar rules.")
            else:
                prev = previous_rows.get(row["evidence"]["id"], {}).get("observation")
                obs, problem, reason = _observe(data, binding, row, origin, horizon, prev)
                model = _empty_model(row, expected, problem, reason) if problem else _model(source, row, obs, expected)
            rows.append({"rank": row["rank"], "ticker": row["ticker"], "evidence_id": row["evidence"]["id"], "observation": obs, "model": model})
        entries.append({"source": {"sha256": sha, "bytes": len(raw), "raw": raw.decode("utf-8")}, "primary": primary,
                        "revision": sequence[applicable], "origin": origin, "rows": rows})
    deadline()
    common = {"schema_version": VERSION, "policy": deepcopy(POLICY), "publication": binding, "generated_at": generated.isoformat(),
              "cohort_set_sha256": _digest([e["source"]["sha256"] for e in entries]), "counts": _counts(entries)}
    bundle = {**common, "cohorts": entries, "limits": LIMITS.copy()}
    raw = _encode(bundle)
    _require(len(raw) <= MAX_BUNDLE_BYTES, "bundle byte bound exceeded")
    receipt = {**common, "bundle": {"path": f"{BUNDLE_DIR}/{_sha(raw)}.json", "sha256": _sha(raw), "bytes": len(raw)}}
    receipt_raw = _encode(receipt)
    validate_bundle(receipt_raw, raw)
    return {"receipt": receipt, "receipt_bytes": receipt_raw, "bundle": bundle, "bundle_bytes": raw}


def _validate_common(value):
    _require(type(value["schema_version"]) is int and value["schema_version"] == VERSION and value["policy"] == POLICY, "policy unsupported")
    _binding(value["publication"])
    generated = _instant(value["generated_at"])
    _require(_instant(value["publication"]["published_at"]) <= generated + timedelta(seconds=MAX_FUTURE_SECONDS), "publication clock exceeds generation")
    _require(isinstance(value["cohort_set_sha256"], str) and HEX.fullmatch(value["cohort_set_sha256"]), "cohort set identity invalid")
    counts = value["counts"]
    _require(_keys(counts, {"cohorts", "primary_cohorts", "rows", "eligible", "by_status"}), "count fields differ")
    _require(all(_integer(counts[k], MAX_ROWS) for k in counts if k != "by_status") and counts["cohorts"] <= MAX_COHORTS, "count bounds invalid")
    _require(_keys(counts["by_status"], STATUSES) and all(_integer(n, MAX_ROWS) for n in counts["by_status"].values()), "status count invalid")
    _require(sum(counts["by_status"].values()) == counts["rows"] and counts["eligible"] == counts["rows"] - counts["by_status"]["excluded"], "counts do not reconcile")


def parse_receipt(raw):
    receipt = cohort._decode(raw, MAX_RECEIPT_BYTES)
    _require(_keys(receipt, COMMON_KEYS | {"bundle"}), "receipt fields differ")
    _validate_common(receipt)
    ref = receipt["bundle"]
    _require(_keys(ref, {"path", "sha256", "bytes"}) and isinstance(ref["sha256"], str) and HEX.fullmatch(ref["sha256"]), "bundle descriptor invalid")
    _require(ref["path"] == f"{BUNDLE_DIR}/{ref['sha256']}.json" and _integer(ref["bytes"], MAX_BUNDLE_BYTES) and ref["bytes"] > 0, "bundle path/size invalid")
    return receipt


def validate_bundle(receipt_raw, bundle_raw):
    """Bounded stdlib-only self-integrity; never claim independent source truth."""
    receipt = parse_receipt(receipt_raw)
    _require(isinstance(bundle_raw, bytes) and len(bundle_raw) == receipt["bundle"]["bytes"] and _sha(bundle_raw) == receipt["bundle"]["sha256"], "bundle bytes differ")
    bundle = cohort._decode(bundle_raw, MAX_BUNDLE_BYTES)
    _require(_keys(bundle, COMMON_KEYS | {"cohorts", "limits"}), "bundle fields differ")
    _require(all(bundle[k] == receipt[k] for k in COMMON_KEYS) and bundle["limits"] == LIMITS, "common fields or limits differ")
    entries = bundle["cohorts"]
    _require(isinstance(entries, list) and len(entries) <= MAX_COHORTS, "cohort list exceeds bound")
    seen = set(); first = set(); sequence = {}; ordering = []
    for entry in entries:
        _require(_keys(entry, {"source", "primary", "revision", "origin", "rows"}), "cohort fields differ")
        source_ref = entry["source"]
        _require(_keys(source_ref, {"sha256", "bytes", "raw"}) and isinstance(source_ref["raw"], str), "frozen cohort source invalid")
        raw = source_ref["raw"].encode("utf-8")
        _require(source_ref["sha256"] == _sha(raw) and type(source_ref["bytes"]) is int and source_ref["bytes"] == len(raw) and source_ref["sha256"] not in seen, "frozen cohort bytes differ")
        seen.add(source_ref["sha256"])
        source = _cohort_raw(raw)
        generated = _instant(source["timing"]["generated_at"])
        _require(generated <= _instant(bundle["generated_at"]) + timedelta(seconds=MAX_FUTURE_SECONDS), "future cohort")
        applicable = source["publication"]["applicable_session"]
        ordering.append((applicable, generated, source_ref["sha256"]))
        primary = source["timing"]["classification"] == "before_entry" and applicable not in first
        if primary: first.add(applicable)
        sequence[applicable] = sequence.get(applicable, 0) + 1
        _require(type(entry["primary"]) is bool and entry["primary"] == primary and type(entry["revision"]) is int and entry["revision"] == sequence[applicable], "primary/revision differs")
        origin = entry["origin"]
        if origin is not None:
            _require(_keys(origin, {"basis", "replay_rules", "anchors"}), "origin fields differ")
            _basis(origin["basis"])
            _require(origin["replay_rules"] is None or origin["replay_rules"] == REPLAY_RULES, "origin replay rules unsupported")
            ids = {r["evidence"]["id"] for r in source["rows"] if r["research"]["allocation_fit"]}
            _require(_keys(origin["anchors"], ids), "origin anchor identities differ")
            for original in source["rows"]:
                if original["evidence"]["id"] not in ids: continue
                anchor = origin["anchors"][original["evidence"]["id"]]
                _require(_keys(anchor, {"date", "close", "source_sha256"}) and anchor["date"] == source["publication"]["measured_session"] and anchor["source_sha256"] == original["evidence"]["source_sha256"] and _number(anchor["close"]) and anchor["close"] > 0, "origin anchor invalid")
        _require(isinstance(entry["rows"], list) and len(entry["rows"]) == len(source["rows"]), "original row population differs")
        for row, original in zip(entry["rows"], source["rows"]):
            _validate_row(row, original, source, origin, bundle)
    _require(ordering == sorted(ordering), "cohort order differs")
    _require(bundle["cohort_set_sha256"] == _digest([e["source"]["sha256"] for e in entries]) and bundle["counts"] == _counts(entries), "cohort identity/counts differ")
    return bundle


def _validate_row(row, original, source, origin, bundle):
    _require(_keys(row, {"rank", "ticker", "evidence_id", "observation", "model"}), "row fields differ")
    _require(type(row["rank"]) is int and row["rank"] == original["rank"] and row["ticker"] == original["ticker"] and row["evidence_id"] == original["evidence"]["id"], "frozen row identity differs")
    obs = row["observation"]
    if obs is not None:
        _require(origin is not None and _keys(obs, OBSERVATION_KEYS), "observation fields differ")
        _binding(obs["publication"]); _basis(obs["basis"])
        _require(obs["basis"] == origin["basis"] and obs["anchor"] == origin["anchors"][row["evidence_id"]], "observation origin differs")
        _require(_instant(obs["publication"]["published_at"]) <= _instant(bundle["generated_at"]) + timedelta(seconds=MAX_FUTURE_SECONDS), "future observation publication")
        _require(obs["publication"]["measured_session"] <= bundle["publication"]["measured_session"] and
                 _instant(obs["publication"]["published_at"]) <= _instant(bundle["publication"]["published_at"]), "observation is later than containing publication")
        _require(type(obs["carried"]) is bool and (obs["carried"] or obs["publication"] == bundle["publication"]), "fresh observation binding differs")
        _require(isinstance(obs["bars"], list) and len(obs["bars"]) <= HORIZON_SESSIONS, "observation clip exceeds bound")
        dates = []
        for bar in obs["bars"]:
            _require(_keys(bar, BAR_KEYS) and _bar(bar) == bar, "bar shape differs")
            _require(bar["from_session"] == obs["publication"]["measured_session"] and source["publication"]["measured_session"] < bar["date"] <= obs["publication"]["measured_session"], "bar attribution differs")
            dates.append(bar["date"])
        _require(dates == sorted(set(dates)) and obs["bars_sha256"] == _digest(obs["bars"]), "bar order/digest differs")
        _require(obs["revision_of"] is None or isinstance(obs["revision_of"], str) and HEX.fullmatch(obs["revision_of"]), "revision identity invalid")
        _require(isinstance(obs["changed_dates"], list) and obs["changed_dates"] == sorted(set(obs["changed_dates"])) and all(d in dates for d in obs["changed_dates"]) and bool(obs["revision_of"]) == bool(obs["changed_dates"]), "revision dates differ")
    model = row["model"]
    _require(_keys(model, MODEL_KEYS) and model["status"] in STATUSES and _text(model["reason"], 600), "model fields invalid")
    _require(_integer(model["day"], HORIZON_SESSIONS) and _integer(model["sessions"], HORIZON_SESSIONS) and model["day"] <= model["sessions"], "model session counts invalid")
    _require(type(model["original_shares"]) is type(original["research"]["shares"]) and model["original_shares"] == original["research"]["shares"], "frozen research quantity differs")
    for key in ("expected_sessions", "missing_sessions"):
        values = model[key]
        _require(isinstance(values, list) and len(values) <= HORIZON_SESSIONS and values == sorted(set(values)), "expected session list invalid")
        for d in values:
            _day(d)
            _require(source["publication"]["measured_session"] < d <= bundle["publication"]["measured_session"], "expected session range invalid")
    _require(set(model["missing_sessions"]) <= set(model["expected_sessions"]), "missing session outside expectation")
    attached_dates = {bar["date"] for bar in obs["bars"]} if obs else set()
    _require(model["missing_sessions"] == [d for d in model["expected_sessions"] if d not in attached_dates], "missing sessions differ from observed coverage")
    _require(model["sessions"] <= len(attached_dates), "model sessions exceed observed bars")
    for key in ("entry", "current_stop", "r"):
        _require(model[key] is None or _number(model[key]) and (key == "r" or model[key] > 0), "model number invalid")
    for key in ("sold_shares", "remaining_shares"):
        _require(model[key] is None or _integer(model[key]), "model whole shares invalid")
    _require(model["uncertainty"] is None or model["uncertainty"] in {"trigger_timing", "stop_sequence", "open_above_limit"}, "uncertainty invalid")
    _require((model["status"] == "uncertain") == (model["uncertainty"] is not None), "uncertainty state differs")
    _require(isinstance(model["events"], list) and len(model["events"]) <= MAX_EVENTS, "event bound exceeded")
    sales = 0
    for event in model["events"]:
        _require(isinstance(event, dict) and set(event) in ({"day", "date", "event", "price"}, {"day", "date", "event", "price", "shares", "remaining"}), "event fields differ")
        _require(_integer(event["day"], HORIZON_SESSIONS) and event["day"] > 0 and event["event"] in EVENTS and (event["price"] is None or _number(event["price"]) and event["price"] > 0), "event invalid")
        _day(event["date"])
        _require(obs is not None and event["date"] in {b["date"] for b in obs["bars"]}, "event lacks bar evidence")
        if "shares" in event:
            _require(_integer(event["shares"]) and event["shares"] > 0 and _integer(event["remaining"]), "sale quantity invalid")
            sales += event["shares"]
            _require(event["remaining"] == model["original_shares"] - sales, "sale quantities do not reconcile")
    known = model["entry"] is not None
    if known:
        _require(model["sold_shares"] == sales and _integer(model["remaining_shares"]) and sales + model["remaining_shares"] == model["original_shares"] and model["status"] in {"open", "resolved", "missing"}, "model quantities do not reconcile")
        _require(original["levels"]["trigger"] <= model["entry"] <= original["levels"]["limit"], "model entry is outside frozen zone")
    else:
        _require(model["sold_shares"] is None and model["remaining_shares"] is None and model["current_stop"] is None and sales == 0, "unknown fill manufactured quantities")
    _require((model["status"] == "resolved") == (model["r"] is not None) and (model["status"] != "resolved" or known and model["remaining_shares"] == 0), "R requires resolved whole-share model")
    if model["r"] is not None:
        expected_r = round(math.fsum(e["shares"] * (e["price"] - model["entry"]) for e in model["events"] if "shares" in e) / (model["original_shares"] * (model["entry"] - original["levels"]["stop"])), 2)
        _require(model["r"] == expected_r, "whole-share R differs")
    _require((model["status"] == "excluded") == (not original["research"]["allocation_fit"]), "frozen eligibility differs")
    if model["status"] in {"pending", "missing", "uncertain", "not_filled", "open", "resolved"}:
        _require(origin is not None and origin["replay_rules"] == REPLAY_RULES, "model lacks supported origin")
    if model["status"] == "pending":
        _require(not model["expected_sessions"] and model["day"] == 0 and not model["events"] and not known, "pending implies nonexistent observation")


def validate_for_publication(canonical_raw, receipt_raw, bundle_raw, *, cohorts, objects, previous=None, publications=None, allow_fixture=False):
    parsed = validate_bundle(receipt_raw, bundle_raw)
    rebuilt = build(canonical_raw, cohorts=cohorts, objects=objects, previous=previous, publications=publications,
                    generated_at=parsed["generated_at"], allow_fixture=allow_fixture)
    _require(rebuilt["receipt_bytes"] == receipt_raw and rebuilt["bundle_bytes"] == bundle_raw, "journal differs from exact source replay")
    return parsed


def _receipt_of(raw):
    value = cohort._decode(raw, MAX_BUNDLE_BYTES)
    return _encode({**{k: value.get(k) for k in COMMON_KEYS}, "bundle": {"path": f"{BUNDLE_DIR}/{_sha(raw)}.json", "sha256": _sha(raw), "bytes": len(raw)}})


def _source_cohorts(docs):
    path = docs / cohort.INDEX_FILE
    if not path.exists() and not path.is_symlink():
        return []
    index = cohort._decode(cohort._safe_read(docs, cohort.INDEX_FILE, cohort.MAX_INDEX_BYTES), cohort.MAX_INDEX_BYTES)
    _require(_keys(index, {"schema_version", "policy_id", "objects"}) and type(index["schema_version"]) is int and index["schema_version"] == 1 and index["policy_id"] == cohort.POLICY_ID and isinstance(index["objects"], list) and len(index["objects"]) <= MAX_COHORTS, "source cohort index invalid")
    result = []; size = 0; seen = set(); publications = set()
    for entry in index["objects"]:
        _require(_keys(entry, {"sha256", "bytes", "publication_sha256", "applicable_session", "generated_at"}) and isinstance(entry["sha256"], str) and HEX.fullmatch(entry["sha256"]) and entry["sha256"] not in seen, "source index entry invalid")
        raw = cohort._safe_read(docs, f"stop-research/{entry['sha256']}.json", cohort.MAX_BUNDLE_BYTES)
        source = _cohort_raw(raw); size += len(raw)
        _require(_sha(raw) == entry["sha256"] and len(raw) == entry["bytes"] and source["publication"]["data_sha256"] == entry["publication_sha256"] and source["publication"]["applicable_session"] == entry["applicable_session"] and source["timing"]["generated_at"] == entry["generated_at"] and entry["publication_sha256"] not in publications, "source index differs from immutable bytes")
        _require(size <= cohort.MAX_ARCHIVE_BYTES, "source archive bytes exceed bound")
        seen.add(entry["sha256"]); publications.add(entry["publication_sha256"]); result.append(raw)
    return result


def write_publication(canonical_raw, docs, *, objects, picks=None, generated_at=None, allow_fixture=False):
    """Append immutable snapshots and install receipt last. Never prune."""
    started = time.monotonic()
    def deadline():
        _require(time.monotonic() - started <= MAX_PROCESS_SECONDS, "archive processing deadline exceeded")
    docs = Path(docs)
    _require(docs.is_dir() and not docs.is_symlink(), "docs root invalid")
    directory = docs / BUNDLE_DIR
    _require(not directory.is_symlink() and (not directory.exists() or directory.is_dir()), "archive directory unsafe")
    latest = docs / RECEIPT_FILE
    _require(not latest.is_symlink(), "receipt unsafe")
    previous = None
    if latest.exists():
        old_receipt = cohort._safe_read(docs, RECEIPT_FILE, MAX_RECEIPT_BYTES)
        ref = parse_receipt(old_receipt)["bundle"]
        old_bundle = cohort._safe_read(docs, ref["path"], MAX_BUNDLE_BYTES)
        validate_bundle(old_receipt, old_bundle); previous = (old_receipt, old_bundle)
    entries = []
    if (docs / INDEX_FILE).exists() or (docs / INDEX_FILE).is_symlink():
        index = cohort._decode(cohort._safe_read(docs, INDEX_FILE, MAX_INDEX_BYTES), MAX_INDEX_BYTES)
        _require(_keys(index, {"schema_version", "policy_id", "objects"}) and type(index["schema_version"]) is int and index["schema_version"] == VERSION and index["policy_id"] == POLICY_ID and isinstance(index["objects"], list) and len(index["objects"]) <= MAX_SNAPSHOTS, "snapshot index invalid")
        entries = index["objects"]
    seen = set(); input_sets = set(); total = 0
    for entry in entries:
        deadline()
        _require(_keys(entry, {"sha256", "bytes", "publication_sha256", "cohort_set_sha256", "generated_at"}) and isinstance(entry["sha256"], str) and HEX.fullmatch(entry["sha256"]) and entry["sha256"] not in seen, "snapshot index entry invalid")
        raw = cohort._safe_read(docs, f"{BUNDLE_DIR}/{entry['sha256']}.json", MAX_BUNDLE_BYTES)
        snap = validate_bundle(_receipt_of(raw), raw)
        key = (snap["publication"]["data_sha256"], snap["cohort_set_sha256"])
        _require(_sha(raw) == entry["sha256"] and len(raw) == entry["bytes"] and key == (entry["publication_sha256"], entry["cohort_set_sha256"]) and snap["generated_at"] == entry["generated_at"] and key not in input_sets, "snapshot index differs")
        seen.add(entry["sha256"]); input_sets.add(key); total += len(raw)
        _require(total <= MAX_ARCHIVE_BYTES, "archive byte capacity exceeded")
    if previous:
        _require(parse_receipt(previous[0])["bundle"]["sha256"] in seen, "latest snapshot missing from index")
    files = list(directory.iterdir()) if directory.exists() else []
    _require(len(files) <= MAX_SNAPSHOTS + 1, "archive file capacity exceeded")
    disk_total = 0; disk_count = 0
    for path in files:
        _require(path.is_file() and not path.is_symlink(), "archive entry unsafe")
        if path.name == "index.json": continue
        _require(re.fullmatch(r"[a-f0-9]{64}\.json", path.name) and 0 < path.stat().st_size <= MAX_BUNDLE_BYTES, "archive entry unknown")
        disk_total += path.stat().st_size; disk_count += 1
    _require(disk_total <= MAX_ARCHIVE_BYTES, "disk byte capacity exceeded")
    sources = _source_cohorts(docs)
    deadline()
    ordered = sorted(sources, key=lambda raw: (_cohort_raw(raw)["publication"]["applicable_session"], _instant(_cohort_raw(raw)["timing"]["generated_at"]), _sha(raw)))
    input_key = (_sha(canonical_raw), _digest([_sha(raw) for raw in ordered]))
    old = next((e for e in entries if (e["publication_sha256"], e["cohort_set_sha256"]) == input_key), None)
    if old:
        raw = cohort._safe_read(docs, f"{BUNDLE_DIR}/{old['sha256']}.json", MAX_BUNDLE_BYTES)
        receipt_raw = _receipt_of(raw)
        deadline()
        cohort._atomic(latest, receipt_raw)
        return parse_receipt(receipt_raw)
    result = build(canonical_raw, cohorts=sources, objects=objects, previous=previous, generated_at=generated_at, allow_fixture=allow_fixture)
    deadline()
    ref = result["receipt"]["bundle"]; target = docs / ref["path"]
    _require(len(entries) < MAX_SNAPSHOTS and total + ref["bytes"] <= MAX_ARCHIVE_BYTES and disk_count + int(not target.exists()) <= MAX_SNAPSHOTS and disk_total + (0 if target.exists() else ref["bytes"]) <= MAX_ARCHIVE_BYTES, "snapshot capacity exhausted")
    entries.append({"sha256": ref["sha256"], "bytes": ref["bytes"], "publication_sha256": input_key[0], "cohort_set_sha256": input_key[1], "generated_at": result["receipt"]["generated_at"]})
    index_raw = _encode({"schema_version": VERSION, "policy_id": POLICY_ID, "objects": entries})
    _require(len(index_raw) <= MAX_INDEX_BYTES, "index byte bound exceeded")
    deadline()
    directory.mkdir(exist_ok=True)
    if target.exists() or target.is_symlink():
        _require(cohort._safe_read(docs, ref["path"], MAX_BUNDLE_BYTES) == result["bundle_bytes"], "immutable snapshot differs")
    else:
        cohort._atomic(target, result["bundle_bytes"])
    deadline()
    cohort._atomic(docs / INDEX_FILE, index_raw)
    deadline()
    cohort._atomic(latest, result["receipt_bytes"])
    return result["receipt"]
