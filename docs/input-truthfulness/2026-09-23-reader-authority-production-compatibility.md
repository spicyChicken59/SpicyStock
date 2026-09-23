# Reader contract and evidence retention — 23 September 2026

## Result and acceptance boundary

**PASS — repository observation and deterministic reconstruction:** all twelve
real requests, original mechanical scores/grades, rejection errors and fallback
decisions reconstruct exactly. **FAIL — diagnosed software contracts:** the
default-model request omitted the required nested finding shape, and the grader
discarded response text before returning rejected attempts. This change corrects
those two defects prospectively without enlarging the authority allowlist.

**BLOCKED — complete incident closeout:** the actual twelve model replies were
not retained. Neither their exact field sets nor their parsed scores, findings,
semantic authority or otherwise valid findings can be recovered. There is no
honest failing-before/fixed-after replay of those replies, and no evidence that
any particular real response becomes acceptable. This is a bounded prospective
correction for Guidance review, **not a claim that the requested stopping
conditions have all been met**. Obtaining original response bodies from an
independently retained trace would be needed for response-level closeout. A fresh
model call would not recover these historical replies and was not made.

## Identities and original evidence

- Verified starting main: `897f507aa2a85f4493c7cc742661d06a1a8ba6f8`, zero open PRs.
  Parents: `e2dee988ad5d36876b7c73090502720e995c65f4` and
  `1c95d0ea686121ac25c6ef1d05610f2bcfb53142`.
