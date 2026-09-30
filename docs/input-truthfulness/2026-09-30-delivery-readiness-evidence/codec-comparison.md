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
provisional Zstandard candidate must earn its own complete size, encode/decode,
memory and recovery result on the pinned Linux PR job. There is no further local
codec search or change to the 199 MiB archive, 200 MiB ciphertext, 2 GiB expanded
payload or ten-minute packaging limits.

The maintained implementation is `python-zstandard` 0.25.0, C backend, bundled
libzstd 1.5.7. Public [versioned documentation](https://python-zstandard.readthedocs.io/en/0.25.0/)
and [release identity](https://github.com/indygreg/python-zstandard/releases/tag/0.25.0)
were read on 2026-09-30. [PyPI wheel identities](archive-dependency-identity.json)
were captured from the public version-specific JSON endpoint. The separate
archive requirements file accepts only the recorded CPython 3.12 Linux x86_64
or Windows amd64 wheel hashes. Runtime code checks package version, C backend
and libzstd version. The existing historical numerical pins are unchanged.
