"""An artifact cannot suppress a scheduled run unless its record reached git."""
from copy import deepcopy

import pytest

from src.pipeline import UNIVERSE_FILE_LABEL
from tests.test_docs_are_true import EDT_CRON, _guard_shell, _run_guard


RECEIPT = {"run": {"date": "2026-09-08", "type": "evening", "fixture": False,
                   "universe": {"label": UNIVERSE_FILE_LABEL}}, "candidates": []}


@pytest.mark.parametrize("branch,published,change,expected", [
    ("main", True, None, "go=false"),
    ("rehearsal-branch", True, None, "go=true"),
    (None, True, None, "go=true"),
    # Same branch and a successful upload, but its persist step failed.
    ("main", False, None, "go=true"),
    ("main", True, {"date": "2026-09-04"}, "go=true"),
    ("main", True, {"fixture": True}, "go=true"),
    ("main", True, {"type": "morning"}, "go=true"),
    ("main", True, {"universe": {"label": "--tickers TEST"}}, "go=true"),
])
def test_the_tuesday_cron_requires_a_matching_committed_universe_run(
    tmp_path, branch, published, change, expected
):
    receipt = deepcopy(RECEIPT)
    receipt["run"].update(change or {})
    artifact = {"name": "evening-2026-09-08-999", "workflow_run": {"head_branch": branch}}
    result = _run_guard(tmp_path, artifacts=[artifact], event="schedule", schedule=EDT_CRON,
                        today_et="2026-09-08", offset="-0400", published=published, snapshot=receipt)
    assert result == expected
    # The workflow's label must match the pipeline's actual file-scan label.
    assert f"--arg universe '{UNIVERSE_FILE_LABEL}'" in _guard_shell()


@pytest.mark.parametrize("api_error", [True, "partial"])
def test_an_artifact_api_failure_cannot_silence_the_cron(tmp_path, api_error):
    assert _run_guard(tmp_path, artifacts=[], event="schedule", schedule=EDT_CRON,
                      today_et="2026-09-08", offset="-0400", api_error=api_error) == "go=true"
