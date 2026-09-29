"""Dedicated manual historical execution; stdout contains only constant status.

Acquisition is a fresh, one-shot command. Offline replay requires the original
ledger and never creates a new allowance. The Actions readiness guard owns the
durable lifetime claim; this wrapper verifies its bound execution before use.
Synthetic rehearsal exercises the real Acquisition cache and replay contracts.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import historical_acquisition as acquisition

MANIFEST_SHA256 = "8d92ed5c56464fe9f342d024da14aa1521f6025d47ec32a6324a298b8fb63ebc"
MANIFEST = ROOT / "docs/input-truthfulness/2026-09-28-historical-input-evidence/acquisition-manifest.json"
REPOSITORY = "spicyChicken59/SpicyStock"
SECRETS = ("ALPACA_API_KEY", "ALPACA_SECRET_KEY")
MODES = ("rehearsal", "real", "offline")
DEADLINE_SECONDS = 25 * 60


class ExecutionError(RuntimeError):
    """Internal reason codes are never replaced by untrusted exception text."""


class ExecutionDeadline(BaseException):
    """Bypass transport retry handling so interrupted slots stay charged."""


def _json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ExecutionError("invalid_document")
            result[key] = value
        return result
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique)


def _checkout_sha():
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout.strip()


def validate_execution(execution, mode, identity):
    """The document is emitted by the independently checked Actions guard."""
    original_mode = execution.get("mode")
    if (execution.get("schema") != "historical-execution-v1" or
            execution.get("status") != "PASS" or
            execution.get("assignment_id") != acquisition.ASSIGNMENT or
            execution.get("manifest_sha256") != identity or
            execution.get("repository") != REPOSITORY or
            execution.get("readiness_status") != "PASS" or
            execution.get("lifetime_status") != "PASS" or
            original_mode not in ("rehearsal", "real") or
            (mode != "offline" and original_mode != mode) or
            type(execution.get("run_attempt")) is not int or execution["run_attempt"] != 1 or
            type(execution.get("run_number")) is not int or
            execution.get("run_number") != (1 if original_mode == "rehearsal" else 2)):
        raise ExecutionError("execution_identity_rejected")
    for field in ("repository_id", "workflow_id", "run_id", "readiness_comment_id", "implementation_pr"):
        if type(execution.get(field)) is not int or execution[field] <= 0:
            raise ExecutionError("execution_identity_rejected")
    for field, size in (("checkout_sha", 40), ("workflow_sha", 40), ("recipient_sha256", 64)):
        if not re.fullmatch("[0-9a-f]{" + str(size) + "}", execution.get(field, "")):
            raise ExecutionError("execution_identity_rejected")
    if execution["checkout_sha"] != _checkout_sha():
        raise ExecutionError("checkout_identity_rejected")
    if mode != "offline":
        expected = {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "workflow_dispatch",
                    "GITHUB_REPOSITORY": REPOSITORY, "GITHUB_REF": "refs/heads/main",
                    "GITHUB_REPOSITORY_ID": str(execution["repository_id"]),
                    "GITHUB_RUN_ID": str(execution["run_id"]),
                    "GITHUB_RUN_NUMBER": str(execution["run_number"]),
                    "GITHUB_RUN_ATTEMPT": "1", "GITHUB_WORKFLOW_SHA": execution["workflow_sha"]}
        if any(os.environ.get(name) != value for name, value in expected.items()):
            raise ExecutionError("runtime_identity_rejected")


def _linked(path):
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def validate_storage(storage, *, fresh):
    """Reject linked paths and Git ancestors before creating private scratch."""
    path = Path(storage)
    if not path.is_absolute() or ".." in path.parts:
        raise ExecutionError("unsafe_storage")
    for parent in (path, *path.parents):
        if _linked(parent) or (parent / ".git").exists():
            raise ExecutionError("unsafe_storage")
    path = path.resolve()
    if path == ROOT or ROOT in path.parents or path == Path(path.anchor):
        raise ExecutionError("unsafe_storage")
    if fresh and path.exists():
        raise ExecutionError("fresh_execution_cannot_resume_or_reset_storage")
    if not fresh:
        if not path.is_dir() or not (path / "ledger.sqlite3").is_file():
            raise ExecutionError("original_ledger_required")
        # Recovered archives are flat except for raw pages. Never traverse links.
        if any(_linked(p) for p in path.rglob("*")):
            raise ExecutionError("unsafe_storage")
    return path


def ledger_accounting(storage, identity):
    """Read-only validation; sqlite must never create a replacement ledger."""
    ledger = Path(storage) / "ledger.sqlite3"
    if not ledger.is_file() or _linked(ledger):
        raise ExecutionError("original_ledger_required")
    with sqlite3.connect(ledger.as_uri() + "?mode=ro", uri=True) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ExecutionError("invalid_original_ledger")
        row = db.execute("SELECT value FROM metadata WHERE name='manifest_sha256'").fetchone()
        if row is None or row[0] != identity:
            raise ExecutionError("original_ledger_identity_rejected")
        count, retained, reserved = db.execute(
            "SELECT COUNT(*),COALESCE(SUM(retained),0),COALESCE(SUM(reservation),0) FROM attempts").fetchone()
    return {"request_slots_charged": count, "uncompressed_retained_bytes_charged": retained,
            "unresolved_byte_reservations": reserved}


@contextmanager
def acquisition_deadline():
    """Linux runner timer leaves five minutes before a 30-minute step timeout."""
    if not hasattr(signal, "SIGALRM"):
        # Real runner execution is Linux; synthetic Windows tests have no HTTP.
        yield
        return
    previous = signal.getsignal(signal.SIGALRM)
    def expired(*_):
        raise ExecutionDeadline()
    signal.signal(signal.SIGALRM, expired)
    signal.alarm(DEADLINE_SECONDS)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


class SyntheticTransport:
    """Deterministic invented daily bars; never creates any HTTP connection.

    Every frozen query is served, but bulk queries deliberately contain only
    the last 80 declared sessions. Missing earlier warmup remains explicit.
    Pagination uses the actual shared total-row limit, including split symbols.
    """
    fields = ("start", "end", "feed", "timeframe", "adjustment", "currency", "asof", "limit", "sort", "symbols")

    def __init__(self, manifest):
        self.queries = {}
        self.calls = 0
        self.now = datetime(2026, 9, 28, tzinfo=timezone.utc).timestamp()
        for item in manifest["queries"]:
            query = acquisition.resolved_query(manifest, item["id"])
            params = {**query, "symbols": ",".join(query["symbols"])}
            key = tuple(params[field] for field in self.fields)
            if key in self.queries:
                raise ExecutionError("synthetic_query_identity_collision")
            self.queries[key] = query

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds

    def __call__(self, params, byte_limit):
        self.calls += 1
        query = self.queries[tuple(params[field] for field in self.fields)]
        dates = query["required_sessions"] if query["scope"] == "probe" else query["required_sessions"][-80:]
        start = int(params.get("page_token", "0"))
        total = len(dates) * len(query["symbols"])
        end = min(start + query["limit"], total)
        bars = {}
        for offset in range(start, end):
            symbol = query["symbols"][offset // len(dates)]
            day_index = offset % len(dates)
            stamp = datetime.fromisoformat(dates[day_index]).replace(tzinfo=acquisition.NY)
            price = 20 + (sum(map(ord, symbol)) % 80) + day_index // 20
            bars.setdefault(symbol, []).append({
                "t": stamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                "o": price, "h": price + 1, "l": price - 1, "c": price,
                "v": 100000 + day_index * 100})
        body = acquisition.encode({"bars": bars, "next_page_token": str(end) if end < total else None})
        if len(body) > byte_limit:
            raise acquisition.AcquisitionError("response_byte_limit_exceeded")
        return acquisition.HTTPResult(200, {"content-type": "application/json"}, body)


def preflight(mode, manifest, storage, execution, approval=None):
    """Validate scope, identity and paths before the provider step has secrets."""
    if mode not in MODES:
        raise ExecutionError("unsupported_mode")
    identity = acquisition.validate_manifest(manifest)
    if identity != MANIFEST_SHA256:
        raise ExecutionError("frozen_manifest_rejected")
    validate_execution(execution, mode, identity)
    storage = validate_storage(storage, fresh=mode != "offline")
    if mode != "offline":
        acquisition.validate_approval(manifest, approval or {}, storage)
    else:
        ledger_accounting(storage, identity)
    if mode == "real" and not hasattr(signal, "SIGALRM"):
        raise ExecutionError("bounded_linux_runner_required")
    return storage, identity


def execute(mode, manifest, storage, execution, approval=None):
    """Run only the frozen scope. Detailed results stay inside private storage."""
    storage, identity = preflight(mode, manifest, storage, execution, approval)
    if mode != "real" and any(os.environ.get(name) for name in SECRETS):
        raise ExecutionError("provider_environment_forbidden")
    if mode == "real" and not all(os.environ.get(name) for name in SECRETS):
        raise ExecutionError("provider_credentials_unavailable")
    diagnostic = {"schema": "historical-execution-diagnostics-v1", "mode": execution["mode"],
                  "manifest_sha256": identity, "synthetic": execution["mode"] == "rehearsal",
                  "provider_calls_authorized": mode == "real", "phase": mode, "status": "BLOCKED"}
    previous_mask = os.umask(0o077)
    try:
        if mode != "offline":
            # Atomic creation also prevents two wrappers sharing fresh storage.
            storage.mkdir(mode=0o700, parents=False, exist_ok=False)
        else:
            prior = storage / "execution-diagnostics.json"
            if prior.is_file():
                prior_record = _json(prior)
                diagnostic["prior_acquisition"] = prior_record.get("prior_acquisition", prior_record)
        try:
            # Suppress unexpected library warnings/value-rich tracebacks. Only
            # fixed status JSON is allowed on the public command streams.
            with open(os.devnull, "w") as quiet, redirect_stdout(quiet), redirect_stderr(quiet):
                if mode == "offline":
                    from tools.historical_reconcile import network_blocked, reconcile
                    results = []
                    with network_blocked():
                        for session in sorted(manifest["populations"]):
                            try:
                                results.append(reconcile(manifest, storage, session))
                            except Exception:
                                results.append({"session": session, "status": "BLOCKED",
                                                "reason": "offline_input_validation_failed"})
                    diagnostic["reconciliation"] = results
                    diagnostic["status"] = ("FAIL" if any(r["status"] == "FAIL" for r in results) else
                                            "BLOCKED" if any(r["status"] != "PASS" for r in results) else "PASS")
                    diagnostic["scientific_reconciliation_status"] = diagnostic["status"]
                    if execution["mode"] == "rehearsal":
                        # A completed synthetic exercise may correctly report
                        # scientific unknowns from its deliberately short data.
                        # Missing outputs, formula disagreement, or an earlier
                        # failed acquisition never pass the rehearsal itself.
                        completed = (diagnostic.get("prior_acquisition", {}).get("status") == "PASS" and
                                     all("output_sha256" in r and r.get("same_input_formula_status") != "FAIL"
                                         for r in results))
                        diagnostic["status"] = "PASS" if completed else "BLOCKED"
                    diagnostic["new_provider_requests"] = 0
                else:
                    kwargs = {}
                    if mode == "rehearsal":
                        from tools.historical_reconcile import network_blocked
                        transport = SyntheticTransport(manifest)
                        kwargs = {"transport": transport, "clock": transport.clock, "sleep": transport.sleep}
                        with network_blocked():
                            reports = acquisition.Acquisition(manifest, approval, storage, **kwargs).run_all()
                        diagnostic["synthetic_transport_calls"] = transport.calls
                        diagnostic["new_provider_requests"] = 0
                        diagnostic["synthetic_bulk_session_limit"] = 80
                    else:
                        with acquisition_deadline():
                            reports = acquisition.Acquisition(manifest, approval, storage).run_all()
                    diagnostic["completed_queries"] = len(reports)
                    diagnostic["status"] = "PASS"
                    diagnostic["dataset_completeness_claimed"] = False
        except (ExecutionDeadline, KeyboardInterrupt):
            diagnostic["reason"] = "execution_interrupted_original_ledger_preserved"
        except Exception:
            diagnostic["reason"] = "execution_failed_original_ledger_preserved"
        try:
            diagnostic["ledger"] = ledger_accounting(storage, identity)
        except Exception:
            diagnostic["status"] = "BLOCKED"
            diagnostic["ledger_status"] = "BLOCKED"
        (storage / "execution-diagnostics.json").write_bytes(acquisition.encode(diagnostic))
    finally:
        os.umask(previous_mask)
    return {"status": diagnostic["status"], "phase": mode,
            "reason": "private_diagnostics_retained", "synthetic": execution["mode"] == "rehearsal"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, default="rehearsal")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--storage", type=Path, required=True)
    parser.add_argument("--execution", type=Path, required=True)
    parser.add_argument("--approval", type=Path)
    args = parser.parse_args(argv)
    try:
        manifest, record = _json(args.manifest), _json(args.execution)
        approval = _json(args.approval) if args.approval else None
        if args.preflight_only:
            preflight(args.mode, manifest, args.storage, record, approval)
            result = {"status": "PASS", "phase": "preflight"}
        else:
            result = execute(args.mode, manifest, args.storage, record, approval)
    except (Exception, KeyboardInterrupt, ExecutionDeadline):
        result = {"status": "BLOCKED", "reason": "execution_preflight_or_storage_failed"}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
