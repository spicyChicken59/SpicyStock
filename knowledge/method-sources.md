# The Stockbee method, as far as the sources reach — and where SpicyStock differs

**Read this before changing a strategy number.** `knowledge/strategy.md` is the
system prompt: what the scoring model is told. This file is the *evidence*:
what Bonde is recorded as saying, who recorded it, and how confident that
makes each number. They are separate on purpose — the round-11 audit found the
rulebook asserting three things the code did not do, and a prompt is a bad
place to keep a citation.

## The standing caveat

**stockbee.blogspot.com is refused by this sandbox's egress proxy**, checked
with curl and again with a fetch, on two separate rounds. Nothing below was
read on Bonde's own site. The sources are, in descending order of weight:

| weight | source |
|---|---|
| strongest | contemporaneous notes taken inside his own bootcamp (`StockBee/Day1.tex`, Pranav Tikkawar, on GitHub) |
| strong | his own posts on X, where the account is his |
| medium | third-party research archives that quote his posts with per-post URLs |
| medium | independent reimplementations that agree with each other without citing each other |
| weak | course material and blog summaries, which copy from one another |

Where two sources disagree this file says so rather than picking. **A number
with one blogger behind it is not a verified number**, and several below are
exactly that.

## The scan

Three conditions, and only three:

```
c/c1 >= 1.04   and   v > v1   and   v >= 100000
```

Close at least 4% above the previous close; volume greater than the previous
session's; volume at least 100,000 shares. Quoted identically by a research
archive tabulating three dated versions (2014-01, 2015-11, 2017-07) and by an
independent reimplementation that had no reason to copy it. Across those three
versions **the only drift is `>` versus `>=` on a constant 100,000** — the
magnitude never moved.

Three things the scan does **not** contain, and this matters more than
anything else in this file:

- **No minimum price.**
- **No float or market-cap limit.**
- **No dollar-volume floor.** The liquidity condition is a *share count*.

And his stated setup *preferences* run toward the small end, not away from it.
From the January 2014 post "How to Identify good momentum burst":

> Low float below 25 million is good. Below 10 million float leads to explosive
> moves
>
> Low priced stocks (below 5 dollar) tend to make very explosive moves

There is a companion scan for expensive names, `c-o >= .90 and v > 100000` —
close minus **open**, so it deliberately excludes the overnight gap, "more
useful on high priced stocks above 40 as they do not often breakout with 4%
move".

*Unresolved:* Telechart's `V` is conventionally in hundreds, which would make
`v>100000` ten million shares. His prose says 100,000, and the breadth version
of the same scan is written `V >= 1000`, which *is* 100,000 in Telechart units.
So either the trading scan is written in raw shares or a transcription lost the
conversion. A reimplementation should use 100,000 shares and say why.

## The quality checklist — 2LYNCH

Scoped by Bonde himself: *"2LYNCH is for only continuation setups. Every setup
I trade has its own qualifying checklist."*

| letter | Bonde | number, if any |
|---|---|---|
| **2** | not up two days in a row into the breakout | a small up day of **less than 1%** before it is fine |
| **L** | linearity of the prior move — "consistent and persistent buying" | none stated |
| **Y** | young trend: the **first or second** breakout out of the consolidation | first or second |
| **N** | a **narrow-range day or a negative day** immediately before the breakout | none stated |
| **C** | consolidation quality: shallow, orderly, compact, low volume | **no more than one 4% breakdown** |
| **H** | the close near the **high** of the day | **not confirmed** — see below |

Five independent sources agree on the letters. The bootcamp notes are the
cleanest rendering and they match his X thread word for word in substance.

**+CV** extends it when the consolidation runs beyond about a month: **C**atalyst,
and **V**olume at **1.5–2x the 50-day average**. That is the only place in any
source where a volume *multiple* appears at all.

Three things nobody could settle:

- **H has three incompatible thresholds in circulation** — top 20% of range,
  top 30%, or "giving back up to 30% of the gain is acceptable" (≈ top 70%).
  Bonde's own wording is qualitative. SpicyStock uses top 30%; the source
  number is unconfirmed.
- **Weighting.** Two secondary sources single out different letters as most
  important (a course calls L critical; the bootcamp notes say a failed H
  reclassifies the setup to *anticipation* rather than rejecting it). No
  Bonde-sourced weighting was found, so a flat pass count is an implementer's
  choice, not his.
