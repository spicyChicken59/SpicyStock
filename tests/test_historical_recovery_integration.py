"""The revised guard's actual output crosses every synthetic execution boundary.

GitHub responses are synthetic/captured metadata; provider sockets remain
blocked by conftest. Age uses only the existing ephemeral test-key fixture.
"""
from copy import deepcopy
import base64
import hashlib
import json

import pytest

from tests.test_historical_execution import run_setup
from tests.test_historical_execution_guard import setup as github_setup
from tests.test_historical_execution_guard import make_rehearsal
from tests.test_historical_execution_guard import TODAY
from tests.test_historical_package import age
from tools import historical_acquisition as acquisition
from tools import historical_execution as runner
from tools import historical_execution_guard as guard
from tools import historical_package as package


@pytest.fixture
def pipeline(github_setup, run_setup, monkeypatch, tmp_path):
    """Use the public guard CLI, not a hand-assembled execution document."""
    manifest, storage, _, _ = run_setup
    real_baseline = deepcopy(github_setup[1:4])
    make_rehearsal(github_setup)
    policy, env, readiness, responses, api_calls, api = github_setup
    identity = acquisition.validate_manifest(manifest)
    readiness["manifest_sha256"] = identity
    monkeypatch.setattr(guard, "MANIFEST", identity)
    monkeypatch.setattr(guard, "load_policy", lambda path=None: deepcopy(policy))
    monkeypatch.setattr(runner, "_checkout_sha", lambda: readiness["checkout_sha"])
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "github-output"))
    monkeypatch.setattr(guard, "GitHub", lambda token: api)
    for key in runner.SECRETS:
        monkeypatch.delenv(key, raising=False)
    provider_calls = []
    def no_provider():
        provider_calls.append(True)
        pytest.fail("provider transport must never be constructed in these tests")
    monkeypatch.setattr(acquisition, "AlpacaTransport", no_provider)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_bytes(acquisition.encode(manifest))
    monkeypatch.setattr(guard, "MANIFEST_PATH", manifest_path)
    case = {"manifest": manifest, "manifest_path": manifest_path, "storage": storage,
            "policy": policy, "readiness": readiness, "responses": responses, "env": env,
            "api": api, "api_calls": api_calls, "provider_calls": provider_calls,
            "real_baseline": real_baseline,
            "guard_dir": tmp_path / "guard", "policy_path": tmp_path / "policy.json"}
    bind_synthetic_release(case)
    return case


def bind_synthetic_release(case):
    """The tiny invented manifest/key is part of the invented release evidence."""
    key = f"/contents/{guard.RELEASE_EVIDENCE_PATH}?ref={case['readiness']['checkout_sha']}"
    entry = case["responses"][key]
    document = json.loads(base64.b64decode(entry["content"]))
    document.update(manifest_sha256=case["readiness"]["manifest_sha256"],
                    recipient_sha256=case["readiness"]["recipient_sha256"])
    raw = guard.encode(document)
    entry["content"] = base64.b64encode(raw).decode()
    case["readiness"]["release_evidence_sha256"] = hashlib.sha256(raw).hexdigest()


def guard_command(case, monkeypatch):
    bind_synthetic_release(case)
    case["policy_path"].write_bytes(acquisition.encode(case["policy"]))
    with monkeypatch.context() as scoped:
        scoped.setenv("GITHUB_TOKEN", "synthetic-read-token")
        code = guard.main(["--policy", str(case["policy_path"]), "--readiness-comment-id", "123",
                           "--mode", case["readiness"]["mode"], "--output-dir", str(case["guard_dir"]),
                           "--storage-root", str(case["storage"])])
    return code


def wrapper_command(case, mode, *, preflight=False, storage=None):
    args = ["--mode", mode, "--manifest", str(case["manifest_path"]),
            "--storage", str(storage or case["storage"]),
            "--execution", str(case["guard_dir"] / "execution.json")]
    if mode != "offline":
        args.extend(["--approval", str(case["guard_dir"] / "approval.json")])
    if preflight:
        args.append("--preflight-only")
    return runner.main(args)


