"""Discovery cannot weaken security classification, liquidity or run identity."""
from copy import deepcopy
from dataclasses import replace
from datetime import date
import json

import pandas as pd
import pytest
import requests

from src import universe, scanner, ledger, pipeline
from tests.test_pipeline import _wide_universe, market_clock, open_gate


def company(symbol="NEW", **values):
    return {"symbol": symbol, "name": "Example Inc. Common Stock", "country": "United States",
            "sector": "Technology", "industry": "Computer Software", "lastsale": "$20", "volume": "2000000", **values}


def directory_response(status=200, count=500):
    response = requests.Response()
    response.status_code = status
    response._content = json.dumps({"data": {"rows": [company()] * count}}).encode()
    return response


def _check_directory_recovers_after_transient_failures(monkeypatch, failure):
    calls, pauses = [], []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        if len(calls) < 3:
            if isinstance(failure, int):
                return directory_response(failure)
            raise failure("temporary")
        return directory_response()
    monkeypatch.setattr(universe.requests, "get", get)
    monkeypatch.setattr(universe.time, "sleep", pauses.append)
    assert len(universe.fetch_directory()) == 500
    assert len(calls) == 3 and pauses == [1, 3]
    assert all(kwargs["timeout"] == (5, 45) for _, kwargs in calls)
    assert all(set(kwargs["headers"]) == {"User-Agent", "Accept"} for _, kwargs in calls)


def _check_directory_failure_is_bounded_and_never_weakens_classification(monkeypatch, failure):
    calls, pauses = [], []
    def get(*args, **kwargs):
        calls.append(1)
        if failure == "timeout":
            raise requests.ReadTimeout("temporary")
        return directory_response(403 if failure == "refused" else 200, count=2)
    monkeypatch.setattr(universe.requests, "get", get)
    monkeypatch.setattr(universe.time, "sleep", pauses.append)
    expected = {"timeout": requests.ReadTimeout, "refused": requests.HTTPError, "incomplete": ValueError}
    with pytest.raises(expected[failure]):
        universe.fetch_directory()
    assert len(calls) == (3 if failure == "timeout" else 1)
    assert pauses == ([1, 3] if failure == "timeout" else [])


@pytest.mark.parametrize("values", [
    {"name": "Trust Income Fund Common Shares"},
    {"name": "Issuer American Depositary Shares representing common shares"},
    {"name": "Issuer Preferred Common Stock"},
    {"country": "China"}, {"country": ""}, {"industry": ""},
    {"industry": "Biotechnology: Pharmaceutical Preparations"},
    {"sector": "Health Care"}, {"industry": "Blank Checks"}, {"symbol": "BRK.B"},
])
def test_unclassified_or_excluded_securities_cannot_enter(values):
    assert universe.classification(company(**values), set()) is not None
    assert universe.directory_pool([company(**values)], ["AAPL"])[0] == []


def test_common_stock_and_only_curated_pharma_exception_survive():
    assert universe.classification(company(), set()) is None
    assert universe.classification(company("LLY", sector="Health Care"), {"LLY"}) is None
    assert universe.classification(company("MRNA", sector="Health Care"), {"LLY"}) is not None


def frame():
    prices = [20.] * 20 + [21.]
    return pd.DataFrame({"Open": prices, "High": [p + 1 for p in prices], "Low": [p - 1 for p in prices],
                         "Close": prices, "Volume": [2_000_000.] * 21},
                        index=pd.bdate_range(end="2026-09-08", periods=21))


@pytest.mark.parametrize("change", ["low_average", "low_today", "stale", "bad_price", "too_short"])
def test_liquidity_and_freshness_each_block_admission(change):
    f = frame()
    assert universe.measure(f, date(2026, 9, 8)) is not None
    if change == "low_average": f.loc[f.index[:-1], "Volume"] = 100_000
    if change == "low_today": f.loc[f.index[-1], "Volume"] = 100_000
    if change == "stale": f.index = f.index - pd.Timedelta(days=1)
    if change == "bad_price": f.loc[f.index[5], "Close"] = float("inf")
    if change == "too_short": f = f.iloc[1:]
    assert universe.measure(f, date(2026, 9, 8)) is None


def test_rotation_makes_room_for_breakouts_and_recent_setups_and_is_bounded():
    metrics = {f"S{i}": {"gain": .01, "momentum": i / 1000, "liquidity": 30e6 + i,
                          "participation": 1} for i in range(800)}
    metrics["BURST"] = {"gain": .05, "momentum": -.3, "liquidity": 25e6, "participation": 4}
    chosen, reasons = universe.rotate(metrics, date(2026, 9, 8), ["S0"])
    assert len(chosen) == 500 and "BURST" in chosen and "S0" in chosen
    assert reasons["rotating discovery"] == 50 and reasons["4% move"] == 1
    assert universe.rotate(dict(reversed(list(metrics.items()))), date(2026, 9, 8), ["S0"])[0] == chosen
    assert universe.rotate(metrics, date(2026, 9, 9), ["S0"])[0] != chosen


