# Historical input run 6: September 24–25 RED on later complete data

**Verdict: RED reproduces on both sessions from a complete later retrieval of
every intended stock.** The independent calculator and the production breadth
code agree on identical inputs. Every completion of the unknown contributions
keeps the 10-session ratio below 1.0, so no unknown can change the verdict. The
receipt says BLOCKED because the reconciliation's strict completeness rule is
not met: six counted stocks lack the history some measures need. It is not a
disagreement. Comparison B, the exact original population, stays BLOCKED,
because the original price-exclusion mask was never retained.

This report quotes public GitHub facts and the owner's price-free local summary.
Decrypted evidence stays on the owner's computer. Nobody else read it, and
Guidance private review is NOT RUN.

## Execution identity (public)

[Machine record](2026-10-02-historical-run6-evidence/public-run.json), read
from the GitHub REST API on 2 October.

| Field | Value |
| --- | --- |
| Run / native number / attempt | `36815689950` / 6 / 1, `workflow_dispatch`, `historical-input-real` |
| Job | `110220126196` (`execution`) |
| Dispatched | 2026-10-01T04:33:41Z by spicyChicken59 on `main` |
| Workflow revision | `a900236900be6e531cc3c0c0e9b0547269861ec8` (docs-only publication on top of the #98 merge) |
| Guard checkout | `d6d774346015c3d2abfe7b7318316292daab57cb`, the reviewed PR #98 head |
| Readiness | Owner comment `5924734477` on PR #98, created 2026-10-01T04:26:41Z, never edited |
| Artifact | `11142297138`, 107,315,902 bytes, `sha256:043af0b3abe27fb47cd00c65b601617f23aa7846993d5e5ea02c94267438f1b3`, expires 2026-10-08T05:06:39Z |

The comment carried the candidate from `5921715962` with only `authorized_on`
changed to its own UTC posting date. The owner dispatched on that readiness.
The separate explicit release that Guidance comment `5921505729` required was
never posted, and the guard does not check for one.

Before dispatch, the actual guard ran against live GitHub data with only the
prospective comment, run and job synthesized. It passed, and every negative
control was refused for its intended reason. It was re-run against the real
comment `5924734477` before dispatch and passed. The boundary step, preflight,
pinned age installation and recipient check also passed offline.

## Public step outcomes

| Step | Outcome | UTC |
| --- | --- | --- |
| Boundary, checkout, runtime, age | success | 04:33:46–04:34:14 |
| Guard | `{"status":"PASS"}` | 04:34:14–04:34:31 |
| Preflight and recipient | PASS / PASS | 04:34:37 |
| Acquisition | `status PASS`, `synthetic false` | 04:34:37–04:48:44 |
| Offline reconciliation | `status BLOCKED`, exit code 2 | 04:48:44–05:06:03 |
| Package | `{"status":"PASS"}` | 05:06:03–05:06:39 |
| Upload and receipt binding | success | 05:06:39–05:06:42 |

The job concludes `failure` only because the offline step exits 2 on BLOCKED,
by design. The package, upload and receipt steps run under `always()`.

## Owner-side recovery

On 2 October the owner downloaded the artifact and checked its size and SHA-256
against GitHub's record. The owner then decrypted it locally with the owner key
through `tools/historical_package.py recover`, from a clone at current `main`,
whose `tools/` matches the guard checkout. The `--expected-execution` input was
built only from GitHub-verified facts and validated by the repository's own
`_execution()` before use ([file](2026-10-02-historical-run6-evidence/expected-execution.json)).
The [helper](2026-10-02-historical-run6-evidence/open-run6.ps1) and
[summarizer](2026-10-02-historical-run6-evidence/summarize_run6.py) were
exercised on Linux beforehand, on a synthetic package with a disposable key.
That covered the complete pass, a tampered zip, a wrong execution identity and
an existing destination. The summarizer prints no prices, volumes or raw pages.
Its verbatim [output](2026-10-02-historical-run6-evidence/owner-summary.txt) is
the only source of the market numbers below.

## Acquisition accounting

All 97 frozen queries completed: the SPY probe and 96 bulk chunks. The persistent
ledger charged **289 request slots** against the 400-slot cap, exactly the
manifest's planning estimate. It retained **275,899,601 uncompressed bytes**
against the 1 GiB cap, with zero unresolved byte reservations. The provider
spend ceiling was $0.

## Results against the original publications

Original values are from the [September 28 report](2026-09-28-historical-input-proof.md).
C re-evaluates target-day eligibility on the later bars. D applies the same
rule on each of the ten event days, a counterfactual policy.

| Quantity | Sep 24 original | Sep 24 C | Sep 24 D | Sep 25 original | Sep 25 C | Sep 25 D |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Breadth population | 3,716 | 3,738 | 3,738 | 3,700 | 3,729 | 3,729 |
| Cut by the $3 rule | 1,047 | 1,041 | 1,041 | 1,058 | 1,051 | 1,051 |
| 10-session up / down | 1,323 / 1,414 | 1,333 / 1,426 | 1,337 / 1,434 | 1,254 / 1,410 | 1,262 / 1,419 | 1,278 / 1,430 |
| 10-session ratio | 0.94 | 0.93 | 0.93 | 0.89 | 0.89 | 0.89 |
| Ratio range over unknowns | — | 0.92–0.95 (17) | 0.93 (0) | — | 0.88–0.90 (13) | 0.89 (0) |
| 5-session ratio | 0.78 | 0.79 | 0.78 | 0.79 | 0.79 | 0.79 |
| Target-day up / down | 92 / 141 | 92 / 142 | 92 / 142 | 84 / 67 | 84 / 68 | 84 / 68 |
| Verdict | RED | RED | RED | RED | RED | RED |
| Diagnostic scan matches | 418 candidates | 418 | — | 455 candidates | 455 | — |

The number in parentheses is the count of unknown contributors to the ratio range.

In every column, exactly the original three predicates fire: `red_ratio_10d`,
`yellow_ratio_10d` and `yellow_up50_month_hot`. The 5-session selling rule
(below 0.5 with more decliners) and the scaled down-event alarm do not fire.
The production regime agrees with the independent calculator in both modes on
both sessions (`same_input_formula_status` PASS). The equal diagnostic-scan
counts are counts, not a name-by-name match, and involve no grading, reader or
ticket.

Every intended stock had readable target-day and prior-day bars in the later
retrieval. The only target-day population reasons are eligible and below $3.
That covers the 16 and 22 stocks originally stale. It shows current
availability only: it does not establish availability at the original fetch
time, or any cause.

## Why the status is BLOCKED

`reconstructed_regime_established` requires two things. No counted stock may
have an unknown 4% event in the ten sessions. And the target day's
up-50%-in-a-month count may have no unknowns. Six counted stocks (ETRA, GIXI,
OIG, TEVA, TRBG, WCCB) lack the complete 20-session close and volume window the
monthly test needs, on both target days. Under C, four of them (ETRA, OIG, TEVA, WCCB) also have an unknown
4% event within the ten sessions. Under D they have none, so D's ratio is exact.
Neither gap can move the verdict:

- The coupled outer bounds cover every allowed up/down completion of the
  unknown contributors. The whole range stays under the 1.0 RED threshold:
  0.92–0.95 and 0.88–0.90.
- The monthly count feeds only `yellow_up50_month_hot`, which already fires on
  the known count. Resolving an unknown can only add to it, and RED takes
  precedence in any case.

263 symbols per session are `partial`: they miss some of the 288 required
sessions. The rest returned complete windows (4,517 and 4,518; both counts include SPY).
No cause is assigned to any partial symbol. The predeclared discrepancy classes
apply, and none is adjudicated here.

## Comparisons, updated

| Comparison | Status after run 6 |
| --- | --- |
| A Original publication | PASS (unchanged, September 28). |
| B Pinned original population | BLOCKED: the original final price mask was not retained. |
| C Later retrieval, target-day eligibility | Formula PASS; RED on both sessions, invariant over all unknowns; strict establishment BLOCKED by six counted stocks' history. |
| D Per-observation-day eligibility | Formula PASS; RED on both sessions with no unknown 4% events; strict establishment BLOCKED by the same monthly unknowns. |

## What this does not establish

- **Not the original information set.** The bars are a later retrieval, and the
  breadth population is re-derived from them. The +10/+12 and +8/+9 differences
  in the 10-session totals are not attributed to any cause.
- **No trading result.** It establishes no reader approval, grade, plan, ticket,
  model outcome or trading edge, and changes no rule or threshold.
- **No independent review of the plaintext.** No reviewer other than the owner
  has read it, so Guidance private review is NOT RUN.
- **Not a new attestation of rights.** The owner's personal-use authorization is
  not provider consent.

## Next

Nothing remains for this workflow. Native 6 was its only remaining slot, and no
further dispatch is admitted. The artifact expires on 8 October. The owner keeps
the downloaded zip and the recovered folder privately. The method's own open
question is unchanged: a prospective qualifying ticket on a GREEN or YELLOW
session.
