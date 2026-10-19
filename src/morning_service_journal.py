"""Bounded local writer evidence, never public delivery or market authority.

Events are appended in the transaction that charges or commits the observation.
No-op ticks create no events: absence cannot establish scheduler failure. Exact
public source/receipt blobs support historical read-only checks. Retention bounds
logical payload, not SQLite page overhead; discarded history is always declared.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from src import morning

VERSION = 1
RETENTION_DAYS = 45
MAX_EVENTS = 20_000
MAX_BYTES = 1024 * 1024 * 1024
MAX_PAYLOAD_BYTES = 4096
MAX_READ_BYTES = 256 * 1024 * 1024
KINDS = {'source_ingested', 'collection_reserved', 'collection_finished', 'provider_reserved', 'provider_finished'}
OUTCOMES = {'committed', 'released_unknown', 'worker_failed', 'worker_deadline', 'collector_failed',
            'source_record_changed', 'previous_observation_changed', 'lease_superseded',
            'lease_expired', 'newer_or_equal_observation_exists'}
FEEDS = {'iex', 'delayed_sip', 'nasdaq'}
FIELDS = {
    'source_ingested': {'git_commit', 'published_at', 'measured_session', 'admitted_count'},
    'collection_reserved': {'started_at', 'expires_at', 'previous_receipt_sha256', 'quota_day', 'quota_used'},
    'collection_finished': {'outcome', 'receipt_sha256', 'previous_receipt_sha256'},
    'provider_reserved': {'feed', 'attempt', 'quota_day', 'quota_used'},
    'provider_finished': {'feed', 'attempt', 'status_code', 'backoff_until'},
}


def instant(value):
    at = morning._instant(value)
    if at is None:
        raise ValueError('journal_clock_requires_offset')
    return at.astimezone(timezone.utc)


def sha(raw):
    return hashlib.sha256(raw).hexdigest() if raw is not None else None


def _hex(value, length=64):
    return isinstance(value, str) and re.fullmatch('[a-f0-9]{' + str(length) + '}', value) is not None


def _payload(kind, value):
    if kind not in KINDS or not isinstance(value, dict) or set(value) != FIELDS[kind]:
        raise ValueError('journal_payload_invalid')
    for key, item in value.items():
        if key.endswith('_sha256') and item is not None and not _hex(item):
            raise ValueError('journal_payload_invalid')
        if key in ('published_at', 'started_at', 'expires_at', 'backoff_until') and item is not None:
            instant(item)
        if key in ('quota_day', 'measured_session'):
            datetime.strptime(item, '%Y-%m-%d')
    if 'git_commit' in value and value['git_commit'] is not None and not _hex(value['git_commit'], 40):
        raise ValueError('journal_payload_invalid')
    if 'outcome' in value and value['outcome'] not in OUTCOMES:
        raise ValueError('journal_payload_invalid')
    if 'feed' in value and value['feed'] not in FEEDS:
        raise ValueError('journal_payload_invalid')
    for key in ('quota_used', 'attempt', 'admitted_count'):
        if key in value and (type(value[key]) is not int or not 0 <= value[key] <= 2**63 - 1):
            raise ValueError('journal_payload_invalid')
    if 'status_code' in value and value['status_code'] is not None and (type(value['status_code']) is not int or not 100 <= value['status_code'] <= 599):
        raise ValueError('journal_payload_invalid')
    if kind == 'collection_finished' and ((value['outcome'] == 'committed') != (value['receipt_sha256'] is not None)):
        raise ValueError('journal_payload_invalid')
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    if len(raw) > MAX_PAYLOAD_BYTES:
        raise ValueError('journal_payload_exceeds_bound')
    return raw


def initialize(db, state):
    """Add empty instrumentation to existing DBs; never fabricate past events."""
    db.execute('CREATE TABLE IF NOT EXISTS morning_journal_meta (id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER NOT NULL, mode TEXT NOT NULL, started_at TEXT, last_at TEXT, migrated INTEGER NOT NULL, pruned_events INTEGER NOT NULL, pruned_through_id INTEGER, pruned_through_at TEXT, retention_days INTEGER NOT NULL, max_events INTEGER NOT NULL, max_bytes INTEGER NOT NULL)')
    db.execute('INSERT OR IGNORE INTO morning_journal_meta VALUES (1, ?, ?, NULL, NULL, ?, 0, NULL, NULL, ?, ?, ?)',
               (VERSION, state['mode'], int(state['publication'] is not None), RETENTION_DAYS, MAX_EVENTS, MAX_BYTES))
    meta = db.execute('SELECT * FROM morning_journal_meta WHERE id=1').fetchone()
    if (meta['version'], meta['mode'], meta['retention_days'], meta['max_events'], meta['max_bytes']) != (VERSION, state['mode'], RETENTION_DAYS, MAX_EVENTS, MAX_BYTES):
        raise ValueError('journal_policy_differs')
    db.execute('CREATE TABLE IF NOT EXISTS morning_journal_events (id INTEGER PRIMARY KEY AUTOINCREMENT, event_key TEXT UNIQUE NOT NULL, recorded_at TEXT NOT NULL, kind TEXT NOT NULL, generation INTEGER NOT NULL, fence INTEGER NOT NULL, applicable_session TEXT NOT NULL, source_sha256 TEXT NOT NULL, payload TEXT NOT NULL, payload_sha256 TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS morning_journal_blobs (sha256 TEXT PRIMARY KEY, kind TEXT NOT NULL, raw BLOB NOT NULL, bytes INTEGER NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS morning_journal_refs (event_id INTEGER NOT NULL, sha256 TEXT NOT NULL, PRIMARY KEY(event_id,sha256))')
    db.execute('CREATE INDEX IF NOT EXISTS morning_journal_refs_sha ON morning_journal_refs(sha256)')


def _blob(db, kind, raw):
    if not isinstance(raw, bytes) or not raw or len(raw) > (morning.MAX_PUBLICATION_BYTES if kind == 'publication' else morning.MAX_OBSERVATION_BYTES):
        raise ValueError('journal_blob_exceeds_bound')
    digest = sha(raw)
    existing = db.execute('SELECT kind,bytes FROM morning_journal_blobs WHERE sha256=?', (digest,)).fetchone()
    if existing is None:
        db.execute('INSERT INTO morning_journal_blobs VALUES (?, ?, ?, ?)', (digest, kind, raw, len(raw)))
    elif existing['kind'] != kind or existing['bytes'] != len(raw):
        raise ValueError('journal_blob_identity_differs')
    return digest


def append(db, *, kind, at, generation, fence, publication, payload, receipt=None, previous=None):
    """Append only within the caller's accepted write transaction; bounded atoms."""
    at = instant(at)
    payload_raw = _payload(kind, payload)
    if type(generation) is not int or type(fence) is not int or generation < 1 or fence < 1:
        raise ValueError('journal_identity_invalid')
    session = json.loads(publication)['run']['timing']['applicable_session']
    datetime.strptime(session, '%Y-%m-%d')
    key = f'{kind}:{generation}:{fence}'
    if kind.startswith('provider_'):
        key += f":{payload['feed']}:{payload['attempt']}"
    # A successful commit is terminal; a finally-release cannot relabel it.
    if db.execute('SELECT 1 FROM morning_journal_events WHERE event_key=?', (key,)).fetchone():
        return
    meta = db.execute('SELECT * FROM morning_journal_meta WHERE id=1').fetchone()
    if meta['last_at'] is not None and at < instant(meta['last_at']):
        raise ValueError('journal_clock_moved_backwards')
    source = _blob(db, 'publication', publication)
    refs = {source}
    for raw, field in ((receipt, 'receipt_sha256'), (previous, 'previous_receipt_sha256')):
        if raw is not None:
            digest = _blob(db, 'receipt', raw)
            if payload.get(field) != digest:
                raise ValueError('journal_blob_identity_differs')
            refs.add(digest)
        elif payload.get(field) is not None:
            raise ValueError('journal_blob_missing')
    cursor = db.execute('INSERT INTO morning_journal_events (event_key,recorded_at,kind,generation,fence,applicable_session,source_sha256,payload,payload_sha256) VALUES (?,?,?,?,?,?,?,?,?)',
                        (key, at.isoformat(), kind, generation, fence, session, source, payload_raw.decode(), sha(payload_raw)))
    db.executemany('INSERT INTO morning_journal_refs VALUES (?,?)', ((cursor.lastrowid, digest) for digest in refs))
    db.execute('UPDATE morning_journal_meta SET started_at=COALESCE(started_at,?),last_at=? WHERE id=1', (at.isoformat(), at.isoformat()))
    _prune(db, at, meta)


