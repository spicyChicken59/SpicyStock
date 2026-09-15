"""Discovery identity reaches the reader; no desired historical grade is assumed."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src import discovery, grader, pipeline, quality, scans
from tests.test_grader import claude  # scripted transport fixture: no network
from tests.test_scans import bar, flat, frame

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "a89ab122d7e0160df6a63c30957668447ace1103"
FIXTURES = ROOT / "tests" / "fixtures" / "grading"
AUDIT = json.loads((FIXTURES / "history-audit.json").read_text())


def archived(ticker):
    directory = FIXTURES  # survives the public catalog's rolling retention window
    return (json.loads((directory / f"burst-{ticker}.json").read_text())["row"],
            json.loads((directory / "record.json").read_text())["rules"])


@pytest.mark.parametrize("ticker,gain,move", [("CACI", 2.57, 9.78), ("ROKU", 1.63, 2.14)])
def test_archived_dollar_request_explicitly_separates_admission(ticker, gain, move):
    row, rules = archived(ticker)
    assert row["scan"] == "dollar" and row["gain_pct"] == gain and row["dollar_move"] == move
    assert "4%" in row["claude"]["reason"]
    # This fails on the old request itself, before any new helper is involved.
    measurements = {k: v for k, v in row.items() if k not in ("claude", "summary", "grade", "plan", "series")}
    text = grader.user_text({**measurements, "recorded_rules": rules})
    assert '"admitted_by": [' in text
    assert "NOT admission requirements" in text
    system = " ".join((ROOT / "knowledge" / "strategy.md").read_text().split())
    assert "up 4% or more on volume above the previous day" not in system
    assert "is NOT by itself a disqualifier" in system
    assert all(f"**{route}**" in system for route in ("burst", "dollar", "both"))


@pytest.mark.parametrize("scan,close,open_,volume", [
    ("dollar", 102.004, 100.001, 150000.49),
    ("burst", 104, 103.5, 250000),
    ("both", 104, 100, 250000),
])
def test_real_scan_publishes_the_contract(scan, close, open_, volume):
    df = frame(flat(260) + [bar(close, o=open_, v=volume)])
    uni = SimpleNamespace(names={}, flags={})
    rows, _, _ = pipeline.scan_frames({"SYN": df}, uni, pipeline.RunReport())
    assert rows[0]["scan"] == scan
    assert "discovery" in rows[0]
    row = rows[0]
    block = row["discovery"]
    admitted = [scan] if scan != "both" else ["burst", "dollar"]
    assert block["admitted_by"] == admitted
    assert set(block["applicable_rules"]) == set(admitted)
    assert set(block["inapplicable_rules"]) == {"burst", "dollar"} - set(admitted)
    assert block["measurements"]["prev_volume"] == 200000
    assert block["measurements"]["close"] == round(close, 2)
    assert block["measurements"]["volume"] == round(volume)
    if scan == "dollar":
        assert row["close"] == 102.004  # published display precision stays intact
        assert block["measurements"]["open"] == 100
    if scan == "dollar":
        assert block["measurements"]["gain_pct"] == 2
        assert block["measurements"]["volume_vs_prior"] == .75
        assert block["applicable_rules"]["dollar"] == {"min_move": .9, "min_volume_exclusive": 100000}
    if "burst" in admitted:
        assert block["applicable_rules"]["burst"] == {"min_ratio": 1.04, "volume_above_prior": True, "min_volume": 100000}
    metrics = quality.metrics_for_model(row["_assessment"], "SYN", close,
                                        {"scan": scan, "discovery": block})
    assert metrics["discovery"] == block
    text = grader.user_text(metrics)
    assert text == grader.user_text(dict(reversed(list(metrics.items()))))


def test_archived_thresholds_are_not_substituted_with_current_constants():
    row, rules = archived("ROKU")
    altered = copy.deepcopy(rules)
    altered["dollar"]["min_move"] = 1.23
    altered["burst"]["min_ratio"] = 1.05
    block = discovery.contract(row, altered)
    assert block["applicable_rules"]["dollar"]["min_move"] == 1.23
    assert block["inapplicable_rules"]["burst"]["min_ratio"] == 1.05
    assert block["measurements"]["prev_volume"] is None
    assert rules["dollar"]["min_move"] == .9
    del altered["dollar"]
    with pytest.raises(KeyError):
        discovery.contract(row, altered)


@pytest.mark.parametrize("case", [r for r in AUDIT["rows"]
                                 if r["classification"] in ("explicit_inapplicable_burst_minimum",
                                                             "unsupported_universal_percent_disqualification")],
                         ids=lambda r: r["source_record"][:7] + "-" + r["ticker"])
def test_all_nine_reviewed_contradictions_fall_back_without_retry(claude, case):
    rules = AUDIT["sources"][case["source_record"]]["rules"]
    block = discovery.contract({**case["measurements"], "scan": case["scan"]}, rules)
    cl = case["original_reader"]
    claude.payload(**{k: cl[k] for k in ("grade", "score", "reason", "key_risk", "entry_note")})
    usage = {}
    result = grader.grade_candidate(case["ticker"], {"scan": case["scan"], "discovery": block},
                                    None, "synthetic system", usage)
    assert result["provenance"]["source"] == grader.SOURCE_FALLBACK
    assert "DiscoveryConflict" in result["provenance"]["error"]
    assert result["grade"] == grader.UNGRADED and result["provenance"]["chart_seen"] is False
    assert len(claude.calls) == 1 and sum(usage.values()) > 0


@pytest.mark.parametrize("ticker", ["CACI", "ROKU"])
def test_independent_archived_quality_evidence_stays_available(claude, ticker):
    row, rules = archived(ticker)
    q = row["quality"]
    if ticker == "CACI":
        assert next(c for c in q["checks"] if c["letter"] == "Y")["passed"] is False
    else:
        assert q["passes"] == q["of"] == 6
        assert next(c for c in q["checks"] if c["letter"] == "RE")["passed"] is True
        assert q["burst"]["volume_vs_avg50"] == .64 and q["burst"]["volume_rank_60"] == 53
    block = discovery.contract(row, rules)
    metrics = {"scan": row["scan"], "discovery": block, "quality": q}
    original = copy.deepcopy(metrics)
    claude.payload(score=5.5, grade="C", reason="Synthetic independent critique: three wide overlapping base bars.")
    result = grader.grade_candidate(ticker, metrics, None, "synthetic system")
    assert result["provenance"]["source"] == grader.SOURCE_CLAUDE
    assert result["reason"].startswith("Synthetic independent")
    assert metrics == original  # no public/historical grade or evidence mutation
    sent = claude.calls[0]["messages"][0]["content"][-1]["text"]
    assert json.loads(sent.split("METRICS:\n")[1].split("\n\nRespond")[0])["quality"] == q


def test_guard_preserves_quality_breakdowns_and_checks_every_explanation_field():
    row, rules = archived("ROKU")
    block = discovery.contract(row, rules)
    assert discovery.conflicting_fields(block, {"reason": "The base fails with two 4% down days."}) == []
    assert discovery.conflicting_fields(block, {"reason": "Volume is 24% below yesterday."}) == []
    assert discovery.conflicting_fields(block, {"entry_note": "Skip if the stop requires more than 4% risk."}) == []
    assert discovery.conflicting_fields(block, {"entry_note": "The burst close gives a stop above the 4% risk threshold."}) == []
    for field in ("reason", "key_risk", "entry_note"):
        assert discovery.conflicting_fields(block, {field: "Below the four-percent minimum; skip."}) == [field]
    burst = discovery.contract({**row, "scan": "burst"}, rules)
    assert discovery.conflicting_fields(burst, {"entry_note": "Fails the $0.90 dollar minimum."}) == ["entry_note"]
    both = discovery.contract({**row, "scan": "both"}, rules)
    assert discovery.conflicting_fields(both, {"reason": "The 4% threshold applies."}) == []


def test_audit_snapshot_is_complete_and_original_fixture_bytes_are_preserved():
    counts = AUDIT["counts"]
    assert counts["entries"] == 1404 and counts["reaction_rows"] == 1359
    assert counts["model_reviewed"] == len(AUDIT["rows"]) == 36
    assert counts["classifications"] == {
        "explicit_inapplicable_burst_minimum": 8,
        "unsupported_universal_percent_disqualification": 1,
        "ambiguous_contextual_critique": 2,
        "no_discovery_contradiction_observed": 25,
    }
    for ticker in ("CACI", "ROKU"):
        case = next(r for r in AUDIT["rows"] if r["ticker"] == ticker)
        assert hashlib.sha256((FIXTURES / f"burst-{ticker}.json").read_bytes()).hexdigest() == case["sha256"]


@pytest.mark.parametrize("conflict", [False, True])
def test_pipeline_archives_the_sent_contract_and_rejects_false_judgement(claude, monkeypatch, tmp_path, conflict):
    df = frame(flat(260) + [bar(102, o=100, v=150000)])
    rep = pipeline.RunReport()
    rows, _, _ = pipeline.scan_frames({"SYN": df}, SimpleNamespace(names={}, flags={}), rep)
    monkeypatch.setattr(pipeline.charts, "render_chart", lambda *args, **kwargs: None)
    if conflict:
        claude.payload(reason="Below the 4% minimum, so this cannot qualify.")
    pipeline.read_charts_and_grade(rows, {"SYN": df}, rep, tmp_path, "synthetic system", True)
    call = claude.calls[0]
    text = call["messages"][0]["content"][-1]["text"]
    sent = json.loads(text.split("METRICS:\n")[1].split("\n\nRespond")[0])
    row = rows[0]
    assert sent["discovery"] == row["discovery"]
    assert sent["discovery"]["admitted_by"] == ["dollar"]
    cl = row["claude"]
    assert cl["discovery_version"] == 1
    assert cl["request_text_sha256"] == hashlib.sha256(json.dumps(
        {"system": "synthetic system", "user": text}, sort_keys=True).encode()).hexdigest()
    assert len(claude.calls) == 1
    if conflict:
        assert row["grade"] == row["grade_mechanical"]
        assert cl["source"] == "fallback" and cl["reason"] is cl["score"] is cl["grade"] is None
        assert cl["chart_seen"] is False and "DiscoveryConflict" in cl["error"]
        assert rep.problems[0]["kind"] == "claude_unavailable"
    else:
        assert cl["source"] == "claude"


def test_a_mismatched_contract_cannot_smuggle_another_admission_rule():
    row, rules = archived("ROKU")
    block = discovery.contract(row, rules)
    block["applicable_rules"]["burst"] = rules["burst"]
    with pytest.raises(ValueError, match="identity disagrees"):
        grader.user_text({"scan": "dollar", "discovery": block})
