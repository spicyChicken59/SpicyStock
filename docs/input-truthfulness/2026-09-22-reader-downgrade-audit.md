# Reader downgrade and source-authority audit — 22 September 2026

Verified base/main: `2d790e1f95a8df746d9e7cb7870d16444462725d`, merge of #85.
Main still equalled that revision and SpicyStock had zero open PRs before branch
`fix/reader-source-authority` was created. No production auto-commit intervened.
The selected effort setting was preserved; its value and quota were not guessed.

**A current implementation defect is demonstrated.** The reader was authorized
to add source-grounded qualitative judgement, but main accepted an arbitrary
lower score without any enforceable source/evidence finding. The existing
scan-specific prompt and discovery text tripwire closed one historical class,
not this general authority gap. Eleven focused negatives fail on untouched main;
the bounded correction rejects them while retaining legitimate downgrade controls.
This is not evidence that every historical downgrade was wrong or that mechanical
A+ must become final A+. No threshold or outcome optimization is justified.

## Population, evidence and source hierarchy

The denominator is **108 completed historical reader results**, twelve in each
of nine real v2 publications on seven sessions, September 11–21. These are a
selected top-mechanical-grade subset of 3,547 retained reaction assessments,
not a random sample of the market or independent observations. Revisions remain
separate: fourteen mechanical A+ rows represent nine date/ticker pairs. All nine
publications were red; all 108 rows had no plan and no ticket.

The [machine-readable claim inventory](2026-09-22-reader-downgrade-audit.json)
contains every decision, exact reader reason/risk/entry text, eight measured
checks and thresholds, mechanical/reader/final grades, source identities,
claim-level findings and per-publication counts. The
[individual A+ evidence records](2026-09-22-reader-a-plus-evidence.md) present all
fourteen separately. These are derived subsets and judgements; no raw historical
publication is duplicated or changed. The existing #85 inventory/candidate matrix
is the population authority. The audit script verifies each original data SHA-256
and execution/publication source equality before extraction.

| Authority class | Treatment in this audit |
|---|---|
| PRIMARY Stockbee/Bonde | Dated, directly inspected discovery formulas remain those in `knowledge/reaction-discovery.md`: percent and Dollar are independent routes. For qualitative checklist concepts, the repository's (B)/(V) attributions are retained as attributions; this audit does not newly authenticate every original post/video. |
| Later Bonde clarification/change | Dated volume-floor variants, different consolidation windows and the later narrower anticipation window remain distinct. They are not silently merged into a timeless rule. Consolidation reconciliation is deferred. |
| Community interpretation | Webinar ports and catalyst-volume interpretations remain secondary. The supplied 16-page *Stockbee AQuality Setup and Momentum Burst Method: A Complete Field Guide* supports conceptual review, not replacement of the repository's dated primary discovery contract. Its differing community Dollar formula is not imported. |
| SpicyStock DERIVED choice | Weights, grade bands, A+ tally, proxy thresholds, lookbacks, source identifiers and reader validation are implementation choices. A measured proxy failure is not automatically a new veto. |
| Historical model assertion | Recorded prose and scores establish what the reader said. Neither repetition nor a successful workflow makes the assertion a strategy rule. |
| Empirical retained observation | Counts, recorded values and dated frame comparisons describe these publications. They do not establish edge, profitability, causal model intent or later results. |

No subsequent prices, returns, settled-plan performance or event-study results
are used as audit evidence. Some historical prose mentions prior-breakout notes
or an event-study cell; only whether those notes had decision authority is
examined. Their reported outcomes are neither recalculated nor endorsed.

**Evidence distinctions:** repository observations are code/contracts; retained
publication evidence is original data and content-addressed objects; deterministic
reconstruction is algebra, frame comparisons and the pure discovery guard;
historical model statements are quotations; current-source comparison applies
main's rules without a new reader; fresh offline tests use doubles. Provider/model
evidence is historical only. A scripted response is not a real model execution.

