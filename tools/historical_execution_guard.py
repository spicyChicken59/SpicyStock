"""Read-only prospective delivery guard after the exact accepted rehearsal.

Owner personal-use authorization is not provider consent. A new reviewed source
and technical evidence binding never relabels the old transport/recovery record.
No provider credentials are read here.
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import historical_incident_recovery as incident

REPOSITORY = "spicyChicken59/SpicyStock"
REPOSITORY_ID = 1352997802
OWNER = "spicyChicken59"
WORKFLOW = ".github/workflows/historical-input-proof.yml"
WORKFLOW_ID = 369770564
POLICY_SCHEMA = "historical-execution-policy-v4"
READINESS_SCHEMA = "readiness-v4"
EXECUTION_SCHEMA = "historical-execution-v3"
LOCAL_RECOVERY_SCHEMA = "historical-local-recovery-v2"
PREVIOUS_COMPATIBILITY_CONTRACT_SHA256 = "61ccac3fc27e9a62ccadee73ec0c069536994fedefd76a272aac129fbd7a484d"
PR97_COMPATIBILITY_CONTRACT_SHA256 = "567f8f0267a4e1923bf2b61d28e74e4fe94905d9405826c9f735e472db66822d"
COMPATIBILITY_CONTRACT_SHA256 = "a425ce24be52c22119f39df1444b9518586f15734998f6d068090d4cef957be8"
RELEASE_EVIDENCE_PATH = "docs/input-truthfulness/historical-native6-release-evidence.json"
ORIGINAL_RECOVERY_CONTRACT_SHA256 = "6b49a4956c8196c432e9798149e2e1544b075a13353351cb10dfe241f72aae7a"
RECOVERY_CONTRACT_SHA256 = incident.RECOVERY_CONTRACT_SHA256
ORIGINAL_MERGE = "33ec181ca60adaf2f7c0ef19a1889a5517161585"
ORIGINAL_HEAD = "eb2b417a7a2289ab22c239ccfe06c20daf1dde7b"
ASSIGNMENT = "spicystock-historical-input-2026-09-28"
MANIFEST = "8d92ed5c56464fe9f342d024da14aa1521f6025d47ec32a6324a298b8fb63ebc"
RECIPIENT_SHA256 = "0f539a14ca5bf12a1ad3a706747316bc886d375b17e757af32c237aa39b8ec4f"
API_ROOT = "https://api.github.com/repos/" + REPOSITORY
MANIFEST_PATH = Path(__file__).resolve().parents[1] / "docs/input-truthfulness/2026-09-28-historical-input-evidence/acquisition-manifest.json"
POLICY_PATH = Path(__file__).with_name("historical-execution-policy.json")
RECOVERY_PATH = Path(__file__).with_name("historical-workflow-recovery.json")
COMPATIBILITY_PATH = Path(__file__).with_name("historical-native6-compatibility.json")
BINDING_FIELDS = ("repository", "repository_id", "assignment_id", "manifest_sha256",
                  "workflow_id", "workflow_path", "recipient_sha256", "run_id", "run_number",
                  "run_attempt", "assignment_phase", "mode", "checkout_sha", "workflow_sha",
                  "implementation_pr", "readiness_comment_id", "recovery_contract_sha256")
DELIVERY_BINDING_FIELDS = ("compatibility_contract_sha256", "release_evidence_sha256")
RELEASE_CHECKS = ("central_capacity", "stress_capacity", "central_exact_recovery", "stress_exact_recovery",
                  "legacy_gzip_recovery", "exact_v2_equivalence", "shared_offline_step", "total_job_envelope", "process_memory", "normal_ci")
RELEASE_PROOFS = ("capacity", "runtime", "equivalence", "legacy_recovery", "normal_ci")
REPAIR_CHECKS = ("input_normalization", "exact_incident_recovery", "wrapper_receipt_binding", "normal_ci")


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
    require(positive(policy.get("implementation_pr")) and policy["implementation_pr"] > 97, "unbound_implementation_pr")
    require(policy.get("recovery_contract_sha256") == RECOVERY_CONTRACT_SHA256, "wrong_recovery_contract")
    require(policy.get("compatibility_contract_sha256") == COMPATIBILITY_CONTRACT_SHA256, "wrong_compatibility_contract")
    recipient = policy.get("recipient", "")
    require(isinstance(recipient, str) and re.fullmatch(r"age1[023456789acdefghjklmnpqrstuvwxyz]{58}", recipient), "invalid_recipient")
    require(policy.get("recipient_sha256") == hashlib.sha256((recipient + "\n").encode()).hexdigest(), "recipient_digest_mismatch")
    require(policy["recipient_sha256"] == RECIPIENT_SHA256, "unaccepted_delivery_recipient")


def recovery_contract():
    contract = parse(RECOVERY_PATH.read_bytes())
    require(hashlib.sha256(encode(contract)).hexdigest() == ORIGINAL_RECOVERY_CONTRACT_SHA256, "changed_recovery_contract")
    try:
        incident.incident_contract()
    except incident.IncidentError as error:
        raise GuardError("changed_incident_contract") from error
    return contract


def compatibility_contract():
    contract = parse(COMPATIBILITY_PATH.read_bytes())
    require(hashlib.sha256(encode(contract)).hexdigest() == COMPATIBILITY_CONTRACT_SHA256,
            "changed_compatibility_contract")
    return contract


def load_policy(path=None):
    recovery_contract()
    compatibility_contract()
    policy = parse((POLICY_PATH if path is None else Path(path)).read_bytes())
    validate_policy(policy)
    return policy


def phase_slot(mode):
    require(mode in {"rehearsal", "real"}, "invalid_mode")
    return (4, 1) if mode == "rehearsal" else (6, 2)


def validate_phase_binding(record):
    """Pure shared identity check; callers enforce their own schema/status.

    Manifest and recipient hashes are shape-checked here; the package verifies
    them against its supplied evidence. The full guard/wrapper also pins policy.
    Native numbering is never inferred by subtracting an unchecked offset.
    """
    require(isinstance(record, dict), "invalid_execution_binding")
    native, phase = phase_slot(record.get("mode"))
    historical = record.get("recovery_contract_sha256") == ORIGINAL_RECOVERY_CONTRACT_SHA256
    if historical and record.get("mode") == "real":
        native = 5
    for key in ("repository_id", "workflow_id", "run_id", "run_number", "run_attempt",
                "assignment_phase", "implementation_pr", "readiness_comment_id"):
        require(positive(record.get(key)), "invalid_execution_binding")
    require(record["run_number"] == native and record["assignment_phase"] == phase and record["run_attempt"] == 1, "wrong_execution_phase")
    require(record.get("repository") == REPOSITORY and record["repository_id"] == REPOSITORY_ID and
            record.get("assignment_id") == ASSIGNMENT and record["workflow_id"] == WORKFLOW_ID and
            record.get("workflow_path") == WORKFLOW and record["implementation_pr"] != 94, "wrong_execution_identity")
    require(historical or record.get("recovery_contract_sha256") == RECOVERY_CONTRACT_SHA256, "wrong_recovery_contract")
    for key, size in (("manifest_sha256", 64), ("recipient_sha256", 64), ("checkout_sha", 40), ("workflow_sha", 40)):
        require(sha(record.get(key), size), "invalid_execution_binding")
    # Historical v2 receipts retain exactly their original projection. Current
    # execution requires both new digests; no legacy record is upgraded here.
    extra = DELIVERY_BINDING_FIELDS if any(k in record for k in DELIVERY_BINDING_FIELDS) else ()
    if extra:
        allowed = {PR97_COMPATIBILITY_CONTRACT_SHA256, PREVIOUS_COMPATIBILITY_CONTRACT_SHA256} if historical else {COMPATIBILITY_CONTRACT_SHA256}
        require(record.get("compatibility_contract_sha256") in allowed and
                sha(record.get("release_evidence_sha256")) and record["implementation_pr"] > (96 if historical else 97), "invalid_delivery_binding")
    else:
        require(historical, "missing_delivery_binding")
    return {key: record[key] for key in (*BINDING_FIELDS, *extra)}


def validate_execution_binding(record, policy):
    binding = validate_phase_binding(record)
    validate_policy(policy)
    require(all(key in binding for key in DELIVERY_BINDING_FIELDS), "missing_delivery_binding")
    require(binding["compatibility_contract_sha256"] == COMPATIBILITY_CONTRACT_SHA256, "stale_delivery_binding")
    require(binding["recovery_contract_sha256"] == RECOVERY_CONTRACT_SHA256, "stale_recovery_binding")
    require(binding["manifest_sha256"] == MANIFEST and binding["recipient_sha256"] == policy["recipient_sha256"] and
            binding["implementation_pr"] == policy["implementation_pr"], "unbound_execution_policy")
    return binding


def validate_context(env, mode):
    require(mode == "real", "rehearsal_slot_closed")
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
    try:
        require(date.fromisoformat(record.get("authorized_on", "")) <= today, "invalid_authorization_date")
    except (ValueError, TypeError):
        raise GuardError("invalid_authorization_date") from None
    native, phase = phase_slot(mode)
    require(type(record.get("run_number")) is int and record["run_number"] == native and
            type(record.get("assignment_phase")) is int and record["assignment_phase"] == phase and
            record.get("recovery_contract_sha256") == RECOVERY_CONTRACT_SHA256, "stale_phase_readiness")
    require(record.get("assignment_id") == ASSIGNMENT and record.get("manifest_sha256") == MANIFEST, "wrong_readiness_assignment")
    require(record.get("compatibility_contract_sha256") == COMPATIBILITY_CONTRACT_SHA256 and
            sha(record.get("release_evidence_sha256")), "unbound_delivery_readiness")
    require(sha(record.get("checkout_sha"), 40) and type(record.get("workflow_id")) is int and record["workflow_id"] == WORKFLOW_ID and record.get("recipient_sha256") == policy["recipient_sha256"], "unbound_readiness")
    evidence = record.get("evidence", {})
    require(isinstance(evidence, dict), "missing_readiness_evidence")
    evidence_item(evidence.get("cost"), today)
    require(evidence["cost"].get("zero_additional_cost") is True, "cost_not_established")
    if mode == "real":
        for name in ("owner_authorization", "entitlement", "local_recovery"):
            evidence_item(evidence.get(name), today, basis=name != "local_recovery")
        owner = evidence["owner_authorization"]
        require(owner.get("schema") == "owner-personal-use-v1" and owner.get("owner") == OWNER and
                owner.get("scope") == "personal_research" and owner.get("owner_authorized") is True and
                owner.get("owner_only_decryption") is True and owner.get("public_plaintext") is False and
                owner.get("direction_reference") == compatibility_contract()["owner_direction_reference"] and
                type(owner.get("public_ciphertext_retention_days")) is int and owner["public_ciphertext_retention_days"] == 7 and
                owner.get("provider_consent") == "NOT ASSERTED" and owner.get("controlled_review_status") == "NOT RUN",
                "owner_scope_not_authorized")
        require(evidence["entitlement"].get("historical_sip_zero_cost") is True, "entitlement_not_established")
        recovery = evidence["local_recovery"]
        require(recovery.get("schema") == LOCAL_RECOVERY_SCHEMA and recovery.get("recovery_contract_sha256") == ORIGINAL_RECOVERY_CONTRACT_SHA256 and
                type(recovery.get("run_number")) is int and recovery["run_number"] == 4 and
                type(recovery.get("assignment_phase")) is int and recovery["assignment_phase"] == 1 and
                type(recovery.get("run_attempt")) is int and recovery["run_attempt"] == 1 and
                sha(recovery.get("checkout_sha"), 40) and sha(recovery.get("workflow_sha"), 40), "stale_recovery_binding")
        require(recovery.get("verified") is True and positive(recovery.get("rehearsal_run_id")) and recovery.get("recipient_sha256") == policy["recipient_sha256"] and sha(recovery.get("ciphertext_sha256")) and sha(recovery.get("recovered_plaintext_sha256")), "recovery_not_established")
        accepted = compatibility_contract()["accepted_transport"]
        require(all(recovery.get(key) == value for key, value in accepted.items()) and
                recovery.get("manifest_sha256") == MANIFEST and
                recovery.get("reference") == "sha256:" + accepted["recovery_checkpoint_sha256"], "unaccepted_prior_transport")
    return record


def validate_pr(pr, record, expected_pr):
    require(type(pr.get("number")) is int and pr["number"] == expected_pr, "wrong_implementation_pr")
    require(pr.get("merged") is True and pr.get("state") == "closed" and not pr.get("draft"), "implementation_not_merged")
    require(pr.get("base", {}).get("ref") == "main" and pr.get("base", {}).get("repo", {}).get("full_name") == REPOSITORY and pr.get("head", {}).get("repo", {}).get("full_name") == REPOSITORY, "wrong_implementation_repository")
    require(pr.get("head", {}).get("sha") == record["checkout_sha"] and sha(pr.get("merge_commit_sha"), 40), "unreviewed_checkout")


def validate_release_date(comment, pr, record):
    """A new owner comment after merge is separate from the PR's evidence."""
    try:
        created = datetime.fromisoformat(comment.get("created_at", "").replace("Z", "+00:00"))
        merged = datetime.fromisoformat(pr.get("merged_at", "").replace("Z", "+00:00"))
        require(created.tzinfo is not None and merged.tzinfo is not None and created >= merged and
                record["authorized_on"] == created.astimezone(timezone.utc).date().isoformat(),
                "execution_release_not_after_merge")
    except (ValueError, TypeError, AttributeError, KeyError):
        raise GuardError("execution_release_not_after_merge") from None


