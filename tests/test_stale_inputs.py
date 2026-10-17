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

from src import followup, inputs, pipeline, scans, source_recovery
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


def produced(session, names, endings, *, previous, names_max=pipeline.STALE_NAMES_MAX, benchmark=pipeline.BENCHMARK_SYMBOL):
    """A record whose tolerance block is the producer's own: inputs.stale_tolerance
    over a minimal coverage ledger in which every named frame is stale."""
    cov = {"acceptance": {"intended_stocks": 4793, "status": "degraded", "capacity_excluded": 0},
           "sessions": {"evaluated": session, "previous": previous, "latest_bar_dates": {previous: len(names)}},
           "stale": len(names), **{k: 0 for k in inputs.OTHER_EXCEPTIONS}}
    tol = inputs.stale_tolerance(cov, pipeline.STALE_TOLERANCE_FRACTION, names=sorted(names), benchmark=benchmark,
                                 names_max=names_max, endings=endings, sessions_max=pipeline.STALE_SESSIONS_MAX)
    data = record(session)
    data["run"]["input_tolerance"] = tol
    return data


@pytest.mark.parametrize("mutate, match", [
    (lambda d: d["run"]["input_tolerance"].update(names="AAA"), "names is not a list"),
    (lambda d: d["run"]["input_tolerance"].update(names=[""]), "not a ticker"),
    (lambda d: d["run"]["input_tolerance"]["endings"].update(AAA="soon"), "not a date"),
    (lambda d: d["run"]["input_tolerance"].update(endings=["AAA"]), "endings is not an object"),
    (lambda d: d["run"].update(input_tolerance=["AAA"]), "input_tolerance is not an object"),
    (lambda d: d["run"]["input_tolerance"].update(stale_stocks=-1), "not a count"),
    (lambda d: d["run"]["input_tolerance"].update(sessions_max=-1), "not a count"),
    (lambda d: d["run"]["input_tolerance"].update(sessions_max=True), "not a count"),
    (lambda d: d["run"].update(stale_followup=[]), "stale_followup is not an object"),
    (lambda d: d["run"].update(stale_followup={"rows": {"AAA": 1}}), "stale_followup.rows is not a list"),
    (lambda d: d["run"].update(stale_followup={"rows": [{"ticker": "AAA", "session": "2026-10-12", "outcome": "listed"}]}), "no outcome"),
    (lambda d: d["run"].update(stale_followup={"rows": [{"ticker": "AAA", "session": "2026-10-12", "outcome": "no_match", "volume": -3}]}), "not a volume"),
    (lambda d: d["run"].update(stale_followup={"rows": [{"ticker": "AAA", "session": "2026-10-12", "outcome": "no_match", "volume": True}]}), "not a volume"),
    (lambda d: d.update(fixture="full"), "not a real schema-2 publication"),
])
def test_a_record_the_reading_cannot_place_is_refused(mutate, match):
    data = record("2026-10-13", ["AAA"], {"AAA": "2026-10-12"})
    mutate(data)
    with pytest.raises(sh.ServiceError, match=match):
        si.publication(data, commit="a" * 40, sequence=0)


@pytest.mark.parametrize("rows, match", [
    ([("AAA", "found", 0)], "no outcome"),
    ([("", "recovered", 0)], "not a ticker"),
    ([("AAA", "recovered", -3)], "not a volume"),
    ([("AAA", "recovered", True)], "not a volume"),
])
def test_a_receipt_the_reading_cannot_place_is_refused(rows, match):
    with pytest.raises(si.StaleError, match=match):
        si.receipt(receipt("2026-10-13", rows), commit="a" * 40, sequence=0)
    with pytest.raises(si.StaleError, match="not a source-recovery receipt"):
        si.receipt({"rows": []}, commit="a" * 40, sequence=0)


def test_a_receipt_read_only_when_it_says_it_was_no_rehearsal():
    night = record("2026-10-13", ["AAA", "BBB", "CCC"], {t: "2026-10-12" for t in ("AAA", "BBB", "CCC")})
    real = receipt("2026-10-13", [("AAA", "recovered", 0)])
    rehearsal = receipt("2026-10-13", [("BBB", "recovered", 0)], dry_run=True)
    unsaid = receipt("2026-10-13", [("CCC", "recovered", 0)])
    del unsaid["dry_run"]
    rows, _ = si.join(pubs(night), recs(real, rehearsal, unsaid))
    assert {r["ticker"]: r["class"] for r in rows} == {"AAA": "under_volume_floor_unscanned", "BBB": "no_later_bar",
                                                        "CCC": "no_later_bar"}


