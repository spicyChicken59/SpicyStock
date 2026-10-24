# Recommendation provenance v1

The September 28 reader request repair adds `grading.reader_request_version = 2`
to prospective rules. Its dated image context is included in reader metrics and
their digest. Old requests, raw responses and receipts remain unchanged; full
replay uses their original code, not new request semantics. See the
[historical validation review](../input-truthfulness/2026-09-28-validation-review.md)
for exact original-code coverage and missing evidence.

Every new reaction candidate and top anticipation plan receives a content-derived
`evidence.id`. This is a decision receipt, not an execution record, an authenticity
signature, a backtest or evidence of trading edge. `docs/picks.json` remains model
plan history; its shares are suggested quantities. Browser annotations are private.

## Identity and canonicalization

`src/provenance.py` owns `typed-json-f64hex-v1`. SHA-256 hashes a UTF-8, compact JSON
encoding of typed values. Objects use sorted string keys; lists preserve order.
Null, boolean, integer, float and string have distinct tags. Integers use decimal
strings; finite binary64 floats use Python `float.hex()` without decimal rounding.
Thus integer 0, float 0.0, -0.0 and false are distinct. Generic nonfinite evidence is
rejected. Equivalent key order or JSON whitespace does not change a digest.

Source objects preserve the actual frame's strictly increasing session order,
`YYYY-MM-DD` labels, and Open, High, Low, Close, Volume column order. Values are the
numeric float64 conversion used by the readers, with missing/nonfinite values
encoded as null. On reconstruction null becomes NaN. Separate scan and quality
digests call **the existing** `scans._bars` and `quality._arrays`; their different
treatment of invalid/nonpositive values is preserved. Anticipation uses
`watchlist._read`. Those readers' native cent-price and whole-share rounding is
part of the normalized view being hashed, with no additional rounding; the
separate source object retains the original float64 inputs. No digest is
calculated from the rounded browser `series`.
Discovery and checklist digests retain the precision of their actual serialized
outputs; full verification reruns their owning functions against the exact input.

An ID hashes the complete receipt before adding `id`. It binds ticker, kind,
session, rules version, sources, stage digests, reader outcome, gate and plan.
Its context digest binds the actual run/session identity, model, feed, universe
and input-population basis, coverage, calendar, timing, rules, breadth, sizing
assumptions, cash-budget decision and ordered candidate inventory. Adjustment
basis remains Alpaca split-adjusted. Operational durations, email status and
publication wall-clock timestamps are excluded. Identical evidence with identical
run facts has the same ID; changed source, reader result or relevant run identity
has a different ID. IDs never depend on a user's save state.

## Stage bindings

| Receipt field | Authoritative evidence and verification |
| --- | --- |
| `source` | Frame object, exact reader-view digests, row count, evaluated/prior session; feed/adjustment/universe live in bound run context. |
| `discovery_sha256` | Existing discovery v1 block, including admitted routes, measurements and applicable thresholds. No second threshold table. |
| `quality_sha256` | Every check, status/aliases, measurements, threshold, partial/unmeasured state, veto/reclassification, score and mechanical grade. Existing `quality.assess`, `score_of` and `grade_of` verify it. |
| `reader_input`, `reader_sha256`, `reader_source` | Exact prepared metrics/system/chart, initial system/user hash, actual per-attempt request hash, returned score/grade/reason or explicit fallback/not-graded. Existing `claude` means model source. |
| `final_grade` | Existing `grader.final_grade` can confirm or lower mechanical quality only. An unattempted/unavailable/rejected reader never supplies a fabricated score, grade or reason. |
| `gate` | Actual stored green/yellow/red regime, final grade, allowed grades, ticket boolean and specific withholding reason. Cash/slot cuts remain distinct. |
| `planning` | Actual planner kwargs, sizing assumptions, signal session, plan output and slim pick-projection digests. Existing plan builders and XNYS schedule verify all prices, suggested shares and applicable session. |

Mechanical, discovery, reader and plan outputs are sealed where produced, before
publication joins them. Verification cannot legitimize a changed upstream value
by silently resealing it. Planner errors are recorded as no-ticket outcomes.
Reader requests retain their existing transport/retry policy: exact request
kwargs include the chart bytes, metrics, system text and retry correction when
applicable. The retained image is the one actually prepared/read, which can show
a provisional mechanical plan before a reader lowers its grade. No call is replayed.
Prospective attempts also retain exact returned text before parser/authority
validation, including rejected and truncated replies, with a text digest, byte
count, stop reason and message ID. The 64 KiB text bound records an explicit
`omitted_oversize` gap; transport failures have no response object. These diagnostic
attempts are sealed with the reader result and copied into the quality ledger.
They never give a fallback a model score or grade. September 22 attempts predate
this retention and cannot supply their discarded response text or findings.

