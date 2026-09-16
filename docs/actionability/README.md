# Burst actionability and chart-source contract

Baseline: `964316f30a81035abf4dd5bd4be3ffbb2520a2fe` (merge #72).
This is browser presentation only. Discovery/source mapping, grades, ticket
permission, calendar, provenance v1 and runtime rules are unchanged.

## Recorded action

`buildModel()` still owns per-setup status; `availability()` and `copyGuard()`
still own publication/timing permission. The Burst summary precedes the chart.
It prints `order_json.stop_price`, `limit_price`, `then.stop_price`, and
`quantity`, and `run.timing.applicable_session`. Copy uses the same `ticket()`
formatter and immediate clock guard as the existing plan disclosure. No quote,
trigger detection, market order, sizing calculation or order submission is added.

No-ticket summaries print the adapter's existing reason, without synthetic
levels. A recorded but expired/stale ticket is inspectable in Plan details,
which begins with its refusal. Its summary has no current levels/copy control.
The existing degraded-publication policy is preserved: a degraded state that
already permits a recorded ticket is not reclassified by this milestone.

## Authentic chart sources

| Source | Use |
| --- | --- |
| Candidate `series` | First choice, no additional request. Producer still keeps 120 bars for trades, cuts, closest miss and top 24 Bursts. |
| Saved Following evidence | Frozen original bars/anchors; no substitution from this run or a newer observation. |
| History recovery | Existing source-addressed archived record, selected explicitly; absent original bars stay absent. |
| Provenance-v1 source object | Explicit **Load recorded chart** on a current Burst detail or open Compare panel with no ordinary series and a matching receipt. |

`provenance.source_object()` retains the consumed source frame's dates and
float64 OHLCV values; its source reference separately hashes the scanner and
quality readers' normalized views. `write_objects()` writes
`docs/evidence/<source.sha256>.json.gz`. Branch-based Pages serves `main /docs`;
these are ordinary static files, retained independently of rotating history.
The existing public `.nojekyll` and `app-chart.js` URLs returned HTTP 200 during
this milestone; `.nojekyll` preserves the static directory. There is no live
provenance-enabled market snapshot to test a production object against yet.
No authenticated endpoint, provider, deployment or new publication format is needed.
The baseline committed market snapshot has **342 Bursts, 25 browser charts and
zero provenance source references**. This change cannot retroactively recover
its missing charts. The recovery path is verified with authentic committed
pipeline-generated provenance fixtures, not a live new publication.

`SCStock.loadSourceChart()` in `app.js` checks receipt/run version, kind,
ticker, session, rules/context identity, source hash format, row count and
evaluated/previous sessions. It hashes the parsed frame using provenance v1's
typed JSON and exact Python-compatible float64 hexadecimal encoding. Plain JSON
bytes have a different digest; floats that look like integers remain floats.
Frame schema, strictly increasing real date labels, column lengths, and finite
numbers/null gaps are checked before use. Nulls stay gaps. Only the last 120
exact source rows become chart input; no price normalization or strategy runs.
This authenticates that object against the published receipt, not the entire
decision chain or the publisher. The offline provenance verifier remains the
authority for a complete replay.

The reader permits only the fixed same-origin hash path, omits credentials and
referrers, refuses redirects, and times out network reads after 12 seconds.
Compressed and expanded input are each bounded at 256 KiB. A host that already
decodes HTTP gzip works too. Missing browser crypto/decompression support fails
visibly without a provider fallback. APIs: [DecompressionStream](https://developer.mozilla.org/en-US/docs/Web/API/DecompressionStream)
and [Web Crypto digest](https://developer.mozilla.org/en-US/docs/Web/API/SubtleCrypto/digest).

Initial evidence requests: **0**. First explicit load: **1** source request;
repeat selection: **0** additional requests. A page-memory cache deduplicates
in-flight/successful objects (64 identities); failures can be retried. Loaded
candidate chart arrays last for that page's record, with no public or local
history rewrite. A disposed panel cannot accept a late response. Save-before-load
keeps its original missing chart; a subsequent new save may capture verified bars.
No new script request, dependency, published series, or retained source bytes.

## Evidence focus and composition

Selecting Base/Burst/Prior still highlights without moving scales. Explicit
focus frames the selected dates with context, keeping at least 21 recorded
observations where available. A base gets at least eight surrounding observations
where retained. Restore returns to the prior Setup/60/120 preference. Focus never
writes that preference; normal range selection or leaving the panel ends it.
A focus range before the signal cannot relabel its last candle as the burst.

Chart heights stay 400/300px; labels, gutters and touch controls remain intact.
The desktop's first viewport now prioritizes the recorded entry decision and
four values; the full chart follows. Screenshot evidence covers 1280/390/320px,
both themes, ticket/no-ticket and focused/restored charts. No personal execution,
broker integration, outcome scoreboard or strategy changes belong to this work.

[Measured payload/request impact and immutability checks](measurements.json)
record the before/after sizes and offline request counts.
