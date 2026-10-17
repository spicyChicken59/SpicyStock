# 17 October 2026 — the stale stocks, read again

**What this is.** `tools/stale_inputs.py` is a reading, not a check and not a
rule. Since the stale tolerance (#104, #105) every evening record names the
stocks whose frame ended before its session (`run.input_tolerance.names`, and
from its second version where each frame ended), and two later sources read
those stocks again: the next evening's follow-up (`run.stale_followup`), which
re-reads each missed session from that run's own frames and, when the late bar
arrived, is in that run's selection and passes the $3 policy, asks the
evening's own scans, every route, whether it would have been listed; and the
source-recovery receipt (`docs/source-recovery.json`, #165), which asks the
provider once more for the publication's own session before the next open.
Nothing joined the three across nights. The tolerance turns a night with a
degraded input acceptance green on the premise that a late frame hides no
candidate; this reading counts what the later readings establish about that
premise, stock-session by stock-session, and claims only what each source can.
It changes no record, decides nothing and asks no provider anything.

**What it read.** The history of `origin/main` through `f714fb32`
(the merge of #180): 31 real publications read, 38 commits
set aside by name (the first build's records and the second build's fixtures,
none a real schema-2 publication), and 4 source-recovery receipts
(the 13 to 16 October publications'). A rehearsal receipt, or one that does not
say it was no rehearsal, is never read. Each session's NEWEST publication names
its stock-sessions -- every session a named stock missed, as
`followup.missed_sessions()` counts them, at most the record's own
`sessions_max` back; a first-version record (7 October) names each stock at its
own session only, its endings not recorded; the benchmark, named beside the
stocks when its frame is stale, is not one; and a night over the names bound
(none so far) still stands as its session's newest, its stale stocks counted
unnamed. A name an earlier revision of the same session carried and a later one
measured is counted beside the night (`measured_by_revision`), never as a
stock-session. Records before 7 October carry no tolerance block and name
nothing.

## Night by night

| Session | `commit` | Stale | Stock-sessions | Revisions | Run | Tolerance |
|---|---|---:|---:|---:|---|---|
| 2026-10-07 | `a8f9a36f` | 16 | 16 | 1 | degraded | not_tolerated (v1) |
| 2026-10-08 | `e67f8cba` | 1 | 3 | 2 | degraded | tolerated (v2) |
| 2026-10-09 | `43dcb8d7` | 1 | 4 | 3 | ok | tolerated (v2) |
| 2026-10-12 | `9936e971` | 11 | 15 | 1 | ok | tolerated (v2) |
| 2026-10-13 | `8772006f` | 16 | 20 | 1 | degraded | not_tolerated (v2) |
| 2026-10-14 | `16032f05` | 19 | 23 | 1 | degraded | not_tolerated (v2) |
| 2026-10-15 | `0f951414` | 20 | 24 | 1 | degraded | not_tolerated (v2) |
| 2026-10-16 | `7a1a9e49` | 18 | 18 | 1 | ok | tolerated (v2) |

The 8 and 9 October first publications (`1e1ffe9c` at 02:06 UTC on 9 October,
`62bce72d` at 01:44 UTC on 10 October) named 22 stale stocks each; their later
revisions -- ten hours on for 8 October, five and a half for 9 October --
measured 21 of them, and WBD alone stayed stale.

## What the later readings establish

From 2026-10-07 to 2026-10-16 the newest publication of each of 8 nights named 103 stale stock-sessions (58 stocks): 64 were scanned again by a follow-up on their late bar and would not have been listed; 11 fell under the $3 session-close policy; 20 carry a later bar read only for its volume, under the 100,000-share floor of the 4%, breakdown and $ scans (the setting-up scans not read); 8 have no later bar read by either source. No follow-up reading found a late bar that would have been listed (127 readings). Of the 95 later bars, 93 have zero volume and the largest 2,891 shares. Why a bar was absent is not established.

Each stock-session lands in one class, in this order of what its sources can
claim:

- **would have been listed** -- a follow-up found the late bar listed by a
  route: **0**.
- **scanned, not listed** -- the last follow-up reading that gave a verdict
  ran the scans, every route, and none listed the bar (a later reading with no
  verdict, such as a re-run that no longer selected the stock, does not undo
  it): **64**.
- **under the price policy** -- the last verdict was the $3 session-close
  policy, which keeps the bar out of every scan: **11**.
- **volume only, under the floor** -- no follow-up gave a verdict; a later bar
  was read for its volume and nothing else, under the 100,000-share floor
  the 4%, breakdown and $ scans read on the session itself
  (`scans.MIN_VOLUME`): **20**. Those three scans could not have
  listed it; the setting-up scans read the three sessions before (`minv3.1`),
  so volume alone does not settle them. Eighteen of the twenty are the
  16 October night's stocks, which only the 17 October recovery receipt has
  read so far; the next evening's follow-up, Monday 19 October, reads again
  those still in its selection and runs the scans on those that pass the $3
  policy -- FKWL, under it on 14 and 15 October, may not. The other two are
  AZTR (14 October) and TJGC (15 October), out of the following run's
  selection.
- **volume only, at or above the floor**: **0**.
- **arrived, volume unread** -- a later bar arrived but neither source could
  read its volume (a recovery row for an unreadable bar, or a follow-up's
  `unmeasurable` one): **0**.
- **no later bar** -- neither source has read a bar for it: **8**, every
  one WBD, at 6 to 15 October. The follow-up's last reading is `still_missing`
  for 6 to 8 October and `not_selected` for the other five, which the
  16 October run read without WBD in its selection (it left the seed with
  #174 that morning); the recovery found it `still_stale` on each of the three
  receipts that asked (13 to 15 October).

Of the 95 later bars, 93 carry zero volume and the largest is
2,891 shares (GEG, 15 October, a late bar under the price policy);
the only other is NCEW's 237 shares the same day, scanned and not listed.
70 of the 95 are bars the four source-recovery receipts returned, 68 of them at
zero volume; the late bars #104 retained from earlier publications, read by no
receipt here, were zero-volume placeholders too. The follow-up read
85 of the stock-sessions 127 times in all (a re-run of a session
re-reads its previous publication's names), and none of those readings was a
match. The recovery read 73: recovered
70, still stale 3.

Each night's own stock-sessions by class (a stock-session two nights named
counts under both; no other class has a member):

| Session | scanned, not listed | price policy | volume only | no later bar |
|---|---:|---:|---:|---:|
| 2026-10-07 | 13 | 2 | 0 | 1 |
| 2026-10-08 | 0 | 0 | 0 | 3 |
| 2026-10-09 | 0 | 0 | 0 | 4 |
| 2026-10-12 | 10 | 0 | 0 | 5 |
| 2026-10-13 | 14 | 1 | 0 | 5 |
| 2026-10-14 | 14 | 3 | 1 | 5 |
| 2026-10-15 | 13 | 5 | 1 | 5 |
| 2026-10-16 | 0 | 0 | 18 | 0 |

Named on three nights or more: WBD (7), NCEW (6), MAYS (5), MDRR (5), HFBL (4), IOR (4), BEBE (3), ELLO (3), FKWL (3), GYRO (3), PFX (3), ROMA (3), WLYB (3).

## What it means

The late bars a follow-up scanned -- 64 stock-sessions, named on 7 and 12 to
15 October -- included none that would have been listed. 54 of the
64 come from nights the tolerance did not tolerate (7 and 13 to 15 October),
so they test the premise on nights it was not relied on; of the nights it did
tolerate (8, 9, 12 and 16 October), only 12 October's 10 were scanned. On
8 and 9 October the only named stock was WBD, which has no later bar, and the
16 October night's 18 are read so far only for their volume. Another 11 fell
under the $3 policy before any scan, and 93 of the 95 later bars carry zero
volume. That supports the premise over the 64 scanned stock-sessions; it is
not evidence for the nights not yet scanned or for a night to come, and it
says nothing about the setting-up scans for the 20 stock-sessions read only by
their volume. Why a provider returned no bar on a session's evening is not
established here: a placeholder bar that arrives hours later at zero volume is
consistent with a stock that did not trade, and the reading cannot tell that
from a delayed feed.

**Reproduce.** `python tools/stale_inputs.py --check` holds
[`stale-inputs.json`](2026-10-17-stale-inputs-evidence/stale-inputs.json) and
[`stale-inputs.md`](2026-10-17-stale-inputs-evidence/stale-inputs.md) to the
commits the JSON names, fetching exactly those into a shallow checkout and,
where the checkout carries the history, walking it again;
`tests/test_stale_inputs.py` re-derives every class straight off git without
the tool's join, and holds every number in this report to its source. A newer
reading is a new dated directory, never an edit of this one.

**Not claimable:** a cause for any missing bar; the setting-up scans on a bar
read for its volume only; any trading edge.
