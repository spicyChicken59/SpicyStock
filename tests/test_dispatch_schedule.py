"""The on-time dispatcher (tools/dispatch_schedule.py): which slots are due at
a frozen clock on the XNYS calendar, across EST and EDT, holidays and half
days; and that a tick starts each due slot once, repeats nothing, refuses to
run without its token and names a refused request by its status alone."""
from __future__ import annotations

import http.client
import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from src import sessions
from tools import dispatch_schedule as ds

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc
ET, CT = ZoneInfo("America/New_York"), ZoneInfo("America/Chicago")
TOKEN = "github_pat_test_only_not_a_real_token"


class FakeGitHub(ds.GitHub):
    """The two calls, answered from memory: a run is listed once dispatched."""

    def __init__(self, answers=None):
        super().__init__(TOKEN)
        self.calls: list[tuple[str, str, dict | None]] = []
        self.runs: dict[str, list[tuple[datetime, int]]] = {}
        self.answers = answers or {}
        self.next_id = 9000
        self.now = None

    def send(self, method, path, body=None):
        self.calls.append((method, path, body))
        workflow = re.search(r"/workflows/([^/]+)/", path).group(1)
        forced = self.answers.get((method, workflow))
        if forced:
            return forced, b""
        if method == "POST":
            self.next_id += 1
            self.runs.setdefault(workflow, []).append((self.now, self.next_id))
            return 204, b""
        since = datetime.strptime(re.search(r"created=%3E%3D([^&]+)", path).group(1).replace("%3A", ":"),
                                  "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        listed = [{"id": i, "created_at": at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}
                  for at, i in sorted(self.runs.get(workflow, []), reverse=True) if at >= since]
        return 200, json.dumps({"workflow_runs": listed}).encode()


def at(day: str, hhmm: str, zone=ET) -> datetime:
    return datetime.fromisoformat(f"{day}T{hhmm}:00").replace(tzinfo=zone)


# ------------------------------------------------------------- the slots ----
def test_a_session_has_ten_slots_in_their_own_zones():
    day = date(2026, 11, 20)                         # a Friday, EST
    assert sessions.is_session(day)
    slots = ds.slots_on(day)
    assert [(s.workflow, s.at.astimezone(UTC).strftime("%H:%M")) for s in slots] == [
        ("service-watch.yml", "12:00"), ("morning.yml", "14:20"), ("service-watch.yml", "14:25"),
        ("service-watch.yml", "15:05"), ("evening.yml", "23:20"), ("service-watch.yml", "00:00"),
        ("evening.yml", "00:20"), ("evening.yml", "01:20"), ("evening.yml", "02:20"), ("service-watch.yml", "02:50")]
    evening = [s for s in slots if s.workflow == "evening.yml"]
    assert all(dict(s.inputs) == {"only_if_unpublished": "true"} for s in evening)
    assert dict(next(s for s in slots if s.workflow == "morning.yml").inputs) == {"dry_run": "false"}
    assert all(dict(s.inputs) == {} for s in slots if s.workflow == "service-watch.yml")


def test_the_watch_slots_are_in_both_zones_wall_clocks():
    by_zone = {zone.key: times for workflow, _, zone, times in ds.SLOTS if workflow == "service-watch.yml"}
    assert by_zone == {"America/New_York": ("19:00", "21:50"), "America/Chicago": ("06:00", "08:25", "09:05")}
    assert ds.EVERY_DAY == frozenset({"evening.yml"})


@pytest.mark.parametrize("day, evening_utc, morning_utc, watch_utc", [
    ("2026-07-15", "22:20", "13:20", ["11:00", "13:25", "14:05", "23:00", "01:50"]),   # EDT / CDT
    ("2026-12-15", "23:20", "14:20", ["12:00", "14:25", "15:05", "00:00", "02:50"]),   # EST / CST
    ("2026-11-02", "23:20", "14:20", ["12:00", "14:25", "15:05", "00:00", "02:50"]),   # after the clocks moved back
    ("2026-10-30", "22:20", "13:20", ["11:00", "13:25", "14:05", "23:00", "01:50"]),   # the Friday before it
    ("2027-03-12", "23:20", "14:20", ["12:00", "14:25", "15:05", "00:00", "02:50"]),   # before they move forward
    ("2027-03-15", "22:20", "13:20", ["11:00", "13:25", "14:05", "23:00", "01:50"]),   # the Monday after
])
def test_the_local_times_hold_across_est_and_edt(day, evening_utc, morning_utc, watch_utc):
    slots = ds.slots_on(date.fromisoformat(day))
    first = lambda wf: next(s for s in slots if s.workflow == wf).at.astimezone(UTC).strftime("%H:%M")
    assert first("evening.yml") == evening_utc and first("morning.yml") == morning_utc
    assert [s.at.astimezone(UTC).strftime("%H:%M") for s in slots if s.workflow == "service-watch.yml"] == watch_utc
    allowed = {(w, zone.key, t) for w, _, zone, times in ds.SLOTS for t in times}
    assert all((s.workflow, s.at.tzinfo.key, s.at.strftime("%H:%M")) in allowed for s in slots)