def read_guard(case):
    return json.loads((case["guard_dir"] / "execution.json").read_bytes())


def assert_phase_one(binding):
    assert binding["run_number"] == 4
    assert binding["assignment_phase"] == 1
    assert binding["run_attempt"] == 1
    assert binding["workflow_id"] == 369770564
    assert binding["repository_id"] == 1352997802
    assert binding["workflow_path"] == ".github/workflows/historical-input-proof.yml"
    assert binding["mode"] == "rehearsal"
    assert len(binding["recovery_contract_sha256"]) == 64


def test_actual_guard_output_drives_native_four_wrapper_and_offline_replay(pipeline, monkeypatch):
    assert guard_command(pipeline, monkeypatch) == 0
    record = read_guard(pipeline)
    assert record["schema"] == "historical-execution-v3"
    assert_phase_one(record)
    assert wrapper_command(pipeline, "rehearsal", preflight=True) == 0
    assert not pipeline["storage"].exists()
    assert not pipeline["provider_calls"]
    assert wrapper_command(pipeline, "rehearsal") == 0
    ledger = (pipeline["storage"] / "ledger.sqlite3").read_bytes()
    assert wrapper_command(pipeline, "offline") == 0
    assert (pipeline["storage"] / "ledger.sqlite3").read_bytes() == ledger
    diagnostic = json.loads((pipeline["storage"] / "execution-diagnostics.json").read_bytes())
    assert_phase_one(diagnostic["execution_binding"])
    assert diagnostic["execution_binding"] == guard.validate_phase_binding(record)
    assert diagnostic["prior_acquisition"]["synthetic_transport_calls"] == 7
    assert diagnostic["new_provider_requests"] == 0
    assert not pipeline["provider_calls"]


def test_guard_binding_survives_actual_encryption_recovery_and_offline_replay(pipeline, age, monkeypatch, tmp_path):
    recipient = age[1][0][1]
    pipeline["policy"]["recipient"] = recipient
    fingerprint = package.recipient_fingerprint(recipient)
    pipeline["policy"]["recipient_sha256"] = fingerprint
    monkeypatch.setattr(guard, "RECIPIENT_SHA256", fingerprint)
    pipeline["readiness"]["recipient_sha256"] = fingerprint
    assert guard_command(pipeline, monkeypatch) == 0
    record = read_guard(pipeline)
    assert wrapper_command(pipeline, "rehearsal") == 0
    assert wrapper_command(pipeline, "offline") == 0
    before = {str(path.relative_to(pipeline["storage"])): path.read_bytes()
              for path in pipeline["storage"].rglob("*") if path.is_file() and path.name != "acquisition.lock"}
    diagnostic = json.loads(before["execution-diagnostics.json"])
    metadata = package.execution_metadata(record, status=diagnostic["status"])
    assert_phase_one(metadata)
    delivery, recovered = tmp_path / "delivery", tmp_path / "recovered"
    receipt = package.package_evidence(pipeline["storage"], pipeline["manifest"], delivery,
                                      age_binary=age[0], recipient=recipient, execution=metadata,
                                      diagnostics={"execution_guard": record})
    assert receipt["schema"] == "historical-encrypted-receipt-v4"
    assert receipt["delivery_envelope"] == "historical-delivery-envelope-v1"
    assert_phase_one(receipt)
    index = package.recover_package(delivery / package.CIPHERTEXT_NAME, receipt, recovered,
                                    age_binary=age[0], identity=age[1][0][0], manifest=pipeline["manifest"],
                                    expected_execution=metadata)
    assert index["schema"] == "historical-private-package-v4"
    assert index["delivery_envelope"] == receipt["delivery_envelope"]
    assert index["execution"] == metadata
    assert all((recovered / name).read_bytes() == raw for name, raw in before.items())
    assert wrapper_command(pipeline, "offline", storage=recovered) == 0
    assert (recovered / "ledger.sqlite3").read_bytes() == before["ledger.sqlite3"]
    for day in pipeline["manifest"]["populations"]:
        name = "reconciliation-" + day + ".json"
        assert (recovered / name).read_bytes() == before[name]
        assert json.loads(before[name])["B"]["status"] == "BLOCKED"
    rebound = json.loads((recovered / "execution-diagnostics.json").read_bytes())
    assert rebound["execution_binding"] == guard.validate_phase_binding(record)
    assert not pipeline["provider_calls"]


