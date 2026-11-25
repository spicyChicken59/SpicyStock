"""The go-live gate (src/go_live.py) and what it does to orders.json.

The gate is version 2 and operational only (the owner's decision of 25
November 2026): two conditions, the owner's record of the Fidelity protocol
and ten sessions published and checked on time. No outcome is a condition.
These hold each condition to the case that meets it and each case that does
not, the ledger to the sessions it closes, the validator to the block's shape
under the gate version the record's own rules archived, and orders.json and
the page to the block. One test fails when a third condition, or any reading
of a scorecard, a settled count or an ablation, is added back.

Version 1 of the gate (19 to 24 November 2026) asked four conditions. Nothing
writes it now, so its validator is held on three real version-1 records,
frozen in tests/fixtures/go-live/v1-records.json by build_v1.py beside it.

Every clock here is pinned in the records the gate reads; the gate itself
reads no clock."""
from __future__ import annotations

import builtins
import copy
import hashlib
import inspect
import io
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from src import go_live as gl, orders, report

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "tests" / "fixtures" / "page"
V1_FILE = ROOT / "tests" / "fixtures" / "go-live" / "v1-records.json"
V1_BUILDER = ROOT / "tests" / "fixtures" / "go-live" / "build_v1.py"
#: the three frozen version-1 records: name, the whole commit git holds it at, its path, the file's SHA-256
V1_SOURCES = (
    ("2026-11-20", "f969d2f7cdbb8a613bae0d2ad3d22e3a34eb5979", "docs/data.json",
     "c88c9f246b47213be62584da1b7363a50e980a9d847ed9f2dc81467245eca6aa"),
    ("2026-11-23", "f82801e750e54ca7cc9a4fbb054cba9e6022877b", "docs/data.json",
     "467fd1f29228a3cb54accf1054a102cee6e67799fbe87b3bc0a8bf76ddb399c2"),
    ("next", "a00d3a30d2da7a5d9b1427c80cbc62d00a43d7ac", "tests/fixtures/page/next.json",
     "97dd167649178d718332502a47faa8157302f06a81d8038f29e711e4b95d9dd7"),
)
V1_NAMES = tuple(source[0] for source in V1_SOURCES)


def page(name: str) -> dict:
    return json.loads((PAGE / f"{name}.json").read_text())


def record(name: str) -> dict:
    """The fixture as the pipeline's record: without the label report.validate() refuses."""
    data = page(name)
    data.pop("fixture", None)
    return data


def frozen(name: str) -> dict:
    """One record made under version 1 of the gate, as the frozen file holds
    it: its rules, its session, its gate block and its count of settled
    plans. A fresh copy each time, so a test may forge it."""
    rows = {row["name"]: row for row in json.loads(V1_FILE.read_text())["records"]}
    return copy.deepcopy(rows[name]["record"])


def owner_record(**changes) -> dict:
    """The owner's record of a passed sitting, as the committed file's shape asks for it."""
    return {"version": 1, "protocol": "knowledge/broker-fidelity-protocol.md", "passed": True,
            "recorded_on": "2026-11-18", "recorded_by": "owner", "note": "", **changes}


def passed_record(monkeypatch, tmp_path, **changes) -> Path:
    """Point the gate at an owner's record that passes (or at one changed as given)."""
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(owner_record(**changes)))
    monkeypatch.setattr(gl, "PROTOCOL_FILE", path)
    return path


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
    """A ledger row closed counted: on time, started automatically and checked by a morning run in time."""
    return {"session": session, "on_time": True, "automatic": True, "morning_on_time": True, "counted": True}


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
TEN = ("2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06", "2026-11-09",
       "2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13", "2026-11-16")


def evening_clock(session: str) -> dict:
    """An evening run's own clock: started 5:20 PM ET on its session, its plans for the next one."""
    from src import sessions
    applicable = sessions.next_sessions(date.fromisoformat(session), 1)[0].isoformat()
    return {"published_at": f"{session}T22:20:00+00:00", "opens_at": f"{applicable}T14:30:00+00:00"}


def build(session="2026-11-18", previous=None, morning=None, sha=SHA, **clock):
    """One evening's gate: by default the evening after a counted 17 November."""
    return gl.build(session=session, previous=previous if previous is not None else previous_record(),
                    previous_sha256=sha, morning=morning if morning is not None else morning_for(SHA),
                    **{**evening_clock(session), **clock})


def prior_with(ledger, session="2026-11-17", newest=None):
    """The record on disk the evening before: its own session, its gate's
    ledger, and the newest session that gate remembers (its own when none is
    given)."""
    run = previous_record(session=session)["run"]
    block = {"version": gl.VERSION, "ledger": ledger, "publication": {"newest": newest or session, "forward": True}}
    return {"run": {**run, "go_live": block}}


def chained(block, session):
    """The record a night leaves on disk, as the next night reads it."""
    return {"run": {**previous_record(session=session)["run"], "go_live": block}}


def on_time(block):
    return next(c for c in block["criteria"] if c["key"] == "on_time_sessions")


def test_the_gate_is_paper_until_both_conditions_hold(monkeypatch, tmp_path):
    block = build()
    assert block["version"] == 2 and block["ready"] is False
    assert block["reasons"] == ["fidelity_protocol", "on_time_sessions"]
    assert block["sentence"].startswith("Paper only: fidelity protocol not met")
    ten = prior_with([counted(d) for d in TEN])
    # ten counted sessions and no passed record: paper, for that one reason
    assert build(previous=ten)["reasons"] == ["fidelity_protocol"]
    passed_record(monkeypatch, tmp_path)
    ready = build(previous=ten)
    assert ready["ready"] is True and ready["reasons"] == [] and ready["sentence"].startswith("Live ready")
    assert on_time(ready)["have"] == 11                          # the ten, and 17 November closed tonight
    # one session short of the ten, with the record passed: paper, for that one reason
    short = build(previous=prior_with([counted(d) for d in TEN[2:]]))
    assert on_time(short)["have"] == gl.ON_TIME_SESSIONS - 1
    assert short["ready"] is False and short["reasons"] == ["on_time_sessions"]
    assert short["sentence"] == f"Paper only: on time sessions not met (9 consecutive of {gl.ON_TIME_SESSIONS})."


def test_the_block_is_two_conditions_a_publication_and_a_ledger_and_nothing_else():
    block = build()
    assert set(block) == {"version", "ready", "criteria", "reasons", "publication", "ledger", "sentence"}
    assert [c["key"] for c in block["criteria"]] == ["fidelity_protocol", "on_time_sessions"]
    assert all(set(c) == {"key", "met", "have", "need", "detail"} for c in block["criteria"])
    assert block["publication"] == {"newest": "2026-11-18", "forward": True}
    assert on_time(block) == {"key": "on_time_sessions", "met": False, "have": 1, "need": gl.ON_TIME_SESSIONS,
                              "detail": f"1 consecutive of {gl.ON_TIME_SESSIONS}"}


def test_the_gate_is_operational_only_and_no_outcome_can_be_a_condition():
    """The owner's rule of 25 November 2026: the gate asks whether the broker
    was tested and whether the service runs on time, and nothing else, now or
    later. A third condition, an argument that hands the gate the rules or
    the scorecard, or a word of an outcome in ``build()`` fails here."""
    assert gl.VERSION == 2
    assert gl.CRITERIA == ("fidelity_protocol", "on_time_sessions") == gl.CRITERIA_BY_VERSION[gl.VERSION]
    assert set(gl.REASONS) == set(gl.CRITERIA) and sorted(gl.CRITERIA_BY_VERSION) == [1, 2]
    assert gl.RULES == {"go_live.version": 2, "go_live.on_time_sessions": gl.ON_TIME_SESSIONS,
                        "go_live.publish_by_et": gl.PUBLISH_BY_ET, "go_live.morning_due_ct": gl.MORNING_DUE_CT}
    assert tuple(inspect.signature(gl.build).parameters) == (
        "session", "previous", "previous_sha256", "morning", "published_at", "opens_at")
    source = inspect.getsource(gl.build)
    for word in ("scorecard", "settled", "ablation", "rules"):
        assert word not in source, word
    for gone in ("ablation", "ABLATION_FILE", "ABLATION_VERSION", "MIN_SETTLED_FORWARD", "first_forward_session",
                 "not_forward_of"):
        assert not hasattr(gl, gone), gone
    from src import pipeline
    assert tuple(inspect.signature(pipeline.read_go_live).parameters) == (
        "docs", "session", "previous", "previous_sha256", "published_at", "opens_at")
    # what a record archives today: the two operational numbers and their clocks, and no settled count
    for name in ("full", "next", "red"):
        assert page(name)["rules"]["go_live"] == {"version": 2, "on_time_sessions": gl.ON_TIME_SESSIONS,
                                                  "publish_by_et": gl.PUBLISH_BY_ET,
                                                  "morning_due_ct": gl.MORNING_DUE_CT}, name


