# SpicyStock daily brief: measured Thu 10 Sep 2026, plans for Fri 11 Sep 2026

> This is SpicyStock's daily brief: one evening publication's model output, derived from that publication's record and its pick ledger, with the model-record block the same evening run computed from its own bars carried in (section 10), and from nothing else, for an outside analyst to read in place of the full record.
> Check that it is current before using it: `status` must be `derived`, and the freshness rule in section 2 (`service.freshness_rule`) is applied with your own clock.
> Only the rows in section 5 (`tickets`) are published model tickets. Every other row is research only: its levels are reference arithmetic and SpicyStock offers no order for it.
> SpicyStock places, cancels and observes no order and reads no brokerage account. The owner decides and places every order.

**Model gate GREEN: size multiplier 1.0; 1 published model ticket for the applicable session.** The record's own cover sentence, written for its model tickets and not an instruction to the reader: "Trade next session. 1 A-quality burst."

## 1. Identity and binding

- Measured session: 2026-09-10 (open); plans are for **2026-09-11**, entry window 2026-09-11T09:30:00-04:00 to 2026-09-11T10:00:00-04:00 (America/New_York), full session closes 2026-09-11T16:00:00-04:00.
- Published 2026-09-10T22:30:00+00:00 (evening, FIXTURE full); rules version `583191ddb160`.
- Canonical record `data.json`: 335,815 bytes, SHA-256 `c277356b79c77e6256d7249f78fc443d780c1fc617691110c75f629de71c7b6c`.
- `picks.json`: 43,332 bytes, SHA-256 `367048d4d41725bfcf61f70ea79701fb55a68a2552e7b20dbae46eaf208ea9b2`.
- This file renders `brief.json` (72,494 bytes, SHA-256 `65338b8685de892c67c3f1291c5616a87b143761310dc78e60c43a88e0075601`).
- Page https://spicychicken59.github.io/SpicyStock/ · record https://spicychicken59.github.io/SpicyStock/data.json · brief https://spicychicken59.github.io/SpicyStock/brief.json and https://spicychicken59.github.io/SpicyStock/brief.md.

## 2. Service state

- Run status: **ok**; problems: none; mail skipped.
- Delivery: Published 6:30 PM ET on Thu 10 Sep, 135 minutes after the measured session's completion (4:15 PM ET); after the primary slot (6:16 PM ET) and before the retry slot (8:16 PM ET); before the next session's open (Fri 11 Sep, 9:30 AM ET). (slot `after_primary`, 135.0 minutes after completion).
- Next publication (`service.expected`): the next session is 2026-09-11; it completes at 2026-09-11T16:15:00-04:00; primary slot 2026-09-11T18:16:00-04:00; retry slot 2026-09-11T20:16:00-04:00; recovery limit 2026-09-14T09:30:00-04:00.
- Freshness rule (states: `newest`, `not_due`, `pending`, `late`, `missing`):
  - Freshness is the reader's own computation: this file carries no clock. Compare your own clock, as an instant with its UTC offset, with the instants in `service.expected`, in this order, and stop at the first that holds.
  - 1. Before `completion_at`: `newest`. The next session has not completed, so no record of a later session can exist yet. The same session can still be published again, and a later run can withdraw a ticket: before acting on a ticket, fetch the file again and compare `identity.canonical.sha256` with the copy the plan was built on.
  - 2. Before `primary_slot_at`: `not_due`. The next session has completed and its evening run is not yet due.
  - 3. Before `retry_slot_at`: `pending`. The first scheduled slot has passed and the retry slot has not.
  - 4. Before `recovery_until`: `late`. Both scheduled slots have passed; a delayed run can still publish the next session until that instant.
  - 5. Otherwise: `missing`. The service does not publish a session after the session that follows it has opened. If this is still the newest file the site serves, the next session was not published and every ticket in this file is expired.
  - From step 2 on, fetch the file again before relying on it: a newer one may exist. A field that is null has its reason in `service.expected.unknown`; without the instant a step needs, freshness is unknown and the file is research only.
  - Freshness is not permission. A ticket applies only from `identity.entry_window.opens_at` to its `cutoff_at`; after the cutoff it is over, whatever state this rule gives.
