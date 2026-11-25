"""The candidate checks (src/candidate_checks.py): SEC filing flags, the
earnings estimate and its recent 8-K items, and the iex cross-check, for up to
80 names a night -- the tickets, the listed setups, the reviewed and admitted
trade-band bursts and the also-quiet coils -- over ONE shared SEC reader and
ONE iex batch, as flags for a reader that change no plan, ticket or order.

Every clock is pinned; every SEC answer is the FakeSec double's and every iex
bar a frame built here."""
from __future__ import annotations

import copy
import json
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from src import candidate_checks as CC
from src import cross_check, earnings_risk, history, issuer_evidence, report, sec_flags
from tests.fakes import FakeSec

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "tests" / "fixtures" / "page"
NOW = datetime(2026, 9, 10, 22, 30, tzinfo=timezone.utc)


def page(name: str) -> dict:
    data = json.loads((PAGE / f"{name}.json").read_text())
    data.pop("fixture", None)
    return data


def bar_frame(session: str, *, close=105.0, volume=60_000, prior_volume=30_000, open_=100.0) -> pd.DataFrame:
    day = date.fromisoformat(session)
    from src import sessions
    prev = sessions.previous_session(day)
    return pd.DataFrame({"Open": [99.0, open_], "High": [101.0, 106.0], "Low": [98.0, 99.5],
                         "Close": [100.0, close], "Volume": [prior_volume, volume]},
                        index=pd.DatetimeIndex([pd.Timestamp(prev), pd.Timestamp(day)]))


def clone(row: dict, ticker: str, rank: int, *, grade="A", selected=False, vetoes=(), admitted=True) -> dict:
    out = copy.deepcopy(row)
    out.update(ticker=ticker, rank=rank, grade_mechanical=grade, grade=grade, vetoes=list(vetoes), plan=None)
    out["review_selection"] = {**out.get("review_selection", {}), "selected": selected}
    out["admission"] = {**out.get("admission", {}), "admitted": admitted}
    return out


def with_candidates(n: int, *, base: str = "full") -> dict:
    """``base`` with ``n`` admitted grade-A bursts appended after its own, ranked after them."""
    data = page(base)
    template = next(b for b in data["bursts"] if b["ticker"] == "AMD")
    last = max(b["rank"] for b in data["bursts"])
    data["bursts"] += [clone(template, f"C{i:03d}", last + 1 + i) for i in range(n)]
    return data


def iex_for(data: dict, names, **bar) -> dict:
    session = data["run"]["session"]
    tickers = CC.symbols(names)
    return {"requested": tickers, "frames": {t: bar_frame(session, **bar) for t in tickers}, "dropped": set(),
            "exception": None, "attempts": 1}


def sip_for(data: dict, names) -> dict:
    session = data["run"]["session"]
    return {t: bar_frame(session) for t in CC.symbols(names)}


def register(sec: FakeSec, tickers, session: str, offset: int = 40, start_cik: int = 5000) -> None:
    for i, t in enumerate(tickers):
        sec.quarterly(t, start_cik + i, f"{t} Corp", session, offset)


def checked(data: dict, block: dict) -> list[str]:
    return CC.faults({**data, "candidate_checks": block})


# ------------------------------------------------------------ the names ---
def burst(ticker, rank, grade="A", *, selected=False, vetoes=(), admitted=True, plan=None):
    return {"ticker": ticker, "rank": rank, "grade_mechanical": grade, "vetoes": list(vetoes), "plan": plan,
            "review_selection": {"selected": selected}, "admission": {"admitted": admitted}}


ORDER = {"eligible": True, "action": "place_buy_stop"}


def test_the_names_are_the_roles_in_order_each_by_rank_and_each_once():
    bursts = [burst("T1", 3, "A+", plan=ORDER, selected=True), burst("R1", 2, "B", selected=True),
              burst("C2", 6), burst("C1", 4), burst("V1", 1, vetoes=["up_days"]), burst("X1", 5, "B"),
              burst("N1", 7, admitted=False)]
    watch = {"top": [{"ticker": "S1", "plan": ORDER}, {"ticker": "L1", "plan": {"eligible": False}}],
             "also_quiet": [{"ticker": "Q1"}, {"ticker": "L1"}]}
    names = CC.names_of(bursts, ["T1"], watch, ["A+", "A"])
    assert [(n["stage"], n["ticker"], n["role"], n["rank"]) for n in names] == [
        ("burst", "T1", "ticket", 3), ("anticipation", "S1", "ticket", 1), ("anticipation", "L1", "listed", 2),
        ("burst", "R1", "reviewed", 2), ("burst", "C1", "candidate", 4), ("burst", "C2", "candidate", 6),
        ("anticipation", "Q1", "also_quiet", 1)]
    # a vetoed burst, one below the band and one the admission stops are not candidates
    assert not {"V1", "X1", "N1"} & {n["ticker"] for n in names}


def test_a_shape_a_record_should_not_carry_is_no_name_and_never_a_raise():
    assert CC.names_of(None, None, None, None) == []
    assert CC.names_of([1, {"ticker": 5}, {"ticker": "A", "rank": "x", "grade_mechanical": "A"}], "x",
                       {"top": "x", "also_quiet": [None]}, ["A"]) == \
        [{"stage": "burst", "ticker": "A", "role": "candidate", "rank": None}]


