"""Synthetic GitHub responses combine pinned public history with invented future
records. No test performs a dispatch, provider request, or live admission.
"""
from copy import deepcopy
from datetime import date
import base64
import hashlib
import json
from pathlib import Path

import pytest

from tools import historical_execution_guard as guard
from tests.test_historical_workflow_validation import (
    bash, path_runtime, initialize, boundary_outputs,
)


APPROVED, CURRENT, MERGED = "a" * 40, "b" * 40, "c" * 40
TODAY = date(2026, 9, 29)
OLD_RUN = 36570997883
FIXTURE_PR = 123
HISTORY = f"/actions/workflows/{guard.WORKFLOW_ID}/runs?per_page=100&page=1"
HISTORY_END = f"/actions/workflows/{guard.WORKFLOW_ID}/runs?per_page=100&page=2"
ROOT = Path(__file__).resolve().parents[1]


def jobs_path(run_id, page=1):
    return f"/actions/runs/{run_id}/attempts/1/jobs?per_page=100&page={page}"


def artifacts_path(run_id, page=1):
    return f"/actions/runs/{run_id}/artifacts?per_page=100&page={page}"


def public_git_bytes(path):
    # These API fixtures represent public LF Git blobs. A Windows checkout may
    # have CRLF bytes; the parent declaration independently pins the LF content.
    return (ROOT / path).read_bytes().replace(b"\r\n", b"\n")