def reviewed_file(api, path, revision):
    item = api(f"/contents/{path}?ref={revision}")
    require(item.get("type") == "file" and item.get("encoding") == "base64", "release_source_missing")
    try:
        raw = base64.b64decode(item["content"].replace("\n", ""), validate=True)
    except (ValueError, TypeError, KeyError):
        raise GuardError("release_source_missing") from None
    require(0 < len(raw) <= 2 * 1024 ** 2, "release_source_size")
    return raw


def validate_release_evidence(api, record):
    """Check reviewed declarative measurements, separately from authorization.

    The evidence file binds exact code/proof bytes, not its own commit hash.
    The dated readiness comment supplies the final reviewed checkout and file
    digest after that commit exists. These checks are not a new benchmark.
    """
    contract = compatibility_contract()
    revision = record["checkout_sha"]
    raw = reviewed_file(api, RELEASE_EVIDENCE_PATH, revision)
    require(hashlib.sha256(raw).hexdigest() == record["release_evidence_sha256"], "release_evidence_changed")
    evidence = parse(raw)
    require(isinstance(evidence, dict) and evidence.get("schema") == "historical-delivery-release-evidence-v3" and
            evidence.get("status") == "PASS" and evidence.get("compatibility_contract_sha256") == COMPATIBILITY_CONTRACT_SHA256 and
            evidence.get("manifest_sha256") == MANIFEST and evidence.get("recipient_sha256") == record["recipient_sha256"],
            "technical_release_not_established")
    require(evidence.get("delivery_envelope") == contract["delivery_envelope"], "unbound_delivery_envelope")
    checks = evidence.get("checks")
    require(isinstance(checks, dict) and set(checks) == set(RELEASE_CHECKS) and
            all(checks[key] == "PASS" for key in RELEASE_CHECKS), "technical_release_not_established")
    sources = evidence.get("source_sha256")
    require(isinstance(sources, dict) and set(sources) == set(contract["required_source_paths"]), "release_source_coverage")
    for path, digest in sources.items():
        require(sha(digest) and hashlib.sha256(reviewed_file(api, path, revision)).hexdigest() == digest,
                "release_source_changed")
    proofs = evidence.get("proofs")
    require(isinstance(proofs, dict) and set(proofs) == set(RELEASE_PROOFS), "release_proof_coverage")
    for proof in proofs.values():
        require(isinstance(proof, dict) and set(proof) == {"path", "sha256"}, "invalid_release_proof")
        path = proof["path"]
        require(isinstance(path, str) and bool(re.fullmatch(r"docs/input-truthfulness/[A-Za-z0-9_./-]+\.json", path)) and
                ".." not in path.split("/") and "//" not in path and path != RELEASE_EVIDENCE_PATH and sha(proof["sha256"]),
                "invalid_release_proof")
        proof_raw = reviewed_file(api, path, revision)
        require(hashlib.sha256(proof_raw).hexdigest() == proof["sha256"], "release_proof_changed")
        proof_record = parse(proof_raw)
        require(isinstance(proof_record, dict) and proof_record.get("status") == "PASS", "technical_release_not_established")
    # PR97's completed measurements remain pinned to PR97. Only the enumerated
    # admission files may differ; unchanged science/codec/runtime and all five
    # measured proof documents must retain their exact previous bytes.
    parent = contract["parent_delivery"]
    require(evidence.get("inherited_delivery") == parent, "unbound_parent_delivery")
    parent_raw = reviewed_file(api, parent["path"], parent["revision"])
    require(hashlib.sha256(parent_raw).hexdigest() == parent["sha256"], "parent_delivery_changed")
    parent_evidence = parse(parent_raw)
    require(parent_evidence.get("schema") == "historical-delivery-release-evidence-v2" and
            parent_evidence.get("status") == "PASS" and
            parent_evidence.get("compatibility_contract_sha256") == PR97_COMPATIBILITY_CONTRACT_SHA256 and
            parent_evidence.get("delivery_envelope") == contract["delivery_envelope"] and
            evidence["checks"] == parent_evidence.get("checks") and evidence["proofs"] == parent_evidence.get("proofs"),
            "inherited_delivery_proof_changed")
    for path, digest in parent_evidence["source_sha256"].items():
        if path not in contract["permitted_changed_code"]:
            require(sources.get(path) == digest, "inherited_source_changed")
    reader = contract["identity_reader_revision"]
    require(parent_evidence["source_sha256"].get(reader["path"]) == reader["before_sha256"] and
            sources.get(reader["path"]) == reader["after_sha256"], "unreviewed_identity_reader")
    scanner = contract["scanner_disposition"]
    require(parent_evidence["source_sha256"].get(scanner["path"]) == scanner["before_sha256"] and
            sources.get(scanner["path"]) == scanner["after_sha256"], "unreviewed_scanner_disposition")
    repair_checks = evidence.get("repair_checks")
    require(isinstance(repair_checks, dict) and set(repair_checks) == set(REPAIR_CHECKS) and
            all(value == "PASS" for value in repair_checks.values()), "repair_not_established")
    proof = evidence.get("repair_proof")
    require(isinstance(proof, dict) and set(proof) == {"path", "sha256"} and
            proof["path"] == "docs/input-truthfulness/2026-09-30-delivery-readiness-evidence/native5-recovery/proof-repair.json" and
            sha(proof["sha256"]), "invalid_repair_proof")
    repair_raw = reviewed_file(api, proof["path"], revision)
    require(hashlib.sha256(repair_raw).hexdigest() == proof["sha256"], "repair_proof_changed")
    repair = parse(repair_raw)
    require(repair.get("schema") == "historical-native6-repair-proof-v1" and repair.get("status") == "PASS" and
            repair.get("checks") == repair_checks and repair.get("source_sha256") == sources,
            "repair_not_established")
    change = api(f"/compare/{contract['continuation_base']}...{revision}")
    files = change.get("files")
    require(change.get("status") in {"identical", "ahead"} and change.get("behind_by") == 0 and
            isinstance(files, list) and len(files) < 300 and all(isinstance(item, dict) for item in files),
            "incomplete_delivery_diff")
    paths = [item.get("filename") for item in files]
    require(all(isinstance(path, str) for path in paths) and len(set(paths)) == len(paths), "incomplete_delivery_diff")
    code = []
    for item in files:
        path = item["filename"]
        require(item.get("status") != "renamed" and "previous_filename" not in item, "unreviewed_delivery_scope")
        if path in contract["permitted_changed_code"]:
            require(item.get("status") in {"added", "modified"} and sha(item.get("sha"), 40), "invalid_delivery_code_change")
            code.append({"path": path, "git_blob": item["sha"]})
        else:
            require(path in {"README.md", "CLAUDE.md", ".env.example"} or
                    path.startswith("tests/") or (item.get("status") in {"added", "modified"} and
                    (path in {"docs/input-truthfulness/2026-09-29-historical-execution.md", RELEASE_EVIDENCE_PATH} or
                     path.startswith("docs/input-truthfulness/2026-09-30-delivery-readiness-evidence/native5-recovery/"))),
                    "unreviewed_delivery_scope")
    require(evidence.get("changed_code") == sorted(code, key=lambda item: item["path"]), "release_diff_changed")
    return evidence


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


