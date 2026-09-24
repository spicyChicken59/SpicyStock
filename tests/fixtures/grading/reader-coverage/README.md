# Reader coverage incident: September 23, 2026

`2026-09-23.json.gz` decompresses to the **complete, byte-identical**
`docs/data.json` from publication commit
`6ff292d7971570d809a2bdd4d476a1f88d3c4234`. `source.json` records its digest,
size, execution checkout and normal production run. It includes every candidate,
original reader result, rejected VEEV response, findings and decision receipt.
No reconstruction, truncation, regrading or provider call produced this fixture.

`tests/test_reader_coverage_retained.py` depends only on APIs present at starting
main `456edb836cc42c908c50330b723dbfd97be5d506`. Copy that test and this fixture
directory into an isolated checkout of that base, then run:

```
python -m pytest tests/test_reader_coverage_retained.py -q
```

Expected before: **2 failed, 4 passed**. The GREEN budget assertion identifies
NDSN/OPY/RRR/STE/TTE/WLY as plan-eligible; the fallback assertion identifies VEEV.
The same final test passes after the correction. GREEN/YELLOW are explicitly
synthetic regime substitutions over retained states, not new production runs.
RED preserves the published absence of plans and tickets.

`test_reader_coverage.py` adds synthetic accepted A/A+ and unknown/fallback
controls, a 13-candidate pipeline budget test using the existing offline doubles,
receipt integrity and reporting checks. The browser gate uses this full retained
publication plus labelled regime projections and the normal pipeline fixtures.
