"""What a record says about the next publication, and the five answers a
reader's own clock gives. Every instant is pinned: the wall clock is never
read. The fixture calendar is written by hand (the 1 November 2026 clock
change, Thanksgiving and the early close after it), so the module is not
compared against the calendar code that would have produced it; two more
tests then hold it to that code and to the delivery module."""
from __future__ import annotations

import copy
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from src import delivery, freshness, morning, sessions

ET = ZoneInfo("America/New_York")
SECOND = timedelta(seconds=1)
POLICY = {"timezone": "America/New_York", "primary_et": "18:16", "retry_et": "20:16",
          "recovery_until": "next_session_open"}


def row(day: str, offset: str, close: str = "16:00", done: str = "16:15") -> dict:
    return {"session": day, "opens_at": f"{day}T09:30:00{offset}", "closes_at": f"{day}T{close}:00{offset}",
            "completion_at": f"{day}T{done}:00{offset}", "shortened": close != "16:00"}


#: Hand-written. Sunday 1 November 2026 ends daylight time (-04:00 before it,
#: -05:00 after); Thursday 26 November is Thanksgiving (no session); Friday
#: 27 November closes at 1:00 PM, so it completes at 1:15 PM.
CALENDAR = [row("2026-10-28", "-04:00"), row("2026-10-29", "-04:00"), row("2026-10-30", "-04:00"),
            row("2026-11-02", "-05:00"), row("2026-11-03", "-05:00"), row("2026-11-04", "-05:00"),
            row("2026-11-24", "-05:00"), row("2026-11-25", "-05:00"),
            row("2026-11-27", "-05:00", close="13:00", done="13:15"),
            row("2026-11-30", "-05:00"), row("2026-12-01", "-05:00")]


def record(session: str, *, policy=POLICY, rows=None, expected_session=None) -> dict:
    rows = CALENDAR if rows is None else rows
    run = {"session": session,
           "calendar": {"schedule": {"start": rows[0]["session"] if rows else None,
                                     "through": rows[-1]["session"] if rows else None, "sessions": rows}}}
    if expected_session is not None:
        run["expected_session"] = expected_session
    if policy is not None:
        run["delivery"] = {"policy": dict(policy)}
    return {"run": run}


def at(text: str) -> datetime:
    return datetime.fromisoformat(text)


# ------------------------------------------------------------------ expected()
def test_an_ordinary_night_names_the_next_session_its_slots_and_the_open_after_it():
    out = freshness.expected(record("2026-10-28"))
    assert out == {"version": 1, "covers_through": "2026-10-28", "next_session": "2026-10-29",
                   "completion_at": "2026-10-29T16:15:00-04:00", "primary_slot_at": "2026-10-29T18:16:00-04:00",
                   "retry_slot_at": "2026-10-29T20:16:00-04:00", "recovery_until": "2026-10-30T09:30:00-04:00",
                   "timezone": "America/New_York",
                   "policy": {"primary_et": "18:16", "retry_et": "20:16", "recovery_until": "next_session_open"},
                   "unknown": {}}


def test_the_clock_change_is_the_time_zones_answer_and_not_the_records_last_offset():
    # Friday 30 October, still on daylight time: the next session is Monday 2 November, on standard time
    out = freshness.expected(record("2026-10-30"))
    assert out["next_session"] == "2026-11-02"
    assert out["completion_at"] == "2026-11-02T16:15:00-05:00"
    assert (out["primary_slot_at"], out["retry_slot_at"]) == ("2026-11-02T18:16:00-05:00", "2026-11-02T20:16:00-05:00")
    assert out["recovery_until"] == "2026-11-03T09:30:00-05:00"
    # 6:16 PM ET is 23:16 UTC after the change and was 22:16 UTC before it
    assert at(out["primary_slot_at"]).astimezone(timezone.utc).hour == 23
    before = freshness.expected(record("2026-10-28"))
    assert at(before["primary_slot_at"]).astimezone(timezone.utc).hour == 22
    # Thursday 29 October: slots before the change, a recovery limit after it
    across = freshness.expected(record("2026-10-29"))
    assert across["primary_slot_at"] == "2026-10-30T18:16:00-04:00" and across["recovery_until"] == "2026-11-02T09:30:00-05:00"


