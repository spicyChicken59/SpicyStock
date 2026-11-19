# The rule sheet: every rule the evening run applies, in order

This is the corrected strategy page. It says what the code does, in the order
`pipeline.run_evening()` does it, so that a reader or an agent with no other
context can apply each rule. It is a description of the model, not advice:
SpicyStock places no order, reads no account and knows no position.

`knowledge/method.md` says whose number each rule is in more words;
`knowledge/strategy.md` is the rulebook the chart reader is given. Where this
sheet and the code disagree, the code is right and this sheet is wrong.

This sheet holds the standing rules. The numbers of one night (the thresholds
as scaled that night, the five market rules as they were evaluated, each
candidate's gates, the model's record so far) are in that night's record and in
the daily brief published beside it (brief.md and brief.json), not here.

## How to read this sheet

- A constant is written `NAME`, and `NAME` = value where it carries a number
  or a word. The module is the one its section heading names; a constant of
  another module is written `module.NAME`. `tests/test_rule_sheet.py` holds
  every constant named here to its module and every value printed beside one
  to the constant, and refuses a rule sentence that carries a number with no
  constant beside it. A night's record archives the same numbers under
  `rules`, and a record made under different numbers keeps its own.
- A function is written `name()`.
- A line that starts with "Example" is a dated illustration. Its numbers are
  facts about one day and are not rules.
- "Session" means a session of the New York Stock Exchange calendar. The
  "signal session" is the day whose finished bar is scanned. "Day one" is the
  next session, the entry day; later days count on from it.
- "R" is the distance from the model's fill to the stop the ticket published,
  on the whole position. A result of minus one R lost that distance.
- "Range" of a bar is its high minus its low, as a percentage of its close.
  "Close position" is where the close sits in the bar: zero at the low, one at
  the high.

## What is Bonde's and what is this project's

Pradeep Bonde's momentum burst is the idea this project implements. Much of
what the run does is this project's own choice. In short:

| Part | Whose it is |
|---|---|
| Entering the next session | His main thesis enters on the burst day itself with the stop at that day's low. Entering the next session after an end-of-day scan is a route he also describes (PRIMARY). Using only that route, the buy stop at the burst close, the skip lines and the limit set from the stop are this project's (P, DERIVED). |
| The stop before day one closes | His stop is the entry day's low. The run cannot know that low when it writes the ticket, so it uses the burst day's low, else the burst bar's midpoint, as a stand-in (P). His own stop replaces it at the close of day one when it is higher. |
| The checklist's weights and bands | The letters and what each asks are his. He publishes no weights, no pass count and no grade bands: the weights, the score, the bands and the rule that two letters must pass outright are this project's (DERIVED). |
| The admission gate | This project's, the owner's decision of 4 November 2026 (P). The dollar scan is his; refusing a plan to a name only the dollar scan found, unless its day also expanded in range and volume, is not. |
| The chart reader | This project's (DERIVED, P). An AI model reads a chart and may lower a grade. Which names it reads, what it may cite and the rule that a burst ticket needs an accepted review are implementation choices. |
| The market light's thresholds | The counts and the readings of them are his, as a field guide quotes them (B*, SECONDARY). Scaling the count thresholds to the stocks measured that night, the two red ratio rules, firing the alarm on a single day, the sizes and the yellow grade band are this project's (P, DERIVED). |
| The exits | The exit ladder is his (B*). The trail from the close of day three is a reading of his words (P). The caution against an early break-even stop comes from a third party's backtest of a different setup (SECONDARY) and has not been measured on bursts. |

> Example (20 sessions, 21 Oct to 17 Nov 2026, newest record of each): of 1,604 mechanical A and A+ grades, 1,108 came through the dollar scan alone; 990 of those lacked the range-expansion, higher-volume day the admission gate asks for.

> Example (48 sessions, 11 Sep to 17 Nov 2026, newest record of each): 35 nights were RED, 13 YELLOW and none GREEN.

## Provenance classes

| Class | Meaning |
|---|---|
| PRIMARY | Bonde's own dated post, its text inspected (`knowledge/reaction-discovery.md`, `knowledge/consolidation-quality.md`, the operating contract of 28 September 2026). |
| LATER BONDE | A later dated statement of his, also inspected. |
| B* | Marked as Bonde's in `knowledge/method.md` or in a module comment, but quoted through a research archive, bootcamp notes and search snippets, and never re-inspected against his text. |
| V | His video of 2018, from one machine transcription. |
| SECONDARY | A field guide, a community port or a third party's study. |
| DERIVED | This project's operational reading of a concept he states in words. |
| P | A provisional implementation choice with no source number behind it. |
| R | A regulation or a broker's rule. |

## 0. When (`src/delivery.py`, `src/timing.py`, `src/plan.py`)

