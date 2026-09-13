# SpicyStock — working notes

An evening run over every US-listed common stock, a static page that says
what to do tomorrow and why, and one email. Bonde's momentum burst method:
`knowledge/method.md` says whose number every rule is, `README.md` says what
the software does with them, `knowledge/strategy.md` is the rulebook the
grader reads. Treat the code as evidence and the prose as suspect until
checked.

This is the second build. The first (fifteen rounds, a ledger of forward
returns, a learning pipeline, a broker bridge, a journal) was cut in one pass
on 11 Sep 2026 because it was tracking, and tracking was work nobody was
going to do; its notes are in the git history before that commit. What was
kept is what had been proven by execution: the market-data transport with
its live-run rules (the `sip` hold-back, the stable de-dup, the closure
read off the frames), the Resend transport with its test-mode respelling,
the prompt cache, and the discipline below.

## Standing rules

**Every change sweeps the docs.** `README.md` and `.env.example` state
facts about thresholds, schedules, files and failure modes. A change is not
done until both are true for the code as it now stands.
`tests/test_docs.py` holds the mechanically checkable ones (the numbers the
README quotes are read off the modules; the workflow inventory; the fixture
variants; the required variables) and prose still needs a human.

**No line numbers in comments or docs.** Cite functions. `run_evening()` is
stable; `pipeline.py:412` is not.

**Prove a test can fail.** When you add or change a rule, delete it and
watch the suite go red; then break a rule the test does NOT name and confirm
the test still passes for the right reason. Four shapes of test that cannot
fail have been found here: one that passes because a different rule
rejects; one that passes on an incidental fact about the fixture; one that
compares a value against the name it came from; and a duplicate definition
that silently replaced the test being edited. A test whose answer depends on
the hour it runs is the worst kind: every night in `tests/test_pipeline.py`
is pinned to an instant.

**Every strategy number is a named constant read by its own code and
archived in the module's `RULES`.** `tests/test_plan.py`'s literal guard
refuses a bare number inside a function body; `quality`, `breadth`,
`watchlist` and `scans` keep the same discipline. `build_rules()` nests
every module's `RULES` into `data.json` and `app.rules_version` digests
them, so two records made by different numbers cannot be read as one.

**Verification is by execution.** A claim argued rather than run is a lead,
not a finding. Reproduce a crash before fixing it; render a page before
describing it; drive the pipeline through the doubles before saying what it
writes. This applies to reviewing agents too: an agent that died mid-run
returns null, and null is not "refuted".

**Check that a fix did not introduce a defect of the same class, and sweep
for the next instance before calling the class closed.** The class this
repository produced most often: code reads a structure off disk, accepts a
shape it never indexes into, and a later consumer breaks after every paid
call has been made. `record.pick_problem()` and `report.validate()` are
shape checks one level in; a malformed pick is dropped and named, an
unreadable file is set aside beside itself, never overwritten.

**A fixture is what the pipeline writes.** `tools/make_fixture.py` drives
`run_evening()` through the same doubles the tests use; a generator that
took a different path could only be checked against itself. `--check` in
CI holds the committed fixtures to it.

## Environment constraints

- **No live market data here.** The sandbox proxy blocks Alpaca, Yahoo,
  stockbee.blogspot.com and x.com. Anything needing a real trading day is
  validated by a dispatch of `evening.yml` (dry run) and its log. Do not
  fake a result.
- **Free Alpaca plan.** `sip` daily bars with the request window sixteen
  minutes behind the clock, proven on the first live run; `delayed_sip` is
  refused by the bars endpoint and accepted by the snapshot endpoint the
  intraday check uses.
- **The interpreter is part of the environment.** This sandbox runs Python
  3.11 and pandas 3.0.5; CI runs 3.12. A generated artifact is only as
  reproducible as its arithmetic (`math.fsum`, rounding once).
- **Playwright's Chromium is installed globally beside node**;
  `tools/chart_check.mjs` and `tools/page_smoke.mjs` find it there or on
  `NODE_PATH`. Run the smoke with `--shots` and LOOK at the screenshots.
- **Do not edit the tree while a mutation harness is running**, and commit
  only the files of agents that have finished: two WIP commits captured
  mutants mid-harness.
- **`secret-scan.yml` reads a rule key with digits as a credential.**
  gitleaks' generic-api-key rule fires when a `key` field holds a lowercase
  value with digits in it, such as `abnormal_10pct`, in a module, the record
  or a fixture; `.gitleaks.toml` allowlists a lowercase underscored value on
  those paths only, and nothing else. A push scan covers only the pushed
  commit, so a red on one push is green on the next: a pull request scans
  them all, and so does this note if it spells the field out. Watch the
  scan, not only the tests.

## The shape now

`pipeline.run_evening()`: preflight → universe → fetch (chunked, budgeted)
→ session state from the bars → breadth → scan and checklist → charts and
Claude (down-only) → plans and the cash budget → the record (`picks.json`,
open plans, scorecard) → `report.build()` and validate → email. Exit codes
0/1/2/3; seven problem words; `run.status` closed on a closed night.
`run_intraday()` is dispatch-only and never commits.

The page (`docs/app.js`) is a small hash-routed application over the
record: Explore (the market in a line, two stage cards that always say how
many of their stocks carry a ticket, one selectable card per stock, one
stock in focus with its chart, four decision answers, the action area --
the design system's `.sc-actionbar`, a row on a desktop and a stack on a
phone -- and four disclosures), Record, Market and Method, with the
tickets and the scan as disclosures under the workspace and one next action
under every view. It computes one thing of the market — the status chip
from the record's session and the ET clock (`status()`) — and prints
everything else verbatim, including the six cover sentences and the plan
instructions. `buildModel()` is the one adapter, and every status it gives a
stock is read off a field the run wrote (`trades[]`,
`cash_budget.cut[].kind`, `plan.eligible`, `plan.action`, `quality.vetoes`,
the grade against `rules.pipeline.trade_grades`); nothing in the browser
scans, grades, sizes or fetches. `parseHash()` and `applyRoute()` are the
router: the selection is remembered per stage, the hash is rewritten to the
resolved route without a history entry, so Back works and a bookmark
reloads to its stock, and the old one-page anchors map onto the routes. The
chart (`docs/app-chart.js`) is annotated SVG on the SpicyChicken design
system snapshot under `docs/design-system/` (v2.11.0): one panel, two
captioned control groups (`view`, `range`, each a `.sc-field--group` the
group names with `aria-labelledby`, because *setup* is a mode AND a range),
Setup | Candles | Line over one geometry (`SCStock.chartGeometry()`), a Setup range that
frames the base (`rangeSlice()`), the level labels in a reserved gutter
with leader lines while the lines stay at their exact prices, the trigger
and the limit told apart, an aim past the visible range named in a
reference area; a coil is drawn with its box and its trigger and no burst
candle, and a name without archived bars gets the chart-unavailable
state. The mode, range and close-line choices are remembered in this
browser (`spicystock:chart:v1`). `pipeline.SERIES_TOP` bursts by rank carry
their bars beside the trades, the cut names and the closest miss, so a
chosen burst has its chart without a second fetch. Under Bursts the cards
have a Map twin (`docs/app-map.js`, restored from the `29e3205` signal
map): the session's gain against its volume ratio, every point a recorded
number, the selection shared with the cards, the search and the chooser,
a table under
it and the names it cannot plot listed by reason. The ratio is read one way
everywhere (`volumeRatio()`: the row's own field, the scan's measurement
for every burst since the dollar scan carried it; for a record from before
that, run 46 and earlier, the checklist's two-place copy, said to be the
checklist's in the measurements; else missing and said so, zero a value).
Following (`docs/app-follow.js`) is a shelf at the end of Explore: one
click keeps a setup's own snapshot and suggested whole-share quantity in
this browser only (`spicystock:following:v1`, versioned, keyed by kind,
symbol, session and rules identity, a corrupt store set aside), an
optional reference size is labelled the reader's, a later observation is
read off the record's `observations` block (`pipeline.observations()`, the
newest archived bar per signal name for `OBSERVATION_DAYS`), and nothing
of it reaches the record, the mail or the scorecard. A page over a fixture
says so: `data-ss-demo`, a chip, a notice and a marked simulated
chart-reader reply.