@pytest.mark.parametrize("n, rows, unchecked", [(CC.MAX_NAMES - 5, CC.MAX_NAMES, {}),
                                                (CC.MAX_NAMES - 4, CC.MAX_NAMES, {"candidate": 1})])
def test_the_first_eighty_names_get_rows_and_the_rest_are_counted_by_role(fake_sec, n, rows, unchecked):
    """full carries 5 names of its own (a ticket, a listed setup, three reviewed bursts)."""
    data = with_candidates(n)
    names = CC.record_names(data)
    assert len(names) == n + 5
    block = CC.collect(data, reader=CC.SecReader(fake_sec, now=NOW), iex=iex_for(data, names), frames=sip_for(data, names))
    assert len(block["rows"]) == rows and block["unchecked"] == unchecked
    assert block["names"] == {"ticket": 1, "listed": 1, "reviewed": 3, "candidate": n}
    assert checked(data, block) == []
    # the validator re-derives the list from the record: a row dropped or moved is named
    forged = copy.deepcopy(block)
    forged["rows"] = forged["rows"][:-1]
    assert "candidate_checks rows are not the record's names" in checked(data, forged)
    forged = copy.deepcopy(block)
    forged["unchecked"] = {}
    assert unchecked == {} or "candidate_checks counts by role are not the record's names" in checked(data, forged)


@pytest.mark.parametrize("name", ["red", "yellow", "full", "next"])
def test_every_light_gets_rows_for_its_listed_setups_and_admitted_bursts(name):
    data = page(name)
    block = data["candidate_checks"]
    assert CC.faults(data) == []
    roles = {r["role"] for r in block["rows"]}
    expected = {n["role"] for n in CC.record_names(data)}
    assert roles == expected and block["rows"]
    if data["breadth"]["regime"]["verdict"] == "red":
        # a RED night publishes no ticket, and its listed setups and admitted bursts are still read
        assert "ticket" not in roles and {"listed", "candidate"} <= roles


# ------------------------------------------------------- the SEC reader ---
def test_eighty_names_cost_one_sec_request_each_and_the_mapping_once(fake_sec):
    data = with_candidates(CC.MAX_NAMES - 5)
    names = CC.record_names(data)
    register(fake_sec, [n["ticker"] for n in names if n["ticker"].startswith("C")], data["run"]["session"])
    for ticker, (cik, label, offset, accepted) in {"AAPL": (320193, "Apple Inc.", 2, "20:30:00"),
                                                    "AMD": (2488, "ADVANCED MICRO DEVICES INC", 40, "11:00:00")}.items():
        fake_sec.quarterly(ticker, cik, label, data["run"]["session"], offset, accepted=accepted)
    reader = CC.SecReader(fake_sec, now=NOW)
    tickets = earnings_risk.tickets_of(data["bursts"], data["trades"], data["watchlist"]["top"])
    earn = earnings_risk.collect(tickets, data["run"]["session"], fetch=reader, now=NOW)
    flags = sec_flags.collect(sec_flags.names_of(tickets, data["watchlist"]["top"]), data["run"]["session"],
                              fetch=reader, now=NOW)
    block = CC.collect(data, reader=reader, iex=iex_for(data, names), frames=sip_for(data, names))
    assert len(fake_sec.calls) == len(set(fake_sec.calls)), "an SEC URL was asked twice"
    assert fake_sec.calls.count(issuer_evidence.MAPPING_URL) == 1 and fake_sec.calls[0] == issuer_evidence.MAPPING_URL
    mapped = sum(1 for n in names if n["ticker"] in fake_sec.issuers)
    assert len(fake_sec.calls) == 1 + mapped
    # each block counts the requests it made, and an answer the reader already held is not one
    assert earn["requests"] + flags["requests"] + block["requests"]["sec"] == len(fake_sec.calls) == reader.made()
    assert block["requests"]["sec_reused"] >= 3
    assert sum(1 for r in block["rows"] if r["earnings"]["reason"] is None) == mapped


def test_the_tickets_are_read_first_and_a_spent_deadline_leaves_the_rest_unknown(fake_sec):
    data = with_candidates(20)
    names = CC.record_names(data)
    register(fake_sec, [n["ticker"] for n in names], data["run"]["session"])
    clock = {"t": 0.0}

    def tick():
        clock["t"] += 1.0
        return clock["t"]
    reader = CC.SecReader(fake_sec, now=NOW, deadline_seconds=8, monotonic=tick)
    tickets = earnings_risk.tickets_of(data["bursts"], data["trades"], data["watchlist"]["top"])
    earnings_risk.collect(tickets, data["run"]["session"], fetch=reader, now=NOW)
    block = CC.collect(data, reader=reader, iex=iex_for(data, names), frames=sip_for(data, names))
    ticket = block["rows"][0]
    assert ticket["role"] == "ticket" and ticket["earnings"]["reason"] is None
    late = [r for r in block["rows"] if r["sec"]["reason"] == "time_budget"]
    assert late and all(r["sec"]["state"] == "unknown" and r["earnings"]["verdict"] == "unknown"
                        and r["earnings"]["error"] == "time_budget" for r in late)
    assert all(r["role"] != "ticket" for r in late) and checked(data, block) == []
    assert "Unknown, and unknown is never clear" in block["sentence"]


