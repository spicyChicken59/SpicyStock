#!/usr/bin/env python3
"""On-time starts for the workflows GitHub's scheduler starts hours late.

GitHub created every scheduled evening run of 2 to 18 November 2026 3.56 to
7.99 hours after its slot, and every scheduled morning run after its entry
window had closed (CLAUDE.md, the 19 November checkpoint). A
``workflow_dispatch`` is created when it is asked for. This tool asks for
one at each slot below, on XNYS sessions (``src/sessions.py``, the one
calendar the run itself reads), and does nothing else:

* ``evening.yml`` at 18:20, 19:20, 20:20 and 21:20 America/New_York, with
  ``only_if_unpublished`` ticked, so the four starts publish the newest
  completed session once and the later three do nothing when the first did
  (the workflow's own guard). These four are started on EVERY calendar day
  (``EVERY_DAY``): on a weekend or a holiday the guard publishes the newest
  completed session only if it is still unpublished and its next session
  has not opened, and refuses otherwise, so they are a missed Friday's (or
  an eve's) recovery before the next open and a no-op after a published one;
* ``morning.yml`` at 08:20 America/Chicago, ``dry_run`` false, inside the
  collector's own window (it opens 30 minutes before the 8:30 open);
* ``service-watch.yml`` at 19:00 and 21:50 America/New_York and at 06:00,
  08:25 and 09:05 America/Chicago: after the evening's first start is due,
  after its last, before the open, five minutes after the morning check
  (``tools/service_watch.MORNING_ALERT_CT``) and after the entry window.

GitHub's own crons stay in each workflow as the backup; every workflow's
guard already makes a second start harmless.

It holds one credential, ``GITHUB_TOKEN``: a fine-grained token with
Actions read and write on this repository and nothing else. It writes no
file but its optional ``--state`` ledger, mails nothing, and logs only the
workflow, the slot, the run id GitHub gives the dispatch and an HTTP status;
never a token, a header or a response body.

Idempotent: a slot is due from its instant for ``DUE_MINUTES``, and before
it asks for a run it reads the workflow's runs created since the slot by a
dispatch (``event=workflow_dispatch``). One there -- this tool's on an earlier
tick, or anyone's -- means the slot is done; with ``--state`` the ledger says
so without asking GitHub again. A repeat tick, a restart and a second copy
of the scheduler therefore start a slot's run at most once each, barring two
copies asking in the same second.

    python tools/dispatch_schedule.py plan --day 2026-11-20    # the day's slots, no network
    python tools/dispatch_schedule.py tick [--now ISO] [--state FILE]
    python tools/dispatch_schedule.py loop [--state FILE]      # a tick every minute (Railway)

Exit codes: 0 every due slot was started or was already started (or none
was due); 1 a dispatch or a listing failed (named by its status); 2 the
configuration is refused (no token, a clock without an offset).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time as clock
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import sessions  # noqa: E402

log = logging.getLogger("spicystock.dispatch")

VERSION = 1
REPOSITORY = "spicyChicken59/SpicyStock"
REF = "main"
API = "https://api.github.com"
ET = ZoneInfo("America/New_York")
CT = ZoneInfo("America/Chicago")
#: (workflow file, inputs, zone, local times). Each is started on XNYS sessions; a
#: workflow in ``EVERY_DAY`` is started on every calendar day.
SLOTS: tuple[tuple[str, dict[str, str], ZoneInfo, tuple[str, ...]], ...] = (
    ("evening.yml", {"only_if_unpublished": "true"}, ET, ("18:20", "19:20", "20:20", "21:20")),
    ("morning.yml", {"dry_run": "false"}, CT, ("08:20",)),
    ("service-watch.yml", {}, ET, ("19:00", "21:50")),
    ("service-watch.yml", {}, CT, ("06:00", "08:25", "09:05")),
)
#: The workflows started on every calendar day, session or not. The evening's
#: ``only_if_unpublished`` guard publishes the newest completed session only from
#: its primary slot, only while it is unpublished and only before its next session
#: opens, and does nothing otherwise (``.github/workflows/evening.yml``): on a
#: weekend or a holiday that is a missed session's one recovery before the open.
EVERY_DAY = frozenset({"evening.yml"})
#: One page of the run listing ``GitHub.runs()`` reads. A page this full may not be
#: all of it, so it is never read as complete.
LIST_PAGE = 50
#: The fields kept of each run GitHub lists; nothing else of the answer is read.
RUN_FIELDS = ("id", "event", "display_title", "created_at", "status", "conclusion", "head_branch", "run_attempt")
#: A slot is due from its instant for this long: a tick missed by a restart
#: still starts it, and a slot this old is left to the next one or the backup.
DUE_MINUTES = 30
TICK_SECONDS = 60
TIMEOUT_SECONDS = 30
TOKEN_ENV = "GITHUB_TOKEN"

EXIT_OK, EXIT_FAILED, EXIT_REFUSED = 0, 1, 2


class Refused(RuntimeError):
    """The configuration cannot be run: no token, or a clock without an offset."""


class HTTPFailure(RuntimeError):
    """GitHub answered a request with a status this tool does not act on."""

    def __init__(self, status: int, what: str):
        super().__init__(f"{what}: HTTP {status}")
        self.status = status


class Incomplete(RuntimeError):
    """A run listing that answered 200 but cannot be read as the whole of what was
    asked: a full page, a count larger than the page, or a run this cannot read."""


@dataclass(frozen=True)
class Slot:
    workflow: str
    inputs: tuple[tuple[str, str], ...]
    at: datetime

    @property
    def key(self) -> str:
        return f"{self.workflow}@{self.at.isoformat()}"

    def due(self, now: datetime) -> bool:
        return self.at <= now < self.at + timedelta(minutes=DUE_MINUTES)


def _aware(now: datetime) -> datetime:
    if now.tzinfo is None or now.utcoffset() is None:
        raise Refused("the clock must carry an offset")
    return now


def _created(value) -> datetime | None:
    """A run's ``created_at`` as GitHub writes it (``2026-11-20T23:20:05Z``), or None."""
    try:
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None
    return parsed if parsed is not None and parsed.tzinfo is not None and parsed.utcoffset() is not None else None


