"""Chronology and refusal tests for the non-trading calibration layer."""
from copy import deepcopy
from datetime import date
import json
import math

import numpy as np
import pytest

from src import learning, ledger


def day(offset):
    return str(np.busday_offset(date(2025, 1, 2), offset))


def run(offset=100, candidates=None, **changes):
    result = {"date": day(offset), "type": "evening", "status": "ok", "dry_run": False,
              "fixture": False, "model": "test-model", "rules": {"score.prompt": "test-prompt", "gate": 3},
              "universe": {"label": "curated test universe", "size": 228},
              "candidates": candidates or [], "gated": []}
    result.update(changes)
    return result


def row(offset, ticker="AAA", score=7, volume=2, passed=4, outcome=3):
    return {"ticker": ticker, "date": day(offset), "score": score, "volume_ratio": volume,
            "lynch_passes": passed, "lynch_total": 6, "source": "claude",
            "forward_returns": {"d5": 900, "as_of": day(offset + 5), "observed_at": day(offset + 5),
                                "from_open": {"d5": outcome}}}


def history(dates=60, per_day=6, degraded=False):
    rng = np.random.default_rng(721)
    result = []
    for offset in range(dates):
        candidates = []
        for index in range(per_day):
            volume = float(rng.uniform(.5, 12))
            score = float(rng.uniform(3, 10))
            passed = int(rng.integers(3, 7))
            outcome = (score * 2 - 9 if degraded else
                       8 * math.log1p(volume) / math.log(11) + 2 * passed / 6 - 4)
            candidates.append(row(offset, f"S{offset}X{index}", score, volume, passed,
                                  outcome + .04 * math.sin(offset + index)))
        result.append(run(offset, candidates))
    return result


def test_no_real_history_says_collecting_without_invented_returns():
    result = learning.build([], run(), [])
    assert result["status"] == "collecting"
    assert result["counts"]["matured"] == 0
    assert result["requirements"] == {"train_setups": 100, "validation_setups": 30,
                                      "total_dates": 20, "validation_dates": 10}
    assert result["model"] is None and result["validation"] is None
    assert all(item["win_rate_pct"] is None for item in result["calibration"])
    assert result["mode"] == "shadow_only"


@pytest.mark.parametrize("change,why", [
    ({"dry_run": True}, "dry_run_or_unknown"),
    ({"dry_run": None}, "dry_run_or_unknown"),
    ({"fixture": True}, "fixture"),
    ({"fixture": "false"}, "fixture"),
    ({"type": "morning"}, "non_evening_or_degraded"),
    ({"status": "degraded"}, "non_evening_or_degraded"),
    ({"universe": {"tickers": ["AAA"]}}, "named_basket"),
    ({"universe": None}, "unknown_universe"),
    ({"universe": ["AAA"]}, "unknown_universe"),
    ({"model": "other-model"}, "different_or_unknown_rules"),
    ({"rules": {"score.prompt": "test-prompt", "gate": 4}}, "different_or_unknown_rules"),
])
def test_training_excludes_rehearsals_partial_runs_and_changed_scoring(change, why):
    result = learning.build([run(0, [row(0)], **change)], run())
    assert result["counts"]["matured"] == 0
    assert result["counts"]["excluded"][why] == 1


def adaptive(members=("AAA",)):
    """The universe block src.universe stamps on a production evening scan.

    Both keys matter and the shape is the record's own: `tickers` beside a
    `selection` object is what the adaptive selector writes, and `tickers`
    alone is what a --tickers basket writes.
    """
    return {"label": "adaptive US common stocks (Nasdaq + Alpaca)", "size": len(members),
            "tickers": list(members), "identity": "4347617073e5cd47",
            "selection": {"version": "nasdaq-sip-rotation-v1", "mode": "adaptive",
                          "session": "2026-09-09", "selected": len(members)}}


def test_an_adaptive_universe_scan_is_not_read_as_a_named_basket():
    """Every production night since the selector landed carries `tickers`.

    The gate used to exclude any run whose universe block held that key, so
    the record's own clean 500-name scan was training data for nothing. The
    default run() here has no `tickers` at all, which is why no test could
    see it: this one uses the shape a real night writes.
    """
    scan = run(0, [row(0)], universe=adaptive())
    assert learning._eligible_run(scan, date.fromisoformat(day(100))) is None
    result = learning.build([scan], run())
    assert result["counts"]["eligible"] == 1
    assert "named_basket" not in result["counts"]["excluded"]


