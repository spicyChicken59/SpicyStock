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
    (at("2026-11-20", "09:05", CT), ["service-watch.yml@2026-11-20T09:05:00-06:00"]),
    (at("2026-11-23", "00:05", CT), []),             # Monday just past midnight: Sunday's evening slots are over
    (at("2026-11-21", "18:21"), ["evening.yml@2026-11-21T18:20:00-05:00"]),      # Saturday: the recovery slot
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
