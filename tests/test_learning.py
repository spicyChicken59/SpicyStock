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


# ---------------------------------------------------------------------------
# The post-merge audit of round 14: a fit is split by what PRODUCED its rows,
# and the research sidecar produces none of them.

def _scored_history(sessions=16, rules=None):
    """One distinct name per session, so every run is its own setup chain.

    Chaining is what hid the size of this: a record whose every session holds
    the same ticker collapses to ONE observation, and the corpus can be
    thrown away without the count moving.
    """
    return [run(offset, [row(offset, ticker="N%02d" % offset)],
                universe=adaptive(), rules=dict(rules or {"score.prompt": "test-prompt", "gate": 3}))
            for offset in range(sessions)]


def test_a_research_constant_moving_does_not_throw_away_the_training_set():
    """Reproduced on the merged tree before this was narrowed: with one name
    per session over sixteen sessions, moving `stockbee.min_share_volume`
    alone -- on runs whose every score, volume ratio, checklist count and
    outcome was untouched -- took the fit from twelve eligible setups to one,
    the other twelve counted under `different_or_unknown_rules`.

    The fit reads score, volume ratio and checklist passes and labels on the
    open-basis d5. The sidecar supplies none of the four: it runs Bonde's own
    scans over the same frames beside the run and selects, scores and gates
    nothing. So this is a record judged against numbers that did not produce
    it -- the class the sidecar's own validator was fixed for in the same
    round, one module over, introduced by the commit that fixed it.
    """
    settled = {"score.prompt": "test-prompt", "gate": 3, "stockbee.min_share_volume": 100000}
    history_runs = _scored_history(rules=settled)
    baseline = learning.build(history_runs, run(20, rules=dict(settled)))

    moved = dict(settled, **{"stockbee.min_share_volume": 1_000_000})
    after = learning.build(history_runs, run(20, rules=moved))

    assert baseline["counts"]["eligible"] > 1, "precondition: the corpus is worth keeping"
    assert after["counts"]["eligible"] == baseline["counts"]["eligible"]
    assert "different_or_unknown_rules" not in after["counts"]["excluded"]


def test_a_production_constant_moving_still_does():
    """The inverse, and the reason the narrowing is a split and not a
    deletion: a gate that moved really did produce different rows, and a fit
    across the boundary would average two screeners."""
    settled = {"score.prompt": "test-prompt", "gate": 3, "stockbee.min_share_volume": 100000}
    history_runs = _scored_history(rules=settled)
    baseline = learning.build(history_runs, run(20, rules=dict(settled)))

    moved = dict(settled, **{"gate": 4})
    after = learning.build(history_runs, run(20, rules=moved))

    assert after["counts"]["eligible"] < baseline["counts"]["eligible"]
    assert after["counts"]["excluded"]["different_or_unknown_rules"] >= 1


def test_the_scoring_signature_ignores_the_research_keys_and_nothing_else():
    """Two runs differing ONLY in the research half hash the same; two
    differing anywhere in the production half do not. Asserted on the
    signature itself, because `build()` can agree for other reasons."""
    base = {"score.prompt": "test-prompt", "gate": 3, "stockbee.scan_gain_ratio": 1.04}
    same = learning._signature(run(0, rules=dict(base)))
    research = learning._signature(run(0, rules=dict(base, **{"stockbee.scan_gain_ratio": 1.10})))
    gained = learning._signature(run(0, rules=dict(base, **{"stockbee.anticipation.min_price": 3})))
    dropped = learning._signature(run(0, rules={k: v for k, v in base.items()
                                                if not k.startswith("stockbee.")}))
    production = learning._signature(run(0, rules=dict(base, gate=4)))
    model = learning._signature(run(0, rules=dict(base), model="other-model"))

    assert same is not None
    assert research == same, "a research value that moved"
    assert gained == same, "a research key that did not exist before"
    assert dropped == same, "a record from before the research keys were named"
    assert production != same, "a production value that moved"
    assert model != same, "the scorer model is still part of it"


def test_the_research_half_is_derived_from_the_sources_the_fingerprint_walks():
    """A PREFIX with a derived guard, not a hand-kept list.

    This project has repeatedly found a hand-kept copy of a set going stale in
    its own direction, so the classification is checked by rebuilding the
    research keys from the same sources `rules_fingerprint()` reads for them
    -- src.stockbee's own STRATEGY_CONSTANTS and the numbers its
    ANTICIPATION_RULES states. A key family added later cannot arrive
    unclassified: it would be in the fingerprint, absent from this
    reconstruction, and this assertion names it.
    """
    from src import pipeline, stockbee

    fingerprint = pipeline.rules_fingerprint()
    expected = {"stockbee.%s" % name.lower() for name in stockbee.STRATEGY_CONSTANTS}
    expected |= {"stockbee.anticipation.%s" % key
                 for key, value in stockbee.ANTICIPATION_RULES.items()
                 if isinstance(value, (int, float)) and not isinstance(value, bool)}
    assert expected, "the sidecar contributes no keys, so this guard proves nothing"

    removed = set(fingerprint) - set(pipeline.production_rules(fingerprint))
    assert removed == expected, (
        "production_rules() removes %s; the sidecar's own sources contribute %s"
        % (sorted(removed), sorted(expected)))
    kept = set(pipeline.production_rules(fingerprint))
    assert kept == set(fingerprint) - expected
    assert not any(name.startswith(pipeline.RESEARCH_PREFIXES) for name in kept)


def test_no_fingerprint_key_family_can_arrive_unclassified():
    """The second guard, and the one the first cannot be: a family nobody
    classified defaults to production and splits the corpus silently.

    A safe default is still a default. This is the shape ScanConfig keeps for
    its own fields and src.stockbee for its constants -- every key matches
    exactly one prefix across the two tuples, so a family added later is red
    until someone says which it is.
    """
    from src import pipeline

    production = set(pipeline.PRODUCTION_PREFIXES)
    research = set(pipeline.RESEARCH_PREFIXES)
    assert production and research
    assert not (production & research), sorted(production & research)

    fingerprint = pipeline.rules_fingerprint()
    for name in fingerprint:
        matched = [prefix for prefix in production | research if name.startswith(prefix)]
        assert len(matched) == 1, (
            "%r matches %s; every fingerprint key must match exactly one prefix "
            "in PRODUCTION_PREFIXES or RESEARCH_PREFIXES" % (name, sorted(matched)))

    # And every prefix earns its place, so a family deleted from the
    # fingerprint does not leave a tuple entry behind claiming to cover it.
    for prefix in production | research:
        assert any(name.startswith(prefix) for name in fingerprint), (
            "%r classifies no key the fingerprint emits" % prefix)


def test_evidence_rules_still_reads_every_key_including_the_research_half():
    """The narrowing is the learning fit's alone. `evidence.rules` asks the
    wider question -- does this record span more than one screener -- and
    evidence.stockbee averages the sidecar's own rows across runs, so a moved
    sidecar threshold there IS two scans and must still show."""
    base = {"score.prompt": "p", "gate": 3, "stockbee.min_share_volume": 100000}
    moved = dict(base, **{"stockbee.min_share_volume": 1_000_000})
    entries = [{"date": "2026-09-08", "type": "evening", "rules": dict(base)},
               {"date": "2026-09-09", "type": "evening", "rules": dict(moved)}]
    view = ledger.rules_view(entries)
    assert view["sets"] == 2, "the record spans two screeners for the sidecar's purposes"
    assert "stockbee.min_share_volume" in view["differ"]
