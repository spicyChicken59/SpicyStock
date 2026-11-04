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


def _mail_text(markup: str) -> str:
    from tests.test_report import _rendered
    return _rendered(markup)


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
    assert run["reads"] == {"requested": 1, "done": 1, "unavailable_reason": None, "version": 2,
                            "causes": {"refused": 0, "format": 0, "account": 0, "credit": 0, "request": 0, "transport": 0},
                            "refusal_limit": 0, "refused_names": [], "refused_admissible": [], "verdict": "complete",
                            "unasked": 0, "sentence": None}
    assert run["input_tolerance"]["verdict"] == "complete" and run["input_tolerance"]["names"] == []
    assert run["stale_followup"]["reason"] == "no_previous_record" and run["stale_followup"]["sentence"] is None
    assert run["published_at"] == data["generated"]
    # where the publication fell against the service's schedule, as the run wrote it: 6:30 PM ET on
    # Thursday 10 Sep, between the slots, before Friday's open; and the archived slots beside it
    from src import delivery
    assert run["delivery"] == delivery.block(date.fromisoformat(SESSION), run["published_at"])
    assert (run["delivery"]["slot"], run["delivery"]["latency_minutes"], run["delivery"]["before_next_open"]) == ("after_primary", 135.0, True)
    assert data["rules"]["pipeline"]["delivery_version"] == delivery.VERSION and data["rules"]["pipeline"]["delivery_primary_et"] == "18:16"

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
    assert data["cover"]["h1"] == "Trade next session. 1 A-quality burst."
    assert data["cash_budget"]["slots_used"] == 2 and data["cash_budget"]["cut"] == []
    assert data["cash_budget"]["at_risk_usd"] == round(burst["plan"]["risk_usd"] + data["watchlist"]["top"][0]["plan"]["risk_usd"], 2)
    assert run["graded"] == {"a_plus": 1, "a": 0, "b": 0, "c": 0, "skip": 0}

    watch = data["watchlist"]
    assert [r["ticker"] for r in watch["top"]] == ["COIL"]
    assert watch["top"][0]["plan"]["order_line"] and watch["top"][0]["box"]["sessions"] >= 3
    assert watch["instruction"] == plan.ANTICIPATION_INSTRUCTION and watch["counts"]["coiled"] == 1
    assert data["open_plans"] == [] and data["scorecard"]["plans"] == data["scorecard"]["pending"] == 2
    assert data["nights"] == [{"session": SESSION, "status": "ok", "published_at": data["generated"]}]
    assert data["rules"]["plan"]["final_exit_day"] == plan.FINAL_EXIT_DAY
    assert data["breadth"]["universe"] >= 12 and data["breadth"]["notes"][0]["key"] == "ratio_10d"

    picks = json.loads((docs / record.PICKS_FILE).read_text())["picks"]
    assert [(p["ticker"], p["date"], p["kind"]) for p in picks] == [("AAA", SESSION, "burst"), ("COIL", SESSION, "anticipation")]
    assert picks[0]["entry_low"] < picks[0]["entry_ref"] < picks[0]["entry_high"] and picks[0]["targets"]["high"]
    assert (docs / pipeline.CHARTS_DIR_NAME / "AAA.png").exists()
    assert len(fake_resend.sent) == 1 and "Trade next session" in fake_resend.sent[0]["subject"]


