# Morning observation browser controls

The publication and receipt files here except `qeta-captured.json` are
**synthetic test data**, not publications or trading recommendations. Never
copy these files into `docs/` or a production artifact.

`full-publication.json` and `red-publication.json` are immutable source inputs
produced by the real evening pipeline and its offline provider/chart/reader
doubles before the reader rollout, retained at commit `62bce72d`. Their raw
SHA-256 values are pinned in `generate.py`; it refuses altered input bytes and
never rewrites these files. The generator passes those exact publication bytes
to the real morning collector with snapshot and RSS doubles. The synthetic run
IDs and this external note identify the controls. Publication
and receipt files deliberately use production shapes so the browser's rejection
of rehearsal receipts can be tested separately. There are no live provider calls
or emails.

The generator supplies the matching event registry archived in both source
publications to the collector. That manual registry was reviewed on 9 October
2026, before ZIM was added; it is not a current event screen. The source inputs
and registry preserve the original migration identities when today's pipeline
or registry changes. Normal page fixtures, used by `test_morning.publication()`,
still exercise the current real pipeline and current registry. The morning
generator writes only derived receipt files, never reads its receipt outputs
to construct expected values, and does not claim today's pipeline recreates
the original historical implementation.

Pin the browser to `2026-09-11T13:35:00Z`. `observed`, `outage`, `halted`,
`resumed`, `corporate-excluded`, and `corporate-retained` bind `full-publication.json`. `no-tickets`
binds `red-publication.json`. The AAPL halt/resumption and cash acquisition are
invented test cases. IEX prices and all daily volumes are invented doubles.
`resumed` and `corporate-retained` complete at `13:35:30Z`, thirty seconds after
their bound preceding receipts, so advance the browser clock for those transitions.
`corporate-resolved` also completes at `13:35:30Z` and carries the explicit
synthetic resolution source for the prior named exclusion. The follow-up
`corporate-resolution-carried` completes at `13:35:45Z` and retains that source
so a browser that missed the first resolution can still check it.

These unprefixed receipt bytes freeze the original canonical-only binding and
remain explicit legacy migration controls. The generator reproduces that original
contract by removing only the new reader transport fields from a real collected
receipt, then validating it. There is no production option to emit legacy receipts.
The `reader-` prefixed versions are produced directly by the current collector and
add the reader projection version and digest derived from the same exact canonical
publication bytes. Their corresponding clocks and preceding receipts match the
unprefixed scenarios. Derive their reader envelope and observation sidecar with
`src.reader.derive(full_or_red_publication_bytes)`; the published input is unchanged.

`reader-halt-outage` at `13:35:30Z` binds the exact legacy `halted.json` as its
preceding receipt. Both quote feeds and the halt feed fail, but the known halt
remains retained. `reader-halt-recovered` at `13:35:45Z` binds that new outage
receipt and releases the halt only from the synthetic sourced trading resumption.
Legacy receipts remain valid for direct canonical loads; a projected browser must
require the new exact reader digest before treating their quotes as bound.

`qeta-captured.json` is different: it is the halt adapter's normalized result
from the retained actual Nasdaq RSS capture in `../morning_halts`, evaluated at
`2026-10-09T15:26:22Z`. It exercises the reported QETA halt with its actual
fractional timestamp. It is not attached to an invented publication or entry
order; the source event occurred after the strategy's morning entry window.

Regenerate with `python tests/fixtures/morning/generate.py`; verify with the
same command and `--check`. The generator only writes this fixture directory.
