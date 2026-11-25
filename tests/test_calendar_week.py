"""Mondays, Thanksgiving, the Friday half day and the two clock changes, in one place.

Each clock-bearing part of the service has its own tests. This file walks the
days that go wrong in practice through all of them at once, with every clock
pinned:

* **Thanksgiving week 2026**, driven through ``pipeline.run_evening()`` itself
  (the doubles and the synthetic market of ``tools/recovery_rehearsal.py``):
  Tuesday 24 November, Wednesday 25 November (whose plans are for Friday),
  Thursday 26 November (XNYS closed), Friday 27 November (1:00 PM ET close) and
  Monday 30 November. Each night's record, handoff, guard decisions, watch
  answers, dispatcher slots and gate ledger are read as the service would read
  them on that day.
* **The clock changes** of Sunday 1 November 2026 and Sunday 14 March 2027, at
  each function that turns a wall-clock rule into an instant.

Nothing here reads the real clock: the test's answer on any day is the same.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import pytest

from src import (charts, delivery, earnings_risk, freshness, go_live, market_data, orders, pipeline, plan, sessions,
                 timing)
from tests.fakes import FakeAlpaca, FakeAnthropic, FakeDataClient, FakeResend, FakeSec
from tools import dispatch_schedule as ds
from tools import publish_morning as pm
from tools import recovery_rehearsal as rr
from tools import service_watch as sw

UTC = timezone.utc
TUESDAY, WEDNESDAY, THANKSGIVING, FRIDAY, MONDAY = (date(2026, 11, d) for d in (24, 25, 26, 27, 30))
SATURDAY, SUNDAY = date(2026, 11, 28), date(2026, 11, 29)
#: the two evening crons in force in standard time, and the two that are not (evening.yml)
PRIMARY_EST, RETRY_EST = "16 23 * * 1-5", "16 1 * * 2-6"
PRIMARY_EDT, RETRY_EDT = "16 22 * * 1-5", "16 0 * * 2-6"
#: the two morning crons in force in standard time (morning.yml), and one that is not
MORNING_EST, MORNING_EDT = "20 14 * * 1-5", "20 13 * * 1-5"
RUN_ID = "900000001"


def at(text: str) -> datetime:
    out = datetime.fromisoformat(text)
    assert out.tzinfo is not None, text
    return out


def evening_at(day: date) -> str:
    """6:20 PM New York on ``day``, as a UTC instant: four minutes after the primary slot."""
    return datetime.combine(day, datetime.min.time().replace(hour=18, minute=20),
                            tzinfo=sessions.MARKET_TZ).astimezone(UTC).isoformat()


class Week:
    """The docs directory as each evening of the week left it, and what each run did."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.states: dict[str, Path] = {}
        self.reports: dict[str, object] = {}
        self.calls: dict[str, dict] = {}

    def docs(self, name: str) -> Path:
        return self.states[name] / "docs"

    def raw(self, name: str) -> bytes:
        return (self.docs(name) / "data.json").read_bytes()

    def record(self, name: str) -> dict:
        return json.loads(self.raw(name))

    def orders(self, name: str) -> dict:
        return json.loads((self.docs(name) / "orders.json").read_bytes())


def receipt_for(raw: bytes, generated: str, status: str = "no_tickets") -> dict:
    """The fields of a morning receipt the gate and the watch read, bound to ``raw``."""
    record = json.loads(raw)
    return {"publication": {"data_sha256": hashlib.sha256(raw).hexdigest(),
                            "measured_session": record["run"]["session"],
                            "applicable_session": record["run"]["timing"]["applicable_session"]},
            "generated_at": generated, "status": status, "dry_run": False, "rows": []}


@pytest.fixture(scope="module")
def week(tmp_path_factory) -> Week:
    """Tuesday to the Monday after, one evening after another over one docs directory."""
    import anthropic
    import resend as resend_module

    base = tmp_path_factory.mktemp("thanksgiving-week")
    live, out = base / "live", Week(base)
    docs = live / "docs"
    frames = rr.market()
    fake = FakeAlpaca()
    claude = type("WeekAnthropic", (FakeAnthropic,),
                  {"calls": [], "payload": dict(rr.READER_REPLY), "raw": None, "raises": None})
    resend = FakeResend()

    def render(ticker, df, out_dir, **kw):
        target = Path(out_dir) / f"{ticker}.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(rr.PNG_1X1)
        return str(target)

    def keep(name: str) -> None:
        shutil.copytree(live, base / name)
        out.states[name] = base / name

    def counts() -> dict:
        return {"bars": len(fake.bar_requests), "reader": len(claude.calls), "mail": len(resend.sent)}

    def night(name: str, day: date) -> None:
        for ticker, df in frames.items():
            fake.add_history(ticker, df)
        before = counts()
        out.reports[name] = pipeline.run_evening(
            tickers=[n for n in frames if n != pipeline.BENCHMARK_SYMBOL], docs=docs, now=at(evening_at(day)))
        out.calls[name] = {k: counts()[k] - before[k] for k in before}
        keep(name)

    def morning(name: str, generated: str) -> None:
        receipt_raw = json.dumps(receipt_for((docs / "data.json").read_bytes(), generated)).encode()
        (docs / "morning.json").write_bytes(receipt_raw)
        # and the morning run's own go/cancel file, as its persist job writes it after the receipt
        orders_raw = (docs / "orders.json").read_bytes()
        (docs / "orders-morning.json").write_bytes(orders.encode(orders.build_morning(orders_raw, receipt_raw)))
        keep(name)

    env = dict(rr.ENV, SCAN_TRIGGER_EVENT="schedule", GITHUB_RUN_ID_FOR_RECORD=RUN_ID)
    with mock.patch.dict(os.environ, env):
        for name in rr.UNSET:
            if name != "GITHUB_RUN_ID_FOR_RECORD":
                os.environ.pop(name, None)
        with mock.patch.object(market_data, "StockHistoricalDataClient", lambda *a, **k: FakeDataClient(fake, *a, **k)), \
                mock.patch.object(anthropic, "Anthropic", claude), \
                mock.patch.object(resend_module.Emails, "send", lambda params, options=None: resend.send(params)), \
                mock.patch.object(resend_module, "api_key", None, create=True), \
                mock.patch.object(charts, "render_chart", render), \
                mock.patch.object(earnings_risk, "FETCH", FakeSec()), \
                mock.patch.object(pipeline.grader, "MODEL", env["CLAUDE_MODEL"]):
            night("tuesday", TUESDAY)
            morning("wednesday-morning", "2026-11-25T14:22:00+00:00")     # 8:22 AM Chicago, for Tuesday's record
            night("wednesday", WEDNESDAY)
            night("thanksgiving", THANKSGIVING)                           # nothing to run
            morning("friday-morning", "2026-11-27T14:22:00+00:00")        # 8:22 AM Chicago, for Wednesday's record
            night("friday", FRIDAY)
            morning("monday-morning", "2026-11-30T14:22:00+00:00")        # 8:22 AM Chicago, for Friday's record
            night("monday", MONDAY)
    return out


@pytest.fixture(scope="module")
def guard_code() -> str:
    return rr.guard_source()


def evening_guard(week: Week, name: str, clock: str, cron: str, code: str) -> dict:
    return rr.guard(week.states[name], clock, cron, code)


def watch(week: Week, name: str, clock: str) -> dict:
    return sw.watch(week.docs(name), at(clock))