@pytest.fixture
def setup(monkeypatch):
    recipient = json.loads(guard.POLICY_PATH.read_bytes())["recipient"]
    policy = {"schema": guard.POLICY_SCHEMA, "implementation_pr": FIXTURE_PR,
              "recipient": recipient, "recipient_sha256": hashlib.sha256((recipient + "\n").encode()).hexdigest(),
              "recovery_contract_sha256": guard.RECOVERY_CONTRACT_SHA256,
              "compatibility_contract_sha256": guard.COMPATIBILITY_CONTRACT_SHA256}
    monkeypatch.setattr(guard, "RECIPIENT_SHA256", policy["recipient_sha256"])
    env = {"GITHUB_REPOSITORY": guard.REPOSITORY, "GITHUB_REPOSITORY_ID": str(guard.REPOSITORY_ID),
           "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main", "GITHUB_JOB": "execution",
           "GITHUB_WORKFLOW_REF": guard.REPOSITORY + "/" + guard.WORKFLOW + "@refs/heads/main",
           "GITHUB_SHA": CURRENT, "GITHUB_WORKFLOW_SHA": CURRENT,
           "GITHUB_RUN_ID": "105", "GITHUB_RUN_NUMBER": "6", "GITHUB_RUN_ATTEMPT": "1"}
    item = {"verified_at": "2026-09-28", "reference": "https://example.test/private-attestation/123",
            "basis": "Invented offline test evidence with no provider activity"}
    evidence = {name: deepcopy(item) for name in ("cost", "owner_authorization", "entitlement", "local_recovery")}
    evidence["cost"]["zero_additional_cost"] = True
    evidence["owner_authorization"].update(schema="owner-personal-use-v1", owner=guard.OWNER, scope="personal_research",
        owner_authorized=True, owner_only_decryption=True, public_plaintext=False, public_ciphertext_retention_days=7,
        provider_consent="NOT ASSERTED", controlled_review_status="NOT RUN",
        direction_reference=guard.compatibility_contract()["owner_direction_reference"])
    evidence["entitlement"]["historical_sip_zero_cost"] = True
    evidence["local_recovery"].update(schema=guard.LOCAL_RECOVERY_SCHEMA, verified=True, rehearsal_run_id=OLD_RUN,
        run_number=4, assignment_phase=1, run_attempt=1, recovery_contract_sha256=guard.ORIGINAL_RECOVERY_CONTRACT_SHA256,
        checkout_sha=APPROVED, workflow_sha=CURRENT, recipient_sha256=policy["recipient_sha256"],
        ciphertext_sha256="d" * 64, recovered_plaintext_sha256="e" * 64)
    evidence["local_recovery"].update(guard.compatibility_contract()["accepted_transport"], manifest_sha256=guard.MANIFEST,
        reference="sha256:" + guard.compatibility_contract()["accepted_transport"]["recovery_checkpoint_sha256"])
    record = {"schema": guard.READINESS_SCHEMA, "status": "PASS", "authorized_on": "2026-09-29", "mode": "real", "assignment_id": guard.ASSIGNMENT,
              "manifest_sha256": guard.MANIFEST, "checkout_sha": APPROVED, "workflow_id": guard.WORKFLOW_ID,
              "recipient_sha256": policy["recipient_sha256"], "evidence": evidence, "run_number": 6, "assignment_phase": 2,
              "recovery_contract_sha256": guard.RECOVERY_CONTRACT_SHA256,
              "compatibility_contract_sha256": guard.COMPATIBILITY_CONTRACT_SHA256}
    repo = {"id": guard.REPOSITORY_ID, "full_name": guard.REPOSITORY, "private": False}
    pr = {"number": FIXTURE_PR, "merged": True, "merged_at": "2026-09-29T10:00:00Z", "state": "closed", "draft": False, "merge_commit_sha": MERGED,
          "base": {"ref": "main", "repo": repo}, "head": {"sha": APPROVED, "repo": repo}}
    runs = []
    for exception in guard.recovery_contract()["exceptions"]:
        runs.append({**{key: exception[key] for key in ("id", "run_number", "run_attempt", "workflow_id", "path", "event", "head_branch", "head_sha", "status", "conclusion")},
                     "repository": deepcopy(repo), "head_repository": deepcopy(repo)})
    runs.extend([{"id": OLD_RUN if n == 4 else 105, "run_number": n, "run_attempt": 1, "workflow_id": guard.WORKFLOW_ID, "path": guard.WORKFLOW, "event": "workflow_dispatch",
             "head_branch": "main", "repository": repo, "head_repository": repo, "head_sha": guard.compatibility_contract()["accepted_transport"]["workflow_sha"] if n == 4 else CURRENT,
             "display_title": "historical-input-" + ("rehearsal" if n == 4 else "real"),
             "status": "completed" if n == 4 else "in_progress", "conclusion": "success" if n == 4 else None} for n in (4, 6)])
    incident = guard.incident.incident_contract()["exception"]
    runs.insert(4, deepcopy(incident["run"]))
    tree = {"truncated": False, "tree": [{"path": path, "type": "tree", "sha": "f" * 40} for path in ("tools", "src", ".github")]}
    content = {"type": "file", "encoding": "base64", "content": base64.b64encode(b"synthetic workflow\n").decode()}
    responses = {"": repo, "/pulls/123": pr,
                 "/pulls/94": {"number": 94, "merged": True, "merge_commit_sha": guard.ORIGINAL_MERGE, "head": {"sha": guard.ORIGINAL_HEAD}},
                 f"/compare/{guard.ORIGINAL_MERGE}...{APPROVED}": {"status": "ahead", "behind_by": 0},
                 f"/compare/{MERGED}...{CURRENT}": {"status": "ahead", "behind_by": 0},
                 f"/git/trees/{APPROVED}": deepcopy(tree), f"/git/trees/{CURRENT}": deepcopy(tree),
                 f"/contents/{guard.WORKFLOW}?ref={APPROVED}": deepcopy(content),
                 f"/contents/{guard.WORKFLOW}?ref={CURRENT}": deepcopy(content),
                 f"/actions/workflows/{guard.WORKFLOW_ID}": {"id": guard.WORKFLOW_ID, "path": guard.WORKFLOW, "state": "active"},
                 HISTORY: {"total_count": 6, "workflow_runs": runs}, HISTORY_END: {"total_count": 6, "workflow_runs": []}}
    for run_record in runs:
        run_id = run_record["id"]
        responses[f"/actions/runs/{run_id}"] = deepcopy(run_record)
        jobs = [] if run_record["run_number"] <= 3 else [{"id": guard.compatibility_contract()["accepted_transport"]["job_id"] if run_record["run_number"] == 4 else 500 + run_id, "run_id": run_id, "name": "execution",
            "status": run_record["status"], "conclusion": run_record["conclusion"], "started_at": "2026-09-29T12:00:00Z"}]
        if run_record["run_number"] == 5:
            jobs = [deepcopy(incident["job"])]
            responses[artifacts_path(run_id)] = {"total_count": 0, "artifacts": []}
        responses[jobs_path(run_id)] = {"total_count": len(jobs), "jobs": jobs}
        if jobs:
            responses[jobs_path(run_id, 2)] = {"total_count": len(jobs), "jobs": []}
    contract = guard.compatibility_contract()
    parent = contract["parent_delivery"]
    parent_raw = public_git_bytes(parent["path"])
    assert hashlib.sha256(parent_raw).hexdigest() == parent["sha256"]
    parent_release = json.loads(parent_raw)
    responses[f"/contents/{parent['path']}?ref={parent['revision']}"] = {
        "type": "file", "encoding": "base64", "content": base64.b64encode(parent_raw).decode()}
    source_bytes = {}
    for path in contract["required_source_paths"]:
        reader = contract.get("identity_reader_revision", {})
        scanner = contract.get("scanner_disposition", {})
        if path == scanner.get("path"):
            source_bytes[path] = public_git_bytes(path)
            assert hashlib.sha256(source_bytes[path]).hexdigest() == scanner["after_sha256"]
        elif path == reader.get("path"):
            source_bytes[path] = public_git_bytes(path)
            assert hashlib.sha256(source_bytes[path]).hexdigest() == reader["after_sha256"]
        elif path in contract["permitted_changed_code"]:
            source_bytes[path] = ("synthetic reviewed admission source " + path + "\n").encode()
        else:
            source_bytes[path] = public_git_bytes(path)
            assert hashlib.sha256(source_bytes[path]).hexdigest() == parent_release["source_sha256"][path]
    source_bytes[guard.WORKFLOW] = b"synthetic workflow\n"
    release = {"schema": "historical-delivery-release-evidence-v3", "status": "PASS",
        "inherited_delivery": deepcopy(parent),
        "repair_checks": {name: "PASS" for name in ("input_normalization", "exact_incident_recovery", "wrapper_receipt_binding", "normal_ci")},
        "delivery_envelope": contract["delivery_envelope"],
        "compatibility_contract_sha256": guard.COMPATIBILITY_CONTRACT_SHA256,
        "manifest_sha256": guard.MANIFEST, "recipient_sha256": policy["recipient_sha256"],
        "checks": deepcopy(parent_release["checks"]),
        "source_sha256": {path: hashlib.sha256(raw).hexdigest() for path, raw in source_bytes.items()},
        "changed_code": [], "proofs": deepcopy(parent_release["proofs"])}
    for path, raw in source_bytes.items():
        responses[f"/contents/{path}?ref={APPROVED}"] = {"type": "file", "encoding": "base64", "content": base64.b64encode(raw).decode()}
    for proof in release["proofs"].values():
        path = proof["path"]
        raw = public_git_bytes(path)
        assert hashlib.sha256(raw).hexdigest() == proof["sha256"]
        responses[f"/contents/{path}?ref={APPROVED}"] = {"type": "file", "encoding": "base64", "content": base64.b64encode(raw).decode()}
    repair_path = "docs/input-truthfulness/2026-09-30-delivery-readiness-evidence/native5-recovery/proof-repair.json"
    repair_raw = guard.encode({"schema": "historical-native6-repair-proof-v1", "status": "PASS",
        "checks": release["repair_checks"], "source_sha256": release["source_sha256"],
        "scope": "Invented offline unit-test review proof, not an actual execution or approval."})
    release["repair_proof"] = {"path": repair_path, "sha256": hashlib.sha256(repair_raw).hexdigest()}
    responses[f"/contents/{repair_path}?ref={APPROVED}"] = {
        "type": "file", "encoding": "base64", "content": base64.b64encode(repair_raw).decode()}
    raw = guard.encode(release)
    record["release_evidence_sha256"] = hashlib.sha256(raw).hexdigest()
    responses[f"/contents/{guard.RELEASE_EVIDENCE_PATH}?ref={APPROVED}"] = {"type": "file", "encoding": "base64", "content": base64.b64encode(raw).decode()}
    responses[f"/compare/{contract['continuation_base']}...{APPROVED}"] = {"status": "ahead", "behind_by": 0, "files": []}
    calls = []

    def api(path):
        calls.append(path)
        if path == "/issues/comments/123":
            return {"id": 123, "user": {"login": guard.OWNER}, "issue_url": guard.API_ROOT + "/issues/123", "body": json.dumps(record),
                    "created_at": "2026-09-29T12:00:00Z"}
        if path not in responses:
            raise guard.GuardError("missing_synthetic_response")
        return deepcopy(responses[path])

    return policy, env, record, responses, calls, api