@pytest.mark.parametrize("universe", [
    None, ["AAA"], "AAA", {}, {"label": "curated test universe", "size": 228},
    {"tickers": ["AAA"]}, {"tickers": []}, {"tickers": "AAA"},
    {"tickers": ["AAA"], "selection": {}}, {"tickers": ["AAA"], "selection": None},
    adaptive(), adaptive(("AAA", "BBB")),
])
def test_the_training_gate_and_the_ledger_read_one_basket_rule(universe):
    """Two copies of this test drifted apart once and the record paid for it.

    The gate may exclude a run for other reasons; what it may never do is
    call a run a named basket that ledger.is_named_basket() calls a scan, or
    the reverse. Asserted over every universe shape either predicate can be
    handed, including the two that are not dicts at all.
    """
    scan = run(0, [row(0)], universe=universe)
    excluded_as_basket = learning._eligible_run(scan, date.fromisoformat(day(100))) == "named_basket"
    assert excluded_as_basket == ledger.is_named_basket(scan)


def test_fixture_document_marker_cannot_be_lost_by_extracting_its_runs():
    result = learning.build({"fixture": True, "runs": history()}, run())
    assert result["counts"]["matured"] == 0
    assert result["counts"]["excluded"]["fixture_document"] == 1
    assert learning.build([], run(fixture=True)) is None


def test_fallback_first_score_is_not_replaced_with_later_claude_score():
    first, second = row(0), row(1)
    first["source"] = "fallback"
    result = learning.build([run(1, [second]), run(0, [first])], run())
    assert result["counts"]["matured"] == 0
    assert result["counts"]["excluded"]["fallback_or_unknown_scorer"] == 1


def test_existing_setup_chain_rule_deduplicates_repeats_and_gated_bridges():
    first, repeated = row(0), row(8)
    bridge = {"ticker": "AAA", "date": day(4), "reason": "lynch_gate"}
    result = learning.build([run(8, [repeated]), run(4, gated=[bridge]), run(0, [first]),
                             run(0, [deepcopy(first)])], run())
    assert result["counts"]["matured"] == 1
    assert sum(item["n"] for item in result["calibration"]) == 1


def test_setup_after_existing_five_session_gap_can_be_a_new_observation():
    result = learning.build([run(0, [row(0)]), run(6, [row(6)])], run())
    assert result["counts"]["matured"] == 2


@pytest.mark.parametrize("value", [None, True, "3", float("nan"), float("inf"), -101])
def test_invalid_and_unmatured_target_never_becomes_a_zero_or_win(value):
    candidate = row(0)
    candidate["forward_returns"]["from_open"]["d5"] = value
    result = learning.build([run(0, [candidate])], run())
    assert result["counts"]["matured"] == 0
    assert result["counts"]["excluded"]["pending_or_invalid_outcome"] == 1


@pytest.mark.parametrize("changes,why", [
    ({"observed_at": None}, "outcome_observation_date_missing"),
    ({"observed_at": "2025-1-09"}, "outcome_observation_date_missing"),
    ({"observed_at": day(101)}, "outcome_not_available_or_invalid_date"),
    ({"observed_at": day(4)}, "outcome_not_available_or_invalid_date"),
    ({"as_of": day(4)}, "outcome_not_available_or_invalid_date"),
    ({"as_of": True}, "outcome_not_available_or_invalid_date"),
])
def test_bar_and_first_observation_dates_are_required_and_available(changes, why):
    candidate = row(0)
    candidate["forward_returns"].update(changes)
    result = learning.build([run(0, [candidate])], run())
    assert result["counts"]["matured"] == 0
    assert result["counts"]["excluded"][why] == 1


def test_calibration_uses_next_open_returns_and_cost_scenario_with_uncertainty():
    candidates = [row(0, "AAA", outcome=.1), row(0, "BBB", outcome=1.1)]
    result = learning.build([run(0, candidates)], run())
    bucket = next(item for item in result["calibration"] if item["n"])
    assert bucket["n"] == 2 and bucket["wins"] == 1
    assert bucket["win_rate_pct"] == 50
    assert bucket["mean_net_return_pct"] == pytest.approx(.4)
    assert bucket["interval_pct"][0] < 10 < 90 < bucket["interval_pct"][1]
    assert result["target"]["round_trip_cost_bps"] == 20
    assert result["status"] == "collecting"


