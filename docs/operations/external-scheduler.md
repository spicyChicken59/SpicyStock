# The on-time dispatcher (Railway)

GitHub creates this repository's scheduled runs hours after their slots. Every
scheduled evening run of 2 to 18 November 2026 was created 3.56 to 7.99 hours
late, and every scheduled morning run was created after its entry window had
closed. A `workflow_dispatch` is created when it is asked for. The dispatcher
(`tools/dispatch_schedule.py`) asks for one at each slot below, on XNYS
sessions, and for the evening on every calendar day. It reads the same
calendar the run reads (`src/sessions.py`).

| workflow | when (local) | days | inputs |
|---|---|---|---|
| `evening.yml` | 18:20, 19:20, 20:20 and 21:20 America/New_York | every day | `only_if_unpublished` true |
| `morning.yml` | 08:20 America/Chicago | sessions | `dry_run` false |
| `service-watch.yml` | 19:00 and 21:50 America/New_York; 06:00, 08:25 and 09:05 America/Chicago | sessions | none |

A slot is due from its instant for 30 minutes (`DUE_MINUTES`), except the
watch's 08:25 America/Chicago slot, which is due only until the session's open
and is never dispatched at or after it (`BEFORE_OPEN`). That watch is not
dispatched until 180 seconds (`WAIT_SECONDS`) after the newest dispatch of the
morning check it judges (`WAITS_FOR`), this tool's or anyone's: the check's
receipts landed on `main` 88 to 94 seconds (23 October 2026) and 97 to 103
seconds (4 November 2026) after its dispatch was created. A catch-up that
starts the check at 08:26 starts the watch at 08:29; one at 08:28 leaves the
morning to the 09:05 slot. The
evening's four starts are one publication and three no-ops: the workflow's
`only_if_unpublished` guard publishes the newest completed session once,
from its primary slot (18:16 ET) on, only while it is unpublished and only
before its next session opens. On a weekend or a holiday the same four starts
are that guard's recovery for a missed Friday or eve, and do nothing after a
published one (`EVERY_DAY`). A half day keeps every slot: the session
completes earlier, and 18:20 ET is after it.

The watch's slots are where its alerts become true: 19:00 ET after an
evening not started by 18:50 ET, 21:50 ET after one started on time but not
published by 21:45 ET, 06:00 CT after a night not published by 3:30 AM ET,
08:25 CT for the morning check (five minutes after it is started, five before
the 8:30 CT open) and 09:05 CT after the entry window. The dispatcher starts
no watch on a weekend or a holiday: a missed Friday is not published from
4:16 AM ET on Saturday, only GitHub's backup crons (hours late) run the watch
before Monday, and the dispatcher's first watch to mail it is Monday's 06:00 CT
slot.

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
asked for it or anyone did. `loop`, which the service runs, also holds its
ledger in memory: each dispatch it made, and when, so one GitHub has not
listed yet is not made again on the next tick and the pre-open watch still
waits for it. A repeat tick, a restart or a second copy starts nothing twice,
except two copies asking in the same second, or a restart before GitHub lists
a dispatch the copy before it made.

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

The service watch (`tools/service_watch.py`) checks that the dispatcher ran.
It reads the Actions run listing of `evening.yml`, `morning.yml` and its own
`service-watch.yml` with its workflow's read-only token and says, of each:

- `on_time`: a `workflow_dispatch` under the dispatcher's run name
  (`Evening dispatch (only if unpublished)`, `Morning publication`,
  `Service watch (manual)`) created inside its first slot's due window. That
  is a dispatch in the slot, whoever asked for it: the listing cannot tell this
  dispatcher's dispatch from one made by hand under the same name (the owner's
  own routine, say), and the watch claims nothing more;
- `started_late`: the work started, but not by a dispatch in that first slot.
  A dispatch in one of the dispatcher's later evening slots (19:20, 20:20 or
  21:20 ET, or a weekend's or a holiday's recovery start) is named as that
  start; anything else (the backup cron, a dispatch outside every slot) is
  said to be no dispatch in any of its slots;
- `not_started`: for the evening, no run listed by 18:50 ET (an evening cron
  whose guard skips it -- not the active UTC slot, or a weekday holiday's own
  crons, whose nominal date is no session -- is no run, and one its guard runs
  for another session is that session's); for the watch, no run dispatched in
  its own previous slot, or one dispatched there that ended failed or
  cancelled, said after the fact by a later watch. A watch run GitHub's cron
  started, red or green, is read by no watch: a red one is seen only in
  Actions;
- `failed`: every run of the evening ended without publishing; a dispatch in a
  first slot that ended without its work, beside a run that did not, is named
  and makes the start `started_late`;
- `unknown`: no token, or that workflow's listing could not be read. Without
  a token it is never an alert; with one, a listing that cannot be read is an
  alert of its own, `scheduler:listing:unreadable`, standing, raised only when
  2 watch runs in a row could not read it (`LISTING_FAILURES_IN_A_ROW`) and
  cleared only after 24 hours with no listing failure (`LISTING_CLEAR_HOURS`).

While the listing shows the morning check's run still queued or in progress
inside its collection window, a check whose receipt or go/cancel file is not
on `main` yet is `in_progress`: no alert, and a later watch judges it.

A `started_late` evening or morning, a watch slot with no dispatched run and a
listing that cannot be read are standing conditions: each is mailed once,
again only after 7 days (`REPEAT_DAYS`) while it stands, and at once when it
returns after clearing (the watch's ledger records when each was last answered
on time). An evening `not_started` or `failed` is about one session and
is mailed once for it. It also still flags an evening run that started more
than 60 minutes after its 18:16 ET primary slot (`LATE_START_MINUTES`, read
off the record when no listing answers), and a morning check that had not
landed by 08:25 CT (`MORNING_ALERT_CT`), on every session. Until this
dispatcher is deployed every one of these is true: the backup crons are what
run, hours late.

## The limit: nothing outside GitHub watches the watch

The watch is a GitHub workflow. It can say that its own previous slot was
not started, but only from a later run; if GitHub starts no watch at all, or
GitHub is down, nothing raises anything. This dispatcher is the only clock
outside GitHub: once it is deployed it starts the watch at its five slots, and
the watch in turn says whether the dispatcher started the evening and the
morning on time. It holds no mail credential and adds no account: a dispatcher
that is itself down is seen only by the watch's scheduler answers, from
GitHub's backup crons. A watch run that judged and mailed ends green; a red one
did not finish (it crashed, a message it owed was refused twice, or the ledger it
changed could not be written). A later watch reads a red run as one that did not
start only when this dispatcher started it in one of its slots; a red run that
GitHub's cron started is read by no watch, and is seen only in Actions.

## Removing it

Delete the Railway service. GitHub's crons keep running, late, as before.
