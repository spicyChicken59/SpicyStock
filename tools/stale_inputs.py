"""What became of the stocks a publication could not measure (#111, #109).

A reading, not a check and not a rule. From the stale tolerance on, every
evening record names the stocks whose frame ended before its session
(``run.input_tolerance``: the names and, from its second version, where each
frame ended), so each night's newest publication names the stock-sessions it
could not measure -- every session a named stock missed, as
``followup.missed_sessions`` counts them. Two later sources read those
stock-sessions again:

- the next evening's follow-up (``run.stale_followup``), which re-reads each
  missed session from that run's own frames and asks the evening's own scans
  whether the late bar would have been listed (``match``); and
- the source-recovery receipt (``docs/source-recovery.json``), which asks the
  provider once more for the publication's own session before the next open.

This reading joins the three per stock and session and counts what the later
readings establish, each class claiming only what its source can: a follow-up
that ran the evening's scans on the late bar and found it listed or not, a late
bar under the $3 session-close policy, a late bar read only for its volume --
against ``scans.MIN_VOLUME``, the floor the 4%, breakdown and $ scans read on
the session itself (the setting-up scans read the three sessions before it, so
volume alone does not settle them) -- and what stays unknown. Why a bar was absent is never established here. It changes no
record, decides nothing and fetches nothing from a provider; the commits it
reads are the ones the committed reading names.

    python tools/stale_inputs.py                       # write the dated reading, origin/main's tip the bound
    python tools/stale_inputs.py --through f714fb32    # ... the history through a named commit
    python tools/stale_inputs.py --check               # the committed files are what the tool writes
"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import followup, scans, source_recovery  # noqa: E402
from tools import service_health as sh  # noqa: E402

VERSION = 1
POLICY = "stale_inputs_v1"
RECORD_PATH = sh.RECORD_PATH
RECOVERY_PATH = sh.COMPANIONS["source_recovery"]
HISTORY_LIMIT = sh.HISTORY_LIMIT
#: the volume floor the 4%, breakdown and $ scans read on the session itself:
#: a late bar under it could not have entered those scans that session. The
#: setting-up scans read the three sessions before (``minv3.1``), so only a
#: follow-up's own reading settles them
FLOOR = scans.MIN_VOLUME
#: a ticker named stale on at least this many nights is listed as recurring
RECURRING_NIGHTS = 3
TRUTH = "docs/input-truthfulness"
OUT_DIR = ROOT / TRUTH / "2026-10-17-stale-inputs-evidence"
OUTPUT_JSON = OUT_DIR / "stale-inputs.json"
OUTPUT_MD = OUT_DIR / "stale-inputs.md"
#: what a stock-session ends as, in the order the summary prints them
#: the first that holds, in this order: a follow-up match anywhere; else the
#: verdict of the last follow-up reading that gave one (``no_match`` after the
#: scans, ``price_excluded`` before them), whatever later readings said; else
#: what a later bar's volume alone says; else a bar that arrived with its
#: volume unread; else nothing arrived
CLASSES = ("would_have_been_listed", "scanned_not_listed", "under_price_policy", "under_volume_floor_unscanned",
           "at_or_above_volume_floor_unscanned", "arrived_volume_unread", "no_later_bar")
#: the follow-up outcomes that are a verdict on the late bar
VERDICTS = ("no_match", "price_excluded")
CLASS_WORDS = {
    "would_have_been_listed": "a follow-up ran the evening's scans on the late bar and it would have been listed",
    "scanned_not_listed": "a follow-up ran the evening's scans on the late bar, every route, and it would not have been listed",
    "under_price_policy": "the late bar's close falls under the $3 session-close policy, which keeps it out of every scan",
    "under_volume_floor_unscanned": "a later bar read for its volume only, under the floor of the 4%, breakdown and $ scans; the setting-up scans not read",
    "at_or_above_volume_floor_unscanned": "a later bar read for its volume only, at or above that floor",
    "arrived_volume_unread": "a later bar arrived but its volume could not be read; no scan verdict",
    "no_later_bar": "no later bar read by either source",
}


class StaleError(sh.ServiceError):
    """The reading could not be made; nothing was printed as if it had."""


# ----------------------------------------------------------- the records ----

def _list(value, where: str) -> list:
    if not isinstance(value, list):
        raise StaleError(f"{where} is not a list")
    return value


def _ticker(value, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise StaleError(f"{where} is not a ticker")
    return value


def _day(value, where: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise StaleError(f"{where} is not a date: {value!r}") from exc


def _volume(value, where: str):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise StaleError(f"{where} is not a volume: {value!r}")
    return value


def publication(data, *, commit: str, sequence: int) -> dict:
    """What one publication says about stale inputs: its session, its own
    named stale stocks and the sessions each missed, and its follow-up rows.
    A record from before the tolerance names nothing (``tolerance`` None)."""
    where = f"{commit[:8]}:{RECORD_PATH}"
    run = sh._real(data, where)["run"]
    session = _day(run.get("session"), where + " run.session")
    tol = run.get("input_tolerance")
    tolerance = None
    if tol is not None:
        if not isinstance(tol, dict):
            raise StaleError(f"{where}: run.input_tolerance is not an object")
        carried = tol.get("names") is not None
        # over the names bound the record names no frame (``names`` and
        # ``endings`` None, as inputs.stale_tolerance writes them): the night
        # still counts, its stale stocks unnamed
        names = [_ticker(t, f"{where} input_tolerance.names[]") for t in _list(tol.get("names"), where + " input_tolerance.names")] \
            if carried else []
        # the benchmark is named beside the stocks and is not one
        benchmark = source_recovery._benchmark(run)
        names = [t for t in names if t != benchmark]
        endings = tol.get("endings")
        if endings is not None and not isinstance(endings, dict):
            raise StaleError(f"{where}: input_tolerance.endings is not an object")
        stale = sh._count(tol.get("stale_stocks"), where, "input_tolerance.stale_stocks")
        bound = tol.get("sessions_max")
        bound = sh._count(bound, where, "input_tolerance.sessions_max") if bound is not None else None
        missed = {}
        for t in names:
            ending = (endings or {}).get(t)
            ending = _day(ending, f"{where} input_tolerance.endings[{t}]") if isinstance(ending, str) else None
            missed[t] = [d.isoformat() for d in followup.missed_sessions(ending, session, bound or 1)]
        tolerance = {"version": tol.get("version"), "verdict": tol.get("verdict"), "stale_stocks": stale, "named": len(names),
                     "names_carried": carried, "endings_recorded": endings is not None, "sessions_max": bound, "missed": missed}
    fu = run.get("stale_followup")
    rows = []
    if fu is not None:
        if not isinstance(fu, dict):
            raise StaleError(f"{where}: run.stale_followup is not an object")
        for i, r in enumerate(_list(fu.get("rows", []), where + " stale_followup.rows")):
            if not isinstance(r, dict) or r.get("outcome") not in followup.OUTCOMES:
                raise StaleError(f"{where}: stale_followup.rows[{i}] has no outcome the follow-up writes")
            rows.append({"ticker": _ticker(r.get("ticker"), f"{where} stale_followup.rows[{i}].ticker"),
                         "session": _day(r.get("session"), f"{where} stale_followup.rows[{i}].session").isoformat(),
                         "outcome": r["outcome"], "volume": _volume(r.get("volume"), f"{where} stale_followup.rows[{i}].volume"),
                         "route": r.get("route")})
    return {"commit": commit, "sequence": sequence, "session": session.isoformat(), "published_at": run.get("published_at"),
            "status": run.get("status"), "tolerance": tolerance,
            "followup": None if fu is None else {"version": fu.get("version"), "status": fu.get("status"), "reason": fu.get("reason"),
                                                 "for_session": fu.get("for_session"), "rows": rows}}


def receipt(data, *, commit: str, sequence: int) -> dict:
    """What one source-recovery receipt read again: its session and each row."""
    where = f"{commit[:8]}:{RECOVERY_PATH}"
    if not isinstance(data, dict) or not isinstance(data.get("frozen"), dict):
        raise StaleError(f"{where}: not a source-recovery receipt")
    session = _day(data["frozen"].get("session"), where + " frozen.session").isoformat()
    rows = []
    for i, r in enumerate(_list(data.get("rows", []), where + " rows")):
        if not isinstance(r, dict) or r.get("outcome") not in source_recovery.OUTCOMES:
            raise StaleError(f"{where}: rows[{i}] has no outcome the receipt writes")
        rows.append({"ticker": _ticker(r.get("ticker"), f"{where} rows[{i}].ticker"), "outcome": r["outcome"],
                     "volume": _volume(r.get("volume"), f"{where} rows[{i}].volume")})
    return {"commit": commit, "sequence": sequence, "session": session, "status": data.get("status"),
            "dry_run": data.get("dry_run"), "rows": rows}


# ---------------------------------------------------------------- joined ----

def stock_sessions(pubs: list[dict]) -> tuple[dict, list[dict]]:
    """Every stock-session a night's newest publication named stale, keyed
    (ticker, session), with the nights that named it; and one row a night."""
    newest, earlier = {}, {}
    for p in sorted(pubs, key=lambda p: p["sequence"]):
        if p["tolerance"] is not None:
            if p["session"] in newest:
                earlier.setdefault(p["session"], set()).update(newest[p["session"]]["tolerance"]["missed"])
            newest[p["session"]] = p
    named: dict[tuple[str, str], dict] = {}
    nights = []
    for session in sorted(newest):
        p = newest[session]
        tol = p["tolerance"]
        pairs = [(t, d) for t, days in tol["missed"].items() for d in days]
        for t, d in pairs:
            named.setdefault((t, d), {"ticker": t, "session": d, "named_by": []})["named_by"].append(session)
        revisions = sum(1 for q in pubs if q["session"] == session)
        nights.append({"session": session, "commit": p["commit"], "revisions": revisions, "status": p["status"],
                       "verdict": tol["verdict"], "tolerance_version": tol["version"], "stale_stocks": tol["stale_stocks"],
                       "named": tol["named"], "unnamed": None if tol["stale_stocks"] is None else tol["stale_stocks"] - tol["named"],
                       "names_carried": tol["names_carried"], "endings_recorded": tol["endings_recorded"], "stock_sessions": len(pairs),
                       # names an earlier publication of the same session called stale
                       # that the newest one, re-run on later bars, measured; unknown
                       # when the newest names no frame
                       "measured_by_revision": len(earlier.get(session, set()) - set(tol["missed"])) if tol["names_carried"] else None})
    return named, nights


def join(pubs: list[dict], receipts: list[dict]) -> tuple[list[dict], list[dict]]:
    """Each named stock-session with every later reading of it, and its class."""
    named, nights = stock_sessions(pubs)
    for p in sorted(pubs, key=lambda p: p["sequence"]):
        for r in (p["followup"] or {}).get("rows", []):
            item = named.get((r["ticker"], r["session"]))
            if item is not None:
                item.setdefault("followup", []).append({"read_by": p["session"], "commit": p["commit"], "outcome": r["outcome"],
                                                         "volume": r["volume"], "route": r["route"]})
    for rc in sorted(receipts, key=lambda r: r["sequence"]):
        if rc["dry_run"] is not False:
            continue
        for r in rc["rows"]:
            item = named.get((r["ticker"], rc["session"]))
            if item is not None:
                item.setdefault("recovery", []).append({"commit": rc["commit"], "outcome": r["outcome"], "volume": r["volume"]})
    rows = []
    for key in sorted(named):
        item = named[key]
        fus, recs = item.get("followup", []), item.get("recovery", [])
        volumes = [x["volume"] for x in fus if x["outcome"] in followup.ARRIVED and x["volume"] is not None] \
            + [x["volume"] for x in recs if x["outcome"] in source_recovery.ARRIVED and x["volume"] is not None]
        arrived = any(x["outcome"] in followup.ARRIVED for x in fus) or any(x["outcome"] in source_recovery.ARRIVED for x in recs)
        final = fus[-1]["outcome"] if fus else None
        verdicts = [x["outcome"] for x in fus if x["outcome"] in VERDICTS]
        verdict = verdicts[-1] if verdicts else None
        if any(x["outcome"] == "match" for x in fus):
            klass = "would_have_been_listed"
        elif verdict == "no_match":
            klass = "scanned_not_listed"
        elif verdict == "price_excluded":
            klass = "under_price_policy"
        elif arrived and volumes and max(volumes) >= FLOOR:
            klass = "at_or_above_volume_floor_unscanned"
        elif arrived and volumes:
            klass = "under_volume_floor_unscanned"
        elif arrived:
            klass = "arrived_volume_unread"
        else:
            klass = "no_later_bar"
        rows.append({**item, "followup": fus, "recovery": recs, "class": klass,
                     "max_volume": max(volumes) if volumes else None, "zero_volume": bool(volumes) and max(volumes) == 0,
                     "followup_final": final, "followup_verdict": verdict})
    # each night's own stock-sessions by class: a stock-session two nights
    # named counts under both
    by_night = {n["session"]: n for n in nights}
    for n in nights:
        n["classes"] = {k: 0 for k in CLASSES}
    for r in rows:
        for night in r["named_by"]:
            by_night[night]["classes"][r["class"]] += 1
    return rows, nights


def _tally(values, keys) -> dict:
    out = {k: 0 for k in keys}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return out


def summary(rows: list[dict], nights: list[dict], pubs: list[dict], receipts: list[dict]) -> dict:
    later = [r for r in rows if r["class"] != "no_later_bar"]
    unread = [r for r in rows if r["class"] == "no_later_bar"]
    nights_named: dict[str, set] = {}
    for r in rows:
        nights_named.setdefault(r["ticker"], set()).update(r["named_by"])
    recurring = sorted(((t, len(n)) for t, n in nights_named.items() if len(n) >= RECURRING_NIGHTS), key=lambda x: (-x[1], x[0]))
    readings = sum(len(r["followup"]) for r in rows)
    return {
        "nights": len(nights), "first_session": nights[0]["session"] if nights else None, "last_session": nights[-1]["session"] if nights else None,
        "publications_read": len(pubs), "publications_naming": sum(1 for p in pubs if p["tolerance"] is not None),
        "stock_sessions": len(rows), "stocks": len({r["ticker"] for r in rows}),
        "unnamed_stale": sum(n["unnamed"] or 0 for n in nights),
        "nights_names_not_carried": sum(1 for n in nights if not n["names_carried"]),
        "measured_by_revision": sum(n["measured_by_revision"] or 0 for n in nights),
        "classes": _tally((r["class"] for r in rows), CLASSES),
        "with_later_bar": len(later), "with_volume_read": sum(1 for r in later if r["max_volume"] is not None),
        "zero_volume": sum(1 for r in later if r["zero_volume"]),
        "max_volume": max((r["max_volume"] for r in later if r["max_volume"] is not None), default=None), "floor": FLOOR,
        "followup": {"readings": readings, "stock_sessions_read": sum(1 for r in rows if r["followup"]),
                     "final_outcomes": _tally((r["followup_final"] for r in rows if r["followup"]), followup.OUTCOMES),
                     "matches": sum(1 for r in rows for x in r["followup"] if x["outcome"] == "match")},
        "recovery": {"receipts": len(receipts), "statuses": _tally((rc["status"] for rc in receipts), source_recovery.STATUSES),
                     "stock_sessions_read": sum(1 for r in rows if r["recovery"]),
                     "outcomes": _tally((x["outcome"] for r in rows for x in r["recovery"]), source_recovery.OUTCOMES)},
        "no_later_bar": {"count": len(unread),
                         "not_read_again": sum(1 for r in unread if not r["followup"] and not r["recovery"]),
                         "followup_final": _tally((r["followup_final"] for r in unread if r["followup"]), followup.OUTCOMES)},
        "recurring": [{"ticker": t, "nights": n} for t, n in recurring],
    }


def sentence(s: dict) -> str:
    """The reading in one paragraph, every number off the summary."""
    if not s["stock_sessions"]:
        return "No retained publication names a stale stock" + (
            f"; {s['unnamed_stale']} were counted but not named, so no stock-session of theirs is read here."
            if s["unnamed_stale"] else ".")
    c = s["classes"]
    parts = [f"{c['scanned_not_listed']} were scanned again by a follow-up on their late bar and would not have been listed",
             f"{c['under_price_policy']} fell under the $3 session-close policy"]
    if c["under_volume_floor_unscanned"]:
        parts.append(f"{c['under_volume_floor_unscanned']} carry a later bar read only for its volume, under the {s['floor']:,}-share floor "
                     "of the 4%, breakdown and $ scans (the setting-up scans not read)")
    if c["at_or_above_volume_floor_unscanned"]:
        parts.append(f"{c['at_or_above_volume_floor_unscanned']} carry a later bar at or above that floor, not yet scanned")
    if c["arrived_volume_unread"]:
        parts.append(f"{c['arrived_volume_unread']} carry a later bar whose volume could not be read")
    parts.append(f"{c['no_later_bar']} have no later bar read by either source")
    match = ("No follow-up reading found a late bar that would have been listed"
             if not c["would_have_been_listed"] else f"{c['would_have_been_listed']} would have been listed, by a follow-up")
    read = ("" if s["with_volume_read"] == s["with_later_bar"]
            else f", {s['with_volume_read']} with a volume read")
    later = (f"Of the {s['with_later_bar']} later bars{read}, {s['zero_volume']} have zero volume and the largest "
             f"{s['max_volume']:,} shares." if s["max_volume"] is not None else
             f"Of the {s['with_later_bar']} later bars, none had a volume read." if s["with_later_bar"] else
             "No named stock-session has a later bar yet.")
    unnamed = (f" {s['unnamed_stale']} more stale stocks were counted but not named, so no stock-session of theirs is read here."
               if s["unnamed_stale"] else "")
    return (f"From {s['first_session']} to {s['last_session']} the newest publication of each of {s['nights']} nights named "
            f"{s['stock_sessions']} stale stock-sessions ({s['stocks']} stocks): " + "; ".join(parts) + ". "
            f"{match} ({s['followup']['readings']} readings). {later}{unnamed} Why a bar was absent is not established.")


# ------------------------------------------------------------------ walk ----

def _read_all(commits: list[str], path: str, make) -> tuple[list[dict], list[dict]]:
    order = sh.sequenced(commits)
    readings, skipped = [], []
    for commit in commits:
        try:
            data, blob = sh.read_at(commit, path)
        except sh.NotJSON as exc:
            skipped.append({"commit": commit, "reason": sh._placed(commit, path, exc)})
            continue
        if blob is None:
            skipped.append({"commit": commit, "reason": f"{commit[:8]}: no {path} at this commit"})
            continue
        try:
            readings.append(make(data, commit=commit, sequence=order[commit]))
        except sh.UNREADABLE as exc:
            skipped.append({"commit": commit, "reason": sh._placed(commit, path, exc)})
    return readings, skipped


def walk(through: str, limit: int) -> tuple[list[str], list[str], list[dict]]:
    pub_commits = sh.file_commits(through, RECORD_PATH, limit)
    rec_commits = sh.file_commits(through, RECOVERY_PATH, limit)
    if not pub_commits:
        raise StaleError(f"no commit at or before {through[:8]} changed {RECORD_PATH}")
    if len(pub_commits) >= limit or len(rec_commits) >= limit:
        raise StaleError(f"the history through {through[:8]} reaches {limit} commits; raise --limit")
    skipped = _read_all(pub_commits, RECORD_PATH, publication)[1] + _read_all(rec_commits, RECOVERY_PATH, receipt)[1]
    return pub_commits, rec_commits, skipped


def assemble(*, ref: str | None, through: str, pub_commits: list[str], rec_commits: list[str], skipped: list[dict], limit: int) -> dict:
    pubs, set_aside = _read_all(pub_commits, RECORD_PATH, publication)
    receipts, set_aside_r = _read_all(rec_commits, RECOVERY_PATH, receipt)
    produced = set_aside + set_aside_r
    unsaid = [row for row in produced if row not in skipped]
    if unsaid:
        raise StaleError("a named commit was set aside and the reading does not say so: " + unsaid[0]["reason"])
    unproduced = [row for row in skipped if row not in produced]
    if unproduced:
        raise StaleError("the reading names a set-aside its commits do not produce: " + str(unproduced[0].get("reason")))
    rows, nights = join(pubs, receipts)
    s = summary(rows, nights, pubs, receipts)
    return {"version": VERSION, "policy": POLICY,
            "source": {"ref": ref, "through": sh.rev_parse(through), "limit": limit, "record_path": RECORD_PATH,
                       "recovery_path": RECOVERY_PATH, "publication_commits": list(pub_commits), "recovery_commits": list(rec_commits)},
            "rules": {"floor": FLOOR, "floor_source": "scans.MIN_VOLUME", "recurring_nights": RECURRING_NIGHTS,
                      "missed_sessions": "followup.missed_sessions over each name's recorded ending, the night's own sessions_max",
                      "classes": dict(CLASS_WORDS)},
            "skipped": list(skipped), "nights": nights, "summary": s, "sentence": sentence(s), "stock_sessions": rows}


def build(*, ref: str = "origin/main", through: str | None = None, limit: int = HISTORY_LIMIT) -> dict:
    if sh.shallow():
        raise StaleError("a shallow clone cannot walk the history; --check reads the committed reading's named commits instead")
    head = sh.rev_parse(through or ref)
    pub_commits, rec_commits, skipped = walk(head, limit)
    return assemble(ref=ref, through=head, pub_commits=pub_commits, rec_commits=rec_commits, skipped=skipped, limit=limit)


def rebuild(committed: dict) -> tuple[dict, str]:
    source = committed.get("source") if isinstance(committed, dict) else None
    if not isinstance(source, dict) or not all(isinstance(source.get(k), list) for k in ("publication_commits", "recovery_commits")) \
            or not isinstance(source.get("through"), str) or not isinstance(source.get("limit"), int) \
            or not isinstance(committed.get("skipped"), list):
        raise StaleError("the committed reading names no commits")
    sh.fetch_missing([source["through"], *source["publication_commits"], *source["recovery_commits"]])
    walked = "not_walked_in_shallow_clone"
    if not sh.shallow():
        pubs, recs, skipped = walk(source["through"], source["limit"])
        if pubs != source["publication_commits"] or recs != source["recovery_commits"] or skipped != committed["skipped"]:
            raise StaleError("the committed reading's commits are not the history's")
        walked = "walked_again"
    return assemble(ref=source.get("ref"), through=source["through"], pub_commits=source["publication_commits"],
                    rec_commits=source["recovery_commits"], skipped=committed["skipped"], limit=source["limit"]), walked


# -------------------------------------------------------------- markdown ----

def markdown(result: dict) -> str:
    s, src = result["summary"], result["source"]
    lines = [f"# Stale inputs read again ({POLICY})", "",
             f"The history of `{src['ref']}` through `{src['through'][:8]}`: {s['publications_read']} publications read, "
             f"{len(src['recovery_commits'])} source-recovery receipts. Derived by `tools/stale_inputs.py`; `--check` holds this file "
             "to the commits named in `stale-inputs.json`.", "", result["sentence"], "",
             "## Night by night", "",
             "| Session | Newest publication | Revisions | Run | Tolerance | Stale | Named | Stock-sessions | Measured by a revision |",
             "|---|---|---:|---|---|---:|---:|---:|---:|"]
    for n in result["nights"]:
        measured = "-" if n["measured_by_revision"] is None else n["measured_by_revision"]
        lines.append(f"| {n['session']} | `{n['commit'][:8]}` | {n['revisions']} | {n['status']} | {n['verdict']} (v{n['tolerance_version']}) | "
                     f"{n['stale_stocks']} | {n['named']} | {n['stock_sessions']} | {measured} |")
    lines += ["", "Each night's stock-sessions by class (one named by two nights counts under both):", "",
              "| Session | " + " | ".join(CLASSES) + " |", "|---|" + "---:|" * len(CLASSES)]
    for n in result["nights"]:
        lines.append(f"| {n['session']} | " + " | ".join(str(n["classes"][k]) for k in CLASSES) + " |")
    c = s["classes"]
    lines += ["", "## Every named stock-session, by what the later readings establish", ""]
    lines += [f"- {CLASS_WORDS[k]}: {c[k]}" for k in CLASSES]
    lines += ["", f"Later bars: {s['with_later_bar']} ({s['with_volume_read']} with a volume read), {s['zero_volume']} at zero volume, the largest "
              f"{format(s['max_volume'], ',') if s['max_volume'] is not None else '-'} shares, against the {s['floor']:,}-share floor "
              "of the 4%, breakdown and $ scans (`scans.MIN_VOLUME`, read on the session itself).", "",
              f"Follow-up: {s['followup']['readings']} readings of {s['followup']['stock_sessions_read']} stock-sessions; the last reading of each: "
              + ", ".join(f"{k} {v}" for k, v in s["followup"]["final_outcomes"].items() if v) + f"; matches {s['followup']['matches']}.", "",
              f"Source recovery: {s['recovery']['receipts']} receipts ("
              + ", ".join(f"{k} {v}" for k, v in s["recovery"]["statuses"].items() if v) + f"), {s['recovery']['stock_sessions_read']} stock-sessions read: "
              + ", ".join(f"{k} {v}" for k, v in s["recovery"]["outcomes"].items() if v) + ".", "",
              f"No later bar: {s['no_later_bar']['count']}, {s['no_later_bar']['not_read_again']} not yet read again"
              + ("; the follow-up's last word on the rest: " + ", ".join(f"{k} {v}" for k, v in s["no_later_bar"]["followup_final"].items() if v)
                 if any(s["no_later_bar"]["followup_final"].values()) else "") + ".", ""]
    if s["recurring"]:
        lines += [f"Named on {RECURRING_NIGHTS} or more nights: " + ", ".join(f"{r['ticker']} ({r['nights']})" for r in s["recurring"]) + ".", ""]
    if result["skipped"]:
        reasons: dict[str, int] = {}
        for r in result["skipped"]:
            reason = r["reason"].split(": ", 1)[-1] if r["reason"].startswith(r["commit"][:8]) else r["reason"]
            reasons[reason] = reasons.get(reason, 0) + 1
        lines += ["Set aside, each by name in `stale-inputs.json`: " + "; ".join(f"{n} commits, {why}" for why, n in sorted(reasons.items())) + ".", ""]
    return "\n".join(lines)


def write(result: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / OUTPUT_JSON.name).write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    (out_dir / OUTPUT_MD.name).write_text(markdown(result))


def check(out_dir: Path) -> list[str]:
    path = out_dir / OUTPUT_JSON.name
    try:
        committed = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        return [f"{path.name}: {exc}"]
    result, _ = rebuild(committed)
    drift = []
    if json.dumps(result, indent=1, sort_keys=True) + "\n" != path.read_text():
        drift.append(f"{OUTPUT_JSON.name} is not what the tool writes from its named commits")
    md = out_dir / OUTPUT_MD.name
    if not md.exists() or md.read_text() != markdown(result):
        drift.append(f"{OUTPUT_MD.name} is not what the tool writes")
    return drift


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ref", default="origin/main")
    ap.add_argument("--through")
    ap.add_argument("--limit", type=int, default=HISTORY_LIMIT)
    ap.add_argument("--output-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    try:
        if args.check:
            drift = check(args.output_dir)
            for line in drift:
                print(line, file=sys.stderr)
            return 1 if drift else 0
        result = build(ref=args.ref, through=args.through, limit=args.limit)
    except sh.ServiceError as exc:
        print(f"stale inputs: {exc}", file=sys.stderr)
        return 2
    write(result, args.output_dir)
    print(result["sentence"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