- Morning check: plans are for 2026-09-11; entry window 2026-09-11T09:30:00-04:00 to 2026-09-11T10:00:00-04:00; the morning collection starts at 2026-09-11T09:00:00-04:00. Receipt https://spicychicken59.github.io/SpicyStock/morning.json: A morning receipt belongs to this publication only when its `publication.data_sha256` equals `identity.canonical.sha256`. One generated before `window_opens_at` carries no quote from inside the entry window. The receipt is not part of this file: it lands the next morning, if a morning check runs.
- Inputs: Alpaca `sip`, split-adjusted 1Day bars, read by the run that began 2026-09-10T22:30:00+00:00; 32 of 32 intended stocks ready (acceptance `ok`); 32 measured, 0 stale.
- Stale tolerance: `complete` (0 stale against a limit of 0).
- Minute bars: 12 plans had a first day the daily bar could not place without minute bars; 8 asked for, 0 fetched, 0 stored; 4 past the run's 8; 8 not fetched (no_minutes); minute bars are retained for 0 plans' first days.
- What the inputs do not establish: Why a stale stock had no session bar is not established; its session inputs are unknown, not a measured non-match, until a later run reads the session again. These bars are the provider's as read by the run that began at 2026-09-10T22:30:00+00:00; a session's volume can be revised afterwards, and this file does not measure by how much. One price source: nothing cross-checks a close, a volume or a split. Bars are adjusted as `service.inputs.basis.adjustment` says and for nothing else. The universe is the selection named in `service.universe`, as fetched; it does not establish which stocks were listed during the session, and the record does not name the stocks that entered or left since the previous publication.
- Chart reader (claude-sonnet-4-6): 4 of 4 reads accepted, verdict `complete`. Chart reader cost: 4 calls for 4 names, 4 replies; 14,612 input tokens (4,436 uncached, 2,544 written to the cache, 7,632 read from it) and 360 output tokens, under claude-sonnet-4-6. Token counts as the API reported them; the record carries no price.
- Review selection (`account_feasible_first_research_v2`): 3 feasible, 4 requested of 12; selected: AAPL (opportunity), AMD (opportunity), NVDA (opportunity), TSLA (research_ranked).
- Admission: 7 reaction candidates, 5 admitted to the trade band and the chart reads (5 by the 4% scan, 0 by the dollar scan on a range-expansion, higher-volume day); 2 came through the dollar scan alone without one and are research only. Of the 5 mechanical A-band names without a veto, 4 are admitted and 1 is not. Admission is read off the recorded discovery route and the checklist's own range-expansion and volume checks; it is never a grade, and the chart reader never sees a name it stops.
- Earnings and 8-K items (status `checked`): Earnings, estimated from SEC results filings for 1 ticket: 1 estimated inside the hold window. An estimate warns and never withholds a ticket. SEC current reports (8-K) in the 14 days before the signal or since: 1 with a material item; a material item names a kind of event and withholds nothing.
- Candidate funnel under a GREEN market: 7 reaction candidates discovered, 4 potentially usable (mechanical grade in the admitted band, no veto, discovery admitted), 1 reaction ticket. Reaction candidates stopped at: 2 mechanical grade below the regime's admitted band, 1 dollar scan alone, without a range-expansion, higher-volume day, 1 ticket withheld: stop rule at the limit, 2 slot cap. Anticipation: 10 momentum names, 4 quiet, 1 passing the coil checks, 1 listed, 0 tickets. Listed setups stopped at: 1 slot cap. A stage is where the record's own gates stopped a name; it is not a judgement of the setup and establishes no entry.
- Closest miss: PLUG came closest at B 8.5: fails close near the high.

## 3. Market regime

- Verdict **GREEN** for 2026-09-10: size multiplier 1.00; grades the regime admits to a ticket: A+, A. The light is SpicyStock's gate for its own model tickets: an input to weigh, not an instruction to the reader.
- Recorded reason: down 4%: 0 < the scaled alarm of 3.4 (700 of 6,500)
- Recorded reason: 10-session ratio 2.75 (11 up, 4 down) >= 1.0
- Recorded reason: 5-session ratio 4.0 (8 up, 2 down) >= 0.5
- Recorded reason: 10-session ratio 2.75 (11 up, 4 down) >= 2.0
- Recorded reason: up 50% in a month: 0 <= the scaled hot mark of 0.1 (20 of 6,500)
- Counts over 32 measured stocks (32 intended, 32 with a session bar, 0 under the $3.00 session close floor): up 4% 5, down 4% 0; up/down 25% in a quarter 1/0; up/down 25% in a month 0/0; up/down 50% in a month 0/0; up/down 13% in 34 days 8/0; 59.4% above the 40-day average.
- Ratios: 5-session 4.00 (8 up, 2 down, unrounded 4); 10-session 2.75 (11 up, 4 down, unrounded 2.75). The rules compare the rounded number.

All five regime rules, in the order they are asked (universe 32 against a reference of 6,500). Count thresholds are the reference count times the stocks measured over the reference universe; that scaling is this project's own. Ratio thresholds are not scaled.

| rule | tier | measured | comparison | threshold tonight | reference | fired | decides | masked |
|---|---|---|---|---|---|---|---|---|
| down4_alarm | red | down4 0 | at or over | 3.4 | 700 of 6,500 | no | no | no |
| ratio_10d_red | red | ratio_10d 2.75 | under | 1 | 1, not scaled | no | no | no |
| ratio_5d_red | red | ratio_5d 4 | under, with more names down 4% than up 4% today | 0.5 | 0.5, not scaled | no | no | no |
| ratio_10d_yellow | yellow | ratio_10d 2.75 | under | 2 | 2, not scaled | no | no | no |
| up50_month_hot | yellow | up50_month 0 | over | 0.1 | 20 of 6,500 | no | no | no |

