# SpicyStock

One evening run over an explicitly selected US-stock universe, one page that says what
to do next session and why, one email that says the same in fewer words. The
method is Pradeep Bonde's (Stockbee) momentum burst: reaction candidates
discovered by either the 4% or Dollar route, then judged for expansion out of
a quiet base, bought the next morning inside a narrow zone with
the stop under the burst bar, sold into strength over three to five days,
and only when breadth allows it. `knowledge/method.md` says whose number
every rule is; this file says what the software does with them. The dated
[reaction discovery source contract](knowledge/reaction-discovery.md) pins
the primary 2015 4% and 2017 Dollar formulas, their differing volume
boundaries, and the repository's separate precision/universe choices.

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

1. **The two clocks.** A record carries two different facts about time and
   the page keeps them apart, because freshness is not permission.
   **Publication** is the one thing the page computes: from the record's
   session and the browser's clock in ET it says *fresh*, *tonight's run
   pending*, *STALE · 1 session behind* or *STALE · N sessions behind*
   (the versioned XNYS schedule expected sessions), *market closed* or *degraded*, with one fixed sentence per
   problem kind. A stale page says *Do not place these orders*, points at
   the run log, and withholds every ticket from the action area, the plan
   and the order sheet, keeping the setups.
   **Action timing** is the run's own (`run.timing`, `src/timing.py`): the
   session the published plans are FOR and the instants its entry window is
   scheduled between, offset and all, so the page compares rather than
   derives and never writes a UTC offset of its own. The window is
   *upcoming*, *in progress* or *ended*; a record published before the field
   existed, or one whose block is half written, is *entry timing
   unavailable — research only*. One calculation answers both
   (`availability(data, now)`) and every surface that offers an action asks
   it: the compact area, a stock's action bar, the plan disclosure and its
   copy control, the ticket sheet, the comparison's ticket row and the next
   action. Timing narrows and never widens — a red night still leads with
   *no new longs*, a stale page is refused under a window that is open, and
   a window that ended leaves the setup, its evidence and the ticket the
   record published readable while offering none of it to place. The clock
   is re-read when the tab comes back, the window takes focus, the browser
   restores the page and on a bounded tick while visible, repainting only
   the words that changed — the chart, the lens, the comparison, an open
   disclosure and the reader's focus all stay where they were — and a copy
   asks again immediately before it writes.
