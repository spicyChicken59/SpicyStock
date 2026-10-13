"""A publication's own named missing or stale stocks, asked for again once before
the next open: bound to the publication, bounded in requests, never a ticket."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from src import market_data, morning, provenance, quality_ledger, source_recovery as recovery
from tests.fakes import FakeAlpaca, FakeDataClient

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/source-recovery"
spec = importlib.util.spec_from_file_location("source_recovery_fixture", FIXTURES / "generate.py")
generate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generate)
NOW, THIN_NOW = generate.NOW, generate.THIN_NOW


@pytest.fixture(autouse=True)
def _no_retry_wait(monkeypatch):
    monkeypatch.setattr(market_data, "RETRY_WAIT_SECONDS", 0)


@pytest.fixture(scope="module")
def capture():
    return generate.capture()


def fixture(name):
    return json.loads((FIXTURES / (name + ".json")).read_bytes())


def collect(raw, ledger, *, fake=None, clock=lambda: NOW, previous=None, dry_run=False, client="double", **kw):
    provider = None if client is None else FakeDataClient(fake or FakeAlpaca())
    return recovery.collect(raw, ledger, client=provider, clock=clock, dry_run=dry_run,
                            observation_run_id=kw.pop("observation_run_id", "test"), previous_raw=previous)


# ------------------------------------------------------------- the request ----

def test_only_the_publications_named_stale_stock_is_requested_under_its_own_basis(capture, monkeypatch):
    raw, ledger = capture
    monkeypatch.setenv("SCAN_FEED", "iex")   # the environment's feed is not the record's
    fake = generate.double("WBD")
    fake.add_history("AAPL", generate.make_ohlcv("flat", seed=[1, 2], days=260))   # a ready name the record never names
    out = collect(raw, ledger, fake=fake)
    assert out["status"] == "recovered" and out["reason"] is None and out["requested"] == ["WBD"]
    assert len(fake.bar_requests) == 1 == out["source"]["batch_attempts"]
    request = fake.bar_requests[0]
    assert list(request.symbol_or_symbols) == ["WBD"] and request.feed.value == "sip" == out["frozen"]["feed"]
    assert request.adjustment.value == "split" == out["frozen"]["adjustment"] == market_data.BAR_ADJUSTMENT.value
    assert request.end.date().isoformat() == "2026-10-09" and str(request.timeframe) == "1Day"
    assert out["frozen"]["lookback_days"] == 260 and out["frozen"]["universe_identity"] == "ea8f2d4b68e1ebd8"
    assert out["source"]["window"]["basis"] == "reconstructed_from_application_arguments_not_observed_wire_request"
    assert out["source"]["window"]["end"] == "2026-10-09T23:59:59+00:00"
    row = out["rows"][0]
    assert row == {"ticker": "WBD", "category": "stale", "original_ending": "2026-10-05", "outcome": "recovered",
                   "ending": "2026-10-09", "ready_fault": None, "volume": row["volume"], "flat": False}
    assert out["recovered"] == {"requested": 1, "arrived": 1, "session_ready": 1, "arrived_not_ready": 0, "still_stale": 0,
                                "still_missing": 0, "not_returned": 0, "zero_volume": 0, "flat": 0}
    assert out["original"] == {**out["original"], "ready_stocks": 4774, "intended_stocks": 4775, "acceptance_status": "degraded",
                               "run_status": "ok", "gate_read_run_status": False, "tolerance_verdict": "tolerated"}
    assert out["coverage"] == recovery.COVERAGE and "no_combined_coverage_figure" in out["limits"]
    forbidden = {"shares", "principal_usd", "risk_usd", "order_json", "order_line", "quantity", "ready", "grade", "plan", "ticket"}
    def scan(value):
        if isinstance(value, dict):
            assert not forbidden & value.keys(), value.keys()
            for v in value.values(): scan(v)
        elif isinstance(value, list):
            for v in value: scan(v)
    scan(out)


def test_the_fixtures_are_the_collectors_own_output():
    for name, body in generate.build().items():
        assert (FIXTURES / name).read_bytes() == body, name


@pytest.mark.parametrize("name,status,reason,outcome,attempts,error", [
    ("recovered", "recovered", None, "recovered", 1, None),
    ("still-stale", "nothing_recovered", None, "still_stale", 1, None),
    ("still-missing", "nothing_recovered", None, "still_missing", 1, None),
    ("arrived-not-ready", "nothing_recovered", None, "arrived_not_ready", 1, None),
    ("placeholder", "recovered", None, "recovered", 1, None),
    ("outage", "provider_unavailable", None, "not_returned", 2, "provider_error"),
    ("refused", "provider_unavailable", None, "not_returned", 1, "authentication"),
    ("no-credentials", "provider_unavailable", None, "not_returned", 0, "missing_credentials"),
    ("window-ended", "inapplicable", "recovery_window_ended", None, 0, None),
    ("stale-publication", "inapplicable", "stale_publication", None, 0, None),
    ("future-publication", "inapplicable", "future_publication", None, 0, None),
    ("already-attempted", "inapplicable", "already_attempted", None, 0, None),
    ("no-deficit", "inapplicable", "no_coverage_deficit", None, 0, None),
    ("deficit-not-named", "inapplicable", "deficit_not_named", None, 0, None),
    ("ledger-mismatch", "inapplicable", "membership_mismatch", None, 0, None),
    ("ledger-named-stale", "recovered", None, "recovered", 1, None),
    ("unreadable", "nothing_recovered", None, "arrived_not_ready", 1, None),
])
def test_every_outcome_and_every_zero_call_reason_is_named(name, status, reason, outcome, attempts, error):
    out = fixture(name)
    assert (out["status"], out["reason"]) == (status, reason)
    assert out["source"]["batch_attempts"] == attempts and out["source"]["error_kind"] == error
    assert [r["outcome"] for r in out["rows"]] == ([outcome] if outcome else [])
    if reason:
        assert out["requested"] == [] and out["source"]["status"] == "not_requested" and out["source"]["checked_at"] is None
        assert out["sentence"].startswith("No source recovery for the ") and "nothing was fetched" in out["sentence"]
    else:
        assert out["requested"] and out["source"]["status"] in ("ok", "unavailable")


def test_the_still_stale_row_keeps_the_ending_the_provider_served_and_the_placeholder_its_zero_volume():
    stale = fixture("still-stale")["rows"][0]
    assert stale["ending"] == "2026-10-05" and stale["ending"] < "2026-10-09" and stale["volume"] is None
    held = fixture("placeholder")
    assert held["rows"][0]["volume"] == 0 and held["rows"][0]["flat"] is True
    assert held["recovered"]["zero_volume"] == 1 == held["recovered"]["flat"]
    assert "(1 with zero volume)" in held["sentence"]
    gapped = fixture("arrived-not-ready")["rows"][0]
    assert gapped["ready_fault"] == "gapped" and gapped["ending"] == "2026-10-09"
    assert "1 carries it but not the session before (WBD)" in fixture("arrived-not-ready")["sentence"]
    unreadable = fixture("unreadable")
    assert unreadable["rows"][0]["ready_fault"] == "unreadable" and unreadable["rows"][0]["ending"] == "2026-10-09"
    assert "1 carries it, but it or the bar before it is unreadable (WBD)" in unreadable["sentence"]
    assert "not the session before" not in unreadable["sentence"]


def test_each_outcome_is_read_off_what_came_back_in_a_fresh_collection(capture):
    """The same outcomes collected again here, not read off the committed
    files, so a rule the collector stops applying cannot hide behind them."""
    raw, ledger = capture
    cases = [
        (generate.double("WBD"), "recovered", "2026-10-09", None, 1, 0),
        (generate.double("WBD", stale_sessions=4), "still_stale", "2026-10-05", None, 0, 0),
        (generate.double("WBD", hole=date(2026, 10, 8)), "arrived_not_ready", "2026-10-09", "gapped", 0, 0),
        (generate.double("WBD", nan_close=True), "arrived_not_ready", "2026-10-09", "unreadable", 0, 0),
        (generate.double("WBD", placeholder=True), "recovered", "2026-10-09", None, 1, 1),
        (generate.double("WBD", history=False), "still_missing", None, None, 0, 0),
    ]
    for fake, outcome, ending, fault, ready, zero in cases:
        out = collect(raw, ledger, fake=fake)
        row = out["rows"][0]
        assert (row["outcome"], row["ending"], row["ready_fault"]) == (outcome, ending, fault), (outcome, row)
        assert (out["recovered"]["session_ready"], out["recovered"]["zero_volume"]) == (ready, zero), (outcome, out["recovered"])
        assert (row["volume"] is None) == (outcome not in recovery.ARRIVED)
        # each fault in its own words, read off this collection's own sentence
        if fault == "gapped":
            assert "1 carries it but not the session before (WBD)" in out["sentence"]
        if fault == "unreadable":
            assert "1 carries it, but it or the bar before it is unreadable (WBD)" in out["sentence"]
            assert "not the session before" not in out["sentence"]
    # a ledger population that does not re-derive the record's own is refused, collected again
    withheld = generate.unnamed(generate.page("thin"))
    empty = {k: [] for k in ("no_bars", "dropped", "unfetched_budget", "unfetched_failure", "refused", "gapped", "unreadable")}
    fake = generate.double("QAA")
    out = collect(withheld, generate.ledger_for(withheld, {"stale": ["QAB"], **empty}), fake=fake, clock=lambda: THIN_NOW, dry_run=True)
    assert (out["reason"], out["requested"], fake.bar_requests) == ("membership_mismatch", [], [])
    fake = generate.double("QAA")
    out = collect(withheld, generate.ledger_for(withheld, {"stale": ["QAA"], **empty}), fake=fake, clock=lambda: THIN_NOW, dry_run=True)
    assert (out["reason"], out["requested"], len(fake.bar_requests)) == (None, ["QAA"], 1)


class _Slow:
    """A client whose every bars request takes longer than the bound allows."""

    def __init__(self, inner, seconds):
        self.inner, self.seconds, self.calls = inner, seconds, 0

    def get_stock_bars(self, request):
        import time
        self.calls += 1
        time.sleep(self.seconds)
        return self.inner.get_stock_bars(request)


def test_a_provider_call_past_the_bound_is_stopped_and_kept_as_a_timeout_with_its_attempt_counted(capture, monkeypatch):
    import signal
    raw, ledger = capture
    monkeypatch.setattr(recovery, "MAX_COLLECTION_SECONDS", recovery.FETCH_RESERVE_SECONDS + 1)   # a one-second call budget
    before = signal.getsignal(signal.SIGALRM)
    slow = _Slow(FakeDataClient(generate.double("WBD")), 3)
    out = recovery.collect(raw, ledger, client=slow, clock=lambda: NOW, observation_run_id="t")
    # stopped inside the first request: the transport's own retry never saw it, so nothing was asked twice
    assert slow.calls == 1
    assert (out["status"], out["source"]["error_kind"], out["source"]["batch_attempts"]) == ("provider_unavailable", "timeout", 1)
    assert [r["outcome"] for r in out["rows"]] == ["not_returned"]
    assert "the provider did not answer within the 1-second bound" in out["sentence"]
    assert recovery.attempted(out, out["publication"]["data_sha256"])          # the spent request still binds the next slot
    assert signal.getitimer(signal.ITIMER_REAL)[0] == 0 and signal.getsignal(signal.SIGALRM) == before


def test_no_request_is_made_where_the_bound_cannot_be_installed(capture):
    import threading
    raw, ledger = capture
    fake, caught = generate.double("WBD"), []

    def off_main():
        try:
            collect(raw, ledger, fake=fake)
        except ValueError as exc:
            caught.append(str(exc))
    worker = threading.Thread(target=off_main)
    worker.start()
    worker.join()
    assert caught == ["source recovery: bounded transport requires an available main-thread timer"] and fake.bar_requests == []


def test_the_sentence_says_what_was_asked_and_what_came_back_and_adds_no_coverage_figure():
    out = fixture("recovered")
    assert out["sentence"] == (
        "Source recovery for the 2026-10-09 publication: its 1 stock without a usable 2026-10-09 bar, named in full, "
        "was asked for again at 9:20 AM ET on Mon 12 Oct, before the 2026-10-12 open, in 1 request; "
        "1 now carries a 2026-10-09 bar that passes the session rules. The publication stays 4774 of 4775 intended "
        "stocks ready; its measurements, grades, plans and tickets are unchanged, and why a bar was absent is not established.")
    assert "4775 of 4775" not in out["sentence"] and "4,775 of 4,775" not in json.dumps(out)
    assert fixture("window-ended")["sentence"] == (
        "No source recovery for the 2026-10-09 publication at 9:30 AM ET on Mon 12 Oct: the next session opened before "
        "this check ran; nothing was fetched.")


# -------------------------------------------------------------- the window ----

@pytest.mark.parametrize("at,reason", [
    ("2026-10-12T13:29:59+00:00", None), ("2026-10-12T13:30:00+00:00", "recovery_window_ended"),
    ("2026-10-10T08:00:00+00:00", None),      # Saturday morning: the window runs to Monday's open
    ("2026-10-11T23:00:00+00:00", None),      # Sunday evening
    ("2026-10-12T21:30:00+00:00", "stale_publication"),
    ("2026-10-10T07:30:12+00:00", None),      # 3.6 s before the 07:30:15.55 publication, inside the 5 s skew
    ("2026-10-10T07:30:00+00:00", "future_publication"),
])
def test_the_window_runs_from_publication_to_the_next_open_inclusive_of_nothing_after(capture, at, reason):
    raw, ledger = capture
    out = collect(raw, ledger, fake=generate.double("WBD"), clock=lambda: datetime.fromisoformat(at))
    assert out["reason"] == reason
    assert out["window"] == {"next_session": "2026-10-12", "next_open_at": "2026-10-12T09:30:00-04:00",
                             "before_next_open": datetime.fromisoformat(at) < datetime.fromisoformat("2026-10-12T09:30:00-04:00")}


def test_the_window_is_the_calendars_across_a_holiday_weekend_in_winter(monkeypatch):
    # Friday 13 November 2026 published Saturday; the window runs to Monday 9:30 AM EST (14:30 UTC)
    raw = (ROOT / "tests/fixtures/page/thin.json").read_bytes()
    data = json.loads(raw)
    frozen = recovery.frozen_basis({**data, "run": {**data["run"], "session": "2026-11-13"}}, {"rules_version": "x"})
    inside = recovery.window_of(frozen, datetime(2026, 11, 16, 14, 29, 59, tzinfo=timezone.utc))
    at_open = recovery.window_of(frozen, datetime(2026, 11, 16, 14, 30, tzinfo=timezone.utc))
    assert inside == {"next_session": "2026-11-16", "next_open_at": "2026-11-16T09:30:00-05:00", "before_next_open": True}
    assert at_open["before_next_open"] is False
    # Labor Day week: Friday 4 September's next session is Tuesday 8 September
    frozen = recovery.frozen_basis({**data, "run": {**data["run"], "session": "2026-09-04"}}, {"rules_version": "x"})
    assert recovery.window_of(frozen, datetime(2026, 9, 7, 13, 20, tzinfo=timezone.utc)) == {
        "next_session": "2026-09-08", "next_open_at": "2026-09-08T09:30:00-04:00", "before_next_open": True}


# ---------------------------------------------------------------- deficits ----

def test_a_degraded_run_status_does_not_gate_the_recovery_and_a_green_one_does_not_excuse_it(capture):
    raw, ledger = capture
    data = json.loads(raw)
    # run.status is outside provenance's sealed run facts, so the flipped record still verifies
    for status, problems in (("degraded", [{"kind": "claude_partial", "message": "x"}]), ("ok", [])):
        flipped = deepcopy(data); flipped["run"]["status"] = status; flipped["run"]["problems"] = problems
        flipped_raw = json.dumps(flipped).encode()
        assert provenance.verify(flipped, require_sources=False)["status"] == "PASS"
        out = collect(flipped_raw, None, fake=generate.double("WBD"))
        assert out["status"] == "recovered" and out["requested"] == ["WBD"]
        assert out["original"]["run_status"] == status and out["original"]["gate_read_run_status"] is False
    # and a night whose status is degraded for the reader alone has no deficit to recover
    out = fixture("no-deficit")
    assert out["reason"] == "no_coverage_deficit" and out["original"]["gaps"] == {c: 0 for c in recovery.CATEGORIES}


def test_names_come_from_the_record_first_and_the_ledger_second_and_never_from_a_guess():
    recorded = fixture("thin-recovered")["deficits"]
    assert recorded["categories"]["stale"] == {"count": 1, "identity": "7a8939e0d8cb3161", "named": True, "source": "record",
                                               "names": ["QAA"], "benchmark_in_population": False}
    assert recorded["ledger"] is None and recorded["named_stocks"] == 1 and recorded["unnamed_frames"] == 0
    ledgered = fixture("ledger-named-stale")["deficits"]
    assert ledgered["categories"]["stale"]["source"] == "ledger" and ledgered["categories"]["stale"]["names"] == ["QAA"]
    assert ledgered["ledger"]["used"] is True and ledgered["ledger"]["path"].startswith("quality-ledger/v1/")
    unnamed = fixture("deficit-not-named")["deficits"]
    assert unnamed["categories"]["stale"] == {"count": 1, "identity": "7a8939e0d8cb3161", "named": False, "source": None,
                                              "names": None, "benchmark_in_population": None}
    assert unnamed["named_stocks"] == 0 and unnamed["unnamed_frames"] == 1
    # a record naming its own stock does not consult the ledger, which stays recorded as present and unused
    assert fixture("recovered")["deficits"]["ledger"]["used"] is False


def test_a_ledger_population_that_is_not_the_records_is_a_mismatch_and_another_publications_entry_is_refused(capture):
    raw, ledger = capture
    out = fixture("ledger-mismatch")
    assert out["reason"] == "membership_mismatch" and out["requested"] == []
    thin = (ROOT / "tests/fixtures/page/thin.json").read_bytes()
    with pytest.raises(ValueError, match="another publication's"):
        recovery.collect(thin, ledger, client=FakeDataClient(FakeAlpaca()), clock=lambda: THIN_NOW, dry_run=True)
    with pytest.raises(ValueError, match="unreadable"):
        recovery.ledger_entry(b"not gzip", hashlib.sha256(raw).hexdigest())


def test_the_benchmark_is_never_requested_and_the_stale_bound_is_the_records_own(capture):
    raw, ledger = capture
    data = json.loads(raw)
    stale = ["SPY", "WBD"]
    data["run"]["input_tolerance"]["names"] = stale
    data["run"]["input_tolerance"]["endings"] = {"SPY": "2026-10-05", "WBD": "2026-10-05"}
    # followup._membership holds the names to the record's own stale population; two names against a count of one is a mismatch
    out = collect(json.dumps(data).encode(), None, fake=generate.double("WBD"))
    assert out["reason"] == "membership_mismatch"
    assert recovery.MAX_NAMES == 100 == data["rules"]["pipeline"]["stale_names_max"]
    assert recovery.MAX_NAMES == recovery.MAX_BATCHES * market_data.DEFAULT_BATCH_SIZE


def test_the_benchmark_is_left_out_of_a_request_by_either_path_and_alone_is_its_own_reason(tmp_path, mocked_boundaries, fake_alpaca, fake_anthropic, seed):
    """The run counts a stale benchmark among its stale frames and names the
    stocks without it; a ledger membership carries it. Neither path requests
    it, and a night whose only stale frame is the benchmark's asks nothing."""
    from src import universe
    from tests.test_pipeline import evening, a_plus_frame, coil, base_frames, CLAUDE_A_PLUS
    from tests.synthetic import make_ohlcv

    def night(name, *, stale_stock, missing=()):
        fake_anthropic.set_payload(dict(CLAUDE_A_PLUS))
        fake_alpaca.add_history("AAA", a_plus_frame())
        fake_alpaca.add_history("COIL", coil())
        for symbol, df in base_frames(11, seed).items():
            fake_alpaca.add_history(symbol, df, stale_sessions=1 if symbol == stale_stock else 0)
        fake_alpaca.add_history("SPY", make_ohlcv("base", seed=[seed, 999], days=260), stale_sessions=1)
        home = tmp_path / name
        (home / "docs").mkdir(parents=True)
        rep, data, docs = evening(home, ["AAA", "COIL"] + [f"B{chr(65 + i)}{chr(65 + i)}" for i in range(11)] + list(missing))
        assert data is not None, rep.problems
        return (docs / "data.json").read_bytes(), data

    raw, data = night("with-a-stock", stale_stock="BAA")
    run = data["run"]
    # the tolerance names every stale frame, the benchmark's among them, and counts the stocks without it
    assert run["input_tolerance"]["names"] == ["BAA", "SPY"] and run["input_tolerance"]["benchmark"] == "SPY"
    assert run["input_tolerance"]["stale_stocks"] == 1
    assert run["coverage"]["stale"] == 2 and run["coverage"]["reasons"]["stale"] == universe.population(["BAA", "SPY"])
    clock = lambda: THIN_NOW                      # 13:20Z on the next session, 11 September, before its open
    # the record path: the tolerance names the stock alone and the benchmark is noted as in the population
    fake = generate.double("BAA")
    out = collect(raw, None, fake=fake, clock=clock, dry_run=True)
    assert out["requested"] == ["BAA"] and out["status"] == "recovered"
    assert out["deficits"]["categories"]["stale"] == {"count": 2, "identity": universe.population(["BAA", "SPY"])["identity"],
                                                      "named": True, "source": "record", "names": ["BAA"], "benchmark_in_population": True}
    assert list(fake.bar_requests[0].symbol_or_symbols) == ["BAA"]
    # the ledger path: the membership carries the benchmark and the request still leaves it out
    stripped = generate.unnamed(raw)
    ledger = generate.ledger_for(stripped, {"stale": ["BAA", "SPY"]})
    fake = generate.double("BAA")
    out = collect(stripped, ledger, fake=fake, clock=clock, dry_run=True)
    assert out["requested"] == ["BAA"] and out["deficits"]["categories"]["stale"]["source"] == "ledger"
    assert out["deficits"]["categories"]["stale"]["benchmark_in_population"] is True and out["deficits"]["ledger"]["used"] is True
    assert list(fake.bar_requests[0].symbol_or_symbols) == ["BAA"] and out["source"]["symbols_requested"] == 1
    # the benchmark alone: counted, named, nothing to ask for, and said in those words
    raw, data = night("benchmark-alone", stale_stock=None)
    assert data["run"]["coverage"]["stale"] == 1 and data["run"]["input_tolerance"]["names"] == ["SPY"]
    assert data["run"]["input_tolerance"]["stale_stocks"] == 0
    fake = generate.double("SPY")
    out = collect(raw, None, fake=fake, clock=clock, dry_run=True)
    assert (out["reason"], out["requested"], out["status"], fake.bar_requests) == ("benchmark_only", [], "inapplicable", [])
    assert out["deficits"]["categories"]["stale"]["names"] == [] and out["deficits"]["categories"]["stale"]["benchmark_in_population"] is True
    assert "the benchmark's, which is never requested; nothing was fetched." in out["sentence"]
    # a stock the provider never answered for, counted and named nowhere without a ledger, beside a named stale one:
    # the named one is asked for and the sentence says how many counted frames it could not name
    raw, data = night("partly-named", stale_stock="BAA", missing=("NOBAR",))
    assert data["run"]["coverage"]["no_bars"] == 1 and data["run"]["input_tolerance"]["names"] == ["BAA", "SPY"]
    out = collect(raw, None, fake=generate.double("BAA"), clock=clock, dry_run=True)
    assert out["requested"] == ["BAA"] and out["deficits"]["unnamed_frames"] == 1
    assert out["deficits"]["categories"]["no_bars"]["named"] is False
    assert "the 1 stock it names of those without a usable 2026-09-10 bar (1 more counted frame is named nowhere) was asked" in out["sentence"]
    assert "named in full" not in out["sentence"]