@pytest.mark.parametrize("day", ["2026-11-26", "2026-12-25", "2026-11-21", "2026-11-22", "2027-01-01"])
def test_a_closed_day_has_the_evenings_recovery_slots_alone(day):
    """A weekend or a holiday keeps the four evening starts and nothing else: the evening's own guard publishes
    the newest completed session then only if it is still unpublished before its next open."""
    assert not sessions.is_session(date.fromisoformat(day))
    slots = ds.slots_on(date.fromisoformat(day))
    assert [(s.workflow, s.at.strftime("%H:%M")) for s in slots] == [
        ("evening.yml", "18:20"), ("evening.yml", "19:20"), ("evening.yml", "20:20"), ("evening.yml", "21:20")]
    assert all(dict(s.inputs) == {"only_if_unpublished": "true"} for s in slots)
    assert [s.key for s in ds.due(at(day, "18:25"))] == [f"evening.yml@{day}T18:20:00-05:00"]
    assert ds.due(at(day, "08:25", CT)) == [] and ds.due(at(day, "19:05")) == []


def test_a_half_day_keeps_every_slot():
    day = date(2026, 11, 27)                         # the day after Thanksgiving: 1:00 PM ET close
    opens, closes, early = sessions.hours(day)
    assert early and closes.hour == 13
    assert [s.workflow for s in ds.slots_on(day)].count("evening.yml") == 4
    assert [s.workflow for s in ds.slots_on(day)].count("service-watch.yml") == 5
    assert ds.slots_on(day)[0].at < ds.slots_on(day)[-1].at


@pytest.mark.parametrize("now, expected", [
    (at("2026-11-20", "18:19"), []),
    (at("2026-11-20", "18:20"), ["evening.yml@2026-11-20T18:20:00-05:00"]),
    (at("2026-11-20", "18:49"), ["evening.yml@2026-11-20T18:20:00-05:00"]),
    (at("2026-11-20", "18:50"), []),
    (at("2026-11-20", "19:05"), ["service-watch.yml@2026-11-20T19:00:00-05:00"]),
    (at("2026-11-20", "21:35"), ["evening.yml@2026-11-20T21:20:00-05:00"]),
    (at("2026-11-20", "21:49"), ["evening.yml@2026-11-20T21:20:00-05:00"]),
    (at("2026-11-20", "21:50"), ["service-watch.yml@2026-11-20T21:50:00-05:00"]),
    (at("2026-11-20", "08:20", CT), ["morning.yml@2026-11-20T08:20:00-06:00"]),
    (at("2026-11-20", "08:25", CT), ["morning.yml@2026-11-20T08:20:00-06:00", "service-watch.yml@2026-11-20T08:25:00-06:00"]),
    (at("2026-11-20", "08:29", CT), ["morning.yml@2026-11-20T08:20:00-06:00", "service-watch.yml@2026-11-20T08:25:00-06:00"]),
    (at("2026-11-20", "08:30", CT), ["morning.yml@2026-11-20T08:20:00-06:00"]),        # the open: the watch is not due
    (at("2026-11-20", "08:54", CT), []),
    (at("2026-11-20", "09:05", CT), ["service-watch.yml@2026-11-20T09:05:00-06:00"]),
    (at("2026-11-23", "00:05", CT), []),             # Monday just past midnight: Sunday's evening slots are over
    (at("2026-11-21", "18:21"), ["evening.yml@2026-11-21T18:20:00-05:00"]),      # Saturday: the recovery slot
])
def test_a_slot_is_due_from_its_instant_for_the_due_window(now, expected):
    assert [s.key for s in ds.due(now)] == expected


def test_the_pre_open_watch_slot_is_due_only_until_the_sessions_open():
    """BEFORE_OPEN: the 8:25 AM CT watch is due until the 8:30 AM CT open, in both seasons and on a half day, and
    every other slot keeps DUE_MINUTES."""
    assert ds.BEFORE_OPEN == frozenset({("service-watch.yml", "America/Chicago", "08:25")})
    for day in ("2026-11-20", "2026-07-15", "2026-11-27", "2027-03-15"):
        opens = sessions.hours(date.fromisoformat(day))[0]
        slots = ds.slots_on(date.fromisoformat(day))
        (pre,) = [s for s in slots if s.workflow == "service-watch.yml" and s.at.strftime("%H:%M") == "08:25"]
        assert pre.end == opens == at(day, "08:30", CT) and ds.slot_end("service-watch.yml", pre.at) == opens
        assert pre.due(opens - timedelta(seconds=1)) and not pre.due(opens)
        for other in slots:
            if other is not pre:
                assert other.end - other.at == timedelta(minutes=ds.DUE_MINUTES), other.key
    # a time that is no slot of the workflow keeps the plain window
    assert ds.slot_end("service-watch.yml", at("2026-11-20", "08:26", CT)) == at("2026-11-20", "08:56", CT)


