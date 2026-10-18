"""Fixed-repository publication handoff, entirely offline synthetic sources."""
from datetime import timedelta
import hashlib
import io
import json
import sqlite3
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from src import morning_service as service
from tools import sync_morning_service as syncer
from tests.test_morning_service import RAW, NOW, FIXTURES, encode, request, store_at

COMMIT = '1' * 40
NEXT = '2' * 40


def reference(commit=COMMIT):
    return encode({'ref': 'refs/heads/main', 'object': {'type': 'commit', 'sha': commit}})


def metadata(raw=RAW):
    return encode({'type': 'file', 'path': 'docs/data.json', 'size': len(raw), 'sha': syncer.blob_sha(raw)})


class Source:
    def __init__(self, raw=RAW, *, previous=None, edited_ref=None):
        self.raw, self.previous, self.edited_ref = raw, previous, edited_ref
        self.calls, self.refs = [], 0

    def __call__(self, url, maximum, deadline):
        self.calls.append((url, maximum, deadline))
        if url == syncer.REF_URL:
            self.refs += 1
            return reference(self.edited_ref if self.refs > 1 and self.edited_ref else COMMIT)
        if url == syncer.CONTENTS_URL + COMMIT:
            return metadata(self.raw)
        if url == syncer.RAW_ROOT + COMMIT + '/docs/data.json':
            return self.raw
        if url == syncer.RAW_ROOT + COMMIT + '/docs/morning.json':
            if self.previous is None:
                raise syncer.SyncError('source_not_found')
            return self.previous
        raise AssertionError('unexpected source URL')


def run(store, source, at=NOW, **kwargs):
    return syncer.sync(store, transport=source, clock=lambda: at, **kwargs)


def test_bootstrap_verifies_immutable_blob_and_migrates_old_bound_restrictions(tmp_path):
    previous = (FIXTURES / 'halted.json').read_bytes()
    source = Source(RAW + b'\n', previous=previous)
    store = service.Store(tmp_path / 'service.sqlite')
    result = run(store, source)
    assert result == {'status': 'ingested', 'requests': 5, 'commit_sha': COMMIT}
    assert all(COMMIT in url or url == syncer.REF_URL for url, _, _ in source.calls)
    claim, _ = store.reserve(now=NOW)
    assert claim.previous == previous and claim.publication == RAW + b'\n'
    assert request(service.application(store.path))['status'] == '503 Service Unavailable'


def test_unchanged_blob_skips_full_download_even_after_code_only_main_commit(tmp_path):
    store = store_at(tmp_path)
    source = Source()
    result = run(store, source)
    assert result == {'status': 'unchanged', 'requests': 3, 'commit_sha': COMMIT}
    assert all(not url.startswith(syncer.RAW_ROOT) for url, _, _ in source.calls)


def test_poll_interval_is_global_and_persistent_across_restarts(tmp_path):
    store = store_at(tmp_path)
    first = Source()
    assert run(store, first)['status'] == 'unchanged'
    second = Source()
    assert run(service.Store(store.path), second, at=NOW + timedelta(seconds=299)) == {'status': 'poll_interval', 'requests': 0}
    assert second.calls == []
    assert run(service.Store(store.path), second, at=NOW + timedelta(seconds=300))['status'] == 'unchanged'


def test_main_moving_during_fetch_cannot_replace_current_source(tmp_path):
    store = store_at(tmp_path)
    source = Source(RAW + b'\n', edited_ref=NEXT)
    assert run(store, source)['status'] == 'source_main_changed'
    claim, _ = store.reserve(now=NOW)
    assert claim.publication == RAW


def test_concurrent_local_ingestion_is_not_overwritten_by_network_result(tmp_path):
    store = store_at(tmp_path)
    source = Source(RAW + b'\n')
    def concurrent(url, maximum, deadline):
        answer = source(url, maximum, deadline)
        if source.refs == 2:
            store.ingest(RAW + b'  ', now=NOW)
        return answer
    assert run(store, concurrent)['status'] == 'source_record_changed'
    claim, _ = store.reserve(now=NOW)
    assert claim.publication == RAW + b'  '