def test_a_named_deficit_over_the_budget_is_refused_whole_and_never_as_a_prefix():
    thin = json.loads((ROOT / "tests/fixtures/page/thin.json").read_bytes())
    run = thin["run"]
    names = [f"Q{i:03d}" for i in range(recovery.MAX_NAMES + 1)]
    defs = {"categories": {c: {"count": 0, "identity": "e3b0c44298fc1c14", "named": True, "source": None, "names": [],
                               "benchmark_in_population": False} for c in recovery.CATEGORIES},
            "named_stocks": len(names), "unnamed_frames": 0, "mismatch": False, "stale_endings": {}, "ledger": None}
    defs["categories"]["no_bars"].update(count=len(names), names=names, source="ledger")
    binding = {"data_sha256": "0" * 64, "rules_version": thin["app"]["rules_version"]}
    frozen = recovery.frozen_basis(thin, binding)
    window = recovery.window_of(frozen, THIN_NOW)
    assert recovery._reason(thin, binding, frozen, window, THIN_NOW, defs, None) == "deficit_over_budget"
    defs["categories"]["no_bars"]["names"] = names[:-1]; defs["named_stocks"] = len(names) - 1
    assert recovery._reason(thin, binding, frozen, window, THIN_NOW, defs, None) is None
    # a basis the record contradicts refuses before the deficit is read
    broken = deepcopy(thin); broken["run"]["input_basis"]["feed"] = "iex"
    assert recovery._reason(broken, binding, recovery.frozen_basis(broken, binding), window, THIN_NOW, defs, None) == "basis_differs"


