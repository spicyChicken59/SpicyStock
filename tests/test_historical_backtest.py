"""tools.historical_backtest: the run's own stages replayed over a recovered
archive, session by session. The archive here is synthetic and built the way
a real one is -- frozen manifest, acquisition ledger, raw pages -- so the
tool is exercised through the same cache the owner's recovered package
presents. Every expected R is computed by hand from the scripted bars."""
from __future__ import annotations

from datetime import date, datetime, time, timezone
import json

import pytest

from src import plan, record, sessions
from tests.test_quality import ideal_bars
from tests.test_record import frame, pick
from tools import historical_acquisition as acquisition
from tools import historical_backtest as backtest
from tools.historical_reconcile import network_blocked

#: the archive's sessions: the production envelope the frozen manifest allows
SESSIONS = [str(d) for d in sessions.dates(date(2025, 8, 4), date(2026, 9, 25))]
#: where the scripted bursts sit (indices into SESSIONS): three past the run's
#: own lookback so the default replay evaluates them, and one (DDD) that only
#: a shortened lookback reaches, more than the published scorecard's window
#: before the archive's end
BURST_A, BURST_C, BURST_B, BURST_D = 270, 272, 280, 150
FLAT = ("F1", "F2", "F3", "F4")
SYMBOLS = sorted(("AAA", "BBB", "CCC", "DDD", "CHEAP", "SPY") + FLAT)
#: the stocks the Market Monitor counts each session: everything but SPY and the $2.50 name
COUNTED = len(SYMBOLS) - 2
VOLUME = 1_500_000


def stamp(day: str) -> str:
    """Alpaca's daily bar timestamp: New York midnight, written in UTC."""
    local = datetime.combine(date.fromisoformat(day), time(), tzinfo=sessions.MARKET_TZ)
    return local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def quiet_series(level: float, n: int, step: float = 0.1, volume: float = 1_000_000) -> list[list[float]]:
    """``n`` sideways bars around ``level``: no 4% day, no $0.90 body."""
    out, prev = [], level
    for i in range(n):
        c = round(level + (step if i % 2 else -step), 2)
        out.append([prev, round(max(prev, c) + 0.2, 2), round(min(prev, c) - 0.2, 2), c, volume])
        prev = c
    return out


def textbook_at(index: int, follow: list[list[float]]) -> list[list[float]]:
    """The field guide's A+ bar with its burst on ``SESSIONS[index]``, the
    scripted ``follow`` bars after it, then a quiet tail to the archive's end."""
    bars = ideal_bars(pre=index - 32)
    assert len(bars) == index + 1
    bars = bars + follow
    tail = quiet_series(follow[-1][3], len(SESSIONS) - len(bars), volume=VOLUME)
    return bars + tail


#: AAA fills at the open, sells half on the +8% day and is stopped at the next
#: open under the raised stop. By hand, against the plan's $121.42 published
#: stop and 4 shares: fill 125.00, half (2) at the +8% level 135.00, the other
#: 2 at the 127.00 open -> (2*10.00 + 2*2.00) / (4*3.58) = 1.6760 -> 1.68.
AAA_FOLLOW = [[125.0, 127.0, 123.5, 125.8, VOLUME],
              [126.0, 135.5, 125.5, 126.8, VOLUME],
              [127.0, 128.0, 126.5, 127.5, VOLUME]]
AAA_R = round((2 * (135.0 - 125.0) + 2 * (127.0 - 125.0)) / (4 * (125.0 - 121.42)), 2)
#: CCC fills at 124.50, holds, sells half at the day-3 close 127.00 and the
#: rest at the day-5 close 128.80 -> (2*2.50 + 2*4.30) / (4*3.08) = 1.1039 -> 1.10.
CCC_FOLLOW = [[124.5, 125.6, 123.0, 125.3, VOLUME],
              [125.4, 126.5, 124.8, 126.1, VOLUME],
              [126.2, 127.3, 125.5, 127.0, VOLUME],
              [127.1, 128.2, 126.4, 127.9, VOLUME],
              [128.0, 129.0, 127.2, 128.8, VOLUME]]