# ------------------------------------------------------- the calendar itself ---
def test_the_week_as_the_exchange_calendar_has_it():
    assert [d.isoformat() for d in sessions.next_sessions(TUESDAY, 4)] == [
        "2026-11-25", "2026-11-27", "2026-11-30", "2026-12-01"]
    assert not sessions.is_session(THANKSGIVING) and not sessions.is_session(SATURDAY) and not sessions.is_session(SUNDAY)
    assert sessions.previous_session(FRIDAY) == WEDNESDAY and sessions.previous_session(MONDAY) == FRIDAY
    opens, closes, shortened = sessions.hours(FRIDAY)
    assert (opens.isoformat(), closes.isoformat(), shortened) == (
        "2026-11-27T09:30:00-05:00", "2026-11-27T13:00:00-05:00", True)
    assert sessions.completion_at(FRIDAY).isoformat() == "2026-11-27T13:15:00-05:00"
    # one second before the half day's completion the completed session is still Wednesday's
    assert sessions.completed_session(at("2026-11-27T13:14:59-05:00")) == WEDNESDAY
    assert sessions.completed_session(at("2026-11-27T13:15:00-05:00")) == FRIDAY
    # all of Thursday, the weekend and Monday before its own completion
    assert sessions.completed_session(at("2026-11-26T18:20:00-05:00")) == WEDNESDAY
    for clock in ("2026-11-28T12:00:00-05:00", "2026-11-29T23:59:00-05:00", "2026-11-30T16:14:59-05:00"):
        assert sessions.completed_session(at(clock)) == FRIDAY, clock
    assert sessions.completed_session(at("2026-11-30T16:15:00-05:00")) == MONDAY


# ------------------------------------------------ Wednesday: plans for Friday ---
def test_every_night_of_the_week_published_and_thanksgiving_did_not(week):
    for name, day in (("tuesday", TUESDAY), ("wednesday", WEDNESDAY), ("friday", FRIDAY), ("monday", MONDAY)):
        rep = week.reports[name]
        assert rep.published and not rep.failed and rep.skipped is None, name
        assert week.record(name)["run"]["session"] == day.isoformat()
        assert week.record(name)["run"]["run_id"] == RUN_ID
    rep = week.reports["thanksgiving"]
    assert rep.skipped == "no_session" and not rep.published and not rep.failed
    assert rep.calendar_outcome["outcome"] == "no_session"
    # the closed day asked no provider, read no chart and sent no mail ...
    assert week.calls["thanksgiving"] == {"bars": 0, "reader": 0, "mail": 0}
    assert week.calls["wednesday"]["bars"] >= 1 and week.calls["wednesday"]["mail"] == 1
    # ... and left every published file as Wednesday wrote it
    before, after = week.docs("wednesday"), week.docs("thanksgiving")
    names = sorted(p.relative_to(before).as_posix() for p in before.rglob("*") if p.is_file())
    assert names == sorted(p.relative_to(after).as_posix() for p in after.rglob("*") if p.is_file())
    assert all((before / n).read_bytes() == (after / n).read_bytes() for n in names)
    assert "data.json" in names and "orders.json" in names


def test_wednesdays_plans_are_for_friday_and_its_window_is_the_ordinary_one(week):
    run = week.record("wednesday")["run"]
    tm = run["timing"]
    assert tm["applicable_session"] == "2026-11-27" and tm["basis"] == timing.BASIS_EXCHANGE_AFTER
    # the half day shortens the close, never the open or the first-30-minutes window
    assert (tm["opens_at"], tm["cutoff_at"], tm["prepare_by"], tm["closes_at"]) == (
        "2026-11-27T09:30:00-05:00", "2026-11-27T10:00:00-05:00", "2026-11-27T09:28:00-05:00",
        "2026-11-27T13:00:00-05:00")
    cal = run["calendar"]
    assert (cal["measured_session"], cal["previous_session"], cal["applicable_session"]) == (
        "2026-11-25", "2026-11-24", "2026-11-27")
    assert cal["applicable"]["shortened"] is True and cal["measured"]["shortened"] is False
    assert cal["applicable"]["completion_at"] == "2026-11-27T13:15:00-05:00"
    assert "2026-11-26" not in [row["session"] for row in cal["schedule"]["sessions"]]
    dl = run["delivery"]
    assert (dl["next_session"], dl["next_open_at"], dl["before_next_open"]) == (
        "2026-11-27", "2026-11-27T09:30:00-05:00", True)
    assert (dl["primary_slot_at"], dl["retry_slot_at"]) == ("2026-11-25T18:16:00-05:00", "2026-11-25T20:16:00-05:00")
    # the freshness answer every reader takes from the record: nothing is expected on Thursday
    expected = freshness.expected(week.record("wednesday"))
    assert (expected["covers_through"], expected["next_session"]) == ("2026-11-25", "2026-11-27")
    assert expected["completion_at"] == "2026-11-27T13:15:00-05:00"
    assert expected["recovery_until"] == "2026-11-30T09:30:00-05:00"      # Friday's session, until Monday's open


def test_the_handoff_holds_through_the_holiday_and_names_the_early_close(week):
    for name, days in (("tuesday", ["2026-11-25", "2026-11-27", "2026-11-30", "2026-12-01", "2026-12-02"]),
                       ("wednesday", ["2026-11-27", "2026-11-30", "2026-12-01", "2026-12-02", "2026-12-03"]),
                       ("friday", ["2026-11-30", "2026-12-01", "2026-12-02", "2026-12-03", "2026-12-04"])):
        book = week.orders(name)
        assert orders.problems(book) == [] and orders.check(week.docs(name)) == [], name
        assert book["tickets"], "the synthetic market publishes a ticket every night of this week"
        record = week.record(name)
        assert days == [d.isoformat() for d in plan.next_sessions(date.fromisoformat(record["run"]["session"]),
                                                                  plan.FINAL_EXIT_DAY)]
        for ticket in book["tickets"]:
            hold = ticket["exit_plan"]["sessions"]
            assert [h["date"] for h in hold] == days and "2026-11-26" not in days
            for h in hold:
                early = h["date"] == "2026-11-27"
                assert h["early_close"] is early
                assert h["close_at"] == f"{h['date']}T{'13:00' if early else '16:00'}:00-05:00"
            entry = ticket["entry"]
            assert (entry["valid_from"], entry["valid_until"], entry["cancel_if_unfilled_at"]) == (
                f"{days[0]}T09:30:00-05:00", f"{days[0]}T10:00:00-05:00", f"{days[0]}T10:00:00-05:00")
            rules = {r["key"]: r for r in ticket["exit_plan"]["rules"]}
            assert (rules["day3_sell_half"]["from_date"], rules["day5_exit"]["to_date"]) == (days[2], days[4])
    # Wednesday's day 1 IS the half day: a position entered on Friday morning has until 1:00 PM
    first = week.orders("wednesday")["tickets"][0]["exit_plan"]["sessions"][0]
    assert (first["day"], first["date"], first["early_close"]) == (1, "2026-11-27", True)


# ------------------------------------------------------- Thursday: closed ---
@pytest.mark.parametrize("clock,cron", [
    ("2026-11-26T23:17:00+00:00", PRIMARY_EST),      # Thursday's own primary slot
    ("2026-11-27T01:17:00+00:00", RETRY_EST),        # and its retry, after UTC midnight
    ("2026-11-27T06:00:00+00:00", PRIMARY_EST),      # the primary event delivered hours late
    ("2026-11-26T23:17:00+00:00", PRIMARY_EDT),      # the summer pair is never the active one in November
    ("2026-11-26T15:00:00+00:00", PRIMARY_EST),      # Wednesday's own slot, delivered on Thursday: already published
    ("2026-11-26T15:00:00+00:00", RETRY_EST),
])
def test_no_evening_slot_runs_on_thanksgiving(week, guard_code, clock, cron):
    decision = evening_guard(week, "thanksgiving", clock, cron, guard_code)
    assert decision["go"] is False and decision["session"] is None, decision


def guarded(week: Week, name: str, clock: str, code: str) -> dict:
    """The evening guard for the dispatcher's own start (only_if_unpublished ticked) at ``clock``."""
    with mock.patch.dict(os.environ, {"SCAN_ONLY_IF_UNPUBLISHED": "true"}):
        return _dispatch_guard(week.states[name], clock, code)


