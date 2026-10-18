"""Provider-free durable evidence tests; recorded fixtures are not live readiness."""
from dataclasses import replace
from datetime import timedelta
import hashlib
import json
import multiprocessing
import sqlite3

import pytest

from src import morning, morning_service as service, morning_service_journal as journal, morning_service_worker as worker
from tests.test_morning_service import NOW, RAW, RED, collect, encode, request, store_at
from tests.test_morning_service_worker import Clock, ledger, state, transport, _hanging_child, _synthetic_child
from tests.test_sync_morning_service import Source, run, COMMIT


def events(store, kind=None, **kwargs):
    rows = journal.read_journal(store.path, **kwargs)['events']
    return [row for row in rows if kind is None or row['kind'] == kind]


def sql(store, query):
    with sqlite3.connect(store.path) as db:
        return db.execute(query).fetchall()


def failure(*args, **kwargs):
    raise ValueError('synthetic journal unavailable')


def test_actual_collector_commit_preserves_writer_clock_and_exact_historical_bytes(tmp_path):
    store = store_at(tmp_path)
    claim, _ = store.reserve(now=NOW)
    raw = encode(collect())
    committed = NOW + timedelta(seconds=3)
    assert store.commit(claim, raw, now=committed) == 'committed'
    store.release(claim, now=committed)
    snapshot = journal.read_journal(store.path)
    assert snapshot['meta']['started_at'] == NOW.isoformat()
    assert snapshot['meta']['migrated'] == 0
    rows = snapshot['events']
    assert [r['kind'] for r in rows] == ['source_ingested', 'collection_reserved', 'collection_finished']
    assert rows[-1]['recorded_at'] == committed.isoformat()
    assert rows[-1]['payload']['outcome'] == 'committed'
    assert rows[-1]['source_sha256'] == hashlib.sha256(RAW).hexdigest()
    assert rows[-1]['generation'] == claim.generation and rows[-1]['fence'] == claim.fence
    assert snapshot['blobs'][rows[-1]['payload']['receipt_sha256']]['raw'] == raw
    assert snapshot['blobs'][rows[-1]['source_sha256']]['raw'] == RAW
    assert json.loads(raw)['generated_at'] != rows[-1]['recorded_at']
    assert not events(store, 'collection_finished', as_of=NOW + timedelta(seconds=2))


def test_prior_receipt_is_context_without_retroactive_commit(tmp_path):
    previous = encode(collect())
    store = store_at(tmp_path, previous=previous)
    claim, _ = store.reserve(now=NOW)
    assert claim.previous == previous
    snapshot = journal.read_journal(store.path)
    assert not events(store, 'collection_finished')
    assert snapshot['blobs'][hashlib.sha256(previous).hexdigest()]['raw'] == previous


def test_existing_database_migrates_empty_without_backfilled_success(tmp_path):
    store = store_at(tmp_path)
    claim, _ = store.reserve(now=NOW)
    assert store.commit(claim, encode(collect()), now=NOW) == 'committed'
    before = sql(store, 'SELECT generation,fence,quota_day,quota_used,receipt_sha FROM state')
    with sqlite3.connect(store.path) as db:
        for table in ('morning_journal_refs', 'morning_journal_events', 'morning_journal_blobs', 'morning_journal_meta'):
            db.execute('DROP TABLE ' + table)
    migrated = service.Store(store.path)
    snapshot = journal.read_journal(migrated.path)
    assert snapshot['events'] == [] and snapshot['blobs'] == {}
    assert snapshot['meta']['migrated'] == 1 and snapshot['meta']['started_at'] is None
    assert sql(store, 'SELECT generation,fence,quota_day,quota_used,receipt_sha FROM state') == before
    claim, _ = migrated.reserve(now=NOW + timedelta(seconds=30))
    assert claim is not None
    assert [r['kind'] for r in events(migrated)] == ['collection_reserved']
    assert journal.read_journal(migrated.path)['meta']['started_at'] == (NOW + timedelta(seconds=30)).isoformat()


