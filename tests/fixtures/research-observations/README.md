# Dated research observation controls

Every file is what `src.research_observations.collect` writes for a pinned
clock over a stop-research fixture, answered by a synthetic IEX snapshot
double (`generate.py`'s `Client`). No provider was called; the prices are
fixed prints chosen to sit under KE's trigger and inside PSNL's band. They are
not market observations and establish nothing about either stock.

The source publication, cohort receipt and bundle are read in place from
`tests/fixtures/stop-research/`: `current` is the immutable production
capture (measured October 9, applicable October 12, 2026; decompressed
SHA-256 `f5cbe38e…`), `red` and `outside` are production-shaped offline
controls. The browser suite serves those same files beside these observations.

The pinned clock is 13:20 UTC on October 12 (8:20 Chicago), the first
scheduled morning slot, inside the half-hour collection window before the
9:30 ET open. `generate.py --check` re-derives all twenty-four files.

- `observed`: both allocation-fit rows (KE, PSNL) observed on one IEX request.
- `partial`: PSNL's print is a minute old (stale), KE's quote is crossed (invalid).
- `outage`: the IEX request failed; one request, no price, provider unavailable.
- `no-credentials`: no Alpaca pair configured; zero requests, provider unavailable.
- `before-window`, `expired`, `wrong-session`: the morning guards; zero requests.
- `no-rows`: the red cohort has no allocation fit; zero requests.
- `outside`: the September cohort is outside the registered period; zero requests.
- `missing-cohort`: no cohort receipt beside the record; zero requests.
- `stale-cohort`: the red cohort beside the current publication is not bound; zero requests.
- `followup`: a second observation thirty seconds after `observed`, bound to its bytes.

- `age-60s`, `age-60s-plus-microsecond`: KE's quote and trade are exactly 60
  seconds old (recent) or 60.000001 seconds old (stale) at collection.
- `future-5s`, `future-5s-plus-microsecond`: KE's quote and trade are exactly
  five seconds ahead (recent) or 5.000001 seconds ahead (invalid).
- The four corresponding `-offset` files retain the same print instants with a
  `+05:30` offset. All eight use a collection clock retaining `.123456` seconds.
- `locked-zero-spread`: a legitimate locked quote has zero dollar and percentage
  spread and stays readable.
- `midpoint-underflow`: a positive subnormal locked quote underflows its midpoint
  to zero; the producer records it invalid with null spreads, never a price signal.
- `rounded-spread-tie`: the percentage lands on an eight-decimal rounding tie;
  the valid producer result remains readable despite binary representation error.
- `large-dollar-spread`: the numeric price limit still roundtrips its exact
  spread; an adjacent representable dollar value is refused by browser replay.
