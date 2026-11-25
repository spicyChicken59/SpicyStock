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
  (``tools/service_watch.MORNING_ALERT_CT``) and after the entry window. The
  08:25 slot is due only until the session's open (``BEFORE_OPEN``), never
  at or after it, and it is not dispatched until ``WAIT_SECONDS`` after the
  newest dispatch of the morning check it judges (``WAITS_FOR``), this
  tool's or anyone's: a catch-up that starts the check late starts the watch
  late too, or leaves it to the 09:05 slot.

GitHub's own crons stay in each workflow as the backup; every workflow's
guard already makes a second start harmless.

It holds one credential, ``GITHUB_TOKEN``: a fine-grained token with
Actions read and write on this repository and nothing else. It writes no
file but its optional ``--state`` ledger, mails nothing, and logs only the
workflow, the slot, the run id GitHub gives the dispatch and an HTTP status;
never a token, a header or a response body.

Idempotent: a slot is due from its instant for ``DUE_MINUTES`` (a
``BEFORE_OPEN`` slot until the session's open), and before
it asks for a run it reads the workflow's runs created since the slot by a
dispatch (``event=workflow_dispatch``). One there -- this tool's on an earlier
tick, or anyone's -- means the slot is done; the ledger (``--state``, or held
in memory by ``loop`` when no file is given) says so without asking GitHub
again, and so covers a dispatch GitHub has not listed yet. A repeat tick, a
restart and a second copy of the scheduler therefore start a slot's run at
most once each, barring two copies asking in the same second, or a restart
before a dispatch it made is listed.

    python tools/dispatch_schedule.py plan --day 2026-11-20    # the day's slots, no network
    python tools/dispatch_schedule.py tick [--now ISO] [--state FILE]
    python tools/dispatch_schedule.py loop [--state FILE]      # a tick every minute (Railway), its ledger in memory

Exit codes: 0 every due slot was started or was already started (or none
was due); 1 a dispatch or a listing failed (named by its status); 2 the
configuration is refused (no token, a clock without an offset).
"""
from __future__ import annotations

import argparse
import http.client
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
#: Slots due only until the session's open, never at or after it: (workflow, zone, local time). The watch's
#: 08:25 CT slot judges the morning check before the 8:30 CT open; a tick that reaches it later (a restart, a
#: catch-up) leaves it to the 09:05 slot.
BEFORE_OPEN = frozenset({("service-watch.yml", "America/Chicago", "08:25")})
#: A slot of the first workflow is not dispatched until ``WAIT_SECONDS`` after the newest dispatch of the second
#: created since that workflow's latest slot on the same day: the watch judges the morning check it waits for.
WAITS_FOR = {"service-watch.yml": "morning.yml"}
#: The morning check's receipts landed on main 88 to 94 seconds (23 October 2026) and 97 to 103 seconds (4 November
#: 2026) after its dispatch was created (CLAUDE.md), and the watch reads main at its checkout: two and a half minutes
#: covers the 103 with margin, the watch's own start on top. Ticks are on the minute and GitHub stamps a dispatch a
#: few seconds after its tick, so the third tick after a catch-up dispatch clears the wait whenever the stamp is
#: within 30 seconds of its tick: a catch-up at 8:26 AM CT starts the watch at 8:29, before the 8:30 open.
WAIT_SECONDS = 150
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
    #: where the due window ends: ``DUE_MINUTES`` after ``at`` unless the slot is in ``BEFORE_OPEN``
    until: datetime | None = None

    @property
    def key(self) -> str:
        return f"{self.workflow}@{self.at.isoformat()}"

    @property
    def end(self) -> datetime:
        return self.until if self.until is not None else self.at + timedelta(minutes=DUE_MINUTES)

    def due(self, now: datetime) -> bool:
        return self.at <= now < self.end


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
            # a BEFORE_OPEN slot is due until the session opens; one at or after the open is never due
            until = max(local, sessions.hours(day)[0]) if (workflow, zone.key, hhmm) in BEFORE_OPEN else None
            out.append(Slot(workflow, tuple(sorted(inputs.items())), local, until))
    return sorted(out, key=lambda s: s.at)


def slot_end(workflow: str, at: datetime) -> datetime:
    """Where the due window of ``workflow``'s slot at ``at`` ends: its own ``Slot.end`` when ``at`` is one of its
    slots, else ``DUE_MINUTES`` after it."""
    at = _aware(at)
    for zone in (ET, CT):
        for slot in slots_on(at.astimezone(zone).date()):
            if slot.workflow == workflow and slot.at == at:
                return slot.end
    return at + timedelta(minutes=DUE_MINUTES)


def due(now: datetime) -> list[Slot]:
    """The slots due at ``now``: their instant passed, and their due window (``Slot.end``) not yet."""
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

    def dispatches_since(self, workflow: str, since: datetime) -> list[tuple[int, datetime | None]]:
        """(id, ``created_at``) of the workflow's dispatched runs created at or after ``since``, newest first as
        GitHub lists them; the instant is None when the answer does not carry one this can read."""
        query = urllib.parse.urlencode({"event": "workflow_dispatch", "per_page": 5,
                                        "created": ">=" + since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
        status, raw = self.send("GET", f"/repos/{self.repository}/actions/workflows/{workflow}/runs?{query}")
        if status != 200:
            raise HTTPFailure(status, f"listing {workflow} runs")
        try:
            runs = json.loads(raw).get("workflow_runs") or []
            return [(int(r["id"]), _created(r.get("created_at"))) for r in runs
                    if isinstance(r, dict) and isinstance(r.get("id"), int)]
        except (ValueError, AttributeError, TypeError):
            raise HTTPFailure(status, f"listing {workflow} runs (an unreadable answer)") from None

    def runs_since(self, slot: Slot) -> list[int]:
        """The ids of the workflow's dispatched runs created at or after the slot."""
        return [run_id for run_id, _ in self.dispatches_since(slot.workflow, slot.at)]

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
def _fresh_state() -> dict:
    """``started``: each slot's run id (None when not yet listed); ``dispatched``: when this tool dispatched it."""
    return {"version": VERSION, "started": {}, "dispatched": {}}