- [Production run 35802203679](https://github.com/spicyChicken59/SpicyStock/actions/runs/35802203679),
  attempt 1; job `106994857638`; session `2026-09-22`.
- Execution checkout: `6533e616bd14ebfebeeccb4c9b1b0d463b47dbb4`.
- Publication commit: `e2dee988ad5d36876b7c73090502720e995c65f4`.
- Publication SHA-256:
  `507127d7a6e07f2d1120290c96cd717e1ef72529be8053218d317bb9b9ee3c36`.
- Ledger: `docs/quality-ledger/v1/507127d7a6e07f2d1120290c96cd717e1ef72529be8053218d317bb9b9ee3c36.json.gz`.
- Evening artifact `10726366526`: 27,077,922 bytes, SHA-256
  `69f923df412d5e3df77944e1f445f5c55c434606bcefa132be19c651514a429a`.
- Input-exception artifact `10726716152`: 249,640 bytes, SHA-256
  `fb01fd76faf9b601b0db7107f078a377647972a1f9d7e3fea86c4f18cc49a38d`.

**PASS — real production artifacts:** both original ZIP hashes match GitHub's
artifact metadata. Evening `data.json` is byte-identical to the publication.
Its 6,145 files comprise data/picks, 12 charts, 3,863 history files and 2,268
evidence objects (2,206 frames, two system texts and 60 PNGs). No response object
exists among them. The input artifact contains `input-exceptions.json` and the
compressed universe directory; it does not contain model replies. The complete
scan job log records twelve HTTP 200 model responses, each followed by the same
authority error, without logging reply text.

**PASS — real input accounting:** 4,778 intended stocks excluding benchmark,
4,763 ready (99.6860611134%), 15 stale; 3,726 scan-ready and measured; 1,037
price-excluded; 513 quality successes; zero scan and quality errors. Matches are
108 burst-only, 307 Dollar-only, 98 both and 3,213 measured non-matches.
This is a real post-#84 observation. No provider cause is inferred.

## Audit A: all twelve attempts

Every candidate has one attempted `claude-sonnet-4-6` request, no correction,
`outcome: rejected`, and the exact error:

```text
src.ReaderAuthorityError: finding has missing or unauthorized fields
```

| Ticker | Mechanical grade | Mechanical score | Final historical grade | Reader result | Raw reply / parsed score / findings |
| --- | --- | ---: | --- | --- | --- |
| IOSP | A+ | 10.0 | A+ | fallback | BLOCKED |
| KYMR | A+ | 10.0 | A+ | fallback | BLOCKED |
| HSIC | A+ | 9.0 | A+ | fallback | BLOCKED |
| IDCC | A | 10.0 | A | fallback | BLOCKED |
| CLMB | A | 8.5 | A | fallback | BLOCKED |
| CRVL | A | 8.5 | A | fallback | BLOCKED |
| MEDP | A | 8.5 | A | fallback | BLOCKED |
| NEM | A | 8.5 | A | fallback | BLOCKED |
| PYPD | A | 8.5 | A | fallback | BLOCKED |
| WPM | A | 8.5 | A | fallback | BLOCKED |
| AG | A | 8.0 | A | fallback | BLOCKED |
| AIT | A | 8.0 | A | fallback | BLOCKED |

The published reader score/grade/reason are null, not model zeroes. The internal
transport fallback is deterministically reconstructible as `ungraded`, score
0.0 and `AI unavailable; checklist not measured.` because these metrics contain
`quality_passes`, not the fallback's legacy `passes`/`of`. That internal score
does not replace mechanical quality. No change to that unrelated fallback
scoring path is proposed. The red-regime publication remains DEGRADED and
`Stand aside.` with no usable model judgement for any of the twelve names.

**PASS — exact request reconstruction:** the companion
[inventory](2026-09-23-reader-production-inventory.json) stores each candidate's
original reader/attempt/input record, mechanical/final result, reconstructed
metrics and all exact request, system, text, chart and metrics identities.
`tools/audit_reader_production.py` rebuilds them with the untouched execution
checkout, supplied archived system object and exact chart bytes, and asserts
every retained hash. The common system-text SHA-256 is
`65e7e197aa48872a6bb60de56b0d5b9dc972031acec576c9503c758a7b062f07`;
its object is `74f8f55c9fb3eea195cece6c651edfc4a64bde9ce0c8cbb09995ba2dd1ab2d53`.
This intentionally uses the execution rulebook, not #87's later source wording.

The production guard checks either a non-object finding or a field set unequal
to `{criterion, source, evidence, observation}`. Thus each reply reached parsed
score handling, passed the discovery conflict check and reached this guard with
a nonempty, bounded findings list. **BLOCKED:** whether any particular response
had missing keys, extra keys or a non-object item. It is equally unknown whether
earlier findings in that list had already passed, or later ones would have
failed different rules. No evidence supports attributing the incident to a
particular extra field, observation, path, source, null, or numeric encoding.

## Audit B: the four contract layers

| Layer | Starting observation | Prospective correction |
| --- | --- | --- |
| `knowledge/strategy.md` | Requires source-grounded findings but delegates their shape to the request; uses singular `finding` in one sentence. | Names the `findings` array and its exact nested fields; keeps #87 attribution and all strategy numbers. |
| `grader.SCORE_SCHEMA` / `_reply_shape` | Schema correctly closes finding/citation fields. The default Sonnet request does not send `output_config`; `_reply_shape` replaces the entire nested schema with a prose placeholder. | `SCORE_SCHEMA` consumes the shared `reader_authority.FINDINGS_SCHEMA`. |
| `reader_authority.instruction()` | Gives source/criterion/observation vocabulary and one citation example, but no exact finding object, required key set, citation-array shape or prohibition on extra fields. | Emits the same full nested schema for every model, plus explicit dot-path, identifier and no-extra-field instructions. |
| `reader_authority.validate()` | Requires exactly four finding keys and exactly two citation keys. Enforces contextual source/path/value authority. | Reads those closed key sets from the same schema. All semantic checks and accepted field sets remain identical. |

**FAIL before / PASS after — offline software regression:** the default-model
request lacked a nested response contract it strictly enforced. This is a
verified prompt/schema exposure defect; its being the cause of any particular
lost reply remains **BLOCKED**. No evidence shows that our prompt explicitly
invited a particular forbidden field, or that the model ignored a fully explicit
finding shape.

Schema validity remains necessary but insufficient: runtime checks bind each
criterion to its source, allowed check letters, actual values and chart presence.
These candidate-dependent constraints are described in the instruction and
enforced in the validator. All finding/citation fields are required; none are
nullable optional fields. Citation values may have scalar JSON types, but null
and UNMEASURED cannot supply adverse authority. Top-level parsing retains its
existing compatibility behavior, including deriving grade from score and treating
omitted findings as empty for confirmation; the canonical answer still requests
the explicit array. No lower grade can pass without a finding.

**PASS — unchanged normalization:** JSON numeric `1`/`1.0` equality already
worked. Boolean/numeric equivalence, numeric strings, rounded/different numbers,
nonfinite numbers and object/list evidence values remain rejected. No observed
evidence justifies new normalization, arbitrary fields, free-form observations
or compatibility aliases. `additionalProperties: false` remains in both objects.

## Audit C: semantic authority

**BLOCKED for each of IOSP, KYMR, HSIC, IDCC, CLMB, CRVL, MEDP, NEM, PYPD,
WPM, AG and AIT.** No retained finding is available to classify as permitted,
supported, exact deterministic, chart-only, unsupported or contradictory.
`findings: null` in the inventory means unknown, never an empty confirmation.
The original shape rejection cannot establish semantic validity or invalidity.

**NOT RUN — real-response acceptance after correction.** No real September 22
reply is claimed newly accepted, intentionally still rejected, or repaired.
The validator accepts the same canonical authorized shapes as before. Scripted
responses over genuine retained inputs are explicitly counterfactual controls;
they cannot substitute for the missing real responses.

**PASS — offline authority controls:** an exact recorded FAIL/PARTIAL may
support a measured downgrade; a qualitative finding needs a chart and unchanged
cited facts; confirmation permits `[]`; integer/float numeric equivalence works.
Unsupported numeric thresholds, foreign discovery requirements, missing charts,
contradicted facts, unknown evidence, extra fields and free-form observation
identifiers remain rejected. A model cannot raise the final mechanical grade.
Fallback remains marked, and the complete rejected attempt is retained.

## Evidence-loss correction and ledger

**PASS — ledger retention of facts supplied to it:** its twelve `reader` objects
exactly equal the publication; it retains mechanical quality, final grades, run
status/problems, input accounting and complete stale membership. **FAIL — incident
diagnosability:** rejected response text, response identity, parsed score/grade
and findings were absent upstream. `grade_candidate()` kept only request hash,
outcome and exception text. `_fallback()` then erased model judgement, correctly
for authority but without a separate diagnostic copy. History, evidence objects,
artifacts and ledger could not recover what was never supplied.

The correction captures returned text immediately after the existing API return,
before truncation, parsing, discovery or authority checks. Each attempt carries
unchanged concatenated text blocks, SHA-256, UTF-8 byte count, stop reason and
message ID. Text over 64 KiB is explicitly `omitted_oversize` with digest/size;
no partial string is presented as a whole reply. Transport failures have no
response object and never borrow the preceding attempt's response. Hidden
thinking and request headers are not retained. Parsed findings can be reconstructed
from exact text rather than silently normalized or duplicated.

The existing pipeline, reader-result seal and ledger deep copy already retain
the whole attempt. **PASS — offline integration:** rejected text survives public
record and ledger capture; changing it breaks the existing reader digest.
No ledger schema, bounds, capture timing or retention policy was expanded.
Oversize omission and a ledger capacity/write failure remain explicit evidence
limits, not permission to alter a decision. The response metadata is diagnostic,
never consulted to assign grade.

## Retry and budget decision

**PASS — repository observation:** parser/score-format failures already receive
one explicit format-correction retry; transport failures can retry the same
request. Authority and discovery failures intentionally stop immediately. The
production run used exactly one application attempt per name. Authentication
failure still stops further futile calls.

No new structural retry is justified without the lost findings: the common guard
does not prove a harmless repair, and structural validity does not prove semantic
authority. Retries, candidate limit, token limit, cache policy, correction text
and down-only behavior are unchanged. Offline tests verify distinct request
hashes and unchanged system prefix for the existing parser retry and retention
of both attempts. No downgrade-coaxing retry is added.

## Verification and preservation

Runtime: Linux, Python 3.12.14, pytest 9.1.1, pandas 3.0.6, NumPy 2.5.3,
exchange_calendars 4.13.2. Test sockets are disabled by the repository's normal
test isolation. Dependencies were installed for local execution only.

| Check | Result | Evidence |
| --- | --- | --- |
| Untouched starting implementation + new contract/retention tests | FAIL | 11 intended failures, three unaffected controls pass; source under `897f507` has no changes. |
| Corrected contract/retention selection | PASS | Same selection: 14 pass after correction, with the inventory test excluded; no repaired historical response fixtures. |
| Real September 22 response failing-before/fixed-after | BLOCKED | All twelve response bodies and findings were discarded. |
| Grader / authority / provenance / pipeline / ledger focused tests | PASS | 216 passed before adding the incident-inventory preservation test. |
| Original September 22 publication verification | PASS | Untouched execution implementation verifies 518 candidate receipts and original picks/source objects. |
| Fixture verification | PASS | All 12 fixtures current; only synthetic prompt/response provenance changes. |
| Full normal pytest | PASS | 1,466 passed in 101.61s. Initial run failed only the stale CLAUDE.md count; corrected to the actual collection count. |
| Continuity / chart / page gates | PASS | 127 continuity, 182 chart, 7,637 page checks; desktop/mobile screenshots inspected. |
| Exact-head CI and Secret Scan | NOT RUN | Automatic PR checks to be linked on the final PR head before handoff. |
| Fresh model/provider calls, scan, workflow dispatch/rerun, refresh, email, manual publication | NOT RUN | None performed. |

Reproduction commands, using the repository's dependencies and offline doubles:

```sh
git worktree add --detach ../reader-execution 6533e616bd14ebfebeeccb4c9b1b0d463b47dbb4
python tools/audit_reader_production.py --implementation ../reader-execution --output /tmp/reader-inventory.json
python -m pytest tests/test_reader_compatibility.py tests/test_reader_authority.py tests/test_grader.py tests/test_provenance.py tests/test_pipeline.py tests/test_quality_ledger.py -q
python -m pytest tests/ -q
python tools/make_fixture.py --check
node tools/continuity_check.mjs
node tools/chart_check.mjs
node tools/page_smoke.mjs --shots /tmp/reader-shots
```

For failing-before evidence, copy only `tests/test_reader_compatibility.py` and
`tests/test_provenance.py` into an untouched `897f507` worktree, then select the
compatibility file and `test_rejected_response_survives_publication_and_ledger`
with `-k 'not all_twelve_real_incident_records'`. This yields the eleven intended
failures and three unaffected passes. The excluded inventory test verifies a new
audit artifact, not changed production behavior. Run the same selection in the
corrected checkout for the fixed-after result. The original-publication command
is `tools/verify_provenance.py --record <publication>/data.json --picks
<publication>/picks.json --objects <publication>/evidence`, executed from the
untouched execution checkout so its historical request text is reproduced.

**PASS — preservation:** all 6,133 Git-retained files also present in the evening
artifact are byte-identical. Its twelve chart-name files are artifact-only; their
exact content-addressed PNGs are retained and request-hash verified. All 46
synthetic candidate rows preserve mechanical/final decisions and plan content.

**PASS — regression isolation:** nine response-retention cases still pass with
the old underspecified prompt restored in memory; the prompt-schema regression
still passes with response retention disabled in memory. Neither fix is using
the other defect as its failure trigger.

No production data/picks, history, evidence objects, ledger bytes, charts, inputs,
strategy thresholds/weights/gates, scoring, segmentation, market/plan rules,
website/design, secrets/settings/schedules or sibling application files changed.
The fixtures were regenerated by the real offline fixture harness and retain
their original synthetic decisions. Historical verification uses the original
execution implementation for prompt/request hashes, not today's changed prompt.
README, provenance/input docs and `.env.example` were reviewed; configuration
is unchanged and the environment template needs no edit.

**KEEP:** #84 universe correction, #85 ledger, #86 authority principle, #87 source
attribution and truthful degraded fallback. **FIX NOW:** explicit nested prompt
contract and proven rejected-response evidence loss. **DEFER:** incident
response-level closeout until original bodies exist, stale-provider causes,
human-labelled C segmentation, profitability and broader strategy work.
**OMIT:** authority weakening, invented responses, historical regrading, tuning,
A+ manufacturing, UI/portfolio/brokerage work, fresh external execution and merge.
