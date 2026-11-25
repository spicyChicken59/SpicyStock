# SpicyStock daily brief: measured Tue 24 Nov 2026, plans for Wed 25 Nov 2026

> This is SpicyStock's daily brief: one evening publication's model output, derived from that publication's record and its pick ledger, with the model-record block the same evening run computed from its own bars carried in (section 10), and from nothing else, for an outside analyst to read in place of the full record.
> Check that it is current before using it: `status` must be `derived`, and the freshness rule in section 2 (`service.freshness_rule`) is applied with your own clock.
> Only the rows in section 5 (`tickets`) are published model tickets. Every other row is research only: its levels are reference arithmetic and SpicyStock offers no order for it.
> SpicyStock places, cancels and observes no order and reads no brokerage account. The owner decides and places every order.

**Model gate RED: size multiplier 0.0; 0 published model tickets for the applicable session.** The record's own cover sentence, written for its model tickets and not an instruction to the reader: "Stand aside."

## 1. Identity and binding

- Measured session: 2026-11-24 (open); plans are for **2026-11-25**, entry window 2026-11-25T09:30:00-05:00 to 2026-11-25T10:00:00-05:00 (America/New_York), full session closes 2026-11-25T16:00:00-05:00.
- Published 2026-11-25T05:27:26.719515+00:00 (run 45553627202, evening); rules version `e40195855de3`.
- Canonical record `data.json`: 13,409,909 bytes, SHA-256 `c74f823525608f22e7464bcc725d6ba8116c847cdbf379e5568fae4ab835c914`.
- `picks.json`: 28,615 bytes, SHA-256 `7f232ab84aca7c3438f70c8110325660b3a40a339fb12f30d502883089b146b0`.
- This file renders `brief.json` (171,682 bytes, SHA-256 `6c30600177f29499811fac137b617444b2f2325d39e7bc62a87ed2eb9986a09a`).
- Page https://spicychicken59.github.io/SpicyStock/ · record https://spicychicken59.github.io/SpicyStock/data.json · brief https://spicychicken59.github.io/SpicyStock/brief.json and https://spicychicken59.github.io/SpicyStock/brief.md · run log https://github.com/spicyChicken59/SpicyStock/actions/runs/45553627202.

## 2. Service state

- Run status: **ok**; problems: none; mail delivered.
- Delivery: Published 12:27 AM ET on Wed 25 Nov, 492.4 minutes after the measured session's completion (4:15 PM ET); after both scheduled slots (6:16 PM and 8:16 PM ET); before the next session's open (Wed 25 Nov, 9:30 AM ET). (slot `after_retry`, 492.4 minutes after completion).
- Next publication (`service.expected`): the next session is 2026-11-25; it completes at 2026-11-25T16:15:00-05:00; primary slot 2026-11-25T18:16:00-05:00; retry slot 2026-11-25T20:16:00-05:00; recovery limit 2026-11-27T09:30:00-05:00.
- Freshness rule (states: `newest`, `not_due`, `pending`, `late`, `missing`):
  - Freshness is the reader's own computation: this file carries no clock. Compare your own clock, as an instant with its UTC offset, with the instants in `service.expected`, in this order, and stop at the first that holds.
  - 1. Before `completion_at`: `newest`. The next session has not completed, so no record of a later session can exist yet. The same session can still be published again, and a later run can withdraw a ticket: before acting on a ticket, fetch the file again and compare `identity.canonical.sha256` with the copy the plan was built on.
  - 2. Before `primary_slot_at`: `not_due`. The next session has completed and its evening run is not yet due.
  - 3. Before `retry_slot_at`: `pending`. The first scheduled slot has passed and the retry slot has not.
  - 4. Before `recovery_until`: `late`. Both scheduled slots have passed; a delayed run can still publish the next session until that instant.
  - 5. Otherwise: `missing`. The service does not publish a session after the session that follows it has opened. If this is still the newest file the site serves, the next session was not published and every ticket in this file is expired.
  - From step 2 on, fetch the file again before relying on it: a newer one may exist. A field that is null has its reason in `service.expected.unknown`; without the instant a step needs, freshness is unknown and the file is research only.
  - Freshness is not permission. A ticket applies only from `identity.entry_window.opens_at` to its `cutoff_at`; after the cutoff it is over, whatever state this rule gives.
- Morning check: plans are for 2026-11-25; entry window 2026-11-25T09:30:00-05:00 to 2026-11-25T10:00:00-05:00; the morning collection starts at 2026-11-25T09:00:00-05:00. Receipt https://spicychicken59.github.io/SpicyStock/morning.json: A morning receipt belongs to this publication only when its `publication.data_sha256` equals `identity.canonical.sha256`. One generated before `window_opens_at` carries no quote from inside the entry window. The receipt is not part of this file: it lands the next morning, if a morning check runs.
- Inputs: Alpaca `sip`, split-adjusted 1Day bars, read by the run that began 2026-11-25T05:27:26.719515+00:00; 4,736 of 4,755 intended stocks ready (acceptance `degraded`); 3,467 measured, 19 stale.
- Stale tolerance: `tolerated` (19 stale against a limit of 47). Stale: ARKR, BEBE, BHM, CUB, DDC, GSIW, KELYB, KEQU, LUD, MAYS, MGRT, NCEW, PBHC, PFX, RAND, SFBC, TOVX, TRSG, WLYB.
- Seed: None of the 19 stale stocks is on the seed alone; each is in the directory this run selected from.
- Follow-up: The 2026-11-23 publication's 17 stocks without a 2026-11-23 bar, read again from this run's split-adjusted fetch: 17 now carry a 2026-11-23 bar (17 with zero volume); 14 would not have been listed; 3 fall under the $3 session-close policy. A late bar is the bar the provider served at this run's check; it never becomes a signal, plan or ticket.
- Minute bars: No plan's first day needed its minute bars tonight; minute bars are retained for 5 plans' first days.
- What the inputs do not establish: Why a stale stock had no session bar is not established; its session inputs are unknown, not a measured non-match, until a later run reads the session again. These bars are the provider's as read by the run that began at 2026-11-25T05:27:26.719515+00:00; a session's volume can be revised afterwards, and this file does not measure by how much. One price source: nothing cross-checks a close, a volume or a split. Bars are adjusted as `service.inputs.basis.adjustment` says and for nothing else. The universe is the selection named in `service.universe`, as fetched; it does not establish which stocks were listed during the session, and the record does not name the stocks that entered or left since the previous publication.
- Chart reader (claude-sonnet-4-6): 2 of 2 reads accepted, verdict `complete`. Chart reader cost: 2 calls for 2 names, 2 replies; 17,181 input tokens (9,061 uncached, 4,060 written to the cache, 4,060 read from it) and 983 output tokens, under claude-sonnet-4-6. Token counts as the API reported them; the record carries no price.
- Review selection (`account_feasible_first_research_v2`): 0 feasible, 2 requested of 12; selected: ADP (research_ranked), PFE (research_rotating).
- Admission: 836 reaction candidates, 310 admitted to the trade band and the chart reads (253 by the 4% scan, 57 by the dollar scan on a range-expansion, higher-volume day); 526 came through the dollar scan alone without one and are research only. Of the 83 mechanical A-band names without a veto, 22 are admitted and 61 are not. Admission is read off the recorded discovery route and the checklist's own range-expansion and volume checks; it is never a grade, and the chart reader never sees a name it stops.
- Earnings and 8-K items (status `not_applicable`): Earnings: no ticket to check.
- Candidate funnel under a RED market: 836 reaction candidates discovered, 0 potentially usable (mechanical grade in the admitted band, no veto, discovery admitted), 0 reaction tickets. Reaction candidates stopped at: 836 market gate: the regime admits no new longs. Anticipation: 857 momentum names, 277 quiet, 5 passing the coil checks, 4 listed, 0 tickets. Listed setups stopped at: 4 market gate: the regime admits no new longs. A stage is where the record's own gates stopped a name; it is not a judgement of the setup and establishes no entry.
- Closest miss: ADP came closest at B 10.0.

## 3. Market regime

