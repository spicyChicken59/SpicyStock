"""Execution authorization tests use invented GitHub responses and no sockets."""
from copy import deepcopy
from datetime import date
import base64
import hashlib
import json

import pytest

from tools import historical_execution_guard as guard


APPROVED, CURRENT, MERGED = "a" * 40, "b" * 40, "c" * 40
TODAY = date(2026, 9, 28)


@pytest.fixture
def setup():
    recipient = "age1" + "a" * 58
    policy = {"schema": "historical-execution-policy-v1", "implementation_pr": 94,
              "recipient": recipient, "recipient_sha256": hashlib.sha256((recipient + "\n").encode()).hexdigest()}
    env = {"GITHUB_REPOSITORY": guard.REPOSITORY, "GITHUB_REPOSITORY_ID": str(guard.REPOSITORY_ID),
           "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main", "GITHUB_JOB": "execution",
           "GITHUB_WORKFLOW_REF": guard.REPOSITORY + "/" + guard.WORKFLOW + "@refs/heads/main",
           "GITHUB_SHA": CURRENT, "GITHUB_WORKFLOW_SHA": CURRENT,
           "GITHUB_RUN_ID": "102", "GITHUB_RUN_NUMBER": "2", "GITHUB_RUN_ATTEMPT": "1"}
    item = {"verified_at": "2026-09-28", "reference": "https://example.test/private-attestation/123",
            "basis": "Invented offline test evidence with no provider activity"}
    evidence = {name: deepcopy(item) for name in ("cost", "rights", "entitlement", "local_recovery")}
    evidence["cost"]["zero_additional_cost"] = True
    evidence["rights"].update(private_retention_permitted=True, controlled_review_status="NOT RUN")
    evidence["entitlement"]["historical_sip_zero_cost"] = True
    evidence["local_recovery"].update(verified=True, rehearsal_run_id=101, recipient_sha256=policy["recipient_sha256"],
        ciphertext_sha256="d" * 64, recovered_plaintext_sha256="e" * 64)
    record = {"schema": "readiness-v1", "status": "PASS", "mode": "real", "assignment_id": guard.ASSIGNMENT,
              "manifest_sha256": guard.MANIFEST, "checkout_sha": APPROVED, "workflow_id": 77,
              "recipient_sha256": policy["recipient_sha256"], "evidence": evidence}
    repo = {"id": guard.REPOSITORY_ID, "full_name": guard.REPOSITORY, "private": False}
    pr = {"merged": True, "state": "closed", "draft": False, "merge_commit_sha": MERGED,
          "base": {"ref": "main", "repo": repo}, "head": {"sha": APPROVED, "repo": repo}}
    runs = [{"id": 100 + n, "run_number": n, "run_attempt": 1, "workflow_id": 77, "event": "workflow_dispatch",
             "head_branch": "main", "repository": repo, "head_repository": repo, "head_sha": CURRENT,
             "display_title": "historical-input-" + ("rehearsal" if n == 1 else "real"),
             "status": "completed" if n == 1 else "in_progress", "conclusion": "success" if n == 1 else None} for n in (1, 2)]
    tree = {"truncated": False, "tree": [{"path": path, "type": "tree", "sha": "f" * 40} for path in ("tools", "src")]}
    content = {"type": "file", "encoding": "base64", "content": base64.b64encode(b"synthetic workflow\n").decode()}
    responses = {"": repo, "/pulls/94": pr,
                 f"/compare/{MERGED}...{CURRENT}": {"status": "ahead", "behind_by": 0},
                 f"/git/trees/{APPROVED}": deepcopy(tree), f"/git/trees/{CURRENT}": deepcopy(tree),
                 f"/contents/{guard.WORKFLOW}?ref={APPROVED}": deepcopy(content),
                 f"/contents/{guard.WORKFLOW}?ref={CURRENT}": deepcopy(content),
                 "/actions/workflows/77": {"id": 77, "path": guard.WORKFLOW, "state": "active"},
                 "/actions/workflows/77/runs?per_page=100&page=1": {"total_count": 2, "workflow_runs": runs},
                 "/actions/runs/102/attempts/1/jobs?per_page=100": {"total_count": 1, "jobs": [{"id": 501, "run_id": 102,
                     "name": "execution", "status": "in_progress", "conclusion": None, "started_at": "2026-09-28T12:00:00Z"}]}}
    calls = []

    def api(path):
        calls.append(path)
        if path == "/issues/comments/123":
            return {"id": 123, "user": {"login": guard.OWNER}, "issue_url": guard.API_ROOT + "/issues/94", "body": json.dumps(record)}
        return responses[path]

    return policy, env, record, responses, calls, api


