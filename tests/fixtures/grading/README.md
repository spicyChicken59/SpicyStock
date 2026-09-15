# Scan-aware grading evidence

The audit is a fixed snapshot of the bounded public recovery catalog at main
`4f640d95f154ece89d26f57e76ca53a4e0abc0f2`: 21 calendar days of retention,
actual dates September 11 and 14, 2026, three published revisions. It covers
1,404 entries (1,359 reaction candidates, 45 anticipation candidates). All
36 chart-reader replies were read in full: 29 dollar-only, seven both, zero
burst-only. All entry SHA-256 values and all three context hashes matched the
public index; all 36 reviewed rows also matched their original data Git blobs.
A mechanical
percent/threshold search helped locate candidates; classification required
manual inspection of reason, key risk, entry note and the recorded admission.
For example, HAE's **24%** volume decline is not a **4%** discovery claim.

`history-audit.json` preserves each reviewed row's source/date, original grades,
measurements, reader text, classification and independent-reason disposition:

| Classification | Published rows |
| --- | ---: |
| Explicit inapplicable 4% minimum | 8 |
| Universal percent-only disqualification without naming 4% | 1 |
| Ambiguous contextual critique; cross-scan contradiction unproven | 2 |
| No discovery contradiction observed | 25 |

The eight explicit rows are CACI and ROKU on September 14; EPAM and DGX in
both September 11 revisions; CAKE and ADP in the later September 11 revision.
The earlier ADP revision is the ninth definite admission conflation. The
earlier CAKE and September 14 ADUS critiques mix percent gain with base/gap
context; they are not counted as proven alternative-rule rejections. ADUS's
gap-versus-intraday-range wording is an adjacent measurement concern, deferred.
All nine definite cases also cite independent quality concerns. None proves
a desired corrected grade. No historical output was rewritten.

`burst-CACI.json`, `burst-ROKU.json` and `record.json` are byte-for-byte copies
from `docs/history/a89ab122d7e0160df6a63c30957668447ace1103/`. Both rows were
also compared with the original September 14 data Git blob
`a89ab122d7e0160df6a63c30957668447ace1103` and matched exactly. Copies in this
test directory preserve regression inputs after the public window expires.

`tests/test_discovery_grading.py` tests the three routes from real synthetic
scanner frames, archived thresholds, exact historical contradictions, legitimate
quality lowering, request determinism, archiving and honest fallback. Scripted
replies for all nine definite cases are quarantined whole, without retry;
no grade is inferred by deleting an offending sentence. The guard recognizes
reviewed constructions and numerical threshold variants. It is deliberately
documented as a limited guard, not proof of arbitrary future prose's semantic
correctness. No model/provider replay was performed.

The page trace is `burstDecision()` (measured summary versus reader),
`discProvenance()` (reason, key risk, entry note and model grade),
`findEarlier()` / `savedSignalSection()` (dated original research), and the independent
ticket/session action gates. `node tools/page_smoke.mjs --only grading` opens
both archived cases at desktop dark, 390px light, and 320px in both themes. The old
contradiction stays visible as **Original chart reader / Historical research
only**, alongside its unchanged grade, session, source and no-ticket status.
