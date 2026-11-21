# SpicyStock daily brief: measured Fri 20 Nov 2026, plans for Mon 23 Nov 2026

> This is SpicyStock's daily brief: one evening publication's model output, derived from that publication's record and its pick ledger, with the model-record block the same evening run computed from its own bars carried in (section 10), and from nothing else, for an outside analyst to read in place of the full record.
> Check that it is current before using it: `status` must be `derived`, and the freshness rule in section 2 (`service.freshness_rule`) is applied with your own clock.
> Only the rows in section 5 (`tickets`) are published model tickets. Every other row is research only: its levels are reference arithmetic and SpicyStock offers no order for it.
> SpicyStock places, cancels and observes no order and reads no brokerage account. The owner decides and places every order.

**Model gate RED: size multiplier 0.0; 0 published model tickets for the applicable session.** The record's own cover sentence, written for its model tickets and not an instruction to the reader: "Stand aside."

## 1. Identity and binding

- Measured session: 2026-11-20 (open); plans are for **2026-11-23**, entry window 2026-11-23T09:30:00-05:00 to 2026-11-23T10:00:00-05:00 (America/New_York), full session closes 2026-11-23T16:00:00-05:00.
- Published 2026-11-21T03:59:48.154369+00:00 (run 44863821801, evening); rules version `577dec8b74e4`.
- Canonical record `data.json`: 7,340,916 bytes, SHA-256 `c88c9f246b47213be62584da1b7363a50e980a9d847ed9f2dc81467245eca6aa`.
- `picks.json`: 28,615 bytes, SHA-256 `7f232ab84aca7c3438f70c8110325660b3a40a339fb12f30d502883089b146b0`.
- This file renders `brief.json` (102,454 bytes, SHA-256 `1af7796e355f6703eda91a84aeab516ba9b204c479022a96851680842e090102`).
- Page https://spicychicken59.github.io/SpicyStock/ · record https://spicychicken59.github.io/SpicyStock/data.json · brief https://spicychicken59.github.io/SpicyStock/brief.json and https://spicychicken59.github.io/SpicyStock/brief.md · run log https://github.com/spicyChicken59/SpicyStock/actions/runs/44863821801.

## 2. Service state

- Run status: **ok**; problems: none; mail delivered.
- Delivery: Published 10:59 PM ET on Fri 20 Nov, 404.8 minutes after the measured session's completion (4:15 PM ET); after both scheduled slots (6:16 PM and 8:16 PM ET); before the next session's open (Mon 23 Nov, 9:30 AM ET). (slot `after_retry`, 404.8 minutes after completion).
- Next publication (`service.expected`): the next session is 2026-11-23; it completes at 2026-11-23T16:15:00-05:00; primary slot 2026-11-23T18:16:00-05:00; retry slot 2026-11-23T20:16:00-05:00; recovery limit 2026-11-24T09:30:00-05:00.
- Freshness rule (states: `newest`, `not_due`, `pending`, `late`, `missing`):
  - Freshness is the reader's own computation: this file carries no clock. Compare your own clock, as an instant with its UTC offset, with the instants in `service.expected`, in this order, and stop at the first that holds.
  - 1. Before `completion_at`: `newest`. The next session has not completed, so no record of a later session can exist yet. The same session can still be published again, and a later run can withdraw a ticket: before acting on a ticket, fetch the file again and compare `identity.canonical.sha256` with the copy the plan was built on.
  - 2. Before `primary_slot_at`: `not_due`. The next session has completed and its evening run is not yet due.
  - 3. Before `retry_slot_at`: `pending`. The first scheduled slot has passed and the retry slot has not.
  - 4. Before `recovery_until`: `late`. Both scheduled slots have passed; a delayed run can still publish the next session until that instant.
  - 5. Otherwise: `missing`. The service does not publish a session after the session that follows it has opened. If this is still the newest file the site serves, the next session was not published and every ticket in this file is expired.
  - From step 2 on, fetch the file again before relying on it: a newer one may exist. A field that is null has its reason in `service.expected.unknown`; without the instant a step needs, freshness is unknown and the file is research only.
  - Freshness is not permission. A ticket applies only from `identity.entry_window.opens_at` to its `cutoff_at`; after the cutoff it is over, whatever state this rule gives.
