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
from datetime import date
from pathlib import Path

import pytest

from src import go_live as gl, orders, report

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "tests" / "fixtures" / "page"


def page(name: str) -> dict:
    return json.loads((PAGE / f"{name}.json").read_text())


def record(name: str) -> dict:
    """The fixture as the pipeline's record: without the label report.validate() refuses."""
    data = page(name)
    data.pop("fixture", None)
    return data


def owner_record(**changes) -> dict:
    """The owner's record of a passed sitting, as the committed file's shape asks for it."""
    return {"version": 1, "protocol": "knowledge/broker-fidelity-protocol.md", "passed": True,
            "recorded_on": "2026-11-18", "recorded_by": "owner", "note": "", **changes}


def previous_record(session="2026-11-17", published="2026-11-17T22:20:00+00:00", event="schedule",
                    flag=None, applicable="2026-11-18", elapsed=180.0, opens="14:30:00+00:00",
                    dry_run=False, status="ok") -> dict:
    # elapsed is the run's finish: seconds from its start to the record's final write
    return {"run": {"session": session, "published_at": published, "finish_seconds": elapsed,
                    "elapsed_seconds": 0.0, "dry_run": dry_run, "status": status,
                    "trigger": {"event": event, "only_if_unpublished": flag},
                    "timing": {"applicable_session": applicable, "opens_at": f"{applicable}T{opens}",
                               "cutoff_at": f"{applicable}T15:00:00+00:00" if opens.startswith("14") else f"{applicable}T14:00:00+00:00"}}}


def morning_for(sha, generated="2026-11-18T14:21:00+00:00", status="no_tickets", dry_run=False) -> dict:
    return {"publication": {"data_sha256": sha}, "generated_at": generated, "status": status, "dry_run": dry_run}


SHA = "a" * 64