def validate_history(runs, record, env, mode, jobs_by_run, contract, artifacts_by_run=None):
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
        if run_id == incident.FAILED_RUN_ID:
            try:
                incident.validate_incident(run, jobs_by_run[run_id], (artifacts_by_run or {}).get(run_id))
            except incident.IncidentError as error:
                raise GuardError("changed_reviewed_incident") from error
            continue
        require(number in (4, 6) and binding["workflow_id"] == WORKFLOW_ID and binding["path"] == WORKFLOW and
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
    require(incident.FAILED_RUN_ID in {item["id"] for item in bindings}, "missing_reviewed_incident")


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
    return collection(api, f"/actions/workflows/{workflow_id}/runs", "workflow_runs", 6)


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
    require(comment_id != incident.CONSUMED_READINESS_COMMENT_ID, "consumed_readiness_comment")
    repository = api("")
    require(repository.get("full_name") == REPOSITORY and repository.get("id") == int(env["GITHUB_REPOSITORY_ID"]) and repository.get("private") is False, "wrong_or_private_repository")
    comment = api(f"/issues/comments/{comment_id}")
    require(comment.get("id") == comment_id, "wrong_readiness_comment_id")
    record = validate_readiness(comment, policy, mode, today)
    pr = api(f"/pulls/{policy['implementation_pr']}")
    validate_pr(pr, record, policy["implementation_pr"])
    validate_release_date(comment, pr, record)
    validate_release_evidence(api, record)
    original = api("/pulls/94")
    require(type(original.get("number")) is int and original["number"] == 94 and original.get("merged") is True and original.get("merge_commit_sha") == ORIGINAL_MERGE and
            original.get("head", {}).get("sha") == ORIGINAL_HEAD, "original_implementation_lineage_changed")
    ancestry = api(f"/compare/{ORIGINAL_MERGE}...{record['checkout_sha']}")
    require(ancestry.get("status") in {"identical", "ahead"} and ancestry.get("behind_by") == 0, "missing_original_implementation_ancestry")
    comparison = api(f"/compare/{pr['merge_commit_sha']}...{env['GITHUB_SHA']}")
    require(comparison.get("status") in {"identical", "ahead"} and comparison.get("behind_by") == 0, "implementation_not_in_main")
    trees = [api(f"/git/trees/{revision}") for revision in (record["checkout_sha"], env["GITHUB_SHA"])]
    for prefix in ("tools", "src", ".github"):
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
    jobs_by_run, artifacts_by_run = {}, {}
    for run in runs:
        individual = api(f"/actions/runs/{run['id']}")
        require(run_binding(individual) == run_binding(run) and individual.get("display_title") == run.get("display_title"), "run_detail_changed_or_missing")
        jobs_by_run[run["id"]] = collection(api, f"/actions/runs/{run['id']}/attempts/1/jobs", "jobs", 1)
        if run["id"] == incident.FAILED_RUN_ID:
            artifacts_by_run[run["id"]] = collection(api, f"/actions/runs/{run['id']}/artifacts", "artifacts", 0)
            try:
                incident.validate_incident(individual, jobs_by_run[run["id"]], artifacts_by_run[run["id"]])
            except incident.IncidentError as error:
                raise GuardError("changed_reviewed_incident") from error
    validate_history(runs, record, env, mode, jobs_by_run, contract, artifacts_by_run)
    for run in runs:
        if run["run_number"] in (4, 6):
            validate_job(jobs_by_run[run["id"]][0], run, today)
            if mode == "real" and run["run_number"] == 4:
                require(jobs_by_run[run["id"]][0]["id"] == compatibility_contract()["accepted_transport"]["job_id"],
                        "unaccepted_prior_transport_job")
    repeated = history(api, record["workflow_id"])
    require(sorted(({**run_binding(item), "display_title": item.get("display_title")} for item in repeated), key=lambda item: item["id"]) ==
            sorted(({**run_binding(item), "display_title": item.get("display_title")} for item in runs), key=lambda item: item["id"]), "history_changed_during_read")
    incident_jobs = collection(api, f"/actions/runs/{incident.FAILED_RUN_ID}/attempts/1/jobs", "jobs", 1)
    incident_artifacts = collection(api, f"/actions/runs/{incident.FAILED_RUN_ID}/artifacts", "artifacts", 0)
    require(incident_jobs == jobs_by_run[incident.FAILED_RUN_ID] and
            incident_artifacts == artifacts_by_run[incident.FAILED_RUN_ID], "incident_changed_during_read")
    validate_history(repeated, record, env, mode, jobs_by_run, contract, artifacts_by_run)
    history_evidence = {"schema": "historical-history-verification-v2", "observed_on": today.isoformat(),
        "pre_acquisition_incident": {"run_id": incident.FAILED_RUN_ID, "job_id": incident.FAILED_JOB_ID,
            "recovery_contract_sha256": RECOVERY_CONTRACT_SHA256, "artifacts_count": 0,
            "artifacts_sha256": hashlib.sha256(encode(incident_artifacts)).hexdigest()},
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
              "compatibility_contract_sha256": COMPATIBILITY_CONTRACT_SHA256,
              "release_evidence_sha256": record["release_evidence_sha256"],
              "readiness_status": "PASS", "lifetime_status": "PASS", "evidence": record["evidence"],
              "history_verification": history_evidence}
    validate_execution_binding(result, policy)
    return result


def approval(execution, storage_root):
    evidence, real = execution["evidence"], execution["mode"] == "real"
    return {"assignment_id": ASSIGNMENT, "manifest_sha256": MANIFEST, "storage_root": str(storage_root), "zero_additional_cost": True, "cost_basis": evidence["cost"]["basis"], "sip_daily_entitlement_basis": evidence["entitlement"]["basis"] if real else "Synthetic rehearsal only; no provider request authorized", "non_public_storage": True, "retention_rights_basis": "Private runner and owner-local plaintext only. Owner-authorized personal research; provider consent NOT ASSERTED. " + evidence["owner_authorization"]["basis"] if real else "Invented synthetic rows only", "reviewer_retrieval_path": "Accepted old transport recovery: " + evidence["local_recovery"]["reference"] + "; Guidance private review: NOT RUN" if real else "Synthetic rehearsal awaiting operator recovery", "approved_by": OWNER + " readiness comment " + str(execution["readiness_comment_id"]), "provider_requests_per_minute": 20}


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
