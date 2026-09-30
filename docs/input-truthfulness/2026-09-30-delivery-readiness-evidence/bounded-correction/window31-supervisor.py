"""DRAFT: exactly one authorized PR96 stress comparison, never run on import.

Windows Job Object commit limits are established/read back before a suspended
child resumes. Parent wall watchdog covers imports, compression, optional TEST
key generation/encryption, hashes and reporting. This is not an OS firewall:
Python sockets/DNS are audit-blocked, and only pinned native age binaries may
be launched. No owner key, provider transport or reconciliation is used.

Do not execute until root approval. No fallback or second attempt is provided.
"""
from __future__ import annotations

import argparse
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

DOCS = [
    "https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information",
    "https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information",
    "https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw",
    "https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-assignprocesstojobobject",
    "https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters_ex",
]

WORK = Path(__file__).resolve().parent
OUT = WORK / "window31-comparison"
ORIGINAL = WORK / "codec-comparison-level12.py"
ORIGINAL_SHA = "1bc3892fd6ae1abc8cb2f1fafd5a055dae7324b3f9823dbf2128de2fd429839a"
MEMORY_LIMIT = 12 * 1024 ** 3
WALL_SECONDS = 600
LIMIT_FLAGS = 0x100 | 0x200 | 0x2000 | 0x8  # PROCESS_MEMORY, JOB_MEMORY, KILL_ON_CLOSE, ACTIVE_PROCESS.
AGE = WORK / "age-tools/age/age.exe"
KEYGEN = AGE.with_name("age-keygen.exe")
AGE_SHA = "2821a4ed191da07372acd302e5f6feae7a7985e285e1417765ebe74025af45f0"
KEYGEN_SHA = "1549c7049be32695594bedd09bbd352a94b6013a9d5c43364f3c6cd7a09ab61c"
ARCHIVE_NAME = "stress-zstd12-long31-canonical.tar.zstd"
RESULT_NAME = "stress-zstd12-long31-canonical.json"
KEY_NAME = "disposable-test-identity.txt"
ENV_NAMES = {"SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG", "LC_ALL", "NO_COLOR"}


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def now():
    return datetime.now(timezone.utc).isoformat()


class Refused(RuntimeError):
    pass


def require(condition, reason):
    if not condition:
        raise Refused(reason)


class BasicLimit(C.Structure):
    _fields_ = [("process_time", C.c_int64), ("job_time", C.c_int64), ("flags", W.DWORD),
                ("min_working_set", C.c_size_t), ("max_working_set", C.c_size_t),
                ("active_processes", W.DWORD), ("affinity", C.c_size_t),
                ("priority", W.DWORD), ("scheduling", W.DWORD)]


class IOCounters(C.Structure):
    _fields_ = [(name, C.c_uint64) for name in
                ("read_count", "write_count", "other_count", "read_bytes", "write_bytes", "other_bytes")]


class ExtendedLimit(C.Structure):
    _fields_ = [("basic", BasicLimit), ("io", IOCounters), ("process_memory", C.c_size_t),
                ("job_memory", C.c_size_t), ("peak_process_memory", C.c_size_t), ("peak_job_memory", C.c_size_t)]


class Accounting(C.Structure):
    _fields_ = [(name, C.c_int64) for name in ("user", "kernel", "period_user", "period_kernel")] + [
        (name, W.DWORD) for name in ("faults", "total_processes", "active_processes", "terminated_processes")]


class MemoryCounters(C.Structure):
    _fields_ = [("cb", W.DWORD), ("faults", W.DWORD)] + [(name, C.c_size_t) for name in
        ("peak_rss", "rss", "peak_paged", "paged", "peak_nonpaged", "nonpaged",
         "commit", "peak_commit", "private_commit")]


class MemoryStatus(C.Structure):
    _fields_ = [("length", W.DWORD), ("load", W.DWORD)] + [(name, C.c_uint64) for name in
        ("total_physical", "available_physical", "total_commit", "available_commit",
         "total_virtual", "available_virtual", "extended_virtual")]


