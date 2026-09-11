# The method SpicyStock implements, and where each number comes from

Pradeep Bonde's (Stockbee) Momentum Burst method, as the field guide
"The Stockbee A-Quality Setup & Momentum-Burst Method" states it and as the
rebuild's research lenses sourced it. Every number the code applies is a named
constant in the module that reads it; this file says whose number it is.

Marks: **(B)** Bonde's own words or formula · **(V)** his 2018 video, one
machine transcription, corroborated by an independent port · **(P)** this
repo's provisional proxy, no source number · **(E)** third-party evidence.

## The thesis (B)

Stocks move in momentum bursts of 3–5 days of 8–20% (lower-priced names up to
40%; names above $40 move $5–25). A burst starts with a range-expansion day
out of a quiet consolidation. Enter day 1, stop at the entry day's low, risk
0.25–1%, exit into strength in 3–5 days, gate everything by breadth, and do
it hundreds of times a year. "This is a pattern and probability based trade."

## Universe (`src/universe.py`)

US-listed common stocks (Bonde's TC2000 "Common Stock" list, ~6,500 names),
price ≥ $3 (B), last-session volume ≥ 100,000 shares (B: `v>=100000`). No
float, cap or sector exclusion (B). Biotech and foreign-domiciled names are
flagged, not excluded (P: binary-event and home-market risk are the page's
warning, not a filter Bonde applies).

## Scans (`src/scans.py`)

- 4% burst: `c/c1 >= 1.04 and v > v1 and v >= 100000` (B, 2015/2017).
- $ breakout: `c - o >= 0.90 and v > 100000` (B, 2017) — close minus OPEN.
- 4% breakdown: the mirror, `c/c1 <= 0.96` (B).
- Anticipation pool: Double Trouble `c/minl252 >= 1.8`, TI65
  `avgc7/avgc65 > 1.05`, MDT `c/avgc126 > 1.19`, each with `minv3.1 > 100000`
  (B), on a quiet day of −1%..+1% (B, 2014; ±0.4% is his 2018 tightening).
- Episodic pivot `c/c1 > 1.04 and v > 3*avgv50.1 and v >= 300000` and EP9M
  `v >= 9,000,000 and c >= 3` (B) — measured, not traded here.

## The A-quality checklist (`src/quality.py`) — Bonde's letters

| letter | rule | source |
|---|---|---|
| 2 | not up two days in a row before the burst; a day under +1% is flat | (B) 2LYNCH 2020/2024 |
| 2 veto | three consecutive up closes of any size → refused | (B) 2014–2018 "not up 3 days in a row"; (V) |
| L | prior leg linear: efficiency ratio ≥ 0.40 or R² ≥ 0.55; failure is a veto | ER formula (B) 2009; veto (B) 2011; thresholds (P) |
| Y | first or second breakout of the move | (B) 2LYNCH; the "start of the move" definition is (P) |
| N | prior day negative OR its range under 2% of price | (B) "narrow or negative"; 2% (V) |
| C | base 3–20 sessions, ≤ 1 breakdown, gave back ≤ ⅓ of the leg, bars tighter than the norm; A+ needs 0 breakdowns, 0 bursts inside, ≤ ¼, lower volume | 3–20 (B) 2014; ≤ 1 (B) 2LYNCH; ⅓ (P, one webinar port); tightness (P) |
| H | closed within 20% of the high and above the open | (V) "within 20% of high"; C>O (V) |
| RE | today's range ≥ every range of the prior 5 (A+: 10) sessions | (B) "bigger than the last 5 to 10 days bars"; ratio (P) |
| VOL | volume above yesterday (scan); rank in the last 60; +CV: a base over ~21 sessions needs 1.5× the 50-day average | (B); +CV (E, two secondary sources) |

A or A+ requires 2 and H to pass outright (P, from Bonde's emphasis). A name
that meets everything but H is an anticipation setup, not a rejection (B,
bootcamp notes). Bonde publishes no pass count; the score weights are (P).

## Market Monitor (`src/breadth.py`)

His Telechart v12.4 formulas (B): up/down 4% with `V >= 100000 and V > V1`;
25% in a quarter (65 sessions) and 25%/50% in a month (20 sessions) with
`AVGC20*AVGV20 >= 250000`; 13% in 34 days; % above the 40-day average.
Regime (B, thresholds scaled to the measured universe against his ~6,500):
10-day ratio below 2 → not ideal for swing longs (yellow); 700+ names down 4%
in a day, or a 10-day ratio below 1, or a 5-day ratio below 0.5 with more
down than up today → red; 50%-in-a-month above 20 → frothy (yellow). Below
200 down-25%-in-a-quarter is an oversold flag (B), informational.

## The plan (`src/plan.py`)

Risk 0.5% of equity per trade (B: 0.25–1%), position ≤ 25% of equity and at
most four open plans (P, scaled from "fully invested across 3–4 positions").
Shares = risk ÷ (entry − stop) (B). Stop: the burst day's low, else half its
range, kept under 4% (B: "less than 4% and ideally less than 2%"); between 2%
and 4% the risk is halved (P). Next-morning entry only if not extended (B):
a buy zone from 2% under the burst close to 4% above it (P), a skip at +8%
(B: the level at which he sells half). The order is a buy stop-limit with an
attached stop-market loss (B: "if they reverse then get stopped out"; stop
type per Qullamaggie "market stops, never limit stops"). Exits (B, 2018):
+8% same or next day → sell half and raise the stop under that day's high;
10%+ abnormal day → partial; 20%+ gap after entry → out at the open; day 3
close → sell at least half; no progress by day 3 → out; after day 3 trail the
stop to each day's low; day 5 → out. No break-even move before day 5 (E).
Hazards halve the size, never veto: a burst day of 15%+ (E: the worst cell in
the one event study, −9.3% at 20 sessions, 36% win rate) and extension of 20%
over the 20-day average (P).

## Anticipation watchlist (`src/watchlist.py`)

His three scans on a quiet day (B), then range contraction made numeric (all
P): three tight days at 70% of the 20-day range, a 7-session range ≤ 0.75 of
the norm, dry volume, ≤ 1 breakdown, not up two days, not extended. Trigger =
box high + a few cents (B), stop = the low of the last 2–3 days (B), refused
over 4% (B). "Most good anticipation setups break out in the first 10 to 15
minutes" (B), so the order is placed the night before.

## What the evidence says (E)

The one pre-registered test of mechanised 2LYNCH gates (n=10,947) found the
gates remove the losing half and do not find the winning half; the raw 4%
scan has no median edge at 20 days; the ≥15% burst day is the worst cell.
theStrat Lab's EP9M backtest: negative expectancy without a hard low-of-day
stop; break-even on day 2 collapses the win rate. Attribution: the 4% event
studies are Fluxus-Trade-Lab's, not theStrat Lab's.

## Unreachable from this sandbox

stockbee.blogspot.com, x.com, YouTube and archive.org were all blocked; every
(B) quote came through a research archive that quotes his posts verbatim with
per-post URLs, his bootcamp notes on GitHub, and search-engine snippets. The
2018 video numbers (2%, 20% of the high) should be re-listened to once.
