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


# SEC lists an XML filing under the directory of the XSL stylesheet that renders
# it. Until 25 October 2026 the row rule refused every such row, so nearly every
# issuer's index read partial on metadata_invalid: 78 of the 240 rows of ZIM's
# index captured on 10 October, and on the runner on 25 October (run
# 40163306777) the same 78 for ZIM and 674 for AAPL.
RENDERED_FORMS = {"3", "4", "144", "EFFECT", "SCHEDULE 13D", "SCHEDULE 13D/A", "SCHEDULE 13G", "SCHEDULE 13G/A"}


def test_the_captured_zim_index_is_read_whole_including_its_rendered_xml_filings():
    entry, raw = source("zim-submissions.json")
    recent = json.loads(raw)["filings"]["recent"]
    rendered = [(form, doc) for form, doc in zip(recent["form"], recent["primaryDocument"]) if "/" in doc]
    assert len(recent["form"]) == 240 and len(rendered) == 78
    assert {form for form, _ in rendered} == RENDERED_FORMS
    assert {doc.split("/")[0] for _, doc in rendered} == {
        "xsl144X01", "xslEFFECTX01", "xslF345X02", "xslF345X06", "xslSCHEDULE_13D_X01", "xslSCHEDULE_13G_X01"}
    parsed = issuer.parse_submissions(raw, ZIM_CIK, "ZIM", NOW)
    assert parsed["invalid_count"] == 0
    # The window now holds the ownership and 144 rows beside the reports it held before.
    forms = [f["form"] for f in parsed["filings"]]
    assert len(forms) == 99 and sum(form in issuer.FORMS for form in forms) == 33 and forms.count("20-F") == 1
    # The rendered rows in the window keep SEC's path, and every one is a form never stored.
    kept = [f for f in parsed["filings"] if "/" in f["primary_document"]]
    assert len(kept) == 99 - 34 and {f["form"] for f in kept} <= RENDERED_FORMS
    assert all(f["primary_document"].startswith("xsl") for f in kept)


@pytest.mark.parametrize("form, document, name", [
    ("4", "xslF345X06/form4.xml", "form4.xml"),
    ("144", "xsl144X01/primary_doc.xml", "primary_doc.xml"),
    ("SCHEDULE 13D/A", "xslSCHEDULE_13D_X01/primary_doc.xml", "primary_doc.xml"),
    ("25-NSE", "xslF25X02/primary_doc.xml", "primary_doc.xml"),
    ("EFFECT", "xslEFFECTX01/primary_doc.xml", "primary_doc.xml"),
    ("4", "xsl" + "A" * 64 + "/f.xml", "f.xml"),
])
def test_a_rendered_row_of_a_form_never_stored_is_read_by_its_documents_own_name(form, document, name):
    assert issuer._rendered(form, document) == name


@pytest.mark.parametrize("form, document", [
    # A current report or an acquisition form is listed, linked and fetched by its document.
    *[(form, "xslF345X06/form4.xml") for form in sorted(issuer.FORMS | issuer.ACQUISITION_FORMS)],
    ("4", "form4.xml"),                      # no directory: the plain rule reads it
    ("4", "xslF345X06/"), ("4", "xsl/form4.xml"), ("4", "XSLF345X06/form4.xml"), ("4", "notxsl/form4.xml"),
    ("4", "xslF345X06/a/form4.xml"), ("4", "xslF345X06/../form4.xml"), ("4", "xslF345X06/..form4.xml"),
    ("4", "xslF345X06/.form4.xml"), ("4", "xsl" + "A" * 65 + "/f.xml"), ("4", "xslF345X06/form4.xml\n"),
    ("4", "xslF-345/form4.xml"), ("4", "/xslF345X06/form4.xml"), ("4", None), (None, "xslF345X06/form4.xml"),
    (["4"], "xslF345X06/form4.xml"),
])
def test_no_other_row_is_read_under_a_rendering_directory(form, document):
    assert issuer._rendered(form, document) is None


def _index(rows):
    keys = ("accessionNumber", "filingDate", "reportDate", "acceptanceDateTime", "form", "items", "primaryDocument")
    return {key: [row[key] for row in rows] for key in keys}