class Startup(C.Structure):
    _fields_ = [("cb", W.DWORD), ("reserved", W.LPWSTR), ("desktop", W.LPWSTR), ("title", W.LPWSTR)] + [
        (name, W.DWORD) for name in ("x", "y", "xsize", "ysize", "xchars", "ychars", "fill", "flags")] + [
        ("show", W.WORD), ("reserved2_length", W.WORD), ("reserved2", C.c_void_p),
        ("stdin", W.HANDLE), ("stdout", W.HANDLE), ("stderr", W.HANDLE)]


class ProcessInformation(C.Structure):
    _fields_ = [("process", W.HANDLE), ("thread", W.HANDLE), ("pid", W.DWORD), ("tid", W.DWORD)]


def winapi():
    require(os.name == "nt" and C.sizeof(C.c_void_p) == 8, "windows_64bit_required")
    kernel = C.WinDLL("kernel32", use_last_error=True)
    signatures = {
        "CreateJobObjectW": ([C.c_void_p, W.LPCWSTR], W.HANDLE),
        "OpenJobObjectW": ([W.DWORD, W.BOOL, W.LPCWSTR], W.HANDLE),
        "SetInformationJobObject": ([W.HANDLE, C.c_int, C.c_void_p, W.DWORD], W.BOOL),
        "QueryInformationJobObject": ([W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.c_void_p], W.BOOL),
        "AssignProcessToJobObject": ([W.HANDLE, W.HANDLE], W.BOOL),
        "IsProcessInJob": ([W.HANDLE, W.HANDLE, C.POINTER(W.BOOL)], W.BOOL),
        "CreateProcessW": ([W.LPCWSTR, W.LPWSTR, C.c_void_p, C.c_void_p, W.BOOL, W.DWORD,
                             C.c_void_p, W.LPCWSTR, C.POINTER(Startup), C.POINTER(ProcessInformation)], W.BOOL),
        "ResumeThread": ([W.HANDLE], W.DWORD),
        "WaitForSingleObject": ([W.HANDLE, W.DWORD], W.DWORD),
        "TerminateJobObject": ([W.HANDLE, W.UINT], W.BOOL),
        "TerminateProcess": ([W.HANDLE, W.UINT], W.BOOL),
        "GetExitCodeProcess": ([W.HANDLE, C.POINTER(W.DWORD)], W.BOOL),
        "GetProcessTimes": ([W.HANDLE, C.POINTER(W.FILETIME), C.POINTER(W.FILETIME),
                              C.POINTER(W.FILETIME), C.POINTER(W.FILETIME)], W.BOOL),
        "GetCurrentProcess": ([], W.HANDLE),
        "CloseHandle": ([W.HANDLE], W.BOOL),
        "GlobalMemoryStatusEx": ([C.POINTER(MemoryStatus)], W.BOOL),
    }
    for name, (args, result) in signatures.items():
        function = getattr(kernel, name)
        function.argtypes, function.restype = args, result
    psapi = C.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [W.HANDLE, C.POINTER(MemoryCounters), W.DWORD]
    psapi.GetProcessMemoryInfo.restype = W.BOOL
    return kernel, psapi


def check(ok, reason):
    require(bool(ok), reason + "_win32_" + str(C.get_last_error()))


def job_limits(kernel, job):
    limits = ExtendedLimit()
    check(kernel.QueryInformationJobObject(job, 9, C.byref(limits), C.sizeof(limits), None), "job_readback")
    require(limits.basic.flags == LIMIT_FLAGS and limits.process_memory == MEMORY_LIMIT and
            limits.job_memory == MEMORY_LIMIT and limits.basic.active_processes == 2, "job_limit_readback_mismatch")
    return limits


