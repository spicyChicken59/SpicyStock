"""The pre-registered ablation (tools/ablation.py), held to its spec, its file
and the code each gate stands on.

The tool's own run reads 55 publications out of git and takes half a
minute. One test runs it over the population the committed file records,
fetching those commits by whole id when the checkout is shallow (CI's), and
holds both committed files to what it writes; when the history is there it
also walks the population from the pinned ref. The rest hold the committed
``ablation.json`` to the tool's encoding, the report to the tool's rendering
of that file (so no figure in it is typed by hand), the spec to its pinned
digest, and each variant's gate and the two re-readings (the light from a
record's own inputs, the grade from its own checks) to the modules they
stand on."""
from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
from datetime import date
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
        assert (f"| {v['admitted']:,} | {v['tickets']:,} | {v['withheld']:,} | {sum(v['not_walked'].values()):,} | "
                f"{v['settled']['n']:,} |") in row
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
    first, newest = (date.fromisoformat(DATA[k]) for k in ("first_session", "newest_session"))
    assert (f"over {DATA['publications']} publications ({DATA['nights']} sessions, "
            f"{first.day} {first:%B} to {newest.day} {newest:%B})" in index)
    assert f"production admits {p['admitted']} rows, {p['settled']['n']} of them settled" in index
    readable = [k for k in ab.VARIANTS if DATA["variants"][k]["readable"]]
    assert f"Only {len(readable)} variants reach {DATA['min_settled_for_a_rate']} settled tickets" in index
    assert all(DATA["variants"][k]["night_bootstrap"]["ci95"][0] < 0 < DATA["variants"][k]["night_bootstrap"]["ci95"][1]
               for k in readable)
    assert "and every one of their night intervals includes zero" in index
    readme = (ROOT / "README.md").read_text()
    assert "ablation.py (" in readme


def test_a_partial_letter_earns_half_its_weight():
    # every letter passed but L and C, each partial: 1.5 * 4 + 2.0 / 2 * 2 = 8.0,
    # an A by the checklist's bands; full weight on a partial would make it 10.0
    row = burst()
    for c in row["quality"]["checks"]:
        if c["letter"] in ("L", "C"):
            c["passed"], c["partial"] = False, True
    assert ab.quality_grade(row["quality"]["checks"], 8, [], quality.WEIGHTS) == "A"
    assert quality.grade_of(8.0, 8, False) == "A" and quality.grade_of(10.0, 8, False) == "A+"


@pytest.mark.parametrize("settled, readable", [(19, False), (20, True), (21, True)])
def test_a_variant_reads_a_rate_from_the_scorecards_own_floor(settled, readable):
    from src import record
    assert record.SCORECARD_MIN_PLANS == 20
    spec = {"cost_bps_per_side": [0, 5, 20], "bootstrap": {"reps": 200, "seed": 7}}
    rows = [{"bucket": "settled", "r": 1.0 if i % 2 else -1.0, "session": f"2026-11-{1 + i % 9:02d}",
             "ticker": f"T{i}", "ticket": {}, "filled": True, "uncertainty": None,
             "cost_r": {"0": 1.0, "5": 0.9, "20": 0.8}} for i in range(settled)]
    out = ab.summary_of(rows, spec)
    assert out["readable"] is readable
    wins = sum(1 for r in rows if r["r"] > 0)
    assert (out["admitted"], out["tickets"], out["withheld"], out["not_walked"]) == (settled, settled, 0, {})
    assert out["win_rate"] == round(wins / settled, 3) and out["settled"]["wins"] == wins


def test_a_summary_counts_its_withheld_unwalked_and_uncertain_rows_and_refuses_one_that_does_not_add_up():
    spec = {"cost_bps_per_side": [0, 5, 20], "bootstrap": {"reps": 50, "seed": 7}}
    base = {"session": "2026-11-02", "r": None, "filled": False, "cost_r": {}, "uncertainty": None}
    rows = [{**base, "ticker": "W", "bucket": so.NO_TICKET, "ticket": None},
            {**base, "ticker": "M", "bucket": "basis_mismatch", "ticket": None},
            {**base, "ticker": "U", "bucket": "uncertain", "ticket": {}, "uncertainty": "trigger_timing"},
            {**base, "ticker": "V", "bucket": "uncertain", "ticket": {}, "uncertainty": None},
            {**base, "ticker": "S", "bucket": "settled", "ticket": {}, "r": -1.0, "filled": True,
             "cost_r": {"0": -1.0, "5": -1.05, "20": -1.2}}]
    out = ab.summary_of(rows, spec)
    assert (out["admitted"], out["tickets"], out["withheld"]) == (5, 3, 1)
    assert out["not_walked"] == {"basis_mismatch": 1}
    assert out["uncertain_by_reason"] == {"trigger_timing": 1, "unnamed": 1}
    assert out["win_rate"] == 0.0 and out["readable"] is False


def test_the_files_figures_add_up_in_every_variant():
    for key, v in DATA["variants"].items():
        assert v["admitted"] == v["tickets"] + v["withheld"] + sum(v["not_walked"].values()), key
        n = v["settled"]["n"]
        assert v["win_rate"] == (round(v["settled"]["wins"] / n, 3) if n else None), key
        assert v["settled"]["wins"] + v["settled"]["losses"] + v["settled"]["breakeven"] == n, key