def test_source_sync_records_verified_commit_but_unchanged_poll_adds_nothing(tmp_path):
    store = service.Store(tmp_path / 'service.sqlite')
    assert run(store, Source())['status'] == 'ingested'
    assert events(store)[0]['payload']['git_commit'] == COMMIT
    assert run(store, Source(), at=NOW + timedelta(seconds=301))['status'] == 'unchanged'
    assert len(events(store)) == 1


def test_source_change_preserves_old_identity_and_leaves_superseded_attempt_unknown(tmp_path):
    store = store_at(tmp_path)
    claim, _ = store.reserve(now=NOW)
    assert store.ingest(RAW + b'\n', now=NOW + timedelta(seconds=1)) == 'ingested'
    assert not store.release(claim, now=NOW + timedelta(seconds=2), outcome='worker_failed')
    assert store.commit(claim, encode(collect()), now=NOW + timedelta(seconds=2)) == 'source_record_changed'
    rows = events(store)
    assert [r['kind'] for r in rows] == ['source_ingested', 'collection_reserved', 'source_ingested']
    assert rows[1]['source_sha256'] != rows[2]['source_sha256']
    assert rows[1]['generation'] == 1 and rows[2]['generation'] == 2


def test_expired_attempt_remains_unknown_after_replacement(tmp_path):
    store = store_at(tmp_path)
    old, _ = store.reserve(now=NOW)
    later = NOW + timedelta(seconds=181)
    current, _ = store.reserve(now=later)
    assert store.commit(old, encode(collect()), now=later) == 'lease_superseded'
    assert not store.release(old, now=later, outcome='worker_deadline')
    assert len(events(store, 'collection_reserved')) == 2
    assert not events(store, 'collection_finished')
    assert sql(store, 'SELECT fence,quota_used FROM state') == [(current.fence, 2)]


def test_noop_ticks_and_public_reads_add_no_observations(tmp_path):
    store = service.Store(tmp_path / 'empty.sqlite')
    for _ in range(10):
        assert store.reserve(now=NOW)[1] == 'publication_missing'
    assert not events(store)
    store.ingest(RAW, now=NOW)
    for _ in range(10):
        assert store.reserve(now=NOW.replace(hour=14))[1] == 'entry_window_ended'
        assert request(service.application(store.path))['status'] == '503 Service Unavailable'
    assert len(events(store)) == 1


def test_replay_journal_is_never_read_as_prepared_evidence(tmp_path):
    store = service.Store(tmp_path / 'replay.sqlite', mode='replay')
    store.ingest(RAW, now=NOW)
    with pytest.raises(ValueError, match='mode_or_version_refused'):
        journal.read_journal(store.path)


@pytest.mark.parametrize('operation', ['source', 'reserve', 'commit'])
def test_journal_failure_atomically_rolls_back_accepted_service_write(tmp_path, monkeypatch, operation):
    store = store_at(tmp_path)
    claim, _ = store.reserve(now=NOW)
    before = sql(store, 'SELECT * FROM state')
    before_events = events(store)
    monkeypatch.setattr(journal, 'append', failure)
    with pytest.raises(ValueError, match='synthetic journal'):
        if operation == 'source':
            store.ingest(RAW + b'\n', now=NOW)
        elif operation == 'reserve':
            store.reserve(now=NOW + timedelta(seconds=181))
        else:
            store.commit(claim, encode(collect()), now=NOW)
    assert sql(store, 'SELECT * FROM state') == before
    assert events(store) == before_events


def test_provider_attempts_and_completion_are_durable_exact_and_sanitized(tmp_path):
    store, claim, clock = state(tmp_path)
    book = ledger(store, claim, clock)
    attempt = book.reserve('iex')
    clock.move(1)
    book.finish('iex', attempt, status=429, retry_after='600')
    # A duplicate callback cannot relabel a known result or its backoff.
    book.finish('iex', attempt, status=200)
    rows = events(store)
    assert [r['kind'] for r in rows][-2:] == ['provider_reserved', 'provider_finished']
    assert rows[-2]['payload'] == {'feed': 'iex', 'attempt': 1, 'quota_day': NOW.date().isoformat(), 'quota_used': 1}
    assert rows[-1]['payload']['status_code'] == 429
    assert rows[-1]['recorded_at'] == clock().isoformat()
    assert sql(store, "SELECT status_code FROM provider_attempts WHERE feed='iex'") == [(429,)]
    assert '600' not in rows[-1]['payload']