def read_state(path: Path | None) -> dict:
    if path is None or not path.exists():
        return _fresh_state()
    try:
        state = json.loads(path.read_text())
        if state.get("version") == VERSION and isinstance(state.get("started"), dict) \
                and isinstance(state.get("dispatched", {}), dict):
            state.setdefault("dispatched", {})
            return state
    except (OSError, ValueError, AttributeError):
        pass
    log.warning("dispatch ledger %s unreadable; starting from GitHub's own runs", path)
    return _fresh_state()


def _slot_at(key: str) -> datetime | None:
    try:
        return _created(key.split("@", 1)[1])
    except IndexError:
        return None


def _prune(state: dict, now: datetime) -> None:
    keep = now - timedelta(days=7)                 # a week of slots is enough to answer any repeat
    for part in ("started", "dispatched"):
        state[part] = {k: v for k, v in state.get(part, {}).items()
                       if (at := _slot_at(k)) is not None and at >= keep}


def write_state(path: Path | None, state: dict, now: datetime) -> None:
    _prune(state, now)
    if path is None:
        return
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True, indent=1) + "\n")
    tmp.replace(path)


def _waited_for(slot: Slot, now: datetime, github: GitHub, state: dict) -> datetime | None:
    """The newest dispatch of the workflow ``slot`` waits for (``WAITS_FOR``), when it was created less than
    ``WAIT_SECONDS`` before ``now``: this tool's own, from its ledger, or anyone's, from GitHub's listing, since
    that workflow's slot on the same day, while that slot is due or was due less than ``WAIT_SECONDS`` ago. None
    when there is nothing to wait for (and then GitHub is not asked)."""
    upstream = WAITS_FOR.get(slot.workflow)
    if upstream is None:
        return None
    wait = timedelta(seconds=WAIT_SECONDS)
    earlier = [s for s in slots_on(slot.at.date()) if s.workflow == upstream and s.at <= now < s.end + wait]
    if not earlier:
        return None
    latest = earlier[-1]
    instants = [at for key in [s.key for s in earlier] if (at := _created(state["dispatched"].get(key))) is not None]
    # a listed dispatch whose instant cannot be read is taken as just made: the watch waits rather than guesses
    instants += [created if created is not None else now
                 for _, created in github.dispatches_since(upstream, latest.at)]
    newest = max(instants, default=None)
    return newest if newest is not None and now - newest < wait else None


# ------------------------------------------------------------------ tick ----
def tick(now: datetime, github: GitHub, state_path: Path | None = None, state: dict | None = None) -> int:
    """Start every due slot not already started. Returns an exit code. ``state`` is a ledger the caller holds in
    memory (``loop`` without ``--state``); otherwise it is read from ``state_path`` and written back."""
    state = read_state(state_path) if state is None else state
    state.setdefault("dispatched", {})
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
            waited = _waited_for(slot, now, github, state)
            if waited is not None:
                log.info("%s waits: %s was dispatched at %s, less than %s seconds ago", slot.key,
                         WAITS_FOR[slot.workflow], waited.isoformat(), WAIT_SECONDS)
                continue
            github.dispatch(slot)
            state["dispatched"][slot.key] = now.isoformat()
            started = github.runs_since(slot)
            state["started"][slot.key] = started[0] if started else None
            log.info("%s dispatched: run %s", slot.key, started[0] if started else "not yet listed")
        except HTTPFailure as exc:
            failed = True
            log.error("%s not started: %s", slot.key, exc)
        except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as exc:
            # a transport fault (a refused connection, a cut or garbled answer) is named by its type alone
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
        # without a file the loop keeps its ledger in memory: a dispatch it made is known before GitHub lists it
        memory = None if args.state is not None else _fresh_state()
        while True:                                   # pragma: no cover - the service's own loop
            tick(datetime.now(timezone.utc), github, args.state, memory)
            clock.sleep(TICK_SECONDS - datetime.now(timezone.utc).second % TICK_SECONDS)
    except Refused as exc:
        log.error("refused: %s", exc)
        return EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())
