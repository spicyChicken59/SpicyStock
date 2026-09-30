"""Prospective source/release compatibility using only invented API responses."""
from copy import deepcopy
import base64
import hashlib
import json

import pytest

from tests.test_historical_execution_guard import setup, run, APPROVED, CURRENT, OLD_RUN, jobs_path
from tools import historical_execution_guard as guard


def release_document(case):
    entry = case[3][f"/contents/{guard.RELEASE_EVIDENCE_PATH}?ref={APPROVED}"]
    return json.loads(base64.b64decode(entry["content"]))


def replace_release(case, document):
    raw = guard.encode(document)
    case[2]["release_evidence_sha256"] = hashlib.sha256(raw).hexdigest()
    case[3][f"/contents/{guard.RELEASE_EVIDENCE_PATH}?ref={APPROVED}"]["content"] = base64.b64encode(raw).decode()


def test_exact_old_transport_and_new_reviewed_source_are_separate(setup):
    result = run(setup)
    old = result["evidence"]["local_recovery"]
    assert old["rehearsal_run_id"] == OLD_RUN and old["checkout_sha"] != result["checkout_sha"]
    assert old["artifact_id"] == 11033808340
    assert result["schema"] == "historical-execution-v3"
    assert result["run_number"] == 5 and result["assignment_phase"] == 2
    assert result["release_evidence_sha256"] == setup[2]["release_evidence_sha256"]
    assert guard.validate_phase_binding(result)["compatibility_contract_sha256"] == guard.COMPATIBILITY_CONTRACT_SHA256


@pytest.mark.parametrize("field", list(guard.compatibility_contract()["accepted_transport"]))
def test_no_other_old_transport_identity_can_use_bridge(setup, field):
    recovery = setup[2]["evidence"]["local_recovery"]
    value = recovery[field]
    recovery[field] = value + 1 if type(value) is int else "unaccepted"
    with pytest.raises(guard.GuardError):
        run(setup)


@pytest.mark.parametrize("field", ["compatibility_contract_sha256", "release_evidence_sha256"])
def test_missing_new_binding_cannot_borrow_old_attestation(setup, field):
    setup[2].pop(field)
    with pytest.raises(guard.GuardError, match="unbound_delivery_readiness"):
        run(setup)


@pytest.mark.parametrize("status", ["FAIL", "BLOCKED", "NOT RUN", False, None])
@pytest.mark.parametrize("check", guard.RELEASE_CHECKS)
def test_any_missing_or_failed_measured_check_blocks_release(setup, status, check):
    document = release_document(setup)
    if status is None:
        del document["checks"][check]
    else:
        document["checks"][check] = status
    replace_release(setup, document)
    with pytest.raises(guard.GuardError, match="technical_release_not_established"):
        run(setup)


@pytest.mark.parametrize("mutation,reason", [("source_missing", "release_source_coverage"),
    ("source_changed", "release_source_changed"), ("proof_missing", "release_proof_coverage"),
    ("proof_changed", "release_proof_changed"), ("proof_failed", "technical_release_not_established"),
    ("proof_escape", "invalid_release_proof"), ("changed_diff", "release_diff_changed"),
    ("foreign_code", "unreviewed_delivery_scope"), ("incomplete_diff", "incomplete_delivery_diff")])
def test_hashed_release_cannot_hide_changed_or_missing_proof(setup, mutation, reason):
    document = release_document(setup)
    path = "tools/historical_package.py"
    if mutation == "source_missing": del document["source_sha256"][path]
    elif mutation == "source_changed":
        setup[3][f"/contents/{path}?ref={APPROVED}"]["content"] = base64.b64encode(b"changed source").decode()
    elif mutation == "proof_missing": del document["proofs"]["runtime"]
    elif mutation in ("proof_changed", "proof_failed"):
        proof = document["proofs"]["runtime"]
        raw = guard.encode({"status": "FAIL"})
        setup[3][f"/contents/{proof['path']}?ref={APPROVED}"]["content"] = base64.b64encode(raw).decode()
        if mutation == "proof_failed": proof["sha256"] = hashlib.sha256(raw).hexdigest()
    elif mutation == "proof_escape": document["proofs"]["runtime"]["path"] = "docs/input-truthfulness/../outside.json"
    else:
        change = setup[3][f"/compare/{guard.compatibility_contract()['continuation_base']}...{APPROVED}"]
        if mutation == "changed_diff": change["files"] = [{"filename": path, "status": "modified", "sha": "d" * 40}]
        elif mutation == "foreign_code": change["files"] = [{"filename": "src/breadth.py", "status": "modified", "sha": "d" * 40}]
        else: change.pop("files")
    replace_release(setup, document)
    with pytest.raises(guard.GuardError, match=reason):
        run(setup)


def test_declared_exact_changed_code_is_reviewable_and_unrelated_control_passes(setup):
    document = release_document(setup)
    change = {"filename": "tools/historical_package.py", "status": "modified", "sha": "d" * 40}
    setup[3][f"/compare/{guard.compatibility_contract()['continuation_base']}...{APPROVED}"]["files"] = [change]
    document["changed_code"] = [{"path": change["filename"], "git_blob": change["sha"]}]
    replace_release(setup, document)
    assert run(setup)["status"] == "PASS"


def test_accepted_history_job_cannot_be_replaced(setup):
    setup[3][jobs_path(OLD_RUN)]["jobs"][0]["id"] += 1
    with pytest.raises(guard.GuardError, match="unaccepted_prior_transport_job"):
        run(setup)


def test_compatibility_does_not_bypass_current_main_source_equality(setup):
    setup[3][f"/git/trees/{CURRENT}"]["tree"][0]["sha"] = "d" * 40
    with pytest.raises(guard.GuardError, match="execution_code_changed"):
        run(setup)


def test_old_provider_rights_booleans_are_not_owner_authorization(setup):
    setup[2]["evidence"]["rights"] = {"private_retention_permitted": True, "encrypted_transport_permitted": True}
    del setup[2]["evidence"]["owner_authorization"]
    with pytest.raises(guard.GuardError, match="missing_readiness_evidence"):
        run(setup)


@pytest.mark.parametrize("field,value", [("owner_authorized", False), ("provider_consent", "PERMITTED"),
    ("scope", "public_redistribution"), ("public_plaintext", True), ("owner_only_decryption", False),
    ("public_ciphertext_retention_days", 8), ("controlled_review_status", "PERMITTED")])
def test_personal_scope_cannot_claim_provider_consent_or_expand_access(setup, field, value):
    setup[2]["evidence"]["owner_authorization"][field] = value
    with pytest.raises(guard.GuardError, match="owner_scope_not_authorized"):
        run(setup)


def test_historical_v2_projection_is_not_relabelled_or_current_authorization(setup):
    result = run(setup)
    legacy = {key: result[key] for key in guard.BINDING_FIELDS}
    assert guard.validate_phase_binding(legacy) == legacy
    with pytest.raises(guard.GuardError, match="missing_delivery_binding"):
        guard.validate_execution_binding(legacy, setup[0])
    assert guard.RECOVERY_CONTRACT_SHA256 == "6b49a4956c8196c432e9798149e2e1544b075a13353351cb10dfe241f72aae7a"
