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


# ---------------------------------------------------------------------------
# The post-merge audit of round 14: the cap cuts BOTH directions, and one of
# them accuses a name rather than omitting it.

def _truncated(archived_gains, production, *, matched=99):
    """A night whose canonical list stopped at the cap.

    `archived_gains` are the gains of the rows that WERE kept, `production` is
    {ticker: gain} for the bursts production found. Every production name here
    is absent from the canonical rows, which is the state the report has to
    read: on a truncated night that absence has two possible causes and the
    record cannot always tell them apart.
    """
    rows = [canonical_row("K%02d" % i, gain_pct=g) for i, g in enumerate(archived_gains)]
    entry = run(rows, [], matched=matched)
    entry["candidates"] = [{"ticker": t, "gain_pct": g} for t, g in production.items()]
    entry["bursts"] = len(production)
    return entry


def test_a_production_burst_below_the_caps_cutoff_is_not_accused_of_failing_the_scan():
    """Reproduced on the committed record before this was split: on 2026-09-08
    the archived rows stop at a 5.70% gain and all five names the report named
    as "admitted ... that fail the canonical scan" are below it, so the cap
    alone explains every one of them.

    The rows are sorted by gain and cut at stockbee.SCAN_LIMIT, so a canonical
    match under the cutoff is simply not in the file. The report was reading
    that absence as evidence, which is an accusation built on a row nobody
    kept -- and CLAUDE.md published those five names as a finding about the
    scan.
    """
    report = fidelity_report.compare(_truncated([9.0, 8.0, 7.0], {"LOW": 4.5}))
    assert report["canonical_truncated"] is True
    assert report["canonical_cutoff_gain_pct"] == 7.0
    assert report["extra"] == [], "the record cannot say this name fails the scan"
    assert report["extra_unsayable"] == ["LOW"]


def test_a_production_burst_above_the_cutoff_is_still_reported_as_extra():
    """The check is narrowed, not deleted. Above the gain the archived rows
    stop at, a canonical match WOULD have been kept, so its absence is real
    evidence and the report still says so."""
    report = fidelity_report.compare(_truncated([9.0, 8.0, 7.0], {"HIGH": 12.0}))
    assert report["extra"] == ["HIGH"]
    assert report["extra_unsayable"] == []


def test_the_boundary_gain_itself_is_unsayable():
    """Equal gains are broken by ticker, so a name ON the cutoff could have
    been the one the cap dropped. The comparison is strictly-above."""
    report = fidelity_report.compare(_truncated([9.0, 8.0, 7.0], {"EDGE": 7.0}))
    assert report["extra"] == [] and report["extra_unsayable"] == ["EDGE"]


def test_a_production_burst_whose_gain_cannot_be_read_is_not_accused():
    """An accusation needs evidence and this has none, so the silent side is
    where a name with no readable gain goes."""
    entry = _truncated([9.0, 8.0, 7.0], {"AAA": 12.0})
    entry["candidates"] = [{"ticker": "AAA"}, {"ticker": "BBB", "gain_pct": "8"}]
    report = fidelity_report.compare(entry)
    assert report["extra"] == []
    assert report["extra_unsayable"] == ["AAA", "BBB"]


def test_an_untruncated_night_accuses_exactly_as_before():
    """The narrowing applies only where the cap bit. A complete canonical list
    is evidence about every name in the universe, so nothing moves."""
    rows = [canonical_row("KEPT", gain_pct=9.0)]
    entry = run(rows, [])
    entry["candidates"] = [{"ticker": "KEPT", "gain_pct": 9.0}, {"ticker": "EXTRA", "gain_pct": 4.1}]
    entry["bursts"] = 2
    report = fidelity_report.compare(entry)
    assert report["canonical_truncated"] is False
    assert report["canonical_cutoff_gain_pct"] is None
    assert report["extra"] == ["EXTRA"], "a complete list can still accuse a low-gain name"
    assert report["extra_unsayable"] == []


def test_the_committed_records_own_accused_names_are_all_below_its_cutoff(capsys):
    """The reproduction itself, kept as a test so the retraction cannot drift.

    This reads the repository's own docs/ledger.json rather than a fixture,
    because what is being pinned is a fact about the published record: the
    2026-09-08 run archived 40 of 70 matches, and the five names the report
    used to accuse are every one of them under the gain the archive stops at.
    """
    import pathlib

    book = json.loads((pathlib.Path(__file__).resolve().parent.parent
                       / "docs" / "ledger.json").read_text())
    entry = next((r for r in book.get("runs", []) if r.get("date") == "2026-09-08"), None)
    if entry is None or not isinstance(entry.get("stockbee"), dict):
        pytest.skip("the committed record no longer carries that run")
    report = fidelity_report.compare(entry)
    assert report["canonical_truncated"] is True, "precondition: the cap bit that night"
    assert set(report["extra_unsayable"]) >= {"BG", "DK", "EIX", "RGTI", "TKO"}
    assert report["extra"] == [], "none of them is sayable from this record"

    assert fidelity_report.main([]) == 0
    printed = capsys.readouterr().out
    assert "admitted" not in printed.split("2026-09-08")[1].split("scored")[0]
    assert "cannot say for 5 more" in printed


