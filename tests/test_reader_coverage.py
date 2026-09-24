"""Synthetic coverage/regime controls and real offline pipeline integration."""
from collections import Counter
from copy import deepcopy
import json

import pytest

from src import pipeline, plan, reader_coverage, report
from tests.test_pipeline import market, claude, evening, a_plus_frame
from tests.test_reader_coverage_retained import retained, replay


@pytest.mark.parametrize("verdict,grade,permitted", [
    ("green", "A+", True), ("green", "A", True), ("green", "B", False),
    ("yellow", "A+", True), ("yellow", "A", False), ("red", "A+", False)])
@pytest.mark.parametrize("source", ["claude", "fallback", "not_graded", None, "unrecognized"])
def test_synthetic_reader_states_and_market_permission_are_separate(verdict, grade, permitted, source):
    row = deepcopy(next(b for b in retained()["bursts"] if b["ticker"] == "OPY"))
    row["grade"] = row["grade_mechanical"] = grade  # explicitly synthetic grade controls
    row["claude"] = {"source": source, "grade": grade, "error": None} if source else None
    row["reader_coverage"] = reader_coverage.state(row)
    trades, _, _ = pipeline.make_plans([row], {}, plan.Account(),
        {"verdict": verdict, "size_multiplier": 0 if verdict == "red" else 0.5 if verdict == "yellow" else 1}, 0)
    expected = permitted and source == "claude"
    assert bool(row["plan"]) is expected
    assert (row["ticker"] in trades) is expected
    assert row["grade"] == grade


@pytest.mark.parametrize("reader", [None, {"source": "fallback"},
    {"source": "claude", "grade": None}, {"source": "claude", "grade": "A", "error": "unavailable"},
    {"source": "claude", "grade": "B"}])
def test_a_coverage_label_alone_cannot_grant_permission(reader):
    row = next(b for b in retained()["bursts"] if b["ticker"] == "NDSN")
    row.update(claude=reader, reader_coverage="accepted")
    trades, _, _ = pipeline.make_plans([row], {}, plan.Account(), {"verdict": "green"}, 0)
    assert row["plan"] is None and trades == []


def test_pipeline_records_budget_coverage_and_keeps_reader_chart_stops(market, claude, fake_alpaca,
        fake_resend, tmp_path, monkeypatch):
    # 13 identical mechanical A+ inputs, 12 scripted accepted replies. No API.
    symbols = ["AAA"] + [f"A{chr(66 + i)}A" for i in range(12)]
    for ticker in symbols:
        fake_alpaca.add_history(ticker, a_plus_frame())
    stops = {}
    def chart(ticker, frame, *args, **kwargs):
        stops[ticker] = kwargs.get("stop")
        return None
    monkeypatch.setattr(pipeline.charts, "render_chart", chart)
    rep, data, docs = evening(tmp_path, market + symbols[1:])
    assert rep.published, rep.failure
    assert len(claude.calls) == 12
    rows = {b["ticker"]: b for b in data["bursts"]}
    assert set(rows) == set(symbols)
    assert Counter(b["reader_coverage"] for b in rows.values()) == {"accepted": 12, "not_selected_budget": 1}
    skipped = rows[symbols[-1]]
    assert skipped["claude"] is None and skipped["grade"] == skipped["grade_mechanical"] == "A+"
    assert skipped["plan"] is None and skipped["ticker"] not in data["trades"]
    assert skipped["evidence"]["gate"]["reason"] == "reader_coverage"
    assert skipped["evidence"]["reader_coverage"] == "not_selected_budget"
    for ticker, stop in stops.items():
        assert stop == rows[ticker]["plan"]["stop"], "pre-review chart input changed"
    picks = json.loads((docs / "picks.json").read_text())["picks"]
    assert skipped["ticker"] not in {p["ticker"] for p in picks}


def test_coverage_receipt_cannot_be_changed_after_grading(market, claude, fake_resend, tmp_path, monkeypatch):
    read = pipeline.read_charts_and_grade
    def changed(bursts, *args, **kwargs):
        result = read(bursts, *args, **kwargs)
        bursts[0]["reader_coverage"] = "not_selected_budget"
        return result
    monkeypatch.setattr(pipeline, "read_charts_and_grade", changed)
    rep, data, _ = evening(tmp_path, market)
    assert not rep.published and data is None
    assert "reader coverage changed after grading" in rep.failure


def test_publication_refuses_a_preview_plan_that_bypasses_final_coverage(market, claude, fake_resend, tmp_path, monkeypatch):
    claude.set_error(RuntimeError("scripted unavailable reader"))
    def bypass(bursts, frames, account, regime, open_count, session=None):
        return pipeline._make_plans(bursts, account, regime, open_count, session, require_reader=False)
    monkeypatch.setattr(pipeline, "make_plans", bypass)
    rep, data, docs = evening(tmp_path, market)
    assert not rep.published and data is None
    assert "plan requires accepted reader review" in rep.failure
    assert not (docs / "picks.json").exists()


@pytest.mark.parametrize("verdict", ["green", "yellow", "red"])
def test_cover_never_calls_missing_reader_coverage_bad_quality(verdict):
    data, (trades, _, _) = replay(verdict)
    for row in data["bursts"]:
        row["reader_coverage"] = reader_coverage.state(row, selected=row["claude"] is not None)
    data["breadth"]["regime"]["verdict"] = verdict
    veev = next(b for b in data["bursts"] if b["ticker"] == "VEEV")
    assert "accepted reader review missing" in report.miss_reason(veev)
    cover = report.cover(data["run"], data["breadth"], trades, data["bursts"], None)
    if verdict == "red":
        assert cover == retained()["cover"]
    else:
        assert cover["h1"] == "No new burst tickets. Reader review incomplete."
        assert "7 with mechanical A+/A grades lack accepted reader review" in cover["dek"]
        assert "not a measured setup failure" in cover["dek"]
        assert "none A-quality" not in cover["dek"]
