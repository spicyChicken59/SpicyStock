# 13 October 2026: when GitHub starts the scheduled runs (#111)

`tools/schedule_reliability.py` reads, for every scheduled run of this
repository, how long after its cron slot GitHub created it. It reads the
public Actions API and nothing else, and decides nothing. The service-health
reading (12 October) measures when each publication landed. It cannot say why
a publication landed hours after its slot, because a record does not know when
its runner started. The Actions listing does. A scheduled run is created when
GitHub's scheduler fires it, so its `created_at` minus the cron instant it was
for is the scheduler's own delay, before any step of ours runs.

The evidence is under
[`2026-10-13-schedule-reliability-evidence/`](2026-10-13-schedule-reliability-evidence/):

- `runs.json`: the snapshot. It holds the 128 scheduled runs the API listed at
  18:14 UTC on 13 October, and the 360 runs a push to `main` triggered (the
  contrast). Both keep only the fields the reading uses. Beside them are each
  scheduled workflow's cron tables, version by version, as `main` carried them
  at `3a972ad7`.
- `schedule-reliability.json` and `.md`: the reading derived from the snapshot.

`--check` holds both reading files to the snapshot, with no network and no
history. The tests hold the snapshot's tables to the workflow files git carries.

## How a run is placed

Every scheduled run since the second build names its cron in its run name.
The evening, morning and source-recovery workflows write
`... cron <expression>`. The run is placed at the latest instant that cron
names at or before the run was created. A run whose name records no cron is
placed at the nearest preceding instant of its workflow's table in force at
that moment, and the reading says so: those are the first build's 14 runs and
the six weekly secret scans. Either way the placement assumes a delay shorter
than the cron's own period. That holds for every run here: the longest is
504.9 minutes against a period of a day.

An expected slot is every instant a table in force named, from that workflow's
first table to the snapshot. A slot with no run is `no_run` once a day has
passed, and `not_started` before that.

## What the history shows

**Before 21 September GitHub created every scheduled run within 17 minutes of
its slot.** That covers 57 runs over the evening, morning and weekly-scan
workflows, with weekly medians of 4.2 to 15.1 minutes. The last prompt run was
the weekly secret scan at 06:00 UTC on Monday 21 September, created 4.3 minutes
after its slot.

**From the evening primary at 22:16 UTC that Monday, no scheduled run has
been prompt.** That run was created 152.2 minutes after its slot. The
reading counts 71 scheduled runs from that slot on, every one of them created
130.6 to 504.9 minutes after their slots, median 276.5. 42 were more than four
hours late, and 13 of them more than six hours. No expected slot of any
workflow went without a run.

The delay has grown each week since:

- The evening workflow's weekly medians were 208.3, 257.4 and 285.2 minutes,
  then 336.8 minutes in the four runs of the week of 12 October.
- The Monday secret scan was 378.3, 418.0 and 470.0 minutes late on 28
  September, 5 October and 12 October.

The slots are spread across the day (06:00, 13:20 to 14:28 and 22:16 to 01:16
UTC), and every one of them is late, so this is not one slow hour of the day.

**The morning is where it bites.** The morning workflow's four new crons, 8:20
and 8:28 Chicago in each season, first fired on Monday 12 October. GitHub
created those four runs 463.3 to 504.9 minutes after their slots. The 13:20 UTC
run was created at 21:44 UTC, more than eight hours after the 8:30 Chicago open
it was meant to precede. Every guard said `entry_window_ended` and
collected nothing, correctly. At the snapshot, the 4 slots of 13 October had
not been created at all, almost five hours after the first of them.

**The contrast: the delay is the scheduler's alone.** Over the same weeks, the
144 runs a push to `main` triggered were each created within seconds of the
pushed commit's own timestamp: none more than 0.3 minutes, median 0.1. That
timestamp is an upper bound on the push, since a commit can be made before it
is pushed. The listing has no reference instant for a manual dispatch, so the
reading does not measure dispatch delay.

What the listing does not say: why the scheduler's delay changed on 21
September, or whether it is specific to this repository. GitHub documents that
scheduled events can be delayed under load and that queued scheduled runs can
be dropped. Nothing here attributes the change to a cause. The listing also
shows nothing of runner pickup: for a run's first attempt the API's
`run_started_at` is its `created_at`. The job logs carry pickup times and are
not read.

## What it means for the service

- **The evening still publishes in time.** All 22 due sessions landed before
  the next open. That is the service-health tool run through `279ec5a3` on 13
  October and recorded in CLAUDE.md; the committed reading stops at 9 October.
  The evening's first run is created hours late, but the window to the next
  open is about 15 hours. The 12 October session landed 410.5 minutes after
  completion. The retry slots are not a retry in practice. On 12 October their
  runs were created at 06:43 and 07:45 UTC, after the primary's publication had
  landed at 03:05.
- **No scheduled morning check can be relied upon at these delays.** A morning
  observation has to land in the 8:20 to 8:30 Chicago window, and every run in
  that window has been created 463 to 505 minutes late. #111's
  acceptance line asks for ten consecutive sessions with morning checks; under
  the scheduler as it now behaves, that line cannot be met by the morning crons.
- **The source-recovery receipts are at risk too.** They must land before the
  next open, and their first slot is 07:37 UTC on 14 October. At the evening
  workflow's delays that is before the open. At the morning workflow's it is
  after, and the receipt would be the honest inapplicable one. The next reading
  will show which.

## Options for the morning, for Mo

Nothing below is adopted here. Each option changes something outside this
repository, holds a credential, or spends runner time, so each is Mo's call.

1. **Leave the crons, and accept no scheduled morning checks.** This costs
   nothing. The guard keeps every late run honest. The morning desk keeps
   working from the evening's record, without dated quotes.
2. **Start the morning run from outside GitHub's scheduler.** The workflow
   already takes a manual dispatch, and a manual dispatch always reaches the
   collector, which applies the same window and refusals. The trigger could
   be:
   - Mo, tapping *Run workflow* on `morning.yml` with `dry_run` off, from the
     GitHub app at about 8:15 Chicago;
   - a claude.ai scheduled routine that dispatches it;
   - an external cron holding a fine-grained token limited to this
     repository's Actions.

   Dispatch promptness is not measured here; push events are prompt. Its
   costs: a person or a token outside GitHub, and the trigger's own
   punctuality, unmeasured until it runs.
3. **Schedule earlier and wait inside the job.** A cron hours before the window
   whose job sleeps until 8:15 Chicago is bounded by a hosted job's 360-minute
   limit. Since 21 September, 58 of 71 scheduled runs were created within 360
   minutes of their slots, but none of the four morning runs was. It holds a
   runner idle for hours and still fails on the slowest days.
4. **A small host with its own clock** (the cached-backend proposal, #108).
   This is the most punctual and the most to own: an account, a deployment and
   credentials outside GitHub.

**Recommendation: option 2, starting with Mo's own tap** for the ten sessions
#111 needs. It uses the guarded workflow as it is and holds no new credential.
Each dispatched run lands in the same Actions listing as `workflow_dispatch`,
so its creation can be checked against Mo's own clock. If the tap is
impractical, a scheduled routine is the next step. This reading should be
re-run first, so the routine's own punctuality is measured rather than assumed.

## Limits

The snapshot is one moment of a listing that grows: a slot listed as not
started may be created later, and a later run changes nothing already listed.
`--fetch` is the only path that touches the network. A new reading is a new
dated snapshot, never an edit of this one. The 13 October morning runs are the
first thing the next snapshot will show.
