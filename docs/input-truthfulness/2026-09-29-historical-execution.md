# Historical execution preparation — 2026-09-29

Preparation checkpoint: **132 focused tests PASS; full suite pending. Dedicated
manual rehearsal, real run, run IDs and attempts: NOT RUN. Alpaca requests: 0;
new provider-response bytes: 0.** No new raw market data has been acquired.
Local synthetic integration exercised the actual acquisition, packaging and
recovery tools with seven invented transport responses; recovered bytes and
both session reconciliation outputs were identical. That establishes local
recovery, not a completed Actions rehearsal or provider-input proof.

Implementation PR: [#94](https://github.com/spicyChicken59/SpicyStock/pull/94).
The policy binds this PR; execution still requires its merge and separate dated
readiness evidence. The reviewed starting commit is `56b34a8bc7a8980559cad56be488e8a29489e4fd`, tree
`12794f02d0c291ff68ccbfdfde327d9551f5dbd1`. The assignment remains
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
The private identity never enters Git, Actions or public artifacts.

Read-only account inspection on September 28–29 found GitHub Free, an existing
Actions $0 budget with **Stop usage: Yes**, and current artifact billing of $0;
no settings changed. [Standard public runners are free](https://docs.github.com/en/actions/concepts/billing-and-usage),
and [exhausted stop-enabled budgets block additional metered usage](https://docs.github.com/en/billing/how-tos/set-up-budgets).
These support a prospective $0 basis, conditional on the applicable budget
remaining effective; they do not guarantee storage availability or delivery.
Recheck before each dispatch. Private account quantities are omitted.

[Alpaca's FAQ](https://docs.alpaca.markets/us/docs/market-data-faq) permits historical
SIP without a subscription when `end` is at least 15 minutes old. The requested
dates qualify, but the account is signed out and accepted terms remain
unverified. Rights are **BLOCKED**: current
[Customer Agreement V26.2026.07, §30](https://files.alpaca.markets/disclosures/library/AcctAppMarginAndCustAgmt.pdf#page=16)
restricts reproduction/distribution without written consent. One secure sign-in
request is pending. Encryption grants no licence. Private Guidance transfer and
recovery remain **NOT RUN** because no actual route was verified; the request
explicitly permits that status.

After Guidance review and merge, a separate owner readiness comment is required
for each phase. Dispatch first with `mode=rehearsal` and
`readiness_comment_id=<owner JSON comment ID>`. Verify GitHub run/artifact identity,
download ciphertext, recover locally, and compare both offline outputs before
considering `mode=real`. The comment body must be the entire JSON object,
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
    "rights": {"verified_at": null, "basis": "PENDING", "reference": "PENDING", "private_retention_permitted": false, "controlled_review_status": "NOT RUN"},
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

**FIX NOW.** Finish the pending full suite and normal CI, and review the dedicated workflow and helper boundary together.
Resolve the existing account's applicable Alpaca permissions through the pending
secure sign-in and read-only evidence inspection. Record what permits private
retention and hosted processing; do not replace that evidence with the fact
that the historical endpoint is free. Before either dispatch, recheck the
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