def _row(n, form, document, day="2026-10-05"):
    return {"accessionNumber": f"0001654126-26-{n:06d}", "filingDate": day, "reportDate": day,
            "acceptanceDateTime": f"{day}T16:00:00Z", "form": form, "items": "", "primaryDocument": document}


def test_a_rendered_row_is_held_to_every_other_row_rule():
    good = _row(1, "4", "xslF345X06/form4.xml")
    bad = [dict(good, accessionNumber="bad"), dict(good, filingDate="2026-10-5"), dict(good, items=None),
           dict(good, acceptanceDateTime="2026-10-11T06:20:00Z"), dict(good, form="")]
    parsed = issuer._parse_rows(_index([good] + bad), NOW)
    assert parsed["invalid_count"] == len(bad) and [f["accession"] for f in parsed["filings"]] == [good["accessionNumber"]]
    # The row keeps SEC's path; only the check reads the document's own name.
    assert parsed["filings"][0]["primary_document"] == "xslF345X06/form4.xml"


def test_a_current_report_under_a_rendering_directory_is_still_refused_and_never_fetched(producer, canonical):
    data = zim_submissions()
    recent = data["filings"]["recent"]
    first = recent["form"].index("6-K")
    recent["primaryDocument"][first] = "xslF345X06/" + recent["primaryDocument"][first]
    fetch = producer.transport(edits={"https://data.sec.gov/submissions/CIK0001654126.json": raw_json(data)})
    result = producer.collect(canonical, fetch=fetch)
    row = next(row for row in result["bundle"]["issuers"] if row["ticker"] == "ZIM")
    assert {"code": "metadata_invalid", "source_url": "https://data.sec.gov/submissions/CIK0001654126.json"} in row["errors"]
    assert row["index"]["coverage_status"] == "partial"
    assert not any("xsl" in url for url in fetch.calls)
    assert "xsl" not in json.dumps(result["bundle"])
    issuer.validate_bundle(result["receipt_bytes"], result["bundle_bytes"])


def test_the_captured_zim_index_now_gives_an_observed_window_with_its_ownership_rows_counted(producer, canonical):
    fetch = producer.transport()
    result = producer.collect(canonical, fetch=fetch)
    row = next(row for row in result["bundle"]["issuers"] if row["ticker"] == "ZIM")
    index = row["index"]
    assert index["coverage_status"] == "observed_window" and index["reason"] is None
    assert index["metadata_count"] == 99 and index["eligible_current_report_count"] == 33
    assert all(error["code"] != "metadata_invalid" for error in row["errors"])
    # A rendered row is counted, never listed, linked or fetched.
    assert "xsl" not in json.dumps(result["bundle"]) and not any("xsl" in url for url in fetch.calls)
    issuer.validate_bundle(result["receipt_bytes"], result["bundle_bytes"])


# SEC also lists some filings with no primary document, or with a name that
# carries a doubled dot. Every such row the probe named on 31 October
# 2026 (run 41149821846) was a Schedule 13G or 13G/A: one of MCS's and six of
# QGEN's. QGEN's index was the one its 30 October collection read, partial on
# metadata_invalid though it reached past its window; MCS's had changed since
# its 29 October collection, so for MCS that cause is inferred.
UNNAMED_ROWS = [("SC 13G/A", "marcus.corp..txt"), ("SC 13G/A", "qiagen.n.v..txt"),
                ("SC 13G/A", "qiagen.nv.reg.shs..txt"), ("SC 13G", "qiagen.nv.reg.shs..txt"),
                ("SC 13G/A", ""), ("SC 13G", "")]
PLAIN_REQUIRED = sorted(issuer.FORMS | issuer.ACQUISITION_FORMS)


@pytest.mark.parametrize("form, document", [
    *UNNAMED_ROWS, ("10-K", ""), ("4", "x.."), ("SCHEDULE 13G/A", ""),
    ("SC 13G/A", "x" * 198 + ".."),          # the basename rule's 200-character bound
])
def test_an_unnamed_row_of_a_form_never_stored_is_counted(form, document):
    assert issuer._unnamed(form, document) is True
    assert not issuer._basename(document) and issuer._rendered(form, document) is None