def test_directory_recovery_and_failure_preserve_the_classified_scope(monkeypatch, tmp_path):
    # Exercise transport recovery and final fallback as one directory contract.
    # Each scenario gets isolated patches; every assertion still executes.
    for failure in (requests.ReadTimeout, requests.ConnectionError, 503, 502):
        with monkeypatch.context() as case:
            _check_directory_recovers_after_transient_failures(case, failure)
    for failure in ("timeout", "refused", "incomplete"):
        with monkeypatch.context() as case:
            _check_directory_failure_is_bounded_and_never_weakens_classification(case, failure)
    monkeypatch.setattr(scanner, "get_universe", lambda: ["AAPL", "MSFT"])
    monkeypatch.setattr(universe, "fetch_directory", lambda: (_ for _ in ()).throw(RuntimeError("unavailable")))
    names, report = universe.select(scanner.ScanConfig(), tmp_path)
    assert names == ["AAPL", "MSFT"] and report["mode"] == "fallback"
    assert report["warning"] and report["screened"] == 0


@pytest.mark.parametrize("cfg", [scanner.ScanConfig(feed=scanner.DataFeed.IEX), scanner.ScanConfig(session_date=date(2025, 1, 2))])
def test_current_membership_and_consolidated_floor_are_never_applied_to_wrong_context(monkeypatch, tmp_path, cfg):
    monkeypatch.setattr(scanner, "get_universe", lambda: ["AAPL"])
    monkeypatch.setattr(universe, "fetch_directory", lambda: pytest.fail("directory must not be fetched"))
    names, report = universe.select(cfg, tmp_path)
    assert names == ["AAPL"] and report["mode"] == "fallback"