- Morning check: plans are for 2026-11-23; entry window 2026-11-23T09:30:00-05:00 to 2026-11-23T10:00:00-05:00; the morning collection starts at 2026-11-23T09:00:00-05:00. Receipt https://spicychicken59.github.io/SpicyStock/morning.json: A morning receipt belongs to this publication only when its `publication.data_sha256` equals `identity.canonical.sha256`. One generated before `window_opens_at` carries no quote from inside the entry window. The receipt is not part of this file: it lands the next morning, if a morning check runs.
- Inputs: Alpaca `sip`, split-adjusted 1Day bars, read by the run that began 2026-11-21T03:59:48.154369+00:00; 4,736 of 4,753 intended stocks ready (acceptance `degraded`); 3,437 measured, 17 stale.
- Stale tolerance: `tolerated` (17 stale against a limit of 47). Stale: ARKR, BEBE, BGM, BMHL, CPBI, DDC, ELLO, GSIW, IOR, ITP, LEGO, MAYS, NCEW, PHOE, RDIB, TOPP, WLYB.
- Seed: None of the 17 stale stocks is on the seed alone; each is in the directory this run selected from.
- Follow-up: The 2026-11-19 publication's 19 stocks without a 2026-11-19 bar, read again from this run's split-adjusted fetch: 19 now carry a 2026-11-19 bar (19 with zero volume); 14 would not have been listed; 5 fall under the $3 session-close policy. A late bar is the bar the provider served at this run's check; it never becomes a signal, plan or ticket.
- Minute bars: No plan's first day needed its minute bars tonight; minute bars are retained for 5 plans' first days.
- What the inputs do not establish: Why a stale stock had no session bar is not established; its session inputs are unknown, not a measured non-match, until a later run reads the session again. These bars are the provider's as read by the run that began at 2026-11-21T03:59:48.154369+00:00; a session's volume can be revised afterwards, and this file does not measure by how much. One price source: nothing cross-checks a close, a volume or a split. Bars are adjusted as `service.inputs.basis.adjustment` says and for nothing else. The universe is the selection named in `service.universe`, as fetched; it does not establish which stocks were listed during the session, and the record does not name the stocks that entered or left since the previous publication.
- Chart reader (claude-sonnet-4-6): 2 of 2 reads accepted, verdict `complete`. Chart reader cost: 2 calls for 2 names, 2 replies; 17,279 input tokens (9,159 uncached, 4,060 written to the cache, 4,060 read from it) and 1,196 output tokens, under claude-sonnet-4-6. Token counts as the API reported them; the record carries no price.
- Review selection (`account_feasible_first_research_v2`): 0 feasible, 2 requested of 12; selected: HTFL (research_ranked), SPB (research_rotating).
- Admission: 94 reaction candidates, 41 admitted to the trade band and the chart reads (28 by the 4% scan, 13 by the dollar scan on a range-expansion, higher-volume day); 53 came through the dollar scan alone without one and are research only. Of the 6 mechanical A-band names without a veto, 3 are admitted and 3 are not. Admission is read off the recorded discovery route and the checklist's own range-expansion and volume checks; it is never a grade, and the chart reader never sees a name it stops.
- Earnings and 8-K items (status `not_applicable`): Earnings: no ticket to check.
- Candidate funnel under a RED market: 94 reaction candidates discovered, 0 potentially usable (mechanical grade in the admitted band, no veto, discovery admitted), 0 reaction tickets. Reaction candidates stopped at: 94 market gate: the regime admits no new longs. Anticipation: 862 momentum names, 288 quiet, 8 passing the coil checks, 4 listed, 0 tickets. Listed setups stopped at: 4 market gate: the regime admits no new longs. A stage is where the record's own gates stopped a name; it is not a judgement of the setup and establishes no entry.
- Closest miss: PLMR came closest at B 8.5: fails close near the high.

## 3. Market regime

- Verdict **RED** for 2026-11-20: size multiplier 0.00; grades the regime admits to a ticket: none. The light is SpicyStock's gate for its own model tickets: an input to weigh, not an instruction to the reader.
- Recorded reason: down 4%: 704 >= the scaled alarm of 370.1 (700 of 6,500): major deterioration
- Recorded reason: 10-session ratio 0.51 (1269 up, 2470 down) < 1.0: more breakdowns than breakouts
- Recorded reason: 5-session ratio 0.18 (334 up, 1837 down) < 0.5 with 704 down vs 28 up today: a fast selling phase
- Counts over 3,437 measured stocks (4,753 intended, 4,736 with a session bar, 1,299 under the $3.00 session close floor): up 4% 28, down 4% 704; up/down 25% in a quarter 368/1,145; up/down 25% in a month 64/413; up/down 50% in a month 13/34; up/down 13% in 34 days 682/1,720; 26.5% above the 40-day average.
- Ratios: 5-session 0.18 (334 up, 1,837 down, unrounded 0.1818); 10-session 0.51 (1,269 up, 2,470 down, unrounded 0.5138). The rules compare the rounded number.

All five regime rules, in the order they are asked (universe 3,437 against a reference of 6,500). Count thresholds are the reference count times the stocks measured over the reference universe; that scaling is this project's own. Ratio thresholds are not scaled.

| rule | tier | measured | comparison | threshold tonight | reference | fired | decides | masked |
|---|---|---|---|---|---|---|---|---|
| down4_alarm | red | down4 704 | at or over | 370.1 | 700 of 6,500 | yes | yes | no |
| ratio_10d_red | red | ratio_10d 0.51 | under | 1 | 1, not scaled | yes | yes | no |
| ratio_5d_red | red | ratio_5d 0.18 | under, with more names down 4% than up 4% today | 0.5 | 0.5, not scaled | yes | yes | no |
| ratio_10d_yellow | yellow | ratio_10d 0.51 | under | 2 | 2, not scaled | yes | no | yes |
| up50_month_hot | yellow | up50_month 13 | over | 10.6 | 20 of 6,500 | yes | no | yes |