def test_each_ticket_carries_its_earnings_warning_and_the_night_is_not_refused_for_it(market, claude, fake_resend,
                                                                                     fake_sec, tmp_path):
    # AAA reported last year two days after this session's date: estimated inside the hold;
    # SEC's list names no COIL, so its warning is unknown, never clear
    fake_sec.quarterly("AAA", 1001, "AAA HOLDINGS INC", SESSION, 2)
    rep, data, docs = evening(tmp_path, market)
    assert rep.exit_code() == 0 and rep.status == "ok", rep.problems
    block = data["run"]["earnings"]
    assert [(r["stage"], r["ticker"], r["verdict"], r["reason"]) for r in block["rows"]] == \
        [("burst", "AAA", "estimate_inside", None), ("anticipation", "COIL", "unknown", "not_mapped")]
    assert block["status"] == "checked" and block["requests"] == 2
    assert block["rows"][0]["window"] == list(dict.fromkeys(r["date"] for r in data["bursts"][0]["plan"]["exit_schedule"]))
    assert block["rows"][0]["retrieved_at"] == "2026-09-10T22:30:00Z"
    # a warning, never a refusal: the ticket and the pick stand
    assert data["trades"] == ["AAA"] and data["bursts"][0]["plan"]["order_json"]
    report.validate(data)
    assert data["rules"]["earnings_risk"]["policy"] == "warn_only"
    mail = _mail_text(fake_resend.sent[0]["html"])
    assert block["rows"][0]["sentence"] in mail and block["rows"][1]["sentence"] in mail
    # a forged verdict is refused by the record's own validator
    block["rows"][0]["verdict"] = "estimate_outside"
    with pytest.raises(ValueError, match="earnings"):
        report.validate(data)


def test_sec_down_leaves_every_ticket_unknown_and_publishes(market, claude, fake_resend, fake_sec, tmp_path):
    fake_sec.fail["sec.gov"] = "network_error"
    rep, data, _ = evening(tmp_path, market)
    assert rep.exit_code() == 0 and data["trades"] == ["AAA"]
    block = data["run"]["earnings"]
    assert block["status"] == "unavailable" and {r["reason"] for r in block["rows"]} == {"source_unavailable"}


def test_the_next_night_follows_the_pick_from_bars_alone(market, claude, fake_resend, tmp_path):
    evening(tmp_path, market)
    rep, data, docs = evening(tmp_path, market, now=datetime(2026, 9, 11, 22, 30, tzinfo=timezone.utc))
    assert rep.exit_code() == 0, rep.problems
    assert data["run"]["session"] == "2026-09-11"
    held = {p["ticker"]: p for p in data["open_plans"]}
    assert set(held) == {"AAA", "COIL"}
    assert held["AAA"]["picked"] == SESSION and held["AAA"]["day"] == 1 and held["AAA"]["targets"]
    assert held["AAA"]["status"] in ("hold", "sell_half", "stopped", "exit", record.NOT_FILLED, record.UNCERTAIN)
    assert len(data["nights"]) == 2
    published = json.loads((docs / record.PICKS_FILE).read_text())["picks"]
    assert data["scorecard"]["plans"] == len(published)
    assert data["scorecard"]["pending"] == sum(p["date"] == "2026-09-11" for p in published)


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
    assert data["open_plans"] == [] and data["scorecard"]["plans"] == data["scorecard"]["pending"] == 2
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
    assert data["trades"] == []                         # grade survives; coverage grants no permission
    assert burst["reader_coverage"] == "fallback" and burst["plan"] is None
    assert burst["evidence"]["gate"]["reason"] == "reader_coverage"
    assert all(p["ticker"] != "AAA" for p in json.loads((docs / record.PICKS_FILE).read_text())["picks"])
    assert data["run"]["reads"]["done"] == 0


def test_claude_may_lower_a_grade_and_never_raise_it(market, claude, fake_resend, tmp_path):
    from tests.test_reader_authority import finding
    claude.set_payload({**CLAUDE_A_PLUS, "score": 5.5, "grade": "C", "findings": [finding()]})
    rep, data, docs = evening(tmp_path, market)
    burst = data["bursts"][0]
    assert burst["quality"]["grade"] == "A+" and burst["grade"] == "C" and burst["claude"]["agree"] is False
    assert data["trades"] == [] and data["cover"]["h1"] == "Nothing qualifies. Keep cash."
    assert data["closest_miss"]["ticker"] == "AAA"