def opened_during(monkeypatch, call):
    """Every file opened while ``call`` runs, and what it returned."""
    opened, real = [], io.open

    def spy(file, *args, **kwargs):
        opened.append(str(file))
        return real(file, *args, **kwargs)
    with monkeypatch.context() as patched:
        patched.setattr(io, "open", spy)
        patched.setattr(builtins, "open", spy)
        result = call()
    return opened, result


def test_the_gate_is_live_on_the_owners_record_and_ten_sessions_and_reads_no_other_file(monkeypatch, tmp_path):
    passed = passed_record(monkeypatch, tmp_path)
    prior = prior_with([counted(d) for d in TEN])
    build(previous=prior)                                        # once first, so every lazy import is done
    opened, block = opened_during(monkeypatch, lambda: build(previous=prior))
    # no scorecard was given and none was read; no ablation file exists to the gate
    assert block["ready"] is True and block["reasons"] == []
    assert opened == [str(passed)]


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


def test_a_revision_of_the_same_session_closes_nothing():
    same = build(session="2026-11-17")
    assert same["ledger"] == []


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
    assert block["version"] == 2 and block["ready"] is False
    assert block["reasons"] == ["fidelity_protocol", "on_time_sessions"]
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
    del older["run"]["go_live"]                             # a record from before the gate carries neither
    assert gl.faults(older) == []


def _live(data, check=True):
    """The record with its gate forged ready in a way its own validator accepts:
    the protocol recorded before tonight, and a ledger of ten counted sessions
    ending on the one before tonight's, each row's verdict its own facts'.
    ``check=False`` forges a block the validator is not asked to accept (a
    version-1 block under version 2's rules)."""
    from src import sessions
    session = data["run"]["session"]
    day, rows = date.fromisoformat(session), []
    for _ in range(gl.ON_TIME_SESSIONS):
        day = sessions.previous_session(day)
        rows.append({"session": day.isoformat(), "published_at": None, "on_time": True, "automatic": True,
                     "applicable_session": None, "morning_generated_at": None, "morning_status": "observed",
                     "morning_on_time": True, "counted": True})
    block = data["run"]["go_live"]
    block.update(ready=True, reasons=[], ledger=sorted(rows, key=lambda r: r["session"]),
                 publication={"newest": session, "forward": True})
    for c in block["criteria"]:
        c["met"] = True
        if c["key"] == "fidelity_protocol":
            c.update(have=session, detail="recorded as passed by the owner")
        if c["key"] == "on_time_sessions":
            c.update(have=gl.ON_TIME_SESSIONS, detail=f"{gl.ON_TIME_SESSIONS} consecutive of {gl.ON_TIME_SESSIONS}")
    block["sentence"] = gl.sentence(block)
    assert not check or gl.faults(data) == [], gl.faults(data)
    return data


def _unmet(data, key):
    """A ready record with one condition made unmet the way the gate would find it: the protocol not
    recorded, or the newest session of the run not counted (its morning check late)."""
    block = data["run"]["go_live"]
    crit = next(c for c in block["criteria"] if c["key"] == key)
    if key == "fidelity_protocol":
        crit.update(met=False, have=None, detail="not recorded as passed by the owner")
    else:
        block["ledger"][-1].update(morning_on_time=False, counted=False)
        crit.update(met=False, have=0, detail=f"0 consecutive of {gl.ON_TIME_SESSIONS}")
    block.update(ready=False, reasons=[c["key"] for c in block["criteria"] if c["met"] is not True])
    block["sentence"] = gl.sentence(block)
    assert gl.faults(data) == [], gl.faults(data)
    return data


def test_orders_json_is_paper_until_the_records_gate_is_ready():
    data = page("full")
    doc = orders.build(json.dumps(data).encode())
    assert doc["mode"] == "paper" and doc["live_ready"] == {"value": False, "reasons": data["run"]["go_live"]["reasons"]}
    assert doc["live_ready"]["reasons"] == ["fidelity_protocol", "on_time_sessions"]
    ready = _live(copy.deepcopy(data))
    live = orders.build(json.dumps(ready).encode())
    assert live["mode"] == "live" and live["live_ready"] == {"value": True, "reasons": []}
    assert orders.problems(live) == []
    for mutate in (lambda d: d["run"].pop("go_live"), lambda d: d["run"]["go_live"].update(version=99),
                   lambda d: d["run"]["go_live"].update(version=1),
                   lambda d: d["run"]["go_live"].update(reasons=["whatever"])):
        forged = copy.deepcopy(ready)
        mutate(forged)
        out = orders.build(json.dumps(forged).encode())
        assert out["mode"] == "paper" and out["live_ready"] == {"value": False, "reasons": [orders.LIVE_READY_REASON]}


@pytest.mark.parametrize("name", V1_NAMES)
def test_a_version_one_gate_block_never_makes_orders_json_live(name):
    """A record made under version 1 keeps its block, and the handoff reads it
    as a gate that was not evaluated: as it stands, and forged ready."""
    data = page("full")
    data["run"]["go_live"] = frozen(name)["run"]["go_live"]
    assert data["run"]["go_live"]["version"] == 1
    unread = {"value": False, "reasons": [orders.LIVE_READY_REASON]}
    doc = orders.build(json.dumps(data).encode())
    assert doc["mode"] == "paper" and doc["live_ready"] == unread
    # with only a reason version 2 also knows, it is still version 1's block
    data["run"]["go_live"]["reasons"] = ["fidelity_protocol"]
    assert orders.build(json.dumps(data).encode())["live_ready"] == unread
    doc = orders.build(json.dumps(_live(data, check=False)).encode())
    assert doc["mode"] == "paper" and doc["live_ready"] == unread
    assert orders.LIVE_READY_REASON == "go_live_gate_not_evaluated"


def go_live_names(text: str) -> set[str]:
    """Every ``go_live.NAME`` a document quotes."""
    return set(re.findall(r"`go_live\.([A-Za-z_]+)(?:\(\))?`", text))


def test_the_page_prints_the_gate_and_the_docs_name_its_numbers():
    js = (ROOT / "docs" / "app.js").read_text()
    body = js.split("function goLiveBlock(data)", 1)[1].split("\n  function ", 1)[0]
    assert "block.sentence" in body and "'absent'" in body and "'unreadable'" in body
    assert "card.appendChild(goLiveBlock(data));" in js
    note = " ".join((ROOT / "docs" / "operations" / "go-live.md").read_text().split())
    for name in ("ON_TIME_SESSIONS", "PUBLISH_BY_ET", "MORNING_DUE_CT", "LEDGER_MAX", "MORNING_RAN",
                 "PUBLISHED_STATUSES"):
        assert f"`go_live.{name}`" in note, name
    readme = " ".join((ROOT / "README.md").read_text().split())
    assert (f"the newest {gl.ON_TIME_SESSIONS} consecutive sessions published by {gl.PUBLISH_BY_ET} New York time"
            in readme)
    assert f"generated by {gl.MORNING_DUE_CT} Chicago time" in readme
    # neither document quotes a name the module no longer has
    quoted = go_live_names(note) | go_live_names(readme)
    assert {"ON_TIME_SESSIONS", "CRITERIA_BY_VERSION"} <= quoted
    assert all(hasattr(gl, name) for name in quoted), sorted(n for n in quoted if not hasattr(gl, n))