def make_rehearsal(setup):
    _, env, record, responses, _, _ = setup
    env.update(GITHUB_RUN_ID=str(OLD_RUN), GITHUB_RUN_NUMBER="4")
    record.update(mode="rehearsal", run_number=4, assignment_phase=1)
    record["evidence"] = {"cost": record["evidence"]["cost"]}
    responses[HISTORY]["workflow_runs"] = [run for run in responses[HISTORY]["workflow_runs"] if run["run_number"] <= 4]
    for path in (HISTORY, HISTORY_END):
        responses[path]["total_count"] = 4
    for run in (responses[HISTORY]["workflow_runs"][-1], responses[f"/actions/runs/{OLD_RUN}"], responses[jobs_path(OLD_RUN)]["jobs"][0]):
        run.update(status="in_progress", conclusion=None)
    for run in (responses[HISTORY]["workflow_runs"][-1], responses[f"/actions/runs/{OLD_RUN}"]):
        run["head_sha"] = CURRENT
    return setup


def change_run(setup, number, **changes):
    run = next(item for item in setup[3][HISTORY]["workflow_runs"] if item["run_number"] == number)
    run_id = run["id"]
    run.update(changes)
    setup[3][f"/actions/runs/{run_id}"].update(changes)
    if run["id"] != run_id:
        setup[3][f"/actions/runs/{run['id']}"] = deepcopy(run)
        setup[3][jobs_path(run["id"])] = deepcopy(setup[3][jobs_path(run_id)])


