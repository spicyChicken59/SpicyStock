# The on-time dispatcher (tools/dispatch_schedule.py) as its own Railway
# service: one process that, at each slot on an XNYS session, asks GitHub to
# start evening.yml, morning.yml or service-watch.yml. It reads the calendar
# (src/sessions.py) and nothing else of the repository, holds one credential
# (GITHUB_TOKEN, Actions read and write on this repository) and needs no
# volume: GitHub's own run list makes a repeat start a no-op. The setup and
# the checks are docs/operations/external-scheduler.md. Built from the
# repository root (Railway's build context), from the same pinned base image
# as the morning host's Dockerfile.
FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements-scheduler.txt constraints.txt ./
RUN python -m pip install --no-cache-dir -r requirements-scheduler.txt -c constraints.txt

COPY src/sessions.py ./src/sessions.py
COPY tools/dispatch_schedule.py ./tools/dispatch_schedule.py

RUN useradd --uid 10003 --no-create-home --shell /usr/sbin/nologin dispatcher \
    && find /app -type d -exec chmod 0555 {} + \
    && find /app -type f -exec chmod 0444 {} +
USER dispatcher

STOPSIGNAL SIGTERM
ENTRYPOINT ["python", "tools/dispatch_schedule.py", "loop"]