# ------------------------------------------------- the review's holes, closed --
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
    assert build()["reasons"] == ["fidelity_protocol", "on_time_sessions"] == list(gl.CRITERIA)


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


@pytest.mark.parametrize("raw", ["[]", '"passed"', "3", '{"passed": true, "recorded_on": "a date", "recorded_by": "owner"}'])
def test_a_protocol_record_that_is_not_an_owners_dated_object_is_unpassed_and_never_raises(monkeypatch, tmp_path, raw):
    path = tmp_path / "p.json"
    path.write_text(raw)
    monkeypatch.setattr(gl, "PROTOCOL_FILE", path)
    assert gl.protocol()["passed"] is False
    assert build()["reasons"][0] == "fidelity_protocol"


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
    doc = orders.build(json.dumps(_live(page("full"))).encode())
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
    block = pipeline.read_go_live(docs, "2026-11-18", prev, sha)
    assert block["version"] == 2 and block["ledger"][-1]["counted"] is True
    (docs / "morning.json").write_text(json.dumps(morning_for("c" * 64)))
    block = pipeline.read_go_live(docs, "2026-11-18", prev, sha)
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
    assert gl.newest_published({"run": {"session": "soon"}}, {"publication": {"newest": 5}}) is None
    assert gl.newest_published({"run": {"session": "2026-11-17"}}, {"publication": {"newest": "soon"}}) == "2026-11-17"
    block = build(previous={"run": {"session": "soon", "go_live": {"ledger": [{"session": "x", "counted": True}],
                                                                    "publication": "newest"}}})
    assert block["ledger"] == [] and block["publication"] == {"newest": "2026-11-18", "forward": True}


def test_the_sentence_names_each_unmet_condition_with_its_detail():
    block = build()
    unmet = [c for c in block["criteria"] if not c["met"]]
    assert len(unmet) == 2
    assert block["sentence"] == "Paper only: " + "; ".join(
        f"{c['key'].replace('_', ' ')} not met ({c['detail']})" for c in unmet) + "."
    # the previous session closed counted; the sentence carries each condition's own detail and no other
    assert block["sentence"] == ("Paper only: fidelity protocol not met (not recorded as passed by the owner); "
                                 f"on time sessions not met (1 consecutive of {gl.ON_TIME_SESSIONS}).")


def test_a_protocol_record_that_is_missing_or_no_file_is_unpassed_and_never_raises(monkeypatch, tmp_path):
    for path in (tmp_path / "missing.json", tmp_path):                    # absent, and a directory
        monkeypatch.setattr(gl, "PROTOCOL_FILE", path)
        assert gl.protocol() == {"passed": False, "recorded_on": None, "detail": "no readable record of the protocol"}
        assert build()["reasons"][0] == "fidelity_protocol"
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
    # the protocol record is the one file the shipped module names: it has no path to an ablation
    assert [name for name in vars(shipped) if name.endswith("_FILE")] == ["PROTOCOL_FILE", "PINNED_PROTOCOL_FILE"]
    note = (ROOT / "docs" / "operations" / "go-live.md").read_text()
    assert "knowledge/go-live/fidelity-protocol.json" in note
    # the evening itself reads the module's path and nothing pins it there
    assert "PROTOCOL_FILE" not in (ROOT / "src" / "pipeline.py").read_text()


@pytest.mark.parametrize("reasons", [{}, None, "fidelity_protocol", 0, [None]])
def test_a_gate_whose_reasons_are_no_list_of_its_own_words_is_paper_and_says_it_was_not_read(reasons):
    data = _live(page("full"))
    data["run"]["go_live"].update(reasons=reasons)
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


def test_the_next_nights_gate_closes_the_night_before_as_not_counted():
    data = page("next")
    block = data["run"]["go_live"]
    # its ledger closed the night before, which no schedule started and no morning checked
    assert [r["session"] for r in block["ledger"]] == ["2026-09-10"]
    assert block["ledger"][0]["counted"] is False and block["ledger"][0]["automatic"] is None
    assert block["publication"] == {"newest": data["run"]["session"], "forward": True}
    assert on_time(block)["have"] == 0 and gl.faults(data) == []
    # the scorecard has settled plans that night, and the gate's block says nothing of them
    assert data["scorecard"]["settled"] >= 1 and "settled" not in json.dumps(block)


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
    assert first["run"]["go_live"]["publication"] == {"newest": "2026-09-10", "forward": True}
    assert second["run"]["go_live"]["publication"] == {"newest": "2026-09-11", "forward": True}
    # the evening's gate is this version's two conditions, archived as the rules say
    for night in (first, second):
        assert night["rules"]["go_live"]["version"] == night["run"]["go_live"]["version"] == gl.VERSION
        assert [c["key"] for c in night["run"]["go_live"]["criteria"]] == list(gl.CRITERIA)


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


# ---------------------------------------------------- a forward publication --
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


def test_a_backfill_is_not_forward_and_the_next_evening_still_knows_the_newest_session():
    prior = prior_with([counted(d) for d in TEN])               # the 17 November record on disk
    # a hand backfill of 6 November, made days later
    backfill = build(session="2026-11-06", previous=prior,
                     published_at="2026-11-18T16:00:00+00:00", opens_at="2026-11-09T14:30:00+00:00")
    assert backfill["publication"] == {"newest": "2026-11-17", "forward": False}
    assert on_time(backfill)["have"] == 0 and on_time(backfill)["detail"].endswith(gl.NOT_FORWARD_DETAIL)
    # the next evening reads the backfill's record on disk, the older session, and still knows the newest
    after = build(session="2026-11-18", previous=chained(backfill, "2026-11-06"))
    assert after["publication"] == {"newest": "2026-11-18", "forward": True}
    # the backfill replaced 6 November's row as not counted, so the run starts over after it
    assert [r["session"] for r in after["ledger"] if r["counted"] is not True] == ["2026-11-06"]
    assert on_time(after)["have"] == 7 and not on_time(after)["detail"].endswith(gl.NOT_FORWARD_DETAIL)
    # a second backfill, read over the first one's record: newer than the record on disk, with a clock
    # before its own open, and still older than the newest session the chain remembers
    second = build(session="2026-11-10", previous=chained(backfill, "2026-11-06"))
    assert second["publication"] == {"newest": "2026-11-17", "forward": False}
    assert on_time(second)["have"] == 0


def test_a_run_made_at_or_after_the_open_its_plans_are_for_is_not_forward(monkeypatch, tmp_path):
    passed_record(monkeypatch, tmp_path, recorded_on="2026-11-01")
    # ten counted sessions ending 16 November, and a re-run of 17 November over its own record
    prior = prior_with([counted(d) for d in TEN])
    late = build(session="2026-11-17", previous=prior,
                 published_at="2026-11-18T14:30:00+00:00", opens_at="2026-11-18T14:30:00+00:00")
    assert late["publication"] == {"newest": "2026-11-17", "forward": False}
    assert late["ready"] is False and late["reasons"] == ["on_time_sessions"]
    assert on_time(late) == {"key": "on_time_sessions", "met": False, "have": 0, "need": gl.ON_TIME_SESSIONS,
                             "detail": f"0 consecutive of {gl.ON_TIME_SESSIONS}{gl.NOT_FORWARD_DETAIL}"}
    # a second before that open it is forward, and so is the retry slot's re-run the same evening
    for made in ("2026-11-18T14:29:59+00:00", "2026-11-18T01:20:00+00:00"):
        retry = build(session="2026-11-17", previous=prior, published_at=made, opens_at="2026-11-18T14:30:00+00:00")
        assert retry["publication"] == {"newest": "2026-11-17", "forward": True}, made
        assert retry["ready"] is True and on_time(retry)["have"] == 10