Top anticipation plans follow their actual measured path, with mechanical
`not_applicable`, reader `not_graded`, grade `watch` and no invented reaction
checklist. Their source, watch measurements, regime, plan and pick are verified.
Quiet research-only watch rows are not given fabricated reaction receipts.

## Publication, persistence and retention

`publish_bundle` verifies source objects and both in-memory records, stages the
actual report/picks serializers, and verifies their bytes after reading them back.
Only then are source objects retained and picks/data installed. A contradictory
new receipt is a pre-publication hard failure; it preserves the prior public pair.
Ordinary rename failures roll the pair back. This is not a crash-atomic multi-file
filesystem transaction: interruption between renames remains a recovery concern.

`write_objects()` writes and closes each staging file before atomic replacement,
including on Windows. Failure cleanup also runs after closure. If unlinking the
staging file fails, the original write/replace error is re-raised; publication
still fails and an unreferenced temporary file may remain. Successfully installed
objects from earlier in the batch can also remain, but no public record is
installed until all required evidence writes succeed. Content identities,
serialization/compression settings and retention bounds are unchanged.

The candidate carries the receipt once. Its plan and schema-2 pick carry compact
references with the same ID/context/plan/pick digests. New history snapshots retain
the original receipt, account/context and candidate order; catalog entries carry
the ID. New My setups originals freeze a reference. Private status, notes and
amount annotations do not change public evidence.

`docs/evidence/<sha>.json.gz` retains frames/system text once; `<sha>.png` retains
exact chart bytes once. Gzip uses `mtime=0`; hashes bind expanded canonical data,
or raw bytes for PNGs. The browser does not fetch these objects on initial load.
Each object is bounded at 256 KiB compressed **and expanded**, and the archive at
128 MiB. Existing different/corrupt objects are refused, never overwritten or
repaired. Capacity exhaustion withholds the new publication. **Retention
(24 October 2026), the explicit decision v1 deferred:** before each night's
objects are written and counted against the cap, `provenance.prune_objects()`
removes every object that no other file under `docs/` names -- the publication
and its compact reader, the 21-day recovery catalog, the research cohorts and
their journal, the quality ledger, the frozen validation cases and the dated
reports all keep what they name. A name is a full 64-character lowercase hex
run in a file's text (a `.gz` file read expanded); any 64 inside a longer run
counts too, while an upper-case spelling or a shortened prefix names nothing.
Every file outside the archive is read in full first: a link, a directory that
cannot be listed, a file that is not regular or is over 64 MiB, or a `.gz` that
does not expand removes nothing, and the capacity check then decides as
before. Inside the archive, unknown entries -- a link or a directory named like
an object among them -- stay. A removal that fails stops there; the run log
says how many objects had gone. The archive follows the catalog a night
behind: a night the catalog drops tonight leaves the archive on the next
publication. Removed objects stay in git at every commit that carried them.
The run log states what is left against the cap and what went, and warns above
80% of it.

**What the rule does not bound.** Some names are permanent: the dated reports
under `docs/input-truthfulness` (22.2 MB of objects on 23 October, none of them
added since), the quality ledger, which names every read chart for good, the
research cohorts and their journal, and the frozen validation cases. On a copy
of the 23 October tree with the publication, its reader files and every
recovery record removed, 31.9 MB stayed; the ledger's share grows by each
night's read charts, about 0.12 MB on a night of two reads and 0.8 MB on a night
of twelve. With the 78.2 MB the 23 October tree keeps, 56.0 MB of the cap is
left: about 70 sessions of twelve reads, or 480 of two, if the rolling part
stays its size, and the 80% warning comes first. What to do then -- a rule for
ledger-named charts or a larger cap -- is a decision for that day, not this one. A frozen case added on a branch cut before a night
removed one of its objects would merge naming an object the archive no longer
holds; `tools/freeze_validation_cases.py --check`, which CI runs, names it, and
git holds the object to restore. Actual chart
sizes vary; the fixture's fixed PNG double is not a production storage estimate.
The evening artifact includes evidence and history. There are no new settings.

