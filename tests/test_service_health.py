"""tools.service_health: the service read off the retained publications and
their commits (#111), the signal kept apart. The arithmetic -- a session's
nominal cron instants across the DST change, the exchange frame across a
holiday and an early close, a publication's latency against its completion
and its slots, the session rows' due/pending/missing states, revisions and
streaks, the summary -- is driven on hand-sized records with hand-computed
answers; the refusals are driven with records that do not reconcile; a
synthetic git history is walked, written and held by ``--check``; and the
committed dated reading is held to the commits it names, fetched into a
shallow checkout exactly as the findings suite fetches its own."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import json
import os
from pathlib import Path
import re
import subprocess

import pytest

from src import sessions
from tools import service_health as sh

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "docs/input-truthfulness/2026-10-12-service-health.md"


def record(session="2026-10-09", published_at="2026-10-10T07:30:00+00:00", *, status="ok", regime="yellow", **run_extra):
    """A minimal real schema-2 record: what the reading indexes into and nothing more."""
    run = {"session": session, "session_state": "open", "status": status, "published_at": published_at,
           "run_id": "38034610157", "dry_run": False, "email": "skipped", "elapsed_seconds": 112.7, "fetch_seconds": 59.2,
           "problems": [], "type": "evening",
           "coverage": {"version": 1, "stale": 1, "acceptance": {"status": "degraded", "intended_stocks": 4775, "ready_stocks": 4774, "fraction": 0.99979}},
           "input_tolerance": {"verdict": "tolerated"},
           "reads": {"requested": 2, "done": 2, "verdict": "complete"},
           "reader_usage": {"version": 1, "model": "claude-sonnet-4-6", "candidates": 2, "calls": 2, "responses": 2,
                            "tokens": {"cache_write": 0, "cache_read": 4780, "uncached": 2218, "output": 180}, "input_tokens": 6998}}
    run.update(run_extra)
    return {"schema_version": 2, "app": {"name": "SpicyStock", "version": "2.0", "rules_version": "c9dc7d6d1d87"},
            "run": run, "breadth": {"regime": {"verdict": regime}}, "bursts": [], "watchlist": {"top": [], "counts": {}},
            "trades": [], "cash_budget": {}}


def reading(session, published_at, landed_at=None, **kw):
    return sh.publication_reading(record(session, published_at, **kw), commit="c" * 40, blob="b" * 40,
                                  landed_at=landed_at or published_at)


# ---------------------------------------------------------------- clocks ----

def test_the_nominal_slots_are_the_crons_wall_clock_in_the_exchange_zone():
    # 16 22 * * 1-5 on EDT and 16 23 * * 1-5 on EST are one instant, 6:16 PM ET; the retry pair is 8:16 PM ET
    assert sh.slots(date(2026, 10, 9)) == {"primary_at": "2026-10-09T22:16:00+00:00", "retry_at": "2026-10-10T00:16:00+00:00"}
    assert sh.slots(date(2026, 11, 2)) == {"primary_at": "2026-11-02T23:16:00+00:00", "retry_at": "2026-11-03T01:16:00+00:00"}


def test_the_frame_is_the_exchanges_own_across_a_holiday_and_an_early_close():
    f = sh.frame(date(2026, 11, 25))
    assert (f["next_session"], f["next_open_at"]) == ("2026-11-27", "2026-11-27T14:30:00+00:00")   # Thanksgiving closed
    assert f["completion_at"] == "2026-11-25T21:15:00+00:00" and f["shortened"] is False
    early = sh.frame(date(2026, 11, 27))
    assert early["shortened"] is True and early["completion_at"] == "2026-11-27T18:15:00+00:00"    # a 1 PM close plus the buffer
    october = sh.frame(date(2026, 10, 9))
    assert october["next_morning_slots_at"] == ["2026-10-12T13:20:00+00:00", "2026-10-12T13:28:00+00:00"]   # 8:20/8:28 Chicago on CDT
    assert sh.frame(date(2026, 11, 2))["next_morning_slots_at"] == ["2026-11-03T14:20:00+00:00", "2026-11-03T14:28:00+00:00"]  # on CST
    with pytest.raises(ValueError):
        sh.frame(date(2026, 11, 26))


def test_instants_are_read_as_utc_and_offsets_are_required():
    assert sh.parse_instant("2026-10-09T16:15:00-04:00").isoformat() == "2026-10-09T20:15:00+00:00"
    assert sh.parse_instant("2026-10-09T20:15:00Z").isoformat() == "2026-10-09T20:15:00+00:00"
    for bad in ("2026-10-09T20:15:00", "tonight", None, 7):
        with pytest.raises(sh.ServiceError):
            sh.parse_instant(bad)


# ---------------------------------------------------------- publications ----

def test_a_publications_timing_is_hand_computed():
    r = reading("2026-10-09", "2026-10-10T07:30:00+00:00", landed_at="2026-10-10T07:32:24+00:00")
    t = r["timing"]
    assert t["completion_at"] == "2026-10-09T20:15:00+00:00" and t["completion_basis"] == "re-derived"
    assert t["latency_minutes"] == 675.0            # 20:15 -> 07:30 the next day
    assert t["after_primary_minutes"] == 554.0      # 22:16 -> 07:30
    assert t["after_retry_slot"] is True and t["retry_slot_at"] == "2026-10-10T00:16:00+00:00"
    assert t["before_next_open"] is True and t["next_open_at"] == "2026-10-12T13:30:00+00:00"
    assert t["landed_minutes"] == 2.4
    early = reading("2026-10-09", "2026-10-09T21:08:00+00:00")
    assert early["timing"]["after_primary_minutes"] == -68.0 and early["timing"]["after_retry_slot"] is False
    late = reading("2026-10-09", "2026-10-12T13:30:00+00:00")
    assert late["timing"]["before_next_open"] is False      # at the open is not before it
    at_retry = reading("2026-10-09", "2026-10-10T00:16:00+00:00")
    assert at_retry["timing"]["after_retry_slot"] is True and at_retry["timing"]["after_primary_minutes"] == 120.0
    assert reading("2026-10-09", "2026-10-10T00:15:59+00:00")["timing"]["after_retry_slot"] is False


def test_a_publication_reading_copies_the_records_own_blocks_and_keeps_the_signal_apart():
    r = reading("2026-10-09", "2026-10-10T07:30:00+00:00")
    assert r["inputs"] == {"version": 1, "intended_stocks": 4775, "ready_stocks": 4774, "ready_fraction": 0.99979,
                           "acceptance": "degraded", "stale": 1, "tolerance": "tolerated"}
    assert r["reader"] == {"requested": 2, "done": 2, "verdict": "complete",
                           "usage": {"model": "claude-sonnet-4-6", "calls": 2, "responses": 2, "input_tokens": 6998, "output_tokens": 180}}
    assert r["signal"] == {"regime": "yellow", "discovered": 0, "listed": 0, "reaction_tickets": 0, "anticipation_tickets": 0}
    assert (r["status"], r["email"], r["run_id"], r["rules_version"]) == ("ok", "skipped", "38034610157", "c9dc7d6d1d87")
    # a record from before a rule carries no block: None, never a guess
    old = reading("2026-09-14", "2026-09-14T22:24:50+00:00", coverage=None, input_tolerance=None, reads=None, reader_usage=None)
    assert old["inputs"] == {k: None for k in old["inputs"]}
    assert old["reader"] == {"requested": None, "done": None, "verdict": None, "usage": None}


def test_an_archived_completion_is_held_to_the_calendar():
    cal = {"measured": {"session": "2026-10-09", "completion_at": "2026-10-09T16:15:00-04:00"}}
    assert reading("2026-10-09", "2026-10-10T07:30:00+00:00", calendar=cal)["timing"]["completion_basis"] == "archived"
    cal["measured"]["completion_at"] = "2026-10-09T16:30:00-04:00"
    with pytest.raises(sh.ServiceError, match="archived completion"):
        reading("2026-10-09", "2026-10-10T07:30:00+00:00", calendar=cal)


@pytest.mark.parametrize("mutate, match", [
    (lambda d: d.__setitem__("fixture", "full"), "not a real"),
    (lambda d: d.__setitem__("schema_version", 1), "not a real"),
    (lambda d: d["run"].__setitem__("session", "2026-10-10"), "not an XNYS trading session"),   # a Saturday
    (lambda d: d["run"].__setitem__("session", "yesterday"), "not a date"),
    (lambda d: d["run"].__setitem__("published_at", "2026-10-10T07:30:00"), "without an offset"),
    (lambda d: d["run"].pop("published_at"), "not an instant"),
])
def test_a_record_the_reading_cannot_place_is_refused(mutate, match):
    data = record()
    mutate(data)
    with pytest.raises(sh.ServiceError, match=match):
        sh.publication_reading(data, commit="c" * 40, blob="b" * 40, landed_at="2026-10-10T07:32:24+00:00")


# ------------------------------------------------------------ companions ----

def receipt(applicable="2026-10-12", generated="2026-10-12T13:20:00+00:00", status="observed", **extra):
    return {"publication": {"run_id": "38034610157", "measured_session": "2026-10-09", "applicable_session": applicable},
            "generated_at": generated, "status": status, "reason": None, "rows": [{"ticker": "KE"}], **extra}


def test_a_companion_receipt_is_read_for_its_binding_and_its_clock():
    r = sh.companion_reading("morning", receipt(entry_phase="open"), commit="d" * 40, blob="e" * 40, landed_at="2026-10-12T13:21:00+00:00")
    assert (r["applicable_session"], r["applicable_open_at"], r["before_applicable_open"], r["rows"]) == \
        ("2026-10-12", "2026-10-12T13:30:00+00:00", True, 1)
    assert (r["status"], r["entry_phase"], r["bound_run_id"], r["measured_session"]) == ("observed", "open", "38034610157", "2026-10-09")
    late = sh.companion_reading("morning", receipt(applicable="2026-10-09", generated="2026-10-09T17:10:18+00:00", status="inapplicable",
                                                   reason="entry_window_ended", rows=[]), commit="d" * 40, blob="e" * 40, landed_at="2026-10-09T17:11:03+00:00")
    assert late["before_applicable_open"] is False and late["reason"] == "entry_window_ended" and late["rows"] == 0
    at_open = sh.companion_reading("morning", receipt(generated="2026-10-12T13:30:00+00:00"), commit="d" * 40, blob="e" * 40, landed_at="2026-10-12T13:31:00+00:00")
    assert at_open["before_applicable_open"] is False       # at the open is not before it
    for bad, match in ((receipt(applicable="2026-10-10"), "not an exchange session"), ({"status": "x"}, "not a bound receipt"),
                       (receipt(generated="noon"), "not an instant")):
        with pytest.raises(sh.ServiceError, match=match):
            sh.companion_reading("morning", bad, commit="d" * 40, blob="e" * 40, landed_at="2026-10-12T13:21:00+00:00")
    research = sh.companion_reading("research_observations", receipt(requests=1, rows=None), commit="d" * 40, blob="e" * 40,
                                    landed_at="2026-10-12T13:21:00+00:00")
    assert research["requests"] == 1 and research["rows"] is None and "entry_phase" not in research


# -------------------------------------------------------------- sessions ----

@pytest.fixture
def week():
    """Five expected sessions, 5-9 October: the 5th published twice, the 6th
    never, the 7th once after the next open, the 8th once in time, the 9th
    not yet complete at the clock."""
    pubs = [reading("2026-10-05", "2026-10-06T02:17:00+00:00"), reading("2026-10-05", "2026-10-06T03:00:00+00:00", status="degraded"),
            reading("2026-10-07", "2026-10-08T14:00:00+00:00"),       # after the 8 October open at 13:30Z
            reading("2026-10-08", "2026-10-09T02:06:00+00:00")]
    morning = [sh.companion_reading("morning", receipt(applicable="2026-10-09", generated="2026-10-09T13:20:00+00:00"),
                                    commit="d" * 40, blob="e" * 40, landed_at="2026-10-09T13:21:00+00:00")]
    return pubs, {"morning": morning, "issuer_evidence": [], "research_observations": []}


def test_session_rows_name_every_expected_session_and_its_state(week):
    pubs, companions = week
    rows = sh.session_rows(pubs, companions, sh.parse_instant("2026-10-09T19:00:00+00:00"))   # the 9th closes at 20:00Z
    assert [r["session"] for r in rows] == ["2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09"]
    by = {r["session"]: r for r in rows}
    assert (by["2026-10-05"]["revisions"], by["2026-10-05"]["service"]["status"], by["2026-10-05"]["latest"]["status"]) == (2, "ok", "degraded")
    assert by["2026-10-05"]["service"]["published_at"] == "2026-10-06T02:17:00+00:00"       # the first, not the latest
    assert (by["2026-10-06"]["published"], by["2026-10-06"]["due"], by["2026-10-06"]["overdue"], by["2026-10-06"]["pending"]) == (False, True, True, False)
    assert by["2026-10-07"]["service"]["before_next_open"] is False
    assert by["2026-10-08"]["service"]["before_next_open"] is True
    assert (by["2026-10-09"]["due"], by["2026-10-09"]["published"], by["2026-10-09"]["overdue"], by["2026-10-09"]["pending"]) == (False, False, False, False)
    assert by["2026-10-08"]["applicable_session"] == "2026-10-09"
    assert [m["before_applicable_open"] for m in by["2026-10-08"]["receipts"]["morning"]] == [True]
    assert by["2026-10-07"]["receipts"]["morning"] == []
    at_completion = sh.session_rows(pubs, companions, sh.parse_instant("2026-10-09T20:15:00+00:00"))[-1]
    assert (at_completion["session"], at_completion["due"]) == ("2026-10-09", True)      # due at the completion instant itself
    pending = sh.session_rows(pubs, companions, sh.parse_instant("2026-10-09T21:00:00+00:00"))[-1]
    assert (pending["session"], pending["due"], pending["pending"], pending["overdue"]) == ("2026-10-09", True, True, False)
    # a clock on a later session reaches that session: the 9th is missing and the 12th is a row not yet due
    later = {r["session"]: r for r in sh.session_rows(pubs, companions, sh.parse_instant("2026-10-12T13:30:00+00:00"))}
    assert (later["2026-10-09"]["due"], later["2026-10-09"]["pending"], later["2026-10-09"]["overdue"]) == (True, False, True)
    assert list(later)[-1] == "2026-10-12" and later["2026-10-12"]["due"] is False and later["2026-10-12"]["published"] is False
    # a weekend clock reaches the Friday
    assert [r["session"] for r in sh.session_rows(pubs, companions, sh.parse_instant("2026-10-11T01:01:36+00:00"))][-1] == "2026-10-09"


def test_streaks_and_the_summary_are_hand_computed(week):
    pubs, companions = week
    clock = sh.parse_instant("2026-10-12T13:30:00+00:00")
    rows = sh.session_rows(pubs, companions, clock)
    # 5th in time, 6th missing, 7th late, 8th in time, 9th missing: longest 1, current 0
    assert sh._streaks(rows) == {"longest": 1, "current": 0}
    s = sh.summary(rows, pubs, companions, clock)
    assert (s["expected_sessions"], s["due_sessions"], s["published_sessions"]) == (6, 5, 3)
    assert s["missing_sessions"] == ["2026-10-06", "2026-10-09"] and s["pending_sessions"] == [] and s["not_yet_due"] == ["2026-10-12"]
    assert (s["before_next_open"], s["after_retry_slot"]) == (2, 3)
    # latencies of the first publications: 5th 20:15->02:17 = 362, 7th 20:15->14:00 = 1065, 8th 20:15->02:06 = 351
    assert s["latency_minutes"] == {"min": 351.0, "median": 362.0, "max": 1065.0}
    assert (s["publications"], s["revisions"], s["resessions"], s["statuses"]) == (4, 1, ["2026-10-05"], {"ok": 3, "degraded": 1})
    assert s["elapsed_seconds"] == round(112.7 * 4, 1) and s["fetch_seconds"] == round(59.2 * 4, 1)
    assert s["reads"] == {"requested": 8, "done": 8, "publications_with_block": 4}
    assert s["reader_usage"] == {"publications_with_block": 4, "calls": 8, "responses": 8, "input_tokens": 6998 * 4, "output_tokens": 720}
    assert s["signal"] == {"regimes": {"yellow": 4}, "reaction_tickets": 0, "anticipation_tickets": 0}
    assert s["fresh"] == {"newest_due_session": "2026-10-09", "newest_published_session": "2026-10-08", "fresh": False}
    assert s["companions"]["morning"] == {"receipts": 1, "statuses": {"observed": 1}, "before_applicable_open": 1, "applicable_sessions": ["2026-10-09"]}
    fresh = sh.summary(sh.session_rows(pubs, companions, sh.parse_instant("2026-10-09T19:00:00+00:00")), pubs, companions,
                       sh.parse_instant("2026-10-09T19:00:00+00:00"))
    assert fresh["fresh"] == {"newest_due_session": "2026-10-08", "newest_published_session": "2026-10-08", "fresh": True}
    assert fresh["not_yet_due"] == ["2026-10-09"] and fresh["streak"] == {"longest": 1, "current": 1}


def test_an_empty_history_is_refused():
    with pytest.raises(sh.ServiceError, match="no publication"):
        sh.session_rows([], {"morning": []}, sh.parse_instant("2026-10-09T19:00:00+00:00"))


# --------------------------------------------------------- a synthetic git ----

def git(repo: Path, *args: str, date_: str | None = None) -> str:
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@x", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@x")
    if date_:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date_
    done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, env=env)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def commit(repo: Path, path: str, payload, message: str, date_: str) -> str:
    (repo / path).parent.mkdir(parents=True, exist_ok=True)
    (repo / path).write_text(json.dumps(payload) + "\n")
    git(repo, "add", path)
    git(repo, "commit", "-q", "-m", message, date_=date_)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A history of its own: a fixture record (set aside), two publications of
    one session, one of the next, and a morning receipt, each landing at a
    known instant; the module reads it as it reads the real one."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    fixture = commit(repo, "docs/data.json", {**record("2026-10-07", "2026-10-08T01:54:00+00:00"), "fixture": "full"}, "fixture", "2026-10-08T02:00:00+00:00")
    first = commit(repo, "docs/data.json", record("2026-10-08", "2026-10-09T02:06:55+00:00", status="degraded"), "run 2026-10-08", "2026-10-09T02:12:06+00:00")
    second = commit(repo, "docs/data.json", record("2026-10-08", "2026-10-09T12:10:20+00:00", status="degraded"), "run 2026-10-08", "2026-10-09T12:15:26+00:00")
    morning = commit(repo, "docs/morning.json", receipt(applicable="2026-10-09", generated="2026-10-09T17:10:18+00:00", status="inapplicable",
                                                        reason="entry_window_ended", rows=[], entry_phase="ended", observation_run_id="37964299335", dry_run=False),
                     "Publish bound morning observation", "2026-10-09T17:11:03+00:00")
    third = commit(repo, "docs/data.json", record("2026-10-09", "2026-10-10T01:44:58+00:00"), "run 2026-10-09", "2026-10-10T01:49:14+00:00")
    monkeypatch.setattr(sh, "ROOT", repo)
    return {"repo": repo, "fixture": fixture, "first": first, "second": second, "morning": morning, "third": third}


def test_a_history_is_walked_from_its_tip_and_the_set_asides_are_named(repo):
    result = sh.build(ref="main")
    assert result["source"]["through"] == repo["third"] and result["source"]["clock"] == "2026-10-10T01:49:14+00:00"
    assert result["source"]["publication_commits"] == [repo["third"], repo["second"], repo["first"]]     # the walk's order, newest first
    assert result["source"]["companion_commits"] == {"morning": [repo["morning"]], "issuer_evidence": [], "research_observations": []}
    assert result["skipped"] == [{"commit": repo["fixture"], "reason": f"{repo['fixture'][:8]}:docs/data.json: not a real schema-2 publication"}]
    assert [p["session"] for p in result["publications"]] == ["2026-10-08", "2026-10-08", "2026-10-09"]   # the readings, by session
    assert [r["session"] for r in result["sessions"]] == ["2026-10-08", "2026-10-09"]
    assert result["sessions"][0]["revisions"] == 2 and result["sessions"][0]["receipts"]["morning"][0]["commit"] == repo["morning"]
    assert result["publications"][2]["landed_at"] == "2026-10-10T01:49:14+00:00" and result["publications"][2]["timing"]["landed_minutes"] == 4.3
    assert result["summary"]["fresh"]["fresh"] is True
    # through an earlier commit the clock is that commit's and the later ones are not read
    earlier = sh.build(ref="main", through=repo["second"])
    assert earlier["source"]["clock"] == "2026-10-09T12:15:26+00:00" and earlier["source"]["companion_commits"]["morning"] == []
    assert [(r["session"], r["due"], r["published"]) for r in earlier["sessions"]] == [("2026-10-08", True, True), ("2026-10-09", False, False)]
    with pytest.raises(sh.ServiceError, match="raise --limit"):
        sh.build(ref="main", limit=2)


def test_the_written_files_are_held_by_check_and_a_drift_is_named(repo, tmp_path):
    out = tmp_path / "out"
    assert sh.main(["--ref", "main", "--output-dir", str(out)]) == 0
    assert sh.main(["--check", "--output-dir", str(out)]) == 0
    written = json.loads((out / sh.OUTPUT_JSON.name).read_text())
    assert written["source"]["through"] == repo["third"]
    drifted = deepcopy(written)
    drifted["sessions"][0]["service"]["latency_minutes"] += 1
    (out / sh.OUTPUT_JSON.name).write_text(json.dumps(drifted, indent=1, sort_keys=True) + "\n")
    assert sh.check(out) == [f"{sh.OUTPUT_JSON.name} is not what the tool writes from its named commits"]
    (out / sh.OUTPUT_JSON.name).write_text(json.dumps(written, indent=1, sort_keys=True) + "\n")
    (out / sh.OUTPUT_MD.name).write_text("# not the reading\n")
    assert sh.check(out) == [f"{sh.OUTPUT_MD.name} is not what the tool writes"]
    # a committed reading that names a commit the history does not carry is refused, not rewritten
    forged = deepcopy(written)
    forged["source"]["publication_commits"] = forged["source"]["publication_commits"][1:]
    (out / sh.OUTPUT_JSON.name).write_text(json.dumps(forged, indent=1, sort_keys=True) + "\n")
    with pytest.raises(sh.ServiceError, match="not the history's"):
        sh.check(out)
    unset_aside = deepcopy(written)
    unset_aside["skipped"] = []
    (out / sh.OUTPUT_JSON.name).write_text(json.dumps(unset_aside, indent=1, sort_keys=True) + "\n")
    with pytest.raises(sh.ServiceError, match="not the history's"):
        sh.check(out)
    assert sh.main(["--check", "--output-dir", str(tmp_path / "nowhere")]) == 1


def test_a_shallow_checkout_rebuilds_from_the_named_commits_alone(repo, monkeypatch):
    out = sh.build(ref="main")
    fetched = []
    monkeypatch.setattr(sh, "shallow", lambda: True)
    monkeypatch.setattr(sh, "fetch_missing", lambda commits: fetched.append(list(commits)) or [])
    again, walked = sh.rebuild(out)
    assert walked == "not_walked_in_shallow_clone" and again == out
    assert fetched == [[out["source"]["through"], *out["source"]["publication_commits"], repo["morning"]]]
    with pytest.raises(sh.ServiceError, match="cannot walk"):
        sh.build(ref="main")
    with pytest.raises(sh.ServiceError, match="names no commits"):
        sh.rebuild({"source": {}})


# ------------------------------------------------------ the committed one ----

@pytest.fixture(scope="module")
def committed():
    """The dated reading, and the commits it names fetched into a shallow
    checkout -- CI's -- exactly those and once; never skipped."""
    data = json.loads(sh.OUTPUT_JSON.read_text(encoding="utf-8"))
    source = data["source"]
    named = [source["through"], *source["publication_commits"], *(c for v in source["companion_commits"].values() for c in v)]
    sh.fetch_missing(named)
    return data