@pytest.mark.parametrize("form, document", [
    # A current report or an acquisition form is listed, linked and fetched by its document.
    *[(form, document) for form in PLAIN_REQUIRED for document in ("", "x..htm")],
    ("SC 13G/A", "marcus.corp.txt"),         # a plain name: the plain rule reads it
    ("SC 13G/A", ".."), ("SC 13G/A", "."), ("SC 13G/A", "..txt"), ("SC 13G/A", ".x..txt"),
    ("SC 13G/A", "a/b..txt"), ("SC 13G/A", "a/.."), ("SC 13G/A", "../x"), ("SC 13G/A", "xsl/.."),
    ("SC 13G/A", "%2e%2e"), ("SC 13G/A", "a\\..\\b.txt"), ("SC 13G/A", "x..\n"), ("SC 13G/A", " "),
    ("SC 13G/A", "a b..txt"), ("SC 13G/A", "x" * 199 + ".."), ("SC 13G/A", None), ("SC 13G/A", 0),
    (None, ""), (["SC 13G/A"], ""),
])
def test_no_other_row_is_counted_without_a_plain_document(form, document):
    assert issuer._unnamed(form, document) is False


@pytest.mark.parametrize("form", PLAIN_REQUIRED)
@pytest.mark.parametrize("document", ["", "x..htm", "a/b.htm"])
def test_a_stored_filing_must_still_name_one_plain_document(form, document):
    filing = {"accession": "0001654126-26-000001", "form": form, "filing_date": "2026-10-05", "report_date": None,
              "accepted_at": "2026-10-05T16:00:00Z", "primary_document": document, "items": ""}
    with pytest.raises(ValueError, match="issuer filing fields"):
        issuer._filing(filing, NOW)
    parsed = issuer._parse_rows(_index([_row(1, form, document)]), NOW)
    assert parsed["invalid_count"] == 1 and parsed["filings"] == []


def test_an_unnamed_row_is_held_to_every_other_row_rule_and_keeps_secs_value():
    good = [_row(1, "SC 13G/A", "marcus.corp..txt"), _row(2, "SC 13G", "")]
    bad = [dict(good[0], accessionNumber="bad"), dict(good[0], filingDate="2026-10-5"), dict(good[1], items=None),
           dict(good[1], acceptanceDateTime="2026-10-11T06:20:00Z"), dict(good[1], form=""),
           dict(good[0], form="8-K"), dict(good[1], form="SC 14D9"), dict(good[0], primaryDocument="a/b..txt")]
    parsed = issuer._parse_rows(_index(good + bad), NOW)
    assert parsed["invalid_count"] == len(bad)
    # The row keeps SEC's value; only the check reads a fixed name in its place.
    assert [(f["form"], f["primary_document"]) for f in parsed["filings"]] == [(form, doc) for form, doc in
                                                                               (("SC 13G/A", "marcus.corp..txt"), ("SC 13G", ""))]


def test_an_unnamed_row_before_the_window_counts_toward_the_range_only():
    rows = [_row(1, "6-K", "a.htm"), _row(2, "SC 13G/A", "qiagen.n.v..txt", day="2003-02-10"),
            _row(3, "SC 13G", "", day="2008-02-11")]
    parsed = issuer._parse_rows(_index(rows), NOW)
    assert parsed["invalid_count"] == 0 and parsed["range_start"] == "2003-02-10"
    assert [f["form"] for f in parsed["filings"]] == ["6-K"]


