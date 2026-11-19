"""The go-live gate (src/go_live.py) and what it does to orders.json.

Every clock here is pinned in the records it reads; the gate itself reads no
clock. These hold each condition to the case that meets it and each case
that does not, the ledger to the sessions it closes, the standing rules to
the nightly membership they ignore, the validator to the block's shape, and
orders.json and the page to the block."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from src import go_live as gl, orders, report

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "tests" / "fixtures" / "page"


def page(name: str) -> dict:
    return json.loads((PAGE / f"{name}.json").read_text())


def previous_record(session="2026-11-17", published="2026-11-17T22:20:00+00:00", event="schedule",
                    flag=None, applicable="2026-11-18") -> dict:
    return {"run": {"session": session, "published_at": published,
                    "trigger": {"event": event, "only_if_unpublished": flag},
                    "timing": {"applicable_session": applicable}}}


def morning_for(sha, generated="2026-11-18T14:21:00+00:00") -> dict:
    return {"publication": {"data_sha256": sha}, "generated_at": generated}


SHA = "a" * 64


# ------------------------------------------------------------- one session --
def test_a_session_published_by_seven_started_on_schedule_and_checked_in_time_is_counted():
    entry = gl.close_session(previous_record(), SHA, morning_for(SHA))
    assert entry == {"session": "2026-11-17", "published_at": "2026-11-17T22:20:00+00:00", "on_time": True,
                     "automatic": True, "applicable_session": "2026-11-18",
                     "morning_generated_at": "2026-11-18T14:21:00+00:00", "morning_on_time": True, "counted": True}


@pytest.mark.parametrize("change, field", [
    ({"published": "2026-11-18T00:01:00+00:00"}, "on_time"),           # 7:01 PM in New York
    ({"published": "2026-11-18T05:00:00+00:00"}, "on_time"),           # past midnight, another date
    ({"event": "workflow_dispatch", "flag": False}, "automatic"),     # a hand-run publish
    ({"event": None}, "automatic"),                                   # a record from before run.trigger
])
def test_a_late_or_hand_run_publication_is_not_counted(change, field):
    entry = gl.close_session(previous_record(**change), SHA, morning_for(SHA))
    assert entry["counted"] is False and entry[field] is not True


def test_seven_pm_exactly_is_on_time_and_the_dispatchers_guarded_dispatch_is_automatic():
    entry = gl.close_session(previous_record(published="2026-11-18T00:00:00+00:00", event="workflow_dispatch",
                                             flag=True), SHA, morning_for(SHA))
    assert (entry["on_time"], entry["automatic"], entry["counted"]) == (True, True, True)
    # in daylight time seven in New York is 23:00 UTC
    summer = gl.close_session(previous_record(session="2026-07-15", published="2026-07-15T23:00:00+00:00",
                                              applicable="2026-07-16"), SHA,
                              morning_for(SHA, "2026-07-16T13:45:00+00:00"))
    assert summer["on_time"] is True and summer["morning_on_time"] is True


@pytest.mark.parametrize("morning", [
    None,
    morning_for("b" * 64),                                  # bound to another publication
    morning_for(SHA, "2026-11-18T14:46:00+00:00"),          # 8:46 AM in Chicago
    morning_for(SHA, "2026-11-17T14:00:00+00:00"),          # another day
    {"publication": {"data_sha256": SHA}},                  # no generation time
])
def test_a_morning_file_that_is_late_missing_or_bound_elsewhere_ends_the_count(morning):
    entry = gl.close_session(previous_record(), SHA, morning)
    assert entry["morning_on_time"] is False and entry["counted"] is False


def test_there_is_nothing_to_close_without_a_real_previous_publication():
    assert gl.close_session({}, None, None) is None
    assert gl.close_session({"fixture": "x", **previous_record()}, SHA, morning_for(SHA)) is None


# ---------------------------------------------------------------- the ledger --
def counted(session):
    return {"session": session, "counted": True}


def test_the_run_of_counted_sessions_ends_at_a_gap_or_an_uncounted_session():
    days = ["2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13", "2026-11-16", "2026-11-17"]
    assert gl.consecutive([counted(d) for d in days]) == 7                     # the weekend is no gap
    assert gl.consecutive([counted(d) for d in days if d != "2026-11-12"]) == 3  # a missed session is
    rows = [counted(d) for d in days]
    rows[-2]["counted"] = False
    assert gl.consecutive(rows) == 1 and gl.consecutive([]) == 0
    # Thanksgiving is no session: the Wednesday and the Friday are adjacent
    assert gl.consecutive([counted("2026-11-25"), counted("2026-11-27")]) == 2


def test_the_ledger_replaces_a_session_closed_twice_and_keeps_the_newest():
    rows = gl.ledger_of({"ledger": [counted("2026-11-16"), {"session": "2026-11-17", "counted": False}]},
                        counted("2026-11-17"))
    assert rows == [counted("2026-11-16"), counted("2026-11-17")]
    many = {"ledger": [counted(f"2026-{m:02d}-{d:02d}") for m in (9, 10) for d in range(1, 28)]}
    assert len(gl.ledger_of(many, None)) == gl.LEDGER_MAX


# ---------------------------------------------------------- the conditions --
def build(session="2026-11-18", previous=None, rows=(), rules=None, morning=None, sha=SHA, **monkey):
    return gl.build(session=session, rules=rules or {"plan": {"x": 1}, "universe": {"identity": "u1"}},
                    previous=previous if previous is not None else previous_record(), previous_sha256=sha,
                    morning=morning if morning is not None else morning_for(SHA), scorecard_rows=list(rows))


def test_the_gate_is_paper_until_every_condition_holds(monkeypatch, tmp_path):
    block = build()
    assert block["ready"] is False and block["reasons"][0] == "fidelity_protocol"
    assert {c["key"]: c["met"] for c in block["criteria"]}["ablation_report"] is True
    assert block["sentence"].startswith("Paper only: fidelity protocol not met")
    passed = tmp_path / "protocol.json"
    passed.write_text(json.dumps({"passed": True, "recorded_on": "2026-11-20", "recorded_by": "owner"}))
    monkeypatch.setattr(gl, "PROTOCOL_FILE", passed)
    ledger = [counted(d) for d in ("2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06", "2026-11-09",
                                   "2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13", "2026-11-16")]
    prior = {**previous_record(), "run": {**previous_record()["run"], "go_live": {
        "ledger": ledger, "strategy": {"digest": gl.strategy_digest({"plan": {"x": 1}, "universe": {"identity": "u0"}}),
                                       "since": "2026-10-01"}}}}
    rows = [{"bucket": "settled", "picked": "2026-10-15"}] * gl.MIN_SETTLED_FORWARD
    ready = build(previous=prior, rows=rows)
    assert ready["ready"] is True and ready["reasons"] == [] and ready["sentence"].startswith("Live ready")
    assert ready["strategy"]["since"] == "2026-10-01"           # the membership moved, the rules did not
    assert next(c for c in ready["criteria"] if c["key"] == "on_time_sessions")["have"] == 11
    # one plan short, or the rules changed, and it is paper again
    assert build(previous=prior, rows=rows[1:])["reasons"] == ["settled_forward_plans"]
    moved = build(previous=prior, rows=rows, rules={"plan": {"x": 2}, "universe": {"identity": "u1"}})
    assert moved["strategy"]["since"] == "2026-11-18" and moved["reasons"] == ["settled_forward_plans"]
    # only settled plans picked on or after the standing rules count: an
    # uncertain or still-open plan, or one picked before them, does not
    padded = rows[1:] + [{"bucket": "uncertain", "picked": "2026-10-15"}, {"bucket": "open", "picked": "2026-10-16"},
                         {"bucket": "settled", "picked": "2026-09-30"}]
    held = build(previous=prior, rows=padded)
    assert held["reasons"] == ["settled_forward_plans"]
    assert next(c for c in held["criteria"] if c["key"] == "settled_forward_plans")["have"] == gl.MIN_SETTLED_FORWARD - 1


@pytest.mark.parametrize("value", [
    {"passed": True, "recorded_on": "2026-11-20", "recorded_by": "someone"},
    {"passed": True, "recorded_on": None, "recorded_by": "owner"},
    {"passed": "yes", "recorded_on": "2026-11-20", "recorded_by": "owner"},
])
def test_only_the_owners_dated_record_passes_the_protocol(monkeypatch, tmp_path, value):
    path = tmp_path / "p.json"
    path.write_text(json.dumps(value))
    monkeypatch.setattr(gl, "PROTOCOL_FILE", path)
    assert gl.protocol()["passed"] is False


def test_the_committed_protocol_record_is_unpassed_and_names_nothing_private():
    value = json.loads(gl.PROTOCOL_FILE.read_text())
    assert value["passed"] is False and value["recorded_by"] is None
    assert "public" in value["note"] and set(value) == {"version", "protocol", "passed", "recorded_on", "recorded_by", "note"}


def test_a_missing_ablation_is_not_met(monkeypatch, tmp_path):
    monkeypatch.setattr(gl, "ABLATION_FILE", ROOT / "nowhere.json")
    assert gl.ablation() is False
    assert "ablation_report" in build()["reasons"]


def test_a_revision_of_the_same_session_closes_nothing():
    same = build(session="2026-11-17")
    assert same["ledger"] == []


def test_the_strategy_digest_ignores_only_the_nightly_membership():
    a = {"plan": {"x": 1}, "universe": {"identity": "u1", "max_discovery": 8000}}
    assert gl.strategy_digest(a) == gl.strategy_digest({**a, "universe": {"identity": "u2", "max_discovery": 8000}})
    assert gl.strategy_digest(a) != gl.strategy_digest({**a, "universe": {"identity": "u1", "max_discovery": 9000}})


def test_the_trigger_is_the_workflows_own_words():
    assert gl.trigger_from({"SCAN_TRIGGER_EVENT": "schedule", "SCAN_TRIGGER_ONLY_IF_UNPUBLISHED": "false"}) == \
        {"event": "schedule", "only_if_unpublished": False}
    assert gl.trigger_from({}) == {"event": None, "only_if_unpublished": None}
    workflow = (ROOT / ".github" / "workflows" / "evening.yml").read_text()
    assert "SCAN_TRIGGER_EVENT: ${{ github.event_name }}" in workflow
    assert "SCAN_TRIGGER_ONLY_IF_UNPUBLISHED: ${{ inputs.only_if_unpublished == true && 'true' || 'false' }}" in workflow


def test_the_morning_due_time_is_the_service_watchs():
    from tools import service_watch
    assert gl.MORNING_DUE_CT == service_watch.MORNING_DUE_CT


# --------------------------------------------------- record, orders, page --
def test_the_evening_writes_the_block_and_the_validator_holds_it():
    data = page("full")
    block = data["run"]["go_live"]
    assert data["rules"]["go_live"]["on_time_sessions"] == gl.ON_TIME_SESSIONS and gl.faults(data) == []
    assert block["ready"] is False and block["reasons"] == ["fidelity_protocol", "on_time_sessions", "settled_forward_plans"]
    for change, words in ((lambda d: d["run"].pop("go_live"), "missing"),
                          (lambda d: d["run"]["go_live"].update(ready=True), "ready"),
                          (lambda d: d["run"]["go_live"].update(reasons=[]), "reasons"),
                          (lambda d: d["run"]["go_live"]["criteria"].pop(), "criteria")):
        forged = copy.deepcopy(data)
        change(forged)
        assert any(words in f for f in gl.faults(forged)), words
        with pytest.raises(ValueError):
            report.validate(forged)
    older = copy.deepcopy(data)
    del older["rules"]["go_live"]
    assert gl.faults(older) == ["run.go_live present under rules that do not write it"]


def test_orders_json_is_paper_until_the_records_gate_is_ready():
    data = page("full")
    doc = orders.build(json.dumps(data).encode())
    assert doc["mode"] == "paper" and doc["live_ready"] == {"value": False, "reasons": data["run"]["go_live"]["reasons"]}
    ready = copy.deepcopy(data)
    ready["run"]["go_live"].update(ready=True, reasons=[])
    for c in ready["run"]["go_live"]["criteria"]:
        c["met"] = True
    live = orders.build(json.dumps(ready).encode())
    assert live["mode"] == "live" and live["live_ready"] == {"value": True, "reasons": []}
    assert orders.problems(live) == []
    for mutate in (lambda d: d["run"].pop("go_live"), lambda d: d["run"]["go_live"].update(version=99),
                   lambda d: d["run"]["go_live"].update(reasons=["whatever"])):
        forged = copy.deepcopy(ready)
        mutate(forged)
        out = orders.build(json.dumps(forged).encode())
        assert out["mode"] == "paper" and out["live_ready"] == {"value": False, "reasons": [orders.LIVE_READY_REASON]}


def test_the_page_prints_the_gate_and_the_docs_name_its_numbers():
    js = (ROOT / "docs" / "app.js").read_text()
    body = js.split("function goLiveBlock(data)", 1)[1].split("\n  function ", 1)[0]
    assert "block.sentence" in body and "'absent'" in body and "'unreadable'" in body
    assert "card.appendChild(goLiveBlock(data));" in js
    note = " ".join((ROOT / "docs" / "operations" / "go-live.md").read_text().split())
    for name in ("ON_TIME_SESSIONS", "PUBLISH_BY_ET", "MORNING_DUE_CT", "MIN_SETTLED_FORWARD", "LEDGER_MAX", "NIGHTLY_RULES"):
        assert f"`go_live.{name}`" in note, name
    readme = " ".join((ROOT / "README.md").read_text().split())
    assert (f"the newest {gl.ON_TIME_SESSIONS} consecutive sessions published by {gl.PUBLISH_BY_ET} New York time"
            in readme)
    assert f"at least {gl.MIN_SETTLED_FORWARD} settled model plans" in readme
    assert f"generated by {gl.MORNING_DUE_CT} Chicago time" in readme