# --------------------------------------------------------------- join ----

G = {"would": ["AAA"], "scanned": ["S1", "S2", "S3", "S4"], "price": ["P1", "P2"], "under": ["U1", "U2", "U3"],
     "above": [f"V{i}" for i in range(1, 9)], "unread": [f"R{i}" for i in range(1, 6)], "none": [f"N{i}" for i in range(1, 6)]}


def scenario():
    """Night 13 October names 28 stocks; the 14 October night names AAA again
    (so AAA is two stock-sessions); the next nights' follow-ups and a recovery
    receipt read them again. Every class has a different count -- 1, 4, 2, 3,
    8, 5, 6 -- so no two clauses of the sentence can trade places unseen."""
    tickers = [t for g in G.values() for t in g]
    night = record("2026-10-13", tickers, {t: "2026-10-12" for t in tickers})
    nxt = record("2026-10-14", ["AAA"], {"AAA": "2026-10-12"}, rows=[
        fu("AAA", "2026-10-13", "match", 0, route="setting_up"),       # a match, then a later no_match: still listed
        fu("S1", "2026-10-13", "no_match", 40), fu("S2", "2026-10-13", "no_match", 0), fu("S3", "2026-10-13", "no_match", 0),
        fu("S4", "2026-10-13", "price_excluded", 0),                   # then no_match: the last verdict holds
        fu("P1", "2026-10-13", "price_excluded", 0), fu("P2", "2026-10-13", "price_excluded", 0),
        fu("U1", "2026-10-13", "still_missing"), fu("U2", "2026-10-13", "unmeasurable", scans.MIN_VOLUME - 1),
        fu("U3", "2026-10-13", "not_selected"), fu("N1", "2026-10-13", "still_missing"), fu("N2", "2026-10-13", "not_selected")])
    later = record("2026-10-15", [], {}, rows=[
        fu("AAA", "2026-10-13", "no_match", 0),
        fu("S2", "2026-10-13", "not_selected"),                        # a later reading with no verdict cannot undo a scan
        fu("S3", "2026-10-13", "still_missing"),
        fu("S4", "2026-10-13", "no_match", 0),
        fu("P2", "2026-10-13", "not_selected")])
    rc = receipt("2026-10-13", [("S1", "recovered", 0), ("U1", "recovered", 0), ("U3", "recovered", 7),
                                *[(f"V{i}", "recovered", scans.MIN_VOLUME + i - 1) for i in range(1, 9)],
                                *[(f"R{i}", "arrived_not_ready", None) for i in range(1, 6)],
                                ("N3", "still_stale", None)])
    dry = receipt("2026-10-13", [("N4", "recovered", 5)], dry_run=True)
    return pubs(night, nxt, later), recs(rc, dry)


