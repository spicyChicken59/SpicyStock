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
| Step 3 sets `feed=` on the bars request | `.env.example`'s "no `feed=` is set anywhere" |
| Step 4 replaces the 5,000,000-share floor | the IEX paragraph in `.env.example`, the volume numbers in README's Costs note, README's Layer-1 filter description |
| Step 5 makes failures loud | `.env.example`'s "these fail in three different ways" block |
| Step 6 fixes the test suite | the `detect_burst` comment in `.gitignore`, the broken-test note in README |

## Standing rule: no line numbers in comments or docs

Cite functions, not `file.py:NN`. Three separate citations rotted inside a
single step's own commits. `get_clients()` is stable; `scanner.py:78` is not.

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
- **The test suite does not run.** `tests/test_pipeline.py` imports
  `detect_burst`; `src/scanner.py` defines `detect_setup`. There is no
  regression net until step 6. Assume nothing is covered.

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
2. Shrink the universe to a checked-in symbol list
3. Fix the data request — split adjustment, freshness assertion
4. Relative volume thresholds, percentile liquidity gate
5. Fail loud
6. Real tests, offline fixture mode, CI
7. Fix the 2LYNCH math (`L` is sign-blind, `Y` excludes the burst day)
8. Harden the LLM layer (`temperature=0`, structured outputs)
9. Persist every scored candidate plus forward returns
10. Resolve morning/evening and statefulness

Full-market scanning comes after all ten.