| Rule | Class |
|---|---|
| The run reads finished daily bars after the close. It is scheduled for `EVENING_PRIMARY_ET` = 18:16 New York time, with a retry at `EVENING_RETRY_ET` = 20:16. A late run may still publish a missed session until the next session opens (`RECOVERY_NEXT_OPEN` = "next_session_open"). | P |
| Every plan is for the next session after the signal session. The entry window is the first `ENTRY_WINDOW_MINUTES` = 30 minutes after the open at `REGULAR_OPEN_ET` = 09:30 New York time. The page asks for orders to be ready by `PREPARE_BEFORE_ET` = 09:28. | B* for the window; P for the rest |
| The run enters on the session after the burst, never on the burst day. | PRIMARY for the route (his post of 2015-11-18, as the operating contract of 28 September 2026 classes it); DERIVED for selecting it and for the ticket |

## 1. Universe (`src/universe.py`)

| Rule | Class |
|---|---|
| A row of the Nasdaq stock directory is a candidate only when its name reads as common stock. Depositary shares, preferred shares, warrants, rights, units, notes, funds, shares of beneficial interest, blank-check companies and rows with no sector or industry are refused (`classify()`). A symbol on the hand-kept seed list `data/symbols.txt` is always kept. | P |
| `BIOTECH_FLAG` = "biotech" (any Health Care row) and `FOREIGN_FLAG` = "foreign" are warnings on a stock. They never exclude it. | P |
| A stock is measured only when its session close, rounded to the cent, is at least `MIN_PRICE` = 3.0 dollars. Seed names are exempt. | P |
| At most `MAX_DISCOVERY` = 8,000 stocks are selected. | P |

## 2. Bars and coverage (`src/pipeline.py`)

| Rule | Class |
|---|---|
| Daily bars are split-adjusted and cover `LOOKBACK_DAYS` = 260 sessions. | B* for the longest lookback his scans need; P for the rest |
| A stock is measured only with a bar on the signal session and on the session before it. If fewer than `MIN_COVERAGE_FRACTION` = 0.5 of the intended stocks have a usable bar, nothing is published. | P |
| Status only, never a gate: a night is not called degraded for a tail of stocks whose bars end early, when that tail is at most `STALE_TOLERANCE_FRACTION` = 0.01 of the intended stocks and each ends within `STALE_SESSIONS_MAX` = 5 sessions before the signal session. A stale stock is never measured. | P |

## 3. Market light (`src/breadth.py`, `src/pipeline.py`)

The light is read first and gates everything after it. It is this project's
gate for its own model tickets. The record does not establish that it improves
outcomes.

Counts, each over the stocks measured that night (the count is the night's
"universe", N):

| Rule | Class |
|---|---|
| Up four percent: the close is at least `BURST_PCT` = 4.0 percent over the previous close, on volume of at least `MIN_VOLUME` = 100,000 shares and more than the previous session's. Down four percent is the mirror, with the same two volume tests. | B* |
| Up or down a quarter: the close is `QUARTER_MOVE_PCT` = 25.0 percent or more over the lowest close, or under the highest close, of the last `QUARTER_SESSIONS` = 65 sessions. | B* |
| Up or down a month: the close is `MONTH_MOVE_PCT` = 25.0 percent, or `MONTH_BIG_MOVE_PCT` = 50.0 percent, or more away from the close `MONTH_SESSIONS` = 20 sessions earlier, when that earlier close was at least `MIN_MONTH_PRICE` = 5.0 dollars. | B* |
| The quarter and month counts need liquidity: the average close times the average volume over those `MONTH_SESSIONS` = 20 sessions is at least `MIN_DOLLAR_VOLUME_20` = 250,000. | B* |
| Counted and shown, and part of no rule: stocks `MOVE_13_PCT` = 13.0 percent or more off their lowest or highest close of the last `SESSIONS_34` = 34 sessions, and the share of stocks closing above their `MA_SESSIONS` = 40 session average. | B* |
| Two ratios: the sum of the up-four-percent counts over the sum of the down-four-percent counts across `RATIO_SHORT_SESSIONS` = 5 and across `RATIO_LONG_SESSIONS` = 10 sessions, each rounded once to `RATIO_DECIMALS` = 2 places and compared as rounded. A ratio with no down count is undefined and fires no rule. | B* for the ratios; P for the rounding |
| A count threshold is his reading over about `REFERENCE_UNIVERSE` = 6,500 stocks, so it is scaled before it is compared: threshold times N divided by the reference, rounded once to `THRESHOLD_DECIMALS` = 1 place (`scaled_threshold()`). Ratios are never scaled. | P |

The verdict comes from five rules:

