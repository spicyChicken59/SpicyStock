**Measured delivery results - 30 September 2026**

Both complete fixed synthetic cases passed on measured source `ca881bba3600d4eadee5481e5528161a5c2edb99` in [Tests run 36734865293, attempt 1](https://github.com/spicyChicken59/SpicyStock/actions/runs/36734865293). Each case packaged, encrypted, recovered, verified every original member, and repeated both dated reconciliations with exact original output bytes. These are provider-free delivery measurements, not authorization to execute the historical workflow.

The source receipts are [central](candidate-accepted/central/benchmark-result.json) and [stress](candidate-accepted/stress/benchmark-result.json), their [central](candidate-accepted/central/memory-envelope.json) and [stress](candidate-accepted/stress/memory-envelope.json) supervisor receipts, profiles, member inventories, hosted-job records, and download verifications. All four downloaded JSON files per case were checked against the retained download hashes when preparing this table. The supervisor report hash matches the exact benchmark-result bytes.

Both runs record all 30 source fingerprints unchanged through execution and identical between cases. The corrected reader fingerprint is `e3f5a6bf5fa798e97378d17e9538917f53f6b2fb002ec7b6423571f8565d6d33`. The selected writer remains Zstandard level 12, 1 GiB window, with the existing fixed generator and seed. The reader now bounds framing work independently at 65,536 blocks; its other window, decoded-byte, archive, member and extraction bounds remain enforced. The initial stress recovery refusal is retained separately in [the initial failure record](candidate-initial/recovery-failure.md).

**Hosted execution and retained artifacts**

| Measurement | Central | Stress |
| --- | --- | --- |
| Case / supervisor / timing result | PASS / PASS / PASS | PASS / PASS / PASS |
| Job ID | [109953976064](https://github.com/spicyChicken59/SpicyStock/actions/runs/36734865293/job/109953976064) | [109953975803](https://github.com/spicyChicken59/SpicyStock/actions/runs/36734865293/job/109953975803) |
| Job start UTC | 2026-09-30T15:12:16Z | 2026-09-30T15:12:17Z |
| Job completion UTC | 2026-09-30T15:47:28Z | 2026-09-30T16:01:42Z |
| Actual job wall seconds | 2,112.000000 | 2,965.000000 |
| Artifact ID | 11109327191 | 11110657864 |
| Downloaded ZIP bytes | 26,640 | 26,550 |
| Downloaded ZIP SHA-256 | `1f3aad3fcd175916187a346a4e9f0818479308f9955ff7c73f2318b34351db3f` | `abc81923766137dc8ed98e58d0ace6ac7009e707c28c62442be644ccc5e276e2` |
| Benchmark report SHA-256 | `e8f3fc896262effd119e34e9c22a76347d867d49e850fd55654022f6fd0190ff` | `957ab3a814593b85ac9dc78f8c2c93c66b19068fc25c0b1c2186c6b188746e83` |
| Supervisor receipt SHA-256 | `0fe33212a75657ac3405b68e65e391f0625cb0d1be327d5251d78a4a27a8a677` | `fec8677ee37e3db0f6980e174627eb04f1df877f8e901fc1ba54615198708ff8` |
| Stage profile SHA-256 | `9fd2f059d556ee1b4b115fbd498e7eaab57fc1461e436595fb8ab0e33a3cd35a` | `1dbda1a0a1d766adf7be15d2a48069b83276e1505f25ab337db80778aa59c7f8` |
| Original-member inventory SHA-256 | `4e6fb8322a47389973c756a209a895244809a8f248dd1bd0f222cdc87fd2e1ae` | `bcb90f3e0b786e48772424eb640fc0eb9f8abfd687d974830335188ea476cdda` |

The artifact ZIPs contain only the four compact public measurement files, not the evidence archive or disposable identity. Both benchmark checkouts are the measured source above; the Actions event merge SHA recorded in the reports is `ab23402815cd1904061fc6c7714b5621b59ca12e`. The jobs use standard `ubuntu-24.04`, recorded image `20260920.314.1`, Python 3.12.14, four available CPUs, and pinned historical dependencies including zstandard 0.25.0. The central and stress hosts report 16,765,378,560 and 16,766,414,848 physical bytes respectively; those host observations are distinct from the enforced workload ceiling.

**Wall time and unchanged deadlines**

| Seconds unless noted | Central | Stress |
| --- | --- | --- |
| Setup including native memory controls | 34.606796 | 26.762633 |
| Synthetic fixture acquisition | 70.857869 | 91.586924 |
| Initial two-date offline pass | 961.338148 | 1,385.438099 |
| Initial offline headroom to 1,800 | 838.661852 | 414.561901 |
| Recovered two-date offline pass | 986.023782 | 1,380.726513 |
| Recovered offline headroom to 1,800 | 813.976218 | 419.273487 |
| Package including encryption | 35.053894 | 60.561012 |
| Package headroom to 600 | 564.946106 | 539.438988 |
| Archive encoding alone | 31.146695 | 56.696353 |
| Recover phase including its member-inventory instrumentation | 14.796773 | 10.326075 |
| Reproduced-member verification phase | 1.284849 | 1.350200 |
| Benchmark body wall | 2,070.765297 | 2,931.522872 |
| Supervisor workload wall | 2,071.818416 | 2,932.329593 |
| Setup plus supervised workload | 2,106.425212 | 2,959.092226 |
| Actual hosted-job headroom to 4,500 | 2,388.000000 | 1,535.000000 |
| Prospective reserved delivery total | 3,130.998838 | 3,572.761744 |
| Prospective headroom before 300-second reserve | 1,669.001162 | 1,227.238256 |
| Prospective headroom after 300-second reserve | 1,369.001162 | 927.238256 |

Prospective reserved delivery = measured setup + 1,800 seconds for the full acquisition step + measured initial two-date offline pass + measured packaging + a 300-second guard/second-checkout/preflight/upload allowance. The allowance is a planning assumption, not measured delivery overhead or a guarantee. The live acquisition guard remains 1,500 seconds, inside its unchanged 1,800-second step. Each full two-date offline pass has one shared 1,800-second budget, packaging has 600 seconds, and the total job remains 4,500 seconds. The extra recovered replay is benchmark verification; it does not split or redefine the production offline deadline.

The synthetic rate clock advances 840 seconds for 289 simulated calls without provider HTTP or real waiting. The unchanged live limits remain one request in flight and at most 20 per minute or the lower provider limit. HTTP latency, retries, Retry-After and lower provider limits remain unmeasured and can exhaust the live guard.

**Memory and scratch**

| Bytes unless noted | Central | Stress |
| --- | --- | --- |
| Enforced process-tree memory ceiling | 12,884,901,888 (12.000000 GiB) | 12,884,901,888 (12.000000 GiB) |
| Final kernel cgroup peak | 7,662,833,664 (7.136570 GiB) | 8,903,364,608 (8.291904 GiB) |
| Margin below 12 GiB | 5,222,068,224 (4.863430 GiB) | 3,981,537,280 (3.708096 GiB) |
| Python process peak RSS | 4,336,902,144 (4.039055 GiB) | 4,792,471,552 (4.463337 GiB) |
| Completed-child cumulative RSS high water | 4,333,260,800 (4.035664 GiB) | 4,792,471,552 (4.463337 GiB) |
| Separate parent/child high-water sum | 8,670,162,944 (8.074718 GiB) | 9,584,943,104 (8.926674 GiB) |
| Sampled peak logical scratch | 4,826,404,506 (4.494939 GiB) | 6,023,943,885 (5.610235 GiB) |
| Observed free disk before workload | 91,718,111,232 (85.419147 GiB) | 91,719,426,048 (85.420372 GiB) |
| Required free-disk preflight | 8,589,934,592 (8.000000 GiB) | 8,589,934,592 (8.000000 GiB) |
| Swap ceiling / workload OOM / OOM kills | 0 / 0 / 0 | 0 / 0 / 0 |
| Workload exit / timeout | 0 / false | 0 / false |

The final supervisor receipt is authoritative for the 12 GiB process-tree ceiling. Linux cgroup accounting includes descendants and charged page cache/kernel memory; the supervisor and Actions runner are outside that group. Swap is disabled for the group and `memory.oom.group=1`. Both actual below-limit controls passed as the dropped-privilege worker, including reading the counters. Both aggregate-over-limit controls intentionally triggered OOM in a separate 256 MiB group containing two 160 MiB children; those expected control failures are not workload OOMs. Both full workloads have zero OOM events, zero kills, return code zero and no timeout.

RSS is a different metric from cgroup memory. The completed-child high water includes git, disposable-identity generation and age; adding it to Python high water is a conservative sum of separate maxima, not simultaneous usage or age-only memory. Stage RSS and scratch are sampled lower bounds. Scratch uses 250 ms recursive logical-file-size samples plus a packaging checkpoint, excludes filesystem allocation overhead, and may miss transient peaks. The actual free-disk observation, rather than a generic hosted-runner disk specification, describes these runs.

**Package envelope and byte identity**

| Bytes | Central | Stress |
| --- | --- | --- |
| Retained raw responses | 286,962,286 | 412,833,919 |
| Raw headroom to 1 GiB | 786,779,538 | 660,907,905 |
| Original source-member payload | 1,546,549,708 | 1,866,346,849 |
| Expanded packaged payload | 1,546,827,527 | 1,866,624,761 |
| Expanded headroom to 2 GiB | 600,656,121 | 280,858,887 |
| Index JSON | 67,358 | 67,452 |
| Decoded tar archive | 1,547,130,880 | 1,866,926,080 |
| Tar headers and padding | 303,353 | 301,319 |
| Compressed archive | 99,741,885 | 215,909,320 |
| Archive headroom to 250 MiB | 162,402,115 | 46,234,680 |
| Ciphertext | 99,766,421 | 215,962,224 |
| Ciphertext headroom to 251 MiB | 163,426,155 | 47,230,352 |
| Ciphertext minus archive | 24,536 | 52,904 |
| Overhead headroom to 1 MiB | 1,024,040 | 995,672 |
| Public receipt JSON | 1,401 | 1,403 |

| Measured object SHA-256 | Central | Stress |
| --- | --- | --- |
| Compressed archive | `b60b318bdee70e5f356bd6ea630d55da3fb02c63d4af129dd5622deeaaba9601` | `221e09c184e8faacc9bdc9407a54eb7ab51263b810000963b00288bc6f9ec156` |
| Ciphertext | `a8a50ebd757455b18d4a9593cbc8d59c92ccbccdd75f691f2e611ad9fa4264d1` | `87192b9a9f485cbdd30048cfeeb3e7dadc0b0399b8f5915f713193e8ae37d7dd` |
| Index / decoded tar | Not separately recorded | Not separately recorded |
| Expanded payload collection | No single concatenated-content hash recorded | No single concatenated-content hash recorded |

Both observed receipts are `historical-encrypted-receipt-v4`, both recovered indexes are `historical-private-package-v4`, and both name `historical-delivery-envelope-v1` with `ustar-zstandard-v1`. The 250 MiB archive, 251 MiB ciphertext and separate 1 MiB encryption-overhead limits apply to this envelope. Earlier v2/v3 readers keep their original 199/200 MiB limits. Index and tar byte counts are measured encoder metadata; no separate index/tar fingerprints were emitted. Their contents are enclosed by the verified archive fingerprint and successful strict recovery. The source inventory fingerprint above hashes the inventory JSON, not concatenated expanded payload bytes.

| Case | Scientific output | Exact bytes | SHA-256 |
| --- | --- | --- | --- |
| central | reconciliation-2026-09-24.json | 629,004,649 | `4a4714313a39494aac8f014fa90de2577eac54e044cdcb03bff233c71ad59955` |
| central | reconciliation-2026-09-25.json | 629,139,853 | `f9c577b65e55f8fe9141861a2c858ce6b4337656a34fda8aed67e999fc5d122c` |
| stress | reconciliation-2026-09-24.json | 725,956,396 | `feb42a6319aab18fe0f4458bd57073aa4fbe9b42e3216c722766978ca307c6db` |
| stress | reconciliation-2026-09-25.json | 726,113,604 | `d981767334f0f57dadbf13bfb806cdc3af08a36088411d713891485728ef0696` |

Each fixed case contains 96 canonical batches, 288 sessions per bulk query, 2,753,568 bulk rows and two probe rows, delivered in 289 synthetic transport calls. Central uses varied two-place OHLC cents with integer volume; stress uses varied nine-place OHLC and six-place fractional volume. These invented precision distributions do not predict provider precision or compressibility.

The PR96 comparison verified **388 scientific members**: 289 raw pages, 97 query manifests and the two complete reconciliation files above. It intentionally does not presume portable SQLite bytes. Recovery separately verified **all 390 original members**, adding the actual run ledger and execution diagnostics, against that run's source inventory. The recovered index has **393 members**, including the three internal package metadata members. The recovered two-date replay reproduces both original outputs exactly; ledger accounting stays unchanged, with 289 charged synthetic slots and zero unresolved byte reservations. Both disposable test identities were removed.

**Exclusive stage profile**

Wall and CPU seconds below are the profile's exclusive values, aggregated across the complete initial and recovered passes where applicable. Removing nested instrumented work avoids double counting; inclusive parent/child times must not be summed. CPU is Python-process CPU, including its threads and sampling work, excluding child-process CPU. The exclusive sums cover instrumented scopes, not a separately measured whole-job CPU total. Each listed scope completed with zero failures and no active scope remained at report time.

| Stage | Calls each case | Central wall s | Central CPU s | Stress wall s | Stress CPU s |
| --- | --- | --- | --- | --- | --- |
| cache_validation | 192 | 65.006172 | 65.733297 | 76.698389 | 77.854085 |
| inventory | 1 | 1.258495 | 1.275688 | 1.348936 | 1.380644 |
| normalization | 192 | 127.091794 | 138.602285 | 196.498754 | 238.566424 |
| offline_initial | 1 | 14.207986 | 14.412412 | 18.033409 | 19.016960 |
| offline_recovered | 1 | 20.722943 | 14.964713 | 19.514455 | 18.689802 |
| package | 1 | 35.048078 | 34.642623 | 60.556106 | 61.371221 |
| parsing | 3076 | 49.025663 | 49.336794 | 49.342422 | 49.758413 |
| production | 80 | 45.235680 | 46.595563 | 57.005571 | 65.769187 |
| projection | 192 | 113.873501 | 114.558936 | 136.351478 | 137.432861 |
| projection_hashing | 384 | 76.245431 | 76.707994 | 99.130103 | 99.870224 |
| recovery | 1 | 11.834725 | 3.861807 | 7.367863 | 4.324512 |
| recovery_inventory | 1 | 2.960852 | 3.042985 | 2.957140 | 3.070477 |
| reference | 8 | 78.838414 | 81.056054 | 95.515414 | 100.306572 |
| reference_preparation | 16 | 1,339.267992 | 1,444.561919 | 1,999.315128 | 2,262.090742 |
| reproduced_inventory | 1 | 1.276631 | 1.311273 | 1.339893 | 1.394760 |
| serialization | 4 | 24.707042 | 24.744333 | 27.573448 | 27.690995 |
| synthetic_acquisition | 1 | 63.965299 | 61.499134 | 82.754474 | 82.858831 |

Summed instrumented exclusive process CPU is 2,176.907810 seconds for central and 3,251.446710 seconds for stress. Recorded child CPU deltas around observed age waits are 0.227427 and 0.429281 seconds respectively; they are not a full process-tree CPU account. Reference preparation is the dominant measured stage, and no scientific or strategy optimization was introduced.

Both cases report **zero provider requests**. Owner identity access, historical workflow execution and runtime admission are **NOT RUN**, and release authorization remains false. These results establish the tested synthetic delivery envelope; they do not establish the original historical information set, market actionability, live account permissions, provider timing, future storage quota, or release approval.

The retained [unfiltered historical-workflow observation](history-final-verification.json), captured at 2026-09-30T15:31:28.026062+00:00, still contains exactly four native records. Runs 1-3 (`36520481662`, `36521323183`, `36524147152`) are bootstrap failures with zero jobs. Native run 4 (`36570997883`, attempt 1, job `109414689761`) is the sole successful transport rehearsal; it is not a real-data acquisition or scientific proof. These PR Tests jobs do not add a historical dispatch. Prospective assignment phase 2 / native run 5 remains NOT RUN.