def test_the_captured_zim_index_with_unnamed_ownership_rows_still_gives_an_observed_window(producer, canonical):
    data = zim_submissions()
    recent = data["filings"]["recent"]
    before = recent["form"].index("SC 13G")              # 14 November 2024, before the window
    inside = recent["form"].index("SCHEDULE 13G/A")       # 13 November 2025, inside it
    assert recent["filingDate"][before] < "2025-10-10" <= recent["filingDate"][inside]
    recent["primaryDocument"][before], recent["primaryDocument"][inside] = "zim..txt", ""
    fetch = producer.transport(edits={"https://data.sec.gov/submissions/CIK0001654126.json": raw_json(data)})
    result = producer.collect(canonical, fetch=fetch)
    row = next(row for row in result["bundle"]["issuers"] if row["ticker"] == "ZIM")
    index = row["index"]
    assert index["coverage_status"] == "observed_window" and index["reason"] is None and index["metadata_count"] == 99
    assert all(error["code"] != "metadata_invalid" for error in row["errors"])
    # An unnamed row is counted, never listed, linked or fetched.
    assert "zim..txt" not in result["bundle_bytes"].decode() and not any("zim..txt" in url for url in fetch.calls)
    listed = index["listed_filings"] + [entry["filing"] for entry in index["acquisition_review"]["filings"]]
    assert all(issuer._basename(filing["primary_document"]) for filing in listed)
    issuer.validate_bundle(result["receipt_bytes"], result["bundle_bytes"])


@pytest.mark.parametrize("document", ["", "zk..htm"])
def test_a_current_report_without_a_plain_document_is_still_refused_and_never_fetched(producer, canonical, document):
    data = zim_submissions()
    recent = data["filings"]["recent"]
    first = recent["form"].index("6-K")
    original = recent["primaryDocument"][first]
    recent["primaryDocument"][first] = document
    fetch = producer.transport(edits={"https://data.sec.gov/submissions/CIK0001654126.json": raw_json(data)})
    result = producer.collect(canonical, fetch=fetch)
    row = next(row for row in result["bundle"]["issuers"] if row["ticker"] == "ZIM")
    assert {"code": "metadata_invalid", "source_url": "https://data.sec.gov/submissions/CIK0001654126.json"} in row["errors"]
    assert row["index"]["coverage_status"] == "partial"
    accession = recent["accessionNumber"][first]
    assert accession not in result["bundle_bytes"].decode()
    assert not any(accession.replace("-", "") in url for url in fetch.calls) and original != document
    issuer.validate_bundle(result["receipt_bytes"], result["bundle_bytes"])


def _cross_file(producer, canonical, recent, history):
    """AAPL's index cut to one 8-K and a twin of one accession, its history file holding the other copy."""
    data = producer.aapl_submissions()
    original = deepcopy(data["filings"]["recent"])
    twin = {"accessionNumber": "0000320193-26-009100", "filingDate": "2026-10-08",
            "reportDate": "2026-10-08", "acceptanceDateTime": "2026-10-08T16:00:00Z", "items": ""}
    copy = lambda form, document: dict(twin, form=form, primaryDocument=document)
    data["filings"]["recent"] = {key: values[:1] + [copy(*recent)[key]] for key, values in original.items()}
    data["filings"]["files"] = [{"name": "CIK0000320193-submissions-001.json", "filingCount": 2,
                                  "filingFrom": "2025-10-01", "filingTo": "2026-10-08"}]
    historical = {key: [copy(*history)[key], values[-1]] for key, values in original.items()}
    archive_url = "https://data.sec.gov/submissions/CIK0000320193-submissions-001.json"
    fetch = producer.transport(edits={producer.AAPL_SUBMISSIONS: raw_json(data), archive_url: raw_json(historical)})
    result = producer.collect(canonical, fetch=fetch)
    issuer.validate_bundle(result["receipt_bytes"], result["bundle_bytes"])
    return next(row for row in result["bundle"]["issuers"] if row["ticker"] == "AAPL"), archive_url


