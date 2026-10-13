"""The minute bars a run reads for a first day the daily bar cannot place.

Every case is hand-sized: a burst ticket with trigger 100, limit 102, skip
line 99 and stop 96 (``test_record.pick()``), signalled on Tuesday 1
September 2026, so its entry session is Wednesday 2 September, 09:30 to 16:00
ET (13:30 to 20:00 UTC). A minute row is ``(offset, o, h, l, c)`` from the
open; offsets 0..29 are the plan's entry window.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest

from src import intraday, plan, record, report
from src import sessions as exchange_sessions

OPEN = datetime(2026, 9, 2, 13, 30, tzinfo=timezone.utc)
FETCHED = datetime(2026, 9, 2, 22, 30, tzinfo=timezone.utc)


def pick(**over) -> dict:
    base = {"ticker": "AAA", "date": "2026-09-01", "kind": "burst", "grade": "A", "score": 8.2,
            "entry_ref": 100.0, "entry_low": 99.0, "entry_high": 102.0, "stop": 96.0, "shares": 10,
            "targets": {"low": 108.0, "high": 120.0}}
    base.update(over)
    return base


def obj(rows, p=None) -> dict:
    """An evidence object built the way a fetch builds one."""
    return intraday.build(p or pick(), [(OPEN + timedelta(minutes=m), o, h, low, c) for m, o, h, low, c in rows],
                          FETCHED)


def day(o, h, low, c) -> dict:
    return {"date": "2026-09-02", "o": o, "h": h, "l": low, "c": c}


LEVELS = {"trigger": 100.0, "limit": 102.0, "skip": 99.0, "stop": 96.0}


# --------------------------------------------------------------- resolve ----
def test_a_crossing_inside_the_window_fills_at_the_trigger_and_rebuilds_the_entry_day():
    rows = [(0, 99.0, 99.4, 97.5, 99.2),        # the session's low, before any fill
            (5, 99.2, 99.8, 99.1, 99.7),
            (12, 99.7, 100.3, 99.6, 100.2),     # the crossing: opened under, reached 100
            (40, 100.2, 101.5, 99.9, 101.0),
            (300, 101.0, 101.2, 98.8, 99.0)]    # an afternoon low under the fill
    got = intraday.resolve(LEVELS, obj(rows), day(99.0, 101.5, 97.5, 99.4))
    status, price, note, why, entry = got
    assert status == intraday.FILLED and price == 100.0 and why is None
    assert "09:42 ET" in note and "at the trigger" in note and "(minute bars)" in note
    # from the fill on: the 12-minute bar's own range and every later one, the close
    assert entry == {"date": "2026-09-02", "o": 100.0, "h": 101.5, "l": 98.8, "c": 99.4, "day_low": 97.5}


def test_a_crossing_minute_that_opened_over_the_trigger_fills_at_its_open():
    rows = [(0, 99.0, 99.5, 98.9, 99.4), (3, 100.6, 101.0, 100.4, 100.9)]   # a gap inside the minute bars
    status, price, note, why, entry = intraday.resolve(LEVELS, obj(rows), day(99.0, 101.0, 98.9, 100.8))
    assert status == intraday.FILLED and price == 100.6 and "at the minute's open" in note
    assert entry["o"] == 100.6 and entry["l"] == 100.4 and entry["day_low"] == 98.9


def test_a_crossing_minute_opening_over_the_limit_cannot_be_ordered():
    rows = [(0, 99.0, 99.5, 98.9, 99.4), (3, 102.5, 103.0, 101.5, 102.8)]
    status, price, note, why, entry = intraday.resolve(LEVELS, obj(rows), day(99.0, 103.0, 98.9, 102.8))
    assert status == intraday.UNCERTAIN and why == intraday.MINUTE_ORDER and price is None and entry is None
    assert "above the $102.00 limit" in note


def test_a_crossing_minute_opening_exactly_at_the_limit_fills_there():
    rows = [(0, 99.0, 99.5, 98.9, 99.4), (3, 102.0, 103.0, 101.5, 102.8)]
    status, price, *_ = intraday.resolve(LEVELS, obj(rows), day(99.0, 103.0, 98.9, 102.8))
    assert status == intraday.FILLED and price == 102.0


def test_a_crossing_minute_whose_low_reaches_the_stop_cannot_be_ordered():
    rows = [(0, 99.0, 99.5, 98.9, 99.4), (8, 99.4, 100.2, 96.0, 99.8)]      # low exactly at the stop
    status, price, note, why, entry = intraday.resolve(LEVELS, obj(rows), day(99.0, 100.2, 96.0, 99.8))
    assert status == intraday.UNCERTAIN and why == intraday.MINUTE_ORDER
    assert "at or under the $96.00 stop" in note
    above = [(0, 99.0, 99.5, 98.9, 99.4), (8, 99.4, 100.2, 96.01, 99.8)]    # a cent above it fills
    assert intraday.resolve(LEVELS, obj(above), day(99.0, 100.2, 96.01, 99.8))[0] == intraday.FILLED


def test_a_crossing_minute_that_opened_over_the_trigger_is_a_fill_before_any_stop_in_it():
    """It opened at 100.3: the fill is that minute's open, and its low at the
    stop came after the fill, so the walk reads it as the day-1 stop."""
    rows = [(0, 99.0, 99.5, 98.9, 99.4), (8, 100.3, 100.5, 95.5, 96.0)]
    status, price, _, _, entry = intraday.resolve(LEVELS, obj(rows), day(99.0, 100.5, 95.5, 96.0))
    assert status == intraday.FILLED and price == 100.3 and entry["l"] == 95.5
    row = record.replay(pick(), [day(99.0, 100.5, 95.5, 96.0)], minutes=obj(rows))
    assert row["status"] == "stopped" and row["exit_price"] == 96.0


@pytest.mark.parametrize("offset, status", [(plan.ENTRY_WINDOW_MINUTES - 1, intraday.FILLED),
                                            (plan.ENTRY_WINDOW_MINUTES, intraday.NOT_FILLED)])
def test_the_window_is_the_plans_first_minutes_and_not_one_more(offset, status):
    rows = [(0, 99.0, 99.5, 98.9, 99.4), (offset, 99.6, 100.1, 99.5, 100.0)]
    got = intraday.resolve(LEVELS, obj(rows), day(99.0, 100.1, 98.9, 100.0))
    assert got[0] == status


def test_a_day_that_reached_the_trigger_only_after_the_window_is_not_filled():
    rows = [(0, 99.0, 99.5, 98.9, 99.4), (20, 99.4, 99.8, 99.2, 99.6), (95, 99.6, 101.0, 99.5, 100.8)]
    status, price, note, why, entry = intraday.resolve(LEVELS, obj(rows), day(99.0, 101.0, 98.9, 100.8))
    assert status == intraday.NOT_FILLED and price is None and why is None and entry is None
    assert "its high in them $99.80" in note and "11:05 ET" in note and "after the plan cancels" in note


def test_a_window_with_no_trade_at_all_is_said_so():
    rows = [(45, 99.6, 101.0, 99.5, 100.8)]
    status, _, note, *_ = intraday.resolve(LEVELS, obj(rows), day(99.6, 101.0, 99.5, 100.8))
    assert status == intraday.NOT_FILLED and "no trade in them" in note


def test_minutes_that_never_reach_the_trigger_disagree_with_the_daily_bar_and_are_not_used():
    rows = [(0, 99.0, 99.5, 98.9, 99.4), (45, 99.4, 99.9, 99.3, 99.8)]
    assert intraday.resolve(LEVELS, obj(rows), day(99.0, 100.5, 98.9, 99.8)) is None


def test_another_sessions_minutes_or_none_are_not_used():
    rows = [(5, 99.6, 100.1, 99.5, 100.0)]
    assert intraday.resolve(LEVELS, obj(rows), {**day(99.0, 100.5, 98.9, 100.0), "date": "2026-09-03"}) is None
    assert intraday.resolve(LEVELS, None, day(99.0, 100.5, 98.9, 100.0)) is None


def test_an_anticipation_ticket_has_no_limit_check_when_it_carries_none():
    p = pick(kind="anticipation", trigger=100.0, limit=None, entry_low=None, entry_high=None)
    rows = [(0, 99.0, 99.5, 98.9, 99.4), (3, 105.0, 105.5, 104.0, 105.2)]
    got = intraday.resolve(record.ticket_levels(p), obj(rows, p), day(99.0, 105.5, 98.9, 105.2))
    assert got[0] == intraday.FILLED and got[1] == 105.0


# ------------------------------------------------------------ the replay ----
def test_replay_walks_a_minute_fill_and_names_the_object_it_came_from():
    """Daily: opened 99.0 under the 100 trigger and reached it -- uncertain on
    timing. Minutes: crossed at 09:42 inside the window. The walk then runs
    from the fill, and day 1's stop rises to the session's own low."""
    rows = [(0, 99.0, 99.4, 97.5, 99.2), (12, 99.7, 100.3, 99.6, 100.2), (40, 100.2, 101.5, 99.9, 101.0)]
    evidence = obj(rows)
    bars = [day(99.0, 101.5, 97.5, 101.2),
            {"date": "2026-09-03", "o": 101.3, "h": 103.0, "l": 100.8, "c": 102.5}]
    without = record.replay(pick(), bars)
    assert without["status"] == record.UNCERTAIN and without["uncertainty"] == "trigger_timing"
    assert "minute_evidence" not in without
    row = record.replay(pick(), bars, minutes=evidence)
    assert row["status"] not in (record.UNCERTAIN, record.NOT_FILLED) and row["entry_ref"] == 100.0
    assert row["minute_evidence"] == intraday.name_of(evidence)
    assert "filled at 09:42 ET" in row["fill"]
    raised = [e for e in row["events"] if e["event"] == "stop_raised_to_entry_low"]
    assert raised and raised[0]["price"] == 97.5     # the session's own low, not the post-fill 99.6


def test_replay_reads_a_stop_sequence_day_again_and_keeps_a_pre_fill_low_out_of_the_walk():
    """Daily: the low 95.5 sits under the 96 stop -- fill and stop in unknown
    order. Minutes: the low came at 09:31, before any fill; the crossing at
    09:50 kept above the stop after it, so the walk holds and the stop does
    not rise (the session's low is under it)."""
    rows = [(1, 99.2, 99.3, 95.5, 97.0), (20, 99.6, 100.4, 99.5, 100.3), (60, 100.3, 101.0, 99.8, 100.9)]
    bars = [day(99.2, 101.0, 95.5, 100.9)]
    assert record.fill(pick(), bars[0])[3] == "stop_sequence"
    row = record.replay(pick(), bars, minutes=obj(rows))
    assert row["status"] == "hold" and row["current_stop"] == 96.0
    assert not [e for e in row["events"] if e["event"] in ("stopped", "stop_raised_to_entry_low")]


def test_replay_leaves_a_reason_minutes_cannot_read_as_the_daily_bar_gave_it():
    rows = [(0, 103.0, 103.5, 101.5, 102.0)]
    bars = [day(103.0, 104.0, 101.5, 102.5)]
    row = record.replay(pick(), bars, minutes=obj(rows))
    assert row["status"] == record.UNCERTAIN and row["uncertainty"] == "open_above_limit"
    assert "minute_evidence" not in row


def test_replay_carries_a_minute_order_answer_as_uncertain():
    rows = [(0, 99.0, 99.5, 98.9, 99.4), (8, 99.4, 100.2, 95.0, 99.8)]
    row = record.replay(pick(), [day(99.0, 100.2, 95.0, 99.8)], minutes=obj(rows))
    assert row["status"] == record.UNCERTAIN and row["uncertainty"] == intraday.MINUTE_ORDER
    assert row["minute_evidence"] == intraday.name_of(obj(rows))
    assert intraday.MINUTE_ORDER in record.UNCERTAIN_REASONS
    assert record.UNCERTAIN_WORDS[intraday.MINUTE_ORDER] == intraday.MINUTE_ORDER_WORDS


def test_the_entry_days_own_low_cannot_sit_above_the_bars_low():
    with pytest.raises(ValueError, match="day_low"):
        plan.follow({**pick(), "entry_ref": 100.0}, [{**day(100.0, 101.0, 99.0, 100.5), "day_low": 99.5}], "green")


# ---------------------------------------------------------------- objects ----
def test_build_keeps_regular_hours_rounds_once_and_keeps_the_last_copy_of_a_minute():
    rows = [(OPEN - timedelta(minutes=5), 98.0, 98.0, 98.0, 98.0),          # pre-market
            (OPEN, 99.123456, 99.5, 98.9, 99.4),
            (OPEN, 99.2, 99.6, 98.95, 99.5),                                 # the same minute again
            (OPEN + timedelta(minutes=390), 99.0, 99.0, 99.0, 99.0)]         # after the close
    built = intraday.build(pick(), rows, FETCHED)
    assert built["minutes"] == [[0, 99.2, 99.6, 98.95, 99.5]]
    first = intraday.build(pick(), rows[1:2], FETCHED)
    assert first["minutes"] == [[0, 99.1235, 99.5, 98.9, 99.4]]
    assert built["session"] == "2026-09-02" and built["key"] == "burst:AAA:2026-09-01"
    assert built["opens_at"] == "2026-09-02T13:30:00+00:00" and built["closes_at"] == "2026-09-02T20:00:00+00:00"


def test_an_early_close_bounds_the_session_by_its_own_hours():
    p = pick(date="2026-11-25")                    # entry Friday 27 November, closing at 13:00 ET
    opens, closes, _ = exchange_sessions.hours(date(2026, 11, 27))
    built = intraday.build(p, [(closes - timedelta(minutes=1), 50.0, 50.0, 50.0, 50.0),
                               (closes, 51.0, 51.0, 51.0, 51.0)], FETCHED)
    assert [m[0] for m in built["minutes"]] == [209]


@pytest.mark.parametrize("change, words", [
    (lambda o: o.update(version=2), "not an intraday object"),
    (lambda o: o.update(extra=1), "keys"),
    (lambda o: o.update(basis={**o["basis"], "feed": "iex"}), "basis"),
    (lambda o: o.update(session="2026-09-03"), "not the session after"),
    (lambda o: o.update(key="burst:BBB:2026-09-01"), "not this ticker"),
    (lambda o: o.update(opens_at="2026-09-02T13:31:00+00:00"), "hours"),
    (lambda o: o.update(fetched_at="yesterday"), "fetch time"),
    (lambda o: o.update(minutes=[[0, 99.0, 99.5, 98.9, 99.4]] * 2), "out of order"),
    (lambda o: o.update(minutes=[[390, 99.0, 99.5, 98.9, 99.4]]), "outside the session"),
    (lambda o: o.update(minutes=[[True, 99.0, 99.5, 98.9, 99.4]]), r"is not \[offset"),
    (lambda o: o.update(minutes=[[0, float("nan"), 99.5, 98.9, 99.4]]), r"is not \[offset"),
    (lambda o: o.update(minutes=[[0, 99.0, 99.5, 98.9]]), r"is not \[offset"),
    (lambda o: o.update(minutes=[[0, 99.6, 99.5, 98.9, 99.4]]), "inside its range"),
    (lambda o: o.update(minutes=[[i, 1.0, 1.0, 1.0, 1.0] for i in range(intraday.MAX_MINUTES + 1)]), "bounded"),
])
def test_an_object_that_is_not_whole_is_refused_by_name(change, words):
    o = json.loads(json.dumps(obj([(5, 99.6, 100.1, 99.5, 100.0)])))
    change(o)
    with pytest.raises(intraday.IntradayError, match=words):
        intraday.validate(o)


# ---------------------------------------------------------------- archive ----
def test_store_writes_once_reads_back_and_load_returns_it_by_key(tmp_path):
    o = obj([(5, 99.6, 100.1, 99.5, 100.0)])
    stored, problems = intraday.store(tmp_path, [o])
    assert stored == [o["key"]] and problems == []
    path = tmp_path / intraday.DIR_NAME / intraday.name_of(o)
    assert path.read_bytes() == intraday.canonical(o)
    again, problems = intraday.store(tmp_path, [o])                # the same object: already there
    assert again == [o["key"]] and problems == [] and len(list(path.parent.glob("*.json"))) == 1
    evidence, problems = intraday.load_archive(tmp_path)
    assert evidence == {o["key"]: o} and problems == []


def test_a_file_whose_bytes_are_not_its_name_is_named_and_not_used(tmp_path):
    o = obj([(5, 99.6, 100.1, 99.5, 100.0)])
    intraday.store(tmp_path, [o])
    path = tmp_path / intraday.DIR_NAME / intraday.name_of(o)
    path.write_bytes(intraday.canonical({**o, "minutes": [[5, 99.6, 100.2, 99.5, 100.0]]}))
    evidence, problems = intraday.load_archive(tmp_path)
    assert evidence == {} and "bytes are not the object its name gives" in problems[0]
    stored, problems = intraday.store(tmp_path, [o])
    assert stored == [] and "a different file holds this object's name" in problems[0]
    (tmp_path / intraday.DIR_NAME / "junk.json").write_text("{")
    assert len(intraday.load_archive(tmp_path)[1]) == 2


def test_two_objects_claiming_one_pick_are_both_set_aside(tmp_path):
    a = obj([(5, 99.6, 100.1, 99.5, 100.0)])
    b = obj([(6, 99.6, 100.1, 99.5, 100.0)])
    intraday.store(tmp_path, [a, b])
    evidence, problems = intraday.load_archive(tmp_path)
    assert evidence == {} and problems == [f"{a['key']}: 2 objects claim it; none is used"]


def test_the_archive_refuses_past_its_bounds_and_names_it(tmp_path, monkeypatch):
    a = obj([(5, 99.6, 100.1, 99.5, 100.0)])
    b = obj([(5, 99.6, 100.1, 99.5, 100.0)], pick(ticker="BBB"))
    monkeypatch.setattr(intraday, "ARCHIVE_MAX_OBJECTS", 1)
    stored, problems = intraday.store(tmp_path, [a, b])
    assert stored == [a["key"]] and "at capacity (1 objects" in problems[0]
    monkeypatch.setattr(intraday, "ARCHIVE_MAX_OBJECTS", 10)
    monkeypatch.setattr(intraday, "OBJECT_MAX_BYTES", 10)
    stored, problems = intraday.store(tmp_path, [b])
    assert stored == [] and "object bound" in problems[0]


# ------------------------------------------------------------------ fetch ----
def minute_frame(rows, start=OPEN) -> pd.DataFrame:
    idx = pd.DatetimeIndex([start + timedelta(minutes=m) for m, *_ in rows], name="timestamp")
    return pd.DataFrame([{"Open": o, "High": h, "Low": low, "Close": c, "Volume": 1000}
                         for _, o, h, low, c in rows], index=idx)


def test_fetch_asks_once_per_entry_session_for_the_sip_split_minutes_of_regular_hours(fake_alpaca):
    from src import market_data
    fake_alpaca.add_minutes("AAA", minute_frame([(5, 99.6, 100.1, 99.5, 100.0)]))
    fake_alpaca.add_minutes("BBB", minute_frame([(0, 50.0, 50.0, 50.0, 50.0)], start=OPEN - timedelta(hours=1)))
    picks = [pick(), pick(ticker="BBB"), pick(ticker="CCC")]
    objects, failures = intraday.fetch(market_data.get_clients(), picks, FETCHED)
    assert len(fake_alpaca.minute_requests) == 1
    fields = fake_alpaca.request_fields[-1]
    req = fake_alpaca.minute_requests[0]
    assert str(fields["timeframe"]) == "1Min"
    assert req.feed == market_data.DataFeed.SIP and req.adjustment == market_data.BAR_ADJUSTMENT
    assert req.symbol_or_symbols == ["AAA", "BBB", "CCC"]
    # the SDK sends UTC without its zone
    assert req.start == datetime(2026, 9, 2, 13, 30) and req.end == datetime(2026, 9, 2, 19, 59, 59)
    assert [o["key"] for o in objects] == ["burst:AAA:2026-09-01"]
    assert failures == [{"key": "burst:BBB:2026-09-01", "kind": "no_minutes"},     # only pre-market rows
                        {"key": "burst:CCC:2026-09-01", "kind": "no_minutes"}]


def test_a_refused_minute_request_is_named_by_its_kind_and_never_its_text(fake_alpaca):
    from src import market_data
    fake_alpaca.raise_on_minutes = RuntimeError("secret-looking text")
    objects, failures = intraday.fetch(market_data.get_clients(), [pick()], FETCHED)
    assert objects == [] and failures == [{"key": "burst:AAA:2026-09-01", "kind": "RuntimeError"}]


# ----------------------------------------------------------------- gather ----
def test_gather_asks_only_for_complete_sessions_newest_first_within_its_bound(tmp_path, monkeypatch):
    asked = []

    def fetcher(client, picks, now):
        asked.extend(p["ticker"] for p in picks)
        return [obj([(5, 99.6, 100.1, 99.5, 100.0)], p) for p in picks], []
    monkeypatch.setattr(intraday, "MAX_PICKS_PER_RUN", 2)
    picks = [pick(ticker="OLD", date="2026-08-28"), pick(ticker="MID"), pick(ticker="NEW", date="2026-09-01"),
             pick(ticker="WAIT", date="2026-09-02")]
    # 16:16 ET on 2 September: its session is 1 minute past the hold-back; 3 September's is not done
    now = datetime(2026, 9, 2, 20, 16, tzinfo=timezone.utc)
    evidence, block = intraday.gather(object(), tmp_path, picks, now=now, write=True, fetcher=fetcher)
    assert asked == ["NEW", "MID"]
    assert block["wanted"] == 4 and block["asked"] == 2 and block["waiting"] == 1 and block["beyond_cap"] == 1
    assert block["fetched"] == 2 and block["stored"] == 2 and block["retained"] == 2
    assert intraday.faults(block) == []
    # the next night reads them from the archive and asks only for the rest
    asked.clear()
    later = datetime(2026, 9, 3, 23, 0, tzinfo=timezone.utc)
    evidence, block = intraday.gather(object(), tmp_path, picks, now=later, write=True, fetcher=fetcher)
    assert sorted(asked) == ["OLD", "WAIT"] and block["wanted"] == 2 and block["retained"] == 4


def test_the_hold_back_is_the_feeds_and_a_minute_short_of_it_waits():
    close = datetime(2026, 9, 2, 20, 0, tzinfo=timezone.utc)
    assert intraday.complete(date(2026, 9, 2), close + timedelta(minutes=intraday.HOLDBACK_MINUTES))
    assert not intraday.complete(date(2026, 9, 2), close + timedelta(minutes=intraday.HOLDBACK_MINUTES, seconds=-1))


def test_a_dry_run_reads_what_it_fetched_and_writes_nothing(tmp_path):
    def fetcher(client, picks, now):
        return [obj([(5, 99.6, 100.1, 99.5, 100.0)], p) for p in picks], []
    evidence, block = intraday.gather(object(), tmp_path, [pick()], now=FETCHED, write=False, fetcher=fetcher)
    assert list(evidence) == ["burst:AAA:2026-09-01"] and block["stored"] == 0 and block["fetched"] == 1
    assert not (tmp_path / intraday.DIR_NAME).exists()


def test_no_client_spends_nothing_and_says_so(tmp_path):
    evidence, block = intraday.gather(None, tmp_path, [pick()], now=FETCHED, write=True)
    assert evidence == {} and block["failures"] == [{"key": "burst:AAA:2026-09-01", "kind": "no_client"}]
    assert "1 not fetched (no_client)" in block["sentence"] and intraday.faults(block) == []


def test_a_night_with_nothing_to_read_says_how_much_is_retained(tmp_path):
    evidence, block = intraday.gather(None, tmp_path, [], now=FETCHED, write=True)
    assert block["sentence"] == ("No plan's first day needed its minute bars tonight; minute bars are retained "
                                 "for 0 plans' first days.")


# ----------------------------------------------------------------- faults ----
def good_block() -> dict:
    return intraday.block(wanted=3, asked=2, fetched=1, stored=1, retained=4, waiting=1, beyond_cap=0,
                          failures=[{"key": "burst:AAA:2026-09-01", "kind": "no_minutes"}], problems=[])


@pytest.mark.parametrize("change, words", [
    (lambda b: b.update(asked=-1), "not a count"),
    (lambda b: b.update(stored=True), "not a count"),
    (lambda b: b.update(policy="other"), "not this version"),
    (lambda b: b.update(asked=intraday.MAX_PICKS_PER_RUN + 1, wanted=99), "its bound"),
    (lambda b: b.update(asked=4), "its bound or its wants"),
    (lambda b: b.update(fetched=2), "do not add up"),
    (lambda b: b.update(stored=2), "stored more"),
    (lambda b: b.update(failures=[{"key": 1, "kind": "x"}]), "pairs"),
    (lambda b: b.update(problems=[3]), "sentences"),
    (lambda b: b.update(failures="none"), "must be lists"),
    (lambda b: b.update(sentence="All fine."), "not its own"),
])
def test_a_block_that_does_not_add_up_is_named(change, words):
    b = good_block()
    assert intraday.faults(b) == []
    change(b)
    assert any(words in f for f in intraday.faults(b)), intraday.faults(b)


def test_a_record_is_asked_for_the_block_only_under_rules_that_write_it():
    b = good_block()
    assert intraday.record_faults({"rules": {}, "run": {}}) == []
    rules = {"intraday": {"version": intraday.VERSION}}
    assert intraday.record_faults({"rules": rules, "run": {"intraday": b}}) == []
    assert intraday.record_faults({"rules": rules, "run": {}}) == ["run.intraday is missing under rules that read minute bars"]
    assert "not one this code reads" in intraday.record_faults({"rules": {"intraday": {"version": 9}}, "run": {}})[0]
    assert intraday.record_faults({"rules": rules, "run": {"intraday": {**b, "fetched": 5}}})


# ------------------------------------------------------------ needs_minutes ----
def frames_for(rows) -> dict:
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d, *_ in rows])
    df = pd.DataFrame([{"Open": o, "High": h, "Low": low, "Close": c, "Volume": 1_000_000}
                       for _, o, h, low, c in rows], index=idx)
    return {"AAA": df}