CCC_R = round((2 * (127.0 - 124.5) + 2 * (128.8 - 124.5)) / (4 * (124.5 - 121.42)), 2)
#: BBB bursts on a RED night. Ungated it fills at 124.40, the stop rises to the
#: entry day's 122.00 low and the next day's low takes it -> -2.40/2.98 -> -0.81.
BBB_FOLLOW = [[124.4, 125.0, 122.0, 123.0, VOLUME],
              [122.5, 123.0, 121.0, 121.5, VOLUME]]
BBB_R = round(4 * (122.0 - 124.4) / (4 * (124.4 - 121.42)), 2)
#: DDD opens over the $126.47 limit and never trades back under it: the
#: ticket could not fill, and the record says so (``not_filled``, no R).
DDD_FOLLOW = [[127.0, 128.0, 126.6, 127.5, VOLUME]]


def market() -> dict[str, list[list[float]]]:
    """Ten names over the archive: four textbook bursts, four flat names
    (three of which break down 5% on BBB's night, which is what makes it RED),
    a $2.50 name the price policy must exclude, and SPY."""
    bars = {"AAA": textbook_at(BURST_A, AAA_FOLLOW), "CCC": textbook_at(BURST_C, CCC_FOLLOW),
            "BBB": textbook_at(BURST_B, BBB_FOLLOW), "DDD": textbook_at(BURST_D, DDD_FOLLOW),
            "CHEAP": quiet_series(2.5, len(SESSIONS), step=0.01),
            "SPY": quiet_series(500.0, len(SESSIONS), step=0.2, volume=50_000_000)}
    for i, name in enumerate(FLAT):
        series = quiet_series(100.0, len(SESSIONS))
        if i < 3:
            # a 4% breakdown the Market Monitor counts: 5% down on volume
            # over the session before (the scan's own volume rule)
            series[BURST_B] = [100.0, 100.2, 94.8, 95.0, 2_000_000]
            level = 95.0
            for j in range(BURST_B + 1, len(SESSIONS)):
                c = round(level + 0.5, 2)
                series[j] = [level, round(c + 0.2, 2), round(level - 0.2, 2), c, 1_000_000]
                level = c
        bars[name] = series
    return bars


def page(bars: dict[str, list[list[float]]], days: list[str], symbols=None) -> acquisition.HTTPResult:
    """One terminal page: the named symbols' bars on ``days``, as the provider writes them."""
    rows = {s: [{"t": stamp(d), "o": o, "h": h, "l": l, "c": c, "v": int(v)}
                for d, (o, h, l, c, v) in zip(SESSIONS, series) if d in days]
            for s, series in bars.items() if symbols is None or s in symbols}
    return acquisition.HTTPResult(200, {}, acquisition.encode({"bars": rows, "next_page_token": None}))


def manifest() -> dict:
    stocks = [s for s in SYMBOLS if s != "SPY"]
    population = {"symbols": stocks, "sha256": acquisition.symbols_digest(stocks), "price_exempt": []}
    return {"schema": acquisition.SCHEMA, "assignment_id": acquisition.ASSIGNMENT,
            "populations": {"2026-09-24": dict(population), "2026-09-25": dict(population)},
            "queries": [
                {"id": "probe", "symbols": ["SPY"], "start": "2026-09-24T04:00:00Z", "end": "2026-09-25T23:59:59Z",
                 "asof": "2026-09-26", "feed": "sip", "timeframe": "1Day", "adjustment": "split", "currency": "USD",
                 "limit": 10000, "sort": "asc", "purpose": "canonical", "scope": "probe",
                 "required_sessions": ["2026-09-24", "2026-09-25"], "target_session": "2026-09-25"},
                {"id": "bulk", "symbols": SYMBOLS, "start": "2025-08-04T04:00:00Z", "end": "2026-09-25T23:59:59Z",
                 "asof": "2026-09-26", "feed": "sip", "timeframe": "1Day", "adjustment": "split", "currency": "USD",
                 "limit": 10000, "sort": "asc", "purpose": "canonical", "scope": "bulk",
                 "required_sessions": SESSIONS, "target_session": "2026-09-25"}],
            "limits": {"requests": 400, "retained_bytes": 1024 ** 3, "requests_per_minute": 20, "page_bytes": 8 * 1024 ** 2},
            "documentation": {"verified_at": "2026-09-28", "stockbars_url": "https://docs.alpaca.markets/us/reference/stockbars",
                              "faq_url": "https://docs.alpaca.markets/us/docs/market-data-faq"}}


