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
    forged["unchecked"] = {} if unchecked else {"candidate": 1}      # never the record's, in either case
    assert "candidate_checks counts by role are not the record's names" in checked(data, forged)


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
    earn = earnings_risk.collect(tickets, data["run"]["session"], fetch=reader, now=NOW)
    # the ticket's own reading, made through this reader before any candidate's, is the one its row carries
    assert earn["rows"][0]["reason"] is None and earn["rows"][0]["error"] is None
    data["run"]["earnings"] = earn
    block = CC.collect(data, reader=reader, iex=iex_for(data, names), frames=sip_for(data, names))
    ticket = block["rows"][0]
    assert ticket["role"] == "ticket" and ticket["earnings"]["reason"] is None
    assert ticket["earnings"]["verdict"] == earn["rows"][0]["verdict"]
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
    # the batch the evening asks for names no ticket: a ticket's cross-check keeps its own request
    tickets = {r["ticker"] for r in data["run"]["cross_check"]["rows"]}
    assert tickets and not tickets & set(CC.cross_symbols(data))
    assert set(CC.cross_symbols(data)) == {n["ticker"] for n in names
                                           if (n["stage"], n["ticker"]) not in CC._run_rows(data)["cross_check"]}


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
                r["cik"] = r["cik"] or 1                        # a reading SEC gave names its issuer
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
    # the tickets' cross-check keeps its own iex request, and the candidate checks ask for the rest in one
    # batch of their own that names no ticket
    iex = [r for r in fake_alpaca.bar_requests if getattr(getattr(r, "feed", None), "value", None) == "iex"]
    tickets = {r["ticker"] for r in run["cross_check"]["rows"]}
    assert block["requests"]["iex"] == 1 and len(iex) == 2
    assert set(iex[0].symbol_or_symbols) == tickets
    assert set(iex[1].symbol_or_symbols) == set(CC.cross_symbols(data)) and not tickets & set(CC.cross_symbols(data))


