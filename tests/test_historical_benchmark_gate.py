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


@pytest.fixture
def comparison_receipt():
    raw = (Path(__file__).resolve().parents[1] / gate.CORRECTION_RECEIPT).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == gate.CORRECTION_RECEIPT_SHA256
    return raw


def correction_git(receipt, *, paths=None, observed=None, ancestor=0, diff=0, show=0):
    baseline_paths = paths if paths is not None else sorted(gate.CORRECTION_PATHS | {gate.CORRECTION_RECEIPT})
    calls = []
    def run(arguments):
        calls.append(arguments)
        if arguments == ["merge-base", "--is-ancestor", "a" * 40, "b" * 40]:
            return SimpleNamespace(returncode=0)
        if arguments == ["merge-base", "--is-ancestor", gate.CORRECTION_BASE, "b" * 40]:
            return SimpleNamespace(returncode=ancestor)
        if arguments == ["show", "b" * 40 + ":" + gate.CORRECTION_RECEIPT]:
            return SimpleNamespace(returncode=show, stdout=receipt)
        assert arguments[:4] == ["diff", "--name-only", "-z", "--no-renames"]
        assert arguments[4:] in (["a" * 40, "b" * 40], [gate.CORRECTION_BASE, "b" * 40])
        full_range = arguments[4] == gate.CORRECTION_BASE
        values = baseline_paths if full_range or observed is None else observed
        return SimpleNamespace(returncode=diff if full_range else 0,
                               stdout=b"\0".join(p.encode() for p in values) + b"\0")
    return run, calls


def test_pr97_defers_only_exact_failed_receipt_and_complete_reviewed_range(comparison_receipt):
    run, calls = correction_git(comparison_receipt)
    result = decide(correction_event(), git=run)
    assert result["run_required"] is False and result["status"] == "NOT RUN"
    assert result["reason"] == "pr97_bounded_comparison_failed_no_further_benchmark_authorized"
    assert result["reviewed_baseline"] == "bd779c2a1ce14b8a7361c4866678e55e29ae18f8"
    assert result["comparison_receipt_sha256"] == "77ee1a171b9c0d0361c18ebfabda17a3e6d63e6287a26c24881295b792368a7e"
    assert result["reviewed_range_changed_paths"] == sorted(gate.CORRECTION_PATHS | {gate.CORRECTION_RECEIPT})
    assert calls[-1] == ["show", "b" * 40 + ":" + gate.CORRECTION_RECEIPT]
    assert result["claim"] == "This decision is not a benchmark result or execution release."


@pytest.mark.parametrize("where,key,value", [
    ("event", "number", 98), ("pr", "number", 96), ("pr", "number", "97"),
    ("repository", "full_name", "other/SpicyStock"), ("repository", "id", 1),
    ("base", "full_name", "other/SpicyStock"), ("head", "full_name", "fork/SpicyStock"),
    ("head", "id", "1352997802"),
])
def test_correction_does_not_apply_to_another_pr_repo_or_fork(comparison_receipt, where, key, value):
    payload = correction_event()
    targets = {"event": payload, "pr": payload["pull_request"], "repository": payload["repository"],
               "base": payload["pull_request"]["base"]["repo"], "head": payload["pull_request"]["head"]["repo"]}
    targets[where][key] = value
    run, calls = correction_git(comparison_receipt)
    assert decide(payload, git=run)["run_required"] is True
    assert not any(arguments[0] == "show" for arguments in calls)


@pytest.mark.parametrize("path", ["tools/historical_archive_codec.py", "src/breadth.py",
    ".github/workflows/tests.yml", "tools/historical_execution_guard.py", "tools/requirements-historical-archive.txt",
    "tests/fixtures/new-input.json", "unknown-file", "docs/input-truthfulness/old-evidence.json"])
def test_correction_checks_earlier_changes_even_when_latest_push_is_docs_only(comparison_receipt, path):
    run, calls = correction_git(comparison_receipt, paths=["README.md", path], observed=["README.md"])
    result = decide(correction_event(), git=run)
    assert result["run_required"] is True
    assert result["reason"] == "pr97_correction_deferral_unverified"
    assert not any(arguments[0] == "show" for arguments in calls)


@pytest.mark.parametrize("options", [{"ancestor": 1}, {"ancestor": 128}, {"diff": 128},
    {"show": 128}, {"paths": []}, {"paths": ["../README.md"]}])
def test_missing_baseline_diff_or_head_receipt_cannot_defer(comparison_receipt, options):
    run, _ = correction_git(comparison_receipt, **options)
    assert decide(correction_event(), git=run)["run_required"] is True


@pytest.mark.parametrize("raw", [b"", b"{}", b"not-json"])
def test_missing_or_changed_receipt_bytes_cannot_defer(raw):
    run, _ = correction_git(raw)
    assert decide(correction_event(), git=run)["run_required"] is True


def test_even_whitespace_changes_to_retained_receipt_cannot_defer(comparison_receipt):
    run, _ = correction_git(comparison_receipt + b"\n")
    assert decide(correction_event(), git=run)["run_required"] is True


@pytest.mark.parametrize("field,value", [("status", "PASS"), ("comparison_status", "PASS"),
    ("archive_bytes", 199 * 1024 * 1024), ("archive_bytes", True), ("archive_headroom_bytes", 0)])
def test_capacity_failure_is_explicit_in_addition_to_receipt_hash(comparison_receipt, monkeypatch, field, value):
    receipt = json.loads(comparison_receipt)
    comparison = receipt["child_result"]["archive_comparison"]
    if field == "status":
        receipt[field] = value
    else:
        comparison["status" if field == "comparison_status" else field] = value
    raw = json.dumps(receipt).encode()
    # Independently exercise semantic refusal after the byte-binding boundary.
    monkeypatch.setattr(gate, "CORRECTION_RECEIPT_SHA256", hashlib.sha256(raw).hexdigest())
    run, _ = correction_git(raw)
    assert decide(correction_event(), git=run)["run_required"] is True


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
    assert "--representative" in runs and "--setup-seconds" in runs
    artifact = next(s for s in job["steps"] if s.get("uses", "").startswith("actions/upload-artifact@"))
    assert artifact["if"] == "always()"
    assert set(Path(line.strip()).name for line in artifact["with"]["path"].splitlines()) == {
        "benchmark-preflight.json", "benchmark-result.json", "runtime-profile.json", "synthetic-member-inventory.json"}
    assert ".age" not in artifact["with"]["path"] and ".tar" not in artifact["with"]["path"]
    normal_runs = "\n".join(s.get("run", "") for s in value["jobs"]["pytest"]["steps"])
    assert normal_runs.index("--require-hashes") < normal_runs.index("-r requirements-dev.txt")