def test_already_attempted_binds_the_same_publication_only(capture):
    raw, ledger = capture
    spent = (FIXTURES / "recovered.json").read_bytes()
    assert collect(raw, ledger, fake=generate.double("WBD"), previous=spent)["reason"] == "already_attempted"
    # the same prior over ANOTHER publication (the thin night) spends nothing of it
    thin = (ROOT / "tests/fixtures/page/thin.json").read_bytes()
    out = recovery.collect(thin, None, client=FakeDataClient(generate.double("QAA")), clock=lambda: THIN_NOW, dry_run=True,
                           previous_raw=spent)
    assert out["reason"] is None and out["previous_observation_sha256"] == hashlib.sha256(spent).hexdigest()
    # an inapplicable prior spent nothing and does not block the next attempt
    unspent = (FIXTURES / "window-ended.json").read_bytes()
    assert collect(raw, ledger, fake=generate.double("WBD"), previous=unspent)["reason"] is None


def test_two_stale_stocks_one_served_late_is_partial(capture):
    raw, ledger = capture
    data = json.loads(raw)
    # the retained record names one stale stock; a second cannot be added without moving the sealed coverage,
    # so the partial case is driven through a thin-night record whose stale pair the ledger names
    thin = json.loads((ROOT / "tests/fixtures/page/thin.json").read_bytes())
    thin["run"]["input_tolerance"]["names"] = None; thin["run"]["input_tolerance"]["endings"] = None
    thin["run"]["coverage"]["stale"] = 2; thin["run"]["coverage"]["reasons"]["stale"] = {"count": 2, "identity": "x", "sample": ["QAA", "QAB"]}
    # the sealed coverage moved, so this record does not verify: the honest path is the validator's refusal
    with pytest.raises(ValueError, match="publication integrity"):
        recovery.collect(json.dumps(thin).encode(), None, client=FakeDataClient(FakeAlpaca()), clock=lambda: THIN_NOW, dry_run=True)
    # partial is reached where a ledger names two stocks of a record that counts two: the unit rule
    rows = [{"ticker": "QAA", "outcome": "recovered"}, {"ticker": "QAB", "outcome": "still_stale"}]
    assert recovery._status(rows, {"status": "ok"}, None) == "partial"
    assert recovery._status([{"outcome": "arrived_not_ready"}], {"status": "ok"}, None) == "nothing_recovered"
    assert recovery._status([{"outcome": "recovered"}], {"status": "unavailable"}, None) == "provider_unavailable"


