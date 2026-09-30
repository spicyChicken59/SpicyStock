# PR97 delivery-envelope acceptance — 30 September 2026

PASS — the complete fixed central and stress synthetic evidence can be packaged,
encrypted with disposable TEST-ONLY identities, recovered and reproduced exactly
under the explicitly versioned envelope. This supersedes the delivery hold in
the [earlier review](../delivery-review.md); its failures remain dated evidence.
Real execution remains BLOCKED. Historical acquisition and findings are NOT RUN.

The repository base is `19f75f3b7ad566fb98e8e8e28fd2482a3737e9bc`; this owner
continuation started at `65cd32ba0991ecad4bb04d53132d4a44889aca32`. The complete
measured code checkout is `ca881bba3600d4eadee5481e5528161a5c2edb99`, tree
`1a3b64ddfd795dbb209780b421138e7d3535312b`. Tests ran ordinary checks at PR merge
`ab23402815cd1904061fc6c7714b5621b59ca12e`; both benchmark jobs explicitly checked
out the head. The subsequent evidence-only commit and its exact-head normal CI
are recorded in the final PR97 timeline checkpoint, avoiding a self-referential
commit claim. No source change follows this measured code.

## Delivery decision and authoritative platform evidence

| Contract | Archive | Ciphertext | Expanded |
|---|---:|---:|---:|
| Preserved v2 gzip / v3 Zstandard | 208,666,624 B (199 MiB) | 209,715,200 B (200 MiB) | 2,147,483,648 B |
| New v4 receipt/index | 262,144,000 B (250 MiB) | 263,192,576 B (251 MiB) | 2,147,483,648 B |

The authenticated index and receipt both name `historical-delivery-envelope-v1`.
Actual encryption overhead must additionally remain at most 1,048,576 B. Old
schemas retain their original caps and interpretation. This changes a delivery
constraint because the full stress archive was demonstrated near 206 MiB while
its independent expanded, memory and runtime bounds fit. It does not change
scientific acceptance or predict unseen provider entropy.

