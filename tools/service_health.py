"""Read the service -- not the signal -- off the retained publications (#111).

A reading, not a check and not a rule: it walks the commits that put a
publication on ``main`` and the commits that put a morning, issuer or
research receipt beside it, and prints what the records and their commit
times establish about delivery -- which expected XNYS session each one is
for, when it landed against the session's completion and the evening cron's
nominal slot, whether it landed before the next open, how often a session was
published twice, what the inputs covered, what the chart reader did and what
it cost -- with the signal (the regime and the tickets) kept in its own
column, because zero tickets can be a successful research run and stale data
cannot be called fresh. It changes no record, decides nothing and fetches
nothing from any provider; what it fetches is a commit this checkout lacks,
exactly the ones the committed reading names, so a shallow clone can hold
``--check``.

    python tools/service_health.py                       # write the dated reading, origin/main's tip the clock
    python tools/service_health.py --through 43dcb8d7    # ... the history through a named commit, its time the clock
    python tools/service_health.py --check               # the committed files are what the tool writes

The expected sessions are the exchange's own (``src/sessions.py``), from the
first retained publication's session through the newest one's; a session the
reading's clock has not reached is not yet due, one whose next open has passed
without a publication is missing. A publication made under older rules is read
for what it recorded: a block it lacks is ``None``, never guessed.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta, timezone
import json
from pathlib import Path
import statistics
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import delivery, funnel, sessions  # noqa: E402

VERSION = 1
POLICY = "service_health_v1"
RECORD_PATH = "docs/data.json"
#: the companion receipts whose commits are read beside the publications
COMPANIONS = {"morning": "docs/morning.json",
              "issuer_evidence": "docs/issuer-evidence.json",
              "research_observations": "docs/research-observations.json",
              "source_recovery": "docs/source-recovery.json"}
HISTORY_LIMIT = 128
#: the evening cron's nominal instants in the exchange's zone: ``16 22 * * 1-5`` on EDT
#: and ``16 23`` on EST are one wall-clock time, 6:16 PM ET; the retry pair is 8:16 PM
# the one slot rule: the record archives it (src/delivery.py) and this reading reads it
EVENING_PRIMARY = delivery.EVENING_PRIMARY_ET
EVENING_RETRY = delivery.EVENING_RETRY_ET
#: the morning workflow's two best-effort attempts, in the desk's zone
MORNING_SLOTS = ("08:20", "08:28")
DESK_TZ = ZoneInfo("America/Chicago")
TRUTH = "docs/input-truthfulness"
OUT_DIR = ROOT / TRUTH / "2026-10-12-service-health-evidence"
OUTPUT_JSON = OUT_DIR / "service-health.json"
OUTPUT_MD = OUT_DIR / "service-health.md"
#: the fields a companion receipt is read for, by kind; a field a receipt lacks is None
COMPANION_FIELDS = {
    "morning": ("status", "reason", "entry_phase", "generated_at", "collection_started_at", "observation_run_id", "dry_run"),
    "issuer_evidence": ("status", "generated_at", "collection_started_at", "collection_run_id", "dry_run"),
    "research_observations": ("status", "reason", "generated_at", "collection_started_at", "requests", "dry_run"),
    "source_recovery": ("status", "reason", "generated_at", "collection_started_at", "observation_run_id", "dry_run"),
}
COMPANION_RUN_ID = {"morning": "observation_run_id", "issuer_evidence": "collection_run_id", "research_observations": "observation_run_id",
                    "source_recovery": "observation_run_id"}
#: the words the service columns use; the signal column is the record's regime and its tickets
SERVICE_WORDS = {
    "published": "a real publication for this session reached main",
    "before_next_open": "its first publication landed before the next session's open",
    "fresh": "the newest publication is for the newest due session",
    "due": "the session's close plus the completion buffer is at or before the reading's clock",
    "overdue": "due, unpublished, and the next session has already opened",
}


class ServiceError(RuntimeError):
    """The reading could not be made; nothing was printed as if it had."""


# ------------------------------------------------------------------- git ----

def _git(*args: str, check: bool = True) -> bytes:
    done = subprocess.run(["git", *args], cwd=ROOT, capture_output=True)
    if check and done.returncode != 0:
        raise ServiceError("git could not produce " + " ".join(args) + ": " + done.stderr.decode(errors="replace").strip())
    return done.stdout


def rev_parse(commit: str) -> str:
    return _git("rev-parse", "--verify", f"{commit}^{{commit}}").decode().strip()


def committed_at(full: str) -> str:
    """The commit's committer instant, in UTC: when the record landed on the branch."""
    return parse_instant(_git("show", "-s", "--format=%cI", full).decode().strip()).isoformat()


