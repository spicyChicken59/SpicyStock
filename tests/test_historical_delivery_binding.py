"""Prospective source/release compatibility using only invented API responses."""
from copy import deepcopy
import base64
import hashlib
import json

import pytest

from tests.test_historical_execution_guard import setup, run, APPROVED, CURRENT, OLD_RUN, TODAY, jobs_path
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
    ("foreign_code", "unreviewed_delivery_scope"), ("renamed_source", "unreviewed_delivery_scope"),
    ("incomplete_diff", "incomplete_delivery_diff")])
def test_hashed_release_cannot_hide_changed_or_missing_proof(setup, mutation, reason):
    document = release_document(setup)
    path = "tools/historical_package.py"
    if mutation == "source_missing": del document["source_sha256"][path]
    elif mutation == "source_changed":
        setup[3][f"/contents/{path}?ref={APPROVED}"]["content"] = base64.b64encode(b"changed source").decode()
    elif mutation == "proof_missing": del document["proofs"]["runtime"]
    elif mutation in ("proof_changed", "proof_failed"):
        proof = document["proofs"]["runtime"]
        raw = guard.encode({"status": "FAIL" if mutation == "proof_failed" else "PASS", "changed": True})
        setup[3][f"/contents/{proof['path']}?ref={APPROVED}"]["content"] = base64.b64encode(raw).decode()
        if mutation == "proof_failed": proof["sha256"] = hashlib.sha256(raw).hexdigest()
    elif mutation == "proof_escape": document["proofs"]["runtime"]["path"] = "docs/input-truthfulness/../outside.json"
    else:
        change = setup[3][f"/compare/{guard.compatibility_contract()['continuation_base']}...{APPROVED}"]
        if mutation == "changed_diff": change["files"] = [{"filename": path, "status": "modified", "sha": "d" * 40}]
        elif mutation == "foreign_code": change["files"] = [{"filename": "src/breadth.py", "status": "modified", "sha": "d" * 40}]
        elif mutation == "renamed_source": change["files"] = [{"filename": "tests/moved.py", "previous_filename": "src/another.py", "status": "renamed", "sha": "d" * 40}]
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
    accepted = guard.compatibility_contract()["accepted_transport"]
    legacy.update(run_id=accepted["rehearsal_run_id"], mode="rehearsal", run_number=4, assignment_phase=1,
                  checkout_sha=accepted["checkout_sha"], workflow_sha=accepted["workflow_sha"],
                  implementation_pr=95, readiness_comment_id=accepted["readiness_comment_id"],
                  recipient_sha256=guard.compatibility_contract()["recipient_sha256"])
    assert guard.validate_phase_binding(legacy) == legacy
    with pytest.raises(guard.GuardError, match="missing_delivery_binding"):
        guard.validate_execution_binding(legacy, setup[0])
    assert guard.RECOVERY_CONTRACT_SHA256 == "6b49a4956c8196c432e9798149e2e1544b075a13353351cb10dfe241f72aae7a"


def test_old_v2_readiness_is_not_a_current_release(setup):
    setup[2]["schema"] = "readiness-v2"
    with pytest.raises(guard.GuardError, match="readiness_not_pass"):
        run(setup)


def test_new_policy_cannot_change_the_frozen_recipient(setup):
    setup[0]["recipient"] = "age1" + "c" * 58
    setup[0]["recipient_sha256"] = hashlib.sha256((setup[0]["recipient"] + "\n").encode()).hexdigest()
    with pytest.raises(guard.GuardError, match="unaccepted_delivery_recipient"):
        run(setup)
    assert setup[4] == []


@pytest.mark.parametrize("path", ["tools/historical_normalization.py", "tools/historical_reconcile.py",
                                "tools/historical_breadth_reference.py"])
def test_scientific_runtime_is_hash_bound_but_not_in_changed_code_scope(setup, path):
    contract = guard.compatibility_contract()
    assert path in contract["required_source_paths"]
    assert path not in contract["permitted_changed_code"]
    setup[3][f"/compare/{contract['continuation_base']}...{APPROVED}"]["files"] = [
        {"filename": path, "status": "modified", "sha": "d" * 40}]
    with pytest.raises(guard.GuardError, match="unreviewed_delivery_scope"):
        run(setup)


def test_compatibility_contract_is_not_an_editable_old_success_fallback(setup, tmp_path, monkeypatch):
    contract = guard.compatibility_contract()
    contract["accepted_transport"]["rehearsal_run_id"] += 1
    path = tmp_path / "altered-compatibility.json"
    path.write_bytes(guard.encode(contract))
    monkeypatch.setattr(guard, "COMPATIBILITY_PATH", path)
    with pytest.raises(guard.GuardError, match="changed_compatibility_contract"):
        run(setup)


@pytest.mark.parametrize("old_pr", [94, 95, 96, None])
def test_old_or_unbound_pr_cannot_admit_new_code(setup, old_pr):
    setup[0]["implementation_pr"] = old_pr
    with pytest.raises(guard.GuardError, match="unbound_implementation_pr"):
        run(setup)
    assert setup[4] == []


