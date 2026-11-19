"""The on-time dispatcher (tools/dispatch_schedule.py): which slots are due at
a frozen clock on the XNYS calendar, across EST and EDT, holidays and half
days; and that a tick starts each due slot once, repeats nothing, refuses to
run without its token and names a refused request by its status alone."""
from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timezone
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
        listed = [{"id": i} for at, i in sorted(self.runs.get(workflow, []), reverse=True) if at >= since]
        return 200, json.dumps({"workflow_runs": listed}).encode()


def at(day: str, hhmm: str, zone=ET) -> datetime:
    return datetime.fromisoformat(f"{day}T{hhmm}:00").replace(tzinfo=zone)


# ------------------------------------------------------------- the slots ----
def test_a_session_has_eight_slots_in_their_own_zones():
    day = date(2026, 11, 20)                         # a Friday, EST
    assert sessions.is_session(day)
    slots = ds.slots_on(day)
    assert [(s.workflow, s.at.astimezone(UTC).strftime("%H:%M")) for s in slots] == [
        ("service-watch.yml", "12:00"), ("morning.yml", "14:20"), ("service-watch.yml", "14:45"),
        ("service-watch.yml", "17:00"), ("evening.yml", "23:20"), ("evening.yml", "00:20"),
        ("evening.yml", "01:20"), ("evening.yml", "02:20")]
    evening = [s for s in slots if s.workflow == "evening.yml"]
    assert all(dict(s.inputs) == {"only_if_unpublished": "true"} for s in evening)
    assert dict(next(s for s in slots if s.workflow == "morning.yml").inputs) == {"dry_run": "false"}


@pytest.mark.parametrize("day, evening_utc, morning_utc", [
    ("2026-07-15", "22:20", "13:20"),                # EDT / CDT
    ("2026-12-15", "23:20", "14:20"),                # EST / CST
    ("2026-11-02", "23:20", "14:20"),                # the Monday after the clocks moved back
    ("2026-03-09", "22:20", "13:20"),                # the Monday after they moved forward
])
def test_the_local_times_hold_across_est_and_edt(day, evening_utc, morning_utc):
    slots = ds.slots_on(date.fromisoformat(day))
    first = lambda wf: next(s for s in slots if s.workflow == wf).at.astimezone(UTC).strftime("%H:%M")
    assert first("evening.yml") == evening_utc and first("morning.yml") == morning_utc
    assert all(s.at.astimezone(ET if s.workflow == "evening.yml" else CT).strftime("%H:%M")
               in dict((w, t) for w, _, _, t in ds.SLOTS)[s.workflow] for s in slots)


@pytest.mark.parametrize("day", ["2026-11-26", "2026-12-25", "2026-11-21", "2026-11-22"])
def test_no_slot_on_a_holiday_or_a_weekend(day):
    assert not sessions.is_session(date.fromisoformat(day))
    assert ds.slots_on(date.fromisoformat(day)) == []
    assert ds.due(at(day, "18:25")) == [] and ds.due(at(day, "08:25", CT)) == []


def test_a_half_day_keeps_every_slot():
    day = date(2026, 11, 27)                         # the day after Thanksgiving: 1:00 PM ET close
    opens, closes, early = sessions.hours(day)
    assert early and closes.hour == 13
    assert [s.workflow for s in ds.slots_on(day)].count("evening.yml") == 4
    assert ds.slots_on(day)[0].at < ds.slots_on(day)[-1].at


@pytest.mark.parametrize("now, expected", [
    (at("2026-11-20", "18:19"), []),
    (at("2026-11-20", "18:20"), ["evening.yml@2026-11-20T18:20:00-05:00"]),
    (at("2026-11-20", "18:49"), ["evening.yml@2026-11-20T18:20:00-05:00"]),
    (at("2026-11-20", "18:50"), []),
    (at("2026-11-20", "21:35"), ["evening.yml@2026-11-20T21:20:00-05:00"]),
    (at("2026-11-20", "08:20", CT), ["morning.yml@2026-11-20T08:20:00-06:00"]),
    (at("2026-11-20", "08:46", CT), ["morning.yml@2026-11-20T08:20:00-06:00", "service-watch.yml@2026-11-20T08:45:00-06:00"]),
    (at("2026-11-23", "00:05", CT), []),             # Monday just past midnight: Sunday had no session
])
def test_a_slot_is_due_from_its_instant_for_the_due_window(now, expected):
    assert [s.key for s in ds.due(now)] == expected


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
    assert sum(1 for c in gh.calls if c[0] == "POST") == 2


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
    assert len(out) == 8 and out[4].startswith("2026-11-20T18:20:00-05:00  evening.yml")


def test_the_dispatched_inputs_are_inputs_the_workflows_declare():
    import yaml
    for workflow, inputs, _, _ in ds.SLOTS:
        declared = yaml.safe_load((ROOT / ".github" / "workflows" / workflow).read_text())
        on = declared.get("on") or declared.get(True)
        assert set(inputs) <= set((on["workflow_dispatch"] or {}).get("inputs") or {}), workflow
