# The on-time dispatcher (Railway)

GitHub creates this repository's scheduled runs hours after their slots. Every
scheduled evening run of 2 to 18 November 2026 was created 3.56 to 7.99 hours
late, and every scheduled morning run was created after its entry window had
closed. A `workflow_dispatch` is created when it is asked for. The dispatcher
(`tools/dispatch_schedule.py`) asks for one at each slot below, on XNYS
sessions only. It reads the same calendar the run reads (`src/sessions.py`).

| workflow | when (local) | inputs |
|---|---|---|
| `evening.yml` | 18:20, 19:20, 20:20 and 21:20 America/New_York | `only_if_unpublished` true |
| `morning.yml` | 08:20 America/Chicago | `dry_run` false |
| `service-watch.yml` | 06:00, 08:45 and 11:00 America/Chicago | none |

A slot is due from its instant for 30 minutes (`DUE_MINUTES`). The
evening's four starts are one publication and three no-ops: the workflow's
`only_if_unpublished` guard publishes the newest completed session once,
from its primary slot (18:16 ET) on. A half day keeps every slot: the
session completes earlier, and 18:20 ET is after it.

GitHub's own crons stay in every workflow as the backup. Each workflow's guard
already makes a second start harmless.

## What it holds and what it does

- **One credential**, `GITHUB_TOKEN`. Make it a fine-grained personal access
  token scoped to this repository alone, with one permission: **Actions:
  Read and write**. Nothing else.
- **Two requests per due slot**, to `api.github.com`:
  - a read of the workflow's dispatched runs created since the slot;
  - the dispatch itself, only when that read finds none.

  One more read after a dispatch finds the run's id.
- **What it logs:** the workflow, the slot, the run id GitHub listed, and,
  when GitHub refuses a request, its HTTP status. It never logs a token, a
  header or a response body.
- **What it does not do:** it writes no file but an optional `--state`
  ledger, mails nothing, and reads nothing of the repository but the
  calendar.

It is idempotent without a volume. A slot is done when GitHub lists a
dispatched run of its workflow created since the slot, whether this tool
asked for it or anyone did. A repeat tick, a restart or a second copy
starts nothing twice, except two copies asking in the same second.

## Setting it up on Railway

This is the owner's step; nothing in the repository deploys it.

1. **Create the service.** In the Railway project that holds the morning
   host, create a new service from this repository.
2. **Point it at its config.** Under the service's settings, set **Config as
   code** to `deploy/scheduler/railway.json`. That file builds
   `deploy/scheduler/Dockerfile` and keeps one replica, restarted always. The
   image installs `exchange_calendars` alone (`requirements-scheduler.txt`,
   with `constraints.txt`) and copies two files: `src/sessions.py` and
   `tools/dispatch_schedule.py`.
3. **Give it the token.** Under **Variables**, add `GITHUB_TOKEN` (the
   fine-grained token above). It needs no other variable, no volume, no
   public domain and no healthcheck: it serves nothing.
4. **Deploy, then read the log.** Off a slot it prints nothing. At a slot it
   prints one line per due slot:
   - `evening.yml@2026-11-20T18:20:00-05:00 dispatched: run 123456789`
   - `... already started: run 123456789`
   - `... not started: dispatching evening.yml: HTTP 403`

## Checking it without Railway

```
python tools/dispatch_schedule.py plan --day 2026-11-20
GITHUB_TOKEN=... python tools/dispatch_schedule.py tick --now 2026-11-20T18:21:00-05:00
```

`plan` needs no token and makes no request. `tick` starts what is due at
the given clock, so give it a clock inside a slot's 30 minutes only when you
mean it.

## When it fails

| log line | what it means | what to do |
|---|---|---|
| `refused: GITHUB_TOKEN is not set` | the variable is missing | add it; the service exits 2 and Railway restarts it |
| `HTTP 401` | the token is wrong or expired | make a new one |
| `HTTP 403` | the token lacks Actions write, or is not scoped to this repository | fix its permissions |
| `HTTP 404` | the workflow file or the repository is not visible to the token | check the repository scope |
| `HTTP 422` | GitHub refused the inputs or the ref | the workflow's inputs changed: read `tools/dispatch_schedule.SLOTS` against them (a test holds the two) |

The service watch (`tools/service_watch.py`) flags two things:

- an evening run that started more than 60 minutes after its 18:16 ET
  primary slot (`LATE_START_MINUTES`);
- a morning check that had not landed by 08:45 CT (`MORNING_DUE_CT`), on
  every session.

Either flag means the dispatcher did not start it. The backup cron is what
ran, hours late.

## Removing it

Delete the Railway service. GitHub's crons keep running, late, as before.