- **The up-days rule has two different numbers in two different places**, and
  this is the one place SpicyStock has been quietly right. 2LYNCH says **two**
  days. A separate post on selecting setups says *"Stock should not be up 3
  days in a row prior to breakout day"* — **three**. Both are his. SpicyStock's
  veto at three or more matches the second statement and not the first.

## What makes a setup A-quality

From the January 2014 post the URL calls "how-to-identify-a-quality-setup"
(the title is actually "How to identify the A quality setup"). The passages
below were recovered through a search index, not read on the page, and the
gaps between them cannot be bounded.

The opening frames the whole problem, and it is the sentence this repo should
have had from the start:

> When you start running scans in the morning like 4% scan or $ breakout scan,
> you are throwing a wider net. It catches few good fish and lot of marginal or
> extended setup. The key is to be extremely clear about what you are looking
> for and not get excited by each and every breakout.

**The scan is meant to be wide and the checklist is meant to be narrow.** A
reimplementation that narrows the *scan* has moved the selectivity to the wrong
layer and cannot get it back — the fish it never caught are not in the net.

The timing rule:

> We are looking for a momentum burst lasting 3 to 5 days and that is preceded
> by a 3 plus days of period where there was no momentum burst.

The worked example, which is the most load-bearing sentence for calibration:

> Preceding the breakout for 17 days the stock did not have a momentum burst,
> did not have a 4% breakdown, had a series of narrow range days, was
> essentially consolidating pre breakout.

Seventeen days with **zero** prior bursts and **zero** 4% breakdowns. And the
four characteristics:

> - It traded in narrow range pre breakout
> - It had low volatility pre breakout
> - It traded linearly in previous move and this was a very compact orderly correction
> - On breakout day volume was higher

**"Higher."** No multiple, no average, no window. The mechanism sentence says
why the checklist is about the base rather than the bar:

> If certain underlying conditions are present like nature of pre breakout
> consolidation and low volatility prior to breakout, then it leads to
> explosive moves.

## Managing the trade

- **Entry is intraday on the burst day** — "as soon as stock shows up in a
  scan, which can be anywhere from market open to just before close". An
  end-of-day scan with entry the next morning is **explicitly sanctioned**:
  "you can also use it for end of the day scanning and enter next day." That
  is the route SpicyStock's 18:16 ET email takes, and it is his alternative
  rather than a compromise.
- **Anticipation is a first-class alternative**, not a lesser one: "Some buy
  ahead of the breakout in anticipation while some buy on breakout day. Both
  approaches work. Only the process flow differs and the profit targets
  differ." Its appeal is risk: "Ideal entry is where you risk just few cents
  or less than 2% to get in early."
- **Hold 3 to 5 days**, and the reason is decay: "In most cases the momentum
  dies down in 3 to 5 days. If you keep holding after the 3 to 5 days period,
  you would often see the stock ends up giving up all the burst gains and may
  not have another momentum burst for several weeks or months."
- **The magnitude band is his.** From his own X account: *"Momentum burst is a
  swing trade of smaller 8 to 20% magnitude in 3 to 5 days."* This retires the
  standing "UNVERIFIED" note on `ledger.CLAIMED_BAND` — 8–20% is sourced to
  Bonde, not to the brief. He also uses "8% to 40%" elsewhere, which reads as
  the full-move band against the capture band; he does not always distinguish
  them.

## Anticipation — buying the base instead of the burst

Bonde does not treat this as a second strategy. It is the same cycle entered a
step earlier: *"Range Expansion, range contraction, Range Expansion, range
contraction. that is the cycle. If you understand that you will be able to
find anticipation setups."* Its appeal is the risk: *"Ideal entry is where you
risk just few cents or less than 2% to get in early."*

The scan is two steps — *has been strong*, then *is quiet today*. The strength
step is three scans he says to merge, "as some stocks will be common":

| name | Telechart formula |
|---|---|
| Double Trouble | `c/minl252 >= 1.8 and minv3.1 >= 100000` |
| TI65 | `avgc7/avgc65 > 1.05 and minv3.1 > 100000` |
| (third variant) | published alongside the two above |

Then the quiet gate, which **tightened 2.5x between 2014 and 2018**: today's
change between −1% and +1% in 2014, and between −0.4% and +0.4% in the 2018
bullish version, with price above $3. TI65's threshold drifted 1.05 → 1.04 in
the same 2018 post, and the 65 is deliberate: *"I have reduced the period used
for calculating momentum from 130 days to 65 days. Markets are faster."*