def test_each_stock_session_lands_in_the_first_class_that_holds():
    rows, nights = si.join(*scenario())
    got = {(r["ticker"], r["session"]): r["class"] for r in rows}
    want = {**{(t, "2026-10-13"): k for k, g in [("would_have_been_listed", G["would"]), ("scanned_not_listed", G["scanned"]),
                                                 ("under_price_policy", G["price"]), ("under_volume_floor_unscanned", G["under"]),
                                                 ("at_or_above_volume_floor_unscanned", G["above"]),
                                                 ("arrived_volume_unread", G["unread"]), ("no_later_bar", G["none"])]
               for t in g},
            ("AAA", "2026-10-14"): "no_later_bar"}
    assert got == want
    by = {(r["ticker"], r["session"]): r for r in rows}
    aaa = by[("AAA", "2026-10-13")]
    assert [x["read_by"] for x in aaa["followup"]] == ["2026-10-14", "2026-10-15"]
    assert aaa["followup_final"] == "no_match" and aaa["named_by"] == ["2026-10-13", "2026-10-14"]
    assert by[("S2", "2026-10-13")]["followup_final"] == "not_selected" and by[("S2", "2026-10-13")]["followup_verdict"] == "no_match"
    assert by[("S4", "2026-10-13")]["followup_verdict"] == "no_match"            # the LAST verdict, not the first
    assert by[("P2", "2026-10-13")]["followup_verdict"] == "price_excluded"
    assert by[("S1", "2026-10-13")]["max_volume"] == 40 and by[("S1", "2026-10-13")]["zero_volume"] is False
    assert by[("U3", "2026-10-13")]["max_volume"] == 7                         # the receipt's bar, beside a follow-up with none
    assert [n["session"] for n in nights] == ["2026-10-13", "2026-10-14", "2026-10-15"]
    assert [n["stock_sessions"] for n in nights] == [28, 2, 0]
    assert nights[0]["classes"] == {"would_have_been_listed": 1, "scanned_not_listed": 4, "under_price_policy": 2,
                                    "under_volume_floor_unscanned": 3, "at_or_above_volume_floor_unscanned": 8,
                                    "arrived_volume_unread": 5, "no_later_bar": 5}
    assert nights[1]["classes"] == {**{k: 0 for k in si.CLASSES}, "would_have_been_listed": 1, "no_later_bar": 1}


def test_a_verdict_is_the_last_reading_that_gave_one():
    night = record("2026-10-13", ["AAA", "BBB", "CCC", "DDD"], {t: "2026-10-12" for t in ("AAA", "BBB", "CCC", "DDD")})
    first = record("2026-10-14", [], {}, rows=[fu("AAA", "2026-10-13", "no_match", 0), fu("BBB", "2026-10-13", "price_excluded", 0),
                                               fu("CCC", "2026-10-13", "no_match", 0), fu("DDD", "2026-10-13", "price_excluded", 0)])
    rerun = record("2026-10-14", [], {}, rows=[fu("AAA", "2026-10-13", "price_excluded", 0), fu("BBB", "2026-10-13", "no_match", 0),
                                               fu("CCC", "2026-10-13", "unmeasurable", 0), fu("DDD", "2026-10-13", "still_missing")])
    rows, _ = si.join(pubs(night, first, rerun), [])
    assert {r["ticker"]: r["class"] for r in rows} == {"AAA": "under_price_policy", "BBB": "scanned_not_listed",
                                                        "CCC": "scanned_not_listed", "DDD": "under_price_policy"}


def test_the_summary_and_its_sentence_are_hand_computed():
    p, r = scenario()
    rows, nights = si.join(p, r)
    s = si.summary(rows, nights, p, r)
    assert s["stock_sessions"] == 29 and s["stocks"] == 28 and s["nights"] == 3
    assert s["classes"] == {"would_have_been_listed": 1, "scanned_not_listed": 4, "under_price_policy": 2,
                            "under_volume_floor_unscanned": 3, "at_or_above_volume_floor_unscanned": 8,
                            "arrived_volume_unread": 5, "no_later_bar": 6}
    # later bars: every class but no_later_bar; the five unread carry no volume;
    # zero: AAA, S2, S3, S4, P1, P2 and U1 (S1 also printed 40, U2 99,999, U3 7)
    assert s["with_later_bar"] == 23 and s["with_volume_read"] == 18 and s["zero_volume"] == 7
    assert s["max_volume"] == scans.MIN_VOLUME + 7
    assert s["followup"] == {"readings": 17, "stock_sessions_read": 12, "matches": 1,
                             "final_outcomes": {**{o: 0 for o in followup.OUTCOMES}, "no_match": 3, "price_excluded": 1,
                                                "still_missing": 3, "not_selected": 4, "unmeasurable": 1}}
    assert s["recovery"]["receipts"] == 2 and s["recovery"]["stock_sessions_read"] == 17
    assert s["recovery"]["statuses"] == {**{k: 0 for k in source_recovery.STATUSES}, "partial": 2}
    assert s["recovery"]["outcomes"] == {**{o: 0 for o in source_recovery.OUTCOMES}, "recovered": 11, "arrived_not_ready": 5,
                                         "still_stale": 1}
    assert s["no_later_bar"] == {"count": 6, "not_read_again": 3,
                                 "followup_final": {**{o: 0 for o in followup.OUTCOMES}, "still_missing": 1, "not_selected": 1}}
    assert s["measured_by_revision"] == 0 and s["publications_naming"] == 3 and s["publications_read"] == 3
    floor = f"{scans.MIN_VOLUME:,}"
    assert si.sentence(s) == (
        "From 2026-10-13 to 2026-10-15 the newest publication of each of 3 nights named 29 stale stock-sessions (28 stocks): "
        "4 were scanned again by a follow-up on their late bar and would not have been listed; "
        "2 fell under the $3 session-close policy; "
        f"3 carry a later bar read only for its volume, under the {floor}-share floor of the 4%, breakdown and $ scans "
        "(the setting-up scans not read); "
        "8 carry a later bar at or above that floor, not yet scanned; "
        "5 carry a later bar whose volume could not be read; "
        "6 have no later bar read by either source. "
        "1 would have been listed, by a follow-up (17 readings). "
        f"Of the 23 later bars, 18 with a volume read, 7 have zero volume and the largest {scans.MIN_VOLUME + 7:,} shares. "
        "Why a bar was absent is not established.")