def test_a_holiday_is_skipped_and_an_early_close_completes_early():
    out = freshness.expected(record("2026-11-25"))                    # the Wednesday before Thanksgiving
    assert out["next_session"] == "2026-11-27"                        # not Thursday the 26th
    assert out["completion_at"] == "2026-11-27T13:15:00-05:00"        # the 1:00 PM close plus the buffer
    assert out["primary_slot_at"] == "2026-11-27T18:16:00-05:00"      # the slots do not move with the close
    assert out["recovery_until"] == "2026-11-30T09:30:00-05:00"       # Monday's open, across the weekend
    assert out["unknown"] == {}


def test_a_closed_night_answers_for_the_day_nobody_traded():
    # the run measured the 25th again on the holiday: it covers the 26th, and the next session is still the 27th
    out = freshness.expected(record("2026-11-25", expected_session="2026-11-26"))
    assert out["covers_through"] == "2026-11-26" and out["next_session"] == "2026-11-27"
    assert out["recovery_until"] == "2026-11-30T09:30:00-05:00"


@pytest.mark.parametrize("change, fields, reason", [
    (lambda r: r["run"].pop("session"), freshness.EXPECTED_FIELDS, "the record names no session"),
    (lambda r: r["run"].pop("calendar"), freshness.EXPECTED_FIELDS,
     "the record carries no readable exchange schedule (run.calendar.schedule)"),
    (lambda r: r["run"]["calendar"]["schedule"]["sessions"][3].pop("completion_at"), freshness.EXPECTED_FIELDS,
     "the record carries no readable exchange schedule (run.calendar.schedule)"),
    (lambda r: r["run"]["calendar"]["schedule"]["sessions"][0].update(opens_at="2026-10-28T09:30:00"),
     freshness.EXPECTED_FIELDS, "the record carries no readable exchange schedule (run.calendar.schedule)"),
    (lambda r: r["run"].update(session="2026-12-02"), freshness.EXPECTED_FIELDS,
     "the record's exchange schedule does not cover its own session"),
    (lambda r: r["run"].update(session="2026-12-01"), freshness.EXPECTED_FIELDS,
     "the record's exchange schedule ends before the next session"),
    (lambda r: r["run"].pop("delivery"), ("primary_slot_at", "retry_slot_at"),
     "this record does not carry the evening service's schedule (run.delivery.policy)"),
    (lambda r: r["run"]["delivery"]["policy"].update(primary_et="6:16 PM"), ("primary_slot_at", "retry_slot_at"),
     "the record's delivery policy does not give two slot times and a time zone this code can read"),
    (lambda r: r["run"]["delivery"]["policy"].update(timezone="Mars/Olympus"), ("primary_slot_at", "retry_slot_at"),
     "the record's delivery policy does not give two slot times and a time zone this code can read"),
    (lambda r: r["run"]["delivery"]["policy"].update(primary_et="20:16", retry_et="18:16"),
     ("primary_slot_at", "retry_slot_at"),
     "the record's delivery policy does not give two slot times and a time zone this code can read"),
    (lambda r: r["run"]["delivery"]["policy"].update(recovery_until="end_of_week"), ("recovery_until",),
     "the record's delivery policy names a recovery rule this code does not know"),
    (lambda r: r["run"].update(session="2026-11-30"), ("recovery_until",),
     "the record's exchange schedule ends before the session after the next"),
])
def test_what_the_record_cannot_say_is_null_with_its_reason_and_never_guessed(change, fields, reason):
    rec = copy.deepcopy(record("2026-10-28"))
    change(rec)
    out = freshness.expected(rec)
    assert {name: out["unknown"].get(name) for name in fields} == {name: reason for name in fields}
    assert all(out[name] is None for name in fields)
    # every field is either given or explained, never both and never neither
    assert all((out[name] is None) == (name in out["unknown"]) for name in freshness.EXPECTED_FIELDS)
    json.dumps(out, allow_nan=False)


def test_a_schedule_whose_instants_are_out_of_order_answers_nothing():
    rows = copy.deepcopy(CALENDAR)
    rows[2]["opens_at"] = "2026-10-29T10:00:00-04:00"      # the session after the next "opens" before the next completes
    out = freshness.expected(record("2026-10-28", rows=rows))
    assert all(out[name] is None for name in freshness.EXPECTED_FIELDS)
    assert set(out["unknown"].values()) == {"the record's schedule instants are not in order"}
    assert freshness.state(out, at("2026-10-29T12:00:00-04:00"))["state"] == freshness.UNKNOWN


