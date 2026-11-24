# SpicyStock daily brief: measured Mon 23 Nov 2026, plans for Tue 24 Nov 2026

> This is SpicyStock's daily brief: one evening publication's model output, derived from that publication's record and its pick ledger, with the model-record block the same evening run computed from its own bars carried in (section 10), and from nothing else, for an outside analyst to read in place of the full record.
> Check that it is current before using it: `status` must be `derived`, and the freshness rule in section 2 (`service.freshness_rule`) is applied with your own clock.
> Only the rows in section 5 (`tickets`) are published model tickets. Every other row is research only: its levels are reference arithmetic and SpicyStock offers no order for it.
> SpicyStock places, cancels and observes no order and reads no brokerage account. The owner decides and places every order.

**Model gate RED: size multiplier 0.0; 0 published model tickets for the applicable session.** The record's own cover sentence, written for its model tickets and not an instruction to the reader: "Stand aside."

## 1. Identity and binding

- Measured session: 2026-11-23 (open); plans are for **2026-11-24**, entry window 2026-11-24T09:30:00-05:00 to 2026-11-24T10:00:00-05:00 (America/New_York), full session closes 2026-11-24T16:00:00-05:00.
- Published 2026-11-24T06:58:22.835349+00:00 (run 45344319258, evening); rules version `d14cd717cd8a`.
- Canonical record `data.json`: 12,549,293 bytes, SHA-256 `467fd1f29228a3cb54accf1054a102cee6e67799fbe87b3bc0a8bf76ddb399c2`.
- `picks.json`: 28,615 bytes, SHA-256 `7f232ab84aca7c3438f70c8110325660b3a40a339fb12f30d502883089b146b0`.
- This file renders `brief.json` (249,472 bytes, SHA-256 `416d10b720c9281ca912c350d5bb5dc37c38834bfb5b2272edbab210299b5bc6`).
- Page https://spicychicken59.github.io/SpicyStock/ · record https://spicychicken59.github.io/SpicyStock/data.json · brief https://spicychicken59.github.io/SpicyStock/brief.json and https://spicychicken59.github.io/SpicyStock/brief.md · run log https://github.com/spicyChicken59/SpicyStock/actions/runs/45344319258.

## 2. Service state

- Run status: **degraded**; problems: coverage_thin: stale tolerance not met (other_exceptions): Incomplete input coverage: 4734 of 4753 intended stocks had usable session bars. 0 fetch names were never attempted (fetch counts include the benchmark); s…; mail delivered.
- Delivery: Published 1:58 AM ET on Tue 24 Nov, 583.4 minutes after the measured session's completion (4:15 PM ET); after both scheduled slots (6:16 PM and 8:16 PM ET); before the next session's open (Tue 24 Nov, 9:30 AM ET). (slot `after_retry`, 583.4 minutes after completion).
- Next publication (`service.expected`): the next session is 2026-11-24; it completes at 2026-11-24T16:15:00-05:00; primary slot 2026-11-24T18:16:00-05:00; retry slot 2026-11-24T20:16:00-05:00; recovery limit 2026-11-25T09:30:00-05:00.
- Freshness rule (states: `newest`, `not_due`, `pending`, `late`, `missing`):
  - Freshness is the reader's own computation: this file carries no clock. Compare your own clock, as an instant with its UTC offset, with the instants in `service.expected`, in this order, and stop at the first that holds.
  - 1. Before `completion_at`: `newest`. The next session has not completed, so no record of a later session can exist yet. The same session can still be published again, and a later run can withdraw a ticket: before acting on a ticket, fetch the file again and compare `identity.canonical.sha256` with the copy the plan was built on.
  - 2. Before `primary_slot_at`: `not_due`. The next session has completed and its evening run is not yet due.
  - 3. Before `retry_slot_at`: `pending`. The first scheduled slot has passed and the retry slot has not.
  - 4. Before `recovery_until`: `late`. Both scheduled slots have passed; a delayed run can still publish the next session until that instant.
  - 5. Otherwise: `missing`. The service does not publish a session after the session that follows it has opened. If this is still the newest file the site serves, the next session was not published and every ticket in this file is expired.
  - From step 2 on, fetch the file again before relying on it: a newer one may exist. A field that is null has its reason in `service.expected.unknown`; without the instant a step needs, freshness is unknown and the file is research only.
  - Freshness is not permission. A ticket applies only from `identity.entry_window.opens_at` to its `cutoff_at`; after the cutoff it is over, whatever state this rule gives.
- Morning check: plans are for 2026-11-24; entry window 2026-11-24T09:30:00-05:00 to 2026-11-24T10:00:00-05:00; the morning collection starts at 2026-11-24T09:00:00-05:00. Receipt https://spicychicken59.github.io/SpicyStock/morning.json: A morning receipt belongs to this publication only when its `publication.data_sha256` equals `identity.canonical.sha256`. One generated before `window_opens_at` carries no quote from inside the entry window. The receipt is not part of this file: it lands the next morning, if a morning check runs.
- Inputs: Alpaca `sip`, split-adjusted 1Day bars, read by the run that began 2026-11-24T06:58:22.835349+00:00; 4,734 of 4,753 intended stocks ready (acceptance `degraded`); 3,453 measured, 17 stale.
- Stale tolerance: `not_tolerated` (17 stale against a limit of 47). Stale: CPBI, DDC, DIT, ELLO, GSIW, KELYB, LBTYB, MAYS, MDRR, NCEW, PBHC, PFX, PHOE, RDIB, SORA, TRSG, WLYB.
- Seed: None of the 17 stale stocks is on the seed alone; each is in the directory this run selected from.
- Follow-up: The 2026-11-20 publication's 17 stocks without a 2026-11-20 bar, read again from this run's split-adjusted fetch: 15 now carry a 2026-11-20 bar (15 with zero volume); 14 would not have been listed; 1 falls under the $3 session-close policy; 2 still have no 2026-11-20 bar. A late bar is the bar the provider served at this run's check; it never becomes a signal, plan or ticket.
- Minute bars: No plan's first day needed its minute bars tonight; minute bars are retained for 5 plans' first days.
- What the inputs do not establish: Why a stale stock had no session bar is not established; its session inputs are unknown, not a measured non-match, until a later run reads the session again. These bars are the provider's as read by the run that began at 2026-11-24T06:58:22.835349+00:00; a session's volume can be revised afterwards, and this file does not measure by how much. One price source: nothing cross-checks a close, a volume or a split. Bars are adjusted as `service.inputs.basis.adjustment` says and for nothing else. The universe is the selection named in `service.universe`, as fetched; it does not establish which stocks were listed during the session, and the record does not name the stocks that entered or left since the previous publication.
- Chart reader (claude-sonnet-4-6): 2 of 2 reads accepted, verdict `complete`. Chart reader cost: 2 calls for 2 names, 2 replies; 17,182 input tokens (9,062 uncached, 4,060 written to the cache, 4,060 read from it) and 672 output tokens, under claude-sonnet-4-6. Token counts as the API reported them; the record carries no price.
- Review selection (`account_feasible_first_research_v2`): 0 feasible, 2 requested of 12; selected: YUMC (research_ranked), CTRI (research_rotating).
- Admission: 723 reaction candidates, 346 admitted to the trade band and the chart reads (332 by the 4% scan, 14 by the dollar scan on a range-expansion, higher-volume day); 377 came through the dollar scan alone without one and are research only. Of the 167 mechanical A-band names without a veto, 58 are admitted and 109 are not. Admission is read off the recorded discovery route and the checklist's own range-expansion and volume checks; it is never a grade, and the chart reader never sees a name it stops.
- Earnings and 8-K items (status `not_applicable`): Earnings: no ticket to check.
- Candidate funnel under a RED market: 723 reaction candidates discovered, 0 potentially usable (mechanical grade in the admitted band, no veto, discovery admitted), 0 reaction tickets. Reaction candidates stopped at: 723 market gate: the regime admits no new longs. Anticipation: 871 momentum names, 189 quiet, 8 passing the coil checks, 2 listed, 0 tickets. Listed setups stopped at: 2 market gate: the regime admits no new longs. A stage is where the record's own gates stopped a name; it is not a judgement of the setup and establishes no entry.
- Closest miss: AFG came closest at A 10.0: dollar scan alone, without a range-expansion, higher-volume day: research only, no ticket and no chart read.

## 3. Market regime

- Verdict **RED** for 2026-11-23: size multiplier 0.00; grades the regime admits to a ticket: none. The light is SpicyStock's gate for its own model tickets: an input to weigh, not an instruction to the reader.
- Recorded reason: 10-session ratio 0.45 (1097 up, 2464 down) < 1.0: more breakdowns than breakouts
- Counts over 3,453 measured stocks (4,753 intended, 4,734 with a session bar, 1,281 under the $3.00 session close floor): up 4% 332, down 4% 26; up/down 25% in a quarter 471/992; up/down 25% in a month 87/276; up/down 50% in a month 16/22; up/down 13% in 34 days 966/1,460; 35.2% above the 40-day average.
- Ratios: 5-session 0.43 (619 up, 1,441 down, unrounded 0.4296); 10-session 0.45 (1,097 up, 2,464 down, unrounded 0.4452). The rules compare the rounded number.

All five regime rules, in the order they are asked (universe 3,453 against a reference of 6,500). Count thresholds are the reference count times the stocks measured over the reference universe; that scaling is this project's own. Ratio thresholds are not scaled.

| rule | tier | measured | comparison | threshold tonight | reference | fired | decides | masked |
|---|---|---|---|---|---|---|---|---|
| down4_alarm | red | down4 26 | at or over | 371.9 | 700 of 6,500 | no | no | no |
| ratio_10d_red | red | ratio_10d 0.45 | under | 1 | 1, not scaled | yes | yes | no |
| ratio_5d_red | red | ratio_5d 0.43 | under, with more names down 4% than up 4% today | 0.5 | 0.5, not scaled | no | no | no |
| ratio_10d_yellow | yellow | ratio_10d 0.45 | under | 2 | 2, not scaled | yes | no | yes |
| up50_month_hot | yellow | up50_month 16 | over | 10.6 | 20 of 6,500 | yes | no | yes |

