# Full-shape synthetic projection benchmark — 2026-09-30

The central case completed an actual encrypted package/recovery round trip, with every original member byte-identical. Its archive has only **5,171,450 bytes of headroom**. The fixed longer-decimal stress case was refused at the existing gzip cap: **423,811,147 bytes**, exceeding the 199 MiB cap by **215,144,523 bytes**. Both cases exceeded the local shared 30-minute offline step. These measurements do not establish real-data capacity or hosted Linux deadline fit; real execution remains BLOCKED pending the existing technical release process.

`status: PASS` in the unchanged central run receipt means completed local synthetic packaging and authenticated recovery. It is **not** an overall workflow/deadline/readiness PASS. Stress `status: FAIL` is the actual package refusal after both complete scientific reconciliations. No caps, mandatory members, arithmetic decisions, or production policies changed, and neither full case was repeated.

## Fixed inputs and actual execution

Each fresh case used the frozen manifest `8d92ed5c56464fe9f342d024da14aa1521f6025d47ec32a6324a298b8fb63ebc`: **96 canonical bulk batches × 288 required sessions**, yielding **2,753,568 bulk rows plus 2 probe rows**. All 97 queries produced 289 synthetic page requests, with 289 ledger slots charged and zero unresolved byte reservations. The seed was `spicystock-compaction-full-shape-v1`. The actual Acquisition transport boundary, compact reconciliations and package implementation ran locally; central also completed actual age recovery. The existing Python socket-blocking context remained active. Provider requests, owner-key access, hosted workflow execution and real-mode acquisition were **NOT RUN**.

The deterministic generator includes timestamp, OHLCV, integer trade count `n`, and midpoint VWAP `vw`. Central uses varied two-place OHLC cents and integer volume. Stress uses varied nine-place OHLC and six-place fractional volume; trailing decimal digits force all five projected fields inexact. The actual projection counts were 10,572,406 inexact conversions out of 13,767,840 fields (76.7905931504%) for central, and 13,767,840 (100%) for stress. Stress's actual field mask was 31 for all 2,753,568 replayable rows. Both retained 96 compact query entries.

These are declared invented scenarios, fixed before measurement. The generator introduces no duplicates or revisions; the complete required raw, normalized and query context is retained. Possible provider revisions, duplicate patterns, other fields and decimal entropy remain uncertain. This is a measured scenario comparison, not an extrapolation from tiny samples or a guarantee of provider compression.

Both target reconciliations in both cases reported complete required windows and same-input formula PASS, with the full decisions retained. Their synthetic regime values do not reproduce an original market information set; reader actionability remains unknown. Raw bars, full reconciliation contents, ciphertext and disposable identities were kept outside Git. Only code, tests and compact synthetic inventories/receipts are published.

## Serialized payload and unchanged caps

All sizes below are actual bytes. There are **390 original source members** per case: 289 raw pages, 97 query manifests, one ledger, one diagnostics file and two complete reconciliations. The actual package index has 393 members after adding the three package metadata files; the tar also contains the index itself. The central index is published. The refused stress archive/index was cleaned by the existing package temporary-directory lifetime; the archive's measured bytes/SHA256 and the index byte count remain in the unchanged result receipt.

| Actual bytes | Central | Stress |
| --- | ---: | ---: |
| Retained raw pages | 286,962,286 | 412,833,919 |
| Query manifests | 1,354,228 | 1,354,239 |
| SQLite ledger | 86,016 | 86,016 |
| Execution diagnostics | 2,676 | 2,675 |
| Complete September 24 reconciliation | 629,004,649 | 725,956,396 |
| Complete September 25 reconciliation | 629,139,853 | 726,113,604 |
| All original source payload | 1,546,549,708 | 1,866,346,849 |
| Three package metadata members | 210,269 | 210,268 |
| Index | 67,074 | 67,168 |
| Expanded indexed payload + index | 1,546,827,051 | 1,866,624,285 |
| Tar headers and padding | 303,829 | 301,795 |
| Complete tar stream | 1,547,130,880 | 1,866,926,080 |
| Gzip archive | 203,495,174 | 423,811,147 |
| Actual age ciphertext | 203,545,054 | NOT RUN |
| External encryption receipt | 968 | NOT RUN |