def run(setup):
    policy, env, record, _, _, api = setup
    return guard.verify(api, policy, env, record["mode"], 123, TODAY)


def test_full_real_authorization_and_truthful_operator_only_recovery(setup, tmp_path):
    result = run(setup)
    assert result["checkout_sha"] == APPROVED
    assert result["run_id"] == 105 and result["run_number"] == 6 and result["assignment_phase"] == 2 and result["lifetime_status"] == "PASS"
    approval = guard.approval(result, tmp_path / "storage")
    assert approval["provider_requests_per_minute"] == 20
    assert approval["reviewer_retrieval_path"].endswith("Guidance private review: NOT RUN")
    assert not (tmp_path / "storage").exists()


@pytest.mark.parametrize("mutation,reason", [("valid", None), ("owner", "untrusted_readiness_comment"),
    ("stale", "execution_release_not_after_merge"), ("head", "unreviewed_checkout"),
    ("phase", "stale_phase_readiness")])
def test_normalization_reaches_actual_guard_without_relaxing_authorization(setup, path_runtime, bash, mutation, reason):
    policy, env, record, responses, _, api = setup
    path_runtime[4].update(env)
    path_runtime[4]["RAW_READINESS_COMMENT_ID"] = " \t 123\t "
    assert initialize(bash, path_runtime).returncode == 0
    canonical = boundary_outputs(path_runtime)["readiness_comment_id"]
    assert canonical == "123"
    if mutation == "head": record["checkout_sha"] = CURRENT
    elif mutation == "phase": record["assignment_phase"] = 1
    def reviewed_api(path):
        response = api(path)
        if path == "/issues/comments/123":
            if mutation == "owner": response["user"]["login"] = "different-owner"
            elif mutation == "stale": response["created_at"] = "2026-09-29T09:59:59Z"
        return response
    if reason is None:
        assert guard.verify(reviewed_api, policy, env, "real", int(canonical), TODAY)["run_number"] == 6
    else:
        with pytest.raises(guard.GuardError, match=reason):
            guard.verify(reviewed_api, policy, env, "real", int(canonical), TODAY)
    # Boundary scratch creation is not provider storage or a fresh ledger.
    assert not list(path_runtime[0].rglob("*.sqlite"))


def test_private_receipt_digest_is_supported_but_generic_reference_is_not(setup):
    assert setup[2]["evidence"]["local_recovery"]["reference"].startswith("sha256:")
    assert run(setup)["status"] == "PASS"
    setup[2]["evidence"]["owner_authorization"]["reference"] = "the owner has checked everything"
    with pytest.raises(guard.GuardError, match="invalid_evidence_reference"):
        run(setup)


@pytest.mark.parametrize("permission", [False, None], ids=["false", "missing"])
def test_real_requires_permission_for_public_ciphertext_transport(setup, permission):
    rights = setup[2]["evidence"]["owner_authorization"]
    if permission is None:
        rights.pop("owner_only_decryption")
    else:
        rights["owner_only_decryption"] = permission
    assert rights["owner_authorized"] is True
    with pytest.raises(guard.GuardError, match="owner_scope_not_authorized"):
        run(setup)


def test_accepted_rehearsal_slot_cannot_be_dispatched_again(setup):
    with pytest.raises(guard.GuardError, match="rehearsal_slot_closed"):
        run(make_rehearsal(setup))
    assert not setup[4]


@pytest.mark.parametrize("key,value", [
    ("GITHUB_REPOSITORY", "other/SpicyStock"), ("GITHUB_REPOSITORY_ID", "123"),
    ("GITHUB_EVENT_NAME", "push"), ("GITHUB_REF", "refs/heads/feature"),
    ("GITHUB_WORKFLOW_REF", "other/path@refs/heads/main"), ("GITHUB_WORKFLOW_SHA", APPROVED),
    ("GITHUB_JOB", "other"), ("GITHUB_RUN_NUMBER", "3"), ("GITHUB_RUN_ATTEMPT", "2"),
    ("GITHUB_RUN_ID", "00102"), ("GITHUB_SHA", "not-a-sha"),
])
def test_context_rejected_before_any_api_access(setup, key, value):
    setup[1][key] = value
    with pytest.raises(guard.GuardError):
        run(setup)
    assert not setup[4]


@pytest.mark.parametrize("key,value", [("implementation_pr", 0), ("recipient_sha256", "0" * 64), ("recipient", "age1BAD")])
def test_policy_placeholder_rejected_before_api(setup, key, value):
    setup[0][key] = value
    with pytest.raises(guard.GuardError):
        run(setup)
    assert not setup[4]


