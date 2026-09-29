"""Read-only GitHub guard for the two explicitly authorized execution slots.

The owner's readiness comment is a human attestation, not machine proof of a
data licence or account billing. No provider credentials are read here.
"""
from __future__ import annotations

import argparse
import base64
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

REPOSITORY = "spicyChicken59/SpicyStock"
REPOSITORY_ID = 1352997802
OWNER = "spicyChicken59"
WORKFLOW = ".github/workflows/historical-input-proof.yml"
ASSIGNMENT = "spicystock-historical-input-2026-09-28"
MANIFEST = "8d92ed5c56464fe9f342d024da14aa1521f6025d47ec32a6324a298b8fb63ebc"
API_ROOT = "https://api.github.com/repos/" + REPOSITORY
MANIFEST_PATH = Path(__file__).resolve().parents[1] / "docs/input-truthfulness/2026-09-28-historical-input-evidence/acquisition-manifest.json"


class GuardError(RuntimeError):
    """Only constant reason codes are suitable for public logs."""


def require(condition, reason):
    if not condition:
        raise GuardError(reason)


def positive(value):
    return type(value) is int and value > 0


def sha(value, size=64):
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{%d}" % size, value)) and set(value) != {"0"}


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def parse(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate_json_key")
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(GuardError("invalid_json")))
    except (ValueError, TypeError):
        raise GuardError("invalid_json") from None


def validate_policy(policy):
    require(isinstance(policy, dict) and policy.get("schema") == "historical-execution-policy-v1", "invalid_policy")
    require(positive(policy.get("implementation_pr")), "unbound_implementation_pr")
    recipient = policy.get("recipient", "")
    require(isinstance(recipient, str) and re.fullmatch(r"age1[023456789acdefghjklmnpqrstuvwxyz]{58}", recipient), "invalid_recipient")
    require(policy.get("recipient_sha256") == hashlib.sha256((recipient + "\n").encode()).hexdigest(), "recipient_digest_mismatch")


def validate_context(env, mode):
    require(mode in {"rehearsal", "real"}, "invalid_mode")
    require(env.get("GITHUB_REPOSITORY") == REPOSITORY and env.get("GITHUB_EVENT_NAME") == "workflow_dispatch", "wrong_repository_or_event")
    require(env.get("GITHUB_REF") == "refs/heads/main" and env.get("GITHUB_WORKFLOW_REF") == REPOSITORY + "/" + WORKFLOW + "@refs/heads/main", "wrong_workflow_or_ref")
    require(env.get("GITHUB_JOB") == "execution", "wrong_job")
    for key in ("GITHUB_RUN_ID", "GITHUB_REPOSITORY_ID"):
        require(bool(re.fullmatch(r"[1-9][0-9]*", env.get(key, ""))), "invalid_runtime_identity")
    require(env["GITHUB_REPOSITORY_ID"] == str(REPOSITORY_ID), "wrong_repository_id")
    require(env.get("GITHUB_RUN_NUMBER") == ("1" if mode == "rehearsal" else "2") and env.get("GITHUB_RUN_ATTEMPT") == "1", "execution_slot_consumed")
    require(sha(env.get("GITHUB_SHA"), 40) and env.get("GITHUB_WORKFLOW_SHA") == env["GITHUB_SHA"], "wrong_workflow_revision")


def evidence_item(item, today, *, basis=True):
    require(isinstance(item, dict), "missing_readiness_evidence")
    try:
        observed = date.fromisoformat(item.get("verified_at", ""))
    except (TypeError, ValueError):
        raise GuardError("invalid_evidence_date") from None
    require(observed <= today, "future_evidence")
    for key in (("reference", "basis") if basis else ("reference",)):
        text = item.get(key)
        require(isinstance(text, str) and len(text.strip()) >= 12 and not re.search(r"\b(todo|tbd|pending|unknown|placeholder|replace.me)\b", text, re.I), "placeholder_evidence")
    reference = item["reference"]
    require(bool(re.fullmatch(r"https://[A-Za-z0-9][A-Za-z0-9.-]*(?:/[^\s]*)?", reference)) or
            (reference.startswith("sha256:") and sha(reference[7:])), "invalid_evidence_reference")


