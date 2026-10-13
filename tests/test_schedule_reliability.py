"""tools/schedule_reliability.py: when GitHub created each scheduled run against its slot.

Every instant here is hand-computed from the calendar, never read off the tool:
the crons are the workflows' own, the dates are the real October 2026 week
(Friday the 9th, Monday the 12th), and the delays are minutes from a slot to a
creation instant written out beside it. The committed reading is held to its
snapshot, and the snapshot's cron tables to the workflow files git carries.
"""
from __future__ import annotations

import copy
import math
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import schedule_reliability as sr  # noqa: E402

UTC = timezone.utc
EVENING = ".github/workflows/evening.yml"
MORNING = ".github/workflows/morning.yml"
SCAN = ".github/workflows/secret-scan.yml"
EVENING_CRONS = ["16 22 * * 1-5", "16 23 * * 1-5", "16 0 * * 2-6", "16 1 * * 2-6"]


def at(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


def run(rid: int, path: str, created: str, title: str = "Secret scan", **kw) -> dict:
    out = {"id": rid, "path": path, "event": "schedule", "display_title": title, "created_at": created,
           "status": "completed", "conclusion": "success", "head_sha": "a" * 40, "head_branch": "main",
           "run_attempt": 1}
    out.update(kw)
    return out


def push(rid: int, created: str, committed: str, path: str = ".github/workflows/tests.yml") -> dict:
    return {"id": rid, "path": path, "created_at": created, "head_sha": "b" * 40, "committed_at": committed}


def version(effective: str, crons: list[str], commit: str = "c" * 40) -> dict:
    return {"commit": commit, "effective_at": effective, "crons": crons}


def snap(runs, tables, pushes=(), fetched="2026-10-13T18:00:00+00:00") -> dict:
    return {"version": sr.VERSION, "repository": "o/r", "fetched_at": fetched, "source": "test",
            "ref": "origin/main", "ref_commit": "d" * 40, "total_count": len(runs),
            "push_total_count": len(pushes), "tables": tables, "runs": list(runs), "push_runs": list(pushes)}


def valid() -> dict:
    tables = {SCAN: [version("2026-09-01T23:16:19+00:00", ["0 6 * * 1"])],
              EVENING: [version("2026-09-11T11:45:04+00:00", EVENING_CRONS)]}
    runs = [run(1, SCAN, "2026-10-12T13:50:02Z"),
            run(2, EVENING, "2026-10-13T03:01:38Z", "Evening cron 16 22 * * 1-5")]
    return snap(runs, tables, [push(9, "2026-10-13T16:14:10Z", "2026-10-13T16:14:06Z")])


# ------------------------------------------------------------------ crons ----

def test_a_cron_is_read_only_in_the_shape_these_workflows_write():
    c = sr.parse_cron("16 22 * * 1-5")
    assert (c["minute"], c["hour"], c["days"], c["text"]) == (16, 22, [1, 2, 3, 4, 5], "16 22 * * 1-5")
    assert sr.parse_cron("37  7 * * *")["days"] is None and sr.parse_cron("37  7 * * *")["text"] == "37 7 * * *"
    assert sr.parse_cron("0 6 * * 0,7")["days"] == [0]      # 7 is Sunday too
    assert sr.parse_cron("16 0 * * 2-6")["days"] == [2, 3, 4, 5, 6]
    for bad in ("16 22 1 * *", "16 22 * 1 *", "x 22 * * *", "60 1 * * *", "1 24 * * *", "1 2 * * 8",
                "1 2 * * 5-1", "1 2 * *", "1 2 * * a", "*/5 1 * * *", 5, None):
        with pytest.raises(sr.ScheduleError):
            sr.parse_cron(bad)


def test_the_latest_instant_a_cron_names_at_or_before_a_moment():
    weekday = sr.parse_cron("16 22 * * 1-5")
    # Saturday 03:00 belongs to Friday's 22:16; the weekend names nothing
    assert sr.latest_at_or_before(weekday, at("2026-10-10T03:00:00")) == at("2026-10-09T22:16:00")
    # Monday 21:00, before Monday's slot: Friday's, across the weekend
    assert sr.latest_at_or_before(weekday, at("2026-10-12T21:00:00")) == at("2026-10-09T22:16:00")
    # the instant itself, and one second before it
    assert sr.latest_at_or_before(weekday, at("2026-10-13T22:16:00")) == at("2026-10-13T22:16:00")
    assert sr.latest_at_or_before(weekday, at("2026-10-13T22:15:59")) == at("2026-10-12T22:16:00")
    # the retry cron fires Tuesday to Saturday: Monday morning belongs to Saturday's
    assert sr.latest_at_or_before(sr.parse_cron("16 0 * * 2-6"), at("2026-10-12T05:00:00")) == at("2026-10-10T00:16:00")
    weekly = sr.parse_cron("0 6 * * 1")
    assert sr.latest_at_or_before(weekly, at("2026-10-12T13:50:02")) == at("2026-10-12T06:00:00")
    assert sr.latest_at_or_before(weekly, at("2026-10-11T23:00:00")) == at("2026-10-05T06:00:00")


def test_firings_are_every_instant_in_a_half_open_window():
    retry = sr.parse_cron("16 0 * * 2-6")
    got = sr.firings(retry, at("2026-10-11T00:00:00"), at("2026-10-18T00:00:00"))
    assert got == [at(f"2026-10-{d}T00:16:00") for d in (13, 14, 15, 16, 17)]
    # the start is included when it is an instant, the end never is
    assert sr.firings(retry, at("2026-10-13T00:16:00"), at("2026-10-14T00:16:00")) == [at("2026-10-13T00:16:00")]


def test_a_run_names_its_cron_however_the_workflow_spelled_the_name():
    for title, cron in (("Evening cron 16 22 * * 1-5", "16 22 * * 1-5"),
                        ("Evening cron 16 22 * * 1-5, the EDT slot", "16 22 * * 1-5"),
                        ("Morning cron 30 13 * * 1-5, the EST slot", "30 13 * * 1-5"),
                        ("Source recovery cron 37 7 * * *", "37 7 * * *"),
                        ("Source recovery cron 37  7 * * *", "37 7 * * *"),     # the event's spelling of the file
                        ("Evening cron 16 22 * * 1-5 (EDT)", "16 22 * * 1-5"),
                        ("X cron 1 2 * * 1,3,5", "1 2 * * 1,3,5")):
        assert sr.name_cron(title)["text"] == cron, title
    for title in ("Secret scan", "Evening scan (6:16 PM ET)", "Morning observation (best effort)", "Evening dispatch",
                  "Microcrons"):
        assert sr.name_cron(title) is None, title
    # a name that says cron and names none the reading can place is refused, never read as no cron
    for title in ("Evening cron", "Evening cron 16 22 * *", "Evening cron 16 22 1 * 1-5"):
        with pytest.raises(sr.ScheduleError):
            sr.name_cron(title)


# ------------------------------------------------------------ attribution ----

def test_a_run_is_attributed_to_the_cron_its_name_records_not_the_nearest_slot():
    versions = [version("2026-09-11T11:45:04+00:00", EVENING_CRONS)]
    # the 12 October primary, created at 03:01:38 on the 13th: 4 h 45 m 38 s = 285.6 minutes
    a = sr.attribute(run(1, EVENING, "2026-10-13T03:01:38Z", "Evening cron 16 22 * * 1-5"), versions)
    assert (a["slot"], a["delay_minutes"], a["basis"], a["cron"]) == ("2026-10-12T22:16:00+00:00", 285.6, "run_name", "16 22 * * 1-5")
    # the same instant with no cron in its name is the nearest preceding slot of any cron in force: 01:16
    b = sr.attribute(run(2, EVENING, "2026-10-13T03:01:38Z", "Evening dispatch"), versions)
    assert (b["slot"], b["delay_minutes"], b["basis"]) == ("2026-10-13T01:16:00+00:00", 105.6, "nearest_slot")


def test_a_run_without_a_cron_name_reads_each_table_while_it_was_in_force():
    versions = [version("2026-09-01T23:16:19+00:00", ["0 6 * * 1"])]
    a = sr.attribute(run(1, SCAN, "2026-10-12T13:50:02Z"), versions)
    assert (a["slot"], a["delay_minutes"], a["delay_seconds"], a["basis"]) == \
        ("2026-10-12T06:00:00+00:00", 470.0, 28202.0, "nearest_slot")
    with pytest.raises(sr.ScheduleError, match="no cron in its name"):
        sr.attribute(run(1, SCAN, "2026-08-31T13:50:02Z"), versions)    # before the table took effect
    # the table emptied at 10:00, after the 06:00 slot and before the run was created: the slot is still 06:00,
    # the one expected() names, not a refusal
    emptied = versions + [version("2026-10-12T10:00:00+00:00", [])]
    assert sr.attribute(run(1, SCAN, "2026-10-12T13:50:02Z"), emptied)["slot"] == "2026-10-12T06:00:00+00:00"
    assert sr.expected(emptied, at("2026-10-12T00:00:00"), at("2026-10-13T00:00:00")) == [("0 6 * * 1", at("2026-10-12T06:00:00"))]
    # moved to 07:00 at 10:00: the run is the 06:00 slot's, and the 07:00 cron names nothing before 10:00
    moved = versions + [version("2026-10-12T10:00:00+00:00", ["0 7 * * 1"])]
    assert sr.attribute(run(1, SCAN, "2026-10-12T13:50:02Z"), moved)["slot"] == "2026-10-12T06:00:00+00:00"
    # a table in force since before the run, with nothing named after its own start, refuses
    with pytest.raises(sr.ScheduleError, match="no cron in its name"):
        sr.attribute(run(1, SCAN, "2026-10-12T13:50:02Z"), [version("2026-10-12T07:00:00+00:00", ["0 6 * * 1"])])


# --------------------------------------------------------------- expected ----

def test_expected_slots_follow_each_table_version_while_it_was_in_force():
    versions = [version("2026-09-01T23:16:19+00:00", ["30 12 * * 1-5"]),
                version("2026-09-11T11:45:04+00:00", []),
                version("2026-10-12T13:20:00+00:00", ["20 13 * * 1-5"])]
    got = sr.expected(versions, at("2026-09-10T00:00:00"), at("2026-10-14T00:00:00"))
    # 10 Sep 12:30 under the first table; 11 Sep 12:30 falls after the table was emptied at 11:45;
    # the third table names its own instant at the moment it took effect, then Tuesday's
    assert got == [("30 12 * * 1-5", at("2026-09-10T12:30:00")),
                   ("20 13 * * 1-5", at("2026-10-12T13:20:00")),
                   ("20 13 * * 1-5", at("2026-10-13T13:20:00"))]


def test_a_slot_with_no_run_is_named_after_a_day_and_unstarted_before():
    versions = [version("2026-10-12T00:00:00+00:00", ["20 13 * * 1-5"])]
    runs = [run(1, MORNING, "2026-10-12T21:44:56Z", "Morning cron 20 13 * * 1-5"),
            run(2, MORNING, "2026-10-13T09:00:06Z", "Morning cron 45 2 * * 1-5")]     # 375.1
    w = sr.workflow_reading(MORNING, runs, versions, at("2026-10-14T13:20:01"))
    assert w["expected"] == 3
    assert w["no_run"] == [{"cron": "20 13 * * 1-5", "slot": "2026-10-13T13:20:00+00:00"}]          # 24 h 0 m 1 s
    assert w["not_started"] == [{"cron": "20 13 * * 1-5", "slot": "2026-10-14T13:20:00+00:00"}]     # 1 s
    assert w["unexpected"] == [{"id": 2, "cron": "45 2 * * 1-5", "slot": "2026-10-13T02:45:00+00:00"}]
    # 12 Oct 13:20 to 21:44:56 is 8 h 24 m 56 s = 504.9 minutes
    assert w["runs"][0]["delay_minutes"] == 504.9 and w["beyond"] == {"15": 2, "60": 2, "240": 2, "360": 2}
    assert w["delay_minutes"] == {"n": 2, "min": 375.1, "median": 440.0, "max": 504.9}
    assert w["weeks"] == [{"week": "2026-10-12", "n": 2, "min": 375.1, "median": 440.0, "max": 504.9}]
    # exactly a day after the slot is a day
    assert sr.workflow_reading(MORNING, runs[:1], versions, at("2026-10-14T13:20:00"))["no_run"] == \
        [{"cron": "20 13 * * 1-5", "slot": "2026-10-13T13:20:00+00:00"}]


def test_two_runs_placed_at_one_slot_are_listed_so_a_misplacement_shows():
    # the first build's hourly pair: a 22:16 run 64 minutes late, named without its cron, lands on 23:16
    versions = [version("2026-09-01T00:00:00+00:00", ["16 22 * * 1-5", "16 23 * * 1-5"])]
    runs = [run(1, EVENING, "2026-09-02T23:20:00Z", "Evening scan"), run(2, EVENING, "2026-09-02T23:25:00Z", "Evening scan")]
    w = sr.workflow_reading(EVENING, runs, versions, at("2026-09-03T00:00:00"))
    assert w["shared"] == [{"cron": "16 23 * * 1-5", "slot": "2026-09-02T23:16:00+00:00", "ids": [1, 2]}]
    assert sr.workflow_reading(EVENING, runs[:1], versions, at("2026-09-03T00:00:00"))["shared"] == []


def test_every_threshold_reads_seconds_never_the_rounded_minutes():
    versions = [version("2026-09-01T00:00:00+00:00", ["16 22 * * 1-5"])]
    # 60 minutes 2 seconds late displays as 60.0 and is still later than an hour
    late = run(1, EVENING, "2026-09-02T23:16:02Z", "Evening cron 16 22 * * 1-5")
    w = sr.workflow_reading(EVENING, [late], versions, at("2026-09-03T00:00:00"))
    assert w["runs"][0]["delay_minutes"] == 60.0 and w["beyond"]["60"] == 1
    result = sr.build(snap([late], {EVENING: versions}, fetched="2026-09-03T00:00:00+00:00"))
    assert result["change"]["first_late"]["delay_minutes"] == 60.0
    # 15 minutes 2 seconds is not prompt
    slow = run(2, EVENING, "2026-09-01T22:31:02Z", "Evening cron 16 22 * * 1-5")
    assert sr.build(snap([slow, late], {EVENING: versions}, fetched="2026-09-03T00:00:00+00:00"))["change"]["last_prompt_before"] is None
    # the spread rounds once: the median of 60:00 and 60:06 is 60:03, 60.05 minutes, and reads 60.0 or 60.1 by
    # the seconds, never the mean of two rounded values
    assert sr._spread([3600.0, 3606.0]) == {"n": 2, "min": 60.0, "median": round(3603.0 / 60, 1), "max": 60.1}


def test_a_workflow_whose_cron_never_fired_is_read_and_named():
    versions = [version("2026-10-13T16:13:00+00:00", ["37 7 * * *", "37 9 * * *"])]
    w = sr.workflow_reading(".github/workflows/source-recovery.yml", [], versions, at("2026-10-15T08:00:00"))
    assert w["runs"] == [] and w["delay_minutes"] is None and w["expected"] == 3
    assert [r["slot"] for r in w["no_run"]] == ["2026-10-14T07:37:00+00:00"]
    assert [r["slot"] for r in w["not_started"]] == ["2026-10-14T09:37:00+00:00", "2026-10-15T07:37:00+00:00"]


# ----------------------------------------------------------------- change ----

def test_the_change_is_the_first_late_run_in_slot_order_and_the_last_prompt_before_it():
    tables = {SCAN: [version("2026-09-01T00:00:00+00:00", ["0 6 * * 1"])],
              EVENING: [version("2026-09-01T00:00:00+00:00", ["16 22 * * 1-5"])]}
    runs = [run(1, EVENING, "2026-09-18T22:31:00Z", "Evening cron 16 22 * * 1-5"),    # 15.0: prompt, the boundary
            run(2, SCAN, "2026-09-21T06:04:19Z"),                                    # 4.3: the last prompt before
            run(3, EVENING, "2026-09-22T00:48:12Z", "Evening cron 16 22 * * 1-5"),    # 152.2: the first late
            run(4, EVENING, "2026-09-22T23:16:00Z", "Evening cron 16 22 * * 1-5"),    # 60.0: not beyond 60
            run(5, SCAN, "2026-09-28T06:10:00Z")]                                    # 10.0: prompt again
    result = sr.build(snap(runs, tables, fetched="2026-09-29T00:00:00+00:00"))
    c = result["change"]
    assert c["first_late"] == {"path": EVENING, "cron": "16 22 * * 1-5", "slot": "2026-09-21T22:16:00+00:00",
                               "created_at": "2026-09-22T00:48:12+00:00", "delay_minutes": 152.2}
    assert c["last_prompt_before"]["path"] == SCAN and c["last_prompt_before"]["delay_minutes"] == 4.3
    assert c["since"] == {"delay_minutes": {"n": 3, "min": 10.0, "median": 60.0, "max": 152.2}, "prompt": 1,
                          "beyond": {"15": 2, "60": 1, "240": 0, "360": 0}}
    # the workflow's own counts: 15.0 and 60.0 are not beyond 15 and 60
    assert result["workflows"][EVENING]["beyond"] == {"15": 2, "60": 1, "240": 0, "360": 0}
    # a run exactly an hour late is not the change
    assert sr.build(snap(runs[:2] + runs[3:4], tables, fetched="2026-09-29T00:00:00+00:00"))["change"] is None
    # a run exactly fifteen minutes late is prompt, and can be the last prompt run before the change
    only = sr.build(snap([runs[0], runs[2]], tables, fetched="2026-09-29T00:00:00+00:00"))["change"]
    assert only["last_prompt_before"]["delay_minutes"] == 15.0 and only["since"]["prompt"] == 0


def test_the_change_is_read_in_slot_order_never_in_creation_order():
    tables = {SCAN: [version("2026-09-01T00:00:00+00:00", ["0 6 * * 1"])],
              MORNING: [version("2026-09-01T00:00:00+00:00", ["0 8 * * 1"])]}
    # the 06:00 slot was created at 12:40, after the 08:00 slot's run at 09:30: both late,
    # and the earlier slot is the change though its run was created second
    runs = [run(1, MORNING, "2026-09-21T09:30:00Z", "Morning cron 0 8 * * 1"),     # 90.0
            run(2, SCAN, "2026-09-21T12:40:00Z")]                                 # 400.0
    c = sr.build(snap(runs, tables, fetched="2026-09-22T00:00:00+00:00"))["change"]
    assert (c["first_late"]["path"], c["first_late"]["slot"], c["first_late"]["delay_minutes"]) == \
        (SCAN, "2026-09-21T06:00:00+00:00", 400.0)


def test_the_contrast_is_each_push_runs_creation_after_its_commit():
    tables = {SCAN: [version("2026-09-01T00:00:00+00:00", ["0 6 * * 1"])]}
    runs = [run(1, SCAN, "2026-09-21T06:04:19Z"), run(2, SCAN, "2026-09-28T12:18:18Z")]   # 378.3 late
    pushes = [push(10, "2026-09-20T10:00:30Z", "2026-09-20T10:00:00Z"),       # 0.5, before the change
              push(11, "2026-09-28T06:00:00Z", "2026-09-28T05:59:54Z"),       # 0.1, at the change's slot
              push(12, "2026-10-01T10:20:06Z", "2026-10-01T10:00:00Z")]       # 20.1, a commit pushed later
    k = sr.build(snap(runs, tables, pushes, fetched="2026-10-02T00:00:00+00:00"))["contrast"]
    assert k["all"] == {"n": 3, "min": 0.1, "median": 0.5, "max": 20.1}
    assert k["since_change"] == {"n": 2, "min": 0.1, "median": 10.1, "max": 20.1}
    assert k["within_prompt_since_change"] == 1
    no_change = sr.build(snap(runs[:1], tables, pushes, fetched="2026-10-02T00:00:00+00:00"))["contrast"]
    assert no_change["since_change"] is None and no_change["within_prompt_since_change"] is None


# -------------------------------------------------------------- validate ----

def _break(field):
    def apply(s):
        field(s)
        return s
    return apply


REFUSALS = {
    "an older version": lambda s: s.update(version=0),
    "a missing ref": lambda s: s.update(ref_commit=""),
    "a count that is not the listing": lambda s: s.update(total_count=3),
    "a push count that is not the listing": lambda s: s.update(push_total_count=2),
    "an extra run field": lambda s: s["runs"][0].update(url="x"),
    "a missing run field": lambda s: s["runs"][0].pop("conclusion"),
    "a boolean id": lambda s: s["runs"][0].update(id=True),
    "a repeated id": lambda s: s["runs"][1].update(id=1),
    "a push id a scheduled run has": lambda s: s["push_runs"][0].update(id=1),
    "a push event": lambda s: s["runs"][0].update(event="push"),
    "a workflow without a table": lambda s: s["runs"][0].update(path=".github/workflows/x.yml"),
    "no run name": lambda s: s["runs"][0].update(display_title=None),
    "a run after the snapshot": lambda s: s["runs"][0].update(created_at="2026-10-13T18:00:01Z"),
    "an instant without an offset": lambda s: s["runs"][0].update(created_at="2026-10-12T13:50:02"),
    "an extra push field": lambda s: s["push_runs"][0].update(event="push"),
    "a push without a commit time": lambda s: s["push_runs"][0].update(committed_at=None),
    "a push after the snapshot": lambda s: s["push_runs"][0].update(created_at="2026-10-14T00:00:00Z"),
    "an empty table": lambda s: s["tables"].update({SCAN: []}),
    "a table version with an extra key": lambda s: s["tables"][SCAN][0].update(note="x"),
    "a table that is not a list of crons": lambda s: s["tables"][SCAN][0].update(crons="0 6 * * 1"),
    "a cron the reading cannot place": lambda s: s["tables"][SCAN][0].update(crons=["0 6 1 * *"]),
    "table versions out of order": lambda s: s["tables"][EVENING].append(version("2026-09-01T00:00:00+00:00", [])),
}


@pytest.mark.parametrize("name", sorted(REFUSALS))
def test_a_snapshot_the_reading_cannot_index_is_refused_whole(name):
    s = valid()
    sr.validate(copy.deepcopy(s))
    REFUSALS[name](s)
    with pytest.raises(sr.ScheduleError):
        sr.validate(s)


# ------------------------------------------------------------------ fetch ----

def _page(runs, total):
    return {"total_count": total, "workflow_runs": runs}


def _api_run(rid, path, created, title):
    return {**run(rid, path, created, title), "url": "https://example", "run_started_at": created, "actor": {"login": "x"}}


def test_fetch_pages_both_listings_keeps_only_the_named_fields_and_reads_the_tables(monkeypatch):
    asked = []
    scheduled = [_api_run(3, SCAN, "2026-10-12T13:50:02Z", "Secret scan"),
                 _api_run(1, SCAN, "2026-10-05T12:58:02Z", "Secret scan"),
                 _api_run(2, EVENING, "2026-10-13T03:01:38Z", "Evening cron 16 22 * * 1-5")]
    pushed = [{"id": 7, "path": ".github/workflows/tests.yml", "created_at": "2026-10-13T18:02:18Z", "head_sha": "e" * 40,
               "head_commit": {"id": "e" * 40, "timestamp": "2026-10-13T18:02:15Z", "message": "m"}, "event": "push"}]

    def get(url):
        asked.append(url)
        page = int(url.rsplit("page=", 1)[1])
        if "event=schedule" in url:
            return _page(scheduled[:2] if page == 1 else scheduled[2:], 3)
        return _page(pushed if page == 1 else [], 1)

    history = {"a" * 40, "e" * 40, "d" * 40}
    monkeypatch.setattr(sr, "_git", lambda *a: "\n".join(sorted(history)) + "\n" if a[0] == "rev-list" else "d" * 40 + "\n")
    monkeypatch.setattr(sr, "scheduled_at", lambda commit: {".github/workflows/source-recovery.yml"})
    monkeypatch.setattr(sr, "table_versions", lambda path, ref: [version("2026-09-01T00:00:00+00:00",
                        {SCAN: ["0 6 * * 1"], EVENING: EVENING_CRONS}.get(path, ["37 7 * * *"]))])
    s = sr.fetch(repository="o/r", get=get, now=at("2026-10-13T18:13:00"))
    assert [u.split("?")[1] for u in asked] == ["event=schedule&per_page=100&page=1", "event=schedule&per_page=100&page=2",
                                                "event=push&branch=main&per_page=100&page=1"]
    assert [r["id"] for r in s["runs"]] == [1, 3, 2]                         # by creation
    assert all(set(r) == set(sr.RUN_FIELDS) for r in s["runs"])
    assert s["push_runs"] == [{"id": 7, "path": ".github/workflows/tests.yml", "created_at": "2026-10-13T18:02:18Z",
                               "head_sha": "e" * 40, "committed_at": "2026-10-13T18:02:15Z"}]
    assert sorted(s["tables"]) == [EVENING, SCAN, ".github/workflows/source-recovery.yml"]
    assert (s["fetched_at"], s["ref_commit"], s["total_count"], s["push_total_count"]) == \
        ("2026-10-13T18:13:00+00:00", "d" * 40, 3, 1)
    # a ref whose history lacks a commit a run ran on is refused: its tables would miss versions
    history.discard("e" * 40)
    with pytest.raises(sr.ScheduleError, match="1 commits the runs ran on are not in"):
        sr.fetch(repository="o/r", get=get, now=at("2026-10-13T18:13:00"))


@pytest.mark.parametrize("body,why", [
    (lambda page: _page([_api_run(1, SCAN, "2026-10-12T13:50:02Z", "Secret scan")] if page == 1 else [], 2), "listed 1"),
    (lambda page: {"workflow_runs": []}, "not a workflow-runs page"),
    (lambda page: [], "not a workflow-runs page"),
    (lambda page: _page([_api_run(page, SCAN, "2026-10-12T13:50:02Z", "Secret scan")], 99), "more than 2 pages"),
    (lambda page: _page([_api_run(page, SCAN, "2026-10-12T13:50:02Z", "Secret scan")], 1001), "lists at most 1000"),
])
def test_a_listing_that_does_not_add_up_is_a_refusal_never_a_truncation(monkeypatch, body, why):
    monkeypatch.setattr(sr, "MAX_PAGES", 2)
    with pytest.raises(sr.ScheduleError, match=why):
        sr._listing(lambda url: body(int(url.rsplit("page=", 1)[1])), "o/r", "event=schedule", dict)


def test_an_http_failure_is_a_refusal_never_a_traceback(monkeypatch):
    import urllib.error

    def refuse(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 403, "rate limited", {}, None)

    def unreachable(request, timeout):
        raise urllib.error.URLError("no route")

    monkeypatch.setattr(sr.urllib.request, "urlopen", refuse)
    with pytest.raises(sr.ScheduleError, match="HTTP 403"):
        sr._get("https://api.github.com/x")
    monkeypatch.setattr(sr.urllib.request, "urlopen", unreachable)
    with pytest.raises(sr.ScheduleError, match="no route"):
        sr._get("https://api.github.com/x")


def _commit(repo: Path, when: str, message: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when, "GIT_AUTHOR_NAME": "t",
           "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", message], cwd=repo, check=True, env=env)
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def test_table_versions_are_each_change_of_the_crons_on_the_first_parent_line(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / ".github/workflows").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    wf = repo / ".github/workflows/w.yml"
    wf.write_text('on:\n  schedule:\n    - cron: "30 12 * * 1-5"   # a\n')
    c1 = _commit(repo, "2026-09-01T23:16:19+00:00", "one")
    wf.write_text('on:\n  schedule:\n    - cron:  "30 12 * * 1-5"   # the same cron, a new comment\n')
    _commit(repo, "2026-09-02T00:00:00+00:00", "comment")
    (repo / "other.txt").write_text("x")
    _commit(repo, "2026-09-03T00:00:00+00:00", "another file")
    # a branch changes the crons on 5 October; they take effect only when it lands on main, on the 9th
    subprocess.run(["git", "checkout", "-q", "-b", "side"], cwd=repo, check=True)
    wf.write_text("on:\n  schedule:\n    - cron: '20 13 * * 1-5'\n    - cron: \"28 13 * * 1-5\"\n")
    _commit(repo, "2026-10-05T12:00:00+00:00", "two, on a branch")
    subprocess.run(["git", "checkout", "-q", "main"], cwd=repo, check=True)
    env = {**os.environ, "GIT_AUTHOR_DATE": "2026-10-09T17:07:37+00:00", "GIT_COMMITTER_DATE": "2026-10-09T17:07:37+00:00",
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "merge", "-q", "--no-ff", "-m", "two, merged", "side"], cwd=repo, check=True, env=env)
    c3 = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
    wf.unlink()
    c4 = _commit(repo, "2026-10-10T00:00:00-04:00", "gone")
    monkeypatch.setattr(sr, "ROOT", repo)
    assert sr.table_versions(".github/workflows/w.yml", "main") == [
        {"commit": c1, "effective_at": "2026-09-01T23:16:19+00:00", "crons": ["30 12 * * 1-5"]},
        {"commit": c3, "effective_at": "2026-10-09T17:07:37+00:00", "crons": ["20 13 * * 1-5", "28 13 * * 1-5"]},
        {"commit": c4, "effective_at": "2026-10-10T04:00:00+00:00", "crons": []}]
    assert sr.scheduled_at(c3) == {".github/workflows/w.yml"} and sr.scheduled_at(c4) == set()
    with pytest.raises(sr.ScheduleError, match="git could not produce"):
        sr._git("rev-parse", "--verify", "nowhere^{commit}")


