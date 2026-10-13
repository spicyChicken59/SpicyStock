# The service's failures, rehearsed, and its recovery

Policy `recovery_rehearsal_v1` (version 1). `pipeline.run_evening()` through the suite's doubles (`tests/fakes.py`) over one synthetic market of 14 names plus `SPY`, seed 20261012; the evening workflow's guard (`.github/workflows/evening.yml`, SHA-256 `608e5c0a7569…`) executed as written under a frozen clock. Every failure is injected; nothing here is a live provider, a runner or GitHub.

## Nights

| night | session | clock (UTC) | injected | exit | status | published | previous publication | bars requests (bound) | minute requests (bound) | reader calls (bound) | mails |
|---|---|---|---|---|---|---|---|---|---|---|---|
| clean | 2026-09-04 | 2026-09-04T22:30 | nothing injected | 0 | ok | yes, 2026-09-04 (ok, mail delivered) | none | 1 (≤ 2) | 0 (≤ 0) | 2 (≤ 4) | 1 |
| holiday | — | 2026-09-07T22:30 | nothing injected | 0 | no_session | no | preserved | 0 (≤ 2) | 0 (≤ 0) | 0 (≤ 0) | 0 |
| provider_outage | 2026-09-08 | 2026-09-08T22:30 | the Alpaca double raises ConnectionError('no route to host') on every bars request | 1 | failed | no | preserved | 2 (≤ 2) | 0 (≤ 0) | 0 (≤ 0) | 1 |
| provider_recovered_at_retry | 2026-09-08 | 2026-09-09T00:30 | nothing injected | 0 | ok | yes, 2026-09-08 (ok, mail delivered) | replaced | 1 (≤ 2) | 1 (≤ 2) | 2 (≤ 4) | 1 |
| reader_credit | 2026-09-09 | 2026-09-09T22:30 | the Anthropic double raises the provider's empty-balance error on every call | 2 | degraded | yes, 2026-09-09 (degraded, mail delivered) | replaced | 1 (≤ 2) | 0 (≤ 0) | 1 (≤ 4) | 1 |
| reader_transport | 2026-09-10 | 2026-09-10T22:30 | the Anthropic double raises RuntimeError('upstream connect error or disconnect/reset before headers') on every call | 2 | degraded | yes, 2026-09-10 (degraded, mail delivered) | replaced | 1 (≤ 2) | 0 (≤ 0) | 4 (≤ 4) | 1 |
| email_failed | 2026-09-11 | 2026-09-11T22:30 | the Resend double raises RuntimeError('Resend refused the request') on every send | 3 | degraded | yes, 2026-09-11 (degraded, mail failed) | replaced | 1 (≤ 2) | 0 (≤ 0) | 2 (≤ 4) | 0 |
| stale_feed | 2026-09-14 | 2026-09-14T22:30 | every registered frame, the benchmark's included, is served two sessions stale | 1 | failed | no | preserved | 1 (≤ 2) | 0 (≤ 0) | 0 (≤ 0) | 1 |
| next_session_after_a_missed_night | 2026-09-15 | 2026-09-15T22:30 | nothing injected | 0 | ok | yes, 2026-09-15 (ok, mail delivered) | replaced | 1 (≤ 2) | 0 (≤ 0) | 2 (≤ 4) | 1 |

## What each night did

**clean** — a clean night: every boundary answers. Exit 0, status `ok`. Published 2026-09-04 (ok; reads 2 of 2, verdict complete; 2 reaction and 1 anticipation ticket(s); cover "Trade next session. 2 A-quality bursts."). Mailed: 'Trade next session. 2 A-quality bursts. · 2026-09-04'. 19 file(s) under docs changed.
- guard before: the primary slot (2026-09-04T22:20, `16 22 * * 1-5`): go=true, session 2026-09-04 — Scheduled session 2026-09-04; nominal slot 2026-09-04T22:16:00+00:00
- guard after: the retry slot (2026-09-05T00:20, `16 0 * * 2-6`): go=false — 2026-09-04 is already published

