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

## The shape now

`pipeline.run_evening()`: preflight → universe → fetch (chunked, budgeted)
→ session state from the bars → breadth → scan and checklist → charts and
Claude (down-only) → plans and the cash budget → the record (`picks.json`,
open plans, scorecard) → `report.build()` and validate → email. Exit codes
0/1/2/3; seven problem words; `run.status` closed on a closed night.
`run_intraday()` is dispatch-only and never commits.

The page (`docs/app.js`) computes one thing — the status chip from the
record's session and the ET clock — and prints everything else verbatim,
including the six cover sentences and the plan instructions. The chart
(`docs/app-chart.js`) is annotated SVG on the SpicyChicken design system
snapshot under `docs/design-system/`.

What is measured offline: 970 tests, the chart check, and the page smoke
over six fixtures plus the stale and no-record states. What is NOT: the
full-market fetch time from a runner (the dry-run dispatch measures it), a
real Claude reply to a real chart, Resend delivering, Pages building after
the commit-back. Each of those is observed on the first live night, and
this file should record what each one found.

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

## Open leads, written down rather than worked

- An upper bound on the day's gain is a strategy decision this build does
  not take; a ≥15% day halves the size as a hazard and is never a veto.
- The scorecard's fill rule is the ticket's own mechanics on daily bars; a
  fill inside the zone at the open is assumed to be at the open.
- `MAX_READS` is twelve by mechanical grade; a night with more A-quality
  bursts than that grades the rest by the checklist alone (`claude_partial`
  is not raised for those, only for names asked and unanswered).
