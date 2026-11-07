# Service health reading (service_health_v3)

Read from `origin/main` through commit `4ad320c2` (clock 2026-11-07 15:05Z), 47 publications and 38 commits set aside. The service columns say whether and when a publication landed -- the committer time of the commit that put it on `main`, which the push follows by seconds -- with the record's own clock beside it as the minutes from generation to landing; a session's publications are in the history's order; the signal column is the record's own regime and ticket count and is never a service verdict.

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
| 2026-10-13 | yes | yes | 1 | degraded | 2026-10-14 01:15Z | 300.6 | 3.4 | 179.6 | yes | yes | 4760/4776 | 0/2 | red | 0/0 |
| 2026-10-14 | yes | yes | 1 | degraded | 2026-10-15 00:34Z | 259.4 | 3.6 | 138.4 | yes | yes | 4759/4778 | 2/2 | red | 0/0 |
| 2026-10-15 | yes | yes | 1 | degraded | 2026-10-16 00:26Z | 252.0 | 4.7 | 131.0 | yes | yes | 4757/4777 | 1/2 | red | 0/0 |
| 2026-10-16 | yes | yes | 1 | ok | 2026-10-17 00:29Z | 254.4 | 3.1 | 133.4 | yes | yes | 4759/4777 | 2/2 | red | 0/0 |
| 2026-10-19 | yes | yes | 2 | degraded | 2026-10-20 01:07Z | 292.4 | 2.3 | 171.4 | yes | yes | 4754/4771 | 0/2 | red | 0/0 |
| 2026-10-20 | yes | yes | 1 | ok | 2026-10-21 00:41Z | 266.3 | 4.9 | 145.3 | yes | yes | 4745/4772 | 1/2 | red | 0/0 |
| 2026-10-21 | yes | yes | 1 | degraded | 2026-10-22 00:43Z | 268.6 | 3.0 | 147.6 | yes | yes | 4754/4773 | 0/2 | red | 0/0 |
| 2026-10-22 | yes | yes | 1 | degraded | 2026-10-23 00:43Z | 268.0 | 4.6 | 147.0 | yes | yes | 4756/4773 | 0/2 | red | 0/0 |
| 2026-10-23 | yes | yes | 1 | ok | 2026-10-24 00:42Z | 267.3 | 4.2 | 146.3 | yes | yes | 4755/4773 | 2/2 | red | 0/0 |
| 2026-10-26 | yes | yes | 1 | ok | 2026-10-27 01:31Z | 316.8 | 3.6 | 195.8 | yes | yes | 4749/4767 | 2/2 | red | 0/0 |
| 2026-10-27 | yes | yes | 1 | degraded | 2026-10-28 01:21Z | 306.0 | 2.8 | 185.0 | yes | yes | 4752/4769 | 1/2 | yellow | 0/2 |
| 2026-10-28 | yes | yes | 1 | degraded | 2026-10-29 01:50Z | 335.9 | 3.4 | 214.9 | yes | yes | 4752/4770 | 1/2 | yellow | 0/2 |
| 2026-10-29 | yes | yes | 1 | degraded | 2026-10-30 01:59Z | 344.5 | 3.4 | 223.5 | yes | yes | 4756/4770 | 1/4 | yellow | 0/2 |
| 2026-10-30 | yes | yes | 1 | degraded | 2026-10-31 01:37Z | 322.5 | 2.8 | 201.5 | yes | yes | 4752/4769 | 1/2 | red | 0/0 |
| 2026-11-02 | yes | yes | 1 | ok | 2026-11-03 04:01Z | 406.5 | 4.7 | 285.5 | yes | yes | 4754/4769 | 4/4 | yellow | 0/1 |
| 2026-11-03 | yes | yes | 1 | ok | 2026-11-04 03:05Z | 350.8 | 4.1 | 229.8 | yes | yes | 4755/4768 | 2/2 | yellow | 0/0 |
| 2026-11-04 | yes | yes | 1 | ok | 2026-11-05 03:37Z | 382.6 | 6.2 | 261.6 | yes | yes | 4748/4768 | 12/12 | yellow | 3/0 |
| 2026-11-05 | yes | yes | 1 | ok | 2026-11-06 03:30Z | 375.3 | 2.3 | 254.3 | yes | yes | 4751/4770 | 2/2 | red | 0/0 |
| 2026-11-06 | yes | yes | 1 | ok | 2026-11-07 02:54Z | 339.4 | 3.5 | 218.4 | yes | yes | 4754/4771 | 2/2 | red | 0/0 |

