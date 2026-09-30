# Prospective delivery compatibility v1

This is an implementation contract under the #96 continuation, not a dated
execution release, readiness approval or proof that the historical study ran.
The original recovery contract and old receipts remain unchanged.

`tools/historical-delivery-compatibility.json` binds only the accepted PR95
transport: run 36570997883, native 4, attempt 1, phase 1, workflow 369770564,
artifact 11033808340, execution checkout
`6b12fdfa67355b436fde89287d159bebda2ce9fc` and workflow revision
`2687b96d0200903c5d457301e4b3f335fcfb79ce`. It also pins the accepted job,
readiness, ciphertext, recovered archive and recovery-checkpoint identities,
canonical manifest, recipient fingerprint and original recovery-contract digest.
That evidence describes the old transport only. It does not validate the new
codec, runtime or checkout.

The current policy, readiness and execution records use v3. The policy's new PR
number is initially unbound and must be the actual newly opened PR, never 94,
95 or 96. A prospective real release remains native 5 / attempt 1 / phase 2.
Complete history must contain all three exact zero-job exceptions, the exact
accepted successful rehearsal and the durable current real job. Pagination,
double snapshots and job checks remain. Nothing starts a replacement rehearsal,
resets a phase or creates another allowance.

## Source and technical evidence

A later owner-authored `readiness-v3` comment must be dated with `authorized_on`,
name the exact reviewed PR head, and bind the new compatibility digest and the
raw-byte SHA-256 of
`docs/input-truthfulness/historical-delivery-release-evidence.json`. The guard
requires that PR to be merged. The new reviewed head's tools/src/.github trees and
workflow bytes must still equal current main; compatibility never bypasses
those checks or rewrites the old execution identity.

The release-evidence file is declarative measured evidence, separate from that
dated authorization. Its schema is `historical-delivery-release-evidence-v1`.
It binds the compatibility, manifest and recipient identities, exact source
hashes for the contract's complete `required_source_paths`, and the sorted
changed-code paths/Git blobs from the continuation base to the reviewed head.
Only enumerated runtime paths and the stated tests/documentation scope are
admitted. Incomplete/truncated differences fail closed. The final allowlist adds
the archive-codec helper and archive dependency lock; normalization,
reconciliation and the independent breadth reference remain hash-bound required
sources but are excluded from permitted changes. Documentation changes are
limited to the existing 2026-09-29 execution report, the new delivery-readiness
evidence directory and the fixed release-evidence JSON. Changing or deleting
earlier evidence is refused.

The file must carry these exact checks as `PASS`: `central_capacity`,
`stress_capacity`, `central_exact_recovery`, `stress_exact_recovery`,
`legacy_gzip_recovery`, `exact_v2_equivalence`, `shared_offline_step`,
`total_job_envelope` and `normal_ci`. Its `proofs` map contains `capacity`,
`runtime`, `equivalence`, `legacy_recovery` and `normal_ci`; each names a public
JSON proof under `docs/input-truthfulness/` and its exact SHA-256. The guard
reads those files from the reviewed checkout, checks their hashes and requires
their declared status to be `PASS`. A missing, changed, false, `FAIL`,
`BLOCKED` or `NOT RUN` technical result cannot release execution. These are
reviewed evidence bindings, not a benchmark performed by the guard.

There is no source-head circularity: source/proof files do not contain their own
commit hash. A later dated comment binds the final head and exact evidence-file
hash after both exist. Normal CI may be cited from the verified code freeze with
exact source pins; documentation-only follow-up CI is reported separately.
The readiness comment must itself be created at or after the PR's authoritative
merge timestamp, and `authorized_on` must equal that creation's UTC date. Editing
an earlier PR comment into a release cannot satisfy this separate-release check.

## Owner scope and legacy records

`owner-personal-use-v1` replaces the obsolete project-created provider-rights
booleans. The owner attests personal research, private runner/owner-local
plaintext, owner-only decryption, no public plaintext, and seven-day public
ciphertext retention under the recorded owner direction. `provider_consent`
must say `NOT ASSERTED`; Guidance private review remains `NOT RUN`. This is
owner scope/authorization and never a provider licence finding. No licensing
investigation or outreach is pending. Cost, entitlement, credentials, frozen
inputs, shared budgets and acquisition deadlines retain their controls.

The legacy acquisition adapter still calls a text field `retention_rights_basis`.
The v3 guard fills it explicitly with owner authorization and `provider consent
NOT ASSERTED`, not fictitious permission. Its `non_public_storage` applies to
the plaintext storage root, not to the separately declared public ciphertext.

New execution projections add `compatibility_contract_sha256` and
`release_evidence_sha256` together. A current wrapper requires v3 and retains
both through its diagnostic and offline checks. The shared historical phase
reader still returns the original v2 projection unchanged for old package
recovery; that projection cannot authorize current execution. Old receipts,
keys and the owner's package are not relabelled, reopened or inspected here.

The implementation-side [sensitivity record](guard-compatibility-controls.json)
pins the tested source and records eight fixed/restored passing controls. Seven
isolated rule removals each make the intended refusal regression fail while the
independent valid control passes: old transport identity, technical status,
proof hash, current-source equality, owner scope, fresh post-merge release and
preservation of earlier evidence.
These tests use invented API responses and do not constitute release evidence
for capacity, runtime, a real account or an operative authorization.
