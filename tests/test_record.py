"""src.record: the picks file, the fill rule, the walk, the scorecard, the
reliability row. Every walk here is driven on bars built by hand, so each
rule is pinned on the bar that decides it and nothing else."""
from __future__ import annotations

import json

import pandas as pd
import pytest

from src import plan, record


# ------------------------------------------------------------- helpers ----
def frame(rows: list[tuple[str, float, float, float, float]], volume: float = 1_000_000.0) -> pd.DataFrame:
    """A frame from (date, open, high, low, close) rows."""
    idx = pd.to_datetime([r[0] for r in rows])
    return pd.DataFrame({"Open": [r[1] for r in rows], "High": [r[2] for r in rows],
                         "Low": [r[3] for r in rows], "Close": [r[4] for r in rows],
                         "Volume": [volume] * len(rows)}, index=idx)


def pick(**over) -> dict:
    base = {"ticker": "AAA", "date": "2026-09-01", "kind": "burst", "grade": "A", "score": 8.2,
            "entry_ref": 100.0, "entry_low": 99.0, "entry_high": 102.0, "stop": 96.0, "shares": 10,
            "targets": {"low": 108.0, "high": 120.0}}
    base.update(over)
    return base


# the sessions after the 1 Sep pick, a clean uptrend closing at +12% on day 5
LATER = [("2026-09-02", 100.5, 103.0, 100.0, 102.0),
         ("2026-09-03", 102.5, 105.0, 101.5, 104.0),
         ("2026-09-04", 104.0, 106.0, 103.0, 105.0),
         ("2026-09-08", 105.5, 110.0, 105.0, 109.0),
         ("2026-09-09", 109.5, 113.0, 108.5, 112.0)]
PICK_DAY = ("2026-09-01", 95.0, 101.0, 94.0, 100.0)


def calendar_frames(n_names: int = 3) -> dict[str, pd.DataFrame]:
    """Enough frames for session_calendar() to vote: the pick day plus LATER
    on every name, and SPY on the same days."""
    rows = [PICK_DAY] + LATER
    frames = {f"C{i}": frame(rows) for i in range(n_names)}
    frames["SPY"] = frame([(d, 500.0 + i, 502.0 + i, 499.0 + i, 501.0 + i) for i, (d, *_) in enumerate(rows)])
    return frames


# ---------------------------------------------------------------- file ----
def test_a_missing_file_is_an_empty_record(tmp_path):
    rec = record.load(tmp_path)
    assert rec == {"schema_version": record.SCHEMA_VERSION, "picks": []}


def test_save_then_load_round_trips_and_drops_the_problem_key(tmp_path):
    rec = record.append(record.empty(), "2026-09-01", [pick()])
    rec["problem"] = "not stored"
    record.save(rec, tmp_path)
    loaded = record.load(tmp_path)
    assert "problem" not in loaded
    assert loaded["picks"][0]["ticker"] == "AAA" and loaded["picks"][0]["date"] == "2026-09-01"
    assert loaded["picks"][0]["regime"] == "green"


def test_an_unreadable_file_is_set_aside_not_overwritten(tmp_path):
    (tmp_path / record.PICKS_FILE).write_text("{not json")
    rec = record.load(tmp_path)
    assert rec["picks"] == [] and "set aside" in rec["problem"]
    aside = list(tmp_path.glob("picks.json.*.unreadable"))
    assert len(aside) == 1 and aside[0].read_text() == "{not json"
    assert not (tmp_path / record.PICKS_FILE).exists()


def test_the_committed_fixture_is_never_walked_as_history(tmp_path):
    """A fresh clone carries tests/fixtures/page/full-picks.json as
    docs/picks.json so the page has something to show; its picks are
    invented and the first real night must start from nothing."""
    body = {"fixture": "full", "schema_version": 1, "picks": [pick()]}
    (tmp_path / record.PICKS_FILE).write_text(json.dumps(body))
    rec = record.load(tmp_path)
    assert rec == record.empty()
    assert (tmp_path / record.PICKS_FILE).exists()          # not set aside: save() replaces it
    record.save(record.append(rec, "2026-09-01", [pick(ticker="REAL")]), tmp_path)
    assert [p["ticker"] for p in record.load(tmp_path)["picks"]] == ["REAL"]