def validate_readiness(comment, policy, mode, today):
    require(isinstance(comment, dict), "invalid_readiness_comment")
    require(comment.get("user", {}).get("login") == OWNER and comment.get("issue_url") == API_ROOT + "/issues/" + str(policy["implementation_pr"]), "untrusted_readiness_comment")
    record = parse(comment.get("body"))
    require(isinstance(record, dict) and record.get("schema") == "readiness-v1" and record.get("status") == "PASS" and record.get("mode") == mode, "readiness_not_pass")
    require(record.get("assignment_id") == ASSIGNMENT and record.get("manifest_sha256") == MANIFEST, "wrong_readiness_assignment")
    require(sha(record.get("checkout_sha"), 40) and positive(record.get("workflow_id")) and record.get("recipient_sha256") == policy["recipient_sha256"], "unbound_readiness")
    evidence = record.get("evidence", {})
    require(isinstance(evidence, dict), "missing_readiness_evidence")
    evidence_item(evidence.get("cost"), today)
    require(evidence["cost"].get("zero_additional_cost") is True, "cost_not_established")
    if mode == "real":
        for name in ("rights", "entitlement", "local_recovery"):
            evidence_item(evidence.get(name), today, basis=name != "local_recovery")
        require(evidence["rights"].get("private_retention_permitted") is True and evidence["rights"].get("controlled_review_status") in {"NOT RUN", "PERMITTED"}, "rights_not_established")
        require(evidence["rights"].get("encrypted_transport_permitted") is True, "encrypted_transport_not_established")
        require(evidence["entitlement"].get("historical_sip_zero_cost") is True, "entitlement_not_established")
        recovery = evidence["local_recovery"]
        require(recovery.get("verified") is True and positive(recovery.get("rehearsal_run_id")) and recovery.get("recipient_sha256") == policy["recipient_sha256"] and sha(recovery.get("ciphertext_sha256")) and sha(recovery.get("recovered_plaintext_sha256")), "recovery_not_established")
    return record


def validate_pr(pr, record):
    require(pr.get("merged") is True and pr.get("state") == "closed" and not pr.get("draft"), "implementation_not_merged")
    require(pr.get("base", {}).get("ref") == "main" and pr.get("base", {}).get("repo", {}).get("full_name") == REPOSITORY and pr.get("head", {}).get("repo", {}).get("full_name") == REPOSITORY, "wrong_implementation_repository")
    require(pr.get("head", {}).get("sha") == record["checkout_sha"] and sha(pr.get("merge_commit_sha"), 40), "unreviewed_checkout")


def validate_history(runs, record, env, mode):
    expected = 1 if mode == "rehearsal" else 2
    require(len(runs) == expected and {run.get("run_number") for run in runs} == set(range(1, expected + 1)), "incomplete_or_consumed_history")
    require(len({run.get("id") for run in runs}) == expected, "duplicate_run_history")
    for run in runs:
        number = run.get("run_number")
        require(positive(run.get("id")) and run.get("workflow_id") == record["workflow_id"] and run.get("run_attempt") == 1 and run.get("event") == "workflow_dispatch" and run.get("head_branch") == "main", "foreign_or_retried_run")
        require(run.get("repository", {}).get("id") == int(env["GITHUB_REPOSITORY_ID"]) and run.get("head_repository", {}).get("id") == int(env["GITHUB_REPOSITORY_ID"]), "foreign_run_repository")
        require(run.get("display_title") == "historical-input-" + ("rehearsal" if number == 1 else "real"), "wrong_historical_phase")
        if number == expected:
            require(run.get("id") == int(env["GITHUB_RUN_ID"]) and run.get("head_sha") == env["GITHUB_SHA"] and run.get("status") == "in_progress" and run.get("conclusion") is None, "current_run_not_durable")
        else:
            require(run.get("status") == "completed" and run.get("conclusion") == "success" and record["evidence"]["local_recovery"]["rehearsal_run_id"] == run["id"], "rehearsal_not_recovered")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise GuardError("github_redirect_refused")


