# Schedule reliability reading (schedule_reliability_v1)

128 scheduled runs of `spicyChicken59/SpicyStock` as the public Actions API listed them at 2026-10-13 18:14Z (snapshot `runs.json`, SHA-256 `17a831a997da7173…`), with each workflow's cron tables as `main` carried them at `3a972ad7`. A delay is the minutes from the cron instant a run was for to the moment GitHub created it -- the scheduler's own, before any step of ours ran. Delays are min / median / max (runs).

## The change

- last run created within 15 minutes of its slot before it: `.github/workflows/secret-scan.yml` `0 6 * * 1` at 2026-09-21 06:00Z, 4.3 min
- first run created more than 60 minutes after its slot: `.github/workflows/evening.yml` `16 22 * * 1-5` at 2026-09-21 22:16Z, 152.2 min
- every run from that slot on: delay 130.6 / 276.5 / 504.9 (71); within 15 min 0; beyond 15 min 71, 60 min 71, 240 min 42, 360 min 13

## The contrast: runs a push to `main` triggered (360)

Minutes from the pushed commit's own timestamp to the run it triggered, an upper bound on that event's delay (a commit made before its push counts the gap).

- every push run: 0.0 / 0.1 / 0.4 (360)
- from the change on: 0.0 / 0.1 / 0.3 (144); within 15 min 144

## .github/workflows/evening.yml

- runs 104; expected slots 104; with no run 0; not started yet 0; runs for a slot no table named 0
- delay, minutes: 5.3 / 173.2 / 389.8 (104); beyond 15 min 66, 60 min 64, 240 min 35, 360 min 6

| cron (UTC) | delay min / median / max (runs) |
|---|---|
| `16 0 * * 2-6` | 13.1 / 286.8 / 387.9 (22) |
| `16 1 * * 2-6` | 10.2 / 310.4 / 389.8 (22) |
| `16 22 * * 1-5` | 5.3 / 132.5 / 285.6 (30) |
| `16 23 * * 1-5` | 7.4 / 132.9 / 259.4 (30) |

| week of (Monday, UTC) | delay min / median / max (runs) |
|---|---|
| 2026-08-31 | 5.3 / 6.8 / 9.5 (8) |
| 2026-09-07 | 5.6 / 9.1 / 13.1 (12) |
| 2026-09-14 | 5.5 / 10.8 / 15.9 (20) |
| 2026-09-21 | 130.6 / 208.3 / 301.5 (20) |
| 2026-09-28 | 164.8 / 257.4 / 356.5 (20) |
| 2026-10-05 | 186.2 / 285.2 / 380.4 (20) |
| 2026-10-12 | 259.4 / 336.8 / 389.8 (4) |

## .github/workflows/morning.yml

- runs 18; expected slots 22; with no run 0; not started yet 4; runs for a slot no table named 0
- delay, minutes: 12.2 / 14.9 / 504.9 (18); beyond 15 min 8, 60 min 4, 240 min 4, 360 min 4

| cron (UTC) | delay min / median / max (runs) |
|---|---|
| `20 13 * * 1-5` | 504.9 / 504.9 / 504.9 (1) |
| `20 14 * * 1-5` | 469.0 / 469.0 / 469.0 (1) |
| `28 13 * * 1-5` | 499.1 / 499.1 / 499.1 (1) |
| `28 14 * * 1-5` | 463.3 / 463.3 / 463.3 (1) |
| `30 12 * * 1-5` | 14.9 / 15.9 / 17.0 (7) |
| `30 13 * * 1-5` | 12.2 / 12.5 / 14.3 (7) |

| week of (Monday, UTC) | delay min / median / max (runs) |
|---|---|
| 2026-08-31 | 12.2 / 13.7 / 15.0 (6) |
| 2026-09-07 | 12.3 / 15.1 / 17.0 (8) |
| 2026-10-12 | 463.3 / 484.1 / 504.9 (4) |

Expected slots not started at the snapshot: `20 13 * * 1-5` at 2026-10-13 13:20Z, `28 13 * * 1-5` at 2026-10-13 13:28Z, `20 14 * * 1-5` at 2026-10-13 14:20Z, `28 14 * * 1-5` at 2026-10-13 14:28Z

## .github/workflows/secret-scan.yml

- runs 6; expected slots 6; with no run 0; not started yet 0; runs for a slot no table named 0
- delay, minutes: 4.2 / 191.3 / 470.0 (6); beyond 15 min 3, 60 min 3, 240 min 3, 360 min 3

| cron (UTC) | delay min / median / max (runs) |
|---|---|
| `0 6 * * 1` | 4.2 / 191.3 / 470.0 (6) |

| week of (Monday, UTC) | delay min / median / max (runs) |
|---|---|
| 2026-09-07 | 4.2 / 4.2 / 4.2 (1) |
| 2026-09-14 | 4.4 / 4.4 / 4.4 (1) |
| 2026-09-21 | 4.3 / 4.3 / 4.3 (1) |
| 2026-09-28 | 378.3 / 378.3 / 378.3 (1) |
| 2026-10-05 | 418.0 / 418.0 / 418.0 (1) |
| 2026-10-12 | 470.0 / 470.0 / 470.0 (1) |

## .github/workflows/source-recovery.yml

- runs 0; expected slots 0; with no run 0; not started yet 0; runs for a slot no table named 0
- delay, minutes: —; beyond 15 min 0, 60 min 0, 240 min 0, 360 min 0
