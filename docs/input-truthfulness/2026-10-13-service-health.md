# 13 October 2026 — the service, read against each publication's own slots (#111, #163)

**Superseded on 17 October by [the same `service_health_v3` reading run again](2026-10-17-service-health.md)**,
pinned to `426d3c59`, four publications later. The files under `2026-10-13-service-health-evidence/` are
kept as they were written, and this report as written apart from this note; `tests/test_service_health.py`
holds all three to their git blob identities. The tool no longer re-derives them, so `--check` below now
holds the 17 October files.

`tools/service_health.py` is a reading of the service and not of the signal;
the [12 October report](2026-10-12-service-health.md) says what it walks and
how. This version, `service_health_v3`, closes the last item of #163: a
publication whose rules archive the evening workflow's slots
(`rules.pipeline.delivery_primary_et` and `delivery_retry_et`, written since
#161 beside `run.delivery`) is read against THOSE slots, not the code's
current ones, so a schedule changed later cannot move where an earlier
publication fell. The archived slots are used only once the record's own
`run.delivery` re-derives from them (`delivery.faults()`, the validator's own
check). Rules that archive the delivery rule beside a record without its block,
and a block beside rules that archive no delivery rule, are a record the
reading cannot place: the commit is set aside by name and does not count as
a publication. Its session reads unpublished only when no other readable
publication exists for it. A record from before the rule archived
no slots and is read against the current policy's, 6:16 and 8:16 PM ET. Each
publication's timing names which (`slot_basis`: `archived` or
`current_policy`) and the wall-clock slots it was read against (`slots_et`);
the session rows carry the basis and the summary counts each.

**Reproduced first**, on `main` as it stood (`7e40716e`), with a synthetic
record of 9 October whose rules archive 7:16 and 9:16 PM ET slots and whose
`run.delivery` re-derives from them, landed at 00:46 UTC on the 10th (8:46 PM
ET): the reading validated the block and then measured it against 22:16 and
00:16 UTC, today's slots, giving 150.0 minutes after the primary slot and
after the retry slot. Read against the slots it archived, 23:16 and 01:16 UTC,
it is 90.0 minutes after the primary slot and before the retry slot. The same
reproduction showed a record whose rules archive the delivery rule and that
carries no block read without a word; it is set aside now. The defect was in the
reading alone: `delivery.faults()` already held each block to the slots its
record archived.

**What it moves over the history: nothing.** No retained publication before
12 October archived slots, and the 12 October one archived 6:16 and 8:16 PM
ET, the current policy's. The v3 reading pinned to the 12 October reading's
commit, `c759a1e6`, is that reading again with the new fields added: every
latency, slot, verdict, order and set-aside is the same.

## What the history establishes (11 September to 13 October 2026)

The reading is pinned to `7e40716e`, the merge of #168, whose committer time,
22:13 UTC on 13 October, is its clock.

- **23 expected sessions, 22 published, 22 of 22 first publications landed
  before the next session's open.** None is missing. The 13 October session is
  pending: it completed at 20:15 UTC and nothing for it had landed on `main`
  at the clock; its next open is 13:30 UTC on 14 October. A pending session is
  due and unpublished, so the current streak reads 0; the longest is 22.
- **Fresh: no.** `main` carries `9936e971`, the 12 October publication; the
  newest due session is 13 October's.
- **15 of 22** first publications landed after the retry slot, as 15 were
  generated after it. From 14 to 18 September the scheduled runs landed 9.6 to
  11.7 minutes after the primary slot; from 22 September to 12 October every
  first publication landed after the retry slot, 137.2 to 289.5 minutes after
  the primary one.
- **Latency after completion, by the landing commit:** min 55.8, median
  283.4, max 410.5 minutes; by the records' own clocks 53.1, 278.6 and 407.2.
  Each commit landed 2.4 to 5.5 minutes after its record's clock.
- **27 publications**; four sessions published more than once (11 and 21
  September, 8 and 9 October). Statuses 19 degraded and 8 ok.
- **Slots:** 1 publication read against the slots its own rules archived (12
  October), 26 against the current policy's.
- **Reader:** 267 of 304 requested reads done over 27 publications; one cost
  block archived, the 12 October publication's: 2 calls, 2 replies, 14,734
  input and 1,357 output tokens.
- **The signal, kept apart:** 21 RED and 6 YELLOW publications, 0 reaction
  tickets, 3 anticipation tickets (each superseded).
- **Companions:** two morning receipts, both `inapplicable`; four issuer
  receipts, all `unavailable`, the newest for 13 October; no research
  observation and no source-recovery receipt. The 12 and 13 October morning
  runs wrote no receipt. GitHub created the 12 October ones hours after their
  slots ([schedule reliability](2026-10-13-schedule-reliability.md)); the 13
  October ones, which that snapshot predates, were created at 19:52, 19:53,
  20:15 and 20:18 UTC (runs 38458332290, 38458466585, 38461411014 and
  38461736889, read off the Actions API and not retained here), and each skipped
  every collection step and its persist job.
- 38 commits set aside, each a record that is not a real schema-2 publication
  (the first build's, and five of the second build's fixture from 11 September
  before its first real night), named with the reason in the reading.

## What it does not establish

A landing is the committer time of the commit that put the record on `main`:
the push follows it by seconds and Pages serves it later still, so every
delivery fact here is a lower bound on when a reader could see the record,
never a claim that Pages served it then (the publication gate's log says
when). Nothing here says why a run landed when it did. No morning check has
been observed, and nothing here is a trading result.

## Known limits, written down rather than worked

- A record archived under a delivery version this code does not re-derive
  (`delivery.VERSION` moving past 1) would be set aside, as `report.validate()`
  refuses it; the version has not moved.
- `delivery.slots()` places both slots on the session's own date, so an
  archived slot past midnight ET would land on the session's morning. The
  current slots are 6:16 and 8:16 PM ET, and no record archives another.
- `slots_et` prints the archived times to the minute, as the rules spell them.

## The earlier readings

The 12 October reading is kept as it was written, no longer re-derived by the
tool: `2026-10-12-service-health-evidence/service-health.{json,md}` are the v2
reading and `v1/` holds the first version as `main` carried it before the v2
correction (`279ec5a3`), both pinned to `c759a1e6`. `tests/test_service_health.py`
holds all four files to their git blob identities.

`python tools/service_health.py --check` holds the two files under
`2026-10-13-service-health-evidence/`: it re-reads the commits the JSON names,
fetching exactly those into a shallow checkout, and where the checkout carries
the history walks it again and requires the same commits read and set aside.
