# SpicyStock — working notes

**Active goal (updated 10 October 2026):** [PRODUCT_GOAL.md](PRODUCT_GOAL.md) is the
current product direction and milestone contract. Mo uses a $2,000 cash
account and America/Chicago time; the broker is unspecified. New production
workflow sizing is versioned at $2,000 / 0.5%; historical publications and local
default model assumptions retain their own values. Mo explicitly authorizes an
ongoing choose/build/test/review/merge/verify loop until manually stopped. Resume
unfinished work, choose the next useful independent milestone, and record actual
production evidence before calling a release complete. The hourly ChatGPT task
**Build SpicyStock milestones** supports continuation; coordinate with active
builders and do not open duplicate work.

**Reader byte-integrity follow-up (10 October 2026):** Browser publication and
research reads preserve actual UTF-8 response bytes for digest checks. BOM-prefixed
JSON and malformed UTF-8 are refused. Boot and refresh share the bounded byte
reader; failed refreshes preserve the current record and private inputs. Native
buffering begins only after a cloned stream reaches EOF within the 32 MiB cap;
the native byte count must match, and refusals cancel both tee branches together.
This avoids a reproduced Chromium 141 streaming-completion diagnostic without
sleeps or network-error exemptions. Canonical publications, immutable fixtures,
historical evidence and strategy rules are unchanged. Direct string callers of
the observations API keep their explicit UTF-8 serialization compatibility.
Local evidence: 119 reader and 991 compatibility browser checks, 238 focused
Python checks, 137 DOM/store continuity assertions and four chart-geometry
controls pass. Seven isolated hash/decoder/cap/native-order/refusal mutations fail their
named controls; an unrelated timeout mutation passes all 119 reader checks.
An independent 200-read transport reproduction has zero failed requests and
preserves the exact source digest. Phone and desktop captures were inspected.
The sidecar timeout remains 15 seconds. The subsequent publication-recovery
change also bounds startup and manual refresh to 15 seconds across headers and
the complete body; failed startup clears partial state, exposes Retry and keeps
private reports accessible. Its dated checkpoint below supersedes the original
byte-integrity checkpoint's unbounded-startup limitation. Exact-head hosted
checks and actual public acceptance are recorded per release below.

**Released review-budget policy (10 October 2026):** `src/review_selection.py`
archives `account_feasible_first_research_v1`. The evening run selects feasible
private mechanical previews first, retaining the twelve-read ceiling and existing
rank. At most two spare A+/A reads retain research (ranked plus deterministic
session/ticker rotation); zero feasible names does not consume twelve reads.
Per-row purposes/blockers and reconciled run counts are provenance-bound and
replayed with the production planner and archived event registry. This changes
selection and rules identity, not final trade guards or historical records.
Method explains the recorded pre-review fit, opportunity/research split and
feasible names left unreviewed only for a reconciled, supported receipt.
The existing conservative model-plan reservation policy still applies across
rules identities. Actual production run `38034610157` requested and accepted
two research reviews from 479 discovered reaction candidates, with zero
pre-review feasible candidates and no final tickets. Ten reads were unused;
this is not a controlled cost-savings or trading-performance measurement.
The dated PR #121 receipt below retains source replay and public evidence.

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
- **The interpreter is part of the environment.** Historical Linux sandbox
  measurements used Python 3.11 and pandas 3.0.5; CI runs 3.12. Record the actual
  runtime with each checkpoint (the Windows correction below uses 3.12.14).
  A generated artifact is only as
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
→ session state from the bars → the stale tolerance (`run.input_tolerance`)
and the previous publication's stale stocks read again from this run's frames
(`run.stale_followup`, `src/followup.py`) → breadth → scan and checklist →
charts and Claude (down-only; `run.reads` by cause) → plans and the cash
budget → the record (`picks.json`, open plans, scorecard) → `report.build()`
and validate → email. Exit codes 0/1/2/3; seven problem words; `run.status`
closed on a closed night. `run.status` ok beside a degraded acceptance means
exactly one thing: the only gap was a stale tail the record's own archived
tolerance allows, named in full.
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

The suite now collects 3607 tests, the chart check remains separate, and the page smoke walks twelve fixtures. Historical measurement: 1107 tests, the chart check, and the page smoke
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
with `--shots`; the suites that visit Method 1075/1075; the full smoke
7637/7637 with `--shots`. **Seven mutants,
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

## Checkpoint, 19 Sep 2026 — native Windows evidence publication

**Reconciled scope.** Base `a4cfa62cb0ba7530f859e28e4ebd9b3d0a116665`,
tree `eec3e0fcf6f71cfb6abdb7e5e58d3667769dadcd`; branch
`fix/windows-evidence-publication`. Remote main matched guidance, #81 and #82
were merged, and there were zero open PRs or existing Windows-fix branches.
The local retention branch was clean; no unpublished Windows fix was found.
This is the publication correction, not a second retention or animation PR.
Final head and normal exact-head CI results belong in its PR, not old #81.

**FAIL before / PASS after, newly executed on native Windows.** Windows 11
build 26200, AMD64, Python 3.12.14; pytest 9.1.1, pandas 3.0.6, NumPy 2.5.3,
alpaca-py 0.44.0, exchange_calendars 4.13.2, matplotlib 3.11.2, anthropic 1.7.0.
The unchanged base's actionable-publication test fails at publish with WinError
32, while the unrelated retained-regime/reader control passes. An isolated base
archive with the new tests has ten lifecycle/real-object failures and that same
green control. The strengthened candidate test also fails on the unchanged
source, then passes with the real corrected writer. This is native execution,
not a Linux simulation or a historical report.

**Correction.** Only `provenance.write_objects()` changes production behavior:
write/flush, exit the temporary-file context, then replace. Cleanup runs after
closure and a cleanup OSError cannot replace the original failure. Every failure
still propagates; required evidence must finish before either public record is
installed. Failed cleanup may leave an unreferenced staging file; earlier
successful objects may remain. Content addresses, validation, canonicalization,
JSON/gzip settings, bounds and ordinary public-pair rollback are unchanged.
The input-retention candidate test now requires exit zero and real data/picks on
every platform. Twenty added cases cover JSON/gzip and binary objects, repeat
writes, corruption, closed handles, write/flush/replace/creation failures,
secondary cleanup failures, installation ordering, rollback and pipeline refusal.

**PASS:** 361 focused provenance/publication/input/pipeline/retention/walkthrough
tests; full `python -m pytest tests/ -q`: 1,398 passed in 87.79 seconds. The same
runtime, frozen clocks and provider/model doubles produce identical complete
prepared records, picks and four source objects before/after, including plans,
grades, coverage, receipts and rules. The snapshot comparison retains both
diagnostics-enabled/disabled runs. No live external boundary was used.

**FAIL, bounded platform limitation:** native `tools/make_fixture.py --check`
now reaches comparison but finds 24 gzip objects whose sole differing byte is
the OS header (offset 9: committed Linux 3, native Windows 10). **PASS:** a
separate executed content audit finds all 12 JSON fixtures equal, the binary
object identical, and every gzip's expanded bytes and all other compressed
bytes identical. This does not relabel the strict check PASS. Compression and
fixtures were not changed; the unchanged Linux exact-byte CI gate is required.

**KEEP** #73–#82, the eleven-step animation and its rule/example tests, degraded
coverage and unmeasured stale inputs. Design manifest v2.13.0 at
`14a752dd0269bd6ebbb7080eb0d9e1922cd1ef2c`: all 22 committed hashes match,
zero repository drift (the Windows checkout applies ordinary Git CRLF conversion
to text files). Production/history/evidence, fixtures, strategy, transport and
workflows have no diff. README and provenance/input docs describe the correction;
`.env.example` was reviewed and remains accurate without changes.
**FIX NOW** this handle lifecycle only. **DEFER** platform-independent gzip
container bytes and #81 production artifact verification (**NOT RUN**; existing
authorized evening execution only). **OMIT** live scanner/provider/model calls,
dispatches, production publication, settings changes, sibling work and merge.
Guidance independently reviews the scoped PR and retains merge authority.

## Checkpoint, 22 Sep 2026 — bounded acquisition-corporation classification

**Revision and authority.** Exact base:
`49e2724c94b60963d914d55a2bf98598ac6507ad`; branch:
`fix/blank-check-universe-classification`; implementation/tested source head:
`4b4639c406494736ea437b0ad8e48990febbc101`. The connected GitHub app
published the identical tested tree after the CLI lacked write credentials.
This documentation-only child adds the checkpoint. The final review head including this note, and its
completed required check runs, are pinned in the PR description rather than
claimed as a self-referential commit hash. Main matched the supplied base,
with zero open PRs before work. Astra owns implementation and one PR only;
guidance retains independent review and merge. The selected effort setting
was preserved; no value or quota was guessed.

**Exact changed files:** `src/universe.py`, `tests/test_universe.py`,
`tests/test_inputs.py`, `tools/check_blank_check_universe.py`,
`docs/input-truthfulness/2026-09-22-blank-check-classification.md`,
`README.md`, and `CLAUDE.md`. All other tracked files match the base.
README is accurate for the new rule; `.env.example` was reviewed and needs
no change because configuration is unchanged.

**Correction.** The classifier depended too heavily on Nasdaq's exact
`blank checks` industry label. It now also recognizes bounded Acquisition
Corp[.]/Corporation legal endings, an optional retained Roman-number suffix,
and a terminal common/ordinary-share label. The existing `blank check company`
family records exclusions before fetch. Generic acquisition/capital/holdings/
investment words do not exclude companies. Seed overrides and unknown-industry
precedence remain unchanged. No manual rules_version change: the existing
membership identity automatically changes its digest when the population changes.

**FAIL before / PASS after.** HEAD was the exact base and the production-source
diff was empty when the new regression produced 11 expected failures and
108 passes. Retained BKHA/EGHA/HCMA rows were admitted and reached mocked bar
requests. The identical selection passes all 119 checks after correction.
Operating Class A shares, generic-name controls, exact blank-check industry,
seed behavior, foreign/biotech warnings and missing-input behavior stay green.
The new ledger case conserves duplicates, security exclusions, seed overrides/
additions and capacity. Disabling only the old industry rule in memory leaves
the three name regressions green and fails its two industry controls.

**Executed verification.** Linux Python 3.12.14, pytest 9.1.1, pandas 3.0.6,
NumPy 2.5.3, exchange_calendars 4.13.2: 229 focused universe/diagnostic/input/
pipeline tests passed; full normal pytest: 1,423 passed; all 12 fixtures remain
current; diff whitespace check passed. Initial SDK tests needed sandbox-only
`socksio`, then passed without repository dependency changes. Browser and secret
gates remain required on the final PR head; their outcomes belong in that PR.

**Sweep and limits.** All 13 retained directory snapshots produce the same
16 new exclusions: AAC, BKHA, EGHA, EMIS, EVAC, HCAC, HCMA, IPEX, KTWO, MCGA,
MTAL, PAAC, SIMA, SOUL, VACI, WSTN. Every name was inspected and is tabulated
in the dated report. No ambiguous operating name, seed loss, other membership
loss or accounting fault remains. Latest comparison: 4,796 → 4,780; the
September 18 eight-row sample loses only BKHA/EGHA/HCMA. This establishes no
historical missing-bar cause. September 18/21 publications remain unchanged;
remaining stale/unavailable inputs stay unknown and unmeasured, with truthful
degraded coverage. No live provider/model/scan/publication action occurred.

**KEEP** historical records, input accounting, strategy, warnings and existing
website/design behavior. **FIX NOW** this narrow classifier hole only.
**DEFER** provider causes and broader security-master work. **OMIT** stale-bar
suppression, generic shell heuristics, live calls, directory refresh, workflow
dispatch/rerun, email, publication, settings/schedule changes and merge.
Exact next action: guidance independently reviews the focused PR and its
completed exact-head checks; Astra stops without merging or another milestone.

## Checkpoint, 22 Sep 2026 — retained quality and A+ evidence

