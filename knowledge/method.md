# The method SpicyStock implements, and where each number comes from

Pradeep Bonde's (Stockbee) Momentum Burst method, as the field guide
"The Stockbee A-Quality Setup & Momentum-Burst Method" states it and as the
rebuild's research lenses sourced it. Every number the code applies is a named
constant in the module that reads it; this file says whose number it is.
For reaction discovery, the directly inspected, dated
[source contract](reaction-discovery.md) supersedes this file's older broad
attributions. Its PRIMARY / LATER BONDE / COMMUNITY / IMPLEMENTATION labels
keep formula authorship separate from the repository's operational choices.
For C, the dated [consolidation source contract](consolidation-quality.md)
supersedes the older broad attributions and records the selected historical
components, segmentation, rounding and A+ policy separately.

Marks: **(B)** Bonde's own words or formula · **(V)** his 2018 video, one
machine transcription, corroborated by an independent port · **(P)** this
repo's provisional proxy, no source number · **(E)** third-party evidence.

Every rule the run applies, in pipeline order, each with its constant and its
class, and what is Bonde's against what is this project's: [rules.md](rules.md).
`tests/test_rule_sheet.py` holds that sheet's numbers to the modules.

## The thesis (B)

Stocks move in momentum bursts of 3–5 days of 8–20% (lower-priced names up to
40%; names above $40 move $5–25). A burst starts with a range-expansion day
out of a quiet consolidation. Enter day 1, stop at the entry day's low, risk
0.25–1%, exit into strength in 3–5 days, gate everything by breadth, and do
it hundreds of times a year. "This is a pattern and probability based trade."