@pytest.mark.parametrize("recent, history, refused_in, counted", [
    # The unnamed copy is refused wherever it is read; the named copy is kept.
    (("SC 13G", "x.txt"), ("SC 13G", ""), ("history",), 2),
    (("SC 13G", ""), ("SC 13G", "x.txt"), ("recent",), 2),
    # Two unnamed copies that differ are both refused, as each was before.
    (("SC 13G", ""), ("SC 13G", "x..txt"), ("recent", "history"), 1),
])
def test_an_unnamed_copy_across_the_index_and_its_history_is_refused_wherever_it_is_read(
        producer, canonical, recent, history, refused_in, counted):
    row, archive_url = _cross_file(producer, canonical, recent, history)
    index = row["index"]
    urls = {"recent": producer.AAPL_SUBMISSIONS, "history": archive_url}
    # The rest of the history is read, so the range reaches the window; the
    # refused copy keeps the index partial, and the reason says why.
    assert index["history_files_fetched"] == 1 and index["range_start"] == "2025-10-01"
    assert row["errors"] == [{"code": "metadata_invalid", "source_url": urls[where]} for where in refused_in]
    assert index["coverage_status"] == "partial" and index["reason"] == issuer.REFUSED_ROWS_REASON
    assert index["metadata_count"] == counted


def test_an_unnamed_history_copy_before_the_window_is_refused_and_does_not_stretch_the_range(producer, canonical):
    data = producer.aapl_submissions()
    original = deepcopy(data["filings"]["recent"])
    twin = {"accessionNumber": "0000320193-26-009100", "form": "SC 13G", "filingDate": "2026-10-08",
            "reportDate": "2026-10-08", "acceptanceDateTime": "2026-10-08T16:00:00Z", "items": "", "primaryDocument": "x.txt"}
    old_copy = dict(twin, filingDate="2024-01-02", reportDate="2024-01-02",
                    acceptanceDateTime="2024-01-02T16:00:00Z", primaryDocument="")
    data["filings"]["recent"] = {key: values[:1] + [twin[key]] for key, values in original.items()}
    data["filings"]["files"] = [{"name": "CIK0000320193-submissions-001.json", "filingCount": 2,
                                  "filingFrom": "2024-01-02", "filingTo": "2026-10-08"}]
    historical = {key: [old_copy[key], values[-1]] for key, values in original.items()}
    archive_url = "https://data.sec.gov/submissions/CIK0000320193-submissions-001.json"
    fetch = producer.transport(edits={producer.AAPL_SUBMISSIONS: raw_json(data), archive_url: raw_json(historical)})
    result = producer.collect(canonical, fetch=fetch)
    row = next(row for row in result["bundle"]["issuers"] if row["ticker"] == "AAPL")
    # The refused copy is outside the window, yet still refused, and its date is not the range's start.
    assert row["index"]["range_start"] == "2025-10-01" and row["index"]["metadata_count"] == 2
    assert row["errors"] == [{"code": "metadata_invalid", "source_url": archive_url}]
    issuer.validate_bundle(result["receipt_bytes"], result["bundle_bytes"])


def test_a_named_acquisition_form_in_the_history_is_kept_over_an_unnamed_recent_copy(producer, canonical):
    row, archive_url = _cross_file(producer, canonical, ("SC 13G", ""), ("DEFM14A", "merger.htm"))
    review = row["index"]["acquisition_review"]
    assert review["observed_count"] == 1
    entry, = review["filings"]
    assert entry["filing"]["primary_document"] == "merger.htm" and entry["index_source"]["url"] == archive_url
    assert row["errors"] == [{"code": "metadata_invalid", "source_url": producer.AAPL_SUBMISSIONS}]


def test_a_named_acquisition_form_in_the_index_is_kept_over_an_unnamed_history_copy(producer, canonical):
    row, archive_url = _cross_file(producer, canonical, ("DEFM14A", "merger.htm"), ("SC 13G", ""))
    entry, = row["index"]["acquisition_review"]["filings"]
    assert entry["index_source"]["url"] == producer.AAPL_SUBMISSIONS
    assert row["errors"] == [{"code": "metadata_invalid", "source_url": archive_url}]


