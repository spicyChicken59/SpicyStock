"""Full prospective guard admission with synthetic GitHub responses only.

No test invents an actual native-6 run or releases execution. The captured
native-5 failure remains one started job; no provider ledger is manufactured.
"""
from copy import deepcopy

import pytest

from tests.test_historical_execution_guard import (
    HISTORY, HISTORY_END, TODAY, jobs_path, run, setup,
)
from tools import historical_execution_guard as guard
from tools import historical_incident_recovery as incident


def artifact_path():
    return f"/actions/runs/{incident.FAILED_RUN_ID}/artifacts?per_page=100&page=1"


def verify_with(setup, api):
    policy, env, record, _, _, _ = setup
    return guard.verify(api, policy, env, record["mode"], 123, TODAY)


def test_full_native6_synthetic_admission_preserves_all_native_history(setup):
    result = run(setup)
    assert result["run_number"] == 6 and result["run_attempt"] == 1
    assert result["assignment_phase"] == 2 and result["mode"] == "real"
    assert result["recovery_contract_sha256"] == incident.RECOVERY_CONTRACT_SHA256
    history = result["history_verification"]
    assert history["schema"] == "historical-history-verification-v2"
    by_number = {record["run_number"]: record for record in history["runs"]}
    assert set(by_number) == {1, 2, 3, 4, 5, 6}
    assert [by_number[number]["attempt_jobs_count"] for number in (1, 2, 3)] == [0, 0, 0]
    assert by_number[4]["conclusion"] == "success"
    assert by_number[5]["id"] == incident.FAILED_RUN_ID
    assert by_number[5]["conclusion"] == "failure"
    assert by_number[5]["attempt_job_ids"] == [incident.FAILED_JOB_ID]
    assert by_number[5]["attempt_jobs_count"] == 1
    assert history["pre_acquisition_incident"]["artifacts_count"] == 0
    assert "ledger" not in history["pre_acquisition_incident"]
    assert setup[4].count(jobs_path(incident.FAILED_RUN_ID)) == 2
    assert setup[4].count(artifact_path()) == 2


def test_consumed_native5_comment_is_rejected_before_github_reads(setup):
    policy, env, record, _, calls, api = setup
    with pytest.raises(guard.GuardError, match="consumed_readiness_comment"):
        guard.verify(api, policy, env, record["mode"], incident.CONSUMED_READINESS_COMMENT_ID, TODAY)
    assert calls == []


@pytest.mark.parametrize("number,mode", [(4, "rehearsal"), (4, "real"), (5, "real"), (7, "real")])
def test_no_old_or_automatic_replacement_slot_can_reach_api(setup, number, mode):
    setup[1]["GITHUB_RUN_NUMBER"] = str(number)
    setup[2]["mode"] = mode
    with pytest.raises(guard.GuardError, match="rehearsal_slot_closed|execution_slot_consumed"):
        run(setup)
    assert setup[4] == []


def test_attempt2_context_remains_forbidden_before_any_read(setup):
    setup[1]["GITHUB_RUN_ATTEMPT"] = "2"
    with pytest.raises(guard.GuardError, match="execution_slot_consumed"):
        run(setup)
    assert setup[4] == []


@pytest.mark.parametrize("mutation", ["old_schema", "old_slot", "old_contract", "wrong_phase"])
def test_old_readiness_cannot_be_relabelled_as_replacement(setup, mutation):
    record = setup[2]
    if mutation == "old_schema":
        record["schema"] = "readiness-v3"
    elif mutation == "old_slot":
        record["run_number"] = 5
    elif mutation == "old_contract":
        record["recovery_contract_sha256"] = guard.ORIGINAL_RECOVERY_CONTRACT_SHA256
    else:
        record["assignment_phase"] = 1
    with pytest.raises(guard.GuardError, match="readiness_not_pass|stale_phase_readiness"):
        run(setup)


