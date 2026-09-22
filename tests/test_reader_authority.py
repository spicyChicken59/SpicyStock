"""Scripted responses exercise authority, never predict a real model's answer."""
from copy import deepcopy
import gzip
import json
from pathlib import Path

import pytest

from src import grader, quality
from tests.test_grader import claude
from tests.test_quality import ideal_bars, frame


def inputs():
    assessment = quality.assess(frame(ideal_bars()))
    metrics = quality.metrics_for_model(assessment, "SYN", 100)
    # Explicit contract also makes these regressions executable on the old
    # implementation. The real quality builder must supply it after the fix.
    metrics["reader_evidence"] = {
        "version": 1,
        "checks": {c.letter: {"status": c.status, "values": c.value}
                   for c in assessment.checks},
    }
    return assessment, metrics


def finding(**changes):
    return {"criterion": "base_shape", "source": "strategy.chart.base",
            "evidence": [{"path": "checks.C.status", "value": "PASS"}],
            "observation": "wide_overlapping_bars",
            **changes}


def response(claude, findings, reason="The base has wide overlapping bars."):
    claude.payload(score=6.5, grade="B", reason=reason, findings=findings)


@pytest.mark.parametrize("flaw", [
    "missing", "empty", "invented_rule", "false_status", "false_number",
    "unknown_as_failure", "discovery_gate", "invented_cutoff", "no_chart", "prose_as_rule",
])
def test_unsupported_downgrade_is_rejected_whole_without_retry(claude, tmp_path, flaw):
    _, metrics = inputs()
    chart = tmp_path / "synthetic.png"
    chart.write_bytes(b"scripted image transport; not a historical chart")
    fs = [finding()]
    if flaw == "missing":
        claude.payload(score=6.5, grade="B", reason="Uncited arbitrary rejection.")
    else:
        if flaw == "empty": fs = []
        if flaw == "invented_rule": fs[0]["criterion"] = "universal_percent_minimum"
        if flaw == "false_status": fs[0]["evidence"][0]["value"] = "FAIL"
        if flaw == "false_number": fs[0]["evidence"] = [{"path": "checks.C.values.giveback", "value": 0.99}]
        if flaw == "unknown_as_failure":
            metrics["reader_evidence"]["checks"]["C"] = {"status": "UNMEASURED", "values": {"giveback": None}}
            fs[0] = finding(criterion="measured_quality", source="strategy.quality",
                            observation="recorded_check_defect",
                            evidence=[{"path": "checks.C.status", "value": "UNMEASURED"}])
        if flaw == "discovery_gate": fs[0]["evidence"] = [{"path": "discovery.gain_pct", "value": 1.63}]
        if flaw == "invented_cutoff": fs[0]["minimum_gain"] = 5
        if flaw == "prose_as_rule": fs[0]["observation"] = "Require 5 percent on every Dollar setup."
        response(claude, fs)
    result = grader.grade_candidate("SYN", metrics, None if flaw == "no_chart" else str(chart), "scripted contract")
    assert result["provenance"]["source"] == grader.SOURCE_FALLBACK
    assert "ReaderAuthorityError" in result["provenance"]["error"]
    assert len(claude.calls) == 1
    assert result["grade"] == grader.UNGRADED


def test_source_grounded_visual_downgrade_control_survives(claude, tmp_path):
    assessment, metrics = inputs()
    before = deepcopy(assessment.to_dict())
    chart = tmp_path / "synthetic.png"
    chart.write_bytes(b"synthetic chart transport")
    # Equivalent JSON numeric notation is not a false factual disagreement.
    sessions = metrics["reader_evidence"]["checks"]["C"]["values"]["base_sessions"]
    response(claude, [finding(evidence=[
        {"path": "checks.C.status", "value": "PASS"},
        {"path": "checks.C.values.base_sessions", "value": float(sessions)}])])
    result = grader.grade_candidate("SYN", metrics, str(chart), "scripted contract")
    assert result["provenance"]["source"] == grader.SOURCE_CLAUDE
    assert grader.final_grade(assessment.grade, result["grade"]) == "B"
    assert assessment.to_dict() == before


def test_model_never_upgrades_a_mechanical_grade(claude):
    _, metrics = inputs()
    metrics["quality_grade"] = "B"
    claude.payload(score=10, grade="A+", findings=[])
    result = grader.grade_candidate("SYN", metrics, None, "scripted contract")
    assert result["provenance"]["source"] == grader.SOURCE_CLAUDE
    assert grader.final_grade("B", result["grade"]) == "B"


def retained_inputs(index):
    """Original dated frame, current unchanged mechanics; no historical write."""
    from src.provenance import frame_of
    root = Path(__file__).resolve().parents[1]
    audit = json.loads((root / "docs/input-truthfulness/2026-09-22-reader-downgrade-audit.json").read_text())
    row = audit["decisions"][index]
    sha = row["provenance"]["source"]["sha256"]
    df = frame_of(json.loads(gzip.decompress((root / "docs/evidence" / (sha + ".json.gz")).read_bytes())))
    assessment = quality.assess(df)
    assert (assessment.grade, assessment.score, assessment.a_plus_count) == (
        row["mechanical_grade"], row["mechanical_score"], row["a_plus_tally"])
    assert {c.letter: c.status for c in assessment.checks} == {
        letter: c["status"] for letter, c in row["checks"].items()}
    metrics = quality.metrics_for_model(assessment, row["ticker"], float(df.Close.iloc[-1]))
    metrics["reader_evidence"] = {"version": 1, "checks": {
        c.letter: {"status": c.status, "values": c.value} for c in assessment.checks}}
    return row, assessment, metrics


def test_retained_wbd_cannot_replace_recorded_giveback_with_a_new_limit(claude):
    row, assessment, metrics = retained_inputs(96)
    assert metrics["reader_evidence"]["checks"]["C"]["values"]["giveback"] == 0.33
    before = deepcopy(assessment.to_dict())
    response(claude, [finding(criterion="measured_quality", source="strategy.quality",
        observation="recorded_check_defect",
        evidence=[{"path": "checks.C.status", "value": "FAIL"}])],
        reason="Giveback 0.33 fails the reader's invented limit.")
    result = grader.grade_candidate(row["ticker"], metrics, None, "scripted retained-input counterexample")
    assert result["provenance"]["source"] == grader.SOURCE_FALLBACK
    assert assessment.to_dict() == before


def test_retained_ptgx_supported_measured_downgrade_needs_no_invented_gate(claude):
    row, assessment, metrics = retained_inputs(105)
    assert metrics["reader_evidence"]["checks"]["RE"]["status"] == "FAIL"
    response(claude, [finding(criterion="measured_quality", source="strategy.quality",
        observation="recorded_check_defect",
        evidence=[{"path": "checks.RE.status", "value": "FAIL"}])],
        reason="The supplied RE check fails against the prior five bars.")
    result = grader.grade_candidate(row["ticker"], metrics, None, "scripted retained-input control")
    assert result["provenance"]["source"] == grader.SOURCE_CLAUDE
    assert grader.final_grade(assessment.grade, result["grade"]) == "B"
