"""Reproduce acquisition guard mutations without editing the working tree.

Run with --output <evidence-directory>. Every child runs synthetic pytest
fixtures with the repository's socket-blocking conftest. Mutants replace source
in an isolated process's memory; production files and retained data stay intact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/historical_acquisition.py"
TEST = ROOT / "tests/test_historical_acquisition.py"
GEOMETRY = ('if not (values["l"] <= min(values["o"], values["c"]) <=\n'
            '                    max(values["o"], values["c"]) <= values["h"]):')
VARIANTS = {
    "request_cap": ('if count >= limits["requests"]:', 'if False:',
                    'test_request_cap_shared_by_queries_and_restarts'),
    "byte_cap": ('if not isinstance(response.body, bytes) or len(response.body) > budget:',
                 'if not isinstance(response.body, bytes):',
                 'test_shared_uncompressed_byte_cap_never_overretains'),
    "probe": ('if query["scope"] == "bulk":', 'if False:',
              'test_bulk_requires_successful_small_probe_with_required_bars[False]'),
    "geometry": (GEOMETRY, 'if False:',
                 'test_wrong_symbol_session_numeric_values_retained_but_quarantined'),
    "unrelated_geometry_control": (GEOMETRY, 'if False:',
                 'test_request_cap_shared_by_queries_and_restarts'),
}


def worker(mode):
    sys.path.insert(0, str(ROOT))
    source = SOURCE.read_text()
    target = str(TEST)
    if mode != "baseline":
        old, new, test = VARIANTS[mode]
        if source.count(old) != 1:
            raise RuntimeError("mutation target must occur exactly once")
        module = types.ModuleType("tools.historical_acquisition")
        module.__file__ = str(SOURCE)
        sys.modules[module.__name__] = module
        import tools
        tools.historical_acquisition = module
        exec(compile(source.replace(old, new), str(SOURCE), "exec"), module.__dict__)
        target += "::" + test
    import pytest
    return pytest.main([target, "-q"])


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    original = SOURCE.read_bytes()
    tests = TEST.read_bytes()
    results = []
    for mode in ["baseline", *VARIANTS]:
        completed = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", mode],
            cwd=ROOT, capture_output=True, text=True, check=False)
        log = completed.stdout + completed.stderr
        (output / (mode + ".txt")).write_text(log, encoding="utf-8")
        failed = sum(int(x) for x in re.findall(r"(?<!\w)(\d+) failed", log))
        passed = sum(int(x) for x in re.findall(r"(?<!\w)(\d+) passed", log))
        expected_failure = mode not in {"baseline", "unrelated_geometry_control"}
        accepted = completed.returncode == (1 if expected_failure else 0)
        if expected_failure:
            accepted = accepted and failed == 1 and "DID NOT RAISE" in log
        if mode == "geometry":
            accepted = accepted and passed == 7
        if mode == "unrelated_geometry_control":
            accepted = accepted and passed == 1
        results.append({"control": mode, "status": "PASS" if accepted else "FAIL",
                        "expected_pytest_exit": 1 if expected_failure else 0,
                        "actual_pytest_exit": completed.returncode,
                        "assertion_failures": failed, "passing_tests": passed,
                        "log": mode + ".txt"})
    unchanged = SOURCE.read_bytes() == original and TEST.read_bytes() == tests
    report = {"status": "PASS" if unchanged and all(r["status"] == "PASS" for r in results) else "FAIL",
              "source_sha256": hashlib.sha256(original).hexdigest(),
              "tests_sha256": hashlib.sha256(tests).hexdigest(),
              "source_and_tests_unchanged": unchanged,
              "network": "blocked_by_test_conftest", "fixtures": "synthetic_only",
              "runtime": sys.version, "controls": results}
    (output / "controls.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    return 0 if report["status"] == "PASS" else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker", choices=["baseline", *VARIANTS], help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        return worker(args.worker)
    if args.output is None:
        parser.error("--output is required")
    return run(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
