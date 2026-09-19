"""Run-local input evidence. Never used to accept, grade or publish a stock.

Only allowlisted application observations are retained, not provider responses.
The public ledger stays compact; these files belong outside the published tree.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import logging
import math
import os
import re
import subprocess
import tempfile
import uuid
import zlib
from datetime import date, datetime, timedelta, timezone
from numbers import Integral, Real
from pathlib import Path

import pandas as pd

from src import market_data, universe

VERSION = 1
TAIL_ROWS = 8
MAX_ROWS_PER_SYMBOL = TAIL_ROWS + 2
MAX_TOTAL_ROWS = (universe.MAX_DISCOVERY + 1) * MAX_ROWS_PER_SYMBOL
DIRECTORY_NAME = "universe-directory.json.gz"
RECORD_NAME = "input-exceptions.json"
ROOT_NAME = "input-diagnostics"
FIELDS = {"Open": "opening price", "High": "highest price", "Low": "lowest price",
          "Close": "closing price", "Volume": "share volume",
          "vwap": "volume-weighted average price", "trade_count": "number of trades"}
REASONS = {"stale": "stale", "gapped": "gapped", "unreadable": "unreadable",
           "no_bars": "no_bars", "dropped": "dropped_symbols", "refused": "refused",
           "unfetched_budget": "unfetched", "unfetched_failure": "unrequested"}
COUNTS = ("intended", "requested", "with_bars", "no_bars", "dropped", "refused",
          "unfetched_budget", "unfetched_failure", "stale", "gapped", "unreadable",
          "on_session", "session_ready", "benchmark_ready", "duplicate_symbols",
          "duplicate_bars", "returned_bars", "batch_attempts")
LIMITS = ["application_normalized_observations_only", "absence_does_not_establish_provider_cause",
          "raw_http_pages_unavailable", "condition_coded_trades_unavailable",
          "sdk_internal_partial_pages_unavailable", "provider_entity_mappings_unavailable",
          "discarded_duplicate_copies_unavailable", "not_final_scan_measurements"]
log = logging.getLogger(__name__)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def population(symbols):
    names = sorted(set(symbols))
    if any(not isinstance(s, str) or not re.fullmatch(r"[A-Z]{1,5}", s) for s in names):
        raise ValueError("invalid diagnostic symbol")
    return {"symbols": names, **universe.population(names)}


def _id(value, pattern):
    return value if isinstance(value, str) and re.fullmatch(pattern, value) else None


def run_identity():
    """Read only explicit CI identifiers and the actual local execution checkout."""
    revision = None
    try:
        result = subprocess.run(["git", "rev-parse", "--verify", "HEAD"],
                                cwd=Path(__file__).resolve().parent.parent,
                                capture_output=True, text=True, timeout=5, check=True)
        revision = _id(result.stdout.strip(), r"[0-9a-f]{40}")
    except (OSError, subprocess.SubprocessError):
        pass
    return {"run_id": _id(os.getenv("GITHUB_RUN_ID_FOR_RECORD") or os.getenv("GITHUB_RUN_ID"), r"[0-9]{1,20}"),
            "attempt": _id(os.getenv("GITHUB_RUN_ATTEMPT"), r"[0-9]{1,10}"),
            "execution_revision": revision,
            "workflow_revision": _id(os.getenv("GITHUB_SHA"), r"[0-9a-f]{40}"),
            "invocation": uuid.uuid4().hex}


def value_cell(value):
    """Keep native numeric precision and distinguish missing from invalid data.

    Never stringify arbitrary objects/strings (they can contain credentials).
    Column-wise scalar access avoids iterrows coercing integer volumes to floats.
    """
    if value is None:
        return {"state": "null"}
    if value is pd.NA:
        return {"state": "missing"}
    if isinstance(value, (bool,)):
        return {"state": "invalid"}
    if isinstance(value, Integral):
        return {"state": "value", "value": int(value)}
    if isinstance(value, Real):
        number = float(value)
        if math.isnan(number):
            return {"state": "nan"}
        if math.isinf(number):
            return {"state": "positive_infinity" if number > 0 else "negative_infinity"}
        return {"state": "value", "value": number}
    return {"state": "invalid"}


def timestamp_cell(value):
    if value is None:
        return {"state": "null"}
    if value is pd.NaT:
        return {"state": "nat"}
    if not isinstance(value, (str, date, datetime, pd.Timestamp)):
        return {"state": "unreadable"}
    try:
        stamp = pd.Timestamp(value)
        if stamp is pd.NaT:
            return {"state": "nat"}
        return {"state": "value", "value": stamp.isoformat(), "session": stamp.date().isoformat()}
    except (ValueError, TypeError, OverflowError):
        return {"state": "unreadable"}


def observations(frame, expected, previous, *, remaining):
    if frame is None:
        return {"frame": "missing", "rows_total": 0, "rows_omitted": 0, "rows": [],
                "session_rows": {}, "partial": False}
    stamps = [timestamp_cell(s) for s in frame.index]
    positions = set(range(max(0, len(frame) - TAIL_ROWS), len(frame)))
    session_positions = {}
    for day in (expected, previous):
        if day is not None:
            key = day.isoformat()
            found = [i for i, s in enumerate(stamps) if s.get("session") == key]
            session_positions[key] = found
            if found:
                positions.add(found[-1])
    # Reserve the dated anchors before spending a restricted global budget.
    anchors = {found[-1] for found in session_positions.values() if found}
    chosen = sorted((sorted(anchors) + sorted(positions - anchors))[:remaining])
    rows = [{"position": i, "timestamp": stamps[i],
             "values": {name: value_cell(frame[name].iloc[i]) if name in frame.columns
                        else {"state": "absent_field"} for name in FIELDS}}
            for i in chosen]
    return {"frame": "available", "rows_total": len(frame), "rows_omitted": len(frame) - len(rows),
            "rows": rows, "partial": len(rows) < len(frame),
            "session_rows": {day: {"present": len(found), "retained": len(set(found) & set(chosen))}
                             for day, found in session_positions.items()}}


def request_basis(symbols, stats, expected, now, lookback, chunk_size, budget):
    """Arguments supplied by fetch_universe, not a claim about SDK wire pages."""
    day = datetime(expected.year, expected.month, expected.day, tzinfo=timezone.utc)
    start = day - timedelta(days=int(lookback * market_data.LOOKBACK_CALENDAR_RATIO))
    end = day + timedelta(hours=23, minutes=59, seconds=59)
    if stats.feed == "sip":
        latest = now - timedelta(minutes=market_data.SIP_HOLDBACK_MINUTES)
        if latest >= day:
            end = min(end, latest)
    return {"provider": "Alpaca", "feed": stats.feed, "adjustment": market_data.BAR_ADJUSTMENT.value,
            "timeframe": "1Day", "fetch_arguments": {"symbols_in_order": list(symbols),
            "session": expected.isoformat(), "lookback_days": lookback, "now": now.isoformat(),
            "chunk_size": chunk_size, "budget_seconds": budget},
            "window": {"basis": "reconstructed_from_application_arguments_not_observed_wire_request",
                       "start": start.isoformat(), "end": end.isoformat()},
            "sdk_batch_size_default": market_data.DEFAULT_BATCH_SIZE,
            "sdk_batch_attempts": stats.batch_attempts, "wire_request_count": None}


def directory_snapshot(docs, uni):
    """Copy existing bytes only when their capture time and field hash match.

    A seed/explicit run never borrowed a leftover directory. A failed cache save
    can leave unrelated bytes at the usual path; those must not be attributed.
    """
    used = uni.source == universe.SOURCE_LIVE or uni.source.startswith(universe.SOURCE_CACHE)
    if not used:
        return {"status": "not_used"}, None
    try:
        with (Path(docs) / universe.DIRECTORY_CACHE).open("rb") as handle:
            raw = handle.read(universe.DIRECTORY_MAX_BYTES + 1)
        if len(raw) > universe.DIRECTORY_MAX_BYTES:
            raise ValueError
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as handle:
            expanded = handle.read(universe.DIRECTORY_MAX_BYTES + 1)
        if len(expanded) > universe.DIRECTORY_MAX_BYTES:
            raise ValueError
        data = json.loads(expanded)
        if set(data) != {"schema_version", "source_url", "fetched_at", "rows"}:
            raise ValueError
        if (data["schema_version"] != universe.DIRECTORY_CACHE_SCHEMA
                or data["source_url"] != universe.SOURCE_URL or data["fetched_at"] != uni.fetched_at
                or not isinstance(data["rows"], list)
                or len(data["rows"]) > universe.DIRECTORY_MAX_ROWS
                or any(set(row) != set(universe.DIRECTORY_FIELDS) for row in data["rows"])):
            raise ValueError
        fingerprint = hashlib.sha256(json.dumps(data["rows"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if fingerprint != uni.snapshot_sha256:
            raise ValueError
        return {"status": "retained", "file": DIRECTORY_NAME, "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(), "canonical_fields_sha256": fingerprint}, raw
    except (OSError, ValueError, TypeError, KeyError, EOFError, zlib.error):
        return {"status": "unavailable_or_identity_mismatch"}, None


def build(*, identity, captured_at, uni, symbols, frames, stats, ready, coverage,
          expected, session, now, lookback, chunk_size, budget, refused=False):
    reasons = {key: population(getattr(stats, attr)) for key, attr in REASONS.items()}
    duplicates = population(stats.duplicates)
    affected = sorted(set().union(*(set(p["symbols"]) for p in reasons.values()), stats.duplicates))
    remaining = MAX_TOTAL_ROWS
    evidence = {}
    not_attempted = set(stats.unfetched) | set(stats.unrequested)
    for symbol in affected:
        obs = observations(frames.get(symbol), expected, stats.previous_session, remaining=remaining)
        remaining -= len(obs["rows"])
        evidence[symbol] = {"role": "benchmark" if symbol == "SPY" else "intended_stock",
                            "attempted": symbol not in not_attempted,
                            **obs}
    source = universe.provenance(uni, expected)
    record = {"schema_version": VERSION, "run": identity,
              "capture": {"stage": "input_session_rules_before_price_and_scan",
                          "captured_at": captured_at.isoformat(), "fetch": "permanent_refusal" if refused else "returned",
                          "evaluation": "not_started", "expected_session": expected.isoformat(),
                          "evaluated_session": session.isoformat(),
                          "prior_session": stats.previous_session.isoformat() if stats.previous_session else None},
              "universe": {key: source[key] for key in ("source_kind", "fetched_at", "identity", "snapshot_sha256")},
              "universe_membership": population(uni.symbols), "intended": population(symbols),
              "intended_stocks": population(set(symbols) - {"SPY"}), "benchmark": "SPY",
              "returned": population(frames), "session_ready": population(ready),
              "exceptions": reasons, "duplicate_repaired": duplicates,
              "duplicate_extra_rows": {s: stats.duplicates[s] for s in sorted(stats.duplicates)},
              "input_counts": {key: coverage[key] for key in COUNTS},
              "ledger_identity": coverage["intended_identity"],
              "basis": request_basis(symbols, stats, expected, now, lookback, chunk_size, budget),
              "bounds": {"tail_rows": TAIL_ROWS, "rows_per_symbol": MAX_ROWS_PER_SYMBOL,
                         "total_rows": MAX_TOTAL_ROWS, "membership_truncated": False,
                         "selection": "last eight frame positions plus last expected/prior-session positions"},
              "payload": {"rows_retained": MAX_TOTAL_ROWS - remaining,
                          "rows_omitted": sum(o["rows_omitted"] for o in evidence.values()),
                          "partial": any(o["partial"] for o in evidence.values())},
              "field_meanings": FIELDS, "observations": evidence,
              "limits": LIMITS, "directory": {"status": "not_checked"}}
    # Validate against the actual compact ledger before losing its full inputs.
    for key, pop in {**reasons, "duplicate_repaired": duplicates}.items():
        if {k: pop[k] for k in ("count", "identity", "sample")} != coverage["reasons"][key]:
            raise ValueError("diagnostic membership disagrees with input ledger")
    return record


def validate(record, *, expected_run, ledger=None, directory_bytes=None):
    """Reject corrupt membership, a mismatched invocation or inconsistent ledger.

    SHA-256 is integrity, not authentication. Supply independently expected run
    identifiers; a self-consistent rewrite cannot authenticate its own origin.
    Final ledgers can be compared only at the unchanged input boundaries below.
    """
    def require(test):
        if not test:
            raise ValueError("invalid input diagnostic")

    require(record["schema_version"] == VERSION and record["run"] == expected_run)
    require(record["record_sha256"] == digest({k: v for k, v in record.items() if k != "record_sha256"}))
    pops = [record[k] for k in ("universe_membership", "intended", "intended_stocks", "returned", "session_ready", "duplicate_repaired")]
    require(set(record["exceptions"]) == set(REASONS))
    pops += list(record["exceptions"].values())
    for pop in pops:
        require(pop == population(pop["symbols"]))
    names, returned, ready = (set(record[k]["symbols"]) for k in ("intended", "returned", "session_ready"))
    require(record["benchmark"] == "SPY" and "SPY" in names)
    require(set(record["intended_stocks"]["symbols"]) == names - {"SPY"})
    require(set(record["universe_membership"]["symbols"]) | {"SPY"} == names)
    require(record["universe"]["identity"] == record["universe_membership"]["identity"])
    require(record["ledger_identity"] == record["intended"]["identity"])
    groups = {k: set(p["symbols"]) for k, p in record["exceptions"].items()}
    exclusive = list(groups.values()) + [ready]
    require(set().union(*exclusive) == names and sum(map(len, exclusive)) == len(names))
    require(returned == ready | groups["stale"] | groups["gapped"] | groups["unreadable"])
    duplicate = set(record["duplicate_repaired"]["symbols"])
    # Repairs can be observed in a failed partial batch even if its frames were
    # never returned. They overlap exceptions; they are not another exclusion.
    require(duplicate <= names and set(record["duplicate_extra_rows"]) == duplicate)
    require(all(type(n) is int and n > 0 for n in record["duplicate_extra_rows"].values()))
    affected = set().union(*groups.values(), duplicate)
    require(set(record["observations"]) == affected)
    c = record["input_counts"]
    require(set(c) == set(COUNTS) and all(type(v) is int and v >= 0 for v in c.values()))
    for key, group in groups.items():
        require(c[key] == len(group))
    require(c["intended"] == len(names) and c["with_bars"] == len(returned))
    require(c["requested"] == len(names - groups["unfetched_budget"] - groups["unfetched_failure"]))
    require(c["on_session"] == len(returned - groups["stale"]) and c["session_ready"] == len(ready))
    require(c["benchmark_ready"] == int("SPY" in ready))
    require(c["duplicate_symbols"] == len(duplicate) and c["duplicate_bars"] == sum(record["duplicate_extra_rows"].values()))
    require(set(record["basis"]["fetch_arguments"]["symbols_in_order"]) == names)
    row_count = 0
    for symbol, obs in record["observations"].items():
        require(obs["role"] == ("benchmark" if symbol == "SPY" else "intended_stock"))
        require(obs["attempted"] == (symbol not in groups["unfetched_budget"] | groups["unfetched_failure"]))
        require(obs["frame"] == ("available" if symbol in returned else "missing"))
        require(0 <= len(obs["rows"]) <= MAX_ROWS_PER_SYMBOL)
        require(obs["rows_total"] == len(obs["rows"]) + obs["rows_omitted"])
        require(obs["rows_omitted"] >= 0 and obs["partial"] == bool(obs["rows_omitted"]))
        require([r["position"] for r in obs["rows"]] == sorted({r["position"] for r in obs["rows"]}))
        require(all(0 <= r["position"] < obs["rows_total"] and set(r["values"]) == set(FIELDS) for r in obs["rows"]))
        row_count += len(obs["rows"])
    require(row_count <= MAX_TOTAL_ROWS)
    require(record["payload"] == {"rows_retained": row_count,
            "rows_omitted": sum(o["rows_omitted"] for o in record["observations"].values()),
            "partial": any(o["partial"] for o in record["observations"].values())})
    if ledger is not None:
        require(all(ledger[k] == c[k] for k in COUNTS))
        require(ledger["intended_identity"] == record["ledger_identity"])
        for key, pop in {**record["exceptions"], "duplicate_repaired": record["duplicate_repaired"]}.items():
            require(ledger["reasons"][key] == {k: pop[k] for k in ("count", "identity", "sample")})
    directory = record["directory"]
    if directory["status"] == "retained":
        require(directory_bytes is not None and len(directory_bytes) == directory["bytes"])
        require(hashlib.sha256(directory_bytes).hexdigest() == directory["sha256"])


def _atomic_write(path, raw):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(raw)
        os.replace(temporary, path)  # close first, including on Windows
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def capture(*, docs, **kwargs):
    """Best effort, isolated from pipeline status and retry/decision machinery."""
    try:
        identity = run_identity()
        record = build(identity=identity, captured_at=datetime.now(timezone.utc), **kwargs)
        directory, raw = directory_snapshot(docs, kwargs["uni"])
        record["directory"] = directory
        record["record_sha256"] = digest(record)
        validate(record, expected_run=identity, ledger=kwargs["coverage"], directory_bytes=raw)
        parent = Path(docs).resolve().parent / ROOT_NAME
        parent.mkdir(parents=True, exist_ok=True)
        name = f"{identity['run_id'] or 'local'}-{identity['attempt'] or 'unknown'}-{identity['invocation']}"
        destination = parent / name
        destination.mkdir()  # unique invocation; never reuse an earlier record
        if raw is not None:
            _atomic_write(destination / DIRECTORY_NAME, raw)
        _atomic_write(destination / RECORD_NAME, canonical(record))
        log.info("Input diagnostic retained: %s", destination)
        return {"status": "retained", "path": str(destination)}
    except Exception:  # diagnostic failure must not replace the original error
        log.error("Input diagnostic capture failed; input decisions unchanged; evidence unavailable")
        return {"status": "failed", "path": None, "failure": "input_diagnostic_capture_failed"}
