"""Synthetic provider transport and historical-clock controls; never live calls."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import io
import json
import multiprocessing
from pathlib import Path
import sqlite3
import time
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
from alpaca.data.enums import DataFeed
from alpaca.data.requests import StockSnapshotRequest

from src import morning, morning_halts, morning_service as service, morning_service_worker as worker
from tests.test_morning import Client, event_outage
from tests.test_morning_halts import edit_feed

NOW = datetime(2026, 9, 11, 13, 35, tzinfo=timezone.utc)
RAW = (Path(__file__).parent / 'fixtures/morning/full-publication.json').read_bytes()
RED = (Path(__file__).parent / 'fixtures/morning/red-publication.json').read_bytes()
HALTS = edit_feed(keep=[], publication=format_datetime(NOW))


class Clock:
    def __init__(self, at=NOW):
        self.at = at
        self.tick = 0
    def __call__(self):
        return self.at
    def move(self, seconds):
        self.at += timedelta(seconds=seconds)
        self.tick += seconds


def state(tmp_path, *, at=NOW, raw=RAW, previous=None, policy=None):
    clock = Clock(at)
    store = service.Store(tmp_path / 'worker.sqlite', policy)
    store.ingest(raw, now=clock(), previous=previous)
    claim, reason = store.reserve(now=clock())
    assert reason == 'reserved'
    return store, claim, clock


def ledger(store, claim, clock):
    return worker.Ledger(store, claim, deadline=clock.tick + 25, clock=clock, monotonic=lambda: clock.tick)


def snapshot(feed, at):
    observed = at if feed == 'iex' else at - timedelta(minutes=15)
    bar = {'t': NOW.replace(hour=4, minute=0).isoformat(), 'o': 124, 'h': 126, 'l': 123, 'c': 125, 'v': 200, 'n': 2, 'vw': 125}
    return {'AAPL': {
        'latestTrade': {'t': observed.isoformat(), 'p': 125, 's': 10, 'x': 'V', 'c': ['@'], 'i': 1, 'z': 'C'},
        'latestQuote': {'t': observed.isoformat(), 'bp': 125, 'ap': 125.02, 'bs': 100, 'as': 200, 'bx': 'V', 'ax': 'V', 'c': ['R'], 'z': 'C'},
        'minuteBar': bar, 'dailyBar': bar,
        'prevDailyBar': {**bar, 't': (NOW - timedelta(days=1)).replace(hour=4, minute=0).isoformat(), 'v': 100}}}


def response(request, body, status=200, headers=None):
    out = requests.Response()
    out.status_code = status
    out.url, out.request = request.url, request
    out.headers.update(headers or {})
    out.raw = io.BytesIO(body if isinstance(body, bytes) else json.dumps(body).encode())
    return out


@pytest.fixture
def transport(monkeypatch):
    monkeypatch.setenv('ALPACA_API_KEY', 'test-not-a-real-key')
    monkeypatch.setenv('ALPACA_SECRET_KEY', 'test-not-a-real-secret')
    calls = []
    behavior = {'clock': lambda: NOW}
    def send(adapter, request, **kwargs):
        calls.append((request, kwargs, adapter.max_retries.total))
        if behavior.get('callback'):
            return behavior['callback'](request)
        if request.url == morning_halts.SOURCE_URL:
            return response(request, HALTS, headers={'Date': format_datetime(NOW)})
        feed = parse_qs(urlsplit(request.url).query)['feed'][0]
        return response(request, snapshot(feed, behavior['clock']()))
    monkeypatch.setattr(requests.adapters.HTTPAdapter, 'send', send)
    return calls, behavior


def test_actual_sdk_and_production_collector_exact_bytes_and_bounded_transport(tmp_path, transport):
    calls, _ = transport
    store, claim, clock = state(tmp_path)
    value = worker.collect_claim(store, claim, deadline=25, clock=clock, monotonic=lambda: clock.tick)
    morning.validate_observation(value, RAW, previous_raw=claim.previous, require_continuity=True)
    assert value['dry_run'] is False and value['status'] == 'observed'
    assert value['publication'] == morning.bind_record(RAW)
    assert value['coverage']['halts']['status'] == 'fresh'
    assert value['coverage']['issuer_news']['status'] == value['coverage']['earnings']['status'] == 'not_checked'
    assert [parse_qs(urlsplit(r.url).query).get('feed', ['nasdaq'])[0] for r, _, _ in calls] == ['iex', 'delayed_sip', 'tradehalts']
    assert all(k['timeout'] == (3, 4) and k['stream'] is True and retries == 0 for _, k, retries in calls)
    assert all(r.headers['Accept-Encoding'] == 'identity' for r, _, _ in calls)
    assert calls[0][0].headers['APCA-API-KEY-ID'] == 'test-not-a-real-key'
    assert 'APCA-API-KEY-ID' not in calls[-1][0].headers
    assert store.commit(claim, service._encode(value), now=clock()) == 'committed'


@pytest.mark.parametrize('status,kind', [(401, 'authentication'), (403, 'entitlement'), (429, 'rate_limit'), (500, 'provider_error')])
def test_failed_http_attempts_charged_once_no_sdk_retry_and_persistent_backoff(tmp_path, transport, status, kind):
    calls, behavior = transport
    store, claim, clock = state(tmp_path)
    behavior['callback'] = lambda request: response(request, b'private response details', status, {'Retry-After': '600'})
    first = ledger(store, claim, clock)
    client = worker.sdk_client(first)
    assert client._retry == 0
    request = StockSnapshotRequest(symbol_or_symbols=['AAPL'], feed=DataFeed.IEX)
    with pytest.raises(worker.Deferred) as exc:
        client.get_stock_snapshot(request)
    assert morning._error(exc.value) == kind
    assert len(calls) == 1
    clock.move(20)
    restarted = worker.sdk_client(ledger(service.Store(store.path), claim, clock))
    with pytest.raises(worker.Deferred, match='backoff'):
        restarted.get_stock_snapshot(request)
    assert len(calls) == 1
    with sqlite3.connect(store.path) as db:
        used, until = db.execute('SELECT used,backoff_until FROM provider_attempts WHERE feed="iex"').fetchone()
    expected = (NOW + timedelta(days=1)).replace(hour=0, minute=0) if status in (401, 403) else NOW + timedelta(seconds=600 if status == 429 else 60)
    assert used == 1 and until == expected.timestamp()


def test_timeout_is_charged_and_generic_error_backoff_survives_restart(tmp_path, transport):
    calls, behavior = transport
    store, claim, clock = state(tmp_path)
    def timeout(request):
        raise requests.ReadTimeout('synthetic secret must not be public')
    behavior['callback'] = timeout
    first = worker.collect_claim(store, claim, deadline=25, clock=clock, monotonic=lambda: clock.tick)
    assert first['status'] == 'provider_unavailable'
    assert all(v['error_kind'] == 'timeout' for v in first['sources'].values())
    assert 'synthetic secret' not in json.dumps(first)
    assert len(calls) == 3
    for feed in worker.FEEDS:
        with pytest.raises(worker.Deferred, match='backoff'):
            ledger(service.Store(store.path), claim, clock).reserve(feed)


def test_parallel_transport_reservations_charge_only_one(tmp_path):
    store, claim, clock = state(tmp_path)
    ledger(store, claim, clock)
    def reserve(_):
        try:
            return ledger(service.Store(store.path), claim, clock).reserve('nasdaq')
        except worker.Deferred as exc:
            return str(exc)
    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(reserve, range(12)))
    assert outcomes.count(1) == 1 and outcomes.count('worker_provider_interval') == 11


def test_durable_nasdaq_cache_preserves_original_time_with_60_second_floor(tmp_path, transport):
    calls, behavior = transport
    store, claim, clock = state(tmp_path)
    def collect(current):
        return worker.collect_claim(store, current, deadline=clock.tick + 25, clock=clock, monotonic=lambda: clock.tick)
    first = collect(claim)
    assert store.commit(claim, service._encode(first), now=clock()) == 'committed'
    clock.move(30)
    behavior['clock'] = clock
    second_claim, _ = service.Store(store.path).reserve(now=clock())
    second = collect(second_claim)
    assert len(calls) == 5
    assert second['coverage']['halts']['fetched_at'] == first['coverage']['halts']['fetched_at']
    assert second['coverage']['halts']['receipt_age_seconds'] == 30
    assert store.commit(second_claim, service._encode(second), now=clock()) == 'committed'
    clock.move(30)
    third_claim, _ = service.Store(store.path).reserve(now=clock())
    third = collect(third_claim)
    assert len(calls) == 8
    assert third['coverage']['halts']['fetched_at'] != first['coverage']['halts']['fetched_at']
    assert third['previous_observation_sha256'] == service._sha(service._encode(second))


def test_failed_nasdaq_attempt_obeys_global_floor_without_cache(tmp_path, transport):
    calls, behavior = transport
    store, claim, clock = state(tmp_path)
    behavior['callback'] = lambda request: response(request, b'failure', 500)
    with pytest.raises(worker.Deferred):
        worker.BoundedSession(ledger(store, claim, clock)).get(morning_halts.SOURCE_URL)
    store.release(claim, now=clock())
    clock.move(30)
    second, _ = service.Store(store.path).reserve(now=clock())
    with pytest.raises(worker.Deferred, match='backoff'):
        worker.BoundedSession(ledger(store, second, clock)).get(morning_halts.SOURCE_URL)
    assert len(calls) == 1


@pytest.mark.parametrize('feed', ['iex', 'delayed_sip', 'nasdaq'])
def test_daily_budget_is_durable_and_charges_reserved_failures(tmp_path, feed):
    store, claim, clock = state(tmp_path)
    first = ledger(store, claim, clock)
    first.reserve(feed)
    # Seed an exhausted durable day, representing previous charged attempts;
    # do not relax the production cap to make a small test convenient.
    with sqlite3.connect(store.path) as db:
        db.execute('UPDATE provider_attempts SET used=?,last_at=? WHERE feed=?', (worker.FEEDS[feed][1], NOW.timestamp() - 61, feed))
    with pytest.raises(worker.Deferred, match='daily_budget') as refused:
        ledger(service.Store(store.path), claim, clock).reserve(feed)
    assert refused.value.local_reason == 'local_budget' and refused.value.status_code is None


def test_global_fence_stops_later_feeds_and_drops_late_cache(tmp_path, transport):
    calls, behavior = transport
    store, claim, clock = state(tmp_path)
    def replace_source(request):
        store.ingest(RAW + b'\n', now=clock())
        return response(request, snapshot('iex', clock()))
    behavior['callback'] = replace_source
    with pytest.raises(ValueError, match='claim_inactive'):
        worker.collect_claim(store, claim, deadline=25, clock=clock, monotonic=lambda: clock.tick)
    assert len(calls) == 1
    with sqlite3.connect(store.path) as db:
        assert db.execute('SELECT count(*) FROM provider_cache').fetchone()[0] == 0
        assert db.execute('SELECT used FROM provider_attempts').fetchone()[0] == 1


def test_cutoff_reached_in_first_feed_prevents_all_later_calls(tmp_path, transport):
    calls, behavior = transport
    store, claim, clock = state(tmp_path, at=NOW.replace(hour=13, minute=59, second=59))
    def finish_after_cutoff(request):
        clock.move(1)
        return response(request, snapshot('iex', clock()))
    behavior['callback'] = finish_after_cutoff
    with pytest.raises(ValueError, match='outside_window'):
        worker.collect_claim(store, claim, deadline=25, clock=clock, monotonic=lambda: clock.tick)
    assert len(calls) == 1


def test_monotonic_deadline_stops_drip_feed_and_later_sources(tmp_path, transport):
    calls, behavior = transport
    store, claim, clock = state(tmp_path)
    class Drip:
        def stream(self, size, decode_content=True):
            yield b'{'  # one harmless first chunk
            clock.tick = 25
            yield b'}'
        def close(self):
            pass
    def drip(request):
        out = response(request, b'')
        out.raw = Drip()
        return out
    behavior['callback'] = drip
    with pytest.raises(worker.Deferred, match='deadline'):
        worker.collect_claim(store, claim, deadline=25, clock=clock, monotonic=lambda: clock.tick)
    assert len(calls) == 1


@pytest.mark.parametrize('url,kwargs', [
    ('http://data.alpaca.markets/v2/stocks/snapshots', {}),
    ('https://data.alpaca.markets/v2/stocks/bars', {}),
    ('https://example.test/private', {}),
    (worker.ALPACA_URL, {'params': {'feed': 'sip', 'symbols': 'AAPL'}}),
    (worker.ALPACA_URL, {'params': {'feed': 'iex', 'symbols': 'EXTRA'}}),
    (worker.ALPACA_URL, {'params': {'feed': 'iex', 'symbols': 'AAPL', 'page_token': 'more'}}),
    (morning_halts.SOURCE_URL, {'params': {'private': 'secret'}}),
])
def test_endpoint_and_params_allowlist_refuses_before_any_attempt(tmp_path, transport, url, kwargs):
    calls, _ = transport
    store, claim, clock = state(tmp_path)
    with pytest.raises(worker.Deferred):
        worker.BoundedSession(ledger(store, claim, clock)).get(url, **kwargs)
    assert calls == []


@pytest.mark.parametrize('status', [301, 302, 307, 308])
def test_redirect_never_follows_or_leaks_auth(tmp_path, transport, status):
    calls, behavior = transport
    store, claim, clock = state(tmp_path)
    behavior['callback'] = lambda request: response(request, b'', status, {'Location': 'https://example.test/collect'})
    with pytest.raises(worker.Deferred):
        worker.sdk_client(ledger(store, claim, clock)).get_stock_snapshot(StockSnapshotRequest(symbol_or_symbols=['AAPL'], feed=DataFeed.IEX))
    assert len(calls) == 1 and urlsplit(calls[0][0].url).hostname == 'data.alpaca.markets'


def test_snapshot_response_byte_cap_charges_attempt(tmp_path, transport):
    calls, behavior = transport
    store, claim, clock = state(tmp_path)
    behavior['callback'] = lambda request: response(request, b'x' * (worker.MAX_SNAPSHOT_BYTES + 1))
    with pytest.raises(worker.Deferred, match='exceeds_bound'):
        worker.sdk_client(ledger(store, claim, clock)).get_stock_snapshot(StockSnapshotRequest(symbol_or_symbols=['AAPL'], feed=DataFeed.IEX))
    assert len(calls) == 1


def test_no_tickets_and_missing_credentials_do_not_make_alpaca_calls(tmp_path, transport, monkeypatch):
    calls, _ = transport
    store, claim, clock = state(tmp_path, raw=RED)
    out = worker.collect_claim(store, claim, deadline=25, clock=clock, monotonic=lambda: clock.tick)
    assert out['status'] == 'no_tickets' and calls == []
    monkeypatch.delenv('ALPACA_API_KEY')
    monkeypatch.delenv('ALPACA_SECRET_KEY')
    other = tmp_path / 'other'
    store, claim, clock = state(other)
    out = worker.collect_claim(store, claim, deadline=25, clock=clock, monotonic=lambda: clock.tick)
    assert all(v['error_kind'] == 'missing_credentials' for v in out['sources'].values())
    assert len(calls) == 1 and calls[0][0].url == morning_halts.SOURCE_URL


def _synthetic_child(path, policy, claim, output, deadline):
    at = service._instant(claim.started_at)
    value = morning.collect(claim.publication, previous_raw=claim.previous, clock=lambda: at,
                            client=Client(), event_observer=event_outage, observation_run_id='synthetic-child')
    Path(output).write_bytes(service._encode(value))


def _hanging_child(path, policy, claim, output, deadline):
    # A delayed unauthorized successor write is an explicit test sentinel.
    time.sleep(1)
    Path(path + '.escaped').write_text('child escaped supervisor')
    _synthetic_child(path, policy, claim, output, deadline)


def _oversized_child(path, policy, claim, output, deadline):
    Path(output).write_bytes(b'x' * (morning.MAX_OBSERVATION_BYTES + 1))


def test_spawn_supervisor_commits_child_exact_validated_bytes(tmp_path):
    store = service.Store(tmp_path / 'worker.sqlite')
    store.ingest(RAW, now=NOW)
    assert worker.run_once(store, clock=lambda: NOW, child_target=_synthetic_child) == 'committed'
    with sqlite3.connect(store.path) as db:
        raw, lease, used = db.execute('SELECT receipt,lease_until,quota_used FROM state').fetchone()
    morning.validate_observation(json.loads(raw), RAW, require_continuity=True)
    assert lease is None and used == 1


def test_supervisor_hard_deadline_reaps_child_before_releasing_lease(tmp_path):
    store = service.Store(tmp_path / 'worker.sqlite')
    store.ingest(RAW, now=NOW)
    before = time.monotonic()
    # Fork avoids interpreter startup obscuring this process-termination test.
    assert worker.run_once(store, clock=lambda: NOW, child_target=_hanging_child,
                           context=multiprocessing.get_context('fork'), seconds=.1) == 'worker_deadline'
    assert time.monotonic() - before < 1
    assert multiprocessing.active_children() == []
    assert not Path(str(store.path) + '.escaped').exists()
    with sqlite3.connect(store.path) as db:
        assert db.execute('SELECT receipt,lease_until,quota_used FROM state').fetchone() == (None, None, 1)
    assert store.reserve(now=NOW + timedelta(seconds=29))[1] == 'collection_interval'


def test_parent_refuses_oversized_child_output(tmp_path):
    store = service.Store(tmp_path / 'worker.sqlite')
    store.ingest(RAW, now=NOW)
    with pytest.raises(ValueError, match='exceeds_bound'):
        worker.run_once(store, clock=lambda: NOW, child_target=_oversized_child)
    with sqlite3.connect(store.path) as db:
        assert db.execute('SELECT receipt,lease_until FROM state').fetchone() == (None, None)


def test_after_cutoff_never_starts_child(tmp_path):
    store = service.Store(tmp_path / 'worker.sqlite')
    store.ingest(RAW, now=NOW)
    assert worker.run_once(store, clock=lambda: NOW.replace(hour=14, minute=0), child_target=_hanging_child) == 'entry_window_ended'
    assert not Path(str(store.path) + '.escaped').exists()


@pytest.mark.parametrize('value', [0, -1, 25.1, True, float('nan')])
def test_deadline_cannot_exceed_production_ceiling(tmp_path, value):
    with pytest.raises(ValueError, match='outside_bounds'):
        worker.run_once(service.Store(tmp_path / 'worker.sqlite'), seconds=value)


def test_cli_cannot_select_fixture_clock_tickers_or_endpoint(tmp_path, capsys):
    for option in ('--dry-run', '--now', '--endpoint', '--ticker', '--retry'):
        with pytest.raises(SystemExit):
            worker.main(['--database', str(tmp_path / 'worker.sqlite'), option, 'unsafe'])
    assert not (tmp_path / 'worker.sqlite').exists()
    capsys.readouterr()


@pytest.mark.parametrize('value,seconds', [('0', 300), ('600', 600), ('99999999', 86400), ('invalid', 300), (None, 300), (format_datetime(NOW + timedelta(seconds=900)), 900)])
def test_retry_after_is_bounded(value, seconds):
    assert worker._retry_after(value, NOW) == seconds


def test_authentication_failure_quarantines_both_feeds_but_not_public_halts(tmp_path, transport):
    calls, behavior = transport
    store, claim, clock = state(tmp_path)
    def reject(request):
        return response(request, HALTS if request.url == morning_halts.SOURCE_URL else b'private', 200 if request.url == morning_halts.SOURCE_URL else 401)
    behavior['callback'] = reject
    value = worker.collect_claim(store, claim, deadline=25, clock=clock, monotonic=lambda: clock.tick)
    assert len(calls) == 2
    assert value['sources']['iex']['error_kind'] == 'authentication'
    assert value['coverage']['halts']['status'] == 'fresh'
    with sqlite3.connect(store.path) as db:
        assert db.execute("SELECT count(*) FROM provider_attempts WHERE feed='delayed_sip'").fetchone()[0] == 0
    with pytest.raises(worker.Deferred, match='backoff') as refused:
        ledger(service.Store(store.path), claim, clock).reserve('delayed_sip')
    assert refused.value.local_reason == 'local_backoff' and refused.value.status_code is None
    with sqlite3.connect(store.path) as db:
        assert db.execute("SELECT status_code, finished_at FROM provider_attempts WHERE feed='iex'").fetchone() == (401, NOW.timestamp())


def test_entitlement_backoff_is_feed_specific(tmp_path, transport):
    calls, behavior = transport
    store, claim, clock = state(tmp_path)
    def reject_iex(request):
        if request.url == morning_halts.SOURCE_URL:
            return response(request, HALTS)
        feed = parse_qs(urlsplit(request.url).query)['feed'][0]
        return response(request, b'private' if feed == 'iex' else snapshot(feed, clock()), 403 if feed == 'iex' else 200)
    behavior['callback'] = reject_iex
    value = worker.collect_claim(store, claim, deadline=25, clock=clock, monotonic=lambda: clock.tick)
    assert len(calls) == 3
    assert value['sources']['iex']['error_kind'] == 'entitlement'
    assert value['sources']['delayed_sip']['status'] == 'ok'


def test_redirect_body_is_never_unboundedly_buffered_by_requests(tmp_path, transport):
    calls, behavior = transport
    store, claim, clock = state(tmp_path)
    class NoRead:
        def read(self, *args, **kwargs):
            raise AssertionError('redirect body consumed outside byte bound')
        def close(self):
            pass
    def redirect(request):
        out = response(request, b'', 302, {'Location': 'https://example.test/collect'})
        out.raw = NoRead()
        return out
    behavior['callback'] = redirect
    with pytest.raises(worker.Deferred, match='provider_unavailable'):
        worker.sdk_client(ledger(store, claim, clock)).get_stock_snapshot(StockSnapshotRequest(symbol_or_symbols=['AAPL'], feed=DataFeed.IEX))
    assert len(calls) == 1


def test_invalid_halt_xml_never_becomes_cached_source(tmp_path, transport):
    calls, behavior = transport
    store, claim, clock = state(tmp_path)
    behavior['callback'] = lambda request: response(request, b'<html>private error</html>')
    with pytest.raises(ValueError):
        worker.BoundedSession(ledger(store, claim, clock)).get(morning_halts.SOURCE_URL)
    with sqlite3.connect(store.path) as db:
        assert db.execute('SELECT count(*) FROM provider_cache').fetchone()[0] == 0
        assert db.execute('SELECT used,backoff_until FROM provider_attempts').fetchone() == (1, (NOW + timedelta(seconds=60)).timestamp())


def test_read_only_endpoint_refuses_post_before_reserving(tmp_path, transport):
    calls, _ = transport
    store, claim, clock = state(tmp_path)
    with pytest.raises(worker.Deferred, match='endpoint_refused'):
        worker.BoundedSession(ledger(store, claim, clock)).post(worker.ALPACA_URL, json={'symbol': 'AAPL'})
    assert calls == []


def test_existing_exclusions_survive_worker_source_outage(tmp_path, transport):
    calls, behavior = transport
    previous = (Path(__file__).parent / 'fixtures/morning/halted.json').read_bytes()
    store, claim, clock = state(tmp_path, previous=previous)
    behavior['callback'] = lambda request: response(request, b'private', 500)
    value = worker.collect_claim(store, claim, deadline=25, clock=clock, monotonic=lambda: clock.tick)
    morning.validate_observation(value, RAW, previous_raw=previous, require_continuity=True)
    assert value['halt_memory'] == json.loads(previous)['halt_memory']
    assert value['rows'][0]['events']['halt']['blocks_entry'] is True
    assert value['status'] == 'provider_unavailable'


def test_replay_database_cannot_be_opened_for_worker(tmp_path, capsys):
    path = tmp_path / 'replay.sqlite'
    service.Store(path, mode='replay')
    assert worker.main(['--database', str(path)]) == 1
    assert capsys.readouterr().out == '{"mode":"bounded_private_worker","result":"refused"}\n'