def posted(gh) -> list[tuple[str, str]]:
    """(workflow, the fake's clock) of every dispatch the tool asked for, in order."""
    return [(path.split("/")[-2], when) for (method, path, _), when in zip(gh.calls, gh.clocks) if method == "POST"]


class ClockedGitHub(FakeGitHub):
    """FakeGitHub that remembers the clock each call was made at, and stamps a dispatch's ``created_at``
    ``stamp`` after the tick that asked for it, as GitHub does."""

    def __init__(self, answers=None, stamp=timedelta(0)):
        super().__init__(answers)
        self.clocks: list[str] = []
        self.stamp = stamp

    def send(self, method, path, body=None):
        self.clocks.append(self.now.astimezone(CT).strftime("%H:%M"))
        if method != "POST":
            return super().send(method, path, body)
        tick, self.now = self.now, self.now + self.stamp
        try:
            return super().send(method, path, body)
        finally:
            self.now = tick


def ticks(gh, start: str, end: str, state=None, day="2026-11-20", refused=False):
    """A tick every minute from ``start`` to ``end`` (both inclusive, Chicago), as the loop runs them; ``refused``
    when GitHub is set to refuse a request in them, and a tick may fail."""
    minute = at(day, start, CT)
    while minute <= at(day, end, CT):
        gh.now = minute
        code = ds.tick(minute, gh, state=state)
        assert code in ((ds.EXIT_OK, ds.EXIT_FAILED) if refused else (ds.EXIT_OK,))
        minute += timedelta(minutes=1)


class Refusing(ClockedGitHub):
    """ClockedGitHub that answers the dispatch of ``workflow`` with HTTP 502 until ``until`` (a Chicago HH:MM)."""

    def __init__(self, until: str, workflow="morning.yml", day="2026-11-20", stamp=timedelta(0)):
        super().__init__(stamp=stamp)
        self.workflow, self.until = workflow, at(day, until, CT)

    def send(self, method, path, body=None):
        if method == "POST" and f"/{self.workflow}/" in path and self.now < self.until:
            self.calls.append((method, path, body))
            self.clocks.append(self.now.astimezone(CT).strftime("%H:%M"))
            return 502, b""
        return super().send(method, path, body)


def dispatched(gh) -> list[tuple[str, str]]:
    """(workflow, the Chicago minute) of every dispatch GitHub accepted, in order of creation."""
    made = sorted((when, workflow) for workflow, runs in gh.runs.items() for when, _ in runs)
    return [(workflow, when.astimezone(CT).strftime("%H:%M")) for when, workflow in made]


def test_the_pre_open_watch_waits_wait_seconds_after_a_catch_up_morning_dispatch():
    """A catch-up at 8:25: the check is dispatched then, and the watch at the first tick WAIT_SECONDS later."""
    assert ds.WAIT_SECONDS == 150 and ds.WAITS_FOR == {"service-watch.yml": "morning.yml"}
    gh = ClockedGitHub()
    ticks(gh, "08:25", "08:31", state=ds._fresh_state())
    assert posted(gh) == [("morning.yml", "08:25"), ("service-watch.yml", "08:28")]


@pytest.mark.parametrize("state", [ds._fresh_state, lambda: None], ids=["ledger-in-memory", "no-ledger"])
def test_a_catch_up_stamped_seven_seconds_after_its_tick_still_starts_the_watch_at_the_third_tick(state):
    """The morning run's created_at is 8:25:07 AM CT, seven seconds after the 8:25 tick that dispatched it: at the
    8:28:00 tick it is 173 seconds old, past WAIT_SECONDS, and the watch is dispatched; at 8:27:00 it was 113
    seconds old, and the watch waited."""
    gh = ClockedGitHub(stamp=timedelta(seconds=7))
    memory = state()
    ticks(gh, "08:25", "08:31", state=memory)
    assert gh.runs["morning.yml"][0][0] == at("2026-11-20", "08:25", CT) + timedelta(seconds=7)
    assert posted(gh) == [("morning.yml", "08:25"), ("service-watch.yml", "08:28")]


@pytest.mark.parametrize("seconds,minute", [(29, "08:27"), (30, "08:27"), (31, "08:28")])
def test_the_wait_ends_at_exactly_wait_seconds(seconds, minute):
    """A morning dispatch someone made at 8:24 and ``seconds``: one stamped 8:24:30 is exactly WAIT_SECONDS old at
    the 8:27:00 tick, and the watch is dispatched there; a second later, it waits one tick more."""
    gh = ClockedGitHub()
    gh.runs["morning.yml"] = [(at("2026-11-20", "08:24", CT) + timedelta(seconds=seconds), 777)]
    ticks(gh, "08:25", "08:29")
    assert posted(gh) == [("service-watch.yml", minute)]
    assert at("2026-11-20", "08:27", CT) - gh.runs["morning.yml"][0][0] == timedelta(seconds=ds.WAIT_SECONDS + 30 - seconds)


