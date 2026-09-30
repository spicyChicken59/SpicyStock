"""Full frozen-shape synthetic compaction benchmark; never a workflow release.

Only invented decimal rows are supplied to the actual Acquisition transport
boundary. The CLI has no provider/key/manifest input and generates a disposable
test-only age identity. Raw rows and recovered artifacts stay outside Git.
Run central and stress in separate fresh processes/workspaces, once per revision.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
from datetime import datetime, timezone
from decimal import Decimal
import gzip
import hashlib
import json
import math
from importlib.metadata import version
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import historical_acquisition as acquisition
from tools import historical_execution_guard as guard
from tools import historical_package as package
from tools import historical_reconcile as reconciliation
from tools.historical_execution import ledger_accounting
from tools.historical_reconcile import network_blocked, reconcile

MANIFEST = ROOT / "docs/input-truthfulness/2026-09-28-historical-input-evidence/acquisition-manifest.json"
SEED = "spicystock-compaction-full-shape-v1"
CASES = ("central", "stress")
FROZEN_ROWS = 2_753_568
MINIMUM_FREE_DISK = 12 * 1024 ** 3
SOURCE_FILES = ("tools/historical_projection_benchmark.py", "tools/historical_acquisition.py",
                "tools/historical_normalization.py", "tools/historical_reconcile.py", "tools/historical_breadth_reference.py",
                "tools/historical_package.py", "tools/historical_execution.py", "tools/historical_execution_guard.py",
                "src/breadth.py", "src/quality.py", "src/scans.py", "src/sessions.py", "tools/requirements-historical.txt")


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def shape(manifest):
    queries = [acquisition.resolved_query(manifest, q["id"]) for q in manifest["queries"]]
    bulk = [q for q in queries if q["scope"] == "bulk"]
    probe = [q for q in queries if q["scope"] == "probe"]
    return {"canonical_batches": len(bulk), "sessions_per_bulk_query": sorted({len(q["required_sessions"]) for q in bulk}),
            "bulk_rows": sum(len(q["symbols"]) * len(q["required_sessions"]) for q in bulk),
            "probe_rows": sum(len(q["symbols"]) * len(q["required_sessions"]) for q in probe),
            "filled_page_requests": sum(math.ceil(len(q["symbols"]) * len(q["required_sessions"]) / q["limit"]) for q in queries)}


def require_full_shape(manifest):
    require(acquisition.validate_manifest(manifest) == guard.MANIFEST, "frozen_manifest_required")
    require(shape(manifest) == {"canonical_batches": 96, "sessions_per_bulk_query": [288],
                               "bulk_rows": FROZEN_ROWS, "probe_rows": 2, "filled_page_requests": 289}, "full_frozen_shape_required")


def decimal_fields(case, symbol, session, seed=SEED):
    """Versioned deterministic scenarios, not a model fitted to provider bars.

    Central: varied cent OHLC around a symbol-specific level, integer volume.
    Stress: longer 9-place OHLC and 6-place fractional volume; last digits force
    a factor of five in every decimal denominator, hence all five are inexact.
    Hash input is seed/symbol/date, so overlapping queries retain equal values.
    """
    require(case in CASES, "unknown_synthetic_case")
    token = hashlib.sha256((seed + ":" + symbol + ":" + session).encode()).digest()
    base = 2000 + int.from_bytes(hashlib.sha256((seed + symbol).encode()).digest()[:4], "big") % 18000
    day = datetime.fromisoformat(session).toordinal()
    opening = base + (day % 288) * 3 + token[0] % 19
    closing = opening + token[1] % 41 - 20
    high, low = max(opening, closing) + 10 + token[2] % 80, min(opening, closing) - 10 - token[3] % 80
    prices = (opening, high, low, closing)
    if case == "central":
        result = [f"{n // 100}.{n % 100:02d}" for n in prices]
        result.append(str(100000 + int.from_bytes(token[4:8], "big") % 9_000_000))
    else:
        # Preserve OHLC order with < one-cent perturbations; all final digits 1.
        result = [f"{n // 100}.{n % 100:02d}{int.from_bytes(token[8+i*3:11+i*3], 'big') % 1_000_000:06d}1"
                  for i, n in enumerate(prices)]
        result.append(f"{100_000_000 + int.from_bytes(token[4:8], 'big') % 900_000_000}.{int.from_bytes(token[20:23], 'big') % 100_000:05d}1")
    return result


class SyntheticTransport:
    fields = ("start", "end", "feed", "timeframe", "adjustment", "currency", "asof", "limit", "sort", "symbols")

    def __init__(self, manifest, case, seed=SEED):
        self.case, self.seed = case, seed
        self.calls, self.rows, self.bytes = 0, 0, 0
        self.now = datetime(2026, 9, 28, tzinfo=timezone.utc).timestamp()
        self.queries = {}
        self.timestamps = {}
        for item in manifest["queries"]:
            q = acquisition.resolved_query(manifest, item["id"])
            key = tuple(",".join(q[k]) if k == "symbols" else q[k] for k in self.fields)
            require(key not in self.queries, "synthetic_query_collision")
            self.queries[key] = q
            for day in q["required_sessions"]:
                self.timestamps[day] = datetime.fromisoformat(day).replace(tzinfo=acquisition.NY).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds

    def __call__(self, params, byte_limit):
        q = self.queries[tuple(params[k] for k in self.fields)]
        days = q["required_sessions"]
        start = int(params.get("page_token", "0"))
        total = len(days) * len(q["symbols"])
        stop = min(start + q["limit"], total)
        require(0 <= start < total, "synthetic_token_out_of_range")
        bars = {}
        for ordinal in range(start, stop):
            symbol, day = q["symbols"][ordinal // len(days)], days[ordinal % len(days)]
            values = decimal_fields(self.case, symbol, day, self.seed)
            trade_count = str(max(1, int(Decimal(values[4])) // 1000))
            vwap = str((Decimal(values[0]) + Decimal(values[3])) / 2)
            # Explicit numeric lexemes avoid rounding long decimals through float.
            row = ('{"t":' + json.dumps(self.timestamps[day]) + ',' + ','.join('"' + k + '":' + v for k, v in zip("ohlcv", values)) +
                   ',"n":' + trade_count + ',"vw":' + vwap + '}')
            bars.setdefault(symbol, []).append(row)
        body = ('{"bars":{' + ','.join(json.dumps(s) + ':[' + ','.join(rows) + ']' for s, rows in bars.items()) +
                '},"next_page_token":' + (json.dumps(str(stop)) if stop < total else 'null') + '}\n').encode()
        require(len(body) <= byte_limit, "synthetic_page_exceeds_original_cap")
        self.calls += 1
        self.rows += stop - start
        self.bytes += len(body)
        return acquisition.HTTPResult(200, {"content-type": "application/json"}, body)


def platform_memory(process_handle=None):
    if os.name != "nt":
        import resource
        multiplier = 1 if sys.platform == "darwin" else 1024
        return {"process_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * multiplier,
                "measurement": "native getrusage ru_maxrss"}
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    *[(n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    require(bool(psapi.GetProcessMemoryInfo(process_handle or kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb)), "native_memory_counter_failed")
    return {"process_peak_rss_bytes": counters.PeakWorkingSetSize, "process_peak_commit_bytes": counters.PeakPagefileUsage,
            "measurement": "native Windows GetProcessMemoryInfo high-water counters"}


def memory_summary(process_metrics, package_metrics):
    """Do not interpret an unmeasured child high water as zero usage."""
    result = dict(process_metrics)
    child_peak = package_metrics.get("age_process_peak_rss_bytes")
    result["python_plus_age_peak_rss_conservative_sum_bytes"] = (
        process_metrics["process_peak_rss_bytes"] + child_peak if child_peak is not None else None)
    result["scope"] = (
        "Python process high water; age encryption/decryption high water separately; their sum is conservative, not a simultaneous peak"
        if child_peak is not None else
        "Python process high water only; age child high water was not measured; combined peak unavailable")
    return result


def memory_headroom():
    if os.name != "nt":
        return {"measurement": "NOT RUN: Windows capacity counters unavailable"}
    from ctypes import wintypes
    class Status(ctypes.Structure):
        _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD),
                    *[(n, ctypes.c_ulonglong) for n in ("physical_total", "physical_available", "commit_total", "commit_available",
                                                       "virtual_total", "virtual_available", "extended")]]
    status = Status()
    status.length = ctypes.sizeof(status)
    require(bool(ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))), "memory_capacity_counter_failed")
    return {"physical_total_bytes": status.physical_total, "physical_available_bytes": status.physical_available,
            "commit_limit_bytes": status.commit_total, "commit_available_bytes": status.commit_available,
            "measurement": "native Windows GlobalMemoryStatusEx; commit values are ullTotalPageFile/ullAvailPageFile"}


class Monitor:
    def __init__(self, root):
        self.root, self.stop = root, threading.Event()
        self.peak_scratch = 0
        self.thread = threading.Thread(target=self.sample_loop, daemon=True)

    def sample(self):
        total = 0
        for path in self.root.rglob("*"):
            try:
                if path.is_file():
                    total += path.stat().st_size
            except FileNotFoundError:
                pass  # Package temporaries can disappear between these reads.
        self.peak_scratch = max(self.peak_scratch, total)

    def sample_loop(self):
        while not self.stop.wait(0.25):
            self.sample()

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join()
        self.sample()


def snapshot(root):
    return {p.relative_to(root).as_posix(): {"bytes": p.stat().st_size, "sha256": package._hash(p)}
            for p in root.rglob("*") if p.is_file() and p.name != "acquisition.lock"}


def same_bytes(first, second):
    with first.open("rb") as left, second.open("rb") as right:
        while True:
            a, b = left.read(1024 ** 2), right.read(1024 ** 2)
            if a != b:
                return False
            if not a:
                return True


def contains_bytes(path, needle):
    with path.open("rb") as stream:
        tail = b""
        for block in iter(lambda: stream.read(1024 ** 2), b""):
            if needle in tail + block:
                return True
            tail = block[-len(needle):]
    return False


@contextmanager
def measure_archive(metrics, monitor):
    """Transparent instrumentation of the actual package; never replaces age."""
    original, original_temp, original_popen = package._age, package.tempfile.TemporaryDirectory, subprocess.Popen
    def inspect(archive):
        if archive.is_file() and "gzip_archive_bytes" not in metrics:
            started = time.perf_counter()
            metrics["gzip_archive_bytes"] = archive.stat().st_size
            metrics["gzip_archive_sha256"] = package._hash(archive)
            with gzip.open(archive, "rb") as stream:
                metrics["tar_archive_bytes"] = sum(len(b) for b in iter(lambda: stream.read(1024 ** 2), b""))
            with tarfile.open(archive, "r:gz") as tar:
                first = tar.next()
                require(first.name == "_package/index.json", "benchmark_index_missing")
                metrics["index_bytes"] = first.size
                index = json.load(tar.extractfile(first))
            payload = sum(e["bytes"] for e in index["members"]) + first.size
            metrics.update(expanded_payload_bytes=payload, indexed_member_count=len(index["members"]),
                           tar_headers_and_padding_bytes=metrics["tar_archive_bytes"] - payload)
            monitor.sample()
            metrics["archive_measurement_seconds"] = round(time.perf_counter() - started, 6)

    class ObservedTemporaryDirectory(original_temp):
        def __exit__(self, *args):
            try:
                inspect(Path(self.name) / "evidence.tar.gz")
            finally:
                super().__exit__(*args)

    class ObservedPopen(original_popen):
        def wait(self, *args, **kwargs):
            result = super().wait(*args, **kwargs)
            if os.name == "nt":
                metrics["age_process_peak_rss_bytes"] = max(metrics.get("age_process_peak_rss_bytes", 0),
                                                            platform_memory(self._handle)["process_peak_rss_bytes"])
            return result

    def measured(binary, arguments, output, **kwargs):
        if arguments[0] == "--encrypt":
            inspect(Path(arguments[-1]))
        return original(binary, arguments, output, **kwargs)
    package._age = measured
    package.tempfile.TemporaryDirectory = ObservedTemporaryDirectory
    subprocess.Popen = ObservedPopen
    try:
        yield
    finally:
        package._age = original
        package.tempfile.TemporaryDirectory = original_temp
        subprocess.Popen = original_popen


def test_identity(age_binary, workspace):
    identity = workspace / "DISPOSABLE-SYNTHETIC-TEST-IDENTITY.txt"
    keygen = age_binary.with_name("age-keygen" + age_binary.suffix)
    result = subprocess.run([str(keygen), "-o", str(identity)], stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=package._age_environment(), check=False)
    require(result.returncode == 0, "synthetic_identity_generation_failed")
    if os.name != "nt":
        identity.chmod(0o600)
    public = subprocess.run([str(keygen), "-y", str(identity)], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=package._age_environment(), check=False)
    require(public.returncode == 0, "synthetic_recipient_failed")
    return identity, public.stdout.decode("ascii").strip()


@contextmanager
def measure_projections(metrics):
    """Count the actual compact return values without retaining extra rows."""
    original = reconciliation.frames_for_replay
    metrics.update(query_count=0, replayable_rows=0, conversion_count=0, field_mask_counts={})
    def observed(*args, **kwargs):
        frames, projection = original(*args, **kwargs)
        require(projection["schema"] == "historical-float64-projection-v2", "compact_projection_required")
        metrics["query_count"] += 1
        metrics["replayable_rows"] += len(projection["rows"])
        metrics["conversion_count"] += projection["conversion_count"]
        for _, mask, _ in projection["rows"]:
            key = str(mask)
            metrics["field_mask_counts"][key] = metrics["field_mask_counts"].get(key, 0) + 1
        return frames, projection
    reconciliation.frames_for_replay = observed
    try:
        yield
    finally:
        reconciliation.frames_for_replay = original
        count = metrics["replayable_rows"] * 5
        metrics["inexact_fraction_of_all_five_fields"] = metrics["conversion_count"] / count if count else None


def run_case(manifest, case, workspace, age_binary, *, full_scale=True):
    require(case in CASES, "unknown_synthetic_case")
    if full_scale:
        require_full_shape(manifest)
    identity = acquisition.validate_manifest(manifest)
    workspace = package._private_path(workspace, exists=False)
    require(not workspace.exists(), "benchmark_workspace_must_be_fresh")
    package._private_path(workspace.parent)
    free = shutil.disk_usage(workspace.parent).free
    require(free >= MINIMUM_FREE_DISK, "benchmark_disk_headroom_unestablished")
    capacity = memory_headroom()
    if full_scale and os.name == "nt":
        require(capacity["commit_available_bytes"] >= 5 * 1024 ** 3, "benchmark_commit_headroom_below_5GiB")
    previous_mask = os.umask(0o077)
    workspace.mkdir(mode=0o700)
    storage = workspace / "synthetic-storage"
    key_path = None
    phase, started = "setup", time.perf_counter()
    report = {"schema": "historical-compaction-benchmark-v1", "case": case, "seed": SEED,
              "generator_assumptions": {"raw_fields": ["t", "o", "h", "l", "c", "v", "n", "vw"],
                  "central": "2-place varied OHLC cents, integer volume, integer trade count, midpoint VWAP",
                  "stress": "9-place varied OHLC, 6-place fractional volume; all five projected fields inexact; integer trade count and midpoint VWAP",
                  "scope": "invented deterministic scenarios, not a promise of provider precision or compression"},
              "synthetic_only": True, "provider_requests": 0, "workflow_execution": "NOT RUN", "owner_key_access": "NOT RUN",
              "full_frozen_shape": full_scale, "shape": shape(manifest), "manifest_sha256": identity,
              "status": "BLOCKED", "started_at": datetime.now(timezone.utc).isoformat(), "free_disk_before_bytes": free,
              "memory_before": capacity, "runtime_scope": f"local {sys.platform} host; timing includes existing host load; not a hosted-runner timing guarantee",
              "python": sys.version, "dependencies": {name: version(name) for name in ("pandas", "numpy", "exchange_calendars")},
              "age_sha256": package._hash(age_binary),
              "phases_seconds": {}, "package_measurements": {},
              "source_sha256": {name: package._hash(ROOT / name) for name in SOURCE_FILES},
              "limits_bytes": {"raw": 1024 ** 3, "expanded": package.MAX_PLAINTEXT_BYTES,
                               "gzip": package.MAX_ARCHIVE_BYTES, "ciphertext": package.MAX_CIPHERTEXT_BYTES}}
    monitor = Monitor(workspace)
    def step(name):
        nonlocal phase, phase_start
        report["phases_seconds"][phase] = round(time.perf_counter() - phase_start, 6)
        phase, phase_start = name, time.perf_counter()
        print(json.dumps({"case": case, "phase": phase, "status": "NOT RUN", "action": "starting"}), flush=True)
    phase_start = started
    try:
        with monitor, network_blocked():
            transport = SyntheticTransport(manifest, case)
            approval = {"assignment_id": acquisition.ASSIGNMENT, "manifest_sha256": identity,
                        "storage_root": str(storage), "zero_additional_cost": True,
                        "cost_basis": "offline invented benchmark bytes; no provider usage", "sip_daily_entitlement_basis": "synthetic benchmark only",
                        "non_public_storage": True, "retention_rights_basis": "invented synthetic benchmark",
                        "reviewer_retrieval_path": "local disposable synthetic benchmark", "approved_by": "synthetic benchmark fixture",
                        "provider_requests_per_minute": 20}
            step("synthetic_acquisition")
            acquisition.Acquisition(manifest, approval, storage, transport=transport, clock=transport.clock, sleep=transport.sleep).run_all()
            report.update(synthetic_transport_calls=transport.calls, generated_rows=transport.rows,
                          raw_response_bytes=transport.bytes, simulated_rate_clock_seconds=transport.now - datetime(2026, 9, 28, tzinfo=timezone.utc).timestamp(),
                          ledger_accounting=ledger_accounting(storage, identity))
            require(transport.rows == report["shape"]["bulk_rows"] + report["shape"]["probe_rows"], "benchmark_row_coverage_failed")
            require(transport.calls == report["shape"]["filled_page_requests"], "benchmark_page_coverage_failed")
            results = []
            report["projection_measurements"] = {}
            with measure_projections(report["projection_measurements"]):
                for session in sorted(manifest["populations"]):
                    step("reconcile_" + session)
                    result = reconcile(manifest, storage, session)
                    require(result["complete_required_input_windows"] and result["same_input_formula_status"] == "PASS", "benchmark_arithmetic_or_coverage_failed")
                    results.append(result)
            require(report["projection_measurements"]["replayable_rows"] == report["shape"]["bulk_rows"], "projection_row_coverage_failed")
            require(case != "stress" or report["projection_measurements"]["conversion_count"] == report["shape"]["bulk_rows"] * 5,
                    "stress_requires_all_five_fields_inexact")
            require(not full_scale or contains_bytes(
                    storage / ("reconciliation-" + sorted(manifest["populations"])[0] + ".json"),
                    b'"historical-float64-projection-v2"'),
                    "compact_projection_required_for_full_benchmark")
            report["reconciliation"] = results
            (storage / "execution-diagnostics.json").write_bytes(acquisition.encode({"schema": "synthetic-compaction-benchmark-diagnostics-v1",
                "status": "PASS", "case": case, "synthetic_only": True, "provider_requests": 0, "reconciliation": results}))
            before = snapshot(storage)
            (workspace / "synthetic-member-inventory.json").write_bytes(acquisition.encode(before))
            report["serialized_member_bytes"] = {"raw_pages": sum(v["bytes"] for n, v in before.items() if n.startswith("pages/")),
                "query_manifests": sum(v["bytes"] for n, v in before.items() if n.endswith("-manifest.json")),
                **{n: v["bytes"] for n, v in before.items() if not n.startswith("pages/") and not n.endswith("-manifest.json")}}
            report["source_member_payload_bytes"] = sum(v["bytes"] for v in before.values())
            report["source_member_inventory_sha256"] = hashlib.sha256(acquisition.encode(before)).hexdigest()
            step("package")
            key_path, recipient = test_identity(age_binary, workspace)
            metadata = {"repository": package.REPOSITORY, "repository_id": guard.REPOSITORY_ID,
                        "assignment_id": acquisition.ASSIGNMENT, "manifest_sha256": identity,
                        "workflow_id": guard.WORKFLOW_ID, "workflow_path": guard.WORKFLOW,
                        "recipient_sha256": package.recipient_fingerprint(recipient), "run_id": 123456, "run_number": 4,
                        "run_attempt": 1, "assignment_phase": 1, "mode": "rehearsal", "checkout_sha": "a" * 40,
                        "workflow_sha": "b" * 40, "implementation_pr": 123, "readiness_comment_id": 654321,
                        "recovery_contract_sha256": guard.RECOVERY_CONTRACT_SHA256, "status": "PASS"}
            report["identity_basis"] = "Fictional test fixture execution identifiers; disposable generated test-only recipient; not an Actions run or readiness"
            with measure_archive(report["package_measurements"], monitor):
                receipt = package.package_evidence(storage, manifest, workspace / "delivery", age_binary=age_binary,
                    recipient=recipient, execution=metadata, diagnostics={"synthetic_only": True, "case": case})
            report["package_measurements"].update(ciphertext_bytes=receipt["ciphertext_bytes"], ciphertext_sha256=receipt["ciphertext_sha256"],
                                                   receipt_bytes=(workspace / "delivery/receipt.json").stat().st_size)
            step("recover")
            recovered = workspace / "recovered"
            with measure_archive(report["package_measurements"], monitor):
                index = package.recover_package(workspace / "delivery" / package.CIPHERTEXT_NAME, receipt, recovered,
                           age_binary=age_binary, identity=key_path, manifest=manifest, expected_execution=metadata)
            require(snapshot(storage) == before, "benchmark_source_changed")
            require(all((recovered / n).stat().st_size == row["bytes"] and package._hash(recovered / n) == row["sha256"] and same_bytes(storage / n, recovered / n)
                        for n, row in before.items()), "benchmark_recovery_changed_member")
            require(ledger_accounting(recovered, identity) == report["ledger_accounting"], "benchmark_recovery_changed_accounting")
            report.update(status="PASS", recovered_original_member_count=len(before), recovered_index_member_count=len(index["members"]),
                          all_original_members_byte_identical=True, ledger_accounting_unchanged=True)
    except Exception as error:
        report.update(status="FAIL", stopped_at_phase=phase, reason=type(error).__name__)
        if isinstance(error, (package.PackageError, acquisition.AcquisitionError, ValueError)):
            report["reason"] = str(error)
    finally:
        os.umask(previous_mask)
        report["phases_seconds"][phase] = round(time.perf_counter() - phase_start, 6)
        report.update(runtime_seconds=round(time.perf_counter() - started, 6), completed_at=datetime.now(timezone.utc).isoformat(),
                      memory=memory_summary(platform_memory(), report["package_measurements"]), peak_scratch_bytes_sampled=monitor.peak_scratch,
                      scratch_measurement="250ms recursive file-size sampling plus packaging checkpoint; sampled lower bound, excludes filesystem allocation overhead")
        report["source_unchanged_through_run"] = all(package._hash(ROOT / name) == digest for name, digest in report["source_sha256"].items())
        if not report["source_unchanged_through_run"]:
            report.update(status="FAIL", reason="benchmark_source_changed_during_run")
        if key_path and key_path.is_file():
            key_path.unlink()
        report["disposable_test_identity_removed"] = key_path is not None and not key_path.exists()
        (workspace / "benchmark-result.json").write_bytes(acquisition.encode(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--age", type=Path, required=True)
    args = parser.parse_args()
    require(args.workspace.name.startswith("synthetic-compaction-"), "explicit_synthetic_workspace_name_required")
    require(not any(os.environ.get(n) for n in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY", "ANTHROPIC_API_KEY")), "provider_environment_forbidden")
    report = run_case(json.loads(MANIFEST.read_bytes()), args.case, args.workspace, args.age.absolute())
    print(json.dumps({"status": report["status"], "case": args.case, "runtime_seconds": report["runtime_seconds"]}), flush=True)
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
