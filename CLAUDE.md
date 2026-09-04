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
| The universe widens past `data/symbols.txt` | the 230-name figures in README's diagram, Tuning and Costs sections |

Nothing else is scheduled to go stale: step 10 was the last of the ten. The one
row left is the open decision at the bottom of this file, not a step.

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
predicted.

## Environment constraints

- **No live market data.** The sandbox proxy blocks Yahoo and Alpaca. Anything
  requiring a real trading day has to be validated by the user locally. Reason
  from the SDK and synthetic frames instead; do not fake a result.
- **Free Alpaca plan.** No SIP subscription. The IEX feed carries a fraction of
  consolidated volume, which is why the absolute share threshold has to become
  a relative one (step 4).
- **There is a regression net.** `pytest tests/` runs 685 tests with no network
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
  Still untested: anything needing a socket — that the credentials can query the
  feed, that Resend delivers, that Claude returns what the parser expects from a
  real chart.

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

  **And `evening.yml`'s commit-back has still never executed.** Every streak,
  and the morning run's entire input, rest on it; the `git add` bug that voided
  it is fixed and guarded by a test, but no run has yet reached the push at all,
  so the push-and-rebase loop below it has never once run in anger. It was
  traced with `bash -ex` against a stub `git` — three attempts really happen
  now, where the old loop aborted after one — but that is a simulation, not a
  run. This is the second time this step was believed done and was not. Watch
  the first evening run after this lands.

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

**Six have since been reproduced and fixed** — the two smoke-test ones and
four of the shape ones — and the table says which. The auditors were right
about every one of the six, and all six were introduced by 3.1 itself, which
is the rule about not replacing a bug with one of the same class failing on
the round that wrote the rule down.

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

**Open decision — the universe is now 230 names.** Step 2 traded ~11,000 symbols
for a hand-curated list to make steps 3-8 testable in seconds instead of twenty
minutes. That is a real strategy narrowing, not just a speed fix: 4% momentum
bursts are most common in the small- and mid-caps this list excludes. The list is
a scaffold. Replacing it with a generated, screened universe is required before
this is a real screener, and it is not one of the ten steps above.
