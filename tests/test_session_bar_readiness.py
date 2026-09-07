"""A broken current bar cannot certify a quiet session or grade yesterday.

These are real scanner and pipeline runs through the offline boundaries. The
quiet prior session is essential: a prior burst already triggered PR20's
wrong-date candidate guard and hid the missing coverage check.
"""

from datetime import date

import pytest

from src import ledger, pipeline, scanner


@pytest.mark.parametrize("column", ["Open", "High", "Low", "Close", "Volume"])
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_unreadable_current_bars_fail_before_a_quiet_market_can_publish(
    column, bad, fake_alpaca, mocked_boundaries, ohlcv, monkeypatch, tmp_path
):
    names = [f"Q{letter}" for letter in "ABCDEFGHIJKL"]
    for i, name in enumerate(names):
        frame = ohlcv("flat", variant=i)
        assert scanner.detect_setup(frame, scanner.ScanConfig()) is None
        frame.iloc[-1, frame.columns.get_loc(column)] = bad
        fake_alpaca.add_history(name, frame)
    monkeypatch.setenv("SCAN_SESSION_DATE", "2026-09-08")
    report = pipeline.RunReport()

    with pytest.raises(scanner.IncompleteScanError, match="not a quiet market"):
        pipeline.run("evening", dry_run=True, tickers=names, report=report)

    assert report.published is False
    assert not (tmp_path / "docs" / "data.json").exists()
    assert not (tmp_path / "docs" / "ledger.json").exists()
    assert mocked_boundaries["anthropic"].calls == []
    assert mocked_boundaries["resend"].sent == []


def test_partial_invalid_current_bars_degrade_and_preserve_the_readable_burst(
    fake_alpaca, mocked_boundaries, ohlcv, monkeypatch, tmp_path
):
    names = []
    for i, letter in enumerate("ABCDEFGHIJKL"):
        name = f"Q{letter}"
        frame = ohlcv("flat", variant=i)
        if i < 2:
            frame.iloc[-1, frame.columns.get_loc("Volume")] = float("nan")
        fake_alpaca.add_history(name, frame)
        names.append(name)
    fake_alpaca.add_history("BURST", ohlcv("burst", variant=99))
    names.append("BURST")
    monkeypatch.setenv("SCAN_SESSION_DATE", "2026-09-08")
    monkeypatch.setattr(pipeline, "MIN_LYNCH_PASSES", 0)
    report = pipeline.RunReport()

    result = pipeline.run("evening", dry_run=True, tickers=names, report=report)

    assert [row["ticker"] for row in result] == ["BURST"]
    assert report.exit_code == 2
    assert report.published is True
    assert len(mocked_boundaries["anthropic"].calls) == 1
    assert any("2 had unreadable required OHLCV fields" in p["message"] for p in report.errors)
    data, why = ledger.read_snapshot(tmp_path / "docs")
    assert why is None and data["run"]["status"] == "degraded"
    assert data["run"]["bursts"] == 1


def test_all_invalid_current_bars_preserve_the_previous_published_record(
    fake_alpaca, mocked_boundaries, ohlcv, monkeypatch, tmp_path
):
    names = [f"Q{letter}" for letter in "ABCDEFGHIJKL"]
    for i, name in enumerate(names):
        fake_alpaca.add_history(name, ohlcv("flat", variant=i))
    monkeypatch.setenv("SCAN_SESSION_DATE", "2026-09-04")
    pipeline.run("evening", dry_run=True, tickers=names)
    files = [tmp_path / "docs" / name for name in ("data.json", "ledger.json")]
    before = {path: path.read_bytes() for path in files}

    for frame in fake_alpaca.history.values():
        frame.iloc[-1, frame.columns.get_loc("Volume")] = float("nan")
    monkeypatch.setenv("SCAN_SESSION_DATE", "2026-09-08")
    with pytest.raises(scanner.IncompleteScanError, match="not a quiet market"):
        pipeline.run("evening", dry_run=True, tickers=names)

    assert {path: path.read_bytes() for path in files} == before
    assert mocked_boundaries["anthropic"].calls == []


@pytest.mark.parametrize("column", ["Open", "High", "Low"])
def test_the_checklist_never_grades_yesterday_for_a_broken_current_burst(
    column, fake_alpaca, ohlcv
):
    frame = ohlcv("burst")
    assert scanner.detect_setup(frame, scanner.ScanConfig()) is not None
    frame.iloc[-1, frame.columns.get_loc(column)] = float("nan")
    fake_alpaca.add_history("BAD", frame)
    fake_alpaca.add_history("GOOD", ohlcv("burst", variant=2))
    stats = {}

    found = scanner.run_scan(scanner.ScanConfig(session_date=date(2026, 9, 8)),
                             universe=["BAD", "GOOD"], stats=stats)

    assert [candidate.ticker for candidate in found] == ["GOOD"]
    assert list(stats["invalid_bars"]) == ["BAD"]
    assert stats["stale"] == stats["gapped"] == stats["off_session"] == {}


def test_readable_zero_volume_and_zero_range_still_use_the_existing_rules(fake_alpaca, ohlcv):
    quiet = ohlcv("flat")
    quiet.iloc[-1, quiet.columns.get_loc("Volume")] = 0
    burst = ohlcv("burst", variant=2)
    burst.loc[burst.index[-1], ["Open", "High", "Low"]] = burst["Close"].iloc[-1]
    fake_alpaca.add_history("QUIET", quiet)
    fake_alpaca.add_history("BURST", burst)
    stats = {}

    found = scanner.run_scan(scanner.ScanConfig(session_date=date(2026, 9, 8)),
                             universe=["QUIET", "BURST"], stats=stats)

    assert [candidate.ticker for candidate in found] == ["BURST"]
    assert stats["invalid_bars"] == {}


def test_a_readable_burst_still_cannot_escape_the_wrong_session_guard(
    fake_alpaca, ohlcv, monkeypatch
):
    fake_alpaca.add_history("BURST", ohlcv("burst"))
    real = scanner.detect_setup

    def wrong_date(frame, cfg):
        result = real(frame, cfg)
        assert result is not None
        return {**result, "date": "2026-09-04"}

    monkeypatch.setattr(scanner, "detect_setup", wrong_date)
    stats = {}
    found = scanner.run_scan(scanner.ScanConfig(session_date=date(2026, 9, 8)),
                             universe=["BURST"], stats=stats)

    assert found == []
    assert stats["invalid_bars"] == {}
    assert stats["off_session"] == {"BURST": "2026-09-04"}
