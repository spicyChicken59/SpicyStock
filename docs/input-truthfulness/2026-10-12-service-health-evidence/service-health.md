# Service health reading (service_health_v1)

Read from `origin/main` through commit `c759a1e6` (clock 2026-10-12 01:01Z), 26 publications and 38 commits set aside. The service columns say whether and when a publication landed; the signal column is the record's own regime and ticket count and is never a service verdict.

## Expected sessions

| session | due | published | revisions | status | published at (UTC) | latency after completion (min) | after primary slot (min) | after retry slot | before next open | inputs ready | reads done/requested | regime | tickets (reaction/anticipation) |
|---|---|---|---:|---|---|---:|---:|---|---|---|---|---|---|
| 2026-09-11 | yes | yes | 2 | ok | 2026-09-11 21:08Z | 53.1 | -67.9 | no | yes | — | 12/12 | red | 0/0 |
| 2026-09-14 | yes | yes | 1 | ok | 2026-09-14 22:24Z | 129.8 | 8.8 | no | yes | — | 12/12 | red | 0/0 |
| 2026-09-15 | yes | yes | 1 | ok | 2026-09-15 22:23Z | 128.3 | 7.3 | no | yes | — | 12/12 | red | 0/0 |
| 2026-09-16 | yes | yes | 1 | degraded | 2026-09-16 22:23Z | 128.0 | 7.0 | no | yes | 4771/4795 | 12/12 | red | 0/0 |
| 2026-09-17 | yes | yes | 1 | degraded | 2026-09-17 22:21Z | 127.0 | 6.0 | no | yes | 4775/4794 | 12/12 | red | 0/0 |
| 2026-09-18 | yes | yes | 1 | degraded | 2026-09-18 22:22Z | 127.6 | 6.6 | no | yes | 4774/4793 | 12/12 | red | 0/0 |
| 2026-09-21 | yes | yes | 2 | degraded | 2026-09-21 23:54Z | 219.4 | 98.4 | no | yes | 4776/4796 | 12/12 | red | 0/0 |
| 2026-09-22 | yes | yes | 1 | degraded | 2026-09-23 00:28Z | 253.9 | 132.9 | yes | yes | 4763/4778 | 0/12 | red | 0/0 |
| 2026-09-23 | yes | yes | 1 | degraded | 2026-09-24 00:29Z | 254.0 | 133.0 | yes | yes | 4766/4781 | 11/12 | red | 0/0 |
| 2026-09-24 | yes | yes | 1 | degraded | 2026-09-25 00:32Z | 257.5 | 136.5 | yes | yes | 4763/4779 | 9/12 | red | 0/0 |
| 2026-09-25 | yes | yes | 1 | degraded | 2026-09-26 00:36Z | 261.9 | 140.9 | yes | yes | 4758/4780 | 11/12 | red | 0/0 |
| 2026-09-28 | yes | yes | 1 | degraded | 2026-09-29 01:54Z | 339.4 | 218.4 | yes | yes | 4761/4780 | 11/12 | red | 0/0 |
| 2026-09-29 | yes | yes | 1 | degraded | 2026-09-30 01:17Z | 302.1 | 181.1 | yes | yes | 4767/4781 | 11/12 | red | 0/0 |
| 2026-09-30 | yes | yes | 1 | degraded | 2026-10-01 01:16Z | 301.9 | 180.9 | yes | yes | 4767/4779 | 10/12 | red | 0/0 |
| 2026-10-01 | yes | yes | 1 | degraded | 2026-10-02 01:40Z | 325.1 | 204.1 | yes | yes | 4766/4781 | 12/12 | red | 0/0 |
| 2026-10-02 | yes | yes | 1 | degraded | 2026-10-03 01:10Z | 295.4 | 174.4 | yes | yes | 4767/4781 | 11/12 | red | 0/0 |
| 2026-10-05 | yes | yes | 1 | degraded | 2026-10-06 02:17Z | 362.1 | 241.1 | yes | yes | 4768/4778 | 11/12 | red | 0/0 |
| 2026-10-06 | yes | yes | 1 | degraded | 2026-10-07 01:31Z | 316.1 | 195.1 | yes | yes | 4759/4778 | 4/12 | red | 0/0 |
| 2026-10-07 | yes | yes | 1 | degraded | 2026-10-08 01:54Z | 339.5 | 218.5 | yes | yes | 4759/4775 | 9/12 | red | 0/0 |
| 2026-10-08 | yes | yes | 2 | degraded | 2026-10-09 02:06Z | 351.9 | 230.9 | yes | yes | 4755/4777 | 11/12 | yellow | 0/2 |
| 2026-10-09 | yes | yes | 3 | ok | 2026-10-10 01:44Z | 330.0 | 209.0 | yes | yes | 4753/4775 | 11/12 | yellow | 0/1 |

## Summary

- expected sessions 21, due 21, published 21, missing 0 (none), pending 0, not yet due 0
- first publications before the next open: 21 of 21; after the retry slot: 14
- latency after completion, minutes: min 53.1, median 261.9, max 362.1
- streak of due sessions published before the next open: current 21, longest 21
- publications 26, re-published sessions 4 (2026-09-11, 2026-09-21, 2026-10-08, 2026-10-09), statuses {"degraded": 19, "ok": 7}
- runner time archived: elapsed 5756.3 s, fetch 1335.2 s over 26 publications
- reader: 265 of 302 reads done over 26 publications with a reads block; cost blocks archived: 0 (0 calls, 0 replies, 0 input and 0 output tokens)
- signal, kept apart: regimes {"red": 21, "yellow": 5}, reaction tickets 0, anticipation tickets 3
- fresh: newest due session 2026-10-09, newest published 2026-10-09: yes

## Companion receipts

| kind | landed (UTC) | generated (UTC) | status | reason | applicable session | before its open | rows | bound run |
|---|---|---|---|---|---|---|---:|---|
| morning | 2026-10-09 17:11Z | 2026-10-09 17:10Z | inapplicable | entry_window_ended | 2026-10-09 | no | 0 | 37928234562 |
| morning | 2026-10-10 08:57Z | 2026-10-10 08:56Z | inapplicable | wrong_session | 2026-10-12 | yes | 0 | 38034610157 |
| issuer_evidence | 2026-10-10 07:36Z | 2026-10-10 07:35Z | unavailable | — | 2026-10-12 | yes | — | 38034610157 |
| issuer_evidence | 2026-10-10 08:58Z | 2026-10-10 08:57Z | unavailable | — | 2026-10-12 | yes | — | 38034610157 |
| issuer_evidence | 2026-10-10 09:19Z | 2026-10-10 09:18Z | unavailable | — | 2026-10-12 | yes | — | 38034610157 |
| research_observations | — | — | none retained | — | — | — | — | — |

## Commits read and set aside

- 38 × not a real schema-2 publication
