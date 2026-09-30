# Prospective compaction compatibility — unresolved, nonoperative

This is a review proposal under Guidance comment 5903186288, not readiness,
permission, a new historical phase, or an implementation of a compatibility gate.
The recommendation for the compaction PR is to leave the execution policy, guard,
workflow, wrapper and package identity checks unchanged. Guidance must separately
decide whether the exact earlier transport/recovery evidence is sufficient for the
new representation after reviewing its offline equivalence and capacity evidence.

## Immutable earlier evidence

The source is only repository `spicyChicken59/SpicyStock`, repository ID
`1352997802`, workflow ID `369770564`, path
`.github/workflows/historical-input-proof.yml`, assignment
`spicystock-historical-input-2026-09-28`:

- Accepted implementation PR: **95**.
- Hosted rehearsal run: **36570997883**, native **4**, attempt **1**, phase **1**.
- Rehearsal workflow revision: `2687b96d0200903c5d457301e4b3f335fcfb79ce`.
- Rehearsal execution checkout: `6b12fdfa67355b436fde89287d159bebda2ce9fc`.
- Execution job: `109414689761`; readiness comment: `5890657526`.
- Artifact: `11033808340`.
- Ciphertext SHA-256: `d5ab72c0c070850c38b7ca5ebbd96c70a979f8f5e186e04ce05ed1d4cc479813`.
- Accepted original gzip plaintext archive SHA-256 (prior public report only):
  `6768b73de9d35569d08461dc23b4abd9ebeec809222c92a90187662fab61db62`.
- Accepted recovery checkpoint SHA-256:
  `da45baf8df75eb7839aeb0aadbfbb3ab8d9568bbe9d89c7430846c5e5b0c4c35`.
- Frozen canonical manifest SHA-256:
  `8d92ed5c56464fe9f342d024da14aa1521f6025d47ec32a6324a298b8fb63ebc`.
- Recipient ASCII-plus-LF SHA-256:
  `0f539a14ca5bf12a1ad3a706747316bc886d375b17e757af32c237aa39b8ec4f`.
- Unchanged original recovery-contract SHA-256:
  `6b49a4956c8196c432e9798149e2e1544b075a13353351cb10dfe241f72aae7a`.

These identities are public facts from the accepted readiness/recovery report and
the public run response, not a new private-data inspection or replay.

PASS - a read-only Git comparison of accepted checkout `6b12fdfa67355b436fde89287d159bebda2ce9fc`
with compaction base `6284cb9787c11929eaedf1a263cf463ab4ae4928` produced no diff
for `.github`, `src` or `tools`. `git rev-parse <revision>:<path>` returned these
identical tree IDs at both revisions:

| Path | Git tree ID |
| --- | --- |
| `.github` | `df40e48410be21d9a7b1cbcda4e21fc911aa9eb8` |
| `src` | `14c96a4b4c8e3e8fdccbdb1d537aade3ab1fb170` |
| `tools` | `2ae341504f3f7ab8d7c5ae22fffb613daf4693bf` |

This establishes the starting relation only. The new compaction deliberately
changes `tools`; it cannot pass the old checkout's source-equality gate.

## Smallest proposed prospective relation

Bind one future reviewed compaction PR number and its exact final head to the
above immutable source, the new explicitly versioned projection representation,
and hashed offline equivalence/capacity evidence. The target fields must remain
unbound until a real PR/final head exists; no placeholder can authorize execution.
The final review should enumerate exact changed paths plus old/new Git blob IDs.

The only changed runtime paths contemplated are
`tools/historical_normalization.py` and `tools/historical_reconcile.py` for the
lossless projection representation/decoder. Any additional runtime path changes
invalidate this narrow proposal and require an explicit scope decision. New
synthetic benchmark helper `tools/historical_projection_benchmark.py`, tests and
documentation are support changes whose exact paths/blobs must be enumerated
separately; they grant no execution rights.
The workflow, guard, policy, acquisition, execution wrapper, package encryption
and recovery implementation, dependencies, `src` tree, frozen manifest, recovery
contract and all limits must remain identical to the accepted checkout.

The reviewed offline evidence must demonstrate unchanged DataFrames, decimal
audit, selected/discarded lineage, predicates, unknowns and decisions, and exact
legacy conversion-fact reconstruction on fresh synthetic inputs. Accepted run
36570997883 remains evidence of the **old** transport/encryption/recovery path;
it must never be described as executing or validating the new decoder. Its
receipt, execution document and local-recovery record are not rewritten.

If Guidance later permits limited compatibility implementation, the declaration
must distinguish the old rehearsal identity from the new execution identity,
admit only this exact pair, and apply only prospectively to real phase 2. Current
reviewed-head-versus-main `tools`/`src` tree equality and workflow-byte equality
must still hold for the **new** PR/head. No older-successful-run fallback, extra
rehearsal, run-number reset, or source-equality bypass is proposed. Existing rights,
cost, entitlement, durable-history, retry, deadline and package checks remain.

## Checks that deliberately block integration today

- `validate_readiness` rejects old recovery checkout versus new readiness checkout:
  `stale_recovery_binding`.
- `validate_pr` rejects a new checkout borrowing PR95's head:
  `unreviewed_checkout`.
- `verify` rejects changed main tools versus the reviewed checkout:
  `execution_code_changed`; workflow bytes are separately checked.
- `validate_execution_binding` rejects an old execution identity under another
  implementation-PR policy: `unbound_execution_policy`.
- Wrapper `validate_execution` rejects offline use of the old execution document
  on another checkout: `checkout_identity_rejected`.
- Wrapper retained-diagnostic/package execution checks and package receipt
  expected-execution checks also preserve the original identity; they must not be
  relaxed or relabelled to make a new-head replay appear to be the accepted run.

Four normal-collected synthetic guard regressions pass. Three independent
in-memory rule removals each produce the intended one-test failure with the other
three controls passing; no shared source was modified. Exact evidence is in
[binding-controls.json](binding-controls.json) beside this proposal. This tests
the present hold, not a future bridge.

The unresolved decision is whether to authorize this narrow compatibility relation
after compaction review. Until then, the current binding mismatch is intentional
and real execution remains BLOCKED for technical release review.
[The later owner decision, comment 5903266884](https://github.com/spicyChicken59/SpicyStock/pull/95#issuecomment-5903266884),
states personal use and ends further licensing audits and Alpaca outreach. The
earlier unsent draft is historical, not pending work. This does not establish
provider consent. Any obsolete project-imposed attestation must receive an
explicit, accurately labelled reviewed adjustment; this PR neither changes those
checks nor fills their booleans with invented consent.
