# Retained production input quality and A+ audit — 22 September 2026

Base/main verified before branching: `09acc0429b5a85e0ac74b8eadda3af564134744c`
(merged #84). Branch: `reliability/retained-quality-ledger`. Astra owns this
implementation and one unmerged PR; Guidance owns independent review and merge.
The selected effort setting was preserved, without guessing its value or quota.

**Finding:** modern retained coverage is repeatedly incomplete, at 99.50–99.60%
ready. There are **zero final A+ among 3,547 v2 candidate-publication rows** from
nine publications on seven sessions, September 11–21. Fourteen mechanical A+
assessments, representing nine date/ticker pairs, were lowered by the reader.
There are no published v2 model plans in this population. Publication-time
quality facts and per-plan observations need separate durable retention: the
existing reliability row and recovery catalog do not provide it.

## Evidence identity and limits

- **Repository observations:** the pinned source, CLAUDE checkpoints,
  `knowledge/{method,strategy,reaction-discovery}.md`, input truthfulness,
  provenance, recovery and scorecard contracts. No new field-guide interpretation
  was imported.
- **Retained production evidence:** original Git publication blobs reachable
  from the base, original picks and existing content-addressed evidence, and the
  two already-retained September 21 input-exception artifacts. Fixtures,
  dry runs and the Method walkthrough are excluded.
- **Deterministic reconstruction:** counts, original checklist algebra,
  original reader down-only reconciliation, and classification of an unchanged
  retained directory. This is not a fresh production observation.
- **Reported historical execution:** GitHub metadata identifies all nine v2
  evening runs, attempts, execution revisions and successful workflow conclusions.
  Workflow success does not mean complete input coverage. These runs were read,
  never dispatched or repeated.
- **Fresh offline execution:** socket-blocked historical verifiers, regressions,
  the normal pytest suite and fixture checks. External boundaries use doubles.
- **Provider evidence:** only previously retained returned frames and recorded
  request identities; no fresh provider evidence or provider-cause finding.
- **Browser evidence:** no new local browser study. Existing page/continuity/chart
  and Secret Scan gates are required on the final PR head, with results pinned
  in the PR rather than a self-referential commit hash here.

The [derived inventory and distributions](2026-09-22-quality-audit.json),
[candidate matrix](2026-09-22-quality-candidates.csv.gz), and
[verification results](2026-09-22-quality-verification.json) retain exact commit,
blob and publication SHA-256 identities. The compressed CSV expands to 3,547
rows, one per original reaction assessment. It contains the requested eight
statuses and A+ flags, scores, grades, vetoes, caps, reader state, plan/ticket
state and recorded timing. Raw historical publications, bars and directory
artifacts are not duplicated in this PR.

Inventory uses `git log --full-history` and deduplicates identical data blobs.
Default path simplification omits the last v1 publication `20e75f3`; first-parent
history alone obscures some origins. There are 22 real publication snapshots:
13 v1 and nine v2. These are not 22 independent executions: `e95d6d5`, for
example, changes a retained September 4 snapshot without a new publication time.
The separate latest-per-session v2 view has 2,766 rows; it is descriptive,
not a fixed-universe panel.

**PASS:** all nine v2 publications validate with their own historical source;
all 3,547 checklist scores/grades and reader reductions reconcile. **PASS:**
full retained-source replay for all five September 16–21 publications, 1,871
evidence candidates including 25 anticipation candidates. **BLOCKED:** complete
frame replay before September 16; those source frames were not retained in the
required form. Stored checklist facts remain distinguishable from verified raw
measurements. The shared historical/current `src/quality.py` blob is
`80fc7574086135730f53e7df1f5e12bbe02abd06`; other rule and universe identities
change, so aggregate counts are not evidence of an unchanged population.

## A. Longitudinal input quality

The modern denominator is intended **stocks**, excluding SPY and preceding the
current-session price filter. Ready does not mean scan-ready, matched or graded.

| Session / publication | Intended | Ready | Coverage | Stale | Price excluded | Scan-ready / measured | Neither | 4% only | Dollar only | Both | Matched / quality success |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Sep 16 / `5808054` | 4,795 | 4,771 | 99.4995% | 24 | 1,059 | 3,712 | 3,409 | 46 | 208 | 49 | 303 |
| Sep 17 / `ebcdea3` | 4,794 | 4,775 | 99.6037% | 19 | 1,050 | 3,725 | 3,305 | 173 | 167 | 80 | 420 |
| Sep 18 / `8387cce` | 4,793 | 4,774 | 99.6036% | 19 | 1,043 | 3,731 | 3,371 | 78 | 218 | 64 | 360 |
| Sep 21 / `25eb5b2` | 4,796 | 4,776 | 99.5830% | 20 | 1,048 | 3,728 | 3,347 | 37 | 318 | 26 | 381 |
| Sep 21 / `49e2724` | 4,796 | 4,776 | 99.5830% | 20 | 1,047 | 3,729 | 3,347 | 37 | 318 | 27 | 382 |

Each of these five records explicitly has zero no-bar, failed-after-retry,
permanent-refusal, budget/fetch omission, gapped, unreadable, scan-error and
quality-error counts. SPY is ready in each. All are **degraded** for incomplete
coverage; all request and complete 12 reader assessments. The retained basis is
Alpaca / SIP / split adjustment / 1Day, with measured and expected session.
These are recorded inputs, not independent certification of provider completeness.

| Publication | Rules version | Universe identity |
|---|---|---|
| `7380a97` | `015229b909b7` | `80f35587e8721108` |
| `ece47f1` | `2fe10c171341` | `8801a51fc93f69b5` |
| `fbaed5c` | `953f37fb787a` | `9d710111b38c6bdd` |
| `442db48` | `e1032aa5ee21` | `d900829ad8057af9` |
| `5808054` | `1fe2b3171634` | `f1687e9251080272` |
| `ebcdea3` | `7ca2debdce10` | `26020fa4d2039ed5` |
| `8387cce` | `e2cace0f7bc6` | `8ffa5412211516cc` |
| `25eb5b2`, `49e2724` | `d5d62f525e0f` | `cb87e6a42a1e01e0` |

Earlier v2 publications have the following **native** ledger. Requests/returned/
on-session include SPY; measured is the stock scan population. A modern ready
denominator, coverage percentage, separate unreadable/refused/budget/quality-error
categories are **UNKNOWN**, not zero. Every row has native errors/no-bars/dropped
equal to zero; the source did not yet make incomplete coverage a degraded status.
All four statuses are `ok` and all four read 12/12. Family and neither counts
below are deterministic counts from retained rows and measured minus matches.

| Session / publication | Universe | Requested = returned | On-session | Measured | Stale | Gapped | Neither | 4% / Dollar / Both | Matches |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| Sep 11 / `7380a97` | 3,009 | 3,010 | 3,009 | 3,008 | 1 | 0 | 2,608 | 56 / 258 / 86 | 400 |
| Sep 11 / `ece47f1` | 3,016 | 3,017 | 3,016 | 3,015 | 1 | 0 | 2,614 | 56 / 258 / 87 | 401 |
| Sep 14 / `fbaed5c` | 3,058 | 3,059 | 3,058 | 3,057 | 0 | 1 | 2,499 | 86 / 356 / 116 | 558 |
| Sep 15 / `442db48` | 3,039 | 3,040 | 3,040 | 3,039 | 0 | 0 | 2,697 | 39 / 256 / 47 | 342 |

Legacy v1 stays separate. Its scorer, letter meanings, liquidity gate and later
parallel Stockbee measurement are different contracts. The inventory keeps their
native counts and separate parallel-scan matched/shown counts; bounded shown
rows cannot yield complete 4%-only/Dollar-only/overlap populations.

| v1 publication(s) | Session | Intended | Native fresh / measured | Primary matched | Reader completed | Status / retained problem stages |
|---|---|---:|---|---:|---:|---|
| `f0780c7` | Sep 4 | 230 | UNKNOWN | 0 | 0 | degraded: session, email |
| `932ec58`, `369c695`, `e95d6d5` | Sep 4 | 230 | UNKNOWN | 0 | 0 | ok |
| `e81f3c7` | Sep 8 | 228 | 228 / 228 | 0 | 0 | ok |
| `91a910b`, `151b1af`, `38d37b4` | Sep 8 | 228 | 228 / 228 | 0 | 0 | degraded: universe |
| `5e6bbb2` | Sep 8 | 500 | 500 / 500 | 15 | 8 | degraded: universe |
| `76783a1` | Sep 9 | 500 | 500 / 500 | 11 | 6 | degraded: universe |
| `a7474d5` | Sep 9 | 500 | 500 / 500 | 11 | 6 | ok |
| `e6bbab7` | Sep 10 | 500 | 500 / 500 | 5 | 2 | ok |
| `20e75f3` | Sep 10 | 1,000 | 1,000 / 1,000 | 8 | 5 | ok |

The nine v1 records with coverage report requested=returned=fresh=measured,
and native stale/gapped/no-bars/dropped=0. Their unretained modern categories
remain UNKNOWN. Before that, `369c695` and its later edited snapshot retain a
complete **over-five-sessions-stale** list of FI, BK and EA, not a complete
all-staleness ledger. The #16 seed correction removed EA/FI and replaced BK by
BNY: 230 became 228. Later native 228/228 coverage and zero stopped-printing
names support disappearance of those reported exceptions in the corrected seed.
The commit reports rehearsal run `34035518295`; that historical execution is
not rerun here. The changed membership does not prove that missing data improved
for the old population, and the old corporate/provider explanations are not
adopted as new findings.

**Recurring versus isolated:** modern coverage failure occurs in 5/5 retained
publications across four sessions. Complete modern exception membership exists
only for the two September 21 artifacts (IDs `10670249042`, `10672540296`).
**PASS:** diagnostic schema, checksums, directory binding, partition conservation
and original-publication reconciliation. Run/attempt/execution revision match
GitHub metadata; invocation comes from the artifact, not independent authentication.
The same complete set of 20 is stale in both runs:

`ATXG AUBN BEBE BKHA BMHL ELLO FSEA GIGM IOR KTWO LBTYB MDRR MGYR NCEW PFAI ROMA SENEB TRSG WSTN YHGJ`

The stale identity is `8cdba4864809b3e7`; retained frames end September 18.
This establishes recurrence **within the September 21 session**, not across days.
Earlier complete membership is **BLOCKED**. Their eight-name samples remain:

| Session | Stale total | Retained sample | Unnamed |
|---|---:|---|---:|
| Sep 16 | 24 | ATXG BKHA BLIV BMHL DIT EGHA ELLO EMIS | 16 |
| Sep 17 | 19 | BEBE BKHA BLIV BMHL DIT EMIS GURE GYRO | 11 |
| Sep 18 | 19 | ANTA BKHA BLIV BMHL EGHA GDEV HCMA INTJ | 11 |

The named observations overlap; they do not establish frequency rankings for the
full exception populations. #69 increased the selected universe from about 3,039
to 4,795 and changed coverage/status accounting. Comparing its stale rate or
match counts directly with the preceding quote-filtered population is invalid.

**BLOCKED:** measured live improvement after #84: no post-correction production
publication is retained. The offline September 21 counterfactual removes 16
names, including three stale names (BKHA/KTWO/WSTN) and 13 ready names. That is
4,763/4,780 ready (99.6444%), with 17 stale, versus 4,776/4,796. It is solely a
denominator/membership calculation, not newly recovered bars. The September 18
sample's removed trio is different (BKHA/EGHA/HCMA).

**BLOCKED:** systematic missingness in otherwise valid operating stocks cannot
be established from these samples and one complete session. The earlier stale
investigation distinguishes operating-company observations from classification
errors; it does not establish cause. A causal investigation would require
explicitly approved dated provider request/page evidence, relevant trade/condition
evidence, contemporaneous security identity and complete multi-session exception
membership. No provider cause is inferred here.

## B. Real A+ funnel

**PASS:** zero final A+ in the exact v2 population above, also zero in the
2,766-row latest-per-session view. This does not mean “SpicyStock never finds
A+.” Separately, all 27 retained v1 scored candidate rows are `skip`, consistent
with their historical score bands. Every v1 literal A+ hit is an empty score-band
heading (`setups=0`), not a dated candidate. Synthetic AAPL and Method examples
are outside both populations.

All 14 mechanical A+ assessments are listed below. `D` is Dollar only; `Both`
means both discovery families. All have no mechanical veto and were reader-assessed.
The matrix preserves every individual check and A+ flag.

| Session | Publication | Ticker | Family | Mechanical score / A+ flags | Reader score | Final grade |
|---|---|---|---|---|---:|---|
| Sep 11 | `7380a97` | DGX | D | 10 / 4 | 3.5 | skip |
| Sep 11 | `7380a97` | SSNC | D | 10 / 4 | 4.5 | skip |
| Sep 11 | `ece47f1` | DGX | D | 10 / 4 | 3.5 | skip |
| Sep 11 | `ece47f1` | SSNC | D | 10 / 4 | 4.5 | skip |
| Sep 14 | `fbaed5c` | GKOS | D | 10 / 4 | 3.5 | skip |
| Sep 14 | `fbaed5c` | ROKU | D | 10 / 4 | 4.5 | skip |
| Sep 15 | `442db48` | RGLD | D | 10 / 4 | 4.5 | skip |
| Sep 18 | `8387cce` | IDT | D | 9 / 5 | 7.5 | B |
| Sep 21 | `25eb5b2` | MRK | D | 10 / 4 | 5.5 | C |
| Sep 21 | `25eb5b2` | WBD | Both | 10 / 6 | 5.0 | C |
| Sep 21 | `25eb5b2` | PTGX | D | 9 / 4 | 4.5 | skip |
| Sep 21 | `49e2724` | WBD | Both | 10 / 6 | 7.5 | B |
| Sep 21 | `49e2724` | MRK | D | 10 / 4 | 5.5 | C |
| Sep 21 | `49e2724` | PTGX | D | 9 / 4 | 4.5 | skip |

All nine v2 publications have a red regime; all 3,547 reaction rows have no
plan and no published ticket. A missing plan is not a measured `eligible=false`
plan. The pipeline withholds new longs on red, so mechanical assessment, final
grade and regime withholding are distinct stages. Receipts from September 16
onward record `regime_gate`; earlier attribution is deterministic source
reconstruction, not a retrospectively added receipt.

September 11 has no retained timing object: applicable opening/cutoff evidence
is UNKNOWN. Later publications record the next applicable session and the
09:30–10:00 America/New_York window (Sep 15, 16, 17, 18, 21 and 22 respectively).
These timings describe the publication's intended entry window, not a claim
that an entry was available then or is available now. No ticket existed, and
no historical browser clock/availability observation is reconstructed.

Reader reasons in the JSON are **recorded model statements**, not validated
mechanical truth. Before #68 some Dollar-only reasons incorrectly invoked a
universal 4% minimum (including DGX/ROKU/RGLD). Other recorded reasons discuss
volume, expansion, gap/overhead context or base quality; some use inconsistent
threshold wording. #68/#76 source-authority corrections do not retroactively
repair these replies or grades. No subsequent return is evidence that a grade
was correct, and no historical candidate is regraded here.

## C. Where the current mechanical contract narrows

PRIMARY Stockbee discovery rules, later Bonde refinements, community commentary,
SpicyStock DERIVED implementation choices and these empirical counts retain
their repository labels. In particular, score weights/bands, gates, base/leg
segmentation, numerical linearity/tightness/giveback policies and A+ flags are
implementation contracts, not newly attributed universal Stockbee requirements.

The mechanical A+ conjunction is score >=9, at least four A+-standard checks,
full PASS on 2 and H, no veto and no unreadable assessment. The six weighted
criteria sum to ten (2/L/Y/N/C/H: 1.5/2/1.5/1.5/2/1.5); PARTIAL earns half.
RE/VOL can contribute A+ flags but no weighted points. All eight checks need
not PASS for mechanical A+. Thresholds and decisions are unchanged.

| Session / publication | Rows | Final A+ / A / B / C / skip | Mechanical A+ / A / B / C / skip |
|---|---:|---|---|
| Sep 11 / `7380a97` | 400 | 0 / 51 / 96 / 68 / 185 | 2 / 61 / 96 / 67 / 174 |
| Sep 11 / `ece47f1` | 401 | 0 / 52 / 96 / 69 / 184 | 2 / 62 / 96 / 67 / 174 |
| Sep 14 / `fbaed5c` | 558 | 0 / 53 / 145 / 147 / 213 | 2 / 63 / 145 / 144 / 204 |
| Sep 15 / `442db48` | 342 | 0 / 29 / 78 / 72 / 163 | 1 / 40 / 77 / 69 / 155 |
| Sep 16 / `5808054` | 303 | 0 / 9 / 82 / 49 / 163 | 0 / 21 / 80 / 45 / 157 |
| Sep 17 / `ebcdea3` | 420 | 0 / 18 / 105 / 93 / 204 | 0 / 30 / 102 / 89 / 199 |
| Sep 18 / `8387cce` | 360 | 0 / 41 / 68 / 74 / 177 | 1 / 52 / 66 / 72 / 169 |
| Sep 21 / `25eb5b2` | 381 | 0 / 34 / 100 / 55 / 192 | 3 / 43 / 99 / 46 / 190 |
| Sep 21 / `49e2724` | 382 | 0 / 34 / 101 / 53 / 194 | 3 / 43 / 99 / 46 / 191 |
| All revisions | 3,547 | 0 / 321 / 871 / 680 / 1,675 | 14 / 415 / 860 / 645 / 1,613 |
| Latest per session | 2,766 | 0 / 236 / 675 / 557 / 1,298 | 9 / 311 / 665 / 532 / 1,249 |

| Criterion | PASS | PARTIAL | FAIL | UNMEASURED | A+ flag |
|---|---:|---:|---:|---:|---:|
| 2 | 3,074 | 0 | 473 | 0 | 2,287 |
| L | 2,384 | 0 | 1,049 | 114 | 1,108 |
| Y | 1,918 | 0 | 1,629 | 0 | 1,307 |
| N | 2,080 | 0 | 1,467 | 0 | 865 |
| C | 304 | 67 | 3,176 | 0 | 32 |
| H | 1,826 | 688 | 1,033 | 0 | 953 |
| RE | 1,024 | 0 | 2,523 | 0 | 642 |
| VOL | 1,438 | 0 | 2,109 | 0 | 428 |

A+ flags per candidate (0 through 8): **268, 804, 1,159, 872, 345, 90, 9, 0, 0**.
There are 1,314 vetoed rows: not-linear 1,049 and up-days 357, with overlap.
L's 114 UNMEASURED observations remain separate from its 1,049 FAILs.

Actual caps, among otherwise qualifying score/tally bands without veto, affect
39 distinct rows: H FAIL 15, H PARTIAL 7, insufficient A+ tally 21 (overlap).
The 2 gate caps zero otherwise eligible rows here. This counts caps that change
a grade, not every diagnostic gate note on an already lower score.

The reader was requested/completed for 108/108 rows and lowered all 108:
94 mechanical A and all 14 mechanical A+. Transitions are A→B 9, A→C 32,
A→skip 53; A+→B 2, A+→C 3, A+→skip 9. Latest-per-session is 84/84 lowered,
including nine mechanical A+. Selection is capped at twelve per publication;
unread candidates are not failed reader attempts. These frequencies combine
different historical reader contracts and do not predict current reader behavior.

For “one/two conditions away,” count unsatisfied **logical clauses** of the
current mechanical conjunction: score, A+ tally, 2 gate, H gate, each veto,
and unreadability. These correlated clauses are not independent chart edits
or a price-distance measure. Counts for 0–6 failed clauses are
**14, 255, 962, 1,458, 660, 170, 28**. Thus 255 are one clause away and 962
two clauses away (latest-per-session 195 and 758). Of the 255, 236 miss only
the score band and 19 only the A+ tally. Only 145 of the 236 score-only rows
already score at least eight; one scores 4.5. “One clause” must not be read
as “one small improvement.” None of this measures distance to a final reader grade.

Most frequent blocking combinations: score+tally+H 919, score+tally 789,
score+tally+H+not-linear veto 424, score+tally+not-linear veto 390, score only
236. C is the largest weighted-check failure count. Its overlapping recorded
value failures are giveback >0.34: 2,877; base outside 3–20: 2,184; breakdowns
>1: 1,697; tightness >1: 652. Only 32 C checks carry an A+ flag. Segmentation
and numerical DERIVED policies are therefore material to the funnel, as are
score/tally/gates and the recorded reader reductions. This observation supports
neither threshold loosening nor outcome-driven optimization.

## D. Model outcome record

`record.scorecard_rows` carries the **original pick grade**, date, ticker, kind,
original regime, evidence reference, observed-through date, five-session horizon,
fill status, replay status, uncertainty, R and paired SPY percentage. It does
not reconstruct today's grade. Original picks retain plan levels and grade;
the file keeps at most 260 picks. The scorecard window is the preceding 60
exchange sessions plus the current session, not an unlimited archive.

Its mutually exclusive buckets are pending (current-session plan), open
(known fill and current observations), settled, not_filled, uncertain,
unreadable, unmeasured and unscored (settled replay without measurable R).
Missing observations/stale incomplete walks do not become open positions or
losses. Intraday fill ambiguity remains uncertain. Replay uses whole-share
partial exits and the original stop; R is a model-plan metric. Benchmark pairing
has its own denominator and requires readable SPY entry/exit observations.
Wins/losses/breakeven partition settled measurable plans. Win rate, average and
median R are withheld below **20 settled**; sum R is nullable with no R values.
The public aggregate retains bucket counts, uncertainty causes, denominators,
R summaries, benchmark pairing and replay/input basis.

**PASS:** every original v2 picks file is empty and every corresponding published
scorecard has zero plans. Deterministically, those empty pick populations imply zero pending/open/
settled/not-filled/uncertain/unreadable/unmeasured/unscored, zero wins/losses/
breakeven and zero benchmark pairs. Grade-stratified settled results have **n=0
for every grade**; rates and R summaries are UNKNOWN/undefined, not zero returns.
There is no readable outcome sample. Legacy v1 forward-return experiments are
a different contract and are not imported into this model record. Browser
actions and personal holdings are excluded.

Original grade retention is sufficient for grade attribution while picks survive.
The prospective defect is that the computed per-plan scorecard rows are reduced
to an aggregate and discarded; reproducing prior as-of strata later needs the
original observations and replay basis, not simply the current picks file.

## E. One evidence-retention correction

**FAIL at base:** `record.nights` retains at most 20 sessions, only
`session/status/published_at`, replacing a same-session entry. The current seven
rows cannot answer A–D. Recovery retains publication context and candidate facts
for 21 calendar days (84 records/10,000 signals/128 MiB bounds), but does not
retain the scorecard/open-plan observation rows; only eight of these nine v2
publications currently occur in its catalog. September 15 requires Git.
Input diagnostics provide complete exceptions but expire with their separate
30-day workflow artifacts. Required source receipts are independently bounded
and do not turn `nights` into a longitudinal quality ledger.

**FIX NOW:** `src/quality_ledger.py` adds one immutable publication snapshot under
`docs/quality-ledger/v1/<publication-sha256>.json.gz`, after the final public
write. It projects facts already computed and uses already-fetched frames for
the existing scorecard-row function. It preserves original rules, execution/
session/run identity, universe/input basis, original denominators, full exception
membership, eight mechanical checks and values, score/tally/veto/grade, recorded
reader result, final grade, plan/ticket/gate/timing, and model scorecard rows.
Input, signal and outcome quality have separate sections. Absent fields are null.
No raw bar history, account holdings, user execution, backfill or new decision
rule is introduced. Existing `git add docs` persists it; no workflow, schedule,
secret or setting change is needed. The older production artifact path list does
not include this directory; the repository ledger is its retention channel.

Canonical JSON uses deterministic gzip without filename, timestamp or platform
header variation. A pure projection of the latest retained publication is
672,026 JSON bytes / 69,722 gzip bytes, versus 5,697,877 original publication
bytes; this sizing exercise creates no historical ledger entry. Future sizes
vary with candidate and plan counts. The original publication hash names the entry; identical
capture is idempotent, conflicting bytes are refused. Atomic creation never
overwrites an existing entry. Limits are 8 MiB expanded per entry, 128 MiB
compressed archive and 4,096 entries. Capacity failure does not evict history;
it requires a future explicit retention decision. Schema changes use a new
version directory and cannot migrate old facts under new rules.

Capture failures are isolated from decisions, publication bytes, delivery and
exit codes, and exposed by `RunReport.quality_ledger`, a log event and
`quality_ledger_status` when attempted. An interruption before capture or a
write/capacity failure can leave a publication without an entry; the ledger must
not imply every attempted run was captured. Failed/unpublished/skipped runs
remain outside this publication ledger and use existing diagnostic/log evidence.
This correction is prospective and does not repair unavailable old membership,
old raw frames or old model replies.

## Verification and disposition

| Check | Result | Evidence / limit |
|---|---|---|
| Exact base and branch | PASS | Main matched supplied merge before branching |
| Historical v2 schema and grade algebra | PASS | Nine original-source verifications, 3,547 rows |
| Historical full-source replay | PASS | Five later publications / 1,871 candidates |
| Earlier full-source replay | BLOCKED | Four v2 and legacy source-frame sets unavailable |
| Retained diagnostic verification | PASS | Both original September 21 artifacts and ledgers |
| Focused failing-before regression | FAIL | Untouched base loses publication-quality evidence; actionable control passes |
| Fixed-after retention and decision controls | PASS | Same retention regression; complete public/source bytes, calls and terminal exit/status controls |
| Full normal pytest | PASS | 1,435 tests; socket-blocked external boundaries |
| Fixture check | PASS | All 12 fixtures current; no fixture regeneration |
| Whitespace and scope | PASS | `git diff --check`; production records, strategy, UI/design unchanged |
| Local browser / continuity / chart gates | NOT RUN | UI unaffected; exact-head existing CI page gate required |
| Exact-head CI and Secret Scan | NOT RUN | Final results and tested commit are pinned in the PR after push |
| New market-data/model calls, email, publication, refresh, dispatch/rerun | NOT RUN | Outside this milestone's execution authority |
| Live effect of #84 / provider cause / profitability | BLOCKED | Missing post-correction production observation, causal evidence or settled sample |

The initial full suite caught documentation counts/inventory and an unnecessary
output on unattempted capture; these were fixed without weakening assertions.
Dependencies were read from already-present cached packages (Python 3.12.14,
pytest 9.1.1, pandas 3.0.6, NumPy 2.5.3, exchange_calendars 4.13.2). Automatic
approval review rejected a package-install attempt; no alternate installation
or registry workaround was used. The cached runtime supplied a safer offline
path. Test-only synthetic provider/model errors are not production observations.

Reproduce the derived audit offline from a complete local Git history:

```sh
python tools/audit_retained_quality.py --ref 09acc0429b5a85e0ac74b8eadda3af564134744c --output /tmp/quality-audit.json --candidates /tmp/quality-candidates.csv.gz
```

For original-source verification, extract `src/` and `knowledge/` from each
listed publication commit into an isolated source root and its `docs/data.json`
and `docs/picks.json` together. Run `tools/verify_retained_publication.py
SOURCE_ROOT DATA_JSON docs/evidence` in a fresh Python process. Never
run an old pipeline or a provider/model transport to verify a stored record.

**KEEP:** truthful degraded/unknown accounting, original publications/provenance,
strategy thresholds, accepted website/mobile/chart/Focus behavior and shared
design. **FIX NOW:** this one publication-time retention gap. **DEFER:** provider
investigation, strategy retuning, profitability conclusions and human usability
work. **OMIT:** retroactive grades, outcome-driven optimization, galleries,
portfolio/brokerage features, unrelated UI and sibling-repository work.

Stop after independent review of this focused PR. A future naturally produced
post-#84 publication could answer the live-coverage question; obtaining new
provider evidence or initiating execution still requires Tahir's explicit
approval. This audit does not initiate either action.
