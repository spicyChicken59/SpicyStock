"""Prepared single-host morning receipt service; no provider transport is wired.

Trusted local commands ingest a verified publication and replay retained receipts.
A scheduler can call ``collect_once`` with an explicit bounded collector. HTTP
only reads committed bytes. SQLite must live on one host's durable local volume,
not an ephemeral filesystem, network filesystem or independent replica volumes.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from wsgiref.simple_server import make_server, WSGIRequestHandler
from urllib.parse import urlsplit

from src import morning
from tools.publish_morning import publication_check

VERSION = 1
MAX_DAILY_RESERVATIONS = 120
MIN_INTERVAL_SECONDS = 30
MAX_LEASE_SECONDS = morning.POLICY['max_collection_seconds']


def _instant(value):
    at = morning._instant(value)
    if at is None:
        raise ValueError('service_clock_requires_offset')
    return at.astimezone(timezone.utc)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest() if raw is not None else None


def _encode(value):
    return json.dumps(value, allow_nan=False, separators=(',', ':')).encode() + b'\n'


def _read(path, maximum):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('service_input_requires_regular_file')
    with path.open('rb') as handle:
        raw = handle.read(maximum + 1)
    if not raw or len(raw) > maximum:
        raise ValueError('service_input_exceeds_bound')
    return raw


@dataclass(frozen=True)
class Policy:
    interval_seconds: int = 30
    daily_reservations: int = 120
    lease_seconds: int = 180

    def __post_init__(self):
        for value in asdict(self).values():
            if type(value) is not int:
                raise ValueError('service_policy_requires_integers')
        if not (MIN_INTERVAL_SECONDS <= self.interval_seconds <= 3600
                and 1 <= self.daily_reservations <= MAX_DAILY_RESERVATIONS
                and 1 <= self.lease_seconds <= MAX_LEASE_SECONDS):
            raise ValueError('service_policy_outside_bounds')


@dataclass(frozen=True)
class Claim:
    fence: int
    generation: int
    started_at: str
    expires_at: str
    publication: bytes
    previous: bytes | None


class Store:
    """Trusted writer API. Every reservation spends quota, including failures.

    A policy is pinned when the database is created. New workers must use that
    exact policy; restarting a worker cannot reset cadence, quota or fencing.
    The ledger retains only the latest UTC day because backwards clocks are
    refused. Old receipt bytes survive publication replacement for restrictions.
    """
    def __init__(self, path, policy=None, *, mode="prepared"):
        if mode not in ("prepared", "replay"):
            raise ValueError("service_mode_invalid")
        self.path = Path(path).absolute()
        self.policy = policy or Policy()
        if self.path.is_symlink():
            raise ValueError('service_database_must_not_be_symlink')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._transaction() as db:
            db.execute('CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER NOT NULL, mode TEXT NOT NULL, policy TEXT NOT NULL, generation INTEGER NOT NULL, fence INTEGER NOT NULL, publication BLOB, publication_sha TEXT, receipt BLOB, receipt_sha TEXT, lease_until REAL, clock REAL, last_reserved REAL, quota_day TEXT, quota_used INTEGER NOT NULL)')
            db.execute('INSERT OR IGNORE INTO state VALUES (1, ?, ?, ?, 0, 0, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 0)', (VERSION, mode, _encode(asdict(self.policy)).decode()))
            state = db.execute('SELECT * FROM state WHERE id=1').fetchone()
            if state['version'] != VERSION or state['mode'] != mode or json.loads(state['policy']) != asdict(self.policy):
                raise ValueError('service_database_policy_differs')

    @contextmanager
    def _transaction(self):
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.execute('COMMIT')
        except BaseException:
            if db.in_transaction:
                db.execute('ROLLBACK')
            raise
        finally:
            db.close()

    @staticmethod
    def _clock(state, at):
        if state['clock'] is not None and at.timestamp() < state['clock']:
            raise ValueError('service_clock_moved_backwards')

    def ingest(self, raw, *, now, previous=None, expected_generation=None):
        """Local authenticated/operator handoff; never exposed over HTTP.

        ``previous`` seeds restriction continuity only on the first ingestion
        using the collector's independently validated cross-publication event
        continuity. Same-source receipts also undergo full validation. Later
        ingestions keep
        the already-validated receipt regardless of publication identity.
        """
        at = _instant(now)
        binding = morning.bind_record(raw)
        if _instant(binding['published_at']) > at + timedelta(seconds=morning.POLICY['max_future_skew_seconds']):
            raise ValueError('service_publication_is_in_future')
        if previous is not None:
            if not isinstance(previous, bytes) or len(previous) > morning.MAX_OBSERVATION_BYTES:
                raise ValueError('service_previous_receipt_exceeds_bound')
            value = json.loads(previous)
            if value.get('dry_run') is not False:
                raise ValueError('service_rehearsal_receipt_refused')
            morning._previous_halts(previous, raw, binding)
            if _instant(value['generated_at']) > at + timedelta(seconds=morning.POLICY['max_future_skew_seconds']):
                raise ValueError('service_receipt_is_in_future')
        with self._transaction() as db:
            state = db.execute('SELECT * FROM state WHERE id=1').fetchone()
            self._clock(state, at)
            if expected_generation is not None and state['generation'] != expected_generation:
                return 'source_record_changed'
            if previous is not None and state['publication'] is not None:
                raise ValueError('service_previous_receipt_only_at_bootstrap')
            if state['publication_sha'] == binding['data_sha256']:
                db.execute('UPDATE state SET clock=? WHERE id=1', (at.timestamp(),))
                return 'unchanged'
            if state['publication'] is not None:
                old = json.loads(state['publication'])['run']
                if (binding['measured_session'] < old['session'] or
                        _instant(binding['published_at']) < _instant(old['published_at'])):
                    raise ValueError('service_publication_rollback_refused')
            db.execute('UPDATE state SET publication=?, publication_sha=?, generation=generation+1, fence=fence+1, lease_until=NULL, clock=?, receipt=?, receipt_sha=? WHERE id=1',
                       (raw, binding['data_sha256'], at.timestamp(), previous if previous is not None else state['receipt'], _sha(previous) if previous is not None else state['receipt_sha']))
        return 'ingested'

    def reserve(self, *, now):
        """Return (claim, reason). No collector is called without a claim.

        At most one unexpired claim exists. An expired claimant loses commit
        authority; its callback must also enforce its own execution deadline.
        Reservations count collections, not provider calls or transport retries.
        """
        at = _instant(now)
        with self._transaction() as db:
            state = db.execute('SELECT * FROM state WHERE id=1').fetchone()
            self._clock(state, at)
            db.execute('UPDATE state SET clock=? WHERE id=1', (at.timestamp(),))
            raw = state['publication']
            if raw is None:
                return None, 'publication_missing'
            # Preserve production's calendar/window/freshness rules exactly.
            reason = morning._reason(json.loads(raw), at)
            if reason:
                return None, reason
            if state['lease_until'] is not None and at.timestamp() < state['lease_until']:
                return None, 'collection_in_progress'
            if state['last_reserved'] is not None and at.timestamp() - state['last_reserved'] < self.policy.interval_seconds:
                return None, 'collection_interval'
            day = at.date().isoformat()
            used = state['quota_used'] if state['quota_day'] == day else 0
            if used >= self.policy.daily_reservations:
                return None, 'daily_reservation_budget'
            fence = state['fence'] + 1
            expires = at + timedelta(seconds=self.policy.lease_seconds)
            db.execute('UPDATE state SET fence=?, lease_until=?, last_reserved=?, quota_day=?, quota_used=? WHERE id=1',
                       (fence, expires.timestamp(), at.timestamp(), day, used + 1))
            return Claim(fence, state['generation'], at.isoformat(), expires.isoformat(), raw, state['receipt']), 'reserved'

    @contextmanager
    def request_transaction(self, claim, *, now):
        """Atomic reservation boundary for a separate bounded provider adapter.

        The adapter may update its own attempt/cache tables using the yielded
        connection. Reserve before sending; never hold this transaction over
        network work. The check does not itself spend any provider attempt.
        """
        at = _instant(now)
        with self._transaction() as db:
            state = db.execute('SELECT * FROM state WHERE id=1').fetchone()
            self._clock(state, at)
            if (state['mode'] != 'prepared' or state['generation'] != claim.generation
                    or state['publication_sha'] != _sha(claim.publication)
                    or state['receipt_sha'] != _sha(claim.previous)
                    or state['fence'] != claim.fence or state['lease_until'] is None
                    or state['last_reserved'] != _instant(claim.started_at).timestamp()
                    or state['lease_until'] != _instant(claim.expires_at).timestamp()
                    or at.timestamp() >= state['lease_until']):
                raise ValueError('service_request_claim_inactive')
            reason = morning._reason(json.loads(claim.publication), at)
            if reason:
                raise ValueError('service_request_outside_window')
            db.execute('UPDATE state SET clock=? WHERE id=1', (at.timestamp(),))
            yield db

    def commit(self, claim, raw, *, now):
        """Commit only the current fenced claim against unchanged stored bytes."""
        at = _instant(now)
        if not isinstance(raw, bytes) or not raw or len(raw) > morning.MAX_OBSERVATION_BYTES:
            raise ValueError('service_receipt_exceeds_bound')
        value = json.loads(raw)
        # Production validation is mandatory; copied identity strings do not
        # replace replay against the actual source and previous receipt bytes.
        refusal = publication_check(value, claim.publication, claim.previous, at)
        if refusal:
            return refusal
        if _instant(value['collection_started_at']) < _instant(claim.started_at):
            raise ValueError('service_receipt_predates_reservation')
        if _instant(value['generated_at']) > at:
            raise ValueError('service_receipt_completion_after_commit')
        with self._transaction() as db:
            state = db.execute('SELECT * FROM state WHERE id=1').fetchone()
            self._clock(state, at)
            if state['generation'] != claim.generation or state['publication_sha'] != _sha(claim.publication):
                return 'source_record_changed'
            if state['receipt_sha'] != _sha(claim.previous):
                return 'previous_observation_changed'
            if (state['fence'] != claim.fence or state['lease_until'] is None
                    or state['last_reserved'] != _instant(claim.started_at).timestamp()
                    or state['lease_until'] != _instant(claim.expires_at).timestamp()):
                return 'lease_superseded'
            if at >= _instant(claim.expires_at) or at.timestamp() >= state['lease_until']:
                return 'lease_expired'
            db.execute('UPDATE state SET receipt=?, receipt_sha=?, lease_until=NULL, clock=? WHERE id=1', (raw, _sha(raw), at.timestamp()))
        return 'committed'

    def release(self, claim, *, now):
        """A failed attempt releases only its own lease and never refunds quota."""
        at = _instant(now)
        with self._transaction() as db:
            state = db.execute('SELECT * FROM state WHERE id=1').fetchone()
            self._clock(state, at)
            if state['fence'] != claim.fence or state['generation'] != claim.generation:
                return False
            db.execute('UPDATE state SET lease_until=NULL, clock=? WHERE id=1', (at.timestamp(),))
        return True


def collect_once(store, collector, *, clock):
    """One scheduler tick with an explicit collector; never a default network call.

    The callable receives canonical and previous bytes plus a clock and bounded
    run id. An audited adapter can wrap ``morning.collect``. Provider attempt
    quotas, retry/backoff, shared halt cache and hard deadline belong to that
    adapter; this store provides collection reservations and commit fencing.
    """
    claim, reason = store.reserve(now=clock())
    if claim is None:
        return reason
    try:
        result = collector(claim.publication, previous_raw=claim.previous,
                           clock=clock, observation_run_id=f'service-{claim.generation}-{claim.fence}')
        return store.commit(claim, _encode(result), now=clock())
    finally:
        store.release(claim, now=clock())


def application(database, *, allowed_origin=None):
    """Create a WSGI read route. GET opens SQLite read-only and performs no writes."""
    path = Path(database).absolute()
    if allowed_origin is not None:
        origin = urlsplit(allowed_origin)
        if (origin.scheme != 'https' or not origin.hostname or origin.username is not None
                or origin.password is not None or origin.path or origin.query or origin.fragment
                or allowed_origin != 'https://' + origin.netloc
                or any(c.isspace() for c in allowed_origin)):
            raise ValueError('service_origin_requires_exact_https_origin')
        origin.port  # Also reject malformed/out-of-range ports.

    def app(environ, start_response):
        status, value, etag = '503 Service Unavailable', b'{"status":"unavailable"}\n', None
        if environ.get('REQUEST_METHOD') != 'GET':
            status, value = '405 Method Not Allowed', b'{"status":"method_not_allowed"}\n'
        elif environ.get('PATH_INFO') != '/morning.json':
            status, value = '404 Not Found', b'{"status":"not_found"}\n'
        elif (environ.get('QUERY_STRING') or environ.get('CONTENT_LENGTH', '') not in ('', '0')
              or environ.get('HTTP_TRANSFER_ENCODING')):
            status, value = '400 Bad Request', b'{"status":"parameters_refused"}\n'
        else:
            try:
                if path.is_symlink():
                    raise ValueError('database path changed')
                db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=1)
                try:
                    state = db.execute('SELECT version, publication_sha, receipt, receipt_sha, mode FROM state WHERE id=1').fetchone()
                finally:
                    db.close()
                if state and state[0] == VERSION and state[4] == 'prepared' and isinstance(state[2], bytes) and 0 < len(state[2]) <= morning.MAX_OBSERVATION_BYTES:
                    receipt = json.loads(state[2])
                    if _sha(state[2]) == state[3] and receipt.get('publication', {}).get('data_sha256') == state[1]:
                        status, value, etag = '200 OK', state[2], state[3]
            except (sqlite3.Error, OSError, ValueError, TypeError, AttributeError):
                pass
        headers = [('Content-Type', 'application/json; charset=utf-8'), ('Content-Length', str(len(value))),
                   ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'),
                   ('X-SpicyStock-Service', 'prepared-adapter')]
        if allowed_origin is not None:
            headers.append(('Vary', 'Origin'))
            if environ.get('HTTP_ORIGIN') == allowed_origin:
                headers.append(('Access-Control-Allow-Origin', allowed_origin))
        if etag:
            headers.append(('ETag', '"' + etag + '"'))
        if status.startswith('405'):
            headers.append(('Allow', 'GET'))
        start_response(status, headers)
        return [value]
    return app


class _QuietHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        # Do not log arbitrary incoming query strings, cookies or headers.
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--database', required=True, type=Path)
    sub = parser.add_subparsers(dest='command', required=True)
    ingest = sub.add_parser('ingest', help='Trusted local publication handoff; no fetches')
    ingest.add_argument('--publication', required=True, type=Path)
    ingest.add_argument('--previous', type=Path)
    replay = sub.add_parser('replay', help='Replay a retained pair at its original instants; no providers')
    replay.add_argument('--publication', required=True, type=Path)
    replay.add_argument('--receipt', required=True, type=Path)
    serve = sub.add_parser('serve', help='Loopback development WSGI server; no collection')
    serve.add_argument('--port', type=int, default=8766)
    serve.add_argument('--allowed-origin', help='Optional exact trusted HTTPS browser origin')
    args = parser.parse_args(argv)
    try:
        if args.command == 'serve':
            if not 1 <= args.port <= 65535:
                raise ValueError('service_port_invalid')
            with make_server('127.0.0.1', args.port, application(args.database, allowed_origin=args.allowed_origin), handler_class=_QuietHandler) as server:
                server.serve_forever()
            return 0
        raw = _read(args.publication, morning.MAX_PUBLICATION_BYTES)
        store = Store(args.database, mode='replay' if args.command == 'replay' else 'prepared')
        if args.command == 'ingest':
            previous = _read(args.previous, morning.MAX_OBSERVATION_BYTES) if args.previous else None
            result = store.ingest(raw, now=datetime.now(timezone.utc), previous=previous)
            print(json.dumps({'mode': 'prepared_adapter', 'result': result}))
            return 0
        receipt = _read(args.receipt, morning.MAX_OBSERVATION_BYTES)
        value = json.loads(receipt)
        started, completed = _instant(value['collection_started_at']), _instant(value['generated_at'])
        store.ingest(raw, now=started)
        claim, reason = store.reserve(now=started)
        result = store.commit(claim, receipt, now=completed) if claim else reason
        print(json.dumps({'mode': 'offline_replay', 'result': result, 'generated_at': value['generated_at']}))
        return 0 if result == 'committed' else 1
    except (ValueError, KeyError, TypeError, sqlite3.Error, OSError):
        print('{"status":"refused","reason":"invalid service input, state or clock"}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