class GitHub:
    def __init__(self, token):
        require(isinstance(token, str) and bool(token), "missing_github_read_token")
        self.token = token
        self.opener = build_opener(NoRedirect)

    def __call__(self, path):
        require((path == "" or path.startswith("/")) and ".." not in path.split("/") and "//" not in path and "#" not in path, "invalid_github_path")
        request = Request(API_ROOT + path, headers={"Authorization": "Bearer " + self.token, "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}, method="GET")
        try:
            with self.opener.open(request, timeout=30) as response:
                require(response.status == 200, "github_read_failed")
                body = response.read(8 * 1024 * 1024 + 1)
                require(len(body) <= 8 * 1024 * 1024, "github_response_too_large")
                return parse(body)
        except (HTTPError, URLError, TimeoutError, OSError):
            raise GuardError("github_read_failed") from None


def history(api, workflow_id):
    records, total = [], None
    for page in range(1, 101):
        result = api(f"/actions/workflows/{workflow_id}/runs?per_page=100&page={page}")
        count, batch = result.get("total_count"), result.get("workflow_runs")
        require(type(count) is int and 0 <= count <= 2 and isinstance(batch, list), "consumed_or_invalid_history")
        require(total is None or total == count, "history_changed_during_read")
        total = count
        records.extend(batch)
        if len(records) == total:
            return records
        require(batch and len(records) < total, "incomplete_run_history")
    raise GuardError("incomplete_run_history")


def verify(api, policy, env, mode, comment_id, today):
    validate_policy(policy)
    validate_context(env, mode)
    require(positive(comment_id), "invalid_readiness_comment_id")
    repository = api("")
    require(repository.get("full_name") == REPOSITORY and repository.get("id") == int(env["GITHUB_REPOSITORY_ID"]) and repository.get("private") is False, "wrong_or_private_repository")
    comment = api(f"/issues/comments/{comment_id}")
    require(comment.get("id") == comment_id, "wrong_readiness_comment_id")
    record = validate_readiness(comment, policy, mode, today)
    pr = api(f"/pulls/{policy['implementation_pr']}")
    validate_pr(pr, record)
    comparison = api(f"/compare/{pr['merge_commit_sha']}...{env['GITHUB_SHA']}")
    require(comparison.get("status") in {"identical", "ahead"} and comparison.get("behind_by") == 0, "implementation_not_in_main")
    trees = [api(f"/git/trees/{revision}") for revision in (record["checkout_sha"], env["GITHUB_SHA"])]
    for prefix in ("tools", "src"):
        entries = [[entry for entry in tree.get("tree", []) if entry.get("path") == prefix and entry.get("type") == "tree"] for tree in trees]
        require(all(not tree.get("truncated") for tree in trees) and all(len(entry) == 1 for entry in entries) and entries[0][0]["sha"] == entries[1][0]["sha"], "execution_code_changed")
    contents = [api(f"/contents/{WORKFLOW}?ref={revision}") for revision in (record["checkout_sha"], env["GITHUB_WORKFLOW_SHA"])]
    require(all(item.get("type") == "file" and item.get("encoding") == "base64" for item in contents), "workflow_missing")
    try:
        workflow_bytes = [base64.b64decode(item["content"].replace("\n", ""), validate=True) for item in contents]
    except (ValueError, KeyError):
        raise GuardError("workflow_missing") from None
    require(workflow_bytes[0] and workflow_bytes[0] == workflow_bytes[1], "workflow_changed")
    workflow = api(f"/actions/workflows/{record['workflow_id']}")
    require(workflow.get("id") == record["workflow_id"] and workflow.get("path") == WORKFLOW and workflow.get("state") == "active", "wrong_workflow_identity")
    validate_history(history(api, record["workflow_id"]), record, env, mode)
    jobs = api(f"/actions/runs/{env['GITHUB_RUN_ID']}/attempts/1/jobs?per_page=100")
    require(jobs.get("total_count") == 1 and isinstance(jobs.get("jobs"), list) and len(jobs["jobs"]) == 1, "ambiguous_execution_job")
    job = jobs["jobs"][0]
    require(job.get("name") == "execution" and job.get("run_id") == int(env["GITHUB_RUN_ID"]) and job.get("status") == "in_progress" and job.get("conclusion") is None and positive(job.get("id")), "execution_job_not_durable")
    try:
        started = datetime.fromisoformat(job.get("started_at", "").replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError):
        raise GuardError("execution_job_not_durable") from None
    require(started.tzinfo is not None and started.date() <= today, "execution_job_not_durable")
    return {"schema": "historical-execution-v1", "status": "PASS", "assignment_id": ASSIGNMENT, "manifest_sha256": MANIFEST, "repository": REPOSITORY, "repository_id": repository["id"], "mode": mode, "checkout_sha": record["checkout_sha"], "workflow_sha": env["GITHUB_WORKFLOW_SHA"], "workflow_id": record["workflow_id"], "recipient_sha256": policy["recipient_sha256"], "run_id": int(env["GITHUB_RUN_ID"]), "run_number": int(env["GITHUB_RUN_NUMBER"]), "run_attempt": 1, "readiness_comment_id": comment_id, "implementation_pr": policy["implementation_pr"], "readiness_status": "PASS", "lifetime_status": "PASS", "evidence": record["evidence"]}


def approval(execution, storage_root):
    evidence, real = execution["evidence"], execution["mode"] == "real"
    return {"assignment_id": ASSIGNMENT, "manifest_sha256": MANIFEST, "storage_root": str(storage_root), "zero_additional_cost": True, "cost_basis": evidence["cost"]["basis"], "sip_daily_entitlement_basis": evidence["entitlement"]["basis"] if real else "Synthetic rehearsal only; no provider request authorized", "non_public_storage": True, "retention_rights_basis": evidence["rights"]["basis"] if real else "Invented synthetic rows only", "reviewer_retrieval_path": "Operator recovery receipt: " + evidence["local_recovery"]["reference"] + "; Guidance private review: " + evidence["rights"]["controlled_review_status"] if real else "Synthetic rehearsal awaiting operator recovery", "approved_by": OWNER + " readiness comment " + str(execution["readiness_comment_id"]), "provider_requests_per_minute": 20}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--readiness-comment-id", required=True)
    parser.add_argument("--mode", choices=("rehearsal", "real"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--storage-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        validate_context(os.environ, args.mode)
        policy = parse(args.policy.read_bytes())
        validate_policy(policy)
        require(hashlib.sha256(encode(parse(MANIFEST_PATH.read_bytes()))).hexdigest() == MANIFEST, "frozen_manifest_changed")
        require(bool(re.fullmatch(r"[1-9][0-9]*", args.readiness_comment_id)), "invalid_readiness_comment_id")
        require(args.output_dir.is_absolute() and args.storage_root.is_absolute() and args.output_dir != args.storage_root and not args.output_dir.exists(), "unsafe_guard_output")
        api = GitHub(os.environ.get("GITHUB_TOKEN"))
        result = verify(api, policy, os.environ, args.mode, int(args.readiness_comment_id), datetime.now(timezone.utc).date())
        args.output_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
        (args.output_dir / "execution.json").write_bytes(encode(result))
        (args.output_dir / "approval.json").write_bytes(encode(approval(result, args.storage_root)))
        output = os.environ.get("GITHUB_OUTPUT")
        require(bool(output), "missing_github_output")
        with open(output, "a", encoding="utf-8") as stream:
            stream.write("checkout_sha=" + result["checkout_sha"] + "\n")
        print('{"status":"PASS"}')
        return 0
    except (GuardError, OSError, ValueError, TypeError, KeyError, AttributeError, IndexError):
        print('{"status":"BLOCKED","reason":"execution_guard_refused"}')
        return 2


if __name__ == "__main__":
    sys.exit(main())
