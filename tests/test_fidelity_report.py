"""The canonical-versus-production comparison, on records built to separate its verdicts.

Every case here is a record the real pipeline could write, and each one is
shaped so that exactly ONE of the report's verdicts is correct for it. A test
whose fixture satisfies two verdicts at once cannot tell them apart, which is
this project's third shape of test that cannot fail.
"""
import json

import pytest

from src.scanner import ScanConfig
from tools import fidelity_report


def canonical_row(ticker, **over):
    """A canonical scan row as src/stockbee.py writes one."""
    row = {"ticker": ticker, "date": "2026-09-09", "close": 50.0, "volume": 1_000_000.0,
           "prev_close": 46.0, "prev_volume": 800_000.0, "gain_pct": 8.7,
           "volume_vs_previous": 1.25, "volume_vs_average": 2.0, "close_position": 0.9}
    row.update(over)
    return row


def run(canonical, production, *, matched=None, gated=(), **over):
    rows = list(canonical)
    entry = {"date": "2026-09-09", "bursts": len(production) + len(gated), "measured": 500,
             "scored": len(production), "score_cap": 25, "top_score": 4.5,
             "universe": {"label": "test basket"},
             "candidates": [{"ticker": t} for t in production],
             "gated": [{"ticker": t} for t in gated],
             "stockbee": {"scan": {"matched": matched if matched is not None else len(rows),
                                   "shown": len(rows), "rows": rows}}}
    entry.update(over)
    return entry


def test_a_name_both_scans_found_is_neither_missed_nor_extra():
    report = fidelity_report.compare(run([canonical_row("AAA")], ["AAA"]))
    assert report["overlap"] == 1
    assert report["missed"] == [] and report["extra"] == []


def test_a_burst_the_gate_refused_still_counts_as_found_by_the_scan():
    """`gated` is where a burst the checklist or a veto turned away lands, and
    it was still FOUND. Reading `candidates` alone would report the gate's
    rejections as scan misses -- two different failures under one number."""
    report = fidelity_report.compare(run([canonical_row("AAA")], [], gated=["AAA"]))
    assert report["missed"] == [], "a gated burst is a scan hit, not a scan miss"
    assert report["overlap"] == 1


def test_a_production_burst_the_canonical_scan_rejects_is_reported_as_extra():
    """The record's real case: volume above the trailing average but NOT above
    the previous session, so `volume > previous volume` refuses it and
    `min_rvol` does not. Day two of a volume event, which is what Bonde's rule
    exists to exclude."""
    report = fidelity_report.compare(run([canonical_row("AAA")], ["AAA", "LATE"]))
    assert report["extra"] == ["LATE"]
    assert report["missed"] == []


@pytest.mark.parametrize("over,expected", [
    ({"volume_vs_average": 1.0}, "rvol_threshold"),
    ({"volume_vs_average": 1.49}, "rvol_threshold"),
    ({"volume_vs_average": 1.5}, "rvol_window"),
    ({"volume_vs_average": 9.0}, "rvol_window"),
    ({"volume_vs_average": None}, "unmeasured"),
    ({"close": 3.5}, "min_price"),
])
def test_each_miss_is_attributed_to_the_first_rule_that_rejects_it(over, expected):
    """The tally is a partition: a name failing several rules is counted once,
    under the first one the scan applies. `rvol_threshold` and `rvol_window`
    are deliberately separate -- one says the bar is too high, the other that
    the 50-session window disagrees with the sidecar's 20 -- and a report that
    merged them would answer neither question."""
    report = fidelity_report.compare(run([canonical_row("AAA", **over)], []))
    assert report["missed"] == ["AAA"]
    assert report["missed_by_rule"] == {expected: 1}


def test_the_price_rule_is_read_off_the_config_and_not_retyped():
    """A name exactly AT `min_price` is refused (`price > min_price`), and a
    hair above it is not. Both sides of the boundary, because a test on one
    side passes with the comparison reversed."""
    cfg = ScanConfig()
    at = fidelity_report.compare(run([canonical_row("AAA", close=cfg.min_price)], []))
    above = fidelity_report.compare(run([canonical_row("AAA", close=cfg.min_price + 0.01)], []))
    assert at["missed_by_rule"] == {"min_price": 1}
    assert above["missed_by_rule"] != {"min_price": 1}


def test_a_truncated_row_list_is_flagged_rather_than_undercounted_in_silence():
    """`stockbee.SCAN_LIMIT` caps the rows written into the record, so on a
    busy night `matched` exceeds what is listed. The misses are then a floor,
    not a count, and the report has to say so -- the 2026-09-08 run in this
    repo's own ledger matched 70 and listed 40."""
    report = fidelity_report.compare(run([canonical_row("AAA")], ["AAA"], matched=70))
    assert report["canonical_truncated"] is True
    assert report["canonical_matched"] == 70 and report["canonical_listed"] == 1


