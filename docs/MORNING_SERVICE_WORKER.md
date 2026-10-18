# Bounded private morning worker

The trusted scheduler can run one production collection tick with:

```sh
python -m src.morning_service_worker --database /srv/spicystock/morning.sqlite
```

Use the prepared store described in [the service contract](operations/morning-service.md),
a single host, and one durable local SQLite volume shared by all worker processes.
The canonical publication must already be ingested through the trusted handoff.
The database must survive restarts; deleting it to reset a budget is prohibited.
This command is never invoked by HTTP, a browser refresh, or an arbitrary ticker.
It accepts no source URL, ticker, simulated clock, dry-run, or retry option.

The existing `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` belong in the worker's
server environment. They are never put into the database, receipt or command
output. Missing credentials produce the existing explicit unavailable feed
status; public Nasdaq evidence may still be collected. No new environment
variable, provider entitlement or paid account is implied.

The supervisor reserves one fenced collection using the production session,
window, publication and account-independent observation rules. It starts a fresh
child process and allows at most 25 seconds, shortened to the current cutoff or
lease expiration. The child calls the actual `morning.collect`, using the exact
stored canonical and prior receipt bytes, `dry_run=False`, the real Alpaca SDK,
and `morning_halts.observe(fetcher=...)`. The supervisor alone validates and
commits the result. A timeout terminates and reaps the child before releasing
its lease; failed work never refunds a reservation. No late output is committed.
A child that the operating system cannot reap leaves its lease occupied for
operator investigation.

Each actual source attempt is charged atomically in the same database before
transport. Its generation, fence, exact lease, prior receipt and production
window must still be current. Checks before requests and while consuming bodies
stop further source work after a deadline or superseded publication. A request
already in flight cannot be recalled; its late result cannot commit. The parent
process bounds DNS, connection, read inactivity and drip-feed hangs together.

| Source | Minimum interval | Maximum attempts per UTC day |
| --- | ---: | ---: |
| Alpaca IEX snapshots | 30 seconds | 120 |
| Alpaca delayed SIP snapshots | 30 seconds | 120 |
| Nasdaq current-halts RSS | 60 seconds | 60 |

Attempts remain charged after errors, process termination and restarts. The
provider policy is pinned in storage. There are no SDK, HTTP adapter or worker
retries. HTTP 401 quarantines both Alpaca feeds until the next UTC day; HTTP 403
quarantines the rejected feed until the next UTC day. Nasdaq authentication
refusals affect Nasdaq only. HTTP 429 waits at least five minutes, respects a
bounded Retry-After interval/date up to one day, and persists across restarts.
Local interval, budget and backoff refusals carry explicit local reason codes,
not a newly observed HTTP status. The original response status and completion
time remain in the durable ledger. Other source failures wait at least one
minute. Successful later requests do
not bypass another feed's authentication quarantine.

The only allowed endpoints are the Alpaca `/v2/stocks/snapshots` path with the
exact admitted symbol list and IEX/delayed-SIP feed, and the fixed Nasdaq RSS
URL. Pagination and redirects are refused. Responses use three-second connect
and four-second read-inactivity timeouts within the process deadline. Alpaca
response bodies are bounded to 2 MiB and Nasdaq bodies to its existing 1,000,000
byte cap. Redirect bodies are not buffered by Requests. No order endpoint exists.

A valid Nasdaq response is cached durably with its original bytes, fetch time
and HTTP date. Workers within the one-minute floor reuse those dated bytes,
including across restarts. During a source backoff, a retained cache can still
expose its original age; stale evidence remains stale and absence never clears
a halt. Invalid RSS does not enter the cache. Existing known halt and corporate
restrictions continue through the unchanged collector and commit validator.

Console output contains only a fixed mode/result summary. Receipts travel from
child to supervisor through a private temporary directory with bounded reads,
not stdout. Operational errors omit raw provider responses, credentials and
exception details. The browser continues reading committed public receipts;
it cannot initiate a collection or alter the account, market or event gates.

The local automated tests use synthetic publications, historical clocks and
HTTP doubles beneath the actual SDK; process tests exercise spawning and forced
termination. They establish software behavior, not live prices, provider
permission, host availability, timely delivery, fills or profits. Deployment
still needs the identified host, durable storage, server-side credential
bindings, scheduler, trusted publication synchronization, TLS route, explicit
browser endpoint and measured on-time session validation. Comprehensive current
issuer news and earnings remain separately unverified.
