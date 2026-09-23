# Consolidation quality source-fidelity audit — 22 September 2026

## Decision

**Keep the deterministic C rules. Correct their attribution and reader-facing
description.** C is a defensible but limited deterministic approximation of
Bonde's consolidation concept. Its precise base boundaries and numeric proxies
are not source-certified. Retained evidence demonstrates consequential
segmentation sensitivity, but does not establish a uniquely source-authorized
replacement. Rarity is not a defect and no threshold was optimized.

A current source-contract defect **is** reproduced: `knowledge/strategy.md`
presented a one-third giveback maximum as part of Bonde's own checklist and
listed lower volume as an ordinary C requirement. The exact giveback limit is
DERIVED, and code permits ordinary C at elevated base volume. Older comments
also juxtaposed reaction and anticipation length variants without their scopes.
The correction labels these choices, scopes the dated variants, and describes
volume's A+-only vote. Source comments, method/README and the prompt are corrected;
no executable quality statement, constant, score weight or reader authority rule
changes. New prompt bytes receive normal provenance identities.

This combines the defensible-approximation conclusion with explicit historical
variant handling and an unresolved segmentation-validation limit. It does not
claim the source proves every selected window correct, or that this sample proves
C's trading value. Guidance owns independent review and merge; Astra does not merge.

## Baseline, evidence and reproduction

Before branching, actual main and zero open PRs were checked against GitHub.
Main was `6533e616bd14ebfebeeccb4c9b1b0d463b47dbb4`, tree
`e711c3bd8bb7b11dda69b61e93208a455dc5584c`, the reviewed #86 merge.
Branch: `audit/consolidation-source-fidelity`. No intervening production commit
was substituted for this verified starting point. Exact submitted head and
automatic CI results are pinned in the PR and the CLAUDE checkpoint handoff.

Read: latest CLAUDE checkpoints, #85's retained-quality audit, #86's reader
audit, quality/scans/discovery/grader/reader-authority implementations, relevant
quality/provenance tests, all three requested knowledge contracts and the
supplied 16-page *Stockbee AQuality Setup and Momentum Burst Method: A Complete
Field Guide*. Source hierarchy is preserved in the new
[C source contract](../../knowledge/consolidation-quality.md): PRIMARY → LATER
BONDE → COMMUNITY → SpicyStock DERIVED → retained observations. The guide is
secondary, not a source of unprinted exact ratios.

The frozen #85 inventory provides **3,547 real reaction candidate-publication
rows**, nine publications across seven sessions, September 11–21. Same-session
revisions remain distinct; these are not 3,547 independent stocks/trades. The
latest-publication-per-session view has 2,766 rows and is reported separately.
No subsequent returns, future-session prices or fabricated reviewer opinions
enter selection or evaluation.

The [derived JSON](2026-09-22-consolidation-audit.json) contains pinned publication
commits/blobs/digests, exact histograms, intersections, boundary counts,
counterfactual membership, original-source verification and 35 stratified
cases. The [case book](2026-09-22-consolidation-cases.md) prints each selected
base/leg date interval, peak versus actual base high, low, counts, numerator and
denominator, volume means/ratios, C state and C A+ state. These are deterministic
reconstructions, **not human visual tests**. No raw-bar objects are duplicated.

Reproduce from this branch with the normal Python dependencies and full git
history:

```sh
python tools/audit_consolidation.py --output /tmp/consolidation-audit.json --cases /tmp/consolidation-cases.md
```

