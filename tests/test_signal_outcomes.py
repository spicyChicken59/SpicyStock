"""tools.signal_outcomes: every archived signal ticketed by the production
mechanics and walked over the records' own published bars. The publications
here are synthetic dicts in the records' shape; every expected R is computed by
hand from the scripted bars, and the one real publication read is read only
to prove the git boundary refuses what the spec did not record."""
from __future__ import annotations

import json
import subprocess

import pytest

from src import plan, record
from tools import signal_outcomes as so

ACCOUNT = {"equity": 10000.0, "risk_pct": 0.5, "max_position_pct": 25.0, "max_open_positions": 4}
#: the field guide's textbook bar: plan trigger 124.21, limit 126.47, stop 121.42, 4 shares
TEXTBOOK = {"close": 124.21, "open": 118.96, "high": 124.49, "low": 118.35, "prev_close": 117.18,
            "gain_pct": 6.0, "extension_pct": 3.1, "scan": "burst"}
#: a bar whose low sits 9% under its close: no limit above the buy stop holds a stop, so no ticket
NO_TICKET_BAR = {"close": 100.0, "open": 92.0, "high": 100.5, "low": 91.0, "prev_close": 94.34,
                 "gain_pct": 6.0, "extension_pct": None, "scan": "burst"}
S11, S14, S15, S16, S17, S18, S21 = ("2026-09-11", "2026-09-14", "2026-09-15", "2026-09-16", "2026-09-17",
                                     "2026-09-18", "2026-09-21")
SIGNAL_BAR = {"date": S11, "o": 118.96, "h": 124.49, "l": 118.35, "c": 124.21, "v": 3_000_000}
#: fills at 125.00, sells half at the +8% level 135.00, stopped at the 127.00 open:
#: (2*10.00 + 2*2.00) / (4*3.58) = 1.6760 -> 1.68
WIN = [{"date": S14, "o": 125.0, "h": 127.0, "l": 123.5, "c": 125.8}, {"date": S15, "o": 126.0, "h": 135.5, "l": 125.5, "c": 126.8},
       {"date": S16, "o": 127.0, "h": 128.0, "l": 126.5, "c": 127.5}, {"date": S17, "o": 127.4, "h": 127.9, "l": 127.0, "c": 127.6},
       {"date": S18, "o": 127.5, "h": 127.8, "l": 127.1, "c": 127.4}]
WIN_R = round((2 * (135.0 - 125.0) + 2 * (127.0 - 125.0)) / (4 * (125.0 - 121.42)), 2)
#: per-side cost: 4 shares bought at 125.00, 2 sold at 135.00 and 2 at 127.00
WIN_COST = lambda bps: round(WIN_R - round((4 * 125.0 + 2 * 135.0 + 2 * 127.0) * bps / 10_000 / (4 * (125.0 - 121.42)), 4), 2)  # noqa: E731
#: fills at 124.40, the stop rises to the entry day's 122.00 low, the next low takes it: -2.40/2.98 -> -0.81
LOSS = [{"date": S14, "o": 124.4, "h": 125.0, "l": 122.0, "c": 123.0}, {"date": S15, "o": 122.5, "h": 123.0, "l": 121.0, "c": 121.5}]
LOSS_R = round(4 * (122.0 - 124.4) / (4 * (124.4 - 121.42)), 2)
#: opens under the 124.21 trigger and reaches it: uncertain (trigger_timing). Had it filled AT the
#: trigger: stop -> 122.50 at the close; day 2 sells half at the +8% level 134.15 (over the 126.00
#: open) and raises the stop to 135.75; day 3 opens at 130.00 under it -> stopped at the open:
#: (2*(134.15-124.21) + 2*(130.00-124.21)) / (4*(124.21-121.42)) = 2.819 -> 2.82
UNCERTAIN = [{"date": S14, "o": 123.0, "h": 126.0, "l": 122.5, "c": 125.5}, {"date": S15, "o": 126.0, "h": 136.0, "l": 125.9, "c": 131.0},
             {"date": S16, "o": 130.0, "h": 131.0, "l": 129.5, "c": 130.5}]