def test_the_table_prints_no_rate_for_a_variant_under_the_floor():
    text = ab.REPORT.read_text()
    for key in ab.VARIANTS:
        v = DATA["variants"][key]
        cells = [c.strip() for c in next(line for line in text.splitlines()
                                         if line.startswith(f"| `{key}` |")).strip("|").split("|")]
        rates = cells[6:11]
        assert (all(c == "—" for c in rates)) is (not v["readable"]), (key, rates)
        assert f"{sum(v['not_walked'].values()):,}" == cells[4]
        section = text.split(f"**`{key}`**")[1].split("**`")[0]
        assert ("mean R after costs" in section) is v["readable"], key


def test_equal_weights_never_move_a_grade_across_an_admitted_band_by_the_arithmetic_alone():
    """Every pass, partial and fail combination of the six scored letters, at
    each A+ tally: the checklist's weights and equal weights put it in the same
    admitted band, so the variant admits what production admits on any night."""
    from itertools import product
    letters = list(quality.WEIGHTS)
    moved = 0
    for states in product(("pass", "partial", "fail"), repeat=len(letters)):
        checks = [{"letter": l, "passed": s == "pass", "partial": s == "partial"} for l, s in zip(letters, states)]
        for a_plus in (3, 4, 8):
            if ab.admitted_band(ab.quality_grade(checks, a_plus, [], quality.WEIGHTS)) != \
                    ab.admitted_band(ab.quality_grade(checks, a_plus, [], ab.EQUAL_WEIGHTS)):
                moved += 1
    assert moved == 0 == DATA["grades_read_again"]["admitted_band_changes_by_equal_weights"]
    assert DATA["grades_read_again"]["changed_by_equal_weights"] > 0
    assert "moves only grades no light admits" in ab.REPORT.read_text()


def test_a_grade_the_checklists_own_weights_do_not_reproduce_refuses_the_ablation():
    good = burst()
    assert ab.regrade([good])[1:] == (1, 0)
    with pytest.raises(ab.AblationError, match="reproduce 1 of 2 recorded grades"):
        ab.regrade([good, {**burst(), "grade_mechanical": "C"}])
    assert ab.regrade([{**burst(), "vetoes": ["L"], "grade_mechanical": "C"}])[1:] == (0, 0)


def _present(commit: str) -> bool:
    return subprocess.run(["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=ROOT, capture_output=True).returncode == 0


def test_the_committed_ablation_is_what_the_tool_writes_over_its_recorded_population():
    """The tool run again, as CI's fixture checks run their generators: a change
    to admits(), the study, the gates or the modules they read moves this.
    A shallow checkout carries only its tip, so the recorded commits are fetched
    by whole id, exactly those and once; when they cannot be had this fails
    with the reason and is never skipped."""
    population = DATA["population"]
    assert len(population) == DATA["publications"] and all(len(e["commit"]) == 40 for e in population)
    missing = [e["commit"] for e in population if not _present(e["commit"])]
    if missing:
        done = subprocess.run(["git", "fetch", "--quiet", "--no-tags", "--depth=1", "origin", *missing],
                              cwd=ROOT, capture_output=True, text=True)
        assert done.returncode == 0 and all(_present(c) for c in missing), \
            f"{len(missing)} commits the ablation records are not in this checkout and could not be fetched: {done.stderr.strip()}"
    shallow = subprocess.run(["git", "rev-parse", "--is-shallow-repository"], cwd=ROOT,
                             capture_output=True, text=True).stdout.strip() == "true"
    result = ab.build(population)
    assert ab.encoded(result) == ab.OUT.read_text()
    assert ab.render(result) == ab.REPORT.read_text()
    if not shallow and _present(SPEC["ref"]):
        from tools import burst_trigger_comparison as cmp
        base = json.loads((ROOT / SPEC["base_spec"]).read_text())
        walked = [{k: e[k] for k in ("commit", "session", "blob")} for e in cmp.population(SPEC["ref"], base)]
        assert walked == population


def test_a_variant_whose_rows_do_not_add_up_is_refused():
    spec = {"cost_bps_per_side": [0, 5, 20], "bootstrap": {"reps": 50, "seed": 7}}
    # a row both ticketed and withheld counts twice: tickets 1 + withheld 1 over 1 admitted
    rows = [{"session": "2026-11-02", "r": None, "filled": False, "cost_r": {}, "uncertainty": None,
             "ticker": "X", "bucket": so.NO_TICKET, "ticket": {}}]
    with pytest.raises(ab.AblationError, match="not its tickets, withheld and unwalked rows"):
        ab.summary_of(rows, spec)


def test_the_admitted_band_tells_a_plus_from_a_and_both_from_the_rest():
    assert [ab.admitted_band(g) for g in ("A+", "A", "B", "C", "skip", None)] == ["A+", "A", None, None, None, None]
    assert set(pipeline.TRADE_GRADES) == {"A+", "A"}