@pytest.mark.parametrize("field,value", [
    ("display_title", "historical-input-rehearsal"),
    ("name", "historical-input-rehearsal"),
    ("url", "https://api.github.com/repos/other/repo/actions/runs/36780349890"),
    ("jobs_url", "https://api.github.com/repos/other/repo/actions/runs/36780349890/jobs"),
    ("artifacts_url", "https://api.github.com/repos/other/repo/actions/runs/36780349890/artifacts"),
    ("previous_attempt_url", "https://api.github.com/other-attempt"),
])
def test_incident_individual_run_cannot_disagree_with_exact_collection(setup, field, value):
    setup[3][f"/actions/runs/{incident.FAILED_RUN_ID}"][field] = value
    with pytest.raises(guard.GuardError, match="run_detail_changed_or_missing|changed_reviewed_incident"):
        run(setup)


@pytest.mark.parametrize("changed", ["jobs", "artifacts", "jobs_inaccessible", "artifacts_inaccessible"])
def test_second_authoritative_incident_read_cannot_change_or_disappear(setup, changed):
    calls = 0
    api = setup[-1]
    path_to_change = jobs_path(incident.FAILED_RUN_ID) if changed.startswith("jobs") else artifact_path()

    def changing(path):
        nonlocal calls
        value = api(path)
        if path == path_to_change:
            calls += 1
            if calls == 2:
                if changed.endswith("inaccessible"):
                    raise guard.GuardError("github_read_failed")
                if changed == "jobs":
                    value["jobs"][0]["steps"][9]["conclusion"] = "success"
                else:
                    value = {"total_count": 1, "artifacts": [{"id": 123456}]}
        return value

    with pytest.raises(guard.GuardError, match="incident_changed_during_read|consumed_or_invalid_history|github_read_failed"):
        verify_with(setup, changing)
    assert calls == 2


@pytest.mark.parametrize("broken", ["missing", "duplicate", "unknown", "partial"])
def test_complete_history_is_required_and_no_record_may_be_skipped(setup, broken):
    responses = setup[3]
    runs = responses[HISTORY]["workflow_runs"]
    if broken == "missing":
        runs[:] = [item for item in runs if item["id"] != incident.FAILED_RUN_ID]
        responses[HISTORY]["total_count"] = responses[HISTORY_END]["total_count"] = 5
    elif broken == "duplicate":
        runs[0] = deepcopy(runs[1])
    elif broken == "unknown":
        extra = deepcopy(runs[-1])
        extra.update(id=987654321, run_number=7)
        runs.append(extra)
        responses[HISTORY]["total_count"] = responses[HISTORY_END]["total_count"] = 7
    else:
        runs.pop()
    with pytest.raises(guard.GuardError, match="incomplete_or_consumed_history|duplicate_run_history|consumed_or_invalid_history|incomplete_run_history"):
        run(setup)


@pytest.mark.parametrize("conclusion", ["failure", "cancelled", "success"])
def test_spent_native6_is_not_another_fresh_real_allowance(setup, conclusion):
    current_id = int(setup[1]["GITHUB_RUN_ID"])
    for item in setup[3][HISTORY]["workflow_runs"]:
        if item["id"] == current_id:
            item.update(status="completed", conclusion=conclusion)
    setup[3][f"/actions/runs/{current_id}"].update(status="completed", conclusion=conclusion)
    setup[3][jobs_path(current_id)]["jobs"][0].update(status="completed", conclusion=conclusion)
    with pytest.raises(guard.GuardError, match="current_run_not_durable"):
        run(setup)


def test_restored_five_record_collector_fails_while_corrected_control_passes(setup, monkeypatch):
    assert run(setup)["run_number"] == 6

    def restored(api, workflow_id):
        return guard.collection(api, f"/actions/workflows/{workflow_id}/runs", "workflow_runs", 5)

    with monkeypatch.context() as scoped:
        scoped.setattr(guard, "history", restored)
        with pytest.raises(guard.GuardError, match="consumed_or_invalid_history"):
            run(setup)
    assert run(setup)["run_number"] == 6


def test_admission_slot_agrees_with_the_explicit_pinned_incident_contract():
    number, phase, attempt = incident.replacement_slot()
    assert guard.phase_slot("real") == (number, phase) == (6, 2)
    assert attempt == 1