Three contracts the ticket-record closeout fixed, each pinned by tests:
a fixed-quantity ticket is sized and its stop judged at its LIMIT, the
highest fill it permits (`plan.burst_plan()`, `plan.anticipation_plan()`,
`plan.SIZING_BASIS`), and a ticket whose stop is past his 4% line there is
withheld with its setup kept; a daily bar establishes a fill only at the
next open inside the ticket (`record.fill()`, `record.KNOWN_FILL`), and a
trigger crossed after the open, an open past the limit or under the skip
line that could still have filled, or a fill-day low under the stop is
`uncertain` with a reason, walked nowhere, scored nowhere, counted by
reason and still holding its model slot; every sale in `plan.follow()` is
whole shares with `shares` and `remaining` on the event, a position that
reaches zero settles there, and `record.r_multiple()` weights by quantity.
The page and the mail say "open model plans" and "model allocation over
configured sizing assumptions", never what the reader holds.

What is measured offline: 1080 tests, the chart check, and the page smoke
over six fixtures walked through every view, stock, search, the chooser,
the keyboard, deep links and the old anchors, then the phone and the stale,
failed, field-dropped and no-record states. What is NOT: the full-market
fetch time from a runner (the dry-run dispatch measures it), a real Claude
reply to a real chart, Resend delivering, Pages building after the
commit-back. Each of those is observed on the first live night, and this
file should record what each one found.

## The v2 mutation pass