class Transport:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def __call__(self, params, limit):
        self.calls.append(dict(params))
        return self.responses.pop(0)


def acquire(tmp_path, bars=None, responses=None):
    """A recovered package the way the owner's is: the frozen manifest, the
    ledger the acquisition wrote and its raw pages, under a private root."""
    bars = bars or market()
    frozen = manifest()
    root = tmp_path / "private" / "recovered"
    approval = {"assignment_id": acquisition.ASSIGNMENT, "manifest_sha256": acquisition.digest(acquisition.encode(frozen)),
                "storage_root": str(root), "zero_additional_cost": True, "cost_basis": "synthetic offline test",
                "sip_daily_entitlement_basis": "synthetic test only", "non_public_storage": True,
                "retention_rights_basis": "invented synthetic rows", "reviewer_retrieval_path": "regenerated locally",
                "approved_by": "synthetic test", "provider_requests_per_minute": 20}
    clock = {"now": 1_790_000_000.0}

    def tick():
        clock["now"] += 1
        return clock["now"]

    transport = Transport(responses or [page(bars, SESSIONS[-2:], ("SPY",)), page(bars, SESSIONS)])
    runner = acquisition.Acquisition(frozen, approval, root, transport=transport, clock=tick, sleep=lambda s: None)
    runner.run("probe")
    try:
        runner.run("bulk")
    except acquisition.AcquisitionError:
        pass
    return frozen, root


@pytest.fixture(scope="module")
def archive(tmp_path_factory):
    frozen, root = acquire(tmp_path_factory.mktemp("archive"))
    return backtest.load_archive(frozen, root)


@pytest.fixture(scope="module")
def result(archive):
    with network_blocked():
        return backtest.run(archive)


# ------------------------------------------------------------- archive ----
def test_the_archive_is_read_through_the_acquisitions_own_cache_offline(archive):
    assert sorted(archive.frames) == SYMBOLS
    assert archive.statuses == {s: "returned_with_bars" for s in SYMBOLS}
    assert archive.non_terminal == [] and archive.queries == ["bulk"]
    assert [d.isoformat() for d in archive.calendar] == SESSIONS
    assert archive.intended == [s for s in SYMBOLS if s != "SPY"]
    assert len(archive.frames["AAA"]) == len(SESSIONS)


def test_an_interrupted_chain_is_named_not_read_as_a_smaller_population(tmp_path):
    frozen, root = acquire(tmp_path, responses=[page(market(), SESSIONS[-2:], ("SPY",)),
                                                acquisition.HTTPResult(200, {}, acquisition.encode({"bars": {}, "next_page_token": "two"})),
                                                acquisition.HTTPResult(403, {}, b"{}")])
    archive = backtest.load_archive(frozen, root)
    assert archive.non_terminal == ["bulk"]
    assert archive.frames == {}
    assert set(archive.statuses.values()) <= {"requested", "failed"}
    with pytest.raises(backtest.BacktestError, match="sessions"):
        backtest.run(archive)


def test_storage_and_output_inside_the_checkout_are_refused(tmp_path):
    with pytest.raises(backtest.BacktestError, match="outside any Git"):
        backtest.load_archive(manifest(), backtest.ROOT / "docs")
    with pytest.raises(backtest.BacktestError, match="outside any Git"):
        backtest._outside_git(backtest.ROOT / "scratch", "the output directory")
    assert backtest._outside_git(tmp_path, "the output directory") == tmp_path.resolve()


