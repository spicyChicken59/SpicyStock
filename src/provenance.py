"""Versioned decision receipts and an offline, read-only verifier.

Digests detect contradictory evidence, not a malicious author's re-signing.
Source inputs are retained once, outside the page payload. No network, model
call, historical repair, or alternative strategy implementation lives here.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import gzip
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile

import numpy as np
import pandas as pd

from src import discovery, grader, plan, quality, scans, watchlist, sessions, inputs

VERSION = 1
OBJECT_DIR = "evidence"
MAX_OBJECT_BYTES = 256 * 1024
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
RULES = {"provenance.version": VERSION, "provenance.canonicalization": "typed-json-f64hex-v1",
         "provenance.grade_bands": [list(band) for band in grader.GRADE_BANDS],
         "provenance.quality_gate_letters": list(quality.GRADE_GATE_LETTERS), "provenance.quality_gate_cap": quality.GATE_CAP}
COLUMNS = ("Open", "High", "Low", "Close", "Volume")
FACTS = ("ticker", "scan", "flags", "close", "prev_close", "open", "high", "low", "gain_pct",
         "volume", "prev_volume", "volume_vs_prior", "dollar_volume", "dollar_move", "extension_pct")
RUN_FACTS = ("session", "expected_session", "type", "run_id", "feed", "model", "universe", "input_basis", "coverage", "calendar", "timing")
ACCOUNT_FIELDS = ("equity", "risk_pct", "max_position_pct", "max_open_positions")
HEX = re.compile(r"[0-9a-f]{64}\Z")


def _typed(value):
    # Type tags make floats lossless and distinguish None/False/0/0.0.
    if value is None:
        return ["null"]
    if isinstance(value, (bool, np.bool_)):
        return ["bool", bool(value)]
    if isinstance(value, (int, np.integer)):
        return ["int", str(value)]
    if isinstance(value, (float, np.floating)):
        if not math.isfinite(value):
            raise ValueError("nonfinite evidence number")
        return ["float", float(value).hex()]
    if isinstance(value, str):
        return ["str", value]
    if isinstance(value, (list, tuple)):
        return ["list", [_typed(v) for v in value]]
    if isinstance(value, dict) and all(isinstance(k, str) for k in value):
        return ["dict", [[k, _typed(value[k])] for k in sorted(value)]]
    raise ValueError(f"unsupported evidence type {type(value).__name__}")


def digest(value):
    return hashlib.sha256(json.dumps(_typed(value), ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _finite(values):
    return [float(v) if np.isfinite(v) else None for v in values]


def source_object(df):
    """Preserve consumed row order and float64 values; never use series_of()."""
    dates = [pd.Timestamp(v).date().isoformat() for v in df.index]
    if dates != sorted(set(dates)):
        raise ValueError("source dates are not strictly increasing session labels")
    return {"version": VERSION, "type": "frame", "dates": dates, "columns": list(COLUMNS),
            "values": [_finite(pd.to_numeric(df[c], errors="coerce").to_numpy(dtype=float, na_value=np.nan)) for c in COLUMNS]}


def frame_of(obj):
    if obj.get("type") != "frame" or obj.get("version") != VERSION or obj.get("columns") != list(COLUMNS):
        raise ValueError("unsupported source frame")
    return pd.DataFrame({c: np.array(v, dtype=float) for c, v in zip(COLUMNS, obj["values"], strict=True)},
                        index=pd.DatetimeIndex(obj["dates"]))


def source_ref(df, obj):
    # These are the scanner's and checklist's OWN normalization functions.
    sb, qb = scans._bars(df, -1), quality._arrays(df, -1)
    if sb is None or qb is None:
        raise ValueError("source frame cannot be normalized by its decision readers")
    return {"sha256": digest(obj), "rows": len(df), "evaluated_session": obj["dates"][-1],
            "previous_session": obj["dates"][-2],
            "scan_sha256": digest({"dates": obj["dates"], "columns": list(COLUMNS),
                                    "values": [_finite(sb._values[c]) for c in COLUMNS]}),
            "quality_sha256": digest({"dates": obj["dates"], "columns": list(COLUMNS),
                                       "values": [_finite(getattr(qb, c)) for c in ("o", "h", "l", "c", "v")]})}


def facts(row):
    return {k: row.get(k) for k in FACTS}


def mechanical(row):
    return {k: row.get(k) for k in ("quality", "grade_mechanical", "score", "vetoes", "reclass")}


def capture(row, df):
    obj = source_object(df)
    row["_evidence"] = {"source": source_ref(df, obj), "facts_sha256": digest(facts(row)),
                        "discovery_sha256": digest(row["discovery"]), "quality_sha256": digest(mechanical(row))}
    row["_objects"] = {digest(obj): obj}


def prepare_reader(row, metrics, chart_path, system):
    """Freeze precisely the prepared inputs; attempted/result are separate."""
    if "_evidence" not in row:
        return  # standalone unit callers can exercise the existing grader
    system_obj = {"version": VERSION, "type": "system", "text": system}
    system_id = digest(system_obj)
    row["_objects"][system_id] = system_obj
    image_id = None
    if chart_path and Path(chart_path).exists():
        raw = Path(chart_path).read_bytes()
        image_id = hashlib.sha256(raw).hexdigest()
        row["_objects"][image_id] = raw
    row["_evidence"]["reader_input"] = {"metrics_sha256": digest(metrics), "system_object": system_id,
        "system_sha256": hashlib.sha256(system.encode()).hexdigest(), "chart_sha256": image_id,
        "request_text_sha256": hashlib.sha256(json.dumps({"system": system, "user": grader.user_text(metrics)}, sort_keys=True).encode()).hexdigest()}


def seal_reader(row):
    if "_evidence" in row:
        row["_evidence"]["reader_sha256"] = digest(row.get("claude"))
        row["_evidence"]["reader_source"] = (row.get("claude") or {}).get("source", grader.SOURCE_NOT_GRADED)
        row["_evidence"]["final_grade"] = row["grade"]


def seal_plan(row, inputs, regime, session, error=None):
    if "_evidence" in row:
        row["_evidence"]["planning"] = {"inputs": deepcopy(inputs), "regime_sha256": digest(regime),
            "session": str(session), "output_sha256": digest(row.get("plan")), "error": error}


def context(data):
    return {"run": {k: data["run"].get(k) for k in RUN_FACTS}, "rules": data["rules"],
            "breadth": data["breadth"], "account": {k: data["account"].get(k) for k in ACCOUNT_FIELDS},
            "cash_budget": data["cash_budget"],
            "candidates": [["burst", r["ticker"]] for r in data["bursts"]]
                          + [["anticipation", r["ticker"]] for r in data.get("watchlist", {}).get("top", [])]}


def plain_plan(row):
    p = row.get("plan")
    return {k: v for k, v in p.items() if k != "evidence_ref"} if isinstance(p, dict) else p


def gate(data, row):
    regime = data["breadth"]["regime"]["verdict"]
    rules = data["rules"]["pipeline"]
    allowed = [] if regime == "red" else rules["yellow_grades"] if regime == "yellow" else rules["trade_grades"]
    p = plain_plan(row)
    cut = next((c for c in data["cash_budget"].get("cut", []) if c["ticker"] == row["ticker"]), None)
    reason = ("regime_gate" if regime == "red" or (regime == "yellow" and row["grade"] not in allowed)
              else "quality_grade" if row["grade"] not in allowed else "quality_veto" if row["vetoes"]
              else "plan_error" if p is None else cut["kind"] if cut
              else "plan_withheld" if not p.get("eligible") else "no_order" if p.get("action") not in plan.ORDER_ACTIONS
              else None)
    error = (row.get("evidence") or row.get("_evidence") or {}).get("planning", {}).get("error")
    return {"regime": regime, "final_grade": row["grade"], "allowed_grades": list(allowed),
            "ticket": reason is None, "reason": reason, "detail": cut.get("reason") if cut else (p or {}).get("reason") or error}


def reference(e):
    return {"version": VERSION, "id": e["id"], "context_sha256": e["context_sha256"],
            "plan_sha256": e["planning"]["output_sha256"], "pick_sha256": e["planning"]["pick_sha256"]}


def _same(actual, expected, reason):
    if digest(actual) != digest(expected):
        raise ValueError(reason)


def finish(data, bursts):
    """Join already-sealed stages. Never re-seal changed upstream evidence."""
    from src.pipeline import pick_of
    ctx = digest(context(data))
    data["run"]["evidence"] = {"version": VERSION, "context_sha256": ctx}
    objects = {}
    for row in bursts:
        e = deepcopy(row["_evidence"])
        _same(digest(facts(row)), e["facts_sha256"], "candidate facts changed after scan")
        _same(digest(row["discovery"]), e["discovery_sha256"], "discovery changed after scan")
        _same(digest(mechanical(row)), e["quality_sha256"], "mechanical quality changed after scan")
        _same(digest(row.get("claude")), e["reader_sha256"], "reader result changed after grading")
        _same(row["grade"], e["final_grade"], "final grade changed after grading")
        _same(digest(plain_plan(row)), e["planning"]["output_sha256"], "plan changed after construction")
        e.update(version=VERSION, kind="burst", ticker=row["ticker"], session=data["run"]["session"],
                 rules_version=data["app"]["rules_version"], context_sha256=ctx, gate=gate(data, row))
        p = plain_plan(row)
        pick = pick_of(p, "burst", row["grade"], row["score"]) if p is not None else None
        e["planning"]["pick_sha256"] = digest(pick)
        e["id"] = digest(e)
        row["evidence"] = e
        if p is not None:
            row["plan"]["evidence_ref"] = reference(e)
        objects.update(row["_objects"])
    return objects


def watch_facts(row):
    return {k: v for k, v in row.items() if not k.startswith("_") and k not in ("plan", "series", "evidence", "name")}


def capture_watch(row, df):
    obj = source_object(df)
    view = watchlist._read(df, -1)
    row["_evidence"] = {"source": {"sha256": digest(obj), "rows": len(df),
        "evaluated_session": obj["dates"][-1], "previous_session": obj["dates"][-2],
        "watch_sha256": digest({"dates": obj["dates"], "columns": list(COLUMNS),
                                 "values": [_finite(view._values[c]) for c in COLUMNS]})},
        "measurements_sha256": digest(watch_facts(row)), "mechanical": "not_applicable",
        "reader": "not_graded", "reason": "anticipation watchlist: measured, not reaction-graded"}
    row["_objects"] = {digest(obj): obj}


def watch_gate(data, row):
    p = plain_plan(row)
    regime = data["breadth"]["regime"]["verdict"]
    reason = ("regime_gate" if regime == "red" else "plan_error" if p is None
              else "plan_withheld" if not p.get("eligible") else "no_order" if p.get("action") not in plan.ORDER_ACTIONS else None)
    return {"regime": regime, "final_grade": "watch", "allowed_grades": None,
            "ticket": reason is None, "reason": reason, "detail": (p or {}).get("reason")}


def finish_watch(data, rows):
    from src.pipeline import pick_of
    objects = {}
    for row in rows:
        e = deepcopy(row["_evidence"])
        _same(digest(watch_facts(row)), e["measurements_sha256"], "anticipation measurements changed")
        _same(digest(plain_plan(row)), e["planning"]["output_sha256"], "anticipation plan changed")
        e.update(version=VERSION, kind="anticipation", ticker=row["ticker"], session=data["run"]["session"],
                 rules_version=data["app"]["rules_version"], context_sha256=data["run"]["evidence"]["context_sha256"],
                 gate=watch_gate(data, row))
        p = plain_plan(row)
        e["planning"]["pick_sha256"] = digest(pick_of(p, "anticipation", "watch", row.get("ti65")) if p else None)
        e["id"] = digest(e)
        row["evidence"] = e
        if p:
            p["evidence_ref"] = reference(e)
            row["plan"] = p
        objects.update(row["_objects"])
    return objects


def _check_watch(data, row, e, objects, compatible=True):
    from src.pipeline import pick_of
    _same(digest(watch_facts(row)), e["measurements_sha256"], "anticipation measurement digest mismatch")
    _same([e["mechanical"], e["reader"]], ["not_applicable", "not_graded"], "anticipation claims reaction grading")
    _same(watch_gate(data, row), e["gate"], "anticipation regime gate mismatch")
    p, planning = plain_plan(row), e["planning"]
    _same(planning["regime_sha256"], digest(data["breadth"]["regime"]), "anticipation regime mismatch")
    _same(planning["session"], data["run"]["session"], "anticipation session mismatch")
    _same(digest(p), planning["output_sha256"], "anticipation plan digest mismatch")
    if p:
        args = deepcopy(planning["inputs"])
        _same([args["ticker"], args["close"], args["box_high"], args["box_low"], args["account"], args["size_multiplier"]],
              [row["ticker"], row["close"], row["box"]["high"], row["box"]["low"],
               {k: data["account"][k] for k in ACCOUNT_FIELDS}, float(data["breadth"]["regime"]["size_multiplier"])],
              "anticipation plan inputs mismatch")
        if compatible:
            args["account"] = plan.Account(**args["account"])
            replay = plan.anticipation_plan(**args)
            replay["exit_schedule"] = plan.dated_schedule(replay, date.fromisoformat(planning["session"]))
            _same(p, replay, "anticipation plan rules mismatch")
        _same(row["plan"].get("evidence_ref"), reference(e), "anticipation plan reference mismatch")
        _same(p["exit_schedule"][0]["date"], data["run"]["calendar"]["applicable_session"], "anticipation calendar mismatch")
    _same(digest(pick_of(p, "anticipation", "watch", row.get("ti65")) if p else None), planning["pick_sha256"], "anticipation pick projection mismatch")
    if objects is not None and compatible:
        obj = _object(objects, e["source"]["sha256"])
        df = frame_of(obj)
        expected = {"ticker": row["ticker"], **watchlist.measure(df)}
        expected["quiet_days"], expected["range_pct"] = expected.get("narrow_range_days"), expected.get("range_pct_today")
        if isinstance(expected.get("box"), dict):
            expected["box"]["sessions"] = expected["box"]["length"]
        _same(watch_facts(row), expected, "anticipation measurements differ from source")
        capture_watch(expected, df)
        _same(expected["_evidence"]["source"], e["source"], "anticipation source digest mismatch")
        _same([obj["dates"][-1], obj["dates"][-2]], [data["run"]["session"], data["run"]["calendar"]["previous_session"]], "anticipation source session mismatch")
        if p:
            _same([float(x) for x in df["Low"].iloc[-plan.STOP_LOOKBACK_SESSIONS:]], planning["inputs"]["lows_last3"], "anticipation stop inputs differ from source")


def _check_mechanical(row):
    q = row["quality"]
    checks = [quality.Check(c["key"], c["letter"], c["label"], c["values"], c["threshold"],
                            c["passed"], c["a_plus"], c["note"], c["partial"]) for c in q["checks"]]
    for obj, c in zip(checks, q["checks"], strict=True):
        _same(obj.to_dict(), c, "quality check representations disagree")
    score, passes, plus = quality.score_of(checks)
    gates = all(c.passed for c in checks if c.letter in quality.GRADE_GATE_LETTERS)
    grade = quality.grade_of(score, plus, bool(q["vetoes"]) or q["unreadable"] is not None, gates)
    _same([score, passes, plus, grade], [q["score"], q["passes"], q["a_plus_count"], q["grade"]], "mechanical score/grade disagreement")
    _same([grade, score, q["vetoes"], q["reclass"]],
          [row["grade_mechanical"], row["score"], row["vetoes"], row["reclass"]], "mechanical result differs from candidate")


def _check_reader(row, e, compatible=True):
    cl = row.get("claude")
    _same(digest(cl), e["reader_sha256"], "reader result digest mismatch")
    _same(e["reader_source"], (cl or {}).get("source", grader.SOURCE_NOT_GRADED), "reader source mismatch")
    if not compatible:
        _same(row["grade"], e["final_grade"], "final grade digest mismatch")
        return
    grade = row["grade_mechanical"]
    if cl and cl["source"] == grader.SOURCE_CLAUDE:
        returned = grader.grade_for(cl["score"])
        _same(returned, cl["returned_grade"], "reader score/returned grade disagreement")
        grade = grader.final_grade(grade, returned)
        _same([grade, grade == row["grade_mechanical"]], [cl["grade"], cl["agree"]], "reader adjustment disagrees")
        if not cl.get("model"):
            raise ValueError("model judgement lacks model identity")
    elif cl:
        if cl["source"] not in (grader.SOURCE_FALLBACK, grader.SOURCE_NOT_GRADED):
            raise ValueError("unknown reader source")
        if any(cl.get(k) is not None for k in ("grade", "score", "reason", "returned_grade")):
            raise ValueError("fallback claims a reader judgement")
    _same([row["grade"], e["final_grade"]], [grade, grade], "final grade violates down-only reader adjustment")
    if cl:
        _same(cl["discovery_version"], row["discovery"]["version"], "reader discovery version mismatch")
        if cl.get("request_text_sha256"):
            _same(cl["request_text_sha256"], e["reader_input"]["request_text_sha256"], "reader request hash mismatch")
            _same(cl["input"], {k: e["reader_input"][k] for k in ("metrics_sha256", "system_sha256", "chart_sha256")}, "reader consumed inputs differ from prepared inputs")
            if not cl["attempts"] or cl["attempts"][-1]["outcome"] != ("model" if cl["source"] == grader.SOURCE_CLAUDE else "rejected"):
                raise ValueError("reader attempt outcome disagrees with source")


def _check_plan(data, row, e, compatible=True):
    from src.pipeline import pick_of
    p, planning = plain_plan(row), e["planning"]
    _same(digest(p), planning["output_sha256"], "plan/ticket digest mismatch")
    _same(planning["regime_sha256"], digest(data["breadth"]["regime"]), "plan regime differs from run regime")
    _same(planning["session"], data["run"]["session"], "plan signal session mismatch")
    decision = gate(data, row)
    _same(decision, e["gate"], "regime gate decision mismatch")
    _same(decision["ticket"], row["ticker"] in data["trades"], "ticket membership contradicts regime/quality/plan gate")
    if p is not None:
        _same(row["plan"].get("evidence_ref"), reference(e), "plan evidence reference mismatch")
        _same(p["ticker"], row["ticker"], "plan ticker mismatch")
        _same(p["kind"], e["kind"], "plan kind mismatch")
        _same(p["exit_schedule"][0]["date"], data["run"]["calendar"]["applicable_session"], "plan calendar applicability mismatch")
        _same(p["exit_schedule"][0]["date"], data["run"]["timing"]["applicable_session"], "plan timing applicability mismatch")
        args = deepcopy(planning["inputs"])
        expected_inputs = {"ticker": row["ticker"], "close": row["close"], "low": row["low"], "high": row["high"],
            "open_": row["open"], "prev_close": row["prev_close"], "gain_pct": row["gain_pct"] or 0.0,
            "account": {k: data["account"][k] for k in ACCOUNT_FIELDS},
            "size_multiplier": float(data["breadth"]["regime"]["size_multiplier"]),
            "scan": "dollar" if row["scan"] == "dollar" else "4pct", "extension_pct": row.get("extension_pct")}
        _same(args, expected_inputs, "plan inputs differ from source candidate/account/regime")
        if compatible:
            args["account"] = plan.Account(**args["account"])
            replay = plan.burst_plan(**args)
            replay["exit_schedule"] = plan.dated_schedule(replay, date.fromisoformat(planning["session"]))
            _same(replay, p, "plan differs from production plan rules")
    pick = pick_of(p, "burst", row["grade"], row["score"]) if p is not None else None
    _same(digest(pick), planning["pick_sha256"], "plan/pick projection mismatch")


def _object(objects, key, binary=False):
    if not isinstance(key, str) or not HEX.fullmatch(key):
        raise ValueError("invalid evidence object identity")
    if isinstance(objects, dict):
        obj = objects[key]
    else:
        path = Path(objects) / (key + (".png" if binary else ".json.gz"))
        raw = path.read_bytes()
        if len(raw) > MAX_OBJECT_BYTES:
            raise ValueError("evidence object exceeds bound")
        if not binary:
            raw = gzip.decompress(raw)
            if len(raw) > MAX_OBJECT_BYTES:
                raise ValueError("expanded evidence object exceeds bound")
        obj = raw if binary else json.loads(raw)
    actual = hashlib.sha256(obj).hexdigest() if binary else digest(obj)
    _same(actual, key, "source object digest mismatch")
    return obj


def _check_source(data, row, e, objects):
    from src.pipeline import base_block, extension_pct, _num, _gain
    obj = _object(objects, e["source"]["sha256"])
    df = frame_of(obj)
    _same(source_ref(df, obj), e["source"], "normalized source-bar digest mismatch")
    _same([obj["dates"][-1], obj["dates"][-2]],
          [data["run"]["session"], data["run"]["calendar"]["previous_session"]], "source evaluated/previous session mismatch")
    found = scans.scan_all(df)
    burst, dollar = found.get("burst"), found.get("dollar")
    route = "both" if burst and dollar else "burst" if burst else "dollar" if dollar else None
    _same(route, row["scan"], "source discovery route mismatch")
    last, prev = df.iloc[-1], df.iloc[-2]
    expected = {**facts(row), "scan": route, "close": _num(last["Close"]), "prev_close": _num(prev["Close"]),
        "open": _num(last["Open"]), "high": _num(last["High"]), "low": _num(last["Low"]),
        "gain_pct": (burst or {}).get("gain_pct", _gain(last, prev)), "volume": _num(last["Volume"]),
        "volume_vs_prior": (burst or dollar)["volume_vs_prior"], "prev_volume": (burst or dollar)["prev_volume"],
        "dollar_volume": (burst or {}).get("dollar_volume", _num(float(last["Close"]) * float(last["Volume"]))),
        "dollar_move": (dollar or {}).get("move"), "extension_pct": extension_pct(df)}
    _same(expected, facts(row), "candidate facts differ from source bars")
    _same(discovery.contract({**expected, **(burst or {}), **(dollar or {})}), row["discovery"], "discovery differs from source scan")
    assessment = quality.assess(df)
    _same({**assessment.to_dict(), "base": base_block(assessment.base, df)}, row["quality"], "quality differs from source checklist")
    ri = e.get("reader_input")
    if ri:
        extra = {k: row[k] for k in ("scan", "discovery", "flags", "gain_pct", "volume_vs_prior", "dollar_volume")}
        metrics = quality.metrics_for_model(assessment, row["ticker"], row["close"], extra)
        _same(digest(metrics), ri["metrics_sha256"], "reader input measurements mismatch")
        system = _object(objects, ri["system_object"])["text"]
        _same(hashlib.sha256(system.encode()).hexdigest(), ri["system_sha256"], "reader system digest mismatch")
        request = hashlib.sha256(json.dumps({"system": system, "user": grader.user_text(metrics)}, sort_keys=True).encode()).hexdigest()
        _same(request, ri["request_text_sha256"], "reader text input mismatch")
        if ri["chart_sha256"]:
            png = _object(objects, ri["chart_sha256"], binary=True)
        else:
            png = None
        cl = row.get("claude") or {}
        for attempt in cl.get("attempts", []):
            content = ([{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(png).decode()}}] if png is not None else [])
            content.append({"type": "text", "text": grader.user_text(metrics)})
            if attempt["correction"]:
                content.append({"type": "text", "text": grader.RETRY_CORRECTION})
            kwargs = grader.request_kwargs(system, content, model=cl["attempted_model"])
            _same(digest(kwargs), attempt["request_sha256"], "actual model request digest mismatch")


def verify(data, picks=None, objects=None, *, require_sources=True, require_picks=False):
    """PASS / FAIL with a break reason / PARTIAL for explicitly missing evidence.