def slots_on(day: date) -> list[Slot]:
    """Every slot of one calendar day, in time order; off a session, only the
    slots of the workflows in ``EVERY_DAY``."""
    session = sessions.is_session(day)
    out = []
    for workflow, inputs, zone, times in SLOTS:
        if not session and workflow not in EVERY_DAY:
            continue
        for hhmm in times:
            local = datetime.combine(day, time.fromisoformat(hhmm), tzinfo=zone)
            out.append(Slot(workflow, tuple(sorted(inputs.items())), local))
    return sorted(out, key=lambda s: s.at)


def due(now: datetime) -> list[Slot]:
    """The slots due at ``now``: their instant passed, by less than DUE_MINUTES."""
    now = _aware(now)
    days = {(now - timedelta(minutes=DUE_MINUTES)).astimezone(z).date() for z in (ET, CT)}
    days |= {now.astimezone(z).date() for z in (ET, CT)}
    return [s for day in sorted(days) for s in slots_on(day) if s.due(now)]


# --------------------------------------------------------------- GitHub ----
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):      # a redirect is a status, never followed
        return None


class GitHub:
    """The two calls this tool makes, and the run listing the service watch
    reads (``runs()``), over ``urllib`` with the environment's proxy settings.
    ``send`` is replaced in the tests."""

    def __init__(self, token: str, repository: str = REPOSITORY):
        self.token, self.repository = token, repository
        self._opener = urllib.request.build_opener(_NoRedirect())

    def send(self, method: str, path: str, body: dict | None = None) -> tuple[int, bytes]:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(API + path, data=data, method=method, headers={
            "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
            "Authorization": f"Bearer {self.token}", "User-Agent": "spicystock-dispatch",
            **({"Content-Type": "application/json"} if data is not None else {})})
        try:
            with self._opener.open(request, timeout=TIMEOUT_SECONDS) as response:
                return response.status, response.read(1 << 20)
        except urllib.error.HTTPError as exc:
            return exc.code, b""

    def runs_since(self, slot: Slot) -> list[int]:
        """The ids of the workflow's dispatched runs created at or after the slot."""
        query = urllib.parse.urlencode({"event": "workflow_dispatch", "per_page": 5,
                                        "created": ">=" + slot.at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
        status, raw = self.send("GET", f"/repos/{self.repository}/actions/workflows/{slot.workflow}/runs?{query}")
        if status != 200:
            raise HTTPFailure(status, f"listing {slot.workflow} runs")
        try:
            runs = json.loads(raw).get("workflow_runs") or []
            return [int(r["id"]) for r in runs if isinstance(r, dict) and isinstance(r.get("id"), int)]
        except (ValueError, AttributeError, TypeError):
            raise HTTPFailure(status, f"listing {slot.workflow} runs (an unreadable answer)") from None

    def runs(self, workflow: str, since: datetime) -> list[dict]:
        """The workflow's runs on ``REF`` created at or after ``since``, every event,
        each cut to ``RUN_FIELDS``. Read by the service watch (``tools/service_watch.py``)
        with the workflow's own read-only token. A status other than 200 raises
        ``HTTPFailure``; an answer that is not the whole listing, or a run in it that
        cannot be read, raises ``Incomplete``: neither is ever read as no run."""
        since = _aware(since)
        query = urllib.parse.urlencode({"branch": REF, "per_page": LIST_PAGE,
                                        "created": ">=" + since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
        status, raw = self.send("GET", f"/repos/{self.repository}/actions/workflows/{workflow}/runs?{query}")
        if status != 200:
            raise HTTPFailure(status, f"listing {workflow} runs")
        try:
            answer = json.loads(raw)
        except (ValueError, UnicodeDecodeError, RecursionError):
            raise Incomplete(f"listing {workflow} runs: an unreadable answer") from None
        rows = answer.get("workflow_runs") if isinstance(answer, dict) else None
        total = answer.get("total_count") if isinstance(answer, dict) else None
        if not isinstance(rows, list) or type(total) is not int or total < 0:
            raise Incomplete(f"listing {workflow} runs: an unreadable answer")
        if len(rows) >= LIST_PAGE or total > len(rows):
            raise Incomplete(f"listing {workflow} runs: {total} runs, more than one page holds")
        out = []
        for row in rows:
            kept = {name: row.get(name) for name in RUN_FIELDS} if isinstance(row, dict) else None
            if (kept is None or type(kept["id"]) is not int or kept["id"] < 1
                    or not all(isinstance(kept[name], str) for name in ("event", "display_title", "status"))
                    or not isinstance(kept["created_at"], str) or _created(kept["created_at"]) is None
                    or not (kept["conclusion"] is None or isinstance(kept["conclusion"], str))
                    or not (kept["head_branch"] is None or isinstance(kept["head_branch"], str))
                    or type(kept["run_attempt"]) is not int or kept["run_attempt"] < 1):
                raise Incomplete(f"listing {workflow} runs: a run this cannot read")
            out.append(kept)
        return out

    def dispatch(self, slot: Slot) -> None:
        status, _ = self.send("POST", f"/repos/{self.repository}/actions/workflows/{slot.workflow}/dispatches",
                              {"ref": REF, "inputs": dict(slot.inputs)})
        if status not in (200, 204):
            raise HTTPFailure(status, f"dispatching {slot.workflow}")


# ---------------------------------------------------------------- ledger ----
def read_state(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {"version": VERSION, "started": {}}
    try:
        state = json.loads(path.read_text())
        if state.get("version") == VERSION and isinstance(state.get("started"), dict):
            return state
    except (OSError, ValueError, AttributeError):
        pass
    log.warning("dispatch ledger %s unreadable; starting from GitHub's own runs", path)
    return {"version": VERSION, "started": {}}


def write_state(path: Path | None, state: dict, now: datetime) -> None:
    if path is None:
        return
    keep = now - timedelta(days=7)                 # a week of slots is enough to answer any repeat
    state["started"] = {k: v for k, v in state["started"].items()
                        if datetime.fromisoformat(k.split("@", 1)[1]) >= keep}
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True, indent=1) + "\n")
    tmp.replace(path)


# ------------------------------------------------------------------ tick ----
def tick(now: datetime, github: GitHub, state_path: Path | None = None) -> int:
    """Start every due slot not already started. Returns an exit code."""
    state = read_state(state_path)
    failed = False
    for slot in due(now):
        if slot.key in state["started"]:
            continue
        try:
            existing = github.runs_since(slot)
            if existing:
                state["started"][slot.key] = existing[0]
                log.info("%s already started: run %s", slot.key, existing[0])
                continue
            github.dispatch(slot)
            started = github.runs_since(slot)
            state["started"][slot.key] = started[0] if started else None
            log.info("%s dispatched: run %s", slot.key, started[0] if started else "not yet listed")
        except HTTPFailure as exc:
            failed = True
            log.error("%s not started: %s", slot.key, exc)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            failed = True
            log.error("%s not started: %s", slot.key, type(exc).__name__)
    write_state(state_path, state, now)
    return EXIT_FAILED if failed else EXIT_OK


def token_from(env: dict) -> str:
    token = (env.get(TOKEN_ENV) or "").strip()
    if not token:
        raise Refused(f"{TOKEN_ENV} is not set: a fine-grained token with Actions read and write on {REPOSITORY}")
    return token


def main(argv=None, env=None) -> int:
    env = os.environ if env is None else env
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p_plan = sub.add_parser("plan", help="print one day's slots; no network")
    p_plan.add_argument("--day", required=True, type=date.fromisoformat)
    p_tick = sub.add_parser("tick", help="start every slot due now")
    p_tick.add_argument("--now", type=datetime.fromisoformat, default=None)
    p_tick.add_argument("--state", type=Path, default=None)
    p_loop = sub.add_parser("loop", help="a tick every minute, for ever")
    p_loop.add_argument("--state", type=Path, default=None)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        if args.command == "plan":
            for slot in slots_on(args.day):
                print(f"{slot.at.isoformat()}  {slot.workflow}  {dict(slot.inputs)}")
            return EXIT_OK
        github = GitHub(token_from(env))
        if args.command == "tick":
            return tick(_aware(args.now or datetime.now(timezone.utc)), github, args.state)
        while True:                                   # pragma: no cover - the service's own loop
            tick(datetime.now(timezone.utc), github, args.state)
            clock.sleep(TICK_SECONDS - datetime.now(timezone.utc).second % TICK_SECONDS)
    except Refused as exc:
        log.error("refused: %s", exc)
        return EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())
