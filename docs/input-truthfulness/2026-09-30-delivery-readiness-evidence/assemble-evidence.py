"""Assemble reviewed public delivery measurements, never authorization.

Only reads small, public JSON/log receipts, current source bytes and local Git.
No provider, network, package, reconciliation, key or runtime imports. Output
must be a fresh directory outside Git. Missing evidence emits BLOCKED/NOT RUN.
The output declaration contains no own-head/self-file hash: a later independent
readiness comment would bind its exact bytes and the final reviewed head.

Use --print-input-template for the input paths and --print-receipt-contracts
for strict CI/legacy receipt requirements. Paths are repository-relative under
docs/input-truthfulness; files must already be public review artifacts.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

REPOSITORY = "spicyChicken59/SpicyStock"
BASE = "19f75f3b7ad566fb98e8e8e28fd2482a3737e9bc"
COMPATIBILITY = "61ccac3fc27e9a62ccadee73ec0c069536994fedefd76a272aac129fbd7a484d"
MANIFEST = "8d92ed5c56464fe9f342d024da14aa1521f6025d47ec32a6324a298b8fb63ebc"
RECIPIENT = "0f539a14ca5bf12a1ad3a706747316bc886d375b17e757af32c237aa39b8ec4f"
EVIDENCE = "docs/input-truthfulness/2026-09-30-delivery-readiness-evidence/"
OLD = "docs/input-truthfulness/2026-09-30-projection-compaction-evidence/"
DECLARATION = "docs/input-truthfulness/historical-delivery-release-evidence.json"
SHAPE = dict(canonical_batches=96, sessions_per_bulk_query=[288], bulk_rows=2753568,
             probe_rows=2, filled_page_requests=289)
CAPS = dict(raw=1073741824, expanded=2147483648, archive=208666624, ciphertext=209715200)
LIMITS = dict(acquisition_guard=1500, acquisition_step=1800, offline_step=1800,
              package_step=600, total_job=4500)
DATES = ("2026-09-24", "2026-09-25")
CHECKS = ("central_capacity", "stress_capacity", "central_exact_recovery", "stress_exact_recovery",
          "legacy_gzip_recovery", "exact_v2_equivalence", "shared_offline_step", "total_job_envelope", "normal_ci")
PROOFS = ("capacity", "runtime", "equivalence", "legacy_recovery", "normal_ci")
CI_CHECKS = {"semantic_gate", "pytest", "producer_fixture", "clean_tree"}
LEGACY_NODE = "tests/test_historical_package.py::test_real_age_legacy_v2_gzip_recovers_original_members_and_guard"
MAX_PUBLIC_BYTES = 16 * 1024 ** 2


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def is_sha(value, length=64):
    return isinstance(value, str) and re.fullmatch("[0-9a-f]{" + str(length) + "}", value) is not None


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def aggregate(statuses):
    values = list(statuses)
    return "PASS" if values and all(x == "PASS" for x in values) else "FAIL" if "FAIL" in values else "NOT RUN"


def verdict(facts, *, missing=False):
    return {"status": "NOT RUN" if missing else "PASS" if all(facts.values()) else "FAIL",
            "facts": facts, "failed_facts": sorted(k for k, v in facts.items() if not v)}


def timestamp(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result if result.tzinfo is not None else None
    except (TypeError, AttributeError, ValueError):
        return None


def unique_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite_json")))


class Reader:
    def __init__(self, root):
        self.root, self.references = root, {}

    def public(self, path, *, json_required=True):
        if not isinstance(path, str) or not path.startswith("docs/input-truthfulness/"):
            raise ValueError("public_receipt_path_required")
        if "\\" in path or ".." in PurePosixPath(path).parts or PurePosixPath(path).is_absolute():
            raise ValueError("unsafe_public_receipt_path")
        target = (self.root / path).resolve(strict=True)
        if not target.is_relative_to(self.root) or target.stat().st_size > MAX_PUBLIC_BYTES:
            raise ValueError("public_receipt_outside_scope_or_oversized")
        raw = target.read_bytes()
        self.references[path] = {"path": path, "sha256": digest(raw), "bytes": len(raw)}
        return unique_json(raw) if json_required else raw

    def optional(self, path):
        return self.public(path) if path else None

    def referenced(self, references):
        if not isinstance(references, list) or not references:
            return False
        for item in references:
            if not isinstance(item, dict) or set(item) != {"path", "sha256"} or not is_sha(item["sha256"]):
                return False
            if digest(self.public(item["path"], json_required=False)) != item["sha256"]:
                return False
        return True


def git(root, *args):
    return subprocess.run(["git", "-c", "safe.directory=" + str(root), *args], cwd=root,
                          capture_output=True, check=True).stdout


def runtime_paths(root):
    tree = ast.parse((root / "tools/historical_projection_benchmark.py").read_text(encoding="utf-8"))
    node = next(item.value for item in tree.body if isinstance(item, ast.Assign) and
                any(isinstance(t, ast.Name) and t.id == "SOURCE_FILES" for t in item.targets))
    for expected in ("tuple", "sorted"):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != expected or len(node.args) != 1:
            raise ValueError("source_inventory_contract_changed")
        node = node.args[0]
    result = ast.literal_eval(node)
    if not isinstance(result, tuple) or len(result) != len(set(result)) or not all(isinstance(p, str) for p in result):
        raise ValueError("source_inventory_contract_changed")
    return tuple(sorted(result))


def frozen_sources(root, contract):
    paths = runtime_paths(root)
    required = set(contract["required_source_paths"])
    if not required.issubset(paths):
        raise ValueError("benchmark_source_inventory_incomplete")
    hashes = {path: digest((root / path).read_bytes()) for path in paths}
    head = git(root, "rev-parse", "HEAD").decode().strip()
    tracked_equal = all(digest(git(root, "show", head + ":" + path)) == value for path, value in hashes.items())
    ancestor = subprocess.run(["git", "-c", "safe.directory=" + str(root), "merge-base", "--is-ancestor", BASE, head],
                              cwd=root, capture_output=True).returncode == 0
    changes = []
    scope_ok = True
    fields = git(root, "diff", "--name-status", "-z", "--no-renames", BASE, head).decode().split("\0")
    if fields[-1] != "" or (len(fields) - 1) % 2:
        raise ValueError("incomplete_git_difference")
    for status, path in zip(fields[0:-1:2], fields[1:-1:2]):
        if path in contract["permitted_changed_code"]:
            scope_ok &= status in {"A", "M"}
            if status in {"A", "M"}:
                changes.append({"path": path, "git_blob": git(root, "rev-parse", head + ":" + path).decode().strip()})
        else:
            support = path in {"README.md", "CLAUDE.md", ".env.example"} or path.startswith("tests/")
            docs = status in {"A", "M"} and (path in {"docs/input-truthfulness/2026-09-29-historical-execution.md", DECLARATION} or path.startswith(EVIDENCE))
            scope_ok &= support or docs
    return hashes, sorted(changes, key=lambda x: x["path"]), verdict({"required_source_coverage": required.issubset(paths),
        "source_bytes_equal_committed_head": tracked_equal, "continuation_base_is_ancestor": ancestor,
        "only_permitted_changes": scope_ok, "fewer_than_300_changed_paths": (len(fields) - 1) // 2 < 300})


def source_match(record, hashes):
    pins = record.get("source_sha256", {})
    return isinstance(pins, dict) and set(pins) == set(hashes) and pins == hashes


def case_checks(case, report, profile, inventory, baseline, baseline_raw_hash, sources, manifest, source_binding):
    names = ("capacity", "recovery", "equivalence", "offline", "recovered_offline", "envelope")
    if report is None:
        return {**{key: verdict({}, missing=True) for key in names}, "measurement_status": "NOT RUN"}
    if not all(isinstance(x, dict) for x in (report, profile, inventory, baseline)):
        return {**{key: verdict({"complete_report_profile_inventory": False}) for key in names}, "measurement_status": report.get("status", "NOT RUN")}
    common = {
        "representative_report_schema": report.get("schema") == "historical-delivery-runtime-benchmark-v2",
        "case_and_fixed_seed": report.get("case") == case and report.get("seed") == "spicystock-compaction-full-shape-v1",
        "synthetic_and_no_provider": report.get("synthetic_only") is True and type(report.get("provider_requests")) is int and report["provider_requests"] == 0,
        "no_historical_execution_or_owner_key": report.get("historical_workflow_execution") == "NOT RUN" and report.get("owner_key_access") == "NOT RUN" and report.get("release_authorized") is False,
        "full_shape_288_sessions": report.get("full_frozen_shape") is True and report.get("shape") == SHAPE,
        "frozen_manifest": report.get("manifest_sha256") == MANIFEST,
        "all_runtime_sources_equal_final_bytes": source_match(report, sources) and source_binding["status"] == "PASS",
        "source_stable_during_measurement": report.get("source_unchanged_through_run") is True,
        "representative_linux": report.get("representative_mode") is True and report.get("runtime_environment", {}).get("RUNNER_OS") == "Linux" and report.get("runtime_environment", {}).get("ImageOS") == "ubuntu24" and report.get("runtime_scope", "").startswith("GitHub Actions standard ubuntu-24.04 PR job;") and report.get("python", "").startswith("3.12.14 "),
        "hosted_pr_run_identity": report.get("runtime_environment", {}).get("GITHUB_EVENT_NAME") == "pull_request" and str(report.get("runtime_environment", {}).get("GITHUB_RUN_ATTEMPT")) == "1" and str(report.get("runtime_environment", {}).get("GITHUB_RUN_ID", "")).isdigit() and is_sha(report.get("checkout_sha"), 40),
        "original_caps_declared": report.get("limits_bytes") == CAPS,
    }
    pins = {}
    for line in manifest["requirements_text"].splitlines():
        if "==" in line and not line.startswith("#"):
            key, value = line.split("==")
            pins[key] = value
    common["historical_dependencies_pinned"] = report.get("dependencies") == pins
    valid_inventory = all(isinstance(k, str) and isinstance(v, dict) and set(v) == {"bytes", "sha256"} and integer(v["bytes"]) and is_sha(v["sha256"]) for k, v in inventory.items())
    common["inventory_shape"] = valid_inventory
    common["inventory_canonical_hash"] = digest(encoded(inventory)) == report.get("source_member_inventory_sha256")
    sizes = {k: v["bytes"] for k, v in inventory.items()} if valid_inventory else {}
    payload = sum(sizes.values())
    serialized = {"raw_pages": sum(v for k, v in sizes.items() if k.startswith("pages/")),
                  "query_manifests": sum(v for k, v in sizes.items() if k.endswith("-manifest.json")),
                  **{k: v for k, v in sizes.items() if not k.startswith("pages/") and not k.endswith("-manifest.json")}}
    common["member_component_sums"] = payload == report.get("source_member_payload_bytes") and serialized == report.get("serialized_member_bytes")
    old_names = {k for k in baseline if k.startswith("pages/") or k.endswith("-manifest.json") or k.startswith("reconciliation-")}
    new_names = {k for k in inventory if k.startswith("pages/") or k.endswith("-manifest.json") or k.startswith("reconciliation-")}
    old_match = old_names == new_names and len(old_names) == 388 and all(inventory[k] == baseline[k] for k in old_names)
    identity = report.get("pr96_output_identity", {})
    recon_names = {"reconciliation-" + day + ".json" for day in DATES}
    identity_ok = identity.get("status") == "PASS" and identity.get("expected_inventory_sha256") == baseline_raw_hash and identity.get("verified_member_count") == len(old_names) and identity.get("reconciliation") == {k: baseline[k] for k in sorted(recon_names)}
    reconciliations = report.get("reconciliation")
    recon_ok = isinstance(reconciliations, list) and len(reconciliations) == 2 and {r.get("session") for r in reconciliations} == set(DATES) and all(
        r.get("status") == "PASS" and r.get("complete_required_input_windows") is True and r.get("same_input_formula_status") == "PASS" and r.get("new_provider_requests") == 0 and r.get("manifest_sha256") == MANIFEST and r.get("output_sha256") == baseline["reconciliation-" + r["session"] + ".json"]["sha256"] for r in reconciliations)
    projection = report.get("projection_measurements", {})
    masks = projection.get("field_mask_counts", {})
    mask_ok = isinstance(masks, dict) and all(k in {str(i) for i in range(32)} and integer(v) for k, v in masks.items())
    mask_rows = sum(masks.values()) if mask_ok else -1
    conversions = sum(int(k).bit_count() * v for k, v in masks.items()) if mask_ok else -1
    projection_ok = projection.get("query_count") == 96 and projection.get("replayable_rows") == SHAPE["bulk_rows"] and mask_rows == SHAPE["bulk_rows"] and projection.get("conversion_count") == conversions and (case != "stress" or conversions == SHAPE["bulk_rows"] * 5)
    equivalent = verdict({**common, "all_388_raw_manifest_v2_members_match_pr96": old_match,
                          "reported_pr96_identity_matches_inventory": identity_ok, "both_v2_results_match_old_full_hashes": recon_ok,
                          "projection_rows_and_masks_complete": projection_ok})
    accounting = report.get("ledger_accounting", {})
    raw_bytes = serialized["raw_pages"]
    raw_ok = report.get("generated_rows") == 2753570 and report.get("synthetic_transport_calls") == 289 and raw_bytes == report.get("raw_response_bytes") and accounting == {
        "request_slots_charged": 289, "uncompressed_retained_bytes_charged": raw_bytes, "unresolved_byte_reservations": 0} and raw_bytes <= CAPS["raw"] and 289 <= manifest["limits"]["requests"] and all(value <= manifest["limits"]["page_bytes"] for key, value in sizes.items() if key.startswith("pages/"))
    package = report.get("package_measurements", {})
    required_sizes = ("archive_bytes", "expanded_payload_bytes", "ciphertext_bytes", "index_bytes", "tar_archive_bytes")
    has_sizes = all(integer(package.get(k), 1) for k in required_sizes)
    caps = {key: package.get(field) for key, field in (("archive", "archive_bytes"), ("expanded", "expanded_payload_bytes"), ("ciphertext", "ciphertext_bytes"))}
    capacity = verdict({**common, "raw_acquisition_request_and_byte_caps": raw_ok,
        "actual_complete_package_sizes": has_sizes,
        "all_delivery_caps": has_sizes and all(caps[k] <= CAPS[k] for k in caps),
        "complete_expanded_payload_includes_index": has_sizes and package["expanded_payload_bytes"] >= payload + package["index_bytes"],
        "tar_component_arithmetic": has_sizes and package["tar_archive_bytes"] - package["expanded_payload_bytes"] == package.get("tar_headers_and_padding_bytes"),
        "archive_and_ciphertext_hashes": is_sha(package.get("archive_sha256")) and is_sha(package.get("ciphertext_sha256")),
        "archive_format": package.get("archive_format") == "ustar-zstandard-v1"})
    reproduced = report.get("reproduced_offline", {})
    recovery = verdict({**common, "full_benchmark_pass": report.get("status") == "PASS", "full_original_member_count": len(inventory) == 390 and report.get("recovered_original_member_count") == len(inventory),
        "all_index_members_retained": report.get("recovered_index_member_count") == len(inventory) + 3 and package.get("indexed_member_count") == len(inventory) + 3,
        "every_original_member_byte_identical": report.get("all_original_members_byte_identical") is True,
        "accounting_unchanged": report.get("ledger_accounting_unchanged") is True,
        "both_offline_replays_exact": reproduced.get("status") == "PASS" and reproduced.get("both_dates_exact_bytes") is True and reproduced.get("reconciliation") == reconciliations and recon_ok,
        "test_identity_removed": report.get("disposable_test_identity_removed") is True})
    phases = report.get("phases_seconds", {})
    timing = report.get("timing_acceptance", {})
    profile_ok = profile.get("schema") == "historical-runtime-stage-profile-v1" and profile.get("active_stages") == []
    stages = profile.get("stages", {})
    def stage_ok(name, cap):
        row = stages.get(name, {})
        return row.get("calls") == 1 and row.get("completed") == 1 and row.get("failures") == 0 and number(row.get("wall_inclusive_seconds")) and row["wall_inclusive_seconds"] <= cap
    complete_initial = all(number(phases.get("reconcile_" + day)) for day in DATES) and recon_ok
    complete_recovered = all(number(phases.get("reproduce_" + day)) for day in DATES) and reproduced.get("status") == "PASS"
    initial = sum(phases.get("reconcile_" + day, 0) for day in DATES)
    recovered = sum(phases.get("reproduce_" + day, 0) for day in DATES)
    close = lambda a, b: number(a) and number(b) and abs(a - b) <= 0.00001
    offline = verdict({**common, "profile_complete": profile_ok, "initial_two_date_pass_complete": complete_initial,
        "initial_shared_offline_under_1800": complete_initial and initial <= 1800 and stage_ok("offline_initial", 1800),
        "reported_initial_sum_equals_phases": close(initial, timing.get("initial_shared_offline_seconds"))},
        missing=not any("reconcile_" + day in phases for day in DATES))
    recovered_offline = verdict({**common, "profile_complete": profile_ok,
        "recovered_two_date_pass_complete": complete_recovered,
        "recovered_shared_offline_under_1800": complete_recovered and recovered <= 1800 and stage_ok("offline_recovered", 1800),
        "reported_recovered_sum_equals_phases": close(recovered, timing.get("recovered_shared_offline_seconds"))},
        missing=not any("reproduce_" + day in phases for day in DATES))
    if "recover" not in phases:
        recovery["status"] = "NOT RUN"
        recovery["measurement_note"] = "Encryption/recovery was not reached; absent member checks are not completed failures."
    cap_measurements = {key: verdict({"within_unchanged_cap": integer(value, 1) and value <= CAPS[key]}, missing=not integer(value, 1))
                        for key, value in caps.items()}
    capacity["measurement_checks"] = cap_measurements
    if not has_sizes and all(common.values()) and raw_ok:
        capacity["status"] = "FAIL" if any(row["status"] == "FAIL" for row in cap_measurements.values()) else "NOT RUN"
        capacity["measurement_note"] = "Archive/expanded and ciphertext are separate. Missing measurements remain NOT RUN; an observed archive overflow remains FAIL."
    setup_seconds, package_seconds = timing.get("measured_setup_seconds"), phases.get("package")
    prospective = setup_seconds + 1800 + initial + package_seconds + 300 if number(setup_seconds) and number(package_seconds) else None
    envelope = verdict({**common, "offline_budgets_pass": offline["status"] == "PASS", "reported_timing_pass": timing.get("status") == "PASS",
        "original_limits_unchanged": timing.get("original_limits_seconds") == LIMITS,
        "package_under_600": number(package_seconds) and package_seconds <= 600 and stage_ok("package", 600),
        "prospective_total_under_4500": number(prospective) and prospective <= 4500,
        "prospective_sum_matches": close(prospective, timing.get("prospective_reserved_total_seconds")),
        "explicit_300_second_assumption": timing.get("delivery_overhead_reserve_seconds") == 300 and "ASSUMPTION" in timing.get("delivery_overhead_reserve_basis", ""),
        "reported_headroom_matches": number(prospective) and close(4500 - prospective, timing.get("remaining_total_seconds_after_overhead_reserve")),
        "actual_full_test_job_runtime_under_4500": number(report.get("runtime_seconds")) and number(setup_seconds) and report["runtime_seconds"] + setup_seconds <= 4500,
        "provider_delay_not_claimed_measured": timing.get("http_retry_and_provider_delay_measured") is False})
    package_complete = stage_ok("package", 600) and is_sha(package.get("ciphertext_sha256")) and integer(package.get("ciphertext_bytes"), 1)
    exceeded_known_time = (number(package_seconds) and package_seconds > 600) or (number(prospective) and prospective > 4500) or (complete_initial and initial > 1800)
    if not package_complete and not exceeded_known_time and all(common.values()):
        envelope["status"] = "NOT RUN"
        envelope["measurement_note"] = "Failed/incomplete packaging has no complete delivery time. Partial duration is not a passing prospective envelope."
    return dict(capacity=capacity, recovery=recovery, equivalence=equivalent, offline=offline, recovered_offline=recovered_offline, envelope=envelope,
        measurement_status=report.get("status"), stopped_at_phase=report.get("stopped_at_phase"), reason=report.get("reason"),
        package_margins_bytes={k: CAPS[k] - v if integer(v) else None for k, v in caps.items()},
        derived_seconds=dict(initial_shared_offline=initial, recovered_shared_offline=recovered if complete_recovered else None,
                             package=package_seconds, package_completed=package_complete,
                             prospective_with_assumed_overhead=prospective if package_complete else None,
                             partial_package_arithmetic_not_complete_envelope=prospective if not package_complete else None),
        limits_of_measurement="Public synthetic receipts only; sampled RSS/disk are lower bounds. HTTP/retries and provider quotas unmeasured. The 300-second overhead allowance is an assumption.")


def legacy_check(record, reader, sources):
    if record is None:
        return verdict({}, missing=True)
    required_sources = {p: sources[p] for p in ("tools/historical_package.py", "tools/historical_archive_codec.py")}
    checks = {"v2_receipt_and_index_unchanged", "all_original_members_exact", "legacy_execution_binding_preserved"}
    return verdict({"schema_and_pass": record.get("schema") == "historical-delivery-legacy-recovery-input-v1" and record.get("status") == "PASS",
        "actual_age_synthetic_only": record.get("synthetic_only") is True and record.get("actual_age") is True and record.get("provider_requests") == 0 and record.get("owner_key_access") == "NOT RUN",
        "final_codec_package_bytes": record.get("source_sha256") == required_sources,
        "existing_positive_test_executed": record.get("test_node") == LEGACY_NODE and type(record.get("exit_code")) is int and record["exit_code"] == 0 and type(record.get("passed")) is int and record["passed"] == 1 and type(record.get("skipped")) is int and record["skipped"] == 0,
        "all_required_preservation_checks": record.get("checks") == {key: "PASS" for key in checks},
        "dated_and_log_bound": timestamp(record.get("observed_at")) is not None and reader.referenced(record.get("observations"))})


def ci_check(record, reader, sources, policy):
    if record is None:
        return verdict({}, missing=True)
    facts = {"schema_and_pass": record.get("schema") == "historical-delivery-normal-ci-input-v1" and record.get("status") == "PASS",
        "repository_and_current_pr": record.get("repository") == REPOSITORY and record.get("implementation_pr") == policy["implementation_pr"],
        "source_pins_match_final_runtime": source_match(record, sources),
        "observation_dated": timestamp(record.get("observed_at")) is not None}
    head = record.get("head_sha")
    facts["head_shape"] = is_sha(head, 40)
    try:
        facts["verified_pr_head_source_equal"] = is_sha(head, 40) and all(digest(git(reader.root, "show", head + ":" + path)) == value for path, value in sources.items())
    except subprocess.CalledProcessError:
        facts["verified_pr_head_source_equal"] = False
    jobs = record.get("jobs", {})
    facts["exact_normal_jobs"] = isinstance(jobs, dict) and set(jobs) == {"pytest", "page", "secret_scan"}
    verified_checkouts = {}
    for name in ("pytest", "page", "secret_scan"):
        job = jobs.get(name, {}) if isinstance(jobs, dict) else {}
        run_id, job_id = job.get("run_id"), job.get("job_id")
        start, stop = timestamp(job.get("started_at")), timestamp(job.get("completed_at"))
        expected_workflow = ".github/workflows/secret-scan.yml" if name == "secret_scan" else ".github/workflows/tests.yml"
        facts[name + "_identity"] = integer(run_id, 1) and integer(job_id, 1) and type(job.get("run_attempt")) is int and job["run_attempt"] == 1 and job.get("head_sha") == head and job.get("workflow_path") == expected_workflow and job.get("event") == "pull_request" and job.get("url") == f"https://github.com/{REPOSITORY}/actions/runs/{run_id}/job/{job_id}"
        facts[name + "_completed_success"] = job.get("status") == "completed" and job.get("conclusion") == "success" and start is not None and stop is not None and stop >= start
        facts[name + "_raw_observations_hashed"] = reader.referenced(job.get("observations"))
        checkout = job.get("checkout_sha")
        if checkout not in verified_checkouts:
            try:
                verified_checkouts[checkout] = is_sha(checkout, 40) and all(digest(git(reader.root, "show", checkout + ":" + path)) == value for path, value in sources.items())
            except subprocess.CalledProcessError:
                verified_checkouts[checkout] = False
        facts[name + "_tested_checkout_source_equal"] = verified_checkouts[checkout]
        if name == "pytest":
            facts["all_pytest_substeps_pass"] = job.get("checks") == {key: "PASS" for key in CI_CHECKS}
    facts["unique_job_ids"] = len({jobs.get(n, {}).get("job_id") for n in ("pytest", "page", "secret_scan")}) == 3 if isinstance(jobs, dict) else False
    return verdict(facts)


def assemble(root, inputs):
    reader = Reader(root)
    contract = unique_json((root / "tools/historical-delivery-compatibility.json").read_bytes())
    policy = unique_json((root / "tools/historical-execution-policy.json").read_bytes())
    contract_hash = digest(encoded(contract))
    # Guard.encode is newline-terminated canonical JSON. Do not import runtime.
    if contract_hash != COMPATIBILITY or policy.get("schema") != "historical-execution-policy-v3" or policy.get("implementation_pr") != 97 or policy.get("compatibility_contract_sha256") != contract_hash or contract.get("continuation_base") != BASE or contract.get("manifest_sha256") != MANIFEST or contract.get("recipient_sha256") != RECIPIENT:
        raise ValueError("fixed_compatibility_or_policy_identity_changed")
    if inputs.get("schema") != "historical-delivery-assembly-input-v1" or set(inputs) != {"schema", "cases", "legacy_recovery", "normal_ci"} or set(inputs["cases"]) != {"central", "stress"}:
        raise ValueError("invalid_assembly_input_schema")
    sources, changed_code, binding = frozen_sources(root, contract)
    manifest = reader.public("docs/input-truthfulness/2026-09-28-historical-input-evidence/acquisition-manifest.json")
    if digest(encoded(manifest)) != MANIFEST:
        raise ValueError("frozen_manifest_changed")
    manifest["requirements_text"] = (root / "tools/requirements-historical.txt").read_text(encoding="utf-8")
    cases = {}
    for case in ("central", "stress"):
        paths = inputs["cases"][case]
        if not isinstance(paths, dict) or set(paths) != {"report", "profile", "inventory"}:
            raise ValueError("invalid_case_paths")
        report, profile, inventory = [reader.optional(paths[name]) for name in ("report", "profile", "inventory")]
        old_path = OLD + "benchmark-" + case + "-members.json"
        baseline = reader.public(old_path)
        cases[case] = case_checks(case, report, profile, inventory, baseline, reader.references[old_path]["sha256"], sources, manifest, binding)
    legacy = legacy_check(reader.optional(inputs["legacy_recovery"]), reader, sources)
    normal = ci_check(reader.optional(inputs["normal_ci"]), reader, sources, policy)
    checks = {case + "_capacity": cases[case]["capacity"]["status"] for case in cases}
    checks.update({case + "_exact_recovery": cases[case]["recovery"]["status"] for case in cases})
    checks.update(legacy_gzip_recovery=legacy["status"], normal_ci=normal["status"],
        exact_v2_equivalence=aggregate(c["equivalence"]["status"] for c in cases.values()),
        shared_offline_step=aggregate(c["offline"]["status"] for c in cases.values()),
        total_job_envelope=aggregate(c["envelope"]["status"] for c in cases.values()))
    common = {"schema": "historical-delivery-derived-proof-v1", "review_role": "implementation-side public synthetic evidence assembly; not Guidance acceptance or dated authorization",
        "compatibility_contract_sha256": contract_hash, "manifest_sha256": MANIFEST, "recipient_sha256": RECIPIENT,
        "assembler_sha256": digest(Path(__file__).read_bytes()), "source_sha256": sources, "source_binding": binding, "raw_evidence": [reader.references[p] for p in sorted(reader.references)],
        "provider_requests": 0, "owner_data_or_key_access": False, "release_authorized": False}
    proofs = {}
    for name, parts in (("capacity", ("capacity",)), ("runtime", ("offline", "recovered_offline", "envelope")), ("equivalence", ("equivalence", "recovery"))):
        records = {case: {key: cases[case][key] for key in parts} for case in cases}
        statuses = [value["status"] for record in records.values() for value in record.values()]
        proofs[name] = {**common, "proof": name, "status": aggregate([binding["status"], *statuses]), "cases": records,
                        "case_measurements": {case: {k: v for k, v in record.items() if k not in {"capacity", "recovery", "equivalence", "offline", "recovered_offline", "envelope"}} for case, record in cases.items()}}
    for name, result in (("legacy_recovery", legacy), ("normal_ci", normal)):
        proofs[name] = {**common, "proof": name, "status": aggregate([binding["status"], result["status"]]), "validation": result}
    proof_files = {EVIDENCE + "proof-" + name.replace("_", "-") + ".json": encoded(value) for name, value in proofs.items()}
    proof_links = {name: {"path": EVIDENCE + "proof-" + name.replace("_", "-") + ".json",
                          "sha256": digest(encoded(proofs[name]))} for name in PROOFS}
    ready = all(checks[key] == "PASS" for key in CHECKS) and all(value["status"] == "PASS" for value in proofs.values())
    declaration = {"schema": "historical-delivery-release-evidence-v1", "status": "PASS" if ready else "BLOCKED",
        "compatibility_contract_sha256": contract_hash, "manifest_sha256": MANIFEST, "recipient_sha256": RECIPIENT,
        "checks": {key: checks[key] for key in CHECKS}, "proofs": proof_links,
        "source_sha256": {p: sources[p] for p in contract["required_source_paths"]}, "changed_code": changed_code,
        "scope": "Declarative measured technical evidence only. No owner execution authorization, provider permission, private review acceptance or historical completion is asserted."}
    return declaration, {**proof_files, DECLARATION: encoded(declaration)}


def template():
    return {"schema": "historical-delivery-assembly-input-v1", "cases": {
        case: {name: None for name in ("report", "profile", "inventory")} for case in ("central", "stress")},
        "legacy_recovery": None, "normal_ci": None}


def receipt_contracts():
    return {"ci_schema": "historical-delivery-normal-ci-input-v1", "ci_required": {
        "status": "PASS", "repository": REPOSITORY, "implementation_pr": "actual current policy PR integer",
        "head_sha": "verified PR code-freeze SHA", "observed_at": "timezone-aware ISO timestamp", "source_sha256": "exact current benchmark SOURCE_FILES mapping",
        "jobs": {name: {"run_id": "positive integer", "run_attempt": 1, "job_id": "positive integer", "head_sha": "same code-freeze head", "checkout_sha": "actual job checkout, locally resolvable Git object",
            "workflow_path": ".github/workflows/secret-scan.yml" if name == "secret_scan" else ".github/workflows/tests.yml",
            "event": "pull_request", "status": "completed", "conclusion": "success", "started_at": "timezone-aware ISO", "completed_at": "timezone-aware ISO",
            "url": f"https://github.com/{REPOSITORY}/actions/runs/<run_id>/job/<job_id>", "observations": [{"path": "public retained API/job-log receipt", "sha256": "actual raw-byte SHA256"}],
            **({"checks": {key: "PASS" for key in sorted(CI_CHECKS)}} if name == "pytest" else {})} for name in ("pytest", "page", "secret_scan")}},
        "ci_scope": "Individual normal jobs only; the whole Tests run may fail from a separately assessed runtime case. No skipped runtime job becomes PASS.",
        "legacy_schema": "historical-delivery-legacy-recovery-input-v1", "legacy_required": {
            "status": "PASS", "synthetic_only": True, "actual_age": True, "provider_requests": 0, "owner_key_access": "NOT RUN",
            "source_sha256": "exact two-key final historical_package.py and historical_archive_codec.py hashes",
            "test_node": LEGACY_NODE, "exit_code": 0, "passed": 1, "skipped": 0, "observed_at": "timezone-aware ISO",
            "checks": {key: "PASS" for key in ("v2_receipt_and_index_unchanged", "all_original_members_exact", "legacy_execution_binding_preserved")},
            "observations": [{"path": "public retained focused-test log/receipt", "sha256": "actual raw-byte SHA256"}]}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--print-input-template", action="store_true")
    parser.add_argument("--print-receipt-contracts", action="store_true")
    args = parser.parse_args()
    if args.print_input_template or args.print_receipt_contracts:
        print(json.dumps(receipt_contracts() if args.print_receipt_contracts else template(), indent=2, sort_keys=True))
        return 0
    if not all((args.repo, args.inputs, args.output_dir)):
        parser.error("--repo, --inputs and --output-dir required")
    root, output = args.repo.resolve(strict=True), args.output_dir.resolve()
    if output.exists() or output.is_relative_to(root) or any((p / ".git").exists() for p in [output, *output.parents]):
        parser.error("output must be fresh and outside every Git checkout")
    try:
        declaration, files = assemble(root, unique_json(args.inputs.read_bytes()))
    except (OSError, ValueError, TypeError, KeyError, AttributeError, subprocess.CalledProcessError) as error:
        print(json.dumps({"status": "BLOCKED", "reason": "assembly_input_or_source_verification_failed", "error_type": type(error).__name__}))
        return 2
    output.mkdir(parents=True, exist_ok=False)
    for path, raw in files.items():
        # Flatten only the six fixed output names; links retain intended public paths.
        (output / PurePosixPath(path).name).write_bytes(raw)
    print(json.dumps({"status": declaration["status"], "checks": declaration["checks"], "declaration_sha256": digest(files[DECLARATION]),
                      "output_file_count": len(files), "operative_readiness": "NOT RUN"}, sort_keys=True))
    return 0 if declaration["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
