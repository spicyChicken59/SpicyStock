# Historical input run 6: September 24–25 RED on a later retrieval of every intended stock

**Verdict: RED reproduces on both sessions.** The later retrieval completed all
97 queries and returned target-day and prior-day bars for every intended stock.
263 symbols per session still miss some required sessions. The independent
calculator and the production breadth code agree on identical inputs under both
later-eligibility policies. Under C, every allowed completion of the unknown
contributions keeps the 10-session ratio below 1.0. Under D there are no unknown
contributions and the ratio is exact.

The receipt says BLOCKED because the reconciliation's strict establishment rule
is not met: six counted stocks lack an input the up-50%-in-a-month test reads.
It is not a disagreement between the calculators. Comparison B, the exact
original population, stays BLOCKED, because the original price-exclusion mask
was never retained.

Market numbers here come only from the owner's price-free local summary. Public
facts come from GitHub. Decrypted evidence stays on the owner's computer.
Nobody else read it, and Guidance private review is NOT RUN.

## Execution identity (public)

[Machine record](2026-10-02-historical-run6-evidence/public-run.json): REST
endpoints read on 2 October, plus verbatim job-log lines read on 1 October.

| Field | Value |
| --- | --- |
| Run / native number / attempt | `36815689950` / 6 / 1, `workflow_dispatch`, `historical-input-real` |
| Job | `110220126196` (`execution`) |
| Dispatched | 2026-10-01T04:33:41Z by spicyChicken59 on `main` |
| Workflow revision | `a900236900be6e531cc3c0c0e9b0547269861ec8` (docs-only publication on top of the #98 merge; the guard ran from this checkout) |
| Execution checkout | `d6d774346015c3d2abfe7b7318316292daab57cb`, the reviewed PR #98 head |
| Readiness | Owner comment `5924734477` on PR #98, created 2026-10-01T04:26:41Z, never edited |
| Artifact | `11142297138`, 107,315,902 bytes, `sha256:043af0b3abe27fb47cd00c65b601617f23aa7846993d5e5ea02c94267438f1b3`, expires 2026-10-08T05:06:39Z |

The guard admitted the execution checkout, and step 7 checked it out. The
`tools/`, `src/` and `.github/` trees are identical at both revisions.

The readiness comment carried the candidate from `5921715962` with only
`authorized_on` changed to its own UTC posting date. The owner dispatched on
that readiness. Guidance comment `5921505729` required a separate explicit
release, and none was posted. The guard reads only the owner's readiness
comment. Its date check on that comment is named
`execution_release_not_after_merge`.

## Pre-dispatch checks (retained receipts)

These ran on 1 October, before dispatch, against live GitHub data. The receipts
are under [`predispatch/`](2026-10-02-historical-run6-evidence/predispatch/).

- **Guard dry run.** The actual guard's `verify()` and `main()` ran with only
  three things synthesized: the prospective readiness comment, run and job.
  Both passed. All sixteen negative controls were refused for their intended
  reasons, and a second dispatch queued as native 7 was refused. The first run
  was against `main` at `5d9b9ad` (`guard-dry-run-first.txt`,
  `guard-dry-run-extra-results.json`). It was repeated after the evening
  publication moved `main` to `a900236`, with the same outcome
  (`guard-dry-run-rerun-after-evening-commit.txt`, `guard-dry-run-results.json`).
- **Real comment.** The same harness then read the real comment `5924734477`
  live, with only the run and job synthesized, and passed. Wrong mode and
  native 7 were refused (`real-comment-check.txt`, captured from the session).
- **Later steps.** Preflight passed from a `d6d7743` checkout in an empty
  network namespace. The pinned age download and recipient validation passed,
  and a bad-checksum recipient was refused.
- **Boundary step.** The input-checking step was run in 50 cases
  (`boundary-step-results.json`).

## Public step outcomes

| Step | Outcome | UTC |
| --- | --- | --- |
| Boundary, checkout, runtime, age | success | 04:33:46–04:34:14 |
| Guard (from `a900236`) | `{"status":"PASS"}` | 04:34:14–04:34:31 |
| Checkout of `d6d7743` | success | 04:34:31–04:34:37 |
| Preflight and recipient | PASS / PASS | 04:34:37 |
| Synthetic rehearsal | skipped (real mode) | — |
| Acquisition | `status PASS`, `synthetic false` | 04:34:37–04:48:44 |
| Offline reconciliation | `status BLOCKED`, exit code 2 | 04:48:44–05:06:03 |
| Package | `{"status":"PASS"}` | 05:06:03–05:06:39 |
| Upload and receipt binding | success | 05:06:39–05:06:42 |

The job concludes `failure` because the offline step exits 2 on any non-PASS
status, by design. The package, upload and receipt steps run under `always()`.

## Owner-side recovery (owner-reported)

The owner reported finishing local recovery on 2 October and pasted the
summary. The [helper](2026-10-02-historical-run6-evidence/open-run6.ps1) does
the following in order:

1. Refuses a zip whose size or SHA-256 differs from GitHub's artifact record.
2. Requires a SpicyStock clone whose `tools/` equals `d6d7743`.
3. Decrypts with the owner key through `tools/historical_package.py recover`,
   against an [expected execution](2026-10-02-historical-run6-evidence/expected-execution.json)
   built from GitHub-verified facts. That file was validated by the
   repository's own `_execution()` before use.
4. Runs the [summarizer](2026-10-02-historical-run6-evidence/summarize_run6.py),
   which prints no prices, volumes or raw pages.

The helper's own step lines were not retained, so the download and digest check
are owner-reported. The [summary](2026-10-02-historical-run6-evidence/owner-summary.txt)
itself is verbatim.

Before the owner ran it, a Linux copy of the helper was rehearsed on a synthetic
package encrypted to a disposable key. It differs only in path separators, the
age binary name, the synthetic digest and size, and a synthetic `--manifest`
([diff](2026-10-02-historical-run6-evidence/predispatch/helper-rehearsal-adaptation.diff)).
It passed, and it refused a tampered zip, a wrong execution identity and an
existing destination ([log](2026-10-02-historical-run6-evidence/predispatch/helper-rehearsal.txt)).

## Acquisition accounting (owner summary)

All 97 frozen queries completed: the SPY probe and 96 bulk chunks. The
persistent ledger charged **289 request slots** against the 400-slot cap,
exactly the manifest's planning estimate. It retained **275,899,601
uncompressed bytes** against the 1 GiB cap, with zero unresolved byte
reservations. The provider spend ceiling was $0.

## Results against the original publications

Original values come from the [September 28 report](2026-09-28-historical-input-proof.md)
and its [machine evidence](2026-09-28-historical-input-evidence/original-reconciliation.json);
the original candidate counts are its `original_candidate_count`.

- **C** re-evaluates target-day eligibility on the later bars.
- **D** applies the same rule on each of the ten event days, a counterfactual
  policy. D's breadth population and $3 cut below are target-day values.

| Quantity | Sep 24 original | Sep 24 C | Sep 24 D | Sep 25 original | Sep 25 C | Sep 25 D |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Breadth population | 3,716 | 3,738 | 3,738 | 3,700 | 3,729 | 3,729 |
| Cut by the $3 rule | 1,047 | 1,041 | 1,041 | 1,058 | 1,051 | 1,051 |
| 10-session up / down | 1,323 / 1,414 | 1,333 / 1,426 | 1,337 / 1,434 | 1,254 / 1,410 | 1,262 / 1,419 | 1,278 / 1,430 |
| 10-session ratio | 0.94 | 0.93 | 0.93 | 0.89 | 0.89 | 0.89 |
| Outer bounds over unknowns | — | 0.92–0.95 (17) | 0.93 (0) | — | 0.88–0.90 (13) | 0.89 (0) |
| 5-session ratio | 0.78 | 0.79 | 0.78 | 0.79 | 0.79 | 0.79 |
| Target-day up / down | 92 / 141 | 92 / 142 | 92 / 142 | 84 / 67 | 84 / 68 | 84 / 68 |
| Verdict | RED | RED | RED | RED | RED | RED |
| Diagnostic scan matches | 418 candidates | 418 | — | 455 candidates | 455 | — |

The number in parentheses is the count of unknown contributors to the outer
bounds. The summarizer's "could be anywhere in" line reports these bounds,
whose endpoints need not be jointly attainable.

**The same rules fire in every column:**
- the 10-session RED rule (`red_ratio_10d`);
- the 10-session YELLOW rule (`yellow_ratio_10d`);
- the up-50%-in-a-month YELLOW rule. The original record names it
  `yellow_up50_month`; the reference calculator names it `yellow_up50_month_hot`.

The 5-session fast-selling rule (below 0.5 with more decliners) and the scaled
down-event alarm do not fire. The production regime matches the independent
calculator in both modes on both sessions (`same_input_formula_status` PASS).

Against the original, the 10-session totals move by +10/+12 and +8/+9 under C,
and by +14/+20 and +24/+20 under D. The equal diagnostic-scan counts are counts
only, not a name-by-name match, and involve no grading, reader or ticket.

**Every intended stock had readable bars** for the target day and the session
before it in the later retrieval. The only target-day population reasons are
eligible and below $3. That includes the 16 and 22 stocks originally stale. It
shows current availability only, not availability at the original fetch time,
and no cause.

## Why the status is BLOCKED

The session status and `reconstructed_regime_established` are evaluated on C.
Establishment requires four things:
- C's reference regime was computed;
- no counted stock has an unknown 4% event in the ten sessions;
- the target day's up-50%-in-a-month count has no unknowns;
- no symbol is `failed`, `unresolved` or `requested`.

The first and last hold. The middle two do not.

**Six counted stocks block it.** ETRA, GIXI, OIG, TEVA, TRBG and WCCB lack at
least one input the monthly test reads (the close 20 sessions back, or the
trailing 20-session close and volume window), so their up-50%-in-a-month result
is unknown on both target days. Under C, four of them (ETRA, OIG, TEVA and WCCB)
also have an unknown 4% event within the ten sessions.

**D carries no unknown 4% events by construction.** It drops a stock on any
session whose own or prior bar is missing. D's own establishment flag is still
false, because of the same six monthly unknowns.

**Neither gap can move the verdict:**
- **The ratio can't reach 1.0.** C's coupled outer bounds cover every allowed
  up/down completion of the unknown contributors, and they stay under the 1.0
  RED threshold: 0.92–0.95 and 0.88–0.90.
- **The monthly unknowns only feed a YELLOW rule that already fires.** Its count
  includes only known up-50% events, so resolving an unknown can only add to
  it. RED takes precedence in any case.

**263 symbols per session are `partial`:** they miss some of the 288 required
sessions. The other 4,517 and 4,518 returned complete windows. The per-session
totals, 4,780 and 4,781, include SPY. No cause is assigned to any partial
symbol. The predeclared discrepancy classes apply, and none is adjudicated here.

## Comparisons, updated

| Comparison | Status after run 6 |
| --- | --- |
| A Original publication | PASS (unchanged, September 28). |
| B Pinned original population | BLOCKED: the original final price mask was not retained. |
| C Later retrieval, target-day eligibility | Formula PASS. RED on both sessions, unchanged across all allowed completions of the unknowns. Strict establishment BLOCKED by six counted stocks' history; this sets the session status. |
| D Per-observation-day eligibility | Formula PASS. RED on both sessions with exact ratios. D's own establishment flag is false (the six monthly unknowns); it does not set the session status. |

## What this does not establish

- **Not the original information set.** The bars are a later retrieval, and the
  breadth population is re-derived from them. No cause is assigned to the
  differences in the totals.
- **No trading result.** It establishes no reader approval, grade, plan, ticket,
  model outcome or trading edge, and changes no rule or threshold.
- **No independent review of the plaintext.** Only the owner has read it, so
  Guidance private review is NOT RUN.
- **Not a new attestation of rights.** The owner's personal-use authorization is
  not provider consent.

## Next

Nothing remains for this workflow. Native 6 was its only remaining slot, and no
further dispatch is admitted. The artifact expires on 8 October. The owner keeps
the downloaded zip and the recovered folder privately. The method's own open
question is unchanged: a prospective qualifying ticket on a GREEN or YELLOW
session.