**holiday** — Labor Day: the calendar says no session, so nothing is fetched, asked, written or mailed. Exit 0, status `no_session`. Published nothing. Mailed nothing. 0 file(s) under docs changed.
- guard before: the primary slot (2026-09-07T22:20, `16 22 * * 1-5`): go=false — 2026-09-07 is not an exchange session
- guard after: the retry slot (2026-09-08T00:20, `16 0 * * 2-6`): go=false — 2026-09-07 is not an exchange session

**provider_outage** — the bars endpoint refuses every batch. Exit 1, status `failed`, failed at `session`: `RuntimeError: insufficient usable coverage: 0 of 14 intended stocks; no new publication (no-bars, stale frames, gaps and unfetched names are not non-matches)`. Published nothing. Mailed: 'FAILED — no plan for 2026-09-08'. 0 file(s) under docs changed.
- guard before: the primary slot (2026-09-08T22:20, `16 22 * * 1-5`): go=true, session 2026-09-08 — Scheduled session 2026-09-08; nominal slot 2026-09-08T22:16:00+00:00
- guard after: the retry slot (2026-09-09T00:20, `16 0 * * 2-6`): go=true, session 2026-09-08 — Scheduled session 2026-09-08; nominal slot 2026-09-09T00:16:00+00:00
- guard after: the next session's open, with nothing recovered (2026-09-09T13:30, `16 0 * * 2-6`): go=false — 2026-09-08 recovery expired at the next session open

**provider_recovered_at_retry** — the retry slot, 8:30 PM ET the same evening: the provider answers again. Exit 0, status `ok`. Published 2026-09-08 (ok; reads 2 of 2, verdict complete; 0 reaction and 1 anticipation ticket(s); cover "Nothing qualifies. Keep cash."). Mailed: 'Nothing qualifies. Keep cash. · 2026-09-08'. 15 file(s) under docs changed.
- guard before: the retry slot (2026-09-09T00:20, `16 0 * * 2-6`): go=true, session 2026-09-08 — Scheduled session 2026-09-08; nominal slot 2026-09-09T00:16:00+00:00
- guard after: the retry slot again (2026-09-09T01:00, `16 0 * * 2-6`): go=false — 2026-09-08 is already published
- guard after: a delayed primary event for the same evening (2026-09-09T00:40, `16 22 * * 1-5`): go=false — 2026-09-08 is already published
- guard after: a delayed retry event for the 4 September slot (a synthetic clock, to show the rule) (2026-09-05T06:00, `16 0 * * 2-6`): go=false — A newer session than 2026-09-04 is already published

**reader_credit** — the reader's account has no credit left. Exit 2, status `degraded`; problems claude_unavailable. Published 2026-09-09 (degraded; reads 0 of 2, verdict unavailable; 0 reaction and 1 anticipation ticket(s); cover "No new burst tickets. Reader review incomplete."). Mailed: 'No new burst tickets. Reader review incomplete. · 2026-09-09'. 15 file(s) under docs changed.
- guard before: the primary slot (2026-09-09T22:20, `16 22 * * 1-5`): go=true, session 2026-09-09 — Scheduled session 2026-09-09; nominal slot 2026-09-09T22:16:00+00:00
- guard after: the retry slot (2026-09-10T00:20, `16 0 * * 2-6`): go=false — 2026-09-09 is already published

**reader_transport** — the reader's transport fails on every call. Exit 2, status `degraded`; problems claude_unavailable. Published 2026-09-10 (degraded; reads 0 of 2, verdict unavailable; 0 reaction and 1 anticipation ticket(s); cover "No new burst tickets. Reader review incomplete."). Mailed: 'No new burst tickets. Reader review incomplete. · 2026-09-10'. 15 file(s) under docs changed.
- guard before: the primary slot (2026-09-10T22:20, `16 22 * * 1-5`): go=true, session 2026-09-10 — Scheduled session 2026-09-10; nominal slot 2026-09-10T22:16:00+00:00
- guard after: the retry slot (2026-09-11T00:20, `16 0 * * 2-6`): go=false — 2026-09-10 is already published