def test_needs_minutes_names_the_first_days_a_daily_bar_left_uncertain_on_a_readable_reason():
    sig = ("2026-09-01", 95.0, 101.0, 94.0, 100.0)
    rec = {"picks": [pick()]}
    timing = frames_for([sig, ("2026-09-02", 99.0, 101.0, 98.0, 100.5)])
    assert record.needs_minutes(rec, timing, "2026-09-02") == [pick()]
    stop_seq = frames_for([sig, ("2026-09-02", 99.0, 101.0, 95.5, 100.5)])
    assert record.needs_minutes(rec, stop_seq, "2026-09-02") == [pick()]
    for other in (("2026-09-02", 100.5, 101.0, 100.0, 100.8),     # a fill at the open
                  ("2026-09-02", 103.0, 104.0, 101.5, 102.5),     # open above the limit: not readable
                  ("2026-09-02", 98.5, 100.5, 98.0, 100.2)):      # under the skip line: not readable
        assert record.needs_minutes(rec, frames_for([sig, other]), "2026-09-02") == []
    # the name printed nothing on its entry session: the first bar is a later one
    assert record.needs_minutes(rec, frames_for([sig, ("2026-09-03", 99.0, 101.0, 98.0, 100.5)]), "2026-09-03") == []


# ----------------------------------------------------------- the evening ----
# The pipeline's own two-night market (tests/test_pipeline.py): AAA's ticket of
# Thursday 10 September (trigger 124.21, stop 123.92) meets a Friday bar that
# opens 123.95, reaches 124.23 and lows at 123.92 -- the stop: the daily bar
# cannot order fill and stop (stop_sequence). Its minutes say the low came at
# the open and the crossing at 09:40, after which the day held.
from tests.test_pipeline import claude, evening, market  # noqa: E402,F401  (fixtures)