**`src/stockbee.py`'s `_anticipates()` is already a faithful reading of the
2014 variant** — `trend_intensity >= 1.05` is TI65, the ±1% band is the 2014
quiet gate, `minv3.1 >= 100000` is the three-session volume floor, and the
price floor is $3. What it adds is a compression ratio, which is this repo's
own numeric proxy for the chart read, and its own comment says so.

The chart checklist he republished word for word in 2014, 2015 and 2018:

> - series of narrow range days in pullback/consolidation
> - orderly pullback with no 4% b/d during the pullback or consolidation
> - low volume pullback
> - low volatility during pullback
> - linear first leg if looking as continuation setup
> - Stock should go up smoothly and not in volatile manner

Note the fifth line. **"Linear first leg"** — the linearity test is about the
*first leg*, the advance, not the pullback. That is the same reading
`src/lynch.py`'s `L` check now applies.

## The Market Monitor — breadth as a go/no-go switch

Its stated purpose is not forecasting: *"an overall filter for deciding when to
use breakout methods, when to be aggressive in terms of margin and risk, and
when to be defensive."*

The daily pair, in his own TC2000 syntax:

```
up 4% in a day:    (100 * (C - C1) / C1) >= 4    AND V >= 1000 AND V > V1
down 4% in a day:  (100 * (C - C1) / C1) <= (-4) AND V >= 1000 AND V > V1
```

`V >= 1000` in Telechart's hundreds is 100,000 shares — the same floor as the
trading scan, which is the strongest argument that the trading scan's
`v>100000` is also meant as 100,000 shares rather than ten million.

The 5- and 10-day ratios are **sums of counts, not averages of daily ratios**:
the count of 4% up days over the window divided by the count of 4% down days
over the same window. `src/stockbee.py` computes them exactly that way.

The quarterly movers use a 65-bar anchor rather than a rate of change:

```
up 25% in a quarter:   100 * ((C+.01) - (MINC65+.01)) / (MINC65+.01) >= 25  and AVGC20 * AVGV20 >= 2500
down 25% in a quarter: 100 * ((C+.01) - (MAXC65+.01)) / (MAXC65+.01) <= -25 and AVGC20 * AVGV20 >= 2500
```

**One caveat that applies to every breadth number this repo publishes.** His
counts are cross-sectional over the whole US common-stock universe. Ours are
over the 500 names the selector picked, and `stockbee.scope.whole_market` says
`false` for exactly that reason. The ratios are internally consistent and they
are **not** comparable to his published Market Monitor figures.

## Where SpicyStock differs, and whether it meant to

| # | Bonde | SpicyStock | deliberate? |
|---|---|---|---|
| 1 | volume > previous session | `min_rvol` 1.5x a 50-session average, **as a scan gate** | no — this is his conditional **+V** criterion promoted to an unconditional filter |
| 2 | volume floor of 100,000 **shares** | 30th-percentile **dollar-volume** floor, $76.7M/day on 2026-09-09 | no — and it refused a $62M/day burst as illiquid |
| 3 | no price minimum; low-priced names preferred | `min_price` $4, and the universe selector drops everything under $4 | no |
| 4 | no float or cap limit; **low float preferred** | universe selects on 20-session momentum and "liquid leader" | no — the selection runs opposite to his preference |
| 5 | `2` = not up two days in a row | veto at three or more | **matches his other statement**; defensible |
| 6 | `Y` = first or second breakout | called `2`, same rule | letter shuffled, rule intact |
| 7 | `N` = narrow **or** negative day before | called `C`, and requires narrow **and** quiet, not either | letter shuffled, rule tightened |
| 8 | `C` = compact base, ≤ one 4% breakdown | called `N` (compactness) plus a separate non-voting breakdown note | letter shuffled, rule split |
| 9 | — | `Y` = extension over the 20-day average and the month's run-up | **an invention**; a real risk measure, but not his |
| 10 | scan wide, filter narrow | scan narrow (rules 1–6), filter at 3 of 6 | inverted |

Items 1 to 4 all push the same way: **toward large, liquid, already-moving
names and away from the small, quiet, low-priced ones his own posts prefer.**
That is one bias with four causes, not four separate defects.

## What no source could settle

Written down so the next round does not re-derive them:

1. Which exchanges Telechart's "Common Stock" list spans, and therefore
   whether a reimplementation's universe should be ~3,000 or ~7,000 names.
2. The `H` threshold.
3. Whether the six letters carry weights.
4. The verbatim exit rules from his July 2018 exit-guidelines post — the
   single highest-value page still unread, and the one a person with ordinary
   network access could settle in a minute.
5. Whether his published win rate is 40% or 60%; both circulate, over
   populations that are probably different.