def test_a_publication_that_is_not_itself_forward_never_reads_live(monkeypatch, tmp_path):
    passed_record(monkeypatch, tmp_path, recorded_on="2026-11-01")
    # ten counted sessions ending 16 November, and the 17 November record on disk
    prior = prior_with([counted(d) for d in TEN])
    tonight = build(session="2026-11-18", previous=prior)
    assert tonight["ready"] is True and on_time(tonight)["have"] == 11
    # days later, with 19 and 20 November never published, a hand re-run of 18 November: the ledger still
    # ends on the session before the record's own, and the record is not a forward publication
    late = build(session="2026-11-18", previous=prior,
                 published_at="2026-11-23T21:30:00+00:00", opens_at="2026-11-19T14:30:00+00:00")
    assert late["ready"] is False and late["reasons"] == ["on_time_sessions"]
    assert on_time(late) == {"key": "on_time_sessions", "met": False, "have": 0, "need": gl.ON_TIME_SESSIONS,
                             "detail": f"0 consecutive of {gl.ON_TIME_SESSIONS}{gl.NOT_FORWARD_DETAIL}"}
    assert late["publication"] == {"newest": "2026-11-18", "forward": False}
    assert late["sentence"] == (f"Paper only: on time sessions not met (0 consecutive of {gl.ON_TIME_SESSIONS}"
                                f"{gl.NOT_FORWARD_DETAIL}).")


def test_the_first_version_two_night_carries_a_version_one_ledger_and_its_newest_session():
    """The ledger's rows are the same under both versions, so the run of
    on-time sessions carries across the change; and version 1 kept the newest
    published session under ``strategy``, where version 2 still reads it."""
    v1 = frozen("2026-11-23")["run"]["go_live"]
    assert [r["session"] for r in v1["ledger"]] == ["2026-11-19", "2026-11-20"] and v1["strategy"]["newest"] == "2026-11-23"
    on_disk = {"run": {**previous_record(session="2026-11-23", published="2026-11-23T22:20:00+00:00",
                                         applicable="2026-11-24")["run"], "go_live": v1}}
    block = build(session="2026-11-24", previous=on_disk, morning=morning_for(SHA, "2026-11-24T14:21:00+00:00"))
    assert block["version"] == 2 and "strategy" not in block
    assert block["ledger"][:2] == v1["ledger"]
    assert [(r["session"], r["counted"]) for r in block["ledger"]] == [("2026-11-19", False), ("2026-11-20", False),
                                                                      ("2026-11-23", True)]
    assert block["publication"] == {"newest": "2026-11-24", "forward": True} and on_time(block)["have"] == 1
    # after a backfill under version 1 the record on disk is the older session; its block still names the newest
    assert gl.newest_published({"run": {"session": "2026-11-06"}}, v1) == "2026-11-23"
    assert gl.newest_published({"run": {"session": "2026-11-06"}}, {"strategy": {"newest": "soon"}}) == "2026-11-06"
    # a version-2 block's own word comes first
    both = {"publication": {"newest": "2026-11-24"}, "strategy": {"newest": "2026-11-23"}}
    assert gl.newest_published({"run": {"session": "2026-11-06"}}, both) == "2026-11-24"
    # so a run of 20 November over that backfill's record, its clock before its own open, is not forward
    older = {"run": {**previous_record(session="2026-11-06")["run"], "go_live": v1}}
    again = build(session="2026-11-20", previous=older)
    assert again["publication"] == {"newest": "2026-11-23", "forward": False} and on_time(again)["have"] == 0


@pytest.mark.parametrize("name", ["protocol", "morning"])
def test_a_file_nested_past_the_decoders_depth_is_unread_and_never_raises(monkeypatch, tmp_path, name):
    deep = tmp_path / "deep.json"
    deep.write_text("[" * 200000 + "]" * 200000)
    with pytest.raises(RecursionError):
        json.loads(deep.read_text())
    if name == "protocol":
        monkeypatch.setattr(gl, "PROTOCOL_FILE", deep)
        assert gl.protocol("2026-11-18")["passed"] is False
    else:
        from src import pipeline
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "morning.json").write_bytes(deep.read_bytes())
        block = pipeline.read_go_live(docs, "2026-11-18", previous_record(), SHA, **evening_clock("2026-11-18"))
        assert block["ledger"][-1]["morning_on_time"] is False


def test_the_gate_reads_the_protocol_record_against_tonights_session(monkeypatch, tmp_path):
    passed_record(monkeypatch, tmp_path, recorded_on="2026-11-19")
    assert "fidelity_protocol" in build(session="2026-11-18")["reasons"]         # dated after tonight's session
    later = build(session="2026-11-19", previous=previous_record(session="2026-11-18", applicable="2026-11-19",
                                                                 published="2026-11-18T22:20:00+00:00"))
    assert "fidelity_protocol" not in later["reasons"]


def test_the_gate_judges_the_newest_morning_receipt_on_main(tmp_path):
    from src import pipeline
    docs = tmp_path / "docs"
    docs.mkdir()
    prev = previous_record()
    (docs / "data.json").write_text(json.dumps(prev))
    sha = pipeline.previous_digest(docs)
    clock = evening_clock("2026-11-18")
    (docs / "morning.json").write_text(json.dumps(morning_for(sha, "2026-11-18T14:21:00+00:00")))      # 8:21 CT
    first = pipeline.read_go_live(docs, "2026-11-18", prev, sha, **clock)
    assert first["ledger"][-1]["counted"] is True
    # a later run for the same publication replaces the receipt: after the due time, or after the window
    for later in (morning_for(sha, "2026-11-18T14:50:00+00:00", status="observed"),
                  morning_for(sha, "2026-11-18T16:30:00+00:00", status="inapplicable")):
        (docs / "morning.json").write_text(json.dumps(later))
        block = pipeline.read_go_live(docs, "2026-11-18", prev, sha, **clock)
        assert block["ledger"][-1]["morning_on_time"] is False and block["ledger"][-1]["counted"] is False


def test_a_hand_revision_of_a_counted_session_closes_it_as_not_counted():
    # the session's first publication was scheduled and on time; a hand re-run replaced it on main that evening
    revised = previous_record(event="workflow_dispatch", flag=False, published="2026-11-18T01:00:00+00:00", elapsed=60.0)
    prior = {"run": {**revised["run"], "go_live": {"ledger": [counted("2026-11-14")]}}}
    block = build(previous=prior)
    assert [(r["session"], r["counted"]) for r in block["ledger"]] == [("2026-11-14", True), ("2026-11-17", False)]
    assert block["ledger"][-1]["automatic"] is False and on_time(block)["have"] == 0


# ------------------------------------------------------ version 2's validator --
def _gate(data):
    block = data["run"]["go_live"]
    return block, {c["key"]: c for c in block["criteria"]}


LIVE_SENTENCE = "Live ready: every go-live condition holds; orders.json is no longer paper only."
THIRD = {"key": "settled_forward_plans", "met": True, "have": 20, "need": 20, "detail": "20 settled of 20"}