FRIDAY = datetime(2026, 9, 11, 22, 30, tzinfo=timezone.utc)
MONDAY = datetime(2026, 9, 14, 22, 30, tzinfo=timezone.utc)
AAA_MINUTES = [(0, 123.95, 124.00, 123.92, 123.98), (10, 124.00, 124.22, 123.99, 124.20),
               (60, 124.20, 124.23, 124.10, 124.15)]


def friday_minutes() -> pd.DataFrame:
    return minute_frame(AAA_MINUTES, start=datetime(2026, 9, 11, 13, 30, tzinfo=timezone.utc))


def test_the_evening_reads_a_stop_sequence_day_from_its_minutes_and_retains_them(market, claude, fake_resend,
                                                                                  fake_alpaca, tmp_path):
    evening(tmp_path, market)
    fake_alpaca.add_minutes("AAA", friday_minutes())
    rep, data, docs = evening(tmp_path, market, now=FRIDAY)
    assert rep.exit_code() == 0, rep.problems
    aaa = next(p for p in data["open_plans"] if p["ticker"] == "AAA")
    assert aaa["status"] == "hold" and aaa["entry_ref"] == 124.21 and "filled at 09:40 ET" in aaa["fill"]
    block = data["run"]["intraday"]
    assert (block["wanted"], block["asked"], block["fetched"], block["stored"], block["retained"]) == (1, 1, 1, 1, 1)
    assert block["failures"] == [] and intraday.faults(block) == []
    files = list((docs / intraday.DIR_NAME).glob("*.json"))
    assert [f.name for f in files] == [aaa["minute_evidence"]]
    assert data["scorecard"]["uncertain"] == 0 and data["scorecard"]["open"] >= 1
    # the quality ledger re-derives the scorecard with the same minutes and agrees
    assert rep.quality_ledger["status"] == "retained"
    report.validate(data)                          # raises on a fault
    # Monday reads them from the archive: no new minute request, the same answer.
    # The double re-dates a frame to end on the night asked, so Monday gets one
    # more bar and Friday keeps the bar it had.
    frame = fake_alpaca.history["AAA"]
    monday = frame.iloc[-1:].copy()
    monday[["Open", "High", "Low", "Close"]] = 124.3
    fake_alpaca.add_history("AAA", pd.concat([frame, monday]))
    asked = len(fake_alpaca.minute_requests)
    rep, data, docs = evening(tmp_path, market, now=MONDAY)
    assert rep.exit_code() == 0, rep.problems
    assert len(fake_alpaca.minute_requests) == asked
    aaa = next(p for p in data["open_plans"] if p["ticker"] == "AAA")
    assert aaa["minute_evidence"] == files[0].name and aaa["entry_ref"] == 124.21
    assert data["run"]["intraday"]["wanted"] == 0 and data["run"]["intraday"]["retained"] == 1