def test_count_threshold_alone_cannot_qualify_one_dense_day():
    result = learning.build(history(dates=1, per_day=200), run())
    assert result["counts"]["matured"] == 200
    assert result["status"] == "collecting" and result["model"] is None


def test_real_regression_learns_predictive_features_and_passes_both_shadow_gates():
    result = learning.build(history(), run())
    assert result["status"] == "qualified"
    assert result["mode"] == "shadow_only"
    assert result["model"]["method"] == "ridge_linear_v1"
    assert result["validation"]["mae_improvement_pct"] > 5
    assert result["validation"]["selection_lift_pct"] > .25
    assert result["validation"]["selection_lift_interval"][0] > 0
    assert len(result["validation"]["folds"]) == 2
    assert all(fold["training_through"] < fold["latest_observed_at"] < fold["validation_from"]
               for fold in result["validation"]["folds"])
    assert result["model"]["label_cutoff"] == result["validation"]["folds"][-1]["validation_from"]
    assert result["counts"]["purged"] == 30
    json.dumps(result, allow_nan=False)


def test_challenger_without_useful_extra_signal_is_refused_promotion():
    result = learning.build(history(degraded=True), run())
    assert result["status"] == "shadow"
    assert result["validation"]["passed"] is False
    assert result["model"] is not None


def test_training_requires_one_hundred_labels_after_purging_overlap():
    result = learning.build(history(dates=30, per_day=6), run())
    assert result["counts"]["matured"] == 180
    assert result["counts"]["train"] == 90
    assert result["counts"]["validation"] == 60
    assert result["counts"]["purged"] == 30
    assert result["status"] == "collecting" and result["model"] is None


def test_final_validation_labels_never_enter_the_published_model():
    runs = history()
    first = learning.build(runs, run())
    cutoff = first["model"]["label_cutoff"]
    for snapshot in runs:
        if snapshot["date"] >= cutoff:
            for candidate in snapshot["candidates"]:
                candidate["forward_returns"]["from_open"]["d5"] = -90
    second = learning.build(runs, run())
    assert first["model"] == second["model"]
    assert first["validation"] != second["validation"]


def test_delayed_label_is_purged_even_when_its_target_bar_predates_validation():
    runs = history()
    baseline = learning.build(runs, run())
    cutoff = baseline["model"]["label_cutoff"]
    runs[0]["candidates"][0]["forward_returns"]["observed_at"] = cutoff
    result = learning.build(runs, run())
    assert result["model"]["training_setups"] == baseline["model"]["training_setups"] - 1
    assert result["model"]["latest_observed_at"] < cutoff


def test_new_matured_history_retrains_and_versions_parameters_without_mutation():
    runs = history(60)
    before = deepcopy(runs)
    initial = learning.build(runs, run())
    updated = learning.build(history(65), run())
    assert runs == before
    assert initial["model"]["version"] != updated["model"]["version"]
    assert initial["model"]["training_through"] < updated["model"]["training_through"]


def test_current_priorities_are_bounded_dated_shadow_predictions_without_reranking_input():
    candidates = [row(100, f"C{i}", volume=i + 1) for i in range(50)]
    before = deepcopy(candidates)
    result = learning.build(history(), run(), candidates)
    assert candidates == before
    assert len(result["priorities"]) == 40
    assert result["priorities"][0]["review_priority"] == 1
    assert all(item["model_version"] == result["model"]["version"] for item in result["priorities"])
    candidates[0]["date"] = day(99)
    candidates[1]["source"] = "fallback"
    small = learning.build(history(), run(), candidates[:2])
    assert small["priorities"] == []


def test_malformed_inputs_fail_closed_without_crashing_or_accepting_bool_features():
    candidate = row(0, score=True)
    result = learning.build([None, "bad", run(0, [candidate]), run(1, candidates="bad")], run())
    assert result["counts"]["matured"] == 0
    assert learning.build([], {"date": True}) is None
    assert learning.build([], {"date": "2025-02-30"}) is None
    assert learning.build([run(0, [row(0, score=10 ** 1000)])], run())["counts"]["matured"] == 0


def test_unknown_rules_and_missing_dry_run_provenance_cannot_train():
    current = run(rules={})
    result = learning.build(history(), current)
    assert result["model"] is None and result["scoring_signature"] is None
    assert "fingerprint" in result["reason"]
    snapshot = run(0, [row(0)])
    del snapshot["dry_run"]
    result = learning.build([snapshot], run())
    assert result["counts"]["matured"] == 0