- GREEN needs all five rules quiet: fewer than 371.9 names down 4% today (it is 26); a 10-session ratio at or over 2 (it is 0.45: 1,097 up against 2,464 down); no 5-session ratio under 0.5 with more names down 4% than up 4% today (it is 0.43, with 26 down against 332 up); and no more than 10.6 names up 50% in a month (it is 16).
- Yellow by rounding (more ten-session breakdowns than breakouts while the rounded ratio is not under the red line): no. Near a line: no (the 10-session ratio is -0.55 from the red line and -1.55 from the yellow line; band 0.06, the band is this project's own label bound, the largest later re-reading of a published ratio seen through 17 November 2026; it is not a rule and gates nothing).

Breadth history (the newest 10 sessions of the record's own breadth history, each read again tonight over tonight's stocks: an earlier session's counts can differ from what its own night published): 2026-11-10 81/147 r10 0.99; 2026-11-11 229/49 r10 1.01; 2026-11-12 49/261 r10 0.88; 2026-11-13 71/135 r10 1.01; 2026-11-16 48/431 r10 0.87; 2026-11-17 57/204 r10 0.80; 2026-11-18 158/167 r10 0.61; 2026-11-19 43/340 r10 0.75; 2026-11-20 29/704 r10 0.51; 2026-11-23 332/26 r10 0.45.

## 4. Model account

- Model account (the model's configured sizing assumptions; not a brokerage balance): equity $30,000.00, risk 0.50% a trade, position cap 25.00%, 4 slots.
- Model allocation: next-session tickets would commit $0.00 of the configured $30,000.00; 0 of 4 slots.
- Cut: CART (anticipation, withheld): ticket withheld: at the $59.74 limit, the highest fill the ticket permits, the stop $56.88 is 4.79% away, past his 4% line; the setup stands, the ticket does not
- Cut: OGN (anticipation, no_new_longs): breadth sizes new positions at zero tonight

## 5. Published model tickets (0)

None. The record published no model ticket for the applicable session.

## 6. Admitted trade-band candidates (58 of 167 in the band; 723 discovered)

Definition: reaction candidates whose mechanical grade is in the trade band (A+, A), with no quality veto, that the discovery admission admits; plus any other name with a published ticket or a selected chart review. Order: published tickets, then names selected for a chart review, then the rest; each in the record's rank order (grade, score descending, ticker). Model status: a row is `TICKET` only when the record published a model ticket for it (its order is in `tickets`); every other row is `RESEARCH ONLY: no SpicyStock ticket`. Later gates: the gates after the market gate, re-derived from the row's recorded fields so a RED night does not hide them; passing them is not a ticket: the stop rule, the event registry, sizing and the slot allocation follow, and the market gate stands.

Checklist, the same thresholds for every name. **2** not up two days in a row: up_run <= 1, counting days above +1.0%; veto at 3+ up closes of any size (weight 1.5). **L** linearity of the prior leg: ER >= 0.4 or R2 >= 0.55 (both for A+); failing is a veto (weight 2.0). **Y** young trend: first or second breakout: prior breakouts since the move started <= 1 (0 for A+) (weight 1.5). **N** narrow or negative day before: prior day negative or range < 2.0% (A+: negative and under its 20-session median range) (weight 1.5). **C** consolidation quality: base 3-20 sessions, breakdowns <= 1, giveback <= 0.34, tightness <= 1.0 (A+: 0 breakdowns, 0 bursts inside, giveback <= 0.25, tightness <= 0.7, base volume under the leg's and the 50-session average) (weight 2.0). **H** close near the high: close_pos >= 0.8 and close > open (A+ >= 0.9; partial from 0.7) (weight 1.5). **RE** range expansion: today's range over the largest of the prior 5 >= 1.0 (A+: also over the prior 10) (recorded, no weight). **VOL** higher volume: volume > prior session (A+: rank <= 3 of the last 60); a base over 21 sessions also needs >= 1.5x the 50-session average (recorded, no weight).
Check marks: letter then + (pass at the A+ level), nothing (pass), ~ (partial), x (fail), ? (not measured).

Hold days for a plan entered on the applicable session: day 1 = 2026-11-24, day 2 = 2026-11-25, day 3 = 2026-11-27, day 4 = 2026-11-30, day 5 = 2026-12-01. The model's exit rules (source B Bonde, P this project, T a third party's test): [B] when same or next day, the price reaches the sell-half level (+8% from the planned entry): sell half and move the stop to 25-50 cents under that day's high. [B] when any single day closes at or above the abnormal-close level (+10%): take at least partial profit and move the stop up to protect the rest. [B] when it opens at or above the gap-exit level (+20%) after entry: sell at the open (or pre-market). [B] when the close of day 1: the stop rises to the entry day's low if that is above the stop. [B] when day 3 close: sell at least half at the close. [B] when day 3 closes at or below the planned entry: exit: no follow-through. [P] when from the close of day 3: raise the stop to each day's low (it never moves down). [B] when day 5 close: exit the remainder into strength. [B] when the protective stop at the stop is a stop-market order, live intraday from the moment the buy fills: if it is somehow not filled, exit on any close below it. [T] when day 2 is green: do not move the stop to break-even before day 5 just because it is green (theStrat Lab EP9M backtest: the win rate collapses from 29.8% to 7.25%; delaying to day 5 restores it); the +8% raise above is a different rule.

Page for any ticker here: https://spicychicken59.github.io/SpicyStock/#/explore/bursts/<TICKER> (setting-up names: the same with `setting-up` in place of `bursts`). Near-volume band: 103 of the discovered bursts have a volume within 0.05 of the previous session's (the burst's volume is within this fraction of the previous session's, so its higher-volume check can flip on the provider's later corrections; the bound is this project's own label, not a rule).

### 6a. In detail (16 of 58 listed: every ticket and reviewed name, then the first 14 others)

### YUMC · Yum China Holdings Inc. Common Stock · rank 2 · A+ 10.00 · reviewed · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $50.80 (1.99% from $49.81), open $49.51, high $50.89, low $49.35; volume 2,904,912 (1.74x the prior session, 1.68x its 50-session average), dollar volume $147.6M; 3.8% over its 20-session average; route dollar (dollar_expansion).
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-0.68 · **L+** er=0.66 r2=0.93 leg_sessions=32 leg_gain_pct=28.7 · **Y+** breakouts_in_move=0 sessions_since_move_start=36 gain_since_move_start_pct=27.1 · **N+** prior_day_pct=-0.68 prior_range_pct=1.8 negative=yes narrow=yes median_range_pct=1.9 · **C** base_sessions=4 breakdowns=0 bursts_in_base=0 giveback=0.2 tightness=0.73 base_volume_vs_leg=0.96 base_volume_vs_avg=1.06 · **H+** close_pos=0.94 close_above_open=yes · **RE+** vs_prior_5=1.25 vs_prior_10=1.03 bar_range_pct=3 · **VOL+** volume_vs_prior=1.74 volume_vs_avg50=1.68 volume_rank_60=3 cv_required=no. Base 2026-11-17 to 2026-11-20, $49.80 to $52.30; extension: close 3.8% vs its 20-SMA, 11.6% over 20 sessions.
- Chart reader: accepted, A+ 9.0 (research_ranked); selection blockers: grade_not_admitted.
  - Reader's reason (commentary): The four-session base in the shaded box is visibly tight and orderly, sitting just below the 52 area with no wide or overlapping bars, and the prior 32-session leg from early October is a clean stair-step advance with high linearity (R2=0.93). The signal bar closed near its high (close_pos=0.94), above the open, on volume ranking 3rd of the last 60 sessions, with range expansion over both the prior 5 and 10 bars. All seven A+ sub-checks pass and the chart confirms the mechanical grade.
  - Reader's main risk (commentary): The move is 27% off the October low with the stock pressing into the 52 area where prior August highs created some overhead supply, so follow-through could stall quickly.
  - Reader's entry note (not the ticket): Skip if the open gaps more than 1% above the signal close (~51.3+) or if the first 30 minutes show a fade back below the prior base high near 51.
- Later gates: GREEN band pass, YELLOW band pass, veto pass, admission pass, reader `accepted`; all of them under GREEN yes, under YELLOW yes.
- research levels (derived; no order is offered at them): trigger $50.85; limit $51.40; stop $49.35 (burst_low, 3.99% under the limit); day-2 line $52.83; skip if it opens under $49.78; sell-half $55.41; risk a share at the limit $2.05; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 36 shares, $1,850.40; at the YELLOW size 18 shares, $925.20; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### CTRI · Centuri Holdings Inc. Common Stock · rank 175 · A 8.00, final B · reviewed · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $22.11 (12.12% from $19.72), open $20.70, high $22.18, low $20.36; volume 2,579,123 (1.87x the prior session, 1.24x its 50-session average), dollar volume $57M; 3.6% over its 20-session average; route both (burst_route).
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-6.23 · **L+** er=1 r2=0.8 leg_sessions=5 leg_gain_pct=21.5 · **Y** breakouts_in_move=1 sessions_since_move_start=12 gain_since_move_start_pct=18.6 · **N** prior_day_pct=-6.23 prior_range_pct=7.7 negative=yes narrow=no median_range_pct=4.3 · **Cx** base_sessions=7 breakdowns=1 bursts_in_base=0 giveback=0.78 tightness=1.25 base_volume_vs_leg=0.43 base_volume_vs_avg=0.58 · **H+** close_pos=0.96 close_above_open=yes · **RE** vs_prior_5=1.06 vs_prior_10=0.9 bar_range_pct=8.2 · **VOL** volume_vs_prior=1.87 volume_vs_avg50=1.24 volume_rank_60=12 cv_required=no. Base 2026-11-12 to 2026-11-20, $19.55 to $23.34; extension: close 3.6% vs its 20-SMA, 9.8% over 20 sessions; prior breakouts worked 3 of 4 (closed higher 3 sessions later, last 4 in 60 sessions); first leg of 21.5% in 5 sessions: his '15% plus in 10 days or less'.
- Chart reader: accepted, B 6.5 (research_rotating); selection blockers: grade_not_admitted.
  - Reader's reason (commentary): The single most decisive flaw is the recorded C FAIL: the base gave back 0.78 of the prior leg (threshold 0.34) and tightness measured 1.25 against a 1.0 ceiling, meaning the seven-session consolidation visible in the shaded box is wide and overlapping rather than the tight, shallow pause Bonde requires. The signal bar itself is honest — closing at 96% of its range above the open — and the prior leg is genuinely linear (ER 1.0, R² 0.8 in five sessions), but the loose base is a clear, measured quality defect that prevents an A grade.
  - Reader's main risk (commentary): A base that gave back 78% of the leg with above-average tightness means the consolidation lacked the orderly compression needed for reliable follow-through.
  - Reader's entry note (not the ticket): Skip if the open gaps above the prior session's high or if the first 30 minutes show a fade back below the burst day's midpoint (~21.40).
- Later gates: GREEN band fail, YELLOW band fail, veto pass, admission pass, reader `accepted`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $22.13; limit $22.15; stop $21.27 (half_range, 3.97% under the limit); day-2 line $22.99; skip if it opens under $21.67; sell-half $23.92; risk a share at the limit $0.88; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 85 shares, $1,882.75; at the YELLOW size 42 shares, $930.30; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### OMC · Omnicom Group Inc. Common Stock · rank 11 · A 10.00 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $87.32 (2.51% from $85.18), open $85.46, high $87.60, low $84.47; volume 3,020,579 (1.25x the prior session, 1.03x its 50-session average), dollar volume $263.8M; 2.1% over its 20-session average; route dollar (dollar_expansion).
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-0.46 · **L** er=0.36 r2=0.87 leg_sessions=32 leg_gain_pct=17.9 · **Y** breakouts_in_move=1 sessions_since_move_start=38 gain_since_move_start_pct=18.6 · **N** prior_day_pct=-0.46 prior_range_pct=3.2 negative=yes narrow=no median_range_pct=2.8 · **C** base_sessions=6 breakdowns=0 bursts_in_base=0 giveback=0.28 tightness=0.84 base_volume_vs_leg=0.97 base_volume_vs_avg=0.89 · **H+** close_pos=0.91 close_above_open=yes · **RE+** vs_prior_5=1.12 vs_prior_10=1.06 bar_range_pct=3.6 · **VOL** volume_vs_prior=1.25 volume_vs_avg50=1.03 volume_rank_60=16 cv_required=no. Base 2026-11-13 to 2026-11-20, $85.04 to $89.43; extension: close 2.1% vs its 20-SMA, 9.4% over 20 sessions; prior breakouts worked 2 of 2 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $87.41; limit $87.98; stop $84.47 (burst_low, 3.99% under the limit); day-2 line $90.81; skip if it opens under $85.57; sell-half $95.02; risk a share at the limit $3.51; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 21 shares, $1,847.58; at the YELLOW size 10 shares, $879.80; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### AXGN · Axogen Inc. Common Stock · rank 17 · A 8.50 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $58.66 (5.22% from $55.75), open $56.92, high $58.87, low $56.02; volume 1,108,225 (1.26x the prior session, 0.66x its 50-session average), dollar volume $65M; 12.3% over its 20-session average; route both (burst_route); flags biotech.
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-1.06 · **L+** er=0.76 r2=0.85 leg_sessions=19 leg_gain_pct=69.4 · **Yx** breakouts_in_move=2 sessions_since_move_start=26 gain_since_move_start_pct=69.4 · **N+** prior_day_pct=-1.06 prior_range_pct=3.4 negative=yes narrow=no median_range_pct=4.3 · **C** base_sessions=7 breakdowns=1 bursts_in_base=0 giveback=0.23 tightness=0.92 base_volume_vs_leg=0.77 base_volume_vs_avg=0.94 · **H+** close_pos=0.93 close_above_open=yes · **RE** vs_prior_5=1.09 vs_prior_10=0.32 bar_range_pct=4.9 · **VOL** volume_vs_prior=1.26 volume_vs_avg50=0.66 volume_rank_60=39 cv_required=no. Base 2026-11-12 to 2026-11-20, $53.87 to $59.72; extension: close 12.3% vs its 20-SMA, 54.3% over 20 sessions; prior breakouts worked 1 of 2 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $58.72; limit $59.84; stop $57.45 (half_range, 3.99% under the limit); day-2 line $61.01; skip if it opens under $57.49; sell-half $63.99; risk a share at the limit $2.39; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 31 shares, $1,855.04; at the YELLOW size 15 shares, $897.60; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### IRWD · Ironwood Pharmaceuticals Inc. Class A Common Stock · rank 23 · A 8.50 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $4.95 (5.32% from $4.70), open $4.80, high $4.98, low $4.59; volume 4,136,492 (1.37x the prior session, 1.76x its 50-session average), dollar volume $20.5M; 14.7% over its 20-session average; route burst (burst_route); flags biotech.
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-0.21 · **L+** er=0.97 r2=0.93 leg_sessions=9 leg_gain_pct=40.2 · **Yx** breakouts_in_move=2 sessions_since_move_start=15 gain_since_move_start_pct=43.1 · **N** prior_day_pct=-0.21 prior_range_pct=4.7 negative=yes narrow=no median_range_pct=4.7 · **C** base_sessions=6 breakdowns=0 bursts_in_base=0 giveback=0.28 tightness=0.82 base_volume_vs_leg=0.83 base_volume_vs_avg=1.23 · **H+** close_pos=0.92 close_above_open=yes · **RE** vs_prior_5=1.58 vs_prior_10=0.88 bar_range_pct=7.9 · **VOL** volume_vs_prior=1.37 volume_vs_avg50=1.76 volume_rank_60=5 cv_required=no. Base 2026-11-13 to 2026-11-20, $4.56 to $5.00; extension: close 14.7% vs its 20-SMA, 41.4% over 20 sessions; price under $5: explosive, wider stops; prior breakouts worked 4 of 4 (closed higher 3 sessions later, last 4 in 60 sessions); first leg of 40.2% in 9 sessions: his '15% plus in 10 days or less'.
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $4.97; limit $4.98; stop $4.79 (half_range, 3.82% under the limit); day-2 line $5.15; skip if it opens under $4.85; sell-half $5.38; risk a share at the limit $0.19; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 394 shares, $1,962.12; at the YELLOW size 197 shares, $981.06; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### KOD · Kodiak Sciences Inc Common Stock · rank 24 · A 8.50 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $105.53 (8.60% from $97.17), open $102.22, high $106.06, low $100.00; volume 971,690 (1.40x the prior session, 0.46x its 50-session average), dollar volume $102.5M; 4.8% over its 20-session average; route both (burst_route); flags biotech.
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-0.75 · **L** er=0.45 r2=0.33 leg_sessions=38 leg_gain_pct=252.8 · **Yx** breakouts_in_move=4 sessions_since_move_start=43 gain_since_move_start_pct=234.8 · **N+** prior_day_pct=-0.75 prior_range_pct=4.5 negative=yes narrow=no median_range_pct=5.8 · **C** base_sessions=5 breakdowns=1 bursts_in_base=0 giveback=0.22 tightness=0.98 base_volume_vs_leg=0.3 base_volume_vs_avg=0.36 · **H+** close_pos=0.91 close_above_open=yes · **REx** vs_prior_5=0.56 vs_prior_10=0.56 bar_range_pct=5.7 · **VOL** volume_vs_prior=1.4 volume_vs_avg50=0.46 volume_rank_60=32 cv_required=no. Base 2026-11-16 to 2026-11-20, $94.62 to $112.79; extension: close 4.8% vs its 20-SMA, 17.8% over 20 sessions; prior breakouts worked 3 of 4 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $105.64; limit $107.32; stop $103.03 (half_range, 4.00% under the limit); day-2 line $109.75; skip if it opens under $103.42; sell-half $115.12; risk a share at the limit $4.29; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 17 shares, $1,824.44; at the YELLOW size 8 shares, $858.56; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### NABL · N-able Inc. Common Stock · rank 26 · A 8.50 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $5.06 (8.35% from $4.67), open $4.79, high $5.07, low $4.75; volume 1,545,780 (1.09x the prior session, 0.74x its 50-session average), dollar volume $7.8M; 2.7% over its 20-session average; route burst (burst_route).
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-3.51 · **L** er=0.32 r2=0.88 leg_sessions=56 leg_gain_pct=67.9 · **Yx** breakouts_in_move=2 sessions_since_move_start=58 gain_since_move_start_pct=32.5 · **N** prior_day_pct=-3.51 prior_range_pct=4.7 negative=yes narrow=no median_range_pct=4.5 · **C** base_sessions=17 breakdowns=0 bursts_in_base=0 giveback=0.32 tightness=0.84 base_volume_vs_leg=0.64 base_volume_vs_avg=0.76 · **H+** close_pos=0.97 close_above_open=yes · **RE+** vs_prior_5=1.15 vs_prior_10=1.15 bar_range_pct=6.3 · **VOL** volume_vs_prior=1.09 volume_vs_avg50=0.74 volume_rank_60=38 cv_required=no. Base 2026-10-29 to 2026-11-20, $4.56 to $5.31; extension: close 2.7% vs its 20-SMA, -1.7% over 20 sessions; prior breakouts worked 4 of 4 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $5.08; limit $5.11; stop $4.91 (half_range, 3.91% under the limit); day-2 line $5.26; skip if it opens under $4.96; sell-half $5.52; risk a share at the limit $0.20; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 375 shares, $1,916.25; at the YELLOW size 187 shares, $955.57; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### TOP · TOP Financial Group Limited Class A Ordinary Shares · rank 30 · A 8.50 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $17.30 (10.12% from $15.71), open $15.69, high $17.36, low $14.73; volume 205,179 (1.27x the prior session, 1.16x its 50-session average), dollar volume $3.5M; 18.4% over its 20-session average; route both (burst_route); flags foreign.
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-7.53 · **L+** er=0.64 r2=0.81 leg_sessions=9 leg_gain_pct=53 · **Yx** breakouts_in_move=3 sessions_since_move_start=13 gain_since_move_start_pct=59.7 · **N** prior_day_pct=-7.53 prior_range_pct=11.4 negative=yes narrow=no median_range_pct=9.5 · **C** base_sessions=4 breakdowns=1 bursts_in_base=0 giveback=0.33 tightness=1 base_volume_vs_leg=1.05 base_volume_vs_avg=1.47 · **H+** close_pos=0.98 close_above_open=yes · **RE** vs_prior_5=1.31 vs_prior_10=0.88 bar_range_pct=15.2 · **VOL** volume_vs_prior=1.27 volume_vs_avg50=1.16 volume_rank_60=19 cv_required=no. Base 2026-11-17 to 2026-11-20, $15.55 to $17.99; extension: close 18.4% vs its 20-SMA, 13.4% over 20 sessions; prior breakouts worked 3 of 4 (closed higher 3 sessions later, last 4 in 60 sessions); first leg of 53.0% in 9 sessions: his '15% plus in 10 days or less'.
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $17.32; ticket withheld (no_room_above_the_trigger): no limit above the trigger keeps a structural stop inside the stop line; day-2 line $17.99; skip if it opens under $16.95.
- Plan rule refusal: ticket withheld: no limit above the $17.32 buy stop keeps a stop inside his 4% line — the burst day's low $14.73 caps the limit at $15.34, at or under that buy stop; the bar's midpoint $16.05 caps the limit at $16.71, at or under that buy stop; the setup stands, the ticket does not
- No ticket: market gate: the regime admits no new longs (stage `market`).

### VRDN · Viridian Therapeutics Inc. Common Stock · rank 32 · A 8.50 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $31.89 (6.44% from $29.96), open $30.92, high $32.09, low $30.49; volume 2,221,078 (1.27x the prior session, 0.91x its 50-session average), dollar volume $70.8M; 11.6% over its 20-session average; route both (burst_route); flags biotech.
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-4.71 · **L+** er=0.76 r2=0.96 leg_sessions=22 leg_gain_pct=71.5 · **Yx** breakouts_in_move=4 sessions_since_move_start=29 gain_since_move_start_pct=75 · **N** prior_day_pct=-4.71 prior_range_pct=6.3 negative=yes narrow=no median_range_pct=4.3 · **C** base_sessions=7 breakdowns=1 bursts_in_base=1 giveback=0.17 tightness=0.95 base_volume_vs_leg=0.69 base_volume_vs_avg=0.84 · **H** close_pos=0.87 close_above_open=yes · **REx** vs_prior_5=0.79 vs_prior_10=0.79 bar_range_pct=5 · **VOL** volume_vs_prior=1.27 volume_vs_avg50=0.91 volume_rank_60=19 cv_required=no. Base 2026-11-12 to 2026-11-20, $29.25 to $31.63; extension: close 11.6% vs its 20-SMA, 36.6% over 20 sessions; prior breakouts worked 3 of 3 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $31.92; limit $32.59; stop $31.29 (half_range, 3.99% under the limit); day-2 line $33.17; skip if it opens under $31.25; sell-half $34.79; risk a share at the limit $1.30; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 57 shares, $1,857.63; at the YELLOW size 28 shares, $912.52; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### WM · Waste Management Inc. Common Stock · rank 33 · A 8.50 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $240.59 (0.40% from $239.63), open $235.44, high $241.05, low $235.25; volume 2,684,814 (1.08x the prior session, 1.17x its 50-session average), dollar volume $645.9M; 1.0% over its 20-session average; route dollar (dollar_expansion).
- Checks: **2+** up_run=0 up_closes=1 prior_day_pct=0.4 · **L+** er=0.46 r2=0.84 leg_sessions=26 leg_gain_pct=19.5 · **Y** breakouts_in_move=1 sessions_since_move_start=37 gain_since_move_start_pct=19.2 · **Nx** prior_day_pct=0.4 prior_range_pct=2.1 negative=no narrow=no median_range_pct=1.6 · **C** base_sessions=11 breakdowns=0 bursts_in_base=0 giveback=0.29 tightness=0.98 base_volume_vs_leg=0.76 base_volume_vs_avg=0.84 · **H+** close_pos=0.92 close_above_open=yes · **RE+** vs_prior_5=1.14 vs_prior_10=1.14 bar_range_pct=2.4 · **VOL** volume_vs_prior=1.08 volume_vs_avg50=1.17 volume_rank_60=12 cv_required=no. Base 2026-11-06 to 2026-11-20, $233.76 to $247.40; extension: close 1.0% vs its 20-SMA, -0.2% over 20 sessions; prior breakouts worked 0 of 1 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $240.83; limit $245.05; stop $235.25 (burst_low, 4.00% under the limit); day-2 line $250.21; skip if it opens under $235.78; sell-half $262.44; risk a share at the limit $9.80; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 7 shares, $1,715.35; at the YELLOW size 3 shares, $735.15; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### ALK · Alaska Air Group Inc. Common Stock · rank 38 · A 8.00 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $37.12 (10.05% from $33.73), open $35.36, high $37.29, low $34.89; volume 4,781,569 (1.16x the prior session, 1.32x its 50-session average), dollar volume $177.5M; -1.9% over its 20-session average; route both (burst_route).
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-5.89 · **L+** er=0.46 r2=0.88 leg_sessions=15 leg_gain_pct=23.9 · **Y** breakouts_in_move=1 sessions_since_move_start=23 gain_since_move_start_pct=10.7 · **N** prior_day_pct=-5.89 prior_range_pct=8.6 negative=yes narrow=no median_range_pct=3.8 · **Cx** base_sessions=8 breakdowns=3 bursts_in_base=0 giveback=0.89 tightness=1.17 base_volume_vs_leg=0.7 base_volume_vs_avg=0.81 · **H+** close_pos=0.93 close_above_open=yes · **REx** vs_prior_5=0.76 vs_prior_10=0.76 bar_range_pct=6.5 · **VOL** volume_vs_prior=1.16 volume_vs_avg50=1.32 volume_rank_60=5 cv_required=no. Base 2026-11-11 to 2026-11-20, $33.47 to $42.35; extension: close -1.9% vs its 20-SMA, 6.2% over 20 sessions; prior breakouts worked 3 of 4 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $37.16; limit $37.59; stop $36.09 (half_range, 3.99% under the limit); day-2 line $38.60; skip if it opens under $36.38; sell-half $40.49; risk a share at the limit $1.50; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 50 shares, $1,879.50; at the YELLOW size 25 shares, $939.75; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### ALKT · Alkami Technology Inc. Common Stock · rank 39 · A 8.00 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $13.34 (6.63% from $12.51), open $13.05, high $13.35, low $12.67; volume 1,441,014 (1.04x the prior session, inside the near-volume band, 0.68x its 50-session average), dollar volume $19.2M; -2.1% over its 20-session average; route burst (burst_route).
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-1.03 · **L** er=0.51 r2=0.52 leg_sessions=19 leg_gain_pct=19.9 · **Y** breakouts_in_move=1 sessions_since_move_start=16 gain_since_move_start_pct=7.6 · **N+** prior_day_pct=-1.03 prior_range_pct=2.8 negative=yes narrow=no median_range_pct=3.8 · **Cx** base_sessions=20 breakdowns=2 bursts_in_base=2 giveback=1.38 tightness=1.2 base_volume_vs_leg=1.02 base_volume_vs_avg=0.95 · **H+** close_pos=0.99 close_above_open=yes · **REx** vs_prior_5=0.71 vs_prior_10=0.71 bar_range_pct=5.1 · **VOL** volume_vs_prior=1.05 volume_vs_avg50=0.68 volume_rank_60=32 cv_required=no. Base 2026-10-26 to 2026-11-20, $12.10 to $16.10; extension: close -2.1% vs its 20-SMA, -15.1% over 20 sessions; prior breakouts worked 2 of 4 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $13.36; limit $13.55; stop $13.01 (half_range, 3.99% under the limit); day-2 line $13.87; skip if it opens under $13.07; sell-half $14.55; risk a share at the limit $0.54; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 138 shares, $1,869.90; at the YELLOW size 69 shares, $934.95; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### ALNY · Alnylam Pharmaceuticals Inc. Common Stock · rank 40 · A 8.00 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $155.98 (8.46% from $143.82), open $149.69, high $156.65, low $146.85; volume 3,363,122 (1.44x the prior session, 1.54x its 50-session average), dollar volume $524.6M; -5.3% over its 20-session average; route both (burst_route); flags biotech.
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-2.71 · **L** er=0.23 r2=0.67 leg_sessions=43 leg_gain_pct=23.6 · **Y+** breakouts_in_move=0 sessions_since_move_start=1 gain_since_move_start_pct=8.5 · **N** prior_day_pct=-2.71 prior_range_pct=5.6 negative=yes narrow=no median_range_pct=5 · **Cx** base_sessions=38 breakdowns=6 bursts_in_base=3 giveback=1.92 tightness=1.08 base_volume_vs_leg=1.27 base_volume_vs_avg=1.13 · **H+** close_pos=0.93 close_above_open=yes · **REx** vs_prior_5=0.97 vs_prior_10=0.97 bar_range_pct=6.3 · **VOL** volume_vs_prior=1.44 volume_vs_avg50=1.54 volume_rank_60=8 cv_required=yes. Base 2026-09-30 to 2026-11-20, $143.40 to $257.27; extension: close -5.3% vs its 20-SMA, -31.5% over 20 sessions; prior breakouts worked 0 of 4 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $156.14; limit $158.07; stop $151.75 (half_range, 4.00% under the limit); day-2 line $162.22; skip if it opens under $152.86; sell-half $170.14; risk a share at the limit $6.32; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 11 shares, $1,738.77; at the YELLOW size 5 shares, $790.35; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### ALSN · Allison Transmission Holdings Inc. Common Stock · rank 42 · A 8.00 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $122.14 (5.06% from $116.26), open $121.21, high $122.45, low $118.70; volume 588,830 (1.25x the prior session, 0.75x its 50-session average), dollar volume $71.9M; 2.3% over its 20-session average; route both (burst_route).
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-4.93 · **L+** er=0.66 r2=0.89 leg_sessions=14 leg_gain_pct=22.4 · **Y** breakouts_in_move=1 sessions_since_move_start=21 gain_since_move_start_pct=14.9 · **N** prior_day_pct=-4.93 prior_range_pct=5.9 negative=yes narrow=no median_range_pct=2.8 · **Cx** base_sessions=7 breakdowns=1 bursts_in_base=0 giveback=0.61 tightness=1.16 base_volume_vs_leg=0.66 base_volume_vs_avg=0.77 · **H+** close_pos=0.92 close_above_open=yes · **REx** vs_prior_5=0.53 vs_prior_10=0.53 bar_range_pct=3.1 · **VOL** volume_vs_prior=1.25 volume_vs_avg50=0.75 volume_rank_60=44 cv_required=no. Base 2026-11-12 to 2026-11-20, $115.62 to $131.54; extension: close 2.3% vs its 20-SMA, 13.9% over 20 sessions; prior breakouts worked 2 of 3 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $122.26; limit $123.64; stop $118.70 (burst_low, 4.00% under the limit); day-2 line $127.03; skip if it opens under $119.70; sell-half $133.23; risk a share at the limit $4.94; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 15 shares, $1,854.60; at the YELLOW size 7 shares, $865.48; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### APOG · Apogee Enterprises Inc. Common Stock · rank 46 · A 8.00 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $45.37 (4.47% from $43.43), open $44.81, high $45.71, low $43.67; volume 271,418 (1.06x the prior session, 0.85x its 50-session average), dollar volume $12.3M; -1.7% over its 20-session average; route burst (burst_route).
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-1.81 · **L+** er=0.48 r2=0.87 leg_sessions=29 leg_gain_pct=35.8 · **Y+** breakouts_in_move=0 sessions_since_move_start=38 gain_since_move_start_pct=28.3 · **N** prior_day_pct=-1.81 prior_range_pct=4.1 negative=yes narrow=no median_range_pct=3 · **Cx** base_sessions=9 breakdowns=0 bursts_in_base=0 giveback=0.43 tightness=0.98 base_volume_vs_leg=0.67 base_volume_vs_avg=0.75 · **H** close_pos=0.83 close_above_open=yes · **RE** vs_prior_5=1.07 vs_prior_10=0.71 bar_range_pct=4.5 · **VOL** volume_vs_prior=1.06 volume_vs_avg50=0.85 volume_rank_60=33 cv_required=no. Base 2026-11-10 to 2026-11-20, $43.11 to $49.50; extension: close -1.7% vs its 20-SMA, 2.9% over 20 sessions; prior breakouts worked 2 of 4 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $45.42; limit $45.48; stop $43.67 (burst_low, 3.98% under the limit); day-2 line $47.18; skip if it opens under $44.46; sell-half $49.12; risk a share at the limit $1.81; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 41 shares, $1,864.68; at the YELLOW size 20 shares, $909.60; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### ASND · Ascendis Pharma A/S Ordinary Share · rank 48 · A 8.00 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $265.72 (5.14% from $252.73), open $254.28, high $266.25, low $252.74; volume 631,825 (1.05x the prior session, inside the near-volume band, 0.78x its 50-session average), dollar volume $167.9M; 2.7% over its 20-session average; route both (burst_route); flags biotech, foreign.
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-1.26 · **L+** er=0.57 r2=0.93 leg_sessions=27 leg_gain_pct=23.7 · **Y+** breakouts_in_move=0 sessions_since_move_start=32 gain_since_move_start_pct=19.3 · **N+** prior_day_pct=-1.26 prior_range_pct=2 negative=yes narrow=no median_range_pct=2.4 · **Cx** base_sessions=5 breakdowns=1 bursts_in_base=0 giveback=0.46 tightness=1.16 base_volume_vs_leg=1.02 base_volume_vs_avg=0.88 · **H+** close_pos=0.96 close_above_open=yes · **REx** vs_prior_5=0.75 vs_prior_10=0.75 bar_range_pct=5.1 · **VOL** volume_vs_prior=1.05 volume_vs_avg50=0.78 volume_rank_60=37 cv_required=no. Base 2026-11-16 to 2026-11-20, $251.55 to $278.56; extension: close 2.7% vs its 20-SMA, 8.4% over 20 sessions; prior breakouts worked 1 of 1 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $265.99; limit $270.31; stop $259.50 (half_range, 4.00% under the limit); day-2 line $276.35; skip if it opens under $260.41; sell-half $289.85; risk a share at the limit $10.81; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 6 shares, $1,621.86; at the YELLOW size 3 shares, $810.93; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### 6b. Compact rows (42 shown; 0 left out of this file; brief.json carries every one)

Every row here is RESEARCH ONLY (no SpicyStock ticket, no chart review). Research levels are derived from the recorded bar by the record's plan rules: `limit` is the highest fill the plan permits; stop basis L is the burst day's low, M the bar's midpoint; the day-2 line (too extended to enter) is the trigger plus the archived entry_above_pct and the skip-under line the trigger minus entry_below_pct (both exact in brief.json); `shares` is the model size under tonight's regime multiplier, then the same plan at full size; `refused` means the plan rule refused it; `*` after the volume ratio marks the near-volume band. Every row stopped at stage `market` (market gate: the regime admits no new longs) unless its ticker carries another in brackets. 

| ticker | gain % | vol x | $ vol M | ext % | grade | checks | trigger | limit | stop | sell-half | risk/sh | shares |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BWA | 8.22 | 1.3 | 197.9 | -0 | A 8 | 2+ L Y+ N Cx H REx VOLx | 50.86 | 51.07 | 49.03L | 55.16 | 2.04 | 0/36 |
| BXC | 6.83 | 1.08 | 6.5 | -10.1 | A 8 | 2+ L Y+ N+ Cx H+ REx VOL | 59.83 | 60.91 | 58.48M | 65.2 | 2.43 | 0/30 |
| CNS | 6.6 | 1.27 | 28 | -4.2 | A 8 | 2+ L Y+ N Cx H+ REx VOL | 68.22 | 69.53 | 66.75M | 74.34 | 2.78 | 0/26 |
| COUR | 5.54 | 1.19 | 25.2 | -4.7 | A 8 | 2+ L+ Y+ N Cx H REx VOLx | 3.64 | 3.7 | 3.56M | 3.95 | 0.14 | 0/535 |
| CR | 6.8 | 1.87 | 163.2 | 4.9 | A 8 | 2+ L Y N Cx H+ REx VOL+ | 216.09 | 216.68 | 208.02L | 234.01 | 8.66 | 0/8 |
| CVCO | 5.38 | 1.04* | 73.6 | 6.7 | A 8 | 2+ L+ Y N Cx H+ RE+ VOL | 675.7 | 686.17 | 658.73M | 736.31 | 27.44 | 0/2 |
| EEFT | 4.21 | 1.43 | 56.8 | -0.3 | A 8 | 2+ L+ Y+ N Cx H+ REx VOL | 67.18 | 68.38 | 65.65M | 73.2 | 2.73 | 0/27 |
| F | 4.3 | 1.04* | 693.7 | -2.9 | A 8 | 2+ L+ Y+ N Cx H+ REx VOL | 11.67 | 11.85 | 11.38L | 12.71 | 0.47 | 0/159 |
| GWRE | 6.23 | 1.08 | 207.3 | -9.1 | A 8 | 2+ L+ Y+ N Cx H+ REx VOL | 142.09 | 144.56 | 138.78M | 154.84 | 5.78 | 0/12 |
| HLNE | 5.53 | 1.99 | 68.2 | -3.8 | A 8 | 2+ L+ Y+ N Cx H+ REx VOL | 85.64 | 85.86 | 82.43L | 92.73 | 3.43 | 0/21 |
| HRMY | 4.48 | 1.53 | 30.4 | -2.2 | A 8 | 2+ L Y+ N+ Cx H+ RE+ VOLx | 34.08 | 34.76 | 33.37M | 37.14 | 1.39 | 0/53 |
| HUBB | 7.69 | 1.13 | 335.2 | 0.7 | A 8 | 2+ L+ Y+ N Cx H+ REx VOLx | 435.15 | 437.13 | 419.65L | 472.1 | 17.48 | 0/4 |
| III | 6.74 | 1* | 1.9 | 1.7 | A 8 | 2+ L Y+ N Cx H+ RE+ VOL | 6.2 | 6.25 | 6M | 6.74 | 0.25 | 0/300 |
| ITRN | 4.84 | 1.36 | 6.7 | -6.4 | A 8 | 2+ L+ Y+ N Cx H REx VOL | 46.63 | 47.03 | 45.15L | 50.79 | 1.88 | 0/39 |
| ITT | 7.29 | 1.42 | 256.1 | 4.7 | A 8 | 2+ L+ Y+ N Cx H+ RE+ VOL | 215.97 | 219.19 | 210.43M | 235.34 | 8.76 | 0/8 |
| J | 4.59 | 1.29 | 209.5 | 1.3 | A 8 | 2+ L+ Y+ N Cx H REx VOL | 157.69 | 159.4 | 153.03L | 171.84 | 6.37 | 0/11 |
| KMT | 8.83 | 1.34 | 55.1 | -9 | A 8 | 2+ L+ Y+ N Cx H+ RE+ VOLx | 23.19 | withheld | n/a | n/a | n/a | n/a |
| KROS | 6.41 | 1.19 | 2.9 | 10.9 | A 8 | 2+ L+ Y N+ Cx H+ REx VOL | 11.81 | 11.84 | 11.37M | 12.79 | 0.47 | 0/159 |
| KRUS | 5.83 | 1.38 | 13.6 | -20.1 | A 8 | 2+ L+ Y+ N Cx H REx VOL+ | 23.61 | 23.9 | 22.95M | 25.74 | 0.95 | 0/78 |
| LAD | 2.56 | 1.04* | 61.1 | -1.9 | A 8 | 2+ L+ Y N Cx H RE VOL | 294.76 | 296.28 | 284.43L | 319.98 | 11.85 | 0/6 |
| NAMS | 13.58 | 1.25 | 45.4 | 5.3 | A 8 | 2+ L+ Y+ N Cx H+ RE+ VOLx | 20.93 | withheld | n/a | n/a | n/a | n/a |
| NRXS | 18.25 | 1.81 | 1.4 | -16.9 | A 8 | 2+ L+ Y+ N+ Cx H REx VOL | 5.01 | withheld | n/a | n/a | n/a | n/a |
| OCTV | 5.04 | 1.37 | 79.6 | -0.1 | A 8 | 2+ L+ Y N Cx H RE VOL+ | 21.28 | 21.67 | 20.81M | 23.19 | 0.86 | 0/87 |
| OSK | 7.63 | 1.15 | 82.3 | 1.1 | A 8 | 2+ L+ Y+ N Cx H+ REx VOL | 140.61 | 143.34 | 137.61M | 153.22 | 5.73 | 0/13 |
| PTRN | 11.89 | 1.19 | 26.1 | 11.1 | A 8 | 2+ L+ Y+ N Cx H+ REx VOL | 20.73 | 20.89 | 20.06M | 22.56 | 0.83 | 0/90 |
| RELY | 9.43 | 1.12 | 88.1 | -5.5 | A 8 | 2+ L+ Y+ N Cx H+ REx VOL | 21.72 | 22.04 | 21.16M | 23.67 | 0.88 | 0/85 |
| RFIL | 13.47 | 1.2 | 1.2 | -0.9 | A 8 | 2+ L+ Y+ N Cx H REx VOLx | 7.18 | 7.27 | 6.98M | 7.81 | 0.29 | 0/258 |
| ROOT | 7.86 | 1.05* | 14.6 | -14.5 | A 8 | 2+ L+ Y+ N Cx H+ REx VOL+ | 39.96 | 40.16 | 38.56M | 43.37 | 1.6 | 0/46 |
| RVLV | 5.55 | 1.38 | 25.2 | -3.5 | A 8 | 2+ L Y+ N Cx H+ REx VOLx | 19.41 | 19.72 | 18.94M | 21.15 | 0.78 | 0/96 |
| SBC | 16.44 | 2.22 | 5.1 | 8.1 | A 8 | 2+ L Y+ N Cx H+ REx VOL+ | 6.04 | withheld | n/a | n/a | n/a | n/a |
| SHIM | 11.64 | 1.48 | 0.4 | 21.3 | A 8 | 2+ L+ Y N Cx H+ REx VOL | 3.28 | withheld | n/a | n/a | n/a | n/a |
| SLQT | 17.17 | 1.34 | 0.8 | -24.6 | A 8 | 2+ L Y+ N+ Cx H+ REx VOL | 5.89 | withheld | n/a | n/a | n/a | n/a |
| SPCB | 13.57 | 1.51 | 1.1 | -11.5 | A 8 | 2+ L+ Y N Cx H+ REx VOL | 7.3 | withheld | n/a | n/a | n/a | n/a |
| STEP | 6.91 | 1.03* | 39.2 | -1.1 | A 8 | 2+ L Y+ N Cx H REx VOL | 44.77 | 44.95 | 43.16L | 48.55 | 1.79 | 0/41 |
| TH | 10.02 | 1.03* | 18.5 | 0.5 | A 8 | 2+ L Y N+ Cx H REx VOLx | 12.32 | 12.5 | 12M | 13.41 | 0.5 | 0/150 |
| TKO | 4.02 | 1.14 | 195.6 | -1.3 | A 8 | 2+ L+ Y+ N Cx H REx VOL | 185.33 | 187.89 | 180.38L | 201.95 | 7.51 | 0/9 |
| WATT | 12.18 | 1.03* | 1.6 | -13.7 | A 8 | 2+ L+ Y+ N Cx H REx VOL | 7.11 | 7.17 | 6.89M | 7.73 | 0.28 | 0/267 |
| WH | 4.14 | 2.1 | 102.2 | 2.3 | A 8 | 2+ L Y+ N Cx H+ REx VOL | 80.37 | 81.37 | 78.12L | 87.58 | 3.25 | 0/23 |
| XENE | 4.02 | 1.18 | 49.8 | -0.4 | A 8 | 2+ L+ Y N+ Cx H REx VOL | 38.57 | 39.27 | 37.7L | 42.03 | 1.57 | 0/47 |
| YETI | 4.59 | 1.12 | 78.8 | -10.1 | A 8 | 2+ L+ Y+ N Cx H REx VOL | 37.84 | 37.85 | 36.34L | 40.88 | 1.51 | 0/49 |
| ZVRA | 5.71 | 1.05* | 11.2 | -10 | A 8 | 2+ L+ Y+ N Cx H REx VOL | 9.28 | 9.3 | 8.93L | 10.04 | 0.37 | 0/202 |
| ZYME | 7.23 | 2.08 | 43.1 | -1.1 | A 8 | 2+ L+ Y N Cx H RE VOL | 28.06 | 28.37 | 27.24M | 30.57 | 1.13 | 0/66 |

## 7. Research tail (665 names)

Every other reaction candidate: RESEARCH ONLY, no SpicyStock ticket and no levels. Tickers in the record's rank order, grouped by the one reason; a ticker whose final grade differs from its mechanical grade shows both.

- not admitted: dollar_no_expansion (109): EVRG, BANF, AFG, ALLE, AZO, CCEP, FSV, MIDD, NXST, PSA, RGA, RPRX, XEL, ADP, AXS, BBIO, BDX, BOX, GILD, MRSH, PFGC, PII, SKWD, USFD, ABM, ACM, ADBE, AII, ALRM, ALV, AN, APD, ARMK, ATO, AVY, AWI, AZN, BCPC, BMRN, BROS, CHH, DAC, DIN, DIS, DOCU, DPZ, DT, DXCM, ECL, EGP, EPR, ETON, EW, EXEL, FERG, GOLF, GRC, GVA, GWW, HON, HXL, IDT, IOSP, ISRG, JOE, LAMR, LHX, LIN, LMT, LNT, LRN, LYV, MELI, MGRC, MPWR, MRNA, MSCI, NBIX, NGVC, NOC, PEN, PH, PRI, PYPL, RACE, RBA, RBC, RGLD, RS, RTX, SKYW, SLDE, SPG, SPGI, SPSC, SR, SSD, TEX, TKR, TM, TMDX, TPR, TTC, UAL, UTI, VRTS, VRTX, WAB, XYL
- mechanical grade B, below the trade band (260): CINF, CL, LH, CHD, EXR, PG, ROP, WELL, CDW, MORN, SJM, USPH, ONT, AGPU, AIT, ALGM, AMGN, AMLX, ARCT, ATR, BA, BUUU, CALX, CHYM, CW, DCH, DE, DGX, DRI, ENSG, ESTC, ETR, EWTX, FFIV, FIG, GD, GE, GL, HALO, IQV, LSTR, META, MSGK, MSI, MU, NRIX, NSC, NUE, PRIM, PRLD, QMCO, RNG, SBUX, SNA, TARS, URI, VISN, AIZ, CWST, EXLS, FCN, MSGR, STN, AAPL, ABBV, ABG, ABTC, ACGL, AEE, AEP, AFCG, AFL, AFRM, AIFA, ALC, ALGN, ALGT, AOS, APG, ATEX, ATI, AYI, BALL, BANR, BJRI, BLKB, BLLN, BMI, BNC, BR, BRUN, BSP, BTGO, CAI, CBRL, CD, CDNA, CI, CKX, CLMB, CLYM, CMBT, CMRC, CON, CP, CPAY, CRH, CSL, CTAS, DASH, DBX, DD, DELL, DFIN, DG, DLTR, DNTH, DOC, DY, EDRY, EG, EHC, ENLT, ENPH, ENS, ESAB, ESE, ESS, EXP, FAC, FBIN, FLYW, FN, FRPT, GCT, GFF, GRMN, GXO, HAPN, HEI, HII, HPE, IBP, ICE, ICFI, ILMN, IMTX, INGM, INSM, JCI, JJSF, KARD, KMB, KO, LAZ, LEVI, LGIH, LIND, LITE, LLY, LMND, LOPE, LPLA, LPTH, LPX, MA, MANE, MAS, MATX, MBX, MCD, MCO, MDLN, MGM, MHK, MHO, MKC, MLM, MMED, MMM, MRCY, MTA, MYRG, NAVN, NEWT, NJR, NSIT, NTRA, NVMI, NVS, NVST, NWL, NXT, OKTA, OPLN, OXM, PAR, PATK, PEP, PLAB, PLMR, POST, POWL, PVH, Q, RARE, RDNW, REAL, REGN, REZI, RHLD, RSG, RUN, SAM, SECZ, SGHT, SITE, SKY, SMCI, SMG, SMTC, SN, SNDX, SPTX, SPXC, STOK, SUNB, SYK, SYY, TAP, TDY, TENB, THC, THO, TOL, TSLA, TTRX, TWLO, UI, ULCC, UNH, USDE, UVE, VAC, VICR, VIK, VMC, VMET, VPG, VSH, VTEX, WCN, WEX, WGO, WGS, WMT, XPOF, ZBH, ZM, ZS
- mechanical grade C, below the trade band (98): KNSA, PCTY, ALG, ARCO, AXSM, CELC, GNL, IONS, IPI, KALU, KWR, NRG, OCS, PXED, ANDG, ARES, BBTX, BC, CGON, COST, CVS, GIB, ORLY, PGR, R, REPL, RL, RSKD, SGP, SIBN, SPOT, TGT, TLS, ULS, VRSN, WYNN, BIIB, TYL, ARWR, AVR, CRS, FMC, IMUX, ACHC, ADSK, ALH, ALL, AMBQ, AMPH, APPN, CBLL, CDNS, CMCO, DRTS, DYN, EROK, EVR, FLS, FND, GKOS, GLOB, HUM, IBM, IMVT, INTU, IRTC, JKHY, KNSL, KRRO, KVYO, KYMR, MFP, NTSK, NUTX, OLED, PAYC, POOL, QLYS, QXO, RBRK, RCEL, S, SEPN, SLDB, SRRK, SVCO, TGLS, TMUS, TPG, TRAX, TREE, TRI, TRV, UFPI, UPBD, VRSK, XNCR, ZJYL
- quality veto: not_linear (167): AAMI, AGM, APH, APTV, BAP, BCC, BCO, CAVA, CF, CLH, CNH, CRL, CRM, CYTK, DCO, DGII, EGAN, FLR, FSS, GRRR, HLIO, IFF, IMPP, INCY, INSG, KMX, LLYVA, MBC, MDGL, MSGE, MTSI, NDSN, PAGS, PDFS, PRLB, PWR, RMIX, SCTX, SEIC, SITM, SNDA, SPHR, SSNC, SXT, TRDA, TRMB, TVTX, UNM, VGNT, WTS, WU, ZUMZ, AGCO, BDC, BIO, CBRS, IDYA, KRYS, LECO, LGND, MDB, MEDP, PLTR, RCUS, SRPT, STUB, V, ZBRA, EPAM, ABSI, AEYE, AIN, ALAB, ALTO, APLD, AXTI, BAND, BBVA, BCTX, BTDR, CAMT, CARR, CCJ, CCS, CDNL, CHKP, CHRN, CMI, CORZ, COYA, CRSP, CRWV, CUE, DECK, DIOD, DVA, FCEL, FDMT, FORM, FTH, FWRD, GFS, GLW, GOLD, IDCC, INIO, KEYS, KODK, KRNT, KURA, LGN, MAN, MLI, MXL, MYE, NBIS, NVDA, NVT, NXDT, ONCO, OSIS, ROG, RXST, SCCO, SFM, SFWL, SGI, SHAZ, SHW, SRZN, STLD, SYM, TWI, UCTT, UEC, UHS, VEEA, VELO, VERA, VKTX, VOGX, WIX, WYFI, XE, XMAX, ECPG, GRDX, OMH, BRKR, CPA, DPC, EL, ELS, FOUR, ICLR, IRLA, JBSS, MBRX, MCFT, MGN, PBLS, RDNT, SMWB, SONO, VNCE, LXEO, OPTX
- quality veto: up_days (2): GH, ASPE
- mechanical grade skip, below the trade band (26): BCS, BNAI, JBL, MITT, NKTR, SLM, STC, THRM, VC, COLM, HD, LOW, PACS, IAM, BIP, EFX, HCA, LFST, LYEL, RSSS, TRXB, VOR, AVTX, FICO, WWB, BRVE
- quality veto: up_days, not_linear (3): FRHC, MIRM, KRSA

## 8. Setting up (anticipation): 2 listed, 10 also quiet

Of 871 momentum names, 189 quiet, 8 pass the coil checks. The record's own sentence over its list (the model's rule, not an instruction to the reader): "Buy only if it clears its trigger in the first 30 minutes on volume already above yesterday's pace; an open more than 2% above the close is gapped and needs a catalyst check before you buy."

### CART · Maplebear Inc. Common Stock · listed 1 · RESEARCH ONLY: no SpicyStock ticket

- Measured: close $56.94 (-0.65% today); setups TI65; compress 0.55, tight days 7, quiet days 7, volume ratio 0.70, ADR 2.6%, extension 0.98; box $56.88 to $59.09 over 10 sessions (2026-11-10 to 2026-11-23).
- research levels (record; no order is offered at them): trigger $59.15; limit $59.74; stop $56.88 (lowest low of the last 3 sessions, 4.79% under the limit); gap check above $58.08; sell-half $63.88; risk a share at the limit $2.86; the plan rule refused it, so no model size is stated.
- No ticket: ticket withheld: at the $59.74 limit, the highest fill the ticket permits, the stop $56.88 is 4.79% away, past his 4% line; the setup stands, the ticket does not (stage `market`).
- Open-entry note (not the ticket): MOO/OPG at the open only for the top 2 names on the list, and only if it opens within +2% of $56.94
- Event registry: not_in_registry.

### OGN · Organon & Co. Common Stock · listed 2 · RESEARCH ONLY: no SpicyStock ticket

- Measured: close $13.90 (0.07% today); setups DT; compress 0.67, tight days 4, quiet days 5, volume ratio 1.36, ADR 0.3%, extension 1.00; box $13.87 to $13.94 over 8 sessions (2026-11-12 to 2026-11-23).
- research levels (record; no order is offered at them): trigger $13.96; limit $14.10; stop $13.89 (lowest low of the last 3 sessions, 1.49% under the limit); gap check above $14.18; sell-half $15.08; risk a share at the limit $0.21; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 531 shares, $7,487.10; at the YELLOW size 357 shares, $5,033.70; no new longs: the size multiplier is 0.
- No ticket: breadth sizes new positions at zero tonight (stage `market`).
- Open-entry note (not the ticket): MOO/OPG at the open only for the top 2 names on the list, and only if it opens within +2% of $13.90
- Event registry: not_in_registry.

Also quiet (not listed; no plan; every row RESEARCH ONLY: no SpicyStock ticket):

| ticker | setups | close | compress | tight | vol ratio | trigger | stop | risk % | why not listed |
|---|---|---|---|---|---|---|---|---|---|
| CBOE | TI65/MDT | 354.67 | 0.75 | 3 | 0.95 | 370.35 | 350.55 | 5.6 | stop wider than 4% |
| MANH | DT/TI65/MDT | 245.00 | 0.71 | 6 | 0.85 | 255.25 | 242.61 | 5.2 | stop wider than 4% |
| HGTY | TI65/MDT | 16.17 | 0.74 | 4 | 0.99 | 16.70 | 15.84 | 5.4 | stop wider than 4% |
| STAA | TI65 | 24.36 | 0.73 | 5 | 0.57 | 25.95 | 23.86 | 8.8 | stop wider than 4% |
| FDS | TI65 | 312.49 | 0.70 | 4 | 0.66 | 324.30 | 307.44 | 5.5 | stop wider than 4% |
| HURN | DT | 171.97 | 0.75 | 6 | 0.51 | 175.48 | 164.74 | 6.5 | stop wider than 4% |
| HLP | DT/TI65/MDT | 3.37 | 1.13 | 5 | 0.93 | 3.68 | 3.14 | 17.2 | failed compress |
| DINO | DT | 87.04 | 0.98 | 6 | 0.91 | 91.93 | 86.50 | 6.3 | failed compress |
| SGRY | DT/TI65/MDT | 26.56 | 0.34 | 0 | 0.48 | 27.10 | 26.48 | 2.3 | failed tight |
| FCN | TI65/MDT | 206.17 | 0.80 | 7 | 0.98 | 210.50 | 201.27 | 4.6 | failed compress |

## 9. Open model plans (0)

Open MODEL plans walked on daily (and retained minute) bars; not holdings.


## 10. Model record

- Scorecard: 22 plans in 60 sessions (2026-08-28 to 2026-11-23): 5 settled (2 wins, 3 losses, 0 even), 0 open, 0 pending, 1 uncertain, 14 not filled, 2 unmeasured; sum of R 0.43.
- Readable as a rate: **no** (needs 20 settled); win rate n/a, average R n/a, median R n/a. These are model plans walked on bars, not trades, and no edge is established.
- How it is counted: from bars alone, a model and not a brokerage record: a daily bar books a fill only at the next open at or over the trigger and at or under the limit; a day that reaches the trigger after the open is read again from that session's retained minute bars, which book a fill in the first 30 minutes at the trigger (or the crossing minute's open over it), none after it, and leave a crossing minute that cannot order the fill against the limit or the stop uncertain; without those minutes such a day, whether or not its low also reached the stop, and an open past the limit or under the skip line that could still have filled are uncertain, counted here and in no rate; a fill at the open whose day then reaches the stop is booked at exactly the stop; the published stop is one R on the whole position, every sale weighted by the whole shares it sold; with complete bars, settled by day 5
- The model record counts 22 tickets issued from 2026-10-08 through 2026-11-13: 17 distinct setups, and 5 tickets that issued a setup again on a later night.
- By ticket: 5 settled, 1 uncertain, 14 not filled, 2 missing or stale bars. By setup: 5 settled, 1 uncertain, 10 not filled, 1 missing or stale bars.
- Issued more than once: OGN anticipation 2 times (2026-10-27 to 2026-10-28); MFIC anticipation 4 times (2026-11-09 to 2026-11-13); UTZ anticipation 2 times (2026-11-10 to 2026-11-11). No ticket that was later issued again has a fill known, so re-issues raise the ticket counts and add nothing to the sum of R.
- The 5 settled tickets sum to +0.43R (2 wins, 3 losses, 0 breakeven). Below 20 settled tickets the record prints no rate.
- The tickets were sized against 3 model accounts: $10,000 at 0.5% risk (2 tickets, 1 settled, +0.41R, +$2.24 in model dollars); $2,000 at 0.5% risk (8 tickets, 1 settled, +3.02R, +$5.25 in model dollars); $30,000 at 0.5% risk (12 tickets, 3 settled, -3.00R, -$90.63 in model dollars).
- A sum of R is not a sum of dollars: R counts each ticket as one unit whatever its size. The settled tickets sum to +0.43R and to -$83.14 in model dollars.
- 3 settled tickets ended on a stop. As the model books them, a stop first reached inside a session at exactly the stop price, the sum is -3.00R (-$90.63). With the same exits at the stop day's close it is -4.66R (-$140.78): what holding to the close would have been, not a fill estimate. At the stop day's low, a worst-case bound, it is -5.78R (-$174.64).
- Under those readings the settled sum is +0.43R as booked, -1.23R at the closes and -2.35R at the lows.
- VIK 2026-11-04: the retained minute bars first reach the stop at 09:58 ET, in a minute that opened at $88.26 with a low of $88.09; at that low the ticket reads -1.03R.
- 2 settled tickets held 1 share and sold it whole at the half-sale step, because 1 share cannot be halved: SN +0.41R, EXEL +3.02R. Walked over the same bars at 2 shares: SN +0.22R, EXEL +2.62R. With those readings the settled sum is -0.16R.
- 1 ticket is uncertain: the bars cannot say whether it filled, and it is in no sum. MCS 2026-10-28 reads -0.91R if filled at its $28.75 limit and -0.88R if filled at its $28.47 trigger. These are bounds, not results.
- 3 counted tickets were withdrawn by a later run of their own session and stay in the record and in these counts: MG 2026-10-08, SN 2026-10-08 (settled, +0.41R), ZIM 2026-10-09.
- Model-record block (version 1): 22 tickets; settled 5, open 0, pending 0, uncertain 1, not_filled 14, unmeasured 2, unreadable 0, unscored 0; sum of R 0.43. Computed by the evening run from that run's fetched bars; its ticket count, bucket counts and sum of R are held to the record's scorecard, the rest is carried as computed.
- Model record, definitions: A ticket is one night's order for one stock. The scorecard counts every retained ticket once.
- Model record, definitions: A setup is a chain of tickets of one ticker and kind: a ticket continues the chain when it was issued within 5 sessions after the ticket before it and that one has no fill known (not filled, awaiting its first session, or without bars). A setup's bucket is its last ticket's.
- Model record, definitions: An era is the tickets sized against one model account (equity and risk percent).
- Model record, definitions: R is a settled ticket's model result over its risk at the model entry (the entry less the published stop, on the whole position), every sale weighted by the whole shares it sold. It counts each ticket as one unit whatever its size.
- Model record, definitions: Model dollars are a settled ticket's sale prices less its model entry, times the shares sold.
- Model record, limits: A model from bars alone, not a brokerage record: no fees, spread, slippage, tax or real execution is measured, and nothing here knows what anyone holds.
- Model record, limits: Minute bars are retained only for a first day the daily bar could not place, so a stop day usually has its daily bar alone and its range stays between that day's low and the stop.
- Model record, limits: A ticket's account is the publishing record's own, the previous brief's for the same evidence id, or the seed read off the publications in git; an account none of them gives is not guessed.
- Model-record tables: not printed here, to keep this file within its bound; brief.json carries every one.
- Pick ledger (picks.json): 22 picks over 17 distinct tickers; repeated: MFIC x4, OGN x2, UTZ x2; by kind anticipation 19, burst 3; by regime at the pick yellow 22; picks in the scorecard window 22 against 22 plans counted. A pick is one published model ticket; the same stock listed on several nights is several picks, and each counts as its own plan in the scorecard. Picks made under different archived accounts are sized differently; a pick carries its shares, not the account it was sized for.

| picked | ticker | kind | regime | shares | trigger | limit | stop |
|---|---|---|---|---|---|---|---|
| 2026-11-13 | MFIC | anticipation | yellow | 96 | 10.42 | 10.52 | 10.13 |
| 2026-11-13 | HZO | anticipation | yellow | 105 | 52.94 | 53.47 | 52.76 |
| 2026-11-13 | CBC | anticipation | yellow | 26 | 38.81 | 39.20 | 37.81 |
| 2026-11-13 | CART | anticipation | yellow | 16 | 59.82 | 60.42 | 58.20 |
| 2026-11-11 | UTZ | anticipation | yellow | 375 | 14.29 | 14.43 | 14.23 |
| 2026-11-11 | MFIC | anticipation | yellow | 117 | 10.44 | 10.54 | 10.22 |
| 2026-11-10 | UTZ | anticipation | yellow | 375 | 14.29 | 14.43 | 14.23 |
| 2026-11-10 | MFIC | anticipation | yellow | 110 | 10.44 | 10.54 | 10.20 |
| 2026-11-09 | MFIC | anticipation | yellow | 104 | 10.44 | 10.54 | 10.18 |
| 2026-11-04 | VIK | burst | yellow | 10 | 91.17 | 91.84 | 88.17 |
| 2026-11-04 | RCBC | burst | yellow | 15 | 60.38 | 61.38 | 58.93 |
| 2026-11-04 | HQY | burst | yellow | 8 | 108.84 | 110.53 | 106.11 |
| 2026-11-02 | ESRT | anticipation | yellow | 12 | 5.12 | 5.17 | 4.97 |
| 2026-10-29 | QGEN | anticipation | yellow | 1 | 50.87 | 51.38 | 50.10 |
| 2026-10-29 | PSNL | anticipation | yellow | 4 | 16.15 | 16.31 | 15.80 |
| 2026-10-28 | OGN | anticipation | yellow | 22 | 13.82 | 13.96 | 13.74 |
| 2026-10-28 | MCS | anticipation | yellow | 2 | 28.47 | 28.75 | 27.64 |
| 2026-10-27 | OGN | anticipation | yellow | 22 | 13.82 | 13.96 | 13.74 |
| 2026-10-27 | EXEL | anticipation | yellow | 1 | 65.65 | 66.31 | 63.91 |
| 2026-10-09 | ZIM | anticipation | yellow | 2 | 30.38 | 30.68 | 29.66 |
| 2026-10-08 | SN | anticipation | yellow | 1 | 186.50 | 188.37 | 181.10 |
| 2026-10-08 | MG | anticipation | yellow | 16 | 21.09 | 21.30 | 20.52 |

## 11. Event registry and coverage

- Event registry (manual; known cash acquisitions only): 7 entries, last reviewed 2026-11-19, 4 days before the measured session 2026-11-23. 1 of 7 unresolved entries are past their review date: ACVA 39 days. Each stays blocked for a SpicyStock ticket; this record does not establish its current status. None of the 735 listed rows (723 bursts, 2 setting up, 10 also quiet) is in the registry. A stock that is not in the registry has not been cleared: SpicyStock reads no company news, and its earnings and SEC checks ran for 0 of the 734 listed names (they run for tickets only).
- Entries: MG (cash_acquisition, announced 2026-09-18, review due 2026-11-25); PRTH (cash_acquisition, announced 2026-09-21, review due 2026-12-17); ARX (cash_acquisition, announced 2026-08-13, review due 2026-12-17); BWIN (cash_acquisition, announced 2026-09-14, review due 2026-12-17); ACVA (cash_acquisition, announced 2026-09-10, review due 2026-10-15); ZIM (cash_acquisition, announced 2026-02-16, review due 2026-12-02); CCC (cash_acquisition, announced 2026-10-15, review due 2026-12-17).
- Status words: `known_event` = in the registry and blocked for a SpicyStock ticket; its manual review is current; `review_required` = in the registry and blocked for a SpicyStock ticket; its manual review is overdue; `not_in_registry` = not in the registry: NOT a clearance, nothing was checked.
- Earnings and 8-K check: status `not_applicable`; 0 ticket rows; 734 of 734 listed names had no check at all.
- Not checked by SpicyStock: company news and press releases, announced earnings dates, offerings and shelf takedowns, FDA and trial dates, halts outside the morning check, delisting notices beyond 8-K item 3.01 on tickets, index changes, lockup expiries, ex-dividend dates.

## 12. Rules

- Rules digest `d14cd717cd8a`; without the universe membership identity `4ba4434239c5` (membership identity `bafd18cdd2e28423`): the record's digest nests the universe membership identity, so it moves on any night the selection's membership moves; `digest_without_membership` is the same digest with that identity removed, and moves only when an archived rule changes.
- pipeline: trade_grades ["A+", "A"], yellow_grades ["A+"], max_reads 12, reader_policy "accepted_required_v1", reader_refusal_fraction 0.25, reader_refusal_min 1, stale_tolerance_fraction 0.01, stale_sessions_max 5, min_coverage_fraction 0.5
- plan: entry_below_pct 2.0, entry_above_pct 4.0, skip_gap_pct 8.0, entry_window_minutes 30, assumed_slippage_pct 1.0, limit_rule "stop_constrained", sizing_basis "order_limit", max_stop_pct 4.0, ideal_stop_pct 2.0, stop_risk_multiplier 0.5, gain_ceiling_pct 15.0, extension_hazard_pct 20.0, hazard_multiplier 0.5, sell_half_pct 8.0, abnormal_day_pct 10.0, gap_exit_pct 20.0, sell_half_day 3, no_progress_day 3, trail_from_day 3, final_exit_day 5, allocation_policy "combined_stages_reserved_principal_v1"
- admission: version 1, policy "burst_route_or_dollar_expansion_v1"
- grading: reader_request_version 3
- record: scorecard_min_plans 20, scorecard_sessions 60

## 13. Bounds

- brief.json: 42 candidates in detail, 16 compact, 0 moved to the tail for size. Tickets and reviewed names are always detailed; of the rest, in the stated order, the largest multiple of 4 (or all) is detailed that keeps brief.json within 250000 bytes, and the others are compact rows; only if none can be detailed are compact rows cut, to the largest multiple of 10 that fits, the rest moving to the research tail.
- This file: 16 in detail, 42 compact rows, 0 compact rows left out, 0 research-tail names not named; reviewed names in their short form: no; model-record tables printed: no. Rule: tickets and reviewed names always in detail; then, to stay within 80000 bytes, the model-record tables are given up first, then the other names' detail (largest multiple of 2 that fits), then tail names (multiple of 50), then the reviewed names' check measurements and all but a cut reason of their reader sentences (the short form), then compact rows (multiple of 5); brief.json carries what this file leaves out.
- Research tail: 665 named, 0 left out (the first 4000: the admitted trade-band names moved out for size, then the rest by the record's rank order). Open plans left out: 0. Stale names left out: 0. The evening run's model-record block is carried whole when its canonical encoding is within 60000 bytes and the brief still fits with it; past that bound it is carried reduced (each plan row keeps its identity, result and account; the setups table is left out), and not at all if that does not fit either; brief.md prints its sentences and, while they fit, the first 30 rows and 12 columns of each of its tables. A copied sentence over 900 characters is cut and ends with an ellipsis.

## 14. What this file does not establish

- This is a model's output from one provider's daily bars. This brief places and observes no order, and SpicyStock reads no brokerage account, balance, position or fill.
- No price here is a live quote. A candidate's prices are the measured session's bar as published; an open plan's, the pick ledger's and the model record's are the earlier sessions' the rows name. Check the current price, spread and halt state before acting.
- A grade is a checklist score over daily bars and, where a review is recorded, one chart reader's judgement. It is not a forecast.
- The model record establishes no edge. Its counts are model plans walked on bars, not trades; read `scorecard.readable` and its counts before any rate, and a sum of R is not a sum of dollars.
- A model fill at the open assumes a buy stop-limit order already resting at the broker before the open. Whether the broker accepts that order for a burst ticket, whose buy stop is the last close, is unconfirmed.
- A stop reached inside a session is booked at exactly the stop price. A real stop order fills at the next available price, which can be worse, and a gap through the stop loses more.
- Research levels are never tickets. For a burst they are what the record's own plan rule gives for the recorded bar at the archived model account; for a setting-up row they are the record's own plan, which the plan rule may have refused (`plan_rule_eligible` false) or left without shares. No chart review accepted them unless the row's reader state says so.
- A model ticket is sized for the archived model account (`account`), not for the reader's account. Shares, cost and risk are planned price-to-stop arithmetic at the limit, not a maximum loss.
- The market regime is SpicyStock's gate for its own model tickets: an input to weigh, not an instruction. The scaling of its count thresholds, the admission rule, the checklist weights and the chart reader are this project's own rules (knowledge/method.md says whose number each is), and the record does not establish that the gate improves outcomes.
- SpicyStock reads no company news. Earnings and SEC 8-K items are read for published tickets only, from SEC filings: a projected date is an estimate, never an announced date, unknown is never clear, and filings are not news coverage.
- The event registry is a hand-kept list of known cash acquisitions. A stock that is not in it has not been cleared: issuer news, offerings, guidance and other corporate events are not checked.
- One provider's bars as of the run's fetch; a session's volume can be revised afterwards. The universe is the selection named in `service.universe`, not point-in-time membership, and a stock named stale had no bar for the session: its inputs are unknown, not a measured non-match.
- Whether the broker accepts the printed order form (a day buy stop-limit with a one-triggers-the-other sell stop) is unconfirmed; see knowledge/broker-fidelity.md.
- Rows are bounded. `bounds` states every list that was cut, how many rows were left out and the rule that chose the kept ones; the canonical record carries every row.
- This brief is bound to one publication by the SHA-256 and byte length in `identity.canonical`. Whether a newer publication exists is not in this file: apply `service.freshness_rule` with your own clock.