def test_nothing_else_is_due_or_flagged_on_thanksgiving(week, guard_code):
    data = week.raw("thanksgiving")
    # the scheduled morning slot knows the day has no session; a hand-started check is always let through
    # to the collector, which refuses the day itself
    assert pm.schedule_guard(data, "schedule", MORNING_EST, at("2026-11-26T14:21:00+00:00")) == (
        False, "not_exchange_session")
    assert pm.schedule_guard(data, "workflow_dispatch", "", at("2026-11-26T14:21:00+00:00")) == (
        True, "manual_dispatch")
    # the on-time dispatcher starts no morning and no watch all day: only the evening's four guarded starts,
    # its recovery for a missed Wednesday, and Wednesday is published, so the guard refuses every one of them
    slots = ds.slots_on(THANKSGIVING)
    assert [s.workflow for s in slots] == ["evening.yml"] * 4
    assert all(dict(s.inputs) == {"only_if_unpublished": "true"} for s in slots)
    clock = at("2026-11-26T00:00:00-05:00")
    while clock < at("2026-11-27T00:00:00-05:00"):
        assert all(s.workflow == "evening.yml" for s in ds.due(clock)), clock
        clock += timedelta(minutes=15)
    for slot in slots:
        start = (slot.at + timedelta(minutes=1)).astimezone(UTC).isoformat()
        assert guarded(week, "thanksgiving", start, guard_code)["go"] is False, start
        # had Wednesday not been published, the same start would publish it before Friday's open
        assert guarded(week, "wednesday-morning", start, guard_code) == {"go": True, "session": "2026-11-25"}, start
    # and the watch, whenever it runs that day, has nothing to say: Wednesday's record is the newest
    # there can be, and the morning it is for is Friday's
    for clock in ("2026-11-26T05:07:00+00:00", "2026-11-26T12:00:00+00:00", "2026-11-26T14:45:00+00:00",
                  "2026-11-26T17:00:00+00:00", "2026-11-26T23:30:00+00:00", "2026-11-27T05:07:00+00:00"):
        result = watch(week, "thanksgiving", clock)
        assert result["alert"] is False and result["exit_code"] == sw.EXIT_OK, clock
        assert (result["evening"]["state"], result["evening"]["judgement"]) == (freshness.NEWEST, sw.OK)
        assert result["morning"]["judgement"] == sw.NOT_DUE and result["morning"]["applicable_session"] == "2026-11-27"


# ------------------------------------------- Friday: the half day's morning ---
def test_the_friday_morning_check_is_let_through_for_wednesdays_record(week):
    data = week.raw("thanksgiving")
    assert pm.schedule_guard(data, "schedule", MORNING_EST, at("2026-11-27T14:21:00+00:00")) == (
        True, "scheduled_morning")
    assert pm.schedule_guard(data, "schedule", "28 14 * * 1-5", at("2026-11-27T14:59:59+00:00")) == (
        True, "scheduled_morning")
    # the summer pair is not the active one, and the cutoff is the ordinary 10:00 AM ET
    assert pm.schedule_guard(data, "schedule", MORNING_EDT, at("2026-11-27T13:21:00+00:00")) == (
        False, "inactive_schedule")
    assert pm.schedule_guard(data, "schedule", MORNING_EST, at("2026-11-27T15:00:00+00:00")) == (
        False, "entry_window_ended")
    # a Friday slot delivered on Saturday is another day's
    assert pm.schedule_guard(data, "schedule", MORNING_EST, at("2026-11-28T06:00:00+00:00")) == (
        False, "scheduled_day_expired")
    due = [(s.workflow, s.at.isoformat()) for s in ds.due(at("2026-11-27T14:21:00+00:00"))]
    assert due == [("morning.yml", "2026-11-27T08:20:00-06:00")]


def test_the_watch_judges_the_friday_morning_from_its_alert_time(week, tmp_path):
    # before 8:25 AM Chicago the morning cannot be judged; Tuesday's receipt is still the one on disk
    early = watch(week, "thanksgiving", "2026-11-27T14:24:59+00:00")
    assert early["morning"]["judgement"] == sw.NOT_DUE and early["alert"] is False
    assert early["morning"]["alert_at"] == "2026-11-27T08:25:00-06:00"
    assert early["morning"]["due_at"] == "2026-11-27T08:45:00-06:00"
    # from then on a receipt bound to another publication is no morning check for this one: five minutes
    # before the 8:30 AM Chicago open, and under the same key through the gate's 8:45 line
    stale = watch(week, "thanksgiving", "2026-11-27T14:25:00+00:00")
    assert stale["morning"]["judgement"] == sw.NOT_LANDED and stale["morning"]["alert"] is True
    assert "bound to another publication" in stale["morning"]["sentence"]
    assert stale["morning"]["key"] == watch(week, "thanksgiving", "2026-11-27T14:45:00+00:00")["morning"]["key"] \
        == "morning:not_landed:2026-11-27"
    # the check that ran at 8:22 AM Chicago is inside its collection window (from 9:00 AM ET), and its
    # orders-morning.json is checked for this orders.json
    for clock in ("2026-11-27T14:25:00+00:00", "2026-11-27T14:45:00+00:00"):
        landed = watch(week, "friday-morning", clock)
        assert landed["morning"]["judgement"] == sw.LANDED and landed["alert"] is False, clock
        assert landed["morning"]["collection_starts_at"] == "2026-11-27T09:00:00-05:00"
    # without the morning run's go/cancel file the evening's pending one stands: not checked
    pending = tmp_path
    shutil.copytree(week.docs("friday-morning"), pending / "docs")
    (pending / "docs" / "orders-morning.json").write_bytes(
        orders.encode(orders.pending_morning((pending / "docs" / "orders.json").read_bytes())))
    unchecked = sw.watch(pending / "docs", at("2026-11-27T14:25:00+00:00"))
    assert (unchecked["morning"]["judgement"], unchecked["morning"]["key"]) == (
        sw.NOT_CHECKED, "morning:not_checked:2026-11-27")
    # the evening answer on Friday morning: nothing is expected until the 1:15 PM completion
    assert landed["evening"]["state"] == freshness.NEWEST


# ------------------------------------------- Friday: the half day's evening ---
def test_the_half_day_completes_early_and_publishes_at_the_ordinary_slot(week, guard_code):
    # between the 1:15 PM completion and the 6:16 PM slot nothing is due: the watch says not due,
    # the dispatcher has no slot, and a guarded dispatch is too early
    for clock in ("2026-11-27T18:15:00+00:00", "2026-11-27T20:00:00+00:00", "2026-11-27T23:15:59+00:00"):
        result = watch(week, "friday-morning", clock)
        assert result["evening"]["state"] == freshness.NOT_DUE and result["alert"] is False, clock
        assert ds.due(at(clock)) == [], clock
    assert watch(week, "friday-morning", "2026-11-27T18:14:59+00:00")["evening"]["state"] == freshness.NEWEST
    # the scheduled slot at 6:16 PM ET runs Friday's session; the summer cron does not
    go = evening_guard(week, "friday-morning", "2026-11-27T23:17:00+00:00", PRIMARY_EST, guard_code)
    assert (go["go"], go["session"]) == (True, "2026-11-27")
    assert evening_guard(week, "friday-morning", "2026-11-27T22:17:00+00:00", PRIMARY_EDT, guard_code)["go"] is False
    assert [(s.workflow, s.at.isoformat()) for s in ds.due(at("2026-11-27T23:21:00+00:00"))] == [
        ("evening.yml", "2026-11-27T18:20:00-05:00")]
    run = week.record("friday")["run"]
    dl = run["delivery"]
    assert dl["completion_at"] == "2026-11-27T13:15:00-05:00" and dl["slot"] == delivery.SLOT_AFTER_PRIMARY
    # 6:20 PM is 305 minutes after a 1:15 PM completion, and 4 after the slot that did not move
    assert dl["latency_minutes"] == 305.0 and dl["after_primary_minutes"] == 4.0
    assert (dl["next_session"], dl["next_open_at"]) == ("2026-11-30", "2026-11-30T09:30:00-05:00")
    tm = run["timing"]
    assert (tm["applicable_session"], tm["opens_at"], tm["closes_at"]) == (
        "2026-11-30", "2026-11-30T09:30:00-05:00", "2026-11-30T16:00:00-05:00")
    assert run["calendar"]["measured"]["shortened"] is True and run["calendar"]["previous_session"] == "2026-11-25"