Twenty-one mutants over the rules this build added (the fill rule's three
boundaries, the R halves, the open-plan window, the read threshold, a
flat exit, the re-run replacement, the fixture refusal, a NaN bar, the
nights cap, tonight's picks in the window; the grade clamp, the graded
keys, the closed status, the fixture nights, the slot count, the
unavailable count, the coverage fraction; the budget's at-risk sum and the
dated schedule's first day). Twelve killed on the first pass. Of the nine
survivors, eight were holes in the tests and were closed with the test each
showed was missing -- the clamp was tested only downward, the day's high
exactly at the trigger sat on no case, an exit at R = 0 was counted
nowhere, the fixture-inheritance test ran on the fixture's own session so
the inherited night was replaced by tonight's and hid -- and one was two
spellings of one rule (`run_status()` now, one place). All twenty-one die.

## The v2 audit, worked

Two reviewers by execution over the merged commit, one on the run and the
record, one on the page and the mail. The first returned eleven findings,
every one reproduced here before it was touched; the two highs were both
about a sentence the record would have published as fact. A fill at the
trigger later in the day was read against that morning's open, so a burst
whose low sat inside the entry zone was "stopped at the open" of a position
that did not exist yet, and the scorecard booked -1R on a hold: the fill day
is walked from the fill now, and only its close is known to have printed
after it. And a closed night said "the plans from <session> stand" over an
empty page: the previous session's tickets are carried verbatim now and its
picks read as plans that have had no session yet. The mediums: an A+ burst
the account could not size to a whole share headlined as a trade and
entered the record as a zero-share pick (a trade is a plan with an order);
the thin-night branch died in breadth over a calendar that lacked the
session (breadth counts the names that printed); a name that stopped
printing after its pick read "buy per the plan" and held a slot; a typo in a
workflow variable was a traceback rather than a preflight sentence; the SPY
line's test could not fail because the fixture's SPY moved the same every
day. Each is pinned by the test the finding named.

The second reviewer read the page back in Chromium and the mail through its
own renderer, twelve findings. The high was mine and a day old: the chart
card's collision pass re-declared `var kept`, the name the date ticks were
gathered under, so every card chart lost its date axis (the chart check
holds the card's axis now). A holiday was filed under the last OPEN session,
so the closed dot replaced the night before and the holiday read "missing"
(`night_session()`). One absent cosmetic field took the whole page down and
four printed `undefined`/`NaN` (the smoke drops eight fields in turn now).
The stop pill sat on the base label at phone width (the box and burst
labels are dropped rather than laid over it; the day marks moved to the pane
floor). The chip said "run failed" from 7 PM while the repo's own retry
fires at 8:16 (pending runs to 9 PM). The scorecard's readable chip was the
page's own arithmetic over `plans` where the record's is over `settled`
(the record's word now). Three vocabularies for one plan status (one map,
held equal across page and mail). The closest miss named a qualified trade
the slot cap had cut (cut names are not misses; beyond-cap bursts get their
card, with no order). The hold button pointed at an anchor that did not
exist. The hold bar assumed the stop under the entry (a trailed stop passes
it). And the mail said things the page would not: the recorded problem
message, an alert with no ticket and no caveat, ratios at one decimal.

## Open leads, written down rather than worked

- An upper bound on the day's gain is a strategy decision this build does
  not take; a ≥15% day halves the size as a hazard and is never a veto.
- The scorecard's fill rule is the ticket's own mechanics on daily bars; a
  fill at or over the trigger at the open is assumed to be at the open, and
  a day order on a session the name's frame lacks is walked from its next bar.
- `MAX_READS` is twelve by mechanical grade; a night with more A-quality
  bursts than that grades the rest by the checklist alone (`claude_partial`
  is not raised for those, only for names asked and unanswered).
- **The +4% ceiling and his 4% stop line cannot both hold at the limit.**
  SETTLED 12 Sep 2026, the one-rule alternative adopted: the ticket's limit
  is `min(day2_spent_above, floor_to_cents(stop / (1 - MAX_STOP_PCT/100)))`
  (`plan.burst_limit()`), and the +4% is the outer extension threshold on
  its own field. The last checkpoint carries what it cost and what it
  rescued. What it does NOT settle: whether the narrower permitted range
  fills as often in the market, which no archived record can say.

## Checkpoint, 11 Sep 2026 — the ticket-record closeout

**Revision.** Branch `claude/spicystock-ticket-record-fixes-su1nh1`, cut
from `main` at `fd9b79e` (the merge of the reviewed `claude/amazing-
ritchie-k95p6g` tip `22459ef`; the trees are identical). The commit on top
of it is the closeout; nothing else is on the branch. The two project
inputs the review named (`SpicyStock_Project_Context.md`, the field-guide
PDF) were not present in the workspace and were not read.

**Reproduced, then fixed, all three findings**, by `scratchpad/repro/`
scripts against `fd9b79e` before any edit: the 24-share ticket sized at
close+1% risked $108 at its $104 limit against a $50 budget with the stop
4.33% away (now withheld, the setup kept); cases A, B and C read as
`not_filled`, `not_filled` and `hold` (now `uncertain` with
`open_above_limit`, `open_below_skip`, `stop_sequence`); the three-share
plan told the reader to sell 2 of 3 and scored +5R at 50/50 (now +6R, and a
one-share plan settles at its one sale with no phantom half). Nothing was
already fixed on the branch; nothing was disproved.

**Checks run at the closeout commit** (all offline, through the doubles):
`pytest tests/ -q` 1019 passed; `python tools/make_fixture.py --check` 7
fixtures current; `node tools/chart_check.mjs` 139/139; `node
tools/page_smoke.mjs --shots <scratch>` 764/764 with the clipboard read
back equal to the printed ticket; the digest rendered from the full
fixture through `report.digest_html()` and read for the affected fields,
not sent. Screenshots at 1280 and 390 px, dark and light, were looked at:
the trade card's new facts (sized at, planned risk, the four ticket terms),
the withheld TSLA card, the three-row model-plan rail (a hold, an
uncertain fill, a 2-of-3 sale), the allocation line, the scorecard's
uncertain count. NOT run, and not claimable: a live fetch, a real Claude
reply, Resend delivering, Pages building.

**Settled here.** Sizing price = the order's limit for both families;
withhold rather than rescue a ticket; `uncertain` is one status with four
reason codes and holds a slot; whole-share sales with quantity-weighted R;
no plain-limit fallback; the ticket's terms printed beside it; the page and
mail vocabulary (`Open model plans`, `Model allocation`, `ticket withheld`,
`No ticket:`); `rules_version` moved with `plan.sizing_basis` and
`record.known_fill`, so older records cannot be read as this one.

**Keep / fix / defer / omit.** Keep: everything above and the design.
Fix next if it bites: a withheld A-quality burst shares `beyond_cap` with
slot-cap cuts (the `kind` tells them apart; the contract says so). Defer
to Astra: the ceiling-versus-stop-line question above; intraday data for
the uncertain cases, if the count of them matters. Omit: a scenario engine, a portfolio view, brokerage
execution.

**Next action.** Dispatch `evening.yml` with dry_run on a real trading day
and read how many A-quality bursts are withheld at the limit; that number
is the input to the ceiling decision.

## Checkpoint, 11 Sep 2026 — the visual discovery experience

**Revision.** Branch `claude/spicystock-ticket-record-fixes-su1nh1`, one
commit on top of the closeout `d6b0b95`: the page rebuilt as a small
client-side app on the same static hosting (no framework, no server, no
new data service), the smoke rewritten for it, the fixtures regenerated
for `SERIES_TOP`.

**What was built.** Four views behind the masthead, the state in the hash.
Explore: a compact market bar (verdict, dek, regime and size, session, the
record's own call to action; the run metadata moved to Method), two stage
cards with counts, a column (a rail on a phone) of selectable stock cards
with grade and status chips, a ticker search that switches stage visibly,
a *Choose stock* dialog with focus management, and one stock in focus: the
annotated chart with 60/120-session tabs, a four-item decision summary
from the record's own sentences, an action area whose only button is
*View conditional plan* or *Inspect conditions*, and four disclosures
(conditions, plan/sizing/order, model exits, provenance). The tickets and
the scan are disclosures under the workspace, every name a way to its
card. Record, Market and Method carry what the one-page layout had;
the old anchors map onto the routes.

**Checks run** (offline, through the doubles): `pytest tests/ -q` 1019
passed; `python tools/make_fixture.py --check` 7 fixtures current after
regeneration; `node tools/chart_check.mjs` 139/139; `node
tools/page_smoke.mjs --shots` 2000/2000, the clipboard read back equal to
the printed ticket. Five page mutants were run against the new smoke: an
unnamed unknown symbol, an unnamed chart-unavailable state, a cut reason
dropped from the action area, and a per-stage selection forgotten on
every route each turned it red (24 failures for the first three, 385 for
the fourth); a stage button navigating without the remembered symbol was
equivalent (the memory lives in `applyRoute()`), not a hole. Screenshots at 1280×900 and 390×844, dark and light, were
looked at: the first screen shows the market bar, the stages, the first
stock and the upper chart (desktop) or the stage cards, the search and
the chooser button (phone); the withheld TSLA card with its reason and no
order; COIL's coil chart (box, trigger, no burst candle); the record view;
the stale page with every ticket withheld; the no-record page. The
chooser's items were squeezed by the dialog's column flex on the first
pass and fixed (`flex: 0 0 auto`).

**Not run, not claimable.** A live fetch, a real Claude reply, Resend,
Pages building, and any judgement of the ticket/replay open leads or of
trading edge: this milestone is the page, not the method.

**Keep / fix / defer / omit.** Keep: `buildModel()` as the one adapter,
the hash as the state, statuses read off record fields, the decision
summary from supplied sentences only, one secondary button per stock and
one spice callout per page. Fix next if it bites: the chart's card labels
can crowd the top-right gutter at 1280 on a tight bar (a chart-module
matter, covered by `chart_check`); a pick card's status chip wraps under
its grade in a narrow column; `test_claude_md_is_short_and_names_the_
fixture_count` measures the line count of prose that has had its line
breaks collapsed, so its cap cannot fail. Defer to Astra: the +4% ceiling
versus his 4% stop line (unchanged); whether `SERIES_TOP` should be every
burst (the record grows by roughly 12 KB per name). Omit: purchase entry,
a journal, portfolio balances, a scenario engine.

**Next action.** Dispatch `evening.yml` with dry_run on a real trading day,
open the committed page against the record it writes, and walk the
ten-step journey once on a phone: the first live night is the only test
of the full-market record's size and of Pages serving the hash routes.

## Checkpoint, 11 Sep 2026 — visual exploration and one-click follow-up

**Revision.** `a63a6d9` on `claude/spicystock-ticket-record-fixes-su1nh1`,
merged to `main` as `74bff88` (#51). SpicyHome was read at `9c24129` and
not written: taken from it were the bounded panel with a compact header
strip, segmented controls in one row and the button hierarchy. The
component restored is the burst map of `29e3205` (`docs/signal-map.js`:
a button per point, stacked coincident points, a table twin, one
selection with the cards).

**What was built.** One chart panel (`detailChart()`): Setup | Candles |
Line share `SCStock.chartGeometry()`, so levels, labels and tooltips
agree in every mode; the Setup range frames the base, the caption
discloses the sessions, the levels and an off-range aim, and the labels
sit in a gutter (`rightLabel()`) while the lines stay at their prices.
The Map is `SCStock.map.render()` over `gain_pct` and `volume_vs_prior`.
Following is `SCStock.follow` over a versioned browser store; a followed card prints the saved levels, the latest close from
the record's new `observations` block (`pipeline.observations()`, from
bars already fetched, refused by `report.validate()` when malformed) and
the movement since the signal close, marked as not a P&L. A page over a
fixture wears `data-ss-demo`, a notice naming the fixture and a marked
simulated chart-reader reply.

**Checks run** (offline, through the doubles): `pytest tests/ -q` 1023
passed; `python tools/make_fixture.py --check` 7 fixtures current;
`node tools/chart_check.mjs` 163/163 with its new panel section;
`node tools/page_smoke.mjs --shots` 2277/2277 with `checkModes`,
`checkMap`, `checkFollowing` and three more dropped fields. Its first run
found eight holes, all closed: a two-row panel header and the notice had
pushed the chart and the phone's search under the first screen (one
strip, a one-line notice now); the store keys were dotted lowercase
digit-bearing values beside the word `KEY`, what the secret scan reads
as a credential (colons now); the browser's validation bubble swallowed
the size sentence (`novalidate`); the record's instruction says
"filled", so a followed card quotes it under *the record says*.
Screenshots at 1280 and 390 px, dark and light, were looked at.

**Run live.** Run 45, a dry run on `74bff88`, then run 46, the first
real publish (`skip_email`, commit `7380a97 run 2026-09-11`, Pages
green): 3009 names, the fetch 36 seconds against the 900-second budget,
3008 measured, 400 bursts (51 A, 96 B, 68 C, 185 skip), twelve reads,
164 seconds end to end. Breadth was red (141 up 4% against 72 down,
10-day ratio 0.74), so *Stand aside.*, no plans, 40 observations. The
record is 3.4 MB, 2.5 MB of it the 400 bursts at 5.7 KB each and 16 KB
with bars: the burst table is the first thing to trim. A red night
offers no ticket, so the withheld count the ceiling decision needs is
still unobserved. NOT claimable: Resend, and any judgement of the ticket
and replay leads, live data quality or trading edge.

**Settled here.** One panel, one geometry, three modes; the map is the
cards' twin, not a third stage; Following saves a snapshot, never a
purchase, a fill or a P&L, in this browser only.

**Keep / fix / defer / omit.** Keep: everything above. Fix next if it
bites: the header strip holds one line at 1280 by fifty pixels; a map
under `LABEL_MIN_WIDTH` labels only the chosen, focused and hovered
point. Defer to Astra: the +4% ceiling versus his 4% stop line
(unchanged). Omit: trade logging, a portfolio, a journal, a scenario
engine.

**Next action.** On the next green or yellow session, dispatch the dry
run again and count the A-quality bursts withheld at the limit from its
artifact, downloaded outside this sandbox; then open the page over that
record on a phone and walk the three modes, the map and one follow.

## Checkpoint, 11 Sep 2026 — first real-data acceptance and the volume-ratio repair

**Revision.** Branch `claude/spicystock-ticket-record-fixes-su1nh1` from
`e93a423`, `origin/main` merged in twice: `7380a97` (run 46, the first real
record, SHA-256 `dd516119…`) as `b16b0a9`, then `ece47f1` (run 47, the
6:16 PM schedule). One work commit on top; the published record untouched.

**Reproduced.** Over the unchanged run-46 record in Chromium: *400 bursts ·
142 plotted · 258 without a measurement*; every omitted row a $-only scan
row, `volume_vs_prior` null beside a numeric `quality.burst.volume_vs_prior`
(RVTY: null against 0.86), and every consumer printed "—". Cause:
`scans._dollar()` never measured volume against the previous session, so
`scan_frames()` wrote null for a day only that scan saw.

**Changed.** The dollar scan carries `prev_volume` and `volume_vs_prior` by
the same `_ratio(v, v1)` at `scans.RATIO_DECIMALS`, None when the previous
session printed nothing, and the day still matches. `scan_frames()` reads
`burst or dollar`; the checklist's two-place copy is untouched. The page
reads the ratio one way (`volumeRatio()`): the row's field when a finite
number of zero or more, else the checklist's copy and the measurements say
so, else missing and said so; a copy that is not the field's rounding is
printed beside it; every consumer goes through it. The chart reader's
metrics carry the ratio for a $-only read now. The fixture market has a
$-only day (DLLR, 0.8649 in the row, 0.86 in the block).

**After.** 400 of 400 plotted (401 of 401 on run 47's record); RVTY at
+2.79% and 0.86×, "+2.8% on 0.9× volume" everywhere. Tests 1027, four new.
Smoke 2507/2507 with `checkVolumeReadings`. Chart check 163/163.

**The journey, over the real record** (Playwright, 89/89, 1280×900 and
390×844): *Stand aside.*, no ticket chip, no order on any route; RVTY card
→ detail → Setup | Candles | Line agree on dates, prices, levels and
tooltip; the Map selects by click and by ArrowRight + Enter; search and
the chooser reach CVX and MPC, which have no archived bars: the
chart-unavailable sentence, never another chart; rapid switching lands on
the last card; one click follows RVTY "for observation, no ticket", the
reference size is the reader's, nothing public changes, the follow
survives a reload and *Open chart* reopens it. Unthrottled: 3.37 MB
fetched in 28 ms, parsed and first rendered in 210 ms, a selection
in 24–36 ms, the map in 100 ms. Phone-shaped, CPU 4×, 4 Mbit/s: the fetch
is 6.8 s of a 9.4 s wall (uncompressed; gzip is 287 KB), parse and first
render 1.2 s, a selection 65–150 ms, the map 370 ms. Not a physical phone or
the public network (the proxy refuses github.io). Uncertain outcomes
have nothing to show on a red night.

**Observed, not fixed.** On the phone the map's corner is one stack (RVTY
+199) under a 182× outlier and a tap at ATEC's centre lands on a
stack-mate; keyboard, table and the stack sentence reach every point. Run 47 (email delivered) re-ran the session on later bars: PDS
joined at rank 1, 116 volumes moved; the 4:51 PM window is not final.

**Settled.** One field, one meaning, whichever scan measured it; the page
never invents a measurement.

**Keep / fix / defer / omit.** Keep everything above. Fix next if it bites:
a log or clamped volume axis. Defer to Astra: the +4% ceiling against his
4% stop line (unchanged); `SERIES_TOP`; the withheld count, still
unobserved. Omit: trade logging, a portfolio, execution.

**Next action.** Merge this branch so the next run writes the ratio; on the
next green or yellow session dispatch the dry run and count the A-quality
bursts withheld at the limit.

## Checkpoint, 12 Sep 2026 — the map's scale and its taps

**Revision.** Branch `claude/volume-repair-mobile-entry-zo54u9`, started at
`5649c71`: the volume repair `d1fb272` with `origin/main` (run 47) merged in,
never merged to `main` and carrying no pull request of its own. `docs/data.json`,
`docs/picks.json` and the universe directory are byte-for-byte `origin/main`'s
throughout, and the repair itself was not re-done.

**The repair is merge-ready, measured at `5649c71`** (offline, through the
doubles): 1027 tests, `make_fixture.py --check` 7 fixtures current, chart check
163/163, page smoke 2507/2507. Not run here, not claimable: a live fetch,
Resend, Pages, CI itself.

**Reproduced in Chromium over that unchanged record** (401 bursts, session
2026-09-11, `scratchpad/repro/map_repro.mjs`): the volume axis read 0.0×, 45.8×,
91.5×, 137.3×, 183.0× against a median burst of 1.08×, and 391 of 401 points sat
within five pixels of the pane floor on a phone, across twelve distinct pixel
rows; the selection sentence listed forty-nine tickers as sharing one spot. A
point's hit box is 44 px, so 393 of 401 markers had another stock's button over
their own centre: a tap at RVTY's own centre selected PDS on a phone, QCOM at
1280. Over the six page fixtures, thirteen stock pages printed "for observation,
no ticket: no ticket".

**Changed.** The volume axis is compressed and the gain axis is not
(`SCStock.map.volumeScale()`): `log1p(v / VOLUME_KNEE)` over
`log1p(top / VOLUME_KNEE)`, the top still the largest recorded ratio with the
headroom the linear axis had. It is a POSITION and nothing else — the ticks are
real ratios off a ladder thinned by `TICK_MIN_GAP`, every point keeps its
recorded value, nothing is clipped, binned or winsorised, and `log1p(0)` is 0, so
a zero ratio is ON the axis line and still told apart from a burst with no
measurement, which is not plotted and is listed by name. A tap is resolved by
distance from the tap within `TAP_RADIUS` (half the 44 px box the browser
hit-tests), never by which marker was appended last: one point in reach is chosen
outright, more than one opens a compact nearby chooser, nearest first, that
chooses nothing until the reader does. Enter or Space on a focused point names
one point and takes it — measured in Chromium, a mouse click and a touch tap both
report `detail` 1 and a `pointerType`, Enter reports 0 and `''` — and the crowd
stays reachable by a *Nearby stocks (N)* button beside the selection. One radius
feeds the badge, the spoken label and the chooser. The duplicated copy is one
helper each way (`noTicketLead()` for the decision summary, the short status
words; `noTicketPhrase()` for the plan disclosure, the record's reason once and
never after a lead that already said it; the Following hint takes the short
words, because the action area above it has just printed the reason in full).

**After** (same script, same record): ticks 0×, 0.25×, 1×, 3×, 10×, 25×, 50×,
183× on a phone; 62 distinct pixel rows for 401 points against 12, one point on
the floor against 391, 325 distinct spots against 129. A tap at RVTY's centre
opens a chooser of the 323 stocks within a finger, RVTY first, and choosing it
selects RVTY in the map, the cards, the chart and the table. Zero duplicated
phrases over the same 35 stock pages. **Not fixed, and not fixable this way:**
401 points in a 262×200 px pane is 0.13 points per square pixel, so even at an
8 px radius the median point has 72 neighbours on a phone. The map is now a
readable distribution with an honest way out of any tap; the cards, the search
and the table are still the precise way to a named stock.

**Checks run** (offline): 1028 tests; 7 fixtures current; chart check 163/163;
page smoke 2623 with `checkMapScale` — the outlier, zero, missing, the
crowded tap at real coordinates (a finger on the phone, a mouse at 1280) and the
chooser's lifecycle. Its first run found four holes, all closed: `data-nearby`
did not exist until a chooser had opened; two points recorded alike had a third
neighbour, so the count assertion was over-specific; and the decision summary had
swallowed the whole withhold reason where a short status word belongs.

**The mutants and the review.** Eleven page mutants; eight died on the first pass and
**`zero off the floor` survived** — a hole of the third shape this file names: the
check compared the zero POINT against the 0× LABEL, and both are drawn through the
same `at()`, so moving one moved the other. The pane floor is read off the vertical
grid lines now, which the scale never touches, and it dies. A second check could
not fail for the reason it named: "the ticks are not evenly spaced, because the
axis is compressed" was reading the tick LADDER, which is uneven on a linear axis
too; it asks where the 1× tick sits now, which on a linear axis over a 183× top
would be half a percent off the floor. And `stale panel survives` survived twice
before it bit: the panel closed anyway because the click moved the focus out of it,
and because selecting a different stock lengthened the page, raised a scrollbar,
narrowed the pane and redrew the map. A deep link moves the shared selection and
nothing else, and that is the case the check uses.

Three survived and each showed a hole, closed with the check it was missing.

A reviewer reading the chooser back in Chromium returned four, all reproduced, all
fixed. Two were the same defect twice over: cancelling handed the focus to the
marker the browser had HIT-TESTED — the one the chooser exists to refuse — so a
reader who tapped LMAT, pressed Escape and then Enter got QCOM, a stock the chooser
had not even listed (the silent topmost, one keystroke later); and a selection made
elsewhere left the panel standing over a fifth of the pane, still describing a tap
that was over. Then: the panel claimed `aria-modal` over a page that stayed live
behind it — 1646 buttons still tabbable — and held Tab in against the claim, so it
is a labelled popover now that Tab may leave and leaving closes; and dismissing it
by a press on bare pane or a redraw dropped the focus on `<body>`, because the
press's own default action runs after the handler. A fifth, that a crowded point's
accessible name promised "choosing it opens the nearby list" when the keyboard
does the opposite, is a wording fix. A reviewer over the whole diff added one
more that the standing rule demands and I had not swept: the same doubled phrase
was still in the MAIL (`report._no_ticket_lines()` printed "No ticket for TSLA:
ticket withheld: ...") and in the page's own budget line. One list of leading
words now (`report.NO_TICKET_LEADS`, `saysNoTicket()` on the page), and
`tests/test_docs.py` holds the two equal, as it does the status words. The same
review found the smoke's scratch records — full copies of a record, carrying the
rule `key` fields the secret scan reads as credentials — written inside
`tests/fixtures/page/` on a path `.gitleaks.toml` does not allowlist and nothing
ignored; one anchored `.gitignore` line covers them. A sixth is measured and left alone: on a
401-burst night 397 of 401 points have a neighbour within a finger on a phone, so
nearly every tap opens the chooser. Narrowing the auto-choose radius to the dot's
own was tried and moves 4 of 401 to 16 of 401 — a second constant for nothing. The
map is a readable distribution with an honest way out of any tap; the cards, the
search and the table are the one-step path to a named stock.

**Keep / fix / defer / omit.** Keep everything above. Fix next if it bites: on a
record whose smallest ratio is well over zero the pane's bottom fifth is empty,
the price of keeping 0× on the axis; `test_claude_md_is_short_and_names_the_
fixture_count` still measures collapsed prose, so its cap cannot fail. Defer to
Astra: the +4% ceiling against his 4% stop line. Omit: trade logging, a
portfolio, execution.

**Next action.** On the next green or yellow session dispatch the dry run and
count the A-quality bursts withheld at the limit from its artifact.

## Checkpoint, 12 Sep 2026 — the entry-limit reading

`tools/entry_limit_study.py` is a reading, not a check and not a rule: it
changes no production number, no record, no regime, no historical ticket and no
scorecard, writes nothing but an explicit `--json`, reads no forward return, and
is not a backtest or a claim about either ceiling. It answers the question this
file has deferred three times.

**What it compares.** The current fixed ceiling (`close + ENTRY_ABOVE_PCT`)
against `min(entry_high, floor_to_cents(stop / (1 - MAX_STOP_PCT/100)))` over
`plan.burst_stop`'s existing candidates in their existing order (`burst_low`,
then `half_range`). The synthetic `max_stop` is never read, so it can rescue
nothing; a proposal is admitted only where `stop < trigger <= limit` still holds
— the assertion `plan.fidelity_orders` already makes — and both columns are
sized at the effective limit under the record's OWN regime multiplier. The
"current" column is `plan.burst_plan()` itself, and `verify()` reproduces every
plan a record carries down to the share count, the action and the money; a drift
is an exit code, not a printed line.

**It is the same cascade at a narrower ceiling, proved per row.**
`production_agrees()` runs `plan.burst_stop` AT the proposed limit and requires
the same basis at the same price inside his line; the study raises rather than
reports if it ever fails. 380 of 380 proposals agree over run 47's record. The
first pass did not: the record carries raw four-decimal lows (ULTA 531.5625) and
`burst_plan` rounds the bar once on the way in, so candidates priced off the
unrounded value proposed stops a cent from the ones the run would write. The bar
is cent-rounded once now, as `burst_plan` rounds it.

**What it found on run 47** (401 bursts, session 2026-09-11, red). Coverage 401,
missing inputs 0. The stop rule rejects **381 today and 21 under the proposal**;
360 are rescued, 350 of them sizing to a whole share at full size. All 20
currently eligible move, their basis going from `half_range` to the tighter
`burst_low`. Kept apart from the stop rule, each under its own gate: the regime
excluded all 401, grade 349, a veto 148, the budget none. Of the **52 that would
reach the stop rule on a green night, 0 are eligible today, 50 under the
proposal, and 47 of those size to a whole share** — that last is the number the
ceiling decision wants, and a red night could not otherwise have shown it.
Downstream of a narrower limit: the indicative entry (close +
`ASSUMED_SLIPPAGE_PCT`, what `targets()` and `exit_schedule()` are quoted from)
sits ABOVE the proposed limit for 96 of 380; the displayed +4% skip line stops
being the limit for all 380 — `skip_if_open_above`, `pre_open_check`, the order
disclosure, the Fidelity ticket and the Following snapshot all quote it — and 3
proposals leave a buy stop-limit no room at all above its own trigger, 38 less
than half a percent.

**The review, worked.** A reviewer by execution returned eight findings over the
study, every one reproduced, every one fixed. The one that mattered was a
contract breach: "excluded by the budget" tallied every `cash_budget.cut[].kind`,
and `withheld` IS the stop rule's own refusal — so a withheld burst was counted
in the stop-rule block AND under the budget, the very separation the study
exists to keep (`BUDGET_CUT_KINDS` is `slot_cap` and `equity` now; `withheld`,
`no_new_longs` and `no_shares` are each reported under their own gate). Then:
the current column had been sized at a neutral 1.0 while the report said it was
the run's answer, so on a yellow night the run's 2-share ticket read 4 — both
columns take the record's multiplier now, `verify()` holds the share count, and
a full-size counterfactual is printed beside it and labelled; "rescued" counted
plans the account cannot size to a whole share, which production refuses as
`no_order`; a burst row with a bad `gain_pct` or no ticker killed the run with a
traceback where `make_plans()` logs and skips; the degenerate band counted
(`limit == stop`) was impossible by the admission rule while the one that
happens (`limit == trigger`) went uncounted; a drift exited 0; and `--json`
keyed by basename, collapsing the natural comparison of two `data.json`s. Two of
the tests were shapes this file names: the yellow-night grade test leaned on
yellow.json having no grade-A burst, so both grade lines selected the same rows;
and the separation test asserted only `count(X) + count(not X) == total`, which
holds for any predicate — the current column could have been replaced wholesale
by the proposed one and stayed green.

**Checks.** 1056 tests (28 new). Eight study mutants, all dead; two survived the
first pass and both were holes — one mutant was equivalent until it was
sharpened to admit `max_stop` as a candidate of its own, and `verify()` compared
only fields independent of the bar's gain.

**Settled here.** The study reads; it does not decide. Adopting the proposal is a
method decision with two questions attached: what the indicative entry becomes
when it is above the limit, and what the displayed skip line says when it is no
longer the limit.

**Next action.** Put this to Astra with the 52 / 0 / 50 / 47 line and those two
questions; separately, on the next green or yellow session dispatch the dry run
and check the study's arithmetic against what the run actually withholds.

## Checkpoint, 12 Sep 2026 — the constrained ticket limit

**Revision.** Branch `claude/volume-repair-mobile-entry-zo54u9` from `cdc9d56`;
the published record stays `origin/main`'s to the byte, and nothing was merged,
deployed, dispatched or mailed.

**The decision, implemented.** The reading found 381 of 401 bursts withheld:
the +4% line and his 4% stop line cannot both hold at the limit. The limit is
`plan.burst_limit()` now,
`min(close +4%, floor_to_cents(stop / (1 - MAX_STOP_PCT/100)))`
over `stop_candidates()` — one list the cascade and the ceiling both
read, without `max_stop`, so nothing manufactures eligibility. A candidate is taken only when `stop < trigger <
limit` — strictly OVER too, since a ceiling landing ON the buy stop is a ticket
with no band, withheld with a named `ticket_refusal`. The ceiling floors to
cents (`CENT_FLOOR_EPSILON`): rounding up puts the stop past the line at the
highest permitted fill, 4.39% away at $1.14 for a $1.09 stop. `burst_plan`
raises rather than publish a limit its cascade would not hold.

**Four prices, four rules, four fields.** `entry_ref` the trigger; `limit`
(and `entry_high`, the zone's top) the executable limit;
**`day2_spent_above`** the outer +4% threshold — `skip_if_open_above`, its own
clause in `pre_open_check`, never an order's limit; `planned_entry` =
`min(close +1%, limit)`, the targets' and exits' basis. Swept through
`pick_of`, `pick_problem`, `record.fill()`, the digest and the page.

**Measured offline.** 1076 tests (32 new, over a 200-odd bar-shape sweep that
asserts it reached every branch); 7 fixtures current, `full` reshaped to carry
all four states — AAPL the textbook bar, once withheld, now a $126.47 ticket
under a $129.18 day-2 line; AMD at the ceiling, NVDA capped, TSLA withheld;
chart check 163/163; smoke 2690/2690. **The
screenshots found what the sweep had not:** `dated_schedule()`'s entry line,
which the Following card quotes, still said "Skip it if it opens above
$126.47" — the ticket's limit as a skip rule, the overload this milestone
removes. It buys to the limit and skips at the day-2 line now.

**The mutants.** Fifteen over the code, seven over the page; two survived the
first pass, each a hole. `the oracle's band drifts from production` lived
because no page fixture has a ceiling landing exactly on its trigger, so the
study's sweep carries those bars itself. `the skip row shows the limit`
lived on the first shape this file names: the check searched the whole plan
disclosure for the day-2 price, which the buy row's narrowing sentence names,
so a row printing the WRONG price stayed green. Each row is read by its own
value now (`factValue()`). Both die. A third was in the wrong harness — it
patches `src/plan.py`, which the page smoke cannot see — and dies in pytest.

**The study, reconciled.** It changed sides rather than compare production
with itself: it carries the retired ceiling, which no module has now, beside
`burst_plan()` and an oracle that re-derives the rule and raises if it is not
what was written. Over the unchanged run-47 record: coverage 401; fixed
20 / 381, unchanged; production 378 / 23 against the proposal's 380 / 21,
three rows having a ceiling exactly on the trigger — PENN fell to the midpoint,
SBET and JVA are refused. Green-night 52 / 0 / 50 / **47**, the reading's
line; 93 indicative entries are capped.

**Settled.** The limit is a fillable price, the +4% an extension rule. Fix if
it bites: `limit_narrowed` is derivable from `limit_basis`. **Not claimable:**
a live fetch, Resend, Pages, CI, or expectancy — this changes which tickets
exist, not whether they win.

**Next action.** On the next green or yellow session dispatch the dry run and
check the study against what the run withholds and writes.

## Checkpoint, 12 Sep 2026 — the handoff, validated by execution

**Revision.** Branch `claude/volume-repair-mobile-entry-zo54u9` at
`31628d8`, taken over from an interrupted builder. Verified before anything was
touched: a clean tree, no stray file, no disabled test, no TODO left by
the two commits, the published record still `origin/main`'s to the byte. This checkpoint is the only commit added;
nothing was merged, deployed, dispatched or mailed.

**Every check rerun here rather than inherited.** 1076 tests pass, none
skipped; the seven fixtures are current through the real generator; the
chart check is 163/163. The page smoke is 2690/2690 bare and **2692/2692
with `--shots`** — two checks (the light-theme page's errors, the
Following store recovering after a blocked write) run only when shots are
asked for, and `--shots` is what CI runs, so the tip's 2690 is the bare
number and not a stale one. The suite and the fixture check were also run
under **Python 3.12**, CI's interpreter rather than this sandbox's 3.11:
1076 pass and the seven fixtures still reproduce. GitHub says the secret
scan is green on this tip and on `3248093`.

**The rule recomputed, not read.** `plan.burst_limit()` was run again over
the `full` fixture's four bars: AAPL narrowed to $126.47 under its $129.18
day-2 line, AMD at the outer ceiling ($128.20 both), NVDA's indicative
entry capped at its $128.12 limit, TSLA withheld because both candidates
cap at or under its $124.21 buy stop ($118.32, $124.14). The screenshots
were looked at, not only the exit code: each plan row carries its own
price, the Fidelity sheet writes the ticket's limit with the day-2 line in
its own *too extended over* column, the followed card saves both, and the
phone's map keeps its compressed volume axis and its nearby chooser.

**The study reproduced.** Over the unchanged run-47 record: coverage 401;
the retired fixed ceiling 20 / 381; production 378 / 23; 358 rescued;
every limit at or under its day-2 line; 93 indicative entries capped; the
green-night decision set **52 / 0 / 50 / 47**. PENN, SBET and JVA are the
three ceilings landing exactly on the trigger — PENN falls to the
midpoint, the other two are refused — so the three rows that differ from
the reading's proposal are the band rule, not a rounding accident.

**The mutants killed again.** Fifteen over the code (the cent floor, both
band strictnesses, a synthetic candidate, the entry cap, the day-2 field,
the skip rule, the dated schedule, the order and sizing prices, the pick,
the record's shape check, the fill sentence, the mail) all die, each in
the tests that name its rule and not only in the study's oracle; a bare
`0.96` in `stop_line_ceiling()` dies against the literal guard. Three page
mutants die too: the ticket limit in the *skip if it opens above* row (the
one the tip commit exists for) fails two row-scoped assertions, the same
price in the order sheet's limit column fails one, and a Following
snapshot saving the day-2 line as the limit fails three.

**No defect found, nothing corrected.** Kept as recorded: `limit_narrowed`
is derivable from `limit_basis`; the CLAUDE.md line cap cannot fail
because `prose()` collapses the file to one line.

**Blockers.** None offline. Not run and not claimable: a live fetch, a
real chart read, Resend, Pages, and the CI test job, which runs on `main`
and on pull requests only — this branch has had the secret scan alone.

**Next action.** Unchanged: dispatch `evening.yml` with dry_run on a green
or yellow session and check the study against what the run withholds and
writes.

## Checkpoint, 12 Sep 2026 — three weak points in the Explore journey, two patterns promoted

**Revision.** SpicyStock `claude/vibrant-volta-7ft7cn` from `5515515` (`main`, the
merge of #52); design-system `claude/vibrant-volta-7ft7cn` from `edacaff`, one
commit `6f10309` = **v2.11.0**. `docs/data.json` and `docs/picks.json` are
`origin/main`'s to the byte. **Both pairs are merged since:** SpicyStock
`c3d6d1d` (#53) and design-system `1ffd905` (#22), each a merge commit, so
`6f10309` is on the sheet's `main` and the vendored provenance still resolves.
Merging SpicyStock published: `publish-dashboard.yml` fires on any push to
`main` touching `docs/**`, so Pages built and deployed clean at `c3d6d1d` —
the same run-47 record under the new layout, no record byte changed. No
evening run was dispatched and no mail was sent; the one workflow dispatched
was the sheet's own `check`, to re-read the tag state after the release.

**Rendered before it was edited**, over the unchanged run-47 record and the marked
`full` fixture at 1280×900, 390×844 and 320 px, both themes, the clock pinned.
Three weaknesses, each measured in Chromium rather than argued:

1. **The one action was buried on a phone.** `.ss-action` stacks under 720 px, and
   its paragraph kept `flex: 1 1 260px` — a basis written for a row becomes a
   HEIGHT in a column, so a three-line sentence sat in a 260 px box with 181 px of
   empty bar between it and the only button, ticket and no-ticket alike.
2. **The chart strip was two look-alike rows.** Two `sc-tabs` groups side by side,
   the first with no visible caption and the second captioned only *range*, while
   *setup* is a button in BOTH (the annotated mode, and the window framing the base).
3. **The phone dropped the stage's action state.** `.ss-stage__sub` was
   `display: none` under 480 px — the only line saying how many of a stage's stocks
   carry a ticket — and the verdict began 232 px down an 844 px screen (310 of 800
   at 320 px), under a masthead of three rows and 56 px of page padding.

**Promoted, not re-invented.** Both fixes were patterns consumers had already
improvised, so they went upstream rather than into `app.css`: **`.sc-actionbar`**
(`__more`) — chip, one sentence, one button, a follow-on row — whose phone rule is
the released row basis; and **`.sc-field--group`** with `.sc-field__label`, making
official the captioned `role="group"` SpicyCar was already writing as a bare
`div.sc-field`. Documented in `DESIGN_SYSTEM.md` §6, `VISUAL-RECIPES.md` and two
`CHECKLIST.md` lines, shown in the style guide on a release page that imports
nothing of this repo, version bumped by the one-stream rule. `app.css` lost the
duplicated layout; `docs/design-system/` was refreshed with `build/vendor.mjs`
(22 files, every SHA-256 verified against the source tree, commit `6f10309`).
The snapshot also crossed `271647f…edacaff`, which changed one line: the sheet's
by-line reads *SpicyChicken*, not a person.

**After** (same record, same phone): the action bar 490 px → 252, its sentence
260 → 20, the button directly under it; *view* and *range* caption their own
groups and each IS the group's accessible name; both stage cards say
"N with a ticket · M without" at every width, the count beside the name and no
collision from 320 px up; the verdict starts at 200 px instead of 232.
Desktop is untouched by design.

**Measured offline.** 1076 tests; 7 fixtures current; chart check 163/163; page
smoke 2700/2700 with `--shots`, six new checks; 66 of 67 extra checks (320 px, 200%
zoom, reduced motion, keyboard, the withheld / no-bars / stale / failed / closed /
no-trade states, a blocked store, and the remembered mode, range and deep link).
Upstream `npm run check` green (107 component blocks, 357 classes findable) and
`visual-check --browser` 6/6. **Each new check was run against `5515515` and
fails there**; the one that also passes there (the button spanning the bar) dies
under its own mutant, the stacked bar not stretching. Two of them could not have
failed as first written — `innerText` reads a `display: none` element, and a count
of `.sc-tabs` is the same on both trees — the third and second shapes this file names.

**The one failure, pre-existing and left.** Under 320 px (200% zoom on a phone) the
page scrolls sideways: 315 px of content at 195, 240 and 280 px, the masthead links,
the footer and the Following empty state. Identical on `5515515`; the brief's floor
is 320 px, where it is clean.

**Blockers. None; both `main`s are green.** SpicyStock passes Tests, the secret
scan, the dashboard publication and the Pages deploy at `c3d6d1d`. The design
system's `main` was red on one gate and one only — `check: 1 problem — origin
has no v2.11.0 tag`, the other seventeen ok — and that red was not this
milestone's: the previous merge to that `main` (`edacaff`, 10 Sep) failed the
same way on `no v2.10.0 tag`, and `origin` carried no tag past `v2.4.0`, six
minors of deferral. It is closed: Tahir published the release from a phone,
`refs/tags/v2.11.0` → `1ffd905` (lightweight, as `v2.2.0`–`v2.4.0` are), and
`check` is green twice over — run 75 on the tag ref, which the unfiltered
`on: push:` triggered, and run 76 dispatched on `main`, the same commit as the
failed run 74 and passing only because rule 1 re-reads `origin` at run time
rather than the commit. The documented jsDelivr pins resolve again, first time
since `v2.4.0`.

**One environment fact worth keeping:** a tag cannot be pushed from this
sandbox. `git push origin v2.11.0` returns HTTP 403 at the agent proxy, which
passes `refs/heads/*` and refuses `refs/tags/*` (branch pushes in the same
session succeed), the proxy's README says to report a 403 rather than route
around it, and the GitHub tools here create branches, not tags. A release cut
in the web UI, targeting `main` when `main` is the intended commit, is the
way round it. Still not claimable, unchanged: a live fetch, a real chart read,
Resend, and expectancy.

**Next action.** The method's own, and nothing of this milestone's is left: on
a green or yellow session dispatch `evening.yml` with dry_run and check the
study against what the run withholds and writes. The tag needed no re-vendor —
it moves no byte, and the snapshot's provenance already names `6f10309`, which
is on the sheet's `main`.

## Checkpoint, 13 Sep 2026 — the release-candidate acceptance, and the gate that under-reported

**Revision.** Branch `claude/spicystock-release-acceptance-l5a1nm` cut from
`main` at `f7f2e8e`, the merge of #54 — already merged when this began, so
nothing of it was re-done. `docs/data.json` and `docs/picks.json` are untouched:
still run 47's record, `origin/main`'s to the byte.

**Executed here, not inherited**, at `f7f2e8e` on this sandbox's 3.11.15 /
pandas 3.0.5: 1076 tests pass at `f7f2e8e` and 1080 with the four added here;
7 fixtures current through the real generator; chart check 163/163; page smoke
2700/2700 with `--shots`. CI at `f7f2e8e` is green on its own runners — Tests
34730044133, Secret scan 34730044031, Pages deploy 34730043404.

**The candidate's run path has real-market evidence already.** `src/`,
`requirements.txt` and `evening.yml` are **byte-identical** between `5515515`
and `f7f2e8e`, and `5515515` is where run **51** (`34720798332`, artifact
`10306165995`) ran a full-market dry run on 12 Sep: 3014 names, 12 chart reads,
`published 2026-09-11: Stand aside.`, exit 0, nothing committed. So the
constrained-limit code has been executed against the real market — on a RED
session. No duplicate run was paid for.

**What that cannot prove, and why no dispatch would fix it today.** 13 Sep is a
Sunday and 12 Sep a Saturday: the newest session the bars carry is Friday
2026-09-11, the red one. A dispatch now re-derives the same stand-aside at full
provider cost. **Live qualifying-ticket acceptance is NOT RUN**, first possible
Monday 2026-09-14 after 6:16 PM ET, and only if breadth is green or yellow.

**The published record is one rules generation behind the code.** Its
`rules_version` is `2fe10c171341`; the code at `f7f2e8e` computes
`765180855b90`, differing by exactly `plan.limit_rule` (None →
`stop_constrained`) and `plan.precision.cent_floor_epsilon`. The versioning
works: no published page has yet shown a constrained-limit ticket.

**One reproduced defect, fixed.** `tools/publish_dashboard.py` is the only check
that reads what a reader is *served*, and it had no test. `docs/index.html` loads
fourteen local assets; its hand-kept tuple named **six**. The design
system's own `sc.css` — where v2.11.0's action bar and field group live, the
whole substance of #53 — plus `app-map.js` and `app-follow.js` were never
fetched, while the gate printed "Verified". It reads the list off the page now
(`public_files()`, 17 files) and names a referenced file the checkout lacks
instead of skipping it. Four mutants die, two of them selectively.

**Blockers.** The served page cannot be read from this sandbox: the proxy
refuses `spicychicken59.github.io` and Actions' blob host with 403 CONNECT, so
run 51's artifact was read through its log, not unzipped. Distribution rests on
the runner-side check instead, which at `c3d6d1d` fetched the public bytes and
matched them — and `docs/` is byte-identical `c3d6d1d`→`f7f2e8e`.

**Keep / fix / defer / omit.** Keep: everything above; the verified `6f10309`
pin (22 files, provenance = source = disk), un-re-vendored. **Fix, and it is a
FAIL not a defer:** `test_claude_md_is_short_and_names_the_fixture_count`
asserts `len(CLAUDE_MD.splitlines()) <= 150` over `prose()`, which collapses
every newline — tightened to `<= 1` it still passes. The file is 911 raw lines
and 9,377 words against a nominal 150. Moving the cap to match reality is this
file's own named anti-pattern, so it needs an owner's call: trim, or retire the
clause. Defer to Astra: the <320 px overflow, pre-existing and identical on
`5515515` (the supported floor is 320 px, clean, 66 of 67 extra checks). Omit:
trade logging, a portfolio, execution.

**Next action.** Monday 2026-09-14 after 6:16 PM ET, on a green or yellow
session, dispatch `evening.yml` with `dry_run=true` and reconcile the artifact
against `tools/entry_limit_study.py`'s green-night line — 52 reach the stop
rule, 0 eligible at the retired ceiling, 50 in production, 47 sizing to a whole
share.

### NEXT BUILDER PROMPT

Continue SpicyStock at `main` (verify the tip; `f7f2e8e` when this was written)
plus PR from `claude/spicystock-release-acceptance-l5a1nm`. Do ONE of these; do
not re-run the design pass, the upstream extraction, the tag, or this
acceptance sweep.

**(a) The live qualifying-ticket acceptance, if a green or yellow session
exists.** Requires explicit dispatch/billing approval — a dry run still pays
Alpaca and twelve Anthropic chart reads. Dispatch `evening.yml` with
`dry_run=true`, `session=""`, `skip_email=false` (dry run mails nothing; the
`Persist the run` step is skipped and nothing is committed). Then, from the
artifact: confirm `app.rules_version` is the code's own digest; that every
eligible burst has `limit <= day2_spent_above`, `stop < entry_ref < limit`,
`entry_high == limit`, `planned_entry == min(close +1%, limit)`; that each
whole-share ticket's stop is within 4% of its LIMIT; and that refusals carry
`ticket_refusal` with the setup kept and no order. Reconcile the eligible /
withheld counts against `python tools/entry_limit_study.py <record>`, whose
green-night line is 52 / 0 / 50 / 47. A red or closed session proves
stand-aside only — say so and stop. Never change regime, data or rules to
manufacture a ticket.

**(b) The CLAUDE.md length gate, which currently cannot fail.** Decide with the
owner: trim this file to a cap that binds, or retire the length clause and
guard something that can fail. Then make the assertion read the RAW file, not
`prose()`. Prove it fails.

Offline gates for either: `python3 -m pytest tests/ -q` (the `pytest` on PATH
here is a uv tool without pandas), `python tools/make_fixture.py --check`,
`node tools/chart_check.mjs`, `node tools/page_smoke.mjs --shots <dir>`. This
sandbox reaches neither the served page nor Actions' artifact blobs (403
CONNECT); read a run through its job log, and report the limit rather than
routing around it. Not claimable without a live night: Resend delivering, a
real chart read, and any trading edge.
