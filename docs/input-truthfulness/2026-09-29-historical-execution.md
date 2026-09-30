# Historical execution preparation - 2026-09-29

**Superseding repair checkpoint:** the PR #94 workflow failed semantic validation
before any job. Its earlier execution release is suspended by
[Guidance comment 5884205539](https://github.com/spicyChicken59/SpicyStock/pull/94#issuecomment-5884205539).
The repair and current hold are recorded below under **Workflow validation and
history recovery correction**. Prior test results and the original v1 example
remain dated evidence; neither authorizes the corrected v2 execution.

Preparation checkpoint: **local full suite 1,818 tests PASS at `747c0abb665ee43fde8227eea3eec25dd9c573d3`; final normal CI is recorded in PR #94. Dedicated
manual rehearsal, real run, run IDs and attempts: NOT RUN. Alpaca requests: 0;
new provider-response bytes: 0.** No new raw market data has been acquired.
Local synthetic integration exercised the actual acquisition, packaging and
recovery tools with seven invented transport responses; recovered bytes and
both session reconciliation outputs were identical. That establishes local
recovery, not a completed Actions rehearsal or provider-input proof.

Implementation PR: [#94](https://github.com/spicyChicken59/SpicyStock/pull/94).
The policy binds this PR; execution still requires its merge and separate dated
readiness evidence. The reviewed starting commit is `56b34a8bc7a8980559cad56be488e8a29489e4fd`, tree
`12794f02d0c291ff68ccbfdfde327d9551f5dbd1`. Automatic publication
`786ade7013a0c55d172d89118322b19a056fa8a6` subsequently advanced main and was
merged without conflicts as `747c0abb665ee43fde8227eea3eec25dd9c573d3`.
The PR records its final head independently. The final transport-permission
change passed 63 focused guard tests; the suite now collects 1,820 tests.
The earlier full run had zero skips and one existing websockets deprecation
warning. Two stale assertions (workflow inventory and status spelling) and the
collection count were corrected before that passing full run. The assignment remains
`spicystock-historical-input-2026-09-28`; its frozen manifest's canonical SHA-256
is `8d92ed5c56464fe9f342d024da14aa1521f6025d47ec32a6324a298b8fb63ebc`.

The dedicated `.github/workflows/historical-input-proof.yml` accepts only
`mode` and numeric `readiness_comment_id`. It uses public repository
`spicyChicken59/SpicyStock` (ID `1352997802`), `main`, one `execution` job,
read-only GitHub permissions, standard `ubuntu-24.04`, Python 3.12.14, and
assignment-wide concurrency without cancellation. Immutable action pins are:

| Action | Version | Commit |
| --- | --- | --- |
| checkout | v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| setup-python | v7.0.0 | `5fda3b95a4ea91299a34e894583c3862153e4b97` |
| upload-artifact | v7.0.1 | `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` |

The installer pins official [age v1.3.2](https://github.com/FiloSottile/age/releases/tag/v1.3.2),
source `b74dce4cdbe35b5e5f66c06d9612b72f89028758`, with release-asset SHA-256:
Linux `cbe24006683f8eb669266162894b9a522a1af52f2665fbc63a4bb032ed26ac10`;
Windows `f48d8f8f9ebe903ab5027ed067652f2cc1db94bc206976430133b905dcd8e8c7`.
The fixed release digests are verified before the two executables are extracted.
No system installation or signature-attestation claim is made.

The guard checks the owner-authored readiness comment on this implementation
PR, merged reviewed head, merge ancestry, unchanged `tools`/`src` trees and
workflow bytes. It checks complete native workflow history and the current
started job before returning the reviewed checkout SHA. Only run number 1,
attempt 1, may rehearse; only number 2, attempt 1, may acquire. A rerun, deleted
history, unexpected dispatch or unsuccessful predecessor cannot reopen a slot.
The owner `spicyChicken59` supplies conceptual Guidance authorization through a
structured attestation; the guard does not independently adjudicate licences.

Provider secrets appear only in the real acquisition step, after scope, storage,
approval and recipient preflight. Limits remain **400 actual HTTP requests,
1 GiB uncompressed response bodies, one inflight request, at most 20/minute,
one retry, and $0 additional spend**. SQLite reservations precede HTTP; interruption
preserves the original ledger. Offline reconciliation blocks sockets. Packaging
allows only closed evidence, encrypts before upload, and projects a public
receipt without raw values or private approval contents. Seven-day transport
retention, a 200 MiB ciphertext ceiling and 2 GiB expanded-package ceiling can
block delivery even when acquisition stayed within its separate raw-byte cap.

The owner custodian generated a dedicated key without overwriting an existing
identity, outside Git on fixed NTFS storage:
`C:/Users/motah/Documents/Codex/private/SpicyStock/historical-input-2026-09-28`.
Its protected ACL permits the owner only. This is local custody, not a shared
Guidance attachment route. Public recipient:
`age1n3xsz54659mz50vml7pg0eqdhq6dtxqmzy0janmq7qgxrhc6gceqmp75vh`.
SHA-256 of its ASCII bytes **plus one LF**:
`0f539a14ca5bf12a1ad3a706747316bc886d375b17e757af32c237aa39b8ec4f`.
The private identity never enters Git, Actions or public artifacts. A local
owner-key recovery check passed at `2026-09-29T04:06:18Z`; recovered synthetic
SHA-256 `13996f8da031ae0141fcb4239489de7049f5be5211450242a97bad831d2fb98e`.
Only `T4HIR\motah` appeared in the verified file access entries.

Read-only account inspection on September 28–29 found GitHub Free, an existing
Actions $0 budget with **Stop usage: Yes**, and current artifact billing of $0;
no settings changed. [Standard public runners are free](https://docs.github.com/en/actions/concepts/billing-and-usage),
and [stop-enabled budgets can block additional metered usage](https://docs.github.com/en/billing/concepts/budgets-and-alerts).
These support a prospective $0 basis, conditional on the applicable budget
remaining effective; they do not guarantee storage availability or delivery.
Recheck before each dispatch. Private account quantities are omitted.

[Alpaca's FAQ](https://docs.alpaca.markets/us/docs/market-data-faq) documents historical
SIP without a subscription when `end` is at least 15 minutes old. The requested
dates qualify. After the owner's secure sign-in, read-only inspection on
September 29 confirmed **Paper Trading / Basic / Current Plan**. The documentary
$0 entitlement basis is PASS; actual secret usability and the probe are NOT RUN.
No account setting, subscription or agreement was changed.

The current [Alpaca Terms and Conditions](https://files.alpaca.markets/disclosures/library/TermsAndConditions.pdf)
(undated public PDF, inspected September 29; personal-use section p. 1 and
content section p. 2) provide a personal, noncommercial-use basis. Their transfer
restriction is purpose-qualified; it does not clearly prohibit owner-only
private computation or retention. We did not establish that the separate
brokerage Customer Agreement governs this Paper account. **BLOCKED** is limited
to the unresolved permission for the proposed public ciphertext transport and
any separate reviewer's raw-data access. The precise missing evidence is a
reviewed applicable permission basis for that transfer; encryption supplies no
licence. Guidance review can remain **NOT RUN** independently if no approved
private handoff exists, as the request allows. A readiness attestation must
explicitly establish encrypted transport as well as private retention.

After Guidance review and merge, a separate owner readiness comment is required
for each phase. Dispatch first with `mode=rehearsal` and
`readiness_comment_id=<owner JSON comment ID>`. Verify GitHub run/artifact identity,
download the exact ciphertext artifact through the connected GitHub
`download_workflow_artifact` route (authenticated browser download is the
operator fallback), recover locally, and compare both offline outputs before
considering `mode=real`. This actual download route is NOT RUN until the
post-merge rehearsal. Its output is encrypted transport, not private shared
storage. Measure expanded/compressed rehearsal sizes and review the full-window
size estimate against both package ceilings before releasing the real slot.
The post-upload job summary binds the artifact ID and GitHub ZIP digest to the
inner ciphertext receipt; recovery must cross-check those against the Actions
API, not trust the downloaded receipt by itself. The comment body must be the entire JSON object,
without a Markdown fence. This example is intentionally **not dispatch-ready**:

```json
{
  "schema": "readiness-v1",
  "status": "BLOCKED",
  "mode": "real",
  "assignment_id": "spicystock-historical-input-2026-09-28",
  "manifest_sha256": "8d92ed5c56464fe9f342d024da14aa1521f6025d47ec32a6324a298b8fb63ebc",
  "checkout_sha": "REVIEWED_PR_HEAD_REQUIRED",
  "workflow_id": 0,
  "recipient_sha256": "0f539a14ca5bf12a1ad3a706747316bc886d375b17e757af32c237aa39b8ec4f",
  "evidence": {
    "cost": {"verified_at": null, "basis": "PENDING", "reference": "PENDING", "zero_additional_cost": false},
    "rights": {"verified_at": null, "basis": "PENDING", "reference": "PENDING", "private_retention_permitted": false, "encrypted_transport_permitted": false, "controlled_review_status": "NOT RUN"},
    "entitlement": {"verified_at": null, "basis": "PENDING", "reference": "PENDING", "historical_sip_zero_cost": false},
    "local_recovery": {"verified_at": null, "reference": "PENDING", "verified": false, "rehearsal_run_id": 0, "ciphertext_sha256": "PENDING", "recovered_plaintext_sha256": "PENDING", "recipient_sha256": "0f539a14ca5bf12a1ad3a706747316bc886d375b17e757af32c237aa39b8ec4f"}
  }
}
```

Use dated `YYYY-MM-DD` evidence and concrete HTTPS references or
`sha256:<64 hex characters>` private receipt identities. Retain private contracts
privately; publish their hashes and a nonsensitive permission basis only.
Rehearsal requires cost evidence; real execution additionally requires rights,
entitlement and the matching successful rehearsal's local recovery receipt.

**KEEP.** Preserve the original manifest, historical evidence, normalizer,
acquisition accounting and all production behaviour. Preserve the distinction
between original inputs, later historical retrieval and synthetic transport.
The protected private key remains under the owner's custody, with its public
recipient and exact LF fingerprint available for review. Keep the native
workflow records, SQLite ledger and failed-run evidence: each supports a
different part of execution identity or spending limits. Keep private Guidance
recovery at NOT RUN until an actual approved route exists; successful local
decryption does not demonstrate another reviewer's access.

**FIX NOW.** Review final normal CI and the dedicated workflow/helper boundary
together. The local full suite passed 1,818 tests with zero skips; the final
transport-permission guard has its own focused verification. Secure sign-in
is complete and Basic entitlement is documented. Resolve only the applicable
permission for public encrypted transfer; record any separately permitted
reviewer access without treating free endpoint access as that permission.
Before either dispatch, recheck the
existing GitHub cost control and publish a complete owner readiness attestation.
Before the real slot, recover the actual rehearsal artifact, verify its identity
against GitHub and reproduce both reconciliation outputs from the recovered
ledger and cache without network access.

**DEFER.** Actual manual execution remains deferred until Guidance review,
merge and the corresponding readiness conditions pass. Account permission
uncertainty blocks real acquisition even if local encryption and tests pass.
Any later retrieval must retain its actual retrieval time, explicit query
identity and missing observations; it cannot become original publication-time
evidence retroactively. Defer complete original membership proof, source-policy
adjudication, new reader decisions and trading-edge conclusions to the evidence
they require. An acquisition or package blocked by a ceiling remains a blocked
result; it does not authorize another run, ledger reset or enlarged allowance.

**OMIT.** Omit raw OHLCV, credentials, private identities, accepted-contract
contents and private account billing details from public logs and artifacts.
Omit paid subscriptions, changed settings, support outreach, alternative data
providers, production patches and UI changes. Omit a fabricated PASS, private
handoff, complete dataset, original-input reconstruction or profitability claim.
This checkpoint prepares one reviewable implementation and stops before merge
or dispatch; it does not claim that the historical investigation is complete.

## Workflow validation and history recovery correction

Baseline main/repair base: `33ec181ca60adaf2f7c0ef19a1889a5517161585`,
tree `6127e63213836f72caf708cb5b4294d750fe6147`. PR #94 reviewed checkout
`eb2b417a7a2289ab22c239ccfe06c20daf1dde7b` remains historical evidence; it
cannot certify the changed execution code. Repair [PR #95](https://github.com/spicyChicken59/SpicyStock/pull/95)
was created with initial head `b00c6593498de62c282af275e2e7e2ac4b413e54`;
only then was its actual number bound in the policy. The PR records the final
submitted head and required checks. It remains unmerged and execution is BLOCKED.
No manual dispatch, rerun, readiness PASS, provider probe or key operation is
part of this correction.

FAIL - GitHub rejected both `runner.temp` expressions in job-level env. The
[original finding](https://github.com/spicyChicken59/SpicyStock/pull/94#issuecomment-5884069064)
preserves the annotations. The official [context table](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#context-availability)
excludes runner at job env. The corrected early Bash step assigns and exports
private paths from RUNNER_TEMP for its own process and writes GITHUB_ENV for
later steps. Scratch stays outside the checkout and is unique to run/attempt;
provider secrets remain confined to the real acquisition step.

PASS - complete unfiltered history was reread at `2026-09-29T11:47:47.5184123Z`:
exactly three records, individually verified with attempt-1 jobs count zero.
The [captured metadata](2026-09-29-workflow-repair-evidence/bootstrap-history.json)
identifies the saved API JSON hashes, source URLs and date. Each event is push,
attempt 1, completed/failure, repository 1352997802, workflow 369770564, original
workflow path. Their exact identities remain:

| Run ID | Native number | Branch | Head |
| --- | --- | --- | --- |
| 36520481662 | 1 | ops/historical-proof-execution | 21e405fa0601bdd476bad2e8027abcae5e6fac15 |
| 36521323183 | 2 | ops/historical-proof-execution | eb2b417a7a2289ab22c239ccfe06c20daf1dde7b |
| 36524147152 | 3 | main | 33ec181ca60adaf2f7c0ef19a1889a5517161585 |

The immutable `historical-workflow-recovery-v1` contract is canonical SHA-256
`6b49a4956c8196c432e9798149e2e1544b075a13353351cb10dfe241f72aae7a`.
It exempts only those exact pre-job failures after authoritative revalidation.
Every other record must be a permitted manual phase; a fourth bootstrap failure,
missing/altered record, inaccessible jobs or incomplete pagination blocks access.
Complete history is read again after individual run/job validation to reject a
changing snapshot. Native number 4 would be phase 1 (rehearsal), and native 5
would be phase 2 (real), only if no intervening record exists. A failed/cancelled
manual attempt consumes its phase. No deletion, offset-only inference, new
workflow identity, rerun or fresh ledger can reopen it.

Policy/readiness/execution are v2. The actual repair PR must be merged, with
its reviewed head bound in the owner readiness comment and checkout. The guard
also verifies PR #94 ancestry, unchanged tools/src trees and workflow bytes.
Readiness binds `run_number`, `assignment_phase`, and `recovery_contract_sha256`.
Real readiness additionally requires `historical-local-recovery-v2`, binding the
successful rehearsal's actual run ID, native 4, attempt 1, phase 1, checkout and
workflow SHAs, matching contract, recipient and recovered evidence hashes.
These are format requirements, not current permission or a readiness attestation.

The wrapper, encrypted receipts and private package index preserve this v2
identity without relabelling native runs. Offline replay compares the supplied
guard against the retained diagnostics and recovered package identity before
writing, and requires the original ledger. Old v1 evidence is retained in Git
under its original meaning; it is not silently promoted to v2 authority.

PASS - official actionlint v1.7.12 reproduces both original context errors in
an external untouched copy before edits. Its source revision is
`914e7df21a07ef503a81201c76d2b11c789d3fca`. Normal CI installs verified release
assets and checks both changed workflows with expression/context validation
unsuppressed. Independent restored-expression controls for HISTORICAL_ROOT and
MPLCONFIGDIR fail, while the valid step-context control passes. Broken controls
stay outside `.github/workflows`. Exact final test counts, diagnostics and
post-push GitHub validation observations are recorded in the repair PR and
its repair evidence directory. Semantic validity does not establish manual
execution or recoverable Actions delivery.

KEEP the unchanged frozen manifest, original acquisition-execution.json, owner
key/recipient, historical records, design-system 2.13.0 and all production
behavior. Request/raw/rate/retry and ciphertext/expanded-package limits remain
unchanged. FIX NOW only workflow validity and this explicit history recovery;
Guidance must independently review and merge the single repair PR. DEFER manual
rehearsal until a new Guidance release after current history/revision/readiness
checks; real execution also retains its separate transfer-permission blocker.
OMIT dispatch, rerun, fresh budget, new key, provider outreach, UI/strategy changes
and market conclusions. Actual manual run/attempt, historical acquisition,
private real evidence recovery and independent real-data reconciliation are
NOT RUN: zero actual Alpaca requests, zero new response bytes, $0 additional
acquisition spend. Original membership completeness remains BLOCKED; new reader
eligibility and trading-edge validation remain NOT RUN. This repair releases
no real-mode execution.

Final local repair verification: **PASS - 1,951 tests, zero failures/errors/skips**
on Python 3.12.14 with verified age and actionlint; one existing websockets
warning. Command: `python -m pytest tests/ -q --tb=short
--basetemp=../repair-pytest-final --junitxml=../repair-final.xml` with
`PYTHONUTF8=1`, `MPLBACKEND=Agg`, external `MPLCONFIGDIR`, verified `AGE_BINARY`
and `ACTIONLINT_BINARY`, and the existing Windows resource telemetry adapter.
The earlier full attempt had one stale current-suite-count assertion; that
count was corrected without rewriting dated historical counts, and the complete
suite was rerun. PASS - 9,756 protected existing Git blobs remain identical.
[Local source/hash verification](2026-09-29-workflow-repair-evidence/local-verification.json)
and [protected scope](2026-09-29-workflow-repair-evidence/protected-scope.json)
record the exact checks. The corrected first push produced no additional
historical-workflow record at `2026-09-29T12:05:40.7803968Z`; count remained three.
The final PR head's normal GitHub CI and fresh complete-history check will be
reported in PR #95 before requesting Guidance review; no dispatch is released.

## Lossless conversion-evidence compaction - 30 Sep 2026

This dated addendum follows [Guidance instruction 5903186288](https://github.com/spicyChicken59/SpicyStock/pull/95#issuecomment-5903186288)
on the [capacity finding 5902648870](https://github.com/spicyChicken59/SpicyStock/pull/95#issuecomment-5902648870).
The implementation base is `6284cb9787c11929eaedf1a263cf463ab4ae4928`.
The one compaction PR records its actual submitted head, required CI and review;
this document does not provide an executable readiness attestation.

[The newer owner direction, comment 5903266884](https://github.com/spicyChicken59/SpicyStock/pull/95#issuecomment-5903266884),
records personal use and ends further licensing investigation and all Alpaca
outreach. The earlier unsent clarification is historical material, not pending
work; do not request authorization for it again. This decision does not establish
provider consent or an agreement interpretation. Guidance's next release review
addresses engineering readiness, exact execution binding and any explicit,
accurately labelled adjustment to obsolete project-imposed attestations. This
compaction does not silently change the guard or claim those attestations passed.

The earlier NOT RUN statements above describe their original checkpoints.
They are superseded for the **old** hosted rehearsal and owner replay by
[rehearsal report 5890923069](https://github.com/spicyChicken59/SpicyStock/pull/95#issuecomment-5890923069),
[exact LF replay 5894734715](https://github.com/spicyChicken59/SpicyStock/pull/95#issuecomment-5894734715)
and [Guidance acceptance 5894791957](https://github.com/spicyChicken59/SpicyStock/pull/95#issuecomment-5894791957).
Run `36570997883`, native 4 / attempt 1 / phase 1, artifact `11033808340`,
used execution checkout `6b12fdfa67355b436fde89287d159bebda2ce9fc`, tree
`d4ac339901ebe99039b912f30397d43d5d76efbb`, and workflow revision
`2687b96d0200903c5d457301e4b3f335fcfb79ce`. The initial CRLF comparison remains
dated FAIL evidence. Guidance accepted the operator-reported private replay;
Guidance plaintext inspection remains NOT RUN. None of that work was repeated.

PASS - the actual untouched adapter was reproduced on fresh invented decimal
inputs before changing it. Its per-field dictionaries repeat symbol, session
and decimal strings already retained in normalized rows. The
[baseline receipt](2026-09-30-projection-compaction-evidence/untouched-adapter.json)
and exact extracted legacy function fixtures preserve that source contract.
The old capacity numbers remain estimates, not provider observations.

PASS - `historical-reconciliation-v2` now selects
`historical-float64-projection-v2`. One selected-row ordinal, fixed OHLCV mask
and complete binary-hex values replace the expanded dictionaries. Query and
complete-normalization hashes bind each entry to its basis, security, target,
decimal strings and selected/discarded raw lineage. Zero-mask rows are explicit.
The [schema contract](2026-09-30-projection-compaction-evidence/contract.md)
describes the bounded decoder, which validates the whole projection before
yielding legacy facts in their original deterministic order. It retrieves
decimal strings directly from retained normalized rows; raw pages remain the
authority for original JSON spellings. No expanded legacy list is constructed
on the new normal path. Actual DataFrames, float conversion, decimal audit,
population masks, predicates, unknown states and decisions are unchanged.

PASS - fresh small full reconciliations reproduce the untouched v1 bytes under
the explicit legacy selector. New v2 outputs reconstruct every old conversion
fact, preserve every other field, and reproduce their complete bytes on repeat
with identical source and dependencies. Tests cover all 32 masks, integers,
exact fractions, cents, longer decimals, fractional and signed-zero volume,
exponents/trailing zeros, multiple queries/securities, selected replacements,
same/cross-page duplicates, missing/invalid rows and partial histories. Broken
references, query/basis bindings, masks, values and schemas are rejected.
Independent exact Fraction/Decimal comparisons against adjacent binary floats
check representative conversion values without using the new decoder as oracle.

PASS - [normal-collected controls](2026-09-30-projection-compaction-evidence/representation-controls.json)
show the actual old adapter failing the compact-output regression, the fixed
implementation passing, and five isolated restored defects failing their named
tests while unrelated controls pass. Only child-process function objects change.
An initial unpublished log receipt hashed pre-write text rather than saved
Windows bytes; that evidence defect remains documented in
[log-hash-correction.json](2026-09-30-projection-compaction-evidence/log-hash-correction.json).
The corrected harness hashes saved bytes, and all seven control logs were
recaptured during the normal full suite. Their committed bytes must match those
hashes; no failure was erased or relabelled.

PASS - the complete local suite passed **2,104 tests**, zero failures/errors/skips,
in 553.49 seconds on existing Python 3.12.14, pandas 2.2.3, NumPy 2.3.5 and
exchange-calendars 4.13.2. One existing websockets warning remains. The
[local verification receipt](2026-09-30-projection-compaction-evidence/local-verification.json)
records commands, environment and saved log/JUnit hashes. Existing cache-resume,
raw-row lineage, request/byte/rate/retry, interruption, encryption, truncation,
hash, plaintext-rejection and lifetime-accounting tests remain in that suite.
The later benchmark reporting-only portability correction has focused checks;
the final submitted head's normal Linux CI is recorded in the PR.

FAIL - local `python tools/make_fixture.py --check` reports 24 stale provenance
gzip objects. A bounded read-only comparison of those existing public fixtures
found only the gzip OS header byte: committed Linux `03`, local Windows `0a`.
Lengths, DEFLATE payloads, trailers and typed-json-f64hex-v1 identities agree.
The [platform evidence](2026-09-30-projection-compaction-evidence/fixture-platform-evidence.json)
records all 24 comparisons and actual Python/zlib behavior. No fixture, browser
gate or checker changed. Normal Linux CI must establish its own result; this
local failure is retained. FixtureClaude errors in the log are intentional
synthetic doubles, not model calls.

The [full-shape benchmark](2026-09-30-projection-compaction-evidence/benchmark.md)
records measured central and longer-decimal stress outcomes, all original member
identities, archive/index overhead, gzip/ciphertext limits, memory, scratch and
runtime. Each case uses the frozen 96 canonical batches, all 288 required
sessions and the two probe rows through the actual acquisition, reconciliation
and packaging code. Fresh deterministic synthetic responses and disposable
TEST-ONLY age identities are used; actual provider requests are zero. No owner
package or owner key was opened. These measurements cannot establish unseen
provider entropy, market correctness or hosted performance.

| Measured bytes / check | Central | Longer-decimal five-field stress |
| --- | ---: | ---: |
| Expanded package, cap 2,147,483,648 | 1,546,827,051 PASS | 1,866,624,285 PASS |
| Gzip archive, cap 208,666,624 | 203,495,174 PASS | 423,811,147 FAIL |
| Ciphertext, cap 209,715,200 | 203,545,054 PASS | NOT RUN |
| Original-member recovery | 390 exact members PASS | NOT RUN |
| Preserved inputs after refusal | NOT RUN (recovery completed) | 390 exact members PASS |
| Combined local reconciliation, 1,800-second step | 3,416.050264 seconds FAIL | 3,489.988850 seconds FAIL |

Central gzip has only 5,171,450 bytes of headroom; ciphertext has 6,170,146.
Stress gzip exceeds its ceiling by 215,144,523 bytes. The unchanged packager
refuses before encryption, so successful expanded-size checks do not establish
recoverable delivery. Post-refusal input preservation is not package recovery.
Both full cases ran once. Neither was trimmed, nested-compressed, repeated or
admitted under a raised limit. The local timings include instrumentation and
cannot predict hosted Linux speed; hosted full-shape performance is NOT RUN.
The benchmark's simulated rate clock avoids wall-clock network pacing, so its
overall duration is not a claim of fitting the workflow's 75-minute deadline.

The representation correction is lossless, but capacity is not closed. The
smallest next decision is Guidance review of this bounded PR and, if justified,
separate authorization for a lossless archive-encoding correction under the
unchanged caps and deadlines. Current gzip already uses its default level 9;
this is not a recommendation to turn up its compression level. No further
optimization, acquisition or hosted rehearsal is part of this handoff.

BLOCKED - changed tools cannot borrow PR #95's approval or relabel accepted run
36570997883. The workflow, policy, guard, wrapper, package code and original
recovery contract are unchanged. [Binding regressions](2026-09-30-projection-compaction-evidence/binding-controls.json)
retain the reviewed-head, source-equality and exact-recovery checks. The
[prospective compatibility proposal](2026-09-30-projection-compaction-evidence/compatibility-proposal.md)
identifies the smallest review decision: one exact new PR/head, one declared
representation change and its offline proof related to only the exact accepted
transport run/checkout/manifest/recipient. It implements no compatibility bridge,
source-equality bypass, new phase or readiness approval. Guidance must decide
that relation independently; merge alone does not release real mode.

Real acquisition, real-data reconciliation, new hosted historical execution, reviewer
plaintext inspection, new reader approval and trading-edge validation are
NOT RUN. Real release and original final-price membership completeness remain
BLOCKED. The later personal-use/no-outreach direction supersedes the earlier
assignment to pursue contractual clarification; no outreach was sent. Frozen
manifest `8d92ed5c56464fe9f342d024da14aa1521f6025d47ec32a6324a298b8fb63ebc`,
recovery contract `6b49a4956c8196c432e9798149e2e1544b075a13353351cb10dfe241f72aae7a`,
owner key/recipient, accepted evidence and original limits remain unchanged.
README.md and .env.example were reviewed and their historical-execution prose
updated without adding settings. Website/strategy behavior and installed
design-system 2.13.0 at `14a752dd0269bd6ebbb7080eb0d9e1922cd1ef2c` are preserved.

PASS - [protected-scope.json](2026-09-30-projection-compaction-evidence/protected-scope.json)
records a raw-byte check of **10,541 existing Git blobs**, with no changed
protected path. Only README.md, .env.example, CLAUDE.md, this existing handoff and
the two representation modules are permitted existing-file edits. The final PR
records staged-byte identity, exact base/head and all added support-file blobs.

## Delivery readiness checkpoint - 30 Sep 2026, PR #97

This continuation follows Guidance review 5362976589 and comment 5906480203.
The measured runtime candidate is `00a56f3dd4d8d2b68377364e04ed1f490e8e5c7c`,
tree `16c8241fe63eab575471fdc2e52254718f6ed685`, based on merged PR #96 at
`19f75f3b7ad566fb98e8e8e28fd2482a3737e9bc`. Later documentation commits do not
constitute another runtime measurement. Earlier failures retain their original
dated meaning. The [technical review](2026-09-30-delivery-readiness-evidence/delivery-review.md) links the source-bound receipts.

PASS - normal CI on actual PR merge checkout
`6c40cf7f97dd905617fe7aa796cf63ed3ae52247` passed 2,324 pytest tests, semantic
workflow validation, 12 producer fixtures and the clean-tree check. Browser
checks passed 127 DOM/store, 378 chart and 9,215 page checks; secret scanning
passed. All 28 runtime source hashes match the branch and tested merge checkout.
These individual normal jobs do not establish a passing whole Tests workflow.

The scientific implementation is unchanged. Each full synthetic case uses 96
bulk queries, all 288 sessions, 2,753,568 bulk observations and two probe
observations. Final central is PASS: archive 99,741,871 bytes, ciphertext
99,766,407 and expanded content 1,546,827,473 all fit their unchanged caps.
All 390 original members retain identical bytes, lengths and hashes; ledger
accounting is unchanged and both complete v2 reconciliation files reproduce
exactly after recovery. The initial and recovered two-date calculations took
1,377.739460 and 1,390.110803 seconds respectively, each within its own shared
1,800-second budget. Packaging took 37.288482 seconds.

Final stress reproduced all 388 original raw-page, query-manifest and full v2
reconciliation identities. Its initial calculation took 1,396.736550 seconds,
within the shared limit. The complete archive is FAIL: 215,909,287 bytes against
208,666,624, exceeding the cap by 7,242,663 bytes. Expanded content fits 2 GiB.
The package phase took 62.202810 seconds before refusing the oversized archive.
Encryption, recovery and a separate all-390-member post-refusal sweep are NOT
RUN. Initial calculation success and unused time do not establish delivery.

Versioned v3 binding relates only accepted transport run 36570997883, native
4 / attempt 1 / phase 1, to separately reviewed new code. The original recovery
contract, complete history and source-equality checks remain. No replacement
rehearsal or extra allowance exists. Legacy gzip v2 recovery preserves its
original metadata. Owner personal-use authorization is not provider consent;
the no-outreach direction remains in force. Technical evidence and a later
dated execution release are separate.

KEEP - the 199 MiB archive, 200 MiB ciphertext, 2 GiB expanded and original
request/raw-byte ceilings, deadlines, owner key/recipient, website, strategy and
design-system 2.13.0. FIX NOW - Guidance reviews this measured engineering result
and the single proposed next decision: separately authorize one level-12,
2 GiB-window comparison on verified synthetic stress inputs, bounded by 600
seconds and a declared 12 GiB process-memory ceiling. Keep the evidence caps;
no fit is promised and this checkpoint does not authorize the comparison.

DEFER - real release remains BLOCKED pending capacity closure and a fresh dated
execution release. Real acquisition, Guidance plaintext inspection, new reader
eligibility and trading-edge validation are NOT RUN; original final-price
membership completeness remains BLOCKED. OMIT - repeated rehearsal, owner-package
inspection, provider/model calls, licensing outreach, broader tuning and raised
caps or deadlines. Guidance owns independent review and merge; merge alone does
not release historical execution.

## PR97 bounded correction checkpoint — 30 Sep 2026


FAIL — the single Guidance-authorized level-12 / 2 GiB-window comparison has
finished and triggers stop condition A. The complete archive is 215,854,671
bytes against the unchanged 208,666,624-byte cap, exceeding it by 7,188,047.
Expanded content is PASS at 1,866,624,285 bytes. No second comparison, codec
adoption, encryption, full-case replay or hosted historical run follows this
failure. See the [dated correction review](2026-09-30-delivery-readiness-evidence/bounded-correction/review.md)
and exact receipts; earlier accepted and failed evidence is preserved.

The repository base remains `19f75f3b7ad566fb98e8e8e28fd2482a3737e9bc` and the
reviewed starting head is `bd779c2a1ce14b8a7361c4866678e55e29ae18f8`. The final
submitted head and actual exact-head Tests/Secret Scan results are recorded in
the subsequent PR97 closeout comment, not invented in this pre-push checkpoint.
The accepted Linux measurement remains `00a56f3dd4d8d2b68377364e04ed1f490e8e5c7c`.

PASS — all 390 original synthetic source members were hash-checked during
streaming, without regenerated observations or changed scientific outputs.
The comparison retained the original public fictional PR96 metadata; it is not
a new execution receipt. Supervised wall time was 191.094 seconds, compression
CPU 180.734375 seconds and native job CPU 181.265625 seconds. Peak Python RSS was
2,205,577,216 bytes; peak aggregate job committed memory was 2,201,931,776.
Hard 12 GiB process/job committed-memory limits and a 600-second watchdog were
verified before execution. The output footprint sampled 215,873,410 bytes;
including retained input lengths gives 2,082,220,259 logical bytes. Ciphertext
size, stress encryption and stress recovery are NOT RUN because capacity failed.

PASS — the narrow scanner correction allows only the two independently verified
public-response hashes at the exact original receipt path. Actual gitleaks
8.24.3 controls retain detection of unrelated values, other paths and another
default detector. Normal final-head hosted CI is a separate required observation.
A receipt-bound PR97-only NOT RUN deferral prevents automatic repetition of the
accepted full benchmark after this stop; it does not certify changed source or
skip normal Python/browser/Secret Scan checks. README and .env.example remain
accurate without modification.

KEEP — the accepted central recovery, legacy gzip reader, lossless v2 outputs,
native-4 transport identity, original limits, owner-personal-use wording,
website/strategy and design-system 2.13.0. FIX NOW — hand this measured failure
and the scanner disposition to Guidance for independent review. DEFER — the
next delivery decision and any prospective source-bound execution review remain
BLOCKED; the unchanged technical declaration is BLOCKED. OMIT — more codec
tuning, a second rehearsal, owner-key/private-package access, provider/model
calls, outreach and actual historical acquisition. No market-data correctness,
new reader authority or trading edge is established. Guidance owns any next
instruction, clean merge and later real release; Astra stops at PR97.


FAIL — subsequent full commit-range scan at
`629ed4433daa6ff60a636cd56490cabb52a371f8` resolved the two original findings
but detected four additional public binary/source fingerprints in the newly
retained evidence. Astra introduced these while recording this correction.
The exact paths and content-hash verification are retained in the correction
review. No additional allowlist, detector exclusion or history rewrite was
made. These findings remain a separate Secret Scan blocker; the capacity
failure already requires the stop. Final hosted results belong to the PR97
closeout comment.