## A. The contract each publication actually ran

GitHub run metadata was read, not dispatched: all nine retained runs completed
successfully at attempt 1. Their execution revisions below match the retained
publication's relevant source files. Exact blobs and SHA-256 values for grader,
pipeline, quality, discovery, provenance and all three knowledge contracts are
in `contracts` in the JSON.

| Session | Publication | Execution revision | Run | Rules | Prompt |
|---|---|---|---:|---|---|
| Sep 11 | `7380a97` | `74bff884dcc1ee4d9c835d4e1560b1dc0ddeff87` | 34647793285 | `015229b909b7` | old |
| Sep 11 | `ece47f1` | `7380a97605c7f16eb902421486c491a95b957cd7` | 34653694658 | `2fe10c171341` | old |
| Sep 14 | `fbaed5c` | `3d60ae15b9f615f6364358affb944a67e869e566` | 34903940252 | `953f37fb787a` | old |
| Sep 15 | `442db48` | `0233b309a43d3c3f64d30ee974d2be15d1fcea28` | 35030668710 | `e1032aa5ee21` | old |
| Sep 16 | `5808054` | `7859ae081a1cbb12ef4c2f949ee0e699df893bc8` | 35157356943 | `1fe2b3171634` | route-specific |
| Sep 17 | `ebcdea3` | `bd34b8b65cbeb0951a659f4002734170e43c26a5` | 35281605621 | `7ca2debdce10` | route-specific |
| Sep 18 | `8387cce` | `ebcdea34464b9090e7734ca543be8733d39fc20a` | 35401227388 | `e2cace0f7bc6` | route-specific |
| Sep 21 | `25eb5b2` | `89d31535fe1684711fb6c15e8541b573b1963f03` | 35669619745 | `d5d62f525e0f` | route-specific |
| Sep 21 | `49e2724` | `25eb5b2688a3ba1ceecc01083a7cb6046cc62aea` | 35673429253 | `d5d62f525e0f` | route-specific |

Old grader blob: `7d1678aa644f773f26ad30c8c696fc873df60a69`;
old strategy blob: `b4c7ccb60da18c3f196dfb74178e7e6a344d5c9d`.
Later grader blob: `05fb9b6be6d35a58cb4cd8f0efbd096be875ef3b`;
later strategy blob: `3da7500efe0a269283926a60b4426943a6e34139`.
The later blobs are also the verified base's grader/prompt. All nine quality
implementations share blob `80fc7574086135730f53e7df1f5e12bbe02abd06`.

All allowed twelve candidate reads, with at most two attempts per candidate.
The reader was told to start from the mechanical grade, confirm or lower, never
raise, and name an independent chart/measurement flaw. Score bands were A+ ≥9,
A ≥8, B ≥6.5, C ≥5, otherwise skip. The parser derived the returned grade from
the score; pipeline used the worse of that grade and the mechanical grade.
Neither reader score nor prose recalculated the mechanical assessment. RE/VOL
are extra checks contributing to the A+ tally, not the six weighted 2LYNCH
letters: a ten-point mechanical assessment can legitimately have RE/VOL failures.

The metrics supplied ticker/close, mechanical grade/score/pass and A+ counts,
checklist strings with measured values and thresholds, vetoes, notes,
reclassification/unreadable status, base/leg/burst summaries, scan, flags, gain,
relative volume and dollar volume, plus a daily chart when rendered. Later
requests additionally supplied explicit applicable/inapplicable discovery rules.
The first 48 exact charts/frames/requests are unavailable; `chart_seen=true` is
only a retained assertion there. The last 60 have frame/chart/system objects
and request digests, with input reconstruction verified against their own code.