def test_the_last_tick_is_the_one_whose_next_is_at_or_past_the_slots_end():
    (pre,) = [s for s in ds.slots_on(date(2026, 11, 20)) if s.key == "service-watch.yml@2026-11-20T08:25:00-06:00"]
    opens = at("2026-11-20", "08:30", CT)
    assert ds.TICK_SECONDS == 60 and pre.end == opens
    assert not ds.last_tick(pre, opens - timedelta(seconds=61))
    assert ds.last_tick(pre, opens - timedelta(seconds=60)) and ds.last_tick(pre, opens - timedelta(seconds=1))
    # a slot with the plain due window: its last tick is its thirtieth minute
    (after,) = [s for s in ds.slots_on(date(2026, 11, 20)) if s.key == "service-watch.yml@2026-11-20T09:05:00-06:00"]
    assert not ds.last_tick(after, at("2026-11-20", "09:33", CT)) and ds.last_tick(after, at("2026-11-20", "09:34", CT))


@pytest.mark.parametrize("until,expected", [
    # refused at 8:20 to 8:22 and accepted at 8:23: the watch waits WAIT_SECONDS after it, to 8:26
    ("08:23", [("morning.yml", "08:23"), ("service-watch.yml", "08:26")]),
    # refused through 8:25: at 8:25 the check's slot is due and nothing has started it, so the watch waits for it,
    # then for WAIT_SECONDS after it, and is dispatched at 8:29, the last tick before the open, whatever is left
    ("08:26", [("morning.yml", "08:26"), ("service-watch.yml", "08:29")]),
    ("08:27", [("morning.yml", "08:27"), ("service-watch.yml", "08:29")]),
    ("08:28", [("morning.yml", "08:28"), ("service-watch.yml", "08:29")]),
    # accepted at the last tick itself: the check first, then the watch, in one tick
    ("08:29", [("morning.yml", "08:29"), ("service-watch.yml", "08:29")]),
    # refused past the open: the watch goes at its last tick all the same, and judges a check that never started
    ("08:40", [("service-watch.yml", "08:29"), ("morning.yml", "08:40")]),
])
def test_a_morning_dispatch_refused_for_several_ticks_holds_the_watch_back_until_its_last_tick(until, expected, caplog):
    gh = Refusing(until)
    with caplog.at_level(logging.INFO, logger="spicystock.dispatch"):
        ticks(gh, "08:20", "08:45", state=ds._fresh_state(), refused=True)
    assert dispatched(gh) == expected
    assert [w for w, _ in dispatched(gh)].count("service-watch.yml") == 1            # once, never at or after the open
    if until >= "08:26":
        assert ("service-watch.yml@2026-11-20T08:25:00-06:00 waits: morning.yml is due since "
                "2026-11-20T08:20:00-06:00 and has not been dispatched yet") in caplog.text
    if until == "08:26":
        assert ("service-watch.yml@2026-11-20T08:25:00-06:00 waits: morning.yml was dispatched at "
                "2026-11-20T08:26:00-06:00, less than 150 seconds ago") in caplog.text
    assert TOKEN not in caplog.text


@pytest.mark.parametrize("back,stamp,watch", [
    ("08:26", 40, "08:29"),          # stamped 8:26:40: 140 seconds old at 8:29:00, the last tick
    ("08:27", 3, "08:29"),
    ("08:28", 3, "08:29"),           # a catch-up at 8:28: the watch a minute later
    ("08:29", 3, "08:29"),           # and at 8:29: both in the last tick
])
def test_a_catch_up_that_leaves_less_than_wait_seconds_before_the_open_starts_the_watch_at_its_last_tick(back, stamp,
                                                                                                        watch):
    """The dispatcher comes back at ``back``: the check is dispatched then, and the watch is never left to the 9:05
    slot while a tick is made in its last minute."""
    gh = ClockedGitHub(stamp=timedelta(seconds=stamp))
    memory = ds._fresh_state()
    ticks(gh, back, "08:35", state=memory)
    assert posted(gh) == [("morning.yml", back), ("service-watch.yml", watch)]
    ticks(gh, "09:05", "09:06", state=memory)
    assert posted(gh)[2:] == [("service-watch.yml", "09:05")]


def test_a_dispatcher_that_made_no_tick_in_the_pre_open_slot_leaves_it_unstarted():
    """Back at 8:30, the open: the pre-open slot is no longer due and is never dispatched; the 9:05 slot is next."""
    gh = ClockedGitHub()
    memory = ds._fresh_state()
    ticks(gh, "08:30", "09:06", state=memory)
    assert posted(gh) == [("morning.yml", "08:30"), ("service-watch.yml", "09:05")]