def test_two_named_copies_across_the_index_and_its_history_still_refuse_the_history_file(producer, canonical):
    data = producer.aapl_submissions()
    original = deepcopy(data["filings"]["recent"])
    twin = {"accessionNumber": "0000320193-26-009100", "form": "SC 13G", "filingDate": "2026-10-08",
            "reportDate": "2026-10-08", "acceptanceDateTime": "2026-10-08T16:00:00Z", "items": ""}
    data["filings"]["recent"] = {key: values[:1] + [twin.get(key, "a.txt")] for key, values in original.items()}
    data["filings"]["files"] = [{"name": "CIK0000320193-submissions-001.json", "filingCount": 2,
                                  "filingFrom": "2025-10-01", "filingTo": "2026-10-08"}]
    historical = {key: [twin.get(key, "b.txt"), values[-1]] for key, values in original.items()}
    archive_url = "https://data.sec.gov/submissions/CIK0000320193-submissions-001.json"
    fetch = producer.transport(edits={producer.AAPL_SUBMISSIONS: raw_json(data), archive_url: raw_json(historical)})
    row = next(row for row in producer.collect(canonical, fetch=fetch)["bundle"]["issuers"] if row["ticker"] == "AAPL")
    assert row["index"]["history_files_fetched"] == 0 and row["index"]["range_start"] == "2026-10-08"
    assert {"code": "metadata_invalid", "source_url": archive_url} in row["errors"]
    assert row["index"]["reason"] != issuer.REFUSED_ROWS_REASON


@pytest.mark.parametrize("copies, refused", [
    ([("SC 13G/A", "marcus.corp.txt"), ("SC 13G/A", "marcus.corp..txt")], 1),
    ([("SC 13G/A", ""), ("SC 13G/A", "marcus.corp.txt")], 1),
    ([("SC 13G", ""), ("SC 13G", "x..txt")], 2),
    ([("SC 13G", ""), ("SC 13G", "x..txt"), ("SC 13G", "x.txt")], 2),
    ([("SC 13G", ""), ("SC 13G", "")], 0),
])
def test_an_unnamed_copy_of_an_accession_listed_differently_in_one_file_is_refused_not_the_index(copies, refused):
    rows = [_row(1, "6-K", "a.htm")] + [_row(2, form, document) for form, document in copies]
    parsed = issuer._parse_rows(_index(rows), NOW)
    assert parsed["invalid_count"] == refused
    named = [d for _, d in copies if issuer._basename(d)]
    kept = named[:1] or ([copies[0][1]] if refused == 0 else [])
    assert [f["primary_document"] for f in parsed["filings"]] == ["a.htm", *kept]
    # In either order, the same rows are refused and kept.
    reversed_rows = [_row(1, "6-K", "a.htm")] + [_row(2, form, document) for form, document in reversed(copies)]
    assert issuer._parse_rows(_index(reversed_rows), NOW)["invalid_count"] == refused


def test_the_job_log_names_each_issuers_index_coverage_and_nothing_of_its_sources():
    bundle = json.loads((FIXTURES / "collected-bundle.json").read_bytes())
    lines = issuer.issuer_lines(bundle)
    assert [line.split(":")[0].strip() for line in lines] == [row["ticker"] for row in bundle["issuers"]]
    zim = next(line for line in lines if line.strip().startswith("ZIM:"))
    assert zim == "  ZIM: partial; identity verified; index observed_window, 99 metadata rows; errors: http_error."
    assert not any("http" in line.replace("http_error", "") or "/" in line or ".htm" in line for line in lines)
    one = deepcopy(bundle)
    row = one["issuers"][1]
    row["index"]["metadata_count"] = 1
    row["errors"] = []
    assert issuer.issuer_lines(one)[1] == "  ZIM: partial; identity verified; index observed_window, 1 metadata row; errors: none."


def test_main_prints_the_status_line_then_one_line_an_issuer(tmp_path, monkeypatch, capsys, producer, canonical):
    result = producer.collect(canonical)
    record = tmp_path / "data.json"
    record.write_bytes(canonical)
    monkeypatch.setattr(issuer, "collect", lambda *a, **k: result)
    monkeypatch.setattr("sys.argv", ["issuer_evidence", "--record", str(record), "--previous", str(tmp_path / "none.json"),
                                     "--output", str(tmp_path / "out"), "--dry-run"])
    assert issuer.main() == 0
    printed = capsys.readouterr().out.splitlines()
    assert printed[0].startswith(f'Issuer evidence: {result["receipt"]["status"]}; ')
    assert printed[1:] == issuer.issuer_lines(result["bundle"])