@pytest.mark.parametrize("name, change, words", [
    ("version", lambda b, c: b.update(version=gl.VERSION + 1), "is missing or not this version"),
    ("version one", lambda b, c: b.update(version=1), "is missing or not this version"),
    ("version a float", lambda b, c: b.update(version=2.0), "is missing or not this version"),
    ("ready", lambda b, c: b.update(ready=True), "ready is not its criteria's"),
    ("ready missing", lambda b, c: b.pop("ready"), "ready is not its criteria's"),
    ("no reason", lambda b, c: b.update(reasons=[]), "reasons are not its unmet criteria"),
    ("one reason of two", lambda b, c: b.update(reasons=["on_time_sessions"]), "reasons are not its unmet criteria"),
    ("reasons out of order", lambda b, c: b["reasons"].reverse(), "reasons are not its unmet criteria"),
    ("a reason of version one", lambda b, c: b["reasons"].append("settled_forward_plans"),
     "reasons are not its unmet criteria"),
    ("a third criterion", lambda b, c: b["criteria"].append(dict(THIRD)), "criteria are not the gate's"),
    ("a criterion dropped", lambda b, c: b["criteria"].pop(), "criteria are not the gate's"),
    ("criteria out of order", lambda b, c: b["criteria"].reverse(), "criteria are not the gate's"),
    ("publication missing", lambda b, c: b.pop("publication"), "publication is not readable"),
    ("publication a word", lambda b, c: b.update(publication="forward"), "publication is not readable"),
    ("publication extra key", lambda b, c: b["publication"].update(not_forward=[]), "publication is not readable"),
    ("publication key missing", lambda b, c: b["publication"].pop("forward"), "publication is not readable"),
    ("newest not a date", lambda b, c: b["publication"].update(newest="soon"), "publication is not readable"),
    ("forward not a bool", lambda b, c: b["publication"].update(forward="yes"), "publication is not readable"),
    ("newest older", lambda b, c: b["publication"].update(newest="2026-09-10"),
     "publication names a newest session older than the record's own"),
    ("have", lambda b, c: c["on_time_sessions"].update(have=1),
     "on_time_sessions is not the run its own ledger ends on before tonight"),
    ("need", lambda b, c: c["on_time_sessions"].update(need=1), "on_time_sessions is not its count against the archived need"),
    ("met", lambda b, c: c["on_time_sessions"].update(met=True), "on_time_sessions is not its count against the archived need"),
    ("have a word", lambda b, c: c["on_time_sessions"].update(have="0"),
     "on_time_sessions is not its count against the archived need"),
    ("sentence says live", lambda b, c: b.update(sentence=LIVE_SENTENCE), "sentence is not its criteria's"),
    ("sentence padded", lambda b, c: b.update(sentence=b["sentence"] + " "), "sentence is not its criteria's"),
    ("sentence a number", lambda b, c: b.update(sentence=5), "ledger or sentence is not readable"),
    ("ledger", lambda b, c: b.update(ledger="2026-09-10"), "ledger or sentence is not readable"),
    ("ledger none", lambda b, c: b.update(ledger=None), "ledger or sentence is not readable"),
    ("met a word", lambda b, c: c["fidelity_protocol"].update(met="no"), "criteria are not readable"),
    ("detail missing", lambda b, c: c["on_time_sessions"].pop("detail"), "criteria are not readable"),
    ("row", lambda b, c: b["ledger"].append({"counted": True}), "ledger rows are not readable"),
    ("row date", lambda b, c: b["ledger"].append({"session": "soon", "counted": True}), "ledger rows are not readable"),
    ("row a word", lambda b, c: b["ledger"].append("2026-09-09"), "ledger rows are not readable"),
])
def test_the_validator_names_each_forged_part_of_the_gate(name, change, words):
    data = record("next")                                     # its ledger has a row
    assert gl.faults(data) == [] and data["run"]["go_live"]["ledger"] and data["run"]["session"] == "2026-09-11"
    report.validate(data)
    forged = copy.deepcopy(data)
    change(*_gate(forged))
    found = gl.faults(forged)
    assert any(f == "run.go_live " + words for f in found), (name, found)
    with pytest.raises(ValueError, match=re.escape("run.go_live " + words)):
        report.validate(forged)


@pytest.mark.parametrize("name, change, words", [
    ("extra key", lambda b, c: b["publication"].update(since="2026-09-10"), "publication is not readable"),
    ("newest older", lambda b, c: b["publication"].update(newest="2026-09-10"),
     "publication names a newest session older than the record's own"),
    ("sentence", lambda b, c: b.update(sentence=LIVE_SENTENCE), "sentence is not its criteria's"),
    ("need", lambda b, c: c["on_time_sessions"].update(need=1), "on_time_sessions is not its count against the archived need"),
    ("have", lambda b, c: c["on_time_sessions"].update(have=1),
     "on_time_sessions is not the run its own ledger ends on before tonight"),
])
def test_a_forgery_of_one_part_is_that_one_fault_and_no_other(name, change, words):
    data = record("next")
    change(*_gate(data))
    assert gl.faults(data) == ["run.go_live " + words], name


def test_the_count_is_held_to_the_need_the_records_own_rules_archived():
    data = record("next")
    block, crit = _gate(data)
    assert data["rules"]["go_live"]["on_time_sessions"] == crit["on_time_sessions"]["need"] == gl.ON_TIME_SESSIONS
    # a record whose rules archived another need is held to that one, not to today's constant
    data["rules"]["go_live"]["on_time_sessions"] = 5
    assert gl.faults(data) == ["run.go_live on_time_sessions is not its count against the archived need"]
    crit["on_time_sessions"]["need"] = 5
    assert gl.faults(data) == []
    # and met is the count against that need: five counted sessions meet a need of five
    crit["on_time_sessions"].update(have=5, met=True)
    block["ledger"] = [counted(d) for d in ("2026-09-03", "2026-09-04", "2026-09-08", "2026-09-09", "2026-09-10")]
    block["reasons"] = ["fidelity_protocol"]
    block["sentence"] = gl.sentence(block)
    assert gl.faults(data) == []
    crit["on_time_sessions"]["met"] = False
    block["reasons"] = ["fidelity_protocol", "on_time_sessions"]
    block["sentence"] = gl.sentence(block)
    assert gl.faults(data) == ["run.go_live on_time_sessions is not its count against the archived need"]
    # rules that archive no need hold no count
    del data["rules"]["go_live"]["on_time_sessions"]
    assert "run.go_live on_time_sessions is not its count against the archived need" in gl.faults(data)


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


def test_the_validator_anchors_the_streak_to_the_records_own_session():
    data = page("full")
    block, crit = _gate(data)
    block["ledger"] = [counted(d) for d in TEN]               # ten counted sessions ending 16 November
    crit["on_time_sessions"].update(have=10, met=True)
    block["reasons"] = [c["key"] for c in block["criteria"] if c["met"] is not True]
    block["sentence"] = gl.sentence(block)
    words = "run.go_live on_time_sessions is not the run its own ledger ends on before tonight"
    # the session after the ledger's last: the run stands
    data["run"]["session"] = block["publication"]["newest"] = "2026-11-17"
    assert gl.faults(data) == []
    # a session was missed: the run is broken
    data["run"]["session"] = block["publication"]["newest"] = "2026-11-18"
    assert gl.faults(data) == [words]
    data["run"]["session"] = "tonight"
    assert gl.faults(data) == ["run.go_live ledger rows are not readable"]


def test_the_validator_reads_the_streak_as_zero_on_a_publication_that_is_not_forward():
    data = record("next")
    block, crit = _gate(data)
    assert block["publication"]["forward"] is True and gl.faults(data) == []
    # a block that says it is not forward and counts nothing validates: zero consecutive, as that night has
    block["publication"]["forward"] = False
    assert gl.faults(data) == []
    # the night before closed counted, and the block counts it: held while the publication is forward
    block["ledger"] = [counted("2026-09-10")]
    crit["on_time_sessions"]["have"] = 1
    block["publication"]["forward"] = True
    assert gl.faults(data) == []
    # and refused when it is not: a publication that is not forward may count no run
    block["publication"]["forward"] = False
    assert gl.faults(data) == ["run.go_live on_time_sessions is not the run its own ledger ends on before tonight"]
    crit["on_time_sessions"]["have"] = 0
    assert gl.faults(data) == []


def test_a_block_without_its_ready_is_named_and_never_raises():
    data = record("next")
    del data["run"]["go_live"]["ready"]
    assert gl.faults(data) == ["run.go_live ready is not its criteria's"]
    with pytest.raises(ValueError, match="run.go_live ready is not its criteria's"):
        report.validate(data)
    # the sentence of a block with no ready is the paper one: a missing ready is not ready
    assert gl.sentence(data["run"]["go_live"]).startswith("Paper only: ")


def _paths(node, here=()):
    """Every path into a JSON value, the value's own first."""
    yield here
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _paths(value, here + (key,))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _paths(value, here + (index,))


def _slim(data: dict) -> dict:
    """The parts of a record the gate's validator reads, and no more."""
    return {"rules": data["rules"], "run": {"session": data["run"]["session"], "go_live": data["run"]["go_live"],
                                            "published_at": data["run"]["published_at"],
                                            "timing": {"opens_at": data["run"]["timing"]["opens_at"]}},
            "scorecard": {"settled": data["scorecard"]["settled"]}}


SHAPES = ("x", [1], 5, None, True, {}, 1.5, [], {"a": 1})