def test_the_watch_does_not_wait_for_a_check_whose_slot_is_over_or_already_started(monkeypatch):
    """The wait for an unstarted check is while its slot is due: a watch slot after it does not wait for a check
    nothing will start, and one whose check the ledger already holds as started does not wait on an empty listing."""
    monkeypatch.setattr(ds, "SLOTS", (("morning.yml", {"dry_run": "false"}, CT, ("08:20",)),
                                      ("service-watch.yml", {}, CT, ("08:51",))))
    gh = ClockedGitHub()
    ticks(gh, "08:51", "08:52", state=ds._fresh_state())            # 8:20 + 30 minutes is past: the check is not due
    assert posted(gh) == [("service-watch.yml", "08:51")]
    monkeypatch.undo()

    class Unlisted(ClockedGitHub):
        def send(self, method, path, body=None):
            status, raw = super().send(method, path, body)
            if method == "GET" and "/morning.yml/" in path:
                raw = json.dumps({"workflow_runs": []}).encode()
            return status, raw
    gh = Unlisted()
    memory = ds._fresh_state()
    memory["started"]["morning.yml@2026-11-20T08:20:00-06:00"] = 777       # seen started on an earlier tick
    ticks(gh, "08:25", "08:26", state=memory)
    assert posted(gh) == [("service-watch.yml", "08:25")]


#: an ordinary Friday, the half day after Thanksgiving, and the sessions either side of both clock changes
LAST_TICK_DAYS = ["2026-11-20", "2026-11-27", "2026-10-30", "2026-11-02", "2027-03-12", "2027-03-15"]


def listed_watch_runs(gh) -> list[dict]:
    """The watch runs the fake holds, as ``GitHub.runs()`` would list them to the service watch."""
    return [{"id": run_id, "event": "workflow_dispatch", "display_title": "Service watch (manual)",
             "created_at": when.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "status": "completed",
             "conclusion": "success", "head_branch": "main", "run_attempt": 1}
            for when, run_id in gh.runs.get("service-watch.yml", [])]


@pytest.mark.parametrize("day", LAST_TICK_DAYS)
@pytest.mark.parametrize("back,started", [("08:28", True), ("08:29", True), ("08:30", False)])
def test_a_watch_dispatched_at_its_last_tick_is_on_time_for_the_watch_that_judges_it(day, back, started):
    """A catch-up at 8:28 or 8:29 AM CT: the pre-open watch is dispatched at 8:29, GitHub stamps it three seconds
    later, and the 9:05 watch reads it as a dispatch in its slot, on every kind of day. With no tick before the
    open there is no such run, and only then is the slot not started."""
    from tools import service_watch as sw
    assert sessions.is_session(date.fromisoformat(day))
    opens = sessions.hours(date.fromisoformat(day))[0]
    assert opens == at(day, "08:30", CT)                                   # 9:30 AM ET, in either season
    gh = ClockedGitHub(stamp=timedelta(seconds=3))
    ticks(gh, back, "08:35", state=ds._fresh_state(), day=day)
    watches = [(w, m) for w, m in posted(gh) if w == "service-watch.yml"]
    assert watches == ([("service-watch.yml", "08:29")] if started else [])
    slot = at(day, "08:25", CT)
    now = at(day, "09:07", CT)
    assert sw.previous_watch_slot(at(day, "08:31", CT)) == slot
    out = sw.judge_watch(at(day, "08:31", CT), listed_watch_runs(gh), None)
    assert sw._instant(out["slot_at"]) == slot
    if started:
        assert gh.runs["service-watch.yml"][0][0] == at(day, "08:29", CT) + timedelta(seconds=3) < opens
        assert (out["judgement"], out["key"], out["alert"]) == (sw.ON_TIME, None, False)
        assert "scheduler:watch:not_started" in sw.clears_of({"scheduler": {"watch": out}, "alerts": []})
    else:
        assert (out["judgement"], out["key"], out["alert"]) == (sw.NOT_STARTED, "scheduler:watch:not_started", True)
        assert f"No watch was dispatched in its slot at {slot.isoformat()}" in out["sentence"]
    assert now > opens


def test_the_wait_is_read_off_the_listing_when_the_ledger_does_not_hold_the_dispatch():
    """A restart with no ledger: the morning dispatch the tool made is read off GitHub's listing, by its own
    created_at; one whose instant cannot be read holds the watch back as if just made."""
    gh = ClockedGitHub()
    gh.runs["morning.yml"] = [(at("2026-11-20", "08:24", CT), 777)]          # anyone's dispatch, listed
    ticks(gh, "08:25", "08:29")
    assert posted(gh) == [("service-watch.yml", "08:27")]

    class Undated(ClockedGitHub):
        def send(self, method, path, body=None):
            status, raw = super().send(method, path, body)
            if method == "GET" and "/morning.yml/" in path:
                answer = json.loads(raw)
                for row in answer["workflow_runs"]:
                    row.pop("created_at")
                raw = json.dumps(answer).encode()
            return status, raw
    gh = Undated()
    gh.runs["morning.yml"] = [(at("2026-11-20", "08:21", CT), 778)]
    ticks(gh, "08:25", "08:28")
    assert posted(gh) == []
    ticks(gh, "08:29", "08:31")                         # the last tick before the open does not wait
    assert posted(gh) == [("service-watch.yml", "08:29")]