def test_no_match_is_said_only_when_there_is_none():
    p = pubs(record("2026-10-13", ["AAA"], {"AAA": "2026-10-12"}), record("2026-10-14", [], {}, rows=[fu("AAA", "2026-10-13", "no_match", 0)]))
    rows, nights = si.join(p, [])
    words = si.sentence(si.summary(rows, nights, p, []))
    assert "No follow-up reading found a late bar that would have been listed (1 readings)" in words
    assert "at or above" not in words and "read only for its volume" not in words and "could not be read" not in words
    assert si.sentence(si.summary([], [], [], [])) == "No retained publication names a stale stock."


def test_a_night_whose_stocks_have_no_later_reading_yet_is_read_without_a_volume():
    # the real history through its first tolerance night (7 October) had exactly this shape
    p = pubs(record("2026-10-13", ["AAA", "BBB"], {"AAA": "2026-10-12", "BBB": "2026-10-12"}))
    rows, nights = si.join(p, [])
    s = si.summary(rows, nights, p, [])
    assert s["with_later_bar"] == 0 and s["max_volume"] is None
    assert si.sentence(s).endswith("2 have no later bar read by either source. No follow-up reading found a late bar that would "
                                   "have been listed (0 readings). No named stock-session has a later bar yet. "
                                   "Why a bar was absent is not established.")
    rows, nights = si.join(p, recs(receipt("2026-10-13", [("AAA", "arrived_not_ready", None)])))
    assert "Of the 1 later bars, none had a volume read." in si.sentence(si.summary(rows, nights, p, []))


def test_a_later_bar_that_arrived_with_its_volume_unread_is_its_own_class():
    # both producers write such a row: a recovery arrived_not_ready with an
    # unreadable bar, a follow-up unmeasurable on a NaN volume
    p = pubs(record("2026-10-13", ["AAA", "BBB"], {"AAA": "2026-10-12", "BBB": "2026-10-12"}),
             record("2026-10-14", [], {}, rows=[fu("BBB", "2026-10-13", "unmeasurable", None)]))
    rows, _ = si.join(p, recs(receipt("2026-10-13", [("AAA", "arrived_not_ready", None)])))
    assert {r["ticker"]: r["class"] for r in rows} == {"AAA": "arrived_volume_unread", "BBB": "arrived_volume_unread"}


def test_only_the_newest_publication_of_a_session_names_its_stale_stocks():
    first = record("2026-10-09", ["XXX", "YYY", "ZZZ"], {t: "2026-10-08" for t in ("XXX", "YYY", "ZZZ")}, status="degraded")
    rerun = record("2026-10-09", ["YYY"], {"YYY": "2026-10-08"})
    rows, nights = si.join(pubs(first, rerun), [])
    assert [(r["ticker"], r["session"]) for r in rows] == [("YYY", "2026-10-09")]
    assert nights == [{"session": "2026-10-09", "commit": f"{1:040x}", "revisions": 2, "status": "ok", "verdict": "tolerated",
                       "tolerance_version": 2, "stale_stocks": 1, "named": 1, "unnamed": 0, "names_carried": True,
                       "endings_recorded": True, "stock_sessions": 1, "measured_by_revision": 2,
                       "classes": {**{k: 0 for k in si.CLASSES}, "no_later_bar": 1}}]