- GREEN needs all five rules quiet: fewer than 3.4 names down 4% today (it is 0); a 10-session ratio at or over 2 (it is 2.75: 11 up against 4 down); no 5-session ratio under 0.5 with more names down 4% than up 4% today (it is 4, with 0 down against 5 up); and no more than 0.1 names up 50% in a month (it is 0).
- Yellow by rounding (more ten-session breakdowns than breakouts while the rounded ratio is not under the red line): no. Near a line: no (the 10-session ratio is 1.75 from the red line and 0.75 from the yellow line; band 0.06, the band is this project's own label bound, the largest later re-reading of a published ratio seen through 17 November 2026; it is not a rule and gates nothing).

Breadth history (the newest 10 sessions of the record's own breadth history, each read again tonight over tonight's stocks: an earlier session's counts can differ from what its own night published): 2026-08-27 1/1 r10 1.14; 2026-08-28 0/0 r10 1.14; 2026-08-31 0/1 r10 1.00; 2026-09-01 1/0 r10 1.17; 2026-09-02 1/0 r10 1.40; 2026-09-03 1/0 r10 2.00; 2026-09-04 1/1 r10 1.80; 2026-09-08 0/1 r10 1.60; 2026-09-09 1/0 r10 1.40; 2026-09-10 5/0 r10 2.75.

## 4. Model account

- Model account (the model's configured sizing assumptions; not a brokerage balance): equity $10,000.00, risk 0.50% a trade, position cap 25.00%, 4 slots.
- Model allocation: next-session tickets would commit $505.88 of the configured $10,000.00; 4 of 4 slots (3 open model plans); $1,762.98 reserved for unfinished model plans.
- Cut: TSLA (burst, withheld): ticket withheld: no limit above the $124.33 buy stop keeps a stop inside his 4% line — the burst day's low $113.59 caps the limit at $118.32, at or under that buy stop; the bar's midpoint $119.18 caps the limit at $124.14, at or under that buy stop; the setup stands, the ticket does not
- Cut: AMD (burst, slot_cap): the 4-slot model cap: 3 open model plans and AAPL take the rest; take AMD only if a plan above is not held or stops out
- Cut: NVDA (burst, slot_cap): the 4-slot model cap: 3 open model plans and AAPL take the rest; take NVDA only if a plan above is not held or stops out
- Cut: COIL (anticipation, slot_cap): the 4-slot model cap: 3 open model plans and AAPL take the rest; take COIL only if a plan above is not held or stops out

## 5. Published model tickets (1)

Every ticket here is a MODEL ticket sized for the model account in section 4; SpicyStock places no order. Order kind `buy_stop_limit_oto`: a day buy stop-limit whose fill triggers a good-til-cancelled sell stop (one-triggers-the-other). The record's action word is a legacy word for an eligible ticket and never means a market-on-open order: the order is `order_as_written`. Where the buy stop is `equal` the last close, a broker takes a buy stop only above the current price, so the order can be entered as written only while the stock trades under its last close. Price states are the words of the morning receipt's rows[].price_checks: where a price sits against the ticket's lines, never an entry or a cancellation instruction. The dated lines are the model's own schedule.

### AAPL · burst · A+ 10.00 · TICKET

- Order as the record wrote it: `Buy 4 AAPL stop-limit: stop $124.33 limit $126.47, day · OTO sell 4 AAPL stop-loss $121.42 GTC`
- levels (record): trigger $124.33; limit $126.47; stop $121.42 (half_range, 3.99% under the limit); day-2 line $129.18; skip if it opens under $121.73; sell-half $135.49; risk a share at the limit $5.05; model size 4 shares, $505.88 cost, $20.20 risk (multiplier 0.50); at the YELLOW size 2 shares, $252.94.
- Order entry: kind `buy_stop_limit_oto`; 4 shares; last close $124.21; the buy stop is `above` the last close; extended above $134.15; record action word `buy_at_open` (legacy).
- Price states: `below_stop` at or under $121.42; `below_entry_floor` over $121.42 to under $121.73; `below_trigger` from $121.73 to under $124.33; `within_published_band` from $124.33 through $126.47; `above_limit` over $126.47 through $129.18; `above_day2_extension` over $129.18.
- Reader's entry note (not the ticket): Skip it if the first print is above the ceiling; a print under the skip line says the burst is failing.
- Limit: the ticket's limit is $126.47: the $129.18 day-2 ceiling (the close +4%) narrowed to the highest price at which the bar's midpoint $121.42 is still inside his 4% line
- Pre-open check: before the open: if the pre-market print is under $121.73 the burst is failing, over $129.18 (+4%) day 2 is spent, and over $134.15 (+8%) he would be selling; do not place the order in any of the three. The ticket's own limit is $126.47, under that day-2 line: an open above it does not fill at the open, though a resting order stays live
- Sizing: sized at the $126.47 limit, the highest fill the ticket permits: 4 shares put $20.20 between that fill and the $121.42 stop, planned price-to-stop risk, not a maximum loss
- Resize: if your fill differs, shares = $25.00 / (fill - $121.42), and no more than $2,500.00 of stock
- Term: A day order rests until the close unless you cancel it. The plan's entry is the first 30 minutes: if it has not filled by then, cancel it yourself; SpicyStock places and cancels nothing.
- Term: An open above the $126.47 limit does not fill at the open, but the resting order stays live and can fill on a pullback under $126.47 later in the day: cancel it rather than let it.
- Term: An open under $121.73 is the burst failing: do not place the order, or cancel it; the buy stop at $124.33 would still trigger if the price recovered.
- Term: The sell stop at $121.42 is attached the moment the buy fills (OTO), as a stop-market order; nothing is protected before the fill.
- Day 1 (2026-09-11): buy in the first 30 minutes inside $121.73–$126.47; the sell stop at $121.42 is live from the fill. Skip it if it opens above $129.18 or under $121.73; cancel the day order yourself if it has not filled by the end of the first 30 minutes.
- Day 1 (2026-09-11): if same or next day, the price reaches $135.49 (+8% from $125.45): sell half and move the stop to 25-50 cents under that day's high.
- Day 1 (2026-09-11): at the close of day 1: the stop rises to the entry day's low if that is above $121.42.
- Day 2 (2026-09-14): if day 2 is green: do not move the stop to break-even before day 5 just because it is green.
- Day 3 (2026-09-15): at the day 3 close: sell at least half at the close. If day 3 closes at or below $125.45: exit: no follow-through.
- Day 4 (2026-09-16): raise the stop to each day's low (it never moves down); sell the rest into strength.
- Day 5 (2026-09-17): at the day 5 close: exit the remainder into strength.
- Event registry: not_in_registry.
- Earnings: Earnings estimated about Mon 14 Sep (±7 days), from last year's results filing of 15 Sep 2025: inside this ticket's hold window Fri 11 Sep–Thu 17 Sep. An estimate from SEC filings, not an announced date: check the company's announcement before entry.
- SEC current reports: Recent SEC current report: 8-K item 1.01 (Entry into a Material Definitive Agreement) filed 8 Sep 2026, accepted Tue 8 Sep 5:05 PM ET, before the signal session's close. An item names a kind of event, not what the filing says: read it before entry. A warning and not a refusal; only the manual event registry withholds a ticket. Other items filed in the 14 days before the signal or since: 9.01 (Financial Statements and Exhibits).

## 6. Admitted trade-band candidates (4 of 5 in the band; 7 discovered)

Definition: reaction candidates whose mechanical grade is in the trade band (A+, A), with no quality veto, that the discovery admission admits; plus any other name with a published ticket or a selected chart review. Order: published tickets, then names selected for a chart review, then the rest; each in the record's rank order (grade, score descending, ticker). Model status: a row is `TICKET` only when the record published a model ticket for it (its order is in `tickets`); every other row is `RESEARCH ONLY: no SpicyStock ticket`. Later gates: the gates after the market gate, re-derived from the row's recorded fields so a RED night does not hide them; passing them is not a ticket: the stop rule, the event registry, sizing and the slot allocation follow, and the market gate stands.

Checklist, the same thresholds for every name. **2** not up two days in a row: up_run <= 1, counting days above +1.0%; veto at 3+ up closes of any size (weight 1.5). **L** linearity of the prior leg: ER >= 0.4 or R2 >= 0.55 (both for A+); failing is a veto (weight 2.0). **Y** young trend: first or second breakout: prior breakouts since the move started <= 1 (0 for A+) (weight 1.5). **N** narrow or negative day before: prior day negative or range < 2.0% (A+: negative and under its 20-session median range) (weight 1.5). **C** consolidation quality: base 3-20 sessions, breakdowns <= 1, giveback <= 0.34, tightness <= 1.0 (A+: 0 breakdowns, 0 bursts inside, giveback <= 0.25, tightness <= 0.7, base volume under the leg's and the 50-session average) (weight 2.0). **H** close near the high: close_pos >= 0.8 and close > open (A+ >= 0.9; partial from 0.7) (weight 1.5). **RE** range expansion: today's range over the largest of the prior 5 >= 1.0 (A+: also over the prior 10) (recorded, no weight). **VOL** higher volume: volume > prior session (A+: rank <= 3 of the last 60); a base over 21 sessions also needs >= 1.5x the 50-session average (recorded, no weight).
Check marks: letter then + (pass at the A+ level), nothing (pass), ~ (partial), x (fail), ? (not measured).

Hold days for a plan entered on the applicable session: day 1 = 2026-09-11, day 2 = 2026-09-14, day 3 = 2026-09-15, day 4 = 2026-09-16, day 5 = 2026-09-17. The model's exit rules (source B Bonde, P this project, T a third party's test): [B] when same or next day, the price reaches the sell-half level (+8% from the planned entry): sell half and move the stop to 25-50 cents under that day's high. [B] when any single day closes at or above the abnormal-close level (+10%): take at least partial profit and move the stop up to protect the rest. [B] when it opens at or above the gap-exit level (+20%) after entry: sell at the open (or pre-market). [B] when the close of day 1: the stop rises to the entry day's low if that is above the stop. [B] when day 3 close: sell at least half at the close. [B] when day 3 closes at or below the planned entry: exit: no follow-through. [P] when from the close of day 3: raise the stop to each day's low (it never moves down). [B] when day 5 close: exit the remainder into strength. [B] when the protective stop at the stop is a stop-market order, live intraday from the moment the buy fills: if it is somehow not filled, exit on any close below it. [T] when day 2 is green: do not move the stop to break-even before day 5 just because it is green (theStrat Lab EP9M backtest: the win rate collapses from 29.8% to 7.25%; delaying to day 5 restores it); the +8% raise above is a different rule.

Page for any ticker here: https://spicychicken59.github.io/SpicyStock/#/explore/bursts/<TICKER> (setting-up names: the same with `setting-up` in place of `bursts`). Near-volume band: 0 of the discovered bursts have a volume within 0.05 of the previous session's (the burst's volume is within this fraction of the previous session's, so its higher-volume check can flip on the provider's later corrections; the bound is this project's own label, not a rule).

### 6a. In detail (4 of 4 listed: every ticket and reviewed name, then the first 0 others)

### AAPL · rank 1 · A+ 10.00 · TICKET (order and schedule in section 5)

- Bar: close $124.21 (6.00% from $117.18), open $118.96, high $124.49, low $118.35; volume 3,000,000 (5.00x the prior session, 2.96x its 50-session average), dollar volume $372.6M; 5.2% over its 20-session average; route both (burst_route).
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-0.17 · **L+** er=1 r2=1 leg_sessions=16 leg_gain_pct=20.5 · **Y+** breakouts_in_move=0 sessions_since_move_start=33 gain_since_move_start_pct=24.2 · **N+** prior_day_pct=-0.17 prior_range_pct=0.8 negative=yes narrow=yes median_range_pct=1 · **C+** base_sessions=17 breakdowns=0 bursts_in_base=0 giveback=0.19 tightness=0.64 base_volume_vs_leg=0.41 base_volume_vs_avg=0.59 · **H+** close_pos=0.95 close_above_open=yes · **RE+** vs_prior_5=4.9 vs_prior_10=4.9 bar_range_pct=4.9 · **VOL+** volume_vs_prior=5 volume_vs_avg50=2.96 volume_rank_60=1 cv_required=no. Base 2026-08-17 to 2026-09-09, $116.83 to $121.09; extension: close 5.2% vs its 20-SMA, 5.7% over 20 sessions.
- Chart reader: accepted, A+ 9.3 (opportunity).
  - Reader's reason (commentary): A clean fifteen-session leg into a sixteen-session base that gave back under a quarter of the move, a negative narrow day, then a burst that closed at the high on three times the volume.
  - Reader's main risk (commentary): A gap over the ceiling at the open leaves no stop the bar supports.
  - Reader's entry note (not the ticket): Skip it if the first print is above the ceiling; a print under the skip line says the burst is failing.
- Later gates: GREEN band pass, YELLOW band pass, veto pass, admission pass, reader `accepted`; all of them under GREEN yes, under YELLOW yes.

### AMD · rank 2 · A+ 10.00 · reviewed · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $123.27 (5.20% from $117.18), open $123.12, high $123.28, low $123.10; volume 2,600,000 (4.33x the prior session, 2.49x its 50-session average), dollar volume $320.5M; 4.9% over its 20-session average; route burst (burst_route).
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-0.17 · **L+** er=1 r2=1 leg_sessions=16 leg_gain_pct=20.5 · **Y+** breakouts_in_move=0 sessions_since_move_start=29 gain_since_move_start_pct=23.3 · **N** prior_day_pct=-0.17 prior_range_pct=0.3 negative=yes narrow=yes median_range_pct=0.3 · **C+** base_sessions=13 breakdowns=0 bursts_in_base=0 giveback=0.18 tightness=0.27 base_volume_vs_leg=0.41 base_volume_vs_avg=0.57 · **H+** close_pos=0.94 close_above_open=yes · **REx** vs_prior_5=0.33 vs_prior_10=0.33 bar_range_pct=0.1 · **VOL+** volume_vs_prior=4.33 volume_vs_avg50=2.49 volume_rank_60=1 cv_required=no. Base 2026-08-21 to 2026-09-09, $117.12 to $121.09; extension: close 4.9% vs its 20-SMA, 10.2% over 20 sessions.
- Chart reader: accepted, A+ 9.3 (opportunity).
  - Reader's reason (commentary): A clean fifteen-session leg into a sixteen-session base that gave back under a quarter of the move, a negative narrow day, then a burst that closed at the high on three times the volume.
  - Reader's main risk (commentary): A gap over the ceiling at the open leaves no stop the bar supports.
  - Reader's entry note (not the ticket): Skip it if the first print is above the ceiling; a print under the skip line says the burst is failing.
- Later gates: GREEN band pass, YELLOW band pass, veto pass, admission pass, reader `accepted`; all of them under GREEN yes, under YELLOW yes.
- research levels (record; no order is offered at them): trigger $123.39; limit $128.20; stop $123.10 (burst_low, 3.98% under the limit); day-2 line $128.20; skip if it opens under $120.80; sell-half $134.46; risk a share at the limit $5.10; model size 4 shares, $512.80 cost, $20.40 risk (multiplier 0.50); at the YELLOW size 2 shares, $256.40.
- No ticket: slot cap (stage `allocation_slot`).

### NVDA · rank 3 · A+ 10.00 · reviewed · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $126.88 (7.40% from $118.14), open $123.46, high $127.57, low $123.00; volume 3,400,000 (5.67x the prior session, 3.44x its 50-session average), dollar volume $431.4M; 6.8% over its 20-session average; route both (burst_route).
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-0.17 · **L+** er=1 r2=1 leg_sessions=15 leg_gain_pct=21.5 · **Y+** breakouts_in_move=0 sessions_since_move_start=34 gain_since_move_start_pct=26.9 · **N** prior_day_pct=-0.17 prior_range_pct=0.3 negative=yes narrow=yes median_range_pct=0.3 · **C+** base_sessions=19 breakdowns=0 bursts_in_base=0 giveback=0.18 tightness=0.24 base_volume_vs_leg=0.41 base_volume_vs_avg=0.61 · **H** close_pos=0.85 close_above_open=yes · **RE+** vs_prior_5=12 vs_prior_10=12 bar_range_pct=3.6 · **VOL+** volume_vs_prior=5.67 volume_vs_avg50=3.44 volume_rank_60=1 cv_required=no. Base 2026-08-13 to 2026-09-09, $118.08 to $122.09; extension: close 6.8% vs its 20-SMA, 4.4% over 20 sessions.
- Chart reader: accepted, A+ 9.3 (opportunity).
  - Reader's reason (commentary): A clean fifteen-session leg into a sixteen-session base that gave back under a quarter of the move, a negative narrow day, then a burst that closed at the high on three times the volume.
  - Reader's main risk (commentary): A gap over the ceiling at the open leaves no stop the bar supports.
  - Reader's entry note (not the ticket): Skip it if the first print is above the ceiling; a print under the skip line says the burst is failing.
- Later gates: GREEN band pass, YELLOW band pass, veto pass, admission pass, reader `accepted`; all of them under GREEN yes, under YELLOW yes.
- research levels (record; no order is offered at them): trigger $127.01; limit $128.12; stop $123.00 (burst_low, 4.00% under the limit); day-2 line $131.96; skip if it opens under $124.34; sell-half $138.37; risk a share at the limit $5.12; model size 4 shares, $512.48 cost, $20.48 risk (multiplier 0.50); at the YELLOW size 2 shares, $256.24.
- No ticket: slot cap (stage `allocation_slot`).

### TSLA · rank 4 · A+ 10.00 · reviewed · RESEARCH ONLY: no SpicyStock ticket

- Bar: close $124.21 (6.00% from $117.18), open $114.71, high $124.77, low $113.59; volume 3,000,000 (5.00x the prior session, 2.96x its 50-session average), dollar volume $372.6M; 5.2% over its 20-session average; route both (burst_route).
- Checks: **2+** up_run=0 up_closes=0 prior_day_pct=-0.17 · **L+** er=1 r2=1 leg_sessions=16 leg_gain_pct=20.5 · **Y+** breakouts_in_move=0 sessions_since_move_start=33 gain_since_move_start_pct=24.2 · **N** prior_day_pct=-0.17 prior_range_pct=0.3 negative=yes narrow=yes median_range_pct=0.3 · **C+** base_sessions=17 breakdowns=0 bursts_in_base=0 giveback=0.18 tightness=0.25 base_volume_vs_leg=0.41 base_volume_vs_avg=0.59 · **H+** close_pos=0.95 close_above_open=yes · **RE+** vs_prior_5=30 vs_prior_10=30 bar_range_pct=9 · **VOL+** volume_vs_prior=5 volume_vs_avg50=2.96 volume_rank_60=1 cv_required=no. Base 2026-08-17 to 2026-09-09, $117.12 to $121.09; extension: close 5.2% vs its 20-SMA, 5.7% over 20 sessions.
- Chart reader: accepted, A+ 9.3 (research_ranked); selection blockers: plan_withheld.
  - Reader's reason (commentary): A clean fifteen-session leg into a sixteen-session base that gave back under a quarter of the move, a negative narrow day, then a burst that closed at the high on three times the volume.
  - Reader's main risk (commentary): A gap over the ceiling at the open leaves no stop the bar supports.
  - Reader's entry note (not the ticket): Skip it if the first print is above the ceiling; a print under the skip line says the burst is failing.
- Later gates: GREEN band pass, YELLOW band pass, veto pass, admission pass, reader `accepted`; all of them under GREEN yes, under YELLOW yes.
- research levels (record; no order is offered at them): trigger $124.33; ticket withheld (no_room_above_the_trigger): no limit above the trigger keeps a structural stop inside the stop line; day-2 line $129.18; skip if it opens under $121.73.
- Plan rule refusal: ticket withheld: no limit above the $124.33 buy stop keeps a stop inside his 4% line — the burst day's low $113.59 caps the limit at $118.32, at or under that buy stop; the bar's midpoint $119.18 caps the limit at $124.14, at or under that buy stop; the setup stands, the ticket does not
- No ticket: ticket withheld: stop rule at the limit (stage `geometry`).

### 6b. Compact rows (0 shown; 0 left out of this file; brief.json carries every one)

Every row here is RESEARCH ONLY (no SpicyStock ticket, no chart review). Research levels are derived from the recorded bar by the record's plan rules: `limit` is the highest fill the plan permits; stop basis L is the burst day's low, M the bar's midpoint; the day-2 line (too extended to enter) is the trigger plus the archived entry_above_pct and the skip-under line the trigger minus entry_below_pct (both exact in brief.json); `shares` is the model size under tonight's regime multiplier, then the same plan at full size; `refused` means the plan rule refused it; `*` after the volume ratio marks the near-volume band. 

## 7. Research tail (3 names)

Every other reaction candidate: RESEARCH ONLY, no SpicyStock ticket and no levels. Tickers in the record's rank order, grouped by the one reason; a ticker whose final grade differs from its mechanical grade shows both.

- not admitted: dollar_no_expansion (1): MSFT
- mechanical grade B, below the trade band (2): PLUG, DLLR

## 8. Setting up (anticipation): 1 listed, 0 also quiet

Of 10 momentum names, 4 quiet, 1 pass the coil checks. The record's own sentence over its list (the model's rule, not an instruction to the reader): "Buy only if it clears its trigger in the first 30 minutes on volume already above yesterday's pace; an open more than 2% above the close is gapped and needs a catalyst check before you buy."

### COIL · listed 1 · RESEARCH ONLY: no SpicyStock ticket

- Measured: close $110.00 (0.00% today); setups TI65; compress 0.33, tight days 10, quiet days 7, volume ratio 0.61, ADR 2.5%, extension 1.03; box $109.50 to $110.50 over 5 sessions (2026-09-03 to 2026-09-10).
- research levels (record; no order is offered at them): trigger $110.61; limit $111.72; stop $109.50 (lowest low of the last 3 sessions, 1.99% under the limit); gap check above $112.20; sell-half $119.46; risk a share at the limit $2.22; model size 22 shares, $2,457.84 cost, $48.84 risk (multiplier 1.00); at the YELLOW size 11 shares, $1,228.92.
- No ticket: the 4-slot model cap: 3 open model plans and AAPL take the rest; take COIL only if a plan above is not held or stops out (stage `allocation_slot`).
- Open-entry note (not the ticket): MOO/OPG at the open only for the top 2 names on the list, and only if it opens within +2% of $110.00
- Event registry: not_in_registry.

## 9. Open model plans (3)

Open MODEL plans walked on daily (and retained minute) bars; not holdings.

- **VRT** (burst, picked 2026-09-03, green): status `sell_into_strength`, day 4; trigger $180.00, limit $183.85, stop $198.05; 3 shares (1 remaining); last close $198.00 on 2026-09-10. The record's own sentence for its model plan, not an instruction to the reader: "Day 4: closed at $198.00 (+10.0%); 2 of 3 VRT sold, sell the remaining 1 into strength by day 5 with the stop at $198.05."
- **SMCI** (burst, picked 2026-09-04, green): status `uncertain`, uncertainty `trigger_timing`, day 3; trigger $24.56, limit $25.32, stop $23.58; 24 shares (24 remaining); last close $24.71 on 2026-09-10. The record's own sentence for its model plan, not an instruction to the reader: "Day 1 (2026-09-08): opened at $24.44, under the $24.56 trigger; the day reached it (high $24.81) at a time the bar cannot give, and the plan's entry is the first 30 minutes. The model books no fill. If you took this plan: the sell stop is $23.58; sell at least half by day 3's close and be out by day 5's close."
- **NBIS** (burst, picked 2026-09-08, green): status `hold`, day 2; trigger $25.52, limit $26.25, stop $25.34; 23 shares (23 remaining); last close $25.75 on 2026-09-10. The record's own sentence for its model plan, not an instruction to the reader: "Day 2: hold 23 NBIS with the stop at $25.34 (closed $25.75, +0.9%)."

## 10. Model record

- Scorecard: 48 plans in 60 sessions (2026-06-15 to 2026-09-10): 20 settled (5 wins, 15 losses, 0 even), 2 open, 1 pending, 12 uncertain, 13 not filled, 0 unmeasured; sum of R -1.75.
- Readable as a rate: **yes** (needs 20 settled); win rate 0.25, average R -0.09, median R -0.15. These are model plans walked on bars, not trades, and no edge is established.
- How it is counted: from bars alone, a model and not a brokerage record: a daily bar books a fill only at the next open at or over the trigger and at or under the limit; a day that reaches the trigger after the open is read again from that session's retained minute bars, which book a fill in the first 30 minutes at the trigger (or the crossing minute's open over it), none after it, and leave a crossing minute that cannot order the fill against the limit or the stop uncertain; without those minutes such a day, whether or not its low also reached the stop, and an open past the limit or under the skip line that could still have filled are uncertain, counted here and in no rate; a fill at the open whose day then reaches the stop is booked at exactly the stop; the published stop is one R on the whole position, every sale weighted by the whole shares it sold; with complete bars, settled by day 5
- Model-record block: not computed (computed only inside an evening run, from that run's fetched bars).
- Pick ledger (picks.json): 48 picks over 25 distinct tickers; repeated: NBIS x3, SMCI x3, ANET x2, CRDO x2, DELL x2, ELF x2, FIX x2, GLW x2, HOOD x2, IONQ x2, JBL x2, KTOS x2, LITE x2, MU x2, ONTO x2, PLTR x2, QTWO x2, RKLB x2, TOST x2, UBER x2, VRT x2; by kind burst 48; by regime at the pick green 48; picks in the scorecard window 48 against 48 plans counted. A pick is one published model ticket; the same stock listed on several nights is several picks, and each counts as its own plan in the scorecard. Picks made under different archived accounts are sized differently; a pick carries its shares, not the account it was sized for.

| picked | ticker | kind | regime | shares | trigger | limit | stop |
|---|---|---|---|---|---|---|---|
| 2026-09-10 | AAPL | burst | green | 4 | 124.33 | 126.47 | 121.42 |
| 2026-09-08 | NBIS | burst | green | 23 | 25.45 | 26.25 | 24.43 |
| 2026-09-04 | SMCI | burst | green | 24 | 24.56 | 25.32 | 23.58 |
| 2026-09-03 | VRT | burst | green | 3 | 180.00 | 183.85 | 172.80 |
| 2026-09-01 | ANET | burst | green | 20 | 29.66 | 30.61 | 28.47 |
| 2026-08-31 | CRDO | burst | green | 20 | 30.29 | 31.17 | 29.08 |
| 2026-08-28 | DELL | burst | green | 21 | 27.72 | 28.67 | 26.61 |
| 2026-08-27 | ELF | burst | green | 26 | 23.29 | 24.10 | 22.36 |
| 2026-08-26 | FIX | burst | green | 24 | 24.70 | 25.54 | 23.71 |
| 2026-08-25 | GLW | burst | green | 21 | 28.55 | 29.50 | 27.41 |
| 2026-08-24 | HOOD | burst | green | 23 | 26.03 | 26.90 | 24.99 |
| 2026-08-21 | IONQ | burst | green | 24 | 25.38 | 26.19 | 24.36 |
| 2026-08-20 | JBL | burst | green | 21 | 27.76 | 28.56 | 26.65 |
| 2026-08-19 | KTOS | burst | green | 25 | 24.17 | 24.78 | 23.20 |
| 2026-08-18 | LITE | burst | green | 26 | 22.47 | 23.28 | 21.57 |
| 2026-08-17 | MU | burst | green | 22 | 27.03 | 27.95 | 25.95 |
| 2026-08-14 | NBIS | burst | green | 23 | 25.37 | 26.30 | 24.36 |
| 2026-08-13 | ONTO | burst | green | 29 | 20.78 | 21.56 | 19.95 |
| 2026-08-12 | PLTR | burst | green | 24 | 24.69 | 25.58 | 23.70 |
| 2026-08-11 | QTWO | burst | green | 24 | 25.06 | 25.75 | 24.06 |
| 2026-08-10 | RKLB | burst | green | 20 | 29.80 | 30.86 | 28.61 |
| 2026-08-07 | SMCI | burst | green | 27 | 21.88 | 22.70 | 21.00 |
| 2026-08-06 | TOST | burst | green | 26 | 22.83 | 23.59 | 21.92 |
| 2026-08-05 | UBER | burst | green | 21 | 28.35 | 29.35 | 27.22 |
| 2026-08-04 | VRT | burst | green | 3 | 173.73 | 177.08 | 165.58 |
| 2026-08-03 | WDC | burst | green | 28 | 21.63 | 22.39 | 20.76 |
| 2026-07-31 | XPEV | burst | green | 13 | 44.43 | 46.03 | 42.65 |
| 2026-07-30 | ZS | burst | green | 21 | 28.70 | 29.64 | 27.55 |
| 2026-07-29 | ANET | burst | green | 20 | 29.14 | 30.07 | 27.97 |
| 2026-07-28 | CRDO | burst | green | 20 | 30.44 | 31.44 | 29.22 |
| 2026-07-27 | DELL | burst | green | 22 | 27.40 | 28.36 | 26.30 |
| 2026-07-24 | ELF | burst | green | 27 | 21.80 | 22.62 | 20.93 |
| 2026-07-23 | FIX | burst | green | 22 | 26.98 | 27.93 | 25.90 |
| 2026-07-22 | GLW | burst | green | 21 | 28.18 | 29.12 | 27.05 |
| 2026-07-21 | HOOD | burst | green | 24 | 25.34 | 26.12 | 24.33 |
| 2026-07-20 | IONQ | burst | green | 23 | 25.36 | 26.28 | 24.35 |
| 2026-07-17 | JBL | burst | green | 21 | 28.73 | 29.72 | 27.58 |
| 2026-07-16 | KTOS | burst | green | 24 | 24.87 | 25.69 | 23.88 |
| 2026-07-15 | LITE | burst | green | 28 | 21.68 | 22.48 | 20.81 |
| 2026-07-14 | MU | burst | green | 22 | 27.25 | 28.13 | 26.16 |

8 older picks left out (the newest 40 retained picks by pick date; picks.json carries every one).

## 11. Event registry and coverage

- Event registry (manual; known cash acquisitions only): 7 entries, last reviewed 2026-11-19, 70 days after the measured session 2026-09-10: the archived registry is newer than the session it is read against. None of its 7 unresolved entries is past its review date (next due 2026-10-15). None of the 8 listed rows (7 bursts, 1 setting up, 0 also quiet) is in the registry. A stock that is not in the registry has not been cleared: SpicyStock reads no company news, and its earnings and SEC checks ran for 1 of the 8 listed names (they run for tickets only).
- Entries: MG (cash_acquisition, announced 2026-09-18, review due 2026-11-25); PRTH (cash_acquisition, announced 2026-09-21, review due 2026-12-17); ARX (cash_acquisition, announced 2026-08-13, review due 2026-12-17); BWIN (cash_acquisition, announced 2026-09-14, review due 2026-12-17); ACVA (cash_acquisition, announced 2026-09-10, review due 2026-10-15); ZIM (cash_acquisition, announced 2026-02-16, review due 2026-12-02); CCC (cash_acquisition, announced 2026-10-15, review due 2026-12-17).
- Status words: `known_event` = in the registry and blocked for a SpicyStock ticket; its manual review is current; `review_required` = in the registry and blocked for a SpicyStock ticket; its manual review is overdue; `not_in_registry` = not in the registry: NOT a clearance, nothing was checked.
- Earnings and 8-K check: status `checked`; 1 ticket rows; 7 of 8 listed names had no check at all.
- Not checked by SpicyStock: company news and press releases, announced earnings dates, offerings and shelf takedowns, FDA and trial dates, halts outside the morning check, delisting notices beyond 8-K item 3.01 on tickets, index changes, lockup expiries, ex-dividend dates.

## 12. Rules

- Rules digest `583191ddb160`; without the universe membership identity `6f80540f06ea` (membership identity `1b97e33400ee217a`): the record's digest nests the universe membership identity, so it moves on any night the selection's membership moves; `digest_without_membership` is the same digest with that identity removed, and moves only when an archived rule changes.
- pipeline: trade_grades ["A+", "A"], yellow_grades ["A+"], max_reads 12, reader_policy "accepted_required_v1", reader_refusal_fraction 0.25, reader_refusal_min 1, stale_tolerance_fraction 0.01, stale_sessions_max 5, min_coverage_fraction 0.5
- plan: entry_below_pct 2.0, entry_above_pct 4.0, skip_gap_pct 8.0, entry_window_minutes 30, assumed_slippage_pct 1.0, limit_rule "stop_constrained", sizing_basis "order_limit", max_stop_pct 4.0, ideal_stop_pct 2.0, stop_risk_multiplier 0.5, gain_ceiling_pct 15.0, extension_hazard_pct 20.0, hazard_multiplier 0.5, sell_half_pct 8.0, abnormal_day_pct 10.0, gap_exit_pct 20.0, sell_half_day 3, no_progress_day 3, trail_from_day 3, final_exit_day 5, allocation_policy "combined_stages_reserved_principal_v1"
- admission: version 1, policy "burst_route_or_dollar_expansion_v1"
- grading: reader_request_version 3
- record: scorecard_min_plans 20, scorecard_sessions 60

## 13. Bounds

- brief.json: 4 candidates in detail, 0 compact, 0 moved to the tail for size. Tickets and reviewed names are always detailed; of the rest, in the stated order, the largest multiple of 4 (or all) is detailed that keeps brief.json within 250000 bytes, and the others are compact rows; only if none can be detailed are compact rows cut, to the largest multiple of 10 that fits, the rest moving to the research tail.
- This file: 4 in detail, 0 compact rows, 0 compact rows left out, 0 research-tail names not named; reviewed names in their short form: no; model-record tables printed: yes. Rule: tickets and reviewed names always in detail; then, to stay within 80000 bytes, the model-record tables are given up first, then the other names' detail (largest multiple of 2 that fits), then tail names (multiple of 50), then the reviewed names' check measurements and all but a cut reason of their reader sentences (the short form), then compact rows (multiple of 5); brief.json carries what this file leaves out.
- Research tail: 3 named, 0 left out (the first 4000: the admitted trade-band names moved out for size, then the rest by the record's rank order). Open plans left out: 0. Stale names left out: 0. The evening run's model-record block is carried whole when its canonical encoding is within 60000 bytes and the brief still fits with it; past that bound it is carried reduced (each plan row keeps its identity, result and account; the setups table is left out), and not at all if that does not fit either; brief.md prints its sentences and, while they fit, the first 30 rows and 12 columns of each of its tables. A copied sentence over 900 characters is cut and ends with an ellipsis.

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