def test_a_morning_check_someone_else_started_on_time_does_not_hold_the_watch_back():
    gh = ClockedGitHub()
    gh.runs["morning.yml"] = [(at("2026-11-20", "08:21", CT), 777)]
    ticks(gh, "08:25", "08:26")
    assert posted(gh) == [("service-watch.yml", "08:25")]


def test_the_wait_asks_github_nothing_for_a_watch_slot_far_from_the_morning():
    """The 9:05 AM CT and evening watch slots are past the morning slot's due window and the wait after it: they
    ask GitHub nothing about the morning check."""
    for when, zone in (("09:05", CT), ("19:00", ET), ("21:50", ET)):
        gh = FakeGitHub()
        gh.now = at("2026-11-20", when, zone)
        assert ds.tick(gh.now, gh) == ds.EXIT_OK
        assert not [path for _, path, _ in gh.calls if "/morning.yml/" in path], when


def test_the_loop_keeps_its_ledger_in_memory_so_a_dispatch_not_yet_listed_is_not_made_twice():
    """GitHub lists a dispatch minutes late: with the ledger the loop holds, the check is dispatched once and the
    watch still waits WAIT_SECONDS after it; without one, each tick would read no run and dispatch again."""
    class Lagging(ClockedGitHub):
        def send(self, method, path, body=None):
            status, raw = super().send(method, path, body)
            if method == "GET" and self.now < at("2026-11-20", "08:40", CT):
                raw = json.dumps({"workflow_runs": []}).encode()            # nothing listed yet
            return status, raw
    gh = Lagging()
    memory = ds._fresh_state()
    ticks(gh, "08:25", "08:31", state=memory)
    assert posted(gh) == [("morning.yml", "08:25"), ("service-watch.yml", "08:28")]
    assert set(memory["dispatched"]) == {"morning.yml@2026-11-20T08:20:00-06:00",
                                         "service-watch.yml@2026-11-20T08:25:00-06:00"}
    # the same lag without a ledger: the morning check is dispatched again on every tick, as it was before
    gh = Lagging()
    ticks(gh, "08:25", "08:27")
    assert [w for w, _ in posted(gh)].count("morning.yml") == 3


@pytest.mark.parametrize("raises", [http.client.IncompleteRead(b"cut"), http.client.BadStatusLine("garbled"),
                                    http.client.RemoteDisconnected("closed"), ConnectionResetError(), TimeoutError()])
def test_a_transport_fault_is_a_failed_slot_named_by_its_type_and_never_stops_the_tick(raises, caplog):
    class Faulty(FakeGitHub):
        def send(self, method, path, body=None):
            if "/evening.yml/" in path:
                raise raises
            return super().send(method, path, body)
    gh = Faulty()
    gh.now = at("2026-11-20", "19:21")                           # the evening's second slot and the 7:00 PM watch
    with caplog.at_level(logging.INFO, logger="spicystock.dispatch"):
        assert ds.tick(gh.now, gh) == ds.EXIT_FAILED
    assert f"evening.yml@2026-11-20T19:20:00-05:00 not started: {type(raises).__name__}" in caplog.text
    assert [c[1].split("/")[-2] for c in gh.calls if c[0] == "POST"] == ["service-watch.yml"]   # the rest ran
    assert TOKEN not in caplog.text


def test_a_clock_without_an_offset_is_refused():
    with pytest.raises(ds.Refused):
        ds.due(datetime(2026, 11, 20, 18, 20))


# -------------------------------------------------------------- the tick ----
def test_a_tick_starts_a_due_slot_and_logs_its_run_id(caplog):
    gh = FakeGitHub()
    gh.now = at("2026-11-20", "18:21")
    with caplog.at_level(logging.INFO, logger="spicystock.dispatch"):
        assert ds.tick(gh.now, gh) == ds.EXIT_OK
    posts = [c for c in gh.calls if c[0] == "POST"]
    assert posts == [("POST", "/repos/spicyChicken59/SpicyStock/actions/workflows/evening.yml/dispatches",
                      {"ref": "main", "inputs": {"only_if_unpublished": "true"}})]
    assert "evening.yml@2026-11-20T18:20:00-05:00 dispatched: run 9001" in caplog.text
    assert TOKEN not in caplog.text and "Bearer" not in caplog.text