# --------------------------------------------------------------- forgeries ----

def forge(name, mutate):
    out = fixture(name)
    mutate(out)
    return out


@pytest.mark.parametrize("name,mutate,match", [
    ("recovered", lambda o: o["rows"][0].update(outcome="still_stale"), "facts on a bar that did not arrive"),
    ("recovered", lambda o: o["source"].update(batch_attempts=3), "batch attempts exceed budget"),
    ("recovered", lambda o: o["source"].update(batch_attempts=0), "a request without an attempt"),
    ("window-ended", lambda o: o["rows"].append({"ticker": "WBD", "category": "stale", "original_ending": "2026-10-05",
                                                 "outcome": "recovered", "ending": "2026-10-09", "ready_fault": None, "volume": 1, "flat": False}), "row membership"),
    ("recovered", lambda o: o["frozen"].update(feed="iex"), "frozen basis differs"),
    ("recovered", lambda o: o["original"].update(ready_stocks=4775), "original coverage facts differ"),
    ("recovered", lambda o: o["policy"].update(max_batch_attempts=3), "recovery policy differs"),
    ("recovered", lambda o: o["recovered"].update(session_ready=0), "tallies differ"),
    ("recovered", lambda o: o.update(sentence="All 4775 stocks are ready now."), "sentence differs"),
    ("recovered", lambda o: o.update(extra=1), "envelope fields differ"),
    ("recovered", lambda o: o.update(previous_observation_sha256="0" * 64), "prior receipt bytes differ"),
    ("recovered", lambda o: o["deficits"]["categories"]["stale"].update(names=["WBD", "AAPL"]), "deficit accounting differs"),
    ("recovered", lambda o: o["window"].update(before_next_open=False), "recovery window differs"),
    ("recovered", lambda o: o.update(status="partial"), "status contradicts"),
    ("recovered", lambda o: o.update(reason="no_coverage_deficit"), "reason differs"),
    ("recovered", lambda o: o["rows"][0].update(volume=-1), "invalid volume"),
    ("still-stale", lambda o: o["rows"][0].update(ending="2026-10-09"), "still-stale row"),
    ("outage", lambda o: o["rows"][0].update(outcome="still_missing"), "contradicts the source"),
    ("no-credentials", lambda o: o["source"].update(batch_attempts=1), "credentials absent yet a request counted"),
])
def test_a_forged_receipt_is_refused_by_name(capture, name, mutate, match):
    raw, ledger = capture
    with pytest.raises(ValueError, match=match):
        recovery.validate_receipt(forge(name, mutate), raw, ledger, require_continuity=True)


