# Issuer evidence transport, version 1

This SEC-only reader lists dated source documents. Collection is not a news
clearance, an event classification, an earnings-calendar check, or entry
authority. Reviewed unresolved events remain separate from fetched filings.

The fixed `issuer-evidence.json` receipt is at most 64 KiB. It references one
immutable `issuer-evidence/<lowercase-sha256>.json` bundle of at most 2 MiB.
Both files use UTF-8 JSON. Consumers hash the original bundle bytes. A valid
receipt for a previous publication may remain on the site; the browser must
decline to attach it to a different publication. Source clocks never rewrite
the immutable publication.

## Public Python API

`parse_receipt(raw)` returns a strictly validated receipt. It is stdlib-only.
`validate_bundle(receipt_raw, bundle_raw)` validates self-integrity, paths,
bounds, clocks and relationships and returns the bundle. It is stdlib-only
and does not require the current canonical record.
`validate_for_publication(canonical_raw, receipt_raw, bundle_raw)` additionally
checks exact canonical/derived-reader and candidate identities. Collection
also verifies production provenance using the existing morning binder.

`collect(canonical_raw, *, fetch=None, now=None, finished_at=None, run_id,
dry_run=True, previous_raw=None, allow_fixture=False, cache_dir=None)` returns
`receipt`, `receipt_bytes`, `bundle`, `bundle_bytes`, and `captures` (raw SHA
to original response bytes). A fake `fetch(url)` returns `body` bytes and an
offset-aware `observed_at` datetime or ISO timestamp, or raises
`SourceError(code, http_status=...)` for an observed HTTP refusal or
`SourceError(code)` when no HTTP status is known. Optional `fetched_at` and `cache_status` distinguish a
verified cache body from the current check. Supplying `now` pins start/as-of;
completion defaults to that instant unless `finished_at` is supplied. Real
collection records actual completion. Parser APIs are
`parse_mapping(raw, ticker)`, `parse_submissions(raw, cik, ticker, as_of)`,
and `parse_primary(raw, url)`.

## Receipt

All keys below are required; unknown keys are rejected.

```text
schema_version: 1
status: collected | partial | unavailable | no_candidates | inapplicable
dry_run: boolean
collection_run_id: nonempty string
collection_started_at, generated_at, expires_at: offset-aware ISO instants
publication: complete morning binding including reader_projection_version=1
             and reader_sha256; no legacy partial binding
previous_receipt_sha256: lowercase SHA-256 or null
policy: exact versioned collector limits
selection: {candidate_count, issuer_count, selected_issuer_count,
            omitted_issuer_count, selected_tickers: [ticker]}
bundle: {sha256, bytes, path: "issuer-evidence/<sha256>.json"}
coverage: {
  issuer_news: {status: "not_cleared", reason: fixed explanatory text},
  earnings: {status: "not_checked", reason: fixed explanatory text}
}
```

Expiry is 24 hours after completion and concerns this receipt's age only.
Source cache age and individual retrieval times remain visible. Freshness
never resolves an event or proves that SEC dissemination has caught up.

## Bundle

Required keys: `schema_version`, `publication`, `collection_started_at`,
`generated_at`, `as_of`, `window_start`, `candidates`, `issuers`, `stats`.
The first four repeat the receipt. `as_of` is the fixed collection start;
`window_start` is its UTC date minus 365 days. Requests crossing midnight do
not change the window.

Every relevant bound candidate remains in `candidates`, even if it exceeds
the eight-issuer fetch cap. Candidate keys:

```text
ticker, kind (burst | anticipation), evidence_id, plan_sha256
admission: admitted | known_event_excluded
selected: boolean
anchors: original archived plan.event_risk.matches objects, unchanged
```

Anchors are reviewed facts from this publication, including their source
links and dates. Their absence from recent filings, collection failure or
review-date expiry cannot clear them. A candidate omitted by the fetch cap
still displays its anchors and the omission.

Each selected `issuers` row has these keys:

```text
ticker
status: collected | partial | unavailable | identity_unverified
reason: string or null
identity: {status: verified | unverified, cik: positive integer or null,
           name: string or null, mapping_source: source or null,
           submissions_source: source or null}
index: {window_start, window_end, coverage_status: observed_window | partial | unknown,
        reason: string or null, range_start: date or null, range_end: date or null,
        metadata_count, eligible_current_report_count, not_selected_count,
        history_files_advertised, history_files_fetched, history_sources: [source],
        selected_accessions: [accession], listed_filings: [filing]}
documents: [document]
errors: [{code, source_url: HTTPS SEC URL or null,
          http_status?: integer 300..599, source_phase?: mapping | submissions | history | primary | exhibit}]
```

