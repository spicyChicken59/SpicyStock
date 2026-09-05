# SpicyStock — working notes

A daily US-equity screener implementing the Stockbee/Qullamaggie 4% Momentum
Burst strategy. Scan → 2LYNCH checklist → chart render → Claude scores the
survivors from metrics plus a chart image → ranked email. Runs as a GitHub
Actions cron.

This project was inherited from another author and is being rebuilt in ranked
steps. Treat the code as evidence and the prose as suspect until checked.

## Standing rule: every step sweeps the docs

`README.md` and `.env.example` state specific facts about thresholds, failure
modes, data feeds and schedules. Several are true only until a later step lands.
**A step is not done until those two files are correct for the code as it now
stands.** This is part of every step's definition of done, not a cleanup task
for later.

Known scheduled falsifications:

| when this lands | what goes stale |
|---|---|
| ~~Step 3 sets `feed=` on the bars request~~ done | ~~`.env.example`'s "no `feed=` is set anywhere"~~ swept, along with the IEX-default paragraph it sat in |
| ~~Step 4 replaces the 5,000,000-share floor~~ done | ~~`.env.example`'s absolute-floor note, README's Layer-1 filter description and Costs volume numbers~~ all swept |
| ~~Step 5 makes failures loud~~ done | ~~`.env.example`'s "these fail in three different ways" block~~ swept |
| ~~Step 6 fixes the test suite~~ done | ~~the `detect_burst` comment in `.gitignore`, the broken-test note in README~~ swept |
| ~~Step 9 emits `docs/data.json`~~ done | ~~the "hand-authored fixture" caveat in README's dashboard section~~ swept — the committed copy is still the fixture and says so in `run.fixture`; the pipeline writes the real one |
| ~~The first commit-back replaces `docs/data.json` with a real run~~ swept before it happened (3.1) | ~~`check_fixture_fresh.py` compared `docs/data.json` to the generator, so the pipeline working would have turned CI red on the next push; README's "regenerate … `docs/data.json`" and "pinned to the fixture" smoke-test section~~ — the canonical fixture is `tests/fixtures/data.json` now, `docs/data.json` is whatever the last run wrote, and the guard only checks a `docs/` copy that still *claims* to be the fixture |
| ~~`evening.yml` keeps `docs/` between runs~~ done in step 9 | ~~README's "Does the history actually accumulate?" section and the stale `charts/` path in that workflow's upload step~~ both swept; step 10 added why that commit-back now also feeds the morning run and every streak |
| ~~Step 10 makes the mode mean something and reads the ledger back~~ done | ~~README's "morning has no workflow and no distinct behaviour" note, the workflow inventory, `.env.example`'s required-variable list~~ all swept; `morning.yml` now exists |
| The universe widens past `data/symbols.txt` | **TWO STRATEGY RULES, not just prose.** (a) Rule 4, "not a biotech stock", is enforced by nothing but the curated contents of that file — `detect_setup(df, cfg)` never sees a ticker — so replacing it DELETES a named rule with the suite green. (b) The dollar-volume percentile is feed-invariant but NOT universe-invariant: measured on log-normal populations of the shape US dollar volume has, 230 curated names put the 30th percentile at $359M/day and 3,000 all-cap names at $3.8M/day, the same 70% kept and a 94x lower bar — so a $20M/day burst, `strategy.md`'s own "slippage eats the edge" kill criterion, is refused today and admitted after. The percentile half is pinned by a test; rule 4 cannot be, because nothing in the code sees a ticker — which is the point. The generator has to answer for both or say plainly that it does not. |
| The universe widens past `data/symbols.txt` | the four 230-name figures in README: its opening line, the diagram's universe box, the diagram's Layer-1 caption, and the Costs section's scan-time note. (This row named a Tuning section that holds none, and missed the opening line — checked by grepping, since a list of places is exactly the kind of claim that rots.) |

Nothing else is scheduled to go stale: step 10 was the last of the ten. The two
rows left are one decision — the open one at the bottom of this file — not a step.

## Standing rule: no line numbers in comments or docs

Cite functions, not `file.py:NN`. Three separate citations rotted inside a
single step's own commits. `get_clients()` is stable; `scanner.py:78` is not.

## Standing rule: prove a test can fail

A test that cannot fail is worse than no test, because it reports safety that
is not there. Three of this project's "rejection path" tests observed a
different rule failing than the one they named — the 4% gain, the rule the
product is named after, could be deleted with the whole suite green.

**When you change or add a rule, delete it and watch the suite go red.** If it
stays green, the test is shaped, not load-bearing. This was mandatory for steps
4 and 7, which changed the scan filter and the 2LYNCH maths; both were done
that way. Half the discipline is the inverse check: break a rule the test does
NOT name and confirm the test fails too, rather than passing while a different
rule does the rejecting. `tests/test_scanner.py`'s `_only_failing()` makes that
a precondition of every rejection test instead of an inequality picked by eye.

The doc-sweep rule above failed on three consecutive commits because it relied
on remembering. `tests/test_docs_are_true.py` now enforces the mechanically
checkable parts — the test count, the universe size, the email's universe
string, `.env.example`'s `feed=` claim, and (step 10) that README's workflow
inventory and its list of run modes are the ones that exist. Prose still needs
a human.

**Three shapes this project has now produced, each found only by mutation:**
a test that passes because a DIFFERENT rule rejects (the rejection-path tests);
a test that passes because of an incidental fact about the fixture rather than
the rule (`test_the_morning_email_attaches_no_chart_and_says_why` passed on a
path that did not resolve, not on the suppression it named; deleting the
suppression left the suite green); and a test that compares a value against the
NAME it came from (`assert report.exit_code == pipeline.EXIT_DEGRADED` stays
green when the constant itself is changed to 0 — fifteen assertions did, and
`test_the_exit_codes_are_the_numbers_actions_reads` is the one place that now
pins the names to numbers so the other fifteen can keep reading legibly). The
third shape is the cheapest to write and the hardest to see: nothing about it
looks wrong.

**A test whose answer depends on the hour it runs is the worst kind there is.**
Step 10 made the run type a promise about the 16:15 ET close, so every
end-to-end test in `tests/test_pipeline.py` would otherwise have been green all
evening and red all morning. The `market_clock` fixture there pins the side of
the close — but only for a caller that does NOT name an instant, so a test that
passes a real `datetime` still exercises the real arithmetic, and the check
itself is pinned against real instants in `tests/test_scanner.py`.

## Verification is by execution

The strongest findings in this rebuild came from running the code, not reading
it — reproducing a crash, sourcing a hostile `.env`, testing `git check-ignore`
against real paths. A claim that was argued rather than executed is a lead, not
a finding. This applies to reviewing agents too.

Twice, a fix was worse than the bug it replaced: an env-loader that leaked the
environment was swapped for one that executed the file as shell, and a
`.gitignore` round that anchored three rules added two more unanchored. **Check
that a fix did not introduce a new defect of the same class.**

And when a defect is one of a class, **sweep for the next instance before
declaring the class closed.** One class has now produced five: code reads a
structure off disk, accepts a shape it never indexes into, and a later consumer
breaks. `Ledger.load()` closed three, one level in each time; `read_snapshot()`
was the fourth, found because the brief asked, and the fifth was found only by
the sweep the fourth prompted — a stored row whose `forward_returns` is not an
object loaded clean and took the evening run down inside `add_run()`, after
every Claude call had been paid for. The sweep that found it was a table of
thirty-seven malformed shapes run through the real code
(`MALFORMED_SNAPSHOTS` in `tests/test_pipeline.py`), not a reading of it; the
brief's one example crashed, and so did nineteen the reading would not have
predicted. (It was thirty-seven when that sentence was written and the table
has grown since — a count in prose beside a table that keeps growing is a
citation that rots, so read the number off `len(MALFORMED_SNAPSHOTS)`.)

## Environment constraints

- **No live market data.** The sandbox proxy blocks Yahoo and Alpaca. Anything
  requiring a real trading day has to be validated by the user locally. Reason
  from the SDK and synthetic frames instead; do not fake a result.
- **Free Alpaca plan.** No SIP subscription. The IEX feed carries a fraction of
  consolidated volume, which is why the absolute share threshold has to become
  a relative one (step 4).