def test_a_malformed_receipt_structure_is_one_refusal(capture):
    raw, ledger = capture
    with pytest.raises(ValueError, match="malformed receipt structure"):
        recovery.validate_receipt(forge("recovered", lambda o: o.update(rows=["x"])), raw, ledger)
    with pytest.raises(ValueError, match="invalid source metadata"):
        recovery.validate_receipt(forge("recovered", lambda o: o.update(source="x")), raw, ledger)
    with pytest.raises(ValueError, match="malformed receipt structure"):
        recovery.validate_receipt(forge("recovered", lambda o: o["rows"][0].pop("ticker")), raw, ledger)
    with pytest.raises(ValueError, match="row membership differs"):
        recovery.validate_receipt(forge("recovered", lambda o: o.update(rows="x")), raw, ledger)
    with pytest.raises(ValueError, match="unsupported receipt envelope"):
        recovery.validate_receipt(forge("recovered", lambda o: o.update(schema_version=2)), raw, ledger)


def test_the_receipt_is_bound_to_its_own_bytes_and_ledger(capture):
    raw, ledger = capture
    out = fixture("recovered")
    thin = (ROOT / "tests/fixtures/page/thin.json").read_bytes()
    with pytest.raises(ValueError, match="publication binding differs|production observations require"):
        recovery.validate_receipt(out, thin, None)
    with pytest.raises(ValueError, match="deficit accounting differs"):
        recovery.validate_receipt(out, raw, None)   # the receipt names a ledger entry; none was given
    encoded = json.dumps(out, allow_nan=False, separators=(",", ":")).encode()
    assert len(encoded) <= recovery.MAX_RECEIPT_BYTES
    # continuity: the publisher asks for the prior's bytes, and a different prior is refused
    chain = fixture("already-attempted")
    recovery.validate_receipt(chain, raw, ledger, previous_raw=(FIXTURES / "recovered.json").read_bytes(), require_continuity=True)
    with pytest.raises(ValueError, match="prior receipt bytes differ"):
        recovery.validate_receipt(chain, raw, ledger, previous_raw=(FIXTURES / "still-stale.json").read_bytes(), require_continuity=True)