@pytest.mark.parametrize("key,value", [("status", "PENDING"), ("manifest_sha256", "1" * 64),
    ("assignment_id", "another-study"), ("checkout_sha", "0" * 40), ("workflow_id", 0), ("recipient_sha256", "2" * 64)])
def test_unbound_readiness_rejected(setup, key, value):
    setup[2][key] = value
    with pytest.raises(guard.GuardError):
        run(setup)


@pytest.mark.parametrize("mutation", ["author", "issue", "fence", "duplicate", "false_recovery", "wrong_recipient", "future", "placeholder", "unpaid", "unlicensed", "no_entitlement"])
def test_readiness_attestation_failures(setup, mutation):
    policy, _, record, _, _, api = setup
    comment = api("/issues/comments/123")
    if mutation == "author": comment["user"]["login"] = "untrusted-reviewer"
    elif mutation == "issue": comment["issue_url"] = guard.API_ROOT + "/issues/94"
    elif mutation == "fence": comment["body"] = "```json\n" + comment["body"] + "\n```"
    elif mutation == "duplicate": comment["body"] = '{"status":"PASS","status":"BLOCKED"}'
    else:
        evidence = record["evidence"]
        if mutation == "false_recovery": evidence["local_recovery"]["verified"] = False
        elif mutation == "wrong_recipient": evidence["local_recovery"]["recipient_sha256"] = "3" * 64
        elif mutation == "future": evidence["cost"]["verified_at"] = "2026-09-30"
        elif mutation == "placeholder": evidence["owner_authorization"]["basis"] = "TODO establish this evidence"
        elif mutation == "unpaid": evidence["cost"]["zero_additional_cost"] = False
        elif mutation == "unlicensed": evidence["owner_authorization"]["owner_authorized"] = False
        elif mutation == "no_entitlement": evidence["entitlement"]["historical_sip_zero_cost"] = False
        comment["body"] = json.dumps(record)
    with pytest.raises(guard.GuardError):
        guard.validate_readiness(comment, policy, "real", TODAY)


@pytest.mark.parametrize("key,value", [("merged", False), ("state", "open"), ("draft", True)])
def test_unmerged_implementation_rejected(setup, key, value):
    setup[3]["/pulls/123"][key] = value
    with pytest.raises(guard.GuardError, match="implementation_not_merged"):
        run(setup)


@pytest.mark.parametrize("mutation,reason", [("head", "unreviewed_checkout"), ("ancestry", "implementation_not_in_main"),
    ("tree", "execution_code_changed"), ("truncated", "execution_code_changed"), ("workflow", "workflow_changed"),
    ("workflow_id", "wrong_workflow_identity"), ("private", "wrong_or_private_repository"),
    ("job_started", "execution_job_not_durable"), ("job_run", "execution_job_not_durable")])
def test_reviewed_source_and_durable_job_failures(setup, mutation, reason):
    responses = setup[3]
    if mutation == "head": responses["/pulls/123"]["head"]["sha"] = CURRENT
    elif mutation == "ancestry": responses[f"/compare/{MERGED}...{CURRENT}"]["behind_by"] = 1
    elif mutation == "tree": responses[f"/git/trees/{CURRENT}"]["tree"][0]["sha"] = CURRENT
    elif mutation == "truncated": responses[f"/git/trees/{CURRENT}"]["truncated"] = True
    elif mutation == "workflow": responses[f"/contents/{guard.WORKFLOW}?ref={CURRENT}"]["content"] = base64.b64encode(b"changed").decode()
    elif mutation == "workflow_id": responses[f"/actions/workflows/{guard.WORKFLOW_ID}"]["id"] = 78
    elif mutation == "private": responses[""]["private"] = True
    elif mutation == "job_started": responses[jobs_path(105)]["jobs"][0]["started_at"] = "invalid"
    elif mutation == "job_run": responses[jobs_path(105)]["jobs"][0]["run_id"] = 999
    with pytest.raises(guard.GuardError, match=reason):
        run(setup)