This build does not enter on day 1. It reads the finished burst day after the
close and enters the next session, a route he also describes ("You can also use
it for end of the day scanning and enter next day"); selecting only that route,
the buy stop a cushion over the burst close (at the close itself before
`plan.burst_trigger_rule`) and the burst-day low as a stand-in stop are
SpicyStock's (P).

## Universe (`src/universe.py`)

US-listed common stocks, with a separate SpicyStock session-price policy
of ≥ $3 and seed/explicit exceptions (P); directory quotes do not gate
admission. Volume belongs to each scan's own formula, not a shared universe
prefilter. The optional price filters in Bonde's posts are documented in the
reaction source contract and are not universal PCF terms. Biotech and foreign-domiciled names are
flagged, not excluded (P: binary-event and home-market risk are the page's
warning, not a filter Bonde applies).

## Scans (`src/scans.py`)

- 4% burst: `c/c1 >= 1.04 and v > v1 and v >= 100000` (PRIMARY, May 21,
  2015; repeated September 20, 2016).
- $ breakout: `c - o >= 0.90 and v > 100000` (PRIMARY, July 13, 2017) —
  close minus OPEN. The 2016 Dollar version has an inclusive volume floor;
  the 2017 4% version has a strict one. See the source contract for these
  dated differences; no formula changed during source verification.
- 4% breakdown: the mirror, `c/c1 <= 0.96` (B).
- Admission (`src/admission.py`, P, 4 November 2026): a name the 4% scan
  discovered may be planned and read; a name the dollar scan alone discovered
  may be only when its burst day passed the checklist's RE and VOL checks --
  RE Bonde's own phrase for a burst day, "a day which is up bigger than the
  last 5 to 10 days bars" (B), VOL the 4% scan's own volume test, v > v1
  (scan) -- applied as a gate by SpicyStock (P). The
  $0.90 body is a 2017 number that does not scale with price: over the 35
  retained sessions to 3 November 2026, 1,913 of 2,473 mechanical A-band
  grades came through the dollar scan alone, 1,757 of them on a day under +4%.
  Admission is never a grade; a name it stops keeps its checklist grade as
  research, earns no ticket and is sent to no chart reader. The scan formulas
  and the checklist are unchanged.
- Anticipation pool: Double Trouble `c/minl252 >= 1.8`, TI65
  `avgc7/avgc65 > 1.05`, MDT `c/avgc126 > 1.19`, each on 100,000 shares over
  the prior three sessions (`minv3.1`: at least for Double Trouble, more than
  for the other two) (B), on a quiet day of −1%..+1% (B, 2014; ±0.4% is his
  2018 tightening).
- Episodic pivot `c/c1 > 1.04 and v > 3*avgv50.1 and v >= 300000` and EP9M
  `v >= 9,000,000 and c >= 3` (B) — measured, not traded here.

## The A-quality checklist (`src/quality.py`) — Bonde's letters

| letter | rule | source |
|---|---|---|
| 2 | not up two days in a row before the burst; a day under +1% is flat | (B) 2LYNCH 2020/2024 |
| 2 veto | three or more consecutive rising closes ending the session before the burst, of any size → refused (grade skip) | (B) 2014–2018 "not up 3 days in a row"; (V); counting a rise of any size is (P) |
| L | prior leg linear: efficiency ratio ≥ 0.40 or R² ≥ 0.55; failure is a veto | ER formula (B) 2009; veto (B) 2011; thresholds (P) |
| Y | first or second breakout of the move | (B) 2LYNCH; the "start of the move" definition is (P) |
| N | prior day negative OR its range under 2% of price | (B) "narrow or negative"; 2% (V) |
| C | selected 3–20 sessions, ≤ 1 price-only 4% down day, giveback ≤ 0.34, tightness ≤ 1.0; A+ additionally requires 0 down/up 4% days, giveback ≤ 0.25, tightness ≤ 0.70 and both volume ratios < 1 | Length PRIMARY 2014; down-day allowance LATER BONDE 2020; base/leg boundaries, partial treatment, exact ratios and composite A+ are DERIVED (P). Ordinary C does not require lower volume. See the dated C contract. |
| H | closed within 20% of the high and above the open | (V) "within 20% of high"; C>O (V) |
| RE | today's range ≥ every range of the prior 5 (A+: 10) sessions | (B) "bigger than the last 5 to 10 days bars"; ratio (P) |
| VOL | volume above yesterday (scan); rank in the last 60; +CV: a base over ~21 sessions needs 1.5× the 50-day average | (B); +CV (E, two secondary sources) |

A or A+ requires 2 and H to pass outright (P, from Bonde's emphasis). A name
that meets everything but H is an anticipation setup, not a rejection (B,
bootcamp notes). Bonde publishes no pass count; the score weights are (P).

Weights (P): L 2, C 2, and 1.5 each for 2, Y, N and H, ten in all; a partial
earns half, and RE and VOL score nothing. Bands (P, `grader.GRADE_BANDS`): A+
from 9.0 with at least four of the eight checks at their A+ standard (else A),
A from 8.0, B from 6.5, C from 5.0, skip below. A veto is skip whatever the
score.

## Reader authority (`src/reader_authority.py`)

The mechanical checklist is unchanged. The reader may confirm or lower its
judgement using the chart-review concepts in `strategy.md` or an actual
recorded FAIL/PARTIAL. The named criterion/source/observation identifiers,
structured evidence citations, and whole-response rejection are DERIVED (P)
implementation boundaries. They are not new source thresholds. Discovery
routes, measured facts and unknowns cannot be redefined. Visual proxies can
miss a qualitative defect; the reader can still name that defect with the
chart present. Code validates authority and cited facts, not subjective visual
truth. Free commentary does not create order terms or an executable rule.
Request version 3 names, in the instruction, the checks each criterion may cite,
and limits a citation's path in the structured-output schema to the paths the
reader evidence carries; it narrows what a reply can say and never widens what
the validator accepts.

Review selection (`src/review_selection.py`) is DERIVED (P) resource allocation,
not a Bonde threshold or a performance claim. `account_feasible_first_research_v2`
keeps the twelve-read ceiling. Feasible private mechanical plans get first
priority in mechanical-grade / descending-score / ticker order; at most 2
spare reviews sample infeasible mechanical A+/A names whose discovery is
admitted, one ranked and one rotated by SHA-256 of policy, measured session
and ticker. A name the admission stopped is blocked (`route_not_admitted`)
and is not research either; version 1 (10 October to 3 November 2026) had no
such blocker and is replayed under its own frozen rules. No feasible review
is displaced. This near-admission research pool is explicitly selection-biased.
Per-candidate blockers/purposes and requested/result/attempt counts are retained
under the rules identity. Final accepted review, regime, sizing, event and
combined-allocation requirements remain separate and unchanged.

## Run status (`src/inputs.py`, `src/followup.py`, `src/reader_coverage.py`)

Two tolerances decide whether a night is called degraded, and nothing else
(P): no grade, gate, plan, ticket or measurement reads them. A stale tail of at
most 1% of the intended stocks, each ending within the 5 sessions before the
session evaluated, is counted and named with where each frame ends, and read
again by the next session's run at every session it missed; stocks with no bar
before the session evaluated in the run's request window (every row dated that
session, as on an exchange listing's first day) are counted beside that tail
against the same limit and never measured, since there is no session before to
measure a move against; refusals by reader authority or the
discovery contract within a quarter
of the night's reads, or within one if that is more, with every other read accepted (at least one) and none on a name the
regime would have planned, are counted by cause. A stale stock is still an
unknown input and a refused reading still leaves the checklist's grade and no
ticket. An empty credit balance stops the calls like a refused key; a request
the API refused as invalid (HTTP 400) is counted by its own cause, never asked
again, and two names refused alike in a row stop the asking.

## Market Monitor (`src/breadth.py`)

His Telechart v12.4 formulas (B): up/down 4% with `V >= 100000 and V > V1`;
25% in a quarter (65 sessions) and 25%/50% in a month (20 sessions) with
`AVGC20*AVGV20 >= 250000`; 13% in 34 days; % above the 40-day average.
Regime: five rules over the stocks measured that night (N). The three count
thresholds are his readings over ~6,500 stocks as the field guide quotes them,
each scaled before it is compared: threshold × N ÷ 6,500, rounded to one
decimal (`scaled_threshold()`, P). The ratios are never scaled. As an example,
at N = 3,513 (the 17 November 2026 record) 700 becomes 378.3, 20 becomes 10.8
and 200 becomes 108.1.

- Red, no new longs and no burst plan (the size multiplier is 0): names down
  4% today at or over the scaled 700 (`DOWN4_ALARM`; his reading is "a series
  of days with 700+", and firing on a single day is P), or a 10-day ratio
  below 1 (`RED_RATIO_10D`, P), or a 5-day ratio below 0.5 with more names
  down 4% than up 4% today (`RED_RATIO_5D`, P).
- Yellow, half size and A+ bursts only (the size and the band are P): a 10-day
  ratio below 2 (`YELLOW_RATIO_10D`: "not an ideal time for swing longs"), or
  more names up 50% in a month than the scaled 20 (`UP50_MONTH_HOT`: frothy).
- Green, full size, A+ and A bursts: none of the five fires. A 10-day ratio at
  or over 2 alone is not enough.

Fewer names down 25% in a quarter than the scaled 200 is an oversold flag,
informational and never a verdict input (`DOWN25_QUARTER_OVERSOLD`; the guide's
wording, not yet checked against his own). The gate is SpicyStock's reading of
his Market Monitor for its own model tickets; the record does not establish
that it improves outcomes.

## The plan (`src/plan.py`)

Risk 0.5% of equity per trade (B: 0.25–1%), position ≤ 25% of equity and at
most four open plans (P, scaled from "fully invested across 3–4 positions").
Shares = risk ÷ (entry − stop) (B). Stop: the burst day's low, else the bar's
midpoint, at most 4% under the ticket's LIMIT (B: "less than 4% and ideally
less than 2%"): a stand-in (P) for his entry-day low, which replaces it at the
close of day 1 when it is higher (B). Between 2% and 4% the risk is halved
(P), which is every burst ticket, because the limit is set from the stop:
0.25% of equity on green, 0.125% on yellow. Next-session entry only if not
extended (B): the ticket is a buy stop a cushion over the burst close, the larger of
$0.02 and 0.1% of the close (`plan.trigger_cushion()`, the setting-up
ticket's own cushion; records made before `plan.burst_trigger_rule` carry
the buy stop AT the close), with a limit at most 4% above the close, so it
can fill only between the two (P); an open more than 2%
under the close is the burst failing and an open above +4% is day 2 already
spent, and neither is taken (P); +8% is the level at which he sells half (B)
and is printed as a third line. The order is a buy stop-limit with an
attached stop-market loss (B: "if they reverse then get stopped out"; stop
type per Qullamaggie "market stops, never limit stops"). The ticket's shares,
its stop distance and the halving are judged at its limit, the highest fill
it permits (P): a fixed quantity that keeps the budget and the 4% line at
every fill it can take, or no ticket. His 4% is measured from his own fill;
the implemented `stop_constrained` rule narrows the ticket limit to the lesser
of the outer +4% ceiling and floor-to-cents(stop / 0.96). It tries the signal
low, then its cent-rounded midpoint, and requires a stop below the trigger
and a limit strictly above it. This DERIVED choice has been implemented since
September 12; the old fixed-ceiling incompatibility is not current behavior.
Price-to-stop risk is not a guaranteed maximum loss: stop-market gaps can
exceed it.

Exits (B, 2018, unless marked), as `plan.EXIT_RULES` prints them on every
ticket and `plan.follow()` walks them, measured from the fill. Each bar is
read open first, then the low against the stop, then the high, then the close
(P).

- `sell_half_8pct`: +8% same or next day → sell half and raise the stop to
  25–50 cents under that day's high. The model uses 25 cents and applies the
  rule on any day until day 3's close has sold a half.
- `abnormal_10pct`: a close 10% or more over the entry → at least partial
  profit. The model books no sale for it and only raises the stop to 25 cents
  under that day's high.
- `gap_20pct`: an open 20% or more over the entry → out at the open.
- `entry_day_low`: close of day 1 → the stop rises to the entry day's low when
  that is higher. This is his own stop; the burst-day low stood in for it.
- `day3_sell_half`: day 3 close → sell at least half, in whole shares, if no
  half has been sold.
- `day3_no_progress`: a day-3 close at or under the entry → out.
- `trail_after_day3`: from the close of day 3 the stop rises to each day's low
  and never moves down (P, a reading of "after 3rd day keep moving stop to low
  of day").
- `day5_exit`: day 5 close → out.
- `stop`: the protective stop is a stop-market order. In the model an open at
  or under the stop is out at that open, which can be well under the stop, and
  a low at or under it is out at the stop price, even when the same bar's high
  reached a sale level (P). The ticket adds "if it is somehow not filled, exit
  on any close below it", which the model does not walk.
- `no_breakeven`: every ticket also prints "do not move the stop to break-even
  before day 5 just because it is green". That is theStrat Lab's backtest of a
  different setup (EP 9M), carried over by this build (DERIVED, unvalidated on
  bursts); his own 2015 text describes earlier break-even management, and the
  model moves no stop for it.

Under a red market an open plan's instruction gains "sell into any strength;
do not add" (P); no stop is moved and no sale is booked for it.

Hazards halve the size, never veto, and both together still halve it once: a
burst day of 15%+ (E: the worst cell in the one event study, −9.3% at 20
sessions, 36% win rate) and a close more than 20% over the 20-day average (P).

## Anticipation watchlist (`src/watchlist.py`)

His three scans on a quiet day (B), then range contraction made numeric (all
P): three tight days in a row, each under 70% of the 20-day average range, or
three such days in the last ten; a 7-session range ≤ 0.75 of
the norm and ≥ 0.30 of it (under that the price is pinned, not coiled: every
name below it on the lists from 11 Sep to 7 Oct 2026 was a pending cash
takeover); ≤ 1 breakdown in the last ten sessions; not up three days in a row;
a close at most 1.10 times its 20-session average; a box of 3–10 sessions.
Dry volume is measured and decides nothing. Trigger =
box high + a few cents (B), stop = the lowest low of the last 3 sessions (B),
ticket refused when that stop is more than 4% under the ticket's limit, the
trigger +1% (the 4% is B, measuring it at the limit is P). The list's own
`eligible` measures the same 4% from the trigger, so a listed name can still
have its ticket withheld. "Most good anticipation setups break out in the
first 10 to 15 minutes" (B), so the order is placed the night before.

## Earnings warnings (`src/earnings_risk.py`)

Not Bonde's rule: no inspected source of his sets an earnings hold, and this
build adopts none. The warning is SpicyStock's, about a gap a stop does not
protect against, and it never vetoes, sizes or cuts a ticket. The estimate is
last year's results filing (SEC form 8-K, item 2.02) put 52 weeks on, 364 days
(P), within ±7 days (P), each of this year's filings standing for at most
one of last year's; an estimate whose range ended more than 45 days before
the signal (P) no longer reads as overdue, though an issuer with no results
filing for longer than any gap between its own earlier ones still does. Every estimate says it is one, and a ticket
SEC did not answer for is unknown, never clear.

Version 2 of the block reads one more thing off the same filing list, at no
extra request: the ticket's recent SEC current reports (form 8-K and its
amendments) filed within 14 days (P) before the signal or since it, 8 kept (P),
those with a material item first and then the newest, with the window's count
beside them, listed by item code under SEC's own Form 8-K headings. A material
item -- 1.01, 1.03, 2.01, 3.01 or 5.01 (DERIVED: SpicyStock's list, each the
first filing a cash acquisition, a delisting or a failure tends to make) -- is
named with its filing date, its acceptance time and where that fell against the
hold. An item names a kind of event, never what the filing says, so the
sentence says to read it before entry; it withholds nothing, and only the
manual event registry does.

## What the evidence says (E)

The one pre-registered test of mechanised 2LYNCH gates (n=10,947) found the
gates remove the losing half and do not find the winning half; the raw 4%
scan has no median edge at 20 days; the ≥15% burst day is the worst cell.
theStrat Lab's EP9M backtest: negative expectancy without a hard low-of-day
stop; break-even on day 2 collapses the win rate. That is a different setup:
this build carries its break-even caution onto burst tickets without having
measured it on bursts. Attribution: the 4% event
studies are Fluxus-Trade-Lab's, not theStrat Lab's. None of this is
SpicyStock's own evidence.

## Earlier access limits

At the rebuild, stockbee.blogspot.com, x.com, YouTube and archive.org were
blocked; every
(B) quote came through a research archive that quotes his posts verbatim with
per-post URLs, his bootcamp notes on GitHub, and search-engine snippets. The
2018 video numbers (2%, 20% of the high) should be re-listened to once.
On September 16, 2026, public Bonde blog text was directly retrieved for the
reaction source contract. Its evidence register records exactly what was
inspected and what remains unavailable; it does not re-certify unrelated
quality, breadth or plan attributions above.
On September 22, 2026, the consolidation contract separately inspected the
2014, 2015, 2017, 2018 and 2020 blog text. In particular, 3–10 belongs to
anticipation; the 2018 reaction window is 5–40 with no 4% breakdowns. These
are not interchangeable versions of the selected C rule. No primary exact
one-third/quarter giveback or tightness-ratio formula was verified.

## The record (`src/record.py`)

Every published plan is kept (`docs/picks.json`) and replayed as a model (P).
A daily bar books a ticket filled only at the next open, at or over its
trigger and at or under its limit. A first day that opened under the trigger
and reached it later is read again from that session's one-minute bars
(`src/intraday.py`, `first_window_minute_v1`, P): the first minute of the first
30 whose high reaches the trigger fills at the trigger, or at that minute's
open when it opened over it; none means not filled; and a crossing minute that
cannot be ordered against the limit or the stop stays uncertain. Without usable
minute bars such a day is uncertain, and so is an open past the limit or under
the skip line that could still have filled a resting order: no fill, no R,
counted by reason. A plan filled at the open whose first-day low then reaches
the stop is not uncertain: it is booked out at the stop, one R lost. A fill at
the open assumes the order was already resting at the broker before the open.
The published stop is one R on the whole position; "at
least half" is whole shares (2 of 3, 1 of 1) and every sale is weighted by
the shares it sold; everything settles by day 5 (B, the hold). The scorecard
prints counts from the first night and rates only from twenty settled plans
(P), with SPY over the same days as one comparison line, not a benchmark (P).