| Independent unchanged limit | Central outcome/headroom | Stress outcome/headroom |
| --- | --- | --- |
| 400 request slots | 289 charged; 111 remaining | 289 charged; 111 remaining |
| Raw 1 GiB = 1,073,741,824 bytes | PASS; 786,779,538 bytes | PASS; 660,907,905 bytes |
| Expanded 2 GiB = 2,147,483,648 bytes | PASS; 600,656,597 bytes | PASS; 280,859,363 bytes |
| Gzip 199 MiB = 208,666,624 bytes | PASS; 5,171,450 bytes | **FAIL; 215,144,523 bytes over** |
| Ciphertext 200 MiB = 209,715,200 bytes | PASS; 6,170,146 bytes | NOT RUN; archive gate refused |

The central age framing/encryption overhead was 49,880 bytes. No nested compression or evidence exclusion was introduced. The stress package stopped with `package_size_or_member_limit` after writing/closing the actual gzip and before age encryption. Ciphertext, delivery, receipt and authenticated recovery therefore do not exist for stress. The separate [post-refusal preservation check](benchmark-stress-preservation.json) made one bounded comparison of all 390 retained files against their saved sizes/SHA256, with read-only SQLite integrity and unchanged accounting; it also verified absent delivery/recovered/key/package-temp paths. This is preservation, not recovery.

## Timings, memory and scratch

| Actual seconds | Central | Stress |
| --- | ---: | ---: |
| Synthetic acquisition | 236.657353 | 268.748605 |
| Reconcile September 24 | 1725.974898 | 1744.656599 |
| Reconcile September 25 plus pre-package inventory work | 1690.075366 | 1745.332251 |
| **Shared offline step sum** | **3416.050264; 56.934171 min — FAIL** | **3489.988850; 58.166481 min — FAIL** |
| Package phase | 386.196256 | 469.158996; refusal |
| Included archive-inspection overhead | 10.069609 | 16.394004 |
| Recovery and full byte/hash/accounting comparisons | 31.508186 | NOT RUN |
| Full measured wall time | 4070.476703 | 4227.963240 |

The workflow assigns both target reconciliations to one 30-minute step, so their sum is the relevant local comparison. Package timings include test-only key generation and transparent archive inspection; they are measured upper bounds for those local operations, with no packaging behavior bypass. Both package phases remained below ten minutes locally, but stress produced no admissible package. The fake acquisition clock advanced 840 seconds per case for rate accounting; those logical waits were not slept. Neither the local total below 75 minutes nor synthetic acquisition time establishes real-provider or hosted-workflow timing. No Linux runner deadline test ran.

| Native/sampled bytes | Central | Stress |
| --- | ---: | ---: |
| Physical RAM available before | 2,651,471,872 | 3,157,725,184 |
| Commit available before | 15,127,703,552 | 13,475,594,240 |
| Python native peak resident set | 4,194,906,112 | 4,602,875,904 |
| Python native peak private commit | 4,891,832,320 | 5,589,397,504 |
| Actual age encryption/decryption child peak resident set | 14,917,632 | NOT RUN |
| Conservative sum of separately measured Python and age RSS peaks | 4,209,823,744 | unavailable |
| Sampled peak scratch file bytes | 3,454,282,458 | 2,290,221,264; through refusal only |
| Free disk before | 647,329,333,248 | 642,344,771,584 |

This Windows host had 16,780,632,064 bytes physical RAM and 41,476,694,016 bytes commit limit. Native `GlobalMemoryStatusEx` checked initial capacity; `GetProcessMemoryInfo` measured process high-water RSS and `PeakPagefileUsage` private commit. Existing host load/paging affects wall time. The sum of separate Python and age peaks is conservative, not a simultaneous-process peak. Scratch is a 250ms recursive file-size sample plus packaging checkpoint, a lower bound excluding filesystem allocation overhead; stress's number covers only its refused path and is not a successful-delivery requirement.