def test_a_night_over_the_names_bound_is_kept_as_the_newest_and_counted_unnamed():
    # the producer names no frame over pipeline.STALE_NAMES_MAX; the night still
    # stands, its revision before it does not stand in for it
    named = produced("2026-10-13", ["AAA"], {"AAA": "2026-10-12"}, previous="2026-10-12")
    over = produced("2026-10-13", [f"S{i:03d}" for i in range(4)], {}, previous="2026-10-12", names_max=3)
    assert over["run"]["input_tolerance"]["names"] is None
    p = pubs(named, over)
    rows, nights = si.join(p, [])
    assert rows == []
    assert [(n["commit"], n["revisions"], n["named"], n["unnamed"], n["names_carried"], n["measured_by_revision"]) for n in nights] \
        == [(f"{1:040x}", 2, 0, 4, False, None)]
    s = si.summary(rows, nights, p, [])
    assert s["unnamed_stale"] == 4 and s["nights_names_not_carried"] == 1 and s["measured_by_revision"] == 0


def test_the_benchmark_named_beside_the_stocks_is_not_a_stock():
    data = produced("2026-10-13", ["AAA", pipeline.BENCHMARK_SYMBOL], {"AAA": "2026-10-12", pipeline.BENCHMARK_SYMBOL: "2026-10-12"},
                    previous="2026-10-12")
    tol = data["run"]["input_tolerance"]
    assert tol["names"] == ["AAA", pipeline.BENCHMARK_SYMBOL] and tol["stale_stocks"] == 1      # the producer's own shape
    rows, nights = si.join(pubs(data), [])
    assert [r["ticker"] for r in rows] == ["AAA"]
    assert (nights[0]["named"], nights[0]["unnamed"], nights[0]["stale_stocks"]) == (1, 0, 1)


def test_a_stock_session_named_by_two_nights_is_one_row_with_both():
    a = record("2026-10-13", ["AAA"], {"AAA": "2026-10-12"})
    b = record("2026-10-14", ["AAA"], {"AAA": "2026-10-12"})
    rows, nights = si.join(pubs(a, b), [])
    assert [(r["session"], r["named_by"]) for r in rows] == [("2026-10-13", ["2026-10-13", "2026-10-14"]), ("2026-10-14", ["2026-10-14"])]
    assert [n["classes"]["no_later_bar"] for n in nights] == [1, 2]


