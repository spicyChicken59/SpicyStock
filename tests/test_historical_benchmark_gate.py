"""An unknown or incomplete PR range runs; skips are never a PASS claim."""
from types import SimpleNamespace
from pathlib import Path
import re

import pytest
import yaml

from tools.historical_benchmark_gate import decide


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