# ------------------------------------------------ the weekend and Monday ---
def test_the_weekend_starts_nothing_and_flags_nothing(week, guard_code):
    # the Friday retry slot arrives on Saturday in UTC, and Friday is already published
    retry = evening_guard(week, "friday", "2026-11-28T01:17:00+00:00", RETRY_EST, guard_code)
    assert retry["go"] is False and "already published" in retry["reason"]
    late = evening_guard(week, "friday", "2026-11-28T09:00:00+00:00", PRIMARY_EST, guard_code)
    assert late["go"] is False and "already published" in late["reason"]
    # the dispatcher's only weekend starts are the evening's guarded recovery, and Friday is published:
    # every one of them does nothing; had Friday been missed, each would publish it before Monday's open
    for day in (SATURDAY, SUNDAY):
        slots = ds.slots_on(day)
        assert [s.workflow for s in slots] == ["evening.yml"] * 4, day
        for slot in slots:
            start = (slot.at + timedelta(minutes=1)).astimezone(UTC).isoformat()
            assert guarded(week, "friday", start, guard_code)["go"] is False, start
            assert guarded(week, "friday-morning", start, guard_code) == {"go": True, "session": "2026-11-27"}, start
    data = week.raw("friday")
    for clock in ("2026-11-28T14:21:00+00:00", "2026-11-29T14:21:00+00:00"):
        assert pm.schedule_guard(data, "schedule", MORNING_EST, at(clock)) == (False, "inactive_schedule")
        assert ds.due(at(clock)) == []
    for clock in ("2026-11-28T05:07:00+00:00", "2026-11-28T15:00:00+00:00", "2026-11-29T09:07:00+00:00",
                  "2026-11-29T23:00:00+00:00", "2026-11-30T08:00:00+00:00", "2026-11-30T14:24:59+00:00"):
        result = watch(week, "friday", clock)
        assert result["alert"] is False and result["exit_code"] == sw.EXIT_OK, clock
        assert result["evening"]["state"] == freshness.NEWEST and result["morning"]["judgement"] == sw.NOT_DUE


def test_mondays_morning_is_fridays_record(week, guard_code):
    data = week.raw("friday")
    assert pm.schedule_guard(data, "schedule", MORNING_EST, at("2026-11-30T14:21:00+00:00")) == (
        True, "scheduled_morning")
    assert [(s.workflow, s.at.isoformat()) for s in ds.due(at("2026-11-30T14:21:00+00:00"))] == [
        ("morning.yml", "2026-11-30T08:20:00-06:00")]
    # Wednesday's receipt, still on disk over the weekend, is no check for Friday's record
    stale = watch(week, "friday", "2026-11-30T14:45:00+00:00")
    assert stale["morning"]["judgement"] == sw.NOT_LANDED and stale["morning"]["alert"] is True
    assert stale["morning"]["applicable_session"] == "2026-11-30"
    landed = watch(week, "monday-morning", "2026-11-30T14:45:00+00:00")
    assert landed["morning"]["judgement"] == sw.LANDED and landed["alert"] is False
    go = evening_guard(week, "monday-morning", "2026-11-30T23:17:00+00:00", PRIMARY_EST, guard_code)
    assert (go["go"], go["session"]) == (True, "2026-11-30")
    run = week.record("monday")["run"]
    assert run["calendar"]["previous_session"] == "2026-11-27"
    assert run["timing"]["applicable_session"] == "2026-12-01"


def test_a_friday_that_was_never_published_is_flagged_on_saturday_morning_not_mondays(week, guard_code):
    """Wednesday's record is still the one on main: Friday's session completed at 1:15 PM ET and may
    be published until Monday's open. The watch flags it from ten hours after Friday's 6:16 PM ET
    primary slot, which over a weekend is earlier than six hours before Monday's open, keeps the same
    answer (and so the same key) until the open, and calls it missing from the open on."""
    limit = at("2026-11-30T09:30:00-05:00")
    # ten hours after 6:16 PM New York on Friday is 4:16 AM on Saturday, written out so the bound itself is held
    quiet = ("2026-11-27T23:30:00+00:00", "2026-11-28T04:15:59-05:00")
    for clock in quiet:
        result = watch(week, "friday-morning", clock)
        assert result["evening"]["judgement"] == sw.OK and result["evening"]["alert"] is False, clock
        assert result["evening"]["next_session"] == "2026-11-27"
    for clock in ("2026-11-28T04:16:00-05:00", "2026-11-29T15:00:00+00:00", "2026-11-30T03:30:00-05:00",
                  "2026-11-30T09:29:59-05:00"):
        near = watch(week, "friday-morning", clock)
        assert near["evening"]["judgement"] == sw.NOT_PUBLISHED and near["evening"]["alert"] is True, clock
        assert near["evening"]["key"] == "evening:not_published:2026-11-27"
        assert near["evening"]["recovery_until"] == "2026-11-30T09:30:00-05:00"
    missing = watch(week, "friday-morning", limit.isoformat())
    assert missing["evening"]["judgement"] == sw.MISSING and missing["evening"]["alert"] is True
    assert missing["evening"]["key"] == "evening:missing:2026-11-27"
    # the dispatcher starts no watch on a closed day: its first watch to mail it is Monday's 6:00 AM CT slot, and
    # only GitHub's backup crons, hours late, can run one before that
    assert first_watch_slot(at("2026-11-28T04:16:00-05:00")) == at("2026-11-30T06:00:00-06:00")
    # all weekend a guarded dispatch would still publish Friday; from Monday's open it will not
    code = guard_code
    root = week.states["friday-morning"]

    def guarded(clock: str) -> dict:
        with mock.patch.dict(os.environ, {"SCAN_ONLY_IF_UNPUBLISHED": "true"}):
            return _dispatch_guard(root, clock, code)
    for clock in ("2026-11-27T23:16:00+00:00", "2026-11-28T15:00:00+00:00", "2026-11-29T15:00:00+00:00",
                  "2026-11-30T14:29:59+00:00"):
        assert guarded(clock) == {"go": True, "session": "2026-11-27"}, clock
    assert guarded("2026-11-27T23:15:59+00:00")["go"] is False          # before its own primary slot
    assert guarded("2026-11-30T14:30:00+00:00")["go"] is False          # Monday's open: the limit, inclusive


def _dispatch_guard(root: Path, clock: str, code: str) -> dict:
    """The evening guard for a workflow_dispatch at ``clock``, run as written with the clock frozen."""
    import contextlib
    import datetime as datetime_module
    import io
    import tempfile

    instant = at(clock)
    real = datetime_module.datetime

    class Frozen(real):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

    cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "github-output"
        env = {"SCAN_EVENT_NAME": "workflow_dispatch", "SCAN_EVENT_SCHEDULE": "", "SCAN_REQUESTED_SESSION": "",
               "GITHUB_OUTPUT": str(output)}
        try:
            os.chdir(root)
            datetime_module.datetime = Frozen
            with mock.patch.dict(os.environ, env), contextlib.redirect_stdout(io.StringIO()):
                exec(compile(code, "evening.yml guard", "exec"), {})
        finally:
            datetime_module.datetime = real
            os.chdir(cwd)
        fields = dict(line.split("=", 1) for line in output.read_text().splitlines())
    return {"go": fields["go"] == "true", "session": fields["session"] or None}


# ------------------------------------------------------------ the gate ---
def test_the_gate_closes_each_session_across_the_holiday_and_the_weekend(week):
    ledger = week.record("monday")["run"]["go_live"]["ledger"]
    assert [(r["session"], r["applicable_session"]) for r in ledger] == [
        ("2026-11-24", "2026-11-25"), ("2026-11-25", "2026-11-27"), ("2026-11-27", "2026-11-30")]
    for row in ledger:
        assert (row["on_time"], row["automatic"], row["morning_on_time"], row["counted"]) == (True, True, True, True), row
    # each session is closed by the next session's evening, never by a closed day's
    assert week.record("wednesday")["run"]["go_live"]["ledger"][-1]["session"] == "2026-11-24"
    assert week.record("thanksgiving")["run"]["go_live"] == week.record("wednesday")["run"]["go_live"]
    assert week.record("friday")["run"]["go_live"]["ledger"][-1]["session"] == "2026-11-25"
    held = {name: next(c for c in week.record(name)["run"]["go_live"]["criteria"] if c["key"] == "on_time_sessions")["have"]
            for name in ("tuesday", "wednesday", "friday", "monday")}
    # Thanksgiving and the weekend are not gaps in the run of consecutive sessions
    assert held == {"tuesday": 0, "wednesday": 1, "friday": 2, "monday": 3}


