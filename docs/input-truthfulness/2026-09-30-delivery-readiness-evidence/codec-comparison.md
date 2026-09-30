# Bounded outer-codec comparison, 2026-09-30

The input is the authorized PR96 public synthetic cache, never an owner package.
[Original verification](original-synthetic-verification.json) checked all 390
members of each case by exact length and SHA-256 against the unchanged PR96
inventories before these trials. No reconciliation was regenerated. The retained
[measurement script](local-codec-comparison.py) is the exact external script run
from the thread's `work/` directory; its paths describe that local workspace.
It is evidence, not an automatic workflow or a new acquisition interface.

Commands, using the existing Python 3.12.14 environment:

```powershell
work/venv/Scripts/python.exe work/codec-comparison.py verify
work/venv/Scripts/python.exe work/codec-comparison.py compress --case stress --codec xz --preset 6
work/venv/Scripts/python.exe work/codec-comparison.py compress --case stress --codec zstd
```

| Measured Windows result | XZ / LZMA2 preset 6 | Zstandard level 19, long-distance matching |
| --- | ---: | ---: |
| Status under the fixed 600-second trial | FAIL | FAIL |
| Wall seconds | 600.033887 | 600.123145 |
| CPU seconds | 571.671875 | 565.765625 |
| Incomplete file bytes, **not final archive size** | 75,522,660 | 52,134,408 |
| Peak native RSS bytes | 122,179,584 | 1,056,862,208 |
| Peak native private commit bytes | 112,103,424 | 1,714,671,616 |
| Dictionary/window ceiling bytes | 8,388,608 | 1,073,741,824 |
| Decode/encryption/recovery | NOT RUN | NOT RUN |

The full [XZ receipt](local-xz6-trial.json) and
[Zstandard receipt](local-zstd19-trial.json) preserve timestamps, exact input
inventory, tool identity, parameters and partial results. A preliminary XZ run
used noncanonical pretty-printed manifest bytes; it was interrupted and excluded
from these measurements. Its 7,926,303-byte partial file is retained locally as
an invalid trial, not counted as passing evidence. Preset 9 is NOT RUN because
the smaller-dictionary preset already exhausted this bounded local trial.

Neither partial file establishes capacity, compression ratio or recoverable
delivery. The differing amount of processed input also prevents ranking them
by these partial lengths. These are Windows-under-load observations. The
initial level 19 candidate subsequently reached the actual Linux package
deadline without a complete archive. Its central reconciliation took 720.360607
seconds, while package processing stopped after 600.097817 seconds. That measured
encoder bottleneck justified the two explicitly bounded comparisons below; it
does not justify changing scientific code or any deadline.

## Final bounded speed/size correction

The level 9 and then final level 12 trials reused all 390 unchanged PR96 stress
members. Each checked the current path set and file lengths, and verified each
member's original SHA-256 while compressing. All framing/window/LDM settings,
tar contents and the fixed 600-second stop stayed unchanged. No reconciliation,
key generation, encryption or recovery was run for these archive-only trials.

| Complete Windows stress trial | Level 9 | Level 12 |
| --- | ---: | ---: |
| Archive bytes | 219,253,907 | 215,909,395 |
| Bytes above unchanged 208,666,624 cap | 10,587,283 | 7,242,771 |
| Wall seconds | 83.097097 | 189.145685 |
| CPU seconds | 78.765625 | 179.609375 |
| Peak native RSS bytes | 1,244,631,040 | 1,276,121,088 |
| Peak private commit bytes | 1,238,302,720 | 1,269,575,680 |
| Archive capacity | FAIL | FAIL |
| Encryption/recovery | NOT RUN | NOT RUN |

Exact [level 9 receipt](local-zstd9-trial.json) and
[level 12 receipt](local-zstd12-trial.json), and the executed external
[level 9 script](local-codec-level9.py) and [level 12 script](local-codec-level12.py),
are retained. Like the initial script, these copied evidence scripts resolve
paths from their original `work/` location; they are not automatic repository
workflows. Commands were the original `compress --case stress --codec zstd`
command with `work/codec-comparison-level9.py` or
`work/codec-comparison-level12.py` respectively.

**Level 12 is the best complete measured candidate; readiness remains BLOCKED.**
It becomes the final review candidate so normal Linux CI can measure central
recovery and the actual stress-cap refusal. It is not claimed to fit the stress
cap. The original level 19 failures and original source hashes remain dated
evidence. No further settings, memory windows or codecs will be tried within
this bounded comparison. The 199 MiB archive, 200 MiB ciphertext, 2 GiB expanded
payload and ten-minute package limits remain unchanged.

The smallest whole-MiB paired proposal that admits the measured level 12 archive
would be 206 MiB archive and 207 MiB ciphertext, but archive headroom would be only
97,261 bytes before the changed v3 package metadata or real-data uncertainty.
That is insufficient evidence for a robust cap increase and **is not implemented
or recommended as a release**. The better next decision is to keep the caps and
request one separately reviewed level 12 / 2 GiB-window experiment, with a
12 GiB process memory ceiling on the 16 GiB runner, the same 600-second deadline
and exact members. A larger window
may improve repeated-content compression; no such improvement or fit has been
measured, and that experiment is deferred for review rather than performed here.

The maintained implementation is `python-zstandard` 0.25.0, C backend, bundled
libzstd 1.5.7. Public [versioned documentation](https://python-zstandard.readthedocs.io/en/0.25.0/)
and [release identity](https://github.com/indygreg/python-zstandard/releases/tag/0.25.0)
were read on 2026-09-30. [PyPI wheel identities](archive-dependency-identity.json)
were captured from the public version-specific JSON endpoint. The separate
archive requirements file accepts only the recorded CPython 3.12 Linux x86_64
or Windows amd64 wheel hashes. Runtime code checks package version, C backend
and libzstd version. The existing historical numerical pins are unchanged.