Base/main verified `09acc0429b5a85e0ac74b8eadda3af564134744c` (merged #84),
unchanged again before PR preparation. Branch `reliability/retained-quality-ledger`.
Astra preserved the selected effort setting without guessing value/quota; owns
implementation and one unmerged PR. Guidance owns independent review and merge.
The final review head and exact-head CI results are pinned in the PR description.

**Audit:** `docs/input-truthfulness/2026-09-22-retained-quality-audit.md`, derived
JSON inventory, compressed candidate matrix and verification results. Full-history
Git inventory finds 13 legacy and nine v2 real snapshots. Nine v2 records on seven
sessions (Sep 11–21) contain 3,547 reaction rows: zero final A+, 14 mechanical A+
assessments (nine date/ticker pairs), all lowered by the historical reader.
Latest-per-session: 2,766 rows, nine mechanical and zero final A+. Legacy's 27
scored rows are skip under their own bands; its literal A+ labels are empty bands.
Source hierarchy and DERIVED thresholds remain explicit; no strategy is retuned.

**PASS retained/offline:** all nine original v2 publication/grade contracts;
five full-source replays (1,871 reaction/anticipation candidates); two original
September 21 input artifacts with complete identical 20-name stale memberships,
checksums, ledger/directory/run binding. Four older v2 full-frame replays and
cross-day complete exception membership are BLOCKED. Modern input readiness is
99.50–99.60%, repeatedly degraded (five publications/four sessions), not equivalent
to workflow failure. No post-#84 real run exists; 4,763/4,780 ready after removing
16 names is only the retained-directory counterfactual. Provider causes and
systematic operating-stock missingness remain BLOCKED. All nine original v2 picks
files are empty: no settled-plan or grade-stratified performance sample exists.

**Verified defect / single correction:** nights stores only session/status/time,
20 sessions and same-session replacement; recovery expires after 21 days and
omits per-plan scorecard observations. `quality_ledger.py` captures immutable
versioned gzip snapshots after final publication, using the publication's
original rules/basis/denominators, full exception membership, mechanical checks,
reader/final grade/plan/ticket gates and computed model scorecard rows. No raw
bars, personal execution or historical backfill. Existing git-add-docs persistence
includes it; no workflow or settings change. Null remains UNKNOWN. Entries are
bounded (8 MiB expanded each; 128 MiB compressed archive; 4,096 entries), never
evicted/regraded/overwritten. Failed capture is explicit in RunReport/log/output
and cannot change publication/decisions/external calls/exit codes. Interrupted or
unpublished runs are not asserted complete by this publication ledger.

**FAIL before / PASS after:** the final regression on extracted untouched base
fails for absent ledger evidence; the actionable A+ ticket control passes.
The fixed suite verifies survival across recovery expiry and same-session revisions,
complete exception membership beyond public samples, original grades on outcome
rows, immutable/bounded writes, failure paths, exact public/source bytes and
external-call/exit/status controls. Full normal offline pytest: 1,435 passed
(latest local results and exact-head checks are pinned in the PR); all 12 fixtures current. Initial documentation/output-contract
failures were corrected without weakening tests. Dependencies came from existing
cached packages after automatic review rejected an install attempt; no registry
workaround or new live boundary was used. New local browser work NOT RUN because
UI is unchanged; exact-head CI includes the normal page and Secret Scan gates.

README and input-truthfulness docs describe retention; `.env.example` reviewed,
no configuration changes. Historical data/picks/history/evidence, strategy,
fixtures, shared design, mobile/chart/Focus code and siblings have no changes.
KEEP truthful unknown/degraded accounting and all accepted behavior. FIX NOW
only publication-time evidence retention. DEFER provider investigation, retuning,
profitability and human usability. OMIT gallery, personal execution/portfolio,
new provider/model calls, dispatch/rerun, email, manual publication and merge.

## Checkpoint, 22 Sep 2026 — reader downgrade source fidelity (#86)

Exact base/main: `2d790e1f95a8df746d9e7cb7870d16444462725d`, merge of #85.
Main and zero open SpicyStock PRs were verified before branching; main was
rechecked unchanged. Exact reviewed implementation head:
`4d3dcec413bb8f7b01669dae355d43d3eae92f5e`, tree
`674e7e4680a94ec12468ea7ce4fcdd2dc1b34e1f`. This checkpoint-only descendant
records the handoff; its exact submitted head and automatic CI results are
pinned in PR #86. Branch `fix/reader-source-authority`. Astra implemented;
Guidance owns independent review and normal clean merge. The selected effort
was preserved without guessing its value or quota.

The dated reader audit reconstructs all **108 completed real v2 reads**, twelve
per publication across nine retained September 11–21 revisions, including
individual evidence records for all **14 mechanical A+ assessments**. Repeated
publications remain distinct. All were red, without plans/tickets. No outcomes
were used. The explicit 395-claim inventory has 209 SUPPORTED, 54 PARTIALLY
SUPPORTED, six UNSUPPORTED, 71 CONTRADICTED and 55 UNVERIFIABLE claims; these are
claim labels, not an overall reader score. Sixty-one responses contain an
unsupported/contradicted claim, often alongside a supported independent concern.
Seven lack a fully supported adverse claim in the inventory; missing charts or
subjective shape uncertainty prevent declaring every such downgrade wrong.

Historically, the first four prompts imposed universal 4% despite their own
independent Dollar scan. #68 corrected that wording/tripwire; #72 corrected
primary attribution; #73 added replay evidence. False measurements and no-vote
notes persisted afterward. Current main's guard catches four of the fourteen
A+ historical replies, but its score parser did not require a source-grounded
finding. That current authority defect is reproduced, not inferred from the
absence of final A+. The supplied field guide supports interpretation without
superseding the repository's dated primary/source hierarchy.

Reader authority v1 permits named existing qualitative concepts and actual
FAIL/PARTIAL checks, requiring exact factual citations and charts for visual
findings. Equivalent JSON numeric notation remains valid; unknowns cannot be
negative evidence. Invalid authority rejects the whole result without retry
into existing degraded mechanical fallback. Findings/version are retained and
verified. Subjective visual truth remains unverified. The reader stays down-only;
mechanical scoring and thresholds are unchanged. Prompt contradictions about a
numerical extension vote and universally drawn plan lines are corrected.

**PASS:** 1,449 offline pytest tests on Python 3.12.14; eleven fixture variants;
127 continuity, 182 chart and 7,637 page checks with desktop/mobile screenshots
inspected. **FAIL before / PASS after:** eleven intended failures on untouched
base, three unaffected controls, all fourteen passing after correction, including
retained WBD/PTGX inputs. **PASS:** all 3,547 historical mechanical/reader
reconciliations and 1,871 later source replays. **BLOCKED:** complete pre-Sep-16
frames/charts were not retained. **PASS:** implementation-head Secret Scan.
**NOT RUN:** final descendant CI at checkpoint writing; exact-head results belong
in PR #86 before handoff. Fresh model/provider execution, scans, dispatch/rerun,
directory refresh, email and publication are **NOT RUN**.

KEEP deterministic evidence, unknowns, history, #85 ledger, mechanical rules,
website/mobile/chart/Focus and shared design. FIX NOW only reader/source authority.
DEFER consolidation source fidelity, provider investigation, live coverage,
profitability and retuning. OMIT outcomes, historical regrading, A+ manufacturing,
ticker exceptions, UI additions, brokerage and siblings. Exact next action:
finish automatic checks on PR #86's submitted head, then stop for Guidance's
independent review; do not merge or start another milestone.

## Checkpoint, 22 Sep 2026 — consolidation source fidelity

Exact base/main: `6533e616bd14ebfebeeccb4c9b1b0d463b47dbb4`, tree
`e711c3bd8bb7b11dda69b61e93208a455dc5584c`, the reviewed #86 merge. Main and
zero open PRs were verified before branching and rechecked unchanged before
submission. Branch `audit/consolidation-source-fidelity`. Exact tested
implementation head: `014f2132c3b65cb39f374af576b8a3e8524b49f3`, tree
`4dd6b120c8c8991dabab0b7523fcd87c131c170e`. This checkpoint-only descendant's
exact submitted head and automatic checks are pinned in the one focused PR.
Astra owns implementation; Guidance owns independent review and normal clean
merge. The selected effort setting was preserved without guessing its value.

The dated consolidation audit reconstructs all 3,547 real reaction assessments
across nine retained publications, with a separate 2,766-row latest-per-session
view, 35 reproducibly selected source-frame cases, overlap matrices, exact
histograms and explicitly offline counterfactuals. All 1,846 available reaction
frames replay exactly; original-source provenance verifies 1,871 later rows
including anticipation. Earlier 1,701 complete frames are unavailable; their
stored checks reconcile, not raw bars. No subsequent returns were used.

Source hierarchy distinguishes directly inspected Bonde text from later
variants, community/secondary interpretations, DERIVED policy and retained
observations. The supplied field guide is secondary. Selected reaction length
3–20 is primary 2014; 3–10 is 2015 anticipation; 5–40 is a distinct 2018 reaction
variant with zero breakdowns. Maximum one breakdown is later 2020. Base/leg
segmentation, partial grades, exact giveback/tightness, volume means and the C
A+ conjunction are DERIVED. No inspected primary exact third/quarter giveback
or tightness ratio was verified. Unavailable X text and unreviewed video audio
remain explicit limits.

Giveback exceeds 0.34 in 2,877 rows, overlapping long bases and breakdowns.
One-session anchor stress changes C in 158/1,846 frames; a defined recent-local-
peak counterfactual changes 148. These demonstrate sensitivity, not erroneous
base prevalence. CTAS has a plausible shorter pause inside its 33-session box;
IDT's recent higher high produces two sessions. No source-labelled human
boundary benchmark establishes a replacement. No numerical correction is
warranted by this evidence.

The verified current defect is attribution: the reader instruction presented
DERIVED giveback as Bonde's rule and lower volume as ordinary C, although it
only gates C A+. Corrected prompt, source comments and dated source contract
separate those facts and historical scopes. Executable quality AST, constants,
rules digest and #86 authority remain unchanged. Before/after C stays
304 PASS / 67 PARTIAL / 3,176 FAIL / zero UNMEASURED, with 32 C A+ flags.
Mechanical grades stay A+ 14 / A 415 / B 860 / C 645 / skip 1,613; no changed
candidates. Historical publications are untouched.

**FAIL before / PASS after:** attribution regression, with eleven unaffected
arithmetic controls. **PASS:** 332 focused tests; 1,451 full pytest tests on
Python 3.12.14; all 12 regenerated fixture files current; retained replays and
unchanged historical bytes. Fixture differences are prompt-derived identities.
README and `.env.example` reviewed. **BLOCKED:** earlier raw frames and a human
source-labelled segmentation benchmark. **NOT RUN:** local UI rerun, fresh
provider/model calls, live scan, refresh, email, manual publication, dispatch
or rerun. Exact-head CI/Secret Scan are **NOT RUN** at checkpoint writing;
their automatic results must be pinned in the PR before handoff.

KEEP #86 authority, #85 ledger, truthful unknowns, history, mechanical rules,
website/mobile/chart/Focus and shared design. FIX NOW attribution only. DEFER
provider/live coverage, labelled segmentation research, profitability and
broader retuning. OMIT A+ manufacturing, future-return tuning, historical
regrading, ticker exceptions, UI/portfolio/brokerage and siblings. Exact next
action: finish automatic checks on the submitted PR head, stop for Guidance's
independent review, and do not merge or start another strategy component.

## Checkpoint, 23 Sep 2026 — production reader contract and retained failures

Verified starting main: `897f507aa2a85f4493c7cc742661d06a1a8ba6f8`, the #87
merge over the real September 22 publication. Main was rechecked unchanged and
zero open PRs were verified before submission. Branch:
`fix/reader-production-compatibility`. Astra owns this implementation and one
unmerged PR; Guidance owns independent review and merge. The selected effort
setting was preserved without guessing its value or quota. The exact submitted
head and completed automatic check links belong in the PR description.

**PASS — real evidence and reconstruction.** Run `35802203679`, attempt 1,
executed `6533e616bd14ebfebeeccb4c9b1b0d463b47dbb4` and published
`e2dee988ad5d36876b7c73090502720e995c65f4`. Both original artifact ZIP hashes
match GitHub metadata. All twelve prepared metrics/system/chart/request identities
reconstruct exactly using the original implementation. IOSP, KYMR, HSIC, IDCC,
CLMB, CRVL, MEDP, NEM, PYPD, WPM, AG and AIT each had one authority rejection
and retained their mechanical grade through labelled fallback. The real input
ledger reconciles 4,763/4,778 ready stocks, 15 stale and 513 quality successes.

**BLOCKED — response-level closeout.** The grader discarded all twelve raw
responses, parsed scores and findings. The ledger faithfully retained the
incomplete attempts supplied to it. The shared field-set/type error cannot
distinguish missing keys, extra keys or a non-object finding, or establish
semantic authority. Neither artifact, history, evidence objects nor job logs
recover these replies. The dated report and twelve-candidate inventory explicitly
preserve unknowns. No real response is claimed newly accepted or semantically
rejected after correction; historical replay and full milestone acceptance remain
blocked. New model execution would not recover missing historical text.

**Correction.** One nested findings schema now supplies the default-model text
instruction, structured-output schema and validator's closed key sets. The
rulebook names the exact shape. Returned text is captured before parsing and
authority checking, with digest, byte count, stop reason and message ID; a
64 KiB bound reports oversize omission explicitly. Existing publication sealing
and ledger copying preserve rejected attempts automatically. No semantic
allowlist, normalization, retry, budget, mechanical score, strategy threshold,
plan rule or #87 source attribution changes. Unknowns and contradictions remain
inadmissible; visual findings need charts; final grades remain down-only.

**FAIL before / PASS after:** untouched starting source produces eleven intended
failures and three unaffected passes; the same corrected selection passes all
fourteen. Independent in-memory isolation checks pass. **PASS:** 216 focused
tests, full normal pytest 1,466 tests, all twelve fixtures current, 127 continuity,
182 chart and 7,637 page checks; desktop/mobile screenshots inspected.
Original-code verification passes all 518 September 22 receipts. All 6,133
Git-retained artifact files are byte-identical; all 46 synthetic candidate
decisions/plans are unchanged. Runtime is Linux Python 3.12.14. **NOT RUN at
checkpoint creation:** exact-head CI/Secret Scan; their final results must be
pinned in the PR before handoff.

README, provenance/input docs and the environment template were reviewed.
**KEEP** #84–#87, ledger, historical records and truthful degraded fallback.
**FIX NOW** the explicit contract and proven response-evidence loss.
**DEFER** historical semantic closeout, provider causes, labelled C segmentation
and profitability. **OMIT** authority weakening, invented replies, regrading,
tuning, UI/design/sibling changes, fresh model/provider/scan/publication actions,
dispatch/rerun, refresh, email and merge. Stop with one focused PR for Guidance;
do not represent the unavailable historical-response gate as passed.

## Checkpoint, 24 Sep 2026 — fallback risk attribution

Starting main: `9357a2791b8440af4b397dec57dee94a14551a0b`, the Guidance
merge of #88; unchanged when fetched again before submission. Zero open PRs
were verified before branching. Branch: `fix/fallback-risk-attribution`.
Astra owns implementation and one unmerged PR; Guidance owns independent
review and the normal clean merge. The selected effort setting was preserved.
Exact submitted head and completed full-browser/CI results belong in the PR.

**Defect and correction.** HSIC's real September 22 fallback had no accepted
reader risk or plan, but detail/comparison substituted the raw `biotech` flag
as "Biotech." Warning chips also used that unqualified interpretation.
The existing classifier flags every Health Care sector row. Its retained
directory identifies HSIC as Health Care / Medical Specialities and KYMR as
Health Care / Biotechnology: Biological Products (No Diagnostic Substances).
Neither directory row is included in the candidate publication. Presentation
now separates stock-specific risk from recorded screening warnings, explicitly
states the unavailable precise basis, and never guesses from ticker/name or a
newer directory. Accepted reader commentary retains its unverified attribution;
plan risk is labelled plan-derived; neither available means explicitly
unavailable. The same functions serve burst/anticipation detail and comparison.
Qualified warning chips, raw flags in provenance and walkthrough language share
that interpretation. Minimal local CSS keeps the warning hierarchy and both
comparison columns readable on phones; shared design-system files are untouched.

**FAIL before / PASS after.** The final 338-check browser regression on an
isolated checkout of untouched starting main produces 123 failures and 215
passing controls. Corrected presentation passes all 338. An unrelated heading
mutation still passes all 338. Real unmodified HSIC/KYMR/IOSP excerpts, accepted
reader-over-plan, plan stop/hazard/note, rejected text, no-flag and legacy
unknown-basis controls exercise detail and comparison. Tests run in the normal
page gate, not an optional replacement. Desktop 1440 and phone 390/320, both
themes, wrapping, native disclosure keyboard/touch and comparison focus/selection
are exercised; screenshots inspected. A separate browser pass uses all 513
bursts in the exact full retained publication and verifies all three journeys
at 1440/390, with no plan, order or copy control created.

**PASS:** 271 directly affected Python tests; full normal suite 1,466; twelve
fixtures current; 127 continuity and 182 chart checks. Runtime: Linux Python
3.12.14, pandas 2.2.3, NumPy 2.3.5; Node 24.19.0, Playwright 1.56.1.
Original publication source verifies 513 mechanical assessments and all 518
receipts. All 6,190 protected source/data/history/evidence/ledger/design/workflow
files match the base. Publication SHA-256 remains
`507127d7a6e07f2d1120290c96cd717e1ef72529be8053218d317bb9b9ee3c36`.
HSIC remains A+ 9.0, C partial, RE/VOL failed, reader fallback, regime_gate,
null plan and no ticket. IOSP/KYMR decisions and all evidence identities remain.

README and `.env.example` reviewed; no configuration change. No strategy,
discovery, membership, raw flag, grading, reader authority, gate, entry, stop,
sizing, plan/ticket, model-outcome or provider behavior changed. No new scan,
provider/model call, workflow dispatch, schedule, secret, publication, email,
brokerage action or sibling change. Next action: Guidance independently reviews
the focused PR and its final-head evidence. Astra stops without merging or
starting another milestone.

## Checkpoint, 24 Sep 2026 — reader coverage and burst actionability

Starting main: `456edb836cc42c908c50330b723dbfd97be5d506` (Guidance #89),
re-resolved with zero open PRs before branch `fix/reader-coverage-actionability`.
The selected effort setting was preserved. Astra implements and submits one
unmerged PR; Guidance independently reviews and owns the clean merge.

The full September 23 publication is pinned byte-for-byte in the retained
regression fixture. On untouched base, synthetic GREEN gives all six budget
exclusions eligible plans; VEEV fallback also gets a plan. VEEV/NDSN/OPY/RRR
become tickets and STE/TTE/WLY hit the slot cap. The final portable regression
produces two intended failures and four passing controls before the correction.

New final burst planning requires an accepted reader result as well as existing
grade/veto/regime/price/sizing/budget gates. Explicit reader coverage is sealed
in the candidate receipt and archived with a prospective policy identifier.
Fallback and budget exclusions keep mechanical grades for research. A private
preview preserves the stops supplied in reader charts, and receipt verification
independently rejects publishing such a preview without accepted coverage.
GREEN A+/A, YELLOW A+ only and RED none remain unchanged. Existing anticipation
watchlists keep their measured, ungraded policy. Historical decisions are not
recomputed. The website names missing review without calling it setup failure.

47 coverage regressions accompany the normal Python suite (1,513 collected),
regenerated synthetic fixtures, full page/continuity/chart gates and inspected
phone/desktop renders. Final-head local/CI results belong in the PR. All 6,797
protected base files are byte-identical. Original-code replay passes September
22 (513 assessments, 518 receipts) and September 23 (282, 287). The 46 synthetic
candidate input/checklist/grade/reader projections are unchanged; only four
fallback plans disappear from the synthetic degraded fixture.

See `docs/input-truthfulness/2026-09-24-reader-coverage.md` for the policy table,
reproduction and SHA-256 values. README and `.env.example` reviewed; no setting
change. No new provider/model/production call, dispatch, rerun, publication,
email, threshold/breadth/universe/account/history change or sibling modification.
Stop at one reviewable PR without merging or beginning reader-quality tuning.

## Checkpoint, 25 Sep 2026 — chart-table keyboard access

Starting main: `6822dddd14d0a541083e7caaecca9c945b451af2`, re-resolved
before branching and again before submission; zero open PRs at both reads.
No newer publication was displaced. Branch: `fix/chart-table-keyboard-access`.
Implementation/test head: `a430e778c64da5de1ce75aff7a1cb4b7be6b5ad1`. The following handoff commits
change only these notes; the PR records the exact submitted head and CI run.
Selected model/effort settings were not changed. Astra implements and stops
at one unmerged PR; Guidance owns independent review and the normal clean merge.

**Reproduced before the repair.** Untouched base, full September 24 publication,
`#/explore/bursts/NIC`, Chromium 141.0.7390.37 through Playwright 1.56.1,
Windows, 390 × 844, both themes: click the table disclosure, Tab into its
scroller, press Right five times. Each key was default-prevented; scrollLeft
stayed zero, volume remained beyond the scroller, and chart inspection opened.
This environment measured clientWidth 344 and scrollWidth 474; those are evidence,
not acceptance constants. The publication SHA-256 remains
`97da76d4f0eae671a5168760b79852c2eb6c4539bef3a144df6ef6bfe20c93f4`.
Run `36077970591`, attempt 1; execution revision
`470c358c06bc9c997184d829c63845c4db0dc4f5`. No live production page or physical
device was tested; a local server served retained sources/data with fonts and
external requests blocked for this focused regression.

**Repair.** `chart()` handles inspection shortcuts only when the event target
is its host. `buildTwin()` gives the native table wrapper an explicit tab stop,
region role and ticker-specific accessible name. Existing design-system focus
tokens remain in force. App source blob changes from
`16ac43f6b8e9f0a1b8fedcc3d0d80ea9765e1344` to
`4990146201710b51f8ca6dd34909fef8b3fd52e3`; no other application file changes.

**Regression and rendered evidence.** `tools/chart_check.mjs` now includes
360 × 800, 390 × 844 and 1280 × 900 in both themes; `tools/page_smoke.mjs`
runs the shared `chart-keyboard` suite in its normal unfiltered gate. Tests use
native keyboard/wheel input, wait for scrolling to settle, and measure every
final-column cell inside the scroller clear of the sticky session column.
They cover return-left, explicit focus/name/native tables/visible outline,
unchanged crosshair/tooltip, host Left/Right/Home/End/Escape, disclosure
Enter/Space, Tab/Shift+Tab exit, pointer scrolling, surrounding document or
desktop pane scroll, geometry and selected route. A descendant input preserves
Home/End caret behavior. Disposable synthetic contexts exercise both comparison
charts (including the phone A/B switch) and saved originals, native Escape
dismissal/focus return, peer-chart independence and unchanged saved snapshots.
The chart-help popover's existing blur delay is allowed to settle before Escape.

The exact retained publication and inspected before/after screenshots are in
`tests/fixtures/chart-keyboard/`. Its evidence manifest records source blobs,
browser, viewport, route, session, hashes and mutation results. The 390 viewport
captures show the final column; tall host crops document inspection state.
Normal CI `page-shots` also retains narrow/desktop and consumer screenshots.

**Executed checks (Windows Python 3.12.14, pandas 3.0.6, NumPy 2.5.3;
Node 24.19.0, Playwright 1.56.1 / Chromium 141.0.7390.37):**

- PASS — `python -m pytest tests/ -q`: 1,513 passed. `MPLBACKEND=Agg` and
  a writable `MPLCONFIGDIR` were used after the initial chart-only attempt
  exposed this runtime's missing Tk resources (9 environment failures).
- PASS — `node tools/continuity_check.mjs`: 127 offline DOM/store checks.
- PASS — `node tools/chart_check.mjs --shots <dir>`: 378/378.
- PASS — `node tools/page_smoke.mjs --only chart-keyboard --shots <dir>`:
  259/259, both themes and all three NIC viewports; comparison/saved at 390/1280.
- FAIL (Windows clipboard only) — `node tools/page_smoke.mjs --shots <dir>`:
  8,402/8,409; seven unchanged clipboard assertions receive CRLF instead of LF.
  The same behavior was reproduced on untouched base. The final focused suite
  above was rerun after the help-delay test correction.
- FAIL (Windows container bytes) — `python tools/make_fixture.py --check`:
  24 retained gzip objects differ only at header byte 9 (Windows OS 10 versus
  Unix OS 3); all decompressed payloads, lengths and all other bytes match.
  All generated page JSON fixtures match. No fixture was regenerated.
- PASS — isolated negative controls via `SCSTOCK_CHART=<source copy> node
  tools/chart_check.mjs --shots <dir>`: untouched base gives 39 intended failures (313/352);
  removing only the target guard gives 37 intended failures (341/378);
  removing only tabindex gives 8 failures (344/352). Existing chart-host and
  geometry controls stay green with the guard removed. Disabling unrelated
  pointermove inspection gives only six existing hover failures (372/378),
  while every keyboard assertion passes. No live working-tree mutation.
- PASS — `git diff --check` and protected-file review; 7,828 prior tracked
  files are unchanged, including publication/history/evidence, all Python
  application code, workflows, configuration and the complete design-system
  2.13.0 snapshot/manifest at `14a752dd0269bd6ebbb7080eb0d9e1922cd1ef2c`.
- CI results on the submitted head are recorded in the PR; normal assertions
  and required checks remain unchanged.
- NOT RUN — physical-device, live-page and assistive-technology testing.

README was reviewed and now documents chart/table key ownership; `.env.example`
was reviewed and remains accurate without changes. No strategy, reader authority,
coverage policy, grading, plans/tickets, sizing, timing, measurements, source data,
historical publication, ledger or outcome changes. No provider/model/production
call, new scan, workflow dispatch/rerun, schedule, secret/settings change, manual
publication, external message, brokerage action or sibling edit. Test-pipeline
messages about reader failures came from the existing offline doubles.
Stop at the reviewable PR; no merge or next milestone is authorized here.

## Handoff — 2026-09-28: historical validation and usable decisions

Repository: `spicyChicken59/SpicyStock`; branch:
`fix/historical-validation-usable-plans`. Actual base was re-resolved repeatedly
as `8be007f68deaa417b85a512d2e16a37899d27011`; no competing open PR existed.
The one scoped release PR records the final remote head and CI status. Guidance
owns independent review and the clean merge. Do not merge, manually dispatch a
scan, or begin another campaign from this checkpoint. Direct git push lacked
credentials; the connected GitHub API publishes the identical tree. The POC was
frozen locally in `24615d6` before outcomes; its raw commit and the later remote
specification-tree commit are preserved in `spec-freeze.json`.

The review is `docs/input-truthfulness/2026-09-28-validation-review.md`, alongside
the frozen specification, selected operating contract and machine evidence.
Thirteen actual rebuild publications represent eleven unique sessions, not
thirteen trading days. All are RED; no accepted review finishes A/A+. All thirteen
original picks files are empty. Nine original-code/source replays agree; four
earlier complete source layers are unavailable. The 5,215 candidate traces show
joint market, grade/review, structural and sizing blockers. Removing only market
or reader gates still gives no tickets. Their joint ablation gives synthetic
counterfactual tickets, never historical orders. Alphabetical review ties and
unreviewed mechanically feasible candidates establish access starvation, not
hypothetical approval or an edge.

Verified prospective repairs send the shared schema for supported Sonnet 4.6,
include the measured leg/base in the exact reader image and date its context,
version request semantics, and remove asymmetric approval/rejection encouragement.
Model, review count, attempts, ceilings, authority and numeric strategy rules stay
unchanged. NIC/BIO/RVTY/MSFT remain rejected. Latest MSFT failed authority, not
JSON parsing. No live API success or acceptance improvement was measured.

The existing website now explains overlapping wait gates and incomplete inputs,
connects Method/Record to frozen CRL/IQV/MSFT development cases, and separates
later observations from original evidence. Reader-image links use retained image
hashes. Saving and outcome reveal preserve the original; no historical case
acquires live order action. Agent-operated Chromium checks cover 390×844,
320×844 and desktop, both themes, with 85 historical checks and screenshots.
The #91 harness now waits for actual chart layout before its unchanged exact
SVG/keyboard assertions; delayed-observer baseline and restored-defect controls
both detect the previous capture race. Physical-device and assistive-technology
checks remain NOT RUN. Final regression results belong to the review package.

KEEP existing authority, stop-constrained mathematics, source identities and the
unchanged design-system 2.13.0 snapshot. FIX NOW the demonstrated request, image,
wording and browser-test defects in this PR. DEFER point-in-time universe/security
identity, comparable volume adjudication, intraday execution and policy proposals.
OMIT profitability claims and approval inflation. Candidate-only next-close
observations are selected, dependent and inconclusive; zero settlements give no
expectancy. Real-data qualified-plan and executable-performance gates remain
BLOCKED. The latest September 25 record offers no ticket for Monday September 28.
After review/authorized merge, only the next existing normal run can supply new
prospective evidence; its health and any ticket remain unknown. Exact next action:
Guidance reviews the final base/head, evidence, publication effects and normal CI.

## PR #92 correction checkpoint — 28 Sep 2026

Continue only `fix/historical-validation-usable-plans`, PR #92. Guidance review
`5338408980` identified two explanation defects on
`2e4d0eca42d4df099069d4ca1d791402d58825d5`. Re-resolved base/main remains
`8be007f68deaa417b85a512d2e16a37899d27011`. Corrected implementation:
`c0e9d9b445a18782e39d5aa2f50b292ee08acca1`, tree
`5d0ae9f67a09f65e940abb76a6999abf508b34de`. The connected GitHub API preserves
that exact verified tree (local sealed metadata differed). This following handoff
commit changes documentation/evidence only; PR #92 records the exact submitted
head and its completed normal CI. No merge or next milestone is authorized.
Selected model/effort and every strategy/provider/account setting stay unchanged.

`evaluationExplanation()` reuses status/calendar/publication evidence: Monday
remains pending after its close buffer when Friday is still loaded. Future,
closed-buffer, pending, stale/missing/possibly failed, explicit failed-run,
newly loaded and insufficient-evidence cases are distinct; no cron or completion
promise was added. The clock updates the text in place even when availability
is unchanged, and refresh preserves the wait disclosure. `planningWaitReasons()`
distinguishes recorded skip, attempted failure, attempted unknown outcome,
ineligible/withheld output, recorded sizing/allocation and legacy unknowns.
Null alone establishes no stage. Independent blockers and all order controls
retain their existing authority.

PASS — 721 correction assertions and the original 85 historical assertions now
run in normal `page_smoke.mjs` through shared modules. They use the frozen
September 25 publication, whose raw SHA-256 is
`37255a5457472d47452ea326e6b6b84cec2d6bd1da07ab391e173daf73a62ce5`, plus the
existing September 24 fixture for real arrival. Holiday/session dates come from
archived XNYS evidence. Synthetic stage/date controls are explicitly identified.
FAIL — the exact reviewed application fails 276 of those 721 assertions; 445
controls pass. Restoring only the selector fails 186; restoring only the planning
explanation fails 84. PASS — the unrelated title control passes all 721. The
control runner never edits the working tree. No assertions were weakened.

PASS — Python 1,541 (JUnit confirmed), 12 fixtures current, 127 continuity and
378 chart checks. PASS — 390×844, 320×844, 1280×844 in both themes; inspected
pending/error/unknown/delayed screenshots and measured wrapping/geometry.
Existing #91 viewport/key ownership coverage remains in the normal gate.
FAIL — the first full-page attempt was 9,190/9,191 on an intermittent phone map
chooser assertion around screenshot capture; the reviewed application reproduces
93/94 with captures, while both pass 94/94 without them. Capture now follows the
unchanged native keyboard sequence and reopens the real control only for the
artifact: PASS 94/94. One restored-capture attempt passes, so its intermittency
is preserved in the report. Map application code and all assertions are unchanged.
The detail-free `plan_error` audit added six failing-before assertions and a
recorded-error fallback; corrected PASS is 721/721. A second full run overlapped
that late edit and is excluded from acceptance. Final sources were then sealed
and all isolated controls rerun unchanged. Final unfiltered exact-head normal
CI belongs in the PR before handoff.

PASS — 8,822 existing protected files match the reviewed Git blob identities;
all prior POC, source/evidence, publications/history/ledger, Python producer,
workflows and design-system bytes are unchanged. The POC was not regenerated.
README and `.env.example` were reviewed; no environment-template change.
The fresh test runtime initially lacked socksio (five offline SDK failures);
only the disposable test environment was corrected. Reports preserve initial
harness/environment failures rather than counting them as acceptance.

Commands and complete evidence:
`docs/input-truthfulness/2026-09-28-pr92-explanation-correction.md` and
`docs/input-truthfulness/2026-09-28-correction-evidence/`.
Use `node tools/page_smoke.mjs --shots <external-dir>` for the normal gate,
`node tools/wait_explanation_controls.mjs --output <external-dir>` for isolated
controls, plus continuity/chart checks, pytest and `make_fixture.py --check`.

BLOCKED — genuine historical qualified ticket, independent full-population data
and breadth truth, executable performance and trading edge. NOT RUN — live
reader improvement, future production health, physical devices/assistive tech,
manual production validation and merge. The website and original report keep
these limits; corrective CI does not complete the larger validation campaign.
No new provider/model/live scan, workflow dispatch/rerun, production publication,
schedule/secret/settings/feed/model/brokerage/upstream/sibling change occurred.
Astra stops with this same PR ready for independent Guidance re-review; Guidance
owns the normal protected merge after authorization.

## Historical input proof checkpoint — 28 Sep 2026

The next bounded milestone starts from re-resolved main
`0d702940814af05e9b8d2a4c887aee00939e46fc`, preserving the accepted PR #92 tree
`b67eef40bd1db94d865e9182d1d13a4e08789ef1`. Branch
`investigate/historical-input-breadth-proof` adds offline investigation tools,
synthetic regressions and dated evidence. Its one PR records the exact submitted
head and normal CI; Guidance owns independent review and the normal clean merge.
No production, strategy, model, account, website or workflow behavior changes.

PASS — both original publication hashes, artifact identities, complete intended
and readiness populations, aggregate algebra and every recorded regime predicate
reconcile. The retained ten-session ratios 0.94 / 0.89 independently force RED.
Independent reference and production agree on 8,830 available selected-source
stock/session comparisons. That selected evidence does not prove the missing
full-market observations. The complete original target-price exclusion masks
were not retained: final membership remains unknown for 4,332 / 4,290 ready
names, containing both included and excluded securities. Intended universes
are retained; the earlier blanket statement that they were unavailable was too
broad. All 31 stale securities / 38 dated occurrences are explicitly accounted
for without assigning unsupported causes.

BLOCKED — a complete later-retrieved basis and its RED verdict. Acquisition and
the access probe are NOT RUN: zero actual requests, zero new response bytes,
zero additional spend. Neither accessible runtime exposes the configured Alpaca
credential pair; current $0 entitlement, retention rights, approved private
storage and an authorized Guidance retrieval path are unestablished. No keys
were extracted and no production workflow was dispatched. The frozen manifest
contains the original 4,780-stock union plus SPY, deliberate mapping dates,
required prefixes, one small probe and 96 bounded chunks. The persistent ledger
enforces shared 400-request / 1-GiB ceilings across retries and restarts.

PASS — the dated CRL public-volume substitution adds the Burst route and one
up event, preserves Dollar admission, and changes mechanical A to A+ while the
conditioned aggregate still rounds to 0.94 / RED. IQV is the unchanged control.
Original final grades were B. Changed inputs cannot inherit old reader approval;
structural feasibility is diagnostic only. No production defect was demonstrated.
Controls deliberately break arithmetic and acquisition guards, with unaffected
controls retained. Initial environment, harness and documentation-count failures
remain disclosed in verification.json. PASS — the final sealed local Python
suite is 1,677/1,677 with no skips; 8,867 protected files match the baseline.
Normal Linux fixture/browser gates are recorded in the PR. Windows needs an external import
adapter for Unix-only resource telemetry; it supplies no fabricated measurement.
The Windows fixture check reports 24 differing gzip objects, left unchanged.

KEEP existing thresholds, accepted_required_v1, reader budgets, stop-constrained
plans, historical records and design-system 2.13.0. FIX NOW the bounded toolchain,
missing-mask accounting and reproducible retained-data investigation. DEFER secure
acquisition, full original-value proof, source-policy and trade-condition
adjudication, and new reader judgments. OMIT invented plans, provider blame,
performance claims, redesign and a second milestone. Reproduction commands and
the precise evidence boundary are in
`docs/input-truthfulness/2026-09-28-historical-input-proof.md`. Exact next action:
Guidance reviews this PR, then identifies an existing secret-capable runtime and
approved private evidence destination under documented $0 access and retention
rights before any historical acquisition. Tahir need not run commands or send keys.

## PR #93 lineage correction checkpoint — 28 Sep 2026

Continue PR #93 and `investigate/historical-input-breadth-proof` only. Guidance
review `5342729066` found incorrect cross-page duplicate references on reviewed
head `a9ed0ec3b64399e1f9d80ac3ce27d921c289f9b1`. Re-resolved base/main remains
`0d702940814af05e9b8d2a4c887aee00939e46fc`. The PR records the exact corrected
head and its completed normal CI. No newer publication or work was displaced.

FAIL — before editing the acquisition source, nine normal pytest regressions
ran the actual class with synthetic transport: six failed on a wrong raw-row
timestamp/value or out-of-range index; three controls passed. This extends the
review's method-level reproduction through raw retention, pagination and ledger
handling. PASS — the correction passes all nine. FAIL — restoring only the old
cumulative-index assignment in an isolated subprocess produces the same six
pointer failures, while all three unaffected controls pass. No test was weakened.

The `raw-page-symbol-row-v1` output contract contains raw-page SHA-256, zero-based
query page number, symbol, and zero-based index within that page's `bars[symbol]`
array. Both previous/discarded and selected references resolve to exact retained
timestamps and OHLCV values, and agree with the unchanged normalizer. Coverage
includes two/three pages, duplicate rows within a later page, multiple symbols,
one-row later pages, repeated replacements, and same-page/no-duplicate controls.
Raw bytes/hashes/order and stable-last-arrival selection remain intact.

PASS — cached resume reproduces the complete manifest with no additional
transport call, unchanged attempt rows/raw bytes and unchanged request/byte
charges even at exhausted synthetic caps. The persistent live authorization and
ledger identity are unchanged; no live ledger exists or was reset. The suite now
collects 1,686 tests. Full-suite verification, source identities, before/after logs
and protected-file proof are in the existing historical-input evidence directory's
`lineage-correction/`; normal Linux fixture and browser results belong to PR #93.
No previous historical analysis was regenerated and no UI change was made.

KEEP all producer/policy/publication/browser safeguards and design-system 2.13.0.
FIX NOW this demonstrated offline acquisition-lineage defect. DEFER the still
BLOCKED secure-runtime, $0 access, retention-rights and approved private reviewer
storage prerequisites. Acquisition and probe remain NOT RUN: zero requests,
zero new response bytes, zero additional spend. The frozen manifest and
acquisition-execution.json stay unchanged. OMIT a new acquisition, invented
full-population proof, new reader judgment, trading-edge claim or next milestone.
Exact next action: Guidance independently re-reviews this same PR and owns the
normal protected merge. Astra stops unmerged after the normal checks finish.

## Secure historical execution checkpoint — 29 Sep 2026

The new `ops/historical-proof-execution` implementation starts from merged
PR #93 at `56b34a8bc7a8980559cad56be488e8a29489e4fd`, tree
`12794f02d0c291ff68ccbfdfde327d9551f5dbd1`. The single implementation PR records
its actual submitted head and normal CI. The source manifest remains canonical
SHA-256 `8d92ed5c56464fe9f342d024da14aa1521f6025d47ec32a6324a298b8fb63ebc`;
the old acquisition-execution.json remains the unchanged historical event.

PASS — local synthetic acquisition, both existing reconciliations, actual age
encryption, authenticated recovery and repeat offline reconciliation preserve
identical ledger, raw pages and detailed outputs. Wrong-key, corruption,
truncation, encryption failure, plaintext upload, incorrect scope and duplicate
execution are refused. Focused and full verification are recorded in the dated
execution handoff and the PR; normal CI runs the real encryption controls.
No historical POC, browser fixture, strategy threshold or timeout was changed.

The dedicated workflow exposes only manual mode and a numeric readiness-comment
identity. Its sole real step receives the existing Alpaca pair. Read-only
GitHub evidence binds the merged reviewed code, workflow, recipient, started
job and complete run history before provider access. Native run number 1 is
reserved for rehearsal, number 2 for real acquisition; both require attempt 1.
Failed or cancelled runs consume their slot. Existing SQLite ceilings remain
400 actual HTTP requests and 1 GiB retained response bodies. Partial evidence
uses the same encrypted delivery path. Runner loss or an oversized package can
still prevent recovery; no blind restart or new allowance is authorized.

PASS — a dedicated age key was generated directly under the owner's protected,
persistent NTFS directory outside Git and recovered a synthetic local file.
Only its public recipient/fingerprint enter the repository. Current read-only
GitHub account evidence supports the reviewed $0 budget basis, subject to a
fresh check before dispatch. The owner completed secure sign-in; read-only
inspection confirmed Paper / Basic / Current Plan. The delayed historical SIP
$0 entitlement basis is PASS; actual credential usability is NOT RUN. Current
API Terms document personal/noncommercial use, without establishing permission
for the proposed public ciphertext transfer or separate reviewer access.
BLOCKED is this narrow transfer-permission gap, not a claim that all personal
retention is prohibited. Guidance private transfer is NOT RUN; a local Windows
path is not a demonstrated reviewer handoff. The local full suite passed 1,818
tests at `747c0abb665ee43fde8227eea3eec25dd9c573d3`; final guard verification and
normal Linux CI are recorded in PR #94. Newer publication
`786ade7013a0c55d172d89118322b19a056fa8a6` was merged intact into this branch.

KEEP original records, design-system 2.13.0, producer/reader safeguards and all
public website behaviour. FIX NOW independent Guidance implementation review
and the concrete account-permission gap. DEFER actual rehearsal/acquisition
until review, merge and dated readiness PASS, then require actual artifact
download and local recovery before the real slot. OMIT a fabricated dataset,
original final-price mask, reader approval, trading edge or private inspection.
Actual manual run/attempt, acquisition, recovered real evidence and independent
real-data reconciliation are NOT RUN: zero Alpaca requests, zero response bytes,
zero acquisition spend. Full contract and next operator steps are in
`docs/input-truthfulness/2026-09-29-historical-execution.md`. Astra stops before
merge and dispatch; Guidance owns the normal protected merge.

## Workflow validation recovery checkpoint - 29 Sep 2026

The repair starts from merged PR #94 main
`33ec181ca60adaf2f7c0ef19a1889a5517161585`, tree
`6127e63213836f72caf708cb5b4294d750fe6147`. The previous reviewed head
`eb2b417a7a2289ab22c239ccfe06c20daf1dde7b` remains historical evidence.
Guidance comment `5884205539` suspends review `5347889698` and authorizes one
follow-up correction, with Guidance retaining review and merge ownership.
Repair PR #95 was created at `b00c6593498de62c282af275e2e7e2ac4b413e54` before
binding its actual number in policy; it records the final head. No old PR/head can approve
changed execution tools. This checkpoint supersedes the earlier native-1/2
execution instructions without erasing their dated test results.

FAIL - the merged historical workflow used runner.temp in job env, a context
GitHub does not allow. Normal Python/browser tests had missed that semantic
boundary. Pinned official actionlint 1.7.12 reproduces both errors in an external
copy of the original workflow. The corrected workflow initializes private paths
from RUNNER_TEMP in its first Bash step, exports them there and propagates them
through GITHUB_ENV. Each restored expression is independently rejected while
the valid control passes. Normal CI now applies that semantic gate to both
changed workflows before the existing tests; browser gates remain intact.

PASS - complete unfiltered history was reread at `2026-09-29T11:47:47.5184123Z`.
Runs `36520481662`, `36521323183`, `36524147152` are native numbers 1/2/3,
attempt 1, completed push failures with authoritative zero-job responses.
The small immutable recovery contract binds their exact repository/workflow,
branches, SHAs, attempts and saved API evidence identities. Any altered,
missing, duplicated, inaccessible or new unaccounted record blocks execution.
Native 4 is only conditionally the first rehearsal; phase numbering remains
separate. Failed/cancelled manual attempts cannot reopen a slot.

Policy, readiness and execution move to v2 and bind the repair PR, reviewed
head, PR #94 ancestry, unchanged tools/src/workflow, native number, phase and
recovery-contract digest. The wrapper and encrypted receipt/index retain that
identity. Offline replay and packaging reject a guard that relabels existing
retained evidence. Synthetic integration uses actual guard output, acquisition,
reconciliation, age encryption, recovery and offline replay; tests create no
live allowance. Targeted binding mutations fail their intended regressions
while the valid replay control passes. Final commands/counts, semantic logs,
protected-file checks and GitHub validation observations belong to the existing
execution handoff and repair PR.

KEEP frozen manifest, old acquisition-execution.json, historical inputs and
decisions, owner key/recipient, original ceilings and design-system 2.13.0.
FIX NOW only semantic workflow validity and evidence-bound history recovery.
DEFER dispatch until Guidance reviews/merges and releases a new rehearsal
identity after rechecking current history/readiness. Real mode retains its
separate transfer-permission blocker. OMIT new keys, new budgets, workflow
replacement, provider/model calls, UI/strategy changes and market conclusions.
Actual manual run/attempt, acquisition, private real recovery and independent
real-data reconciliation are NOT RUN: 0 Alpaca requests, 0 response bytes and
$0 additional acquisition spend. Original membership completeness remains
BLOCKED; new reader eligibility and trading-edge validation remain NOT RUN.
Astra stops at one repair PR for Guidance, without merging or dispatching.

Final local repair checks: PASS - 1,951 tests, zero skips, Python 3.12.14; one existing websockets warning. PASS - 9,756 protected existing Git blobs unchanged. The first full attempt's stale current suite count was corrected and the full suite rerun. PR #95 records final-head Linux CI and the post-push history check. Execution release remains BLOCKED; no merge or dispatch.

## Lossless projection compaction checkpoint - 30 Sep 2026

This bounded correction follows Guidance comments 5903186288 and 5903266884
on PR #95, from main `6284cb9787c11929eaedf1a263cf463ab4ae4928`.
The submitted compaction PR records its exact final head and normal CI.
Accepted execution checkout `6b12fdfa67355b436fde89287d159bebda2ce9fc`, tree
`d4ac339901ebe99039b912f30397d43d5d76efbb`, and rehearsal workflow revision
`2687b96d0200903c5d457301e4b3f335fcfb79ce` retain their historical meaning.
Run 36570997883, native 4 / attempt 1 / phase 1, artifact 11033808340,
and its accepted exact owner-side replay were not repeated or relabelled.

PASS - the actual untouched adapter was reproduced with invented decimals.
Versioned reconciliation/projection v2 constructs selected-row references,
fixed OHLCV masks and complete binary-hex values directly. The bounded decoder
reconstructs every legacy fact in order from hash-bound query/normalization
context. Raw pages remain authoritative for original JSON spellings. Tests
preserve exact frames, decimal audits, lineage, masks, unknowns and decisions;
explicit legacy output remains byte-reproducible. All 32 masks, precision
cases, duplicate replacements and corruption controls are exercised, with
independent exact rational checks and isolated restored-defect failures.

PASS - the local full suite ran 2,104 tests, zero skips, in 553.49 seconds.
Later reporting-only benchmark corrections passed nine focused tests; the
final collection is 2,106. FAIL - the separate local fixture check found 24
unchanged gzip objects differing only in Windows/Linux OS header byte, with
identical payloads, trailers and content identities. No fixture or gate was
changed; the PR records actual Linux CI. PASS - 10,541 protected existing Git
blobs were raw-byte checked, preserving frozen records and all execution limits.

Each full synthetic case ran once: 96 batches, 288 sessions, 2,753,568 bulk
rows plus two probe rows, 289 simulated transport slots and zero provider
requests. Central encrypted recovery is PASS: expanded 1,546,827,051 bytes,
gzip 203,495,174 and ciphertext 203,545,054, with all 390 original members
unchanged. Stress expanded size is PASS at 1,866,624,285 bytes, but gzip is
FAIL at 423,811,147 against 208,666,624. Encryption/recovery are NOT RUN;
post-refusal preservation is PASS. Both local combined reconciliation times
exceed the unchanged 30-minute step; hosted full-shape performance is NOT RUN.
Detailed measurements, hashes, commands and reporting limitations are in the
existing execution handoff and its linked compaction evidence directory.

KEEP the lossless representation, historical evidence, owner key, frozen
manifest/recovery identity, design-system 2.13.0 and website/strategy behavior.
FIX NOW Guidance review of this one PR and the measured archive/deadline
findings; any further archive-encoding work needs separate scoped authorization.
DEFER execution compatibility and real release: unchanged guards intentionally
reject borrowing #95's approval for changed tools. The nonoperative proposal
names only the exact earlier transport evidence and requires a reviewed new
head. OMIT repeated rehearsal, private-package inspection, provider/model calls,
new readiness, market conclusions and Alpaca outreach. The later personal-use
decision ends licensing investigation, without asserting provider consent or
silently changing attestations. Real acquisition, new reader eligibility,
Guidance plaintext inspection and trading-edge evidence remain NOT RUN.
Original final-price membership and real release remain BLOCKED. Astra stops
at the PR; merge does not release execution.

## Delivery readiness checkpoint - 30 Sep 2026, PR #97

This continuation follows Guidance review 5362976589 and comment 5906480203.
The measured runtime candidate is `00a56f3dd4d8d2b68377364e04ed1f490e8e5c7c`,
tree `16c8241fe63eab575471fdc2e52254718f6ed685`, based on merged PR #96 at
`19f75f3b7ad566fb98e8e8e28fd2482a3737e9bc`. Later documentation commits do not
constitute another runtime measurement. Earlier failures retain their original
dated meaning. The [technical review](docs/input-truthfulness/2026-09-30-delivery-readiness-evidence/delivery-review.md) links the source-bound receipts.

PASS - normal CI on actual PR merge checkout
`6c40cf7f97dd905617fe7aa796cf63ed3ae52247` passed 2,324 pytest tests, semantic
workflow validation, 12 producer fixtures and the clean-tree check. Browser
checks passed 127 DOM/store, 378 chart and 9,215 page checks; secret scanning
passed. All 28 runtime source hashes match the branch and tested merge checkout.
These individual normal jobs do not establish a passing whole Tests workflow.

The scientific implementation is unchanged. Each full synthetic case uses 96
bulk queries, all 288 sessions, 2,753,568 bulk observations and two probe
observations. Final central is PASS: archive 99,741,871 bytes, ciphertext
99,766,407 and expanded content 1,546,827,473 all fit their unchanged caps.
All 390 original members retain identical bytes, lengths and hashes; ledger
accounting is unchanged and both complete v2 reconciliation files reproduce
exactly after recovery. The initial and recovered two-date calculations took
1,377.739460 and 1,390.110803 seconds respectively, each within its own shared
1,800-second budget. Packaging took 37.288482 seconds.

Final stress reproduced all 388 original raw-page, query-manifest and full v2
reconciliation identities. Its initial calculation took 1,396.736550 seconds,
within the shared limit. The complete archive is FAIL: 215,909,287 bytes against
208,666,624, exceeding the cap by 7,242,663 bytes. Expanded content fits 2 GiB.
The package phase took 62.202810 seconds before refusing the oversized archive.
Encryption, recovery and a separate all-390-member post-refusal sweep are NOT
RUN. Initial calculation success and unused time do not establish delivery.

Versioned v3 binding relates only accepted transport run 36570997883, native
4 / attempt 1 / phase 1, to separately reviewed new code. The original recovery
contract, complete history and source-equality checks remain. No replacement
rehearsal or extra allowance exists. Legacy gzip v2 recovery preserves its
original metadata. Owner personal-use authorization is not provider consent;
the no-outreach direction remains in force. Technical evidence and a later
dated execution release are separate.

KEEP - the 199 MiB archive, 200 MiB ciphertext, 2 GiB expanded and original
request/raw-byte ceilings, deadlines, owner key/recipient, website, strategy and
design-system 2.13.0. FIX NOW - Guidance reviews this measured engineering result
and the single proposed next decision: separately authorize one level-12,
2 GiB-window comparison on verified synthetic stress inputs, bounded by 600
seconds and a declared 12 GiB process-memory ceiling. Keep the evidence caps;
no fit is promised and this checkpoint does not authorize the comparison.

DEFER - real release remains BLOCKED pending capacity closure and a fresh dated
execution release. Real acquisition, Guidance plaintext inspection, new reader
eligibility and trading-edge validation are NOT RUN; original final-price
membership completeness remains BLOCKED. OMIT - repeated rehearsal, owner-package
inspection, provider/model calls, licensing outreach, broader tuning and raised
caps or deadlines. Guidance owns independent review and merge; merge alone does
not release historical execution.

## PR97 bounded correction checkpoint — 30 Sep 2026

FAIL — the single Guidance-authorized level-12 / 2 GiB-window comparison has
finished and triggers stop condition A. The complete archive is 215,854,671
bytes against the unchanged 208,666,624-byte cap, exceeding it by 7,188,047.
Expanded content is PASS at 1,866,624,285 bytes. No second comparison, codec
adoption, encryption, full-case replay or hosted historical run follows this
failure. See the [dated correction review](docs/input-truthfulness/2026-09-30-delivery-readiness-evidence/bounded-correction/review.md)
and exact receipts; earlier accepted and failed evidence is preserved.

The repository base remains `19f75f3b7ad566fb98e8e8e28fd2482a3737e9bc` and the
reviewed starting head is `bd779c2a1ce14b8a7361c4866678e55e29ae18f8`. The final
submitted head and actual exact-head Tests/Secret Scan results are recorded in
the subsequent PR97 closeout comment, not invented in this pre-push checkpoint.
The accepted Linux measurement remains `00a56f3dd4d8d2b68377364e04ed1f490e8e5c7c`.

PASS — all 390 original synthetic source members were hash-checked during
streaming, without regenerated observations or changed scientific outputs.
The comparison retained the original public fictional PR96 metadata; it is not
a new execution receipt. Supervised wall time was 191.094 seconds, compression
CPU 180.734375 seconds and native job CPU 181.265625 seconds. Peak Python RSS was
2,205,577,216 bytes; peak aggregate job committed memory was 2,201,931,776.
Hard 12 GiB process/job committed-memory limits and a 600-second watchdog were
verified before execution. The output footprint sampled 215,873,410 bytes;
including retained input lengths gives 2,082,220,259 logical bytes. Ciphertext
size, stress encryption and stress recovery are NOT RUN because capacity failed.

PASS — the narrow scanner correction allows only the two independently verified
public-response hashes at the exact original receipt path. Actual gitleaks
8.24.3 controls retain detection of unrelated values, other paths and another
default detector. Normal final-head hosted CI is a separate required observation.
A receipt-bound PR97-only NOT RUN deferral prevents automatic repetition of the
accepted full benchmark after this stop; it does not certify changed source or
skip normal Python/browser/Secret Scan checks. README and .env.example remain
accurate without modification.

KEEP — the accepted central recovery, legacy gzip reader, lossless v2 outputs,
native-4 transport identity, original limits, owner-personal-use wording,
website/strategy and design-system 2.13.0. FIX NOW — hand this measured failure
and the scanner disposition to Guidance for independent review. DEFER — the
next delivery decision and any prospective source-bound execution review remain
BLOCKED; the unchanged technical declaration is BLOCKED. OMIT — more codec
tuning, a second rehearsal, owner-key/private-package access, provider/model
calls, outreach and actual historical acquisition. No market-data correctness,
new reader authority or trading edge is established. Guidance owns any next
instruction, clean merge and later real release; Astra stops at PR97.


FAIL — subsequent full commit-range scan at
`629ed4433daa6ff60a636cd56490cabb52a371f8` resolved the two original findings
but detected four additional public binary/source fingerprints in the newly
retained evidence. Astra introduced these while recording this correction.
The exact paths and content-hash verification are retained in the correction
review. No additional allowlist, detector exclusion or history rewrite was
made. These findings remain a separate Secret Scan blocker; the capacity
failure already requires the stop. Final hosted results belong to the PR97
closeout comment.


## 30 September 2026 — explicit delivery-envelope continuation on PR97

The owner superseded the stopped compression experiment with an explicit
250 MiB archive / 251 MiB ciphertext contract. The existing level-12 / 1 GiB
Zstandard codec, scientific contents and 2 GiB expanded limit are unchanged.
The v4 receipt/index bind the envelope; v2 gzip and v3 Zstandard retain their
original limits. Full synthetic acceptance at the new source is NOT RUN until
the normal PR benchmark completes; real execution stays BLOCKED.

The [current evidence](docs/input-truthfulness/2026-09-30-delivery-readiness-evidence/envelope-continuation/platform-and-contract.md)
records official platform limits, the unchanged account Actions $0 stopping
budget, narrow public-digest dispositions, exact history and focused controls.
The complete fixed central/stress cases require encrypted recovery, all390
original members and exact v2 replay under a kernel-enforced 12 GiB process-tree
ceiling. Dated earlier failures remain evidence. No compression search, provider
call, owner-key operation, private-package inspection or historical dispatch.


### 30 September 2026 - envelope recovery reader correction

The first v4 candidate `2e50aba0ffdc3b8bb09a7745c4e9edc45ce9281d` fit
all stress size and memory bounds, but recovery failed before tar extraction.
The reader incorrectly inferred a maximum block count from 128 KiB, which is
Zstandard's maximum block size rather than a required size. The retained stress
archive has 20,463 valid blocks. The reader now has an explicit 65,536-block work
budget; the writer, window, science and all other resource limits are unchanged.
The [dated failure](docs/input-truthfulness/2026-09-30-delivery-readiness-evidence/envelope-continuation/candidate-initial/recovery-failure.md)
remains FAIL evidence. A one-time decode of the retained synthetic archive checked
all 393 indexed members and all 390 original PR96 lengths/hashes without
recompression. The 126 focused package tests pass, including the restored defect
and before-allocation excess-work refusal; collection is 2,449 tests. New
source-pinned hosted acceptance is still required. Real execution remains
BLOCKED; historical acquisition and findings are NOT RUN.


### 30 September 2026 — complete synthetic delivery accepted for PR97 review

PASS — the explicitly versioned delivery envelope now retains and recovers the
complete fixed central and stress evidence. Base remains
`19f75f3b7ad566fb98e8e8e28fd2482a3737e9bc`; continuation started at
`65cd32ba0991ecad4bb04d53132d4a44889aca32`. Measured code is
`ca881bba3600d4eadee5481e5528161a5c2edb99`, tree
`1a3b64ddfd795dbb209780b421138e7d3535312b`. The final evidence-only head and its
normal CI are identified in PR97's subsequent dated checkpoint; source remains
identical to this measured revision.

The owner's delivery decision changes archive/ciphertext ceilings from
199/200 MiB to 250/251 MiB, with an additional explicit 1 MiB actual encryption
overhead bound. Expanded content remains capped at 2 GiB. The selected level-12,
one-GiB-window writer is unchanged. GitHub's authoritative artifact documentation
does not impose the former project ceiling; public standard-runner execution is
free, while storage remains separately quota-bound under the unchanged $0
stopping budget. Future quota can refuse delivery and is not certified here.

PASS — Tests run 36734865293/attempt1 completed both full cases. Central archive,
ciphertext and expanded sizes are 99,741,885  / 99,766,421  / 1,546,827,527 bytes;
stress sizes are 215,909,320  / 215,962,224  / 1,866,624,761 bytes. Both cases recovered
all 390 original members exactly, preserved ledger accounting and reproduced both
complete v2 reconciliation files byte-for-byte. All 388 portable scientific members
also match PR96. The 289 transport slots per case are simulated; provider requests
are zero. Compact artifacts 11109327191 and 11110657864 have verified GitHub ZIP
digests. TEST-ONLY encryption ran on the benchmark runners; no owner key or private
package was accessed.

PASS — initial/recovered offline passes took 961.338/986.024 seconds centrally
and 1385.438/1380.727 seconds under stress; packaging took 35.054/60.561 seconds.
Kernel-enforced benchmark peaks were 7,662,833,664/8,903,364,608 bytes, below 12 GiB,
without workload OOM. Existing shared-step/package/job deadlines remain. The
prospective full acquisition reservation plus measured work and assumed 300-second
overhead leaves 1369.001/927.238 seconds.

PASS — 126 focused package regressions, 2449 hosted tests, producer fixtures,
semantic lint, unchanged page gates and Secret Scan 36734865392. Exact path/value
scanner dispositions retain unrelated-value detection. The first v4 reader failure
is preserved and corrected with a bounded block-work contract; no compression
experiment followed. Ten assembled technical checks pass. Real execution remains
BLOCKED; native 5/phase2 is prospective, and accepted native 4 proves its old transport
only. Historical acquisition and historical findings are NOT RUN.

KEEP — scientific identities, every original member and dated evidence.
FIX NOW — Guidance independently reviews this completed technical package and
exact final-head CI. DEFER — protected merge and separately authorized acquisition
to Guidance. OMIT — further compression optimization, readiness approval and any
new infrastructure milestone.

See the [bound delivery review](docs/input-truthfulness/2026-09-30-delivery-readiness-evidence/envelope-continuation/review.md) for measured tables and receipts.

### 30 September 2026 — native-5 input and exact-attempt recovery

Guidance comment 5920371235 supersedes the unsupported root-walk diagnosis.
Base is `6979904ad872d8d648c93537c77ead5fda909481`, tree
`29c13da32a2752bc5d5abeec2c46c8d5c6fd9b13`; merged PR97 head remains
`8cc49dceb47d6fad8206c44caf091b1f2dadee14`. The repair head and exact CI will
be identified on its PR, linked from PR97. No historical record is rewritten.

FAIL — run 36780349890 / native 5 / attempt 1, job 110108745578, stopped
at the numeric readiness-ID check because the input contained four leading
ASCII spaces. Setup succeeded, step 2 failed, and the captured steps 3–14
were skipped. There was one job and no artifact. This is a started failure
before checkout/acquisition, not a zero-job exception. Provider usage was zero
because the acquisition step never executed; no ledger is invented. The root
walk succeeds and remains byte-identical, including Git-ancestor refusal.

PASS — the workflow now trims only edge ASCII spaces/tabs, rejects all other
noncanonical input with a constant diagnostic, and explicitly passes the
canonical ID through its boundary output to the guard. Owner, date, PR, head,
mode, phase and evidence checks still apply. Complete history was freshly
captured through empty terminators at 2026-09-30T22:10:04Z: exactly native 1–5,
with unchanged main and no open PR. Runtime admission must repeat that check.

The new incident relation is canonically pinned at
`8f884be642bbcc01a0c02907d73c8d1075ac9040c1b9620e1a307d7330c25c71`.
It requires the exact native-5 run, sole job and every captured step outcome,
with empty artifacts only as corroboration. Prospective native 6 / attempt 1 /
phase 2 requires readiness-v4 on the repair PR after merge. Readiness 5920107119,
native-5 attempt 2, extra history and another replacement remain refused.

PASS — 768 focused offline regressions, including actual workflow extraction,
restored defects, full guard/wrapper/TEST-ONLY encryption recovery, legacy gzip
and PR97 v4 reading. A minimal package identity conditional preserves old v4
reading; every byte outside that conditional matches PR97. Scientific, codec,
runtime, acquisition, old recovery/compatibility and measured proof pins remain.
The precise CI exemption verifies those pins and this repair's scope; it records
the unchanged full-scale benchmark as NOT RUN, never as a new measurement.
PASS — local Gitleaks directory scan; normal Linux CI is NOT RUN at this dated
pre-PR checkpoint. The technical declaration stays BLOCKED until actual CI.

KEEP — accepted evidence, budgets and all 250/251 MiB/2 GiB envelopes.
FIX NOW — complete the repair PR's normal CI and Guidance review.
DEFER — merge, fresh post-merge readiness and separate explicit release; only
then may Tahir dispatch once. OMIT — root changes, compression, provider calls
and readiness approval. Acquisition, recovery of provider data and historical
findings remain NOT RUN. README was corrected; .env.example remains accurate.


### 2026-09-30 PR98 implementation CI checkpoint (supersedes pending checks only)

PASS — the repair implementation at `4f1b6e3b37d206c70c0fe64780d0dceffa4b0ff6`
completed normal Tests run 36787315265 and Secret Scan run 36787315309, attempt 1.
Base/main remains `6979904ad872d8d648c93537c77ead5fda909481`. This dated
addendum records results; the final submitted head and its additional normal CI
are recorded on PR98. The implementation source is unchanged by this addendum.

PASS — the actual workflow boundary trims only edge ASCII spaces/tabs and emits
one canonical positive-decimal ID through the boundary output to the guard.
Embedded whitespace/newlines, Unicode, malformed IDs and wrong authorization
remain refused. The original ancestor loop is byte-for-byte unchanged: root
termination and Git-ancestor refusal pass. The four-leading-space failure,
fixed path and isolated restored defect are covered by extracted-shell tests.

PASS — fresh complete unfiltered workflow history at 22:45:55 UTC contains only
native runs 1–5. Run 36780349890 / native 5 / attempt 1, job 110108745578, is
one failed pre-acquisition job, not a zero-job exception. Setup succeeded,
step 2 failed, exact steps 3–14 were skipped and artifacts are empty. No ledger
was created; provider requests remain zero. The original three zero-job records
and accepted native-4 rehearsal retain their original meaning. New contract
`8f884be642bbcc01a0c02907d73c8d1075ac9040c1b9620e1a307d7330c25c71`
admits only prospective native 6 / attempt 1 / phase 2, under fresh post-merge
readiness-v4 and a separate release. Comment 5920107119 remains consumed.

PASS — 768 initial focused tests, 383 focused binding follow-ups and 32 actual
gitleaks-engine controls. Normal Linux CI passed 2727 Python tests, semantic
workflow validation, 12 fixture comparisons, clean tree, 127 continuity checks,
378 chart checks and 9215 page assertions. The single public Git blob false
positive has an exact path/value AND disposition; unrelated values, other paths
and default detectors still fail. Earlier CI failures remain dated evidence.

PASS — all 27 declared source pins and 13 protected Git objects match. PR97's
scientific/codec/runtime proof documents remain unchanged; no full-scale
benchmark was repeated. The 250/251 MiB archive/ciphertext, 1 MiB overhead,
2 GiB expanded, 12 GiB memory, 400-request/1 GiB raw, rate/retry/$0 and deadline
controls remain intact. The pure technical declaration is separate from any
owner readiness approval. Evidence and commands are retained in
`native5-recovery/proof-repair.json`, `history-final.json` and the existing
execution handoff.

KEEP — accepted evidence and limits. FIX NOW — Guidance review of PR98 and its
final-head CI. DEFER — normal protected merge, fresh post-merge owner readiness
and explicit execution release before Tahir dispatches once. OMIT — root-walk
changes, compression work, provider calls and readiness approval. Real execution
remains BLOCKED; acquisition, provider-package recovery and historical findings
remain NOT RUN. No dispatch, rerun, key access or private-package scan occurred.


## Checkpoint, 2 Oct 2026 — historical input run 6, executed and read

Main `a930ca0` (tools identical to the PR #98 head `d6d7743`). The owner posted
readiness-v4 comment `5924734477` on PR #98 (the `5921715962` candidate with only
`authorized_on` set to its UTC posting date) and dispatched once: run
`36815689950`, native 6 / attempt 1, job `110220126196`, workflow SHA `a900236`.
Guidance's separate release was never posted; the guard reads only the owner's
readiness comment. Pre-dispatch receipts are retained under the report's
`predispatch/`: the actual guard against live GitHub with only comment/run/job
synthesized (PASS; sixteen negative controls refused; repeated after `main`
moved), the real comment `5924734477` (PASS), preflight, pinned age, recipient
and 50 boundary inputs.

Public outcome (job log): guard PASS (it ran from `a900236`; step 7 then checked
out `d6d7743`); acquisition PASS in 14 minutes; offline reconciliation BLOCKED
(exit 2, so the job reads `failure` by design); package and upload PASS.
Artifact `11142297138`, 107,315,902 bytes, `sha256:043af0b3…f1b3`, expires 8 Oct.
The sandbox cannot fetch artifact blobs (403). The owner reported downloading,
recovering locally through the helper (zip digest check, `historical_package.py
recover` with a GitHub-verified expected-execution) and pasted a price-free
summary. The helper's step lines were not retained. A Linux copy of the helper
was rehearsed on a synthetic package with a disposable key, with refusals; its
log and adaptation diff are retained.

Owner summary ([report](docs/input-truthfulness/2026-10-02-historical-run6-result.md)):
97/97 queries, 289 of 400 slots, 275,899,601 retained bytes. RED on both
sessions under C and D, production and the independent calculator agreeing.
10-session ratios 0.93 / 0.89 against the original 0.94 / 0.89. Under C the
outer bounds over every unknown are 0.92–0.95 and 0.88–0.90, all below 1.0;
under D the ratios are exact. Populations 3,738 / 3,729 against 3,716 / 3,700.
The same three rules fire. Every intended stock returned target and prior bars,
but 263 symbols per session are partial, causes unassigned. Strict establishment
(evaluated on C) is BLOCKED by six counted stocks (ETRA, GIXI, OIG, TEVA, TRBG,
WCCB) lacking an input of the up-50%-month test; four also carry an unknown 4%
event under C. B stays BLOCKED.

KEEP the evidence and limits. FIX nothing: the strict rule did its job. DEFER
partial-symbol causes and Guidance private review (NOT RUN). OMIT any further
dispatch — no slot remains — and any trading claim. Next: the method's own
prospective qualifying-ticket check on a GREEN or YELLOW session.

## Checkpoint, 2 Oct 2026 — the first real-bar outcomes, and the two tools that read them

**Revision.** Branch `claude/spicystock-historical-workflow-i53ud1` from `main`
at `d185e48` (the merge of #99), pushed as **PR #100**; three commits:
`513eb170` (the archive replay), `70dba340` (the spec freeze and the retention
fix) and this closeout. `docs/data.json`, `docs/picks.json`, the history, the
evidence objects, the quality ledger and the vendored design system are untouched;
no run, mail, dispatch, merge or deployment. Guidance owns review and merge.
The owner asked, going to sleep, for "satisfiable proof or at least a way to
start investing". A 52-agent read of the repository (five readers, two skeptic
lenses per headline claim, a completeness critic, three paths, a judge; 1
confirmed, 18 reworded, 0 refuted) answered the first part: **no**. Run 6
reproduced one input (the RED regime on 24–25 September, owner-reported); the
pipeline has run on 17 real publications, 15 sessions, every one RED with 0
tickets, 0 picks and a scorecard of 0 plans; no fill, R, win rate or
expectancy had ever been measured on real data. Two readings were built so that
stops being true.

**`tools/historical_backtest.py`** replays the run's own stages over the bars a
recovered acquisition package holds -- the run-6 archive is 288 sessions of
4,780 names on the owner's computer -- session by session, through the
functions `run_evening()` calls (`apply_session_rules`, `session_eligible`,
`breadth.snapshot`, `scan_frames`, `rank`, `_make_plans(require_reader=False)`
with `slots_held(open_plans())`, `record.append`, `scorecard_rows` over the
whole archive, `summarize_scorecard`). Reader NOT RUN (a name's mechanical grade
caps its final grade; the ticket SET is not a superset of the live run's);
universe the archive's later membership; daily-bar fills; a labelled
counterfactual block without the gate; a shortened `--lookback` admitted only
with its equivalence check against the run's own on every overlapping session
(regime, every candidate's grade/score/vetoes, every plan's prices and shares;
one difference is FAIL and exit 2). **The judge's reviewer found a defect by
execution before the owner ran it:** `record.append()`'s `MAX_PICKS` retention
(260) silently dropped a long replay's oldest plans -- 284 issued, 260 scored,
the four winners gone. `record.append()` gains `max_picks` and
`record.scorecard_rows()` gains `window_sessions`, both default-unchanged and
read at call time; the replay passes `retention_bound()` and refuses to score a
population it did not issue. The same reviewer corrected the report: the exact
lookback's window (18 Aug–25 Sep) was not "already known RED"; the records'
own history puts the 10-session ratio at 1.03–1.54 through 8 September, YELLOW
on that rule, RED only from 9 September. Eighteen tests; eight in-memory
mutants killed with controls green, one (the published window) after it
SURVIVED on an incidental fact of the fixture. One session costs about thirty
seconds at the archive's scale on a burst-heavy synthetic market; the owner's
helper `run-backtest.ps1` runs the exact lookback and `--lookback 130`.
**NOT RUN here**: the owner's run over the real archive.

**`tools/signal_outcomes.py`**, under a spec frozen in `70dba340` before any
outcome was computed (`docs/input-truthfulness/2026-10-02-signal-outcomes-spec.json`,
SHA-256 `d93ad856…`), tickets every burst row in the first publication of each
of the 15 real sessions with `plan.burst_plan` at the GREEN multiplier -- no
reader, no gate, no slot -- and walks it with `record.replay` over the records'
own published bars (53,452 bars over 2,053 symbols; the newest publication
wins; 2 revisions, both a re-priced low), bucketed as `scorecard_rows` buckets
and summed by `summarize_scorecard`, in strata by the checklist's verdict.
**Over 6,064 rows and 14 nights, 11–30 September 2026, every stratum lost.**
Admitted (A+/A, no veto): 202 settled, 37 wins / 159 losses / 6 even, mean R
−0.235, median −0.47, mean of night means −0.291 with a 95% night-bootstrap
interval [−0.486, −0.109]; B −0.445, C −0.368, skip −0.386, vetoed −0.425; all
1,478 settled −0.392. 234 admitted tickets are uncertain on daily bars (1,828
of all rows; the bound with every one filled at its trigger is −0.332), 619
rows set aside because an 11 or 14 September signal's own bar is in no later
history, 579 pending (1 October), the five settled A+ tickets all losses, costs
at 5/20 bps a side −0.276/−0.400. The reader-accepted stratum is one pending
row (DAC). **Read it as: on every night the gate refused, its own tickets would
have lost, in every grade -- the first real-bar evidence that the RED refusal
had value on the nights it was applied -- and the checklist's grade ordered the
strata the right way but found no group that made money on RED nights.** It
says nothing about GREEN or YELLOW nights, which the record has never carried,
and nothing about the reader. Exploratory: every next close was public before
the spec. Thirteen tests, hand-computed R; eight mutants killed. Results in
`docs/input-truthfulness/2026-10-02-signal-outcomes.md` and its evidence folder
(`summary.txt` verbatim; `signal-outcomes.json.gz`, whose uncompressed SHA-256
is `cc67f25ef2f9963426e807e2085b12323fa2fbea3d0183dc909fbac3983a4341`).

**Measured** (this sandbox, Python 3.12, pandas 2.2.3): 2,758 tests collected;
the full suite at `513eb170` 2,707 passed with 34 environment-gated skips, and
the final tree's run is recorded in PR #100; gitleaks 8.24.3 with the repo
config: no leaks; `git diff --check` clean. CI on `513eb170` green on all
seven checks (pytest, page, both benchmark jobs, the gate, two gitleaks runs).
Not run: the owner's archive replay; any GREEN or YELLOW night; the reader.

**Keep / fix / defer / omit.** Keep: the spec frozen, the study re-run unchanged
as nights mature (every publication after 1 October adds confirmatory signals,
settling five sessions later); the replay's conservation refusal. Fix if it
bites: `historical_backtest.py`'s `_slim()` keeps every candidate's plan per
night, so a 158-session `backtest.json` will be large. Defer to the owner:
run `run-backtest.ps1` before the artifact expires on 8 October (the recovered
folder makes the expiry moot); decide the 128 MiB evidence cap the judge
projects to bind in November. Omit: any threshold or rule change in response to
these numbers (CLAUDE.md's own OMIT of future-return tuning); another
acquisition; any claim of edge. **The way to start investing is unchanged and
now has a reason behind it:** the product writes a ticket on the first GREEN or
YELLOW night an accepted reader review admits; the one study that exists says
the nights it refused deserved refusing. The first confirmatory number arrives
when the first post-freeze signal settles.

## Checkpoint, 6 Oct 2026 — the first readable rate: the owner's backtest, and the confirmatory read

**Revision.** PR #100 merged on the owner's instruction as `788aa092` on
`main`, over `d185e48` plus the two nightly publications its tests had never
seen: run 2026-10-02 (`58e0f384`) and run 2026-10-05 (`178956b4`), both RED
(10-session ratio 0.91 and 0.97), no ticket, both `degraded` on thin coverage
and one unread name. The branch was restarted from that tip. This checkpoint's
PR carries documentation and evidence only: no code, no run, no mail, no
dispatch, nothing under `src/` or `tools/`.

**`main` is red on the page job since the merge, and the likely cause is not
#100's.** The job log's assertion is `control exists: [data-history-inspect=
"2c5ec387…"]` in `tools/continuity_check.mjs`. The mechanism, read from the
check's source and not reproduced here: the check drives its journey over two
fixture records but its recovery step searches the LIVE `docs/history` index
of the checkout and clicks the 11 September record by a hard-coded blob; the
public history keeps a 21-calendar-day window, 11 September left it between
the 2 and 5 October publications, and a `GITHUB_TOKEN` push triggers no
workflow, so the merge of #100 was the first CI run to see the new index. Pytest is green on the
same commit. It is the shape this file names worst, a test whose answer depends
on the date, and it fails every pull request's page job until the check
resolves the identity from the index it just searched or serves a frozen index
through its own fetch stub. Fix pending. Also seen: the evening cron fired three
to four hours after its slot on both nights, the records landing at 9 and
10 PM ET, still before the next open.

**The owner's backtest, recorded**
(`docs/input-truthfulness/2026-10-06-backtest-results.md`, the two summaries
verbatim beside it). The exact lookback: 28 sessions, 15 YELLOW and 13 RED,
the counts the records' own history implied; the production policy wrote 16 A+ tickets, 6 settled,
3/3, +1.94R. The 130-session lookback, equivalence PASS over 28 sessions with 0
differences: 158 sessions from 10 February, **100 YELLOW, 58 RED, 0 GREEN**;
99 A+ tickets at half size, 44 settled, 16/27/1, win rate 0.36, mean +0.08R,
median −0.09R, net +3.72R (at most about $46: the $25 YELLOW budget is halved
again by the stop-risk rule on every stop-constrained ticket), 42 uncertain, 13 not filled, SPY +0.37% over the same windows. The counterfactual
without the gate: 153 tickets, 69 settled, +17.40R; its RED nights 25 settled,
7/18, +1.14R; A grade 23 settled +10.22R against A+ 46 settled +7.18R. The
first readable rate the mechanical policy has had, its own dispersion and costs
unmeasured without the per-row file; the reader NOT RUN, the universe the archive's later membership, daily-bar fills.

**The confirmatory read** (`2026-10-06-signal-outcomes-confirmatory.md`): the
frozen code over nineteen publications under a spec that differs from the
frozen one by two appended entries only (SHA `688d552f…`, the byte-level diff
retained as `spec-diff.txt`). Exploratory admitted now 267 settled, −0.189,
night CI [−0.431, −0.049]: the 1 October night's 50 settled are 0 wins, and
fifteen late-September tickets that settled since are 13 wins, +15.10R. **The
re-read found a bias the first report did not name: a night read before its
fifth session leans toward losses** (29 September −0.425R over 27 settled on
2 October, −0.038R over 39 now). Confirmatory admitted 132 rows, 5 settled all
at −1.0R on their first session, 81 pending; the reader's own A/A+
admissions are two rows, DAC on 1 and 2 October, one uncertain, one holding.
Nothing confirmatory is readable before the 9 October publication.

**Keep / fix / defer / omit.** Keep: the spec frozen and extended by appended
publications only, each extension committed with its hash and diff. Fix: the
continuity check's dated identity. Record, not defer: the counterfactual's
A/A+ split (23 and 46 settled, grade not split by regime) is not a tuning input
and raises no method question at these counts; GREEN, unobserved in 158
sessions. Omit: any rule change on these numbers; a second
acquisition; an edge claim.

**Next action.** Re-run the study after the 8 October publication (1 October's
tickets settle) and after 9 October's (2 October's); fix the page job; the live
policy's own first ticket still needs a YELLOW night with an accepted A+ review.

## Checkpoint, 6 Oct 2026 — the page job's dated identity, fixed

**Revision.** Branch `claude/spicystock-historical-workflow-i53ud1` restarted
from `main` after PR #101 merged (the owner's instruction, as #100 was). One
code change, under `tools/`, nothing under `src/`: no run, no mail, no
dispatch, no record touched.

**Reproduced here first**, with jsdom installed in the sandbox: on the current
tree, where the 11 September directories are gone from `docs/history`,
`node tools/continuity_check.mjs` exits 1 on `control exists:
[data-history-inspect="2c5ec387…"]`, the assertion CI showed on `main` and on
#101. The mechanism, confirmed by reading `history.publish()` and the page's
`findEarlier()`: the archive keeps `history.DAYS` (21) calendar days, so the
2 and 5 October publications dropped the 11 September records from
`docs/history/index.json` and their directories, while the check pinned its
clock to 14 September and searched the checkout's LIVE archive. The page smoke's
own grading-history case was never exposed: it pins its index and serves its
files through `page.route()` from `tests/fixtures/grading/`.

**The fix.** The check's fetch stub serves every `docs/history/` path from
`tests/fixtures/continuity/history-2026-10-01.json.gz`, the 1 October
`index.json` and the 11 September record's `record.json`, `burst-ATEC.json`
and `burst-VICR.json` exactly as published (commit `d185e48`), their SHA-256
digests verified against the index before freezing; a path the bundle lacks is
a 404. One assertion was added: the recovery read the frozen archive and the
checkout no longer carries the record. 128 checks pass on the current tree.
**Four mutants in separate copies of the tree**, the working tree untouched:
serving the checkout again reproduces the original assertion; a broken
`data-history-save` fails on the save control; one changed byte of the frozen
context is refused by the page's own digest check (`publicJSON()`); an
unrelated label change passes. gitleaks 8.24.3 over the fixture and the check:
no leaks. README and `docs/continuity/README.md` name the frozen archive.

**Not run here:** the chart check and the page smoke, which need Chromium the
sandbox cannot download; CI's page job is the proof, and its result is on the
PR. **Settled:** a check over a rolling public artifact pins that artifact in
a fixture; the live `docs/history` is read by the page, never by a test.

## Checkpoint, 6 Oct 2026 — the findings on the site, night by night

**Revision.** Branch `claude/spicystock-historical-workflow-i53ud1` from `main` at
`e57b41ee` (the merge of #102). The owner, after the plain-words account of what
the October work found, asked for it on the site, "to visually understand how
the strategy looked over this period and how the market and the suggestions
responded, something dynamic like the method". `docs/data.json`, `docs/picks.json`,
the history, the evidence objects and the vendored design system are untouched;
nothing under `src/` changed; no run, mail, dispatch, merge or deployment.

**What the site showed before** (three readers and two skeptics by execution,
nothing refuted): the Record view's "What historical validation establishes" was
the 28 September study alone -- `docs/historical-validation.json` v1, thirteen
publications through 25 September, zero tickets, zero settled, three wait cases --
and nothing on the site named run 6, the signal-outcome study, its confirmatory
read or the owner's backtest, which lived only as Markdown under
`docs/input-truthfulness/` with no link from the page.

**What was built.** `tools/build_historical_findings.py` is a reader over committed
evidence only: the two study outputs, the publication records the study's spec
names (read from git by commit and held to the blob through
`signal_outcomes.load_publications`), the owner's two pasted backtest summaries
parsed by the exact line grammar `historical_backtest.summary_text()` emits (a
line the grammar does not know is a refusal, never a skipped number), and the
pasted run-6 summary with its public receipt. It writes
`docs/historical-findings.json`, every block naming its source and digest,
`--check` holding the file as `make_fixture.py --check` holds the fixtures, and a
field name the secret scan would read as a credential refused before anything is
written. Its one arithmetic is the per-night, per-stratum count, sum and mean of
settled R over the study's own rows, re-derived by `tests/test_historical_findings.py`.
`docs/app-findings.js` (`SCStock.findings`) is the walkthrough's sibling: a stepper
over the published nights (Back, Play, Next, the arrow keys, Space,
`SCStock.findingsInterval` for tests, reduced motion honoured); one SVG with two
panels over the same sessions -- the 10-session ratio on every session the records
know, each published night its own publication's value and every other session
read from the newest publication whose history carries it (only 24 August to 10
September from the 5 October record; the rest from older ones), a later history
that reads a night differently named beside it, the two thresholds of its ratio
rule named at the axis with a key that says green also needs every other breadth
rule quiet, the backtest's 28-session exact-lookback pass bracketed under the
dates; and under it every settled R of that night's counterfactual tickets for
the chosen stratum on a compressed signed-log axis (a position and never a value:
real ticks, nothing clipped, every R in the table twin) with the night's mean, the
nights after the current one ghosted so Play reveals the outcomes as they came.
A stratum control (A-quality, B, C, skip, vetoed, every burst), a lead line that
counts the nights and their verdicts off the file, a caption with the night in
words, the facts, the first-read-against-now line and the hold's horizon, a
legend, two table twins; then the owner's backtest (a stat strip, labelled bars,
the production and counterfactual rows and the exact-lookback pass, the pasted
summaries' digests), the run-6 fresh-bar check, the caveats with the pooled strata
printed off the file, the six reports; the 28 September cases follow under their
own heading, the section last in the Record view. It reads no record, no clock
and no storage; `loadFindings()` in app.js fetches the file when the Record view
is first shown and the shape check passes or one sentence says why not; a
fixture page says the replay reads the public findings; the page adds no figure
of its own. `tools/backtest_timeline.py` is the per-session export the owner can
run on the private backtest record -- each night's breadth and how each gate's
tickets came out, every field copied by type from a fixed list, a ticker or a
private key anywhere a refusal -- so the February-to-September nights' breadth
and outcomes could one day be drawn beside the published ones; it carries no
grade per R and no fired reasons, so not the stratum control (NOT RUN on the
real file). The publication gate's `RECORD_FILES` names both study files, so
Pages is verified serving them, which it was not before.

**Measured** (this sandbox, Python 3.12.3 and pandas 2.2.3, Chromium through
Playwright 1.56.1, at the first pushed tip): 2809 tests collected, 2775 passed, 34 environment-gated
skips; 12 fixtures current; the findings file current; continuity 128 on every
one of fifteen runs, the last five on this tree; the chart check 378/378; the
`findings` suite 598/598 at 1280, 390 and 320, both themes; the full smoke with
`--shots` 9813/9813.
gitleaks 8.24.3 over the tree with the repository's config: no leaks. After the
third review (CI's own runners at `5b94f01b`): 2886 tests pass; continuity 134;
the chart check 378/378; the full smoke with `--shots` 10059/10059, the
`findings` suite 844 of them; gitleaks green. Here: 12 fixtures current, the
findings file current, and gitleaks over the tree finds no leaks.

**Two reviews by execution, every upheld finding reproduced before it was
touched.** The first, over the first pushed tip, returned 54. The page said
things the file does not: "settled after their 5-session hold" on nights still
inside it, "after the chart reader N stayed" on the night it gave no usable read
(22 Sep), means the study writes at three places re-rounded to two (−0.09 for
−0.085), a wash claiming green off the ratio alone. The builder now counts what
the page used to add up (`tickets`, `a_quality`, `first_read.horizon_passed`,
`admitted_positive_nights`, `inside_hold`), refuses a bucket it does not know, a
night with two horizons and a report the checkout lacks; it also carries
provenance and summary fields the page does not print. The module checks the file's shape before it draws
(`shapeProblem()`), every field the drawing and the blocks index into, and ends
in one sentence; a failure one level further down takes the half-drawn replay
away. Both historical files load only when the Record view is first shown, under
a timeout, and a continuation whose block has left the page writes nothing: that
is what crashed `continuity_check.mjs` on four of six runs (the fetch resolving
after jsdom closed); `continuity_check.mjs` closes a window with both files in
flight to hold that guard. The second review, over the fixed
tip, found three more of substance. The rules wrote 58 A-quality tickets on 11
September and the page said 30: the study plans every burst before it checks the
bars, so its 28 set-aside rows carried tickets it never walked (named now as some
of those written, and the reason is the later records not carrying the signal's
own bar, which all 631 such rows say). The lazily loaded replay pushed the page's
own *Open model plans* link about 3,450 px down, so the evidence follows the
plans now and nothing a link lands on sits under it. And a file missing a
threshold, a phase or an R drew NaN or printed "undefined".

**The browser found what the checks had not.** Choosing a night in the phone's
chooser removed it, the removal fired a focus-out that removed it again, and the
exception aborted the step (`closePick()` clears its reference first). The
current night's dots were never highlighted: the inline tone beat the rule, which
sets a fill now. `is-animated` was toggled and styled nowhere (the transitions
are scoped to it, so a redraw no longer animates), found by a class check that
had matched by substring. Screenshots at 1280, 390 and 320, both themes, were
looked at: the bracket's label ran off a 320 px chart and the tabs' caption sat
beside four rows of tabs, both fixed.

**The mutation passes.** Builder mutants in full copies of the tree, each
regenerating the file with the mutated builder so the byte comparison cannot be
what kills it: six for this pass's fields and refusals, all dead in the test
naming their rule, a control green. Page mutants through a routed copy of the
module, `app.js`, `app.css` or `index.html`, the tree never written: thirty-two
over three rounds, all dead, three controls green. Three survived the first
time, one of them a hole: "yet" on a finished night with nothing settled lived
because no A-quality night has one (the check reads graded skip on 11 September
now, the second shape this file names). The other two were mine: a mutant that
removed one of Play's two off-screen stops while the observer still stopped it
(sharpened, and it dies), and a no-op.

**CI found what the sandbox could not.** The first pytest run on the pull
request errored three findings tests: CI's checkout is one commit deep and the
builder reads the spec's nineteen publications from git by commit. Reproduced in
a depth-1 clone (the same three errors; full history, all eight pass). Giving
the job `fetch-depth: 0` is not open to this pass: `tests.yml`'s SHA-256 is one
of the accepted delivery proofs' pinned sources, and editing it turned 363
binding tests red (5 failures, 358 errors). The module's first fixture fetches exactly the named commits
when they are missing and fails with the reason, never skips: proved green in a
depth-1 clone of a remote that serves commits by id, as GitHub does, with no
stray file, and red with all eight erroring when the remote cannot be reached.

**A third review, over the merge-ready tip, returned 52 findings, each upheld by
two verifiers; all 52 are fixed.** Six were high, and all six were sentences the
page could not support. "The live policy would have written no more tickets than
any counterfactual here" is false of the backtest, whose slot cap a reader
downgrade frees. It now says the signal-outcome study bounds the names and the
backtest's ticket set is not a superset of the live run's. "Gate removed" over the
graded B, C and skip and the vetoed strata hid that the study's `ticket()` also
bypasses the grade's and the veto's own refusals; each stratum now names what its
counterfactual removed. The pooled reading mixed the five confirmatory first-day
stops into the exploratory figure and would have called the refusals valuable
over a green night. The builder now writes a `reading` block: the exploratory
nights pooled over RED nights only, and the nights left out counted. The
confirmatory split is printed from the study's own E2 figure against its minimum.
And no test held the market line, the gate's reasons or most table cells.

The mediums:
- A later history that moved a night's counts but not its ratio went unnamed; the `later` block now carries all three.
- A night past its hold was printed as final while 30 of its rows could still move; `movable` counts them, so "so far" and "yet" hold until none can.
- Means of 2 or 11 settled tickets were read as rates; under `record.SCORECARD_MIN_PLANS` a night now shows its count and sum, and its mark is hollow.
- A tap during Play let the next tick close the chooser.
- A stratum change collapsed the twins.
- The tooltip ran off a 320 px chart.
- The caption drifted screens under the stage as the list of nights grew.
- The literal guard could not see a number typed as a numeric literal; a guard over the code now refuses one, and a routed file moves every rule number a caption quotes.
- The parsers now refuse a missing, repeated or misplaced line and a bool that is not True or False.
- The timeline's privacy sweep rested on fixture facts. It now places one name in each source alone and allowlists the output schema field by field.

The lows were wording, CSS specificity, an index name that ran digits together,
and a loading line.

**Its mutation passes.** Twelve builder mutants were run in a scratch clone, each
regenerating the file with the mutated builder: all twelve died in the test naming
their rule, and the control stayed green. Twenty-four page mutants were run
through routed copies: all died, and two controls stayed green. One was a no-op of mine (a
duplicate `rows` key, which a later key overrides) and dies once sharpened.
Another died by a throw that stopped the suite, so a missing mark now fails its
check instead. The continuity check now closes a window with both historical
files in flight, once answering and once failing. Removing the catch-side guard,
or the study's, kills it. Removing the then-side guard alone is equivalent: the
catch-side guard swallows what it would have prevented. Fifty-one timeline
mutants (the agent's) all died; three were re-run here and died, with a control
green.

**Keep / fix / defer / omit.** Keep: the builder reads and the page prints; the
study's spec stays frozen and extended by appended publications only, the
findings file rebuilt after each extension with `--check` holding it. Fix if it
bites: on a phone 29 of the 46 sessions precede the first night, so the 17 nights
share about 100 px at 390 and a tap at 320 offers nine (the list of nights is the
precise way); future nights are ghosted to about 1.5:1, by design during Play; a
page with no record leaves the section an empty card, as on `main`; on a 320 px
chart the note before the first night has no room and is left out. Defer: the
three frozen cases leaving the public window on the 16 and 19 October
publications; the February-to-September nights, which wait on the owner running
`tools/backtest_timeline.py`. Omit: any rule change on these numbers; a claim of
edge. **Not claimable:** a live fetch, Resend, Pages until the gate prints
Verified on the merge, and CI on this branch until the pull request runs.

**Next action.** Review and merge the pull request; after the 8 and 9 October
publications, append them to the spec, re-run `tools/signal_outcomes.py` and then
`tools/build_historical_findings.py`, and the replay shows the first confirmatory
nights.

## Checkpoint, 7 Oct 2026 — green nights when only a few stocks are a session behind

**Revision.** Branch `claude/spicystock-historical-workflow-i53ud1` restarted
from `main` at `42258ace` (the merge of #103), pushed as **PR #104**. The owner
asked, going to sleep, for the nightly runs that "literally always end in
degraded" over 10-20 stocks to finish green, or for a way to handle the stocks
that did not get data after the run. `docs/data.json`, `docs/picks.json`, the
history, the evidence objects, the quality ledger, the workflows and the
vendored design system are untouched; no pinned file is edited; no run, mail or
dispatch.

**What the record said** (all 16 publications from 16 September to 6 October,
read from git). Every one was `degraded`. Each carried 10-24 stale stock frames
of about 4,790 (0.21%-0.50%), every one ending on the previous XNYS session,
the benchmark printed. On nine of the 16 the reader also had one to three
replies refused by reader authority; on 22 September all twelve (the format
defect #88 fixed); on 6 October the Anthropic balance ran out after six
answered reads and the run spent twelve more calls on six names. The late bars
the archive retains for six of those stocks (GRAL, GURE, HBNB, LBTYB, SANG,
SPHL) are all the provider's placeholder: one price, zero volume. And the
mail's `coverage_thin` sentence -- "the bars fetch ran out of time or names
answered late" -- was never true of any of them.

**The rule.** The ledger is untouched: acceptance stays `degraded`, every stale
stock counted and its inputs unknown. `inputs.stale_tolerance()` writes
`run.input_tolerance`: a degraded acceptance whose ONLY gap is stale frames,
each one session behind, no stock under an unfinished open model plan among
them, and at most `pipeline.STALE_TOLERANCE_FRACTION` (1%, floored in exact
arithmetic: 47 of 4,793) of the intended stocks, is tolerated and named, and
the stale frames do not degrade the run. The benchmark is counted beside the
stocks and never among them: it feeds only the scorecard's comparison line.
`src/followup.py` reads the previous publication's stale stocks again from the
next session's own frames -- no provider request, the evening's own session
rules, price policy, `scans.scan_all` and `watchlist.build`, at the previous
session -- into `run.stale_followup`; a late bar that would have been listed
degrades the night that finds it and is named, and is never a signal, plan or
ticket. A same-session re-run reads the same stocks again from its own fetch.
`reader_coverage.reads()` counts the reader's shortfall by cause (`refused`,
`format`, `account`, `credit`, `transport`), names the refused tickers, and
tolerates refusals within `READER_REFUSAL_FRACTION` (a quarter) of the night's
reads while every other read was accepted and no refused name is one the
regime would have planned (`admitted_grades()`, one rule for the planner and
the reads; a vetoed name costs no ticket either way). An empty credit balance
stops the calls like a refused key and says to top up; an error made of the
reply's own text can never stop the run. The mail's `coverage_thin` sentence
is the page's now, and it names late inputs as well as missing ones. Each
block is held one level in by `report.validate()` to the record's OWN archived
constants, and asked for only under rules that write it.

**The owner's decision, shipped as yes.** May a night be green when reader
authority refused at most a quarter of its reads, none on a stock that would
otherwise have had a ticket? Yes is what is merged; a refused name keeps its
checklist grade and earns no ticket either way. `READER_REFUSAL_FRACTION = 0`
restores the old rule for refusals and keeps the cause names and the credit
stop.

**Projected over the record** (the reviewed code over each publication's own
blocks, read-only from git): 14 of 16 publications and 13 of 15 sessions green,
against 0. 22 September stays degraded (no reading accepted), 6 October too
(the credit). Not one night would be degraded on coverage.

**The review, worked.** A workflow by execution over the first pushed tip, six
dimensions, two skeptics per finding: 39 findings. Thirty-five were upheld by
both skeptics and two by the only skeptic of theirs that finished (the disk
filled under the review's own copies of the tree). The skeptics of the last
two test holes ran after the fixes were pushed: they found both closed at
`728e184c` and the review's own mutants killed there, an independent check of
the fix rather than of the finding. The highs were sentences:
- "so the run is not degraded" on a night degraded for another reason;
- "each ending on the previous session" when one frame ended two back;
- the problem sentence on a night whose only gap was a late match;
- a late bar the setting-up list would have taken read as `no_match`;
- a same-session re-run carrying the replaced record's block verbatim.

The tests named five holes:
- a forged-reads test matching only `run.reads`, so three of its checks could be deleted green;
- the one-rule test held only the planner's half;
- no test held the unfinished-plan filter on either side, or the veto exemption;
- the tolerance's re-derivation compared no `stale`, `evaluated` or `previous`.

Each is pinned by the test it named. One is stated rather than fixed: the
follow-up reads the late bar on the next run's split-adjusted basis and says
so, so a reverse split on that one night could make it name a match the
original basis would not; it degrades, never greens.

**The page job.** `main`'s own page job ran 14 m 54 s of its fifteen minutes on
the #103 merge, so this PR's first CI run was cancelled at the cap with
10599/10599 checks passed. `tests.yml` is a pinned source, so the smoke runs in
two lanes over one browser: lane A every suite that writes the smoke's shared
scratch records or reads the clipboard (Chromium shares it between contexts),
one after another; lane B the self-contained modules. No suite was dropped or
changed (the calls diffed equal); each printed line carries its lane. CI's
first two-lane run took the smoke's step from 14 m 38 s to 9 m 30 s, and found
one suite that had leaned on the clock: `refresh` raced a 900 ms slow answer
against fixed pauses, and with the other lane loading the runner, the click on
the re-rendered control landed after the slow answer, so 7 checks failed. The
slow answer is held now until the check releases it, every press waits for its
request to be answered, and the page counts the answers it has read before
the order is asserted. The sequence-guard mutant still fails it (6 checks), and
three loaded runs at once pass 1149/1149.

**Measured** (this sandbox, Python 3.12.3, pandas 2.2.3, Chromium through
Playwright 1.56.1): 3026 tests collected, 2992 passed and 34
environment-gated skips; 13 fixtures current, `thin`
new; continuity 134; the chart check 378/378; the full smoke with `--shots`
10608/10608 in its two lanes, 12 m 36 s here beside a running mutation pass.
Screenshots at 1280, 390 and 320 in both themes were looked at; the first pass
found "1 fetched frames were stale". gitleaks 8.24.3 over the 45 changed files
with the repository's config: no leaks.

**Mutation passes**, every mutant in its own copy of the tree, judged by the
test naming its rule, a control green each time:
- before the review, 38 mutants: 37 died first, and the 38th (a hard-coded 1% on the page) died once a fixture archived 2%;
- over the tests the review asked for, 10 mutants, all dead;
- over the review's fixes, 10 mutants, all dead: the setting-up route, the re-run re-read, the zero-volume re-derivation, the publication's day in the sentence, the ending's dates, the benchmark count, the clause's wording (its anchor respelled once before it could run), the run-fatal guard, the veto exemption, and "within" only when it applied.

**Keep / fix / defer / omit.** Keep: the ledger's acceptance as built; the
tolerance a status rule only. Fix if it bites: there is no trend alarm if the
stale count climbs toward 1% behind a green chip (every stale stock is named
nightly and the follow-up keeps what its bar turned out to be); a lane-B suite
that one day writes a shared scratch record must move to lane A. Defer: a
stale walk under an open model plan stops a session short (pre-existing; the
guard degrades such a night instead). Omit: suppressing a stale stock,
re-fetching it, or treating its late bar as a signal.

**Not claimable:** a live night. The first evening after the merge is the only
test of the tolerance on real data; until the Anthropic credit is topped up
every night reads `claude_unavailable` with the credit sentence, after one
call.

**Next action.** Top up the Anthropic credit; read the first live night's chip,
its `run.input_tolerance`, `run.stale_followup` and `run.reads`, and record
them here.

## Checkpoint, 8 Oct 2026 — the first live night under the tolerance, and the bound it needed

**Revision.** Branch `claude/spicystock-historical-workflow-i53ud1` restarted
from `main` at `a8f9a36f` (the 7 Oct publication over the #104 merge), pushed
as **PR #105**. `docs/data.json`, `docs/picks.json`, the history, the evidence
objects, the quality ledger, the workflows and the vendored design system are
untouched; no pinned file is edited; no run, mail or dispatch.

**The first live night, read.** Session 7 Oct published at 01:54 UTC on 8 Oct
(the primary cron slot fired 3 h 38 min late), `degraded` on `behind_more`:
sixteen stale stocks (ATGL, BEBE, BLIV, ELLO, ELTK, GYRO, HFBL, IOR, MAYS,
MDRR, MFI, NCEW, PFX, ROMA, TULP, WBD), fifteen ending on 6 Oct and ONE on
5 Oct, against a limit of 47. The rest of #104 held: `run.reads` 9 of 12
accepted, 3 refused (ASMB, CMND, VSTM) within the limit of 3, `tolerated`; no
credit failure on the topped-up balance, exactly 12 calls (cache_write 3,336,
cache_read 36,696, uncached 48,562: about $0.26); `run.stale_followup`
`not_applicable` / `membership_not_recorded`, because the 6 Oct record predates
the rule. Regime RED (ratio 0.96, 54 up 4% against 196 down); mechanical A+ 1
(ROKU, lowered to C), A 28; no ticket. The rule did what it said; what it said
was too narrow.

**The bound.** `pipeline.STALE_SESSIONS_MAX = 5` (P, archived as
`pipeline.stale_sessions_max`; `rules_version` moves). `inputs.stale_tolerance()`
tolerates a frame ending within the five XNYS sessions before the evaluated one
on a readable date (`allowed_endings()`), and `run.input_tolerance` is version 2:
`sessions_max`, and `endings`, where each named frame ends, held by
`tolerance_faults()` to the names and to the ledger's `latest_bar_dates`.
`followup.missed_sessions()` gives the sessions a stock missed, from the one
after its recorded last bar to the previous publication's, the most recent five
at most; `night()` reads every one, one row per stock and session
(`rows[].session`, `block.sessions`, `block.stocks` beside `count`). A
version-1 membership is read at the previous session alone, so the 8 Oct run
reads 7 Oct's sixteen names at 7 Oct only; a same-session re-run re-reads the
same stock-sessions, a version-1 block among them. The page's Method quotes the
archived bound and keeps the first version's words for a record without it.
The `thin` fixture's first evening serves one stock two sessions behind and one
a session behind; its second evening reads three stock-sessions.

**The review, worked.** A workflow over the first pushed tip returned 21
findings. Five were upheld by both skeptics; sixteen were left unverified when
the skeptics hit a usage limit, which is not "refuted", so each was checked here
by execution. One of those was refuted by a skeptic that did finish (the ledger's
date histogram is not reconciled against `stale`; pre-existing, out of scope)
and one is an equivalent mutant (`ending >= previous` in `missed_sessions()`).
The rest were real and are fixed:
- **The validator refused the block the run wrote** when more than
  `STALE_NAMES_MAX` frames were stale and the benchmark was one of them:
  `names=names or []` re-derived the stock count with the benchmark among the
  stocks. Reproduced at 102 stale frames, then fixed. `_benchmark_stale()` reads
  the benchmark off the ledger: ready means not stale; not ready with no other
  gap that could hold it means stale; only beside another gap is the block's own
  count read, as one benchmark or none. Pre-existing on `main`.
- A frame ending on Labor Day, or five sessions back across it, decided nothing
  in the suite, so a weekday count survived. Both cases now hold the calendar.
- A same-session re-run over a version-1 block re-read nothing. It reads that
  block at its own session now, and keeps a not-applied block's reason and words.
- The multi-session sentence counted readings as stocks ("1 stock ... 3 are not
  in this run's selection"). No frame and out of selection are said in stocks
  now, with their readings beside them.
- The late-bar problem named two readings before the 200-character bound cut it.
  It leads with its counts now and names tickers (`followup.problem_message()`).
- The page said a version-1 record's `behind_more` in version-2 words; it says
  each in its own words now. The README, `.env.example` and `method.md` said "the
  last 5 sessions"; they say "the 5 sessions before the session evaluated" now.
- Untested until now: the row bound, the near edge of the session bound, endings
  without names, an unreadable ending accepted, the page's new rule strings, and
  `allowed_endings` sitting outside the literal guard.

**Measured** (this sandbox, Python 3.11.15, Chromium through Playwright 1.56.1):
3070 tests, 3036 passed and 34 environment-gated skips; 13 fixtures current;
continuity 134; the chart check 378/378; the page smoke 10623/10623 with
`--shots`, the `inputs` suite 216/216.
Screenshots of Method at 1280 and 390, over the current rule, a frame past it and
the first version's record, were looked at. Twenty mutants, each in its own copy
of a snapshot taken before the pass and judged by the full test files that name
the rule (no `-k` filter, the gap a reviewer found in the last harness): all
eighteen die, both controls green. Over the first tip, before the review, eleven
mutants died the same way. gitleaks 8.24.3 over the tree and over the branch's
commits: no leaks.

**Projected over 7 Oct's own record:** green under this rule (16 within 47, the
furthest two sessions back, 3 refusals within 3).

**Keep / fix / defer / omit.** Keep: the ledger's acceptance as built; the bound
a status rule only. Fix if it bites: a stock stale for more than a week degrades
the night as a different kind of gap, by design, and nothing yet says how many
nights that costs. Defer: the evening cron fires 2-6 hours late every night and
the primary slot has no already-published guard (a late primary re-ran 21 Sep's
session after a dispatch had published it: two full runs, two mails); a
two-line guard, in its own pull request. Omit: suppressing a stale stock,
re-fetching it, or treating its late bar as a signal.

**Not claimable:** a live night under this rule. The first evening after the
merge is the test: read its chip and `run.input_tolerance.endings`, and the
night after, a `run.stale_followup` with more than one session.

## Checkpoint, 8 Oct 2026 — a pinned price is not a coil

**Found by the owner's first trade.** The owner drafted a first live trade from
the 7 Oct record's two top setting-up names, PRTH and ARX, at the record's own
trigger, limit and stop. Both are pending all-cash takeovers: PRTH at $8.05 (a
CEO-led take-private, announced 21 Sep, closing H1 2027) and ARX at $20.25
(Thoma Bravo, signed 13 Aug, go-shop ended 22 Sep with no bid). So are the
other three names of that top five: BWIN ($32.50), ACVA ($10.50) and MG
($20.35, trading above it in its go-shop). A price a deal holds stops moving,
and the list ranks exactly that first: TTT, a high TI65 from the deal's own
gap, the lowest compress. The plans' +8% targets sat above the deal prices,
and a broken deal gaps far through any stop. Nothing in the method trades a
merger spread.

**The rule.** `watchlist.MIN_COMPRESS = 0.30` (P, archived as
`watchlist.min_compress`, so `rules_version` moves): a name whose last seven
sessions range under three tenths of the sixty before them fails Stage C as
`pinned`, and is left out of the also-quiet rows too: it is no near miss, and
the list's own key (lowest compress first) would rank it ahead of every real
one. Every name under 0.30 on the lists from 11 Sep to 7 Oct 2026, 17 in
all, was checked against filings and the press, and each was a pending cash or
mostly-cash takeover. Every other name was at 0.37 or above, including the two
nearest, which were not cash pins. The textbook coil the tests draw is 0.33.
It reads the bars, not the news: MG, at 0.46, stays on the list, and only a
corporate-actions source could take it off. The tests' frames that sat under
the floor were redrawn above it, with each test's subject unchanged; the
sequel fixtures' AMD, short by its box alone, is now short by two and leaves
the also-quiet rows.

**Not run here:** a live night under the rule. The burst scan is untouched: an
announcement day is a real 4% day, and only the day after shows the pin.

## Checkpoint, 9 Oct 2026 — the $2,000 cash-account morning milestone

**Goal.** `PRODUCT_GOAL.md` is the owner's active milestone contract. Cash
account, Chicago time, broker unspecified. The first release improves reliable
preparation; it does not assert a financial result or a daily supply of trades.

**What changed.** `docs/app-morning.js` adds a native Morning desk dialog in the
masthead, over the existing publication/model/availability authorities. Chicago
window and preparation instants come from the archived schedule. The $2,000 /
0.5% / 25% personal reference is compared with the publication, never used to
rewrite an old ticket. Settled cash starts unknown, is tab-local, clears on
reload/new session and is never treated as verified. Manual checks clear on a
new publication. Clock repaint preserves an open dialog, cash draft and focus.
Known corporate-event risk and its safe primary-source links are readable in
the selected setup. The existing stock workspace keeps its first-screen space.

`src/allocation.py` is the shared reaction/anticipation allocation. Reaction
rank precedes watchlist rank. Existing hold, sell-half, sell-into-strength,
pending, uncertain, unmeasured and unreadable model plans reserve their original
principal; partial model sales do not free it. Missing commitment evidence
reserves the configured equity conservatively. An occupied symbol or a second
same-symbol ticket is refused. Every allocated-out order is cleared before
retaining picks; raw structural eligibility is kept separate from allocation.
`record.replay()` carries the original ticket limit so a pending or uncertain
commitment uses the maximum permitted cost. `provenance` reconstructs both
plan families, event refusals and the combined budget. The offline historical
reaction study stays reaction-only but uses the same reservation; entry-limit
comparisons read the record's account and archived gates.

`knowledge/event-risk.json` contains dated SEC and issuer sources for MG, PRTH,
ARX, BWIN, ACVA and ZIM. `src/event_risk.py` refuses their unresolved cash-acquisition
momentum tickets, archives the bounded registry and its digest in the rules,
keeps overdue reviews blocked, and requires a sourced resolution to end one.
Evidence from after the evaluated date is not presented as then available.
Unlisted stocks have not been cleared by live news; this is a manual registry.

The 10 October 2026 ZIM correction reviewed the actual 9 October publication
at `62bce72d`: its anticipation plan offered two shares with $61.36 maximum
order cost and $2.04 planned price-to-stop risk, despite the unresolved
Hapag-Lloyd $35 cash merger. The issuer's 16 February announcement, 30
September SEC approval-process update and 6 October guidance release are
captured byte-for-byte under `release-evidence/2026-10-10-zim/`, with exact
excerpts, URL, retrieval time and raw SHA in its manifest. The September report
says the Israeli GCA stopped handling the existing application and Hapag-Lloyd
intended to submit a revised proposal; this is not a sourced deal termination.
The October guidance increase remains research context, not an exception to
the existing cash-acquisition policy. The registry reason uses only the
original announcement, so later updates are not leaked into earlier sessions.
The old production data, picks and morning receipt were not rewritten; a new
verified publication must establish the exclusion on the live site.

Validation on Python 3.12.14: 257 targeted event, pipeline, provenance, morning
and documentation tests passed; 13 current-pipeline page fixtures and 21 morning
receipt fixtures passed their generator checks. Removing only ZIM from an
isolated registry copy made all four ZIM tests fail; removing unrelated MG kept
those four green. The original morning full/red publications are now immutable
SHA-pinned source inputs, not regenerated outputs. Receipt generation uses their
archived registry; current page fixtures continue to exercise today's pipeline.
The original legacy receipt bytes remain unchanged. Removing the archived-input
digest guard failed its new test; an unrelated captured-halt clock edit passed.
Source hashes and excerpts were checked against the retained response bytes.
`.env.example` was reviewed: this evidence-only correction needs no new variable.
These are local checks, not a claim about later hosted CI or production release.

Next event-coverage milestone: inspect provisionally executable candidates via
verified CIK/SEC submissions and bounded issuer releases, retain dated source
evidence, and expose unavailable or unreviewed coverage explicitly. Unresolved
older agreements need their latest updates; a recent-headlines-only window
would miss ZIM's February agreement. No upcoming ZIM earnings date was verified
in this bounded review, and source discovery must never mean comprehensive
news clearance.

`evening.yml` explicitly configures $2,000 and 0.5%; local defaults retain the
old model for compatibility. Both scheduled slots check the intended nominal
session, not the delayed runner's calendar date. They skip current real
ok/degraded publications, holidays, newer records and recovery after the next
exchange open. The selected branch is checked out at its current tip. Manual
session/rehearsal controls remain. New account notes state cash preparation,
unknown broker balances, general T+1 timing and order-support checks; they no
longer assert a Fidelity margin account.

**Executed locally.** Python 3.12.14; source-backed synthetic pipeline fixture
regeneration (13 JSON files), 199 core targeted tests, then 96 post-regeneration
allocation/provenance tests, 158 research-tool compatibility tests, 41 workflow
tests and pinned actionlint. Chart checks 378/378; morning/risk/actionability
615/615; final focused morning 260/260; continuity 134/134. Phone/desktop dark
and light screenshots were inspected. Independent review executed another 117
pipeline/workflow/allocation/event checks with no blocking finding. Isolated
rule-removal tests failed their intended controls; unrelated controls remained
green. The full Python suite passed all 3,151 tests locally and on GitHub.
The hosted browser pass found a narrow masthead overflow and stale allocation
and order-control assertions; those are repaired in the release follow-up.
The combined allocator also explains zero-share refusals using the actual
effective risk budget and position cap; two regression cases cover market/stop
reductions and an independently binding position cap. Legacy record wording is
preserved. The final suite collects 3,153 tests.
Hosted browser and historical runtime gates subsequently passed; the
production acceptance checkpoint below records the completed release.
Local historical storage tests need unsandboxed
execution because the sandbox can synthesize `/tmp/.git`; do not weaken their
storage or authorization guards to accommodate that environment.

**Current evidence.** The Oct 8 record had 730 discovered reactions, 12 reviews
and 11 accepted replies (all eleven below the trading grades); yellow admits
A+ only. Zero reaction tickets. MG and SN anticipation tickets bypassed its old
budget. At $2,000, MG is now event-excluded, SN sizes no whole share, and FTNT
and VRNS have invalid stop geometry. Do not force a ticket from that list.
Current publication and historical results are not edited by this code release;
the production acceptance checkpoint below records the real hosted
publication that accepted the new settings on actual data.
The no-email real-provider rehearsal (Actions run 37921303809) passed its
publication gate and independent evidence replay with no missing objects or
provenance breaks. It measured 4,774 of 4,775 intended stocks, published 728
reaction candidates, accepted 11 of 12 chart readings, and retained a partial
reader warning for HAE. The $2,000 account, $10 base risk, Chicago opening
time, combined cash/slot membership and cleared refused orders all passed
independent checks. It allocated no orders and refused MG with the archived
cash-acquisition source. This dry run is a rehearsal, not a new live record.
PR #107 records the final hosted gate and publication evidence.
The next milestone is trustworthy morning quotes/event coverage and a smaller
initial payload, followed by measured opportunity coverage.

## Checkpoint, 9 Oct 2026 — defer the closed scan matrix

**Scope.** `renderScan()` now publishes the count, explanation and closest miss
immediately, but `hydrateScan()` builds the criterion rows only when the native
disclosure opens. It reuses that table across close/reopen so sorting and opened
evidence survive. Every record render clears old rows, including same-object
revisions; an already open scan rebuilds synchronously from the current record.
Legacy scan routes hydrate before scrolling; legacy stock routes still open
their stock without constructing the scan. The design system observes the added
table and attaches its existing keyboard and criterion controls. No publication,
schema, observations, plan, availability gate or provider request changes.

**Executed.** Python 3.12.14, Node 24.19.0 and Playwright 1.56.1 Chromium.
`tools/scan_cases.mjs` covers absent initial rows, native keyboard opening,
record immutability, no extra record fetch, sorting, evidence, criterion and
arrow navigation, reuse, open/closed refresh, same-object revisions, a queued
toggle across replacement, empty records and legacy destinations. All 80 new
checks passed; the focused fixture/reading/refresh/volume/chart-keyboard pass
passed 2,246 checks. An isolated source override restoring eager construction
failed six intended checks; an unrelated wording override passed all 80.
`tests/test_docs.py` passed 37 tests; continuity passed 134/134. README and `.env.example` were swept;
no environment configuration changes. Desktop and phone screenshots inspected.

**Measured, not a mobile-device benchmark.** One cold Chromium context at each
of 1280 and 390 pixels, height 900, on the same Linux host without CPU/network
throttling, against the unchanged Oct 8 publication: 14,789,950 raw bytes,
SHA-256 `f5d94ffc5cf10566c6debe7b0cb9bd946165d026c90d757fc494908e6f60cb5b`.
First usable paint was the render marker followed by two animation frames.
The earlier local baseline was 1,006.8 / 988.6 ms; deferred rendering measured
512.8 / 516.2 ms. Work between JSON parse and the render marker fell from
411.9 / 373.9 ms to 131.8 / 138.1 ms; initial DOM nodes fell from
63,601 / 63,599 to 5,901 / 5,899. No browser errors. The payload remains
unchanged (the public host previously transferred 1,528,683 gzip bytes).
Opening the complete 730-row matrix took 1,343.3 / 1,344.3 ms through paint:
the work is deferred, not eliminated. Loading with a scan deep link still pays
that cost, deliberately. Payload separation and progressive matrix rendering
remain separate future work. The production acceptance checkpoint below records
the completed hosted gates and release of this follow-up.

## Checkpoint, 9 Oct 2026 — morning milestone published on real data

**Released.** [PR #107](https://github.com/spicyChicken59/SpicyStock/pull/107)
merged as [1b6e9c24](https://github.com/spicyChicken59/SpicyStock/commit/1b6e9c24).
The exact release head passed 3,153 Python tests, 10,881 browser assertions,
378 chart assertions, and the historical central, stress and release gates.
The local runtime was Python 3.12.14. This closes the earlier checkpoint's
pending hosted core gates.

**Production evidence.** The explicitly no-email
[production scan](https://github.com/spicyChicken59/SpicyStock/actions/runs/37928234562)
published the Oct 8 session at 12:10:20 UTC on Oct 9 (7:10 a.m. Chicago), with
`dry_run=false`, `email=skipped`, rules identity `8e9ea8528b31`, and publication
commit [e67f8cba](https://github.com/spicyChicken59/SpicyStock/commit/e67f8cba).
The [dashboard publisher](https://github.com/spicyChicken59/SpicyStock/actions/runs/37928885283)
and [Pages deployment](https://github.com/spicyChicken59/SpicyStock/actions/runs/37928913340)
both succeeded. This is now real production evidence, superseding the earlier
rehearsal-only acceptance gap.

The published account is $2,000 cash-account model equity, 0.5% base risk
($10 before reductions), 25% per-name cap and four model slots. Independent
account/allocation verification passed; provenance replay passed all 732
retained evidence objects with no missing evidence or breaks. Both reaction and
anticipation allocated zero tickets and zero new commitment. MG remains
excluded with its archived acquisition source; FTNT and VRNS fail final stop
geometry; SN sizes no whole share. Its explanation now uses its actual reduced
risk budget. The run remains explicitly degraded because 11 of 12 chart
readings were accepted and HAE's reply violated the evidence contract. These
outcomes do not justify relaxing the gates or claiming a winning trade.

**Live browser acceptance.** At 12:21 UTC,
[the public site](https://spicychicken59.github.io/SpicyStock/) passed browser
checks at 1280 and 390 pixels against production run `37928234562`: matching
$2,000 / 0.5% account, unknown settled cash, Chicago 8:30–9:00 entry window,
zero tickets and $0 commitment, MG's SEC source with no order, restored dialog
focus, no horizontal overflow and no JavaScript errors. The production mobile
Morning desk and desktop site screenshots were inspected. The receipt and
screenshots are under `/tmp/spicystock-live-37928234562/`; PR #107 retains the
final acceptance summary and deployment links. Milestone 1 is accepted on live
data. Browser verification used a task-scoped proxy CA pin without a persistent
trust-store change.

**Performance follow-up.** [PR #112](https://github.com/spicyChicken59/SpicyStock/pull/112)
defers rendering the closed scan matrix until requested. Its reviewed head is
[f45d917c](https://github.com/spicyChicken59/SpicyStock/commit/f45d917c), with
3,153 Python tests, 10,961 browser assertions and 378 chart assertions passed.
All historical central/stress and release gates passed in
[Tests 37924303043](https://github.com/spicyChicken59/SpicyStock/actions/runs/37924303043).
Merged as [12ea3b23](https://github.com/spicyChicken59/SpicyStock/commit/12ea3b23).
[Publisher 37929813283](https://github.com/spicyChicken59/SpicyStock/actions/runs/37929813283)
and [Pages 37929842050](https://github.com/spicyChicken59/SpicyStock/actions/runs/37929842050)
succeeded. At 12:26 UTC the live 1280/390 browser checks again passed against
run `37928234562`, including zero initial scan rows and all 728 rows after
opening the scan. The cash/account, Chicago window, sourced event refusal,
focus, overflow and browser-error checks remained green; final screenshots
were inspected. Receipts are under `/tmp/spicystock-live-37928234562-deferred/`.
PR #112 retains the hosted and public acceptance summary. Final documentation
checks passed 37/37; README and `.env.example` were swept with no additional
configuration change. Deferring the matrix does not reduce the initial JSON transfer:
the production record is still 14,918,679 bytes before transport compression.

**Continue at milestone 2.** Add a secure read-only morning quote/event check
with actual feed entitlement, observation times, spread/liquidity coverage,
trigger/limit/stop comparisons, named news/earnings/action/halt sources and
explicit missing/stale/outage states. Verify it before the normal 8:30 a.m.
Chicago open; keep credentials server-side and confirm the broker before
adding broker-specific instructions. Split detailed retained evidence out of
the initial payload without breaking provenance or old-record readability.
Then improve review-path compliance and measure whole-share feasibility and
the complete candidate funnel under milestone 3. The existing workflows provide
scheduled scans; this checkpoint creates no unattended development process.

## Checkpoint, 9 Oct 2026 — publication-bound morning observations

**Scope.** The next part of PRODUCT_GOAL milestone 2 is a dated, read-only
observation layer. `src/morning.py` reads only existing admitted orders and
binds exact canonical bytes, publication/run/rules/session, stage, ticker,
evidence and retained plan. It never edits evening records, changes sizing,
grades a stock, creates an order or sends email. IEX quotes/trades retain their
source timestamps, conditions, venue and sizes; delayed SIP volume keeps its
own timing and cannot confirm live pace. The receipt archives separate
measurement-age policy. Invalid, stale, crossed, missing, future or failed
measurements cannot become current quotes. The collector refuses an expired
window before spending provider calls.

**Events and persistence.** `src/morning_halts.py` parses the bounded Nasdaq
RSS and distinguishes quote restart from explicit trading resumption, older
unresolved halts, source-clock rollback and security deletion. Known positive
halt and corporate exclusions persist through omission, outage and empty
candidate lists; source-backed resolution evidence is needed to clear them.
News and earnings remain unchecked, and the corporate registry remains bounded.
Current registry classification stays separate from retained source facts.
The publication helper checks both canonical-record and prior-observation
hashes against current main, as well as run identity and clock bounds. Each
ordinary push changes only `docs/morning.json`; a race repeats all checks or
refuses. Provider credentials belong to the read-only collector job, while a
separate job has the repository write permission.

**Website.** `docs/app-observations.js` verifies the actual loaded publication
bytes before attaching a morning receipt. It shows dated source observations,
price comparisons, expiry and coverage limits in the Morning desk and selected
stock. A source-backed halt or corporate restriction narrows order-copy
controls. Pre-open prices below a conditional trigger remain observations,
not a new strategy cancellation. A bounded session cache retains verified
public event evidence across reload/fetch failures; it stores no private cash
or saved-watchlist data. Requests use the fixed public morning file and never
send private saved symbols. Clock repaint preserves focus and cash input.

**Operations.** `morning.yml` makes two best-effort attempts at 8:20/8:28
Chicago, with active UTC-offset, XNYS-session and entry-cutoff guards. Manual
rehearsals do not publish. The optional fixed-SPY source diagnostic uses the
same adapter/normalizers but has no publication or order authority, cannot
write into docs, and is retained separately. The legacy intraday workflow is
now artifact-only with no email credentials or activation schedule. The
existing dashboard publisher verifies morning.json whenever it is committed.

**Validation and release acceptance.** Python 3.12.14. Tests use the real
fixture producer and morning collector; captured Nasdaq RSS is separately
identified from invented AAPL corporate/halt scenarios. The deterministic
morning fixture check is part of CI. Named isolated mutations exercise
source age, exact limit versus extension, evidence retention and publication
races; unrelated controls remain green. Local source/probe/workflow/doc checks,
hosted full checks, provider rehearsal and public acceptance are recorded in
the final release PR. No production financial result follows from these tests.
Historical Git/API doubles use captured prior workflow and scanner blobs,
with their original compatibility hashes still required. A historical chart
comparison waits for its first attached layout; the exact text assertion still
detects changed chart data. Production historical gates and evidence are unchanged.

**Remaining acceptance.** This implementation is a dated snapshot transport;
Actions/Pages delays can exceed the quote freshness limit. Reliable morning
delivery and current entry-window observations need a suitable backend.
Issuer news, earnings and comprehensive corporate-action coverage, the
smaller reader payload, broker-specific guidance and an actual first-trade
review remain unfinished. Continue milestone 2 without marking a first
successful trade or dependable live-quote service complete.

## Checkpoint, 9 Oct 2026 — compact reader and deferred research

**Scope.** `src/reader.py` derives a compact `reader.json` and a shared,
content-addressed complete observations object from exact canonical bytes.
The browser keeps candidate evidence, plans, account, timing and embedded
charts immediately available; it requests the larger public history only for
saved research. `data.json`, `picks.json`, recommendation provenance and old
historical bytes remain unchanged. Production run `37928234562` projects from
14,918,679 to 5,606,909 bytes, with a 5,040,916-byte deferred object. Hydrating the
projection reproduces the original parsed publication exactly.

**Binding and continuity.** New morning receipts derive a reader SHA on the
server. The browser hashes the actual loaded reader before attaching a quote
receipt; a copied canonical SHA claim cannot substitute. Legacy receipts keep
independently validated positive event facts through the migration, including
halt, corporate exclusion and carried resolution evidence. They do not become
reader-bound quote receipts. Missing or failed deferred research stays unknown.
Verified sidecars merge once without resetting morning state or replacing
saved chart/input nodes. Fallback bars never merge before hydration, avoiding
an equal-close adjustment-basis conflict. Exact retained model outcomes stay
readable without inventing prices or fills. Public requests carry no private
saved symbols, notes or positions.

**Publication.** Initial installation and both final evening restamp paths use
one staged companion installer, preserving rollback of fixed records. The
publisher verifies exact canonical-to-reader-to-sidecar derivation before a
Pages request, and evening artifacts include the companions. The owned
`reader-observations/retention.json` preserves the currently served object and
21 calendar days measured against advancing publication-session dates, with
the old current object's session refreshed on supersession. This is not a
wall-clock grace guarantee after a late publication. It removes only verified,
previously indexed derived objects after successful publication; unrelated
files and canonical/history/evidence remain untouched. Capacity is bounded to
84 retained objects and 128 MiB, with one additional 32 MiB installation
allowance. Malformed ownership refuses mutation; cleanup failures warn and
retain ownership for retry. Prior reader ownership must replay against its
canonical bytes before adoption.

**Verification.** Independent checks reproduce production and all 12 schema-2
page fixtures with exact hydration and valid provenance. Failure injection
covers staging, reader/data/index installation, final restamps, cleanup retry,
unknown-file preservation, expired ownership, and capacity refusal. Browser
acceptance covers deferred requests, digest/metadata tampering, publication
races, retry, legacy event evidence, saved adjustment basis and private draft
continuity. Local reader assertions passed 89/89, existing related browser
flows 477/477, continuity 134/134 and evidence geometry 4/4. Full hosted and
public acceptance belong to the final release PR; these local checks alone do
not establish deployment.

**Remaining goal.** Continue verified morning delivery and broader issuer-news
and earnings coverage. Actions/Pages snapshots are still not a dependable
entry-window quote service. Broker confirmation and the first actual trade
remain outstanding. The read-only opportunity audit for #109 found that the
only whole-share-feasible A+ pre-review candidate was already reviewed and
then downgraded; no missed executable candidate was established in that scan.

## Checkpoint, 9 Oct 2026 — combined morning release accepted on the public site

**Released.** PR #114 merged as `37fd449f552247ba41e7b09df16e1e6f0d6f444d`.
It includes the complete morning-observation work and compact reader. PR #113
was closed as incorporated; its unfinished central replay was cancelled as
superseded, not counted as a passing run. All release gates passed on the
actual integrated head `484cf8b1998f2769536d034140a2cb790f809e67` before merge.
Merged-main Tests `37964050670` also passed the full Python, fixture, browser
and chart checks at the deployed merge commit.
The design-system repository remains connected and unchanged; the existing
local, pinned SpicyChicken assets continue to style the page.

**Hosted checks.** Tests run `37960437440` passed 3,368 Python tests, fixture
reproduction and clean-tree checks, 11,204 browser assertions and 378 chart
checks. Secret scan `37960436448` passed. Both native historical cases passed
with enforced 12 GiB memory and zero swap: central took about 18m04s at 7.09 GiB
peak; stress 27m49s at 8.24 GiB. Each recovered all 390 originals byte-identically,
kept ledger accounting unchanged and reproduced both offline dates with zero
provider requests. Positive and negative controls passed. This establishes
runtime/recovery behavior, not live strategy profitability. Local execution
used Python 3.12.14; the hosted Python jobs use 3.12 and native cases pin 3.12.14.

**Actual sources.** Rehearsal `37964077963` ran on merged main with dry-run and
fixed-symbol source probing enabled; persistence was skipped. At 17:08:31 UTC,
the IEX request succeeded with a quote about 0.35 seconds old and a trade about
7.63 seconds old. Delayed SIP also succeeded; its latest trade was about 15
minutes behind. The diagnostic is explicitly outside publication/order
correctness and does not prove pre-open availability. A separate actual Nasdaq
RSS capture at 16:40:43 UTC parsed 49 events, had a source age of about 22.55
seconds, and validated ten sampled symbols including halt and resumption
cases. Unmatched symbols remained unverified. Exact diagnostic bytes and results
are retained in [the release evidence](release-evidence/2026-10-09-morning/acceptance.json)
and its neighboring `nasdaq-source.xml`; no provider credentials are included.

**Production and publication.** Morning run `37964299335` persisted only
`docs/morning.json` in commit `2fa9773f046299de78c95d1b513c05880a3eefdb`.
Its actual 17:10:18 UTC collection was after the entry cutoff, so it truthfully
reports `inapplicable / entry_window_ended`, zero rows and no provider lookup.
It binds canonical source run `37928234562`, canonical SHA
`36e3ac12a53d78d7f9adccfb302793aa8fad2e2fb00548ed1d2124538350b1bd`
and reader SHA `fd24d85a0a32ba26d550b5840ff80b9be6db4453c55c1ca7c1ca4a9e7faf70ca`.
Publisher `37964465703` verified all 28 public files against committed main;
Pages `37964497884` built and deployed successfully. No email or broker order
was sent in this release work.

**Public browser acceptance.** The actual site passed at 1280 and 390 pixels;
all four captured screenshots were inspected. Both visits loaded 5,606,909
reader bytes (690,230 encoded response-body bytes), with zero initial canonical,
sidecar or historical requests. A later explicit shared read verified the
5,040,916-byte sidecar, restored 2,305 observed symbols and 7,944 retained signals,
and preserved the morning binding, real chart node, cash input/value and focus.
No browser provider request, horizontal overflow or page error occurred.
First desk-ready measurements were about 1.37s and 1.02s in these single
unthrottled hosted navigations; they are not a mobile-device or future latency
guarantee. The page showed the $2,000 reference, Chicago window ended, unknown
settled cash, zero tickets and $0 model commitment. The source record, picks
and old evidence remain unchanged.

**Documentation correction.** The sidecar retention clock uses advancing
publication-session dates. A late manual publication need not occur on its
measured session date, so README and the reader checkpoint now state that
basis instead of promising 21 elapsed days after wall-clock replacement.
Current sidecars are always retained; cleanup ownership and behavior did not
change.

**Next work.** Milestone 2 remains open for dependable entry-window delivery
and broader issuer-news/earnings coverage. The concrete cached-backend proposal
is in #108; no existing backend account has been identified. #109 records both
the review-funnel audit and risk-sizing sensitivity: the only whole-share-feasible
pre-review A+ at the baseline was already reviewed and downgraded, and raising
base risk to 1% still yields no reaction candidate passing retained review and
regime gates. The separate 2% anticipation sizing experiment is outside the
archived risk band and is not a deployed recommendation or observed outcome.
#110 now has a practical owner walkthrough and explicit personal-sizing and
actual-fill/P&L gaps. The next expected stock open is October 12 at 8:30 Chicago;
banking calendars differ that day, so cash still comes from the broker.
Broker identity, pre-open operational acceptance, actual fills and the first
successful trade remain outstanding. Continue from these gaps; do not mark the
whole goal or milestone 2 complete.

## Checkpoint, 10 Oct 2026 — consistent ticket and workflow status (local)

**Executed defect.** The October 9 publication at `62bce72d` admits one ZIM
anticipation ticket for October 12. At phone and desktop sizes, the morning
desk counted it while `nextActionCore()` counted bursts alone: it offered no
next step for the coil and said nothing had been offered once the window ended.
The same contradiction occurs with the pipeline-generated `notrade` fixture.
The optional stale-page run log also called an already-published, skipped
scheduled attempt “tonight’s run: completed.” Its success was workflow evidence,
not a new publication.

**Correction.** The next-action message reads both existing model ticket counts,
preserving publication, market and clock refusal precedence. Zero-ticket wording
covers both setup families, and cutoff retains the published ticket count as
history. The optional run log names the latest evening workflow, includes its
exchange-local date, distinguishes cancellation/skipping from failure, and says
successful workflows can skip publication. It makes no new data or delivery
claim. No strategy number, ticket, source record, provider request or workflow
changed; `.env.example` was reviewed and needs no new setting.

**Local evidence.** The new `status` browser suite plus `full`, `degraded` and
`notrade` pass 1,424 checks. Independent review passed all 106 status checks.
Docs/secret tests pass 92. Isolated burst-only and false-publication-claim
mutations fail their intended assertions (92/106 and 94/106); an unrelated
coil-sorting mutation still passes 106/106. Exact current publication bytes
were also replayed at 1280 and 390 pixels with explicitly pinned pre-open, open,
cutoff and stale clocks; before/after screenshots were inspected. This local
browser work does not establish future pre-open delivery or a live trade.
Runtime: Node 24.19.0, Playwright Chromium 151, Python 3.12.14.
Hosted and public acceptance remain the release owner's next steps.

## Checkpoint, 10 Oct 2026 — personal cash preview ready for release

Mo expanded the operating contract to continued milestone releases until
manually stopped. `PRODUCT_GOAL.md` records that contract; the hourly ChatGPT
continuation task resumes work but is not an uninterrupted process. Both
repositories remain connected, and the pinned design-system assets are reused.

The morning desk now offers a separate, tab-local preview of one admitted
published plan using entered settled cash, an explicit fees buffer and optional
smaller whole-share quantity. Integer-cent arithmetic caps at both published
quantity and cash affordable at the limit. It shows principal, fees, total
cash, limit-to-stop risk and cash remaining. Published order copying retains
the original quantity and says so beside the preview. Nothing reserves cash,
submits an order or reads a broker balance. Invalid or unknown inputs, zero
affordability, incompatible account assumptions, fixture publications, entry-window expiry
and event refusal cannot produce a current preview. Inputs are reconsidered
against the current clock and publication; session changes clear settled cash.

The asynchronous observations callback now checks that the application is
still mounted. The prior teardown exception was reproduced on unchanged main;
a held-crypto teardown control passes and deleting the guard restores failure.

Executed local evidence: 534 morning/cash browser assertions, 137 continuity
assertions, seven producer-fixture tests and six reproduced fixture files.
Independent review passed 421 browser assertions and 10,014 arithmetic cases,
and inspected phone/desktop captures. Quantity, fees, event, account and cutoff
mutations fail their intended controls; an unrelated maximum-share mutation
passes. The publisher inventory includes all 29 files, including the new
`app-cash-preview.js`. After incorporating the ZIM registry and narrow scanner
correction, 44 documentation/fixture tests pass and collection finds 3,383
Python tests. Runtime: Python 3.12.14 and Node 24.19.0. `.env.example` documents
that this calculation needs no broker credential or new environment variable.

Hosted checks and actual public acceptance remain outstanding. The original
October 9 ZIM ticket must be superseded through normal production after PR #115;
its retained model history must not be erased. No actual fill or successful
trade has been reported by Mo.

## Checkpoint, 10 Oct 2026 — enforce cash-fixture integrity (PR #119)

Independent review found that the cash-preview generator and publication test
called `provenance.verify()` without checking its returned status. Both now
require PASS with `require_sources=False`. The generator's temporary source
objects are not retained, so this checks publication integrity and compatible
rule replay; it does not claim a retained-source audit.

The new regression runs the real offline producer, changes only a candidate's
recorded review-selection decision, and requires the generator to reject the
evidence mismatch. In an isolated copy, deleting only the new assertion makes
that regression fail with a missing rejection; changing unrelated archive
capacity keeps it passing. All six cash-preview fixture files reproduce their
existing bytes. Collection now finds 3,424 Python tests.

The preceding independent selector review passed 156 targeted Python and 427
browser checks, with phone and desktop explanations inspected. This follow-up
changes test enforcement only; it does not change an application asset,
published plan, fixture JSON, strategy rule or source record. README and
`.env.example` need no factual change for this test-only correction. Hosted
checks and public acceptance remain the release owner's responsibility.

## Checkpoint, 10 Oct 2026 — bounded SEC evidence ready for hosted review

Issue #118 adds an optional Morning desk source reader for admitted plans and
known-event-excluded candidates. It binds a small receipt and digest-named
bundle to the exact canonical record, compact reader and candidate plans.
The SEC-only collector cross-checks ticker/CIK identity, records separate
filing, acceptance and retrieval clocks, and retains incomplete excerpts with
raw and displayed-text digests. A recent filing sample never clears a known
event or the unchecked future earnings calendar. ZIM's original merger anchor
survives newer filings, source outages and omitted collection.

Collection is bounded by source paths, request spacing, requests, response
bytes, aggregate network bytes, distinct captured bytes and an absolute request
deadline within the run budget. Verified cache reuse preserves the last network
clock. Main-only workflow guards serialize at most three production starts per
UTC day, including failed attempts and reruns. The collector has a read-only
token; a separate publisher revalidates current main, canonical bytes and the
previous receipt before writing only its owned receipt, immutable bundle and
retention manifest. Superseded bundles have a 21-day elapsed-time grace period;
unknown files remain untouched. Older valid evidence cannot attach to another
scan and does not block an evening publication.

After integration with the exact PR #119 ancestry, 12 issuer producer fixtures
reproduce and 203 focused collector/source/publisher/workflow Python checks
pass. The combined issuer, cash, morning, status, review-selection, session and
refresh browser checks pass 1,054/1,054. Phone and desktop screenshots were
inspected. Independent issuer review passed 220 checks plus real-producer
inapplicable and long-excerpt controls; a 3,677-pixel phone overflow was
reproduced and corrected to the 352-pixel dialog width. Continuity passed 137
checks. Source, raw-byte digest, publication binding, cache clock, publisher
race, retention and layout mutations fail their intended controls, with
unrelated controls passing. Absolute transport deadlines were exercised with
an actually blocked transport, not inferred from timeout configuration.

Generated publication/reader fixtures carry the same three public numeric rule
identifiers as existing fixtures. The scanner disposition requires one of
those exact values AND one of the two exact new paths; default detectors remain
enabled. All 76 real-engine controls pass on each of pinned gitleaks 8.24.3 and
current 8.30.1. No producer or captured source bytes are rewritten for scanning.
Collection finds 3,577 Python tests. Runtime: Python 3.12.14 and Node 24.19.0.
README and `.env.example` describe the source bounds, retention and absence of
new credentials. Hosted gates and actual main/public-site acceptance remain
outstanding; these offline checks do not establish live filing coverage,
morning delivery or a successful trade.

## Checkpoint, 10 Oct 2026 — private broker handoff ready for hosted review

Issue #120 closes the gap between a smaller personal cash preview and the
unchanged original ticket. An explicitly saved, browser-local draft carries
the chosen whole-share quantity, exact publication and plan identities,
unchanged levels, dated exit instructions and a separate broker readback.
Current publication, cash, account, event and entry-window guards apply to new
drafts and copying. Manual reports remain correctable after expiry or a known
event; reported facts do not authorize another entry.

The owner reports cumulative submitted, filled, cancelled, exited and
protective quantities with explicit-offset event times. Remaining holdings
are calculated only when both filled and exited quantities are known;
explicit zero exits differs from unknown. Protection is compared with those
remaining reported holdings, not cumulative entry fills. Clearing a report to
unknown cannot revive its entry copy. There is no broker submission,
observation of fills, account balance inference or realized-P&L calculation.

Private storage is bounded to 100 items and 1 MiB with serialized,
revision-checked writes. Unknown or corrupt storage remains untouched.
Readback and rollback faults retain exact prior/proposed recovery data.
Preparing another setup and delayed save completion preserve unsaved edits.
Explicit draft creation persists the entered cash and fee buffer locally;
the unsaved cash preview remains tab-local. README and `.env.example` state
these distinctions and the absence of new credentials.

Independent execution passed 161 browser checks, 19 named model controls and
36 additional workflow controls, including actual double storage faults.
Two reproduced defects were corrected and rechecked: clearing all reported
fields had revived entry copying, and switching drafts had discarded unsaved
edits. Five model and two UI mutations fail the intended controls while
unrelated controls pass. CI directly executes the named model runner.

After merging the exact PR #121 issuer ancestry, combined handoff, issuer,
cash, morning, status, review-selection, session and refresh checks pass
1,215/1,215; phone and desktop screenshots were inspected. Focused Python
checks pass 274/274, continuity passes 137/137, all six cash and twelve issuer
producer fixtures reproduce, and actionlint passes. The 31-commit PR range
has no gitleaks findings. Collection remains 3,577 Python tests; local runtime
is Python 3.12.14 and Node 24.19.0. Hosted exact-head gates and actual public
acceptance remain outstanding. All fill examples are synthetic; no real fill,
exit, profit or successful trade is established by this release work.

## Checkpoint, 10 Oct 2026 — byte verification integrated with the morning desk

The original-byte fix from issue #122 now includes the exact PR #123 ancestry,
including private broker reports and issuer evidence. Both initial load and
refresh still pass bounded original bytes to morning observation binding.
The merged DOM harness uses real streamed Responses and includes all three
new desk modules. No canonical publication, compact reader, morning receipt,
retained research, history, evidence or producer fixture changed relative to
that ancestry.

The combined reader, refresh, handoff, issuer, cash, morning, status,
review-selection, observations and session browser checks pass 1,488/1,488.
Phone and desktop reader captures were inspected. Focused Python checks pass
287/287, named handoff model controls pass 19/19 and continuity passes 137/137.
The 33-commit integrated PR range passes gitleaks. The independent byte review
passed 165/165 and confirmed early-refusal cancellation and the existing
deferred-read timeout with a stalled response. Initial-load and refresh
deadlines remain an inherited limitation. These checks establish local
integration; hosted exact-head gates and actual public acceptance remain open.

## Checkpoint, 10 Oct 2026 — ZIM correction accepted on the public site

PR #115 passed exact-head hosted acceptance at
`41d250c43225dd6f517e10199cf98b3f46038e0e` and merged as
`21cd3497cd7ee06c66e4c2b46dcbed4782a7213e`. Production evening run
`38033614291`, explicitly measured on October 9 with email skipped, published
`dcb12a0b20f2d41900c4235c30efa76a40285c0b` for the October 12 session.
[The compact release receipt](release-evidence/2026-10-10-zim/acceptance.json)
retains these identities, exact canonical/reader/sidecar digests, the 31-file
public hash inventory, source-receipt digests and primary-source manifest link.

Hosted run `38030547868` passed 3,376 Python tests, 11,204 page checks and 378
chart checks; both native central and stress jobs passed. Native artifact
digests are those reported in the official job evidence, not a claim that the
artifact bodies were independently downloaded. Public acceptance on the live
site passed 135 checks at 1280 and 390 pixels with no route, data or clock
overrides and no browser errors. Six screenshots were inspected. While writing
this checkpoint, all 31 recorded public hashes were independently matched to
the designated production Git tree, and all 17,415 baseline immutable
evidence/history blobs were compared byte-for-byte through their Git identities.
Production provenance passes for 484 setups, with no breaks or missing sources.

The actual current ZIM candidate is present and refused for the pending cash
acquisition, with dated source links and no executable order. Its original
two-share model pick remains historical research. There are zero admitted
tickets and zero new commitment. The $188.37 reserved for unfinished SN model
plans does not establish Mo's holdings, balance or settled cash. All 12 requested
reviews completed, but 467 of 479 discovered reaction candidates were not
selected; this is not full opportunity or event coverage. Of 4,775 intended
stocks, 4,774 have usable session bars; WBD's stale input remains unknown under
the recorded tolerance.

The retained morning receipt was generated on October 9 for an older
publication and is correctly unavailable for this new record. This rerun and
public review establish neither on-time morning quotes nor a successful trade.
The public commit also predates the separate status fix: its old banner still
says October 9 was closed despite the recorded session being open. The cash
preview, status, SEC evidence, handoff, original-byte reader and reported-result
changes being integrated separately are not claimed released by this receipt.
Earlier pending-ZIM statements describe their checkpoint date and are
superseded by this recorded production acceptance.

## Checkpoint, 10 Oct 2026 — reported completed results ready for hosted review

Issue #124 adds actual average exit price and separately entered entry/exit
fees to the private handoff. Model commit
`9fab47657755d3e8ac1ce5a33ca3bb98af252f74` and UI commit
`4f8a9a579aaeaef97ed0568cdcfb3cce3be897c4` are integrated in this branch.
Reported gross, costs and net require positive filled quantity fully exited,
filled plus explicit cancelled quantity equal to submitted quantity, both
average prices, both actual costs and latest fill/exit timestamps. Submission
and cancellation timestamps remain optional. Partial exits have no inferred
cost basis; missing costs are unknown, while an explicit zero is accepted.

BigInt arithmetic preserves six-decimal prices and cent fees; rounding occurs
only for display. Gain/loss/breakeven uses the exact unrounded result, with a
visible sub-cent gain or loss instead of a misleading $0.00. Actual reported
costs remain separate from the draft fee buffer. Corrections remain available
after entry expiry or events, and cannot revive entry copying. Results do not
change original plans, model scorecards, cash allocation or goal completion.

Strict v1 records normalize to unknown new fields in memory without any write
on read. An explicit successful save writes v2 under the existing private key;
identities and untouched facts retain their meaning. Unknown, mixed or future
schemas remain untouched. Quota/readback failures retain exact prior/proposed
recovery; migration cannot exceed the 1 MiB cap or evict another record.

All 31 named model controls pass. Six isolated model mutations fail their named
rules while unrelated controls pass. The handoff browser suite passes 219
checks and the handoff/cash/morning compatibility run passes 753; phone and
desktop screenshots were inspected. Independent review passes 194 additional
browser assertions against 40 Python Decimal oracle cases, including genuine
original-v1 producer records, no-write reads, explicit upgrades, recovery and
revision conflicts. UI net-versus-gross and stale-result mutations fail their
intended checks, with unrelated wording still passing. README and
`.env.example` describe the private schema and absence of new credentials.
These are synthetic local rehearsals. Hosted exact-head gates and actual
public acceptance remain outstanding; no real entry, exit or profit is claimed.

The combined branch also corrects the two executed walkthrough failures from
PR #123 and PR #125. A delayed hosted runner could observe a valid later
playback step instead of the synchronous restart; the test now captures the
transient state inside its browser event task, then separately verifies
advancement. The intentional missing-publication response is required to be
HTTP 404 before its exact request cancellation is accepted. Other errors stay
failures. Independent baseline checks pass 109/109 (110 with screenshots),
delayed observations pass, deleting restart fails, and HTTP 500 plus unrelated
404/cancellation controls fail. Application behavior and required gates did
not change. Those failed prior runs are superseded, not called passing.

PR #121 is merged at `ef9f150d64e47e0241c58d749ff1bc27f17d8a86`, incorporating
#116, #117 and #119 by ancestry. Exact head
`c0cc1720a5655561c1752837aa7dbded3c9a1611` passed all seven hosted checks:
3,577 Python tests, 11,761 page checks, 378 chart and 137 continuity checks,
both native recovery jobs and both secret scans. Its actual production
acceptance is in progress. The live SEC rehearsal `38034513636` completed
with an honest unavailable result: the ticker-mapping request returned an
HTTP error, two selected issuers were unverified, and no fresh filing bytes
were retrieved. Existing event anchors remain retained. This is not live
filing-coverage acceptance. Evening `38034610157` will verify the new review
selector and trigger the bounded production collector. Continue by verifying
that real publication, then the combined private-result release; on-time
quotes, broader event/earnings coverage and an actual owner trade remain open.

## Issuer parent workflow identity correction — 10 October 2026

The first automatic issuer run, `38034801783`, refused its successful evening
parent `38034610157` as `unknown_parent`. GitHub supplied the dynamic run name
`Evening backfill 2026-10-09`, while the guard expected the workflow's static
title. The actual parent metadata and current publication reproduced the refusal
offline. The corrected guard identifies only the exact workflow paths
`.github/workflows/evening.yml` and `.github/workflows/morning.yml`. It still
requires the same repository, completed main parent, current publication or
morning binding, and bounded daily collection history. Friendly display names
cannot authorize missing, unknown or lookalike paths. Publisher recursion is
still refused; no schedule, permission, source request or daily limit changed.

The publisher, dashboard and workflow suites pass 137 checks, including 30 new
path and parent-trust cases. Six isolated mutants fail for the intended dynamic
name, friendly-name bypass, suffix-path bypass, repository, current-publication
binding and daily-limit defects; an unrelated retention-cap mutant passes all
33 targeted guard controls. The docs/scanner suite passes 116 checks and
actionlint passes for the issuer, dashboard publisher and test workflows.
Collection finds 3,607 Python tests. Runtime is Python 3.12.14.
The other workflow guards were searched for display-name identity
comparisons; no additional instance was found. README was clarified and
`.env.example` remains accurate with no new variables or credentials.

This correction has not yet passed hosted CI or an actual automatic production
collection. The earlier SEC rehearsal truthfully reported unavailable source
coverage after an HTTP failure; fixing the trigger does not establish SEC
availability, event clearance or trading permission. Canonical publications,
immutable evidence and model history were not edited.

## Checkpoint, 10 Oct 2026 — cash preview and issuer reader accepted on production

PR #121 merged as `ef9f150d64e47e0241c58d749ff1bc27f17d8a86`, including
#116, #117 and #119. Exact reviewed head
`c0cc1720a5655561c1752837aa7dbded3c9a1611` passed all seven hosted gates:
3,577 Python tests, 11,761 page checks, 378 chart checks, both native recovery
jobs and both secret scans; continuity passed 137 assertions.
[The scoped release receipt](release-evidence/2026-10-10-cash-issuer/acceptance.json)
retains run links, exact identities, public file hashes and remaining defects.

Actual evening run `38034610157` measured October 9 with email skipped and
published `43dcb8d7c6eb0d63c1825198aa161fc4d4caec80`. The archived
account-feasible-first policy found no feasible pre-review reaction candidates:
all 479 failed the yellow regime's grade gate before a private sizing preview;
185 also had a quality veto. Zero later-stage blocker counts do not establish
whole-share feasibility or event clearance. BIIB and NTAP used the two research
slots and both reviews completed; ten reads remained unused. Their final grades
were B and C, with no tickets. This is an observed execution, not a controlled
cost-saving or performance estimate. Full source provenance passes 484 setups;
all 18,087 prior immutable evidence/history objects remain unchanged, with 496
new objects retained. SN's $188.37 model reservation is not Mo's balance.

The automatic issuer child `38034801783` skipped with `unknown_parent`: it
compared the dynamic parent run title to a fixed label. Issue #128 / PR #129
track the exact-workflow-path correction. The separately dispatched production
collection `38034924561` succeeded and persisted
`981e6792827a222c26b94da622f30d88b74d53e1`; publisher `38034993443` and Pages
`38035005959` passed. Its receipt honestly reports unavailable: one SEC ticker
identity request failed, with no downloaded or captured bytes. MG and ZIM keep
their dated event anchors. Fresh issuer news is not cleared and future earnings
remain unchecked. Manual publication does not verify the automatic trigger.

The actual public site passed 187 checks over 27 exact files at 1280 and 390
pixels, with no route/data/clock overrides or browser errors. Fourteen screenshots
were inspected; the cash test used only an ephemeral synthetic input in a fresh
browser context. The preview correctly refused the zero-ticket publication,
preserved its entered value/focus, and the issuer reader matched the exact
canonical record, compact reader and immutable bundle. All 27 public hashes were
also independently matched to the designated production Git tree.

Screenshot review found a separate sentence attributing Saturday's closure to
the measured Friday; issue #131 tracks that correction. This scoped receipt
does not accept that sentence, automatic collection, fresh SEC coverage, on-time
morning delivery or a successful personal trade. Continue with those concrete
gaps and the private-report/recovery releases; do not infer goal completion.

## Checkpoint, 10 Oct 2026 — bounded publication recovery and truthful closed-day guidance

Issue #127 bounds both startup and manual refresh to 15 seconds across response
headers and the complete original-byte read. A new attempt aborts its predecessor;
late success or failure cannot overwrite the latest attempt. Failed startup
exposes an explicit Retry and clears partial local/exported publication state,
including navigation and the chooser. A failed refresh retains the displayed
record. The Morning desk mounts before loading so private saved reports remain
readable and correctable without a current publication. Missing publication
cannot prepare or copy a new entry. Retry preserves editor identity, unsaved
values, focus/caret, storage bytes and an explicit pending save; it does not
write or migrate private data automatically.

Owned implementation `4a1ed0ec62c59fe350326ebfa3934bb268b21fd9` passes 131
recovery and 1,836 compatibility browser checks, 44 focused Python tests,
31 handoff model controls and 137 continuity assertions. Five isolated guard
removals fail the intended timeout, latest-attempt, cancellation, initial-failure
and partial-model cleanup controls; an unrelated tooltip change passes all 131.
Independent review passed 191 transport/private-state checks, 59 late-response
controls and 56 final cleanup checks. Actual blocked header and body sockets
were cancelled at the 15-second deadline. Phone/desktop captures were inspected.
These tests use explicit local fixtures and synthetic private reports.

Issue #131 corrects the actual public next-step sentence that called measured
Friday October 9 sessionless when viewed Saturday. The closed state now reuses
its existing calendar sentence, naming the closed viewing date and recorded
next applicable session. It changes no status classification or entry authority.
Owned correction `76e004c1d10ecee893ce6a0735a4d570a09c4fa5` passes 707
status/closed/session checks after 12 intended pre-fix failures; an unrelated
headline mutation passes all 130 status checks. Independent review passes those
130 checks plus 22 over the actual publication bytes with an explicitly pinned
Saturday clock. Friday remains open and Monday October 12 remains the recorded
next session. No historical publication or plan is rewritten.

The combined branch incorporates the exact PR #126 and #129 heads plus actual
production `981e6792827a222c26b94da622f30d88b74d53e1`. README and
`.env.example` now describe bounded retry and private access without new
credentials or settings. The pinned design system is unchanged. Runtime is
Python 3.12.14 and Node 24.19.0. Integration checks, hosted exact-head gates and
actual public acceptance are recorded below when executed; these local checks
do not establish on-time provider delivery or a personal trade.

After integration, 380 recovery/status/refresh/reader browser checks and 143
focused documentation/reader/issuer-publisher Python tests pass. Collection
finds 3,607 Python tests. Integrated application bytes equal the independently
reviewed recovery source plus the single reviewed calendar sentence; the other
owned recovery modules match exactly. Current production data, compact reader,
morning receipt, immutable evidence/history and design-system files match
`981e6792` byte-for-byte. Integrated timeout/private-report screenshots were
inspected. Staged documentation and receipt scan clean with gitleaks 8.30.1.
