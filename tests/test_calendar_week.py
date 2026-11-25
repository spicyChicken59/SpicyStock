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
        (docs / "morning.json").write_text(json.dumps(receipt_for((docs / "data.json").read_bytes(), generated)))
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


def test_nothing_else_is_due_or_flagged_on_thanksgiving(week):
    data = week.raw("thanksgiving")
    # the scheduled morning slot knows the day has no session; a hand-started check is always let through
    # to the collector, which refuses the day itself
    assert pm.schedule_guard(data, "schedule", MORNING_EST, at("2026-11-26T14:21:00+00:00")) == (
        False, "not_exchange_session")
    assert pm.schedule_guard(data, "workflow_dispatch", "", at("2026-11-26T14:21:00+00:00")) == (
        True, "manual_dispatch")
    # the on-time dispatcher starts nothing all day: no evening, no morning, no watch
    assert ds.slots_on(THANKSGIVING) == []
    clock = at("2026-11-26T00:00:00-05:00")
    while clock < at("2026-11-27T00:00:00-05:00"):
        assert ds.due(clock) == [], clock
        clock += timedelta(minutes=15)
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


def test_the_watch_judges_the_friday_morning_from_its_due_time(week):
    # before 8:45 AM Chicago the morning cannot be judged; Tuesday's receipt is still the one on disk
    early = watch(week, "thanksgiving", "2026-11-27T14:44:59+00:00")
    assert early["morning"]["judgement"] == sw.NOT_DUE and early["alert"] is False
    assert early["morning"]["due_at"] == "2026-11-27T08:45:00-06:00"
    # from then on a receipt bound to another publication is no morning check for this one
    stale = watch(week, "thanksgiving", "2026-11-27T14:45:00+00:00")
    assert stale["morning"]["judgement"] == sw.NOT_LANDED and stale["morning"]["alert"] is True
    assert "bound to another publication" in stale["morning"]["sentence"]
    # the check that ran at 8:22 AM Chicago is inside its collection window (from 9:00 AM ET)
    landed = watch(week, "friday-morning", "2026-11-27T14:45:00+00:00")
    assert landed["morning"]["judgement"] == sw.LANDED and landed["alert"] is False
    assert landed["morning"]["collection_starts_at"] == "2026-11-27T09:00:00-05:00"
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
    assert ds.slots_on(SATURDAY) == [] and ds.slots_on(SUNDAY) == []
    data = week.raw("friday")
    for clock in ("2026-11-28T14:21:00+00:00", "2026-11-29T14:21:00+00:00"):
        assert pm.schedule_guard(data, "schedule", MORNING_EST, at(clock)) == (False, "inactive_schedule")
        assert ds.due(at(clock)) == []
    for clock in ("2026-11-28T05:07:00+00:00", "2026-11-28T15:00:00+00:00", "2026-11-29T09:07:00+00:00",
                  "2026-11-29T23:00:00+00:00", "2026-11-30T08:00:00+00:00", "2026-11-30T14:44:59+00:00"):
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


def test_a_friday_that_was_never_published_is_flagged_before_mondays_open(week, guard_code):
    """Wednesday's record is still the one on main: Friday's session completed at 1:15 PM ET and may
    be published until Monday's open. The watch stays quiet through the weekend, flags it from six
    hours before that open, and calls it missing from the open on."""
    limit = at("2026-11-30T09:30:00-05:00")
    # six hours before Monday's open is 3:30 AM New York, written out so the bound itself is held
    quiet = ("2026-11-27T23:30:00+00:00", "2026-11-28T15:00:00+00:00", "2026-11-29T15:00:00+00:00",
             "2026-11-30T03:29:59-05:00")
    for clock in quiet:
        result = watch(week, "friday-morning", clock)
        assert result["evening"]["judgement"] == sw.OK and result["evening"]["alert"] is False, clock
        assert result["evening"]["next_session"] == "2026-11-27"
    near = watch(week, "friday-morning", "2026-11-30T03:30:00-05:00")
    assert near["evening"]["judgement"] == sw.LATE_NEAR_LIMIT and near["evening"]["alert"] is True
    assert near["evening"]["recovery_until"] == "2026-11-30T09:30:00-05:00"
    missing = watch(week, "friday-morning", limit.isoformat())
    assert missing["evening"]["judgement"] == sw.MISSING and missing["evening"]["alert"] is True
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
    ("2026-10-30", "22:20", "13:20", ["11:00", "13:45", "16:00"]),      # daylight time
    ("2026-11-02", "23:20", "14:20", ["12:00", "14:45", "17:00"]),      # standard time
    ("2027-03-12", "23:20", "14:20", ["12:00", "14:45", "17:00"]),
    ("2027-03-15", "22:20", "13:20", ["11:00", "13:45", "16:00"]),
    ("2026-11-27", "23:20", "14:20", ["12:00", "14:45", "17:00"]),      # the half day: no slot moves
    ("2026-11-30", "23:20", "14:20", ["12:00", "14:45", "17:00"]),      # the Monday after it
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
