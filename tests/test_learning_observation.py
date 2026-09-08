"""The real ledger fill and dashboard preserve first observation provenance."""
from copy import deepcopy
from datetime import date
import json

from src import ledger
from tests.test_ledger import _run, frame_with_opens


def _real_run(session, tickers=("AAA",)):
    run, candidates, gated = _run(session, tickers)
    run.update(rules={"score.prompt": "observation-test"},
               universe={"label": "curated test universe", "size": 228})
    return run, candidates, gated


def _book(tmp_path):
    book = ledger.Ledger(tmp_path).load()
    entry = book.add_run(*_real_run("2026-08-24"))
    return book, entry["candidates"][0]


def _bars():
    return frame_with_opens([100, 101, 102, 103, 104, 110],
                            [99, 100.5, 101, 102, 103, 104], end="2026-08-31")


def test_delayed_fill_records_observation_date_separately_from_target_bar(tmp_path):
    book, candidate = _book(tmp_path)
    moved = book.fill_forward_returns({"AAA": _bars()}, through=date(2026, 9, 4),
                                     observed_on=date(2026, 9, 4))
    assert {item.horizon for item in moved} == {1, 3, 5}
    returns = candidate["forward_returns"]
    assert returns["as_of"] == "2026-08-31"
    assert returns["observed_at"] == "2026-09-04"
    assert returns["from_open"]["d5"] == 9.45
    assert book.latest["candidates"][0]["forward_returns"]["observed_at"] == "2026-09-04"


def test_first_observation_survives_later_fills_and_a_ledger_reload(tmp_path):
    book, candidate = _book(tmp_path)
    book.fill_forward_returns({"AAA": _bars()}, through=date(2026, 9, 4),
                              observed_on=date(2026, 9, 4))
    first = deepcopy(candidate["forward_returns"])
    book.fill_forward_returns({"AAA": _bars()}, through=date(2026, 9, 8),
                              observed_on=date(2026, 9, 8))
    assert candidate["forward_returns"] == first
    book.write()
    restored = ledger.Ledger(tmp_path).load()
    assert restored.load_error is None
    assert restored.runs[0]["candidates"][0]["forward_returns"]["observed_at"] == "2026-09-04"


def test_missing_observation_date_is_not_invented_from_bars_or_a_later_rerun(tmp_path):
    book, candidate = _book(tmp_path)
    book.fill_forward_returns({"AAA": _bars()}, through=date(2026, 9, 4))
    assert candidate["forward_returns"]["from_open"]["d5"] == 9.45
    assert "observed_at" not in candidate["forward_returns"]
    book.fill_forward_returns({"AAA": _bars()}, through=date(2026, 9, 4),
                              observed_on=date(2026, 9, 4))
    assert "observed_at" not in candidate["forward_returns"]


def test_observation_stamp_requires_the_full_open_basis_horizon(tmp_path):
    book, candidate = _book(tmp_path)
    short = _bars().iloc[:4]
    book.fill_forward_returns({"AAA": short}, through=date(2026, 8, 27),
                              observed_on=date(2026, 8, 27))
    assert candidate["forward_returns"]["from_open"]["d3"] == 2.49
    assert candidate["forward_returns"]["from_open"]["d5"] is None
    assert "observed_at" not in candidate["forward_returns"]
    book.fill_forward_returns({"AAA": _bars()}, through=date(2026, 9, 4),
                              observed_on=date(2026, 9, 4))
    assert candidate["forward_returns"]["observed_at"] == "2026-09-04"


def test_a_target_bar_after_the_supplied_observation_day_is_not_stamped(tmp_path):
    book, candidate = _book(tmp_path)
    book.fill_forward_returns({"AAA": _bars()}, through=date(2026, 8, 28),
                              observed_on=date(2026, 8, 28))
    assert candidate["forward_returns"]["as_of"] == "2026-08-31"
    assert "observed_at" not in candidate["forward_returns"]


def test_weekend_observation_is_valid_calendar_provenance_for_a_weekday_setup(tmp_path):
    book, candidate = _book(tmp_path)
    book.fill_forward_returns({"AAA": _bars()}, through=date(2026, 9, 4),
                              observed_on=date(2026, 9, 5))
    assert candidate["forward_returns"]["observed_at"] == "2026-09-05"
    book.add_run(*_real_run("2026-09-08", tickers=()))
    result = book.dashboard()["learning"]
    assert result["counts"]["matured"] == 1
    assert result["counts"]["excluded"].get("outcome_observation_date_missing", 0) == 0


def test_dashboard_computes_learning_from_current_headline_and_persisted_outcomes(tmp_path):
    book, candidate = _book(tmp_path)
    book.fill_forward_returns({"AAA": _bars()}, through=date(2026, 9, 4),
                              observed_on=date(2026, 9, 4))
    book.add_run(*_real_run("2026-09-04", tickers=()))
    headline = deepcopy(book.latest)
    # An older backfill becomes latest internally, but the published headline
    # determines the availability cutoff for the dashboard's learning block.
    book.add_run(*_real_run("2026-08-21", tickers=()))
    result = book.dashboard(headline)
    assert result["learning"]["as_of"] == "2026-09-04"
    assert result["learning"]["counts"]["matured"] == 1
    assert result["learning"]["status"] == "collecting"
    assert "learning" not in result["run"]
    assert all("learning" not in entry for entry in result["runs"])
    book.write(headline)
    saved = json.loads((tmp_path / "data.json").read_text())
    assert saved["learning"] == result["learning"]
    archive = json.loads((tmp_path / "ledger.json").read_text())
    assert "learning" not in archive
    assert any(entry["candidates"] and entry["candidates"][0]["forward_returns"].get("observed_at")
               == "2026-09-04" for entry in archive["runs"])
