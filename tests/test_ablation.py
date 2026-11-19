"""The pre-registered ablation (tools/ablation.py), held to its spec, its file
and the code each gate stands on.

The tool's own run reads 55 publications out of git and takes half a
minute; these tests do not run it. They hold the committed ``ablation.json``
to the tool's encoding, the committed report to the tool's rendering of that
file (so no figure in it is typed by hand), the spec to its pinned digest,
and each variant's gate and the two re-readings (the light from a record's
own inputs, the grade from its own checks) to the modules they stand on."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

import pytest

from src import breadth, pipeline, plan, quality
from tools import ablation as ab
from tools import signal_outcomes as so

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads(ab.OUT.read_text())
SPEC = json.loads(ab.SPEC.read_text())
PAGE = ROOT / "tests" / "fixtures" / "page"


def test_the_spec_is_the_pre_registered_one_and_names_every_variant():
    assert hashlib.sha256(ab.SPEC.read_bytes()).hexdigest() == ab.SPEC_SHA256 == DATA["spec_sha256"]
    assert [v["key"] for v in SPEC["variants"]] == list(ab.VARIANTS) == sorted(DATA["variants"], key=ab.VARIANTS.index)
    assert SPEC["metrics"]["cost_bps_per_side"] == [0, 5, 20] and SPEC["ref"] == DATA["ref"]
    assert "No variant is promoted" in SPEC["reading_rule"]


def test_a_spec_that_is_not_the_pre_registered_one_is_refused(monkeypatch, tmp_path):
    forged = tmp_path / "spec.json"
    forged.write_text(ab.SPEC.read_text().replace("Analysis only.", "Analysis."))
    monkeypatch.setattr(ab, "SPEC", forged)
    with pytest.raises(ab.AblationError, match="pre-registered"):
        ab.load_spec()


def test_the_file_is_the_tools_encoding_and_the_report_is_the_tools_rendering():
    assert ab.OUT.read_text() == ab.encoded(DATA)
    assert ab.REPORT.read_text() == ab.render(DATA)


def test_the_report_prints_each_variants_figures_from_the_file():
    text = ab.REPORT.read_text()
    for key in ab.VARIANTS:
        v = DATA["variants"][key]
        row = next(line for line in text.splitlines() if line.startswith(f"| `{key}` |"))
        assert f"| {v['admitted']:,} | {v['tickets']:,} | {v['withheld']:,} | {v['settled']['n']:,} |" in row
        assert (v["readable"] is False) == (" Under the floor: no rate is read." in text.split(f"**`{key}`**")[1].split("**`")[0])
        assert v["readable"] == (v["settled"]["n"] >= DATA["min_settled_for_a_rate"])


def test_the_regime_read_again_gives_every_recorded_light_and_the_grades_their_recorded_band():
    assert DATA["regime_read_again"]["agree"] == DATA["regime_read_again"]["nights"] == DATA["nights"]
    assert DATA["grades_read_again"]["reproduced"] == DATA["grades_read_again"]["rows"]


# ---------------------------------------------------------------- the gates --
def regime_of(name: str) -> dict:
    data = json.loads((PAGE / f"{name}.json").read_text())
    return data


@pytest.mark.parametrize("name", ["full", "red", "yellow", "next"])
def test_the_five_rules_over_a_records_inputs_give_its_own_light(name):
    data = regime_of(name)
    r = data["breadth"]["regime"]
    assert ab.verdict(r["inputs"], r["thresholds"], data["rules"]["breadth"]) == r["verdict"]


def test_each_rule_fires_alone_and_unscaled_reads_the_archived_raw_counts():
    rules = {"down4_alarm": breadth.DOWN4_ALARM, "up50_month_hot": breadth.UP50_MONTH_HOT}
    thresholds = {"down4_alarm": 100.0, "up50_month_hot": 5.0, "ratio_10d_red": 1.0, "ratio_5d_red": 0.5,
                  "ratio_10d_yellow": 2.0}
    calm = {"down4": 10, "up4": 50, "up50_month": 1, "ratio_10d": 3.0, "ratio_5d": 3.0}
    assert ab.verdict(calm, thresholds, rules) == "green"
    for change, light in (({"down4": 100}, "red"), ({"ratio_10d": 0.9}, "red"),
                          ({"ratio_5d": 0.4, "down4": 60}, "red"), ({"ratio_5d": 0.4}, "green"),
                          ({"ratio_10d": 1.9}, "yellow"), ({"up50_month": 6}, "yellow")):
        assert ab.verdict({**calm, **change}, thresholds, rules) == light, change
    # a count over the scaled alarm and under Bonde's own is red scaled and green unscaled
    assert ab.verdict({**calm, "down4": 150}, thresholds, rules, scaled=False) == "green"
    assert ab.verdict({**calm, "up50_month": 6}, thresholds, rules, scaled=False) == "green"
    assert ab.verdict({**calm, "down4": breadth.DOWN4_ALARM}, thresholds, rules, scaled=False) == "red"
    assert ab.verdict(None, thresholds, rules) is None


def test_the_light_admits_the_pipelines_own_grades():
    assert ab.light_grades("green") == tuple(pipeline.TRADE_GRADES)
    assert ab.light_grades("yellow") == tuple(pipeline.YELLOW_GRADES)
    assert ab.light_grades("yellow", yellow_admits_a=True) == tuple(pipeline.TRADE_GRADES)
    assert ab.light_grades("red") == () == ab.light_grades(None)


def burst(grade="A+", scan="both", vetoes=(), re_vol=True) -> dict:
    checks = [{"letter": letter, "passed": True, "partial": False} for letter in quality.WEIGHTS]
    checks += [{"letter": "RE", "key": "range_expansion", "passed": re_vol, "partial": False, "status": "PASS" if re_vol else "FAIL"},
               {"letter": "VOL", "key": "higher_volume", "passed": re_vol, "partial": False, "status": "PASS" if re_vol else "FAIL"}]
    return {"ticker": "X", "grade_mechanical": grade, "scan": scan, "vetoes": list(vetoes),
            "quality": {"checks": checks, "a_plus_count": 8}}


NIGHT = {"light": "yellow", "unscaled": "green"}


@pytest.mark.parametrize("variant, row, night, admitted", [
    ("production", burst("A+"), NIGHT, True),
    ("production", burst("A"), NIGHT, False),
    ("yellow_admits_a", burst("A"), NIGHT, True),
    ("no_regime_gate", burst("A"), {"light": "red", "unscaled": "red"}, True),
    ("production", burst("A+"), {"light": "red", "unscaled": "red"}, False),
    ("unscaled_thresholds", burst("A"), NIGHT, True),
    ("production", burst("A+", vetoes=["L"]), NIGHT, False),
    ("no_regime_gate", burst("A+", vetoes=["L"]), NIGHT, False),
    ("production", burst("A+", scan="dollar", re_vol=False), NIGHT, False),
    ("admission_off", burst("A+", scan="dollar", re_vol=False), NIGHT, True),
    ("production", burst("A+", scan="dollar", re_vol=True), NIGHT, True),
])
def test_each_variant_changes_its_one_gate(variant, row, night, admitted):
    assert ab.admits(variant, row, night) is admitted


def test_the_checklists_own_weights_give_a_rows_recorded_grade_and_equal_weights_can_move_it():
    data = json.loads((PAGE / "full.json").read_text())
    rows = [b for b in data["bursts"] if not b.get("vetoes") and isinstance(b.get("quality"), dict)]
    assert rows and all(ab.quality_grade(b["quality"]["checks"], b["quality"]["a_plus_count"], b["vetoes"],
                                         quality.WEIGHTS) == b["grade_mechanical"] for b in rows)
    # L and C failed, the four 1.5-point letters passed: 6.0 by the checklist, 6.67 equally
    row = burst()
    for c in row["quality"]["checks"]:
        if c["letter"] in ("L", "C"):
            c["passed"] = False
    assert ab.quality_grade(row["quality"]["checks"], 8, [], quality.WEIGHTS) == "C"
    assert ab.equal_weight_grade(row) == "B"
    assert ab.admits("equal_checklist_weights", {**row, "grade_mechanical": "C"}, {"light": "green", "unscaled": "green"}) is False
    assert sum(ab.EQUAL_WEIGHTS.values()) == pytest.approx(sum(quality.WEIGHTS.values()), abs=0.001)


def test_the_gate_letters_cap_an_equal_weight_grade_as_they_cap_the_checklists():
    row = burst()
    next(c for c in row["quality"]["checks"] if c["letter"] == "H")["passed"] = False
    next(c for c in row["quality"]["checks"] if c["letter"] == "H")["partial"] = True
    assert ab.equal_weight_grade(row) == quality.GATE_CAP


def test_the_low_only_ticket_withholds_a_ticket_whose_stop_fell_to_the_midpoint():
    def production(row, account):
        return ({"stop_basis": row["basis"]}, None, None)

    ticket = ab.low_only_ticket(production)
    assert ticket({"basis": "burst_low"}, None) == ({"stop_basis": "burst_low"}, None, None)
    assert ticket({"basis": "half_range"}, None) == (None, so.NO_TICKET, ab.LOW_ONLY_REASON)
    # and on a real bar: a low under the 4% line at the limit, a midpoint inside it
    account = plan.Account(equity=30000, risk_pct=0.5, max_position_pct=25, max_open_positions=4)
    row = {"ticker": "X", "close": 100.0, "low": 94.0, "high": 104.0, "open": 95.0, "prev_close": 95.0,
           "gain_pct": 5.26, "scan": "both", "extension_pct": None}
    from tools import burst_trigger_comparison as cmp
    real = cmp.ticket_under(plan.BURST_TRIGGER_RULE)
    p, _, _ = real(row, account)
    assert p is not None and p["stop_basis"] == "half_range"
    assert ab.low_only_ticket(real)(row, account) == (None, so.NO_TICKET, ab.LOW_ONLY_REASON)


def test_the_index_and_the_readme_name_the_ablation_with_the_files_figures():
    index = " ".join((ROOT / "docs" / "input-truthfulness" / "README.md").read_text().split())
    p = DATA["variants"]["production"]
    assert "[19 November 2026: the pre-registered ablation](2026-11-19-ablation.md)" in index
    assert (f"over {DATA['publications']} publications ({DATA['nights']} sessions, 11 September to 18 November)"
            in index)
    assert f"production admits {p['admitted']} rows, {p['settled']['n']} of them settled" in index
    readable = [k for k in ab.VARIANTS if DATA["variants"][k]["readable"]]
    assert f"Only {len(readable)} variants reach {DATA['min_settled_for_a_rate']} settled tickets" in index
    assert all(DATA["variants"][k]["night_bootstrap"]["ci95"][0] < 0 < DATA["variants"][k]["night_bootstrap"]["ci95"][1]
               for k in readable)
    assert "and every one of their night intervals includes zero" in index
    readme = (ROOT / "README.md").read_text()
    assert "ablation.py (" in readme
