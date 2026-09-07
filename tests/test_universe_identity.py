"""The rescan guard identifies requested symbols, not only their count."""

import json

from src import pipeline
from tests.test_pipeline import _wide_universe, clean, market_clock, open_gate


def test_equal_sized_different_baskets_really_scan_the_requested_symbols(
    fake_alpaca, mocked_boundaries, ohlcv, open_gate, market_clock, tmp_path
):
    names = _wide_universe(fake_alpaca, ohlcv, fresh=6)
    first, second = names[:3], names[3:]
    assert len(first) == len(second) and set(first).isdisjoint(second)
    pipeline.run("evening", dry_run=True, tickers=first)
    paid = len(mocked_boundaries["anthropic"].calls)
    fetched = len(mocked_boundaries["alpaca"].bar_requests)
    assert paid and fetched, "the first basket really reached the scanner and scorer"

    report = pipeline.RunReport()
    rows = pipeline.run("evening", dry_run=True, tickers=second, report=report)

    assert len(mocked_boundaries["alpaca"].bar_requests) > fetched
    assert len(mocked_boundaries["anthropic"].calls) > paid
    assert rows and {row["ticker"] for row in rows} <= set(second)
    assert not any("already published" in error["message"] for error in report.errors)
    assert clean(tmp_path)["run"]["universe"]["tickers"] == sorted(second)


def test_reordering_the_same_basket_keeps_the_published_scan(
    fake_alpaca, mocked_boundaries, ohlcv, open_gate, market_clock, tmp_path
):
    names = _wide_universe(fake_alpaca, ohlcv, fresh=3)
    pipeline.run("evening", dry_run=True, tickers=names)
    before = (tmp_path / "docs" / "data.json").read_bytes()
    fetched = len(mocked_boundaries["alpaca"].bar_requests)
    paid = len(mocked_boundaries["anthropic"].calls)

    report = pipeline.RunReport()
    pipeline.run("evening", dry_run=True, tickers=list(reversed(names)), report=report)

    assert len(mocked_boundaries["alpaca"].bar_requests) == fetched
    assert len(mocked_boundaries["anthropic"].calls) == paid
    assert (tmp_path / "docs" / "data.json").read_bytes() == before
    assert any("already published" in error["message"] for error in report.errors)


def test_an_old_explicit_basket_is_preserved_without_claiming_its_identity(
    fake_alpaca, mocked_boundaries, ohlcv, open_gate, market_clock, tmp_path
):
    names = _wide_universe(fake_alpaca, ohlcv, fresh=6)
    pipeline.run("evening", dry_run=True, tickers=names[:3])
    path = tmp_path / "docs" / "data.json"
    old = json.loads(path.read_text())
    old["run"]["universe"].pop("tickers", None)
    path.write_text(json.dumps(old))
    before = path.read_bytes()
    fetched = len(mocked_boundaries["alpaca"].bar_requests)

    report = pipeline.RunReport()
    pipeline.run("evening", dry_run=True, tickers=names[3:], report=report)

    assert len(mocked_boundaries["alpaca"].bar_requests) == fetched
    assert path.read_bytes() == before
    reason = " ".join(error["message"] for error in report.errors)
    assert "did not record which symbols" in reason
    assert "SCAN_SESSION_DATE" in reason
    assert "same daily bars" not in reason