def test_repeat_ticks_start_a_slot_once_with_or_without_a_ledger(tmp_path):
    gh = FakeGitHub()
    gh.now = at("2026-11-20", "18:21")
    state = tmp_path / "ledger.json"
    for minute in ("18:21", "18:22", "18:40"):
        assert ds.tick(at("2026-11-20", minute), gh, state) == ds.EXIT_OK
    assert sum(1 for c in gh.calls if c[0] == "POST") == 1
    ledger = json.loads(state.read_text())
    assert ledger["started"] == {"evening.yml@2026-11-20T18:20:00-05:00": 9001}
    # a restart with no ledger reads GitHub's own runs and starts nothing twice
    assert ds.tick(at("2026-11-20", "18:45"), gh, None) == ds.EXIT_OK
    assert sum(1 for c in gh.calls if c[0] == "POST") == 1
    # the next hour's slot is its own
    gh.now = at("2026-11-20", "19:20")
    assert ds.tick(gh.now, gh, state) == ds.EXIT_OK
    evenings = [c for c in gh.calls if c[0] == "POST" and "/evening.yml/" in c[1]]
    assert len(evenings) == 2
    # the 7:00 PM watch slot is still due at 7:20: started once with it
    assert sum(1 for c in gh.calls if c[0] == "POST" and "/service-watch.yml/" in c[1]) == 1


def test_with_a_ledger_a_started_slot_asks_github_nothing_again(tmp_path):
    gh = FakeGitHub()
    gh.now = at("2026-11-20", "18:21")
    state = tmp_path / "ledger.json"
    assert ds.tick(gh.now, gh, state) == ds.EXIT_OK
    asked = len(gh.calls)
    assert ds.tick(at("2026-11-20", "18:30"), gh, state) == ds.EXIT_OK
    assert len(gh.calls) == asked            # the ledger answered; no listing, no dispatch


def test_only_a_dispatched_run_counts_as_the_slots_own():
    gh = FakeGitHub()
    gh.now = at("2026-11-20", "18:21")
    ds.tick(gh.now, gh)
    listings = [path for method, path, _ in gh.calls if method == "GET"]
    assert listings and all("event=workflow_dispatch" in path for path in listings)


def test_a_slot_late_in_the_evening_is_still_due_after_local_midnight(monkeypatch):
    # in Chicago, the later of the two zones: just past its midnight, every local date is the new day
    monkeypatch.setattr(ds, "SLOTS", (("service-watch.yml", {}, CT, ("23:50",)),))
    after_midnight = datetime(2026, 11, 21, 0, 5, tzinfo=CT)
    assert {after_midnight.astimezone(z).date() for z in (ET, CT)} == {date(2026, 11, 21)}
    assert [s.key for s in ds.due(after_midnight)] == ["service-watch.yml@2026-11-20T23:50:00-06:00"]


def test_a_run_someone_else_started_after_the_slot_counts_as_started():
    gh = FakeGitHub()
    gh.runs["morning.yml"] = [(at("2026-11-20", "08:21", CT), 777)]
    assert ds.tick(at("2026-11-20", "08:24", CT), gh) == ds.EXIT_OK
    assert not [c for c in gh.calls if c[0] == "POST"]


@pytest.mark.parametrize("status", [401, 403, 404, 422, 500])
def test_a_refused_dispatch_is_named_by_its_status_and_the_tick_fails(status, caplog):
    gh = FakeGitHub({("POST", "evening.yml"): status})
    gh.now = at("2026-11-20", "18:21")
    with caplog.at_level(logging.INFO, logger="spicystock.dispatch"):
        assert ds.tick(gh.now, gh) == ds.EXIT_FAILED
    assert f"evening.yml@2026-11-20T18:20:00-05:00 not started: dispatching evening.yml: HTTP {status}" in caplog.text
    assert TOKEN not in caplog.text
    # one attempt a tick: the next tick tries again, nothing retries in between
    assert sum(1 for c in gh.calls if c[0] == "POST") == 1


@pytest.mark.parametrize("status", [401, 404, 422])
def test_a_refused_listing_starts_nothing(status, caplog):
    gh = FakeGitHub({("GET", "evening.yml"): status})
    with caplog.at_level(logging.INFO, logger="spicystock.dispatch"):
        assert ds.tick(at("2026-11-20", "18:21"), gh) == ds.EXIT_FAILED
    assert not [c for c in gh.calls if c[0] == "POST"]
    assert f"listing evening.yml runs: HTTP {status}" in caplog.text


def test_no_token_is_refused_before_any_request(capsys):
    assert ds.main(["tick", "--now", "2026-11-20T18:21:00-05:00"], env={}) == ds.EXIT_REFUSED
    assert ds.main(["tick", "--now", "2026-11-20T18:21:00-05:00"], env={"GITHUB_TOKEN": "  "}) == ds.EXIT_REFUSED


def test_the_plan_command_needs_no_token(capsys):
    assert ds.main(["plan", "--day", "2026-11-20"], env={}) == ds.EXIT_OK
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 10 and out[4].startswith("2026-11-20T18:20:00-05:00  evening.yml")
    assert ds.main(["plan", "--day", "2026-11-21"], env={}) == ds.EXIT_OK            # Saturday
    assert [line.split()[1] for line in capsys.readouterr().out.splitlines()] == ["evening.yml"] * 4