def test_a_spent_request_budget_leaves_the_rest_unknown_and_names_it(fake_sec):
    data = with_candidates(20)
    names = CC.record_names(data)
    register(fake_sec, [n["ticker"] for n in names], data["run"]["session"])
    reader = CC.SecReader(fake_sec, now=NOW, max_requests=6)
    block = CC.collect(data, reader=reader, iex=iex_for(data, names), frames=sip_for(data, names))
    over = [r for r in block["rows"] if r["sec"]["reason"] == "request_budget"]
    assert over and reader.made() == 6 and len(fake_sec.calls) == 6
    assert all(r["earnings"]["error"] == "request_budget" and r["sec"]["state"] == "unknown" for r in over)
    assert checked(data, block) == []


def test_the_reader_keeps_a_failure_so_both_readings_of_a_name_say_the_same(fake_sec):
    fake_sec.issuer("AAA", 1, "AAA Inc.", [], start="2024-01-02")
    fake_sec.fail["CIK0000000001"] = "http_error"
    reader = CC.SecReader(fake_sec, now=NOW)
    for _ in range(3):
        with pytest.raises(earnings_risk.SourceError):
            reader(earnings_risk.SUBMISSIONS_URL.format(cik=1))
    assert reader.made() == 1 and reader.reused == 2 and len(fake_sec.calls) == 1


def test_a_refusal_before_a_request_went_out_is_not_a_request_and_not_kept():
    class Budget:
        requests = 0

    def base(url):
        raise earnings_risk.SourceError("time_budget")   # the transport refused before sending
    base.budget = Budget()
    reader = CC.SecReader(base, now=NOW)
    for _ in range(2):
        with pytest.raises(earnings_risk.SourceError):
            reader("https://www.sec.gov/files/company_tickers_exchange.json")
    assert reader.made() == 0 and reader.reused == 0


# ------------------------------------------------------- the iex batch ---
def test_one_iex_batch_reads_every_name_and_one_that_failed_once_is_retried(fake_alpaca, monkeypatch):
    from src import market_data
    monkeypatch.setattr(market_data, "RETRY_WAIT_SECONDS", 0)
    data = with_candidates(CC.MAX_NAMES - 5)
    names = CC.record_names(data)
    tickers = CC.symbols(names)
    for t in tickers:
        fake_alpaca.add_history(t, bar_frame(data["run"]["session"]))
    client = market_data.get_clients()
    real = type(client).get_stock_bars
    failed = {"n": 0}

    def flaky(self, request):
        if failed["n"] == 0:
            failed["n"] += 1
            raise ConnectionError("one dropped connection")
        return real(self, request)
    monkeypatch.setattr(type(client), "get_stock_bars", flaky)
    got = CC.read_iex(client, tickers, date.fromisoformat(data["run"]["session"]))
    assert len(tickers) == CC.MAX_NAMES and got["attempts"] == 2 and got["dropped"] == set()
    assert len(fake_alpaca.bar_requests) == 1 and set(got["frames"]) == set(tickers)
    assert all(getattr(r, "feed", None).value == cross_check.FEED for r in fake_alpaca.bar_requests)


def test_a_batch_that_fails_twice_is_iex_unavailable_on_every_row_never_no_bar(fake_alpaca, monkeypatch):
    from src import market_data
    monkeypatch.setattr(market_data, "RETRY_WAIT_SECONDS", 0)
    data = page("full")
    names = CC.record_names(data)
    fake_alpaca.raise_on_bars = ConnectionError("down")
    session = date.fromisoformat(data["run"]["session"])
    got = CC.read_iex(market_data.get_clients(), CC.symbols(names), session)
    assert got["dropped"] == set(CC.symbols(names)) and got["attempts"] == 2
    words = "iex_unavailable (IexBatchFailed)"
    for name in names:
        assert CC._cross(name, got, sip_for(data, names), session)["reason"] == words
    # the tickets' own block reads the same batch, and names it the same way
    tickets = earnings_risk.tickets_of(data["bursts"], data["trades"], data["watchlist"]["top"])
    block = cross_check.collect(None, tickets, sip_for(data, names), session, fetch=CC.ticket_fetch(got))
    assert {r["reason"] for r in block["rows"]} == {words}


def test_a_refused_batch_is_every_rows_with_its_type_and_a_name_outside_it_is_not_checked():
    data = page("full")
    names = CC.record_names(data)
    session = date.fromisoformat(data["run"]["session"])
    refused = {"requested": CC.symbols(names), "frames": {}, "dropped": set(), "exception": PermissionError("no"),
               "attempts": 1}
    assert CC._cross(names[0], refused, {}, session)["reason"] == "iex_unavailable (PermissionError)"
    outside = {**refused, "exception": None, "requested": []}
    assert CC._cross(names[0], outside, {}, session) == {"result": "unknown", "reason": "not_checked", "differences": None}