Synthetic fixture providers use eight-decimal OHLC inputs and whole-share
volumes **before** the production pipeline reads them. This removes one-bit
NumPy scalar/vector exponential differences between CPUs. Production frames and
canonical hashing do not apply this fixture-only grid. The CI drift was reproduced
locally with `NPY_DISABLE_CPU_FEATURES=X86_V4,X86_V3`; both dispatch paths must
pass `tools/make_fixture.py --check` against the same retained source objects.

Picks v1 loads conservatively into v2, retaining every valid old row and extra
field. Old rows have no evidence reference; none is invented. Unknown future
schemas are refused rather than reinterpreted. Production data/picks and all
September 11/14 historical bytes are untouched by this change.

## Offline verification

```sh
python tools/verify_provenance.py --record tests/fixtures/page/full.json \
  --picks tests/fixtures/page/full-picks.json --objects tests/fixtures/provenance/objects
python tools/verify_provenance.py --archive docs/history/SOURCE_ID --objects docs/evidence
python tools/provenance_impact.py --json docs/provenance/measurements.json
```

CLI exit codes are 0 PASS, 1 FAIL with a specific break, and 2 PARTIAL with missing
layers. `verify_setup(candidate_or_plan, publication, picks, objects)` also checks
one supplied setup against its publication. Full verification requires retained
source objects; supplying picks additionally checks persistence and membership.
The pipeline requires both. Internal report guards explicitly use integrity-only
verification after the full publication boundary has verified sources.

Legacy publications report PARTIAL/unknown without retrospective reconstruction.
An archive whose rules differ from the installed implementation reports PARTIAL,
verifies retained identities and requests a compatible checkout for rule replay.
It is never regraded using new rules. This verifier detects contradictions and
accidental tampering, not an author deliberately replacing evidence and all hashes.

The `full` fixture's AAPL reaction on 2026-09-10 has ID
`9883ec82500af184a1ea94075b5fd3df11f22a752bb2439bb45e9827476612b5`.
Its 113 split-adjusted source rows end on September 10 with September 9 as prior
session. Mechanical A+ plus a **simulated** 9.3/A+ reader result remains A+.
Green admits A+/A; the plan publishes four suggested shares, trigger $124.21,
limit $126.47 and stop $121.42 for September 11. Candidate, plan, persisted pick
and reconstructed recovery archive verify. The red fixture still has A+ quality,
but its gate records `ticket=false`, `reason=regime_gate`.

## Verification evidence and impact

Before implementation, eight injected contradictions all published: discovery
measurement, mechanical check, mechanical grade, upward final grade, changed
regime, stop, trigger and a different persisted pick. Their rejection assertions
failed while the actionable control passed. They now require a provenance-specific
failure before publication. Additional acceptance covers all eleven fixture nights,
yellow A+ only, reader lowering, unavailable/contradiction fallback, unattempted
reader, exact numeric views, source corruption, calendar mismatch, consistent-but-
illegal resealing, original recovery, legacy migration and source-retention bounds.

Seven isolated source mutations removed discovery, quality, reader-result,
down-only, plan-rule, calendar or picks guards. Every named detection test failed
for its required reason; a normal full-chain fixture and an unrelated tamper test
stayed green for each mutant. [Control results](mutation-controls.json) are retained.

Terminal local verification: **1,266 pytest tests**, **12 JSON fixtures plus source
objects current**, **89 continuity**, **182 chart**, and **4,161 page checks**, all
PASS. The 57 focused provenance cases are included in pytest. Desktop, 390px and
320px dark/light screenshots were inspected. The initial full pass caught an old
artifact-inventory assertion, which now requires the new retained inputs/history.

[Measurements](measurements.json) compare the same full fixture/picks and a new
recovery snapshot against base `f744b88a6117b933310f370b8f9ab4cd1d03a3c8`.
They include raw/gzip receipt and plan-reference sizes, retained source bytes and
full offline verification runtime. Whole-file totals also reflect the declared
synthetic-provider grid; receipt/reference sizes isolate the evidence payload.
No provider/model/email replay, deployment,
portfolio integration or design-system change is involved. Design v2.13.0 stays
vendored unchanged. Dollar-formula primary-source validation, live qualifying
ticket evidence and empirical profitability remain deferred.