@pytest.mark.parametrize('alter', [lambda value: value.update(sha='0' * 40),
                                  lambda value: value.update(size=len(RAW) + 1)])
def test_bytes_must_match_git_blob_digest_and_size(tmp_path, alter):
    store = service.Store(tmp_path / 'service.sqlite')
    source = Source()
    def corrupt(url, maximum, deadline):
        result = source(url, maximum, deadline)
        if url.startswith(syncer.CONTENTS_URL):
            value = json.loads(result); alter(value); return encode(value)
        return result
    assert run(store, corrupt)['status'] == 'source_blob_identity_differs'
    assert store.reserve(now=NOW)[1] == 'publication_missing'


def test_missing_bootstrap_receipt_is_distinct_from_invalid_receipt(tmp_path):
    store = service.Store(tmp_path / 'missing.sqlite')
    assert run(store, Source())['status'] == 'ingested'
    other = service.Store(tmp_path / 'invalid.sqlite')
    assert run(other, Source(previous=b'{"wrong":"receipt"}'))['status'] == 'source_publication_or_receipt_invalid'
    assert other.reserve(now=NOW)[1] == 'publication_missing'


def test_bootstrap_receipt_access_failure_refuses_instead_of_discarding_restrictions(tmp_path):
    store = service.Store(tmp_path / 'service.sqlite')
    source = Source()
    def denied(url, maximum, deadline):
        if url.endswith('/docs/morning.json'):
            raise syncer.SyncError('source_access_denied', backoff=3600)
        return source(url, maximum, deadline)
    assert run(store, denied)['status'] == 'source_access_denied'
    assert store.reserve(now=NOW)[1] == 'publication_missing'
    again = Source()
    assert run(service.Store(store.path), again, at=NOW + timedelta(seconds=301))['status'] == 'poll_interval'
    assert again.calls == []


def test_deadline_covers_response_body_completion_and_preserves_original(tmp_path):
    store = store_at(tmp_path)
    elapsed = [0]
    def late(url, maximum, deadline):
        elapsed[0] = 31
        return reference()
    result = run(store, late, monotonic=lambda: elapsed[0])
    assert result['status'] == 'source_deadline_exceeded' and result['requests'] == 1
    claim, _ = store.reserve(now=NOW)
    assert claim.publication == RAW


def test_wall_clock_jumps_cannot_import_a_result_outside_total_deadline(tmp_path):
    store = store_at(tmp_path)
    calls = iter([NOW, NOW + timedelta(seconds=31), NOW + timedelta(seconds=31)])
    assert syncer.sync(store, transport=Source(RAW + b'\n'), clock=lambda: next(calls))['status'] == 'source_deadline_exceeded'


@pytest.mark.parametrize('payload', [b'[]', b'not JSON', encode({'ref': 'refs/heads/other', 'object': {'type': 'commit','sha': COMMIT}}),
                                     encode({'ref': 'refs/heads/main', 'object': {'type': 'tag','sha': COMMIT}})])
def test_ref_descriptor_shape_is_not_trusted(tmp_path, payload):
    store = service.Store(tmp_path / 'service.sqlite')
    assert run(store, lambda *args: payload)['status'] in ('source_metadata_invalid', 'source_ref_invalid')
    assert store.reserve(now=NOW)[1] == 'publication_missing'


def test_metadata_cannot_supply_an_arbitrary_download_url(tmp_path):
    store = service.Store(tmp_path / 'service.sqlite')
    source = Source()
    def changed(url, maximum, deadline):
        result = source(url, maximum, deadline)
        if url.startswith(syncer.CONTENTS_URL):
            value = json.loads(result); value['download_url'] = 'https://attacker.invalid/private'; return encode(value)
        return result
    assert run(store, changed)['status'] == 'ingested'
    assert all('attacker' not in url for url, _, _ in source.calls)