@pytest.mark.parametrize("mutation", ["deleted", "extra", "duplicate", "rerun", "failed", "cancelled", "wrong_receipt", "wrong_phase", "fork", "wrong_current", "not_started"])
def test_native_history_cannot_reopen_a_slot(setup, mutation):
    listing = setup[3][HISTORY]
    runs = listing["workflow_runs"]
    if mutation == "deleted":
        listing.update(total_count=5, workflow_runs=runs[1:])
        setup[3][HISTORY_END]["total_count"] = 5
    elif mutation == "extra": listing.update(total_count=7, workflow_runs=runs + [deepcopy(runs[0])])
    elif mutation == "duplicate": runs[-1]["id"] = runs[-2]["id"]
    elif mutation == "rerun": change_run(setup, 4, run_attempt=2)
    elif mutation in {"failed", "cancelled"}: change_run(setup, 4, conclusion="failure" if mutation == "failed" else "cancelled")
    elif mutation == "wrong_receipt": setup[2]["evidence"]["local_recovery"]["rehearsal_run_id"] = 99
    elif mutation == "wrong_phase": change_run(setup, 4, display_title="historical-input-real")
    elif mutation == "fork": change_run(setup, 4, head_repository={"id": 123})
    elif mutation == "wrong_current": change_run(setup, 6, head_sha=APPROVED)
    elif mutation == "not_started": change_run(setup, 6, status="queued")
    reasons = {"deleted": "incomplete_or_consumed_history", "extra": "consumed_or_invalid_history",
        "duplicate": "duplicate_run_history", "rerun": "unaccounted_or_retried_run",
        "failed": "rehearsal_not_recovered", "cancelled": "rehearsal_not_recovered",
        "wrong_receipt": "unaccepted_prior_transport", "wrong_phase": "wrong_historical_phase",
        "fork": "foreign_run_repository", "wrong_current": "current_run_not_durable", "not_started": "current_run_not_durable"}
    with pytest.raises(guard.GuardError, match=reasons[mutation]):
        run(setup)


def test_history_reads_all_pages_and_refuses_inconsistent_totals(setup):
    listing = setup[3][HISTORY]
    first, second = listing["workflow_runs"][:2], listing["workflow_runs"][2:]
    listing["workflow_runs"] = first
    path = HISTORY_END
    setup[3][path] = {"total_count": 6, "workflow_runs": second}
    setup[3][f"/actions/workflows/{guard.WORKFLOW_ID}/runs?per_page=100&page=3"] = {"total_count": 6, "workflow_runs": []}
    assert run(setup)["status"] == "PASS"
    assert path in setup[4]
    setup[3][path]["total_count"] = 4
    with pytest.raises(guard.GuardError, match="history_changed_during_read"):
        run(setup)


def test_fixed_three_exception_contract_and_private_snapshot(setup):
    exceptions = guard.recovery_contract()["exceptions"]
    assert [(item["id"], item["run_number"], item["head_sha"]) for item in exceptions] == [
        (36520481662, 1, "21e405fa0601bdd476bad2e8027abcae5e6fac15"),
        (36521323183, 2, "eb2b417a7a2289ab22c239ccfe06c20daf1dde7b"),
        (36524147152, 3, "33ec181ca60adaf2f7c0ef19a1889a5517161585")]
    result = run(setup)
    snapshot = result["history_verification"]
    assert [item["attempt_jobs_count"] for item in snapshot["runs"]] == [0, 0, 0, 1, 1, 1]
    assert snapshot["runs"][4]["attempt_job_ids"] == [guard.incident.FAILED_JOB_ID]
    assert snapshot["runs"][-1]["attempt_job_ids"] == [605]
    assert snapshot["first_listing_sha256"] == snapshot["repeated_listing_sha256"]
    assert setup[4].count(HISTORY) == 2 and setup[4].count(HISTORY_END) == 2
    assert all("event=" not in call and "status=" not in call and "branch=" not in call for call in setup[4])


@pytest.mark.parametrize("number", [1, 2, 3])
@pytest.mark.parametrize("field,value,reason", [("id", 999, "unaccounted_or_retried_run"),
    ("head_sha", "1" * 40, "changed_reviewed_exception"), ("run_attempt", 2, "changed_reviewed_exception"),
    ("event", "workflow_dispatch", "changed_reviewed_exception"), ("head_branch", "unreviewed", "changed_reviewed_exception"),
    ("status", "queued", "changed_reviewed_exception"), ("conclusion", "cancelled", "changed_reviewed_exception"),
    ("workflow_id", 987, "changed_reviewed_exception"), ("path", ".github/workflows/other.yml", "changed_reviewed_exception"),
    ("run_number", 4, "incomplete_or_consumed_history"), ("run_attempt", True, "invalid_run_history"),
    ("repository", {"id": 123, "full_name": guard.REPOSITORY}, "foreign_run_repository"),
    ("head_repository", {"id": 123, "full_name": guard.REPOSITORY}, "foreign_run_repository")])
def test_every_reviewed_exception_field_is_bound(setup, number, field, value, reason):
    change_run(setup, number, **{field: value})
    with pytest.raises(guard.GuardError, match=reason):
        run(setup)