# ------------------------------------------------------------ files, check ----

def test_check_holds_both_files_to_the_snapshot(tmp_path):
    s = valid()
    sr.write(s, sr.build(s), tmp_path)
    assert sr.check(tmp_path) == []
    md = tmp_path / sr.OUTPUT_MD.name
    md.write_text(md.read_text() + "\nedited\n")
    assert sr.check(tmp_path) == [f"{sr.OUTPUT_MD.name} is not what the tool writes from {sr.SNAPSHOT.name}"]
    sr.write(s, sr.build(s), tmp_path)
    js = tmp_path / sr.OUTPUT_JSON.name
    js.write_text(js.read_text().replace("285.6", "285.7"))
    assert sr.check(tmp_path) == [f"{sr.OUTPUT_JSON.name} is not what the tool writes from {sr.SNAPSHOT.name}"]
    js.unlink()
    assert sr.check(tmp_path)[0].startswith(sr.OUTPUT_JSON.name)
    (tmp_path / sr.SNAPSHOT.name).write_text("{")
    with pytest.raises(sr.ScheduleError):
        sr.check(tmp_path)


def test_the_command_line_writes_checks_and_refuses(tmp_path, capsys):
    s = valid()
    (tmp_path / sr.SNAPSHOT.name).write_text(json.dumps(s))
    assert sr.main(["--output-dir", str(tmp_path)]) == 0
    assert sr.main(["--check", "--output-dir", str(tmp_path)]) == 0
    (tmp_path / sr.OUTPUT_MD.name).write_text("x")
    assert sr.main(["--check", "--output-dir", str(tmp_path)]) == 1
    s["runs"][0]["event"] = "push"
    (tmp_path / sr.SNAPSHOT.name).write_text(json.dumps(s))
    assert sr.main(["--output-dir", str(tmp_path)]) == 2
    assert "refused:" in capsys.readouterr().err


