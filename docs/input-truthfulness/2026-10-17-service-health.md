# 17 October 2026 — the service through the first night under the retired seed (#111)

`tools/service_health.py` is a reading of the service and not of the signal;
the [12 October report](2026-10-12-service-health.md) says what it walks and
how, and the [13 October report](2026-10-13-service-health.md) what
`service_health_v3` reads a publication's slots against. This is the same
version run again four publications later, pinned to `426d3c59` (the issuer
receipt that followed the 16 October publication), whose committer time, 00:31
UTC on 17 October, is its clock. Nothing in the tool's rules changed; the 13
October reading is kept as it was written and no longer re-derived. What is new
in the history is the first evening under the seed that no longer asks for
WBD, the first three source-recovery receipts and four more archived cost
blocks (five in all; the 13 October reading carried the 12 October
publication's). A record's own clock, `published_at`, is set when its run
starts; this reading calls it the generation time.

## What the history establishes (11 September to 16 October 2026)

- **26 expected sessions, 26 published, 26 of 26 first publications landed
  before the next session's open.** None is missing and none is pending: the 16
  October session completed at 20:15 UTC and its publication landed at 00:29
  UTC on the 17th, before its next open (13:30 UTC on Monday 19 October). Every
  due session has a publication, so the current streak reads 26; the longest is
  26.
- **Fresh: yes.** `main` carries `7a1a9e49`, the 16 October publication, and
  the newest due session is 16 October's.
- **19 of 26** first publications landed after the retry slot, as 19 were
  generated after it. From 14 to 18 September the scheduled runs landed 9.6 to
  11.7 minutes after the primary slot; from 22 September to 16 October every
  first publication landed after the retry slot, 131.0 to 289.5 minutes after
  the primary one. The four since the 13 October reading landed 179.6, 138.4,
  131.0 and 133.4 minutes after it: 15 and 16 October's are the two promptest
  from 22 September on, 14 October's the fifth (behind 23 and 22 September's
  137.2 and 137.7), all still after the retry slot.
- **Latency after completion, by the landing commit:** min 55.8, median
  264.4, max 410.5 minutes; by the records' own clocks 53.1, 259.7 and 407.2.
  Each commit landed 2.4 to 5.5 minutes after its record's clock.
- **31 publications**; four sessions published more than once (11 and 21
  September, 8 and 9 October), none since. Statuses 22 degraded and 9 ok. The
  13, 14 and 15 October nights are degraded, each naming WBD, a seed name whose
  last bar is 5 October, past the tolerance's five-session bound (13 October
  carries two refused reader replies beside it, 15 October one); 16 October is
  `ok`, the first night under the seed that no longer asks for WBD, its 18
  stale frames all ending on the previous session and within the tolerance.
- **Slots:** 5 publications read against the slots their own rules archived
  (12 to 16 October, each 6:16 and 8:16 PM ET), 26 against the current
  policy's.
- **Reader:** 272 of 312 requested reads done over 31 publications; five cost
  blocks archived, the 12 to 16 October publications': 10 calls, 10 replies,
  73,439 input and 5,715 output tokens, under `claude-sonnet-4-6`.
- **The signal, kept apart:** 25 RED and 6 YELLOW publications, 0 reaction
  tickets, 3 anticipation tickets (each superseded).
- **Companions:** two morning receipts, both `inapplicable`; eight issuer
  receipts, seven `unavailable` and the newest, for 19 October, `no_candidates`
  (the 16 October publication admitted no plan and listed no setup, so nothing
  was asked of the SEC); three source-recovery receipts, all `partial`, for 14,
  15 and 16 October, each landed before its applicable open (13:04, 12:50 and
  12:42 UTC; the 07:37 slot was created about five hours late each day); no
  research observation. The 13, 14, 15 and 16 October morning runs wrote no
  receipt: GitHub created each day's slots hours late (on 16 October at 17:26,
  17:32, 18:05 and 18:15 UTC, runs 38939668907, 38940441166, 38944618528 and
  38945895892, read off the Actions API and not retained here), and each skipped
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
been observed, and nothing here is a trading result. A `partial` recovery
receipt says the provider returned a bar on a second ask: 52 bars recovered
so far, 50 of them the provider's placeholder (zero volume) and two, GEG's and
NCEW's 15 October bars (recovered on 16 October), carrying 2,891 and 237
shares; the publication a receipt is bound to is unchanged by it.

## Known limits, written down rather than worked

- A record archived under a delivery version this code does not re-derive
  (`delivery.VERSION` moving past 1) would be set aside, as `report.validate()`
  refuses it; the version has not moved.
- `delivery.slots()` places both slots on the session's own date, so an
  archived slot past midnight ET would land on the session's morning. The
  current slots are 6:16 and 8:16 PM ET, and no record archives another.
- `slots_et` prints the archived times to the minute, as the rules spell them.

## The earlier readings

The 13 October reading is kept as it was written, no longer re-derived by the
tool: `2026-10-13-service-health-evidence/service-health.{json,md}` are the v3
reading pinned to `7e40716e`. The 12 October reading beside it is the v2
reading, with `v1/` holding the first version as `main` carried it before the
v2 correction (`279ec5a3`), both pinned to `c759a1e6`.
`tests/test_service_health.py` holds all six files to their git blob
identities.

`python tools/service_health.py --check` holds the two files under
`2026-10-17-service-health-evidence/`: it re-reads the commits the JSON names,
fetching exactly those into a shallow checkout, and where the checkout carries
the history walks it again and requires the same commits read and set aside.
