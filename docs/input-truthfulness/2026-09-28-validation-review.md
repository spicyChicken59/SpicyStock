# Historical validation and usable decisions · review gate

**Product verdict:** the release supports inspected research and conditional
decision support. It does not establish a trading edge. The latest verified
publication is September 25, with zero reaction tickets and an empty picks file.
Its next-session window is September 28, 09:30–10:00 America/New_York
(08:30–09:00 America/Chicago). No order is made eligible by this work.
After the existing next evening evaluation, inspect the new record's actual
data, review, market, plan and timing gates. A healthy run need not buy anything.

Actual base: `8be007f68deaa417b85a512d2e16a37899d27011`, re-resolved before editing.
Branch: `fix/historical-validation-usable-plans`. PR #91 was already merged;
no competing open PR or assignment branch was found. Guidance owns independent
review of the final PR head and the clean merge. No manual dispatch, new live
provider/model call, external message or brokerage action occurred.

The [POC specification](2026-09-28-poc-spec.md) was frozen in commit `24615d6`
before new outcome calculations. The [operating contract](2026-09-28-operating-contract.md)
separates the selected next-morning variant, source attribution and execution
limits. This set influenced earlier development; no blind holdout is claimed.
The original local commit object is retained in
[`spec-freeze.json`](2026-09-28-evidence/spec-freeze.json). Direct git push had no
credentials; the authorized GitHub connector publishes an identical specification
tree in `f92a8c0d1efbe0f2291cb5b4d4bb80404826471c`. That later upload is not the
claimed pre-experiment timestamp.

## The causal explanation

There are **13 actual publications over 11 unique sessions**, September 11–25:
5,215 candidate-publication rows and 4,434 distinct candidate/session pairs.
September 11 and 21 were revised; revisions are not additional trading days.
Every publication has RED market permission. Every accepted reader judgment
finishes below A/A+. Together these block all reaction plans, before cash
allocation, receipt sealing or publication. No internally eligible reaction
ticket was found lost between planning and the site.

The measured overlapping constraints are more informative than “conservative.”
The runner evaluates the actual recorded first blocker and every independently
calculable later constraint, with substituted-market arithmetic clearly labeled.
Structural feasibility is not inferred from a RED refusal, and missing review
is never counted as acceptance or measured failure.

| Publication session | Candidates | Accepted / selected | Structurally feasible if GREEN | Feasible mechanical A unreviewed |
| --- | ---: | ---: | ---: | ---: |
| 2026-09-11 | 400 | 12 / 12 | 377 | 46 |
| 2026-09-11 revision | 401 | 12 / 12 | 378 | 47 |
| 2026-09-14 | 558 | 12 / 12 | 528 | 47 |
| 2026-09-15 | 342 | 12 / 12 | 319 | 27 |
| 2026-09-16 | 303 | 12 / 12 | 281 | 9 |
| 2026-09-17 | 420 | 12 / 12 | 376 | 16 |
| 2026-09-18 | 360 | 12 / 12 | 321 | 38 |
| 2026-09-21 | 381 | 12 / 12 | 352 | 30 |
| 2026-09-21 revision | 382 | 12 / 12 | 353 | 30 |
| 2026-09-22 | 513 | 0 / 12 | 477 | 34 |
| 2026-09-23 | 282 | 11 / 12 | 266 | 6 |
| 2026-09-24 | 418 | 9 / 12 | 371 | 42 |
| 2026-09-25 | 455 | 11 / 12 | 440 | 59 |

All rows above have RED permission, zero accepted A/A+ names and zero published
reaction tickets. “Feasible” substitutes GREEN for arithmetic only; “unreviewed
A” also requires mechanical A/A+, no veto, a feasible band and nonzero size.
Original policy identities, complete gate combinations, first blocker,
review status, structural feasibility, sizing and isolated interventions are in
[candidate-traces.json.gz](2026-09-28-evidence/candidate-traces.json.gz).

For September 24 the 418 rows overlap as follows: 418 RED; 368 final grade below
A; 168 vetoed; 406 not selected; three rejected reviews; 47 structurally infeasible;
20 feasible but zero whole shares under substituted GREEN. September 25's 455
rows have 455 RED, 391 below A, 158 vetoed, 443 not selected, one rejected review,
15 structurally infeasible and 20 feasible but zero shares. These are overlapping
counts, not a partition. Market is the first recorded blocker in both receipts.