- GREEN needs all five rules quiet: fewer than 370.1 names down 4% today (it is 704); a 10-session ratio at or over 2 (it is 0.51: 1,269 up against 2,470 down); no 5-session ratio under 0.5 with more names down 4% than up 4% today (it is 0.18, with 704 down against 28 up); and no more than 10.6 names up 50% in a month (it is 13).
- Yellow by rounding (more ten-session breakdowns than breakouts while the rounded ratio is not under the red line): no. Near a line: no (the 10-session ratio is -0.49 from the red line and -1.49 from the yellow line; band 0.06, the band is this project's own label bound, the largest later re-reading of a published ratio seen through 17 November 2026; it is not a rule and gates nothing).

Breadth history (the newest 10 sessions of the record's own breadth history, each read again tonight over tonight's stocks: an earlier session's counts can differ from what its own night published): 2026-11-09 504/46 r10 1.14; 2026-11-10 82/146 r10 1.00; 2026-11-11 229/48 r10 1.02; 2026-11-12 49/260 r10 0.89; 2026-11-13 71/133 r10 1.02; 2026-11-16 48/429 r10 0.87; 2026-11-17 56/202 r10 0.80; 2026-11-18 159/166 r10 0.62; 2026-11-19 43/336 r10 0.75; 2026-11-20 28/704 r10 0.51.

## 4. Model account

- Model account (the model's configured sizing assumptions; not a brokerage balance): equity $30,000.00, risk 0.50% a trade, position cap 25.00%, 4 slots.
- Model allocation: next-session tickets would commit $0.00 of the configured $30,000.00; 0 of 4 slots.
- Cut: CART (anticipation, withheld): ticket withheld: at the $59.74 limit, the highest fill the ticket permits, the stop $57.19 is 4.27% away, past his 4% line; the setup stands, the ticket does not
- Cut: LH (anticipation, withheld): ticket withheld: at the $379.22 limit, the highest fill the ticket permits, the stop $363.00 is 4.28% away, past his 4% line; the setup stands, the ticket does not
- Cut: AZO (anticipation, withheld): ticket withheld: at the $3,395.79 limit, the highest fill the ticket permits, the stop $3,242.26 is 4.52% away, past his 4% line; the setup stands, the ticket does not
- Cut: OGN (anticipation, no_new_longs): breadth sizes new positions at zero tonight

## 5. Published model tickets (0)

None. The record published no model ticket for the applicable session.

## 6. Admitted trade-band candidates (3 of 6 in the band; 94 discovered)

Definition: reaction candidates whose mechanical grade is in the trade band (A+, A), with no quality veto, that the discovery admission admits; plus any other name with a published ticket or a selected chart review. Order: published tickets, then names selected for a chart review, then the rest; each in the record's rank order (grade, score descending, ticker). Model status: a row is `TICKET` only when the record published a model ticket for it (its order is in `tickets`); every other row is `RESEARCH ONLY: no SpicyStock ticket`. Later gates: the gates after the market gate, re-derived from the row's recorded fields so a RED night does not hide them; passing them is not a ticket: the stop rule, the event registry, sizing and the slot allocation follow, and the market gate stands.

Checklist, the same thresholds for every name. **2** not up two days in a row: up_run <= 1, counting days above +1.0%; veto at 3+ up closes of any size (weight 1.5). **L** linearity of the prior leg: ER >= 0.4 or R2 >= 0.55 (both for A+); failing is a veto (weight 2.0). **Y** young trend: first or second breakout: prior breakouts since the move started <= 1 (0 for A+) (weight 1.5). **N** narrow or negative day before: prior day negative or range < 2.0% (A+: negative and under its 20-session median range) (weight 1.5). **C** consolidation quality: base 3-20 sessions, breakdowns <= 1, giveback <= 0.34, tightness <= 1.0 (A+: 0 breakdowns, 0 bursts inside, giveback <= 0.25, tightness <= 0.7, base volume under the leg's and the 50-session average) (weight 2.0). **H** close near the high: close_pos >= 0.8 and close > open (A+ >= 0.9; partial from 0.7) (weight 1.5). **RE** range expansion: today's range over the largest of the prior 5 >= 1.0 (A+: also over the prior 10) (recorded, no weight). **VOL** higher volume: volume > prior session (A+: rank <= 3 of the last 60); a base over 21 sessions also needs >= 1.5x the 50-session average (recorded, no weight).
Check marks: letter then + (pass at the A+ level), nothing (pass), ~ (partial), x (fail), ? (not measured).

Hold days for a plan entered on the applicable session: day 1 = 2026-11-23, day 2 = 2026-11-24, day 3 = 2026-11-25, day 4 = 2026-11-27, day 5 = 2026-11-30. The model's exit rules (source B Bonde, P this project, T a third party's test): [B] when same or next day, the price reaches the sell-half level (+8% from the planned entry): sell half and move the stop to 25-50 cents under that day's high. [B] when any single day closes at or above the abnormal-close level (+10%): take at least partial profit and move the stop up to protect the rest. [B] when it opens at or above the gap-exit level (+20%) after entry: sell at the open (or pre-market). [B] when the close of day 1: the stop rises to the entry day's low if that is above the stop. [B] when day 3 close: sell at least half at the close. [B] when day 3 closes at or below the planned entry: exit: no follow-through. [P] when from the close of day 3: raise the stop to each day's low (it never moves down). [B] when day 5 close: exit the remainder into strength. [B] when the protective stop at the stop is a stop-market order, live intraday from the moment the buy fills: if it is somehow not filled, exit on any close below it. [T] when day 2 is green: do not move the stop to break-even before day 5 just because it is green (theStrat Lab EP9M backtest: the win rate collapses from 29.8% to 7.25%; delaying to day 5 restores it); the +8% raise above is a different rule.

Page for any ticker here: https://spicychicken59.github.io/SpicyStock/#/explore/bursts/<TICKER> (setting-up names: the same with `setting-up` in place of `bursts`). Near-volume band: 6 of the discovered bursts have a volume within 0.05 of the previous session's (the burst's volume is within this fraction of the previous session's, so its higher-volume check can flip on the provider's later corrections; the bound is this project's own label, not a rule).

### 6a. In detail (3 of 3 listed: every ticket and reviewed name, then the first 1 others)

### SPB · Spectrum Brands Holdings Inc. Common Stock · rank 44 · A 8.00, final C · reviewed · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $80.65 (6.30% from $75.87), open $76.26, high $80.82, low $76.26; volume 655,196 (1.92x the prior session, 1.82x its 50-session average), dollar volume $52.8M; -4.6% over its 20-session average; route both (burst_route).
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-7.52 · **L+** er=0.51 r2=0.74 leg_sessions=23 leg_gain_pct=20.5 · **Y+** breakouts_in_move=0 sessions_since_move_start=1 gain_since_move_start_pct=6.3 · **N** prior_day_pct=-7.52 prior_range_pct=7.6 negative=yes narrow=no median_range_pct=3.5 · **Cx** base_sessions=11 breakdowns=2 bursts_in_base=0 giveback=0.96 tightness=1.81 base_volume_vs_leg=1.31 base_volume_vs_avg=1.28 · **H+** close_pos=0.96 close_above_open=yes · **REx** vs_prior_5=0.75 vs_prior_10=0.75 bar_range_pct=5.7 · **VOL+** volume_vs_prior=1.92 volume_vs_avg50=1.82 volume_rank_60=3 cv_required=no. Base 2026-11-05 to 2026-11-19, $75.86 to $94.25; extension: close -4.6% vs its 20-SMA, 1.0% over 20 sessions; prior breakouts worked 1 of 2 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: accepted, C 5.5 (research_rotating); selection blockers: grade_not_admitted.
  - Reader's reason (commentary): The consolidation box (Nov 5–19) contains two 4%-plus breakdowns and a giveback of 0.96 — meaning the base surrendered virtually the entire prior leg gain — making it a declining, wide structure rather than a tight orderly pause; the chart confirms this with visibly wide, overlapping red bars that undercut each other repeatedly inside the shaded region. The burst bar itself is not the widest of the last five sessions (RE FAIL, vs_prior_5=0.75), so the range expansion that defines a momentum burst is absent. These two independent failures — a structurally broken base and no genuine range expansion — together push the setup well below A quality.
  - Reader's main risk (commentary): The base gave back nearly the entire prior leg and contains two large breakdowns, so there is no compressed energy to release and the burst bar is not a true expansion.
  - Reader's entry note (not the ticket): Skip if the open is below the burst-day close (~80.65) or if the first 30 minutes show immediate selling pressure with no ability to hold the prior day's low.
- Later gates: GREEN band fail, YELLOW band fail, veto pass, admission pass, reader `accepted`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $80.73; limit $81.81; stop $78.54 (half_range, 4.00% under the limit); day-2 line $83.88; skip if it opens under $79.04; sell-half $87.98; risk a share at the limit $3.27; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 22 shares, $1,799.82; at the YELLOW size 11 shares, $899.91; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### HTFL · Heartflow Inc. Common Stock · rank 65 · A 8.00, final skip · reviewed · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $46.69 (4.62% from $44.63), open $43.87, high $47.16, low $43.78; volume 1,891,230 (1.48x the prior session, 1.03x its 50-session average), dollar volume $88.3M; -13.1% over its 20-session average; route both (burst_route); flags biotech.
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-2.75 · **L** er=0.21 r2=0.62 leg_sessions=45 leg_gain_pct=29.9 · **Y+** breakouts_in_move=0 sessions_since_move_start=1 gain_since_move_start_pct=4.6 · **N** prior_day_pct=-2.75 prior_range_pct=7 negative=yes narrow=no median_range_pct=5.5 · **Cx** base_sessions=6 breakdowns=1 bursts_in_base=0 giveback=1.07 tightness=1.58 base_volume_vs_leg=1.28 base_volume_vs_avg=1.24 · **H** close_pos=0.86 close_above_open=yes · **REx** vs_prior_5=0.34 vs_prior_10=0.34 bar_range_pct=7.2 · **VOL** volume_vs_prior=1.48 volume_vs_avg50=1.03 volume_rank_60=20 cv_required=no. Base 2026-11-12 to 2026-11-19, $44.37 to $60.66; extension: close -13.1% vs its 20-SMA, -17.7% over 20 sessions; prior breakouts worked 3 of 4 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: accepted, skip 4.5 (research_ranked); selection blockers: grade_not_admitted.
  - Reader's reason (commentary): The base recorded a giveback of 1.07 (the entire prior leg was retraced inside the consolidation window) and tightness of 1.58 against a 1.0 threshold, and the chart confirms this: the shaded base region shows wide, overlapping red bars cascading from ~60 down to ~44, a clear declining structure rather than an orderly consolidation. RE also fails with the burst bar at only 0.34x the prior 5-session range, meaning the signal bar is not even the widest of the recent sessions — the expansion is not genuine.
  - Reader's main risk (commentary): The base is a visible downtrend with heavy giveback, not a tight consolidation, so any follow-through is fighting against a broken structure and significant overhead supply from prior trading between $55–$60.
  - Reader's entry note (not the ticket): Skip if the open gaps below the burst close of 46.69 or if the first 30 minutes show continued selling pressure given the broken base structure.
- Later gates: GREEN band fail, YELLOW band fail, veto pass, admission pass, reader `accepted`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $46.74; limit $47.36; stop $45.47 (half_range, 3.99% under the limit); day-2 line $48.56; skip if it opens under $45.76; sell-half $50.93; risk a share at the limit $1.89; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 39 shares, $1,847.04; at the YELLOW size 19 shares, $899.84; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### LSAK · Lesaka Technologies Inc. Common Stock · rank 3 · A 8.00 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $3.14 (5.37% from $2.98), open $2.93, high $3.21, low $2.73; volume 790,267 (2.27x the prior session, 3.53x its 50-session average), dollar volume $2.5M; -13.2% over its 20-session average; route burst (burst_route); flags foreign.
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-10.78 · **L+** er=0.77 r2=0.9 leg_sessions=10 leg_gain_pct=19.1 · **Y+** breakouts_in_move=0 sessions_since_move_start=1 gain_since_move_start_pct=5.4 · **N** prior_day_pct=-10.78 prior_range_pct=14.8 negative=yes narrow=no median_range_pct=4.8 · **Cx** base_sessions=28 breakdowns=6 bursts_in_base=0 giveback=2.34 tightness=1.44 base_volume_vs_leg=0.67 base_volume_vs_avg=0.92 · **H** close_pos=0.85 close_above_open=yes · **RE+** vs_prior_5=1.03 vs_prior_10=1.03 bar_range_pct=15.3 · **VOL+** volume_vs_prior=2.27 volume_vs_avg50=3.53 volume_rank_60=2 cv_required=yes. Base 2026-10-13 to 2026-11-19, $2.94 to $4.98; extension: close -13.2% vs its 20-SMA, -22.9% over 20 sessions; price under $5: explosive, wider stops; prior breakouts worked 2 of 4 (closed higher 3 sessions later, last 4 in 60 sessions); first leg of 19.1% in 10 sessions: his '15% plus in 10 days or less'.
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $3.16; ticket withheld (no_room_above_the_trigger): no limit above the trigger keeps a structural stop inside the stop line; day-2 line $3.27; skip if it opens under $3.08.
- Plan rule refusal: ticket withheld: no limit above the $3.16 buy stop keeps a stop inside his 4% line — the burst day's low $2.73 caps the limit at $2.84, at or under that buy stop; the bar's midpoint $2.97 caps the limit at $3.09, at or under that buy stop; the setup stands, the ticket does not
- No ticket: market gate: the regime admits no new longs (stage `market`).

### 6b. Compact rows (0 shown; 0 left out of this file; brief.json carries every one)

Every row here is RESEARCH ONLY (no SpicyStock ticket, no chart review). Research levels are derived from the recorded bar by the record's plan rules: `limit` is the highest fill the plan permits; stop basis L is the burst day's low, M the bar's midpoint; the day-2 line (too extended to enter) is the trigger plus the archived entry_above_pct and the skip-under line the trigger minus entry_below_pct (both exact in brief.json); `shares` is the model size under tonight's regime multiplier, then the same plan at full size; `refused` means the plan rule refused it; `*` after the volume ratio marks the near-volume band. 

## 7. Research tail (91 names)

Every other reaction candidate: RESEARCH ONLY, no SpicyStock ticket and no levels. Tickers in the record's rank order, grouped by the one reason; a ticker whose final grade differs from its mechanical grade shows both.

- not admitted: dollar_no_expansion (3): DBD, EFOR, NJR
- mechanical grade B, below the trade band (39): PLMR, EVCM, FLNT, NUTX, PLSE, SIGI, VEEV, YSWY, KVYO, TYL, ADUS, AEMD, ATRC, BKE, BLLN, CALM, CVX, DTIL, ESTA, GWRE, HUBS, HURN, KNSL, MELI, MNDY, MPC, NSP, NTLA, PRK, PXLW, RCI, RKT, SBAC, SPSC, TEAM, TGLS, USPH, WST, XOM
- mechanical grade C, below the trade band (20): HDB, PSQL, GPN, HCA, MSGR, BNAI, PSMT, AKAN, AMT, APPN, BGS, CAR, CBLL, ECO, GH, GLOB, RBLX, TMUS, VOR, WING
- quality veto: not_linear (19): IPAR, NHC, OPTX, TDS, CRSP, DVA, GAP, INTA, LGND, ROST, UHS, WDAY, BORR, COP, EVH, FRHC, LB, LNG, RDNT
- quality veto: up_days (2): XPEL, LYCA
- mechanical grade skip, below the trade band (7): STC, CRAI, DNTH, BRVE, CTY, FICO, KRSA
- quality veto: up_days, not_linear (1): MIRM

## 8. Setting up (anticipation): 4 listed, 10 also quiet

Of 862 momentum names, 288 quiet, 8 pass the coil checks. The record's own sentence over its list (the model's rule, not an instruction to the reader): "Buy only if it clears its trigger in the first 30 minutes on volume already above yesterday's pace; an open more than 2% above the close is gapped and needs a catalyst check before you buy."

### CART · Maplebear Inc. Common Stock · listed 1 · RESEARCH ONLY: no SpicyStock ticket

- Measured: close $57.31 (-0.92% today); setups TI65; compress 0.44, tight days 9, quiet days 7, volume ratio 0.73, ADR 3.1%, extension 0.98; box $57.19 to $59.09 over 10 sessions (2026-11-09 to 2026-11-20).
- research levels (record; no order is offered at them): trigger $59.15; limit $59.74; stop $57.19 (lowest low of the last 3 sessions, 4.27% under the limit); gap check above $58.46; sell-half $63.88; risk a share at the limit $2.55; the plan rule refused it, so no model size is stated.
- No ticket: ticket withheld: at the $59.74 limit, the highest fill the ticket permits, the stop $57.19 is 4.27% away, past his 4% line; the setup stands, the ticket does not (stage `market`).
- Open-entry note (not the ticket): MOO/OPG at the open only for the top 2 names on the list, and only if it opens within +2% of $57.31
- Event registry: not_in_registry.

### LH · Labcorp Holdings Inc. Common Stock · listed 2 · RESEARCH ONLY: no SpicyStock ticket

- Measured: close $367.13 (-0.47% today); setups TI65; compress 0.60, tight days 7, quiet days 7, volume ratio 0.93, ADR 2.6%, extension 1.01; box $363.00 to $375.10 over 10 sessions (2026-11-09 to 2026-11-20).
- research levels (record; no order is offered at them): trigger $375.47; limit $379.22; stop $363.00 (lowest low of the last 3 sessions, 4.28% under the limit); gap check above $374.47; sell-half $405.51; risk a share at the limit $16.22; the plan rule refused it, so no model size is stated.
- No ticket: ticket withheld: at the $379.22 limit, the highest fill the ticket permits, the stop $363.00 is 4.28% away, past his 4% line; the setup stands, the ticket does not (stage `market`).
- Open-entry note (not the ticket): MOO/OPG at the open only for the top 2 names on the list, and only if it opens within +2% of $367.13
- Event registry: not_in_registry.

### AZO · AutoZone Inc. Common Stock · listed 3 · RESEARCH ONLY: no SpicyStock ticket

- Measured: close $3,255.43 (-0.67% today); setups TI65; compress 0.75, tight days 3, quiet days 5, volume ratio 0.63, ADR 2.2%, extension 1.01; box $3,235.16 to $3,358.91 over 6 sessions (2026-11-13 to 2026-11-20).
- research levels (record; no order is offered at them): trigger $3,362.17; limit $3,395.79; stop $3,242.26 (lowest low of the last 3 sessions, 4.52% under the limit); gap check above $3,320.54; sell-half $3,631.14; risk a share at the limit $153.53; the plan rule refused it, so no model size is stated.
- No ticket: ticket withheld: at the $3,395.79 limit, the highest fill the ticket permits, the stop $3,242.26 is 4.52% away, past his 4% line; the setup stands, the ticket does not (stage `market`).
- Open-entry note (not the ticket): MOO/OPG at the open only for the top 2 names on the list, and only if it opens within +2% of $3,255.43
- Event registry: not_in_registry.

### OGN · Organon & Co. Common Stock · listed 4 · RESEARCH ONLY: no SpicyStock ticket

- Measured: close $13.89 (-0.14% today); setups DT; compress 0.67, tight days 3, quiet days 5, volume ratio 1.47, ADR 0.3%, extension 1.00; box $13.87 to $13.94 over 7 sessions (2026-11-12 to 2026-11-20).
- research levels (record; no order is offered at them): trigger $13.96; limit $14.10; stop $13.88 (lowest low of the last 3 sessions, 1.56% under the limit); gap check above $14.17; sell-half $15.08; risk a share at the limit $0.22; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 531 shares, $7,487.10; at the YELLOW size 340 shares, $4,794.00; no new longs: the size multiplier is 0.
- No ticket: breadth sizes new positions at zero tonight (stage `market`).
- Open-entry note (not the ticket): MOO/OPG at the open only for the top 2 names on the list, and only if it opens within +2% of $13.89
- Event registry: not_in_registry.

Also quiet (not listed; no plan; every row RESEARCH ONLY: no SpicyStock ticket):

| ticker | setups | close | compress | tight | vol ratio | trigger | stop | risk % | why not listed |
|---|---|---|---|---|---|---|---|---|---|
| CBOE | TI65/MDT | 357.71 | 0.68 | 3 | 0.85 | 370.36 | 354.08 | 4.6 | stop wider than 4% |
| MANH | DT/TI65/MDT | 243.00 | 0.71 | 5 | 0.71 | 255.24 | 242.83 | 5.1 | stop wider than 4% |
| HCSG | TI65 | 24.72 | 0.70 | 6 | 0.75 | 25.72 | 24.50 | 5.0 | stop wider than 4% |
| TASK | DT/TI65/MDT | 8.72 | 0.70 | 3 | 0.51 | 9.22 | 8.44 | 9.2 | stop wider than 4% |
| KNSA | DT/TI65/MDT | 93.90 | 0.77 | 7 | 0.60 | 99.40 | 92.68 | 7.3 | failed compress |
| SGRY | DT/TI65/MDT | 26.78 | 0.31 | 0 | 0.50 | 27.10 | 26.58 | 2.0 | failed tight |
| KOD | DT/TI65/MDT | 97.17 | 0.97 | 3 | 0.36 | 104.46 | 95.58 | 9.3 | failed compress |
| CRCT | DT/TI65/MDT | 8.35 | 1.15 | 4 | 1.21 | 8.96 | 8.09 | 10.8 | failed compress |
| GKOS | DT/TI65/MDT | 237.31 | 0.84 | 6 | 0.68 | 250.85 | 231.61 | 8.3 | failed compress |
| PGNY | DT/TI65/MDT | 35.71 | 0.84 | 5 | 0.89 | 37.25 | 34.94 | 6.6 | failed compress |

## 9. Open model plans (4)

Open MODEL plans walked on daily (and retained minute) bars; not holdings.

- **CART** (anticipation, picked 2026-11-13, red): status `not_filled`, day 1; trigger $59.82, limit $60.42, stop $58.20; 16 shares (16 remaining); last close $58.13 on 2026-11-16. The record's own sentence for its model plan, not an instruction to the reader: "Day 1 (2026-11-16): never reached the $59.82 trigger (high $59.00): the day order expired. Nothing to hold."
- **CBC** (anticipation, picked 2026-11-13, red): status `not_filled`, day 1; trigger $38.81, limit $39.20, stop $37.81; 26 shares (26 remaining); last close $38.55 on 2026-11-16. The record's own sentence for its model plan, not an instruction to the reader: "Day 1 (2026-11-16): never reached the $38.81 trigger (high $38.73): the day order expired. Nothing to hold."
- **HZO** (anticipation, picked 2026-11-13, red): status `not_filled`, day 1; trigger $52.94, limit $53.47, stop $52.76; 105 shares (105 remaining); last close $52.81 on 2026-11-16. The record's own sentence for its model plan, not an instruction to the reader: "Day 1 (2026-11-16): never reached the $52.94 trigger (high $52.83): the day order expired. Nothing to hold."
- **MFIC** (anticipation, picked 2026-11-13, red): status `not_filled`, day 1; trigger $10.42, limit $10.52, stop $10.13; 96 shares (96 remaining); last close $10.14 on 2026-11-16. The record's own sentence for its model plan, not an instruction to the reader: "Day 1 (2026-11-16): never reached the $10.42 trigger (high $10.22): the day order expired. Nothing to hold."

## 10. Model record

- Scorecard: 22 plans in 60 sessions (2026-08-27 to 2026-11-20): 5 settled (2 wins, 3 losses, 0 even), 0 open, 0 pending, 1 uncertain, 14 not filled, 2 unmeasured; sum of R 0.43.
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

Model record, plans (22 of 22 rows, 12 of 34 columns; brief.json carries every one):

| picked | ticker | kind | shares | bucket | r | model_usd | issued_equity | account_basis | issue_no | issues | withdrawn |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-08 | MG | anticipation | 16 | not_filled | n/a | n/a | 10000 | seed | 1 | 1 | yes |
| 2026-10-08 | SN | anticipation | 1 | settled | 0.41 | 2.24 | 10000 | seed | 1 | 1 | yes |
| 2026-10-09 | ZIM | anticipation | 2 | not_filled | n/a | n/a | 2000 | seed | 1 | 1 | yes |
| 2026-10-27 | EXEL | anticipation | 1 | settled | 3.02 | 5.25 | 2000 | seed | 1 | 1 | no |
| 2026-10-27 | OGN | anticipation | 22 | not_filled | n/a | n/a | 2000 | seed | 1 | 2 | no |
| 2026-10-28 | MCS | anticipation | 2 | uncertain | n/a | n/a | 2000 | seed | 1 | 1 | no |
| 2026-10-28 | OGN | anticipation | 22 | not_filled | n/a | n/a | 2000 | seed | 2 | 2 | no |
| 2026-10-29 | PSNL | anticipation | 4 | not_filled | n/a | n/a | 2000 | seed | 1 | 1 | no |
| 2026-10-29 | QGEN | anticipation | 1 | not_filled | n/a | n/a | 2000 | seed | 1 | 1 | no |
| 2026-11-02 | ESRT | anticipation | 12 | not_filled | n/a | n/a | 2000 | seed | 1 | 1 | no |
| 2026-11-04 | HQY | burst | 8 | settled | -1 | -30.48 | 30000 | seed | 1 | 1 | no |
| 2026-11-04 | RCBC | burst | 15 | settled | -1 | -30.15 | 30000 | seed | 1 | 1 | no |
| 2026-11-04 | VIK | burst | 10 | settled | -1 | -30 | 30000 | seed | 1 | 1 | no |
| 2026-11-09 | MFIC | anticipation | 104 | not_filled | n/a | n/a | 30000 | seed | 1 | 4 | no |
| 2026-11-10 | MFIC | anticipation | 110 | not_filled | n/a | n/a | 30000 | seed | 2 | 4 | no |
| 2026-11-10 | UTZ | anticipation | 375 | unmeasured | n/a | n/a | 30000 | seed | 1 | 2 | no |
| 2026-11-11 | MFIC | anticipation | 117 | not_filled | n/a | n/a | 30000 | seed | 3 | 4 | no |
| 2026-11-11 | UTZ | anticipation | 375 | unmeasured | n/a | n/a | 30000 | seed | 2 | 2 | no |
| 2026-11-13 | CART | anticipation | 16 | not_filled | n/a | n/a | 30000 | seed | 1 | 1 | no |
| 2026-11-13 | CBC | anticipation | 26 | not_filled | n/a | n/a | 30000 | seed | 1 | 1 | no |
| 2026-11-13 | HZO | anticipation | 105 | not_filled | n/a | n/a | 30000 | seed | 1 | 1 | no |
| 2026-11-13 | MFIC | anticipation | 96 | not_filled | n/a | n/a | 30000 | seed | 4 | 4 | no |

Model record, setups (17 of 17 rows; brief.json carries every one):

| ticker | kind | bucket | r | issues | tickets | setup | first | last | changed |
|---|---|---|---|---|---|---|---|---|---|
| MG | anticipation | not_filled | n/a | 1 | ["2026-10-08"] | anticipation:MG:2026-10-08 | 2026-10-08 | 2026-10-08 | [] |
| SN | anticipation | settled | 0.41 | 1 | ["2026-10-08"] | anticipation:SN:2026-10-08 | 2026-10-08 | 2026-10-08 | [] |
| ZIM | anticipation | not_filled | n/a | 1 | ["2026-10-09"] | anticipation:ZIM:2026-10-09 | 2026-10-09 | 2026-10-09 | [] |
| EXEL | anticipation | settled | 3.02 | 1 | ["2026-10-27"] | anticipation:EXEL:2026-10-27 | 2026-10-27 | 2026-10-27 | [] |
| OGN | anticipation | not_filled | n/a | 2 | ["2026-10-27","2026-10-28"] | anticipation:OGN:2026-10-27 | 2026-10-27 | 2026-10-28 | [[]] |
| MCS | anticipation | uncertain | n/a | 1 | ["2026-10-28"] | anticipation:MCS:2026-10-28 | 2026-10-28 | 2026-10-28 | [] |
| PSNL | anticipation | not_filled | n/a | 1 | ["2026-10-29"] | anticipation:PSNL:2026-10-29 | 2026-10-29 | 2026-10-29 | [] |
| QGEN | anticipation | not_filled | n/a | 1 | ["2026-10-29"] | anticipation:QGEN:2026-10-29 | 2026-10-29 | 2026-10-29 | [] |
| ESRT | anticipation | not_filled | n/a | 1 | ["2026-11-02"] | anticipation:ESRT:2026-11-02 | 2026-11-02 | 2026-11-02 | [] |
| HQY | burst | settled | -1 | 1 | ["2026-11-04"] | burst:HQY:2026-11-04 | 2026-11-04 | 2026-11-04 | [] |
| RCBC | burst | settled | -1 | 1 | ["2026-11-04"] | burst:RCBC:2026-11-04 | 2026-11-04 | 2026-11-04 | [] |
| VIK | burst | settled | -1 | 1 | ["2026-11-04"] | burst:VIK:2026-11-04 | 2026-11-04 | 2026-11-04 | [] |
| MFIC | anticipation | not_filled | n/a | 4 | ["2026-11-09","2026-11-10","2026-11-11","2026-11-13"] | anticipation:MFIC:2026-11-09 | 2026-11-09 | 2026-11-13 | [["stop","shares"],["stop","shares"],["trigger","limit","stop","shares"]] |
| UTZ | anticipation | unmeasured | n/a | 2 | ["2026-11-10","2026-11-11"] | anticipation:UTZ:2026-11-10 | 2026-11-10 | 2026-11-11 | [[]] |
| CART | anticipation | not_filled | n/a | 1 | ["2026-11-13"] | anticipation:CART:2026-11-13 | 2026-11-13 | 2026-11-13 | [] |
| CBC | anticipation | not_filled | n/a | 1 | ["2026-11-13"] | anticipation:CBC:2026-11-13 | 2026-11-13 | 2026-11-13 | [] |
| HZO | anticipation | not_filled | n/a | 1 | ["2026-11-13"] | anticipation:HZO:2026-11-13 | 2026-11-13 | 2026-11-13 | [] |

Model record, eras (3 of 3 rows, 12 of 17 columns; brief.json carries every one):

| model_usd | issued_equity | label | tickets | settled | sum_r | risk_pct | from | through | setups | buckets | wins |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2.24 | 10000 | $10,000 at 0.5% risk | 2 | 1 | 0.41 | 0.5 | 2026-10-08 | 2026-10-08 | 2 | {"settled":1,"open":0,"pending":0,"uncertain":0,"not_filled":1,"unmeasured":0,"… | 1 |
| 5.25 | 2000 | $2,000 at 0.5% risk | 8 | 1 | 3.02 | 0.5 | 2026-10-09 | 2026-11-02 | 7 | {"settled":1,"open":0,"pending":0,"uncertain":1,"not_filled":6,"unmeasured":0,"… | 1 |
| -90.63 | 30000 | $30,000 at 0.5% risk | 12 | 3 | -3 | 0.5 | 2026-11-04 | 2026-11-13 | 8 | {"settled":3,"open":0,"pending":0,"uncertain":0,"not_filled":7,"unmeasured":2,"… | 0 |
- stops.labels.booked: what the model books: a stop first reached inside a session at exactly the stop price, and a session that opens at or under the stop at its open
- stops.labels.at_close: the same exit at that session's close: what holding to the close would have been, and not a fill estimate
- stops.labels.at_low: the same exit at that session's low: a worst-case bound for a stop order filled that day
- stops.labels.minute: where that session's minute bars are retained, the first minute at or under the stop: a stop order filled inside that minute would be between its low and the stop
- stops.count: 3
- stops.unexamined: 0
- stops.sum_r: booked -3, at_close -4.66, at_low -5.78
- stops.sum_usd: booked -90.63, at_close -140.78, at_low -174.64
- stops.settled_sum_r: booked 0.43, at_close -1.23, at_low -2.35

Model record, stops (3 of 3 rows, 12 of 15 columns; brief.json carries every one):

| picked | ticker | kind | shares | r | date | day | event | stopped_shares | entry | stop_price | close |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-11-04 | HQY | burst | 8 | {"booked":-1.0,"at_close":-1.7,"at_low":-2.04} | 2026-11-05 | 1 | stopped | 8 | 109.92 | 106.11 | 103.46 |
| 2026-11-04 | RCBC | burst | 15 | {"booked":-1.0,"at_close":-1.29,"at_low":-1.46} | 2026-11-05 | 1 | stopped | 15 | 60.94 | 58.93 | 58.34 |
| 2026-11-04 | VIK | burst | 10 | {"booked":-1.0,"at_close":-1.67,"at_low":-2.28} | 2026-11-05 | 1 | stopped | 10 | 91.17 | 88.17 | 86.16 |
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

- Event registry (manual; known cash acquisitions only): 7 entries, last reviewed 2026-11-19, 1 days before the measured session 2026-11-20. 1 of 7 unresolved entries are past their review date: ACVA 36 days. Each stays blocked for a SpicyStock ticket; this record does not establish its current status. None of the 108 listed rows (94 bursts, 4 setting up, 10 also quiet) is in the registry. A stock that is not in the registry has not been cleared: SpicyStock reads no company news, and its earnings and SEC checks ran for 0 of the 108 listed names (they run for tickets only).
- Entries: MG (cash_acquisition, announced 2026-09-18, review due 2026-11-25); PRTH (cash_acquisition, announced 2026-09-21, review due 2026-12-17); ARX (cash_acquisition, announced 2026-08-13, review due 2026-12-17); BWIN (cash_acquisition, announced 2026-09-14, review due 2026-12-17); ACVA (cash_acquisition, announced 2026-09-10, review due 2026-10-15); ZIM (cash_acquisition, announced 2026-02-16, review due 2026-12-02); CCC (cash_acquisition, announced 2026-10-15, review due 2026-12-17).
- Status words: `known_event` = in the registry and blocked for a SpicyStock ticket; its manual review is current; `review_required` = in the registry and blocked for a SpicyStock ticket; its manual review is overdue; `not_in_registry` = not in the registry: NOT a clearance, nothing was checked.
- Earnings and 8-K check: status `not_applicable`; 0 ticket rows; 108 of 108 listed names had no check at all.
- Not checked by SpicyStock: company news and press releases, announced earnings dates, offerings and shelf takedowns, FDA and trial dates, halts outside the morning check, delisting notices beyond 8-K item 3.01 on tickets, index changes, lockup expiries, ex-dividend dates.

## 12. Rules

- Rules digest `577dec8b74e4`; without the universe membership identity `4ba4434239c5` (membership identity `29365a85f49efce6`): the record's digest nests the universe membership identity, so it moves on any night the selection's membership moves; `digest_without_membership` is the same digest with that identity removed, and moves only when an archived rule changes.
- pipeline: trade_grades ["A+", "A"], yellow_grades ["A+"], max_reads 12, reader_policy "accepted_required_v1", reader_refusal_fraction 0.25, reader_refusal_min 1, stale_tolerance_fraction 0.01, stale_sessions_max 5, min_coverage_fraction 0.5
- plan: entry_below_pct 2.0, entry_above_pct 4.0, skip_gap_pct 8.0, entry_window_minutes 30, assumed_slippage_pct 1.0, limit_rule "stop_constrained", sizing_basis "order_limit", max_stop_pct 4.0, ideal_stop_pct 2.0, stop_risk_multiplier 0.5, gain_ceiling_pct 15.0, extension_hazard_pct 20.0, hazard_multiplier 0.5, sell_half_pct 8.0, abnormal_day_pct 10.0, gap_exit_pct 20.0, sell_half_day 3, no_progress_day 3, trail_from_day 3, final_exit_day 5, allocation_policy "combined_stages_reserved_principal_v1"
- admission: version 1, policy "burst_route_or_dollar_expansion_v1"
- grading: reader_request_version 3
- record: scorecard_min_plans 20, scorecard_sessions 60

## 13. Bounds

- brief.json: 3 candidates in detail, 0 compact, 0 moved to the tail for size. Tickets and reviewed names are always detailed; of the rest, in the stated order, the largest multiple of 4 (or all) is detailed that keeps brief.json within 250000 bytes, and the others are compact rows; only if none can be detailed are compact rows cut, to the largest multiple of 10 that fits, the rest moving to the research tail.
- This file: 3 in detail, 0 compact rows, 0 compact rows left out, 0 research-tail names not named; reviewed names in their short form: no; model-record tables printed: yes. Rule: tickets and reviewed names always in detail; then, to stay within 80000 bytes, the model-record tables are given up first, then the other names' detail (largest multiple of 2 that fits), then tail names (multiple of 50), then the reviewed names' check measurements and all but a cut reason of their reader sentences (the short form), then compact rows (multiple of 5); brief.json carries what this file leaves out.
- Research tail: 91 named, 0 left out (the first 4000: the admitted trade-band names moved out for size, then the rest by the record's rank order). Open plans left out: 0. Stale names left out: 0. The evening run's model-record block is carried whole when its canonical encoding is within 60000 bytes and the brief still fits with it; past that bound it is carried reduced (each plan row keeps its identity, result and account; the setups table is left out), and not at all if that does not fit either; brief.md prints its sentences and, while they fit, the first 30 rows and 12 columns of each of its tables. A copied sentence over 900 characters is cut and ends with an ellipsis.

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