# ---------------------------------------------- the night, flag only ------
@pytest.fixture
def night_market(fake_alpaca, fake_anthropic, seed):
    from tests.test_pipeline import CLAUDE_A_PLUS, a_plus_frame, base_frames
    from tests.test_watchlist import coil
    from tests.synthetic import make_ohlcv
    fake_anthropic.set_payload(dict(CLAUDE_A_PLUS))
    # six A+ bursts against four model slots: the ones the slot cap cuts are names no
    # ticket's block reads, so the candidate checks read them on their own
    for ticker in BURSTS:
        fake_alpaca.add_history(ticker, a_plus_frame())
    fake_alpaca.add_history("COIL", coil())
    for name, df in base_frames(11, seed).items():
        fake_alpaca.add_history(name, df)
    fake_alpaca.add_history("SPY", make_ohlcv("base", seed=[seed, 999], days=260))
    return list(BURSTS) + ["COIL"] + [f"B{chr(65 + i)}{chr(65 + i)}" for i in range(11)]


BURSTS = ("AAA", "AAB", "AAC", "AAD", "AAE", "AAF")


def run_night(tmp_path, tickers, name="docs"):
    from src import pipeline
    from tests.test_pipeline import EVENING
    docs = tmp_path / name
    rep = pipeline.run_evening(tickers=tickers, docs=docs, now=EVENING)
    data = json.loads((docs / pipeline.DATA_FILE).read_text())
    orders = json.loads((docs / "orders.json").read_text()) if (docs / "orders.json").exists() else None
    return rep, data, orders, docs


DECISIONS = ("bursts", "trades", "beyond_cap", "watchlist", "cash_budget", "funnel", "open_plans", "scorecard",
             "closest_miss", "cover")


def decisions(data, orders):
    out = {k: data[k] for k in DECISIONS}
    out["run"] = {k: data["run"][k] for k in ("earnings", "sec_flags", "cross_check", "reads", "status")}
    if orders is not None:
        out["orders"] = {k: orders[k] for k in ("tickets", "trade_allowed", "reasons", "night_checks", "mode")}
        for t in out["orders"]["tickets"]:
            t.pop("evidence", None)
    out = json.loads(json.dumps(out))
    # the reader double bills a cache write on the process's first call and reads after it, so the
    # three nights' token classes differ by the order they ran in; nothing here reads them
    for b in out["bursts"]:
        b.pop("reader_usage", None)
    return out


def flag_everything(real):
    """The night's block with every row no run.* row stands behind flagged on all three checks."""
    def collect(data, **kwargs):
        block = real(data, **kwargs)
        runs = CC._run_rows(data)
        rows = []
        for r in block["rows"]:
            if not any((r["stage"], r["ticker"]) in runs[k] for k in runs):
                r = copy.deepcopy(r)
                r["sec"] = {"state": "flagged", "reason": None, "filings_count": 1,
                            "filings": [{"accession": "0000000001-26-000001", "filing_date": data["run"]["session"],
                                         "form": "SC TO-T", "items": []}]}
                r["cross_check"] = {"result": "fail", "reason": "differ: close",
                                    "differences": {"open": 0.0, "high": 0.0, "low": 0.0, "close": 9.0, "volume": 0.0}}
            rows.append(r)
        return CC._block(data, CC.record_names(data), rows, block["requests"], block["shed"])
    return collect


def test_the_block_is_a_flag_only_every_decision_reads_the_same_whatever_it_says(night_market, fake_resend, tmp_path,
                                                                                    monkeypatch):
    rep, data, orders, _ = run_night(tmp_path, night_market, "real")
    assert rep.exit_code() == 0 and data["candidate_checks"]["rows"] and report.validate(data) is None
    roles = {r["role"] for r in data["candidate_checks"]["rows"]}
    assert {"ticket", "reviewed"} <= roles and data["beyond_cap"], roles
    real = CC.collect
    monkeypatch.setattr(CC, "collect", flag_everything(real))
    _, flagged, flagged_orders, _ = run_night(tmp_path, night_market, "flagged")
    assert any(r["sec"]["state"] == "flagged" for r in flagged["candidate_checks"]["rows"] if r["role"] != "ticket")

    def broken(data, **kwargs):
        raise RuntimeError("a bug in the candidate checks")
    monkeypatch.setattr(CC, "collect", broken)
    rep_b, failed, failed_orders, _ = run_night(tmp_path, night_market, "failed")
    assert rep_b.exit_code() == 0 and report.validate(failed) is None
    alone = [r for r in failed["candidate_checks"]["rows"] if r["role"] in ("reviewed", "candidate")]
    assert alone and all(r["sec"]["reason"] == "not_checked" for r in alone)
    assert decisions(data, orders) == decisions(flagged, flagged_orders) == decisions(failed, failed_orders)