def _outcome_section(book, **flags):
    """Drive the real report over a hand-built ledger and hand back the
    per-rule outcome block a reader sees."""
    import contextlib
    import io
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(book, fh)
        path = fh.name
    buf = io.StringIO()
    argv = ["--ledger", path]
    for key, value in flags.items():
        argv += ["--" + key.replace("_", "-"), str(value)]
    with contextlib.redirect_stdout(buf):
        assert fidelity_report.main(argv) == 0
    printed = buf.getvalue()
    return printed, printed.split("What each cut went on to do")[1].split("Call budget")[0]


def _missed_row(ticker, ratio, d5=None):
    row = canonical_row(ticker, volume_vs_average=ratio)
    if d5 is not None:
        row["forward_returns"] = {"d1": None, "d3": None, "d5": d5, "as_of": "2026-09-16",
                                  "from_open": {"d1": None, "d3": None, "d5": d5}}
    return row


def test_a_rule_whose_misses_are_all_pending_still_gets_a_row():
    """The fallback was `pooled.items() or [...]`, which fires only when NO
    rule has a measured return -- so the moment one did, every rule still
    waiting on its outcomes vanished from a section a reader takes for the
    whole partition. Driven: one rvol_threshold miss with a return beside one
    rvol_window miss without."""
    entry = run([_missed_row("AAA", 1.0, d5=3.0), _missed_row("BBB", 2.0)], [])
    report = fidelity_report.compare(entry)
    assert set(report["missed_by_rule"]) == {"rvol_threshold", "rvol_window"}, "precondition"
    assert "rvol_window" not in report["missed_returns_by_rule"], "precondition: it is pending"

    _all, section = _outcome_section({"runs": [entry]}, min_setups=1)
    assert "rvol_threshold" in section
    assert "rvol_window" in section, "a rule that dropped a name is on no line"
    import re
    assert re.search(r"rvol_window\s+nothing measured yet", section), (
        "the pending rule is listed but says nothing about its state")
    assert re.search(r"rvol_threshold\s+\+3\.00% over 1 setups", section)


def test_a_night_the_canonical_scan_matched_nothing_is_still_reported():
    """It was skipped whole over a zero denominator, so the bursts production
    found on it -- the widest possible disagreement between the two scans,
    every one a name Bonde's scan did not print -- appeared nowhere, and
    neither did its call budget."""
    entry = run([], ["AAA", "BBB"], matched=0)
    entry["bursts"] = 2
    printed, _section = _outcome_section({"runs": [entry]}, min_setups=1)
    assert "2026-09-09" in printed, "the night is not skipped"
    assert "canonical scan matched none" in printed
    assert "production called 2 a burst" in printed
    assert "no overlap to state" in printed, "there is no percentage over a zero denominator"
    assert "admitted 2 that fail the canonical scan" in printed, (
        "an empty canonical list is complete, so it IS evidence about every burst")
    assert "scored" in printed, "and its budget line survives with it"


def test_the_night_tail_is_one_rule_for_both_paths():
    """A night with a canonical list and a night without print the same tail,
    so the two paths cannot drift into two vocabularies."""
    with_list = run([canonical_row("KEPT")], ["KEPT", "EXTRA"])
    with_list["bursts"] = 2
    printed, _ = _outcome_section({"runs": [with_list]}, min_setups=1)
    assert "admitted 1 that fail the canonical scan" in printed
    assert "scored" in printed


def test_a_miss_under_productions_share_floor_is_attributed_to_it():
    """`min_share_volume` arrived in production in round 14 and `_why_missed`
    had no branch for it, so a name production refused for share volume was
    filed under a relative-volume verdict instead.

    It cannot happen while production's floor is at or below the canonical
    scan's own 100,000, because a canonical match cleared that by definition
    -- but the two numbers live in different modules and nothing makes them
    move together, which is exactly why the branch is checked rather than
    assumed. This plants the row that state produces.
    """
    cfg = ScanConfig()
    thin = canonical_row("THIN", volume=float(cfg.min_share_volume - 1), volume_vs_average=9.0)
    report = fidelity_report.compare(run([thin], []))
    assert report["missed"] == ["THIN"]
    assert report["missed_by_rule"] == {"min_share_volume": 1}, (
        "a name refused for share volume must not be filed under a relative-volume verdict")

    fat = canonical_row("FAT", volume=float(cfg.min_share_volume), volume_vs_average=9.0)
    assert fidelity_report.compare(run([fat], []))["missed_by_rule"] == {"rvol_window": 1}, (
        "and the floor is inclusive, so a name exactly on it is not attributed to it")