def test_as_of_frames_carry_the_lookback_and_nothing_after_the_session(archive):
    session = date.fromisoformat(SESSIONS[BURST_A])
    frames = backtest.as_of(archive, session, backtest.PRODUCTION_LOOKBACK)
    for symbol, df in frames.items():
        dates = [d.date().isoformat() for d in df.index]
        assert dates[-1] == SESSIONS[BURST_A], symbol
        assert dates[0] == SESSIONS[BURST_A - backtest.PRODUCTION_LOOKBACK], symbol
        assert len(df) == backtest.PRODUCTION_LOOKBACK + 1
    short = backtest.as_of(archive, session, 20)
    assert all(len(df) == 21 for df in short.values())
    # a name with no bar in the span is absent, as an unanswered name is live
    early = backtest.as_of(archive, date.fromisoformat(SESSIONS[5]), 3)
    assert all(len(df) == 4 for df in early.values()) and sorted(early) == SYMBOLS


# ------------------------------------------------------------ decisions ----
def test_the_production_policy_takes_the_green_tickets_and_refuses_the_red_one(result):
    nights = {r["session"]: r for r in result["nights"][backtest.PRODUCTION]}
    assert result["evaluated"]["count"] == len(SESSIONS) - backtest.PRODUCTION_LOOKBACK
    a, c, b = (nights[SESSIONS[i]] for i in (BURST_A, BURST_C, BURST_B))
    assert a["regime"]["verdict"] == "green" and a["trades"] == ["AAA"] and a["grades"] == {"A+": 1}
    assert c["regime"]["verdict"] == "green" and c["trades"] == ["CCC"] and c["slots_held"] == 1
    assert b["regime"]["verdict"] == "red" and b["regime"]["down4"] == 3 and b["trades"] == []
    assert b["grades"] == {"A+": 1} and b["eligible_plans"] == 0
    assert all(r["price_excluded"] == 1 and r["counted"] == COUNTED for r in nights.values())
    assert [(p["ticker"], p["date"], p["regime"]) for p in result["outcomes"][backtest.PRODUCTION]["picks"]] == \
        [("AAA", SESSIONS[BURST_A], "green"), ("CCC", SESSIONS[BURST_C], "green")]


def test_the_counterfactual_block_is_the_same_market_without_the_gate(result):
    picks = result["outcomes"][backtest.NO_GATE]["picks"]
    assert [(p["ticker"], p["regime"]) for p in picks] == [("AAA", "green"), ("CCC", "green"), ("BBB", "red")]
    nights = {r["session"]: r for r in result["nights"][backtest.NO_GATE]}
    assert nights[SESSIONS[BURST_B]]["regime"]["verdict"] == "red", "the night's own regime is still recorded"
    assert nights[SESSIONS[BURST_B]]["trades"] == ["BBB"]


def test_outcomes_are_the_records_own_walk_over_the_whole_archive(result):
    production = result["outcomes"][backtest.PRODUCTION]["summary"]
    assert (production["plans"], production["settled"], production["wins"], production["losses"]) == (2, 2, 2, 0)
    assert production["sum_r"] == round(AAA_R + CCC_R, 2) == 2.78
    assert production["readable"] is False and production["win_rate"] is None
    rows = {r["ticker"]: r for r in result["outcomes"][backtest.PRODUCTION]["rows"]}
    assert rows["AAA"]["r"] == AAA_R == 1.68 and rows["AAA"]["status"] == "stopped"
    assert rows["CCC"]["r"] == CCC_R == 1.1 and rows["CCC"]["status"] == "exit"
    ungated = result["outcomes"][backtest.NO_GATE]
    assert (ungated["summary"]["settled"], ungated["summary"]["wins"], ungated["summary"]["losses"]) == (3, 2, 1)
    assert {r["ticker"]: r["r"] for r in ungated["rows"]}["BBB"] == BBB_R == -0.81
    assert ungated["by_regime"]["red"]["sum_r"] == BBB_R and ungated["by_regime"]["green"]["settled"] == 2
    assert ungated["by_grade"]["A+"]["plans"] == 3