def test_the_night_reads_each_sec_url_once_and_its_ticket_rows_agree(night_market, fake_resend, fake_sec, fake_alpaca,
                                                                    tmp_path):
    from tests.test_pipeline import SESSION
    register(fake_sec, [*BURSTS, "COIL", "BAA", "BBB"], SESSION)
    rep, data, _, _ = run_night(tmp_path, night_market)
    assert rep.exit_code() == 0
    assert len(fake_sec.calls) == len(set(fake_sec.calls)) and fake_sec.calls.count(issuer_evidence.MAPPING_URL) == 1
    block = data["candidate_checks"]
    assert CC.faults(data) == [] and block["rows"][0]["ticker"] == "AAA" and block["rows"][0]["role"] == "ticket"
    run = data["run"]
    total = run["earnings"]["requests"] + run["sec_flags"]["requests"] + block["requests"]["sec"]
    assert total == len(fake_sec.calls)
    # the names no ticket's block reads were read by the candidate checks themselves
    alone = [r for r in block["rows"] if r["role"] in ("reviewed", "candidate")]
    assert alone and all(r["earnings"]["reason"] is None and r["sec"]["state"] == "clear"
                         and r["cross_check"]["result"] != "unknown" for r in alone)
    assert block["requests"]["sec"] == len(alone)
    # one iex batch a night, shared with the tickets' own cross-check
    iex = [r for r in fake_alpaca.bar_requests if getattr(getattr(r, "feed", None), "value", None) == "iex"]
    assert block["requests"]["iex"] == 1 and len(iex) == 1


# ------------------------------------------------------------- agreement ---
@pytest.mark.parametrize("part, change, words", [
    ("earnings", {"verdict": "estimate_outside", "reason": None}, "earnings"),
    ("sec", {"state": "clear", "filings": [], "filings_count": 0}, "sec"),
    ("cross_check", {"result": "fail", "reason": "differ: close",
                     "differences": {"open": 0.0, "high": 0.0, "low": 0.0, "close": 9.0, "volume": 0.0}}, "cross_check"),
])
def test_a_tickets_row_that_disagrees_with_its_own_run_row_is_named(part, change, words):
    data = page("full")
    row = data["candidate_checks"]["rows"][0]
    assert row["role"] == "ticket"
    row[part] = {**row[part], **change}
    if part == "earnings":
        row["earnings"]["sentence"] = earnings_risk.sentence({**row["earnings"], "window":
                                                              earnings_risk.window(data["run"]["session"])})
    found = CC.faults(data)
    assert f"candidate_checks {words} for AAPL is not its run.* row's" in found, found


def test_a_listed_setups_sec_reading_is_held_to_its_run_sec_flags_row():
    data = page("full")
    listed = next(r for r in data["candidate_checks"]["rows"] if r["role"] == "listed")
    listed["sec"] = {"state": "clear", "reason": None, "filings": [], "filings_count": 0}
    assert f"candidate_checks sec for {listed['ticker']} is not its run.* row's" in CC.faults(data)


# --------------------------------------------------------------- bounds ---
def max_row(data: dict, name: dict) -> dict:
    """A row at every bound the module keeps: four flagged filings, four
    material items, the longest earnings sentence a row can carry."""
    session = data["run"]["session"]
    row = CC._row_of(name, {"earnings": {}, "sec_flags": {}, "cross_check": {}}, session,
                     earnings_risk.window(session), NOW)
    filing = {"accession": "0000000001-26-000001", "filing_date": session, "form": "8-K", "items": list(sec_flags.ITEMS)}
    row["sec"] = {"state": "flagged", "reason": None, "filings": [filing] * CC.MAX_FILINGS, "filings_count": 30}
    material = {"item": "1.01", "title": earnings_risk.ITEM_TITLES["1.01"], "form": "8-K/A",
                "accession": "0000000001-26-000002", "filing_date": session, "accepted_at": "2026-09-10T21:00:00Z",
                "placement": "before_signal_close"}
    row["items"] = {"status": "material", "reason": None, "material": [material] * CC.MAX_MATERIAL,
                    "material_count": 40, "codes": sorted(earnings_risk.ITEM_TITLES), "count": 8, "unread": 3,
                    "after_hold": 1, "unretained_material": 2}
    projection = {"date": session, "low": session, "high": session, "from_accession": "0000000001-25-000003",
                  "from_filing_date": "2025-09-11", "slack_days": earnings_risk.ESTIMATE_SLACK_DAYS,
                  "timing_last_year": "before_open"}
    earn = {"verdict": "overdue", "reason": None, "error": None, "placement": "any_day", "projection": projection,
            "observed": None}
    row["earnings"] = {**earn, "sentence": earnings_risk.sentence(
        {**earn, "window": earnings_risk.window(session)}, hold=CC._hold(name["role"]))}
    row["cik"] = 1234567
    row["source"] = {"bytes": 2_000_000, "retrieved_at": "2026-09-10T22:30:00Z", "sha256": "a" * 64}
    row["cross_check"] = {"result": "pass", "reason": None,
                          "differences": {k: 0.123456789012345 for k in ("open", "high", "low", "close", "volume")}}
    return row


