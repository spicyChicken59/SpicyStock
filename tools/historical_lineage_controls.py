"""Reproduce PR #93 raw-pointer failures through Acquisition and synthetic HTTP.

Run --output <external-directory>. Each variant runs normal collected pytest
regressions in a separate socket-blocked process. Reviewed source and the
restored defect are loaded into memory; no checkout, raw data or ledger is reset.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/historical_acquisition.py"
TEST = ROOT / "tests/test_historical_acquisition.py"
REVIEWED = "a9ed0ec3b64399e1f9d80ac3ce27d921c289f9b1"
SELECTOR = "duplicate_source_coordinates"
EXPECTED_FAILURES = {
    "test_duplicate_source_coordinates_resolve_retained_raw[two_pages_wrong_observation]",
    "test_duplicate_source_coordinates_resolve_retained_raw[one_row_later_page]",
    "test_duplicate_source_coordinates_resolve_retained_raw[three_page_replacements]",
    "test_duplicate_source_coordinates_resolve_retained_raw[within_later_page]",
    "test_duplicate_source_coordinates_resolve_retained_raw[multiple_symbols]",
    "test_duplicate_source_coordinates_cached_resume[three_page_replacements]",
}


def source_for(mode):
    if mode == "reviewed":
        raw = subprocess.check_output([
            "git", "-c", f"safe.directory={ROOT.as_posix()}", "show",
            f"{REVIEWED}:tools/historical_acquisition.py"], cwd=ROOT)
        return raw.decode("utf-8")
    source = SOURCE.read_text(encoding="utf-8")
    if mode == "restored_defect":
        correct = '"row_index": row_index'
        if source.count(correct) != 1:
            raise RuntimeError("expected exactly one raw-page coordinate assignment")
        source = source.replace(correct, '"row_index": len(by_symbol[symbol])')
    return source


def worker(mode, junit):
    sys.path.insert(0, str(ROOT))
    source = source_for(mode)
    module = types.ModuleType("tools.historical_acquisition")
    module.__file__ = str(SOURCE)
    sys.modules[module.__name__] = module
    import tools
    tools.historical_acquisition = module
    exec(compile(source, str(SOURCE), "exec"), module.__dict__)
    import pytest
    return pytest.main([str(TEST), "-q", "-k", SELECTOR, f"--junitxml={junit}"])


def run(output):
    output = output.resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError("write control outputs outside the repository")
    output.mkdir(parents=True, exist_ok=True)
    inputs = {p: p.read_bytes() for p in (SOURCE, TEST, Path(__file__).resolve())}
    results = []
    for mode in ("reviewed", "fixed", "restored_defect"):
        junit = output / f"{mode}.xml"
        completed = subprocess.run([sys.executable, str(Path(__file__).resolve()),
            "--worker", mode, "--junit", str(junit)], cwd=ROOT,
            capture_output=True, text=True, encoding="utf-8", check=False)
        log = completed.stdout + completed.stderr
        (output / f"{mode}.txt").write_text(log, encoding="utf-8")
        cases = ET.parse(junit).getroot().findall(".//testcase") if junit.exists() else []
        observations = []
        failures = set()
        for case in cases:
            failure = case.find("failure")
            status = "FAIL" if failure is not None or case.find("error") is not None else "NOT RUN" if case.find("skipped") is not None else "PASS"
            if status == "FAIL":
                failures.add(case.attrib["name"])
            observations.append({"test": case.attrib["name"], "status": status,
                "failure_is_raw_pointer_assertion": failure is not None and "raw source" in (failure.text or "")})
        expected = set() if mode == "fixed" else EXPECTED_FAILURES
        correct = (len(cases) == 9 and failures == expected
            and completed.returncode == (0 if mode == "fixed" else 1)
            and all(o["status"] == "PASS" or o["failure_is_raw_pointer_assertion"] for o in observations))
        results.append({"variant": mode, "status": "PASS" if mode == "fixed" and correct else "FAIL",
            "expected_result_verified": correct, "pytest_exit": completed.returncode,
            "passed": sum(o["status"] == "PASS" for o in observations), "failed": len(failures),
            "source_utf8_lf_sha256": hashlib.sha256(source_for(mode).encode()).hexdigest(),
            "tests": observations, "log": f"{mode}.txt", "junit": junit.name})
    unchanged = all(p.read_bytes() == raw for p, raw in inputs.items())
    report = {"status": "PASS" if unchanged and all(r["expected_result_verified"] for r in results) else "FAIL",
        "reviewed_head": REVIEWED, "scope": "Actual Acquisition class with synthetic transport, retained raw JSON, normalizer and cached resume; no method excerpt or live HTTP.",
        "source_coordinate_contract": "raw-page-symbol-row-v1: SHA256(raw page), query-chain page_index, symbol, zero-based row_index into that raw page's bars[symbol] array.",
        "unchanged_control_cases": ["same_page_control", "no_duplicate_control", "cached same_page_control"],
        "network": "blocked by tests/conftest.py", "real_provider_requests": 0,
        "source_tests_runner_unchanged": unchanged, "runtime": sys.version,
        "input_sha256": {p.relative_to(ROOT).as_posix(): hashlib.sha256(raw).hexdigest() for p, raw in inputs.items()},
        "variants": results}
    (output / "controls.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "variants": [
        {k: r[k] for k in ("variant", "status", "expected_result_verified", "passed", "failed")} for r in results]}))
    return 0 if report["status"] == "PASS" else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker", choices=("reviewed", "fixed", "restored_defect"), help=argparse.SUPPRESS)
    parser.add_argument("--junit", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        if args.junit is None:
            parser.error("--junit required for worker")
        return worker(args.worker, args.junit)
    if args.output is None:
        parser.error("--output required")
    return run(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
