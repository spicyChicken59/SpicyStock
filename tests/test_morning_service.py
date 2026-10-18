"""Provider-free service controls using the unchanged production validators.

The publication/snapshots are explicitly synthetic retained fixtures. Assertions
establish adapter behavior, never live data, orders, fills or delivery timing.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from src import morning, morning_service as service
from tests.test_morning import Client, event_outage

FIXTURES = Path(__file__).parent / 'fixtures' / 'morning'
NOW = datetime(2026, 9, 11, 13, 35, tzinfo=timezone.utc)
RAW = (FIXTURES / 'full-publication.json').read_bytes()
RED = (FIXTURES / 'red-publication.json').read_bytes()


def encode(value):
    return json.dumps(value, allow_nan=False, separators=(',', ':')).encode() + b'\n'


def collect(raw=RAW, at=NOW, previous=None, client=None, observer=event_outage):
    return morning.collect(raw, clock=lambda: at, client=client or Client(),
                           event_observer=observer, previous_raw=previous,
                           observation_run_id='synthetic-service-test')


def request(app, *, method='GET', path='/morning.json', query='', length='', **more):
    response = {}
    def start(status, headers):
        response.update(status=status, headers=dict(headers))
    response['body'] = b''.join(app({'REQUEST_METHOD': method, 'PATH_INFO': path,
                                    'QUERY_STRING': query, 'CONTENT_LENGTH': length, **more}, start))
    return response


def store_at(tmp_path, *, raw=RAW, policy=None, previous=None):
    store = service.Store(tmp_path / 'morning.sqlite', policy)
    assert store.ingest(raw, now=NOW, previous=previous) == 'ingested'
    return store


def test_real_collector_through_scheduler_retains_exact_source_and_serves_bytes(tmp_path):
    store = store_at(tmp_path)
    client = Client()
    def collector(raw, **kwargs):
        return morning.collect(raw, client=client, event_observer=event_outage, **kwargs)
    assert service.collect_once(store, collector, clock=lambda: NOW) == 'committed'
    response = request(service.application(store.path))
    receipt = json.loads(response['body'])
    morning.validate_observation(receipt, RAW, require_continuity=True)
    assert response['status'] == '200 OK'
    assert [r.feed.value for r in client.requests] == ['iex', 'delayed_sip']
    assert receipt['publication'] == morning.bind_record(RAW)
    assert receipt['dry_run'] is False and len(receipt['rows']) == 1
    assert receipt['coverage']['earnings']['status'] == 'not_checked'
    assert response['headers']['ETag'] == '"' + hashlib.sha256(response['body']).hexdigest() + '"'
    assert response['headers']['Cache-Control'] == 'no-store'


def test_parallel_workers_have_exactly_one_durable_reservation(tmp_path):
    store = store_at(tmp_path)
    def attempt(_):
        return service.Store(store.path).reserve(now=NOW)
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(attempt, range(16)))
    assert sum(claim is not None for claim, reason in results) == 1
    assert sorted(reason for claim, reason in results).count('collection_in_progress') == 15


def test_expired_worker_is_fenced_and_cannot_release_replacement(tmp_path):
    policy = service.Policy(lease_seconds=20)
    store = store_at(tmp_path, policy=policy)
    old, _ = store.reserve(now=NOW)
    later = NOW + timedelta(seconds=31)
    current, reason = service.Store(store.path, policy).reserve(now=later)
    assert reason == 'reserved' and current.fence > old.fence
    assert store.release(old, now=later) is False
    assert store.commit(old, encode(collect(at=later)), now=later) == 'lease_superseded'
    assert store.commit(current, encode(collect(at=later)), now=later) == 'committed'


def test_expired_lease_cannot_commit_even_before_a_replacement(tmp_path):
    store = store_at(tmp_path, policy=service.Policy(lease_seconds=10))
    claim, _ = store.reserve(now=NOW)
    later = NOW + timedelta(seconds=10)
    assert store.commit(claim, encode(collect(at=later)), now=later) == 'lease_expired'
    assert request(service.application(store.path))['status'] == '503 Service Unavailable'


def test_claim_clocks_cannot_be_forged_to_admit_pre_reservation_receipt(tmp_path):
    store = store_at(tmp_path)
    later = NOW + timedelta(seconds=31)
    claim, _ = store.reserve(now=later)
    forged = replace(claim, started_at=NOW.isoformat())
    assert store.commit(forged, encode(collect()), now=later) == 'lease_superseded'


def test_failed_collections_spend_quota_across_restart_and_interval_is_global(tmp_path):
    policy = service.Policy(daily_reservations=2)
    store = store_at(tmp_path, policy=policy)
    first, _ = store.reserve(now=NOW)
    assert store.release(first, now=NOW)
    restarted = service.Store(store.path, policy)
    assert restarted.reserve(now=NOW + timedelta(seconds=29))[1] == 'collection_interval'
    second, _ = restarted.reserve(now=NOW + timedelta(seconds=30))
    assert restarted.release(second, now=NOW + timedelta(seconds=30))
    assert service.Store(store.path, policy).reserve(now=NOW + timedelta(seconds=60))[1] == 'daily_reservation_budget'
    with pytest.raises(ValueError, match='policy_differs'):
        service.Store(store.path, service.Policy(daily_reservations=3))


@pytest.mark.parametrize('policy', [dict(interval_seconds=29), dict(daily_reservations=121),
                                  dict(lease_seconds=181), dict(lease_seconds=0), dict(interval_seconds=True)])
def test_reservation_policy_cannot_relax_hard_caps(policy):
    with pytest.raises(ValueError):
        service.Policy(**policy)


@pytest.mark.parametrize('at,reason', [
    (NOW.replace(hour=12, minute=59), 'before_collection_window'),
    (NOW.replace(hour=14, minute=0), 'entry_window_ended'),
    (NOW + timedelta(days=1), 'wrong_session')])
def test_off_window_ticks_call_no_collector(tmp_path, at, reason):
    store = service.Store(tmp_path / 'morning.sqlite')
    store.ingest(RAW, now=min(NOW, at))
    calls = []
    assert service.collect_once(store, lambda *a, **k: calls.append(1), clock=lambda: at) == reason
    assert calls == []


def test_no_ticket_receipt_is_usable_and_spends_no_source_calls(tmp_path):
    store = store_at(tmp_path, raw=RED)
    client = Client()
    def collector(raw, **kwargs):
        return morning.collect(raw, client=client, event_observer=event_outage, **kwargs)
    assert service.collect_once(store, collector, clock=lambda: NOW) == 'committed'
    receipt = json.loads(request(service.application(store.path))['body'])
    assert receipt['status'] == 'no_tickets' and client.requests == []
    assert receipt['coverage']['halts']['status'] == 'not_requested'


def test_same_session_revision_invalidates_lease_and_preserves_prior_bytes(tmp_path):
    previous = (FIXTURES / 'halted.json').read_bytes()
    store = store_at(tmp_path, previous=previous)
    first_at = NOW + timedelta(seconds=1)
    first, _ = store.reserve(now=first_at)
    updated = RAW + b'\n'
    assert store.ingest(updated, now=first_at) == 'ingested'
    assert request(service.application(store.path))['status'] == '503 Service Unavailable'
    assert store.commit(first, encode(collect(previous=previous, at=first_at)), now=first_at) == 'source_record_changed'
    later = NOW + timedelta(seconds=31)
    current, _ = store.reserve(now=later)
    assert current.previous == previous and current.publication == updated
    value = collect(updated, at=later, previous=current.previous)
    assert value['halt_memory']
    assert store.commit(current, encode(value), now=later) == 'committed'
    assert json.loads(request(service.application(store.path))['body'])['halt_memory'] == value['halt_memory']


def test_same_publication_unchanged_does_not_cancel_active_lease(tmp_path):
    store = store_at(tmp_path)
    claim, _ = store.reserve(now=NOW)
    assert store.ingest(RAW, now=NOW) == 'unchanged'
    assert store.commit(claim, encode(collect()), now=NOW) == 'committed'


def test_prior_receipt_changed_during_collection_cannot_be_overwritten(tmp_path):
    store = store_at(tmp_path)
    claim, _ = store.reserve(now=NOW)
    receipt = encode(collect())
    # Simulate a competing trusted writer at the storage boundary; commit must
    # compare the stored prior receipt as well as its source and lease.
    with sqlite3.connect(store.path) as db:
        db.execute('UPDATE state SET receipt=?,receipt_sha=?', (receipt, hashlib.sha256(receipt).hexdigest()))
    assert store.commit(claim, receipt, now=NOW) == 'previous_observation_changed'


def test_validation_refuses_tampered_levels_rehearsal_and_copy_of_source_hash(tmp_path):
    store = store_at(tmp_path)
    claim, _ = store.reserve(now=NOW)
    value = collect()
    value['rows'][0]['levels']['limit'] += 1
    with pytest.raises(ValueError):
        store.commit(claim, encode(value), now=NOW)
    value = collect()
    value['dry_run'] = True
    with pytest.raises(ValueError, match='rehearsal'):
        store.commit(claim, encode(value), now=NOW)
    value = collect()
    value['publication']['reader_sha256'] = 'a' * 64
    with pytest.raises(ValueError):
        store.commit(claim, encode(value), now=NOW)
    assert request(service.application(store.path))['status'] == '503 Service Unavailable'


def test_outage_retains_existing_halt_and_corporate_restrictions(tmp_path):
    previous = (FIXTURES / 'corporate-excluded.json').read_bytes()
    store = store_at(tmp_path, previous=previous)
    later = NOW + timedelta(seconds=31)
    claim, _ = store.reserve(now=later)
    value = collect(at=later, previous=previous, client=Client(errors=['iex', 'delayed_sip']))
    assert value['status'] == 'provider_unavailable'
    assert value['corporate_memory'] == json.loads(previous)['corporate_memory']
    assert store.commit(claim, encode(value), now=later) == 'committed'


def test_bad_callback_releases_lease_without_refunding_budget(tmp_path):
    store = store_at(tmp_path, policy=service.Policy(daily_reservations=1))
    def broken(*args, **kwargs):
        raise RuntimeError('synthetic transport failure')
    with pytest.raises(RuntimeError, match='synthetic'):
        service.collect_once(store, broken, clock=lambda: NOW)
    assert store.reserve(now=NOW + timedelta(seconds=31))[1] == 'daily_reservation_budget'


def test_backwards_clock_refused_without_resetting_state(tmp_path):
    store = store_at(tmp_path)
    claim, _ = store.reserve(now=NOW)
    with pytest.raises(ValueError, match='backwards'):
        store.reserve(now=NOW - timedelta(seconds=1))
    assert store.commit(claim, encode(collect()), now=NOW) == 'committed'


def test_http_traffic_performs_no_writes_and_never_restarts_collection(tmp_path, monkeypatch):
    receipt = encode(collect())
    store = store_at(tmp_path, previous=receipt)
    before = store.path.read_bytes()
    def unexpected(*args, **kwargs):
        raise AssertionError('HTTP triggered writer or collector')
    monkeypatch.setattr(morning, 'collect', unexpected)
    monkeypatch.setattr(service.Store, '__init__', unexpected)
    app = service.application(store.path)
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: request(app), range(100)))
    assert all(r['status'] == '200 OK' and r['body'] == receipt for r in results)
    assert store.path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [store.path]


@pytest.mark.parametrize('arguments,status', [
    ({'method': 'POST'}, '405'), ({'method': 'HEAD'}, '405'),
    ({'path': '/morning.json/refresh'}, '404'), ({'path': '/private'}, '404'),
    ({'query': 'ticker=PRIVATE&cash=2000'}, '400'), ({'length': '2'}, '400'),
    ({'HTTP_TRANSFER_ENCODING': 'chunked'}, '400')])
def test_http_refuses_parameters_methods_and_other_paths(tmp_path, arguments, status):
    path = tmp_path / 'absent.sqlite'
    response = request(service.application(path), **arguments)
    assert response['status'].startswith(status)
    assert not path.exists()
    assert b'PRIVATE' not in response['body']
    assert 'Access-Control-Allow-Origin' not in response['headers']


def test_http_missing_or_corrupt_state_has_bounded_generic_unavailability(tmp_path):
    path = tmp_path / 'absent.sqlite'
    assert request(service.application(path))['status'] == '503 Service Unavailable'
    assert not path.exists()
    store = store_at(tmp_path, previous=encode(collect()))
    with sqlite3.connect(store.path) as db:
        db.execute('UPDATE state SET receipt=?', (b'{"private":"do not expose"}',))
    response = request(service.application(store.path))
    assert response['status'] == '503 Service Unavailable'
    assert b'private' not in response['body'] and len(response['body']) < 100


def test_http_preserves_expired_receipt_original_clocks(tmp_path):
    receipt = encode(collect())
    store = store_at(tmp_path, previous=receipt)
    response = request(service.application(store.path))
    assert response['body'] == receipt  # no serving-time restamp or invented quote
    assert json.loads(response['body'])['generated_at'] == NOW.isoformat()


def test_cli_replay_is_persistently_separate_and_cannot_be_served(tmp_path, capsys):
    path = tmp_path / 'replay.sqlite'
    assert service.main(['--database', str(path), 'replay', '--publication',
                         str(FIXTURES / 'full-publication.json'), '--receipt',
                         str(FIXTURES / 'observed.json')]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['mode'] == 'offline_replay' and result['result'] == 'committed'
    assert request(service.application(path))['status'] == '503 Service Unavailable'
    with pytest.raises(ValueError, match='policy_differs'):
        service.Store(path)


def test_cli_refuses_replay_into_prepared_database(tmp_path, capsys):
    store = store_at(tmp_path)
    before = store.path.read_bytes()
    assert service.main(['--database', str(store.path), 'replay', '--publication',
                         str(FIXTURES / 'full-publication.json'), '--receipt',
                         str(FIXTURES / 'observed.json')]) == 1
    assert json.loads(capsys.readouterr().out)['status'] == 'refused'
    assert store.path.read_bytes() == before


def test_bootstrap_requires_verified_non_future_receipt(tmp_path):
    value = collect()
    value['dry_run'] = True
    with pytest.raises(ValueError, match='rehearsal'):
        store_at(tmp_path, previous=encode(value))
    value = collect(at=NOW + timedelta(minutes=1))
    with pytest.raises(ValueError, match='future'):
        store_at(tmp_path, previous=encode(value))


def test_bootstrap_cannot_overwrite_existing_receipt(tmp_path):
    store = store_at(tmp_path, previous=encode(collect()))
    with pytest.raises(ValueError, match='only_at_bootstrap'):
        store.ingest(RAW, now=NOW, previous=(FIXTURES / 'halted.json').read_bytes())


def test_provider_adapter_transaction_requires_current_claim_and_open_window(tmp_path):
    store = store_at(tmp_path)
    claim, _ = store.reserve(now=NOW)
    with store.request_transaction(claim, now=NOW) as db:
        db.execute('CREATE TABLE adapter_test (attempt INTEGER)')
        db.execute('INSERT INTO adapter_test VALUES (1)')
    store.release(claim, now=NOW)
    with pytest.raises(ValueError, match='claim_inactive'):
        with store.request_transaction(claim, now=NOW):
            raise AssertionError('stale claim admitted')
    with sqlite3.connect(store.path) as db:
        assert db.execute('SELECT COUNT(*) FROM adapter_test').fetchone()[0] == 1


def test_provider_adapter_cannot_start_an_attempt_at_cutoff(tmp_path):
    store = store_at(tmp_path)
    before_cutoff = NOW.replace(hour=13, minute=59, second=50)
    claim, _ = store.reserve(now=before_cutoff)
    with pytest.raises(ValueError, match='outside_window'):
        with store.request_transaction(claim, now=before_cutoff + timedelta(seconds=10)):
            raise AssertionError('post-cutoff attempt admitted')


def test_cors_opt_in_is_exact_public_read_only_origin_without_credentials(tmp_path):
    store = store_at(tmp_path, previous=encode(collect()))
    allowed = 'https://spicychicken59.github.io'
    app = service.application(store.path, allowed_origin=allowed)
    matched = request(app, HTTP_ORIGIN=allowed)
    assert matched['headers']['Access-Control-Allow-Origin'] == allowed
    assert matched['headers']['Vary'] == 'Origin'
    assert 'Access-Control-Allow-Credentials' not in matched['headers']
    assert 'Access-Control-Allow-Origin' not in request(app, HTTP_ORIGIN='https://foreign.example')['headers']
    assert 'Access-Control-Allow-Origin' not in request(app)['headers']


@pytest.mark.parametrize('origin', ['*', 'http://example.com', 'https://user@example.com',
                                    'https://example.com/path', 'https://example.com/',
                                    'https://example.com?secret=x', 'https://example.com#part',
                                    'https://example.com:bad', 'https://example.com\n'])
def test_cors_refuses_unscoped_or_malformed_origin(tmp_path, origin):
    with pytest.raises(ValueError):
        service.application(tmp_path / 'absent.sqlite', allowed_origin=origin)


def test_bootstrap_previous_publication_keeps_independently_validated_restrictions(tmp_path):
    previous = (FIXTURES / 'halted.json').read_bytes()
    changed = RAW + b'\n'
    store = store_at(tmp_path, raw=changed, previous=previous)
    assert request(service.application(store.path))['status'] == '503 Service Unavailable'
    later = NOW + timedelta(seconds=31)
    claim, _ = store.reserve(now=later)
    assert claim.previous == previous
    value = collect(changed, at=later, previous=claim.previous)
    assert value['halt_memory'] == json.loads(previous)['halt_memory']
    assert store.commit(claim, encode(value), now=later) == 'committed'
    response = request(service.application(store.path))
    assert response['status'] == '200 OK'
    assert json.loads(response['body'])['publication']['data_sha256'] == hashlib.sha256(changed).hexdigest()


def test_unchanged_ingest_advances_clock_without_replacing_lease(tmp_path):
    store = store_at(tmp_path)
    claim, _ = store.reserve(now=NOW)
    later = NOW + timedelta(seconds=1)
    assert store.ingest(RAW, now=later) == 'unchanged'
    with pytest.raises(ValueError, match='backwards'):
        store.reserve(now=NOW)
    assert store.commit(claim, encode(collect(at=later)), now=later) == 'committed'