def _prune(db, at, meta):
    """Oldest-first pruning keeps every retained event's referenced bytes intact."""
    rows = db.execute('SELECT id,recorded_at,length(CAST(payload AS BLOB)) AS bytes FROM morning_journal_events ORDER BY id').fetchall()
    counts = {row[0]: [row[1], row[2]] for row in db.execute('SELECT b.sha256,b.bytes,COUNT(r.event_id) FROM morning_journal_blobs b JOIN morning_journal_refs r ON b.sha256=r.sha256 GROUP BY b.sha256')}
    refs = {}
    for row in db.execute('SELECT event_id,sha256 FROM morning_journal_refs'):
        refs.setdefault(row[0], []).append(row[1])
    size = sum(row['bytes'] for row in rows) + sum(value[0] for value in counts.values())
    cutoff = at - timedelta(days=meta['retention_days'])
    removed = []
    for row in rows:
        if len(rows) - len(removed) <= meta['max_events'] and size <= meta['max_bytes'] and instant(row['recorded_at']) >= cutoff:
            break
        removed.append(row)
        size -= row['bytes']
        for digest in refs.get(row['id'], []):
            counts[digest][1] -= 1
            if counts[digest][1] == 0:
                size -= counts[digest][0]
    if removed:
        last = removed[-1]
        db.execute('DELETE FROM morning_journal_refs WHERE event_id<=?', (last['id'],))
        db.execute('DELETE FROM morning_journal_events WHERE id<=?', (last['id'],))
        db.execute('UPDATE morning_journal_meta SET pruned_events=pruned_events+?,pruned_through_id=?,pruned_through_at=? WHERE id=1', (len(removed), last['id'], last['recorded_at']))
    db.execute('DELETE FROM morning_journal_blobs WHERE NOT EXISTS (SELECT 1 FROM morning_journal_refs WHERE sha256=morning_journal_blobs.sha256)')


