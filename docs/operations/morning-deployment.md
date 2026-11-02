# Single-host morning deployment handoff

This is the host contract for the service in
[morning-service.md](morning-service.md). The prepared
[Railway container and runbook](morning-railway.md) implement its process
separation and scheduler; they are not an installed schedule or an active
endpoint. Other hosts need durable local storage, a Python runtime, a production
WSGI server and TLS routing. Use one reviewed application revision and its
requirements for all three processes.

## Process separation and cadence

| Process | Invocation from the checkout | Scheduler target | Access |
| --- | --- | --- | --- |
| Publication synchronization | `python -m tools.sync_morning_service --database /srv/spicystock/morning.sqlite` | Every 300 seconds | Fixed public GitHub sources; write service database; no provider secrets |
| Bounded collection worker | `python -m src.morning_service_worker --database /srv/spicystock/morning.sqlite` | Every 30 seconds | Provider secrets; fixed Alpaca/Nasdaq sources; write service database |
| Public receipt reader | WSGI callable below | Continuously supervised | Read-only database access; no provider secrets or collection command |

These are invocation targets, not measured delivery guarantees. Run the timers
throughout the day; the existing exchange calendar, recorded collection window,
cutoff, quotas and backoffs decide whether any source work is permitted. Do not
replace those rules with an independently maintained holiday or fixed UTC
schedule. A worker tick outside the applicable window makes no provider request.
A zero-ticket session remains a valid service outcome.

Mount `/srv/spicystock` on persistent **local** storage shared by the trusted
writer processes and readable by the public process. Preserve the database and
all its ledgers through restarts and application upgrades. Never delete or copy
a replay database over it to reset a quota. Give the public process read access
only; it does not need write permission to the database or its directory.

Provide `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` only to the worker process through
the selected host's server-side secret mechanism. The synchronizer and WSGI
reader receive neither variable. No broker credentials, email credentials or
GitHub token are needed by these commands. Confirm the existing feed entitlement
and host costs before enabling the real worker.

For a host already using systemd, the following timer settings express the
cadence. They are examples to install and validate on that host, not repository
workflow changes:

```ini
# spicystock-sync.timer
[Timer]
OnBootSec=5s
OnUnitActiveSec=300s
AccuracySec=1s
RandomizedDelaySec=0
Unit=spicystock-sync.service

# spicystock-worker.timer
[Timer]
OnBootSec=45s
OnUnitActiveSec=30s
AccuracySec=1s
RandomizedDelaySec=0
Unit=spicystock-worker.service
```

Each corresponding service uses `Type=oneshot`, the checkout as its
`WorkingDirectory`, and the matching command above as `ExecStart`, using the
host's **absolute Python environment path**. Use `TimeoutStartSec=45s`,
`TimeoutStopSec=5s` and `KillMode=control-group` so a stopped service cannot leave
a child running. Add the host's provider secret binding only to
`spicystock-worker.service`; do not put it on a common target or the WSGI service.
The source and worker commands retain their tighter internal deadlines and
persistent budgets. Another scheduler must provide the same cadence and process
supervision; it must not start work from public HTTP requests.

## Read route and browser connection

Load this callable with the host's production WSGI server in a process separate
from both timers:

```python
from src.morning_service import application

app = application(
    '/srv/spicystock/morning.sqlite',
    allowed_origin='https://spicychicken59.github.io',
)
```

The exact allowed origin is the existing GitHub Pages browser origin, not the
new service origin. If the selected host provides same-origin routing, omit
`allowed_origin`. Bind the WSGI server behind the host's TLS route. Expose only
HTTPS `GET /morning.json`; preserve its `Cache-Control: no-store` and CORS
headers. There is no public refresh, ingest, worker or write route. The module's
`serve` command remains a loopback development server and is not a production
WSGI/TLS substitute.

After the real HTTPS route has been validated, set the existing
`spicystock-morning-endpoint` meta tag in `docs/index.html` to that exact HTTPS
URL ending in `/morning.json`, then use the normal reviewed Pages release. Keep
its value empty until a concrete route exists (it names the Railway route from
31 October 2026: [the Railway runbook](morning-railway.md) records what was read). It accepts no query, fragment,
user information or private account values. The browser's visible-window polling
reads receipts only and cannot trigger provider work. A failed dynamic read
remains unavailable; do not silently redirect it to an older static receipt.

## Bring-up and verification

1. Create the persistent directory and a new prepared database by running one
   trusted source synchronization. Check its typed result and source commit.
   An invalid bootstrap or denied source is a refusal to fix, not a reason to
   discard the previous receipt or event restrictions.
2. Run one bounded worker invocation with the actual clock and server-side
   provider bindings. Outside the collection window, an explained skip is
   expected. Do not change the clock or production gates to obtain a receipt.
3. Start the separate WSGI process and validate the TLS GET route. An older-bound
   bootstrap receipt correctly returns 503 until a receipt for the ingested
   publication exists. A served receipt must retain its original timestamps
   and exact publication identity. Confirm extra GET traffic causes no worker
   invocation or provider request.
4. Install the chosen scheduler's equivalent of the cadence above. Confirm
   restart preserves source polling, provider budgets, backoff and exclusions;
   keep replay/testing databases separate. Record actual resource usage.
5. Release the exact browser endpoint configuration and verify phone and desktop
   behavior, CORS, source changes, outages and visible expiry. Record actual
   pre-open arrival and quote ages during expected sessions, including no-ticket
   sessions. Ten consecutive-session acceptance remains measured operating
   evidence; installing timers does not establish it.

The [operational journal and read-only report](morning-service-report.md) retain
bounded worker observations in the same durable database. Export a dated report
alongside the independently measured HTTPS arrival and cost evidence. The first
trusted writer opening an uninstrumented database starts a new journal without
reconstructing earlier operations; later upgrades preserve its history. Check
the report's capture and pruning limits before interpreting a missing receipt. No-op ticks
are not scheduler heartbeats, and local receipt commitment is not public delivery.

The remaining external inputs are the selected existing host/account, persistent
volume, production WSGI/TLS route and its URL, server-side provider bindings and
verified entitlement/costs. These templates purchase or provision nothing.
