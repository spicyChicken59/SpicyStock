"""The retained HAE reply of 8 October 2026, held rejected (#109): both
publications' own rows, their digests, the grader's parse of the retained
text, the authority refusal for the citation paths it used, the replay into
the recorded fallback through the scripted transport, and no ticket under any
regime. The one control -- the same findings with citations copied from the
row's own reader evidence -- is synthetic and labelled; it shows the refusal
is the paths, never a corrected grade for HAE."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path

import pytest

from src import discovery, grader, pipeline, plan, reader_authority
from tests.test_grader import claude  # noqa: F401  -- the scripted transport: no network

FIXTURE = Path(__file__).parent / "fixtures/grading/reader-hae"
META = json.loads((FIXTURE / "source.json").read_text(encoding="utf-8"))
PUBLICATIONS = META["publications"]
#: the citations both replies made: measurements the model read, none under checks.<letter>
UNAUTHORIZED_PREFIXES = ("burst.", "flags")


def row_of(pub: dict) -> dict:
    return json.loads((FIXTURE / pub["file"]).read_text(encoding="utf-8"))


def reply_of(row: dict) -> str:
    return row["claude"]["attempts"][0]["response"]["text"]


def metrics_of(row: dict) -> dict:
    """The parts of the grader's metrics block the authority and discovery
    checks read, rebuilt from the row's own archived checks and discovery
    contract; the checklist prose the model saw is not needed to judge the
    reply, and the row does not carry it."""
    checks = {c["letter"]: {"status": c["status"], "values": deepcopy(c["values"])} for c in row["quality"]["checks"]}
    return {"ticker": row["ticker"], "scan": row["scan"], "discovery": deepcopy(row["discovery"]),
            "quality_grade": row["quality"]["grade"], "quality_score": row["quality"]["score"],
            "passes": row["quality"]["passes"], "of": row["quality"]["of"],
            "reader_evidence": {"version": reader_authority.VERSION, "checks": checks}}


@pytest.mark.parametrize("pub", PUBLICATIONS, ids=[p["label"] for p in PUBLICATIONS])
def test_the_retained_rows_are_the_publications_own(pub):
    raw = (FIXTURE / pub["file"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == pub["row_sha256"]
    row = json.loads(raw)
    assert row["ticker"] == META["ticker"] == "HAE"
    reader = row["claude"]
    assert reader["source"] == grader.SOURCE_FALLBACK and reader["grade"] is None and reader["score"] is None
    assert reader["error"] == pub["recorded_error"] == "src.ReaderAuthorityError: evidence outside criterion authority"
    # one attempt: an authority refusal is never retried
    assert len(reader["attempts"]) == 1
    attempt = reader["attempts"][0]
    assert attempt["outcome"] == "rejected" and attempt["error"] == pub["recorded_error"]
    response = attempt["response"]
    text = response["text"]
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == response["text_sha256"] == pub["reply_text_sha256"]
    assert len(text.encode("utf-8")) == response["bytes"] == pub["reply_bytes"]
    assert response["message_id"] == pub["reply_message_id"] and response["stop_reason"] == "end_turn"
    # the mechanical judgement survived the fallback whole; nothing was planned on it
    assert row["grade"] == row["grade_mechanical"] == row["quality"]["grade"] == pub["mechanical_grade"] == "A+"
    assert (row["quality"]["score"], row["quality"]["passes"], row["quality"]["of"]) == (10.0, 6, 6)
    assert row["reader_coverage"] == "fallback" and row["plan"] is None
    assert row["evidence"]["reader_source"] == grader.SOURCE_FALLBACK


@pytest.mark.parametrize("pub", PUBLICATIONS, ids=[p["label"] for p in PUBLICATIONS])
def test_the_retained_reply_is_a_downgrade_citing_paths_outside_the_contract(pub):
    row = row_of(pub)
    parsed = grader._validated(grader._extract_json(reply_of(row)))
    # a lower grade than the mechanical A+, with findings attached
    assert grader.GRADES.index(parsed["grade"]) > grader.GRADES.index("A+")
    assert parsed["score"] < row["quality"]["score"]
    paths = [c["path"] for f in parsed["findings"] for c in f["evidence"]]
    assert len(parsed["findings"]) == 2 and paths
    assert all(p.startswith(UNAUTHORIZED_PREFIXES) for p in paths), paths
    assert not any(p.startswith("checks.") for p in paths)
    metrics = metrics_of(row)
    # the admission tripwire did not fire: the reply's refusal is the authority rule's
    assert discovery.conflicting_fields(discovery.for_metrics(metrics), parsed) == []
    with pytest.raises(reader_authority.ReaderAuthorityError, match="evidence outside criterion authority") as caught:
        reader_authority.validate(parsed, metrics, chart_seen=True)
    assert grader._error_text(caught.value) == pub["recorded_error"]


@pytest.mark.parametrize("pub", PUBLICATIONS, ids=[p["label"] for p in PUBLICATIONS])
def test_control_the_same_findings_cited_from_the_contract_are_admissible(pub):
    """SYNTHETIC: the refusal is the citation paths. Copying each finding's
    citations from the row's own reader evidence -- the measurements the
    contract names, at the values the checks recorded -- makes the same two
    findings admissible. This is what the contract admits, not HAE's grade."""
    row = row_of(pub)
    metrics = metrics_of(row)
    checks = metrics["reader_evidence"]["checks"]
    parsed = grader._validated(grader._extract_json(reply_of(row)))
    cited = {"signal_shape": [("RE", "bar_range_pct"), ("VOL", "volume_vs_prior")],
             "event_structure": [("VOL", "volume_vs_avg50"), ("RE", "vs_prior_5")]}
    for finding in parsed["findings"]:
        finding["evidence"] = [{"path": f"checks.{letter}.values.{field}", "value": checks[letter]["values"][field]}
                               for letter, field in cited[finding["criterion"]]]
    findings = reader_authority.validate(parsed, metrics, chart_seen=True)
    assert [f["criterion"] for f in findings] == ["signal_shape", "event_structure"]
    # and without a chart the same visual findings are refused for THAT reason
    with pytest.raises(reader_authority.ReaderAuthorityError, match="visual finding without a chart"):
        reader_authority.validate(parsed, metrics, chart_seen=False)


