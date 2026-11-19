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


def previous_record(session="2026-11-17", published="2026-11-17T22:20:00+00:00", event="schedule",
                    flag=None, applicable="2026-11-18", elapsed=180.0, opens="14:30:00+00:00") -> dict:
    return {"run": {"session": session, "published_at": published, "elapsed_seconds": elapsed,
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
    assert gl.first_forward_session("2026-11-18", "2026-11-17") == "2026-11-18"
    assert gl.first_forward_session("2026-11-17", "2026-11-17") == "2026-11-18"     # a revision is not forward
    assert gl.first_forward_session("2026-11-18", None) == "2026-11-18"


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
