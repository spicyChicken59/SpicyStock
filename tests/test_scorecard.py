"""The public denominator includes plans whose outcome evidence is absent."""
from copy import deepcopy
import json
from pathlib import Path
import pytest

from src import record
from tests.test_record import frame, pick, PICK_DAY, LATER, _scored


def test_missing_and_pending_plans_cannot_disappear_from_the_population():
    rec = record.append(record.empty(), "2026-09-01", [pick(ticker="ABSENT"), pick(ticker="EMPTY")])
    rec = record.append(rec, "2026-09-09", [pick(ticker="NEW")])
    before = deepcopy(rec)
    sc = record.scorecard(rec, {"EMPTY": frame([PICK_DAY])}, "2026-09-09")
    assert sc["plans"] == 3
    assert sc["unmeasured"] == 2 and sc["pending"] == 1
    assert sum(sc[k] for k in record.SCORECARD_BUCKETS) == sc["plans"]
    assert sc["settled"] == 0 and sc["win_rate"] is None
    assert rec == before


def test_stale_open_walk_is_missing_coverage_not_a_current_open_position():
    rec = record.append(record.empty(), "2026-09-01", [pick()])
    frames = {"AAA": frame([PICK_DAY] + LATER[:2])}
    current = record.scorecard(rec, frames, "2026-09-03")
    stale = record.scorecard(rec, frames, "2026-09-09")
    assert current["open"] == 1 and current["unmeasured"] == 0
    assert stale["open"] == 0 and stale["unmeasured"] == 1


def test_resolved_result_does_not_depend_on_bars_after_its_five_session_horizon():
    rec = record.append(record.empty(), "2026-09-01", [pick()])
    frames = {"AAA": frame([PICK_DAY] + LATER + [("2026-09-11", 112, 114, 111, 113)])}
    sc = record.scorecard(rec, frames, "2026-09-14")
    assert sc["settled"] == 1 and sc["unreadable"] == 0
    assert sc["sum_r"] == record.r_multiple(record.replay(pick(), record.later_bars(frames["AAA"], "2026-09-01", "2026-09-09")), 96)


def test_metrics_keep_the_resolved_denominator_and_benchmark_pair_count(monkeypatch):
    sc = _scored(3, 2, monkeypatch, min_read=5)
    assert sc["metric_denominator"] == 5 and sc["benchmark_pairs"] == 5
    assert sc["breakeven"] == 0 and sc["median_r"] > 0
    assert sc["contract_version"] == 2
    small = _scored(3, 2, monkeypatch, min_read=6)
    assert small["median_r"] is None


def test_population_limits_and_missing_metadata_are_explicit(monkeypatch):
    monkeypatch.setattr(record, "MAX_PICKS", 2)
    rec = {"picks": [pick(date="2020-01-02"), pick(ticker="NEW", date="2026-09-09")], "problem": "one malformed pick dropped"}
    sc = record.scorecard(rec, {}, "2026-09-09")
    assert sc["population"]["outside_window"] == 1
    assert sc["population"]["at_capacity"] is True
    assert "malformed" in sc["population"]["problem"]
    assert sc["input_basis"] is None and sc["replay_rules_version"] is None


def test_independent_summary_groups_never_select_a_better_population():
    rec = {"picks": [pick(ticker="A", regime="green"), pick(ticker="B", kind="anticipation", grade="watch", regime="yellow")]}
    rows = record.scorecard_rows(rec, {}, "2026-09-09")
    assert [r["bucket"] for r in rows] == ["unmeasured", "unmeasured"]
    assert record.summarize_scorecard(rows)["plans"] == 2
    assert {r["kind"] for r in rows} == {"burst", "anticipation"}


def test_every_outcome_stays_in_a_reconciling_population(monkeypatch):
    monkeypatch.setattr(record, "SCORECARD_MIN_PLANS", 3)
    rec = {"picks": [pick(ticker=t) for t in ("WIN", "LOSS", "FLAT", "UNCERTAIN", "NOFILL", "HOLE", "MISSING")]
           + [pick(ticker="NEW", date="2026-09-09"), pick(ticker="OPEN", date="2026-09-08")]}
    frames = {
        "WIN": frame([PICK_DAY] + LATER),
        "LOSS": frame([PICK_DAY, ("2026-09-02", 100.5, 101, 95, 96.5)]),
        "FLAT": frame([PICK_DAY, ("2026-09-02", 100.5, 102, 100, 101),
                       ("2026-09-03", 101, 102, 100.2, 101.5), ("2026-09-04", 101, 102, 100.2, 100.5)]),
        "UNCERTAIN": frame([PICK_DAY, ("2026-09-02", 99.5, 101, 99.2, 100.8)]),
        "NOFILL": frame([PICK_DAY, ("2026-09-02", 103, 105, 102.5, 104)]),
        "HOLE": frame([PICK_DAY, LATER[1]]),
        "OPEN": frame([("2026-09-09", 100.5, 103, 100, 102)])}
    sc = record.scorecard(rec, frames, "2026-09-09")
    assert [sc[k] for k in record.SCORECARD_BUCKETS] == [3, 1, 1, 1, 1, 1, 1, 0]
    assert sc["plans"] == 9 and sc["metric_denominator"] == 3
    assert (sc["wins"], sc["losses"], sc["breakeven"]) == (1, 1, 1)
    assert sc["win_rate"] == 0.333 and sc["median_r"] == 0
    assert sc["benchmark_pairs"] == 0 and sc["spy_avg_pct"] is None


