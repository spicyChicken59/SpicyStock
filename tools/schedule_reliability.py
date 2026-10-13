"""Read when GitHub started each scheduled run against the slot it was for (#111).

A reading, not a check and not a rule. The service-health reading measures
when each publication landed; it cannot say why one landed hours after its
slot, because a record does not know when its runner started. The Actions API
does: a scheduled run is created when GitHub's scheduler fires it, so its
``created_at`` against the cron instant it was for is the scheduler's own
delay, before any code of ours has run. This reads that, per workflow and per
week, and names every expected slot that produced no run.

    python tools/schedule_reliability.py --fetch    # snapshot the public API into the dated folder, then write the reading
    python tools/schedule_reliability.py            # write the reading from the committed snapshot
    python tools/schedule_reliability.py --check    # the committed reading is what the snapshot gives

``--fetch`` is the only path that touches a network, and only the public
Actions API (``GET /repos/{repo}/actions/runs?event=schedule``, paged; a
``GITHUB_TOKEN`` in the environment is sent when present, for the rate limit,
never needed). The snapshot keeps the fields the reading uses and nothing
else, beside each scheduled workflow's cron tables as ``main`` carried them,
version by version, read from git at fetch time with the commit that made each
take effect. Everything after is derived from the snapshot alone, so ``--check``
needs no network and no history.

A run's slot is the cron its own run name records (the evening, morning and
source-recovery workflows write ``... cron <expression>``), at the latest
instant that cron names at or before the run was created; that assumes a delay
shorter than the cron's own period, a day for the daily ones. A run whose name
records no cron takes the latest instant any cron named, at or before its
creation, by the table in force at that instant -- the assignment ``expected()``
makes -- and says so; that assumes a delay shorter than the gap to the table's
next instant, an hour for some tables. A run placed at a slot another run has
too is listed under ``shared``, so a misplacement shows. An expected slot is
every instant a cron in force named, from the workflow's first table to the
snapshot; one with no run is ``no_run`` once a day has passed without one, and
``not_started`` before that. Every threshold compares the delay in seconds; the
minutes are rounded once, for display.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent

VERSION = 1
POLICY = "schedule_reliability_v1"
REPOSITORY = "spicyChicken59/SpicyStock"
API = "https://api.github.com"
PER_PAGE = 100
#: the most pages a fetch reads; a history longer than this is a refusal, never a truncation
MAX_PAGES = 20
#: the most runs GitHub lists for a filtered listing (``event=``, ``branch=``); past it the
#: listing must be split by ``created=`` windows, which this version does not do, so it refuses
API_RESULT_CAP = 1000
FETCH_TIMEOUT_SECONDS = 30
OUT_DIR = ROOT / "docs/input-truthfulness/2026-10-13-schedule-reliability-evidence"
SNAPSHOT = OUT_DIR / "runs.json"
OUTPUT_JSON = OUT_DIR / "schedule-reliability.json"
OUTPUT_MD = OUT_DIR / "schedule-reliability.md"
#: the run fields the reading keeps; the API's other fields are not copied
RUN_FIELDS = ("id", "path", "event", "display_title", "created_at", "status", "conclusion",
              "head_sha", "head_branch", "run_attempt")
#: the contrast listing: runs a push to ``main`` triggered, created against the pushed commit's own timestamp
PUSH_FIELDS = ("id", "path", "created_at", "head_sha", "committed_at")
#: an expected slot with no run this long after it is ``no_run``; a younger one has ``not_started`` yet
UNSEEN_AFTER_HOURS = 24
#: the delays the reading counts runs beyond, in minutes; 360 is a GitHub-hosted job's own time limit
DELAY_MARKS = (15, 60, 240, 360)
#: a run created within this many minutes of its slot is prompt; the change the reading names is the first run
#: created later than ``LATE_MINUTES`` after its slot, and the last prompt run before it
PROMPT_MINUTES = 15
LATE_MINUTES = 60
#: a run name's cron: the five fields after the word ``cron``, however spaced (``github.event.schedule``
#: is the cron as the file spells it); older names add ``, the EDT slot`` after it
NAME_WORD = re.compile(r"\bcron\b")
NAME_CRON = re.compile(r"\bcron\s+(\S+\s+\S+\s+\S+\s+\S+\s+\S+)")
FILE_CRON = re.compile(r'^\s*-\s*cron:\s*["\']([^"\']+)["\']', re.M)


class ScheduleError(Exception):
    """A snapshot or a cron the reading cannot place: the reading refuses it whole."""


# ------------------------------------------------------------------ crons ----

def parse_cron(text: str) -> dict:
    """``minute hour * * day-of-week`` in UTC, the only shape these workflows use;
    anything else is a refusal rather than a guess at its instants."""
    if not isinstance(text, str):
        raise ScheduleError(f"not a cron: {text!r}")
    fields = text.split()
    if len(fields) != 5:
        raise ScheduleError(f"not a five-field cron: {text!r}")
    minute, hour, dom, month, dow = fields
    if dom != "*" or month != "*":
        raise ScheduleError(f"a day-of-month or month field the reading does not place: {text!r}")
    try:
        m, h = int(minute), int(hour)
    except ValueError as exc:
        raise ScheduleError(f"a minute or hour the reading does not place: {text!r}") from exc
    if not (0 <= m <= 59 and 0 <= h <= 23):
        raise ScheduleError(f"out of range: {text!r}")
    return {"text": " ".join(fields), "minute": m, "hour": h, "days": _days(dow, text)}


def _days(field: str, text: str) -> list[int] | None:
    """Cron days of week (0 = Sunday; 7 is Sunday too), or None for every day."""
    if field == "*":
        return None
    out: set[int] = set()
    for part in field.split(","):
        bounds = part.split("-")
        try:
            lo, hi = (int(bounds[0]), int(bounds[-1])) if len(bounds) in (1, 2) else (None, None)
        except ValueError as exc:
            raise ScheduleError(f"a day of week the reading does not place: {text!r}") from exc
        if lo is None or not (0 <= lo <= hi <= 7):
            raise ScheduleError(f"a day of week the reading does not place: {text!r}")
        out.update(d % 7 for d in range(lo, hi + 1))
    return sorted(out)


def _cron_day(instant: datetime) -> int:
    return (instant.weekday() + 1) % 7      # Python: Monday 0; cron: Sunday 0


def latest_at_or_before(cron: dict, instant: datetime) -> datetime:
    """The latest instant the cron names at or before ``instant`` (UTC)."""
    at = instant.astimezone(timezone.utc).replace(hour=cron["hour"], minute=cron["minute"], second=0, microsecond=0)
    if at > instant:
        at -= timedelta(days=1)
    for _ in range(8):
        if cron["days"] is None or _cron_day(at) in cron["days"]:
            return at
        at -= timedelta(days=1)
    raise ScheduleError(f"{cron['text']} names no day")


def firings(cron: dict, start: datetime, end: datetime) -> list[datetime]:
    """Every instant the cron names in ``[start, end)``, in order."""
    out = []
    at = start.astimezone(timezone.utc).replace(hour=cron["hour"], minute=cron["minute"], second=0, microsecond=0)
    if at < start:
        at += timedelta(days=1)
    while at < end:
        if cron["days"] is None or _cron_day(at) in cron["days"]:
            out.append(at)
        at += timedelta(days=1)
    return out


# ------------------------------------------------------------------ time ----

def parse_instant(value) -> datetime:
    if not isinstance(value, str):
        raise ScheduleError(f"not an instant: {value!r}")
    try:
        at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ScheduleError(f"not an instant: {value!r}") from exc
    if at.tzinfo is None:
        raise ScheduleError(f"instant without an offset: {value!r}")
    return at.astimezone(timezone.utc)


def iso(at: datetime) -> str:
    return at.astimezone(timezone.utc).isoformat()


def seconds(later: datetime, earlier: datetime) -> float:
    return (later - earlier).total_seconds()


def minutes(later: datetime, earlier: datetime) -> float:
    """For display: rounded once; every threshold reads :func:`seconds`."""
    return round(seconds(later, earlier) / 60, 1)


# ------------------------------------------------------------- snapshot ----

def _git(*args: str) -> str:
    done = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if done.returncode != 0:
        raise ScheduleError("git could not produce " + " ".join(args) + ": " + done.stderr.strip())
    return done.stdout


def table_versions(path: str, ref: str) -> list[dict]:
    """The workflow's cron tables as ``ref``'s first-parent history carried them,
    oldest first, one entry per change of the table: the commit that made it take
    effect, when that commit landed, and its crons (none once a version has no
    schedule, or the file is gone)."""
    out: list[dict] = []
    for line in _git("log", "--first-parent", "--reverse", "--format=%H %cI", ref, "--", path).split("\n"):
        if not line.strip():
            continue
        commit, landed = line.split()
        done = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT, capture_output=True, text=True)
        crons = [" ".join(c.split()) for c in FILE_CRON.findall(done.stdout)] if done.returncode == 0 else []
        if not out or out[-1]["crons"] != crons:
            out.append({"commit": commit, "effective_at": iso(parse_instant(landed)), "crons": crons})
    return out


def scheduled_at(commit: str) -> set[str]:
    """The workflow files that carry a schedule at ``commit``: a workflow whose
    cron has never produced a run is still read, so its slots are named."""
    out = set()
    for path in _git("ls-tree", "--name-only", commit, ".github/workflows/").split("\n"):
        if path.endswith((".yml", ".yaml")) and FILE_CRON.search(_git("show", f"{commit}:{path}")):
            out.add(path)
    return out


def _get(url: str) -> dict:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "spicystock-schedule-reliability",
               "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=FETCH_TIMEOUT_SECONDS) as response:
            if response.status != 200:
                raise ScheduleError(f"{url}: HTTP {response.status}")
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise ScheduleError(f"{url}: HTTP {exc.code}") from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise ScheduleError(f"{url}: {exc}") from exc


def _listing(get, repository: str, query: str, keep) -> tuple[list[dict], int]:
    """Every run one Actions listing names, paged until the count it gave is read;
    a listing that does not add up is a refusal, never a truncation."""
    runs: list[dict] = []
    total = None
    for page in range(1, MAX_PAGES + 1):
        body = get(f"{API}/repos/{repository}/actions/runs?{query}&per_page={PER_PAGE}&page={page}")
        if not isinstance(body, dict) or not isinstance(body.get("workflow_runs"), list) or not isinstance(body.get("total_count"), int):
            raise ScheduleError(f"{query} page {page}: not a workflow-runs page")
        total = body["total_count"] if total is None else total
        if total > API_RESULT_CAP:
            raise ScheduleError(f"{query}: the API counted {total} runs and lists at most {API_RESULT_CAP} of a "
                                "filtered listing; split it by created= windows")
        runs += [keep(r) for r in body["workflow_runs"]]
        if len(runs) >= total or not body["workflow_runs"]:
            break
    else:
        raise ScheduleError(f"{query}: more than {MAX_PAGES} pages; raise MAX_PAGES")
    if len(runs) != total:
        raise ScheduleError(f"{query}: the API counted {total} runs and listed {len(runs)}")
    return sorted(runs, key=lambda r: (r["created_at"], r["id"])), total


def _push(run: dict) -> dict:
    commit = run.get("head_commit") if isinstance(run.get("head_commit"), dict) else {}
    return {"id": run.get("id"), "path": run.get("path"), "created_at": run.get("created_at"),
            "head_sha": run.get("head_sha"), "committed_at": commit.get("timestamp")}


def fetch(*, repository: str = REPOSITORY, ref: str = "origin/main", get=_get, now=None) -> dict:
    """Every scheduled run the public API lists, its kept fields only, beside each
    scheduled workflow's table versions as ``ref`` carried them, and every run a
    push to ``main`` triggered, for the contrast."""
    fetched_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)
    runs, total = _listing(get, repository, "event=schedule", lambda r: {k: r.get(k) for k in RUN_FIELDS})
    pushes, push_total = _listing(get, repository, "event=push&branch=main", _push)
    head = _git("rev-parse", "--verify", f"{ref}^{{commit}}").strip()
    history = set(_git("rev-list", head).split())
    outside = sorted({r.get("head_sha") for r in runs + pushes} - history, key=str)
    if outside:
        raise ScheduleError(f"{len(outside)} commits the runs ran on are not in {ref}'s history "
                            f"(first {str(outside[0])[:12]}); fetch it, or name a ref that carries them")
    paths = sorted({r["path"] for r in runs if isinstance(r.get("path"), str)} | scheduled_at(head))
    snapshot = {"version": VERSION, "repository": repository, "fetched_at": iso(fetched_at),
                "source": f"GET {API}/repos/{repository}/actions/runs?event=schedule and ?event=push&branch=main "
                          f"(public API, paged by {PER_PAGE})",
                "ref": ref, "ref_commit": head, "total_count": total, "push_total_count": push_total,
                "tables": {p: table_versions(p, head) for p in paths},
                "runs": runs, "push_runs": pushes}
    validate(snapshot)
    return snapshot


def validate(snapshot) -> None:
    """The snapshot is what the reading indexes into, whole, or it is refused."""
    if not isinstance(snapshot, dict) or snapshot.get("version") != VERSION:
        raise ScheduleError("not a schedule snapshot of this version")
    for key in ("repository", "fetched_at", "source", "ref", "ref_commit"):
        if not isinstance(snapshot.get(key), str) or not snapshot[key]:
            raise ScheduleError(f"snapshot.{key} is missing")
    fetched = parse_instant(snapshot["fetched_at"])
    runs, tables = snapshot.get("runs"), snapshot.get("tables")
    if not isinstance(runs, list) or not isinstance(tables, dict) or snapshot.get("total_count") != len(runs):
        raise ScheduleError("snapshot.runs is not the whole listing")
    seen = set()
    for run in runs:
        if not isinstance(run, dict) or set(run) != set(RUN_FIELDS):
            raise ScheduleError(f"a run without exactly the kept fields: {run!r}"[:200])
        if not isinstance(run["id"], int) or isinstance(run["id"], bool) or run["id"] in seen:
            raise ScheduleError(f"a run id that is not a unique integer: {run['id']!r}")
        seen.add(run["id"])
        if run["event"] != "schedule" or not isinstance(run["path"], str) or run["path"] not in tables:
            raise ScheduleError(f"run {run['id']}: not a scheduled run of a workflow the snapshot has a table for")
        if not isinstance(run["display_title"], str):
            raise ScheduleError(f"run {run['id']}: no run name")
        if parse_instant(run["created_at"]) > fetched:
            raise ScheduleError(f"run {run['id']}: created after the snapshot")
    pushes = snapshot.get("push_runs")
    if not isinstance(pushes, list) or snapshot.get("push_total_count") != len(pushes):
        raise ScheduleError("snapshot.push_runs is not the whole listing")
    for run in pushes:
        if not isinstance(run, dict) or set(run) != set(PUSH_FIELDS):
            raise ScheduleError(f"a push run without exactly the kept fields: {run!r}"[:200])
        if not isinstance(run["id"], int) or isinstance(run["id"], bool) or run["id"] in seen:
            raise ScheduleError(f"a run id that is not a unique integer: {run['id']!r}")
        seen.add(run["id"])
        if not isinstance(run["path"], str) or not isinstance(run["head_sha"], str):
            raise ScheduleError(f"push run {run['id']}: no workflow or commit")
        if parse_instant(run["created_at"]) > fetched:
            raise ScheduleError(f"push run {run['id']}: created after the snapshot")
        parse_instant(run["committed_at"])
    for path, versions in tables.items():
        if not isinstance(versions, list) or not versions:
            raise ScheduleError(f"{path}: no table versions")
        last = None
        for v in versions:
            if not isinstance(v, dict) or set(v) != {"commit", "effective_at", "crons"} or not isinstance(v["crons"], list):
                raise ScheduleError(f"{path}: a table version the reading cannot place")
            at = parse_instant(v["effective_at"])
            if last is not None and at < last:
                raise ScheduleError(f"{path}: table versions out of order")
            last = at
            for c in v["crons"]:
                parse_cron(c)


def digest(snapshot: dict) -> str:
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


# --------------------------------------------------------------- reading ----

def name_cron(title: str) -> dict | None:
    """The cron a run name records, or None for a name without the word ``cron``;
    a name that has the word and no cron the reading can place is a refusal."""
    if not NAME_WORD.search(title):
        return None
    named = NAME_CRON.search(title)
    if not named:
        raise ScheduleError(f"a run name that says cron and names none: {title!r}")
    fields = named.group(1).split()
    fields[-1] = fields[-1].rstrip(",")
    return parse_cron(" ".join(fields))


def nearest_slot(versions: list[dict], created: datetime) -> tuple[dict, datetime]:
    """The latest instant any cron named at or before ``created``, each cron read
    only while its table was in force -- the slots ``expected()`` names."""
    best = None
    for n, v in enumerate(versions):
        start = parse_instant(v["effective_at"])
        if start > created:
            break
        until = parse_instant(versions[n + 1]["effective_at"]) if n + 1 < len(versions) else None
        bound = created if until is None or until > created else until - timedelta(microseconds=1)
        for text in v["crons"]:
            cron = parse_cron(text)
            at = latest_at_or_before(cron, bound)
            if at >= start and (best is None or at > best[1]):
                best = (cron, at)
    if best is None:
        raise ScheduleError(f"no cron of any table in force named an instant at or before {iso(created)}")
    return best


def attribute(run: dict, versions: list[dict]) -> dict:
    """The slot a run was for: its run name's cron when recorded, else the nearest
    preceding instant any table in force named."""
    created = parse_instant(run["created_at"])
    cron = name_cron(run["display_title"])
    if cron is not None:
        slot, basis = latest_at_or_before(cron, created), "run_name"
    else:
        try:
            cron, slot = nearest_slot(versions, created)
        except ScheduleError as exc:
            raise ScheduleError(f"run {run['id']}: no cron in its name and {exc}") from exc
        basis = "nearest_slot"
    return {"id": run["id"], "cron": cron["text"], "slot": iso(slot), "basis": basis,
            "created_at": iso(created), "delay_seconds": seconds(created, slot), "delay_minutes": minutes(created, slot),
            "conclusion": run["conclusion"], "status": run["status"], "head_sha": run["head_sha"], "attempt": run["run_attempt"]}


def expected(versions: list[dict], start: datetime, end: datetime) -> list[tuple[str, datetime]]:
    """Every (cron, instant) a table in force named in ``[start, end)``."""
    out = []
    for n, v in enumerate(versions):
        lo = max(parse_instant(v["effective_at"]), start)
        hi = min(parse_instant(versions[n + 1]["effective_at"]), end) if n + 1 < len(versions) else end
        for text in v["crons"]:
            out += [(" ".join(text.split()), at) for at in firings(parse_cron(text), lo, hi)]
    return sorted(out, key=lambda pair: (pair[1], pair[0]))


def _spread(secs: list[float]) -> dict | None:
    """Min / median / max of delays given in seconds, each rounded once to a tenth of a minute."""
    if not secs:
        return None
    return {"n": len(secs), "min": round(min(secs) / 60, 1), "median": round(statistics.median(secs) / 60, 1),
            "max": round(max(secs) / 60, 1)}


def _week(at: datetime) -> str:
    return str((at - timedelta(days=at.weekday())).date())       # the Monday of the slot's UTC week


def workflow_reading(path: str, runs: list[dict], versions: list[dict], fetched: datetime) -> dict:
    """One workflow's runs against every slot its tables named from the first
    table on -- a cron that never fired is named, not skipped."""
    mine = sorted((attribute(r, versions) for r in runs if r["path"] == path), key=lambda a: (a["slot"], a["created_at"], a["id"]))
    due = expected(versions, parse_instant(versions[0]["effective_at"]), fetched)
    started = {(a["cron"], a["slot"]) for a in mine}
    no_run, not_started = [], []
    for text, at in due:
        if (text, iso(at)) in started:
            continue
        (no_run if fetched - at >= timedelta(hours=UNSEEN_AFTER_HOURS) else not_started).append({"cron": text, "slot": iso(at)})
    expected_keys = {(t, iso(a)) for t, a in due}
    weeks: dict[str, list[float]] = {}
    by_cron: dict[str, list[float]] = {}
    by_slot: dict[tuple, list[int]] = {}
    for a in mine:
        weeks.setdefault(_week(parse_instant(a["slot"])), []).append(a["delay_seconds"])
        by_cron.setdefault(a["cron"], []).append(a["delay_seconds"])
        by_slot.setdefault((a["slot"], a["cron"]), []).append(a["id"])
    delays = [a["delay_seconds"] for a in mine]
    return {
        "path": path, "runs": mine, "expected": len(due),
        "no_run": no_run, "not_started": not_started,
        "unexpected": [{"id": a["id"], "cron": a["cron"], "slot": a["slot"]} for a in mine if (a["cron"], a["slot"]) not in expected_keys],
        "shared": [{"cron": c, "slot": s, "ids": ids} for (s, c), ids in sorted(by_slot.items()) if len(ids) > 1],
        "delay_minutes": _spread(delays),
        "beyond": {str(m): sum(1 for d in delays if d > m * 60) for m in DELAY_MARKS},
        "weeks": [{"week": w, **_spread(v)} for w, v in sorted(weeks.items())],
        "by_cron": {c: _spread(v) for c, v in sorted(by_cron.items())},
    }


def change(workflows: dict) -> dict | None:
    """Across every workflow, in slot order: the first run created more than
    ``LATE_MINUTES`` after its slot, the last prompt run before it, and every run
    from that slot on -- a measurement of when the scheduler's delay changed,
    never an attribution of why."""
    runs = sorted(({"path": p, **a} for p, w in workflows.items() for a in w["runs"]),
                  key=lambda a: (a["slot"], a["created_at"], a["id"]))
    first = next((a for a in runs if a["delay_seconds"] > LATE_MINUTES * 60), None)
    if first is None:
        return None
    before = [a for a in runs if a["slot"] < first["slot"] and a["delay_seconds"] <= PROMPT_MINUTES * 60]
    since = [a["delay_seconds"] for a in runs if a["slot"] >= first["slot"]]
    pick = lambda a: None if a is None else {k: a[k] for k in ("path", "cron", "slot", "created_at", "delay_minutes")}
    return {"first_late": pick(first), "last_prompt_before": pick(before[-1] if before else None),
            "since": {"delay_minutes": _spread(since), "prompt": sum(1 for d in since if d <= PROMPT_MINUTES * 60),
                      "beyond": {str(m): sum(1 for d in since if d > m * 60) for m in DELAY_MARKS}}}


def contrast(pushes: list[dict], since: str | None) -> dict:
    """Minutes from each pushed commit's own timestamp to the run its push to
    ``main`` triggered: an upper bound on that event's delay (a commit made before
    it was pushed counts the gap), over every push run and over those from the
    change on."""
    def gap(r):
        return seconds(parse_instant(r["created_at"]), parse_instant(r["committed_at"]))
    after = [gap(r) for r in pushes if since is not None and parse_instant(r["created_at"]) >= parse_instant(since)]
    return {"event": "push", "branch": "main", "all": _spread([gap(r) for r in pushes]),
            "since_change": _spread(after) if since is not None else None,
            "within_prompt_since_change": None if since is None else sum(1 for d in after if d <= PROMPT_MINUTES * 60)}


def build(snapshot: dict) -> dict:
    validate(snapshot)
    fetched = parse_instant(snapshot["fetched_at"])
    tables = snapshot["tables"]
    workflows = {p: workflow_reading(p, snapshot["runs"], tables[p], fetched) for p in sorted(tables)}
    moved = change(workflows)
    return {
        "version": VERSION, "policy": POLICY,
        "snapshot": {"file": SNAPSHOT.name, "sha256": digest(snapshot), "fetched_at": snapshot["fetched_at"],
                     "repository": snapshot["repository"], "ref_commit": snapshot["ref_commit"], "runs": len(snapshot["runs"]),
                     "push_runs": len(snapshot["push_runs"])},
        "rules": {"unseen_after_hours": UNSEEN_AFTER_HOURS, "delay_marks_minutes": list(DELAY_MARKS),
                  "prompt_minutes": PROMPT_MINUTES, "late_minutes": LATE_MINUTES,
                  "attribution": "the run name's cron at its latest instant at or before the run was created (a delay "
                                 "shorter than the cron's period assumed), else the latest instant any cron named at or "
                                 "before it while its table was in force (a delay shorter than the gap to the table's next "
                                 "instant assumed); runs sharing a slot are listed"},
        "change": moved,
        "contrast": contrast(snapshot["push_runs"], None if moved is None else moved["first_late"]["slot"]),
        "workflows": workflows,
    }


# -------------------------------------------------------------- markdown ----

def _hm(value: str) -> str:
    return value[:16].replace("T", " ") + "Z"


def _s(spread: dict | None) -> str:
    return "—" if spread is None else f"{spread['min']} / {spread['median']} / {spread['max']} ({spread['n']})"


def markdown(result: dict) -> str:
    s = result["snapshot"]
    lines = [f"# Schedule reliability reading ({POLICY})", "",
             f"{s['runs']} scheduled runs of `{s['repository']}` as the public Actions API listed them at {_hm(s['fetched_at'])} "
             f"(snapshot `{SNAPSHOT.name}`, SHA-256 `{s['sha256'][:16]}…`), with each workflow's cron tables as `main` carried "
             f"them at `{s['ref_commit'][:8]}`. A delay is the minutes from the cron instant a run was for to the moment GitHub "
             "created it -- the scheduler's own, before any step of ours ran. Delays are min / median / max (runs).", ""]
    c = result["change"]
    if c is not None:
        f, b, n = c["first_late"], c["last_prompt_before"], c["since"]
        lines += ["## The change", "",
                  f"- last run created within {PROMPT_MINUTES} minutes of its slot before it: " +
                  ("none" if b is None else f"`{b['path']}` `{b['cron']}` at {_hm(b['slot'])}, {b['delay_minutes']} min"),
                  f"- first run created more than {LATE_MINUTES} minutes after its slot: `{f['path']}` `{f['cron']}` "
                  f"at {_hm(f['slot'])}, {f['delay_minutes']} min",
                  f"- every run from that slot on: delay {_s(n['delay_minutes'])}; within {PROMPT_MINUTES} min {n['prompt']}; beyond " +
                  ", ".join(f"{m} min {n['beyond'][str(m)]}" for m in DELAY_MARKS), ""]
    k = result["contrast"]
    lines += [f"## The contrast: runs a push to `main` triggered ({s['push_runs']})", "",
              "Minutes from the pushed commit's own timestamp to the run it triggered, an upper bound on that event's "
              "delay (a commit made before its push counts the gap).", "",
              f"- every push run: {_s(k['all'])}"]
    if k["since_change"] is not None:
        lines.append(f"- from the change on: {_s(k['since_change'])}; within {PROMPT_MINUTES} min {k['within_prompt_since_change']}")
    lines.append("")
    for path, w in result["workflows"].items():
        lines += [f"## {path}", "",
                  f"- runs {len(w['runs'])}; expected slots {w['expected']}; with no run {len(w['no_run'])}; "
                  f"not started yet {len(w['not_started'])}; runs for a slot no table named {len(w['unexpected'])}; "
                  f"slots placed with more than one run {len(w['shared'])}",
                  f"- delay, minutes: {_s(w['delay_minutes'])}; beyond " +
                  ", ".join(f"{m} min {w['beyond'][str(m)]}" for m in DELAY_MARKS), ""]
        if w["by_cron"]:
            lines += ["| cron (UTC) | delay min / median / max (runs) |", "|---|---|"]
            lines += [f"| `{c}` | {_s(v)} |" for c, v in w["by_cron"].items()]
            lines += ["", "| week of (Monday, UTC) | delay min / median / max (runs) |", "|---|---|"]
            lines += [f"| {wk['week']} | {wk['min']} / {wk['median']} / {wk['max']} ({wk['n']}) |" for wk in w["weeks"]]
            lines.append("")
        for label, rows in (("Expected slots with no run", w["no_run"]), ("Expected slots not started at the snapshot", w["not_started"])):
            if rows:
                lines += [f"{label}: " + ", ".join(f"`{r['cron']}` at {_hm(r['slot'])}" for r in rows), ""]
    return "\n".join(lines).rstrip("\n") + "\n"


# ------------------------------------------------------------------ main ----

def _dump(value) -> str:
    return json.dumps(value, indent=1, sort_keys=True) + "\n"


def write(snapshot: dict, result: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / SNAPSHOT.name).write_text(_dump(snapshot), encoding="utf-8")
    (out_dir / OUTPUT_JSON.name).write_text(_dump(result), encoding="utf-8")
    (out_dir / OUTPUT_MD.name).write_text(markdown(result), encoding="utf-8")


def load(out_dir: Path) -> dict:
    try:
        return json.loads((out_dir / SNAPSHOT.name).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ScheduleError(f"{SNAPSHOT.name}: {exc}") from exc


def check(out_dir: Path) -> list[str]:
    """The committed reading is what the committed snapshot gives."""
    result = build(load(out_dir))
    problems = []
    for name, expected_text in ((OUTPUT_JSON.name, _dump(result)), (OUTPUT_MD.name, markdown(result))):
        try:
            current = (out_dir / name).read_text(encoding="utf-8")
        except OSError as exc:
            problems.append(f"{name}: {exc}")
            continue
        if current != expected_text:
            problems.append(f"{name} is not what the tool writes from {SNAPSHOT.name}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--fetch", action="store_true", help="snapshot the public Actions API first (the only network path)")
    parser.add_argument("--ref", default="origin/main", help="the ref whose history gives the cron tables, at fetch")
    parser.add_argument("--output-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--check", action="store_true", help="hold the committed reading to the committed snapshot")
    args = parser.parse_args(argv)
    try:
        if args.check:
            problems = check(args.output_dir)
            for p in problems:
                print(f"stale: {p}")
            if not problems:
                print(f"current: {OUTPUT_JSON.name} and {OUTPUT_MD.name} are what {SNAPSHOT.name} gives")
            return 1 if problems else 0
        snapshot = fetch(ref=args.ref) if args.fetch else load(args.output_dir)
        result = build(snapshot)
    except ScheduleError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    write(snapshot, result, args.output_dir)
    for path, w in result["workflows"].items():
        print(f"{path}: {len(w['runs'])} runs, delay {_s(w['delay_minutes'])} min, no run {len(w['no_run'])}, not started {len(w['not_started'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