- **There is a regression net.** `pytest tests/` runs 889 tests with no network
  and no API keys (step 6a). The scan filter's thresholds ARE asserted (step 4)
  and the 2LYNCH checks are too (step 7), each mutation-tested; step 6b
  re-mutated both — 88 mutants, 84 killed, and the four survivors are each
  provably equivalent or measure-zero (`>=`→`>` on a float boundary the grid
  steps over), not gaps. Step 10 mutated its own additions the same way — 38
  mutants over the mode/clock check, the streak arithmetic and the morning
  mode, all 38 killed, and its three first-round survivors closed with the
  tests they showed were missing rather than argued away. Step 11 mutated its
  own additions the same way -- nine over `evidence()`, five over the widened
  snapshot shape check, three over the required-key set, all killed -- and
  3.3 mutated its own additions the same way -- 41 over the up-days veto, the
  base-breakdown criterion, the gate's reason vocabulary and the synthetic
  frame's new knob; 36 killed on the first pass, and four of the five
  survivors were real holes closed with the tests they showed were missing.
  One of those four was not a missing test but a defect: `>` and `>=` on the
  breakdown threshold were indistinguishable because NO frame could put the
  raw `pct_change` on the boundary (8,000 adjacent close ratios tried), while
  every surface printed the number rounded to a tenth -- so -4.04% was refused
  displaying "-4.0%" and -3.96% passed displaying "-4.0%", two rows showing
  the threshold under a note stating it, one refused and one not.
  `worst_base_day()` rounds now, and the archive, the note and the predicate
  are one number. The fifth survivor is the up-day loop's `range(n-1, 0, -1)`:
  widening it to 0 is provably equivalent (index 0 is only reached by a
  strictly increasing series, whose first element loses to its last), and the
  argument is written beside the loop rather than here.
  3.4 closed the five survivors the brief named: the staleness band's
  `>= 2` boundary (every band test used a gap of 15), `current_session()`'s
  weekend rewind (the Sunday case passes at one step OR two; only a Saturday
  tells them apart), and `MIN_LYNCH_PASSES` / `TOP_N` / `MAX_TO_SCORE`, whose
  truncation was tested everywhere while the numbers themselves were pinned
  nowhere. One of those was not
  a missing test but a real regression: the catch-all that stops an unreadable
  history from killing a run had reopened the door to a run OVERWRITING the
  history it could not read, which is exactly what Ledger.set_aside() exists to
  prevent. The three holes this section used to name are closed:
  `get_universe()` and the symbol-file parser (`tests/test_scanner.py`),
  `main()`'s exit code (`tests/test_pipeline.py`), and the SDK wire shapes —
  `tests/test_sdk_contract.py` builds a genuine `StockBarsRequest` and a genuine
  `BarSet` offline and runs one scan through both the real object and the
  double, so a shape change in alpaca-py fails here rather than passing.
  Still untested HERE: anything needing a socket — that the credentials can
  query the feed, that Resend delivers, that Claude returns what the parser
  expects from a real chart. `tools/live_check.py` now asks each of those once,
  through the pipeline's own calls, from a machine that has the keys; the
  owner runs it before the first scheduled night (README, "One-time setup").
  Its own logic is exercised offline in `tests/test_live_check.py` through the
  same doubles the pipeline tests use — and that suite caught its first
  version printing READY under `--no-spend` over boundaries it had never
  tried, which is the confidently false sentence in the tool meant to prevent
  one.

  **The record measured the picks against the claimed band and against each
  other, and never against the alternative.** The north star is "its picks
  beat the alternative", and the ledger has archived the alternative since
  3.3 -- every refused burst, with the same forward returns -- without one
  block ever comparing them. `evidence()` carries five disjoint populations
  now, each with its own `enough`: `shortlist`, `rest`, `refused` (what the
  checklist or an absolute rule said no to), `crowded_out` (cleared the
  gate, never scored because MAX_TO_SCORE filled) and, since round 5,
  `illiquid` (what rule 6 refused, kept beside the control and not in it). The split is the point: a
  crowded-out name is one the screener LIKED, and folding it into the
  refusals would let a full night pad the control by exactly what those names
  went on to make. A row with no reason word predates the reasons and counts
  as refused. The page renders the ladder under the score-band table and
  states a direction only when BOTH sides clear `min_setups` at the longest
  horizon, always with both n's -- the same rule `scoreVerdict()` follows.
  Read off the thirty-run history before any page existed to show it: the
  refusals returned 3.63% at five sessions against 5.9% for what was scored,
  over 14 and 74 -- which is the "only one side can be read" sentence, and
  the page says exactly that. The three verdict branches are pinned on three
  sources, because no real source can hold more than one of them yet.

## Findings from the round-4 audit — the first-run and scanner lenses

Five auditors over disjoint lenses, three refuters per finding, all by
execution against `git archive` copies (the first attempt died on a session
limit, all fourteen agents, the way the 3.1 verifiers did; the second ran).
The first two lenses back returned sixteen findings; every one below was
reproduced HERE before it was fixed, and one of the reproductions caught the
harness rather than the code — the synthetic burst pins the same final close
on every seed, so "raise on B3's close" raised on ten frames.

**Two the first real night would have hit.** The backup-cron guard counted
any `evening-*` artifact created on today's UTC date as "already ran", and
the artifact step uploads on failure too: a preflight failure, or a
Run-workflow click at lunch to test the secrets, silenced that night's cron
— read off the Actions API, both failed 4 Sep runs left one. And an EST
night starts at 23:16 UTC, so a run over ~44 minutes uploaded under
tomorrow's date and silenced the following night. A run that published
names its artifact after the SESSION now, a failed one is `evening-failed-`,
and the guard counts only the first shape; six scenarios traced through the
guard's own shell against a stub `gh` running its real `jq` filter.

**A lunchtime dispatch re-scanned yesterday, paid Claude again, and replaced
the clean record with a degraded one — committed, since exit 2 persists.**
If the session an evening run would scan is already published, it
re-presents it the way the morning does and says why; the clock
disagreement stays in the report and the exit code stays 2.

**A backfill made the morning announce that nothing had published.**
`SCAN_SESSION_DATE` of last week rewrote `docs/data.json`'s headline to last
week while `runs` two lines down still listed last night; the morning read
the top block and escalated to NOTHING PUBLISHED IN 3 SESSIONS over a file
naming the newer run itself. `publish()` keeps the newer headline when the
run just added is older; the record still gains the backfill.

**Exit 3 committed a record that said `ok`.** A night whose email failed
kept its record — and the record carried `status: ok, errors: []`, so the
page and the next morning presented it as clean and only the Actions colour
knew. The delivery failure is stamped into both files before it is raised.

**The scanner assumed bars arrive oldest-first and once each.** Neither is
promised: `BarSet.df` keeps the response's order and the request pins no
`sort`. A newest-first reply made every symbol read as stale and killed the
run blaming a holiday; a bar sent twice hid a real burst behind a 0% gain.
Sorted and de-duplicated on the way in, with genuine `BarSet`s in the tests
— not by pinning `sort` on the request, which would change the wire on an
unverified lead.

**A hole before the session published a two-day move as the day's burst.**
Freshness checked only the newest bar, so a halt or a dropped bar the
session before left `iloc[-2]` two sessions old: 12.0% printed as 12.45%,
dated to the session. `_drop_gapped_symbols()` requires the bar before the
session to be the previous business day (weekend-only, the same arithmetic
`current_session()` makes), counts the rest, and the run degrades on them
with the stale ones. **And a detector that raised on every symbol was a
quiet market**: `detect_setup`'s per-symbol `except: continue` had no count,
so a pandas change would have returned `[]` with `with_bars` intact — the
shape every coverage guard exists to prevent, on the one path none covered.
Counted now, degraded at any count, fatal when it is every symbol.

**Smaller, each reproduced:** Y printed `+0.0% past month` to the model when
it had fewer than 21 closes to measure one (the real run-up over the sessions
it had was +16.9%) — it says it could not measure now, and the half it did
measure decides alone; H passed a close ABOVE its own high at "145% of day's
range" — the same class of bad bar as an inverted one, refused the same way;
the email's funnel said "N checked-in US common stocks" over names typed with
`--tickers` while the archive beside it said `--tickers` — one label now;
`.env.example` omitted the CSV an evening run writes; and two boundaries no
test sat on (`>=` on `coverage_guard_min_symbols`, the "not permitted"
clause) are pinned. **One class of finding was about the record's own
contract and was left for its own round:** a burst rule 6 refuses for
liquidity vanished from every surface — not in `bursts`, not in `gated_out`,
not in the ledger — so on a two-name `--tickers` smoke test the thinner of two
$5B names was refused and the email read "4% bursts found: 1". Round 5 below
is that round.

## Findings from the round-4 audit — the reader and ledger lenses

Twenty-one more, three HIGH, every one reproduced here before it was fixed.

