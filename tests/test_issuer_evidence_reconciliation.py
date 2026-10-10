"""Coherently resealed evidence cannot promote trust or hide visible work."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from src import issuer_evidence as issuer

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures" / "issuer-evidence"


def packet(name="semantic-complete"):
    return tuple(json.loads((FIXTURES / f"{name}-{kind}.json").read_bytes()) for kind in ("receipt", "bundle"))


def validate(values):
    receipt, bundle = values
    raw = issuer._encode(bundle)
    sha = hashlib.sha256(raw).hexdigest()
    receipt["bundle"] = {"sha256": sha, "bytes": len(raw), "path": f"issuer-evidence/{sha}.json"}
    return issuer.validate_bundle(issuer._encode(receipt), raw)


def set_aggregate(receipt, bundle):
    rows = bundle["issuers"]
    receipt["status"] = ("unavailable" if all(row["status"] in ("unavailable", "identity_unverified") for row in rows)
                         else "partial" if any(row["status"] != "collected" for row in rows) else "collected")


@pytest.mark.parametrize("name,status,coverage,requests", [
    ("complete", "collected", "observed_window", 5),
    ("empty-window", "collected", "observed_window", 3),
    ("cached", "collected", "observed_window", 2),
    ("cache-unverified", "unavailable", "unknown", 0),
    ("document-denied", "partial", "observed_window", 5),
    ("metadata-invalid", "partial", "partial", 5),
    ("short-index", "partial", "partial", 5),
    ("prefetch-budget", "unavailable", "unknown", 0),
])
def test_genuine_producer_states_reconcile(name, status, coverage, requests):
    receipt, bundle = packet("semantic-" + name)
    assert receipt["dry_run"] is False
    assert receipt["status"] == status
    assert {row["index"]["coverage_status"] for row in bundle["issuers"]} == {coverage}
    assert bundle["stats"]["request_count"] == requests
    issuer.validate_for_publication((FIXTURES / "publication.json").read_bytes(),
                                    (FIXTURES / f"semantic-{name}-receipt.json").read_bytes(),
                                    (FIXTURES / f"semantic-{name}-bundle.json").read_bytes(), allow_fixture=True)
    if name in ("cache-unverified", "prefetch-budget"):
        assert bundle["stats"]["downloaded_bytes"] == 0
        assert (bundle["stats"]["capture_bytes"] > 0) == (name == "cache-unverified")
    if name == "empty-window":
        assert all(not row["documents"] and not row["index"]["selected_accessions"] for row in bundle["issuers"])
    if name == "document-denied":
        assert all(row["errors"][0]["http_status"] == 403 for row in bundle["issuers"])


def test_all_existing_and_new_fixtures_pass_stdlib_validator():
    code = (f"import sys;sys.path.insert(0,{str(ROOT)!r});from pathlib import Path;"
            "from src.issuer_evidence import validate_bundle;"
            f"p=Path({str(FIXTURES)!r});"
            "[validate_bundle(r.read_bytes(),r.with_name(r.name.replace('-receipt','-bundle')).read_bytes()) "
            "for r in p.glob('*-receipt.json')];print('PASS')")
    result = subprocess.run([sys.executable, "-I", "-S", "-c", code], capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr.decode()
    assert result.stdout == b"PASS\n"


def test_generator_reproduces_additive_controls_without_rewriting_originals():
    spec = importlib.util.spec_from_file_location("issuer_reconciliation_generator", FIXTURES / "generate.py")
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    outputs = generator.build()
    assert len(outputs) == 30
    assert all((FIXTURES / name).read_bytes() == raw for name, raw in outputs.items())


def test_unverified_identity_cannot_claim_observed_window():
    values = packet("semantic-cache-unverified")
    values[1]["issuers"][0]["index"].update(coverage_status="observed_window", reason=None)
    with pytest.raises(ValueError, match="unverified index"):
        validate(values)


def test_unverified_identity_cannot_claim_collected_even_with_matching_aggregate():
    values = packet("semantic-cache-unverified")
    for row in values[1]["issuers"]:
        row.update(status="collected", reason=None)
    values[0]["status"] = "collected"
    with pytest.raises(ValueError, match="unverified row"):
        validate(values)


def test_unverified_index_cannot_hide_nonzero_metadata_under_unknown_label():
    values = packet("semantic-cache-unverified")
    values[1]["issuers"][0]["index"]["metadata_count"] = 1
    with pytest.raises(ValueError, match="unverified index"):
        validate(values)


@pytest.mark.parametrize("name", ["short-index", "metadata-invalid"])
def test_verified_index_requires_range_and_index_stage_success(name):
    values = packet("semantic-" + name)
    values[1]["issuers"][0]["index"].update(coverage_status="observed_window", reason=None)
    with pytest.raises(ValueError, match="index label"):
        validate(values)


@pytest.mark.parametrize("location", ["mapping", "submissions", "history"])
def test_legacy_index_errors_preclude_full_window_label(location):
    values = packet()
    row = values[1]["issuers"][0]
    prefix = f'https://data.sec.gov/submissions/CIK{row["identity"]["cik"]:010d}'
    url = {"mapping": issuer.MAPPING_URL, "submissions": prefix + ".json",
           "history": prefix + "-submissions-001.json"}[location]
    row["errors"].append({"code": "http_error", "source_url": url})
    row["status"] = "partial"
    set_aggregate(*values)
    with pytest.raises(ValueError, match="index label"):
        validate(values)
    row["index"]["coverage_status"] = "partial"
    validate(values)


def test_late_legacy_document_failure_does_not_reclassify_index():
    values = packet("semantic-document-denied")
    for row in values[1]["issuers"]:
        for error in row["errors"]:
            error.pop("http_status")
            error.pop("source_phase")
    validate(values)
    values[1]["issuers"][0]["index"]["coverage_status"] = "partial"
    with pytest.raises(ValueError, match="index label"):
        validate(values)


def test_collected_requires_selected_primary_even_when_every_hash_matches():
    values = packet()
    values[1]["issuers"][0]["documents"] = []
    with pytest.raises(ValueError, match="row label"):
        validate(values)
    # Narrowing is allowed without inventing an HTTP response for absent text.
    values[1]["issuers"][0]["status"] = "partial"
    set_aggregate(*values)
    validate(values)


@pytest.mark.parametrize("name", ["document-denied", "metadata-invalid"])
def test_partial_evidence_cannot_be_relabelled_collected(name):
    values = packet("semantic-" + name)
    for row in values[1]["issuers"]:
        row.update(status="collected", reason=None)
    values[0]["status"] = "collected"
    with pytest.raises(ValueError, match="row label"):
        validate(values)


def test_listed_metadata_count_cannot_omit_an_unselected_report():
    values = packet("collected")
    index = values[1]["issuers"][0]["index"]
    assert len(index["listed_filings"]) == 4
    index["listed_filings"].pop()
    with pytest.raises(ValueError, match="listed metadata count"):
        validate(values)


@pytest.mark.parametrize("field,message", [("request_count", "request count"),
                                          ("downloaded_bytes", "downloaded bytes"),
                                          ("capture_bytes", "capture bytes")])
def test_visible_network_sources_set_budget_lower_bounds(field, message):
    values = packet()
    values[1]["stats"][field] = 0
    with pytest.raises(ValueError, match=message):
        validate(values)


def test_explicit_http_failure_is_one_attempt_despite_repeated_issuer_rows():
    values = packet("http-denied")
    assert len(values[1]["issuers"]) == 2 and values[1]["stats"]["request_count"] == 1
    validate(values)
    values[1]["stats"]["request_count"] = 0
    with pytest.raises(ValueError, match="request count"):
        validate(values)


def test_legacy_unknown_status_error_does_not_invent_a_request():
    values = packet("outage")
    values[1]["stats"]["request_count"] = 0
    validate(values)


def test_visible_successes_and_explicit_http_failures_add_lower_bounds():
    values = packet("semantic-document-denied")
    values[1]["stats"]["request_count"] = 4
    with pytest.raises(ValueError, match="request count"):
        validate(values)


def test_cache_adds_capture_but_no_network_lower_bound():
    values = packet("semantic-cached")
    bundle = validate(values)
    assert bundle["stats"]["request_count"] == 2
    assert all(row["identity"]["mapping_source"]["cache_status"] == "verified_cache" for row in bundle["issuers"])
    assert bundle["stats"]["capture_bytes"] > bundle["stats"]["downloaded_bytes"]


def test_shared_source_event_dedup_normalizes_equivalent_time_offsets():
    values = packet()
    source = values[1]["issuers"][1]["identity"]["mapping_source"]
    source["fetched_at"] = source["checked_at"] = "2026-10-10T02:20:00-04:00"
    validate(values)


def test_distinct_microsecond_source_events_are_not_collapsed():
    values = packet()
    source = values[1]["issuers"][1]["identity"]["mapping_source"]
    source["fetched_at"] = source["checked_at"] = "2026-10-10T06:20:00.000001+00:00"
    with pytest.raises(ValueError, match="request count"):
        validate(values)
    values[1]["stats"]["request_count"] += 1
    values[1]["stats"]["downloaded_bytes"] += source["bytes"]
    validate(values)


def test_identical_bodies_at_different_urls_are_two_downloads_one_capture():
    values = packet()
    bundle = validate(values)
    docs = [row["documents"][0]["source"] for row in bundle["issuers"]]
    assert docs[0]["raw_sha256"] == docs[1]["raw_sha256"] and docs[0]["url"] != docs[1]["url"]
    values[1]["stats"]["downloaded_bytes"] -= docs[0]["bytes"]
    with pytest.raises(ValueError, match="downloaded bytes"):
        validate(values)


def test_one_digest_cannot_claim_two_body_sizes():
    values = packet()
    values[1]["issuers"][1]["documents"][0]["source"]["bytes"] += 1
    # Keep independent floors satisfied so only the conflicting digest rejects.
    values[1]["stats"]["downloaded_bytes"] += 1
    values[1]["stats"]["capture_bytes"] += 1
    with pytest.raises(ValueError, match="conflicting byte sizes"):
        validate(values)


def test_unseen_work_can_increase_counters_without_false_exact_accounting():
    values = packet()
    for key in ("request_count", "downloaded_bytes", "capture_bytes"):
        values[1]["stats"][key] += 1
    validate(values)


def test_positive_download_requires_request_even_without_visible_sources():
    values = packet("outage")
    values[1]["stats"].update(request_count=0, downloaded_bytes=1)
    with pytest.raises(ValueError, match="download requires"):
        validate(values)


def test_aggregate_status_must_match_valid_row_states():
    values = packet("semantic-document-denied")
    values[0]["status"] = "collected"
    with pytest.raises(ValueError, match="aggregate status"):
        validate(values)