The old opening universally required 4% although its own revision's scanner
and method already admitted Dollar separately. This is an **internal historical
contract conflict**: those readers followed stale prompt wording; the same
wording contradicted discovery authority. We do not pretend the old prompt
already contained today's correction. #68 corrected the opening and added a
narrow rejection tripwire; #72 corrected primary Dollar attribution; #73 made
source/request reconstruction verifiable. None retroactively changed a reply.

## B. Why the fourteen mechanical A+ rows were lowered

Each row's complete claim adjudication, exact text and measured checklist is in
the A+ appendix. This table is a navigation summary, not an overall reader score.

| Session / revision | Ticker | Mechanical score / A+ tally | Reader score → final | Material explanation and evidence distinctions |
|---|---|---:|---|---|
| Sep 11 `7380a97` | DGX | 10 / 4 | 3.5 → skip | RE/VOL failures SUPPORTED; universal 4% gate CONTRADICTED; visual looseness UNVERIFIABLE. |
| Sep 11 `7380a97` | SSNC | 10 / 4 | 4.5 → skip | RE failure SUPPORTED; weak rank/average inference PARTIALLY SUPPORTED; mature/loose visual interpretation UNVERIFIABLE. |
| Sep 11 `ece47f1` | DGX | 10 / 4 | 3.5 → skip | Same independent failures; additionally “below average” CONTRADICTED by 1.04× average (0.92× prior is different). |
| Sep 11 `ece47f1` | SSNC | 10 / 4 | 4.5 → skip | Same types of RE/context/visual claims, distinct retained response and measurements. |
| Sep 14 `fbaed5c` | GKOS | 10 / 4 | 3.5 → skip | RE failure SUPPORTED; declining/loose base interpretation UNVERIFIABLE without original chart. Small gain alone supplies no independent rejection gate. |
| Sep 14 `fbaed5c` | ROKU | 10 / 4 | 4.5 → skip | All eight checks pass. Universal 4% rejection CONTRADICTED; rank 53/0.64× average is real context but no extra hard minimum; loose chart claim UNVERIFIABLE. |
| Sep 15 `442db48` | RGLD | 10 / 4 | 4.5 → skip | All eight checks pass. Universal 4% gate and “smallest” bar CONTRADICTED (RE passes vs five; prior N range is smaller); visual decline UNVERIFIABLE. |
| Sep 18 `8387cce` | IDT | 9 / 5 | 7.5 → B | Two-session C PARTIAL supports a short-base concern. Categorical “no consolidation” overstates partial treatment. Six-week 68–72 confinement CONTRADICTED by retained lows; 72.12-as-ceiling UNSUPPORTED. |
| Sep 21 `25eb5b2` | MRK | 10 / 4 | 5.5 → C | VOL failure SUPPORTED; loose-base judgement PARTIALLY SUPPORTED; wicks outside both measured bounds CONTRADICTED; institutional absence UNVERIFIABLE. |
| Sep 21 `25eb5b2` | WBD | 10 / 6 | 5.0 → C | Gap dominance SUPPORTED and source-authorized visual concern. Premarket/high-low conflation, “near 15%” vote and 0.33 A+ limit CONTRADICTED. Catalyst/plan identity UNVERIFIABLE. |
| Sep 21 `25eb5b2` | PTGX | 9 / 4 | 4.5 → skip | RE/VOL failures SUPPORTED; adverse base context retained; no-volume-of-any-kind overstates mixed rank/average context; prior-result note as a strike CONTRADICTED. |
| Sep 21 `49e2724` | WBD | 10 / 6 | 7.5 → B | Same measured inputs, different reader score. Gap concern remains SUPPORTED; range arithmetic and supply above a 30.80 close from highs near 29 CONTRADICTED; invented 31.50 ceiling UNSUPPORTED. |
| Sep 21 `49e2724` | MRK | 10 / 4 | 5.5 → C | VOL failure SUPPORTED; “already modest” prior volume CONTRADICTED by 31,158,866 shares/visible spike; base high near 147 CONTRADICTED by 156.92. |
| Sep 21 `49e2724` | PTGX | 9 / 4 | 4.5 → skip | RE/VOL failures SUPPORTED, qualitative declining-base concern eligible; prior-result note cannot become a grading strike. |