def test_eighty_rows_at_their_bounds_fit_the_block_and_shedding_never_takes_a_ticket(monkeypatch):
    data = with_candidates(CC.MAX_NAMES)
    names = CC.record_names(data)[:CC.MAX_NAMES]
    runs = CC._run_rows(data)
    rows = [CC._row_of(n, runs, data["run"]["session"], earnings_risk.window(data["run"]["session"]), NOW)
            if any((n["stage"], n["ticker"]) in runs[k] for k in runs) else max_row(data, n) for n in names]
    block = CC._bounded(data, CC.record_names(data), list(rows), {"sec": 0, "sec_reused": 0, "iex": 0})
    assert block["shed"] == 0 and len(CC._compact(block)) <= CC.MAX_BLOCK_BYTES
    # under half the bound, rows are shed from the end, never one a run.* row stands behind
    bound = len(CC._compact(block)) // 2
    monkeypatch.setattr(CC, "MAX_BLOCK_BYTES", bound)
    data["rules"]["candidate_checks"]["max_block_bytes"] = bound
    shed = CC._bounded(data, CC.record_names(data), list(rows), {"sec": 0, "sec_reused": 0, "iex": 0})
    assert shed["shed"] > 0 and len(CC._compact(shed)) <= bound
    kept_runs = [r for r in shed["rows"] if any((r["stage"], r["ticker"]) in runs[k] for k in runs)]
    assert [r["ticker"] for r in kept_runs] == [r["ticker"] for r in rows if r in kept_runs] and kept_runs
    assert all(r == next(x for x in rows if x["ticker"] == r["ticker"]) for r in kept_runs)
    tail = shed["rows"][-shed["shed"]:]
    assert all(r["sec"]["reason"] == "not_checked" and r["earnings"]["reason"] == "not_checked" for r in tail)
    assert checked(data, shed) == [] and f"{shed['shed']} shed to stay within" in shed["sentence"]
    # and a block past its archived bound is named
    data["rules"]["candidate_checks"]["max_block_bytes"] = len(CC._compact(shed)) - 1
    assert "candidate_checks is over its archived byte bound" in checked(data, shed)


def test_the_block_sentence_lists_at_most_three_names_a_flag_however_many_are_flagged():
    data = with_candidates(CC.MAX_NAMES)
    names = CC.record_names(data)[:CC.MAX_NAMES]
    rows = [max_row(data, n) for n in names]
    for r in rows:
        r["earnings"] = {**r["earnings"], "verdict": "estimate_inside"}
    block = CC._block(data, CC.record_names(data), rows, {"sec": 0, "sec_reused": 0, "iex": 0})
    text = block["sentence"]
    named = [n["ticker"] for n in names if n["ticker"] in text.replace(",", " ").replace("(", " ").split()]
    assert len(set(named)) <= 3 * 4 and len(text) < 1500, text
    assert "and 77 more" in text and "Not checked past the bound of 80: 5 admitted A+/A bursts" in text


def test_the_recovery_catalog_copies_no_candidate_row_into_its_context(tmp_path):
    data = page("full")
    big = with_candidates(CC.MAX_NAMES)
    names = CC.record_names(big)
    rows = [max_row(big, n) for n in names[:CC.MAX_NAMES]]
    data_with = copy.deepcopy(data)
    data_with["candidate_checks"] = CC._block(big, names, rows, {"sec": 0, "sec_reused": 0, "iex": 0})
    assert len(CC._compact(data_with["candidate_checks"])) > 100_000
    contexts = []
    for i, record in enumerate((data, data_with)):
        root = tmp_path / f"h{i}"
        root.mkdir()
        raw = json.dumps(record, separators=(",", ":")).encode()
        try:
            history.publish(raw, root)
        except ValueError as exc:
            pytest.fail(f"history.publish refused: {exc}")
        found = [p for p in root.rglob("record.json")]
        contexts.append(found[0].read_bytes() if found else b"")
    # the rules archive the family; no row of the block (its sources, its filings) reaches the context
    assert contexts[0] and b"0000000001-26-000002" not in contexts[1] and b"sec_reused" not in contexts[1]
    # history.publish() refuses a context past 256 KiB; the block never reaches it
    assert len(contexts[1]) - len(contexts[0]) < 2000 and len(contexts[1]) < 256 * 1024


# ------------------------------------------------------------ validation ---
def test_a_record_from_before_the_rule_is_asked_for_no_block_and_one_beside_no_rule_is_named():
    data = page("full")
    del data["rules"]["candidate_checks"]
    assert CC.faults(data) == ["candidate_checks present under rules that do not write it"]
    del data["candidate_checks"]
    assert CC.faults(data) == []
    data = page("full")
    data["rules"]["candidate_checks"]["version"] = 2
    assert CC.faults(data) == ["candidate_checks rules version is unknown"]
    data["rules"]["candidate_checks"] = "x"
    assert CC.faults(data) == ["rules.candidate_checks is not an object"]


