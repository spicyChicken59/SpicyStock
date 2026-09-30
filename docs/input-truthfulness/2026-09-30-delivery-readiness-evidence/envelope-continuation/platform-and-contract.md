# Delivery-envelope continuation — 30 September 2026

The owner's explicit continuation supersedes the stopped 199 MiB experiment in
[Guidance 5912900598](https://github.com/spicyChicken59/SpicyStock/pull/97#issuecomment-5912900598).
This is the same PR97, from `65cd32ba0991ecad4bb04d53132d4a44889aca32` against
`19f75f3b7ad566fb98e8e8e28fd2482a3737e9bc`. No compression search is reopened.

## Platform check before edits — PASS

Read on 2026-09-30, 14:25–14:30 UTC. The pinned
[upload-artifact v7.0.1 documentation](https://github.com/actions/upload-artifact/blob/v7.0.1/README.md#limitations)
documents 500 artifacts per job and an account storage quota. Its compression
example uploads a 1 GB random file. It does not specify a 199/200 MiB per-artifact
limit. The project uses one artifact containing ciphertext and a receipt,
compression-level 0, retention 7 days, no overwrite, and immutable artifact IDs.
The action remains pinned to `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`.
The new envelope is below the documented example; this is compatibility evidence,
not a claim that artifact size or quota is unlimited. The GitHub ZIP wrapper adds
small container overhead outside the cipher file's cap.

[GitHub billing documentation](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
states standard hosted runners are free for public repositories; artifact storage
is accounted separately, shared with Packages, and accrues hourly. GitHub Free
includes 500 MB storage. Storage reporting can lag. The standard Ubuntu runner
and existing project deadlines remain unchanged; no larger paid runner is used.

Read-only authenticated account observation: Actions **product**, account scope
covering this owner/repository, **$0 budget**, **Stop usage: Yes**. This is a stopping
budget, not an alert-only budget. The
[budget documentation](https://docs.github.com/en/billing/concepts/budgets-and-alerts)
explains product scope and stopping usage. No setting was changed. Actions storage
displayed **0.3 GB used / 0.5 GB included (65%)**; its tooltip explicitly described
hourly accrual. This is not a measurement of instantaneous available bytes. Future
artifact delivery can still be refused by shared quota while spending remains
stopped. This PR uploads only small public synthetic receipts; future real
ciphertext delivery and current quota must be considered at the separate release.

## Versioned project decision

| Contract | Compressed archive | Ciphertext | True expanded content |
|---|---:|---:|---:|
| Original v2 gzip / v3 Zstandard | 208,666,624 (199 MiB) | 209,715,200 (200 MiB) | 2,147,483,648 (2 GiB) |
| New v4 package | 262,144,000 (250 MiB) | 263,192,576 (251 MiB) | 2,147,483,648 (2 GiB) |

The v4 receipt and authenticated index both identify
`historical-delivery-envelope-v1`. Ciphertext must also exceed archive length by
no more than 1,048,576 bytes. Old schemas keep their old caps and exact shapes.
The selected production codec remains level-12 Zstandard, 1 GiB window,
`ustar-zstandard-v1`; the failed 2 GiB-window experiment was never adopted.

The complete fixed stress population already measured approximately 206 MiB
compressed while expanded content, runtime and memory passed their independent
bounds. Raising the delivery envelope removes that project-imposed bottleneck
with about 44 MiB archive headroom at the prior selected-codec measurement. It
does not relax scientific acceptance or establish real-provider compressibility.
The 2 GiB expanded, 4 MiB index, 4,096-member, 600-second package, acquisition,
offline, total-job, 12 GiB process-memory and all provider budget bounds remain.

## Execution truth

The new compatibility relation names the old relation's exact digest and retains
only the exact accepted native-4 transport evidence. New package/runtime claims
require the new source-pinned central/stress evidence. Current-head/main equality,
complete history, merge review and a separate dated release remain mandatory.
Owner personal use does not assert provider consent. Real acquisition and
historical findings are NOT RUN; real execution is BLOCKED. No owner key or
accepted private package is used in these tests.