BOUND_R = round((2 * (round(124.21 * 1.08, 2) - 124.21) + 2 * (130.0 - 124.21)) / (4 * (124.21 - 121.42)), 2)


def burst(ticker, grade="A+", score=10.0, vetoes=(), bar=TEXTBOOK, accepted=False, final=None):
    return {"ticker": ticker, **bar, "grade_mechanical": grade, "score": score, "vetoes": list(vetoes),
            "grade": final or grade, "reader_coverage": "accepted" if accepted else "not_selected_budget", "series": []}


def observation(history):
    latest = history[-1]
    return {**latest, "v": 1.0, "since": history[0]["date"], "history": [{**h, "v": 1.0} for h in history]}


def publication(session, bursts, observations=None, *, published_at=None, commit=None, regime="red"):
    return {"commit": commit or (session.replace("-", "") + "a" * 32), "blob": "0" * 40, "session": session,
            "data": {"run": {"session": session, "published_at": published_at or f"{session}T22:20:00+00:00"},
                     "account": dict(ACCOUNT), "breadth": {"regime": {"verdict": regime}},
                     "bursts": bursts, "observations": {"symbols": observations or {}}}}


def spec(frozen=S18, costs=(0, 5, 20)):
    return {"schema": so.SPEC_SCHEMA, "frozen_through_session": frozen, "bootstrap": {"reps": 500, "seed": 7},
            "cost_bps_per_side": list(costs), "publications": [], "_sha256": "f" * 64}


def market():
    """Signals on 11 Sep, read against a 18 Sep publication that carries
    their later bars, plus a 21 Sep publication whose signal is confirmatory
    and still pending at the newest session."""
    night = publication(S11, [
        burst("WIN"), burst("LOSS", grade="B", score=6.0), burst("VETO", grade="A", score=8.0, vetoes=["up_days"]),
        burst("NOTIX", bar=NO_TICKET_BAR), burst("UNC", grade="A", score=8.5), burst("BASIS", grade="C", score=4.0),
        burst("GONE", grade="skip", score=2.0),
    ])
    later = publication(S18, [], {
        "WIN": observation([SIGNAL_BAR] + WIN), "LOSS": observation([SIGNAL_BAR] + LOSS),
        "VETO": observation([SIGNAL_BAR] + WIN), "UNC": observation([SIGNAL_BAR] + UNCERTAIN),
        "BASIS": observation([{**SIGNAL_BAR, "c": 120.0}] + WIN),
    })
    newest = publication(S21, [burst("NEWEST", accepted=True)])
    return [night, later, newest]


@pytest.fixture(scope="module")
def result():
    return so.study(market(), spec())


def rows_by(result):
    return {r["ticker"]: r for r in result["rows"]}


# ----------------------------------------------------------------- walks ----
def test_every_row_lands_in_exactly_one_bucket_and_the_strata_partition_the_rows(result):
    rows = rows_by(result)
    assert {t: r["bucket"] for t, r in rows.items()} == {
        "WIN": "settled", "LOSS": "settled", "VETO": "settled", "NOTIX": so.NO_TICKET, "UNC": record.UNCERTAIN,
        "BASIS": so.BASIS_MISMATCH, "GONE": "unmeasured", "NEWEST": "pending"}
    assert {t: r["stratum"] for t, r in rows.items()} == {
        "WIN": so.ADMITTED, "LOSS": "B", "VETO": so.VETOED, "NOTIX": so.ADMITTED, "UNC": so.ADMITTED,
        "BASIS": "C", "GONE": "skip", "NEWEST": so.ADMITTED}
    strata = result["summary"]["strata"]
    assert sum(v["rows"] for v in strata.values()) == result["summary"]["all"]["rows"] == 8
    assert sum(result["summary"]["all"]["buckets"].values()) == 8


