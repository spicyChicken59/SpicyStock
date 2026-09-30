"""Bounded stage accounting for synthetic historical runtime measurements.

Instrumentation changes no returned value or persisted scientific object. CPU
and wall totals distinguish inclusive from exclusive time; sampled peaks are
lower bounds, not allocation counts. No provider or credential interface exists.
"""
from contextlib import contextmanager
from functools import wraps
import json
import os
from pathlib import Path
import signal
import threading
import time
from types import SimpleNamespace


class RuntimeDeadline(BaseException):
    """Leave ordinary malformed-data handlers; only the benchmark owns this stop."""


@contextmanager
def deadline(name, seconds):
    """Interrupt Linux work before the unchanged workflow hard timeout.

    Python handles SIGALRM at an interpreter boundary; a long native call can
    delay delivery. On platforms without setitimer only a post-return check is
    available, which is explicitly not representative enforcement.
    """
    started = time.monotonic()
    supported = hasattr(signal, "setitimer")
    fired = False
    if supported:
        previous = signal.getsignal(signal.SIGALRM)
        timer = signal.getitimer(signal.ITIMER_REAL)
        def expired(*_):
            nonlocal fired
            fired = True
            raise RuntimeDeadline(name + "_deadline_exceeded")
        signal.signal(signal.SIGALRM, expired)
        signal.setitimer(signal.ITIMER_REAL, min(seconds, timer[0]) if timer[0] else seconds)
    try:
        yield
        if fired or time.monotonic() - started > seconds:
            raise RuntimeDeadline(name + "_deadline_exceeded")
    except BaseException as error:
        if fired and not isinstance(error, RuntimeDeadline):
            raise RuntimeDeadline(name + "_deadline_exceeded") from error
        raise
    finally:
        if supported:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
            if timer[0]:
                signal.setitimer(signal.ITIMER_REAL, max(0.000001, timer[0] - (time.monotonic() - started)), timer[1])


def current_rss():
    """Current resident bytes, or None when this platform has no measurement."""
    if os.name == "posix" and Path("/proc/self/statm").is_file():
        return int(Path("/proc/self/statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE")
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                       *[(name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize",
                         "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                         "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        if psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            return counters.WorkingSetSize
    return None


class RuntimeProfile:
    def __init__(self, *, wall=time.perf_counter, cpu=time.process_time, rss=current_rss):
        self.wall, self.cpu, self.rss = wall, cpu, rss
        self.metrics, self.stack = {}, []
        self.lock = threading.RLock()
        self.last_disk = 0

    def observe(self, scratch_bytes):
        resident = self.rss()
        with self.lock:
            self.last_disk = scratch_bytes
            for active in self.stack:
                metric = self.metrics[active["name"]]
                metric["sampled_peak_scratch_bytes"] = max(metric["sampled_peak_scratch_bytes"], scratch_bytes)
                if resident is not None:
                    metric["sampled_peak_rss_bytes"] = max(metric["sampled_peak_rss_bytes"] or 0, resident)

    @contextmanager
    def scope(self, name):
        with self.lock:
            metric = self.metrics.setdefault(name, {"calls": 0, "completed": 0, "failures": 0,
                "wall_inclusive_seconds": 0.0, "wall_exclusive_seconds": 0.0,
                "cpu_inclusive_seconds": 0.0, "cpu_exclusive_seconds": 0.0,
                "sampled_peak_rss_bytes": None, "sampled_peak_scratch_bytes": self.last_disk})
            metric["calls"] += 1
            active = {"name": name, "wall": self.wall(), "cpu": self.cpu(), "child_wall": 0.0, "child_cpu": 0.0}
            self.stack.append(active)
        self.observe(self.last_disk)
        failed = False
        try:
            yield
        except BaseException:
            failed = True
            raise
        finally:
            self.observe(self.last_disk)
            with self.lock:
                elapsed, cpu = self.wall() - active["wall"], self.cpu() - active["cpu"]
                assert self.stack.pop() is active
                metric["completed"] += 1
                metric["failures"] += int(failed)
                metric["wall_inclusive_seconds"] += elapsed
                metric["wall_exclusive_seconds"] += max(0.0, elapsed - active["child_wall"])
                metric["cpu_inclusive_seconds"] += cpu
                metric["cpu_exclusive_seconds"] += max(0.0, cpu - active["child_cpu"])
                if self.stack:
                    self.stack[-1]["child_wall"] += elapsed
                    self.stack[-1]["child_cpu"] += cpu

    def report(self):
        with self.lock:
            return {"schema": "historical-runtime-stage-profile-v1",
                    "measurement": "process CPU; monotonic wall; current process RSS and recursive logical file bytes sampled",
                    "limits": "nested inclusive times overlap; exclusive times remove nested instrumented work; RSS/disk samples are lower bounds; child-process CPU/RSS excluded",
                    "active_stages": [x["name"] for x in self.stack],
                    "stages": {name: {key: round(value, 6) if isinstance(value, float) else value
                                      for key, value in values.items()} for name, values in self.metrics.items()}}

    def wrap(self, name, function):
        @wraps(function)
        def measured(*args, **kwargs):
            with self.scope(name):
                return function(*args, **kwargs)
        return measured


@contextmanager
def instrument(profile):
    """Restore every import boundary even after a deadline or failed assertion."""
    from tools import historical_acquisition as acquisition
    from tools import historical_normalization as normalization
    from tools import historical_reconcile as reconciliation
    from tools import historical_breadth_reference as reference
    from src import breadth
    changed = []
    targets = [(reconciliation, "cached_pages", "cache_validation"),
               (reconciliation, "normalize_pages", "normalization"),
               (reconciliation, "frames_for_replay", "projection"),
               (normalization, "_projection_digest", "projection_hashing"),
               (reference, "reference_replay", "reference"),
               (reference, "_prepare", "reference_preparation"),
               (breadth, "daily_counts", "production"),
               (reconciliation, "encode", "serialization")]
    try:
        for module, attribute, name in targets:
            original = getattr(module, attribute)
            changed.append((module, attribute, original))
            setattr(module, attribute, profile.wrap(name, original))
        # Module-local proxies prevent changing the shared standard-library JSON
        # module used by unrelated callers or the profiler's own receipt writer.
        for module in (acquisition, normalization):
            original = module.json
            changed.append((module, "json", original))
            module.json = SimpleNamespace(**{**vars(original), "loads": profile.wrap("parsing", original.loads)})
        yield
    finally:
        for module, attribute, original in reversed(changed):
            setattr(module, attribute, original)