The [platform observation](platform-and-contract.md) records the official sources
and the 2026-09-30 14:25–14:30 UTC read-only account check performed before edits.
[Pinned upload-artifact v7.0.1](https://github.com/actions/upload-artifact/blob/v7.0.1/README.md#limitations)
documents 500 artifacts per job and shared account quota, with a 1 GB upload
example; it does not impose the project's former 199/200 MiB ceiling. The intended
real artifact remains exactly ciphertext plus receipt, compression level 0 and
seven-day retention. GitHub's ZIP wrapper adds small separate overhead.
[Standard public-runner execution is free; artifact storage is separately metered](https://docs.github.com/en/billing/concepts/product-billing/github-actions).
The existing account-wide Actions product budget was $0 with Stop usage enabled;
no billing or storage setting changed. Reported accrued storage is not available
instantaneous capacity. Future shared-quota refusal remains possible under that
stopping control and belongs to the separate real-execution review.

## Actual full-shape acceptance

[Tests 36734865293, attempt 1](https://github.com/spicyChicken59/SpicyStock/actions/runs/36734865293)
completed PASS at the measured head. Central job `109953976064` and stress job
`109953975803` ran Ubuntu 24.04 / Python 3.12.14 with the pinned historical runtime.
Both used the unchanged PR96 generator `spicystock-compaction-full-shape-v1`,
96 canonical batches, 288 sessions, 2,753,568 bulk rows and two probe rows. The
fresh runner had no fixture cache, so each declared deterministic fixture was
generated once. Central uses varied cents/integer volume; stress uses nine-place
OHLC and six-place fractional volume, all five projected fields inexact. These
are synthetic assumptions, never provider observations.

[Measured results](measured-results.md) provide exact lengths, hashes, timings,
memory, disk and stage CPU. Each package retained 390 original members and 393
indexed members including execution/provenance. Each original member was compared
by actual bytes, length and hash after TEST-ONLY age recovery; ledger accounting
was unchanged. All 388 scientific members also match the PR96 baseline; SQLite
file bytes and diagnostics are not assumed portable between runtimes. Both full
v2 reconciliation outputs were rerun offline and compared byte-for-byte. No
excluded fields, rewritten hashes, tolerances, evidence omission or nested
compression were used. The 289 charged transport slots are simulated; provider
requests are zero. Original-information-set limits and reader uncertainty remain.

Only four compact public measurement files per case were uploaded and downloaded:
central artifact `11109327191` (26,640 B) and stress `11110657864` (26,550 B).
Their downloaded ZIP hashes match GitHub's recorded digests. Full synthetic
encryption/recovery occurred on the benchmark runner; these small artifacts are
receipts, not the full ciphertext package. The old native-4 run remains the exact
historical evidence of its hosted ciphertext-transfer path. It did not execute
this codec or envelope. No owner identity or retained private package was read.

## Bounded correction and security controls

The selected writer is unchanged: Zstandard 0.25.0 / library 1.5.7, level 12,
one-GiB window, long-distance matching and one frame. There was no further
compression search. The first v4 candidate `2e50aba0ffdc3b8bb09a7745c4e9edc45ce9281d`
fit stress capacities but failed recovery. Its reader incorrectly derived a
block-count bound from the format's maximum block size. The
[preserved failure](candidate-initial/recovery-failure.md) and actual retained
archive establish the defect; the format permits smaller blocks. The reader now
has an explicit 65,536-block work cap, checked before decoding allocation. The
writer, 1 GiB window, single-frame boundary and expanded limit did not change.

PASS — 126 focused package tests, including restored-defect failure, valid control,
exact block-work boundary and boundary-plus-one refusal. Legacy gzip and v3
Zstandard recovery, incorrect envelope/schema/binding, over-cap, resource,
corruption, truncation, trailing-data and plaintext-upload refusals remain.
PASS — normal hosted suite: 2,449 tests, 12 producer fixtures, semantic workflow
validation and clean-tree gate; unchanged page checks: 378 charts and 9,215 checks.
PASS — [Secret Scan 36734865392](https://github.com/spicyChicken59/SpicyStock/actions/runs/36734865392).
The [scanner controls](scanner-controls.md) independently verify four public
executable/source digest findings and their exact path/value AND dispositions.
Actual-engine negatives still detect unrelated key-shaped values at the same
paths, the same values elsewhere and another default detector. No broad rule,
directory, commit exclusion or history rewrite was introduced.

Hard 12 GiB cgroup enforcement covers the synthetic benchmark and its descendants,
including charged file cache/kernel memory; its supervisor and Actions runner are
outside that group. Expected OOM in a separate negative control proves enforcement.
Neither full workload had OOM or timeout. This does not claim a new memory
supervisor in the future historical workflow. Each two-date pass retains one
1,800-second deadline, packaging 600 seconds and the job 4,500 seconds. Prospective
timing reserves the whole 1,800-second acquisition step plus an explicit assumed
300 seconds for guard/checkouts/upload. HTTP latency, retry delay and future quota
are not measured by synthetic clock jumps.

## Bound evidence and reproducibility

The [public input map](candidate-accepted/assembly-input.json), actual API objects,
download checks, logs, inventories and source hashes feed the retained assembler:

```text
python docs/input-truthfulness/2026-09-30-delivery-readiness-evidence/envelope-continuation/assemble-envelope-evidence.py --repo . --inputs docs/input-truthfulness/2026-09-30-delivery-readiness-evidence/envelope-continuation/candidate-accepted/assembly-input.json --output-dir <fresh-directory-outside-Git>
```

The actual invocation produced ten PASS checks and five PASS proofs. The six
canonical output files were copied without text conversion; declaration SHA-256
is `4676955bd89be86e0e025f0724d07bc1279ed822170239c5fa446bcfe5144490`.
The assembler's independent synthetic predicate/mutation controls are retained
separately and are not hosted proof. Existing guard validation is applied to the
actual final committed technical files; no readiness or run identity is invented.

[Protected-source verification](protected-corrected-source.json) preserves 10,619
existing entries from the continuation head and 10,515 from base, all 23 actual
`src` files, frozen manifest, original recovery contract, recipient LF convention,
production/history and design-system 2.13.0/source identity. README and .env.example
were reviewed; no credential or runtime setting was added.

The [complete history observation](history-final-verification.json) at
15:31:28 UTC revalidated the three exact zero-job exceptions and native-4 rehearsal,
including authoritative attempt jobs and empty terminal pages. There are exactly
four records. Native 5 / attempt 1 / phase 2 has no run ID and remains prospective.
Compatibility v2 is narrowly bound to the exact old transport evidence and this
PR's new technical proof; current-main/source equality, reviewed final head,
merge and separate dated Guidance release remain mandatory. Personal-use wording
does not assert provider consent. Real-data fit, acquisition and historical findings
are NOT RUN. No trading correctness, reader approval or trading edge is claimed.

KEEP — complete evidence, scientific identities and the accepted evidence chain.
FIX NOW — Guidance's independent review of this measured delivery envelope,
exact recovery and scanner hygiene. DEFER — merge and any real acquisition to
Guidance's normal protected process and explicit separate release. OMIT — all
further compression optimization. This closeout starts no new milestone.
