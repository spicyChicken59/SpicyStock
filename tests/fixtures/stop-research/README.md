# Stop-width research controls

All comparisons come from `src.stop_research.build`; none is an executable
stock card or a measured return. `generate.py --check` re-derives all 22 files,
verifying retained sources before producing the comparisons. No network/model
calls occur: synthetic controls use the existing market/model doubles and the
real evening pipeline, grader, planner, allocator, provenance and reader.

`current-publication.json.gz` is an immutable capture of actual publication
commit `43dcb8d7c6eb0d63c1825198aa161fc4d4caec80`, evening run `38034610157`,
measured October 9 and applicable October 12, 2026. Decompressed exact SHA-256:
`f5cbe38eaa38647364f4994bb867bbb7da4354e6a8f7f28315fb96e9b650ef0d`.
The generator checks that literal hash and all referenced sources in the
repository's immutable `docs/evidence` store. It never follows moving
`docs/data.json` for this input. The compressed transport uses gzip mtime 0;
all comparison identities refer to the original decompressed bytes.

`current` keeps the literal MG, KE, ZIM, SN, PSNL cohort: KE 1 share/$29.52/
$1.27 and PSNL 3 shares/$49.26/$2.22 are hypothetical allocation fits. SN
remains unaffordable and occupied; MG/ZIM remain archived-event refusals.
This is a source-derived research comparison with a **pinned test generation
clock** of October 10 at 12:00 UTC, not a claim that production published
research at that instant. `current-late` uses October 12 at 15:00 UTC and the
same original canonical bytes to prove a backfill remains labelled late.

Other canonical/reader files are explicitly **production-shaped synthetic
controls**, produced from offline inputs. They are not provider observations.
Following the established cash-preview fixture convention, the generator
removes make_fixture's external `fixture` marker and normalizes its transport
telemetry through that standard helper; it does not modify sealed plans.

- `priority`: four higher-ranked 4.49% research shapes, followed by unchanged
  baseline ZBASE. ZBASE reserves first; only COIL/RONE/RTHR fit remaining
  slots and RTWO is refused. Inputs deliberately change historical OHLCV
  ranges before calculation, not a published plan or receipt.
- `red`: the same five shapes with a genuine red-regime input tape; all are
  refused, including all four otherwise in-band names.
- `empty`: a quiet input tape produces no top anticipation cohort.
- `outside`: September 10 publication, outside the registered session range;
  zero comparison rows while the actual original top count remains visible.

Each normal variant stores gzip canonical bytes, gzip reader bytes, a plain
receipt and plain bundle. The late variant stores only its receipt/bundle
because its canonical/reader are exactly `current`. Synthetic source objects
are verified while the generator's temporary directory exists; they are not
archived as permanent source captures. Later fixture-only replay without that
directory is integrity and rule replay, not a retained-source audit.