def test_a_record_without_a_picks_list_is_set_aside(tmp_path):
    (tmp_path / record.PICKS_FILE).write_text(json.dumps({"picks": "nope"}))
    rec = record.load(tmp_path)
    assert rec["picks"] == [] and "picks list" in rec["problem"]
    assert list(tmp_path.glob("picks.json.*.unreadable"))


MALFORMED_PICKS = [
    ("not an object", "a pick is not an object"),
    ({k: v for k, v in pick().items() if k != "stop"}, "lacks stop"),
    (pick(ticker=""), "ticker is not a symbol"),
    (pick(date="yesterday"), "not YYYY-MM-DD"),
    (pick(kind="hunch"), "kind"),
    (pick(entry_ref="100"), "entry_ref is not a positive price"),
    (pick(stop=float("nan")), "stop is not a positive price"),
    (pick(entry_ref=95.0), "not above the stop"),
    (pick(shares=2.5), "shares is not a whole number"),
    (pick(shares=True), "shares is not a whole number"),
    (pick(entry_high="high"), "entry_high is not a number"),
    (pick(entry_high=99.5), "outside its zone"),
    (pick(kind="anticipation", trigger=95.0, limit=96.0), "trigger 95.0 is not above the stop"),
    (pick(kind="anticipation", trigger=100.0, limit=99.0), "limit 99.0 is under the trigger"),
]


@pytest.mark.parametrize("bad, words", MALFORMED_PICKS, ids=[w for _, w in MALFORMED_PICKS])
def test_a_malformed_pick_is_dropped_at_load_and_named(tmp_path, bad, words):
    body = {"schema_version": 1, "picks": [pick(ticker="OK"), bad]}
    (tmp_path / record.PICKS_FILE).write_text(json.dumps(body, default=str))
    rec = record.load(tmp_path)
    assert [p["ticker"] for p in rec["picks"]] == ["OK"]
    assert "1 malformed" in rec["problem"] and words in rec["problem"]


def test_the_load_check_can_fail_on_a_good_pick():
    assert record.pick_problem(pick()) is None


def test_append_stamps_the_session_and_regime_and_replaces_a_rerun():
    rec = record.append(record.empty(), "2026-09-01", [pick(shares=5)], "yellow")
    rec = record.append(rec, "2026-09-01", [pick(shares=7)], "green")
    assert len(rec["picks"]) == 1
    assert rec["picks"][0]["shares"] == 7 and rec["picks"][0]["regime"] == "green"
    rec = record.append(rec, "2026-09-02", [pick(ticker="BBB")])
    assert [(p["date"], p["ticker"]) for p in rec["picks"]] == [("2026-09-01", "AAA"), ("2026-09-02", "BBB")]


def test_append_refuses_a_pick_the_walk_could_not_read():
    with pytest.raises(ValueError, match="not above the stop"):
        record.append(record.empty(), "2026-09-01", [pick(entry_ref=90.0)])
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        record.append(record.empty(), "tonight", [pick()])


def test_append_keeps_the_newest_max_picks(monkeypatch):
    monkeypatch.setattr(record, "MAX_PICKS", 3)
    rec = record.empty()
    for i in range(5):
        rec = record.append(rec, f"2026-09-0{i + 1}", [pick()])
    assert [p["date"] for p in rec["picks"]] == ["2026-09-03", "2026-09-04", "2026-09-05"]


# ------------------------------------------------------------ the bars ----
def test_later_bars_are_the_sessions_after_the_pick_through_the_session_oldest_first():
    df = frame([PICK_DAY] + LATER)
    bars = record.later_bars(df, "2026-09-01", "2026-09-04")
    assert [b["date"] for b in bars] == ["2026-09-02", "2026-09-03", "2026-09-04"]
    assert bars[0] == {"o": 100.5, "h": 103.0, "l": 100.0, "c": 102.0, "date": "2026-09-02"}