@pytest.mark.parametrize("mutation,reason", [("missing", "missing_synthetic_response"), ("missing_jobs", "consumed_or_invalid_history"),
    ("missing_total", "consumed_or_invalid_history"), ("nonzero", "reviewed_exception_has_jobs"),
    ("count_disagreement", "incomplete_run_history"), ("partial", "incomplete_run_history"), ("boolean_count", "consumed_or_invalid_history")])
def test_exception_requires_authoritative_complete_attempt_jobs(setup, mutation, reason):
    responses = setup[3]
    run_id = 36520481662
    path = jobs_path(run_id)
    if mutation == "missing": del responses[path]
    elif mutation == "missing_jobs": responses[path] = {"total_count": 0}
    elif mutation == "missing_total": responses[path] = {"jobs": []}
    elif mutation == "nonzero":
        responses[path] = {"total_count": 1, "jobs": [{"id": 999}]}
        responses[jobs_path(run_id, 2)] = {"total_count": 1, "jobs": []}
    elif mutation == "count_disagreement": responses[path] = {"total_count": 0, "jobs": [{"id": 999}]}
    elif mutation == "partial": responses[path] = {"total_count": 1, "jobs": []}
    else: responses[path] = {"total_count": False, "jobs": []}
    with pytest.raises(guard.GuardError, match=reason):
        run(setup)


@pytest.mark.parametrize("mutation", ["missing", "missing_terminator", "short_page_gap", "boolean_count", "missing_individual", "changed_individual"])
def test_partial_or_unavailable_history_fails_closed(setup, mutation):
    responses = setup[3]
    if mutation == "missing": del responses[HISTORY]
    elif mutation == "missing_terminator": del responses[HISTORY_END]
    elif mutation == "short_page_gap": responses[HISTORY]["workflow_runs"] = responses[HISTORY]["workflow_runs"][:2]
    elif mutation == "boolean_count": responses[HISTORY]["total_count"] = True
    elif mutation == "missing_individual": del responses["/actions/runs/36520481662"]
    else: responses["/actions/runs/36520481662"]["run_attempt"] = 2
    with pytest.raises(guard.GuardError):
        run(setup)


def test_unknown_fourth_zero_job_validation_failure_is_not_exempt(setup):
    change_run(setup, 4, event="push", status="completed", conclusion="failure")
    setup[3][jobs_path(OLD_RUN)] = {"total_count": 0, "jobs": []}
    with pytest.raises(guard.GuardError, match="unaccounted_or_retried_run"):
        run(setup)


def test_changed_second_history_snapshot_fails_closed(setup):
    policy, env, record, responses, calls, api = setup
    def changing_api(path):
        value = api(path)
        if path == HISTORY and calls.count(HISTORY) == 2:
            value["workflow_runs"][0]["run_attempt"] = 2
        return value
    with pytest.raises(guard.GuardError, match="history_changed_during_read"):
        guard.verify(changing_api, policy, env, record["mode"], 123, TODAY)


@pytest.mark.parametrize("field,value", [("schema", "readiness-v1"), ("run_number", 2),
    ("run_number", True), ("assignment_phase", 1), ("recovery_contract_sha256", "1" * 64)])
def test_stale_readiness_cannot_approve_repaired_phase(setup, field, value):
    setup[2][field] = value
    with pytest.raises(guard.GuardError):
        run(setup)


@pytest.mark.parametrize("field,value", [("schema", "historical-local-recovery-v1"), ("run_number", 1),
    ("assignment_phase", True), ("run_attempt", 2), ("checkout_sha", CURRENT),
    ("workflow_sha", APPROVED), ("recovery_contract_sha256", "1" * 64)])
def test_stale_local_recovery_cannot_release_real(setup, field, value):
    setup[2]["evidence"]["local_recovery"][field] = value
    with pytest.raises(guard.GuardError):
        run(setup)


@pytest.mark.parametrize("field,value", [("run_number", 2), ("run_number", True), ("assignment_phase", 1),
    ("assignment_phase", True), ("run_attempt", 2), ("run_id", "105"), ("repository_id", 123),
    ("workflow_id", 123), ("workflow_path", "other.yml"), ("implementation_pr", 94),
    ("implementation_pr", None), ("recovery_contract_sha256", "0" * 64)])
def test_shared_binding_rejects_relabeling_and_wrong_identity(setup, field, value):
    result = run(setup)
    result[field] = value
    with pytest.raises(guard.GuardError):
        guard.validate_phase_binding(result)


def test_full_binding_adds_runtime_policy_identity(setup):
    result = run(setup)
    assert guard.validate_execution_binding(result, setup[0]) == guard.validate_phase_binding(result)
    result["implementation_pr"] = 96
    with pytest.raises(guard.GuardError, match="invalid_delivery_binding"):
        guard.validate_execution_binding(result, setup[0])


