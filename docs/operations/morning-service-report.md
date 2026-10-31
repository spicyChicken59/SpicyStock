# Morning service observations

The prepared service keeps a bounded operational journal in its existing SQLite
database. It records source ingestion, collection reservations and completion,
and provider attempt reservations and responses. Each event retains its source
identity and writer timestamp. Exact source and committed receipt bytes are
deduplicated by digest so a later report can inspect the observations that were
available at that point.

This journal measures the private worker and its stored receipts. It does not
observe the public HTTPS route, browser arrival, Fidelity orders or actual
trading results. An HTTP 200 from a provider establishes a transport response;
the receipt's coverage and quote timestamps still determine what was observed.

## Capture and retention

The first trusted writer opening an uninstrumented prepared database creates
an empty journal. Later upgrades preserve it; read-only reports do not create
or migrate it. Earlier receipts and counters are not reconstructed as past
operational success. Capture begins with the first recorded writer event.
Replay data stays separate from live service evidence.

Provider reservation evidence is committed in the same transaction as its quota
charge, before transport. A process interrupted after reservation can leave an
attempt without a known response. A receipt becomes a recorded completion only
after the existing publication, prior-receipt and lease checks accept it.
Recording history does not reset request limits, backoff or fencing.

On each append, oldest events are pruned to 45 calendar days, 20,000 events and
1 GiB of logical event/blob payload, whichever removes evidence first. An idle
database can retain older history; read-only reports never prune it. These are
retention ceilings, not a guarantee of 45 complete days or a bound on SQLite's
physical file size and overhead. Pruning removes unreferenced blobs and records
that history was lost. Export needed observations before they leave the
retained window; preserve the database and its journal during upgrades.

Ticks that do no work outside the collection window are not heartbeat events.
An absent receipt means no receipt was observed in the retained evidence; it
does not diagnose a stopped scheduler or a failed provider. Before capture
began, after pruning, or in a legacy database, missing evidence remains unknown.

## Deterministic read-only report

Run the report against the service database with explicit dates and an
offset-aware observation cutoff. For example, this reads the stated historical
window without collecting anything:

```sh
python -m src.morning_service_report \
  --database /srv/spicystock/morning.sqlite \
  --start 2026-10-12 --end 2026-10-16 \
  --as-of 2026-10-18T16:00:00Z
```

The command reads a consistent, bounded snapshot and prints JSON. It opens the
database read-only, needs no credentials and makes no network request. Identical
retained input and valid arguments produce the same report. The CLI refuses an
as-of cutoff later than the actual UTC clock. The internal deterministic builder
uses the caller's explicit cutoff for historical/fixture work; callers must not
present a future cutoff as an observed result. The requested range is
limited to 62 calendar days; journal retention may cover less. A report that
exceeds 256 MiB of selected payload or 8 MiB of encoded JSON output is refused
instead of silently dropping observations.
The selected payload includes each publication's whole canonical bytes. These
bounds were sized when a record was at most 32 MiB; the record may be 48 MiB
since 25 October 2026, and the design point the 22 October scan-ready
population makes is 46,640,227 bytes. At that size five publications fit the
256 MiB a report may read and at most 23 the 1 GiB the journal keeps (the
publications alone; their receipts and events share the same 1 GiB), short of
its 45 days; at today's sizes (10 to 19 MB) many more fit both. Revisit both before
the service runs across a thrust stretch.
The as-of cutoff filters the writer's recorded time, so an older provider
timestamp cannot admit an event written after that cutoff.

The report uses the existing XNYS calendar and Chicago session times. It keeps
not-yet-due, missing, late and pre-open receipt observations distinct, reports
source revisions, and separates a no-ticket morning from feed coverage. The
receipt's generated time and the time it was committed are separate: generating
before the open does not establish availability before the open. Provider
attempt counts are charged reservations, with known responses listed separately;
they do not establish a monetary bill.

The first retained receipt is not necessarily the first receipt produced. If
earlier history is unavailable, a retained post-open receipt cannot establish
that the first delivery was late. A retained pre-open receipt still establishes
that at least one local receipt was available before the open; missing earlier
history and the exact first-arrival time remain explicit.

The report never supplies order authority or an overall live-service acceptance
verdict. Public delivery remains unobserved, and a successful collection with
zero tickets is not fresh quote coverage. Keep this report beside independently
observed HTTPS arrival/expiry, publication delivery and actual cost evidence.
Ten consecutive expected sessions are still a future operating validation,
including valid no-ticket mornings and any observed failures.

See [deployment and bring-up](morning-deployment.md) for process separation,
provider bindings, scheduling and the browser endpoint, which names the Railway
service deployed on 31 October 2026 ([the Railway runbook](morning-railway.md)).
