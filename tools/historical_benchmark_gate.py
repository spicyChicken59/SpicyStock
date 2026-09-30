"""Skip observed docs-only pushes or the exact reviewed admission repair.

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

# This is a one-incident exception, not a generic exemption for guard changes.
# PR97's complete scientific/codec/runtime evidence stays bound to its original
# bytes. The repair's normal tests establish the new admission behavior; this
# gate cannot attest that the old benchmark executed the new admission code.
REPAIR_BASE = "6979904ad872d8d648c93537c77ead5fda909481"
REPAIR_BRANCH = "fix/native5-readiness-input-recovery"
PARENT_RELEASE = "docs/input-truthfulness/historical-delivery-release-evidence.json"
PARENT_RELEASE_SHA256 = "4676955bd89be86e0e025f0724d07bc1279ed822170239c5fa446bcfe5144490"
IDENTITY_READER = "tools/historical_package.py"
IDENTITY_READER_BEFORE_SHA256 = "b0e45dd12f1c17538fc15d1d3a1ed48c67c89c5b67e91c63ec2c17420a692128"
IDENTITY_READER_AFTER_SHA256 = "e16c675a62d0880ea2148b4569bc10128c6c667ea47804b88725aa58d6ed7cbb"
REPAIR_EVIDENCE = NEW_EVIDENCE + "native5-recovery/"
REPAIR_CODE = {
    ".github/workflows/historical-input-proof.yml",
    "tools/historical-execution-policy.json",
    "tools/historical-native5-recovery.json",
    "tools/historical-native6-compatibility.json",
    "tools/historical_incident_recovery.py",
    "tools/historical_execution_guard.py",
    "tools/historical_benchmark_gate.py",
    IDENTITY_READER,
}
REPAIR_TESTS = {
    "tests/fixtures/workflow-validation/native5-original-preflight.sh",
    "tests/test_historical_benchmark_gate.py",
    "tests/test_historical_workflow_validation.py",
    "tests/test_historical_incident_recovery.py",
    "tests/test_historical_native6_recovery.py",
    "tests/test_historical_execution_guard.py",
    "tests/test_historical_delivery_binding.py",
    "tests/test_historical_recovery_integration.py",
    "tests/test_historical_execution.py",
    "tests/test_historical_package.py",
}
REPAIR_DOCUMENTS = {"README.md", ".env.example", "CLAUDE.md",
    "docs/input-truthfulness/2026-09-29-historical-execution.md",
    "docs/input-truthfulness/historical-native6-release-evidence.json"}


def _repair_identity(event):
    pr = event.get("pull_request", {})
    number = event.get("number")
    repo = {"id": 1352997802, "full_name": "spicyChicken59/SpicyStock"}
    if not (type(number) is int and number > 97 and pr.get("number") == number and
            event.get("action") in {"opened", "reopened", "synchronize", "ready_for_review"} and
            pr.get("head", {}).get("ref") == REPAIR_BRANCH and
            pr.get("base", {}).get("ref") == "main" and
            pr.get("base", {}).get("sha") == REPAIR_BASE):
        return False
    return all(isinstance(item, dict) and all(item.get(key) == value for key, value in repo.items())
               for item in (event.get("repository"), pr.get("head", {}).get("repo"), pr.get("base", {}).get("repo")))


def _git_bytes(run, revision, path):
    result = run(["show", revision + ":" + path])
    if result.returncode != 0 or not isinstance(result.stdout, bytes) or not 0 < len(result.stdout) <= 2 * 1024**2:
        raise ValueError("repair_source_unavailable")
    return result.stdout


def _repair_decision(event, run, head):
    if not _repair_identity(event):
        return None
    if run(["merge-base", "--is-ancestor", REPAIR_BASE, head]).returncode != 0:
        raise ValueError("repair_base_not_ancestor")
    paths = _changed_paths(run, REPAIR_BASE, head)
    if any(path not in REPAIR_CODE | REPAIR_TESTS | REPAIR_DOCUMENTS and
           not path.startswith(REPAIR_EVIDENCE) for path in paths):
        raise ValueError("repair_scope_changed")
    # Read Git object bytes, not worktree text subject to CRLF conversion.
    old = _git_bytes(run, REPAIR_BASE, PARENT_RELEASE)
    current = _git_bytes(run, head, PARENT_RELEASE)
    if hashlib.sha256(old).hexdigest() != PARENT_RELEASE_SHA256 or current != old:
        raise ValueError("repair_parent_evidence_changed")
    evidence = json.loads(old)
    pins = evidence["source_sha256"]
    if not isinstance(pins, dict) or not pins:
        raise ValueError("repair_source_pins_missing")
    # The only package edit is the exact reviewed old-v4 identity reader
    # conditional. Pin the complete old/new files: no codec/work-bound bypass.
    if (pins.get(IDENTITY_READER) != IDENTITY_READER_BEFORE_SHA256 or
            hashlib.sha256(_git_bytes(run, REPAIR_BASE, IDENTITY_READER)).hexdigest() != IDENTITY_READER_BEFORE_SHA256 or
            hashlib.sha256(_git_bytes(run, head, IDENTITY_READER)).hexdigest() != IDENTITY_READER_AFTER_SHA256):
        raise ValueError("repair_identity_reader_changed")
    preserved = {path: digest for path, digest in pins.items() if path not in REPAIR_CODE}
    for path, digest in preserved.items():
        if hashlib.sha256(_git_bytes(run, head, path)).hexdigest() != digest:
            raise ValueError("repair_measured_source_changed")
    for proof in evidence["proofs"].values():
        if hashlib.sha256(_git_bytes(run, head, proof["path"])).hexdigest() != proof["sha256"]:
            raise ValueError("repair_measurement_proof_changed")
    return {"schema": "historical-runtime-pr-gate-v2", "status": "NOT RUN", "run_required": False,
            "reason": "exact_native5_admission_repair_preserves_pr97_measurements",
            "observed_base": REPAIR_BASE, "observed_head": head,
            "changed_file_count": len(paths), "changed_paths": paths,
            "parent_release_sha256": PARENT_RELEASE_SHA256, "preserved_source_sha256": preserved,
            "identity_reader_revision": {"path": IDENTITY_READER,
                "before_sha256": IDENTITY_READER_BEFORE_SHA256, "after_sha256": IDENTITY_READER_AFTER_SHA256},
            "claim": "PR97 measured the pinned prior sources. No new benchmark or execution release is asserted."}


def _changed_paths(run, before, head):
    changed = run(["diff", "--name-only", "-z", "--no-renames", before, head])
    if changed.returncode != 0:
        raise ValueError("diff_unavailable")
    paths = [p.decode("utf-8", "strict") for p in changed.stdout.split(b"\0") if p]
    if not paths or any("\n" in p or "\r" in p or p.startswith("/") or ".." in p.split("/") for p in paths):
        raise ValueError("empty_or_ambiguous_diff")
    return paths


def relevant(path):
    # Unknown files are material. In particular, prior inventories, attributes,
    # dependencies, actions and fixtures cannot quietly become a docs-only push.
    return path not in DOCUMENTATION and not path.startswith(NEW_EVIDENCE)


def decide(event, *, git=None):
    result = {"schema": "historical-runtime-pr-gate-v1", "status": "NOT RUN", "run_required": True,
              "reason": "unverified_event_range", "claim": "This decision is not a benchmark result or execution release."}
    run = git or (lambda arguments: subprocess.run(["git", *arguments], capture_output=True, check=False))
    head = event.get("pull_request", {}).get("head", {}).get("sha")
    if isinstance(head, str) and _SHA.fullmatch(head):
        try:
            repair = _repair_decision(event, run, head)
            if repair is not None:
                return repair
        except (OSError, UnicodeError, ValueError, TypeError, AttributeError, KeyError):
            result["reason"] = "native5_repair_preservation_not_established"
            return result
    if event.get("action") != "synchronize":
        result["reason"] = "initial_or_reopened_review_requires_measurement"
        return result
    before, head = event.get("before"), event.get("pull_request", {}).get("head", {}).get("sha")
    if not all(isinstance(value, str) and _SHA.fullmatch(value) for value in (before, head)) or before == head:
        return result
    result.update(observed_before=before, observed_head=head)
    try:
        if run(["merge-base", "--is-ancestor", before, head]).returncode != 0:
            result["reason"] = "range_unavailable_or_not_ancestor"
            return result
        paths = _changed_paths(run, before, head)
        material = [p for p in paths if relevant(p)]
        result.update(run_required=bool(material), changed_file_count=len(paths), relevant_changed_paths=material,
                      reason="runtime_or_validation_inputs_changed" if material else "observed_docs_only_push_no_runtime_change")
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
