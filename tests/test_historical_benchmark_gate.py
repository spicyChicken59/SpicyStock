"""An unknown or incomplete PR range runs; skips are never a PASS claim."""
from types import SimpleNamespace
from pathlib import Path
import hashlib
import json
import re

import pytest
import yaml

from tools.historical_benchmark_gate import decide
from tools import historical_benchmark_gate as gate


def event(action="synchronize"):
    return {"action": action, "before": "a" * 40, "pull_request": {"head": {"sha": "b" * 40}}}


def git(paths, *, ancestor=0, diff=0):
    def run(arguments):
        if arguments[0] == "merge-base":
            assert arguments == ["merge-base", "--is-ancestor", "a" * 40, "b" * 40]
            return SimpleNamespace(returncode=ancestor)
        assert arguments == ["diff", "--name-only", "-z", "--no-renames", "a" * 40, "b" * 40]
        return SimpleNamespace(returncode=diff, stdout=b"\0".join(p.encode() for p in paths) + b"\0")
    return run


@pytest.mark.parametrize("action", ["opened", "reopened", "ready_for_review", "unknown"])
def test_initial_event_always_runs_even_if_a_range_claims_docs_only(action):
    assert decide(event(action), git=lambda _: pytest.fail("unexpected git"))["run_required"]


def test_complete_multi_commit_docs_only_range_skips_with_not_run_receipt():
    result = decide(event(), git=git(["README.md", "CLAUDE.md", ".env.example",
        "docs/input-truthfulness/2026-09-30-delivery-readiness-evidence/measurement.json"]))
    assert result["status"] == "NOT RUN" and result["run_required"] is False
    assert result["observed_before"] == "a" * 40 and result["observed_head"] == "b" * 40
    assert result["changed_file_count"] == 4


@pytest.mark.parametrize("path", ["tools/historical_projection_benchmark.py", "src/breadth.py",
    "tools/requirements-historical.txt", ".github/workflows/tests.yml", ".github/actions/new-action/action.yml",
    ".gitattributes", "unrecognized-file", "tests/fixtures/new-input.json",
    "docs/input-truthfulness/2026-09-30-projection-compaction-evidence/benchmark-central-members.json"])
def test_known_runtime_and_unknown_paths_always_run(path):
    assert decide(event(), git=git(["README.md", path]))["run_required"]


@pytest.mark.parametrize("ancestor,diff", [(1, 0), (128, 0), (0, 128)])
def test_unavailable_nonancestor_or_failed_diff_runs(ancestor, diff):
    assert decide(event(), git=git(["README.md"], ancestor=ancestor, diff=diff))["run_required"]


@pytest.mark.parametrize("before", [None, "", "not-a-sha", "b" * 40, "x" * 40])
def test_missing_or_invalid_observed_before_runs(before):
    value = event()
    value["before"] = before
    assert decide(value, git=lambda _: pytest.fail("invalid range was used"))["run_required"]


@pytest.mark.parametrize("paths", [[], ["README.md\nother"], ["../README.md"], ["/README.md"]])
def test_empty_or_ambiguous_diff_does_not_skip(paths):
    assert decide(event(), git=git(paths))["run_required"]


def correction_event():
    value = event()
    value["number"] = value["pull_request"]["number"] = 97
    repo = {"id": 1352997802, "full_name": "spicyChicken59/SpicyStock"}
    value["repository"] = dict(repo)
    value["pull_request"]["head"]["repo"] = dict(repo)
    value["pull_request"]["base"] = {"repo": dict(repo)}
    return value


def test_dated_failed_comparison_receipt_is_preserved_without_current_authority():
    path = Path(__file__).resolve().parents[1] / (
        "docs/input-truthfulness/2026-09-30-delivery-readiness-evidence/bounded-correction/window31-supervisor.json")
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "77ee1a171b9c0d0361c18ebfabda17a3e6d63e6287a26c24881295b792368a7e"
    assert json.loads(raw)["status"] == "FAIL"


@pytest.mark.parametrize("path", ["tools/historical_memory_supervisor.py", "tools/historical_package.py",
    "tools/historical_projection_benchmark.py", "tools/historical_benchmark_gate.py",
    "tests/test_historical_memory_supervisor.py", ".github/workflows/tests.yml", ".gitleaks.toml"])
def test_pr97_new_material_changes_require_measurement_despite_dated_failure(path):
    result = decide(correction_event(), git=git([path, "README.md"]))
    assert result["run_required"] is True
    assert result["reason"] == "runtime_or_validation_inputs_changed"


def test_pr97_later_complete_docs_only_range_does_not_repeat_measured_cases():
    result = decide(correction_event(), git=git(["CLAUDE.md", "README.md"]))
    assert result["run_required"] is False and result["status"] == "NOT RUN"
    assert result["reason"] == "observed_docs_only_push_no_runtime_change"


