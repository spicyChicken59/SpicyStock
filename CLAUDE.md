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
record: Explore (the market in a line, two stage cards, one selectable card
per stock, one stock in focus with its chart, four decision answers, the
action area and four disclosures), Record, Market and Method, with the
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
system snapshot under `docs/design-system/`: one panel, Setup | Candles |
Line over one geometry (`SCStock.chartGeometry()`), a Setup range that
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
a table under it and the names it cannot plot listed by reason.
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

What is measured offline: 1023 tests, the chart check, and the page smoke
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
  Judged at the ticket's limit, a burst's stop is inside his line only when
  the usable stop (the low, else the bar's midpoint under the buy stop)
  sits within about 0.16% of the close: the field guide's textbook bar,
  low 4.7% under the close, is withheld, and so is nearly every real burst.
  The closeout implemented the withhold as specified rather than narrow the
  ticket's band; the one-rule alternative, a limit capped at the price 4%
  over the stop (`min(entry_high, stop / 0.96)`), keeps tickets and the
  stop rule at every fill but narrows the permitted range. A method
  decision, deferred to Astra; the fixtures carry three tight-bar bursts so
  the page still shows a ticket.

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
The Map is `SCStock.map.render()` over `gain_pct` and `volume_vs_prior`
as recorded. Following is `SCStock.follow` over a versioned browser
store; a followed card prints the saved levels, the latest close from
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
bites: the header strip holds one line at 1280 by fifty pixels and wraps
on a narrower column; a map under `LABEL_MIN_WIDTH` labels only the
chosen, focused and hovered point. Defer to Astra: the +4% ceiling
versus his 4% stop line (unchanged); whether a followed setup keeps an
observation older than `OBSERVATION_DAYS`. Omit: trade logging, a
portfolio, a journal, a scenario engine.

**Next action.** On the next green or yellow session, dispatch the dry
run again and count the A-quality bursts withheld at the limit from its
artifact, downloaded outside this sandbox; then open the page over that
record on a phone and walk the three modes, the map and one follow.