def test_a_bar_with_a_missing_price_is_left_out_rather_than_read_as_the_next():
    rows = [PICK_DAY] + LATER
    df = frame(rows)
    df.loc[pd.Timestamp("2026-09-03"), "High"] = float("nan")
    bars = record.later_bars(df, "2026-09-01")
    assert [b["date"] for b in bars] == ["2026-09-02", "2026-09-04", "2026-09-08", "2026-09-09"]


def test_later_bars_on_nothing_is_nothing():
    assert record.later_bars(None, "2026-09-01") == []
    assert record.later_bars(frame([PICK_DAY]), "not a date") == []


# ------------------------------------------------------------ the fill ----
@pytest.mark.parametrize("bar, status, price, words", [
    ({"o": 100.5, "h": 103.0}, "filled", 100.5, "filled at the open"),          # at/above the trigger
    ({"o": 100.0, "h": 101.0}, "filled", 100.0, "filled at the open"),          # exactly the trigger
    ({"o": 99.5, "h": 101.0}, "filled", 100.0, "filled at the trigger"),        # under the trigger, day reaches it
    ({"o": 99.5, "h": 100.0}, "filled", 100.0, "filled at the trigger"),        # the day's high exactly at the trigger
    ({"o": 99.5, "h": 99.9}, record.NOT_FILLED, None, "never reached"),         # under the trigger, never reaches
    ({"o": 102.01, "h": 104.0}, record.NOT_FILLED, None, "gap ate the trade"),  # above the limit
    ({"o": 102.0, "h": 104.0}, "filled", 102.0, "filled at the open"),          # exactly the limit
    ({"o": 98.99, "h": 104.0}, record.NOT_FILLED, None, "skip line"),           # under the skip line
    ({"o": 99.0, "h": 104.0}, "filled", 100.0, "filled at the trigger"),        # exactly the skip line
])
def test_the_burst_ticket_fills_the_way_a_stop_limit_does(bar, status, price, words):
    got = record.fill(pick(), {**bar, "l": min(bar["o"], 95.0), "c": bar["o"], "date": "2026-09-02"})
    assert got[0] == status and got[1] == price and words in got[2]


@pytest.mark.parametrize("bar, status, price, words", [
    ({"o": 50.2, "h": 51.0}, "filled", 50.2, "at the open"),
    ({"o": 49.5, "h": 50.5}, "filled", 50.0, "at the trigger"),
    ({"o": 49.5, "h": 49.9}, record.NOT_FILLED, None, "never reached"),
    ({"o": 50.51, "h": 52.0}, record.NOT_FILLED, None, "above the"),
])
def test_the_anticipation_ticket_fills_at_the_trigger_or_not_at_all(bar, status, price, words):
    p = pick(kind="anticipation", entry_ref=50.0, trigger=50.0, limit=50.5, stop=48.0, entry_low=None, entry_high=None)
    got = record.fill(p, {**bar, "l": 49.0, "c": bar["o"], "date": "2026-09-02"})
    assert got[0] == status and got[1] == price and words in got[2]


def test_a_pick_without_a_zone_fills_at_the_trigger_rule_alone():
    p = pick(entry_low=None, entry_high=None)
    assert record.fill(p, {"o": 150.0, "h": 151.0, "l": 149.0, "c": 150.0, "date": "x"})[0] == "filled"


# ------------------------------------------------------------ the walk ----
def test_replay_walks_from_the_fill_price_and_carries_the_published_stop_and_targets():
    bars = record.later_bars(frame([PICK_DAY] + LATER), "2026-09-01")
    row = record.replay(pick(), bars)
    assert row["entry_ref"] == 100.5                     # the day-1 open, inside the zone
    assert row["stop"] == 96.0 and row["targets"] == {"low": 108.0, "high": 120.0}
    assert row["fill"] == "filled at the open, $100.50"
    assert row["status"] == "exit" and row["day"] == 5   # day 5: out into strength
    assert row["exit_price"] == 112.0 and row["half_sold"] is True
    assert row["picked"] == "2026-09-01" and row["kind"] == "burst" and row["grade"] == "A"


