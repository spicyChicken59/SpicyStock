"""Bounded restored-defect controls; mutate imported code only, never source files.

Run from the repository with the pinned archive dependency installed. Output and
pytest temporary files must be outside Git. These are invented test fixtures;
no provider, owner package or owner key is accessed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


CHILD = r'''
import importlib, json, pathlib, sys
import pytest
case = json.loads(sys.argv[1])
if case.get("module"):
    module = importlib.import_module(case["module"])
    source = pathlib.Path(module.__file__).read_text(encoding="utf-8")
    assert source.count(case["before"]) == 1
    exec(compile(source.replace(case["before"], case["after"]), module.__file__, "exec"), module.__dict__)
raise SystemExit(pytest.main(["tests/test_historical_package.py", "-q", "-k", case["selection"],
                             "--basetemp", sys.argv[2], "--tb=short"]))
'''

CASES = [
    {"name": "unchanged_valid_and_negative_controls", "expected_exit": 0,
     "selection": "codec_valid_single_stream_roundtrip or (codec_rejects and zero_tail and gzip) or (tar_framing and index_cap) or (resources_rejected and window)"},
    {"name": "restored_legacy_gzip_ignored_trailer", "expected_exit": 1,
     "module": "tools.historical_archive_codec",
     "before": "if decoder.unused_data or source.read(1):", "after": "if False:",
     "selection": "codec_rejects and zero_tail and gzip"},
    {"name": "restored_index_excluded_from_expanded_cap", "expected_exit": 1,
     "module": "tools.historical_package",
     "before": "expected, total = {}, first.size", "after": "expected, total = {}, 0",
     "selection": "tar_framing and index_cap"},
    {"name": "restored_window_allocation_before_header_bound", "expected_exit": 1,
     "module": "tools.historical_archive_codec",
     "before": "params.window_size > WINDOW_BYTES", "after": "False",
     "selection": "resources_rejected and window"},
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    target = args.output.resolve()
    if target.exists() or any((part / ".git").exists() for part in (target, *target.parents)):
        raise SystemExit("fresh external output directory required")
    target.mkdir(mode=0o700, parents=True)
    paths = [Path("tools/historical_package.py"), Path("tools/historical_archive_codec.py"),
             Path("tests/test_historical_package.py")]
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    results = []
    for ordinal, case in enumerate(CASES):
        # Keep fixture paths under Windows' legacy path limit.
        result = subprocess.run([sys.executable, "-c", CHILD, json.dumps(case), str(target / ("c" + str(ordinal)))],
                                stdin=subprocess.DEVNULL, capture_output=True, timeout=120, check=False)
        (target / (case["name"] + ".txt")).write_bytes(result.stdout + result.stderr)
        summary = result.stdout.decode("utf-8", "replace").strip().splitlines()[-1]
        matched = (result.returncode == case["expected_exit"] and "error" not in summary.lower() and
                   ("passed" in summary if case["expected_exit"] == 0 else "1 failed" in summary))
        results.append({"name": case["name"], "selection": case["selection"],
                        "expected_exit": case["expected_exit"], "actual_exit": result.returncode,
                        "status": "PASS" if matched else "FAIL", "pytest_summary": summary})
    after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    report = {"schema": "historical-codec-restored-controls-v1", "synthetic_only": True,
              "status": "PASS" if before == after and all(r["status"] == "PASS" for r in results) else "FAIL",
              "source_hashes_before": before, "source_hashes_after": after,
              "source_files_unchanged": before == after, "cases": results,
              "owner_key_access": "NOT RUN", "provider_requests": 0,
              "interpretation": "Each restored defect must make its existing negative test fail; unchanged valid and negative controls must pass."}
    (target / "codec-restored-controls.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
