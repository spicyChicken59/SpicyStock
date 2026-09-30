"""Exact public incident observations plus explicitly synthetic corruptions.

These pure controls do not represent a live native-6 job or readiness release.
The full history collector and wrapper admission are tested separately.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from tools import historical_incident_recovery as incident

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/input-truthfulness/2026-09-30-delivery-readiness-evidence/native5-recovery"


@pytest.fixture
def captured():
    observation = json.loads((EVIDENCE / "incident-observation.json").read_bytes())
    return observation["run"], observation["jobs"], observation["artifacts"]


def test_retained_observation_and_log_have_the_bound_bytes(captured):
    contract = incident.incident_contract()
    raw = (ROOT / contract["evidence"]["path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == contract["evidence"]["sha256"]
    observed = json.loads(raw)
    log = (EVIDENCE / observed["job_log"]["path"]).read_bytes()
    assert hashlib.sha256(log).hexdigest() == observed["job_log"]["sha256"]
    assert b"READINESS_COMMENT_ID:     5920107119\n" in log
    assert observed["history_native_numbers"] == [1, 2, 3, 4, 5]
    assert observed["history_run_ids"] == [36520481662, 36521323183, 36524147152, 36570997883, 36780349890]
    assert observed["provider_requests"] == 0
    assert "No acquisition ledger exists" in observed["provider_request_basis"]


def test_old_zero_job_contract_is_preserved_and_cannot_classify_this_job(captured):
    old = json.loads(incident.ORIGINAL_RECOVERY_PATH.read_bytes())
    assert hashlib.sha256(incident.encode(old)).hexdigest() == incident.ORIGINAL_RECOVERY_CONTRACT_SHA256
    assert [entry["run_number"] for entry in old["exceptions"]] == [1, 2, 3]
    assert all(entry["jobs_total_count"] == 0 for entry in old["exceptions"])
    run, jobs, _ = captured
    assert len(jobs) == 1
    assert not any(entry["id"] == run["id"] for entry in old["exceptions"])
    assert old["slots"]["real"]["run_number"] == 5


def test_exact_started_failure_has_one_new_explicit_relation(captured):
    result = incident.validate_incident(*captured)
    assert result["classification"] == "reviewed-pre-acquisition-failure"
    assert result["run_id"] == 36780349890
    assert result["job_id"] == 110108745578
    assert result["run_number"] == 5
    assert result["run_attempt"] == 1
    assert "ledger" not in result
    assert incident.replacement_slot() == (6, 2, 1)
    contract = incident.incident_contract()
    assert contract["consumed_readiness_comment_id"] == 5920107119
    assert contract["replacement"]["requires_new_post_merge_readiness"] is True


@pytest.mark.parametrize("field,value", [
    ("id", 36780349891), ("id", "36780349890"), ("run_number", 6),
    ("run_attempt", 2), ("run_attempt", True), ("event", "push"),
    ("head_branch", "fix/native5-readiness-input-recovery"),
    ("head_sha", "8cc49dceb47d6fad8206c44caf091b1f2dadee14"),
    ("path", ".github/workflows/other.yml"), ("workflow_id", 369770565),
    ("name", "historical-input-rehearsal"), ("display_title", "historical-input-rehearsal"),
    ("status", "in_progress"), ("conclusion", "cancelled"), ("conclusion", "success"),
    ("url", "https://api.github.com/repos/other/SpicyStock/actions/runs/36780349890"),
    ("previous_attempt_url", "https://api.github.com/earlier-attempt"),
    ("repository", {"id": 1352997803, "full_name": "spicyChicken59/SpicyStock"}),
    ("head_repository", {"id": 1352997802, "full_name": "other/SpicyStock"}),
])
def test_every_mutated_run_identity_is_refused(captured, field, value):
    run, jobs, artifacts = captured
    run[field] = value
    with pytest.raises(incident.IncidentError, match="changed_native5_run"):
        incident.validate_incident(run, jobs, artifacts)


@pytest.mark.parametrize("field,value", [
    ("id", 110108745579), ("run_id", 36780349891), ("run_attempt", 2),
    ("name", "other"), ("workflow_name", "historical-input-rehearsal"),
    ("head_sha", "8cc49dceb47d6fad8206c44caf091b1f2dadee14"), ("head_branch", "other"),
    ("run_url", "https://api.github.com/repos/spicyChicken59/SpicyStock/actions/runs/36780349891"),
    ("status", "in_progress"), ("conclusion", "cancelled"), ("conclusion", "success"),
])
def test_every_mutated_job_identity_is_refused(captured, field, value):
    run, jobs, artifacts = captured
    jobs[0][field] = value
    with pytest.raises(incident.IncidentError, match="changed_native5_job"):
        incident.validate_incident(run, jobs, artifacts)


@pytest.mark.parametrize("step", range(15))
@pytest.mark.parametrize("field", ["name", "number", "status", "conclusion"])
def test_each_bound_step_field_is_required(captured, step, field):
    run, jobs, artifacts = captured
    jobs[0]["steps"][step][field] = 99 if field == "number" else "changed"
    with pytest.raises(incident.IncidentError, match="changed_native5_job"):
        incident.validate_incident(run, jobs, artifacts)


@pytest.mark.parametrize("outcome", ["success", "failure", "cancelled", None])
def test_empty_artifacts_do_not_excuse_acquisition_start(captured, outcome):
    run, jobs, artifacts = captured
    assert artifacts == []
    acquisition = jobs[0]["steps"][9]
    acquisition["conclusion"] = outcome
    with pytest.raises(incident.IncidentError, match="changed_native5_job"):
        incident.validate_incident(run, jobs, artifacts)


@pytest.mark.parametrize("kind", ["missing_step", "extra_step", "duplicate_step", "wrong_order", "missing_steps"])
def test_incomplete_ambiguous_or_unordered_steps_are_refused(captured, kind):
    run, jobs, artifacts = captured
    steps = jobs[0]["steps"]
    if kind == "missing_step":
        steps.pop()
    elif kind == "extra_step":
        steps.append(deepcopy(steps[-1]))
    elif kind == "duplicate_step":
        steps[8] = deepcopy(steps[7])
    elif kind == "wrong_order":
        steps[5], steps[6] = steps[6], steps[5]
    else:
        del jobs[0]["steps"]
    with pytest.raises(incident.IncidentError, match="changed_native5_job"):
        incident.validate_incident(run, jobs, artifacts)


@pytest.mark.parametrize("bad_jobs", [None, [], {}, {"total_count": 0, "jobs": []}, [None]])
def test_missing_inaccessible_or_empty_jobs_never_become_exception(captured, bad_jobs):
    run, _, artifacts = captured
    with pytest.raises(incident.IncidentError):
        incident.validate_incident(run, bad_jobs, artifacts)


def test_duplicate_execution_job_is_refused(captured):
    run, jobs, artifacts = captured
    jobs.append(deepcopy(jobs[0]))
    with pytest.raises(incident.IncidentError, match="changed_native5_jobs"):
        incident.validate_incident(run, jobs, artifacts)


@pytest.mark.parametrize("bad_artifacts", [None, {}, {"total_count": 0, "artifacts": []}, [{"id": 123}]])
def test_artifacts_require_positive_complete_collection(captured, bad_artifacts):
    run, jobs, _ = captured
    with pytest.raises(incident.IncidentError, match="changed_native5_artifacts"):
        incident.validate_incident(run, jobs, bad_artifacts)


def test_incidental_api_fields_do_not_redefine_the_incident(captured):
    run, jobs, artifacts = captured
    run["updated_at"] = "a later API refresh"
    jobs[0]["runner_name"] = "unrelated platform metadata"
    jobs[0]["steps"][0]["started_at"] = "bound evidence deliberately omits timing fields"
    assert incident.validate_incident(run, jobs, artifacts)["job_id"] == 110108745578


@pytest.mark.parametrize("changed", ["schema", "replacement", "exception"])
def test_changed_or_unsupported_contract_is_refused(tmp_path, monkeypatch, captured, changed):
    contract = incident.incident_contract()
    contract[changed] = "unsupported"
    path = tmp_path / "contract.json"
    path.write_bytes(incident.encode(contract))
    monkeypatch.setattr(incident, "RECOVERY_PATH", path)
    with pytest.raises(incident.IncidentError, match="changed_incident_contract"):
        incident.validate_incident(*captured)


def test_preserved_original_contract_remains_a_required_pin(tmp_path, monkeypatch, captured):
    path = tmp_path / "old.json"
    path.write_bytes(b'{}\n')
    monkeypatch.setattr(incident, "ORIGINAL_RECOVERY_PATH", path)
    with pytest.raises(incident.IncidentError, match="changed_incident_contract"):
        incident.validate_incident(*captured)


def test_duplicate_keys_and_missing_contract_fail_closed(tmp_path, monkeypatch):
    path = tmp_path / "contract.json"
    monkeypatch.setattr(incident, "RECOVERY_PATH", path)
    with pytest.raises(incident.IncidentError, match="missing_incident_contract"):
        incident.incident_contract()
    path.write_bytes(b'{"schema":"one","schema":"two"}')
    with pytest.raises(incident.IncidentError, match="duplicate_incident_json_key"):
        incident.incident_contract()