def test_a_fill_at_the_trigger_is_walked_from_the_fill_not_from_that_mornings_open():
    """The reviewer's case: a burst whose low sits inside the entry zone. The
    day opens under the stop, runs through the trigger and fills there, and
    closes up. The position never traded under the stop, so day 1 is a hold;
    the walk used to read the pre-fill open as a stop-out and record -1R."""
    p = pick(entry_ref=106.0, entry_low=103.88, entry_high=110.24, stop=104.0, shares=8)
    bars = [{"date": "2026-09-02", "o": 103.9, "h": 106.5, "l": 103.9, "c": 106.2},
            {"date": "2026-09-03", "o": 106.5, "h": 108.0, "l": 106.0, "c": 107.5}]
    row = record.replay(p, bars)
    assert row["fill"] == "filled at the trigger, $106.00" and row["entry_ref"] == 106.0
    assert row["status"] == "hold" and row["day"] == 2 and row["exit_price"] is None
    assert not [e for e in row["events"] if e["event"].startswith("stopped")]
    # the same day at the open (inside the zone, above the stop) reads the whole bar
    at_open = record.replay(p, [{**bars[0], "o": 106.1}])
    assert at_open["fill"] == "filled at the open, $106.10"


def test_after_a_trigger_fill_only_the_close_decides_the_fill_day():
    """A high the price left behind before the fill is not a sale into
    strength; a close under the stop is a stop-out."""
    p = pick(entry_ref=100.0, entry_low=99.0, entry_high=102.0, stop=96.0, shares=10)
    ran_then_faded = [{"date": "2026-09-02", "o": 99.2, "h": 109.0, "l": 95.0, "c": 100.5}]
    row = record.replay(p, ran_then_faded)
    assert row["fill"] == "filled at the trigger, $100.00" and row["half_sold"] is False and row["status"] == "hold"
    closed_under = [{"date": "2026-09-02", "o": 99.2, "h": 101.0, "l": 95.0, "c": 95.5}]
    assert record.replay(p, closed_under)["status"] == "stopped"


def test_an_unreadable_first_bar_is_unreadable_not_a_confident_fill():
    row = record.replay(pick(), [{"date": "2026-09-02", "o": 200.0, "h": 103.0, "l": 100.0, "c": 102.0}])
    assert row["status"] == record.UNREADABLE and "could not be read" in row["instruction"]


def test_replay_with_no_bars_is_pending_and_says_so():
    row = record.replay(pick(), [])
    assert row["status"] == "pending" and row["day"] == 0 and "No session since" in row["instruction"]


def test_a_ticket_that_never_filled_has_no_result_and_nothing_to_hold():
    bars = record.later_bars(frame([PICK_DAY, ("2026-09-02", 103.0, 105.0, 102.5, 104.0)]), "2026-09-01")
    row = record.replay(pick(), bars)
    assert row["status"] == record.NOT_FILLED and row["exit_price"] is None
    assert "gap ate the trade" in row["instruction"] and "Nothing to hold" in row["instruction"]
    assert row["events"][0]["event"] == record.NOT_FILLED


def test_a_later_bar_the_walk_refuses_is_reported_not_raised():
    bars = [{"date": "2026-09-02", "o": 100.5, "h": 103.0, "l": 100.0, "c": 102.0},
            {"date": "2026-09-03", "o": 200.0, "h": 103.0, "l": 100.0, "c": 102.0}]   # open above its own high
    row = record.replay(pick(), bars)
    assert row["status"] == record.UNREADABLE and "could not be read" in row["instruction"]


def test_the_red_regime_reaches_the_walks_instruction():
    bars = record.later_bars(frame([PICK_DAY] + LATER[:1]), "2026-09-01")
    row = record.replay(pick(), bars, "red")
    assert plan.RED_CLAUSE in row["instruction"]