def test_runtime_workflow_is_provider_free_pinned_pr_only_with_compact_artifacts():
    path = Path(__file__).resolve().parents[1] / ".github/workflows/tests.yml"
    value = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
    gate, job = value["jobs"]["historical-runtime-gate"], value["jobs"]["historical-runtime"]
    assert gate["if"] == "github.event_name == 'pull_request'"
    assert "github.event_name == 'pull_request'" in job["if"]
    assert job["needs"] == "historical-runtime-gate"
    assert job["runs-on"] == "ubuntu-24.04" and job["timeout-minutes"] == "75"
    assert job["strategy"]["matrix"]["case"] == ["central", "stress"]
    assert job["strategy"]["fail-fast"] == "false"
    assert gate["permissions"] == job["permissions"] == {"contents": "read"}
    assert "secrets." not in str(job) and "GITHUB_TOKEN" not in str(job)
    for spec in (gate, job):
        for step in spec["steps"]:
            if "uses" in step:
                assert re.fullmatch(r"actions/[a-z-]+@[0-9a-f]{40}", step["uses"])
    python = next(s for s in job["steps"] if s.get("uses", "").startswith("actions/setup-python@"))
    assert python["with"]["python-version"] == "3.12.14"
    runs = "\n".join(s.get("run", "") for s in job["steps"])
    assert "--require-hashes --only-binary=:all: -r tools/requirements-historical-archive.txt" in runs
    assert "pip install -r tools/requirements-historical.txt" in runs
    assert "historical_memory_supervisor.py" in runs and "--setup-start" in runs
    assert "sudo --preserve-env=" in runs and '--uid "$(id -u)" --gid "$(id -g)"' in runs
    artifact = next(s for s in job["steps"] if s.get("uses", "").startswith("actions/upload-artifact@"))
    assert artifact["if"] == "always()"
    assert set(Path(line.strip()).name for line in artifact["with"]["path"].splitlines()) == {
        "memory-envelope.json", "benchmark-preflight.json", "benchmark-result.json", "runtime-profile.json", "synthetic-member-inventory.json"}
    assert ".age" not in artifact["with"]["path"] and ".tar" not in artifact["with"]["path"]
    normal_runs = "\n".join(s.get("run", "") for s in value["jobs"]["pytest"]["steps"])
    assert normal_runs.index("--require-hashes") < normal_runs.index("-r requirements-dev.txt")


def native5_repair_event(action="opened"):
    value = correction_event()
    value["action"] = action
    value["number"] = value["pull_request"]["number"] = 123  # invented test PR
    value["pull_request"]["head"]["ref"] = gate.REPAIR_BRANCH
    value["pull_request"]["base"].update(ref="main", sha=gate.REPAIR_BASE)
    return value


def repair_git(paths=None, *, mutate=None, missing=None):
    root = Path(__file__).resolve().parents[1]
    release = (root / gate.PARENT_RELEASE).read_bytes()
    evidence = json.loads(release)
    files = {gate.PARENT_RELEASE: release}
    for path in evidence["source_sha256"]:
        if path not in gate.REPAIR_CODE:
            files[path] = (root / path).read_bytes()
    for proof in evidence["proofs"].values():
        files[proof["path"]] = (root / proof["path"]).read_bytes()
    files[gate.IDENTITY_READER] = (root / gate.IDENTITY_READER).read_bytes()
    # Reconstruct only the literal pre-repair identity conditional; assert the
    # full old hash so this fixture cannot hide a codec/packing change.
    old_conditional = b'''    if not legacy and value["compatibility_contract_sha256"] != (
            PREVIOUS_COMPATIBILITY_CONTRACT_SHA256 if previous else execution_guard.COMPATIBILITY_CONTRACT_SHA256):
'''
    new_conditional = b'''    # Reading a PR97 v4 identity does not grant new execution authorization.
    # validate_phase_binding above keeps its old recovery/native-slot pairing;
    # the live guard separately requires the new policy and incident relation.
    allowed = {PREVIOUS_COMPATIBILITY_CONTRACT_SHA256} if previous else {
        execution_guard.COMPATIBILITY_CONTRACT_SHA256,
        execution_guard.PR97_COMPATIBILITY_CONTRACT_SHA256}
    if not legacy and value["compatibility_contract_sha256"] not in allowed:
'''
    old_reader = files[gate.IDENTITY_READER].replace(new_conditional, old_conditional)
    assert hashlib.sha256(old_reader).hexdigest() == gate.IDENTITY_READER_BEFORE_SHA256
    changed = paths if paths is not None else sorted(gate.REPAIR_CODE | gate.REPAIR_TESTS)
    calls = []

    def run(arguments):
        calls.append(arguments)
        if arguments[0] == "merge-base":
            assert arguments == ["merge-base", "--is-ancestor", gate.REPAIR_BASE, "b" * 40]
            return SimpleNamespace(returncode=0)
        if arguments[0] == "diff":
            assert arguments == ["diff", "--name-only", "-z", "--no-renames", gate.REPAIR_BASE, "b" * 40]
            return SimpleNamespace(returncode=0, stdout=b"\0".join(p.encode() for p in changed) + b"\0")
        assert arguments[0] == "show"
        revision, path = arguments[1].split(":", 1)
        assert revision in {gate.REPAIR_BASE, "b" * 40}
        if path == missing:
            return SimpleNamespace(returncode=128, stdout=b"")
        data = old_reader if path == gate.IDENTITY_READER and revision == gate.REPAIR_BASE else files[path]
        if mutate == path and revision == "b" * 40:
            data += b" changed"
        return SimpleNamespace(returncode=0, stdout=data)
    return run, calls