- Verdict **RED** for 2026-11-24: size multiplier 0.00; grades the regime admits to a ticket: none. The light is SpicyStock's gate for its own model tickets: an input to weigh, not an instruction to the reader.
- Recorded reason: 10-session ratio 0.52 (1279 up, 2446 down) < 1.0: more breakdowns than breakouts
- Counts over 3,467 measured stocks (4,755 intended, 4,736 with a session bar, 1,269 under the $3.00 session close floor): up 4% 252, down 4% 119; up/down 25% in a quarter 538/975; up/down 25% in a month 103/379; up/down 50% in a month 17/30; up/down 13% in 34 days 977/1,395; 37.9% above the 40-day average.
- Ratios: 5-session 0.60 (817 up, 1,362 down, unrounded 0.5999); 10-session 0.52 (1,279 up, 2,446 down, unrounded 0.5229). The rules compare the rounded number.

All five regime rules, in the order they are asked (universe 3,467 against a reference of 6,500). Count thresholds are the reference count times the stocks measured over the reference universe; that scaling is this project's own. Ratio thresholds are not scaled.

| rule | tier | measured | comparison | threshold tonight | reference | fired | decides | masked |
|---|---|---|---|---|---|---|---|---|
| down4_alarm | red | down4 119 | at or over | 373.4 | 700 of 6,500 | no | no | no |
| ratio_10d_red | red | ratio_10d 0.52 | under | 1 | 1, not scaled | yes | yes | no |
| ratio_5d_red | red | ratio_5d 0.6 | under, with more names down 4% than up 4% today | 0.5 | 0.5, not scaled | no | no | no |
| ratio_10d_yellow | yellow | ratio_10d 0.52 | under | 2 | 2, not scaled | yes | no | yes |
| up50_month_hot | yellow | up50_month 17 | over | 10.7 | 20 of 6,500 | yes | no | yes |