# --------------------------------------------------------------------- state()
BLOCK = freshness.expected(record("2026-10-30"))      # across the clock change: every boundary is at -05:00
BOUNDARIES = [("completion_at", freshness.NEWEST, freshness.NOT_DUE),
              ("primary_slot_at", freshness.NOT_DUE, freshness.PENDING),
              ("retry_slot_at", freshness.PENDING, freshness.LATE),
              ("recovery_until", freshness.LATE, freshness.MISSING)]


@pytest.mark.parametrize("name, before, after", BOUNDARIES)
def test_each_boundary_one_second_either_side_and_exactly_on_it(name, before, after):
    edge = at(BLOCK[name])
    assert freshness.state(BLOCK, edge - SECOND)["state"] == before
    assert freshness.state(BLOCK, edge)["state"] == after           # an instant exactly at a boundary has passed it
    assert freshness.state(BLOCK, edge + SECOND)["state"] == after


def test_the_five_answers_in_order_each_with_one_sentence():
    clocks = ["2026-10-30T21:00:00-04:00", "2026-11-02T17:00:00-05:00", "2026-11-02T19:00:00-05:00",
              "2026-11-02T23:00:00-05:00", "2026-11-03T12:00:00-05:00"]
    answers = [freshness.state(BLOCK, at(clock)) for clock in clocks]
    assert tuple(a["state"] for a in answers) == freshness.STATES
    assert all(isinstance(a["sentence"], str) and a["sentence"].endswith(".") for a in answers)
    assert "2026-11-02T16:15:00-05:00" in answers[0]["sentence"]     # each names the instant it turns on
    assert "2026-11-02T18:16:00-05:00" in answers[1]["sentence"]
    assert "2026-11-02T20:16:00-05:00" in answers[2]["sentence"]
    assert "2026-11-03T09:30:00-05:00" in answers[3]["sentence"]
    # missing is conditional: the record cannot know whether a newer file exists
    assert "If this is still the newest file the site serves" in answers[4]["sentence"]
    assert "expired" in answers[4]["sentence"]


def test_the_readers_clock_may_be_in_any_zone_and_must_carry_one():
    edge = at(BLOCK["primary_slot_at"])
    assert freshness.state(BLOCK, edge.astimezone(timezone.utc))["state"] == freshness.PENDING
    assert freshness.state(BLOCK, (edge - SECOND).astimezone(ZoneInfo("America/Chicago")))["state"] == freshness.NOT_DUE
    with pytest.raises(ValueError, match="instant with an offset"):
        freshness.state(BLOCK, datetime(2026, 11, 2, 19, 0))            # naive: refused, never assumed UTC
    with pytest.raises(ValueError):
        freshness.state(BLOCK, "2026-11-02T19:00:00-05:00")


def test_a_record_from_before_the_schedule_names_no_slot_and_still_reads_its_window():
    block = freshness.expected(record("2026-10-30", policy=None))
    assert block["primary_slot_at"] is None and block["recovery_until"] == "2026-11-03T09:30:00-05:00"
    assert freshness.state(block, at("2026-11-02T12:00:00-05:00"))["state"] == freshness.NEWEST
    pending = freshness.state(block, at("2026-11-02T23:59:00-05:00"))
    assert pending["state"] == freshness.PENDING and "no slot is named" in pending["sentence"]
    edge = at(block["recovery_until"])
    assert freshness.state(block, edge - SECOND)["state"] == freshness.PENDING
    assert freshness.state(block, edge)["state"] == freshness.MISSING


def test_a_missing_instant_is_unknown_and_never_read_as_newest():
    nothing = freshness.expected({"run": {"session": "2026-10-30"}})
    out = freshness.state(nothing, at("2026-11-02T12:00:00-05:00"))
    assert out["state"] == freshness.UNKNOWN and "research only" in out["sentence"]
    assert "no readable exchange schedule" in out["sentence"]
    # the slots are known and the recovery limit is not: the early steps still answer, the late ones do not guess
    partial = freshness.expected(record("2026-11-30"))
    assert partial["recovery_until"] is None and partial["retry_slot_at"] is not None
    assert freshness.state(partial, at("2026-12-01T19:00:00-05:00"))["state"] == freshness.PENDING
    assert freshness.state(partial, at("2026-12-01T21:00:00-05:00"))["state"] == freshness.UNKNOWN
    assert freshness.state({}, at("2026-12-01T21:00:00-05:00"))["state"] == freshness.UNKNOWN