@pytest.mark.parametrize("created,merged,authorized", [
    ("2026-09-29T09:59:59Z", "2026-09-29T10:00:00Z", "2026-09-29"),
    ("2026-09-29T12:00:00Z", "2026-09-29T10:00:00Z", "2026-09-28"),
    ("2026-09-29T12:00:00", "2026-09-29T10:00:00Z", "2026-09-29"),
    (None, "2026-09-29T10:00:00Z", "2026-09-29"),
    ("2026-09-29T12:00:00Z", None, "2026-09-29"),
], ids=["before_merge", "wrong_release_date", "naive_comment", "missing_comment_time", "missing_merge_time"])
def test_execution_release_requires_a_fresh_comment_after_merge(setup, created, merged, authorized):
    policy, env, record, responses, _, api = setup
    responses["/pulls/123"]["merged_at"] = merged
    record["authorized_on"] = authorized
    def changed_api(path):
        value = api(path)
        if path == "/issues/comments/123":
            value["created_at"] = created
            value["updated_at"] = "2026-09-29T12:30:00Z"
        return value
    with pytest.raises(guard.GuardError, match="execution_release_not_after_merge"):
        guard.verify(changed_api, policy, env, "real", 123, TODAY)


@pytest.mark.parametrize("path", [
    "docs/input-truthfulness/2026-09-29-workflow-repair-evidence/guard-controls.json",
    "docs/input-truthfulness/2026-09-30-projection-compaction-evidence/benchmark-stress.json",
])
@pytest.mark.parametrize("status", ["modified", "removed"])
def test_previous_evidence_cannot_be_altered_or_deleted(setup, path, status):
    setup[3][f"/compare/{guard.compatibility_contract()['continuation_base']}...{APPROVED}"]["files"] = [
        {"filename": path, "status": status, "sha": "d" * 40}]
    with pytest.raises(guard.GuardError, match="unreviewed_delivery_scope"):
        run(setup)


@pytest.mark.parametrize("path", [
    "docs/input-truthfulness/2026-09-29-historical-execution.md",
    "docs/input-truthfulness/2026-09-30-delivery-readiness-evidence/measured.json",
    guard.RELEASE_EVIDENCE_PATH,
])
def test_only_current_delivery_documents_are_allowed_support_changes(setup, path):
    setup[3][f"/compare/{guard.compatibility_contract()['continuation_base']}...{APPROVED}"]["files"] = [
        {"filename": path, "status": "modified", "sha": "d" * 40}]
    assert run(setup)["status"] == "PASS"


@pytest.mark.parametrize("mutation", ["changed", "missing"])
def test_other_github_workflow_changes_cannot_bypass_source_equality(setup, mutation):
    tree = setup[3][f"/git/trees/{CURRENT}"]["tree"]
    entry = next(item for item in tree if item["path"] == ".github")
    if mutation == "missing":
        tree.remove(entry)
    else:
        entry["sha"] = "d" * 40
    with pytest.raises(guard.GuardError, match="execution_code_changed"):
        run(setup)


@pytest.mark.parametrize("mutation", ["missing", "old_archive", "old_cipher", "expanded", "memory"])
def test_new_delivery_envelope_is_explicitly_bound(setup, mutation):
    document = release_document(setup)
    if mutation == "missing":
        document.pop("delivery_envelope")
    else:
        field, value = {"old_archive": ("max_archive_bytes", 199 * 1024**2),
                        "old_cipher": ("max_ciphertext_bytes", 200 * 1024**2),
                        "expanded": ("max_expanded_bytes", 3 * 1024**3),
                        "memory": ("max_process_tree_memory_bytes", 13 * 1024**3)}[mutation]
        document["delivery_envelope"][field] = value
    replace_release(setup, document)
    with pytest.raises(guard.GuardError, match="unbound_delivery_envelope"):
        run(setup)


def test_previous_package_binding_is_readable_but_not_current_execution(setup):
    result = run(setup)
    result["compatibility_contract_sha256"] = guard.PREVIOUS_COMPATIBILITY_CONTRACT_SHA256
    assert guard.validate_phase_binding(result)["compatibility_contract_sha256"] == guard.PREVIOUS_COMPATIBILITY_CONTRACT_SHA256
    with pytest.raises(guard.GuardError, match="stale_delivery_binding"):
        guard.validate_execution_binding(result, setup[0])


def test_previous_technical_declaration_cannot_certify_changed_envelope(setup):
    document = release_document(setup)
    document["schema"] = "historical-delivery-release-evidence-v1"
    replace_release(setup, document)
    with pytest.raises(guard.GuardError, match="technical_release_not_established"):
        run(setup)


def test_versioned_envelope_preserves_accepted_transport_and_codec():
    contract = guard.compatibility_contract()
    assert contract["schema"] == "historical-delivery-compatibility-v2"
    assert contract["supersedes_compatibility_sha256"] == guard.PREVIOUS_COMPATIBILITY_CONTRACT_SHA256
    assert contract["accepted_transport"]["rehearsal_run_id"] == 36570997883
    assert contract["accepted_transport"]["checkout_sha"] == "6b12fdfa67355b436fde89287d159bebda2ce9fc"
    assert contract["delivery_envelope"]["archive_format"] == "ustar-zstandard-v1"
    assert contract["delivery_envelope"]["max_expanded_bytes"] == 2 * 1024**3
