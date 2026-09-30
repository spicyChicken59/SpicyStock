# Historical outer archive v3 — best complete candidate, readiness BLOCKED

The writer uses `historical-encrypted-receipt-v3`,
`historical-private-package-v3`, archive format `ustar-zstandard-v1`, and the
fixed ciphertext name `evidence.tar.zst.age`. The final candidate uses level 12,
the smallest complete archive in the bounded comparison. Its measured stress
archive still exceeds the unchanged cap, so delivery readiness is **BLOCKED**.
The final pinned Linux experiment measures this candidate's successful and
refused paths; it is not another compression search. See [the comparison](codec-comparison.md).

Every ordinary source member remains its exact original bytes. Only the outer
compression and explicit package metadata change. There is one USTAR archive,
one Zstandard frame and one age ciphertext. There is no nested compression or
excluded source member. The frozen scientific format remains reconciliation v2.

The encoder requires python-zstandard 0.25.0, its C backend and bundled libzstd
1.5.7, with the independently recorded wheel hashes. Parameters are level 12,
window_log 30 (1,073,741,824 bytes), long-distance matching enabled, zero worker
threads, checksum enabled and a pledged exact tar size. The remaining level/LDM
defaults are those of this pinned version. The complete local level 12 trial
measured peak private commit 1,269,575,680 bytes and 189.145685 seconds. Its archive
was 215,909,395 bytes, exceeding the 208,666,624-byte cap by 7,242,771 bytes. These
are observations, not a general encoder memory ceiling or hosted measurement.

## Identity and limits

New execution metadata contains the existing exact projection plus
`compatibility_contract_sha256` and `release_evidence_sha256`. Neither field is
optional for a new package. The CLI accepts only a full v3 guard and retained v3
diagnostic with matching execution binding. A receipt adds the fixed codec/name,
compressed archive length/SHA-256 and ciphertext length/SHA-256. The authenticated
index independently binds execution, recipient, manifest, codec and every member
path, byte length and SHA-256. Receipt provenance still comes from the operator's
independently verified expected execution, not successful decryption.

The limits remain distinct:

| Boundary | Maximum |
| --- | ---: |
| Compressed archive | 208,666,624 bytes (199 MiB) |
| Age ciphertext | 209,715,200 bytes (200 MiB) |
| Actual expanded payload, **including index** | 2,147,483,648 bytes (2 GiB) |
| Index and each internal metadata member | 4,194,304 bytes |
| All tar members including index | 4,096 |
| Decoder window | 1,073,741,824 bytes |

Tar headers and padding are measured separately. Decoding uses bounded 1 MiB
output reads into a new private spool, limited to the payload cap plus at most
4,096 ×1,024 +10,240 framing bytes. The exact index sum is checked before member
extraction. Large reconciliation files are copied and hashed in chunks, never
loaded as JSON by recovery. Internal metadata reads have the smaller bound above.

Recovery temporarily retains sources, ciphertext, decrypted compressed archive,
decoded tar and recovered members. At all maximum bounds this can exceed 6 GiB;
the synthetic runner's conservative free-space preflight is 8 GiB. Scratch must
remain outside Git with the existing private-directory controls. This preflight
is not an increase to any evidence cap.

## Strict reader and legacy compatibility

Zstandard framing is checked before decoder allocation: exact standard magic,
valid descriptor bits, known bounded decoded length, checksum present, no external
dictionary and a window no larger than 1 GiB. A bounded block walk requires one
complete frame ending exactly at the compressed file's EOF. Skippable frames,
second frames, trailing zeros/data and truncation are refused. libzstd then checks
the actual compressed data and checksum while output remains bounded.

The pinned binding passes `max_window_size` in **bytes**, directly to
`ZSTD_DCtx_setMaxWindowSize`; its prose documentation labels this argument KiB.
The source implementation and a focused before-allocation window test govern the
explicit byte bound here. See the [versioned C source](https://github.com/indygreg/python-zstandard/blob/0.25.0/c-ext/decompressor.c)
and [Zstandard 1.5.7 framing specification](https://github.com/facebook/zstd/blob/v1.5.7/doc/zstd_compression_format.md).

The tar reader parses fixed 512-byte USTAR headers with Python's checksum/numeric
parser, without automatic PAX/GNU extension interpretation. It admits only regular
allowlisted files, unique canonical paths and matching indexed lengths/hashes.
Links, extensions, duplicate paths, nonzero padding, extra tar records/archives,
missing end markers and unapproved members fail closed. Exactly two zero end
blocks and their zero padding to the final 10,240-byte record are required.
SQLite integrity and retained metadata are checked before atomic promotion.
Handled failure or interruption removes temporary plaintext and never promotes
a partial recovered directory; original source storage is preserved.

Old receipt/index **v2**, their original execution key set and
`evidence.tar.gz.age` remain readable without installing Zstandard. They are never
relabelled v3. The gzip reader now requires one complete stream, a valid footer
and EOF; old valid writer output passes, while previously ignored trailing data
is refused. It also includes the index in expanded accounting. Receipt v1 and
unsupported codec/schema combinations remain rejected.

## Executed controls

The focused package/codec suite includes actual age roundtrips with disposable
TEST-ONLY keys, wrong-key/tamper/truncation refusals, exact legacy member recovery,
both-format unsafe-member controls, unsupported codec and receipt binding,
oversized/unknown-window or content-size rejection, bounded decoded output,
corruption/concatenation/trailing-byte rejection, index accounting, source
preservation, failed encryption and interruption cleanup.

[Final restored-defect evidence](codec-restored-controls-level12.json) executes five unchanged
valid/negative controls, then separately restores ignored gzip trailers, excluded
index bytes and late window checks in child-process memory. Each restored defect
makes its targeted test fail; no source file is edited. The
[small reproduction script](codec-restored-controls.py) also rejects fixture errors
as evidence of a caught defect. A first external attempt had overlong Windows
fixture paths and its FAIL receipt is retained locally; the published run uses
short paths and records the actual test results and unchanged source hashes.

All [95 focused package controls](codec-level12-focused-summary.json) passed on
the selected level 12 source, with zero skips, in 8.82 seconds. The explicitly
identified [positive legacy recovery](codec-legacy-controls-level12.json) proves
the old receipt/index and execution binding are preserved and every member is
recovered exactly, using disposable TEST-ONLY age identities.

Frozen runtime SHA-256 values at the final controls:

- `tools/historical_package.py`: `25abc3d522b9a6398f3a9567387bb3e51831f7fa95fcb940c62decbf0c942d9d`
- `tools/historical_archive_codec.py`: `4a0b4fbbe18eae1a3feed32cc7a6a08a9ee97ebd8e3e507c6029baf031319def`

The initial level 19 codec hash remains
`1d99e3f826e7a64ae99d317ad44d941337187d8dc66802e1ab6c405c94565248`, with its
[original restored-control receipt](codec-restored-controls.json) and measured
deadline failures preserved. The only codec source change selects level 12.

Full-scale representative capacity, encryption/recovery and shared-step/total
runtime results must be read from the actual Linux benchmark evidence. The local
unit and restored-defect controls do not authorize historical execution.