def test_two_frozen_bases_of_the_eight_october_pair_are_not_one_cohort():
    a = {"universe_identity": "ded8b0a93cffbafe", "universe_snapshot_sha256": "a", "feed": "sip", "adjustment": "split",
         "session": "2026-10-08", "rules_version": "r"}
    b = {**a, "universe_identity": "ea8f2d4b68e1ebd8"}
    with pytest.raises(ValueError, match="universe_identity differs"):
        recovery.same_cohort(a, b)
    assert recovery.same_cohort(a, dict(a)) is True
    with pytest.raises(ValueError, match="session differs"):
        recovery.same_cohort(a, {**a, "session": "2026-10-09"})


# ----------------------------------------------------------------- the run ----

def docs_with(tmp_path, raw, ledger=None, previous=None):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "data.json").write_bytes(raw)
    if ledger is not None:
        (docs / quality_ledger.DIRECTORY).mkdir(parents=True)
        (docs / quality_ledger.DIRECTORY / (hashlib.sha256(raw).hexdigest() + ".json.gz")).write_bytes(ledger)
    if previous is not None:
        (docs / recovery.RECEIPT_FILE).write_bytes(previous)
    return docs


def test_run_reads_the_ledger_beside_the_record_writes_one_file_and_refuses_a_foreign_output(tmp_path, capture, monkeypatch):
    raw, ledger = capture
    docs = docs_with(tmp_path, raw, ledger)
    monkeypatch.setattr(market_data, "get_clients", lambda: FakeDataClient(generate.double("WBD")))
    monkeypatch.setenv("GITHUB_RUN_ID", "77")
    out = recovery.run(docs=docs, output=tmp_path / "out" / "source-recovery.json", clock=lambda: NOW)
    assert out["observation_run_id"] == "77" and out["deficits"]["ledger"]["sha256"] == hashlib.sha256(ledger).hexdigest()
    written = json.loads((tmp_path / "out" / "source-recovery.json").read_bytes())
    assert written == out and (docs / "data.json").read_bytes() == raw
    assert sorted(p.name for p in docs.iterdir()) == ["data.json", "quality-ledger"]
    with pytest.raises(ValueError, match="must not overwrite publication files"):
        recovery.run(docs=docs, output=docs / "data.json", clock=lambda: NOW)
    with pytest.raises(ValueError, match="must not overwrite publication files"):
        recovery.run(docs=docs, output=docs / "picks.json", clock=lambda: NOW)