# --------------------------------------------------------------- R --------
def test_r_is_the_result_over_the_published_stop_with_the_half_weighted():
    row = {"entry_ref": 100.0, "exit_price": 110.0, "half_sold": True,
           "events": [{"event": "sell_half", "price": 108.0}, {"event": "day5_exit", "price": 110.0}]}
    assert record.r_multiple(row, 96.0) == 2.25          # 0.5 * 8/4 + 0.5 * 10/4
    assert record.r_multiple({**row, "half_sold": False}, 96.0) == 2.5
    assert record.r_multiple({**row, "exit_price": 94.0, "half_sold": False}, 96.0) == -1.5
    assert record.r_multiple({**row, "exit_price": None}, 96.0) is None
    assert record.r_multiple(row, 100.0) is None         # no risk to divide by


# ------------------------------------------------------- open plans -------
def test_open_plans_follow_every_pick_of_the_last_five_sessions_oldest_first():
    frames = calendar_frames()
    rec = record.empty()
    rec = record.append(rec, "2026-09-01", [pick(ticker="C0")])
    rec = record.append(rec, "2026-09-03", [pick(ticker="C1", entry_ref=104.0, entry_low=103.0, entry_high=106.0, stop=100.0)])
    rows = record.open_plans(rec, frames, "2026-09-09")
    assert [(r["ticker"], r["picked"]) for r in rows] == [("C0", "2026-09-01"), ("C1", "2026-09-03")]
    c0, c1 = rows
    assert c0["day"] == 5 and c0["status"] == "exit"
    assert c1["day"] == 3 and c1["sessions"] == 3 and c1["last_date"] == "2026-09-09"
    assert c1["status"] in ("sell_half", "hold", "sell_into_strength")


def test_open_plans_leave_out_tonights_picks_and_picks_older_than_the_window():
    frames = calendar_frames()
    rec = record.empty()
    rec = record.append(rec, "2026-08-25", [pick(ticker="C0")])   # six sessions back
    rec = record.append(rec, "2026-09-09", [pick(ticker="C1")])   # tonight: a trade, not a hold
    assert record.open_plans(rec, frames, "2026-09-09") == []
    rec = record.append(rec, "2026-09-01", [pick(ticker="C2")])   # exactly five sessions back: in
    assert [r["ticker"] for r in record.open_plans(rec, frames, "2026-09-09")] == ["C2"]


def test_the_window_can_fail():
    """A pick dated inside the window is walked; one session further back is
    not -- pinned on the boundary, because "five sessions" was the whole rule."""
    frames = calendar_frames()
    sessions = record.sessions_before(frames, "2026-09-09", record.OPEN_PLAN_SESSIONS)
    assert sessions == ["2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04", "2026-09-08"]


def test_a_pick_whose_name_the_night_did_not_fetch_is_unmeasured_not_invented():
    frames = calendar_frames()
    rec = record.append(record.empty(), "2026-09-01", [pick(ticker="GONE")])
    rows = record.open_plans(rec, frames, "2026-09-09")
    assert rows[0]["status"] == "unmeasured" and "No bars for GONE" in rows[0]["instruction"]


def test_a_name_with_no_bar_since_its_pick_is_unmeasured_not_a_live_ticket():
    """The market printed six sessions; this name printed none of them. A
    'buy per the plan' instruction would be about a name that stopped
    trading, and the plan must not hold a slot."""
    frames = calendar_frames()
    frames["HALT"] = frame([PICK_DAY])
    rec = record.append(record.empty(), "2026-09-01", [pick(ticker="HALT")])
    rows = record.open_plans(rec, frames, "2026-09-09")
    assert rows[0]["status"] == "unmeasured" and "No bar since the pick for HALT" in rows[0]["instruction"]
    # the same name on a night no session has passed is a ticket that stands
    frames_tonight = {k: frame([PICK_DAY]) for k in ("C0", "C1", "C2", "HALT")}
    rows = record.open_plans(rec, frames_tonight, "2026-09-02")
    assert rows[0]["status"] == "pending" and "No session since" in rows[0]["instruction"]


def test_sessions_before_falls_back_to_weekdays_without_a_calendar():
    assert record.sessions_before({}, "2026-09-09", 3) == ["2026-09-04", "2026-09-07", "2026-09-08"]
    assert record.sessions_before({}, "bad", 3) == []


