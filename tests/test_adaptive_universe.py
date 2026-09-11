"""Discovery cannot weaken security classification, liquidity or run identity."""
from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import gzip
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
    assert all(kwargs["headers"] == universe.DIRECTORY_HEADERS for _, kwargs in calls)


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


def _check_dated_cache_contract(monkeypatch, tmp_path):
    now = datetime(2026, 9, 9, 1, tzinfo=timezone.utc)
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz else now.replace(tzinfo=None)
    monkeypatch.setattr(universe, "datetime", Clock)
    monkeypatch.setattr(scanner, "current_session", lambda: date(2026, 9, 8))
    monkeypatch.setattr(scanner, "get_universe", lambda: ["AAPL"])
    symbols = ["A" + chr(65 + i // 26) + chr(65 + i % 26) for i in range(120)]
    rows = [company(s) for s in symbols] + [company("MRNA", sector="Health Care")] * 380
    cached = {"schema_version": 1, "source_url": universe.SOURCE_URL,
              "fetched_at": (now - timedelta(days=7)).isoformat(), "rows": rows}
    path = tmp_path / universe.DIRECTORY_CACHE
    def save(value):
        path.write_bytes(gzip.compress(json.dumps(value).encode(), mtime=0))
    save(cached)
    requested = []
    def download(client, names, cfg, session):
        requested.extend(names)
        assert cfg.feed == scanner.DataFeed.SIP and session == date(2026, 9, 8)
        return {symbol: frame() for symbol in names}
    monkeypatch.setattr(scanner, "_download_batch", download)
    failures = [requests.ReadTimeout("provider-detail"), requests.ConnectionError("provider-detail")]
    failures += [requests.HTTPError("provider-detail", response=directory_response(status))
                 for status in (500, 502, 503, 504)]
    for failure in failures:
        def unavailable(failure=failure):
            raise failure
        monkeypatch.setattr(universe, "fetch_directory", unavailable)
        names, report = universe.select(scanner.ScanConfig(), tmp_path, data_client=object())
        assert set(names) == set(symbols), type(failure).__name__
        assert set(requested) == set(symbols) and "MRNA" not in requested
        assert report["mode"] == "adaptive" and report["directory_status"] == "cached"
        assert report["directory_age_days"] == 7 and report["source_date"] is None
        assert report["directory_fetched_at"] == cached["fetched_at"]
        assert "2026-09-02" in report["warning"] and "provider-detail" not in report["warning"]
        assert path.read_bytes() == gzip.compress(json.dumps(cached).encode(), mtime=0), "Using a cache cannot redatestamp it"
    # A valid cache cannot override an explicit refusal or a malformed live payload.
    for failure in [requests.HTTPError("provider-detail", response=directory_response(403)),
                    requests.HTTPError("provider-detail", response=directory_response(429)),
                    ValueError("Invalid live directory")]:
        def unavailable(failure=failure):
            raise failure
        monkeypatch.setattr(universe, "fetch_directory", unavailable)
        names, report = universe.select(scanner.ScanConfig(), tmp_path, data_client=object())
        assert names == ["AAPL"] and report["mode"] == "fallback"
        assert report["directory_status"] is None
    monkeypatch.setattr(universe, "fetch_directory", lambda: (_ for _ in ()).throw(requests.ReadTimeout("provider-detail")))
    bad = []
    for key, value in [("schema_version", 2), ("schema_version", True),
                       ("source_url", "https://example.com/other-directory"),
                       ("fetched_at", (now - timedelta(days=7, microseconds=1)).isoformat()),
                       ("fetched_at", (now + timedelta(seconds=1)).isoformat()),
                       ("fetched_at", now.replace(tzinfo=None).isoformat()),
                       ("fetched_at", now.astimezone(timezone(timedelta(hours=1))).isoformat()),
                       ("fetched_at", "unknown"), ("rows", rows[:499]),
                       ("rows", rows * 21), ("rows", rows[:499] + ["not a row"]),
                       ("rows", rows[:499] + [{"symbol": "MISS"}])]:
        value = dict(cached, **{key: value})
        bad.append(value)
    for value in bad:
        save(value)
        names, report = universe.select(scanner.ScanConfig(), tmp_path, data_client=object())
        assert names == ["AAPL"] and report["mode"] == "fallback"
        assert report["screened"] == 0 and "no valid Nasdaq directory" in report["warning"]
    for raw in [b"invalid gzip", gzip.compress(b"invalid json"), gzip.compress(b" " * (universe.DIRECTORY_MAX_BYTES + 1))]:
        path.write_bytes(raw)
        assert universe.select(scanner.ScanConfig(), tmp_path, data_client=object())[1]["mode"] == "fallback"
    save(cached)
    with monkeypatch.context() as case:
        case.setattr(universe, "DIRECTORY_MAX_BYTES", path.stat().st_size - 1)
        assert universe.select(scanner.ScanConfig(), tmp_path, data_client=object())[1]["mode"] == "fallback"
    # Stale prices still invalidate selection even with a usable classified directory.
    stale = frame()
    stale.index = stale.index - pd.Timedelta(days=1)
    monkeypatch.setattr(scanner, "_download_batch", lambda client, names, cfg, session: {s: stale for s in names})
    names, report = universe.select(scanner.ScanConfig(), tmp_path, data_client=object())
    assert names == ["AAPL"] and report["mode"] == "fallback" and report["fresh"] == 0
    path.unlink()
    assert universe.select(scanner.ScanConfig(), tmp_path, data_client=object())[1]["mode"] == "fallback"


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
    # An explicit capacity, because the point here is the BOUND: with 801 names
    # and CAPACITY at 1000 the selection is limited by the input instead and
    # this test would pass whatever rotate() did with its ceiling.
    chosen, reasons = universe.rotate(metrics, date(2026, 9, 8), ["S0"], capacity=500)
    assert len(chosen) == 500 and "BURST" in chosen and "S0" in chosen
    assert reasons["rotating discovery"] == 50 and reasons["4% move"] == 1
    assert universe.rotate(dict(reversed(list(metrics.items()))), date(2026, 9, 8),
                           ["S0"], capacity=500)[0] == chosen
    assert universe.rotate(metrics, date(2026, 9, 9), ["S0"], capacity=500)[0] != chosen


def test_the_directory_request_presents_as_a_browser_because_nothing_else_is_answered():
    """api.nasdaq.com holds a non-browser User-Agent open until the read times
    out, from every GitHub-hosted runner tried: the pipeline's former
    "SpicyStock/1.0 (...)", python-requests' default and the honest
    "Mozilla/5.0 (compatible; ...)" form each hung for the full timeout, while
    a Chrome-style string from the same runners returned the whole directory in
    about a second (probe run 34414747241, 9 Sep 2026, one header set per fresh
    runner, with requests and with curl). This pins the SHAPE that answered and
    not the constant's name: putting any of the three strings that hung back
    turns it red, and so does dropping the Accept a browser sends. The request
    itself is held to the constant by the transport-recovery check above.
    """
    headers = universe.DIRECTORY_HEADERS
    assert set(headers) == {"User-Agent", "Accept"}
    agent = headers["User-Agent"]
    assert agent.startswith("Mozilla/5.0 (")
    assert all(token in agent for token in ("AppleWebKit/", "Chrome/", "Safari/"))
    assert not any(hung in agent for hung in ("compatible", "SpicyStock", "python-requests", "curl"))
    assert headers["Accept"] == "application/json, text/plain, */*"


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
    with monkeypatch.context() as case:
        _check_dated_cache_contract(case, tmp_path)


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
    rows = [company(s, unused="not retained") for s in symbols] + [company("MRNA", sector="Health Care")] * 380
    monkeypatch.setattr(universe, "fetch_directory", lambda: rows)
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
    cache_path = tmp_path / universe.DIRECTORY_CACHE
    saved = cache_path.read_bytes()
    payload = json.loads(gzip.decompress(saved))
    assert report["directory_status"] == "live" and report["directory_age_days"] == 0
    assert payload["fetched_at"] == report["directory_fetched_at"] and len(payload["rows"]) == 500
    assert payload["source_url"] == universe.SOURCE_URL
    assert all(set(row) == set(universe.DIRECTORY_FIELDS) for row in payload["rows"])
    with monkeypatch.context() as case:
        case.setattr(universe, "fetch_directory", lambda: [company("NEW")])
        assert universe.select(scanner.ScanConfig(), tmp_path, data_client=object())[1]["mode"] == "fallback"
        assert cache_path.read_bytes() == saved, "An incomplete refresh cannot replace a good cache"
    with monkeypatch.context() as case:
        def cannot_replace(self, target):
            raise PermissionError("storage unavailable")
        case.setattr(universe.Path, "replace", cannot_replace)
        names, report = universe.select(scanner.ScanConfig(), tmp_path, data_client=object())
        assert set(names) == set(symbols) and report["mode"] == "adaptive"
        assert cache_path.read_bytes() == saved
        assert list(tmp_path.glob(".universe-directory-*.tmp")) == []


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
    assert len(names) == universe.CAPACITY and reasons["rotating discovery"] == 50
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
    warning = "Live listings refresh unavailable; using dated Nasdaq listings with fresh session prices."
    selection = {"mode": "adaptive", "warning": warning, "directory_status": "cached"}
    monkeypatch.setenv("SCAN_UNIVERSE", "adaptive")
    monkeypatch.setattr(universe, "select", lambda cfg, docs: (names, selection))
    monkeypatch.setattr(pipeline, "_already_published", lambda cfg, tickers: None)
    report = pipeline.RunReport()
    pipeline.run("evening", dry_run=False, report=report)
    snapshot = json.loads((tmp_path / "docs" / "data.json").read_text())
    assert report.published and report.status == "degraded"
    assert {"stage": "universe", "message": warning} in report.errors
    assert snapshot["run"]["universe"]["selection"] == selection
    assert snapshot["run"]["status"] == "degraded" and mocked_boundaries["resend"].sent == []


def test_the_selector_says_which_of_its_numbers_are_strategy_and_the_fingerprint_carries_them(monkeypatch):
    """The selector decides which names can produce a burst, so the record has
    to say which selector produced a row.

    "Already per run in run.universe" was rules_fingerprint()'s stated reason
    for leaving this module out, and it was true while the universe was a
    checked-in symbol file. Reproduced before it was changed: moving
    MIN_DOLLARS and CAPACITY left the fingerprint byte-identical, so
    evidence.rules would have reported one screener across a change that
    moved the pool. Two lists and a guard, the shape ScanConfig and
    src.stockbee keep, so a constant added later cannot arrive unclassified.
    """
    scalars = {n for n in dir(universe)
               if n.isupper() and isinstance(getattr(universe, n), (int, float))
               and not isinstance(getattr(universe, n), bool)}
    strategy, plumbing = set(universe.STRATEGY_CONSTANTS), set(universe.PLUMBING_CONSTANTS)
    assert not (strategy & plumbing), sorted(strategy & plumbing)
    assert strategy | plumbing == scalars, (
        f"uncategorised: {sorted(scalars - strategy - plumbing)}; "
        f"named but not constants: {sorted((strategy | plumbing) - scalars)}")

    fingerprint = pipeline.rules_fingerprint()
    for name in strategy:
        assert fingerprint[f"universe.{name.lower()}"] == getattr(universe, name)
    for name in plumbing:
        assert f"universe.{name.lower()}" not in fingerprint
    assert universe.QUOTAS, "no quotas, so this guard proves nothing"
    for reason, quota in universe.QUOTAS.items():
        assert fingerprint[f"universe.quota.{reason.replace(' ', '_')}"] == quota

    # And the record can SEE a move, which is the whole point.
    monkeypatch.setattr(universe, "MIN_DOLLARS", 3_000_000)
    monkeypatch.setitem(universe.QUOTAS, "rotating discovery", 200)
    moved = pipeline.rules_fingerprint()
    assert moved["universe.min_dollars"] == 3_000_000
    assert moved["universe.quota.rotating_discovery"] == 200
    assert moved != fingerprint


def test_a_moved_universe_floor_splits_the_learning_corpus(monkeypatch):
    """The narrower question src.learning asks, over the wider fingerprint.

    The fit reads a row's score, volume ratio and checklist passes -- none of
    which the selector supplies directly -- but a floor that moved changes
    which names could be scored at all, so those rows were produced by a
    different screener. The universe keys are PRODUCTION for that reason, and
    a run recorded either side of the change must not pool.
    """
    from src import learning

    before = {"model": "claude-x", "rules": pipeline.rules_fingerprint()}
    monkeypatch.setattr(universe, "MIN_DOLLARS", 3_000_000)
    after = {"model": "claude-x", "rules": pipeline.rules_fingerprint()}
    assert learning._signature(before) and learning._signature(after)
    assert learning._signature(before) != learning._signature(after)


def test_the_selector_reads_the_scan_thresholds_rather_than_spelling_them_again(monkeypatch):
    """One number, one spelling -- on both floors this module used to retype.

    Each was reproduced before it was fixed: with min_price at $10 the pool
    still admitted a $6 name, and with min_gain_pct at 10% the "4% move"
    quota still reserved room for a 4.5% mover. Both are archived under the
    config's own value, so the record named a threshold that had not decided
    anything. Patched on the CLASS, so a default bound at definition time
    dies here -- the trap round 14 named for exactly this kind of test.
    """
    cheap = company(symbol="CHEAP", lastsale="$6.00", volume="5000000")
    assert universe.directory_pool([cheap], [])[0] == ["CHEAP"]
    monkeypatch.setattr(scanner.ScanConfig, "min_price", 10.0)
    pool, reasons = universe.directory_pool([cheap], [])
    assert pool == []
    assert reasons == {"no recent trading above $10": 1}

    metrics = {"AAA": {"gain": .05, "participation": 1., "liquidity": 1e9, "momentum": 1.},
               "BBB": {"gain": .045, "participation": .9, "liquidity": 9e8, "momentum": .9},
               "CCC": {"gain": .01, "participation": .5, "liquidity": 8e8, "momentum": .8}}
    session = date(2026, 9, 9)
    assert universe.rotate(metrics, session, capacity=60)[1].get("4% move") == 2
    monkeypatch.setattr(scanner.ScanConfig, "min_gain_pct", 10.0)
    assert universe.rotate(metrics, session, capacity=60)[1].get("4% move") is None
    # The applied config still wins over the class, which is what select() passes.
    assert universe.rotate(metrics, session, capacity=60, min_gain_pct=4.0)[1]["4% move"] == 2

    # And the third spelling, in measure(), found by sweeping after the first two.
    days = pd.bdate_range(end=pd.Timestamp("2026-09-09"), periods=universe.LOOKBACK + 1)
    frame = pd.DataFrame({"Open": 6., "High": 6.2, "Low": 5.8, "Close": 6.,
                          "Volume": 2e7}, index=days)
    assert universe.measure(frame, session, min_price=4.0) is not None
    assert universe.measure(frame, session) is None, "measure() ignored the raised floor"


def test_the_selector_leaves_no_strategy_number_as_a_bare_literal():
    """The one thing a fingerprint of named constants cannot catch.

    src.lynch has this guard because six windows, then a seventh, then four
    more in extra_context() were each a strategy number no other layer could
    see. rotate() held five quota sizes and the burst threshold the same way,
    and the price floor was spelled THREE times -- directory_pool(), rotate()
    and measure() -- the third found only by sweeping after the first two were
    fixed. The AST is read rather than the values, because a literal that
    happens to equal the constant it shadows agrees tonight and diverges on
    the commit that moves one of them.

    SCOPED TO THE THREE FUNCTIONS THAT APPLY A SELECTION THRESHOLD, and the
    scope is the residual: fetch_directory(), the cache readers, identity()
    and benchmark_history() carry status codes, timeouts and slice widths,
    which are transport and not strategy, and naming all of them would put
    two dozen constants in a fingerprint that must stay readable. A fourth
    selection function would be outside this guard -- what catches it is the
    assertion below that these three still exist, so a rename is red rather
    than silently uncovered, plus the STRATEGY_CONSTANTS guard for anything
    that arrives NAMED. A number never named, in a function nobody added
    here, is what this cannot see.
    """
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(universe))
    # indices (0, 1, 2 for iloc[-2]), an empty floor, and the percent divisor
    allowed = {0, 1, 2, 100}

    def reads_a_named_threshold(fn):
        """Does this function apply a threshold something else can move?"""
        for n in ast.walk(fn):
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) \
                    and n.value.id == "ScanConfig":
                return True
            if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) \
                    and n.value.id == "QUOTAS":
                return True
        return False

    # DERIVED, not hand-kept: the first version of this guard listed the three
    # function names and then asserted the list against itself, so dropping a
    # name from it passed. A function that reads ScanConfig or QUOTAS is
    # applying a threshold, and is therefore exactly the kind that must not
    # spell a second one as a literal beside it.
    selection = {fn.name for fn in ast.walk(tree)
                 if isinstance(fn, ast.FunctionDef) and reads_a_named_threshold(fn)}
    assert {"directory_pool", "measure", "rotate"} <= selection, sorted(selection)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name in selection):
            continue
        found = {n.value for n in ast.walk(node)
                 if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
                 and not isinstance(n.value, bool)}
        assert found <= allowed, (
            f"{node.name}() names {sorted(found - allowed)} as a bare literal; "
            "put it in QUOTAS or read it off ScanConfig")