def test_run_refuses_when_the_record_the_ledger_or_the_prior_moves_during_collection(tmp_path, capture, monkeypatch):
    raw, ledger = capture
    docs = docs_with(tmp_path, raw, ledger)
    monkeypatch.setattr(market_data, "get_clients", lambda: FakeDataClient(generate.double("WBD")))
    ticks = iter([NOW, NOW, NOW + timedelta(seconds=1), NOW + timedelta(seconds=2)])
    def clock():
        at = next(ticks, NOW + timedelta(seconds=3))
        if at == NOW + timedelta(seconds=1):
            (docs / recovery.RECEIPT_FILE).write_bytes(b"{}")
        return at
    with pytest.raises(ValueError, match="previous receipt changed"):
        recovery.run(docs=docs, output=tmp_path / "r.json", clock=clock)
    assert not (tmp_path / "r.json").exists()


def test_the_command_line_prints_counts_and_one_fixed_line_on_refusal(tmp_path, capture, monkeypatch, capsys):
    raw, ledger = capture
    docs = docs_with(tmp_path, raw, ledger)
    for key in market_data.REQUIRED_ENV:
        monkeypatch.setenv(key, "present-for-the-test")
    monkeypatch.setattr(market_data, "get_clients", lambda: FakeDataClient(generate.double("WBD")))
    monkeypatch.setattr(recovery, "datetime", type("Clock", (), {"now": staticmethod(lambda tz=None: NOW)}))
    assert recovery.main(["--docs", str(docs), "--output", str(tmp_path / "r.json")]) == 0
    printed = json.loads(capsys.readouterr().out.strip())
    assert printed == {"status": "recovered", "reason": None, "requested": 1, "arrived": 1, "session_ready": 1,
                       "batch_attempts": 1, "generated_at": NOW.isoformat(), "data_sha256": hashlib.sha256(raw).hexdigest()}
    (docs / "data.json").write_bytes(b"{")
    assert recovery.main(["--docs", str(docs), "--output", str(tmp_path / "r2.json")]) == 1
    assert capsys.readouterr().out.strip() == "Source recovery refused: invalid publication, ledger entry or collection; no receipt replaced."


