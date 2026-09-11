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
run and printed verbatim.

**Fourteen days.** Week one is paper: read the page every evening, place the
orders in Fidelity's paper view or not at all, and read the open-plan rail
each morning. Week two is the $10,000 account at the default 0.5% risk
(0.25% is the more conservative end of his band and one variable away). Day
fourteen is the decision, made on the page's own reliability row and its
bars-only scorecard, not on a feeling.

## What the page says

Top to bottom, in the order a reader needs it:

1. **The verdict.** One of six sentences: *Trade tomorrow. N A-quality
   bursts.* · *Trade small. N A+ bursts.* (a yellow regime) · *Stand aside.*
   (red) · *Nothing qualifies. Keep cash.* · *Market closed. Plans
   unchanged.* · *No verdict for <session>.* (the run failed before it
   published). The dek carries the breadth numbers and the size rule.
2. **The status chip.** The one thing the page computes: from the record's
   session and the browser's clock in ET it says *fresh*, *tonight's run
   pending*, *STALE · 1 session behind* (closed or failed, it cannot tell),
   *STALE · N sessions behind* (never a closure: no two US market holidays
   are adjacent), *market closed* or *degraded*, with one fixed sentence per
   problem kind. A stale page says *Do not place these orders* and points
   at the run log.
3. **Is it a night to trade?** Bonde's Market Monitor over every stock that
   printed today: up and down 4% on volume, the 5- and 10-day ratios, the
   25%-in-a-quarter and 25%/50%-in-a-month counts, the share above the
   40-day average, the 10-day ratio over the last thirty sessions with his
   line drawn on it, and the regime verdict with every rule that fired.
   Thresholds are scaled to the measured universe against his ~6,500.
4. **What to do tomorrow.** One card per A-quality burst, ranked: the
   annotated chart (the base box, the burst bar, the buy zone, the stop, the
   +8%/+20% ruler, the last sixty or hundred and twenty sessions), the buy
   zone and the two skip lines, the stop and its basis, the shares and the
   position, the dollars at risk, the aim, the hazards, and the order in
   Fidelity's field order with a copy button: a buy stop-limit (stop at the
   burst close, limit at the ceiling) with a one-triggers-the-other sell
   stop attached. Beside it the exits, dated, and what Claude saw in the
   chart. **What you hold** is every pick from the last five sessions
   walked from bars alone: *day 3: sell half*, *stopped*, *not filled*,
   with the stop the rules would have moved it to. On a phone that rail
   comes first. Then the budget and the order sheet.
5. **Alerts.** The anticipation list: quiet, coiled names inside
   established momentum, each with a buy stop over its box, a limit, a stop
   under the last three lows and a ticket. Set them before the open.
6. **Everything the scan found.** Every burst against the checklist — the
   six letters, range expansion and volume — with the measured value, his
   threshold and the verdict in words; sortable by score; the closest miss
   named above it.
7. **The rules' record.** The bars-only scorecard (plans, fills, win rate,
   average R, SPY over the same days) and fourteen dots for the last
   fourteen evenings: ok, degraded, closed, missing.

The email is the same record in fewer words: the verdict, the breadth line,
one block per trade with its order line, the open-plan instructions, the
alerts, the problems and a link. Delivery failing never costs the page.

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
- **plan** — every A-quality burst gets a plan sized from the account
  (default $10,000, 0.5% risk, 25% cap, four slots): entry zone, stop (the
  burst low, or the bar's midpoint when the low is too far, refused past
  4%), shares, the ticket, the exits and the targets. A trade is a plan with
  an order: plans past the free slots or the equity, and a plan the account
  cannot size to a whole share, are listed as cut with the reason.
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
compares what it reads back with the record it was handed, then views the
`full` record at three later instants for the stale states and once with no
record at all.

## The record

`docs/data.json` (schema 2) is one object: `run`, `cover`, `breadth`,
`bursts[]`, `trades[]`, `beyond_cap[]`, `cash_budget`, `watchlist`,
`open_plans[]`, `scorecard`, `nights[]`, `account`, `rules`, `closest_miss`,
`app`, and `_contract`, which names every top-level key in a sentence.
`rules` is every module's constants nested by family, and `app.rules_version`
is a digest of that block, so two records produced by different numbers can
never be read as one. `docs/picks.json` is every published plan: ticker,
session, kind, the entry zone or trigger, the stop, the shares, the targets,
the ticket. It holds nothing about what anyone did with them.

**The scorecard is the rules' record, not yours.** Every pick is replayed
from bars alone: a burst ticket fills at the next open if the open sits
inside the zone (or at the trigger if the day trades up through it), an
anticipation ticket at its trigger; the published stop is one R; a half
sold at +8% or at day 3 is half the position; everything settles by day 5.
A fill at the trigger is walked from the fill: on that day only the close
is known to have printed after it, so a low under the stop that morning is
not a stop-out and a high before the fill is not a sale.
It prints counts from the first night and rates only from twenty settled
plans, and SPY over the same days is one comparison line beside it, not a
benchmark. What it cannot see — a fill you never took, slippage, a stop
that gapped — it says so under the tiles.

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
docs/           index.html · app.js · app.css · app-chart.js · design-system/
                data.json · picks.json (the record) · charts/ (gitignored)
knowledge/      strategy.md (the rulebook the grader reads) · method.md (whose number is whose)
tests/          the suite, the doubles (fakes.py), the synthetic frames, fixtures/page/
tools/          make_fixture.py · page_smoke.mjs · chart_check.mjs · publish_dashboard.py
.github/        evening.yml · intraday.yml · tests.yml · publish-dashboard.yml · secret-scan.yml
```

Paper prices, one venue's prints, no slippage. Not investment advice.
