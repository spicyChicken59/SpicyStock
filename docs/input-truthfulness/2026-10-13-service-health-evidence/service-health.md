# Service health reading (service_health_v3)

Read from `origin/main` through commit `7e40716e` (clock 2026-10-13 22:13Z), 27 publications and 38 commits set aside. The service columns say whether and when a publication landed -- the committer time of the commit that put it on `main`, which the push follows by seconds -- with the record's own clock beside it as the minutes from generation to landing; a session's publications are in the history's order; the signal column is the record's own regime and ticket count and is never a service verdict.

## Expected sessions

| session | due | published | revisions | status | landed at (UTC) | latency after completion (min) | generation to landing (min) | after primary slot (min) | after retry slot | before next open | inputs ready | reads done/requested | regime | tickets (reaction/anticipation) |
|---|---|---|---:|---|---|---:|---:|---:|---|---|---|---|---|---|
| 2026-09-11 | yes | yes | 2 | ok | 2026-09-11 21:10Z | 55.8 | 2.7 | -65.2 | no | yes | — | 12/12 | red | 0/0 |
| 2026-09-14 | yes | yes | 1 | ok | 2026-09-14 22:27Z | 132.7 | 2.8 | 11.7 | no | yes | — | 12/12 | red | 0/0 |
| 2026-09-15 | yes | yes | 1 | ok | 2026-09-15 22:26Z | 131.3 | 3.0 | 10.3 | no | yes | — | 12/12 | red | 0/0 |
| 2026-09-16 | yes | yes | 1 | degraded | 2026-09-16 22:26Z | 131.5 | 3.5 | 10.5 | no | yes | 4771/4795 | 12/12 | red | 0/0 |
| 2026-09-17 | yes | yes | 1 | degraded | 2026-09-17 22:25Z | 130.6 | 3.6 | 9.6 | no | yes | 4775/4794 | 12/12 | red | 0/0 |
| 2026-09-18 | yes | yes | 1 | degraded | 2026-09-18 22:26Z | 131.1 | 3.5 | 10.1 | no | yes | 4774/4793 | 12/12 | red | 0/0 |
| 2026-09-21 | yes | yes | 2 | degraded | 2026-09-21 23:58Z | 223.2 | 3.8 | 102.2 | no | yes | 4776/4796 | 12/12 | red | 0/0 |
| 2026-09-22 | yes | yes | 1 | degraded | 2026-09-23 00:33Z | 258.7 | 4.8 | 137.7 | yes | yes | 4763/4778 | 0/12 | red | 0/0 |
| 2026-09-23 | yes | yes | 1 | degraded | 2026-09-24 00:33Z | 258.2 | 4.2 | 137.2 | yes | yes | 4766/4781 | 11/12 | red | 0/0 |
| 2026-09-24 | yes | yes | 1 | degraded | 2026-09-25 00:37Z | 262.0 | 4.5 | 141.0 | yes | yes | 4763/4779 | 9/12 | red | 0/0 |
| 2026-09-25 | yes | yes | 1 | degraded | 2026-09-26 00:41Z | 266.7 | 4.8 | 145.7 | yes | yes | 4758/4780 | 11/12 | red | 0/0 |
| 2026-09-28 | yes | yes | 1 | degraded | 2026-09-29 01:58Z | 343.9 | 4.5 | 222.9 | yes | yes | 4761/4780 | 11/12 | red | 0/0 |
| 2026-09-29 | yes | yes | 1 | degraded | 2026-09-30 01:21Z | 306.4 | 4.3 | 185.4 | yes | yes | 4767/4781 | 11/12 | red | 0/0 |
| 2026-09-30 | yes | yes | 1 | degraded | 2026-10-01 01:21Z | 306.4 | 4.5 | 185.4 | yes | yes | 4767/4779 | 10/12 | red | 0/0 |
| 2026-10-01 | yes | yes | 1 | degraded | 2026-10-02 01:44Z | 329.9 | 4.8 | 208.9 | yes | yes | 4766/4781 | 12/12 | red | 0/0 |
| 2026-10-02 | yes | yes | 1 | degraded | 2026-10-03 01:15Z | 300.1 | 4.7 | 179.1 | yes | yes | 4767/4781 | 11/12 | red | 0/0 |
| 2026-10-05 | yes | yes | 1 | degraded | 2026-10-06 02:22Z | 367.0 | 4.9 | 246.0 | yes | yes | 4768/4778 | 11/12 | red | 0/0 |
| 2026-10-06 | yes | yes | 1 | degraded | 2026-10-07 01:34Z | 319.9 | 3.8 | 198.8 | yes | yes | 4759/4778 | 4/12 | red | 0/0 |
| 2026-10-07 | yes | yes | 1 | degraded | 2026-10-08 02:00Z | 345.0 | 5.5 | 224.0 | yes | yes | 4759/4775 | 9/12 | red | 0/0 |
| 2026-10-08 | yes | yes | 2 | degraded | 2026-10-09 02:12Z | 357.1 | 5.2 | 236.1 | yes | yes | 4755/4777 | 11/12 | yellow | 0/2 |
| 2026-10-09 | yes | yes | 3 | ok | 2026-10-10 01:49Z | 334.2 | 4.3 | 213.2 | yes | yes | 4753/4775 | 11/12 | yellow | 0/1 |
| 2026-10-12 | yes | yes | 1 | ok | 2026-10-13 03:05Z | 410.5 | 3.3 | 289.5 | yes | yes | 4767/4778 | 2/2 | yellow | 0/0 |
| 2026-10-13 | yes | no (pending) | 0 | — | — | — | — | — | — | — | — | — | — | — |

