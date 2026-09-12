"""The evening run end to end, through the doubles: a market of textbook
frames registered with the Alpaca double, the grader double answering in the
rubric's shape, the Resend double catching the digest. Every night here is
pinned to an instant (the clock never decides a test), and every assertion
reads docs/data.json the way the page does."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from src import pipeline, plan, record, report, scans
from tests.synthetic import make_ohlcv
from tests.test_quality import frame as qframe, ideal_bars
from tests.test_watchlist import coil

# Thursday 10 Sep 2026, 6:30 PM ET: after the close, the session is the 10th.
EVENING = datetime(2026, 9, 10, 22, 30, tzinfo=timezone.utc)
SESSION = "2026-09-10"

CLAUDE_A_PLUS = {"score": 9.2, "grade": "A+", "reason": "a clean leg into a tight base and a 6% burst that closed at its high",
                 "key_risk": "the gap at the open", "entry_note": "skip it above the ceiling"}


def a_plus_frame() -> pd.DataFrame:
    """An A+ burst whose ticket qualifies at its limit: the burst bar spans
    0.25% of its close, so the bar's midpoint sits inside his 4% line under
    the +4% ceiling. (The textbook bar, whose low sits 4.7% under the close,
    grades A+ too and has its ticket withheld: see test_a_textbook_burst...)"""
    return qframe(ideal_bars(burst_range_pct=0.25, base_range=0.15, prior_range=0.1))


def base_frames(n: int, seed: int) -> dict[str, pd.DataFrame]:
    """`n` ordinary names that never burst, so coverage clears the session
    rules' floor and breadth has a universe to count."""
    return {f"B{chr(65 + i)}{chr(65 + i)}": make_ohlcv("base", seed=[seed, i], days=260) for i in range(n)}


@pytest.fixture
def market(fake_alpaca, seed):
    """The night's universe: one A+ burst, one coiled name, eleven quiet names
    and SPY. Returns the tickers in the order the pipeline is given them."""
    fake_alpaca.add_history("AAA", a_plus_frame())
    fake_alpaca.add_history("COIL", coil())
    for name, df in base_frames(11, seed).items():
        fake_alpaca.add_history(name, df)
    fake_alpaca.add_history("SPY", make_ohlcv("base", seed=[seed, 999], days=260))
    return ["AAA", "COIL"] + [f"B{chr(65 + i)}{chr(65 + i)}" for i in range(11)]


@pytest.fixture
def claude(fake_anthropic):
    fake_anthropic.set_payload(dict(CLAUDE_A_PLUS))
    return fake_anthropic


def evening(tmp_path: Path, tickers: list[str], *, now: datetime = EVENING, dry_run: bool = False) -> tuple:
    docs = tmp_path / "docs"
    rep = pipeline.run_evening(dry_run=dry_run, tickers=tickers, docs=docs, now=now)
    data = json.loads((docs / pipeline.DATA_FILE).read_text()) if (docs / pipeline.DATA_FILE).exists() else None
    return rep, data, docs


# --------------------------------------------------------------- a night ---
def test_a_clean_night_publishes_a_trade_with_its_ticket_and_records_the_pick(market, claude, fake_resend, tmp_path):
    rep, data, docs = evening(tmp_path, market)
    assert rep.exit_code() == 0 and rep.status == "ok", rep.problems
    assert data["schema_version"] == report.SCHEMA_VERSION
    run = data["run"]
    assert run["session"] == SESSION and run["expected_session"] == SESSION and run["session_state"] == "open"
    assert run["status"] == "ok" and run["problems"] == [] and run["email"] == "delivered"
    assert run["universe"]["size"] == len(market) and "--tickers" in run["universe"]["label"]
    assert set(run["graded"]) == set(pipeline.GRADE_KEYS)
    assert run["reads"] == {"requested": 1, "done": 1, "unavailable_reason": None}
    assert run["published_at"] == data["generated"]

    assert data["trades"] == ["AAA"] and data["beyond_cap"] == []
    burst = data["bursts"][0]
    assert burst["ticker"] == "AAA" and burst["grade"] == "A+" and burst["scan"] == "burst"   # a 0.25%-wide bar is not a $ breakout (close - open)
    assert burst["quality"]["grade"] == "A+" and burst["quality"]["checks"][0]["pass"] is True
    assert burst["claude"]["source"] == "claude" and burst["claude"]["agree"] is True
    base = burst["quality"]["base"]
    assert base["sessions"] == 17 and base["start"] < base["end"] < SESSION and base["depth_pct"] > 0
    assert burst["series"] and burst["series"][-1]["date"] == SESSION
    assert burst["summary"].startswith("AAA:")
    ticket = burst["plan"]["order_json"]
    assert ticket["action"] == "buy" and ticket["order_type"] == "stop_limit" and ticket["conditional"] == plan.OTO
    assert ticket["then"]["order_type"] == "stop" and ticket["then"]["stop_price"] == burst["plan"]["stop"]
    assert [row["day"] for row in burst["plan"]["exit_schedule"]][0] == 1
    assert burst["plan"]["exit_schedule"][0]["date"] == "2026-09-11"
    assert data["cover"]["h1"] == "Trade tomorrow. 1 A-quality burst."
    assert data["cash_budget"]["slots_used"] == 1 and data["cash_budget"]["cut"] == []
    assert data["cash_budget"]["at_risk_usd"] == burst["plan"]["risk_usd"]
    assert run["graded"] == {"a_plus": 1, "a": 0, "b": 0, "c": 0, "skip": 0}

    watch = data["watchlist"]
    assert [r["ticker"] for r in watch["top"]] == ["COIL"]
    assert watch["top"][0]["plan"]["order_line"] and watch["top"][0]["box"]["sessions"] >= 3
    assert watch["instruction"] == plan.ANTICIPATION_INSTRUCTION and watch["counts"]["coiled"] == 1
    assert data["open_plans"] == [] and data["scorecard"]["plans"] == 0
    assert data["nights"] == [{"session": SESSION, "status": "ok", "published_at": data["generated"]}]
    assert data["rules"]["plan"]["final_exit_day"] == plan.FINAL_EXIT_DAY
    assert data["breadth"]["universe"] >= 12 and data["breadth"]["notes"][0]["key"] == "ratio_10d"

    picks = json.loads((docs / record.PICKS_FILE).read_text())["picks"]
    assert [(p["ticker"], p["date"], p["kind"]) for p in picks] == [("AAA", SESSION, "burst"), ("COIL", SESSION, "anticipation")]
    assert picks[0]["entry_low"] < picks[0]["entry_ref"] < picks[0]["entry_high"] and picks[0]["targets"]["high"]
    assert (docs / pipeline.CHARTS_DIR_NAME / "AAA.png").exists()
    assert len(fake_resend.sent) == 1 and "Trade tomorrow" in fake_resend.sent[0]["subject"]