@pytest.mark.parametrize("generated,counts", [
    ("2026-11-27T14:00:00+00:00", True),      # 9:00 AM ET: the collection window's first instant
    ("2026-11-27T13:59:59+00:00", False),     # a second before it
    ("2026-11-27T14:45:00+00:00", True),      # 8:45 AM Chicago, the due time itself
    ("2026-11-27T14:45:01+00:00", False),     # a second after
    ("2026-11-26T14:22:00+00:00", False),     # 8:22 AM on Thanksgiving: not the session the plans were for
    ("2026-11-30T14:22:00+00:00", False),     # nor the Monday after
])
def test_wednesdays_morning_check_counts_only_on_friday_morning(week, generated, counts):
    raw = week.raw("wednesday")
    row = go_live.close_session(json.loads(raw), hashlib.sha256(raw).hexdigest(), receipt_for(raw, generated))
    assert row["applicable_session"] == "2026-11-27" and row["morning_on_time"] is counts
    assert row["counted"] is counts


def _closed(session: str, applicable: str, finished: str, generated: str, opens: str) -> dict:
    """A publication as close_session() reads it, finished and checked at the instants given."""
    raw = json.dumps({"run": {"session": session, "status": "ok", "dry_run": False, "published_at": finished,
                              "finish_seconds": 0, "trigger": {"event": "schedule", "only_if_unpublished": False},
                              "timing": {"applicable_session": applicable, "opens_at": opens,
                                         "cutoff_at": opens.replace("T09:30", "T10:00")}}}).encode()
    return go_live.close_session(json.loads(raw), hashlib.sha256(raw).hexdigest(), receipt_for(raw, generated))


@pytest.mark.parametrize("session,applicable,opens,utc_evening,utc_morning", [
    # the Friday before the clocks go back: 7 PM EDT is 23:00 UTC; Monday's 8:45 AM CST is 14:45 UTC
    ("2026-10-30", "2026-11-02", "2026-11-02T09:30:00-05:00", "2026-10-30T23:00:00+00:00", "2026-11-02T14:45:00+00:00"),
    # the Monday after: 7 PM EST is midnight UTC
    ("2026-11-02", "2026-11-03", "2026-11-03T09:30:00-05:00", "2026-11-03T00:00:00+00:00", "2026-11-03T14:45:00+00:00"),
    # the Friday before the clocks go forward: 7 PM EST; Monday's 8:45 AM CDT is 13:45 UTC
    ("2027-03-12", "2027-03-15", "2027-03-15T09:30:00-04:00", "2027-03-13T00:00:00+00:00", "2027-03-15T13:45:00+00:00"),
    # the Monday after: 7 PM EDT
    ("2027-03-15", "2027-03-16", "2027-03-16T09:30:00-04:00", "2027-03-15T23:00:00+00:00", "2027-03-16T13:45:00+00:00"),
])
def test_the_gates_two_deadlines_are_wall_clock_times_on_both_sides_of_a_clock_change(
        session, applicable, opens, utc_evening, utc_morning):
    evening, morning = at(utc_evening), at(utc_morning)
    assert evening.astimezone(go_live.NEW_YORK).strftime("%Y-%m-%d %H:%M") == f"{session} {go_live.PUBLISH_BY_ET}"
    assert morning.astimezone(go_live.CHICAGO).strftime("%Y-%m-%d %H:%M") == f"{applicable} {go_live.MORNING_DUE_CT}"
    second = timedelta(seconds=1)
    on_time = _closed(session, applicable, evening.isoformat(), morning.isoformat(), opens)
    assert (on_time["on_time"], on_time["morning_on_time"], on_time["counted"]) == (True, True, True)
    late_evening = _closed(session, applicable, (evening + second).isoformat(), morning.isoformat(), opens)
    assert (late_evening["on_time"], late_evening["counted"]) == (False, False)
    late_morning = _closed(session, applicable, evening.isoformat(), (morning + second).isoformat(), opens)
    assert (late_morning["morning_on_time"], late_morning["counted"]) == (False, False)
    # a run that finished after New York's midnight is on the wrong date, however early its clock reads
    after_midnight = _closed(session, applicable, (evening + timedelta(hours=6)).isoformat(), morning.isoformat(), opens)
    assert (evening + timedelta(hours=6)).astimezone(go_live.NEW_YORK).strftime("%H:%M") == "01:00"
    assert (after_midnight["on_time"], after_midnight["counted"]) == (False, False)
    # and one that finished at 6:59 PM the evening before its session's date is not that session's
    day_before = _closed(session, applicable, (evening - timedelta(days=1, minutes=1)).isoformat(), morning.isoformat(), opens)
    assert (day_before["on_time"], day_before["counted"]) == (False, False)


# ------------------------------------------------------ the clock changes ---
#: (the Friday before, the Monday after, UTC offset before, UTC offset after) for each change
CHANGES = [("2026-10-30", "2026-11-02", "-04:00", "-05:00"), ("2027-03-12", "2027-03-15", "-05:00", "-04:00")]


@pytest.mark.parametrize("friday,monday,before,after", CHANGES)
def test_a_fridays_plans_cross_the_clock_change_at_mondays_own_offset(friday, monday, before, after):
    assert sessions.next_sessions(date.fromisoformat(friday), 1) == [date.fromisoformat(monday)]
    tm = timing.plan_timing(date.fromisoformat(friday), date.fromisoformat(monday),
                            window="first 30 minutes", window_minutes=30)
    assert (tm["opens_at"], tm["cutoff_at"], tm["prepare_by"], tm["closes_at"]) == (
        f"{monday}T09:30:00{after}", f"{monday}T10:00:00{after}", f"{monday}T09:28:00{after}",
        f"{monday}T16:00:00{after}")
    # the evening slots are 6:16 and 8:16 PM New York on each side, an hour apart in UTC
    for day, offset in ((friday, before), (monday, after)):
        primary, retry = delivery.slots(date.fromisoformat(day))
        assert (primary.isoformat(), retry.isoformat()) == (f"{day}T18:16:00{offset}", f"{day}T20:16:00{offset}")
        assert sessions.completion_at(date.fromisoformat(day)).isoformat() == f"{day}T16:15:00{offset}"
    block = delivery.block(date.fromisoformat(friday), f"{friday}T18:20:00{before}")
    assert (block["next_session"], block["next_open_at"]) == (monday, f"{monday}T09:30:00{after}")
    assert block["before_next_open"] is True and block["after_primary_minutes"] == 4.0


@pytest.mark.parametrize("clock,cron,session", [
    # Friday 30 October 2026, daylight time: the "22" and "0" crons are the active pair
    ("2026-10-30T22:17:00+00:00", PRIMARY_EDT, "2026-10-30"),
    ("2026-10-30T23:17:00+00:00", PRIMARY_EST, None),
    ("2026-10-31T00:17:00+00:00", RETRY_EDT, "2026-10-30"),
    ("2026-10-31T01:17:00+00:00", RETRY_EST, None),
    # Monday 2 November 2026, standard time: the "23" and "1" crons
    ("2026-11-02T22:17:00+00:00", PRIMARY_EDT, None),
    ("2026-11-02T23:17:00+00:00", PRIMARY_EST, "2026-11-02"),
    ("2026-11-03T00:17:00+00:00", RETRY_EDT, None),
    ("2026-11-03T01:17:00+00:00", RETRY_EST, "2026-11-02"),
    # Friday 12 March 2027, still standard time
    ("2027-03-12T22:17:00+00:00", PRIMARY_EDT, None),
    ("2027-03-12T23:17:00+00:00", PRIMARY_EST, "2027-03-12"),
    ("2027-03-13T00:17:00+00:00", RETRY_EDT, None),
    ("2027-03-13T01:17:00+00:00", RETRY_EST, "2027-03-12"),
    # Monday 15 March 2027, daylight time again
    ("2027-03-15T22:17:00+00:00", PRIMARY_EDT, "2027-03-15"),
    ("2027-03-15T23:17:00+00:00", PRIMARY_EST, None),
    ("2027-03-16T00:17:00+00:00", RETRY_EDT, "2027-03-15"),
    ("2027-03-16T01:17:00+00:00", RETRY_EST, None),
])
def test_exactly_one_evening_cron_pair_is_active_on_each_side_of_a_clock_change(tmp_path, guard_code, clock, cron,
                                                                              session):
    (tmp_path / "docs").mkdir()
    decision = rr.guard(tmp_path, clock, cron, guard_code)
    assert (decision["go"], decision["session"]) == (session is not None, session), decision