The HTTP fields are an optional pair. Both are absent on legacy errors or when
no HTTP response status was observed; absence is unknown, never inferred from
a timeout, cache result or error message. Present status must be a real integer
(not a boolean), with `redirect_refused` for 3xx, `rate_limit` for 429 and
`http_error` for other 4xx/5xx. The collector supplies the phase and original
requested URL; neither comes from a response body, header or redirect target.
Mapping uses the one fixed mapping URL. Submissions and history use the current
issuer CIK. Primary documents exactly match a selected filing; exhibits remain
under that selected accession, use a safe HTML filename and cannot be its primary
document. Error bodies, exception text and headers are never read or retained.
This diagnostic does not change source coverage, clearance, budgets, caching,
retry behavior or redirect refusal. Existing two-field errors remain valid and
are not rewritten.

A `source` is `{url, raw_sha256, bytes, fetched_at, checked_at, cache_status}`;
cache status is `network` or `verified_cache`. A `filing` is
`{accession, form, filing_date, report_date, accepted_at, primary_document, items}`.
An empty report date becomes null. An invalid, naive or future acceptance
timestamp is rejected, not clamped. Acceptance is availability metadata,
not the event date or issuer release date.
An acceptance beyond this check's fixed as-of tolerance is omitted and makes
metadata coverage partial, even if a legitimate new filing appeared while
the request was in flight. The next attempt can include it; no clock is
clamped or rewritten to make it fit this check.
For a cache hit, `checked_at` remains the last successful network retrieval
time, equal to `fetched_at`; a local digest check never impersonates a new
SEC source check.

A `document` is `{accession, form, role, source, filing_date, report_date,
accepted_at, release_date, excerpt}`. Role is `primary` or `exhibit`.
`release_date` is null in this first slice: extracting an article date would
need an independently tested source-specific rule. An `excerpt` is
`{text, normalization: "html_text_v1", start: 0, characters,
normalized_characters, truncated, sha256}`. Its SHA hashes the displayed
UTF-8 text; `source.raw_sha256` hashes the original HTTP body. Text is inert,
HTML scripts/styles are excluded, whitespace is collapsed, and at most
16 KiB of UTF-8 text is retained. Truncation is explicit. Fetching an entire
body does not claim its complete content was reviewed.

The index also includes `exhibit_links_observed` and `exhibit_links_not_fetched`.
History sources record their own URL, body digest and fetch/check clocks.
`stats` is `{request_count, downloaded_bytes, capture_bytes, budget_stop}`.
Capture bytes count distinct retained response bodies, including cache hits,
and are bounded separately at 32 MiB. Exceeding that limit refuses the new
source before displaying it and reports partial `size_limit`; cache hits do
not fabricate network request/download counts. Budget stop is
null or a source error code. Source error codes are `rate_limit`, `http_error`,
`timeout`, `network_error`, `redirect_refused`, `size_limit`, `request_budget`,
`time_budget`, `invalid_response`, `identity_unverified`, `metadata_invalid`,
`document_invalid`, and `history_incomplete`.

## Selection and limits

Select admitted candidates first, then current known-event-excluded candidates,
deduplicating tickers in that order. Preserve every candidate and anchor.
Read the trailing-year index, not a claim of a trailing-year content screen.
Latest three 8-K/6-K reports and amendments may be fetched, with up to two
same-accession HTML exhibits each. At most one advertised overlapping history
file per issuer is fetched. Duplicate accessions must agree. Short index
coverage, missing/exhausted history, invalid metadata, unfetched reports and
excerpts are explicitly incomplete. A young issuer's index does not prove a
full year of history. SEC mapping has no completeness guarantee.

Maximums: eight issuers; 128 relevant candidates; 2,000 metadata rows per
recent/history response; 12 listed metadata rows per issuer; 96 requests
including retries; 2 MiB per response; 32 MiB downloaded per run; four minutes
per collection; one request per second. Future-clock tolerance is five seconds.
The network adapter runs in the main thread of Linux Actions and uses an
absolute POSIX request alarm in addition to read1/socket deadlines. This also
interrupts slow HTTP headers and chunk headers. Network work stops five seconds
before the collection ceiling to leave bounded receipt-finalization time.
Production streaming stops at the aggregate ceiling. An injected complete
response may exceed it by one response; that refusal reports the actual bytes
and requires `budget_stop: "size_limit"`, rather than silently clamping a count.
Responses are fetched from fixed SEC HTTPS hosts, without redirects, arbitrary
query URLs or browser/provider credentials. Primary basenames and exhibit
links must remain under the verified issuer CIK and accession path; filing-agent
accession prefixes do not establish issuer identity. No new IR transport is
included. Reviewed IR anchor links remain readable.

Mapping may use a verified seven-day cache; submissions are checked on every
attempt; document caches last at most 24 hours. Cache bodies and metadata are
bounded and digest-validated. Raw downloads are retained in the Actions run
artifact for 30 days; this is not a permanent complete filing archive.
The cache holds at most 256 URL-hashed body/metadata pairs and 128 MiB total.
Expired valid pairs may be pruned only after all entries validate. Unknown,
orphan, symlinked or tampered files are preserved and disable cache reuse/save;
network collection can continue. `validate_cache(path, prune=True)` is the
stdlib save guard. Only trusted-main workflows may restore/save this cache.