def test_interrupted_provider_request_remains_reserved_unknown_across_restart(tmp_path):
    store, claim, clock = state(tmp_path)
    assert ledger(store, claim, clock).reserve('nasdaq') == 1
    restarted = service.Store(store.path)
    assert len(events(restarted, 'provider_reserved')) == 1
    assert not events(restarted, 'provider_finished')
    assert sql(store, "SELECT used,finished_at FROM provider_attempts WHERE feed='nasdaq'") == [(1, None)]
    with pytest.raises(worker.Deferred, match='interval'):
        ledger(restarted, claim, clock).reserve('nasdaq')


@pytest.mark.parametrize('operation', ['reserve', 'finish'])
def test_provider_journal_failure_rolls_back_quota_or_result(tmp_path, monkeypatch, operation):
    store, claim, clock = state(tmp_path)
    book = ledger(store, claim, clock)
    attempt = book.reserve('iex') if operation == 'finish' else None
    before = sql(store, 'SELECT * FROM provider_attempts')
    monkeypatch.setattr(journal, 'append', failure)
    with pytest.raises(ValueError, match='synthetic journal'):
        book.reserve('iex') if operation == 'reserve' else book.finish('iex', attempt, status=200)
    assert sql(store, 'SELECT * FROM provider_attempts') == before
    assert not events(store, 'provider_finished')


def test_actual_bounded_transport_records_attempts_without_credentials(tmp_path, transport):
    calls, _ = transport
    store, claim, clock = state(tmp_path)
    receipt = worker.collect_claim(store, claim, deadline=25, clock=clock, monotonic=lambda: clock.tick)
    assert store.commit(claim, encode(receipt), now=clock()) == 'committed'
    snapshot = journal.read_journal(store.path)
    assert len(calls) == 3
    assert [r['payload']['feed'] for r in snapshot['events'] if r['kind'] == 'provider_reserved'] == ['iex', 'delayed_sip', 'nasdaq']
    assert len(events(store, 'provider_finished')) == 3
    with sqlite3.connect(store.path) as db:
        dump = '\n'.join(db.iterdump())
    assert 'test-not-a-real-key' not in dump and 'test-not-a-real-secret' not in dump
    assert 'APCA-API-KEY-ID' not in dump


@pytest.mark.parametrize('child,expected', [(_synthetic_child, 'committed'), (_hanging_child, 'worker_deadline')])
def test_supervisor_terminal_outcome_is_recorded_only_after_reaping(tmp_path, child, expected):
    store = store_at(tmp_path)
    result = worker.run_once(store, clock=lambda: NOW, child_target=child,
                             context=multiprocessing.get_context('fork'), seconds=.15 if child == _hanging_child else 25)
    assert result == expected
    assert events(store, 'collection_finished')[0]['payload']['outcome'] == expected
    assert not multiprocessing.active_children()


@pytest.mark.parametrize('cap', ['events', 'bytes', 'age'])
def test_retention_declares_loss_preserves_references_and_never_resets_quota(tmp_path, monkeypatch, cap):
    if cap == 'events':
        monkeypatch.setattr(journal, 'MAX_EVENTS', 2)
    if cap == 'bytes':
        monkeypatch.setattr(journal, 'MAX_BYTES', len(RAW) + 2000)
    if cap == 'age':
        monkeypatch.setattr(journal, 'RETENTION_DAYS', 1)
    store = store_at(tmp_path)
    claim, _ = store.reserve(now=NOW)
    store.commit(claim, encode(collect()), now=NOW)
    if cap == 'age':
        store.ingest(RAW + b'\n', now=NOW + timedelta(days=2))
    else:
        store.ingest(RAW + b'\n', now=NOW + timedelta(seconds=1))
    # Under tiny byte cap a complete event may itself be evicted; never keep
    # an unverifiable event whose referenced source or prior receipt was lost.
    snapshot = journal.read_journal(store.path, max_read_bytes=min(journal.MAX_READ_BYTES, journal.MAX_BYTES))
    assert snapshot['meta']['pruned_events'] > 0
    assert snapshot['meta']['pruned_through_id'] is not None
    for row in snapshot['events']:
        assert row['source_sha256'] in snapshot['blobs']
        for field in ('receipt_sha256', 'previous_receipt_sha256'):
            if row['payload'].get(field):
                assert row['payload'][field] in snapshot['blobs']
    assert sql(store, 'SELECT quota_used,generation FROM state') == [(1, 2)]
    assert sql(store, 'SELECT count(*) FROM morning_journal_blobs WHERE sha256 NOT IN (SELECT sha256 FROM morning_journal_refs)') == [(0,)]
    retained = sum(b['bytes'] for b in snapshot['blobs'].values()) + sum(len(json.dumps(e['payload'], sort_keys=True, separators=(',', ':')).encode()) for e in snapshot['events'])
    assert retained <= journal.MAX_BYTES