@pytest.mark.parametrize("clock,cron,day,offset,answer", [
    ("2026-10-30T13:21:00+00:00", "20 13 * * 1-5", "2026-10-30", "-04:00", (True, "scheduled_morning")),
    ("2026-10-30T14:21:00+00:00", "20 14 * * 1-5", "2026-10-30", "-04:00", (False, "inactive_schedule")),
    ("2026-11-02T14:21:00+00:00", "20 14 * * 1-5", "2026-11-02", "-05:00", (True, "scheduled_morning")),
    ("2026-11-02T13:21:00+00:00", "20 13 * * 1-5", "2026-11-02", "-05:00", (False, "inactive_schedule")),
    ("2027-03-12T14:29:00+00:00", "28 14 * * 1-5", "2027-03-12", "-05:00", (True, "scheduled_morning")),
    ("2027-03-12T13:29:00+00:00", "28 13 * * 1-5", "2027-03-12", "-05:00", (False, "inactive_schedule")),
    ("2027-03-15T13:29:00+00:00", "28 13 * * 1-5", "2027-03-15", "-04:00", (True, "scheduled_morning")),
    ("2027-03-15T14:29:00+00:00", "28 14 * * 1-5", "2027-03-15", "-04:00", (False, "inactive_schedule")),
    # the cutoff is 10:00 AM New York on each side: 14:00 UTC in daylight time, 15:00 in standard time
    ("2026-10-30T14:00:00+00:00", "20 13 * * 1-5", "2026-10-30", "-04:00", (False, "entry_window_ended")),
    ("2026-11-02T15:00:00+00:00", "20 14 * * 1-5", "2026-11-02", "-05:00", (False, "entry_window_ended")),
])
def test_exactly_one_morning_cron_pair_is_active_on_each_side_of_a_clock_change(monkeypatch, clock, cron, day,
                                                                              offset, answer):
    from src import morning
    monkeypatch.setattr(morning, "bind_record",
                        lambda raw: {"applicable_session": json.loads(raw)["run"]["timing"]["applicable_session"]})
    record = json.dumps({"run": {"timing": {"applicable_session": day, "cutoff_at": f"{day}T10:00:00{offset}"}}})
    assert pm.schedule_guard(record.encode(), "schedule", cron, at(clock)) == answer


@pytest.mark.parametrize("day,evening_utc,morning_utc,watch_utc", [
    ("2026-10-30", "22:20", "13:20", ["11:00", "13:25", "14:05", "23:00", "01:50"]),      # daylight time
    ("2026-11-02", "23:20", "14:20", ["12:00", "14:25", "15:05", "00:00", "02:50"]),      # standard time
    ("2027-03-12", "23:20", "14:20", ["12:00", "14:25", "15:05", "00:00", "02:50"]),
    ("2027-03-15", "22:20", "13:20", ["11:00", "13:25", "14:05", "23:00", "01:50"]),
    ("2026-11-27", "23:20", "14:20", ["12:00", "14:25", "15:05", "00:00", "02:50"]),      # the half day: no slot moves
    ("2026-11-30", "23:20", "14:20", ["12:00", "14:25", "15:05", "00:00", "02:50"]),      # the Monday after it
])
def test_the_dispatchers_slots_are_wall_clock_times_whatever_the_offset(day, evening_utc, morning_utc, watch_utc):
    slots = ds.slots_on(date.fromisoformat(day))

    def utc(workflow):
        return [s.at.astimezone(UTC).strftime("%H:%M") for s in slots if s.workflow == workflow]
    assert utc("evening.yml")[0] == evening_utc and utc("morning.yml") == [morning_utc]
    assert utc("service-watch.yml") == watch_utc
    local = {(s.workflow, s.at.strftime("%H:%M")) for s in slots}
    assert ("evening.yml", "18:20") in local and ("morning.yml", "08:20") in local
    # the first evening slot is four minutes after the delivery policy's primary slot, the morning slot
    # is inside the collection window (it starts thirty minutes before the 9:30 AM New York open)
    primary = delivery.slots(date.fromisoformat(day))[0]
    first_evening = next(s.at for s in slots if s.workflow == "evening.yml")
    assert first_evening - primary == timedelta(minutes=4)
    opens = sessions.hours(date.fromisoformat(day))[0]
    morning_slot = next(s.at for s in slots if s.workflow == "morning.yml")
    assert opens - timedelta(minutes=freshness.PREOPEN_MINUTES) <= morning_slot < opens


@pytest.mark.parametrize("day,due_utc", [("2026-10-30", "13:45"), ("2026-11-02", "14:45"),
                                         ("2027-03-12", "14:45"), ("2027-03-15", "13:45")])
def test_the_watchs_morning_due_time_is_chicagos_wall_clock(day, due_utc):
    due = sw.morning_due(day)
    assert due.astimezone(UTC).strftime("%Y-%m-%d %H:%M") == f"{day} {due_utc}"
    assert due.strftime("%H:%M") == sw.MORNING_DUE_CT == go_live.MORNING_DUE_CT
    # 8:45 AM Chicago is 9:45 AM New York on both sides: fifteen minutes into the entry window
    assert due.astimezone(sessions.MARKET_TZ).strftime("%H:%M") == "09:45"


@pytest.mark.parametrize("day,alert_utc", [("2026-10-30", "13:25"), ("2026-11-02", "14:25"),
                                           ("2027-03-12", "14:25"), ("2027-03-15", "13:25")])
def test_the_watchs_morning_alert_is_chicagos_wall_clock_before_the_open(day, alert_utc):
    alert = sw.morning_alert(day)
    assert alert.astimezone(UTC).strftime("%Y-%m-%d %H:%M") == f"{day} {alert_utc}"
    # 8:25 AM Chicago is 9:25 AM New York on both sides: five minutes before the entry window opens
    assert alert.astimezone(sessions.MARKET_TZ).strftime("%H:%M") == "09:25"
    assert alert < sessions.hours(date.fromisoformat(day))[0]


# ------------------------------------- every alert before the 8:30 AM CT open ---
CHICAGO = sw.CHICAGO
ONE_SECOND = timedelta(seconds=1)


def synthetic_record(covers: date) -> dict:
    """SYNTHETIC record covering ``covers``: only the blocks the watch reads, each written by the module that
    writes it in a real record (the calendar, the delivery block of an on-time 6:20 PM ET run, the entry
    window, a funnel with no ticket)."""
    published = (delivery.slots(covers)[0] + timedelta(minutes=4)).isoformat()
    return {"run": {"session": str(covers), "status": "ok", "dry_run": False, "run_id": "1",
                    "published_at": published, "calendar": sessions.publication(covers),
                    "delivery": delivery.block(covers, published),
                    "timing": pipeline.plan_timing(covers, covers, False)},
            "funnel": {"reaction": {"stages": {"ticket": 0}}, "anticipation": {"stages": {"ticket": 0}}}}