A+ does not require every A+ component. In particular, a claim that 0.33 is the
A+ C giveback limit is false even when the overall mechanical grade is A+: the
recorded tighter component is 0.25 and ordinary pass is 0.34. This audit does
not adjudicate whether those consolidation numbers should change.

## C. All 108 decisions

Every returned score was below 8, so every selected mechanical A/A+ was lowered.
The code's down-only rule reconciles all 108; it did not mechanically compel a
lower answer. The recorded reasons repeatedly emphasize RE, volume, base shape
and trend age, with both authorized concerns and demonstrable overreach. The
prompt's strict/skip preference may have influenced responses, but retained
text cannot establish the model's internal cause or an alternative score.

| Mechanical → final | Count |
|---|---:|
| A → B | 9 |
| A → C | 32 |
| A → skip | 53 |
| A+ → B | 2 |
| A+ → C | 3 |
| A+ → skip | 9 |

| Reader score | 2.0 | 3.0 | 3.5 | 4.2 | 4.5 | 5.0 | 5.5 | 5.8 | 6.5 | 7.2 | 7.5 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Count | 9 | 2 | 16 | 5 | 30 | 1 | 32 | 2 | 7 | 1 | 3 |

Grade-distance counts (A+, A, B, C, skip): one step 9; two 34; three 56; four 9.
Mechanical-minus-reader score differences span 1–8 points; the full distribution
is retained in JSON. This subtraction describes two recorded judgements, not a
recalculation of checklist weights.

The manually adjudicated inventory contains **395 material factual/rule claims**:
209 SUPPORTED, 54 PARTIALLY SUPPORTED, 6 UNSUPPORTED, 71 CONTRADICTED and 55
UNVERIFIABLE. These labels apply only to the explicit claims, not to whole
responses. Frequencies count reviewed claim instances, not sentences or unique
rules; repeated publications can repeat a claim. They are not a reader accuracy
score. A candidate may contain multiple statuses.

Common categories: base shape 89; recorded RE failure 65; VOL failure 52; Y
failure 39; C failure/partial 31; N failure 1; contextual volume-strength inference
17; universal percent gate 13; impermissible no-vote-note use 26. Eight additional
risk-only references to a no-vote note have **UNVERIFIABLE grade influence** and
are not counted as proven votes. Remaining categories include range ordering,
false thresholds, entry authority, candle/reference confusion and incorrect
check/veto attribution; the complete frequency table is in JSON.

| Publication | Candidates with CONTRADICTED claim | With UNSUPPORTED claim |
|---|---:|---:|
| `7380a97` | 7 | 0 |
| `ece47f1` | 7 | 0 |
| `fbaed5c` | 7 | 1 |
| `442db48` | 7 | 1 |
| `5808054` | 6 | 1 |
| `ebcdea3` | 5 | 1 |
| `8387cce` | 5 | 1 |
| `25eb5b2` | 6 | 0 |
| `49e2724` | 8 | 1 |

Overall, 58 candidates have at least one CONTRADICTED claim and six have an
UNSUPPORTED claim; their union is 61. **This does not mean 61 downgrades were
wrong.** Many have a separate supported defect. Conversely, seven records have
no fully supported adverse claim in this bounded inventory: ADP `ece47f1`,
ADUS/ROKU `fbaed5c`, RGLD/JPM/JNJ `442db48`, and JRSH `5808054`. The first six
lack original chart evidence; JRSH has a permitted but only partially supported
shape judgement. Thus downgrades lacking a *verified* adverse reason exist;
absence of every possible legitimate visual reason is UNKNOWN, not proven.

