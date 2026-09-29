"""Read-only guard for two phases after three exact reviewed zero-job failures.

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
WORKFLOW_ID = 369770564
POLICY_SCHEMA = "historical-execution-policy-v2"
READINESS_SCHEMA = "readiness-v2"
EXECUTION_SCHEMA = "historical-execution-v2"
LOCAL_RECOVERY_SCHEMA = "historical-local-recovery-v2"
RECOVERY_CONTRACT_SHA256 = "6b49a4956c8196c432e9798149e2e1544b075a13353351cb10dfe241f72aae7a"
ORIGINAL_MERGE = "33ec181ca60adaf2f7c0ef19a1889a5517161585"
ORIGINAL_HEAD = "eb2b417a7a2289ab22c239ccfe06c20daf1dde7b"
ASSIGNMENT = "spicystock-historical-input-2026-09-28"
MANIFEST = "8d92ed5c56464fe9f342d024da14aa1521f6025d47ec32a6324a298b8fb63ebc"
API_ROOT = "https://api.github.com/repos/" + REPOSITORY
MANIFEST_PATH = Path(__file__).resolve().parents[1] / "docs/input-truthfulness/2026-09-28-historical-input-evidence/acquisition-manifest.json"
POLICY_PATH = Path(__file__).with_name("historical-execution-policy.json")
RECOVERY_PATH = Path(__file__).with_name("historical-workflow-recovery.json")
BINDING_FIELDS = ("repository", "repository_id", "assignment_id", "manifest_sha256",
                  "workflow_id", "workflow_path", "recipient_sha256", "run_id", "run_number",
                  "run_attempt", "assignment_phase", "mode", "checkout_sha", "workflow_sha",
                  "implementation_pr", "readiness_comment_id", "recovery_contract_sha256")


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
    require(isinstance(policy, dict) and policy.get("schema") == POLICY_SCHEMA, "invalid_policy")
    require(positive(policy.get("implementation_pr")) and policy["implementation_pr"] != 94, "unbound_implementation_pr")
    require(policy.get("recovery_contract_sha256") == RECOVERY_CONTRACT_SHA256, "wrong_recovery_contract")
    recipient = policy.get("recipient", "")
    require(isinstance(recipient, str) and re.fullmatch(r"age1[023456789acdefghjklmnpqrstuvwxyz]{58}", recipient), "invalid_recipient")
    require(policy.get("recipient_sha256") == hashlib.sha256((recipient + "\n").encode()).hexdigest(), "recipient_digest_mismatch")


def recovery_contract():
    contract = parse(RECOVERY_PATH.read_bytes())
    require(hashlib.sha256(encode(contract)).hexdigest() == RECOVERY_CONTRACT_SHA256, "changed_recovery_contract")
    return contract


def load_policy(path=None):
    recovery_contract()
    policy = parse((POLICY_PATH if path is None else Path(path)).read_bytes())
    validate_policy(policy)
    return policy


def phase_slot(mode):
    require(mode in {"rehearsal", "real"}, "invalid_mode")
    return (4, 1) if mode == "rehearsal" else (5, 2)


def validate_phase_binding(record):
    """Pure shared identity check; callers enforce their own schema/status.

    Manifest and recipient hashes are shape-checked here; the package verifies
    them against its supplied evidence. The full guard/wrapper also pins policy.
    Native numbering is never inferred by subtracting an unchecked offset.
    """
    require(isinstance(record, dict), "invalid_execution_binding")
    native, phase = phase_slot(record.get("mode"))
    for key in ("repository_id", "workflow_id", "run_id", "run_number", "run_attempt",
                "assignment_phase", "implementation_pr", "readiness_comment_id"):
        require(positive(record.get(key)), "invalid_execution_binding")
    require(record["run_number"] == native and record["assignment_phase"] == phase and record["run_attempt"] == 1, "wrong_execution_phase")
    require(record.get("repository") == REPOSITORY and record["repository_id"] == REPOSITORY_ID and
            record.get("assignment_id") == ASSIGNMENT and record["workflow_id"] == WORKFLOW_ID and
            record.get("workflow_path") == WORKFLOW and record["implementation_pr"] != 94, "wrong_execution_identity")
    require(record.get("recovery_contract_sha256") == RECOVERY_CONTRACT_SHA256, "wrong_recovery_contract")
    for key, size in (("manifest_sha256", 64), ("recipient_sha256", 64), ("checkout_sha", 40), ("workflow_sha", 40)):
        require(sha(record.get(key), size), "invalid_execution_binding")
    return {key: record[key] for key in BINDING_FIELDS}


def validate_execution_binding(record, policy):
    binding = validate_phase_binding(record)
    validate_policy(policy)
    require(binding["manifest_sha256"] == MANIFEST and binding["recipient_sha256"] == policy["recipient_sha256"] and
            binding["implementation_pr"] == policy["implementation_pr"], "unbound_execution_policy")
    return binding


def validate_context(env, mode):
    native, _ = phase_slot(mode)
    require(env.get("GITHUB_REPOSITORY") == REPOSITORY and env.get("GITHUB_EVENT_NAME") == "workflow_dispatch", "wrong_repository_or_event")
    require(env.get("GITHUB_REF") == "refs/heads/main" and env.get("GITHUB_WORKFLOW_REF") == REPOSITORY + "/" + WORKFLOW + "@refs/heads/main", "wrong_workflow_or_ref")
    require(env.get("GITHUB_JOB") == "execution", "wrong_job")
    for key in ("GITHUB_RUN_ID", "GITHUB_REPOSITORY_ID"):
        require(bool(re.fullmatch(r"[1-9][0-9]*", env.get(key, ""))), "invalid_runtime_identity")
    require(env["GITHUB_REPOSITORY_ID"] == str(REPOSITORY_ID), "wrong_repository_id")
    require(env.get("GITHUB_RUN_NUMBER") == str(native) and env.get("GITHUB_RUN_ATTEMPT") == "1", "execution_slot_consumed")
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
    require(isinstance(record, dict) and record.get("schema") == READINESS_SCHEMA and record.get("status") == "PASS" and record.get("mode") == mode, "readiness_not_pass")
    native, phase = phase_slot(mode)
    require(type(record.get("run_number")) is int and record["run_number"] == native and
            type(record.get("assignment_phase")) is int and record["assignment_phase"] == phase and
            record.get("recovery_contract_sha256") == RECOVERY_CONTRACT_SHA256, "stale_phase_readiness")
    require(record.get("assignment_id") == ASSIGNMENT and record.get("manifest_sha256") == MANIFEST, "wrong_readiness_assignment")
    require(sha(record.get("checkout_sha"), 40) and type(record.get("workflow_id")) is int and record["workflow_id"] == WORKFLOW_ID and record.get("recipient_sha256") == policy["recipient_sha256"], "unbound_readiness")
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
        require(recovery.get("schema") == LOCAL_RECOVERY_SCHEMA and recovery.get("recovery_contract_sha256") == RECOVERY_CONTRACT_SHA256 and
                type(recovery.get("run_number")) is int and recovery["run_number"] == 4 and
                type(recovery.get("assignment_phase")) is int and recovery["assignment_phase"] == 1 and
                type(recovery.get("run_attempt")) is int and recovery["run_attempt"] == 1 and
                recovery.get("checkout_sha") == record["checkout_sha"] and sha(recovery.get("workflow_sha"), 40), "stale_recovery_binding")
        require(recovery.get("verified") is True and positive(recovery.get("rehearsal_run_id")) and recovery.get("recipient_sha256") == policy["recipient_sha256"] and sha(recovery.get("ciphertext_sha256")) and sha(recovery.get("recovered_plaintext_sha256")), "recovery_not_established")
    return record


def validate_pr(pr, record, expected_pr):
    require(type(pr.get("number")) is int and pr["number"] == expected_pr, "wrong_implementation_pr")
    require(pr.get("merged") is True and pr.get("state") == "closed" and not pr.get("draft"), "implementation_not_merged")
    require(pr.get("base", {}).get("ref") == "main" and pr.get("base", {}).get("repo", {}).get("full_name") == REPOSITORY and pr.get("head", {}).get("repo", {}).get("full_name") == REPOSITORY, "wrong_implementation_repository")
    require(pr.get("head", {}).get("sha") == record["checkout_sha"] and sha(pr.get("merge_commit_sha"), 40), "unreviewed_checkout")


def run_binding(run):
    require(isinstance(run, dict), "invalid_run_history")
    for key in ("id", "run_number", "run_attempt", "workflow_id"):
        require(positive(run.get(key)), "invalid_run_history")
    require(sha(run.get("head_sha"), 40), "invalid_run_history")
    binding = {key: run.get(key) for key in ("id", "run_number", "run_attempt", "workflow_id", "path",
                                           "event", "head_branch", "head_sha", "status", "conclusion")}
    for key in ("repository", "head_repository"):
        repository = run.get(key)
        require(isinstance(repository, dict) and type(repository.get("id")) is int and
                repository["id"] == REPOSITORY_ID and repository.get("full_name") == REPOSITORY, "foreign_run_repository")
        binding[key + "_id"] = repository["id"]
    return binding


def validate_history(runs, record, env, mode, jobs_by_run, contract):
    native, _ = phase_slot(mode)
    bindings = [run_binding(run) for run in runs]
    require(len(bindings) == native and {run["run_number"] for run in bindings} == set(range(1, native + 1)), "incomplete_or_consumed_history")
    require(len({run["id"] for run in bindings}) == native, "duplicate_run_history")
    exceptions = {item["id"]: item for item in contract["exceptions"]}
    for run, binding in zip(runs, bindings):
        number, run_id = binding["run_number"], binding["id"]
        require(run_id in jobs_by_run and isinstance(jobs_by_run[run_id], list), "missing_attempt_jobs")
        if run_id in exceptions:
            expected = exceptions[run_id]
            require(binding == {key: expected[key] for key in binding}, "changed_reviewed_exception")
            require(jobs_by_run[run_id] == [], "reviewed_exception_has_jobs")
            continue
        require(number in (4, 5) and binding["workflow_id"] == WORKFLOW_ID and binding["path"] == WORKFLOW and
                binding["run_attempt"] == 1 and binding["event"] == "workflow_dispatch" and binding["head_branch"] == "main", "unaccounted_or_retried_run")
        require(run.get("display_title") == "historical-input-" + ("rehearsal" if number == 4 else "real"), "wrong_historical_phase")
        require(len(jobs_by_run[run_id]) == 1, "ambiguous_execution_job")
        if number == native:
            require(run_id == int(env["GITHUB_RUN_ID"]) and binding["head_sha"] == env["GITHUB_SHA"] and binding["status"] == "in_progress" and binding["conclusion"] is None, "current_run_not_durable")
        else:
            recovery = record["evidence"]["local_recovery"]
            require(binding["status"] == "completed" and binding["conclusion"] == "success" and
                    recovery["rehearsal_run_id"] == run_id and recovery["workflow_sha"] == binding["head_sha"], "rehearsal_not_recovered")
    require(set(exceptions) <= {item["id"] for item in bindings}, "missing_reviewed_exception")


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


def collection(api, path, key, maximum):
    """Read unfiltered pages through an empty terminator, with stable totals."""
    records, total = [], None
    for page in range(1, 101):
        result = api(f"{path}?per_page=100&page={page}")
        require(isinstance(result, dict), "invalid_collection")
        count, batch = result.get("total_count"), result.get(key)
        require(type(count) is int and 0 <= count <= maximum and isinstance(batch, list) and len(batch) <= 100, "consumed_or_invalid_history")
        require(total is None or total == count, "history_changed_during_read")
        total = count
        if not batch:
            require(len(records) == total, "incomplete_run_history")
            return records
        records.extend(batch)
        require(len(records) <= total and all(isinstance(item, dict) and positive(item.get("id")) for item in records), "incomplete_run_history")
        require(len({item["id"] for item in records}) == len(records), "duplicate_run_history")
    raise GuardError("incomplete_run_history")


def history(api, workflow_id):
    require(type(workflow_id) is int and workflow_id == WORKFLOW_ID, "wrong_workflow_identity")
    return collection(api, f"/actions/workflows/{workflow_id}/runs", "workflow_runs", 5)


def validate_job(job, run, today):
    require(job.get("name") == "execution" and type(job.get("run_id")) is int and job["run_id"] == run["id"] and
            job.get("status") == run["status"] and job.get("conclusion") == run["conclusion"] and positive(job.get("id")), "execution_job_not_durable")
    try:
        started = datetime.fromisoformat(job.get("started_at", "").replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError):
        raise GuardError("execution_job_not_durable") from None
    require(started.tzinfo is not None and started.date() <= today, "execution_job_not_durable")


def verify(api, policy, env, mode, comment_id, today):
    validate_policy(policy)
    validate_context(env, mode)
    contract = recovery_contract()
    require(positive(comment_id), "invalid_readiness_comment_id")
    repository = api("")
    require(repository.get("full_name") == REPOSITORY and repository.get("id") == int(env["GITHUB_REPOSITORY_ID"]) and repository.get("private") is False, "wrong_or_private_repository")
    comment = api(f"/issues/comments/{comment_id}")
    require(comment.get("id") == comment_id, "wrong_readiness_comment_id")
    record = validate_readiness(comment, policy, mode, today)
    pr = api(f"/pulls/{policy['implementation_pr']}")
    validate_pr(pr, record, policy["implementation_pr"])
    original = api("/pulls/94")
    require(type(original.get("number")) is int and original["number"] == 94 and original.get("merged") is True and original.get("merge_commit_sha") == ORIGINAL_MERGE and
            original.get("head", {}).get("sha") == ORIGINAL_HEAD, "original_implementation_lineage_changed")
    ancestry = api(f"/compare/{ORIGINAL_MERGE}...{record['checkout_sha']}")
    require(ancestry.get("status") in {"identical", "ahead"} and ancestry.get("behind_by") == 0, "missing_original_implementation_ancestry")
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
    runs = history(api, record["workflow_id"])
    jobs_by_run = {}
    for run in runs:
        individual = api(f"/actions/runs/{run['id']}")
        require(run_binding(individual) == run_binding(run), "run_detail_changed_or_missing")
        jobs_by_run[run["id"]] = collection(api, f"/actions/runs/{run['id']}/attempts/1/jobs", "jobs", 1)
    validate_history(runs, record, env, mode, jobs_by_run, contract)
    for run in runs:
        if run["run_number"] in (4, 5):
            validate_job(jobs_by_run[run["id"]][0], run, today)
    repeated = history(api, record["workflow_id"])
    require(sorted((run_binding(item) for item in repeated), key=lambda item: item["id"]) ==
            sorted((run_binding(item) for item in runs), key=lambda item: item["id"]), "history_changed_during_read")
    validate_history(repeated, record, env, mode, jobs_by_run, contract)
    history_evidence = {"schema": "historical-history-verification-v1", "observed_on": today.isoformat(),
        "first_listing_sha256": hashlib.sha256(encode(runs)).hexdigest(),
        "repeated_listing_sha256": hashlib.sha256(encode(repeated)).hexdigest(),
        "runs": [{**run_binding(run), "attempt_jobs_count": len(jobs_by_run[run["id"]]),
                  "attempt_job_ids": [job["id"] for job in jobs_by_run[run["id"]]],
                  "attempt_jobs_sha256": hashlib.sha256(encode(jobs_by_run[run["id"]])).hexdigest()} for run in runs]}
    result = {"schema": EXECUTION_SCHEMA, "status": "PASS", "assignment_id": ASSIGNMENT, "manifest_sha256": MANIFEST,
              "repository": REPOSITORY, "repository_id": repository["id"], "mode": mode, "checkout_sha": record["checkout_sha"],
              "workflow_sha": env["GITHUB_WORKFLOW_SHA"], "workflow_id": record["workflow_id"], "workflow_path": WORKFLOW,
              "recipient_sha256": policy["recipient_sha256"], "run_id": int(env["GITHUB_RUN_ID"]), "run_number": int(env["GITHUB_RUN_NUMBER"]),
              "run_attempt": 1, "assignment_phase": phase_slot(mode)[1], "readiness_comment_id": comment_id,
              "implementation_pr": policy["implementation_pr"], "recovery_contract_sha256": RECOVERY_CONTRACT_SHA256,
              "readiness_status": "PASS", "lifetime_status": "PASS", "evidence": record["evidence"],
              "history_verification": history_evidence}
    validate_execution_binding(result, policy)
    return result


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
        policy = load_policy(args.policy)
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
