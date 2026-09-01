"""End-to-end: the real pipeline.run(), with all three boundaries mocked.

This is the test the old file was trying to be. It runs the actual
orchestrator -- scan, checklist, chart, score, archive -- against in-memory
Alpaca bars, a stubbed Claude and a stubbed Resend, in a temporary working
directory, with no network and no API keys.

What it asserts is wiring, not strategy: that the run completes, that a CSV
lands with the columns the workflow uploads, that the row count matches the
shortlist, and that a dry run does not send mail. The 2LYNCH gate is opened
in most tests so that steps 4 and 7 can move their thresholds without
turning this file into a no-op.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from src import pipeline

ARCHIVE_COLUMNS = [
    "ticker", "date", "close", "gain_pct", "volume_ratio",
    "lynch", "score", "verdict", "reason", "key_risk",
]


@pytest.fixture
def universe(fake_alpaca, ohlcv) -> list[str]:
    """Three symbols: one unmistakable burst, two that cannot be one."""
    fake_alpaca.add_history("BURST", ohlcv("burst"))
    fake_alpaca.add_history("QUIET", ohlcv("flat"))
    fake_alpaca.add_history("WALK", ohlcv("base"))
    return ["BURST", "QUIET", "WALK"]


@pytest.fixture
def open_gate(monkeypatch):
    """Neutralise the 2LYNCH gate for the end-to-end tests.

    The gate's pass/fail arithmetic is step 7's to change. Opening it here
    means the run always reaches the chart, scoring and archive stages, so
    this file keeps testing wiring rather than accidentally testing where
    today's checklist thresholds happen to sit.
    """
    monkeypatch.setattr(pipeline, "MIN_LYNCH_PASSES", 0)


def archived_csv(tmp_path: Path) -> Path:
    files = sorted((tmp_path / "results").glob("*.csv"))
    assert len(files) == 1, f"expected exactly one archive, found {files}"
    return files[0]


# ----------------------------------------------------------- the whole run --


def test_dry_run_completes_and_archives_a_csv(universe, mocked_boundaries, open_gate, tmp_path):
    results = pipeline.run("evening", dry_run=True, tickers=universe)

    assert isinstance(results, list)
    assert results, "the burst symbol should have reached the shortlist"

    path = archived_csv(tmp_path)
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert list(rows[0]) == ARCHIVE_COLUMNS
    assert len(rows) == len(results)
    assert {r["ticker"] for r in rows} == {r["ticker"] for r in results}
    assert "BURST" in {r["ticker"] for r in rows}


def test_dry_run_does_not_send_email(universe, mocked_boundaries, open_gate):
    pipeline.run("evening", dry_run=True, tickers=universe)
    assert mocked_boundaries["resend"].sent == [], "--dry-run must skip delivery"


def test_every_shortlisted_candidate_cost_exactly_one_model_call(
    universe, mocked_boundaries, open_gate
):
    results = pipeline.run("evening", dry_run=True, tickers=universe)
    assert len(mocked_boundaries["anthropic"].calls) == len(results)


def test_a_chart_is_rendered_for_each_scored_candidate(
    universe, mocked_boundaries, open_gate, tmp_path
):
    results = pipeline.run("evening", dry_run=True, tickers=universe)
    charts = sorted(p.stem for p in (tmp_path / "charts").glob("*.png"))
    assert charts == sorted(r["ticker"] for r in results)


def test_the_run_writes_only_inside_the_working_directory(
    universe, mocked_boundaries, open_gate, tmp_path
):
    """archive() and render_chart() both use paths relative to the process
    working directory. That is why the suite chdirs into tmp_path."""
    pipeline.run("evening", dry_run=True, tickers=universe)
    assert Path("results").resolve().is_relative_to(tmp_path)
    assert Path("charts").resolve().is_relative_to(tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["charts", "results"]


def test_live_run_sends_through_the_mocked_transport(universe, mocked_boundaries, open_gate):
    results = pipeline.run("evening", dry_run=False, tickers=universe)

    sent = mocked_boundaries["resend"].sent
    assert len(sent) == 1
    for row in results:
        assert row["ticker"] in sent[0]["html"]


def test_morning_and_evening_both_run(universe, mocked_boundaries, open_gate, tmp_path):
    pipeline.run("morning", dry_run=True, tickers=universe)
    assert archived_csv(tmp_path).name.endswith("_morning.csv")


def test_a_scan_with_no_candidates_still_completes(fake_alpaca, mocked_boundaries, ohlcv, tmp_path):
    fake_alpaca.add_history("QUIET", ohlcv("flat"))
    fake_alpaca.add_history("WALK", ohlcv("base"))

    results = pipeline.run("evening", dry_run=True, tickers=["QUIET", "WALK"])

    assert results == []
    assert mocked_boundaries["anthropic"].calls == []
    with archived_csv(tmp_path).open(newline="") as f:
        assert next(csv.reader(f)) == ARCHIVE_COLUMNS
        assert list(csv.reader(f)) == []


# --------------------------------------------------------------- archiving --


def test_archive_writes_the_documented_columns(tmp_path):
    path = pipeline.archive([], "evening")
    assert path.parent.name == "results"
    with path.open(newline="") as f:
        assert next(csv.reader(f)) == ARCHIVE_COLUMNS


def test_archive_drops_the_columns_the_csv_does_not_carry(tmp_path):
    """score_all() rows also carry lynch_detail and chart; the archive is
    declared with extrasaction='ignore' so those are dropped, not an error."""
    row = {c: c.upper() for c in ARCHIVE_COLUMNS}
    row["lynch_detail"] = ["PASS  a: b"]
    row["chart"] = "charts/AAA.png"

    path = pipeline.archive([row], "evening")
    with path.open(newline="") as f:
        written = list(csv.DictReader(f))

    assert list(written[0]) == ARCHIVE_COLUMNS
    assert written[0]["ticker"] == "TICKER"


def test_archive_names_the_file_by_date_and_run_type(tmp_path):
    evening = pipeline.archive([], "evening")
    morning = pipeline.archive([], "morning")
    assert evening.name.endswith("_evening.csv")
    assert morning.name.endswith("_morning.csv")
    assert evening.name[:10] == morning.name[:10], "both should carry the same UTC date stamp"