def run(setup):
    policy, env, record, _, _, api = setup
    return guard.verify(api, policy, env, record["mode"], 123, TODAY)


def test_full_real_authorization_and_truthful_operator_only_recovery(setup, tmp_path):
    result = run(setup)
    assert result["checkout_sha"] == APPROVED
    assert result["run_id"] == 102 and result["lifetime_status"] == "PASS"
    approval = guard.approval(result, tmp_path / "storage")
    assert approval["provider_requests_per_minute"] == 20
    assert approval["reviewer_retrieval_path"].endswith("Guidance private review: NOT_RUN")
    assert not (tmp_path / "storage").exists()


def test_private_receipt_digest_is_supported_but_generic_reference_is_not(setup):
    setup[2]["evidence"]["local_recovery"]["reference"] = "sha256:" + "6" * 64
    assert run(setup)["status"] == "PASS"
    setup[2]["evidence"]["rights"]["reference"] = "the owner has checked everything"
    with pytest.raises(guard.GuardError, match="invalid_evidence_reference"):
        run(setup)


def test_rehearsal_needs_cost_evidence_but_not_provider_rights(setup):
    policy, env, record, responses, _, _ = setup
    env.update(GITHUB_RUN_ID="101", GITHUB_RUN_NUMBER="1")
    record["mode"] = "rehearsal"
    record["evidence"] = {"cost": record["evidence"]["cost"]}
    first = responses["/actions/workflows/77/runs?per_page=100&page=1"]["workflow_runs"][0]
    first.update(status="in_progress", conclusion=None)
    responses["/actions/workflows/77/runs?per_page=100&page=1"] = {"total_count": 1, "workflow_runs": [first]}
    jobs = responses.pop("/actions/runs/102/attempts/1/jobs?per_page=100")
    jobs["jobs"][0]["run_id"] = 101
    responses["/actions/runs/101/attempts/1/jobs?per_page=100"] = jobs
    assert run(setup)["run_number"] == 1


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
    elif mutation == "issue": comment["issue_url"] = guard.API_ROOT + "/issues/95"
    elif mutation == "fence": comment["body"] = "```json\n" + comment["body"] + "\n```"
    elif mutation == "duplicate": comment["body"] = '{"status":"PASS","status":"BLOCKED"}'
    else:
        evidence = record["evidence"]
        if mutation == "false_recovery": evidence["local_recovery"]["verified"] = False
        elif mutation == "wrong_recipient": evidence["local_recovery"]["recipient_sha256"] = "3" * 64
        elif mutation == "future": evidence["cost"]["verified_at"] = "2026-09-29"
        elif mutation == "placeholder": evidence["rights"]["basis"] = "TODO establish this evidence"
        elif mutation == "unpaid": evidence["cost"]["zero_additional_cost"] = False
        elif mutation == "unlicensed": evidence["rights"]["private_retention_permitted"] = False
        elif mutation == "no_entitlement": evidence["entitlement"]["historical_sip_zero_cost"] = False
        comment["body"] = json.dumps(record)
    with pytest.raises(guard.GuardError):
        guard.validate_readiness(comment, policy, "real", TODAY)