def test_the_committed_reading_is_what_the_tool_writes(committed):
    assert sh.check(sh.OUT_DIR) == []


def test_the_committed_reading_reads_the_records_it_names(committed):
    # the newest publication's facts, read again off its commit without the tool's own reading
    newest = max(committed["publications"], key=lambda p: (p["session"], p["published_at"]))
    data, blob = sh.read_at(newest["commit"], sh.RECORD_PATH)
    assert blob == newest["blob"]
    run = data["run"]
    assert (run["session"], run["run_id"], run["status"], run["published_at"]) == \
        (newest["session"], newest["run_id"], newest["status"], sh.parse_instant(run["published_at"]).isoformat())
    assert run["calendar"]["measured"]["completion_at"] == "2026-10-09T16:15:00-04:00" and newest["timing"]["completion_at"] == "2026-10-09T20:15:00+00:00"
    assert newest["inputs"]["ready_stocks"] == run["coverage"]["acceptance"]["ready_stocks"]
    assert newest["reader"]["done"] == run["reads"]["done"]
    # every expected XNYS session between the first and the newest is a row, and the sum of rows' publications is the publications
    first, last = committed["sessions"][0]["session"], committed["sessions"][-1]["session"]
    assert [r["session"] for r in committed["sessions"]] == [str(d) for d in sessions.dates(date.fromisoformat(first), date.fromisoformat(last))]
    assert sum(r["revisions"] for r in committed["sessions"]) == len(committed["publications"]) == len(committed["source"]["publication_commits"])
    assert all(r["service"]["before_next_open"] for r in committed["sessions"] if r["published"])


def test_the_report_quotes_the_reading(committed):
    text = REPORT.read_text(encoding="utf-8")
    s = committed["summary"]
    for quoted in (f"{s['published_sessions']} of {s['due_sessions']}", f"median {s['latency_minutes']['median']}",
                   f"longest {s['streak']['longest']}", str(s["publications"]), str(s["after_retry_slot"])):
        assert quoted in text, quoted
    assert committed["source"]["through"][:8] in text
    prose = " ".join(text.split())
    for session in s["resessions"]:       # named as a date or in words ("11 September")
        day = date.fromisoformat(session)
        assert session in prose or f"{day.day} {day.strftime('%B')}" in prose, session
    numbers = {float(n) for n in re.findall(r"\b\d+\.\d\b", text)}
    assert {s["latency_minutes"]["min"], s["latency_minutes"]["median"], s["latency_minutes"]["max"]} <= numbers