## Summary

- expected sessions 23, due 23, published 22, missing 0 (none), pending 1, not yet due 0
- first publications landed before the next open: 22 of 22 (generated before it: 22); landed after the retry slot: 15
- evening slots each publication is read against: 1 the slots its own rules archived; 26 the current policy's, its rules archiving none
- latency after completion, landed, minutes: min 55.8, median 283.4, max 410.5; generated, by the record's own clock: min 53.1, median 278.6, max 407.2
- streak of due sessions published before the next open: current 0, longest 22
- publications 27, re-published sessions 4 (2026-09-11, 2026-09-21, 2026-10-08, 2026-10-09), statuses {"degraded": 19, "ok": 8}
- runner time archived: elapsed 5891.3 s, fetch 1391.6 s over 27 publications
- reader: 267 of 304 reads done over 27 publications with a reads block; cost blocks archived: 1 (2 calls, 2 replies, 14,734 input and 1,357 output tokens)
- signal, kept apart: regimes {"red": 21, "yellow": 6}, reaction tickets 0, anticipation tickets 3
- fresh: newest due session 2026-10-13, newest published 2026-10-12, main carries `9936e971` (session 2026-10-12): no

## Companion receipts

| kind | landed (UTC) | generated (UTC) | status | reason | applicable session | landed before its open | rows | bound run |
|---|---|---|---|---|---|---|---:|---|
| morning | 2026-10-09 17:11Z | 2026-10-09 17:10Z | inapplicable | entry_window_ended | 2026-10-09 | no | 0 | 37928234562 |
| morning | 2026-10-10 08:57Z | 2026-10-10 08:56Z | inapplicable | wrong_session | 2026-10-12 | yes | 0 | 38034610157 |
| issuer_evidence | 2026-10-10 07:36Z | 2026-10-10 07:35Z | unavailable | — | 2026-10-12 | yes | — | 38034610157 |
| issuer_evidence | 2026-10-10 08:58Z | 2026-10-10 08:57Z | unavailable | — | 2026-10-12 | yes | — | 38034610157 |
| issuer_evidence | 2026-10-10 09:19Z | 2026-10-10 09:18Z | unavailable | — | 2026-10-12 | yes | — | 38034610157 |
| issuer_evidence | 2026-10-13 03:07Z | 2026-10-13 03:06Z | unavailable | — | 2026-10-13 | yes | — | 38339720035 |
| research_observations | — | — | none retained | — | — | — | — | — |
| source_recovery | — | — | none retained | — | — | — | — | — |

## Commits read and set aside

- 38 × not a real schema-2 publication
