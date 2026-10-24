# Prepared morning receipt service

This adapter implements the durable collection/receipt boundary in issue #108.
It is prepared software, not an active quote service or evidence of timely
morning delivery. The [deployment handoff](morning-deployment.md) gives
concrete invocation cadences, process separation and bring-up checks. GitHub Pages and existing workflows are unchanged. Its tests
use explicitly synthetic retained publications and provider doubles.

`src.morning_service` supplies a **single-host SQLite store on durable local
storage**, an injectable scheduled collection operation, and a read-only WSGI
route. It is not a multi-region coordinator. All workers must share the same
local database; network filesystems, separate replica volumes and ephemeral
container filesystems do not satisfy its storage contract.

The trusted local ingestion command validates canonical bytes with the existing
production provenance, calendar and reader-binding code. Same-session byte
revisions advance a fencing generation. Publication replacement preserves the
previous validated receipt for halt/corporate-event continuity, while GET stays
unavailable until a receipt matches the replacement publication. Bootstrap may
supply a receipt validated against that exact publication, or a prior-publication
receipt whose independent halt/corporate facts pass the existing collector
continuity validator; later ingestion
cannot replace retained receipt history through that option.

Reservations use one SQLite write transaction, a monotonically increasing fence,
source generation, and the exact prior receipt. Default cadence is no more than
one reservation every 30 seconds, at most 120 reservations per UTC day, with a
180-second lease. A caller can choose stricter limits (maximum interval 3,600
seconds). Policy is pinned in the database, including across restarts; recreating
a database is not an allowed recovery procedure. Failed or abandoned attempts
spend their reservation. The next reservation can replace an expired lease,
and the old worker can neither commit nor release its replacement. Backwards
shared clocks are refused.

The scheduler uses the unchanged morning collector's session, collection-window,
cutoff and publication-freshness rules. A no-ticket collection remains useful
service evidence and the existing collector calls no providers for it. Commit
replays `tools.publish_morning.publication_check`, then atomically compares source,
prior receipt, generation and exact lease identity. It never restamps an old
receipt or changes a ticket. Lease expiration fences commits; **it does not kill
a hung transport or bound its provider calls**.

## Local commands

Install the repository requirements in the same Python environment as the
current collectors. Use an operator-owned directory outside `docs/` and a
persistent local filesystem. The command reads files only; it does not fetch
publications, poll GitHub, request provider data or publish the database.

```sh
python -m src.morning_service --database /srv/spicystock/morning.sqlite ingest \
  --publication docs/data.json
```

A first bootstrap can add `--previous /path/to/matching-morning.json`; that receipt
must pass production validation against the ingested publication when it matches;
a previous-publication receipt may seed independently validated restrictions only,
using the existing collector continuity validator. Without a matching receipt,
GET returns 503. A previous-publication receipt already in the
database survives later ingestion for continuity.

```sh
python -m src.morning_service --database /srv/spicystock/morning.sqlite serve \
  --port 8766
```

`serve` is a **loopback development server**, not production HTTP/TLS hosting.
A production WSGI server can load `application(database_path)`. The only route
is `GET /morning.json`; query strings, bodies and other methods are refused. All
clients receive the same public bytes. Reads open SQLite in read-only mode and
never initialize storage, collect, enqueue, or reserve a job. Responses use
`Cache-Control: no-store`, exact byte lengths, and digest ETags. An expired
receipt may still be served with its original timestamps; the browser's current
freshness rules remain authoritative. There is no stale timestamp extension.

For a configured cross-origin deployment, pass one exact HTTPS origin to
`application(database_path, allowed_origin="https://spicychicken59.github.io")`
or the development `--allowed-origin` option. Only matching Origin requests get
that exact CORS origin, never a wildcard or credentials permission. CORS is a
browser read policy, not authorization to collect. Same-origin reverse-proxy
routing needs no CORS option. No real service origin is configured here.

## Scheduler integration

The public Python boundary is:

```python
from src.morning_service import Store, collect_once

store = Store('/srv/spicystock/morning.sqlite')
result = collect_once(store, bounded_collector, clock=utc_clock)
```

`bounded_collector(canonical_raw, previous_raw=..., clock=...,
observation_run_id=...)` returns the existing `morning.collect` receipt shape.
There is deliberately **no implicit provider in this store**. The separately
implemented [bounded worker](../MORNING_SERVICE_WORKER.md) is the explicit live
integration entry point; it owns provider attempt quotas, retries, backoff, halt
cache and execution supervision. The store tests call
`morning.collect` with explicit provider/halt doubles and the production
validators; identical recorded inputs produce identical decisions.

A supervised worker can call `reserve(now=...)` itself to obtain a `Claim`, run
its bounded child, then `commit(claim, receipt_bytes, now=...)` or
`release(claim, now=...)`. The claim contains source and previous receipt bytes,
fence, generation, start and expiry. `request_transaction(claim, now=...)`
yields a transaction for a separate provider adapter's attempt/cache tables,
only while the exact prepared-mode claim remains current and the production
collection window is still open. Reserve an attempt in that transaction,
release the transaction, then perform the network request. This helper does not
spend a provider request or implement its adapter's limits itself.

