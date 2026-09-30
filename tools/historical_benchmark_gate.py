"""Skip observed docs-only pushes or the receipt-bound PR97 correction.

A skip is NOT RUN, never evidence of a passing benchmark for another checkout.
The existing pytest/browser jobs remain independent of this optional-cost gate.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


_SHA = re.compile(r"[0-9a-f]{40}\Z")
DOCUMENTATION = {"README.md", ".env.example", "CLAUDE.md",
                 "docs/input-truthfulness/2026-09-29-historical-execution.md",
                 "docs/input-truthfulness/2026-09-30-delivery-readiness.md",
                 "docs/input-truthfulness/historical-delivery-release-evidence.json"}
NEW_EVIDENCE = "docs/input-truthfulness/2026-09-30-delivery-readiness-evidence/"
CORRECTION_BASE = "bd779c2a1ce14b8a7361c4866678e55e29ae18f8"
CORRECTION_RECEIPT = NEW_EVIDENCE + "bounded-correction/window31-supervisor.json"
CORRECTION_RECEIPT_SHA256 = "77ee1a171b9c0d0361c18ebfabda17a3e6d63e6287a26c24881295b792368a7e"
CORRECTION_PATHS = {".gitleaks.toml", "tests/secret_scan_controls.py", "tests/test_secret_scan.py",
                    "tools/historical_benchmark_gate.py", "tests/test_historical_benchmark_gate.py"}


def _correction_identity(event):
    pr = event.get("pull_request", {})
    repositories = (event.get("repository", {}), pr.get("base", {}).get("repo", {}),
                    pr.get("head", {}).get("repo", {}))
    return (type(event.get("number")) is int and event["number"] == 97
            and type(pr.get("number")) is int and pr["number"] == 97
            and all(repo.get("full_name") == "spicyChicken59/SpicyStock"
                    and type(repo.get("id")) is int and repo["id"] == 1352997802
                    for repo in repositories))


def _changed_paths(run, before, head):
    changed = run(["diff", "--name-only", "-z", "--no-renames", before, head])
    if changed.returncode != 0:
        raise ValueError("diff_unavailable")
    paths = [p.decode("utf-8", "strict") for p in changed.stdout.split(b"\0") if p]
    if not paths or any("\n" in p or "\r" in p or p.startswith("/") or ".." in p.split("/") for p in paths):
        raise ValueError("empty_or_ambiguous_diff")
    return paths


def _correction_deferral(run, head):
    """The whole reviewed range and the receipt at this head must agree."""
    if run(["merge-base", "--is-ancestor", CORRECTION_BASE, head]).returncode != 0:
        raise ValueError("correction_baseline_unavailable_or_not_ancestor")
    paths = _changed_paths(run, CORRECTION_BASE, head)
    if any(relevant(path) and path not in CORRECTION_PATHS for path in paths):
        raise ValueError("correction_contains_unreviewed_path")
    retained = run(["show", head + ":" + CORRECTION_RECEIPT])
    if retained.returncode != 0 or hashlib.sha256(retained.stdout).hexdigest() != CORRECTION_RECEIPT_SHA256:
        raise ValueError("correction_receipt_missing_or_changed")
    receipt = json.loads(retained.stdout)
    comparison = receipt.get("child_result", {}).get("archive_comparison", {})
    if not (receipt.get("schema") == "historical-window31-supervisor-v1"
            and receipt.get("status") == "FAIL" and comparison.get("status") == "FAIL"
            and type(comparison.get("archive_bytes")) is int
            and comparison["archive_bytes"] > 199 * 1024 * 1024
            and comparison.get("archive_headroom_bytes") == 199 * 1024 * 1024 - comparison["archive_bytes"]):
        raise ValueError("correction_receipt_does_not_record_capacity_failure")
    return {"run_required": False, "reason": "pr97_bounded_comparison_failed_no_further_benchmark_authorized",
            "reviewed_baseline": CORRECTION_BASE, "reviewed_range_changed_paths": paths,
            "comparison_receipt_path": CORRECTION_RECEIPT,
            "comparison_receipt_sha256": CORRECTION_RECEIPT_SHA256}


def relevant(path):
    # Unknown files are material. In particular, prior inventories, attributes,
    # dependencies, actions and fixtures cannot quietly become a docs-only push.
    return path not in DOCUMENTATION and not path.startswith(NEW_EVIDENCE)


def decide(event, *, git=None):
    result = {"schema": "historical-runtime-pr-gate-v1", "status": "NOT RUN", "run_required": True,
              "reason": "unverified_event_range", "claim": "This decision is not a benchmark result or execution release."}
    if event.get("action") != "synchronize":
        result["reason"] = "initial_or_reopened_review_requires_measurement"
        return result
    before, head = event.get("before"), event.get("pull_request", {}).get("head", {}).get("sha")
    if not all(isinstance(value, str) and _SHA.fullmatch(value) for value in (before, head)) or before == head:
        return result
    result.update(observed_before=before, observed_head=head)
    run = git or (lambda arguments: subprocess.run(["git", *arguments], capture_output=True, check=False))
    try:
        if run(["merge-base", "--is-ancestor", before, head]).returncode != 0:
            result["reason"] = "range_unavailable_or_not_ancestor"
            return result
        paths = _changed_paths(run, before, head)
        material = [p for p in paths if relevant(p)]
        result.update(run_required=bool(material), changed_file_count=len(paths), relevant_changed_paths=material,
                      reason="runtime_or_validation_inputs_changed" if material else "observed_docs_only_push_no_runtime_change")
        if _correction_identity(event):
            # Do not let a later docs-only push hide an earlier material change.
            result.update(run_required=True, reason="pr97_correction_deferral_unverified")
            result.update(_correction_deferral(run, head))
    except (OSError, UnicodeError, ValueError, TypeError, AttributeError):
        return result
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = decide(json.loads(args.event.read_bytes()))
    except (OSError, ValueError, TypeError, AttributeError):
        result = {"schema": "historical-runtime-pr-gate-v1", "status": "NOT RUN", "run_required": True,
                  "reason": "event_unavailable"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes((json.dumps(result, sort_keys=True, indent=2) + "\n").encode())
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
            stream.write("run_required=" + str(result["run_required"]).lower() + "\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