def test_the_report_states_every_strategy_clause_production_applies(capsys):
    """The stated rule went on describing the scan without `min_share_volume`
    and `min_rvol_sessions` after the same merge added both. It is built from
    ScanConfig's own STRATEGY_FIELDS now, and says so when it falls short."""
    assert fidelity_report.main([]) == 0
    line = next(l for l in capsys.readouterr().out.splitlines()
                if l.startswith("Production rule:"))
    cfg = ScanConfig()
    assert f"{cfg.min_share_volume:,} shares" in line
    assert f"at least {cfg.min_rvol_sessions} sessions" in line
    assert f"{cfg.rvol_lookback}-session average" in line
    assert f"gain >= {cfg.min_gain_pct}%" in line and f"${cfg.min_price}" in line
    assert f"{cfg.min_dollar_volume_pctile:g}th percentile" in line
    assert "does not state" not in line, "a strategy field is unstated and the report admits it"


def test_the_sidecar_volume_window_is_read_off_the_rule_and_not_retyped(monkeypatch):
    """The constant's comment claimed it was read from the rule string and it
    was a hand-typed 20 that nothing referenced. A number the docs quote and
    the code applies have to come from one place."""
    from src import stockbee

    assert fidelity_report.SIDECAR_VOLUME_SESSIONS == fidelity_report._sidecar_volume_sessions()
    assert "previous %d contiguous sessions" % fidelity_report.SIDECAR_VOLUME_SESSIONS in (
        stockbee.MEASUREMENT_RULES["volume_vs_average"])

    # THE CONSTANT ITSELF, not just the function beside it. Comparing the two
    # is 20 against 20 while they agree, so a mutant that types the number
    # back survived it; the module is re-imported under a moved rule string
    # and the constant has to move with it.
    import importlib

    moved_rule = dict(stockbee.MEASUREMENT_RULES)
    moved_rule["volume_vs_average"] = moved_rule["volume_vs_average"].replace(
        "previous 20 contiguous", "previous 35 contiguous")
    monkeypatch.setattr(stockbee, "MEASUREMENT_RULES", moved_rule)
    reloaded = importlib.reload(fidelity_report)
    try:
        assert reloaded.SIDECAR_VOLUME_SESSIONS == 35, (
            "the constant is typed rather than read off the rule it quotes")
    finally:
        monkeypatch.undo()
        importlib.reload(fidelity_report)

    moved = dict(stockbee.MEASUREMENT_RULES)
    moved["volume_vs_average"] = moved["volume_vs_average"].replace(
        "previous 20 contiguous", "previous 35 contiguous")
    monkeypatch.setattr(stockbee, "MEASUREMENT_RULES", moved)
    assert fidelity_report._sidecar_volume_sessions() == 35, "it follows the rule it quotes"

    reworded = dict(stockbee.MEASUREMENT_RULES)
    reworded["volume_vs_average"] = "mean volume over the trailing window"
    monkeypatch.setattr(stockbee, "MEASUREMENT_RULES", reworded)
    with pytest.raises(ValueError):
        fidelity_report._sidecar_volume_sessions()


@pytest.mark.parametrize("book", [
    {"runs": "not a list"}, {"runs": [1, 2]}, {"runs": [None]}, [], "a string", {"no": "runs"},
])
def test_a_file_that_is_not_a_record_is_named_rather_than_traced(book, capsys, tmp_path):
    """This reads a PATH, so it can be handed a quarantined casualty or a
    hand-edited file. A traceback is a worse answer than a sentence.

    Recorded with it: an audit lead claimed run shapes that
    `Ledger._malformed_rows()` loads clean crash this tool. Driven over seven
    of them -- a string, list or missing `universe`, a string `bursts`, a null
    `scored`, a string `score_cap` and `measured`, a list `top_score` -- the
    load check REFUSES every one, so no record this repo writes can hold them
    and the premise does not hold. What is true is the path, which is this.
    """
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps(book))
    assert fidelity_report.main(["--ledger", str(path)]) == 1
    assert "nothing to compare" in capsys.readouterr().err


def test_a_run_whose_universe_is_not_an_object_reads_as_unnamed_rather_than_raising():
    entry = run([canonical_row("AAA")], ["AAA"], universe="a basket")
    assert fidelity_report.compare(entry)["universe"] is None
