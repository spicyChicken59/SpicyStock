"""Trusted fixed-repository publication handoff for the prepared morning service.

One bounded read-only GitHub synchronization, at most every five minutes across
all processes sharing the service database. No URL, ref, symbol or credential
input is accepted. This command never invokes a provider, workflow or Git write.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import multiprocessing
from pathlib import Path
import re
import sqlite3
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from src import morning
from src.morning_service import Store

REPOSITORY = 'spicyChicken59/SpicyStock'
REF_URL = f'https://api.github.com/repos/{REPOSITORY}/git/ref/heads/main'
CONTENTS_URL = f'https://api.github.com/repos/{REPOSITORY}/contents/docs?ref='
RAW_ROOT = f'https://raw.githubusercontent.com/{REPOSITORY}/'
MIN_POLL_SECONDS = 300
MAX_REQUESTS = 5
MAX_SYNC_SECONDS = 30
MAX_METADATA_BYTES = 16 * 1024
MAX_DIRECTORY_BYTES = 256 * 1024
MAX_SUPERVISOR_SECONDS = 35
MAX_RESULT_BYTES = 4096
MAX_ERROR_BACKOFF_SECONDS = 3600
HEX = re.compile(r'[a-f0-9]{40}')


class SyncError(ValueError):
    def __init__(self, reason, *, backoff=MIN_POLL_SECONDS):
        super().__init__(reason)
        self.reason = reason
        self.backoff = max(MIN_POLL_SECONDS, min(MAX_ERROR_BACKOFF_SECONDS, backoff))


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SyncError('source_redirect_refused')


def _instant(value):
    at = morning._instant(value)
    if at is None:
        raise SyncError('source_clock_requires_offset')
    return at.astimezone(timezone.utc)


def _remaining(deadline):
    left = deadline - time.monotonic()
    if left <= 0:
        raise SyncError('source_deadline_exceeded')
    return min(left, 5)


def fetch(url, maximum, deadline):
    """Fixed caller-generated URL, no redirects/retries, bounded streaming body."""
    request = Request(url, headers={'User-Agent': 'SpicyStock morning publication handoff',
                                   'Accept': 'application/vnd.github+json' if url.startswith('https://api.github.com/') else 'application/json',
                                   'Accept-Encoding': 'identity'})
    try:
        with build_opener(_NoRedirect()).open(request, timeout=_remaining(deadline)) as response:
            length = response.headers.get('Content-Length')
            if length is not None and (not length.isdecimal() or int(length) > maximum):
                raise SyncError('source_response_exceeds_bound')
            chunks, size = [], 0
            while length is None or size < int(length):
                try:
                    response.fp.raw._sock.settimeout(_remaining(deadline))
                except AttributeError:
                    raise SyncError('source_deadline_transport_unavailable') from None
                # read1 performs a single underlying read; read(n) may continue
                # filling n bytes across repeated socket waits past the deadline.
                body = response.read1(min(65536, maximum + 1 - size))
                _remaining(deadline)
                if not body:
                    if length is not None and size != int(length):
                        raise SyncError('source_response_truncated')
                    break
                size += len(body)
                if size > maximum:
                    raise SyncError('source_response_exceeds_bound')
                chunks.append(body)
            return b''.join(chunks)
    except HTTPError as exc:
        if exc.code == 404:
            raise SyncError('source_not_found') from None
        if exc.code in (403, 429):
            wait = exc.headers.get('Retry-After', '') if exc.headers else ''
            backoff = int(wait) if wait.isdecimal() else MAX_ERROR_BACKOFF_SECONDS
            raise SyncError('source_access_denied' if exc.code == 403 else 'source_rate_limit', backoff=backoff) from None
        raise SyncError('source_http_error') from None
    except (URLError, OSError, TimeoutError):
        raise SyncError('source_transport_unavailable') from None


def _json(raw):
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError):
        raise SyncError('source_metadata_invalid') from None
    if not isinstance(value, dict):
        raise SyncError('source_metadata_invalid')
    return value


def _ref(raw):
    value = _json(raw)
    obj = value.get('object')
    if (value.get('ref') != 'refs/heads/main' or not isinstance(obj, dict)
            or obj.get('type') != 'commit' or not isinstance(obj.get('sha'), str)
            or not HEX.fullmatch(obj['sha'])):
        raise SyncError('source_ref_invalid')
    return obj['sha']


def _metadata(raw):
    try:
        items = json.loads(raw)
    except (ValueError, UnicodeError):
        raise SyncError('source_metadata_invalid') from None
    if not isinstance(items, list) or not 1 <= len(items) <= 1000:
        raise SyncError('source_directory_invalid')
    # A directory listing never embeds file content, even for small canonical
    # files. Only the exact fixed path is used; API-supplied URLs are ignored.
    matching = [item for item in items if isinstance(item, dict) and
                (item.get('path') == 'docs/data.json' or item.get('name') == 'data.json')]
    if len(matching) != 1:
        raise SyncError('source_file_identity_invalid')
    value = matching[0]
    if (value.get('type') != 'file' or value.get('path') != 'docs/data.json' or value.get('name') != 'data.json'
            or type(value.get('size')) is not int or not 0 < value['size'] <= morning.MAX_PUBLICATION_BYTES
            or not isinstance(value.get('sha'), str) or not HEX.fullmatch(value['sha'])):
        raise SyncError('source_file_identity_invalid')
    return value


def blob_sha(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def sync(store, *, transport=fetch, clock=None, monotonic=None):
    """Read immutable committed bytes; retain current service state on any refusal."""
    clock = clock or (lambda: datetime.now(timezone.utc))
    monotonic = monotonic or time.monotonic
    started = _instant(clock())
    with store._transaction() as db:
        db.execute('CREATE TABLE IF NOT EXISTS morning_source_sync (id INTEGER PRIMARY KEY CHECK(id=1), fence INTEGER NOT NULL, next_allowed REAL NOT NULL, last_started REAL, last_status TEXT, request_count INTEGER NOT NULL, commit_sha TEXT)')
        db.execute('INSERT OR IGNORE INTO morning_source_sync VALUES (1, 0, 0, NULL, NULL, 0, NULL)')
        state = db.execute('SELECT * FROM state WHERE id=1').fetchone()
        store._clock(state, started)
        if state['mode'] != 'prepared':
            raise SyncError('source_replay_database_refused')
        prior = db.execute('SELECT * FROM morning_source_sync WHERE id=1').fetchone()
        if started.timestamp() < prior['next_allowed']:
            return {'status': 'poll_interval', 'requests': 0}
        fence = prior['fence'] + 1
        generation, existing = state['generation'], state['publication']
        db.execute('UPDATE morning_source_sync SET fence=?,next_allowed=?,last_started=?,last_status=?,request_count=0 WHERE id=1',
                   (fence, started.timestamp() + MIN_POLL_SECONDS, started.timestamp(), 'collecting'))
        db.execute('UPDATE state SET clock=? WHERE id=1', (started.timestamp(),))
    deadline = monotonic() + MAX_SYNC_SECONDS
    requests = 0
    commit = None
    backoff = MIN_POLL_SECONDS

    def get(url, maximum):
        nonlocal requests
        if requests >= MAX_REQUESTS:
            raise SyncError('source_request_budget')
        if monotonic() >= deadline:
            raise SyncError('source_deadline_exceeded')
        requests += 1  # Failed attempts consume the same bound; no retry.
        raw = transport(url, maximum, deadline)
        if monotonic() >= deadline:
            raise SyncError('source_deadline_exceeded')
        if not isinstance(raw, bytes) or not raw or len(raw) > maximum:
            raise SyncError('source_response_exceeds_bound')
        return raw

    try:
        commit = _ref(get(REF_URL, MAX_METADATA_BYTES))
        metadata = _metadata(get(CONTENTS_URL + commit, MAX_DIRECTORY_BYTES))
        unchanged = existing is not None and blob_sha(existing) == metadata['sha'] and len(existing) == metadata['size']
        raw = existing if unchanged else get(RAW_ROOT + commit + '/docs/data.json', morning.MAX_PUBLICATION_BYTES)
        if len(raw) != metadata['size'] or blob_sha(raw) != metadata['sha']:
            raise SyncError('source_blob_identity_differs')
        morning.bind_record(raw)
        previous = None
        if existing is None:
            try:
                previous = get(RAW_ROOT + commit + '/docs/morning.json', morning.MAX_OBSERVATION_BYTES)
            except SyncError as exc:
                if exc.reason != 'source_not_found':
                    raise
        if _ref(get(REF_URL, MAX_METADATA_BYTES)) != commit:
            raise SyncError('source_main_changed')
        finished = _instant(clock())
        if finished < started or (finished - started).total_seconds() > MAX_SYNC_SECONDS or monotonic() >= deadline:
            raise SyncError('source_deadline_exceeded')
        result = store.ingest(raw, now=finished, previous=previous, expected_generation=generation)
    except SyncError as exc:
        result, backoff = exc.reason, exc.backoff
    except (ValueError, KeyError, TypeError, UnicodeError):
        result = 'source_publication_or_receipt_invalid'
    except OSError:
        result = 'source_transport_unavailable'
    finished = _instant(clock())
    with store._transaction() as db:
        # A stale completion cannot alter another poll's backoff/status. Source
        # ingestion separately compares the captured generation atomically.
        db.execute('UPDATE morning_source_sync SET last_status=?,request_count=?,commit_sha=?,next_allowed=MAX(next_allowed,?) WHERE id=1 AND fence=?',
                   (result, requests, commit, max(started, finished).timestamp() + (backoff if result not in ('ingested', 'unchanged') else 0), fence))
    return {'status': result, 'requests': requests, 'commit_sha': commit}


def _child(database, output):
    """Only fixed repository reads and atomic local writes, with bounded output."""
    try:
        result = sync(Store(database))
    except (ValueError, OSError, sqlite3.Error):
        result = {'status': 'source_state_unavailable', 'requests': 0}
    try:
        encoded = json.dumps(result, allow_nan=False, separators=(',', ':')).encode()
        if len(encoded) > MAX_RESULT_BYTES:
            encoded = b'{"status":"source_result_exceeds_bound","requests":0}'
        output.send_bytes(encoded)
    finally:
        output.close()


def supervise(database, *, timeout=MAX_SUPERVISOR_SECONDS, context=None, child=None):
    """Bound startup, DNS, HTTP and local ingestion; no unsupervised CLI sync.

    A timeout may coincide with a completed atomic local ingestion. The next
    invocation rechecks the source; it never assumes a timeout changed nothing.
    ``context`` and ``child`` are deterministic-test seams, not CLI inputs.
    """
    if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout) or not 0 < timeout <= MAX_SUPERVISOR_SECONDS):
        raise ValueError('source_supervisor_deadline_invalid')
    context = context or multiprocessing.get_context('spawn')
    incoming, outgoing = context.Pipe(duplex=False)
    process = context.Process(target=child or _child, args=(str(database), outgoing), daemon=True)
    result = {'status': 'source_supervisor_timeout', 'requests': None}
    try:
        process.start()
        outgoing.close()
        if incoming.poll(timeout):
            try:
                payload = incoming.recv_bytes(MAX_RESULT_BYTES)
                observed = json.loads(payload)
                if (not isinstance(observed, dict) or not isinstance(observed.get('status'), str)
                        or len(observed['status']) > 80 or set(observed) - {'status', 'requests', 'commit_sha'}
                        or type(observed.get('requests')) is not int or not 0 <= observed['requests'] <= MAX_REQUESTS
                        or ('commit_sha' in observed and observed['commit_sha'] is not None
                            and (not isinstance(observed['commit_sha'], str) or not HEX.fullmatch(observed['commit_sha'])))):
                    raise ValueError('invalid child result')
                result = observed
            except (EOFError, OSError, ValueError, UnicodeError):
                result = {'status': 'source_supervisor_result_invalid', 'requests': None}
    finally:
        outgoing.close()
        incoming.close()
        if process.pid is not None:
            # Even a child that returned a result cannot keep running in the
            # background. No unbounded join follows the deadline.
            if process.is_alive():
                process.terminate()
            process.join(timeout=2)
            if process.is_alive():
                process.kill()
                process.join(timeout=2)
            if process.is_alive():
                result = {'status': 'source_supervisor_cleanup_failed', 'requests': None}
            else:
                process.close()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--database', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = supervise(args.database)
    except (ValueError, OSError, sqlite3.Error):
        result = {'status': 'source_state_unavailable', 'requests': 0}
    print(json.dumps(result))
    return 0 if result['status'] in ('ingested', 'unchanged', 'poll_interval') else 1


if __name__ == '__main__':
    raise SystemExit(main())