def test_claude_cannot_raise_a_grade_the_checklist_capped(fake_alpaca, seed, claude, fake_resend, tmp_path):
    """A mechanical A remains A despite an A+ reply. B names now remain outside
    the review pool; this A shape exercises the actual selected-reader path."""
    fake_alpaca.add_history("AMECH", qframe(ideal_bars(base_range=3.2)))
    for name, df in base_frames(11, seed).items():
        fake_alpaca.add_history(name, df)
    fake_alpaca.add_history("SPY", make_ohlcv("base", seed=[seed, 999], days=260))
    rep, data, docs = evening(tmp_path, ["AMECH"] + [f"B{chr(65 + i)}{chr(65 + i)}" for i in range(11)])
    burst = data["bursts"][0]
    assert burst["quality"]["grade"] == "A" and burst["claude"]["source"] == "claude"
    assert burst["claude"]["returned_grade"] == "A+"
    assert burst["grade"] == "A" and burst["claude"]["grade"] == "A" and burst["claude"]["agree"] is True
    assert data["run"]["graded"] == {"a_plus": 0, "a": 1, "b": 0, "c": 0, "skip": 0}


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
                                      "expired", record.NOT_FILLED, record.UNCERTAIN, "unmeasured", "unreadable")]
    assert pipeline.slots_held(plans) == 7
    assert pipeline.SLOT_STATUSES == ("hold", "sell_half", "sell_into_strength", "pending", record.UNCERTAIN, "unmeasured", "unreadable")
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
def test_known_holiday_preserves_every_file_and_sends_no_duplicate_signals(market, claude, fake_resend, fake_alpaca, tmp_path):
    first, data, docs = evening(tmp_path, market, now=datetime(2026, 9, 4, 22, 30, tzinfo=timezone.utc))
    assert first.published and data["run"]["timing"]["applicable_session"] == "2026-09-08"
    before = {p: p.read_bytes() for p in docs.rglob("*") if p.is_file()}
    calls = (len(fake_alpaca.bar_requests), len(claude.calls), len(fake_resend.sent))
    rep = pipeline.run_evening(docs=docs, now=datetime(2026, 9, 7, 22, 30, tzinfo=timezone.utc))
    assert rep.status == "no_session" and rep.exit_code() == 0 and not rep.published
    assert rep.calendar_outcome["most_recent_completed"] == "2026-09-04"
    assert before == {p: p.read_bytes() for p in docs.rglob("*") if p.is_file()}
    assert calls == (len(fake_alpaca.bar_requests), len(claude.calls), len(fake_resend.sent))


def test_known_holiday_first_run_creates_no_publication(market, claude, fake_resend, fake_alpaca, tmp_path):
    docs = tmp_path / "never_created"
    rep = pipeline.run_evening(docs=docs, now=datetime(2026, 9, 7, 22, 30, tzinfo=timezone.utc))
    assert rep.status == "no_session" and not docs.exists()
    assert fake_alpaca.bar_requests == [] and claude.calls == [] and fake_resend.sent == []


def test_expected_open_feed_absence_fails_without_republishing(market, claude, fake_resend, fake_alpaca, tmp_path):
    from datetime import date
    fake_alpaca.close_session(date(2026, 9, 10))
    rep, data, docs = evening(tmp_path, market)
    assert rep.failed and not rep.published and not data
    assert rep.input_coverage["acceptance"]["status"] == "fail"
    assert rep.input_coverage["stale"] == rep.input_coverage["with_bars"]


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
    assert data["cash_budget"]["cut"] == [{"ticker": "WIDE", "setup_kind": "burst", "kind": "withheld", "reason": p["reason"]}]
    assert data["cover"]["h1"] == report.H1_KEEP_CASH and "1 with a qualifying setup and no ticket" in data["cover"]["dek"]
    assert data["closest_miss"] is None                      # a withheld ticket is not a miss
    assert json.loads((docs / record.PICKS_FILE).read_text())["picks"] == []


def test_a_thin_night_degrades_and_publishes_over_the_names_that_printed(market, claude, fake_resend, fake_alpaca, tmp_path):
    """Six of thirteen names stale: usable coverage exceeds half and degrades."""
    stale = [f"B{chr(65 + i)}{chr(65 + i)}" for i in range(6)]
    for name in stale:
        fake_alpaca.add_history(name, fake_alpaca.history[name], stale_sessions=1)
    rep, data, docs = evening(tmp_path, market)
    assert rep.exit_code() == pipeline.EXIT_DEGRADED, rep.failure
    assert [p["kind"] for p in data["run"]["problems"]] == ["coverage_thin"]
    assert data["run"]["session"] == SESSION and data["run"]["coverage"]["stale"] == 6
    assert data["breadth"]["universe"] == 7 and data["trades"] == ["AAA"]


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
    text = _mail_text(fake_resend.sent[0]["html"])
    assert rep.stage in report.INPUT_STAGES and report.PROBLEM_SENTENCES["coverage_thin"] in text
    assert f"It stopped at its {rep.stage} stage, one of the stages that read the night's inputs;" in text