def test_real_selection_pipeline_records_screened_pool_and_rotation(monkeypatch, tmp_path):
    symbols = ["A" + chr(65 + i // 26) + chr(65 + i % 26) for i in range(120)]
    monkeypatch.setattr(scanner, "get_universe", lambda: ["AAPL"])
    monkeypatch.setattr(scanner, "current_session", lambda: date(2026, 9, 8))
    monkeypatch.setattr(universe, "fetch_directory", lambda: [company(s) for s in symbols])
    requested = []
    def download(client, names, cfg, session):
        requested.extend(names)
        assert cfg.lookback_days == 35 and cfg.feed == scanner.DataFeed.SIP
        return {name: frame() for name in names}
    monkeypatch.setattr(scanner, "_download_batch", download)
    names, report = universe.select(scanner.ScanConfig(), tmp_path, data_client=object())
    assert set(requested) == set(symbols) == set(names)
    assert report["mode"] == "adaptive" and report["eligible"] == report["screened"] == 120
    assert report["removed"] == ["AAPL"] and report["selected"] == 120


def test_adaptive_basket_does_not_become_an_explicit_smoke_test():
    run = {"universe": {"tickers": ["AAPL"], "selection": {"mode": "adaptive"}}}
    assert ledger.is_named_basket(run) is False
    run["universe"].pop("selection")
    assert ledger.is_named_basket(run) is True


def test_adaptive_mode_identity_does_not_reuse_the_old_seed_session(monkeypatch):
    monkeypatch.setenv("SCAN_UNIVERSE", "adaptive")
    monkeypatch.setattr(scanner, "current_session", lambda: date(2026, 9, 8))
    run = {"type": "evening", "date": "2026-09-08", "universe": {"label": pipeline.UNIVERSE_FILE_LABEL}}
    monkeypatch.setattr(ledger, "read_snapshot", lambda _: ({"run": run}, None))
    assert pipeline._already_published(scanner.ScanConfig(), None) is None
    run["universe"]["label"] = universe.LABEL
    assert pipeline._already_published(scanner.ScanConfig(), None) == run


def test_benchmark_fetch_keeps_original_members_even_after_rotation(monkeypatch):
    old = {"date": "2026-09-04", "universe": {"tickers": ["OLD", "KEEP"], "selection": {"mode": "adaptive"}}}
    book = type("Book", (), {"_fill_window": lambda self: [old]})()
    monkeypatch.setattr(scanner, "get_clients", lambda: object())
    calls = []
    def fetch(client, symbols, cfg, session):
        calls.extend(symbols)
        assert cfg.lookback_days == 15
        return {s: frame() for s in symbols}
    monkeypatch.setattr(scanner, "_download_batch", fetch)
    frames = universe.benchmark_history(book, scanner.ScanConfig(), date(2026, 9, 8), {"KEEP": frame(), "NEW": frame()})
    assert calls == ["OLD"] and set(frames) == {"OLD", "KEEP", "NEW"}


def test_unknown_mode_is_an_error(monkeypatch):
    monkeypatch.setenv("SCAN_UNIVERSE", "adpative")
    with pytest.raises(ValueError): universe.enabled()


def test_rotated_benchmark_measures_original_basket_not_new_winners(tmp_path):
    original = {"label": universe.LABEL, "tickers": ["OLD"], "selection": {"mode": "adaptive"}}
    current = {"label": universe.LABEL, "tickers": ["NEW"], "selection": {"mode": "adaptive"}}
    book = ledger.Ledger(tmp_path)
    book.runs = [{"date": "2026-09-04", "type": "evening", "universe": original, "measured": 1}]
    def prices(values):
        return pd.DataFrame({"Open": values, "Close": values, "Volume": [1e7]*len(values)},
                            index=pd.bdate_range(start="2026-09-04", periods=len(values)))
    assert book.fill_benchmarks({"OLD": prices([100, 101, 102, 103, 104, 105]),
                                 "NEW": prices([100, 200, 300, 400, 500, 600])},
                                date(2026, 9, 11), current) == 1
    benchmark = book.runs[0]["benchmark"]
    assert benchmark["d5"] == 5.0 and benchmark["universe"]["tickers"] == ["OLD"]


def test_missing_original_member_leaves_benchmark_pending(tmp_path):
    book = ledger.Ledger(tmp_path)
    original = {"label": universe.LABEL, "tickers": ["MISSING", "KEEP"], "selection": {"mode": "adaptive"}}
    book.runs = [{"date": "2026-09-04", "type": "evening", "universe": original, "measured": 2}]
    assert book.fill_benchmarks({"KEEP": frame()}, date(2026, 9, 8), original) == 0
    assert book.runs[0]["benchmark"]["d1"] is None


def test_discovery_slots_survive_when_all_other_buckets_are_full():
    metrics = {f"S{i}": {"gain": .05 if i < 400 else .01, "momentum": i / 1000,
                          "liquidity": 30e6 + i, "participation": 1} for i in range(1000)}
    names, reasons = universe.rotate(metrics, date(2026, 9, 8), [f"S{i}" for i in range(100)])
    assert len(names) == 500 and reasons["rotating discovery"] == 50
    assert reasons["recent setup"] == 100 and reasons["4% move"] == 150


def test_legacy_seed_benchmark_keeps_a_named_reference_during_transition(tmp_path):
    book = ledger.Ledger(tmp_path)
    book.runs = [{"date": "2026-09-04", "type": "evening", "measured": 1,
                  "universe": {"label": pipeline.UNIVERSE_FILE_LABEL, "size": 1}}]
    old = pd.DataFrame({"Open": [100, 101], "Close": [100, 101], "Volume": [1e7, 1e7]},
                       index=pd.to_datetime(["2026-09-04", "2026-09-08"]))
    current = {"label": universe.LABEL, "selection": {"mode": "adaptive"}}
    assert book.fill_benchmarks({"OLD": old, "NEW": old * 2}, date(2026, 9, 8), current, calendar=[date(2026, 9, 4), date(2026, 9, 8)], legacy_seed=["OLD"]) == 1
    block = book.runs[0]["benchmark"]
    assert block["d1"] == 1 and block["n1"] == 1
    assert block["universe"]["label"] == pipeline.UNIVERSE_FILE_LABEL
    assert "did not record dated membership" in block["membership_note"]


def test_email_opt_out_is_not_a_dry_run_and_suppresses_failure_notices(monkeypatch):
    monkeypatch.setenv("SCAN_SEND_EMAIL", "false")
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("EMAIL_TO", raising=False)
    assert "RESEND_API_KEY" not in pipeline.missing_env(False)
    monkeypatch.setattr(pipeline, "missing_delivery_env", lambda: pytest.fail("failure delivery must not run"))
    pipeline.notify_failure("evening", pipeline.RunReport(), dry_run=False)


def test_no_email_publication_preserves_real_run_identity(fake_alpaca, mocked_boundaries, ohlcv, market_clock, open_gate, monkeypatch, tmp_path):
    monkeypatch.setenv("SCAN_SEND_EMAIL", "false")
    names = _wide_universe(fake_alpaca, ohlcv, fresh=3)
    report = pipeline.RunReport()
    pipeline.run("evening", dry_run=False, tickers=names, report=report)
    snapshot = json.loads((tmp_path / "docs" / "data.json").read_text())
    assert report.published is True and snapshot["run"]["dry_run"] is False
    assert snapshot["run"]["email_delivery"] == "disabled"
    assert mocked_boundaries["resend"].sent == []