**email_failed** — the record publishes and the mail provider refuses the digest. Exit 3, status `degraded`, failed at `email`: `RuntimeError: Resend refused the request`; problems email_failed. Published 2026-09-11 (degraded; reads 2 of 2, verdict complete; 2 reaction and 1 anticipation ticket(s); cover "Trade next session. 2 A-quality bursts."). Mailed nothing. 15 file(s) under docs changed.
- guard before: the primary slot (2026-09-11T22:20, `16 22 * * 1-5`): go=true, session 2026-09-11 — Scheduled session 2026-09-11; nominal slot 2026-09-11T22:16:00+00:00
- guard after: the retry slot (2026-09-12T00:20, `16 0 * * 2-6`): go=false — 2026-09-11 is already published

**stale_feed** — every frame the provider serves ends two sessions back. Exit 1, status `failed`, failed at `session`: `RuntimeError: insufficient usable coverage: 0 of 14 intended stocks; no new publication (no-bars, stale frames, gaps and unfetched names are not non-matches)`. Published nothing. Mailed: 'FAILED — no plan for 2026-09-14'. 0 file(s) under docs changed.
- guard before: the primary slot (2026-09-14T22:20, `16 22 * * 1-5`): go=true, session 2026-09-14 — Scheduled session 2026-09-14; nominal slot 2026-09-14T22:16:00+00:00
- guard after: the retry slot (2026-09-15T00:20, `16 0 * * 2-6`): go=true, session 2026-09-14 — Scheduled session 2026-09-14; nominal slot 2026-09-15T00:16:00+00:00
- guard after: the next session's open, with nothing recovered (2026-09-15T13:30, `16 0 * * 2-6`): go=false — 2026-09-14 recovery expired at the next session open

**next_session_after_a_missed_night** — the night after a missed one: every boundary answers again. Exit 0, status `ok`. Published 2026-09-15 (ok; reads 2 of 2, verdict complete; 2 reaction and 1 anticipation ticket(s); cover "Trade next session. 2 A-quality bursts."). Mailed: 'Trade next session. 2 A-quality bursts. · 2026-09-15'. 15 file(s) under docs changed.
- guard before: the primary slot (2026-09-15T22:20, `16 22 * * 1-5`): go=true, session 2026-09-15 — Scheduled session 2026-09-15; nominal slot 2026-09-15T22:16:00+00:00
- guard after: the retry slot (2026-09-16T00:20, `16 0 * * 2-6`): go=false — 2026-09-15 is already published

## Summary

- 9 nights: 6 published, 2 failed before publishing, 1 skipped by the calendar.
- Sessions published: 2026-09-04, 2026-09-08, 2026-09-09, 2026-09-10, 2026-09-11, 2026-09-15.
- The previous publication's files survived every night that published nothing: yes.
- Bars requests within batches × 2 attempts every night: yes; by night: clean 1, holiday 0, provider_outage 2, provider_recovered_at_retry 1, reader_credit 1, reader_transport 1, email_failed 1, stale_feed 1, next_session_after_a_missed_night 1.
- Minute-bar requests within the plans each night asked for: yes; by night: clean 0, holiday 0, provider_outage 0, provider_recovered_at_retry 1, reader_credit 0, reader_transport 0, email_failed 0, stale_feed 0, next_session_after_a_missed_night 0.
- Reader calls within names × 2 attempts every night: yes; by night: clean 2, holiday 0, provider_outage 0, provider_recovered_at_retry 2, reader_credit 1, reader_transport 4, email_failed 2, stale_feed 0, next_session_after_a_missed_night 2.
- Guard decisions: 10 permitted, 7 refused as already published, 1 refused because a newer session was published, 2 refused as expired at the next open, 2 refused as not a session, 0 other.
- Scheduled slots the guard would have admitted after a publication: 0 (duplicate work). After a failure, before the next open: 2 (recovery).

The exit codes are the pipeline's own (0 clean, 1 failed before publishing, 2 degraded but published, 3 failed after publishing). A night that published nothing is proved by the bytes: every file under docs before the run is byte-identical after it (previous publication `preserved`); a night that published replaced them (`replaced`). Nothing here measures a real provider, a runner's start time or a commit landing.
