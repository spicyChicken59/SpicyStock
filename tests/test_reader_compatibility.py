"""Offline contract/retention regressions; scripted replies are NOT Sep 22 replies.

The twelve actual replies were discarded. The dated incident inventory records
that limit, and these tests never replace missing history with invented text.
"""
from copy import deepcopy
import hashlib
import json
import gzip
from pathlib import Path

import pytest

from src import grader, reader_authority
from tests.test_grader import claude, _Reply
from tests.test_reader_authority import inputs, finding


def test_default_model_receives_the_exact_nested_finding_schema():
    _, metrics = inputs()
    text = grader.user_text(metrics)
    marker = "FINDINGS JSON SCHEMA:\n"
    assert marker in text, "default model never receives the required finding object shape"
    schema, _ = json.JSONDecoder().raw_decode(text.split(marker, 1)[1])
    assert schema == grader.SCORE_SCHEMA["properties"]["findings"]
    item = schema["items"]
    assert set(item["required"]) == {"criterion", "source", "evidence", "observation"}
    assert item["additionalProperties"] is False
    citation = item["properties"]["evidence"]["items"]
    assert set(citation["required"]) == {"path", "value"}
    assert citation["additionalProperties"] is False


@pytest.mark.parametrize("flaw", ["extra", "missing", "non_object", "contradiction", "observation"])
def test_rejected_reply_is_retained_exactly_before_authority_checks(claude, flaw):
    assessment, metrics = inputs()
    before = deepcopy(assessment.to_dict())
    f = finding(criterion="measured_quality", source="strategy.quality",
                observation="recorded_check_defect")
    if flaw == "extra": f["unsupported_limit"] = 1.5
    if flaw == "missing": del f["source"]
    if flaw == "non_object": f = "loose base"
    if flaw == "contradiction": f["evidence"][0]["value"] = "FAIL"
    if flaw == "observation": f["observation"] = "arbitrary free text"
    raw = '\n' + json.dumps({"score": 6.5, "grade": "B", "reason": "Scripted defect.",
        "key_risk": "scripted", "entry_note": "scripted", "findings": [f]}, indent=2) + '\n'
    claude.replies(raw)
    result = grader.grade_candidate("SYN", metrics, None, "scripted contract")
    assert result["provenance"]["source"] == "fallback"
    assert "ReaderAuthorityError" in result["provenance"]["error"]
    assert len(claude.calls) == 1
    attempt = result["provenance"]["attempts"][0]
    assert attempt["response"]["text"] == raw
    assert attempt["response"]["text_sha256"] == hashlib.sha256(raw.encode()).hexdigest()
    assert attempt["response"]["bytes"] == len(raw.encode())
    assert attempt["response"]["retention"] == "complete"
    assert json.loads(attempt["response"]["text"])["findings"] == [f]
    assert attempt["outcome"] == "rejected" and not attempt["correction"]
    assert assessment.to_dict() == before
    assert result["grade"] == grader.UNGRADED


@pytest.mark.parametrize("kind", ["malformed", "truncated"])
def test_parser_retry_preserves_both_responses_and_request_identity(claude, kind):
    _, metrics = inputs()
    first = '{"score": 6.5, "findings": ['
    last = json.dumps({"score": 10, "grade": "A+", "findings": []})
    claude.replies(_Reply(first, "max_tokens" if kind == "truncated" else "end_turn"), last)
    result = grader.grade_candidate("SYN", metrics, None, "unchanged cache prefix")
    attempts = result["provenance"]["attempts"]
    assert len(attempts) == len(claude.calls) == 2
    assert [a["response"]["text"] for a in attempts] == [first, last]
    assert [a["outcome"] for a in attempts] == ["rejected", "model"]
    assert [a["correction"] for a in attempts] == [False, True]
    assert attempts[0]["request_sha256"] != attempts[1]["request_sha256"]
    assert claude.calls[0]["system"] == claude.calls[1]["system"]
    assert claude.calls[1]["messages"][0]["content"][-1]["text"] == grader.RETRY_CORRECTION


def test_transport_failure_does_not_borrow_a_previous_response(claude):
    claude.replies('{"score":', TimeoutError("scripted transport failure"))
    result = grader.grade_candidate("SYN", {}, None, "scripted")
    attempts = result["provenance"]["attempts"]
    assert attempts[0]["response"]["text"] == '{"score":'
    assert "response" not in attempts[1]


def test_oversize_response_retention_is_explicit_and_bounded(claude):
    raw = 'é' * (64 * 1024)
    claude.replies(raw)
    result = grader.grade_candidate("SYN", {}, None, "scripted", attempts=1)
    response = result["provenance"]["attempts"][0]["response"]
    assert response["retention"] == "omitted_oversize"
    assert response["text"] is None
    assert response["bytes"] == len(raw.encode())
    assert response["text_sha256"] == hashlib.sha256(raw.encode()).hexdigest()


def test_confirmation_needs_no_adverse_findings(claude):
    _, metrics = inputs()
    claude.payload(score=metrics["quality_score"], grade=metrics["quality_grade"], findings=[])
    result = grader.grade_candidate("SYN", metrics, None, "scripted")
    assert result["provenance"]["source"] == "claude"
    assert result["findings"] == []


def test_schema_and_validator_keep_unknown_fields_and_nulls_closed():
    _, metrics = inputs()
    for change in ({"new_threshold": 2}, {"evidence": None}, {"observation": None}):
        with pytest.raises(reader_authority.ReaderAuthorityError):
            reader_authority.validate({"grade": "B", "reason": "scripted", "findings": [finding(**change)]},
                                      metrics, chart_seen=True)


def test_boolean_cannot_impersonate_numeric_evidence():
    _, metrics = inputs()
    metrics["reader_evidence"]["checks"]["C"]["values"]["base_sessions"] = 1
    with pytest.raises(reader_authority.ReaderAuthorityError, match="contradicts"):
        reader_authority.validate({"grade": "B", "reason": "scripted", "findings": [finding(
            evidence=[{"path": "checks.C.values.base_sessions", "value": True}])]}, metrics, chart_seen=True)


def test_all_twelve_real_incident_records_preserve_unknown_responses():
    """Real records, not real reply fixtures: no assertion invents absent text."""
    from src.provenance import digest
    root = Path(__file__).resolve().parents[1]
    audit = json.loads((root / "docs/input-truthfulness/2026-09-23-reader-production-inventory.json").read_text())
    ledger = json.loads(gzip.decompress((root / audit["ledger_path"]).read_bytes()))
    assert [r["ticker"] for r in audit["decisions"]] == [
        "IOSP", "KYMR", "HSIC", "IDCC", "CLMB", "CRVL", "MEDP", "NEM", "PYPD", "WPM", "AG", "AIT"]
    assert len(audit["decisions"]) == 12
    for row in audit["decisions"]:
        saved = next(r for r in ledger["signal"]["candidates"] if r["ticker"] == row["ticker"])
        assert row["reader"] == saved["reader"]
        assert row["mechanical_grade"] == row["final_grade"] == saved["grade"]
        assert row["mechanical_score"] == saved["assessment"]["score"]
        assert digest(row["metrics"]) == row["reader_input"]["metrics_sha256"]
        assert row["reader"]["attempts"][0]["error"] == (
            "src.ReaderAuthorityError: finding has missing or unauthorized fields")
        assert "response" not in row["reader"]["attempts"][0]
        for field in ("raw_response", "raw_response_sha256", "parsed_score", "parsed_grade", "findings",
                      "structural_subclass", "semantic_authority", "otherwise_valid_finding"):
            assert row[field] is None
        assert row["response_reconstruction"] == "BLOCKED"