Across 156 publication-level selections, 139 reviews were accepted and 17 were
rejected/unavailable. Repeated-session reviews are not independent observations.
Six selected cases have infeasible current structural bands: September 16
ARQT/EROC, September 17 CPOP, September 18 ALMU, September 24 DRK/TEM. No September
25 selection has that particular defect. Each publication leaves 6–59 otherwise
mechanically feasible A/A+ candidates unreviewed. On September 25 seven remaining
review slots go to the first seven alphabetic names in a **70-way grade-A,
score-8 tie**: ACLS, ADI, AJG, AMGN, AMT, ATO, BKR. This establishes review-access
starvation and ticker dependence, not the hypothetical quality of unreviewed names.

Changing market permission to GREEN or YELLOW while retaining actual reviews
still yields zero tickets in every publication. Omitting the reader gate alone
under recorded RED also yields zero. Substituting GREEN **and** omitting the
reader gate yields four allocated counterfactual tickets per publication.
These are ablations, not historical plans, new model opinions or performance.
There is no evidence that changing ranking alone would solve zero plans.
Ranking/approval prerequisites remain unchanged pending explicit decision review.

56 September 24 and 74 September 25 mechanical A/A+ rows coexist with RE/VOL/C
FAIL/PARTIAL measurements. This is permitted by the weighted composite semantics,
not proof every criterion passed. RE/VOL carry no score weight. C can contribute
partial credit. Only the recorded necessary conditions/vetoes are hard gates.

The browser's existing `degraded` status is not itself a universal order ban;
invalid publication/input/calendar evidence and stale/ended timing have separate
effects. In these sessions candidate-validity exceptions did not create the
universal zero-plan result. This release changes no global actionability policy.
Uncertain daily-bar execution can consume an open slot in the five-session
open-plan window; it is not retained indefinitely as a proven live position.
There are no actual published picks here to exercise that portfolio question.

## Evidence inventory and input truth

[results.json.gz](2026-09-28-evidence/results.json.gz) contains the publication
inventory, source manifest, provider/adjustment/session basis, per-object hashes,
capture times, date spans, row counts, symbol bindings, reader identities,
exception membership, breadth checks, simulations and limits. The 3,376 unique
retained source-frame objects appear in 3,559 candidate/watch occurrences,
covering 996,244 row-occurrences. These are normalized contemporaneous snapshots
of selected securities, **not** 288-session point-in-time universes.

Independent scalar inspection found no nonfinite/nonpositive prices, negative
or fractional volumes, invalid OHLC relationships, duplicate/unsorted dates,
non-session dates or internal missing sessions in those retained frame spans.
Integer-valued float64 volumes remain within exact-integer range. This establishes
coherence of retained values, not correctness of the original wire values. Subcent
prices are counted, not rounded away. 81 occurrences have fewer than 111 bars,
short of the maximal 110-session warm-up: this is separately exposed rather than
renamed a measured quality failure. Security class, ticker-change/split histories,
raw pagination, trade conditions and adjustment correctness cannot be independently
certified from normalized frames. No bars were synthesized or forward-filled.

Full intended universes, complete eligible OHLCV universes and benchmark source
series were not retained. Candidate frames cannot validate underlying historical
breadth. All 26 retained 5-/10-session aggregate calculations match the independent
ratio-of-sums oracle; averaging ratios would be a different calculation. The
existing breadth tests exercise qualifying events, zero denominators, gaps,
rolling windows and scaling with synthetic controls. That is software proof,
not corroboration of every historical underlying count.

September 24 intended 4,779 stocks: 4,763 ready + 16 stale. September 25 intended
4,780: 4,758 ready + 22 stale. All benchmark-inclusive names were requested and
returned histories: this is not established as a fetch-budget shortage. The
latest last available observations are September 23 and September 24 respectively.
Intended/requested/returned/exclusion membership is retained in full in the
exception fixtures; the production validator and independent stale-date check pass.

- September 24: ARBB BLIV CKX ELLO FKWL FOXX GIGM HTLM IOR LEGO MAYS MDRR PFX PLUT SENEB TRSG.
- September 25: BEBE BHM BLIV BYFC CLST CPHC CVR DIT ELLO ELTK GDEV HBNB HTLM IOR LCFY LEGO MDRR MEGL NCEW SANG SENEB STRR.
- Recurring: BLIV ELLO HTLM IOR LEGO MDRR SENEB. Fifteen newly stale names are listed in the machine result; nine September 24 stale names are no longer in that group.

