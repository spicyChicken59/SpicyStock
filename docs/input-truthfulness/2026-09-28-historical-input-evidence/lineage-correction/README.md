# PR #93 raw-row lineage correction

Review `5342729066`, reviewed head `a9ed0ec3b64399e1f9d80ac3ce27d921c289f9b1`,
base/main `0d702940814af05e9b8d2a4c887aee00939e46fc`. The final correction head
and completed normal CI are recorded in PR #93 without a self-referential
follow-up commit. Every page in these regressions is synthetic.

`page_sha256` identifies exact retained JSON bytes; `symbol` selects the raw
`bars` array; `row_index` selects that array's zero-based row. `page_index` is
the zero-based query pagination order. The output marker is
`raw-page-symbol-row-v1`. These four fields exactly match the unchanged
normalizer's raw-row source identity. No cumulative index is retained.

| Evidence | Executed result |
| --- | --- |
| `before-working-tree.txt` | FAIL: direct pytest on the untouched reviewed acquisition source, 6 raw-pointer failures / 3 passing controls. Both wrong-timestamp and out-of-range defects reproduced through the actual class. |
| `controls.json`, `reviewed.txt` | FAIL: exact reviewed source loaded in an isolated process, same 6 pointer failures / 3 passing controls. |
| `fixed.txt` | PASS: all 9 focused tests, including both references, all OHLCV fields, page hashes and normalizer agreement. |
| `restored_defect.txt` | FAIL: only cumulative indexing restored in memory, same 6 failures / 3 passing controls. The expected failures make the overall control assessment PASS. |
| `verification.json` | Full-suite result, execution order, test-log hashes, source identities, zero real requests and runtime limitations. |
| `protected-files.json` | PASS: every reviewed-head tracked blob/mode except the five explicitly edited code/test/report files remains unchanged. |

The 7 page cases cover: two pages with an in-range wrong observation; a one-row
later page; three pages with multiple replacements; a duplicate inside a later
page; multiple independently indexed symbols; an unchanged same-page control;
and a no-duplicate control. The 2 additional cached-resume cases cover repeated
cross-page replacements and the same-page control.

Cached resume deliberately starts with request slots and retained bytes exactly
at their synthetic caps. The real `Acquisition.run()` path reproduces its full
manifest and duplicate references without calling transport, altering attempt
rows, changing raw bytes or resetting charges. Both previous/discarded and
selected references resolve to the actual expected raw symbol/timestamp/OHLCV
and equal the normalizer's equivalent identities. Multiple replacements point
to the immediately discarded observation, not always the first page.

Reproduction from a full-history clone (reviewed parent present), after installing
the existing pinned historical requirements:

```sh
python tools/historical_lineage_controls.py --output /tmp/spicystock-lineage-controls
MPLBACKEND=Agg python -m pytest tests/ -q
```

The runner changes source only in isolated subprocess memory and leaves the
checkout unchanged. Normal pytest collects all nine regressions; no Git history
is required by those tests themselves. Existing socket-blocking fixtures remain
active. Prior request/byte/rate/lock/retry/hash/missingness/credential assertions
are unchanged. Historical analyses and prior evidence are not regenerated.

Real acquisition and probe are NOT RUN (0 requests, 0 new response bytes, $0).
`../acquisition-execution.json` and the frozen request manifest are unchanged.
Secure runtime, access/cost, retention and approved private reviewer storage
remain BLOCKED. This repairs source references, not missing historical values,
original population membership, independent provider truth or reader approval.