@pytest.mark.parametrize("mutation", ["repair_number", "original_number", "original_merge", "original_ancestry", "null_policy", "old_policy"])
def test_repair_and_original_pr_lineage_are_both_required(setup, mutation):
    responses = setup[3]
    if mutation == "repair_number": responses["/pulls/123"]["number"] = 96
    elif mutation == "original_number": responses["/pulls/94"]["number"] = 93
    elif mutation == "original_merge": responses["/pulls/94"]["merge_commit_sha"] = MERGED
    elif mutation == "original_ancestry": responses[f"/compare/{guard.ORIGINAL_MERGE}...{APPROVED}"]["behind_by"] = 1
    elif mutation == "null_policy": setup[0]["implementation_pr"] = None
    else: setup[0]["schema"] = "historical-execution-policy-v1"
    with pytest.raises(guard.GuardError):
        run(setup)


def test_changed_recovery_contract_is_not_a_new_allowance(setup, tmp_path, monkeypatch):
    contract = guard.recovery_contract()
    contract["exceptions"].append(deepcopy(contract["exceptions"][0]))
    path = tmp_path / "changed-contract.json"
    path.write_bytes(guard.encode(contract))
    monkeypatch.setattr(guard, "RECOVERY_PATH", path)
    with pytest.raises(guard.GuardError, match="changed_recovery_contract"):
        run(setup)
    assert not setup[4]


def test_cli_invalid_context_never_reads_credentials_or_policy(monkeypatch, tmp_path):
    class ForbiddenEnvironment(dict):
        def get(self, key, default=None):
            assert key != "GITHUB_TOKEN", "credentials must not be inspected"
            return super().get(key, default)
    monkeypatch.setattr(guard.os, "environ", ForbiddenEnvironment())
    assert guard.main(["--policy", str(tmp_path / "absent.json"), "--mode", "real", "--readiness-comment-id", "123",
                       "--output-dir", str(tmp_path / "guard"), "--storage-root", str(tmp_path / "storage")]) == 2


def test_cli_changed_manifest_never_reads_credentials(setup, monkeypatch, tmp_path):
    class ForbiddenEnvironment(dict):
        def get(self, key, default=None):
            assert key != "GITHUB_TOKEN", "credentials must not be inspected"
            return super().get(key, default)
    monkeypatch.setattr(guard.os, "environ", ForbiddenEnvironment(setup[1]))
    policy = tmp_path / "policy.json"
    policy.write_bytes(guard.encode(setup[0]))
    manifest = tmp_path / "manifest.json"
    manifest.write_bytes(b'{"changed":true}\n')
    monkeypatch.setattr(guard, "MANIFEST_PATH", manifest)
    assert guard.main(["--policy", str(policy), "--mode", "real", "--readiness-comment-id", "123",
                       "--output-dir", str(tmp_path / "guard"), "--storage-root", str(tmp_path / "storage")]) == 2


def test_cli_writes_reviewed_revision_and_bound_approval(setup, monkeypatch, tmp_path):
    env = dict(setup[1], GITHUB_TOKEN="synthetic-value", GITHUB_OUTPUT=str(tmp_path / "output"))
    monkeypatch.setattr(guard.os, "environ", env)
    monkeypatch.setattr(guard, "GitHub", lambda token: setup[5])
    policy = tmp_path / "policy.json"
    policy.write_bytes(guard.encode(setup[0]))
    output = tmp_path / "guard"
    assert guard.main(["--policy", str(policy), "--mode", "real", "--readiness-comment-id", "123",
                       "--output-dir", str(output), "--storage-root", str(tmp_path / "storage")]) == 0
    assert (tmp_path / "output").read_text().strip() == "checkout_sha=" + APPROVED
    assert json.loads((output / "execution.json").read_bytes())["recipient_sha256"] == setup[0]["recipient_sha256"]
    assert json.loads((output / "approval.json").read_bytes())["storage_root"] == str(tmp_path / "storage")
    assert not (tmp_path / "storage").exists()


def test_fixed_transport_root_and_redirect_refusal(monkeypatch):
    calls = []
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self, limit): return b'{"id":1352997802}'
    class Opener:
        def open(self, request, timeout):
            calls.append(request)
            return Response()
    monkeypatch.setattr(guard, "build_opener", lambda *args: Opener())
    client = guard.GitHub("synthetic-credential")
    assert client("")["id"] == guard.REPOSITORY_ID
    assert calls[0].full_url == guard.API_ROOT and calls[0].method == "GET"
    client(f"/compare/{MERGED}...{CURRENT}")
    with pytest.raises(guard.GuardError): client("//evil.test")
    with pytest.raises(guard.GuardError): client("https://evil.test")
    with pytest.raises(guard.GuardError): client("/../another-repository")
    with pytest.raises(guard.GuardError): guard.NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.test")
