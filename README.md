# SpicyStock

One evening run over every US-listed common stock, one page that says what
to do tomorrow and why, one email that says the same in fewer words. The
method is Pradeep Bonde's (Stockbee) momentum burst: a 4% range-expansion
day out of a quiet base, bought the next morning inside a narrow zone with
the stop under the burst bar, sold into strength over three to five days,
and only when breadth allows it. `knowledge/method.md` says whose number
every rule is; this file says what the software does with them.

The page is the product. It is generated, static, and renders one file,
`docs/data.json`; it computes nothing of its own except whether the record
it is showing is tonight's. Everything else — the regime, the grades, the
share counts, the order tickets, the exits, the record — is written by the
run and printed verbatim. It is an implementation of the method with
explicit assumptions (the archived rules, and `knowledge/method.md` on whose
number each is), not a proven edge, and it knows nothing about what anyone
holds: every plan it follows is a model of the published ticket.

**Fourteen days.** Week one is paper: read the page every evening, place the
orders in Fidelity's paper view or not at all, and read the open-plan rail
each morning. Week two is the $10,000 account at the default 0.5% risk
(0.25% is the more conservative end of his band and one variable away). Day
fourteen is a decision point, made on the page's own reliability row and
its bars-only scorecard, not on a feeling — and not an automatic switch to
real money: twenty settled model plans make a rate readable, not an edge.

## What the page says

The page is a small application over one record: four views behind the
masthead, the state kept in the hash (`#/explore/bursts/AAPL`,
`#/explore/setting-up/COIL`, `#/record`, `#/market`, `#/method`) so a link
reloads to the same stock and the Back button works; the old one-page
anchors (`#hold`, `#orders`, `#trade-X`, `#burst-X`, `#closest-miss`) still
land where they used to. Choosing a stock fetches nothing, grades nothing
and sizes nothing; a route the page does not know, or a symbol the record
does not carry, falls back to Explore and says so.

1. **The status chip.** The one thing the page computes: from the record's
   session and the browser's clock in ET it says *fresh*, *tonight's run
   pending*, *STALE · 1 session behind* (closed or failed, it cannot tell),
   *STALE · N sessions behind* (never a closure: no two US market holidays
   are adjacent), *market closed* or *degraded*, with one fixed sentence per
   problem kind. A stale page says *Do not place these orders*, points at
   the run log, and withholds every ticket from the action area, the plan
   and the order sheet, keeping the setups.
2. **Explore**, the default view. The market in a line: the verdict, one
   of six sentences — *Trade tomorrow. N A-quality bursts.* · *Trade small.
   N A+ bursts.* (a yellow regime) · *Stand aside.* (red) · *Nothing
   qualifies. Keep cash.* · *Market closed. Plans unchanged.* · *No verdict
   for <session>.* (the run failed before it published) — with the dek's
   breadth numbers, the regime chip and the size rule, the session, and the
   record's own call to action. Then two stage cards, **Bursts · N** (the
   range-expansion days the scan graded) and **Setting up · N** (the
   anticipation list: quiet, coiled names inside established momentum),
   and inside the chosen stage — as cards, or for the bursts as a **map**
   of the session's gain against its volume relative to the previous
   session, every point the same selection as its card, the unmeasured
   listed beside it, position a measurement and not a return — one
   selectable card per stock with its grade and its status in the record's
   words — *ticket*, *ticket
   withheld*, *beyond the slot cap*, *beyond the configured equity*, *no
   whole share*, *no new longs*, *vetoed*, *no ticket*, *watch* — a search
   that finds a ticker in either stage and says when it switched, and on a
   phone a rail of cards with a *Choose stock* dialog. The first load shows
   Bursts when the scan found any, Setting up otherwise, and a chosen stage
   is never switched away from: an empty one says why it is empty. Each
   stage remembers its last chosen stock.