def test_transport_failure_spends_reserved_poll_and_has_generic_status(tmp_path):
    store = service.Store(tmp_path / 'service.sqlite')
    def unavailable(*args):
        raise OSError('private proxy response must not escape')
    result = run(store, unavailable)
    assert result['status'] == 'source_transport_unavailable' and result['requests'] == 1
    assert 'private' not in json.dumps(result)
    with sqlite3.connect(store.path) as db:
        assert db.execute('SELECT request_count,last_status FROM morning_source_sync').fetchone() == (1, 'source_transport_unavailable')
    assert run(service.Store(store.path), Source(), at=NOW + timedelta(seconds=1))['status'] == 'poll_interval'


def test_sync_refuses_replay_storage(tmp_path):
    store = service.Store(tmp_path / 'replay.sqlite', mode='replay')
    source = Source()
    with pytest.raises(syncer.SyncError, match='replay'):
        run(store, source)
    assert source.calls == []


class Response:
    def __init__(self, chunks, headers=None):
        self.chunks = iter(chunks)
        self.headers = headers or {}
        self.timeouts = []
        self.fp = SimpleNamespace(raw=SimpleNamespace(_sock=SimpleNamespace(settimeout=self.timeouts.append)))
    def read1(self, amount):
        return next(self.chunks)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


def test_real_transport_bounds_stream_and_shrinks_socket_deadline(monkeypatch):
    response = Response([b'{}', b''])
    requests = []
    def open_(request, timeout):
        requests.append((request, timeout))
        return response
    monkeypatch.setattr(syncer, 'build_opener', lambda *args: SimpleNamespace(open=open_))
    ticks = iter([0, 26, 27, 28, 29])
    monkeypatch.setattr(syncer.time, 'monotonic', lambda: next(ticks))
    assert syncer.fetch(syncer.REF_URL, 100, 30) == b'{}'
    assert response.timeouts == [4, 2]
    headers = dict(requests[0][0].header_items())
    assert headers['Accept-encoding'] == 'identity'
    assert not any('auth' in h.lower() for h in headers)


@pytest.mark.parametrize('response', [Response([b'abc', b'']), Response([b''], {'Content-Length': '100'})])
def test_transport_enforces_header_and_actual_body_bounds(monkeypatch, response):
    monkeypatch.setattr(syncer, 'build_opener', lambda *args: SimpleNamespace(open=lambda *a, **k: response))
    monkeypatch.setattr(syncer.time, 'monotonic', lambda: 0)
    with pytest.raises(syncer.SyncError, match='exceeds_bound'):
        syncer.fetch(syncer.REF_URL, 2, 30)


@pytest.mark.parametrize('code,reason', [(403, 'source_access_denied'), (429, 'source_rate_limit'), (404, 'source_not_found'), (500, 'source_http_error')])
def test_http_errors_are_typed_without_response_bodies(monkeypatch, code, reason):
    def denied(*args, **kwargs):
        raise HTTPError(syncer.REF_URL, code, 'private error', {'Retry-After': '999999'}, io.BytesIO(b'private response'))
    monkeypatch.setattr(syncer, 'build_opener', lambda *args: SimpleNamespace(open=denied))
    monkeypatch.setattr(syncer.time, 'monotonic', lambda: 0)
    with pytest.raises(syncer.SyncError) as found:
        syncer.fetch(syncer.REF_URL, 100, 30)
    assert found.value.reason == reason
    assert found.value.backoff <= syncer.MAX_ERROR_BACKOFF_SECONDS
    assert 'private' not in str(found.value)


def test_redirects_are_refused():
    with pytest.raises(syncer.SyncError, match='redirect'):
        syncer._NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.invalid')