@pytest.mark.parametrize("field,value", [
    ("schema", "historical-execution-v1"), ("run_number", 1), ("assignment_phase", 4),
    ("run_attempt", 2), ("recovery_contract_sha256", "0" * 64), ("workflow_id", 123),
    ("schema", "historical-execution-v2"), ("compatibility_contract_sha256", "1" * 64),
    ("release_evidence_sha256", "0" * 64),
])
def test_guard_output_tampering_stops_wrapper_before_storage_or_transport(pipeline, monkeypatch, field, value):
    assert guard_command(pipeline, monkeypatch) == 0
    record = read_guard(pipeline)
    record[field] = value
    (pipeline["guard_dir"] / "execution.json").write_bytes(acquisition.encode(record))
    assert wrapper_command(pipeline, "rehearsal", preflight=True) == 2
    assert wrapper_command(pipeline, "rehearsal") == 2
    assert not pipeline["storage"].exists()
    assert not pipeline["provider_calls"]


def test_rehearsal_guard_cannot_authorize_real_or_spoof_native_number(pipeline, monkeypatch):
    assert guard_command(pipeline, monkeypatch) == 0
    assert wrapper_command(pipeline, "real", preflight=True) == 2
    assert wrapper_command(pipeline, "real") == 2
    monkeypatch.setenv("GITHUB_RUN_NUMBER", "1")
    assert wrapper_command(pipeline, "rehearsal") == 2
    assert not pipeline["storage"].exists()
    assert not pipeline["provider_calls"]


def test_offline_cannot_relabel_ledger_with_another_valid_phase_identity(pipeline, monkeypatch):
    assert guard_command(pipeline, monkeypatch) == 0
    assert wrapper_command(pipeline, "rehearsal") == 0
    record = read_guard(pipeline)
    record["run_id"] += 1000
    # The shape and phase remain valid: rejection must bind the retained data
    # to its actual acquisition, rather than incidentally reject another field.
    guard.validate_phase_binding(record)
    before = {str(path.relative_to(pipeline["storage"])): path.read_bytes()
              for path in pipeline["storage"].rglob("*") if path.is_file()}
    (pipeline["guard_dir"] / "execution.json").write_bytes(acquisition.encode(record))
    assert wrapper_command(pipeline, "offline") == 2
    after = {str(path.relative_to(pipeline["storage"])): path.read_bytes()
             for path in pipeline["storage"].rglob("*") if path.is_file()}
    assert after == before
    assert not pipeline["provider_calls"]


def test_package_cli_rejects_relabelled_guard_before_encryption(pipeline, monkeypatch, tmp_path):
    assert guard_command(pipeline, monkeypatch) == 0
    assert wrapper_command(pipeline, "rehearsal") == 0
    record = read_guard(pipeline)
    record["run_id"] += 1000
    guard.validate_phase_binding(record)
    (pipeline["guard_dir"] / "execution.json").write_bytes(acquisition.encode(record))
    encryption_calls = []
    def no_encryption(*args, **kwargs):
        encryption_calls.append(True)
        raise RuntimeError("encryption must not start for mismatched retained identity")
    monkeypatch.setattr(package, "_age", no_encryption)
    delivery = tmp_path / "delivery"
    assert package.main(["package", "--manifest", str(pipeline["manifest_path"]),
                         "--storage", str(pipeline["storage"]),
                         "--execution", str(pipeline["guard_dir"] / "execution.json"),
                         "--policy", str(pipeline["policy_path"]), "--age", str(tmp_path / "unused-age"),
                         "--delivery", str(delivery)]) == 2
    assert encryption_calls == []
    assert not delivery.exists()
    assert not pipeline["provider_calls"]