def test_recurring_names_count_nights_not_sessions_and_sort_by_nights():
    # ZZZ, ending 7 October, is named on four nights and is five stock-sessions;
    # BBB on three nights; neither is alphabetical order
    nights = [record("2026-10-09", ["ZZZ"], {"ZZZ": "2026-10-07"}),
              *[record(d, ["BBB", "ZZZ"], {"BBB": "2026-10-09", "ZZZ": "2026-10-07"}) for d in ("2026-10-12", "2026-10-13", "2026-10-14")],
              record("2026-10-15", ["CCC"], {"CCC": "2026-10-14"})]
    p = pubs(*nights)
    rows, n = si.join(p, [])
    s = si.summary(rows, n, p, [])
    assert sum(1 for r in rows if r["ticker"] == "ZZZ") == 5
    assert s["recurring"] == [{"ticker": "ZZZ", "nights": 4}, {"ticker": "BBB", "nights": 3}]
    assert si.summary(*si.join(pubs(*nights[:2]), []), pubs(*nights[:2]), [])["recurring"] == []


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
    for forge in (lambda f: f["source"].update(recovery_commits=[]),
                  lambda f: f["source"]["publication_commits"].remove(repo["first"]),
                  lambda f: f["skipped"].append({"commit": repo["second"], "reason": f"{repo['second'][:8]}: no docs/data.json at this commit"})):
        forged = deepcopy(written)
        forge(forged)
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
    unsaid = deepcopy(out)
    unsaid["skipped"] = []                                # the fixture commit is set aside and nothing says so
    with pytest.raises(sh.ServiceError, match="does not say so"):
        si.rebuild(unsaid)
    extra = deepcopy(out)                                 # a set-aside no named commit produces
    extra["skipped"].append({"commit": repo["second"], "reason": f"{repo['second'][:8]}: no docs/data.json at this commit"})
    with pytest.raises(sh.ServiceError, match="do not produce"):
        si.rebuild(extra)
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
            # the benchmark is named beside the stocks; a night over the names bound names none
            newest[run["session"]] = dict(tol, names=[t for t in tol["names"] or [] if t != tol.get("benchmark", pipeline.BENCHMARK_SYMBOL)])
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
        fus = readings.get(key, [])                                   # newest first
        verdict = next((r["outcome"] for r in fus if r["outcome"] in ("no_match", "price_excluded")), None)
        arrived = any(r["outcome"] in followup.ARRIVED for r in fus) or key in recovered
        vols = [v for v in [r["volume"] for r in fus if r["outcome"] in followup.ARRIVED] + recovered.get(key, []) if v is not None]
        if any(r["outcome"] == "match" for r in fus):
            classes["would_have_been_listed"] += 1
        elif verdict == "no_match":
            classes["scanned_not_listed"] += 1
        elif verdict == "price_excluded":
            classes["under_price_policy"] += 1
        elif vols:
            classes["at_or_above_volume_floor_unscanned" if max(vols) >= scans.MIN_VOLUME else "under_volume_floor_unscanned"] += 1
        elif arrived:
            classes["arrived_volume_unread"] += 1
        else:
            classes["no_later_bar"] += 1
    s = committed["summary"]
    assert len(named) == s["stock_sessions"] == len(committed["stock_sessions"])
    assert classes == s["classes"]
    assert s["nights"] == len(newest) == len(committed["nights"])
    assert sum(len(v) for k, v in readings.items() if k in named) == s["followup"]["readings"]
    assert s["followup"]["matches"] == sum(1 for k, v in readings.items() if k in named for r in v if r["outcome"] == "match")


WORDS = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
         "seventeen eighteen nineteen twenty").split()
BULLETS = {"would_have_been_listed": "would have been listed", "scanned_not_listed": "scanned, not listed",
           "under_price_policy": "under the price policy", "under_volume_floor_unscanned": "volume only, under the floor",
           "at_or_above_volume_floor_unscanned": "volume only, at or above the floor",
           "arrived_volume_unread": "arrived, volume unread", "no_later_bar": "no later bar"}


def _day(session: str) -> str:
    return f"{int(session[8:])} October"


def _days(sessions) -> str:
    """The report's own spelling of a set of October sessions: a run of three or more calendar days is 'a to b',
    shorter runs are listed -- '7 and 13 to 15 October', '8, 9, 12 and 16 October', '14 and 15 October'."""
    days = sorted({int(x[8:]) for x in sessions})
    items, start = [], days[0]
    for a, b in zip(days, days[1:] + [None]):
        if b != a + 1:
            items += [f"{start} to {a}"] if a - start >= 2 else [str(d) for d in range(start, a + 1)]
            start = b
    return (", ".join(items[:-1]) + " and " + items[-1] if len(items) > 1 else items[0]) + " October"