| Verdict | Fires when | Class |
|---|---|---|
| RED | The down-four-percent count today is at or over the scaled `DOWN4_ALARM` = 700. | SECONDARY for the reading ("a series of days" with that many); DERIVED for firing on one day |
| RED | The longer ratio is under `RED_RATIO_10D` = 1.0. | P |
| RED | The shorter ratio is under `RED_RATIO_5D` = 0.5 and today's down count is larger than today's up count. | P |
| YELLOW | The longer ratio is under `YELLOW_RATIO_10D` = 2.0. | B*, SECONDARY for the reading |
| YELLOW | The count of stocks up the larger monthly amount is over the scaled `UP50_MONTH_HOT` = 20. | B*, SECONDARY for the reading |
| GREEN | None of the five rules fires. A longer ratio at or over the yellow line is not enough by itself. | |

Any red rule makes the night RED, whatever the yellow rules say. What the
verdict does:

| Rule | Class |
|---|---|
| The verdict multiplies every new position's risk: `SIZE_MULTIPLIER` = {"green": 1.0, "yellow": 0.5, "red": 0.0}. | P |
| GREEN admits bursts graded `pipeline.TRADE_GRADES` = ("A+", "A"). YELLOW admits only `pipeline.YELLOW_GRADES` = ("A+",). RED admits none: no burst plan is written, and a setting-up plan keeps its levels with no shares ("no new longs"). | B* for wanting only the best setups; P for the bands |
| Informational only, never part of the verdict: fewer stocks down a quarter than the scaled `DOWN25_QUARTER_OVERSOLD` = 200 is an oversold flag. | SECONDARY (not yet checked against his own words) |

> Example (17 Nov 2026 record, N = 3,513): 700 scales to 378.3, 20 to 10.8 and 200 to 108.1. That night was RED on the longer ratio (0.79) and on the shorter ratio (0.42 with 210 down against 61 up).

## 4. Discovery (`src/scans.py`)

Two scans find a reaction candidate. Being found is not being admitted
(section 6) and is not a grade (section 5).

| Rule | Class |
|---|---|
| Burst scan: the close is at least `BURST_RATIO` = 1.04 times the previous close, on more volume than the previous session and at least `MIN_VOLUME` = 100,000 shares. | PRIMARY (2015-05-21) |
| Dollar scan: the close is at least `DOLLAR_MOVE` = 0.90 dollars over the same session's open, on more than `MIN_VOLUME` = 100,000 shares. It asks nothing of the day's gain, its range, the previous session's volume or the price. | PRIMARY (2017-07-13) |
| Each candidate records its route: `burst`, `dollar` or `both`. | P |
| Setting-up pool: the day's change is within `QUIET_PCT` = 1.0 percent either way, and at least one of three momentum tests holds. Double Trouble: the close is at least `DT_RATIO` = 1.8 times the lowest low of the last `LOW_LOOKBACK` = 252 sessions. Trend intensity: the average close of the last `TI_SHORT_SESSIONS` = 7 sessions is more than `TI65_RATIO` = 1.05 times that of the last `TI_LONG_SESSIONS` = 65. Modified Double Trouble: the close is more than `MDT_RATIO` = 1.19 times the average close of the last `MDT_SESSIONS` = 126 sessions. Each also asks the lowest volume of the prior `PRIOR_VOLUME_SESSIONS` = 3 sessions: at least `MIN_VOLUME` = 100,000 shares for Double Trouble, and more than that for the other two. | B* |
| The episodic-pivot scans are computed and decide nothing. | not traded |

## 5. Checklist (`src/quality.py`, `src/grader.py`)

Every reaction candidate is measured. Two spans are located first, both by
this project's reading (DERIVED). The base runs from the session after the
first highest high of the `BASE_SEARCH_SESSIONS` = 40 sessions before the
burst, through the session before the burst. The leg runs from the last lowest
close of the `LEG_SEARCH_SESSIONS` = 60 sessions before the base, to that high.

