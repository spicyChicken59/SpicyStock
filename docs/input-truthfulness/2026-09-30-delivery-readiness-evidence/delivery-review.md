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
capacity still FAIL. Final candidate results will have their own source binding.
No real release or acquisition occurs.

## Exact representation and archive contract

PASS — the accepted normalization/projection and reconciliation implementations
remain byte-identical to PR96. Their source SHA-256 values are respectively
`19c7ac5ecd0cc1cae1fb45cd5d9f11b731e9d1f7ca99ab418727f67e92b0e5a5` and
`f78e38a53ed3ebc1a99ae0d05d2626b497d49aa9b51c099751787c8019fffb1c`.
No strategy arithmetic, original raw file, membership or decision is edited.
The [protected-file result](protected-scope.json) checks 10,565 original blobs
outside the explicit authorized edit list. [Source identity](source-identity.json)
compares 23 critical local files against binary-safe Git blob reads; Git IDs and
content SHA-256 are reported separately.

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

## Requests and prospective time envelope

PASS — [offline frozen-query arithmetic](frozen-request-calculation.json) covers
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