The frozen helper used zero for an unmeasured child in one combined-RSS reporting field. Stress never launched age encryption/decryption, so **its unchanged raw combined-RSS number is unavailable**, not a measured combined peak. After both cases, only that metadata availability rule and the hardcoded Windows platform label were corrected. No generation, normalization, reconciliation, packaging or recovery behavior changed. The [reversible diff](benchmark-reporting.patch) and [before/after hashes plus focused regression evidence](benchmark-reporting-correction.json) preserve the distinction; neither full case was rerun.

## Commands and provenance

Executed from `work/SpicyStock-compaction` using the existing Python 3.12.14 environment, pandas 2.2.3, numpy 2.3.5, exchange_calendars 4.13.2 and verified age 1.3.2. In a PowerShell process, the following paths resolve to the actual fresh external workspaces used:

```powershell
$taskWork = 'C:\Users\motah\Documents\Codex\2026-09-28\github-plugin-github-openai-curated-remote\work'
@('ALPACA_API_KEY','ALPACA_SECRET_KEY','ANTHROPIC_API_KEY','GH_TOKEN','GITHUB_TOKEN') | ForEach-Object { Remove-Item -LiteralPath ('Env:\' + $_) -ErrorAction SilentlyContinue }
$env:PYTHONUTF8='1'
& ..\venv\Scripts\python.exe tools/historical_projection_benchmark.py --case central --workspace "$taskWork\synthetic-compaction-central" --age "$taskWork\age-tools\age\age.exe" 2>&1 | Tee-Object -FilePath ..\synthetic-compaction-central-full.log
# Stress started only after central and the independent normal checks finished.
& ..\venv\Scripts\python.exe tools/historical_projection_benchmark.py --case stress --workspace "$taskWork\synthetic-compaction-stress" --age "$taskWork\age-tools\age\age.exe" 2>&1 | Tee-Object -FilePath ..\synthetic-compaction-stress-full.log
```

These workspaces now exist and must not be reused; the CLI refuses reuse. Central ran once from 2026-09-30T03:32:42.615442+00:00 to 2026-09-30T04:40:33.111037+00:00, exit 0. Stress ran once from 2026-09-30T04:54:17.018318+00:00 to 2026-09-30T06:04:45.062370+00:00, exit 2. An earlier central command with a relative `..` workspace was rejected by the path preflight before workspace/data creation; the retained log records that rejection. Canonical absolute paths were then used. The full-case receipts are exact copies, not rewritten summaries.

Each actual package used a newly generated **disposable TEST-ONLY** identity, removed at exit. All execution identifiers in the central package index/receipt are **fictional fixtures**, including run ID 123456, native run number 4, phase 1 and placeholder checkout/workflow hashes. They are not an Actions execution, guard admission, real readiness assertion or reviewer release. Random test recipients/encryption mean archive/ciphertext hashes identify these exact runs; fresh reruns are not expected to reproduce ciphertext hashes. No owner key was involved.

Verified age binary SHA256: `2821a4ed191da07372acd302e5f6feae7a7985e285e1417765ebe74025af45f0`. Both full cases used the same following raw source hashes, all unchanged throughout both runs:

| Executed source | SHA256 |
| --- | --- |
| `src/breadth.py` | `8b5a27ca89d77a0e18883a3f4bbca808a87d2475eb2220d01da6d0cee0a2cb9a` |
| `src/quality.py` | `8cca1509e40de7096fd396bdff9c1a0464a7e641ae0d75c81812532d3cbc4ecc` |
| `src/scans.py` | `67559cdf70ffea87a4fcd75c13abd19193b1f55bf2d62a335ddbf68dac182668` |
| `src/sessions.py` | `aea32502bea30159d49e6b35cd68e95889694808eb561c8d34bbf7d268ad3a4b` |
| `tools/historical_acquisition.py` | `5a2202c0be49512ec6bcd7271babe3f35f3f0d1fab70cfad042112113dc5b32e` |
| `tools/historical_breadth_reference.py` | `f7dfce71abc2e048b7231e43c4de305ceaf43e4d331f0fff0798919006cfd42c` |
| `tools/historical_execution.py` | `ca5f1c842f1ddebdfc47220a687f8a5dc3ce0618153cc2e3dcacf6e7666873f0` |
| `tools/historical_execution_guard.py` | `8a1228f0909119c7602d4578a2306280492261fe29b4e85c8c211b8338d0dc3f` |
| `tools/historical_normalization.py` | `19c7ac5ecd0cc1cae1fb45cd5d9f11b731e9d1f7ca99ab418727f67e92b0e5a5` |
| `tools/historical_package.py` | `76250695cc74d01fb71b4bb51b749a7aedf2f979e2d0b4a58a24350817c6f928` |
| `tools/historical_projection_benchmark.py` | `219dae7ecd32f7f31885d98cda16c0ad7478debbdbd7e9fab21b7e0101a45d88` |
| `tools/historical_reconcile.py` | `f78e38a53ed3ebc1a99ae0d05d2626b497d49aa9b51c099751787c8019fffb1c` |
| `tools/requirements-historical.txt` | `f623de4774dc8e643e9abe19ca90d3e0970722ebaa2f8a545d657a4435ad4003` |