All thirteen universal-percent claims cluster in the old-prompt first four
publications. None of that explicit class appears in the last five. False facts
and no-vote-note use continue after the correction. Raw signal/prior frame
comparisons specifically test range superlatives: ICE/MEDP/MSFT claims are
contradicted, whereas BFH/BCPC “smallest” claims are supported. RE below the
maximum alone proves neither minimum nor absence of expansion versus every bar.

## D. Intended product role and demonstrated current defect

| Proposed authority | Authorized by verified current contracts? | Boundary |
|---|---|---|
| A. Validate mechanical measurements | Limited | Read and contextualize supplied facts; flag a perceived chart/proxy mismatch. No power to rewrite deterministic facts/statuses. |
| B. Add source-grounded qualitative context | Yes | The enumerated chart-review concepts and actual measurements. |
| C. Downgrade for supported qualitative defects | Yes | Explicit confirm-or-lower instruction, including a visually loose base despite a passing proxy. |
| D. Invent additional numerical gates | No | Recorded thresholds and route-specific rules govern; notes are not votes. |
| E. Override established deterministic facts | No | Discovery is already established; qualitative disagreement with a proxy's adequacy is distinct from changing its measured value/status. |

At the base, `grader._validated` only required a finite score and converted
commentary to strings; no reason, citation, source or authorized criterion was
required. `grade_candidate` applied the narrow discovery regex, and pipeline
accepted the resulting score band down-only. `report` consumed the final grade
for qualification, counts and explanations; `quality_ledger` retained that fact.
`provenance` proved hashes, source replay and grade algebra, not source support
for the reader's reason. The page's unverified-prose label did not constrain the
score's authority. This code path proves an implementation gap against the
independent-evidence contract, not merely an undesirable historical distribution.

There is also a current prompt inconsistency: its extension note has “no vote”
yet a later sentence treats 25% above the average as a spent move. No numerical
source for that extra reader gate is established in the repository; method's
separate plan hazard is sizing, not grading. The correction removes that reader
number and preserves qualitative extension review. Prompt text also stops
asserting that every chart has a planned stop/ceiling; red candidates have none.
No plan or mechanical threshold changes.

## E. Offline comparison with main and bounded correction

The pinned-main pure discovery guard, run over the historical words without a
model, rejects thirteen of 108 responses. Among the fourteen A+ rows it rejects
DGX in both Sep 11 revisions, ROKU and RGLD: **four of fourteen**. It does not
reject the other ten, including WBD's false numerical statement or MRK's false
facts. Current prose forbids those errors but current code did not generally
prevent them. Each A+ appendix record includes this exact guard result. No claim
is made about what an uncalled current model would answer.

Existing fixes retained: #68 route-specific prompt and direct-threshold guard;
#72 dated primary formula authorship; #73 retained input/replay evidence; #85
quality ledger. They respectively correct authority wording, attribution,
observability and retention. They do not prove arbitrary reader semantics.

The correction introduces **reader authority v1**, a DERIVED response contract:

- The model receives typed check values/statuses alongside the existing human
  checklist. Findings name a finite existing strategy concept/source/observation
  and cite supplied values exactly. No arbitrary rule text, new cutoff or
  discovery criterion is an executable finding.
- A measured finding must cite an actual FAIL/PARTIAL. Null/UNMEASURED cannot be
  negative evidence. Visual findings require a supplied chart and may question
  a passing proxy's qualitative adequacy without falsifying its facts.
- A downgrade without a valid finding is rejected whole, without retry, through
  existing degraded mechanical fallback. Accepted findings/version are retained;
  compatible publication verification enforces the same boundary. Historical
  rules without v1 remain distinguishable and use their own verifier.
- Mechanical scoring, A+ tally, 2/H gates, vetoes, score bands and down-only clamp
  are unchanged. No ticker is specially treated. Supported qualitative
  downgrades remain possible, as do measured RE/VOL concerns.