2. **Explore**, the default view. The market in a line: the verdict, one
   of six sentences — *Trade next session. N A-quality bursts.* · *Trade small.
   N A+ bursts.* (a yellow regime) · *Stand aside.* (red) · *Nothing
   qualifies. Keep cash.* · *Market closed. Plans unchanged.* · *No verdict
   for <session>.* (the run failed before it published) — with the dek's
   breadth numbers, the regime chip and the size rule, the session, and the
   record's own call to action. Then two stage cards, **Bursts · N** (the
   range-expansion days the scan graded) and **Setting up · N** (the
   anticipation list: quiet, coiled names inside established momentum),
   each under its count saying how many of them carry a ticket — the line
   a phone keeps, because that is the stage's own action state —
   and inside the chosen stage one selectable card per stock with its grade
   and its status in the record's words — *ticket*, *ticket
   withheld*, *beyond the slot cap*, *beyond the configured equity*, *no
   whole share*, *no new longs*, *vetoed*, *no ticket*, *watch* — a search
   that finds a ticker in either stage and says when it switched, and on a
   phone a rail of cards with a *Choose stock* dialog. That dialog reaches
   every stock in the record, which is what it is for, so it says which of
   them the lens in front of the reader holds and which it hides: two
   counted groups, the hidden ones marked and listed second, and one line
   saying that choosing one of those widens the lens for that stock without
   changing the lens kept for next time. The first load shows
   Bursts when the scan found any, Setting up otherwise, and a chosen stage
   is never switched away from: an empty one says why it is empty. Each
   stage remembers its last chosen stock.
   Desktop **Cards** uses two matching, viewport-height panes. Search, counts,
   filters and sorting stay above the scrolling card list; the selected stock's
   full details scroll alongside it, including the normal-size chart and every
   disclosure. Wheel scrolling stays in its pane. Arrow/Home/End move card focus;
   Enter selects. A different stock starts at its identity; selecting the same
   stock or repainting it keeps the reader's detail position. Selection, search,
   Previous/Next and Back reveal the selected card only when needed, without
   snapping back during browse-only focus movement. The surrounding page remains
   scrollable, Map stays full width, and phones retain the horizontal rail,
   chooser and stacked details. Scroll positions are not persisted. When the
   detail pane is constrained, identity, badges and navigation use separate
   rows. The pane's own width controls this, so tools cannot squeeze the summary
   into a sliver. Narrow panes also keep ticket levels in two columns.
   A **lens** narrows the stage, each option a question asked of a field the
   run wrote and each wearing the count it will show: *A-quality* (the A and
   A+ grades this record archived), *All bursts*, *With ticket* (a ticket
   written into the published record) and *Following* (tonight's candidates
   already on this browser's shelf); Setting up has the last three. The
   first visit opens on A-quality when the record archived an A or A+ burst
   and on every burst otherwise, so the first screen is never empty — on the
   published 401-burst night that is 52 stocks rather than 401. A lens the
   reader chooses is remembered in this browser and never widened behind
   their back: an empty one stays empty, explains itself and offers one
   click out. *With ticket* is a reading of the record and never a
   permission — a stale, pending, failed or sample page still withholds
   every order, and says so beside the list. The heading keeps the stage's
   own total beside the subset (*bursts · 52 of 401*), the lens combines
   with the ticker search, and a search that matches a stock the lens is
   hiding says which lens is hiding it and offers to inspect it rather than
   claiming it does not exist. An optional sort offers the run's rank (the
   default), the session's gain and volume against the previous session;
   it changes the order only, every card keeps its published rank as its
   own label, and a stock the record has no measurement for sorts last
   rather than as a zero. One visible-candidate list feeds the cards, the
   map, the counts and the previous/next stepper beside the chosen stock.
   The bursts have a second view of the same list, a **map** of the
   session's gain against its volume relative to the previous session:
   every point the same selection as its card, the unmeasured listed
   beside it, position a measurement and not a return (the ratio is the
   scan's own for every burst, the dollar scan's days included; a record
   from before 12 Sep 2026 holds it for those days only in the checklist's
   block, and the page reads that copy and says so). The gain axis is
   linear; the volume axis is compressed, because the ratio has no upper
   bound and one name at 169× laid four hundred at about 1× on the pane
   floor. Every tick is labelled with the ratio it stands for, every burst
   is plotted at its own recorded ratio, the largest is never clipped, 0×
   sits on the axis line, and the map says so in words. Points still
   overlap, so a tap is resolved by distance from the tap and not by which
   marker was drawn last: when more than one is within a finger, a compact
   **nearby chooser** lists them nearest-first with their measurements and
   chooses nothing until you do. It is the design system's own `.sc-pick`,
   which was written from this page's panel and two others like it, so the
   page keeps the behaviour and the sheet supplies the look: a finger's 44px
   a row, the stock's name, what else the record knows about it, and the
   session's gain as the row's figure. It is a labelled popover, not a modal: the
   arrows move inside it, Escape closes it and hands the focus back to the
   stock you meant — never to the marker the browser happened to hit-test —
   tabbing out of it closes it, any selection made elsewhere closes it, and
   a *Nearby stocks* button beside the selection opens it from the keyboard.
   A tap on a point standing alone chooses it outright, and the keyboard's
   Enter takes the point it has focused. A table under the map carries every
   burst, plotted or not, and both the chosen point and every table row
   carry the same *Compare* toggle the cards carry, so two candidates can be
   pinned from the map without going back to the cards to find them again. On a four-hundred-burst night almost every point
   has a neighbour within a finger, so almost every tap asks: the cards, the
   search and the table are the one-step path to a stock you can name.