- GREEN needs all five rules quiet: fewer than 373.4 names down 4% today (it is 119); a 10-session ratio at or over 2 (it is 0.52: 1,279 up against 2,446 down); no 5-session ratio under 0.5 with more names down 4% than up 4% today (it is 0.6, with 119 down against 252 up); and no more than 10.7 names up 50% in a month (it is 17).
- Yellow by rounding (more ten-session breakdowns than breakouts while the rounded ratio is not under the red line): no. Near a line: no (the 10-session ratio is -0.48 from the red line and -1.48 from the yellow line; band 0.06, the band is this project's own label bound, the largest later re-reading of a published ratio seen through 17 November 2026; it is not a rule and gates nothing).

Breadth history (the newest 10 sessions of the record's own breadth history, each read again tonight over tonight's stocks: an earlier session's counts can differ from what its own night published): 2026-11-11 231/50 r10 1.01; 2026-11-12 51/264 r10 0.89; 2026-11-13 72/137 r10 1.01; 2026-11-16 50/429 r10 0.87; 2026-11-17 58/204 r10 0.80; 2026-11-18 162/166 r10 0.62; 2026-11-19 43/343 r10 0.75; 2026-11-20 30/705 r10 0.52; 2026-11-23 330/29 r10 0.45; 2026-11-24 252/119 r10 0.52.

## 4. Model account

- Model account (the model's configured sizing assumptions; not a brokerage balance): equity $30,000.00, risk 0.50% a trade, position cap 25.00%, 4 slots.
- Model allocation: next-session tickets would commit $0.00 of the configured $30,000.00; 0 of 4 slots.
- Cut: OGN (anticipation, no_new_longs): breadth sizes new positions at zero tonight
- Cut: RXO (anticipation, no_new_longs): breadth sizes new positions at zero tonight
- Cut: CART (anticipation, withheld): ticket withheld: at the $59.40 limit, the highest fill the ticket permits, the stop $56.88 is 4.24% away, past his 4% line; the setup stands, the ticket does not
- Cut: LH (anticipation, withheld): ticket withheld: at the $383.05 limit, the highest fill the ticket permits, the stop $366.33 is 4.36% away, past his 4% line; the setup stands, the ticket does not

## 5. Published model tickets (0)

None. The record published no model ticket for the applicable session.

## 6. Admitted trade-band candidates (22 of 83 in the band; 836 discovered)

Definition: reaction candidates whose mechanical grade is in the trade band (A+, A), with no quality veto, that the discovery admission admits; plus any other name with a published ticket or a selected chart review. Order: published tickets, then names selected for a chart review, then the rest; each in the record's rank order (grade, score descending, ticker). Model status: a row is `TICKET` only when the record published a model ticket for it (its order is in `tickets`); every other row is `RESEARCH ONLY: no SpicyStock ticket`. Later gates: the gates after the market gate, re-derived from the row's recorded fields so a RED night does not hide them; passing them is not a ticket: the stop rule, the event registry, sizing and the slot allocation follow, and the market gate stands.

Checklist, the same thresholds for every name. **2** not up two days in a row: up_run <= 1, counting days above +1.0%; veto at 3+ up closes of any size (weight 1.5). **L** linearity of the prior leg: ER >= 0.4 or R2 >= 0.55 (both for A+); failing is a veto (weight 2.0). **Y** young trend: first or second breakout: prior breakouts since the move started <= 1 (0 for A+) (weight 1.5). **N** narrow or negative day before: prior day negative or range < 2.0% (A+: negative and under its 20-session median range) (weight 1.5). **C** consolidation quality: base 3-20 sessions, breakdowns <= 1, giveback <= 0.34, tightness <= 1.0 (A+: 0 breakdowns, 0 bursts inside, giveback <= 0.25, tightness <= 0.7, base volume under the leg's and the 50-session average) (weight 2.0). **H** close near the high: close_pos >= 0.8 and close > open (A+ >= 0.9; partial from 0.7) (weight 1.5). **RE** range expansion: today's range over the largest of the prior 5 >= 1.0 (A+: also over the prior 10) (recorded, no weight). **VOL** higher volume: volume > prior session (A+: rank <= 3 of the last 60); a base over 21 sessions also needs >= 1.5x the 50-session average (recorded, no weight).
Check marks: letter then + (pass at the A+ level), nothing (pass), ~ (partial), x (fail), ? (not measured).

Hold days for a plan entered on the applicable session: day 1 = 2026-11-25, day 2 = 2026-11-27, day 3 = 2026-11-30, day 4 = 2026-12-01, day 5 = 2026-12-02. The model's exit rules (source B Bonde, P this project, T a third party's test): [B] when same or next day, the price reaches the sell-half level (+8% from the planned entry): sell half and move the stop to 25-50 cents under that day's high. [B] when any single day closes at or above the abnormal-close level (+10%): take at least partial profit and move the stop up to protect the rest. [B] when it opens at or above the gap-exit level (+20%) after entry: sell at the open (or pre-market). [B] when the close of day 1: the stop rises to the entry day's low if that is above the stop. [B] when day 3 close: sell at least half at the close. [B] when day 3 closes at or below the planned entry: exit: no follow-through. [P] when from the close of day 3: raise the stop to each day's low (it never moves down). [B] when day 5 close: exit the remainder into strength. [B] when the protective stop at the stop is a stop-market order, live intraday from the moment the buy fills: if it is somehow not filled, exit on any close below it. [T] when day 2 is green: do not move the stop to break-even before day 5 just because it is green (theStrat Lab EP9M backtest: the win rate collapses from 29.8% to 7.25%; delaying to day 5 restores it); the +8% raise above is a different rule.

Page for any ticker here: https://spicychicken59.github.io/SpicyStock/#/explore/bursts/<TICKER> (setting-up names: the same with `setting-up` in place of `bursts`). Near-volume band: 108 of the discovered bursts have a volume within 0.05 of the previous session's (the burst's volume is within this fraction of the previous session's, so its higher-volume check can flip on the provider's later corrections; the bound is this project's own label, not a rule).

### 6a. In detail (16 of 22 listed: every ticket and reviewed name, then the first 14 others)

### ADP · Automatic Data Processing Inc. Common Stock · rank 82 · A+ 10.00, final B · reviewed · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $310.79 (2.87% from $302.11), open $302.79, high $311.61, low $301.64; volume 2,269,644 (1.27x the prior session, 1.02x its 50-session average), dollar volume $705.4M; 2.8% over its 20-session average; route dollar (dollar_expansion).
- Checks: **2+** up_run=0 up_closes=2 prior_day_pct=0.13 · **L+** er=0.46 r2=0.82 leg_sessions=32 leg_gain_pct=21.6 · **Y** breakouts_in_move=1 sessions_since_move_start=37 gain_since_move_start_pct=20.6 · **N** prior_day_pct=0.13 prior_range_pct=1.3 negative=no narrow=yes median_range_pct=2.2 · **C** base_sessions=5 breakdowns=0 bursts_in_base=0 giveback=0.29 tightness=0.88 base_volume_vs_leg=1.02 base_volume_vs_avg=0.99 · **H+** close_pos=0.92 close_above_open=yes · **RE+** vs_prior_5=1.23 vs_prior_10=1.07 bar_range_pct=3.2 · **VOL** volume_vs_prior=1.27 volume_vs_avg50=1.02 volume_rank_60=23 cv_required=no. Base 2026-11-17 to 2026-11-23, $298.62 to $316.14; extension: close 2.8% vs its 20-SMA, 6.0% over 20 sessions; prior breakouts worked 0 of 1 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: accepted, B 7.5 (research_ranked); selection blockers: grade_not_admitted.
  - Reader's reason (commentary): The base shaded in the chart (Nov 17–23) shows five sessions with noticeably wide, overlapping bars — the range of each candle overlaps substantially with its neighbors, and tightness of 0.88 is well above the A+ threshold of 0.70, confirming the bars are not genuinely tight. The burst bar itself is clean (close near the high, above open, modest gap), but the consolidation lacks the orderly, narrow character Bonde requires for top-grade setups. Volume on the signal day is only marginally above average (rank 23 of 60), which is ordinary rather than confirming.
  - Reader's main risk (commentary): The base is visually loose with overlapping bars, meaning the consolidation did not compress energy as tightly as an A+ setup demands, raising the risk of a failed follow-through.
  - Reader's entry note (not the ticket): Skip if ADP opens below the burst day's close (~310.79) or gaps up more than 1% above it, leaving no room within the plan's risk parameters.
- Later gates: GREEN band fail, YELLOW band fail, veto pass, admission pass, reader `accepted`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $311.10; limit $314.20; stop $301.64 (burst_low, 4.00% under the limit); day-2 line $323.22; skip if it opens under $304.57; sell-half $339.01; risk a share at the limit $12.56; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 5 shares, $1,571.00; at the YELLOW size 2 shares, $628.40; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### PFE · Pfizer Inc. Common Stock · rank 534 · A 8.00, final skip · reviewed · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $28.46 (3.87% from $27.40), open $27.49, high $28.60, low $27.38; volume 31,087,445 (1.08x the prior session, 0.91x its 50-session average), dollar volume $884.7M; -2.3% over its 20-session average; route dollar (dollar_expansion); flags biotech.
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=0 · **L** er=0.18 r2=0.58 leg_sessions=59 leg_gain_pct=11.5 · **Y+** breakouts_in_move=0 sessions_since_move_start=1 gain_since_move_start_pct=3.9 · **N** prior_day_pct=0 prior_range_pct=1.4 negative=no narrow=yes median_range_pct=1.9 · **Cx** base_sessions=12 breakdowns=0 bursts_in_base=0 giveback=0.82 tightness=1.05 base_volume_vs_leg=1.05 base_volume_vs_avg=1.03 · **H** close_pos=0.89 close_above_open=yes · **RE+** vs_prior_5=1.54 vs_prior_10=1.3 bar_range_pct=4.3 · **VOL** volume_vs_prior=1.08 volume_vs_avg50=0.91 volume_rank_60=31 cv_required=no. Base 2026-11-06 to 2026-11-23, $27.31 to $31.44; extension: close -2.3% vs its 20-SMA, -4.5% over 20 sessions.
- Chart reader: accepted, skip 4.5 (research_rotating); selection blockers: grade_not_admitted.
  - Reader's reason (commentary): The base is a clear downtrend, not a consolidation: the shaded region from early November through November 23 shows a sequence of lower highs and lower lows with wide, overlapping red bars, giving back 82% of the prior leg — the checklist records C as FAIL with giveback=0.82 and tightness=1.05, both well outside threshold. The prior leg itself is 59 sessions of only 11.5% gain with an efficiency ratio of 0.18, which is a slow, choppy grind rather than a persistent momentum advance. Bursting out of a declining base into a still-falling price structure is not a momentum burst setup.
  - Reader's main risk (commentary): The base is a downtrend with heavy giveback; any follow-through is likely to be absorbed by overhead supply from the October–November distribution zone near 29–31.
  - Reader's entry note (not the ticket): Skip if the open is below the burst close of 28.46 or if the first 30 minutes show no ability to hold above the prior day's high, confirming the base breakdown continues.
- Later gates: GREEN band fail, YELLOW band fail, veto pass, admission pass, reader `accepted`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $28.49; limit $28.52; stop $27.38 (burst_low, 4.00% under the limit); day-2 line $29.60; skip if it opens under $27.89; sell-half $30.80; risk a share at the limit $1.14; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 65 shares, $1,853.80; at the YELLOW size 32 shares, $912.64; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### CAH · Cardinal Health Inc. Common Stock · rank 1 · A+ 10.00 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $279.65 (2.82% from $271.97), open $270.88, high $280.35, low $269.30; volume 2,076,819 (1.04x the prior session, inside the near-volume band, 1.14x its 50-session average), dollar volume $580.8M; 3.9% over its 20-session average; route dollar (dollar_expansion); flags biotech.
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-0.31 · **L+** er=0.5 r2=0.8 leg_sessions=30 leg_gain_pct=21.6 · **Y+** breakouts_in_move=0 sessions_since_move_start=42 gain_since_move_start_pct=27 · **N+** prior_day_pct=-0.31 prior_range_pct=1.7 negative=yes narrow=yes median_range_pct=1.9 · **C** base_sessions=12 breakdowns=0 bursts_in_base=0 giveback=0.32 tightness=0.82 base_volume_vs_leg=0.91 base_volume_vs_avg=0.89 · **H+** close_pos=0.94 close_above_open=yes · **RE+** vs_prior_5=1.29 vs_prior_10=1.29 bar_range_pct=4 · **VOL** volume_vs_prior=1.04 volume_vs_avg50=1.14 volume_rank_60=12 cv_required=no. Base 2026-11-06 to 2026-11-23, $263.92 to $286.29; extension: close 3.9% vs its 20-SMA, 13.5% over 20 sessions.
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band pass, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $279.93; limit $280.52; stop $269.30 (burst_low, 4.00% under the limit); day-2 line $290.84; skip if it opens under $274.06; sell-half $302.96; risk a share at the limit $11.22; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 6 shares, $1,683.12; at the YELLOW size 3 shares, $841.56; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### OGS · ONE Gas Inc. Common Stock · rank 4 · A+ 10.00 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $82.85 (1.48% from $81.64), open $81.61, high $83.25, low $81.07; volume 503,900 (1.10x the prior session, 0.75x its 50-session average), dollar volume $41.7M; 1.8% over its 20-session average; route dollar (dollar_expansion).
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-0.07 · **L+** er=0.53 r2=0.96 leg_sessions=36 leg_gain_pct=17.2 · **Y+** breakouts_in_move=0 sessions_since_move_start=41 gain_since_move_start_pct=15.6 · **N+** prior_day_pct=-0.07 prior_range_pct=1.4 negative=yes narrow=yes median_range_pct=1.7 · **C** base_sessions=5 breakdowns=0 bursts_in_base=0 giveback=0.3 tightness=1 base_volume_vs_leg=1.13 base_volume_vs_avg=1.11 · **H** close_pos=0.82 close_above_open=yes · **RE** vs_prior_5=1 vs_prior_10=0.96 bar_range_pct=2.6 · **VOL** volume_vs_prior=1.1 volume_vs_avg50=0.75 volume_rank_60=47 cv_required=no. Base 2026-11-17 to 2026-11-23, $80.40 to $84.72; extension: close 1.8% vs its 20-SMA, 5.6% over 20 sessions.
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band pass, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $82.93; limit $84.44; stop $81.07 (burst_low, 3.99% under the limit); day-2 line $86.16; skip if it opens under $81.19; sell-half $90.37; risk a share at the limit $3.37; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 22 shares, $1,857.68; at the YELLOW size 11 shares, $928.84; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### MCK · McKesson Corporation Common Stock · rank 11 · A 10.00 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $1,078.09 (2.83% from $1,048.42), open $1,049.55, high $1,082.86, low $1,043.00; volume 842,900 (1.16x the prior session, 1.10x its 50-session average), dollar volume $908.7M; 2.3% over its 20-session average; route dollar (dollar_expansion); flags biotech.
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-1.96 · **L** er=0.33 r2=0.66 leg_sessions=55 leg_gain_pct=27.8 · **Y** breakouts_in_move=1 sessions_since_move_start=39 gain_since_move_start_pct=26.3 · **N** prior_day_pct=-1.96 prior_range_pct=2.1 negative=yes narrow=no median_range_pct=2 · **C** base_sessions=12 breakdowns=0 bursts_in_base=0 giveback=0.28 tightness=0.86 base_volume_vs_leg=0.8 base_volume_vs_avg=0.87 · **H** close_pos=0.88 close_above_open=yes · **RE+** vs_prior_5=1 vs_prior_10=1 bar_range_pct=3.7 · **VOL** volume_vs_prior=1.16 volume_vs_avg50=1.1 volume_rank_60=16 cv_required=no. Base 2026-11-06 to 2026-11-23, $1,042.86 to $1,121.50; extension: close 2.3% vs its 20-SMA, 11.5% over 20 sessions; prior breakouts worked 1 of 2 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $1,079.17; limit $1,086.45; stop $1,043.00 (burst_low, 4.00% under the limit); day-2 line $1,121.21; skip if it opens under $1,056.53; sell-half $1,173.37; risk a share at the limit $43.45; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 1 shares, $1,086.45; at the YELLOW size 0 shares, $0.00; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### AON · Aon plc Class A Ordinary Shares (Ireland) · rank 15 · A 8.50 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $342.86 (3.31% from $331.86), open $334.04, high $343.24, low $332.17; volume 1,132,422 (1.15x the prior session, 0.67x its 50-session average), dollar volume $388.3M; 2.7% over its 20-session average; route dollar (dollar_expansion).
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-0.36 · **L+** er=0.64 r2=0.94 leg_sessions=25 leg_gain_pct=27.8 · **Yx** breakouts_in_move=2 sessions_since_move_start=37 gain_since_move_start_pct=27.2 · **N** prior_day_pct=-0.36 prior_range_pct=2.1 negative=yes narrow=no median_range_pct=2.1 · **C** base_sessions=12 breakdowns=0 bursts_in_base=0 giveback=0.28 tightness=0.79 base_volume_vs_leg=0.52 base_volume_vs_avg=0.53 · **H+** close_pos=0.97 close_above_open=yes · **RE+** vs_prior_5=1.33 vs_prior_10=1.19 bar_range_pct=3.2 · **VOL** volume_vs_prior=1.15 volume_vs_avg50=0.67 volume_rank_60=47 cv_required=no. Base 2026-11-06 to 2026-11-23, $326.57 to $350.47; extension: close 2.7% vs its 20-SMA, 13.3% over 20 sessions; prior breakouts worked 2 of 4 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $343.20; limit $346.01; stop $332.17 (burst_low, 4.00% under the limit); day-2 line $356.57; skip if it opens under $336.00; sell-half $373.69; risk a share at the limit $13.84; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 5 shares, $1,730.05; at the YELLOW size 2 shares, $692.02; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### CRI · Carter's Inc. Common Stock · rank 19 · A 8.50 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $37.04 (4.28% from $35.52), open $35.78, high $37.07, low $35.69; volume 1,664,762 (1.04x the prior session, inside the near-volume band, 1.22x its 50-session average), dollar volume $61.7M; 9.1% over its 20-session average; route both (burst_route).
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-0.03 · **L** er=0.21 r2=0.62 leg_sessions=46 leg_gain_pct=27 · **Yx** breakouts_in_move=6 sessions_since_move_start=49 gain_since_move_start_pct=27.6 · **N+** prior_day_pct=-0.03 prior_range_pct=3.5 negative=yes narrow=no median_range_pct=4 · **C** base_sessions=3 breakdowns=1 bursts_in_base=0 giveback=0.25 tightness=0.9 base_volume_vs_leg=0.99 base_volume_vs_avg=0.98 · **H+** close_pos=0.98 close_above_open=yes · **REx** vs_prior_5=0.49 vs_prior_10=0.49 bar_range_pct=3.7 · **VOL** volume_vs_prior=1.04 volume_vs_avg50=1.22 volume_rank_60=16 cv_required=no. Base 2026-11-19 to 2026-11-23, $35.06 to $37.08; extension: close 9.1% vs its 20-SMA, 17.9% over 20 sessions; prior breakouts worked 1 of 4 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $37.08; limit $37.17; stop $35.69 (burst_low, 3.98% under the limit); day-2 line $38.52; skip if it opens under $36.30; sell-half $40.14; risk a share at the limit $1.48; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 50 shares, $1,858.50; at the YELLOW size 25 shares, $929.25; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### TSCO · Tractor Supply Company Common Stock · rank 26 · A 8.50 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $39.45 (5.00% from $37.57), open $37.85, high $39.49, low $37.56; volume 11,950,971 (1.28x the prior session, 0.97x its 50-session average), dollar volume $471.5M; 7.6% over its 20-session average; route both (burst_route).
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-2.26 · **L** er=0.37 r2=0.75 leg_sessions=34 leg_gain_pct=25.5 · **Yx** breakouts_in_move=2 sessions_since_move_start=37 gain_since_move_start_pct=26.9 · **N+** prior_day_pct=-2.26 prior_range_pct=2.9 negative=yes narrow=no median_range_pct=3.3 · **C** base_sessions=3 breakdowns=0 bursts_in_base=0 giveback=0.25 tightness=0.86 base_volume_vs_leg=0.78 base_volume_vs_avg=0.85 · **H+** close_pos=0.98 close_above_open=yes · **REx** vs_prior_5=0.91 vs_prior_10=0.91 bar_range_pct=4.9 · **VOL** volume_vs_prior=1.28 volume_vs_avg50=0.97 volume_rank_60=18 cv_required=no. Base 2026-11-19 to 2026-11-23, $37.28 to $39.71; extension: close 7.6% vs its 20-SMA, 22.4% over 20 sessions; prior breakouts worked 4 of 4 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $39.49; limit $40.13; stop $38.53 (half_range, 3.99% under the limit); day-2 line $41.03; skip if it opens under $38.66; sell-half $43.03; risk a share at the limit $1.60; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 46 shares, $1,845.98; at the YELLOW size 23 shares, $922.99; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### AZN · AstraZeneca PLC Ordinary Shares · rank 32 · A 8.00 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $183.20 (3.49% from $177.02), open $178.72, high $184.02, low $178.56; volume 1,858,644 (1.33x the prior session, 0.65x its 50-session average), dollar volume $340.5M; 0.4% over its 20-session average; route dollar (dollar_expansion); flags biotech, foreign.
- Checks: **2** up_run=1 up_closes=1 prior_day_pct=1.53 · **L+** er=0.57 r2=0.86 leg_sessions=18 leg_gain_pct=19.9 · **Y+** breakouts_in_move=0 sessions_since_move_start=30 gain_since_move_start_pct=17.6 · **N** prior_day_pct=1.53 prior_range_pct=1.9 negative=no narrow=yes median_range_pct=1.8 · **Cx** base_sessions=12 breakdowns=0 bursts_in_base=0 giveback=0.48 tightness=1 base_volume_vs_leg=0.6 base_volume_vs_avg=0.73 · **H** close_pos=0.85 close_above_open=yes · **RE+** vs_prior_5=1.25 vs_prior_10=1.25 bar_range_pct=3 · **VOL** volume_vs_prior=1.33 volume_vs_avg50=0.65 volume_rank_60=53 cv_required=no. Base 2026-11-06 to 2026-11-23, $174.03 to $192.64; extension: close 0.4% vs its 20-SMA, 7.7% over 20 sessions; prior breakouts worked 1 of 1 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $183.38; limit $186.00; stop $178.56 (burst_low, 4.00% under the limit); day-2 line $190.53; skip if it opens under $179.54; sell-half $199.83; risk a share at the limit $7.44; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 10 shares, $1,860.00; at the YELLOW size 5 shares, $930.00; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### BRO · Brown & Brown Inc. Common Stock · rank 34 · A 8.00 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $76.01 (4.51% from $72.73), open $73.25, high $76.12, low $73.17; volume 1,951,465 (1.14x the prior session, 0.77x its 50-session average), dollar volume $148.3M; 5.8% over its 20-session average; route both (burst_route).
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-0.47 · **L+** er=0.4 r2=0.71 leg_sessions=25 leg_gain_pct=24.2 · **Y** breakouts_in_move=1 sessions_since_move_start=37 gain_since_move_start_pct=26.9 · **N+** prior_day_pct=-0.47 prior_range_pct=1.3 negative=yes narrow=yes median_range_pct=3 · **Cx** base_sessions=12 breakdowns=0 bursts_in_base=0 giveback=0.36 tightness=0.96 base_volume_vs_leg=0.79 base_volume_vs_avg=0.84 · **H+** close_pos=0.96 close_above_open=yes · **RE** vs_prior_5=1.3 vs_prior_10=0.97 bar_range_pct=3.9 · **VOL** volume_vs_prior=1.14 volume_vs_avg50=0.77 volume_rank_60=38 cv_required=no. Base 2026-11-06 to 2026-11-23, $70.00 to $76.07; extension: close 5.8% vs its 20-SMA, 12.5% over 20 sessions; prior breakouts worked 1 of 3 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $76.09; limit $76.21; stop $73.17 (burst_low, 3.99% under the limit); day-2 line $79.05; skip if it opens under $74.49; sell-half $82.31; risk a share at the limit $3.04; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 24 shares, $1,829.04; at the YELLOW size 12 shares, $914.52; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### COR · Cencora Inc. Common Stock · rank 37 · A 8.00 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $349.68 (3.44% from $338.04), open $337.65, high $351.13, low $335.90; volume 1,608,178 (1.27x the prior session, 1.21x its 50-session average), dollar volume $562.3M; 1.8% over its 20-session average; route dollar (dollar_expansion); flags biotech.
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-0.31 · **L** er=0.36 r2=0.56 leg_sessions=27 leg_gain_pct=13.1 · **Y+** breakouts_in_move=0 sessions_since_move_start=39 gain_since_move_start_pct=16.5 · **N+** prior_day_pct=-0.31 prior_range_pct=1.4 negative=yes narrow=yes median_range_pct=2.2 · **Cx** base_sessions=12 breakdowns=0 bursts_in_base=0 giveback=0.45 tightness=0.97 base_volume_vs_leg=0.98 base_volume_vs_avg=1 · **H+** close_pos=0.9 close_above_open=yes · **RE+** vs_prior_5=1.38 vs_prior_10=1.38 bar_range_pct=4.4 · **VOL** volume_vs_prior=1.27 volume_vs_avg50=1.21 volume_rank_60=11 cv_required=no. Base 2026-11-06 to 2026-11-23, $332.67 to $363.95; extension: close 1.8% vs its 20-SMA, 7.5% over 20 sessions.
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $350.03; limit $357.82; stop $343.51 (half_range, 4.00% under the limit); day-2 line $363.67; skip if it opens under $342.69; sell-half $381.43; risk a share at the limit $14.31; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 5 shares, $1,789.10; at the YELLOW size 2 shares, $715.64; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### EMBC · Embecta Corp. Common Stock · rank 43 · A 8.00 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $8.08 (40.77% from $5.75), open $6.88, high $8.23, low $6.57; volume 6,986,936 (8.13x the prior session, 7.71x its 50-session average), dollar volume $56.5M; 26.9% over its 20-session average; route both (burst_route); flags biotech.
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-4.65 · **L** er=0.37 r2=0.68 leg_sessions=55 leg_gain_pct=96 · **Y+** breakouts_in_move=0 sessions_since_move_start=1 gain_since_move_start_pct=40.8 · **N** prior_day_pct=-4.65 prior_range_pct=10.6 negative=yes narrow=no median_range_pct=4.9 · **Cx** base_sessions=22 breakdowns=2 bursts_in_base=1 giveback=0.39 tightness=1 base_volume_vs_leg=0.63 base_volume_vs_avg=0.91 · **H+** close_pos=0.91 close_above_open=yes · **RE+** vs_prior_5=1.93 vs_prior_10=1.93 bar_range_pct=20.5 · **VOL+** volume_vs_prior=8.13 volume_vs_avg50=7.71 volume_rank_60=1 cv_required=yes. Base 2026-10-23 to 2026-11-23, $5.56 to $6.90; extension: close 26.9% vs its 20-SMA, 23.4% over 20 sessions; gain of 40.77% is 15% or more: the worst cell in the only event study, a 36% win rate and -9.3% at 20 sessions; prior breakouts worked 2 of 4 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $8.10; ticket withheld (no_room_above_the_trigger): no limit above the trigger keeps a structural stop inside the stop line; day-2 line $8.40; skip if it opens under $7.92.
- Plan rule refusal: ticket withheld: no limit above the $8.10 buy stop keeps a stop inside his 4% line — the burst day's low $6.57 caps the limit at $6.84, at or under that buy stop; the bar's midpoint $7.40 caps the limit at $7.70, at or under that buy stop; the setup stands, the ticket does not
- No ticket: market gate: the regime admits no new longs (stage `market`).

### ES · Eversource Energy (D/B/A) Common Stock · rank 44 · A 8.00 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $72.66 (1.69% from $71.45), open $71.24, high $72.98, low $71.09; volume 3,130,740 (1.06x the prior session, 1.04x its 50-session average), dollar volume $227.5M; 3.2% over its 20-session average; route dollar (dollar_expansion).
- Checks: **2+** up_run=0 up_closes=2 prior_day_pct=0.58 · **L+** er=0.45 r2=0.83 leg_sessions=29 leg_gain_pct=13.7 · **Y+** breakouts_in_move=0 sessions_since_move_start=41 gain_since_move_start_pct=14.8 · **N** prior_day_pct=0.58 prior_range_pct=1.8 negative=no narrow=yes median_range_pct=1.6 · **Cx** base_sessions=12 breakdowns=0 bursts_in_base=0 giveback=0.42 tightness=0.97 base_volume_vs_leg=1.04 base_volume_vs_avg=1.04 · **H** close_pos=0.83 close_above_open=yes · **RE+** vs_prior_5=1.37 vs_prior_10=1.08 bar_range_pct=2.6 · **VOL** volume_vs_prior=1.06 volume_vs_avg50=1.04 volume_rank_60=19 cv_required=no. Base 2026-11-06 to 2026-11-23, $68.71 to $73.05; extension: close 3.2% vs its 20-SMA, 7.2% over 20 sessions.
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $72.73; limit $74.05; stop $71.09 (burst_low, 4.00% under the limit); day-2 line $75.57; skip if it opens under $71.21; sell-half $79.26; risk a share at the limit $2.96; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 25 shares, $1,851.25; at the YELLOW size 12 shares, $888.60; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### IMXI · International Money Express Inc. Common Stock · rank 49 · A 8.00 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $5.46 (7.27% from $5.09), open $5.20, high $5.58, low $4.80; volume 3,051,296 (2.66x the prior session, 3.16x its 50-session average), dollar volume $16.7M; -21.7% over its 20-session average; route burst (burst_route).
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-7.96 · **L+** er=0.87 r2=0.83 leg_sessions=12 leg_gain_pct=19.9 · **Y+** breakouts_in_move=0 sessions_since_move_start=1 gain_since_move_start_pct=7.3 · **N** prior_day_pct=-7.96 prior_range_pct=16.7 negative=yes narrow=no median_range_pct=7.9 · **Cx** base_sessions=31 breakdowns=9 bursts_in_base=2 giveback=3.24 tightness=2.5 base_volume_vs_leg=1.58 base_volume_vs_avg=1.16 · **H** close_pos=0.85 close_above_open=yes · **REx** vs_prior_5=0.86 vs_prior_10=0.66 bar_range_pct=14.3 · **VOL+** volume_vs_prior=2.66 volume_vs_avg50=3.16 volume_rank_60=2 cv_required=yes. Base 2026-10-12 to 2026-11-23, $5.05 to $12.73; extension: close -21.7% vs its 20-SMA, -39.3% over 20 sessions; prior breakouts worked 1 of 3 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $5.48; ticket withheld (no_room_above_the_trigger): no limit above the trigger keeps a structural stop inside the stop line; day-2 line $5.68; skip if it opens under $5.35.
- Plan rule refusal: ticket withheld: no limit above the $5.48 buy stop keeps a stop inside his 4% line — the burst day's low $4.80 caps the limit at $5.00, at or under that buy stop; the bar's midpoint $5.19 caps the limit at $5.40, at or under that buy stop; the setup stands, the ticket does not
- No ticket: market gate: the regime admits no new longs (stage `market`).

### IP · International Paper Company Common Stock · rank 50 · A 8.00 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $30.62 (5.66% from $28.98), open $28.73, high $30.64, low $28.42; volume 12,622,716 (1.02x the prior session, inside the near-volume band, 2.17x its 50-session average), dollar volume $386.5M; -9.4% over its 20-session average; route both (burst_route).
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-4.55 · **L+** er=0.71 r2=0.68 leg_sessions=16 leg_gain_pct=15.4 · **Y+** breakouts_in_move=0 sessions_since_move_start=1 gain_since_move_start_pct=5.7 · **N** prior_day_pct=-4.55 prior_range_pct=7.2 negative=yes narrow=no median_range_pct=3.6 · **Cx** base_sessions=15 breakdowns=3 bursts_in_base=0 giveback=1.37 tightness=1.46 base_volume_vs_leg=0.99 base_volume_vs_avg=1 · **H+** close_pos=0.99 close_above_open=yes · **RE+** vs_prior_5=1.01 vs_prior_10=1.01 bar_range_pct=7.3 · **VOL+** volume_vs_prior=1.02 volume_vs_avg50=2.17 volume_rank_60=1 cv_required=no. Base 2026-11-03 to 2026-11-23, $28.94 to $37.18; extension: close -9.4% vs its 20-SMA, -8.3% over 20 sessions; prior breakouts worked 1 of 3 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $30.65; limit $30.76; stop $29.53 (half_range, 4.00% under the limit); day-2 line $31.84; skip if it opens under $30.01; sell-half $33.22; risk a share at the limit $1.23; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 60 shares, $1,845.60; at the YELLOW size 30 shares, $922.80; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### LILA · Liberty Latin America Ltd. Class A Common Stock · rank 52 · A 8.00 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $9.50 (7.34% from $8.85), open $8.85, high $9.52, low $8.81; volume 544,918 (1.43x the prior session, 1.41x its 50-session average), dollar volume $5.2M; 2.9% over its 20-session average; route burst (burst_route).
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-4.22 · **L+** er=0.61 r2=0.92 leg_sessions=14 leg_gain_pct=25.4 · **Y** breakouts_in_move=1 sessions_since_move_start=21 gain_since_move_start_pct=22.4 · **N** prior_day_pct=-4.22 prior_range_pct=7 negative=yes narrow=no median_range_pct=4.3 · **Cx** base_sessions=7 breakdowns=2 bursts_in_base=0 giveback=0.6 tightness=1.27 base_volume_vs_leg=0.81 base_volume_vs_avg=1.03 · **H+** close_pos=0.97 close_above_open=yes · **RE** vs_prior_5=1.06 vs_prior_10=0.69 bar_range_pct=7.5 · **VOL** volume_vs_prior=1.43 volume_vs_avg50=1.41 volume_rank_60=8 cv_required=no. Base 2026-11-13 to 2026-11-23, $8.74 to $10.33; extension: close 2.9% vs its 20-SMA, 20.1% over 20 sessions; prior breakouts worked 1 of 3 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $9.52; limit $9.54; stop $9.16 (half_range, 3.98% under the limit); day-2 line $9.88; skip if it opens under $9.31; sell-half $10.30; risk a share at the limit $0.38; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 197 shares, $1,879.38; at the YELLOW size 98 shares, $934.92; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### 6b. Compact rows (6 shown; 0 left out of this file; brief.json carries every one)

Every row here is RESEARCH ONLY (no SpicyStock ticket, no chart review). Research levels are derived from the recorded bar by the record's plan rules: `limit` is the highest fill the plan permits; stop basis L is the burst day's low, M the bar's midpoint; the day-2 line (too extended to enter) is the trigger plus the archived entry_above_pct and the skip-under line the trigger minus entry_below_pct (both exact in brief.json); `shares` is the model size under tonight's regime multiplier, then the same plan at full size; `refused` means the plan rule refused it; `*` after the volume ratio marks the near-volume band. Every row stopped at stage `market` (market gate: the regime admits no new longs) unless its ticker carries another in brackets. 

| ticker | gain % | vol x | $ vol M | ext % | grade | checks | trigger | limit | stop | sell-half | risk/sh | shares |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LTC | 2.97 | 1.15 | 24.2 | -0.4 | A 8 | 2+ L Y+ N Cx H+ RE VOL | 43.7 | 43.76 | 42.01L | 47.26 | 1.75 | 0/42 |
| MZTI | 4.19 | 1.03* | 28.2 | 0.1 | A 8 | 2+ L Y+ N+ Cx H+ RE+ VOL | 109.15 | 111.06 | 106.62M | 118.94 | 4.44 | 0/16 |
| NYT | 3.1 | 1.14 | 151.7 | 0.4 | A 8 | 2+ L Y+ N+ Cx H+ RE+ VOL | 70.51 | 71.7 | 68.84M | 76.83 | 2.86 | 0/26 |
| QSR | 2.48 | 1.02* | 194.3 | 0.6 | A 8 | 2 L+ Y N Cx H+ RE+ VOL | 75.65 | 76.61 | 73.55L | 82.44 | 3.06 | 0/24 |
| SOBO | 3.27 | 2.41 | 23.7 | -1.3 | A 8 | 2+ L Y+ N Cx H+ RE+ VOL | 32.9 | 33.51 | 32.17M | 35.86 | 1.34 | 0/55 |
| TM | -1.04 | 1.43 | 88.3 | 1 | A 8 | 2 L+ Y+ N Cx H+ RE+ VOL | 210.18 | 214.06 | 205.5L | 229.04 | 8.56 | 0/8 |

## 7. Research tail (814 names)

Every other reaction candidate: RESEARCH ONLY, no SpicyStock ticket and no levels. Tickers in the record's rank order, grouped by the one reason; a ticker whose final grade differs from its mechanical grade shows both.

- not admitted: dollar_no_expansion (61): CINF, KR, ROP, WELL, WTRG, AIZ, BYD, CCEP, PSA, AHR, AJG, ASO, AZO, CHD, EXR, FSV, HWKN, MRSH, OMC, OTIS, USFD, YUMC, ATO, ATR, AWK, BMO, CB, CL, COST, CPT, CRVL, CWEN, ED, ESNT, ESS, FRT, GEHC, JNJ, MA, MAR, NIC, NP, NSC, O, OHI, OKE, ORLY, PAYX, PEN, PGR, PLD, PNFP, PRKS, REG, RSG, RY, SPG, TJX, TRV, UNP, WFC
- mechanical grade B, below the trade band (233): LH, PG, WEC, CBOE, CME, VLTO, BDX, NXST, STE, VNT, AGL, ALL, CI, CPK, EWBC, EXE, HUM, ICE, KFY, KNSL, KO, LMT, MEOH, NNNN, NSP, NVS, PEP, RACE, SO, SRE, SSB, SU, TTWO, UNH, WTFC, ALLE, AXGN, BBIO, BIIB, DSGX, GILD, KNSA, KOD, PNR, RGA, RYAN, RYTM, TW, ULTA, USPH, VCEL, AAPL, ABBV, ABT, ACN, ADBE, AGIO, AIG, ALC, ALKS, ALNY, ALTG, AMCR, AMGN, AMLX, AMT, ANGI, ANNX, APD, APO, ASND, ATEX, AVBP, AVY, AVZO, AWI, AWR, BANF, BFAM, BHVN, BJ, BR, BRCB, CBRE, CCI, CHTR, CHYM, CLX, CNI, CP, CPAY, CTAS, CTEV, CTRE, CVS, CVSA, CVX, DEO, DFTX, DHR, DIS, DOV, DPZ, DRI, DT, DTE, DTM, DUK, DXCM, ECL, EGG, EGP, EHC, EPR, EPRX, ERAS, ERIE, ETON, EXPD, FANG, FDS, GD, GENB, GGG, GLBE, GM, GMED, GRMN, GSHD, GWW, GYRE, HELP, HIW, HON, HQY, HTO, HURN, IBM, IDA, IDXX, IMNM, IMTX, INDB, INSP, IPAR, IRTC, ISRG, ITW, JBHT, JCI, JLL, KARD, KMDA, KMTS, KRUS, KSS, LAMR, LINE, LLY, LOPE, LRN, LYV, M, MANU, MDLN, MELI, MMED, MMSI, MNPR, MRNA, MSCI, MSI, MSM, NAMS, NBIX, NHI, NKE, NNN, NRIX, NTRA, NUE, NVO, OBX, OFIX, OI, OLLI, OMCL, OMER, PBH, PFG, PHAT, PHVS, PKG, PM, POST, PRLD, PRU, PTCT, QUIT, RBA, RIGL, RITM, RJF, RNA, ROCK, ROK, RS, SBAC, SCI, SHOE, SJM, SLB, SLQT, SOLV, SPGI, STEP, STOK, SWX, TARS, TKO, TRUP, TXRH, UAL, UMBF, URI, UTHR, VRTX, VSTM, WING, WLK, WM, WTW, XRAY
- mechanical grade C, below the trade band (218): RPRX, SHAK, ANAB, BIOA, CTY, UNIT, AFRM, AGYS, AX, AXON, BALL, BCPC, BOOT, CMP, CMPR, CSV, DMRA, DOCU, EBS, ENSG, FERG, GVA, HUBS, JAZZ, LGIH, MCD, MKC, NJR, PEPG, PNC, PYPL, REF, SNDX, TLYS, TNET, WAL, WHD, WK, WSM, ENOV, MORN, TYL, GBFH, SCHW, A, AKAN, ALIT, AMP, ANF, ANRO, AOS, APP, ARCT, ARES, AXP, BA, BAM, BEPC, BGS, BKNG, BL, BLKB, BMI, BMRN, BMY, BRC, BTSG, BX, BXP, CACI, CD, CDNA, CMBT, CNM, COAG, CODX, COF, CPNG, CRH, CRTO, CRUS, CSL, CTNM, CTRN, DAL, DBD, DBX, DD, DG, DGX, DNLI, DNTH, DYN, ECVT, EEFT, ELMD, ENTA, ESTA, ESTC, EW, EWTX, FISV, FIVE, FLS, FSLR, FTNT, GKOS, GOLF, GPN, GRAL, GTLB, GWRE, H, HCA, HD, HII, HSY, ICUI, IMVT, INSW, IPI, IR, IRON, IT, KAI, KBH, KBR, KFRC, KROS, LDOS, LHX, LII, LIN, LIVN, LLYVK, LOW, LQDA, MAZE, MLM, MMM, MPAA, MSFT, MSGK, MTH, MTN, NDAQ, NFLX, NOC, NOW, NUS, OCTV, ODTX, PGEN, PHR, PINS, PLMR, PODD, POOL, PRAX, PRGS, PRME, PSIX, PVLA, QCOM, RCL, RDNW, REGN, RGLD, RGNX, RL, RNG, ROIV, RPM, RVTY, SEPN, SGP, SKY, SKYW, SLDB, SLGN, SNA, SPSC, SSD, SYK, SYRE, TEX, TGT, THO, TMO, TOST, TPR, TRAX, TRI, TRVI, TSLA, TXG, ULS, UPS, VAL, VEEV, VLGEA, VMC, VOYA, VRDN, VRSK, VRSN, VRTS, WAT, WD, WEX, WMT, WSO, XENE, XNCR, ZG, ZM, ZTS, ZYME
- quality veto: up_days (11): EG, ADC, CAR, CLNN, GH, TYRA, ELVN, MLTX, MSGR, WWB, CRAI
- quality veto: not_linear (163): ARMP, BSX, CSR, FR, MAA, MRK, MUSA, SION, SUI, TRGP, V, XRN, ELV, MPLT, SIND, VMI, MANH, TGTX, ATRA, BATRK, BBNX, BEAM, BNTC, BPOP, CADL, CHRW, CNC, COKE, COP, CRM, CYTK, DRUG, DSGN, DVA, ELS, EOLS, FDMT, FELE, FTH, GPC, GRBK, HHH, IDYA, IMMX, INBX, INCY, JANX, KMX, KRYS, KURA, LFVN, LGND, LLYVA, LMAT, MDGL, MTB, NBN, NGVT, NTR, NVCT, OFRM, PCVX, PTGX, RCUS, RNR, ROST, RXST, SDRL, SGI, SPHR, SRPT, STLD, STRA, STRO, TRDA, TRNO, TVTX, UHT, UNM, VIR, WFG, WMB, ZBIO, ABSI, BCC, CARR, COYA, CTSH, ELF, HCC, HP, JAGX, MLI, ORIC, RMD, SSNC, SYM, TECK, TRMB, VCTR, VERA, ALMR, APPF, AURA, BCO, CAVA, CCS, CF, CLH, COGT, CPA, CRL, CRSP, EL, FIRY, FLNC, FOX, FOXA, GOSS, GRRR, HONA, IFF, INTA, JPM, MDB, MOH, MSGE, NDSN, PANW, PBLS, PDS, PEGA, PI, PLTR, PLX, RDDT, RLAY, SDGR, SHW, SII, SRZN, SWKS, SXT, VEEA, VKTX, VOGX, WDAY, WIX, XYZ, AIN, BIRK, DECK, IOT, UA, URGN, EPAM, AKAM, CNXC, GRDN, ICLR, JBIO, LXEO, RDWR
- mechanical grade skip, below the trade band (125): ARVN, ARWR, ASMB, ATTO, AXSM, CELC, CGEM, GHRS, HSIC, KWR, MGTX, MLYS, MTRI, NANO, NFE, OCUL, QTTB, QURE, RAPP, UNF, VNDA, WVE, YARW, AMTM, CGON, COLM, COO, CROX, CVLT, DFH, DLTR, EXP, FTDR, IRD, JKHY, MHO, OC, OKUR, ORKA, PPG, RBLX, REPL, SGMT, SN, TFX, THC, TPG, VIK, ZBH, ACRE, ALG, ASTE, CBT, ETRA, IONS, MSA, NCT, PRTA, ALGN, ARQT, BAH, BLDR, BLK, CAMP, CCCC, CG, CSGP, DHI, DKS, DTIL, EFX, ETSY, EXPO, IBP, INSM, INTU, KLRA, KRRO, KTB, KYMR, LBRX, LULU, MANE, MBX, MCO, MLAB, MNDY, NGNE, PRCH, QTWO, RHI, SAIC, SEZL, SI, SIG, SITE, SPOT, SRRK, TEAM, TGLS, TOL, TREX, U, W, WYNN, CUE, EAT, GLUE, HROW, IAM, RVMD, UBER, UNCY, GLOB, LEN, LYEL, PHM, CRVS, OLMA, TSHA, GMRS, TNDM, RNAC, SABS, STC
- quality veto: up_days, not_linear (3): SFM, FRHC, MIRM

## 8. Setting up (anticipation): 4 listed, 10 also quiet

Of 857 momentum names, 277 quiet, 5 pass the coil checks. The record's own sentence over its list (the model's rule, not an instruction to the reader): "Buy only if it clears its trigger in the first 30 minutes on volume already above yesterday's pace; an open more than 2% above the close is gapped and needs a catalyst check before you buy."

### OGN · Organon & Co. Common Stock · listed 1 · RESEARCH ONLY: no SpicyStock ticket

- Measured: close $13.92 (0.14% today); setups DT; compress 0.67, tight days 5, quiet days 5, volume ratio 1.36, ADR 0.3%, extension 1.00; box $13.87 to $13.94 over 9 sessions (2026-11-12 to 2026-11-24).
- research levels (record; no order is offered at them): trigger $13.96; limit $14.10; stop $13.89 (lowest low of the last 3 sessions, 1.49% under the limit); gap check above $14.20; sell-half $15.08; risk a share at the limit $0.21; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 531 shares, $7,487.10; at the YELLOW size 357 shares, $5,033.70; no new longs: the size multiplier is 0.
- No ticket: breadth sizes new positions at zero tonight (stage `market`).
- Open-entry note (not the ticket): MOO/OPG at the open only for the top 2 names on the list, and only if it opens within +2% of $13.92
- Event registry: not_in_registry.

### RXO · RXO Inc. Common Stock · listed 2 · RESEARCH ONLY: no SpicyStock ticket

- Measured: close $28.88 (0.87% today); setups DT, TI65; compress 0.44, tight days 3, quiet days 4, volume ratio 1.24, ADR 1.7%, extension 1.03; box $28.19 to $28.94 over 9 sessions (2026-11-12 to 2026-11-24).
- research levels (record; no order is offered at them): trigger $28.97; limit $29.26; stop $28.24 (lowest low of the last 3 sessions, 3.49% under the limit); gap check above $29.46; sell-half $31.29; risk a share at the limit $1.02; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 73 shares, $2,135.98; at the YELLOW size 36 shares, $1,053.36; no new longs: the size multiplier is 0.
- No ticket: breadth sizes new positions at zero tonight (stage `market`).
- Open-entry note (not the ticket): MOO/OPG at the open only for the top 2 names on the list, and only if it opens within +2% of $28.88
- Event registry: not_in_registry.

### CART · Maplebear Inc. Common Stock · listed 3 · RESEARCH ONLY: no SpicyStock ticket

- Measured: close $57.35 (0.72% today); setups TI65; compress 0.55, tight days 4, quiet days 6, volume ratio 0.57, ADR 1.9%, extension 0.99; box $56.88 to $58.75 over 4 sessions (2026-11-19 to 2026-11-24).
- research levels (record; no order is offered at them): trigger $58.81; limit $59.40; stop $56.88 (lowest low of the last 3 sessions, 4.24% under the limit); gap check above $58.50; sell-half $63.51; risk a share at the limit $2.52; the plan rule refused it, so no model size is stated.
- No ticket: ticket withheld: at the $59.40 limit, the highest fill the ticket permits, the stop $56.88 is 4.24% away, past his 4% line; the setup stands, the ticket does not (stage `market`).
- Open-entry note (not the ticket): MOO/OPG at the open only for the top 2 names on the list, and only if it opens within +2% of $57.35
- Event registry: not_in_registry.

### LH · Labcorp Holdings Inc. Common Stock · listed 4 · RESEARCH ONLY: no SpicyStock ticket

- Measured: close $376.11 (0.95% today); setups TI65, MDT; compress 0.75, tight days 7, quiet days 6, volume ratio 0.90, ADR 2.6%, extension 1.02; box $363.00 to $378.88 over 10 sessions (2026-11-11 to 2026-11-24).
- research levels (record; no order is offered at them): trigger $379.26; limit $383.05; stop $366.33 (lowest low of the last 3 sessions, 4.36% under the limit); gap check above $383.63; sell-half $409.60; risk a share at the limit $16.72; the plan rule refused it, so no model size is stated.
- No ticket: ticket withheld: at the $383.05 limit, the highest fill the ticket permits, the stop $366.33 is 4.36% away, past his 4% line; the setup stands, the ticket does not (stage `market`).
- Open-entry note (not the ticket): MOO/OPG at the open only for the top 2 names on the list, and only if it opens within +2% of $376.11
- Event registry: not_in_registry.

Also quiet (not listed; no plan; every row RESEARCH ONLY: no SpicyStock ticket):

| ticker | setups | close | compress | tight | vol ratio | trigger | stop | risk % | why not listed |
|---|---|---|---|---|---|---|---|---|---|
| IBTA | DT/TI65/MDT | 55.07 | 0.75 | 6 | 0.71 | 56.70 | 52.84 | 7.3 | stop wider than 4% |
| CYRX | DT/TI65 | 19.50 | 0.95 | 5 | 0.79 | 20.04 | 18.82 | 6.5 | failed compress |
| UNFI | TI65 | 50.18 | 0.94 | 4 | 0.87 | 51.65 | 49.70 | 3.9 | failed compress |
| DINO | DT | 86.32 | 0.93 | 7 | 0.99 | 91.93 | 85.13 | 8.0 | failed compress |
| CORT | DT | 66.79 | 1.02 | 4 | 0.67 | 68.04 | 62.81 | 8.3 | failed compress |
| LAW | DT/TI65/MDT | 6.07 | 1.64 | 3 | 1.54 | 6.31 | 5.61 | 12.5 | failed compress |
| BOBS | TI65/MDT | 20.55 | 0.91 | 4 | 1.01 | 21.21 | 19.60 | 8.2 | failed compress |
| CROX | DT/TI65/MDT | 159.24 | 0.94 | 3 | 0.80 | 164.40 | 153.92 | 6.8 | failed compress |
| JRSH | DT/TI65/MDT | 7.30 | 1.48 | 3 | 1.11 | 7.83 | 6.95 | 12.7 | failed compress |
| JAKK | DT/TI65/MDT | 34.72 | 1.03 | 3 | 1.26 | 35.74 | 33.11 | 7.9 | failed compress |

## 9. Open model plans (0)

Open MODEL plans walked on daily (and retained minute) bars; not holdings.


## 10. Model record

- Scorecard: 22 plans in 60 sessions (2026-08-31 to 2026-11-24): 5 settled (2 wins, 3 losses, 0 even), 0 open, 0 pending, 1 uncertain, 14 not filled, 2 unmeasured; sum of R 0.43.
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

- Event registry (manual; known cash acquisitions only): 7 entries, last reviewed 2026-11-19, 5 days before the measured session 2026-11-24. 1 of 7 unresolved entries are past their review date: ACVA 40 days. Each stays blocked for a SpicyStock ticket; this record does not establish its current status. None of the 850 listed rows (836 bursts, 4 setting up, 10 also quiet) is in the registry. A stock that is not in the registry has not been cleared: SpicyStock reads no company news, and its earnings and SEC checks ran for 0 of the 848 listed names (they run for tickets only).
- Entries: MG (cash_acquisition, announced 2026-09-18, review due 2026-11-25); PRTH (cash_acquisition, announced 2026-09-21, review due 2026-12-17); ARX (cash_acquisition, announced 2026-08-13, review due 2026-12-17); BWIN (cash_acquisition, announced 2026-09-14, review due 2026-12-17); ACVA (cash_acquisition, announced 2026-09-10, review due 2026-10-15); ZIM (cash_acquisition, announced 2026-02-16, review due 2026-12-02); CCC (cash_acquisition, announced 2026-10-15, review due 2026-12-17).
- Status words: `known_event` = in the registry and blocked for a SpicyStock ticket; its manual review is current; `review_required` = in the registry and blocked for a SpicyStock ticket; its manual review is overdue; `not_in_registry` = not in the registry: NOT a clearance, nothing was checked.
- Earnings and 8-K check: status `not_applicable`; 0 ticket rows; 848 of 848 listed names had no check at all.
- Not checked by SpicyStock: company news and press releases, announced earnings dates, offerings and shelf takedowns, FDA and trial dates, halts outside the morning check, delisting notices beyond 8-K item 3.01 on tickets, index changes, lockup expiries, ex-dividend dates.

## 12. Rules

- Rules digest `e40195855de3`; without the universe membership identity `4ba4434239c5` (membership identity `f53941531295d065`): the record's digest nests the universe membership identity, so it moves on any night the selection's membership moves; `digest_without_membership` is the same digest with that identity removed, and moves only when an archived rule changes.
- pipeline: trade_grades ["A+", "A"], yellow_grades ["A+"], max_reads 12, reader_policy "accepted_required_v1", reader_refusal_fraction 0.25, reader_refusal_min 1, stale_tolerance_fraction 0.01, stale_sessions_max 5, min_coverage_fraction 0.5
- plan: entry_below_pct 2.0, entry_above_pct 4.0, skip_gap_pct 8.0, entry_window_minutes 30, assumed_slippage_pct 1.0, limit_rule "stop_constrained", sizing_basis "order_limit", max_stop_pct 4.0, ideal_stop_pct 2.0, stop_risk_multiplier 0.5, gain_ceiling_pct 15.0, extension_hazard_pct 20.0, hazard_multiplier 0.5, sell_half_pct 8.0, abnormal_day_pct 10.0, gap_exit_pct 20.0, sell_half_day 3, no_progress_day 3, trail_from_day 3, final_exit_day 5, allocation_policy "combined_stages_reserved_principal_v1"
- admission: version 1, policy "burst_route_or_dollar_expansion_v1"
- grading: reader_request_version 3
- record: scorecard_min_plans 20, scorecard_sessions 60

## 13. Bounds

- brief.json: 22 candidates in detail, 0 compact, 0 moved to the tail for size. Tickets and reviewed names are always detailed; of the rest, in the stated order, the largest multiple of 4 (or all) is detailed that keeps brief.json within 250000 bytes, and the others are compact rows; only if none can be detailed are compact rows cut, to the largest multiple of 10 that fits, the rest moving to the research tail.
- This file: 16 in detail, 6 compact rows, 0 compact rows left out, 0 research-tail names not named; reviewed names in their short form: no; model-record tables printed: no. Rule: tickets and reviewed names always in detail; then, to stay within 80000 bytes, the model-record tables are given up first, then the other names' detail (largest multiple of 2 that fits), then tail names (multiple of 50), then the reviewed names' check measurements and all but a cut reason of their reader sentences (the short form), then compact rows (multiple of 5); brief.json carries what this file leaves out.
- Research tail: 814 named, 0 left out (the first 4000: the admitted trade-band names moved out for size, then the rest by the record's rank order). Open plans left out: 0. Stale names left out: 0. The evening run's model-record block is carried whole when its canonical encoding is within 60000 bytes and the brief still fits with it; past that bound it is carried reduced (each plan row keeps its identity, result and account; the setups table is left out), and not at all if that does not fit either; brief.md prints its sentences and, while they fit, the first 30 rows and 12 columns of each of its tables. A copied sentence over 900 characters is cut and ends with an ellipsis.

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