**Limit:** source/measurement eligibility is structural; subjective visual truth
and whether a model sincerely used its stated finding are not mechanically
certified. A permitted visual observation may still be mistaken. Free reason,
risk and entry commentary remains explicitly unverified, and cannot define
order terms. This change does not establish a complete semantic oracle, a
proper score for any archived candidate, or a guarantee of future final A+.
Live response/schema acceptance has not been tested because model execution is
outside this milestone. The existing score/grade severity judgement is preserved,
not retuned from these examples.

## Verification and reproducibility

| Check | Result | Evidence |
|---|---|---|
| Base/main and open PRs before branching | PASS | Exact supplied main; zero open PRs. |
| Nine publication hashes and relevant execution/source equality | PASS | Audit generator; complete identities in JSON. |
| Historical publication shape, 3,547 mechanical assessments and down-only reconciliation | PASS | Fresh socket-blocked execution with each original source revision; [results](2026-09-22-reader-historical-verification.json). |
| Complete source replay, last five publications | PASS | 1,871 source candidates, including 25 anticipation rows, with own historical verifiers. |
| Complete source replay, first four publications | BLOCKED | Original complete frames/charts were not retained; checklist evidence is still available. |
| Focused regression on unmodified base | FAIL | Expected 11 failures at authority checks; three unaffected controls pass. Same 14 tests copied into an untouched base archive. |
| Focused regression after correction | PASS | All 14; retained WBD inputs reject a false measured defect; retained PTGX RE control and synthetic visual control remain eligible; no model upgrade. |
| Full normal pytest / grader-quality-pipeline-provenance coverage | PASS | 1,449 tests, Python 3.12.14; one dependency deprecation warning. All mechanical quality AST outside `metrics_for_model` is identical to base. |
| Fixture regeneration and reproducibility | PASS | All eleven synthetic page fixtures reproduce; existing grade/ticket assertions are retained. Real publications, picks, source objects and quality ledger are unchanged. |
| Local continuity and chart gates | PASS | 127 DOM/store checks and 182 chart checks; offline cached dependencies. Desktop ticket and mobile evidence screenshots inspected. |
| Local page smoke | NOT RUN | Final browser run pending. |
| Secret Scan / exact-head CI | NOT RUN | Results will be pinned to the submitted PR head, never claimed from another revision. |
| Fresh model/provider run, scan, directory refresh, dispatch, email or publication | NOT RUN | Excluded by milestone. |

Reproduce the derived inventory and appendix from the unchanged Git evidence:

```sh
python tools/audit_reader_downgrades.py --output /tmp/reader-audit.json --a-plus-output /tmp/reader-a-plus.md
```

Claim labels are explicitly curated source judgements, not an automated language
classifier. The generator freezes the base/population and automates extraction,
identities, counts, raw-bar comparisons and the base's pure discovery guard. The
normal test suite blocks network connections. Historical verification uses
`tools/verify_retained_publication.py` with extracted original `src/knowledge`,
original `data.json`/`picks.json`, and the retained `docs/evidence` object directory.
No historical grade is changed in place or recomputed with a fabricated reader.

## Disposition and stopping point

KEEP deterministic evidence, truthful unknowns, historical publications, #85's
ledger, mechanical thresholds, website/mobile/chart/Focus behavior and shared
design. FIX NOW only the demonstrated reader/source-authority boundary and its
contradictory prompt statements. DEFER consolidation-rule source fidelity,
provider investigation, post-#84 live coverage, profitability and threshold
retuning. OMIT outcomes, historical regrading, A+ manufacturing, ticker exceptions,
new UI, brokerage/portfolio work and sibling changes.

The six milestone questions are answered by the original reasons, claim-level
adjudication, distributions, historical correction boundaries, failing-base
regressions and bounded fix above. The next action is Guidance's independent
review of one focused PR and normal clean merge if accepted. Astra does not merge
or proceed into a live run or another enhancement round.
