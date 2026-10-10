# Registered anticipation stop-width research, version 1

`anticipation_stop_width_4_to_5_v1` compares the original 4% anticipation cap
with an explicit 5% pure-planner input for applicable sessions **2026-10-12
through 2026-11-06**, inclusive. The account remains $2,000, 0.5% base risk,
25% per-position cap and four slots. No provider/model calls or order payloads
are produced. Production wrappers and archived strategy rules remain unchanged.

## API and transport

`src.stop_research.build(canonical_bytes, objects=retained_source_directory,
picks=None, generated_at=None)` returns `receipt`, `receipt_bytes`, `bundle`,
`bundle_bytes`. A supplied clock makes it deterministic. The normal clock is
actual UTC collection time, not the publication's older run-start stamp.
Supported rule/account integrity and all retained candidate sources must PASS.
`allow_fixture=True` permits explicitly offline rehearsals. Integrity-only
replay (`require_sources=False`) is reserved for already captured controls and
validation, not the production writer.

`parse_receipt(raw)` and `validate_bundle(receipt_raw, bundle_raw)` require only
Python's standard library. `validate_for_publication(canonical_raw,
receipt_raw, bundle_raw, objects=None, picks=None)` also replays the comparison
against exact canonical bytes and supported archived rules. With an object
directory, this includes source verification; without it, it is integrity and
rule replay, not an independent retained-source audit.

Fixed `stop-research.json` is at most 16 KiB. Its `bundle` has exactly `path`,
`sha256`, `bytes`; the only path is `stop-research/<64-lowercase-hex>.json`,
at most 128 KiB. Both JSON objects reject duplicate keys/nonfinite values and
unknown fields. Byte hashes cover exact UTF-8 bytes, before JSON decoding.
They are consistency checks, not signatures from an independent authority.

Common receipt/bundle fields:

- `schema_version`: 1; `policy`: exact supported object from `POLICY` in the
  module (registration dates, account, caps and unchanged-geometry policy).
- `publication`: existing morning/reader binding: `data_sha256`,
  `context_sha256`, `run_id`, `rules_version`, `measured_session`,
  `applicable_session`, `published_at`, `reader_projection_version`,
  `reader_sha256`. Reader identity is the exact compact-reader byte hash.
- `timing`: `generated_at`, `entry_opens_at`, `entry_cutoff_at`, all aware
  timestamps; `classification` is `before_entry`, `during_entry` or
  `after_entry`, judged using the actual producer clock. A late backfill is
  never labelled prospective merely because its source stamp is earlier.
- `status`: `recorded` within the registration dates, otherwise
  `outside_period`; `reason`: null or the fixed outside-period explanation.
- `counts`: `top_count`, `considered`, `in_band`, `mechanical_fit`,
  `allocation_fit`, and `by_blocker` with every supported blocker key.

## Cohort and allocation

The bundle adds `rows`, `reservations` and the exact `limits` list in the
module. All original top anticipation rows (maximum five) are retained in
rank order, including refusals/out-of-band names. Outside-period cohorts have
zero considered rows, retaining the actual `top_count`. Empty/refused cohorts
are evidence, not missing results. This is a dated comparison, not live entry
permission; an old exact-bound record may only be described as archived.

Each row has exactly:

- `rank`, `ticker`, `in_band` (`4 < recorded rounded stop_pct <= 5`).
- `evidence`: original `id`, `plan_sha256`, `source_sha256`, and
  `inputs_sha256` (the existing `typed-json-f64hex-v1` input digest).
- `baseline`: `admitted`, `eligible`, `action`, `reason`, `shares`; copied
  original admission/refusal and sizing, never a new order.
- `levels`: null on invalid planning inputs, otherwise unchanged `trigger`,
  `limit`, `stop`, `stop_pct`. The 4% helper must reproduce original geometry,
  sizing and multipliers before any comparison is accepted.
- `research`: `mechanical_fit`, `allocation_fit`, `shares`, `principal_usd`,
  `risk_usd`, `risk_per_share`, `effective_risk_budget_usd`, `multipliers`
  (`regime`, `hazard`, `stop_risk`, `total`), `blockers`, `projection_sha256`.
  Sizing fields are null when inputs cannot be planned. The projection hash
  covers sorted-key compact UTF-8 JSON of evidence, levels, exact policy and
  research fields excluding the digest. Browsers do not reconstruct Python
  numeric spelling; they verify raw bundle SHA and original reference IDs.
- `event`: `blocked`, `status` (`known_event`, `review_required`,
  `not_in_registry`), `registry_sha256`, `event_ids`. Exact archived manual
  registry only; no-match never asserts live news/earnings clearance.
- `quality`: original `watchlist_eligible`, `source_session`, and
  `review: not_required_by_anticipation`. There is no invented chart review.

Blockers are `outside_band`, `watchlist_ineligible`, `market_gate`,
`known_event`, `invalid_inputs`, `no_whole_share`, `occupied_model_symbol`,
`baseline_symbol_reserved`, `slot_cap`, `equity`, `duplicate`. These can
overlap; for example SN has both zero shares and an occupied model symbol.
Mechanical fit excludes market/events/invalid inputs/zero shares; allocation
fit additionally respects occupied symbols and shared remaining resources.

`reservations` contains `equity_usd`, `position_cap_usd`, `max_slots`,
`open_model_principal_usd`, `open_model_slots`, `open_symbols`,
`baseline_principal_usd`, `baseline_risk_usd`, `baseline_slots`,
`baseline_symbols`, `available_principal_usd_before_research`,
`research_principal_usd`, `research_risk_usd`, `research_slots`, `slots_used`,
`remaining_model_principal_usd`. Actual baseline tickets reserve first,
then research fits in original watchlist rank. Baseline tickets cannot be
displaced. These are model commitments, never broker cash or holdings.

The exact `limits` list states research-only/no-orders, manual-event-only
coverage, no new chart review/live quote/earnings check, principal excluding
actual fees, gross price-to-stop risk excluding gaps/slippage, model rather
than broker cash, and no established returns or strategy edge.

## Retention and failure

`write_publication` first verifies the complete result, then keeps immutable
bundles and a bounded append-only `stop-research/index.json`. At most 128
cohorts / 16 MiB, index at most 64 KiB, no pruning. Each index entry records
bundle SHA/bytes, canonical SHA, applicable session and actual generated time.
Repeating an exact publication preserves its first cohort and clock, including
when revisiting an older publication. The latest receipt is installed last.
Symlinks, invalid existing evidence or exhausted capacity refuse a new write;
original publication/history and retained cohorts remain inspectable.

The evening hook runs after final canonical/reader bytes in both delivery
outcomes. Optional research failure does not restamp canonical bytes. A prior
receipt may then exist but cannot bind the new record. Publisher validates
self-integrity, allows this old binding, verifies the referenced bundle, and
excludes the retention index/unreferenced cohorts from the required public-byte
verification inventory. Git/Pages archive paths remain public; only the lazy
UI controls initial fetching. UI cannot promote/copy research orders.