def file_commits(through: str, path: str, limit: int) -> list[str]:
    """The commits at or before ``through`` that changed ``path``, newest first, bounded."""
    if limit < 1:
        raise ServiceError("limit must be at least 1")
    return _git("log", "--format=%H", f"--max-count={limit}", through, "--", path).decode().split()


def present(commit: str) -> bool:
    return subprocess.run(["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=ROOT, capture_output=True).returncode == 0


def fetch_missing(commits: list[str]) -> list[str]:
    """Fetch exactly the named commits this checkout lacks (a shallow clone's),
    once, and fail with the reason when they cannot be had; never skip."""
    missing = [c for c in commits if not present(c)]
    if missing:
        done = subprocess.run(["git", "fetch", "--quiet", "--no-tags", "--depth=1", "origin", *missing],
                              cwd=ROOT, capture_output=True, text=True)
        still = [c for c in missing if not present(c)]
        if done.returncode != 0 or still:
            raise ServiceError(f"{len(still or missing)} named commits are not in this checkout and could not be fetched: {done.stderr.strip()}")
    return missing


def read_at(commit: str, path: str) -> tuple[dict | list | None, str | None]:
    """The JSON a commit carries at ``path`` and its blob identity; (None, None) when absent."""
    done = subprocess.run(["git", "rev-parse", f"{commit}:{path}"], cwd=ROOT, capture_output=True)
    if done.returncode != 0:
        return None, None
    blob = done.stdout.decode().strip()
    raw = _git("cat-file", "-p", f"{commit}:{path}")
    try:
        return json.loads(raw), blob
    except ValueError as exc:
        raise ServiceError(f"{commit[:8]}:{path} is not JSON: {exc}") from exc


def shallow() -> bool:
    return _git("rev-parse", "--is-shallow-repository").decode().strip() == "true"


# ------------------------------------------------------------------ time ----

def parse_instant(value) -> datetime:
    """An offset-aware instant, read as UTC; anything else is a refusal."""
    if not isinstance(value, str):
        raise ServiceError(f"not an instant: {value!r}")
    try:
        at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ServiceError(f"not an instant: {value!r}") from exc
    if at.tzinfo is None or at.utcoffset() is None:
        raise ServiceError(f"instant without an offset: {value!r}")
    return at.astimezone(timezone.utc)


def minutes_between(later: datetime, earlier: datetime) -> float:
    return round((later - earlier).total_seconds() / 60, 1)


def slots(session: date) -> dict:
    """The evening cron's nominal instants for a session: the primary pair's
    6:16 PM and the retry pair's 8:16 PM in the exchange's zone, so the DST
    change is the tz database's answer and no UTC hour is written here."""
    primary, retry = delivery.slots(session, EVENING_PRIMARY, EVENING_RETRY)
    return {"primary_at": primary.astimezone(timezone.utc).isoformat(), "retry_at": retry.astimezone(timezone.utc).isoformat()}


def frame(session: date) -> dict:
    """The exchange's own facts about a session and the one after it."""
    opens, closes, shortened = sessions.hours(session)
    following = sessions.next_sessions(session, 1)[0]
    morning = [datetime.combine(following, time.fromisoformat(s), tzinfo=DESK_TZ).astimezone(timezone.utc).isoformat() for s in MORNING_SLOTS]
    return {"session": str(session), "opens_at": opens.astimezone(timezone.utc).isoformat(),
            "closes_at": closes.astimezone(timezone.utc).isoformat(),
            "completion_at": sessions.completion_at(session).astimezone(timezone.utc).isoformat(), "shortened": shortened,
            "next_session": str(following), "next_open_at": sessions.hours(following)[0].astimezone(timezone.utc).isoformat(),
            "next_morning_slots_at": morning, **slots(session)}


# ---------------------------------------------------------- publications ----

def _real(data, where: str) -> dict:
    if (not isinstance(data, dict) or data.get("fixture") or data.get("schema_version") != 2
            or not isinstance(data.get("run"), dict) or not isinstance(data.get("app"), dict)):
        raise ServiceError(f"{where}: not a real schema-2 publication")
    return data


def _dict(value) -> dict | None:
    return value if isinstance(value, dict) else None


def publication_reading(data, *, commit: str, blob: str, landed_at: str) -> dict:
    """One publication's service facts, read off the record and its commit alone."""
    where = f"{commit[:8]}:{RECORD_PATH}"
    data = _real(data, where)
    run = data["run"]
    try:
        session = date.fromisoformat(run["session"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ServiceError(f"{where}: run.session is not a date") from exc
    try:
        sessions.require_session(session)
    except ValueError as exc:
        raise ServiceError(f"{where}: {exc}") from exc
    published = parse_instant(run.get("published_at"))
    landed = parse_instant(landed_at)
    fr = frame(session)
    completion = parse_instant(fr["completion_at"])
    archived = _dict((_dict(run.get("calendar")) or {}).get("measured")) or {}
    if archived.get("completion_at") is not None and parse_instant(archived["completion_at"]) != completion:
        raise ServiceError(f"{where}: the archived completion {archived['completion_at']} is not the calendar's {fr['completion_at']}")
    archived_delivery = _dict(run.get("delivery"))
    if archived_delivery is not None:
        rules = _dict((_dict(data.get("rules")) or {}).get("pipeline")) or {}
        if delivery.faults(run, rules):
            raise ServiceError(f"{where}: run.delivery does not re-derive from the archived slots: {delivery.faults(run, rules)[0]}")
        if parse_instant(archived_delivery["published_at"]) != published:
            raise ServiceError(f"{where}: run.delivery names another publication instant")
    coverage = _dict(run.get("coverage"))
    acceptance = _dict((coverage or {}).get("acceptance"))
    tolerance = _dict(run.get("input_tolerance"))
    reads = _dict(run.get("reads"))
    usage = _dict(run.get("reader_usage"))
    tokens = _dict((usage or {}).get("tokens")) or {}
    block = funnel.build(data)
    problems = [p.get("kind") for p in (run.get("problems") or []) if isinstance(p, dict)]
    return {
        "commit": commit, "blob": blob, "landed_at": landed.isoformat(),
        "session": str(session), "session_state": run.get("session_state"), "status": run.get("status"),
        "problems": problems, "published_at": published.isoformat(), "run_id": run.get("run_id"),
        "dry_run": run.get("dry_run"), "email": run.get("email"), "rules_version": data["app"].get("rules_version"),
        "elapsed_seconds": run.get("elapsed_seconds"), "fetch_seconds": run.get("fetch_seconds"),
        "timing": {
            "completion_at": fr["completion_at"], "completion_basis": "archived" if archived else "re-derived",
            "delivery_basis": "archived" if archived_delivery is not None else "re-derived",
            "latency_minutes": minutes_between(published, completion),
            "primary_slot_at": fr["primary_at"], "after_primary_minutes": minutes_between(published, parse_instant(fr["primary_at"])),
            "retry_slot_at": fr["retry_at"], "after_retry_slot": published >= parse_instant(fr["retry_at"]),
            "next_open_at": fr["next_open_at"], "before_next_open": published < parse_instant(fr["next_open_at"]),
            "landed_minutes": minutes_between(landed, published),
        },
        "inputs": {
            "version": (coverage or {}).get("version"),
            "intended_stocks": (acceptance or {}).get("intended_stocks"), "ready_stocks": (acceptance or {}).get("ready_stocks"),
            "ready_fraction": (acceptance or {}).get("fraction"), "acceptance": (acceptance or {}).get("status"),
            "stale": (coverage or {}).get("stale"), "tolerance": (tolerance or {}).get("verdict"),
        },
        "reader": {
            "requested": (reads or {}).get("requested"), "done": (reads or {}).get("done"), "verdict": (reads or {}).get("verdict"),
            "usage": None if usage is None else {
                "model": usage.get("model"), "calls": usage.get("calls"), "responses": usage.get("responses"),
                "input_tokens": usage.get("input_tokens"), "output_tokens": tokens.get("output"),
            },
        },
        "signal": {
            "regime": block["regime"], "discovered": block["reaction"]["discovered"], "listed": block["anticipation"]["listed"],
            "reaction_tickets": block["reaction"]["stages"]["ticket"], "anticipation_tickets": block["anticipation"]["stages"]["ticket"],
        },
    }


def companion_reading(kind: str, data, *, commit: str, blob: str, landed_at: str) -> dict:
    """One companion receipt's facts: which publication and applicable session it
    binds, when it was generated, what it says of itself; nothing re-derived."""
    where = f"{commit[:8]}:{COMPANIONS[kind]}"
    if not isinstance(data, dict) or not isinstance(data.get("publication"), dict):
        raise ServiceError(f"{where}: not a bound receipt")
    binding = data["publication"]
    generated = parse_instant(data.get("generated_at"))
    applicable = binding.get("applicable_session")
    try:
        applicable_day = date.fromisoformat(applicable)
        sessions.require_session(applicable_day)
    except (TypeError, ValueError) as exc:
        raise ServiceError(f"{where}: publication.applicable_session is not an exchange session") from exc
    opens = sessions.hours(applicable_day)[0].astimezone(timezone.utc)
    rows = data.get("rows")
    out = {"kind": kind, "commit": commit, "blob": blob, "landed_at": parse_instant(landed_at).isoformat(),
           "bound_run_id": binding.get("run_id"), "measured_session": binding.get("measured_session"),
           "applicable_session": applicable, "applicable_open_at": opens.isoformat(),
           "generated_at": generated.isoformat(), "before_applicable_open": generated < opens,
           "rows": len(rows) if isinstance(rows, list) else None}
    for field in COMPANION_FIELDS[kind]:
        if field != "generated_at":
            out[field] = data.get(field)
    if kind == "source_recovery":
        # the recovery's own two counts, copied: what it asked for and what now carries the session's bar
        tally = data.get("recovered") if isinstance(data.get("recovered"), dict) else {}
        source = data.get("source") if isinstance(data.get("source"), dict) else {}
        out["session_ready"] = tally.get("session_ready")
        out["batch_attempts"] = source.get("batch_attempts")
    return out


# -------------------------------------------------------------- sessions ----

def session_rows(pubs: list[dict], companions: dict[str, list[dict]], clock: datetime) -> list[dict]:
    """One row per expected XNYS session from the first publication's to the
    newest one's, or to the newest session the clock has reached: its
    publications in the order they were published, the first one's delivery
    facts as the service column, its signal beside them, and the companion
    receipts bound to the session its plans are for (the next one)."""
    if not pubs:
        raise ServiceError("no publication to read")
    first = min(date.fromisoformat(p["session"]) for p in pubs)
    # through the newest published session or the newest session the clock has
    # reached, whichever is later, so a night the run missed is a row and not a gap
    market_day = sessions.market_time(clock).date()
    reached = market_day if sessions.is_session(market_day) else sessions.previous_session(market_day)
    last = max(max(date.fromisoformat(p["session"]) for p in pubs), reached)
    by_session: dict[str, list[dict]] = {}
    for p in sorted(pubs, key=lambda p: (p["session"], p["published_at"], p["commit"])):
        by_session.setdefault(p["session"], []).append(p)
    rows = []
    for day in sessions.dates(first, last):
        fr = frame(day)
        mine = by_session.get(str(day), [])
        due = parse_instant(fr["completion_at"]) <= clock
        overdue = due and not mine and parse_instant(fr["next_open_at"]) <= clock
        head = mine[0] if mine else None
        rows.append({
            "session": str(day), "shortened": fr["shortened"], "completion_at": fr["completion_at"], "next_open_at": fr["next_open_at"],
            "due": due, "published": bool(mine), "overdue": overdue, "pending": due and not mine and not overdue,
            "publications": [p["commit"] for p in mine], "revisions": len(mine),
            "service": None if head is None else {
                "status": head["status"], "problems": head["problems"], "published_at": head["published_at"], "run_id": head["run_id"],
                "latency_minutes": head["timing"]["latency_minutes"], "after_primary_minutes": head["timing"]["after_primary_minutes"],
                "after_retry_slot": head["timing"]["after_retry_slot"], "before_next_open": head["timing"]["before_next_open"],
                "inputs": head["inputs"], "reader": head["reader"], "elapsed_seconds": head["elapsed_seconds"],
            },
            "signal": None if head is None else head["signal"],
            "latest": None if head is None else {"commit": mine[-1]["commit"], "status": mine[-1]["status"], "email": mine[-1]["email"],
                                                  "published_at": mine[-1]["published_at"], "signal": mine[-1]["signal"]},
            "applicable_session": fr["next_session"],
            "receipts": {kind: [{"commit": i["commit"], "status": i["status"], "reason": i.get("reason"),
                                 "generated_at": i["generated_at"], "before_applicable_open": i["before_applicable_open"], "rows": i["rows"]}
                                for i in items if i["applicable_session"] == fr["next_session"]]
                         for kind, items in companions.items()},
        })
    return rows


def _streaks(rows: list[dict]) -> dict:
    """Consecutive due sessions whose first publication landed before the next
    open: the longest run and the run ending at the newest due session."""
    longest = current = 0
    for row in rows:
        if not row["due"]:
            continue
        ok = row["published"] and row["service"]["before_next_open"]
        current = current + 1 if ok else 0
        longest = max(longest, current)
    return {"longest": longest, "current": current}


def summary(rows: list[dict], pubs: list[dict], companions: dict[str, list[dict]], clock: datetime) -> dict:
    due = [r for r in rows if r["due"]]
    published = [r for r in due if r["published"]]
    firsts = [r["service"] for r in published]
    latencies = [s["latency_minutes"] for s in firsts]
    statuses: dict[str, int] = {}
    for p in pubs:
        statuses[str(p["status"])] = statuses.get(str(p["status"]), 0) + 1
    usage_pubs = [p for p in pubs if p["reader"]["usage"] is not None]
    newest_due = due[-1]["session"] if due else None
    newest_published = max((p["session"] for p in pubs), default=None)
    def total(key):
        values = [p[key] for p in pubs if isinstance(p[key], (int, float))]
        return round(sum(values), 1) if values else None
    return {
        "clock": clock.isoformat(),
        "expected_sessions": len(rows), "due_sessions": len(due), "published_sessions": len(published),
        "missing_sessions": [r["session"] for r in due if r["overdue"]],
        "pending_sessions": [r["session"] for r in due if r["pending"]],
        "not_yet_due": [r["session"] for r in rows if not r["due"]],
        "before_next_open": sum(1 for s in firsts if s["before_next_open"]),
        "after_retry_slot": sum(1 for s in firsts if s["after_retry_slot"]),
        "latency_minutes": None if not latencies else {"min": min(latencies), "median": round(statistics.median(latencies), 1), "max": max(latencies)},
        "streak": _streaks(rows),
        "publications": len(pubs), "revisions": sum(max(0, r["revisions"] - 1) for r in rows),
        "republished_sessions": [r["session"] for r in rows if r["revisions"] > 1],
        "statuses": statuses, "elapsed_seconds": total("elapsed_seconds"), "fetch_seconds": total("fetch_seconds"),
        "reads": {"requested": sum(p["reader"]["requested"] or 0 for p in pubs if p["reader"]["requested"] is not None),
                  "done": sum(p["reader"]["done"] or 0 for p in pubs if p["reader"]["done"] is not None),
                  "publications_with_block": sum(1 for p in pubs if p["reader"]["requested"] is not None)},
        "reader_usage": {"publications_with_block": len(usage_pubs),
                         "calls": sum(p["reader"]["usage"]["calls"] or 0 for p in usage_pubs),
                         "responses": sum(p["reader"]["usage"]["responses"] or 0 for p in usage_pubs),
                         "input_tokens": sum(p["reader"]["usage"]["input_tokens"] or 0 for p in usage_pubs),
                         "output_tokens": sum(p["reader"]["usage"]["output_tokens"] or 0 for p in usage_pubs)},
        "signal": {"regimes": _tally(p["signal"]["regime"] for p in pubs),
                   "reaction_tickets": sum(p["signal"]["reaction_tickets"] for p in pubs),
                   "anticipation_tickets": sum(p["signal"]["anticipation_tickets"] for p in pubs)},
        "fresh": {"newest_due_session": newest_due, "newest_published_session": newest_published,
                  "fresh": newest_due is not None and newest_due == newest_published},
        "companions": {kind: {"receipts": len(items), "statuses": _tally(i["status"] for i in items),
                              "before_applicable_open": sum(1 for i in items if i["before_applicable_open"]),
                              "applicable_sessions": sorted({i["applicable_session"] for i in items})}
                       for kind, items in companions.items()},
    }


def _tally(values) -> dict:
    out: dict[str, int] = {}
    for v in values:
        out[str(v)] = out.get(str(v), 0) + 1
    return dict(sorted(out.items()))


# ----------------------------------------------------------------- build ----

#: what a reading of one commit may fail with; the commit is then set aside by name, never guessed at
UNREADABLE = (ServiceError, KeyError, TypeError, ValueError, AttributeError)


def _placed(commit: str, path: str, exc: BaseException) -> str:
    """The reason a commit was set aside, led by the commit and the path it was read at."""
    text = str(exc)
    return text if text.startswith(commit[:8]) else f"{commit[:8]}:{path}: {text}"


def read_publications(commits: list[str]) -> tuple[list[dict], list[dict]]:
    """Every named commit's record as a reading, or named under ``skipped`` with
    the reason (the first build's records and the fixtures a ref's history
    carries; a commit that removed the file; a record the reading cannot place)."""
    readings, skipped = [], []
    for commit in commits:
        data, blob = read_at(commit, RECORD_PATH)
        if blob is None:
            skipped.append({"commit": commit, "reason": f"{commit[:8]}: no {RECORD_PATH} at this commit"})
            continue
        try:
            readings.append(publication_reading(data, commit=commit, blob=blob, landed_at=committed_at(commit)))
        except UNREADABLE as exc:
            skipped.append({"commit": commit, "reason": _placed(commit, RECORD_PATH, exc)})
    return readings, skipped


def read_companions(by_kind: dict[str, list[str]]) -> tuple[dict[str, list[dict]], list[dict]]:
    """Every named companion commit's receipt as a reading, by kind, and the
    commits set aside with the reason (the file removed, a receipt unreadable)."""
    out: dict[str, list[dict]] = {}
    skipped = []
    for kind, path in COMPANIONS.items():
        items = []
        for commit in by_kind.get(kind, []):
            data, blob = read_at(commit, path)
            if blob is None:
                skipped.append({"commit": commit, "reason": f"{commit[:8]}: no {path} at this commit"})
                continue
            try:
                items.append(companion_reading(kind, data, commit=commit, blob=blob, landed_at=committed_at(commit)))
            except UNREADABLE as exc:
                skipped.append({"commit": commit, "reason": _placed(commit, path, exc)})
        out[kind] = sorted(items, key=lambda i: (i["generated_at"], i["commit"]))
    return out, skipped


def assemble(*, ref: str | None, through: str, publication_commits: list[str], skipped: list[dict],
             companion_commits: dict[str, list[str]], limit: int) -> dict:
    through_full = rev_parse(through)
    clock = parse_instant(committed_at(through_full))
    pubs, refused = read_publications(publication_commits)
    if refused:
        raise ServiceError("a named publication commit does not carry a real publication: " + refused[0]["reason"])
    pubs.sort(key=lambda p: (p["session"], p["published_at"], p["commit"]))
    companions, set_aside = read_companions(companion_commits)
    if any(row not in skipped for row in set_aside):
        raise ServiceError("a named companion commit was set aside and the reading does not say so: " + set_aside[0]["reason"])
    rows = session_rows(pubs, companions, clock)
    return {
        "version": VERSION, "policy": POLICY,
        "source": {"ref": ref, "through": through_full, "clock": clock.isoformat(), "limit": limit,
                   "record_path": RECORD_PATH, "companion_paths": dict(COMPANIONS),
                   "publication_commits": list(publication_commits), "companion_commits": {k: list(v) for k, v in companion_commits.items()}},
        "slots": {"evening_primary_et": EVENING_PRIMARY.isoformat(timespec="minutes"), "evening_retry_et": EVENING_RETRY.isoformat(timespec="minutes"),
                  "morning_chicago": list(MORNING_SLOTS), "completion_buffer_minutes": sessions.COMPLETION_BUFFER_MINUTES,
                  "basis": "the workflows' cron tables read in the exchange's and the desk's zones; a session's instants are the pinned XNYS calendar's"},
        "words": dict(SERVICE_WORDS),
        "publications": pubs, "skipped": list(skipped), "sessions": rows, "companions": companions,
        "summary": summary(rows, pubs, companions, clock),
    }


def walk(through: str, limit: int) -> tuple[list[str], list[dict], dict[str, list[str]]]:
    """The history through a commit: the publication commits that carry a real
    record, the ones set aside with their reasons, and each companion's commits."""
    commits = file_commits(through, RECORD_PATH, limit)
    if not commits:
        raise ServiceError(f"no commit at or before {through[:8]} changed {RECORD_PATH}")
    if len(commits) >= limit:
        raise ServiceError(f"the history through {through[:8]} has at least {limit} publication commits; raise --limit")
    pubs, skipped = read_publications(commits)
    companions = {kind: file_commits(through, path, limit) for kind, path in COMPANIONS.items()}
    skipped += read_companions(companions)[1]
    return [p["commit"] for p in pubs], skipped, companions


def build(*, ref: str = "origin/main", through: str | None = None, limit: int = HISTORY_LIMIT) -> dict:
    """Walk the ref's history through its tip (or the commit named), whose time
    is the reading's clock; refused on a shallow clone, whose walk is not the history."""
    if shallow():
        raise ServiceError("a shallow clone cannot walk the history; --check reads the committed reading's named commits instead")
    head = rev_parse(through or ref)
    publications, skipped, companions = walk(head, limit)
    return assemble(ref=ref, through=head, publication_commits=publications, skipped=skipped, companion_commits=companions, limit=limit)


def rebuild(committed: dict) -> tuple[dict, str]:
    """The reading again from the commits the committed one names, fetching the
    ones this checkout lacks; on a full clone the walk is repeated and must give
    the same commits, read and set aside alike. Returns the reading and a word
    for what the walk could establish here."""
    source = committed.get("source") if isinstance(committed, dict) else None
    if not isinstance(source, dict) or not isinstance(source.get("publication_commits"), list) \
            or not isinstance(source.get("companion_commits"), dict) or not isinstance(source.get("through"), str) \
            or not isinstance(source.get("limit"), int) or not isinstance(committed.get("skipped"), list):
        raise ServiceError("the committed reading names no commits")
    named = [source["through"], *source["publication_commits"], *(c for v in source["companion_commits"].values() for c in v)]
    fetch_missing(named)
    skipped = committed["skipped"]
    walked = "not_walked_in_shallow_clone"
    if not shallow():
        publications, skipped, companions = walk(source["through"], source["limit"])
        if publications != source["publication_commits"] or companions != {k: source["companion_commits"].get(k, []) for k in COMPANIONS} \
                or skipped != committed["skipped"]:
            raise ServiceError("the committed reading's commits are not the history's")
        walked = "walked_again"
    return assemble(ref=source.get("ref"), through=source["through"], publication_commits=source["publication_commits"], skipped=skipped,
                    companion_commits={k: source["companion_commits"].get(k, []) for k in COMPANIONS}, limit=source["limit"]), walked


# -------------------------------------------------------------- markdown ----

def _hm(iso: str) -> str:
    return iso[:16].replace("T", " ") + "Z" if iso else "—"


def _yn(value) -> str:
    return "yes" if value is True else "no" if value is False else "—"


def markdown(result: dict) -> str:
    s = result["summary"]
    lines = [f"# Service health reading ({POLICY})", "",
             f"Read from `{result['source']['ref']}` through commit `{result['source']['through'][:8]}` "
             f"(clock {_hm(result['source']['clock'])}), {len(result['publications'])} publications and "
             f"{len(result['skipped'])} commits set aside. "
             "The service columns say whether and when a publication landed; the signal column is the record's own "
             "regime and ticket count and is never a service verdict.", "",
             "## Expected sessions", "",
             "| session | due | published | revisions | status | published at (UTC) | latency after completion (min) | after primary slot (min) | after retry slot | before next open | inputs ready | reads done/requested | regime | tickets (reaction/anticipation) |",
             "|---|---|---|---:|---|---|---:|---:|---|---|---|---|---|---|"]
    for r in result["sessions"]:
        sv, sg = r["service"], r["signal"]
        if sv is None:
            state = "not yet due" if not r["due"] else ("missing" if r["overdue"] else "pending")
            lines.append(f"| {r['session']} | {_yn(r['due'])} | no ({state}) | 0 | — | — | — | — | — | — | — | — | — | — |")
            continue
        ready = "—" if sv["inputs"]["ready_stocks"] is None else f"{sv['inputs']['ready_stocks']}/{sv['inputs']['intended_stocks']}"
        reads = "—" if sv["reader"]["requested"] is None else f"{sv['reader']['done']}/{sv['reader']['requested']}"
        lines.append(f"| {r['session']} | yes | yes | {r['revisions']} | {sv['status']} | {_hm(sv['published_at'])} | {sv['latency_minutes']} | "
                     f"{sv['after_primary_minutes']} | {_yn(sv['after_retry_slot'])} | {_yn(sv['before_next_open'])} | {ready} | {reads} | "
                     f"{sg['regime']} | {sg['reaction_tickets']}/{sg['anticipation_tickets']} |")
    lat = s["latency_minutes"] or {}
    lines += ["", "## Summary", "",
              f"- expected sessions {s['expected_sessions']}, due {s['due_sessions']}, published {s['published_sessions']}, "
              f"missing {len(s['missing_sessions'])} ({', '.join(s['missing_sessions']) or 'none'}), pending {len(s['pending_sessions'])}, "
              f"not yet due {len(s['not_yet_due'])}",
              f"- first publications before the next open: {s['before_next_open']} of {s['published_sessions']}; after the retry slot: {s['after_retry_slot']}",
              f"- latency after completion, minutes: min {lat.get('min')}, median {lat.get('median')}, max {lat.get('max')}",
              f"- streak of due sessions published before the next open: current {s['streak']['current']}, longest {s['streak']['longest']}",
              f"- publications {s['publications']}, re-published sessions {len(s['republished_sessions'])} ({', '.join(s['republished_sessions']) or 'none'}), "
              f"statuses {json.dumps(s['statuses'], sort_keys=True)}",
              f"- runner time archived: elapsed {s['elapsed_seconds']} s, fetch {s['fetch_seconds']} s over {s['publications']} publications",
              f"- reader: {s['reads']['done']} of {s['reads']['requested']} reads done over {s['reads']['publications_with_block']} publications with a reads block; "
              f"cost blocks archived: {s['reader_usage']['publications_with_block']} ({s['reader_usage']['calls']} calls, "
              f"{s['reader_usage']['responses']} replies, {s['reader_usage']['input_tokens']:,} input and {s['reader_usage']['output_tokens']:,} output tokens)",
              f"- signal, kept apart: regimes {json.dumps(s['signal']['regimes'], sort_keys=True)}, reaction tickets {s['signal']['reaction_tickets']}, "
              f"anticipation tickets {s['signal']['anticipation_tickets']}",
              f"- fresh: newest due session {s['fresh']['newest_due_session']}, newest published {s['fresh']['newest_published_session']}: {_yn(s['fresh']['fresh'])}",
              "", "## Companion receipts", "",
              "| kind | landed (UTC) | generated (UTC) | status | reason | applicable session | before its open | rows | bound run |",
              "|---|---|---|---|---|---|---|---:|---|"]
    for kind, items in result["companions"].items():
        if not items:
            lines.append(f"| {kind} | — | — | none retained | — | — | — | — | — |")
        for i in items:
            lines.append(f"| {kind} | {_hm(i['landed_at'])} | {_hm(i['generated_at'])} | {i['status']} | {i.get('reason') or '—'} | "
                         f"{i['applicable_session']} | {_yn(i['before_applicable_open'])} | {'—' if i['rows'] is None else i['rows']} | {i['bound_run_id'] or '—'} |")
    if result["skipped"]:
        reasons = _tally(row["reason"].split(": ", 1)[-1] for row in result["skipped"])   # the reason without its commit prefix
        lines += ["", "## Commits read and set aside", ""]
        lines += [f"- {n} × {reason}" for reason, n in reasons.items()]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ main ----

def write(result: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / OUTPUT_JSON.name).write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / OUTPUT_MD.name).write_text(markdown(result), encoding="utf-8")


def check(out_dir: Path) -> list[str]:
    """The committed files are what the tool writes from the commits they name."""
    problems = []
    try:
        committed = json.loads((out_dir / OUTPUT_JSON.name).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"{OUTPUT_JSON.name}: {exc}"]
    result, walked = rebuild(committed)
    print(f"history: {walked}")
    expected_json = json.dumps(result, indent=1, sort_keys=True) + "\n"
    if (out_dir / OUTPUT_JSON.name).read_text(encoding="utf-8") != expected_json:
        problems.append(f"{OUTPUT_JSON.name} is not what the tool writes from its named commits")
    try:
        current_md = (out_dir / OUTPUT_MD.name).read_text(encoding="utf-8")
    except OSError as exc:
        return problems + [f"{OUTPUT_MD.name}: {exc}"]
    if current_md != markdown(result):
        problems.append(f"{OUTPUT_MD.name} is not what the tool writes")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--ref", default="origin/main")
    parser.add_argument("--through", help="read the history through this commit (default: the newest publication commit on --ref)")
    parser.add_argument("--limit", type=int, default=HISTORY_LIMIT)
    parser.add_argument("--output-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--check", action="store_true", help="hold the committed files to the tool")
    args = parser.parse_args(argv)
    try:
        if args.check:
            problems = check(args.output_dir)
            for p in problems:
                print(f"stale: {p}")
            if not problems:
                print(f"current: {OUTPUT_JSON.name} and {OUTPUT_MD.name} are what the tool writes")
            return 1 if problems else 0
        result = build(ref=args.ref, through=args.through, limit=args.limit)
    except ServiceError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    write(result, args.output_dir)
    s = result["summary"]
    print(f"{s['published_sessions']} of {s['due_sessions']} due sessions published ({s['expected_sessions']} expected through "
          f"{result['source']['through'][:8]}); {s['before_next_open']} before the next open; latency median {(s['latency_minutes'] or {}).get('median')} min; "
          f"streak current {s['streak']['current']} / longest {s['streak']['longest']}; re-published sessions {len(s['republished_sessions'])}; "
          f"tickets {s['signal']['reaction_tickets']}/{s['signal']['anticipation_tickets']} (signal, not service).")
    for row in result["skipped"]:
        print(f"skipped {row['commit'][:8]}: {row['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
