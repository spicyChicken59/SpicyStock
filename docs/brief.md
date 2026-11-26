# SpicyStock daily brief: measured Wed 25 Nov 2026, plans for Fri 27 Nov 2026

> This is SpicyStock's daily brief: one evening publication's model output, derived from that publication's record and its pick ledger, with the model-record block the same evening run computed from its own bars carried in (section 10), and from nothing else, for an outside analyst to read in place of the full record.
> Check that it is current before using it: `status` must be `derived`, and the freshness rule in section 2 (`service.freshness_rule`) is applied with your own clock.
> Only the rows in section 5 (`tickets`) are published model tickets. Every other row is research only: its levels are reference arithmetic and SpicyStock offers no order for it.
> SpicyStock places, cancels and observes no order and reads no brokerage account. The owner decides and places every order.

**Model gate RED: size multiplier 0.0; 0 published model tickets for the applicable session.** The record's own cover sentence, written for its model tickets and not an instruction to the reader: "Stand aside."

## 1. Identity and binding

- Measured session: 2026-11-25 (open); plans are for **2026-11-27**, entry window 2026-11-27T09:30:00-05:00 to 2026-11-27T10:00:00-05:00 (America/New_York), full session closes 2026-11-27T13:00:00-05:00; a shortened session.
- Published 2026-11-26T05:07:36.856554+00:00 (run 45759449238, evening); rules version `fa7df9ae9b76`.
- Canonical record `data.json`: 16,983,068 bytes, SHA-256 `eb1b2cf4de83289fb4554ddd1f4a9f2f9023c5d5d6d255e37396b5ae442aa49b`.
- `picks.json`: 28,615 bytes, SHA-256 `7f232ab84aca7c3438f70c8110325660b3a40a339fb12f30d502883089b146b0`.
- This file renders `brief.json` (242,780 bytes, SHA-256 `1a1c72f3563a8f5c5eea281a07cd72f7df4ec39f48e1f9e396c411cdba6fd492`).
- Page https://spicychicken59.github.io/SpicyStock/ · record https://spicychicken59.github.io/SpicyStock/data.json · brief https://spicychicken59.github.io/SpicyStock/brief.json and https://spicychicken59.github.io/SpicyStock/brief.md · run log https://github.com/spicyChicken59/SpicyStock/actions/runs/45759449238.

## 2. Service state

- Run status: **ok**; problems: none; mail delivered.
- Delivery: Published 12:07 AM ET on Thu 26 Nov, 472.6 minutes after the measured session's completion (4:15 PM ET); after both scheduled slots (6:16 PM and 8:16 PM ET); before the next session's open (Fri 27 Nov, 9:30 AM ET). (slot `after_retry`, 472.6 minutes after completion).
- Next publication (`service.expected`): the next session is 2026-11-27; it completes at 2026-11-27T13:15:00-05:00; primary slot 2026-11-27T18:16:00-05:00; retry slot 2026-11-27T20:16:00-05:00; recovery limit 2026-11-30T09:30:00-05:00.
- Freshness rule (states: `newest`, `not_due`, `pending`, `late`, `missing`):
  - Freshness is the reader's own computation: this file carries no clock. Compare your own clock, as an instant with its UTC offset, with the instants in `service.expected`, in this order, and stop at the first that holds.
  - 1. Before `completion_at`: `newest`. The next session has not completed, so no record of a later session can exist yet. The same session can still be published again, and a later run can withdraw a ticket: before acting on a ticket, fetch the file again and compare `identity.canonical.sha256` with the copy the plan was built on.
  - 2. Before `primary_slot_at`: `not_due`. The next session has completed and its evening run is not yet due.
  - 3. Before `retry_slot_at`: `pending`. The first scheduled slot has passed and the retry slot has not.
  - 4. Before `recovery_until`: `late`. Both scheduled slots have passed; a delayed run can still publish the next session until that instant.
  - 5. Otherwise: `missing`. The service does not publish a session after the session that follows it has opened. If this is still the newest file the site serves, the next session was not published and every ticket in this file is expired.
  - From step 2 on, fetch the file again before relying on it: a newer one may exist. A field that is null has its reason in `service.expected.unknown`; without the instant a step needs, freshness is unknown and the file is research only.
  - Freshness is not permission. A ticket applies only from `identity.entry_window.opens_at` to its `cutoff_at`; after the cutoff it is over, whatever state this rule gives.
- Morning check: plans are for 2026-11-27; entry window 2026-11-27T09:30:00-05:00 to 2026-11-27T10:00:00-05:00; the morning collection starts at 2026-11-27T09:00:00-05:00. Receipt https://spicychicken59.github.io/SpicyStock/morning.json: A morning receipt belongs to this publication only when its `publication.data_sha256` equals `identity.canonical.sha256`. One generated before `window_opens_at` carries no quote from inside the entry window. The receipt is not part of this file: it lands the next morning, if a morning check runs.
- Inputs: Alpaca `sip`, split-adjusted 1Day bars, read by the run that began 2026-11-26T05:07:36.856554+00:00; 4,738 of 4,755 intended stocks ready (acceptance `degraded`); 3,479 measured, 17 stale.
- Stale tolerance: `tolerated` (17 stale against a limit of 47). Stale: ANGH, BEBE, BLIV, DDC, EHLD, EQS, IOR, KELYB, LEGO, LIVE, MAYS, PFX, RDIB, TLIH, TOVX, TRSG, WLYB.
- Seed: None of the 17 stale stocks is on the seed alone; each is in the directory this run selected from.
- Follow-up: The 2026-11-24 publication's 19 stocks without a 2026-11-24 bar, read again from this run's split-adjusted fetch: 19 now carry a 2026-11-24 bar (19 with zero volume); 16 would not have been listed; 3 fall under the $3 session-close policy. A late bar is the bar the provider served at this run's check; it never becomes a signal, plan or ticket.
- Minute bars: No plan's first day needed its minute bars tonight; minute bars are retained for 5 plans' first days.
- What the inputs do not establish: Why a stale stock had no session bar is not established; its session inputs are unknown, not a measured non-match, until a later run reads the session again. These bars are the provider's as read by the run that began at 2026-11-26T05:07:36.856554+00:00; a session's volume can be revised afterwards, and this file does not measure by how much. One price source: nothing cross-checks a close, a volume or a split. Bars are adjusted as `service.inputs.basis.adjustment` says and for nothing else. The universe is the selection named in `service.universe`, as fetched; it does not establish which stocks were listed during the session, and the record does not name the stocks that entered or left since the previous publication.
- Chart reader (claude-sonnet-4-6): 2 of 2 reads accepted, verdict `complete`. Chart reader cost: 2 calls for 2 names, 2 replies; 17,242 input tokens (9,122 uncached, 4,060 written to the cache, 4,060 read from it) and 1,192 output tokens, under claude-sonnet-4-6. Token counts as the API reported them; the record carries no price.
- Review selection (`account_feasible_first_research_v2`): 0 feasible, 2 requested of 12; selected: CHH (research_ranked), POWI (research_rotating).
- Admission: 1248 reaction candidates, 310 admitted to the trade band and the chart reads (179 by the 4% scan, 131 by the dollar scan on a range-expansion, higher-volume day); 938 came through the dollar scan alone without one and are research only. Of the 286 mechanical A-band names without a veto, 61 are admitted and 225 are not. Admission is read off the recorded discovery route and the checklist's own range-expansion and volume checks; it is never a grade, and the chart reader never sees a name it stops.
- Earnings and 8-K items (status `not_applicable`): Earnings: no ticket to check.
- Candidate checks (flags only) for 73 of 73 names: 2 listed setups, 2 reviewed bursts, 59 discovery-admitted A+/A bursts, 10 also-quiet coils. SEC merger, tender or deal filings flagged for 13 (CART, MIDD, FWONA and 10 more); a material 8-K item for 6 (CNO, EP, HY and 3 more); earnings reported after the signal, estimated in or near the hold window, or overdue for 5 (CART, OGN, EMR and 2 more); the iex feed's signal-day bar differs for 66 (CART, POWI, MIDD and 63 more). Unknown, and unknown is never clear: the earnings date of 17. A flag is for a reader: it changes no plan, ticket or order, and only the manual event registry withholds a ticket.
- Candidate funnel under a RED market: 1248 reaction candidates discovered, 0 potentially usable (mechanical grade in the admitted band, no veto, discovery admitted), 0 reaction tickets. Reaction candidates stopped at: 1248 market gate: the regime admits no new longs. Anticipation: 844 momentum names, 323 quiet, 2 passing the coil checks, 2 listed, 0 tickets. Listed setups stopped at: 2 market gate: the regime admits no new longs. A stage is where the record's own gates stopped a name; it is not a judgement of the setup and establishes no entry.
- Closest miss: CHH came closest at B 10.0.

## 3. Market regime

- Verdict **RED** for 2026-11-25: size multiplier 0.00; grades the regime admits to a ticket: none. The light is SpicyStock's gate for its own model tickets: an input to weigh, not an instruction to the reader.
- Recorded reason: 10-session ratio 0.5 (1226 up, 2462 down) < 1.0: more breakdowns than breakouts
- Counts over 3,479 measured stocks (4,755 intended, 4,738 with a session bar, 1,259 under the $3.00 session close floor): up 4% 177, down 4% 46; up/down 25% in a quarter 576/938; up/down 25% in a month 100/363; up/down 50% in a month 11/34; up/down 13% in 34 days 1,058/1,346; 41.0% above the 40-day average.
- Ratios: 5-session 0.67 (836 up, 1,248 down, unrounded 0.6699); 10-session 0.50 (1,226 up, 2,462 down, unrounded 0.498). The rules compare the rounded number.

All five regime rules, in the order they are asked (universe 3,479 against a reference of 6,500). Count thresholds are the reference count times the stocks measured over the reference universe; that scaling is this project's own. Ratio thresholds are not scaled.