@pytest.mark.parametrize("path, value, words", [
    (("candidate_checks",), None, "candidate_checks is missing or its keys are not this version's"),
    (("candidate_checks", "rows"), "x", "candidate_checks rows are not this version's"),
    (("candidate_checks", "rows", 0, "sec"), "x", "candidate_checks parts for AAPL"),
    (("candidate_checks", "rows", 0, "earnings", "sentence"), "x", "candidate_checks earnings sentence for AAPL"),
    (("candidate_checks", "rows", 2, "cross_check", "differences", "close"), 9.0,
     "candidate_checks cross-check for AMD is not what its differences give"),
    (("candidate_checks", "rows", 2, "items", "material_count"), 3, "candidate_checks current-report items for AMD"),
    (("candidate_checks", "rows", 2, "sec", "filings_count"), 1, "candidate_checks SEC reading for AMD"),
    (("candidate_checks", "rows", 2, "role"), "boss", "candidate_checks row identity"),
    (("candidate_checks", "session"), "2026-09-11", "candidate_checks session differs from the run's"),
    (("candidate_checks", "max_names"), 81, "candidate_checks bound is not the rules it archived"),
    (("candidate_checks", "requests", "sec"), -1, "candidate_checks shed or request counts"),
    (("candidate_checks", "status"), "checked", "candidate_checks status is not its rows'"),
    (("candidate_checks", "sentence"), "x", "candidate_checks sentence is not its rows'"),
    (("candidate_checks", "rows", 0), [1], "candidate_checks rows are not this version's"),
])
def test_the_validator_names_a_forged_block_and_never_raises(path, value, words):
    data = page("full")
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    found = CC.faults(data)
    assert words in found, found
    with pytest.raises(ValueError, match="candidate_checks"):
        report.validate(data)


def test_a_flagged_filing_outside_the_window_or_of_no_listed_form_is_named():
    data = page("full")
    row = next(r for r in data["candidate_checks"]["rows"] if r["sec"]["filings"])
    row["sec"]["filings"][0]["filing_date"] = "2020-01-02"
    assert any("is outside the window or of no listed form or item" in f for f in CC.faults(data))


def at_commit(commit: str) -> bytes:
    """docs/data.json at a commit, fetched by its whole id when a shallow checkout lacks it; never skipped."""
    def present() -> bool:
        return subprocess.run(["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=ROOT,
                              capture_output=True).returncode == 0
    if not present():
        done = subprocess.run(["git", "fetch", "--quiet", "--no-tags", "--depth=1", "origin", commit],
                              cwd=ROOT, capture_output=True, text=True)
        assert done.returncode == 0 and present(), f"{commit} could not be fetched: {done.stderr.strip()}"
    return subprocess.run(["git", "show", f"{commit}:docs/data.json"], cwd=ROOT, capture_output=True,
                          check=True).stdout


@pytest.mark.parametrize("commit", [
    # the publications of 18 to 23 November, the last before the rule, by whole object id
    "35dc2cc087e67802e9b49dcc3666b4235b9f3db8", "1a602273620af3ad50093cd5706d3e585e4195ad",
    "f969d2f7cdbb8a613bae0d2ad3d22e3a34eb5979", "f82801e750e54ca7cc9a4fbb054cba9e6022877b",
])
def test_a_retained_publication_from_before_the_rule_validates_unchanged(commit):
    raw = at_commit(commit)
    data = json.loads(raw)
    assert "candidate_checks" not in data and "candidate_checks" not in data["rules"]
    assert CC.faults(data) == []
    report.validate(data)


def test_the_committed_publication_validates_unchanged():
    data = json.loads((ROOT / "docs" / "data.json").read_text())
    assert CC.faults(data) == []
    report.validate(data)


# ----------------------------------------------------------------- words ---
def test_a_candidates_earnings_sentence_names_the_hold_a_next_session_entry_would_have():
    data = page("full")
    for r in data["candidate_checks"]["rows"]:
        if r["role"] == "ticket":
            assert r["earnings"]["sentence"] == data["run"]["earnings"]["rows"][0]["sentence"]
        else:
            assert "this ticket" not in r["earnings"]["sentence"]
    amd = next(r for r in data["candidate_checks"]["rows"] if r["ticker"] == "AMD")
    assert earnings_risk.CANDIDATE_HOLD in amd["earnings"]["sentence"], amd["earnings"]["sentence"]


def test_the_earnings_sentences_default_words_are_the_tickets_unchanged():
    row = page("full")["run"]["earnings"]["rows"][0]
    assert earnings_risk.sentence(row) == row["sentence"] == earnings_risk.sentence(row, hold=earnings_risk.TICKET_HOLD)
    assert "this ticket's hold window" in row["sentence"] or row["verdict"] == "unknown"


# ------------------------------------------------------- the closed night ---
def test_a_closed_night_carries_the_previous_block_while_it_holds_and_reads_again_when_not(fake_sec):
    data = page("full")
    block = data["candidate_checks"]
    assert CC.carried(block, data) is block
    names = CC.record_names(data)
    assert CC.night(data, previous=block, reader=CC.SecReader(fake_sec, now=NOW), iex=iex_for(data, names),
                    frames=sip_for(data, names)) is block
    # tonight's cross-check for the ticket read differently: the previous block no longer holds
    moved = copy.deepcopy(data)
    moved["run"]["cross_check"]["rows"][0]["reason"] = "no_iex_bar"
    moved["run"]["cross_check"]["rows"][0].update(result="unknown", differences=None)
    moved["run"]["cross_check"]["status"] = "unknown"
    assert CC.carried(block, moved) is None
    again = CC.night(moved, previous=block, reader=CC.SecReader(fake_sec, now=NOW), iex=iex_for(moved, names),
                     frames=sip_for(moved, names))
    assert again is not block and CC.faults({**moved, "candidate_checks": again}) == []


def test_a_night_whose_collection_raises_is_the_block_with_nothing_read(monkeypatch):
    data = page("full")
    monkeypatch.setattr(CC, "collect", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("bug")))
    block = CC.night(data, reader=CC.SecReader(FakeSec(), now=NOW))
    assert CC.faults({**data, "candidate_checks": block}) == []
    assert [r["sec"]["reason"] for r in block["rows"] if r["role"] == "reviewed"] == ["not_checked"] * 3
    assert block["rows"][0] == data["candidate_checks"]["rows"][0]   # a ticket keeps its own blocks' reading