| Letter | Weight | PASS | A+ standard | Class |
|---|---|---|---|---|
| 2 | `WEIGHT_2` = 1.5 | Counting back from the session before the burst until a down close: at most `MAX_UP_RUN` = 1 day rose more than `UP_DAY_PCT` = 1.0 percent. A smaller rise is flat. | No such day. | B* |
| L | `WEIGHT_L` = 2.0 | The leg's efficiency ratio (net move over the sum of daily moves) is at least `MIN_ER` = 0.40, or the fit of a straight line to its log closes is at least `MIN_R2` = 0.55. A leg shorter than `MIN_LEG_SESSIONS` = 5 sessions is unmeasured. | Both. | B* for the formula; DERIVED for the thresholds |
| Y | `WEIGHT_Y` = 1.5 | At most `MAX_PRIOR_BREAKOUTS` = 1 earlier breakout since the move began. A breakout is a day that closed at least the burst ratio over the previous close, on more volume than the previous session, at a close position of at least `BREAKOUT_MIN_CLOSE_POS` = 0.70. The move begins at the lowest close of the `MOVE_SEARCH_SESSIONS` = 60 sessions before the burst, preferring one under its `MOVE_SMA_SESSIONS` = 50 session average. | None. | B* for the idea; DERIVED for where the move begins |
| N | `WEIGHT_N` = 1.5 | The session before the burst closed down, or its range is under `NARROW_RANGE_PCT` = 2.0 percent. | It closed down and its range is under the median of the `NARROW_NORM_SESSIONS` = 20 sessions before it. | V for the narrow range; DERIVED for the median |
| C | `WEIGHT_C` = 2.0 | The base is `BASE_MIN` = 3 to `BASE_MAX` = 20 sessions long, has at most `MAX_BREAKDOWNS` = 1 breakdown day (a close at or under `scans.BREAKDOWN_RATIO` = 0.96 times the previous close), gave back at most `MAX_GIVEBACK` = 0.34 of the leg, and its average range is at most `MAX_TIGHTNESS` = 1.0 times that of the `TIGHTNESS_NORM_SESSIONS` = 60 sessions before it. A base of `PARTIAL_BASE_MIN` = 2 sessions, or longer than the maximum, that meets the rest is a partial. | No breakdown day and no day up the burst ratio inside the base, giveback at most `A_PLUS_MAX_GIVEBACK` = 0.25, tightness at most `A_PLUS_MAX_TIGHTNESS` = 0.70, and base volume under both the leg's and the average of the `VOLUME_AVG_SESSIONS` = 50 sessions before the burst. | PRIMARY for the length; LATER BONDE for the one down day; DERIVED for the rest |
| H | `WEIGHT_H` = 1.5 | The close is above the open, at a close position of at least `MIN_CLOSE_POS` = 0.80. From `PARTIAL_CLOSE_POS` = 0.70 it is a partial. | At least `A_PLUS_CLOSE_POS` = 0.90. | V; SECONDARY for the partial band |
| RE | none | The burst day's range is at least `MIN_RANGE_EXPANSION` = 1.0 times the largest range of the prior `RE_WINDOW` = 5 sessions. | Also of the prior `RE_WINDOW_LONG` = 10. | B*; P for the ratio |
| VOL | none | Volume is above the previous session's. When the base is longer than `CV_BASE_SESSIONS` = 21 sessions, volume must also be at least `CV_MIN_VOLUME` = 1.5 times the average of the `VOLUME_AVG_SESSIONS` = 50 sessions before the burst. | Its volume ranks in the top `A_PLUS_MAX_VOLUME_RANK` = 3 of the last `VOLUME_RANK_SESSIONS` = 60 sessions. | V for the rank; SECONDARY for the long-base rule |

| Rule | Class |
|---|---|
| Veto `up_days`: `VETO_UP_DAYS` = 3 or more closes in a row that each rose, by any amount, ending the session before the burst. The grade is skip whatever the score. This counts every rising close, where the letter 2 counts only the larger rises. | B*, V; DERIVED for counting a rise of any size |
| Veto `not_linear`: L was measured and failed. The grade is skip. | B* |
| Score: a passed letter earns its weight and a partial earns half. RE and VOL earn nothing. The weights sum to ten. | DERIVED |
| Bands: `grader.GRADE_BANDS` = ((9.0, "A+"), (8.0, "A"), (6.5, "B"), (5.0, "C")), each a floor, with skip below the last. The top band also needs at least `MIN_A_PLUS_LETTERS` = 4 of the eight checks at their A+ standard, and is A without them. | DERIVED |
| The top two bands also need the letters `GRADE_GATE_LETTERS` = ("2", "H") passed outright. A name that scores into them without that is capped at the third band. | DERIVED |

## 6. Admission (`src/admission.py`)

`POLICY` = "burst_route_or_dollar_expansion_v1", the owner's decision of
4 November 2026.

| Rule | Class |
|---|---|
| A candidate the burst scan found (route `burst` or `both`) is admitted. | P |
| A candidate only the dollar scan found (route `dollar`) is admitted only when both RE and VOL of section 5 passed. A check that could not be read is not a pass. | P |
| A candidate that is not admitted keeps its checklist grade as research. It gets no plan, no ticket and no chart read. Admission is never a grade. | P |

## 7. Chart reads (`src/review_selection.py`, `src/pipeline.py`, `src/grader.py`, `src/reader_coverage.py`, `src/reader_authority.py`)

`review_selection.POLICY` = "account_feasible_first_research_v2" chooses which
candidates an AI model reads. `reader_coverage.POLICY` = "accepted_required_v1"
says what a read is needed for.