3. **The chosen stock.** A Burst first answers whether SpicyStock offers an
   entry for this exact setup. A usable published ticket shows its applicable
   session, buy-stop trigger, stop-limit limit, protective stop and suggested
   model shares directly, with **Copy order** and **Plan details**. It prints
   the recorded order fields and keeps material sizing explanations. A setup
   without a usable ticket says **No SpicyStock entry for this setup** and the
   actual grade, planner, budget, breadth or timing/publication reason. Expired
   plans remain inspectable as recorded history with no actionable levels or
   copy button in this summary. No client-side trading levels are calculated.
   Then one chart panel with one header (the symbol, its
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
   sessions. Each group of controls carries its own visible caption —
   *view* over the modes, *range* over the ranges — which is also the name
   assistive tech announces for it: *setup* is a mode AND a range, and an
   uncaptioned row of pills cannot be told from the one beside it. The mode
   and the range are remembered in the browser. The aim
   levels are printed beside the chart, and say so when they sit outside
   the visible range; a coil draws its box and its trigger and no burst
   candle; a name without archived bars says *Chart unavailable* and keeps
   its conditions. Four answers, each from the record's own sentences:
   *why this stock?*, *what would need to happen?*, *what invalidates it,
   or makes me wait?*, *principal risk or limitation*. Anticipation keeps its
   existing action area below those answers. The Burst action summary uses
   the shared `.sc-actionbar` with a compact four-field grid (two columns on
   a phone); browse cards keep their compact form. Four disclosures follow:
   the conditions (one tile per
   criterion with the measured value, his threshold and the verdict in
   words, then the base, the burst and the grade); the plan, sizing and
   order (the buy zone, whose top IS the ticket's own limit; the two skip
   lines, of which the upper one is the +4% day-2 threshold and not the
   limit; the stop and its basis; the shares sized at the limit — the
   highest fill the ticket permits, so the fixed quantity keeps the risk
   budget, the position cap and his 4% stop line at every fill it can take
   — the position, the planned price-to-stop risk, the aim, the hazards,
   and the order in Fidelity's field order with a copy button: a buy
   stop-limit with a one-triggers-the-other sell stop attached, and under
   it what the ticket enforces and what it leaves to the reader); the
   model exit guidance, dated; and the provenance (what Claude saw in the
   chart, the bars, the rules digest). Where the limit is under the day-2
   line the buy row says so in the plan's own words, and a burst no limit
   above its buy stop can hold a stop under keeps its card and has its
   ticket withheld, with the reason in the action area. Below the workspace, two more disclosures: **Tomorrow's
   tickets** (the model allocation over the configured sizing assumptions
   and the order sheet, every cut name explained) and **Everything the
   scan found** (every burst against the checklist — the six letters,
   range expansion and volume — sortable by score, each name a way to its
   card, the closest miss named above it).
   A **Show on chart** row under the plot marks the recorded evidence: the
   *Base* (the producer's own archived start, end and bounds), the *Burst
   day* (the session the record was published for, not whichever bar is
   last after a later observation is appended) and the *Prior day* (the
   previous archived observation before that signal, not the previous
   calendar day); a coil offers its *Box*. Choosing one draws a dashed
   column over exactly those sessions — in every mode, with the recorded
   bounds as edges when both already sit inside the drawn scale — and prints
   beside it the recorded measurement, the producer's own threshold and his
   verdict in words (*pass*, *partial*, *fail*, *not measured*). The marker
   is a position and nothing else: it widens no scale, moves no level and
   moves no label, so turning it on leaves every price where it was. The
   checklist tiles the record dated are the same mechanism — pressing
   *consolidation quality* marks the base, pressing *higher volume* marks
   the burst day — and a check the record carries no date range for
   (linearity, the trend's age, the run of up days) stays a tile and is
   never made clickable rather than a region being invented for it.
   Evidence outside the range on screen is offered (*Show recorded range*)
   and never taken silently; a name with no archived bars keeps the words
   and says there is no chart to sit on.
   **Focus evidence** explicitly frames the selected marker with nearby actual
   sessions: three context observations on available sides of the whole
   evidence, expanded to at least 21 actual observations where available.
   If that floor or a long base prevents useful horizontal zoom, Focus draws
   the plot 30% taller while retaining its recorded prices and plan levels.
   **Back to setup range** (or the prior 60/120 range) restores the exact normal
   date window and geometry. Normal chart heights remain 400px desktop and
   300px narrow/mobile. Focus never writes the saved Setup/60/120 preference;
   repeats do not compound, and another marker requires an explicit Focus.
   A new provenance-enabled Burst without ordinary browser bars offers
   **Load recorded chart**. Only that explicit press fetches its exact retained
   source object, with bounded decompression, source-hash and reference checks.
   It displays up to 120 sessions from that frame and identifies them as
   recorded source evidence. No eager evidence requests, market providers,
   later observations or fabricated bars are used. Failures leave the setup
   usable and offer a retry; legacy missing sources remain unavailable.
   Saved originals/history recovery keep their existing evidence. A chart loaded
   before a new save can be saved with that original; loading never rewrites an
   already saved chart. Compare can request a missing chart independently.
   [The chart-source contract](docs/actionability/README.md) describes validation
   and request/payload limits.
   A **Compare** toggle sits beside each card's selection button and in the
   chosen stock's own tool row — never inside either, so pinning neither
   chooses the stock nor follows it. Two pinned candidates of one stage and
   one published record open a comparison sheet: two balanced panels, each
   its own chart instance with its own price scale, its own dates and its
   own range sentence (the two are never drawn on one axis), one set of
   view and range controls driving both, and under them an aligned table of
   what the record says — grade and how it was graded, session gain, the
   volume ratio named for what it measures, the base or box, the trigger,
   the ticket limit, the stop and its published distance, the main
   qualifying reason, the principal concern, and the ticket or the exact
   reason there is none. A row the two differ on is marked; nothing
   declares a winner, and a value the record does not carry reads *not
   recorded* rather than as a failure. A third pin asks which of the two it
   replaces; a pin from the other stage is explained rather than refused. A
   pin the reader then narrows the lens past is never dropped: the chip says
   which lens is hiding it, the tray says it stays pinned because the
   comparison reads the record rather than the lens, and one click goes to
   it.
   On a phone an A/B switch shows one chart at a time while both symbols
   and both statuses stay on screen. *Open setup* and the same Follow
   action are offered from each side, and closing returns the reader to the
   stock, the lens, the scroll and the focus they left.
4. **Record.** **Open model plans** is every pick from the last five
   sessions walked from bars alone as a model: *day 3: sell half*,
   *stopped*, *not filled*, *uncertain* (the bars cannot say whether it
   filled), with the stop the rules would have moved it to; SpicyStock
   does not know what you hold. Then the bars-only scorecard (plans, fills,
   win rate, average R, SPY over the same days) and fourteen dots for the
   last fourteen exchange sessions: ok, degraded or missing; older recorded closure outcomes remain readable.
5. **Market.** Bonde's Market Monitor over usable fetched stock frames for the measured session:
   up and down 4% on volume, the 5- and 10-day ratios, the
   25%-in-a-quarter and 25%/50%-in-a-month counts, the share above the
   40-day average, the 10-day ratio over the last thirty sessions with his
   line drawn on it, and the regime verdict with every rule that fired.
   Thresholds are scaled to the measured universe against his ~6,500.
6. **Method.** Published run (coverage, grades, reads, delivery, timing,
   the run log), how to read the page, and the configured sizing
   assumptions every ticket was computed from.
7. **My setups.** A prominent peer to **Latest scan**, reachable even when
   empty. **Save setup** on cards, details and comparison entries freezes the
   exact signal in this browser. Discovery’s **Saved in this scan** lens is
   only a subset; My setups includes every local save regardless of filters,
   grade or membership. Legacy Following links and saved identity links remain.
   **I followed this plan** on a ticketed detail saves the original and records
   a browser-local choice of that exact published plan. It freezes the recorded
   order, dated session/horizon, evidence/plan/pick receipt and selection timestamp. It does not
   establish an order, fill, actual quantity, sale or personal P&L. Original signal,
   dated observed movement, coverage and the public model outcome remain separate.
   Exact receipt matches join the existing Record replay; the newest loaded model
   outcome is cached with its publication date, never replaced by an older record.
   There is no client-side fill/outcome engine. Uncertain remains uncertain.
   If the public five-session model window ends without an outcome loaded here,
   the page says so; it never invents a terminal result. Price observations retain
   their independent public horizon and basis caveats.
   Legacy **I took this setup** notes remain editable only where already present;
   migration never turns them into plan selection or execution evidence. Old saves
   lacking complete plan receipts explicitly cannot join an exact model outcome.
   Optional **Reference amount (USD)** remains a local note. A marking timestamp is
   not a purchase date. Amounts start unknown, use integer cents and clear back to unknown;
   existing suggested/reference whole-share values retain their meanings.
   Schema v4 migrates the existing Following key with preserved backups and
   unknown fields. Page writes use Web Locks on HTTPS to serialize tabs;
   conflicts follow lock acquisition order and removed items are not resurrected
   by stale edits. Without Web Locks the saved list is readable but writes fail
   explicitly. No cross-device synchronization is provided.
   **Find earlier setup** searches a public, source-addressed catalog on demand.
   It retains 21 calendar days, up to 84 distinct publications and 10,000 signals
   per publication, within 128 MiB. Originals load only when selected; chart
   evidence is at most the authentic 120 published bars. Absent charts stay
   absent. Revisions keep separate provenance. An unavailable original is never
   reconstructed from a later signal. Local saves do not expire with this window.
   Observed movement uses the dated original research close, not personal P&L;
   neither saving nor marking can create a ticket or change public strategy results.
8. **Sample data.** A record written by `tools/make_fixture.py` says so:
   a *Do not trade sample data* notice under the market bar naming the
   fixture, a *demo data* chip on the chart panel and the burst map, a
   *demo* chip on a followed card, and a chart-reader reply labelled
   simulated. Demo follows are kept under their own browser key.
9. **The next action**, under every view, and it names the session rather
   than saying *tomorrow*: *Plan for Mon 14 Sep: place the N orders in
   Fidelity before 9:28 AM ET* before the window, *The entry window for Mon
   14 Sep is in progress* inside it (with the last observed data timestamp
   kept in view, and live trigger and fill conditions said to be unverified
   here), *The entry window for Mon 14 Sep has ended* after it — where the
   cancellation is conditional, *if you submitted an order that did not
   fill*, and SpicyStock is said to place and cancel nothing. Otherwise
   nothing to place, no new longs, plans unchanged, or do not place these
   orders. 9:28 AM is the desk's own preparation reminder
   (`timing.PREPARE_BEFORE_ET`), never the cutoff.
10. **Check for updates**, one control beside the publication line. It
   re-reads the same static record and nothing else — no rescan, no grading
   call, no paid request, no dispatch, no polling. It reports unchanged (the
   served bytes are identical, so no Following observation is added), a
   newer session, a file for an EARLIER session (refused rather than applied
   backwards), the same session re-published on later bars (a revision of
   that trading day, not a second one), or a file it could not read or
   reach. A press supersedes one in flight and only the newest answer can
   land. A load hands back the stage, the stock and the search, keeps the
   theme, the lens, the chart's mode and range, every saved identity with
   its frozen evidence and a half-typed reference size — and closes a
   comparison rather than remapping its pins onto other stocks, saying so.

The email is the same record in fewer words: the verdict, the breadth line,
one block per trade with its order line and the day-order term, the plans
without a ticket and why, the open model plans' instructions, the alerts,
the problems and a link. Delivery failing never costs the page.

## How a night runs

`evening.yml` fires at 6:16 PM ET on weekdays (two crons, one per UTC
offset; the guard runs the right one) and again at 8:16 PM ET as a retry
that runs only if `docs/data.json` does not already carry tonight's
session. The run:

- **universe** — Nasdaq's security-name and industry classifier approximates
  common stock; it is not exact TC2000 membership. Directory price and volume
  never gate discovery. Biotech and foreign domicile remain flags. The
  seven-day cache and 228-name seed fallback remain explicit. Seeds can bypass
  classification; overrides and additions are counted. The 8,000-name capacity
  safeguard retains seeds, ranks any remaining tail by directory dollar volume,
  and counts every cut. A capacity cut degrades coverage; it can lose a breakout
  and is not a strategy rule. It does not bind on the archived September 15
  directory: 4,797 selected stocks versus 3,039 under the old quote gates.
- **fetch** — 260 sessions of daily bars from Alpaca's consolidated `sip`
  feed, explicitly split-adjusted, not raw or dividend-adjusted. The request
  remains sixteen minutes behind the clock, in chunks, under a 900-second budget.
  SPY rides along for the scorecard. The archived population expansion changes
  estimated initial SDK batches from 31 to 48, before pagination/retries; it does
  not raise the timeout or the twelve-call chart-reader cap. Actual calls can
  vary with qualifying candidates within that cap; this milestone used none.
- **session and coverage** — XNYS owns expected session dates and hours;
  missing bars on an expected session are outage/coverage evidence, never proof
  of a holiday. Each frame needs the evaluated session and the required previous
  session with readable OHLCV. Fewer than half the intended stocks with usable
  session bars refuses publication before grading; the denominator excludes SPY.
  At least half but less than all is degraded, as is any capacity cut or scan/
  quality error. A fully evaluated selection can be complete without being the
  complete listed market. The existing $3 session-close policy now reads actual
  cent-rounded bars, with seed/explicit exemptions preserved; actual scan volume
  remains the scanner's rule. Known non-session runs skip before universe/provider work and preserve the prior publication.
  No-bar responses, failed batches, budget-unfetched names, stale frames, gaps,
  unreadable pairs and repaired duplicates are distinct in `run.coverage`.
  Counts reconcile from selection through measured burst/dollar/both/neither and
  quality outcomes; each reason carries a bounded sample and membership digest.
  Below-threshold failures retain their population on `RunReport.input_coverage`
  and in the run log, leaving the last published record intact.
  `run.universe` records the source, capture timestamp, snapshot hash, selection
  identity, exclusions and the snapshot date's relation to the scan session.
  A contemporary or cached directory never proves historical point-in-time
  membership; pinned sessions carry that limitation. No survivorship-bias-free
  historical backtest is claimed. `run.input_basis` records the feed, split
  adjustment and expected/evaluated sessions; recovery copies the original run.
  Older records without these fields remain explicitly unknown on the page.
  See `docs/input-truthfulness/README.md` for conservation equations and offline impact.
  Method shows the ledger concisely, and incomplete empty results are qualified
  beside the verdict and empty-state text.
- **breadth** — the Market Monitor columns and the regime: green (full
  size), yellow (half size, A+ only), red (no new longs; the open plans get
  a tighten-and-sell clause).
- **scan** — the repository's recorded formulas: `c/c1 >= 1.04 and v > v1 and v >= 100000`
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
  `claude_unavailable`. Each reaction row archives a versioned `discovery`
  block from those same scan rules and measurements: `burst`, `dollar` or
  both, with applicable and explicitly inapplicable rules kept apart. A
  dollar-only candidate does not require a +4% close-to-close gain. Quality
  can still be lowered for independent chart/checklist evidence. Recognized
  contradictory replies are rejected whole into mechanical fallback without
  a retry; their score and explanation are not published as chart judgement.
  This narrow text guard is not a semantic correctness guarantee. The reader
  result archives the discovery version and a SHA-256 of the initial system
  and user text; transport, cache prefix and down-only clamping remain intact.
  See `tests/fixtures/grading/history-audit.json` for the bounded, manually
  reviewed historical audit. Old published reasons and grades are unchanged.
  The page's primary explanation reports the recorded checklist and grade
  outcome. Original reader reason, risk and entry commentary remain inspectable
  in Provenance and are labelled unverified; recorded checklist criteria govern
  thresholds and only the published plan defines order terms. Saved and recovered
  originals carry the same qualification. This presentation boundary does not
  fact-check arbitrary prose, regrade a result or rewrite a historical receipt.
- **plan** — every A-quality burst gets a plan sized from the configured
  account (default $10,000, 0.5% risk, 25% cap, four slots). Four prices it
  keeps apart, because they are four rules: the **trigger**, a buy stop at
  the burst close; the ticket's **limit** (`plan.burst_limit`), the day-2
  ceiling narrowed to the highest price at which the structural stop is
  still inside his 4% line,
  `min(close +4%, floor_to_cents(stop / (1 - plan.MAX_STOP_PCT/100)))` over
  the burst low then the bar's midpoint; the **day-2 threshold**
  (`day2_spent_above`, the close +4%), above which his follow-through is
  already spent — the skip rule, never the order's limit; and the
  **indicative entry** (`planned_entry`), the close +1% capped at that
  limit, which the exits and the targets are quoted from and which is
  never a fill. The shares are sized at the limit. A trade is a plan with
  an order: a setup no limit above its buy stop can hold a stop under (the
  synthetic 4% level never buys a ticket, and a limit landing ON the
  trigger is a ticket with no band), plans past the free slots or the
  equity, and a plan the account cannot size to a whole share, are listed
  as cut with the kind and the reason. An anticipation ticket is judged
  and sized at its limit the same way.
- **record** — the picks go to `docs/picks.json`; the open plans and the
  scorecard are computed from it and the bars. Suggested shares are model
  sizing, never shares bought. New plans carry a versioned evidence reference.
- **publish** — source, discovery, checklist, reader, regime and plan evidence
  must verify before the serialized data/picks pair replaces the previous
  publication. Contradictions fail closed. Then the email
  goes out. The workflow commits `docs/` back on exit 0, 2 or 3 (never a
  rehearsal), and `publish-dashboard.yml` asks GitHub Pages for a build,
  because a token push does not trigger one. It then fetches every file the
  page loads -- the HTML, both records, each script and stylesheet, the
  vendored design system -- and fails unless the public bytes are the
  commit's; the list is read off `docs/index.html`, not kept beside it.

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

One tool is not a check but a reading. `python tools/entry_limit_study.py
[record.json ...]` puts three readings of every burst in an already-written
record beside each other: the **retired** fixed ceiling (the close +4%,
`plan.ENTRY_ABOVE_PCT`, with the stop cascade judged there), which is no
longer in `src/` and lives in the tool alone; **production**, which is
`plan.burst_plan()` itself and which `verify()` reproduces down to the share
count, the action and the money; and an **oracle**, the constrained ceiling
re-derived in the tool from the spec and held against what production wrote,
so a drift in either raises rather than prints. The oracle never reads the
synthetic `max_stop` fallback, so that level can rescue nothing, and it
admits a ticket only where `stop < trigger < limit` holds at the rounded
ceiling — strictly under and strictly over, because a limit at the buy stop
is a ticket with no band. It reports candidate coverage, the retired
ceiling's stop-rule rejections, what production admits and refuses (by
refusal), and what inputs are missing, each kept apart from the regime,
grade and budget exclusions, and it counts what the narrower limit carried
with it. It changes no rule, writes nothing, reads no forward return, and is
not a backtest or a claim about either ceiling.

The fixtures under `tests/fixtures/page/` are records the real pipeline wrote
over a synthetic market through the same doubles the tests use, one per
state the page can be in (`full`, `degraded`, `notrade`, `yellow`, `red`,
`closed`, `empty`, `partial`, `early`), plus two sequels of the `full` night (`next`, `revised`) run over
the docs that night wrote, so a setup followed then can be read against a
genuinely newer record: `next` is the same market one session on, where the
ticket and the withheld setup have left the record, one burst has burst
again and the coil has broken out; `revised` is that same session re-run on
later bars, one close a few cents off — a correction and not another trading
day. `docs/data.json` on a fresh clone is the `full` one until the
first real night replaces it. The page smoke opens each in Chromium and
compares what it reads back with the record it was handed — every stock in
both stages, the search, the chooser and the rail on a phone, the keyboard,
deep links and Back, the old anchors, unknown routes and symbols, rapid
switching — then views the `full` record at three later instants for the
stale states, drops fourteen fields in turn (a burst without browser bars must
offer its matching retained source or say *Chart unavailable*), and opens it
once with no record at all.

## The record

`docs/data.json` (schema 2) is one object: `run`, `cover`, `breadth`,
`bursts[]`, `trades[]`, `beyond_cap[]`, `cash_budget`, `watchlist`,
`open_plans[]`, `scorecard`, `nights[]`, `account`, `rules`, `closest_miss`,
`observations` (every saveable published signal's own identity and 21-day
window, plus up to 20 real dated observations per symbol from frames already
fetched; missing frames retain dated real observations),
`app`, and `_contract`, which names every top-level key in a sentence.
`rules` is every module's constants nested by family, and `app.rules_version`
is a digest of that block, so two records produced by different numbers can
never be read as one. `docs/picks.json` (schema 2 for new writes) is every published plan: ticker,
session, kind, the entry zone or trigger, the stop, the shares, the targets,
the ticket. It holds nothing about what anyone did with them.

New candidates carry provenance v1: a stable evidence ID, exact source/read-view
digests, discovery and mechanical-check digests, chart-reader input/result or
explicit fallback, breadth eligibility and plan inputs/output. The same ID
travels with tickets, persisted picks, immutable recovery and new saved originals.
The detail disclosure says **Evidence recorded** and whether a ticket existed;
technical IDs stay inside a further disclosure. Local annotations do not alter it.

Full frames and exact reader inputs are deduplicated under `docs/evidence/`,
outside the initial page payload. The chart's optional source reader verifies
one retained frame's identity; it does not replay the recommendation chain.
Full verification calls the existing strategy
functions offline; it never repairs evidence or requests providers/models.
Schema-1 picks retain their original fields; September 11/14 histories are not
rewritten. Missing legacy provenance is explicitly partial/unknown. See
[the provenance contract](docs/provenance/README.md) for canonicalization,
retention bounds, examples and measured impact. To verify a retained publication:

```sh
python tools/verify_provenance.py --record docs/data.json --picks docs/picks.json --objects docs/evidence
```

**The scorecard is the rules' record, not yours.** It counts every retained
published Burst and Anticipation ticket from the prior 60 exchange sessions
plus the current publication. Current plans await their first session. Missing
or stale observations, uncertain fills, unreadable walks and unfilled orders
stay in the total; none is silently converted to a loss, a win or zero R.
Non-ticket setups and browser-local selections never enter that population.
File-capacity and malformed-record limits are disclosed; this is not an
unlimited inception-to-date record.

The existing daily-bar replay is unchanged: a ticket is booked filled only at
the next open, at or over its trigger and at or under its limit. Ambiguous
trigger timing or fill/stop ordering remains uncertain. The published stop is
one R on the whole position; a half sold at +8% or at day 3 is at least half in
whole shares, and every sale is weighted by its quantity. With complete usable
bars, everything settles by day 5. Missing evidence never establishes that exit.
Only those five sessions feed the scorecard; later data gaps cannot erase its
resolved result. A stop gap is modeled at the open, not at the stop price.

It prints counts from the first night and rates only from twenty settled
plans. Wins, losses and breakeven reconcile to that explicit resolved denominator;
mean and median R use the same plans. Breakeven is the existing R rounded to two
decimals equalling zero. SPY is a percent-price comparison over matched entry/exit
dates, with its own pair count, not portfolio performance or excess R. Small
samples remain prominent, and twenty observations alone do not establish an edge.
Fees, spread, tax, actual executions and subsequent split rebasing are not measured.

[The scorecard contract](docs/scorecard-contract.md) documents all states,
retention, price basis, regime, versioning and the offline analysis command.
`tools/scorecard_analysis.py` uses the same replay and summary for complete
partitions by original rules version, burst/dollar/both, grade, regime, kind and
reader source. Exact original publication receipts establish attribution;
missing metadata stays unknown. These partitions do not select a preferred
strategy or change the aggregate. Legacy website summaries retain their recorded
values and explicitly admit incomplete coverage accounting.

## What was cut, and why

The previous version carried a trade journal, a portfolio tracker, a broker
bridge with its own database, a ledger of forward returns on both bases, a
learning pipeline, a fidelity report against the canonical scan, a research
sidecar and a second daily run. All of it was tracking, and tracking was
work the reader was not going to do. What remains is the evening run, the
page, the email, and the one record that needs no hand: the picks file and
what the bars say happened to them.


### Exchange-session basis

`src/sessions.py` is the single authority: **XNYS (New York Stock Exchange)**,
from pinned [`exchange_calendars` 4.13.2](https://pypi.org/project/exchange_calendars/4.13.2/).
It works offline after installation and supplies historical holidays, exceptional
closures and shortened hours. [NYSE hours](https://www.nyse.com/markets/hours-calendars)
are the exchange reference. The calendar range is explicitly 1990–2035; requested sessions also need
their lookback and plan dates inside it. Requests without that context fail instead of substituting weekdays. Future schedules can change.

The newest completed session reaches its **scheduled close plus 15 minutes**;
this policy is separate from the exchange close and does not guarantee extended-hours
bar finality. Plan day 1 and subsequent dated exits enumerate actual sessions.
The entry window remains the strategy's first 30 minutes after the scheduled open.
All instants carry America/New_York offsets; no UTC offset is hard-coded.

A known holiday/weekend evening or intraday run logs `no_session`, publishes
nothing, preserves every previous file and sends no duplicate signal email. An
incomplete evening session logs `session_incomplete`. `SCAN_SESSION_DATE` means
requested exchange session: a pinned non-session is a precise preflight failure.
The workflow's cron slots are unchanged; `published=false` prevents persistence,
and skipped runs do not upload the previous record as a new artifact. The retry
may log the same skip, still without any provider work.

`run.calendar` records calendar schema, exchange/library/version, measured,
previous and next applicable session, scheduled opens/closes, shortened status,
and completion policy. Its ±45-calendar-day schedule lets the browser count real
sessions without independent holiday arithmetic. Beyond that window, or on old
records lacking provenance, freshness is unknown and actions are withheld. Old
records and saved setups retain their original timing and limitations. New saves
freeze their original timing evidence; later observations do not replace it.

Deterministic cases include 2024-08-26 (ordinary Monday), Aug 31/Sep 1 (weekend),
Sep 2 (Labor Day), Aug 30→Sep 3 (adjacent sessions), Nov 29 (13:00 ET close),
Dec 2 (the following session), Mar 8→11 and Nov 1→4 (DST offsets). Historical
1992-11-27 closes at 14:00 ET, proving shortened hours are not a fixed 13:00 rule.
The `closed` fixture is an unchanged Sep 4, 2026 publication viewed on Labor Day;
`early` is the Nov 27, 2024 signal for Black Friday. These are offline fixtures,
not historical point-in-time universe or profitability evidence.

## Layout

```
src/            history.py (public recovery and coverage)
                provenance.py (immutable evidence receipts and offline verification)
                pipeline.py (the run) · inputs.py (population ledger) · universe.py · market_data.py · clock.py
                scans.py · discovery.py · quality.py · breadth.py · watchlist.py · plan.py
                sessions.py (pinned XNYS sessions, actual hours and timing provenance)
                timing.py (which session a plan is for, and when its window is over)
                grader.py · charts.py · record.py · report.py
docs/           index.html · app.js · app.css · app-chart.js · app-map.js · app-follow.js · design-system/
                data.json · picks.json (the record) · charts/ (gitignored)
                history/ (recovery) · evidence/ (deduplicated source objects)
knowledge/      strategy.md (the rulebook the grader reads) · method.md (whose number is whose)
tests/          the suite, the doubles (fakes.py), the synthetic frames, fixtures/page/
tools/          make_fixture.py · page_smoke.mjs · chart_check.mjs · publish_dashboard.py
                verify_provenance.py · provenance_impact.py (offline receipts and measurements)
                entry_limit_study.py (read-only: the retired ceiling, production and an oracle over an archived record)
.github/        evening.yml · intraday.yml · tests.yml · publish-dashboard.yml · secret-scan.yml
```

Paper prices, one venue's prints, no slippage. Not investment advice.

## Continuity development

`python tools/backfill_history.py` builds `docs/history/` from existing published
v2 Git records without provider or chart-reader calls. The evening pipeline
maintains the catalog from final published bytes; it does not read local saves.
Initial backfill dates: September 11 and 14, 2026; September 11 has two distinct
publications. Both carry ATEC's original chart and neither carries VICR's.
`npm ci && npm run test:continuity` runs offline DOM/store regressions. This
is not browser or layout acceptance; use the existing Playwright checks too.
The original two records are gzip fixtures under `tests/fixtures/continuity/`.