#: (the session the record covers, the session its evening publishes S, the session after it A). The record's
#: plans and its morning check are for S; S's absence is to be known before A's 8:30 AM CT open.
SCENARIOS = [
    pytest.param(date(2026, 11, 13), date(2026, 11, 16), date(2026, 11, 17), id="monday"),
    pytest.param(date(2026, 11, 24), date(2026, 11, 25), date(2026, 11, 27), id="wednesday-before-thanksgiving"),
    pytest.param(date(2026, 11, 25), date(2026, 11, 27), date(2026, 11, 30), id="friday-half-day"),
    pytest.param(date(2026, 10, 29), date(2026, 10, 30), date(2026, 11, 2), id="friday-before-1-november"),
    pytest.param(date(2026, 10, 30), date(2026, 11, 2), date(2026, 11, 3), id="monday-after-1-november"),
    pytest.param(date(2027, 3, 11), date(2027, 3, 12), date(2027, 3, 15), id="friday-before-14-march"),
    pytest.param(date(2027, 3, 12), date(2027, 3, 15), date(2027, 3, 16), id="monday-after-14-march"),
]


def first_watch_slot(after: datetime) -> datetime:
    """The first of the dispatcher's watch slots at or after ``after``."""
    day = after.astimezone(CHICAGO).date() - timedelta(days=1)
    for _ in range(12):
        found = [s.at for s in ds.slots_on(day) if s.workflow == "service-watch.yml" and s.at >= after]
        if found:
            return min(found)
        day += timedelta(days=1)
    raise AssertionError(f"no watch slot after {after}")


def chicago(day: date, hhmm: str) -> datetime:
    return datetime.combine(day, datetime.strptime(hhmm, "%H:%M").time(), tzinfo=CHICAGO)


def new_york(day: date, hhmm: str) -> datetime:
    return datetime.combine(day, datetime.strptime(hhmm, "%H:%M").time(), tzinfo=sessions.MARKET_TZ)


@pytest.mark.parametrize("covers,session,after", SCENARIOS)
def test_every_evening_alert_is_true_and_mailed_before_the_next_open(covers, session, after):
    """For each alert about S, its first true instant -- held one second either side -- and the first watch
    slot of the on-time dispatcher at or after it are both before A's 8:30 AM Chicago open, and the alert
    still holds at that slot. ``missing`` is the one at the open itself, and ``not_published`` precedes it."""
    record = synthetic_record(covers)
    opens = sessions.hours(after)[0]
    assert opens.astimezone(CHICAGO).strftime("%H:%M") == "08:30"
    expected = freshness.expected(record)
    assert (expected["next_session"], sw._instant(expected["recovery_until"])) == (str(session), opens)
    name = str(session)

    # the evening has not started: 6:50 PM New York on S, with no run listed
    started_by = new_york(session, sw.EVENING_STARTED_BY_ET)
    assert sw.judge_evening(record, started_by - ONE_SECOND, [], None)["judgement"] == sw.NOT_DUE
    out = sw.judge_evening(record, started_by, [], None)
    assert (out["judgement"], out["key"]) == (sw.NOT_STARTED, f"evening:not_started:{name}")
    slot = first_watch_slot(started_by)
    assert started_by <= slot < opens and slot == new_york(session, "19:00")
    assert sw.judge_evening(record, slot, [], None)["key"] == out["key"]

    # every run failed: true from the failed run's own listing, here an hour after the primary slot
    primary = delivery.slots(session)[0]
    failed = {"id": 9, "event": "workflow_dispatch", "display_title": sw.EVENING_DISPATCH_TITLE,
              "created_at": (primary + timedelta(minutes=4)).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "status": "completed", "conclusion": "failure", "head_branch": "main", "run_attempt": 1}
    out = sw.judge_evening(record, primary + timedelta(hours=1), [failed], None)
    assert (out["judgement"], out["key"]) == (sw.FAILED, f"evening:failed:{name}")
    assert first_watch_slot(primary + timedelta(hours=1)) < opens

    # not published: the earlier of six hours before the open and ten hours after the primary slot
    deadline = sw.not_published_from(record, name, opens)
    assert deadline == min(opens - timedelta(hours=sw.ALERT_WITHIN_HOURS),
                           primary + timedelta(hours=sw.NOT_PUBLISHED_AFTER_PRIMARY_HOURS))
    assert sw.evening(record, deadline - ONE_SECOND)["judgement"] == sw.OK
    out = sw.evening(record, deadline)
    assert (out["judgement"], out["key"]) == (sw.NOT_PUBLISHED, f"evening:not_published:{name}")
    slot = first_watch_slot(deadline)
    assert deadline <= slot < opens and sw.evening(record, slot)["key"] == out["key"]
    if after - session > timedelta(days=1):
        # over a weekend or a holiday the judgement is true the morning after the evening, not hours before the
        # next open; only GitHub's backup crons run the watch on a closed day, and the dispatcher's first watch to
        # mail it is the next session's 6:00 AM CT slot
        local = deadline.astimezone(sessions.MARKET_TZ)
        assert (local.date(), local.strftime("%H:%M")) == (session + timedelta(days=1), "04:16")
        assert slot == chicago(after, "06:00")
    else:
        assert deadline == opens - timedelta(hours=sw.ALERT_WITHIN_HOURS)

    # not published although the dispatcher started it on time: 9:45 PM New York on S
    published_by = new_york(session, sw.EVENING_PUBLISHED_BY_ET)
    assert sw.evening(record, published_by - ONE_SECOND, on_time_start=True)["judgement"] == sw.OK
    assert sw.evening(record, published_by, on_time_start=True)["key"] == f"evening:not_published:{name}"
    assert published_by <= first_watch_slot(published_by) == new_york(session, "21:50") < opens

    # missing: at the open itself, never before it
    assert sw.evening(record, opens - ONE_SECOND)["judgement"] == sw.NOT_PUBLISHED
    assert sw.evening(record, opens)["key"] == f"evening:missing:{name}"


class Listing:
    """A double of the run listing: the runs given, filtered by ``since`` as GitHub filters."""

    def __init__(self, runs=None):
        self.runs_by = runs or {}

    def runs(self, workflow, since):
        return [r for r in self.runs_by.get(workflow, []) if ds._created(r["created_at"]) >= since]


def dispatch(workflow_title: str, created: datetime, **fields) -> dict:
    out = {"id": 4100, "event": "workflow_dispatch", "display_title": workflow_title,
           "created_at": created.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "status": "completed",
           "conclusion": "success", "head_branch": "main", "run_attempt": 1}
    out.update(fields)
    return out


@pytest.mark.parametrize("covers,session,after", [s for s in SCENARIOS if s.id in (
    "friday-half-day", "monday-after-1-november", "monday-after-14-march")])