No repair or write. Objects may be a directory or the pipeline's in-memory
archive. Integrity-only callers explicitly disable the source replay requirement.
"""
    breaks, missing, checked = [], [], []
    if not isinstance(data, dict):
        return {"status": "FAIL", "breaks": ["publication is not an object"], "missing": [], "checked": []}
    if not isinstance(data.get("run", {}), dict):
        return {"status": "FAIL", "breaks": ["publication run is not an object"], "missing": [], "checked": []}
    marker = (data.get("run") or {}).get("evidence")
    if not marker:
        if (data.get("rules", {}).get("provenance") or any(r.get("evidence") for r in data.get("bursts", []))):
            return {"status": "FAIL", "breaks": ["new publication lacks run provenance"], "missing": [], "checked": []}
        return {"status": "PARTIAL", "breaks": [], "missing": ["legacy publication: provenance unknown"], "checked": []}
    try:
        if marker["version"] != VERSION:
            raise ValueError("unsupported provenance version")
        ctx = digest(context(data))
        _same(ctx, marker["context_sha256"], "run/context digest mismatch")
        _same(data["run"]["feed"], data["run"]["input_basis"]["feed"], "display feed differs from source basis")
        _same(data["run"]["input_basis"]["evaluated_session"], data["run"]["session"], "input basis session mismatch")
        from src.report import rules_version, timing_faults
        _same(rules_version(data["rules"]), data["app"]["rules_version"], "rules identity mismatch")
        mismatches = []
        for rules in (scans.RULES, discovery.RULES, quality.RULES, plan.RULES, watchlist.RULES, sessions.RULES, RULES):
            for key, value in rules.items():
                family, _, name = key.partition(".")
                if digest(data["rules"].get(family, {}).get(name)) != digest(value):
                    mismatches.append(key)
        compatible = not mismatches
        if mismatches:
            missing.append("archived rules need a compatible verifier implementation: " + ", ".join(mismatches))
        if compatible:
            existing_faults = inputs.record_faults(data["run"]) + sessions.record_faults(data["run"]) + timing_faults(data["run"]["timing"])
            if existing_faults:
                raise ValueError("input/calendar contract: " + "; ".join(existing_faults))
        if data["breadth"]["regime"]["verdict"] not in ("red", "yellow", "green"):
            raise ValueError("unknown regime")
        candidates = [("burst", r) for r in data["bursts"]] + [("anticipation", r) for r in data.get("watchlist", {}).get("top", [])]
        for kind, row in candidates:
            ticker = row.get("ticker", "?")
            try:
                e = row["evidence"]
                _same(digest({k: v for k, v in e.items() if k != "id"}), e["id"], "evidence identity mismatch")
                _same([e["version"], e["ticker"], e["kind"], e["session"], e["rules_version"], e["context_sha256"]],
                      [VERSION, ticker, kind, data["run"]["session"], data["app"]["rules_version"], ctx], "setup/context identity mismatch")
                if kind == "burst":
                    _same(digest(facts(row)), e["facts_sha256"], "candidate facts digest mismatch")
                    _same(digest(row["discovery"]), e["discovery_sha256"], "discovery digest mismatch")
                    _same(digest(mechanical(row)), e["quality_sha256"], "mechanical quality digest mismatch")
                    if compatible:
                        _check_mechanical(row)
                    _check_reader(row, e, compatible)
                    _check_plan(data, row, e, compatible)
                    if objects is not None and compatible:
                        _check_source(data, row, e, objects)
                else:
                    _check_watch(data, row, e, objects, compatible)
                if objects is not None and not compatible:
                    _object(objects, e["source"]["sha256"])
                if objects is None and require_sources:
                    missing.append(f"{ticker}: source objects not supplied")
                if e["gate"]["ticket"]:
                    if picks is None:
                        if require_picks:
                            missing.append(f"{ticker}: persisted picks not supplied")
                    else:
                        matches = [p for p in picks["picks"] if p["ticker"] == ticker and p["date"] == e["session"] and p["kind"] == kind and (p.get("evidence_ref") or {}).get("id") == e["id"]]
                        if len(matches) != 1:
                            raise ValueError("published ticket has no unique persisted pick")
                        pick = matches[0]
                        _same(pick.get("evidence_ref"), reference(e), "persisted pick evidence reference mismatch")
                        _same(pick["regime"], e["gate"]["regime"], "persisted pick regime mismatch")
                        projection = {k: v for k, v in pick.items() if k not in ("date", "regime", "evidence_ref")}
                        _same(digest(projection), e["planning"]["pick_sha256"], "picks/data plan mismatch")
                checked.append(e["id"])
            except (ValueError, KeyError, TypeError, IndexError, OSError, AttributeError) as exc:
                breaks.append(f"{ticker}: {exc}")
        if picks is not None:
            current = [p for p in picks["picks"] if p["date"] == data["run"]["session"] and (p.get("evidence_ref") or {}).get("context_sha256") == ctx]
            expected = {(kind, r["ticker"]) for kind, r in candidates if r["evidence"]["gate"]["ticket"]}
            if {(p["kind"], p["ticker"]) for p in current} != expected:
                breaks.append("persisted ticket membership differs from publication")
        if compatible:
            plans = [plain_plan(r) for r in data["bursts"] if r.get("plan")]
            account = plan.Account(**{k: data["account"][k] for k in ACCOUNT_FIELDS})
            replay_budget = plan.cash_budget(plans, account, open_positions=data["cash_budget"]["open_positions"])
            _same(replay_budget, data["cash_budget"], "cash-budget decision differs from candidate plans")
    except (ValueError, KeyError, TypeError, IndexError, AttributeError) as exc:
        breaks.append(str(exc))
    return {"status": "FAIL" if breaks else "PARTIAL" if missing else "PASS", "breaks": breaks, "missing": missing, "checked": checked}


def require(data, picks=None, objects=None, *, require_sources=False, require_picks=False):
    result = verify(data, picks, objects, require_sources=require_sources, require_picks=require_picks)
    if result["status"] != "PASS":
        raise ValueError("provenance refused: " + "; ".join(result["breaks"] + result["missing"]))
    return result


def verify_setup(candidate_or_plan, publication, picks=None, objects=None):
    """Check a supplied candidate/ticket against its publication, then its chain."""
    evidence = candidate_or_plan.get("evidence") or candidate_or_plan.get("evidence_ref") or {}
    identity = evidence.get("id")
    if not identity:
        return {"status": "PARTIAL", "breaks": [], "missing": ["legacy setup: provenance unknown"], "checked": []}
    rows = publication.get("bursts", []) + publication.get("watchlist", {}).get("top", [])
    for row in rows:
        if (row.get("evidence") or {}).get("id") == identity:
            original = row if "evidence" in candidate_or_plan else row.get("plan")
            if digest(original) != digest(candidate_or_plan):
                return {"status": "FAIL", "breaks": ["supplied setup/plan differs from publication"], "missing": [], "checked": []}
            return verify(publication, picks, objects, require_picks=picks is not None)
    return {"status": "FAIL", "breaks": ["setup is absent from publication"], "missing": [], "checked": []}


def write_objects(objects, directory):
    """Content addressed; existing different bytes are never overwritten."""
    directory = Path(directory)
    prepared = {}
    for key, obj in objects.items():
        binary = isinstance(obj, bytes)
        _object(objects, key, binary)
        raw = obj if binary else json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
        if len(raw) > MAX_OBJECT_BYTES:
            raise ValueError("expanded evidence object exceeds bound")
        raw = raw if binary else gzip.compress(raw, mtime=0)
        if len(raw) > MAX_OBJECT_BYTES:
            raise ValueError("evidence object exceeds bound")
        path = directory / (key + (".png" if binary else ".json.gz"))
        if path.exists():
            _object(directory, key, binary)
        else:
            prepared[path] = raw
    existing_bytes = sum(p.stat().st_size for p in directory.glob("*") if p.is_file())
    if existing_bytes + sum(len(raw) for raw in prepared.values()) > MAX_ARCHIVE_BYTES:
        raise ValueError("evidence archive capacity exceeded; publication withheld")
    directory.mkdir(parents=True, exist_ok=True)
    for path, raw in prepared.items():
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as staged:
            temporary = Path(staged.name)
            try:
                staged.write(raw)
                staged.flush()
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)


def publish_bundle(data, rec, docs, objects, *, dry_run=False):
    """Verify the serialized data AND picks before installing either file.

Publish data last. Ordinary write/rename failures restore the previous pair;
process death between filesystem renames is not a multi-file transaction.
"""
    from src import record, report
    docs = Path(docs)
    require(data, None if dry_run else rec, objects, require_sources=True, require_picks=not dry_run)
    with tempfile.TemporaryDirectory(prefix=".publication-", dir=docs) as tmp:
        stage = Path(tmp)
        report.write(data, stage / "data.json")
        if not dry_run:
            record.save(rec, stage)
        staged = json.loads((stage / "data.json").read_bytes())
        persisted = None if dry_run else json.loads((stage / "picks.json").read_bytes())
        require(staged, persisted, objects, require_sources=False, require_picks=not dry_run)
        write_objects(objects, docs / OBJECT_DIR)
        names = ["data.json"] if dry_run else ["picks.json", "data.json"]
        previous = {n: (docs / n).read_bytes() if (docs / n).exists() else None for n in names}
        installed = []
        try:
            for n in names:
                os.replace(stage / n, docs / n)
                installed.append(n)
        except OSError:
            for n in reversed(installed):
                if previous[n] is None:
                    (docs / n).unlink()
                else:
                    (stage / n).write_bytes(previous[n])
                    os.replace(stage / n, docs / n)
            raise