def test_the_next_night_follows_the_pick_from_bars_alone(market, claude, fake_resend, tmp_path):
    evening(tmp_path, market)
    rep, data, docs = evening(tmp_path, market, now=datetime(2026, 9, 11, 22, 30, tzinfo=timezone.utc))
    assert rep.exit_code() == 0, rep.problems
    assert data["run"]["session"] == "2026-09-11"
    held = {p["ticker"]: p for p in data["open_plans"]}
    assert set(held) == {"AAA", "COIL"}
    assert held["AAA"]["picked"] == SESSION and held["AAA"]["day"] == 1 and held["AAA"]["targets"]
    assert held["AAA"]["status"] in ("hold", "sell_half", "stopped", "exit", record.NOT_FILLED, record.UNCERTAIN)
    assert len(data["nights"]) == 2 and data["scorecard"]["plans"] == 2


def test_a_dry_run_writes_the_record_and_mails_nothing_and_records_no_pick(market, claude, fake_resend, tmp_path):
    rep, data, docs = evening(tmp_path, market, dry_run=True)
    assert rep.exit_code() == 0
    assert data["run"]["dry_run"] is True and data["run"]["email"] == "skipped"
    assert not (docs / record.PICKS_FILE).exists()
    assert fake_resend.sent == []


def test_the_committed_fixture_lends_the_first_night_neither_its_nights_nor_its_picks(market, claude, fake_resend, tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    fixture = json.loads((Path(__file__).parent / "fixtures" / "page" / "full.json").read_text())
    assert fixture["fixture"] == "full" and fixture["nights"] and fixture["open_plans"]
    (docs / pipeline.DATA_FILE).write_text(json.dumps(fixture))
    (docs / record.PICKS_FILE).write_text((Path(__file__).parent / "fixtures" / "page" / "full-picks.json").read_text())
    # PRECONDITION: the night under test is a later session than the fixture's,
    # or an inherited fixture night would be replaced by tonight's and hide.
    assert fixture["run"]["session"] < "2026-09-11"
    rep, data, docs = evening(tmp_path, market, now=datetime(2026, 9, 11, 22, 30, tzinfo=timezone.utc))
    assert rep.exit_code() == 0, rep.problems
    assert data["nights"] == [{"session": "2026-09-11", "status": "ok", "published_at": data["generated"]}]
    assert data["open_plans"] == [] and data["scorecard"]["plans"] == 0
    assert "fixture" not in data
    picks = json.loads((docs / record.PICKS_FILE).read_text())
    assert "fixture" not in picks and [p["ticker"] for p in picks["picks"]] == ["AAA", "COIL"]


# ------------------------------------------------------------ degraded ---
def test_claude_down_grades_by_the_checklist_alone_and_degrades_the_run(market, claude, fake_resend, tmp_path):
    claude.set_error(RuntimeError("502 upstream"))
    rep, data, docs = evening(tmp_path, market)
    assert rep.exit_code() == pipeline.EXIT_DEGRADED
    assert [p["kind"] for p in data["run"]["problems"]] == ["claude_unavailable"]
    burst = data["bursts"][0]
    assert burst["grade"] == burst["quality"]["grade"] == "A+"
    assert burst["claude"]["source"] != "claude" and burst["claude"]["error"]
    assert data["trades"] == ["AAA"]                      # the checklist's grade still trades
    assert data["run"]["reads"]["done"] == 0


def test_claude_may_lower_a_grade_and_never_raise_it(market, claude, fake_resend, tmp_path):
    claude.set_payload({**CLAUDE_A_PLUS, "score": 5.5, "grade": "C"})
    rep, data, docs = evening(tmp_path, market)
    burst = data["bursts"][0]
    assert burst["quality"]["grade"] == "A+" and burst["grade"] == "C" and burst["claude"]["agree"] is False
    assert data["trades"] == [] and data["cover"]["h1"] == "Nothing qualifies. Keep cash."
    assert data["closest_miss"]["ticker"] == "AAA"


def test_claude_cannot_raise_a_grade_the_checklist_capped(fake_alpaca, seed, claude, fake_resend, tmp_path):
    """An H-only miss is capped at B by the checklist; Claude answering A+ is
    kept as its opinion and the grade stays B, so the name is not traded."""
    fake_alpaca.add_history("HMISS", qframe(ideal_bars(close_pos=0.55)))
    for name, df in base_frames(11, seed).items():
        fake_alpaca.add_history(name, df)
    fake_alpaca.add_history("SPY", make_ohlcv("base", seed=[seed, 999], days=260))
    rep, data, docs = evening(tmp_path, ["HMISS"] + [f"B{chr(65 + i)}{chr(65 + i)}" for i in range(11)])
    burst = data["bursts"][0]
    assert burst["quality"]["grade"] == "B" and burst["claude"]["source"] == "claude"
    assert burst["grade"] == "B" and burst["claude"]["grade"] == "B" and burst["claude"]["agree"] is True
    assert data["trades"] == [] and data["run"]["graded"] == {"a_plus": 0, "a": 0, "b": 1, "c": 0, "skip": 0}


def dollar_day(seed: int, variant: int, *, ratio: float, gain: float = 2.0, prev_volume: float | None = None) -> pd.DataFrame:
    """A quiet walk rescaled so the previous close is $100, whose last session
    opens there and closes ``gain`` percent up on ``ratio`` of the previous
    session's volume: at 2% the dollar scan's day alone (a $2 body, no 4%
    burst); at 5% on more volume both scans' day. ``prev_volume`` rewrites
    the previous session's volume (0 for a halt)."""
    df = make_ohlcv("base", seed=[seed, variant], days=260)
    prices = ["Open", "High", "Low", "Close"]
    df[prices] = df[prices] * (100.0 / float(df["Close"].iloc[-2]))
    if prev_volume is not None:
        df.iloc[-2, df.columns.get_loc("Volume")] = prev_volume
    v1 = float(df["Volume"].iloc[-2])
    close = round(100.0 * (1 + gain / 100), 2)
    df.iloc[-1, df.columns.get_loc("Open")] = 100.0
    df.iloc[-1, df.columns.get_loc("High")] = round(close + 0.9, 2)
    df.iloc[-1, df.columns.get_loc("Low")] = 99.6
    df.iloc[-1, df.columns.get_loc("Close")] = close
    df.iloc[-1, df.columns.get_loc("Volume")] = round((v1 or 3_000_000.0) * ratio)
    return df


def test_a_dollar_only_day_carries_the_scans_volume_ratio_into_its_row(seed):
    """RVTY on the first real night: a $1.91 body on 0.86x the previous
    session's volume, +2.8%, the dollar scan's day alone -- and its row's
    volume_vs_prior was null while the checklist's block held 0.86, so the
    page listed it as unmeasured. The row carries the scan's own ratio now,
    at the scan's four places (the checklist's two-place copy is a copy, not
    what is written over it); a day both scans see carries the 4% scan's;
    and a previous session that printed nothing leaves both readings None,
    the row still in the list, so the page says the measurement is missing
    rather than inventing one."""
    frames = {"AAA": a_plus_frame(), "DLR": dollar_day(seed, 7, ratio=0.8649), "BOTH": dollar_day(seed, 9, ratio=1.5, gain=5.0),
              "HALT": dollar_day(seed, 8, ratio=0.9, prev_volume=0)}
    uni = SimpleNamespace(names={"DLR": "Dollar Day Inc"}, flags={})
    rows = {r["ticker"]: r for r in pipeline.scan_frames(frames, uni, pipeline.RunReport())[0]}
    dlr = rows["DLR"]
    assert dlr["scan"] == "dollar" and dlr["gain_pct"] == 2.0 and dlr["dollar_move"] == 2.0
    assert dlr["volume_vs_prior"] == scans.dollar_breakout(frames["DLR"])["volume_vs_prior"] == 0.8649
    assert dlr["quality"]["burst"]["volume_vs_prior"] == 0.86
    aaa = rows["AAA"]
    assert aaa["scan"] == "burst" and aaa["volume_vs_prior"] == scans.burst_4pct(frames["AAA"])["volume_vs_prior"] > 1
    both = rows["BOTH"]
    assert both["scan"] == "both" and both["gain_pct"] == 5.0
    assert both["volume_vs_prior"] == scans.burst_4pct(frames["BOTH"])["volume_vs_prior"] == scans.dollar_breakout(frames["BOTH"])["volume_vs_prior"] == 1.5
    halt = rows["HALT"]
    assert halt["scan"] == "dollar" and halt["volume_vs_prior"] is None and halt["quality"]["burst"]["volume_vs_prior"] is None
    assert set(rows) == {"AAA", "DLR", "BOTH", "HALT"}


def test_the_committed_fixture_carries_the_dollar_scans_ratio_beside_the_checklists_copy():
    """The full fixture holds a $-only burst (DLLR), and its row's ratio is the
    scan's own: the last two bars of its archived series at four places, the
    checklist's block the same number at two, the summary sentence saying it.
    A fixture that lost the row, or the ratio, fails here rather than at the
    page smoke."""
    data = json.loads((Path(__file__).resolve().parent / "fixtures" / "page" / "full.json").read_text())
    dollar = [b for b in data["bursts"] if b["scan"] == "dollar"]
    assert dollar and all(len(b.get("series") or []) >= 2 for b in dollar), [b["ticker"] for b in dollar]
    for b in dollar:
        last, prev = b["series"][-1], b["series"][-2]
        assert b["volume_vs_prior"] == round(last["v"] / prev["v"], scans.RATIO_DECIMALS) < 1, (b["ticker"], b["volume_vs_prior"])
        assert b["quality"]["burst"]["volume_vs_prior"] == round(b["volume_vs_prior"], 2), b["ticker"]
        assert f"on {b['volume_vs_prior']:.1f}× volume" in b["summary"], b["summary"]


def test_the_slot_count_and_the_status_word_are_the_named_rules():
    plans = [{"status": s} for s in ("hold", "sell_half", "sell_into_strength", "pending", "stopped", "exit",
                                      "expired", record.NOT_FILLED, record.UNCERTAIN, "unmeasured")]
    assert pipeline.slots_held(plans) == 5
    assert pipeline.SLOT_STATUSES == ("hold", "sell_half", "sell_into_strength", "pending", record.UNCERTAIN)
    rep = pipeline.RunReport()
    assert pipeline.run_status(rep, closed=True) == "closed" and pipeline.run_status(rep, closed=False) == "ok"
    rep.problem("chart_missing", "x")
    assert pipeline.run_status(rep, closed=True) == "degraded"


def test_an_email_failure_keeps_the_record_and_exits_three(market, claude, fake_resend, tmp_path):
    fake_resend.raises = RuntimeError("Resend refused")
    rep, data, docs = evening(tmp_path, market)
    assert rep.exit_code() == pipeline.EXIT_FAILED_AFTER_PUBLISH
    assert data["run"]["email"] == "failed" and data["run"]["status"] == "degraded"
    assert [p["kind"] for p in data["run"]["problems"]] == ["email_failed"]
    assert data["trades"] == ["AAA"]


# --------------------------------------------------------------- closed ---
def test_a_closed_market_republishes_the_previous_sessions_plans_unchanged(market, claude, fake_resend, fake_alpaca, tmp_path):
    """Night one publishes a trade for the 9th; the 10th is a holiday. The
    closed night re-presents the 9th's tickets verbatim, walks its picks as
    plans that have had no session yet, and records nothing new."""
    from datetime import date
    first, first_data, docs = evening(tmp_path, market, now=datetime(2026, 9, 9, 22, 30, tzinfo=timezone.utc))
    assert first_data["trades"] == ["AAA"]
    picks_before = (docs / record.PICKS_FILE).read_text()
    fake_alpaca.close_session(date(2026, 9, 10))
    rep, data, docs = evening(tmp_path, market)
    assert rep.exit_code() == 0, rep.problems
    run = data["run"]
    assert run["session_state"] == "closed" and run["status"] == "closed"
    assert run["expected_session"] == SESSION and run["session"] == "2026-09-09"
    assert data["cover"]["h1"] == report.H1_CLOSED and "The plans from 2026-09-09 stand" in data["cover"]["dek"]
    assert data["trades"] == ["AAA"] and [b["ticker"] for b in data["bursts"]] == [b["ticker"] for b in first_data["bursts"]]
    assert data["bursts"][0]["plan"]["order_json"] == first_data["bursts"][0]["plan"]["order_json"]
    assert data["watchlist"]["top"][0]["ticker"] == "COIL"
    held = {p["ticker"]: p for p in data["open_plans"]}
    assert held["AAA"]["status"] == "pending" and "No session since the 2026-09-09 pick" in held["AAA"]["instruction"]
    assert (docs / record.PICKS_FILE).read_text() == picks_before
    # the holiday is filed under the day nobody traded; the night before keeps its own row
    assert [(n["session"], n["status"]) for n in data["nights"]] == [("2026-09-09", "ok"), ("2026-09-10", "closed")]


def test_a_closed_first_night_has_nothing_to_carry_and_says_so(market, claude, fake_resend, fake_alpaca, tmp_path):
    from datetime import date
    fake_alpaca.close_session(date(2026, 9, 10))
    rep, data, docs = evening(tmp_path, market)
    assert rep.exit_code() == 0 and data["cover"]["h1"] == report.H1_CLOSED
    assert data["bursts"] == [] and data["trades"] == [] and data["open_plans"] == []


def test_a_closed_night_whose_email_failed_is_a_degraded_night_in_the_row(market, claude, fake_resend, fake_alpaca, tmp_path):
    from datetime import date
    fake_alpaca.close_session(date(2026, 9, 10))
    fake_resend.raises = RuntimeError("refused")
    rep, data, docs = evening(tmp_path, market)
    assert rep.exit_code() == pipeline.EXIT_FAILED_AFTER_PUBLISH
    assert data["run"]["status"] == "degraded"
    assert data["nights"][-1] == {"session": SESSION, "status": "degraded", "published_at": data["generated"]}


def test_an_a_plus_burst_the_account_cannot_size_is_cut_not_traded(market, claude, fake_resend, tmp_path, monkeypatch):
    monkeypatch.setenv("ACCOUNT_EQUITY", "100")
    rep, data, docs = evening(tmp_path, market)
    assert rep.exit_code() == 0, rep.problems
    assert data["trades"] == [] and data["beyond_cap"] == ["AAA"]
    assert data["cover"]["h1"] == report.H1_KEEP_CASH
    assert "1 with a qualifying setup and no ticket" in data["cover"]["dek"]
    cut = data["cash_budget"]["cut"][0]
    assert cut["ticker"] == "AAA" and cut["kind"] == "no_shares" and "cannot size it" in cut["reason"]
    assert data["bursts"][0]["plan"]["shares"] == 0 and data["bursts"][0]["plan"]["order_json"] is None
    assert json.loads((docs / record.PICKS_FILE).read_text())["picks"] == []


def test_a_textbook_burst_grades_a_plus_and_gets_a_ticket_narrowed_to_its_stop(fake_alpaca, seed, claude, fake_resend, tmp_path):
    """The field guide's own bar: its low sits 4.7% under the close, so at a
    fixed +4% ceiling neither the low nor the midpoint was inside his 4%
    line and the closeout withheld it. The limit is the stop's own ceiling
    now -- the midpoint 121.42 / 0.96 = 126.47, under the 129.18 day-2 line
    -- so the setup carries an executable ticket and a pick."""
    fake_alpaca.add_history("WIDE", qframe(ideal_bars()))
    for name, df in base_frames(11, seed).items():
        fake_alpaca.add_history(name, df)
    fake_alpaca.add_history("SPY", make_ohlcv("base", seed=[seed, 999], days=260))
    rep, data, docs = evening(tmp_path, ["WIDE"] + [f"B{chr(65 + i)}{chr(65 + i)}" for i in range(11)])
    assert rep.exit_code() == 0, rep.problems
    burst = data["bursts"][0]
    p = burst["plan"]
    assert burst["grade"] == "A+" and p["eligible"] is True and p["action"] == "buy_at_open"
    assert p["limit"] == 126.47 and p["day2_spent_above"] == 129.18 and p["limit_basis"] == "stop_line"
    assert p["stop"] == 121.42 and p["stop_basis"] == "half_range" and p["stop_pct"] <= plan.MAX_STOP_PCT
    assert p["order_json"]["limit_price"] == 126.47 and p["order_json"]["stop_price"] == p["entry_ref"]
    assert data["trades"] == ["WIDE"] and data["cash_budget"]["cut"] == []
    pick = json.loads((docs / record.PICKS_FILE).read_text())["picks"][0]
    assert pick["ticker"] == "WIDE" and pick["entry_high"] == 126.47 and pick["day2_spent_above"] == 129.18


def test_a_burst_no_limit_can_hold_a_stop_under_is_published_without_a_ticket(fake_alpaca, seed, claude, fake_resend, tmp_path):
    """The same shape with a 9% range: the low caps the limit at 118.32 and
    the midpoint at 123.83, both under the 124.21 buy stop, so no limit
    exists this bar can hold a stop under. The setup is published with its
    card and its reason; no ticket, no pick."""
    fake_alpaca.add_history("WIDE", qframe(ideal_bars(burst_range_pct=9.0)))
    for name, df in base_frames(11, seed).items():
        fake_alpaca.add_history(name, df)
    fake_alpaca.add_history("SPY", make_ohlcv("base", seed=[seed, 999], days=260))
    rep, data, docs = evening(tmp_path, ["WIDE"] + [f"B{chr(65 + i)}{chr(65 + i)}" for i in range(11)])
    assert rep.exit_code() == 0, rep.problems
    burst = data["bursts"][0]
    p = burst["plan"]
    assert p["eligible"] is False and p["action"] == "refused" and p["ticket_refusal"] == "no_room_above_the_trigger"
    assert p["reason"].startswith("ticket withheld: no limit above the") and p["order_json"] is None
    assert data["trades"] == [] and data["beyond_cap"] == ["WIDE"]
    assert data["cash_budget"]["cut"] == [{"ticker": "WIDE", "kind": "withheld", "reason": p["reason"]}]
    assert data["cover"]["h1"] == report.H1_KEEP_CASH and "1 with a qualifying setup and no ticket" in data["cover"]["dek"]
    assert data["closest_miss"] is None                      # a withheld ticket is not a miss
    assert json.loads((docs / record.PICKS_FILE).read_text())["picks"] == []


def test_a_thin_night_degrades_and_publishes_over_the_names_that_printed(market, claude, fake_resend, fake_alpaca, tmp_path):
    """Eight of thirteen names one session stale: under half carry the
    session, over five percent do. The run continues over the five that
    printed, says coverage_thin, and breadth counts those five."""
    stale = [f"B{chr(65 + i)}{chr(65 + i)}" for i in range(8)]
    for name in stale:
        fake_alpaca.add_history(name, fake_alpaca.history[name], stale_sessions=1)
    rep, data, docs = evening(tmp_path, market)
    assert rep.exit_code() == pipeline.EXIT_DEGRADED, rep.failure
    assert [p["kind"] for p in data["run"]["problems"]] == ["coverage_thin"]
    assert data["run"]["session"] == SESSION and data["run"]["coverage"]["stale"] == 8
    assert data["breadth"]["universe"] == 5 and data["trades"] == ["AAA"]


@pytest.mark.parametrize("name, value, words", [
    ("SCAN_SESSION_DATE", "tomorrow", "SCAN_SESSION_DATE"),
    ("ACCOUNT_EQUITY", "ten grand", "the account variables"),
    ("SCAN_SEND_EMAIL", "maybe", "SCAN_SEND_EMAIL"),
    ("SCAN_FEED", "bloomberg", "SCAN_FEED"),
    ("SCAN_UNIVERSE", "everything", "SCAN_UNIVERSE"),
])
def test_a_variable_the_code_does_not_understand_is_a_preflight_failure(market, claude, fake_resend, tmp_path, monkeypatch, name, value, words):
    monkeypatch.setenv(name, value)
    with pytest.raises(pipeline.PreflightError, match=words):
        pipeline.run_evening(tickers=market, docs=tmp_path / "docs", now=EVENING)
    assert not (tmp_path / "docs" / pipeline.DATA_FILE).exists() and fake_resend.sent == []


# --------------------------------------------------------------- failed ---
def test_a_feed_outage_fails_before_publishing_and_mails_the_notice(market, claude, fake_resend, fake_alpaca, tmp_path):
    fake_alpaca.raise_on_bars = ConnectionError("no route")
    rep, data, docs = evening(tmp_path, market)
    assert rep.exit_code() == pipeline.EXIT_FAILED and data is None
    assert len(fake_resend.sent) == 1
    assert fake_resend.sent[0]["subject"] == f"FAILED — no plan for {SESSION}"


def test_stale_frames_on_every_name_are_an_outage_not_a_market(market, claude, fake_resend, fake_alpaca, tmp_path):
    """Every frame two sessions old: neither the expected session nor the one
    before it is carried, so the bars say the feed answered stale frames."""
    for name in list(fake_alpaca.history):
        fake_alpaca.add_history(name, fake_alpaca.history[name], stale_sessions=2)
    rep, data, docs = evening(tmp_path, market)
    assert rep.exit_code() == pipeline.EXIT_FAILED and data is None
    assert "stale frames" in rep.failure


def test_session_state_reads_the_three_states_off_the_bars():
    from datetime import date
    expected = date(2026, 9, 10)

    def frames(dates):
        return {f"T{i}": pd.DataFrame({"Close": [1.0]}, index=pd.to_datetime([d])) for i, d in enumerate(dates)}
    assert pipeline.session_state({}, expected) == ("outage", 0.0)
    assert pipeline.session_state(frames(["2026-09-10"] * 5 + ["2026-09-09"] * 5), expected) == ("open", 0.5)
    assert pipeline.session_state(frames(["2026-09-10"] * 4 + ["2026-09-09"] * 6), expected)[0] == "outage"
    assert pipeline.session_state(frames(["2026-09-09"] * 20 + ["2026-09-10"]), expected)[0] == "closed"    # 1 of 21 is under 5%
    assert pipeline.session_state(frames(["2026-09-09"] * 19 + ["2026-09-10"] * 2), expected)[0] == "outage"  # 2 of 21 is not
    assert pipeline.session_state(frames(["2026-09-09"] * 20), expected) == ("closed", 0.0)
    assert pipeline.session_state(frames(["2026-09-08"] * 20), expected)[0] == "outage"


# --------------------------------------------------------------- intraday ---
class _Snap:
    def __init__(self, **fields):
        self.__dict__.update(fields)


class FakeSnapshotClient:
    """Answers get_stock_snapshot with fixed prices: IEX for the trade, delayed
    SIP for the partial-day bar, the way run_intraday asks."""

    def __init__(self, quotes: dict):
        self.quotes, self.requests = quotes, []

    def get_stock_snapshot(self, request):
        self.requests.append(request)
        out = {}
        for symbol in request.symbol_or_symbols:
            q = self.quotes.get(symbol)
            if q is None:
                continue
            out[symbol] = _Snap(latest_trade=_Snap(price=q["last"]),
                                daily_bar=_Snap(open=q["open"], high=q["high"], low=q["low"], volume=q["volume"]),
                                previous_daily_bar=_Snap(close=q["prev_close"], volume=q["prev_volume"]))
        return out


def test_the_intraday_check_reads_the_previous_evenings_names_and_mails_only_a_confirmed_break(market, claude, fake_resend, tmp_path):
    evening(tmp_path, market)
    data = json.loads((tmp_path / "docs" / pipeline.DATA_FILE).read_text())
    coil = data["watchlist"]["top"][0]
    trigger, prev_close = coil["plan"]["trigger"], coil["close"]
    quotes = {"COIL": {"last": round(trigger + 0.5, 2), "open": prev_close, "high": trigger + 0.6, "low": prev_close - 0.2,
                       "volume": 500_000.0, "prev_close": prev_close, "prev_volume": 120_000.0},
              "AAA": {"last": 100.0, "open": 100.0, "high": 101.0, "low": 99.0, "volume": 10.0, "prev_close": 99.0, "prev_volume": 3_000_000.0}}
    client = FakeSnapshotClient(quotes)
    rep = pipeline.run_intraday(docs=tmp_path / "docs", now=datetime(2026, 9, 11, 19, 30, tzinfo=timezone.utc), client=client)
    assert rep.exit_code() == 0 and rep.published
    assert sorted(client.requests[0].symbol_or_symbols) == ["AAA", "COIL"]
    assert [getattr(r.feed, "value", r.feed) for r in client.requests] == ["iex", "delayed_sip"]
    live = json.loads((tmp_path / "docs" / pipeline.LIVE_FILE).read_text())
    rows = {r["ticker"]: r for r in live["rows"]}
    assert live["session"] == SESSION
    assert rows["COIL"]["kind"] == "anticipation" and rows["COIL"]["level"] == trigger
    assert rows["COIL"]["above_level"] is True and rows["COIL"]["volume_state"] == "confirmed"
    aaa = data["bursts"][0]["plan"]
    # the burst's level is its DAY-2 line, not the narrower price its ticket
    # can fill at: on this bar the two differ, so the field it reads is proved
    assert aaa["day2_spent_above"] != aaa["entry_high"]
    assert rows["AAA"]["kind"] == "burst" and rows["AAA"]["level"] == aaa["day2_spent_above"]
    assert rows["AAA"]["above_level"] is False and rows["AAA"]["volume_state"] == "not_yet"
    assert len(fake_resend.sent) == 2 and fake_resend.sent[-1]["subject"] == "Breakout in progress — COIL"
    assert "COIL" in fake_resend.sent[-1]["html"] and "AAA" not in fake_resend.sent[-1]["html"].split("above its level")[0].rsplit("<p>", 1)[-1]


def test_the_intraday_check_stays_silent_without_a_confirmed_break_and_fails_without_a_record(market, claude, fake_resend, tmp_path):
    evening(tmp_path, market)
    sent_before = len(fake_resend.sent)
    client = FakeSnapshotClient({"COIL": {"last": 1.0, "open": 1.0, "high": 1.0, "low": 1.0, "volume": None,
                                          "prev_close": 100.0, "prev_volume": None}})
    rep = pipeline.run_intraday(docs=tmp_path / "docs", client=client)
    assert rep.exit_code() == 0 and len(fake_resend.sent) == sent_before
    rows = json.loads((tmp_path / "docs" / pipeline.LIVE_FILE).read_text())["rows"]
    assert {r["ticker"]: r["volume_state"] for r in rows}["COIL"] == "unknown"
    empty = tmp_path / "nothing"
    empty.mkdir()
    rep = pipeline.run_intraday(docs=empty, client=client)
    assert rep.exit_code() == pipeline.EXIT_FAILED and "nothing to check" in rep.failure


def test_preflight_names_every_missing_variable_and_spends_nothing(monkeypatch, tmp_path):
    for name in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY", "ANTHROPIC_API_KEY", "RESEND_API_KEY", "EMAIL_TO"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(pipeline.PreflightError, match="ALPACA_API_KEY, ALPACA_SECRET_KEY, ANTHROPIC_API_KEY, RESEND_API_KEY, EMAIL_TO"):
        pipeline.run_evening(tickers=["AAA"], docs=tmp_path / "docs", now=EVENING)
    assert pipeline.missing_env("evening", dry_run=True) == ["ALPACA_API_KEY", "ALPACA_SECRET_KEY", "ANTHROPIC_API_KEY"]
    assert pipeline.missing_env("intraday") == ["ALPACA_API_KEY", "ALPACA_SECRET_KEY", "RESEND_API_KEY", "EMAIL_TO"]


def test_the_exit_codes_are_the_numbers_actions_reads():
    assert (pipeline.EXIT_OK, pipeline.EXIT_FAILED, pipeline.EXIT_DEGRADED, pipeline.EXIT_FAILED_AFTER_PUBLISH) == (0, 1, 2, 3)


def test_main_returns_the_reports_exit_code(market, claude, fake_resend, tmp_path, monkeypatch):
    real = pipeline.run_evening
    monkeypatch.setattr(pipeline, "run_evening", lambda **kw: real(**{**kw, "docs": tmp_path / "docs", "now": EVENING}))
    assert pipeline.main(["evening", "--tickers", ",".join(market)]) == 0
    assert pipeline.main(["evening", "--tickers", ",".join(market), "--dry-run"]) == 0
    claude.set_error(RuntimeError("down"))
    assert pipeline.main(["evening", "--tickers", ",".join(market)]) == pipeline.EXIT_DEGRADED
    monkeypatch.setenv("SCAN_SEND_EMAIL", "maybe")
    assert pipeline.main(["evening", "--tickers", ",".join(market)]) == pipeline.EXIT_FAILED


# --------------------------------------------------------- observations ---
def _frame(dates: list[str], closes: list[float]) -> pd.DataFrame:
    idx = pd.to_datetime(dates)
    return pd.DataFrame({"Open": closes, "High": [c * 1.01 for c in closes], "Low": [c * 0.99 for c in closes],
                         "Close": closes, "Volume": [1000.0] * len(closes)}, index=idx)


def test_observations_carry_the_newest_bar_for_tonights_signals_and_the_window_of_earlier_ones():
    session = date.fromisoformat(SESSION)
    frames = {"AAA": _frame(["2026-09-09", SESSION], [10.0, 10.5]), "KEEP": _frame(["2026-09-08", "2026-09-09"], [5.0, 5.2])}
    previous = {"observations": {"as_of": "2026-09-09", "days": pipeline.OBSERVATION_DAYS, "symbols": {
        "KEEP": {"date": "2026-09-09", "o": 5.0, "h": 5.1, "l": 4.9, "c": 5.2, "v": 900.0, "since": "2026-09-01"},
        "GONE": {"date": "2026-09-09", "o": 1.0, "h": 1.1, "l": 0.9, "c": 1.0, "v": 10.0, "since": "2026-09-02"},
        "OLD": {"date": "2026-08-01", "o": 2.0, "h": 2.1, "l": 1.9, "c": 2.0, "v": 10.0,
                "since": (session - timedelta(days=pipeline.OBSERVATION_DAYS + 1)).isoformat()},
        "JUNK": "not a bar"}}}
    block = pipeline.observations(frames, previous, {"AAA", "NOBAR"}, session)
    assert block["as_of"] == SESSION and block["days"] == pipeline.OBSERVATION_DAYS
    symbols = block["symbols"]
    assert symbols["AAA"] == {"date": SESSION, "o": 10.5, "h": 10.605, "l": 10.395, "c": 10.5, "v": 1000.0, "since": SESSION}
    assert symbols["KEEP"]["date"] == "2026-09-09" and symbols["KEEP"]["c"] == 5.2 and symbols["KEEP"]["since"] == "2026-09-01"
    assert symbols["GONE"] == previous["observations"]["symbols"]["GONE"]      # no frame tonight: the last observation, dated as it was
    assert "OLD" not in symbols and "JUNK" not in symbols and "NOBAR" not in symbols
    assert list(symbols) == sorted(symbols)


def test_a_previous_record_without_a_block_and_a_symbol_on_the_window_edge():
    session = date.fromisoformat(SESSION)
    edge = (session - timedelta(days=pipeline.OBSERVATION_DAYS)).isoformat()
    block = pipeline.observations({}, {"observations": {"symbols": {"EDGE": {"date": edge, "c": 1.0, "since": edge}}}}, set(), session)
    assert list(block["symbols"]) == ["EDGE"]
    assert pipeline.observations({}, {}, set(), session)["symbols"] == {}
    assert pipeline.observations({}, None, set(), session)["symbols"] == {}


def test_a_clean_night_publishes_observations_for_its_signals(market, claude, fake_resend, tmp_path):
    rep, data, docs = evening(tmp_path, market)
    assert rep.exit_code() == 0
    block = data["observations"]
    assert block["as_of"] == SESSION and block["days"] == pipeline.OBSERVATION_DAYS
    assert "AAA" in block["symbols"] and block["symbols"]["AAA"]["date"] == SESSION
    assert block["symbols"]["AAA"]["c"] == data["bursts"][0]["close"] and block["symbols"]["AAA"]["since"] == SESSION
    for row in data["watchlist"]["top"]:
        assert row["ticker"] in block["symbols"]
    assert data["_contract"]["observations"]