## Summary

- expected sessions 41, due 41, published 41, missing 0 (none), pending 0, not yet due 0
- first publications landed before the next open: 41 of 41 (generated before it: 41); landed after the retry slot: 34
- evening slots each publication is read against: 21 the slots its own rules archived; 26 the current policy's, its rules archiving none
- latency after completion, landed, minutes: min 55.8, median 300.6, max 410.5; generated, by the record's own clock: min 53.1, median 297.2, max 407.2
- streak of due sessions published before the next open: current 41, longest 41
- publications 47, re-published sessions 5 (2026-09-11, 2026-09-21, 2026-10-08, 2026-10-09, 2026-10-19), statuses {"degraded": 30, "ok": 17}
- runner time archived: elapsed 8769.7 s, fetch 2856.5 s over 47 publications
- reader: 304 of 358 reads done over 47 publications with a reads block; cost blocks archived: 21 (60 calls, 52 replies, 411,396 input and 27,998 output tokens)
- signal, kept apart: regimes {"red": 35, "yellow": 12}, reaction tickets 3, anticipation tickets 10
- fresh: newest due session 2026-11-06, newest published 2026-11-06, main carries `f1feb636` (session 2026-11-06): yes

## Companion receipts

| kind | landed (UTC) | generated (UTC) | status | reason | applicable session | landed before its open | rows | bound run |
|---|---|---|---|---|---|---|---:|---|
| morning | 2026-10-09 17:11Z | 2026-10-09 17:10Z | inapplicable | entry_window_ended | 2026-10-09 | no | 0 | 37928234562 |
| morning | 2026-10-10 08:57Z | 2026-10-10 08:56Z | inapplicable | wrong_session | 2026-10-12 | yes | 0 | 38034610157 |
| morning | 2026-10-23 13:24Z | 2026-10-23 13:23Z | no_tickets | — | 2026-10-23 | yes | 0 | 39879239067 |
| morning | 2026-11-02 14:32Z | 2026-11-02 14:31Z | no_tickets | — | 2026-11-02 | no | 0 | 41155959854 |
| morning | 2026-11-03 14:23Z | 2026-11-03 14:22Z | partial | — | 2026-11-03 | yes | 1 | 41575117262 |
| morning | 2026-11-04 14:23Z | 2026-11-04 14:22Z | no_tickets | — | 2026-11-04 | yes | 0 | 41764401775 |
| morning | 2026-11-05 14:23Z | 2026-11-05 14:22Z | partial | — | 2026-11-05 | yes | 3 | 41962047048 |
| morning | 2026-11-06 14:23Z | 2026-11-06 14:22Z | no_tickets | — | 2026-11-06 | yes | 0 | 42156635345 |
| issuer_evidence | 2026-10-10 07:36Z | 2026-10-10 07:35Z | unavailable | — | 2026-10-12 | yes | — | 38034610157 |
| issuer_evidence | 2026-10-10 08:58Z | 2026-10-10 08:57Z | unavailable | — | 2026-10-12 | yes | — | 38034610157 |
| issuer_evidence | 2026-10-10 09:19Z | 2026-10-10 09:18Z | unavailable | — | 2026-10-12 | yes | — | 38034610157 |
| issuer_evidence | 2026-10-13 03:07Z | 2026-10-13 03:06Z | unavailable | — | 2026-10-13 | yes | — | 38339720035 |
| issuer_evidence | 2026-10-14 01:17Z | 2026-10-14 01:16Z | unavailable | — | 2026-10-14 | yes | — | 38494353799 |
| issuer_evidence | 2026-10-15 00:36Z | 2026-10-15 00:35Z | unavailable | — | 2026-10-15 | yes | — | 38660383665 |
| issuer_evidence | 2026-10-16 00:28Z | 2026-10-16 00:28Z | unavailable | — | 2026-10-16 | yes | — | 38829043191 |
| issuer_evidence | 2026-10-17 00:31Z | 2026-10-17 00:30Z | no_candidates | — | 2026-10-19 | yes | — | 38986314620 |
| issuer_evidence | 2026-10-20 01:09Z | 2026-10-20 01:08Z | no_candidates | — | 2026-10-20 | yes | — | 39351383749 |
| issuer_evidence | 2026-10-20 17:25Z | 2026-10-20 17:24Z | partial | — | 2026-10-20 | no | — | 39465001509 |
| issuer_evidence | 2026-10-21 00:43Z | 2026-10-21 00:42Z | partial | — | 2026-10-21 | yes | — | 39522265859 |
| issuer_evidence | 2026-10-22 00:45Z | 2026-10-22 00:44Z | partial | — | 2026-10-22 | yes | — | 39701029811 |
| issuer_evidence | 2026-10-23 00:45Z | 2026-10-23 00:44Z | partial | — | 2026-10-23 | yes | — | 39879239067 |
| issuer_evidence | 2026-10-23 13:26Z | 2026-10-23 13:25Z | partial | — | 2026-10-23 | yes | — | 39879239067 |
| issuer_evidence | 2026-10-24 00:44Z | 2026-10-24 00:43Z | partial | — | 2026-10-26 | yes | — | 40045887700 |
| issuer_evidence | 2026-10-27 01:33Z | 2026-10-27 01:33Z | partial | — | 2026-10-27 | yes | — | 40432684287 |
| issuer_evidence | 2026-10-27 13:44Z | 2026-10-27 13:44Z | partial | — | 2026-10-27 | no | — | 40432684287 |
| issuer_evidence | 2026-10-28 01:23Z | 2026-10-28 01:22Z | partial | — | 2026-10-28 | yes | — | 40614157533 |
| issuer_evidence | 2026-10-29 01:53Z | 2026-10-29 01:52Z | partial | — | 2026-10-29 | yes | — | 40802470870 |
| issuer_evidence | 2026-10-30 02:01Z | 2026-10-30 02:00Z | partial | — | 2026-10-30 | yes | — | 40988674329 |
| issuer_evidence | 2026-10-31 01:39Z | 2026-10-31 01:38Z | no_candidates | — | 2026-11-02 | yes | — | 41155959854 |
| issuer_evidence | 2026-11-02 14:33Z | 2026-11-02 14:33Z | no_candidates | — | 2026-11-02 | no | — | 41155959854 |
| issuer_evidence | 2026-11-03 04:04Z | 2026-11-03 04:03Z | partial | — | 2026-11-03 | yes | — | 41575117262 |
| issuer_evidence | 2026-11-03 14:25Z | 2026-11-03 14:24Z | partial | — | 2026-11-03 | yes | — | 41575117262 |
| issuer_evidence | 2026-11-04 03:08Z | 2026-11-04 03:07Z | partial | — | 2026-11-04 | yes | — | 41764401775 |
| issuer_evidence | 2026-11-04 14:25Z | 2026-11-04 14:24Z | partial | — | 2026-11-04 | yes | — | 41764401775 |
| issuer_evidence | 2026-11-05 03:40Z | 2026-11-05 03:39Z | partial | — | 2026-11-05 | yes | — | 41962047048 |
| issuer_evidence | 2026-11-05 14:25Z | 2026-11-05 14:25Z | partial | — | 2026-11-05 | yes | — | 41962047048 |
| issuer_evidence | 2026-11-06 03:32Z | 2026-11-06 03:31Z | no_candidates | — | 2026-11-06 | yes | — | 42156635345 |
| issuer_evidence | 2026-11-06 14:25Z | 2026-11-06 14:24Z | no_candidates | — | 2026-11-06 | yes | — | 42156635345 |
| issuer_evidence | 2026-11-07 02:56Z | 2026-11-07 02:55Z | no_candidates | — | 2026-11-09 | yes | — | 42331176108 |
| research_observations | 2026-10-23 13:24Z | 2026-10-23 13:23Z | no_research_rows | — | 2026-10-23 | yes | 0 | 39879239067 |
| research_observations | 2026-11-02 14:32Z | 2026-11-02 14:31Z | no_research_rows | — | 2026-11-02 | no | 0 | 41155959854 |
| research_observations | 2026-11-03 14:23Z | 2026-11-03 14:22Z | partial | — | 2026-11-03 | yes | 1 | 41575117262 |
| research_observations | 2026-11-04 14:23Z | 2026-11-04 14:22Z | no_research_rows | — | 2026-11-04 | yes | 0 | 41764401775 |
| research_observations | 2026-11-05 14:23Z | 2026-11-05 14:22Z | inapplicable | cohort_not_current | 2026-11-05 | yes | 0 | 41962047048 |
| research_observations | 2026-11-06 14:23Z | 2026-11-06 14:22Z | inapplicable | cohort_not_current | 2026-11-06 | yes | 0 | 42156635345 |
| source_recovery | 2026-10-14 13:04Z | 2026-10-14 13:03Z | partial | — | 2026-10-14 | yes | 16 | 38494353799 |
| source_recovery | 2026-10-15 12:50Z | 2026-10-15 12:50Z | partial | — | 2026-10-15 | yes | 19 | 38660383665 |
| source_recovery | 2026-10-16 12:42Z | 2026-10-16 12:42Z | partial | — | 2026-10-16 | yes | 20 | 38829043191 |
| source_recovery | 2026-10-17 11:44Z | 2026-10-17 11:44Z | recovered | — | 2026-10-19 | yes | 18 | 38986314620 |
| source_recovery | 2026-10-20 12:57Z | 2026-10-20 12:56Z | recovered | — | 2026-10-20 | yes | 17 | 39351383749 |
| source_recovery | 2026-10-21 13:11Z | 2026-10-21 13:10Z | recovered | — | 2026-10-21 | yes | 27 | 39522265859 |
| source_recovery | 2026-10-22 13:11Z | 2026-10-22 13:10Z | recovered | — | 2026-10-22 | yes | 19 | 39701029811 |
| source_recovery | 2026-10-23 12:51Z | 2026-10-23 12:50Z | recovered | — | 2026-10-23 | yes | 17 | 39879239067 |
| source_recovery | 2026-10-24 12:12Z | 2026-10-24 12:11Z | partial | — | 2026-10-26 | yes | 18 | 40045887700 |
| source_recovery | 2026-10-27 13:32Z | 2026-10-27 13:31Z | inapplicable | recovery_window_ended | 2026-10-27 | no | 0 | 40432684287 |
| source_recovery | 2026-10-28 14:26Z | 2026-10-28 14:26Z | inapplicable | recovery_window_ended | 2026-10-28 | no | 0 | 40614157533 |
| source_recovery | 2026-10-29 14:38Z | 2026-10-29 14:37Z | inapplicable | recovery_window_ended | 2026-10-29 | no | 0 | 40802470870 |
| source_recovery | 2026-10-30 14:30Z | 2026-10-30 14:29Z | inapplicable | recovery_window_ended | 2026-10-30 | no | 0 | 40988674329 |
| source_recovery | 2026-10-31 13:50Z | 2026-10-31 13:49Z | partial | — | 2026-11-02 | yes | 17 | 41155959854 |
| source_recovery | 2026-11-03 15:28Z | 2026-11-03 15:27Z | inapplicable | recovery_window_ended | 2026-11-03 | no | 0 | 41575117262 |
| source_recovery | 2026-11-04 15:44Z | 2026-11-04 15:43Z | inapplicable | recovery_window_ended | 2026-11-04 | no | 0 | 41764401775 |
| source_recovery | 2026-11-05 15:46Z | 2026-11-05 15:45Z | inapplicable | recovery_window_ended | 2026-11-05 | no | 0 | 41962047048 |
| source_recovery | 2026-11-06 15:21Z | 2026-11-06 15:20Z | inapplicable | recovery_window_ended | 2026-11-06 | no | 0 | 42156635345 |
| source_recovery | 2026-11-07 14:19Z | 2026-11-07 14:18Z | recovered | — | 2026-11-09 | yes | 17 | 42331176108 |

## Commits read and set aside

- 38 × not a real schema-2 publication
