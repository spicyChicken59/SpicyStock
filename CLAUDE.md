# SpicyStock — working notes

**Active goal (updated 17 October 2026):** [PRODUCT_GOAL.md](PRODUCT_GOAL.md) is the
current product direction and milestone contract. Mo uses a $2,000 cash
account and America/Chicago time; the broker is Fidelity (17 October 2026,
`knowledge/broker-fidelity.md`). New production
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
the minute bars of earlier plans' first days a daily bar could not place
(`run.intraday`, `src/intraday.py`; every walk below reads them) →
charts and Claude (down-only; `run.reads` by cause) → plans and the cash
budget → the record (`picks.json`, open plans, scorecard, and the stale
frames joined to the universe's seed-only additions: `run.seed_stale`,
`inputs.seed_stale()`, the names on the seed alone or the one reason the join
could not be made) → `report.build()`
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
newest record and did the run finish -- and when the newest expected session
has no record yet, pending against stale is the service's own recovery window
read off the record (the next session's open on `run.calendar`; the slot the
ET clock has passed in the words `run.delivery` archived, `src/delivery.py`),
never a fixed hour on the page. `run.timing` (`src/timing.py`, written
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

The suite now collects 5620 tests, the chart check remains separate, and the page smoke walks twelve fixtures. Historical measurement: 1107 tests, the chart check, and the page smoke
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

## Checkpoint, 10 Oct 2026 — registered stop-width research ready for hosted review

Issue #130 adds the optional Morning desk comparison
`anticipation_stop_width_4_to_5_v1` for applicable sessions October 12 through
November 6. It changes one explicit pure-helper input for anticipation research:
a 5% cap versus the unchanged 4% production wrapper. The $2,000 / 0.5% account,
25% position cap, four slots, trigger, limit, structural stop, risk reductions,
market/watchlist/event checks and whole-share sizing remain the baseline.
Production reaction-stop geometry and archived numeric rules are unchanged.

The producer retains every original top anticipation row, including exclusions,
zero shares, empty cohorts and outside-period status. Existing baseline tickets
and unfinished model reservations consume resources before research; research
cannot displace a lower-ranked baseline trade. Exact canonical/reader/rules,
plan/input/source identities bind the comparison to verified retained evidence.
Generation uses actual UTC time, classifies before/during/after entry, and never
uses an old run-start stamp to claim prospective capture. An exact-publication
repeat or revisit preserves its first cohort and generation clock. The bounded
append-only index refuses overflow or invalid evidence without pruning records.

The optional producer runs after final evening canonical/reader writes on both
delivery paths. Its failure does not restamp or degrade the authoritative record.
The existing publisher validates any present receipt and its referenced bundle;
an older valid receipt may remain but cannot attach to a new record. Source and
reader loads are deferred until the disclosure opens. The panel shows baseline
refusals, unchanged levels, hypothetical sizing, risk reductions, allocation and
coverage limits; it adds no research order-copy, private draft or execution path.
Elapsed entry windows are labelled archived. Private cash/report inputs remain
independent. No provider/model calls, credentials or settings are added.

Implementation commits: publication hooks `3122067f`, producer `6fd884a1`, UI
`081e58a9`, browser controls `50e070ca`. Producer verification passes 41 focused
and 123 planner tests; 22 generated artifacts reproduce. Independent review
passes 57 additional checks, 288 comparisons against the prior production
planner, 42 backend/publication tests and five final clock-input controls.
Seven isolated backend mutations fail cap/risk/baseline/event/clock/retention/
binding controls; an unrelated change passes. UI checks pass 332 assertions,
with five validation mutants rejected and an unrelated timeout control passing;
all 12 phone/desktop dark/light screenshots were inspected. Existing browser
compatibility passes 1,019 checks, continuity 137 and geometry four.

After merging exact recovery/calendar head `d7e33174`, the combined Morning,
cash, handoff, issuer, research, recovery, refresh and status checks pass 1,613.
The fixture command inventory is extended to require the new generator in CI;
removing that command fails its intended assertion, while an unrelated workflow
timeout change passes. Source, immutable fixtures and strategy policy were not
relaxed to satisfy that guard. Collection finds 3,664 Python tests. README and
`.env.example` document the optional producer, public retained cohorts, bounds,
registered dates and absence of new credentials. Runtime is Python 3.12.14 and
Node 24.19.0. Actual public acceptance remains pending.

Both pinned and current engines scan the producer commit without findings.
The separately decompressed fixture scan has 60 pinned-engine detections, all
exact previously classified public numeric-rule identifiers, with zero unknown
values; it is not a zero-findings scan. The current engine finds zero on those
raw bytes. Independent decompression/digest comparison confirms all ten raw
canonical/reader files match the scanned originals. No source bytes or scanner
rules were changed to hide a finding.

The first actual comparison was derived locally at
`2026-10-10T08:11:55.173159+00:00` from the exact retained production
publication `43dcb8d7` (canonical `f5cbe38e…`, reader `f9282e90…`). Full source
and picks validation passed; no new scan, model call or provider request was made.
The receipt is 1,650 bytes (SHA-256 `98cc1b85b04aa3b570c777576d7d49f55edfe2bab5fe4e804362c5be7e2eeb22`);
its 8,918-byte immutable bundle is
`249b60c01b702eabc05bba17b0160c7664177e34cfdf26e217c5dbbd1db788f0`. This is pre-entry capture for October 12,
not a claim of an on-time live quote or a trade. All original data, reader,
picks, morning/issuer receipts, history and evidence remain unchanged.

All five top rows are retained. Three fall within the 4–5% band; two fit the
unchanged effective $2.50 risk budget: KE one share at the fixed $29.52 limit,
$1.27 price-to-stop risk; PSNL three at $16.42, $49.26 principal and $2.22 risk.
Total hypothetical principal is $78.78 and price-to-stop risk $3.49. SN remains
zero-share and occupies a model slot; its $188.37 model reserve is not Mo's
holding or settled cash. MG/ZIM retain their event exclusions. Fees, gaps,
slippage, current quotes and broad news/earnings clearance are not supplied by
this derivation. The companion is prepared in this branch, not yet deployed;
there is no reported personal execution or result.

Final documentation/publisher verification passes 74 tests over the prepared
actual companion; all 49 workflow checks pass with the extended fixture-command
inventory. The 22 producer fixtures remain current. The new generator-command
removal is detected, while its unrelated timeout control passes. Integrated
phone/desktop research captures were inspected. The prepared files enter the
existing required exact-head hosted gates before any merge or public claim.

## Checkpoint, 10 Oct 2026 — bounded issuer HTTP diagnostics ready for hosted review

Issue #133 retains an observed HTTP response status and a fixed source phase
beside the original requested SEC URL. The optional pair is backward compatible:
legacy errors and failures without a response retain unknown status. Strict
status/code/phase and current CIK/selected-accession checks apply in both the
stdlib validator and browser. Mapping, submissions, history, primary reports
and exhibits remain distinct. Diagnostic fields contain no response bodies,
headers, redirect destinations or exception text. Coverage, provider identity,
request/download/cache bounds, retry policy and trading authority are unchanged.

A bounded environment-only mapping probe at 08:02:15 UTC returned HTTP 200 and
524,131 bytes (SHA-256
`33b3998934205f0ce54c874470a41689ea5aaaba7d04c909f20976eb3e551ba4`).
This does not explain or overwrite the earlier Actions receipt's generic HTTP
failure. The next actual collection can now identify its observed status and
phase without guessing. No new production collection was used for this change.

Independent review found and reproduced two new browser filename-boundary gaps;
primary and exhibit diagnostics now use the collector's bounded safe basename.
A reproduced existing urllib redirect-response leak is also fixed: all five
supported redirect statuses close the original response without reading or
following it, including when close itself raises. The refusal status, one
attempted request and zero downloaded bytes remain accurate.

Owned commits are backend `933f896d`, UI `7c6b6665` / `346254b7`, and redirect
cleanup `9989ea6c`. Owner validation passes 303 focused Python checks and 358
browser checks; all 14 producer outputs reproduce and all 13 existing fixture
JSON files retain their bytes. Independent validation passes 166 Python, 358
browser and ten actual stdlib redirect-dispatch controls. Seven backend
mutations fail their intended checks with an unrelated 70-check control passing;
primary/exhibit browser guard removal fails six targeted cases each, while an
unrelated control passes all 358. Phone and desktop screenshots were inspected.

The diagnostics branch incorporates exact reviewed research/recovery head
`49d96480` without conflicts. Python 3.12.14 collects 3,734 tests. README and
`.env.example` now explain observed/unknown status and the absence of new
credentials/settings. Existing production artifacts and the pinned design
system remain unchanged by these diagnostics. Integrated checks, required
hosted exact-head gates and actual public acceptance are still pending; local
HTTP success does not establish Actions access or fresh news coverage.

Integrated verification passes 397 focused Python checks and 1,751 browser
checks across issuer diagnostics, cash preview, private handoff/results,
registered research, publication recovery, status, morning and refresh. All
14 issuer and 22 research fixture outputs remain current. Integrated phone
and desktop diagnostic captures were inspected. The 28-commit range scans
clean with gitleaks 8.30.1. The final independent research review also approved
`49d96480`: 332 browser, 54 clock/private-continuity and 52 HTTP integration
checks, plus exact production-companion validation/replay with sockets denied
and independent Decimal sizing. Those are local review results, not a public
release or a reported personal trade.

## Checkpoint, 10 Oct 2026 — personal trade reports accepted on production

PR #126 merged exact reviewed head `6a505ffd` as `9edab25c` at 08:28:26 UTC.
Its 3,577 Python, 12,014 page, 378 chart and 137 continuity checks passed;
13 page, 21 morning and 12 issuer fixture files reproduced. All seven required
checks were green, including both native runtime cases and both secret scans.
Two independent reviewers confirmed the final receipt-only correction against
actual run `38033614291`: final A=41 and A+=0, rather than its mechanical A=53.
The eight previously reviewed application hashes were unchanged by that delta.

Publisher `38037996469` and replacement Pages deployment `38038008362` passed
for `9edab25c`; initial Pages run `38037996293` was cancelled, not passed.
Actual public acceptance passed 56 checks and matched 32 native original-byte
files against this exact commit, using the real clock/default loader in fresh
390px light and 1280px dark browsers. Cash remained unknown and private history
empty, with no horizontal overflow, application/transport errors or invented
entry. Seven scoped screenshots were inspected. A separate synthetic private
rehearsal passed 17 controls for v1 read without save, explicit v2 correction,
net gain $3.65, net loss -$1.85, and an unknown exit fee hiding all result amounts.
No request carried those corrections; these were test facts, not Mo's trades.

The scoped receipt is
`release-evidence/2026-10-10-personal-results/acceptance.json`. A second local
check matched all 32 public hashes to Git and confirmed all 18,584 retained
history/evidence files, canonical/reader/picks and design-system bytes unchanged
from `981e6792`. The published historical morning receipt remains unavailable
for the newer source publication. The old closed-session sentence still names
the measured Friday when viewed on Saturday; PR #132 contains its reviewed fix.
On-time quotes, current issuer-news/earnings clearance, broker-specific terms
and any actual successful trade remain open.

PR #129 head `639dff8b` also passed all seven checks, including 3,607 Python,
11,761 page, 378 chart and 137 continuity controls. After #126 merged, #129
conflicted with main. Its reviewed source is already integrated into exact
PR #132 head `d7e33174`, which is mergeable and has passed Python/page/secrets
but still awaits its native gates. Ship that existing integration when all its
checks pass, then verify one actual off-hours morning publication and automatic
issuer collection. No conflicting head was merged or gate bypassed. Only one
of the three daily production issuer starts has been used at this checkpoint.

## Checkpoint, 10 Oct 2026 — whole-share personal exit reference prepared

Issue #137 was reproduced over a genuine producer cash fixture: a personal
one-share draft retained the four-share model's literal "sell half" schedule
with no personal quantity explanation. The schedule now explicitly says it is
archived model wording. A derived whole-share reference applies the existing
`plan.follow()` at-least-half convention: one of one, two of three. It is
reference arithmetic, never a decision that an exit is due or a claim that a
broker supports fractional shares. Prior exits need review before acting.

Before reporting, the reference names the personal draft. After any report it
uses only remaining holdings derived from both reported entry fills and exits;
unknown quantities stay unknown and zero remaining shares leaves the schedule
as history. The original schedule, published plan, saved storage schema,
entry/copy guards and personal facts remain unchanged. The explanation also
travels with the clipboard readback. There is no broker connection or new
provider/configuration requirement.

All 34 model controls pass, including three added controls that fail against
the original module. Three isolated semantic mutations (round down, infer draft
holdings, discard reported exits) each fail two targeted cases. An unrelated
storage-capacity change passes all three new controls; the existing capacity
test correctly rejects it when the full suite is run. Integrated browser
acceptance passes 674 cash/handoff/recovery checks and 37 documentation checks
pass. Phone/desktop captures were inspected. Independent verification adds 20
controls against actual Python `plan.follow()` whole-share sales and 269 browser
checks. The final precision edit "in whole shares" passes 34 model checks and
eight additional independent phone checks; its source delta contains only those
words. No production release of this exit-reference change is claimed yet.

## Checkpoint, 10 Oct 2026 — frozen research follow-through prepared

Issue #136 adds `anticipation_stop_width_follow_through_v1`, a dated journal of
all original registered wider-stop cohorts. It reuses retained observations;
no new market-data/model calls, private reports or account credentials enter
its producer. Every original exclusion, quantity, level, source identity and
actual capture time remains frozen. The first before-entry cohort per applicable
session is primary; later revisions and late captures remain visible. Only
original allocated research rows are replayed with their original whole shares.

The existing daily-bar fill/follow/R model remains conditional. Pending,
missing, uncertain, not-filled, open, resolved and unsupported-source states
remain distinct. Missing observations are not zero returns. Only a reconciled
resolved model receives an R result; there is no aggregate performance, win
rate or cross-night portfolio simulation. Actual execution, fees and slippage
remain unspecified. Known event exclusions and production tickets are unchanged.

Observation identity includes its containing publication, provider/feed,
adjustment, daily timeframe, source anchor and full OHLCV clip. Public anchor
comparison uses the pipeline's explicit four-decimal price conversion while
preserving the raw anchor and hash. Expected sessions follow the containing
publication's measured completed session, not a later wall clock. A prior
conclusive clip can remain readable under partial later coverage with its old
date and identity; conflicting fresh evidence remains explicit. Full bar
revisions append new snapshots without rewriting old evidence.

The optional hook follows final canonical/reader writes and the stop-comparison
attempt on both delivery paths. Failure preserves the main record and previous
companion. The fixed receipt is bounded to 16 KiB, each immutable bundle to
2 MiB, and the lazy browser read to 15 seconds. The producer bounds 128 cohorts /
640 rows, 16 MiB of cohort inputs, 128 MiB of sequential original-publication
reads and 60 seconds of processing. Its append-only archive allows 128 snapshots /
64 MiB with a 64 KiB index; exhausted or invalid archives refuse without pruning.
An exact publication/cohort revisit preserves its first snapshot and clock.

Independent review found and fixed genuine defects in rounded anchor matching,
missing-session accounting, retention of conclusive old clips under partial
new coverage, and the cached-write deadline. Owner validation passes 54 backend
tests and 40 reproducible fixture files. All twelve isolated mutations fail
their named assertions, with an unrelated seven-test control passing; setup
errors from the first harness attempt were corrected and are not counted.
Independent backend verification passes 44 contract/source/archive controls
and eleven boundary controls in addition to the 54 tests. Publication hooks
pass 117 focused and 112 pipeline/provenance checks; seven isolated mutations
are detected and an unrelated 25-test control passes.

The browser suite passes 324 checks, six targeted mutations and an unrelated
324-check control. The final wording changes only “Model whole-share partial
exit” to “Model whole-share exit”; receipts explicitly reconcile the unchanged
guards from the mutation source with the final source. Compatibility passes
592 checks and 137 DOM/store continuity assertions. Independent review passes
108 private/recovery/carried-source controls plus 41 integrated checks after
merging the exact whole-share-exit head from PR #139. Synthetic 2.26R/-1R and
private dollar results are test fixtures, not actual cohort performance or
Mo's executions. Phone and desktop screenshots were inspected.

Both pinned and current scanners report zero on the committed packed source
and fixtures. On twenty independently decompressed exact Git fixture files,
the pinned engine reports 110 findings, all previously classified public numeric
rule identifiers with zero unknown values; the current engine reports zero.
Raw hashes and all 110 finding coordinates match the original scan. The pinned
raw scan is not described as zero-findings, and no scanner rule or source byte
was changed to conceal a finding.

The first actual snapshot was derived with sockets denied at
`2026-10-10T08:50:21.159749+00:00` from canonical `f5cbe38e…`, reader `f9282e90…`
and original cohort `249b60c0…`. Full source/picks and exact journal replay
validation pass. Receipt `15de998bec9ac4862b1e5b4d480b1a7cd0a69cabbcaab77d24b36e2a7c970db2`
is 2,132 bytes; bundle
`31f3b94cfb219a2fe4a9a779e3f04f352228cedaf5909c8b5a0840aa1a0f1172`
is 17,104 bytes. It preserves all five rows: KE one share and PSNL three shares
are pending for October 12; MG, ZIM and SN remain excluded. There are no later
bars, entries, exits or R results. Canonical, reader, picks, morning/issuer
receipts, original cohort, immutable history/evidence and pinned design system
retain their bytes. This is a prepared companion, not yet a public release.

README and `.env.example` explain the optional journal, exact data boundaries,
retention limits and absence of new configuration. Python 3.12.14 collects
3,813 tests; Node is 24.19.0. The actual first personal successful trade remains
unobserved. Required hosted gates and public acceptance remain outstanding.

Final combined verification passes 314 focused Python checks, 1,767 browser
checks across journal/research/private handoff/cash/recovery/morning/status/
refresh, all 34 handoff model checks, 37 final documentation checks and
workflow lint. All 40 journal and 22 original research fixture files reproduce.
Independent actual-companion replay passes with zero connection attempts;
30 further real-clock phone/desktop checks confirm the prepared pending rows,
unknown personal cash, empty private history and exactly two lazy public reads.
All 19,058 original tracked docs files (191,243,348 bytes) retain their Git
object bytes. These results establish local preparation; hosted and actual
public acceptance will be recorded after the reviewed exact head passes.


## Checkpoint, 10 Oct 2026 — recovery, calendar and automatic issuer delivery released

[PR #132](https://github.com/spicyChicken59/SpicyStock/pull/132) merged the exact
reviewed `d7e33174` head at `01632f44`, including the parent-workflow path fix
from #129. All seven hosted gates passed: 3,607 Python, 12,170 page, 378 chart
and 137 continuity checks; both native memory/runtime jobs and both secret
checks succeeded. Native artifact upload hashes agree with official metadata;
those archive payloads were not independently downloaded. Publisher
`38039203191` and replacement Pages `38039216830` succeeded.

Actual public acceptance matched 32 original served files to the merged commit
and passed 54 real-clock phone/desktop checks. The closed-session sentence now
correctly names Saturday October 10 and Monday October 12. A separate local
rehearsal using the verified public assets passed 89 recovery checks: real
header/body/refresh sockets closed around the 15-second deadline, explicit
Retry recovered, and unsaved private values, focus and original storage bytes
survived faults. These controlled failures are not reported public outages.
All 18,584 immutable history/evidence objects retain their prior bytes.

One authorized production morning dispatch, `38039598040`, published an honest
Saturday `inapplicable / wrong_session` receipt with zero rows and no IEX,
delayed-SIP or halt requests. Its commit `fa480f2a` automatically started issuer
run `38039664597`; the guard correctly admitted `production_collection`. The
issuer collector and persistence succeeded operationally, publishing commit
`3e1dfed6`, but SEC identity retrieval remained unavailable: one request, zero
downloaded/captured bytes, no matched issuer content. This proves automatic
delivery, not fresh SEC coverage or timely morning quotes. The complete-history
quota check records two of three allowed UTC-day production starts used.

The subsequent publisher `38039736422` verified all 34 required public files,
and Pages `38039747189` succeeded. Independent live verification passed 72
checks with 32 native original-byte matches, actual default loading/clock,
unknown settled cash and empty private history. Both MG/ZIM remain excluded
with unverified identity, unknown index coverage and explicit source failure.
A supplementary 40-check phone/desktop run scrolls the source-failure body
into view. Its captures supplement the initial header/age captures. A first
harness assertion wrongly expected the age caption to contain “unavailable”;
that retained failed attempt was corrected to verify age and coverage in their
actual separate fields. No product change or missing check was concealed.

Strict exact-production validation of both companions passes with socket
access denied. The morning receipt SHA is `97c60ab9…`; issuer receipt
`c0d1c97f…` references bundle `c20f9e4d…`. Canonical `f5cbe38e…`, reader
`f9282e90…`, picks, model history and source evidence are unchanged. Full run
identities, hashes, scoped checks and limitations are retained in
[the release receipt](release-evidence/2026-10-10-recovery/acceptance.json).

Next: release the already reviewed registered comparison, HTTP diagnostics,
whole-share personal guidance and dated follow-through after each exact head
passes its required gates. Use at most the remaining daily issuer start for
observed HTTP diagnostics after that code is public. Fresh SEC coverage,
on-time market observations, broker-specific guidance and the first actual
personal trade remain open; no profit or daily-ticket claim is made.


## Checkpoint, 10 Oct 2026 — issuer evidence states reconciled

Issue #138 closes reproducible internally inconsistent issuer states. The
stdlib and browser validators now reconcile identity, index coverage, retrieved
primaries and remaining omissions before accepting a collected label. Unknown
identity cannot claim an observed window. A full metadata window can still be
observed when a later document request fails; the issuer remains partial.
Valid cache, empty-window, partial-history and legacy unknown-status cases
remain readable. This is evidence consistency, not SEC authentication or news
clearance, and changes no collection request, cache policy, trading gate or schema.

Distinct visible network events and explicit HTTP refusals establish only
request/download minima. Shared events copied into issuer rows are counted
once using equivalent UTC instants; distinct body hashes establish captured
byte minima. Cache hits can contribute captured bytes without a new request.
Legacy errors without an HTTP status do not imply an observed response. Counts
can exceed visible minima because attempts and discarded responses remain
possible. Conflicting sizes for the same body digest are refused.

Backend commit `09b12b6b` passes 231 core/source/semantic/publisher/dashboard
checks, including 37 new semantic controls. Thirteen isolated mutations fail
their intended checks; an unrelated control passes all 37. Independent review
passes the 37 tests, 33 further controls, legal producer packets and all seven
coherently resealed contradictions now rejected. The actual latest unavailable
issuer receipt from `3e1dfed6` remains valid with its legacy unknown HTTP status:
one request, zero downloaded/captured bytes. No HTTP 403 is inferred.

Browser test commit `3a6a47e3` and UI commit `48f30d46` pass 476 checks: all
358 prior assertions remain and 118 semantic checks are added. Twelve isolated
guard mutations are detected; an unrelated timeout change passes 118 controls.
Phone/desktop views of a genuine synthetic collector case retain the observed
index beside a primary-document HTTP 403 failure. That fixture response is not
the production SEC result. Eight new producer fixture pairs bring generated
outputs to 30, while all prior 14 generated outputs and 17 tracked fixture JSON
files retain their exact bytes. Packed source and fixture scans pass with both
pinned and current engines without an exception.

README, `.env.example` and the issuer schema document these facts and the
absence of new configuration. Python 3.12.14 collects 3,850 tests; Node is
24.19.0. No new source or provider request is made for this milestone. The
implementation still requires final integrated review, hosted exact-head gates
and actual public acceptance; no new source coverage or trade is claimed.

Final combined documentation/workflow/issuer/publisher verification passes
221 checks. The prepared-source validators also accept the latest actual
unavailable issuer publication without guessing its missing HTTP status.


## Checkpoint, 10 Oct 2026 — registered wider-stop comparison released

[PR #134](https://github.com/spicyChicken59/SpicyStock/pull/134) merged exact
reviewed head `49d96480` at `6abbc950`. All seven gates passed: 3,664 Python,
12,502 page, 378 chart and 137 continuity checks; both native jobs and both
secret checks succeeded. Native API artifact digests match official upload
logs; their payloads were not separately downloaded. Publisher `38040190670`
and replacement Pages `38040201537` succeeded.

Actual public acceptance passes 261 checks with native original-byte matches
for all 37 required public files. Fourteen phone/desktop screenshots were
inspected, with no errors or horizontal overflow. The unchanged canonical
`f5cbe38e…` and reader `f9282e90…` bind the exact dated comparison
`249b60c0…`, captured before entry opened for October 12. Production strategy,
picks, histories, source objects, latest morning/issuer receipts and the
pinned design system retain their bytes. The reviewed producer/runtime and
cohort hashes are identical after merge, preserving the prior retained-source
and independent Decimal replay evidence.

All five original rows remain. KE one share requires $29.52 principal and
$1.27 price-to-stop risk; PSNL three shares require $49.26 and $2.22. The
unchanged stop/market reductions leave a $2.50 effective research risk budget
per idea. The comparison totals $78.78 principal and $3.49 price-to-stop risk;
fees, gaps and slippage are excluded. Baseline tickets/reservations precede
research. MG/ZIM remain event-refused; SN remains zero-share/occupied with
its model reservation. None establishes Mo's holdings or settled cash.

Initial personal cash is unknown. A separately disclosed ephemeral test input
of $1,743.29 stayed local and preserved focus/storage; it is not an observed
account balance. Opening the research panel makes exactly two bounded public
reads and creates no order, copied ticket, private draft or reported fill.
No provider, broker or workflow action occurred in this public verification.
Full identities, checks, hashes and retained limitations are in
[the dated release receipt](release-evidence/2026-10-10-stop-research/acceptance.json).

The experiment is available as dated research, not an observed October 12
trade or measured strategy return. The journal in PR #140 remains pending
its required native gates. Next releases cover HTTP diagnostics, whole-share
personal guidance and issuer evidence consistency; timely quotes, broader
coverage and an actual first personal trade remain open.

The integrated issuer-consistency branch passes 476 issuer checks and 1,459
additional morning/cash/private-handoff/research/journal checks in two scoped
browser invocations (1,935 total), after incorporating the actual current
morning/issuer receipts from main. All reviewed runtime hashes are unchanged.
Final documentation checks pass 37/37; the current 40-file publisher inventory
and exact production issuer companion validate with zero network attempts.

## Checkpoint, 10 Oct 2026 — HTTP diagnostics released

[PR #135](https://github.com/spicyChicken59/SpicyStock/pull/135) merged reviewed
head `ce1184c5` at `d72bcf35` after all seven required checks passed. Hosted
verification records 3,734 Python, 12,640 page, 378 chart and 137 continuity
checks, both native runtime jobs and both secret scans. Official native artifact
digests match the upload logs and API metadata; their payloads were not separately
downloaded. Publisher `38040596719` and Pages `38040608992` succeeded.

Actual public acceptance passed 183 checks and all 37 required native file hashes.
Eighteen phone/desktop captures were inspected. The first attempt stopped on an
external Google Fonts CORS failure; its 130/131 results remain in the receipt.
A fresh run of the unchanged strict checker passed, with no error exemption or
substituted asset. This establishes that run's result, not continuous availability
of the third-party font service.

The legacy issuer receipt `c0d1c97f…` / bundle `c20f9e4d…` remains honestly
unavailable: one request, zero downloaded/captured bytes, identity/index unknown.
The UI labels its source error "HTTP status not recorded" and preserves the
original requested URL. It does not infer 403 from missing metadata. MG/ZIM's
dated acquisition exclusions remain intact. A separately disclosed disposable
synthetic cash input checks local continuity; it is not Mo's actual balance.
The canonical publication, reader, picks, histories, retained sources, morning
and issuer companions, research cohort and pinned design system are unchanged.

Exact heads, gate results, independent source review, public hashes, screenshot
digests and the failed attempt are retained in
[the diagnostic release receipt](release-evidence/2026-10-10-issuer-diagnostics/acceptance.json).
The day's one remaining authorized production issuer collection is a separate
verification step; its result must not be attributed to this legacy acceptance.

That subsequent collection, `38040893686`, published `f9b91d00` with receipt
`f36c6b4e…` and bundle `f525a5f9…`. It observed HTTP 403 at the original SEC
ticker-mapping URL. One shared request failed for both selected MG/ZIM rows;
there were no submissions/document requests, downloads or captures. The failure
body/headers are deliberately absent, so the denial's cause is not established.
Both the deployed validator and queued issuer-consistency validator accept the
exact source, prior-receipt compare-and-swap and current canonical/reader binding.
All 18,594 protected prior docs blobs retain their bytes.

Publisher `38040976621` verified all 37 files; Pages `38040987252` succeeded.
The unchanged strict browser checker passed 183/183 on its first typed-response
attempt, with 37 exact native hashes and 18 inspected captures. The public UI
says "Observed HTTP 403 · SEC ticker mapping" and retains unknown identity/index
coverage, no filing excerpts and both known event exclusions. This separate
collection and acceptance are appended to the same dated release receipt.
The unchanged daily guard's complete run/attempt history counts exactly three
production starts today, leaving zero. No fourth start is authorized by the
current budget. A public-contact/client-identification change would be an
unproven access hypothesis, requiring a designated contact and a future budgeted
verification; never infer one from private email credentials. Broader source
coverage and a first actual trade remain open.

## Checkpoint, 10 Oct 2026 — anticipation decisions and chart inspection

Issue #142 reproduces two gaps on the retained October 9 publication: the
Morning desk's wait explanation named only reaction gates, and the registered
research rows offered no action to inspect their existing recorded charts.
UI commit `59199f7b` adds the original top anticipation refusals with separate
top/quiet/ticket counts, and a keyboard-accessible recorded-chart action on each
current research row. MG/ZIM's acquisition exclusions and KE/SN/PSNL's original
stop refusals remain visible. It creates no new plan or trade authority.

Inspection rechecks the exact publication, canonical/reader digest and original
family/ticker/source/plan identity before synchronously closing the desk and
opening/focusing the existing chart. A stale action, including a detached button
after a same-ticker publication replacement, is refused with an explanation.
Back navigation, filters, private input nodes and storage remain intact. Actual
row choices fetch no new chart data. Missing evidence remains unknown; an
anticipation-only ticket no longer coexists with a global zero-ticket wait.

Review also reproduced a sealed planner exception that the new summary initially
called unknown. The final expression reuses the existing planning explanation,
preserving the actual error and distinguishing absent or incomplete evidence.
The reproduction uses the real offline pipeline with a labelled synthetic
planner exception, not invented market data or an observed production failure.

The owner suite passes 108 controls over the existing frozen actual publication
and producer fixtures. It uses no moving `docs/data.json` assumptions or new
fixture path. Six isolated guard mutations fail their named controls; an
unrelated timeout change passes all 108. Independent review passes 25 chart,
identity, filter and modal controls plus 14 focused planner-evidence controls.
Restoring only the old planner expression fails eight checks; an unrelated
chart-padding change passes all 14. Twelve phone/desktop/canonical screenshots
were inspected, including the actual button at phone width.

The earlier final-draft compatibility run passed 1,490 morning, wait, research,
status and refresh checks. After the one-expression planner correction, all
721 wait checks pass again. README/configuration are swept; 37 documentation
checks pass. The new suite is part of the normal page gate via
`--only decisioninspection`, which also passes all 108 controls in the shared
harness. Final exact-head review, hosted gates and actual public acceptance
are still pending. Python test
collection remains 3,850; the design-system pin and all original source data
and strategy rules are unchanged.

## Checkpoint, 10 Oct 2026 — whole-share exit guidance released

[PR #139](https://github.com/spicyChicken59/SpicyStock/pull/139) merged reviewed
head `08b919f3` at `22309bb1`. All seven gates passed: 3,734 Python, 12,690 page,
378 chart and 137 continuity checks, both native jobs and both secret checks.
Native API artifact digests match official upload logs; their payloads were
not separately downloaded. Publisher `38041498479` and Pages `38041510424`
succeeded. The actual public runner passes 59 checks and matches 35 native
files; a separate two-file native supplement verifies the historical companions
and completes all 37 files in the current publisher inventory.

Fresh actual public contexts keep cash unknown and private reports empty.
Separate disposable contexts pass 80 clearly labelled synthetic private checks
using genuine model-produced historical one/three-share drafts. They show the
whole-share half-exit reference as one/zero or two/one exited/remaining, without
deciding that another exit is due or assuming fractional-share support. Unknown
reported exits keep holdings unknown; later explicit reports update the reference
without rewriting original terms. Unknown prices/fees leave completed personal
results unavailable. These controls do not establish Mo's balance, position,
execution or profit. All eight screenshots were inspected without errors or
overflow; there were no provider, broker or clipboard-copy actions.

Reviewed runtime hashes match the merge. Source/strategy modules, canonical and
reader publications, picks, histories, retained sources, morning/issuer/research
companions and the design-system pin retain their prior bytes. Full exact heads,
hosted counts and separate actual/private verification are retained in
[the whole-share release receipt](release-evidence/2026-10-10-whole-share-exits/acceptance.json).
The current baseline still has zero tickets; registered research is hypothetical.
Next are the reviewed research journal and issuer consistency releases after their
native gates, then the anticipation explanation/chart-inspection milestone.


## Checkpoint, 10 Oct 2026 — independently executed research reports

Issue #144 addresses a concrete gap: a trade executed independently from a
retained research idea could not be recorded without first creating an admitted
personal entry draft. The new explicit research-row action opens a blank,
unsaved report. Its first save requires a positive actual fill and the matching
submitted quantity. Every other unknown broker fact remains unknown; published
research quantities and prices are never inserted as actual executions.

The version-3 private store distinguishes planned handoffs from independent
research reports. The latter preserve the exact original publication, cohort,
evidence and actual baseline-admission boolean, without any order, plan, draft
or cash payload. Both admitted and withheld original ideas can be recorded after
cutoff. The same publication/evidence identity cannot be duplicated or converted
over an existing planned handoff. Corrections keep the original source after
expiry or publication replacement. Model exit schedules, entry-copy authority,
settled cash and positions are not inferred from independent reports.

Model commit `cad52c80` passes 49 direct controls; 12 isolated guard mutations
fail their named checks and an unrelated control passes all 49. Independent
model review passes 86 complementary controls over genuine legacy bytes,
reported result arithmetic, both origin kinds, shared-identity collisions,
source binding and storage failures. Version-1 and version-2 reads preserve
original bytes; only an explicit successful save migrates them, retaining
existing values and validation. The shared 100-record/1 MiB cap, locking,
compare-and-swap and recovery remain in force.

Independent review also reproduced an existing planned-handoff refusal when a
valid upstream publication timestamp contained six fractional digits. A genuine
positive producer fixture succeeds before that single labelled source-clock
projection and failed after it. The corrected source-time validator preserves
the original six-digit clock; seven-digit source clocks and six-digit manually
entered broker times still fail. This is an executed transport-format control,
not a claim that an actual Mo order failed or that the current zero-ticket
publication admits a trade.

The initial browser acceptance found phone select overflow. A scoped Morning
desk select-width constraint fixes the measured overflow. Original admission,
dates and report status remain visible; technical source identifiers sit in an
optional disclosure. The legacy handoff suite passes 269 controls after its
synthetic v1 envelope omits the newly introduced kind field and expects version
3 only after explicit save. The combined morning, status, cash-preview, research, journal, decision and
refresh compatibility run passes 1,475 controls. The final dedicated browser
suite passes 147 controls; six isolated mutations fail their named assertions,
and an unrelated timeout change passes all 147. Four blank/completed phone and
desktop captures are inspected. Independent final-source browser review passes
53 additional source-binding, stale-reference, private-input and correction
controls. Exact-head integration review, hosted checks and actual public
acceptance remain pending. README and
configuration documentation are swept, with 37 documentation checks passing.
No strategy, provider, production source or design-system pin is changed.


## Checkpoint, 10 Oct 2026 — frozen research follow-through released

[PR #140](https://github.com/spicyChicken59/SpicyStock/pull/140) merged reviewed
head `84a0a0cd` at `62f7905d`. All seven exact-head gates passed: 3,813 Python,
13,014 page, 378 chart and 137 continuity checks, both native jobs and both
secret checks. Native memory supervision passed; official upload/API artifact
digests match, without claiming a separate artifact-payload download.

Publisher `38042651865` verified all 40 public files and completed successfully.
Its Pages build `38042666532` deployed successfully; the initial push-triggered
Pages build was superseded/cancelled and is recorded separately. The unchanged
strict public runner passed 127/127 on its first attempt against that exact
merge, with all 40 native hashes matched and six phone/desktop captures inspected.
The default clock and actual public source were used; private records remained
empty and settled cash remained unknown. There were no browser errors,
overflow, provider calls, private saves or order-copy actions.

The actual journal contains one original cohort with five rows. KE's one-share
and PSNL's three-share research allocations are pending at zero of five observed
sessions; MG, ZIM and SN remain excluded. All result-R fields are null. This
records what is awaiting observation, not a model fill, personal execution,
portfolio, return or demonstrated strategy edge. Opening the disclosure loads
only the two bound journal files; closing it leaves initial loading deferred.
Exact checks, publication identities and screenshots are retained in
[the released journal receipt](release-evidence/2026-10-10-research-follow-through/acceptance.json).
The current canonical scan still supplies zero baseline tickets. Next are the
reviewed issuer-consistency and decision-inspection releases after their gates,
then the independently executed report milestone.


## Checkpoint, 10 Oct 2026 — private backup and restore prepared

Issue #146 follows an eight-check executed portability audit: a saved private
trade report survives a same-browser reload, but a fresh isolated profile has
no normal transfer path. This was missing capability, not a demonstrated save
failure. The new local backup disclosure downloads the exact saved bytes and
previews a selected supported file before a separate explicit restore action.
Restore accepts only a readable, empty destination and never merges or replaces
existing records. No server, provider, broker or cloud account is involved.

Locally reviewed model commit `7cb02af2` reuses the full private-store validator with the shared
100-record / 1 MiB bounds. Versions 1, 2 and 3 retain their exact bytes through
read, export and restore; normal explicit report corrections keep their existing
migration behavior. Unknown broker facts, decimal strings, original clocks and source
identities retain their meaning. An invalid selected file cannot poison the
healthy destination's storage status. File reads are bounded and strict UTF-8;
BOM bytes are preserved for rejection, not silently trimmed.

Review executed a draft API mismatch: replacing only a preview object's raw
fee value left its summary unchanged and was accepted. The final model binds
the issued preview object to its exact original raw bytes and destination in a
private WeakMap, rechecking both inside the Web Lock. Rewritten or cloned
previews fail. A changed destination refuses before any write. Successful
restore consumes its preview; a failed write retains its original preview for
retry and prior/proposed recovery bytes. This is a reproduced local API contract
issue, not evidence of a remote attack or changed Mo record.

Locally reviewed UI commit `d3e8ad46` keeps the existing report nodes mounted. Choosing,
previewing, cancelling or rejecting a file preserves unsaved values; restore
refuses a dirty or new unsaved report. Exact saved-byte download excludes those
unsaved edits. The optional disclosure remains available when public loading
fails. Successful restore returns focus to its visible result status when the
confirm button still held focus; it does not steal a later user focus move.
Emergency prior/proposed recovery downloads remain a separate format.

The model passes 67 controls and 14 isolated guard mutations fail their named
checks; unrelated capacity/copy controls pass 18 and 67 checks respectively.
Independent source review passes 38 model and 27 browser controls, including
legacy/mixed bytes, the exact 1 MiB boundary, raw concurrency checks, readback
failure, strict file decoding, cancelled late reads, source outages, dirty input
identity/focus/caret and unchanged order authority. Phone and desktop captures
are inspected. Existing handoff, independent-report and refresh compatibility
passes 463 controls; the corrected integrated publication-recovery suite passes
131/131, and 37 documentation checks pass. The final dedicated browser baseline
passes 137 controls. Eight isolated guard mutations fail their named assertions,
and an unrelated control passes all 137. Locally reviewed browser-test commit
`dbf84e3f` contains those controls. Final exact-head review, hosted gates and
actual public release remain pending.

The earlier recovery compatibility run exposed an inherited synthetic fixture:
it built version 1 from a version-3 seed without removing the new kind field.
The correction belongs to existing PR #145 and is published at `75f5bbc7`, with
131/131 recovery checks and independent 22-integrity/5-legacy-control approval.
Its runtime is unchanged; the earlier `e556a5c0` hosted checks are historical,
and new exact-head gates must pass. That correction is merged into this branch.
No storage validation or trading guard was weakened to accept the bad seed.


## Checkpoint, 10 Oct 2026 — issuer, inspection and independent reporting released

[PR #145](https://github.com/spicyChicken59/SpicyStock/pull/145) merged exact
reviewed head `75f5bbc7` at `e081535d`, 13:25:38 UTC. All seven required checks
passed on that corrected head: 3,850 Python, 13,387 page, 378 chart and 137
continuity checks, both native cases and both secret scans. Native memory
supervision passed; official artifact API/upload digests matched. No separate
artifact-payload download is claimed. The earlier `e556a5c0` run remains
historical. Exact-head independent review preserved the initial 32 integration
checks and added 22 correction-integrity and five executed legacy controls.

GitHub had refused the older issuer branch as conflicting. This release uses
the already reviewed successor's own successful checks and normal expected-head
merge. GitHub automatically marked #141 and #143 merged by ancestry, closing
#138, #142 and #144. Their independently reviewed heads and separate seven-gate
receipts are retained. No required gate was bypassed or unreviewed head merged.

Publisher `38055671203` verified all 40 public files and completed at 13:27:01
UTC. Final Pages `38055685479` deployed successfully at 13:26:44; initial Pages
`38055671329` was superseded/cancelled and is recorded separately. Three unchanged
strict runners passed their first actual public attempt at the exact merge:
189 issuer, 147 decision-inspection and 163 independent-report checks. Each
matched all 40 native file hashes. All 30 phone/desktop screenshots were directly
inspected, with no browser/transport errors or overflow. The issuer runner's
synthetic cash-only DOM control is separately labelled; it is not Mo's balance.

Actual issuer evidence still records HTTP 403 during SEC ticker mapping,
unverified identity, unknown index coverage and no documents. Its cause is
unknown; the retained MG/ZIM exclusions remain visible. The five original
anticipation refusals remain separate from ten quiet setups and zero tickets.
Research inspection opens the exact recorded KE chart without promoting a
research allocation or creating entry authority. Every actual bound research
row opens a blank independent report with 14 unknown fields and can be cancelled
without a private write. No provider request, broker action, actual fill or
personal profit was produced by acceptance. The journal remains pending/excluded.

The [combined durable receipt](release-evidence/2026-10-10-independent-reports/acceptance.json)
binds each exact head, hosted run, public file and inspected screenshot. Runtime
and original source identity checks keep scope separate from the displayed
research and synthetic private controls. Prior evidence, history, strategy and
the pinned design system retain their bytes.

Next: #147 adds the locally verified exact-byte private backup; its unchanged
remote head `101dc9ff` has independent complete-tree approval and is awaiting
hosted checks. #148 addresses an executed decision-clarity gap: the selected
reader batch completed 2/2, with zero feasible reaction candidates and two
intentional research reads, while the original headline says reader review is
incomplete. Coverage remains partial. The new display must separate these facts
without changing historical publications, strategy gates or order authority.

## Checkpoint, 10 Oct 2026 — selected review completion and wider coverage

Issue #148 addresses that reproduced wording gap. The cover and Morning desk
now show reconciled selection, selected-batch completion and wider coverage as
separate facts. The actual retained publication selected and accepted two
intentional research reviews, with zero individually feasible reaction candidates
before review. Of 479 discovered candidates, 477 were not selected; 51 mechanical
A-band names lacked accepted review under the archived Yellow A+-only gate.
Completing the selected batch does not establish full coverage or admit a trade.

The shared helper checks supported archived policy semantics, row/evidence
agreement, purposes, feasibility, attempts, reader outcomes and broader counts.
Missing or contradictory completion evidence preserves original wording. The
narrow current-session headline correction keeps the dated published headline
available; ended or unavailable sessions retain their original primary verdict.
Reaction selection stays separate from anticipation and from portfolio cash.

Local UI commit `95957c93` and test commit `e46b9703` pass 349 dedicated browser
controls. Seven isolated guard mutations fail their named assertions; the
unrelated control passes all 349. Eleven explicitly renderer-only outcome
packets agree with the unchanged backend helpers; they are not new canonical
publications. Independent review passes 57 helper and 20 browser controls on
the actual compact reader and genuine offline fixtures. Six owner and six
independent phone/desktop screenshots were inspected. Review resolved unsupported
policy metadata, archived-headline substitution and exact backend error-prefix
classification before source freeze.

The root's ten existing compatibility suites pass 2,124 controls on the final
runtime hashes. Dirty private forms, saved legacy bytes, unknown cash and
existing entry gates remain intact. README and configuration documentation are
swept. The [preparation receipt](release-evidence/2026-10-10-review-clarity/prepared.json)
distinguishes local component commits, synthetic controls and the still-pending
hosted and actual public release acceptance. No original publication, source,
strategy, provider, account safeguard or design-system pin changes.

Next: release #147 after its remaining required gate, finish exact-head review
and hosted acceptance for #148, then #149 enables a first actual-fill report from
a verified retained journal row after a newer scan replaces the current cohort.
Timely morning delivery, SEC source access and the first actual trade remain open.

## Checkpoint, 10 Oct 2026 — first reports from retained journal cohorts

Issue #149 closes a reproduced gap after publication replacement: the current
research comparison can be empty while the verified journal retains original
ideas. Each verified original row now offers a blank actual-fill report. Its
request binds the currently loaded journal to the current publication and the
selected original cohort, row and evidence. Stored version-3 source identity
remains the original publication; current journal identity is only a transient
lookup prerequisite. Unknown origins and arbitrary ticker requests refuse.

The existing current-comparison path retains its original publication guard.
First saves still require actual positive fills and submitted quantities, and
recheck the source inside the existing storage lock. A replaced journal requires
an explicit verified reopen; reopening the same original preserves mounted dirty
inputs, focus and caret. Busy saves refuse reference replacement. Different
cohort revisions of the same original publication/evidence open the same private
record, rather than creating duplicate trades. Saved corrections remain available
after source disappearance. Model outcomes never fill in actual broker facts.

Local model commit `bca160e5` passes 76 controls, including nine new journal
boundaries. Nine isolated model guard mutations fail their named controls;
an unrelated share-cap change passes the nine journal controls. Local UI commit
`7b2c71f9` and browser-suite commit `020298fb` pass 128 dedicated controls.
Three isolated browser guard removals fail exact-reference, loaded-state and
explicit-reopen assertions; an unrelated control passes all 128. Independent
browser review passes 41 complementary controls, including a real Web Lock wait,
journal replacement, original-source deduplication and unavailable-source
correction. Eight bounded owner and two independent phone/desktop screenshots
were inspected. The normal page gate includes `journalreports`.

These local receipts use genuine producer fixtures with clearly labelled
synthetic private fills. They establish neither a real execution nor public
release acceptance. README and configuration documentation describe the loaded
journal path without new provider calls or settings. Exact-head integration
review, hosted checks and actual public acceptance remain pending. The
[preparation receipt](release-evidence/2026-10-10-journal-reports/prepared.json)
preserves component hashes and evidence boundaries.

Next independent data milestone #151 adds a separate dated IEX observation for
the current registered research cohort's allocation-fit rows. An offline source
replay demonstrates that the admitted-only morning collector supplies no quotes
for current KE/PSNL research, even at an eligible synthetic Monday clock. The
new work must preserve ticket admission and label unchecked halt, volume and
event coverage. It does not resolve best-effort delivery or SEC HTTP 403 access.

## Checkpoint, 10 Oct 2026 — private backup released

[PR #147](https://github.com/spicyChicken59/SpicyStock/pull/147) merged reviewed
head `101dc9ff` at `a9862564`. All seven exact-head gates passed: 3,850 Python,
13,524 page, 378 chart and 137 continuity checks, both native jobs and both
secret checks. Native memory supervision passed and official upload/API artifact
digests matched; artifact payloads were not separately downloaded. Publisher
`38058127724` verified all 40 public files and final Pages `38058141730` deployed.

First-attempt public acceptance passed 68 actual-empty controls and matched all
40 files. Cash stayed unknown, no private records existed and empty download made
no write or download. A separate synthetic rehearsal passed 45 controls: a real
file download, new browser chooser, zero-write preview/cancel, explicit restore
and re-export preserved exactly 4,773 bytes. Both legacy and independent report
origins and unknown costs/times survived. All seven phone/desktop screenshots
were directly inspected without errors or overflow. Synthetic fields are not
Mo's account facts, execution or successful trade.

The [durable release receipt](release-evidence/2026-10-10-private-backup/acceptance.json)
embeds eight original proof files with exact byte digests, the reviewed/merged
identities, delivery, source hashes and separate public/private scopes. Root
readback checked 26 proof, source, image and release identities. Actual public
reads are complete and the main-release hold is lifted. PR #150 review clarity
is undergoing hosted checks; #149 retained-journal reporting is locally verified
and being prepared for review; #151 research observations is in implementation.

## Checkpoint, 10 Oct 2026 — #150 and #152 finished in one PR

Mo asked Claude to find where the hourly ChatGPT loop stopped and to finish and
merge it. It had stopped with two open PRs: #150 (review clarity, `31c32fbb`)
and #152 (retained-journal reports, `d830f75b`, built on #150). Both failed the
same three page checks, and #152's page job was cancelled at its 15-minute cap
with 13,951 of 13,954 checks done. Main was green. This branch restarts
`claude/spicystock-historical-workflow-i53ud1` from main, merges #152's exact
head (which carries #150's), and adds two corrections, so merging it lands both
reviewed heads by ancestry. Nothing of either PR's reviewed code is rewritten.

**The first screen.** Reproduced in Chromium on #150's head: the cover's new
review paragraph and original-verdict card took the market bar from 166 to
326 px at 1280 (first stock at 1021 against the 900 gate) and the stage cards
and search below the 844 px phone screen, on EVERY record, while the facts
answer only one headline. The cover now carries them only under the
reader-wait headline (`report.H1_READER_WAIT`, which `reader_pending()` writes
when an A+/A burst lacks accepted review), as one collapsed line naming the
accepted selected reviews and the mechanical A+/A still unreviewed ("Chart
reviews: 2 of 2 selected accepted · 51 mechanical A+/A not reviewed" on the
retained Oct 9 record); opening it shows the full reconciled summary and the
dated original headline. Every other night's first screen measures main's to
the pixel at 320, 390 and 1280. The Morning desk and Method keep the facts for
every record, and the clarified headline rewrite is unchanged.
`tools/review_selection_cases.mjs` now asserts that contract and the line's
visibility, not just text present in the DOM: always-visible, never-visible
and dropped-count mutants fail 7, 20 and 5 of the review and phone suites'
402 checks; an unrelated control passes all 402.

**The CI caps.** On main (`a9862564`) the pytest job took 14m13s and the page
job 14m11s against 15-minute caps. `tests.yml` is no longer a pinned source (the
loop has edited it five times since), so both caps are 30 minutes now: a cap
stops a hang and does not bound a suite. No suite, check or lane changed.

**Not done here, and why.** #151 (current-cohort research quotes) was "in
implementation" in the loop's own notes and has no pushed branch or PR, so there
is nothing of it to finish. Public acceptance is the publication gate's: this
sandbox's proxy refuses github.io, so the served page is read on GitHub's
runner (`publish_dashboard.py`, every public file against committed main), not
here. No run, mail, provider call or record change.

## Checkpoint, 11 Oct 2026 — dated IEX observations for the research cohort (#151)

**Revision.** Branch `claude/spicystock-historical-workflow-i53ud1` restarted from
`main` at `7bc5d2c2` (the merge of #153), pushed as **PR #154**. `docs/data.json`,
`docs/picks.json`, the compact reader, the retained morning, issuer, stop-research
and journal receipts, the history, the evidence objects, the quality ledger and the
vendored design system are untouched; no run, mail, dispatch, provider call,
credential, subscription, broker connection or hosting change. Saturday tests
cannot prove Monday delivery, and nothing here claims they do.

**What was missing**, reproduced offline before anything was built: the morning
collector (`src/morning.py`) reads admitted orders only, so at an eligible
synthetic Monday clock over the retained 9 Oct publication it supplied no quote
for KE or PSNL, the two allocation-fit rows of the registered stop-width cohort
(`249b60c0…`), and the research panel could say nothing about where either traded
before the window it was registered for.

**What was built.** `src/research_observations.py` is a separate, dated
observation bound to the exact publication, the compact reader and the current
cohort: `collect()` selects only the bundle's `allocation_fit` rows of a bound,
recorded cohort, makes at most one IEX snapshot request
(`MAX_REQUESTS = 1`, `FEED = "iex"`, the morning transport's `_fetch`,
`trade_observation`, `quote_observation` and `price_state` reused, so the ages,
the future skew and the crossed-quote refusal are the morning policy's own and
archived in `POLICY`), and writes bid, ask, spread, last trade and each price's
position against the row's own trigger, limit and stop. Every zero-call case is a
named reason before the request: `wrong_session`, `entry_window_ended`,
`before_collection_window`, `stale_publication`, `future_publication`,
`cohort_missing`, `cohort_not_current`; no fit rows is `no_research_rows`; a
refused or failed snapshot is `provider_unavailable` with the error kind and never
its text; missing credentials spend nothing. `COVERAGE` says what is not checked
(halts, delayed volume, issuer news, earnings; corporate action from the archived
cohort registry only) and `LIMITS` that this is a dated best-effort single-venue
snapshot. `_validate()` re-derives the whole receipt before it is accepted: the
publication binding, the cohort block field by field, the clocks (started at or
before generated, a five-minute expiry, the 180-second collection bound), the rows
against the cohort's own fit rows, the request count against the error kind, every
freshness and price-state replay, the status against its measurements, the
64 KiB bound. `run()` refuses an output path under the publication files, re-reads
the data, cohort and prior receipt after collection and refuses to replace the
prior when any moved, and writes atomically. `tools/publish_morning.py` gains
`--target research`: a one-file commit of `docs/research-observations.json` beside
the cohort, compare-and-swap on the record's canonical bytes, the prior
observation and the cohort on main (`research_cohort_changed` when main's
`stop-research.json` no longer hashes to the receipt the observation binds), a
rehearsal or a future completion refused. `morning.yml` collects it after the
morning observation with `continue-on-error`, uploads it under its own run and
attempt and persists it only against the unchanged record and cohort; the
publication gate's `OPTIONAL_RECORD_FILES` names it so Pages is verified serving
it when it exists. `docs/app-research-observations.js` attaches to the research
panel only after it has hashed the loaded reader, the receipt bytes and the
bundle (`attach({record, receipt, receiptSha, bundle, hosts, summary})`), replays
the validator's checks in the browser (`validate()`), and renders one dated
section per fit row under the row's levels: bid and ask, spread, the quote and
trade times in Chicago, and each price's state in words ("below the published
trigger", "between the published trigger and limit (a position, not a signal)");
an inapplicable or unavailable receipt is one sentence with its reason; a
publication or cohort change clears every rendered section. No ready label, no
size, no order copy, no private draft, no new ticket authority: the research
rows' own "no SpicyStock entry" refusals and the morning desk's admitted-only
quotes are unchanged.

**Measured** (this sandbox, Python 3.11.15, Node 22, Chromium through Playwright
1.56.1): 3905 tests collected, 3871 passed and 34 environment-gated skips in
15 m 33 s; fixtures current through their generators: 13 page, 21 morning,
30 issuer, 22 stop-research, 40 research-outcomes and the 12 research-observation
variants (observed, partial, outage, no-credentials, before-window, expired,
wrong-session, no-rows, outside, missing-cohort, stale-cohort, followup), each the
collector's own output over the genuine producer cohorts; continuity 137; chart
check 378/378; the `research-observations` suite 226/226 at 1280 dark, 390 light
and 390 dark over the canonical publication, the stop-research suite 332/332, the
independent-report, private-backup and journal-report suites 520/520; the full
smoke with `--shots` 14198/14198 in 19 m 15 s. CI at `7d12bc2e`: the page job 14198/14198 in
13 m 58 s, pytest in 15 m 45 s, both gitleaks runs and the gate green, the two
native jobs still running when this was written; the seven checks on the final
head are recorded on PR #154. The two added tests moved the collection to 3907. Screenshots at 1280 dark and 390 light and dark over the observed,
partial and red cohorts were looked at: the sections sit under each fit row's
levels, the Chicago times carry their offset, the phone keeps one column and
nothing scrolls sideways.

**Mutation passes**, each mutant in its own copy, the tree never written, judged
by the test files naming the rule (the two that the fixture-equality test would
catch first were re-judged with it deselected, so each dies in its own test). Browser, through routed copies of the module:
the receipt-digest check, the freshness replay, the price-state replay, a
below-trigger print read as within the band, the request-count check, the
publication binding and a future receipt accepted all die; the control (an
unasserted note) stays green. Three survived the first pass and each was a hole,
closed with the case it showed was missing: a future receipt was refused by the
duration bound and then by the session freshness before the clock rule could be
reached (the case is built from the before-window variant moved to 2099 with
consistent clocks now); zero requests beside observed prices was caught by the
budget bound, not the count (a zero-request case with prices now); and the
dropped publication binding was covered by `binding()` on a projected load (a
canonical load with a mismatched reader digest now). Python, in a worktree copy:
selecting every row with levels, dropping the morning guards, two requests a run,
skipping the price-check replay, the cohort equality, the publisher's cohort
compare, the run's cohort-change check and the unbound-cohort reason all die in the test
naming them; `ignore_cohort_binding` is equivalent (`_reason()` names an unbound
cohort before `research_rows()` is asked); and **two survived, each a hole**.
`observed_when_any_recent` lived on the second shape this file names: every
fixture and case had both rows recent or both not, so `any` and `all` agreed; one
case stales PSNL's print alone now, holds KE recent on both prints and the status
to `partial`. `skip_request_count_check` lived because the one request-count
forgery set two requests, which the budget bound refuses before the count rule is
reached (the first shape); an observed receipt claiming zero requests beside its
prices is a forgery now. Both die; the control (the CLI refusal's wording)
stays green. One harness defect of mine: the worktree the Python mutants run in
was pinned to the branch's start, so a later patch of the working diff failed to
apply; it is reset to the pushed head before each pass now.

**Keep / fix / defer / omit.** Keep: the observation reads and never decides; its
rows are the cohort's own fit rows and nothing it says widens a refusal. Fix if it
bites: the research publisher does not re-validate the prior observation it
compares against (the morning target does not either); the shared error labels
(`existing_morning_snapshot_too_large`, `morning_publication_requires_main`,
`morning_observation_run_mismatch`) are spelled for the morning target and
reused. Defer: sub-minute cadence and hosting (#108); SEC mapping HTTP 403 and
broader event coverage; a halt or delayed-volume read for research rows. Omit: a
ready label, personal sizing, an order path, any stop-policy change.

**Not claimable:** a live observation. The first can exist at 13:20 or 13:28 UTC on
Monday 12 October, when the morning workflow's two attempts run, and only if the
Alpaca pair the morning collector already reads is present and the cohort on main
is still the one the publication binds. Read its receipt's status, reason, rows and
request count, and the page's sections, and record them here.

## Checkpoint, 11 Oct 2026 — PR #154 accepted on the public site, and the candidate funnel (#109)

**PR #154, accepted.** Merged as `a7600c50` on `main` with a merge commit over
`7bc5d2c2`; the final head `a0d26372` passed pytest (18:30–18:49 UTC), page
(18:30–18:46), the historical-runtime gate (decision
`observed_docs_only_push_no_runtime_change`: the push `2b5946be`→`a0d26372`
changed `CLAUDE.md` alone, so the gate's own rule skipped the native matrix on
that head) and both gitleaks runs; the native central and stress cases passed on
Tests run 38161496122 at `7d12bc2e`, whose tree differs from the final head in
`CLAUDE.md` and `tests/test_research_observations.py` only, neither a source
the native cases read. Publisher 38165726718 waited for the five changed files
and printed *Verified: every one of the 41 public files matches committed main*;
Pages 38165745839 deployed (38165726883 cancelled as superseded, as every merge
does); the merge commit's own Secret scan passed. The first live research
observation can exist Monday 12 October at 13:20 or 13:28 UTC and is still not
claimable.

**Revision.** Branch `claude/spicystock-historical-workflow-i53ud1` restarted
from `main` at `a7600c50`. The owner's loop continues on #109, milestone 3's first
deliverable: "persist and show separate denominators" and "explain where each
potentially usable candidate was lost". `docs/data.json`, `docs/picks.json`, the
compact reader, every receipt, the history, the evidence objects, the quality
ledger and the vendored design system are untouched; no run, mail, dispatch,
provider call or credential.

**What was built.** `src/funnel.py` gives every discovered reaction candidate
and every listed anticipation setup exactly one terminal stage, in the order the
run applies its gates: the regime (RED stops everything at `market`), the
mechanical grade against the regime's admitted band (`reader_coverage.admitted`,
the one shared rule), the quality veto; then for a name the review budget never
reached, the review selection's own recorded blockers (`preview_event`,
`preview_geometry`, `preview_sizing`, `preview_no_order`, `preview_unavailable`,
`review_budget`); for a reviewed name the reader's state by its cause
(`review_refused`, `review_format`, `review_account`, `review_credit`,
`review_transport`, `review_downgraded`); then the constructed plan's own
combined allocation (`event`, `geometry`, `sizing`, `allocation_slot`,
`allocation_cash`, `allocation_occupied`, `ticket`). The stage counts sum to the
discovered count by construction; `potentially_usable` counts the names past
the first three gates; `by_mechanical_grade` is beside it. `report.build()`
composes the block last, off the cleaned record, beside `closest_miss`;
`report.validate()` refuses a block the record does not re-derive (whole-block
equality against `build()`, so a forged count, a dropped row, a changed label
or a rewritten sentence is one fault); `funnel.version` joins the archived
rules, so `rules_version` moves and a record made under older rules is asked
for no block. Legacy records are read for what they recorded -- a plan from
before the combined allocation is placed by the cash budget's cut, the trade
list or the record's own old anticipation-ticket definition, and a field a
record lacks is `unknown`, never guessed. The labels travel in the block, so the
page and the mail print the record's words: the scan disclosure prints the
table and the sentence, each matrix row says where its name stopped, and the
mail prints the same sentence under *where the candidates stopped*.
`tools/candidate_funnel.py` reads the funnel of any publication, of commits, or
of a ref's whole retained history, skipping the first build's records by name.

**Over every retained publication**
(`docs/input-truthfulness/2026-10-11-candidate-funnel.md`): 26 publications
over 21 sessions, 11 September to 9 October, 21 RED and 5 YELLOW, GREEN never
published. Of 11,513 discovered reaction candidates, 8,618 stopped at the
market gate and 2,887 at the YELLOW band's A+ gate; 8 were potentially usable
(the four mechanical A+ in each of the two 8 October publications), 2 refused
by reader authority and 6 lowered below the band; 0 reaction tickets. Of 128
listed anticipation setups, 105 stopped at the market, 6 at a known event, 13 at
the stop rule, 1 at a whole share, and 3 were the tickets the record published
and later superseded (MG, SN; ZIM). Entry geometry, sizing and allocation have
refused no reaction candidate yet, because none has reached them.

**Measured** (this sandbox, Python 3.11.15, Node 22, Chromium through Playwright
1.56.1, on the final tree): 3974 collected, 3939 passed and 34 environment-gated
skips in 15 m 50 s, the one failure the suite-count line this checkpoint moves to
3974 (`tests/test_docs.py` 37/37 after); 13 page fixtures current and the six
cascaded generators current (issuer-evidence, stop-research, research-outcomes,
research-observations and cash-preview regenerated through their own producers
each time the record moved -- the funnel rule, then the sentence's wording --
morning pinned, unchanged); the `funnel` suite 303/303 at 1280 dark, 390 light,
390 dark and 320 dark over the full record, the red and empty nights, a routed
record whose counts are not the page's own at 1280 and 320, a ticker spelled
like an Object property behind the scan deep link, and nineteen shapes the
block check refuses one at a time; the deferred-scan suite 80/80; continuity
137; the chart check 378/378; the full smoke with `--shots` 14501/14501 in its two lanes (its
first run here stopped in the deferred-scan suite: the matrix scroller's
locator, `#scan .sc-table-scroll`, matched the funnel's own table once it
shared the disclosure, so it names the matrix region `[data-sc-matrix-nav]`
now); gitleaks 8.24.3 (fetched into a temporary directory for this pass; it is
not installed in this sandbox) over the branch's commits and over the new
files: no leaks. Screenshots at 1280, 390 and 320, both themes, were looked at:
the table's stage column was a third of a phone's width under wide numeric
columns, so the count columns are sized to their content with a narrow gutter
and the third header reads *setups*, and at 320 the stage column keeps about
half the table (the runner's mono font is wider than this sandbox's, which the
first CI run showed at 110 of 230 px, so the check asks for 45% and the
narrow-screen gutter is 4 px).

**CI found what the local gates had passed.** The first run on the pull request
failed the fixture gate: the red variants of the stop-research and
research-outcomes generators, and two research-observation cases, carried
`geometry` where the anticipation rule, moved to read the market gate first
after they were regenerated, writes `market`. Every cascaded generator's
`--check` had passed here, before that later change. The rule that follows:
after any change that moves the record, regenerate every cascaded generator and
run their `--check` last, not the page fixtures' alone.

**Two reviews by execution over the first pushed tip, every upheld finding
reproduced before it was touched.** The Python reviewer returned nine. The
verdict guard in `admitted_grades()` had no test that would go red, and its
consequence was the opposite of the docstring: `reader_coverage.admitted()`
answers the trade grades for a verdict it does not know, so a record with a
missing or unreadable regime would have been read as GREEN; a missing or
unreadable verdict is `unknown` now, held by a test over seven shapes of
breadth block. The closed-night test was the second shape this file names: the
closed fixture IS the 4 September record the holiday no-op preserved, so its
comparison with the full night could not fail for the reason it claimed; it
asserts what the fixture is now. A listed setup without a plan (`plan: None`,
which `make_watchlist` writes beside the planner's error) had no test, and a
burst row without a mechanical grade was placed at `grade` rather than
`unknown` (no retained publication lacks the field; it is `unknown` now). Seven
more rules survived deletion under the suite -- the re-derivation guard in
`faults()`, the legacy cut's default, an empty error string read as an error,
a legacy trade-list ticket without an order action, the watchlist counts' `all`,
a non-string regime raising inside `sentence()`, and the sentence's plural -- and
each is pinned now; the sentence says "1 momentum name", names the watchlist's
own admission as "passing the coil checks" rather than a second "admitted", and
says "under a market this record does not name" rather than raise. The sentence
test's label loop was substring-fragile (`known corporate event` is a prefix of
the preview label), so it reads each stopped-at clause as "N label" segments.
The page reviewer returned seven. The high: a non-string `rows[].stage` took
the whole page down through the scan deep link (`words()` calls `.replace` on
it) and emptied the matrix on every other path, and a ticker spelled
`constructor` with no row resolved to `Object.prototype.constructor` -- the
pre-review page, run under the new suite, fails "the page rendered through the
scan deep link" and never hydrates the matrix. `funnelBlock()` now checks every
field the drawing indexes into (plain objects, non-negative integer counts, a
non-blank sentence, rows of string ticker and stage) and refuses the block
whole; the stage map has no prototype; `stopped()` reads a string stage only.
The mediums and lows, all fixed: the mutate loop exercised one clause of the
shape check (it walks nineteen now); the empty-stage row printed two literal
zeros and `num()` rounded a fraction (it prints "none counted" and integers
only); a stage outside a family printed "—", the page's word for unreported
(an empty cell now); the sentence had no `overflow-wrap`; the lede introduced
the matrix over a table it did not mention (it introduces both); the 320 px
column widths above. Recorded, not changed: the `typeof` guard in `stopped()`
is redundant behind the rows clause, kept as a second line; the provenance
watch gate's `no_order` beside the funnel's `allocation_slot` for a slot-capped
coil is the coarser, pre-existing reason and not a funnel defect.

**Mutation passes.** Before the review, Python, each mutant in the mutation
worktree at the funnel commit and judged by `tests/test_funnel.py` and
`tests/test_report.py` in full: thirteen mutants -- the veto read before the
grade, the market gate dropped for reactions and for anticipation, an unknown
blocker read as the budget, a withheld plan read as geometry whatever its event,
the usable count ignoring the veto, the validator never comparing, the sentence
dropping the listed setups' stops, a legacy anticipation ticket read off the
trade list, a refused reader read as a downgrade, the validator skipping the
block, the builder skipping it. Twelve die in the test naming the rule (the
veto-before-grade order dies in the test over the retained 9 October
publication, whose 185 vetoed names all sit below the band), and one is
equivalent: the preview's `known_event` and `plan_withheld` blockers are written
by an if/elif in `review_selection.blockers()`, so no record carries both and
their order cannot matter. `usable_ignores_veto` SURVIVED the first pass -- no
fixture has a vetoed name inside the band, the second shape this file names --
and a synthetic record holds it now, so it dies. After the review, ten more over
its rules (the verdict guard, the missing grade, the unplanned setup, the cut's
default, the empty error, the legacy order action, `all` to `any`, the unguarded
`upper()`, the re-derivation branch, the plural): all ten die, each in the test
naming it (the plural first in the fixture tests, whose two nights count one
momentum name, and in its own test with those deselected); the control (a
docstring) stays green both times. Browser, through routed copies of `app.js`
(`SCSTOCK_APP`) judged by `--only funnel`: before the review nine mutants, eight
dead at once and **the half-written block SURVIVED** (the suite's one case was
refused by an earlier clause, the first shape this file names; three more shapes
closed it). After the review sixteen: the rows clause, the prototype-free map
with the guard, the integer-count, plain-object, non-blank-sentence and listed
clauses, discovered and listed read off the page's own lists, the empty-stage
row printing zero, a dash for a stage outside the family, the lede without the
funnel, the caption, the row headers' scope, and the funnel appended after the
matrix. Thirteen died at once. `caption_dropped` died by a locator timeout
rather than a named check, so the caption is read count-guarded and it dies on
four. `funnel_after_matrix` SURVIVED twice: a page loaded with the scan closed,
and one opened by the deep link, both append the matrix after the funnel
whatever the order of the two calls, so the check reads a re-render over an
OPEN scan now, where the matrix is built inside the same render, and it dies.
`typeof_guard_dropped` survives and is equivalent behind the rows clause, as
recorded above. The control (the caption's last words) stays green.

**Keep / fix / defer / omit.** Keep: the funnel reads and never decides; a stage
is the record's accounting of its own gates. Fix if it bites: the block carries
one row per candidate (`reaction.rows`), about 15 KB on a 500-candidate night,
in the record and the compact reader alike. Defer: the funnel's own history
grows with each publication made under the rule; the reading tool is the way to
see it across nights until a page view earns its place. Omit: any rule change
on these numbers; a stage that guesses what an unreached gate would have done.

**Not claimable:** a live night under the rule (the first evening after the
merge writes the first archived block); any trading edge.

## Checkpoint, 11 Oct 2026 — PR #155 accepted on the public site; what the reads cost, and what the account can buy (#109)

**PR #155, accepted.** Merged as `2c077c99` on `main` with a merge commit over
`a7600c50`; the final head `907b593a` passed all seven checks (pytest, 3974
collected; page 14501/14501; the historical-runtime central and stress cases,
21 m 02 s and 21 m 31 s; the gate; both gitleaks runs). Publisher 38176782458
waited for the changed files and printed *Verified: every one of the 41 public
files matches committed main* at 21:33:16 UTC; Pages 38176797847 deployed
(38176781943 cancelled as superseded, as every merge does); the merge commit's
own Secret scan 38176782428 and Tests 38176782434 (21:32–21:51) are green.

**Revision.** Branch `claude/spicystock-historical-workflow-i53ud1` restarted
from `main` at `2c077c99`, pushed as **PR #156**. Two deliverables of #109's
acceptance line remain after the funnel: "measured review cost/coverage" and
"whole-share $2,000 simulations". `docs/data.json`, `docs/picks.json`, the
compact reader, every receipt, the history, the evidence objects, the quality
ledger, the workflows and the vendored design system are untouched; no run,
mail, dispatch, provider call or credential.

**What the record did not say.** Every retained publication archives
`run.reads` (the shortfall by cause) and `run.model`, and the pipeline LOGGED
what the reads cost -- `Claude usage: {...}` -- without archiving it: the
7 October night's cache_write 3,336 / cache_read 36,696 / uncached 48,562
survive in this file alone, and no retained record carries a token count or a
call count a reader could re-derive. The grader's own accounting was also
short: it billed a reply only after the reply checks had run, so a reply the
parser could not read as a score -- which the API charged for all the same --
was never added, and the attempts' response evidence from #88 carried text
digests and stop reasons but no bill.

**The block.** `run.reader_usage` (version 1, archived as
`pipeline.reader_usage_version`, so `rules_version` moves): the model the run
asked, the names asked, the calls sent, the replies received, the four token
classes a reply reports (`cache_write`, `cache_read`, `uncached`, `output`),
their input sum and one sentence. `reader_coverage.usage_block()` composes it
from `grader.grade_all`'s accounting: `cache_usage()` reads the four classes;
`grade_candidate()` counts a call when the request is sent and a reply when
one arrives, bills every reply on arrival -- a reply reader authority or the
discovery contract then refuses, or one that cannot be read, cost what an
accepted one did -- and keeps each attempt's bill in `provenance.billing`,
aligned with `attempts` and None where no reply arrived. The pipeline writes
each selected name's bills to the row as `bursts[].reader_usage` (calls,
replies, tokens, the bills), OUTSIDE `claude`, because a bill is not part of
the judgement's identity: the same night read twice bills a cache write and
then a cache read, and `test_identity_repeats_for_identical_evidence_and_
changes_with_inputs` holds `evidence.id` equal across two such runs, which it
could not with the bill inside the sealed reader result. `usage_faults()`
holds the block one level in: the shape whole, the model the run's, the input
sum its classes', replies no more than calls and calls no more than names
times `grader.ATTEMPTS`, no tokens without a reply, the names the night's
reads, replies at least the accepted readings, and on an open night the
bursts' own -- each selected name's block held to its attempts (one bill per
attempt, None exactly where no reply arrived, well-formed, summed) and the run
block their sum -- and the sentence its own. No price: a price is the
provider's list, not a fact the run observes; the Method view, the mail's
*inputs and reads* block and the quality ledger carry the sentence verbatim,
and a record made under older rules is asked for no block. The version sits in
`pipeline.RULES` beside the reads' own rule and outside the provenance
verifier's replay set: the first placement, in `grader.RULES`, turned every
retained publication and every committed fixture PARTIAL ("archived rules need
a compatible verifier implementation") in 42 tests, which is what that set is
for and not what a cost block is.

**The reading.** `tools/whole_share_feasibility.py` sizes every reaction
candidate a publication archived again through `plan.burst_plan` (via
`entry_limit_study.current_plan`, the cascade the run writes tickets with) at
the account the record archived -- or one given on the command line and
labelled a counterfactual -- under three regimes, the record's own, YELLOW and
GREEN, each with the grade band it admits (the record's archived
`trade_grades`/`yellow_grades` through `reader_coverage.admitted`, the one
rule) and the multiplier it applies; per band it counts the mechanical A-band
names without a veto (the funnel's potentially usable), how many pass the stop
rule and how many size to a whole share, by mechanical grade beside the band,
and prints the limit under which one share fits a stop-constrained ticket
(`one_share_ceilings()`, held to `plan.size` at the boundary). Anticipation
setups are read off their recorded plans only. Over the 26 retained
publications (21 sessions, 11 September to 9 October; 21 RED, 5 YELLOW;
11,513 candidates, none set aside), at the archived accounts (22 at $10,000,
4 at $2,000): tonight 8 in band / 8 past the stop rule / 5 a whole share;
YELLOW 40 / 40 / 35; GREEN 1,666 / 1,598 / 1,409. At Mo's $2,000 / 0.5% for
every night: 8 / 8 / 2; 40 / 40 / 5; 1,666 / 1,598 / 846. **The stop rule is
not the bottleneck; the price is**: 96% of the in-band names pass the stop
rule at any account, 88% of those size to a share at $10,000 and 53% at
$2,000, and under YELLOW at $2,000 -- the only regime a ticket has ever been
published under -- 5 of 40, because a half-size $5 risk budget, halved again
by the stop-risk rule every stop-constrained ticket triggers, buys one share
only under $62.50 (GREEN: $125.00; at $10,000: $312.50 and $625.00). The
price ceiling cuts every grade alike. Anticipation, as recorded: 128 listed,
82 eligible, 3 with a whole share (MG, SN; ZIM, each superseded). Report:
`docs/input-truthfulness/2026-10-11-whole-share-feasibility.md`, the two
history tables beside it. Nothing here is a ticket, a fill or an edge.

**Measured** (this sandbox, Python 3.11.15, Node 22, Chromium through Playwright
1.56.1, on the final tree): 4001 tests collected, 3966 passed and 34 environment-gated skips in 14 m 16 s, the one failure the suite-count line, which read 4003 because the browser mutants' `inputs` suite had its scratch record under `tests/fixtures/page/` while the suite collected (alone, 4001 and `tests/test_docs.py` 37/37); 13 page fixtures regenerated and current,
and every cascaded generator regenerated and current (issuer-evidence,
stop-research, research-outcomes, research-observations, cash-preview; morning
pinned, unchanged); continuity 137; the chart check 378/378; the `inputs`
suite 232/232 with its six new checks (the cost sentence verbatim and nothing priced on the thin fixture at 1280, 390 and 320 in both themes; no cost line for a record from before the rule or a half-written block); the full smoke with `--shots` 14517/14517 in its two lanes; gitleaks 8.24.3 over
the branch's commits and the new files: no leaks. Screenshots of Method at 1280
and 390, both themes, were looked at: the cost sentence sits under the reads'
own, in the record's words, with no figure the page added. CI on the pushed head is recorded on PR #156.

**Mutation passes.** Python, each mutant in the mutation worktree at the milestone commit and judged by the whole test files naming the rule (`test_reader_coverage`, `test_grader`, `test_report`; `test_whole_share_feasibility`), no `-k` filter: twenty mutants, all dead -- the output class dropped from the bill, a retry's reply left unbilled, a call counted only when a reply arrived, the row block written inside `claude`, an empty night without a block, the bursts' own re-derivation skipped, the one-bill-per-attempt and the None-iff-no-reply alignment checks dropped, the input sum including output, the older-rules gate dropped, replies over calls allowed, the sentence and the model unchecked; the reading counting an ineligible plan as a share, YELLOW admitting the trade grades, the ceiling without the stop-risk halving, the account override ignored, the veto ignored, tonight sized at full size, anticipation counting ineligible plans. **The control died on the first pass**, in `test_a_graded_row_records_the_model_and_that_the_chart_was_seen`: the provenance-shape assertion excludes `input`, `attempts` and `attempted_model` and did not yet exclude `billing`, a test defect the earlier grader-side rerun had already reported (1 failed, 273 passed) and I had read as a pass off the wrapper's exit code -- the control is what caught it. Fixed in the commit after; the control then survives (282 passed) and the first mutant still dies. Browser, through routed copies of `app.js` judged by `--only inputs`: the cost line dropped (6 checks), the page pricing the tokens itself (3, the nothing-priced check), a half-written block printed (the undefined check); the control (a comment) passes 232/232. One harness defect of mine: the priced mutant's replacement text held `$'`, which `String.replace` reads as the text after the match, so the first run spliced the file and the page never rendered -- a kill for the wrong reason; the harness replaces through a function now and the mutant dies on the named check.

**Keep / fix / defer / omit.** Keep: counts, never a price; the bill beside the
reader result and outside its identity; the reading reads and never decides.
Fix if it bites: the row block adds about 200 bytes per selected name to the
record and the compact reader; the cost history starts with the first
publication under the rule (the attempts retained since 23 September carry no
bill, and the 7 October log line is the only earlier token count). Defer: a
dated price list the reading can apply (`--prices`), when dollars are wanted;
a GREEN night, which no publication has shown. Omit: any rule, threshold or
account change on these numbers; a budget that stops reads.

**Not claimable:** a live night under the rule (the first evening after the
merge writes the first archived bill); any trading edge.

## Checkpoint, 12 Oct 2026 — PR #156 accepted on the public site; the evidence review that closes #109

**PR #156, accepted.** Merged as `ed23218f` on `main` with a merge commit over
`2c077c99`; the code push `b25e28b1` passed all seven checks on Tests run
38181859353 (pytest 22:48–23:07 UTC; page 22:48–23:04; the historical-runtime
central case 22:49–23:15 and stress 22:49–23:37; the gate; both gitleaks runs),
and the final head `68871eea` (docs only over it) passed pytest, page, the gate
(decision `observed_docs_only_push_no_runtime_change`) and both gitleaks runs on
run 38181878051. Publisher 38185195704 waited for `app.js` and printed *Verified:
every one of the 41 public files matches committed main* at 23:42:08 UTC; Pages
38185210035 deployed (38185195406 cancelled as superseded, as every merge
does); the merge commit's own Secret scan 38185195805 and Tests 38185195670 ran
on `main`. The first evening after the merge writes the first archived
`run.reader_usage` block; it is still not claimable.

**Revision.** Branch `claude/spicystock-historical-workflow-i53ud1` restarted
from `main` at `ed23218f`, pushed as **PR #157**. #109's acceptance line has
one deliverable left after the funnel (#155) and the cost block and feasibility
reading (#156): "an explicit evidence review before promoting strategy
changes" -- and one named case, the retained HAE failure, to test and keep
rejected. `docs/data.json`, `docs/picks.json`, the compact reader, every
receipt, the history, the evidence objects, the quality ledger, the workflows
and the vendored design system are untouched; nothing under `src/` changed; no
run, mail, dispatch, provider call or credential. The PR closes #109.

**The review.** `tools/evidence_review.py` reads committed evidence and
nothing else, and `--check` holds the two files it writes
(`docs/input-truthfulness/2026-10-12-evidence-review-evidence/review.{json,md}`;
the dated report is `2026-10-12-evidence-review.md` beside them). It re-derives
the frozen signal-outcome study's strata from the study's own rows and refuses a
file whose summary is not its rows' (`crosscheck()`); splits the admitted
stratum by phase, calendar month, halves of its exploratory nights and
mechanical grade, each with the study's own night bootstrap at the spec's reps
and seed (`periods()`); walks each stratum's cumulative-R path in the study's
own order and reports its deepest fall (`drawdown()`: the admitted stratum ends
at -55.56R with a 62.31R fall from 11 September to 2 October, the night-means
path 5.05R; a stream no slot cap held, so a path of R paid, not an equity
curve); copies the backtest as the findings file parsed it, the funnel's and
the feasibility reading's totals and the registered cohort and its journal, each
with its file's digest; and reads a fixed ledger of five floated changes under
criteria it states and archives (`CRITERIA`): a rate at
`record.SCORECARD_MIN_PLANS` settled or more, a **sign** only from a 95%
night-bootstrap interval clear of zero (a pasted summary carries counts and sums
and cannot establish one), `supported` only when every direct source is positive
and every evaluation period agrees, an *adjacent* population (another regime,
mixed regimes, the reader not run) shown and never counted. Verdicts today:
trading RED nights **not_supported** (the study's RED nights establish a
negative sign at 267 and at 1,741 settled; the backtest's 25-ticket RED
counterfactual has no interval); admitting A under YELLOW, the 5% anticipation
stop, a ticket without an accepted review, and a larger risk or account all
**insufficient**, each for the reason the file prints. The first eight
exploratory nights straddle zero ([-0.400, +0.041]) and the last seven are
negative; the reader-accepted population is the study's own definition (an
accepted reply AND a final grade in the band), 0 settled -- the first render
counted every answered reply, 22 settled at -0.227, most of them downgrades
out of the band, a mislabelling the committed file no longer carries. Nothing
is promoted and no change earns `supported`.

**The retained HAE reply.** `tests/fixtures/grading/reader-hae/` freezes HAE's
8 October row from both publications (`1e1ffe9c` at $10,000, B/6.5;
`e67f8cba` at $2,000, C/5.5) with the publications' digests, the replies'
SHA-256, byte counts and message ids, the archived account and regime, and the
error the grader recorded. Both replies cite `burst.gap_pct`,
`burst.bar_range_pct` and their kin: measurements the model read, none a path
under `checks.<letter>` of the reader-evidence contract. `tests/test_reader_hae_
retained.py` parses the retained text through the grader's own parser, shows the
discovery tripwire did not fire, holds `reader_authority.validate()` to
"evidence outside criterion authority", replays the text into the recorded
fallback through the scripted transport (one call, no retry, one bill, the chart
not claimed) and keeps `pipeline.make_plans()` to no ticket under synthetic
YELLOW and GREEN regimes with the gate reason `reader_coverage`. Its one labelled
control copies the same two findings' citations from the row's own reader
evidence (`checks.RE.values.bar_range_pct`, `checks.VOL.values.volume_vs_avg50`)
and shows them admissible, and refused again without a chart for that reason:
the refusal is the paths, never a corrected grade for HAE.

**Measured** (this sandbox, Python 3.11.15, on the final tree): 4026 collected, 3992 passed and 34 environment-gated skips in 17 m 53 s at `b96ed95f` (the test-only commit `5ece64a7` landed after that run began; its file passes 13/13 alone and the collection count is unchanged);
the two new files 25 passed; `tests/test_docs.py` 37/37 with the suite count at
4026; `python tools/evidence_review.py --check` current; no record or rule
moved, so the 13 page fixtures and every cascaded generator are untouched;
gitleaks 8.24.3 over the branch's commits with the repository's config: no
leaks. No browser change: the chart check and the page smoke are CI's, recorded
on the PR. One defect of mine, found by the first `--check` inside pytest: the
output directory was a relative path, so a test running from `tmp_path` compared
against files that did not exist; it is absolute now, as the findings builder's.

**Mutation pass.** Twenty mutants in the mutation worktree at the milestone commit, each judged by the whole test files naming the rule (no `-k`): over the authority contract, the grader and the planner as the HAE regression holds them -- the path rule admitting two-segment citations (4 failures), an authority refusal retried (12), the planner ignoring the reader (24), visual findings needing no chart (3) -- and over the review -- the sign touching zero, the drawdown path starting nowhere, the halves floored, adjacent sources counted, the cross-check never refusing, the floor at ten, the reader-accepted population widened to every answered reply, the cohort binding unchecked, months read as years, a pasted sum establishing a sign, disagreeing periods still supported, the study digest unbound, the night-means path dropped, the rendered sentence changed. All dead. Two controls survive: the HAE fixture README's wording and the tool's module docstring. A first "control" changed a sentence the renderer prints and died on the file comparison: not a control, counted above as a mutant. And the pasted-sum mutant first died only on the committed-file comparison -- the byte-equality kill the findings pass warned about -- so the rule has its own test now (`pasted_row` drives the sign, and the live build's ledger is held to the same rules as the committed one) and the mutant dies in it with the file comparison deselected.

**Keep / fix / defer / omit.** Keep: the review reads and never decides; its
criteria are archived in its output so a reader can disagree with them in
writing; the HAE control is synthetic and labelled. Fix if it bites: the ledger
is a fixed list in the tool, so a new floated change is a code change; the
halves split nights by count, not by calendar. Defer: re-run the review as
publications and the journal mature (the first journal row can resolve five
sessions after 12 October; a changed verdict is a changed file, which `--check`
shows); a GREEN night, which nothing here speaks to. Omit: any rule, threshold
or account change on these numbers; a budget or a dollar price in the review.

**Not claimable:** a live night; any trading edge. The first live research
observation can still exist Monday 12 October at 13:20 or 13:28 UTC, and the
evening after the #156 merge writes the first archived cost block.

## Checkpoint, 12 Oct 2026 — PR #157 accepted on the public site; the service read off the retained publications (#111)

**PR #157, accepted.** Merged as `c759a1e6` on `main` with a merge commit over
`ed23218f`, closing #109. The code head `5ece64a7` passed all seven checks on
Tests run 38187082296 (pytest, page, the historical-runtime central case
00:12–01:00 UTC and stress 00:12–00:40, the gate, both gitleaks runs); the final
head `6a402d68` (CLAUDE.md alone over it) passed pytest, page, the gate's
docs-only decision and both gitleaks runs on run 38187958520. Publisher
38190278545 printed *Verified: every one of the 41 public files matches
committed main* at 01:01:56 UTC; Pages 38190292804 deployed (38190278294
cancelled as superseded, as every merge does); the merge commit's own Secret
scan 38190278557 and Tests 38190278502 (pytest 01:02–01:18, page 01:01–01:17)
are green. **One red on `main` that was not #156's or #157's, read rather than
assumed:** the Tests run on the #156 merge commit (38185195670) failed its page
job 14516/14517 on `Play from the last night starts over -- got 2, want 1` in
the findings suite, while the same head's pull-request run and the #157 runs
over the same page passed it. The check clicked Play and read the step 120 ms
later under a 250 ms test interval, so a loaded runner reached the read after
the first tick, the shape the walkthrough suite's restart check already had
fixed (PR #123/#125): it reads the step inside the click's own task now and
then waits for the advance. Pytest was green on that commit, and both jobs are
green on `c759a1e6`.

**Revision.** Branch `claude/spicystock-historical-workflow-i53ud1` restarted
from `main` at `c759a1e6`, pushed as **PR #158**. #111's first deliverable
("track publication and morning-refresh success, latency, intended/measured
sessions, provider coverage, ... reader acceptance and allocated ticket count";
"keep service health separate from signal quality"). `docs/data.json`,
`docs/picks.json`, the compact reader, every receipt, the history, the evidence
objects, the quality ledger, the workflows and the vendored design system are
untouched; nothing under `src/` changed; no run, mail, dispatch, provider call
or credential.

**What was built.** `tools/service_health.py` is a reading of the service and
not of the signal: it walks the commits that put a publication on `main`
(`git log -- docs/data.json` through one pinned commit, whose committer time is
the reading's clock) and the commits that put a morning, issuer or research
receipt beside it, reads each real schema-2 record (the first build's 38
commits are set aside by name and counted), and writes per publication its
session, status, problems, `published_at`, run id, mail state, elapsed and
fetch seconds, the inputs' coverage and tolerance verdict, the reader's reads
and cost block, and its timing: latency after the session's completion (the
scheduled close plus `sessions.COMPLETION_BUFFER_MINUTES`; the archived
`calendar.measured.completion_at` is held equal to the calendar's and a
record without one is re-derived and says so), minutes after the evening cron's
nominal primary slot and whether after the retry slot (6:16 and 8:16 PM ET,
`datetime.combine` in the exchange's zone so the 1 November change is the tz
database's answer and no UTC hour is written), whether before the next
session's open, and how long the commit took after the record's own clock.
`session_rows()` gives one row per expected XNYS session from the first
retained publication's to the newest one's or to the newest session the clock
has reached, whichever is later, so a night the run missed is a row and not a
gap: due (completion at or before the clock), published, pending, overdue
(unpublished with its next open passed), revisions, the FIRST publication's
delivery facts as the service column, its regime and ticket counts as the
signal column that makes no service verdict, and the companion receipts bound
to the session its plans are for. `summary()` counts them, the streak of due
sessions published before the next open (longest and current), the latency's
min/median/max, the re-published sessions, the reads done of requested, the
cost blocks, and whether the newest publication is for the newest due session
(`fresh`). `--check` holds the two files under
`docs/input-truthfulness/2026-10-12-service-health-evidence/`: it re-reads the
commits the JSON names, fetching exactly those into a shallow checkout as the
findings suite fetches its own, and where the checkout carries the history
walks it again and requires the same commits read and set aside. The dated
report is `2026-10-12-service-health.md`.

**What the history establishes** (11 September to 9 October, pinned at
`c759a1e6`, clock 01:01 UTC on 12 October): 21 expected sessions, 21 published,
21 of 21 first publications before the next open, the streak 21 and 21; 26
publications, four sessions published more than once (11 and 21 September, 8
and 9 October, the last three times); latency after completion min 53.1,
median 261.9, max 362.1 minutes, and **14 of 21 first publications after the
retry slot** -- from 14 to 18 September the scheduled runs landed 6–9 minutes
after the primary slot, from 22 September every one landed 133–241 minutes
after it, a position of the publication and not an attribution to a cron
(the record does not know which slot fired); the commit landed 2–5 minutes
after each record's own clock. Statuses 19 degraded and 7 ok; inputs ready
4,753–4,776 of 4,775–4,796 where the ledger exists; the reader answered 265 of
302 requested reads; cost blocks archived 0 (the rule is #156's and the first
publication under it is the next evening's). The signal, kept apart: 21 RED and
5 YELLOW publications, 0 reaction tickets, 3 anticipation tickets, each
superseded. Companions: two morning receipts, both `inapplicable`
(`entry_window_ended` at 17:10 UTC on 9 October; `wrong_session` on the
Saturday for 12 October, before its open), three issuer receipts for 12
October, all `unavailable`, no research observation yet -- so **the acceptance
line's morning checks stand at zero observed**; the first scheduled attempts
are 13:20 and 13:28 UTC on Monday 12 October.

**Measured** (this sandbox, Python 3.11.15, on the final tree): 4049 tests collected; the full suite on the code head `a21de55a` 4014 passed, 34 environment-gated skips and one failure, the suite-count line, which the docs-only commit after it moves to 4049 (`tests/test_docs.py` 37/37 with it), 17 m 40 s; an earlier full run was voided by my own hand -- the committed reading was regenerated with a renamed summary key while the suite ran, so two tests read a file their already-imported module did not write, the hazard this file's standing rule names -- and is not counted;
`tests/test_service_health.py` 22 passed; `tests/test_docs.py` 37/37 with the
suite count at 4048; `python tools/service_health.py --check` current with the
history walked again; no record or rule moved, so the 13 page fixtures and
every cascaded generator are untouched; gitleaks 8.24.3 over the branch's
commits with the repository's config: no leaks. No page change beyond the
findings check, so the chart check and the page smoke are CI's, recorded on
the PR. The tests drive the arithmetic on hand-sized records -- the slots on
9 October and 2 November, the frame across Thanksgiving and the 27 November
early close, a publication's latency and slots at pinned instants and at the
boundaries (at the retry slot, at the next open, at the completion instant, at
the applicable open), a five-session week with a session published twice, one
never, one after the next open and one not yet due, a clock on a later session
and on a weekend -- a synthetic git history walked from its tip and from an
earlier commit, written and held by `--check` with a drifted number, a
rewritten markdown, a dropped commit and an emptied set-aside list each named,
a shallow rebuild that fetches the named commits and does not walk, and the
committed reading held to the commits it names and to the records read again
off them.

**Mutation pass.** Eighteen mutants over the tool in the mutation worktree at
the milestone commit, each judged by the whole test file (no `-k`): the slots
built in UTC instead of the exchange's zone, before-next-open inclusive,
after-retry exclusive, due strict, overdue ignoring the publication, the
service column reading the latest publication rather than the first, the streak
counting a late publication, the session range stopping at the last
publication, the rebuild ignoring the set-asides, `--check` ignoring the
markdown, the latency reversed, fresh needing no due session, output tokens
read from the uncached class, the walk's limit unchecked, a companion at its
open read as before it, the archived completion not held, receipts joined on
the measured session, revisions counted from zero. All eighteen die, each in
the test naming its rule; the control (a docstring word) survives. A second
pass over the set-aside commit, four mutants: a removed companion raising
instead of being set aside, the reason without its commit and path and the
shallow rebuild's set-aside guard dropped all die; **an unreadable receipt
raising instead of being set aside SURVIVED**, the second shape this file
names: the synthetic history had a removed receipt and no malformed one. It
has one now (a receipt without its binding), the mutant dies in the test that
names it at the pushed head, and the control (a comment) survives both passes.

**Keep / fix / defer / omit.** Keep: the reading reads git and the records and
decides nothing; the signal column never makes a service verdict. Fix if it
bites: the walk is bounded by `--limit` (128; the history is 68 commits now,
38 of them the first build's, set aside on every walk); the record does not
know which cron slot fired or when GitHub started the runner, so "after the
retry slot" is where the publication fell and the Actions log, by `run.run_id`,
is where the cause is. Defer: #111's site surface (a readable service state
and recovery guidance), its failure/recovery rehearsal and the ten-session
acceptance, which needs morning checks that have not yet been observed. Omit:
any change to the crons on these numbers; a status that reads the signal.

**Not claimable:** Monday's morning observation (13:20 or 13:28 UTC on 12
October), the first archived `run.reader_usage` block (the next evening's
publication), the ten consecutive sessions with morning checks, and any
trading edge.

## Checkpoint, 12 Oct 2026 — PR #158 accepted on the public site; the service's failures rehearsed, and its recovery (#111)

**PR #158, accepted.** Merged as `670a7fd8` on `main` with a merge commit over
`c759a1e6`. The code head `a21de55a` passed page, the historical-runtime gate,
both native cases (central 01:41–02:29 UTC, stress 01:41–02:30) and both
gitleaks runs on Tests run 38192799644, its pytest failing the suite-count line
alone (4048 passed); the final head `e701de33` (two CLAUDE.md-only commits over
it) passed pytest, page, the gate's docs-only decision and both gitleaks runs on
run 38194448238. Publisher 38196807225 printed *Verified: every one of the 41
public files matches committed main* at 02:42:16 UTC; Pages 38196820286 deployed
(38196806890 cancelled as superseded, as every merge does); the merge commit's
own Secret scan 38196807276 and Tests 38196807248 (02:42–02:56) are green.

**Revision.** Branch `claude/spicystock-historical-workflow-i53ud1` restarted
from `main` at `670a7fd8`, pushed as **PR #160**. #111's fourth deliverable
("rehearse provider, reader and publication failures; recover idempotently
without duplicate work, stale overwrite or unbounded calls") and the
"completed failure/recovery rehearsal" its acceptance line names.
`docs/data.json`, `docs/picks.json`, the compact reader, every receipt, the
history, the evidence objects, the quality ledger, the workflows and the
vendored design system are untouched; nothing under `src/` changed; no run,
mail, dispatch, provider call or credential.

**What was built.** `tools/recovery_rehearsal.py` drives `pipeline.run_evening()`
-- the real evening, every stage -- through the doubles the suite and the
fixture generator use (`tests/fakes.py`), over one synthetic market (the
suite's own night plus a second A+ burst, so the reader has two names to be
bounded over; eleven quiet names, a coil, the benchmark; inputs rounded as the
fixture generator rounds them), nine pinned nights from Friday 4 to Tuesday 15
September 2026, injecting one failure a night: the bars endpoint refusing every
batch, every frame served two sessions stale, the reader's account out of
credit (the provider's own 6 October wording), the reader's transport dead, the
mail provider refusing the digest, and Labor Day among them. Before and after
each night it executes the evening workflow's own guard -- the Python body of
`evening.yml`'s guard step, read off the workflow and run as written with the
clock frozen -- at the primary slot, the retry slot, the next session's open and
for a delayed event. Each night records the pipeline's exit code, status, stage
and failure, what was published and for which session, the cost and reads
blocks, the funnel's ticket counts, whether the previous publication's files
survived byte for byte (`previous.outcome`: `none`, `preserved`, `replaced`; a
night that published nothing and changed a file is refused, never recorded),
how many times each boundary was asked against the fetch's own bound (batches ×
2, one retry then dropped) and the grader's (names × `ATTEMPTS`), what was
mailed, and the guard's decisions in its own words. `--check` runs the whole
rehearsal again and holds both files; two runs here are byte-identical, the
clock fields the record carries nulled in the identity it keeps.

**What the rehearsal establishes.** Nine nights: six published, two failed
before publishing with the previous publication preserved, one skipped by the
calendar. Of 22 guard decisions, the ten admitted were the slot before each
night with a session and the retry slot after each failure; **zero** were
admitted after a publication -- a degraded publication and one whose mail
failed are publications, and the retry slot after each was refused as already
published. A delayed event for the 4 September slot over the 8 September
publication was refused ("A newer session than 2026-09-04 is already
published"); recovery at the next open was refused as expired, twice. The bars
endpoint was asked twice on the outage night and once on every other; reader
calls stayed within names × 2 every night, the empty balance stopping them
after one (the second name a fallback row without a call), the dead transport
costing exactly four. The retry slot after the outage was admitted, published
the missed session once, and the same slot asked again and a delayed primary
event for the same evening were both refused. What it does not establish: how a
real provider fails, when a runner starts (the service reading records 14 of 21
first publications after the retry slot), whether GitHub accepts the commit or
Pages serves it; the persist step, the publication gate and the morning
collectors are not driven.

**Measured** (this sandbox, Python 3.11.15, on the final tree): the full suite on the code head `faa94bba` 4030 passed with 34
environment-gated skips and two failures in 17 m 25 s -- the two
warning-capturing publication tests, silenced because the tool's command-line
path had set the root logger to ERROR and the new CLI test runs before them;
CI's pytest on that head found the same two (4064 passed); reproduced on the
three tests alone, fixed by saving and restoring the caller's level around the
command and pinned by a test that reads the level inside the run and after it;
on the fixed tree `94484095` 4033 passed with 34 environment-gated skips in
17 m 36 s;
`tests/test_recovery_rehearsal.py` 18 passed in 10 s; `tests/test_docs.py` and
`tests/test_workflows.py` 87 passed with the suite count at 4067;
`python tools/recovery_rehearsal.py --check` current; no record or rule moved,
so the 13 page fixtures and every cascaded generator are untouched; gitleaks
8.24.3 over the commit and the new files with the repository's config: no
leaks. No page change, so the chart check and the page smoke are CI's,
recorded on the PR.

**Mutation pass.** Nineteen mutants over the tool in the mutation worktree, each judged by
the whole `tests/test_recovery_rehearsal.py` with the committed-files byte
comparison deselected, so each dies in the test naming its rule (the byte
comparison IS the rule's test for one, the identity keeping the clock fields,
and it was judged with it). At the code head `faa94bba`, sixteen: a changed
file on a night that published nothing recorded as preserved; the outcome
ignoring whether the night published; the bars bound without the retry; the
guard's clock not frozen; the guard asked as a manual dispatch; the next-open
expiry check dropped; the reader bound strict; a newer-session refusal counted
as already published; every after-slot counted as admitted; the bars failure
and the stale frames left in place between nights (the latter killed broadly,
because the reset is the only registration); the outage injecting a transport
failure instead; the credit text without the provider's marker (four calls
instead of one); the identity keeping the clock fields; `check()` ignoring the
markdown; `--check` exiting zero on a problem. All sixteen die; two controls (a
docstring, the quiet level) survive. At the fix `94484095`, three more: the
logger restore dropped (dies in the test the fix added), the stale frames kept
across nights by carrying the benchmark's staleness forward (the sharper form,
dying in the night-after test alone, with the summary and the CLI run behind
it), and the identity's clock fields again; two controls (the docstring, the
restore's comment) survive.

**Keep / fix / defer / omit.** Keep: the rehearsal injects and records, and
decides nothing; a night that published nothing and changed a file is refused,
not reported. Fix if it bites: the market is fixed and every night's bursts
recur, so the ticket counts are the allocator's accounting over recurring
names and not a market fact; the outage night sleeps the fetch's own
`RETRY_WAIT_SECONDS`. Defer: #111's site surface (a readable service state and
recovery guidance) and the ten-session acceptance, which needs morning checks
not yet observed; a rehearsal of the workflow's persist step and the publication
gate, which need a runner. Omit: any change to the crons, the retry bounds or
the guard on these numbers; a rehearsal that calls a provider.

**Not claimable:** Monday's morning observation (13:20 or 13:28 UTC on 12
October), the first archived `run.reader_usage` block (the next evening's
publication), the ten consecutive sessions with morning checks, and any
trading edge.

## Checkpoint, 12 Oct 2026 — PR #160 accepted on the public site; the service state read off the record, and the recovery window the page names (#111)

**PR #160, accepted.** Merged as `c174818e` on `main` with a merge commit over
`670a7fd8`. The fixed code head `94484095` passed all seven checks on Tests run
38199735910 (pytest 03:26–03:37 UTC; page 03:26–03:42; the historical-runtime
gate; the central case 03:27–03:58 and stress 03:27–04:16; both gitleaks runs);
the final head `911a58d7` (CLAUDE.md alone over it) passed pytest, page, the
gate's docs-only decision and both gitleaks runs on run 38200988502. Publisher
38203153703 printed *Verified: every one of the 41 public files matches
committed main* at 04:17:24 UTC; Pages 38203168312 deployed (38203153082
cancelled as superseded, as every merge does); the merge commit's own Secret
scan 38203153715 passed and its Tests run 38203153660 (04:17–04:34) are green.

**Revision.** Branch `claude/spicystock-historical-workflow-i53ud1` restarted
from `main` at `c174818e`, pushed as **PR #161**. #111's third deliverable
("show a readable service state and recovery guidance on the site") and the
"visible outage/staleness behavior" its acceptance line names. `docs/data.json`,
`docs/picks.json`, the compact reader, every receipt, the history, the evidence
objects, the quality ledger, the workflows and the vendored design system are
untouched; no run, mail, dispatch, provider call or credential.

**What the page did before, read rather than argued.** `status()` decided
pending against stale with `PENDING_UNTIL_HOUR = 21`, a 9 PM ET constant whose
comment named the retry cron, while the service-health reading had just
established that 14 of 21 first publications landed after the retry slot and
the latest 362 minutes after completion (10:17 PM ET): on most nights between
9 PM and the publication the page read *STALE · 1 session behind ... check the
run log* over a run that was merely late, and on a Saturday morning after a
missed Friday it said the same with no word of what the service would still do.
The evening guard's own rule, rehearsed in PR #160, is that a delayed or
retried run may publish a missed session until the next session opens and
never after; the page knew nothing of it.

**What was built.** `src/delivery.py` writes `run.delivery` (version 1): the
measured session's completion, the publication instant copied verbatim, the
latency in minutes (rounded once to a tenth), the evening workflow's two slots
as instants in the exchange's zone (`EVENING_PRIMARY_ET` 18:16,
`EVENING_RETRY_ET` 20:16, the one rule `tools/service_health.py` now imports
and `tests/test_workflows.py` holds the four crons to on both sides of the
November change), which of them the publication followed (`before_primary`,
`after_primary`, `after_retry`, the slot itself inclusive), the next session
and its open and whether the publication came before it, the policy words
(`primary_et`, `retry_et`, `timezone`, `recovery_until: next_session_open`)
and one sentence of facts with no verdict in it. `pipeline.RULES` archives the
version, both slot times and the recovery policy (`pipeline.delivery_*`), so
`rules_version` moves and `report.validate()` holds a block to the slots ITS
record archived (`delivery.faults()`: present under rules that write it,
every field re-derived from the run's own session and instant, a differing
field named, an unknown archived version named rather than guessed, absent
without a fault for every record from before). The mail prints the sentence
under *// delivery*; the service-health reading holds an archived block to its
own re-derivation and records `delivery_basis`, its committed reading
regenerated pinned to the same commit with that field alone added.

**The page.** `deliveryOf()` reads the block whole or not at all (every field
the drawing indexes into, the policy's HH:MM words, its timezone against the
clock the page compares in, a recovery policy the page has a sentence for).
`status()` no longer carries an hour: one session behind, the expected
session's NEXT open on the record's own calendar is the boundary -- before it
the session is pending however late the clock is, naming which slot the ET
clock has passed in the record's words (*tonight's run pending* with the first
slot ahead or the retry slot ahead; *run pending · past both slots* with the
window's end named and the run log linked), and after it the session is stale
and *will not be published now*. A record from before the block names no slot
and still reads the window off its calendar. `evaluationExplanation()` names
the window for every pending record and the passed slots when the record
archived them; `reclock()` repaints when the sentence changes, not only the
chip. The Method view prints the delivery sentence and the archived schedule
with the page's one sentence per recovery policy (`RECOVERY_WORDS`, held equal
to `delivery.RECOVERY_POLICIES` by `tests/test_docs.py`, which also holds the
page to no fixed pending hour); the run strip's published stat carries the
latency the record wrote.

**Measured** (this sandbox, Python 3.11.15, Node 22, Chromium through Playwright
1.56.1): 4103 tests collected; the full suite on the final head 4069 passed and 34 environment-gated skips in 19 m 46 s (run in the mutation worktree at the same commit, beside the smoke);
13 page fixtures regenerated and current, and every cascaded generator
regenerated and current (issuer-evidence 30, stop-research 22,
research-outcomes 40, research-observations 12, cash-preview 6; morning
pinned, 21 current); `tools/recovery_rehearsal.py --check` current after its
evidence was regenerated (each night's publication identity carries the rules
digest, which moved); `tools/service_health.py --check` current with the
history walked again; continuity 137; the chart check 378/378; the new
`service` suite 278/278 at 1280 dark, 390 light and 320 dark over the `full`
night, a routed copy from before the block, a half-written one, one archived
under 7:16 / 9:16 PM slots, and sixteen shapes the block check refuses one at a
time; the `states` suite 209/209 with its stale clock moved to Monday after the
open and three pending clocks at the hours the page used to call stale; the
`wait-explanations` suite 775/775 with its Monday-night and Tuesday-morning
cases inside the window; the full smoke with `--shots` 14873/14873 in 20 m 10 s. Screenshots
at 1280, 390 and 320, both themes, were looked at: the Method block's delivery
and schedule lines, the Saturday pending notice with its run-log link, the
Monday stale notice naming the window's end. gitleaks 8.24.3 over the branch's
commits with the repository's config: no leaks.

**Mutation passes.** Python, each mutant in the mutation worktree at the
milestone commit and judged by the whole test files naming the rule (no `-k`;
the pipeline mutants by the clean-night tests, the validator's and the mail's
by `tests/test_report.py` in full): sixteen -- the slot boundary made
exclusive, the next open made inclusive, the slots built in UTC, the
re-derivation skipped, the archived slot ignored for the code's own, the
version unchecked, the recovery policy unchecked, the slot words swapped, the
latency rounded to whole minutes, the archived slot misspelt, the sentence
dropped from the block's fields, the block dropped from the run, the validator
not asking, the mail block dropped, the service reading on its own hour, and
the archived block unheld there. All sixteen die, each in the test naming its
rule; the two controls (a docstring, a comment) survive. Browser, through
routed copies of `app.js`, the tree never written: sixteen over two passes.
Eleven died at once -- at the open still pending, the retry slot never passed,
the policy's timezone unchecked, a legacy record naming a slot, the stale
sentence without the window, the pending word back to "tonight", the Method
line for a legacy record, the strip's latency dropped, the explanation without
the window and the explanation naming a slot for a legacy record -- and one,
the half-written policy accepted, died by a throw that ended the suite (the
status probe reports a throw as a named failure now, and it dies on ten
checks). **Four SURVIVED the first pass, two holes of the second shape this
file names:** `fixed_hour_back` and `states_boundary_hour` (the old 9 PM rule
reinstated) lived because no pending clock in either suite sat at or after
9 PM ET -- the very hours the old page called stale -- so Friday 9:00 PM,
Friday 11:30 PM and Sunday 10:00 PM ET are pending cases now, and the states
suite has Friday 10 PM; `slot_in_sentence_hardcoded` and
`method_schedule_hardcoded` (the page spelling 6:16 and 8:16 itself) lived
because every record carried those slots, so a routed record archived under
7:16 / 9:16 PM holds every slot word on the page to the record. All four die
(42, 3, 1 and 1 checks); the control (a comment) survives both passes.

**Keep / fix / defer / omit.** Keep: the block says where a publication fell
and the page says what the service will still do; neither decides. Fix if it
bites: the slot phase on the page is an ET wall-clock comparison through
`etParts()`, so a record archived under another timezone names no slot (the
block is refused whole, by design); a session whose next open is outside the
±45-day browser schedule reads stale without the window's end named. Defer:
#111's ten-session acceptance, which needs morning checks not yet observed.
Omit: any change to the crons or the guard; a countdown.

**Not claimable:** Monday's morning observation (13:20 or 13:28 UTC on 12
October), the first archived `run.reader_usage`, `run.funnel` and `run.delivery`
blocks (the next evening's publication), the ten consecutive sessions with
morning checks, and any trading edge.

## Checkpoint, 12 Oct 2026 — current public release reconciled; observation fidelity correction #159

The pause advanced `main` to `c759a1e671227717cae8d0bf1d50a4121d167396`
through PRs #154–#157. #154 ships a different implementation of #151.
The locally prepared `a328b6b4` and tree `d5c3883e` were never published to a
branch or PR; an immutable API tree object alone is not a release. Preserve
that old preparation as history and do not transplant it over the shipped code.
The same applies to superseded local review-layout preparation `203fa3cd`.

Independent read-only reconciliation found each PR's final tree equal to its
merge tree. Applicable final-head checks passed. On #154, #156 and #157 the
native matrix was skipped by the existing observed-docs-only gate; predecessor
native/memory passes and the exact intervening source differences were checked,
not described as new executions on the final heads. #155 passed all seven
checks on its exact final head. No formal GitHub approval is invented. The
latest main Tests run `38190278502` passed 4026 Python, 14517 page and 378 chart
checks; publisher `38190278545` verified all 41 public files and final Pages
`38190292804` passed. #156's earlier post-merge page failure remains recorded:
the findings Play test raced its first tick, which active PR #158 addresses.

Actual public verification of `c759a1e6` at 02:00 UTC passed 107 checks, matched
41 assets, and inspected 14 captures on desktop and phone. The default clock
and public data were unmodified. KE/PSNL observation requests actually returned
404 with explicit unavailable wording; no quote, cash, execution or profit was
invented. Zero baseline tickets, pending journal rows and the original research
sizes remain. The old record truthfully has no archived funnel or token bill.
There were no unexpected browser errors or private-storage writes. Two initial
runner expectation errors were corrected only in the temporary audit harness
and retained separately from the final acceptance. Phone search is still below
the first screen; this release does not claim to solve that navigation gap.
`release-evidence/2026-10-12-public-reconciliation/acceptance.json` preserves the
public proof and hosted audit with their exact identities and scopes.

PR #158 at `1836d6ff` is another builder's active service-health milestone.
Independent source review and 60 local service/docs tests ran without editing
its worktree. Additional isolated probes found two issues the existing tests
miss: service delivery metrics use embedded generation time rather than commit
landing time, and syntactically invalid historical JSON aborts instead of being
named under skipped records. Choosing the first delivery also needs landing-time
ordering. No retained record changes its before-open classification, but actual
commit-latency min/median/max is 55.8/266.7/367.0 minutes versus the reported
53.1/261.9/362.1 generation latency. All 69 examined history JSON blobs parse;
no actual malformed record or late-open incident is claimed. Independent
receipts are embedded in the reconciliation file. These findings remain open;
this branch does not modify the concurrent service tool or its report.

Issue #159 is the independent next deliverable. On the shipped research
implementation, real-SDK/fake-HTTP probes made four HTTP attempts while the
receipt reported one; producer-generated microsecond boundary receipts disagreed
with browser parsing; forged spread percentages were rendered; missing credentials
still printed one request; and a subnormal locked quote divided by zero. All
are isolated executable findings, not reports of a live provider failure.
The correction keeps the shipped schema, cohort bindings, strategy, schedules,
private records and pinned design system. No production collection is needed.
Local final checks, exact-head review, hosted gates and public acceptance for
#159 are pending until explicitly recorded below.


### #159 local acceptance, 12 Oct 2026

The research-only transport now makes one counted, streamed HTTPS attempt to
Alpaca's fixed IEX snapshots endpoint, with no retry, redirect or pagination.
It prepares headers and the environment's TLS/proxy settings before counting
an attempt, caps decoded input at 256 KiB, and enforces the remaining existing
180-second collection budget with the POSIX main-thread timer. Unsupported or
busy timer/configuration preflight refuses without replacing previous evidence.
The evening and normal morning SDK paths, schedules and publication rules are
unchanged. A nonpositive or nonfinite computed quote midpoint is invalid, so a
subnormal locked quote cannot crash the collector.

The browser preserves timestamp microseconds and offsets at the 60-second age
and 5-second future boundaries, verifies both recorded spread fields against
bid/ask, preserves legitimate producer rounding, and reports zero or one actual
request. Prices and statuses are explicitly described at collection time.

Final-source local evidence: 26 transport checks, 17 quote checks, 40 independent
backend controls (including six real Requests/urllib3 loopback controls), 360
pinned browser checks, 24 exactly reproduced producer fixtures, 450 additional
producer/browser numeric comparisons, and 235 independent DOM controls passed.
Eight transport, one midpoint and eleven browser targeted mutations failed their
named guards; each unrelated control passed. Three final browser captures were
inspected. Continuity passed 137 offline DOM/store checks; its initial missing
jsdom dependency was fixed in the ignored local environment and is not counted
as a product failure. Docs passed 37 tests; collection found 4056 tests. A broad
190-test run imported earlier transport source and is retained only as
supplementary history, excluded from final-source acceptance. No whole-suite
local pass is claimed. Source identities, raw receipts, limits and earlier
release reconciliation are preserved under
`release-evidence/2026-10-12-observation-fidelity/prepared.json`.

This is local preparation, not hosted acceptance or a public release. Exact
remote head review, CI, merge, publisher, Pages and actual public verification
must be read back before claiming #159 shipped. Public observations are still
absent at the last actual 02:00 UTC read. No live quote or trade is inferred
from fixture controls. Next: finish that release chain, then resolve the
independent #158 delivery-clock/history findings when its builder is finished,
or improve the first-screen ticker path without changing trading authority.


## Checkpoint, 13 Oct 2026 — resume #159 over the new publication

The earlier #159 preparation at `04fc0a70` was reviewed locally but never
published as a commit, branch or PR. Its API tree `0416eece` exists; that is
not a release. The branch is now rebased onto
`0cbeada9ea25236e97e79eb19b1c5ee05b6b03a3`, preserving PRs #158, #160 and #161,
the October 12 evening publication and the subsequent issuer receipt. No open
PR or competing #159 builder was found at the 04:04 UTC read. The only manual
rebase conflict was CLAUDE.md: both sets of checkpoints are retained, and the
current collection count is 4133. Runtime correction files are byte-identical
to the independently reviewed preparation. Existing fixtures regenerated by
#161 remain current; their changed publication bindings need fresh browser
verification, not a reuse of the old acceptance claim.

Monday's scheduled morning runs did not deliver quotes. The 13:20 and 13:28 UTC
runs `38312550090` and `38312772384` were created at 21:44:56 and 21:47:04 UTC,
respectively; their guards reported `entry_window_ended` and all collection and
retention steps skipped. The inactive winter-slot pair also skipped. Successful
Actions conclusions are not successful morning collection. No manual dispatch,
provider call or email was made to manufacture an observation. The optional
research receipt remains absent at the initial October 13 public read.

The new evening record is measured October 12 and applies October 13. Its real
funnel, reader usage and delivery blocks now exist. The initial read finds zero
baseline tickets and two completed research reviews; current hypothetical
allocation-fit research is QUAD/GTE, while the retained KE/PSNL journal has its
first dated no-fill observation. These are public model records, not Mo's
executions. Full current public acceptance and final #159 local/hosted/release
readbacks are recorded separately when completed. The prior dated preparation
receipts remain historical source-bound evidence, not checks on this rebased
head. Next release must retain the actual scheduling gap and unknown issuer
coverage explicitly.


### #159 acceptance after rebasing

The rebased runtime passed 26 transport tests, 17 quote tests and 40 independent
backend controls, including six Requests/urllib3 loopback controls without any
provider traffic. All 24 producer fixtures remain exactly current. The pinned
Playwright 1.56.1 / Chromium 141.0.7390.37 run passed 360 browser checks, 137
continuity checks and 235 additional DOM controls. Three final captures were
inspected. Independent rebase review passed 39 integrity/scope checks with no
findings and preserved all 19,981 other current-main tree entries. Python
3.12.14 collected 4133 tests; current docs passed 38. The old mutation receipts
still pin identical feature runtime/test sources; their execution date is not
changed into a new run. Final rebase receipts and source hashes are retained in
`release-evidence/2026-10-13-observation-fidelity/prepared.json`. These local
results do not claim hosted or public acceptance for the correction; those
remain required on the final published head before merging and releasing it.


### #159 CI repair — preserve the dated review inputs

PR #162's original head `8ae8f0adc63daee746b37a8ec7c309de1abc1e42`
failed the required pytest gate: 4131 passed and two dated evidence-review
checks failed. The October 12 evening publication had advanced the rolling
research cohort and journal, while `tools/evidence_review.py` still read them
into the October 12 historical report. Both failures reproduce on the
unchanged base inputs; the gate stays binding. Page checks passed 15007/15007,
chart checks 378/378 and DOM/store continuity 137/137 on that original head.
Those outcomes are historical checks on that head, not acceptance of the repair.

The repair retains the exact original cohort and journal bytes under the dated
review's `inputs/`, verifies their digests from one read, and records original
commit/path provenance. Missing or changed inputs refuse before writing; rolling
publications can advance independently. Every historical numeric result and
verdict remains unchanged, as do today's live cohort, journal and publication.
The outer report and README now describe a frozen October 12 review. A later
evidence review needs separately dated outputs. No configuration changes apply;
`.env.example` remains correct.

Local repair acceptance passed 23 focused tests, 25 independent controls and
`--check`. Four named isolated mutations failed their intended guards; baseline
and unrelated controls passed. Python 3.12.14 now collects 4143 tests. The
source-bound receipt is `release-evidence/2026-10-13-observation-fidelity/dated-review-repair.json`.
The quote-fidelity runtime is byte-identical to the prior reviewed source.
Independent final-tree review, all applicable hosted checks and actual public
verification remain required on the new head; this entry does not claim release.

## Checkpoint, 13 Oct 2026 — PR #161 accepted; the first live nights read; the publication's own missing stocks, asked for once more (#111)

**PR #161, accepted.** Merged as `4bd38751` on `main` with a merge commit over
`c174818e`. The code head `839f5d19` passed all seven checks on Tests run
38208300516; the final head `f98359ad` (CLAUDE.md alone over it) passed
pytest, page, the gate's docs-only decision and both gitleaks runs on run
38208316663. One gitleaks run on `839f5d19` (38208300486) failed on a race
with the checkpoint push -- `Invalid revision range 3f086182^..f98359ad`, 0
bytes scanned -- and was explained on the PR. Publisher 38212808053 printed
*Verified: every one of the 41 public files matches committed main* at
06:31:00 UTC on 12 October; Pages 38212827405 deployed (38212807387 cancelled
as superseded); the merge commit's own Secret scan 38212808057 passed.

**The first live morning, read.** Both 12 October morning crons were created
8 h 24 m late (13:20 and 13:28 UTC slots; runs 38312550090 and 38312772384 at
21:44:56 and 21:47:04 UTC), their guard said `entry_window_ended`, and every
collection step skipped: no morning, research or recovery observation exists
yet. No 13 October morning run had been created by 14:58 UTC.

**The first live night under every new block, read.** Session 12 October, run
38339720035, published 03:02:09 UTC on 13 October: `run.delivery` 407.2
minutes after completion, after both slots, before the 13 October open.
`run.status` `ok` beside a degraded acceptance, the first live night the
tolerance kept green: 4,767 of 4,778 ready, eleven stale stocks named in full
(BEBE, ELLO, HFBL, MDRR, MGRT, NCEW, PFX, RAND, ROMA and TCBS ending 9
October, WBD ending 5 October) within the limit of 47; `run.stale_followup`
version 2 read WBD at the four sessions it missed (6–9 October), still missing
at each. YELLOW (10-session ratio 1.0; up 50% in a month hot, 14 against
11.2). `run.reads` 2 of 2, `complete`. The first archived `run.reader_usage`:
2 calls for 2 names, 14,734 input tokens (8,062 uncached, 3,336 written to the
cache, 3,336 read) and 1,357 output, under claude-sonnet-4-6. The first
archived `run.funnel`: 362 reaction candidates, every one below YELLOW's A+
band, 0 potentially usable, 0 tickets; anticipation 751 momentum names, 5
listed, 1 refused for a known event and 4 for the stop rule at the limit, 0
tickets.

**Revision.** Branch `claude/spicystock-historical-workflow-i53ud1` restarted
from `main` at `4bd38751`, `main` merged in again at `289ab4a1` (the 12
October publication, the issuer receipt, and #162's research-observation
fidelity), pushed as **PR #165**. #111's bounded same-session source-recovery
study. `docs/data.json`, `docs/picks.json`, the compact reader, every receipt,
the history, the evidence objects, the quality ledger and the vendored design
system are untouched; nothing the evening runs changed
(`pipeline.build_rules()` nests no rule of the new module, so `rules_version`
does not move); no run, mail, dispatch, provider call or credential.

**What the record showed.** The 9 October session was published three times
under one universe identity: 22 stale stocks at 01:44:58 UTC on 10 October,
one at 07:12:55, the same one at 07:30:15. The same provider, asked again five
and a half hours later over the same selection, returned 21 of the 22 -- as
two whole evening runs. The three share the universe, snapshot, feed,
adjustment and session but not the rules digest (#115 and #121 merged between
them), so `same_cohort()` refuses each pair while the bars request's own
fields agree.

**What was built.** `src/source_recovery.py` freezes the record's own basis
(`frozen_basis()`), takes the window off the publication's own calendar
(`window_of()`), copies its coverage facts (`original_facts()`) and names the
deficits (`deficits()`): the record's tolerance names FIRST, the publication's
quality-ledger exception membership SECOND, each held to the publication's own
count and identity per category, never a guess. `_reason()` names every
zero-call case before anything is asked. One request of at most two attempts
over at most 100 names goes through `market_data.download_bars` under the
record's feed, adjustment and lookback (`_fetch()`), the call under a
main-thread timer set to the earlier of `FETCH_RESERVE_SECONDS` short of the
300-second budget and the next open. Each row is the stock's own outcome
(`_rows()`); `original` and `recovered` are never combined (`sentence_of()`).
`validate_receipt()` re-derives what the bound inputs determine, compares it as
JSON, and holds what only the provider determines to its shape and to every
field it implies. `.github/workflows/source-recovery.yml` runs it at 07:37 and
09:37 UTC on `main`, its persist job running whatever else happened, and the
dashboard publisher now follows it. `tools/publish_morning.py --target
recovery` commits one file with compare-and-swap on the record, the ledger
entry on `main` and the prior receipt. `tools/service_health.py` reads it as a
fourth companion. `docs/app.js` prints one Method line, *Recovery: <the
receipt's sentence>*, after hashing the loaded publication against the
receipt's binding.

**The first review by execution** (the collector, over the first pushed tip)
returned four findings and five surviving mutants, all fixed before the second
push: the provider call had no bound of its own (the SDK retries a 429 or 504
inside one call), a benchmark-only deficit read as `deficit_not_named`, a
partly named night and an unreadable bar had no words of their own, and five
mutants lived because the tests read only the committed fixtures, closed by a
test that collects each outcome fresh. A browser mutant then found a real
defect: a redraw of the Method view left its new line loading; each drawn line
is asked once now.

**The second review by execution** (five dimensions over `dd3314a9`, each
finding reproduced by a finder and checked by two skeptics) returned 22: 17
upheld by both, 5 split one each way, and all 22 reproduced again here before
they were touched. The high one: the recovery rode the morning workflow
as its third collector, about ten minutes before the open on time, and the 12
October crons started 8 h 24 m late; it has its own workflow now. The
mediums: a call answered after the open was published as before it (the open
bounds the call now, and an answer after it is not kept); zero volume was
counted beside the bars that pass the session rules when the placeholder had
failed them; "in N requests" undercounted the SDK's retries and pages (it says
calls to the bars endpoint, and `LIMITS` names what is not counted); 23
validator checks had no test (each has a forgery refused by its own message
now); a manual dry-run dispatch spent a request it could never record (the new
workflow has no rehearsal input); a 500, a timeout and a truncated receipt all
read "no receipt has been published" on the page (only a 404 says that now);
an open tab never saw a receipt published the next morning, and a reload could
serve the cached one (the page reads past the cache and again on an unchanged
update check while Method is shown); the page suite never loaded the compact
reader production serves, so breaking its digest binding passed every check;
and the report promised a first receipt on mornings already past. The lows:
the timer armed outside its `try`, so an expiry at the wrong instant leaked the
handler or turned an answer into a timeout; a prior receipt of another
publication and schema blocked collection; the size bound measured compact
bytes while the indented ones are written; a zero-attempt timeout said the
stocks were asked for; `True` and `4774.0` passed for `1` and `4774`; the
rehearsal, `context_sha256` and `published_at` clauses on the page had no
case; the page's status list was not held to the module's; and four wrong
sentences in the report. The publisher also refuses a repeated inapplicable
receipt for the same publication and reason now, so the daily schedule commits
at most one receipt per publication and reason.

**Measured** (this sandbox, Python 3.11.15, Node 22, Chromium through
Playwright 1.56.1, at `aed055c7`): 4258 tests collected, 4224 passed and 34
environment-gated skips in 23 m 32 s; 13 page fixtures current and every
cascaded generator current (morning 21, issuer-evidence 30, stop-research 22,
research-outcomes 40, research-observations 24, cash-preview 6, source
recovery 20); `tools/service_health.py --check` current with the history walked
again; continuity 137; the chart check 378/378; the `recovery` suite 124/124,
its failure-state and refresh cases red on the page from before the fix; the
full smoke with `--shots` 15131/15131; gitleaks 8.24.3 over the branch's
commits: no leaks; actionlint over the three changed workflows: clean.
Screenshots of the Method line at 1280 dark, 390 light and 320 dark were looked
at: one column on the phone, under the service schedule, "in 1 call to the bars
endpoint". The continuity check first exited 1 here because this worktree had
no `jsdom` installed; with the existing install linked it passes.

**Mutation passes.** Page, through routed copies of `app.js` judged by `--only
recovery`: ten mutants -- the projection's digest ignored, the reader digest
unchecked, a rehearsal admitted anywhere, the context and publication-time
clauses dropped, the HTTP cache allowed, no re-read on an unchanged update,
every failure read as absent, a parse error read as absent, a re-read away from
Method -- all dead, a control green. Python, each mutant in the mutation
worktree at `500fc060` and judged by the whole test files naming the rule (the
committed-fixture equality deselected, so each dies in the test that names its
rule): twenty-four -- an unrelated prior refused and one of this publication
accepted unread, the timer armed outside its `try` and raising when disarmed,
the open not capping the call, an answer after the open kept and validated, a
request window without a call written and unchecked, the zero-call sentence
dropped, the open's words never used, the tallies, the original facts and the
window compared by Python's `==`, a flat flag of `0` admitted, zero volume
counted beside the session-ready clause, the size bound on compact bytes, and
five of the checks the review found untested (the inapplicable source, the
duration bound, the symbols requested, the row category, a missing row's
ending), with the publisher committing an unchanged receipt and raising on an
unrelated prior -- all dead, two controls green.

**Keep / fix / defer / omit.** Keep: the receipt reads and never decides; the
record is unchanged by it; `original` and `recovered` are never one figure.
Fix if it bites: the ledger entry is read whole (up to 8 MiB) to name a few
stocks; the second slot may spend once more after a first slot whose persist
was refused, which `LIMITS` says; GitHub's scheduled starts are late by hours
on some days, and nothing here can make them punctual. Defer: #111's
ten-session acceptance, which needs morning checks not yet observed; a reading
of the receipts across nights once there are some. Omit: any change to the
stale tolerance, the coverage denominators or the scan on a recovered bar; a
late bar treated as a signal.

**Not claimable:** a live receipt. The first can exist on the first scheduled
slot after the merge whose publication's next open is still ahead, only if
GitHub starts it before that open, and only with the Alpaca pair present. Read
its status, reason, rows, call count and the page's line, and record them here.
Also still not claimable: a live morning or research observation, the ten
consecutive sessions with morning checks, and any trading edge.

## Checkpoint, 13 Oct 2026 — PR #165 accepted; the service read by the commit that landed it (#111)

**PR #165, accepted.** Merged as `279ec5a3` on `main` with a merge commit over
`289ab4a1` (the merge of #162). The code tip `aed055c7` passed all seven checks
on Tests run 38417767071 (pytest 14:56–15:22 UTC; page 14:56–15:11; the gate;
the native stress case 14:57–15:25 and central 14:57–15:47) and Secret scans
38417767097 and 38417758819; the final head `849fd510` (CLAUDE.md alone over
it) passed pytest, page and the gate's docs-only decision on run 38425035651
and both gitleaks runs. Publisher 38428819520 printed *Verified: every one of
the 41 public files matches committed main* at 16:15:21 UTC; Pages 38428851261
deployed (38428818848 cancelled as superseded, as every merge does); the merge
commit's own Secret scans 38428819611 and 38428944632 passed, and so did its
Tests run 38428819598 (page 16:14–16:31 UTC, pytest 16:14–16:39; the native
cases skipped by the gate, as a merge's are). The
source-recovery workflow (id 383411937) is registered and active; its first
slot is 07:37 UTC on 14 October. **No 13 October morning run had been created
by 16:26 UTC** (the 12 October ones were created at 21:44 and 21:47 UTC), so
the morning checks still stand at zero observed.

**Revision.** Branch `claude/spicystock-historical-workflow-i53ud1` restarted
from `main` at `279ec5a3`. The service-health findings the 12 October
reconciliation recorded and left open while PR #158's builder was working.
`docs/data.json`, `docs/picks.json`, the compact reader, every receipt, the
history, the evidence objects, the quality ledger, the workflows and the
vendored design system are untouched; nothing under `src/` changed; no run,
mail, dispatch, provider call or credential.

**Reproduced first** (`scratchpad/landing/repro.py`, synthetic histories
through the tool as it stood): a record generated at 13:25 UTC and landed at
13:40, after a 13:30 open, read `before_next_open: true`; a session whose
later-generated run landed first named the other as its first delivery, while
`main` had carried the first to land; and one commit whose `docs/data.json` was
not JSON stopped the whole walk (`read_at()` ran outside the `try` that sets a
commit aside). Over the committed reading, the commit-landing latency was
55.8/266.7/367.0 minutes against the 53.1/261.9/362.1 it reported.

**Changed** (`tools/service_health.py`, version 2, `service_health_v2`). Every
delivery fact is the commit's landing -- the committer time of the commit that
put the record on `main`, which the push follows by seconds and Pages later
still, so a lower bound on when a reader could see it: latency after
completion, the minutes after the primary slot, after the retry slot, before
the next open, the streak and the summary. The record's own `published_at` is
kept beside it as `generated_latency_minutes` and `generated_before_next_open`,
and the companions' `before_applicable_open` is the landing's with
`generated_before_applicable_open` beside it. A file that is not JSON
(`read_at()`'s `NotJSON`, named `<commit>:<path>: not JSON: ...`) or a record a
reader indexes past (`UNREADABLE` takes `LookupError`) is set aside by name with
its reason, as the first build's records are.

**The review, worked.** A reviewer by execution over the first pushed tip
(`133612de`) returned eleven findings, each reproduced here before it was
touched; ten are fixed and one is recorded. Ordering by committer time was
still a clock: a child commit dated inside its parent's second, or behind it,
was ordered before it and named the first delivery. The walk is `--topo-order`
now, each reading carries its place in it (`sequence`), and `landing_order()`
reads that and no clock. A truncated record on `main` read as fresh, because
fresh compared the newest record that could be read; `main_carries()` names the
newest commit that changed the record, read or set aside, the committed reading
names it (`source.record_head`) and `--check` holds it to the walk, and fresh
needs it readable and for the newest due session. Moving `read_at()` inside the
`try` had turned a git store that could not produce an object into a missing
session; only `NotJSON` is set aside now, and a git failure is a refusal again.
A count the summary adds up that was not a non-negative integer took the summary
down with a traceback (pre-existing); `_count()` makes it a record the reading
cannot place. The markdown's generation-to-landing column rounded twice; it
prints `landed_minutes`. `delivery_basis` is `record_delivery_block`
(`held`/`absent`), because the record's own block is the run's clock beside the
landing figures, and `src/delivery.py`'s docstring says the rule is shared and
the instant is not. A test held the archived latency equal to the block's only
because its helper landed each record at its own clock; it lands twenty minutes
later now. And the dated report was mine to get wrong: it quoted 137.7 where the
file's minimum is 137.2, said two reads where one publication asked for two, and
gave the morning receipts' generation times as landings; each is corrected, and
the report test, which a substitution of 13 for 14 or 25 for 26 passed because
those numbers sit elsewhere in the prose, anchors every count to its own phrase
and the slot ranges to the file's minimum and maximum (seven substitutions now
fail it, a control passes). Recorded, not fixed: a shallow `--check` takes the
set-aside reasons and the newest record commit as the committed file names them
(the report says so). The reviewer's uncounted note -- that "the first instant
the record was there to serve" overstated what a committer time is -- is fixed:
it is worded as a lower bound everywhere.

The pinned reading was regenerated at the same commit, `c759a1e6`: identical to
the first version apart from the new fields -- the history's order is the
committer times' on every commit here -- so no before-open verdict, first
delivery, revision count, set-aside or order moved; the latency is the
landing's, 55.8/266.7/367.0, with the generated 53.1/261.9/362.1 beside it, and
each commit landed 2.4 to 5.5 minutes after its record's clock. `main` carried
`43dcb8d7`, the 9 October session, readable: fresh.

**Through the current tip** (`279ec5a3`, 16:13 UTC, measured here and not
committed; the dated reading stays pinned): 22 of 22 due sessions published,
all landed before the next open, latency 55.8/283.4/410.5 landed against
53.1/278.6/407.2 generated, 15 of 22 after the retry slot, the 12 October
session landed at 03:05 UTC, 410.5 minutes after completion and 3.3 after its
record's clock; one cost block archived (2 calls, 14,734 input and 1,357 output
tokens); the 13 October session not yet due.

**Measured** (this sandbox, Python 3.11.15): 4269 tests collected, 4235 passed
and 34 environment-gated skips in 19 m 22 s at `7f85e911`; `tools/service_health.py
--check` current with the history walked again; `tests/test_service_health.py`
35 passed (13 new). No record, rule or page file moved, so the fixtures and the
page smoke are CI's, recorded on the PR. gitleaks 8.24.3 over the branch's
commits with the repository's config: no leaks.

**Mutation passes**, each mutant in the mutation worktree and judged by the
whole `tests/test_service_health.py` with the committed-files byte comparison
deselected (a markdown mutant's rule IS that comparison, and it was judged with
it). Before the review, at `074f5697`, twenty-one over the landing rules
(latency, both slots and before-the-open read off the record's clock; the
generated figures read off the landing; the companions' flags swapped; three
sorts by the records' clocks; the summary's generated counts and spread; the
reads outside the `try`; `KeyError` for `LookupError`; the not-JSON words; the
service column's landing; the markdown column): all die in the test naming their
rule, after three cases were added that could tell landing from generation at
all; the control survives. After the review, at `ea05a9fc`, twenty more (order
by committer time, the sequence reversed, fresh off the newest readable
record, fresh off the newest published session, `main_carries()` never
refusing, a git failure set aside, three count checks, the record head
uncompared and taken from the first readable commit, the delivery block's label
swapped, the markdown gap as latency, and five of the first pass's rules again):
eighteen die, each in the test naming its rule; the control survives; two are
equivalent. Dropping `--topo-order` changes nothing on a linear history, where
git already lists a child before its parent whatever the dates (the real
history's five paths walk identically both ways); and fresh's `readable` guard
is redundant beside its session comparison, an unreadable head having no
session. Both are kept as statements of intent.

**Keep / fix / defer / omit.** Keep: the reading reads git and the records and
decides nothing; the record's clock is printed beside the landing and never
read as it. Fix if it bites: the committer time is the commit's own clock on
the runner that made it, the push follows it by seconds and Pages serves it
later still (the publication gate's log says when); a rebase before a push
rewrites it to the rebase's instant, which is closer to the landing, not
further. Defer: #111's ten-session acceptance, which needs morning checks not
yet observed; a newer dated reading once the morning and recovery receipts
exist. Omit: any change to the crons or the guard on these numbers.

**Not claimable:** a live morning, research or recovery observation; the ten
consecutive sessions with morning checks; any trading edge.

## Checkpoint, 13 Oct 2026 — PR #166 accepted; when GitHub starts the scheduled runs (#111)

**PR #166, accepted.** Merged as `3a972ad7` on `main` with a merge commit over
`279ec5a3`. The head `ee644c63` passed all seven checks on Tests run
38436632272 (pytest 17:11–17:27 UTC, page 17:11–17:27, the gate, the native
central case 17:11–17:59 and stress 17:11–18:01) and Secret scans 38436632305
and 38436575840. Publisher 38443506496 printed *Verified: every one of the 41
public files matches committed main* at 18:02:45 UTC; Pages 38443553543
deployed (38443505085 cancelled as superseded, as every merge does). The merge
commit's own Secret scan 38443506687 passed, and so did its
Tests run 38443506807 (page 18:02–18:19 UTC, pytest 18:02–18:22; the native
cases skipped by the gate, as a merge's are).

**Revision.** Branch `claude/spicystock-historical-workflow-i53ud1` restarted
from `main` at `3a972ad7`. #111 cannot reach its ten sessions with morning
checks while no morning check runs. This milestone measures why. `docs/data.json`,
`docs/picks.json`, the compact reader, every receipt, the history, the evidence
objects, the quality ledger, the workflows and the vendored design system are
untouched; nothing under `src/` changed; no run, mail, dispatch, provider call
or credential.

**What was built.** `tools/schedule_reliability.py` reads when GitHub created
each scheduled run against the cron slot it was for: the scheduler's own delay,
before any step of ours runs. `--fetch` is its only network path. It pages the
public Actions listing of scheduled runs, and of the runs a push to `main`
triggered as a contrast, refusing a listing that does not add up rather than
truncating it. It keeps only the fields the reading uses, beside every
scheduled workflow's cron tables as `main`'s first-parent history carried them,
version by version, each with the commit that made it take effect
(`table_versions()`, `scheduled_at()`, so a cron that never fired is still
read). A run is placed at the slot its run name's cron names (`name_cron()`: the
five fields after the word, however spaced; a name that says cron and names
none is refused), or, for a name without one, at the latest instant any cron
named while its table was in force (`nearest_slot()`, the slots `expected()`
names). Every threshold compares seconds; minutes are rounded once, for
display. A slot two runs were placed at is listed (`shared`).
The reading writes, per workflow, cron and UTC week, the minutes from slot to
creation; every expected slot with no run (`no_run` after a day, `not_started`
before); runs for a slot no table named; the first run more than an hour late
across all workflows in slot order and the last prompt one before it
(`change()`); and the push runs' minutes after their commits (`contrast()`).
`--fetch` refuses an HTTP failure, a filtered listing over the API's 1000-run
cap, and a ref whose history lacks a commit a run ran on. `--check` holds the
reading to the committed snapshot with no network.

**What the listing shows** (128 scheduled runs, 360 push runs, fetched 18:34
UTC on 13 October): before the evening slot of 21 September every scheduled run was created
within 17 minutes of its slot (57 runs, weekly medians 4.2 to 15.1). The last
prompt one was the Monday secret scan at 06:00 UTC on 21 September, 4.3
minutes. From the evening primary at 22:16 UTC that day (152.2 minutes), all 71
scheduled runs were created 130.6 to 504.9 minutes after their slots, median
276.5; 13 were more than six hours late; no expected slot went without a run.
The weekly medians have grown since: the evening's were 208.4, 257.4, 285.2 and
336.8 minutes, and the Monday scan's were 378.3, 418.0 and 470.0. The four
morning runs of 12 October were 463.3 to 504.9 minutes late; the two in that
season's window (13:20 and 13:28 UTC) were 504.9 and 499.1, their guards
saying `entry_window_ended` and the winter pair's `inactive_schedule`. The
four 13 October slots had not been created at the snapshot, more than five
hours after the first. The 144 push runs over the same weeks were created within 0.3 minutes of
their commits. The listing says nothing of why, and nothing of runner pickup
(a first attempt's `run_started_at` is its `created_at`).

**What it means, and the options** (`docs/input-truthfulness/2026-10-13-schedule-reliability.md`):
the evening still lands before the next open (its window is about 15 hours).
No scheduled morning check can be relied upon at these delays. The
source-recovery receipts, first slot 07:37 UTC on 14 October, would be created
before the open at the median delay since the change and after it at the
evening's two latest; no forecast is made. Four options are written down and none is adopted:

1. leave the crons, with no scheduled morning checks;
2. dispatch the morning run from outside GitHub's scheduler: Mo's own tap on
   *Run workflow* from the GitHub app, a claude.ai routine, or an external cron
   with a narrowly scoped token;
3. schedule hours early and wait inside the job, bounded by a hosted job's 360
   minutes, which none of the four morning runs met;
4. the small host of #108.

The recommendation is option 2, starting with Mo's own tap, and re-reading the
listing before relying on any automated trigger. It is Mo's decision: each
option changes something outside the repository, holds a credential or spends
runner time.

**The review, worked.** A reviewer by execution over the first pushed tip
(`f543958a`) re-derived every headline number from `runs.json` with its own
script, and every one matched. It returned 17 findings, each reproduced here
before it was touched.

The report said more than the evidence:
- "every guard said `entry_window_ended`" (the winter pair said
  `inactive_schedule`);
- "every run in that window" counted runs outside it;
- the retry runs were dated the 12th, not the 13th they were created;
- the push bound was stated backwards;
- "before 21 September" counted a run on the 21st;
- which runs name their cron was misstated;
- one sentence was a forecast;
- the nearest-slot bound was the cron's period, not the gap to the table's
  next instant.

The code:
- matched a run name's cron more strictly than the file's, and fell back
  silently on a miss;
- read nearest-slot placement against the table at creation, so a table
  changed after the slot refused the reading;
- compared thresholds on rounded minutes;
- let an HTTP error out as a traceback;
- had no answer for the API's 1000-run cap;
- took a ref older than the runs without a word;
- carried dead code.

One test passed on an incidental fact (the morning's maximum is the overall
maximum), and most of the report's numbers had no test. All seventeen are
fixed. Fourteen numbers substituted in the report and the index each fail
their test now, and an identity substitution passes.

**Measured** (this sandbox, Python 3.11.15): 4320 tests collected; the full
suite at `0dfb9fb3` 4285 passed and 34 environment-gated skips in 19 m 10 s, the
one failure the suite-count line this commit moves to 4320 (at `f543958a`,
before the review, 4282 passed and 34 skips in 18 m 33 s); `tests/test_schedule_reliability.py`
51 passed; `tests/test_docs.py` 40/40 with the suite count at 4320;
`python tools/schedule_reliability.py --check` current; no record, rule or page
file moved, so the fixtures and the page smoke are CI's, recorded on the PR.
gitleaks 8.24.3 over the branch's commits: no leaks.

**Mutation pass.** Thirty-one mutants over the tool in the mutation worktree,
each judged by the whole `tests/test_schedule_reliability.py` with the
committed-reading comparison deselected:
- placement: the cron instant excluded, the firing window's start excluded,
  7 not Sunday, the run name ignored, the nearest slot taken as the earliest;
- the tables: the table in force taken strictly, a version's first instant
  excluded, later versions ignored, a version per commit, every parent rather
  than the first, the scheduled files dropped;
- the slots and counts: the day boundary strict, the unexpected runs dropped,
  the boundary counts inclusive, weeks from Sunday, delays in whole minutes;
- the change and the contrast: an hour late counted as late, fifteen minutes
  not prompt, the first prompt run rather than the last, creation order for
  slot order, the contrast unfiltered, the push time read off the run;
- the listing and the snapshot: the count unchecked, the page bound
  truncating, repeated ids admitted, future runs admitted, versions out of
  order admitted;
- the output: the change dropped from the markdown, `--check` ignoring the
  markdown, `--check` exiting zero.

Thirty died. **Three survived the first pass**, each the second shape this file
names (a test passing on an incidental fact of its fixture). No delay sat
exactly on a count boundary; no prompt run exactly at fifteen minutes was the
last before the change; and slot order and creation order never disagreed.
Each has its case now, and all three die. The synthetic history carries a
merge, so the first-parent rule has a case that can fail.

A second pass after the review ran 43 mutants over the fixed tool, adding the
new rules: the five-field and comma rules, the silent miss, the table in force
at the slot, the shared slots, the thresholds on rounded minutes, the HTTP and
network refusals, the cap and the history check. Forty-one died at once. Two
more were the same shape. No case had a cron dropped from its table before
its instant, and no median told the median of the seconds from the median of
the rounded minutes. Both have their cases and die. The control (a docstring
word) survives every pass.

**Keep / fix / defer / omit.** Keep: the reading reads and never decides; a new
reading is a new dated snapshot, never an edit of this one. Fix if it bites:
the push contrast's reference is the commit's own timestamp, an upper bound on
the push. Defer: the morning delivery decision, which is Mo's; a reading of
dispatched runs once any exist. Omit: any change to the crons, the guards or
the workflows on these numbers here.

**Not claimable:** a live morning, research or recovery observation; the ten
consecutive sessions with morning checks; any cause for the scheduler's delay;
any trading edge.

## Checkpoint, 13 Oct 2026 — PR #167 accepted; a first day read again from its minute bars (#111, #109)

**PR #167, accepted.** Merged as `c83ce0f2` on `main` with a merge commit over
`3a972ad7`. The head `abe7c2f7` passed pytest and page on Tests run
38451315934 (19:00–19:25 UTC; the native cases skipped by the gate, nothing
under `src/` having changed) and both Secret scans (38451316009, 38451310011).
Publisher 38454824707 printed *Verified: every one of the 41 public files
matches committed main* at 19:26:41 UTC; Pages 38454858877 deployed
(38454822745 cancelled as superseded, as every merge does); the merge commit's
own Secret scan 38454824651 and Tests run 38454824683 (pytest 19:26–19:51,
page 19:26–19:42) are green. **The 13 October morning runs, read:** the 13:20
and 13:28 UTC slots were created at 19:52:41 and 19:53:42 UTC (392.7 and 385.7
minutes late), their guards passed the job through and every collection step
skipped, as on 12 October. The morning checks still stand at zero observed.

**Revision.** Branch `claude/spicystock-historical-workflow-i53ud1` restarted
from `main` at `c83ce0f2`, pushed as **PR #168**. `docs/data.json`,
`docs/picks.json`, the compact reader, every receipt, the history, the
evidence objects, the quality ledger, the workflows and the vendored design
system are untouched; no run, mail, dispatch, provider call or credential.

**What was missing.** A daily bar books a fill only at the next open
(`record.fill()`). A first day that opened under the trigger and reached it
later is `uncertain` for ever: `trigger_timing`, or `stop_sequence` when the
day's low also reached the stop. That is the usual first day of a buy-stop
ticket and of every anticipation ticket; the October production tickets
(SN, ZIM) sit there, each holding a model slot and settling nowhere, and
twelve of every page fixture's seeded picks do too.

**What was built.** `src/intraday.py` (policy `first_window_minute_v1`,
archived as `rules.intraday` and `rules.record.intraday_fill`, so
`rules_version` moves). `resolve()` reads the entry session's regular-hours
one-minute bars: the first minute of the plan's first 30 whose high reaches
the trigger fills at the trigger, or at its own open when it opened over it;
none in the window is `not_filled` (the plan's day order is cancelled at the
window's end); a crossing minute that opened over the limit is `not_filled`
when no minute of the window traded back to it and stays `uncertain` with a new
reason, `minute_order`, when one did, as does one that reached the stop from
under the trigger; minutes that do not reproduce the daily bar (`_disagrees()`)
are not used. `record.replay(..., minutes=)` reads only the two resolvable
reasons again, walks a fill from the fill on over an entry day
rebuilt from the crossing minute (`plan._bar()`'s `day_low` carrying the
session's own low, which `plan.follow()` raises the stop to at day 1's
close), and names the object in `minute_evidence`.
`record.needs_minutes()` names the scorecard window's plans needing them;
`intraday.gather()` asks one `sip`, split-adjusted `1Min` request per entry
session, at most `MAX_PICKS_PER_RUN` (8) plans a run, newest first, each only
past the session's close plus the 16-minute hold-back, and keeps them as one
content-addressed object per plan under `docs/intraday/`, written once and
read back (512 objects, 16 MiB, 64 KiB an object). `pipeline.gather_minutes()`
runs before the first walk, so the model slots, the published open plans, the
scorecard and `quality_ledger.capture()` all read the same evidence; it never
fails the run, and a dry run writes nothing. `run.intraday` names what was
needed, asked, fetched and stored and the failures by kind;
`intraday.record_faults()` holds it in `report.validate()` under rules that
read minutes; the Method view and the mail print its sentence.

**Measured** (this sandbox, Python 3.11.15, Chromium through Playwright 1.56.1):
4416 tests collected; the full suite at `b093afc2` 4382 passed and 34
environment-gated skips in 18 m 37 s; `tests/test_intraday.py` 96 at `fb42ac0f`;
13 page fixtures and every cascaded generator regenerated and current, their
`--check`s run last (morning 21, issuer-evidence 30, stop-research 22,
research-outcomes 40, research-observations 24, source-recovery 20,
cash-preview 8 tests); `tools/recovery_rehearsal.py --check` current after its
evidence was regenerated; the page smoke with `--shots` 15144/15144 at
`2b7ed442` (no page file changed after it); gitleaks 8.24.3: no leaks. The
first full run at `2b7ed442` found the follow-up's no-request test counting the
minute request as a daily one (`b32d655d` counts the daily fetch alone).

**The review, worked.** A reviewer by execution over `2b7ed442` returned
twelve findings, each reproduced before it was touched. The high one: minutes
that are not the daily bar's day were used -- a minute outside the bar's range,
or a stop the bar's low reached that no minute showed, read as a clean fill.
`_disagrees()` refuses them now (the range at four decimals, a minute reaching
the trigger, a minute at the stop when the bar's low reached it). Then: a
crossing over the limit that never trades back in the window is `not_filled`;
the walk from a minute fill is the daily model's, documented and pinned (a
day-1 bar reaching the stop and +8% books the stop); a writing run walked
objects it failed to store, and walks only what it stored now, `retained`
counting the disk; a gathering that failed whole dropped the archive, and the
evening reads what is retained under the block's `failed` status; last night's
failures go after the rest, so one cannot hold the cap; a key two objects claim
is set aside and never asked for again (`set_aside`); the block's invariants,
the record's object names against what the walks could read, the singular, the
store's disk failures, every bound in `RULES` and `scorecard_analysis.py
--docs`. The validator's new name check found a defect of its own on its first
run: a dry run's record names objects it fetched and did not store, which the
first rule refused; a dry run's fetched objects count as readable now.

**CI on the code head `fb42ac0f`**, Tests run 38468073418: pytest 21:06–21:26
UTC, page 21:06–21:22, the gate, the native central case 21:06–21:42 and stress
21:06–21:55; Secret scans 38468073473 and 38468066425. All seven green.

**Mutation passes**, in the mutation worktree at `9181355a`, each judged by the
whole test files naming its rule (`tests/test_intraday.py`, `test_record.py`,
`test_plan.py`; the evening's and the validator's by `tests/test_intraday.py`):
35 mutants -- the window inclusive, the fill always at the trigger, the limit
and stop boundaries, the stop check ignoring the open, the day's low and the
post-fill range, disagreeing minutes used, another session's minutes used, the
hold-back strict, oldest first, the cap ignored, a reply with no regular-hours
row kept, a dry run storing, the first copy of a minute kept, rows outside
hours kept, the hours unchecked, a file's bytes unchecked, a doubly claimed pick
used, a different file overwritten, the capacity unchecked, the block's sum and
sentence unchecked, a missing block admitted, every uncertain reason read again,
the evidence unnamed, the entry session unchecked, the walk from the daily bar,
the day's low ignored, each of the four walks of the evening without the
minutes, and the validator skipping the block. 33 died at once, **two
survived, each a missing case**: a reply whose every row is outside regular
hours never reached the empty-minutes check, because the double filters by the
request's window (a stub client that ignores the window holds it now); and the
first walk, the slots tonight's tickets are sized against, read no minutes
without any test noticing, because a resolved fill and an uncertain one both
hold a slot (minutes saying the trigger came after the window free AAA's slot
and its commitment now). Both die; two controls (a docstring, a comment)
survive. Over the review's rules, at `c595e8f3`, 28 more: 27 died, and
**`unordered_rows` survived** -- the second shape this file names: the
same-object test reversed two copies of one minute, so the order never
mattered. It reverses two different minutes now and dies (`fb42ac0f`). The
first pass re-run at `fb42ac0f`: the 31 mutants that still apply die, and the
four whose text the review replaced die in their new form. Controls survive
every pass.

**Keep / fix / defer / omit.** Keep: the daily answer wherever minutes cannot
read it; uncertain stays uncertain without evidence. Fix if it bites: a plan
whose minutes the provider never returns is asked again every night until it
leaves the 60-session window (bounded by the cap, and behind the rest after
its first failure); the archive fills in about a
year of two tickets a night, after which nothing new is written and the block
says so; no page fixture shows a minute-resolved plan (the end-to-end tests
do). Defer: a crossing over the limit that trades back to it inside the
window, which only sub-minute data could order. Omit: minute bars for any other purpose; a fill inferred
from a bar the minutes do not show.

**Not claimable:** a live night with minute bars. The first evening after the
merge whose window holds a `trigger_timing` or `stop_sequence` first day asks
for them (the 12 October record carries two, SN and ZIM); read its
`run.intraday`, the rows' `minute_evidence` and the objects under
`docs/intraday/`, and record them here. Also not claimable: a live
morning, research or recovery observation; any trading edge.

## Checkpoint, 13 Oct 2026 — PR #168 accepted; each publication read against the slots it archived (#163)

**PR #168, accepted.** Merged as `7e40716e` on `main` with a merge commit over
`c83ce0f2`. The code head `fb42ac0f` passed all seven checks on Tests run
38468073418; the final head `36c11cc1` (CLAUDE.md alone over it) passed
pytest, page, the gate's docs-only decision and both gitleaks runs.
Publisher 38476351986 printed *Verified: every one of the 41 public files
matches committed main* at 22:14:57 UTC; Pages 38476380614 deployed
(38476350936 cancelled as superseded, as every merge does); the merge
commit's own Secret scan 38476351921 and Tests run 38476351925 (pytest
22:13–22:40 UTC, page 22:14–22:29; the native cases skipped by the gate, as
a merge's are) are green. The first evening after the merge whose window
holds a `trigger_timing` or `stop_sequence` first day is still the test of
the minute bars; not claimable yet.

**Revision.** Branch `claude/spicystock-historical-workflow-i53ud1` restarted
from `main` at `7e40716e`, pushed as **PR #169**, closing #163. Its first
three items shipped in #166; this is the last: *an alternate archived
delivery schedule is validated, but reporting still calculates against
today's slots.* `docs/data.json`, `docs/picks.json`, the compact reader,
every receipt, the history, the evidence objects, the quality ledger, the
workflows and the vendored design system are untouched; nothing under
`src/` changed; no run, mail, dispatch, provider call or credential.

**Reproduced first** (`scratchpad/slots/repro.py`, the tool as `main` carried
it): a synthetic 9 October record whose rules archive 7:16 and 9:16 PM ET
slots, its `run.delivery` re-deriving from them, landed 00:46 UTC on the
10th, was validated and then measured against 22:16 and 00:16 UTC, today's
slots: 150.0 minutes after the primary, after the retry. A record whose rules
archive the delivery rule and that carries no block was read without a word.

**Changed** (`tools/service_health.py`, `service_health_v3`).
`slot_policy()` reads a publication whose `rules.pipeline` archives the
delivery rule against THOSE slots, once its `run.delivery` re-derives from
them (`delivery.faults()`, the validator's own check, now asked in one
place); rules that archive the rule beside a record without its block, and a
block beside rules that archive no rule, are set aside by name and do not
count as publications. A session reads unpublished only when no other
readable publication exists for it; a record from before the rule is read
against the current policy's slots and says so. Each publication's `timing` names
`slot_basis` and `slots_et`; a session row carries its FIRST publication's
basis; the summary counts each; the markdown prints one line. The dated
reading moves to `2026-10-13-service-health-evidence/`, pinned at `7e40716e`
(clock 22:13 UTC on 13 October). The 12 October reading is kept as written --
v2 in place, v1 copied byte for byte from `279ec5a3` into its `v1/`, as #163
asked -- each file held to its git blob identity by the tests, and the old
report says it is superseded.

**What it moves over the history: nothing.** The only publication under the
rule, 12 October's, archived the current slots; the v3 reading pinned at
`c759a1e6` is the frozen v2 with the new fields added. Through `7e40716e`: 22
of 23 due sessions published, all 22 before the next open; the 13 October
session pending at the clock (completed 20:15 UTC, nothing on `main` at
22:13), so fresh reads no and the current streak 0, the longest 22; latency
by the landing commit 55.8 / 283.4 / 410.5 minutes (53.1 / 278.6 / 407.2 by
the records' own clocks); 15 of 22 after the retry slot; 1 publication read
against its own archived slots, 26 against the current policy's.

**The review, worked.** A reviewer by execution in its own worktree checked
the slot rule against an independent zoneinfo computation (196 comparisons
across the DST change, Thanksgiving, both early closes and New Year, four
archived slot pairs, every boundary at and a second before each slot and
open: 0 mismatches), the frozen bytes, the v2-equivalence claim and every
number in the report. Nine findings, each reproduced; six fixed in
`9e1e6afb`. The medium one was mine: the report cited the schedule-reliability
snapshot for the 13 October morning runs, which predates them; it cites the
four runs by id now (38458332290, 38458466585, 38461411014, 38461736889,
created 19:52–20:18 UTC, each skipping every collection step and its persist
job, re-read off the Actions API). Then: the index said "22 of 22 due"; five
of the 38 set-aside commits are the second build's 11 September fixtures,
not the first build's records; README said "refused" for a set-aside; a block
beside rules that archive no delivery rule read as `held` against today's
slots (set aside now); and a review mutant reading a row's basis off its LAST
publication survived (pinned now). Three are written into the report as
known limits: a future `delivery.VERSION` sets aside version-1 records, as
`report.validate()` already refuses them; `delivery.slots()` places an
archived slot past midnight ET on the session's own date; `slots_et` prints
to the minute.

**Measured** (this sandbox, Python 3.11.15): 4419 collected; the full suite
at `4082d51c` 4385 passed and 34 environment-gated skips in 18 m 27 s;
`tests/test_service_health.py` and `tests/test_docs.py` 78 passed at
`9e1e6afb`; `python tools/service_health.py --check` current with the history
walked again; gitleaks 8.24.3 over the branch's commits: no leaks. No record,
rule or page file moved, so the fixtures and the page smoke are CI's.

**Mutation passes**, each mutant in the mutation worktree and judged by the
whole `tests/test_service_health.py`, the committed-file comparison
deselected except where it is the rule's own test. At `4082d51c` thirteen:
the archived slots ignored, `faults()` skipped, the retry from the current
policy, the frame not updated, the basis always current, `slots()` ignoring
its arguments, the row basis fixed, the summary over one publication, the
words swapped, `slots_et` from the current policy, the markdown line dropped,
`OUT_DIR` back at 12 October, the version back at 2: all die, a control
survives. At `9e1e6afb` the same thirteen die again and two more (a block
without rules read, a row's basis off its last publication); a control
survives.

**Keep / fix / defer / omit.** Keep: the reading reads git and the records
and decides nothing; a record is read under the rules it archived. Fix if it
bites: the three known limits above. Defer: #111's ten-session acceptance,
which needs morning checks not yet observed. Omit: any change to the crons,
the guard or `src/delivery.py` on these numbers.

**Not claimable:** Pages serving a publication at the instant its commit
landed; a live morning, research or recovery observation; any trading edge.


## Continuation, 13 Oct 2026 — #162 verified; the intended stock within reach (#164)

PR #162 was merged normally as `289ab4a1b886feb3ddcd3e6099d59ea4bf8b8147`
over reviewed head `1381d0da553af7fdfde4a77eab2c4f2cc20107da`; its merge
tree equals reviewed tree `930321fc0195f2a121f679e4ebe85a7e42e2b94d`.
All seven premerge checks passed: 4143 Python tests, 15007 page checks, 378
chart checks, 137 continuity checks, 76 handoff-model checks, current producer
fixtures, clean tree and both secret scans. Native central/stress benchmarks
and memory supervisors passed; upload/API artifact digests matched, while
binary artifact payloads were not downloaded. Its publisher `38369500620`
matched 41 core files and Pages `38369524784` deployed the merge.

Actual public verification at 08:31:26–08:32:20 UTC passed 129 checks, matched
46 files and inspected all 16 desktop/mobile captures, with no unexpected
browser errors or private-storage changes. The quote receipt remained 404;
positive at-collection labels had local fixture coverage and deployed-byte
identity, but no actual current quote row on which to display them. The
scoped proof is `release-evidence/2026-10-13-observation-fidelity/acceptance.json`.
Its snapshot predates the completed main Tests run; the later passing outcome
is retained separately in `release-evidence/2026-10-13-observation-fidelity/postmerge.json`.
No timely quote, personal fill or return is inferred.

Main subsequently advanced through PRs #165–#168 to `7e40716e`. The 22:26 UTC
HTTP-only audit matched 41 core files plus 11 dated artifacts to that commit;
both optional research and recovery receipts were still 404. Its canonical
October 12 publication for October 13 has zero tickets and no new minute-bar
result. The reconciliation evidence is
`release-evidence/2026-10-13-evening-reconciliation/acceptance.json`; its later
`main-checks-final.json` records completed main Tests: 4416 Python, 15144 page,
378 chart, 137 continuity and 76 handoff checks, with all seven producer fixture
generators current. This HTTP audit is not a new public browser acceptance.

Issue #164 now gives the opening guidance a 44px **Find a stock** control and
prioritizes an exact ticker over company-name matches on Enter. Choosing a
stock or using a validated research Inspect action clears an incompatible
query and temporarily reveals a hidden candidate, preserving the saved lens.
Desktop review reproduced a second obstacle: the detail pane could retain its
lower scroll position or remain below the document viewport. Explicit choices
now begin at the stock and chart. An independent sweep then reproduced a Method
help return restoring that old lower position; explicit choices clear that
return target while ordinary Method Return keeps its reading position.
Validation and history refusal precede the research inspection changes.

Final local source checks pass 669 browser assertions (139 finder, 149 existing
mobile/lens/reach, 257 inspection including 102 new scroll/Method controls,
124 source recovery), 137 DOM/store continuity and 24 recovery/minute-bar
interaction checks. Independent review passes 131 controls, including actual
archived LW/CNI ambiguity, QUAD/GTE, real cross-tab unfollow, desktop/phone and
reduced/smooth motion; eight independent captures were inspected. Six targeted
scroll/restoration mutations fail, and an unrelated timeout control passes all
102. Pre-fix and intermediate failures are distinguished in
`release-evidence/2026-10-13-stock-finder/prepared.json`. Producer code and
fixtures retain their base bytes; this local verifier did not rerun generators.
Hosted fixture checks remain required. README describes the explicit navigation
exception; `.env.example` needs no configuration change. The design-system pin,
strategy, market data, provider architecture and account facts are unchanged.
Exact-head review, hosted checks, merge and actual public acceptance are still
pending for this stock-finder change.

Concurrent PR #169 owns the service-policy work. Our earlier local #163
preparations remain unpublished and must not replace it. Independent read-only
review of `4082d51c` reproduced an unversioned-delivery validation gap and an
index denominator mismatch; passing CI alone does not clear those findings.
Recheck its current head and reviewed evidence before any merge decision.

The next independent deliverable repairs visible reload controls that currently
leave same-cohort research quotes unavailable after a new receipt is published.
A local producer-fixture reproduction confirms that the existing internal
research reload API fetches them correctly. Implementation is isolated pending
this release. The owner manual-morning workflow handoff is a subsequent option;
manual startup latency, timely quotes, broader issuer access, broker facts and
an actual personal trade remain unestablished. No workflow dispatch or new
provider access is part of either UI change.


## Repair preparation, 13 Oct 2026 — compact stock finder at tablet widths

PR #170's original head `0e2a681a` failed its hosted page job in Tests
`38480748216`: 15426 of 15432 page checks passed. The six failures were the
existing compact-orientation requirement at 820, 768 and 721 pixels in dark
and light themes; 378 chart checks passed. This is a real layout regression,
not an accepted flaky check. Local execution reproduces all six failures:
the guidance is 94px tall against the existing strict 90px limit.

The existing two-row layout below 1001px now removes its inherited 8px row gap.
The six failing cases render at 86px, with all words, font sizes and the 44px
Find a stock target preserved. The finder geometry suite now includes those
three intermediate widths. No existing assertion was loosened. Local reading
and finder checks pass 307 of 307. The original CSS fails the unchanged reading
rule in six cases; an unrelated chart-reading margin mutation passes all 141
reading checks and was restored before recording final source hashes.
Independent exact-base browser diagnosis confirms the same repair in eight
cases; root and independent reviewers inspected the before/after captures.
`release-evidence/2026-10-13-stock-finder/compact-repair.json` retains the failed
CI identity, local results, measured geometry and source identities.

README's finder description remains accurate; `.env.example` needs no change.
Source and fixture bytes unrelated to the CSS and added viewport coverage are
unchanged. The previous exact-head evidence belongs to the original head; the
corrected head needs fresh independent review and normal hosted gates before
merge, deployment and actual public acceptance. Research quote reload plus its
owner-workflow handoff are prepared separately for a subsequent coherent
milestone and must reconcile this correction after #170 releases.

## Main reconciliation, 13 Oct 2026 — retain the reviewed finder over #169

The concurrent service-policy PR #169 merged as `bf266a6e` while #170's
required checks were finishing. Its tree equals reviewed `174f47c0`.
The existing #170 branch is reconciled over that main without changing either
the six reviewed stock-finder runtime/test files from `05794ffe` or the merged
service-health runtime/tests. Both appended CLAUDE checkpoints are preserved.

Independent execution found one remaining prose error in #169: a later
malformed revision is skipped, while an earlier readable publication still
keeps that session published. README, the current dated service report and
the corresponding checkpoint now say that the offending commit does not
count; the session is unpublished only if no other readable publication
exists. Current-main freshness is a separate result. Generated service-report
evidence and all published record/history bytes retain their existing values.

The reconciliation passes 110 service/delivery/documentation tests, 307
reading/finder browser checks and the full pinned service-history replay.
Two synthetic phone/tablet captures were inspected. The design-system pin and
`.env.example` are unchanged. The exact repair review and
`release-evidence/2026-10-13-stock-finder/main-reconciliation.json` retain the
source comparisons, executed checks, prior service finding and deployment
provenance.

All seven checks ultimately passed at the preceding head `05794ffe`: 4416
Python tests, current producer fixtures, 15459 page checks, 378 chart checks,
both native benchmarks and memory supervisors, gate and secret scans. That
completed evidence belongs to its old `7e40716e` base; it does not replace
fresh required checks for the reconciled head. Independent final review,
normal hosted gates, merge and actual public verification remain required.
The combined research-quote reload/owner-workflow preparation must then be
rebased onto this accepted release before publication.

## Checkpoint, 14 Oct 2026 — PR #169 accepted; the first trade rehearsed end to end, its reported result reproduced offline (#110)

**PR #169, accepted.** Merged as `bf266a6e` on `main` with a merge commit over
`7e40716e`, closing #163. The code head `9e1e6afb` passed all seven checks
(the stress case 22:49–23:25 UTC); the final head `174f47c0` (CLAUDE.md alone
over it) passed pytest, page, the gate's docs-only decision and both gitleaks
runs. Publisher 38485532089 printed *Verified: every one of the 41 public files
matches committed main* at 23:39:28 UTC; Pages 38485556648 deployed
(38485531013 cancelled as superseded, as every merge does); the merge commit's
own Secret scan 38485532024 passed and its Tests run 38485532032 passed.

**Revision.** Branch `claude/spicystock-historical-workflow-i53ud1` restarted
from `main` at `bf266a6e`, pushed as **PR #171**. #110's acceptance line:
"end-to-end rehearsal covering partial fill, cancellation, gaps and unconfirmed
cash; traceable evidence throughout; reproducible user-reported P&L". The
private pieces (#116, #120, #124, #144, #146, #149) each had their own suite;
nothing traced one trade from the publication to a P&L figure, and nothing
reproduced that figure outside the browser. `docs/data.json`, `docs/picks.json`,
the history, the evidence objects, the workflows and the vendored design system
are untouched; nothing under `src/` changed; no run, mail, dispatch, provider
call or credential.

**The page.** `beyondStop()` in `app-handoff.js`: a planned handoff's completed
result whose average exit is under the protective stop its plan froze names how
far under, per share and on the reported shares, as one more result row (a gap
or slippage past the stop). Reported averages only, so a gap on part of a
position can sit inside an average at or above the stop; an independent report
has no frozen stop and no row.

**The rehearsal.** `tools/first_trade_cases.mjs` (the smoke's `firsttrade`
suite, lane A) drives the real page over the cash-preview `publication-multiple`
fixture ($2,000 / 0.5%; AAPL one burst share, COIL four anticipation shares) on
one clock it moves for the page and the private store alike: blank, unreadable, $0 and $300 cash
each refused for three COIL; $2,000 drafts three COIL and one AAPL; the readback
copied; AAPL filled at $62.40, COIL two of three at $111.05; after the cutoff no
new draft, no cash preview, and COIL's third share cancelled at 9:00; on 14 September AAPL's stop
fills at $59.85 on a gap ($0.85 past the $60.70 stop, net −$2.56) and COIL
sells one; on 15 September COIL's last (average $113.60, net $5.08); the backup
downloaded. Run at 390 and 1280 px, the two journeys must write the same bytes;
`tests/fixtures/first-trade/` holds them and what the page printed
(`SCSTOCK_FIRST_TRADE_WRITE=1` regenerates). **The cascade grows by one:** when
`tests/fixtures/cash-preview/` is regenerated, regenerate this after it, and
then the parity corpus built from its backup; `tests/test_private_results.py`
fails first and names the commands.

**The reproducer.** `tools/private_results.py`, stdlib only, reads the backup on
the owner's machine: the page's `validItem()`/`normalizeReport()` rules ported,
so a record the page would refuse is refused by name; each completed result
re-derived by `completedResult()`/`beyondStop()` in integer micro-dollars; each
record traced to its publication by the SHA-256 it froze (among `--publication`
files or `--git`, the checkout's history of `docs/data.json`) and to the plan
whose reference, order, entry window and exit schedule it froze (an independent
report: the setting-up row whose evidence id, plan and source digests it
names); and the model's own daily-bar replay of that plan beside it, read off
the newest later publication's `open_plans` by evidence reference, never added
(#111's "settled model observations beside separately reported owner results",
task #58). `--git` reads the 65 retained publications in about 6 s, holding
only a small index of each.

**Measured** (this sandbox, Python 3.11.15, Node 22, Chromium through Playwright
1.56.1): before the review, the full suite at `5bc0c83f` 4438 passed with 34
environment-gated skips, the full smoke with `--shots` 15208/15208. On
`ad592da7`, after it: 4608 collected, 4574 passed and 34 environment-gated
skips in 18 m 25 s; `tests/test_private_results.py` 189 (the parity corpus
109 of them); the JS model cases 78; the parity corpus current, 109 cases, 32
accepted by the page; continuity 137; the chart check 378/378; the full smoke
with `--shots` 15224/15224, the rehearsal 78 of them; gitleaks 8.24.3 over the
branch's five commits: no leaks. CI on `ad592da7` passed pytest, page and both
secret scans before the native cases finished. The reworded gap row at 390
light and 1280 dark was looked at.

**Mutation pass.** 33 mutants plus two controls, the tree never written (Python
in the mutation worktree, judged by the whole test file; page through the
smoke's routed module copies, judged by the model cases and the browser suites).
27 died first. **Six survived, five of them holes**, each a missing case:
filled plus cancelled over submitted with each alone within it (the first shape
this file names: a different clause refused the only case); an exit exactly at
the stop; a gap on more than one share, in the reproducer and on the page (the
rehearsal's gap is on one share, the second shape); and the history's
oldest-first order, held only by positions that were 0 and 1 either way. All
five die now. The sixth, the model read from the plan's own session, is
equivalent on records the pipeline writes: tonight's picks never sit in that
session's `open_plans`. Both controls survive.

**The review, worked.** A reviewer by execution over `5bf2bd4b` returned nine
findings, each reproduced here before it was touched. The tool and the page
disagreed at their edges, both ways: the tool accepted a boolean where the page
wants an integer (Python counts `True` as 1), a revision of 2^60 past
JavaScript's safe integers, entry-window clocks with six fractional digits and
an exit instruction of 1,500 astral characters (3,000 UTF-16 units to the
page); it refused `2.0` where `JSON.parse` reads 2, a record clock without
milliseconds or with an offset, and year 0000. One mechanism closes both
directions: `tools/private_results_parity.mjs` runs the page's own
`app-handoff.js` in a vm over 109 private backups and writes its verdicts
(`tests/fixtures/first-trade/parity.json.gz`), `tests/test_private_results.py`
holds the tool to every one -- the same accept or refuse, and for an accepted
store every record's figures and displays -- and CI's page job holds the file
to the page with `--check`. **The corpus found a page defect of the class this
file names most:** six of the store validator's pattern tests called
`RegExp.test()` on a stored field without asking its type, so an array holding
one matching string passed by coercion (a reference digest, a publication
digest and rules version, a ticker, a cohort digest). The page never writes
one; it tests the type first now (`matches()`), and the pre-fix page fails
`--check`. The independent trace compares the applicable session and context
digest too, and every trace names what it did not compare (a planned handoff's
draft; an independent report's reader digest, cohort, inputs digest and
baseline admission). The beyond-stop row said "past the stop", which read as the
stop's own price; it reads "$0.85 a share on average · the 1 reported share
exited for $0.85 less than at the stop". A RecursionError, a missing file and a
bad ref were tracebacks: refused at the parse, and exit 3 in one line;
`--limit` is at least 1; "result None%" is "no result yet".

**The rehearsal's cutoff had passed on the wrong rule**, the first shape this
file names. The page was opened with a pinned clock (`SCStock.now`), and a
pinned page never reclocks, so the desk sat at 8:35 through every later step
while only the private store's `Date` moved; "no new draft after the entry
window" held because AAPL already had its draft. The page is opened unpinned
now, one replaced `Date` read by the desk, `availability()` and the store, each
step asserts the page read its instant, and after the cutoff the cash preview
is checked `unavailable` with the window named (pinned, it said `calculated`).
The clipboard check writes a sentinel first (Chromium shares the clipboard
between contexts), and the request check requires no query string. The
reviewer's 21 surviving mutants are each closed by a named test: the model's
order by session and by clock whatever the files' order, a publication of the
plan's own session, a mismatch's exit code, each field an independent trace
compares, the refusal messages matched exactly, the write check over the
checkout as well as the temporary directory.

**Second mutation pass.** Python, in the mutation worktree at `7a1910eb`, each
mutant judged by the whole `tests/test_private_results.py`: 55 (the first
pass's 25 that still apply and 30 over this round's rules); 51 died at once and
**four survived, each a missing case** -- NaN and Infinity refused by a field
rule rather than at the parse (the refusal pinned by its message now), a
RecursionError-deep nesting never tried, a planned report's `published_at`
mismatch, and the text's beyond-stop line held on one share, where per share
equals total. All four die at `ad592da7`; two controls survive. Page, through
routed copies: three guard removals die on the parity `--check`, a copy button
that does nothing dies on the readback check, a save that leaks a reported
quantity in a morning-file query dies on the request check; the control
survives. A query on the page's own morning fetch survives and cannot reach
the rule: the journey fetches no morning file after the first report.

**Keep / fix / defer / omit.** Keep: the reported result and the model replay
are two columns and never one figure; the reproducer refuses what the page
refuses. Fix if it bites: the beyond-stop line reads averages, so a gap on part
of a position can hide in an average above the stop; the cash-preview cascade
now includes the rehearsal. Defer: #110's actual first trade, which is Mo's.
Omit: any broker connection, a cloud copy of the backup, a P&L the reports do
not support.

**Not claimable:** a real trade or a real backup -- every broker fact here is
synthetic -- and any trading edge.


## Stock finder reconciled with private-report release — 15 October 2026

PR #170 is reconciled over `c7a3566e`, including the merged #171 private-result
reproducer and reported gap behavior. Finder runtime remains byte-identical to
reviewed `71d5fc5c`; new private-report runtime, fixtures, workflows, configuration,
canonical publications and historical evidence remain current main's exact bytes.
Both append-only checkpoint histories survive the CLAUDE conflict. The combined
smoke driver invokes both finder and first-trade suites. README was reviewed with
both feature descriptions retained; `.env.example` is exact current main.

[Reconciliation evidence](release-evidence/2026-10-15-stock-finder/prepared.json):
229 affected Python/documentation checks, 476 reading/inspection/first-trade browser
checks, 166 separately executed finder checks, 78 handoff model cases and a current
109-case parity corpus pass. Two root captures were inspected. Independent review
passed 18 provenance checks over 20,324 files and 92 browser checks on the actual
October 14/15 publication, inspecting five captures and preserving an unsaved
private correction. Harness-scope corrections and the unknown-selector diagnostic
are recorded, without changing product assertions or claiming omitted execution.
Python 3.12.14, Node 24.19.0, Playwright 1.56.1 and Chromium 141 were used.

All seven prior `71d5fc5c` remote checks completed successfully; the dated receipt
retains that historical evidence and its tested base. This reconciliation still
requires final committed-head review, fresh required gates, ordinary merge and
actual public acceptance. Current production remains the October 14 scan for
October 15, degraded/behind_more, red market, zero tickets. Its source-recovery
receipt binds the previous publication; research quotes remain unavailable. No
current morning coverage, personal trade or trading edge is inferred. The next
prepared milestone pairs research quote reload with the static owner handoff;
the subsequent policy/window preparation must include #171's first-trade fixture
cascade before fresh verification.


## Independent Chicago broker-time helper preparation — 15 October 2026

The optional **Enter Chicago time** helper is now prepared directly on published
main `145716b7`, independently of the pending combined morning workflow. It
starts blank for each of the five broker-event fields, previews the entered
America/Chicago time with its UTC offset and instant, refuses the spring clock
gap, and requires an explicit occurrence choice for the repeated autumn hour.
Apply changes only the chosen unsaved field; Cancel preserves entries. Existing
explicit-offset entry, save validation, chronology, quantity and private-storage
rules remain intact. The helper infers no broker execution or event time.

The original [local preparation](release-evidence/2026-10-15-broker-time/prepared.json)
and its failure/review receipts retain their original `2c8c3ca8` base and scope.
The [direct-main reconciliation](release-evidence/2026-10-15-broker-time/main-reconciliation.json)
records current-base verification separately. The broker UI, CSS, test helper
and smoke registration retain the exact reviewed `600fb098` bytes; README adds
only the broker helper paragraph. Current-main fixtures, the newer recovery
receipt, published history, provider/strategy source, workflows, configuration
and pinned design system are unchanged. The combined morning candidate's code,
fixture changes and collection-window behavior are not included in this release.

Automatic approval review separately blocked publishing a regenerated synthetic
fixture for that combined morning candidate; this broker-only work neither
uploads that fixture nor retries the rejected action. Its fresh required hosted
gates, reviewed exact-head merge, existing deployment and actual public
acceptance remain outstanding. README describes the optional unsaved helper;
`.env.example` remains accurate and unchanged. Timely morning observations,
confirmed broker facts and Mo's first actual successful trade remain open.


[Finder PR #170](https://github.com/spicyChicken59/SpicyStock/pull/170) is already
shipped: reviewed head `b30cbdf6` passed all seven required checks and merged as
`8c251c1f`. Its actual public verification passed 297 checks with 58 matching
files, superseding the earlier pending finder notes. The separate local morning
candidate `66e92a57` retains the full acceptance receipts and the blocked fixture
publication checkpoint; no remote PR exists for that candidate. Those combined
changes are not a dependency of this broker-only release. These implementation
and release checks do not establish a personal execution or profitable trade.


The broker candidate's first publication attempt was stopped by automatic
approval review because the mutation receipt included raw synthetic broker/order
records inside assertion diagnostics. The rejected full receipt is preserved
locally at `19dcb98c` and is not retried. The
[evidence minimization](release-evidence/2026-10-15-broker-time/evidence-minimization.json)
replaces raw detail strings in both mutation receipts with byte counts and
SHA-256 digests, retaining every control/result name, count, assertion status
and source/log hash. Runtime, test code, fixtures and README are unchanged;
prior checks are not claimed rerun. Original source reviews keep their original
scope. Fresh documentation, secret-scan and independent exact-head checks are
required before publishing this smaller receipt; hosted gates and actual public
acceptance remain outstanding. The separate combined-morning fixture upload
remains blocked and is not included in this independent broker release.

## Checkpoint, 16 Oct 2026 — PR #171 accepted; the first live minute bars and recovery receipts read; the browser suites held to a slow runner

**PR #171, accepted.** Merged as `59eeca2a` on `main` with a merge commit over
`64481f2f`. The code head `e6d49c2d` passed all seven checks (pytest, page, the
gate, the native central case to 02:38 UTC and stress to 02:29, both gitleaks
runs). Publisher 38502113793 waited for `app-handoff.js` and `app-handoff-ui.js`
and printed *Verified: every one of the 41 public files matches committed main*
at 02:39:57 UTC on 14 October; Pages 38502138200 deployed (38502113293 cancelled
as superseded, as every merge does); the merge commit's own Secret scan
38502113754 and Tests 38502113755 (pytest, page; the native cases skipped by the
gate, as a merge's are) passed.

**Revision.** Branch `claude/spicystock-historical-workflow-i53ud1` restarted
from `main` at `55a458ad` (the 15 October publication and its issuer receipt,
over #170 and #172, which another builder merged while this ran). Nothing under
`src/` changed; the one change under `docs/` is `followBlock()` in `app.js`,
the repair recorded below. `docs/data.json`, `docs/picks.json`, the compact
reader, every receipt, the history, the evidence objects, the quality ledger,
the workflows and the vendored design system are untouched; no run, mail,
dispatch, provider call or credential.

**One red on the way, read before it was touched.** The page job failed on
`27ad3a10`, a commit that changed `CLAUDE.md` alone, at `it stopped within a step
of leaving -- 12` in the findings replay suite (#103's), 15223 of 15224. The
check bounded the step at an absolute 3, but Play resumed from wherever the
scroll-off stop had left it, and on a loaded runner the wall clock between two
Playwright calls let nights pass before that stop. Reproduced in the mutation
worktree by adding two seconds after each Play click: exactly that assertion
fails (stopped at 17) and every other check passes, as on the runner. Fixed in
`e6d49c2d`: each stop starts from night 1, reads the step in the same task as the
scroll or the hash change, waits for the stop, and is bounded relative to that
step and short of the last night. The last-night bound closed a hole of the first
shape this file names: with both stops removed, Play ran to the last night and
stopped by its own rule, so "the night holds" passed.

**The sweep that followed.** A read-only workflow over every browser suite
(four readers, eight verifiers, each candidate re-run in an isolated worktree
with a modelled slow runner) returned 36 distinct candidates of that class, and
the verifiers reproduced five by name, two more as a thrown suite and one as a
vacuous pass. Then one agent per family, in its own worktree, with the same
proof demanded of each fix: the named check fails under the injection and passes
without it; the fix passes plain and under the same injection; a page mutant
breaking the rule the check names fails it by name; a control passes. A test
file was the only thing any of them changed. Three of the eight could not be
started on the first launch (the primary working directory had drifted off the
repository, so their worktrees could not be made) and ran on a relaunch of the
same run, the five finished ones replayed from its journal.

**The session suite** (two, both the page's own 30 s `watchClock()` tick,
`CLOCK_TICK_MS`). *Crossing the deadline while it sits there changes the
answer* moved the clock in one call and asked `reclock()` in the next, so a
tick inside the gap caught the page up first and the check credited the wrong
caller (reproduced with a 31 s wait and a counter on the page's own reclocks:
one tick, `[false, "ended"]`). The move, the reclock and the window read are
one `evaluate` now. *Pressing it after the window closed copies nothing* was a
crash, not a failure: the same tick repainted the plan disclosure for an ended
window and removed the copy control, and the trusted click waited out
Playwright's 30 s and threw before the named check ran. The clipboard sentinel
is written first; a one-shot capturing listener moves the clock at the start
of the press's own task; the trusted click is unchanged. Each fix passes under
the 31 s wait; a page that never notices the window ending fails five checks by
name, one whose `copyGuard()` trusts the drawn answer fails three; the controls
pass 95/95.

**The findings replay** (six, all `tools/findings_cases.mjs`). Play from
night 1 reaches the last night after sixteen 250 ms ticks and stops by its
own rule, so any driver gap over four seconds read a finished Play: *Space
plays from the stage* read the label 650 ms later (it reads it in the
keydown's own task now and waits for the step); *Pause holds the night* could
pause a Play that had stopped and so restart it (Play is started and paused in
the task of its first step, through a MutationObserver on the step, bounded
to resolve `null` on a page that never steps); *Play stops at the last night*
read 900 ms after the click (a 1.5 s renderer stall put the first read before
the overdue tick: it waits for `playing()` to go false, bounded); *Play was
running when the replay was scrolled away* and its twin for leaving the view
clicked Play one call before the scroll or the hash change (Play starts inside
that task now); *it stopped within two steps of the scroll* assumed when the
IntersectionObserver would be delivered (an observer of the test's own, made
in the scroll's task, records the night it is told the stage is off screen,
which the page's observer is told in the same delivery, and the check holds
the stop to that night); and the 390 px *a tap during Play stops it* was
vacuous under a 1.5 s delay, Play having stopped at the last night before the
tap (the tap's own capturing listener starts Play and records that it was
running, and a page whose tap stops nothing fails four checks under the delay
it survived before). The *in flight* check held the file on a 1,500 ms timer
and crashed when the runner outlasted it; the route is held on a promise the
check releases after it has read the loading line and `aria-busy` in one
task. Every fix passes plain and under its injection; a page that never stops
at the last night, never pauses, ignores its observer or sets no busy state
fails by name; the controls pass 848/848.

**The Following suite** (seven of eight sibling sleeps, all the store's
origin-wide Web Lock: every save, size edit, removal and observation lands only
after `SCStock.follow.commit()`'s grant, and the suite read each 150–250 ms
after the click). Under a 1.5 s hold of `spicystock:following:demo:v1` placed
before the action, *one click follows*, *an invalid size is refused with a
sentence* (and three checks downstream of the same held lock, the reload
dropping the still-queued size commit), *a newer observation updates the card*,
*undo removes the setup*, *a blocked write is named* and the shots-only *the
store works again once unblocked* all fail by name; *a second blocked write
does not stack its sentence* was vacuous, the count being 1 before and after
the second grant. Each read waits, bounded to five seconds, on the state it
names (`settled()`), and the stacking check captures the first warning node and
waits for a different one. The eighth, *the withheld reason stays beside the
followed setup*, was not reproduced: its locator auto-waits for a card that
exists only after the grant, so its sleep stays. A page that never flips
`data-follow`, accepts a size of zero, never commits the observation, drops the
refusal or lets refusals stack fails each check by name; the control passes
30/30 (31/31 with shots).

**The lens, compare and refresh suites** (five, the same lock). *Following
counts the setup just saved* read the tab's `data-count` 250 ms after the save;
*unfollowing empties the lens and stays in it* read the empty state 300 ms after
the remove; *N is saved under the session it was signalled on* and *following
from the comparison saves one setup in this browser* read `follow.list()` 250 ms
after the save; *a setup is saved before the reload* read the store 250 ms after
it, and every later identity check compared against that snapshot. Each waits,
bounded, on the count, the empty state or the store itself. The five mutants
fail by name; the controls pass 66/66, 86/86 and 47/47.

**The follow-through suite** (seven, six of them the same lock through the
render's own queued commits, read through the suite's `rerender()` helper and
four fixed sleeps after a reload or a click). *A v1 store is upgraded in place*
read the version 300 ms after the reload (the migration is a commit the render
queues); *and says the list was left as it was* read the status 300 ms after
the render whose backup copy was made to fail; *a v1 follow gets its chart back*
read the store 320 ms after the reload and the next check indexed into the
evidence it had not got, a TypeError that ended the lane; *and says so* read the
refusal 200 ms after a save over a version-99 store; *one observation, dated by
the market* and every card check after it read the shelf 320 ms after a render
whose observe commit was still queued; *a follow in one tab shows in the other*
gave the lock grant, the write, the storage event and the other tab's repaint
650 ms between them; and *a store with no room still saves the setup* read the
quota fallback 300 ms after the click, the next check indexing into an empty
store. `rerender()` now marks the shelf the render draws synchronously, in the
render's own task, and waits for the pass that redraws it without the mark;
every other read waits, bounded, on the store or the sentence it names, and the
two reads that threw fail by name. A page that never migrates, never attaches
the recovered evidence, writes no refusal, commits no observation, never hears
another tab's write or has no chart-less fallback fails by name; the control
passes 143/143. **One lead outside the tests**, seen only under the injection:
when another tab's save landed while this tab's own save still waited for its
grant, the storage event redrew the detail block and the handler's later
`redraw()` ran on the detached box (`Cannot read properties of null (reading
'replaceChild')`): the save was in the store and the block stayed on *Save
setup*. **Reproduced on the page, then fixed, in this pull request's one change
outside the tests.** A standalone two-tab script over the `full` fixture, the
store's lock held 1.5 s in tab a before both tabs pressed Save: tab b threw
`Cannot read properties of null (reading 'replaceChild')`, its store held both
setups, its block read `not-following` and its shelf showed one; without the
hold both tabs were consistent. `followBlock()`'s `redraw()` and `warn()` now
find the block the document holds for this setup when the one they drew has
been replaced (`live()`), and leave a block the reader has moved on from alone.
The through suite's two-tab block holds the lock until both saves are queued,
releases it, and reads the second tab's block, shelf and store: on the page
before the fix 142/144, that check and the page-errors check failing by name
(`["not-following", 2, ...]` and the throw); after it 144/144; a comment
control 144/144. The other `replaceChild` sites in `app.js` query the live
node or go through `repaint()`, which already refuses a detached one.

**Publication recovery, issuer evidence and continuity** (four). *New refresh
aborts the superseded headers request* pressed again 150 ms after the first
press, so on a runner where the first request had not yet reached the server
the press aborted a request the server never saw, the stall fell to the
replacement, and the suite threw at its 21 s wait; the second press waits,
bounded by the deadline, until the server holds the first request on its
headers step. *Timeout covers headers and entire body within deadline
allowance* measured the deadline from the server's receipt, which the route
hop delays; both instants are read on the page's own clock now, the fetch as
it is issued and the timeout as it renders. *Race control actually holds a
requested old bundle* polled for about two seconds while the page read and
digested the receipt before asking for the bundle; it waits on the parked
handler itself, bounded at 30 s like the suite's other waits. And the
continuity check's archive recovery gave two 15 ms turns for two thread-pool
digests and a re-render (reproduced with a 40 ms digest); it waits, bounded,
on the Save control and then on the saved sheet. A page that never aborts the
superseded request, arms its deadline a second early, never requests the
bundle or renames the Save control fails by name; the controls pass 131/131,
476/476 and 137.

**Panes, reading, followed plan, actionability** (five fixed, two not
reproduced). Two native scrolls were read 180 ms after the wheel (*selecting
the same stock preserves detail scroll*, *detail bottom is reachable*: with the
settles dropped, eight checks fail across four journeys); the first read now
waits until the pane's offset has left its start and held for eight frames,
the second until the pane is at its bottom, both bounded. *Clearing selection
retains the saved original* read the store 100 ms after a click whose commit
waits for the lock (reproduced with a 300 ms grant); it waits on the cleared
store and the re-rendered control, and an emptied store fails by name instead
of throwing. *Method restores page and detail reading position* read the
positions 180 ms after the return click while `restoreReading()` restores them
in one animation frame (reproduced with a 400 ms frame); it waits for the
focus that frame gives the help trigger. *A disposed panel response is cached*
held the source response on a 350 ms timer against the hash change that
disposes the panel, and with 1.5 s between the click and the change the
response drew the chart on the still-mounted panel and the suite threw; the
response is held on a promise the test releases after the panel is gone. Not
reproduced, and left as written: the map chooser's redraw after a resize (the
rendering update that closes it runs ahead of the driver's read even under a
50x CPU throttle with the sleep removed), and the evidence-focus `--dom` mode's
80 ms mount wait (a 0 ms timer still observes the mounted host; nothing in
that path waits on a timer). A page that resets the pane's scroll on a
same-stock click, hides the pane's overflow, removes the item instead of its
selection, never restores the page scroll or drops the cached response fails
by name; the controls pass 548/548, 57/57, 141/141 and 200/200.




**The first live nights under the new blocks, read off `main`.** Three
publications since #165 and #168 merged: 13, 14 and 15 October (runs
38494353799, 38660383665, 38829043191), RED all three, each `degraded` on
`behind_more` with 16, 19 and 20 stale stocks within the limit of 47 -- WBD,
ending 5 October, is past the five-session bound and degrades every night on
its own, the cost the #105 checkpoint said nothing yet measured (three nights
so far). `run.delivery` 297.2, 255.8 and 247.3 minutes after completion, after
the retry slot and before the next open every time. `run.reads` 0 of 2 (ARXS,
MSM refused), 2 of 2, and 1 of 2 (JAKK refused); at two reads a quarter floors
to a refusal limit of zero, so one refusal degrades such a night.
`run.reader_usage` 2 calls each: 14,649 / 1,150, 14,716 / 1,312 and 14,673 /
837 input and output tokens. **The first live minute bars:** the 13 October run
wanted, asked, fetched and stored 2 (SN and ZIM, the two anticipation plans
whose first day the daily bar could not place), two objects under
`docs/intraday/`. SN is placed: *filled at 09:33 ET, inside the first 30
minutes, at the minute's open, $186.56*, walked to an exit at +1.2%. ZIM is
`not_filled`: *the $30.38 trigger was not reached in the first 30 minutes (its
high in them $30.23); the day reached it at 10:05 ET, after the plan cancels the
day order*. The two nights after needed none and retained both. **The first
live source-recovery receipts:** the 07:37 UTC slot was created at 13:02 UTC on
14 October and 12:49 on the 15th, both before the open, and each published a
receipt (`c5dad9a9`, `145716b7`): the 13 October publication's 16 stale stocks
asked for again in one call, 15 recovered and 1 (WBD) still stale; the 14th's 19,
18 recovered and WBD again -- every recovered bar at zero volume, the provider's
placeholder, as #104 found for the late bars it retained. Both say the
publication is unchanged and the cause not established. The 09:37 slots ran
after the open and published nothing. **Still zero observed:** the morning
checks -- the 13, 14 and 15 October morning slots were created 4.3 to 6.5 hours
late, every collection step skipped -- and `docs/research-observations.json`
does not exist on `main`.

**Measured** (this sandbox, Python 3.11.15, Node 22, Chromium through Playwright
1.56.1, on the final tree `5300a645`): 4608 tests collected, 4574 passed and 34 environment-gated skips in 26 m 58 s (beside the running smoke); `tests/test_docs.py` 40/40
with the suite count unchanged at 4608 (no Python test moved); the full smoke
with `--shots` 15897/15897 in its two lanes, 21 m 20 s, one check more than the
tree it started from (the two-tab race); the touched suites alone, plain:
session 95/95, findings 848/848, following 30/30 (31/31 with shots), lens 66/66,
compare 86/86, refresh 47/47, through 144/144, publication-recovery 131/131,
issuer 476/476, actionability 200/200, followed-plan 57/57, reading 141/141,
panes 548/548; continuity 137; the chart check 378/378; the parity corpus
current (109 cases, 32 accepted by the page). Injections of my own here,
through copies in `tools/` deleted afterwards, beside the families' own: a
1.5 s hold of the store's lock before three Following actions (30/30) and two
lens actions (66/66), the same hold before the render inside `rerender()`
(through 143/143), and two seconds between the load click and the hash change
(actionability 200/200). gitleaks 8.24.3 over the branch's six commits with the
repository's config: no leaks. The follow block after a save and the My setups
shelf at 1280 were looked at: the page change moves no pixel. CI on the pull
request is recorded there.

**Keep / fix / defer / omit.** Keep: a check reads the page's state in the task
of the action that changes it, or waits on the condition, never on the clock;
the suites' fixes are to the suites alone, and the one page change repairs a
defect the sweep exposed, not a test. Fix if it bites: WBD degrades every night until
its bar returns or it leaves the selection, and nothing yet says that in the
record's own words. Defer: #111's ten-session acceptance, which still needs a
morning check that has run; a reading of the recovery receipts across nights.
Omit: any change to the page to make a test pass; a wider tolerance.

**Not claimable:** a morning or research observation; any trading edge.

## Checkpoint, 16 Oct 2026 — PR #173 accepted; the seed stops asking for a stock that stopped trading

**PR #173, accepted.** Merged as `348cd710` on `main` with a merge commit over
`55a458ad`. The head `df5c06ba` passed all seven checks (Tests run 38859329915:
pytest, page, the gate, both native cases; Secret scans 38859329305 and
38859254475). Publisher 38864236322 printed *Verified: every one of the 42
public files matches committed main* at 06:59:16 UTC; Pages 38864262643
deployed (38864235631 cancelled as superseded, as every merge does); the merge
commit's own Secret scan 38864236349 passed and its Tests run 38864236254
passed (06:57–07:25 UTC).

**Revision.** Branch `claude/spicystock-historical-workflow-i53ud1` restarted
from `main` at `348cd710`, pushed as **PR #174**. Nine files move:
`data/symbols.txt`, `README.md`, `.env.example`, `tests/test_docs.py`,
`tools/check_blank_check_universe.py`, `tests/test_historical_input_proof.py`,
the two frozen-fixture files under `tests/fixtures/historical-input-proof/`
and this file. Nothing under `src/` changed and no rule
moved: the seed is membership, not a rule, and the 13 page fixtures reproduce
byte for byte, `rules_version` among them. `docs/data.json`, `docs/picks.json`,
the compact reader, every receipt, the history, the evidence objects, the
quality ledger, the workflows and the vendored design system are untouched; no
run, mail, dispatch, provider call or credential.

**What the record said.** The 13, 14 and 15 October publications are each
`degraded`, each with `behind_more` as the tolerance's one reason (13 and 15
October carry a reader problem beside it, below), and each names ONE frame
ending past the five-session bound: WBD, last bar 5 October, in
`run.input_tolerance.endings` on all three nights (every other stale frame --
15, 18 and 19 of them -- ends on the previous session, within the limit of 47,
`held` empty). The 15 October
follow-up read WBD `still_missing` at every session from 8 to 14 October; the
14 and 15 October source-recovery receipts asked for it again and found it
`still_stale`. `run.universe.selection.seed_added` is `1` with the sample
`['WBD']` on all three nights: the live Nasdaq directory no longer lists it,
and the hand-written seed alone was adding it to the selection, so the
tolerance named a stock the market had stopped quoting. What the sandbox
could read of why: a web search, which put the close of Paramount Skydance's
all-cash acquisition at 6 October 2026 in press reports, with the common
stock's Nasdaq delisting requested, and listed a 2026 definitive merger proxy
(DEFM14A) at sec.gov for the issuer. sec.gov itself does not resolve from this
sandbox, so neither that proxy nor a closing filing was read, and the seed
note says exactly that and no more.

**The change.** WBD leaves the seed's Communication services block and enters
its RETIRED section with a dated note in the file's own convention (EA, FI and
BK before it), citing the blocks it was read off; the header's three mentions
of `get_universe()` in `src/scanner.py`, a reader the 11 September cut
deleted, name `universe.read_seed()` now. README, `.env.example` and
`tests/test_docs.py` say 227 where they said 228, the test holding the file
and both documents to that one literal, so a drift in any of the three fails
it. `tools/check_blank_check_universe.py`,
the dated 22 September classifier sweep, asserted the working seed equal to
its pinned base's; it reads the seed AT that base now, so a later retirement
cannot move a dated reading, and run again it gives the same 13 snapshots, the
same 16 new exclusions and conservation PASS. One defect of mine, found by
running it: the first edit dropped the `seed_raw` name the tool's
`seed_sha256` field still reads, a NameError on its first run, fixed before
anything was committed. Swept for the next instance: the 18 September
stale-input diagnostic (`tools/investigate_stale_inputs.py`) pins four
working-tree files to their blobs of that day -- the seed, `src/inputs.py`,
`src/market_data.py` and `src/universe.py` -- and refused the tree before this
change on `src/inputs.py` and `src/universe.py`, which moved in #84 and again
in #104 and #105; after it the first refusal is the seed's. It is a read-only
reading of one retained artifact at one revision, left as it is, and its tests
never ask it to read the tree.

**What retiring it does, and does not.** The next evening's selection no
longer asks for WBD: `seed_added` falls to 0, the universe membership identity
moves, and the stale list loses the one frame past the bound. Read off the
three publications' own blocks rather than run: with WBD out of the selection,
every remaining stale frame ends on the previous session, so coverage would
have been tolerated on all three nights; 14 October would have been green
(`run.reads` 2 of 2), and 13 and 15 October degraded on the reader alone
(0 of 2 accepted; 1 of 2, JAKK refused). The historical publications keep WBD
as they recorded it, and the follow-up and recovery rows it occupies are
theirs. The burst scan, the tolerance, the follow-up and the recovery are
unchanged: a stock that stops printing is still named every night until a
human retires it, which is the convention the seed file states.

**The review, worked.** A workflow by execution over the pushed tip
`3c3a022b`, three lenses (the facts against the publications, the tests and
the sweep, the documents) and two skeptics per finding, returned nine
findings, seven distinct. Two, each raised by two lenses, were upheld by both
skeptics: the Revision
paragraph said seven files where the diff moves nine, and the sweep sentence
named three of the stale diagnostic's four pins and described its refusal as it
stood before this change. Four were split one skeptic each way, and each was
a sentence saying more than was read: the seed note had the merger proxy
"describing the deal" when only a search listing of it was seen; "each
degraded on `behind_more`" left out the reader problems two of the nights
also carry; "the file's own count" glossed a test that holds the file and both
documents to one literal; and the seed header still named `get_universe()` in
`src/scanner.py`, deleted at the 11 September cut (pre-existing, but prose this
change edits). One was refuted by both: the commit trailer names the model,
which the session's attribution rule requires. Nothing in the code, the frozen
fixture or the tests was found wrong; every fix above is to a sentence, in
the seed note, the seed header and this checkpoint.

**The owner's question, recorded and not decided.** `READER_REFUSAL_FRACTION`
is a quarter, floored: at two reads the refusal limit is zero, so one refused
reply degrades the night, as on 13 and 15 October. Whether two reads should
tolerate one refusal is a policy choice (the #104 checkpoint records the
quarter as the owner's), and nothing here changes it.

**The full suite found the reader the greps had not.** At `632e2d2e` (the
retirement alone) 4573 passed, 34 environment-gated skips and ONE failed in
29 m 50 s: `tests/test_historical_input_proof.py`'s offline boundary, which
stands in for `git_bytes()` on a shallow checkout, served the CHECKOUT's own
`data/symbols.txt` for the seed at the 24 and 25 September execution
revisions and held it to the frozen manifest's digest -- the second shape
this file names, passing only while nobody retired a name. The seed at both
revisions (blob `61fa0d91…`, SHA-256 `ff905018…`, the same bytes at each) is
a frozen copy under `tests/fixtures/historical-input-proof/` now, served in
its place and held to the same digest, and a new test puts a different seed in
a temporary checkout and shows the boundary serves the frozen bytes and refuses
a changed frozen byte. Proved in the mutation worktree at `632e2d2e`: the old
boundary beside the new test fails that test and the manifest test (2 failed,
15 passed); the fixed boundary passes 17; one byte appended to the frozen
fixture fails the same two. The production tool itself was never wrong: it
reads the blob from git at the execution revision.

**Measured** (this sandbox, Python 3.11.15): the full suite at `632e2d2e` as
above, then `tests/test_historical_input_proof.py` 17/17 and
`tests/test_docs.py` 40/40 on the fix, the collection 4609 with the one test
added (this file's count line moves with it); `tests/test_docs.py
tests/test_universe.py tests/test_inputs.py tests/test_market_data.py` 368
passed; `python tools/make_fixture.py --check` 13 fixtures current;
`python tools/check_blank_check_universe.py` 13 snapshots, 16 exclusions,
conservation PASS; `git diff --check` clean; gitleaks 8.24.3 over the changed
and new files with the repository's config: no leaks. No page file moved, so
the chart check and the smoke are CI's, recorded on the PR.

**Keep / fix / defer / omit.** Keep: the seed is a hand-written list whose
retirements are dated and reasoned in the file itself; the nightly blocks are
what found this one. Fix if it bites: a seed name that stops trading degrades
every night until it is retired by hand, and the record says only that it is
stale. Defer: the refusal floor at two reads (the owner's); #111's ten-session
acceptance, which still needs a morning check that has run. Omit: a seed that
edits itself; suppressing a stale stock in code; a wider tolerance.

**Not claimable:** the first evening under the retired seed -- read its
`run.universe.selection.seed_added`, its stale count and its chip, and record
them here; a morning or research observation; any trading edge.

## Checkpoint, 16 Oct 2026 — PR #174 accepted; the three frozen decisions outlive the archive that carried them

**PR #174, accepted.** Merged as `6555538e` on `main` with a merge commit over
`348cd710`. The head `d4f33191` passed all seven checks (Tests run 38875963604:
pytest, page, the gate, the native stress case 08:47–09:15 UTC and central
08:47–09:36; Secret scans 38875963680 and 38875958028). The diff touched nothing
under `docs/`, so the publisher did not fire, correctly (as at #64); Pages
38881709835 deployed at 09:38 UTC; the merge commit's own Secret scan 38881710484
and Tests run 38881710698 (09:37–09:54 UTC) passed.

**Revision.** Branch `claude/spicystock-historical-workflow-i53ud1` restarted
from `main` at `6555538e`, pushed as **PR #175**. Nothing under `src/` changed
and no rule moved; `docs/data.json`, `docs/picks.json`, the compact reader,
every receipt, the history, the evidence objects, the quality ledger, the
workflows other than the fixture step of `tests.yml`, and the vendored design
system are untouched; no run, mail, dispatch, provider call or credential.

**What tonight would have broken.** `docs/historical-validation.json` names
three wait cases by the archive record that carried each (CRL and IQV in
`332b99ff…`, the 24 September record; MSFT in `6fce465e…`, the 25 September
one), and the Record view's *Inspect frozen decision* read both of a case's
files from `docs/history/` by `publicJSON()`. `history.publish()` keeps
`history.DAYS` (21) calendar days: the 16 October publication's cutoff is 25
September, so it deletes the 24 September record's directory, and the 19
October one deletes the 25 September record's. Each button would then have
ended in *This original is unavailable in the retained public archive*, on a
date the study never chose -- the shape this file names worst, in the product
rather than a test -- and `tests/test_reader_request_v2.py`'s MSFT case, which
read the same archive path, would have failed every pull request from 19
October. Found by reading `publish()` and the index (`as_of` 2026-10-15,
oldest sessions 24 and 25 September) the morning before, not by a red run.

**What was built.** `tools/freeze_validation_cases.py` copies each case's
context (`<record>/record.json`) and evidence (`<record>/burst-<ticker>.json`)
byte for byte to `docs/historical-validation/<record>/...` -- the same relative
paths, a directory nothing prunes -- from the archive while it still carries the
record, else from git at the commit the case names, and holds every copy to the
digest the study recorded (`entry.sha256`, `source.context_sha256`).
`case_files()` refuses the study whole on an unknown version, no cases, a record
id that disagrees with its source, an evidence path outside its own record or
not naming its ticker, a malformed digest or commit, or two cases naming
different digests for one context; `freeze()` writes only what is missing,
atomically, never a file the study does not name, and refuses an existing copy
whose bytes are not the study's (left in place), a source whose bytes are not
the digest's (nothing written) and a source over the archive's 256 KiB file
bound; `check()` names a missing copy, a drifted byte and a file the study does
not name; the study file itself is never rewritten. Run on 16 October before the
prune: five files written, `--check` *5 frozen case files current*, every
digest the study's. The study's cases name no commit (`source.commit` is null),
so a copy lost after the prune would need the publication commit written into
its case first; `--check` needs no source. CI runs it beside the fixture checks.

The page reads a case from that directory and nowhere else: `verifiedJSON()` is
the one bounded, digest-checked reader behind `publicJSON()` (the archive, for
the recovery search, its words unchanged) and `studyJSON()` (the frozen files:
the same strict path regex, a required 64-hex digest, the 256 KiB bound, its own
sentences for unavailable, oversize and corrupt). `tools/publish_dashboard.py`'s
`study_case_files()` adds the five files to the public inventory the gate
fetches and matches on the served site -- the study's own list through the
tool's `case_files()`, each held to its digest, a missing or drifted file a
refusal by name, a study without cases (no `cases` field, an empty list or
null, as the test fixtures' synthetic roots) none -- so the count the gate
prints moves from 42 to 47. `.gitleaks.toml`'s first
allowlist, the rule-key disposition, covers `docs/historical-validation/
<record>/(record|burst-<T>).json` beside the archive path and nothing beside it
(the two frozen contexts carry `down25_quarter` and `pct_above_40ma`, which
the engine flags: 4 findings before the change, 0 after, a sibling file and a
lookalike directory still flagged). `tools/historical_cases.mjs` serves the case
records' archive directories 404 while it inspects CRL and asserts the two
files were read from `historical-validation/` and nothing from `history/`; three
added contexts serve CRL's frozen evidence tampered (one byte appended),
oversize and missing, and hold the page to its own sentence, no original shown, no archive
asked, Inspect enabled again, and the deliberate 404 counted off the response
event rather than the console (one for the missing file, none for the other
two, two after a second press, which shows one sentence and not two). The MSFT
authority test reads the frozen copy under its digest.

**Measured** (this sandbox, Python 3.11.15, Node 22, Chromium through Playwright
1.56.1, on the final tree): 4655 tests collected; the full suite at `db1e3ac2`
-- the tree before the strays' sort below, which changed one tool, its test
file and this file -- 4620 passed and 34 environment-gated skips in 24 m 58 s
(run in the mutation worktree, which mirrors the tree byte for byte, the mirror
checked by the diff's digest), and on the final tree `d912de09` 4621 passed and
34 environment-gated skips in 24 m 47 s, the same way;
`tests/test_freeze_validation_cases.py` 33; the eight touched Python test files
(`test_freeze_validation_cases`, `test_publish_dashboard`, `test_docs`,
`test_workflows`, `test_reader_request_v2`, `test_secret_scan`,
`test_discovery_grading`, `test_findings_page`) 299 with the count line at 4655;
`python tools/freeze_validation_cases.py --check` current and under
`python -I -S`; `python tools/make_fixture.py --check` 13 fixtures current (no
record moved); continuity 137; the `historical` suite 124/124 with
`--shots` at 390, 320 and 1280, both themes, the three refusal contexts at 1280
(85 on `main`), and 124/124 again with the deliberate 404 held back 5.5 seconds,
the injection the review used; gitleaks 8.24.3 with the repository's config
over the frozen copies (0 findings; 4 without the allowlist, the engine's own
view) and from inside a root holding every changed and new file (20 files, no
leaks, after one of my own: a Stripe-shaped example value in the new allowlist
test tripped the engine's own detector and is a hashed canary now); the 100
real-engine controls of `tests/secret_scan_controls.py` PASS, 24 of them new
over the frozen path (per frozen context: defaults, exact, unrelated, altered,
sibling, lookalike directory, prefix, suffix, a record id one character over
forty, an upper-case spelling of it, a ticker one over sixteen, another
detector). The 390 dark frozen-case screenshot was looked at: the case renders
as before, from the frozen bytes.

**Mutation passes**, the tree never written. Python, each mutant in the
mutation worktree and judged by the whole test files naming its rule:
thirty-five die and one is moot -- the tool's ticker check, its
conflicting-digest check, an existing different copy overwritten, the source
digest unchecked, `check()` ignoring an unnamed file and comparing no bytes,
the file bound dropped, a path outside its record admitted, the git fallback
reading HEAD (alive until the three-commit test below), `check()` passing a
linked copy, `freeze()` counting one as a copy, the walk ignoring a linked
directory or following links, the frozen directory itself a link, a direct
write in place of the temporary file, the temporary file left behind on a
failed replace, the walk restricted to `*.json`, `check()` raising on an
unreadable copy, the strays' order left to the filesystem; the publisher skipping the digest, swallowing a missing file,
serving a study it cannot, refusing an empty case list and not extending the
inventory; the scanner's frozen path removed, widened to every file in the
case directory, to a record id of forty or more characters, to upper-case hex
and to a seventeen-character ticker (the last three dead in the allowlist test
AND in the real-engine controls, the record-id one only once its case appended
a hex digit rather than the `x` the review suggested, which no hex class
absorbs); CI's freeze check dropped. The moot one, `main()` letting an
`OSError` out, has nothing left to let out once `freeze()` and `check()` name
every tree-shape fault themselves. The controls (a docstring word, a comment, a
comment in the scanner's config) stay green, the publisher's once the
worktree's suite-count line was current. Page, through routed copies of
`app.js` judged by `--only historical`: six mutants over three passes -- the
study loader reverted to `publicJSON` (25 checks), the study reader reading
`history/` (24), falling back to the archive on a refusal (7), its digest
unchecked (3), its bound dropped, and after the review the catch stacking a
second alert (3) -- all die, each by the check naming its rule, and the control
(a comment) stays green each time. **The bound SURVIVED the first pass**, the
second shape this file names: no frozen file is near 256 KiB, so nothing read
the bound; a third refusal context serves CRL's evidence padded past it and
holds the page to the bound's own sentence rather than the digest's, and it
dies (117/118 then).

**The review, worked.** A workflow by execution over the pushed tip
`94df35ad`, four lenses (the page and its suite; the tool and the publisher;
the scanner and its controls; the documents), each finding meant for two
skeptics. The finders returned sixteen. **The skeptic stage did not run**: my
script handed `parallel()` promises where it wants thunks, so one skeptic (the
page lens by execution) finished before the error and the rest never started.
It upheld the console-404 finding's first half (a 404 answered 5.5 seconds
late fails the check for a reason it does not name) and could not reproduce
its second (a late 404 missed by the no-404 checks, in three runs); nothing
else was judged, and an unjudged finding is not refuted, so each of the
sixteen was reproduced here by execution before it was touched, and each is
fixed. The page: the deliberate 404's count was read off the console at an
instant (counted off the response event now, and 124/124 under the review's
own 5.5-second delay), and a second Inspect press after a refusal stacked a
second identical alert (pre-existing; the catch removes the earlier one, and
the missing context presses twice). The tool: it took a symbolic link for a
frozen copy -- `check()` tested presence with `is_file()`, which follows
links, so a link into the archive's still-present original passed `--check`
and `freeze()` reported it kept, and a dangling link or a linked directory
under the frozen tree was named as nothing (the publisher's own reader already
refused a linked file, so a committed one would have failed publication, not
the tool); a link is never a copy now, named wherever `check()` finds it,
refused by `freeze()`, and the walk never follows one. The git fallback's "at
the case's commit" had no test that could fail (a tool reading HEAD survived
the file; the test commits the publication, prunes the archive in a later
commit and names the earlier one, and refuses a commit from before the
publication). The temp-then-replace write had no test, and a failed replace
left `<name>.tmp` behind that `--check` then named as an unnamed file (an
`OSError` is a refusal by name now, the temporary file unlinked, and `check()`
clean after it). `check()`'s unnamed-file rule was exercised with `.json` names
alone (it plants a `.tmp` and a `README` now). The publisher refused a study
with an empty or null case list with a sentence about a case it could not
serve (such a study names no files, as the docstring said). Tree-shape faults
-- the case directory a regular file, a frozen target a directory -- escaped
`main()` as tracebacks (named refusals now, and an unreadable copy a `check()`
problem rather than a raise). The scanner: the frozen path's three bounds had
no assertion that could fail (above). And the documents: "107 on `main`" was
false (the suite prints 85 there); "292" counted eight files where the
sentence named seven; the draft described `94df35ad` while the branch stood at
`36a51c8b`; four in-tree sentences (README, the publisher's docstring, the
suite's header, the reader test's comment) stated tonight's prune as a past
event on a tree whose archive still carries both records, and say "leaves" and
"drops" now; and "six mutants" introduced a list of five.

**CI found what the sandbox had not.** The pytest job on `36a51c8b` failed one
test, 4648 passed: `check()` reported the files the study does not name in the
order the filesystem listed them, and the runner listed the lookalike directory
before the case's own, where this sandbox lists them the other way round -- the
shape this file names worst, in a test's expected order. The strays are
collected and reported in path order now, whatever order the walk yields; a
test drives the walk in reverse and holds the report to that order, and the
symbolic-link test's expectation moved to the same order. The mutant that drops
the sort dies in both tests; the control (a comment) passes 33.

**Keep / fix / defer / omit.** Keep: the study's digests are the authority; a
frozen copy is read under them or not at all, and the rolling archive is never
asked for a case. Fix if it bites: `tools/build_historical_review.py`, the
one-off 28 September builder of the study, still reads `docs/history/index.json`
and would need the frozen directory to rebuild. Defer: #111's ten-session
acceptance, which still needs a morning check that has run; the first evening
under the retired seed, still ahead. Omit: a copy of the whole archive; a page
fallback from the frozen files to the archive.

**Not claimable:** the served site after tonight's prune -- the publisher
prints its count on the merge, and the first publication after it is the
first the Record view inspects over an archive that no longer carries the
record; a morning or research observation; any trading edge.

## Checkpoint, 16 Oct 2026 — the stale stocks the seed alone asked for

**Revision.** Branch `claude/spicystock-historical-workflow-i53ud1` restarted from
`main` at `1e66929c` (the merge of #175), pushed as **PR #176**. `docs/data.json`,
`docs/picks.json`, the compact reader, every retained receipt, the history, the
evidence objects, the quality ledger, the workflows and the vendored design
system are untouched; no run, mail, dispatch, provider call or credential.

**PR #175, accepted.** Merged as `1e66929c` (merge tree `c11e23c4`, the PR head
`1131d4a9`'s tree to the byte). Tests `38900948089` on the merge commit itself
green (12:30 to 12:56 UTC); Secret scan `38900948429` passed; publisher
`38900948063` printed *Verified: every one of the 47 public files matches
committed main* at 12:32:03 UTC; Pages `38900991213` deployed (`38900947004`
cancelled as superseded). The three frozen cases are served under the study's
digests, and tonight's prune can no longer take them off the Record view.

**What the record showed, and what it took to read.** The 15 Oct publication
(run `38829043191`, published 00:22 UTC on 16 Oct) is `degraded` on `behind_more`:
twenty stale stocks, nineteen ending 14 Oct and WBD ending 5 Oct. Its universe
ledger says `selection.kind` directory, `seed_added.count` 1, sample `["WBD"]`.
Both facts were in the record and nothing joined them: that WBD was stale every
night BECAUSE the seed alone asked for it, a name the directory had dropped,
was read by hand off two blocks, and the retirement (`632e2d2e`, 07:20 UTC, a
`RETIRED` note in `data/symbols.txt`) was done by hand. A stock the directory
still lists goes stale and comes back; a stock only the seed lists stays stale
until someone edits a file, and the record should say which is which.

**The rule.** `inputs.seed_stale(tol, selection)` writes `run.seed_stale`
(version 1, archived as `pipeline.seed_stale_version`, so `rules_version` moves
and older records are asked for no block). It reads two lists the record already
carries and nothing else: the tolerance's stale `names` and the selection's
`seed_added` sample. `membership` is `complete` when the sample IS the
membership (`count == len(sample)`), `sampled` when the ledger's bound
(`universe.SAMPLE_LIMIT`, 8) cut it, `unavailable` when the universe was not a
directory selection (a seed or explicit universe: there is no directory to be
"not in"). `names` is the sorted stale-and-seed intersection, the benchmark
excluded, only when membership is complete and the stale names are carried;
every other case is `None` with one `reason` (`no_directory_selection`,
`seed_universe`, `explicit_universe`, `seed_additions_sampled`,
`stale_names_not_carried`). `seed_stale_sentence()` says only what the lists
show: nothing on a night with nothing stale; "is not recorded: <why>" when the
join could not be made; "None of the N stale stocks is on the seed alone; each
is in the directory this run selected from." when it was made and found none;
and "k of the N stale stocks are on the seed alone, not in the directory this
run selected from: <names>. A seed name that has stopped trading stays stale
every night until it is retired from data/symbols.txt by hand." when it found
some. `report.validate()` asks for the block only under rules that write it
(`inputs.seed_stale_faults`: missing, version unknown, malformed, or not what
the record's own tolerance and selection re-derive) and refuses a forgery one
level in. The mail prints the sentence in the inputs block right after the
"Without a <session> bar: …" line; the page prints it on the cover between the
stale names and the follow-up sentence and under Method as *Seed check:*; a
missing or half-written block prints nothing, and the page adds no words.

**Projected over the 15 Oct record** (read-only, the module over the published
blocks): membership complete, 1 of 1 seed additions named, `names` `["WBD"]`,
and the sentence "1 of the 20 stale stocks is on the seed alone, not in the
directory this run selected from: WBD. A seed name that has stopped trading
stays stale every night until it is retired from data/symbols.txt by hand." —
the sentence that would have named the retirement before anyone read two blocks
by hand. Over the `thin` fixture, whose universe is an explicit list, the block
is `unavailable` / `explicit_universe` and says so; the seed-only case is driven
through `run_evening()` over a directory universe in `tests/test_inputs.py`
(two stale stocks, one on the seed alone: block, validation, mail and trades
all read) and through a routed browser variant in the `inputs` suite.

**16 Oct service observations.** The source-recovery cron `37 7 * * *` fired at
12:41 UTC (run `38902285071`, 5 h 4 min after its slot), asked for the 15 Oct
publication's twenty stale stocks in one bars call, and published `00cd2d2a` at
12:42:44 UTC: nineteen now carry a 15 Oct bar that passes the session rules
(seventeen with zero volume, eighteen flat) and WBD still ends 5 Oct; the
publication stays 4757 of 4777 intended stocks ready and nothing downstream
moved. Publisher `38902464259` verified the commit. WBD left the seed at
07:20 UTC, after that publication ran, so tonight's evening is the first under
the retired seed.

**Measured** (this sandbox, Python 3.11.15, Node 22, Chromium through
Playwright 1.56.1): 4681 tests collected, 4647 passed and 34 environment-gated skips in 27 m 19 s in a
worktree copy whose diff hashes equal to this tree's, one test-case edit before
the final tree (that case's file was then run in full here: 245 passed); docs tests 40/40 with the count line at 4681;
fixtures current through their generators (13 page, 21 morning pinned, 30
issuer, 22 stop-research, 40 research-outcomes, 24 research-observations, 20
source-recovery, 6 cash-preview, the first-trade backup and its 109-case parity
corpus, 5 frozen validation copies); the `inputs` suite 266/266 at 1280 and 390
in both themes; the full smoke with `--shots` 15963/15963 (15957 before the review's
fixes), the screenshots at 1280 and 390 in both themes looked at: Method's
*Seed check:* line sits above the follow-up on the phone, the cover's first
screen measures what it did before; gitleaks 8.24.3 over the 122 changed files from
inside a scratch root with the repository's config: no leaks.

**Mutation passes**, each mutant in its own copy of the tree, the working tree
never written, judged by the full test files naming its rule (no `-k` filter).
Python, in a
worktree copy of the tree: sixteen over the first tree, thirteen dead in the
test naming their rule, the docstring control green, and **two survived, each
a hole**: `names_unsorted` lived because no case had two seed-only stale names
(one does now, in reverse symbol order), and `validator_gate_dropped` lived on
the first shape this file names -- the gating test popped every block and
every rules key together, so with the gate gone the tolerance's absence
short-circuited the check before the gate could be reached; a record made
between the tolerance's second version and this rule (every publication from
8 to 15 Oct) is the case now, and it also kills the reviewer's two wrong-key
gates. Then twenty-five over the final tree, the review's own validator mutants among
them (a gate on another rules key, the rules half of the version check
dropped, the coverage guard dropped, `is None` for the shape check, Python
equality for the canonical bytes, the record guard dropped, the sample bound
not archived, the mail's order swapped, the closing sentence dropped):
twenty-four dead in the test naming their rule, the control green, and **two
survived on the first pass, each a hole closed with its case**: the shape
check's case used `None`, which `is None` handles the same way (a bare list of
names now, the shape the ledger's own reconciliation refuses); and nothing
held `universe.sample_limit` to the archived rules (the run test does now).
Both die re-judged. The final pass caught a regression of mine
before anything was committed: its CONTROL died in six seconds, because the
`record_faults` guard had turned an older archive's empty selection into a
size fault, in a test the focused selection I had run had filtered out. Fixed,
pinned by a case, and the pass re-run. The page, through routed copies of
`app.js` against the `inputs` suite: six mutants (the cover's seed sentence
dropped, Method's dropped, Method's order against the follow-up swapped, the
page adding a word of its own, a half-written block printing `undefined`, the
cover's order swapped) all die in the check naming them, and an equivalent
control stays green.

**The review, worked.** A workflow by execution over the first tree: six finders
(the join, the validator, the two surfaces, the tests, the docs, the fixtures),
each reproducing what it reported, returned sixteen findings; the skeptic
stage was stopped before it had judged one, because every finding was checked
here by execution instead, the tree being about to change under it. Two
were medium and both were test holes: the validator's gate key was pinned by
no test (a gate on `delivery_version` passed the whole selection while it
refused the live 15 Oct record), and the mail's order of the seed sentence
against the follow-up was pinned by nothing. The rest were low, and most are
fixed: the closing sentence claimed what the two lists cannot show ("stays
stale every night", when a name the fetch window has passed goes to `no_bars`
instead), so it says what the seed does, "is asked for again every night until
it is retired from data/symbols.txt by hand"; the re-derivation compared Python
values, so a JSON `true` or `1.0` where the run writes `1` was the same block,
and it compares canonical JSON bytes now (`_canonical`, a NaN refused);
Method listed the seed check after the follow-up where the cover and the mail
put it before; the sample bound that decides `complete` against `sampled` was
in no document and not archived (`universe.sample_limit`, 8, is in the rules
now, so `rules_version` moved again and the fixtures with it); `record_faults`
raised through `validate()` on a `run.universe` or selection that was not an
object, byte-identical since before this branch and the class this file names
most, and names it now; the guard's comment misattributed what names a missing
coverage ledger; README named Method and the mail and not the cover; CLAUDE.md
placed the join before breadth where the code makes it at the record; the
inputs.py literal guard did not scope the three new functions. Two are
recorded and not fixed: a seed-only name that returns no bars at all is under
`coverage.no_bars`, not stale, and the block says nothing about it (the join
over that list is the next step if it bites); and without provenance the
selection's `kind` is not held to `run.universe.source_kind`, a reconciliation
that belongs to the selection ledger, not this block. One was the count line,
right for the tree it read and moved again by the cases added since.

**Keep / fix / defer / omit.** Keep: the block reads two lists the record already
carries and says nothing they do not show; the ledger's sample bound is the
ledger's, so nine or more seed additions make the join `sampled` and named, not
guessed. Fix if it bites: the block names a seed-only stale stock every night
until the file is edited, which is the point, and nothing counts how many nights
that has been. Defer: retiring a seed name automatically, which the seed exists
to refuse. Omit: suppressing a stale stock, re-fetching it, or treating its late
bar as a signal.

**Not claimable:** a live night. The first evening after the merge writes the
first `run.seed_stale`; read its `membership`, `names` and sentence beside the
chip, and record them here.

## Checkpoint, 16 Oct 2026 — PR #176 accepted; the validator names a shape instead of raising

**PR #176, accepted.** Merged as `3117f46a` on `main` with a merge commit over
`1e66929c`. The head `08af3ce5` passed all seven checks (Tests run
38922240762: pytest 4681 passed in 13 m 16 s on Python 3.12.15, page, the gate,
the native central case 15:14–15:40 UTC and stress 15:14–16:05; Secret scans
38922240759 and 38922186413). Publisher 38929254638 waited for `app.js` and
printed *Verified: every one of the 47 public files matches committed main* at
16:07:26 UTC; Pages 38929297514 deployed (38929255024 cancelled as superseded,
as every merge does); the merge commit's own Secret scan 38929254751 passed and
its Tests run 38929254778 is green (pytest 16:06–16:26 UTC, page 16:06–16:21;
the native cases skipped by the gate, as a merge's are). The first `run.seed_stale` is tonight's publication's, the
first evening under the retired seed (WBD left `data/symbols.txt` at 07:20 UTC,
after the 15 October publication ran); read its `membership`, `names` and
sentence beside the chip and `seed_added`, and record them in the next
checkpoint.

**Revision.** Branch `claude/spicystock-historical-workflow-i53ud1` restarted
from `main` at `3117f46a`, pushed as **PR #177**. Four modules move by a guard
or two (`src/inputs.py`, `src/followup.py`, `src/report.py`,
`src/universe.py`), one test file is new, README and this file are swept; no
rule moves, so
`rules_version` stays and the 13 page fixtures and every cascaded generator
are untouched. `docs/data.json`, `docs/picks.json`, the compact reader, every
receipt, the history, the evidence objects, the quality ledger, the workflows
and the vendored design system are untouched; no run, mail, dispatch,
provider call or credential. `.env.example` was reviewed: nothing here is
configuration.

**What the probe found.** The #176 review had found `inputs.record_faults()`
raising through `report.validate()` on a `run.universe` or a selection that
was not an object, and that pull request named both. The standing rule says to
sweep for the next instance before calling the class closed, so a probe
substituted a string, a list and an integer at every top-level key of the
`thin` record, every child of a top-level object and every grandchild under
`run`, and held `validate()` to a `ValueError` or a pass. Six paths raised
something else (fourteen substitutions, over five lines in four functions),
each the class this file names most -- a check that names a fault, followed by
another that indexes into the same value: `run.problems` as `5` or
`True` (`followup.faults()` iterated it after `validate()` had named it not a
list: `TypeError`); `run.timing` as `'x'` (`sessions.record_faults()` read
`.get` off it beside a calendar block, an `AttributeError` its own `except`
does not catch); `observations.symbols`
as `'x'` (`validate()` named it not an object, then called `.items()` on it);
`run.coverage.acceptance` as `'x'` (`inputs.record_faults()` read its status);
`run.coverage.benchmark_added` or `run.universe.size` as `'x'` (added to an
integer). Every retained publication and fixture carries the right shapes, so
no record ever hit one; a half-written record would have, after every paid
call was made, and the page's own shape check would have had no fault to
print.

**The guards.** Each site asks the type first and names the shape in its own
words: `run.problems` that is not a list is named by `validate()` alone and
`followup.faults()` reads no kinds off it; `run timing is not an object beside
its calendar` is named by `validate()` itself, which then does not ask
`sessions.record_faults()`; `observations.symbols` that is not an object is
named once and not walked; `coverage acceptance is not an object`; `universe
size or benchmark count is not an integer` (`type(...) is int`, so a `True` is
refused too). A fault is appended or returned, never raised, and every other
clause of each function is unchanged.

**The full suite found what the focused runs could not.** The timing guard was
first written where the read is, two lines in `sessions.record_faults()`, and
the focused files passed. The full suite
in the worktree copy then returned 5 failed, 4294 passed, 33 skipped and 362
errors in 27 m 15 s, every error one assertion: `src/sessions.py` is one of
the historical delivery proof's `required_source_paths`
(`tools/historical-delivery-compatibility.json`, beside `breadth`, `quality`
and `scans`), pinned by SHA-256 in the accepted delivery's receipt, and the
guard's two lines moved its digest from `aea32502…` to `0fadc3b4…`; the
benchmark gate's five failures read the same digest. This file already records
the class for `tests.yml` (the findings checkpoint: 363 binding tests red on an
edit). The pinned module is byte-identical to `main` again, and `validate()`
names the shape before it asks the module; nothing of the proof's binding is
touched, and a change to any of those four `src` modules is a change to the
delivery proof, which this loop does not make.

**The review, worked, and the three more it found one level deeper.** A
workflow by execution over the pushed tip `de884a5f`, three lenses (a deeper
fuzz, the guards' semantics against `main`, the words against the code), each
finding meant for two skeptics, with each finder in its own worktree. The
deeper fuzz walked where the committed one did not -- list items and
great-grandchildren under `run` -- and found three more raises, each
reproduced here before it was touched: `bursts[i].ticker` as a list or an
object (the validator added it to a set: `TypeError`), and so a `trades[]` or
`beyond_cap[]` element asked of that set; `run.coverage.sessions.
latest_bar_dates` as a string (`inputs.faults()` read `.values()` inside an
`except` that named `KeyError`, `TypeError` and `ValueError` and not
`AttributeError`); and `run.universe.selection.exclusions` the same way in
`universe.selection_faults()`. The semantics lens confirmed by execution that
every committed record -- the 13 page fixtures, `docs/data.json`, the retained
grading records -- validates identically at the tip and at `main`, that
`run.universe.size` and `run.coverage.benchmark_added` are plain integers in
every retained record (so `type(...) is int` refuses nothing the run writes),
and that each guard revert dies in its named case and in the fuzz; and it
found one regression of fault TEXT: on `main` a wrong calendar beside a
non-object timing named the calendar (`sessions.record_faults()` checks the
calendar before it reads the timing), and the first guard, by not asking that
module, masked it behind the shape fault. Fixed: `validate()` names the shape
and then asks the module over an empty timing block for its calendar faults
alone, so a doubly malformed record names both; the ticker is held to a string
before the set is asked and a `trades`/`beyond_cap` element to a string before
the set is searched; the two `except` tuples name `AttributeError`, as the
file's other two already did. `src/universe.py` is not a pinned source
(`breadth`, `quality`, `scans`, `sessions` are), so it could be edited. The
words lens re-derived both digests, the pinned-source list, the test counts,
the fault strings and the unheld keys and found them right, and found three
sentences saying more than the evidence: README's "a block that is not an
object, a count that is not an integer or a list that is not a list is a fault
by name" (a `scorecard` that is a string passes; it says now what the fuzz
proves and names what passes); "six substitutions" where the probe's walk gave
fourteen substitutions on six paths; and a fuzz bound written as "less the
shapes a path already had" while the code subtracted a constant three, with no
slack left on the `full` night -- the count is exact now. Two figures of the
first draft named no files and are named or dropped above.

**The guard that cannot be deleted quietly.** `tests/test_record_shapes.py`
holds the two fixtures passing as committed; each of the eleven paths that once
raised (the six above, #176's two, the review's three) to its named fault, the
two list cases on the `full` night, which alone carries trades and a
beyond-cap list; the doubly malformed record naming both faults; and the fuzz
itself: over every top-level key, every child of a top-level object, every
grandchild and great-grandchild under `run`, and the first item of every
top-level list with each of its children, on the `thin` and `full` records --
`_paths()`, held to reach a fourth key and a list -- each of `'x'`, `[1]` and
`5` is substituted in place and restored, `validate()` is held to a named
refusal or a pass, a raise of any other kind failing with the path and the
shape in its message, the count of substitutions held exactly (three per path
less the values that already were a shape), refused more than passed, and the
record held equal to a copy taken before the walk, so the validator is shown
to write nothing into it. Recorded, not fixed: `closest_miss`, `generated`,
`schema_version` and `scorecard` substituted whole with a string pass
`validate()`, which never indexes into them; the fuzz counts them among the
passes, and a check on any of them is a change to what the record promises,
not to this guard.

**Measured** (this sandbox, Python 3.11.15): the full suite on the pushed tip
`de884a5f`, in a worktree copy whose diff hashed equal to the tree's, 4660
passed and 34 environment-gated skips in 28 m 07 s beside the running review
(4694 collected), and on the final tree `9d924572` 4666 passed and 34
environment-gated skips in 26 m 40 s (4700 collected);
`tests/test_record_shapes.py` 19 passed in 33 s (the fuzz substitutes in
place and restores, so its 542 and 570 paths cost under a minute);
`tests/test_report.py`, `test_inputs.py`, `test_universe.py`,
`test_followup.py` and `test_docs.py` 463 passed in 4 m 23 s (on the first
tip `de884a5f`, `test_record_shapes`, `test_report`, `test_inputs`,
`test_followup` and `test_docs` 359); `tests/test_historical_execution_guard.py`,
`test_historical_benchmark_gate.py`, `test_historical_delivery_binding.py`,
`test_historical_native6_recovery.py`, `test_historical_incident_recovery.py`,
`test_historical_recovery_integration.py`, `test_historical_execution.py` and
`test_historical_workflow.py` 584 passed and 1 skipped on the moved guard,
where the first tree had them erroring; `tests/test_docs.py` 40/40 with the
count line at 4700;
`python tools/make_fixture.py --check` 13 fixtures current (`rules_version`
unchanged); `git diff --check` clean; gitleaks 8.24.3 from inside a scratch
root holding the changed files and the repository's config: no leaks. No
record, rule or page file moved, so the fixture checks, the chart check and
the smoke are CI's, recorded on the PR.

**Mutation passes**, each mutant in the worktree copy, the tree never
written, judged by the whole new test file. Over the first tree, the six
guards reverted one at a time -- the follow-up iterating `problems or []`, the
timing guard dropped (`if False:`), the symbols walk unguarded, the acceptance
read unguarded, the arithmetic unguarded, and #176's universe guard dropped --
all die, each in the case naming it AND in the fuzz on both fixtures; an
earlier pass, over an earlier draft of the fuzz, had killed four of them in
the named case alone, the fuzz reaching none of the four, which is why it
walks past the top level now. Over the final tree, fifteen runs, thirteen
mutants and two controls: those six again,
the calendar probe dropped (dies in the doubly malformed record's test alone,
as it should), the ticker guard dropped, the `trades`/`beyond_cap` guard
dropped (dies on the `full` night's two list cases and its fuzz), each
`except` narrowed back, and two mutants of the fuzz's own walk -- the
great-grandchildren dropped, the lists skipped -- each dying in the fuzz's
assertion that it reached a fourth key and a list. Thirteen die; the two
controls (a word in the follow-up's comment, a word in the validator's)
survive at 19 passed.

**Keep / fix / defer / omit.** Keep: a validator names and never raises; a
block is read after its shape is asked, one level in, and the fuzz is what
keeps the next guard from being forgotten. Fix if it bites: the fuzz walks the
`thin` and `full` records only, so a block those records do not carry (a
closed night's, a legacy one's) is fuzzed only by the cases that name it.
Defer: the four unheld top-level keys above. Omit: a fuzz over random shapes,
or over every grandchild of every block, which would run minutes for the same
answer.

**Not claimable:** tonight's evening publication, the first under the retired
seed and the first with a `run.seed_stale` block; a morning or research
observation; any trading edge.

## Checkpoint, 17 Oct 2026 — PR #177 accepted; the first night under the retired seed, read; the service read again through it

**PR #177, accepted.** Merged as `d89e4e90` on `main` with a merge commit over
`3117f46a` at 18:31 UTC on 16 October. The code heads `de884a5f` and `9d924572`
and the docs head `8847c8d6` each passed all seven checks; on the merge commit
itself Tests run 38948032930 passed (page 18:31–18:48 UTC, pytest 18:31–18:55,
the native cases skipped by the gate, as a merge's are), Secret scan
38948032803 passed and Pages 38948031418 deployed at 18:33 UTC. The publisher
did not fire, correctly: the diff touched nothing under `docs/` (as at #64 and
#174), so the served site stayed the #176 merge's 47 verified files.

**The review workflow starved, and the sandbox with it.** Of the #177 review's
29 agents, 18 failed on `No space left on device`: the disk was 100% full with
229 MB free, 17 isolation worktrees of this and an earlier review still present
under `/home/user/SpicyStock/.claude/worktrees/` (about 300 MB each; a review
agent's worktree is removed only when it finishes, and an agent that errors
leaves its own behind) and about 21 GB of scratch copies from finished
milestones. The findings that reached a skeptic were upheld; the nine that did
not were each reproduced and fixed by execution, as the #177 checkpoint
records, and null was not read as refuted. Cleaned the same evening: the 17
worktrees removed through `git worktree remove --force` on literal paths and
pruned, their 49 `worktree-wf_*` branches deleted, 38 scratch directories
removed (the kept ones: `ft/`, `venv312`, `gitleaks`); 24 GB free after. The
rule that follows: read `git worktree list` and `df` before launching a review
workflow, and remove the worktrees it leaves when any agent errors.

**Revision.** Branch `claude/spicystock-historical-workflow-i53ud1` restarted
from `main` at `426d3c59` (the issuer receipt that followed the 16 October
publication), pushed as **PR #178**. One constant moves in one tool
(`tools/service_health.py`'s `OUT_DIR`, to the 17 October directory); the 17
October reading and its report are new; the 12 and 13 October reports gain a
sentence each; `tests/test_service_health.py` pins the 13 October files and
reads the 17 October report; README and this file are swept. Nothing under
`src/` changed and no rule moved; `docs/data.json`, `docs/picks.json`, the
compact reader, every receipt, the history, the evidence objects, the quality
ledger, the workflows and the vendored design system are untouched; no run,
mail, dispatch, provider call or credential. `.env.example` was reviewed:
nothing here is configuration.

**The first night under the retired seed, read.** Session 16 October, run
38986314620, the `16 22` primary slot created at 00:25:39 UTC on the 17th
(129.7 minutes late), the pipeline 00:26:16–00:29:23 (`elapsed_seconds` 145.4,
`fetch_seconds` 78.5), the record's own clock (`published_at`, set when the run
starts) 00:26:18, landed as `7a1a9e49` at 00:29:26, the mail delivered. `run.status` **ok** beside a
`degraded` acceptance -- the third session the tolerance kept green (9 and 12
October before it), and the first since 12 October with no frame past the bound: `run.universe.selection.seed_added` is
0 with an empty sample (WBD left `main`'s seed with the #174 merge, `6555538e`,
at 09:37 UTC on the 16th -- the 07:20 UTC the #176 and #177 checkpoints give is
the branch commit's time; the 15 October night's was 1, `['WBD']`), 4,759 of 4,777 intended stocks ready, and
`run.input_tolerance` (version 2) `tolerated`: 18 stale stocks (ACVA, ATXG,
BSBK, CVR, DIT, FKWL, GBLI, HFBL, IOR, MAYS, NCEW, NSYS, PBHC, RAND, ROMA,
SENEB, SFWL, XBP), every one ending 15 October, `held` empty, against the limit
of 47. **The first `run.seed_stale`** (version 1): membership `complete`,
`seed_added` 0, `seed_named` 0, `stale_stocks` 18, `names` empty, no reason,
and the sentence *None of the 18 stale stocks is on the seed alone; each is in
the directory this run selected from.* The sentence the rule was built to print
-- WBD's -- would have run on every publication from 7 to 15 October, seven
sessions (`inputs.seed_stale()` re-derived over each record names WBD on all
ten); on the first night it ran
the seed had already been retired by hand, so its first live case is the none
case, and the record now says so on every night rather than leaving the join to
a reader. `run.stale_followup` (version 2, `applied`) read the 15 October
publication's 20 stale stocks again, 24 readings -- WBD at the five sessions it
missed (9 and 12–15 October), the other 19 at 15 October alone: 13 `no_match`, 5 `price_excluded`, 6 `not_selected` (WBD
at all five sessions, and TJGC at 15 October), 0 `match`; of the 18 readings that
carried a late bar, 16 at zero volume (the provider's placeholder again) and 17
flat; GEG's carried 2,891 shares and NCEW's 237. `run.reads` 2 of
2, `complete` (AIG and AR, the review selection's two research reads under
RED; the refusal limit at two reads is 0). `run.reader_usage`: 2 calls, 2
replies, 14,667 input tokens (7,995 uncached, 3,336 written to the cache,
3,336 read) and 1,059 output, under `claude-sonnet-4-6`. `run.delivery`: 251.3
minutes after completion, after both slots (130.3 after the primary), before
the next open, Monday 19 October 9:30 AM ET. `run.intraday`: `gathered`,
wanted 0, retained 2. The signal, kept apart: RED (10-session ratio 0.63, 1,116
up against 1,768 down; 5-session 0.45; 32 up 4% against 239 down today, "a
fast selling phase"), `funnel` 206 reaction candidates (mechanical A+ 0, A 28,
B 31, C 28, skip 119), all 206 at the market gate, 0 potentially usable, 0
tickets; anticipation 707 momentum names, 162 quiet, 8 passing the coil checks,
0 listed, 0 tickets; the closest miss AIG at B 9.0; the cover *Stand aside.*;
`rules_version` `f6c9a7388d9c`. The `16 23` cron (run 38990388404) -- the
EST season's primary, inactive while the US is on EDT -- was created at
01:19:53 UTC, 123.9 minutes after its slot; its guard printed *Not the active
UTC slot* (job 117271274212) and every step after it skipped.

**The publication's path to the served site.** The evening's own persist is a
`GITHUB_TOKEN` push and triggers no workflow (this file's standing note); the
issuer-evidence workflow, which the evening's completion triggers, collected
`no_candidates` at 00:30:46 (the record admitted no plan and listed no setup,
so nothing was asked of the SEC) and persisted `426d3c59` at 00:31:27, and the
publisher that followed it (38986767616) waited for the issuer's two files and
printed *Verified: every one of the 47 public files matches committed main* at
00:32:38 UTC -- three minutes after the record landed, the first time this
file records that interval. The 16 October morning slots were created at
17:26, 17:32, 18:05 and 18:15 UTC (runs 38939668907, 38940441166,
38944618528 and 38945895892; 246.2, 244.2, 225.3 and 227.2 minutes late), the
guard step ran and refused each -- `entry_window_ended` for the 13:20 and 13:28
slots and `inactive_schedule` for the winter pair, which
`tools/publish_morning.schedule_guard()` replayed over the 15 October record at
each creation instant also says -- so every collection step and the persist
job skipped: the morning checks still stand at zero observed. The 16 October `37 9`
source-recovery slot (run 38913623932) was created at 14:10:27 UTC, after the
open, and published nothing; the 17 October `37 7` slot (07:37 UTC) was still
ahead when this was written, and the 16 October publication's next open is
Monday's, so a
Saturday or Sunday slot may publish its receipt.

**The service, read again** (`docs/input-truthfulness/2026-10-17-service-health.md`,
the same `service_health_v3` pinned to `426d3c59`, clock 00:31 UTC on 17
October; the 13 October reading kept as written and no longer re-derived, its
two files held to their git blob identities beside the 12 October reading's
four). 26 expected sessions, 26 published, 26 of 26 first publications before
the next open; none missing, none pending; **fresh: yes** (`main` carries
`7a1a9e49`, the newest due session's); the streak 26 and 26. 19 of 26 first
publications after the retry slot, as 19 were generated after it; from 22
September to 16 October every first publication landed 131.0 to 289.5 minutes
after the primary slot, the four since the 13 October reading at 179.6, 138.4,
131.0 and 133.4 -- 15 and 16 October's the two promptest from 22 September on,
14 October's the fifth (behind 23 and 22 September's), all still after the retry
slot. Latency by the landing commit 55.8 / 264.4 / 410.5
minutes (by the records' clocks 53.1 / 259.7 / 407.2), each commit 2.4 to 5.5
minutes after its record. 31 publications, 22 degraded and 9 ok; 5 read
against their own archived slots and 26 against the current policy's. Reader
272 of 312 requested reads over 31 publications; the first five cost blocks
(12–16 October): 10 calls, 10 replies, 73,439 input and 5,715 output tokens.
Signal 25 RED and 6 YELLOW, 0 reaction tickets, 3 anticipation tickets, each
superseded. Companions: two morning receipts (`inapplicable`), eight issuer
receipts (seven `unavailable`, the newest `no_candidates`), the first three
source-recovery receipts (all `partial`, for 14, 15 and 16 October, each landed
before its applicable open at 13:04, 12:50 and 12:42 UTC), no research
observation. 38 commits set aside, the same 38.

**Measured** (this sandbox, Python 3.11.15): `tests/test_service_health.py`
39 passed (one new: the 13 October report quotes its own frozen reading) after
the 17 October report was written to carry every phrase the report test reads
off the file -- fresh yes or no, pending or none, the slot basis in the plural,
each companion count in words; `tests/test_docs.py` 40/40 with this file's
count line at 4701; `python tools/service_health.py --check` current with the
history walked again (two runs of the tool, into a scratch directory and into
the repository, byte-identical); `git diff --check` clean; gitleaks 8.24.3 from
inside a scratch root holding the eleven changed and new files and the
repository's config: no leaks. The full suite, in the mutation worktree with
its diff hashed equal to this tree's: at the pushed head `abec26a9` 4667 passed
and 34 environment-gated skips in 21 m 36 s, and on the corrected tree below
4667 passed and 34 skips in 20 m 33 s (4701 collected both times; the only edits
after that run are this file's prose, which the suite reads for its count line
alone). CI on `abec26a9`: all seven checks green (Tests run 38996501106 --
pytest 02:50–03:06 UTC, page 02:50–03:05, the gate, the native stress case
02:51–03:10 and central 02:51–03:39; Secret scans 38996501029 and 38996469642).

**Mutation pass**, each mutant in the mutation worktree (its diff hashed equal
to this tree's before and after), judged by the whole
`tests/test_service_health.py`: one byte appended to the frozen 13 October
reading dies in the blob test; the 17 October report's median moved by a tenth
dies in the report test; `OUT_DIR` set back to the 13 October directory dies
in the frozen test and the report test (the committed-reading test alone would
have passed it, the 13 October files being what the tool writes through their
own commit, which is why the report is held to the directory the tool writes);
the issuer counts off by one in words die in the report test; the committed
JSON's median moved dies in `--check` and the report test; the 13 October
report naming no 17 October report dies in the frozen test. Six die; the
control, a word of the report outside every quoted phrase, passes 39.

**The review, worked, and the sentences it caught.** A workflow by execution over
the pushed tip `abec26a9`, three lenses (the words against the record, the
reading against its reports, whether the tests can fail), two skeptics a
finding. Its first launch produced nothing: all three finders hit the session's
usage limit before running a check, and two of their isolation worktrees were
left behind and removed. Re-run, it returned 27 findings, 21 distinct, and both
skeptics upheld every one; each was also reproduced here before it was touched.
Eleven were sentences of this checkpoint that said more than the record:
- the `16 23` cron called the retry slot, its lateness measured from another
  slot (63.9 minutes against 123.9), and -- a skeptic one level deeper, from the
  job log -- its guard never reached the published check;
- "the second live night the tolerance kept green" (9 and 12 October were
  before it) and "the first with no frame past the bound" (8, 9 and 12 October
  had none);
- the follow-up's 20 stocks "at the five sessions each missed" (WBD alone missed
  five);
- WBD leaving the seed at 07:20 UTC (the branch commit; `main`'s seed moved at
  09:37), and its sentence "on 13, 14 and 15 October" (every publication from 7
  October on);
- the morning guard "passed each through" (it ran and refused each);
- a slot "not created at 02:40 UTC" five hours before its own time;
- the record "generated at" its run's start clock;
- 16 of 18 late bars "the provider's placeholder" with two carrying 2,891 and
  237 shares unnamed;
- "the three promptest since 21 September" (14 October is fifth);
- and the full-suite figure promised and absent.
Five were sentences of the reports and the index: the 17 October report's
"first five" cost blocks (four were new), its one refused reply on 13 October
(two), its "every recovered bar so far" a placeholder (50 of 52 -- found here
while checking the receipts, beside the review's late-bar finding), the 13
October report "kept as written" while this pull request edited it, and the
index still saying `--check` holds the 13 October files; and the tool's `OUT_DIR`
comment naming only the 12 October reading. Five were test holes: the
republished-sessions check passed with the list deleted (every date matched
text elsewhere in the report), the superseded notes were held by a filename
alone, and the recovery sentence, the cost-block counts, the four latest
landings, the promptest ranking and the archived-slot span were held by nothing.
Each assertion now builds its phrase from the committed reading or the records
-- the 13 and 15 October refusals and the 52 recovered bars read off git at the
commits the reading names -- and the 12 and 13 October reports are held to
their blobs. Thirteen mutants over the new assertions, each in the mutation
worktree and judged by the report and frozen tests (the only ones that read
the reports), all die in the test that names their rule; the control, a word
of a definition, passes. One of mine found while fixing: GEG's and NCEW's
recovered bars were first written "on 16 October"; they are 15 October bars,
recovered on the 16th, and the test now reads each bar's own session.

**Not claimable:** a morning or research observation; a source-recovery
receipt for the 16 October publication; the 19 October session; any trading
edge.

## Checkpoint, 17 Oct 2026 — PR #178 accepted; the first readable confirmatory figure, and the page sentences it made false

**PR #178, accepted.** Merged as `6ac9153c` on `main` with a merge commit over
`426d3c59`. The head `2768e467` passed all seven checks (Tests run 39002277462:
pytest 04:21–04:49 UTC, page 04:21–04:36, the gate, the native central case
04:22–04:49 and stress 04:22–05:11; Secret scans 39002277439 and 39002274175).
Publisher 39005598815 printed *Verified: every one of the 47 public files
matches committed main* at 05:15:58 UTC; Pages 39005614956 deployed
(39005598233 cancelled as superseded, as every merge does); the merge commit's
own Secret scan 39005598755 passed.

**Revision.** Branch `claude/spicystock-historical-workflow-i53ud1` restarted
from `main` at `6ac9153c`. Nothing under `src/` changed and no rule moved;
`docs/data.json`, `docs/picks.json`, the compact reader, every receipt, the
history, the evidence objects, the quality ledger, the workflows and the
vendored design system are untouched; no run, mail, dispatch, provider call or
credential. `.env.example` was reviewed: nothing here is configuration.

**The re-read** (`docs/input-truthfulness/2026-10-17-signal-outcomes-confirmatory.md`).
The frozen study (`tools/signal_outcomes.py`, blob `39d4f25a`, unchanged since
PR #100) over thirty-one publications under a spec that is the frozen file with
fourteen entries appended (SHA-256 `5598366c9851…`, the byte-level diff
retained), run under Python 3.12.3 and pandas 2.2.3 and again under 3.11.15 and
pandas 3.0.6 to the same bytes. **The confirmatory admitted stratum is readable
for the first time: 209 settled over ten nights, −0.157R a ticket, the mean of
its night means −0.138R with a 95% night-bootstrap interval of −0.431 to
+0.129. The interval includes zero: it establishes no sign.** Three facts the
frozen sentences do not carry, each written into the report: three of the
eleven confirmatory nights were YELLOW (8, 9 and 12 October), so the footer's
"refused by the RED gate" is false of all 104 tickets settled on them: 102
grade A, refused by YELLOW's own A+-only band, and the two A+ of 8 October
refused by the reader (an accepted review lowered MANH to C; reader authority
refused HAE's reply, so the accepted-review requirement withheld its ticket);
the eight RED nights' 105 settled are −0.302R a ticket. The account under the
spec's own rule fell from $10,000 to $2,000 at `e67f8cba`, the second 8 October
publication, a revision, so the first signals ticketed at $2,000 are 9
October's, and the admitted rows the study marks `no_order` rose from 0–6 a
night to between 8 and 59; and the 1 October night,
read whole, moved from −0.364R over 50 settled with no win to −0.087R over 81
with 20 wins, the early-read bias measured on a full night. The exploratory
stratum stays negative, −0.119R over 301, its interval clear of zero. 77 of the
78 confirmatory rows still moving belong to 13 to 16 October; read again after
23 October.

**Two dated readers had to stop reading rolling files.** The 12 October evidence
review read `docs/historical-findings.json`, which this re-read rebuilds: its
findings input is retained under its `inputs/` now (as `c759a1e6` carried it,
SHA-256 `0d806808…`, refused on a changed byte), its study paths pinned to the 6
October run, and its review files regenerated with only their `sources` moved.
And the findings builder copied a night's whole `run.reads` block, which from 7
October (`a8f9a36f`) carries a cause named `credit` that its own credential
guard refuses;
`reads_of()` copies the two counts the page prints and refuses a block without
them.

**The page said things the file does not, once a yellow night existed.** The
Record view's reading list was written when every night was red, and two of its
sentences rendered false over the rebuilt file: the confirmatory line said the
non-red nights were ones on which "the gate published some of their tickets",
and the last line said the same of the nights left out -- the record published
no burst ticket on 8, 9 or 12 October, the tickets the study walks, and three
setting-up tickets (MG and SN on 8 October, ZIM on 9 October), which it does
not. Every check passed, because the checks read each
sentence's first words. The confirmatory line now prints the study's interval
and whether it includes zero, its hold count over every confirmatory night (it
said 4, the reading block's red-night count, where 5 of 11 are inside their
hold), and the red nights' own A-quality figure beside the study's; the last line
names the nights not red by date, says such a night admits some grades, counts
what the gate published on them off the file, and says the confirmatory result
includes them only when one is confirmatory. A readable confirmatory split
without its interval is refused by the shape check. The builder's docstring
claimed the same false thing about yellow nights and is corrected.

**Measured** (this sandbox, Python 3.11.15, Node 22, Chromium through Playwright
1.56.1): 4713 tests collected. **The full suite found what the focused runs had
not:** on the first tree 4678 passed, 34 environment-gated skips and one failed
in 22 m 07 s -- `tests/test_findings_page.py`'s literal guard, which refuses a
number the page types itself. The new sentence said "a 95% night-bootstrap
interval"; the 95 lives only in the study's key name (`ci95`), and neither the
frozen spec nor the findings file carries it as a value. The page says "the
study's night-bootstrap interval" now, the guard is unchanged, and the full
suite on the final tree, run in the mutation worktree at the commit with its
index hashed equal to this one's: 4679 passed and 34
environment-gated skips in 22 m 25 s.
`tests/test_historical_findings.py`, `tests/test_evidence_review.py` and the new
`tests/test_signal_outcomes_reread.py` 46 passed; with `tests/test_findings_page.py`
and `tests/test_docs.py` 94; `python tools/build_historical_findings.py --check`
and `python tools/evidence_review.py --check` current; no record or rule moved,
so the page fixtures and every cascaded generator are untouched; continuity 137;
the `findings` suite 1080/1080 on the final sentence, the screenshots at 1280 and
on the phone looked at (the reading list, the yellow nights in the chart and the
list of nights); gitleaks 8.24.3 over the 21 changed files from inside a scratch
root with the repository's config: no leaks.

**Mutation passes**, the tree never written. The report, through copies read by
the new test: thirteen numbers moved one at a time (a night-table sum, the
interval's bound, the yellow sum, the red mean, the no-order list, the 1 October
wins, a still-moving count, the row total, the uncertain bound, the late
settlers' sum, the hold count, the under-twenty count, the A+ count) all die;
the control (a heading word) survives. The page, through routed copies of
`app-findings.js` (`SCSTOCK_FINDINGS`, a read-only override added to the smoke
beside the other modules'): nine mutants -- the hold back to red nights only,
"includes zero" printed always, the interval dropped, the published count fixed
at zero, the dates dropped, "the confirmatory result includes them" printed
always, the red figure read off the study's, the interval unchecked by the shape
check, and the old false clause put back. Eight died at once. **The old false
clause SURVIVED**, the hole this checkpoint is about: nothing read that clause.
It is checked now and dies. The branch case's yellow confirmatory nights are read
red there, so its two non-red nights are exploratory and the "includes them"
clause has a side that can fail; its green night publishes two tickets, so the
published count can be told from zero. The interval-unchecked mutant first died
by name and then ended the suite, waiting on an alert a half-drawn page never
shows; the alert is read only when present. The control (a comment) passes
1080/1080. Python, in a scratch worktree carrying this diff: seven mutants (the
reads block copied whole, done over requested admitted, a bool admitted, the
findings digest unchecked, the missing findings file read from the rolling one,
the review reading the new study, the findings origin unnamed) all die in the
test naming them; the control (a docstring) survives.

**CI found what the sandbox could not.** The page job on `df0bf3e2` passed
16193 of 16195: at 320 px, dark and light, the bracket's label *exact lookback ·
28 sessions* sat partly outside the chart. Its placement read an estimated glyph
width (`CHAR`, 6.5 px for the 10.5 px mono face): the label starts at the
bracket's left end, or ends at its right end when that would run past the chart.
The rebuilt file has more sessions before the first night, so the bracket moved
left and an end-anchored label had about 7 px to spare here; the runner draws
the face wider. Reproduced here by loading the page with `letter-spacing: .4px`
on the chart's text: the same two checks fail, the rest pass. `bracketPlace()`
now has a third case -- neither end fits, so the label sits inside the chart with
its right end at the edge -- and `draw()` places it again by the length the
browser measures once the chart is on the page (`getComputedTextLength()`, which
jsdom lacks, so the estimate stands there). `tools/findings_cases.mjs` loads the
320 px chart with its letters 0.4 and 0.8 px wider (8 checks; the suite is
1088). The old page, the measured placement dropped and the clamp dropped each
fail both wider-font checks; a control (a comment) passes 1088/1088.

**And CI kept finding the class, because CI draws a different font.** The page
job failed on `0483cf00`, `433e474c` and `a6a77f93` on the 0.8 px case (the lower
panel's name past the chart) and on `0a6e163b` on *320 light* (the bracket's
label 12.2 px past the chart's left edge). The cause, found by a review workflow
and reproduced here with the font files it downloaded: a runner reaches Google
Fonts, so its pages draw IBM Plex Mono, about 7.0 px a glyph at 10.5 px, where
this sandbox, which cannot reach Google, draws the Liberation Mono fallback at
6.3. The chart measured its labels once, at the draw, and nothing measured them
again when the web font arrived; whether a check failed depended on whether the
font beat the replay's draw in that browser context. Served 1.5 s late, the real
font reproduces CI's failures exactly; served at once, nothing is out. The same
review found three more labels still placed by the glyph estimate: the note
before the first night (past its ground and over the first night's mark at
390 px from 0.8 px wider), the pill (its frame sized at 6.4 px a glyph, the text
across it from 0.8 px) and the ±10R ticks (past the chart's left edge on a phone
from 1.2 px, in the strata that reach them).

`fit()` now measures every label the drawing placed by the estimate -- the
bracket's (narrowed to the chart if even its measured length is wider), the panel
names (`panelFit()`, the first wording that ends inside the chart), the note
(`noteFit()`, its ground sized to the measured text, left out where no wording
fits its sessions), the left-axis labels (narrowed to the margin) and the pill
(framed by its measured text) -- after every draw, and again whenever
`document.fonts` fires *loadingdone*, without rebuilding the chart. In jsdom
`draw()` never runs (the chart has no width), so nothing there is fitted. The
suite reads the chart only once the page's fonts have settled; drives the
letters 0.4, 0.8 and 1.2 px wider at 320 and 390, in the default stratum and in
every burst's (whose ±10R ticks are drawn), holding every label, the pill's frame
and the note's ground; widens the letters after the draw and says the fonts have
loaded, with Google's fonts refused so a runner and this sandbox draw the same
face, and holds the labels fitted and the chart not rebuilt; drives 3 px at 320
(the phone wording measured past the chart first, the step-down held on the first
draw, after a stratum change and after a redraw, the bracket narrowed) and at 390
(the note left out); and 700 px, where every burst's desktop name steps to its
middle wording. That page job failed once more, on `c7b0b159`, 16371/16373: at
390 px with the letters 1.2 px wider five pairs of dates touched -- the dates were
the last label the estimate still placed, fine with this sandbox's fallback at
1.2 px and not with CI's font. `datesFit()` now walks the dates the drawing
chose and keeps one only where its measured width clears the one kept before it
and the last date by `DATE_GAP` (4 px), so a wider font drops dates and never
crowds them; the real font at normal spacing keeps every date (4, 6 and 14 at
320, 390 and 1280), and the drawing's count is archived on the chart
(`data-dates-drawn`) so the suite holds that nothing is thinned where nothing
would touch. The real font reproduces CI's 5 touching pairs on `c7b0b159` and
leaves none now. 1263/1263 here, and the real font served late (1.5 s, 320 and
390, 0, 0.8 and 1.2 px) leaves nothing out and no dates touching in every
repeat. Ten mutants through routed
copies: the font listener dropped (5 checks), the note's fit dropped (8) and its
removal dropped (8), the pill unmeasured (10) and its text unnarrowed (2), the
axis labels unnarrowed (4), the bracket uncapped (2), the panels unfitted (11),
the fit on the first draw only (13), a desktop list jumping to its shortest
wording (1) all die on the checks naming them, and `0a6e163b` itself fails 24;
so do four over the dates -- the thinning dropped (2), its gap unchecked (2), the
last date's clearance unchecked (1), the gap at 40 px, which over-thins (5).
A cap on the pill's frame survived as equivalent -- the measured text is already
narrowed to the plot -- and is removed. The control (a comment) passes.

**The review, worked.** A workflow by execution over `df0bf3e2`, three finders
(the numbers, the page, the tests) and one skeptic a finding, returned 17
findings, 13 distinct, and the skeptic upheld every one; each was reproduced
here before it was touched. The high one was the class this checkpoint is about,
one level deeper: the replay counted the burst tickets the record published and
said the gate published none on the yellow nights, while the 8 and 9 October
records published three setting-up tickets (MG and SN, ZIM). The builder counts
each night's setting-up tickets now (`setup_tickets_published`, held in the test
to the watchlist's own orders), and the page prints them beside the burst
tickets and never adds the two. Then sentences, each now asserted from the
study's rows or from the records read off git at the commits the spec names:
the two A+ of 8 October were refused by the reader and not by the band, so the
RED footer is false of all 104 yellow-night tickets and not 102 (the report, the
README and this checkpoint said 102); the account moved at `e67f8cba`, the
second 8 October publication, not the 9 October one; the rows without an order
are the study's `no_order` and fell to 8 on 16 October, not "22–59"; three
nights reach twenty settled, so "no night's mean is a rate" was false; the
pooled −0.069R is the 205 bounded uncertain tickets' +4.27R pooled with the
settled, not the uncertain tickets' own figure; the `credit` cause is in every
`run.reads` from 7 October, not 13; and the last reading line said the
confirmatory result includes every non-red night, which is false of a non-red
night before the freeze (the committed file has none, its three yellow nights
all confirmatory; the branch case has two), so it names the confirmatory ones
by date now. Three were browser holes, and the suite drives each branch now through a
routed copy of the file: every night made red, with the confirmatory split one
short of its minimum (the unreadable sentence and the all-red last line, which
the rebuilt file no longer reaches); an interval wholly under zero, with the red
nights one short of a rate (the "clear of zero" side and the count side of
`oneRate()`); and every confirmatory night made yellow (the guard that drops the
red-night clause). The re-read test also reads the numbers it had let move: the
no-order rows by night, the uncertain bound, the A+ refusals and the account.
The five page mutants the review named -- the unreadable sentence saying the
split is readable, the all-red line saying green, "clear of zero" only above
it, `oneRate()` always a rate, the red-night clause printed with no red night
-- each die through a routed copy on the two checks naming its rule (1158/1160);
the control (a comment) passes 1160/1160. Measured on that tree (`a6a77f93`):
4714 collected, and the full suite, run in the mutation worktree at the commit,
4680 passed and 34 environment-gated skips in 23 m 43 s;
the re-read, findings, findings-page, docs and evidence-review tests 95 passed;
both `--check`s current; continuity 137; gitleaks 8.24.3 over the five files the
round changed: no leaks.

**Keep / fix / defer / omit.** Keep: the spec frozen and extended by appended
publications only; dated readers read retained inputs, never a rolling file.
Fix if it bites: the frozen study's footer and reading rule still say every
ticket was refused by the RED gate, and only a new spec could change them; the
account change mixes two populations in one confirmatory figure, which the report
names and the frozen rule cannot split. Defer: the re-read after 23 October, when
the 16 October tickets reach their fifth session. Omit: any rule, threshold or
account change on these numbers; an edge claim.

**Not claimable:** a morning or research observation; any trading edge.

## Checkpoint, 17 Oct 2026 — PR #179 accepted; the owner's hand-started morning check (#108, #111)

**PR #179, accepted.** Merged as `2156aaca` on `main` with a merge commit over
`6ac9153c`. The head `4b135e3c` passed all seven checks (Tests run 39020763752,
09:20–10:00 UTC; Secret scans 39020763677 and 39020760337). Publisher
39023298699 waited for the two changed files, `historical-findings.json` and
`app-findings.js`, then printed *Verified: every one of the 47 public files
matches committed main* at 10:02:38 UTC; Pages 39023317287 deployed
(39023298199 cancelled as superseded, as every merge does); the merge commit's
own Tests (39023298690) and Secret scan (39023298716) passed.

**Revision.** Branch `claude/spicystock-historical-workflow-i53ud1` restarted
from `main` at `2156aaca`. Nothing under `src/` changed and no rule moved;
`docs/data.json`, `docs/picks.json`, the compact reader, every receipt, the
history, the evidence objects, the quality ledger, the workflows and the
vendored design system are untouched; no run, mail, dispatch, provider call or
credential. `.env.example` was reviewed: the handoff reads no variable.

**Why this.** The morning checks stand at zero observed, and the cause is the
scheduler, not the guard: every scheduled morning run from 12 to 16 October
was created after its entry window had ended (the 13 October schedule reading;
the 16 October runs 225 to 246 minutes late), and each guard refused, as it
should. The reading's recommendation was the owner's own hand-started run of
`morning.yml`, which needs no credential and no host. The page said nothing
about it: not when a run is accepted, not which input publishes, not that a
reader who opened the desk at 8:10 could start one.

**What was built.** The Morning desk's observation summary
(`docs/app-observations.js`, `handoff()` and `offerHandoff()`) offers a link to
this repository's `morning.yml` with the steps -- main, **dry_run** unticked --
and what a run does: it quotes the publication's admitted plans (IEX quotes and
delayed SIP volume) and any research rows the opened comparison names (IEX
quotes), publishes its dated receipts, starts the SEC evidence collection
that follows every morning run (at most three a UTC day, the evening's
included) and places no order. It asks the collector's own questions first: on
the applicable session's market date, from `src/morning.py`'s
`POLICY["preopen_minutes"]` before the open until `START_MINUTES` (2) before the
entry cutoff, because the collector reads its clock after checkout and install,
28.8 and 31.7 seconds after the two measured dispatches were created. It offers
only once the morning file was read and shown to hold no current check for
this publication -- a 404, a receipt bound to another publication (every
morning before a check), an inapplicable one, or one past its five-minute life
-- never while the file is unread, could not be read or cannot be verified. A
no-ticket receipt is final, since nothing it could quote appears without a new
publication, and a publication that admits no plan says a run would quote
nothing for one unless the opened comparison names allocation-fit rows (the
research module's `status().fit`, which repaints the summary when a cohort
attaches). Earlier that day it names when the window opens and offers no link.
A withdrawn link hands the focus to the section's reload control, never the
body behind the open dialog. It is a link and a sentence: the page dispatches
nothing, holds no token and requests nothing from any GitHub host.
`tests/test_workflows.py` holds the link to `app.js`'s `REPO` and the workflow
file, the instruction to the `dry_run` input's default, both collect steps'
`DRY_RUN_FLAG` and the persist job's condition, and the minutes to the
collector's `POLICY`.

**The reload that read nothing.** The same morning run publishes the research
rows' dated observation, and neither button a reader presses re-read it:
**Reload published observations** read `morning.json` alone, and **Reload
published comparison** re-attached an unchanged cohort, which renders from the
kept result without a request -- so an observation published after the page
loaded stayed invisible until a full page reload. The morning reload now
re-reads the research observation too (nothing while the comparison has never
been opened), and the comparison reload asks it again for an unchanged cohort;
a new cohort's re-attach already reads it, so the press adds no second request.
Both go through `refresh()`, which keeps the verified observation until a newer
file validates and names a failed read beside it; `reload()`, a plain read,
stays the module's own.

**Measured: how long a hand-started run takes.** Two earlier dispatches with
`dry_run` off: run 38039598040 (10 October) went from its creation at 08:56:01
UTC to its committed receipt `fa480f2a` in 64 seconds; the run finished at
08:57:10, the Pages deployment that carried it at 08:58:05, and publisher
38039664633 printed *Verified* at 08:58:11, 130 seconds after the run was
created. Run 37964299335 (9 October) committed `2fa9773f` 75 seconds after
creation. Neither asked a market-data provider anything (a Saturday, and after
the cutoff); the 10 October run's completion started the SEC evidence
collection (38039664597), which made one request. So the offer says to press
Reload a minute or two after the run finishes, and that an earlier press reads
the previous files. Neither measures how promptly GitHub creates a dispatched
run, which the listing cannot show.

**The review, worked.** A workflow by execution over `622e07ff` -- three finders
(the page's semantics against the collector, whether the tests can fail, the
prose) and a skeptic a finding -- returned 18 findings and the skeptic upheld
every one, each reproduced. The mediums: the offer was made on a publication
with no admitted plan and an empty cohort, where a run asks no provider
anything, and came back every five minutes once its no-ticket receipt aged;
either reload button dropped a verified research observation when its re-read
failed, where `main` kept it; an unread morning file (a 5xx, no WebCrypto) was
offered as "no current check", pointing at a reload button that was disabled;
the page said a run "publishes one dated receipt" when the persist job commits
two and every morning run starts an SEC collection under its daily cap; and
four test holes -- the workflow test never read the flag that makes an
unticked dispatch publish (inverting it passed all 54), "requested nothing from
GitHub" filtered `github.com` and so could not see a dispatch to
`api.github.com`, nothing observed the unread state (the checkpoint's own
mutant line credited the practice record with it, a different rule), and the
research quiet check counted requests before a read could start. The lows: the
offer ran to the exact cutoff, half a minute after which a dispatched run
starts collecting; "when the run has finished, press Reload" reads the old file
for about a minute; focus fell to the body when the link was withdrawn; the
later-cohort check never identified the cohort; the day-after check could only
fail from the cutoff rule; the reload hint said "is open" where the module
keeps reading once opened; and the README dated the scheduler's change to 21
September when that morning's secret scan was still prompt. Each is fixed and
held by the check it named.

**Checks.** `main`'s three modules (`2156aaca`'s `app-observations.js`,
`app-stop-research.js` and `app-research-observations.js`, routed in) fail 34
of the `observations` suite's 216 checks and 16 of the `research-observations`
suite's 387; the branch passes all of both. Twenty-three mutants through routed
copies, each judged by both suites, all die on the checks naming their rules:
the absent-file rule dropped (2), a no-ticket receipt expiring (1), every
publication worth a run (3), no start allowance (6) or an inclusive one (4),
the pre-open minutes dropped (19), an inapplicable receipt read as current (1),
the session date unchecked (2), an expired receipt read as current (3), the
focus fallback dropped (3) or the link's focus restoration (5), the
other-publication and 404 markers dropped (1, 32), the research fits ignored
(2), the summary not repainted when a cohort attaches (2), fits counted over
every row (1), the morning press reading the morning file only (7) or the
research observation destructively (2), the module's refresh made a plain read
(4) or its kept observation lost (4), and the comparison press not asking
again (4), asking destructively (4) or without its new-cohort guard (2: a
second request); the control, a comment, passes both. The first pass found one
hole of the first shape this file names: the unread-file rule died only on the
no-WebCrypto case, because the 503 case ran in a tab whose kept fresh receipt
suppressed the offer anyway; it runs from a fresh tab now and dies there too.
Inverting both collect steps' `DRY_RUN_FLAG` in a copy of `morning.yml` fails
the workflow test; an unmodified copy passes. On the final tree (`a87b8ddd`):
4715 collected, the full suite 4681 passed and 34 environment-gated skips in
25 m 00 s (and in 25 m 19 s at `622e07ff`); the full smoke with `--shots`
16467/16467; continuity 137; the chart check 378/378 (no chart module
changed); gitleaks 8.24.3 over the changed files: no leaks. The handoff at 1280
dark and 390 light was looked at, its longer sentence read at 390.

**Keep / fix / defer / omit.** Keep: the page links and explains; the owner
dispatches; a pressed reload never loses what it verified. Fix if it bites:
over the offer the summary's heading still reads *Morning observations
unavailable* when the file is absent or bound to an older publication -- the
file's own status, and true, but not the action; and the issuer guard admits a
morning parent whatever its receipt's status, so a too-early or too-late
hand-started run still spends one of the day's three SEC collections. Defer: a
scheduled routine that dispatches the run (the reading's next step), which
holds a token or a person's clock outside this repository and is Mo's call;
#111's ten consecutive sessions with a morning check, which now depend on
someone starting a run by 8:58 AM CT. Omit: a dispatch from the page, which
would need a credential in the browser.

**Not claimable:** a morning or research observation; any trading edge.

## Checkpoint, 17 Oct 2026 — PR #180 accepted; the stale stocks read again across nights; the owner's four answers

**PR #180, accepted.** Merged as `f714fb32` on `main` with a merge commit over
`3567f698` (the 17 October recovery receipt, over #179's `2156aaca`). The final
head `2967d3d5` passed all seven checks on Tests run 39033134847 (pytest
12:35–12:56 UTC, page 12:35–12:52, the gate, the native central case
12:35–13:02 and stress 12:35–13:25) and the Secret scans. Publisher
39036539250 waited for `app-observations.js`, `app-research-observations.js` and
`app-stop-research.js` and printed *Verified: every one of the 47 public files
matches committed main* at 13:27:22 UTC.

**The 17 October recovery receipt, read.** The `37 7` source-recovery slot's
run published `3567f698` at 11:44 UTC, 4 h 7 min after the slot: the 16
October publication's 18 stale stocks asked for again in one call to the bars
endpoint, all 18 now carrying a 16 October bar that passes the session rules,
all 18 at zero volume, status `recovered`; the publication unchanged.

**The owner's four answers (17 October 2026).** Asked which things only the
owner could unblock, Mo answered:
- **Morning check delivery: automated, from Claude.** A claude.ai scheduled
  task (`trig_01SVeMxasSA4sUuuQXPxjnSu`, *SpicyStock morning check (8:21 CT)*,
  `CRON_TZ=America/Chicago 21 8 * * 1-5`, first firing Monday 19 October 13:21
  UTC) fires into one persistent session whose only job is one
  `workflow_dispatch` of `morning.yml` on `main` with `dry_run` false. A
  fresh session per firing came up without the GitHub tools, so the session
  persists; its checkout is the orphan branch `morning-dispatcher` (`930aea9a`,
  a README only) and it runs a smaller model, which took a test firing from
  about $2.40 over the full repository to under a cent. 8:21 CT is inside the
  collector's window (from `POLICY["preopen_minutes"]`, 30, before the 8:30
  open to `START_MINUTES` before the 9:00 cutoff). Two test dispatches on
  Saturday 17 October (runs 39045039134 and 39045240320, 15:26 and 15:29
  UTC) ran with `dry_run` true: the collector read `wrong_session`, made zero
  requests, the persist job skipped and nothing was committed; each completion
  started an issuer-evidence run whose guard skipped collection. Not claimable
  until it fires: that the routine starts on time and the dispatched run
  reaches its window.
- **The SEC contact: the owner's chosen email.** `src/issuer_evidence.USER_AGENT`
  names the project and that address, as SEC's fair-access policy asks; the
  five collections from 10 to 16 October that recorded a status answered HTTP
  403 at the ticker mapping (two earlier ones recorded no status; the 17 October
  one asked nothing: `no_candidates`). `tests/test_issuer_http_diagnostics.py`
  holds the header to a sender and an address. Not claimable: that SEC now
  answers; the next collection with a candidate is the test.
- **The broker: Fidelity.** The goal paragraph above still says unspecified;
  the broker-specific first-trade steps are the next pull request but one.
- **The reader rule: tolerate one refused review of two.** At two reads a
  quarter floors to a limit of zero, so one refusal degrades the night (13 and
  15 October). The owner chose to tolerate one; it is the next pull request.

**Revision.** Branch `claude/spicystock-historical-workflow-i53ud1` restarted
from `main` at `f714fb32`, pushed as **PR #181**. Nothing under `src/` moved but
the SEC header; no rule moved, so the page fixtures and every cascaded
generator are untouched; `docs/data.json`, `docs/picks.json`, the compact
reader, every receipt, the history, the evidence objects, the quality ledger,
the workflows and the vendored design system are untouched; no run, mail or
provider call beyond the two dry-run dispatches above.

**The reading.** `tools/stale_inputs.py` (`stale_inputs_v1`) asks what became
of the stocks a publication could not measure. Each session's newest
publication names its stale stock-sessions -- every session a named stock
missed, as `followup.missed_sessions()` counts them at the record's own
`sessions_max`; a first-version record names each stock at its own session --
and the reading joins them to every later follow-up reading and every
source-recovery receipt's row (a rehearsal receipt never), then puts each in
the first class that holds: a follow-up match; the last follow-up reading that
gave a verdict (`no_match`, scanned and not listed; `price_excluded`, under the
$3 policy), whatever later readings said; a later bar read only for its
volume, under or at or above `scans.MIN_VOLUME`; a bar that arrived with its
volume unread; no later bar. `--check` holds its two files to the commits they
name. Through `f714fb32` (7 to 16 October, 8 nights, 31 publications read, 38
commits set aside, 4 receipts): 103 stock-sessions over 58 stocks -- 64 scanned
and not listed, 11 under the price policy, 20 read only for their volume (18
the 16 October night's), 0 arrived unread, 8 with no later bar (every one WBD);
no follow-up reading a match over 127; 93 of the 95 later bars at zero volume,
the largest 2,891 shares. 54 of the 64 scanned come from nights the tolerance
did not tolerate; of the tolerated nights only 12 October's 10 were scanned.
It supports the premise over the 64 and says nothing of the setting-up scans
for the 20, nor of a night to come; it establishes no cause.

**The review, worked.** A workflow by execution over the first pushed tip returned
fifteen findings, each reproduced here before it was touched. The rule: a later
reading with no verdict -- a re-run that no longer selected the stock, writing
`not_selected` -- undid a scan, so the verdict is the last reading that gave one
now; a late bar whose volume neither source could read sat under *no later
bar*, and has its own class; a night over the names bound (`names` None) was
refused, and stands as its session's newest with its stale stocks counted
unnamed; the benchmark named beside the stocks was read as a stock. The report
said more than the reading: it called the premise supported on the nights the
tolerance relied on when 54 of the 64 scanned stock-sessions came from nights it
did not tolerate (only 12 October's 10 are from a tolerated night), and it said
what Monday's follow-up would read; both are scoped now. The tests: the report
test read four columns of one table and two phrases, so a substituted number
passed it; every number the report and the index print is built in the test
from the committed reading or the records read off git at the commits it names,
and nineteen substitutions each fail it while a heading change passes. The
shallow rebuild accepted a set-aside its commits do not produce, and refuses it
now; the walked rebuild refuses a dropped publication commit and an extra
set-aside. README said the follow-up "ran the evening's scans on the late bar"
(only on one that arrived, is selected and passes the $3 policy) and "under or
at the floor". None of the rule fixes moves a class of the committed reading.

**Measured.** (this sandbox, Python 3.11.15): 4756 tests collected; the full
suite at `de7cff55` 4722 passed and 34 environment-gated skips in 23 m 56 s;
after it one commit (`072e052c`) changed `sentence()` and one test, and
`tests/test_stale_inputs.py`, `tests/test_docs.py` and
`tests/test_issuer_http_diagnostics.py` pass 151 on it; `python
tools/stale_inputs.py --check` current with the history walked again; gitleaks
8.24.3 over the eleven changed files with the repository's config: no leaks. No
record, rule or page file moved, so the fixtures, the chart check and the smoke
are CI's, recorded on the PR.

**Mutation passes.** Over the rules the review changed, in the mutation worktree
at `de7cff55`, each judged by the whole `tests/test_stale_inputs.py` with the
committed-file comparison deselected: the verdict read off the first reading or
off the last whatever it said, `not_selected` counted a verdict, an unread bar
put under *no later bar*, the floor made strict, the benchmark kept, the
unnamed count dropped, the produced-set-aside check dropped, a stock-session
counted under its first night only, a rehearsal receipt read, an older
publication of a session naming its stocks, the unread clause and the
read-suffix rule of the sentence each broken -- all die in the test naming
their rule. **One survived, a hole**: the sentence's unnamed clause, which no
test said, and which an empty reading could not say at all (it returned
before the clause). Both are said and held in `072e052c`, where the mutant and
its empty-reading twin die; the controls (a docstring, a comment) survive.
Two passes over the first tip (`236be66d`) had closed four holes before the
review.

**Keep / fix / defer / omit.** Keep: the reading reads git and decides
nothing; a new reading is a new dated directory. Fix if it bites: the 16
October night's 18 are read only for their volume until a follow-up scans them;
the reading's classes rest on the follow-up's selection, so a stock a run no
longer selects is never scanned. Defer: the reader rule (next), the Fidelity
steps, #111's ten-session acceptance from Monday's first dispatched check.
Omit: any change to the tolerance on these numbers.

**Not claimable:** a morning or research observation; that SEC answers the
named contact; any trading edge.

## Checkpoint, 17 Oct 2026 — PR #181 accepted; one refused review of two is tolerated (the owner's rule)

**PR #181, accepted.** Merged as `97dbf7bd` on `main` with a merge commit over
`f714fb32`. The head `a46707ac` passed all seven checks on Tests run
39048460273 (pytest 16:13–16:41 UTC, page 16:13–16:29, the gate, the native
central case 16:13–16:59 and stress 16:13–17:04) and Secret scans 39048460277
and 39048455759. Publisher 39052334531 printed *Verified: every one of the 47
public files matches committed main* at 17:07:22 UTC; Pages 39052354549
deployed; the merge commit's own Secret scan 39052334520 passed. **The pytest
job took 28 of its 30 minutes** on that head, so this pull request raises its
cap to 45 (`tests.yml`, a cap stops a hang and does not bound a suite); no
suite, check or lane changed.

**Revision.** Branch `claude/spicystock-historical-workflow-i53ud1` restarted
from `main` at `97dbf7bd`. The owner's fourth answer of 17 October: tolerate
one refused review when a night has two reads. `docs/data.json`,
`docs/picks.json`, the compact reader, every receipt, the history, the evidence
objects, the quality ledger, the workflows other than the pytest cap and the
vendored design system are untouched; no run, mail, dispatch, provider call or
credential.

**What the rule was.** `reader_coverage.reads()` tolerates refused replies --
names reader authority refused, not a format, account, credit or transport
failure -- while every other read was accepted, no refused name is one the
regime would have planned, and the refusals are within a limit: the night's
reads times `READER_REFUSAL_FRACTION` (a quarter), floored. Under bounded review
selection (#121) a RED or no-feasible night asks for two research reads, and a
quarter of two floors to zero, so one refused reply of two degraded the night:
15 October (JAKK refused, ROKU accepted, under RED) read `partial` and
`claude_partial`.

**The rule.** `pipeline.READER_REFUSAL_MIN = 1` (P, archived as
`pipeline.reader_refusal_min`, so `rules_version` moves): the limit is the
fraction's floor or the minimum, whichever is greater, and never every read
(`_limit()`: `max(floor(n × f), min(m, n − 1))`), since a night with no accepted
read is `unavailable` whatever refused it. Every other condition stands. The
floor reaches the night through `read_charts_and_grade()` and the empty-night
default in `run_evening()`. `reads_faults()` holds a record's limit to the
fraction AND the floor it archived; an archived floor that is not a
non-negative whole number (a bool among them) is a fault by name, and a record
made before the rule archives no floor and is read under the fraction alone.
The page reads the limit the same way (`refusalLimit()`), reconciles the
Morning desk's selected batch only where its own limit is the run's, and
Method says "once they number more than both 25% of the night's reads and 1"
under a record that archived the floor, "past 25% of the night's reads" under
one that did not, and quotes no refusal rule over a floor it cannot read.
README, `.env.example` and `knowledge/method.md` say the same. The rules digest
moved, so the 13 page fixtures and every cascaded generator were regenerated
through their own producers (issuer-evidence, stop-research, research-outcomes,
research-observations, source-recovery, cash-preview, the first-trade backup and
its parity corpus; morning pinned, unchanged) and `tools/recovery_rehearsal.py`'s
evidence with them, each publication identity carrying the digest.

**Projected over the record** (the new `_limit()` and `_verdict()` over each
retained publication's own `run.reads`, read off git): all 36 schema-2
publications carry a reads block, 11 of them (7 October on) the refusal limit
#104 added, which the floor reads; one verdict moves -- 15 October's, `partial` to `tolerated` -- and
that night stays degraded on coverage (WBD past the five-session bound). 13
October stays `unavailable` (both reads refused); every twelve-read night keeps
its limit of three.

**Measured** (this sandbox, Python 3.11.15, Node 22, Chromium through Playwright
1.56.1): 4774 tests collected; the full suite at `cd64070d` (the rule, before
two test-only commits) 4738 passed, 34 environment-gated skips and the one
failure the suite-count line this checkpoint moves, in 24 m 25 s;
`tests/test_docs.py`, `tests/test_workflows.py` and
`tests/test_reader_coverage.py` 186 passed on the final tree; every page fixture and cascaded generator current, their
`--check`s run last, beside `tools/recovery_rehearsal.py`, `service_health.py`,
`stale_inputs.py`, `evidence_review.py`, `build_historical_findings.py` and
`freeze_validation_cases.py` (`--check` each, current); the `inputs` suite
293/293; the full smoke with `--shots` 16488/16488 in its two lanes, 20 m 58 s.
The Method sentence at 390 px dark was looked at. CI on the pushed head is
recorded on the PR.

**Mutation passes.** Python, each mutant in a spare worktree judged by the
whole `tests/test_reader_coverage.py` and `tests/test_report.py`: the floor
dropped, the every-read cap dropped, the validator ignoring the archived floor,
the floor's count check dropped, the rules not archiving it, the floor at two,
and the pipeline passing zero -- six died on the first pass, and **the last
SURVIVED**: no test drove the evening's own read of its charts with two reads,
so `read_charts_and_grade()` could pass any floor. A test drives it now (two A+
bursts read, one refused: tolerated with a limit of one, no problem) and the
mutant dies; the control (a docstring word) survives both passes. Page, through
routed copies of `app.js` judged by `--only inputs`: the page's limit ignoring
the floor, Method always saying "past", the floor's shape check dropped, Method
quoting a floor of one whatever was archived, and the every-read cap dropped.
Two died on the first pass and **three SURVIVED**, the second shape this file
names: nothing in the suite read the Morning desk's reconciliation, the one
consumer of the page's limit. The suite now reads the desk's review state on
the thin night (reconciled at every width and theme), under another archived
rule (reconciled: half of two reads floors to one and a floor of two is capped
under every read) and under a floor that is not a number (unknown, and no
refusal rule quoted); all five die and the control (a comment) passes 293/293.

**The review, worked.** A workflow by execution over `13a8883c`, three finders
(the Python rule, the page, the documents), returned nine findings. The page's
verifiers upheld three and judged one not a defect; the Python verifiers never
finished, and a finding no verifier judged is not refuted, so each was
reproduced here by execution before it was touched. The page held the core case
nowhere: no variant had one of two selected reads refused, the night the floor
exists for (15 October). `a tolerated refusal of two` now drives it, TSLA's
reply refused by reader authority beside an accepted read, and holds the
Morning desk reconciled, its sentence *1 of 2 chart reviews accepted; 1 without
an accepted review (1 refused)* with *within the archived tolerance*, and
Method printing the run's own tolerated sentence verbatim. The malformed floor
was tested with a bool alone; a floor of -1 and of 1.5 are variants now, each
leaving the desk `unknown` and Method quoting no refusal rule.
`knowledge/method.md` said a refusal is tolerated on any night; it says "with
every other read accepted (at least one)". The Python side: the validator's
re-derivation of a record's limit under its archived floor had no test (an open
night re-derives its reads from the bursts under the floor now, and dropping
`refusal_min` from that re-derivation fails it alone, 1 failed and 92 passed);
`READER_REFUSAL_MIN`'s comment said 13 October was one refusal of two when it
was both (it names 15 October now, and 13 October as the night with none
accepted); `test_review_selection.py` still asserted the fraction-only verdict
(it asserts a limit of 1 and `tolerated` under the floor, 0 and `partial` under
the fraction alone); the 1-of-2 test never read its `problems` (it does); and
`_limit()`'s docstring read as if the floor could exceed the reads. Recorded,
not fixed: Python's `type(...) is int` refuses an archived floor of `1.0` that
the page reconciles, and accepts `2**60`, which the page reads as unknown;
neither is a record the run writes. Page mutants through routed copies, judged
by `--only inputs`: the desk's verdict on the fraction's floor alone fails the
two tolerated-desk checks (304/306); Method's floor check without its `>= 0`
fails the negative floor (305/306); the desk's floor check as `typeof ===
'number'` fails the fractional floor (305/306; -1 is refused there by the
limit's equality anyway); the control (a comment) passes 306/306. Measured on
this tree: 4775 collected; the `inputs` suite 306/306;
`tests/test_reader_coverage.py`, `tests/test_review_selection.py`,
`tests/test_docs.py` and `tests/test_report.py` 292 passed.

**Keep / fix / defer / omit.** Keep: a refusal is tolerated only beside an
accepted read and never on a name the regime would plan. Fix if it bites: at
twelve reads the floor changes nothing; a night of three reads tolerates one.
Defer: the Fidelity steps (next). Omit: tolerating format, account, credit or
transport failures under this rule.

**Not claimable:** a live night under the floor (the first night with two
reads and one refused); a morning or research observation; any trading edge.

## Checkpoint, 17 Oct 2026 — PR #182 accepted; Fidelity's part-fill rule and SpicyStock's advice beside every order the page and the mail print (#110)

**PR #182, accepted.** Merged as `b9196b14` on `main` with a merge commit over
`97dbf7bd`. Publisher 39061392038 printed *Verified: every one of the 47
public files matches committed main* at 19:12:46 UTC; Pages 39061414396
deployed; the merge commit's own Secret scan 39061392064 and Tests run
39061392015 (19:11–19:39 UTC) passed. The first night under the refusal floor
is still ahead.

**Revision.** Branch `claude/spicystock-historical-workflow-i53ud1` restarted
from `main` at `b9196b14`, pushed as **PR #183**. The owner's third answer of
17 October: the broker is Fidelity. Nothing under `docs/data.json`,
`docs/picks.json`, the compact reader, the receipts, the history, the evidence
objects, the quality ledger, the workflows or the vendored design system moves,
and no rule moves (`src/plan.py` changes a comment), so `rules_version` and
every fixture stand; no run, mail, dispatch, provider call or credential.

**What the ticket did not say.** A ticket is a day buy stop-limit with a
one-triggers-the-other sell stop riding on it. Its terms, its entry instruction
and its dated schedule -- which provenance replays and which name no broker --
say the stop "is attached the moment the buy fills" and "is live from the
fill". Fidelity's conditional-trading help says the secondary order is released
only when the primary executes in full, and that "a partial fill of your
primary order will not release your secondary order" (the excerpt, read off a
search result; fidelity.com does not resolve from this sandbox). So on a part
fill the shares that filled have no stop at all until the rest fills, and
nothing SpicyStock printed said so.

**What was built.** `knowledge/broker-fidelity.md`, dated 17 October, maps a
ticket field by field onto Fidelity's order entry (the field names labelled
unconfirmed; the conditional ticket's Trade Type drop-down named from a dated
excerpt) and labels every fact as Fidelity's words or a regulator's words with
the numbered source it was read from (21 sources, each a search-result excerpt;
the T+1 fact cited to the SEC staff's investor bulletin, the press release seen
as a link only), inferred, unconfirmed, or SpicyStock's advice. Its unconfirmed list is what to
check in Fidelity's own ticket before the first order: that the web and mobile
tickets offer a Stop Limit with an OTO secondary and where; that an OTO takes a
Day buy beside a Good 'til Canceled sell stop -- the sources read disagree, and
item 6 says what to do if it does not (never a Day stop, never a GTC buy; the
buy alone, then a separate stop for the shares that filled); the price Fidelity
compares a buy stop against before the open -- a burst ticket's buy stop IS
its last close, so if Fidelity compares against the close every burst ticket is
refused as written, with no fallback; that a 10:00 AM ET expiration (9:00 AM
CT, the end of the entry window) can be set on an OTO primary; that a sell stop
on shares bought the same day is accepted. One text, `report.BROKER_PART_FILL`,
held equal to the page's two copies by `tests/test_docs.py`, labels the two
apart: *Fidelity’s rule: an OTO’s sell stop is released only when the buy fills
in full. SpicyStock’s advice: wherever a ticket, a plan or its dated schedule
says the sell stop is attached at or live from the fill, that assumes a full
fill; if the buy fills only in part, place a separate Sell Stop Loss, Good ’til
Canceled, at the stop for the shares that filled, confirm Fidelity accepts it
on shares bought that day, and check that no second sell stop remains for
shares you do not hold.* The page prints it through one helper,
`partFillNote()`, at each of its ten places, beside the order and never inside
its terms or a copied order: the order block, a recorded ticket, the Burst's
action card above its **Copy order**, the setting-up action bar after its order
line, the comparison under its facts, the tickets sheet, a ticket's decision
summary under its entry (a setting-up stock's only while its action bar does
not offer the order), the model exits under a ticket's dated schedule, a
saved setup's archived order and an archived original's status; the private
handoff prints it in its readback, and the mail once after its burst orders and
once after its alerts, by the same rule the card and the row print an order by
(`_trade_order()`, `_alert_order()`). A pick card's summary never falls back to
a ticket's order line. Before and during the window, the next action says the
sell stop is part of the order (OTO) and that Fidelity releases it only when
the buy fills in full, where it said to attach the stop after a fill. `PRODUCT_GOAL.md`'s 9 October "broker
confirmation remains outstanding" is marked closed.

**Two reviews by execution, every upheld finding reproduced before it was
touched.** The first, over `a8c5c1e7`, returned 23. The note said things its
sources do not (that Fidelity will not cancel a day order at 9:00 CT, when its
own source offers a 10:00 AM ET expiration; an anticipation trigger at the top
of its box, when it sits a cushion above; an extended-hours parenthetical no
excerpt carries; one sentence called "Fidelity's own rule" when the second half
is SpicyStock's); the action bar, the Burst card's **Copy order** and the
comparison printed an order with no note; the next action told the reader to
attach a stop after a fill beside an OTO ticket; and no test held a copied
order free of the note or the note's placement beyond two surfaces. The
second, over `88278545`, returned 30 over three lenses (wording, placement,
tests), a skeptic each: 24 upheld, one not, and five never judged -- the disk
filled under the review's own worktrees and five skeptics died. A skeptic that
died is not a refutation, so all five are treated as upheld: each is fixed, and
the mutant each describes dies under the new check (below). The note still sat beside the record's words "live from the fill"
without naming them (the advice names them now, and the record's own words,
which provenance replays, are unchanged); four surfaces printed an order with
no note (the decision summary, the model exits, a saved setup and an archived
original, the last reproduced on the committed 9 October ZIM original);
the knowledge note dropped the time-in-force disagreement its own research had
flagged, cited a fee to a page that did not carry it, invented a "funds on
hand" parenthetical, called a deposit fact unconfirmed that Fidelity's words
give, cited a press-release URL it never read, and gave the tickets sheet a
copy button it does not have. Its test findings were the shapes this file
names: the page's "beside" was a count, so a note inside the ticket's terms or
under the controls passed; "shown" read `display` and so called a
screen-reader-only box shown; the mail's visibility test read three words of
the note's own style, so a hidden wrapper passed; two rows' notes were held by
a count, so a note after the first passed; the next action was a keyword
denylist. `notePlaces()` names each note by where it sits relative to the
element that prints its order, and what a sighted reader gets (seen, collapsed
inside a closed disclosure, or unseen); the mail's test walks every ancestor of
the note's text. Not upheld: the Morning desk's cash preview, which prints a
personal quantity and no order.

**A third round re-ran the second's 30 findings against `fe8afb14`** -- 23
fixed, 6 partly fixed, 1 not a defect -- and three finders returned 15 new
ones, 13 upheld by both skeptics and 2 by one each; every one was reproduced
here before it was touched. A setting-up ticket printed the 75-word note twice
on one desktop screen, in the decision summary's entry and after the action
bar's order line: the entry gives its note up while the bar, on the same
screen, offers the order, and `reclockDetail()` repaints the summary, so when
the window ends under an open tab the note returns to the entry (held by a
left-open check across the deadline). The note inherited the answer's and the
action bar's text colour where its paragraph's own rule lost to theirs
(`p.sc-hint.ss-order__broker` keeps the hint's colour everywhere). Inside the
window the next action still said the exit terms apply after a fill; it says
the sell stop is part of the order (OTO) and that Fidelity releases it only
when the buy fills in full, before and during the window alike. The Method
walkthrough had put Fidelity's full-fill release into Bonde's own words; it
carries the record's words again. The knowledge note said the tickets sheet
lists every offered ticket (it lists burst tickets; a setting-up ticket is on
its own stock's plan and bar), pinned the conditional ticket's Trade Type to
one page when the excerpt summarises about ten, cited one page for both sides
of the time-in-force disagreement (item 6 is unconfirmed now, both summaries
named by the links they cover), and carried facts under no label of its four
(*a regulator's words* is the fifth). The tests: the dropped-summary chooser
check ran at 1280, where the chooser never opens (it reads a 390 page now);
*seen* passed a note in transparent text, off the page or clipped by an
ancestor (each is unseen now); the mail's denylist of hiding styles missed a
real wrapper (the test walks the mail's tree and holds the note to the column
that holds *Next-session orders*, the allocation line's own style and the order
block before it); the no-note arms of the exits and the saved setup were never
reached (a fixture ticket without an entry step and the withheld TSLA saved
reach them); the archived TSLA's no-order check was vacuous and the clipboard
waits never waited; and `tests/test_docs.py` counted calls inside comments (it
strips the page's comments first, keeping strings, templates and regular
expressions, with a test of its own). Recorded, not fixed: the exits note sits
after the dated timeline rather than under day 1 (one skeptic each way; the
timeline is one block); `plan.NOTE_ATTACH_STOP`, an account note every record
archives, still says to plan a protective order as soon as the buy fills (one
skeptic each way; changing it changes what new records say about every broker);
and a plan without a ticket still prints the record's "live from the fill" with
no note, because it offers no order.

**Measured** (this sandbox, Python 3.11.15, Node 22, Chromium through Playwright
1.56.1, on the code head `2726830e`): 4787 tests collected, the full suite 4753 passed
and 34 environment-gated skips in 22 m 03 s (in a spare worktree at the commit);
the full smoke with `--shots` 16740/16740 in its two lanes;
continuity 137; the chart check 378/378; 13 page fixtures and every cascaded
generator current (morning 21, issuer-evidence 30, stop-research 22,
research-outcomes 40, research-observations 24, source-recovery 20), the parity
corpus current (109 cases, 32 accepted by the page) and the 5 frozen validation
copies current, though no record or rule moved; gitleaks 8.24.3 over the
branch's 11 commits with the repository's config: no leaks. The setting-up
stock's action bar and decision summary, and a burst's, at 1280 and 390 in both
themes, were looked at: one note per screen, in the hint's colour. CI on
`47ef12db` passed the page job and failed pytest on the count line alone (4786
against 4787), which `2726830e` moves.

**Mutation passes**, the tree never written: page mutants through routed copies
of `app.js`, `app-handoff-ui.js` or `index.html`, judged by the suites that
visit their placement; mail and docs-test mutants in a spare worktree, judged by
the whole `tests/test_report.py` and `tests/test_docs.py`. Round 2: seventeen
page mutants (the need, exits, saved and original notes dropped; a pick card's
summary falling back to the order line; the card's note under its controls; the
note inside the terms; the bar's note when the bar offers nothing; the
comparison's and the sheet's notes above their tables; the recorded ticket's
note screen-reader-only; the need and exits notes on every status; the next
action asking for a second stop; the handoff's note screen-reader-only, after
its readback or in its copy) and ten mail mutants (the trades' and the alerts'
note after the first row; the note in a hidden wrapper, at zero opacity, in
white text or at zero size; the trades' note after the open plans; the card's
order read raw; an alert's order read as `or`; the advice's old wording): all
die, each control green. Round 3: nineteen page mutants -- the coil's
deduplication dropped and forced; the decision summary not repainted on the
clock; the note transparent, off the page and clipped; the in-window and
pre-window wording put back; the bar's note after the follow row; an original's
note on every status and an order shape in its status sentence; the exits note
on every ticket; the saved note on every status; the need note without the
order-line fallback; the chooser printing the order line; the handoff's copy
rewriting the clipboard with the note 400 ms later; the readback's note
transparent and off the page; the colour rule overridden by the old selectors
-- and eight mail and docs-test mutants (the note in a plain wrapper, after the
allocation line, at the mail's end and before the alert rows; a `<pre>` printed
for a blank order; the note in a style of its own; a real `partFillNote()` call
in `app.js` commented out, by line and by block). **Two survived the first
pass, each a hole.** The archived original's no-order check was case-sensitive,
so a status sentence carrying "Stop-limit order." passed it (`/i` now). And a
copy that wrote the readback and then, 400 ms later, the readback with the rule
passed the copy check, which had already read the first write: the handoff suite
now records every text the page writes to the clipboard, across the reload, and
holds them all, after the report, the reload and the deletion, to one readback
without the rule. Both die. The controls (an `app.js` comment, an `index.html`
comment, a `report.py` docstring) survive; the docstring control first failed
`test_claude_md_counts_the_suite` alone, because the count line still read 4786
at `47ef12db`, and survives at 4787.


**Keep / fix / defer / omit.** Keep: Fidelity's words, SpicyStock's advice and
the unconfirmed list kept apart; the record's own terms broker-neutral. Fix if
it bites: the knowledge note is read off search excerpts, and a fact confirmed
in Fidelity's own ticket belongs in a dated revision. Defer: the first trade,
which is Mo's, and the unconfirmed list with it. Omit: a broker connection, an
order SpicyStock places, a plain-limit fallback for a refused buy stop.

**Not claimable:** that Fidelity's ticket behaves as its help pages say; a
first trade; any trading edge.

## Checkpoint, 18 Oct 2026 — PR #183 accepted; SEC answers the named contact from a runner

**PR #183, accepted.** Merged as `169557c1` on `main` with a merge commit over
`b9196b14`. The head `50cce5d7` passed pytest, page, the gate's docs-only
decision and both gitleaks runs; the native central and stress cases passed on
the code head `2726830e`. Publisher 39094690154 waited for `app.css`,
`app-handoff-ui.js` and `app.js` and printed *Verified: every one of the 47
public files matches committed main* at 03:45:55 UTC on 18 October; Pages
39094704703 deployed (39094690122 cancelled as superseded, as every merge
does); the merge commit's own Secret scan 39094690128 passed and its Tests run
is on the PR below.

**Revision.** Branch `claude/spicystock-historical-workflow-i53ud1` restarted
from `main` at `169557c1`, pushed as **PR #184**. One tool is new
(`tools/probe_sec_access.py`), `issuer-evidence.yml` gains one dispatch input
and two steps, the tests, README and this file are swept. Nothing under `src/`
changed and no rule moved; `docs/data.json`, `docs/picks.json`, every receipt,
the history and the vendored design system are untouched. `.env.example` was
reviewed: the probe reads no variable.

**Monday's first dispatched morning check, pre-flighted offline.** Over the
16 October record on `main` at the dispatcher's instant (13:21:40 UTC on
19 October), `tools/publish_morning.schedule_guard()` admits a dispatch
(`manual_dispatch`), the record admits no plan (RED), and `src/morning.collect()`
with the halt fetcher stubbed writes a valid `no_tickets` receipt, phase
`upcoming`, both feeds `not_requested`; the research cohort holds no
allocation-fit row, so the research observation will say so. Nothing a
provider answers can change that: Monday's check is a check that runs and
quotes nothing.

**Why a probe.** The issuer collector asks SEC only for a night's candidates
(admitted plans and known-event exclusions); a RED night has none and writes
`no_candidates` without a request, so no night since the owner named the SEC
contact on 17 October could show whether SEC answers it, and every collection
from 10 to 16 October that recorded a status got HTTP 403 at the ticker
mapping. `tools/probe_sec_access.py` asks twice -- the mapping, then a fixed
issuer's submissions (AAPL) -- through the collector's own `_Transport` with no
cache (its User-Agent, spacing, deadline, refused redirects and size bounds),
and writes each request's outcome, status, bytes and digest, whether the
identity was established and the submissions parsed, and whether the
User-Agent names a sender and a contact, never the address (a payload carrying
the header or any address is refused); it prints the result to the job log,
which this sandbox can read where it cannot read an artifact blob, writes
nothing under `docs/`, never replaces a file and never logs a raw exception.
`issuer-evidence.yml` runs it on a dispatch with `dry_run` and `probe_sec`
ticked, in place of the rehearsal collection, keeps it as a 14-day artifact
and never persists it.

**The runner's answer.** Dispatched once on the branch, run 39095391329 (job
117580649908, Python 3.12.15) at 03:57:30–31 UTC on 18 October: the mapping
523,925 bytes (`d04923d6…`) and AAPL's submissions 163,690 bytes (`aad00f6a…`),
both `ok`, the identity verified (CIK 320193), 17 filings in the 365-day window
and one history file advertised. The refusal recorded through 16 October is
not what SEC gives the named contact. The sandbox's own run of the probe says
`network_error` -- the proxy refuses sec.gov here -- which is why the answer
had to come from a runner. Not shown: a collection with candidates succeeding,
or anything of news or earnings coverage.

**Measured** (this sandbox, Python 3.11.15): 4798 tests collected;
`tests/test_sec_probe.py` 10 and with `test_docs`, `test_workflows` and
`test_issuer_http_diagnostics` 178 passed; actionlint 1.7.12 clean on the
workflow; gitleaks 8.24.3 over the changed files: no leaks. Twelve mutants of
the probe in the spare worktree, judged by the whole `tests/test_sec_probe.py`
-- the cache used, an unverified identity still asked, `answered` ignoring the
submissions, a null status counted as a refusal, the address check dropped,
overwrite allowed, the raw error logged, the contact always claimed, no log
line, `docs/` writable, a backwards clock unchecked, the status words changed
-- all die; the control (a docstring word) survives.

**Keep / fix / defer / omit.** Keep: a diagnostic binds nothing and is read off
its log. Defer: a pending-acquisition flag from the merger forms SEC's
submissions already list (`PREM14A`, `DEFM14A`, `SC TO-T`, `SC 14D9`) for each
candidate, now that SEC answers -- no extra request, a warning beside the
evidence and never an order authority; the account note `plan.NOTE_ATTACH_STOP`
recorded under #183. Omit: a scheduled probe.

**Not claimable:** a collection with candidates; Monday's dispatched morning
check, until it runs; any trading edge.


## Codex continuation, 18 October 2026 — acquisition metadata warning

Resumed from main `88e708f2`, after reading the product goal, standing rules,
latest #183/#184 handoff and open #108/#111 dependencies. Branch
`codex/issuer-acquisition-review` adds the handoff's deferred acquisition-form
review warning from existing SEC submissions/history metadata. It makes no
extra provider request and does not classify a deal, alter plans or clear an
event. The optional field is absent when no matching form was observed; both
that absence and older receipts explicitly remain unknown, never clearance.

Local evidence is in `release-evidence/2026-10-18-acquisition-review/acceptance.json`.
320 focused Python/documentation checks passed before one final cap/order test
was added; all 14 acquisition tests passed afterward. 502 issuer browser checks
passed with phone/desktop captures inspected, and all 30 existing producer
fixtures remain current. Removing form detection makes all six propagation
checks fail; an unrelated docstring control passes them. Python 3.12, Node 22,
Playwright 1.62.1; writable XDG cache and matching Chromium were required in
this fresh environment. No provider credentials are configured here.
README and the issuer schema are updated; `.env.example` was reviewed and
needs no change because this adds no variable, request or schedule.

This is local implementation evidence, not a new production release receipt.
Remaining dependencies: identified hosting and provider bindings for dependable
morning delivery, broader news/earnings source coverage, actual on-time session
validation, and owner-confirmed Fidelity capabilities/cash/executions.
Preserve production/history bytes and the existing strategy. No actual trade
or trading edge is claimed.


### Acquisition review follow-up — 18 October 2026

Mo explicitly authorized PR creation and merge after the earlier approval block.
PR #185 was open at this checkpoint; the release reconciliation below records
its completed merge and public acceptance. Independent execution passed 270 Python checks, 502 browser
checks and the six detection-mutation/control cases. It found that the displayed
count of metadata rows not listed omitted the new acquisition links. The count
now subtracts both disjoint lists; a visible assertion at each width holds it.
504 browser checks pass after the fix, with refreshed captures. Hosted checks
and production verification were pending here; no current event or trade is inferred.

### Optional morning receipt browser adapter — 18 October 2026

The browser can read one deployment-owned exact HTTPS `/morning.json` endpoint.
The committed meta tag is empty, so production retains its static same-origin
receipt and does not poll. An explicit deployment opt-in uses credential-free,
referrer-free reads with redirects refused and the existing 512 KiB / 15-second
bounds. Automatic reads are separated by at least 30 seconds, require visible
current production plans inside their recorded pre-open/entry window, stop when
hidden and abort by cutoff. Manual reload and exact-publication binding remain;
source revisions cancel old work. Failed or older receipts cannot replace the
last verified receipt or remove retained source-backed exclusions. No automatic
static fallback is added. README and `.env.example` describe the disabled default.
Locally deferred budget/cadence and backoff outcomes explicitly say no provider
request was made; the source validator refuses unknown or contradictory error
kinds and a local deferral carrying an asserted provider HTTP response.
Independent review reproduced unavailable source metadata beside recent copied
prices. The browser now matches the producer's unavailable observation shapes:
empty trade/quote/volume fields and unknown comparisons, for provider failures
and local deferrals alike. Contradictory source/row claims are refused.

The local preparation receipt in
`release-evidence/2026-10-18-morning-service-reader/prepared.json` separates
synthetic browser controls, targeted Python checks, source mutations and
independent review. Hosting, scheduler precision, server-side provider bindings,
actual fresh quote coverage, measured live-session delivery and the goal's
ten-session reliability gate remain external deployment/operating work. This
adapter alone establishes none of them and places no trade.

### Integrated prepared morning service — 18 October 2026

The service branch joins the durable single-host store, supervised live worker,
fixed-repository source synchronization and optional browser reader. The public
endpoint remains empty. The deployment runbook describes separate processes,
persistent storage, 300-second source sync and 30-second worker invocation
targets; actual host, TLS route and worker credential bindings remain external.

`release-evidence/2026-10-18-morning-service/integration.json` records the exact
runtime hashes and scoped evidence: 264 integrated Python checks, 333 browser
checks (also independently run), 21 unchanged producer fixtures and 4,953
collected Python tests. Independent review and named mutation controls covered
leases/replay isolation, source identity, real socket completion, hard process
deadlines, quotas, shared credential backoff and truthful local refusal labels.
The actual public GitHub handoff used five requests; an immediate repeat used
zero. Today's actual Sunday worker returned `wrong_session` with no network,
child process or reservation. Those are dated implementation/source checks,
not live-session quote coverage or deployed service reliability.

README and `.env.example` now describe the combined runtime. Production data,
history, fixtures and strategy rules retain their bytes. Hosted checks and
public acceptance were pending here and are completed below; the goal still needs
identified hosting/provider bindings, broader news/earnings source coverage,
actual expected-session evidence and owner-reported trade outcomes.

### Verified release reconciliation — 18 October 2026

PR #185 merged reviewed head `6aba0952` as `5931d9de`; PR #186 merged reviewed
head `25d8677d` as `0d32bd29`. Each merged tree equals its reviewed tree. All
seven hosted checks passed on each reviewed head, including 4,812 and 4,953
Python tests respectively. Publisher and final Pages deployments succeeded.
The actual public site matched all 47 required assets for each release and
passed 72 (#185) and 78 (#186) phone/desktop browser checks without browser,
network or HTTP errors. Compact, self-contained transcriptions of the original
observations and source-artifact hashes are retained in
`release-evidence/2026-10-18-pr185/acceptance.json` and
`release-evidence/2026-10-18-pr186/acceptance.json`. This reconciliation does not
repeat or expand those dated acceptance executions.

The current RED/zero-plan state and unknown settled cash are preserved. The
static morning receipt belongs to another publication and remains unavailable;
the issuer receipt has no relevant candidates, so public acceptance does not
claim an actual acquisition warning was shown. The optional service endpoint
meta tag is empty. Hosting, TLS/scheduling, provider bindings and entitlement,
broader issuer news/future earnings and ten expected sessions of live evidence
remain outstanding. Broker cash, order capabilities and actual fills require
owner/broker observations; no actual trade or trading edge is established.

### Operational morning history — 18 October 2026

Continuation found a buildable gap after #186: the service overwrote prior
receipts and provider ledgers, so future operation would lose the evidence
needed to review repeated sessions. Branch `codex/morning-operational-evidence`
adds a bounded local journal and a deterministic read-only session report.
Source, collection and provider events share the existing atomic transactions;
exact publication and receipt bytes are retained by digest. Existing databases
start without backfilled history. Append-time pruning declares lost evidence;
public reads still perform no writes or collection. Strategy, provider quotas,
production records and the empty public endpoint configuration are preserved.

The report separates source changes, local commit time, quote/provider coverage,
charged attempts and unknown public delivery. A late first retained receipt
cannot establish late first delivery when earlier history is missing. Actual
first times stay unknown in that case, while a retained pre-open receipt remains
positive evidence that one existed. The real CLI refuses future observation
cutoffs; the internal builder keeps explicit historical/fixture cutoffs.

The scoped preparation evidence is in
`release-evidence/2026-10-18-morning-operations/prepared.json`. Producer verification
passed 168 focused checks (30 new), report verification passed 36 new checks,
and independent review exercised real SQLite rollback, child interruption,
snapshot consistency, retention, 43 report controls and the CLI clock guard.
Named guard mutations fail their corresponding controls; unrelated controls
pass. An indexed realistic 20,000-event retention check took 0.174–0.330 seconds
in this environment; it is a bounded local measurement, not a hosting SLA.
An offline check using the actual Sunday clock and current publication returned
`wrong_session` with no quota charge or socket connection. The report left ten
past sessions unobserved and Monday not yet due; no live-service history was
manufactured from the current record.

README, `.env.example`, the goal and deployment/report instructions are swept.
Use the release PR for this branch for final hosted-check and deployment
identities; this checkpoint describes the retained local evidence. The prepared
journal/report does not provide a host, provider bindings, broader event sources,
future expected-session measurements or owner-confirmed trading results.

### Prepared CCC event correction — 20 October 2026

The official 15 October issuer release identifies NASDAQ:CCC and a pending
$7.75-per-share cash acquisition by a consortium led by GTCR and including
Elliott. The manual registry now applies its existing unresolved-event exclusion
from that announcement date. Review expiry and the expected closing quarter do
not resolve it. The release's earnings date is source context only; this adds no
earnings-calendar rule or broader news coverage. The bounded source receipt in
`release-evidence/2026-10-20-ccc/source-manifest.json` records the verified
response identity and a short excerpt without redistributing the full webpage.

Five added regression cases cover announcement timing, otherwise executable
burst and anticipation plans, retained stop/sizing refusals, and an unresolved
event after review and expected closing dates. Independent review also replayed
the actual retained October 19 CCC plan: its wide stop, zero shares and absence
of an order remain. Three in-memory registry mutations fail the corresponding
controls; an unrelated event change leaves CCC controls passing.

The initial 101-file regeneration missed downstream consumers: one check ran
before its source regeneration, and the sweep omitted cash previews and the
synthetic recovery rehearsal. Hosted CI exposed three Python failures and two
browser failures; the browser correctly refused the stale publication binding.
The preparation receipt preserves those results and the incomplete initial
checks. Existing generators now update 112 synthetic test fixtures and one
synthetic rehearsal JSON, including dependent private-report controls. All eight
CI generator checks and three additional consumer checks pass after the final
writes in dependency order. Independent comparison found only registry and
binding changes; numeric results, eligibility, provider inputs, bars and
timestamps are unchanged. The same browser still refuses the old receipt.

Production records, history, captured sources and frozen controls retain their
original bytes. README is updated and `.env.example` remains accurate; this
correction requires no new configuration. The scoped local and independent
review receipt is `release-evidence/2026-10-20-ccc/prepared.json`. A subsequent
verified production publication is still needed to show the added exclusion on
the site; this checkpoint claims neither deployment nor a trade.

## Checkpoint, 23 Oct 2026 -- the chart reader's two empty nights, read off the runner, and the SDK held below the API version that refuses `temperature`

**Revision.** Branch `claude/spicystock-market-data-vfd3o2` from `main` at
`503193ea` (the issuer receipt after the 22 October publication). Four files
move: `requirements.txt`, `src/grader.py` (one named constant and its comment;
no rule, so `rules_version` stands and no fixture moves), `tests/test_grader.py`
and `README.md`, plus this note. The checkpoint branch
`codex/issuer-transaction-review` (`4cd163c3`) was read and left where it is;
its two changes follow in the next pull request, reconciled onto `main` rather
than replayed.

**The first morning check inside its window.** The owner's claude.ai task fired
at 13:21 UTC and dispatched `morning.yml` (run 39960745472, created 13:23:07 UTC,
8:23 CT). The guard admitted it, the collector wrote `docs/morning.json` at
13:23:41 UTC (`no_tickets`: the 22 October record is RED and admits no plan, so
no provider was asked), the research collector wrote `docs/research-observations.json`
at 13:23:48 (`no_research_rows`), and the persist job committed both
(`6418f2a8`, `777a9917`) 88 and 94 seconds after the dispatch was created (the
persist job finished at 98). The four scheduled morning crons were created 4.1
to 4.5 hours after their own slots (17:52 to 18:34 UTC; the winter pair's slots
are 14:20 and 14:28) and each skipped every collection step. One in-window check that had nothing to quote is
what the service has to show; the ten-session acceptance still needs a night
with an admitted plan.

**The two empty nights, read off the job logs** (an agent fetched both whole
logs through the GitHub API; the archive host is refused from this sandbox).
Runs 39701029811 (21 October session) and 39879239067 (22 October) installed
`anthropic-2.1.0` from the unpinned `anthropic>=0.40`, and every one of their
four chart-reader calls was answered `HTTP 400 invalid_request_error:
temperature: Extra inputs are not permitted`; the grader fell back to the
checklist for CL, ABT, COST and WRB, `run.reads` counted the four refusals as
`transport` -- the one cause it has for an answer it does not know -- and both
nights published `degraded` on `claude_unavailable`. The 19 and 20 October runs
installed 1.17.0 and were answered. The timeline is exact: anthropic 2.0.0 was
released 15:51 UTC on 21 October, between the two. Reproduced offline with a
mock transport: 2.2.0 sends `anthropic-version: 2026-10-21`, 1.17.0 sends
`2023-06-01`, and the request body is the same under both; under 2026-10-21 the
Messages API removes `temperature`, `top_p` and `top_k` on every model, and the
grader sends `temperature: 0` on purpose for `SAMPLING_MODELS` through
`extra_body`.

**The fix, and the decision it leaves to the owner.** `requirements.txt` holds
`anthropic>=1.15,<2` with the reason beside it; `grader.API_VERSION` names
`2023-06-01` as the version the request shape was validated under; a new test
reads the header the INSTALLED SDK puts on the wire through the grader's own
client, with `temperature` and `output_config` in the body, so a loosened pin
fails CI and not the next evening's run; a second holds the pin's text.
Moving to API version 2026-10-21 means deleting the temperature and grading at
default sampling (the migration guide marks a non-default value the owner's
decision); nothing here decides it. Recorded, not fixed: a 400 is counted as
`transport`, because `run.reads` version 1 has no cause for a request the API
refuses; a new cause is a reads version bump and a validator change, and
`reads()` could stop asking after the first 400 the way it does after a refused
key -- both leads, not tonight's work. The morning host image (`requirements-host.txt`)
already pins 1.15.0.

**Measured** (this sandbox, Python 3.12.3, anthropic 1.17.0 under the pin):
`tests/test_grader.py`, `tests/test_reader_request_v2.py` and
`tests/test_docs.py` 127 passed with the count line at 5069; the full suite and
the mutation controls are recorded on the pull request. **Not claimable until
tonight's run:** that the API answers the pinned SDK's request again -- the
22:16 UTC evening cron on `main` is the test, and its `run.reads` and
`run.reader_usage` are what to read tomorrow.

## Checkpoint, 23 Oct 2026 -- the paused handoff reconciled onto `main`: merger and tender forms under the shipped review block, and acknowledgements that belong to one plan

**PR #190, accepted.** Merged as `28513f27` on `main` with a merge commit over
`503193ea`. The head `17d2f092` passed all seven checks (Tests run 40018042500,
20:17–21:06 UTC: pytest, page, the gate, the native central case to 21:06 and
stress to 20:48; both gitleaks runs). The diff touched nothing under `docs/`, so
the publisher did not fire, correctly (as at #64, #174 and #177); Pages
40024969508 deployed at 21:12 UTC; the merge commit's own Secret scan 40024970058
and Tests run 40024969981 (21:11–21:29 UTC; the native cases skipped by the gate,
as a merge's are) passed. The full suite under the pin here was 5000 passed, 34
environment-gated skips and 35 failed, every failure `tests/test_historical_package.py`
on a sandbox venv without `zstandard`; with it installed that file is 107 passed
and 21 skipped, and CI's pytest on the same head was green. **The first live night under
the pin, read off `main`:** session 23 October, run 40045887700 (the `16 22`
slot, created 00:37:26 UTC on the 24th, 141 minutes late), published 00:38:06
and landed as `cd239b20` at 00:42:20, `run.delivery` 263.1 minutes after
completion, after both slots, before Monday's open; `run.status` **ok**, the
mail delivered. `run.reads` 2 of 2, `complete`, every cause zero (IOSP and Q,
the review selection's two research reads under RED; the refusal limit reads 1
under the #182 floor, unexercised); `run.reader_usage` 2 calls, 2 replies,
14,712 input tokens (8,040 uncached, 3,336 written to the cache, 3,336 read)
and 1,340 output, under `claude-sonnet-4-6`: the API answered the pinned SDK's
request, where the 21 and 22 October nights had four 400s each. The rest of the
night: RED (10-session ratio 0.81, 1,511 up against 1,862 down), 493 reaction
candidates, all at the market gate, 0 tickets; anticipation 822 momentum names,
278 quiet, 10 passing the coil checks, 5 listed, 0 tickets; the tolerance
`tolerated` over 18 stale stocks, every one in the directory (`run.seed_stale`
names none on the seed alone); the follow-up read the 22 October night's 17
stale stocks again at 22 October; `rules_version` `07ccd74f29c7`. One night is
not a trend: the next 400 the API answers is PR C's to name.

**Revision.** Branch `claude/spicystock-market-data-vfd3o2` restarted from
`main` at `28513f27` (the merge of #190) and pushed as **PR #191**: four
commits cherry-picked from the local worktree branch the reconciliation was
built on, their trees equal byte for byte. The checkpoint branch
`codex/issuer-transaction-review` (`4cd163c3`, base `88e708f2`, handoff
`FABLE_HANDOFF.md`) was read and its two changes carried onto current `main`
selectively; nothing of it was merged or replayed wholesale, and `main` had
advanced through PRs #185-#190, five publications over four sessions (19
October twice, then 20, 21 and 22 October) and twelve companion-receipt
commits since its base. `docs/data.json`, `docs/picks.json`, the compact
reader, every receipt, the history, the evidence objects, the quality ledger,
the workflows and the vendored design system are untouched; no run, mail,
dispatch, provider call or credential.

**The issuer change, reconciled rather than duplicated.** The handoff added a
second block, `index.transaction_filings`, beside the `index.acquisition_review`
that PR #185 had shipped a week earlier for the same forms, with a second
section and a second count on the page. One block now: `acquisition_review`
version 2 under the key version 1 shipped. The collector writes it for EVERY
row (`_empty_acquisition_review()`, filled in `_collect_issuer`), so nothing
observed is said rather than left out, and an unverified identity carries zero;
the forms are the eight the handoff named (PREM14A, DEFM14A, SC TO-T, SC 14D9
and each `/A` amendment; version 1 had six); `not_listed_count` is the observed
count less the twelve listed; and each listed entry is `{filing, index_source}`,
the source byte-equal to the row's retained `submissions_source` or one of its
`history_sources` (a filing in both the recent file and a fetched history file
keeps the recent source). `_acquisition_review()` holds version 2 one level in
(version, counts against `metadata_count` less the current reports, the twelve
bound, forms, window, unique accessions never among `listed_filings`, each
source validated as a source and found among the row's, newest first) and
`_acquisition_review_v1()` keeps the first collector's block readable under its
own rules; an absent block is a bundle from before the warning and clears
nothing. The page's `validateAcquisitionReview()` mirrors both branches, and
`acquisitionReview()` draws ONE section (`data-acquisition-section`,
`data-acquisition-state` of `not_recorded`, `unknown`, `none` or `observed`,
`data-acquisition-version` of `none`, `1` or `2`) with the existing per-filing
`data-acquisition-review` lines, each version-2 line naming its retained index
with its retrieval and check instants; the "observed metadata rows not listed
here" count subtracts the listed forms as before. The receipt's `policy` block
is unchanged on purpose: a changed policy would refuse every published receipt.
**Compatibility by execution:** all eleven issuer receipts ever published on
`main` (every commit of `docs/issuer-evidence.json`, each with the bundle it
names at that commit) validate under the new validator; none carries a block.
The generator gains six variants through the real collector (`observed`,
`none`, `partial`, `unavailable`, `history`, `capped`), so the 30 fixtures are
42 and every bundle regenerated, since every row now carries the block.

**The acknowledgement change, and the control that timed out.** `refreshPreview()`
clears the four manual checks when the previewed plan's identity changes
(stage, ticker, `plan_sha256`, the order), as the handoff did; `render()` still
clears them only on a new publication or session. The handoff's same-plan
refresh control called `SCStock.render(SCStock.data, …)` and waited for the
observations to load, which can never happen: `render()` nulls the record's
bytes and resets the observations module to `unbound`, and only the loader's
`bind(raw)` moves it on. The product's clock path is `reclock()`, which a
pinned page refuses, so the multiple-plan case now opens UNPINNED with `Date`
replaced (the first-trade rehearsal's pattern over the same fixture), moves the
clock across the 14:00Z cutoff and calls `SCStock.reclock()`: the desk repaints
through `morning.render()` (`data-morning-offered` true to false), the preview
is withdrawn with the cutoff's own reason, the plan selection and the four
checks survive. Before it, an edit of the same plan's quantity recalculates the
preview and keeps them. README says both.

**Measured** (this sandbox, Python 3.12.3, anthropic 1.17.0, Node 22, Chromium
through Playwright 1.63): the six issuer Python test files 340 passed
(`test_issuer_acquisition_review` new, 59 cases at that commit; 67 at the
round-3 tip and 77 now); `tests/test_docs.py`,
`test_workflows.py`, `test_publish_dashboard.py` and `test_secret_scan.py` 224
passed with the count line at 5130; the issuer generator `--check` 42 current;
the `issuer`, `cashpreview` and `morning` suites 1165/1165 with `--shots`
against `main`'s 1038, and the four new screenshots at 1280 and 390 were
looked at (one column on the phone, nothing sideways); gitleaks 8.24.3 with the
repository's config over the 50 changed files: no leaks. `.env.example` was
read: nothing here is configuration. The full suite, the chart check, the full
smoke, the mutation passes and the review are recorded below as they finished.

**Mutation passes**, the tree never written: page mutants through routed copies
of `app-morning.js` and `app-issuer-evidence.js` (`SCSTOCK_MORNING`,
`SCSTOCK_ISSUER_EVIDENCE`) judged by `--only cashpreview` and `--only issuer`;
Python mutants in a full copy of the worktree, judged by two issuer test files
(`test_issuer_acquisition_review`, `test_issuer_evidence`) with the six
committed-fixture equality cases deselected, so each dies in the test that
names its rule. The acknowledgement rule, four: the reset removed (4
checks), the quote check alone reset (4), the reset made unconditional (8: the
same-plan edit and the same-publication render both lose the checks) and
`render()` clearing on every render (6) die; the control (a comment) passes
565/565 under `--only cashpreview,morning` (305 and 260). The page's review
block, seven: any version accepted (4), the index
source unchecked (4), the omitted count unchecked (2), the amendments dropped
(the producer's observed variant, whose forms are the amendments too, refuses to
load), an unknown identity read as `none` (2), the version-1 branch refused (the
synthetic version-1 bundle refuses to load) die, and the unverified clause
survives (below); the control passes 600/600. The collector and validator,
nine: the amendments dropped, a history source
overriding the recent one, any version, the source unchecked, the omitted count
unchecked, the order unchecked, version 1 refused and the block omitted on a
zero count die, each in the test naming it, and the unverified clause survives
(below); the docstring control passes 120/120. **Two survived and both are
equivalent**, the same rule in two
readers: the browser's `observed_count === 0` clause under an unverified
identity and the Python `_require` beside it. An unverified issuer's index is
held to `metadata_count` 0 by the identity rule (`coverage()`, `_reconcile_row`),
and the count rule bounds `observed_count` by `metadata_count` less the current
reports, so a forged count is refused before either clause is reached. Both are
kept as the statement of intent beside the arithmetic. The harness's Python
phase first died on a missing `rsync`; it copies with `shutil.copytree` now.

**The review, worked.** A workflow by execution over the pushed tip
(`b2973b87`), three finders (the page, the Python, the morning desk). The page
finder returned four, each reproduced here with its own read-only probe before
anything was touched, then driven through the real collector where the finding
named a shape. The medium one: a verified issuer whose index yielded no readable
metadata row under partial coverage -- the collector writes `metadata_count` 0,
`coverage_status` partial, `metadata_invalid` and a zero review block, proved by
driving it over an index whose only in-window row has a future acceptance clock
-- read as `none` and printed *No merger or tender-offer forms ... among the 0
observed metadata rows*, a negative finding over a vacuous denominator. The
state is `unknown` now (`unreadable` in `acquisitionReview()`), in its own words
(*no metadata row of its SEC index was readable (index coverage: partial), so
... were not checked*), and a complete window that held no filing of any form
says so instead of counting forms among zero rows. The generator gains the
variant through the real collector (`semantic-rows-invalid`; 44 fixtures, the
42 byte-identical), the reconciliation test holds its shape, and the issuer
suite holds both states. The lows: every version-2 index link read *retained
SEC submissions index* when the retained source was the history file the same
page calls *Older SEC submissions index* two paragraphs below (named by equality
against the row's own sources now, both labels held in words, not only the
href); the browser's `filing()` admitted a primary document of `.` -- a link to
the accession directory, which Python's `BASENAME` refuses -- and the acquisition
lines are the one place a reader is told the link IS the filing (it is the
collector's basename rule now, through the module's own `diagnosticBasename`,
and the dotted document is a refusal case); and the browser accepts
`schema_version` 2.0 and `observed_count` 8.0 where Python refuses them, because
`JSON.parse` cannot tell 2.0 from 2 -- a pre-existing class for every integer
field, recorded in the schema document and README rather than guessed at from
the raw text: the publisher's validator holds the typed contract before any
publication. Six routed mutants over the three rules (the zero-row state back to
`none`, the coverage clause dropped, the empty-window wording dropped, the label
fixed either way, the old basename rule) die on the checks naming them; the
comment control passes 615/615.

The Python finder returned nine, each reproduced here before it was touched,
and the morning finder four. Two were the shapes this file names. The
unverified-identity clause's test passed for a different rule: with the
unverified row's metadata count left at zero the count rule refused first, and
deleting the clause survived every issuer test (it is also behind the source
rule, since an unverified row retains no index source); the test forges the
metadata count with the block now and holds the clause to its own message, so
the clause dies in the test naming it, and its comment says what stands behind
it. And the every-row rule was held only by the committed fixture bytes: a
collector writing the block once the identity was verified passed the test
that names the rule, which read the fixtures off disk, and died only in the
byte comparison; the test drives `collect_acquisition()` over the `none` and
`unavailable` variants now. **One was the class this file names most, and a
regression of this change:** every new bundle carries the block, and
`_acquisition_review()` read the listed current reports for its overlap check
before the validator had named their shape, so `listed_filings` of `[1]`,
`[{"form": "8-K"}]`, `["x"]` or `[None]` raised a `TypeError` or `KeyError`
through `validate_bundle()` where the module from before the block named
`issuer object keys` (the publisher catches all three, so the effect was the
wrong word in a log); the block is read after the listed reports now, and the
four shapes are a named refusal. Then: the newest-first checks compared the
clock's spelling, so a later instant written under another offset was
accepted last (`_newest_first()` sorts by the instant, in the review block and
the listed reports alike, and the case is held); the overlap with a selected
current report was refused under the word *ordering* (each rule names itself
now, and the corruption cases match the message); the count bound, the recent
file's bound times the history files, was untested above the recent bound, so
a bound of the recent file alone survived while a collector output of 3,999
observed forms -- which the finder drove through the real collector and the
real validator accepted -- would have been refused (two positive cases at the
boundary now, and the refusal past it, which the metadata relationship
refuses first); the README said each filing names *the exact retained SEC
index it was read from*, which the validator cannot hold -- it holds the
source to one of the row's retained sources, and which file carried the filing
is the collector's own record, checked against its captures where they exist
-- and said a version-1 block is *held to its own rules* where it is held to
the current form list (both sentences say what the code does, in README and
the schema). The ninth was the replay: the eleven receipt versions in `main`'s
ancestry validate under the new validator with the bundles they name, none
carrying a block; the retention store keeps fourteen bundles, three of them
(`0848ff98…`, `c20f9e4d…`, `f525a5f9…`) named only by receipts in 10 October
commits outside `main`'s ancestry (`981e6792`, `3e1dfed6`, `f9b91d00`), each
validating with that receipt and its record; the live
pair passes `validate_for_publication`, and the observed and none variants
differ only in the block, the sources that carried it and the counts. The
morning finder's three were test holes: *new plan has no broker
acknowledgements* passed on a fresh desk whatever the clearing rule did (it is
named for what it reads now; the rule is held two checks later, which the
first pass's mutant showed); *the withdrawn preview says the window ended*
read only the preview's state, so a desk printing *Preview paused.* at the
cutoff passed (it reads the availability sentence now, and that mutant dies
on both widths, 305/307); and seven checks inside the two-width loop carried
width-less names. Its fourth was the record of what held: Escape, the Close
button, a prepare click, an observations reload, the cutoff repaint and a
later focus repaint all keep the four checks; a same-session revision of the
same plan clears them, which is `render()`'s own rule.

**The third mutation pass**, over this round's validator rules, each mutant in a
copy of the worktree judged by the three issuer test files in full (172
collected then, nothing deselected), so each dies in the test naming its rule: the
unverified clause removed (dies in the forged-count test now), the count bound
on the recent file alone (the two boundary cases), the block read before the
listed reports -- in its original place and moved one require later (the
shape-corruption cases, and the four malformed listed reports) -- the sort by
the clock's spelling (the other-offset case) and the overlap refused under
*ordering* (the current-report case) all die; the control (a comment) passes
172/172. On the page, through a routed copy of `app-morning.js` judged by
`--only cashpreview`: the cutoff reason replaced by *Preview paused.* dies on
both widths, 305/307.

**The fourth review, over the tests and the documents** -- the two lenses the
starved workflow never judged -- a fresh workflow by execution over `699fafa4`:
two finders and two skeptics a finding, the finders recording 35 single-rule
breaks with the test that caught each. Seventeen findings (nine on the tests,
eight on the documents), each reproduced here by execution before it was
touched. **The skeptic stage starved again**: of the 34 skeptics (two a
finding), 18 died on the session's usage limit, so eight findings were judged
and nine were not; seven of the eight were upheld by both skeptics and one (the
empty-string `match` cases) was split one each way. An unjudged finding is not
refuted, so each of the nine was reproduced here by execution before it was
fixed, and the finders' own 35 single-rule breaks are the record of what the
tests could and could not catch. **One was a page defect**: `newestFirst` ordered the review's filings by the SPELLING of
`accepted_at` where the publisher orders by the instant, so a bundle whose last
entry's clock was respelled under -05:00 (the latest instant) loaded on the
page and was refused by Python, and one whose first entry was respelled to the
SAME instant was refused by the page and accepted by Python -- README's "the
browser holds every other rule of the block" and the schema's ordering sentence
were false of the browser as committed. It compares `instant()` now, in both
branches, and the issuer suite holds both cases. The tests, the shapes this
file names: the shape/count corruption test accepted a `TypeError` or
`KeyError`, so a validator raising through on `filings: None` -- the class this
file names most, which round 3 had closed one function away -- stayed green
(every case names its clause as a `ValueError` now, and `2.0`, `8.0` and `0.0`
hold the typed-integer rule README leans on, which no test held); four
version-1 rules (duplicate accession, the overlap with the listed reports, the
window, the metadata relationship) were held by no test, the v1 duplicate case
appending a copy the count rule refused first (each has a case that keeps the
count consistent and names its clause); eight of twelve corruption cases
matched the empty string, which pytest warns always passes (each names its
clause, and the file runs under `-W error::pytest.PytestWarning`); the entry key
set `{filing, index_source}` was held on neither side; the relationship test
was refused by the bound clause (it is named for the bound now, with a second
case the relationship alone refuses); two browser controls named rules they
never reached (the v1 duplicate, refused by the count; a block copied onto a
VERIFIED issuer, refused by its count and not by any identity or source rule),
and the v1 final rule -- uniqueness, overlap, order -- had no browser case at
all. Recorded, not fixed, three equivalents: the per-entry `_source` call, which
the equality against the row's already-validated sources refuses first; the
bound clause of the count rule, implied by the index's own metadata bound; and
the v1 verified-identity clause, behind the identity and count rules as the v2
one is. The documents: the fixtures README still said thirty outputs and eight
semantic pairs (44 and nine, the six acquisition pairs and the rows-invalid
variant unnamed); README said the validator holds the collector's captures to
the file that carried a filing (only a test replays them); "twelve
publications since its base" counted the companion-receipt commits (five
publications over four sessions; twelve receipt commits); "61 cases" was 59;
round 3's "172/172" was the three issuer files with nothing deselected; the
first mutation pass's "five", "eight" and "ten" named four, seven and nine
mutants with the survivors among them, and its 565/565 control was
`--only cashpreview,morning`; "all fourteen bundles on `main`'s history
validate with their own receipts" overstated what the ancestry carries (eleven
receipt versions, and three retained bundles named only by 10 October receipts
outside it, each re-validated here with that receipt and its record); and the
morning-run figures in the reader-pin checkpoint and `PRODUCT_GOAL.md` measured
the winter cron pair against the summer slots (4.1 to 4.5 hours against their
own) and gave 97 seconds for commits that landed 88 and 94 seconds after the
dispatch was created. Each sentence is corrected above and in its file.

**The fourth mutation pass**, each Python mutant in its own copy of the
worktree judged by the three issuer test files in full, each page mutant a
routed copy judged by `--only issuer`: the v1 duplicate, overlap, window and
relationship clauses deleted one at a time; the v2 entry key set loosened; the
typed `schema_version` and `_count` loosened to admit a float; the `filings`
list clause dropped; the v2 relationship dropped -- nine, all dead in the test
naming the rule (the relationship in three, its new case among them). On the
page: the order back to the spelling (3 checks, the respelled-instant case
among them), the v1 final rule removed (6), its uniqueness half (2) and its
overlap half (2), the entry keys loosened (2) -- all dead. The `_source` call
dropped survives, equivalent as recorded; the two controls (a comment each)
survive at 182 and 627.

**Measured** (this sandbox, Python 3.12.3, Node 22, Chromium through Playwright
1.63, on the round-4 tree): the three issuer test files 182 passed under
`-W error::pytest.PytestWarning` (`test_issuer_acquisition_review` 77 cases);
`tests/test_docs.py` passes with the count line at 5149; the `issuer` suite
627/627 (615 at `699fafa4`), `cashpreview` 307/307 and `morning` 260/260; the
issuer generator `--check` 44 current (no fixture moved). The full suite at
`699fafa4` was 5105 passed and 34 environment-gated skips in 22 m 00 s, and CI
on that head passed all seven checks (Tests run 40025679322: pytest
21:17–21:46 UTC, page 21:17–21:34, the gate, the native central case
21:17–21:45 and stress 21:17–21:46; Secret scans 40025679311 and 40025525146).
On the final tree the full suite was run on the WORKTREE itself, committed
and quiet: 5115 passed and 34 environment-gated skips in 20 m 50 s (5149
collected). A first attempt over a `.git`-less snapshot copy of the tree
returned 3 failed and 24 errors, every one `fatal: not a git repository`: the
tests that read publications off git by commit need the repository, so a suite
run on a copy must carry `.git` or be run on a worktree. CI on the pushed tip
`2a30af64` passed all seven checks (Tests run 40034777473: pytest 22:37–22:58
UTC, page -- the full smoke with `--shots` -- 22:37–22:54, the gate, the native
central case 22:37–22:55 and stress 22:37–23:17; Secret scans 40034777459 and
40034772674).

## Checkpoint, 24 Oct 2026 -- PR #191 accepted; a request the API refuses is its own reads cause, asked once (PR C)

**PR #191, accepted.** Merged as `f466932f` on `main` with a merge commit over
`f8db66e3` (the 23 October publication and its issuer receipt). The code head
`2a30af64` passed all seven checks on Tests run 40034777473 (pytest 22:37–22:58
UTC, page 22:37–22:54, the gate, the native central case 22:37–22:55 and
stress 22:37–23:17; Secret scans 40034777459 and 40034772674); the final head
`a3bc5d2a` (CLAUDE.md alone over it) passed pytest (02:20–02:47), page
(02:20–02:38), the gate's docs-only decision and both gitleaks runs on run
40053753949. Publisher 40055715771 waited for `app-issuer-evidence.js` and
`app-morning.js` and printed *Verified: every one of the 48 public files
matches committed main* at 02:49:56 UTC; Pages 40055736501 deployed at
02:49:54 (40055715503 cancelled as superseded, as every merge does); the merge
commit's own Secret scan 40055715775 and Tests run 40055715801 (02:48–03:16 UTC)
passed. The merge tree equals the local merge the PR C
branch was built on, byte for byte.

**Revision.** Branch `claude/spicystock-market-data-vfd3o2` restarted from `main` at
`f466932f`, pushed as **PR #192**: three commits, `ea97fce3`, `3b758fbe` and
`3ee0e427`, cherry-picked from the worktree branch the work was built on
(`a84ac114`, `5f3d99c0`, `913f9a1e`, over the #191 tree merged with `main`),
the trees equal byte for byte. The reader-pin checkpoint's "recorded, not
fixed": a 400 was counted as `transport`, because `run.reads` version 1 had no
cause for a request the API refuses, and the grader retried an identical
request after one. `docs/data.json`, `docs/picks.json`, the compact reader,
every receipt, the history, the evidence objects, the quality ledger, the
workflows and the vendored design system are untouched; no run, mail,
dispatch, provider call or credential. `.env.example` was read: nothing here
is configuration.

**The rule.** `grader.is_request_refusal()` names an answer whose text carries
the SDK's `Error code: 400 -` prefix and is neither the account's empty-balance
answer (a 400 too, matched first), a refused key nor a reply's own words; such
a request is not asked again -- a transport retry sends the body unchanged and
is refused the same way -- so `grade_candidate()` breaks after one attempt as it
does for an admission conflict. `grade_all()` stops asking after
`REQUEST_OUTAGE_AFTER` (two) consecutive asked names were refused with one
message, `refusal_key()`: the API's own `message`, read off the text, or the
text with its per-request id removed; the remaining names fall back without a
call and carry the refusal, as a credit outage's do. A refusal that names one
request's own content (an oversized image, a prompt too long) differs from name
to name and stops nothing; an accepted reply, a reply the checks refused or a
transport failure between two refusals ends the streak. `run.reads` is version
2 (`reader_coverage.FAILURES_BY_VERSION`): `request` sits between `credit` and
`transport`, the sentence says "N names' requests were refused by the API as
invalid (HTTP 400) and not asked again", and `pipeline.reads_version` is
archived, so `rules_version` moves. `reads_faults()` holds a block to the
version its rules archived -- version 1 and its five causes for every record
from before, which archived none -- and re-derives an open night's reads in
that version's words (`failure_of(error, version)` folds a refused request into
`transport` under version 1, as those records counted it). The funnel is
version 2 with `review_request` ("review request refused by the API as invalid
(HTTP 400)"), and `funnel.faults()` asks for a block only under the version it
archived: a record archived under version 1 is read for what it recorded and
held to nothing. The page's `READ_CAUSES` prints the new word on the Method
strip, `READ_FAILURES_BY_VERSION` is held equal to the module's by
`tests/test_docs.py`, and `reviewSelectionFacts()` reconciles the Morning desk
under the record's archived version, classifying a 400 by the grader's own
marker into `request` under version 2 and `transport` under version 1. README's
reads paragraph and funnel stage list and `knowledge/method.md` say the rule.

**Over the two empty nights, read again** (read-only, the new modules over
the records on `main`): the 21 October publication (`2eb0e0be`, COST and WRB)
and the 22 October one (`503193ea`, CL and ABT) each carry two selected rows
with two attempts apiece, every attempt refused with one message, so one
`refusal_key` across both nights: `temperature: Extra inputs are not
permitted`. `failure_of()` reads each row `request` under version 2 and
`transport` under version 1; both records archived no `reads_version` and
wrote version-1 blocks (`transport: 2`), and `reads_faults()` and
`funnel.faults()` accept both as they stand. Under the new grader each night
would have spent two calls, not four -- one per name, the second refusal
stopping the asking -- and `run.reads` would have said `request: 2` and
"2 names' requests were refused by the API as invalid (HTTP 400) and not asked
again." The nights' verdicts (`unavailable`, `claude_unavailable`, degraded)
are unchanged by the name.

**Measured** (this sandbox, Python 3.12.3, Node 22, Chromium through Playwright
1.63). On the first commit (`a84ac114`): the full suite on the committed
worktree 5132 passed, 34 environment-gated skips and one failure in 20 m 05 s
-- the recovery rehearsal's clean-night literal, which still spelled five
causes and which `5f3d99c0` moved (its two files 87 passed there). On the
final tree (`913f9a1e`, the review's fixes): 5191 collected, the full suite on
the committed worktree **5157 passed and 34 environment-gated skips in
19 m 47 s**; the eight touched Python files 537 passed; 13 page fixtures and
every cascaded generator regenerated twice (once for the rules digest, once
for the `unasked` field) and current, their `--check`s run last (morning
pinned 21, issuer-evidence 44, stop-research 22, research-outcomes 40,
research-observations 24, source-recovery 20, cash-preview 6, the first-trade
backup 80/80 and its parity corpus 109 cases with 32 accepted,
`tools/recovery_rehearsal.py --check` and `freeze_validation_cases --check`);
the browser suites `review-selection` 442/442 -- new: a refused request under
version 2 and under version 1, every request refused under each, the SDK's
plain-text and oversized-body shapes, a name never asked, the grader's own two
non-refusals, the Method strip's cause word under both versions, four
renderer-only faults over the retained 9 October publication (a version-one
block) and two over the version-two producer fixture -- and `inputs`,
`funnel`, `reader` and `coverage` 908/908 over the regenerated fixtures (1315
on the first commit, 1309 before the two faults were pointed at the record that
can show them); screenshots at 1280, 390 and 320 in both themes looked at (the
funnel table lists no stage with no name, so the night's page is unchanged);
`git diff --check` clean; gitleaks 8.24.3 over the branch's commits with the
repository's config: no leaks. The full smoke with `--shots` is CI's page job:
on the pushed code head `3ee0e427` (Tests run 40062212976) the page job
passed 04:24–04:39 UTC, the gate and the native stress case (04:24–04:42)
passed, both gitleaks runs passed, and **pytest failed**: 5172 passed, 8
skipped and eleven errors, every one the setup of the eleven-publication
funnel test. Its fixture fetches the commits a shallow checkout lacks, and
`VERSION_ONE_PUBLICATIONS` named them by eight-character prefix; GitHub
serves a commit the clone does not hold only by its whole object id, so the
runner's `git fetch --depth=1 origin 279ec5a3 …` was answered *couldn't
find remote ref*, and the findings test the fixture was modelled on passes
in CI only because its spec names whole ids. Reproduced here in a depth-1
clone of the real remote: the original file gives the same eleven setup
errors, the abbreviated fetch is refused by hand and the whole id is
fetched. The list is the eleven whole ids now, each case keeps its
eight-character id, and a guard test holds every entry to forty lowercase
hex digits with no duplicate, so the next abbreviation fails on any
checkout, shallow or not; in the depth-1 clone the ten missing commits are
fetched and 12 pass, over the full history the file passes 81, an id
abbreviated kills the guard and a comment control passes 12. The native
central case was still running when this was written; the seven checks on
the final head are recorded on PR #192. The checkpoint commit's own message
(`37f75b51`) counts thirty-six Python and eleven page mutants where the
passes ran 18 and 30 Python (12 of the second pass new) and 5 page; the
counts in this checkpoint are the right ones.

**Mutation passes**, the tree never written. Python, each mutant in its own
detached git worktree of the shared repository at the PR C commit (so the
tests that read publications off git by commit still run), judged by
`tests/test_grader.py`, `test_reader_coverage.py`, `test_funnel.py` and
`test_docs.py` in full: eighteen -- the no-retry break dropped, the stop after
one and after three, the streak never reset, `refusal_key` keeping the request
id and ignoring the message, `is_request_refusal` admitting the credit answer
and a reply's own words, the marker without its dash, `failure_of` ignoring the
version, `reads()` writing the current version, the validator ignoring the
archived version and taking an untyped one, the sentence without its request
clause, the funnel gate dropped and its stage dropped, `reads_version` not
archived, and the page's lists drifting from the module's. All eighteen die,
each in the test naming its rule (the dropped stage first against the
regenerated fixtures and, with the fixture-equality tests deselected, in the
stage test `5f3d99c0` adds; the unarchived version first in the pipeline's own
publication, refused by the validator); the control (a comment) passes 292.
Page, through routed copies of `app.js` judged by `--only review-selection`:
the classifier reading every 400 as transport (2 checks), as request under
version 1 too (2), the failure list fixed to version 2 (7, the retained
version-one record among them), the archived-version check dropped (4, the
retained record's fault and the producer fixture's) and `READ_CAUSES` without
the new word (2, the Method strip) all die; the control (a comment) passes
409/409.

**The second mutation pass**, over the final tree, each of thirty mutants in
its own detached worktree at the fix commit and judged by the same four test
files in full with the fixture-equality test deselected, so each dies in the
test naming its rule. The first pass's eighteen again, their anchors moved by
the review's fixes (the funnel gate is "a record made before the funnel rule
is asked for no block" now, since the version-equality gate it struck no
longer exists), and twelve over the fixes' own rules: the SDK's class labels
dropped (dies in the eleven-status shape test), `RequestOutage`'s label not a
refusal, the names after the stop carrying the second name's answer, `unasked`
never counted, unchecked by the validator and not re-derived on an open night,
the sentence ignoring it, `funnel.build()` ignoring the archived version, the
stage read under the current reads version, the labels unfiltered, an unknown
funnel version not a fault, and `archived_version()` untyped. All thirty die:
the three funnel-version mutants in the git-backed test over the eleven
retained version-one publications and the stage test; the unarchived reads
version in ten tests, the pipeline's own publication among them; the page's
drifted list in the docs test alone; the control (a comment) passes 304. Two
harness defects of mine on the way, neither a kill: the pass stopped at its
fourteenth mutant on the sentence anchor the review had moved, and its
failure filter kept the grader's `ERROR` log lines, so the first three kills
were named by their count alone; re-anchored, the remaining seventeen ran and
those three were judged again under the fixed filter, each dying in the tests
named above.

**The review, worked.** A workflow by execution over the first commit
(`a84ac114`), three finders (the rule's semantics, the page, the tests and the
documents) and one skeptic a finding: ten findings, ten upheld -- the two
mediums read as low-to-medium and low by their skeptics -- and every one
reproduced here before it was touched. The rule finder's three. **The marker
missed the SDK's own shapes** (medium): `anthropic`'s client writes "Error
code: 400 - <body>" only when the body parses as JSON; a plain-text, HTML or
empty 400 body gives the text alone or "Error code: 400" with no dash, and a
413 is `RequestTooLargeError` -- built through the installed client's own
`_make_status_error_from_response()` over constructed responses, each read as
transport and retried. The rule reads the SDK's class labels now
(`REQUEST_REFUSAL_LABELS`: a 400 or 413 whatever the body) beside the status
markers for a 400 or 413 another wrapper carried, and the test builds its cases
through the same constructor over eleven statuses (400 as JSON, text, HTML and
empty; 413; 401, 403, 404, 429, 500, 529), so the suite sees the shapes a run
meets rather than ones a test spelled. **The funnel gate held a version-1
record to nothing** (medium): the first commit skipped every check for a record
archiving funnel version 1 -- every publication from 12 to 23 October -- so a
forged, moved or malformed block on a retained publication passed
`report.validate()` and `tools/verify_retained_publication.py` where the code
before the commit refused it, because the re-derivation was version-blind
(`failure_of()` read a 400 as `review_request` where those records wrote
`review_transport`). `funnel.build()` re-derives a record under the version its
rules archived now (`archived_version()`, `REACTION_STAGES_BY_VERSION`,
`READS_VERSION_BY_FUNNEL`: a version-1 record in version 1's stages, groups,
labels and reads words), `faults()` holds every known version to its own
re-derivation and names an unknown one, and a test fetches the eleven retained
version-1 publications by whole object id (12–23 October, both 19 October
revisions) and holds each to its archived block to the byte, the 21 and 22
October refusals at `review_transport` under version 1 and `review_request`
under 2. **Never-asked names were worded as refused** (low): after the stop,
the remaining names carried the second name's answer verbatim -- another name's
request id -- and the sentence said their requests were refused. They carry
`grader.RequestOutage`'s own sentence now (the message, no request id),
`run.reads` counts them as `unasked` beside `request`, and the sentence says
how many were refused and how many went unasked; the funnel's label says both.
The page finder's one (low) was a hole: no browser control told the dashed
marker from a bare "error code: 400", so a page classifying by the bare text
passed the suite and only the docs test's string check held it -- which a
comment could satisfy. Two controls carry the grader's own non-refusals now (a
4000 status, the bare 400 without the SDK's dash), and the docs test reads the
page's label and marker lists off their `const` lines against the module's. The
tests-and-documents finder's six: README, the commit message and the grader's
comment promised that a refusal naming one request's own content "never stops
the run by itself", while the rule is message equality -- two names refused
alike for an oversized chart stop the asking as the temperature refusals did,
and the one test of the rule scripted two DIFFERENT messages (the second shape
this file names); the words say what the code does now, and a test holds two
identical content refusals to the stop beside two different ones that do not.
The commit message and the grader's comment conflated calls and names ("four
calls bought nothing, and run.reads counted the four as transport": four calls
a night, eight over the two nights, and two names a night counted); the comment
says so, the commit message stands as written. The first commit's funnel gate
test passed its named assertion for another reason (the first shape: the
lowered version left a version-2 block that still equalled the re-derivation,
and only the deleted block failed), replaced by the version-aware test above.
`a84ac114` alone was red on the rehearsal literal `5f3d99c0` fixed. The
integration test gave every name one request id where the real nights'
differed, so `refusal_key()`'s id rule could not fail there; each name has its
own id now. And `build()` over a version-1 record yielded version 2's stage
set, the reading tool's half of the funnel finding, closed by the same fix.

**Keep / fix / defer / omit.** Keep: a refused request is named, never
retried, and never read as a transport fault; the stop needs two alike. Fix if
it bites: the stop reads the API's message by a regular expression over the
SDK's error text; a provider that changes its error shape makes two refusals
read as different and the run asks every name once (bounded by the names, as
before). Defer: a reads cause for an HTTP 429 or 5xx, which a transport retry
is right to retry. Omit: any retry of a refused request; a page that guesses a
cause a record did not archive.

**Not claimable:** a live night with a refused request -- the first such night
after the merge is the test; any trading edge.

## Checkpoint, 24 Oct 2026 -- PR #192 accepted; the confirmatory figure read again after 23 October, and the forty September rows the newest publications reached

**PR #192, accepted.** Merged as `b4901830` on `main` with a merge commit over
`f466932f` at 05:47 UTC on 24 October, its tree the head `cd1f5512`'s byte for
byte. That head passed all seven checks (Tests run 40064272219: pytest
04:55–05:18 UTC, page 04:55–05:13, the gate, the native central case
04:56–05:44 and stress 04:56–05:47; Secret scans 40064272373 and 40064269201).
Publisher 40067658261 waited for `app.js` and printed *Verified: every one of
the 48 public files matches committed main* at 05:48:58 UTC; Pages 40067674802
deployed (40067657796 cancelled as superseded, as every merge does); the merge
commit's own Secret scan 40067658337 and Tests run 40067658289 (05:47–06:09
UTC) passed. The first night with a refused request is still the test of the
rule; not claimable yet.

**Revision.** Branch `claude/spicystock-market-data-vfd3o2` restarted from
`main` at `b4901830`, pushed as **PR #193**. The 17 October
re-read's own next action: the 16 October tickets reached their fifth session
on 23 October, and six publications had landed since (19 October twice, then
20, 21, 22 and 23 October). Nothing under `src/` changed and no rule moved; the
frozen study (`tools/signal_outcomes.py`, blob `39d4f25a…`) is unchanged and
the guard now holds the tree's file to that blob; `docs/data.json`,
`docs/picks.json`, the compact reader, every receipt, the history, the evidence
objects, the quality ledger, the workflows and the vendored design system are
untouched; no run, mail, dispatch, provider call or credential. `.env.example`
was read: nothing here is configuration.

**The re-read** (`docs/input-truthfulness/2026-10-24-signal-outcomes-confirmatory.md`).
The frozen study over thirty-seven publications under a spec that is the frozen
file with twenty entries appended -- the 17 October extension's fourteen and
these six (SHA-256 `ae700f197805…`; the byte-level diff against the frozen file
retained), run under Python 3.12.3 and pandas 3.1.0 (exit 0, 15.4 s) and again
under Python 3.13.17 and pandas 3.0.5 (exit 0, 17.0 s) to the same bytes
(uncompressed SHA-256 `310a2fdecb3f…`), each run's record retained. **The
confirmatory admitted stratum is 316 settled over fifteen nights (2 to 22
October), mean −0.081R a ticket, the mean of its night means −0.051R with a 95%
night-bootstrap interval of −0.319 to +0.251: readable, moved from −0.138R a
night as the 12 to 16 October nights completed, and still establishing no
sign.** Of the 78 rows still moving on 17 October, 62 settled (22 wins, 39
losses, 1 even, −0.97R in sum), 12 became uncertain and 4 were not filled; the
15 October night read whole is −0.463R over 61 where its 18 first-session stops
alone read −1.000R, the early-read bias measured a second time and the night
still the stratum's largest loss; the 14 October night went from −0.450R over 7
to +0.267R over 21. The five nights since are all RED and carry 65 rows still
open or pending (the 23 October night's 37 tickets enter Monday 26 October);
the 19 October night is the stratum's best, +19.75R over 14 settled with 6
still open; the 22 October night, 257 admitted rows, is the largest the study
has read, 87 of its rows unsized at $2,000 and 13 withheld by the stop rule.
Three of the sixteen confirmatory nights were YELLOW (105 settled, −0.10R in
sum) and thirteen RED (211 settled, −25.43R, mean −0.121R); the eight
mechanical A+ tickets that settled are 2 wins and 6 losses, −3.18R. The
reader's own A/A+ admissions are still the two DAC rows. The exploratory
stratum is unchanged to the figure (301 settled, −0.119R, interval −0.347 to
−0.014).

**The forty rows that moved, and why.** Every one of the 17 October run's
11,323 rows is in this one and no settled ticket changed its R, but forty rows
of the two oldest nights (19 of 11 September, 21 of 14 September) moved between
buckets, 13 of them settling for the first time, none admitted. The frozen rule
that the newest publication wins each bar worked two ways, decided by whether a
later publication charted the symbol: the study reads bars from bursts'
120-session series and the `observations` block alone, and each of the six
publications lists 335 to 988 bursts but charts only its tickets, cut names,
closest miss and top 24 by rank (`pipeline.SERIES_TOP`). Twenty-eight rows,
over twenty-three symbols (five of them on both nights), belong to symbols one
of the six charted: the series begins between 29 April and 5 May, so the
September signal is walked (13 settled, 9 uncertain, 6 not filled). Twelve
rows, twelve symbols, gained no series -- eleven listed again below the charted
bursts and one, EDHL, only observed -- so two to five October observations move
a signal from `unmeasured` to `basis_mismatch`. Of the forty, three are
admitted rows: TWFG and VRDN of 14 September the second way, ROKU of 14
September the first.

**What else moved.** `tools/build_historical_findings.py` reads the 24 October
study and lists the new report; `docs/historical-findings.json` is rebuilt
(31 nights, 28 RED and 3 YELLOW, 11 to 23 October, `--check` current), so the
Record view's replay carries the 19 to 23 October nights and the confirmatory
split's 16 nights, 5 inside their hold. `tests/test_signal_outcomes_reread_24_october.py`
is the re-read's own guard (twelve tests): the tool held to its blob, computed
without git; each run record parsed and its code commit held, fetched by whole
id, to a tree whose tool is that blob; the second run's two output digests held
to this run's bytes; the spec held to the frozen file with publications
appended and to its retained diff; the title, the appended commits and the
frozen file's digest read off the spec files; every number the report prints
read again off the rows, the run records, `record.SCORECARD_MIN_PLANS` and the
publications fetched from git by whole id, anchored to its phrase; which bursts
each publication charts read off the publication and held to
`pipeline.SERIES_TOP`; the night table's rows held to the study's nights by
their date cells, in order. The 17 October guard is unchanged and its report
carries one pointer line. README, `docs/input-truthfulness/README.md` and this
file are swept.

**The review, worked.** A workflow by execution over the uncommitted re-read,
three finders (the numbers, whether the tests can fail, the mechanism) and one
skeptic a finding. The finders returned ten findings; all ten skeptics died on
the session's usage limit before judging one, so each finding was reproduced
here by execution before it was touched; the skeptic stage, resumed on
another model, then upheld all ten. Every figure the finders re-derived from the rows matched the
report, and the study re-ran byte-identically under both interpreters in the
review's own directory. The two mediums on the report: the mechanism said
twenty-eight of the forty "are symbols that burst again" and the other twelve
were "merely observed", when 39 of the 40 rows' symbols were listed as bursts
again -- eleven of the twelve below the bursts a publication charts -- and the
twenty-eight are rows over twenty-three symbols (the report's numbers were
right, its explanation was not); and the guard said the study was frozen at
blob `39d4f25a` while holding only a string in the run record, so a modified
tool passed it. The lows: "In the admitted stratum three rows moved ... its
non-settled buckets read 106" labelled the exploratory admitted stratum's line
as the stratum's (whose summary line reads 261); the index entry said the forty
moved "between unsettled buckets" when thirteen settled; twenty-one numbers and
identifiers the report prints were read by no test (the frozen digest, the
appended commits and counts, the run's interpreter and wall time, the DAC
dates, the second mentions of 65 and 371, the risk a ticket, the twenty-settled
minimum, the last YELLOW night); the run record was held to three strings; the
night table's row count admitted a row with any regime word but red, yellow or
green; an assertion carried an unreachable first branch; and the count line
was stale. One more found while fixing: "as the 13 to 16 October nights
completed" left out 12 October, whose one moving row settled; the nights moving
on 17 October were 12 to 16 October, and the test now reads them. The second
interpreter's run was a claim with no record behind it; it was run again here
and its record, with both outputs' digests, is retained.

**Measured** (this sandbox, Python 3.12.3, Node 22, Chromium through Playwright
1.63): the full suite on the staged re-read over `b4901830`, before the review's
fixes: 5168 passed, 34 environment-gated skips and one failure, the count line
this checkpoint moves (21 m 32 s); after them the guard 12 passed under
`-W error::pytest.PytestWarning`, the six related test files 110 passed with
5204 collected, `build_historical_findings.py --check` and `evidence_review.py
--check` current, and the findings browser suite 1378/1378 with `--shots` over
the new `main`, the phone and desktop screenshots looked at. Thirty-nine mutants
over the report, the two run records and the tool, each in a copy of the tree
and judged by the whole guard file, all die in the test naming their rule; two
controls (an unasserted word, a reflowed paragraph) pass 12/12. One mutant's
anchor first missed a line break and was re-run with it, and died. gitleaks
8.24.3 over the changed files with the repository's config: no leaks;
`git diff --check` clean. The full suite on the committed tree (`448f9aa4`):
5170 passed and 34 environment-gated skips in 21 m 59 s. CI on that head passed
all seven checks (Tests run 40070529781: pytest 06:31–06:48 UTC, page
06:31–06:47, the gate, the native stress case 06:31–06:50 and central
06:31–06:58; Secret scans 40070529775 and 40070469317).

**The morning checks of 19 to 23 October, read.** The owner's scheduled
dispatcher (*SpicyStock morning check (8:21 CT)*, one persistent session) was
due each weekday, but its session answered Monday to Thursday with the
account's weekly usage limit (*You've hit your weekly limit*), so nothing was
dispatched on 19, 20, 21 or 22 October; on Friday it read the four queued
firings as stale and dispatched once, run 39960745472, created 13:23:07 UTC
(8:23 CT, inside the window), whose two receipts landed at 13:24:35 and
13:24:41 UTC: `no_tickets` (the 22 October record admits no plan) and
`no_research_rows`. GitHub's own morning crons for the 13:20 UTC slot were
created between 17:52 and 19:20 UTC each day, after the 9:00 CT cutoff, and
every collection step skipped. So #111's count of consecutive sessions with an
in-window morning check stands at one. The dispatcher session was created on
Haiku and was switched on 23 October to Fable 5.1 at extra-high effort with
ultracode on; this session met the Fable usage limit at about 05:50 UTC on 24
October. A dispatcher that runs on the account's own usage competes with every
other session for it, so whether Monday's 13:21 UTC firing dispatches depends
on the limit then; the owner can put that session back on Haiku with `/model`.
Not claimable: Monday's check.

**Keep / fix / defer / omit.** Keep: the spec frozen and extended by appended
publications only; each re-read a dated directory with its own guard and a
record for every run it cites; the findings builder reading the newest study
and the page printing what the file writes. Fix if it bites: the frozen study's
footer still says every ticket was refused by the RED gate, which the dated
reports correct and only a new freeze could change; a September signal's walk
can still change when a later publication charts its symbol, which is the
frozen rule and is counted, never hidden. Defer: the re-read after 30 October,
when the 23 October tickets reach their fifth session. Omit: any rule,
threshold or account change on these numbers; an edge claim.

**Not claimable:** a morning or research observation; any trading edge.

## Checkpoint, 24 Oct 2026 -- PR #193 accepted; the evidence archive keeps what a served file names, before its cap refused a publication

**PR #193, accepted.** Merged as `bef7dd67` on `main` with a merge commit over
`b4901830`. Publisher 40073876114 printed *Verified: every one of the 48 public
files matches committed main* at 07:23:42 UTC; the merge commit's own Tests run
40073876121 (pytest, page) and Secret scan 40073876152 passed.

**Revision.** Branch `claude/spicystock-market-data-vfd3o2` from `main` at
`bef7dd67`, pushed as **PR #194**. `docs/data.json`, `docs/picks.json`, the
compact reader, every receipt, the history, the quality ledger, the workflows
and the vendored design system are untouched; no rule moved (`rules_version`
stands, no fixture regenerated); no run, mail, dispatch, provider call or
credential.

**What a sweep for date-dependence found.** A workflow by execution (finders
over the tests, the browser suites and the production writers, each claim
simulated in the future, a skeptic each, a completeness critic) confirmed three
of four candidates; the critic added two. The serious one was not a test.
`provenance.write_objects()` refuses a publication once `docs/evidence` would
pass `MAX_ARCHIVE_BYTES` (128 MiB, 134,217,728 bytes), and nothing removed an
object: v1 said so, and that capacity exhaustion would need "an explicit
retention decision". On 23 October the archive held 86,196,761 bytes (86.2 MB,
82.2 MiB; the first commit's message says "86 of its 128 MiB", the wrong unit),
grown by 0.5 to 4.9 MB a publication, about 3 MB a session from 12 to 23
October. The 48.0 MB left would have refused the first evening publication
between about 6 November (4.9 MB a night) and 17 November (3 MB). Also
confirmed: `tests/test_clock.py`'s no-argument test read the real clock, and
the calendar it reads ends in 2035; and the weekly full-history secret scan
reads the SEC excerpts the issuer collector commits, which no allowlist covers.

**The rule.** Before each night's objects are written and counted against the
cap, `publish_bundle()` calls `provenance.prune_objects(docs, keep=tonight)`:
an object no other file under `docs/` names leaves the working tree. A name is
a full 64-character lowercase hex run in a file's text (`.gz` read expanded);
any 64 inside a longer run counts too. Nothing is removed unless every file
outside the archive was read in full: a link, a directory that cannot be
listed, a file that is not regular or is over `RETENTION_SCAN_BYTES` (64 MiB),
or a `.gz` that does not expand raises, and the capacity check then decides as
before. Unknown entries in the archive stay. A removal that fails stops there
and says how far it got. `pipeline.log_retention()` writes what is left against
the cap and what went, and warns above `RETENTION_WARN_FRACTION` (80%). The
archive follows the recovery catalog a night behind. `git add docs` stages the
deletions, as it already does for the catalog's own; git keeps every removed
object at every commit that carried it. On a copy of the 23 October tree it
removes 1,652 objects (7,978,559 bytes) and leaves 13,185 (78,218,202 bytes,
58% of the cap), the scan taking about 6 seconds.

**What it does not bound.** The publication and the 21-day catalog are the
rolling part. The dated reports under `docs/input-truthfulness` (22.2 MB, a
protected-files manifest of 28 September among them), the quality ledger
(every read chart, for good), the research cohorts and journal and the frozen
validation cases are permanent: 31.9 MB with the rolling part removed. The
ledger adds about 0.12 MB a two-read night and 0.8 MB a twelve-read night, so
the 56.0 MB left lasts about 70 to 480 sessions at today's rolling size; the
80% warning comes first, and the next decision -- a rule for ledger-named
charts or a larger cap -- is that day's.

**Tests that read the rolling archive.** A full `pytest tests/` run and both
research fixture generators recorded every read under `docs/evidence`: 497
objects (the 9 October publication's 487, six provider placeholders, two dated
reader frames, CRL's and IQV's frozen-case frames). They are frozen byte for
byte under `tests/fixtures/retained-evidence/` and read through
`provenance._object()`; a test holds each to its own name. A second full run
in a worktree with `docs/evidence` deleted found the one read the repointing
had missed: `tools/historical_input_proof.volume_sensitivity()` read a fixed
path, and takes the archive it reads now. Both generators and all 13 page
fixtures reproduce byte for byte there.

**Also.** The wall-clock test pins the clock it reads, four instants
(unpinned, all four fail). Every direct runtime and test requirement is held
below its next major (`tests/test_requirements.py`); their own dependencies are
not -- `python-dateutil` resolves to 3.0.0 under pandas here, where
`requirements-host.txt` pins 2.9.0.post0 -- and the sentences say so (they
are pinned since 24 October, in `constraints.txt`; see that checkpoint).
`tools/freeze_validation_cases.py --check`, which CI runs, holds each frozen
case's source frame, system prompt and chart present in `docs/evidence`: the
one way a branch cut before a night's removal could merge naming an object the
archive no longer holds.

**The review, worked.** A workflow by execution over `d2df33ff` (safety, can
the tests fail, every sentence; a skeptic a finding, 28 agents) returned 25
findings and every one was upheld, each reproduced here before it was touched.
Two mediums on the code: the merge race above, and `log_retention()`'s refusal
branch and 80% warning, which no test reached (dropping the branch turned a scan
refusal into a failed evening after the publication was installed). The lows:
`os.walk` silently skipped a directory it could not list; a removal failing
midway was logged as "left as it was"; the OSError half of the catch, the
bounds one byte over, gzip members over the bound together, a FIFO, a `.csv.gz`
and an object-named link or folder in the archive had no case; the evening
test's first assertion was held by the previous `data.json` rather than the
catalog, and its last could not fail its own message; two frozen reads skipped
the digest; and seven sentences said more than the code (the unit, links
inside the archive, "never missed for its spelling", the permanent growth, the
actionability README, every dependency bounded, the frozen set's groups). All
are fixed.

**Mutation pass.** Twenty mutants and a control, each in a scratch worktree
and judged by the whole test file naming its rule: 19 died first; **one
survived, a hole** -- the archive link in the unknown-entries test pointed at
nothing, so `is_file()` alone also kept it; it points at a real file now and
the mutant dies. The control (a comment) survives.

**Measured** (this sandbox, Python 3.12.3): the retention and freeze tests 30
and 35; the full suite and CI on the pushed head are recorded on PR #194.
gitleaks 8.24.3 over the branch's commits: no leaks.

**Open leads, written down.** The reader-observation sidecars (`docs/reader-
observations/`, 15 objects, 80.2 MB on 23 October, about 5.9 MB each and
growing with the signal window) peak near 110 MB of their own 128 MiB cap on 30
October at today's size and refuse a publication if a sidecar grows about 20%;
the same class, not yet reached. The weekly full-history secret scan reads the
SEC excerpts and would stay red from the first detector-shaped phrase; a scan
before the issuer collector commits is the fix. Transitive dependencies could be
held with a constraints file (done 24 October: `constraints.txt`).

**Not claimable:** the first night under the rule -- Monday 26 October's
publication; read its run log's *Evidence archive:* line and the commit's
deletions, and record them here. Also not claimable: a morning or research
observation; any trading edge.


## Checkpoint, 24 Oct 2026 -- PR #194 accepted; past the reader archive's cap, an old tab's copy gives way before a publication does

**PR #194, accepted.** Merged as `01b29d8d` on `main` with a merge commit over
`a46c0932` (the 23 October source-recovery receipt). The head `82c12552` passed
all seven checks (Tests run 40095200289: pytest, page, the gate, the native
central and stress cases; both gitleaks runs). Publisher 40097467723 printed
*Verified: every one of the 48 public files matches committed main* at
13:17:22 UTC; Pages 40097487954 deployed (40097467397 cancelled as superseded);
the merge commit's own Secret scan 40097467736 passed. The first night under
the evidence rule is still Monday's.

**Revision.** Branch `claude/spicystock-market-data-vfd3o2` from `main` at
`01b29d8d`, pushed as **PR #195**. Nothing but `src/reader.py`, its tests,
`tests/test_docs.py`, README, `.env.example` and this file moves; no rule, no
record, no fixture; no run, mail, dispatch, provider call or credential.

**What the record showed.** `docs/reader-observations/` holds one object per
publication, the deferred observations the browser loads for saved research,
kept 21 calendar days for an open tab under a cap of 84 objects and 128 MiB
whose excess refused the whole evening publication ("explicit retention
decision required"). On 23 October: 15 objects, 80,201,638 bytes, the objects
grown from 5,040,916 bytes (9 October) to 5,925,119 (22 October) with the
signals and symbols in the 21-day observation window. A replay from that real
archive (`scratchpad/sidecar-sim`, one publication a session, objects grown
over ten sessions to a final size): at 6 and 7 MB neither rule refuses (peaks
109.6 and 118.3 MB); at 8 MB the old rule refuses once, 25 November; at 10 MB
four times, the first on 12 November. A GREEN stretch is where the objects
grow and where a refused publication costs most.

**The rule.** When a new object would pass the cap, the owned objects still
inside their window give way, oldest last-served session first, ties by
digest. Never the object served tonight (an older object served again
included), never the one it replaces, never an unknown file, and never an
owned file whose bytes or length are not the manifest's (that refuses, as an
expired one did). Removals wait until the fixed files are installed, unless the
working set is already past its bound (an earlier failed cleanup, or a file the
archive does not own): then the planned removals go first. An owned entry
whose file is gone is retired before planning; the manifest bound reads kept
entries against the cap and the whole index against one past the working set;
a rollback removes the object it brought in. `_log_archive()` states objects
and bytes against both caps, warns past 80% of either, and says when objects
were removed, could not be, or the manifest update failed; it never fails an
installed publication.

**Two reviews by execution.** The first, over `27e8e66a`, three lenses and a
skeptic a finding: 15 findings, all upheld. The defects were the failed-cleanup
class: a manifest rename failing after an eviction left the manifest owning a
deleted file inside its grace, and at the count cap every night refused until
it expired (17 nights in the probe); at the count cap eviction left no working
set slack, so one transient cleanup failure refused every later night. The rest
were the log ("1 objects", "were removed" after a failed cleanup, the byte cap
named when the count cap bound) and test holes (order held only on equal
sizes, the length half of the ownership check, an expired and an in-grace
removal on one night, the tie-break's precondition, README's numbers). The
second, over `20928335`, two lenses: 8 findings, 7 upheld: the orphan a
rolled-back install leaves (pre-existing, unreachable in the workflow, which
persists nothing from a failed run), the early removals' real trigger, the log
after a failed manifest rename, the count warning's boundary, the log's guard.
All fixed.

**Measured** (this sandbox, Python 3.12.3): the full suite on `cbc3c5eb`, run
on the committed checkout, 5232 passed and 34 environment-gated skips in
22 m 34 s (5266 collected, the count line); `tests/test_reader_projection.py`
and `tests/test_docs.py` pass on it. CI on `cbc3c5eb` (Tests run 40103249278):
pytest 14:36-15:00 UTC, page 14:36-14:54, the gate and both gitleaks runs
green; the native cases are recorded on PR #195. Three mutation passes, each
mutant in a detached worktree judged by the whole of
`tests/test_reader_projection.py` and `tests/test_docs.py`: over `9f9ea745`,
fifteen, fourteen dead at once and **one survivor, a hole** -- the served
object could be evicted, because no test served an older object again (one
does now, `9023e72b`); over `20928335`, twenty-nine, twenty-eight dead and **one
survivor, a hole** -- the manifest's read bound back at one past the cap,
which no test read after two failed cleanups (one does, `81c5f884`); over
`cbc3c5eb`, thirty-five over every rule of the change -- the eviction loop, the
protected pair, the order and its tie-break, both halves of the ownership
check, the deferred removals and the early ones, both caps, the final and the
working-set refusals, the absent-entry retirement, both manifest bounds, the
rollback's own object, the cleanup flag and every clause of the log -- all
dead in the test naming their rule; the control (a comment) survives every
pass. A first run of the third pass used an interpreter without pytest, so
every mutant "died" with no test run, the control too; it is void and was run
again. gitleaks 8.24.3 over the branch's commits: no leaks.

**Keep / fix / defer / omit.** Keep: the cache serves open tabs and never
outranks a publication; nothing unowned or unverified is removed. Fix if it
bites: a night that rolls back after the early removals loses those old-tab
copies. Defer: the canonical `data.json`'s own 32 MiB bound, shared by the
morning, issuer and browser readers: 19.1 MB at 988 bursts on 22 October, about
11 KB a burst raw and the observations block about 6 MB compact, so a thrust day
near 2,300 bursts, or an active stretch's larger observations, refuses that
night's publication -- the next milestone. Omit: a larger cap as the fix.

**Not claimable:** a live night on which either cap binds; Monday 26 October's
*Evidence archive:* and *Reader observation archive:* lines are the first to
read. Also not claimable: a morning or research observation; any trading edge.

## Checkpoint, 24 Oct 2026 -- PR #195 accepted; past the recovery catalog's cap its oldest records give way, and the ledger is captured whatever the catalog does

**PR #195, accepted.** Merged as `1e1ad24f` on `main` with a merge commit over
`01b29d8d`. The code head `cbc3c5eb` passed all seven checks (Tests run
40103249278: pytest 14:36-15:00 UTC, page 14:36-14:54, the gate, the native
central and stress cases 14:36-15:25; both gitleaks runs); the final head
`22812193` (CLAUDE.md alone over it) passed pytest, page, the gate's docs-only
decision and both gitleaks runs. The diff touched nothing the publisher serves,
so the publisher did not fire, correctly; Pages 40108275306 deployed at 15:44
UTC; the merge commit's own Secret scan 40108275741 and Tests run 40108275733
(15:43-16:08 UTC) passed.

**Revision.** Branch `claude/spicystock-market-data-vfd3o2` restarted from
`main` at `1e1ad24f`, pushed as **PR #196**. `docs/data.json`,
`docs/picks.json`, the compact reader, every receipt, the history, the evidence
objects, the quality ledger, the workflows and the vendored design system are
untouched; no rule moved; no run, mail, dispatch, provider call or credential.

**How this was chosen.** A read-only design workflow over the canonical
record's 32 MiB bound (three investigations, three designs, two judges; 8
agents) found the nearer risk one bound over: `docs/history/`, the public
recovery catalog behind *Find earlier setup*, capped at 84 records and 128 MiB,
held 20 records over 16 sessions on 23 October -- 86.5 MB of files and a 3.9
MB index against 134.2 MB, 67%. Each burst costs about 7.9 KB a record and a
same-session re-run keeps a whole second copy (three revisions of 9 October,
two each of 8 and 19 October in the window). `history.publish()` raised past
either cap AFTER the record was installed and the mail sent, and
`run_evening()` then skipped `quality_ledger.capture()`, so the night lost its
permanent ledger entry and exited 3. Both judges recommended the canonical fix
(below, deferred to the next PR); judge 0 named this one the higher safety
priority.

**A replay from the real catalog** (`scratchpad/catalog-sim`, the real 22
October record, 988 bursts, published once a session for 30 sessions from a
copy of `docs/history` at 23 October): 988 bursts every session peaks at 131.8
MB, 98% of the cap, with no refusal under either rule; with a re-run every fifth
session the old rule refuses 5 nights, the first 9 November, and the new none,
the window ending at 13 sessions; one 2,500-burst day refuses 2 nights under the
old rule, the first 10 November, and none under the new.

**The rule.** Past either cap the records still inside their window give way,
oldest session first, then the earlier publication of a session, then the
digest, until tonight's fits; tonight's record never does, even when it is the
oldest (a backfill). Of the caps, only a record too large to fit alone refuses;
the evidence and identity checks refuse as before, and every refusal leaves the
old index and files. An evicted record is pruned as an expired one is: every
file in an owned directory goes (an interrupted write's `.tmp` included), a
directory already gone is already pruned, and one that cannot be removed is
named without stopping the others. A kept record's every file counts against
the byte cap. `_log_catalog()` states records, sessions and bytes against both
caps once a night, warns past `CATALOG_WARN_FRACTION` (80%) of either, and names
the sessions that gave way. `pipeline.retain_publication()` writes the catalog,
then captures the ledger whatever the catalog did, then fails the run (exit 3)
under its own stage, `history`; a clean night still ends at `email`.

**The review, worked.** A workflow by execution over `261d5337`, three lenses
and two skeptics a finding (23 agents, none errored), returned 8 distinct
findings. Upheld by every skeptic: the stage set to `history` on every night,
which made the recovery rehearsal's committed evidence stale and failed three
of its tests on CI (found by CI before the review; fixed in `302cf54e`); the
ordering tests passing on digest order (the record that must give way carried
the smaller digest, so an order by digest alone passed); the docs test's warning
clause matched by the evidence archive's paragraph; "only a record too large to
fit alone refuses" overstated (the evidence and identity checks still refuse);
the byte-cap test's precondition, which reduced to nothing; and the PR body's
"15 sessions" (16). Not upheld, both skeptics finding them identical on `main`:
a prune that stops at the first directory it cannot remove, after the new index
is written, stranding evicted directories unowned and uncounted (hardened here
anyway, since eviction now prunes directories inside the window); and a failed
restamp write (`reader.write_publication`) still skipping both the catalog and
the ledger -- the next instance of this class, an open lead.

**Measured** (this sandbox, Python 3.12.3): the full suite on `0c0b0c87`, run on
a committed worktree, 5251 passed and 34 environment-gated skips in 22 m 51 s
(5285 collected, the count line); the first full run, on `0ae36be4`, failed
the three rehearsal tests CI also failed, the stage defect above, and nothing
else. CI's Tests run on `302cf54e` passed whole (16:47-17:35 UTC). The replay
above re-run with the final `history.py` gives the same table. Two mutation
passes, each mutant judged by the whole of `tests/test_history.py`,
`test_quality_ledger.py` and `test_docs.py` in a detached worktree: 23 over the
eviction, the order, the caps, the log and `retain_publication()`, 21 dead at
once; **one survivor, a hole** -- an order by session and digest alone passed,
because the earlier of the two revisions also carried the smaller digest (the
test sets them against each other now, `7bf2dd46`, and it dies); and one
equivalent, the pipeline's fixture guard, since a pipeline record never
carries `fixture` (`load_previous()` refuses one). Over the review's prune
rules, 6 more (only `*.json` removed, a directory already gone counted as
stranded, the loop stopping at the first failure, the stranded directory
unlogged, a kept record's stray file uncounted, the prune raising) all dead.
The control survives every pass. gitleaks 8.24.3 over the branch's commits: no
leaks.

**Keep / fix / defer / omit.** Keep: a companion that cannot take tonight costs
that companion, never the night's ledger; the window shrinks under pressure and
says so. Fix if it bites: a failed restamp write after publication still skips
the catalog and the ledger. Defer: the canonical record's 32 MiB bound, the next
PR -- written compact (+48%: refused above about 3,530 bursts at today's
observations instead of 2,350), a log line against the bound, a refusal that
names the size, and one coherence test over every copy of the bound; the
misfiled failure notice (every post-preflight failure is mailed as
`coverage_thin`). Omit: a larger catalog cap as the fix.

**Not claimable:** a live night on which the catalog's cap binds; its
*Recovery catalog:* line is the first to read. Also not claimable: a morning or
research observation; any trading edge.

## Checkpoint, 24 Oct 2026 -- PR #196 accepted; the canonical record written compact and stated against its 32 MiB bound

**PR #196, accepted.** Merged as `29a7eaa0` on `main` with a merge commit over
`1e1ad24f`. The head `ae927027` passed all seven checks (Tests run
40117054923; both gitleaks runs). Publisher 40119482198 printed *Verified:
every one of the 48 public files matches committed main*; Pages 40119503623
deployed (40119481734 cancelled as superseded, as every merge does); the merge
commit's own Tests run 40119482205 and Secret scan 40119482199 passed. The first
night under the catalog rule is Monday 26 October's; read its *Recovery
catalog:* line.

**Revision.** Branch `claude/spicystock-market-data-vfd3o2` restarted from
`main` at `29a7eaa0`, pushed as **PR #197**. `docs/data.json`,
`docs/picks.json`, the compact reader, every receipt, the history, the evidence
objects, the quality ledger, the workflows, the fixtures and the vendored design
system are untouched; no rule moved, so `rules_version` stands; no run, mail,
dispatch, provider call or credential. No pinned source of the delivery proof
moved.

**What the bound did.** `reader.MAX_PUBLICATION_BYTES` (32 MiB) bounds the
canonical `docs/data.json`; the morning, issuer and stop-research readers, the
issuer publisher and the browser (`app-reader.js`) each hold the same number.
Past it `reader.derive()` refused the whole night after every paid call with
*reader transport bytes exceed bound*, naming neither the size nor the bound,
and no log line said how close a night had come. The record was written at
`indent=1`. The 22 October record (988 bursts, the most yet) was 19,092,277
bytes, 57% of the bound; the 23 October one 14,124,268. A refit over the 14
publications of 12 to 23 October (the read-only design workflow's: three
investigations, three designs, two judges) put an indented record past the
bound above about 2,430 bursts at that night's observations, near the design's
own estimate for a thrust day like 10 November 2022 (2,200 to 2,500 bursts).

**The change.** `report.write()` writes the record compact
(`separators=(",",":")`), keeping key order (which
`provenance._check_mechanical` reads), UTF-8 and the trailing newline: the 23
October record is 9,992,325 bytes compact, 29% less, and the 22 October one
13,738,612. Every digest over the parsed record is unchanged (evidence ids,
`rules_version`, the provenance hashes); only bindings over the file's own bytes
move, as they do on every new publication. The same fit puts the compact record
past the bound above about 3,600 bursts at 22 October's observations (+48%), and
the warning at about 2,700. `derive()` names the size and the bound when it
refuses (*canonical publication is N bytes, over its B-byte bound*).
`reader.log_publication()` states each night's record against the bound with
its bursts and observation bytes -- INFO, WARNING past
`PUBLICATION_WARN_FRACTION` (80%), ERROR past the bound with what the refusal
does -- and never raises; the size line survives counts it cannot read. Page
fixtures stay indented: `tools/make_fixture.py` re-serializes the pipeline's
record, labelled and its two run clocks zeroed, for reviewable diffs, so the
compact format is held by the pipeline's own tests, not by `--check`.

**The restamp after delivery** (found by the review). `restamp()` rewrites the
record after the mail -- `run.email` *skipped* to *delivered* adds two bytes, a
mail failure adds a problem -- through `reader.write_publication()`, after the
first record was installed. A record that crossed the bound there failed the run
at stage `email` with the first record installed, and skipped the recovery
catalog and the quality ledger. `pipeline.finish_publication()` now runs the
restamp, the research companions and retention in that order: a refused
restamp leaves the record first installed, which the catalog and the ledger
then retain from disk, and the run fails (exit 3) under its own stage,
`restamp`. The restamp is logged in its own words (*Canonical record after
delivery:*). The failure notice still carries its fixed missing-inputs sentence
for every post-preflight failure, not the size (the open lead from #196).

**The review, worked.** A workflow by execution over `0ac00dee`, three lenses
(the consumers of the bytes, the bound, the documents) and two skeptics a
finding, 23 agents, none errored. The consumers lens found nothing: no reader
splits, greps or offsets the record. On a tree with the 23 October record
rewritten compact and its companions re-derived, the full suite passed (5,266),
1,497 page checks over production passed, the publisher verified 48 files,
provenance gave PASS on both forms, three study tools gave byte-identical output,
a transition night (an indented record, then a compact one) published and bound,
and every fixture generator reproduced with nothing regenerated. The bound lens
returned three, all upheld: the restamp above; the refusal test held three files
in an empty directory, so a refusal moved after the evidence prune and write
passed it (the test publishes a night first, holds every file under `docs/` to
its bytes, and the refused night re-runs on a revised bar that brings evidence
objects of its own, held before it is asked); and the log line dropped the size
when a count could not be read. The documents lens returned seven, six upheld:
the restamp sentence again; "every size quoted above is indented" was false of
the compact `reader.json` and sidecar sizes; the paragraph said both "written
compact" and "the canonical record is unchanged"; "indentation was a third of
the file" (whitespace was 29%, newlines and indentation 26%); README still said
the fixtures are what the pipeline writes; and "one number every reader holds"
when several readers hold no bound. The seventh, that the refusal is mailed as
missing inputs, was not upheld (the base mails the same; README now says so).
The bound lens's own mutation pass killed fifteen mutants over the first commit
with two controls green, the evidence-order mutant its one survivor.

**Mutation pass over the fixes**, each mutant in a detached worktree judged by
`tests/test_publication_bound.py` and `tests/test_report.py`: the refused restamp
propagating, not logged, its stage unnamed, given the first write's tail, skipping
retention, or not a failure; the counts inside the size's `try`; the warning
fraction ignored; the refusal moved after the evidence write. Eight died at once;
**the last survived the first test** (night two's evidence objects were night
one's) and dies under the revised bar. The control (a docstring word) survives.

**Measured** (this sandbox, Python 3.12.3): the full suite on `2cb5f609`, run on
a committed worktree, 5269 passed and 34 environment-gated skips in 22 m 06 s
(5303 collected); `tests/test_publication_bound.py` (17) and
`tests/test_report.py` 149 passed; the docs test holds README's bound sentence
and 80% to the module. CI on `2cb5f609` (Tests run 40122196236): page and the
gate passed, both gitleaks runs passed; pytest and the native cases are
recorded on PR #197. The design workflow measured, read-only: gitleaks 8.24.3 over
the 22 and 23 October records finds the same rule keys in both forms without the
allowlist and none with the repository's config; git packs three consecutive
records 17% smaller compact (2,910 against 3,520 KiB).

**Keep / fix / defer / omit.** Keep: one bound, one number, held by every copy;
the restamp never costs the night's retention. Fix if it bites: the 80% warning
predicts nothing for a one-night spike (an ordinary night sits at 25 to 41%);
it is the slow term, observations, it watches. Defer: the failure notice's
fixed sentence; a thrust past about 3,600 bursts still refuses the night, and
clearing that needs the per-burst evidence factored out (about 1.15 KB of
constant check fields a burst) or a larger bound. Omit: a larger bound as the
fix.

**Not claimable:** the first compact night -- Monday 26 October's: read its
*Canonical record:* and *Canonical record after delivery:* lines, and confirm
`docs/data.json` is one line and `reader.json`'s `canonical.bytes` equals its
length. Also not claimable: a morning or research observation; any trading
edge.

## Checkpoint, 24 Oct 2026 -- PR #197 accepted; the failure notice names the stage it stopped at

**PR #197, accepted.** Merged as `0e68a112` on `main` with a merge commit over
`29a7eaa0`. The code head `2cb5f609` passed all seven checks (Tests run
40122196236: pytest 18:45-19:08 UTC, page 18:45-19:02, the gate, the native
stress case to 19:06 and central to 19:20; both gitleaks runs); the final head
`a45d215a` (CLAUDE.md alone over it) passed pytest, page, the gate's docs-only
decision and both gitleaks runs on run 40123887099. The diff touched nothing
under `docs/`, so the publisher did not fire, correctly (as at #64, #174 and
#177); Pages 40126002916 deployed and the merge commit's own Secret scan
40126003534 passed; its Tests run 40126003532 passed (19:35-20:05 UTC; the native cases skipped by
the gate, as a merge's are). The first compact night is
Monday 26 October's.

**Revision.** Branch `claude/spicystock-market-data-vfd3o2` restarted from
`main` at `0e68a112`, pushed as **PR #198**. Nothing under `docs/` moves and
no rule moves (`rules_version` stands, no fixture regenerated); no run, mail,
dispatch, provider call or credential. `.env.example` was read: nothing here is
configuration.

**What the notice said.** `pipeline.notify_failure()` mails the failure notice
for a run that stopped after preflight with nothing published, and it appended
a `coverage_thin` problem to every one, so every such mail said *Some inputs
were missing, could not be evaluated or arrived late*. Reproduced through the
doubles: a night refused at the canonical bound (stage `publish`) and a planner
crash (stage `grade`) were both mailed that sentence, the same one a real feed
outage gets (stage `session`, *insufficient usable coverage*). The record and
the page never see the notice; only the mail was wrong.

**The rule.** The notice names the stage the run stopped at, a word from
`report.NOTICE_STAGES` -- the inputs' stages and every one after them up to
`publish`, the stages a run can stop at with nothing published --
(`report.RUN_STAGES` is held by `tests/test_docs.py` to the stages
`run_evening()`, `finish_publication()` and `retain_publication()` set, in
order), and leaves what the run raised to the workflow's run log; the mail
quotes no free text, as before. A stop in `report.INPUT_STAGES` (`universe`,
`fetch`, `session`) is mailed the missing-inputs sentence for that failure; a
stop after them says those stages had passed and claims no cause, since a later
failure can be the code's or the data's. Problems recorded earlier in the night
go out as recorded, so a stale night that then crashes is mailed both. Preflight
mails nothing and a run past `publish` mails the digest, so neither is named.

**The review, worked.** A workflow by execution over `47faf34f`, two lenses
(whether a stage tells the truth about inputs; tests and documents), one
skeptic a finding, nine agents, none errored: seven findings, all upheld, each
reproduced here before it was touched. The medium one: a stage is a proxy -- a
whole night of truncated history (every frame six bars) passes the input stages,
which test only the session bar and the one before it, and fails at `breadth`
(*a 10-session ratio needs 10 days*); an `inf` close twenty bars back fails at
`publish` (*candidate facts differ from source bars*). The first version mailed
both "after the night's inputs were read" and commented that a failure after
them is not a missing input, which said more than the code knows; the old notice
had mailed them the inputs sentence, which was true there. The notice now claims
no cause past the inputs' stages. The lows: `preflight`, `email`, `restamp` and
`history` were given the after-inputs sentence (only `NOTICE_STAGES` are
printed now); README and the comments said the inputs sentence comes "only"
from an input stage when an earlier recorded `coverage_thin` is mailed too
(said so, and a test holds the two together); and a report assertion could not
fail for the rule it named (the report test now holds only what the report
owns). Recorded, not fixed: the ledger's own reconciliation runs at `session`
and again at `watchlist`, so the same fault is mailed the inputs sentence at
one and the stage sentence at the other; both say true things.

**Mutation passes**, each mutant in a detached worktree judged by
`tests/test_report.py`, `tests/test_publication_bound.py`, `tests/test_docs.py`
and the three notice tests in `tests/test_pipeline.py`: over `47faf34f`, twelve,
ten dead at once and **one survivor, a hole** -- a notice that adds a problem
nobody recorded passed, because no pipeline test read the problems block of a
crash with none (it reads *No problem was recorded before it stopped.* now);
the control survived. Over `fe1bb2ef`, sixteen -- the inputs sentence on every failure and never,
earlier problems dropped, the stage not passed at either hand-off, any owned
word or any word printed, the notice stages from `preflight` or past
`publish`, every stage an input stage and none, `session` not one, `history`
dropped from the stages, the stage line not rendered, a problem nobody
recorded, the passed stages unnamed -- all dead in the test naming their rule;
the control (a comment) survives.

**Measured** (this sandbox, Python 3.12.3): the full suite on `961a913c`, run on
a committed worktree, 5273 passed and 34 environment-gated skips in 21 m 41 s
(5307 collected); the touched files and the three notice tests 200 passed. CI
on the pushed head is recorded on PR #198.

**Keep / fix / defer / omit.** Keep: the mail names a stage the code owns and
never quotes what was raised. Fix if it bites: the input stages accept a frame
whose session bar and the one before it are readable, so a night of truncated
history is refused at `breadth` with no cause named in the mail -- an input
acceptance rule for the bars breadth and the scans need is a strategy-adjacent
change, not this one. Defer: a link to the Actions run in the notice (the record
carries `run_id` only once published). Omit: quoting the exception.

**Not claimable:** a live failure notice under the rule; the first compact
night (Monday 26 October); a morning or research observation; any trading edge.

## Checkpoint, 24 Oct 2026 -- PR #198 accepted; the evening rehearsed on the merged storage rules; the whole dependency resolution pinned

**PR #198, accepted.** Merged as `446e9db1` on `main` with a merge commit over
`0e68a112` at 20:57 UTC. The head `6c197082` passed pytest, page, the gate and
both gitleaks runs (Tests run 40128351140, pytest to 20:35 UTC); the native
central and stress cases passed on the code head `961a913c` (Tests run
40128316388, to 20:56). The diff touched nothing under `docs/`, so the
publisher did not fire, correctly (as at #64, #174, #177 and #197); Pages
40132079280 deployed, and the merge commit's own Secret scan 40132079612 and
Tests run 40132079573 (pytest 20:57-21:14 UTC, page 20:57-21:15; the native
cases skipped by the gate, as a merge's are) passed.

**The evening rehearsed over every storage rule merged on 24 October.** A dry
run of `evening.yml` on `main` at `0e68a112` (run 40128552858, job
120975138958, dispatched with `dry_run` and `session` 2026-10-23) re-ran the 23
October session over the real archives in the runner's checkout, committing
nothing and mailing nothing, and exited 0 (`exit 0 (ok)`), the pipeline
20:10:28-20:13:35 UTC. 4,773 classified stocks; ACA stale, ending 22 October,
tolerated (1 within the limit of 47); 3,587 scanned, 493 reaction candidates;
two chart reads, both answered HTTP 200 (2 calls, 2 replies, 3,336 tokens
written to the cache, 3,336 read, 8,040 uncached, 1,388 output). The four
storage lines, each the rule's first reading on a real-size archive:
- *Canonical record: 10066399 of 33554432 bytes, with 493 bursts and 5915489
  bytes of observations.*, and the same after delivery (#197's compact record:
  30% of the bound; the published 23 October record, indented, was 14,124,268);
- *Reader observation archive: 16 of 84 objects, 86115379 of 134217728 bytes.*
  (#195's rule, 64% of its cap, no object given way);
- *Evidence archive: 13185 objects, 78218202 of 134217728 bytes; 1652 objects
  (7978559 bytes) no file under docs/ names were removed (git keeps them).* --
  to the object and the byte what #194 predicted from a copy of the same tree;
- *Recovery catalog: 21 of 84 records over 16 sessions, 94719417 of 134217728
  bytes.* (#196's rule, 71% of its byte cap, nothing given way).
Two warnings are the dry run's own and not faults: *Stop research publication
unavailable (ValueError)* and *Research outcomes publication unavailable
(ValueError)*, each `ValueError('production observations require a real
publication')`, which both companions raise for a dry run by design
(reproduced locally); the real nights write them (the 23 October publication
`cd239b20` updated both). A dry run captures no quality-ledger entry
(`quality_ledger.capture()` returns `not_applicable` for one), so the log has no
ledger line. The rehearsal says the four rules hold on today's archives; the
first real night under all four is Monday 26 October's.

**The full-history secret scan, read before it ran.** The 24 October retention
checkpoint named a future risk: the issuer collector commits SEC excerpts, which
the weekly scan reads over the whole history. gitleaks 8.24.3 with the
repository's config over every commit this sandbox's clone held (`--log-opts
--all`, 705 commits, 1.34 GB, the issuer bundles and receipts among them; the
clone is shallow, so this is not the whole of `main`'s history): no leaks. The
last weekly run that read the whole history (run 39245153189, 19 October, 669
commits) found none either. The risk stays a future one, until an excerpt
carries a detector-shaped phrase.

**Revision.** Branch `claude/spicystock-market-data-vfd3o2` restarted from
`main` at `446e9db1`, pushed as **PR #199**. Nothing under `src/` or `docs/`
moves and no rule moves (`rules_version` stands, no fixture regenerated); no
run, mail, dispatch, provider call or credential. `.env.example` was read:
nothing here is configuration.

**What PyPI could still change.** #190 held anthropic below 2 after 2.0.0
changed the API version under the evening; #194 held every direct requirement
below its next major in a test and recorded that their own dependencies were
not held -- `python-dateutil` resolves to 3.0.0 under pandas, where the morning
host pins 2.9.0.post0. Each workflow installed `pip install -r
requirements.txt`, so a release of any of the 36 packages under the eight
direct ones (pydantic under anthropic and alpaca-py, matplotlib under
mplfinance, python-dateutil under pandas, ...), or of a direct one inside its
bound, reached the next night with no change in this repository, and CI
resolved its own set at the hour it ran.

**The change.** `constraints.txt` pins the whole resolution: the 44 runtime
packages the evening's own runner installed in the rehearsal above (Python
3.12.15, pip 26.2.1, read off its *Successfully installed* line) and the five
the suite adds (iniconfig, pluggy, Pygments, pytest, PyYAML), 49 bare `==` pins
in canonical-name order; a clean Python 3.12.3 venv resolves the same 49, and a
constrained install of `requirements-dev.txt` installs exactly those 49 with
`pip check` clean. Every workflow step that installs `requirements.txt`
(evening, intraday, issuer-evidence, morning, source-recovery: eight jobs)
installs `-r requirements.txt -c constraints.txt`, and so does the README's
setup line; `requirements-dev.txt` carries `-c constraints.txt`, so `tests.yml`,
unchanged, runs the suite against the night's own runtime set, and pip reads
that path beside the file from any directory. `requirements.txt` carries no
`-c`: `requirements-host.txt` reads it and pins the morning host's whole set
(anthropic 1.15.0, pandas 3.0.6, python-dateutil 2.9.0.post0, so the suite does
not run the host's versions); the historical jobs install
`tools/requirements-historical*.txt`, which pin their direct requirements only
(13 pins; the second review's clean install of `requirements-historical.txt`
resolved 50, python-dateutil 3.0.0 among the 37 that float) and are left
alone. The pins need CPython 3.12 (numpy 2.5.4 and contourpy 1.4.0 require
it), which README's *Run locally* now says. The
header's re-resolve recipe prints the pins in the order the test holds and
removes its temporary file whether the install succeeds, fails or is
interrupted, under bash or sh: run in a clean CPython 3.12.3 venv its output
equals the 49 pins byte for byte, under dash and under bash; with the install
made to fail, and with a SIGINT sent to the process group mid-install, the file
is gone (the first recipe, under dash, left it).

`tests/test_requirements.py` holds the file:
- each line a bare pin, once, in canonical-name order, and a ranged, extra,
  marker or option line refused (a synthetic case each);
- every direct requirement pinned inside its own bound;
- the installed versions equal to the pins, so a machine set up some other way
  says so;
- the pins closed under their own `Requires-Dist`, walked from the roots with
  extras followed and markers read in `RUNNER`, CPython 3.12 on Linux x86_64,
  naming a dependency without a pin, a pin outside the range a root or a
  dependent asks and a pin nothing reaches -- over the real metadata, and over a
  synthetic tree that drives each of those ways;
- the walk reading `RUNNER` and never this machine's environment (a test moves
  `RUNNER` to Windows and the walk must follow), and `RUNNER` held to the
  workflows: every job that installs the runtime or the suite's set runs on
  `ubuntu-*` under `setup-python` at `RUNNER`'s Python;
- every pip invocation a workflow job or a README code block runs -- prose is
  not read -- with continuations joined, cut at `&&`, `||`, `;`, `|`, `&` and
  parentheses, comments and redirections dropped (`shlex` with
  `punctuation_chars`), a script handed to another shell as one word
  (`bash -c '...'`) read as well, and its words read by pip's own option parsers
  (`parse_command`, then the install command's `parse_args`, isolated from this
  machine's `PIP_*` variables and pip.conf), so every spelling pip accepts is
  read as pip reads it: clustered `-qr`, abbreviated `--constr`, the value of
  `--only-binary :all:`, a path to `pip3.12` with a general option before
  `install`. It installs no package or editable by name, reads only a file the
  test accounts for, and reads `requirements.txt` only with `constraints.txt`
  (`install_problems()`, a pure rule driven over synthetic installs as well as
  the real ones); words pip itself would refuse are named.

**The first review, worked.** A workflow by execution over the first commit
(`a431bf49`), three lenses (every install the repository runs, whether each test
can fail, every sentence) and one skeptic a finding, 22 agents, none errored:
19 findings, 15 upheld, each reproduced by its skeptic before it was touched.
No install was wrong: the constrained installs reproduce the pins exactly with
`pip check` clean, the `-c` line resolves beside its file from any directory
(a decoy `constraints.txt` in the working directory is never read), the host's
Docker build is unaffected, and an unconstrained resolve today gives the same
49, so the change is a no-op for every job today. What was upheld:
- *every workflow installs `-r requirements.txt -c constraints.txt`* was false:
  the historical jobs install their own file (found by all three lenses);
- the commit message said the test held *every install line*; it held only the
  ones that read `requirements.txt`, by one literal spelling a line, so a second
  job's install spelled `--requirement`, or continued onto a second line,
  escaped it, and it refused two edits pip accepts (a trailing comment on the
  `-c` line, the `-c` before the `-r`);
- nothing on Linux CI held the marker rule: reading this machine's environment
  in place of `RUNNER` left every test green;
- a docstring said the installed-versions test held in CI *only because* of the
  `-c` line, when today an unconstrained install gives the same set;
- the recipe's `pip freeze` lists typing-inspection before typing_extensions,
  so its output failed the order test, and a failed install left its temporary
  file in the repository root;
- the pins no longer install on Python 3.11, and README did not say 3.12;
- README and `requirements-dev.txt` said every pin was what the evening
  installed, when five are the suite's;
- the suite count line (two lenses), and the two sentences of the 24 October
  retention checkpoint that said the dependencies were not pinned and that a
  constraints file could hold them, which now carry a pointer here.
Not upheld: that the host's seven differing pins are this change's (they
predate it, and the files said so; the sentence above now says it plainly), and
that the provenance run being a dry run made *the night's own set* false (the
scheduled 23 October night, run 40045887700, installed the same 44 at the same
versions, unconstrained, read off its job log here).

**The second review, worked.** A workflow by execution over the fixes
(`b3c39de4`), two lenses (the tests, every sentence), a skeptic a finding:
14 findings, 13 upheld. The install reader was still a hand parser:
a general option before `install` (`pip --disable-pip-version-check install`)
or a path to pip (`/usr/bin/pip3.12`) was silently skipped, so an unconstrained
install there passed (medium); `-qr` and `--constr`, which pip accepts, were
refused, and so were `--only-binary :all:`, `--timeout 60`, a pipe and a
redirection; the README was read only on lines beginning `pip install`, so an
unconstrained `python -m pip install` passed; `os.path.normpath` turned
`tools/...` into `tools\...` on Windows. That is why the reader asks pip now
rather than imitating it. Also upheld: *pinned on their own* was false of the
historical files (both lenses); a `--constraint constraints.txt` line in
`requirements-dev.txt` broke four tests; two rules had no case that fails when
loosened (a separate-word `./requirements.txt`, the bare-pin rule); the closure
let a root pinned outside its own bound through; the recipe's temporary file
survived an interrupt under sh; the commit message called `tests.yml` a pinned
source of the delivery proof, which the 10 October checkpoint says it no longer
is; and the CLAUDE.md pointer named a checkpoint not yet written (this one).
Not upheld: that nothing holds `RUNNER`'s own values on Linux -- there the
machine's environment and `RUNNER` agree on every marker key the closure reads,
so the swap changes nothing.

**Mutation passes**, each mutant in a minimal copy of the files the test reads,
judged by the whole of `tests/test_requirements.py`.
- Over `a431bf49`: seventeen and a control, fifteen dead, **two survivors, both
  holes** -- the closure walked without comparing a dependency's range to its
  pin, or checking that every pin was reached, and the real metadata agreed with
  the walk either way; the walk became a pure function (`closure_problems()`)
  driven over a synthetic tree, and a third run killed all eighteen.
- Over `b3c39de4`: 39 mutants and five controls (edits pip accepts, which must
  stay green); 36 died in the test naming their rule. **Three survived, the same
  hole one rule over** -- the install check's own clauses were exercised only on
  today's compliant workflows -- and **one control died**: a
  `--constraint=constraints.txt` line in `requirements-dev.txt` was read as a
  requirement. Both fixed, and over `37845862` all 41 died with the five
  controls alive.
- Over the final tree (`943eaf8c`): 61 mutants and seven controls. All 61 died
  in the test naming their rule; all seven controls lived. The mutants: a
  transitive pin dropped, a stale one kept (and an installed one), a pin moved
  or outside its bound, the file unsorted, in pip freeze's order, a duplicate, a
  range, the bare-pin rule loosened; markers ignored or read on this machine,
  `RUNNER` at another Python or on Windows, a job on 3.13 or on Windows; extras
  unfollowed; a root's range, a dependent's range, the stale pins and an
  unpinned dependency unchecked; option lines read as requirements, or every
  option line skipped; general options unparsed, the install options read by
  hand, paths unnormalized, `PIP_*` variables read, pip.conf read, the caller's
  `PIP_CONFIG_FILE` not put back, a refusal read as nothing or not named,
  editables accepted; comments kept, redirections kept, the descriptor of `2>&1`
  kept, command lists uncut, continuations unjoined, a path to pip or `pip3.12`
  unread, a script handed to another shell unread, the README's prose read or
  the README unread; each install clause dropped; the reader blind to every
  workflow; and as data the evening, the
  README and the dev file without the constraint, a `-c` or `--constraint=` in
  `requirements.txt`, a second job's `--requirement` install, a clustered `-qr`,
  a path to pip with a general option, a continued line, a bare package, the
  host's file in a workflow, a README `python -m pip` line, a second quiet
  install, a `bash -c` line and a new `windows-latest` workflow on Python 3.13
  installing with a general option before `install`, each without the
  constraint. The controls: the dev file's `-c` before its `-r`, with a trailing
  comment, as `--constraint=` and as `--constraint` spaced; a workflow install
  as `python -m pip --disable-pip-version-check install --only-binary :all:
  -qr ./requirements.txt --constr constraints.txt 2>&1 | tee pip.log`; README
  prose naming an install; a comment. The long-spelled control first died for a
  reason of mine -- written into a plain YAML scalar, `:all: ` made the file
  invalid YAML, which GitHub would refuse too -- and lives written as the block
  scalar a step would really use.

**Measured** (this sandbox, Python 3.12.3): the full suite on `943eaf8c`, run
on a committed worktree, 5304 passed and 34 environment-gated skips in
21 m 21 s (5338 collected); `tests/test_requirements.py`, `tests/test_docs.py`
and `tests/test_workflows.py` 137 passed under `-W error::pytest.PytestWarning`;
actionlint 1.7.12 on the five changed workflows: clean; gitleaks 8.24.3 over the
changed files and the branch's commit with the repository's config: no leaks.
No record, rule or page file moved, so the fixtures, the chart check and the
smoke are CI's, recorded on the PR.

**Keep / fix / defer / omit.** Keep: a pin moves in its own change with the
suite run against it; the host's set stays its own. Fix if it bites: a pinned
package yanked from PyPI fails the next install loudly (a constraint cannot
install what the index no longer serves), which is the point; a security
release underneath waits for a change here. Defer: hashes (`--require-hashes`)
over every wheel, which would pin the bytes as well as the versions. Omit: a
bot that moves the pins.

**Not claimable:** the first night under the constraints (the first workflow to
install them after the merge); the first real night under the four storage
rules (Monday 26 October); a morning or research observation; any trading edge.

## Checkpoint, 25 Oct 2026 -- PR #199 accepted; the record the browser never downloads bounded apart from the files it does

**PR #199, accepted.** Merged as `d9e2e9c3` on `main` with a merge commit over
`39627bf0`. Its diff touched nothing under `docs/`, so the publisher did not
fire, correctly (as at #64, #174, #177, #197 and #198). Pages 40141038953
deployed. The merge commit's own Secret scan 40141038652 and Tests run
40141038602 (23:01-23:30 UTC on 24 October) passed. The first workflow to
install the constraints is Monday's morning dispatch or evening run.

**Revision.** Branch `claude/spicystock-market-data-vfd3o2` from `main` at
`d9e2e9c3`, pushed as **PR #200**. Changed:
- `src/reader.py`, with its copies of the bound in `src/morning.py`,
  `src/issuer_evidence.py`, `tools/publish_issuer_evidence.py` and
  `docs/app-reader.js`;
- `src/quality_ledger.py` (a log line and two refusal sentences);
- the tests and two browser suites;
- README, `.env.example` and the two operations documents.

No rule moved: `rules_version` stands and no fixture was regenerated.
`docs/data.json`, `docs/picks.json`, every receipt, the history, the evidence
objects, the quality ledger, the workflows and the vendored design system are
untouched. No run, mail, dispatch, provider call or credential. `.env.example`
was swept for the new bound.

**Why.** One 32 MiB number (`reader.MAX_PUBLICATION_BYTES`) bounded the
canonical `data.json`, which the browser never downloads, and `reader.json`, its
projection, which it does. The record carries the observation window the
projection defers to its sidecar, so the record reached the bound first. A
night over it was refused at `publish` after every paid call. On 22 October (988
bursts, the most yet) the record was 13.7 MB compact, the observations 5.9 MB of
it.

A read-only design workflow (wf_6c3ed3bc-a5d) compared three designs:
- (A) pack each burst and hydrate it in the browser;
- (B) shed the low-ranked bursts' detail into evidence objects;
- (C) split the bound.

It ran three measurements, the three designs and two judges. Both judges chose
C: no schema, identity or browser change.

**The rule.**
- **The record**, which only the readers of a publication read, is bounded at
  48 MiB. Its copies hold the one number: the morning, issuer and stop-research
  readers, the issuer publisher, and the browser, which holds it only as the
  size `reader.json` may name. The evidence archive's retention scan reads it
  whole under its own 64 MiB.
- **`reader.json` and its sidecar** keep 32 MiB each (`MAX_READER_BYTES`,
  `MAX_OBSERVATION_BYTES`).
- **`derive()`** asks the record's bound before it projects, then the sidecar's,
  then the projection's, each refusal naming the file's size and bound.
- **The run log** states every projection a record within its bound makes, in
  two lines (*Reader projection:*, *Reader observations:*), at the first staging
  and after delivery (`log_projection()`). It warns past 80% of either.
- **The quality ledger's** retained line states the entry (expanded) and the
  archive against their bounds, warning past 80% of any. A capture a bound
  refused names the sizes in its `quality_ledger_capture_failed` log line, and
  no other exception's text is quoted.

**The design point, and how far it reaches.** `tests/test_publication_ceiling.py`
builds it from the real 22 October publication (`fb70e706`, fetched by whole
id): every stock that night measured as scan-ready (3,581) bursts, and every
stock carries the window's whole history. Every stock and session holds the
record's own 1.237 signal identities for each stock and session that carried
one.

It is one chosen point, not the largest night that population can make: a
stock and session of that record carries up to four signal identities.

| at the design point | bytes |
|---|---|
| record | 46,640,227 (past the old bound) |
| projection | 27,351,450 |
| sidecar | 19,289,227 |
| ledger entry | 6,732,678 (with no scorecard rows or exception membership) |

The frozen record cannot see what the current code adds, so tripwires read
the regenerated `red.json` against what it was at `3ee0e427`:
- an unreviewed, unplanned burst, a funnel row, a signal, a history bar and a
  symbol entry, each added once an entry;
- the rules, added once;
- the ledger's candidate, once a burst;
- the rest of the record and of its ledger entry, as if it came once a burst.
  That overestimates anything written once a night; a fixed addition of about
  6 KB to the record's rest, or 3 KB to the ledger's, asks for a re-measure.

The headroom left a burst is 1,031 bytes in the record and 462 in the ledger
entry. The crossings are computed from the bytes each further burst appends,
and held to a real build at the burst before two of them:
- while every bursting stock keeps a full window, the record's bound is reached
  first, at 3,864 bursts;
- with 22 October's window held, the projection's is reached first, at 4,403,
  and the record's at 5,837;
- the ledger's 8 MiB entry is reached at 4,465 either way.

**Two reviews by execution, every finding reproduced here before it was
touched.**

*The first review*, over `fccb5ad0`, had four lenses: the tests, the consumers,
the words and the ledger. It returned 25 findings. 17 of its 50 skeptic
verdicts had arrived after about two and a half hours, every one upheld. The
run was stopped there and all 25 were reproduced and fixed (`3d819170` to
`f5614088`). They included:
- the sidecar's bound could now refuse a night before the record's, naming no
  size and writing no log line;
- the "full window" design point left 1,845 of its 3,581 symbols short, so it
  built 42,926,403 bytes where a full one is 46,640,227;
- the observation tripwire under-projected a signal's growth by half;
- no browser check failed by name when the download bound was raised: one suite
  hung to its timeout and the other passed for another reason;
- the count line;
- the morning report's 256 MiB read bound, and the sync's 30-second deadline
  counting only the transfer.

*The second review*, over `f5614088`, had three lenses and a completeness
critic. It returned 19 findings, 17 distinct, and its skeptics upheld every
one:
- the tripwires read five components, so a new per-candidate block anywhere
  else in the record (the way the funnel came on 11 October) moved nothing;
- the ledger entry, which copies each check's whole values, the reader block,
  the review selection and the gate, was not projected at all, and has less
  than half the record's headroom a burst;
- the README's crossings, density and the report's counts were held by no test;
- no test held the sidecar-first order;
- no test held the retained line's entry filter;
- nine sentences said more than the code. The ones that mattered: "the largest
  night"; a density called per stock and session that is per stock and session
  that carried one; a failure notice said to come with a ledger refusal that
  changes no exit; sizes said to sit beside a word that is only in the log; and
  a validation time naming no record.

Commit `fccb5ad0`'s message keeps two statements the review superseded. Its
42,926,403 is 46,640,227 from `3d819170` on. And it says "app-reader.js moves
to 48 MiB": only the size `reader.json` names moved; every download stays at
32 MiB.

**Mutation passes**, each mutant in a detached worktree and judged by the whole
test files naming its rule:
- over `fccb5ad0`: 28 mutants, all dead, both controls alive;
- over `3d819170`: 19 mutants; 16 dead and three survivors, each a hole:
  - a signal tripwire measured without its key;
  - a projection that ignored funnel rows;
  - bars counted as symbols.
  All three die at `f5614088`;
- over `8cd1591e`: 17 mutants over the second review's rules -- the
  sidecar-first order, the retained line's filter, the ledger left out of the
  fits, each tripwire's landing and spread, the crossing arithmetic, two data
  mutants in the fixture (a 600-byte check value, a per-candidate run block)
  and three documents. 16 died at once, with **one survivor, a hole**: the
  signal arithmetic shifted one index late passed, because at 3,863 bursts the
  two entries the shift trades are both 152 bytes, so the real build there
  could not see it, though the shift moves 136 of the 282 steps before it (the
  second shape this file names). Every step to the crossing is now held to the
  real build's own entries (`360e9190`), and the shifted arithmetic dies at the
  first step it moves. Of the three controls, one first failed for a harness
  defect of mine: it wrote its 2 KB under the test's own `added_by_a_later_build`
  key, which the tripwire's mutation then overwrote. Under a key of its own it
  survives, as do the other two (a comment in `reader.py` and in
  `quality_ledger.py`). One README mutant first missed its anchor on a line
  break; re-run, it died.

**Measured** (this sandbox, Python 3.12.3): the full suite on `8cd1591e`, run
on a committed worktree, 5349 passed and 34 environment-gated skips in
22 m 06 s (5383 collected, the count line); `360e9190` added assertions to one
test and no test, and `tests/test_publication_ceiling.py` and
`tests/test_docs.py` 68 passed on it. CI on `f5614088` passed all
seven checks (Tests run 40152946712: pytest, page, the gate, the native central
and stress cases; both gitleaks runs). The browser's reader suite is 125/125 and
the publication-recovery suite 138/138.

**Keep / fix / defer / omit.**
- *Keep:* the record's bound is one number every reader of the record holds,
  and the browser downloads nothing over 32 MiB.
- *Fix if it bites:*
  - At the design point the morning journal keeps at most 23 publications in
    its 1 GiB, their receipts and events sharing it, and a report reads at most
    five. Revisit both before the host runs across a thrust stretch.
  - A 27 MB `reader.json` is what a phone downloads on every load at the design
    point.
  - The ledger's 8 MiB entry is the next bound a growing night reaches (4,465
    bursts, fewer with a night's scorecard rows).
- *Defer:* the two options that would give the record more room per burst:
  factoring out each burst's constant check fields (about 1.15 KB a burst), and
  compacting the observations.
- *Omit:* a larger bound for the files the browser downloads.

GitHub's 50 MiB push warning was read off search excerpts only.

**Not claimable:**
- a night past 32 MiB, or Pages and the publication gate serving one;
- the undeployed morning host syncing one;
- Monday 26 October's first real night under the storage rules and the split
  bounds. Read its *Canonical record:*, *Reader projection:*, *Reader
  observations:*, *Evidence archive:*, *Reader observation archive:*,
  *Recovery catalog:* and *Quality ledger retained:* lines;
- any trading edge.

## Checkpoint, 30 Oct 2026 -- PR #201 accepted; the first YELLOW week read; request v3 shows the reader each criterion's checks

**PR #201, accepted.** Mo merged it as `ed5b400c` on `main` at 13:42 UTC on
27 October, a merge commit over `d383e9c5` (the source-recovery receipt that
followed the 26 October publication). Its
head `7dd49f1a` had all of its checks complete green (the check-suite event
of 25 October). Its review workflow (`wf_d51f5765-0b6`) lost 18 agents to the
session's weekly usage limit. Its one upheld finding -- README's XSL form
list -- is carried by PR #202: the list now names the forms exactly as the
25 October probe counted them, and the claim that the rerun read the same
index bytes cites both job logs' digests (AAPL `5891cf87…`, ZIM `7d822c20…`).

**The first production collections under the XSL rule.** The issuer receipt
committed at 13:44 UTC on 27 October (`000bc057`) was the first after the
merge. It read ZIM's index `observed_window`: 100 metadata rows, no error. The
01:33 receipt the same day (`d3a2f5c4`) had read `partial` on
`metadata_invalid` with 35 rows. After that:
- EXEL (107 rows) and OGN (88) on 28 October, OGN (88) on 29 October and PSNL
  (92) on 30 October all read `observed_window`.
- MCS (94 rows, 29 October) and QGEN (24 rows, 30 October) still read
  `partial` on `metadata_invalid`, for a reason the job log's per-issuer line
  does not record; the probe has not been asked about them. Not worked here.

**The nights of 26 to 29 October, read off `main`.** Runs 40432684287,
40614157533, 40802470870 and 40988674329. Each published after both slots and
before the next open, 303 to 341 minutes after completion, and each delivered
its mail.
- 26 October was RED (10-session ratio 0.87) and `ok`.
- **27, 28 and 29 October were YELLOW** (ratios 1.13, 1.64 and 1.50), the
  first YELLOW nights since 12 October. Each was `degraded` on `claude_partial`
  and nothing else. The stale tails (17, 18 and 14 stocks) were tolerated, none
  of them on the seed alone.
- The reader refused every A+ name it was asked to read: WST (27), IBM (28),
  AEE, BSY and TTEK (29). Every reply was a downgrade to B or C. Of these, only
  BSY and TTEK were account-feasible (purpose `opportunity`). WST, IBM and AEE
  were research reads blocked by `no_whole_share`. Other A+ names were never
  reviewed (`preview_sizing`).
- **The anticipation list published tickets on all three nights:** EXEL 1 and
  OGN 22 shares (for 28 October), OGN 22 and MCS 2 (29 October), QGEN 1 and
  PSNL 4 (30 October). These are the first tickets since ZIM on 9 October.
- The 29 October record's model plans:
  - EXEL filled at 09:40 ET at the $65.65 trigger, placed by minute bars, and
    holds;
  - OGN was not filled either day; on 29 October its minute bars put the
    trigger at 11:00 ET, after the window;
  - MCS is uncertain, having opened above its limit and traded back under it.

  These are model plans, not anyone's trades.
- **The storage lines, read off the four job logs**, held on every night:
  - canonical record 9.96 to 12.32 MB of its 48 MiB bound;
  - reader projection 4.1 to 6.2 MB of 32 MiB;
  - evidence archive 78.2 to 80.4 MB of 128 MiB, removing 401 to 1,652 unnamed
    objects a night;
  - reader observation archive 86.0 to 103.9 MB of 128 MiB (77%; the dry runs
    of 30 October warned at 110.2 MB, past 80%);
  - recovery catalog 90.8 to 97.6 MB over 16 sessions;
  - quality ledger entries 0.97 to 1.50 MB of 8 MiB.

**No morning check ran for any of those tickets.** There has been no
`workflow_dispatch` of `morning.yml` since 23 October.
- The owner's claude.ai task fired every weekday. Its session answered 27, 28
  and 29 October with the account's weekly usage limit.
- On 30 October its GitHub connection timed out (`CONNECT_TIMEOUT`, twice).
- GitHub's own morning crons were created 18:38 to 20:02 UTC each day, five to
  six hours late, and each guard refused them as past the window.

The in-window count for #111 stays at one (23 October). The delivery choice is
the owner's; this records what it did.

**What the refusals were.** `tests/fixtures/grading/reader-authority-refusals/`
freezes every retained reply that reader authority refused. Its `build.py`
reads every schema-2 publication through `13b4da23`, read-only over git, and
pins the commit it read through. That gives 30 replies over 28 name-nights in
18 sessions, 23 September to 29 October, and every one is a downgrade. Three
groups:
- **3 cited a path `reader_evidence` does not carry**: HAE twice and TTEK,
  citing `burst.*` or `flags`.
- **23 cited a real check their criterion does not list**:
  - `overhead_supply` citing `checks.Y`, `checks.L` or `checks.RE` (9; TTEK's
    is a tenth, counted with the three above);
  - `extension` citing `checks.C` or `checks.RE` (8);
  - `trend_maturity` citing `checks.C` or `checks.L` (6 findings).
- **4 named a `measured_quality` defect on a candidate whose eight checks all
  recorded PASS**: INGN, JAKK, MSM and RVTY. There was nothing to cite.

In 26 of the 30, the reply's other findings alone would have carried the
downgrade.

**Request v3, and the design the API refused.** The first design made each
finding one `anyOf` branch per criterion, each with its own path enum, so the
schema itself would have excluded 26 of the 30. The dry run of `93fde91f`
(run 41120821225, session 29 October, nothing committed) was answered
"The compiled grammar is too large" (HTTP 400). #192's rule stopped after two
calls. No offline test could see that: llguidance compiled the same schema at
about 1.6 times version 2's lexer size, so the API's compiler and its limit
are not llguidance's. **What shipped:**
- One finding shape, as in version 2, but `path` is an enum of the 39 paths
  `reader_evidence` carries (`EVIDENCE_PATHS`, over `CHECK_VALUES`).
- The instruction names each criterion's checks, says one citation outside its
  criterion refuses the reply, and says no FAIL/PARTIAL means no
  `measured_quality` finding.
- `validate()` is unchanged.
- `REQUEST_VERSION` is 3, and `rules_version` moves.
- The verifier rebuilds a record's reader requests under the version it
  archived. `FINDINGS_SCHEMA_V2` and `instruction(2)` are kept byte for byte and
  pinned by SHA-256. `provenance.replayable_request_version()` admits int 2 or
  3, and any other version is partial. Without this, the bump would have made
  every version-2 publication fail the readers that require PASS: morning,
  stop-research, research-observation and issuer.
- Of the 28 publications that archive request v2, 19 verify PASS with full
  source replay. 9 stay PARTIAL as on `main`, on
  `plan.allocation_policy`/`watchlist.min_compress`. None changes status.

**The dry runs of the shipped design** (session 29 October, the same four
names as the live night). Run 41124967933 at `3b7ae4cc` returned 4 × HTTP 200,
and **all four reviews were accepted**, against 1 of 4 under v2 on the live
night. Run 41128246793 at `4e72a4b9`, with the final instruction (the request
`fb0edfef` sends is the same), did the same: 4 × HTTP 200, all four accepted.
One night and four names is not a rate.

**The review, worked.** `wf_fb57ef00-177` ran three lenses over `93fde91f`,
with one skeptic per finding.
- The safety lens re-ran all 28 version-2 publications on the base and the
  head: no status moved. Forcing version 3 onto a version-2 record broke its
  replay with 12 mismatches, as it must.
- The words lens returned 10 findings, all upheld:
  - README called a v2 record partial;
  - "every v2 publication verifies PASS";
  - the measured-defect four;
  - "every candidate the band would have planned";
  - the per-criterion counts;
  - "no branch offers";
  - the uncited same-bytes claim;
  - "constants" for enums;
  - the misplaced `SCORE_SCHEMA` comment;
  - `docs/provenance/README.md`.

  Each is fixed, except the two that live only in a pushed commit message,
  which are corrected in the PR.
- The tests lens ran 46 mutants. Four survived, each a hole, and all four are
  closed (`fb0edfef`) and die in the test named for their rule:
  - the citation key-set rule;
  - the int clause;
  - `REPLAYABLE_REQUEST_VERSIONS` against what can be rebuilt;
  - `CHECK_VALUES` against `quality.assess()`.

A second review (`wf_42bc8805-dfd`) read the final design at `a2e83065` with
two lenses. The words lens returned 9 findings, every one fixed: the XSL
directory, "most" visual, the measured-defect four, the source of the
instruction's list, a test comment and name, #201's merge parent, the 9 of the
23, and MCS/QGEN. The tests lens ran 47 mutants and found 2 real holes, both
closed: the instruction's per-criterion list is now parsed whole (an extra check
on a criterion passed the substring test), and request version 3 is pinned by
SHA-256 beside version 2, since production records carry it from the merge on.
Each new test's mutant dies in it; a control survives.

**Not claimable:**
- a live night under request v3;
- that the acceptance rate holds;
- a morning check for any of the week's tickets;
- any trading edge.

## Checkpoint, 31 Oct 2026 -- #202 to #205: the first night under request v3, the probe that names its issuers, a Railway build, and the SEC rows the collector only counts

**#202, #203 and #204, accepted.**
- **#202** (request v3) merged as `0a995dd7` at 23:26 UTC on 30 October. Tests run 41144514304 on that merge passed.
- **#203** merged as `184e1578`, from head `0f247bba`, which passed all seven checks on Tests run 41146630460. It gives `issuer-evidence.yml` a `probe_tickers` dispatch input: up to four distinct tickers in SEC's hyphen spelling, passed through the environment to `tools.probe_sec_access --tickers`; anything else is refused whole, with exit 2, before any request.
- **#204** merged as `053e1c64`, from head `adcfe7b9`, which passed all seven checks on Tests run 41153040747.

**#204: the Railway build.** Railway refused the first deployment of the morning host on 30 October (23:5x UTC). The message, in full: "The Dockerfile failed validation. Please check the build logs for more details."
- The `Dockerfile` had mounted an optional `proxy_ca` BuildKit secret (`RUN --mount=type=secret`) and carried a syntax directive.
- What Railway refuses was read only in search excerpts:
  - its forum quotes its builder refusing a secret mount, and a staff reply that secret mounts are not supported;
  - its Dockerfile documentation requires a cache mount's id to carry the service's own id.
- The image now installs `requirements-host.txt` with a plain `RUN` and its normal trust store. Nothing else in the image moves.
- `docs/operations/morning-railway.md` gives a local proxied build a bind-mount recipe. Built here (Docker 29.9.2, buildx 0.38.1):
  - it installs the 45 host pins;
  - no trace of the proxy certificate appears in the exported filesystem, the history or the provenance;
  - it refuses to start with no volume;
  - on a bind-mounted ext volume, `/healthz` answers 200 and `/morning.json` answers 503.
- `tests/test_host_dockerfile.py` reads the file as Docker does: comments are dropped before continuations are joined, and a byte-order mark is stripped. It holds the file to: no `RUN --mount`, no syntax directive or build secret, no `VOLUME`, the exact install line, and the supervisor entrypoint.
- Two reviews by execution. The second ran 17 agents, none errored. Neither found an image defect. Seven low findings were upheld and fixed: the two test-reader holes above, a misdated refusal, a misattribution, a test's name and two PR-body errors.
- **Not claimable:** that Railway builds it. Mo deploys from `main`; `/healthz` on the service's domain is the first reading, and the page's `spicystock-morning-endpoint` meta tag stays empty until that endpoint is verified, in a reviewed change of its own.

**The 30 October night, the first under request v3.**
- Run published `e4063d25`. RED: down 4% count 490, against an alarm of 385.8. No ticket.
- `run.reads` 1 of 2: CLMT's reply was refused by reader authority. The refusal floor (#182) tolerated it (`verdict` `tolerated`, `refusal_limit` 1), as it had on 19 and 20 October.
- `run.reader_usage`: 2 calls, 16,973 input and 1,254 output tokens.
- `degraded`: `run.input_tolerance` read `not_tolerated` on `other_exceptions`. 16 stale stocks, all ending 29 October, within 47; but one stock was missing the previous session, a gap the tolerance does not cover. Not worked here.
- `run.delivery`: 319.7 minutes after completion, after both slots, before the next open.
- One night and two names say nothing about request v3's acceptance rate.

**The probe, with issuers named.** Run 41149821846 on `main` (`184e1578`) with `probe_tickers: "MCS QGEN"`. SEC answered all 3 requests.
- MCS: one row of its recent index was refused on `primary_document`, an SC 13G/A naming `marcus.corp..txt` (96 admitted rows fell in the window).
- QGEN: six rows were refused, all SC 13G or 13G/A: three named a doubled-dot document, three named none (24 admitted rows fell in the window).
- QGEN's index was byte for byte the one its 30 October collection read (`98c75f54…`). MCS's had changed since 29 October (`54e41963…`, 151,981 bytes, then; `e3505edc…`, 151,744, on the probe). So for MCS the cause is inferred, not observed.

**#205: count an unnamed row of a form the collector never stores.**
- **Design.** A read-and-design workflow (`wf_340ec2f8-085`) ran four readers, three prototyped designs and two judges by execution. Both judges chose the narrowest design.
- **The rule.** `issuer_evidence._unnamed()`, beside #201's `_rendered()`, counts such a row for a form outside `FORMS` and `ACQUISITION_FORMS` whose document is empty, or one name the basename rule refuses only for its doubled dot.
  - The row is held to every other row rule by a fixed name, and is never read, listed, linked or fetched.
  - `_basename`, `_filing`, `_sec_url` and every validator are unchanged.
- **Duplicate accessions.** Where SEC lists one accession more than once and the copies differ, an unnamed copy is refused wherever it is read and the named copy is kept. Two differing unnamed copies are both refused.
  - A refused copy counts as one invalid row of its file, and its date is not in the range.
  - An unnamed copy beside a copy in its own file that the row rules refuse is refused too.
  - Two differing named copies still refuse the recent index, or the history file when both are in the window, as before; a refused history file is not read, so its copies refuse nothing.
- **The reason sentence.** An index that is partial only on `metadata_invalid`, and whose range reaches the window, carries `REFUSED_ROWS_REASON`, not the missing-history sentence.
- **The page** printed every index reason with two full stops; it now strips the reason's own.
- **The probe:**
  - names an unnamed copy under `unnamed_twin`, from a walk written apart from the collector's;
  - prints each refused row's filing date;
  - its artifact schema is `spicystock-sec-probe-v3`.
- **The branch probe** (run 41158793431) read the same index bytes. It parsed MCS and QGEN with no row refused and the same rows in the window (96 and 24), so every formerly refused row was older than the window.
- **Review.** A review by execution over `b3da391f` (`wf_65ff82b2-be2`, four lenses, two skeptics per finding):
  - One behaviour defect was upheld by both skeptics: across the recent index and its history file the first version kept an unnamed recent copy over a named history copy. That could drop an acquisition form `main` listed (implausible in real data).
  - Upheld and fixed with it:
    - an out-of-window refused history copy stretched the range;
    - the two-unnamed-copies order dependence;
    - two test holes (which copy is kept across files; the probe's printed value for a twin);
    - the probe's docstring and schema version;
    - five wording errors, including the MCS bytes.
  - Not upheld, by either skeptic: a case or whitespace variant of a stored form (`8-K `) being counted. The PR keeps the exact form sets the collector lists by.
- **A second review over `0a09a635`** (`wf_71287756-50b`, two lenses, two skeptics a finding) ran an 800-case recent/history fuzz on both commits and an independent oracle of the stated rule; both matched, and the probe agreed with the collector on 1,811 random in-file indexes. Upheld by both skeptics and fixed:
  - when every row of both files is a refused copy, the range kept the refused recent copy's date; it is unknown now;
  - an unnamed copy beside a copy the row rules refuse was counted (main refused both); it is refused now, and the probe names both;
  - five wording errors (this checkpoint's MCS "1 of 96" and "first live use" among them).
- **Mutation pass over the fixes,** each mutant in a detached worktree, judged by the two issuer test files: eleven mutants, each dying in the test named for its rule, and a comment control surviving.
  - The mutants: both in-file clauses, displacement, refusal, the range, out-of-window twins, the recent error, the probe's walk, its twin rule, its filing date, and the reason.
  - On the page, reverting the full-stop fix fails 8 of the issuer suite's 645 checks.

**Not claimable:**
- that MCS or QGEN read `observed_window` in production: the next collection with them as candidates shows it;
- that Railway builds the image;
- request v3's acceptance rate;
- a morning check for any ticket;
- any trading edge.