# ------------------------------------------------------------------ docs ---
def test_the_readme_and_the_env_example_quote_the_modules_own_numbers():
    readme = " ".join((ROOT / "README.md").read_text().split())
    env = " ".join((ROOT / ".env.example").read_text().split())
    section = readme.split("### Candidate checks")[1].split("### ")[0]
    assert f"up to {CC.MAX_NAMES} names a night" in section and CC.POLICY == "flag_only" and "policy `flag_only`" in section
    assert f"past {CC.DEADLINE_SECONDS} seconds from its start" in section
    assert f"or past the issuer transport's {CC.MAX_REQUESTS} requests for the night" in section
    assert CC.MAX_REQUESTS == issuer_evidence.MAX_REQUESTS
    assert f"bounded at {CC.MAX_BLOCK_BYTES} bytes" in section and CC.MAX_BLOCK_BYTES == 256 * 1024
    assert f"the newest {CC.MAX_FILINGS} kept" in section and f"the first {CC.MAX_MATERIAL} material items kept" in section
    assert f"at most {CC.SENTENCE_NAMES} names for each kind of flag" in section
    roles = "every ticket, every listed setup, every burst the review selected, every burst"
    assert roles in section and CC.ROLES == ("ticket", "listed", "reviewed", "candidate", "also_quiet")
    assert "`iex_unavailable` on every row, never `no_iex_bar`" in section
    assert f"up to {CC.MAX_NAMES} of the night's candidates" in env and f"within {CC.DEADLINE_SECONDS} seconds" in env
    assert f"the transport's {CC.MAX_REQUESTS} requests" in env and "No new variable or credential" in env


# ------------------------------------------------- the mail and the brief ---
def test_the_mail_prints_the_blocks_own_sentence_and_nothing_for_a_record_before_it():
    data = page("full")
    html = report.digest_html(data)
    assert "// candidate checks" in html and report.esc(data["candidate_checks"]["sentence"]) in html
    assert html.index("// candidate checks") > html.index("// where the candidates stopped")
    del data["candidate_checks"]
    assert "// candidate checks" not in report.digest_html(data)


def test_the_brief_carries_each_candidates_row_and_counts_what_was_checked():
    from src import brief
    raw = (PAGE / "full.json").read_bytes()
    json_raw, md_raw, why = brief.compose(raw, None)
    assert why is None
    out, record = json.loads(json_raw), json.loads(raw)
    rows = {(r["stage"], r["ticker"]): r for r in record["candidate_checks"]["rows"]}
    detailed = out["candidates"]["detailed"]
    assert detailed
    for c in detailed:
        row = rows[("burst", c["ticker"])]
        carried = c["candidate_checks"]
        assert carried == brief.check_row(row), c["ticker"]
        # the readings themselves, read off the record's row: nothing added, the accessions left out
        assert (carried["role"], carried["cik"], carried["source"], carried["cross_check"]) == \
            (row["role"], row["cik"], row["source"], row["cross_check"])
        assert carried["sec"]["state"] == brief.SEC_STATE_WORDS[row["sec"]["state"]] != "clear"
        assert carried["sec"]["filings_count"] == row["sec"]["filings_count"]
        assert [f["filing_date"] for f in carried["sec"]["filings"]] == [f["filing_date"] for f in row["sec"]["filings"]]
        assert carried["earnings"]["sentence"] == row["earnings"]["sentence"]
        assert carried["items"]["status"] == row["items"]["status"] and brief.scanner_names(carried) == []
    assert out["service"]["candidate_checks"]["sentence"] == record["candidate_checks"]["sentence"]
    assert record["candidate_checks"]["sentence"] in md_raw.decode()
    events = out["events"]
    assert events["earnings"]["candidate_rows"] == len(record["candidate_checks"]["rows"])
    checked = {r["ticker"] for r in record["candidate_checks"]["rows"]}
    assert events["earnings"]["listed_names_with_a_check"] == len(checked)
    assert "(they run for tickets only)" not in events["sentence"] and "candidate checks' flags" in events["sentence"]
    assert len(json_raw) <= brief.MAX_JSON_BYTES


def test_a_ceiling_carries_the_block_at_its_own_bound_never_at_the_fixtures_size():
    from tests import test_publication_ceiling as ceiling
    red = json.loads(ceiling.FIXTURE.read_bytes())
    assert len(CC._compact(red["candidate_checks"])) < CC.MAX_BLOCK_BYTES
    assert ("candidate_checks",) in ceiling.NIGHTLY
    assert ceiling.components(red)["nightly"][1] >= CC.MAX_BLOCK_BYTES
