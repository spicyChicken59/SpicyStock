# The retained HAE reply: a mechanical A+ the reader refused, 8 October 2026

Issue #109 asked that the retained HAE failure be tested and kept rejected:
"That reply attempted C/5.5 with unauthorized citations". Both publications of
the 8 October session carried the case, and each file here is that
publication's own `bursts[]` row for HAE, serialised with sorted keys from the
exact `docs/data.json` blob named in `source.json`, with nothing added,
regraded or reconstructed. `source.json` records each publication's commit, the
data blob, its SHA-256 and size, the production run, the archived account and
regime, the retained reply's SHA-256, byte count and message id, the error the
grader recorded, and the SHA-256 of the row file itself.

| publication | commit | run | account | the reply | recorded error |
| --- | --- | --- | --- | --- | --- |
| first (`burst-HAE-1e1ffe9c.json`) | `1e1ffe9c` | 37872972790 | $10,000 / 0.5% | B / 6.5, two findings | `src.ReaderAuthorityError: evidence outside criterion authority` |
| corrected (`burst-HAE-e67f8cba.json`) | `e67f8cba` | 37928234562 | $2,000 / 0.5% | C / 5.5, two findings | the same |

Both replies cite `burst.gap_pct`, `burst.bar_range_pct`, `burst.gain_pct`,
`burst.volume_vs_avg50` and (the first) `burst.volume_rank_60` or (the second)
`flags`: measurements the model read in its metrics, none of them a path under
`checks.<letter>` of the reader-evidence contract `reader_authority.validate()`
grants a finding. The row kept its mechanical A+ (10 of 10) through the
labelled fallback, the reader coverage reads `fallback`, and the plan is null:
no ticket was written on the checklist alone.

`tests/test_reader_hae_retained.py` holds the rows to their digests, parses the
retained text through the grader's own parser, replays it into the grader
through the scripted transport and into `pipeline.make_plans()` under synthetic
YELLOW and GREEN regimes, and keeps a labelled control: the same two findings
with citations copied from the row's own reader evidence are admissible, so the
refusal is the citation paths and nothing else. The control is synthetic and
proves what the contract admits; it is not a corrected grade for HAE.
