"""Operational evidence from the real Store/collector with explicit synthetic feeds.

All clocks/publications are retained test data. No live delivery, provider access,
market opportunity, order or actual profit is established by these controls.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from src import morning, morning_service as service, morning_service_journal as journal
from src import morning_service_report as report, morning_service_worker as worker
from tests.test_morning import snapshot, event_outage

RAW = (Path(__file__).parent / 'fixtures/morning/full-publication.json').read_bytes()
RED = (Path(__file__).parent / 'fixtures/morning/red-publication.json').read_bytes()
OPEN = datetime(2026, 9, 11, 13, 30, tzinfo=timezone.utc)
INGEST = OPEN - timedelta(minutes=40)


class SnapshotClient:
    def __init__(self, at, *, unavailable=False):
        self.at, self.unavailable = at, unavailable
    def get_stock_snapshot(self, request):
        if self.unavailable:
            raise ValueError('synthetic source unavailable')
        at = self.at if request.feed.value == 'iex' else self.at - timedelta(minutes=15)
        return {ticker: snapshot(at) for ticker in request.symbol_or_symbols}


def store_at(tmp_path, *, raw=RAW, at=INGEST):
    store = service.Store(tmp_path / 'morning.sqlite')
    assert store.ingest(raw, now=at) == 'ingested'
    return store


def commit(store, started, *, committed=None, unavailable=False):
    claim, reason = store.reserve(now=started)
    assert reason == 'reserved'
    value = morning.collect(claim.publication, previous_raw=claim.previous,
                            client=SnapshotClient(started, unavailable=unavailable),
                            event_observer=event_outage, clock=lambda: started,
                            observation_run_id='synthetic-operational-report')
    assert store.commit(claim, service._encode(value), now=committed or started) == 'committed'
    return value


def read(store, *, as_of=OPEN, start='2026-09-11', end='2026-09-11'):
    return report.build_report(store.path, start=start, end=end, as_of=as_of)


def test_store_produced_preopen_receipt_has_separate_quote_coverage_and_public_arrival(tmp_path):
    store = store_at(tmp_path)
    value = commit(store, OPEN - timedelta(minutes=1))
    result = read(store)
    row = result['sessions'][0]
    assert row['worker_delivery']['state'] == 'before_open'
    assert row['worker_delivery']['first_commit_seconds_from_open'] == -60
    assert row['source']['sha256'] == hashlib.sha256(RAW).hexdigest()
    assert row['source']['admitted_plans'] == 1 and row['plan_state'] == 'admitted_plans'
    assert row['latest_receipt']['feeds']['iex']['scope'] == 'single_venue'
    assert row['latest_receipt']['feeds']['delayed_sip']['minimum_delay_seconds'] == 900
    quote = row['latest_receipt']['rows'][0]['quote']
    assert quote['age_seconds_at_generation'] == 0 and quote['age_seconds_as_of'] == 60
    assert row['latest_receipt']['coverage']['issuer_news']['status'] == 'not_checked'
    assert row['latest_receipt']['coverage']['earnings']['status'] == 'not_checked'
    assert row['public_https_arrival']['observed_at'] is None
    assert row['public_https_arrival']['before_open'] is None
    assert result['summary']['quote_health_pass'] is None
    assert result['summary']['ten_session_acceptance'] == 'not_established_by_writer_evidence'


def test_generated_before_open_but_committed_after_open_is_late(tmp_path):
    store = store_at(tmp_path)
    commit(store, OPEN - timedelta(minutes=1), committed=OPEN + timedelta(minutes=1))
    row = read(store, as_of=OPEN + timedelta(minutes=2))['sessions'][0]
    assert row['worker_delivery']['state'] == 'late'
    assert row['worker_delivery']['first_generated_at'] == (OPEN - timedelta(minutes=1)).isoformat()
    assert row['worker_delivery']['first_committed_at'] == (OPEN + timedelta(minutes=1)).isoformat()
    assert row['latest_receipt']['commit_after_generation_seconds'] == 120
    assert row['latest_receipt']['rows'][0]['quote']['age_seconds_as_of'] == 180


def test_exact_open_commit_is_late_not_preopen(tmp_path):
    store = store_at(tmp_path)
    commit(store, OPEN)
    assert read(store)['sessions'][0]['worker_delivery']['state'] == 'late'


def test_after_asof_commit_and_provider_response_are_not_backdated(tmp_path):
    store = store_at(tmp_path)
    began = OPEN - timedelta(minutes=1)
    claim, _ = store.reserve(now=began)
    ledger = worker.Ledger(store, claim, deadline=25, clock=lambda: began, monotonic=lambda: 0)
    attempt = ledger.reserve('iex')
    later = OPEN + timedelta(minutes=1)
    ledger.clock = lambda: later
    ledger.finish('iex', attempt, status=200)
    value = morning.collect(claim.publication, previous_raw=None,
                            client=SnapshotClient(began), event_observer=event_outage,
                            clock=lambda: began, observation_run_id='synthetic-old-generation-clock')
    assert store.commit(claim, service._encode(value), now=later) == 'committed'
    row = read(store, as_of=OPEN)['sessions'][0]
    assert row['worker_delivery']['state'] == 'missing_recorded_receipt'
    assert row['latest_receipt'] is None
    iex = row['provider_attempts']['per_feed']['iex']
    assert iex['retained_reserved_attempts'] == 1
    assert iex['retained_finished_attempts'] == 0 and iex['http_response_status_counts'] == {}
    assert iex['reserved_without_retained_finish'] == 1
    assert later.isoformat() not in report.encode(read(store, as_of=OPEN)).decode()


@pytest.mark.parametrize('seconds,expected', [(-1, 'not_yet_due'), (0, 'missing_recorded_receipt'), (1, 'missing_recorded_receipt')])
def test_not_yet_due_and_missing_recorded_receipt_do_not_mean_scheduler_failure(tmp_path, seconds, expected):
    store = store_at(tmp_path)
    row = read(store, as_of=OPEN + timedelta(seconds=seconds))['sessions'][0]
    assert row['worker_delivery']['state'] == expected
    assert row['worker_delivery']['first_committed_at'] is None
    assert 'scheduler outage' in ' '.join(read(store)['limitations'])


def test_no_ticket_morning_has_a_receipt_but_does_not_claim_quote_health(tmp_path):
    store = store_at(tmp_path, raw=RED)
    commit(store, OPEN - timedelta(minutes=1))
    result = read(store)
    row = result['sessions'][0]
    assert row['worker_delivery']['state'] == 'before_open'
    assert row['plan_state'] == 'no_admitted_plans'
    assert row['latest_receipt']['status'] == 'no_tickets'
    assert row['latest_receipt']['row_count'] == 0
    assert row['latest_receipt']['quote_status_counts_at_generation'] == {}
    assert all(source['status'] == 'not_requested' for source in row['latest_receipt']['feeds'].values())
    assert result['summary']['quote_health_pass'] is None


def test_outage_and_later_recovery_remain_visible_in_retained_summary(tmp_path):
    store = store_at(tmp_path)
    commit(store, OPEN - timedelta(minutes=2), unavailable=True)
    commit(store, OPEN - timedelta(minutes=1))
    row = read(store)['sessions'][0]
    assert row['worker_delivery']['state'] == 'before_open'
    assert row['latest_receipt']['status'] == 'observed'
    assert row['retained_observation_summary']['receipt_status_counts'] == {'observed': 1, 'provider_unavailable': 1}
    assert row['retained_observation_summary']['feed_error_counts']['iex'] == {'provider_error': 1}
    assert row['retained_observation_summary']['quote_row_status_counts'] == {'recent': 1, 'unavailable': 1}


def test_new_source_revision_cannot_borrow_old_receipt_as_current(tmp_path):
    store = store_at(tmp_path)
    commit(store, OPEN - timedelta(minutes=2))
    assert store.ingest(RAW + b'\n', now=OPEN - timedelta(minutes=1)) == 'ingested'
    row = read(store)['sessions'][0]
    assert row['worker_delivery']['state'] == 'before_open'
    assert row['worker_delivery']['latest_receipt_matches_latest_source'] is False
    assert row['latest_source_receipt'] is None
    assert len(row['source_revisions']) == 2
    assert row['source']['sha256'] != row['latest_receipt']['source_sha256']
    before_revision = read(store, as_of=OPEN - timedelta(seconds=90))['sessions'][0]
    assert len(before_revision['source_revisions']) == 1
    assert before_revision['worker_delivery']['latest_receipt_matches_latest_source'] is True


def test_failed_and_superseded_claims_do_not_become_successful_receipts(tmp_path):
    store = store_at(tmp_path)
    claim, _ = store.reserve(now=OPEN - timedelta(minutes=2))
    store.release(claim, now=OPEN - timedelta(minutes=2), outcome='worker_deadline')
    second, _ = store.reserve(now=OPEN - timedelta(minutes=1))
    store.ingest(RAW + b'\n', now=OPEN - timedelta(seconds=30))
    assert store.release(second, now=OPEN - timedelta(seconds=30), outcome='source_record_changed') is False
    row = read(store)['sessions'][0]
    assert row['worker_delivery']['retained_commits'] == 0
    assert row['worker_delivery']['collection_outcomes'] == {'worker_deadline': 1}
    assert row['latest_receipt'] is None


def test_http_200_response_is_separate_from_usable_quotes(tmp_path):
    store = store_at(tmp_path)
    at = OPEN - timedelta(minutes=1)
    claim, _ = store.reserve(now=at)
    ledger = worker.Ledger(store, claim, deadline=25, clock=lambda: at, monotonic=lambda: 0)
    attempt = ledger.reserve('iex')
    ledger.finish('iex', attempt, status=200)
    store.release(claim, now=at, outcome='collector_failed')
    row = read(store)['sessions'][0]
    feed = row['provider_attempts']['per_feed']['iex']
    assert feed['retained_reserved_attempts'] == feed['retained_finished_attempts'] == 1
    assert feed['http_response_status_counts'] == {'200': 1}
    assert row['latest_receipt'] is None
    assert row['provider_attempts']['actual_socket_requests'] is None
    assert row['worker_delivery']['state'] == 'missing_recorded_receipt'


def test_transport_failure_has_no_fabricated_http_status(tmp_path):
    store = store_at(tmp_path)
    at = OPEN - timedelta(minutes=1)
    claim, _ = store.reserve(now=at)
    ledger = worker.Ledger(store, claim, deadline=25, clock=lambda: at, monotonic=lambda: 0)
    attempt = ledger.reserve('iex')
    ledger.finish('iex', attempt)
    row = read(store)['sessions'][0]
    feed = row['provider_attempts']['per_feed']['iex']
    assert feed['finished_without_http_status'] == 1
    assert feed['http_response_status_counts'] == {}


def test_empty_new_journal_is_unobserved_not_an_outage_or_zero_total(tmp_path):
    store = service.Store(tmp_path / 'empty.sqlite')
    result = read(store)
    row = result['sessions'][0]
    assert result['journal']['capture_state'] == 'not_started_as_of'
    assert row['worker_delivery']['state'] == 'unobserved'
    assert row['source'] is None and row['latest_receipt'] is None
    assert row['provider_attempts']['per_feed']['iex']['reserved_attempts_as_of'] is None


def test_preinstrumentation_and_future_windows_remain_unobserved(tmp_path):
    store = store_at(tmp_path)
    result = read(store, start='2026-09-10', end='2026-09-14')
    old, today, future = result['sessions']
    assert old['worker_delivery']['state'] == 'unobserved'
    assert 'collection_window_precedes_instrumentation' in old['evidence']['gaps']
    assert future['worker_delivery']['state'] == 'not_yet_due'
    assert 'collection_window_not_started_as_of' in future['evidence']['gaps']
    assert future['provider_attempts']['per_feed']['iex']['reserved_attempts_as_of'] is None


def test_existing_uninstrumented_database_migration_does_not_backfill_success(tmp_path):
    store = store_at(tmp_path)
    commit(store, OPEN - timedelta(minutes=1))
    with sqlite3.connect(store.path) as db:
        for table in ('morning_journal_refs', 'morning_journal_events', 'morning_journal_blobs', 'morning_journal_meta'):
            db.execute('DROP TABLE ' + table)
    migrated = service.Store(store.path)
    result = read(migrated)
    row = result['sessions'][0]
    assert result['journal']['migration_without_backfill'] is True
    assert row['latest_receipt'] is None
    assert row['worker_delivery']['state'] == 'unobserved'
    assert 'legacy_history_not_backfilled' in row['evidence']['gaps']


def test_retention_pruning_inside_session_cannot_be_misread_as_complete_missing(tmp_path, monkeypatch):
    # Tighten the retention ceiling only, exercising the production prune path.
    monkeypatch.setattr(journal, 'MAX_EVENTS', 3)
    store = store_at(tmp_path)
    commit(store, OPEN - timedelta(minutes=10))
    claim, _ = store.reserve(now=OPEN - timedelta(minutes=9))
    store.release(claim, now=OPEN - timedelta(minutes=9), outcome='worker_failed')
    store.ingest(RAW + b'\n', now=OPEN - timedelta(minutes=8))
    result = read(store)
    row = result['sessions'][0]
    assert result['journal']['pruned_events'] == 3
    assert row['source'] is not None and len(row['source_revisions']) == 1
    assert row['worker_delivery']['state'] == 'unobserved'
    assert 'retention_removed_all_or_part_of_window' in row['evidence']['gaps']
    assert row['provider_attempts']['per_feed']['iex']['reserved_attempts_as_of'] is None


def test_deterministic_read_only_snapshot_performs_no_store_or_network_calls(tmp_path, monkeypatch):
    store = store_at(tmp_path)
    commit(store, OPEN - timedelta(minutes=1))
    before = store.path.read_bytes()
    def refused(*args, **kwargs):
        raise AssertionError('report attempted write or source work')
    monkeypatch.setattr(service.Store, '__init__', refused)
    monkeypatch.setattr(morning, 'collect', refused)
    import socket
    monkeypatch.setattr(socket.socket, 'connect', refused)
    first = report.encode(read(store))
    second = report.encode(read(store))
    assert first == second
    assert store.path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [store.path]


def test_snapshot_is_closed_before_report_interpretation(tmp_path, monkeypatch):
    store = store_at(tmp_path)
    original = report._build
    def interpret(snapshot, *args):
        # An exclusive writer lock would fail if the report kept a read snapshot.
        with sqlite3.connect(store.path, timeout=0) as db:
            db.execute('BEGIN EXCLUSIVE')
            db.rollback()
        return original(snapshot, *args)
    monkeypatch.setattr(report, '_build', interpret)
    assert read(store)['sessions'][0]['source'] is not None


@pytest.mark.parametrize('start,end,expected', [
    ('2026-10-30', '2026-11-02', [('2026-10-30', '2026-10-30T08:30:00-05:00'), ('2026-11-02', '2026-11-02T08:30:00-06:00')]),
    ('2026-11-26', '2026-11-27', [('2026-11-27', '2026-11-27T08:30:00-06:00')]),
])
def test_xnys_holidays_weekends_chicago_dst_and_early_close(tmp_path, start, end, expected):
    store = service.Store(tmp_path / 'calendar.sqlite')
    result = read(store, start=start, end=end, as_of='2026-11-28T15:00:00Z')
    assert [(r['session'], r['schedule']['opens_chicago']) for r in result['sessions']] == expected
    if end == '2026-11-27':
        assert result['sessions'][0]['schedule']['closes_chicago'] == '2026-11-27T12:00:00-06:00'
        assert result['sessions'][0]['schedule']['shortened'] is True


def test_ten_expected_sessions_with_no_evidence_cannot_form_acceptance_streak(tmp_path):
    store = service.Store(tmp_path / 'calendar.sqlite')
    result = read(store, start='2026-10-05', end='2026-10-16', as_of='2026-10-18T15:00:00Z')
    assert result['summary']['expected_sessions'] == 10
    assert result['summary']['worker_commit_states'] == {'unobserved': 10}
    assert result['summary']['ten_session_acceptance'] == 'not_established_by_writer_evidence'
    assert result['summary']['public_https_arrivals'] is None


@pytest.mark.parametrize('start,end,as_of', [
    ('2026-01-01', '2026-03-04', '2026-10-18T15:00:00Z'),
    ('2026-10-02', '2026-10-01', '2026-10-18T15:00:00Z'),
    ('2026-1-01', '2026-01-02', '2026-10-18T15:00:00Z'),
    ('2026-10-01', '2026-10-02', '2026-10-18T15:00:00'),
    ('2036-01-01', '2036-01-02', '2026-10-18T15:00:00Z'),
])
def test_invalid_dates_clocks_and_range_refused_before_database_open(tmp_path, start, end, as_of):
    missing = tmp_path / 'must-not-exist.sqlite'
    with pytest.raises(ValueError):
        report.build_report(missing, start=start, end=end, as_of=as_of)
    assert not missing.exists()


def test_replay_database_is_not_live_operational_evidence(tmp_path):
    store = service.Store(tmp_path / 'replay.sqlite', mode='replay')
    with pytest.raises(ValueError, match='mode_or_version'):
        read(store)


def test_unsupported_journal_version_and_changed_blob_refused(tmp_path):
    store = store_at(tmp_path)
    with sqlite3.connect(store.path) as db:
        db.execute('UPDATE morning_journal_meta SET version=99')
    with pytest.raises(ValueError, match='mode_or_version'):
        read(store)
    with sqlite3.connect(store.path) as db:
        db.execute('UPDATE morning_journal_meta SET version=1')
        db.execute("UPDATE morning_journal_blobs SET raw=CAST(raw || ' ' AS BLOB),bytes=bytes+1")
    with pytest.raises(ValueError, match='blob_invalid'):
        read(store)


def test_read_bound_refuses_instead_of_silently_dropping_source(tmp_path, monkeypatch):
    store = store_at(tmp_path)
    monkeypatch.setattr(report, 'MAX_READ_BYTES', 1)
    with pytest.raises(ValueError, match='read_exceeds_bound'):
        read(store)


def test_regressing_event_clock_refused_even_with_valid_payload_hash(tmp_path):
    store = store_at(tmp_path)
    claim, _ = store.reserve(now=OPEN - timedelta(minutes=1))
    store.release(claim, now=OPEN - timedelta(seconds=59), outcome='worker_failed')
    with sqlite3.connect(store.path) as db:
        # Move only the later completion before its reservation while staying
        # after capture start and below meta.last_at: isolate event ordering.
        db.execute('UPDATE morning_journal_events SET recorded_at=? WHERE kind=?', ((OPEN - timedelta(minutes=2)).isoformat(), 'collection_finished'))
    with pytest.raises(ValueError, match='evidence_invalid'):
        read(store)


def test_cli_exports_exact_stable_json_and_safe_refusal(tmp_path, capsys):
    store = store_at(tmp_path)
    args = ['--database', str(store.path), '--start', '2026-09-11', '--end', '2026-09-11', '--as-of', OPEN.isoformat()]
    assert report.main(args) == 0
    assert capsys.readouterr().out.encode() == report.encode(read(store))
    assert report.main(['--database', str(tmp_path / 'PRIVATE.sqlite'), '--start', '2026-09-11', '--end', '2026-09-11', '--as-of', OPEN.isoformat()]) == 1
    refused = capsys.readouterr().out
    assert json.loads(refused)['status'] == 'refused' and 'PRIVATE' not in refused


def test_pruned_preopen_commit_cannot_turn_later_retained_receipt_into_first_delivery(tmp_path, monkeypatch):
    monkeypatch.setattr(journal, 'MAX_EVENTS', 2)
    store = store_at(tmp_path)
    commit(store, OPEN - timedelta(minutes=1))
    commit(store, OPEN + timedelta(minutes=5))
    result = read(store, as_of=OPEN + timedelta(minutes=6))
    row = result['sessions'][0]
    assert row['worker_delivery']['state'] == 'unobserved'
    assert row['worker_delivery']['first_committed_at'] is None
    assert row['worker_delivery']['first_generated_at'] is None
    assert row['worker_delivery']['first_receipt_sha256'] is None
    assert row['worker_delivery']['first_commit_seconds_from_open'] is None
    assert row['worker_delivery']['first_retained_committed_at'] == (OPEN + timedelta(minutes=5)).isoformat()
    assert row['worker_delivery']['first_retained_commit_timing'] == 'late'
    assert row['worker_delivery']['at_least_one_preopen_commit'] is None
    assert result['summary']['worker_commit_states'] == {'unobserved': 1}


def test_retained_preopen_receipt_remains_positive_evidence_despite_unknown_first(tmp_path, monkeypatch):
    monkeypatch.setattr(journal, 'MAX_EVENTS', 2)
    store = store_at(tmp_path)
    commit(store, OPEN - timedelta(minutes=1))
    row = read(store)['sessions'][0]
    assert row['worker_delivery']['state'] == 'before_open'
    assert row['worker_delivery']['first_committed_at'] is None
    assert row['worker_delivery']['first_retained_commit_timing'] == 'before_open'
    assert row['worker_delivery']['at_least_one_preopen_commit'] is True
    assert row['evidence']['window_capture'] == 'partial_or_unobserved'


def test_cli_future_asof_is_refused_before_database_read(tmp_path, monkeypatch, capsys):
    store = store_at(tmp_path)
    monkeypatch.setattr(report, 'utcnow', lambda: OPEN)
    reads = []
    original_read = journal.read_journal
    def observed_read(*args, **kwargs):
        reads.append(1)
        return original_read(*args, **kwargs)
    monkeypatch.setattr(journal, 'read_journal', observed_read)
    args = ['--database', str(store.path), '--start', '2026-09-11', '--end', '2026-09-11', '--as-of', (OPEN + timedelta(seconds=1)).isoformat()]
    assert report.main(args) == 1
    value = json.loads(capsys.readouterr().out)
    assert value['reason'] == 'report_future_as_of_refused'
    assert value['operational_evidence'] is None and reads == []
    # At the exact observed current instant, the same real CLI accepts a report.
    args[-1] = OPEN.isoformat()
    assert report.main(args) == 0
    assert json.loads(capsys.readouterr().out)['as_of'] == OPEN.isoformat() and reads == [1]


def test_pure_report_remains_explicit_asof_without_hidden_wall_clock(tmp_path, monkeypatch):
    store = store_at(tmp_path)
    def refused():
        raise AssertionError('pure report consulted wall clock')
    monkeypatch.setattr(report, 'utcnow', refused)
    assert read(store)['as_of'] == OPEN.isoformat()
