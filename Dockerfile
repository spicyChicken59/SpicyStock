FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    MORNING_WORKER_ENABLED=false

WORKDIR /app

COPY requirements.txt requirements-host.txt ./
# No build secret and no RUN --mount. Railway's builder refused the earlier
# file, which mounted an optional proxy_ca secret ("The Dockerfile failed
# validation", 31 October 2026). Railway does not support secret mounts, and it
# accepts a cache mount only when the mount's id carries the service's own id,
# which this file does not hard-code. A build behind an intercepting proxy
# supplies its certificate outside this file (docs/operations/morning-railway.md).
RUN python -m pip install --no-cache-dir -r requirements-host.txt

RUN groupadd --gid 10000 morning \
    && useradd --uid 10001 --gid morning --no-create-home --shell /usr/sbin/nologin morning-writer \
    && useradd --uid 10002 --gid morning --no-create-home --shell /usr/sbin/nologin morning-reader \
    && mkdir -p /srv/spicystock

COPY src/*.py ./src/
COPY tools/*.py ./tools/
COPY knowledge/event-risk.json ./knowledge/event-risk.json
COPY data/symbols.txt ./data/symbols.txt

# Checkout permissions vary between builders. Every unprivileged role must be
# able to import these root-owned files, and none needs to edit application code.
RUN find /app -type d -exec chmod 0555 {} + \
    && find /app -type f -exec chmod 0444 {} +

# Root initializes the mounted volume, then launches separate unprivileged roles.
# The launcher refuses an ordinary directory in place of the persistent mount.
STOPSIGNAL SIGTERM
EXPOSE 8080
ENTRYPOINT ["python", "-m", "src.morning_host"]
