"""tools.stale_inputs: what became of the stocks a publication could not
measure (#111, #109). The join -- each night's newest publication's named
stock-sessions, every later follow-up reading and recovery row of them, and
the class each lands in -- is driven on hand-sized records with hand-computed
answers; the refusals with records that do not parse; a synthetic git
history is walked, written and held by ``--check``; and the committed dated
reading is held to the commits it names, its counts re-derived here straight
off git without the tool's join."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import json
import os
from pathlib import Path
import re
import subprocess

import pytest

from src import followup, scans, source_recovery
from tools import service_health as sh
from tools import stale_inputs as si

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "docs/input-truthfulness/2026-10-17-stale-inputs.md"


def record(session, names=(), endings=None, *, sessions_max=5, version=2, stale=None, rows=None, status="ok", published_at=None):
    tol = {"version": version, "verdict": "tolerated", "names": list(names), "stale_stocks": len(names) if stale is None else stale}
    if endings is not None:
        tol["endings"] = dict(endings)
        tol["sessions_max"] = sessions_max
    run = {"session": session, "status": status, "published_at": published_at or f"{session}T23:00:00+00:00", "input_tolerance": tol}
    if rows is not None:
        run["stale_followup"] = {"version": 2, "status": "applied", "reason": None, "for_session": None, "rows": rows}
    return {"schema_version": 2, "app": {}, "run": run}


def fu(ticker, session, outcome, volume=None, route=None):
    arrived = outcome in followup.ARRIVED
    return {"ticker": ticker, "session": session, "outcome": outcome, "volume": volume if arrived else None,
            "flat": (volume == 0) if arrived and volume is not None else None, "route": route}


def receipt(session, rows, *, dry_run=False, status="partial"):
    return {"frozen": {"session": session}, "status": status, "dry_run": dry_run,
            "rows": [{"ticker": t, "outcome": o, "volume": v} for t, o, v in rows]}


def pubs(*records):
    return [si.publication(r, commit=f"{n:040x}", sequence=n) for n, r in enumerate(records)]


def recs(*receipts, start=100):
    return [si.receipt(r, commit=f"{start + n:040x}", sequence=start + n) for n, r in enumerate(receipts)]


# ------------------------------------------------------------- missed ----

def test_a_named_stock_counts_every_session_it_missed_on_the_exchanges_calendar():
    # ending Thursday 8 October, named on Tuesday 13 October: Friday, Monday and Tuesday (the 10th and 11th a weekend)
    p = si.publication(record("2026-10-13", ["AAA", "BBB"], {"AAA": "2026-10-08", "BBB": "2026-10-12"}), commit="a" * 40, sequence=0)
    assert p["tolerance"]["missed"] == {"AAA": ["2026-10-09", "2026-10-12", "2026-10-13"], "BBB": ["2026-10-13"]}
    # the night's own bound: the most recent two of them
    p = si.publication(record("2026-10-13", ["AAA"], {"AAA": "2026-10-08"}, sessions_max=2), commit="a" * 40, sequence=0)
    assert p["tolerance"]["missed"] == {"AAA": ["2026-10-12", "2026-10-13"]}


def test_a_first_version_record_without_endings_is_read_at_its_own_session_alone():
    p = si.publication(record("2026-10-07", ["AAA"], None, version=1), commit="a" * 40, sequence=0)
    assert p["tolerance"]["missed"] == {"AAA": ["2026-10-07"]} and p["tolerance"]["endings_recorded"] is False


def test_a_record_from_before_the_tolerance_names_nothing():
    data = record("2026-10-06")
    del data["run"]["input_tolerance"]
    assert si.publication(data, commit="a" * 40, sequence=0)["tolerance"] is None
    rows, nights = si.join(pubs(data), [])
    assert rows == [] and nights == []


@pytest.mark.parametrize("mutate, match", [
    (lambda d: d["run"]["input_tolerance"].update(names="AAA"), "names is not a list"),
    (lambda d: d["run"]["input_tolerance"].update(names=[""]), "not a ticker"),
    (lambda d: d["run"]["input_tolerance"]["endings"].update(AAA="soon"), "not a date"),
    (lambda d: d["run"]["input_tolerance"].update(stale_stocks=-1), "not a count"),
    (lambda d: d["run"].update(stale_followup=[]), "stale_followup is not an object"),
    (lambda d: d["run"].update(stale_followup={"rows": [{"ticker": "AAA", "session": "2026-10-12", "outcome": "listed"}]}), "no outcome"),
    (lambda d: d["run"].update(stale_followup={"rows": [{"ticker": "AAA", "session": "2026-10-12", "outcome": "no_match", "volume": -3}]}), "not a volume"),
    (lambda d: d.update(fixture="full"), "not a real schema-2 publication"),
])
def test_a_record_the_reading_cannot_place_is_refused(mutate, match):
    data = record("2026-10-13", ["AAA"], {"AAA": "2026-10-12"})
    mutate(data)
    with pytest.raises(sh.ServiceError, match=match):
        si.publication(data, commit="a" * 40, sequence=0)


def test_a_receipt_the_reading_cannot_place_is_refused():
    with pytest.raises(si.StaleError, match="not a source-recovery receipt"):
        si.receipt({"rows": []}, commit="a" * 40, sequence=0)
    with pytest.raises(si.StaleError, match="no outcome"):
        si.receipt(receipt("2026-10-13", [("AAA", "found", 0)]), commit="a" * 40, sequence=0)


# --------------------------------------------------------------- join ----

def scenario():
    """Night 13 October names eight stocks; the next night's follow-up and a
    recovery receipt read them again, one stock to each class."""
    night = record("2026-10-13", ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH"],
                   {t: "2026-10-12" for t in "AAA BBB CCC DDD EEE FFF GGG HHH".split()})
    nxt = record("2026-10-14", [], {}, rows=[
        fu("AAA", "2026-10-13", "no_match", 0), fu("BBB", "2026-10-13", "no_match", 40),
        fu("CCC", "2026-10-13", "price_excluded", 0), fu("DDD", "2026-10-13", "still_missing"),
        fu("FFF", "2026-10-13", "not_selected"), fu("HHH", "2026-10-13", "unmeasurable", 99_999)])
    later = record("2026-10-15", [], {}, rows=[fu("AAA", "2026-10-13", "match", 0, route="setting_up")])
    rc = receipt("2026-10-13", [("DDD", "recovered", 0), ("EEE", "recovered", scans.MIN_VOLUME), ("FFF", "still_stale", None)])
    dry = receipt("2026-10-13", [("GGG", "recovered", 5)], dry_run=True)
    return pubs(night, nxt, later), recs(rc, dry)


def test_each_stock_session_lands_in_the_first_class_that_holds():
    rows, nights = si.join(*scenario())
    got = {r["ticker"]: r["class"] for r in rows}
    assert got == {
        "AAA": "would_have_been_listed",               # a match anywhere, even before a later no_match
        "BBB": "scanned_not_listed",                   # the last follow-up reading ran the scans
        "CCC": "under_price_policy",
        "DDD": "under_volume_floor_unscanned",         # the follow-up still missed it; the receipt's bar did not
        "EEE": "at_or_above_volume_floor_unscanned",   # the floor is inclusive: MIN_VOLUME itself is at it
        "FFF": "no_later_bar",
        "GGG": "no_later_bar",                         # a rehearsal receipt is never read
        "HHH": "under_volume_floor_unscanned",         # arrived but unmeasurable: one share under the floor
    }
    assert [n["session"] for n in nights] == ["2026-10-13", "2026-10-14", "2026-10-15"]
    assert nights[0]["stock_sessions"] == 8 and nights[1]["stock_sessions"] == 0
    aaa = next(r for r in rows if r["ticker"] == "AAA")
    assert [x["read_by"] for x in aaa["followup"]] == ["2026-10-14", "2026-10-15"] and aaa["followup_final"] == "match"


def test_the_summary_and_its_sentence_are_hand_computed():
    p, r = scenario()
    rows, nights = si.join(p, r)
    s = si.summary(rows, nights, p, r)
    assert s["stock_sessions"] == 8 and s["stocks"] == 8 and s["nights"] == 3
    assert s["classes"] == {"would_have_been_listed": 1, "scanned_not_listed": 1, "under_price_policy": 1,
                            "under_volume_floor_unscanned": 2, "at_or_above_volume_floor_unscanned": 1, "no_later_bar": 2}
    # later bars: AAA 0, BBB 40, CCC 0, DDD 0, EEE MIN_VOLUME, HHH 99,999
    assert s["with_later_bar"] == 6 and s["zero_volume"] == 3 and s["max_volume"] == scans.MIN_VOLUME
    assert s["followup"] == {"readings": 7, "stock_sessions_read": 6, "matches": 1,
                             "final_outcomes": {**{o: 0 for o in followup.OUTCOMES}, "match": 1, "no_match": 1, "price_excluded": 1,
                                                "still_missing": 1, "not_selected": 1, "unmeasurable": 1}}
    assert s["recovery"]["receipts"] == 2 and s["recovery"]["stock_sessions_read"] == 3
    assert s["recovery"]["outcomes"] == {**{o: 0 for o in source_recovery.OUTCOMES}, "recovered": 2, "still_stale": 1}
    assert s["no_later_bar"] == {"count": 2, "not_read_again": 1,
                                 "followup_final": {**{o: 0 for o in followup.OUTCOMES}, "not_selected": 1}}
    words = si.sentence(s)
    assert words.startswith("From 2026-10-13 to 2026-10-15 the newest publication of each of 3 nights named 8 stale stock-sessions (8 stocks): ")
    assert "1 would have been listed, by a follow-up (7 readings)" in words
    assert "1 carry a later bar at or above that floor, not yet scanned" in words
    assert "the largest 100,000 shares" in words and words.endswith("Why a bar was absent is not established.")


def test_no_match_is_said_only_when_there_is_none():
    p = pubs(record("2026-10-13", ["AAA"], {"AAA": "2026-10-12"}), record("2026-10-14", [], {}, rows=[fu("AAA", "2026-10-13", "no_match", 0)]))
    rows, nights = si.join(p, [])
    words = si.sentence(si.summary(rows, nights, p, []))
    assert "No follow-up reading found a late bar that would have been listed (1 readings)" in words
    assert "at or above" not in words and "read only for its volume" not in words
    assert si.sentence(si.summary([], [], [], [])) == "No retained publication names a stale stock."


def test_a_later_bar_with_no_volume_read_is_refused():
    p = pubs(record("2026-10-13", ["AAA"], {"AAA": "2026-10-12"}))
    with pytest.raises(si.StaleError, match="no volume read"):
        si.join(p, recs(receipt("2026-10-13", [("AAA", "recovered", None)])))


def test_only_the_newest_publication_of_a_session_names_its_stale_stocks():
    first = record("2026-10-09", ["XXX", "YYY", "ZZZ"], {t: "2026-10-08" for t in ("XXX", "YYY", "ZZZ")}, status="degraded")
    rerun = record("2026-10-09", ["YYY"], {"YYY": "2026-10-08"})
    rows, nights = si.join(pubs(first, rerun), [])
    assert [(r["ticker"], r["session"]) for r in rows] == [("YYY", "2026-10-09")]
    assert nights == [{"session": "2026-10-09", "commit": f"{1:040x}", "revisions": 2, "status": "ok", "verdict": "tolerated",
                       "tolerance_version": 2, "stale_stocks": 1, "named": 1, "unnamed": 0, "endings_recorded": True,
                       "stock_sessions": 1, "measured_by_revision": 2}]


def test_a_stock_session_named_by_two_nights_is_one_row_with_both():
    a = record("2026-10-13", ["AAA"], {"AAA": "2026-10-12"})
    b = record("2026-10-14", ["AAA"], {"AAA": "2026-10-12"})
    rows, _ = si.join(pubs(a, b), [])
    assert [(r["session"], r["named_by"]) for r in rows] == [("2026-10-13", ["2026-10-13", "2026-10-14"]), ("2026-10-14", ["2026-10-14"])]


def test_unnamed_stale_stocks_and_recurring_names_are_counted():
    nights = [record(d, ["AAA"], {"AAA": "2026-10-08"}, sessions_max=1, stale=3) for d in ("2026-10-09", "2026-10-12", "2026-10-13")]
    p = pubs(*nights)
    rows, n = si.join(p, [])
    s = si.summary(rows, n, p, [])
    assert s["unnamed_stale"] == 6 and s["recurring"] == [{"ticker": "AAA", "nights": 3}]
    p2 = pubs(*nights[:2])
    rows2, n2 = si.join(p2, [])
    assert si.summary(rows2, n2, p2, [])["recurring"] == []


# ------------------------------------------------------ a synthetic git ----

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
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    fixture = commit(repo, "docs/data.json", {**record("2026-10-12", ["QQQ"], {}), "fixture": "full"}, "fixture", "2026-10-13T00:00:00+00:00")
    first = commit(repo, "docs/data.json", record("2026-10-13", ["AAA", "BBB"], {"AAA": "2026-10-12", "BBB": "2026-10-12"}),
                   "run 2026-10-13", "2026-10-14T01:00:00+00:00")
    rc = commit(repo, "docs/source-recovery.json", receipt("2026-10-13", [("AAA", "recovered", 0), ("BBB", "still_stale", None)]),
                "Publish bound source recovery", "2026-10-14T12:00:00+00:00")
    second = commit(repo, "docs/data.json", record("2026-10-14", [], {}, rows=[fu("AAA", "2026-10-13", "no_match", 0), fu("BBB", "2026-10-13", "not_selected")]),
                    "run 2026-10-14", "2026-10-15T01:00:00+00:00")
    monkeypatch.setattr(sh, "ROOT", repo)
    return {"repo": repo, "fixture": fixture, "first": first, "receipt": rc, "second": second}


def test_a_history_is_walked_joined_and_the_set_asides_are_named(repo):
    result = si.build(ref="main")
    assert result["source"]["through"] == repo["second"]
    assert result["source"]["publication_commits"] == [repo["second"], repo["first"], repo["fixture"]]
    assert result["source"]["recovery_commits"] == [repo["receipt"]]
    assert result["skipped"] == [{"commit": repo["fixture"], "reason": f"{repo['fixture'][:8]}:docs/data.json: not a real schema-2 publication"}]
    assert {r["ticker"]: r["class"] for r in result["stock_sessions"]} == {"AAA": "scanned_not_listed", "BBB": "no_later_bar"}
    earlier = si.build(ref="main", through=repo["receipt"])
    assert {r["ticker"]: r["class"] for r in earlier["stock_sessions"]} == {"AAA": "under_volume_floor_unscanned", "BBB": "no_later_bar"}
    with pytest.raises(sh.ServiceError, match="raise --limit"):
        si.build(ref="main", limit=3)


def test_the_written_files_are_held_by_check_and_a_drift_is_named(repo, tmp_path):
    out = tmp_path / "out"
    assert si.main(["--ref", "main", "--output-dir", str(out)]) == 0
    assert si.main(["--check", "--output-dir", str(out)]) == 0
    written = json.loads((out / si.OUTPUT_JSON.name).read_text())
    drifted = deepcopy(written)
    drifted["summary"]["classes"]["no_later_bar"] -= 1
    (out / si.OUTPUT_JSON.name).write_text(json.dumps(drifted, indent=1, sort_keys=True) + "\n")
    assert si.check(out) == [f"{si.OUTPUT_JSON.name} is not what the tool writes from its named commits"]
    (out / si.OUTPUT_JSON.name).write_text(json.dumps(written, indent=1, sort_keys=True) + "\n")
    (out / si.OUTPUT_MD.name).write_text("# not the reading\n")
    assert si.check(out) == [f"{si.OUTPUT_MD.name} is not what the tool writes"]
    forged = deepcopy(written)
    forged["source"]["recovery_commits"] = []
    (out / si.OUTPUT_JSON.name).write_text(json.dumps(forged, indent=1, sort_keys=True) + "\n")
    with pytest.raises(sh.ServiceError, match="not the history's"):
        si.check(out)
    assert si.main(["--check", "--output-dir", str(tmp_path / "nowhere")]) == 1


def test_a_shallow_checkout_rebuilds_from_the_named_commits_alone(repo, monkeypatch):
    out = si.build(ref="main")
    fetched = []
    monkeypatch.setattr(sh, "shallow", lambda: True)
    monkeypatch.setattr(sh, "fetch_missing", lambda commits: fetched.append(list(commits)) or [])
    again, walked = si.rebuild(out)
    assert walked == "not_walked_in_shallow_clone" and again == out
    assert fetched == [[out["source"]["through"], *out["source"]["publication_commits"], repo["receipt"]]]
    with pytest.raises(sh.ServiceError, match="cannot walk"):
        si.build(ref="main")
    with pytest.raises(sh.ServiceError, match="names no commits"):
        si.rebuild({"source": {}})


# ------------------------------------------------------ the committed one ----

@pytest.fixture(scope="module")
def committed():
    """The dated reading, and the commits it names fetched into a shallow
    checkout -- CI's -- exactly those and once; never skipped."""
    data = json.loads(si.OUTPUT_JSON.read_text(encoding="utf-8"))
    source = data["source"]
    sh.fetch_missing([source["through"], *source["publication_commits"], *source["recovery_commits"]])
    return data