# -------------------------------------------------------- scorecard -------
def _scored(n_wins: int, n_losses: int, monkeypatch, min_read: int | None = None) -> dict:
    """A record of n_wins winning and n_losses losing picks, all settled."""
    if min_read is not None:
        monkeypatch.setattr(record, "SCORECARD_MIN_PLANS", min_read)
    rows = [PICK_DAY] + LATER
    losing = [PICK_DAY, ("2026-09-02", 100.5, 101.0, 95.0, 96.5)] + LATER[1:]   # stopped on day 1
    frames = {}
    rec = record.empty()
    names = []
    for i in range(n_wins):
        frames[f"W{i}"] = frame(rows); names.append(f"W{i}")
    for i in range(n_losses):
        frames[f"L{i}"] = frame(losing); names.append(f"L{i}")
    # SPY moves every day, so the pairing (entry-day open to exit-day close)
    # is the only reading that gives the number the test computes by hand
    frames["SPY"] = frame([(d, 500.0 + 3 * i, 503.0 + 3 * i, 499.0 + 3 * i, 501.0 + 3 * i) for i, (d, *_) in enumerate(rows)])
    rec = record.append(rec, "2026-09-01", [pick(ticker=t) for t in names])
    return record.scorecard(rec, frames, "2026-09-09")


def test_the_scorecard_counts_plans_fills_wins_and_losses_and_sums_r(monkeypatch):
    sc = _scored(3, 2, monkeypatch, min_read=5)
    assert (sc["plans"], sc["filled"], sc["settled"], sc["wins"], sc["losses"]) == (5, 5, 5, 3, 2)
    assert sc["readable"] is True and sc["win_rate"] == 0.6
    # a win: filled 100.5, half at 108.54 (+8%) on day 4, out 112 on day 5 -> R over a 4.5 stop
    win_r = record.r_multiple(record.replay(pick(), record.later_bars(frame([PICK_DAY] + LATER), "2026-09-01")), 96.0)
    assert win_r > 0
    assert sc["sum_r"] == round(3 * win_r + 2 * -1.0, 2)
    assert sc["avg_r"] == round(sc["sum_r"] / 5, 2)
    # a win exits on day 5 (9 Sep: SPY 516 close), a loss on day 1 (2 Sep: 504 close); both enter at the 2 Sep open, 503
    win_spy, loss_spy = 100 * (516.0 / 503.0 - 1), 100 * (504.0 / 503.0 - 1)
    assert sc["spy_avg_pct"] == round((3 * win_spy + 2 * loss_spy) / 5, 2)
    assert sc["min_read"] == 5 and sc["note"] == record.SCORECARD_NOTE


def test_below_the_read_threshold_the_counts_stand_and_the_rates_are_null(monkeypatch):
    sc = _scored(3, 2, monkeypatch, min_read=20)
    assert sc["plans"] == 5 and sc["wins"] == 3 and sc["sum_r"] is not None
    assert sc["readable"] is False
    assert sc["win_rate"] is None and sc["avg_r"] is None and sc["spy_avg_pct"] is None


def test_the_read_threshold_is_a_boundary(monkeypatch):
    assert _scored(3, 2, monkeypatch, min_read=5)["readable"] is True
    assert _scored(3, 2, monkeypatch, min_read=6)["readable"] is False


def test_an_unfilled_ticket_counts_as_a_plan_but_not_a_fill_and_an_open_walk_is_not_settled():
    frames = calendar_frames()
    frames["GAP"] = frame([PICK_DAY, ("2026-09-02", 103.0, 105.0, 102.5, 104.0)] + LATER[1:])
    frames["OPEN"] = frame([PICK_DAY] + LATER[:2])       # two sessions in: still held
    rec = record.append(record.empty(), "2026-09-01", [pick(ticker="GAP"), pick(ticker="OPEN")])
    sc = record.scorecard(rec, frames, "2026-09-09")
    assert sc["plans"] == 2 and sc["filled"] == 1 and sc["settled"] == 0 and sc["open"] == 1