def test_the_module_never_imports_the_followup_reader_into_its_request_path_and_carries_no_bare_rule_number():
    import ast
    tree = ast.parse((ROOT / "src/source_recovery.py").read_text())
    calls = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    assert "night" not in calls and "scan_all" not in calls and "build" not in calls
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, (int, float)) and not isinstance(sub.value, bool):
                    assert sub.value in (0, 1, 2, 3, 16, 64, 128), (node.name, sub.value)
    assert recovery.RULES["max_names"] == recovery.MAX_NAMES and recovery.RULES["recovery_until"] == "next_session_open"
    assert recovery.MAX_FUTURE_SKEW_SECONDS == morning.POLICY["max_future_skew_seconds"]
    assert 180 + 180 + recovery.MAX_COLLECTION_SECONDS < 15 * 60


def test_the_next_evening_is_byte_identical_with_and_without_a_committed_receipt(tmp_path, mocked_boundaries, fake_alpaca, fake_anthropic, seed):
    """The recovery is a companion: the pipeline never reads it, so a committed
    receipt changes no record, pick or follow-up the next evening writes."""
    from tests.test_pipeline import evening, a_plus_frame, coil, base_frames, CLAUDE_A_PLUS
    from tests.synthetic import make_ohlcv
    fake_anthropic.set_payload(dict(CLAUDE_A_PLUS))
    fake_alpaca.add_history("AAA", a_plus_frame())
    fake_alpaca.add_history("COIL", coil())
    for name, df in base_frames(11, seed).items():
        fake_alpaca.add_history(name, df)
    fake_alpaca.add_history("SPY", make_ohlcv("base", seed=[seed, 999], days=260))
    tickers = ["AAA", "COIL"] + [f"B{chr(65 + i)}{chr(65 + i)}" for i in range(11)]
    def comparable(record):
        # Two evenings over one reader double differ in exactly two facts a
        # receipt cannot touch: the wall clock, and the prompt cache, which the
        # first call writes and the second reads (the input SUM is held equal).
        record = deepcopy(record)
        for clock_fact in ("elapsed_seconds", "fetch_seconds"):
            record["run"].pop(clock_fact)
        blocks = [record["run"]["reader_usage"]] + [b["reader_usage"] for b in record["bursts"] if b.get("reader_usage")]
        for block in blocks:
            for tokens in [block["tokens"]] + [a for a in block.get("attempts", []) if a]:
                tokens["cache_write"] = tokens["cache_write"] + tokens.pop("cache_read")
            block.pop("sentence", None)
        return record
    outcomes = []
    for name in ("without", "with"):
        home = tmp_path / name
        (home / "docs").mkdir(parents=True)
        if name == "with":
            (home / "docs" / recovery.RECEIPT_FILE).write_bytes((FIXTURES / "recovered.json").read_bytes())
        rep, data, docs = evening(home, tickers)
        assert rep.exit_code() in (0, 2), rep.problems
        record = json.loads((docs / "data.json").read_bytes())
        assert record["run"]["reader_usage"]["calls"] == 1 and record["run"]["reader_usage"]["input_tokens"] > 0
        outcomes.append((comparable(record), (docs / "picks.json").read_bytes(), data["run"].get("stale_followup")))
        assert (docs / recovery.RECEIPT_FILE).exists() == (name == "with")
        if name == "with":
            assert (docs / recovery.RECEIPT_FILE).read_bytes() == (FIXTURES / "recovered.json").read_bytes()
    assert outcomes[0] == outcomes[1]
    assert outcomes[0][0]["run"]["reader_usage"]["calls"] == 1 and outcomes[0][0]["app"]["rules_version"]