def test_a_slot_cap_of_one_is_path_dependent_on_the_open_model_plan(archive):
    with network_blocked():
        out = backtest.run(archive, account=plan.Account(max_open_positions=1))
    nights = {r["session"]: r for r in out["nights"][backtest.PRODUCTION]}
    assert nights[SESSIONS[BURST_A]]["trades"] == ["AAA"]
    assert nights[SESSIONS[BURST_C]]["trades"] == [] and nights[SESSIONS[BURST_C]]["cut"] == {"slot_cap": 1}
    assert [p["ticker"] for p in out["outcomes"][backtest.PRODUCTION]["picks"]] == ["AAA"]


def test_new_replays_reserve_original_model_principal_before_admitting_tickets(monkeypatch):
    row = {"ticker": "NEW", "scan": "burst", "grade": "A+", "grade_mechanical": "A+", "score": 10,
           "vetoes": [], "close": 50, "low": 49.95, "high": 50.20, "open": 49.98,
           "prev_close": 47, "gain_pct": 6.38}
    measured = backtest.Measurement(date(2026, 10, 8), {}, {}, {"verdict": "green", "size_multiplier": 1.0}, [row], {})
    monkeypatch.setattr(record, "open_plans", lambda *args: [
        {"ticker": "OLD", "status": "unmeasured", "entry_ref": 100, "limit": 100, "shares": 20}])
    rec, decision = backtest.decide(measured, plan.Account(equity=2000), record.empty(), gate=True)
    assert decision["eligible_plans"] == 1 and decision["slots_held"] == 1
    assert decision["trades"] == [] and decision["cut"] == {"equity": 1}
    assert rec["picks"] == [] and row["plan"]["order_json"] is None


# ----------------------------------------------------------- equivalence ----
def test_a_shortened_lookback_is_held_to_the_runs_own_on_every_overlapping_session(archive):
    with network_blocked():
        out = backtest.run(archive, lookback=130)
    check = out["lookback"]["equivalence"]
    assert check["required"] and check["status"] == "PASS" and check["differences"] == []
    assert check["compared"] == len(SESSIONS) - backtest.PRODUCTION_LOOKBACK
    assert out["evaluated"]["count"] == len(SESSIONS) - 130
    # the shorter lookback reaches DDD's night, 138 sessions before the archive
    # ends: further back than the published scorecard's window, and still read
    nights = {r["session"]: r for r in out["nights"][backtest.PRODUCTION]}
    assert nights[SESSIONS[BURST_D]]["regime"]["verdict"] == "green" and nights[SESSIONS[BURST_D]]["trades"] == ["DDD"]
    summary = out["outcomes"][backtest.PRODUCTION]["summary"]
    assert (summary["plans"], summary["settled"], summary["not_filled"]) == (3, 2, 1)
    assert summary["sum_r"] == round(AAA_R + CCC_R, 2)
    rows = {r["ticker"]: r for r in out["outcomes"][backtest.PRODUCTION]["rows"]}
    assert rows["DDD"]["bucket"] == "not_filled" and rows["DDD"]["r"] is None
    assert len(SESSIONS) - 1 - BURST_D > record.SCORECARD_SESSIONS


def test_a_lookback_too_short_for_the_checklist_fails_the_equivalence_check(archive):
    with network_blocked():
        out = backtest.run(archive, lookback=20, limit=30)
    check = out["lookback"]["equivalence"]
    assert check["status"] == "FAIL" and check["differences"]
    diff = check["differences"][0]
    assert diff["shortened"] != diff["production"]


def test_the_full_lookback_needs_no_check_and_a_longer_one_is_refused(result, archive):
    assert result["lookback"]["equivalence"] == {"required": False, "compared": 0, "differences": [],
                                                 "status": "not required"}
    with pytest.raises(backtest.BacktestError, match="lookback"):
        backtest.run(archive, lookback=backtest.PRODUCTION_LOOKBACK + 1)


# --------------------------------------------------------------- outputs ----
def test_the_summary_carries_counts_and_r_but_no_price_and_no_ticker(result):
    text = backtest.summary_text(result)
    assert "PRODUCTION POLICY" in text and "COUNTERFACTUAL" in text and "NOT RUN" in text
    assert "settled 2: wins 2, losses 0" in text and "sum R 2.78" in text
    for forbidden in ("124.21", "121.42", "126.47", "125.0", "AAA", "CCC", "BBB", "$"):
        assert forbidden not in text, forbidden
    assert "regimes: {'green'" in text and "'red'" in text