@pytest.mark.parametrize("action", ["opened", "reopened", "synchronize", "ready_for_review"])
def test_exact_admission_repair_uses_complete_base_diff_and_immutable_measurements(action):
    run, calls = repair_git()
    result = decide(native5_repair_event(action), git=run)
    assert result["status"] == "NOT RUN" and result["run_required"] is False
    assert result["schema"] == "historical-runtime-pr-gate-v2"
    assert result["observed_base"] == gate.REPAIR_BASE and result["observed_head"] == "b" * 40
    assert result["parent_release_sha256"] == gate.PARENT_RELEASE_SHA256
    # Package, codec, wrapper, scientific runtime, dependency and benchmark job
    # bytes remain pinned. New admission behavior is tested by normal pytest.
    for path in ["tools/historical_archive_codec.py",
                 "tools/historical_execution.py", "src/breadth.py", ".github/workflows/tests.yml",
                 "tools/requirements-historical.txt", "tools/historical-workflow-recovery.json"]:
        assert path in result["preserved_source_sha256"]
    assert result["identity_reader_revision"] == {"path": gate.IDENTITY_READER,
        "before_sha256": gate.IDENTITY_READER_BEFORE_SHA256, "after_sha256": gate.IDENTITY_READER_AFTER_SHA256}
    assert ["diff", "--name-only", "-z", "--no-renames", gate.REPAIR_BASE, "b" * 40] in calls


@pytest.mark.parametrize("mutation", ["branch", "base", "head_repo", "base_repo", "repository", "number", "fork"])
def test_other_identity_cannot_borrow_the_incident_benchmark_exception(mutation):
    value = native5_repair_event()
    if mutation == "branch": value["pull_request"]["head"]["ref"] = "other"
    elif mutation == "base": value["pull_request"]["base"]["sha"] = "c" * 40
    elif mutation == "head_repo": value["pull_request"]["head"]["repo"]["id"] = 1
    elif mutation == "base_repo": value["pull_request"]["base"]["repo"]["id"] = 1
    elif mutation == "repository": value["repository"]["full_name"] = "someone/SpicyStock"
    elif mutation == "number": value["number"] = 97
    else: value["pull_request"]["head"]["repo"]["full_name"] = "someone/SpicyStock"
    result = decide(value, git=lambda _: pytest.fail("unbound repair inspected Git"))
    assert result["run_required"] is True


@pytest.mark.parametrize("path", ["tools/historical_execution.py",
    "tools/historical_archive_codec.py", "src/breadth.py", ".github/workflows/tests.yml", ".gitleaks.toml",
    "tests/fixtures/changed.json", "tests/conftest.py", "tools/new-admission.py",
    gate.PARENT_RELEASE, "tools/historical-workflow-recovery.json",
    gate.NEW_EVIDENCE + "envelope-continuation/proof-runtime.json"])
def test_incident_exception_does_not_admit_unrelated_or_preserved_changes(path):
    run, _ = repair_git(paths=[path])
    result = decide(native5_repair_event(), git=run)
    assert result["run_required"] is True
    assert result["reason"] == "native5_repair_preservation_not_established"


@pytest.mark.parametrize("mutation", [gate.PARENT_RELEASE, "tools/historical_package.py",
    "tools/historical_execution.py", ".github/workflows/tests.yml",
    gate.NEW_EVIDENCE + "envelope-continuation/proof-runtime.json"])
@pytest.mark.parametrize("failure", ["changed", "missing"])
def test_partial_diff_cannot_hide_changed_or_unavailable_pinned_bytes(mutation, failure):
    run, _ = repair_git(**{"mutate" if failure == "changed" else "missing": mutation})
    result = decide(native5_repair_event(), git=run)
    assert result["run_required"] is True
    assert result["reason"] == "native5_repair_preservation_not_established"


def test_restored_initial_event_defect_repeats_the_forbidden_benchmark(monkeypatch):
    # The untouched initial-event gate necessarily requests another benchmark.
    value = native5_repair_event()
    run, _ = repair_git()
    assert decide(value, git=run)["run_required"] is False
    monkeypatch.setattr(gate, "_repair_decision", lambda *args: None)
    restored = decide(value, git=lambda _: pytest.fail("old opened-event gate should not inspect Git"))
    assert restored["run_required"] is True
    assert restored["reason"] == "initial_or_reopened_review_requires_measurement"
    # The unrelated docs-only synchronization control remains effective.
    assert decide(event(), git=git(["README.md"]))["run_required"] is False
