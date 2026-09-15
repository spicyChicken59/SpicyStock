# Saved research continuity

This branch extends the existing Following store and detail sheet. It does not
change strategy numbers, grades, model picks, scorecard denominators, credentials,
or the fetched universe. Published data.json and picks.json remain untouched by
this implementation session.

Today’s scan and My setups are peer destinations. The former's "Saved in this
scan" lens is narrower than the latter. All saved signals survive scan/filter
changes. Original status, signal date, publication identity, saved time and
optional annotation timestamps have distinct meanings. A new same-ticker signal
or a different published revision does not replace a saved original.

Store schema 3 uses the existing `spicystock:following:v1` key (and existing demo
key). Suggested shares and reference shares stay whole-share research fields.
USD is stored explicitly with integer minor units; blank is unknown. All public
mutators return Promises, serialized by origin-wide Web Locks. Each operation
rereads inside the lock; conflicting field edits follow acquisition order. A
stale edit cannot recreate a removed item. Browsers without Web Locks retain
read access and receive an explicit write refusal. v1/v2 backups and unknown
fields survive migration. A failed write/readback retains the input and attempts
to restore the previous payload; a browser-local recovery download preserves
both proposed and prior data if storage remains unusable. No recovery copy is
sent anywhere automatically.

The recovery catalog is built from real published Git records, never picks or
personal saves. `sources.json` identifies all three recovered publications. The
September 11 data blob required by the mission is included. An earlier September
11 publication was also inspected; neither contains VICR's original chart.
No Git history exists for docs/charts/VICR.png. Actions artifact metadata was
accessible, but binary artifacts were not inspected in this execution. The
absence claim is limited to the inspected archived records.

The public window is 21 calendar days from each signal date (existing inclusive
boundary retained). Same-ticker signals have separate windows. Up to 20 real dated
observations are carried per symbol, using already-fetched frames. Missing frames
retain the last real bar with its date/source; gaps are never filled. Historical
revisions and adjustment cautions remain. No extra original charts are captured
beyond each publication's existing series (at most 120 bars).

Limits: 84 publications; 10,000 signals per publication; 256 KiB per lazy file;
128 MiB catalog. A bound violation refuses publication of a new index, retaining
the old one. Expiration prunes only catalog-owned source files. Local saves do
not expire. Backfill currently covers September 11 and 14, with two September 11
revisions. Search loads one index; inspection loads context and one original.
Measurements and their replay limitations are in `measurements.json`.

Reusable patterns for later coordinated design promotion: peer research/saved
destinations; precise original/latest labels; optional currency annotation with
explicit unknown state; a local-persistence disclosure; and honest missing-chart
and observation-coverage states. Existing v2.13.0 tokens/components are reused;
no shared or vendored design assets were edited.

Verification: `npm ci && npm run test:continuity` exercises actual DOM controls
and store code offline. JSDOM is explicitly not a real browser or a layout test.
`tests/test_history.py` exercises source hashes, coverage, bounds, revisions,
retention and unchanged provider/chart-reader call counts. Existing Playwright
commands remain required for desktop, 390/320px, both themes, keyboard and focus.
They are blocked here because Chromium is unavailable and its download times out.

The existing generic-api-key exception for lowercase underscored rule identifiers
now includes only the source-addressed recovery JSON paths. The value regex,
AND condition, default detectors and historical fingerprints are unchanged.
The new originals contain the same published rule-key values as data.json.
No gitleaks execution is claimed in this environment (binary unavailable).