def test_the_report_quotes_the_reading(committed):
    """Every number the dated report prints is built here from the committed reading, or from the records read
    again off git at the commits it names, and found at its own phrase -- never a bare digit anywhere."""
    raw = REPORT.read_text(encoding="utf-8")
    text = " ".join(raw.split())
    s, rows, nights = committed["summary"], committed["stock_sessions"], committed["nights"]
    by = {n["session"]: n for n in nights}
    assert committed["sentence"] in text
    assert f"`{committed['source']['through'][:8]}`" in text
    assert f"{s['publications_read']} real publications read, {len(committed['skipped'])} commits set aside by name" in text
    receipts = [_show(c, "docs/source-recovery.json") for c in committed["source"]["recovery_commits"]]
    sessions = sorted(r["frozen"]["session"] for r in receipts if r and r.get("dry_run") is False)
    assert len(sessions) == s["recovery"]["receipts"]
    assert f"and {s['recovery']['receipts']} source-recovery receipts (the {_days(sessions)} publications')" in text

    # the night table, every column
    for n in nights:
        cells = [n["session"], f"`{n['commit'][:8]}`", n["stale_stocks"], n["stock_sessions"], n["revisions"],
                 n["status"], f"{n['verdict']} (v{n['tolerance_version']})"]
        assert "| " + " | ".join(str(c) for c in cells) + " |" in raw, n["session"]
    assert raw.count("| 2026-10-") == 2 * len(nights)                 # the night table and the class table, nothing else

    # the revised nights: the first publications, their stale counts, what the revisions measured
    revised = [n for n in nights if n["revisions"] > 1]
    first = {}
    for c in reversed(committed["source"]["publication_commits"]):     # oldest first: each session's first publication
        data = _show(c, "docs/data.json")
        if isinstance(data, dict) and data.get("schema_version") == 2 and not data.get("fixture") \
                and data["run"]["session"] in {n["session"] for n in revised} and data["run"]["session"] not in first:
            first[data["run"]["session"]] = (c, data["run"]["input_tolerance"]["stale_stocks"])
    assert [n["session"] for n in revised] == ["2026-10-08", "2026-10-09"]
    for n in revised:
        c, stale = first[n["session"]]
        assert f"`{c[:8]}`" in text and stale == 22
        assert n["measured_by_revision"] == 21 and n["named"] == 1
    assert "named 22 stale stocks each" in text and "measured 21 of them, and WBD alone stayed stale" in text
    assert {r["ticker"] for r in rows if set(r["named_by"]) & {"2026-10-08", "2026-10-09"}} == {"WBD"}

    # the class bullets, each its own count
    for key, label in BULLETS.items():
        m = re.search(rf"- \*\*{re.escape(label)}\*\*.*?\*\*(\d+)\*\*", raw, re.S)
        assert m and int(m.group(1)) == s["classes"][key], key
    under = [r for r in rows if r["class"] == "under_volume_floor_unscanned"]
    newest = max(by)
    late = [r for r in under if newest in r["named_by"]]
    others = sorted((r for r in under if newest not in r["named_by"]), key=lambda r: r["session"])
    assert f"{WORDS[len(late)].capitalize()} of the {WORDS[len(under)]} are the {_day(newest)} night's stocks" in text
    assert f"The other {WORDS[len(others)]} are " + " and ".join(f"{r['ticker']} ({_day(r['session'])})" for r in others) in text
    fkwl = sorted(r["session"] for r in rows if r["ticker"] == "FKWL" and r["class"] == "under_price_policy")
    assert any(r["ticker"] == "FKWL" for r in late)
    assert f"FKWL, under it on {_days(fkwl)}, may not" in text
    none_ = [r for r in rows if r["class"] == "no_later_bar"]
    assert {r["ticker"] for r in none_} == {"WBD"}
    assert f"**{len(none_)}**, every one WBD, at {_days([min(r['session'] for r in none_)])[:-8]} to {_day(max(r['session'] for r in none_))}" in text
    missing = [r["session"] for r in none_ if r["followup_final"] == "still_missing"]
    unselected = [r for r in none_ if r["followup_final"] == "not_selected"]
    assert len(missing) + len(unselected) == len(none_)
    assert f"`still_missing` for {_days(missing)} and `not_selected` for the other {WORDS[len(unselected)]}" in text
    stale_recv = sorted(r["session"] for r in none_ if any(x["outcome"] == "still_stale" for x in r["recovery"]))
    assert f"`still_stale` on each of the {WORDS[len(stale_recv)]} receipts that asked ({_days(stale_recv)})" in text

    # the later bars
    traded = sorted((r for r in rows if r["max_volume"]), key=lambda r: -r["max_volume"])
    assert len(traded) == s["with_later_bar"] - s["zero_volume"] == 2 and traded[0]["max_volume"] == s["max_volume"]
    big, small = traded
    assert (f"Of the {s['with_later_bar']} later bars, {s['zero_volume']} carry zero volume and the largest is "
            f"{big['max_volume']:,} shares ({big['ticker']}, {_day(big['session'])}, a late bar under the price policy)") in text
    assert big["class"] == "under_price_policy" and small["class"] == "scanned_not_listed" and small["session"] == big["session"]
    assert f"the only other is {small['ticker']}'s {small['max_volume']:,} shares the same day, scanned and not listed" in text
    returned = [x for r in rows for x in r["recovery"] if x["outcome"] in source_recovery.ARRIVED]
    assert len(returned) == s["recovery"]["outcomes"]["recovered"] + s["recovery"]["outcomes"]["arrived_not_ready"]
    assert (f"{len(returned)} of the {s['with_later_bar']} are bars the {WORDS[s['recovery']['receipts']]} source-recovery "
            f"receipts returned, {sum(1 for x in returned if x['volume'] == 0)} of them at zero volume") in text
    f, rc = s["followup"], s["recovery"]
    assert f"The follow-up read {f['stock_sessions_read']} of the stock-sessions {f['readings']} times in all" in text
    assert f"none of those readings was a match" in text and f["matches"] == 0
    assert f"The recovery read {rc['stock_sessions_read']}: recovered {rc['outcomes']['recovered']}, still stale {rc['outcomes']['still_stale']}." in text

    # the per-night class table: four columns, and no other class has a member
    for n in nights:
        c = n["classes"]
        assert c["would_have_been_listed"] == c["arrived_volume_unread"] == 0
        cells = [n["session"], c["scanned_not_listed"], c["under_price_policy"],
                 c["under_volume_floor_unscanned"] + c["at_or_above_volume_floor_unscanned"], c["no_later_bar"]]
        assert "| " + " | ".join(str(x) for x in cells) + " |" in raw, n["session"]

    # what it means
    scanned = [r for r in rows if r["class"] == "scanned_not_listed"]
    assert f"The late bars a follow-up scanned -- {len(scanned)} stock-sessions, named on {_days({x for r in scanned for x in r['named_by']})}" in text
    untol = {x for x, n in by.items() if n["verdict"] != "tolerated"}
    tol = sorted(x for x, n in by.items() if n["verdict"] == "tolerated")
    from_untol = [r for r in scanned if set(r["named_by"]) & untol]
    from_tol = [r for r in scanned if set(r["named_by"]) & set(tol)]
    assert {x for r in from_tol for x in r["named_by"]} & set(tol) == {"2026-10-12"}
    assert (f"{len(from_untol)} of the {len(scanned)} come from nights the tolerance did not tolerate ({_days(untol)}), "
            f"so they test the premise on nights it was not relied on; of the nights it did tolerate ({_days(tol)}), "
            f"only 12 October's {len(from_tol)} were scanned") in text
    assert f"the {_day(newest)} night's {by[newest]['stock_sessions']} are read so far only for their volume" in text
    assert by[newest]["stock_sessions"] == by[newest]["classes"]["under_volume_floor_unscanned"] == len(late)
    assert f"Another {s['classes']['under_price_policy']} fell under the $3 policy before any scan" in text
    assert f"for the {s['classes']['under_volume_floor_unscanned']} stock-sessions read only by their volume" in text
    assert f"{s['recovery']['receipts']} source-recovery receipts" in text
    assert ", ".join(f"{r['ticker']} ({r['nights']})" for r in s["recurring"]) in text


