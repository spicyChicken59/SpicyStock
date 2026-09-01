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

## Environment constraints

- **No live market data.** The sandbox proxy blocks Yahoo and Alpaca. Anything
  requiring a real trading day has to be validated by the user locally. Reason
  from the SDK and synthetic frames instead; do not fake a result.
- **Free Alpaca plan.** No SIP subscription. The IEX feed carries a fraction of
  consolidated volume, which is why the absolute share threshold has to become
  a relative one (step 4).
- **There is a regression net.** `pytest tests/` runs 568 tests with no network
  and no API keys (step 6a). The scan filter's thresholds ARE asserted (step 4)
  and the 2LYNCH checks are too (step 7), each mutation-tested; step 6b
  re-mutated both — 88 mutants, 84 killed, and the four survivors are each
  provably equivalent or measure-zero (`>=`→`>` on a float boundary the grid
  steps over), not gaps. Step 10 mutated its own additions the same way — 38
  mutants over the mode/clock check, the streak arithmetic and the morning
  mode, all 38 killed, and its three first-round survivors closed with the
  tests they showed were missing rather than argued away. One of those was not
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
  which the previous round of these notes said was impossible. Run it. The
  script now checks README's claim about how many checks it is, so that number
  cannot rot the way three others in this repo already did. The streak
  line the page carries was additionally rendered against a data.json holding
  every streak state and read back from the DOM, rather than argued about, and
  five of those wordings are asserted in the script now: the email and the page
  had drifted apart on the null-`day` sentence, on the verdict after a scored
  last appearance, on "day N **of this setup**", and on what the gated table
  calls a burst the call budget crowded out — two vocabularies for one
  mechanism, side by side on one page, under two comments each claiming they
  matched.

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
