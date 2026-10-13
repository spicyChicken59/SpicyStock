# 12 October 2026 — the service, read off the retained publications (#111)

**Superseded on 13 October by [the `service_health_v3` reading](2026-10-13-service-health.md)**, which reads
each publication against the evening slots its own rules archived. This report and the files under
`2026-10-12-service-health-evidence/` are kept as they were written: `service-health.{json,md}` are the
v2 reading, and `v1/` holds the first version as `main` carried it before the correction below
(`279ec5a3`), each held to its git blob identity by `tests/test_service_health.py`. The tool no longer
re-derives either, so `--check` below now holds the 13 October files; over this history the
correction moves nothing, no record here archiving its own slots.

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

**Corrected 13 October (`service_health_v2`).** Every delivery fact is now the
commit's landing: the committer time of the commit that put the record on
`main`, the instant git keeps for it. The push follows it by seconds and Pages
serves it later still, so it is a lower bound on when a reader could see the
record, and the closest one the history holds. The record's own
`published_at`, when the run generated it, is kept beside it as `generated_*`
and never read as a delivery. The first reading measured the latency, the slots
and before-the-open off the generation instant, chose a session's first
delivery by generation order, and would have stopped the whole walk on one
commit whose file was not JSON. Each was reproduced on synthetic histories
before it was changed: a record generated at 13:25 UTC and landed at 13:40,
after a 13:30 open, read as before it; a session whose later-generated run
landed first named the other as its first delivery; a truncated record aborted
the walk.

A review of the correction by execution found five more, each reproduced
before it was touched. Ordering by committer time was still a clock: a child
commit dated inside its parent's second, or behind it, was ordered before it.
The order is the history's own now (`--topo-order`, each reading's `sequence`),
and the committer time is only the instant. "Fresh" read the newest record that
could be read, so a truncated record on `main` read as fresh; `main_carries`
names the newest commit that changed the record, read or set aside, and fresh
needs it to be readable and for the newest due session. Setting a commit aside
on any failure had made a git store that could not produce an object read as a
missing session; only a file that is not JSON is set aside now (`NotJSON`), and
a git failure is a refusal again. A count the summary adds up that is not a
non-negative integer is a record the reading cannot place. And the first draft
of this report gave a range one session short of the file's.

Over this history the correction moves the latency by the 2.4 to 5.5 minutes
each commit took after its record's clock, and changes no before-open verdict,
first delivery, revision count, set-aside or order: the history's order is the
committer times' on every commit here.

## What the history establishes (11 September to 9 October 2026)

- **21 expected sessions, 21 published, 21 of 21 first publications landed
  before the next session's open.** The current streak is 21 and the longest 21. No session
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
- **Latency after completion, landed: min 55.8, median 266.7, max 367.0
  minutes** (by the records' own clocks: min 53.1, median 261.9, max 362.1). The
  minimum is 11 September's manual run, landed before the slot (65 minutes
  before it). From 14 to 18 September the scheduled runs landed 9.6 to 11.7
  minutes after the primary slot. From 22 September every scheduled run landed after the
  retry slot, 137.2 to 246.0 minutes after the primary one: **14 of 21** first
  publications landed after 8:16 PM ET, as 14 were generated after it. The reading reads the publication's instant, not which
  cron fired it; CLAUDE.md records the primary slot itself firing hours late on
  7 October, so "after the retry slot" is a position, not an attribution.
- The commit landed 2.4 to 5.5 minutes after the record's own `published_at`
  on every publication (`landed_minutes`); every first publication was
  generated, and landed, before the next open.
- **Statuses: 19 degraded, 7 ok.** Where the coverage ledger exists (from 16
  September) the inputs ready were 4,753 to 4,776 of 4,775 to 4,796 intended
  stocks; the 9 October publications are the first under the stale tolerance to
  read `ok` beside a degraded acceptance. The chart reader answered 265 of 302
  requested reads over the 26 publications (twelve on each until the
  review-budget policy's own publication, the last of 9 October's three, which
  asked for two); the 22
  September night's 0 of 12 is the format defect #88 fixed. **Cost blocks
  archived: none** -- `run.reader_usage` merged on 11 October (#156) and the
  first publication under it is the next evening's.
- Runner time archived: 5,756.3 seconds elapsed and 1,335.2 seconds of fetch
  over 26 publications, about 3.7 minutes a run.
- **The signal, kept apart:** 21 RED and 5 YELLOW publications, 0 reaction
  tickets, 3 anticipation tickets (the records name them: MG and SN on 8
  October, ZIM on 9 October's first publication), each superseded by a later
  publication of its session.
- **Companion receipts.** Two morning receipts, both `inapplicable`: one
  generated at 17:10 and landed at 17:11 UTC on 9 October for the 9 October
  session (`entry_window_ended`: the run was dispatched after the window), and
  one generated at 08:56 and landed at 08:57 UTC on 10 October for the 12
  October session (`wrong_session`: a Saturday dispatch, before that session's
  open). Three issuer receipts for the 12 October session, all `unavailable`
  and all landed before its open (the receipts' own errors say the SEC mapping
  request failed, the third with an observed HTTP 403; the reading copies the
  status only). No research observation is retained yet. **So the acceptance line's
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
and set aside and the same newest record commit; on a shallow checkout it says
so, fetches the named commits, and takes the set-aside reasons and that newest
commit as the committed file names them.
