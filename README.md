# SpicyStock

The active [product goal and milestones](PRODUCT_GOAL.md) are a usable morning
trading workspace for a $2,000 cash account in Chicago time: trustworthy data,
clear conditional setups, bounded sizing and an explained wait when nothing
qualifies. Milestone 1 is live with morning preparation, combined cash
allocation, known corporate-action exclusions and dependable session handling.
Verified morning observations and the compact reader are deployed; reliable
on-time delivery and broader event coverage remain open. The
[implementation tickets](https://github.com/spicyChicken59/SpicyStock/milestone/1)
track this work and the practical first-trade workflow. The original October 9
evening publication exposed a missing ZIM takeover exclusion; the source-backed
correction and its production verification are tracked in
[PR #115](https://github.com/spicyChicken59/SpicyStock/pull/115). A successful
real-money trade has not yet been recorded. Mo authorizes continued
milestone releases with tests, independent review and public verification. The
hourly **Build SpicyStock milestones** ChatGPT task supports resuming that work;
see the goal's continuation contract.

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

The page is the product. It is generated and static: `docs/data.json` supplies
the latest decision, with separate read-only historical evidence and optional
browser-local saved research. It displays recorded gate counts and entry timing.
The regime, the grades, the
share counts, the order tickets, the exits, the record — is written by the
run and printed verbatim. It is an implementation of the method with
explicit assumptions (the archived rules, and `knowledge/method.md` on whose
number each is), not a proven edge, and it knows nothing about what anyone
holds: every plan it follows is a model of the published ticket.

**Historical validation.** The retained rebuild sample contains 13 publications
across 11 sessions, with no published reaction ticket or settled plan. It does
not establish an executable trading edge or a timetable for funding an account.
The $10,000 / 0.5% / 25% / four-slot account is a model assumption. Twenty settled
plans would make a rate readable, not certify an edge. Read the
[versioned evidence and blocked claims](docs/input-truthfulness/2026-09-28-validation-review.md)
and [selected operating contract](docs/input-truthfulness/2026-09-28-operating-contract.md).
October 2026 added the first outcomes on real bars, none of them an edge
claim. Run 6 reproduced the red reading of 24 and 25 September on a later
retrieval of every intended stock (10-session ratios 0.93 and 0.89 against
the published 0.94 and 0.89); the signal-outcome study, which runs the
production plan rules over every archived burst with the regime gate, the
slot cap and the reader removed (and, outside the admitted stratum, the
grade's or the veto's own refusal), found every stratum losing on the red
nights -- the admitted stratum's exploratory rows −0.235R per settled ticket
over 202 on 2 October and −0.189R over 267 on the 6 October re-read, the
whole stratum −0.204R over 272 with the five confirmatory tickets settled
since the freeze, all at −1R; a night read before its tickets' fifth session
leans toward losses -- and the owner's backtest over 158 archive sessions (100
yellow, 58 red, no green) wrote 99 half-size A+ tickets, of which 44
settled, 16 won, 27 lost and 1 was even, +3.72R net, the reader not run. The
Record view replays those nights one at a time from
`docs/historical-findings.json`, which `tools/build_historical_findings.py`
builds from the committed evidence files and binds to their digests; the
page prints its figures as the file writes them and adds no figure of its own.

## What the page says

**Morning desk.** The masthead's preparation button opens the published session's entry
window in America/Chicago, publication and market state, separate reaction and
setting-up ticket counts, and the account assumptions beside the next step.
The personal reference is a $2,000 cash account, $10 base planned risk and a
$500 per-name cap before existing strategy reductions. An older publication
sized for another account says so; the published tickets retain their quantities.
Optional settled cash begins unknown and stays in this tab. A separate cash-aware
preview uses that entered cash, an explicit fees buffer, and an optional smaller
whole-share quantity. It caps the calculation at the published shares and the
cash affordable at the entry limit, then shows principal, total cash, planned
limit-to-stop risk and remaining cash. Decimal amounts are calculated in integer
cents. Unknown or invalid inputs, unavailable plans, event restrictions and
mismatched account assumptions cannot produce a current personal preview.

Each preview considers one plan independently and reserves no cash. Account for
other orders and broker holds before entering available settled cash. Changing
plans clears the fees and quantity inputs; a new session clears cash too, and a
reload clears these preview inputs. Published copy controls still copy the original model
quantity, clearly identified beside the preview. The calculation does not submit
an order or verify a balance. Preparation checks do not establish live quotes,
news coverage, broker buying power or execution, and cannot turn an unavailable
setup into an order. Planned price-to-stop risk excludes fees, gaps and slippage.

**Private broker handoff.** A calculated preview can be explicitly saved as a
separate personal draft for broker review. Its chosen whole-share quantity stays
within the admitted published quantity and entered cash; trigger, limit, stop and
dated exit instructions retain the published terms. The draft keeps the exact
publication and plan identities, selected terms, cash and fees on this device.
Its personal readback uses the chosen quantity for entry and planned protection.
The original published ticket remains separate. Copying is only a clipboard
operation, not a broker order format or a confirmation of execution.

The dated exit schedule is labelled as archived model wording. A separate
whole-share reference applies the existing model's at-least-half convention to
the personal draft, or to explicitly reported remaining holdings after reporting
begins. It rounds up: one of one share or two of three. A one-share position
cannot be partly exited in whole shares. Unknown fills or exits leave holdings
unknown; zero reported remaining shares leaves the schedule as history. This
reference arithmetic does not decide whether another exit is due, infer broker
fractional-share support or resize the saved schedule. Review prior exits and
choose feasible quantities at the broker before acting.

New preparation and copying recheck the current publication, account, entry
window and event restrictions. A superseded or expired draft remains readable.
Manual broker reports remain editable afterward: submitted quantity, cumulative
entry fills and average price/time, cancelled remainder, cumulative exits and
average exit price/time, actual entry/exit fees, and the broker-reported
protective quantity. Actual submissions, prices and
times can differ from the draft and are labeled as deviations. They do not
rewrite the strategy or the original terms. Copying, saving and market prices
never create a reported fill.

Blank values mean unknown. Remaining holdings require both entry fills and
exits, including an explicit zero when no exit has occurred. Filled plus
cancelled shares cannot exceed the quantity reported submitted; exits cannot
exceed reported fills. The protective quantity is compared with reported shares
remaining, not cumulative purchases. A quantity match does not verify an active
broker stop. Once reporting has begun, clearing fields to unknown cannot revive
the draft as a new entry to copy. Corrections are explicit; stale revisions
cannot overwrite a newer report. Dates require an explicit time-zone offset
and are displayed in Chicago time.

The private store holds at most 100 records and 1 MiB, never silently evicts
records, and serializes writes with browser Web Locks. Unavailable, unreadable
or future-version storage is preserved and reported; it does not imply no
holdings. Saved drafts and reports persist across reloads, but clearing this
site's browser data removes them. They are not uploaded, backed up in the cloud,
added to model performance, or used to infer buying power. The handoff creates
no broker connection, reserves no cash, and neither places nor cancels a
protective order.

**Independently executed research trade.** A verified retained research row also
offers **Record an already executed trade**. This opens a blank private report
without saving anything. The first explicit save requires a positive quantity
reported filled and the corresponding submitted quantity; prices, fees, times,
exits and protection remain unknown until entered. Research quantities and
prices are never filled in as actual broker facts.

The record preserves its original publication, cohort, evidence and baseline
admission status. Both admitted and withheld comparison rows can be recorded
after the entry window, including a trade for which no personal draft was saved.
Reported quantities may differ from the hypothetical allocation. An existing
record for the same publication and evidence cannot be duplicated or overwritten
by this creation path; its existing correction form remains available.

This report-only kind contains no draft, cash assumption or order payload, and
never gains entry-copy or preparation authority. It shows actual reported
holdings/protection and, when reconciled, the same personal result described
below. No original model exit schedule is inferred for an independent execution.
Initial creation rechecks the verified source inside the save operation. Later
corrections retain the frozen original evidence even after publication replacement
or expiry. Modal close/reopen preserves unsaved input; cancelling the new unsaved
report is an explicit action. Reports remain private on this device.

The verified research journal also offers this blank report for an original
cohort retained after a newer scan arrives. The loaded journal must match the
current publication, and the selected row must match its exact original cohort
and evidence. A refreshed journal requires an explicit reopen before the first
save; reopening the same verified original preserves unsaved broker inputs.
Different cohort revisions sharing an original publication/evidence identity
open the same private record. Conditional model outcomes never supply fill facts.

**Personal completed-trade result.** A separate, user-reported result requires
positive entry fills, all filled shares exited, and submitted shares fully
reconciled as filled or cancelled (including an explicit zero cancellation).
Both average prices, actual entry/exit fees and latest entry/exit times must be
reported. Blank costs remain unknown; explicit zero fees means no reported fee.
The draft's estimated fee buffer is never substituted for actual costs.
Partial exits retain their facts without estimating a realized cost basis.

Gross result is filled shares multiplied by the difference between average
exit and entry prices; net subtracts the reported entry and exit fees. Prices use at most six
decimal places and actual fees use cents. Integer arithmetic retains exact
microdollars, rounding only the displayed amount to cents; a nonzero sub-cent
gain or loss is named explicitly. Corrections recompute this personal result.
It is not broker-verified, tax accounting, settlement confirmation, model
performance or evidence of a strategy's future returns.

Existing version-1 and version-2 private records remain readable. Missing
version-1 result fields stay unknown; recorded version-2 prices and costs retain
their validation and values. Reading adapts them in memory without rewriting
storage. An explicit successful save writes version 3, retaining the original
identities and previously reported facts and distinguishing planned handoffs
from independent research reports. Failed writes retain prior and proposed
recovery bytes; unknown versions remain untouched. Upgrading does not expand
the shared 100-record / 1 MiB limit.

**Local private backup.** In Private broker handoffs and reports, **Download
private backup** saves the exact supported store bytes to a file on this device.
It includes private broker facts; keep the file private. Downloading does not
change the saved records, migrate older versions or upload anything. Unsaved
form edits are not included. This is separate from the emergency recovery file
containing prior/proposed payloads after a failed write.

**Restore private backup** reads a bounded local file and previews its validated
record count, kinds and original dates. Only a separate explicit restore click
writes it, and only into an empty, readable destination. Existing, unreadable
or concurrently changed storage is refused without overwrite. Choosing,
previewing, cancelling or rejecting a file preserves the mounted editor and
unsaved input; restore cannot replace a dirty or new unsaved report.

Supported legacy bytes, unknown broker facts, decimal strings and original
source references are preserved. Restore grants no new order-copy authority;
independent reports remain report-only, and planned handoffs retain all ordinary
current-publication checks. The shared 100-record / 1 MiB limit, Web Lock,
readback and failure recovery still apply. There is no cloud backup or sync,
and public data need not be available to access this local recovery path.

The next-action message counts the same published reaction and anticipation
tickets as the desk, including tickets retained for inspection after cutoff.
The wait explanation separates the reaction review gates from the original
anticipation decisions. Each retained top anticipation row keeps its recorded
ticket status and refusal reason; an absent reason stays unknown rather than
being reconstructed from the experimental policy.
Retained planner errors remain visible even when they produced no plan.
On a weekend or holiday, the next-action message names the closed viewing date
and the next session from the recorded calendar; it does not relabel the last
measured open session as closed. In recovery notices, the latest evening
workflow is reported separately: a successful scheduled check may skip
publication and does not refresh the record.

The page is a small application over one record: five views behind the
masthead, the state kept in the hash (`#/explore/bursts/AAPL`,
`#/explore/setting-up/COIL`, `#/record`, `#/market`, `#/method`) so a link
reloads to the same stock and the Back button works; the old one-page
anchors (`#hold`, `#orders`, `#trade-X`, `#burst-X`, `#closest-miss`) still
land where they used to. Choosing a stock fetches nothing, grades nothing
and sizes nothing; a route the page does not know, or a symbol the record
does not carry, falls back to Explore and says so.
The full scan's count is available immediately; its criterion table is built
when the disclosure opens, from the record already loaded. Reopening keeps its
sort and expanded evidence; loading a new record replaces the old scan rows.

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
   anticipation list: quiet, coiled names inside established momentum; a
   name whose last seven sessions range under 0.30 of its sixty-session
   base is pinned, not coiled -- a pending cash takeover looks exactly like
   that -- and is kept off it, and off the near misses beside it),
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
   The chart's arrow keys, Home/End and Escape inspect sessions when the
   chart itself has focus. Open its table disclosure and Tab into the named
   table region to scroll horizontally with the arrow keys; Tab/Shift+Tab
   leave the table normally. These table keys do not inspect the chart.
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
   or makes me wait?*, *principal risk or limitation*. Risk uses accepted reader
   commentary (still explicitly unverified), then plan-derived risk, otherwise
   an explicit unavailable assessment. Recorded screening warnings are separate
   in both detail and comparison; they never fill an absent risk assessment.
   The broad `biotech` flag covers Health Care sector rows as well as matching
   industry text, and does not establish a biotechnology company or event risk.
   `foreign` also includes unstated country. The publication does not carry the
   precise per-stock directory basis, so that limit is stated; raw flags remain
   inspectable in provenance. Anticipation keeps its
   existing action area below those answers. The Burst action summary uses
   the shared `.sc-actionbar` with a compact four-field grid (two columns on
   a phone); browse cards keep their compact form. Four disclosures follow:
   the conditions (one tile per
   criterion with a plain question, local verdict, observed value and reference
   period, this record’s ordinary rule, and method rationale; separate A+
   criteria, formulas and original fields remain in an accessible disclosure.
   Unknown rule formats retain their recorded wording without inferred meaning.
   Then the base, the burst and the grade); the plan, sizing and
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
   checklist criteria the record dated offer separate **Show Base/Burst/Prior
   evidence** buttons using the same mechanism — and a check the record carries no date range for
   (linearity, the trend's age, the run of up days) stays a tile and is
   given an honest unavailable explanation instead of an invented region.
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
   Last, under the open model plans so that nothing a link lands on moves
   as it loads, **What historical validation establishes** replays the record
   night by night from `docs/historical-findings.json` (`docs/app-findings.js`,
   `SCStock.findings`): a stepper over every published night the study carries, the
   10-session ratio on every session the records know -- the gate's own
   reading on a published night, a later record's history on any other, and a
   later history that reads a night's counts or ratio differently named beside
   it -- with the two thresholds of its ratio rule drawn and named at the axis
   (a key says that green also needs every other breadth rule quiet) and a
   dotted line at the study's freeze; under it every settled R of that night's
   counterfactual tickets by stratum on a compressed axis with the night's
   mean. Each stratum's caption says what its counterfactual removed: the gate
   and the reader for A-quality, and for the graded B, C and skip or vetoed
   bursts the grade's or the veto's own refusal too. A night's mean is printed
   and drawn as a rate only from the record's minimum of settled tickets
   (`record.SCORECARD_MIN_PLANS`, 20); under it the night shows its count and
   its sum and its mark is hollow. A night whose hold is over can still move
   while rows a later record can settle remain, and says so; every hold word
   is dated by the records the study read. Three table twins carry the nights,
   every settled R and the market. Then the owner's backtest, the run-6 check
   of the red reading, the "Read it as" caveats -- the exploratory reading
   pooled over the red nights only, the confirmatory split from the study's own
   figure against its minimum, the nights left out counted -- and the 28
   September frozen cases. Every figure it prints is a field of that file at
   the precision the file writes it (a mean at three places, a sum at two);
   its own arithmetic is a night's place in the list, the length of a list the
   file carries, the comparisons that choose a sentence (a count against the
   minimum, every readable stratum under zero, a night's verdict) and the
   drawing. It reads no record, no clock and no storage, checks the file's
   shape before it draws and says in one sentence what it refused; both
   historical files are fetched only when the Record view is first shown, say
   they are loading while in flight and end in a sentence if they stall, and a
   page over a fixture says the replay reads the public findings. On a phone a
   tap within a finger of more than one night asks which, nearest first, and
   stops Play; the list of nights is the precise way to one, and a narrow chart
   shows no tooltip because the caption and the tables carry the values.
5. **Market.** Bonde's Market Monitor over usable fetched stock frames for the measured session:
   up and down 4% on volume, the 5- and 10-day ratios, the
   25%-in-a-quarter and 25%/50%-in-a-month counts, the share above the
   40-day average, the 10-day ratio over the last thirty sessions with his
   line drawn on it, and the regime verdict with every rule that fired.
   Thresholds are scaled to the measured universe against his ~6,500.
6. **Method: How to read SpicyStock.** The view opens on **The method, one burst at a time**
   (`docs/app-method.js`): an animated walkthrough of Bonde’s burst over one
   synthetic series, eleven steps from the thesis to the record — the
   leg, the base, the day before, the signal, the Market Monitor, the plan, the
   fill, the day-3 close, the trail and the exit, the replay — each captioned
   with this build’s numbers and whose number each is. Every number it prints
   is named for the constant it quotes and held to `src/` by
   `tests/test_walkthrough.py`, which also re-derives the example ticket and its
   five-session replay through `plan.burst_plan()` and `record.replay()`, so the
   walkthrough prints what the code writes. It reads no record and stands on
   the no-record page; `#/method/walkthrough` deep-links to it; the bars have a
   table twin. Then the reading journey and concise definitions
   precede the original scan summary, full publication details and configured
   sizing assumptions. Nearby help opens on hover, keyboard focus or deliberate
   tap; its interactive disclosure supports Close/Escape and viewport placement,
   including Compare and enlarged text. `#/method/<topic>` routes open the
   relevant definition; **Back to what I was reading** restores selection,
   browsing positions and an open comparison. Route, record and selection changes
   dismiss stale help. Help is never nested inside an interactive stock card.
   The compact first screen names the purpose, first action, measured population
   and dated snapshot, and says the site neither places trades nor knows holdings.
   Discovery, weighted grade, published ticket and current entry availability are
   distinct. Pass/fail/partial/veto/not measured are local checklist verdicts;
   market regime, publication status, timing, saved confirmation and model outcomes
   retain their own words and palette. Candle direction is close versus open;
   headline gain is versus previous close. Map volume uses the existing compressed
   scale, with an explicit unequal-distance warning and selected-symbol exception.
   `app-reading.js` formats recognised recorded expressions and provides reusable
   definitions; it never scores, changes a plan or applies current defaults to an
   older record. Primary rules, later changes, secondary interpretations and
   implementation proxies remain attributed in the existing source documents.
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
   than saying *tomorrow*: *Review N conditional tickets for Mon 14 Sep*
   before the window, with preparation and protective-stop terms conditional on
   the reader choosing to follow a plan, *The entry window for Mon
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
   reach. Startup and manual refresh each have a 15-second deadline covering
   response headers and the complete bounded body. A press aborts the previous
   attempt and only the newest answer can land. Failed startup offers **Retry**;
   saved private reports remain readable and editable in the Morning desk while
   the publication is unavailable. There is no current entry preparation or
   copying in that state. A failed refresh keeps the displayed record and
   unsaved private inputs; a retry never saves or migrates them automatically.
   A load hands back the stage, the stock and the search, keeps the
   theme, the lens, the chart's mode and range, every saved identity with
   its frozen evidence and a half-typed reference size — and closes a
   comparison rather than remapping its pins onto other stocks, saying so.

The email is the same record in fewer words: the verdict, the breadth line,
one block per trade with its order line and the day-order term, the plans
without a ticket and why, the open model plans' instructions, the alerts,
the problems and a link. Delivery failing never costs the page.

## How a night runs

`evening.yml` is scheduled at 6:16 PM ET on weekdays (two crons, one per UTC
offset) and again at 8:16 PM ET as a retry. GitHub may deliver either job hours
late. The guard resolves the intended occurrence and exchange session, checks
the offset at that occurrence, skips holidays and refuses a delayed run once
the next session opens. Both scheduled slots skip an already published real
ok/degraded record for that session; a failed or rehearsal record cannot
suppress recovery, and a newer publication cannot be replaced by a late job.
Manual dispatch keeps its explicit session and rehearsal controls. The run:

- **universe** — Nasdaq's security-name and industry classifier approximates
  common stock; it is not exact TC2000 membership. Blank-check exclusions use
  the exact industry label or a narrowly bounded `Acquisition Corp[.]` /
  `Acquisition Corporation` legal name, optionally numbered, immediately
  followed by a common/ordinary-share label. Generic acquisition, capital,
  investment and holdings words do not exclude a company. The
  [retained-directory correction](docs/input-truthfulness/2026-09-22-blank-check-classification.md)
  documents every newly excluded name; it does not explain absent provider bars
  or revise the September 18/21 publications. Directory price and volume
  never gate discovery. Broad healthcare/category and domicile warnings remain
  flags (`biotech` / `foreign`), not verified company classifications or
  stock-specific risk assessments. The
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
  At least half but less than all leaves the ledger's acceptance degraded, as
  does any capacity cut or scan/quality error. The run itself is degraded too,
  unless the only gap is stale frames each ending within the 5 sessions before
  the session evaluated -- at most 1% of the intended stocks, no stock under an
  open model plan among them (SPY is outside the stock count here, as in
  acceptance) -- which
  `run.input_tolerance` names, with where each frame ends; the next session's
  run, when it publishes, reads each of them again from its own split-adjusted
  fetch at every session it missed, one reading per stock and session, with no
  extra provider call (`run.stale_followup`, `src/followup.py`), and a late bar
  that the publication for that session would have listed (a 4% or $ scan match, or a setting-up
  name) makes the night that finds it degraded and is named. A late bar is never
  a signal, plan or ticket. A fully evaluated selection can be complete without being the
  complete listed market. The existing $3 session-close policy now reads actual
  cent-rounded bars, with seed/explicit exemptions preserved; actual scan volume
  remains the scanner's rule. Known non-session runs skip before universe/provider work and preserve the prior publication.
  No-bar responses, failed batches, budget-unfetched names, stale frames, gaps,
  unreadable pairs and repaired duplicates are distinct in `run.coverage`.
  Counts reconcile from selection through measured burst/dollar/both/neither and
  quality outcomes; each reason carries a bounded sample and membership digest.
  Below-threshold failures retain their population on `RunReport.input_coverage`
  and in the run log, leaving the last published record intact.
  A separate **input-exceptions** artifact retains every exception name and
  bounded normalized observations before coverage refusal, scans or grading.
  Its run/session/revision identity, complete intended membership and input
  counts reconcile with the compact ledger. Files live under the gitignored
  `input-diagnostics/`, outside `docs/`; the existing evening artifact is unchanged.
  These are input-stage observations, not final measurement counts or raw
  provider evidence. Missing frames stay missing. Capture failures are logged
  separately and do not alter publication decisions or exit codes. See the
  [format and offline verifier](docs/input-truthfulness/README.md#input-exception-artifact-v1).
  `run.universe` records the source, capture timestamp, snapshot hash, selection
  identity, exclusions and the snapshot date's relation to the scan session.
  A contemporary or cached directory never proves historical point-in-time
  membership; pinned sessions carry that limitation. No survivorship-bias-free
  historical backtest is claimed. `run.input_basis` records the feed, split
  adjustment and expected/evaluated sessions; recovery copies the original run.
  Older records without these fields remain explicitly unknown on the page.
  See `docs/input-truthfulness/README.md` for conservation equations and offline impact.
  The [September 18 stale-input investigation](docs/input-truthfulness/2026-09-18-stale-inputs.md)
  pins retained evidence and separates the missing-bar symptom from unresolved causes.
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
  non-linear leg is a veto. A+ and A need 2 and H. The dated
  [consolidation source contract](knowledge/consolidation-quality.md) separates
  Bonde's historical variants from DERIVED segmentation, ratios and C A+ policy.
  The [retained C audit](docs/input-truthfulness/2026-09-22-consolidation-source-fidelity.md)
  reproduces the measurements and their sensitivity without retuning thresholds.
- **grade** — Claude reads the chart and the numbers for up to twelve
  bursts and may only LOWER a grade, never raise it. The versioned
  `account_feasible_first_research_v1` policy prioritizes private pre-review
  plans that satisfy the mechanical grade/regime, veto, known-event, entry
  geometry and whole-share checks. Their existing mechanical grade / descending
  score / ticker order is preserved. All feasible names are covered when the
  twelve-name budget permits; none is displaced for research. At most 2 spare
  reads go to infeasible mechanical A+/A research: one by that same rank, then
  one by the lowest SHA-256 of policy, measured session and ticker. With no
  feasible names this is at most two reads, and an empty research pool makes
  no model calls. This near-admission sample is not an unbiased market sample.
  `bursts[].review_selection` retains each purpose and checked blocker;
  `run.review_selection` reconciles feasibility, research-pool size, selected
  names, accepted/unaccepted/refused results, actual retained attempts and
  unused capacity. Attempts are distinct from requested names and billed cost.
  Method explains reconciled pre-review fit and opportunity/research selection.
  The current cover and Morning desk add selected-batch completion separately
  from broader review coverage only when the supporting counts reconcile.
  A completed research batch does not mean all discovered candidates were
  reviewed or that any plan is admitted. The original published summary remains
  available; missing, unsupported or contradictory completion evidence leaves
  that wording in place without the new completion claim.
  The private preview precedes combined allocation; selection grants no ticket.
  Final accepted-review, grade/regime, sizing, event and allocation guards
  remain unchanged. Archived records without this policy keep their original
  selection contract. A new rules identity also retains the existing
  conservative reservation behavior for open model plans.
  The rulebook it reads is `knowledge/strategy.md`. No reply, or a refused
  key, leaves the checklist's grade standing for research and marks the night
  `claude_unavailable`. Every new reaction row records `reader_coverage`:
  `accepted`, `fallback` (selected but no accepted result), or
  `not_selected_budget`; missing legacy evidence remains `unknown`.
  Rejected/unavailable fallback and budget exclusions are not reader approval
  and do not measure a bad setup. Neither may enter final burst planning.
  Each reaction row archives a versioned `discovery`
  block from those same scan rules and measurements: `burst`, `dollar` or
  both, with applicable and explicitly inapplicable rules kept apart. A
  dollar-only candidate does not require a +4% close-to-close gain. Quality
  can still be lowered for independent chart/checklist evidence. Recognized
  contradictory replies are rejected whole into mechanical fallback without
  a retry; their score and explanation are not published as chart judgement.
  Reader authority v1 additionally requires a permitted criterion/source/observation
  and exact citations to structured checklist evidence for any downgrade. Missing,
  unknown, contradictory or unauthorized evidence rejects the whole judgement
  without retry and leaves the mechanical grade standing; such refusals, and the
  discovery contract's, degrade the night only past a quarter of the night's
  reads, when none is accepted, or when the refused name would otherwise have
  been planned. A reply that never arrived
  or could not be read always degrades it, and an empty credit balance stops the
  calls the way a refused key does. `run.reads` counts the shortfall by cause.
  Visual findings require a supplied chart; recorded FAIL/PARTIAL findings can
  use measurements. Subjective chart truth and free commentary remain unverified.
  Every model receives the same nested findings schema in text; supported models
  also receive it through structured output. Findings and citations remain closed
  objects. Returned text is retained before parsing/authority checks in each
  attempt, with its SHA-256, byte count, stop reason and message ID. Text above
  64 KiB is explicitly omitted with its digest and size retained. Rejected text is
  diagnostic evidence, never an accepted judgement, and the quality ledger retains
  those attempts unchanged. Authority failures still do not retry; only parser
  failures receive the existing format-correction retry. The September 22 replies
  were discarded before this correction, so their exact fields and semantic
  authority cannot be recovered; see [the incident audit](docs/input-truthfulness/2026-09-23-reader-authority-production-compatibility.md).
  See [the 108-decision audit](docs/input-truthfulness/2026-09-22-reader-downgrade-audit.md). The reader
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
- **plan** — an accepted reader review is required in addition to the existing
  grade, veto and market gates: GREEN admits final A+/A, YELLOW only final A+,
  RED none. The versioned `pipeline.reader_policy` records this requirement;
  the decision receipt records coverage separately from market permission and
  ticket status. An admitted burst gets a plan sized from the configured
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
  and sized at its limit the same way. Reaction plans and anticipation plans
  share one allocation, with reactions considered first and anticipation in
  watchlist rank. Existing occupied model plans reserve their original model
  principal even after partial sales; uncertain observations do not create free
  slots or cash. Zero-share refusals show the effective risk budget after size
  reductions and the position cap. This allocation is a model, never the owner's
  observed holdings or settled cash.
  A dated manual corporate-action registry with primary-source links withholds
  known cash-takeover candidates from both kinds of momentum ticket. Its
  evidence is part of the rules identity; a due review does not silently clear
  an exclusion. Unknown names have not passed a comprehensive live news check.
  ZIM was added on 10 October 2026 after reviewing its 16 February $35 cash
  merger announcement, 30 September Israeli approval-process update, and
  6 October guidance release identifying the transaction as pending. The
  guidance increase remains useful research context; it does not remove the
  existing takeover exclusion. This addition does not establish live news or
  earnings-calendar coverage for other candidates. The [captured issuer and
  SEC sources](release-evidence/2026-10-10-zim/README.md) retain the reviewed
  bytes, source dates, retrieval times and digests.
- **record** — the picks go to `docs/picks.json`; the open plans and the
  scorecard are computed from it and the bars. Suggested shares are model
  sizing, never shares bought. New plans carry a versioned evidence reference.
- **publish** — source, discovery, checklist, reader, regime and plan evidence
  must verify before the serialized data/picks pair replaces the previous
  publication. Source-object staging handles close before installation, including
  on Windows; a required evidence write failure withholds publication.
  Contradictions fail closed. Then the email
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

`intraday.yml` remains a manual legacy research artifact. Its old combined
price/volume fields do not establish entry validity. The workflow sends no
email, forwards no delivery credentials, writes `docs/live.json` and commits
nothing. Use the separate morning-observation path for dated quote checks.

### Morning observations

`morning.yml` collects a small, read-only `docs/morning.json` beside the
canonical evening publication. Each observation binds the exact publication
bytes, run, rules, applicable session, candidate stage and retained plan.
Only already-admitted tickets can request quotes; a withheld candidate cannot
become a ticket through this refresh. The evening record and its evidence are
unchanged.

The browser shows IEX as a single-venue observation, with bid/ask, spread and
provider timestamps kept separate from collection time. A latest trade is not
a current executable quote. Delayed SIP daily volume remains explicitly
delayed; its daily-bar timestamp is a session label, not a claim about when the
volume was complete. Invalid, crossed, stale, future-dated, missing and failed
observations stay visible as limitations. Quotes and latest trades expire after
60 seconds; the collection receipt expires after 300 seconds. A halt feed is
fresh for at most 180 seconds by its channel publication time. These limits
label measurement age, not permission to trade. Price comparisons use the retained
trigger, limit and stop and do not authorize an order. Check current prices,
spread and order terms at the broker.

Nasdaq's public halt RSS supplies named halt observations. A quote-resumption
time alone does not establish trade resumption; older unresolved halts remain
relevant. A missing symbol or unavailable feed is not a clearance. Issuer news
and earnings remain unchecked, and corporate-action coverage is the bounded
source-backed manual registry. Known event restrictions survive publication
updates and require dated, source-backed resolution evidence to clear. The page
states these coverage limits.

Two best-effort scheduled attempts target 8:20 and 8:28 a.m. Chicago, with
separate daylight/standard UTC slots and XNYS session checks. Delayed scheduled
jobs skip the wrong session and the expired entry window. GitHub Actions and
Pages can deliver late; this is a dated snapshot, not a sub-minute quote
service. The browser recomputes freshness as time passes. Its reload control
only re-reads the public snapshot; it does not call a market-data provider.

Manual dispatch defaults to a rehearsal artifact. An optional rehearsal-only
source diagnostic requests the fixed SPY symbol through the same feed adapter
and normalizers, even when there are no admitted tickets. Its separate artifact
contains no plan or publication authority and cannot be written into `docs/`.
Production persistence is
restricted to main and rechecks the current canonical record and any newer
observation before a one-file, ordinary fast-forward push. The existing
publisher then verifies the committed public files. Collection receives only
the Alpaca data credentials; it never requests trading, chart-reader or email
credentials, and no provider secret reaches the browser. No new subscription
or environment variable is required. Timely morning delivery and comprehensive
event coverage remain acceptance work for milestone 2.

### SEC issuer evidence

The Morning desk includes an optional filing reader for current admitted plans
and candidates withheld by known corporate events. Opening it loads a small
publication-bound receipt and one verified source bundle. It shows the issuer,
SEC identity, filing and acceptance dates, retrieval time, primary links and
short text excerpts. Private cash, notes and selected symbols are never sent
to a source service. The closed reader makes no additional browser requests.

The collector verifies ticker/CIK identity and lists current-report metadata
from a trailing 365-day window. It selects up to eight issuers, prioritizing
admitted plans, then retrieves at most three recent 8-K/6-K reports per issuer
and two same-accession exhibits per report. One bounded history file may extend
the metadata window. Missing history, omitted issuers, unfetched reports and
truncated excerpts are explicit; a recent-document sample does not establish
complete news coverage. Domestic 8-K and foreign 6-K reports retain their own
dates and document types. An acquisition mentioned by an issuer does not, by
itself, establish that the issuer is a takeover target.

Known unresolved events remain separate, source-backed anchors. The collector
does not classify new events or clear an existing exclusion. In the 10 October
2026 source audit, the original ZIM merger report was seventeenth newest among
33 trailing-year current reports, illustrating why a recent-filings panel
cannot replace those anchors.
Future earnings and comprehensive issuer news still require verification.
This reader does not change a ticket, copied quantity or cash preview.

`issuer-evidence.yml` follows an actual committed evening or morning publication;
the guard identifies the parent by its exact workflow file path, then checks
its repository, main branch and current publication binding. Dynamic run titles
are display text. It adds no polling schedule. Production collection is capped
at three starts
per UTC day, including failed attempts and reruns, with a serialized guard that
refuses incomplete Actions history. Manual dispatch defaults to a rehearsal.
The SEC-only client uses the public project identity, no provider credential,
and at most one request per second, 96 requests, 2 MiB per response, 32 MiB of
downloads and four minutes per collection. Retained raw captures, including
reused cache bodies, have a separate 32 MiB cap. Cached source bodies retain their
last network-check time. Mapping cache lifetime is seven days and document
cache lifetime is 24 hours; submissions are requested on each collection.
The cache is bounded to 256 entries and 128 MiB.

When an HTTP response refuses a request, the reader shows its observed status
and source stage (mapping, submissions, history, primary report or exhibit).
Older receipts and failures without an HTTP response leave the status unknown.
Diagnostics retain the original requested SEC URL, never a redirect destination,
response body, headers or exception text. Redirects remain refused; refused
responses are closed without reading their bodies. A status explains a failed
source request and does not establish news or earnings coverage.

Coverage labels must reconcile with the retained evidence. Unverified identity
cannot claim an observed index or collected issuer. A complete index can coexist
with a later filing-document failure; that issuer remains partial. Collected
rows require every selected primary and no recorded omissions or truncation.
Request and byte totals must cover the distinct visible source events and
explicit HTTP failures, while preserving valid cached and legacy observations.
These checks establish internal consistency, not comprehensive source truth.

The receipt expires 24 hours after collection; individual source ages remain
visible, and this period is not news clearance. Up to 16 KiB of normalized
text is retained per excerpt, with a separate excerpt digest and original-body
digest. Raw captures are kept in a 30-day Actions artifact, rather than claimed
as a permanent complete archive. The public receipt is limited to 64 KiB and
its digest-addressed bundle to 2 MiB. A main-only publisher revalidates the
source publication, previous receipt and current branch before committing.
It retains superseded bundles for at least 21 days and protects the current
bundle; its owned store is bounded to 256 objects and 256 MiB.
Previously published receipts remain readable as dated evidence but cannot
attach to a different scan. An issuer-source failure does not prevent the
evening record from publishing. See the
[versioned source contract](docs/ISSUER_EVIDENCE_SCHEMA.md) for exact fields.

### Registered anticipation stop-width research

The Morning desk has a closed **Wider-stop anticipation research** disclosure.
It compares the unchanged 4% production stop-width cap with a separate 5%
anticipation calculation for applicable sessions **October 12 through November
6, 2026**. The versioned experiment is `anticipation_stop_width_4_to_5_v1`.
It changes no production ticket, reaction/burst stop selection or model record.
There is no research order-copy or broker-draft action.
An **Inspect recorded chart** action opens the same publication's existing
anticipation chart and baseline decision. It checks the publication and retained
evidence identity again when pressed, including after a same-ticker refresh.
Missing or changed identity leaves an explanation in the research panel.
Inspection preserves private preparation and adds no current quote or order.

The producer uses the actual retained planning inputs and the same pure planner,
changing only the anticipation cap. Original trigger, limit and structural stop
must match; the 4% calculation must reproduce original geometry, sizing and
multipliers before a comparison is accepted. The reference remains $2,000,
0.5% base risk, a 25% per-name cap and four slots. Existing market, watchlist,
known-event, whole-share and shared-allocation rules still apply. A stop beyond
the ideal distance still halves the risk budget; widening the cap does not
increase the configured dollar-risk budget.

All original top anticipation rows are retained, including excluded names,
zero-share results and out-of-band rows. Current baseline tickets and unfinished
model positions reserve their cash and slots first; research cannot displace a
baseline trade. The panel shows the original refusal, fixed levels, hypothetical
quantity, principal, price-to-stop risk, risk multipliers and each remaining
blocker. These amounts exclude actual fees, gaps and slippage. Model reserves
are not broker holdings or available settled cash. A manual event-registry
match is an exclusion; no match is not news or earnings clearance. There is no
new chart review, quote, provider request or inferred trading outcome.

The comparison is bound to the exact canonical publication, compact reader,
archived rules, plans and retained sources. Its actual generation timestamp is
separate from the source publication's run-start timestamp. Collection before,
during or after entry is labelled accordingly; a late backfill cannot claim to
be pre-entry research. The reader labels an elapsed entry window as archived.
Empty/refused cohorts and outside-period status remain visible evidence.

The evening hook runs after final canonical/reader bytes, including delivery
failure restamps. Unsupported account/rules, invalid retained sources or a
research-write refusal leave the authoritative publication unchanged. An older
receipt can remain, but cannot attach to a different current publication.
There is no research environment variable, provider credential or subscription.

Opening the disclosure fetches only the optional `stop-research.json` receipt
(at most 16 KiB) and its exact digest-named bundle (at most 128 KiB), with a
15-second deadline and the existing omitted-credential/no-redirect transport.
Its immutable cohorts and append-only index retain at most 128 cohorts / 16 MiB;
the index is capped at 64 KiB. Capacity exhaustion refuses a new write without
pruning past cohorts. Repeating an exact publication preserves its first
cohort and generation time. These repository/Pages paths are public; they contain
no private reports. The publisher verifies the current referenced bundle;
retained cohorts are not initial page requests. See
[the registered schema](docs/STOP_RESEARCH_SCHEMA.md) for the exact contract.

This is a dated strategy experiment, not evidence of an established edge.
User-reported trades/results remain separate. Promotion or performance claims
require a later explicit strategy review using the retained comparison and
subsequent observations.

### Research follow-through

The Morning desk's optional **Research follow-through** view follows every frozen
wider-stop cohort using observations already retained by normal publications.
It makes no new provider or model requests. The first before-entry cohort for
an applicable session is identified as primary; later revisions and late
captures remain visible. Original exclusions, quantities and levels stay frozen.
Each verified original row can open a blank private actual-fill report. Its
explicitly entered broker facts stay separate from these conditional model
outcomes; the journal adds no order or personal entry-draft action.

The companion reports pending, missing, uncertain, not-filled, open or resolved
conditional daily-bar models, plus explicit unsupported-source states. Before
an entry session has a completed observation publication, it remains pending.
The initial October 10 snapshot has October 9 bars and remains pending for
the October 12 entry session; no outcome or R is invented. Missing sessions do not become zero
returns. A daily high/low crossing cannot establish the first thirty minutes
or intraday event order. Only a reconciled resolved model has an R result;
actual fees and slippage remain unspecified. This is not personal execution,
a portfolio return or a win rate. Research positions are not reserved across
separate cohorts as a hypothetical portfolio.

Each evaluated clip identifies its containing observation publication, dates,
bar digest and provider/feed/adjustment/daily-timeframe basis. The original
source anchor and supported fill/follow/R rules must agree. Anchor comparisons
use the pipeline's explicit four-decimal public price format while retaining
the raw source anchor and hash. Unknown or conflicting carried bases remain
unavailable. A prior conclusive clip may remain readable with its original date
when newer coverage is partial; genuinely conflicting new evidence is flagged.
Full OHLCV revisions produce new snapshots, retaining the prior snapshot.

The evening hook runs after final canonical/reader writes and the optional
stop comparison. Its failure preserves the authoritative record and previous
companion. Opening the disclosure fetches the fixed `research-outcomes.json`
receipt (16 KiB maximum) and its exact digest-named bundle (2 MiB maximum),
with a 15-second deadline and no private browser inputs. The original frozen
cohort bytes are embedded, so the browser requests no extra ticker histories.
A differently bound receipt cannot attach to the current observation publication.

The producer accepts at most 128 cohorts / 640 original rows, 16 MiB of cohort
inputs and 128 MiB of sequential original-publication reads within a 60-second
processing deadline. Its append-only store retains up to 128 snapshots / 64 MiB
and a 64 KiB index. Repeating the same publication/cohort set preserves the first
snapshot and generation time. Invalid archives or exhausted bounds refuse a
write without pruning earlier results. These repository/Pages archives are
public and contain no private reports. The publisher verifies the current
receipt and referenced bundle. See the [versioned contract](docs/RESEARCH_OUTCOMES_SCHEMA.md)
for source limits, replay semantics and exact fields.


### Reader payload and saved research

The page initially loads `reader.json`, a compact projection of the complete
canonical `data.json`. Candidate evidence, plans, account assumptions, timing
and embedded charts remain available immediately. The larger retained
observation history loads as one shared, digest-addressed file when saved
research needs it. A morning visit does not download that history or the full
canonical publication. Direct canonical records and old saved originals remain
readable.

The October 9 production record projects from 14,918,679 to 5,606,909 decoded
bytes, including its envelope. The deferred observation file is 5,040,916 bytes.
These are artifact sizes, not measured network transfer or a mobile-device
speed guarantee. Complete hydration reproduces the original parsed publication;
the canonical record, picks and historical evidence are unchanged.

New morning receipts derive both canonical and reader hashes from the exact
canonical source bytes. The browser verifies the actual reader bytes before
matching observations. An older receipt can still preserve independently
validated event restrictions, but cannot claim a reader-bound quote check.
Initial loads, refreshes and deferred research preserve the actual response
bytes within the 32 MiB limit. Digests use those bytes directly; malformed UTF-8
and BOM-prefixed JSON are refused instead of being silently normalized. Startup
and refresh share a 15-second header-and-body deadline and cancel superseded
attempts. A failed refresh keeps the displayed publication and private inputs;
failed startup clears partial publication state and offers an explicit retry.
Saved private reports stay available without a publication.
Missing, loading or failed deferred research stays explicitly incomplete.
Saved bars merge only after the sidecar's digest, length, shape and metadata
validate; a stale response cannot overwrite a newer publication. Retry is
available after a fetch failure.

Sidecar requests use only a shared public digest path and send no private saved
symbols, notes or positions. Reads omit credentials and referrers, refuse
redirects and enforce size/time bounds. The publication installs verified
immutable sidecars before replacing fixed records and rolls fixed files back
on installation failure. It refreshes companions after final publication
restamping as well as the initial write. Owned derived transport files have a
21-calendar-day retention window measured against advancing publication-session
dates, with the prior current object's session refreshed when it is superseded.
The currently served file is always retained. This is not a guarantee of 21
elapsed days after a late publication. Canonical history and evidence
are outside this cleanup. The committed-main publisher verifies the reader and
its referenced sidecar before declaring the site updated.

`python -m src.reader --docs docs --check` verifies committed companions without
repairing them. Omitting `--check` derives companions from the existing canonical
bytes; it makes no provider request and does not rewrite the canonical record.

The combined morning/reader release shipped in [PR #114](https://github.com/spicyChicken59/SpicyStock/pull/114).
Its [dated acceptance record](release-evidence/2026-10-09-morning/acceptance.json)
retains hosted test counts, real-feed diagnostics, the production observation,
public asset hashes and phone/desktop browser results. The October 9 production
check is after the entry cutoff, with no quote rows or eligible orders. It is
evidence of correct binding and publication, not pre-open delivery or a trade.

## One-time setup

Six repository secrets: `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`,
`ANTHROPIC_API_KEY`, `RESEND_API_KEY`, `RESEND_FROM`, `EMAIL_TO`. Two
optional repository variables: `SCAN_FEED`, `SCAN_UNIVERSE`. The production
evening workflow explicitly sets `ACCOUNT_EQUITY=2000` and `RISK_PCT=0.5`;
edit that versioned configuration when the owner's sizing reference changes.
Local `Account.from_env()` defaults remain the historical $10,000 model and
accept local `ACCOUNT_EQUITY` / `RISK_PCT` overrides. GitHub Pages from `main`
`/docs`. Until a
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
node tools/page_smoke.mjs --only reading      # recorded meanings, help and review journey
node tools/page_smoke.mjs --only status       # both ticket families and workflow/publication distinction
node tools/page_smoke.mjs --only decisioninspection # anticipation reasons and exact recorded-chart navigation
node tools/page_smoke.mjs --only findings     # the Record view's replay over the committed findings
python tools/make_fixture.py --check        # the fixtures are what the pipeline writes
```

The page smoke runs its suites in two lanes over one browser, each line it
prints marked `[A]` or `[B]`: lane A holds every suite that writes the
smoke's own scratch records under `tests/fixtures/page/` or reads the
clipboard (Chromium shares it between contexts), one after another; lane B
holds the self-contained modules beside them. In one line they took 14 m 54 s
of the CI page job's fifteen minutes. `--only` still runs the suites it names.

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

The one tool that IS a backtest is `python tools/historical_backtest.py
--manifest <acquisition-manifest.json> --storage <recovered package> --output
<private directory>`. It replays the run's own stages over the bars a recovered
historical acquisition package holds, one session at a time, calling the
functions the pipeline calls: the session rules and the $3 policy over the names
that printed, `breadth.snapshot()` and its regime, `pipeline.scan_frames()` and
`pipeline.rank()`, `pipeline._make_plans()` with the open model plans of the
sessions before counted against the slots, `record.append()`, and the published
scorecard's own `record.scorecard_rows()` and `record.summarize_scorecard()` over
the whole archive instead of their window, with `record.append()` told a
retention its picks cannot reach and the run refusing to score a population it
did not issue. Every number is the module's. The reader is NOT RUN, so every
name's mechanical grade is the ceiling of its final grade (the ticket set is
not a superset of the live run's, because a reader downgrade frees a slot the
next name takes); the universe is the archive's later membership
(survivorship); fills, exits and R are the daily-bar model the scorecard uses. A
second block removes the regime gate and is labelled a counterfactual. Each
evaluated session needs `pipeline.LOOKBACK_DAYS` sessions of history before it,
as a live frame carries; `--lookback` may shorten that to reach more sessions,
and a shortened lookback is admitted only with its equivalence check -- on every
session that also carries the full lookback both are measured and compared
(regime, every candidate's grade, score and vetoes, every plan's prices and
shares), and a single difference is a FAIL and exit code 2. It writes
`backtest.json` (every row, with prices: private) and `summary.txt` (counts and
R only). Both the storage and the output must sit outside any Git checkout. It
makes no provider, model or network call, and it is not an edge claim: the
summary reads no rate under the scorecard's own minimum.
Its first real result -- the owner's run of 6 October 2026 over the run-6
archive, 158 sessions with the equivalence check reported PASS -- is recorded as
pasted, from the two summaries, in
`docs/input-truthfulness/2026-10-06-backtest-results.md`; the per-row files stay
on the owner's machine.

Its sibling over the public records is `python tools/signal_outcomes.py --spec
<spec.json> --output <dir>`: every burst row in the first publication of each
session the spec names, ticketed by `plan.burst_plan()` with the record's own
account at the GREEN multiplier -- the regime gate, the slot cap and the budget
not applied -- and walked by `record.replay()` over `plan.FINAL_EXIT_DAY`
sessions of the records' own published bars (the observation histories, the
latest observations and the candidate series, the newest publication winning
and every changed bar counted as a revision), bucketed as
`record.scorecard_rows()` buckets a plan and summed by
`record.summarize_scorecard()`. The rows are read in strata by the checklist's
verdict -- admitted (`pipeline.TRADE_GRADES` with no veto), B, C, skip, vetoed
-- so the admitted stratum stands against the rest of the same nights, by night
with a night-block bootstrap, with a labelled bound for the uncertain fills
(the same ticket filled at its trigger) and three per-side costs beside it. The
spec is committed before any outcome is computed and names the publication
commits and their record blobs; a commit the checkout cannot produce or a blob
that differs is a refusal, never a smaller population. Signals published up to
the spec's freeze are exploratory, later ones confirmatory. It is a
counterfactual: every ticket it walks was refused by the RED gate and the
reader is not run; it reads no rate under the scorecard's minimum and is not
an edge claim.
Its first confirmatory re-read, over nineteen publications under a spec that
differs from the frozen one by appended publication entries only, is
`docs/input-truthfulness/2026-10-06-signal-outcomes-confirmatory.md`.
`python tools/build_historical_findings.py --check` holds the committed
`docs/historical-findings.json`, which the Record view replays, to those
evidence files and nothing else: the two study outputs, the publication
records the spec names (read from git by commit and held to the blob), the
owner's two pasted backtest summaries parsed by the exact line grammar
`historical_backtest.summary_text()` emits, and the pasted run-6 summary
with its public receipt. A difference exits 1, as `make_fixture.py --check`
does; a line the grammar does not know is a refusal, never a skipped
number, and so are a missing or repeated line, a line before the block it
belongs to and a printed bool that is not True or False; and a field name the
secret scan would read as a credential is refused before anything is written.

The fixtures under `tests/fixtures/page/` are records the real pipeline wrote
over a synthetic market through the same doubles the tests use, one per
state the page can be in (`full`, `degraded`, `notrade`, `yellow`, `red`,
`closed`, `empty`, `partial`, `early`, `thin`), plus two sequels of the `full` night (`next`, `revised`) run over
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
stale states, drops twenty fields in turn (a burst without browser bars must
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

The wait explanation uses that same publication/calendar authority. The close
buffer does not end an unpublished evening evaluation: the completed session
remains pending, or is reported as delayed/missing/possibly failed under the
existing freshness policy. A future completion time is not promised. Clock, focus,
visibility and refresh updates preserve the reading state. Planning explanations
distinguish a recorded early-gate skip, an attempted error, a produced refusal,
recorded sizing/allocation and unknown historical evidence; null alone establishes
none of those stages. See the [PR #92 correction and proof limits](docs/input-truthfulness/2026-09-28-pr92-explanation-correction.md).

The normal `page_smoke.mjs` gate includes the shared historical journey and wait
regressions, pinned to retained publications independently of later automatic
`docs/data.json` updates. `--only historical,wait-explanations` runs that focused
selection; `tools/historical_journeys.mjs` remains a standalone entry point to
the same historical assertions.

Deterministic cases include 2024-08-26 (ordinary Monday), Aug 31/Sep 1 (weekend),
Sep 2 (Labor Day), Aug 30→Sep 3 (adjacent sessions), Nov 29 (13:00 ET close),
Dec 2 (the following session), Mar 8→11 and Nov 1→4 (DST offsets). Historical
1992-11-27 closes at 14:00 ET, proving shortened hours are not a fixed 13:00 rule.
The `closed` fixture is an unchanged Sep 4, 2026 publication viewed on Labor Day;
`early` is the Nov 27, 2024 signal for Black Friday. `thin` is two evenings
over one docs directory and a 100-stock selection: on the first, two stocks are
behind -- one by two sessions, one by one -- (over the limit of one, so the
night is degraded and names both, with where each frame ends); on the second,
the first stays a session behind (within the limit, so the night is ok and
names it), the follow-up reads the first evening's two again from the second's
fetch at every session each missed -- three readings over two stocks, each a
flat, zero-volume bar the publication for that session would not have listed --
and the red regime uses only two accepted near-admission research reads. Reader
refusal limits remain covered by pinned offline policy tests. These
are offline fixtures, not historical point-in-time universe or profitability
evidence.

## Layout

```
src/            history.py (public recovery and coverage)
                provenance.py (immutable evidence receipts and offline verification)
                pipeline.py (the run) · inputs.py (population ledger) · universe.py · market_data.py · clock.py
                input_diagnostics.py (run-scoped exception membership and observations)
                followup.py (the next session's read of the previous publication's stale stocks, from its own fetch; never a signal)
                quality_ledger.py (immutable publication input/grade/model-outcome facts)
                review_selection.py (feasible-first chart review and bounded spare research)
                stop_research.py (registered source-bound anticipation comparison and immutable cohorts)
                research_outcomes.py (frozen cohort follow-through from dated retained observations)
                scans.py · discovery.py · quality.py · breadth.py · watchlist.py · plan.py
                sessions.py (pinned XNYS sessions, actual hours and timing provenance)
                timing.py (which session a plan is for, and when its window is over)
                grader.py · reader_authority.py · reader_coverage.py · charts.py · record.py · report.py · event_risk.py · allocation.py · morning.py · morning_halts.py · reader.py · issuer_evidence.py
docs/           index.html · app.js · app.css · app-reading.js · app-method.js · app-chart.js · app-map.js · app-follow.js · app-findings.js · app-morning.js · app-cash-preview.js · app-handoff.js · app-handoff-ui.js · app-observations.js · app-reader.js · app-issuer-evidence.js · app-stop-research.js · app-research-outcomes.js · design-system/
                data.json · picks.json (the record) · charts/ (gitignored)
                reader.json · reader-observations/ (derived browser projection and deferred public history)
                stop-research.json · stop-research/ (registered comparison and immutable cohorts)
                research-outcomes.json · research-outcomes/ (dated conditional follow-through snapshots)
                historical-validation.json · historical-findings.json (read-only evidence the Record view fetches; the second built from the evidence files, not written by the run)
                history/ (recovery) · evidence/ (deduplicated source objects)
                quality-ledger/ (versioned publication facts; created by future real publications)
knowledge/      strategy.md (the rulebook the grader reads) · method.md (whose number is whose)
tests/          the suite, the doubles (fakes.py), the synthetic frames, fixtures/page/
tools/          make_fixture.py · page_smoke.mjs · chart_check.mjs · publish_dashboard.py · publish_morning.py · probe_morning_sources.py
                verify_provenance.py · provenance_impact.py (offline receipts and measurements)
                entry_limit_study.py (read-only: the retired ceiling, production and an oracle over an archived record)
                historical_backtest.py (offline: the run's own stages replayed over a recovered archive; reader not run)
                backtest_timeline.py (offline: the owner's private backtest record read into one row per night per gate -- the night's breadth and its tickets' outcomes by scorecard bucket, uncertainty kind and settled R -- every field copied by type from a fixed list; a private key, or a ticker the record names as a whole word in any case in a key or string that is not one of the tool's own words, is a refusal, as are a night or gate whose counts do not reconcile, a malformed file and an --output over the private file)
                signal_outcomes.py (offline: every archived signal ticketed and walked over the records' own bars; a counterfactual)
                build_historical_findings.py (a reader: docs/historical-findings.json from the committed evidence, every number bound to its source digest; --check holds it)
                findings_cases.mjs (the page smoke's findings suite: the Record view's replay over the committed findings)
.github/        evening.yml · intraday.yml · morning.yml · issuer-evidence.yml · tests.yml · publish-dashboard.yml · secret-scan.yml · historical-input-proof.yml
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
The original two records are gzip fixtures under `tests/fixtures/continuity/`,
and so is the public archive the check's recovery journey searches:
`history-2026-10-01.json.gz` is `docs/history/index.json` and the 11 September
record's context and ATEC/VICR rows exactly as published on 1 October, digests
intact, because the live `docs/history` keeps a 21-day window and stopped
carrying those originals on 2 October. The check never reads the checkout's
rolling archive, so its answer does not depend on the date.

## Retained quality evidence

The dedicated manual `historical-input-proof.yml` workflow prepares encrypted
historical evidence under the [execution handoff](docs/input-truthfulness/2026-09-29-historical-execution.md).
The replacement real phase ran once as native 6 / attempt 1 (run 36815689950,
1 October) on the owner's dated readiness-v4 comment, after the repair merged;
no further dispatch is admitted. Its [result](docs/input-truthfulness/2026-10-02-historical-run6-result.md)
is below. Native 5 failed before checkout because its comment-ID
input contained leading spaces. The boundary now trims only edge ASCII spaces
and tabs, then passes the canonical numeric ID to the unchanged authorization
checks. Its failed attempt and consumed readiness remain immutable history.
The original workflow failed GitHub context
validation before any job; the execution handoff records its three preserved
failures and the narrowly reviewed recovery contract. Native run numbers are
not phase numbers. Normal CI checks the changed workflows with pinned actionlint.
The hosted synthetic rehearsal (run 36570997883, native 4 / attempt 1 / phase 1)
and exact source-pinned owner replay were accepted on PR #95. They used the
previous execution checkout; they did not exercise the later conversion-evidence
compaction or archive delivery changes. Guidance's separate execution release was
never posted; the guard does not require one, and the owner dispatched on readiness.
The prior 199 MiB stress failure is preserved. The explicit delivery-envelope
continuation uses a 250 MiB archive / 251 MiB ciphertext ceiling, preserving
the 2 GiB expanded limit and the selected codec. The complete central and stress
synthetic cases passed encryption, recovery of all 390 original members and exact
offline reproduction under that contract on PR #97. The
[dated delivery evidence](docs/input-truthfulness/2026-09-30-delivery-readiness-evidence/envelope-continuation/review.md)
binds those measurements to their actual source and hosted jobs. The versioned delivery relation names only that accepted transport
evidence and requires the new implementation's own capacity/runtime evidence, reviewed head,
current-main source equality and complete native run history. It does not reopen
the rehearsal slot. The personal-use decision on PR #95 ends licensing/outreach
work; the new owner-scope attestation records authorization, not provider consent.
Cost, entitlement, credential and technical safety checks remain separate.
Synthetic fit does not establish real-data fit or market correctness.

The [September 24/25 input and market-permission investigation](docs/input-truthfulness/2026-09-28-historical-input-proof.md)
reconciles retained aggregate RED decisions and the available stock observations.
Complete original final-population masks and full daily-bar inputs remain missing.
`tools/historical_input_proof.py` reproduces the retained-data analysis with sockets
blocked. The separate bounded acquisition tool defaults to offline validation;
live historical retrieval requires the frozen manifest and documented zero-cost,
private-storage authorization. Run 6 performed that one retrieval: all 97 queries
completed, using 289 of 400 request slots. Every intended stock returned
target-day and prior-day bars, and 263 symbols per session are partial. The
owner-decrypted, price-free summary reproduces RED on both sessions under both
later-eligibility policies. Under C the 10-session ratio stays below 1.0 across
the outer bounds over every unknown (0.92–0.95 and 0.88–0.90). Under D it is
exact (0.93 and 0.89). Strict establishment stays BLOCKED by six counted stocks'
missing monthly-test inputs, and the exact original population stays BLOCKED.
`tools/historical_reconcile.py` consumes only that tool's verified private cache,
keeps later observations separate and never publishes plans or reuses reader approval.
Its version-2 output stores lossless float-conversion evidence by selected-row
reference and field mask. Exact normalized decimal strings and raw-page lineage
remain retained; a bounded decoder reconstructs the legacy per-field facts.
The representation changes neither the float DataFrames nor market predicates.

The [22 September quality audit](docs/input-truthfulness/2026-09-22-retained-quality-audit.md)
distinguishes input reliability, mechanical/final grades and model outcomes.
Future real publications append compact immutable facts under
`docs/quality-ledger/v1/`, named by the original publication SHA-256. Original
rules, denominators, UNKNOWN fields, complete exception membership, grading
facts and per-plan scorecard observations survive recovery expiry. This ledger
does not participate in trading decisions or change the existing reliability row.
It retains no raw bars or personal execution. Existing Git persistence includes
it; no new workflow or dashboard is required.

Each deterministic gzip entry is limited to 8 MiB expanded; the archive is
limited to 128 MiB compressed and 4,096 entries, without eviction or historical
rewrites. Capture failures leave decisions/publication/exit codes unchanged and
emit `quality_ledger_capture_failed`, RunReport status and an attempted-capture
`quality_ledger_status` output. Interrupted, failed or skipped runs can lack an
entry; ledger membership is not proof that every attempted run was captured.
No historical backfill is performed. Capacity and future schema changes require
an explicit retention decision, preserving old entries and their rule basis.
