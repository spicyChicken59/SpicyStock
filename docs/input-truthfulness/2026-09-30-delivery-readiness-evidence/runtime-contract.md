# Representative synthetic runtime contract

This benchmark measures the integrated delivery candidate. It authorizes no
provider request, owner-key access, historical-workflow dispatch or real release.
The existing Tests workflow runs independent central and stress jobs only for a
pull request. Both use standard `ubuntu-24.04`, Python `3.12.14`, every direct pin
in `tools/requirements-historical.txt`, and verified age. Actual installed
distributions, checkout/source hashes, runner image identifiers, CPU affinity,
available memory and disk are recorded. Ordinary pytest and browser checks keep
their existing independent jobs.

The PR96 generator, seed, numeric lexemes and data shape remain fixed: 96 bulk
queries, 288 sessions per query, 2,753,568 bulk rows plus two probe rows. A fresh
Linux runner declares that the old local fixture cache is unavailable and
generates that same synthetic fixture once. This is neither a provider model nor
a shortened rehearsal. The representative entry point checks the unchanged
arithmetic source bytes before acquisition, then compares every generated raw
page, query manifest and both complete v2 reconciliation files with PR96's
published member inventory. SQLite's cross-platform file layout is not presumed
identical; the current run's ledger bytes and accounting must survive delivery.

The actual package encoder reports format, archive/index/tar/expanded sizes and
hashes before its original cap check. Profiling does not decompress the archive
again merely to count bytes. Actual age encryption uses a disposable test-only
identity. Recovery verifies every original member's bytes, hash and length and
unchanged accounting. Reconciliation then runs again from the recovered cache;
both resulting files and returned metadata must exactly match the first pass.
The disposable identity is removed even after a handled failure.

## Profiles and budgets

`historical_runtime_profile.instrument` records parsing, cache validation,
normalization, projection, projection hashing, reference preparation/reference,
production comparison and serialization. The orchestrator separately records
acquisition, inventory, package and recovery work. Nested wall and process-CPU
totals have both inclusive and exclusive values; inclusive totals overlap.
Current process RSS and logical scratch file sizes are sampled, so their peaks
are lower bounds. Linux child RSS is the cumulative high water of completed
children, including git, test key generation and age. Parent and child peaks are
separate; their conservative sum is not a simultaneous or age-only measurement.

Each complete two-date offline pass has one 1,800-second deadline. The recovered
pass is a separate verification pass, not a way to divide the production offline
step. Packaging has one 600-second deadline. Linux SIGALRM produces a handled
receipt when delivered at an interpreter boundary; an unusually long native
call can delay delivery. The matrix job retains the original 75-minute outer
ceiling. Partial metrics and a final failure receipt are retained for handled
refusals. A hard runner loss can still prevent final receipt creation.

The prospective execution arithmetic reserves the full 1,800-second acquisition
step, including the unchanged 1,500-second internal guard and failure handling,
then adds measured setup, initial two-date reconciliation and packaging. It also
reserves 300 seconds for guard, a second checkout, preflight and upload. This is
an explicit conservative planning **ASSUMPTION**, not measured runtime or a
guarantee. Both remaining time before and after that reserve are reported;
insufficient headroom fails acceptance. Simulated transport
clock jumps are separately labelled and are not measured HTTP time. The current
289-request fixture waits roughly 840.014 simulated seconds under the original
burst-capable limiter. A lower provider quota, retries or HTTP delays can still
exhaust the unchanged acquisition guard; a synthetic PASS never promises real
input completeness or operative readiness.

The benchmark requires 8 GiB of measured free scratch at entry. This is a local
test preflight, not a change to any evidence cap. The strict archive reader can
temporarily hold source, recovered content and a bounded decoded-tar spool,
plus compressed/ciphertext files. The original 2 GiB true expanded content,
199 MiB archive and 200 MiB ciphertext caps remain separate and unchanged.

## Evidence and repeat work

Only `benchmark-result.json`, `runtime-profile.json`, the small synthetic member
inventory and a possible preflight-refusal receipt are uploaded. Raw pages,
reconciliations, archives and disposable identities are not workflow artifacts.
Artifact results are measured evidence for their recorded source bytes, not for
a later changed implementation.

The cost gate always runs initial/reopened reviews. On a synchronize event it may
skip only when Git verifies the exact observed `before` to pull-request-head
range is ancestral and every changed file is on the explicit documentation/new
evidence whitelist. Unknown paths, missing event coordinates, missing commits or
failed diff inspection run the benchmarks. The skip receipt says **NOT RUN**;
it does not manufacture a new PASS or silently reuse another revision's result.
This leaves ordinary pytest and browser checks active on documentation pushes.

Local small profiles validate instrumentation and byte preservation. Full-shape
representative performance is established only by the actual PR-job receipts;
Windows measurements and normal CI under different dependency versions remain
distinct evidence.