# ------------------------------------------------------------- agreement ---
@pytest.mark.parametrize("part, change, words", [
    ("earnings", {"verdict": "estimate_outside", "reason": None}, "earnings"),
    ("sec", {"state": "clear", "filings": [], "filings_count": 0}, "sec"),
    ("cross_check", {"result": "fail", "reason": "differ: close",
                     "differences": {"open": 0.0, "high": 0.0, "low": 0.0, "close": 9.0, "volume": 0.0}}, "cross_check"),
    ("items", {"codes": ["1.01", "9.99"]}, "items"),
    ("source", {"bytes": 1}, "source"),
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


def test_a_tickets_cik_that_is_not_its_run_rows_is_named():
    data = page("full")
    row = data["candidate_checks"]["rows"][0]
    assert row["role"] == "ticket" and row["cik"] == data["run"]["earnings"]["rows"][0]["cik"]
    row["cik"] += 1
    assert "candidate_checks cik for AAPL is not its run.* row's" in CC.faults(data)


def test_a_rows_cik_is_the_earnings_readings_else_the_sec_flags():
    name = {"stage": "anticipation", "ticker": "QQQ", "role": "listed", "rank": 1}
    session = page("full")["run"]["session"]
    er = CC._unread_earnings(name, session, earnings_risk.window(session), NOW)
    sr = {**CC._unread_sec(name), "state": "clear", "reason": None, "cik": 4321}
    assert er["cik"] is None and CC._lean(name, er, sr, CC._unread_cross())["cik"] == 4321
    assert CC._lean(name, {**er, "cik": 99}, sr, CC._unread_cross())["cik"] == 99


def test_a_listed_setups_sec_reading_is_held_to_its_run_sec_flags_row():
    data = page("full")
    listed = next(r for r in data["candidate_checks"]["rows"] if r["role"] == "listed")
    listed["sec"] = {"state": "clear", "reason": None, "filings": [], "filings_count": 0}
    listed["cik"] = listed["cik"] or 1                  # an issuer named, so only the agreement rule is left
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


def test_a_row_keeps_the_newest_filings_and_the_first_material_items_with_their_counts():
    filings = [{"accession": f"0000000001-26-00000{i}", "filing_date": f"2026-09-0{i}", "form": "SC TO-T", "items": []}
               for i in range(1, 7)]                                         # oldest first, as sec_flags keeps them
    part = CC._sec_part({"state": "flagged", "reason": None, "filings": filings})
    assert part["filings"] == filings[-CC.MAX_FILINGS:] and part["filings_count"] == 6
    material = [{**MATERIAL, "accession": f"0000000001-26-00001{i}"} for i in range(6)]   # material first, retained order
    er = {"items": {"status": "material", "reason": None, "material": material, "codes": ["1.01"], "count": 6,
                    "unread": 0, "after_hold": 0, "unretained_material": 0}}
    items = CC._items_part(er)
    assert items["material"] == material[:CC.MAX_MATERIAL] and items["material_count"] == 6


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


def test_a_row_a_tickets_block_stands_behind_is_never_shed_even_past_the_bound(monkeypatch):
    """Past every row that can give way, the rows the tickets' own blocks stand behind
    keep their reading and are not counted as shed: the block stays over its bound,
    which the validator names."""
    data = with_candidates(CC.MAX_NAMES)
    names = CC.record_names(data)
    runs = CC._run_rows(data)
    session = data["run"]["session"]
    rows = [CC._row_of(n, runs, session, earnings_risk.window(session), NOW) for n in names[:CC.MAX_NAMES]]
    monkeypatch.setattr(CC, "MAX_BLOCK_BYTES", 1000)
    block = CC._bounded(data, names, list(rows), {"sec": 0, "sec_reused": 0, "iex": 0})
    backed = [i for i, n in enumerate(names[:CC.MAX_NAMES]) if any((n["stage"], n["ticker"]) in runs[k] for k in runs)]
    assert backed and block["shed"] == CC.MAX_NAMES - len(backed)
    assert [block["rows"][i] for i in backed] == [rows[i] for i in backed]
    assert f"{CC.MAX_NAMES - len(backed)} shed to stay within" in block["sentence"]


def test_the_blocks_status_is_checked_partial_or_unavailable_by_what_its_rows_read():
    data = page("full")
    rows = {r["ticker"]: r for r in data["candidate_checks"]["rows"]}
    read, half = rows["AMD"], rows["TSLA"]
    assert all(CC._read(read).values()) and not all(CC._read(half).values()) and any(CC._read(half).values())
    session = data["run"]["session"]
    none = CC._row_of({"stage": "burst", "ticker": "ZZZ", "role": "candidate", "rank": 9},
                      {"earnings": {}, "sec_flags": {}, "cross_check": {}}, session, earnings_risk.window(session), NOW)
    assert not any(CC._read(none).values())
    assert (CC.status_of([]), CC.status_of([read]), CC.status_of([read, half]), CC.status_of([none]),
            CC.status_of([none, read])) == ("not_applicable", "checked", "partial", "unavailable", "partial")


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
    assert "and 77 more" in text and "Not checked past the bound of 80: 5 discovery-admitted A+/A bursts" in text
    # an overdue report is a flag of its own kind of words, named like the rest
    for r in rows:
        r["earnings"] = {**r["earnings"], "verdict": "estimate_outside"}
    rows[3]["earnings"] = {**rows[3]["earnings"], "verdict": "overdue"}
    text = CC._block(data, CC.record_names(data), rows, {"sec": 0, "sec_reused": 0, "iex": 0})["sentence"]
    assert f"estimated in or near the hold window, or overdue for 1 ({rows[3]['ticker']})" in text, text


def test_a_block_that_read_nothing_says_so_and_never_none_flagged():
    data = page("full")
    session = data["run"]["session"]
    names = [{"stage": "burst", "ticker": t, "role": "candidate", "rank": i} for i, t in enumerate(("ZZA", "ZZB"))]
    none = [CC._row_of(n, {"earnings": {}, "sec_flags": {}, "cross_check": {}}, session,
                       earnings_risk.window(session), NOW) for n in names]
    block = {"rows": none, "names": {"candidate": 2}, "unchecked": {}, "shed": 0, "max_names": CC.MAX_NAMES}
    assert CC.status_of(none) == "unavailable"
    text = CC.sentence(block, data)
    assert "Nothing could be read for these names, so none is flagged and none is clear." in text
    assert "None flagged" not in text and "Unknown, and unknown is never clear" in text
    read = [r for r in data["candidate_checks"]["rows"] if r["ticker"] == "AMD"]
    assert CC.status_of(read) == "checked"
    text = CC.sentence({**block, "rows": read, "names": {"reviewed": 1}}, data)
    assert "None flagged among the readings made." in text and "Nothing could be read" not in text


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


FILING = {"accession": "0000000001-26-000009", "form": "SC TO-T", "items": []}
MATERIAL = {"item": "1.01", "title": earnings_risk.ITEM_TITLES["1.01"], "form": "8-K",
            "accession": "0000000001-26-000010", "accepted_at": "2026-09-10T21:00:00Z",
            "placement": "before_signal_close"}


@pytest.mark.parametrize("part, change, words", [
    # each keeps the length rule (the list as long as its count allows) so only the consistency clause can refuse
    ("sec", {"state": "flagged"}, "SEC reading"),                                       # flagged, no filing
    ("sec", {"state": "clear", "filings_count": 1, "filings": ["FILING"]}, "SEC reading"),  # a filing, called clear
    ("sec", {"state": "unknown", "reason": None}, "SEC reading"),                       # unknown with no reason
    ("sec", {"state": "clear", "reason": "not_checked"}, "SEC reading"),                # read, with a reason
    ("items", {"status": "none", "material_count": 1, "material": ["MATERIAL"]}, "current-report items"),
    ("items", {"status": "material"}, "current-report items"),                          # material, no item
])
def test_each_consistency_clause_of_a_row_is_held_on_its_own(part, change, words):
    data = page("full")
    row = data["candidate_checks"]["rows"][2]
    assert row["ticker"] == "AMD" and row["sec"]["state"] == "clear" and row["items"]["status"] == "none"
    for key, value in change.items():
        if value == ["FILING"]:
            value = [{**FILING, "filing_date": data["run"]["session"]}]
        elif value == ["MATERIAL"]:
            value = [{**MATERIAL, "filing_date": data["run"]["session"]}]
        row[part][key] = value
    found = CC.faults(data)
    assert f"candidate_checks {words} for AMD" in found, found
    # and the same row put back is refused for nothing
    assert CC.faults(page("full")) == []


def test_a_filing_in_the_window_of_a_form_and_items_the_flags_do_not_list_is_named():
    data = page("full")
    row = data["candidate_checks"]["rows"][2]
    row["sec"] = {"state": "flagged", "reason": None, "filings_count": 1,
                  "filings": [{**FILING, "form": "10-K", "filing_date": data["run"]["session"]}]}
    assert any("of no listed form or item" in f for f in CC.faults(data))
    row["sec"]["filings"][0].update(form="8-K", items=["2.02"])          # an 8-K item the flags do not list
    assert any("of no listed form or item" in f for f in CC.faults(data))
    row["sec"]["filings"][0]["items"] = ["1.01"]                          # one they do
    assert not any("for AMD" in f for f in CC.faults(data))


def test_the_window_is_the_sec_flags_archived_one_not_the_codes():
    data = page("full")
    assert CC.faults(data) == []
    data["rules"]["sec_flags"]["window_days"] = sec_flags.WINDOW_DAYS + 1
    assert "candidate_checks window is not the SEC flags' archived window" in CC.faults(data)
    data["rules"]["sec_flags"]["window_days"] = "30"
    assert "candidate_checks window is not the SEC flags' archived window" in CC.faults(data)


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


@pytest.mark.parametrize("verdict, placement", [("reported_after_signal", "during_hold"), ("estimate_outside", None),
                                                ("estimate_inside", "any_day"), ("estimate_near", None),
                                                ("overdue", "any_day")])
def test_every_earnings_sentence_a_candidate_can_carry_names_its_own_hold(verdict, placement):
    data = page("full")
    row = {**data["run"]["earnings"]["rows"][0], "verdict": verdict, "placement": placement,
           "observed": {"filing_date": data["run"]["session"], "accepted_at": "2026-09-10T21:00:00Z"}}
    ticket, candidate = earnings_risk.sentence(row), earnings_risk.sentence(row, hold=earnings_risk.CANDIDATE_HOLD)
    assert earnings_risk.TICKET_HOLD in ticket and earnings_risk.CANDIDATE_HOLD in candidate
    assert "this ticket" not in candidate and candidate == ticket.replace(earnings_risk.TICKET_HOLD,
                                                                        earnings_risk.CANDIDATE_HOLD)


def test_a_kept_answer_is_dated_when_sec_gave_it_not_when_it_was_read_again(fake_sec):
    fake_sec.issuer("AAA", 1, "AAA Inc.", [], start="2024-01-02")
    first, later = NOW, NOW + timedelta(minutes=2)
    reader = CC.SecReader(fake_sec, now=first)
    reader(issuer_evidence.MAPPING_URL)
    reader._now = later
    reader(earnings_risk.SUBMISSIONS_URL.format(cik=1))
    assert reader.last_at == later
    reader(issuer_evidence.MAPPING_URL)                                  # held: no request, SEC's own instant
    assert reader.last_at == first and reader.made() == 2 and reader.reused == 1


def test_no_sec_request_begins_once_the_transport_has_downloaded_its_bound():
    class Budget:
        requests = 0
        bytes = 0

    sent = []

    def base(url):
        sent.append(url)
        base.budget.requests += 1
        base.budget.bytes += 1000
        return b"{}"
    base.budget = Budget()
    reader = CC.SecReader(base, now=NOW)
    reader("https://www.sec.gov/a")
    base.budget.bytes = issuer_evidence.MAX_DOWNLOAD_BYTES - 1
    reader("https://www.sec.gov/b")                                       # under the bound: it goes out
    with pytest.raises(earnings_risk.SourceError, match="size_limit"):
        reader("https://www.sec.gov/c")                                    # at it: refused before it goes out
    assert sent == ["https://www.sec.gov/a", "https://www.sec.gov/b"] and reader.made() == 2


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
    assert f"past {CC.DEADLINE_SECONDS} seconds from its first request" in section
    assert "a candidate's ticker the provider refuses never changes a ticket's row or `orders.json`" in section
    assert f"past the issuer transport's {CC.MAX_REQUESTS} requests for the night" in section
    assert CC.MAX_REQUESTS == issuer_evidence.MAX_REQUESTS
    assert f"bounded at {CC.MAX_BLOCK_BYTES} bytes" in section and CC.MAX_BLOCK_BYTES == 256 * 1024
    assert f"the newest {CC.MAX_FILINGS} kept" in section and f"the first {CC.MAX_MATERIAL} material items kept" in section
    assert f"at most {CC.SENTENCE_NAMES} names for each kind of flag" in section
    roles = "every ticket, every listed setup, every burst the review selected, every burst"
    assert roles in section and CC.ROLES == ("ticket", "listed", "reviewed", "candidate", "also_quiet")
    assert "`iex_unavailable` on every row, never `no_iex_bar`" in section
    assert f"or once that transport has downloaded its {issuer_evidence.MAX_DOWNLOAD_BYTES} bytes for the night" in section
    assert f"its {issuer_evidence.MAX_DOWNLOAD_BYTES} downloaded bytes" in env
    assert "beside each burst, listed setup and also-quiet coil it prints" in section
    coverage = " ".join((ROOT / "knowledge" / "event-coverage.md").read_text().split())
    prompt = " ".join((ROOT / "docs" / "analyst" / "prompt.md").read_text().split())
    assert f"for up to {CC.MAX_NAMES} of the night's candidates, whatever the light" in coverage
    assert f"| up to {CC.MAX_NAMES} names a night in role order" in coverage
    assert f"the iex bar for up to {CC.MAX_NAMES} of the night's candidates, whatever the light" in prompt
    assert f"(`candidate_checks`, up to {CC.MAX_NAMES} names a night)" in prompt
    assert "issuer check only the tickets and the plans the registry blocked" in prompt
    assert f"up to {CC.MAX_NAMES} of the night's candidates" in env
    assert f"within {CC.DEADLINE_SECONDS} seconds of its first request" in env
    assert f"the transport's {CC.MAX_REQUESTS} requests" in env and "No new variable or credential" in env


# ------------------------------------------------- the mail and the brief ---
def test_the_mail_prints_the_blocks_own_sentence_and_nothing_for_a_record_before_it():
    data = page("full")
    html = report.digest_html(data)
    assert "// candidate checks" in html and report.esc(data["candidate_checks"]["sentence"]) in html
    assert html.index("// candidate checks") > html.index("// where the candidates stopped")
    del data["candidate_checks"]
    assert "// candidate checks" not in report.digest_html(data)


def test_a_filing_with_no_issuer_or_no_accession_names_no_folder():
    from src import brief
    filing = {"accession": "0001193125-26-423478", "filing_date": "2026-10-16", "form": "8-K", "items": ["2.01"]}
    row = {"cik": 900075, "sec": {"state": "flagged", "filings": [filing]}, "items": {"material": [filing]}}
    assert brief.check_row(row)["sec"]["filings"][0]["filing_index"] == \
        "https://www.sec.gov/Archives/edgar/data/900075/000119312526423478/"
    for change in ({"cik": None}, {"cik": "900075"}):
        assert brief.check_row({**row, **change})["sec"]["filings"][0]["filing_index"] is None
    odd = {**row, "sec": {"filings": [{**filing, "accession": "1193125-26-423478"}]}}
    assert brief.check_row(odd)["sec"]["filings"][0]["filing_index"] is None
    assert brief.scanner_names(brief.check_row(row)) == []


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
        # the readings themselves, read off the record's row: nothing added, each filing's EDGAR folder named
        assert (carried["role"], carried["cik"], carried["source"], carried["cross_check"]) == \
            (row["role"], row["cik"], row["source"], row["cross_check"])
        assert carried["sec"]["state"] == brief.SEC_STATE_WORDS[row["sec"]["state"]] != "clear"
        assert carried["sec"]["filings_count"] == row["sec"]["filings_count"]

        def folder(f):
            return f"https://www.sec.gov/Archives/edgar/data/{row['cik']}/{f['accession'].replace('-', '')}/"
        assert [(f["filing_index"], f["filing_date"]) for f in carried["sec"]["filings"]] == \
            [(folder(f), f["filing_date"]) for f in row["sec"]["filings"]]
        assert [m["filing_index"] for m in carried["items"]["material"]] == [folder(m) for m in row["items"]["material"]]
        assert carried["earnings"]["sentence"] == row["earnings"]["sentence"]
        assert carried["items"]["status"] == row["items"]["status"] and brief.scanner_names(carried) == []
    assert out["service"]["candidate_checks"]["sentence"] == record["candidate_checks"]["sentence"]
    assert record["candidate_checks"]["sentence"] in md_raw.decode()
    # a setting-up row carries its own candidate-check row, as a burst does
    for listed in out["setting_up"]["listed"] + out["setting_up"]["also_quiet"]:
        row = rows.get(("anticipation", listed["ticker"]))
        assert listed.get("candidate_checks") == (brief.check_row(row) if row else None), listed["ticker"]
    assert any(l.get("candidate_checks") for l in out["setting_up"]["listed"])
    events = out["events"]
    assert events["earnings"]["candidate_rows"] == len(record["candidate_checks"]["rows"])
    # a name counts as read only where its row records a reading, never for having a row
    cand = record["candidate_checks"]["rows"]
    earnings_read = {r["ticker"] for r in cand if r["earnings"]["verdict"] != "unknown"}
    sec_read = {r["ticker"] for r in cand if r["sec"]["state"] != "unknown"}
    assert {r["ticker"] for r in cand} - (earnings_read | sec_read), "the fixture has a row with nothing read"
    assert events["earnings"]["listed_names_earnings_read"] == len(earnings_read)
    assert events["earnings"]["listed_names_sec_read"] == len(sec_read)
    assert events["earnings"]["listed_names_with_a_check"] == len(earnings_read | sec_read)
    assert (f"an earnings date was read for {len(earnings_read)} and SEC filings for {len(sec_read)}"
            in events["sentence"])
    assert "(they run for tickets only)" not in events["sentence"] and "candidate checks' flags" in events["sentence"]
    assert len(json_raw) <= brief.MAX_JSON_BYTES


def test_a_ceiling_carries_the_block_at_its_own_bound_never_at_the_fixtures_size():
    from tests import test_publication_ceiling as ceiling
    red = json.loads(ceiling.FIXTURE.read_bytes())
    assert len(CC._compact(red["candidate_checks"])) < CC.MAX_BLOCK_BYTES
    assert ("candidate_checks",) in ceiling.NIGHTLY
    assert ceiling.components(red)["nightly"][1] >= CC.MAX_BLOCK_BYTES


# ---------------------------------------------------- the review's rules ---
def test_a_candidate_whose_earnings_date_is_unknown_is_never_counted_as_read(fake_sec):
    """A filing list read in full can still give no date (a foreign issuer, a history the reader could not
    reach): the row is partial, and the sentence counts its earnings date among the unknown."""
    data = page("full")
    block = copy.deepcopy(data["candidate_checks"])
    alone = next(r for r in block["rows"] if r["role"] == "reviewed")
    for reason in ("foreign_issuer", "history_not_read"):
        row = copy.deepcopy(alone)
        row.update(cik=row["cik"] or 7, source=row["source"] or {"sha256": "0" * 64, "bytes": 1,
                                                               "retrieved_at": NOW.isoformat()})
        row["sec"] = {"state": "clear", "reason": None, "filings": [], "filings_count": 0}
        row["cross_check"] = {"result": "pass", "reason": None,
                              "differences": {"open": 0.0, "high": 0.0, "low": 0.0, "close": 0.0, "volume": 0.0}}
        row["earnings"] = {**row["earnings"], "verdict": "unknown", "reason": reason}
        assert row["earnings"]["reason"] in earnings_risk.ASSESSED_REASONS
        assert CC._read(row) == {"sec": True, "earnings": False, "cross_check": True}
        assert CC.status_of([row]) == "partial"
        one = {**block, "rows": [row], "names": {"reviewed": 1}, "unchecked": {}, "shed": 0}
        assert "Unknown, and unknown is never clear: the earnings date of 1." in CC.sentence(one, data), reason


def test_a_candidates_ticker_the_provider_refuses_never_changes_a_tickets_cross_check(night_market, fake_resend,
                                                                                      fake_alpaca, tmp_path,
                                                                                      monkeypatch):
    """The tickets' cross-check asks the iex feed on its own; the candidate checks' batch names no ticket.
    A candidate-only ticker that makes the provider refuse its iex batch leaves every ticket's row, and
    orders.json, as they were."""
    from src import market_data
    monkeypatch.setattr(market_data, "RETRY_WAIT_SECONDS", 0)
    _, data, orders, _ = run_night(tmp_path, night_market, "plain")
    tickets = {r["ticker"] for r in data["run"]["cross_check"]["rows"]}
    alone = sorted(set(CC.cross_symbols(data)) - tickets)
    assert tickets and alone
    client_type = type(market_data.get_clients())
    real = client_type.get_stock_bars

    def refusing(self, request):            # the iex feed refuses any batch naming that candidate
        if getattr(getattr(request, "feed", None), "value", None) == "iex" and \
                alone[0] in (request.symbol_or_symbols or ()):
            raise ConnectionError("the provider refuses this batch")
        return real(self, request)
    monkeypatch.setattr(client_type, "get_stock_bars", refusing)
    _, refused, refused_orders, _ = run_night(tmp_path, night_market, "refused")
    assert refused["run"]["cross_check"] == data["run"]["cross_check"]
    assert decisions(refused, refused_orders) == decisions(data, orders)
    rows = {r["ticker"]: r for r in refused["candidate_checks"]["rows"]}
    assert rows[alone[0]]["cross_check"]["reason"].startswith("iex_unavailable")


def test_the_sec_readers_deadline_runs_from_its_first_request_not_its_construction(fake_sec):
    fake_sec.issuer("AAA", 1, "AAA Inc.", [], start="2024-01-02")
    clock = {"t": 0.0}
    reader = CC.SecReader(fake_sec, now=NOW, deadline_seconds=10, monotonic=lambda: clock["t"])
    clock["t"] = 1000.0                                # the evening's plans and record took this long
    reader(issuer_evidence.MAPPING_URL)               # the first request is never past the deadline
    assert reader.started == 1000.0 and reader.made() == 1
    clock["t"] = 1009.0
    reader(earnings_risk.SUBMISSIONS_URL.format(cik=1))
    clock["t"] = 1010.0                                # ten seconds after the first request
    with pytest.raises(earnings_risk.SourceError, match="time_budget"):
        reader(earnings_risk.SUBMISSIONS_URL.format(cik=2))
    assert reader.made() == 2


@pytest.mark.parametrize("change, words", [
    (lambda r: r.update(cik=None, sec={"state": "clear", "reason": None, "filings": [], "filings_count": 0}),
     "SEC reading for {t} names no issuer"),
    (lambda r: r.update(source=None), "earnings reading for {t} names no issuer or no source"),
    (lambda r: r.update(cik=None), "earnings reading for {t} names no issuer or no source"),
])
def test_a_reading_with_no_issuer_or_no_source_behind_it_is_refused(change, words):
    data = page("full")
    row = next(r for r in data["candidate_checks"]["rows"] if r["role"] == "reviewed")
    assert row["earnings"]["reason"] in earnings_risk.ASSESSED_REASONS and row["cik"] and row["source"]
    change(row)
    if row["sec"]["state"] != "unknown" and row["cik"] is None and "SEC" not in words:
        row["sec"] = {"state": "unknown", "reason": "not_checked", "filings": [], "filings_count": 0}
    assert f"candidate_checks {words.format(t=row['ticker'])}" in CC.faults(data)


def test_a_block_its_validator_refuses_falls_back_to_the_unread_block_with_its_requests_counted(fake_sec, monkeypatch):
    data = page("full")
    names = CC.record_names(data)
    register(fake_sec, [n["ticker"] for n in names], data["run"]["session"])
    real = CC.collect

    def forged(data, **kwargs):
        block = real(data, **kwargs)
        block["shed"] = -1                              # a count the validator refuses
        return block
    monkeypatch.setattr(CC, "collect", forged)
    reader = CC.SecReader(fake_sec, now=NOW)
    block = CC.safe_collect(data, reader=reader, iex=iex_for(data, names), frames=sip_for(data, names))
    assert CC.faults({**data, "candidate_checks": block}) == [] and block["shed"] == 0
    assert block["requests"]["sec"] == reader.made() > 0
    alone = [r for r in block["rows"] if r["role"] == "reviewed"]
    assert alone and all(r["sec"]["reason"] == "not_checked" for r in alone)


def test_the_iex_batch_asks_only_for_the_first_eighty_names_and_none_a_ticket_reads():
    data = with_candidates(CC.MAX_NAMES + 7)
    names = CC.record_names(data)
    runs = CC._run_rows(data)
    within = {n["ticker"] for n in names[:CC.MAX_NAMES] if (n["stage"], n["ticker"]) not in runs["cross_check"]}
    assert len(names) > CC.MAX_NAMES and CC.cross_symbols(data) == sorted(within)
    past = {n["ticker"] for n in names[CC.MAX_NAMES:]}
    assert past and not past & set(CC.cross_symbols(data))


@pytest.mark.parametrize("shape", [5, "x", [1], {"stage": "burst", "ticker": "AAPL"}])
def test_a_run_row_a_reader_cannot_index_into_never_makes_the_evenings_block_raise(shape):
    data = page("full")
    data["run"]["earnings"]["rows"][0] = shape if not isinstance(shape, dict) else {**shape}
    block = CC.night(data)
    assert isinstance(block, dict) and block["rows"] and isinstance(block["sentence"], str)
    assert isinstance(CC.unread(data), dict)


def test_a_flagged_filing_whose_items_hold_an_object_is_named_and_never_raises():
    data = page("full")
    data["run"]["sec_flags"]["rows"][0].update(state="flagged", cik=1, filings=[
        {"accession": "0000000001-26-000001", "filing_date": data["run"]["session"], "form": "8-K",
         "items": [{"code": "1.01"}]}])
    found = sec_flags.faults(data)
    assert any("outside the window or of no listed form or item" in f for f in found), found
