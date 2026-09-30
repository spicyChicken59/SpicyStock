# First v4 envelope candidate - 30 September 2026

FAIL - full stress recovery at candidate
`2e50aba0ffdc3b8bb09a7745c4e9edc45ce9281d`, Tests run `36731412511`,
job `109941861391`, attempt 1. This is provider-free PR test work, not a
historical workflow execution. The artifact was downloaded through the GitHub
connector and its 26,303-byte ZIP matched GitHub's SHA-256
`f77b8f6faef8174a10ce4519efa16e983e66918474b15f48636e947c0c646d95`.
The four exact small diagnostic members and authoritative API metadata are
retained beside this report. No private key or market-data package was accessed.

PASS - the fixed complete stress archive fits the new envelope: 215,909,311
archive bytes, 215,962,215 ciphertext bytes (52,904 overhead), and 1,866,624,761
expanded payload bytes including index. The two complete v2 outputs and all 388
portable scientific members matched PR96. The original 390-member inventory was
captured, but recovery stopped before its exact comparison; that check is NOT RUN
for this candidate. Packaging took 47.837187 seconds, initial two-date reconciliation
480.632557 seconds, and the enforced 12 GiB cgroup peaked at 5,951,119,360 bytes without
OOM. These bounds passing do not turn recovery into PASS.

The decoder returned `invalid_package_archive` after decrypting. A read-only
frame walk of the already-retained selected-codec synthetic stress archive
(`b6b9b607efe8c9380ae13d63faaa12c6481e9334b9403df7224d9f60b1435035`,
215,909,395 bytes) reproduced the underlying `invalid_archive_block` refusal.
It has 20,463 legal blocks; the old reader admitted only 16,418 and rejected
block 16,419. Its 1 GiB window, known content size, checksum flag, dictionary absence
and exact final boundary all passed structural checks.

The [Zstandard 1.5.7 specification](https://github.com/facebook/zstd/blob/v1.5.7/doc/zstd_compression_format.md#blocks)
defines 128 KiB as a maximum block size, not a required size. The correction replaces
the false decoded-size-derived count with a separate 65,536-header work ceiling.
This permits the demonstrated valid variable blocks while retaining a finite
preallocation refusal for excessive framing work. Writer version, level, window,
LDM, frame format and scientific content do not change. No new compression trial
was performed. Existing window, expanded, compressed, member, index, checksum,
truncation, trailing-data and unsupported-format checks remain in force.

FAIL - the independent browser job `109941704034` reached its unchanged 15-minute
timeout. Its complete log is retained. No browser fixture, assertion, code or
timeout is altered. Secret Scan run `36731412817` and the normal Python job
passed (2,446 tests); the overall Tests workflow cannot be called PASS.

BLOCKED - the technical declaration and real execution remain blocked. A changed
reader requires new source-pinned normal CI and complete synthetic recovery;
earlier results stay dated evidence. Historical acquisition and findings are
NOT RUN. Native 4 remains old transport evidence and native 5 / phase 2 is prospective.