def test_a_run_with_no_sidecar_is_skipped_rather_than_compared_against_nothing():
    """Every run before the sidecar landed has no `stockbee` block. Treating a
    missing block as an empty canonical list would report every burst that
    night as EXTRA."""
    entry = run([], ["AAA"])
    del entry["stockbee"]
    assert fidelity_report.compare(entry) is None


def test_the_report_runs_against_this_repos_own_committed_record(capsys):
    """The record is the input this tool exists for. It must not raise on it,
    and it must actually find the divergence -- an empty report over a ledger
    that has one is the failure mode nothing else here would catch."""
    assert fidelity_report.main([]) == 0
    out = capsys.readouterr().out
    assert "canonical scan matched" in out
    book = json.loads((fidelity_report.LEDGER).read_text())
    if any(isinstance(r.get("stockbee"), dict) for r in book.get("runs") or []):
        assert "in both" in out


# ---------------------------------------------------------------------------
# The call budget. On this record the cap has never bound while the scan it
# feeds was dropping the setups the method is named for, so the report says
# which of the two the record shows rather than leaving a reader to subtract.
# ---------------------------------------------------------------------------

def test_the_unspent_calls_are_the_cap_less_what_was_spent():
    report = fidelity_report.compare(run([canonical_row("AAA")], ["AAA"], scored=6, score_cap=25))
    assert report["unspent_calls"] == 19


@pytest.mark.parametrize("over", [
    {"score_cap": None}, {"scored": None}, {"score_cap": "25"}, {"scored": True},
])
def test_a_run_that_does_not_say_what_its_budget_was_reports_no_unspent_calls(over):
    """None, not zero. A run entry from before the field existed says nothing
    about the budget, and folding that into the total as "nothing unspent"
    would put a fact in the report the record does not hold."""
    report = fidelity_report.compare(run([canonical_row("AAA")], ["AAA"], **over))
    assert report["unspent_calls"] is None


def test_a_budget_that_bound_is_reported_as_the_live_question_it_is(capsys):
    """The opposite verdict, on the only record that can produce it — because
    a report that only ever prints one of its two sentences cannot be shown
    to choose between them."""
    entry = run([canonical_row("AAA")], ["AAA"], scored=25, score_cap=25)
    book = {"runs": [entry]}
    path = pytest.importorskip("pathlib").Path
    import tempfile
    tmp = path(tempfile.mkdtemp()) / "ledger.json"
    tmp.write_text(json.dumps(book))
    assert fidelity_report.main(["--ledger", str(tmp)]) == 0
    out = capsys.readouterr().out
    assert "0 unspent" in out
    assert "ranking what to spend it on is a live question" in out
    assert "not a budget that is too small" not in out


def test_an_idle_budget_says_the_funnel_is_the_constraint(capsys):
    entry = run([canonical_row("AAA"), canonical_row("BBB")], ["AAA"], scored=1, score_cap=25)
    import tempfile
    from pathlib import Path
    tmp = Path(tempfile.mkdtemp()) / "ledger.json"
    tmp.write_text(json.dumps({"runs": [entry]}))
    assert fidelity_report.main(["--ledger", str(tmp)]) == 0
    out = capsys.readouterr().out
    assert "1 of 25 allowed, 24 unspent" in out
    assert "1 canonical 4% match(es)" in out
    assert "not a budget that is too small" in out


def test_the_dollar_breakouts_are_reported_and_none_of_them_was_scored(capsys):
    """Every $ breakout row is by construction a name production never
    scored: the sections are disjoint and production admits only 4% bursts.
    Reported so the idle-budget sentence counts them."""
    entry = run([canonical_row("AAA")], ["AAA"], scored=1, score_cap=25)
    entry["stockbee"]["dollar"] = {"matched": 2, "shown": 2, "rules": {}, "rows": [
        {"ticker": "HIGH", "date": "2026-09-09", "dollar_move": 1.4},
        {"ticker": "PRICY", "date": "2026-09-09", "dollar_move": 0.95}]}
    report = fidelity_report.compare(entry)
    assert report["dollar_listed"] == 2 and report["dollar_names"] == ["HIGH", "PRICY"]
    import tempfile
    from pathlib import Path
    tmp = Path(tempfile.mkdtemp()) / "ledger.json"
    tmp.write_text(json.dumps({"runs": [entry]}))
    fidelity_report.main(["--ledger", str(tmp)])
    out = capsys.readouterr().out
    assert "$ breakout matched 2 that the 4% scan did not, none of them scored" in out
    assert "and 2 $ breakout(s) went unscored" in out


