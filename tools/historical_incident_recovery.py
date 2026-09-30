"""One exact failed-job exception, never a reusable failure or budget reset.

The caller must collect complete unfiltered workflow history and authoritative
attempt-specific jobs and artifacts through a fail-closed GitHub collector.
This module has no network, provider, ledger, or readiness-approval capability.
It classifies only the captured native-5/attempt-1 incident; it cannot admit a
replacement by itself. Fresh review, readiness, and all execution guards remain
mandatory for the separately declared native-6/attempt-1 real phase.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

RECOVERY_PATH = Path(__file__).with_name("historical-native5-recovery.json")
RECOVERY_CONTRACT_SHA256 = "8f884be642bbcc01a0c02907d73c8d1075ac9040c1b9620e1a307d7330c25c71"
ORIGINAL_RECOVERY_PATH = Path(__file__).with_name("historical-workflow-recovery.json")
ORIGINAL_RECOVERY_CONTRACT_SHA256 = "6b49a4956c8196c432e9798149e2e1544b075a13353351cb10dfe241f72aae7a"
FAILED_RUN_ID = 36780349890
FAILED_JOB_ID = 110108745578
CONSUMED_READINESS_COMMENT_ID = 5920107119


class IncidentError(RuntimeError):
    """Only fixed reason codes, never untrusted API contents, enter logs."""


def require(condition, reason):
    if not condition:
        raise IncidentError(reason)


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def _parse(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate_incident_json_key")
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(IncidentError("invalid_incident_json")))
    except (ValueError, TypeError, UnicodeDecodeError):
        raise IncidentError("invalid_incident_json") from None


def _pinned_document(path, digest):
    try:
        raw = path.read_bytes()
    except OSError:
        raise IncidentError("missing_incident_contract") from None
    document = _parse(raw)
    require(isinstance(document, dict) and hashlib.sha256(encode(document)).hexdigest() == digest,
            "changed_incident_contract")
    return document


def incident_contract():
    """Load the new exact relation and preserve the original v1 contract."""
    _pinned_document(ORIGINAL_RECOVERY_PATH, ORIGINAL_RECOVERY_CONTRACT_SHA256)
    return _pinned_document(RECOVERY_PATH, RECOVERY_CONTRACT_SHA256)


def replacement_slot():
    """Return the explicitly reviewed prospective slot, never run-number math."""
    slot = incident_contract()["replacement"]
    return slot["run_number"], slot["assignment_phase"], slot["run_attempt"]


def _exact_projection(actual, expected, reason):
    """Permit unrelated API fields, but no missing/changed bound value or type."""
    require(type(actual) is type(expected), reason)
    if isinstance(expected, dict):
        require(set(expected).issubset(actual), reason)
        for key, value in expected.items():
            _exact_projection(actual[key], value, reason)
    elif isinstance(expected, list):
        require(len(actual) == len(expected), reason)
        for observed, fixed in zip(actual, expected):
            _exact_projection(observed, fixed, reason)
    else:
        require(actual == expected, reason)


def validate_incident(run, jobs, artifacts):
    """Classify native 5 only after positive authoritative collection reads.

    ``jobs`` and ``artifacts`` must be the complete lists returned by the guard's
    collector, not a first page, a cached default, or a substituted empty list
    after an API error. None/response envelopes are refused. The guard separately
    binds individual-run and collection responses and repeats the history read.
    All fifteen job steps are checked in order, including the skipped acquisition
    and upload. Empty artifacts alone never establish this classification.
    """
    contract = incident_contract()
    exception = contract["exception"]
    _exact_projection(run, exception["run"], "changed_native5_run")
    require(type(jobs) is list and len(jobs) == exception["jobs_total_count"], "changed_native5_jobs")
    _exact_projection(jobs[0], exception["job"], "changed_native5_job")
    require(type(artifacts) is list and len(artifacts) == exception["artifacts_total_count"],
            "changed_native5_artifacts")
    return {
        "schema": "historical-native5-classification-v1",
        "classification": contract["classification"],
        "run_id": FAILED_RUN_ID,
        "run_number": 5,
        "run_attempt": 1,
        "job_id": FAILED_JOB_ID,
        "recovery_contract_sha256": RECOVERY_CONTRACT_SHA256,
        "attempt_job_projection_sha256": hashlib.sha256(encode(exception["job"])).hexdigest(),
        "artifacts_total_count": 0,
        "provider_request_basis": "acquisition_step_skipped_before_checkout_no_ledger_created",
    }