@pytest.mark.parametrize("name", ["full", "next", "v1 2026-11-23", "v1 next"])
def test_the_validator_names_a_shape_it_cannot_read_and_never_raises(name):
    """Under each version: every key of the gate's block, of the archived
    gate rules and the session, deleted and replaced by each shape in turn.
    The validator answers with a list of sentences, whatever it is given."""
    data = frozen(name[3:]) if name.startswith("v1 ") else _slim(record(name))
    assert gl.faults(data) == []
    cases = 0
    for where in (("run", "go_live"), ("rules", "go_live"), ("run", "session")):
        root = data
        for key in where:
            root = root[key]
        for path in _paths(root):
            for shape in SHAPES + ("<deleted>",):
                forged = {**data, "rules": {**data["rules"], "go_live": copy.deepcopy(data["rules"]["go_live"])},
                          "run": copy.deepcopy(data["run"])}
                node, full = forged, where + path
                for key in full[:-1]:
                    node = node[key]
                if shape == "<deleted>":
                    del node[full[-1]]
                else:
                    node[full[-1]] = shape
                found = gl.faults(forged)
                assert isinstance(found, list) and all(isinstance(f, str) for f in found), (full, shape)
                cases += 1
    assert cases > 200
    # each key of the block is held: without any one of them the record is refused by name
    for key in data["run"]["go_live"]:
        forged = {**data, "run": copy.deepcopy(data["run"])}
        del forged["run"]["go_live"][key]
        assert gl.faults(forged) and all(f.startswith("run.go_live ") for f in gl.faults(forged)), key


def test_report_validate_asks_the_validator_of_the_version_the_rules_archived():
    data = record("next")
    report.validate(data)                                              # the record as the pipeline wrote it validates
    forged = copy.deepcopy(data)
    forged["run"]["go_live"]["sentence"] = 5
    with pytest.raises(ValueError, match="run.go_live ledger or sentence is not readable"):
        report.validate(forged)
    # the same night's record with version 1's archived rules and version 1's block: version 1's validator
    # is asked, and finds nothing; what refuses the transplant is the record's own seal, not the gate
    v1 = frozen("next")
    whole = copy.deepcopy(data)
    whole["rules"]["go_live"], whole["run"]["go_live"] = v1["rules"]["go_live"], v1["run"]["go_live"]
    whole["run"]["go_live"]["strategy"]["digest"] = gl.strategy_digest(whole["rules"])
    assert gl.faults(whole) == []
    with pytest.raises(ValueError) as sealed:
        report.validate(whole)
    assert "go_live" not in str(sealed.value) and "go-live" not in str(sealed.value)
    whole["run"]["go_live"]["strategy"]["digest"] = "0" * 64
    with pytest.raises(ValueError, match=re.escape("run.go_live strategy digest is not the record's own rules'")):
        report.validate(whole)


# ------------------------------------------------ version 1, frozen as it stood --
def test_the_frozen_version_one_records_name_their_sources_by_whole_commit():
    document = json.loads(V1_FILE.read_text())
    assert set(document) == {"about", "records"}
    assert [(r["name"], r["source"]["commit"], r["source"]["path"], r["source"]["sha256"])
            for r in document["records"]] == list(V1_SOURCES)
    for row in document["records"]:
        assert set(row) == {"name", "source", "record"} and set(row["record"]) == {"rules", "run", "scorecard"}
        assert set(row["record"]["run"]) == {"session", "go_live"} and set(row["record"]["scorecard"]) == {"settled"}
        assert re.fullmatch(r"[0-9a-f]{40}", row["source"]["commit"])
    # the builder freezes exactly these, and only records made under version 1
    builder = V1_BUILDER.read_text()
    for name, commit, path, _ in V1_SOURCES:
        assert f'("{name}", "{commit}", "{path}")' in builder, name
    assert "was not made under version 1 of the gate" in builder