def test_the_committed_reading_is_what_the_tool_writes(committed):
    assert si.check(si.OUT_DIR) == []


def _show(commit: str, path: str):
    done = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT, capture_output=True)
    if done.returncode != 0:
        return None
    try:
        return json.loads(done.stdout)
    except ValueError:
        return None


def test_the_committed_counts_rederive_straight_off_git(committed):
    """Without the tool's join: each session's newest real record (the walk's
    first commit for it, the walk being newest first) names its stocks, every
    later record's follow-up rows and every receipt's rows are read raw, and
    the classes counted again."""
    src = committed["source"]
    newest, readings = {}, {}
    for c in src["publication_commits"]:                       # newest first
        data = _show(c, "docs/data.json")
        if not isinstance(data, dict) or data.get("fixture") or data.get("schema_version") != 2:
            continue
        run = data["run"]
        tol = run.get("input_tolerance")
        if tol is not None and run["session"] not in newest:
            newest[run["session"]] = tol
        for r in (run.get("stale_followup") or {}).get("rows", []):
            readings.setdefault((r["ticker"], r["session"]), []).append(r)    # newest reading first
    named = set()
    for session, tol in newest.items():
        for t in tol["names"]:
            ending = (tol.get("endings") or {}).get(t)
            for d in followup.missed_sessions(date.fromisoformat(ending) if ending else None, date.fromisoformat(session), tol.get("sessions_max") or 1):
                named.add((t, d.isoformat()))
    recovered = {}
    for c in src["recovery_commits"]:
        rc = _show(c, "docs/source-recovery.json")
        if rc and rc.get("dry_run") is False:
            for r in rc["rows"]:
                if r["outcome"] in source_recovery.ARRIVED:
                    recovered.setdefault((r["ticker"], rc["frozen"]["session"]), []).append(r["volume"])
    classes = {k: 0 for k in si.CLASSES}
    for key in named:
        fus = readings.get(key, [])
        vols = [r["volume"] for r in fus if r["outcome"] in followup.ARRIVED] + recovered.get(key, [])
        if any(r["outcome"] == "match" for r in fus):
            classes["would_have_been_listed"] += 1
        elif fus and fus[0]["outcome"] == "no_match":
            classes["scanned_not_listed"] += 1
        elif fus and fus[0]["outcome"] == "price_excluded":
            classes["under_price_policy"] += 1
        elif vols:
            classes["at_or_above_volume_floor_unscanned" if max(vols) >= scans.MIN_VOLUME else "under_volume_floor_unscanned"] += 1
        else:
            classes["no_later_bar"] += 1
    s = committed["summary"]
    assert len(named) == s["stock_sessions"] == len(committed["stock_sessions"])
    assert classes == s["classes"]
    assert s["nights"] == len(newest) == len(committed["nights"])
    assert sum(len(v) for k, v in readings.items() if k in named) == s["followup"]["readings"]
    assert s["followup"]["matches"] == sum(1 for k, v in readings.items() if k in named for r in v if r["outcome"] == "match")


def test_the_report_quotes_the_reading(committed):
    text = REPORT.read_text(encoding="utf-8")
    s = committed["summary"]
    assert committed["sentence"] in " ".join(text.split())
    assert f"`{committed['source']['through'][:8]}`" in text
    for n in committed["nights"]:
        assert re.search(rf"\| {n['session']} \| `{n['commit'][:8]}` \| {n['stale_stocks']} \| {n['stock_sessions']} \|", text), n["session"]
    assert f"{s['recovery']['receipts']} source-recovery receipts" in text
    assert ", ".join(f"{r['ticker']} ({r['nights']})" for r in s["recurring"]) in text