def test_the_scheduler_alerts_reach_the_watch_across_the_half_day_and_the_clock_changes(covers, session, after,
                                                                                         tmp_path):
    """The whole watch, with a run listing, over a record whose next session is the half day or a session either
    side of a clock change: no evening run by 6:50 PM ET, an on-time dispatch unpublished at 9:45 PM ET, and no
    morning run by 8:25 AM CT each reach the alerts."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / sw.DATA_FILE).write_text(json.dumps(synthetic_record(covers)))
    name = str(session)
    started_by = new_york(session, sw.EVENING_STARTED_BY_ET)
    keys = [a["key"] for a in sw.watch(docs, started_by, github=Listing())["alerts"]]
    assert f"evening:not_started:{name}" in keys
    first = delivery.slots(session)[0] + timedelta(minutes=4)                    # the dispatcher's 6:20 start
    on_time = Listing({"evening.yml": [dispatch(sw.EVENING_DISPATCH_TITLE, first)]})
    published_by = new_york(session, sw.EVENING_PUBLISHED_BY_ET)
    out = sw.watch(docs, published_by, github=on_time)
    assert out["scheduler"]["evening"]["judgement"] == sw.ON_TIME
    assert f"evening:not_published:{name}" in [a["key"] for a in out["alerts"]]
    # the record's own morning (its plans are for the same session): nothing listed by 8:25 AM CT is the morning
    # check not started, said beside the morning's own alert
    out = sw.watch(docs, chicago(session, sw.MORNING_ALERT_CT), github=Listing())
    assert out["scheduler"]["morning"]["judgement"] == sw.NOT_STARTED
    (morning,) = [a for a in out["alerts"] if a["key"] == f"morning:not_landed:{name}"]
    assert "No morning run" in morning["detail"]


def test_an_off_season_evening_cron_in_standard_time_is_no_evening_run(tmp_path):
    """In EST the EDT pair (16 22, 16 0) fires and its guard skips it: the 4 December session's evening is not
    started, and a failed dispatch beside the skip is still failed."""
    record = synthetic_record(date(2026, 12, 3))
    skip = dispatch("Evening cron 16 22 * * 1-5", at("2026-12-04T22:16:30+00:00"), event="schedule", id=4201)
    out = sw.judge_evening(record, at("2026-12-05T02:30:00+00:00"), [skip], None)
    assert (out["judgement"], out["key"]) == (sw.NOT_STARTED, "evening:not_started:2026-12-04")
    failed = dispatch(sw.EVENING_DISPATCH_TITLE, at("2026-12-04T23:20:30+00:00"), conclusion="failure")
    out = sw.judge_evening(record, at("2026-12-05T02:30:00+00:00"), [skip, failed], None)
    assert (out["judgement"], out["key"]) == (sw.FAILED, "evening:failed:2026-12-04")
    # the active EST cron is a run: hours late, it is the backup's start
    active = dispatch("Evening cron 16 23 * * 1-5", at("2026-12-05T03:30:00+00:00"), event="schedule", id=4202)
    out = sw.judge_evening(record, at("2026-12-05T04:00:00+00:00"), [skip, active], None)
    assert (out["judgement"], out["key"]) == (sw.STARTED_LATE, "scheduler:evening:started_late")


@pytest.mark.parametrize("covers,session,after", SCENARIOS)
def test_the_morning_alerts_are_true_at_8_25_and_mailed_before_the_8_30_open(covers, session, after):
    record = synthetic_record(covers)
    raw = json.dumps(record).encode()
    assert freshness.morning_window(record)["applicable_session"] == str(session)
    alert = chicago(session, sw.MORNING_ALERT_CT)
    opens = sessions.hours(session)[0]
    assert opens == chicago(session, "08:30")
    files = {"orders_raw": None, "orders_morning_raw": None}
    early = sw.morning(record, raw, None, "morning.json is not a regular file", alert - ONE_SECOND, **files)
    assert early["judgement"] == sw.NOT_DUE
    out = sw.morning(record, raw, None, "morning.json is not a regular file", alert, **files)
    assert (out["judgement"], out["key"]) == (sw.NOT_LANDED, f"morning:not_landed:{session}")
    # a receipt that landed with no checked orders-morning.json beside it: not checked, from the same instant
    landed = receipt_for(raw, chicago(session, "08:22").isoformat())
    assert sw.morning(record, raw, landed, None, alert - ONE_SECOND, **files)["judgement"] == sw.NOT_DUE
    out = sw.morning(record, raw, landed, None, alert, **files)
    assert (out["judgement"], out["key"]) == (sw.NOT_CHECKED, f"morning:not_checked:{session}")
    # the dispatcher's watch is started at that very minute, five minutes before the open
    assert first_watch_slot(alert) == alert < opens
    # and the gate's 8:45 line gives the same answer under the same key
    assert sw.morning(record, raw, landed, None, chicago(session, sw.MORNING_DUE_CT), **files)["key"] == out["key"]
    # the morning's scheduler answer is asked at the same instant: none listed by 8:25 is not started
    assert sw.judge_morning(record, None, raw, alert, [], None)["judgement"] == sw.NOT_STARTED
    assert sw.judge_morning(record, None, raw, alert - ONE_SECOND, [], None)["judgement"] == sw.NOT_DUE


# --------------------------------- a weekday holiday's evening crons ---
def _cron_run(cron: str, created: datetime, run_id: int, **fields) -> dict:
    return dispatch(f"Evening cron {cron}", created, event="schedule", id=run_id, **fields)


def test_a_holidays_evening_crons_are_never_the_evening_runs_of_the_session_before_it():
    """Wednesday 25 November unpublished, read at Friday's 6:00 AM CT watch: the dispatcher's four starts and
    Wednesday's two backup crons all failed, and Thanksgiving's own crons -- the active pair, which the guard
    skips because the 26th is no session -- ended success. The night is failed, not started on time, and
    nothing is cleared."""
    record = synthetic_record(TUESDAY)
    runs = [dispatch(sw.EVENING_DISPATCH_TITLE, new_york(WEDNESDAY, hhmm) + timedelta(seconds=40), id=4300 + n,
                     conclusion="failure") for n, hhmm in enumerate(("18:20", "19:20", "20:20", "21:20"))]
    runs += [_cron_run(PRIMARY_EST, at("2026-11-26T04:30:00+00:00"), 4310, conclusion="failure"),
             _cron_run(RETRY_EST, at("2026-11-26T07:10:00+00:00"), 4311, conclusion="failure")]
    thanksgiving = [_cron_run(PRIMARY_EST, at("2026-11-27T03:40:00+00:00"), 4320),
                    _cron_run(RETRY_EST, at("2026-11-27T06:05:00+00:00"), 4321)]
    friday_watch = chicago(FRIDAY, "06:00")
    for listed in (runs, runs + thanksgiving):
        out = sw.judge_evening(record, friday_watch, listed, None)
        assert (out["session"], out["judgement"], out["key"]) == ("2026-11-25", sw.FAILED, "evening:failed:2026-11-25")
        assert {r["id"] for r in out["runs"]} == {r["id"] for r in runs}, "Thanksgiving's crons are no run of it"
    result = {"scheduler": {"evening": sw.judge_evening(record, friday_watch, runs + thanksgiving, None)},
              "start": {}, "alerts": []}
    assert "scheduler:evening:started_late" not in sw.clears_of(result)
    # each holiday cron is read as the guard reads it: skipped, and no session's
    for skipped in thanksgiving:
        assert sw.skipped_evening_cron(skipped) is True and sw.evening_cron_session(skipped) is None
    # Wednesday's own crons, hours late, are Wednesday's
    assert [sw.evening_cron_session(r) for r in runs[4:]] == ["2026-11-25", "2026-11-25"]


#: Every weekday XNYS holiday from Thanksgiving 2026 to Christmas 2027, with the session before it.
HOLIDAYS = [date(2026, 11, 26), date(2026, 12, 25), date(2027, 1, 1), date(2027, 1, 18), date(2027, 2, 15),
            date(2027, 3, 26), date(2027, 5, 31), date(2027, 6, 18), date(2027, 7, 5), date(2027, 9, 6),
            date(2027, 11, 25), date(2027, 12, 24)]


@pytest.mark.parametrize("holiday", HOLIDAYS, ids=[str(h) for h in HOLIDAYS])
def test_the_watch_reads_each_holidays_evening_crons_as_the_guard_runs_them(holiday, guard_code, tmp_path):
    """For each weekday holiday and the session before it, both active crons, on time and five hours late: the
    session the watch reads a cron run as (``evening_cron_session``) is the session the evening guard itself runs
    it for, and a run the guard skips is one the watch skips."""
    assert holiday.weekday() < 5 and not sessions.is_session(holiday)
    before = sessions.previous_session(holiday)
    for day in (before, holiday):
        edt = new_york(day, "12:00").utcoffset() == timedelta(hours=-4)
        for cron, hour, next_day in ((PRIMARY_EDT, 22, False), (RETRY_EDT, 0, True)) if edt else \
                ((PRIMARY_EST, 23, False), (RETRY_EST, 1, True)):
            slot = datetime.combine(day + timedelta(days=next_day), datetime.min.time().replace(hour=hour, minute=16),
                                    tzinfo=UTC)
            for late in (timedelta(seconds=40), timedelta(hours=5)):
                created = slot + late
                decision = rr.guard(tmp_path, created.isoformat(), cron, guard_code)
                listed = _cron_run(cron, created, 4400)
                assert sw.evening_cron_session(listed) == decision["session"], (day, cron, late, decision)
                assert sw.skipped_evening_cron(listed) is (decision["go"] is False), (day, cron, late)
                assert decision["session"] == (str(day) if day == before else None)