The bounded worker must remain the only live provider path: bypassing its
attempt budgets, disabled retries, authentication/entitlement/429 backoff,
durable Nasdaq cache and process deadline invalidates those guarantees. Its
offline checks do not establish actual provider access or on-time delivery.
The existing SDK's retry/timeout settings cannot be connected unchanged and
called a 30-second guarantee. Public GET never accepts source URLs or symbols.

## Deterministic offline replay

```sh
python -m src.morning_service --database /tmp/spicystock-replay.sqlite replay \
  --publication tests/fixtures/morning/full-publication.json \
  --receipt tests/fixtures/morning/observed.json
```

This uses the retained receipt's original collection instants, outputs
`mode: offline_replay`, and creates a database permanently marked **replay**.
A replay database cannot be opened as a prepared service or served by the public
WSGI route. Replaying into an existing prepared database is refused. The command
performs no provider request and establishes no current recommendation, fill,
profit or live service timing.

Remaining deployment acceptance depends on the selected existing host, durable
volume and scheduler, TLS/service route, server-side source secrets and measured
provider entitlements/costs, the production browser's explicit endpoint config,
and actual expected-session delivery evidence. Broader issuer news/earnings
coverage remains separate. Ten expected live sessions cannot be inferred from
these deterministic implementation checks.

## Trusted publication synchronization

The separate fixed-repository handoff can ingest committed main directly:

```sh
python -m tools.sync_morning_service --database /srv/spicystock/morning.sqlite
```

It accepts only a local database path. The repository is fixed to
`spicyChicken59/SpicyStock`, ref `refs/heads/main`, source `docs/data.json` and
bootstrap companion `docs/morning.json`; public clients cannot choose a URL,
ref or symbol. It reads the small GitHub ref descriptor, then a bounded docs-directory metadata listing at
that exact immutable commit. The fixed `docs/data.json` entry is selected; a
directory listing never embeds canonical content, including for small files. The canonical bytes must match the reported Git
blob SHA-1 and length and pass existing SHA-256 publication/reader binding and
provenance validation. A matching stored blob skips the full download, even
when code-only main commits advance. A changed main ref at the final check
refuses ingestion. This establishes the source at that final observed instant,
not a promise that main cannot advance afterward. A concurrent local ingestion
is refused by an expected-generation compare-and-swap inside the store.

Each synchronization makes at most five read-only requests and has a 30-second
whole-response deadline with bounded headers and streamed bodies, decreasing
socket read timeouts, refused redirects and no retries or credentials. Ref descriptors are limited to 16 KiB and directory metadata to 256 KiB / 1,000
entries. The normal CLI runs synchronization in a spawned child with a 35-second
wall-clock cap, including startup, DNS, HTTP and local ingestion. It terminates
and joins a stalled child, escalating to kill if necessary; cleanup waits are
limited to two seconds each. The parent accepts at most 4 KiB of structured child
output. A timeout can coincide with an already completed atomic ingestion, so
it reports unknown completion rather than claiming a rollback. The next
synchronization rechecks committed source identity and deduplicates normally.
The canonical record it downloads may be 48 MiB (`reader.MAX_PUBLICATION_BYTES`,
32 MiB until 25 October 2026); carrying that inside the 30-second deadline needs
roughly 13 Mbit/s, which no deployed host has been measured at. A download that
misses the deadline is refused like any other timeout.

The SQLite poll ledger reserves the next allowed time before source requests.
Normally completed success/failure records include the request count; interrupted
completion can leave that count unknown while the poll floor remains durable.
Calls before 300 seconds elapse perform no source
requests. HTTP 403 and 429 use typed statuses and bounded backoff up to one hour;
no response body or credentials are logged. A bootstrap 404 means no published
morning receipt was available. Other failures or an invalid receipt refuse the
entire bootstrap, preserving the distinction between missing observations and
lost restrictions. An older receipt seeds independently validated event facts;
its quotes are not served as current publication authority.

The synchronizer creates no schedule or hosting resource. A selected host must
invoke it before and during the preparation window at an appropriate bounded
cadence, retain its ledger across restarts, and run the separately supervised
worker. The automated checks use synthetic transport responses. A separate
read-only check on 18 October 2026 ingested public main `88e708f2` into an isolated
local database in five requests, verifying the actual metadata and 10,404,000-byte
canonical transport. Its prior-publication receipt remained unavailable at the
GET route, and a repeat synchronization made zero requests. This establishes
that dated source handoff only; it is not a production deployment or a timely
morning quote check. The minimal receipt is retained in
[release evidence](../../release-evidence/2026-10-18-morning-source-sync/real-source.json).