def test_the_frozen_version_one_records_are_what_git_holds():
    """The frozen file is read from git by whole commit id. A shallow
    checkout, CI's, carries only its tip, so the three commits are fetched
    here, exactly those and once; when they cannot be had this test fails
    with the reason and is never skipped. No other test here needs git."""
    commits = [commit for _, commit, _, _ in V1_SOURCES]

    def present(commit: str) -> bool:
        return subprocess.run(["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=ROOT,
                              capture_output=True).returncode == 0
    missing = [c for c in commits if not present(c)]
    if missing:
        done = subprocess.run(["git", "fetch", "--quiet", "--no-tags", "--depth=1", "origin", *missing],
                              cwd=ROOT, capture_output=True, text=True)
        assert done.returncode == 0 and all(present(c) for c in missing), \
            f"{len(missing)} commits the frozen records name are not in this checkout and could not be fetched: {done.stderr.strip()}"
    done = subprocess.run([sys.executable, str(V1_BUILDER), "--check"], cwd=ROOT, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout.strip() == f"go-live v1 records: {len(V1_SOURCES)} records current"


def _builder():
    import importlib.util
    spec = importlib.util.spec_from_file_location("go_live_build_v1", V1_BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_builder_freezes_only_version_one_records_and_its_check_can_fail(monkeypatch, tmp_path, capsys):
    builder = _builder()
    assert [source for source in builder.SOURCES] == [source[:3] for source in V1_SOURCES]
    whole = {name: {**frozen(name), "extra": "a part the validator does not read"} for name in V1_NAMES}
    raws = {commit: json.dumps(whole[name]).encode() for name, commit, _, _ in V1_SOURCES}
    monkeypatch.setattr(builder, "read_at", lambda commit, path: raws[commit])
    out = tmp_path / "v1-records.json"
    monkeypatch.setattr(builder, "OUTPUT", out)
    assert builder.main([]) == 0
    written = json.loads(out.read_text())
    assert [r["record"] for r in written["records"]] == [frozen(name) for name in V1_NAMES]
    assert [r["source"]["sha256"] for r in written["records"]] == [
        hashlib.sha256(raws[commit]).hexdigest() for _, commit, _, _ in V1_SOURCES]
    assert builder.main(["--check"]) == 0
    # a changed byte of the committed file, or of what git holds, is not current
    out.write_bytes(out.read_bytes() + b" ")
    assert builder.main(["--check"]) == 1 and "is not what git holds" in capsys.readouterr().err
    out.unlink()
    assert builder.main(["--check"]) == 1
    # a record made under version 2 is refused by name, and nothing is written
    raws[V1_SOURCES[0][1]] = json.dumps(_slim(record("next"))).encode()
    assert builder.main([]) == 1 and not out.exists()
    assert "was not made under version 1 of the gate" in capsys.readouterr().err


@pytest.mark.parametrize("name", V1_NAMES)
def test_a_record_made_under_version_one_still_validates_under_its_own_rules(name):
    data = frozen(name)
    block = data["run"]["go_live"]
    assert data["rules"]["go_live"]["version"] == block["version"] == 1 == gl.archived_version(data["rules"])
    assert [c["key"] for c in block["criteria"]] == list(gl.CRITERIA_BY_VERSION[1]) == [
        "fidelity_protocol", "on_time_sessions", "settled_forward_plans", "ablation_report"]
    assert data["rules"]["go_live"]["min_settled_forward"] == 20
    assert gl.faults(data) == []
    # its digest is version 1's digest of the record's own rules, which this code still computes
    assert block["strategy"]["digest"] == gl.strategy_digest(data["rules"])


def test_the_strategy_digest_ignores_only_the_membership_and_the_event_registry():
    a = {"plan": {"x": 1}, "universe": {"identity": "u1", "max_discovery": 8000},
         "event_risk": {"version": 1, "registry": {"reviewed_on": "2026-11-19"}, "registry_sha256": "r1"}}
    assert gl.strategy_digest(a) == gl.strategy_digest({**a, "universe": {"identity": "u2", "max_discovery": 8000}})
    assert gl.strategy_digest(a) != gl.strategy_digest({**a, "universe": {"identity": "u1", "max_discovery": 9000}})
    # a registry review (its dates, its digest) is data the run reads, not a strategy rule
    reviewed = {**a, "event_risk": {"version": 1, "registry": {"reviewed_on": "2026-11-25"}, "registry_sha256": "r2"}}
    assert gl.strategy_digest(a) == gl.strategy_digest(reviewed)
    assert gl.strategy_digest(a) != gl.strategy_digest({**a, "event_risk": {**a["event_risk"], "version": 2}})
    real = frozen("2026-11-23")["rules"]
    assert {"registry", "registry_sha256"} <= set(real["event_risk"])
    # the two publications were made under different nightly memberships and one standing digest
    other = frozen("2026-11-20")["rules"]
    assert real["universe"]["identity"] != other["universe"]["identity"]
    assert gl.strategy_digest(real) == gl.strategy_digest(other)


@pytest.mark.parametrize("name, change, words", [
    ("version", lambda b, c: b.update(version=2), "is missing or not this version"),
    ("a criterion dropped", lambda b, c: b["criteria"].pop(), "criteria are not the gate's"),
    ("ready", lambda b, c: b.update(ready=True), "ready is not its criteria's"),
    ("reasons", lambda b, c: b.update(reasons=[]), "reasons are not its unmet criteria"),
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
def test_version_ones_validator_names_each_forged_part_of_its_block(name, change, words):
    data = frozen("next")                                     # its ledger has a row
    assert gl.faults(data) == [] and data["run"]["go_live"]["ledger"]
    change(*_gate(data))
    found = gl.faults(data)
    assert any(f == "run.go_live " + words for f in found), (name, found)


@pytest.mark.parametrize("name, change, words", [
    ("since", lambda s: s.update(since="soon"), "strategy is not readable"),
    ("newest", lambda s: s.pop("newest"), "strategy is not readable"),
    ("not_forward", lambda s: s.update(not_forward=["2026-09-10", "2026-09-09"]), "strategy is not readable"),
    ("not_forward dates", lambda s: s.update(not_forward=["soon"]), "strategy is not readable"),
    ("not_forward list", lambda s: s.update(not_forward=None), "strategy is not readable"),
    ("not_forward too long", lambda s: s.update(not_forward=[date.fromordinal(date(2025, 1, 1).toordinal() + n).isoformat()
                                                             for n in range(gl.NOT_FORWARD_MAX + 1)]),
     "strategy is not readable"),
    ("forward", lambda s: s.update(forward="yes"), "strategy is not readable"),
    ("forward missing", lambda s: s.pop("forward"), "strategy is not readable"),
    ("digest", lambda s: s.update(digest="0" * 64), "strategy digest is not the record's own rules'"),
])
def test_version_ones_validator_holds_the_standing_rules_block(name, change, words):
    data = frozen("next")
    assert gl.faults(data) == []
    change(data["run"]["go_live"]["strategy"])
    assert gl.faults(data) == ["run.go_live " + words], name
    whole = frozen("next")
    whole["run"]["go_live"]["strategy"] = "standing"
    assert gl.faults(whole) == ["run.go_live strategy is not readable"]


def test_version_ones_digest_is_held_to_the_records_own_rules():
    data = frozen("2026-11-23")
    # the nightly membership is not a strategy rule: the digest stands when it moves
    data["rules"]["universe"]["identity"] = "another night's membership"
    assert gl.faults(data) == []
    # any other rule is: a record whose rules moved under its block is refused
    data["rules"]["plan"]["a_rule_added_later"] = 1
    assert gl.faults(data) == ["run.go_live strategy digest is not the record's own rules'"]


def test_version_ones_validator_holds_each_count_to_its_need_and_the_streak_to_its_ledger():
    for key, need in (("on_time_sessions", "on_time_sessions"), ("settled_forward_plans", "min_settled_forward")):
        for change, words in (
                (lambda c: c.update(need=1), f"{key} is not its count against the archived need"),
                (lambda c: c.update(have="3"), f"{key} is not its count against the archived need")):
            data = frozen("2026-11-23")
            change(_gate(data)[1][key])
            assert "run.go_live " + words in gl.faults(data), (key, gl.faults(data))
        # the need is the one the record's own rules archived
        data = frozen("2026-11-23")
        data["rules"]["go_live"][need] = 5
        data["run"]["go_live"]["strategy"]["digest"] = gl.strategy_digest(data["rules"])
        assert gl.faults(data) == [f"run.go_live {key} is not its count against the archived need"]
        _gate(data)[1][key]["need"] = 5
        assert gl.faults(data) == []
    data = frozen("2026-11-23")
    _gate(data)[1]["on_time_sessions"]["have"] = 3
    assert gl.faults(data) == ["run.go_live on_time_sessions is not the run its own ledger ends on before tonight"]


def test_version_ones_forward_count_is_never_more_than_the_scorecards_settled_plans():
    data = frozen("next")
    block, crit = _gate(data)
    have = crit["settled_forward_plans"]["have"]
    assert have == 1 and data["scorecard"]["settled"] == 22 and gl.faults(data) == []
    assert crit["settled_forward_plans"]["detail"] == f"1 settled since {block['strategy']['since']} of 20"
    data["scorecard"]["settled"] = have                       # every settled plan a forward one: still the record's
    assert gl.faults(data) == []
    data["scorecard"]["settled"] = have - 1
    assert gl.faults(data) == ["run.go_live settled_forward_plans is more than the scorecard's settled plans"]


def test_version_ones_validator_holds_a_publication_that_was_not_forward():
    data = frozen("next")
    block, crit = _gate(data)
    session = data["run"]["session"]
    assert block["strategy"]["forward"] is True and gl.faults(data) == []
    # a block that says it is not forward and does not keep its own session
    block["strategy"]["forward"] = False
    assert gl.faults(data) == ["run.go_live names a publication that is not forward without keeping its session"]
    block["strategy"]["not_forward"] = [session]
    assert gl.faults(data) == []                                 # zero consecutive, as that night has
    # and one that claims a run it may not count
    block["ledger"] = [counted("2026-09-10")]
    crit["on_time_sessions"]["have"] = 1
    assert gl.faults(data) == ["run.go_live on_time_sessions is not the run its own ledger ends on before tonight"]
    block["strategy"]["forward"], block["strategy"]["not_forward"] = True, []
    assert gl.faults(data) == []


def test_a_block_is_held_to_the_gate_version_its_own_rules_archived():
    v1, v2 = frozen("next"), record("next")
    unread = ["run.go_live is missing or not this version"]
    # a version-2 block under rules that archive version 1
    mixed = copy.deepcopy(v1)
    mixed["run"]["go_live"] = copy.deepcopy(v2["run"]["go_live"])
    assert gl.faults(mixed) == unread
    # relabelled version 1, it is still two conditions where version 1 has four
    mixed["run"]["go_live"]["version"] = 1
    assert gl.faults(mixed) == ["run.go_live criteria are not the gate's"]
    # a version-1 block under rules that archive version 2
    mixed = copy.deepcopy(v2)
    mixed["run"]["go_live"] = copy.deepcopy(v1["run"]["go_live"])
    assert gl.faults(mixed) == unread
    with pytest.raises(ValueError, match="run.go_live is missing or not this version"):
        report.validate(mixed)
    # relabelled version 2, it is still four conditions where version 2 has two
    mixed["run"]["go_live"]["version"] = 2
    assert gl.faults(mixed) == ["run.go_live criteria are not the gate's"]
    # and under either version's rules, no block at all
    for data in (v1, v2):
        del data["run"]["go_live"]
        assert gl.faults(data) == unread


@pytest.mark.parametrize("version", [3, 0, -1, "2", 2.0, True, None, [2], "absent"])
def test_an_archived_gate_version_this_code_does_not_know_is_one_named_fault(version):
    data = record("next")
    if version == "absent":
        del data["rules"]["go_live"]["version"]
    else:
        data["rules"]["go_live"]["version"] = version
    # a version is a whole number; one that is not is no version, and a whole number this code does not know is unknown
    assert gl.archived_version(data["rules"]) == (version if type(version) is int else None)
    assert gl.faults(data) == ["rules archive a go-live gate version this code does not know"]
    with pytest.raises(ValueError, match="rules archive a go-live gate version this code does not know"):
        report.validate(data)
    # the same over a version-1 record, and over archived rules that are no block at all
    old = frozen("next")
    old["rules"]["go_live"] = {**old["rules"]["go_live"], "version": version} if version != "absent" else "the gate"
    assert gl.faults(old) == ["rules archive a go-live gate version this code does not know"]


# --------------------------------------------------- the handoff and the schema --
def test_the_schemas_live_ready_reasons_are_the_gates_criteria_and_the_unread_gate():
    schema = json.loads((ROOT / "docs" / "operations" / "orders-schema.json").read_text())
    reasons = schema["properties"]["live_ready"]["properties"]["reasons"]["items"]["enum"]
    assert reasons == list(gl.CRITERIA) + [orders.LIVE_READY_REASON]
    assert reasons == ["fidelity_protocol", "on_time_sessions", "go_live_gate_not_evaluated"]
    assert set(gl.REASONS) == set(gl.CRITERIA)


def test_a_live_handoff_is_refused_while_the_committed_protocol_record_is_not_passed(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "data.json").write_text(json.dumps(_live(page("full"))))
    orders.write_publication(docs)
    assert json.loads((docs / "orders.json").read_text())["mode"] == "live"
    # the record and the file agree, and the committed protocol record (the suite's pinned copy) is unpassed
    assert orders.check(docs) == ["orders.json is live while the committed protocol record is not passed"]
    session = page("full")["run"]["session"]
    passed = passed_record(monkeypatch, tmp_path, recorded_on=session)
    orders.check(docs)                                           # once first, so every lazy import is done
    opened, found = opened_during(monkeypatch, lambda: orders.check(docs))
    # the protocol record is the one condition a committed file can show again: nothing else is asked,
    # and no ablation or study is read anywhere
    assert found == [] and str(passed) in opened
    assert not [name for name in opened if "ablation" in name or "input-truthfulness" in name]
    # a record dated after the record's own session does not pass it
    passed_record(monkeypatch, tmp_path, recorded_on="2026-12-31")
    assert orders.check(docs) == ["orders.json is live while the committed protocol record is not passed"]


def test_a_handoff_written_under_an_earlier_version_is_paper_or_refused(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    raw = json.dumps(page("full")).encode()
    (docs / "data.json").write_bytes(raw)
    assert orders.VERSION == 6
    # 5 is the two-condition gate's first handoff, 4 the four-condition gate's
    for version in (5, 4, 3, 1):
        earlier = {"version": version, "mode": "paper", "live_ready": {"value": False, "reasons": []},
                   "source": {"data_sha256": hashlib.sha256(raw).hexdigest()}}
        (docs / "orders.json").write_text(json.dumps(earlier))
        assert orders.earlier_version((docs / "orders.json").read_bytes()) == version
        assert orders.check(docs) == []                          # bound to the record: held to that alone
        for change in ({"mode": "live"}, {"live_ready": {"value": True, "reasons": []}}, {"live_ready": None}):
            (docs / "orders.json").write_text(json.dumps({**earlier, **change}))
            assert orders.check(docs) == ["orders.json written under an earlier version is not paper"], (version, change)
        (docs / "orders.json").write_text(json.dumps({**earlier, "source": {"data_sha256": "0" * 64}}))
        assert orders.check(docs) == ["orders.json is not bound to data.json"], version


@pytest.mark.parametrize("unmet", gl.CRITERIA)
def test_a_handoff_is_written_and_meets_its_schema_with_any_one_condition_unmet(unmet):
    data = _unmet(_live(page("full")), unmet)
    doc = orders.build(json.dumps(data).encode())
    assert doc["mode"] == "paper" and doc["live_ready"] == {"value": False, "reasons": [unmet]}
    assert orders.problems(doc) == []
    assert unmet in gl.REASONS and gl.REASONS[unmet]


@pytest.mark.parametrize("reason", gl.CRITERIA_BY_VERSION[1][2:])
def test_a_handoff_that_names_a_condition_the_gate_no_longer_has_is_refused_by_its_schema(reason):
    assert reason in ("settled_forward_plans", "ablation_report")
    data = _unmet(_live(page("full")), "fidelity_protocol")
    doc = orders.build(json.dumps(data).encode())
    assert doc["live_ready"] == {"value": False, "reasons": ["fidelity_protocol"]} and orders.problems(doc) == []
    # the same paper file naming a condition only version 1 had: the schema's list has no such word
    doc["live_ready"]["reasons"] = [reason]
    allowed = list(gl.CRITERIA) + [orders.LIVE_READY_REASON]
    assert orders.problems(orders.sealed(doc)) == [f"$.live_ready.reasons[0]: {reason!r} is not one of {allowed}"]


# ------------------------------------------------------------- the documents --
def table_rows(note: str, heading: str) -> list[list[str]]:
    """The rows of the first table under a heading, each a list of its cells, past the header and its rule."""
    rows = []
    for line in note.split(heading, 1)[1].splitlines()[1:]:
        if line.startswith("|"):
            rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
        elif rows:
            break
    return rows[2:]


OUTCOME_WORDS = ("settled", "ablation", "win rate", "expectancy", "scorecard", "study")


def test_the_guide_lists_the_gates_conditions_and_reasons_and_no_outcome_among_them():
    note = (ROOT / "docs" / "operations" / "go-live.md").read_text()
    conditions = table_rows(note, "## The conditions")
    assert [row[0] for row in conditions] == [f"`{key}`" for key in gl.CRITERIA]
    reasons = table_rows(note, "## The reasons `live_ready` can name")
    assert [row[0] for row in reasons] == [f"`{key}`" for key in gl.CRITERIA] + [f"`{orders.LIVE_READY_REASON}`"]
    assert [row[1] for row in reasons[:-1]] == [gl.REASONS[key] for key in gl.CRITERIA]
    for row in conditions + reasons:
        assert not [word for word in OUTCOME_WORDS if word in " ".join(row).lower()], row
    flat = " ".join(note.split())
    assert "says both conditions below hold" in flat and len(gl.CRITERIA) == 2
    assert "no settled-plan count, win rate, expectancy or study is a condition, and none is to be added" in flat
    # the conditions version 1 also asked are told as history, under their own heading and nowhere above it
    above, history = note.split("### Version 1 of the gate", 1)
    assert "`settled_forward_plans`" in history and "`ablation_report`" in history
    assert "settled_forward_plans" not in above and "ablation_report" not in above


def test_the_readme_names_two_conditions_and_no_outcome_among_them():
    section = (ROOT / "README.md").read_text().split("### The go-live gate", 1)[1].split("\n### ", 1)[0]
    flat = " ".join(section.split())
    assert "Two conditions:" in flat and len(gl.CRITERIA) == 2
    listed = section.split("Two conditions:", 1)[1].split("\n\nThe ledger closes", 1)[0]
    assert len([line for line in listed.splitlines() if line.startswith("- **")]) == len(gl.CRITERIA)
    assert not [word for word in OUTCOME_WORDS if word in listed.lower()]
    assert "it reads no outcome" in flat
    assert "`go_live.CRITERIA_BY_VERSION`" in flat and "the ablation stays as research the gate does not read" in flat


def test_the_guide_lists_each_reason_in_the_gates_own_words_and_names_what_the_gate_reads():
    note = (ROOT / "docs" / "operations" / "go-live.md").read_text()
    flat = " ".join(note.split())
    for code in gl.CRITERIA:
        assert f"| `{code}` | {gl.REASONS[code]} |" in note, code
    assert f"| `{orders.LIVE_READY_REASON}` |" in note
    for name in ("`go_live.PUBLISHED_STATUSES`", "`run.finish_seconds`", "`run.elapsed_seconds` is not the finish",
                 "`run.go_live.publication`", "How the morning check was started is not read at all",
                 "the gate judges the newest receipt, not the first"):
        assert name in flat, name
    readme = " ".join((ROOT / "README.md").read_text().split())
    assert "`run.finish_seconds`" in readme and "`run.go_live.publication`" in readme
    agent = " ".join((ROOT / "docs" / "operations" / "orders.md").read_text().split())
    assert "once written" not in agent and "[`go-live.md`](go-live.md)" in agent
    protocol = (ROOT / gl.PROTOCOL_NAME).read_text()
    assert "docs/operations/go-live.md" in protocol and "Completing the sitting is not passing it." in protocol
