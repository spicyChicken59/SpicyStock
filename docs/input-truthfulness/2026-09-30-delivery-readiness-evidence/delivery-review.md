# Delivery and execution-binding review — PR97, 2026-09-30

The implementation follows Guidance review 5362976589 and
[continuation 5906480203](https://github.com/spicyChicken59/SpicyStock/pull/96#issuecomment-5906480203).
Base/main is `19f75f3b7ad566fb98e8e8e28fd2482a3737e9bc`, the merge of reviewed
PR96 head `ff0c194b754f110dfacda7a8f0cf2e86133ad6d5`, tree
`96e62c78a693e734b1b61a6c1c3d0b9b9f0142a1`. The first integrated runtime candidate is
`d53155bba5f63f42f65d21b4af708a3257b920f2`, tree
`e99d2e76ecdc4775771eb57d65abcb58bbe55b23`. Its dated measurements remain in
`candidate-first/`; they do not certify the later level-12 candidate. The bounded
comparison now selects level 12 as the best complete measured result, with stress
capacity still FAIL. The final runtime source is
`00a56f3dd4d8d2b68377364e04ed1f490e8e5c7c`, tree
`16c8241fe63eab575471fdc2e52254718f6ed685`, measured by Tests run
`36694310857` / native 373 / attempt 1. This is ordinary PR CI, not workflow
369770564. Final results have their own source binding.
No real release or acquisition occurs.

## Exact representation and archive contract

PASS — the accepted normalization/projection and reconciliation implementations
remain byte-identical to PR96. Their source SHA-256 values are respectively
`19c7ac5ecd0cc1cae1fb45cd5d9f11b731e9d1f7ca99ab418727f67e92b0e5a5` and
`f78e38a53ed3ebc1a99ae0d05d2626b497d49aa9b51c099751787c8019fffb1c`.
No strategy arithmetic, original raw file, membership or decision is edited.
The [protected-file result](protected-scope.json) checks 10,565 original blobs
outside the explicit authorized edit list. The [first source identity](source-identity.json)
and [final runtime source identity](source-identity-candidate.json) each compare
23 critical local files against binary-safe Git blob reads. The benchmark also
records its larger 28-file inventory, including the installer and prior expected
outputs. Git IDs and content SHA-256 are reported separately.

The [codec contract](codec-contract.md) specifies the new v3 receipt/index,
`ustar-zstandard-v1` outer archive and literal `evidence.tar.zst.age` delivery.
The reader retains old v2 gzip packages under their original schemas. It rejects
unsupported formats, changed execution bindings, extra frames/trailers,
truncation, corrupted content, unsafe members, excessive windows, index/metadata
and expanded limits. Original members are neither transformed nor omitted.

The [bounded comparison](codec-comparison.md) preserves the original gzip stress
refusal and both local 600-second incomplete codec trials. Those local trials
are FAIL for their bounded Windows timing and NOT RUN for complete size/recovery;
their partial lengths are not compression ratios. The new codec is accepted for
delivery only if the complete representative results satisfy every unchanged cap.

## Preserved first Linux candidate and bounded adjustment

Tests run 36690070837 / native 372 / attempt 1 used `d53155b`. Both cases
used Ubuntu 24.04 image `20260920.314.1`, Python 3.12.14, the historical direct
pins and four available CPUs. Each reported 16,765,378,560 bytes physical RAM.
Their [central](candidate-first/central/benchmark-result.json) and
[stress](candidate-first/stress/benchmark-result.json) receipts, full stage
profiles, member inventories, authoritative jobs/artifacts and verified-download
records remain separate from the final candidate.

| First Linux measurement | Central | Stress |
| --- | ---: | ---: |
| Initial two-date calculation, cap 1,800 s | 720.360607 PASS | 1,401.613271 PASS |
| PR96 scientific members, exact bytes/hashes | 388 PASS | 388 PASS |
| Packaging wall seconds | 600.097817 FAIL | 600.162784 FAIL |
| Recorded failure reason | ZstdError | ZstdError |
| Complete archive / encryption / recovery | NOT RUN | NOT RUN |
| Python peak RSS bytes | 4,334,104,576 | 4,790,198,272 |
| Sampled scratch bytes, lower bound | 1,611,608,914 | 1,985,394,069 |

The package failures occurred at the 600-second guard. The original error label
is preserved: the pinned C stream writer can replace a callback deadline with
its close error. The final profiler retains the explicit fired flag; it does not
infer a timeout solely from elapsed time. No scientific optimization follows
these results because both unchanged calculations fit their shared deadline.

The [bounded archive comparison](codec-comparison.md) then tried level 9 and
one final intermediate level 12 on the verified original stress cache. Level 12
completed in 189.145685 seconds, with all 390 source hashes preserved, but its
215,909,395-byte archive exceeded the cap by 7,242,771 bytes. No encryption or
recovery was attempted for that oversized archive. Level 12 is the best complete
measured setting in this bounded pass; no further codec/window search was run.

Normal-collected regressions preserve a valid control while demonstrating
restored gzip/trailer, index-accounting and decoder-window defects. The final
95-test package suite includes real age and exact legacy gzip recovery. Another
64 focused controls cover the actual small pipeline, both-date reproduction,
deadline propagation, incomplete replay timing refusal and missing optional
dependency metadata. [Intermediate validation](intermediate-validation.json)
retains earlier CI and local failures instead of treating them as final proof.

## Final Linux result and release decision

**BLOCKED - retain the execution hold.** The final candidate proves exact central
delivery and both complete initial calculations fit the original offline budget.
The complete stress archive still exceeds the unchanged archive limit. This is
the bounded best measured result, not a completed technical release.

| Final measured check | Central | Five-field stress |
| --- | ---: | ---: |
| Archive, cap 208,666,624 bytes | 99,741,871 PASS | 215,909,287 FAIL |
| Archive headroom, bytes | 108,924,753 | -7,242,663 |
| Ciphertext, cap 209,715,200 bytes | 99,766,407 PASS | NOT RUN |
| Ciphertext headroom, bytes | 109,948,793 | NOT RUN |
| Expanded payload, cap 2,147,483,648 bytes | 1,546,827,473 PASS | 1,866,624,707 PASS |
| Expanded headroom, bytes | 600,656,175 | 280,858,941 |
| Initial two-date offline seconds, shared cap 1,800 | 1,377.739460 PASS | 1,396.736550 PASS |
| Package seconds, cap 600 | 37.288482 PASS | 62.202810 FAIL (size refusal) |
| Recovered two-date offline seconds, shared cap 1,800 | 1,390.110803 PASS | NOT RUN |
| Original members recovered byte/length/hash-identical | 390 PASS | NOT RUN |
| Recovered ledger accounting unchanged | PASS | NOT RUN |
| All 388 PR96 scientific identities before packaging | PASS | PASS |

| Actual serialized components, bytes | Central | Stress |
| --- | ---: | ---: |
| Exact retained raw pages | 286,962,286 | 412,833,919 |
| Query manifests | 1,354,228 | 1,354,239 |
| September 24 full v2 output | 629,004,649 | 725,956,396 |
| September 25 full v2 output | 629,139,853 | 726,113,604 |
| Ledger | 86,016 | 86,016 |
| Original execution diagnostics | 2,676 | 2,675 |
| Internal manifest/execution/diagnostics | 210,461 | 210,460 |
| Index | 67,304 | 67,398 |
| Outer tar headers/padding, separate from expanded payload | 303,407 | 301,373 |

Both ledgers record 289 simulated transport slots and zero unresolved byte
reservations. Those are synthetic counters; actual provider requests are zero.
The scientific representation, population and generator precision are unchanged.

The [central receipt](candidate-final/central/benchmark-result.json) records
complete encryption, recovery, post-recovery preservation and exact reproduction
of both full files. Its ciphertext SHA-256 is
`7d5216288d697531434444046e9c7097ff2e27f6f85c6b2ca48c8a07af550852`.
The current package's 390 original members are verified against its own captured
inventory before and after recovery/replay. Cross-platform PR96 equivalence
covers the 388 scientific members; it does not presume SQLite bytes are portable.
Neither test changes the accepted owner package or its historical hashes.

Final runs use the same stated Ubuntu 24.04 image, historical pins and exact
source bytes as recorded in each receipt. Central's complete test took
2,896.733345 seconds, including its second verification pass. Python peak RSS
was 4,342,165,504 bytes and sampled scratch 4,788,654,819 bytes. The separate
completed-child high-water observation is 4,341,706,752 bytes: their
8,683,872,256-byte sum is conservative, not a simultaneous process peak or an
age-only measurement. Stress Python peak RSS was 4,787,785,728 bytes and sampled
scratch 2,082,333,732 bytes at refusal. Sampling is a lower bound for scratch;
filesystem allocation overhead is excluded. Both runners reported 4 available
CPUs, 16,766,410,752 (central) and 16,766,414,848 (stress) bytes host RAM, and more than
91 GB initial free scratch. Host counters are observations, not guaranteed
available resources for another run.

The central prospective production sum is 3,545.027942 seconds, including the
full 1,800-second acquisition reservation and 300-second assumed delivery
overhead, leaving 954.972058 seconds under 4,500. Stress's partial sum is
3,583.939360 seconds but is not admitted as a complete envelope: encryption and
recovery did not run. No scientific optimization or deadline change is made.
Stage-level CPU/wall, parsing, projection hashing, independent reference,
production comparison, serialization, inventories and package measurements are
in each `runtime-profile.json` and the independent audits. Inclusive nested
durations must not be added together; exclusive durations identify actual work.
The central profile includes its initial and recovered passes; stress includes
only its initial pass. The different observed durations between the first and
final runners are retained rather than presented as a timing guarantee.

The final stress [receipt](candidate-final/stress/benchmark-result.json) and
[independent arithmetic](candidate-final/stress-independent-audit.json) establish
the actual bounded result. The unchanged full shape produced 412,833,919 raw
bytes, 1,866,346,849 original-member bytes and a 67,398-byte index; the complete
expanded package is 1,866,624,707 bytes. Tar headers/padding add 301,373 bytes.
The archive is **215,909,287 bytes**, SHA-256
`0198197dad33ed363984f7e47e25adc9681932b2ed1b8ae65bf13c8c555d3405`, so capacity
is **FAIL by 7,242,663 bytes**. Encoding took 60.478218 seconds and the package
step 62.202810 seconds. The byte difference from the Windows trial is attributable
to this run's package/ledger metadata; the 388 scientific members match exactly.
It is not evidence trimming or an altered precision case.

Encryption, recovery and recovered replay are NOT RUN for stress. The initial
388-member comparison is PASS; a post-refusal sweep of all original members is
NOT RUN. `source_unchanged_through_run` verifies 28 code/config/input files, not
the retained raw-cache members. No uploaded plaintext fallback exists. The
disposable TEST-ONLY key was removed. The complete stress job remains FAIL and
is preserved even if later documentation-only CI skips this expensive job.

**One decision for Guidance:** retain every data/deadline cap and, only under a
separate instruction, permit one level-12 / 2 GiB-window synthetic comparison
with the same exact members, 600-second bound and declared 12 GiB process-memory
ceiling. This trades increased encoder/decoder memory allowance for a possible
size improvement; neither improvement nor fit is measured. It is not implemented
or authorized by this report. No further codec/window search runs in this task.
The unchanged 1 GiB-window candidate stays fail closed. Real-data entropy and
useful recoverability at arbitrary provider limits remain unmeasured.

The actual compact measurement artifacts are central **11088634733** and stress
**11088360331**, both from run **36694310857**, attempt 1, at `00a56f3...`.
Their downloaded ZIP SHA-256 values are respectively
`0d663261ca7391342c5320667418caece78877d57385a0dba0327b7c3783583b` and
`467f8da0316694b28d57a401b47ef2b907e34c149c565da5c590ca65ff1711fa`.
The [central](candidate-final/central-download-verification.json) and
[stress](candidate-final/stress-download-verification.json) verification records
bind every downloaded report/profile/inventory member to the GitHub digest.
They contain measurements only, not either huge synthetic data package or a key.
The actual Tests workflow is FAIL because stress failed; normal jobs separately
pass. The [derived capacity](proof-capacity.json), [runtime](proof-runtime.json),
[equivalence/recovery](proof-equivalence.json), [legacy](proof-legacy-recovery.json)
and [normal CI](proof-normal-ci.json) proofs retain those distinct meanings.

The nonoperative [technical declaration](../historical-delivery-release-evidence.json)
is **BLOCKED**, raw-byte SHA-256
`10b16cc6f542f85a4c0d13fe698133e682d508d216c766de3ee9af6fe32463d5`.
Central capacity/recovery, exact v2 equivalence, legacy recovery, both initial
offline budgets and normal CI are PASS. Stress capacity is FAIL; stress recovery
and the complete combined envelope are NOT RUN. In particular, the stress
partial time sum is not promoted to total-envelope PASS. No readiness comment
or actual runtime admission is created by the declaration.

## Requests and prospective time envelope

PASS - [offline frozen-query arithmetic](frozen-request-calculation.json) covers
all 97 queries: 96 bulk batches of 288 sessions, 2,753,568 bulk security-session
rows, and two probe rows. The actual calculation resolves each existing query
with `historical_acquisition.resolved_query` and uses
`ceil(len(symbols) * len(required_sessions) / limit)`, summed by query.
No acquisition object, transport, API probe or model call is used.

| Assumed nonterminal page fill | Calculated requests | Headroom below 400 |
| --- | ---: | ---: |
| 100% | 289 | 111 |
| 75% | 385 | 15 |
| 50% | 575 | -175 (FAIL) |

These are explicit sensitivities, not provider observations or guaranteed
request bounds. Retrying each theoretical minimum page once would require 578
requests and fail the shared cap. The existing rolling-window limiter permits
an initial burst of 20: instantaneous-response lower bounds are 840.014 seconds
for 289 requests and 1,140.019 for 400. Synthetic clock advances are not elapsed
HTTP time. Response latency, partial pages, lower provider quotas, Retry-After,
parsing and filesystem work remain unknown before real execution.

The unchanged live acquisition timer is 1,500 seconds inside its 1,800-second
step. Each complete two-date offline pass has one shared 1,800-second ceiling;
packaging has 600 seconds and the job has 4,500. Prospective accounting reserves
the entire 1,800-second acquisition step, then adds measured setup, initial
reconciliation and packaging, plus an explicit 300-second **assumption** for
the live guard, second checkout, recipient check and upload. It must still fit
4,500 seconds. The accepted old rehearsal measured these latter steps at about
15 seconds, but that smaller run does not measure the changed guard or a larger
upload. The new allowance is not a timing guarantee or a larger job budget.

Handled acquisition failure preserves the original ledger and partial pages.
Offline diagnostics and packaging remain attempted under the existing `always`
conditions. Packaging failure emits no uploadable plaintext fallback. Abrupt VM
loss or a later hard job timeout can still prevent recovery; passing synthetic
caps does not promise a complete or recoverable arbitrary provider response.

## Prospective identity, owner scope and historical limits

PASS — the [versioned compatibility contract](compatibility-contract.md) has
canonical SHA-256
`61ccac3fc27e9a62ccadee73ec0c069536994fedefd76a272aac129fbd7a484d`.
It reuses only old transport run 36570997883 / native 4 / attempt 1 / phase 1,
workflow 369770564, artifact 11033808340, old checkout
`6b12fdfa67355b436fde89287d159bebda2ce9fc` and old workflow
`2687b96d0200903c5d457301e4b3f335fcfb79ce`. New codec/runtime claims require new
source-bound evidence. The current policy binds actual PR97. Complete native
history, exact three zero-job exceptions, `.github`/`tools`/`src` equality,
preserved evidence and a fresh owner release comment created after merge remain
required. Native 5 / attempt 1 / phase 2 has no run ID and is prospective only.

`owner-personal-use-v1` records the owner's personal research scope and seven-day
public ciphertext transport, with `provider_consent=NOT ASSERTED`. It grants no
third-party plaintext access or redistribution finding. The owner-directed
no-outreach/no-further-licensing decision applies; no contact task is pending.
Cost, entitlement, credential, acquisition and technical controls remain.

The canonical manifest
`8d92ed5c56464fe9f342d024da14aa1521f6025d47ec32a6324a298b8fb63ebc` and original
recovery contract
`6b49a4956c8196c432e9798149e2e1544b075a13353351cb10dfe241f72aae7a` are unchanged.
The 400-request, 1 GiB raw, one-inflight, 20/minute-or-lower, one-retry and $0
limits remain. Archive/ciphertext/expanded ceilings remain 199 MiB / 200 MiB /
2 GiB. Owner keys and the accepted private package were not accessed. Installed
design-system 2.13.0 at `14a752dd0269bd6ebbb7080eb0d9e1922cd1ef2c`, the website
and strategy remain unchanged.

Actual real acquisition, stock-level real reconciliation, Guidance plaintext
inspection, new reader approval and trading-edge evidence are NOT RUN.
Original final-price membership completeness and real release remain BLOCKED.

## Reproduction commands and evidence boundaries

The actual representative PR step ran each case once at each materially changed
candidate, with the declared seed and full shape enforced by the entry point:

```sh
python -m pip install --require-hashes --only-binary=:all: -r tools/requirements-historical-archive.txt
python -m pip install -r tools/requirements-historical.txt
python tools/install_historical_age.py --destination "$BENCHMARK_PARENT/age"
python tools/historical_projection_benchmark.py --case "$BENCHMARK_CASE" \
  --workspace "$BENCHMARK_PARENT/synthetic-compaction-$BENCHMARK_CASE" \
  --age "$BENCHMARK_PARENT/age/age" --representative --setup-seconds "$benchmark_setup_seconds"
```

`BENCHMARK_CASE` was exactly `central` or `stress`; this is a provider-free PR
benchmark, not a historical-workflow dispatch or fabricated real guard record.
The benchmark checks absent provider credentials, blocks Python networking,
and supplies only its explicit deterministic transport. Setup installs public
dependencies before that blocked-network computation. Only disposable TEST-ONLY
identities are generated, and they are removed on success/handled failure.

Normal CI actually ran:

```sh
"$RUNNER_TEMP/actionlint/actionlint" -no-color -shellcheck= -pyflakes= .github/workflows/historical-input-proof.yml .github/workflows/tests.yml
pytest tests/ -q
python tools/make_fixture.py --check
git status --porcelain --untracked-files=all
node tools/continuity_check.mjs
node tools/chart_check.mjs
node tools/page_smoke.mjs --shots /tmp/shots
```

The [normal CI receipt](candidate-final-ci/normal-ci-input.json) binds the actual
PR merge checkout `6c40cf7f97dd905617fe7aa796cf63ed3ae52247` to branch head
`00a56f3dd4d8d2b68377364e04ed1f490e8e5c7c` by all 28 runtime source hashes.
PASS: 2,324 pytest tests, one existing warning; semantic validation, 12 current
producer fixtures and clean tree; 127 DOM/store, 378 chart and 9,215 page checks;
secret scanning. This is the individual normal-job result, not a passing whole
Tests workflow or stress-capacity result.

Source verification used binary `git show <head>:<path>` subprocess captures
and `Path.read_bytes()`, not text redirection. Protected files were compared
against `git ls-tree -rz 19f75f3...` by raw Git blob identity and SHA-256.
Complete workflow-history collection read every unfiltered page through an empty
terminator, each exact run and attempt-1 jobs endpoint, and repeated the history
snapshot. [The post-source-push verification](final-history-verification.json)
at `2026-09-30T09:11:42.214397+00:00` binds
[the full capture](final-history-api.json), SHA-256
`c9105ffabf8c048d38df831bf2ef3e470261066d23d10d8243a8a30b988c4dc4`.
It still contains only the three exact zero-job exceptions and accepted run 4.
Runtime admission is NOT RUN; no run 5 was invented.
The complete collection and attempt-job checks were repeated at
`2026-09-30T09:58:43.361764+00:00` with the same result: the
[pre-handoff verification](prehandoff-history-verification.json) binds
[that later capture](prehandoff-history-api.json), SHA-256
`da80449a587d2b3352be9c637624e4ac7dc12b8c088e3ec8b258a4446e211287`.

The [bounded evidence assembler](assemble-evidence.py) is an offline calculation
over these public receipts and pinned source files. It does not query accounts,
dispatch jobs or issue authorization. It checks source hashes and reported size,
index, tar, timing and identity arithmetic. Referenced normal-CI observations
were independently read; accepting their declared shape is not a second CI run.
Raw retained job-log whitespace is intentionally preserved where hashed. The
source/document whitespace check excludes those immutable `.log` observations.

The actual final assembly command was:

```sh
python ../assemble_delivery_evidence.py --repo . \
  --inputs ../delivery-assembly-input.json --output-dir ../delivery-final-proofs
```

It returned a nonzero result with `status=BLOCKED`, the nine explicit check
statuses and the declaration hash above. Exact copies of the script and
[input mapping](assembly-input.json) are retained here. To reproduce it, use
those files with the reviewed repository and a fresh output directory outside
Git; it reads public receipts and does not regenerate any case. Its five proof
files and declaration were copied byte-for-byte. README.md and .env.example were
reviewed for the new format and owner-scope wording; no new credential or
runtime setting was added. The existing CLAUDE/execution checkpoints preserve
earlier evidence and name the same capacity hold.

## 30 September 2026 — superseding explicit envelope decision

The owner authorized a 250 MiB archive / 251 MiB ciphertext envelope while
preserving the selected writer and independent scientific/resource limits.
The [dated continuation review](envelope-continuation/review.md) records complete
central/stress encryption, exact recovery and offline reproduction at the new
source, with actual hosted receipts. This supersedes the capacity hold described
above; it does not rewrite that failure. Real execution remains BLOCKED and
historical acquisition/findings are NOT RUN.