def test_the_cli_writes_the_private_record_and_the_pasteable_summary(tmp_path, capsys):
    frozen, root = acquire(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_bytes(acquisition.encode(frozen))
    out = tmp_path / "private" / "out"
    with network_blocked():
        code = backtest.main(["--manifest", str(manifest_path), "--storage", str(root), "--output", str(out),
                              "--sessions", "12"])
    assert code == 0
    written = json.loads((out / "backtest.json").read_text())
    assert written["evaluated"]["count"] == 12 and written["evaluated"]["through"] == SESSIONS[-1]
    assert written["outcomes"][backtest.PRODUCTION]["summary"]["plans"] == 0, "the last twelve sessions hold no burst"
    summary = (out / "summary.txt").read_text()
    assert summary == capsys.readouterr().out and "no price in this summary" in summary
    assert backtest.main(["--manifest", str(manifest_path), "--storage", str(backtest.ROOT), "--output", str(out)]) == 2


# ---------------------------------------------------- the record's retention ----
def test_the_files_retention_cannot_drop_a_plan_the_replay_made(archive, monkeypatch):
    """record.MAX_PICKS is a nightly file's policy. Set to two, it would keep
    the two newest of the counterfactual's three picks and the walk would
    score a population the replay did not issue; the replay passes a bound
    its picks cannot reach, and refuses the mismatch outright."""
    monkeypatch.setattr(record, "MAX_PICKS", 2)
    with network_blocked():
        out = backtest.run(archive)
    ungated = out["outcomes"][backtest.NO_GATE]
    assert ungated["tickets_issued"] == ungated["summary"]["plans"] == len(ungated["picks"]) == 3
    assert out["outcomes"][backtest.PRODUCTION]["tickets_issued"] == 2


def test_the_retention_bound_is_over_every_ticket_a_run_could_write():
    assert backtest.retention_bound(29, plan.Account()) == max(record.MAX_PICKS, 29 * plan.DEFAULT_MAX_OPEN_POSITIONS)
    assert backtest.retention_bound(1, plan.Account()) == record.MAX_PICKS
    assert backtest.retention_bound(400, plan.Account(max_open_positions=2)) == 800


def test_a_record_that_loses_a_ticket_is_refused_not_scored(archive, monkeypatch):
    kept = record.append

    def dropping(rec, session, picks, regime="green", **kw):
        return kept(rec, session, picks, regime, max_picks=2)
    monkeypatch.setattr(record, "append", dropping)
    with network_blocked(), pytest.raises(backtest.BacktestError, match="3 tickets issued but 2 plans recorded"):
        backtest.run(archive)


def test_append_keeps_the_published_retention_by_default_and_a_wider_one_on_request():
    picks = [pick(ticker=f"T{i}") for i in range(3)]
    rec = record.append(record.empty(), "2026-09-01", picks)
    assert len(rec["picks"]) == 3
    assert len(record.append(record.empty(), "2026-09-01", picks, max_picks=2)["picks"]) == 2
    for bad in (0, True, 2.5):
        with pytest.raises(ValueError, match="max_picks"):
            record.append(record.empty(), "2026-09-01", picks, max_picks=bad)


# ------------------------------------------------------- the record's window ----
def test_scorecard_rows_read_the_published_window_by_default_and_a_wider_one_on_request():
    old, recent = "2026-01-05", "2026-09-01"
    rec = {"picks": [pick(ticker="OLD", date=old), pick(ticker="NEW", date=recent)]}
    frames = {}
    default = record.scorecard_rows(rec, frames, "2026-09-09")
    assert [r["ticker"] for r in default] == ["NEW"]
    wide = record.scorecard_rows(rec, frames, "2026-09-09", window_sessions=200)
    assert [r["ticker"] for r in wide] == ["OLD", "NEW"]
    assert record.summarize_scorecard(wide)["plans"] == 2
