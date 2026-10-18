"""One private, bounded production collection tick for a durable single-host store.

Run from a trusted scheduler, never from an HTTP handler. The supervisor reserves
and commits; its disposable child alone talks to the fixed read-only sources.
No invocation can place an order, accept a ticker, or weaken production rules.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import json
import multiprocessing
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time

import requests
from requests.adapters import HTTPAdapter

from src import morning, morning_halts, morning_service as service

TOTAL_SECONDS = 25
CONNECT_SECONDS = 3
READ_SECONDS = 4
MAX_SNAPSHOT_BYTES = 2 * 1024 * 1024
ALPACA_URL = 'https://data.alpaca.markets/v2/stocks/snapshots'
FEEDS = {'iex': (30, 120), 'delayed_sip': (30, 120), 'nasdaq': (60, 60)}
RATE_BACKOFF_SECONDS = 300
ERROR_BACKOFF_SECONDS = 60
MAX_BACKOFF_SECONDS = 86400
LEDGER_VERSION = 1


def utcnow():
    return datetime.now(timezone.utc)


class Deferred(ValueError):
    """Fixed, nonsecret refusal; never includes URL, response or credentials."""

    def __init__(self, reason, status_code=None):
        super().__init__(reason)
        self.status_code = status_code
        self.local_reason = ('local_backoff' if reason == 'worker_provider_backoff' else
                             'local_budget' if reason in ('worker_provider_interval', 'worker_provider_daily_budget') else None)


def _retry_after(value, at):
    try:
        seconds = int(value) if re.fullmatch(r'[0-9]{1,8}', value or '') else (parsedate_to_datetime(value) - at).total_seconds()
        return max(RATE_BACKOFF_SECONDS, min(MAX_BACKOFF_SECONDS, seconds))
    except (TypeError, ValueError, OverflowError):
        return RATE_BACKOFF_SECONDS


class Ledger:
    """Attempts and halt cache share the store's durable SQLite transaction lock.

    The ledger charges immediately before transport, including failed attempts.
    An interrupted attempt retains its cadence and budget charge. Only successful
    halt bytes are cached, with their original receipt time, never refreshed by
    reading the cache. No provider call occurs while a transaction is open.
    """

    def __init__(self, store, claim, *, deadline, clock=utcnow, monotonic=time.monotonic):
        self.store, self.claim = store, claim
        self.clock, self.monotonic, self.deadline = clock, monotonic, deadline
        with store.request_transaction(claim, now=self.now()) as db:
            db.execute('CREATE TABLE IF NOT EXISTS provider_policy (id INTEGER PRIMARY KEY CHECK(id=1), policy TEXT NOT NULL)')
            policy = json.dumps({'version': LEDGER_VERSION, 'feeds': FEEDS, 'auth': 'alpaca_provider_next_utc_day', 'rate': RATE_BACKOFF_SECONDS, 'error': ERROR_BACKOFF_SECONDS, 'max_backoff': MAX_BACKOFF_SECONDS}, sort_keys=True)
            db.execute('INSERT OR IGNORE INTO provider_policy VALUES (1, ?)', (policy,))
            if db.execute('SELECT policy FROM provider_policy WHERE id=1').fetchone()[0] != policy:
                raise ValueError('worker_provider_policy_differs')
            db.execute('CREATE TABLE IF NOT EXISTS provider_attempts (feed TEXT PRIMARY KEY, day TEXT NOT NULL, used INTEGER NOT NULL, last_at REAL NOT NULL, attempt INTEGER NOT NULL, backoff_until REAL, status_code INTEGER, finished_at REAL)')
            db.execute('CREATE TABLE IF NOT EXISTS provider_cache (feed TEXT PRIMARY KEY, body BLOB NOT NULL, fetched_at TEXT NOT NULL, http_date TEXT)')

    def now(self):
        if self.monotonic() >= self.deadline:
            raise Deferred('worker_deadline')
        return service._instant(self.clock())

    def check(self):
        with self.store.request_transaction(self.claim, now=self.now()):
            pass

    def reserve(self, feed):
        if feed not in FEEDS:
            raise Deferred('worker_feed_refused')
        at = self.now()
        with self.store.request_transaction(self.claim, now=at) as db:
            if feed in ('iex', 'delayed_sip'):
                blocked = db.execute("SELECT 1 FROM provider_attempts WHERE feed IN ('iex','delayed_sip') AND status_code=401 AND backoff_until>? LIMIT 1", (at.timestamp(),)).fetchone()
                if blocked:
                    raise Deferred('worker_provider_backoff')
            row = db.execute('SELECT * FROM provider_attempts WHERE feed=?', (feed,)).fetchone()
            interval, budget = FEEDS[feed]
            if row:
                if row['backoff_until'] is not None and at.timestamp() < row['backoff_until']:
                    raise Deferred('worker_provider_backoff')
                if at.timestamp() - row['last_at'] < interval:
                    raise Deferred('worker_provider_interval')
            used = row['used'] if row and row['day'] == at.date().isoformat() else 0
            if used >= budget:
                raise Deferred('worker_provider_daily_budget')
            attempt = row['attempt'] + 1 if row else 1
            db.execute('INSERT OR REPLACE INTO provider_attempts VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL)', (feed, at.date().isoformat(), used + 1, at.timestamp(), attempt))
            return attempt

    def finish(self, feed, attempt, *, status=None, retry_after=None, cache=None):
        at = self.now()
        until = None
        if status in (401, 403):
            until = datetime.combine(at.date() + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).timestamp()
        elif status == 429:
            until = at.timestamp() + _retry_after(retry_after, at)
        elif status != 200:
            until = at.timestamp() + ERROR_BACKOFF_SECONDS
        with self.store.request_transaction(self.claim, now=at) as db:
            changed = db.execute('UPDATE provider_attempts SET backoff_until=?, status_code=?, finished_at=? WHERE feed=? AND attempt=?', (until, status, at.timestamp(), feed, attempt)).rowcount
            if changed and cache is not None and status == 200 and feed == 'nasdaq':
                db.execute('INSERT OR REPLACE INTO provider_cache VALUES (?, ?, ?, ?)', (feed, cache['body'], cache['fetched_at'], cache['http_date']))

    def cached_halts(self):
        at = self.now()
        with self.store.request_transaction(self.claim, now=at) as db:
            row = db.execute('SELECT * FROM provider_attempts WHERE feed=?', ('nasdaq',)).fetchone()
            # A cache hit is allowed only until the next attempt is due. During
            # a backoff retain dated evidence instead of manufacturing a fetch.
            if row and (at.timestamp() - row['last_at'] < FEEDS['nasdaq'][0]
                        or row['backoff_until'] is not None and at.timestamp() < row['backoff_until']):
                cached = db.execute('SELECT body, fetched_at, http_date FROM provider_cache WHERE feed=?', ('nasdaq',)).fetchone()
                if cached:
                    return dict(cached)
        return None


class BoundedSession(requests.Session):
    """Real requests transport constrained underneath the real Alpaca SDK."""

    def __init__(self, ledger):
        super().__init__()
        self.ledger = ledger
        self.symbols = ','.join(sorted({row['ticker'] for row in morning.admitted_rows(json.loads(ledger.claim.publication))}))
        for prefix in ('https://', 'http://'):
            self.mount(prefix, HTTPAdapter(max_retries=0))

    def resolve_redirects(self, response, request, **kwargs):
        # Requests otherwise buffers a redirect body to prepare response.next
        # even with allow_redirects=False. Refuse without reading that body.
        return iter(())

    def request(self, method, url, **kwargs):
        if method.upper() != 'GET' or kwargs.get('json') is not None or kwargs.get('data') is not None:
            raise Deferred('worker_endpoint_refused')
        params = kwargs.get('params') or {}
        if url == ALPACA_URL:
            feed = params.get('feed')
            feed = getattr(feed, 'value', feed)
            if (feed not in ('iex', 'delayed_sip') or not self.symbols
                    or params.get('symbols') != self.symbols
                    or set(params) - {'feed', 'symbols', 'limit', 'page_token'}
                    or params.get('limit') is not None or params.get('page_token') is not None):
                raise Deferred('worker_snapshot_parameters_refused')
            bound = MAX_SNAPSHOT_BYTES
        elif url == morning_halts.SOURCE_URL and not params:
            feed, bound = 'nasdaq', morning_halts.MAX_FEED_BYTES
        else:
            raise Deferred('worker_endpoint_refused')
        self.ledger.check()
        attempt = self.ledger.reserve(feed)
        response = None
        try:
            remaining = self.ledger.deadline - self.ledger.monotonic()
            if remaining <= 0:
                raise Deferred('worker_deadline')
            kwargs.update(allow_redirects=False, timeout=(min(CONNECT_SECONDS, remaining), min(READ_SECONDS, remaining)), stream=True)
            headers = dict(kwargs.get('headers') or {})
            headers['Accept-Encoding'] = 'identity'
            kwargs['headers'] = headers
            response = super().request(method, url, **kwargs)
            self.ledger.check()
            if response.status_code != 200:
                status = response.status_code
                self.ledger.finish(feed, attempt, status=status, retry_after=response.headers.get('Retry-After'))
                raise Deferred('worker_provider_unavailable', status)
            body = bytearray()
            for chunk in response.iter_content(chunk_size=8192):
                self.ledger.check()
                body.extend(chunk)
                if len(body) > bound:
                    raise Deferred('worker_response_exceeds_bound')
            self.ledger.check()
            # The SDK still consumes its usual requests.Response and parses its
            # own Snapshot model. No test-only client replaces this boundary.
            response._content = bytes(body)
            response._content_consumed = True
            fetched = self.ledger.now().isoformat()
            cache = None
            if feed == 'nasdaq':
                morning_halts.parse(response.content)
                date = response.headers.get('Date')
                cache = {'body': response.content, 'fetched_at': fetched,
                         'http_date': date if isinstance(date, str) and len(date) <= morning_halts.MAX_FIELD_LENGTH else None}
                response.worker_halt_receipt = cache
            self.ledger.finish(feed, attempt, status=200, cache=cache)
            return response
        except Exception:
            # Preserve a specific HTTP backoff instead of replacing it with a
            # generic error. A dead/superseded claim cannot write cache/results.
            if response is None or response.status_code == 200:
                self.ledger.finish(feed, attempt)
            raise
        finally:
            if response is not None:
                response.close()


def sdk_client(ledger):
    from alpaca.data.historical import StockHistoricalDataClient
    keys = [os.environ.get(name, '').strip() for name in ('ALPACA_API_KEY', 'ALPACA_SECRET_KEY')]
    if not all(keys):
        return None
    client = StockHistoricalDataClient(*keys)
    client._session.close()
    client._session = BoundedSession(ledger)
    # alpaca-py's retry_attempts=0 does not disable retries: its constructor
    # ignores falsey values. Pin the actual field and exercise 429 in tests.
    client._retry = 0
    return client


def collect_claim(store, claim, *, deadline, clock=utcnow, monotonic=time.monotonic):
    """Child-side production collection; injectable clocks only for local tests."""
    ledger = Ledger(store, claim, deadline=deadline, clock=clock, monotonic=monotonic)
    client = sdk_client(ledger)
    with BoundedSession(ledger) as halt_session:
        def fetch_halts():
            cached = ledger.cached_halts()
            if cached is not None:
                return cached
            return halt_session.get(morning_halts.SOURCE_URL, headers={'User-Agent': 'SpicyStock/1.0 (public halt observations)', 'Accept': 'application/rss+xml, text/xml'}).worker_halt_receipt

        def events(symbols, now, *, previous=None):
            ledger.check()
            return morning_halts.observe(symbols, now, previous=previous, fetcher=fetch_halts)

        try:
            ledger.check()
            result = morning.collect(claim.publication, previous_raw=claim.previous, client=client,
                                     clock=clock, event_observer=events, dry_run=False,
                                     observation_run_id=f'service-{claim.generation}-{claim.fence}')
            ledger.check()
            return result
        finally:
            if client is not None:
                client._session.close()


def _collect_child(path, policy, claim, output, deadline):
    try:
        store = service.Store(path, policy)
        value = collect_claim(store, claim, deadline=deadline)
        raw = service._encode(value)
        if len(raw) > morning.MAX_OBSERVATION_BYTES:
            raise ValueError('worker_receipt_exceeds_bound')
        with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as handle:
            handle.write(raw)
    except BaseException:
        # Do not print provider exception text, request headers or record bytes.
        raise SystemExit(2) from None


def run_once(store, *, clock=utcnow, context=None, child_target=_collect_child, seconds=TOTAL_SECONDS):
    """Supervise one child; kill and reap before releasing its claim on timeout."""
    if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or not 0 < seconds <= TOTAL_SECONDS:
        raise ValueError('worker_deadline_outside_bounds')
    deadline = time.monotonic() + seconds
    claim, reason = store.reserve(now=clock())
    if claim is None:
        return reason
    child = None
    try:
        at = service._instant(clock())
        cutoff = service._instant(json.loads(claim.publication)['run']['timing']['cutoff_at'])
        deadline = min(deadline, time.monotonic() + (cutoff - at).total_seconds(),
                       time.monotonic() + (service._instant(claim.expires_at) - at).total_seconds())
        if time.monotonic() >= deadline:
            return 'worker_deadline'
        with tempfile.TemporaryDirectory(prefix='spicystock-worker-') as private:
            output = str(Path(private) / 'receipt.json')
            child = (context or multiprocessing.get_context('spawn')).Process(target=child_target, args=(str(store.path), store.policy, claim, output, deadline))
            child.start()
            child.join(max(0, deadline - time.monotonic()))
            if child.is_alive() or time.monotonic() >= deadline:
                return 'worker_deadline'
            if child.exitcode != 0:
                return 'worker_failed'
            raw = service._read(output, morning.MAX_OBSERVATION_BYTES)
            return store.commit(claim, raw, now=clock())
    finally:
        if child is not None and child.is_alive():
            child.terminate()
            child.join(1)
            if child.is_alive():
                child.kill()
                child.join(1)
        # Never free the lease before the collector is reaped. If the OS cannot
        # reap it, leave the lease charged/fenced for operator investigation.
        if child is None or not child.is_alive():
            store.release(claim, now=clock())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--database', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = run_once(service.Store(args.database))
        print(json.dumps({'mode': 'bounded_private_worker', 'result': result}))
        return 1 if result in ('worker_deadline', 'worker_failed') else 0
    except (ValueError, OSError, sqlite3.Error, KeyError, TypeError):
        print('{"mode":"bounded_private_worker","result":"refused"}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