**The red band was the one leaf carrying free text from OUTSIDE the codebase
on the first real night, and it was raw.** anthropic's SDK sets the exception
message to the raw response body when it is not JSON, so an edge 5xx HTML
page landed in `_check_scoring()`'s sentence and the band interpolated it as
markup: the operator read "502 Bad Gateway 502 Bad Gateway cloudflare" with
the tags swallowed. The escaping round before this one swept eight leaves and
missed the band, the checklist lines, the chart note, the close cell, the
session in the title and funnel, and the stale note — all escaped now, each
pinned through a real parser. Two existing tests then broke, and correctly:
they grepped the mail SOURCE for a sentence with an apostrophe in it, which
is an entity now, and the reader is the standard.

**The page, the code and the fixture held three different fallback rules.**
The page said a fallback score is "passes ÷ checks × 10"; `_fallback_score()`
has mapped the pass count to the LOW end of its rubric band since step 8; and
`tools/make_fixture.py` typed the old arithmetic under a comment reading
"src/scorer.py's own fallback formula, verbatim", which is why the page's
sentence and the fixture agreed and nothing noticed. A real 5/6 fallback
printed 7.0 under a sentence whose formula gives 8.3. The generator calls the
scorer's own function now, the sentence states the map, and a docs test reads
the sentence's numbers back against the function.

**The sixth instance of the class, one level further than the fifth.** A
stored row whose `checks` is a list, whose `ticker` is not a string, whose
`date` is a list or whose `d5` is a string loaded CLEAN and took the evening
run down at archive — after the scan and every Claude call — and, not having
been set aside, took every following night down the same way. Driven through
the real evening path, all four shapes: exit 2 now, set aside, record written.

**A setup refused on day one and scored on day two was invisible to every
score-keyed block.** The common case the veto produces — a 6/6 name three up
days into a run, allowed back the next session. `setup_leads()` made the
refused row the lead, `scored` kept only leads that were candidates, and so
the paid-for score and its realised outcome were in neither `overall` nor
`by_score` nor `by_month`; `by_ticker` printed an em dash for a name with a
score; the run's own mean skipped it. The committed thirty-run history held
THREE. Setups are chains now (`setup_chains()`): `by_check` still judges the
first appearance, whose verdict was passed that day, and every score-keyed
block judges the first SCORED appearance; a setup is on one side of the
control only. The history's scored setups went 92 → 94 and refusals 18 → 16.

**A backfill older than the fill window never got its outcomes.** The window
is the ten newest runs by session, so a `SCAN_SESSION_DATE` run of an older
one landed outside it on the very run that scored it, and README's "a run
pinned to an old session resolves its own outcomes" was false from the
eleventh session back. The run just added is always in the window. The only
test named for the window could not see it — every run held the same two
names and `pending_tickers()` de-duplicates — so the window could be deleted
green, and this lived under it.

**Four rules no test could fail on:** a scored row landing in its `by_score`
bucket (a mutant keeping fallbacks only passed, the floor test comparing
empty to empty), both edges of the 8–20% band, `top_score` (max → min
passed), and `outcome_summary`'s `fsum` (only `mean_returns` was pinned, so
every published evidence mean could go back to `sum()` green). All pinned.
Two design choices fixed with them: `record.sessions` now comes from
`Record.of()`, the rule every streak reads, so one undated run entry no
longer makes one page publish two session counts; and the shortlist split
uses each run's own `shortlist_size` rather than the newest run's.