3. **The chosen stock.** One chart panel with one header (the symbol, its
   last close and session), the controls together above the plot, and every
   price label in a reserved right gutter with a leader back to its exact
   level: the last close, the stop, the trigger, the limit (the highest fill
   the ticket permits) and, for a burst, the zone's floor. Three modes over
   the same bars, levels and dates — *Setup* (the annotated view: the base,
   the trigger and zone, the stop, the burst evidence), *Candles*
   (conventional up/down candles, hollow and filled, with a quiet close-line
   toggle) and *Line* (the recorded closes) — and three ranges: the *Setup
   range* (the base and a short run of context before it, the dates
   disclosed; without base dates it says so and shows 60), 60 and 120
   sessions. The mode and the range are remembered in the browser. The aim
   levels are printed beside the chart, and say so when they sit outside
   the visible range; a coil draws its box and its trigger and no burst
   candle; a name without archived bars says *Chart unavailable* and keeps
   its conditions. Four answers, each from the record's own sentences:
   *why this stock?*, *what would need to happen?*, *what invalidates it,
   or makes me wait?*, *principal risk or limitation*. Then the action
   area: the conditional ticket's order line with *View conditional plan*,
   or the reason there is no ticket with *Inspect conditions* — never a buy
   button. Under it four disclosures: the conditions (one tile per
   criterion with the measured value, his threshold and the verdict in
   words, then the base, the burst and the grade); the plan, sizing and
   order (the buy zone and the two skip lines, the stop and its basis, the
   shares sized at the limit — the highest fill the ticket permits, so the
   fixed quantity keeps the risk budget, the position cap and his 4% stop
   line at every fill it can take — the position, the planned
   price-to-stop risk, the aim, the hazards, and the order in Fidelity's
   field order with a copy button: a buy stop-limit with a
   one-triggers-the-other sell stop attached, and under it what the ticket
   enforces and what it leaves to the reader); the model exit guidance,
   dated; and the provenance (what Claude saw in the chart, the bars, the
   rules digest). A burst whose stop is past the line at the limit keeps
   its card and has its ticket withheld, with the reason in the action
   area. Below the workspace, two more disclosures: **Tomorrow's
   tickets** (the model allocation over the configured sizing assumptions
   and the order sheet, every cut name explained) and **Everything the
   scan found** (every burst against the checklist — the six letters,
   range expansion and volume — sortable by score, each name a way to its
   card, the closest miss named above it).
4. **Record.** **Open model plans** is every pick from the last five
   sessions walked from bars alone as a model: *day 3: sell half*,
   *stopped*, *not filled*, *uncertain* (the bars cannot say whether it
   filled), with the stop the rules would have moved it to; SpicyStock
   does not know what you hold. Then the bars-only scorecard (plans, fills,
   win rate, average R, SPY over the same days) and fourteen dots for the
   last fourteen evenings: ok, degraded, closed, missing.
5. **Market.** Bonde's Market Monitor over every stock that printed today:
   up and down 4% on volume, the 5- and 10-day ratios, the
   25%-in-a-quarter and 25%/50%-in-a-month counts, the share above the
   40-day average, the 10-day ratio over the last thirty sessions with his
   line drawn on it, and the regime verdict with every rule that fired.
   Thresholds are scaled to the measured universe against his ~6,500.
6. **Method.** Tonight's run (coverage, grades, reads, delivery, timing,
   the run log), how to read the page, and the configured sizing
   assumptions every ticket was computed from.
7. **Following.** One click beside a stock's action area — *Follow this
   setup*, with the plan's suggested whole-share quantity when it has a
   ticket, for observation alone when it does not — keeps the setup on a
   compact shelf at the end of Explore, saved in this browser only (a
   versioned store keyed by symbol, session, kind and rules identity;
   idempotent; a blocked or corrupt store is named, never reported as
   saved). A card carries the saved plan's levels, one optional reference
   size of the reader's, the latest close the record carries for the
   symbol (the `observations` block, else the record's own rows, else the
   last observed date and *no newer observation available*), the movement
   since the signal close as price movement and not a result, and the
   model plan's update separately labelled. A saved plan is never a fill,
   a holding, a sale or a stop-out, and nothing here reaches the record,
   the mail or the scorecard.
8. **Sample data.** A record written by `tools/make_fixture.py` says so:
   a *Do not trade sample data* notice under the market bar naming the
   fixture, a *demo data* chip on the chart panel and the burst map, a
   *demo* chip on a followed card, and a chart-reader reply labelled
   simulated. Demo follows are kept under their own browser key.
9. **The next action**, under every view: place the N orders from
   tomorrow's tickets before 9:28 AM, nothing to place, no new longs, plans
   unchanged, or do not place these orders.

The email is the same record in fewer words: the verdict, the breadth line,
one block per trade with its order line and the day-order term, the plans
without a ticket and why, the open model plans' instructions, the alerts,
the problems and a link. Delivery failing never costs the page.

## How a night runs

`evening.yml` fires at 6:16 PM ET on weekdays (two crons, one per UTC
offset; the guard runs the right one) and again at 8:16 PM ET as a retry
that runs only if `docs/data.json` does not already carry tonight's
session. The run:

- **universe** — Nasdaq's stock directory, every US-listed common stock at
  $3 and 100,000 shares (about 3,000 names; biotech and foreign are flags on
  the page, not exclusions). A directory that will not answer falls back to
  its seven-day cache, then to the 228-name seed, and the run is marked
  `universe_cached`.