def test_the_rule_text_names_every_field_and_every_state_it_uses():
    text = " ".join(freshness.RULE)
    for name in ("completion_at", "primary_slot_at", "retry_slot_at", "recovery_until"):
        assert f"`{name}`" in text
    assert [f"`{word}`" in text for word in freshness.STATES] == [True] * 5
    assert text.index("`newest`") < text.index("`not_due`") < text.index("`pending`") < text.index("`late`") \
        < text.index("`missing`")
    assert "no clock" in freshness.RULE[0]


# ------------------------------------------------------------- morning_window()
def test_the_morning_window_is_the_records_timing_and_collection_starts_half_an_hour_before():
    rec = {"run": {"timing": {"applicable_session": "2026-11-02", "timezone": "America/New_York",
                              "opens_at": "2026-11-02T09:30:00-05:00", "cutoff_at": "2026-11-02T10:00:00-05:00",
                              "prepare_by": "2026-11-02T09:28:00-05:00", "closes_at": "2026-11-02T16:00:00-05:00"}}}
    assert freshness.morning_window(rec) == {
        "applicable_session": "2026-11-02", "window_opens_at": "2026-11-02T09:30:00-05:00",
        "window_cutoff_at": "2026-11-02T10:00:00-05:00", "prepare_by": "2026-11-02T09:28:00-05:00",
        "session_closes_at": "2026-11-02T16:00:00-05:00", "timezone": "America/New_York",
        "collection_starts_at": "2026-11-02T09:00:00-05:00", "collection_starts_minutes_before_open": 30,
        "unknown": None}
    assert freshness.morning_window({"run": {}})["unknown"] == "this record carries no entry-window timing (run.timing)"
    half = copy.deepcopy(rec)
    half["run"]["timing"].pop("cutoff_at")
    out = freshness.morning_window(half)
    assert out["unknown"] == "the record's entry-window timing is not complete" and out["window_cutoff_at"] is None


# ------------------------------------------------- held to the modules it mirrors
def test_the_constants_are_the_modules_own():
    assert freshness.PREOPEN_MINUTES == morning.POLICY["preopen_minutes"]
    assert freshness.RECOVERY_NEXT_OPEN == delivery.RECOVERY_NEXT_OPEN
    assert POLICY["primary_et"] == delivery.EVENING_PRIMARY_ET.isoformat(timespec="minutes")
    assert POLICY["retry_et"] == delivery.EVENING_RETRY_ET.isoformat(timespec="minutes")


@pytest.mark.parametrize("day", ["2026-10-28", "2026-10-30", "2026-11-25"])
def test_the_slots_and_the_calendar_are_what_the_service_itself_computes(day):
    out = freshness.expected(record(day))
    following = date.fromisoformat(out["next_session"])
    assert sessions.next_sessions(date.fromisoformat(day), 2)[0] == following       # the hand-written calendar is XNYS's
    primary, retry = delivery.slots(following)
    assert (at(out["primary_slot_at"]), at(out["retry_slot_at"])) == (primary, retry)
    assert at(out["completion_at"]) == sessions.completion_at(following)
    assert at(out["recovery_until"]) == sessions.hours(sessions.next_sessions(date.fromisoformat(day), 2)[1])[0]


def test_a_real_record_reads_as_the_run_wrote_it():
    rec = json.loads((Path(__file__).parent / "fixtures" / "page" / "full.json").read_text())
    out = freshness.expected(rec)
    assert out["unknown"] == {} and out["covers_through"] == rec["run"]["session"] == "2026-09-10"
    assert out["next_session"] == rec["run"]["delivery"]["next_session"] == "2026-09-11"
    # the record's own recovery window for ITS session ends where the brief's "newest" boundary is still ahead
    assert at(rec["run"]["delivery"]["next_open_at"]) < at(out["completion_at"])
    window = freshness.morning_window(rec)
    assert window["applicable_session"] == rec["run"]["timing"]["applicable_session"]
    assert at(window["collection_starts_at"]) == at(rec["run"]["timing"]["opens_at"]) - timedelta(minutes=30)


def test_the_module_reads_no_clock_and_imports_only_the_standard_library():
    source = Path(freshness.__file__).read_text()
    assert "datetime.now" not in source and "time.time" not in source and "utcnow" not in source
    imports = [line for line in source.splitlines() if line.startswith(("import ", "from "))]
    assert imports == ["from __future__ import annotations",
                       "from datetime import date, datetime, time as time_of_day, timedelta",
                       "from zoneinfo import ZoneInfo"]