def child():
    """Runs only under the already configured supervisor job; never standalone."""
    result = {"schema": "window31-child-v1", "status": "FAIL", "started_at": now(),
              "provider_requests": 0, "owner_key_access": "NOT RUN", "encryption": "NOT RUN"}
    key = OUT / KEY_NAME
    try:
        config = json.loads((OUT / "configuration.json").read_bytes())
        require(config["child_pid"] == os.getpid(), "child_pid_mismatch")
        kernel, _ = winapi()
        job = kernel.OpenJobObjectW(0x0004, False, config["job_name"])
        check(job, "child_open_job")
        try:
            inside = W.BOOL()
            check(kernel.IsProcessInJob(kernel.GetCurrentProcess(), job, C.byref(inside)), "child_query_job")
            require(inside.value, "child_not_in_required_job")
            job_limits(kernel, job)
        finally:
            kernel.CloseHandle(job)  # Only the parent retains the kill-on-close handle.
        require({name.upper() for name in os.environ} <= ENV_NAMES, "unexpected_child_environment")
        require(sha(OUT / "candidate.py") == config["candidate_sha256"], "candidate_source_changed")
        sys.path.insert(0, str(WORK / "codecdeps"))
        import zstandard as zstd
        import zstandard.backend_c as backend
        require(zstd.__version__ == "0.25.0" and zstd.ZSTD_VERSION == (1, 5, 7) and zstd.backend == "cext",
                "codec_identity_mismatch")
        result["codec_backend_binary_sha256"] = sha(backend.__file__)
        allowed_binary = None
        def audit(event, arguments):
            if event.startswith("socket.") or event in ("os.system", "os.posix_spawn", "os.spawn"):
                raise Refused("python_network_or_spawn_blocked")
            if event == "subprocess.Popen":
                require(allowed_binary is not None and str(arguments[0]) == str(allowed_binary), "unapproved_child_binary")
        sys.addaudithook(audit)
        import socket
        for operation in (lambda: socket.socket(), lambda: socket.getaddrinfo("example.invalid", 443)):
            try:
                operation()
            except Refused:
                pass
            else:
                raise Refused("network_negative_control_failed")
        result["network_control"] = "PASS: Python socket/DNS audit deny; native age offline commands only; no OS firewall claim"
        # No inherited standard handles: child opens its own bounded metadata log.
        original_output = sys.stdout, sys.stderr
        try:
            with (OUT / "child.stdout.txt").open("x", encoding="utf-8") as log:
                sys.stdout = sys.stderr = log
                sys.argv = [str(OUT / "candidate.py"), "compress", "--case", "stress", "--codec", "zstd"]
                source = (OUT / "candidate.py").read_bytes()
                exec(compile(source, str(OUT / "candidate.py"), "exec"),
                     {"__name__": "__main__", "__file__": str(OUT / "candidate.py")})
        finally:
            sys.stdout, sys.stderr = original_output
        trial = json.loads((OUT / RESULT_NAME).read_bytes())
        result["archive_comparison"] = trial
        require(trial["status"] == "PASS" and trial.get("source_hashes_verified_while_compressing") is True,
                "archive_comparison_failed")
        require(sha(AGE) == AGE_SHA and sha(KEYGEN) == KEYGEN_SHA, "age_binary_changed")
        def run(binary, arguments, **kwargs):
            nonlocal allowed_binary
            allowed_binary = binary
            try:
                completed = subprocess.run([str(binary), *map(str, arguments)], stdin=subprocess.DEVNULL,
                                           stderr=subprocess.DEVNULL, env=dict(os.environ), close_fds=True,
                                           creationflags=0x08000000, check=False, **kwargs)
                require(completed.returncode == 0, "test_age_operation_failed")
                return completed
            finally:
                allowed_binary = None
        run(KEYGEN, ["-o", key], stdout=subprocess.DEVNULL)
        os.chmod(key, 0o600)
        recipient = run(KEYGEN, ["-y", key], stdout=subprocess.PIPE).stdout.decode("ascii").strip()
        require(recipient.startswith("age1") and len(recipient) == 62, "unexpected_test_recipient")
        cipher = OUT / "test-only-comparison.age"
        with cipher.open("xb") as output:
            run(AGE, ["--encrypt", "--recipient", recipient, OUT / ARCHIVE_NAME], stdout=output)
        with cipher.open("rb") as encrypted:
            require(encrypted.read(22) == b"age-encryption.org/v1\n", "unexpected_ciphertext_header")
        result.update(encryption="PASS", ciphertext_bytes=cipher.stat().st_size, ciphertext_sha256=sha(cipher),
                      ciphertext_cap_bytes=200 * 1024 ** 2,
                      recipient_sha256=hashlib.sha256((recipient + "\n").encode("ascii")).hexdigest(),
                      comparison_only="Original fictional archive metadata unchanged; this is not a new execution/package receipt.")
        require(cipher.stat().st_size <= 200 * 1024 ** 2, "ciphertext_cap_exceeded")
        result["status"] = "PASS"
    except BaseException as error:
        result["reason"] = str(error) if isinstance(error, Refused) else type(error).__name__
    finally:
        if key.exists():
            key.unlink()
        result.update(completed_at=now(), disposable_test_identity_removed=not key.exists())
        write_json(OUT / "child-result.json", result)
    return 0 if result["status"] == "PASS" else 2