- **fetch** — 260 sessions of daily bars from Alpaca's consolidated `sip`
  feed, the request held sixteen minutes behind the clock (the free plan's
  route), in chunks, under a 900-second budget. Fewer than half the names
  answering is a feed outage and the run fails before spending anything
  else. SPY rides along for the scorecard's comparison line.
- **session** — from the bars alone: if half the names carry a bar for the
  expected session the market was open; if almost none do but the previous
  session is there, it was closed and the run republishes the previous
  session's tickets verbatim with its picks as plans that have had no
  session yet; between the two it is a thin night, `coverage_thin`, and the
  run goes on over the names that printed; fewer than that with the previous
  session absent too is an outage and the run fails.
- **breadth** — the Market Monitor columns and the regime: green (full
  size), yellow (half size, A+ only), red (no new longs; the open plans get
  a tighten-and-sell clause).
- **scan** — Bonde's own formulas: `c/c1 >= 1.04 and v > v1 and v >= 100000`
  and the dollar breakout `c - o >= 0.90 and v > 100000`, then the
  checklist over every hit: **2** not up two days in a row, **L** a linear
  prior leg, **Y** a young trend, **N** a narrow or negative prior day,
  **C** a tight base with at most one 4% breakdown, **H** a close near the
  high, plus range expansion and volume. A run of three up closes or a
  non-linear leg is a veto. A+ and A need 2 and H.
- **grade** — Claude reads the chart and the numbers for up to twelve
  bursts by mechanical grade and may only LOWER a grade, never raise it;
  the rulebook it reads is `knowledge/strategy.md`. No reply, or a refused
  key, leaves the checklist's grade standing and marks the night
  `claude_unavailable`.
