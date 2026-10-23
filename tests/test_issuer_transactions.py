"""Transaction form metadata warns without inferring a deal or clearing news."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

from src import issuer_evidence as issuer


FIXTURES = Path(__file__).parent / "fixtures" / "issuer-evidence"
EXPECTED_FORMS = {"PREM14A", "PREM14A/A", "DEFM14A", "DEFM14A/A",
                  "SC TO-T", "SC TO-T/A", "SC 14D9", "SC 14D9/A"}


@pytest.fixture(scope="module")
def producer():
    spec = importlib.util.spec_from_file_location("issuer_transaction_fixture_generator", FIXTURES / "generate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def canonical():
    return (FIXTURES / "publication.json").read_bytes()


def packet(name="observed"):
    return tuple(json.loads((FIXTURES / f"transaction-{name}-{kind}.json").read_bytes())
                 for kind in ("receipt", "bundle"))


def aapl(bundle):
    return next(row for row in bundle["issuers"] if row["ticker"] == "AAPL")


def warning(values):
    return aapl(values[1])["index"]["transaction_filings"]


def validate(values):
    receipt, bundle = values
    raw = issuer._encode(bundle)
    digest = issuer._sha(raw)
    receipt["bundle"] = {"sha256": digest, "bytes": len(raw), "path": f"issuer-evidence/{digest}.json"}
    return issuer.validate_bundle(issuer._encode(receipt), raw)


@pytest.mark.parametrize("variant,count,listed,coverage", [
    ("observed", 8, 8, "observed_window"), ("none", 0, 0, "observed_window"),
    ("partial", 8, 8, "partial"), ("unavailable", 0, 0, "unknown"),
    ("history", 8, 8, "observed_window"), ("capped", 15, 12, "observed_window"),
])
def test_saved_controls_are_actual_collector_outputs(producer, canonical, variant, count, listed, coverage):
    result = producer.collect_transactions(canonical, variant)
    for kind in ("receipt", "bundle"):
        assert result[kind + "_bytes"] == (FIXTURES / f"transaction-{variant}-{kind}.json").read_bytes()
    row = aapl(result["bundle"])
    observed = row["index"]["transaction_filings"]
    assert observed["observed_count"] == count
    assert len(observed["filings"]) == listed
    assert observed["not_listed_count"] == count - listed
    assert row["index"]["coverage_status"] == coverage
    assert result["receipt"]["coverage"]["issuer_news"]["status"] == "not_cleared"
    assert result["receipt"]["coverage"]["earnings"]["status"] == "not_checked"


def test_all_form_families_and_amendments_are_retained_beyond_current_reports():
    values = packet()
    index = aapl(values[1])["index"]
    observed = warning(values)
    assert {item["filing"]["form"] for item in observed["filings"]} == EXPECTED_FORMS
    assert index["eligible_current_report_count"] == 4
    assert len(index["selected_accessions"]) == 3
    assert all(item["filing"]["accession"] not in index["selected_accessions"] for item in observed["filings"])
    assert [item["filing"]["accession"] for item in observed["filings"]] == [
        f"0000320193-26-{number:06d}" for number in range(8007, 7999, -1)]


@pytest.mark.parametrize("variant", ["observed", "history"])
def test_each_observation_is_replayable_from_exact_retained_index_bytes(producer, canonical, variant):
    result = producer.collect_transactions(canonical, variant)
    row = aapl(result["bundle"])
    expected = row["index"]["history_sources"][0] if variant == "history" else row["identity"]["submissions_source"]
    for item in row["index"]["transaction_filings"]["filings"]:
        assert item["index_source"] == expected
        raw = result["captures"][expected["raw_sha256"]]
        assert issuer._sha(raw) == expected["raw_sha256"] and len(raw) == expected["bytes"]
        parsed = (issuer._parse_rows(json.loads(raw), producer.NOW) if variant == "history"
                  else issuer.parse_submissions(raw, 320193, "AAPL", producer.NOW))
        assert item["filing"] in parsed["filings"]


def test_observations_add_no_request_or_document_selection_and_preserve_exclusion(producer, canonical):
    none_fetch = producer.transport(edits=producer.transaction_responses("none"))
    observed_fetch = producer.transport(edits=producer.transaction_responses("observed"))
    none = producer.collect_transactions(canonical, "none", fetch=none_fetch)
    observed = producer.collect_transactions(canonical, "observed", fetch=observed_fetch)
    assert none_fetch.calls == observed_fetch.calls
    assert none["bundle"]["stats"]["request_count"] == observed["bundle"]["stats"]["request_count"]
    assert aapl(none["bundle"])["documents"] == aapl(observed["bundle"])["documents"]
    assert none["bundle"]["candidates"] == observed["bundle"]["candidates"]
    zim = next(row for row in observed["bundle"]["candidates"] if row["ticker"] == "ZIM")
    assert zim["admission"] == "known_event_excluded" and zim["anchors"]
    assert observed["receipt"]["policy"] == none["receipt"]["policy"]


@pytest.mark.parametrize("form", ["PRE 14A", "DEF 14A", "SC TO-I", "SC TO-I/A", "SC 13D", "SC 13D/A",
                                  "PREM14A/A/A", "SC TO-T/A ", "prem14a"])
def test_unlisted_forms_do_not_invent_transaction_observation(producer, canonical, form):
    edits = producer.transaction_responses("observed")
    data = json.loads(edits[producer.AAPL_SUBMISSIONS])
    data["filings"]["recent"]["form"][5:] = [form] * 8
    edits[producer.AAPL_SUBMISSIONS] = producer.json_bytes(data)
    result = producer.collect_transactions(canonical, "observed", fetch=producer.transport(edits=edits))
    observed = aapl(result["bundle"])["index"]["transaction_filings"]
    assert observed == {"schema_version": 1, "observed_count": 0, "not_listed_count": 0, "filings": []}


@pytest.mark.parametrize("field,value", [("filingDate", "2025-10-09"),
                                         ("filingDate", "2026-10-11"),
                                         ("acceptanceDateTime", "2026-10-11T16:00:00Z")])
def test_out_of_window_or_future_metadata_cannot_generate_warning(producer, canonical, field, value):
    edits = producer.transaction_responses("observed")
    data = json.loads(edits[producer.AAPL_SUBMISSIONS])
    data["filings"]["recent"][field][5:] = [value] * 8
    edits[producer.AAPL_SUBMISSIONS] = producer.json_bytes(data)
    result = producer.collect_transactions(canonical, "observed", fetch=producer.transport(edits=edits))
    assert aapl(result["bundle"])["index"]["transaction_filings"]["observed_count"] == 0


def test_duplicate_recent_and_history_observation_retains_recent_source(producer, canonical):
    edits = producer.transaction_responses("history")
    recent = json.loads(edits[producer.AAPL_SUBMISSIONS])
    history_url = "https://data.sec.gov/submissions/CIK0000320193-submissions-001.json"
    history = json.loads(edits[history_url])
    for key, values in recent["filings"]["recent"].items():
        values.append(history[key][-1])
    edits[producer.AAPL_SUBMISSIONS] = producer.json_bytes(recent)
    result = producer.collect_transactions(canonical, "history", fetch=producer.transport(edits=edits))
    row = aapl(result["bundle"])
    observed = row["index"]["transaction_filings"]
    assert observed["observed_count"] == 8
    assert observed["filings"][0]["index_source"] == row["identity"]["submissions_source"]
    assert all(item["index_source"] == row["index"]["history_sources"][0] for item in observed["filings"][1:])


def test_failed_history_cannot_supply_warning_or_claim_full_index(producer, canonical):
    edits = producer.transaction_responses("history")
    history_url = "https://data.sec.gov/submissions/CIK0000320193-submissions-001.json"
    edits[history_url] = issuer.SourceError("http_error", http_status=403)
    result = producer.collect_transactions(canonical, "history", fetch=producer.transport(edits=edits))
    index = aapl(result["bundle"])["index"]
    assert index["transaction_filings"]["observed_count"] == 0
    assert index["coverage_status"] == "partial" and index["history_sources"] == []


def test_legacy_receipt_without_optional_extension_remains_readable():
    values = packet()
    for row in values[1]["issuers"]:
        row["index"].pop("transaction_filings")
    checked = validate(values)
    assert all("transaction_filings" not in row["index"] for row in checked["issuers"])


@pytest.mark.parametrize("field,value", [("schema_version", True), ("schema_version", 2),
    ("observed_count", True), ("observed_count", -1), ("observed_count", 9),
    ("not_listed_count", 1), ("not_listed_count", True), ("filings", None), ("pending", True)])
def test_extension_shape_and_count_corruption_is_rejected_after_reseal(field, value):
    values = packet()
    warning(values)[field] = value
    with pytest.raises((ValueError, TypeError, KeyError)):
        validate(values)


@pytest.mark.parametrize("mutation", ["unsupported_form", "outside_window", "future_acceptance", "duplicate", "order",
    "wrong_issuer", "wrong_digest", "wrong_size", "wrong_clock", "mapping_source", "current_report_accession"])
def test_filing_or_source_corruption_is_rejected_after_reseal(mutation):
    values = packet()
    observed = warning(values)
    item = observed["filings"][0]
    if mutation == "unsupported_form": item["filing"]["form"] = "SC TO-I"
    elif mutation == "outside_window": item["filing"]["filing_date"] = "2025-10-09"
    elif mutation == "future_acceptance": item["filing"]["accepted_at"] = "2026-10-11T16:00:00+00:00"
    elif mutation == "duplicate": observed["filings"][1] = deepcopy(item)
    elif mutation == "order": observed["filings"].reverse()
    elif mutation == "wrong_issuer": item["index_source"]["url"] = "https://data.sec.gov/submissions/CIK0001045810.json"
    elif mutation == "wrong_digest": item["index_source"]["raw_sha256"] = "a" * 64
    elif mutation == "wrong_size": item["index_source"]["bytes"] += 1
    elif mutation == "wrong_clock": item["index_source"]["fetched_at"] = item["index_source"]["checked_at"] = "2026-10-10T06:19:59+00:00"
    elif mutation == "mapping_source": item["index_source"] = deepcopy(aapl(values[1])["identity"]["mapping_source"])
    elif mutation == "current_report_accession": item["filing"]["accession"] = aapl(values[1])["index"]["selected_accessions"][0]
    with pytest.raises((ValueError, TypeError, KeyError)):
        validate(values)


def test_capped_list_cannot_silently_discard_an_observation():
    values = packet("capped")
    warning(values)["filings"].pop()
    warning(values)["not_listed_count"] += 1
    with pytest.raises(ValueError, match="transaction filing counts"):
        validate(values)


def test_count_cannot_exceed_noncurrent_metadata_even_when_list_remains_capped():
    values = packet("capped")
    warning(values)["observed_count"] += 1
    warning(values)["not_listed_count"] += 1
    with pytest.raises(ValueError, match="transaction filing counts"):
        validate(values)


def test_partial_metadata_does_not_erase_positive_observations():
    values = packet("partial")
    assert aapl(validate(values))["index"]["transaction_filings"]["observed_count"] == 8


def test_captured_zim_sources_remain_unchanged_and_zero_forms_do_not_end_exclusion():
    values = packet()
    zim = next(row for row in values[1]["issuers"] if row["ticker"] == "ZIM")
    assert zim["index"]["transaction_filings"]["observed_count"] == 0
    candidate = next(row for row in values[1]["candidates"] if row["ticker"] == "ZIM")
    assert candidate["admission"] == "known_event_excluded" and candidate["anchors"]
    manifest = json.loads((FIXTURES / "manifest.json").read_bytes())
    for entry in manifest["captures"]:
        body = (FIXTURES / entry["file"]).read_bytes()
        assert issuer._sha(body) == entry["sha256"] and len(body) == entry["bytes"]