def test_a_tick_on_a_closed_day_starts_the_evenings_guarded_recovery_and_nothing_else():
    gh = FakeGitHub()
    gh.now = at("2026-11-21", "18:21")                # Saturday
    assert ds.tick(gh.now, gh) == ds.EXIT_OK
    assert [c for c in gh.calls if c[0] == "POST"] == [
        ("POST", "/repos/spicyChicken59/SpicyStock/actions/workflows/evening.yml/dispatches",
         {"ref": "main", "inputs": {"only_if_unpublished": "true"}})]
    gh = FakeGitHub()
    assert ds.tick(at("2026-11-21", "08:25", CT), gh) == ds.EXIT_OK and gh.calls == []


# ------------------------------------------------------- the run listing ----
class ListingGitHub(ds.GitHub):
    """One canned answer to GET .../runs, recorded."""

    def __init__(self, status=200, answer=None, raw=None):
        super().__init__(TOKEN)
        self.status, self.answer, self.raw, self.calls = status, answer, raw, []

    def send(self, method, path, body=None):
        self.calls.append((method, path, body))
        return self.status, self.raw if self.raw is not None else json.dumps(self.answer).encode()


def listed(**fields):
    out = {"id": 1, "event": "workflow_dispatch", "display_title": "Morning publication", "created_at": "2026-11-20T14:20:05Z",
           "status": "completed", "conclusion": "success", "head_branch": "main", "run_attempt": 1,
           "actor": {"login": "someone"}, "head_commit": {"message": "x"}, "html_url": "https://example.invalid/run/1"}
    out.update(fields)
    return out


def test_the_run_listing_asks_for_main_since_an_instant_and_keeps_only_its_fields():
    gh = ListingGitHub(answer={"total_count": 1, "workflow_runs": [listed()]})
    runs = gh.runs("morning.yml", at("2026-11-20", "08:00", CT))
    (method, path, body), = gh.calls
    assert method == "GET" and body is None
    assert path.startswith("/repos/spicyChicken59/SpicyStock/actions/workflows/morning.yml/runs?")
    assert "branch=main" in path and f"per_page={ds.LIST_PAGE}" in path and "created=%3E%3D2026-11-20T14%3A00%3A00Z" in path
    assert "event=" not in path                       # every event: crons and dispatches alike
    assert runs == [{name: listed()[name] for name in ds.RUN_FIELDS}]
    assert set(runs[0]) == set(ds.RUN_FIELDS) and "actor" not in runs[0]


@pytest.mark.parametrize("answer", [
    {"total_count": ds.LIST_PAGE, "workflow_runs": [listed(id=i) for i in range(1, ds.LIST_PAGE + 1)]},   # a full page
    {"total_count": 3, "workflow_runs": [listed()]},                                                     # more than listed
    {"workflow_runs": [listed()]},                                                                       # no count
    {"total_count": 1, "workflow_runs": [listed(id=True)]},
    {"total_count": 1, "workflow_runs": [listed(created_at="2026-11-20 14:20")]},
    {"total_count": 1, "workflow_runs": [listed(run_attempt=0)]},
    {"total_count": 1, "workflow_runs": [listed(conclusion=7)]},
    {"total_count": 1, "workflow_runs": [listed(head_branch=7)]},
    {"total_count": 1, "workflow_runs": [listed(display_title=None)]},
    {"total_count": 1, "workflow_runs": [listed(event=None)]},
    {"total_count": 1, "workflow_runs": [listed(status=3)]},
    {"total_count": -1, "workflow_runs": []},
    {"total_count": True, "workflow_runs": []},
    {"total_count": 1, "workflow_runs": ["a run"]},
    {"total_count": 1, "workflow_runs": {"id": 1}},
    [],
])
def test_a_listing_that_is_not_the_whole_of_it_is_refused_never_read_as_no_run(answer):
    with pytest.raises(ds.Incomplete):
        ListingGitHub(answer=answer).runs("evening.yml", at("2026-11-20", "18:00"))
    with pytest.raises(ds.Incomplete):
        ListingGitHub(raw=b"{not json").runs("evening.yml", at("2026-11-20", "18:00"))


@pytest.mark.parametrize("status", [401, 403, 404, 500])
def test_a_refused_listing_is_named_by_its_status(status):
    with pytest.raises(ds.HTTPFailure, match=f"listing evening.yml runs: HTTP {status}"):
        ListingGitHub(status=status, answer={}).runs("evening.yml", at("2026-11-20", "18:00"))


def test_an_empty_listing_is_no_run_and_a_clock_without_an_offset_is_refused():
    assert ListingGitHub(answer={"total_count": 0, "workflow_runs": []}).runs("evening.yml", at("2026-11-20", "18:00")) == []
    with pytest.raises(ds.Refused):
        ListingGitHub(answer={}).runs("evening.yml", datetime(2026, 11, 20, 18, 0))


def test_the_dispatched_inputs_are_inputs_the_workflows_declare():
    import yaml
    for workflow, inputs, _, _ in ds.SLOTS:
        declared = yaml.safe_load((ROOT / ".github" / "workflows" / workflow).read_text())
        on = declared.get("on") or declared.get(True)
        assert set(inputs) <= set((on["workflow_dispatch"] or {}).get("inputs") or {}), workflow