def test_an_evening_without_the_minutes_leaves_the_plan_uncertain_and_publishes(market, claude, fake_resend,
                                                                                fake_alpaca, tmp_path):
    evening(tmp_path, market)
    rep, data, docs = evening(tmp_path, market, now=FRIDAY)
    assert rep.exit_code() == 0, rep.problems
    aaa = next(p for p in data["open_plans"] if p["ticker"] == "AAA")
    assert aaa["status"] == record.UNCERTAIN and aaa["uncertainty"] == "stop_sequence"
    assert data["run"]["intraday"]["failures"] == [{"key": "burst:AAA:2026-09-10", "kind": "no_minutes"}]
    assert not (docs / intraday.DIR_NAME).exists() and rep.quality_ledger["status"] == "retained"


def test_a_minute_request_that_fails_never_fails_the_evening(market, claude, fake_resend, fake_alpaca, tmp_path):
    evening(tmp_path, market)
    fake_alpaca.raise_on_minutes = ConnectionError("refused")
    rep, data, _ = evening(tmp_path, market, now=FRIDAY)
    assert rep.exit_code() == 0 and data["run"]["status"] == "ok"
    assert data["run"]["intraday"]["failures"] == [{"key": "burst:AAA:2026-09-10", "kind": "ConnectionError"}]


def test_a_dry_run_reads_the_minutes_and_writes_none(market, claude, fake_resend, fake_alpaca, tmp_path):
    evening(tmp_path, market)
    fake_alpaca.add_minutes("AAA", friday_minutes())
    rep, data, docs = evening(tmp_path, market, now=FRIDAY, dry_run=True)
    aaa = next(p for p in data["open_plans"] if p["ticker"] == "AAA")
    assert aaa["status"] == "hold" and data["run"]["intraday"]["stored"] == 0
    assert not (docs / intraday.DIR_NAME).exists()


def test_the_rules_archive_the_minute_policy_and_a_record_without_the_block_is_refused(market, claude,
                                                                                    fake_resend, tmp_path):
    rep, data, _ = evening(tmp_path, market)
    assert data["rules"]["intraday"]["policy"] == intraday.POLICY
    assert data["rules"]["record"]["intraday_fill"] == intraday.POLICY
    assert data["rules"]["intraday"]["window_minutes"] == plan.ENTRY_WINDOW_MINUTES
    report.validate(data)
    del data["run"]["intraday"]
    with pytest.raises(ValueError, match="run.intraday is missing under rules that read minute bars"):
        report.validate(data)
