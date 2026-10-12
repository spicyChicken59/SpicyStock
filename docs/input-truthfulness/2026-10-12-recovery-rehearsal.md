# The service's failures, rehearsed, and its recovery — 12 October 2026

Issue #111 asks the service to "rehearse provider, reader and publication
failures; recover idempotently without duplicate work, stale overwrite or
unbounded calls", and names "a completed failure/recovery rehearsal" in its
acceptance line. This is that rehearsal, as a tool that can be run again and
whose output is held: `tools/recovery_rehearsal.py` writes
[`2026-10-12-recovery-rehearsal-evidence/rehearsal.json`](2026-10-12-recovery-rehearsal-evidence/rehearsal.json)
and [its readable twin](2026-10-12-recovery-rehearsal-evidence/rehearsal.md), and
`--check` runs the whole rehearsal again and refuses a byte of drift in either.

## What is rehearsed, and how

The real evening, every stage: `pipeline.run_evening()` is driven through the
same doubles the test suite and the fixture generator use (`tests/fakes.py`: the
Alpaca data client, the Anthropic client, Resend), over one small synthetic
market (two A+ bursts the reader is asked about, one coiled name, eleven quiet
names and the benchmark; the suite's own night plus a second burst, so the
reader's bound has two names to count), one pinned night after another from
Friday 4 September to Tuesday 15 September 2026, Labor Day among them. One
boundary is broken a night:

| night | injected | what the service did |
|---|---|---|
| 4 Sep | nothing | published, two reaction tickets and one anticipation ticket, one mail |
| 7 Sep (Labor Day) | nothing | the calendar said no session: nothing fetched, asked, written or mailed |
| 8 Sep | the bars endpoint refuses every batch | exit 1, nothing published, the 4 September publication byte-identical, one FAILED notice, zero reader calls |
| 8 Sep, 8:30 PM ET | the provider answers again | the retry slot published 8 September once |
| 9 Sep | the reader's account has no credit | one call, then no more; published degraded, no reaction ticket |
| 10 Sep | the reader's transport fails every call | two names times two attempts, four calls; published degraded, no reaction ticket |
| 11 Sep | the mail provider refuses the digest | exit 3, the record published and kept, mail `failed` |
| 14 Sep | every frame served two sessions stale | exit 1, nothing published, the 11 September publication byte-identical, one FAILED notice |
| 15 Sep | nothing | published again |

Before and after every night the evening workflow's own guard is asked what a
scheduled slot would do: the Python body of `evening.yml`'s guard step,
executed as written under a frozen clock over the rehearsal's own
`docs/data.json`, at the primary slot (6:16 PM ET), the retry slot (8:16 PM ET),
the next session's open, and for a delayed event.

## What it establishes

- **No duplicate work.** Of 22 guard decisions, the ten it admitted were the
  slot before each night that had a session (the retry slot, for the recovery
  run) and the retry slot after each night that failed; it admitted **zero**
  slots after a publication. A
  degraded publication and a publication whose mail failed are publications: the
  retry slot after each was refused as "already published".
- **No stale overwrite.** Two nights published nothing, and on each every file
  under `docs` was byte-identical after the run (the tool refuses to record a
  night that published nothing and changed a file). A delayed event for the 4
  September slot arriving over the 8 September publication was refused: "A newer
  session than 2026-09-04 is already published". Recovery at the next session's
  open was refused as expired, twice.
- **No unbounded calls.** The bars endpoint was asked twice on the outage night
  (one batch, one retry, then dropped) and once on every other. Reader calls
  stayed within names times `grader.ATTEMPTS` every night: the empty balance
  stopped them after **one** call (the second name was a fallback row without a
  call), the dead transport cost exactly four.
- **Recovery is one run.** The retry slot after the outage was admitted, its run
  published the missed session once, and the same slot asked again, and a
  delayed primary event for the same evening, were both refused.

## What it does not establish

Every failure is injected and the market is synthetic. The rehearsal shows that
the code does what it says under a failure it was told to have. It does not show
that a real provider fails that way, that a runner starts at its slot (the
service reading in
[`2026-10-12-service-health.md`](2026-10-12-service-health.md) records that 14
of 21 first publications landed after the retry slot), that GitHub accepts the
commit, or that Pages serves it. The workflow's persist step, the publication
gate and the morning collectors are not driven here. No provider was called, no
mail was sent, no rule changed.

## Reproduce

```
python tools/recovery_rehearsal.py            # writes the two files (about fifteen seconds)
python tools/recovery_rehearsal.py --check    # runs it again and holds them
```

`tests/test_recovery_rehearsal.py` runs the rehearsal once and states every
night's facts by hand; the committed files are held equal to that fresh run.