def test_ended_without_reconciled_sales_is_never_a_zero_return(monkeypatch):
    monkeypatch.setattr(record, "r_multiple", lambda row, stop: None)
    sc = record.scorecard({"picks": [pick()]}, {"AAA": frame([PICK_DAY] + LATER)}, "2026-09-09")
    assert sc["unscored"] == 1 and sc["settled"] == 0 and sc["breakeven"] == 0
    assert sc["sum_r"] is None


def native_publication():
    from src.pipeline import pick_of
    data = json.loads((Path(__file__).parent / "fixtures/page/full.json").read_text())
    candidate = next(c for c in data["bursts"] if c["ticker"] in data["trades"])
    p = pick_of(candidate["plan"], "burst", candidate["grade"], candidate["score"])
    rec = record.append(record.empty(), data["run"]["session"], [p], data["breadth"]["regime"]["verdict"])
    return data, candidate, deepcopy(rec)


def test_offline_partitions_keep_unknowns_and_require_the_exact_publication():
    from tools.scorecard_analysis import analyze
    data, candidate, rec = native_publication()
    rec["picks"].append(pick(ticker="LEGACY", grade="A+", regime="yellow"))
    result = analyze(rec, {}, "2026-09-11", [data])
    assert result["scorecard"]["plans"] == 2
    for groups in result["partitions"].values():
        assert sum(g["plans"] for g in groups.values()) == 2
    assert result["partitions"]["rules_version"][data["app"]["rules_version"]]["plans"] == 1
    assert result["partitions"]["rules_version"]["unknown"]["plans"] == 1
    assert result["rows"][0]["scan"] == candidate["scan"]
    rec["picks"][0]["evidence_ref"]["id"] = "0" * 64
    unknown = analyze(rec, {}, "2026-09-11", [data])
    assert list(unknown["partitions"]["rules_version"]) == ["unknown"]


def test_offline_analysis_refuses_tampered_attribution():
    from tools.scorecard_analysis import analyze
    data, candidate, rec = native_publication()
    candidate["scan"] = "dollar" if candidate["scan"] != "dollar" else "both"
    with pytest.raises(ValueError, match="integrity failed"):
        analyze(rec, {}, "2026-09-11", [data])


def test_offline_analysis_refuses_regime_mismatch_and_placeholder_history(tmp_path):
    from tools.scorecard_analysis import analyze, main
    data, _, rec = native_publication()
    rec["picks"][0]["regime"] = "yellow"
    with pytest.raises(ValueError, match="attribution disagrees"):
        analyze(rec, {}, "2026-09-11", [data])
    (tmp_path / "picks.json").write_text(json.dumps({"fixture": True, "picks": []}))
    (tmp_path / "frames.json").write_text("{}")
    with pytest.raises(SystemExit) as exc:
        main(["--picks", str(tmp_path / "picks.json"), "--frames", str(tmp_path / "frames.json"), "--session", "2026-09-11"])
    assert exc.value.code == 1


def test_offline_command_uses_the_same_replay_and_writes_only_stdout(tmp_path, capsys):
    from src import provenance
    from tools.scorecard_analysis import main
    rec = {"schema_version": 2, "picks": [pick()]}
    bars = frame([PICK_DAY] + LATER)
    (tmp_path / "picks.json").write_text(json.dumps(rec))
    (tmp_path / "frames.json").write_text(json.dumps({"AAA": provenance.source_object(bars)}))
    assert main(["--picks", str(tmp_path / "picks.json"), "--frames", str(tmp_path / "frames.json"), "--session", "2026-09-09"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["scorecard"] == record.scorecard(rec, {"AAA": bars}, "2026-09-09")
    assert result["rows"][0]["bucket"] == "settled"
    assert result["partitions"]["scan"]["unknown"]["plans"] == 1
    assert sorted(p.name for p in tmp_path.iterdir()) == ["frames.json", "picks.json"]