| rule | tier | measured | comparison | threshold tonight | reference | fired | decides | masked |
|---|---|---|---|---|---|---|---|---|
| down4_alarm | red | down4 46 | at or over | 374.7 | 700 of 6,500 | no | no | no |
| ratio_10d_red | red | ratio_10d 0.5 | under | 1 | 1, not scaled | yes | yes | no |
| ratio_5d_red | red | ratio_5d 0.67 | under, with more names down 4% than up 4% today | 0.5 | 0.5, not scaled | no | no | no |
| ratio_10d_yellow | yellow | ratio_10d 0.5 | under | 2 | 2, not scaled | yes | no | yes |
| up50_month_hot | yellow | up50_month 11 | over | 10.7 | 20 of 6,500 | yes | no | yes |

- GREEN needs all five rules quiet: fewer than 374.7 names down 4% today (it is 46); a 10-session ratio at or over 2 (it is 0.5: 1,226 up against 2,462 down); no 5-session ratio under 0.5 with more names down 4% than up 4% today (it is 0.67, with 46 down against 177 up); and no more than 10.7 names up 50% in a month (it is 11).
- Yellow by rounding (more ten-session breakdowns than breakouts while the rounded ratio is not under the red line): no. Near a line: no (the 10-session ratio is -0.5 from the red line and -1.5 from the yellow line; band 0.06, the band is this project's own label bound, the largest later re-reading of a published ratio seen through 17 November 2026; it is not a rule and gates nothing).

Breadth history (the newest 10 sessions of the record's own breadth history, each read again tonight over tonight's stocks: an earlier session's counts can differ from what its own night published): 2026-11-12 50/266 r10 0.89; 2026-11-13 71/136 r10 1.01; 2026-11-16 49/434 r10 0.87; 2026-11-17 58/209 r10 0.80; 2026-11-18 162/169 r10 0.62; 2026-11-19 44/344 r10 0.75; 2026-11-20 30/710 r10 0.52; 2026-11-23 331/28 r10 0.45; 2026-11-24 254/120 r10 0.52; 2026-11-25 177/46 r10 0.50.

## 4. Model account

- Model account (the model's configured sizing assumptions; not a brokerage balance): equity $30,000.00, risk 0.50% a trade, position cap 25.00%, 4 slots.
- Model allocation: next-session tickets would commit $0.00 of the configured $30,000.00; 0 of 4 slots.
- Cut: CART (anticipation, withheld): ticket withheld: at the $59.40 limit, the highest fill the ticket permits, the stop $56.88 is 4.24% away, past his 4% line; the setup stands, the ticket does not
- Cut: OGN (anticipation, no_new_longs): breadth sizes new positions at zero tonight

## 5. Published model tickets (0)

None. The record published no model ticket for the applicable session.

## 6. Admitted trade-band candidates (61 of 286 in the band; 1,248 discovered)

Definition: reaction candidates whose mechanical grade is in the trade band (A+, A), with no quality veto, that the discovery admission admits; plus any other name with a published ticket or a selected chart review. Order: published tickets, then names selected for a chart review, then the rest; each in the record's rank order (grade, score descending, ticker). Model status: a row is `TICKET` only when the record published a model ticket for it (its order is in `tickets`); every other row is `RESEARCH ONLY: no SpicyStock ticket`. Later gates: the gates after the market gate, re-derived from the row's recorded fields so a RED night does not hide them; passing them is not a ticket: the stop rule, the event registry, sizing and the slot allocation follow, and the market gate stands.

Checklist, the same thresholds for every name. **2** not up two days in a row: up_run <= 1, counting days above +1.0%; veto at 3+ up closes of any size (weight 1.5). **L** linearity of the prior leg: ER >= 0.4 or R2 >= 0.55 (both for A+); failing is a veto (weight 2.0). **Y** young trend: first or second breakout: prior breakouts since the move started <= 1 (0 for A+) (weight 1.5). **N** narrow or negative day before: prior day negative or range < 2.0% (A+: negative and under its 20-session median range) (weight 1.5). **C** consolidation quality: base 3-20 sessions, breakdowns <= 1, giveback <= 0.34, tightness <= 1.0 (A+: 0 breakdowns, 0 bursts inside, giveback <= 0.25, tightness <= 0.7, base volume under the leg's and the 50-session average) (weight 2.0). **H** close near the high: close_pos >= 0.8 and close > open (A+ >= 0.9; partial from 0.7) (weight 1.5). **RE** range expansion: today's range over the largest of the prior 5 >= 1.0 (A+: also over the prior 10) (recorded, no weight). **VOL** higher volume: volume > prior session (A+: rank <= 3 of the last 60); a base over 21 sessions also needs >= 1.5x the 50-session average (recorded, no weight).
Check marks: letter then + (pass at the A+ level), nothing (pass), ~ (partial), x (fail), ? (not measured).

Hold days for a plan entered on the applicable session: day 1 = 2026-11-27, day 2 = 2026-11-30, day 3 = 2026-12-01, day 4 = 2026-12-02, day 5 = 2026-12-03. The model's exit rules (source B Bonde, P this project, T a third party's test): [B] when same or next day, the price reaches the sell-half level (+8% from the planned entry): sell half and move the stop to 25-50 cents under that day's high. [B] when any single day closes at or above the abnormal-close level (+10%): take at least partial profit and move the stop up to protect the rest. [B] when it opens at or above the gap-exit level (+20%) after entry: sell at the open (or pre-market). [B] when the close of day 1: the stop rises to the entry day's low if that is above the stop. [B] when day 3 close: sell at least half at the close. [B] when day 3 closes at or below the planned entry: exit: no follow-through. [P] when from the close of day 3: raise the stop to each day's low (it never moves down). [B] when day 5 close: exit the remainder into strength. [B] when the protective stop at the stop is a stop-market order, live intraday from the moment the buy fills: if it is somehow not filled, exit on any close below it. [T] when day 2 is green: do not move the stop to break-even before day 5 just because it is green (theStrat Lab EP9M backtest: the win rate collapses from 29.8% to 7.25%; delaying to day 5 restores it); the +8% raise above is a different rule.

Page for any ticker here: https://spicychicken59.github.io/SpicyStock/#/explore/bursts/<TICKER> (setting-up names: the same with `setting-up` in place of `bursts`). Near-volume band: 171 of the discovered bursts have a volume within 0.05 of the previous session's (the burst's volume is within this fraction of the previous session's, so its higher-volume check can flip on the provider's later corrections; the bound is this project's own label, not a rule).

### 6a. In detail (14 of 61 listed: every ticket and reviewed name, then the first 12 others)

### CHH · Choice Hotels International Inc. Common Stock · rank 285 · A+ 10.00, final B · reviewed · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $121.86 (1.30% from $120.30), open $118.89, high $122.37, low $117.18; volume 490,728 (1.19x the prior session, 0.86x its 50-session average), dollar volume $59.8M; 2.4% over its 20-session average; route dollar (dollar_expansion).
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-0.22 · **L** er=0.39 r2=0.93 leg_sessions=48 leg_gain_pct=28.9 · **Y** breakouts_in_move=1 sessions_since_move_start=52 gain_since_move_start_pct=26.2 · **N+** prior_day_pct=-0.22 prior_range_pct=1.9 negative=yes narrow=yes median_range_pct=2.8 · **C** base_sessions=4 breakdowns=0 bursts_in_base=0 giveback=0.29 tightness=0.91 base_volume_vs_leg=0.92 base_volume_vs_avg=0.93 · **H+** close_pos=0.9 close_above_open=yes · **RE+** vs_prior_5=1.1 vs_prior_10=1.1 bar_range_pct=4.3 · **VOL** volume_vs_prior=1.19 volume_vs_avg50=0.86 volume_rank_60=36 cv_required=no. Base 2026-11-19 to 2026-11-24, $116.91 to $125.50; extension: close 2.4% vs its 20-SMA, 10.8% over 20 sessions; prior breakouts worked 0 of 1 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: accepted, B 7.5 (research_ranked); selection blockers: grade_not_admitted.
  - Reader's reason (commentary): The mechanical grade is A+ but the chart reveals two meaningful visual concerns: the 4-session base (shaded box, mid-to-late November) shows bars with overlapping ranges and tightness of 0.91 — near the 1.0 ceiling — suggesting the consolidation is not as orderly as the numbers imply, and the prior leg spanning 48 sessions with only an ER of 0.39 (below the 0.4 A+ threshold) reflects a move that is more drift than persistent stair-step buying. The signal bar itself is honest — closed near the high, above the open — but volume rank of 36 out of 60 is mediocre and the move is 52 sessions old with 26% gain already banked.
  - Reader's main risk (commentary): The trend is mature at 52 sessions and the base tightness is near its upper limit, leaving little room for the consolidation to absorb further selling before the setup degrades.
  - Reader's entry note (not the ticket): Skip if CHH opens below the prior session's close (~120.30) or gaps up more than 1% above the signal close, as either would invalidate the measured base or extend risk beyond plan.
- Later gates: GREEN band fail, YELLOW band fail, veto pass, admission pass, reader `accepted`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $121.98; limit $122.06; stop $117.18 (burst_low, 4.00% under the limit); day-2 line $126.73; skip if it opens under $119.42; sell-half $131.82; risk a share at the limit $4.88; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 15 shares, $1,830.90; at the YELLOW size 7 shares, $854.42; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### POWI · Power Integrations Inc. Common Stock · rank 690 · A 8.00, final skip · reviewed · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $41.40 (4.20% from $39.73), open $38.00, high $41.99, low $36.82; volume 1,337,710 (1.22x the prior session, 1.64x its 50-session average), dollar volume $55.4M; -4.8% over its 20-session average; route both (burst_route).
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-8.92 · **L+** er=0.53 r2=0.71 leg_sessions=13 leg_gain_pct=14.3 · **Y+** breakouts_in_move=0 sessions_since_move_start=14 gain_since_move_start_pct=6.6 · **N** prior_day_pct=-8.92 prior_range_pct=10 negative=yes narrow=no median_range_pct=5.6 · **Cx** base_sessions=37 breakdowns=8 bursts_in_base=5 giveback=1.95 tightness=1.15 base_volume_vs_leg=0.95 base_volume_vs_avg=0.99 · **H** close_pos=0.89 close_above_open=yes · **RE+** vs_prior_5=1.25 vs_prior_10=1.25 bar_range_pct=12.5 · **VOL** volume_vs_prior=1.22 volume_vs_avg50=1.64 volume_rank_60=5 cv_required=yes. Base 2026-10-05 to 2026-11-24, $38.06 to $55.86; extension: close -4.8% vs its 20-SMA, -16.1% over 20 sessions; prior breakouts worked 1 of 3 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: accepted, skip 4.5 (research_rotating); selection blockers: grade_not_admitted.
  - Reader's reason (commentary): The consolidation box spans 37 sessions with 8 recorded 4%-down breakdowns and 5 bursts inside it — the chart shows a prolonged, choppy, declining base from ~$55 down to ~$38 with wide overlapping bars and repeated failed rallies, which is the opposite of the tight, orderly consolidation Bonde requires. The base gave back 1.95x the prior leg gain and ranged wider than the leg itself, confirming visually what the FAIL records. The burst bar itself opened with a large gap down (~4.4%) from the prior close and then recovered, meaning much of the 12.5% bar range is gap-dominated and the net close-to-close gain is only 4.2% on a day that started sharply lower.
  - Reader's main risk (commentary): The base is a multi-month declining channel with repeated breakdowns, not a consolidation — any follow-through faces the full weight of overhead supply from $42 to $56.
  - Reader's entry note (not the ticket): Skip if the open is below the burst day's close of $41.40 or if the stock gaps up more than 1% above it without holding, given the heavy overhead supply and weak base structure.
- Later gates: GREEN band fail, YELLOW band fail, veto pass, admission pass, reader `accepted`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $41.44; ticket withheld (no_room_above_the_trigger): no limit above the trigger keeps a structural stop inside the stop line; day-2 line $43.06; skip if it opens under $40.57.
- Plan rule refusal: ticket withheld: no limit above the $41.44 buy stop keeps a stop inside his 4% line — the burst day's low $36.82 caps the limit at $38.35, at or under that buy stop; the bar's midpoint $39.41 caps the limit at $41.05, at or under that buy stop; the setup stands, the ticket does not
- No ticket: market gate: the regime admits no new longs (stage `market`).

### MIDD · Middleby Corporation (The) Common Stock · rank 3 · A 10.00 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $135.26 (0.94% from $134.00), open $133.43, high $135.81, low $131.16; volume 522,710 (1.04x the prior session, inside the near-volume band, 0.95x its 50-session average), dollar volume $70.7M; 2.5% over its 20-session average; route dollar (dollar_expansion).
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-1.24 · **L+** er=0.81 r2=0.87 leg_sessions=28 leg_gain_pct=34.4 · **Y** breakouts_in_move=1 sessions_since_move_start=39 gain_since_move_start_pct=31.7 · **N+** prior_day_pct=-1.24 prior_range_pct=2 negative=yes narrow=no median_range_pct=3 · **C** base_sessions=11 breakdowns=0 bursts_in_base=0 giveback=0.26 tightness=0.96 base_volume_vs_leg=0.88 base_volume_vs_avg=0.87 · **H** close_pos=0.88 close_above_open=yes · **RE** vs_prior_5=1 vs_prior_10=0.97 bar_range_pct=3.4 · **VOL** volume_vs_prior=1.04 volume_vs_avg50=0.95 volume_rank_60=26 cv_required=no. Base 2026-11-10 to 2026-11-24, $131.19 to $141.43; extension: close 2.5% vs its 20-SMA, 18.6% over 20 sessions; prior breakouts worked 0 of 1 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $135.40; limit $136.62; stop $131.16 (burst_low, 4.00% under the limit); day-2 line $140.67; skip if it opens under $132.55; sell-half $147.54; risk a share at the limit $5.46; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 13 shares, $1,776.06; at the YELLOW size 6 shares, $819.72; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### CDW · CDW Corporation Common Stock · rank 7 · A 8.50 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $174.97 (6.59% from $164.16), open $160.69, high $175.61, low $158.28; volume 1,542,627 (1.25x the prior session, 1.00x its 50-session average), dollar volume $269.9M; 6.3% over its 20-session average; route both (burst_route).
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-3.47 · **L** er=0.36 r2=0.74 leg_sessions=31 leg_gain_pct=35 · **Yx** breakouts_in_move=4 sessions_since_move_start=40 gain_since_move_start_pct=36.5 · **N** prior_day_pct=-3.47 prior_range_pct=6.6 negative=yes narrow=no median_range_pct=4.2 · **C** base_sessions=9 breakdowns=0 bursts_in_base=1 giveback=0.32 tightness=0.93 base_volume_vs_leg=0.78 base_volume_vs_avg=0.82 · **H+** close_pos=0.96 close_above_open=yes · **RE+** vs_prior_5=1.5 vs_prior_10=1.5 bar_range_pct=9.9 · **VOL** volume_vs_prior=1.25 volume_vs_avg50=1 volume_rank_60=25 cv_required=no. Base 2026-11-12 to 2026-11-24, $160.03 to $175.19; extension: close 6.3% vs its 20-SMA, 7.6% over 20 sessions; prior breakouts worked 1 of 3 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $175.14; ticket withheld (no_room_above_the_trigger): no limit above the trigger keeps a structural stop inside the stop line; day-2 line $181.97; skip if it opens under $171.47.
- Plan rule refusal: ticket withheld: no limit above the $175.14 buy stop keeps a stop inside his 4% line — the burst day's low $158.28 caps the limit at $164.87, at or under that buy stop; the bar's midpoint $166.94 caps the limit at $173.89, at or under that buy stop; the setup stands, the ticket does not
- No ticket: market gate: the regime admits no new longs (stage `market`).

### FWONA · Liberty Media Corporation Series A Common Stock · rank 9 · A 8.50 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $103.15 (1.78% from $101.35), open $100.75, high $103.42, low $99.24; volume 254,931 (1.17x the prior session, 1.00x its 50-session average), dollar volume $26.3M; 4.3% over its 20-session average; route dollar (dollar_expansion).
- Checks: **2+** up_run=0 up_closes=2 prior_day_pct=0.52 · **L+** er=0.85 r2=0.93 leg_sessions=13 leg_gain_pct=27.5 · **Y+** breakouts_in_move=0 sessions_since_move_start=21 gain_since_move_start_pct=25.8 · **Nx** prior_day_pct=0.52 prior_range_pct=2.6 negative=no narrow=no median_range_pct=2.7 · **C** base_sessions=8 breakdowns=0 bursts_in_base=0 giveback=0.27 tightness=0.82 base_volume_vs_leg=0.73 base_volume_vs_avg=0.95 · **H+** close_pos=0.94 close_above_open=yes · **RE+** vs_prior_5=1.14 vs_prior_10=1.14 bar_range_pct=4.1 · **VOL** volume_vs_prior=1.17 volume_vs_avg50=1 volume_rank_60=17 cv_required=no. Base 2026-11-13 to 2026-11-24, $99.56 to $106.52; extension: close 4.3% vs its 20-SMA, 23.0% over 20 sessions; prior breakouts worked 2 of 2 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $103.25; limit $103.37; stop $99.24 (burst_low, 4.00% under the limit); day-2 line $107.28; skip if it opens under $101.09; sell-half $111.64; risk a share at the limit $4.13; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 18 shares, $1,860.66; at the YELLOW size 9 shares, $930.33; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### AEM · Agnico Eagle Mines Limited Common Stock · rank 18 · A 8.00 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $161.20 (3.03% from $156.46), open $150.11, high $162.14, low $147.80; volume 3,408,724 (1.70x the prior session, 1.70x its 50-session average), dollar volume $549.5M; -7.1% over its 20-session average; route dollar (dollar_expansion); flags foreign.
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-2.03 · **L+** er=0.85 r2=0.92 leg_sessions=7 leg_gain_pct=21.4 · **Y+** breakouts_in_move=0 sessions_since_move_start=3 gain_since_move_start_pct=6.5 · **N** prior_day_pct=-2.03 prior_range_pct=3.7 negative=yes narrow=no median_range_pct=3.2 · **Cx** base_sessions=11 breakdowns=5 bursts_in_base=1 giveback=1.26 tightness=1.11 base_volume_vs_leg=0.89 base_volume_vs_avg=1.2 · **H+** close_pos=0.93 close_above_open=yes · **RE+** vs_prior_5=1.44 vs_prior_10=1.44 bar_range_pct=8.9 · **VOL** volume_vs_prior=1.7 volume_vs_avg50=1.7 volume_rank_60=6 cv_required=no. Base 2026-11-10 to 2026-11-24, $150.76 to $202.24; extension: close -7.1% vs its 20-SMA, -12.0% over 20 sessions; prior breakouts worked 1 of 3 (closed higher 3 sessions later, last 4 in 60 sessions); first leg of 21.4% in 7 sessions: his '15% plus in 10 days or less'.
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $161.36; limit $161.42; stop $154.97 (half_range, 4.00% under the limit); day-2 line $167.65; skip if it opens under $157.98; sell-half $174.33; risk a share at the limit $6.45; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 11 shares, $1,775.62; at the YELLOW size 5 shares, $807.10; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### APOG · Apogee Enterprises Inc. Common Stock · rank 27 · A 8.00 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $47.46 (3.90% from $45.68), open $45.21, high $47.72, low $44.46; volume 176,675 (1.22x the prior session, 0.55x its 50-session average), dollar volume $8.4M; 2.5% over its 20-session average; route dollar (dollar_expansion).
- Checks: **2** up_run=1 up_closes=2 prior_day_pct=0.68 · **L+** er=0.48 r2=0.87 leg_sessions=29 leg_gain_pct=35.8 · **Y** breakouts_in_move=1 sessions_since_move_start=40 gain_since_move_start_pct=34.2 · **N** prior_day_pct=0.68 prior_range_pct=1.9 negative=no narrow=yes median_range_pct=3.2 · **Cx** base_sessions=11 breakdowns=0 bursts_in_base=1 giveback=0.43 tightness=0.98 base_volume_vs_leg=0.65 base_volume_vs_avg=0.74 · **H+** close_pos=0.92 close_above_open=yes · **RE+** vs_prior_5=1.53 vs_prior_10=1.53 bar_range_pct=6.9 · **VOL** volume_vs_prior=1.22 volume_vs_avg50=0.55 volume_rank_60=55 cv_required=no. Base 2026-11-10 to 2026-11-24, $43.11 to $49.50; extension: close 2.5% vs its 20-SMA, 6.1% over 20 sessions; prior breakouts worked 2 of 3 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $47.51; limit $48.01; stop $46.09 (half_range, 4.00% under the limit); day-2 line $49.36; skip if it opens under $46.51; sell-half $51.76; risk a share at the limit $1.92; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 39 shares, $1,872.39; at the YELLOW size 19 shares, $912.19; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### AU · AngloGold Ashanti PLC Ordinary Shares · rank 32 · A 8.00 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $77.94 (2.20% from $76.26), open $72.98, high $78.36, low $71.60; volume 3,818,897 (1.45x the prior session, 1.47x its 50-session average), dollar volume $297.6M; -7.6% over its 20-session average; route dollar (dollar_expansion); flags foreign.
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-1.63 · **L+** er=0.92 r2=0.93 leg_sessions=7 leg_gain_pct=24.5 · **Y+** breakouts_in_move=0 sessions_since_move_start=3 gain_since_move_start_pct=7.6 · **N+** prior_day_pct=-1.63 prior_range_pct=2.8 negative=yes narrow=no median_range_pct=3.7 · **Cx** base_sessions=11 breakdowns=4 bursts_in_base=1 giveback=1.28 tightness=1.28 base_volume_vs_leg=0.85 base_volume_vs_avg=1.1 · **H+** close_pos=0.94 close_above_open=yes · **RE+** vs_prior_5=1.26 vs_prior_10=1.26 bar_range_pct=8.7 · **VOL** volume_vs_prior=1.45 volume_vs_avg50=1.47 volume_rank_60=6 cv_required=no. Base 2026-11-10 to 2026-11-24, $71.89 to $100.44; extension: close -7.6% vs its 20-SMA, -10.7% over 20 sessions; prior breakouts worked 1 of 3 (closed higher 3 sessions later, last 4 in 60 sessions); first leg of 24.5% in 7 sessions: his '15% plus in 10 days or less'.
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $78.02; limit $78.10; stop $74.98 (half_range, 3.99% under the limit); day-2 line $81.06; skip if it opens under $76.38; sell-half $84.35; risk a share at the limit $3.12; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 24 shares, $1,874.40; at the YELLOW size 12 shares, $937.20; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### AVNT · Avient Corporation Common Stock · rank 34 · A 8.00 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $45.41 (3.20% from $44.00), open $43.23, high $45.55, low $42.96; volume 707,534 (1.26x the prior session, 0.89x its 50-session average), dollar volume $32.1M; 2.0% over its 20-session average; route dollar (dollar_expansion).
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-0.59 · **L+** er=0.79 r2=0.86 leg_sessions=19 leg_gain_pct=26.6 · **Y+** breakouts_in_move=0 sessions_since_move_start=33 gain_since_move_start_pct=20.2 · **N+** prior_day_pct=-0.59 prior_range_pct=2.5 negative=yes narrow=no median_range_pct=3 · **Cx** base_sessions=14 breakdowns=1 bursts_in_base=0 giveback=0.52 tightness=1.14 base_volume_vs_leg=0.7 base_volume_vs_avg=0.86 · **H+** close_pos=0.95 close_above_open=yes · **RE+** vs_prior_5=1.58 vs_prior_10=1.54 bar_range_pct=5.7 · **VOL** volume_vs_prior=1.26 volume_vs_avg50=0.89 volume_rank_60=29 cv_required=no. Base 2026-11-05 to 2026-11-24, $42.65 to $49.08; extension: close 2.0% vs its 20-SMA, 7.6% over 20 sessions; prior breakouts worked 0 of 1 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $45.46; limit $46.09; stop $44.25 (half_range, 3.99% under the limit); day-2 line $47.23; skip if it opens under $44.50; sell-half $49.53; risk a share at the limit $1.84; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 40 shares, $1,843.60; at the YELLOW size 20 shares, $921.80; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### AXTA · Axalta Coating Systems Ltd. Common Shares · rank 35 · A 8.00 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $36.06 (2.33% from $35.24), open $34.95, high $36.09, low $34.85; volume 2,732,371 (2.84x the prior session, 1.54x its 50-session average), dollar volume $98.5M; 0.4% over its 20-session average; route dollar (dollar_expansion).
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-0.68 · **L** er=0.36 r2=0.81 leg_sessions=28 leg_gain_pct=17.8 · **Y** breakouts_in_move=1 sessions_since_move_start=39 gain_since_move_start_pct=13.2 · **N+** prior_day_pct=-0.68 prior_range_pct=1.7 negative=yes narrow=yes median_range_pct=2.4 · **Cx** base_sessions=11 breakdowns=1 bursts_in_base=0 giveback=0.6 tightness=0.93 base_volume_vs_leg=0.51 base_volume_vs_avg=0.56 · **H+** close_pos=0.97 close_above_open=yes · **RE+** vs_prior_5=1.13 vs_prior_10=1.13 bar_range_pct=3.5 · **VOL** volume_vs_prior=2.84 volume_vs_avg50=1.54 volume_rank_60=7 cv_required=no. Base 2026-11-10 to 2026-11-24, $33.97 to $38.06; extension: close 0.4% vs its 20-SMA, 4.1% over 20 sessions; prior breakouts worked 2 of 2 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $36.10; limit $36.30; stop $34.85 (burst_low, 3.99% under the limit); day-2 line $37.50; skip if it opens under $35.34; sell-half $39.20; risk a share at the limit $1.45; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 51 shares, $1,851.30; at the YELLOW size 25 shares, $907.50; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### B · Barrick Mining Corporation Common Shares · rank 37 · A 8.00 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $34.52 (2.80% from $33.58), open $32.42, high $34.64, low $31.99; volume 13,630,015 (1.21x the prior session, 1.58x its 50-session average), dollar volume $470.5M; -7.0% over its 20-session average; route dollar (dollar_expansion); flags foreign.
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-1 · **L+** er=0.74 r2=0.86 leg_sessions=7 leg_gain_pct=14.2 · **Y+** breakouts_in_move=0 sessions_since_move_start=3 gain_since_move_start_pct=9.4 · **N** prior_day_pct=-1 prior_range_pct=2.9 negative=yes narrow=no median_range_pct=2.9 · **Cx** base_sessions=11 breakdowns=3 bursts_in_base=1 giveback=1.75 tightness=1.36 base_volume_vs_leg=1.09 base_volume_vs_avg=1.28 · **H+** close_pos=0.95 close_above_open=yes · **RE+** vs_prior_5=1.33 vs_prior_10=1.12 bar_range_pct=7.7 · **VOL** volume_vs_prior=1.21 volume_vs_avg50=1.58 volume_rank_60=5 cv_required=no. Base 2026-11-10 to 2026-11-24, $31.34 to $42.86; extension: close -7.0% vs its 20-SMA, -13.0% over 20 sessions; prior breakouts worked 1 of 3 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $34.55; limit $34.69; stop $33.31 (half_range, 3.98% under the limit); day-2 line $35.90; skip if it opens under $33.83; sell-half $37.47; risk a share at the limit $1.38; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 54 shares, $1,873.26; at the YELLOW size 27 shares, $936.63; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### BNC · BNB Standard Corporation Common Stock · rank 46 · A 8.00 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $3.04 (4.47% from $2.91), open $2.90, high $3.04, low $2.68; volume 718,712 (1.03x the prior session, inside the near-volume band, 0.65x its 50-session average), dollar volume $2.2M; -26.6% over its 20-session average; route burst (burst_route).
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-9.91 · **L** er=0.35 r2=0.9 leg_sessions=41 leg_gain_pct=154.3 · **Y+** breakouts_in_move=0 sessions_since_move_start=1 gain_since_move_start_pct=4.5 · **N** prior_day_pct=-9.91 prior_range_pct=9.6 negative=yes narrow=no median_range_pct=5.8 · **Cx** base_sessions=37 breakdowns=15 bursts_in_base=7 giveback=0.85 tightness=0.78 base_volume_vs_leg=0.32 base_volume_vs_avg=0.81 · **H+** close_pos=1 close_above_open=yes · **REx** vs_prior_5=0.64 vs_prior_10=0.64 bar_range_pct=11.8 · **VOLx** volume_vs_prior=1.03 volume_vs_avg50=0.65 volume_rank_60=43 cv_required=yes. Base 2026-10-05 to 2026-11-24, $2.90 to $6.30; extension: close -26.6% vs its 20-SMA, -46.1% over 20 sessions; price under $5: explosive, wider stops; prior breakouts worked 0 of 3 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $3.06; ticket withheld (no_room_above_the_trigger): no limit above the trigger keeps a structural stop inside the stop line; day-2 line $3.16; skip if it opens under $2.98.
- Plan rule refusal: ticket withheld: no limit above the $3.06 buy stop keeps a stop inside his 4% line — the burst day's low $2.68 caps the limit at $2.79, at or under that buy stop; the bar's midpoint $2.86 caps the limit at $2.97, at or under that buy stop; the setup stands, the ticket does not
- No ticket: market gate: the regime admits no new longs (stage `market`).

### BRVE · Braveheart Bio Inc. Common Stock · rank 49 · A 8.00 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $23.51 (5.52% from $22.28), open $22.28, high $23.58, low $20.60; volume 653,232 (1.08x the prior session, 1.16x its 50-session average), dollar volume $15.4M; 15.6% over its 20-session average; route both (burst_route); flags biotech.
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-4.09 · **L** er=0.55 r2=0.27 leg_sessions=13 leg_gain_pct=33.4 · **Y+** breakouts_in_move=0 sessions_since_move_start=14 gain_since_move_start_pct=35 · **N** prior_day_pct=-4.09 prior_range_pct=12.6 negative=yes narrow=no median_range_pct=7 · **Cx** base_sessions=1 breakdowns=1 bursts_in_base=0 giveback=0.41 tightness=1.47 base_volume_vs_leg=0.8 base_volume_vs_avg=1.07 · **H+** close_pos=0.98 close_above_open=yes · **REx** vs_prior_5=0.81 vs_prior_10=0.81 bar_range_pct=12.7 · **VOL** volume_vs_prior=1.08 volume_vs_avg50=1.16 volume_rank_60=17 cv_required=no. Base 2026-11-24 to 2026-11-24, $21.46 to $24.75; extension: close 15.6% vs its 20-SMA, 8.0% over 20 sessions; prior breakouts worked 2 of 3 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $23.53; ticket withheld (no_room_above_the_trigger): no limit above the trigger keeps a structural stop inside the stop line; day-2 line $24.45; skip if it opens under $23.04.
- Plan rule refusal: ticket withheld: no limit above the $23.53 buy stop keeps a stop inside his 4% line — the burst day's low $20.60 caps the limit at $21.45, at or under that buy stop; the bar's midpoint $22.09 caps the limit at $23.01, at or under that buy stop; the setup stands, the ticket does not
- No ticket: market gate: the regime admits no new longs (stage `market`).

### CNO · CNO Financial Group Inc. Common Stock · rank 62 · A 8.00 · candidate · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $56.11 (0.45% from $55.86), open $53.92, high $56.20, low $53.92; volume 538,701 (1.04x the prior session, inside the near-volume band, 0.59x its 50-session average), dollar volume $30.2M; -0.9% over its 20-session average; route dollar (dollar_expansion).
- Checks: **2** up_run=1 up_closes=2 prior_day_pct=0.23 · **L** er=0.21 r2=0.65 leg_sessions=27 leg_gain_pct=6.7 · **Y** breakouts_in_move=1 sessions_since_move_start=40 gain_since_move_start_pct=6 · **N** prior_day_pct=0.23 prior_range_pct=1.6 negative=no narrow=yes median_range_pct=1.9 · **Cx** base_sessions=13 breakdowns=0 bursts_in_base=0 giveback=0.74 tightness=1.01 base_volume_vs_leg=0.63 base_volume_vs_avg=0.64 · **H+** close_pos=0.96 close_above_open=yes · **RE+** vs_prior_5=1.21 vs_prior_10=1.21 bar_range_pct=4.1 · **VOL** volume_vs_prior=1.04 volume_vs_avg50=0.59 volume_rank_60=50 cv_required=no. Base 2026-11-06 to 2026-11-24, $53.80 to $59.15; extension: close -0.9% vs its 20-SMA, 3.2% over 20 sessions; prior breakouts worked 1 of 1 (closed higher 3 sessions later, last 4 in 60 sessions).
- Chart reader: not_selected_budget; selection blockers: grade_not_admitted.
- Later gates: GREEN band pass, YELLOW band fail, veto pass, admission pass, reader `not_selected_budget`; all of them under GREEN no, under YELLOW no.
- research levels (derived; no order is offered at them): trigger $56.17; limit $57.35; stop $55.06 (half_range, 3.99% under the limit); day-2 line $58.35; skip if it opens under $54.99; sell-half $61.20; risk a share at the limit $2.29; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 32 shares, $1,835.20; at the YELLOW size 16 shares, $917.60; no new longs: the size multiplier is 0.
- No ticket: market gate: the regime admits no new longs (stage `market`).

### 6b. Compact rows (47 shown; 0 left out of this file; brief.json carries every one)

Every row here is RESEARCH ONLY (no SpicyStock ticket, no chart review). Research levels are derived from the recorded bar by the record's plan rules: `limit` is the highest fill the plan permits; stop basis L is the burst day's low, M the bar's midpoint; the day-2 line (too extended to enter) is the trigger plus the archived entry_above_pct and the skip-under line the trigger minus entry_below_pct (both exact in brief.json); `shares` is the model size under tonight's regime multiplier, then the same plan at full size; `refused` means the plan rule refused it; `*` after the volume ratio marks the near-volume band. Every row stopped at stage `market` (market gate: the regime admits no new longs) unless its ticker carries another in brackets. 

| ticker | gain % | vol x | $ vol M | ext % | grade | checks | trigger | limit | stop | sell-half | risk/sh | shares |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CVLG | 2.16 | 1.08 | 3.3 | -3.4 | A 8 | 2+ L+ Y N Cx H+ RE+ VOL | 30.77 | 31.15 | 29.91M | 33.53 | 1.24 | 0/60 |
| CWH | 7.04 | 1.11 | 9.2 | -3.8 | A 8 | 2+ L Y+ N Cx H RE+ VOL | 4.43 | withheld | n/a | n/a | n/a | n/a |
| CXT | 2.03 | 1.59 | 51.4 | -6.3 | A 8 | 2+ L+ Y+ N+ Cx H+ RE+ VOL+ | 53.31 | 53.56 | 51.42M | 57.84 | 2.14 | 0/35 |
| DE | 4.44 | 1.08 | 1510.6 | -2.7 | A 8 | 2+ L Y+ N Cx H+ RE+ VOL+ | 641.66 | withheld | n/a | n/a | n/a | n/a |
| ELVA | 4.76 | 1.02* | 1.7 | -21.5 | A 8 | 2+ L+ Y+ N Cx H+ RE+ VOLx | 3.54 | withheld | n/a | n/a | n/a | n/a |
| EMR | 0.16 | 1.07 | 469.1 | -3.6 | A 8 | 2+ L Y+ N+ Cx H+ RE+ VOL | 157.39 | 160.41 | 154M | 171.5 | 6.41 | 0/11 |
| EP | 23.92 | 5.54 | 0.4 | 27.2 | A 8 | 2+ L+ Y N+ Cx H+ RE+ VOL+ | 3.18 | withheld | n/a | n/a | n/a | n/a |
| ESAB | 3.31 | 1.05 | 48.4 | 0.8 | A 8 | 2+ L+ Y N+ Cx H+ RE+ VOL | 80.26 | 80.4 | 77.19M | 86.83 | 3.21 | 0/23 |
| FLUT | 5.14 | 1.04* | 141.5 | -9.4 | A 8 | 2+ L Y+ N+ Cx H RE+ VOL | 70.83 | 71.72 | 68.86M | 77.19 | 2.86 | 0/26 |
| FMX | 1.98 | 1.13 | 125.2 | -0.6 | A 8 | 2+ L+ Y N Cx H+ RE+ VOL | 128.05 | 128.46 | 123.33L | 138.74 | 5.13 | 0/14 |
| FTV | 0.52 | 1.08 | 144.1 | -0.6 | A 8 | 2 L+ Y+ N Cx H RE+ VOL | 66.18 | 66.55 | 63.89L | 71.87 | 2.66 | 0/28 |
| HLNE | 1.35 | 1.68 | 82.6 | -4.3 | A 8 | 2+ L+ Y N+ Cx H RE+ VOL+ | 85.42 | 86.54 | 83.08M | 93.07 | 3.46 | 0/21 |
| HY | 10.2 | 1.19 | 14.5 | -29.7 | A 8 | 2+ L+ Y+ N Cx H+ REx VOL | 17.3 | withheld | n/a | n/a | n/a | n/a |
| HYMC | 6.6 | 1.68 | 55.6 | -15.2 | A 8 | 2+ L Y+ N+ Cx H RE+ VOL+ | 13.74 | withheld | n/a | n/a | n/a | n/a |
| IA | 1.54 | 1.52 | 5.2 | -7.6 | A 8 | 2+ L+ Y+ N Cx H RE+ VOL | 18.46 | 18.65 | 17.91M | 20.11 | 0.74 | 0/101 |
| IAG | 5.12 | 1.97 | 100.7 | -4.4 | A 8 | 2+ L+ Y+ N+ Cx H+ RE+ VOL | 16.02 | withheld | n/a | n/a | n/a | n/a |
| JOBY | 11.11 | 1.39 | 133.1 | -19.1 | A 8 | 2+ L+ Y+ N Cx H+ RE+ VOL | 3.92 | withheld | n/a | n/a | n/a | n/a |
| LASR | 4.9 | 1.09 | 32.2 | -8.9 | A 8 | 2+ L+ Y N Cx H REx VOL | 34.29 | withheld | n/a | n/a | n/a | n/a |
| LAZ | 1.57 | 1.22 | 68.2 | -3.6 | A 8 | 2+ L+ Y N Cx H RE+ VOL | 37.62 | 38.12 | 36.6M | 41 | 1.52 | 0/49 |
| LMND | 5.73 | 1.32 | 61.1 | -6.8 | A 8 | 2+ L+ Y+ N Cx H RE VOLx | 38.03 | withheld | n/a | n/a | n/a | n/a |
| LPTH | 4.9 | 1.21 | 17.4 | -18.2 | A 8 | 2+ L+ Y+ N Cx H REx VOLx | 5.59 | withheld | n/a | n/a | n/a | n/a |
| LYFT | 5.14 | 1.26 | 159.8 | 0.4 | A 8 | 2+ L+ Y N+ Cx H REx VOL | 16.99 | 17.09 | 16.41M | 18.46 | 0.68 | 0/110 |
| LYNX | 4.06 | 1.64 | 5.5 | -3.2 | A 8 | 2+ L+ Y+ N Cx H RE+ VOL | 12.33 | withheld | n/a | n/a | n/a | n/a |
| MRCY | 1.25 | 1.54 | 40.3 | -5.7 | A 8 | 2+ L+ Y N Cx H+ RE+ VOL | 73.14 | 73.76 | 70.81M | 79.66 | 2.95 | 0/25 |
| MSI | 2.06 | 1.21 | 675.7 | 4.3 | A 8 | 2 L+ Y+ N Cx H RE+ VOL | 541.54 | 544.79 | 523L | 588.37 | 21.79 | 0/3 |
| NEM | 1.76 | 1.08 | 810.9 | -8 | A 8 | 2+ L+ Y+ N+ Cx H+ RE+ VOL | 101.54 | 102.19 | 98.11M | 110.37 | 4.08 | 0/18 |
| NEXA | 4.2 | 1.46 | 6.8 | -5.7 | A 8 | 2+ L+ Y+ N Cx H+ RE+ VOLx | 10.44 | 10.45 | 10.04M | 11.29 | 0.41 | 0/182 |
| NSIT | 3.26 | 1.06 | 68.1 | -2.9 | A 8 | 2+ L Y+ N Cx H+ RE+ VOL | 158.9 | 158.93 | 152.58M | 171.64 | 6.35 | 0/11 |
| NUE | 0.13 | 1.09 | 379.1 | -3.1 | A 8 | 2+ L+ Y N Cx H RE+ VOL | 248.59 | 248.94 | 238.99L | 268.86 | 9.95 | 0/7 |
| OMF | 2.05 | 1.52 | 61.2 | 1.7 | A 8 | 2+ L+ Y+ N+ Cx H+ RE VOL | 57.32 | 58.2 | 55.88M | 62.46 | 2.32 | 0/32 |
| OR | 3.91 | 1.4 | 27.2 | -2.3 | A 8 | 2+ L+ Y+ N+ Cx H+ RE+ VOL | 33 | 33.09 | 31.77M | 35.74 | 1.32 | 0/56 |
| PEN | 0.43 | 1.79 | 104.7 | 0.8 | A 8 | 2+ L+ Y+ N Cx H+ RE+ VOL | 323.87 | 333.11 | 319.79L | 352.93 | 13.32 | 0/5 |
| PGY | 2 | 1.61 | 26 | -14.4 | A 8 | 2+ L+ Y+ N Cx H+ RE+ VOL | 14.33 | withheld | n/a | n/a | n/a | n/a |
| PICS | 7.35 | 1.37 | 5.5 | -17.5 | A 8 | 2+ L+ Y+ N Cx H+ RE VOLx | 5.28 | withheld | n/a | n/a | n/a | n/a |
| RDVT | 2.76 | 1.37 | 12.3 | -5.8 | A 8 | 2+ L Y+ N Cx H RE+ VOL | 69.25 | 70.21 | 67.41M | 75.46 | 2.8 | 0/26 |
| RGC | 7.57 | 1.59 | 0.5 | -12.4 | A 8 | 2+ L+ Y+ N+ Cx H+ RE+ VOLx | 4.57 | withheld | n/a | n/a | n/a | n/a |
| RGLD | 3.55 | 1.15 | 179.8 | -2.5 | A 8 | 2+ L Y+ N Cx H+ RE+ VOL | 241.52 | 243.14 | 233.42M | 262.59 | 9.72 | 0/7 |
| RH | 8.67 | 1.45 | 117.2 | -12.1 | A 8 | 2+ L+ Y+ N Cx H+ RE+ VOL | 112.53 | withheld | n/a | n/a | n/a | n/a |
| SCZM | 9.64 | 1.28 | 5.5 | 5.9 | A 8 | 2+ L Y+ N Cx H+ RE+ VOL | 7.53 | withheld | n/a | n/a | n/a | n/a |
| TFPM | 3.6 | 1.34 | 23.4 | -1.9 | A 8 | 2+ L+ Y+ N+ Cx H+ RE+ VOL | 29.1 | 29.29 | 28.12M | 31.63 | 1.17 | 0/64 |
| TPB | 5.21 | 1.09 | 17.9 | -16.1 | A 8 | 2+ L Y+ N+ Cx H RE VOL | 48.35 | 48.75 | 46.8M | 52.65 | 1.95 | 0/38 |
| UNP | 2.6 | 1.11 | 913.6 | -0.2 | A 8 | 2+ L+ Y+ N Cx H+ RE+ VOL | 298.68 | 298.9 | 286.95L | 322.81 | 11.95 | 0/6 |
| VMET | 4.95 | 1.17 | 2.6 | -10.4 | A 8 | 2+ L Y+ N Cx H+ RE+ VOL | 7.23 | withheld | n/a | n/a | n/a | n/a |
| WAB | 2.6 | 1.75 | 322.5 | -0.5 | A 8 | 2+ L+ Y+ N Cx H+ RE+ VOL | 287.88 | 291.83 | 280.16M | 313.71 | 11.67 | 0/6 |
| WOR | 0.9 | 1.67 | 16 | -3.4 | A 8 | 2+ L Y N+ Cx H+ RE+ VOL | 58.08 | 58.68 | 56.34M | 63.29 | 2.34 | 0/32 |
| WPM | 5.15 | 1.62 | 319.9 | -2.4 | A 8 | 2+ L+ Y+ N Cx H+ RE+ VOL | 122.72 | withheld | n/a | n/a | n/a | n/a |
| XXI | 5.85 | 1.22 | 6.4 | -9.4 | A 8 | 2+ L Y+ N Cx H+ RE+ VOLx | 4.54 | withheld | n/a | n/a | n/a | n/a |

## 7. Research tail (1,187 names)

Every other reaction candidate: RESEARCH ONLY, no SpicyStock ticket and no levels. Tickers in the record's rank order, grouped by the one reason; a ticker whose final grade differs from its mechanical grade shows both.

- not admitted: dollar_no_expansion (225): PFGC, HLT, WH, AZO, CASY, CROX, PSA, SARO, STN, AAON, ACLS, ACMR, ADI, AEIS, AER, AGX, AIT, ALGM, ALV, AMAT, AMZN, APG, ARMK, AROC, ATI, ATMU, AUGO, AYI, BE, BEN, BETA, BFH, BH, BHE, BJRI, BLSH, BNY, BROS, BWA, BWXT, CALX, CASH, CDRE, CEVA, CGAU, CGNX, CIEN, CLFD, CLS, CMC, COIN, CRC, CRDO, CRUS, CSCO, CUBI, DCI, DELL, DOCN, DRS, DY, EFXT, ENLT, ENPH, ENS, ENTG, EPAC, ERO, ESI, ETR, EWBC, FCX, FDX, FERG, FFIV, FHI, FITB, FIX, FN, FPS, FTAI, FTI, GATX, GE, GEV, GGG, GRC, GS, GVA, HOOD, HPE, HQ, HUBB, IBKR, ICHR, INGM, INOD, IOND, ITT, ITW, JBHT, JCI, JEF, JXN, KAI, KEX, KGS, KLAC, KLIC, KN, KNF, KRMN, LEA, LEU, LIFE, LITE, LPLA, LSTR, MC, MCHP, MDA, META, MKSI, MOD, MPWR, MRVL, MSTR, MTZ, MU, MYRG, NE, NET, NOVT, NPO, NSSC, NTAP, NTRS, NUTX, NVMI, NXT, ODFL, OKTA, ON, ORA, OSK, P, PCAR, PH, PLAB, PLOW, PLUS, PLXS, PNC, PNRG, PNW, POWL, PRIM, PRU, PSX, Q, QCOM, RACE, RAL, RBC, RGEN, RMBS, ROAD, ROK, RPM, RS, RTX, RY, SF, SLF, SMCI, SMTC, SNA, SNDK, SNDR, SOLS, SPCX, SPXC, SSB, SSD, STM, STRL, SU, SUNB, SWK, SYF, SYY, TBBK, TD, TDG, TDY, TEL, TEM, TITN, TKR, TM, TNC, TROW, TSLA, TTC, TWLO, TWST, UMC, URI, VECO, VICR, VNOM, VPG, VRTS, VSAT, VSH, VTOL, WDC, WERN, WFRD, WHR, WLDN, WMS, XYL, YOU, ZWS
- mechanical grade B, below the trade band (209): ALLE, CINF, STZ, CCEP, EXR, RGA, DPZ, AN, ASH, ASST, BG, CHDN, CW, DASH, EQIX, ESE, GM, GPI, HNGE, HXL, IDA, IMO, LAD, LIN, MAR, MET, MPC, MWH, NGS, PAYC, SBUX, SXI, TATT, TPL, TSAT, TTEK, VLO, WATT, ASO, CAH, CRI, FSV, IBP, NXST, PII, ROP, VNT, ABG, ACDC, ACM, AFYA, AGL, AIR, ALSN, AMD, AMP, AMRZ, AOSL, AR, AXP, AYA, BC, BMO, BSP, BUR, BYRN, CACI, CDNS, CE, CHWY, CLMB, CMCO, CMPR, CNX, CNXN, COF, CP, CR, CRWD, CSX, CTS, CVNA, CWEN, DD, DINO, DKNG, DORM, DOV, EBAY, ECL, ECO, EE, EEFT, EMN, EQT, ESTA, ESTC, EVR, EXE, EXP, FANG, FAST, FBIN, FDXF, FIGS, FLOC, FND, FROG, FRPT, FRT, FSLR, FWONK, GCT, GD, GFF, GNRC, GWW, GXO, HAE, HAL, HALO, HLI, HPP, HQY, HRB, HRI, IBEX, ILMN, INSP, INVX, IP, ITRI, JLHL, KD, KKR, KMI, KNSL, KT, LSCC, MAIN, MAS, MATX, MDT, MEOH, MFP, MGRC, MMS, MMSI, MOS, MSGK, MSM, MTA, MZTI, NFG, NIC, NOW, NSC, NTCT, NU, NX, OKE, OLED, PATK, PBA, PJT, PPIH, PS, PSIX, PSN, QLYS, QXO, R, RBRK, RHLD, RJF, RNG, RRX, RYZ, S, SCL, SEI, SLB, SLVM, SMA, SMPL, TDC, TENB, TILE, TMDX, TRN, TRNS, TRP, TTWO, TXG, TXN, UBS, UMBF, UNH, VINP, VIRT, VOYA, VSEC, VVX, W, WDFC, WHD, WS, WTFC, XP
- mechanical grade C, below the trade band (191): AJG, MORN, OMC, PCOR, AA, AADX, AGLT, ALB, ASPE, BKR, BYND, C, CENX, CSIQ, ETOR, IFS, JBL, KTOS, MITT, NRG, PSQL, RUSHA, SQM, STLA, STT, TFII, UPST, ABNB, AFL, AGYS, BA, BKNG, BR, CVX, DEO, ENSG, FER, FLY, GEHC, HEI, IR, LII, LOAR, LYB, MCB, MMYT, MSCI, MSFT, NTSK, PAYX, PFG, PRI, SENEA, SNPS, SPGI, STNG, TBBB, AON, BBIO, PNR, ANT, CRS, CYD, KALU, MDRN, AAPL, ABT, AFRM, ALKS, AMCR, AMLX, APD, APO, APP, ARRY, ASND, ATR, AVY, AWI, AX, AXON, BALL, BCPC, BLK, BMRN, BN, BOOT, BRC, BSY, CB, CBRE, CHTR, CLX, CME, CNI, COCO, COR, CPAY, CPT, CRBG, CRVL, CTEV, CTRI, CTRN, CWK, DIS, DT, DTM, ENTA, EQH, FCUV, FICO, FLS, FTNT, GBX, GL, GPGI, GTLB, H, HII, HON, HURN, ICE, INGR, INTR, IPAR, IQV, KBR, KRT, KRUS, LFTO, LGIH, LHX, LMT, LQDT, LRN, LUV, MA, MDLN, MHK, MLAB, NBIX, NDAQ, NFLX, NTRA, NYT, OI, PGR, PINS, PKG, PNFP, PPG, PYPL, PZZA, RBA, RES, REZI, RIG, ROCK, RRC, RVTY, SAIC, SBAC, SITE, SLG, SMG, SPG, SPRY, SSP, SW, TEN, TFC, THC, TJX, TPC, TPR, TXRH, ULS, USB, VAL, VMC, VNO, VVV, WAL, WELL, WFC, WLY, WSM, WYNN, ZG, ZS
- quality veto: up_days (72): AFG, AXS, AIZ, HZN, VLTO, AEE, MRSH, USFD, HCA, HIG, IBM, PCTY, TYL, AIG, CTAS, EG, STE, FCN, ADP, ANF, BL, CAR, DBD, DOX, EFOR, EHC, ESS, ICFI, JKHY, QSR, SR, SUPN, TEAM, TREE, TRV, UFPI, WEX, WK, WM, CLNN, DBX, DLB, HUBS, MNDY, RYAN, ADSK, BDX, COLM, CRAI, CSGP, FDS, G, HD, IT, LOW, MCD, MTH, PHM, POST, PRG, RBLX, RKT, TGLS, VEEV, VRSN, APPN, DHI, STC, ACN, EFX, LEN, TRI
- quality veto: not_linear (322): AAMI, AAOI, ACHR, ADEA, AEHR, AG, AGCO, AGI, AGRO, ALLY, ALNT, AMBA, AMKR, AMR, AMSC, AP, APH, ARCB, ARQQ, ARW, ASM, ASTS, AVAV, AVGO, AVT, BAP, BDC, BIO, BLBD, BTU, CAMT, CAT, CBRS, CCJ, CDE, CDNL, CDZI, CHRN, CMI, CNH, CNR, COHR, COHU, CRCL, CRWV, DAVE, DCO, DGII, DIOD, DLR, ECG, ECHO, EGO, ELE, EME, ENVA, EQPT, ESQ, ETN, EXK, EZPW, FCEL, FCFS, FIGR, FLEX, FORM, FSS, FTK, GENI, GFS, GLW, GOLD, GOOG, GOOGL, HBM, HLIO, HSBC, HUT, IDCC, IE, IESC, IEX, INIO, INTC, IONQ, IPGP, IRDM, IREN, IVZ, JPM, KEYS, KGC, LB, LBRT, LECO, LFUS, LGN, LNN, LOGI, LRCX, MAIR, MDB, MRX, MS, MTCH, MTSI, MUX, MXL, NBIS, NDSN, NESR, NEU, NEWP, NPK, NVDA, NVT, NVTS, OII, OKLO, ONEW, ONTO, OPY, OSIS, OSS, OTTR, OUST, PAAS, PANW, PDFS, PENG, PPTA, PRLB, QUBT, RIO, RIOT, RKLB, ROG, SA, SAIA, SAIL, SANM, SCCO, SCSC, SEDG, SEIC, SHAZ, SHLS, SHOP, SII, SILC, SITM, SKE, SMC, SMHI, SNOW, SNX, SSRM, ST, STX, TECK, TER, TGB, TSEM, TTAM, TTMI, UCTT, UHS, USAU, VGNT, VIAV, VOXR, VOYG, VRT, VST, WCC, WNC, WTS, WWD, XPO, YSS, ZBRA, ADM, AXTI, BTDR, CRL, FEIM, HWC, MEI, STLD, VELO, WOLF, MANH, ALAB, AMG, ANET, ARXS, ASTH, ATRO, AVEX, BCC, BCO, BPOP, CFG, CLH, COMP, DAR, DPC, DRUG, ECPG, ELF, EOG, EXPE, FET, FLR, FUL, GHM, GPC, GRPN, HONA, HPQ, HWM, LMB, MGA, MIR, MTW, NBN, NXPI, PRM, RNR, SAH, SIND, SNDA, SON, TDW, TLN, UEIC, VCTR, WBI, WHK, WMB, ZETA, CELH, COKE, DVN, EROK, FELE, GGB, GPOR, MBI, NGVT, OPTX, SPHR, SXT, TRGP, VMI, XMTR, AIN, AKAM, ARE, BBY, BSX, CAKE, CARR, CCSI, CHKP, CHRW, COGT, COP, CPIX, CXW, ELV, HCC, HHH, HNI, HP, INBX, JAGX, KOP, LGND, LNG, MAA, MLI, MTB, OMH, OSCR, PCVX, PI, PLTR, QNT, RDDT, SDRL, SGI, SHW, SJT, SSNC, SWKS, TRMB, UNM, V, XYZ, CAVA, CNMD, CRM, GRBK, GTBP, KNTK, MBC, MOH, MSGE, PEGA, RMD, SYM, WIX, CPA, DECK, EL, GOSS, RDWR, VKTX, KRYS, APPF, MDGL
- mechanical grade skip, below the trade band (157): DSGX, SHAK, ALG, BAC, CBT, DUOL, MSA, PUMP, THRM, UBER, UHAL, VC, YARW, APEI, ATEX, BRO, CCB, CING, DOCU, EW, EXPD, GLBE, GMED, GPN, GWRE, HSY, HUM, ICUI, INSW, JAZZ, KSS, LINC, MELI, MLM, NKE, NOC, PFSI, POOL, PVH, QTWO, SAM, SCI, TEX, TMO, UTHR, WAT, WLK, XRAY, ANAB, ADBE, ALC, ANRO, AOS, ARES, BAH, BAM, BHVN, BMI, BURL, BX, CG, CNM, CRH, CSL, CVLT, CVSA, DCBO, DHR, EGP, EWTX, FISV, FLYW, GDDY, GRAL, GRMN, HELE, HUN, IRON, JACK, JLL, LDOS, LOPE, LPX, LULU, MAZE, MBX, MCO, MMM, MNPR, OCTV, OKUR, OLN, ORKA, PAR, PODD, PPLI, PRAX, PRGS, PROF, SEPN, SEZL, SKY, SN, SPOT, STEP, STOK, SYK, TFX, TKO, TOL, TPG, TRAX, TREX, VRDN, VYLR, VYX, WD, WSO, WTW, Z, ZBH, ZM, ADAM, ARWR, BCAX, BNAI, CUE, KWR, QURE, UNCY, UNF, ALGN, BLDR, BLKB, COO, FTDR, GKOS, NAVN, OC, RCL, RL, SYRE, TRU, WCN, DKS, ISRG, PVLA, U, UPS, ZTS, AXSM, CELC, EAT, HSIC, ZONE, NFE, USEA
- quality veto: up_days, not_linear (11): BBNX, CCS, SFM, WDAY, FRHC, EPAM, CNXC, CTSH, GRDN, IFF, FOUR

## 8. Setting up (anticipation): 2 listed, 10 also quiet

Of 844 momentum names, 323 quiet, 2 pass the coil checks. The record's own sentence over its list (the model's rule, not an instruction to the reader): "Buy only if it clears its trigger in the first 30 minutes on volume already above yesterday's pace; an open more than 2% above the close is gapped and needs a catalyst check before you buy."

### CART · Maplebear Inc. Common Stock · listed 1 · RESEARCH ONLY: no SpicyStock ticket

- Measured: close $57.68 (0.58% today); setups TI65; compress 0.56, tight days 3, quiet days 6, volume ratio 0.56, ADR 1.8%, extension 0.99; box $56.88 to $58.75 over 5 sessions (2026-11-19 to 2026-11-25).
- research levels (record; no order is offered at them): trigger $58.81; limit $59.40; stop $56.88 (lowest low of the last 3 sessions, 4.24% under the limit); gap check above $58.83; sell-half $63.51; risk a share at the limit $2.52; the plan rule refused it, so no model size is stated.
- No ticket: ticket withheld: at the $59.40 limit, the highest fill the ticket permits, the stop $56.88 is 4.24% away, past his 4% line; the setup stands, the ticket does not (stage `market`).
- Open-entry note (not the ticket): MOO/OPG at the open only for the top 2 names on the list, and only if it opens within +2% of $57.68
- Event registry: not_in_registry.

### OGN · Organon & Co. Common Stock · listed 2 · RESEARCH ONLY: no SpicyStock ticket

- Measured: close $13.86 (-0.43% today); setups DT; compress 0.67, tight days 5, quiet days 4, volume ratio 1.28, ADR 0.3%, extension 1.00; box $13.85 to $13.94 over 10 sessions (2026-11-12 to 2026-11-25).
- research levels (record; no order is offered at them): trigger $13.96; limit $14.10; stop $13.85 (lowest low of the last 3 sessions, 1.77% under the limit); gap check above $14.14; sell-half $15.08; risk a share at the limit $0.25; model size 0 shares, $0.00 cost, $0.00 risk (multiplier 0.00); at full size 531 shares, $7,487.10; at the YELLOW size 300 shares, $4,230.00; no new longs: the size multiplier is 0.
- No ticket: breadth sizes new positions at zero tonight (stage `market`).
- Open-entry note (not the ticket): MOO/OPG at the open only for the top 2 names on the list, and only if it opens within +2% of $13.86
- Event registry: not_in_registry.

Also quiet (not listed; no plan; every row RESEARCH ONLY: no SpicyStock ticket):

| ticker | setups | close | compress | tight | vol ratio | trigger | stop | risk % | why not listed |
|---|---|---|---|---|---|---|---|---|---|
| BILL | DT/TI65/MDT | 61.55 | 1.00 | 6 | 4.30 | 61.81 | 61.45 | 0.6 | failed compress |
| HGV | TI65 | 44.57 | 0.94 | 4 | 0.99 | 45.28 | 43.55 | 4.0 | failed compress |
| LTH | DT/TI65 | 47.81 | 0.88 | 5 | 0.69 | 48.53 | 46.51 | 4.3 | failed compress |
| MD | TI65 | 30.48 | 0.77 | 5 | 0.80 | 31.42 | 30.22 | 4.0 | failed compress |
| RARE | TI65 | 18.11 | 1.02 | 5 | 0.64 | 18.20 | 16.82 | 8.2 | failed compress |
| PTLO | DT/TI65/MDT | 6.17 | 1.02 | 3 | 0.85 | 6.46 | 5.66 | 14.1 | failed compress |
| AXGN | DT/TI65/MDT | 59.34 | 0.87 | 3 | 0.65 | 60.17 | 56.02 | 7.4 | failed compress |
| LAW | DT/TI65/MDT | 6.12 | 1.74 | 3 | 1.54 | 6.31 | 5.82 | 8.4 | failed compress |
| PGNY | DT/TI65/MDT | 36.27 | 0.87 | 6 | 0.93 | 36.89 | 35.27 | 4.6 | failed compress |
| ENR | TI65/MDT | 27.92 | 1.58 | 4 | 1.36 | 29.29 | 27.32 | 7.2 | failed compress |

## 9. Open model plans (0)

Open MODEL plans walked on daily (and retained minute) bars; not holdings.


## 10. Model record

- Scorecard: 22 plans in 60 sessions (2026-09-01 to 2026-11-25): 5 settled (2 wins, 3 losses, 0 even), 0 open, 0 pending, 1 uncertain, 14 not filled, 2 unmeasured; sum of R 0.43.
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

- Event registry (manual; known cash acquisitions only): 7 entries, last reviewed 2026-11-25, 0 days before the measured session 2026-11-25. None of its 6 unresolved entries is past its review date (next due 2026-12-02). None of the 1260 listed rows (1248 bursts, 2 setting up, 10 also quiet) is in the registry. A stock that is not in the registry has not been cleared: SpicyStock reads no company news; of the 1260 listed names, an earnings date was read for 56 and SEC filings for 73 (the tickets', and the candidate checks' flags for up to 80 names; a check that could not read a name says unknown, never clear).
- Entries: MG (cash_acquisition, announced 2026-09-18, review due 2026-12-17); PRTH (cash_acquisition, announced 2026-09-21, review due 2026-12-17); ARX (cash_acquisition, announced 2026-08-13, review due 2026-12-17); BWIN (cash_acquisition, announced 2026-09-14, review due 2026-12-17); ACVA (cash_acquisition, announced 2026-09-10, review due 2026-11-25, ended 2026-10-16); ZIM (cash_acquisition, announced 2026-02-16, review due 2026-12-02); CCC (cash_acquisition, announced 2026-10-15, review due 2026-12-17).
- Status words: `known_event` = in the registry and blocked for a SpicyStock ticket; its manual review is current; `review_required` = in the registry and blocked for a SpicyStock ticket; its manual review is overdue; `not_in_registry` = not in the registry: NOT a clearance, nothing was checked.
- Earnings and 8-K check: status `not_applicable`; 0 ticket rows; 1,187 of 1,260 listed names had nothing read (an earnings date read for 56, SEC filings for 73).
- Not checked by SpicyStock: company news and press releases, announced earnings dates, offerings and shelf takedowns, FDA and trial dates, halts outside the morning check, delisting notices beyond 8-K item 3.01 on the names checked, index changes, lockup expiries, ex-dividend dates.

## 12. Rules

- Rules digest `fa7df9ae9b76`; without the universe membership identity `63ff95fff12b` (membership identity `5c674e4a20da44d3`): the record's digest nests the universe membership identity, so it moves on any night the selection's membership moves; `digest_without_membership` is the same digest with that identity removed, and moves only when an archived rule changes.
- pipeline: trade_grades ["A+", "A"], yellow_grades ["A+"], max_reads 12, reader_policy "accepted_required_v1", reader_refusal_fraction 0.25, reader_refusal_min 1, stale_tolerance_fraction 0.01, stale_sessions_max 5, min_coverage_fraction 0.5
- plan: entry_below_pct 2.0, entry_above_pct 4.0, skip_gap_pct 8.0, entry_window_minutes 30, assumed_slippage_pct 1.0, limit_rule "stop_constrained", sizing_basis "order_limit", max_stop_pct 4.0, ideal_stop_pct 2.0, stop_risk_multiplier 0.5, gain_ceiling_pct 15.0, extension_hazard_pct 20.0, hazard_multiplier 0.5, sell_half_pct 8.0, abnormal_day_pct 10.0, gap_exit_pct 20.0, sell_half_day 3, no_progress_day 3, trail_from_day 3, final_exit_day 5, allocation_policy "combined_stages_reserved_principal_v1"
- admission: version 1, policy "burst_route_or_dollar_expansion_v1"
- grading: reader_request_version 3
- record: scorecard_min_plans 20, scorecard_sessions 60

## 13. Bounds

- brief.json: 26 candidates in detail, 35 compact, 0 moved to the tail for size. Tickets and reviewed names are always detailed; of the rest, in the stated order, the largest multiple of 4 (or all) is detailed that keeps brief.json within 250000 bytes, and the others are compact rows; only if none can be detailed are compact rows cut, to the largest multiple of 10 that fits, the rest moving to the research tail.
- This file: 14 in detail, 47 compact rows, 0 compact rows left out, 0 research-tail names not named; reviewed names in their short form: no; model-record tables printed: no. Rule: tickets and reviewed names always in detail; then, to stay within 80000 bytes, the model-record tables are given up first, then the other names' detail (largest multiple of 2 that fits), then tail names (multiple of 50), then the reviewed names' check measurements and all but a cut reason of their reader sentences (the short form), then compact rows (multiple of 5); brief.json carries what this file leaves out.
- Research tail: 1187 named, 0 left out (the first 4000: the admitted trade-band names moved out for size, then the rest by the record's rank order). Open plans left out: 0. Stale names left out: 0. The evening run's model-record block is carried whole when its canonical encoding is within 60000 bytes and the brief still fits with it; past that bound it is carried reduced (each plan row keeps its identity, result and account; the setups table is left out), and not at all if that does not fit either; brief.md prints its sentences and, while they fit, the first 30 rows and 12 columns of each of its tables. A copied sentence over 900 characters is cut and ends with an ellipsis.

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
- SpicyStock reads no company news. Earnings and SEC 8-K items are read from SEC filings for published tickets, and under the candidate checks (`service.candidate_checks`) as flags for the night's other candidates up to its bound: a projected date is an estimate, never an announced date, unknown is never clear, and filings are not news coverage.
- The event registry is a hand-kept list of known cash acquisitions. A stock that is not in it has not been cleared: issuer news, offerings, guidance and other corporate events are not checked.
- One provider's bars as of the run's fetch; a session's volume can be revised afterwards. The universe is the selection named in `service.universe`, not point-in-time membership, and a stock named stale had no bar for the session: its inputs are unknown, not a measured non-match.
- Whether the broker accepts the printed order form (a day buy stop-limit with a one-triggers-the-other sell stop) is unconfirmed; see knowledge/broker-fidelity.md.
- Rows are bounded. `bounds` states every list that was cut, how many rows were left out and the rule that chose the kept ones; the canonical record carries every row.
- This brief is bound to one publication by the SHA-256 and byte length in `identity.canonical`. Whether a newer publication exists is not in this file: apply `service.freshness_rule` with your own clock.