| Rule | Class |
|---|---|
| At most `pipeline.MAX_READS` = 12 candidates are read a night. | P |
| First come the feasible candidates, ordered by mechanical grade, then by score from the highest, then by ticker. Feasible means: the mechanical grade is in the night's band, there is no veto, the candidate is admitted, no known event blocks it, and a private preview of its ticket is eligible with at least one share. | DERIVED |
| Then at most `RESEARCH_MAX` = 2 research reads go to admitted candidates of mechanical grade A+ or A that are not feasible: `RANKED_RESEARCH` = 1 by rank and the rest by a fixed rotation. A research read cannot produce a ticket by itself. | DERIVED |
| The reader sees a chart and the recorded measurements. It may confirm a grade or lower it and can never raise it (`grader.final_grade()`). | DERIVED |
| A reply that lowers a grade must cite recorded evidence its criterion allows. A reply that does not is refused whole (`reader_authority.validate()`) and is not asked again: the mechanical grade stands and no ticket follows. A request that fails in transit is tried at most `grader.ATTEMPTS` = 2 times. | DERIVED |
| A burst plan needs an accepted review. A candidate that was refused, failed or was never read gets no ticket. | DERIVED |

## 8. Burst plan gates, in order (`src/pipeline.py`)

A reaction candidate gets a plan only when it passes every gate, in this
order (`_make_plans()`):

1. Its final grade is in the band the night's verdict admits (section 3).
2. It has no veto (section 5).
3. It is admitted (section 6).
4. Its chart review was accepted (section 7).
5. The ticket rule can write a ticket (section 9).
6. No known event blocks it (section 11).
7. The allocation has a slot and the cash for it (section 13).

On a RED night every candidate stops at the first gate, so the record says
nothing of the later gates for that night. The admission block on each row
(`bursts[].admission`) and the night's summary (`run.admission`) are still
written, and the daily brief works the later gates out again from each row's
recorded fields.

## 9. Burst ticket (`src/plan.py`)

Written by `burst_plan()` from the signal bar's close, low and high.