# ------------------------------------------------------------- one session --
def test_a_session_published_by_seven_started_on_schedule_and_checked_in_time_is_counted():
    entry = gl.close_session(previous_record(), SHA, morning_for(SHA))
    assert entry == {"session": "2026-11-17", "published_at": "2026-11-17T22:20:00+00:00", "on_time": True,
                     "automatic": True, "applicable_session": "2026-11-18",
                     "morning_generated_at": "2026-11-18T14:21:00+00:00", "morning_status": "no_tickets",
                     "morning_on_time": True, "counted": True}


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
    # the run's finish (its start clock plus its elapsed 180 seconds) lands exactly at seven
    entry = gl.close_session(previous_record(published="2026-11-17T23:57:00+00:00", event="workflow_dispatch",
                                             flag=True), SHA, morning_for(SHA))
    assert (entry["on_time"], entry["automatic"], entry["counted"]) == (True, True, True)
    # in daylight time seven in New York is 23:00 UTC
    summer = gl.close_session(previous_record(session="2026-07-15", published="2026-07-15T22:57:00+00:00",
                                              applicable="2026-07-16", opens="13:30:00+00:00"), SHA,
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
    # a previous record whose session is no date closes nothing: a row the validator could not read
    assert gl.close_session(previous_record(session="soon"), SHA, morning_for(SHA)) is None
    assert gl.close_session(previous_record(session=20261117), SHA, morning_for(SHA)) is None
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
def evening_clock(session: str) -> dict:
    """An evening run's own clock: started 5:20 PM ET on its session, its plans for the next one."""
    from src import sessions
    applicable = sessions.next_sessions(date.fromisoformat(session), 1)[0].isoformat()
    return {"published_at": f"{session}T22:20:00+00:00", "opens_at": f"{applicable}T14:30:00+00:00"}


def build(session="2026-11-18", previous=None, rows=(), rules=None, morning=None, sha=SHA, **clock):
    return gl.build(session=session, rules=rules or {"plan": {"x": 1}, "universe": {"identity": "u1"}},
                    previous=previous if previous is not None else previous_record(), previous_sha256=sha,
                    morning=morning if morning is not None else morning_for(SHA), scorecard_rows=list(rows),
                    **{**evening_clock(session), **clock})


def test_the_gate_is_paper_until_every_condition_holds(monkeypatch, tmp_path):
    block = build()
    assert block["ready"] is False and block["reasons"][0] == "fidelity_protocol"
    assert {c["key"]: c["met"] for c in block["criteria"]}["ablation_report"] is True
    assert block["sentence"].startswith("Paper only: fidelity protocol not met")
    passed = tmp_path / "protocol.json"
    passed.write_text(json.dumps(owner_record()))
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


@pytest.mark.parametrize("change", [
    {"recorded_by": "someone"},
    {"recorded_on": None},
    {"recorded_on": "the 18th"},
    {"recorded_on": "2026-11-19"},                  # dated after tonight's session
    {"passed": "yes"},
    {"version": 2}, {"version": True}, {"version": 1.0},
    {"protocol": "knowledge/another-protocol.md"},
])
def test_only_the_owners_dated_record_of_this_protocol_passes(monkeypatch, tmp_path, change):
    path = tmp_path / "p.json"
    monkeypatch.setattr(gl, "PROTOCOL_FILE", path)
    path.write_text(json.dumps(owner_record()))
    assert gl.protocol("2026-11-18") == {"passed": True, "recorded_on": "2026-11-18",
                                         "detail": "recorded as passed by the owner"}
    path.write_text(json.dumps(owner_record(**change)))
    assert gl.protocol("2026-11-18")["passed"] is False
    assert gl.protocol("tonight")["passed"] is False            # a session that is no date bounds nothing


def test_the_owners_record_is_held_to_the_committed_files_own_words():
    committed = json.loads((ROOT / "knowledge" / "go-live" / "fidelity-protocol.json").read_text())
    assert committed["version"] == gl.PROTOCOL_RECORD_VERSION and committed["protocol"] == gl.PROTOCOL_NAME
    assert (ROOT / gl.PROTOCOL_NAME).is_file()


def test_the_committed_protocol_record_names_nothing_private_and_the_suite_reads_a_pinned_copy():
    committed = json.loads((ROOT / "knowledge" / "go-live" / "fidelity-protocol.json").read_text())
    assert "public" in committed["note"] and set(committed) == {"version", "protocol", "passed", "recorded_on",
                                                                "recorded_by", "note"}
    assert committed["recorded_by"] in (None, "owner") and isinstance(committed["passed"], bool)
    # the owner sets the committed record; the suite and the fixture generators never read it
    assert gl.PROTOCOL_FILE == gl.PINNED_PROTOCOL_FILE != ROOT / "knowledge" / "go-live" / "fidelity-protocol.json"
    pinned = json.loads(gl.PINNED_PROTOCOL_FILE.read_text())
    assert pinned["passed"] is False and set(pinned) == set(committed)
    for tool in ("make_fixture.py", "recovery_rehearsal.py"):
        assert "go_live.PROTOCOL_FILE = go_live.PINNED_PROTOCOL_FILE" in (ROOT / "tools" / tool).read_text(), tool


def test_a_missing_ablation_is_not_met(monkeypatch, tmp_path):
    monkeypatch.setattr(gl, "ABLATION_FILE", ROOT / "nowhere.json")
    assert gl.ablation() is False
    assert "ablation_report" in build()["reasons"]


def test_a_revision_of_the_same_session_closes_nothing():
    same = build(session="2026-11-17")
    assert same["ledger"] == []


def test_the_strategy_digest_ignores_only_the_membership_and_the_event_registry():
    a = {"plan": {"x": 1}, "universe": {"identity": "u1", "max_discovery": 8000},
         "event_risk": {"version": 1, "registry": {"reviewed_on": "2026-11-19"}, "registry_sha256": "r1"}}
    assert gl.strategy_digest(a) == gl.strategy_digest({**a, "universe": {"identity": "u2", "max_discovery": 8000}})
    assert gl.strategy_digest(a) != gl.strategy_digest({**a, "universe": {"identity": "u1", "max_discovery": 9000}})
    # a registry review (its dates, its digest) is data the run reads, not a strategy rule
    reviewed = {**a, "event_risk": {"version": 1, "registry": {"reviewed_on": "2026-11-25"}, "registry_sha256": "r2"}}
    assert gl.strategy_digest(a) == gl.strategy_digest(reviewed)
    assert gl.strategy_digest(a) != gl.strategy_digest({**a, "event_risk": {**a["event_risk"], "version": 2}})
    real = page("full")["rules"]
    assert {"registry", "registry_sha256"} <= set(real["event_risk"])


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
    data = record("full")
    block = data["run"]["go_live"]
    report.validate(data)                                   # as the pipeline wrote it, the record validates
    assert data["rules"]["go_live"]["on_time_sessions"] == gl.ON_TIME_SESSIONS and gl.faults(data) == []
    assert block["ready"] is False and block["reasons"] == ["fidelity_protocol", "on_time_sessions", "settled_forward_plans"]
    for change, words in ((lambda d: d["run"].pop("go_live"), "missing"),
                          (lambda d: d["run"]["go_live"].update(ready=True), "ready"),
                          (lambda d: d["run"]["go_live"].update(reasons=[]), "reasons"),
                          (lambda d: d["run"]["go_live"]["criteria"].pop(), "criteria")):
        forged = copy.deepcopy(data)
        change(forged)
        assert any(words in f for f in gl.faults(forged)), words
        with pytest.raises(ValueError, match="run.go_live"):
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
    for name in ("ON_TIME_SESSIONS", "PUBLISH_BY_ET", "MORNING_DUE_CT", "MIN_SETTLED_FORWARD", "LEDGER_MAX",
                 "NON_STRATEGY_RULES", "MORNING_RAN"):
        assert f"`go_live.{name}`" in note, name
    readme = " ".join((ROOT / "README.md").read_text().split())
    assert (f"the newest {gl.ON_TIME_SESSIONS} consecutive sessions published by {gl.PUBLISH_BY_ET} New York time"
            in readme)
    assert f"at least {gl.MIN_SETTLED_FORWARD} settled model plans" in readme
    assert f"generated by {gl.MORNING_DUE_CT} Chicago time" in readme


# ------------------------------------------------- the review's holes, closed --
TEN = ("2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06", "2026-11-09",
       "2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13", "2026-11-16")


def prior_with(ledger, since="2026-10-01", session="2026-11-17", digest_rules=None):
    rules = digest_rules or {"plan": {"x": 1}, "universe": {"identity": "u0"}}
    return {**previous_record(session=session), "run": {**previous_record(session=session)["run"], "go_live": {
        "ledger": ledger, "strategy": {"digest": gl.strategy_digest(rules), "since": since}}}}


def on_time(block):
    return next(c for c in block["criteria"] if c["key"] == "on_time_sessions")


@pytest.mark.parametrize("tonight, have", [
    ("2026-11-18", 11),     # the run ends on 17 November, the session before tonight
    ("2026-11-19", 0),      # 18 November was never published: it leaves no row and breaks the run
    ("2026-12-09", 0),      # a previous record weeks old
])
def test_the_run_must_end_on_the_session_before_tonight(tonight, have):
    block = build(session=tonight, previous=prior_with([counted(d) for d in TEN]))
    assert on_time(block)["have"] == have
    assert on_time(block)["met"] is (have >= gl.ON_TIME_SESSIONS)


def test_the_run_of_counted_sessions_is_anchored_to_tonight():
    rows = [counted(d) for d in TEN]
    assert gl.consecutive(rows, "2026-11-17") == 10 and gl.consecutive(rows, "2026-11-18") == 0
    assert gl.consecutive([], "2026-11-18") == 0
    # an uncounted newest session ends the run at once, whatever stands before it
    assert gl.consecutive(rows + [{"session": "2026-11-17", "counted": False}]) == 0
    assert gl.consecutive(rows + [{"session": "2026-11-17", "counted": False}], "2026-11-18") == 0


@pytest.mark.parametrize("held, met", [(gl.ON_TIME_SESSIONS - 1, False), (gl.ON_TIME_SESSIONS, True)])
def test_the_ten_session_line_is_held_at_its_boundary(held, met):
    from src import sessions
    days, day = [], date(2026, 11, 17)
    for _ in range(held):
        days.insert(0, day.isoformat())
        day = sessions.previous_session(day)
    block = build(session="2026-11-18", previous=prior_with([counted(d) for d in days[:-1]]))
    assert (on_time(block)["have"], on_time(block)["met"]) == (held, met)
    assert ("on_time_sessions" in block["reasons"]) is (not met)


def test_the_default_gate_lists_every_unmet_condition():
    assert build()["reasons"] == ["fidelity_protocol", "on_time_sessions", "settled_forward_plans"]


@pytest.mark.parametrize("morning", [
    morning_for(SHA, status="inapplicable"),
    morning_for(SHA, status="provider_unavailable"),
    morning_for(SHA, dry_run=True),
    morning_for(SHA, status=None),
    morning_for(SHA, "2026-11-18T13:59:00+00:00"),       # before the collection window opens
])
def test_a_morning_check_that_did_not_run_in_its_window_is_not_on_time(morning):
    entry = gl.close_session(previous_record(), SHA, morning)
    assert entry["morning_on_time"] is False and entry["counted"] is False


def test_the_morning_statuses_that_count_are_the_watchs():
    from tools import service_watch
    assert gl.MORNING_RAN == service_watch.RAN_STATUSES
    for status in gl.MORNING_RAN:
        assert gl.close_session(previous_record(), SHA, morning_for(SHA, status=status))["counted"] is True


@pytest.mark.parametrize("published, elapsed, on_time", [
    ("2026-11-17T23:57:00+00:00", 180.0, True),       # finishes at seven exactly
    ("2026-11-17T23:58:00+00:00", 180.0, False),      # starts before seven, finishes after it
    ("2026-11-17T23:00:00+00:00", None, None),        # no finish recorded: not counted
])
def test_published_by_seven_is_read_at_the_runs_finish(published, elapsed, on_time):
    entry = gl.close_session(previous_record(published=published, elapsed=elapsed), SHA, morning_for(SHA))
    assert entry["on_time"] is on_time and entry["counted"] is (on_time is True)


def test_a_rule_change_first_seen_on_a_backfill_stands_from_after_the_newest_publication():
    prior = prior_with([], session="2026-11-17")
    rows = [{"bucket": "settled", "picked": d} for d in ("2026-11-06", "2026-11-09", "2026-11-17", "2026-11-18")]
    backfill = build(session="2026-11-06", previous=prior, rows=rows, rules={"plan": {"x": 2}})
    assert backfill["strategy"]["since"] == "2026-11-18"
    assert next(c for c in backfill["criteria"] if c["key"] == "settled_forward_plans")["have"] == 1
    forward = build(session="2026-11-18", previous=prior, rows=rows, rules={"plan": {"x": 2}})
    assert forward["strategy"]["since"] == "2026-11-18"
    assert gl.first_forward_session("2026-11-18", "2026-11-17", True) == "2026-11-18"
    assert gl.first_forward_session("2026-11-17", "2026-11-17", False) == "2026-11-18"     # a late revision is not forward
    assert gl.first_forward_session("2026-11-06", "2026-11-17", False) == "2026-11-18"
    assert gl.first_forward_session("2026-11-18", None, True) == "2026-11-18"
    assert gl.first_forward_session("2026-11-18", None, False) == "2026-11-19"


@pytest.mark.parametrize("raw", ["[]", '"passed"', "3", '{"passed": true, "recorded_on": "a date", "recorded_by": "owner"}'])
def test_a_protocol_record_that_is_not_an_owners_dated_object_is_unpassed_and_never_raises(monkeypatch, tmp_path, raw):
    path = tmp_path / "p.json"
    path.write_text(raw)
    monkeypatch.setattr(gl, "PROTOCOL_FILE", path)
    assert gl.protocol()["passed"] is False
    monkeypatch.setattr(gl, "ABLATION_FILE", path)
    assert gl.ablation() is False


def test_the_validator_holds_each_count_to_its_need_and_the_streak_to_its_ledger():
    data = page("full")
    assert gl.faults(data) == []
    block = data["run"]["go_live"]
    i = [c["key"] for c in block["criteria"]].index("on_time_sessions")
    for change, words in (
            (lambda b: b["criteria"][i].update(need=1), "is not its count against the archived need"),
            (lambda b: b["criteria"][i].update(have=3), "on_time_sessions is not the run its own ledger ends on"),
            (lambda b: b["criteria"][i].update(have="3"), "is not its count against the archived need")):
        forged = copy.deepcopy(data)
        change(forged["run"]["go_live"])
        assert any(words in f for f in gl.faults(forged)), (words, gl.faults(forged))


@pytest.mark.parametrize("ready, reasons", [(True, ["fidelity_protocol"]), (False, []), (True, [{}])])
def test_an_inconsistent_gate_never_makes_orders_json_live(ready, reasons):
    data = page("full")
    data["run"]["go_live"].update(ready=ready, reasons=reasons)
    doc = orders.build(json.dumps(data).encode())
    assert doc["mode"] == "paper" and doc["live_ready"]["value"] is False


def test_the_committed_handoff_is_held_to_the_records_gate(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "data.json").write_text(json.dumps(page("full")))
    orders.write_publication(docs)
    assert orders.check(docs) == []
    ready = page("full")
    ready["run"]["go_live"].update(ready=True, reasons=[])
    for c in ready["run"]["go_live"]["criteria"]:
        c["met"] = True
    doc = orders.build(json.dumps(ready).encode())
    assert doc["mode"] == "live"
    (docs / "orders.json").write_bytes(orders.encode(doc))       # a live file over a record that is not ready
    found = orders.check(docs)
    assert found and found[0] in ("orders.json is not bound to data.json",
                                  "orders.json's live_ready is not the committed record's gate")
    doc["source"]["data_sha256"] = hashlib.sha256((docs / "data.json").read_bytes()).hexdigest()
    (docs / "orders.json").write_bytes(orders.encode(orders.sealed(doc)))
    assert "orders.json's live_ready is not the committed record's gate" in orders.check(docs)


def test_the_pipeline_binds_the_morning_file_to_the_record_it_replaces(tmp_path):
    from src import pipeline
    docs = tmp_path / "docs"
    docs.mkdir()
    prev = previous_record()
    raw = json.dumps(prev).encode()
    (docs / "data.json").write_bytes(raw)
    (docs / "picks.json").write_text("{}")
    sha = pipeline.previous_digest(docs)
    assert sha == hashlib.sha256(raw).hexdigest()
    (docs / "morning.json").write_text(json.dumps(morning_for(sha)))
    block = pipeline.read_go_live(docs, "2026-11-18", {"plan": {"x": 1}}, prev, sha, [])
    assert block["ledger"][-1]["counted"] is True
    (docs / "morning.json").write_text(json.dumps(morning_for("c" * 64)))
    block = pipeline.read_go_live(docs, "2026-11-18", {"plan": {"x": 1}}, prev, sha, [])
    assert block["ledger"][-1]["counted"] is False and block["ledger"][-1]["morning_on_time"] is False
    # the evening reads the digest of the record on disk before it replaces it
    body = (ROOT / "src" / "pipeline.py").read_text().split("def run_evening", 1)[1]
    assert body.index("previous_sha256 = previous_digest(docs) if previous else None") < body.index("publish_bundle(")


# ------------------------------------------ the second review's holes, closed --
def test_an_unrecorded_trigger_is_unknown_and_any_other_event_is_not_automatic():
    assert gl.automatic({}) is None and gl.automatic(None) is None and gl.automatic({"event": None}) is None
    assert gl.automatic({"event": "push"}) is False
    assert gl.automatic({"event": "workflow_dispatch", "only_if_unpublished": "true"}) is False    # the flag is a bool
    entry = gl.close_session(previous_record(event=None), SHA, morning_for(SHA))
    assert entry["automatic"] is None and entry["counted"] is False


@pytest.mark.parametrize("elapsed", [-1.0, True, "180", float("nan"), float("inf"), 1e20])
def test_an_elapsed_time_that_is_no_duration_gives_no_finish_and_never_raises(elapsed):
    entry = gl.close_session(previous_record(elapsed=elapsed), SHA, morning_for(SHA))
    assert entry["on_time"] is None and entry["counted"] is False


def test_a_morning_check_counts_only_on_its_own_session_from_the_window_start_on():
    from src import freshness
    start = freshness.morning_window(previous_record())["collection_starts_at"]
    assert start == "2026-11-18T14:00:00+00:00"
    # exactly at the window's start it counts; the same clock time a day later does not
    assert gl.close_session(previous_record(), SHA, morning_for(SHA, start))["morning_on_time"] is True
    next_day = gl.close_session(previous_record(), SHA, morning_for(SHA, "2026-11-19T14:21:00+00:00"))
    assert next_day["morning_on_time"] is False and next_day["counted"] is False
    # exactly at the due time it counts
    due = gl.close_session(previous_record(), SHA, morning_for(SHA, "2026-11-18T14:45:00+00:00"))
    assert due["morning_on_time"] is True


@pytest.mark.parametrize("dry_run", ["absent", None, "false", 0])
def test_a_morning_receipt_that_does_not_say_it_was_no_rehearsal_is_not_counted(dry_run):
    receipt = morning_for(SHA)
    if dry_run == "absent":
        del receipt["dry_run"]
    else:
        receipt["dry_run"] = dry_run
    entry = gl.close_session(previous_record(), SHA, receipt)
    assert entry["morning_on_time"] is False and entry["counted"] is False


def test_a_receipt_bound_elsewhere_lends_the_ledger_neither_its_time_nor_its_status():
    other = gl.close_session(previous_record(), SHA, morning_for("b" * 64))
    assert (other["morning_generated_at"], other["morning_status"]) == (None, None)
    # with no digest of the record it replaces, nothing is bound: None is no binding
    unbound = {"publication": {}, "generated_at": "2026-11-18T14:21:00+00:00", "status": "no_tickets", "dry_run": False}
    entry = gl.close_session(previous_record(), None, unbound)
    assert (entry["morning_generated_at"], entry["morning_status"], entry["morning_on_time"]) == (None, None, False)
    assert entry["counted"] is False


def test_a_record_that_names_no_applicable_session_leaves_the_morning_unknown():
    prev = previous_record()
    del prev["run"]["timing"]["applicable_session"]
    entry = gl.close_session(prev, SHA, morning_for(SHA))
    assert entry["morning_on_time"] is None and entry["counted"] is False


def test_the_ledger_is_sorted_keeps_the_newest_and_drops_what_it_cannot_read():
    from src import sessions
    days, day = [], date(2026, 11, 17)
    for _ in range(gl.LEDGER_MAX + 5):
        days.append(day.isoformat())
        day = sessions.previous_session(day)
    shuffled = days[1::2] + days[0::2]                                    # neither ascending nor descending
    kept = gl.ledger_of({"ledger": [counted(d) for d in shuffled]}, None)
    assert [r["session"] for r in kept] == sorted(days)[-gl.LEDGER_MAX:]
    # an entry older than the rows it joins takes its own place
    placed = gl.ledger_of({"ledger": [counted("2026-11-16"), counted("2026-11-17")]}, counted("2026-11-13"))
    assert [r["session"] for r in placed] == ["2026-11-13", "2026-11-16", "2026-11-17"]
    # rows that name no session, or no date, or are no rows, are dropped; a ledger that is no list is empty
    junk = {"ledger": [counted("2026-11-17"), {"counted": True}, {"session": 5, "counted": True},
                       {"session": "soon", "counted": True}, "2026-11-16", None]}
    assert gl.ledger_of(junk, None) == [counted("2026-11-17")]
    assert gl.ledger_of({"ledger": "2026-11-17"}, None) == [] and gl.ledger_of(None, None) == []
    assert gl.ledger_of({"ledger": 5}, None) == [] and gl.ledger_of({"ledger": {"session": "2026-11-17"}}, None) == []


def test_the_run_never_raises_over_a_ledger_or_a_session_it_cannot_read():
    rows = [counted(d) for d in TEN]
    assert gl.consecutive(rows, "tonight") == 0
    assert gl.consecutive(rows + [{"session": "soon", "counted": True}]) == 0
    assert gl.consecutive([{"session": "2026-11-16", "counted": "yes"}]) == 0      # counted is a bool
    assert gl.newest_published({"run": {"session": "soon"}}, {"newest": 5}) is None
    assert gl.newest_published({"run": {"session": "2026-11-17"}}, {"newest": "soon"}) == "2026-11-17"
    block = build(previous={"run": {"session": "soon", "go_live": {"ledger": [{"session": "x", "counted": True}],
                                                                    "strategy": "standing"}}})
    assert block["ledger"] == [] and block["strategy"]["since"] == "2026-11-18"


def test_a_standing_digest_without_its_session_is_read_again():
    rules = {"plan": {"x": 1}, "universe": {"identity": "u1"}}
    for since in (None, 5, ["2026-10-01"]):
        prior = prior_with([], since=since, digest_rules=rules)
        block = build(previous=prior, rows=[{"bucket": "settled", "picked": "2026-11-18"}], rules=rules)
        assert block["strategy"]["since"] == "2026-11-18", since
        assert next(c for c in block["criteria"] if c["key"] == "settled_forward_plans")["have"] == 1


def test_the_sentence_names_each_unmet_condition_with_its_detail():
    block = build()
    unmet = [c for c in block["criteria"] if not c["met"]]
    assert len(unmet) == 3
    assert block["sentence"] == "Paper only: " + "; ".join(
        f"{c['key'].replace('_', ' ')} not met ({c['detail']})" for c in unmet) + "."
    # the previous session closed counted, and nothing has settled since tonight's rules
    assert (f"(1 consecutive of {gl.ON_TIME_SESSIONS})" in block["sentence"]
            and f"(0 settled since 2026-11-18 of {gl.MIN_SETTLED_FORWARD})" in block["sentence"])


def _gate(data):
    block = data["run"]["go_live"]
    return block, {c["key"]: c for c in block["criteria"]}


@pytest.mark.parametrize("name, change, words", [
    ("version", lambda b, c: b.update(version=gl.VERSION + 1), "is missing or not this version"),
    ("met", lambda b, c: c["on_time_sessions"].update(met=True), "on_time_sessions is not its count against the archived need"),
    ("settled need", lambda b, c: c["settled_forward_plans"].update(need=1),
     "settled_forward_plans is not its count against the archived need"),
    ("settled met", lambda b, c: c["settled_forward_plans"].update(met=True),
     "settled_forward_plans is not its count against the archived need"),
    ("sentence", lambda b, c: b.update(sentence=5), "ledger or sentence is not readable"),
    ("ledger", lambda b, c: b.update(ledger="2026-09-10"), "ledger or sentence is not readable"),
    ("ledger none", lambda b, c: b.update(ledger=None), "ledger or sentence is not readable"),
    ("row", lambda b, c: b["ledger"].append({"counted": True}), "ledger rows are not readable"),
    ("row date", lambda b, c: b["ledger"].append({"session": "soon", "counted": True}), "ledger rows are not readable"),
])
def test_the_validator_names_each_forged_part_of_the_gate(name, change, words):
    data = record("next")                                     # its ledger has a row
    assert gl.faults(data) == [] and data["run"]["go_live"]["ledger"]
    report.validate(data)
    forged = copy.deepcopy(data)
    change(*_gate(forged))
    found = gl.faults(forged)
    assert any(f == "run.go_live " + words for f in found), (name, found)
    with pytest.raises(ValueError, match="run.go_live " + words):
        report.validate(forged)


def test_the_validator_anchors_the_streak_to_the_records_own_session():
    data = page("full")
    block, crit = _gate(data)
    block["ledger"] = [counted(d) for d in TEN]               # ten counted sessions ending 16 November
    crit["on_time_sessions"].update(have=10, met=True)
    block["reasons"] = [c["key"] for c in block["criteria"] if c["met"] is not True]
    words = "run.go_live on_time_sessions is not the run its own ledger ends on before tonight"
    data["run"]["session"] = "2026-11-17"                     # the session after the ledger's last: the run stands
    assert gl.faults(data) == []
    data["run"]["session"] = "2026-11-18"                     # a session was missed: the run is broken
    assert gl.faults(data) == [words]
    data["run"]["session"] = "tonight"
    assert gl.faults(data) == ["run.go_live ledger rows are not readable"]


def test_a_protocol_record_that_is_missing_or_no_file_is_unpassed_and_never_raises(monkeypatch, tmp_path):
    for path in (tmp_path / "missing.json", tmp_path):                    # absent, and a directory
        monkeypatch.setattr(gl, "PROTOCOL_FILE", path)
        assert gl.protocol() == {"passed": False, "recorded_on": None, "detail": "no readable record of the protocol"}
        monkeypatch.setattr(gl, "ABLATION_FILE", path)
        assert gl.ablation() is False
    binary = tmp_path / "p.json"
    binary.write_bytes(b"\xff\xfe\x00")
    monkeypatch.setattr(gl, "PROTOCOL_FILE", binary)
    assert gl.protocol()["passed"] is False


def test_the_production_gate_reads_the_owners_committed_record():
    """The suite pins ``PROTOCOL_FILE`` to an unpassed copy, so the module's
    own path is read here from a copy of the module nothing has patched."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("go_live_as_shipped", ROOT / "src" / "go_live.py")
    shipped = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shipped)
    assert shipped.PROTOCOL_FILE == ROOT / "knowledge" / "go-live" / "fidelity-protocol.json"
    assert shipped.PROTOCOL_FILE.is_file() and shipped.PINNED_PROTOCOL_FILE == gl.PINNED_PROTOCOL_FILE
    assert shipped.ABLATION_FILE.is_file() and shipped.ablation() is True
    note = (ROOT / "docs" / "operations" / "go-live.md").read_text()
    assert "knowledge/go-live/fidelity-protocol.json" in note
    # the evening itself reads the module's path and nothing pins it there
    assert "PROTOCOL_FILE" not in (ROOT / "src" / "pipeline.py").read_text()


@pytest.mark.parametrize("reasons", [{}, None, "fidelity_protocol", 0, [None]])
def test_a_gate_whose_reasons_are_no_list_of_its_own_words_is_paper_and_says_it_was_not_read(reasons):
    data = page("full")
    for c in data["run"]["go_live"]["criteria"]:
        c["met"] = True
    data["run"]["go_live"].update(ready=True, reasons=reasons)
    doc = orders.build(json.dumps(data).encode())
    assert doc["mode"] == "paper" and doc["live_ready"] == {"value": False, "reasons": [orders.LIVE_READY_REASON]}


def test_a_gate_that_is_not_ready_and_names_no_reason_still_names_one():
    data = page("full")
    data["run"]["go_live"].update(ready=False, reasons=[])
    doc = orders.build(json.dumps(data).encode())
    assert doc["live_ready"] == {"value": False, "reasons": [orders.LIVE_READY_REASON]} and doc["mode"] == "paper"
    # a truthy ready that is not true is not ready
    data["run"]["go_live"].update(ready=1, reasons=[])
    assert orders.build(json.dumps(data).encode())["live_ready"]["value"] is False


def test_the_next_nights_gate_counts_the_plan_that_settled_since_the_rules_stood():
    data = page("next")
    block, crit = _gate(data)
    since = block["strategy"]["since"]
    settled = [p["ticker"] for p in data["open_plans"]
               if p.get("picked", "") >= since and p.get("status") in ("stopped", "exit")]
    assert settled and crit["settled_forward_plans"]["have"] == len(settled)
    assert crit["settled_forward_plans"]["have"] < data["scorecard"]["settled"]     # the seeded picks are older
    assert crit["settled_forward_plans"]["detail"] == f"{len(settled)} settled since {since} of {gl.MIN_SETTLED_FORWARD}"
    # and its ledger closed the night before, which no schedule started and no morning checked
    assert [r["session"] for r in block["ledger"]] == [since]
    assert block["ledger"][0]["counted"] is False and block["ledger"][0]["automatic"] is None


from tests.test_pipeline import claude, evening, market  # noqa: E402,F401  (fixtures)


def test_the_evening_records_how_it_was_started_and_the_next_night_closes_it(market, claude, fake_resend, tmp_path,  # noqa: F811
                                                                             monkeypatch):
    from datetime import datetime, timezone
    monkeypatch.setenv("SCAN_TRIGGER_EVENT", "workflow_dispatch")
    monkeypatch.setenv("SCAN_TRIGGER_ONLY_IF_UNPUBLISHED", "true")
    rep, first, docs = evening(tmp_path, market)
    assert rep.exit_code() == 0, rep.problems
    assert first["run"]["trigger"] == {"event": "workflow_dispatch", "only_if_unpublished": True}
    assert first["run"]["go_live"]["ledger"] == [] and gl.faults(first) == []
    monkeypatch.setenv("SCAN_TRIGGER_EVENT", "schedule")
    monkeypatch.setenv("SCAN_TRIGGER_ONLY_IF_UNPUBLISHED", "false")
    rep, second, docs = evening(tmp_path, market, now=datetime(2026, 9, 11, 22, 30, tzinfo=timezone.utc))
    assert rep.exit_code() == 0, rep.problems
    assert second["run"]["trigger"] == {"event": "schedule", "only_if_unpublished": False}
    row = second["run"]["go_live"]["ledger"][-1]
    assert (row["session"], row["automatic"], row["on_time"]) == (first["run"]["session"], True, True)
    assert row["morning_on_time"] is False and row["counted"] is False           # no morning file was written
    assert gl.faults(second) == []
    # both nights were forward: made the evening of their session, before the next open
    assert first["run"]["go_live"]["strategy"] == {**first["run"]["go_live"]["strategy"], "since": "2026-09-10",
                                                   "newest": "2026-09-10", "forward": True, "not_forward": []}
    assert second["run"]["go_live"]["strategy"] == {**second["run"]["go_live"]["strategy"], "since": "2026-09-10",
                                                    "newest": "2026-09-11", "forward": True, "not_forward": []}


# ------------------------------------------- the third review's findings, held --
def test_the_finish_is_the_final_write_and_not_the_scans_own_clock():
    # the scan's clock says seven sharp; the record's final write came four minutes later
    prev = previous_record(published="2026-11-17T23:57:00+00:00", elapsed=240.0)
    prev["run"]["elapsed_seconds"] = 180.0
    entry = gl.close_session(prev, SHA, morning_for(SHA))
    assert entry["on_time"] is False and entry["counted"] is False
    # a record with no finish stamped (first installed, its restamp refused) is not shown on time
    del prev["run"]["finish_seconds"]
    assert gl.close_session(prev, SHA, morning_for(SHA))["on_time"] is None


def test_the_evening_stamps_its_finish_at_the_records_final_write(market, claude, fake_resend, tmp_path, monkeypatch):  # noqa: F811
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from src import pipeline
    clock = {"t": 1000.0}
    monkeypatch.setattr(pipeline, "time", SimpleNamespace(monotonic=lambda: clock["t"]))
    install = pipeline.provenance.publish_bundle
    first_installed = {}

    def slow_install(data, *args, **kwargs):
        out = install(data, *args, **kwargs)
        first_installed["finish"] = json.loads((tmp_path / "docs" / "data.json").read_text())["run"]["finish_seconds"]
        clock["t"] += 240.0                                   # the install, the mail and the restamp take four minutes
        return out
    monkeypatch.setattr(pipeline.provenance, "publish_bundle", slow_install)
    monkeypatch.setenv("SCAN_TRIGGER_EVENT", "schedule")
    # started 6:57 PM ET: the scan's own clock stops inside seven, the final write lands after it
    rep, first, docs = evening(tmp_path, market, now=datetime(2026, 9, 10, 22, 57, tzinfo=timezone.utc))
    assert rep.exit_code() == 0, rep.problems
    assert first_installed == {"finish": None}                # the record first installed carries no finish
    assert first["run"]["elapsed_seconds"] == 0.0 and first["run"]["finish_seconds"] == 240.0
    rep, second, docs = evening(tmp_path, market, now=datetime(2026, 9, 11, 22, 30, tzinfo=timezone.utc))
    assert rep.exit_code() == 0, rep.problems
    row = second["run"]["go_live"]["ledger"][-1]
    assert (row["session"], row["on_time"], row["counted"]) == ("2026-09-10", False, False)


@pytest.mark.parametrize("change", [{"dry_run": True}, {"dry_run": None}, {"status": "failed"}, {"status": "closed"},
                                    {"status": None}])
def test_a_rehearsal_or_a_night_that_published_nothing_new_closes_no_session(change):
    assert gl.close_session(previous_record(**change), SHA, morning_for(SHA)) is None
    assert build(previous=previous_record(**change))["ledger"] == []
    for status in gl.PUBLISHED_STATUSES:
        assert gl.close_session(previous_record(status=status), SHA, morning_for(SHA))["counted"] is True
    guard = (ROOT / ".github" / "workflows" / "evening.yml").read_text()
    # the evening guard's own definition of an already-published session
    assert all(f'"{status}"' in guard or f"'{status}'" in guard for status in gl.PUBLISHED_STATUSES)


OPEN, BEFORE, AFTER = "2026-11-19T14:30:00+00:00", "2026-11-18T22:20:00+00:00", "2026-11-19T14:30:00+00:00"


@pytest.mark.parametrize("session, newest, made, opens, want", [
    ("2026-11-18", "2026-11-17", BEFORE, OPEN, True),       # tonight's session, before the open its plans are for
    ("2026-11-18", "2026-11-18", BEFORE, OPEN, True),       # the retry slot's re-run of the same session
    ("2026-11-18", None, BEFORE, OPEN, True),               # the first record of a chain
    ("2026-11-06", "2026-11-17", BEFORE, OPEN, False),      # a backfill of an older session
    ("2026-11-18", "2026-11-17", AFTER, OPEN, False),       # made at the open: after the fact
    ("2026-11-18", "2026-11-17", None, OPEN, False),        # a clock it cannot read
    ("2026-11-18", "2026-11-17", BEFORE, None, False),
    ("2026-11-18", "2026-11-17", BEFORE, "soon", False),
])
def test_a_publication_is_forward_only_of_a_new_session_before_its_open(session, newest, made, opens, want):
    assert gl.forward(session, newest, made, opens) is want


def settled_have(block):
    return next(c for c in block["criteria"] if c["key"] == "settled_forward_plans")["have"]


def chained(block, session):
    """The record a night leaves on disk, as the next night reads it."""
    return {"run": {**previous_record(session=session)["run"], "go_live": block}}


def test_a_backfills_picks_are_never_forward_plans_whatever_the_rules_did():
    rules = {"plan": {"x": 1}, "universe": {"identity": "u1"}}
    prior = prior_with([], since="2026-10-01", session="2026-11-17", digest_rules=rules)
    rows = [{"bucket": "settled", "picked": d} for d in ("2026-11-06", "2026-11-10", "2026-11-17", "2026-11-18")]
    # a hand backfill of 6 November, made days later under unchanged rules
    backfill = build(session="2026-11-06", previous=prior, rows=rows, rules=rules,
                     published_at="2026-11-18T16:00:00+00:00", opens_at="2026-11-09T14:30:00+00:00")
    assert backfill["strategy"] == {"digest": gl.strategy_digest(rules), "since": "2026-10-01",
                                    "newest": "2026-11-17", "forward": False, "not_forward": ["2026-11-06"]}
    assert settled_have(backfill) == 3                        # every row but the backfill's own pick
    # the next evening reads the backfill's record on disk and still knows the newest session
    after = build(session="2026-11-18", previous=chained(backfill, "2026-11-06"), rows=rows, rules=rules)
    assert after["strategy"]["newest"] == "2026-11-18" and after["strategy"]["not_forward"] == ["2026-11-06"]
    assert after["strategy"]["since"] == "2026-10-01" and settled_have(after) == 3
    # a rule change first seen on a second backfill stands from after the newest session, not the backfill's own
    second = build(session="2026-11-10", previous=chained(backfill, "2026-11-06"), rows=rows, rules={"plan": {"x": 2}},
                   published_at="2026-11-18T17:00:00+00:00", opens_at="2026-11-11T14:30:00+00:00")
    assert second["strategy"]["since"] == "2026-11-18" and second["strategy"]["not_forward"] == ["2026-11-06", "2026-11-10"]
    assert settled_have(second) == 1


def test_a_run_made_at_or_after_the_open_its_plans_are_for_is_not_forward():
    rules = {"plan": {"x": 1}, "universe": {"identity": "u1"}}
    prior = prior_with([], since="2026-10-01", session="2026-11-17", digest_rules=rules)
    rows = [{"bucket": "settled", "picked": "2026-11-17"}, {"bucket": "settled", "picked": "2026-11-14"}]
    late = build(session="2026-11-17", previous=prior, rows=rows, rules=rules,
                 published_at="2026-11-18T14:30:00+00:00", opens_at="2026-11-18T14:30:00+00:00")
    assert late["strategy"]["not_forward"] == ["2026-11-17"] and settled_have(late) == 1
    # under changed rules such a run's own session is not the standing one either
    moved = build(session="2026-11-17", previous=prior, rows=rows, rules={"plan": {"x": 2}},
                  published_at="2026-11-18T16:00:00+00:00", opens_at="2026-11-18T14:30:00+00:00")
    assert moved["strategy"]["since"] == "2026-11-18" and settled_have(moved) == 0
    # the retry slot's re-run the same evening is forward, and marks nothing
    retry = build(session="2026-11-17", previous=prior, rows=rows, rules=rules,
                  published_at="2026-11-18T01:20:00+00:00", opens_at="2026-11-18T14:30:00+00:00")
    assert retry["strategy"]["not_forward"] == [] and settled_have(retry) == 2


def test_the_sessions_not_forward_are_sorted_bounded_and_read_as_dates():
    from src import sessions
    days, day = [], date(2026, 11, 17)
    for _ in range(gl.NOT_FORWARD_MAX + 3):
        day = sessions.previous_session(day)
        days.append(day.isoformat())
    kept = gl.not_forward_of({"not_forward": days + ["soon", 5, None]}, "2026-11-18", True)
    assert kept == sorted(days)[-gl.NOT_FORWARD_MAX:]
    assert gl.not_forward_of({"not_forward": "2026-11-17"}, "2026-11-18", False) == ["2026-11-18"]
    assert gl.not_forward_of({}, "2026-11-18", True) == []
    assert gl.not_forward_of({"not_forward": 5}, "2026-11-18", True) == []          # a list or nothing
    from src import record as rec
    assert gl.NOT_FORWARD_MAX >= rec.SCORECARD_SESSIONS       # no row the scorecard still reads is forgotten


@pytest.mark.parametrize("name", ["protocol", "ablation", "morning"])
def test_a_file_nested_past_the_decoders_depth_is_unread_and_never_raises(monkeypatch, tmp_path, name):
    deep = tmp_path / "deep.json"
    deep.write_text("[" * 200000 + "]" * 200000)
    with pytest.raises(RecursionError):
        json.loads(deep.read_text())
    if name == "protocol":
        monkeypatch.setattr(gl, "PROTOCOL_FILE", deep)
        assert gl.protocol("2026-11-18")["passed"] is False
    elif name == "ablation":
        monkeypatch.setattr(gl, "ABLATION_FILE", deep)
        assert gl.ablation() is False
    else:
        from src import pipeline
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "morning.json").write_bytes(deep.read_bytes())
        block = pipeline.read_go_live(docs, "2026-11-18", {"plan": {"x": 1}}, previous_record(), SHA, [],
                                      **evening_clock("2026-11-18"))
        assert block["ledger"][-1]["morning_on_time"] is False


def test_the_ablation_counts_only_as_results_computed_under_its_committed_spec(monkeypatch, tmp_path):
    committed = json.loads(gl.ABLATION_FILE.read_text())
    assert gl.ablation() is True and committed["version"] == gl.ABLATION_VERSION
    path = tmp_path / "ablation.json"
    monkeypatch.setattr(gl, "ABLATION_FILE", path)
    path.write_text(json.dumps(committed))
    assert gl.ablation() is True
    for change in ({"version": "ablation-v2"}, {"variants": {}}, {"variants": None}, {"spec": None},
                   {"spec": "docs/nowhere.json"}, {"spec_sha256": "0" * 64}, {"spec": "../outside.json"}):
        path.write_text(json.dumps({**committed, **change}))
        assert gl.ablation() is False, change
    path.write_text(json.dumps({"version": gl.ABLATION_VERSION}))      # a file with nothing but its version
    assert gl.ablation() is False
    # a spec outside the repository is not the committed one, whatever its bytes
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    spec = (ROOT / committed["spec"]).read_bytes()
    (repo / "docs" / "spec.json").write_bytes(spec)
    (tmp_path / "outside.json").write_bytes(spec)
    monkeypatch.setattr(gl, "ROOT", repo)
    path.write_text(json.dumps({**committed, "spec": "docs/spec.json"}))
    assert gl.ablation() is True
    path.write_text(json.dumps({**committed, "spec": "../outside.json"}))
    assert gl.ablation() is False


def test_report_validate_asks_the_gates_own_validator():
    data = record("next")
    report.validate(data)                                              # the record as the pipeline wrote it validates
    forged = copy.deepcopy(data)
    forged["run"]["go_live"]["sentence"] = 5
    with pytest.raises(ValueError, match="run.go_live ledger or sentence is not readable"):
        report.validate(forged)


@pytest.mark.parametrize("name, change, words", [
    ("since", lambda s: s.update(since="soon"), "strategy is not readable"),
    ("newest", lambda s: s.pop("newest"), "strategy is not readable"),
    ("not_forward", lambda s: s.update(not_forward=["2026-09-10", "2026-09-09"]), "strategy is not readable"),
    ("not_forward dates", lambda s: s.update(not_forward=["soon"]), "strategy is not readable"),
    ("not_forward list", lambda s: s.update(not_forward=None), "strategy is not readable"),
    ("forward", lambda s: s.update(forward="yes"), "strategy is not readable"),
    ("forward missing", lambda s: s.pop("forward"), "strategy is not readable"),
    ("digest", lambda s: s.update(digest="0" * 64), "strategy digest is not the record's own rules'"),
])
def test_the_validator_holds_the_standing_rules_block(name, change, words):
    data = record("next")
    assert gl.faults(data) == []
    change(data["run"]["go_live"]["strategy"])
    assert gl.faults(data) == ["run.go_live " + words], name
    whole = record("next")
    whole["run"]["go_live"]["strategy"] = "standing"
    assert gl.faults(whole) == ["run.go_live strategy is not readable"]


def test_the_schemas_live_ready_reasons_are_the_gates_criteria_and_the_unread_gate():
    schema = json.loads((ROOT / "docs" / "operations" / "orders-schema.json").read_text())
    reasons = schema["properties"]["live_ready"]["properties"]["reasons"]["items"]["enum"]
    assert reasons == list(gl.CRITERIA) + [orders.LIVE_READY_REASON]
    assert set(gl.REASONS) == set(gl.CRITERIA)


def _live(data):
    block = data["run"]["go_live"]
    block.update(ready=True, reasons=[])
    for c in block["criteria"]:
        c["met"] = True
    return data


def test_a_live_handoff_is_refused_while_the_committed_protocol_record_is_not_passed(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "data.json").write_text(json.dumps(_live(page("full"))))
    orders.write_publication(docs)
    assert json.loads((docs / "orders.json").read_text())["mode"] == "live"
    # the record and the file agree, and the committed protocol record (the suite's pinned copy) is unpassed
    assert orders.check(docs) == ["orders.json is live while the committed protocol record or ablation does not hold"]
    passed = tmp_path / "protocol.json"
    passed.write_text(json.dumps(owner_record(recorded_on=page("full")["run"]["session"])))
    monkeypatch.setattr(gl, "PROTOCOL_FILE", passed)
    assert orders.check(docs) == []
    monkeypatch.setattr(gl, "ABLATION_FILE", tmp_path / "nowhere.json")
    assert orders.check(docs) == ["orders.json is live while the committed protocol record or ablation does not hold"]


def test_a_handoff_written_under_an_earlier_version_is_paper_or_refused(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    raw = json.dumps(page("full")).encode()
    (docs / "data.json").write_bytes(raw)
    earlier = {"version": orders.VERSION - 1, "mode": "paper", "live_ready": {"value": False, "reasons": []},
               "source": {"data_sha256": hashlib.sha256(raw).hexdigest()}}
    (docs / "orders.json").write_text(json.dumps(earlier))
    assert orders.check(docs) == []
    for change in ({"mode": "live"}, {"live_ready": {"value": True, "reasons": []}}, {"live_ready": None}):
        (docs / "orders.json").write_text(json.dumps({**earlier, **change}))
        assert orders.check(docs) == ["orders.json written under an earlier version is not paper"], change


def test_the_forward_count_is_never_more_than_the_scorecards_settled_plans():
    data = record("next")
    have = _gate(data)[1]["settled_forward_plans"]["have"]
    assert have >= 1 and gl.faults(data) == []
    data["scorecard"]["settled"] = have                       # every settled plan a forward one: still the record's
    assert gl.faults(data) == []
    data["scorecard"]["settled"] = have - 1
    assert gl.faults(data) == ["run.go_live settled_forward_plans is more than the scorecard's settled plans"]


@pytest.mark.parametrize("unmet", gl.CRITERIA)
def test_a_handoff_is_written_and_meets_its_schema_with_any_one_condition_unmet(unmet):
    data = _live(page("full"))
    block = data["run"]["go_live"]
    next(c for c in block["criteria"] if c["key"] == unmet)["met"] = False
    block.update(ready=False, reasons=[unmet])
    doc = orders.build(json.dumps(data).encode())
    assert doc["mode"] == "paper" and doc["live_ready"] == {"value": False, "reasons": [unmet]}
    assert orders.problems(doc) == []
    assert unmet in gl.REASONS and gl.REASONS[unmet]


def test_the_guide_lists_each_reason_in_the_gates_own_words_and_names_what_the_gate_reads():
    note = (ROOT / "docs" / "operations" / "go-live.md").read_text()
    flat = " ".join(note.split())
    for code in gl.CRITERIA:
        assert f"| `{code}` | {gl.REASONS[code]} |" in note, code
    assert f"| `{orders.LIVE_READY_REASON}` |" in note
    for name in ("`go_live.PUBLISHED_STATUSES`", "`run.finish_seconds`", "`run.elapsed_seconds` is not the finish",
                 "`not_forward`", "How the morning check was started is not read at all",
                 "the gate judges the newest receipt, not the first"):
        assert name in flat, name
    readme = " ".join((ROOT / "README.md").read_text().split())
    assert "`run.finish_seconds`" in readme and "`run.go_live.strategy.not_forward`" in readme
    agent = " ".join((ROOT / "docs" / "operations" / "orders.md").read_text().split())
    assert "once written" not in agent and "[`go-live.md`](go-live.md)" in agent
    protocol = (ROOT / gl.PROTOCOL_NAME).read_text()
    assert "docs/operations/go-live.md" in protocol and "Completing the sitting is not passing it." in protocol


def test_the_gate_reads_the_protocol_record_against_tonights_session(monkeypatch, tmp_path):
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(owner_record(recorded_on="2026-11-19")))
    monkeypatch.setattr(gl, "PROTOCOL_FILE", path)
    assert "fidelity_protocol" in build(session="2026-11-18")["reasons"]         # dated after tonight's session
    later = build(session="2026-11-19", previous=previous_record(session="2026-11-18", applicable="2026-11-19",
                                                                 published="2026-11-18T22:20:00+00:00"))
    assert "fidelity_protocol" not in later["reasons"]


def test_a_publication_that_is_not_itself_forward_never_reads_live(monkeypatch, tmp_path):
    passed = tmp_path / "protocol.json"
    passed.write_text(json.dumps(owner_record(recorded_on="2026-11-01")))
    monkeypatch.setattr(gl, "PROTOCOL_FILE", passed)
    rules = {"plan": {"x": 1}, "universe": {"identity": "u1"}}
    # ten counted sessions ending 16 November, and the 17 November record on disk
    prior = prior_with([counted(d) for d in TEN], since="2026-10-01", session="2026-11-17", digest_rules=rules)
    rows = [{"bucket": "settled", "picked": "2026-10-15"}] * gl.MIN_SETTLED_FORWARD
    tonight = build(session="2026-11-18", previous=prior, rows=rows, rules=rules)
    assert tonight["ready"] is True and on_time(tonight)["have"] == 11
    # days later, with 19 and 20 November never published, a hand re-run of 18 November: the ledger still
    # ends on the session before the record's own, and the record is not a forward publication
    late = build(session="2026-11-18", previous=prior, rows=rows, rules=rules,
                 published_at="2026-11-23T21:30:00+00:00", opens_at="2026-11-19T14:30:00+00:00")
    assert late["ready"] is False and late["reasons"] == ["on_time_sessions"]
    assert on_time(late) == {"key": "on_time_sessions", "met": False, "have": 0, "need": gl.ON_TIME_SESSIONS,
                             "detail": f"0 consecutive of {gl.ON_TIME_SESSIONS}{gl.NOT_FORWARD_DETAIL}"}
    assert late["strategy"]["forward"] is False and late["strategy"]["not_forward"] == ["2026-11-18"]


def test_the_validator_reads_the_streak_as_zero_on_a_publication_that_is_not_forward():
    data = record("full")
    block, crit = _gate(data)
    session = data["run"]["session"]
    assert block["strategy"]["forward"] is True and gl.faults(data) == []
    # a block that says it is not forward and does not keep its own session
    block["strategy"]["forward"] = False
    assert gl.faults(data) == ["run.go_live names a publication that is not forward without keeping its session"]
    block["strategy"]["not_forward"] = [session]
    assert gl.faults(data) == []                                 # zero consecutive, as the fixture's first night has
    # and one that claims a run it may not count
    from src import sessions
    block["ledger"] = [{"session": sessions.previous_session(date.fromisoformat(session)).isoformat(), "counted": True}]
    crit["on_time_sessions"]["have"] = 1
    assert gl.faults(data) == ["run.go_live on_time_sessions is not the run its own ledger ends on before tonight"]
    block["strategy"]["forward"], block["strategy"]["not_forward"] = True, []
    assert gl.faults(data) == []


def test_the_gate_judges_the_newest_morning_receipt_on_main(tmp_path):
    from src import pipeline
    docs = tmp_path / "docs"
    docs.mkdir()
    prev = previous_record()
    (docs / "data.json").write_text(json.dumps(prev))
    sha = pipeline.previous_digest(docs)
    clock = evening_clock("2026-11-18")
    (docs / "morning.json").write_text(json.dumps(morning_for(sha, "2026-11-18T14:21:00+00:00")))      # 8:21 CT
    first = pipeline.read_go_live(docs, "2026-11-18", {"plan": {"x": 1}}, prev, sha, [], **clock)
    assert first["ledger"][-1]["counted"] is True
    # a later run for the same publication replaces the receipt: after the due time, or after the window
    for later in (morning_for(sha, "2026-11-18T14:50:00+00:00", status="observed"),
                  morning_for(sha, "2026-11-18T16:30:00+00:00", status="inapplicable")):
        (docs / "morning.json").write_text(json.dumps(later))
        block = pipeline.read_go_live(docs, "2026-11-18", {"plan": {"x": 1}}, prev, sha, [], **clock)
        assert block["ledger"][-1]["morning_on_time"] is False and block["ledger"][-1]["counted"] is False


def test_a_hand_revision_of_a_counted_session_closes_it_as_not_counted():
    # the session's first publication was scheduled and on time; a hand re-run replaced it on main that evening
    revised = previous_record(event="workflow_dispatch", flag=False, published="2026-11-18T01:00:00+00:00", elapsed=60.0)
    prior = {"run": {**revised["run"], "go_live": {"ledger": [counted("2026-11-14")]}}}
    block = build(previous=prior)
    assert [(r["session"], r["counted"]) for r in block["ledger"]] == [("2026-11-14", True), ("2026-11-17", False)]
    assert block["ledger"][-1]["automatic"] is False and on_time(block)["have"] == 0