def read_journal(path, *, as_of=None, start=None, end=None, max_read_bytes=MAX_READ_BYTES):
    """Read a consistent bounded snapshot, without initializing or pruning it.

    Dates filter applicable_session inclusively; as_of filters the writer's
    recorded_at, never the older receipt/provider timestamp. Referenced bytes
    are preflighted before loading. Existing uninstrumented DBs fail explicitly.
    """
    if type(max_read_bytes) is not int or not 1 <= max_read_bytes <= MAX_BYTES:
        raise ValueError('journal_read_bound_invalid')
    path = Path(path).absolute()
    if path.is_symlink():
        raise ValueError('journal_database_invalid')
    if as_of is not None:
        as_of = instant(as_of)
    for value in (start, end):
        if value is not None:
            datetime.strptime(str(value), '%Y-%m-%d')
    db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=1)
    db.row_factory = sqlite3.Row
    try:
        db.execute('BEGIN')
        meta = dict(db.execute('SELECT * FROM morning_journal_meta WHERE id=1').fetchone())
        state = db.execute('SELECT mode FROM state WHERE id=1').fetchone()
        if meta['version'] != VERSION or meta['mode'] != 'prepared' or state['mode'] != 'prepared':
            raise ValueError('journal_mode_or_version_refused')
        if not 1 <= meta['max_events'] <= MAX_EVENTS or not 1 <= meta['max_bytes'] <= MAX_BYTES or not 1 <= meta['retention_days'] <= RETENTION_DAYS:
            raise ValueError('journal_policy_invalid')
        if db.execute('SELECT count(*) FROM morning_journal_events').fetchone()[0] > meta['max_events']:
            raise ValueError('journal_event_bound_invalid')
        # Preflight lengths before fetching any variable-sized body. Copy only
        # the selected snapshot while locked; hashes/JSON validation run after
        # closing the connection so reports do not hold up writer commits.
        headers = db.execute('SELECT id,recorded_at,applicable_session,length(CAST(payload AS BLOB)) AS bytes FROM morning_journal_events ORDER BY id').fetchall()
        selected = {row['id'] for row in headers if not (
            as_of is not None and instant(row['recorded_at']) > as_of
            or start is not None and row['applicable_session'] < str(start)
            or end is not None and row['applicable_session'] > str(end))}
        selected_headers = [row for row in headers if row['id'] in selected]
        if any(not 0 < row['bytes'] <= MAX_PAYLOAD_BYTES for row in selected_headers):
            raise ValueError('journal_payload_invalid')
        refs, needed = {}, set()
        for row in db.execute('SELECT event_id,sha256 FROM morning_journal_refs'):
            if row[0] in selected:
                refs.setdefault(row[0], set()).add(row[1])
                needed.add(row[1])
        sizes = {row[0]: (row[1], row[2], row[3]) for row in db.execute('SELECT sha256,bytes,length(raw),kind FROM morning_journal_blobs') if row[0] in needed}
        if set(sizes) != needed or any(size != length or size <= 0 for size, length, _ in sizes.values()):
            raise ValueError('journal_blob_missing')
        for size, _, kind in sizes.values():
            if kind not in ('publication', 'receipt') or size > (morning.MAX_PUBLICATION_BYTES if kind == 'publication' else morning.MAX_OBSERVATION_BYTES):
                raise ValueError('journal_blob_invalid')
        if sum(size for size, _, _ in sizes.values()) + sum(row['bytes'] for row in selected_headers) > max_read_bytes:
            raise ValueError('journal_read_exceeds_bound')
        raw_events, blobs = [], {}
        ids = sorted(selected)
        for offset in range(0, len(ids), 900):
            chunk = ids[offset:offset + 900]
            raw_events.extend(dict(row) for row in db.execute('SELECT * FROM morning_journal_events WHERE id IN (' + ','.join('?' for _ in chunk) + ') ORDER BY id', chunk))
        digests = sorted(needed)
        for offset in range(0, len(digests), 900):
            chunk = digests[offset:offset + 900]
            for row in db.execute('SELECT * FROM morning_journal_blobs WHERE sha256 IN (' + ','.join('?' for _ in chunk) + ')', chunk):
                blobs[row['sha256']] = dict(row)

    finally:
        db.close()

    events = []
    for item in raw_events:
        payload = item['payload'].encode()
        if sha(payload) != item['payload_sha256']:
            raise ValueError('journal_payload_invalid')
        item['payload'] = json.loads(payload)
        if _payload(item['kind'], item['payload']) != payload or not _hex(item['source_sha256']):
            raise ValueError('journal_payload_invalid')
        if type(item['generation']) is not int or type(item['fence']) is not int or item['generation'] < 1 or item['fence'] < 1:
            raise ValueError('journal_identity_invalid')
        expected = {item['source_sha256']} | {item['payload'][key] for key in ('receipt_sha256', 'previous_receipt_sha256') if item['payload'].get(key) is not None}
        if refs.get(item['id'], set()) != expected:
            raise ValueError('journal_blob_references_invalid')
        events.append(item)
    for digest, row in blobs.items():
        if sha(row['raw']) != digest:
            raise ValueError('journal_blob_invalid')
    return {'meta': meta, 'events': events, 'blobs': blobs}
