# SpicyStock — working notes

An evening run over an explicitly selected US-stock universe, a static page that says
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
record: Today’s scan / Explore (the market in a line, two stage cards that always say how
many of their stocks carry a ticket, a lens row beside them, one selectable
card per stock, one stock in focus with its recorded entry decision, chart,
four decision answers and four disclosures; a Burst's compact action grid
precedes its chart, while anticipation keeps its existing action position), Record, Market and Method,
with the tickets and the scan as disclosures under the workspace and one
next action under every view. Method opens on the walkthrough
(`docs/app-method.js`, `SCStock.walkthrough`): one synthetic burst in eleven
steps, every number a caption quotes named in its `RULES` and held to the
modules, its example ticket and five-session replay re-derived by
`tests/test_walkthrough.py`; it reads no record and decides nothing.

**A record carries two facts about time and the page keeps them apart**,
because freshness is not permission. `status()` is publication: is this the
newest record and did the run finish. `run.timing` (`src/timing.py`, written
by `pipeline.plan_timing()`) is ACTION TIMING: the session the published
plans are FOR -- `plan.next_sessions(session, 1)[0]`, the same call
`dated_schedule()` makes for its day 1, so the two cannot disagree -- and
the offset-aware instants its entry window is scheduled between. The shared
`src/sessions.py` authority uses XNYS via exchange_calendars 4.13.2; the strategy
still owns window duration and the desk's 9:28 reminder. Completion is the
scheduled close plus 15 minutes. Known non-session runs skip all providers and
preserve the prior publication; missing bars on an expected-open day are an
outage. `run.calendar` freezes versioned dates/hours and a bounded schedule for
the browser. Historical records without it retain their limitations and are
research only; their immutable timing is never recomputed.
`availability(data, now)` is the ONE answer every surface that offers an
action asks (the compact area, the stock action bar, `discPlan()` and its
copy control, `renderTickets()`, `cmpFacts()`, `nextAction()`), and timing
NARROWS and never widens: a red night still leads with no new longs, a stale
page is refused under a window that is open, and a record with no timing
block -- or a half-written one, which `timingOf()` refuses one level in -- is
research only. A window that ended keeps the setup, its evidence and the
ticket the record published readable (`recordedTicket()`) and offers none of
it to place; the cancellation sentence is conditional and SpicyStock is said
to place and cancel nothing. `reclock()` re-reads the clock on visibility,
focus, page restoration and a bounded tick while visible, repaints only the
words that changed through `repaint()` (a chart is never disposed, an open
disclosure stays open, and focus falls back to the replacement's own first
control rather than the body), and `copyGuard()` asks again immediately
before a copy writes. `checkUpdates()` re-reads the same static file and
nothing else: it compares the served BYTES (a stamp of session, publish time
and rules digest cannot see a re-publish of the same session on later bars),
refuses a record older than the one on screen, lets a press supersede one in
flight so only the newest answer lands, and hands the reader back their
stage, stock, search and half-typed reference size while closing a
comparison rather than remapping its pins. `visible(stage)` is the ONE
visible-candidate selector -- the lens (`lensPass()`: the archived grade
against `tradeGrades`, the record's own `ticket` status, this browser's
Following shelf), the ticker search and the sort, in that order -- and the
cards, the map, the counts and the detail's stepper all read it, so a
subset can never differ between them. `defaultLens()` opens on A-quality
when the record archived one and on every burst otherwise; a lens the
reader chooses is stored (`spicystock:lens:v1`) and never widened behind
them, an empty one explains itself and offers one click out, and a lens is
a reading of the record and never a permission -- `blocked(st)` still
refuses every order under *With ticket*. A route that NAMES a stock the
lens hides widens it for that stock, says so, and does not store it. It computes one thing of the market — the status chip
from the record's session and the ET clock (`status()`) — and prints
everything else verbatim, including the six cover sentences and the plan
instructions. `buildModel()` is the one adapter, and every status it gives a
stock is read off a field the run wrote (`trades[]`,
`cash_budget.cut[].kind`, `plan.eligible`, `plan.action`, `quality.vetoes`,
the grade against `rules.pipeline.trade_grades`); nothing in the browser
scans, grades, sizes or fetches. `fillChooser()` reaches every stock
in the record, which is what it is for, so it is the one door that says so
first: each stage is split into what the lens holds and what it hides, both
counted, the hidden ones marked and listed second, and one line says that
choosing one widens the lens for that stock without changing the stored one.
`parseHash()` and `applyRoute()` are the
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
browser (`spicystock:chart:v1`). `chartPanel(c, {idPrefix})` is the panel
factory: the host, its observers and its tooltip belong to the handle it
returns and every id it writes is namespaced, so the comparison sheet can
mount `cmp-a` and `cmp-b` beside the detail's `chart` and neither disposes
another (`SCStock.liveCharts()` counts the undisposed ones). Under the plot
a *Show on chart* row marks recorded evidence -- `evidenceItems()`: the
base's archived `start`/`end`/bounds, the burst day read off `run.session`
(never the last bar, which a later observation would move), the previous
ARCHIVED bar before it, a coil's box -- and `options.highlight` in
`app-chart.js` draws it as a dashed column over those sessions in every
mode. It is a marker and never a level: it is kept out of the domain, so
turning it on moves no price, no label and no gutter. `CHECK_ANCHOR` is the
one mechanism the checklist tiles share; a check the record dates no range
for (linearity, the trend's age, the up-day run) stays a tile and is never
made clickable. Compare pins two candidates of one stage and one record
(`togglePin()`: a third asks which to replace, the other stage is
explained; a pin the lens later hides is marked, named and reachable in one
click, never dropped -- `trayState()` redraws the tray only when what it
shows has changed, because the list behind it is redrawn on every
keystroke), and the sheet gives each its own chart, its own price scale and
its own range sentence under one set of view/range controls, with an
aligned table of what the record says and no winner declared. `pipeline.SERIES_TOP` bursts by rank carry
their bars beside the trades, the cut names and the closest miss, so a
chosen burst has its chart without a second fetch. Under Bursts the cards
have a Map twin (`docs/app-map.js`, restored from the `29e3205` signal
map): the session's gain against its volume ratio, every point a recorded
number, the selection shared with the cards, the search and the chooser,
a table under
it and the names it cannot plot listed by reason. Its `control(point, where)`
hook takes the page's OWN `pinButton()` and places it beside the chosen point
and in the table's `compare` column, so two candidates are pinned from the map
without a detour through the cards and the map never grows a second pin. The ratio is read one way
everywhere (`volumeRatio()`: the row's own field, the scan's measurement
for every burst since the dollar scan carried it; for a record from before
that, run 46 and earlier, the checklist's two-place copy, said to be the
checklist's in the measurements; else missing and said so, zero a value).
My setups (`docs/app-follow.js`, payload version 4) is a peer destination to
Today’s scan (the existing Explore route), and a saved setup outlives the record it came from: one click
freezes the setup's own snapshot, its suggested whole-share quantity AND
the evidence the record carried for that signal -- the archived bars up to
the signal session, capped at `EVIDENCE_BARS`, and the dated anchors drawn
on them -- in this browser only (`spicystock:following:v1`, keyed by kind,
symbol, session and rules identity; a corrupt store set aside, an entry
with no identity set aside by name, a v1 payload upgraded only after it has
been copied beside itself and the new one has read back, a payload from a
FUTURE version left untouched and every write to it refused). Each record
loaded afterwards contributes at most one observation per market DATE
(`recordObservations()` over `recordBarsFor()`: the archived series, the
`observations` block, the record's own rows, the open plan -- fullest source
wins the date), so a re-render, a reload and a theme change add none; an
OLDER record never replaces a newer observation; a different close on a
date already observed is a REVISION of that trading day carrying what it
replaced; a session no record carried stays missing; `OBSERVATION_MAX`
dates are kept and the original is not one of them. `basisOf()` asks the
bars rather than assuming: a session both records hold, priced the same, is
`match`; an EARLIER session whose close has moved means the archive was
re-priced since (a split does that) and the change is withheld with the
reason; nothing in common is `unknown`, said so, and the change still
shown. `#/followed/<identity>` opens the saved setup's own sheet over
whatever the reader was on -- *At the signal* (the frozen chart through the
same `chartPanel()`, the levels, the grade THAT record gave, its
limitations, and its instruction shown as dated history) against *Since the
signal* (the observed closes, their dates, their sources and their
revisions) -- and never substitutes tonight's setup for it: a current
signal for the same symbol is a separate, named link, and a symbol on no
list tonight says so. `recoverEvidence()` gives a v1 follow its chart back
only from a record that IS its signal, never from a newer same-ticker one.
`modelUpdateOf()` attaches the record's open model plan only on the same
session, the same family and the same rules identity; anything else is
named as another signal's. An optional reference size is labelled the
reader's, and nothing of any of it reaches the record, the mail, the
scorecard or the URL. A page over a fixture
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

The suite now collects 1378 tests, the chart check remains separate. Historical measurement: 1107 tests, the chart check, and the page smoke
over eleven fixtures walked through every view, stock, lens, search, the
chooser and what its lens hides, the comparison and the pins a lens no
longer shows, the map's own Compare column, the recorded evidence, the
keyboard, deep links
and the old anchors, then the phone and the stale, failed, field-dropped
and no-record states. What is NOT: the full-market
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

## Checkpoint, 13 Sep 2026 — narrow it, compare two, show the evidence

**Revision.** Branch `claude/spicystock-compare-evidence-y3hykv` from `main` at
`cf08c900` (#55 already merged; the branch was at that tip, clean and empty).
`docs/data.json` and `docs/picks.json` are `origin/main`'s to the byte — run
47's record. The vendored snapshot is untouched; every new style is `ss-*`.
**Merged to `main` as `017b776` (#56) on Tahir's word, and merging published:**
`publish-dashboard.yml` fires on any push to `main` touching `docs/**`, so Pages
rebuilt and the gate waited for the new `app.js`, `app.css`, `app-chart.js` and
`app-map.js` to appear before printing *Verified: every one of the 17 public
files matches committed main* — the first time that gate, repaired in #55, has
had a change to those files to prove. All four post-merge runs are green
(Tests 34752200664, Secret scan 34752200734, publication 34752200728, Pages
34752206578; the Pages run 34752200299 was cancelled as superseded, as at
`cf08c900`). No evening run was dispatched and no mail was sent.

**One selector, three capabilities.** `visible(stage)` is the only
visible-candidate list — lens, search, sort — read by the cards, the map, the
counts and the detail's stepper, so the map can no longer plot a population the
cards do not. The lens asks four questions of fields the run wrote and is never
a permission: it turns the published record's 401 bursts into the 52 graded
A-quality, and a stale page under *With ticket* still offers no order. Compare
pins two candidates of one stage and one record, each with its own chart
instance (`chartPanel(c, {idPrefix})`: `cmp-a`, `cmp-b` and the detail's `chart`
coexist; `SCStock.liveCharts()` proves the teardown). *Show on chart* marks the
archived base, the signal session read off `run.session` and the previous
archived bar, in every mode and outside the domain, so it moves no price.

**Measured, not argued.** At 1280×900 the chart's top is 667 px over the marked
fixture (identical to `cf08c900`) and 625 px over the published record: the lens
rides beside the stage cards, in the half of that band they leave empty, and the
stepper stacks under the chips. At 390 px the search stays at 809 px, unchanged,
the lens moving into the rail head (`lensHome()`). Nothing scrolls sideways.

**Three defects, each reproduced before it was fixed.** Unfollowing the last
saved setup jumped out of the Following lens — the deep-link widen fired on a
re-render, and now fires only for a stock the reader was not already on. A
checklist tile stayed clickable for a stock whose base carried no dates: a tile
reads THIS stock's own anchors now. And the comparison's evidence table rendered
**2 px tall over 502 px of rows** — the dialog's scrolling column flex shrinking
its items, the class that squeezed the chooser, closed with `flex: 0 0 auto`.

**Checks.** 1082 tests (2 new, holding the page's anchors to keys `quality.py`
writes and dates the record carries); 7 fixtures current; chart check 178/178
(15 new); page smoke 2904/2904 with `--shots` (three new suites, 194 checks);
the journey 160/160 over the published record at 1280 and 390, the ticket
fixture, a red night, a stale clock, a record with no bars and no dated base,
and one symbol under two signal identities. **Thirty-two mutants: 29 died on the
first pass and 3 survived**, each a hole — a missing gain read as zero still
sorted last, every gain in every record being positive (the volume ratio, where
zero IS a value, discriminates); the undated-check assertion named `linearity`
and left `young_trend` free; nothing read the two panels' alignment. All die now.

**CI green on its own runners** at `dd8a50d` (#56): pytest 103698824535, page
103698824435, gitleaks 103698824509, the PR `clean` with no review thread. The
page job — the chart check and the full smoke with `--shots` — took **3 m 57 s
against its 15-minute cap**, so the three new suites left the margin intact; the
same smoke takes about twenty-five minutes in this sandbox, which is the slow
machine, not the gate.

**Keep / fix / defer / omit.** Keep everything above. Fix if it bites: the
chooser reaches a stock any lens hides, the notice saying so only afterwards; a
401-point map is rebuilt per keystroke while the search is typed in map mode.
Defer to Astra: the +4% ceiling against his 4% stop line; the <320 px overflow,
pre-existing. Omit: trade logging, a portfolio, execution. **Blockers: none.
Not claimable:** a live fetch, a real chart read, Resend, and any trading edge —
this changes what the reader sees, not what wins. Pages is claimable now, and
only because the publication gate fetched the served bytes and matched them.

**Next action.** The method's own, untouched here: on a green or yellow session
dispatch `evening.yml` with `dry_run=true` and reconcile the artifact against
`tools/entry_limit_study.py`'s green-night line, 52 / 0 / 50 / 47.

## Checkpoint, 13 Sep 2026 — the lens, where the reader reaches past it

**Revision.** Branch `claude/spicystock-compare-evidence-j30kl4` from `main` at
`9597898` (the merge of #57). The brief's three capabilities — the lens, the
comparison, the chart evidence — were ALREADY merged as #56 and none was
re-done; this is what reading them back in Chromium showed they left open.
Both published records are `origin/main`'s to the byte, run 47's; no Python
was touched.

**Reproduced before anything was edited**, over that record (401 bursts, the
A-quality lens showing 52): the **chooser** listed all 416 stocks with nothing
marking the 364 the lens hides, and the widen notice came only after the page
had moved; a **pin** made under *All bursts* survived a narrowing to A-quality
unmarked — a stock in the comparison that is in no list behind it; and the
**map**, the cards' own twin, had no Compare toggle at all, so the journey
(inspect on the map → pin two → compare) went back through the cards to find
them again. One class, in a new place: a control that reaches a stock
without carrying the reader's context — `visible(stage)` feeds the cards, the
map, the counts and the stepper, and these three were the doors it never
reached.

**Changed.** `fillChooser()` splits each stage into what the lens holds and what
it hides, counts both, marks the hidden (`data-in-lens`), lists them second so
Enter takes a stock the reader can see, and says BEFORE the choice what it will
do — and that the stored lens is not changed by it.
`renderTray()` marks a pin the current lens hides, names it once with one click
to it, and is redrawn with the list only when `trayState()` changes.
`SCStock.map.render()` takes `control(point, where)` and places it beside the
chosen point and in a `compare` column of the table twin; `mountMap()` supplies
`pinButton()` itself, so the map's pin IS the cards' pin, never a second
mechanism.

**Measured** (offline, through the doubles): 1082 tests; 7 fixtures current;
chart check 178/178; page smoke **2952/2952** with `--shots`, a new `reach`
suite of 48, all 48 red at `9597898`. The journey was walked **80/80** over the
published record at 1280 and 390 px, the ticket fixture, a red night and two
blocked states: two pinned FROM the map, compared, the evidence read inside the
sheet, one setup opened, followed, the lens and stock still there on Back. No
sideways scroll at 320 or 390 px, either theme. A tap on a 401-burst night still
opens the nearby chooser, so the journey takes a point by Enter, as documented.

**The mutants.** Eleven over the new rules, all dead. A shape this file names
returned: "the prompt survives a keystroke" passed on an incidental fact — the
prompt is re-rendered from state either way — so it reads the FOCUS now, and the
redraw is pinned both ways. Three controls — the map's selection sentence, the
tray's slot wording, the chooser's reason text — all SURVIVED.

**Keep / fix / defer / omit.** Keep everything above and #56's capabilities
untouched. Fix if it bites: the chooser's group heading is an `.sc-eyebrow`,
which lowercases, so the lens reads "a-quality" there as on its own tab. Defer
to Astra: the +4% ceiling against his 4% stop line; the <320 px overflow;
`test_claude_md_is_short_and_names_the_fixture_count`, still unfailable — that
cleanup is a separate pass. Omit: trade logging, a portfolio, execution.

**Blockers: none. Not claimable**, unchanged: a live fetch, a real chart read,
Resend, and any trading edge.

**Next action.** The method's own: on a green or yellow session dispatch
`evening.yml` with `dry_run=true` and reconcile the artifact against
`entry_limit_study.py`'s green-night line, 52 / 0 / 50 / 47.

## Checkpoint, 14 Sep 2026 — a followed setup that outlives its record

**Revision.** Branch `claude/spicystock-follow-through-clqeb8` from `main` at
`e0f68d9` (the merge of #58), clean and empty at that tip; three commits on
it, pushed as **#59** and **merged to `main` as `97609cb`** on Tahir's word.
`docs/data.json`, `docs/picks.json` and the vendored `docs/design-system/` are
untouched to the byte; no sibling repository was written; no evening run was
dispatched and no mail was sent. **Merging published**, as it does on any push
to `main` touching `docs/**`: all four runs are green on `97609cb` (Tests
34796937896, Secret scan 34796938005, publication 34796937880, Pages 34796945221;
Pages run 34796937072 was cancelled as superseded, as at `cf08c900` and
`dd8a50d`), and the publication gate waited for the five changed files —
`index.html`, `app.css`, `app-chart.js`, `app-follow.js`, `app.js` — to appear
on the served site before printing *Verified: every one of the 17 public files
matches committed main*.

**Reproduced first, over two records** (`scratchpad/repro/follow_repro.mjs` at
`e0f68d9`): a setup followed on the `full` night saved no chart and no
observation history, there was no way into a saved setup by its identity, and
*Open chart* on the followed AAPL — a symbol that had LEFT the newer record —
navigated to **NVDA**, silently, because `routeHash()` looks the id up in
tonight's model and drops the ticker when it is not there. The same session
re-run on later bars rewrote −5.5% to −5.2% with nothing saying it was one
trading day read twice; an OLDER record put the card back to "no newer
observation available", losing the 11 September close and claiming none
existed. The archived ticket chip and the order sentence read as current on a
night the symbol was in no scan.

**The records that made it measurable.** `make_fixture.py` writes two sequels
over the docs the `full` night wrote, so each inherits its record and its
picks as a real night does: `next` (Friday — the ticket and the withheld setup
gone, AAPL closing under the stop its own plan named, NVDA bursting again, the
coil breaking out into *Bursts*, NVDA carrying the night's one ticket) and
`revised` (that same session on later bars, AAPL's close 37¢ off). Eight
fixtures; the other six byte-identical.

**Measured.** 1086 tests; 9 fixtures current through the real generator; chart
check 182/182; **CI green on its own runners at `e7ba821`** — pytest, gitleaks
and the `page` job, which is the chart check and the FULL smoke with
`--shots`: **3364/3364** in 5 m 08 s, the new `through` suite (133 checks) the
longest single one at 91 s.

**The mutation pass, and a harness bug of mine.** Thirty-two mutants over the
new rules. The runner assigned four repo copies BY INDEX while running four
threads, so two mutants could share a copy and each `finally` restore erased
the other's mutation — six false survivors, and most of an evening. Fixed (a
queue: one copy held per mutant). Twenty-three died in that flawed pass; of
the six reported survivors, three re-judged individually now die, and **three
were real holes, each closed with the check it showed was missing**: "an older
record cannot replace it" passed because a DIFFERENT rule rejected (every bar
the `full` night holds for that symbol is at or before the signal, so the
merge never reached the guard); the migration's read-back of its own COPY was
never exercised at its failure point; and the STORE's bound on frozen bars was
untested, the page-side filter being equivalent on any real record. **NOT
run:** the remaining ~25 mutants under the fixed harness. That is a gap, not a
pass.

**One process failure worth recording.** A command of mine contained `git
checkout -- .` and reverted every uncommitted file. All eleven were
reconstructed from the session's own patches; the proof it is exact is that
`make_fixture.py --check` reproduces both surviving fixtures byte-for-byte.
Commit before running anything that can touch the tree.

**Keep / fix / defer / omit.** Keep everything above. Fix if it bites:
observations that ARE contiguous real OHLC could use the existing chart modes
rather than the dotted trail (the trail is right for a sparse series and is
what is built). Note for a later authorised promotion, NOT upstream now: the
bounded sheet with a head strip and a scrolling column whose rows are
`flex: 0 0 auto`, and the two-group card. Defer to Astra: the +4% ceiling
against his 4% stop line; the <320 px overflow; the CLAUDE.md length gate,
still unfailable. Omit: trade logging, a portfolio, execution.

**Blockers: none. Not claimable**, unchanged: a live fetch, a real chart read,
Resend, and any trading edge — this changes what a reader can still read a
week later, not what wins.

**Next action.** The method's own, untouched here: on a green or yellow session
dispatch `evening.yml` with `dry_run=true` and reconcile the artifact against
`entry_limit_study.py`'s green-night line, 52 / 0 / 50 / 47.

## Checkpoint, 14 Sep 2026 — the session-aware desk

**Revision.** Branch `claude/spicystock-follow-through-clqeb8` restarted from
`main` at `14f9d18` (the merge of #60, which was already merged when this
began); six commits on it, pushed as **#61** and **merged to `main` as
`ce2c6c1`** on Tahir's word. `docs/data.json`, `docs/picks.json` and the
vendored `docs/design-system/` are untouched to the byte; no sibling
repository was written; no evening run was dispatched and no mail was sent.
**Merging published**, as it does on any push to `main` touching `docs/**`:
all four runs are green on `ce2c6c1` (Tests 34839198850 — `pytest` and the
`page` job, the chart check and the FULL smoke with `--shots`, 5 m 48 s;
Secret scan 34839198817; publication 34839198750; Pages 34839210085, with
run 34839197636 cancelled as superseded, as at `cf08c900`, `dd8a50d` and
`97609cb`). The publication gate WAITED for the three changed files —
`index.html`, `app.css`, `app.js` — to appear on the served site before
printing *Verified: every one of the 17 public files matches committed
main*, so Pages is claimable on this commit and the served bytes are this
commit's.

**One red on `main` that is not this milestone's, checked rather than
assumed.** The SCHEDULED Secret scan (34811928399, 06:04 on `14f9d18`)
fails where the push-triggered scan on the same SHA passed at 02:01: the
scheduled run scans all 233 commits and reports 14 findings in
`tools/research_cockpit_smoke.mjs` at `742c2695` (8 Sep), a first-build
file that no longer exists on `main`. A push scan covers only the pushed
commit, which is the asymmetry this file's environment note already
describes. Nothing here touches it, and it will keep failing on every
scheduled run until the historical fingerprints are allowlisted.

**Reproduced first** (`scratchpad/repro/session_repro.mjs`, over the published
record and the ticket fixtures at five pinned clocks): at 11:00 AM and 3:00 PM
ET on the very session its plans were for, the page said *"Place the 1 order
from tomorrow's tickets in Fidelity before 9:28 AM"*, the action bar said the
ticket *"fills only on its own terms tomorrow"*, and the copy control was live.
Publication was `fresh` and `blocked` false at every instant — correctly, the
record WAS fresh. Freshness was being read as permission.

**The run serializes the window once** (`src/timing.py`, `run.timing`). The
applicable session is `plan.next_sessions(session, 1)[0]`, the same call
`dated_schedule()` makes for its day 1, so the block and every plan's schedule
name one date by construction. The instants are built with `zoneinfo` from
named policy times, so DST is the tz database's answer (−05:00 in December,
−04:00 after the spring-forward Sunday) and no offset is written by hand. A
closed night uses the one holiday fact the run ever gets — its expected session
printed no bars — and applies the standing plans to the weekday after THAT,
naming the closed date. What it cannot read it says: `no_holiday_calendar`,
`regular_hours_assumed`. `rules_version` moved to `cf1422d7ad5c`, so no older
record reads as one of these.

**One answer, six surfaces.** `availability(data, now)` is asked by the compact
area, the stock action bar, the plan disclosure and its copy control, the
ticket sheet, the comparison's ticket row and the next action. Timing NARROWS
and never widens: a red night still leads with *no new longs*, a stale page
stays refused under a window that IS open, and a record with no timing block —
or a half-written one — is *research only*. A window that ended keeps the
setup, its evidence and the published ticket readable and offers none of it to
place; the cancellation is conditional and SpicyStock is said to cancel
nothing. The clock is re-read on visibility, focus, page restoration and a
bounded tick, repainting only the words that changed. `checkUpdates()` compares
the served BYTES, refuses a record older than the one on screen, lets a press
supersede one in flight, and hands back stage, stock, search and a half-typed
reference size while closing a comparison rather than remapping its pins.

**Measured offline.** 1107 tests (21 new); 9 fixtures current through the real
generator; chart check 182/182; page smoke 3538 with two new suites (`session`
94, `refresh` 46). Screenshots at 1280, 390 and 320 px, both themes, looked at.

**Defects this milestone's own checks found, all fixed.** A second press was
REFUSED while one was in flight, so the out-of-order guard could never run.
"Unchanged" was a stamp of session, publish time and rules digest — exactly
what a same-session re-publish keeps. `repaint()` dropped focus on the body
when the control the reader was on was the one the clock withdrew. The copy
refusal was appended to the subtree that catching the page up rebuilds. And
the compact area regressed the first screen (bar 156→246 px at 1280, 295→394
at 390): the regime went back to the verdict it belongs to, each clock fact
carries its chip beside its LABEL, and the update control shares the quiet
links row. Two test defects: a clipboard assertion that was no evidence
(Chromium's clipboard is shared across contexts), and the blocked-states hint
asserted by a fixed sentence rather than the state's own word.

**Nine mutants over the timing rules all die**, each in the tests that name it,
with a control mutant staying green. Two survived the first pass — both the
shape this file names second, a test passing on an incidental fact about a
generated fixture — and both assert against the live modules now.

**The page-side pass was abandoned three mutants in, and that is a gap, not a
pass.** Of the three judged: the window staying open AT its cutoff dies, an
ended window still offering the order dies, and **`the window opens a minute
early` SURVIVED** — the `session` suite reads the phase at 9:00, 9:28, 9:30 and
9:40, and none of those falls in the minute a sixty-second shift moves. The
boundary is pinned in pytest (`test_the_phase_at_every_boundary_of_the_window`
asserts one second either side) but not in the browser. The remaining
twenty-one mutants were never run.

**And a process failure, mine, the one this file already warns about.** A
mutant batch was still running in the background when I committed: `1f649c8`
captured `the window opens a minute early` in `docs/app.js` and I pushed it and
opened a pull request on it. Found by reading `git status` rather than by any
check — no gate would have caught a commit whose tests ran before it. Reverted
in the commit after, with `docs/app.js` proved byte-identical to the last clean
commit. The rule stands and is now twice earned: do not run a mutation harness
while anything else may touch the tree, and never `git add -A` while one is
alive. The full smoke run that overlapped it is void and was re-run.

**CI caught what the sandbox did not.** The `page` job was red on a tree whose
local smoke was 3543/3543: the no-record page came back reading *"No verdict."*
under `data-ss-rendered="failed"` instead of *"The record could not be read."*
under `error`. `failed()` leaves `current` a stub so the Following shelf and a
saved setup still read — and that stub HAS a `run` object, so `reclock()`'s
"is there a record" guard was asking a question `current` could not answer. The
`pageshow` the browser fires on its own then repainted the market bar over the
failure sentence. Order-dependent, so it passed here and failed on a runner.
`loaded` is the flag now, set by `render()` and cleared by `failed()`, and the
check that pins it fires the three events itself rather than waiting for the
browser to — proved red without the fix, green with it.

One smoke failure did not recur and is recorded rather than chased: on one
combined run the volume-sort check read a pick card mid-render; three runs
alone and the full smoke are green.

**Blockers: none. Not claimable**, unchanged: a live fetch, a real chart read,
Resend, Pages, and any trading edge.

**Next action.** The method's own: on a green or yellow session dispatch
`evening.yml` with `dry_run=true` and reconcile the artifact against
`entry_limit_study.py`'s green-night line, 52 / 0 / 50 / 47.

## Checkpoint, 15 Sep 2026 — the shared v2.13.0 release, merged, scanned and accepted on real data

**Revision.** `main` at `dc6d1c8`, green on all four runs (Tests 34919173522,
Secret scan 34919173527, Pages 34919172987, and the dispatched full-history scan
34919192464), by two merges: `591837b` (#63, the adoption and the scanner) and
`dc6d1c8` (#64, one test). Merging #63 published — the gate waited for the seven
changed files to appear on the served site before printing *Verified: every one
of the 17 public files matches committed main*. #64 touched only `tests/`, so no
publication fired, correctly.

**The adoption.** `node build/vendor.mjs` from a clean checkout of the v2.13.0
tag: 22 files, `2.11.0/6f10309` → `2.13.0/14a752d`, every manifest hash equal to
the installed bytes AND to the clean source, 22/22 both ways, purely additive.
`.sc-pick` replaces the map's twelve chooser rules; `.sc-unreported` an absent
compared value; `.sc-estimate` the saved setup's aim, the one derived figure
among exact ticket terms — trigger, limit and stop are never marked.
`.sc-compare-pair`, `.sc-signal-matrix--fit` and `.is-best` refused on a
measurement: two record columns already fit at 390px, and a difference is not a
winner.


**The scan, closed on a runner.** `.gitleaksignore` carries twelve fingerprints
for the fourteen historical `generic-api-key` findings, each read at its commit
and classified as a `localStorage` key name in a file the v2 rewrite deleted — no
credential, nothing to rotate. The dispatched scan **read 240 commits, 23.92 MB,
and found no leaks**, its debug lines showing each finding located at `68685338`,
`2a6b3e56` and `742c2695` and skipped **by exact fingerprint**, not by path, rule
or file exclusion. Every detector and the whole history stay.

**One test that could not fail** (#64). `tests/test_timing.py` asserted
`published["run"]["timing"] is None` — about which record happened to be
committed, true only while run 47's stood. It broke at `fbaed5c` and surfaced on
the #63 merge only because a `GITHUB_TOKEN` push triggers no workflows. **Worth
keeping: the nightly record reaches `main` and the served site read by
`publish_dashboard.py` alone.** Two invariants are asserted now.

**Accepted against real data — run 2026-09-14, red again** (ratio 0.86, 558
bursts). The published record is now the code's own rules generation,
`953f37fb787a` computed and recorded with no module differing: the first time
the two have agreed. All 558 bursts driven through `plan.burst_plan()` hold
every acceptance invariant — `limit <= day2_spent_above`, `stop < entry_ref <
limit`, `entry_high == limit`, `planned_entry == min(close +1%, limit)`, each
stop inside 4% of its limit, and all 30 refusals carrying `ticket_refusal` with
the setup kept and `order_json`/`order_line`/`order_terms` None. `limit_basis`
is `stop_line` for **528 of 528**: not one limit set by the outer ceiling, the
constrained-limit premise confirmed in the market. The study reproduces on a
second real record, **53 / 0 / 48 / 47** against run 47's 52 / 0 / 50 / 47, the
47 stable across both. The page was read back over the served record, 37/37 at
four instants around the window it names, 1280/390/320, both themes: the two
clocks stay apart (*data through · Mon 14 Sep* beside *plan for · Tue 15 Sep ·
window 9:30–10:00 AM ET*, the first `run.timing` block to render), no order is
offered at any phase of a red night, and the lens's A-quality count is 53 — the
study's green-night line, reached independently in the browser.

**Keep / fix / defer / omit.** Keep everything above. Fix, nothing in the product:
the lens row's clipped right edge at 390px is `.ss-lens`, a real `overflow-x`
scroller whose *With ticket* button is reachable at 320px too. One defect of mine,
found by a reader's question and by no gate: trimming this checkpoint to the
brief's word budget deleted the sibling findings while leaving the prompt below
pointing at them. A cut needs a re-read, not a word count. Defer, all
pre-existing: the <320px overflow; the CLAUDE.md length gate, still unfailable;
gitleaks 8.24.3 ships no Anthropic detector, so `sk-ant-` is invisible here.
Omit: trade logging, a portfolio, execution.

**Not claimable.** A live QUALIFYING TICKET: 11 and 14 Sep were both red, so no
ticket has ever been published and the withheld-at-the-limit count is still
unobserved. Also Resend, a real chart read, and any trading edge.

### NEXT BUILDER PROMPT

Continue SpicyStock at `main` (verify the tip; `dc6d1c8` when this was written,
green on all four runs). The v2.13.0 adoption, the scanner disposition and the
full-history scan are DONE — do not re-vendor, do not re-open the chooser, the
comparison, the figure basis, or the historical findings, and do not re-dispatch
the scan.

**One thing remains, and it needs a green or yellow session.** The live
qualifying-ticket acceptance requires explicit dispatch/billing approval — a dry
run still pays Alpaca and twelve Anthropic chart reads. Both sessions the record
has ever carried were red, so no published record has yet shown a ticket. On a
green or yellow session dispatch `evening.yml` with `dry_run=true`, `session=""`.
From the artifact: confirm `app.rules_version` is the code's own digest; that
every eligible burst has `limit <= day2_spent_above`, `stop < entry_ref < limit`,
`entry_high == limit`, `planned_entry == min(close +1%, limit)`; that each
whole-share ticket's stop is within 4% of its LIMIT; and that refusals carry
`ticket_refusal` with the setup kept and no order. Reconcile against `python
tools/entry_limit_study.py <record>`, whose green-night line is 53 / 0 / 48 / 47
on run 2026-09-14 and 52 / 0 / 50 / 47 on run 47. A red or closed session proves
stand-aside only — say so and stop. Never change regime, data or rules to
manufacture a ticket.

The evening cron's guard is worth knowing: it fires `16 1 * * 2-6` and skips
every step when tonight is already published, so a second firing costs nothing.
And a `GITHUB_TOKEN` push triggers no workflows, so the nightly record lands on
`main` and on the served site having been read by `publish_dashboard.py` alone —
a record-shape regression surfaces on the NEXT pull request, not on the commit
that caused it.

Offline gates: `python3 -m pytest tests/ -q` (`pip install -r requirements-dev.txt`
first on a fresh container), `python tools/make_fixture.py --check`, `node
tools/chart_check.mjs`, `node tools/page_smoke.mjs --shots <dir>`. The full smoke
takes about fifty minutes here and six on a runner; `--only <suite>` runs one of
the nine fixture variants or `mobile`, `modes`, `lens`, `compare`, `evidence`,
`map`, `reach`, `volume`, `mapscale`, `following`, `through`, `session`,
`refresh`, `ticket`, `states` — which is what a mutant should be judged by.
`--shots` CHANGES the totals, so quote the `--shots` number: 3564 at `dc6d1c8`.
This sandbox reaches neither the served page nor Actions' artifact blobs (403
CONNECT); read a run through its job log and report the limit rather than routing
around it.

Do not touch SpicyHome or SpicyCar; neither needed a change. All three apps carry
byte-identical v2.13.0 assets -- the same 22 SHA-256s -- Stock's and Home's
provenance naming the tag `14a752d` and Car's naming `ad5aa0f`, that tag's second
parent on the same tree. Validated at Home `19ddcf6` and Car `62db117`; Home's tip
has moved to `b745197` since, its own tracker bot writing data only, with the
provenance unchanged. Two findings stay OPEN in Car, to be fixed in THAT repository
rather than here -- not because they are another owner's, since all four
repositories are one account's: `docs/design-review/` still records #78's numbers
that #79 superseded, and two NON-CI harnesses fail on a `#signal-card` that
computes `display:none`. Both were proved pre-existing.

## Checkpoint, 15 Sep 2026 — local saved-research continuity milestone

**Scope and state.** Tahir explicitly authorized Stock-only local implementation
and offline verification in this execution. Branch `continuity/my-setups` starts
at `0233b309a43d3c3f64d30ee974d2be15d1fcea28`; live main was rechecked unchanged,
with zero open PRs at preflight. No push, PR, merge, deployment, dispatch, paid
scan, email, credential or sibling-repository change is authorized or performed.
This checkpoint supersedes the older NEXT BUILDER PROMPT above. Astra High was
requested; the runtime exposes no authoritative selected-model/effort field.

**Implemented.** Today’s scan and My setups are peer destinations, using existing
Explore/Following routes and cards. Card/detail/comparison saves use the same
store. Saved originals remain independent of current filters and membership.
Optional “I took this setup” and USD reference amounts are browser-local
annotations, never execution data. Schema 3 preserves legacy share fields,
original evidence, unknown fields and migration backups. Currency is explicit
integer cents; clear means unknown. Web Locks serialize mutations across tabs;
conflicts follow acquisition order and stale edits cannot resurrect removals.
Failed writes preserve editable drafts and offer a local recovery copy.

**Recovery and coverage.** `src/history.py` and `tools/backfill_history.py` retain
published originals by source blob, with a lazy index/context/evidence contract.
Three authentic publications cover September 11 and 14, including both September
11 revisions. ATEC’s required original has 120 bars; both inspected September 11
originals lack VICR’s chart. No chart is reconstructed. Actions artifact metadata
was read, but artifact binaries were not inspected here. Public coverage now
includes every saveable signal, with separate signal dates and a 21-calendar-day
window, up to 20 real observations and no new provider/chart-reader calls.
Catalog bounds are 84 publications, 10,000 signals per publication, 256 KiB per
lazy file and 128 MiB total. Local saves do not expire.

**Verified so far.** Baseline DOM reproduction saved both September 11 cases and
retained them on September 14: no deletion was reproduced. Their later closes
were 10.86/184.73; original grades remained A. Focused Python verification passed
180 checks, then 40 closeout checks; offline DOM/store verification passed 83.
The new destination protection fails on baseline for the missing destination.
Removing VICR’s later coverage identity fails the intended window test while
its source-control test passes. These are not real-browser acceptance results.
Final normal verification commands run at the handoff revision; the execution
handoff records their results separately from historical totals. The first full
pass had 1110 passes and four SDK-construction failures from missing runtime
`socksio`; installing proxy support resolved all 65 grader checks without a
repository change or disabling the proxy. Fixtures: 9 current. Real-browser
checks remain blocked as described below.

**Impact and limits.** `docs/continuity/measurements.json` records the published-bar
replay: observations cover 72→877 symbols / 989 identities; compressed data grows
363,932→410,038 bytes. The recovery index is 74,023 bytes compressed; originals
load on demand. Initial requests: +0; first search: 1; inspection: 2. Actual future
full-frame payload was not measured. Browser/layout acceptance is BLOCKED:
Playwright’s Chromium is absent and official downloads time out. Desktop,
390/320px, both themes and real keyboard acceptance remain unaccepted.

**Keep/fix/defer/omit.** Keep existing discovery, session guards and model results.
Fix only continuity. Defer all queued campaigns; omit portfolios, executions,
personal P&L and cross-device sync. Design v2.13.0 remains installed/released;
22 source blobs matched, with vendored assets untouched. The scanner’s existing
rule-key exception now also names immutable recovery paths; detectors and
historical fingerprints are unchanged. See `docs/continuity/README.md` for
reusable patterns, source evidence and remaining verification.

## Checkpoint, 15 Sep 2026 — PR #67 browser merge-gate correction

The correction starts at remote `ac96f6894d44049a8e58659530b3ee630e21994c`,
with main still `0233b309a43d3c3f64d30ee974d2be15d1fcea28`. The original local
commits remain on their branch; their published replacements have identical
trees. Tahir authorized corrections on the existing PR branch. No merge,
manual deployment, paid/provider scan or workflow dispatch is part of this work.
During verification, main advanced independently to
`442db489342660d7588d16dcc18e6c126187c1e6` (`run 2026-09-15`, published data and
universe directory only). That work is preserved; the PR's merge base remains
`0233b309a43d3c3f64d30ee974d2be15d1fcea28`, without a rebase or merge.

The exact page-job log from Tests run 35030039637 (job 104586138583) showed two
layout regressions: `checkMobile()` measured the chart at y=682.78125, exceeding
the existing y+220<=900 first-screen limit; `checkCompare()` timed out because
AMD's selection button intercepted the click on AAPL's mobile Compare control.
The latter reproduces locally in Chromium 141 / Playwright 1.56.1, installed
through Playwright's official fallback download. The original CI screenshot
artifact 10421440924 was downloaded, hash-verified and visually inspected.

The added column wrapping and 100% flex basis pushed each mobile card's action
row into the next column. Removing those two rules keeps Save and Compare below
their own selection. Equal desktop band columns accommodate the longer saved
scan-lens label without adding height above the chart. Removing small-screen
nav link side padding also keeps the new labels on one row at 390px with the
fallback font; that font exposed the existing search/chooser viewport check
locally. Text size, destination names and existing assertions are unchanged.

New rendered-bounds protections fail on the uncorrected CSS at 390/320px in both
themes. The corrected mobile/comparison suites pass 120/120 checks. Continuing
past the original blocker exposed saved-setup regressions: asynchronous migration
did not notify its own tab, migration sanitization notices disappeared on the
next read, and rebuilding the saved shelf on dialog route changes destroyed the
opener needed for Escape focus restoration. The correction reports migration
completion while its queue guard is active, retains those notices in the existing
in-memory migration note, and keeps the shelf's nodes during dialog routing.

The remaining test-contract corrections explicitly visit My setups before
measuring its phone shelf and visit a candidate before attempting a save. The
return-context test now clicks and counts actual sibling Compare controls, with
a two-pin precondition. The generated next/revised fixtures carry the unchanged
signal close in public observation history, so their basis is `match`, not the
old latest-only fixture's `unknown`. A separate latest-only case preserves the
unknown-basis and full-disclosure assertions; re-pricing protections are intact.
Final local verification: `python3 -m pytest tests/ -q` passes 1,114 tests;
`python tools/make_fixture.py --check` confirms nine current fixtures;
`npm run test:continuity` passes 83 checks; `node tools/chart_check.mjs` passes
182 checks; and `node tools/page_smoke.mjs --shots <evidence-directory>` passes
3,577 checks. Focused follow-through passes 141/141. Original and corrected
desktop/mobile screenshots were actually inspected, including 390/320px and both
themes. No local browser gate remains blocked. Automatic CI is recorded on PR
#67. Correction evidence lives outside the checkout under
`evidence/pr67-correction`, including the original job log and CI screenshots,
negative rendered-bounds checks, focused browser logs and corrected screenshots.
README.md and .env.example were swept: no product contract, threshold or
environment variable changed. Store schema 3, original evidence, public history,
private annotations, strategy populations and design-system v2.13.0 remain
unchanged. This is a merge-gate correction, not the next reliability campaign.

## Checkpoint, 15 Sep 2026 — scan-aware grading contract

SpicyStock only, branch `grading/scan-aware-contract`, from verified main
`4f640d95f154ece89d26f57e76ca53a4e0abc0f2`. The checkout was clean, with no
open PRs or intervening main changes. Existing local branches were preserved.
This is the first bounded reliability milestone; the older paid-scan prompt
does not apply. XHigh/Standard was requested; selected runtime effort was not
exposed. The project context and original field-guide attachment were available
and consulted, including its primary/community/implementation distinctions.

**Reproduced.** September 14 CACI and ROKU were dollar-only but their reader
reasons incorrectly required +4%; ROKU's entry note repeated it. Their gains
were +2.57% / +1.63%, dollar bodies $9.78 / $2.14. CACI's independent Y/base
concerns and ROKU's weak contextual volume/base concerns remain legitimate
inputs. No corrected grade is asserted. Original rows matched Git blob
`a89ab122d7e0160df6a63c30957668447ace1103` exactly.

**Implemented.** `discovery.contract()` copies the scanner's recorded rules
and decision measurements, including its rounded prices/whole shares, into
version 1: admitted routes, applicable rules, explicitly inapplicable rules and
measurements. The block reaches quality metrics, the deterministic request and
the published row. Reader provenance adds its version and initial system/user
text SHA-256. The rulebook separates discovery from quality. Recognized
alternative-threshold replies and the reviewed universal-percent construction
fall back whole, without retry or fabricated chart judgement. This text guard
is bounded protection, not semantic certification of arbitrary future prose.
The page/report now say “no usable chart-reader judgement” for fallback.

**Audit.** `tests/fixtures/grading/history-audit.json` covers all 1,404 retained
entries, 1,359 reaction rows and all 36 model replies across three publications
on September 11/14: eight explicit contradictions (CACI, ROKU, EPAM, DGX, CAKE,
ADP), one additional ADP universal-percent rejection, two ambiguous contextual
critiques and 25 with no observed discovery contradiction. All 36 reviewed rows
match their original Git blobs. Historical bytes/grades were not rewritten.

**Verification.** Five negative cases failed on the starting implementation
for missing discovery context. Focused scanner/quality/grader/pipeline/report/
history/docs checks passed; all nine definite old contradictions are exercised
with scripted replies. Full pytest: PASS, 1,136; fixture check: PASS, nine;
continuity: PASS, 83; chart: PASS, 182. Focused browser: PASS, 467. Full page:
PASS, 3,613. Screenshots were inspected, including dated original reasons
on desktop, 390px and 320px. Evidence is under `evidence/scan-grading` outside
the checkout; CI results and exact published head belong to the milestone PR.

**Limits and next action.** Zero live market/provider/model calls; paid replay
NOT RUN. The six-row full fixture grows 223,781→228,193 bytes, gzip
26,480→27,159; no extra requests. Published data/picks/history are unchanged.
KEEP scan formulas, down-only grading, cache/parser/fallback, ticket/breadth
gates, continuity and private annotations. FIX the admission contract only.
DEFER dollar source-validation, broader measurement/provenance reliability and
live model replay. OMIT historical regrading or product expansion. Installed
and latest released design system remain v2.13.0, source `14a752d`, 22/22 hashes
match; no assets changed. Next: independent PR review and separate merge
authorization. Nothing merged, deployed, manually dispatched or emailed here.

PR #68's first automatic Secret Scan classified two copied public breadth
identifiers in `tests/fixtures/grading/record.json` as generic credentials.
The original source is already covered by the existing rule-key disposition;
the new fixture path was not. A second AND allowlist matches only those two
exact values at that exact path, with scope protection in the regression suite.
No fixture bytes, credential, default detector or historical commit changed.
The initial Tests run and subsequent CI results are linked from PR #68.

## Checkpoint, 16 Sep 2026 — universe, coverage and bar basis

Tahir authorized Stock-only repository edits, branch/commit/push and one PR;
no merge, live scan, deployment, email or credential/settings change. Branch
`reliability/input-truthfulness` starts at verified origin/main
`7e6d056672079e2ac46b6e5a84ae9589f1648e80`, after PR #68. The existing partial
draft was preserved and completed. Main was rechecked unchanged and no PR was
open before publication. Work used one active builder and no subagents.

**Reproduced on the base.** Five negative assertions failed as intended: a
valid common stock with directory volume 50,000 disappeared before its actual
+5% / 150,000-share reaction bar could be scanned; a $2.90 directory quote hid
an actual $3.05 breakout; a three-name fetch reported three requests after only
two were attempted; published coverage lacked its intended population; and a
September 10 scan did not identify its September 15 directory as a later snapshot.

**Settled contract.** Security classification no longer gates on directory
quotes. The existing $3 policy reads cent-rounded session closes after fetch,
with seed/explicit exceptions retained; actual-session volume stays in each
scanner. Selection and the extended DownloadStats reconcile directory rows,
classification, seeds, capacity, requests, no bars, retry failures, permanent
refusals, unattempted tails, stale/gapped/unreadable frames, benchmark, price
exclusions, measured routes and quality errors. Counts have bounded reason
samples and membership identities; inconsistent populations cannot publish.
Duplicate repair is an overlapping diagnostic, not another exclusive bucket.

The unchanged 50% minimum now means usable session bars divided by intended
stocks, excluding SPY and before current-price eligibility. Below it, or on
permanent refusal, no new record publishes. Partial coverage at/above it,
capacity cuts or scan/quality errors are degraded; incomplete empty results
name their evaluated subset. Complete means this selection, never every listed
security. The 8,000-name bound can exclude a breakout if it binds and is said
so; it cuts zero names in the measured archive. The 900-second budget stays.

**Basis and history.** The actual request and published metadata agree on
Alpaca daily `Adjustment.SPLIT`, explicit feed and expected/evaluated sessions.
Method, stock details, archived recovery context and newly saved originals
carry the basis. Old originals remain unknown. Nasdaq live/cache/seed/explicit
source, capture timestamp, selection identity, snapshot SHA-256 and date
relationship are explicit. Neither a current nor a cached directory establishes
historical point-in-time membership; no survivorship-free backtest is claimed.

**Measured impact.** The archived 7,141-row directory admits 3,039→4,797 stocks;
initial SDK batches rise 31→48 (+54.84%). The uniform 260-bar fake returns
790,400→1,247,480 bars in 13.260→20.186 seconds. Full fixture bytes are
228,193→231,724 raw and 27,159→28,034 gzip. These are offline measurements,
not live timing or dollar-cost forecasts. The twelve-read chart-reader cap is
unchanged; future candidate-dependent calls can vary within it. No live Nasdaq,
Alpaca, other provider, chart-reader model or Resend call was made.

**Verification.** Full pytest: 1,176 passed; fixtures: eleven current;
continuity: 83 passed; chart: 182 passed; full page with screenshots: 3,692
passed. Six targeted mutations were killed with unaffected controls remaining
green. Desktop and 390/320px screenshots, including Method, incomplete results
and saved continuity, were inspected. The last wording clarification separates
stock coverage from fetch counts that include the benchmark; its focused
Python/browser and regenerated-fixture checks are recorded in the PR. Design
v2.13.0 remains installed, all 22 hashes match, and vendored assets are untouched.

KEEP discovery v1, scan-aware grading, historical audit, My setups/recovery,
browser-local annotations and ticket/breadth gates. FIX the input boundary only.
DEFER holiday/short-session timing, full measurement-to-publication provenance,
dollar-formula source validation, real qualifying-ticket evidence and trading
edge. OMIT paid replay, manual deployment and sibling changes. Exact published
head and automatic CI status belong to the PR. Next: review that PR; merging
requires separate authorization. No older dispatch prompt supersedes this scope.

## Exchange-session truthfulness — next milestone after #69

Base `5dbcf41d157b37caaa519a3466c3a622f1945616`. This supersedes older
weekday/closure-inference descriptions above; historical publications remain
unchanged. `src/sessions.py` owns XNYS dates and actual scheduled hours through
pinned exchange_calendars 4.13.2. No handwritten holiday table or second browser
calendar. The calendar spans 1990–2035; scans require their lookback and plan
context within it. New rules digests include calendar identity, version, range,
15-minute completion buffer and the ±45-day browser schedule policy.

Baseline protections failed for their semantic reasons: Friday→holiday Monday,
Tuesday's previous session incorrectly Monday, accepted holiday pin, 16:00
serialized on a 13:00 close, holiday universe/provider work, fixed 16:15 completion
on an early close, and all-stale expected-open data incorrectly called closed.
All seven now have regressions. Six targeted calendar mutations were killed,
each with an unaffected outage control passing; originals were restored before
normal verification. Known holidays preserve every publication/pick/history byte
and send no duplicate signals or email. A missing expected-open session remains
coverage/outage evidence. Breadth includes expected missing dates; replay refuses
missing-session renumbering. Strategy formulas and thresholds are unchanged.

`run.calendar` records exchange/library/version, measured/prior/applicable dates,
scheduled open/close, shortened status and completion policy; `run.timing` uses
that same authority and retains the strategy's entry window. Browser freshness
uses the bounded serialized schedule; missing/out-of-range evidence is unknown
and research only. Method/email state actual hours and dates. New saves freeze
original timing; old records retain their limitations. Known closure is logged
as `no_session`, unfinished evening as `session_incomplete`; workflow persistence
requires `published=true`. Cron slots stay unchanged; either holiday slot may log
a no-spend skip.

Measured in the existing Python 3.12 environment: dependency install 23.926 s,
approximately 654 kB of new wheels and 2,836,036 installed bytes including package
metadata/bytecode. Added exchange_calendars, korean_lunar_calendar, pyluach, toolz,
tzdata; no existing dependency changed. Cold calendar construction 0.275 s;
1,000 warm completed/prior/next-five groups averaged 0.080 ms; first publication
snapshot 9.658 ms. Full fixture 231,724→247,832 raw bytes and 28,034→29,416 gzip.
These are local measurements, not production latency or dollar-saving forecasts.
On the deterministic Sep 2, 2024 holiday baseline, 32 symbols/one SDK batch/8,110
rows were read and a record published; now all provider work is skipped. Model
calls were zero in both versions of that holiday fixture. No live Nasdaq, Alpaca,
chart-reader/model or email call was made for this milestone.

KEEP input ledger, split-adjusted bars, discovery v1, scan-aware grading,
history/recovery, My setups/private annotations, ticket/breadth gates and design
v2.13.0. FIX calendar dates, hours, adjacency and closure truthfulness. DEFER full
measurement→grade→plan→publication provenance, dollar-formula primary-source
validation, real qualifying-ticket evidence and profitability evidence. OMIT a
calendar dashboard, speculative holiday maintenance and paid replay. Do not
merge or deploy; exact head and terminal verification belong in the focused PR.

Terminal local verification: 1,209 pytest cases pass; twelve generated fixtures
are current; continuity 83/83; chart 182/182; full page 4,057/4,057. The obsolete
prompt assertion requiring “tomorrow's open” was corrected to require “next
session's open” and forbid “tomorrow”; grading fields and thresholds remain
unchanged. Desktop/mobile holiday and shortened-session Method screenshots,
ordinary pages and saved-original timing were inspected. A final presentation
sweep labels the navigation “Latest scan” and the Method block “Published run”,
so an unchanged holiday publication is not called tonight's run. Calendar/mobile/
entry-window browser checks passed 155/155 for that wording; docs checks passed 33/33. All 22 vendored design
hashes still match v2.13.0. Production data.json, picks.json and history archives
are unchanged. No live provider/model/email call, merge or deployment occurred.

## Recommendation provenance — after #70

Base `f744b88a6117b933310f370b8f9ab4cd1d03a3c8`; Astra only. The user's
“Continue” authorized this focused Stock branch/edit/commit/push/PR session.
No merge, deployment, paid/provider replay, secret/settings change or siblings.
`src/provenance.py` v1 seals source/discovery/mechanical evidence at scanning,
actual reader input/result at grading, and inputs/output at planning. It joins
them to the run/input/calendar/rules/breadth/budget context and stable setup ID.
Canonical typed JSON uses exact binary64 hex floats, ordered daily labels and
the scanner/checklist's own normalized arrays, never rounded browser bars.
Discovery v1 and existing quality/plan functions remain authoritative.

New candidate, ticket, schema-2 model pick, recovery snapshot and saved original
share evidence identity. Grade is distinct from regime/budget ticket permission.
Fallback and unattempted readers contain no invented judgement. Anticipation
plans have an explicit measured/not-graded path. Final planning clears provisional
mechanical plans when the reader lowers quality below eligibility. Suggested
shares remain model sizing; local user annotations never enter public evidence.

`publish_bundle` verifies the actual serialized data/picks pair and retained
inputs before installing it; contradictions fail closed. Source frames/prompts
are compressed/deduplicated and exact chart images retained under docs/evidence.
Object bound 256 KiB, archive 128 MiB; capacity exhaustion fails publication,
without deleting originals. Ordinary installation failures roll back the pair;
there is no crash-atomic filesystem transaction. Legacy schema-1 picks migrate
without adding evidence; old publications report PARTIAL/unknown. Archived rules
that differ require the matching implementation for full replay. September 11/14
history and production records are never rewritten to fabricate provenance.

Before code edits, eight contradiction protections failed while their actionable
control passed. Seven later source-guard mutations were killed with two unaffected
controls each. CLI and canonicalization: docs/provenance/README.md; measured sizes
and runtime: docs/provenance/measurements.json. Initial browser requests added: 0.
The user-facing change is one concise detail paragraph and collapsed technical
reference. Design v2.13.0 remains unchanged. KEEP input truthfulness, calendar,
split-adjusted bars, discovery, down-only grading, breadth/tickets and My setups.
FIX the publication chain only. DEFER dollar-formula primary-source validation,
live qualifying-ticket evidence and empirical edge. OMIT portfolio/brokerage,
provenance dashboard and paid replay. Next: terminal verification and one PR;
the PR records exact head and final results, and remains unmerged for review.

Terminal local pass: 1,266 pytest cases (57 focused provenance cases), twelve
generated JSON fixtures plus retained source objects current, 89 continuity,
182 chart and 4,161 page checks. All PASS. Seven source mutations killed;
fourteen unaffected controls PASS. Desktop and 390/320px dark/light evidence
disclosures inspected, including red withholding. First full pass only exposed
the obsolete three-path artifact assertion; it now requires evidence/history.
Production records and all 1,408 historical files match the base byte-for-byte;
all 22 design hashes match v2.13.0. Live provider/model/email calls: zero.

CI passed all 1,266 tests and the page job, then exposed fixture-only raw-float
drift from NumPy's vector/scalar exponential kernels. Disabling X86_V4/X86_V3
locally reproduced the exact three differing source IDs. The synthetic provider
now serves eight-decimal OHLC and whole-share volume before the pipeline reads
it. Production hashing/inputs are unchanged. Both CPU dispatch paths regenerate
the same fixtures and source objects. The correction belongs to the same PR #71.

## Checkpoint, 16 Sep 2026 — primary-source Dollar reaction contract

Base `660e9beefd1125203628f8a162ddae4d6f3c3549`; branch
`strategy/dollar-source-contract`; Astra only, no subagents. Main matched
the supplied base, the existing checkout was clean, no PR was open and no
applicable AGENTS.md was present. The latest #71 checkpoint was read.
Prior branches/work were preserved in a separate worktree. Exact published
head and PR are recorded in the focused PR; nothing is merged or deployed.

**Outcome A, no formula change.** Bonde's public May 21, 2015 post establishes
the selected PRIMARY 4% formula. September 20, 2016 prints a Dollar PCF with
an inclusive current-volume floor; July 13, 2017 prints the selected
`c-o>=.90 and v>100000`. This is a dated primary mapping, not a claim of
one timeless formula or intentional universal supersession. The 2017 post's
4% volume floor is strict too; the repository retains its selected 2015
burst version. Near-high setup quality and high-price context are separate
from Dollar discovery. No prior/average volume or +4% condition is added.

`knowledge/reaction-discovery.md`, revision reaction-discovery-sources-v1,
is the source contract. It labels PRIMARY, LATER BONDE, COMMUNITY and
IMPLEMENTATION, distinguishes cent/share/ratio normalization and universe
policy, and keeps quality, breadth and plans downstream. Bonde's January 4
and January 14, 2014 article text was also inspected, alongside lukebrod's
May 29, 2022 TradingView description and the supplied field guide. The
July 5, 2017 video landing page and Wiley chapter metadata/summary were
partially inspected. November 18, 2015 blog full-text retrieval failed;
the supplied X thread returned 403. Full chapter, Pine code, embedded
charts/videos/transcripts and member materials were not inspected or purchased.
No latest-member-formula claim follows from these public sources.

README/Method's universal-4% introduction is corrected, with one source note.
Scanner changes are comments/docstrings only; its executable AST, constants,
grader prompt, schemas and payloads match the base. Source revision is
documentation only: no rules_version or evidence-ID change and no backfill.
The retained full fixture still has rules a6354faa5da9; production legacy
rules remain e1032aa5ee21. Discovery v1 and provenance v1 still verify.

Verification: 317 focused checks, 1,276 full pytest cases, twelve current
fixtures, 89 continuity and 182 chart checks; 4,182 page checks.
Desktop and 390/320px Method screenshots inspected; wording fits. Three mutations were killed (source label, volume boundary,
open/prior-close reference) with unaffected controls passing. All 1,408 history
files and 1,465 retained production/history/audit/provenance/design files match
the base byte-for-byte. September 11/14 grades are unchanged. Installed and
latest released design remain v2.13.0, source 14a752d, with 22/22 hashes intact.

KEEP #68–#71 software-trust layers. FIX source attribution and its presentation.
DEFER prospective live qualifying-ticket validation and profitability evaluation.
OMIT tuning, dashboard expansion, anticipation/EP edits and paid membership
research. Provider/model/market scan, email, manual dispatch, merge and deployment
actions: zero. Next: review the focused PR; no merge authorization is inferred.


## Checkpoint, 16 Sep 2026 — Burst actionability and chart readability

Base `964316f30a81035abf4dd5bd4be3ffbb2520a2fe` (merge #72), verified against
origin/main; branch `ux/burst-actionability`. Clean starting checkout, no open
PRs or applicable AGENTS.md. Latest checkpoint read. Astra only, no subagents.
Normal Stock branch/edit/commit/push/PR work is authorized in this session;
no merge, deployment, provider/model scan, email or settings/secret changes.

Before: the selected Burst put its chart and four explanations ahead of an
order sentence and disclosure. Now its recorded conditional stop-limit values
and applicable session appear directly under the stock header. Copy uses the
same recorded ticket and clock guard. Plan details retains sizing/terms; a
non-ticket/expired setup leads with No SpicyStock entry and its existing reason.
Browse cards stay compact. No trading levels or sizing are computed in JavaScript.

Candidate series remain first choice. New provenance-enabled Bursts lacking
browser series offer explicit Load recorded chart in detail/Compare. The bounded
same-origin gzip reader verifies typed float64 source identity and reference
context/dates, then displays up to 120 exact retained rows. It does not replay
strategy or claim the complete decision chain is browser-verified. No eager
requests or new assets; one 8,501-byte gzip fixture source request on demand,
zero on repeat selection. Failed/late responses preserve the rest of the page.
Saved originals and history recovery are unchanged. The committed legacy snapshot
still has 25 charts across 342 Bursts and no source receipts: no fabricated
retroactive recovery is claimed. See docs/actionability/README.md and measurements.

Evidence selection still only highlights. Focus evidence explicitly frames
recorded dates with context; restore returns to the prior Setup/60/120 range.
Focus never writes that preference. Earlier focused ranges cannot relabel their
last bar as the burst. Screenshots at 1280/390/320px in both themes support the
new composition; drawing heights stay 400/300px. The first desktop viewport now
prioritizes actionable values, with the full chart immediately following.

Validation: 1,304 Python tests, all 12 fixture checks, 89 continuity checks and
182 chart checks pass. Three integrity/value/focus mutations are killed with
six unaffected controls. The full page run passed 4,379/4,380: its only failure
was an old missing-browser-bars assertion expecting unavailable instead of the
new retained-source button. The corrected states suite passes 168/168; a full
4,380-check rerun and automatic exact-head CI are recorded in the PR closeout.
The first chart gate caught ES5 syntax in the standalone renderer; moving the
loader to app.js restored app-chart.js byte-for-byte and the final gate passes.
All 1,497 protected source/fixture/history/design files match the base. No
runtime rule, discovery/provenance version or evidence identity changes. Existing
September 11/14 grades and data/picks remain immutable. Installed shared design
v2.13.0 retains all 22 hashes; siblings and shared upstream were read-only.

KEEP #68–#72 trust contracts, history, annotations, calendar, grading and ticket
gates. FIX selected-stock actionability, authentic optional charts and explicit
focus only. DEFER following-plan observation/reconciliation, live qualifying-ticket
validation and profitability work. OMIT Fidelity connectivity, personal execution
tracking, scoreboards, strategy changes and paid research. Next: final gates and
one focused PR for review; do not merge or deploy.

## Checkpoint, 16 Sep 2026 — overnight campaign, followed published plans

Tahir explicitly authorized this sequential Stock-only campaign, including merge
commits after exact-head Tests/Secret Scan, required local checks, material review,
clean tree and mergeability all pass. This supersedes the earlier no-merge handoff.
No paid/provider/model calls, scans, broker connections/orders, external messages,
settings/secrets changes, shared-design writes or manual deployment dispatches.

Milestone 1 PR #73 merged as `3f8d0f2dcd69cc7af8260b336afb5adbc6d3e417` after all
local gates and exact-head CI passed. Origin/main matched its reviewed tree.
Automatic publication and post-merge checks passed; public app.js returned HTTP
200 and exactly matched that main. No production scan was dispatched.

Milestone 2 branch `product/followed-plan` starts from that merge. The baseline
browser journey proved the explicit selection control was absent. A ticket now
permits I followed this plan, atomically saving the original and the browser-local
selection timestamp. The recorded order and dated horizon are frozen; existing
snapshot timing and evidence fields hold the original session and full plan/pick
receipt. No trading level, fill, actual quantity or outcome is computed here.

Following schema v4 preserves v1–v3 backups, original evidence, reference amounts,
shares and unknown fields. Legacy taken annotations keep their old meaning and
are never converted into selection or execution evidence. Original plan identity
missing means exact model outcome unavailable. Removing selection keeps the save.
A stale tab cannot resurrect a removal or silently select a different publication.

Record replay now carries its existing persisted pick receipt into public model
rows. Following joins only exact evidence/context/plan/pick identity plus signal
kind/ticker/session. It caches a dated public outcome when loaded, never replaces
it with an older publication, and retains it after the public five-session model
window. A terminal state not loaded before that window ends remains unknown.
Public observations continue independently, including missing/stale/horizon and
price-basis caveats. Personal choices do not affect public population or scorecard.

Focused validation: 143 record/provenance checks, 11 selection-store checks,
90 continuity checks and 197 browser checks passed. Three meaningful mutations
(identity, newer outcome, ticket-only selection) were killed with unaffected
controls passing. The unchanged 4,000-character low-storage regression caught
unnecessary duplicated plan fields; the compact chart-free save is 3,979 characters.
Full verification and exact published head/PR are recorded in the PR closeout.
Final material review also applies the receipt guard to native saves without a
personal selection. Its mismatch mutation was killed with 11 independent store
controls passing; the corrected focused browser run passes 198 checks.
Only offline sequel fixtures gain outcome receipt fields; production data/picks,
September 11/14 history, source objects and reaction rules remain unchanged.
Installed/latest design v2.13.0, source 14a752d: 22/22 hashes intact, zero drift.

Next: complete milestone 2 gates, open and merge only its accepted exact head,
verify new main/publication, then complete milestone 3 using the existing public
Record scorecard. No personal performance calculation or parallel outcome engine.


## Checkpoint, 16 Sep 2026 — overnight campaign, public model scorecard

Milestone 2 PR #74 merged as `e6fa0a967d1765e4600222853df3043c430f5d62`, from
reviewed head `a2882e57929e4f92a7ba73d1823da77c0e365511`. Local verification:
1,321 Python, 12 fixtures, 90 continuity, 182 chart and 4,437 page checks PASS.
Exact-head Tests and Secret Scan PASS; clean/mergeable gates passed. Main matched
the reviewed tree. Automatic publication, Pages and post-merge checks passed.
No manual dispatch or live scan. User explicitly authorized these campaign merges.

Milestone 3 branch `product/model-scorecard` starts from that accepted main.
There were no other open PRs or intervening publication commits at branch start.
The existing scorecard silently skipped plans without bars, hid coverage counts,
and could lose a resolved result to gaps after its five-session horizon. Six
new baseline tests failed before correction. Replay/fill/exit rules themselves
remain unchanged; there is one outcome engine. Missing or stale unfinished
observations now stay unmeasured, rather than disappearing or implying open.
Current-publication plans stay pending and all eight outcome buckets reconcile.

Reporting contract 2 records the population window, retained-file limitations,
input basis and replay rules digest. Wins/losses/breakeven reconcile to resolved;
mean/median R and win rate have that explicit denominator and the existing
20-resolved display threshold. SPY has its own pair count. Counts are not an edge
claim. The existing Record page leads with a compact shared count strip; rates
are a line, methodology a disclosure, model-plan rows follow. Small samples and
legacy incomplete accounting are explicit. Initial stacked mobile tiles were
replaced after screenshot inspection; chart dimensions are unchanged.

Offline `tools/scorecard_analysis.py` calls the same replay/summary, preserving
unknowns in full partitions by original rules version, burst/dollar/both,
grade, entry regime, kind and reader source. Native attribution requires all
four original receipt digests and an integrity-verified publication. No source
frame replay is claimed by that metadata check. Supplied offline outcome bars
still need independently established basis; no provider calls are made.

Twelve focused accounting/analysis tests cover missing/pending/stale coverage,
all outcome classes, rounded breakeven, no invented zero result, horizon,
retention, exact attribution and CLI behavior. Four mutations (missing-plan
omission, stale-as-open, guessed attribution, small-sample rate display) were
killed; independent controls passed. Focused record/pipeline/provenance/docs verification passes 222 tests; the
complete fixture/browser journey passes 498 checks after the compact spacing
pass. Final normal gates and exact CI are recorded in the PR closeout. Screenshots are inspected at 1280/390/320px
in both themes. `.env.example` was reviewed; no environment/workflow change.

Production data/picks, history, source objects, discovery/provenance v1, grading,
plan constants and all existing receipts remain unchanged. Generated page
fixtures differ only in scorecard and its descriptive contract: +634–635 raw
bytes, +216–238 gzip bytes. Live data.json remains 2,962,276 raw / 264,521 gzip.
No extra chart series or browser requests. Installed/latest design v2.13.0,
source 14a752dd0269bd6ebbb7080eb0d9e1922cd1ef2c, 22/22 hashes, zero drift.

KEEP the trust stack, original signals, browser-only selection and uncertain
outcomes. FIX public denominator/coverage and compact Record readability.
DEFER prospective qualifying-ticket evidence, actual execution reconciliation
and trading-edge evaluation; none was performed with synthetic fixtures.
OMIT Fidelity/broker connections, strategy tuning, parallel outcome engines,
new dashboards/workflows, paid/provider/model calls and manual deployments.
Next: complete exact-head gates, merge only the accepted PR, verify new main
and automatic publication, then report completion of the three received
milestones. The supplied campaign message ended mid-milestone 3 at “Personal”;
no additional milestones or missing instructions were invented.

## September 17 — first scheduled post-release acceptance correction

Tahir authorized repository edits, branch/push and one correction PR in this
execution session. No merge is authorized. Scope is SpicyStock only; siblings
and the shared design system remain read-only.

Pinned acceptance publication is `580805487b22006c6f2fa35490c3edc8a5760d73`,
parented by engineering merge #75, `7859ae081a1cbb12ef4c2f949ee0e699df893bc8`.
Remote main still matched that publication and no PRs were open before this
branch. Run `35157356943`, attempt 1, is the ordinary scheduled evening run:
GitHub success, pipeline exit 2/degraded. The actual Pages URL from deployment
metadata is `https://spicychicken59.github.io/SpicyStock/`. Read-only HTTP checks
matched the pinned data, picks, app and HTML bytes. No scan was regenerated.

The actual offline verifier returned PASS for both `--record docs/data.json`
and `--archive docs/history/9dfc2d51aef7d0adf723428931c61cc83824fa71`, with
`--picks docs/picks.json --objects docs/evidence`: 308 candidates checked,
no breaks and no missing layers. This owning-function replay does not certify
reader prose. No real ticket exists in this publication or retained archives.

JRSH reproduces the explanatory mismatch: raw reader prose calls 0.34 the A+
giveback ceiling; the recorded criterion is ordinary <=0.34, A+ <=0.25.
`burstDecision()` now reports recorded checklist/grade facts, while
`discProvenance()` retains the raw commentary under an explicit authority note.
Risk summaries/comparison and saved/recovered originals carry that same
boundary. No NLP checker, ticker exception, grade change or reader replay.
JRSH remains mechanical A, published C; no original receipt or generated file
is rewritten. Byte-for-byte JRSH/JKHY regression copies live under
`tests/fixtures/grading/reader-commentary/` with their source and hashes.

The legacy verifier regression incorrectly read today's production file and
assumed it was legacy. It now uses existing fixed September 11/14 originals,
asserting PARTIAL/missing legacy evidence and no mutation for record and archive.
README was updated; .env.example was reviewed and needs no change.

Before/after execution: the new JRSH regression fails on the original primary
explanation, then passes after the boundary fix. Removing the risk attribution
in an in-memory mutant fails the risk assertion; an unrelated deliberately
wrong no-entry sentence leaves these controls passing. No mutant touched the
working tree. Full local pytest: 1,333 passed; fixture check: 12 current;
continuity DOM/store: 127 passed; geometry-only chart check: 112 passed. A
separate deterministic harness over the exact pinned full publication passes
32 checks, including all nine red-gated As, JKHY Dollar-only admission,
MANH retained-source recovery/cache reuse, and authentic older VICR chart
unavailability. Zero initial evidence requests; explicit MANH recovery fetched
one 5,250-byte source object and reused it without another request.

Local browser/visual acceptance remains BLOCKED: the interactive browser
capabilities could not establish a fresh profile or required viewports, and the
repository test runner's Chromium download timed out. No real profile was
mutated. New browser regressions are queued for normal PR CI, with retained
excerpt screenshots in both themes at 1280/390/320. CI results and any actual
visual inspection must be reported separately after execution. Fixture tickets
are never production tickets; local plan selection is not an order or fill.
No provider/model call, brokerage action, schedule change, message, deployment
change, shared-system write or empirical profitability claim was made.

PR #76 was opened at `e1d75891a12d37510c1d65ea175ee34a79c4b237` with tree
`2279300390abb40ccad163bfb6dbcf5e18ba12a6`, byte-identical to the locally
verified commit. Shell push lacked authentication; the connected GitHub API
published that verified tree. The original local commit remains on a local
branch. Exact-head CI Python and fixture/clean-tree checks passed. Secret scan
identified the same two public breadth-rule identifiers already allowed in
PR #68's retained context fixture. Its existing exact-value/path exception was
extended only to `tests/fixtures/grading/reader-commentary/record.json`.
Gitleaks 8.24.3 reproduced the original two findings, passed the corrected
path, still rejected a synthetic credential at that allowed path, and still
rejected those identifiers at an unrelated path. No detector/file exclusion,
GitHub settings or secrets were changed. The publication and archive verifier
were also rerun on the PR head: both PASS, 308 checked, no missing layers.

The first page CI job passed 127 DOM/store and 182 chart checks, then reached
the new retained-reader case and stopped because its test locator selected
both the outer Provenance summary and the nested technical-reference summary.
The regression now selects the direct child summary. This was a test-harness
strict-selector error, not a second product defect; the application tree is
unchanged. Final CI and visual results belong to the subsequent PR head.

## September 19 — bounded evidence focus correction, PR #77

Tahir authorized one Stock-only correctness PR, without merge or manual
deployment. Both the supplied baseline and inspected origin/main were
`8387ccedae22fbf30ddebdb6f52e1e42326a7ec5`; no intervening commits or open PRs.
The clean checkout preserves #73–#76. Coverage work remains deferred.

New source-attributed BPOP/BNY chart excerpts reproduce the acceptance failure
without mutable production data. On untouched application code, geometry-only
tests FAIL at 1440/390: BPOP stays at 36 observations and 1.000x magnification;
BNY expands 17 to 21 with 0.852x candle spacing and unchanged price scale.
The initial normal-browser test had an incorrect SVG selector; that test-only
error was corrected before judging the baseline browser results. The corrected
baseline CI head is `794b08f15be48e93be8954cfe2ba21c0f1780bad`.

`focusSlice()` now keeps three context observations on available sides of the
whole selected evidence, expanding evenly to 21 where available. If the normal
range comparison cannot deliver useful horizontal spacing, the actual SVG is
temporarily drawn 30% taller. Each Focus compares to the normal range rather
than the previous focus. Selection, stored preferences, normal layout, exact
recorded prices and the date-specific burst guard are unchanged. No renderer,
CSS or shared-design modification was needed. README reflects this behavior;
`.env.example` was reviewed and needs no change.

Local geometry results PASS: BPOP 36 to 26 observations, 1.3125x spacing;
BNY 17 to 21, 1.3345x desktop and 1.35x mobile price scale. Reverting compact
padding or temporary height is caught independently; an unrelated wrong
no-entry sentence leaves the focus controls passing. Local offline gates PASS:
1,333 Python tests, 12 fixtures, 127 continuity and 112 geometry checks.
All 3,844 protected files and all 22 design v2.13.0 hashes match the base.

Local Chromium remains BLOCKED by its download timeout. Normal automatic PR CI
owns the full browser gates, 84 pinned-evidence journeys and boundary cases,
actual SVG measurements, screenshots, keyboard, Restore and localStorage/reload
acceptance. Their results and visual inspection are recorded in the PR closeout
and evidence checkpoint; the geometry results above are not visual acceptance.
The report shell and altered boundary targets are explicitly offline fixtures,
not new production evidence, provider validation or a trading-edge claim.

## September 19 — bounded Explore pane scrolling, PR #78

Tahir authorized one Stock-only frontend correction PR, not a merge or manual
deployment. Supplied baseline and actual starting origin/main both matched
`9ebf27ca42845d2892fc5868a80a253b1ceadccd`, the merge of accepted #77. No open PRs
or intervening commits existed. Existing clean checkouts were preserved; work
uses `fix/explore-pane-scrolling`. No AGENTS.md applies. Shared design remains
v2.13.0 at `14a752dd0269bd6ebbb7080eb0d9e1922cd1ef2c`; siblings are read-only.

FAIL before: the regression-only head `124ce78af4671a46a8f0a1d91579a171b4a3ed90`
leaves application code untouched. Automatic Tests `35417284346` ran fresh
normal-origin Chromium contexts. Its 72 failures cover both stages, both themes,
1440x1000 and 1280x800; all pre-existing browser checks pass (6888/6960 total).
The offline full.json fixture is expanded only in memory with labelled TESTB/
TESTS candidates (46/19 totals). This is not a production publication or the
retained 360-Burst guidance record. In the dark 1440 viewport, Bursts has a
10,550px list; wheel leaves list.scrollTop at 0 and moves pageY 502 to 1152.
End/Enter selects TESTB040 at pageY 10608 with detail.top -10089.52px. Setting up
has a 3,335px list and detail.top -2891.52px after selecting TESTS018. The
1280 viewport reproduces both. Page-viewport screenshots were captured before
any operation targeting the detail and inspected: the neighboring area is empty.
Artifact `10576691414`, ZIP SHA-256
`51b0a566016afc9f052a82a95ffbe6c246b47fb0b44c3cf6a7a28fa67929bd0a`.

The fix bounds desktop Cards only: fixed header/filters, native list overflow,
matching full-detail overflow, unshrunk cards and normal chart heights. Scoped
nearest scrolling reveals focus/selection without moving the document; a stock
change resets detail only, while rerenders preserve reading/browsing positions.
Previous/Next retains keyboard focus. Mode/breakpoint changes clear the obsolete
scroll axis. Mobile rail and full-width Map remain their existing compositions.
The chart renderer, focusSlice/chartPanel and #77 geometry are unchanged.

PASS local offline gates before implementation: 1,333 Python, 12 fixtures,
127 continuity and 112 geometry-only checks. PASS continuity after implementation.
BLOCKED local real browser: Chromium is absent and its download times out.
FAIL first corrected browser run `35417985180`, head
`6f993cbdbd29cbb91b087c23a623a8b5e1bcf3f3`: 7301/7304 page checks pass. All core
pane journeys and #77 regressions pass. Remaining findings: height-only resizing
can clip the selected card; the fixed filters push the first card below the
existing first-screen gate; one test clicks a partially clipped preceding card
and incorrectly expects no nearest-position adjustment. The corrected journey
first browses to a fully visible different card before measuring preservation.
The correction reveals selection on viewport resize and tightens only header
gaps. Named Back/deep links clear an incompatible search, and live search updates
the existing stepper without selecting or rebuilding the chart. These also have
explicit browser checks. PASS this head's Python/fixture/clean-tree, continuity,
182 chart checks and Secret Scan. Final exact-head results remain in #78.
README is updated; .env.example reviewed with no environment change needed.

KEEP all production data, history, receipts, source evidence, rules, plans,
grades, Following and scorecard semantics. Coverage stays deferred: the retained
record's 4774/4793 ready stocks and 19 stale inputs are unchanged. No new scan,
provider/model call, broker action, external message, setting, schedule, shared
design write or manual deployment. Stop at one evidence-backed reviewable PR.

## September 19 — website comprehension campaign, #78 responsive acceptance

Tahir supersedes the earlier single-PR stop: normal Stock-only campaign merges
and their established automatic publication are authorized, with exact-head
Tests/Secret Scan and actual review requirements; no bypasses or manual deploys.
Continuation began at 08:06:36 UTC. No original five-hour campaign deadline could
be verified; the previous bounded #78 task ran approximately 48 minutes. Keep
that completed work and reserve the final integration hour rather than claiming
a fresh five-hour window. The user makes first-visit comprehension the priority.

A frozen-main CSS comparison proves the constrained header predates #78. At
721/768px the AAPL fixture identity's grid column is 0px on main and on #78;
at 820px it is 46.86px on main and 23.86px on #78. A pane container query stacks
identity, badges and navigation without changing the page breakpoint or font
size. Corrected widths at 721/768/820/960 are 310/357/409/549px; header heights
188.19/167.39/140.39/143.47px. The prior #78 heights were 376.16/376.16/376.16/
132.06px: the 960px header intentionally takes an extra short row to provide
readable width. Constrained ticket levels use two columns as on phones.

PASS focused normal-origin Chromium: 548 pane checks, including new readable
identity-width and bounded-header checks at 721/768/820/960 in both themes.
Screenshots inspected: 721 dark and 960 light viewport Cards plus AAPL's ticket
at both widths; source comparison and measurements are in campaign evidence.
This preserves native pane scrolling, the phone rail/chooser and full-width Map.
Full final-tree and exact-head CI results are recorded on #78 before merge.

No strategy, production evidence, chart geometry, saved semantics or shared
v2.13.0 design files change. README is updated; .env.example reviewed with no
changed configuration. Next slice must branch from the actual accepted main.

FAIL local Python on the continuation's Saturday clock: one existing intraday
fixture omitted `now`, so the correct non-session early return left no live
file. The test now supplies its intended September 11 session, matching the
neighboring test. This repairs the test fixture only; calendar/production code
is unchanged. Its failure was reproduced before correction (1,332/1,333 pass).

## September 19 — first-visit comprehension campaign

Readability starts from #78 merge `d273256f5fbfde826a76eb596eb756fe7e67f59f`, head `13d527be5aedbd7b73ca7a5045b658e39315f8aa`. Tests 35431463638, Secret Scan 35431463692, publication 35431920098 and Pages 35431927661 PASS. Continuation began 08:06:36 UTC, retaining 48 prior minutes; deadline/quota unverified.

The first screen explains purpose, order, population/session and snapshot/account boundaries. Conditions show a plain question, local verdict, observed measurements and periods, this record’s ordinary rule, and method rationale. A+ requirements, precision, formulas and attribution remain inspectable. Unknown rule formats remain uninterpreted. UNMEASURED/PARTIAL display accurately; scores stay unchanged. Discovery, grade and ticket differ. Waiting has a next action; missing risk narrative never means no risk.

Hover/focus/tap disclosures support Close/Escape, viewport placement and Method routes. Return restores stock, scrolling and Compare. Dated evidence, Focus/Restore, chooser, Map and saves remain intact. Captions distinguish candle direction, prior-close gain, evidence, plan levels and volume references. Compressed Map distances and selection overriding source fill are explicit.

Section-purpose inventory:

| Section | Reader’s question | Basis | Useful action | Visible / optional |
|---|---|---|---|---|
| Latest scan | What was found, when? | Own session and coverage | Check context | Counts/date / full ledger |
| Market | What is permitted? | Recorded breadth/regime | Respect entry filter | Regime / fired rules |
| Candidates | Why included/graded? | Discovery/checklist | Choose evidence | Status / admission formula |
| Selected stock | Evidence, permission, invalidation? | Checks/plan/timing | Inspect, plan or wait | Action / conditions/provenance |
| Compare | Which differences matter? | Same-record fields | Choose what to inspect | Differences / full setup |
| My setups | What was saved/observed? | Browser snapshot/later records | Revisit | Save state / dated observations |
| Record | What did the model do? | Public bar-based replay | Inspect assumptions | Outcomes / accounting detail |
| Method | How do I read this? | Definitions/source contracts | Verify and return | Journey / anchored rules |

Semantic-colour inventory (existing palette retained):

| Family | Authority and meaning | Does not establish |
|---|---|---|
| Market | Recorded regime: sizing/refusal | Stock permission |
| Checklist | Recorded pass/partial/fail/veto/unknown | Profit or whole-setup approval |
| Publication | Session/input status | Open entry window |
| Timing | Dated permitted interval | Valid ticket/fill |
| Ticket | Published terms plus availability | Submission/execution |
| Chart/Map | Direction, evidence, levels, source/selection | Forecast or grade |
| Saved | Browser write confirmation | Stock assessment |
| Model outcome | Recorded replay state | Personal holdings/instruction |

FAIL before: independent rendered-only review could not reconcile passing linearity or failing base from truncated values, and found ambiguous purpose/marks. PASS after: all eight questions were answerable; follow-up resolved misleading risk wording. These are simulated agent reviews; actual human validation NOT RUN. Screenshots cover 1440/1280/960/820/768/721/390/320, both themes; keyboard, touch, reduced motion and enlarged text are exercised. Phone future-window detail still needs scrolling; dense chart values remain available in its table.

PASS local: 1,333 Python tests; 12 fixtures; 127 continuity checks; 182 chart checks; 7,531 browser checks. PASS failure controls: wrong period/threshold rejected, unrelated change accepted. Exact-head release evidence follows in the PR.

FAIL two #79 CI runs: 7,530/7,531 checks; first card 13px below viewport. Compact status left CI geometry unchanged. Cards workspace gap: 24→8px; type/controls/warnings unchanged. The first-screen limit remains 900px and must pass before merge.

All 22 v2.13.0 hashes and 2,583 protected files remain unchanged. README is updated; .env.example unchanged. Contracts and the secondary guide ground explanations. Stale-security diagnosis stays deferred. No scan, paid call or manual deployment. Final release identifiers: PR and evidence report.

## September 19 — September 18 stale-input investigation

Repository: spicyChicken59/SpicyStock. Investigation branch:
`investigation/stale-inputs-20260918`, based on verified main
`3f4b3312c136104f0c187dd495e4c8e035bd48e1` (tree
`c1a4b329eca236b60cbf896403278c2f5e765eab`). This is one evidence-focused
PR; its exact head and standard check results are recorded in the PR description.
Tahir authorized this bounded builder investigation and expressly reserved
merge for independent guidance review. No campaign or effort-setting change
is implied; the selected effort and remaining quota were not independently
verified.

The [dated report](docs/input-truthfulness/2026-09-18-stale-inputs.md) pins
run 35401227388, artifact 10570901548, actual ingestion checkout
`ebcdea34464b9090e7734ca543be8733d39fc20a`, publication
`8387ccedae22fbf30ddebdb6f52e1e42326a7ec5`, and original data.json SHA-256
`aae64bbd1be0c0126f9c24c6ad5b4b5be1434a51e7351e5085c2f00862215567`.
PASS original-byte identity and before/after evidence integrity. The history
identifier is a Git blob identity, not an execution commit; its record.json is
a context subset. The ZIP contains 3,687 entries. The directory is retained
separately in the publication commit and exactly reproduces all 4,793 intended
stocks and their recorded selection identity.

Retained logs/ledger establish that 19 normalized frames ended September 17
and were withheld for September 18. Coverage remains degraded: 4,774/4,793
intended stocks ready; 3,731/3,731 scan-ready stocks measured; 12/12 reader
calls recorded complete. PASS conservation. Only ANTA, BKHA, BLIV, BMHL, EGHA,
GDEV, HCMA and INTJ are individually identified. BLOCKED recovery of the other
11: the bounded sample/digest cannot supply their names. Original stale frames,
HTTP pages and provider entity mappings were not retained.

The eight-row table separates dated issuer/exchange disclosures from directory
metadata and provider documentation. BKHA, EGHA and HCMA expose an exact-label
classification limitation: retained operating-industry labels admit them,
while dated filings describe blank-check companies. A copied-row fixture
reproduces the distinction. This is not proof of the missing-bar cause or
complete September 18 security status. Every sampled provider cause remains
unresolved; no legitimate absence, halt or mapping failure is asserted as fact.

PASS 210 local diagnostic/universe/market-data tests, including deliberate
incorrect-input controls. FAIL existing input/pipeline suites: 25 failed,
49 passed because Windows fixture publication replaces a still-open temporary
file; downstream records are then absent. No production correction or test
weakening is included. Full Linux PR checks were NOT RUN at checkpoint commit;
their exact-head outcome belongs in the PR. Local package differences and
commands are recorded. Browser/visual/human checks are NOT RUN locally.

KEEP original records, unknowns, denominators, completed website behavior and
installed shared design v2.13.0. FIX NOW the evidence gap in the handoff through
this report and reproducible read-only diagnostic. DEFER any dated shell-policy
correction, Windows portability fix or newly authorized provider investigation.
OMIT guessed stale members, inferred provider causes, retroactive exclusions
and cosmetic coverage repairs. README is updated; .env.example reviewed and
unchanged. No scan, directory refresh, application model call, manual publication,
schedule, secret or shared-design change occurred. Exact next action: guidance
reviews this evidence PR and its checks; builder stops without merging.

FAIL first Linux PR run 35467846396 at head
`3d81fec5459f49795982b5b2dd73697105ad7a66`: 1,336 passed; the sole failure
was the handoff's current suite count (1,333 versus 1,337 after four added tests).
The current count is corrected to 1,337; the count assertion is unchanged.
Final exact-head gates remain recorded in the PR.

## September 19 — bounded input-exception evidence retention

Repository: spicyChicken59/SpicyStock. Base main is
`2b44d227829e6859d7f65358534022fa8cc8553a`, tree
`72071ad648b3183fbe63c19a3bd927b10ac1c04e`. Before edits, post-merge Tests
35468881024 was rechecked completed/success; main had not advanced, zero PRs
were open, and no input-exception-evidence branch existed. Work is on
`reliability/input-exception-evidence`. The user reserves independent review
and normal merge for guidance. Effort settings were not changed; their value
and remaining quota remain unverified. No new campaign budget was inferred.

The first full local suite found the new module missing from README's enforced
inventory and extra CLI fields on skipped/mocked runs. Both are corrected:
the inventory names the module and not-attempted runs retain the old exact CLI
output. Explicit tests cover artifact outputs on retained/failed capture paths.

The dedicated input diagnostic captures after existing session classification
and before price/coverage refusal, scans, grading or publication. It retains
complete exception and intended memberships, original ledger identities,
benchmark distinction, actual checkout/run/attempt/session context, and bounded
normalized observations. Eight tail rows plus expected/prior anchors permit at
most ten rows per symbol, with a global 80,010-row payload limit; membership is
never sampled away. Missing, null, nonfinite, absent-field and unreadable states
remain distinct. No arbitrary exception text, clients or account/environment
objects are serialized. Supplied fetch arguments are explicit and reconstructed
windows are labelled. A directory is copied byte-for-byte only when actually
used and matching the universe's capture time and canonical hash.

The existing evening workflow gains one separate 30-day diagnostic upload,
using only this invocation's emitted path. Its old artifact name, paths and ZIP
root remain unchanged. Cron, inputs, permissions, retries, persistence and
publication guards are untouched. Known skipped/preflight runs produce no
snapshot; failures before completed classification remain unavailable. Capture
failure is separately logged/reported and changes no existing error, retry,
coverage, trading decision or exit code. Process termination before output-path
emission can still prevent upload; no durability beyond that boundary is claimed.

PASS failing-before control: the unmodified base publishes the synthetic
19-stale cohort with eight public names, then fails specifically on its missing
diagnostic. The implementation retains every name and available observation.
These names are not the historical missing eleven. Focused tests cover refusal
after earlier successes, never-attempted tails, each input category, timestamp
precision, row bounds, overlapping duplicates, used-directory bytes, sentinel
exclusion, tampering, identity mismatch, consecutive runs and writer failure.
Frozen clocks compare enabled/disabled publication bytes and all coverage/call/
exit behavior. Candidate comparisons include prepared records, picks, objects,
plans, grades and rule digests; normal Linux CI also requires publication.

The deterministic extreme fixture fills 80,010 rows across 8,001 exceptions:
approximately 45.56 MB JSON / 0.40 MB gzip, plus at most 10 MiB directory.
Real compressed size is not predicted. Full local/CI outcomes and exact head
are recorded in the PR. Local Windows reproduces the accepted source-object
open-temporary rename defect; no portability repair or gate weakening is included.
README and .env.example are updated only for the new output, with no new variable.

KEEP compact coverage, unknown provider causes, historical pins, strategy and
all accepted website/design behavior. FIX NOW future loss of complete exception
membership and bounded observations. DEFER classification correction, transport
research, Windows publication portability and production artifact verification
(NOT RUN until an existing authorized run produces it). OMIT provider/scanner/
model execution, directory refresh, manual dispatch/publication, secrets/settings
changes, sibling work and merge. Next action: guidance reviews the scoped PR
with exact-head Tests and Secret Scan; builder stops without merging.

## Checkpoint, 19 Sep 2026 — the method, one burst at a time

**Revision.** Branch `claude/fervent-dirac-9digzt` from `main` at `27b2b49`
(the merge of #81). Tahir uploaded a standalone HTML explainer of the method
that had finally made it click for him and asked for it on the site; it is
integrated into the Method view, on the page's own design system, rather
than linked as a page off it. `docs/data.json`, `docs/picks.json`, the
history, the evidence objects and the vendored design system are untouched;
nothing under `src/` changed; no run, mail, merge or deployment.

**The explanation was checked against the code before it was kept, and
three things it said are not what this build does.** Its "Day 1" was the
burst day, so its day 3 and day 5 sat one session early: the record numbers
the fill day as day 1 (`plan.ENTRY_DAY`) and everything from it. It sold
"half more" at day 3's close after a +8% half: `plan.follow()` sells the
day-3 half only when the +8% half was not sold, then the remainder on day 5.
And its buy zone was the retired −2%..+4% ceiling: the limit is
`plan.burst_limit()`'s stop-constrained price, +4% is the extension
threshold, and at that limit every ticket's stop sits 3.99% under it, so the
risk is halved on every one (all four fixture tickets carry `risk_halved`;
the walkthrough says so). Its synthetic bars were redrawn so
`quality.assess()` reads the drawn base as the base — the highest high of
the 40 sessions before the burst opens it, so a base that makes its high
late is two sessions long — and finds no earlier 4% day in the move; the
code grades them A+, 10 of 10.

**What was built.** `docs/app-method.js` (`SCStock.walkthrough`): eleven
steps over one 27-bar synthetic series, the chart drawn in px at its own
column's width on the page's tone slots, gutter labels spread by
`SC.spreadLabels`, a table twin, keyboard, Play with a test-injected
interval, reduced motion honoured. `RULES` names every number a caption
quotes for its constant, `BARS` and `EXAMPLE` are JSON, and
`tests/test_walkthrough.py` holds `RULES` to `src/` and re-derives `EXAMPLE`
— scan, checklist, `burst_plan()`, `pick_of()`, `replay()`, `r_multiple()` —
so the page prints what the code writes (+3.04R, settled on day 5). A
literal guard refuses a digit in a caption that is not a year, 2LYNCH, the
score's ten points, the plan's own day-2 field, "3rd" or the letter 2.
`#/method/walkthrough` keeps its path; the card stands on the no-record
page; README's layout is held to every `docs/app-*.js`.

**Measured** (offline, this sandbox): 1378 tests (8 new); 12 fixtures
current; continuity 127; chart check 182/182; the walkthrough suite 106/106
with `--shots`; the suites that visit Method 1075/1075. **Seven mutants,
all dead, a control green in both harnesses:** a drifted rule, a drifted R,
a bar out of place, a bare 4% in a caption, a reveal that ignores the step,
the day-2 line printed as the limit, Next never refused. The bare-4% mutant
SURVIVED the first guard, which allowed "4%" anywhere for the scan's own
name: the scan's 4%, the Market Monitor's 25% and 50%, its 5- and 10-day
ratios and the entry day are quoted from the modules now and that
allowance is gone. gitleaks 8.24.3 over the new files: no leaks.

**The screenshots found what the checks had not.** The chart was drawn at
the mount's width — the whole card — and scaled into its 3fr column: tiny
candles and 6px labels at 1280 while every assertion passed. It measures its
own column now, and a check holds the drawn width to it. Then, each found by
looking: labels past the gutter (the gutter is sized from its longest
label), the burst word on D1, "2 · N" over the base's label, two sale pills
on each other (the words moved to the gutter), and a phone's "burst" against
"hold" (two axis rows under 560px). Twenty-two step screenshots at 1280 and
390 and two at 320, both themes, were looked at.

**Keep / fix / defer / omit.** Keep: the walkthrough reads no record and
decides nothing; every number it prints is the module's. Fix if it bites:
the score's "of 10" is the one number a caption carries that no single
constant names (the six weights sum to it). Defer to Astra: unchanged.
Omit: a walkthrough over a real burst from the record. **Not claimable:**
a live fetch, Resend, Pages, and CI on this branch until the pull request
runs.