def test_the_markdown_says_what_the_reading_holds():
    text = sr.markdown(sr.build(valid()))
    # in slot order the Monday scan, 06:00, comes before the evening's 22:16
    assert "first run created more than 60 minutes after its slot: `.github/workflows/secret-scan.yml` `0 6 * * 1` " \
           "at 2026-10-12 06:00Z, 470.0 min" in text
    assert "| `16 22 * * 1-5` | 285.6 / 285.6 / 285.6 (1) |" in text
    assert "| `0 6 * * 1` | 470.0 / 470.0 / 470.0 (1) |" in text
    assert "- every push run: 0.1 / 0.1 / 0.1 (1)" in text


# ------------------------------------------------------- the committed one ----

def _present(commit: str) -> bool:
    return subprocess.run(["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=ROOT, capture_output=True).returncode == 0


@pytest.fixture(scope="module")
def committed() -> dict:
    """The committed snapshot, with every commit its tables name present: a
    shallow checkout -- CI's -- fetches exactly those, once, and fails with the
    reason when it cannot."""
    s = json.loads(sr.SNAPSHOT.read_text(encoding="utf-8"))
    named = sorted({s["ref_commit"]} | {v["commit"] for vs in s["tables"].values() for v in vs})
    missing = [c for c in named if not _present(c)]
    if missing:
        done = subprocess.run(["git", "fetch", "--quiet", "--no-tags", "--depth=1", "origin", *missing],
                              cwd=ROOT, capture_output=True, text=True)
        assert done.returncode == 0 and all(_present(c) for c in missing), \
            f"{len(missing)} commits the snapshot names could not be fetched: {done.stderr.strip()}"
    return s


def test_the_committed_reading_is_what_its_snapshot_gives():
    assert sr.check(sr.OUT_DIR) == []


def test_the_committed_tables_are_the_workflow_files_git_carries(committed):
    shallow = sr._git("rev-parse", "--is-shallow-repository").strip() == "true"
    for path, versions in committed["tables"].items():
        for v in versions:
            show = subprocess.run(["git", "show", f"{v['commit']}:{path}"], cwd=ROOT, capture_output=True, text=True)
            crons = [" ".join(c.split()) for c in sr.FILE_CRON.findall(show.stdout)] if show.returncode == 0 else []
            assert crons == v["crons"], (path, v["commit"])
            assert sr.iso(sr.parse_instant(sr._git("show", "-s", "--format=%cI", v["commit"]).strip())) == v["effective_at"]
        # the table the snapshot's ref carried is the last version's
        show = subprocess.run(["git", "show", f"{committed['ref_commit']}:{path}"], cwd=ROOT, capture_output=True, text=True)
        assert [" ".join(c.split()) for c in sr.FILE_CRON.findall(show.stdout)] == versions[-1]["crons"], path
        if not shallow:      # with the history here, no version is missing either
            assert sr.table_versions(path, committed["ref_commit"]) == versions, path
    assert sr.scheduled_at(committed["ref_commit"]) <= set(committed["tables"])
    if not shallow:          # and every run ran on a commit the ref carries
        history = set(sr._git("rev-list", committed["ref_commit"]).split())
        assert {r["head_sha"] for r in committed["runs"] + committed["push_runs"]} <= history


def _hm(instant: str) -> str:
    return instant[11:16]


def test_the_dated_report_quotes_the_reading():
    reading = json.loads(sr.OUTPUT_JSON.read_text(encoding="utf-8"))
    snapshot = json.loads(sr.SNAPSHOT.read_text(encoding="utf-8"))
    report = (ROOT / "docs/input-truthfulness/2026-10-13-schedule-reliability.md").read_text(encoding="utf-8")
    prose = " ".join(report.split())
    c, k, w = reading["change"], reading["contrast"], reading["workflows"]
    since = c["since"]
    runs = [a for v in w.values() for a in v["runs"]]
    before = [a for a in runs if a["slot"] < c["first_late"]["slot"]]
    assert f"128 scheduled runs the API listed at {snapshot['fetched_at'][11:16]} UTC" in prose
    assert reading["snapshot"]["runs"] == 128 and f"the {reading['snapshot']['push_runs']} runs a push to `main`" in prose
    # before the change
    assert f"within {math.ceil(max(a['delay_seconds'] for a in before) / 60)} minutes of its slot.** That covers {len(before)} runs" in prose
    clean = [wk["median"] for v in w.values() for wk in v["weeks"]
             if all(a["slot"] < c["first_late"]["slot"] for a in v["runs"] if sr._week(sr.parse_instant(a["slot"])) == wk["week"])]
    assert f"weekly medians of {min(clean)} to {max(clean)} minutes" in prose
    assert f"created {c['last_prompt_before']['delay_minutes']} minutes after its slot" in prose
    # the change and since
    assert f"That run was created {c['first_late']['delay_minutes']} minutes after its slot" in prose
    assert f"{since['delay_minutes']['n']} scheduled runs from that slot on" in prose
    assert f"{since['delay_minutes']['min']} to {since['delay_minutes']['max']} minutes after their slots, median {since['delay_minutes']['median']}" in prose
    assert f"{since['beyond']['240']} were more than four hours late, and {since['beyond']['360']} of them more than six hours" in prose
    assert f"{since['delay_minutes']['n'] - since['beyond']['360']} of {since['delay_minutes']['n']} scheduled runs were created within 360 minutes" in prose
    # the weekly growth
    evening = [wk["median"] for wk in w[EVENING]["weeks"] if wk["week"] >= sr._week(sr.parse_instant(c["first_late"]["slot"]))]
    assert f"weekly medians were {evening[0]}, {evening[1]} and {evening[2]} minutes, then {evening[3]} minutes in the {w[EVENING]['weeks'][-1]['n']} runs" in prose
    scan = [wk["median"] for wk in w[SCAN]["weeks"] if wk["median"] > 60]
    assert f"Monday secret scan was {scan[0]}, {scan[1]} and {scan[2]} minutes late" in prose
    # the morning
    october = [a for a in w[MORNING]["runs"] if a["slot"].startswith("2026-10-12")]
    assert f"created those four runs {min(a['delay_minutes'] for a in october)} to {max(a['delay_minutes'] for a in october)} minutes after their slots" in prose
    window = {a["cron"]: a["delay_minutes"] for a in october if a["cron"] in ("20 13 * * 1-5", "28 13 * * 1-5")}
    assert f"were {window['20 13 * * 1-5']} and {window['28 13 * * 1-5']} minutes late" in prose
    assert f"were created {window['20 13 * * 1-5']} and {window['28 13 * * 1-5']} minutes late" in prose
    assert f"the {len(w[MORNING]['not_started'])} slots of 13 October had not been created" in prose
    # the contrast
    assert f"{k['since_change']['n']} runs a push to `main` triggered were each created within seconds" in prose
    assert f"none more than {k['since_change']['max']} minutes, median {k['since_change']['median']}" in prose
    # the retries for the 12 October session
    retries = [a for a in w[EVENING]["runs"] if a["slot"].startswith("2026-10-13") and a["cron"] in ("16 0 * * 2-6", "16 1 * * 2-6")]
    assert f"created at {_hm(retries[0]['created_at'])} and {_hm(retries[1]['created_at'])} UTC on 13 October" in prose
    # the source-recovery arithmetic: 07:37 plus the median, and plus the evening's two latest
    at_median = at("2026-10-14T07:37:00") + timedelta(seconds=round(since["delay_minutes"]["median"] * 60))
    assert f"{since['delay_minutes']['median']} minutes, a run would be created at {at_median:%H:%M} UTC" in prose
    latest = sorted(w[EVENING]["runs"], key=lambda a: a["slot"])[-2:]
    assert f"evening's two latest delays, {latest[0]['delay_minutes']} and {latest[1]['delay_minutes']} minutes" in prose
    # the first build's nearest-slot runs
    first_build = [a for p, v in w.items() if p != SCAN for a in v["runs"] if a["basis"] == "nearest_slot"]
    assert f"Those are {sum(a['basis'] == 'nearest_slot' for a in runs)} runs: the first build's {len(first_build)}" in prose
    assert f"their {len(first_build)} runs were {min(a['delay_minutes'] for a in first_build)} to {max(a['delay_minutes'] for a in first_build)} minutes late" in prose


def test_the_evidence_index_quotes_the_reading():
    reading = json.loads(sr.OUTPUT_JSON.read_text(encoding="utf-8"))
    index = " ".join((ROOT / "docs/input-truthfulness/README.md").read_text(encoding="utf-8").split())
    entry = index.split("(2026-10-13-schedule-reliability.md)")[1].split("[12 October 2026")[0]
    c, k, w = reading["change"], reading["contrast"], reading["workflows"]
    since = c["since"]["delay_minutes"]
    october = [a["delay_minutes"] for a in w[MORNING]["runs"] if a["slot"].startswith("2026-10-12")]
    assert f"all {since['n']} runs were created {since['min']} to {since['max']} minutes late" in entry
    assert f"were {round(min(october))} to {round(max(october))} minutes late" in entry
    assert f"within {k['since_change']['max']} minutes of their commits" in entry
    assert "within 17 minutes of its slot" in entry and "the 13 October ones had not been created" in entry
