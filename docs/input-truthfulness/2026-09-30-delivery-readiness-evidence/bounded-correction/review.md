# PR97 bounded correction — 30 September 2026

**FAIL — stop condition A.** The one authorized level-12 / 2 GiB-window
comparison produced **215,854,671 bytes**, exceeding the unchanged 199 MiB
archive limit by **7,188,047 bytes**. No further compressor, level, window,
encryption, full-case replay or optimization follows this finding. Guidance
owns the next decision; merge and real execution remain **BLOCKED**.

Authority: [Guidance comment 5910491108](https://github.com/spicyChicken59/SpicyStock/pull/97#issuecomment-5910491108).
Base: `19f75f3b7ad566fb98e8e8e28fd2482a3737e9bc`. Reviewed starting head:
`bd779c2a1ce14b8a7361c4866678e55e29ae18f8`. The final submitted head and actual
normal workflow results belong in the dated PR97 closeout comment, after push.

## The one comparison

The [unaltered supervisor receipt](window31-supervisor.json),
[comparison receipt](window31-comparison.json) and
[explicit calculation](window31-decision.json) record the actual Windows
experiment from 12:01:52 to 12:05:03 UTC. This is measured synthetic evidence,
not provider data or another representative Linux runtime claim.

| Check | Measurement | Unchanged boundary | Result |
| --- | ---: | ---: | --- |
| Complete compressed archive | 215,854,671 B | 208,666,624 B | FAIL |
| True expanded members including index | 1,866,624,285 B | 2,147,483,648 B | PASS |
| Supervised wall time | 191.094 s | 600 s | PASS |
| Python peak RSS | 2,205,577,216 B | 12,884,901,888 B | PASS |
| Peak aggregate job committed memory | 2,201,931,776 B | 12,884,901,888 B | PASS |
| Ciphertext / encryption / stress recovery | No ciphertext produced | 209,715,200 B | NOT RUN |

Compression itself took 190.425042 seconds wall / 180.734375 seconds CPU.
Native job accounting recorded 181.265625 total CPU seconds; Python peak
private commit was 2,200,743,936 bytes. The supervisor used hard Windows
process **and aggregate-job committed-memory limits**, set/read back before
resuming the suspended process. A parent wall-clock watchdog covered imports,
compression, hashing and any conditional test encryption. RSS was measured and
independently checked; the hard limit is committed memory, not working-set
trimming. See the [executed supervisor](window31-supervisor.py), its
[non-compression controls](window31-supervisor-controls.json), and the linked
Microsoft primary documentation in those receipts. Smoke, allocation refusal
and watchdog controls all passed before the experiment.

Exactly 390 retained PR96 source members (1,866,346,849 bytes) were verified
against inventory SHA-256
`1287f11bac46dfb0992c045716f8174788912bf0eb9b2d9942fc0fb701ced813`.
Every source was hashed again while being streamed into the archive. The same
96 canonical batches, 288 sessions, 2,753,568 bulk rows, two probe rows and 289
**simulated** transport slots remain. Real provider requests: **0**.

The canonical comparison has 393 indexed members plus its 67,168-byte index:
394 regular USTAR members, padded tar length 1,866,926,080 bytes. It retains the
earlier public fictional PR96 execution metadata exactly. It does not fabricate
a new real guard record. Its expanded payload is 422 bytes smaller than the
separately measured current v3 Linux package; those metadata shapes are not
silently equated. Compared with the matching earlier local 1 GiB-window
archive (215,909,395 bytes), the larger window saved only **54,724 bytes**.
The reviewed Linux v3 failure remains 215,909,287 bytes under its original
source and receipt.

The new archive SHA-256 is
`6745850f3c82a81994c6c916794868e8f4067c9e7f245b2cbfd6d93eb9a14354`.
The sampled output footprint was 215,873,410 bytes; original source lengths
plus that footprint total 2,082,220,259 bytes. This is logical retained data,
not filesystem allocation or whole-machine peak disk use. No intermediate
uncompressed tar spool was created. The full archive is retained outside Git;
only code, compact receipts and nonsensitive identities are published.

The separate [post-comparison preservation check](window31-postcomparison-preservation.json)
again matched every original member, both complete v2 output hashes and the
86,016-byte ledger hash. Its observed inventory is byte-identical to the
retained PR96 inventory. Unchanged ledger bytes preserve the recorded 289
synthetic slots / 412,833,919 retained response bytes / zero reservations;
SQLite was not opened. At this later observation the output directory totaled
215,876,657 bytes, including the final receipt written after the supervisor's
earlier sample. No ciphertext or disposable identity was present.

The process used Python 3.12.14, python-zstandard 0.25.0 C backend / libzstd
1.5.7, level 12, window_log 31, LDM, one thread, pledged content size and
checksum. The backend binary hash is recorded. The environment contained no
provider/model credentials; Python socket/DNS operations were denied by audit
hook and tested. This is not an OS firewall claim. The conditional age path
was never reached: no test identity, ciphertext or owner-key operation occurred.

Executed once from the existing workspace, with UTF-8 enabled:

```text
../venv/Scripts/python.exe ../window31_supervisor_controls.py
../venv/Scripts/python.exe ../window31_comparison_supervisor.py --execute-authorized-once
```

The first command contains only small process/resource controls, no compression.
These are recorded commands, not an instruction or permission to repeat the
closed comparison. The supervisor refuses an existing one-shot output directory.

## Security correction and retained boundaries

The [Secret Scan correction](security-controls.md) adds one AND-scoped
`.gitleaks.toml` exception for exactly two independently verified public response
digests at exactly the original `candidate-final-ci/secret_scan-api.json` path.
No default detector, historical commit, directory or rule is excluded. Actual
gitleaks 8.24.3 controls reproduce two findings before the disposition and zero
after; unrelated values at the same path, those values at other paths, and a
separate default detector still fail as intended. Normal collected tests retain
the scope constraints. Hosted final-head Secret Scan remains a separate check.

A narrowly bound PR97 benchmark deferral prevents the security/evidence push
from automatically repeating the already accepted full 1 GiB-window cases after
the new comparison has failed. It requires the exact failed receipt and the
complete unchanged scientific scope from the reviewed head. It emits **NOT RUN**,
never a current benchmark PASS. Ordinary pytest, browser and Secret Scan jobs
remain independent. Unknown paths, missing/altered evidence, different PRs and
unverified history retain the existing run-required behavior.

Production codec/package code, receipt/reader formats, scientific arithmetic,
the accepted lossless v2 representation, deadlines and all archive/raw/request
limits remain unchanged. The attempted 2 GiB window is **not adopted**. Accepted
central recovery and Linux runtime at `00a56f3dd4d8d2b68377364e04ed1f490e8e5c7c`
retain their original PASS meaning; a new central/stress recovery is **NOT RUN**.
The original native-4 transport and exact exception history are unchanged.
Native 5 / phase 2 remains prospective. The technical declaration remains
**BLOCKED**; new helper/security source changes are not certified by the old
source-bound proof. The current prospective scope does not grant a new release
for `.gitleaks.toml`. No compatibility or release guard was weakened to hide that.

KEEP — original evidence, native identities, owner-personal-use wording, limits,
strategy/website and design-system 2.13.0. FIX NOW — Guidance reviews this measured
stop and the exact scanner correction. DEFER — any additional delivery decision
and any later source-bound release require a new explicit instruction. OMIT —
another optimization round, repeated hosted rehearsal, owner-package access,
provider contact/acquisition and trading claims. Real-data correctness, reader
authority and trading edge are not established by these synthetic checks.


## Later local commit-range finding — preserved FAIL

The full PR-range scan after local commit
`629ed4433daa6ff60a636cd56490cabb52a371f8` scanned five commits / approximately
1.75 MB and returned exit 2 with four new `generic-api-key` findings. The two
original public-response findings are resolved. Astra introduced the new
findings in the retained measurement/source-identity evidence; the final gate
cannot be called PASS from the earlier focused controls.

- `window31-supervisor.json`, line 4, and `window31-supervisor.py`, line 45:
  the SHA-256 of the already verified public age-keygen executable.
- `focused-tests.json`, lines 52 and 54: SHA-256 fingerprints of the two new
  public scanner-control source files.

These are nonsensitive provenance values, independently checked against the
actual binary/source bytes. They are not owner identities or credentials.
Nevertheless, no additional exception is authorized by this correction.
Deleting or renaming them in a later commit would not remove the range finding.
The original exact two-value/path exception remains the only new disposition;
there is no detector bypass, broad suppression or rewritten history. This
additional FAIL must be reviewed by Guidance alongside the capacity stop.

Actual command:

```text
gitleaks 8.24.3 detect --redact=100 --no-banner --config .gitleaks.toml --report-format json --exit-code 2 --log-opts="--no-merges --first-parent 7c0d35d1b4ea781f1660656a193c5c0ce019f04a^..HEAD"
```

See [the independent finding verification](final-local-scan-findings.json).
Normal exact-head hosted Tests and Secret Scan will be reported separately in
PR97; this local failure is preserved even if subsequent review changes scope.