@pytest.mark.parametrize("key,value", [("merged", False), ("state", "open"), ("draft", True)])
def test_unmerged_implementation_rejected(setup, key, value):
    setup[3]["/pulls/94"][key] = value
    with pytest.raises(guard.GuardError, match="implementation_not_merged"):
        run(setup)


@pytest.mark.parametrize("mutation,reason", [("head", "unreviewed_checkout"), ("ancestry", "implementation_not_in_main"),
    ("tree", "execution_code_changed"), ("truncated", "execution_code_changed"), ("workflow", "workflow_changed"),
    ("workflow_id", "wrong_workflow_identity"), ("private", "wrong_or_private_repository"),
    ("job_started", "execution_job_not_durable"), ("job_run", "execution_job_not_durable")])
def test_reviewed_source_and_durable_job_failures(setup, mutation, reason):
    responses = setup[3]
    if mutation == "head": responses["/pulls/94"]["head"]["sha"] = CURRENT
    elif mutation == "ancestry": responses[f"/compare/{MERGED}...{CURRENT}"]["behind_by"] = 1
    elif mutation == "tree": responses[f"/git/trees/{CURRENT}"]["tree"][0]["sha"] = CURRENT
    elif mutation == "truncated": responses[f"/git/trees/{CURRENT}"]["truncated"] = True
    elif mutation == "workflow": responses[f"/contents/{guard.WORKFLOW}?ref={CURRENT}"]["content"] = base64.b64encode(b"changed").decode()
    elif mutation == "workflow_id": responses["/actions/workflows/77"]["id"] = 78
    elif mutation == "private": responses[""]["private"] = True
    elif mutation == "job_started": responses["/actions/runs/102/attempts/1/jobs?per_page=100"]["jobs"][0]["started_at"] = "invalid"
    elif mutation == "job_run": responses["/actions/runs/102/attempts/1/jobs?per_page=100"]["jobs"][0]["run_id"] = 999
    with pytest.raises(guard.GuardError, match=reason):
        run(setup)


@pytest.mark.parametrize("mutation", ["deleted", "extra", "duplicate", "rerun", "failed", "wrong_receipt", "wrong_phase", "fork", "wrong_current", "not_started"])
def test_native_history_cannot_reopen_a_slot(setup, mutation):
    listing = setup[3]["/actions/workflows/77/runs?per_page=100&page=1"]
    runs = listing["workflow_runs"]
    if mutation == "deleted": listing.update(total_count=1, workflow_runs=runs[1:])
    elif mutation == "extra": listing.update(total_count=3, workflow_runs=runs + [deepcopy(runs[0])])
    elif mutation == "duplicate": runs[1]["id"] = runs[0]["id"]
    elif mutation == "rerun": runs[0]["run_attempt"] = 2
    elif mutation == "failed": runs[0]["conclusion"] = "failure"
    elif mutation == "wrong_receipt": setup[2]["evidence"]["local_recovery"]["rehearsal_run_id"] = 99
    elif mutation == "wrong_phase": runs[0]["display_title"] = "historical-input-real"
    elif mutation == "fork": runs[0]["head_repository"] = {"id": 123}
    elif mutation == "wrong_current": runs[1]["head_sha"] = APPROVED
    elif mutation == "not_started": runs[1]["status"] = "queued"
    with pytest.raises(guard.GuardError):
        run(setup)


def test_history_reads_all_pages_and_refuses_inconsistent_totals(setup):
    listing = setup[3]["/actions/workflows/77/runs?per_page=100&page=1"]
    first, second = listing["workflow_runs"]
    listing["workflow_runs"] = [first]
    path = "/actions/workflows/77/runs?per_page=100&page=2"
    setup[3][path] = {"total_count": 2, "workflow_runs": [second]}
    assert run(setup)["status"] == "PASS"
    assert path in setup[4]
    setup[3][path]["total_count"] = 1
    with pytest.raises(guard.GuardError, match="history_changed_during_read"):
        run(setup)


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