def test_read_bound_refuses_before_loading_blobs_and_filters_sessions(tmp_path):
    store = store_at(tmp_path)
    with pytest.raises(ValueError, match='read_exceeds_bound'):
        journal.read_journal(store.path, max_read_bytes=100)
    snapshot = journal.read_journal(store.path, start='2026-09-12', end='2026-09-13', max_read_bytes=100)
    assert snapshot['events'] == [] and snapshot['blobs'] == {}
    assert journal.read_journal(store.path, as_of=NOW - timedelta(seconds=1))['events'] == []


@pytest.mark.parametrize('table,column,value,error', [
    ('morning_journal_events', 'payload', '{}', 'payload_invalid'),
    ('morning_journal_blobs', 'raw', b'changed', 'blob_missing'),
    ('morning_journal_meta', 'version', 2, 'version_refused')])
def test_read_only_report_input_fails_closed_on_corrupt_evidence(tmp_path, table, column, value, error):
    store = store_at(tmp_path)
    with sqlite3.connect(store.path) as db:
        db.execute(f'UPDATE {table} SET {column}=?', (value,))
    with pytest.raises(ValueError, match=error):
        journal.read_journal(store.path)


def test_reader_never_initializes_legacy_database(tmp_path):
    path = tmp_path / 'legacy.sqlite'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE state (mode TEXT)')
        db.execute("INSERT INTO state VALUES ('prepared')")
    before = path.read_bytes()
    with pytest.raises(sqlite3.OperationalError):
        journal.read_journal(path)
    assert path.read_bytes() == before


def test_reader_releases_snapshot_before_hash_validation(tmp_path, monkeypatch):
    store = store_at(tmp_path)
    original = journal.sha
    checked = []
    def check(raw):
        # DELETE journal mode blocks this write if the reader still holds its
        # snapshot. The no-op transaction changes no source or observed fact.
        with sqlite3.connect(store.path, timeout=0) as db:
            db.execute('UPDATE state SET generation=generation WHERE id=1')
        checked.append(True)
        return original(raw)
    monkeypatch.setattr(journal, 'sha', check)
    assert journal.read_journal(store.path)['events']
    assert checked


def test_release_cannot_record_forged_claim_identity(tmp_path):
    store = store_at(tmp_path)
    claim, _ = store.reserve(now=NOW)
    assert not store.release(replace(claim, publication=RAW + b'\n'), now=NOW, outcome='worker_failed')
    assert not events(store, 'collection_finished')
    assert sql(store, 'SELECT lease_until FROM state')[0][0] is not None


def test_raw_exception_text_is_not_a_terminal_reason(tmp_path):
    store = store_at(tmp_path)
    claim, _ = store.reserve(now=NOW)
    with pytest.raises(ValueError, match='release_outcome_invalid'):
        store.release(claim, now=NOW, outcome='APCA-SECRET-KEY: private')
    assert not events(store, 'collection_finished')


def test_orphan_gc_has_digest_index(tmp_path):
    store = store_at(tmp_path)
    plan = sql(store, "EXPLAIN QUERY PLAN SELECT 1 FROM morning_journal_refs WHERE sha256='digest'")
    assert any('morning_journal_refs_sha' in str(row) for row in plan)