INDEX = ROOT / "docs/input-truthfulness/README.md"


def test_the_index_entry_quotes_the_reading(committed):
    entry = " ".join(INDEX.read_text(encoding="utf-8").split("\n\n")[1].split())
    s, rows = committed["summary"], committed["stock_sessions"]
    c = s["classes"]
    assert "(2026-10-17-stale-inputs.md)" in entry
    assert f"{s['stock_sessions']} stale stock-sessions ({s['stocks']} stocks) over {s['nights']} nights" in entry
    assert f"{c['scanned_not_listed']} were scanned again by a follow-up on their late bar and would not have been listed" in entry
    assert f"{c['under_price_policy']} fell under the $3 policy" in entry
    late = [r for r in rows if r["class"] == "under_volume_floor_unscanned" and committed["nights"][-1]["session"] in r["named_by"]]
    assert f"{c['under_volume_floor_unscanned']} carry a later bar read only for its volume" in entry
    assert f"({len(late)} of them the {_day(committed['nights'][-1]['session'])} night's" in entry
    assert f"{c['no_later_bar']} -- every one WBD -- have no later bar" in entry
    assert f"{s['zero_volume']} of the {s['with_later_bar']} later bars carry zero volume" in entry
    assert "Monday" not in entry                       # what a later evening will read is not this reading's to say