The final reporting-only helper SHA256 is `3ff1e870bc64c28a8000d02650ed6eaeb7974fff29df2b0b9328ce54b9bd018e`; executed full-case receipts intentionally retain the original `219dae7ecd32f7f31885d98cda16c0ad7478debbdbd7e9fab21b7e0101a45d88`. Initial seven focused benchmark checks passed with real age, including both tiny round trips and an actual archive-cap refusal before age/delivery; the frozen-shape mutation failed while two unaffected decimal controls passed. After the reporting correction, nine focused checks passed in 1.90 seconds; restoring missing-child-as-zero in memory produced one expected failure and three unaffected passes. Existing broader safety/representation controls are recorded separately in the implementation verification evidence.

## Compact evidence files

| File | Bytes | SHA256 |
| --- | ---: | --- |
| [benchmark-central.json](benchmark-central.json) | 8,099 | `7b76630958f818e52d163ca4af5e0a84c517cf56c30881d344b465d0c0b6651f` |
| [benchmark-central-members.json](benchmark-central-members.json) | 62,984 | `afb554858e6f3c2978f590e7f8a49998c7b003dce0bf139d17a14415048f78cf` |
| [benchmark-central-package-index.json](benchmark-central-package-index.json) | 67,074 | `0ae7590a90f6587b46d12f4eb19ebaa5302cf3902dee55f433905c79ea433492` |
| [benchmark-central-fixture-receipt.json](benchmark-central-fixture-receipt.json) | 968 | `d5a5fa274c905dd62347d21c3f2c811b82d257e080347ca66268d4ecbbd87883` |
| [benchmark-stress.json](benchmark-stress.json) | 7,671 | `35b739a1f0e40bbfcd5be80e38323606f4da1127a17baf926ca35f15062ca47a` |
| [benchmark-stress-members.json](benchmark-stress-members.json) | 63,078 | `1287f11bac46dfb0992c045716f8174788912bf0eb9b2d9942fc0fb701ced813` |
| [benchmark-stress-preservation.json](benchmark-stress-preservation.json) | 1,461 | `509ffdc5338000aaf33efb82310d1eee019bfcf26082f53d008cd5c73d45f040` |
| [benchmark-validation.json](benchmark-validation.json) | 1,420 | `8ddd2bbd089757d0ec0533adfd91f92d901d376e48d7da72bb91a4f6ada5f4cb` |
| [benchmark-reporting-correction.json](benchmark-reporting-correction.json) | 1,800 | `3ed191b356cc564e2fda2fb4970607ab99c75deeff01e7e01583a8346352f1f4` |
| [benchmark-reporting.patch](benchmark-reporting.patch) | 3,547 | `f736c50e3c208b44499a2121fb41ffebb7619c9c3ac9c35002d0d6556560d28a` |
| [capacity-arithmetic.json](capacity-arithmetic.json) | 8,743 | `66b691e54f64faee0d925c8b6effa454f436a3683074f0a30c49161ef650a3c3` |

The minimal next engineering decision is whether to authorize a separately reviewed approach that can fit the declared longer-decimal case and establish hosted offline deadline fit. This change does not resolve that decision by omitting evidence, increasing caps, tuning the seed, rerunning the failed stress case, or releasing a real execution. Guidance inspection and a real-data run were **NOT RUN** by this benchmark.