- **plan** — every A-quality burst gets a plan sized from the configured
  account (default $10,000, 0.5% risk, 25% cap, four slots): entry zone,
  stop (the burst low, or the bar's midpoint when the low is too far,
  judged at the ticket's limit and refused past 4% there), shares sized at
  that limit, the ticket, the exits and the targets from an indicative
  entry. A trade is a plan with an order: a ticket the stop rule withholds,
  plans past the free slots or the equity, and a plan the account cannot
  size to a whole share, are listed as cut with the kind and the reason.
  An anticipation ticket is judged and sized at its limit the same way.
- **record** — the picks go to `docs/picks.json`; the open plans and the
  scorecard are computed from it and the bars.
- **publish** — `docs/data.json` is written and validated, then the email
  goes out. The workflow commits `docs/` back on exit 0, 2 or 3 (never a
  rehearsal), and `publish-dashboard.yml` asks GitHub Pages for a build,
  because a token push does not trigger one.

Exit codes are the workflow's contract: **0** clean, **1** failed before
publishing (the failure notice is mailed instead, when the failure came
after preflight and the delivery keys are there), **2** degraded but
published (a warning, not a red run), **3** published but the email failed.
Preflight checks every variable the run reads, for presence and for a value
the code understands, before anything is fetched or paid for.
A degraded night names its problem with one of seven words —
`universe_cached`, `coverage_thin`, `claude_unavailable`, `claude_partial`,
`chart_missing`, `email_failed`, `push_retried` — and the page has one fixed
sentence for each; the message the run recorded never reaches it.

`intraday.yml` is a button, not a schedule: it reads the previous evening's
watchlist and trades, asks Alpaca's snapshots whether a name has cleared its
level on volume already past yesterday's, writes `docs/live.json`, mails a
short *breakout in progress* note when one has, and commits nothing. Switch
its schedule on after the evening run has published ten nights in a row.

## One-time setup

Six repository secrets: `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`,
`ANTHROPIC_API_KEY`, `RESEND_API_KEY`, `RESEND_FROM`, `EMAIL_TO`. Four
optional repository variables: `SCAN_FEED`, `SCAN_UNIVERSE`,
`ACCOUNT_EQUITY`, `RISK_PCT`. GitHub Pages from `main` `/docs`. Until a
domain is verified at Resend, `EMAIL_TO` has to be the address the Resend
account is registered under, alone. `.env.example` explains each.

Before the first cron: dispatch `evening.yml` with **dry_run** ticked. That
is the one thing this repository cannot rehearse offline — a full-market
fetch from a runner — and its log says how long the fetch took against the
budget, how many names answered, how many bursts the scan found (Bonde's
median night is 239 over 6,500 names), and what the page would have said.
The artifact holds the record and the charts; nothing is committed or mailed.

## Run locally

```bash
pip install -r requirements.txt
cp .env.example .env              # single-quote every value
set -a; . ./.env; set +a
MPLBACKEND=Agg python -m src.pipeline evening --dry-run --tickers AAPL,AMD,NVDA,SPY
```

`--tickers` skips the directory; `--dry-run` mails nothing and records no
pick, but still fetches, grades and writes `docs/data.json`. Then open the
page from the repository root, `python -m http.server`, at
`/docs/index.html`. `git checkout -- docs/` puts the committed record back.

The regression net needs no keys and no network:

```bash
pip install -r requirements-dev.txt
pytest tests/ -q                            # every boundary is a double
node tools/chart_check.mjs                  # the chart's geometry, and a render
node tools/page_smoke.mjs --shots /tmp/shots   # the page against every fixture, read back
python tools/make_fixture.py --check        # the fixtures are what the pipeline writes
```

The fixtures under `tests/fixtures/page/` are records the real pipeline wrote
over a synthetic market through the same doubles the tests use, one per
state the page can be in (`full`, `degraded`, `notrade`, `yellow`, `red`,
`closed`), and `docs/data.json` on a fresh clone is the `full` one until the
first real night replaces it. The page smoke opens each in Chromium and
compares what it reads back with the record it was handed — every stock in
both stages, the search, the chooser and the rail on a phone, the keyboard,
deep links and Back, the old anchors, unknown routes and symbols, rapid
switching — then views the `full` record at three later instants for the
stale states, drops fourteen fields in turn (a burst without bars must say
*Chart unavailable*), and opens it once with no record at all.

## The record

`docs/data.json` (schema 2) is one object: `run`, `cover`, `breadth`,
`bursts[]`, `trades[]`, `beyond_cap[]`, `cash_budget`, `watchlist`,
`open_plans[]`, `scorecard`, `nights[]`, `account`, `rules`, `closest_miss`,
`observations` (the newest bar per recorded signal — the trades, the cut
names, the charted bursts, the anticipation list, the open plans — carried
for three weeks, for the page's Following shelf),
`app`, and `_contract`, which names every top-level key in a sentence.
`rules` is every module's constants nested by family, and `app.rules_version`
is a digest of that block, so two records produced by different numbers can
never be read as one. `docs/picks.json` is every published plan: ticker,
session, kind, the entry zone or trigger, the stop, the shares, the targets,
the ticket. It holds nothing about what anyone did with them.

**The scorecard is the rules' record, not yours.** Every pick is replayed
from daily bars alone, as a model: a ticket is booked filled only at the
next open, at or over its trigger and at or under its limit. A day that
opened under the trigger and reached it later, an open above the limit or
under the skip line that could still have filled a resting order, and a
fill-day low at or under the stop are *uncertain*: no fill is booked, no R
is scored, the plan keeps its slot in the model allocation, and the
scorecard counts them by reason. The published stop is one R on the whole
position; a half sold at +8% or at day 3 is "at least half" in whole shares
(2 of 3, 1 of 1) and every sale is weighted by the shares it sold;
everything settles by day 5.
It prints counts from the first night and rates only from twenty settled
plans (an uncertain plan never counts toward that), and SPY over the same
days is one comparison line beside it, not a benchmark. What it cannot
see — a fill you never took, slippage, a stop that gapped — it says so
under the tiles.

## What was cut, and why

The previous version carried a trade journal, a portfolio tracker, a broker
bridge with its own database, a ledger of forward returns on both bases, a
learning pipeline, a fidelity report against the canonical scan, a research
sidecar and a second daily run. All of it was tracking, and tracking was
work the reader was not going to do. What remains is the evening run, the
page, the email, and the one record that needs no hand: the picks file and
what the bars say happened to them.

## Layout

```
src/            pipeline.py (the run) · universe.py · market_data.py · clock.py
                scans.py · quality.py · breadth.py · watchlist.py · plan.py
                grader.py · charts.py · record.py · report.py
docs/           index.html · app.js · app.css · app-chart.js · app-map.js · app-follow.js · design-system/
                data.json · picks.json (the record) · charts/ (gitignored)
knowledge/      strategy.md (the rulebook the grader reads) · method.md (whose number is whose)
tests/          the suite, the doubles (fakes.py), the synthetic frames, fixtures/page/
tools/          make_fixture.py · page_smoke.mjs · chart_check.mjs · publish_dashboard.py
.github/        evening.yml · intraday.yml · tests.yml · publish-dashboard.yml · secret-scan.yml
```

Paper prices, one venue's prints, no slippage. Not investment advice.
