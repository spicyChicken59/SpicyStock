"""The entry window as the run serializes it, and what it refuses to claim.

Every night here is pinned to an instant: a test whose answer depends on the
hour it runs is this repository's worst shape of unfailable test.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from src import clock, pipeline, plan, report, timing

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "docs" / "app.js"


@pytest.fixture
def full_record() -> dict:
    """The `full` fixture as the pipeline wrote it -- a green night with a
    ticket, read rather than hand-built, so a rule this module asserts is a
    rule the run actually applied."""
    return json.loads((ROOT / "tests" / "fixtures" / "page" / "full.json").read_text())

#: a Friday, its Monday, and the window that Monday schedules
FRI = date(2026, 9, 11)
MON = date(2026, 9, 14)


def block(measured: date = FRI, applicable: date = MON, minutes: int = 30, **kw) -> dict:
    return timing.plan_timing(measured, applicable, window=f"first {minutes} minutes",
                              window_minutes=minutes, **kw)


def at_et(day: date, hour: int, minute: int = 0) -> datetime:
    """An instant in market time, built the way the module does so the test is
    not asserting the offset it happens to be written under."""
    return timing.at(day, timing.time_of_day(hour, minute))


# ------------------------------------------------ the applicable session ----


def test_the_applicable_session_is_the_one_the_dated_schedule_calls_day_one():
    """The block and every plan's schedule name one date BY CONSTRUCTION: the
    pipeline asks plan.next_sessions() once and the schedule asks it again with
    the same session. If they ever came apart the page would print an entry
    window for one day beside an instruction dated another."""
    for session in (FRI, date(2026, 9, 14), date(2026, 9, 10), date(2026, 12, 31)):
        tm = pipeline.plan_timing(session, session, closed=False)
        day_one = plan.dated_schedule({"kind": "burst", "exits": []}, session)[0]
        assert tm["applicable_session"] == day_one["date"], session
        assert day_one["day"] == plan.ENTRY_DAY


def test_a_friday_night_plans_for_monday_and_not_for_saturday():
    tm = pipeline.plan_timing(FRI, FRI, closed=False)
    assert tm["applicable_session"] == "2026-09-14"
    assert tm["basis"] == timing.BASIS_EXCHANGE_AFTER
    assert tm["closed_session"] is None


def test_calendar_closure_cannot_be_inferred_on_an_expected_open_day():
    with pytest.raises(ValueError, match="expected-open"):
        pipeline.plan_timing(date(2026, 9, 9), date(2026, 9, 10), closed=True)
    tm = pipeline.plan_timing(date(2026, 9, 4), date(2026, 9, 7), closed=True)
    assert tm["applicable_session"] == "2026-09-08"
    assert tm["basis"] == timing.BASIS_EXCHANGE_AFTER


def test_a_plan_cannot_be_for_a_session_already_measured():
    with pytest.raises(ValueError, match="not after the measured one"):
        block(measured=MON, applicable=MON)
    with pytest.raises(ValueError, match="not after the measured one"):
        block(measured=MON, applicable=FRI)


def test_an_unknown_basis_is_refused_rather_than_written():
    with pytest.raises(ValueError, match="is not one of"):
        block(basis="whatever_the_caller_felt_like")


# ------------------------------------------------------- the instants -------


def test_the_window_is_the_bell_and_the_strategy_minutes_after_it():
    tm = block()
    assert tm["opens_at"] == "2026-09-14T09:30:00-04:00"
    assert tm["cutoff_at"] == "2026-09-14T10:00:00-04:00"
    assert tm["window_minutes"] == 30
    # and a different window moves the cutoff and nothing else
    wide = block(minutes=45)
    assert wide["opens_at"] == tm["opens_at"]
    assert wide["cutoff_at"] == "2026-09-14T10:15:00-04:00"
    assert wide["cutoff_et"] == "10:15"


def test_the_preparation_reminder_is_not_the_cutoff():
    """9:28 AM is the desk's own "be ready" and the page used to print it as a
    deadline at every hour of the day. It is its own field, two minutes before
    the bell, and the window runs half an hour PAST it."""
    tm = block()
    assert tm["prepare_by"] == "2026-09-14T09:28:00-04:00"
    assert tm["prepare_by"] < tm["opens_at"] < tm["cutoff_at"]
    assert timing.PREPARE_BEFORE_ET != timing.REGULAR_OPEN_ET
    # and being past it is not being past the window
    assert timing.phase(tm, at_et(MON, 9, 29)) == timing.PHASE_UPCOMING


def test_the_offsets_come_from_the_time_zone_database_and_not_from_this_repo():
    """A hardcoded -04:00 would be wrong for five months of the year and wrong
    for the session after every spring forward. December carries -05:00, the
    Monday after the 2026 change carries -04:00, and the Friday before it
    carries -05:00 -- three answers no constant here could give."""
    assert block(date(2026, 12, 10), date(2026, 12, 11))["opens_at"].endswith("-05:00")
    assert block(date(2026, 3, 6), date(2026, 3, 9))["opens_at"].endswith("-04:00")
    assert block(date(2026, 3, 5), date(2026, 3, 6))["opens_at"].endswith("-05:00")
    # the WALL CLOCK is the same on both sides: the bell does not move
    for tm in (block(date(2026, 12, 10), date(2026, 12, 11)), block(date(2026, 3, 6), date(2026, 3, 9))):
        assert tm["opens_at"][11:16] == "09:30" and tm["cutoff_at"][11:16] == "10:00"
        assert tm["opens_et"] == "09:30"


def test_the_zone_is_named_once_for_the_whole_repository():
    assert block()["timezone"] == clock.MARKET_TZ_NAME == "America/New_York"
    assert str(clock.MARKET_TZ) == clock.MARKET_TZ_NAME


def test_a_window_of_no_minutes_is_refused():
    for bad in (0, -30, 30.0, "30", None):
        with pytest.raises(ValueError, match="positive whole number"):
            timing.entry_window(MON, bad)


# ---------------------------------------------------------- the phases ------


def test_the_phase_at_every_boundary_of_the_window():
    tm = block()
    cases = [
        (at_et(MON, 0, 0), timing.PHASE_UPCOMING),
        (at_et(MON, 9, 29), timing.PHASE_UPCOMING),
        (at_et(MON, 9, 30), timing.PHASE_OPEN),        # the bell is inside
        (at_et(MON, 9, 59), timing.PHASE_OPEN),
        (at_et(MON, 10, 0), timing.PHASE_ENDED),       # the cutoff is NOT
        (at_et(MON, 11, 0), timing.PHASE_ENDED),
        (at_et(MON, 23, 59), timing.PHASE_ENDED),
        (at_et(FRI, 18, 0), timing.PHASE_UPCOMING),    # the evening it was published
    ]
    for when, want in cases:
        assert timing.phase(tm, when) == want, (when.isoformat(), want)
    # one second either side of the cutoff, so the boundary sits on a case
    assert timing.phase(tm, at_et(MON, 10, 0) - timedelta(seconds=1)) == timing.PHASE_OPEN
    assert timing.phase(tm, at_et(MON, 10, 0) + timedelta(seconds=1)) == timing.PHASE_ENDED


def test_a_weekend_is_before_the_window_and_never_inside_it():
    """Saturday and Sunday have no window of their own: a Friday night's plans
    are for Monday, and at ten o'clock on Sunday morning -- inside the clock
    time the window occupies -- they are still upcoming."""
    tm = block()
    for when in (at_et(date(2026, 9, 12), 9, 45), at_et(date(2026, 9, 13), 9, 45),
                 at_et(date(2026, 9, 13), 23, 0)):
        assert timing.phase(tm, when) == timing.PHASE_UPCOMING, when.isoformat()


def test_a_record_with_no_timing_block_is_unknown_and_never_guessed():
    for absent in (None, {}, {"opens_at": None}, "not an object", []):
        assert timing.phase(absent, at_et(MON, 9, 45)) == timing.PHASE_UNKNOWN


def test_an_instant_without_an_offset_is_refused_rather_than_read_locally():
    """Read in the reader's own zone, 09:30 is a different moment on every
    desk: a naive stamp is no answer at all."""
    tm = block()
    naive = dict(tm, opens_at="2026-09-14T09:30:00")
    assert timing.phase(naive, at_et(MON, 9, 45)) == timing.PHASE_UNKNOWN
    backwards = dict(tm, cutoff_at=tm["opens_at"])
    assert timing.phase(backwards, at_et(MON, 9, 45)) == timing.PHASE_UNKNOWN
    assert timing.phase(dict(tm, opens_at="the morning"), at_et(MON, 9, 45)) == timing.PHASE_UNKNOWN


# ------------------------------------------- the shape check in report ------


def test_an_absent_block_is_no_fault_and_a_broken_one_is_every_fault():
    """Absent is how every record published before this field existed reads,
    and the page answers "entry timing unavailable" for them. A block that IS
    there is held to its shape one level in."""
    assert report.timing_faults(None) == []
    good = block()
    assert report.timing_faults(good) == []
    for broken, says in (
        ({}, "applicable_session"),
        (dict(good, applicable_session="2026-09-11"), "not after its measured_session"),
        (dict(good, cutoff_at=good["opens_at"]), "no width"),
        (dict(good, opens_at="2026-09-15T09:30:00-04:00"), "not on its own applicable_session"),
        (dict(good, opens_at="2026-09-14T09:30:00"), "offset"),
        (dict(good, basis="invented"), "basis"),
        (dict(good, limits=["invented"]), "limits"),
        (dict(good, window_minutes="30"), "whole number of minutes"),
        ([1, 2, 3], "neither absent nor an object"),
        ("", "neither absent nor an object"),
    ):
        faults = report.timing_faults(broken)
        assert faults, broken
        assert any(says in f for f in faults), (says, faults)


def test_a_record_is_refused_when_its_window_has_no_width(full_record):
    """The whole file is refused, not repaired: a run that wrote a window
    backwards wrote something else wrong too."""
    bad = json.loads(json.dumps(full_record))
    bad["run"]["timing"]["cutoff_at"] = bad["run"]["timing"]["opens_at"]
    with pytest.raises(ValueError, match="no width"):
        report.validate(bad)


def test_the_run_writes_the_block_on_every_night_the_fixtures_hold():
    """Red, closed, degraded and quiet nights all carry it: which session a
    reader would act on is a fact about the record even when the record offers
    nothing to do."""
    seen = {}
    for path in sorted((ROOT / "tests" / "fixtures" / "page").glob("*.json")):
        data = json.loads(path.read_text())
        if path.name.startswith(".") or "picks" in data:       # the record's own picks file, not a docs/data.json
            continue
        tm = data["run"]["timing"]
        assert report.timing_faults(tm) == [], path.name
        assert tm["measured_session"] == data["run"]["session"], path.name
        seen[path.stem] = tm["basis"]
    # and both bases are actually exercised by the committed fixtures
    assert set(seen.values()) == {timing.BASIS_EXCHANGE_AFTER}, seen


# ------------------------------------------- the page reads the same words --


def test_the_page_names_a_sentence_for_every_limitation_the_run_can_write():
    """One list of limitation keys, two consumers. A key the run can write and
    the page has no sentence for would print nothing at all."""
    page = APP_JS.read_text()
    start = page.index("const TIMING_LIMITS = {")
    body = page[start:page.index("\n  };", start)]
    keys = set(re.findall(r"^    (\w+): '", body, re.M))
    assert keys == set(timing.LIMITS), (keys, timing.LIMITS)


def test_the_page_knows_the_same_four_phases_the_run_does():
    page = APP_JS.read_text()
    words = set(re.findall(r"(\w+): '[^']+'", re.search(r"const PHASE_WORDS = \{([^}]+)\}", page).group(1)))
    assert words == set(timing.PHASES), words


def test_the_window_the_record_archives_is_the_window_the_rules_archive(full_record):
    """`rules.plan.entry_window` is the phrase and `run.timing.window_minutes`
    is the number behind it: the phrase is written FROM the number, so a moved
    window moves both and the page cannot quote two lengths.

    Asserted against the LIVE constants as well as the committed fixture: a
    fixture was generated before any edit under test, so on its own it passes
    on an incidental fact about a file rather than on the rule."""
    live = pipeline.plan_timing(FRI, FRI, closed=False)
    assert plan.ENTRY_WINDOW == f"first {plan.ENTRY_WINDOW_MINUTES} minutes"
    assert live["window"] == plan.ENTRY_WINDOW
    assert live["window_minutes"] == plan.ENTRY_WINDOW_MINUTES
    assert (datetime.fromisoformat(live["cutoff_at"]) - datetime.fromisoformat(live["opens_at"])
            == timedelta(minutes=plan.ENTRY_WINDOW_MINUTES))
    rules, tm = full_record["rules"]["plan"], full_record["run"]["timing"]
    assert rules["entry_window"] == tm["window"] == f"first {rules['entry_window_minutes']} minutes"
    assert tm["window_minutes"] == rules["entry_window_minutes"] == plan.ENTRY_WINDOW_MINUTES
    opens = datetime.fromisoformat(tm["opens_at"])
    assert datetime.fromisoformat(tm["cutoff_at"]) - opens == timedelta(minutes=tm["window_minutes"])


class _Universe:
    """What `build_rules()` actually reads off a universe: its identity."""

    identity = "test-universe"


def test_the_archived_rules_carry_the_timing_constants_the_code_holds(full_record):
    """A record made under these constants must not read as one made before
    them: `timing.RULES` is nested into the archive and digested. Built HERE
    from the modules, not read off a fixture that was written earlier."""
    nested = pipeline.build_rules(_Universe())
    assert nested["timing"] == {k.split(".", 1)[1]: v for k, v in timing.RULES.items()}
    assert nested["timing"]["regular_open_et"] == "09:30"
    assert nested["timing"]["prepare_before_et"] == "09:28"
    assert nested["timing"]["limits"] == list(timing.LIMITS)
    assert nested["plan"]["entry_window_minutes"] == plan.ENTRY_WINDOW_MINUTES
    # and moving one of them moves the digest, which is the whole point of it
    moved = json.loads(json.dumps(nested))
    moved["timing"]["regular_open_et"] = "09:31"
    assert report.rules_version(moved) != report.rules_version(nested)
    # the fixture was written by this code, so it carries the same block
    assert full_record["rules"]["timing"] == nested["timing"]
    # The published record is rewritten by every evening run, so anything asserted
    # here about WHICH generation wrote it is an accident of the calendar. This
    # said `run.timing is None`, true only while run 47's record stood, and went
    # red the night a run first published one (`fbaed5c`, 2026-09-14) -- the first
    # shape CLAUDE.md names, and one that could not have failed for its own reason.
    # Nor can its digest be compared with the fixture's: they differ in
    # `universe.identity` alone, the real universe against the test double, so
    # that comparison passes for a reason that has nothing to do with timing.
    # What is true of EVERY record is that its archived rules digest to its own
    # recorded version -- which is what makes two records made under different
    # numbers unreadable as one.
    published = json.loads((ROOT / "docs" / "data.json").read_text())
    assert report.rules_version(published["rules"]) == published["app"]["rules_version"]
    # and a record carrying the timing block archived the timing constants it ran
    # under. The KEYS, not the values: a record published before a constant moved
    # is legitimately one generation behind the code until the next run.
    if published["run"].get("timing") is not None:
        assert set(published["rules"]["timing"]) == set(nested["timing"])
