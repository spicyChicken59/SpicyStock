# 12 October 2026 — the service, read off the retained publications (#111)

`tools/service_health.py` is a reading of the service and not of the signal.
It walks the commits that put a publication on `main` and the commits that put
a morning, issuer or research receipt beside it, and prints what the records
and their commit times establish about delivery: which expected XNYS session
each publication is for, when it landed against the session's completion
(the scheduled close plus `sessions.COMPLETION_BUFFER_MINUTES`) and against
the evening cron's nominal slot (6:16 PM ET; the retry pair 8:16 PM ET, both
read in the exchange's zone so the DST change is the tz database's answer),
whether it landed before the next open, how often one session was published
twice, what the inputs covered, what the chart reader did and what it cost.
The regime and the ticket counts sit in their own column and never make a
service verdict: zero tickets can be a successful research run, and stale data
cannot be called fresh. It changes no record, decides nothing and fetches no
provider; a shallow checkout fetches the commits the committed reading names,
exactly those, so `--check` holds the two files under
`2026-10-12-service-health-evidence/` on CI as it does here. The reading is
pinned to one commit, `c759a1e6` (the merge of #157, 01:01 UTC on 12 October),
whose time is its clock; `python tools/service_health.py` writes a newer one.

## What the history establishes (11 September to 9 October 2026)

- **21 expected sessions, 21 published, 21 of 21 first publications before the
  next session's open.** The current streak is 21 and the longest 21. No session
  is missing or pending at the clock; the 12 October session is not yet in the
  range, because no publication has been made for it.
- **26 publications**, so four sessions were published more than once: 11
  September (the first real publish, then the scheduled run on later bars), 21
  September (a dispatch and then the late primary slot, two full runs and two
  mails, the duplicate CLAUDE.md already records), 8 October (the scheduled run
  and the owner's no-email production scan at 12:10 UTC) and 9 October (three:
  the scheduled run with the mail delivered, then two no-email production runs
  for the ZIM correction and the review-budget policy). Every revision landed
  after a first publication that was already before the next open.
- **Latency after completion: min 53.1, median 261.9, max 362.1 minutes.** The
  minimum is 11 September's manual run, made before the slot (68 minutes before
  it). From 14 to 18 September the scheduled runs landed 6 to 9 minutes after
  the primary slot. From 22 September every scheduled run landed after the retry
  slot, 133 to 241 minutes after the primary one: **14 of 21** first publications
  are after 8:16 PM ET. The reading reads the publication's instant, not which
  cron fired it; CLAUDE.md records the primary slot itself firing hours late on
  7 October, so "after the retry slot" is a position, not an attribution.
- The commit landed 2 to 5 minutes after the record's own `published_at` on
  every publication (`landed_minutes`).
- **Statuses: 19 degraded, 7 ok.** Where the coverage ledger exists (from 16
  September) the inputs ready were 4,753 to 4,776 of 4,775 to 4,796 intended
  stocks; the 9 October publications are the first under the stale tolerance to
  read `ok` beside a degraded acceptance. The chart reader answered 265 of 302
  requested reads over the 26 publications (twelve a night until the
  review-budget policy, two on 9 October's two later publications); the 22
  September night's 0 of 12 is the format defect #88 fixed. **Cost blocks
  archived: none** -- `run.reader_usage` merged on 11 October (#156) and the
  first publication under it is the next evening's.
- Runner time archived: 5,756.3 seconds elapsed and 1,335.2 seconds of fetch
  over 26 publications, about 3.7 minutes a run.
- **The signal, kept apart:** 21 RED and 5 YELLOW publications, 0 reaction
  tickets, 3 anticipation tickets (MG and SN on 8 October, ZIM on 9 October's
  first publication), each superseded by a later publication of its session.
- **Companion receipts.** Two morning receipts, both `inapplicable`: 9 October
  17:10 UTC for the 9 October session (`entry_window_ended`: the run was
  dispatched after the window) and 10 October 08:56 UTC for the 12 October
  session (`wrong_session`: a Saturday dispatch, before that session's open).
  Three issuer receipts for the 12 October session, all `unavailable` (the SEC
  mapping request failed, the third with an observed HTTP 403), all before the
  open. No research observation is retained yet. **So the acceptance line's
  "morning checks" stand at zero observed:** the first scheduled morning
  attempts are 13:20 and 13:28 UTC on Monday 12 October, and nothing here says
  they will land.

## What it does not establish

The reading reads git and the records. It does not know when GitHub started a
runner, which cron slot fired, or why a run was late; the record archives
`run.run_id` and the reading prints it, and the Actions log is the place to
look. It does not know whether a publication was read by anyone before the
open, or whether Pages served it (the publication gate's log says that). It
says nothing about trading edge: a regime and a ticket count are printed from
the record for the reader who wants them beside the service, and nothing in
this file is a ticket, a fill or a result.

## Reproduce

```
python tools/service_health.py --check                 # the committed files are what the tool writes
python tools/service_health.py                         # a new reading, origin/main's tip the clock
python tools/service_health.py --through <commit>      # the history through a named commit
```

`--check` re-reads the commits the committed JSON names and, where the
checkout carries the history, walks it again and requires the same commits read
and set aside; on a shallow checkout it says so and fetches the named commits.
