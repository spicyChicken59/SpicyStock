# Frozen research follow-through, version 1

`anticipation_stop_width_follow_through_v1` follows the immutable
`anticipation_stop_width_4_to_5_v1` cohorts. It does not create orders, change
selection, obtain prices, or read personal browser reports. Each result is a
conditional daily-bar model with unspecified actual costs and slippage, not a
personal execution or portfolio return.

## API and transport

`build(canonical_raw, cohorts=[exact_bundle_bytes], objects=source_directory,
previous=None, publications=None, generated_at=None, allow_fixture=False)`
returns `receipt`, `receipt_bytes`, `bundle`, `bundle_bytes`. `previous`, when
supplied, is `(receipt_bytes, bundle_bytes)`. `publications` is an optional
callable taking an original canonical SHA and returning exact local bytes or
None; originals are processed one at a time. It performs no retrieval itself.
The current publication supplies its own origin. A previously validated
journal can retain a compact original basis/rule/anchor seed. An old cohort
without either original source is explicitly unavailable.

`parse_receipt(raw)` and `validate_bundle(receipt_raw, bundle_raw)` are strict
standard-library self-integrity validators. `validate_for_publication` takes
the same derivation arguments and verifies exact replay. Self-integrity is
not a signature or independent verification of source truth.

`write_publication(canonical_raw, docs, objects=..., picks=None, ...)` reads
the bounded existing stop-research index and journal. `picks` is accepted for
hook compatibility and does not select or size research. The hook runs after
the stop-research attempt, including when that optional update is refused.
An optional failure preserves the previous receipt and all original data.

The fixed receipt `research-outcomes.json` is at most 16 KiB. Its `bundle`
descriptor is exactly `{path, sha256, bytes}` and references
`research-outcomes/<64 lowercase hex>.json`, at most 2 MiB. Hashes cover exact
UTF-8 bytes. Duplicate keys, unknown fields and nonfinite JSON are refused.
Both objects share exactly:

- `schema_version`: 1; `policy`: exact supported module `POLICY`.
- `publication`: the existing nine-field canonical/reader binding, identifying
  the **observation publication**, not any older cohort's original publication.
- `generated_at`: actual aware producer clock; never a substituted run start.
- `cohort_set_sha256`: SHA-256 of sorted-key compact JSON of the ordered
  original cohort SHA list; no typed float serialization is involved.
- `counts`: `cohorts`, `primary_cohorts`, `rows`, `eligible`, and `by_status`,
  containing every supported row status, including zero counts.

The bundle additionally has `cohorts` and `limits` (the exact module list).
Each cohort is exactly `{source, primary, revision, origin, rows}`:

- `source`: `{sha256, bytes, raw}`. `raw` is the exact original UTF-8 bundle
  string; encoding it as UTF-8 reproduces its byte hash. The original bundle
  retains every original refusal, research quantity, geometry and reservation.
- `primary`: true only for the first `before_entry` capture for that applicable
  session. Ordering is actual original generation time, then SHA. A session
  with only during/after-entry cohorts has no primary. `revision` is its
  one-based generation order within the applicable session, including late
  cohorts. No revision replaces another cohort.
- `origin`: null, or `{basis, replay_rules, anchors}`. Basis contains exactly
  provider/feed/adjustment/timeframe. Replay rules are the supported subset
  used by fill/follow/R and the calendar. Unrelated strategy-rule changes do
  not invalidate replay. Anchors are keyed by original evidence ID, each
  `{date, close, source_sha256}` verified against the original retained frame.
- `rows`: in the original rank order, exactly `{rank, ticker, evidence_id,
  observation, model}`. Only original `research.allocation_fit` rows are
  replayed, using their frozen research shares, not the refused baseline size.

`observation` is null or exactly `{publication, basis, anchor, bars,
bars_sha256, carried, revision_of, changed_dates}`. Bars contain exactly
`{date,o,h,l,c,v,from_session}` and at most five sessions. The bar digest is
SHA-256 of sorted-key compact JSON encoded by the producer; browsers treat it
as an opaque evidence identity and verify the enclosing raw bundle bytes.
`revision_of` is the prior bar digest or null; `changed_dates` compares full
OHLCV values, not the legacy close-only revision flag. Carried evidence keeps
its original publication, basis and dates; it never becomes freshly observed.

`model` is exactly `{status, reason, day, sessions, entry, original_shares,
sold_shares, remaining_shares, current_stop, events, r, uncertainty,
expected_sessions, missing_sessions}`. Status is one of `pending`, `missing`,
`uncertain`, `not_filled`, `open`, `resolved`, `excluded`, `origin_unavailable`,
`basis_conflict`, `unsupported`, `unreadable`. Unknown numeric facts are null.
`reason` is a bounded explanatory string, never an order instruction. Events
are the bounded original replay events with their date, model event, price
and optional whole shares/remaining. R is null except for a reconciled resolved
model. No aggregate R, win rate, broker cash or portfolio result is produced.

## Observation and replay rules

Expected sessions are the five XNYS sessions after the original measured
session, through the observation publication's measured completed session.
The containing publication must be at or after scheduled completion; a later
producer wall clock cannot manufacture another completed observation session.
Zero expected sessions means pending; an expected missing session means
missing. A conclusive earlier result remains readable if later sessions are
absent, with its original evidence date.

Fresh evaluation requires matching original/current provider, feed,
adjustment and daily timeframe; a matching original signal-date close anchor;
and every consumed history bar and anchor freshly attributed via `from_session`
to that observation publication. Mixed/unknown carried bases are refused.
The original anchor retains its raw float64 close and source hash. Comparison
uses exactly the pipeline's public-series `round(float(close), 4)` conversion,
pinned as `policy.observation_price_decimals = 4`, not an arbitrary tolerance.
A prior evaluated clip may remain dated evidence when current coverage is
missing, but cannot override a conflicting new basis or changed anchor.

The existing `record.replay` and `record.r_multiple` define fill uncertainty,
contiguous sessions, stop-first daily-bar assumptions, whole-share exits and
five-session maximum. An open inside the trigger/limit is the model's known
fill. Later crossings do not establish the first thirty minutes or ordering.
Model instruction strings are omitted. Full OHLC revisions yield new dated
snapshots; the original snapshot is never rewritten.

## Bounds and retention

At most 128 source cohorts / 640 original rows are evaluated. Source cohort
bytes total at most 16 MiB; original canonical reads total at most 128 MiB,
one at a time; a run has a 60-second processing deadline. The existing source
frame bound applies to anchors. One snapshot is at most 2 MiB; at most 128
snapshots / 64 MiB are retained. The append-only retention index is at most
64 KiB. The same observation canonical SHA and ordered cohort set preserve
their first snapshot and generation time, including revisits. A changed
source/cohort set appends. Unknown files, symlinks, malformed prior artifacts,
untracked capacity or exhausted limits refuse a write; nothing is pruned.
The latest receipt is installed last. All archive paths are public; laziness
controls initial requests, not privacy. Publisher verification covers the
latest receipt and referenced bundle; the UI refuses a different publication
binding and makes no implicit requests for old cohorts or ticker data.