The tool blocks network sockets, verifies original publication hashes, compares
the mechanical quality AST (ignoring the attribution-only module docstring and
#86's `metrics_for_model` addition), reconciles all 3,547 stored assessments,
and replays all **1,846** reactions with retained exact frames using current
quality code. It separately extracts each publication's original source and
JSON into temporary storage and runs `verify_retained_publication.py`, covering
**1,871** later source rows including 25 anticipation rows. Earlier 1,701
reaction frames are unavailable: stored-check reconciliation is not raw replay.

Sample selection is deterministic: first eligible retained-frame row by
session/commit/ticker for each status, C A+, overall A+ without C A+, C-only
weighted failure, and each named boundary; nine explicitly identified geometry
cases supplement those strata. Selection uses no later performance. All 35
have provenance-backed frames from September 16 onward.

## Source findings

| Component | Strongest inspected evidence | Implementation classification |
|---|---|---|
| Base concept | Orderly pause/pullback, narrow bars, shallow depth; a preceding orderly advance | The highest-high/lowest-close algorithms and search lengths are DERIVED; no inspected source supplies a segmentation formula |
| 3–20 sessions | Bonde, January 4, 2014, reaction consolidation | Selected primary interval |
| 3–10 sessions | Bonde, February 19, 2015, anticipation | Later statement for a different scope; not a reaction replacement |
| 5–40 sessions | Bonde, January 16, 2018, reaction base/pullback, with no 4% breakdowns | Distinct later variant; not implemented as a complete version |
| Two-session / long partial | No source partial grade established | DERIVED half-credit policy; actual long range is 21–39 |
| Maximum one breakdown | Bonde, December 8, 2020: “no more than one 4% b/d in consolidation” | Selected later allowance; daily price-only counting/rounding is the implementation interpretation |
| One-third giveback | Unidentified secondary webinar port in older repository attribution; exact primary statement not verified | Shallow is sourced; 0.34 and its geometry are DERIVED |
| Quarter giveback for A+ | No verified primary exact cutoff | DERIVED stricter shallowness flag; “upper third” does not establish one-quarter |
| Tightness | Qualitative narrow bars / low volatility | Both numeric ratios and the normalization window are DERIVED |
| Base volume | Orderly volume in 2014; low volume in 2020 | Exact means, windows, strict rounded comparisons and A+-only requirement are DERIVED |

Primary URLs and access limits are in the source contract. The 2017 process
post supports orderly shallow consolidation, not an exact depth denominator.
The inaccessible 2024 X thread and unreviewed video audio cannot settle missing
rules. No named community interpretation was sufficiently verified to elevate
the secondary one-third attribution. The older 2016 volume quotation is not
needed as sole authority: directly inspected 2014/2020 text supports the
qualitative concept. This audit does not recertify other checklist letters.

## Why C fails frequently

**Retained production evidence:** PASS 304, PARTIAL 67, FAIL 3,176,
UNMEASURED 0; C A+ flag 32. Latest-per-session: PASS 248, PARTIAL 52,
FAIL 2,466, UNMEASURED 0; C A+ 22. The broad explanation survives removal of
same-session revision duplication.

| Unsatisfied clause | All 3,547 rows | Among 3,176 C FAIL | Sole unsatisfied clause among C FAIL |
|---|---:|---:|---:|
| Giveback > 0.34 | 2,877 | 2,877 (90.59%) | 414 |
| Length outside 3–20 | 2,184 | 2,117 (66.66%) | 94 |
| Breakdowns > 1 | 1,697 | 1,697 (53.43%) | 39 |
| Tightness > 1.0 | 652 | 652 (20.53%) | 24 |

These are overlapping diagnostic failures, not independently attributable
causes. Length-only violations also produce 67 PARTIAL rows; “outside 3–20”
does not always mean C FAIL. A total of 352 C FAIL rows have all five other
weighted letters PASS, limiting their score to eight; C is not itself a veto.
This can still be mechanical A. Range expansion/volume are contextual checks,
not additional weighted letters in that statement.

Pairwise overlap, all candidate-publication rows (diagonal = clause count):

| | Length | Giveback | Tightness | Breakdowns |
|---|---:|---:|---:|---:|
| Length | 2,184 | 1,889 | 388 | 1,184 |
| Giveback | 1,889 | 2,877 | 491 | 1,645 |
| Tightness | 388 | 491 | 652 | 318 |
| Breakdowns | 1,184 | 1,645 | 318 | 1,697 |

| Metric | Minimum | P25 | Median | P75 | P90 | Maximum |
|---|---:|---:|---:|---:|---:|---:|
| Base sessions | 1 | 11 | 22 | 31 | 37 | 39 |
| Giveback | −0.16 | 0.41 | 0.66 | 0.96 | 1.41 | 9.91 |
| Tightness | 0.22 | 0.75 | 0.85 | 0.96 | 1.10 | 6.65 |
| Breakdown count | 0 | 0 | 1 | 4 | 6 | 24 |

Length counts: one session 208; two 76; 3–10 586; 11–20 777; 21–30 1,004;
31–39 896. Breakdowns: zero 1,129; one 721; two 485; three 296; four or more
916. Full integer and two-decimal histograms are retained in JSON.

Boundary neighborhoods (exact **rounded** values, not proposed changes):

| Metric | Two steps below | One below | Boundary | One above | Two above |
|---|---:|---:|---:|---:|---:|
| Giveback at 0.34 | 0.32: 32 | 0.33: 27 | 0.34: 43 | 0.35: 32 | 0.36: 43 |
| Giveback A+ at 0.25 | 0.23: 25 | 0.24: 29 | 0.25: 32 | 0.26: 27 | 0.27: 25 |
| Tightness at 1.00 | 0.98: 37 | 0.99: 37 | 1.00: 44 | 1.01: 50 | 1.02: 35 |
| Tightness A+ at 0.70 | 0.68: 43 | 0.69: 61 | 0.70: 56 | 0.71: 65 | 0.72: 44 |

Only 75 rows lie just above the ordinary giveback cutoff at 0.35–0.36;
85 lie at tightness 1.01–1.02. Most giveback failures are not a rounding-edge
phenomenon. Among the 304 ordinary passes, overlapping reasons for no C A+
are tightness 208, giveback 171, one breakdown 85, internal burst 65, volume
not below leg 55, volume not below prior-50 average 66. The exact A+ conjunction
is selective, and **overall mechanical A+ does not require C A+**.

## Segmentation and numeric geometry

**Repository observation:** `_find_base` takes the first highest cent-rounded
High from `t-40` through `t-2`; all following bars through `t-1` form the base.
No internal event terminates it. A higher later peak resets it; equal highs
keep the first; a rolling search can expire the anchor. `_find_leg` starts at
the last lowest close within 60 sessions ending at the anchor; its depth uses
the minimum intraday low in that selected leg. A short nearby pause under an
older high can therefore be absorbed into a much longer decline/pause.

**Deterministic reconstruction:** CTAS on September 16 selects July 30–September
15, **33 sessions**, after a July 29 high of 219.16. Low 196.50 and prior-leg
low 161.16 produce giveback `22.66 / 58.00 = 0.39`; daily-range means
`1.754545 / 2.466667 = 0.71`; one breakdown; volume ratios 0.78/0.87.
C FAIL reflects length and giveback. A later containing local peak on August
28 (205.81) bounds an 11-session August 31–September 15 pause: giveback 0.22,
tightness 0.72, no breakdown, volume 0.80/0.82. Under the unchanged clauses
that **counterfactual** is C PASS. A plausible recent consolidation exists;
the source does not determine whether the older adverse context should be
discarded. This is consequential proxy behavior, not a source-labelled fix.

IDT on September 18 instead selects **two sessions**, September 16–17, after
September 15's rounded high 72.12 (September 14 high 72.10). Earlier August
27–September 10 closes span 67.97–69.42; highs then rise to 70.91, 72.10,
72.12. Current base low 68.41 versus leg low 51.55 gives 0.18 giveback,
tightness `2.60 / 2.735 = 0.95`, zero breakdowns, volume 1.19/1.28: C PARTIAL,
overall mechanical A+ at nine. It demonstrates a high reset truncating a
broader pause, but does not prove a longer encompassing box is the uniquely
source-correct base. No valid containing local peak in the diagnostic 3–20
window exists for this case.

Across 1,846 frames, **100** actual base highs exceed the stored peak anchor
because `t-1` cannot be selected as the peak. Four givebacks are negative.
Thus `base.high` must be understood as an anchor, not an all-bars bounding-box
maximum. This is deliberate, tested segmentation behavior. Changing it would
also change the prior leg and measurements; the inspected sources do not
dictate such a replacement.

### Breakdown, giveback, tightness and volume fidelity

- **Breakdowns:** price-only daily ratio ≤ 0.96, including the first base
  day's change from the peak close. Repeated down days count separately.
  PLTR September 16 has two (September 2/4), but only one meets the scan's
  separate volume requirements. The selected 11-session base fails C. A later
  September 3 anchor produces seven sessions and one counted breakdown, with
  giveback 0.27/tightness 0.73: counterfactual PASS. On 845 frames, adding the
  scan-volume qualifiers changes the count; on 245 it changes the breakdown
  gate. The primary C wording does not require those qualifiers. No change
  is justified by those counts.
- **Giveback:** peak-to-base-low depth divided by selected leg-low-to-peak
  amplitude, not the leg's separately reported close-to-close percentage.
  This is an intelligible shallowness proxy; a small denominator can give a
  very large ratio. WBD September 21 uses `1.25 / 3.74 = 0.33`, passing
  ordinary C and missing quarter A+; MRK uses `14.60 / 45.35 = 0.32`.
  Both are nevertheless overall mechanical A+ at ten.
- **Tightness:** averages daily `(high-low)/close` percentages, then compares
  with 60 sessions before the **base starts**. It does not measure total box
  width or wick/gap ordering. NFG September 18 averages 1.842105% against
  1.828333%, ratio 1.01: relatively wider despite small absolute ranges.
  Its giveback 0.57 independently fails. Eleven frames fail tightness with
  mean base range below 2%. This illustrates normalization bias, not proof
  those bases meet all source criteria; the source's 2% prior-day concept
  must not become a new whole-base threshold. Whether visually orderly bases
  are systematically rejected remains unvalidated without labelled examples.
- **Volume:** base mean / leg mean and base mean / preceding-50 mean. The
  latter overlaps the base; this is not a purely pre-base norm. INSW
  September 16 passes ordinary C with **1.61/1.52** volume ratios and lacks
  C A+. A rounded ratio of exactly 1.00 also blocks A+. Low volume is a
  source preference, but the conjunctive averaging policy is DERIVED.

### OFFLINE COUNTERFACTUALS — diagnostics only

Change only the length pass window, freezing all other clauses and existing
partial fallback:

| Length window | C PASS | C PARTIAL | C FAIL | Changes |
|---|---:|---:|---:|---|
| Current 3–20 | 304 | 67 | 3,176 | Recorded baseline |
| 3–10 | 199 | 172 | 3,176 | 105 PASS → PARTIAL |
| 5–40 | 270 | 101 | 3,176 | 30 PARTIAL → PASS; 64 PASS → PARTIAL |

Neither row is execution of a full historical strategy. In particular 3–10
belongs to anticipation and the 2018 zero-breakdown clause is not applied.
The wider upper limit alone does not cure the current C FAIL population.

Boundary diagnostics recompute the leg and C with unchanged thresholds:

| Diagnostic | Eligible frames | Changed C states | Share of all 1,846 frames |
|---|---:|---:|---:|
| Anchor one session earlier | 1,844 | 123 | 6.66% |
| Anchor one session later | 1,736 | 71 | 3.85% |
| Latest containing local peak yielding 3–20 sessions | 1,571 | 148 | 8.02% |

The union of one-session state changes is **158 / 1,846 = 8.56%**. A one-session
perturbation need not remain a valid containing peak: this is a stress test.
The local-peak diagnostic requires a high at least its previous high, greater
than its next, and no lower than every subsequent pre-signal high; it picks
the latest such peak independently of C score. It changes 1,398 boundaries;
133 FAIL and ten PARTIAL become PASS, while five PARTIAL become FAIL. It
can discard meaningful adverse history. These percentages quantify tested
sensitivity, **not the fraction of objectively wrong bases**. No full
mechanical or reader regrading is inferred from alternate boundaries.

## Correction, versioning and verification

The failing-before regression reads the actual reader C instruction: it lacks
DERIVED attribution and fails to distinguish ordinary C from C A+ volume.
On the untouched instruction it fails; eleven selected existing C arithmetic
controls pass. After the correction, source mapping and the runtime controls
pass without weakening tests. Two-session/long partial policy, event counting,
giveback, tightness and A+ thresholds are all unchanged.

`quality.RULES` and the mechanical AST are unchanged. Consequently the existing
rules digest is preserved, not manually overridden. Future deterministic rule
changes must flow through it. Prompt provenance changes normally; synthetic
fixtures are regenerated through the real offline pipeline and show only
prompt-derived identity changes. Historical data, picks, history, evidence and
quality-ledger objects are not rewritten. No new reader final grades exist.

| Retained distribution | Before | After attribution correction |
|---|---|---|
| C | PASS 304 / PARTIAL 67 / FAIL 3,176 / UNMEASURED 0 | Identical |
| C A+ flag | 32 | 32 |
| Mechanical grades | A+ 14 / A 415 / B 860 / C 645 / skip 1,613 | Identical |
| Mechanical grade changes | — | None; candidate list `[]` |
| Mechanical A+ count change | — | 0 |

The after column is current-source frame replay for 1,846 rows plus original
check reconciliation and identical mechanical AST for the earlier 1,701.
It is not falsely described as 3,547 raw-frame replays or retrospective
publication replacement.

| Check | Status | Evidence / limitation |
|---|---|---|
| Failing-before attribution regression | FAIL | Intended failure on old C instruction; eleven arithmetic controls PASS |
| Fixed-after focused suites | PASS | 332 quality, scans, discovery, source, provenance and reader-authority tests |
| Frozen publication identities / mechanical AST / 3,547 reconciliations | PASS | Audit script assertions |
| Current-source reaction-frame replay | PASS | 1,846 exact assessments |
| Original-source provenance replay | PASS | 1,871 source rows across the five later publications; all nine publication shapes and mechanical/reader reconciliations PASS |
| Pre-September-16 raw-frame replay | BLOCKED | 1,701 complete frames not retained |
| Full normal pytest | PASS | 1,451 tests on Python 3.12.14; initial stale CLAUDE suite count corrected without weakening tests |
| Fixture verification | PASS | All 12 fixture files current; only prompt-derived identity paths change, with the synthetic prompt object replaced by the generator |
| Local page/chart/continuity rerun | NOT RUN | No UI behavior changes; normal exact-head CI still includes these gates |
| Secret Scan / exact-head CI | NOT RUN | At report commit; submitted-head results are pinned in the PR before handoff. Automatic events only, no workflow dispatch or rerun |
| Human source-labelled base benchmark | BLOCKED | No adjudicated retained-boundary reference set |
| New provider/model calls, live scan, refresh, email or publication | NOT RUN | Outside this milestone |

README and `.env.example` were reviewed; no configuration change is needed.

## Answers and stopping boundary

1. **Why frequent failure?** High giveback under the selected peak/leg
   geometry dominates; long windows and repeated price-only breakdowns overlap
   it. Tightness contributes less, and failures are mostly not a narrow margin
   around cutoffs. This is descriptive, not a conclusion about excess severity.
2. **Whose rules?** Selected 2014 length and later 2020 down-day allowance are
   directly attributable; alternative historical scopes remain explicit.
   Segmentation, partial credit, numeric depth/tightness, volume windows and
   the A+ conjunction are DERIVED.
3. **Are windows source-faithful?** They implement an interpretable outer
   pause proxy, but can absorb a shorter recent consolidation or reset on a
   slight new high. Exact source fidelity cannot be certified; nearby cases
   and sensitivity are documented without inventing a human ground truth.
4. **Do metrics match documentation?** Code matches its documented arithmetic
   and intended price-only counts. The reader description did not distinguish
   DERIVED giveback or A+-only volume; that verified mismatch is corrected.
5. **Is a deterministic rule materially mis-specified?** No source-proven
   numerical or segmentation defect is established by this evidence. Known
   limitations remain visible; a sensitivity gain is not proof of a fix.
6. **Production correction?** Only source attribution/prompt wording and
   source comments. No numerical correction, rule retuning or new model call.

**KEEP:** #86 reader authority, #85 quality ledger, truthful unknown/degraded
accounting, history, current mechanical rules, website/mobile/chart/Focus and
shared design. **FIX NOW:** the demonstrated C attribution/ordinary-volume
mismatch only. **DEFER:** any independently labelled segmentation study,
provider investigation, live post-#84 observation, profitability, outcome
research and broader retuning. **OMIT:** A+ manufacturing, future-return
selection, historical regrading, ticker exceptions, gallery/UI additions,
brokerage/portfolio and siblings. Exact next action: finish normal automatic
checks on the one focused PR, stop for Guidance review, and do not merge.
