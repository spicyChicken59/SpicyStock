# 7 November 2026 — the service through the first morning checks delivered inside their window (#111)

`tools/service_health.py` is a reading of the service and not of the signal;
the [12 October report](2026-10-12-service-health.md) says what it walks and
how, and the [13 October report](2026-10-13-service-health.md) what
`service_health_v3` reads a publication's slots against. This is the same
version run again fifteen sessions after the
[17 October reading](2026-10-17-service-health.md), pinned to `4ad320c2` (the
merge of #215, the 7 November re-read of the signal-outcome study), whose
committer time, 15:05 UTC on 7 November, is its clock. Nothing in the tool's
rules changed; the 17 October reading is kept as it was written and no longer
re-derived. What is new in the history is the morning checks that landed before
their open on 23 October and 3 to 6 November, the weekday source-recovery
receipts that were generated after the open and could recover nothing, the two
empty reader nights of 21 and 22 October and the nights under request v3 from
30 October, and the three reaction tickets the 4 November publication carried.
A record's own clock, `published_at`, is set when its run starts; this reading
calls it the generation time.

## What the history establishes (11 September to 6 November 2026)

- **41 expected sessions, 41 published, 41 of 41 first publications landed
  before the next session's open.** None is missing and none is pending: the
  6 November session completed at 21:15 UTC (the close is 16:00 ET under
  standard time since 1 November) and its publication landed at 02:54 UTC on
  the 7th, before its next open (14:30 UTC on Monday 9 November). Every due
  session has a publication, so the current streak reads 41; the longest is
  41.
- **Fresh: yes.** `main` carries `f1feb636`, the 6 November publication, and
  the newest due session is 6 November's.
- **34 of 41** first publications landed after the retry slot, as 34 were
  generated after it. From 14 to 18 September the scheduled runs landed 9.6 to
  11.7 minutes after the primary slot; from 22 September to 6 November every
  first publication landed after the retry slot, 131.0 to 289.5 minutes after
  the primary one. The fifteen since the 17 October reading landed 171.4,
  145.3, 147.6, 147.0, 146.3, 195.8, 185.0, 214.9, 223.5, 201.5, 285.5, 229.8,
  261.6, 254.3 and 218.4 minutes after it, none among the promptest from 22
  September on, which stay 15 and 16 October's 131.0 and 133.4. The clocks
  changed on 1 November; the winter cron (`16 23`) is the same 6:16 PM ET,
  read in the exchange's zone.
- **Latency after completion, by the landing commit:** min 55.8, median
  300.6, max 410.5 minutes; by the records' own clocks 53.1, 297.2 and 407.2.
  Each commit landed 2.3 to 6.2 minutes after its record's clock.
- **47 publications**; five sessions published more than once (11 and 21
  September, 8, 9 and 19 October), none since: 19 October's second is a second
  publication of that session generated on 20 October (`d179f206`, landed
  17:23 UTC, 1,268.3 minutes after the session's completion), the one that
  named LCU.
  Statuses 30 degraded and 17 ok. Of the sixteen publications since the 17
  October reading, eight are degraded and eight ok: both of 19 October's
  (`claude_unavailable` on the first, `coverage_thin` on the backfill), 21 and
  22 October (`claude_unavailable`: the two empty reader nights, every call
  answered HTTP 400 under the SDK that had moved its API version, #190, the
  records' own error text), 27, 28
  and 29 October (`claude_partial`: replies refused by reader authority under
  request v2) and 30 October (`coverage_thin`: NORD, a stock new to the
  directory, #206); 20, 23 and 26 October and 2 to 6 November are `ok`.
- **Slots:** 21 publications read against the slots their own rules archived
  (12 October to 6 November, each 6:16 and 8:16 PM ET), 26 against the current
  policy's.
- **Reader:** 304 of 358 requested reads done over 47 publications; 21 cost
  blocks archived, the 12 October to 6 November publications' (60 calls, 52
  replies, 411,396 input and 27,998 output tokens, under `claude-sonnet-4-6`),
  sixteen more than the 17 October reading's five; the sixteen new ones
  carry 50 calls and 42 replies. Since
  that reading: under request v2, the ten publications of 19 to 29 October (nine
  sessions, 19 October's twice) got 9 of 22 requested reads (the two empty nights' four calls apiece got no reply;
  the refusal floor of #182 tolerated one refusal of two on 19 October's second
  publication and on 20 October);
  under request v3, from the 30 October publication, 23 of 24 (one refused on
  30 October, CLMT, tolerated; then 4 of 4, 2 of 2, 12 of 12, 2 of 2 and 2 of
  2). Twenty-four reads over six nights is not a rate.
- **The signal, kept apart:** 35 RED and 12 YELLOW publications, 3 reaction
  tickets, 10 anticipation tickets; the three reaction tickets are the 4
  November publication's HQY, RCBC and VIK.
- **Companions, morning:** eight receipts: two `inapplicable` (the 9 October
  one after its window, `entry_window_ended`; the 10 October one on a Saturday,
  `wrong_session`), four `no_tickets`
  (23 October, 2, 4 and 6 November) and two `partial` (3 November, one row;
  5 November, three rows, the published tickets' pre-open quotes, every print
  stale under the 60-second rule). Six of the eight were generated and landed
  before their applicable open. **Five sessions have a morning check that
  landed before the applicable open: 23 October, 3, 4, 5 and 6 November, the
  last four consecutive**, each generated at 14:22 UTC (8:22 CT); the 2
  November check was generated at 14:31 UTC, after the 14:30 open and inside
  the collector's own window (its `entry_phase` reads `open`). #111's count of
  consecutive sessions with a morning check before the open stands at four;
  with any check inside the collector's window, at five (2 to 6 November).
  What dispatched each check is not in the receipts.
- **Companions, issuer:** 31 receipts: seven `unavailable` (all before 17
  October), 17 `partial` and seven `no_candidates`; 28 before their applicable
  open; the newest, for 9 November, `no_candidates`.
- **Companions, research observations:** six: three `no_research_rows` (23
  October, 2 and 4 November), one `partial` (3 November, one row) and two `inapplicable` `cohort_not_current` (5 and 6 November: the cohort on
  `main` was still the 3 November publication's, for 4 November, because the 4
  and 5 November publications' comparisons were refused inside the registered
  period; the 6 November publication's cohort reads `outside_period` for 9
  November).
- **Companions, source recovery:** 19 receipts: six `recovered` (for 19, 20,
  21, 22 and 23 October, 9 November), five `partial` (for 14, 15, 16 and 26
  October, 2 November) and eight `inapplicable` `recovery_window_ended` (for
  27, 28, 29 and 30 October, 3, 4, 5 and 6 November). Eleven of the 19
  landed before their applicable open: every one that recovered or partly
  recovered did, and each `inapplicable` one was generated on a weekday after the applicable open
  (landed 13:32 to 14:38 UTC under daylight time, 15:21 to 15:46 under standard
  time) and says the window had ended and it asked nothing; the four Saturday
  runs (17, 24 and 31 October, 7 November) ran for the Friday publications,
  whose applicable session is the Monday, and recovered or partly recovered.
  Since 27 October no weekday receipt has recovered a bar; which slot's run
  each was, and when GitHub created it, is the schedule-reliability reading's
  question, not this one's.
- 38 commits set aside, each a record that is not a real schema-2 publication
  (the first build's, and five of the second build's fixture from 11 September
  before its first real night), named with the reason in the reading.

## What it does not establish

A landing is the committer time of the commit that put the record on `main`:
the push follows it by seconds and Pages serves it later still, so every
delivery fact here is a lower bound on when a reader could see the record,
never a claim that Pages served it then (the publication gate's log says
when). Nothing here says why a run landed when it did: no run log is read, so
why GitHub created a scheduled run late is the
[13 October schedule-reliability reading's](2026-10-13-schedule-reliability.md)
question. The Railway morning host is not a companion the reading walks, so
nothing here says what it served. A morning receipt's rows are dated prices
and never fills; a recovery receipt's bars are a second ask of the provider
and change no publication. Nothing here is a trading result.

## Known limits, written down rather than worked

- A record archived under a delivery version this code does not re-derive
  (`delivery.VERSION` moving past 1) would be set aside, as `report.validate()`
  refuses it; the version has not moved.
- `delivery.slots()` places both slots on the session's own date, so an
  archived slot past midnight ET would land on the session's morning. The
  current slots are 6:16 and 8:16 PM ET, and no record archives another.
- `slots_et` prints the archived times to the minute, as the rules spell them.

## The earlier readings

The 17 October reading is kept as it was written, no longer re-derived by the
tool: `2026-10-17-service-health-evidence/service-health.{json,md}` are the v3
reading pinned to `426d3c59`. The 13 October reading beside it is the v3
reading pinned to `7e40716e`, and the 12 October one the v2 reading, with
`v1/` holding the first version as `main` carried it before the v2 correction
(`279ec5a3`), both pinned to `c759a1e6`. `tests/test_service_health.py` holds
all eight files, and the three earlier reports, to their git blob identities.

`python tools/service_health.py --check` holds the two files under
`2026-11-07-service-health-evidence/`: it re-reads the commits the JSON names,
fetching exactly those into a shallow checkout, and where the checkout carries
the history walks it again and requires the same commits read and set aside.
