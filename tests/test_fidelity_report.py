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