| Rule | Class |
|---|---|
| Trigger: a buy stop at the signal close (the plan's `entry_ref`). | P |
| Stop: the signal bar's low, else the midpoint of its high and low (`stop_candidates()`). The first of the two that is under the trigger and leaves a limit above the trigger is used. | B* for the line it is held to; DERIVED for the two stand-ins |
| Limit: the lower of two prices (`burst_limit()`, `LIMIT_RULE` = "stop_constrained"). One is the close plus `ENTRY_ABOVE_PCT` = 4.0 percent. The other is the highest price at which the stop is still within `MAX_STOP_PCT` = 4.0 percent of it, rounded down to the cent. When neither stand-in leaves a limit above the trigger, the ticket is withheld and the setup is kept. | B* for the stop line; DERIVED for the rule (12 Sep 2026) |
| The order can fill only from the trigger up to the limit. Under the trigger it waits and buys nothing. | P |
| Skip line above: an open more than `ENTRY_ABOVE_PCT` = 4.0 percent over the close is not taken (`day2_spent_above`). It is a rule of its own, not the limit: the two prices are the same only when the close plus `ENTRY_ABOVE_PCT` is the lower of the limit's two prices (`limit_basis` = "outer_ceiling"). | P |
| Skip line below: an open more than `ENTRY_BELOW_PCT` = 2.0 percent under the close is the burst failing and is not taken. | P |
| A third printed line, the close plus `SKIP_GAP_PCT` = 8.0 percent, is the level at which he would be selling. | B* |
| Indicative entry: the close plus `ASSUMED_SLIPPAGE_PCT` = 1.0 percent, capped at the limit. Only the targets and the exit levels on the ticket are quoted from it. It is not a fill and not the sizing price. | P |
| Order: a day buy stop-limit with a sell stop-market order at the stop attached to it, good until cancelled (`fidelity_orders()`). The buy is cancelled by hand at the end of the entry window. | P |
| The sell stop rides on the buy as a one-triggers-the-other order (`OTO`). Fidelity's stated rules release such a stop only when the buy fills in full, and take a buy stop only above the current price. A burst's trigger is its last close, so whether Fidelity accepts this ticket before the open is unconfirmed (`knowledge/broker-fidelity.md`). | R |

## 10. Size (`src/plan.py`)

`size()` works at the ticket's limit, the highest fill the ticket allows
(`SIZING_BASIS` = "order_limit").

| Rule | Class |
|---|---|
| Risk budget: equity times the risk percentage, times the verdict's multiplier, times the hazard multiplier, times the stop-risk multiplier. | B* for the formula; P for the multipliers |
| Shares: the budget divided by the distance from the limit to the stop, rounded down to a whole share, and never more than the position cap buys at the limit. No whole share means no order. | B* |
| The account is set per run: `ACCOUNT_EQUITY` (default `DEFAULT_EQUITY` = 10,000 dollars), `RISK_PCT` (default `DEFAULT_RISK_PCT` = 0.5 percent of equity), `MAX_POSITION_PCT` (default `DEFAULT_MAX_POSITION_PCT` = 25 percent of equity in one name) and `MAX_OPEN_POSITIONS` (default `DEFAULT_MAX_OPEN_POSITIONS` = 4 slots). | B* for the risk band (`RISK_PCT_BAND_LOW` = 0.25 to `RISK_PCT_BAND_HIGH` = 1.0 percent); P for the values |
| Stop-risk: when the stop is more than `IDEAL_STOP_PCT` = 2.0 percent and at most `MAX_STOP_PCT` = 4.0 percent under the limit, the budget is multiplied by `STOP_RISK_MULTIPLIER` = 0.5. | B* for the two lines; P for the halving |
| Every burst ticket on a stock at or over the price floor of section 1 takes that halving. Its limit is set from its stop, so its stop always sits between those two lines, close to the wider one. | DERIVED |
| Hazards: a burst-day gain of `GAIN_CEILING_PCT` = 15.0 percent or more, or a close more than `EXTENSION_HAZARD_PCT` = 20.0 percent over its `EXTENSION_SESSIONS` = 20 session average, multiplies the budget by `HAZARD_MULTIPLIER` = 0.5. Both together still multiply it once. A hazard never refuses a ticket. | SECONDARY for the gain; P for the extension |

> Example (production account since the 4 Nov 2026 session: `ACCOUNT_EQUITY` 30,000 and `RISK_PCT` 0.5): the full budget is $150. A burst ticket risks $75 on a GREEN night and $37.50 on a YELLOW night, half of that again with a hazard.

## 11. Events and earnings (`src/event_risk.py`, `src/earnings_risk.py`)

| Rule | Class |
|---|---|
| A stock in the hand-kept registry `knowledge/event-risk.json` loses its order: the plan stays for research and no ticket is offered (`event_risk.apply()`). The registry lists pending cash acquisitions someone found and sourced. It is not a news feed, and a stock that is not in it has not been cleared. | P |
| Each ticket carries an earnings warning and a list of the issuer's recent current reports, read from its regulatory filings (`earnings_risk.collect()`). The warning never withholds, sizes or cuts a ticket. A stock the filings could not be read for is unknown, never clear. | P |

## 12. Setting up, the anticipation list (`src/watchlist.py`, `src/plan.py`)

A separate list with its own ticket. It has no checklist grade, no admission
gate and no chart read. The verdict's multiplier still applies, so a RED night
gives every setting-up plan no shares.

A stock in the setting-up pool of section 4 is listed when all of these hold:

| Rule | Class |
|---|---|
| Tight days: a day is tight when its range is under `TIGHT_FRACTION` = 0.70 of the average range of the `ADR_SESSIONS` = 20 sessions that end the day before today. The last `TTT_SESSIONS` = 3 days are all tight, or at least `MIN_TIGHT` = 3 of the last `TIGHT_LOOKBACK` = 10 are. | B* for the idea; P for the numbers |
| Compression: the average range of the last `COMPRESS_RECENT` = 7 sessions, over that of the `COMPRESS_BASE` = 60 before them, is at most `MAX_COMPRESS` = 0.75 and at least `MIN_COMPRESS` = 0.30. Under the lower bound the price is pinned, as a pending cash takeover pins it, not coiled. | P |
| At most `MAX_BREAKDOWNS` = 1 breakdown day in the last `BREAKDOWN_LOOKBACK` = 10 sessions. | B* for the count; P for the window |
| At most `MAX_UP_RUN` = 2 rising closes in a row ending today. | B* |
| The close is at most `MAX_EXTENSION` = 1.10 times its `EXTENSION_SESSIONS` = 20 session average. | P |
| A box: the longest run of `BOX_MIN` = 3 to `BOX_MAX` = 10 sessions ending today whose highs lie within `BOX_SPREAD_ADRS` = 1.0 times that average range of each other, taken as a share of today's close. | B* for the length; P for the spread |
| Dry volume is measured and decides nothing. | P |
| Only a stock whose trigger (below) is at most `MAX_RISK_PCT` = 4.0 percent above the lowest low of the last `STOP_SESSIONS` = 3 sessions is listed. | B* |
| The list keeps the top `TOP_N` = 5, ranked by three tight days in a row first, then the highest trend-intensity ratio, then the tightest compression. | B* |

The ticket, written by `anticipation_plan()`:

| Rule | Class |
|---|---|
| Trigger: the box high plus the larger of `plan.TRIGGER_CENTS` = 0.02 dollars and `plan.TRIGGER_FRACTION` = 0.001 of the close. | B* for a few cents above; P for the amount |
| Limit: the trigger plus `plan.TRIGGER_LIMIT_PCT` = 1.0 percent. | P |
| Stop: the lowest low of the last `plan.STOP_LOOKBACK_SESSIONS` = 3 sessions. | B* |
| The ticket is withheld when that stop is more than `plan.MAX_STOP_PCT` = 4.0 percent under the limit. The list measures its own line from the trigger, so a listed stock can still have its ticket withheld. | B* for the line; P for measuring it at the limit |
| The stop-risk halving of section 10 applies between the same two lines. There are no hazards on this ticket. | P |
| An open more than `plan.GAP_OK_PCT` = 2.0 percent above the close is a gap that asks for a catalyst check before buying. | B* |

## 13. Allocation (`src/allocation.py`, `src/plan.py`)

`POLICY` = "combined_stages_reserved_principal_v1". One budget covers both
kinds of ticket (`allocation.budget()`, `plan.cash_budget()`).

| Rule | Class |
|---|---|
| Tickets are taken in rank order, bursts first, then the setting-up list. | P |
| A ticket needs a free slot. An unfinished model plan holds a slot and reserves its whole original cost, and a part sale frees nothing. Unfinished means one of `OCCUPIED_STATUSES` = ("hold", "sell_half", "sell_into_strength", "pending", "uncertain", "unmeasured", "unreadable"). | P |
| One ticket per symbol. A symbol an unfinished model plan holds gets no new ticket. | P |
| The tickets' cost at their limits cannot exceed the equity less that reserve. | P |
| A plan that is cut keeps its levels and loses its order. | P |

This is a model allocation over the configured account. It is not a balance,
settled cash or buying power.

## 14. Fill model (`src/record.py`, `src/intraday.py`, `src/plan.py`)

How the record decides whether a published ticket filled (`fill()`,
`replay()`, `intraday.resolve()`). It is a model, not a brokerage record.

| Rule | Class |
|---|---|
| The first day opens at or over the trigger and at or under the limit: filled at that open (`KNOWN_FILL` = "open_inside_zone"). This assumes the buy order was already resting at the broker before the open. | P |
| The first day never reaches the trigger, or opens over the limit and never trades back to it: not filled. | P |
| The first day opens under the trigger and reaches it later: that session's one-minute bars are read (`intraday.POLICY` = "first_window_minute_v1"). The first minute of the first `plan.ENTRY_WINDOW_MINUTES` = 30 minutes whose high reaches the trigger fills at the trigger, or at that minute's open when it opened over the trigger. No such minute means not filled, however far the day went later. | P; B* for the length of the window |
| A crossing minute that cannot be ordered against the limit or the stop is uncertain. So is such a day with no usable minute bars, an open over the limit that later traded back to it, and an open under the lower skip line that later recovered through the trigger. | P |
| Uncertain means no fill and no R. The plan still holds its slot until its window ends. | P |

## 15. Exits (`src/plan.py`)

`follow()` walks a filled plan one session at a time. Every level is measured
from the fill. Within a bar the open is read first, then the low against the
stop, then the high, then the close. The steps are checked in this order each
day, and the first that ends the position ends the walk. The step names are
the ones `EXIT_RULES` prints on every ticket.

| Order | Step | Rule | Class |
|---|---|---|---|
| 1 | | A session after day `FINAL_EXIT_DAY` = 5 finds the plan expired. | B* |
| 2 | `stop` | The open is at or under the stop: out at that open, which can be well under the stop. | P |
| 3 | `gap_20pct` | The open is `GAP_EXIT_PCT` = 20.0 percent or more over the fill: out at the open. | B* |
| 4 | `stop` | The low is at or under the stop: out at the stop price, even when the same bar's high reached a sale level. | P |
| 5 | `sell_half_8pct` | The high is `SELL_HALF_PCT` = 8.0 percent or more over the fill and no half has been sold: sell half, rounded up to whole shares, and raise the stop to `TRAIL_CENTS` = 0.25 dollars under that day's high. The sale is booked at that level, or at the open when the session opened above it. The ticket says "same or next day" and names a range up to `TRAIL_CENTS_MAX` = 0.50 dollars. The model applies the step on any day until the day-three step has sold a half. | B* |
| 6 | `abnormal_10pct` | The close is `ABNORMAL_DAY_PCT` = 10.0 percent or more over the fill: the ticket says take at least part profit. The model books no sale and only raises the stop to `TRAIL_CENTS` = 0.25 dollars under that day's high. | B* |
| 7 | `day3_no_progress` | On day `NO_PROGRESS_DAY` = 3 the close is at or under the fill: out at the close. | B* |
| 8 | `day3_sell_half` | On day `SELL_HALF_DAY` = 3, when no half has been sold: sell half at the close. | B* |
| 9 | `entry_day_low` | At the close of day `ENTRY_DAY` = 1 the stop rises to that day's low when it is higher. This is his own stop taking over from the stand-in. | B* |
| 10 | `trail_after_day3` | From the close of day `TRAIL_FROM_DAY` = 3 the stop rises to each day's low. It never moves down. | P |
| 11 | `day5_exit` | On day `FINAL_EXIT_DAY` = 5: out at the close. | B* |
| 12 | | On a RED night the instruction of a plan still held gains the words of `RED_CLAUSE` (sell into any strength, do not add). The model moves no stop and books no sale for it. | P |

Printed on every ticket and not walked by the model:

| Step | Rule | Class |
|---|---|---|
| `stop` | "If it is somehow not filled, exit on any close below it." | B* |
| `no_breakeven` | "Do not move the stop to break-even before day `NO_BREAKEVEN_BEFORE_DAY` = 5 just because it is green." It comes from a third party's backtest of a different setup, the episodic pivot. Its use on these tickets is this project's and has not been measured on bursts, and his own text of 2015 describes moving to break-even earlier. The steps above can still lift the stop over the fill sooner. | SECONDARY; DERIVED for using it here |

A setting-up plan is walked the same way, with one more rule: a first day
whose high never reaches the trigger ends the plan unfilled.

Targets printed on a ticket, from the indicative entry: `TARGET_LOW_PCT` = 8.0
to `TARGET_HIGH_PCT` = 20.0 percent. A stock under `LOW_PRICE_BAND_USD` = 5.0
dollars is quoted `LOW_PRICE_TARGET_LOW_PCT` = 20.0 to
`LOW_PRICE_TARGET_HIGH_PCT` = 40.0 percent. A stock over
`HIGH_PRICE_BAND_USD` = 40.0 dollars is quoted in dollars,
`HIGH_PRICE_TARGET_LOW_USD` = 5.0 to `HIGH_PRICE_TARGET_HIGH_USD` = 25.0
(B*). A target is a reference level, not a forecast, and no exit step reads it.

## 16. What the model does at a stop (`src/plan.py`, `src/record.py`)

The stop on a ticket is a stop-market order. A real one fills at whatever the
market gives after it is touched. The model does not know that price. It books
one of two prices (`follow()`), and `r_multiple()` turns the sales into R:

| Rule | Class |
|---|---|
| A session that opens at or under the stop is booked out at that open. The loss is then larger than one R. | P |
| A session whose low reaches the stop, after an open above it, is booked out at exactly the stop price. Slippage past the stop inside the day is not modelled. | P |
| So a plan filled at the open and stopped the same day always reads exactly minus one R, however far under the stop the day closed. | P |
| The stop wins inside a bar: a bar that reached both the stop and a sale level is booked as stopped. A daily bar cannot say which came first. | P |
| A stop raised by an exit step can sit above the fill, so a plan can be "stopped" at a gain. A stop raised to just under a day's high can also sit above that day's close, and the next open at or under it is booked out at that open. | P |
| Sales are whole shares, so a position of one share cannot be halved: the half-sale step sells it all. The same bars can therefore give a different R at a different size. | P |
| A first day that opened under the trigger, reached it, and also reached the stop is uncertain unless its one-minute bars can order the two. | P |

The daily brief's model record (its `stops` block) reads every stopped ticket
three ways: `booked`, what the rules above book; `at_close`, the same exit at
that session's close; and `at_low`, the same exit at that session's low, a
worst case for a stop order filled that day. The last two are bounds, not
results, and the close is not a fill estimate.

> Example (the three burst tickets of the 4 Nov 2026 record): each was stopped on day one, 5 Nov 2026, and each is booked at exactly its stop, minus 1.00 R. Each closed under its stop that day. The same exits read about minus 1.70, minus 1.29 and minus 1.67 R at that day's close, and about minus 2.04, minus 1.46 and minus 2.28 R at that day's low. A real stop-market order triggers at the first trade at or under the stop and fills at the next available price, and a daily bar cannot say where that was. These figures are bounds, not results.

## 17. Scorecard (`src/record.py`)

| Rule | Class |
|---|---|
| A plan's result in R is the sum over its sales of shares sold times the gain from the fill, divided by the whole position times the distance from the fill to the published stop (`r_multiple()`). | P |
| Plans picked in the last `SCORECARD_SESSIONS` = 60 sessions are counted. A plan is followed for `OPEN_PLAN_SESSIONS` = 5 sessions. | P; B* for the length of the hold |
| Rates and averages are printed only from `SCORECARD_MIN_PLANS` = 20 settled plans. Under that the scorecard prints counts. | P |
| The benchmark `BENCHMARK` = "SPY" over the same days is one comparison line. | P |
| Each night's re-offer of the same setup is a new plan and is counted again. | P |
| A later run of the same session replaces a plan it issues again (the same session, ticker and kind, `append()`). A plan the later run no longer issues stays in the record and in the scorecard. | P |
