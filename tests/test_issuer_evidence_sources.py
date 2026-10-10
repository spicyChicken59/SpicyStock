"""Source controls and transport failures cannot masquerade as event clearance."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import html
import importlib.util
import json
from pathlib import Path

import pytest

from src import issuer_evidence as issuer


FIXTURES = Path(__file__).parent / "fixtures" / "issuer-evidence"
NOW = datetime(2026, 10, 10, 6, 20, tzinfo=timezone.utc)
ZIM_CIK = 1654126
ZIM_LATEST = "https://www.sec.gov/Archives/edgar/data/1654126/000117891326004724/zk2636204.htm"


def raw_json(value):
    return json.dumps(value, separators=(",", ":")).encode()


def zim_submissions():
    return json.loads((FIXTURES / "sources" / "zim-submissions.json").read_bytes())


def source(name):
    manifest = json.loads((FIXTURES / "manifest.json").read_bytes())
    entry = next(row for row in manifest["captures"] if row["file"].endswith(name))
    return entry, (FIXTURES / entry["file"]).read_bytes()


def test_saved_sources_match_the_original_response_receipts():
    manifest = json.loads((FIXTURES / "manifest.json").read_bytes())
    assert len(manifest["captures"]) == 5
    for row in manifest["captures"]:
        body = (FIXTURES / row["file"]).read_bytes()
        assert len(body) == row["bytes"]
        assert hashlib.sha256(body).hexdigest() == row["sha256"]
        assert row["fixture_kind"] == "captured_raw_response"
        assert row["url"].startswith(("https://www.sec.gov/Archives/", "https://data.sec.gov/submissions/"))


def test_mapping_uses_declared_column_order_and_cannot_merge_conflicting_tickers():
    mapping = {"fields": ["exchange", "ticker", "name", "cik"], "data": [
        ["NYSE", "ZIM", "ZIM Integrated Shipping Services Ltd.", ZIM_CIK],
        ["Nasdaq", "NVDA", "NVIDIA CORP", 1045810],
    ]}
    assert issuer.parse_mapping(raw_json(mapping), "ZIM")["cik"] == ZIM_CIK
    mapping["data"].append(["NYSE", "ZIM", "Different issuer", 1045810])
    with pytest.raises(issuer.SourceError) as error:
        issuer.parse_mapping(raw_json(mapping), "ZIM")
    assert error.value.code == "identity_unverified"


def test_mapping_does_not_guess_share_class_punctuation_aliases():
    mapping = {"fields": ["cik", "name", "ticker", "exchange"],
               "data": [[1067983, "Synthetic share-class mapping control", "BRK-B", "NYSE"]]}
    with pytest.raises(issuer.SourceError) as error:
        issuer.parse_mapping(raw_json(mapping), "BRK.B")
    assert error.value.code == "identity_unverified"


def test_zim_original_merger_is_seventeenth_current_report_not_in_latest_three():
    _, body = source("zim-submissions.json")
    parsed = issuer.parse_submissions(body, ZIM_CIK, "ZIM", NOW)
    reports = [f for f in parsed["filings"] if f["form"] in ("6-K", "6-K/A", "8-K", "8-K/A")]
    reports.sort(key=lambda f: (f["accepted_at"], f["accession"]), reverse=True)
    assert len(reports) == 33
    assert [r["filing_date"] for r in reports[:3]] == ["2026-10-06", "2026-09-30", "2026-08-19"]
    assert reports[16]["accession"] == "0001178913-26-000483"
    assert reports[16]["filing_date"] == "2026-02-17"
    assert reports[16]["items"] == ""
    assert parsed["history"] == []


def test_sec_acceptance_utc_is_preserved_separately_from_filing_and_event_dates():
    parsed = issuer.parse_submissions(source("zim-submissions.json")[1], ZIM_CIK, "ZIM", NOW)
    latest = next(f for f in parsed["filings"] if f["accession"] == "0001178913-26-004724")
    assert latest["filing_date"] == latest["report_date"] == "2026-10-06"
    assert datetime.fromisoformat(latest["accepted_at"].replace("Z", "+00:00")) == datetime(2026, 10, 7, 0, 10, 39, tzinfo=timezone.utc)


@pytest.mark.parametrize("changes", [
    {"cik": "0001045810"}, {"tickers": ["NVDA"]}, {"tickers": []}, {"tickers": ["ZI.M"]},
])
def test_submissions_identity_conflicts_do_not_become_matched_issuer(changes):
    data = zim_submissions()
    data.update(changes)
    with pytest.raises(issuer.SourceError) as error:
        issuer.parse_submissions(raw_json(data), ZIM_CIK, "ZIM", NOW)
    assert error.value.code == "identity_unverified"


def test_parallel_submissions_columns_cannot_silently_shift_filing_identity():
    data = zim_submissions()
    data["filings"]["recent"]["primaryDocument"].pop(0)
    with pytest.raises(issuer.SourceError) as error:
        issuer.parse_submissions(raw_json(data), ZIM_CIK, "ZIM", NOW)
    assert error.value.code == "metadata_invalid"


@pytest.mark.parametrize("accepted", ["2026-10-11T06:20:00Z", "2026-10-06T12:00:00", "not-a-time"])
def test_invalid_or_future_acceptance_is_not_relabelled_as_current(accepted):
    data = zim_submissions()
    data["filings"]["recent"]["acceptanceDateTime"][0] = accepted
    parsed = issuer.parse_submissions(raw_json(data), ZIM_CIK, "ZIM", NOW)
    assert parsed["invalid_count"] >= 1
    assert "0001178913-26-004724" not in {f["accession"] for f in parsed["filings"]}
    assert "0001178913-26-004656" in {f["accession"] for f in parsed["filings"]}


def test_empty_report_date_remains_unknown_while_filing_identity_survives():
    data = zim_submissions()
    data["filings"]["recent"]["reportDate"][0] = ""
    parsed = issuer.parse_submissions(raw_json(data), ZIM_CIK, "ZIM", NOW)
    latest = next(f for f in parsed["filings"] if f["accession"] == "0001178913-26-004724")
    assert latest["report_date"] is None
    assert latest["filing_date"] == "2026-10-06"


def test_filing_agent_prefix_is_not_the_issuer_cik_or_exhibit_directory():
    row, body = source("zim-2026-02-17-6k.html")
    parsed = issuer.parse_primary(body, row["url"])
    root = "https://www.sec.gov/Archives/edgar/data/1654126/000117891326000483/"
    assert parsed["links"] == [root + "exhibit_99-1.htm", root + "exhibit_99-2.htm"]
    assert all("/1178913/" not in url for url in parsed["links"])
    assert "35.00" in parsed["text"]


def test_zim_regulatory_setback_text_is_preserved_without_claiming_deal_termination():
    row, body = source("zim-2026-09-30-6k.html")
    parsed = issuer.parse_primary(body, row["url"])
    assert "cease handling the pending application" in parsed["text"]
    assert "intends to submit a revised proposal" in parsed["text"]
    assert parsed["links"] == []
    assert set(parsed) == {"text", "links", "rejected_links"}


def test_zim_newer_guidance_exhibit_still_preserves_pending_transaction_language():
    row, body = source("zim-2026-10-06-6k.html")
    parsed = issuer.parse_primary(body, row["url"])
    exhibit_row, exhibit = source("zim-2026-10-06-release.html")
    assert parsed["links"] == [exhibit_row["url"]]
    release = issuer.parse_primary(exhibit, exhibit_row["url"])
    assert "pending transaction with Hapag-Lloyd" in release["text"]


@pytest.mark.parametrize("filename,expected", [
    ("nvda-acquirer.txt", "purchase price payable to Hugging Face stockholders"),
    ("nvda-credit-support.txt", "OpenAI has agreed to reimburse and indemnify NVIDIA"),
])
def test_captured_acquirer_and_credit_support_passages_are_reading_not_target_classification(filename, expected):
    manifest = json.loads((FIXTURES / "excerpts" / "manifest.json").read_bytes())
    row = next(r for r in manifest["excerpts"] if r["file"] == filename)
    excerpt = (FIXTURES / "excerpts" / filename).read_bytes()
    assert hashlib.sha256(excerpt).hexdigest() == row["sha256"]
    assert row["source_sha256"] != row["sha256"]
    assert row["full_source_body_retained"] is False
    # This wrapper is a synthetic parser input around a captured text passage,
    # not the original SEC HTTP body whose digest the excerpt manifest records.
    wrapper = ("<html><body><p>" + html.escape(excerpt.decode()) + "</p></body></html>").encode()
    parsed = issuer.parse_primary(wrapper, row["url"])
    assert expected in parsed["text"]
    assert set(parsed) == {"text", "links", "rejected_links"}


@pytest.mark.parametrize("href", [
    "https://example.invalid/exhibit.htm", "https://www.sec.gov.evil.invalid/exhibit.htm",
    "https://www.sec.gov@evil.invalid/exhibit.htm", "javascript:alert(1)",
    "../000117891326004656/exhibit.htm", "%2e%2e/exhibit.htm",
    "exhibit.htm?next=https://example.invalid", "exhibit%2fsecret.htm",
    "https://www.sec.gov/Archives/edgar/data/1045810/000117891326004724/exhibit.htm",
])
def test_primary_cannot_expand_fetches_outside_verified_accession(href):
    body = ('<p>Actual issuer text</p><a href="' + html.escape(href, quote=True) + '">Exhibit 99.1</a>').encode()
    parsed = issuer.parse_primary(body, ZIM_LATEST)
    assert parsed["links"] == []
    assert "Actual issuer text" in parsed["text"]


def test_exhibit_deduplication_precedes_cap_and_keeps_literal_html_text_inert():
    body = b'''<html><head><style>private-style</style><script>private-script</script></head>
    <body><p>&lt;img src=x onerror=alert(1)&gt; &amp; issuer text</p>
    <a href="exhibit_99-1.htm">Exhibit 99.1</a><a href="exhibit_99-1.htm">Again</a>
    <a href="exhibit_99-2.htm">Exhibit 99.2</a><a href="#section">Section</a></body></html>'''
    parsed = issuer.parse_primary(body, ZIM_LATEST)
    assert "private-script" not in parsed["text"] and "private-style" not in parsed["text"]
    assert "<img src=x onerror=alert(1)> & issuer text" in parsed["text"]
    assert parsed["links"] == [ZIM_LATEST.replace("zk2636204.htm", "exhibit_99-1.htm"),
                               ZIM_LATEST.replace("zk2636204.htm", "exhibit_99-2.htm")]


@pytest.fixture(scope="module")
def producer():
    spec = importlib.util.spec_from_file_location("issuer_source_fixture_generator", FIXTURES / "generate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def canonical(producer):
    return producer.publication()


@pytest.fixture(scope="module")
def produced(producer, canonical):
    return producer.collect(canonical)


def test_producer_binds_original_ticket_and_archived_anchor_without_event_reclassification(canonical, produced):
    data = json.loads(canonical)
    assert not data.get("fixture")
    assert data["run"]["run_id"] == "synthetic-issuer-evidence"
    assert data["run"]["elapsed_seconds"] == data["run"]["fetch_seconds"] == 0.0
    original = next(row for row in data["watchlist"]["top"] if row["ticker"] == "ZIM")
    candidate = next(row for row in produced["bundle"]["candidates"] if row["ticker"] == "ZIM")
    assert candidate["admission"] == "known_event_excluded"
    assert candidate["anchors"] == original["plan"]["event_risk"]["matches"]
    assert [s["published_on"] for s in candidate["anchors"][0]["sources"]] == ["2026-02-16"]
    assert candidate["plan_sha256"] == original["plan"]["evidence_ref"]["plan_sha256"]
    assert produced["receipt"]["publication"]["data_sha256"] == hashlib.sha256(canonical).hexdigest()
    assert produced["receipt"]["coverage"]["issuer_news"]["status"] == "not_cleared"
    assert produced["receipt"]["coverage"]["earnings"]["status"] == "not_checked"
    row = next(row for row in produced["bundle"]["issuers"] if row["ticker"] == "ZIM")
    assert row["index"]["eligible_current_report_count"] == 33
    assert row["index"]["not_selected_count"] == 30
    assert "0001178913-26-000483" not in row["index"]["selected_accessions"]
    assert any("pending transaction with Hapag-Lloyd" in d["excerpt"]["text"] for d in row["documents"])
    issuer.validate_for_publication(canonical, produced["receipt_bytes"], produced["bundle_bytes"], allow_fixture=True)


def test_display_excerpt_sha_is_not_the_full_source_body_sha(produced):
    row = next(row for row in produced["bundle"]["issuers"] if row["ticker"] == "AAPL")
    assert row["identity"]["status"] == "verified"
    assert row["index"]["not_selected_count"] == 1
    primary = next(d for d in row["documents"] if d["role"] == "primary")
    text = primary["excerpt"]["text"]
    assert "<img src=x onerror=alert(1)>" in text
    assert "issuer-script-must-not-run" not in text
    assert primary["excerpt"]["sha256"] == hashlib.sha256(text.encode()).hexdigest()
    assert primary["source"]["raw_sha256"] != primary["excerpt"]["sha256"]
    assert primary["source"]["raw_sha256"] in produced["captures"]


@pytest.mark.parametrize("code", ["rate_limit", "http_error", "timeout", "network_error", "redirect_refused", "size_limit"])
def test_provider_failures_leave_source_unknown_and_reviewed_anchor_intact(producer, canonical, code):
    def fail(url):
        raise issuer.SourceError(code)

    result = producer.collect(canonical, fetch=fail)
    assert result["receipt"]["status"] == "unavailable"
    assert result["receipt"]["coverage"]["issuer_news"]["status"] == "not_cleared"
    for row in result["bundle"]["issuers"]:
        assert row["identity"]["status"] == "unverified"
        assert row["documents"] == []
        assert any(error["code"] == code for error in row["errors"])
    candidate = next(row for row in result["bundle"]["candidates"] if row["ticker"] == "ZIM")
    assert candidate["admission"] == "known_event_excluded" and candidate["anchors"]
    issuer.validate_for_publication(canonical, result["receipt_bytes"], result["bundle_bytes"], allow_fixture=True)


def test_oversized_fake_response_cannot_bypass_real_collection_body_limit(producer, canonical):
    def oversized(url):
        return {"body": b"x" * (2 * 1024 * 1024 + 1), "observed_at": NOW}

    result = producer.collect(canonical, fetch=oversized)
    assert result["receipt"]["status"] == "unavailable"
    assert all(not row["documents"] for row in result["bundle"]["issuers"])
    assert any(error["code"] == "size_limit" for row in result["bundle"]["issuers"] for error in row["errors"])


def test_wrong_submissions_cik_never_inherits_verified_mapping_or_source_documents(producer, canonical):
    result = producer.collect(canonical, "identity-unverified")
    row = next(row for row in result["bundle"]["issuers"] if row["ticker"] == "AAPL")
    assert row["status"] == "identity_unverified"
    assert row["identity"]["status"] == "unverified"
    assert row["documents"] == []
    assert any(error["code"] == "identity_unverified" for error in row["errors"])


def test_short_recent_index_does_not_assert_a_year_of_coverage(producer, canonical):
    data = producer.aapl_submissions()
    data["filings"]["recent"] = {key: values[:1] for key, values in data["filings"]["recent"].items()}
    fetch = producer.transport(edits={producer.AAPL_SUBMISSIONS: raw_json(data)})
    result = producer.collect(canonical, fetch=fetch)
    row = next(row for row in result["bundle"]["issuers"] if row["ticker"] == "AAPL")
    assert row["index"]["coverage_status"] == "partial"
    assert row["index"]["range_start"] == "2026-10-09"
    assert row["index"]["history_files_fetched"] == 0
    assert any(error["code"] == "history_incomplete" for error in row["errors"])


def test_short_index_follows_only_advertised_overlapping_archive(producer, canonical):
    data = producer.aapl_submissions()
    original = deepcopy(data["filings"]["recent"])
    data["filings"]["recent"] = {key: values[:1] for key, values in original.items()}
    data["filings"]["files"] = [
        {"name": "CIK0000320193-submissions-001.json", "filingCount": 4, "filingFrom": "2025-10-01", "filingTo": "2026-10-08"},
        {"name": "CIK0000320193-submissions-002.json", "filingCount": 1, "filingFrom": "2020-01-01", "filingTo": "2020-12-31"},
    ]
    archive_url = "https://data.sec.gov/submissions/CIK0000320193-submissions-001.json"
    historical = {key: values[1:] for key, values in original.items()}
    fetch = producer.transport(edits={producer.AAPL_SUBMISSIONS: raw_json(data), archive_url: raw_json(historical)})
    result = producer.collect(canonical, fetch=fetch)
    row = next(row for row in result["bundle"]["issuers"] if row["ticker"] == "AAPL")
    assert archive_url in fetch.calls
    assert not any("submissions-002" in url for url in fetch.calls)
    assert row["index"]["coverage_status"] == "observed_window"
    assert row["index"]["history_files_fetched"] == 1
    history_source, = row["index"]["history_sources"]
    assert history_source["url"] == archive_url
    assert history_source["raw_sha256"] == hashlib.sha256(raw_json(historical)).hexdigest()
    assert history_source["bytes"] == len(raw_json(historical))
    assert row["index"]["eligible_current_report_count"] == 4
    assert row["index"]["not_selected_count"] == 1


def test_conflicting_archive_accession_keeps_current_filing_and_marks_history_partial(producer, canonical):
    data = producer.aapl_submissions()
    original = deepcopy(data["filings"]["recent"])
    data["filings"]["recent"] = {key: values[:1] for key, values in original.items()}
    data["filings"]["files"] = [{"name": "CIK0000320193-submissions-001.json", "filingCount": 2,
                                  "filingFrom": "2025-10-01", "filingTo": "2026-10-09"}]
    historical = {key: [values[0], values[-1]] for key, values in original.items()}
    historical["primaryDocument"][0] = "conflicting-document.htm"
    archive_url = "https://data.sec.gov/submissions/CIK0000320193-submissions-001.json"
    fetch = producer.transport(edits={producer.AAPL_SUBMISSIONS: raw_json(data), archive_url: raw_json(historical)})
    result = producer.collect(canonical, fetch=fetch)
    row = next(row for row in result["bundle"]["issuers"] if row["ticker"] == "AAPL")
    assert row["index"]["coverage_status"] == "partial"
    assert row["index"]["range_start"] == "2026-10-09"
    assert any(error == {"code": "metadata_invalid", "source_url": archive_url} for error in row["errors"])
    assert not any("conflicting-document" in url for url in fetch.calls)
    assert any("synthetic-9001.htm" in doc["source"]["url"] for doc in row["documents"])


def test_source_response_after_start_is_valid_only_with_actual_completion_clock(producer, canonical):
    from datetime import timedelta
    base = producer.transport()

    def slow(url):
        return {**base(url), "observed_at": NOW + timedelta(seconds=7)}

    result = producer.collect(canonical, fetch=slow, finished_at=NOW + timedelta(seconds=10))
    row = next(row for row in result["bundle"]["issuers"] if row["ticker"] == "AAPL")
    assert row["identity"]["status"] == "verified" and row["documents"]
    assert result["bundle"]["as_of"] == result["receipt"]["collection_started_at"]
    assert datetime.fromisoformat(result["receipt"]["generated_at"].replace("Z", "+00:00")) == NOW + timedelta(seconds=10)
    expiry = datetime.fromisoformat(result["receipt"]["expires_at"].replace("Z", "+00:00"))
    assert expiry == NOW + timedelta(days=1, seconds=10)


def test_committed_browser_inputs_are_what_the_pipeline_and_collector_write(producer, canonical):
    from src import reader
    assert (FIXTURES / "publication.json").read_bytes() == canonical
    assert (FIXTURES / "reader.json").read_bytes() == reader.derive(canonical)[0]
    for variant in producer.VARIANTS:
        result = producer.collect(canonical, variant, dry_run=False)
        assert (FIXTURES / (variant + "-receipt.json")).read_bytes() == result["receipt_bytes"]
        assert (FIXTURES / (variant + "-bundle.json")).read_bytes() == result["bundle_bytes"]


def test_inapplicable_publication_uses_no_fetch_budget_and_keeps_original_anchor(producer, canonical):
    fetch = producer.transport()
    result = producer.collect(canonical, "inapplicable", fetch=fetch, dry_run=False)
    assert result["receipt"]["status"] == "inapplicable"
    assert result["receipt"]["selection"]["selected_tickers"] == []
    assert fetch.calls == []
    assert result["bundle"]["stats"]["request_count"] == 0
    assert result["bundle"]["issuers"] == []
    candidate = next(row for row in result["bundle"]["candidates"] if row["ticker"] == "ZIM")
    assert candidate["selected"] is False
    assert candidate["admission"] == "known_event_excluded"
    data = json.loads(canonical)
    original = next(row for row in data["watchlist"]["top"] if row["ticker"] == "ZIM")
    assert candidate["anchors"] == original["plan"]["event_risk"]["matches"]
    issuer.validate_for_publication(canonical, result["receipt_bytes"], result["bundle_bytes"])