**The reader lens's smaller findings, each reproduced and each pinned on the
state it named.** A morning with nothing to read printed "4% bursts that
session: 0 | Passed 2LYNCH gate: 0" under a session it called "not recorded"
— the guaranteed state of the first production morning — and prints "not
recorded" for both now. One name's checklist read two ways in two emails a
night apart: the evening prints `src.lynch`'s own lines and raw floats, the
morning rebuilt the lines off disk with the code and label split and printed
values `_num()` had turned to ints ("+12%", "8x", "7/10"); one formatter for
the three numbers on both paths, and `email_row()` rebuilds the line in the
scorer's exact shape, pinned by a test that mails the same candidate both
ways and compares. The page's `day()` printed "NaN undefined not" for a run
entry whose date will not parse, a state the pipeline keeps rather than
refuses; its weakest-check sentence said "of the ones that failed it" for a
rate taken over the bursts that failed the CHECKLIST; a snapshot with no gate
block reached the funnel as "under undefined checks passed", one field past
where the nogatetotal round stopped; a day number with no `first_seen` read
"since —" on the page and "since " in the email; and two sentences were not
quite true of their own data. Fixed with three smoke variants (`undated`,
`oldsnap`, `nosince`) and one test whose name promised the monitor and
exercised its headline. Nine mutants across them, all killed.


  **The interpreter is part of the environment, and it changed an answer.**
  CPython 3.12 made the builtin `sum()` compensated for floats, so the same
  `docs/ledger.json` read by 3.11 and by 3.12 published two different run
  means -- 5.52 against 5.53, on a `round(x, 2)` boundary. CI runs 3.12 and
  this sandbox runs 3.11, so it would have turned the next PR red and looked
  like a fixture problem. Found by regenerating `tests/fixtures/history` under
  both and diffing: 2 of 1788 numbers differed and both were run-level means.
  `mean_returns()` uses `math.fsum` now, which is correctly rounded, fixed
  across versions and order-independent; the fixture is byte-identical under
  3.11 and 3.12, at numpy 1.26/2.0/2.4/2.5 and pandas 2.0/2.2/3.0. Worth
  knowing for the next fixture: **a generated artifact committed to this repo
  is only as reproducible as the arithmetic behind it**, and the sandbox's
  interpreter is not CI's. It is also a limit on mutation testing here -- from
  3.12 no input distinguishes `sum()` from `fsum()` (300,000 adversarial cases
  tried), so the two tests that pin this are load-bearing on 3.11 and
  documentation on CI.

  **THE SCHEDULED RUNS HAVE NEVER ONCE HAD THEIR SECRETS, and that is the
  whole reason nothing has accumulated.** Read from the Actions log on 4 Sep,
  not inferred: every weekday since the rebuild merged, BOTH jobs have failed
  the same way.

      PreflightError: missing or empty required environment: ALPACA_API_KEY,
      ALPACA_SECRET_KEY, ANTHROPIC_API_KEY, RESEND_API_KEY, EMAIL_TO

  That is the EVENING message. The morning job cannot produce it and never
  has: `missing_env()` composes the requirement from the layers the mode
  actually runs, and a follow-through scans nothing, so it names
  `RESEND_API_KEY, EMAIL_TO` and no more. This paragraph said "BOTH jobs have
  failed the same way" and printed one message; the mechanism is the same and
  the message is not, which matters because that difference is the preflight
  working exactly as designed.

  The pairs of crons make this easy to misread, so it is written down: the
  US is on EDT, so the `16 22` (evening) and `30 12` (morning) crons are the
  live ones and they FAIL; the `16 23` and `30 13` runs report SUCCESS
  because the guard correctly no-ops them. A glance at the Actions tab shows
  green ticks next to red ones every day and the green ones did nothing.

  Nothing in the code is wrong here -- this is step 5 working exactly as
  designed: preflight caught it before spending anything, named every missing
  variable, and exited 1. It cannot even mail the failure notice, because two
  of the missing secrets are what mailing needs, and it says so.
  **It needs the six repository secrets set (README, "One-time setup"); no
  amount of further work in this repo can do it.** Until then
  `docs/ledger.json` will never exist, the forward returns cannot be measured,
  the page's evidence block stays empty and correct, and the morning run has
  nothing to follow through on.

  **A DEGRADED night could not commit its record, and that was the biggest
  thing standing between this project and its own north star.** Exit 2 means
  the run WORKED and noted a problem: the scan ran, the charts rendered, up to
  MAX_TO_SCORE Claude calls were paid for, `docs/data.json` and
  `docs/ledger.json` were written complete, the shortlist was mailed — and then
  the record died with the container, because a `run:` step fails on any
  non-zero code and the persist step's `if:` carried no status function, so
  Actions ANDed `success()` into it and skipped the commit-back. The artifact
  step right below it carries an explicit `(success() || failure())` and its
  own comment reasons about exactly that asymmetry; the persist step did not.
  Verified from the Actions API on run 33927201865: step 6 failure, step 7
  SKIPPED, step 8 success.

  Not a corner case — one chart that will not render is enough, as is one
  Claude fallback, >10% stale symbols, an unreadable history, or a mode/clock
  disagreement. **This repo's own 30-session fixture is 2 degraded in 30, and
  its newest run is one of them**, so the canonical picture of "what `docs/`
  holds after a month" contains two nights this workflow could not have kept.
  `src.pipeline`'s contract is that a degraded run publishes — there is a test
  named `..._degrades_the_run_but_still_publishes` — and the workflow was
  throwing the publication away. The pipeline step captures its code now and
  `Report the pipeline's verdict` re-raises it last, after the persist and the
  artifact upload, so the job's COLOUR is unchanged and only the record is
  rescued. Whether red is right for exit 2 is a separate question, deliberately
  not answered.

  **And the same defect was one stage further on, found by sweeping for it
  rather than by waiting for it.** The fix above asserted that exit 1 means
  "there is nothing trustworthy to commit", and that was false: `publish()`
  runs BEFORE the email, so a run that dies delivering has scanned, rendered
  every chart, paid for every Claude call and written both files complete --
  and exited 1, the same code as a preflight that spent nothing. Reproduced by
  driving the real evening path with a Resend double raising the message an
  unverified sender domain actually returns: exit 1, `data.json` with three
  candidates, `ledger.json` with three rows, three Claude calls paid for,
  three charts on disk. `EXIT_FAILED_AFTER_PUBLISH` is 3 now, set by a
  `report.published` flag that `publish()` raises the moment `book.write()`
  returns, and the persist condition keeps 0, 2 and 3. A THIRD code rather
  than widening the condition to "any non-zero", because a preflight failure
  must not claim a record: the workflow would commit whatever `docs/` the
  checkout carried and call it tonight's run. Six mutants over the new rule,
  all six killed; the workflow test reads the constant rather than the digit,
  so renumbering cannot pass one half while the other keeps the old number.
  This is the sweep this file's "check that a fix did not introduce a new
  defect of the same class" rule asks for, and it found one.

  **The empty-shortlist note was a two-way flag and NEITHER way was reliably
  true.** `refused_all` read `vetoed and not gated` -- but `gated` is how many
  PASSED the checklist, not how many it rejected, so the flag actually meant
  "something was vetoed and nobody got through". ONE veto among ten bursts set
  it, and the cell then read "Every burst the scan found was refused outright
  by an absolute rule" three lines under a funnel line reading "Refused by an
  absolute rule: 1". The email contradicted itself on one screen. Its other
  branch printed "No candidates passed the quality gate today" on a night the
  scan found NO BURST AT ALL, directly under "4% bursts found: 0" -- the named
  collapse arriving from the opposite direction, with the gate blamed for an
  outcome it had no part in. The note is computed from the counts now, one
  sentence per state, and every state was rendered and read before it was
  written down; three of the six were wrong. Nine mutants, eight killed; the
  ninth drops `- passed` from `by_checklist`, which is provably equivalent
  because every branch that reads it sits below the `passed` early return, and
  the argument is written beside the code rather than here.

  **The page did not have that defect, and checking cost one shaped test.**
  On a zero-burst night it hides every candidate card and lets the funnel say
  it: "The widest cut is 230 names at '4% bursts' -- no 4% gain on the day".
  Both facts are pinned by a `quietmarket` variant now, because "the page is
  fine here" was an unchecked claim until one existed. The first version of
  that check read `textContent('body')` and failed -- on the page's own
  `<script>`, whose comments discuss the very sentences it was searching for.
  `innerText` is what a reader sees; `textContent` inside this page is source.
  That is the "asserting the page's own source" shape from the 3.3 audit,
  caught this time by the check failing rather than by it passing.

  **The email's funnel had no scoring stage, so the names the call budget
  never reached appeared nowhere.** It went "Passed 2LYNCH gate: 54" straight
  to "Shortlisted: 1", with "Scored by Claude: 25 of 25" beside it -- which a
  reader takes for complete coverage of the 54, and 29 names that cleared the
  checklist were never looked at by anything. The page has had that cut since
  step 9. The email has it now, counted off the archived reason word and
  printed only when the cap actually bit, the same rule the refusals line
  follows. Six mutants, all killed -- but only after the fifth survived and
  showed the tests were shaped: with nothing vetoed, every unscored burst IS a
  score_cap one, so counting them all gave the same number. The test that
  distinguishes them needs a night with both kinds in it, in different
  numbers, and says so in a precondition. Neither surface had the phrase "the
  N-call cap" pinned, which is how one mechanism grows two vocabularies; both
  do now, each asserting against the other's source.

  **The system prompt is 59% of every request and was paid for 25 times a
  night.** `knowledge/strategy.md` is byte-identical on every call of a run --
  measured at ~1,590 tokens against ~388 of metrics and ~721 for an 869x622
  chart -- and nothing asked for it to be cached. It carries `cache_control`
  now: a write costs 1.25x and a read 0.1x, so break-even is the second call
  (1.28 calls: the write costs 0.25x more than the uncached call it replaces
  and each read saves 0.9x) and a full night is 41% cheaper, $0.25 to $0.15.
  This said 1.4 calls, 43% and "$0.24 to $0.13" while README said $0.25 — the
  same paragraph in two files with two arithmetics, and a test now does it
  from README's stated inputs. No `ttl`, because 5 minutes is
  the cheap write and every read resets the window. The SDK's own
  `TextBlockParam` says the block is well formed, checked offline, which is
  the only kind of wire check this suite can make.

  The saving is invisible from inside the run -- the reply is identical either
  way -- so `cache_usage()` reads the reply's own counts and `score_all()`
  logs one line per run. Without it a cache that quietly stopped working (a
  system prompt edited below the 1,024-token minimum, two calls further apart
  than the TTL) would cost 1.25x forever with a code comment as the only
  evidence it was ever meant to. Eight mutants, all killed, including an
  explicit `ttl: 1h` and a prefix split across two blocks.

  Both test doubles in this suite bill the cached prefix by ONE shared rule
  (`billed_usage` in `tests/fakes.py`): the first call of a run writes it,
  every call after reads it, and only a block carrying `cache_control` counts.
  A flat per-call number would have made the totalling test pass with the
  caching removed, which is this file's third shape -- a test that cannot tell
  the states apart -- and the inverse test that drops `cache_control` is what
  proves it does.

  **And the retry for an unparseable reply resent the request byte for byte,
  at temperature 0.** Measured, not argued: a prose reply produced two
  IDENTICAL requests, both unparseable, and the candidate fell back anyway
  having been paid for twice. That is the reasoning `score_candidate()`
  already applies to a rejected credential -- "a rejected key is not
  transient; the retry is theatre" -- three lines above, and it was not
  applied to a reply that arrived in the wrong shape, which is equally a fact
  about the request that produced it. temperature 0 is not a guarantee of an
  identical reply, so the second call was not certain to be wasted; it just
  had no reason to go differently. It has one now: `RETRY_CORRECTION` is
  APPENDED to the content, the system prompt untouched so the cached prefix
  still hits, and a transport error still resends what it had -- correcting a
  request that was fine tells the model its own output was wrong when it never
  produced any. Five mutants; the fourth survived and was a real hole, a retry
  carrying the correction ALONE, which asks the model to score a candidate it
  can no longer see and returns a reply that parses. Nothing downstream would
  have noticed.

  **Two findings about the quarantine, and one of them was wrong.** The claim
  was that `Ledger.set_aside()`'s casualty dies with the container because it
  is not gitignored. Both halves are checkable and the conclusion is the
  opposite of the premise: `git check-ignore` says the casualty is NOT
  ignored, which is exactly why `git add docs` stages it and the commit-back
  keeps it. Simulated end to end against a real `git` in a real repository --
  a corrupt ledger committed, a night run over it, `git add docs`, and the
  night after -- and the second night quarantines nothing, because the fresh
  ledger reached the branch on exit 2. **That is the persist fix paying for
  itself twice**: before it, a corrupt ledger was permanent, since every night
  set it aside, wrote a good one, and threw the good one away with the
  container. Both halves are pinned now, and the test reads this repo's own
  docs/ rules out of `.gitignore` rather than retyping them, so a later round
  that gitignores the casualty fails here instead of silently reinstating the
  bug that was never there.

  What IS true and stays open: nothing ever prunes the casualties.
  `quarantined()` returns them oldest-first and is called by no production
  code, so repeated corruption commits an unbounded number of ~1.5 MB files
  (172 KB per 30 runs, at MAX_RUNS 260) into a directory GitHub Pages serves.
  Deliberately not "fixed" here: every pruning rule destroys the data
  `set_aside()` exists to keep, the oldest casualty holds the most history and
  the newest is the most diagnostic, and inventing a policy to answer a
  failure mode nobody has seen is how this project's notes record two fixes
  being worse than their bugs. Written down instead.

  **The fourth number in this repo to rot, and the first with a tool to stop
  it.** README quoted 8.8 MB raw and 0.59 MB gzipped for a full year of
  `docs/ledger.json` -- and the page's whole "fetch it only when asked" design
  is argued from those. The 3.3 audit added `context` to both row types and
  nobody re-measured, because re-measuring meant building an eleven-megabyte
  file by hand. It was 11.04 and 0.66 when measured, 11.07 and 0.68 once
  the round-4 prose sweep put a universe block on every run entry, 11.54
  and 0.72 once round 5 put a liquidity block on every entry, and 13.63 and
  0.97 once round 6 put the open basis on every row and every mean and the
  round-5 audit put the dollar volume on every ledger row -- the guard below
  caught every move on the commit that made it. The gzipped figure has
  grown faster than the raw one, because a block of nulls compresses worse
  than a run of numbers; the page's fetch-on-demand argument still holds at
  a megabyte. `tools/measure_ledger.py` builds one now
  -- real rows from the generated history, real row counts from the canonical
  one-night fixture, and `src.ledger`'s own writer, because `indent=2` is most
  of the raw size and a compact estimate is not the file a browser fetches --
  and `tests/test_docs_are_true.py` asserts README against what it prints.
  Two estimates disagreed by a factor of two on the way here (968 B/row scaled,
  against per-row-type sums at compact separators); building the actual file is
  what settled it, which is this file's own rule about argued findings.

  **The commit-back was the last artifact still naming a clock.** Step 10 made
  "name the session you really read" a rule for the subject line, the table
  heading and the CSV filename; `evening.yml` committed `run $(date -u +%F)`.
  Two ways they differ: an EST evening starts at 23:16 UTC, so a run over ~44
  minutes commits under TOMORROW's date, and a `SCAN_SESSION_DATE` backfill
  scans an old session and labels it today -- the silent relabelling step 10
  exists to end. It reads `docs/data.json`'s own `run.date` now, and when it
  cannot, the message SAYS the date is a commit time rather than passing one
  off as the other. The test cuts those lines out of the real workflow and runs
  them against a stub `git`, the way the push loop was traced: reading them
  proves nothing about what `sh` does with `$(...)` and `[ -n ]`.

  **And the page's streak tooltip named the 2LYNCH gate alone, under a comment
  saying it matched the email.** The 3.3 audit swept that sentence in
  `_streak_footnote()` -- three reasons, because a veto is not a gate rejection
  -- and did not sweep the page. A 6/6 name refused by an absolute rule is
  counted in `seen_before`, and the tooltip told the reader it was not. Same
  round, a second one: the streak table's null bucket said "the record does not
  reach back far enough", which is ONE of the four reasons that put a burst
  there, and the only one any available fixture carries -- so a run whose
  history could not be READ was told a different fault with a different fix.
  The bucket has no reason field to narrow it, so it now says what is true of
  all four and points at the rows, which do. Both pinned by tests that read
  both files, because a comment claiming two surfaces match is exactly what
  carried this for a round.

  **And CI was red for three commits while the suite was green here, for the
  reason this section already warns about.** The workflow checks parse
  `.github/workflows/*.yml` and assert on the PARSED structure -- right, since
  what went wrong there twice was a property of an `if:` condition and not a
  spelling -- but `import yaml` was never declared. This sandbox happens to
  have PyYAML; the runner installs `requirements-dev.txt` and nothing else, so
  four tests errored there and passed here. PyYAML is declared now, and
  `test_every_module_this_repo_imports_is_a_dependency_it_declares` walks the
  AST of `src/`, `tests/` and `tools/` and maps each import to the
  distribution that provides it -- `yaml` comes from PyYAML and `alpaca` from
  alpaca-py, neither guessable from the module name. **The interpreter was the
  first way this machine differed from CI and the installed packages are the
  second; assume there is a third.**

  **And `evening.yml`'s commit-back has still never executed** — nor has the
  step it lives in. Every streak, and the morning run's entire input, rest on
  it; the `git add` bug that would have voided it is fixed and guarded by a
  test. But read from the Actions API: `evening.yml` has fired SIX times ever,
  all scheduled — three DST-guard no-ops and three preflight failures — and a
  failed pipeline step skips the persist step entirely, so nothing has reached
  the add, the commit or the push under any version. The buggy `git add docs
  results` lived only on the rebuild branch and was fixed before that branch
  merged, so no scheduled run ever checked it out either. An earlier draft of
  this note, and two paragraphs of README, described that bug as failing
  silently every night; it never ran once. The defect was real in the code and
  the invented nightly failure was not, which is the difference this file's own
  "verification is by execution" rule exists to keep. The push-and-rebase loop
  was traced with `bash -ex` against a stub `git` — three attempts really
  happen now, where the old loop aborted after one — but that is a simulation.
  Watch the first evening run that gets past preflight.

  **One judgement about the calendar, written down once.** The morning email's
  staleness band needs to know whether a market closure could explain nothing
  having published, and this project deliberately carries no holiday calendar
  (an approximate one used to make a confident claim is worse than the defect
  it replaces). It does not need one: NONE OF THE US MARKET'S SCHEDULED
  HOLIDAYS ARE ADJACENT, so a gap of one session is genuinely ambiguous and a
  gap of two or more is not — at least one of those days was a scheduled
  session. (Unscheduled closures HAVE run to consecutive sessions — 9/11,
  Sandy, the 2007 day of mourning the day after New Year's Day — so the band
  keeps one clause for them, named as the exception, which is what stops the
  arithmetic from becoming the next confidently false sentence.) That is the whole rule
  behind `stale_snapshot_note()`'s branches and behind the subject line's
  escalation, and it is arithmetic over `ledger.sessions_between()`, not a
  calendar. Before it, the emails rendered at 1, 3 and 15 sessions stale were
  byte-identical but for a date, and at 15 the hedge all three carried ("or the
  market held no session for it to scan") was itself false — the screener dead
  for three weeks arrived looking like the Tuesday after Presidents' Day.

  `docs/index.html` CAN be opened here after all: playwright's chromium is
  installed in this sandbox (`node tools/dashboard_smoke.mjs` after cloning the
  design system to /tmp/design-system runs every check with no page errors),
  which the previous round of these notes said was impossible. Run it, and
  LOOK at the screenshots it writes with `--shots`. The script now checks
  README's claim about how many checks it is, so that number cannot rot the
  way three others in this repo already did. Since 3.1 it opens the page
  against three sources — the canonical fixture, the thirty-run history
  `tools/make_history.py` writes by driving the real pipeline offline, and
  whatever `docs/` holds — so the checks that know a fixture's contents never
  run against the file a real run replaces. The streak
  line the page carries was additionally rendered against a data.json holding
  every streak state and read back from the DOM, rather than argued about, and
  five of those wordings are asserted in the script now: the email and the page
  had drifted apart on the null-`day` sentence, on the verdict after a scored
  last appearance, on "day N **of this setup**", and on what the gated table
  calls a burst the call budget crowded out — two vocabularies for one
  mechanism, side by side on one page, under two comments each claiming they
  matched.

## Round 6 — every return measured twice, from the close and from the open

The wild ideator's first proposal, verified by execution before it was
adopted: `forward_returns()` divided every later close by the BURST-DAY
CLOSE, which is the price the screener measured and the price nobody reading
an 18:16 ET email can buy. Burst close 100, next open 110, next close 111:
the record said d1 = +11.0% while the price a reader could actually have paid
returned +0.91%. The overnight gap is where a 4% burst's momentum shows up
first, and the record was crediting the strategy with it.

Every row, every run mean and every evidence outcome now carries a second
measurement, `from_open` — the same later closes divided by the next
session's open — with its own n and its own `enough_from_open`, because a
frame with no usable open has a close-basis return and no open-basis one and
the two counts must not be read as one. The contract says which basis
answers which question (what the setup did; what acting on it could have
had) and that both are paper prices from one venue's prints with no
slippage. `_malformed_rows()` refuses a `from_open` that is not an object or
holds a string where a number belongs — the seventh instance of the
one-level-short class, closed before it could open. A row from before the
basis existed gains the block, pending, when its bars are next fetched, and
the fill window keeps a row while a horizon is open on EITHER basis.

**The page shows one basis at a time, chosen by one control, and names it in
every heading that carries a return.** Two bases side by side in one table is
the "two vocabularies for one mechanism" shape this project keeps finding,
so there is a segmented control in the evidence card and no second column:
pressing a basis re-renders the whole page from the same data, every rate
cell, verdict sentence, candidate row, runs-table mean and per-name record
goes through one accessor, and a record from before the basis existed greys
the open choice and says why rather than showing close-basis numbers under
an open-basis label. The smoke checks read the ledger's own `from_open`
block for each surface and compare after switching, then switch back.

**Two things the round found on the way.** The basis accessor was first
named `pick()`, which is also the shortlist card builder's name; the later
declaration won, every card became a plain object and the shortlist rendered
empty with no error anywhere — found because a pre-existing smoke check
timed out waiting for a card, not by any check of the new work. And a scored
lead with no usable rank fell out of BOTH `shortlist` and `rest`, so the five
populations did not add up to the record: no writer produces such a row, a
hand-edited or older file can, and the contract walker's new sum check found
it on a test that plants one. Not shown to be on the shortlist is `rest`.

**The round-5 audit, worked in the same commit.** Three lenses by execution
over the round-5 tree, sixteen findings, every one reproduced here before
it was touched. Four were real defects: the gated hint's clause joiner
found the LAST comma in the finished sentence, so on any night the call cap
did not bite — most nights on 230 names — the liquidity clause's own
parenthetical was rewritten to "($12.4M/day and the 30th percentile)", and
alone it lost its comma outright; the fixture always had a score_cap clause
after it, which is why every check passed. Every liquidity_floor row was
archived with `streak: null` — the value the contract reserves for a run
that could not read its history — because the streak lookup covered the
kept candidates and not the refused ones; the round's 29 mutants never read
the refused row's streak. `slim_row()` dropped `dollar_volume`, so the
ledger held the floor on every entry and the number it was compared against
on no row. And the footnote test looped over three phrases for a round after
the fourth clause arrived, so the clause could be deleted from either
surface green — the "test that cannot fail" shape, on the sentence the
round's commit message named as swept. Smaller: `_count()` let a negative
count reach the funnel ("Below the liquidity floor: -2") and a float vetoed
count contradict the note beside it; both surfaces printed "the 1th
percentile" for any percentile ending in 1, 2 or 3; the email printed
"$12,400,000/day" beside a page printing "$12.4M/day" for one floor, and a
docs test now executes the page's own formatter through node against the
email's; a reason word the page did not know rendered as a gate rejection,
the one collapse the contract forbids; `snapshot_problem()` accepted a
`run.liquidity` in shapes no writer produces; the page told a run with the
rule off that it had enforced a floor; the noliquidity smoke check's ladder
half ran against a page whose ladder is never rendered; and seven sentences
still enumerated three reasons. The contract walker checks round 5's
sentences now — the block's count against the rows, the rows against the
floor, the five populations against the record — and a test breaks each
one alone.

## Round 5 — rule 6's refusals reach every surface

The one round-4 finding deliberately left open, and the only one of
forty-six that survived the refuters: two of them reproduced it independently
through the real evening path before this round began. `apply_liquidity_gate()`
built `dropped`, logged it at INFO and returned `kept`, so a burst refused for
dollar volume below the session's percentile floor was in no count, no
`gated_out` row, no ledger row and no line of the email — the one refusal
class the contract's "every burst the scan found, scored or refused" did not
hold for, and the one whose outcomes the open decision about widening the
universe most needs, since the floor is the number that decision turns on.

`liquidity_split()` hands back both halves and the floor; `run_scan()` passes
the refused bursts to the caller through a `refused=` list, the same idiom as
`stats=`, and records `liquidity_floor` in the stats. The pipeline runs the
checklist on them anyway (the contract says every burst carries
`lynch_detail`, and a row archived without its measurements can never be
judged), archives them under `ledger.LIQUIDITY_REASON` — `liquidity_floor`,
deliberately not a `veto_` word, because those derive from `lynch.VETO_RULES`
and are judged on a frame the checklist has seen, while this one is judged in
the scanner against every other name that traded — counts them in
`run.bursts`, and writes `run.liquidity` (`pctile`, `floor` in dollars,
`refused`) into the run block and the ledger entry. Every gated row carries
`dollar_volume` now, so a refused row can be read against the floor.

**The fifth population is not part of the control, for the opposite reason
the crowded-out one is not.** `evidence.illiquid` sits beside `refused` with
the same shape and its own `enough`; its forward returns are bar prices on
names the rule says are too thin to be bought at them, so folding them into
the alternative would let the thinnest names flatter or damn the strategy on
returns nobody could capture. The contract sentence says so, the page's
ladder has a fifth row that says so, and the control verdict still compares
picks against what the STRATEGY refused, whose n the floor cannot move.

Every surface that enumerated three reasons enumerates four: the email's
funnel gets a line carrying the floor in dollars and the percentile when the
run recorded them ("Below the liquidity floor ($359,000,000/day, the 30th
percentile): 2"), the empty-shortlist note gets a clause for it — three
verdicts a burst can carry on a night nothing was scored, each printed only
when its count is not zero, so "1 refused outright by an absolute rule, 2
below the liquidity floor and 7 rejected by the 2LYNCH checklist" is one
sentence and none of its three facts is another — the streak footnote on
both surfaces names it, `LAST_OUTCOME` and `OUTCOME_SHORT` on both surfaces
carry it, the page's funnel caption and gated hint print the floor read off
`run.liquidity` rather than retyped, and a `noliquidity` smoke variant holds
a snapshot from before the block existed, which must not be told it enforced
a floor. The one-night fixture carries two refused rows under a $12.4M floor
(the remapper that lifts thin rows to a plausible volume had to learn to
leave those two thin — its lift put a $92M/day row under the floor, and the
generator's own assertion caught it), and the thirty-run history gained
eight ledger rows and an `illiquid` population of four setups from the real
gate running over the synthetic market, with forward returns filled by the
real code.

## Findings from the round-4 audit — the prose lens

The lens CLAUDE.md recorded as never having run before 3.3, run again over the
tree after the other four lenses' fixes landed. Nine findings and seven leads;
every one reproduced here by execution before it was touched, and the fixes
mutation-tested — 35 mutants over the new guards, 34 killed on the first pass.
The survivor was a shaped assertion of exactly this file's third kind: the
morning-time check used `in`, so changing one of README's two "8:30 AM ET"
mentions left the other to satisfy it. Every clock time README prints is a
set equality against the crons now.

**The contract the file carries omitted the word that exists to stop a
collapse.** README's `last_outcome` bullet named four outcomes; the
`_contract` block `src.ledger` writes into every `docs/data.json` named
three, and `veto_up_days` — the word that exists so a 6/6 name refused by an
absolute rule is never called a gate rejection — was the missing one. The
collapse README forbids, in the file's own documentation of the field, on
every run since 3.3. Every word the email and the page can render is checked
against the published sentences now, and README's bullet is held to the same
set.

**A `--tickers` run left a row the record could not tell from a scan.** The
four-name smoke test README documents writes `docs/ledger.json` like any
other run — one row per name, no marker — and the next real run on another
session read it as history: streaks starting on a night that scanned nothing,
scored rows counted as setups in the evidence, and `git add docs` committing
the lot. README said `git checkout docs/data.json` put everything back; it
never touched the ledger, which on a fresh clone is untracked, so the first
`git pull` after `evening.yml` commits a real one refuses to overwrite it.
Every run entry carries its `universe` now, in the ledger and in the page's
runs table, and README says how to put both files back. The row is still
written — the whole test suite and `tools/make_history.py` drive the pipeline
through this path, and a run that writes no record cannot be tested for what
it records. The ledger-size guard caught the block on the same commit: 11.04
MB became 11.07, which is what it is for.

**Nine numbers the docs quote were pinned nowhere, and two guards could no
longer fire.** The prose audit mutated the gate to 4/6, the cap to 99, the
retention to 999 runs, the fill window to two, the shortlist to 7, the evening
to 7:16 PM, the volume ratio to 9.5x, the price floor to $40 and the close to
17:15 at once, and the suite stayed green. One guard asserted a string the
pipeline could no longer produce in that shape; the other was conditioned on
a sentence step 3 swept out of `.env.example`. Both replaced: the diagram's
numbers are read off `ScanConfig`, `MIN_LYNCH_PASSES`, `MAX_TO_SCORE`,
`TOP_N`, `MAX_RUNS` and `FILL_WINDOW_RUNS`; the clock times are derived from
the workflow crons the way README derives them; the feed list and default
from alpaca-py's `DataFeed` and `DEFAULT_FEED`.

**The cache paragraph's arithmetic was wrong in two of its four conclusions,
and the two files quoting it disagreed on a third.** Break-even was given as
1.25/0.9 = 1.4 calls, which charges the whole cache write against the reads
as if the first call were otherwise free; it is 1 + 0.25/0.9 = 1.28. The
cached night was $0.13 in README and rounded from a different token count
than the "$0.24" beside it here, while README said $0.25. Recomputed from
the inputs the paragraph states: $0.25 uncached, $0.15 cached, 41% cheaper,
$37 a year — and a test now does that arithmetic from those inputs, so the
conclusions can only be wrong together. The saving was overstated by two
points and the nightly figure by two cents; the conclusion stands.

**And a verdict that contradicted its own score was archived as given.**
`knowledge/strategy.md` defines the verdict AS the score's band, and
`_validated()` derived it only for a word outside the rubric: a reply with
score 9.5 and verdict "skip" kept both, so the email ranked the name first
and printed skip beside it. The band is what is kept now and the
disagreement is logged, because a model that keeps doing it is worth knowing
about. Found as a lead argued from the code; reproduced before it was fixed.

Smaller, each reproduced: README said eight smoke variants beside a ninth
while `VARIANTS` served sixteen beside `nodata`, and the smoke script now
checks that number the way it checks its own count of checks; this file said
"both are pinned by tests" of a rule nothing in the code can see; the
one-night fixture's README called it "the page on its first day" while its
`runs[]` and streak blocks describe a seven-session history and its
`evidence` the one run it holds rows for — two records in one file, by
design, and now said so; `strategy.md` told the model `Y` fails at 15% when
it also fails at a 25% run-up over the month, and asked for relative strength
against a market no input carries; `evening.yml`'s persist comment was the
third copy of the retracted "failed every night" story; a `ScanConfig`
comment described a field deleted in step 4. What the relative-strength
bullet now says is what the inputs can support, which is also where a
benchmark series would go if one is ever added.

## Findings from the 3.3 audit — three auditors, every one finished

The process the brief asks for, run properly for the first time: three agents
over disjoint file sets, each working by execution, each re-running its
findings against a pristine `git archive` copy because this tree was being
edited under them. **All three finished** — including the prose/docs set,
which CLAUDE.md had recorded as never audited at all. Thirty-eight findings.
Every one was reproduced HERE before it was fixed, and two turned out to be
about my own harness rather than the code.

**The single highest-value pattern.** The commit put the veto's vocabulary in
four places on the page — `LAST_OUTCOME`, `OUTCOME_SHORT`, the gated-hint
sentence and the funnel caption — and pinned exactly one. Each of the other
three could be made to say "rejected at the gate" about a burst that passed
6/6, with the whole suite and every dashboard check green. All four are
asserted on their WORDS now, and the funnel's guard needed a `novetoes`
variant to pin at all: it is the branch for a snapshot written before the rule
existed, and no source exercised it.

**Six that were about the work being wrong, not untested:**

| what | how it was found |
|---|---|
| A second veto added to `src.lynch` alone left the suite green and killed the evening run on `KeyError`, after the scan was paid for — while the comment above the lookup promised that was impossible | an auditor added a realistic `gap_too_wide` rule and ran it. `VETO_REASONS` is derived from `lynch.VETO_RULES` now and nothing indexes into it; `veto_reason()` computes the word |
| `evaluate_2lynch` and `extra_context` cleaned the frame with different `dropna` sets, so one bar missing only its `High` made the veto count 2 and allow the burst while the metrics block told the model 3 | found by two auditors independently, reproduced on all five columns; both callers hand the measurements the frame as received now, and `_base()` is the one rule |
| "Both measurements are archived per candidate … so the evidence views can ask whether either separates the winners" was false twice over: the VETOED row carried no `context` at all, and `slim_row()` dropped the block before the ledger — the only durable file, and the only one with forward returns | reproduced by reading the fixtures. `gated_record()` takes `context` and `slim_row()` keeps it; 52 refusals now sit in the record beside their outcomes |
| An unhashable `streak.last_outcome` took the morning run down inside `LAST_OUTCOME.get()` — one field from a guard whose comment names that exact mechanism | driven through the real morning path. The sweep it prompted found `history_sessions`, which does not crash and instead renders "[1, 2] sessions in the record" |
| **The rounding class was declared closed on the one instance that could not fire.** `worst_base_day()` was rounded so the shown and compared numbers were one; four other checks went on printing one number and deciding on another, at 3.2% (N) and 0.8% (L) of frames | measured over 600 bursts, independently reproduced. Every measurement is rounded once now and both the verdict and the line read it |
| The email's funnel printed the veto-filtered count under "Passed 2LYNCH gate", so a 6/6 name was told it had failed the checklist — the one collapse this file forbids by name | reproduced on a real run. Refusals get their own line, and only when there are some |

**And the fixture generator had the same defect the commit had just fixed
elsewhere.** `make_ohlcv` got an `up_run` parameter because the veto's rate
was whatever the walk did; `tools/make_history.py` was not swept, and its rate
was 33% of every planted burst — a third of the record refused by nothing.
Worse, when the parameter went in, 19 of 184 bursts still missed their run:
a later burst's pre-window clobbered an earlier burst's, which is the
one-pass hazard that file already documents for burst days. Up-runs get their
own pass now. `VETO_RATE` is named for what it PLANTS and not for what comes
out, because 16 of the 17 further refusals are real — a name that bursts again
two sessions later has a genuine run of up days behind it.

**Three things the auditors settled that are worth keeping.** A check counted
among the 134 dashboard checks never opened the page — it compared Node-side
arithmetic to Node-side arithmetic over the fixture. A check asserting
`/worst base day/i` was asserting a label hard-coded in the page's own source,
so every row could print an em dash and pass. And a test of mine that this
file would call load-bearing was shaped: it put the NaN on the one offset
where pruning the bar changes nothing, and passed with the defect restored.
The precondition inside it is what makes the position load-bearing now.

## Findings from the 3.1 audit — twelve worked, one left standing

Three auditors were run over disjoint file sets after 3.1 (the process in the
brief: make the change, two agents audit, fix every finding, two verify).
**Two of the three finished; the third — the prose/docs auditor — never
started, and every one of the 39 verifier agents died on a session usage
limit.** The workflow's own summary therefore called all thirteen "refuted",
which is an artefact of a dead verifier returning null and not a judgement:
they arrived as leads, unchecked either way.

Twelve have since been reproduced HERE, by running them, and fixed. The
thirteenth is a restatement of a limit the tests' own docstrings already
carry. The auditors were right about every one that reproduced, and two of
their claims were right about the crash but wrong about the mechanism — both
noted in the table. **The prose/docs file set was never audited at all**, so
whatever that third agent would have found is still unfound.

The two auditors that did finish both worked by execution: the runtime one
drove 264 malformed shapes through the real morning path AND the real email
renderer (the sweep in 3.1(b) stopped at the dry run, which does not render
the email), and the fixtures one simulated a real commit-back into a copy of
the repo.

Two things that only running them settled, both worth keeping:
`streak.seen_before` sits behind a short-circuit that opens ONLY when `day`
is null, so a sweep varying one field at a time reports it safe — it needs
the pair. And `run.scored_by` does not crash on strings: `"5" + "1"` is
`"51"`, so the email rendered "Scored by Claude: 5 of 51", a fabricated
count, which is worse than a crash because nothing says it is wrong.

| severity | file | the claim | where it stands |
|---|---|---|---|
| high | `src/emailer.py` | the line 3.1(b) fixed still crashes the morning email: `seen_before` was left beside `day` and is still compared raw | **FIXED** — reproduced with `day` null AND a non-numeric `seen_before`; refused by `snapshot_problem()` now |
| high | `tools/dashboard_smoke.mjs` | the docs/-facing check counts the page's "Nothing to show." placeholder as a candidate row, so a real run that scores nothing turns CI red | **FIXED** — reproduced on a 1-burst/0-scored run; row counts exclude `.sc-empty` and a `quietnight` variant now runs the any-run checks in CI |
| high | `tools/dashboard_smoke.mjs` | the docs/-facing headline check hard-codes the plural "bursts", so a real run finding exactly one burst turns CI red | **FIXED** — reproduced on a 1-burst run; the smoke test pluralises, and the two fixture-facing headlines with it |
| high | `src/ledger.py` | `snapshot_problem()` exempts `run.status = null`, and null is exactly the value that crashes `follow_through` | **FIXED** — reproduced (`.get("status", "ok")`'s default applies to a MISSING key, not a null one); absent is fine, null is refused |
| medium | `src/pipeline.py` | `carried_problems()` raises on a non-iterable `run.errors`, and its docstring says it cannot | **FIXED** — reproduced with an int and a bool; `run.errors` must be a list |
| medium | `src/emailer.py` | an unhashable `streak.unknown_reason` crashes `_no_day_note()` on a snapshot `read_snapshot` accepts | **FIXED** — reproduced with a list and a dict; must be a string or null |
| medium | `src/emailer.py` | `run.scored_by` is shape-checked one level too shallow: its values crash or silently fabricate the provenance count | **FIXED** — does not crash, FABRICATES: the counts must be numbers now |
| medium | `src/ledger.py` | `SNAPSHOT_ROW_KEYS` is all-or-nothing over 23 keys of which only 9 are load-bearing, so the first morning after any schema-additive deploy refuses a genuine snapshot | **FIXED** — measured: exactly 9 of the 23 are load-bearing, the auditor's number. The required set is those 9, and it is now DERIVED by a test that drops each key and runs the real morning path, so it is not a hand-kept second copy of the emailer |
| medium | `tests/test_ledger.py` | the two tests guarding the `fsum` change cannot fail on the interpreter CI runs, so that commit reverts green there (this one is DOCUMENTED as such in the tests' own docstrings and in the note below — the auditor is restating a known limit, not finding a new one) | still a lead — see the note above |
| medium | `tools/make_history.py` | not deterministic: `CLAUDE_MODEL` leaks into the fixture, and the `MODEL` constant meant to pin it is never used | **FIXED** — reproduced (`CLAUDE_MODEL=claude-opus-4-5` changed `run.model`, so the guard failed for whoever had it set); `_patched()` pins `scorer.MODEL` now, which the unused `MODEL` constant existed for |
| medium | `tools/check_fixture_fresh.py` | nothing guards `docs/ledger.json`: the invented 30-run ledger can be dropped in, passes the guard and the suite, and the next real run adopts it and strips the fixture marker | **FIXED, more strongly than reported** — `Ledger.load()` refuses a ledger carrying `fixture: true` and sets it aside, the same rule `read_snapshot()` applies to `data.json`. That stops the pipeline adopting invented history at RUN time, not just in CI |
| low | `src/ledger.py` | `snapshot_problem()`'s `context` clause is neither tested nor load-bearing: it can be deleted with the suite green | **HALF FIXED, half refused** — "not tested" was true and now is not. "Not load-bearing" is also true, and the clause STAYS: a missing key is what an older pipeline wrote, a wrong-typed one is not something any version writes. That distinction is in the code now, because it is what reconciles keeping this with narrowing the key set |
| low | `tools/make_history.py` | the scorer-down comment states a window a week wider than the code searches | **FIXED** — it is six to fourteen sessions, stated as the range the code searches |

The two highest-value patterns in there, if the list is ever thinned: the
smoke test's docs/-facing checks were supposed to hold for ANY run and two of
them do not, which is the same class of defect 3.1(a) existed to close; and
the shape check stops one level short in three separate places, which is the
same class 3.1(b) existed to close. **Check that a fix did not introduce a new
defect of the same class** applies to 3.1 itself.

## Local run

```bash
pip install -r requirements.txt
cp .env.example .env              # single-quote every value
set -a; . ./.env; set +a          # this sources .env as a shell script
python -m src.pipeline evening --dry-run
```

`--dry-run` skips only the email; it still calls Alpaca and Claude.

## Rebuild order

1. ~~Repo hygiene — `.gitignore`, truthful `.env.example`, secret scanning~~ done
2. ~~Shrink the universe to a checked-in symbol list~~ done
3. ~~Fix the data request — split adjustment, freshness assertion~~ done
4. ~~Relative volume thresholds, percentile liquidity gate~~ done
5. ~~Fail loud~~ done
6. ~~6a: real tests, offline mode, CI · 6b: threshold + canary assertions~~ done
7. ~~Fix the 2LYNCH math (`L` is sign-blind, `Y` excludes the burst day)~~ done
8. ~~Harden the LLM layer (`temperature=0` — which is a TypeError in anthropic 1.x; it goes via `extra_body`)~~ done
9. ~~Persist every scored candidate plus forward returns~~ done —
   `docs/data.json` + `docs/ledger.json`, forward returns filled by later runs,
   and `evening.yml` commits `docs/` back so the history survives the container
10. ~~Resolve morning/evening and statefulness~~ done — the two modes are now
    two behaviours: `evening` discovers (scan → score → archive), `morning`
    follows through on what `evening` published and scans nothing, because
    before the open it would be reading the same daily bar for the same answer.
    Each mode declares which side of the 16:15 ET close it belongs on and
    degrades loudly when the clock disagrees, with the session it really read
    named in the subject line, above the table, and — on the evening run, the
    only one that writes a CSV — in that file's name. The REASON for a
    disagreement lands in the email, in `docs/data.json`'s `run.errors` and in
    the exit code; `add_run()` keeps a status word and not the sentences, which
    three separate places used to claim otherwise;
    `SCAN_SESSION_DATE` is exempt, since a pin is the user overruling the clock
    on purpose. And the ledger is finally READ as well as written: every burst
    carries a streak — day N of this setup, when the name was last seen, and
    what was DONE with it then (scored, rejected at the gate, or crowded out by
    the call cap: three different facts that "not scored" used to cover with
    one phrase) — with `ledger.MAX_STREAK_GAP_SESSIONS` holding the one
    judgement about what "the same setup" means. A record that cannot answer —
    unreadable, empty, or not reaching back far enough — publishes no day
    number and says which of the three it is, on every surface, in words. It
    never takes the run with it and never collapses into a confident day 1.
    The morning email carries no chart: `docs/charts/` is one file per ticker
    with no session in it, so a pass that reads it off disk cannot show the
    picture belongs to the numbers beside it (the evening email, which attaches
    what it just rendered, is unaffected).

All ten are done. Full-market scanning comes next, and the open decision below
is the first thing standing in front of it.

**The two Bonde rules the screener did not hold anywhere.** "Never buy after
3+ consecutive up days" and "no 4% breakdown during the pullback" were in
neither `src/lynch.py` nor `knowledge/strategy.md`, so the tool did not apply
them and could not have been asked to. They are in now, and **neither is a
seventh and eighth checklist item, which is the decision and not an
omission.** `MIN_LYNCH_PASSES` is 3 of 6 — HALF of them — so two more checks
would silently make it 3 of 8: a weaker gate wearing the same number, with
the six-check structure that `tools/make_fixture.py`, the email, the page and
every archived `lynch_total` are built on changed underneath them. (This
said "a MAJORITY" here, in `README.md` and in `src/lynch.py` until the prose
audit did the arithmetic. A majority of six is four. The argument the word
was supporting is untouched; the word was simply false, in three places, and
it was the stated justification for refusing the two rules as checklist
items — which is the worst kind of place for a wrong one.)

Each rule went where the way Bonde states it puts it. **Up days is cardinal**
("never buy") and is pure arithmetic on closes, so it is a VETO: it refuses
the burst before the pass count is consulted, and the archived row names the
rule. The case it exists for is a burst that passes 6/6 and is refused anyway
— `veto_up_days` is a third reason beside `lynch_gate` and `score_cap`, and
no surface may collapse it into either, because "rejected at the 2LYNCH gate"
states the opposite of what happened to a 6/6 name. **A 4% base breakdown is
a quality criterion**, so it is measured, judged against `BREAKDOWN_PCT`, and
handed to the scoring model as a `quality_notes` line that carries the figure
the code applied; `knowledge/strategy.md` names the criterion and deliberately
holds no second copy of the number. It rejects nothing on its own.

Two things this landed that were not the rules themselves. The synthetic
`burst` frame's run of up days was whatever its walk happened to do — three
or more on 8.5% of seeds, measured — so every end-to-end test in the suite
carried an undeclared one-in-twelve chance of scanning a universe whose only
candidate was refused; five really did, and they failed by finding zero
candidates, which reads as a broken scan. `make_ohlcv`'s `up_run` is a
parameter now. And the page's per-check view split every burst into "cleared
the gate" and "failed the gate" using the pass count, which stopped being the
same thing as the gate: a 6/6 vetoed row would have landed on the failed side,
six passing checks counted as evidence that the checks reject. It is the
CHECKLIST's split now, said so in the column heading, and the smoke test pins
the difference against the vetoed count rather than asserting the two are
equal.

**UNVERIFIED AGAINST THE PRIMARY SOURCE.** stockbee.blogspot.com and
qullamaggie.net are both blocked by this sandbox's egress proxy — checked
with curl, not assumed — so three days and -4% come from the brief that
specified the work and NOT from Bonde's own words. They are named constants
for exactly that reason. Someone with access should check them.

**And so is the 8–20% band**, which this note used to omit while naming the
other two, though `ledger.CLAIMED_BAND` is sourced identically. It is the
number every published verdict about the strategy is measured against — the
page asks whether outcomes land in it, not merely whether they are positive
— so of the three it is the one most worth checking. Found by the prose
audit, which asked why one unverified constant carried the warning and its
sibling did not.

**Open decision — the universe is now 230 names.** Step 2 traded ~11,000 symbols
for a hand-curated list to make steps 3-8 testable in seconds instead of twenty
minutes. That is a real strategy narrowing, not just a speed fix: 4% momentum
bursts are most common in the small- and mid-caps this list excludes. The list is
a scaffold. Replacing it with a generated, screened universe is required before
this is a real screener, and it is not one of the ten steps above.
