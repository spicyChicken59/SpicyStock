# Cash-preview browser controls

Every file here is **synthetic offline test data**, not a real publication,
trading recommendation, broker balance or corporate event. Never copy these
files into `docs/` or a production artifact.

`generate.py` drives the real evening pipeline with the established
`tools.make_fixture` provider, reader and chart doubles. It supplies an explicit
fresh model ledger and $2,000 equity, 0.5% base risk, 25% position cap and four-slot
ceiling. It does not change the historical $10,000 publication fixtures or
rewrite their quantities to make a test pass. The pipeline admits one COIL
anticipation ticket: four shares, $110.61 trigger, $111.72 limit and $109.50 stop,
$446.88 principal and $8.88 gross planned price-to-stop risk. Those are backend
outputs, not browser-derived strategy sizing.

`publication-multiple.json` uses the same producer and account inputs, with
only the synthetic AAPL input OHLC bars multiplied by 0.5. This makes one AAPL
share viable under the existing rules: $62.10 trigger, $63.22 limit, $60.70
stop, $63.22 principal and $2.52 gross planned risk. COIL is unchanged and the
combined producer allocation commits $510.10. `observed-multiple.json` binds
this separate publication. This hypothetical input control proves that a
per-plan preview does not reserve cash or change either published ticket.

`publication.json` retains the producer's complete publication shape. As in the
morning-observation controls, the fixture flag is removed solely so browser
tests can exercise current-publication UI guards. The synthetic run identifier
and this external note identify the control. Its source session is 10 September
2026 and its entry window is 11 September, 8:30–9:00 a.m. Chicago.

The real morning collector consumes those exact publication bytes with
snapshot and RSS doubles. `observed.json` supplies a bound observation receipt;
`halted.json` reports an invented COIL halt; `corporate-excluded.json` applies an
invented COIL cash-acquisition source. Both positive event controls must refuse
the cash preview. Synthetic quote values are coverage controls and do not claim
that COIL is inside its entry band. All receipts bind the canonical and compact
reader byte identities. No live providers or email are used.

Pin the browser to `2026-09-11T13:35:00Z`. A fee buffer of $0 and entered settled
cash of $446.88 can preview the published four shares; $446.87 can preview only
three. A preview never changes the original order, reserves cash, establishes
an actual fill or releases cash from a partial model sale.

Regenerate with `python tests/fixtures/cash-preview/generate.py`; verify with
the same command and `--check`. The generator writes only the six JSON controls
in this directory. Derive reader/sidecar transport controls with
`src.reader.derive(publication_bytes)` when a browser test needs the projected
load path.

The two complete publications retain three public strategy rule identifiers
that the generic credential detector flags. Their scanner disposition matches
only those exact identifiers AND these two publication paths. The offline
scanner controls prove copied paths, altered identifiers, unrelated values and
other credential types remain detectable; no file or detector is excluded.