def test_the_discovery_cap_is_strategy_because_it_cuts_names_out_of_the_pool(monkeypatch):
    """Why MAX_DISCOVERY is STRATEGY where src.stockbee's section caps are not.

    A section cap truncates the ARCHIVE and changes no verdict. This one cuts
    the liquidity-ranked tail out of the pool, so a name past it is never
    fetched, never measured and can never burst -- which is the same question
    scan.min_gain_pct answers one stage later. Stated in a tuple, the
    classification is only self-consistent; driven, it is justified, and
    moving the constant to PLUMBING is red here rather than silently dropping
    a threshold out of the fingerprint.
    """
    rows = [company("Z" + chr(65 + i), volume=str(9_000_000 - i * 1000)) for i in range(6)]
    assert len(universe.directory_pool(rows, [])[0]) == 6
    monkeypatch.setattr(universe, "MAX_DISCOVERY", 4)
    pool, reasons = universe.directory_pool(rows, [])
    assert len(pool) == 4 and reasons["discovery capacity"] == 2
    assert pipeline.rules_fingerprint()["universe.max_discovery"] == 4
    assert "MAX_DISCOVERY" in universe.STRATEGY_CONSTANTS


def test_select_applies_the_price_floor_of_the_config_it_was_handed(monkeypatch, tmp_path):
    """The threading, at the call site, which the class fallback hides.

    measure() reading ScanConfig at call time is right for a caller with no
    config, and it made dropping `min_price=cfg.min_price` from select()
    invisible: the default and the applied config agree until someone passes
    a different one. A `--tickers` run with its own floor is that someone.
    """
    # 120 names, because select() falls back below its classified-pool minimum.
    symbols = ["B" + chr(65 + i // 26) + chr(65 + i % 26) for i in range(120)]
    monkeypatch.setattr(scanner, "get_universe", lambda: [])
    monkeypatch.setattr(scanner, "current_session", lambda: date(2026, 9, 8))
    # The DIRECTORY price is $50 and the measured close is frame()'s $21, so a
    # $25 floor separates the two stages: the pool still fills, and only
    # measure() can refuse. The first version of this test left both at $20,
    # so directory_pool() emptied the pool and the assertion passed with
    # measure() reading the class -- a test passing because a DIFFERENT rule
    # rejected, which is the shape this project names.
    monkeypatch.setattr(universe, "fetch_directory",
                        lambda: [company(s, lastsale="$50") for s in symbols])
    monkeypatch.setattr(scanner, "_download_batch",
                        lambda client, names, cfg, session: {n: frame() for n in names})
    assert universe.select(scanner.ScanConfig(), tmp_path, data_client=object())[1]["mode"] == "adaptive"
    cfg = replace(scanner.ScanConfig(), min_price=25.0)
    report = universe.select(cfg, tmp_path, data_client=object())[1]
    assert report["eligible"] == len(symbols), "the pool must fill, or measure() is not what refused"
    assert report["mode"] == "fallback", "select() ignored the config's own price floor"