@pytest.mark.parametrize("pub", PUBLICATIONS, ids=[p["label"] for p in PUBLICATIONS])
def test_the_grader_replays_the_retained_reply_into_the_recorded_fallback(pub, claude, tmp_path):  # noqa: F811
    row = row_of(pub)
    claude.replies(reply_of(row))
    chart = tmp_path / "HAE.png"
    chart.write_bytes(b"\x89PNG\r\n\x1a\n synthetic chart bytes: the grader reads them, it never looks")
    usage: dict = {}
    result = grader.grade_candidate("HAE", metrics_of(row), str(chart), "system prompt", usage)
    prov = result["provenance"]
    assert prov["source"] == grader.SOURCE_FALLBACK and prov["error"] == pub["recorded_error"]
    assert result["grade"] == grader.UNGRADED
    assert len(claude.calls) == 1 and len(prov["attempts"]) == 1   # an authority refusal is not retried
    attempt = prov["attempts"][0]
    assert attempt["outcome"] == "rejected" and attempt["error"] == pub["recorded_error"]
    assert attempt["response"]["text_sha256"] == pub["reply_text_sha256"]
    assert attempt["response"]["bytes"] == pub["reply_bytes"]
    # the one reply that arrived was billed, refused or not
    assert (usage["calls"], usage["responses"]) == (1, 1)
    assert len(prov["billing"]) == 1 and set(prov["billing"][0]) == {"cache_write", "cache_read", "uncached", "output"}
    assert prov["chart_seen"] is False   # a fallback row never claims the chart was read


@pytest.mark.parametrize("pub", PUBLICATIONS, ids=[p["label"] for p in PUBLICATIONS])
@pytest.mark.parametrize("verdict", ["yellow", "green"])
def test_the_fallback_row_earns_no_ticket_under_any_regime(pub, verdict):
    """SYNTHETIC regimes over the retained row: the planner needs an accepted
    review, and the fallback is not one, so no plan is constructed at any
    multiplier. The control swaps in an accepted A+ judgement and the same row
    gets a plan: the gate that held HAE was the reader, not the price."""
    account = plan.Account(**pub["account"])
    regime = {"verdict": verdict, "size_multiplier": {"yellow": 0.5, "green": 1.0}[verdict]}
    row = row_of(pub)
    trades, cut, budget = pipeline.make_plans([row], {}, account, regime, 0, date(2026, 10, 8))
    assert trades == [] and cut == [] and row["plan"] is None
    assert row["evidence"]["gate"]["reason"] == "reader_coverage"
    control = row_of(pub)
    control["claude"] = {**control["claude"], "source": grader.SOURCE_CLAUDE, "grade": "A+", "score": 10.0,
                         "error": None, "reason": "SYNTHETIC accepted judgement for the control"}
    trades, cut, budget = pipeline.make_plans([control], {}, account, regime, 0, date(2026, 10, 8))
    assert control["plan"] is not None
    if pub["account"]["equity"] >= 10000:
        assert control["plan"]["eligible"] and trades == ["HAE"]