def test_a_flat_exit_is_settled_but_neither_a_win_nor_a_loss():
    """Day 3 closes exactly at the fill: the no-progress exit at R = 0."""
    flat = [PICK_DAY, ("2026-09-02", 100.5, 102.0, 100.0, 101.0), ("2026-09-03", 101.0, 102.0, 100.2, 101.5),
            ("2026-09-04", 101.0, 102.0, 100.2, 100.5)] + LATER[3:]
    frames = calendar_frames()
    frames["FLAT"] = frame(flat)
    row = record.replay(pick(ticker="FLAT"), record.later_bars(frames["FLAT"], "2026-09-01"))
    assert row["status"] == "exit" and row["exit_price"] == 100.5 and row["entry_ref"] == 100.5
    assert record.r_multiple(row, 96.0) == 0.0
    sc = record.scorecard(record.append(record.empty(), "2026-09-01", [pick(ticker="FLAT")]), frames, "2026-09-09")
    assert (sc["settled"], sc["wins"], sc["losses"]) == (1, 0, 0)


def test_the_scorecard_window_can_fail(monkeypatch):
    monkeypatch.setattr(record, "SCORECARD_SESSIONS", 3)
    frames = calendar_frames()
    frames["OLD"] = frame([PICK_DAY] + LATER)
    rec = record.append(record.empty(), "2026-09-01", [pick(ticker="OLD")])
    assert record.scorecard(rec, frames, "2026-09-09")["plans"] == 0
    monkeypatch.setattr(record, "SCORECARD_SESSIONS", 5)
    assert record.scorecard(rec, frames, "2026-09-09")["plans"] == 1


def test_spy_is_read_over_the_same_days_as_the_pick():
    frames = calendar_frames()
    spy = frames["SPY"]
    # entry day 2 Sep open 501, exit day 9 Sep close 506 -> +0.998%
    assert round(record._spy_move(spy, "2026-09-02", "2026-09-09"), 3) == round(100 * (506.0 / 501.0 - 1), 3)
    assert record._spy_move(spy, "2026-09-02", "2026-12-25") is None
    assert record._spy_move(None, "2026-09-02", "2026-09-09") is None


# ------------------------------------------------------------ nights ------
def test_nights_keeps_the_newest_by_session_and_replaces_a_rerun(monkeypatch):
    monkeypatch.setattr(record, "NIGHTS_KEPT", 3)
    rows = record.nights(None, {"session": "2026-09-01", "status": "ok", "published_at": "a"})
    rows = record.nights(rows, {"session": "2026-09-02", "status": "degraded"})
    rows = record.nights(rows, {"session": "2026-09-01", "status": "closed"})
    rows = record.nights(rows, {"session": "2026-09-03", "status": "ok"})
    rows = record.nights(rows, {"session": "2026-09-04", "status": "ok"})
    assert [(r["session"], r["status"]) for r in rows] == [("2026-09-02", "degraded"), ("2026-09-03", "ok"), ("2026-09-04", "ok")]


def test_nights_drops_a_malformed_earlier_entry_and_refuses_an_undated_one():
    rows = record.nights(["junk", {"session": "x"}, {"session": "2026-09-01", "status": 3}, {"session": "2026-09-02", "status": "ok"}],
                         {"session": "2026-09-03", "status": "ok"})
    assert [r["session"] for r in rows] == ["2026-09-02", "2026-09-03"]
    with pytest.raises(ValueError):
        record.nights(rows, {"status": "ok"})


# ------------------------------------------------------------- rules ------
def test_every_upper_case_number_in_the_module_is_archived_in_rules():
    import ast, inspect
    tree = ast.parse(inspect.getsource(record))
    numbers = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id.isupper():
            value = node.value
            if isinstance(value, ast.Constant) and isinstance(value.value, (int, float)) and not isinstance(value.value, bool):
                numbers[node.targets[0].id] = value.value
            elif isinstance(value, ast.Attribute) and isinstance(getattr(record, node.targets[0].id), (int, float)):
                numbers[node.targets[0].id] = getattr(record, node.targets[0].id)
    archived = set(record.RULES.values())
    unarchived = {k: v for k, v in numbers.items() if v not in archived and k not in ("SCHEMA_VERSION",)}
    assert not unarchived, unarchived