def supervisor():
    require(not OUT.exists(), "single_attempt_directory_already_exists")
    for path in (WORK, *WORK.parents):
        require(not (path / ".git").exists() and not path.is_symlink() and not path.is_junction(), "unsafe_output_parent")
    OUT.mkdir(mode=0o700)
    report = {"schema": "historical-window31-supervisor-v1", "status": "BLOCKED", "started_at": now(),
              "synthetic_only": True, "provider_requests": 0, "owner_key_access": "NOT RUN",
              "process_commit_limit_bytes": MEMORY_LIMIT, "job_commit_limit_bytes": MEMORY_LIMIT,
              "wall_limit_seconds": WALL_SECONDS, "active_process_limit": 2,
              "memory_limit_semantics": "Hard Windows committed-memory limits, not a sampled RSS ceiling or working-set trimming.",
              "network_scope": "Python socket/DNS audit deny; pinned native age offline commands; not OS firewall isolation",
              "supervisor_sha256": sha(__file__), "compression_started": False, "official_tool_documentation": DOCS}
    kernel = psapi = job = None
    process = ProcessInformation()
    resumed = assigned = False
    started = None
    peak_rss = peak_commit = peak_scratch = 0
    try:
        kernel, psapi = winapi()
        require(sha(ORIGINAL) == ORIGINAL_SHA, "original_comparison_changed")
        require(sha(AGE) == AGE_SHA and sha(KEYGEN) == KEYGEN_SHA, "age_binary_identity_mismatch")
        host = MemoryStatus()
        host.length = C.sizeof(host)
        check(kernel.GlobalMemoryStatusEx(C.byref(host)), "host_memory_query")
        report["host_before"] = {name: getattr(host, name) for name in
                                ("total_physical", "available_physical", "total_commit", "available_commit")}
        require(host.available_commit >= MEMORY_LIMIT, "insufficient_available_host_commit")
        require(shutil.disk_usage(OUT).free >= 2 * 1024 ** 3, "insufficient_output_disk")
        original = ORIGINAL.read_text(encoding="utf-8")
        replacements = {"window_log=30": "window_log=31", "window_bytes=1024**3": "window_bytes=2*1024**3",
                        '"zstd12-long30"': '"zstd12-long31"',
                        "WORK = Path(__file__).resolve().parent": "WORK = Path(" + repr(str(WORK)) + ")",
                        'OUT = WORK / "synthetic-codec-comparison"': "OUT = Path(" + repr(str(OUT)) + ")"}
        candidate = original
        for before, after in replacements.items():
            require(candidate.count(before) == 1, "comparison_patch_not_unique")
            candidate = candidate.replace(before, after)
        anchor = '    result["tar_archive_bytes"] = tar_bytes\n'
        require(candidate.count(anchor) == 1, "canonical_assertion_anchor_mismatch")
        candidate = candidate.replace(anchor, anchor + '''    assert len(index_raw) == 67168
    assert hashlib.sha256(index_raw).hexdigest() == "fc7cb4d2b61d3351179ee1c8e86b76a24546fb24d8b20385d1963031bf8a2fdc"
    assert payload == 1866624285 and tar_bytes == 1866926080
    result["canonical_index_sha256"] = hashlib.sha256(index_raw).hexdigest()
''')
        (OUT / "candidate.py").write_text(candidate, encoding="utf-8", newline="\n")
        shutil.copyfile(WORK / "synthetic-codec-comparison/original-member-verification.json",
                        OUT / "original-member-verification.json")
        # Direct underlying interpreter avoids the Windows venv launcher's extra
        # process. -I -S excludes user/site startup code; only the pinned codec
        # directory is inserted explicitly in the child.
        python = Path(sys._base_executable).resolve(strict=True)
        report.update(python_binary_sha256=sha(python), parent_python=sys.version,
                      original_script_sha256=ORIGINAL_SHA, candidate_script_sha256=sha(OUT / "candidate.py"),
                      age_binary_sha256=AGE_SHA, age_keygen_binary_sha256=KEYGEN_SHA)
        job_name = "Local\\SpicyStock-Window31-" + uuid.uuid4().hex
        C.set_last_error(0)
        job = kernel.CreateJobObjectW(None, job_name)
        check(job, "create_job")
        require(C.get_last_error() != 183, "job_name_already_exists")
        limits = ExtendedLimit()
        limits.basic.flags, limits.basic.active_processes = LIMIT_FLAGS, 2
        limits.process_memory = limits.job_memory = MEMORY_LIMIT
        check(kernel.SetInformationJobObject(job, 9, C.byref(limits), C.sizeof(limits)), "set_hard_memory_limits")
        job_limits(kernel, job)
        report["hard_limit_readback"] = "PASS"
        environment = {k: v for k, v in os.environ.items() if k.upper() in ENV_NAMES}
        environment.update(TEMP=str(OUT), TMP=str(OUT), NO_COLOR="1")
        require(any(k.upper() == "SYSTEMROOT" for k in environment), "systemroot_missing")
        block = C.create_unicode_buffer("\0".join(k + "=" + v for k, v in sorted(environment.items(), key=lambda x: x[0].upper())) + "\0\0")
        command = C.create_unicode_buffer(subprocess.list2cmdline([str(python), "-I", "-S", "-B", "-X", "utf8",
                                                                  str(Path(__file__).resolve()), "--child"]))
        startup = Startup()
        startup.cb = C.sizeof(startup)
        # FALSE inheritance and hidden, suspended startup: no inherited job,
        # console, token, pipe or unrelated file handle is passed to the child.
        check(kernel.CreateProcessW(str(python), command, None, None, False,
                                    0x00000004 | 0x00000400 | 0x08000000, block, str(WORK),
                                    C.byref(startup), C.byref(process)), "create_suspended_child")
        check(kernel.AssignProcessToJobObject(job, process.process), "assign_suspended_child")
        assigned = True
        inside = W.BOOL()
        check(kernel.IsProcessInJob(process.process, job, C.byref(inside)), "verify_child_assignment")
        require(inside.value, "child_assignment_missing")
        job_limits(kernel, job)
        write_json(OUT / "configuration.json", {"job_name": job_name, "child_pid": process.pid,
                                               "candidate_sha256": report["candidate_script_sha256"]})
        report.update(child_pid=process.pid, child_assignment_before_resume="PASS", environment_names=sorted(environment))
        write_json(OUT / "supervisor-result.json", report)
        started = time.monotonic()
        require(kernel.ResumeThread(process.thread) == 1, "resume_child_failed")
        resumed = True
        report["compression_started"] = True
        while True:
            sample = MemoryCounters()
            sample.cb = C.sizeof(sample)
            if psapi.GetProcessMemoryInfo(process.process, C.byref(sample), C.sizeof(sample)):
                peak_rss, peak_commit = max(peak_rss, sample.peak_rss), max(peak_commit, sample.peak_commit)
                if peak_rss > MEMORY_LIMIT:
                    check(kernel.TerminateJobObject(job, 126), "terminate_rss_limit_job")
                    raise Refused("observed_rss_limit_exceeded")
            peak_scratch = max(peak_scratch, sum(p.stat().st_size for p in OUT.iterdir() if p.is_file()))
            elapsed = time.monotonic() - started
            state = kernel.WaitForSingleObject(process.process, 0)
            require(state != 0xFFFFFFFF, "wait_process_failed")
            if state == 0:
                break
            if elapsed >= WALL_SECONDS:
                check(kernel.TerminateJobObject(job, 124), "terminate_timeout_job")
                raise Refused("hard_parent_600_second_timeout")
            state = kernel.WaitForSingleObject(process.process, min(100, max(1, int((WALL_SECONDS - elapsed) * 1000))))
            require(state != 0xFFFFFFFF, "wait_process_failed")
        code = W.DWORD()
        check(kernel.GetExitCodeProcess(process.process, C.byref(code)), "child_exit_code")
        report["child_exit_code"] = code.value
        child_result = json.loads((OUT / "child-result.json").read_bytes())
        report["child_result"] = child_result
        require(code.value == 0 and child_result["status"] == "PASS", "bounded_child_comparison_failed")
        require(time.monotonic() - started <= WALL_SECONDS, "parent_elapsed_limit_exceeded")
        report["status"] = "PASS"
    except BaseException as error:
        report["status"] = "FAIL" if resumed else "BLOCKED"
        report["reason"] = str(error) if isinstance(error, Refused) else type(error).__name__
    finally:
        if process.process and kernel:
            if kernel.WaitForSingleObject(process.process, 0) != 0:
                if assigned:
                    kernel.TerminateJobObject(job, 125)
                else:
                    kernel.TerminateProcess(process.process, 125)
                kernel.WaitForSingleObject(process.process, 5000)
            if job:
                limits, accounting = ExtendedLimit(), Accounting()
                if kernel.QueryInformationJobObject(job, 9, C.byref(limits), C.sizeof(limits), None):
                    report.update(job_peak_process_commit_bytes=limits.peak_process_memory,
                                  job_peak_aggregate_commit_bytes=limits.peak_job_memory)
                    if max(limits.peak_process_memory, limits.peak_job_memory) > MEMORY_LIMIT:
                        report.update(status="FAIL", reason="hard_commit_peak_limit_exceeded")
                else:
                    report.update(status="FAIL", reason="final_job_memory_accounting_unavailable")
                if kernel.QueryInformationJobObject(job, 1, C.byref(accounting), C.sizeof(accounting), None):
                    report.update(job_user_cpu_seconds=accounting.user / 10000000,
                                  job_kernel_cpu_seconds=accounting.kernel / 10000000,
                                  job_total_processes=accounting.total_processes)
                else:
                    report.update(status="FAIL", reason="final_job_cpu_accounting_unavailable")
            sample = MemoryCounters()
            sample.cb = C.sizeof(sample)
            final_memory = bool(psapi.GetProcessMemoryInfo(process.process, C.byref(sample), C.sizeof(sample)))
            if final_memory:
                peak_rss, peak_commit = max(peak_rss, sample.peak_rss), max(peak_commit, sample.peak_commit)
            if peak_rss > MEMORY_LIMIT:
                report.update(status="FAIL", reason="final_rss_limit_exceeded")
            report.update(python_peak_rss_bytes=peak_rss, python_peak_commit_bytes=peak_commit,
                          final_process_memory_query_succeeded=final_memory,
                          rss_scope="Native Python high-water counters; final-query availability recorded. Job peaks are exact committed-memory accounting, not combined RSS.")
        # Fixed TEST-only path under a fresh owned directory, even after hard kill.
        key = OUT / KEY_NAME
        if key.exists():
            key.unlink()
        report.update(disposable_test_identity_removed=not key.exists(), completed_at=now(),
                      parent_wall_seconds=None if started is None else time.monotonic() - started,
                      sampled_peak_output_bytes=peak_scratch,
                      output_bytes_at_completion=sum(p.stat().st_size for p in OUT.iterdir() if p.is_file()))
        write_json(OUT / "supervisor-result.json", report)
        if kernel:
            for handle in (process.thread, process.process, job):
                if handle:
                    kernel.CloseHandle(handle)
    print(json.dumps({"status": report["status"], "reason": report.get("reason"), "receipt": str(OUT / "supervisor-result.json")}))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-authorized-once", action="store_true")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    arguments = parser.parse_args()
    if arguments.child:
        raise SystemExit(child())
    if not arguments.execute_authorized_once:
        parser.error("draft only; explicit root approval and --execute-authorized-once are required")
    raise SystemExit(supervisor())
