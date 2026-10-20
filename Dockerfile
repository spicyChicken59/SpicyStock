# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    MORNING_WORKER_ENABLED=false

WORKDIR /app

COPY requirements.txt requirements-host.txt ./
# A managed build may supply its CA bundle as a temporary BuildKit secret.
# Public builds use the image's normal trust store; no proxy or CA is retained.
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    python -m pip install --no-cache-dir -r requirements-host.txt

RUN groupadd --gid 10000 morning \
    && useradd --uid 10001 --gid morning --no-create-home --shell /usr/sbin/nologin morning-writer \
    && useradd --uid 10002 --gid morning --no-create-home --shell /usr/sbin/nologin morning-reader \
    && mkdir -p /srv/spicystock

COPY src/*.py ./src/
COPY tools/*.py ./tools/
COPY knowledge/event-risk.json ./knowledge/event-risk.json
COPY data/symbols.txt ./data/symbols.txt

# Root initializes the mounted volume, then launches separate unprivileged roles.
# The launcher refuses an ordinary directory in place of the persistent mount.
STOPSIGNAL SIGTERM
EXPOSE 8080
ENTRYPOINT ["python", "-m", "src.morning_host"]