def test_the_ticket_is_the_production_plan_and_the_walk_is_the_records(result):
    rows = rows_by(result)
    assert rows["WIN"]["ticket"] == {"entry_ref": 124.21, "entry_low": 121.73, "entry_high": 126.47, "limit": 126.47,
                                     "stop": 121.42, "shares": 4, "day2_spent_above": 129.18}
    assert rows["WIN"]["r"] == WIN_R == 1.68 and rows["WIN"]["status"] == "stopped"
    assert rows["LOSS"]["r"] == LOSS_R == -0.81 and rows["LOSS"]["stratum"] == "B"
    assert rows["VETO"]["r"] == WIN_R, "a vetoed row is ticketed the same way, as the control it is"
    assert rows["NOTIX"]["reason"].startswith("ticket withheld")
    assert "120.0" in rows["BASIS"]["reason"] and rows["BASIS"]["ticket"] is None
    untied = so.study([publication(S11, [burst("WIN")]), publication(S18, [], {"WIN": observation(WIN)})], spec())
    assert untied["rows"][0]["bucket"] == so.BASIS_MISMATCH and "not among them" in untied["rows"][0]["reason"]


def test_costs_are_charged_per_side_on_the_fill_and_every_sale(result):
    win = rows_by(result)["WIN"]
    assert win["cost_r"] == {"0": WIN_R, "5": WIN_COST(5), "20": WIN_COST(20)}
    assert WIN_COST(5) == 1.64 and WIN_COST(20) == 1.54
    costs = result["summary"]["strata"][so.ADMITTED]["costs_per_side_bps"]
    assert costs["0"]["mean_r"] == WIN_R and costs["20"]["mean_r"] == WIN_COST(20)


def test_an_uncertain_day_is_scored_nowhere_and_bounded_by_a_labelled_walk_from_the_trigger(result):
    unc = rows_by(result)["UNC"]
    assert unc["bucket"] == record.UNCERTAIN and unc["uncertainty"] == "trigger_timing" and unc["r"] is None
    assert unc["bound_r"] == BOUND_R == 2.82
    admitted = result["summary"]["strata"][so.ADMITTED]
    assert admitted["settled"]["n"] == 1 and admitted["settled"]["sum_r"] == WIN_R
    assert admitted["uncertain_bound"] == {"uncertain": 1, "bounded": 1, "sum_r_if_filled_at_trigger": BOUND_R,
                                           "pooled_mean_r_with_bound": round((WIN_R + BOUND_R) / 2, 3)}


def test_the_scorecards_own_denominators_and_no_rate_under_its_minimum(result):
    sc = result["summary"]["all"]["scorecard"]
    assert sc["plans"] == 6 and sc["settled"] == 3 and sc["uncertain"] == 1 and sc["pending"] == 1 and sc["unmeasured"] == 1
    assert sc["wins"] == 2 and sc["losses"] == 1 and sc["sum_r"] == round(WIN_R + WIN_R + LOSS_R, 2)
    assert sc["readable"] is False and sc["win_rate"] is None and sc["min_read"] == record.SCORECARD_MIN_PLANS


def test_nights_are_the_unit_and_one_night_has_no_interval(result):
    admitted = result["summary"]["strata"][so.ADMITTED]
    assert admitted["by_night"] == {S11: {"settled": 1, "rows": 3, "mean_r": WIN_R}}, "WIN, NOTIX and UNC on 11 Sep"
    assert admitted["night_bootstrap"] is None
    two = so.bootstrap_nights({S11: 1.0, S14: 3.0}, reps=200, seed=1)
    assert two["nights"] == 2 and two["mean_of_night_means"] == 2.0
    assert two["ci95"][0] >= 1.0 and two["ci95"][1] <= 3.0 and two["ci95"][0] < two["ci95"][1]


def test_phases_split_at_the_freeze_and_the_readers_own_admissions_are_a_stratum(result):
    rows = rows_by(result)
    assert rows["WIN"]["phase"] == "exploratory" and rows["NEWEST"]["phase"] == "confirmatory"
    assert result["summary"]["phases"]["confirmatory"]["rows"] == 1
    assert result["summary"]["phases"]["confirmatory"]["buckets"]["pending"] == 1
    assert result["summary"]["reader_accepted"]["rows"] == 1


