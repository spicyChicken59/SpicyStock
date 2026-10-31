# Railway morning-service runbook

This is a prepared deployment procedure, not an installed Railway service or
schedule. No production service URL, provider binding or live-session acceptance
is established by this document. The browser endpoint remains empty until the
real HTTPS route is verified. The approved monthly ceiling is **$20 total**;
account access and the controls below must be verified before provisioning.

Use the repository's root `Dockerfile` and `requirements-host.txt`. The image
starts `python -m src.morning_host`, which supervises the public Gunicorn reader,
publication synchronization and an optional bounded worker. The image contains
code and required static rule files; it does not contain a database, publication,
provider credential or private account data. Follow the existing
[single-host contract](morning-service.md) and [deployment handoff](morning-deployment.md).

## Establish account access and budget first

1. Connect the Railway account and identify the intended workspace. Inspect its
   subscription, billing period, current and projected usage, existing projects,
   and applicable taxes. Verify workspace-admin access to spending controls;
   access to one project's environment is insufficient to establish those
   controls. Railway distinguishes account, workspace, project-environment and
   OAuth permissions in its [API authentication documentation](https://docs.railway.com/integrations/api).
2. Confirm the Hobby subscription and payment setup. Hobby's $5 monthly minimum
   includes $5 of usage; it is not another $5 added to all resource usage. Its
   default volume size is 5 GB. Free/trial storage is only 0.5 GB and is not this
   deployment. See [plans](https://docs.railway.com/pricing/plans) and
   [volume limits](https://docs.railway.com/volumes/reference).
3. In the selected workspace's Usage page, set **Compute email alert $10**, **Compute
   hard limit $15**, and **Railway Agent hard limit $0**. Read the saved values
   back, including the workspace identity, before creating the service. Compute
   covers all workspace services, not just this application. Agent usage has a
   separate limit. Reaching the Compute limit takes workloads offline; it does
   not preserve the morning delivery guarantee. These settings reserve room
   under the $20 ceiling while taxes and other usage are checked. They are not
   an unconditional guarantee of the final invoice. See
   [cost controls](https://docs.railway.com/pricing/cost-control),
   [limit commands and scopes](https://docs.railway.com/cli/usage), and
   [invoice taxes](https://docs.railway.com/pricing/understanding-your-bill).
4. Verify the projected total fits the ceiling after other workspace usage,
   taxes and any backup charges. If it does not, stop before provisioning; do
   not silently increase the cap, change plan or buy a domain. The generated
   Railway HTTPS service domain is sufficient for this adapter.

Current published resource rates are RAM $10/GB-month, CPU $20/vCPU-month,
egress $0.05/GB and volume storage $0.15/used-GB-month. A full 5 GB volume is
approximately $0.75/month before additional charges. The 2 GB memory setting
below is a peak resource ceiling, not a prepaid allocation or cost guarantee;
measure actual use. Recheck [Railway pricing](https://docs.railway.com/pricing)
when provisioning and review the workspace estimate after deployment.

## Configure one persistent service

Use verified dashboard settings or authorized API calls, then read them back.
Do not rely on a new `railway.toml` or `railway.json`: current Railway documentation
says new services cannot opt into that legacy system. This procedure does not
create an IaC configuration or apply infrastructure before account access is
available. See [current configuration support](https://docs.railway.com/config-as-code).

| Setting | Required value or procedure |
| --- | --- |
| Project/environment | One explicitly selected project and production environment |
| Service | One Docker service in one selected region; no replicas or multi-region copies |
| Source | Reviewed application revision; record its full commit and the actual deployed image digest |
| Build | Repository root `Dockerfile`; install `requirements-host.txt`; no custom pre-deploy command |
| Start | Preserve image entrypoint `python -m src.morning_host`; do not replace it with a bare web server |
| Volume | One 5 GB persistent volume mounted exactly at `/srv/spicystock` |
| Database | `/srv/spicystock/morning.sqlite`, shared by processes in this service |
| Memory ceiling | 2 GB; inspect actual memory, CPU, egress and storage use |
| Runtime user | Root launcher; retain image default, or use `RAILWAY_RUN_UID=0` if a platform override is needed |
| Port | Image default `PORT=8080`; public target and healthcheck port must match actual `PORT` |
| Worker | `MORNING_WORKER_ENABLED=false` for initial deployment |
| Healthcheck | `/healthz`, with a 120-second startup timeout |
| Restart | `Always` on the paid plan; investigate repeated configuration refusals |
| Shutdown | At least 15 seconds draining time; overlap time 0 |
| Serverless/sleep | Disabled; the private schedules must run without browser traffic |
| Automatic deployment | Disabled; deploy reviewed application changes deliberately |

Attach the volume before the first start. Railway mounts volumes at runtime,
not during build or pre-deploy, and mounts them root-owned. The launcher verifies
an actual kernel mount at the fixed path and holds a single-supervisor file
lock. It refuses missing mounts and unexpected storage entries rather than
creating an ephemeral replacement. See [volume mounting](https://docs.railway.com/volumes).

The launcher assigns the directory to writer UID **10001**, group **10000**,
mode **0750**, and database files mode **0640**. Both trusted writer commands run
as UID 10001. Gunicorn runs as reader UID **10002**, group 10000, without filesystem
write permission there. Child processes use umask 027 and cleared supplementary
groups. Keep reports, arbitrary files and manually copied backups outside this
volume; its startup validation accepts only the service database files, its
lock, and the filesystem's permitted `lost+found` directory.

A Railway volume cannot be shared by replicas. Volume-backed deployments have
some downtime, including when `/healthz` is configured. Keep redeployments away
from the preparation/entry window and preserve the same volume across upgrades.
Do not redeploy for data-only commits: the bounded synchronizer already follows
the fixed repository's current publication. See
[volume deployment constraints](https://docs.railway.com/volumes/reference),
[restart policy](https://docs.railway.com/deployments/restart-policy), and
[shutdown controls](https://docs.railway.com/deployments/deployment-teardown).

## Process behavior and provider activation

The launcher runs independent monotonic schedules: source synchronization every
**300 seconds**, and the enabled worker every **30 seconds**. A role never starts
a replacement command until its prior process group is reaped. Missed ticks do
not cause a catch-up burst. Sync and worker may run concurrently; the existing
SQLite source-generation, receipt, lease and quota checks still govern writes.
Each scheduled command has a **45-second external deadline**, then **5 seconds**
to terminate before its process group is killed and reaped. The commands retain
their tighter internal deadlines. These are bounded invocation targets, not
measured on-time delivery.

On SIGTERM/SIGINT the launcher stops scheduling and terminates its child groups.
Gunicorn exit causes the supervisor to stop the other roles and exit unsuccessfully
so the platform can restart it. The HTTP process uses one Gunicorn worker with
two threads. `/healthz` reports only that the reader process can answer; it does
not read the database, contact a provider or certify source freshness. Railway
checks the endpoint during deployment, not as continuing operational monitoring.
See [healthcheck behavior](https://docs.railway.com/deployments/healthchecks).

Leave the worker disabled for initial storage, source and HTTP checks. To activate
it, confirm access and entitlement for the existing Alpaca feeds, then place
`ALPACA_API_KEY` and `ALPACA_SECRET_KEY` directly in this service's Railway Variables.
Set `MORNING_WORKER_ENABLED=true` deliberately and apply the controlled deployment.
The flag accepts exactly `false` or `true`; enabling it without both nonempty
credentials refuses startup. This does not purchase a data subscription.

Do not paste credentials into chat, logs, code, Docker `ARG`/`ENV` instructions,
image layers or command arguments. The root launcher receives Railway's runtime
variables and constructs sanitized child environments. Only the worker command
receives the Alpaca pair; the reader and synchronizer do not. Unrelated application
secrets are not needed. Railway needs no custom CA setting for this deployment.
The `Dockerfile` uses no build secret and no `RUN --mount`: Railway's builder
refused the first deployment of the earlier file, which mounted an optional
`proxy_ca` secret, with "The Dockerfile failed validation" (31 October 2026). A
local build behind an intercepting proxy supplies its certificate outside the
committed file.

## Bring up and verify

1. Deploy the reviewed image with the worker disabled. Confirm the intended
   volume is attached, runtime permissions are correct, and source synchronization
   can ingest the fixed public repository. Supervisor logs contain fixed lifecycle
   outcomes; child output is suppressed. Inspect the persisted source ledger and
   [read-only operational report](morning-service-report.md) through authorized
   private access when more detail is needed. Do not dump environment variables.
2. Generate a Railway service domain and route it to the actual `PORT`. Keep TLS
   verification enabled. Check HTTPS `GET /healthz` independently of
   `GET /morning.json`. A missing or prior-publication receipt correctly returns
   503 while `/healthz` returns 200. No receipt timestamp should be rewritten to
   make the service appear fresh. Railway provides generated domains and automatic
   TLS through [public networking](https://docs.railway.com/networking/public-networking).
3. Verify `/morning.json` preserves `Cache-Control: no-store`, exact receipt bytes
   and CORS for **`https://spicychicken59.github.io`** only. Check that POST, query
   parameters and unexpected paths cannot start work. Extra public GETs must not
   increase collection reservations or provider attempts.
4. Activate the worker as above, using the real clock. Outside the recorded
   collection window it should skip provider work. During an applicable window,
   inspect committed receipt identity, original timestamps, coverage and charged
   attempts. A valid zero-ticket receipt does not establish fresh quote coverage.
   Restart the service and verify source identity, quotas, backoff and retained
   event restrictions survive. Never wipe or replace the database to clear a limit.
5. Only after the real TLS route and browser behavior are verified, release its
   exact HTTPS URL ending `/morning.json` in the existing
   `spicystock-morning-endpoint` meta tag in `docs/index.html`. Keep the tag empty
   until then. Use the normal reviewed Pages release and verify phone/desktop
   reads, source changes, outages and visible expiry. Do not add a static fallback
   when the configured dynamic route fails.
6. Read back workspace spending limits and current/projected costs. Check disk
   headroom, restart behavior and provider access during actual expected sessions.
   Export dated reports to a separate retained location before journal pruning;
   preserve the production volume and ledgers during application changes.

The journal's 1 GiB logical payload limit is not a physical disk cap or complete
backup. Keep independent evidence of public HTTPS arrival, expiry and actual
costs alongside its local worker observations. Ten consecutive expected sessions,
including honest no-ticket outcomes and failures, remain operating acceptance.
Broader issuer-news/future-earnings coverage and actual broker cash, orders and
fills remain separate dependencies. This deployment procedure establishes none
of those results by itself.
