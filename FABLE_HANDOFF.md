# Fable handoff — 23 October 2026

The user requested a safe stop and handoff to Fable. Development is paused. This
branch is a preserved checkpoint, **not ready to merge or deploy**. No new PR was
opened because current main already ships overlapping issuer work.

## Start here

- Repository: `spicyChicken59/SpicyStock`; local checkout `/workspace/SpicyStock`.
- Checkpoint branch: `codex/issuer-transaction-review`.
- Its base is `88e708f254988b7b11abb72f5b70ffca40a64050` (PR #184).
- Last fetched main: `503193eab5dff16a505f2b90c34abc8b40446799`.
- Read current `PRODUCT_GOAL.md` and `CLAUDE.md` from main before resuming. Main
  has advanced through PRs #185–#189 and new production publications.
- Start a fresh branch from current main and selectively reconcile useful work
  from this checkpoint. Do not replace current main's files wholesale.

The product goal remains dependable morning trading preparation for a $2,000
Fidelity cash account in America/Chicago. Missing evidence must stay missing;
no manufactured tickets, claimed trading success, broker execution, new paid
infrastructure or new outbound messages are authorized by this handoff.

## Preserved changes

**Issuer transaction metadata:** `src/issuer_evidence.py` and
`docs/app-issuer-evidence.js` add optional `index.transaction_filings`. It records
eight merger/tender forms including amendments, the newest twelve observations,
observed/omitted counts, and each filing's exact retained recent/history index
source. The UI distinguishes positive, zero, partial, unavailable and legacy
coverage without asserting an active transaction or clearing event risk. It
adds no SEC calls or document downloads and does not change trade authority.

Tests include `tests/test_issuer_transactions.py`, producer-generated variants
in `tests/fixtures/issuer-evidence`, reconciliation counts, and browser cases in
`tools/issuer_evidence_cases.mjs`. README describes the draft behavior. The local
CLAUDE suite inventory is updated to the measured 4,847 tests on this old base.
No environment variables were added; `.env.example` was checked and unchanged.

**Critical overlap:** main already has PR #185's `index.acquisition_review`
collector, validators and UI. The draft's potentially useful additions are
`PREM14A/A` and `DEFM14A/A`, explicit zero/unknown states, omitted counts and
per-filing source attribution. Main and this draft accept different optional
extension keys. Preserve readability of already published `acquisition_review`
receipts, avoid duplicate sections and counts, and regenerate fixtures through
the actual producer after reconciliation. This concern came from source
comparison; it is not a completed compatibility execution review.

**Per-plan acknowledgements:** `docs/app-morning.js` clears all four manual
preparation checkboxes when the selected plan identity changes. Cash is retained;
fees/quantity retain their existing reset behavior. `tools/cash_preview_cases.mjs`
adds switch/back and same-plan refresh controls at phone and desktop widths.
Neither file changed remotely between this branch's base and the fetched main.

## Verification and known failure

Durable logs are in `release-evidence/2026-10-23-fable-handoff/`.

- Handoff run: 137 issuer Python tests passed across `test_issuer_transactions`,
  `test_issuer_evidence`, and `test_issuer_evidence_reconciliation`.
- Handoff run: issuer generator `--check` confirmed all 42 fixtures current.
- Handoff run: 42 documentation tests passed; collection found 4,847 tests.
- Earlier completed run on the preserved issuer implementation: 537/537 issuer
  browser checks passed. Phone/desktop screenshots were inspected.
- **Current morning/cash browser run failed:** the added same-plan refresh
  control calls `SCStock.render(...)`, then its observation-state `wait(page)`
  times out after 30 seconds. The log is preserved. Determine whether the render
  invocation or expected observation state is wrong; do not count an earlier
  553/553 baseline as validation of these final test bytes. The remaining
  assertions after this timeout were not reached. Cash screenshots before the
  timeout were inspected at 390 and 1280 pixels.
- `git diff --check` passed before the checkpoint commit.
- Independent review is **incomplete**, with no approval to merge. Broader
  issuer suites and isolated mutation runs lost their sessions during an
  environment replacement; their completion is unverified. Local full-suite,
  full-browser, mutation, chart and secret-scan gates remain outstanding.
- No related tests, mutation harnesses or development servers remain running.

No production data, immutable history or deployed files were changed by this
checkpoint. PR #184's earlier successful hosted CI and public verification are
historical evidence only, not verification of this draft or today's main.

## Next steps for Fable

1. Fetch main and inspect current production and PR state. Reconcile issuer
   work with the shipped acquisition schema before attempting a release.
2. Carry the independent checkbox fix onto current main, repair the failing
   test control, and prove reset-on-change plus preservation-on-same-plan with
   the final browser tests. Repeat omitted-reset, quote-only-reset,
   unconditional-reset and unrelated-control mutations in isolated copies.
3. Finish issuer validation/mutation coverage and independent review; rerun
   producer fixture checks and relevant gates on the reconciled commit.
4. Only then consider a normal PR, required CI, merge and actual public
   acceptance under the user's current instructions. This handoff does not
   claim the larger product goal is complete.

The earlier proposal for a repository-evidence service acceptance streak was
design only in this workspace: no service implementation, tests or report were
started. Main has since gained morning service work in PRs #186–#188; inspect
that implementation before considering further service changes.

Local tools: Python `/workspace/spicystock-venv/bin/python` (3.12.14), Node 24,
and `PLAYWRIGHT_BROWSERS_PATH=/workspace/pw-browsers`. Relevant commands:

```sh
/workspace/spicystock-venv/bin/python -m pytest -q tests/test_issuer_transactions.py tests/test_issuer_evidence.py tests/test_issuer_evidence_reconciliation.py
/workspace/spicystock-venv/bin/python tests/fixtures/issuer-evidence/generate.py --check
/workspace/spicystock-venv/bin/python -m pytest -q tests/test_docs.py
PLAYWRIGHT_BROWSERS_PATH=/workspace/pw-browsers node tools/page_smoke.mjs --only issuer,cashpreview,morning --shots /tmp/fable-review
```