@pytest.mark.parametrize("fault", ["old_readiness", "wrong_contract", "missing_owner_authorization_for_real"])
def test_failed_guard_has_no_output_that_wrapper_can_use(pipeline, monkeypatch, fault):
    if fault == "old_readiness":
        pipeline["readiness"]["schema"] = "readiness-v1"
    elif fault == "wrong_contract":
        pipeline["readiness"]["recovery_contract_sha256"] = "0" * 64
    else:
        real_env, real_record, real_responses = deepcopy(pipeline["real_baseline"])
        real_record["manifest_sha256"] = acquisition.validate_manifest(pipeline["manifest"])
        pipeline["readiness"].clear()
        pipeline["readiness"].update(real_record)
        pipeline["responses"].clear()
        pipeline["responses"].update(real_responses)
        for key, value in real_env.items():
            monkeypatch.setenv(key, value)
        del pipeline["readiness"]["evidence"]["owner_authorization"]
    expected = {"old_readiness": "readiness_not_pass", "wrong_contract": "stale_phase_readiness",
                "missing_owner_authorization_for_real": "missing_readiness_evidence"}[fault]
    with pytest.raises(guard.GuardError, match=expected):
        guard.validate_readiness(pipeline["api"]("/issues/comments/123"), pipeline["policy"],
                                 pipeline["readiness"]["mode"], TODAY)
    assert guard_command(pipeline, monkeypatch) == 2
    assert not (pipeline["guard_dir"] / "execution.json").exists()
    assert wrapper_command(pipeline, pipeline["readiness"]["mode"]) == 2
    assert not pipeline["storage"].exists()
    assert not pipeline["provider_calls"]


@pytest.mark.parametrize("fault", ["unknown_fourth_validation_record", "reviewed_exception_has_a_job"])
def test_disallowed_history_cannot_emit_a_runnable_guard_record(pipeline, monkeypatch, fault):
    responses = pipeline["responses"]
    history_key = f"/actions/workflows/{guard.WORKFLOW_ID}/runs?per_page=100&page=1"
    runs = responses[history_key]["workflow_runs"]
    exception = next(run for run in runs if run["run_number"] == 1)
    if fault == "unknown_fourth_validation_record":
        unknown = deepcopy(exception)
        unknown.update(id=999, run_number=4)
        current = next(index for index, run in enumerate(runs) if run["run_number"] == 4)
        runs[current] = unknown
        responses["/actions/runs/999"] = deepcopy(unknown)
        responses["/actions/runs/999/attempts/1/jobs?per_page=100&page=1"] = {"total_count": 0, "jobs": []}
        expected = "unaccounted_or_retried_run"
    else:
        run_id = exception["id"]
        jobs_key = f"/actions/runs/{run_id}/attempts/1/jobs?per_page=100&page="
        responses[jobs_key + "1"] = {"total_count": 1, "jobs": [{
            "id": 777, "run_id": run_id, "name": "execution", "status": "completed",
            "conclusion": "failure", "started_at": "2026-09-28T12:00:00Z"}]}
        responses[jobs_key + "2"] = {"total_count": 1, "jobs": []}
        expected = "reviewed_exception_has_jobs"
    with pytest.raises(guard.GuardError, match=expected):
        guard.verify(pipeline["api"], pipeline["policy"], pipeline["env"], "rehearsal", 123, TODAY)
    assert guard_command(pipeline, monkeypatch) == 2
    assert not (pipeline["guard_dir"] / "execution.json").exists()
    assert wrapper_command(pipeline, "rehearsal") == 2
    assert not pipeline["storage"].exists()
    assert not pipeline["provider_calls"]