Every observed provider cause remains **unknown**. Exception tails contain
last observations and limited anchors, not complete history or raw trade tapes.
[Alpaca's aggregation FAQ](https://docs.alpaca.markets/us/docs/market-data-faq),
checked September 28, documents condition-dependent price/volume updates and
different minute/daily aggregation rules. Missing eligible price trades and
missing provider observations are distinct possibilities. Neither low directory
volume nor recurrence adjudicates the cause; minute sums are not assumed equal
to daily volume. Directory snapshots were captured after the measured sessions
and do not establish permanent security identities or unbiased past membership.
Existing retention does not establish redistribution entitlements; no provider
license was inferred and the user-supplied guide is not republished.

## Independent volume disagreement and revisions

Read-only September 28 observations of the named Stock Analysis historical pages
reconfirm CRL's supplied public figures and supply a newly dated IQV comparison:

| Name / session | Retained Alpaca SIP shares | Public page shares |
| --- | ---: | ---: |
| CRL / September 24 | 1,590,887 | 1,574,098 |
| CRL / September 23 | 1,594,208 | 1,474,124 |
| IQV / September 24 | 1,893,479 | 1,891,777 |
| IQV / September 23 | 1,116,832 | 1,104,252 |

Sources: [CRL](https://stockanalysis.com/stocks/crl/history/),
[IQV](https://stockanalysis.com/stocks/iqv/history/), S&P Global page data.
The security names, listed market, daily dates and share units align to the
stated extent; exact trade-condition, adjustment and revision comparability is
unresolved. These pages may revise data. Today's IQV values are not asserted to
be the missing earlier audit's values. There is no after-the-fact acceptable
volume-discrepancy percentage: exact comparisons decide the predicates.

An isolated two-volume substitution makes CRL's above-prior predicate true,
adds its 4% route and changes mechanical A to A+ through VOL's A+ count. Its
independent Dollar discovery remains. IQV's route/grade stays unchanged. This is
a **scan and quality boundary** disagreement, with potential breadth-count impact
if the full population were substituted; it is not merely display noise. Under
the actually recorded RED regime and accepted final B reviews neither would get
a ticket. Reusing those opinions after changing metrics is not allowed in a new
request. The sensitivity is not an adjudication of provider error or a feed swap.
[Exact values and component results](2026-09-28-evidence/volume-corroboration.json).

Both same-session publication revisions change volumes and aggregate breadth.
September 11 adds PDS and changes HTFL's discovery route; EXPD's final grade
changes. September 21 adds VWAV; REGN/WBD final grades change. Mechanical grades,
structural feasibility and published reaction tickets do not change for common
names. The event-study manifest also preserves unique differing later bar
observations, with unresolved adjustment/revision causes. Four-decimal publication
normalization is separated from changed underlying values.

## Historical findings and limits

1. **ORIGINAL-PUBLICATION REPLAY:** original source revisions reproduce source,
   mechanical decisions, reader inputs/requests and provenance for nine available
   publications (September 16 onward, including the September 21 revision).
   Four earlier publications pass available shape/algebra/down-only checks but
   complete source replay is BLOCKED. Thirty-six retained raw responses can be
   parsed and authority-checked (31 accepted, five authority rejections; no
   retained truncation/transport/authentication failure in these latest replies); missing historical raw responses remain missing.
   Production Python 3.12.14 / pandas 3.0.6 / NumPy 2.5.3 differ from this offline
   pandas 2.2.3 / NumPy 2.3.5 environment; retained results agree within the
   performed replay, not a claim of identical runtime or fresh API execution.
2. **CURRENT-POLICY HISTORICAL SIMULATION:** real `scan_frames`, `quality.assess`
   and `_make_plans` run against retained candidate prefixes. Nine publications
   are supported; four lack exact frames. Discovery/mechanical scores and grades
   have zero changes versus those recorded cases. Proposed request-v2 reviews
   are UNKNOWN, because prompt/chart/payload identities changed. Zero tickets
   result; no old accepted answer is fabricated for a new request.
3. **COMPONENT/EVENT STUDY:** the first publication for each candidate/session
   defines the event. Subsequent bars come from earliest retained captures,
   including full candidate frames. The outcome bar's own preceding close must
   match the signal basis; a different capture cannot supply that match.
4. **SYNTHETIC ENGINEERING CONTROL:** the real offline evening pipeline publishes
   a qualified ticket, persists its receipt/pick and exercises browser availability
   through existing full fixtures. This is the minimal software reachability
   witness, not a real historical qualifying case.

| Selected event population | Events | Next close available on matched basis | Mean close change | Median close change |
| --- | ---: | ---: | ---: | ---: |
| Discovery | 4,434 | 3,649 | −0.3849% | −0.3028% |
| Mechanical A/A+ | 520 | 372 | −0.4951% | −0.1552% |
| Accepted final A/A+ | 0 | 0 | unavailable | unavailable |

Discovery observations include 1,616 positive, 2,011 negative and 22 unchanged;
785 events lack comparable next observations. Mechanical A/A+ has 170 positive,
199 negative and three unchanged, with 148 missing. Extreme moves include
−74.1439% and +50.2123%; corporate-action identity gaps constrain interpretation.
The mean and median comparisons differ, observation availability is selected,
and repeated symbols/dates are dependent. This is not a randomized selection
effect, portfolio return or evidence of a trading edge. All regimes are RED;
there is no defensible multi-regime comparison. SPY source coverage is absent.

There are zero published fills/settlements, hence **no expectancy, win rate,
drawdown, exposure, concentration or cost-adjusted portfolio estimate**. The
predeclared 0/5/20 bps per-side cost scenarios have an empty eligible settlement
sample, not zero measured costs or zero risk. Daily observations cannot resolve
stop-limit path/queue/first-30-minute eligibility. No ambiguous trade was dropped
to market the remaining subset, and no synthetic minute paths were invented.

Two runner defects were caught during independent construction: substituting
Decimal midpoint rounding changed the established binary-cent boundary, and
an early outcome collector omitted full retained frames and matched an overlap
from the wrong capture. Both were corrected before the final event figures;
the initial subset figures are not promoted as a separate winning strategy.
No production numeric gate changed. The first-pass mismatch counts and final
zero-mismatch result are explained in the regression evidence, not hidden.

## Repairs and prospective effects

- Correct default Sonnet 4.6 schema delivery and independently gate supported
  capabilities. One schema/mapping remains the request/validator source.
  Unsupported combinations stay controlled. Exact SDK binding and mocked
  payload tests pass; this is not a measured live acceptance improvement.
- Extend images through the measured leg/base and date the context. Nine retained
  reviews clipped leg starts: ABBV (September 17), HSIC (22), MET/IEX/DCO/IR/LTH/MSM
  (23), PAG (25). The new PAG control covers May 19–September 25, 90 rows. Original
  images and replies retain their hashes. Authority validation is unchanged.
- Remove asymmetric skip-versus-A encouragement; clarify the selected information
  set without softening evidence authority or categorical source concepts.
  CRL/IQV remain accepted semantic challenge cases: CRL's prose calls 0.80 an
  ordinary tightness ceiling although the threshold is 1.0; IQV's lower-volume
  rationale risks confusing A+ preference with ordinary C. Scalar/schema
  validation cannot prove visual truth. Prompt causality remains unmeasured.
- September 25's actual failed MSFT response cited Y evidence for overhead supply,
  outside its C-only authority. It is not a recycled explanation for September
  24. NIC/BIO remain wrong-authority and RVTY remains missing-measured-defect
  regressions. All remain rejected; no finding was dropped or rewritten.
  Separately, MSFT's prose describes 45% over 46 sessions while its retained
  measured citations record 35.3% and 45 sessions. This factual contradiction
  is distinct from the recorded authority rejection; free-text truth is not
  established by a valid schema or a correct numeric citation elsewhere.
- Add overlapping wait reasons, explicit population completeness and compact
  historical cases to the existing Latest scan / detail / Method / Record /
  My setups journey. Historical outcome reveals never replace current inputs,
  create orders or update saved originals. The synthetic walkthrough keeps its
  engineering label. Fix stale method text about the already-constrained limit
  and explain that September 24/25 digest changes are **membership only**:
  `rules.universe.identity` changes, not a numeric strategy constant.
- Keep historical reader-image links bound to their receipt's SHA-256 PNG;
  rotating `charts/TICKER.png` cannot identify an earlier image. The new journey
  caught and repaired that presentation defect before release. It also verifies
  saving the real CRL original, toggling later observations, Back and refresh.

## Smallest remaining acquisition / decision proposals — not executed

| Blocked claim | Exact next evidence / action | What it would not establish |
| --- | --- | --- |
| Full-population input and breadth corroboration for September 24/25 | First locate any unretained original full-universe objects in authorized storage. If absent, request separately authorized Alpaca `GET /v2/stocks/bars` daily SIP, split adjustment, the union of the two fully retained September 24/25 membership lists plus SPY, 2025-08-01 through 2026-09-25; OHLCV, timestamps, trade count, VWAP, pagination tokens, headers and retrieval time. About 1.5 million unique symbol/daily rows, tens to low hundreds of MB before compression. Preserve these as later-retrieved data, plus those original membership lists and a corporate-action/security-ID crosswalk; earlier sessions still lack full membership. Entitlement, retention/redistribution rights and any cost require confirmation. | Later retrieval cannot recreate original wire values or a missing point-in-time security master; it does not create accepted historical reader labels or trading edge. |
| CRL/IQV and exception causes | Separately authorize retained/revised SIP daily responses for September 23–25 and matching trade pages/condition codes for CRL/IQV and the 31-name union of exceptions; security-class and corporate-action records. Keep exact request feed/session/adjustment and all page tokens. Trade volume may be large; size/cost are unknown before entitlement and provider limits are checked. | Daily or minute sums alone do not adjudicate trade-condition differences. A returned bar does not authenticate the earlier absence's cause. |
| Executable first-30-minute entry / exit timing | After a real qualified case exists, retrieve existing or separately authorized SIP trades/quotes (or genuine minute bars with narrower claims) for its applicable entry session 09:30–10:00 ET and management sessions. Use actual session close/shortened schedules and consistent adjustment. Source: Alpaca historical trades/quotes/bars endpoints; fields timestamp, prices, size, exchange/conditions, bid/ask and pagination. Size and paid entitlement unknown. | OHLC minute bars still do not establish queue position, partial fills or brokerage execution; no-progress same-close timing needs an explicit policy decision. |
| Quality-selection value / broader edge | Review a versioned, source-supported selection/exit proposal and predeclare a new untouched historical universe with permanent security identity, delisted names and sufficient adverse/transition regimes. Obtain licensed point-in-time membership before requesting prices. No suitable complete dataset or entitlement is currently connected. Future reader/human reviews need separate authorization and leakage labels. | No affordable dataset or model call alone certifies the full accepted-reader strategy. Current small, reused, RED-only sample cannot supply this claim. |

The exception union is 31 securities (16 + 22 − 7). No security was removed
after observing missing data; no policy or provider was changed to improve the
denominator. These are bounded proposals, not approval to call an API or deploy
personal capital. Review these alongside the completed independent work.

## Reproduction and acceptance

From a clean full-history checkout, without credentials:

```bash
python -m pip install -r tools/requirements-historical.txt
MPLBACKEND=Agg python tools/historical_validation.py --output /tmp/spicystock-poc --cache /tmp/spicystock-originals --original-replay --simulate
python tools/build_historical_review.py /tmp/spicystock-poc
MPLBACKEND=Agg python -m pytest tests/ -q
MPLBACKEND=Agg python tools/make_fixture.py --check
python tools/historical_repair_mutations.py --output /tmp/spicystock-mutations.json
npm install --no-save --no-audit --no-fund playwright@1.56.1
npx playwright install chromium
node tools/continuity_check.mjs
node tools/chart_check.mjs
node tools/page_smoke.mjs --shots /tmp/spicystock-page-shots
node tools/historical_journeys.mjs --output /tmp/spicystock-history-shots
SCSTOCK_TEST_RESIZE_DELAY_MS=350 node tools/page_smoke.mjs --only chart-keyboard --shots /tmp/spicystock-delayed-layout
```

The replay blocks sockets, uses no random sampling and writes isolated outputs.
Immutable original-code replays are cached. Machine results include the actual
source-file hashes, checkout head, fixed clock, dependency versions, elapsed
seconds, peak RSS and artifact bytes. Results were generated from a worktree
based on the spec commit; those file hashes identify the implementation even
before its final commit. Normal final-head checks and exact PR revision are
recorded in the handoff/PR, not inferred from that earlier checkout SHA.

The first full Python run had four proxy-environment failures (missing socksio);
the affected baseline grader tests passed after installing it. A later complete
run had only a stale documented test-count failure; the count was corrected.
The first full browser run caught the added summary pushing phone/desktop
controls down; the summary was made compact and omitted on ticket days. Neither
environment failures nor failed layout runs are counted as passing acceptance.

The #91 consumer test also exposed an intermittent pre-existing capture race:
the saved chart's SVG was captured at detached width 640, then its normal
ResizeObserver redrew it at visible width 730. One complete run passed 8,409/8,409;
two other full runs detected this race. Untouched application code with a labeled
350 ms ResizeObserver-delivery control reproduces eight equality failures
(251/259). Waiting for visible SVGs to fit their actual hosts before the keyboard
baseline gives 259/259 under the same delay. Exact SVG/peer equality, native keys,
focus, scroll and geometry assertions remain unchanged; no assertion is skipped.
This is a test timing repair, not a claim of a keyboard regression in production.

The first extended save-journey check expected a whole-page destination; the
established app opens a saved-detail dialog. That harness expectation was
corrected, without changing application save behavior. A directory secret scan
during browser mutation cases saw public breadth rule identifiers in temporary
generated fixtures; the final committed-range secret scan is reported separately.

Original code and isolated restored-defect mutations both fail the new reader
request/chart regressions, while unchanged controls pass. The browser baseline
lacks both overlap explanations and the study; a restored summary omission is
also detected. Existing adversarial suites cover transport pagination/duplicates,
wrong symbol/session/adjustment, missing bars, null-vs-zero citations, receipt
mutation, cash/slots, stop gaps, same-bar ambiguity, repeated and interrupted
publication. 116 append/alter-future controls pass over outcome-independently
chosen retained cases. Independent cent-band/share checks agree for all 5,215
candidate records. Synthetic accepted reviews never count as human labels.

Browser evidence uses agent-operated Chromium/Playwright, 390×844, 320×844 and
1280×844, both themes, with touch emulation on narrow widths. Native browser
keyboard/focus/scroll and comparison checks from #91 remain required. Screenshots
and measured chart/page geometry are inspected. Physical-device, assistive-
technology and human-usability certification are NOT RUN.

The [browser acceptance manifest](2026-09-28-evidence/browser-acceptance.json)
records actual source-file hashes, dataset/rules, clock, routes, viewport geometry
and 85 checks. Its checkout-head field is explicitly a dirty-worktree base, not
an assertion that the base contains the new implementation. The final PR tree
contains those exact application bytes. Seven retained, inspected images include
both themes, phone/narrow/desktop, saved-original research and the complete PAG
reader context. [Browser negative controls](2026-09-28-evidence/browser-controls.json)
keep the baseline failures and restored-defect failures separate from acceptance.
The save path preserves the original record and cannot acquire an order from
the subsequent-observation reveal. [Executed verification](2026-09-28-evidence/verification.json)
records commands, runtimes and log hashes. [The resize control](2026-09-28-evidence/keyboard-resize-control.json)
records the reproduced eight failures, 259/259 repair and eight restored-defect
failures, retaining every SVG equality assertion.

## Gate verdicts

| Gate | Status | Scope / exact remaining blocker |
| --- | --- | --- |
| Original replay agrees with available retained evidence | PASS | Nine complete candidate-source replays; four early source layers remain BLOCKED, no missing reply invented. |
| Required data adequate for claimed component/replay analyses | PASS | Retained normalized candidate values and explicit selected-population study only. |
| Required data adequate for full-universe performance | BLOCKED | Missing historical full universes, permanent identity/actions and intraday execution observations. |
| Inputs and material disagreements accounted for | PASS | Values, membership, missingness and decision sensitivity enumerated; cross-source truth remains unresolved. |
| Current-policy software path reachable / zero causes explained | PASS | Synthetic full pipeline witness and overlapping historical blockers; no approval imputation. |
| Real-data historical qualified-plan end-to-end case | BLOCKED | Zero accepted final A/A+ under 13 RED publications; no genuine qualifying case found in the declared sample. |
| Executable cost-adjusted historical performance | BLOCKED | Empty settlement sample; no expectancy or edge claim. |
| Wait/history/conditional-control website journeys | PASS | Agent-operated acceptance; real qualified historical journey remains BLOCKED. |
| Regression gates / historical immutability | PASS | Local final-source gates: 1,541 Python; 12 current fixtures; 127 continuity; 378 chart; 8,409 full browser; 85 historical journey checks. 8,577 protected files unchanged; committed-range secret scan clean. Exact remote-head CI is recorded separately in the PR. |

Software readiness, data reliability, strategy fidelity, decision quality and
trading-edge evidence are separate. Request construction and UI repairs do not
repair missing data or validate subjective judgments. Independent review is the
next release action. After an authorized merge, the next existing scheduled run
may supply prospective operational evidence; it has not happened and is not
promised to be healthy.