def test_a_record_from_before_the_dollar_scan_reports_none_rather_than_guessing():
    report = fidelity_report.compare(run([canonical_row("AAA")], ["AAA"]))
    assert report["dollar_matched"] is None and report["dollar_listed"] == 0


# ---------------------------------------------------------------------------
# What each cut went on to do. The report's reason for existing: a rule that
# drops most of the canonical matches is a quality filter only if the names it
# drops did worse, and every canonical row carries forward returns now.
# ---------------------------------------------------------------------------

def measured(ticker, d5_open, **over):
    row = canonical_row(ticker, **over)
    row["forward_returns"] = {"d1": 1.0, "d3": 2.0, "d5": d5_open + 1,
                              "as_of": "2026-09-16",
                              "from_open": {"d1": 0.5, "d3": 1.5, "d5": d5_open}}
    return row


@pytest.mark.parametrize("returns", [
    None, "measured", {}, {"from_open": None}, {"from_open": {}},
    {"from_open": {"d5": None}}, {"from_open": {"d5": True}}, {"from_open": {"d5": "4"}},
    {"d5": 9.0},          # the CLOSE basis alone is not the basis this reads
])
def test_a_row_with_no_open_basis_at_the_longest_horizon_is_pending_not_zero(returns):
    """Pending is not a return of nothing. A horizon that has not happened,
    or a row whose entry the fill refused, must not be averaged in as 0."""
    row = canonical_row("AAA")
    if returns is not None:
        row["forward_returns"] = returns
    assert fidelity_report._longest_return(row) is None


def test_the_return_is_read_at_the_longest_horizon_on_the_open_basis():
    from src import ledger
    row = measured("AAA", 7.5)
    assert fidelity_report._longest_return(row) == 7.5
    assert max(ledger.HORIZONS) == fidelity_report._longest_horizon()


def test_each_miss_carries_its_outcome_under_the_rule_that_dropped_it():
    report = fidelity_report.compare(run(
        [measured("KEPT", 6.0), measured("THIN", 1.0, volume_vs_average=1.2),
         measured("CHEAP", -2.0, close=2.0)],
        ["KEPT"]))
    assert report["kept_returns"] == [6.0]
    assert report["missed_returns_by_rule"] == {"rvol_threshold": [1.0], "min_price": [-2.0]}


def test_a_group_under_the_minimum_prints_its_count_and_refuses_a_rate(capsys):
    import tempfile
    from pathlib import Path
    entry = run([measured("KEPT", 6.0), measured("THIN", 1.0, volume_vs_average=1.2)], ["KEPT"])
    tmp = Path(tempfile.mkdtemp()) / "ledger.json"
    tmp.write_text(json.dumps({"runs": [entry]}))
    assert fidelity_report.main(["--ledger", str(tmp)]) == 0
    out = capsys.readouterr().out
    assert "1 measured — too few to read as a rate (this report wants 30)" in out
    assert "No verdict yet" in out
    assert "+1.00% over" not in out


def test_both_sides_over_the_minimum_print_their_means_and_the_caveat(capsys):
    import tempfile
    from pathlib import Path
    kept = [measured(f"K{i}", 6.0) for i in range(3)]
    thin = [measured(f"T{i}", 1.0, volume_vs_average=1.2) for i in range(3)]
    tmp = Path(tempfile.mkdtemp()) / "ledger.json"
    tmp.write_text(json.dumps({"runs": [run(kept + thin, [r["ticker"] for r in kept])]}))
    assert fidelity_report.main(["--ledger", str(tmp), "--min-setups", "3"]) == 0
    out = capsys.readouterr().out
    assert "kept by production     +6.00% over 3 setups" in out
    assert "rvol_threshold         +1.00% over 3 setups" in out
    assert "overlapping bursts are not independent draws" in out
    assert "No verdict yet" not in out


def test_the_section_prints_even_when_nothing_is_measured_yet(capsys):
    """The committed record is in exactly this state, and a reader who sees
    nothing cannot tell "not filled yet" from "this report does not ask"."""
    import tempfile
    from pathlib import Path
    tmp = Path(tempfile.mkdtemp()) / "ledger.json"
    tmp.write_text(json.dumps({"runs": [run(
        [canonical_row("KEPT"), canonical_row("THIN", volume_vs_average=1.2)], ["KEPT"])]}))
    assert fidelity_report.main(["--ledger", str(tmp)]) == 0
    out = capsys.readouterr().out
    assert "What each cut went on to do" in out
    assert "kept by production     nothing measured yet" in out
    assert "rvol_threshold         nothing measured yet" in out