# ------------------------------------------------------------------ bars ----
def test_the_newest_publication_wins_a_bar_and_the_change_is_a_counted_revision():
    early = publication(S16, [], {"WIN": observation([SIGNAL_BAR, {**WIN[0], "c": 125.7}])})
    late = publication(S17, [], {"WIN": observation([SIGNAL_BAR] + WIN[:2])})
    bars, revisions = so.gather_bars([late, early])
    assert bars["WIN"][S14]["c"] == 125.8
    assert len(revisions) == 1 and revisions[0]["earlier"]["c"] == 125.7 and revisions[0]["later"]["c"] == 125.8
    assert revisions[0]["later_publication"] == late["commit"][:8]
    same = so.gather_bars([early, publication(S17, [], {"WIN": observation([SIGNAL_BAR, WIN[0] | {"c": 125.7}])})])
    assert same[1] == [], "an equal bar is not a revision"


def test_a_re_publication_of_a_night_adds_bars_but_no_signal():
    first = publication(S11, [burst("WIN")], published_at=f"{S11}T21:08:00+00:00")
    again = publication(S11, [burst("WIN"), burst("XTRA")], {"WIN": observation([SIGNAL_BAR] + WIN)},
                        published_at=f"{S11}T22:22:00+00:00", commit="b" * 40)
    out = so.study([again, first, publication(S18, [])], spec())
    assert [r["ticker"] for r in out["rows"]] == ["WIN"]
    assert out["rows"][0]["publication"] == first["commit"][:8] and out["rows"][0]["r"] == WIN_R
    assert [p["first"] for p in out["publications"]] == [False, True, True]


def test_the_horizon_is_the_scorecards_and_a_later_hole_cannot_erase_a_result():
    bars = {b["date"]: b for b in [SIGNAL_BAR] + WIN}
    pick = {"ticker": "WIN", "date": S11, "kind": "burst", "entry_ref": 124.21, "entry_low": 121.73,
            "entry_high": 126.47, "stop": 121.42, "shares": 4, "targets": None}
    row, walk = so.walk_signal(pick, bars, "2026-10-01")
    assert row["bucket"] == "settled" and row["r"] == WIN_R and walk["status"] == "stopped"
    open_row, _ = so.walk_signal(pick, {d: b for d, b in bars.items() if d <= S14}, S14)
    assert open_row["bucket"] == "open"
    hole, _ = so.walk_signal(pick, {d: b for d, b in bars.items() if d != S15}, "2026-10-01")
    assert hole["bucket"] == record.UNREADABLE


# -------------------------------------------------------------- the spec ----
def test_the_spec_names_what_the_study_reads_and_a_different_blob_is_refused(tmp_path):
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=so.ROOT, capture_output=True, text=True).stdout.strip()
    blob = subprocess.run(["git", "rev-parse", "HEAD:docs/data.json"], cwd=so.ROOT, capture_output=True, text=True).stdout.strip()
    session = json.loads((so.ROOT / "docs" / "data.json").read_text())["run"]["session"]
    good = spec() | {"publications": [{"commit": head, "blob": blob, "session": session}]}
    del good["_sha256"]
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(good))
    loaded = so.load_spec(path)
    assert len(loaded["_sha256"]) == 64
    pubs = so.load_publications(loaded)
    assert len(pubs) == 1 and pubs[0]["session"] == session
    with pytest.raises(so.StudyError, match="the spec recorded"):
        so.load_publications(loaded | {"publications": [{"commit": head, "blob": "1" * 40, "session": session}]})
    with pytest.raises(so.StudyError, match="could not produce"):
        so.load_publications(loaded | {"publications": [{"commit": "0" * 40, "blob": blob, "session": session}]})
    path.write_text(json.dumps(good | {"schema": "other"}))
    with pytest.raises(so.StudyError, match="not a signal-outcomes spec"):
        so.load_spec(path)


def test_the_summary_text_names_the_counterfactual_and_prints_the_hand_numbers(result):
    text = so.summary_text(result)
    assert "no reader, no regime gate, no slot" in text and "not an edge claim" in text
    assert f"sum R {WIN_R}" in text and "settled 1: wins 1 losses 0" in text
    assert "[stratum B]" in text and "[admitted · confirmatory] rows 1" in text


def test_the_cli_writes_both_files_and_refuses_a_bad_spec(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema": "x"}))
    assert so.main(["--spec", str(bad), "--output", str(tmp_path / "out")]) == 2
    assert not (tmp_path / "out").exists()
