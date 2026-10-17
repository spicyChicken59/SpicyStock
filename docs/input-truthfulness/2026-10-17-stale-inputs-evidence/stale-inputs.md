# Stale inputs read again (stale_inputs_v1)

The history of `origin/main` through `f714fb32`: 31 publications read, 4 source-recovery receipts. Derived by `tools/stale_inputs.py`; `--check` holds this file to the commits named in `stale-inputs.json`.

From 2026-10-07 to 2026-10-16 the newest publication of each of 8 nights named 103 stale stock-sessions (58 stocks): 64 were scanned again by a follow-up on their late bar and would not have been listed; 11 fell under the $3 session-close policy; 20 carry a later bar read only for its volume, under the 100,000-share floor of the 4%, breakdown and $ scans (the setting-up scans not read); 8 have no later bar read by either source. No follow-up reading found a late bar that would have been listed (127 readings). Of the 95 later bars, 93 have zero volume and the largest 2,891 shares. Why a bar was absent is not established.

## Night by night

| Session | Newest publication | Revisions | Run | Tolerance | Stale | Named | Stock-sessions | Measured by a revision |
|---|---|---:|---|---|---:|---:|---:|---:|
| 2026-10-07 | `a8f9a36f` | 1 | degraded | not_tolerated (v1) | 16 | 16 | 16 | 0 |
| 2026-10-08 | `e67f8cba` | 2 | degraded | tolerated (v2) | 1 | 1 | 3 | 21 |
| 2026-10-09 | `43dcb8d7` | 3 | ok | tolerated (v2) | 1 | 1 | 4 | 21 |
| 2026-10-12 | `9936e971` | 1 | ok | tolerated (v2) | 11 | 11 | 15 | 0 |
| 2026-10-13 | `8772006f` | 1 | degraded | not_tolerated (v2) | 16 | 16 | 20 | 0 |
| 2026-10-14 | `16032f05` | 1 | degraded | not_tolerated (v2) | 19 | 19 | 23 | 0 |
| 2026-10-15 | `0f951414` | 1 | degraded | not_tolerated (v2) | 20 | 20 | 24 | 0 |
| 2026-10-16 | `7a1a9e49` | 1 | ok | tolerated (v2) | 18 | 18 | 18 | 0 |

Each night's stock-sessions by class (one named by two nights counts under both):

| Session | would_have_been_listed | scanned_not_listed | under_price_policy | under_volume_floor_unscanned | at_or_above_volume_floor_unscanned | arrived_volume_unread | no_later_bar |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2026-10-07 | 0 | 13 | 2 | 0 | 0 | 0 | 1 |
| 2026-10-08 | 0 | 0 | 0 | 0 | 0 | 0 | 3 |
| 2026-10-09 | 0 | 0 | 0 | 0 | 0 | 0 | 4 |
| 2026-10-12 | 0 | 10 | 0 | 0 | 0 | 0 | 5 |
| 2026-10-13 | 0 | 14 | 1 | 0 | 0 | 0 | 5 |
| 2026-10-14 | 0 | 14 | 3 | 1 | 0 | 0 | 5 |
| 2026-10-15 | 0 | 13 | 5 | 1 | 0 | 0 | 5 |
| 2026-10-16 | 0 | 0 | 0 | 18 | 0 | 0 | 0 |

## Every named stock-session, by what the later readings establish

- a follow-up ran the evening's scans on the late bar and it would have been listed: 0
- a follow-up ran the evening's scans on the late bar, every route, and it would not have been listed: 64
- the late bar's close falls under the $3 session-close policy, which keeps it out of every scan: 11
- a later bar read for its volume only, under the floor of the 4%, breakdown and $ scans; the setting-up scans not read: 20
- a later bar read for its volume only, at or above that floor: 0
- a later bar arrived but its volume could not be read; no scan verdict: 0
- no later bar read by either source: 8

Later bars: 95 (95 with a volume read), 93 at zero volume, the largest 2,891 shares, against the 100,000-share floor of the 4%, breakdown and $ scans (`scans.MIN_VOLUME`, read on the session itself).

Follow-up: 127 readings of 85 stock-sessions; the last reading of each: no_match 64, price_excluded 11, still_missing 3, not_selected 7; matches 0.

Source recovery: 4 receipts (recovered 1, partial 3), 73 stock-sessions read: recovered 70, still_stale 3.

No later bar: 8, 0 not yet read again; the follow-up's last word on the rest: still_missing 3, not_selected 5.

Named on 3 or more nights: WBD (7), NCEW (6), MAYS (5), MDRR (5), HFBL (4), IOR (4), BEBE (3), ELLO (3), FKWL (3), GYRO (3), PFX (3), ROMA (3), WLYB (3).

Set aside, each by name in `stale-inputs.json`: 38 commits, not a real schema-2 publication.