def _crash_planner(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("planner bug https://example.invalid")
    monkeypatch.setattr(pipeline, "make_plans", boom)


def test_a_failure_after_the_inputs_is_mailed_by_its_stage_and_not_as_missing_inputs(market, claude, fake_resend, tmp_path, monkeypatch):
    """A crash past the inputs' stages, on a night whose inputs were all ready:
    the notice names the stage it stopped at, claims no cause, and leaves what it
    raised to the run log."""
    _crash_planner(monkeypatch)
    rep, data, docs = evening(tmp_path, market)
    assert rep.exit_code() == pipeline.EXIT_FAILED and data is None and rep.stage == "grade" and rep.problems == []
    [sent] = fake_resend.sent
    text = _mail_text(sent["html"])
    assert sent["subject"] == f"FAILED — no plan for {SESSION}"
    assert ("It stopped at its grade stage, after its universe, fetch and session stages had passed; "
            "what it raised is in the workflow's run log, not in this mail.") in text
    assert report.PROBLEM_SENTENCES["coverage_thin"] not in text
    assert "No problem was recorded before it stopped." in text and "what went wrong tonight" not in text
    assert "planner bug" not in sent["html"] and "example.invalid" not in sent["html"]


def test_a_missing_input_recorded_before_a_later_failure_is_mailed_beside_its_stage(market, claude, fake_resend, fake_alpaca, tmp_path, monkeypatch):
    """A night that recorded a missing input and then crashed past the inputs'
    stages mails both: the stage it stopped at, and the problem as recorded."""
    fake_alpaca.add_history("BAA", fake_alpaca.history["BAA"], stale_sessions=1)
    _crash_planner(monkeypatch)
    rep, data, docs = evening(tmp_path, market)
    assert rep.exit_code() == pipeline.EXIT_FAILED and data is None and rep.stage == "grade"
    assert [(p["stage"], p["kind"]) for p in rep.problems] == [("session", "coverage_thin")]
    text = _mail_text(fake_resend.sent[0]["html"])
    assert "It stopped at its grade stage, after its universe, fetch and session stages had passed;" in text
    assert report.PROBLEM_SENTENCES["coverage_thin"] in text


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
    assert pipeline.session_state(frames(["2026-09-09"] * 20 + ["2026-09-10"]), expected)[0] == "outage"    # an expected session, even if almost every frame lacks it
    assert pipeline.session_state(frames(["2026-09-09"] * 19 + ["2026-09-10"] * 2), expected)[0] == "outage"  # 2 of 21 is not
    assert pipeline.session_state(frames(["2026-09-09"] * 20), expected) == ("outage", 0.0)
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
    # A real session is part of this fixture; the wall clock may be a weekend.
    now = datetime(2026, 9, 11, 13, 45, tzinfo=timezone.utc)
    sent_before = len(fake_resend.sent)
    client = FakeSnapshotClient({"COIL": {"last": 1.0, "open": 1.0, "high": 1.0, "low": 1.0, "volume": None,
                                          "prev_close": 100.0, "prev_volume": None}})
    rep = pipeline.run_intraday(docs=tmp_path / "docs", client=client, now=now)
    assert rep.exit_code() == 0 and len(fake_resend.sent) == sent_before
    rows = json.loads((tmp_path / "docs" / pipeline.LIVE_FILE).read_text())["rows"]
    assert {r["ticker"]: r["volume_state"] for r in rows}["COIL"] == "unknown"
    empty = tmp_path / "nothing"
    empty.mkdir()
    rep = pipeline.run_intraday(docs=empty, client=client, now=now)
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


# ------------------------------------------------ the discovery admission ----
def dollar_a_frame(expansion: bool) -> pd.DataFrame:
    """A dollar-only day the checklist grades in the A band (src/admission.py).
    With ``expansion``: +2.5% over the previous close on a $2.88 body, a bar 3%
    wide against a base of 0.8%-wide bars, on double the previous session's
    volume -- RE and VOL pass, the 4% scan does not match. Without: +2% on a
    $1.43 body inside a 1.5%-wide bar narrower than the base's 2%-wide bars,
    on five-sixths of the previous session's volume -- RE and VOL fail, and
    the wider base fails C, so the checklist scores it 8.0 and grades it A,
    the shape 32 of the 34 dollar-only A names of 3 November 2026 had."""
    if expansion:
        return qframe(ideal_bars(burst_gain=2.5, close_pos=0.9, burst_vol=1_200_000, burst_range_pct=3.0))
    return qframe(ideal_bars(burst_gain=2.0, close_pos=0.9, burst_vol=500_000, burst_range_pct=1.5, base_range=2.0))


def _market_with(fake_alpaca, seed, ticker, frame):
    """The night's universe with one more name beside the A+ burst and the coil."""
    fake_alpaca.add_history("AAA", a_plus_frame())
    fake_alpaca.add_history(ticker, frame)
    fake_alpaca.add_history("COIL", coil())
    for name, df in base_frames(11, seed).items():
        fake_alpaca.add_history(name, df)
    fake_alpaca.add_history("SPY", make_ohlcv("base", seed=[seed, 999], days=260))
    return ["AAA", ticker, "COIL"] + [f"B{chr(65 + i)}{chr(65 + i)}" for i in range(11)]


def test_a_dollar_only_a_without_expansion_is_research_only_whatever_the_reader_would_say(fake_alpaca, seed, claude, fake_resend, tmp_path):
    """The rule of 4 November 2026: a dollar-only day without a range-expansion,
    higher-volume day is not admitted. The checklist still grades it A; the run
    asks no reader about it, plans nothing for it, blocks it at the selection
    and the funnel, seals its gate as the admission, and counts it as A-band
    not admitted -- while the 4% burst beside it is planned and traded."""
    from src import admission, provenance
    tickers = _market_with(fake_alpaca, seed, "DNO", dollar_a_frame(expansion=False))
    rep, data, docs = evening(tmp_path, tickers)
    assert rep.exit_code() == 0 and rep.status == "ok", rep.problems
    rows = {b["ticker"]: b for b in data["bursts"]}
    dno = rows["DNO"]
    assert dno["scan"] == "dollar" and dno["grade_mechanical"] == "A" and dno["grade"] == "A" and dno["vetoes"] == []
    assert dno["admission"] == admission.block(dno)
    assert dno["admission"]["basis"] == "dollar_no_expansion" and dno["admission"]["admitted"] is False
    assert dno["admission"]["expansion"] == {"range_expansion": False, "higher_volume": False}
    # no read, no plan, blocked at the selection and not research either
    assert dno["claude"] is None and dno["reader_coverage"] == "not_selected_budget" and dno["plan"] is None
    assert dno["review_selection"]["blockers"] == ["route_not_admitted"]
    assert dno["review_selection"]["research_pool"] is False and dno["review_selection"]["purpose"] == "outside_research_pool"
    assert data["run"]["reads"]["requested"] == 1 and data["run"]["review_selection"]["blockers"]["route_not_admitted"] == 1
    assert data["run"]["review_selection"]["policy"] == "account_feasible_first_research_v2"
    # the burst beside it is planned and traded as before
    assert data["trades"] == ["AAA"] and rows["AAA"]["admission"]["basis"] == "burst_route"
    assert data["cover"]["h1"] == "Trade next session. 1 A-quality burst."
    # the night's own accounting
    assert data["run"]["admission"] == admission.summary(data["bursts"], ["A+", "A"])
    assert data["run"]["admission"]["in_band"] == {"total": 2, "burst_route": 1, "dollar_expansion": 0, "dollar_no_expansion": 1}
    assert "1 came through the dollar scan alone without one and is research only" in data["run"]["admission"]["sentence"]
    stages = {r["ticker"]: r["stage"] for r in data["funnel"]["reaction"]["rows"]}
    assert stages["DNO"] == "route" and data["funnel"]["reaction"]["stages"]["route"] == 1
    assert data["funnel"]["reaction"]["potentially_usable"] == 1 and data["funnel"]["version"] == 3
    assert dno["evidence"]["gate"]["reason"] == "route_not_admitted" and dno["evidence"]["gate"]["ticket"] is False
    assert data["rules"]["admission"]["version"] == 1 and data["rules"]["admission"]["dollar_checks"] == ["RE", "VOL"]
    assert provenance.verify(data, objects=docs / "evidence")["status"] == "PASS"
    assert report.validate(data) is None
    # the mail says so in the record's words
    assert "// discovery admission" in _mail_text(fake_resend.sent[-1]["html"]) and data["run"]["admission"]["sentence"] in _mail_text(fake_resend.sent[-1]["html"])


def test_the_planner_itself_refuses_a_stopped_name_even_without_the_reader():
    """The admission gate is the planner's own (pipeline._make_plans), so a
    replay that asks no reader -- tools/historical_backtest.py runs it with
    require_reader False -- still plans nothing for a stopped name; the block is
    what it reads, so a forged block admits (which report.validate() refuses
    elsewhere)."""
    import copy, json
    from datetime import date
    from src import plan, pipeline as pl
    data = json.loads((Path(__file__).parent / "fixtures" / "page" / "full.json").read_text())
    rows = {b["ticker"]: copy.deepcopy(b) for b in data["bursts"] if b["ticker"] in ("AAPL", "MSFT")}
    assert rows["MSFT"]["admission"]["admitted"] is False and rows["AAPL"]["admission"]["admitted"] is True
    regime, session = data["breadth"]["regime"], date.fromisoformat(data["run"]["session"])
    bursts = [rows["AAPL"], rows["MSFT"]]
    trades, _, _ = pl._make_plans(bursts, plan.Account(), regime, 0, session, require_reader=False)
    assert rows["AAPL"]["plan"] is not None and rows["MSFT"]["plan"] is None and trades == ["AAPL"]
    assert rows["MSFT"]["evidence"]["gate"]["reason"] == "route_not_admitted"
    forged = copy.deepcopy(rows["MSFT"])
    forged["admission"]["admitted"] = True
    pl._make_plans([forged], plan.Account(), regime, 0, session, require_reader=False)
    assert forged["plan"] is not None, "the planner reads the block, not the route"


def test_a_dollar_only_a_with_expansion_is_admitted_read_and_planned_like_a_burst(fake_alpaca, seed, claude, fake_resend, tmp_path):
    """The same route on a range-expansion, higher-volume day is admitted: the
    reader is asked, an accepted review lets it be planned, and its ticket is
    the dollar scan's own (plan.scan 'dollar')."""
    from src import admission, provenance
    tickers = _market_with(fake_alpaca, seed, "DEX", dollar_a_frame(expansion=True))
    rep, data, docs = evening(tmp_path, tickers)
    assert rep.exit_code() == 0 and rep.status == "ok", rep.problems
    rows = {b["ticker"]: b for b in data["bursts"]}
    dex = rows["DEX"]
    assert dex["scan"] == "dollar" and dex["grade_mechanical"] in ("A+", "A") and dex["gain_pct"] < 4
    assert dex["admission"]["basis"] == "dollar_expansion" and dex["admission"]["admitted"] is True
    assert dex["admission"]["expansion"] == {"range_expansion": True, "higher_volume": True}
    assert dex["review_selection"]["feasible"] is True and dex["review_selection"]["selected"] is True
    assert dex["claude"]["source"] == "claude" and dex["reader_coverage"] == "accepted"
    assert dex["plan"] is not None and dex["plan"]["scan"] == "dollar"
    assert set(data["trades"]) == {"AAA", "DEX"} and data["run"]["reads"]["requested"] == 2
    assert data["run"]["admission"]["in_band"] == {"total": 2, "burst_route": 1, "dollar_expansion": 1, "dollar_no_expansion": 0}
    stages = {r["ticker"]: r["stage"] for r in data["funnel"]["reaction"]["rows"]}
    assert stages["DEX"] == "ticket" and data["funnel"]["reaction"]["stages"]["route"] == 0
    assert dex["evidence"]["gate"]["ticket"] is True and dex["evidence"]["gate"]["reason"] is None
    assert provenance.verify(data, objects=docs / "evidence")["status"] == "PASS"
