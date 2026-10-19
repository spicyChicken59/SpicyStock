"""Independent synthetic controls against the real Store, journal and report.

This script never contacts a provider or measures actual public delivery.
Run with the target checkout and evidence output directory as positional args.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))
from src import morning, morning_service as service
from src import morning_service_journal as journal
from src import morning_service_report as report
from src import morning_service_worker as worker
from tests.test_morning import snapshot, event_outage

RAW = (ROOT / 'tests/fixtures/morning/full-publication.json').read_bytes()
RED = (ROOT / 'tests/fixtures/morning/red-publication.json').read_bytes()
OPEN = datetime(2026, 9, 11, 13, 30, tzinfo=timezone.utc)
checks = []
samples = {}


def check(name, condition):
    checks.append({'name': name, 'passed': bool(condition)})
    if not condition:
        raise AssertionError(name)


def no_network(*args, **kwargs):
    raise AssertionError('independent report control attempted network access')


socket.socket.connect = no_network
socket.socket.connect_ex = no_network
socket.create_connection = no_network


class Feed:
    def __init__(self, at, unavailable=False):
        self.at, self.unavailable = at, unavailable
        self.reads = 0

    def get_stock_snapshot(self, request):
        self.reads += 1
        if self.unavailable:
            raise RuntimeError('independent synthetic feed outage')
        at = self.at if request.feed.value == 'iex' else self.at - timedelta(minutes=15)
        return {symbol: snapshot(at) for symbol in request.symbol_or_symbols}


def fresh(path, raw=RAW):
    store = service.Store(path)
    assert store.ingest(raw, now=OPEN - timedelta(minutes=40)) == 'ingested'
    return store


def collect_claim(claim, at, unavailable=False):
    feed = Feed(at, unavailable)
    value = morning.collect(claim.publication, previous_raw=claim.previous,
                            client=feed, event_observer=event_outage,
                            clock=lambda: at, observation_run_id='independent-synthetic-report')
    return value, feed


def commit(store, at, *, recorded=None, unavailable=False):
    claim, reason = store.reserve(now=at)
    assert reason == 'reserved'
    value, feed = collect_claim(claim, at, unavailable)
    assert store.commit(claim, service._encode(value), now=recorded or at) == 'committed'
    return value, feed


def read(store, at=OPEN, start='2026-09-11', end='2026-09-11'):
    return report.build_report(store.path, start=start, end=end, as_of=at)


def row(store, at=OPEN):
    return read(store, at)['sessions'][0]


def run(directory):
    # Cross the report boundary with both a completion and provider response.
    store = fresh(directory / 'late.sqlite')
    began, finished = OPEN - timedelta(minutes=1), OPEN + timedelta(minutes=1)
    claim, reason = store.reserve(now=began)
    assert reason == 'reserved'
    ledger = worker.Ledger(store, claim, deadline=25, clock=lambda: began, monotonic=lambda: 0)
    attempt = ledger.reserve('iex')
    ledger.clock = lambda: finished
    ledger.finish('iex', attempt, status=200)
    value, _ = collect_claim(claim, began)
    assert store.commit(claim, service._encode(value), now=finished) == 'committed'
    before = row(store, OPEN - timedelta(seconds=1))
    asof = row(store)
    after = row(store, finished)
    check('before open remains not yet due', before['worker_delivery']['state'] == 'not_yet_due')
    check('as-of filters later commit despite old generated timestamp', asof['worker_delivery']['state'] == 'missing_recorded_receipt' and asof['latest_receipt'] is None)
    check('as-of retains charged reservation without later HTTP response', asof['provider_attempts']['per_feed']['iex']['retained_reserved_attempts'] == 1 and asof['provider_attempts']['per_feed']['iex']['http_response_status_counts'] == {})
    check('writer late completion controls timing', after['worker_delivery']['state'] == 'late')
    check('generated and committed clocks remain separate', after['latest_receipt']['generated_at'] == began.isoformat() and after['latest_receipt']['committed_at'] == finished.isoformat())
    check('local writer is not public HTTPS evidence', after['public_https_arrival']['observed_at'] is None and after['public_https_arrival']['before_open'] is None)
    samples['late'] = read(store, finished)

    # Retained outage must remain visible after recovery, independent of any HTTP 200.
    store = fresh(directory / 'outage.sqlite')
    commit(store, OPEN - timedelta(minutes=2), unavailable=True)
    commit(store, OPEN - timedelta(minutes=1))
    result = read(store)
    current = result['sessions'][0]
    check('successful worker commit does not hide provider outage', current['retained_observation_summary']['receipt_status_counts'] == {'provider_unavailable': 1, 'observed': 1})
    check('historical unavailable rows remain visible after recovery', current['retained_observation_summary']['quote_row_status_counts'] == {'unavailable': 1, 'recent': 1})
    check('latest generation freshness is separate from report age', current['latest_receipt']['rows'][0]['quote']['age_seconds_at_generation'] == 0 and current['latest_receipt']['rows'][0]['quote']['age_seconds_as_of'] == 60)
    check('journal does not claim overall quote health', result['summary']['quote_health_pass'] is None)
    samples['outage_recovery'] = result

    store = fresh(directory / 'no-plans.sqlite', RED)
    _, feed = commit(store, OPEN - timedelta(minutes=1))
    result = read(store)
    current = result['sessions'][0]
    check('no-plan receipt avoids synthetic snapshot reads', feed.reads == 0)
    check('no-plan local receipt remains separate from source health', current['plan_state'] == 'no_admitted_plans' and current['latest_receipt']['status'] == 'no_tickets' and current['latest_receipt']['rows'] == [])
    check('no-plan feed statuses are not requested', all(x['status'] == 'not_requested' for x in current['latest_receipt']['feeds'].values()))
    check('no-plan report does not establish ten-session acceptance', result['summary']['ten_session_acceptance'] == 'not_established_by_writer_evidence')
    samples['no_plans'] = result

    # A current source revision cannot reuse the prior source's receipt.
    store = fresh(directory / 'revision.sqlite')
    commit(store, OPEN - timedelta(minutes=3))
    old, reason = store.reserve(now=OPEN - timedelta(minutes=2))
    assert reason == 'reserved'
    changed = OPEN - timedelta(minutes=1)
    assert store.ingest(RAW + b'\n', now=changed) == 'ingested'
    assert store.release(old, now=changed, outcome='source_record_changed') is False
    current = row(store)
    check('source revision is bound to exact changed bytes', current['source']['sha256'] == hashlib.sha256(RAW + b'\n').hexdigest())
    check('older source receipt is not current-source evidence', current['latest_source_receipt'] is None and current['worker_delivery']['latest_receipt_matches_latest_source'] is False)
    check('source history is retained', len(current['source_revisions']) == 2)
    check('future revision is excluded from earlier as-of', len(row(store, OPEN - timedelta(seconds=90))['source_revisions']) == 1)
    samples['source_revision'] = read(store)

    # An HTTP response is transport evidence even when no receipt is ever committed.
    store = fresh(directory / 'transport.sqlite')
    at = OPEN - timedelta(minutes=1)
    claim, reason = store.reserve(now=at)
    assert reason == 'reserved'
    ledger = worker.Ledger(store, claim, deadline=25, clock=lambda: at, monotonic=lambda: 0)
    attempt = ledger.reserve('iex')
    ledger.finish('iex', attempt, status=200)
    assert store.release(claim, now=at, outcome='collector_failed') is True
    current = row(store)
    check('HTTP 200 alone does not create receipt coverage', current['latest_receipt'] is None and current['worker_delivery']['state'] == 'missing_recorded_receipt')
    check('HTTP response and collector outcome remain separately visible', current['provider_attempts']['per_feed']['iex']['http_response_status_counts'] == {'200': 1} and current['worker_delivery']['collection_outcomes'] == {'collector_failed': 1})
    check('charged reservation does not invent actual socket count', current['provider_attempts']['actual_socket_requests'] is None)

    # Keep only two events, evicting the genuine pre-open commit.
    previous_cap = journal.MAX_EVENTS
    journal.MAX_EVENTS = 2
    try:
        store = fresh(directory / 'pruned.sqlite')
        commit(store, OPEN - timedelta(minutes=1))
        commit(store, OPEN + timedelta(minutes=5))
        current = row(store, OPEN + timedelta(minutes=6))
        check('retention gap remains explicit', 'retention_removed_all_or_part_of_window' in current['evidence']['gaps'])
        check('retained late receipt cannot establish first-ever late delivery', current['worker_delivery']['state'] not in {'late', 'before_open'})
        check('partial capture clears unqualified first-commit fields', all(current['worker_delivery'][key] is None for key in ('first_committed_at', 'first_generated_at', 'first_receipt_sha256', 'first_commit_seconds_from_open')))
        check('partial capture explicitly labels first retained commit', current['worker_delivery']['first_retained_committed_at'] == (OPEN + timedelta(minutes=5)).isoformat() and current['worker_delivery']['first_retained_commit_timing'] == 'late')
        check('pruned pre-open history cannot establish absence of pre-open delivery', current['worker_delivery']['at_least_one_preopen_commit'] is None)
        check('retained late receipt remains inspectable', current['latest_receipt']['committed_at'] == (OPEN + timedelta(minutes=5)).isoformat())
        check('pruned reservations have unknown as-of total', current['provider_attempts']['per_feed']['iex']['reserved_attempts_as_of'] is None)
        samples['retention_gap'] = read(store, OPEN + timedelta(minutes=6))
        early = fresh(directory / 'pruned-but-preopen.sqlite')
        commit(early, OPEN - timedelta(minutes=1))
        retained = row(early)
        check('retained pre-open commit remains positive evidence despite earlier pruning', retained['worker_delivery']['state'] == 'before_open' and retained['worker_delivery']['at_least_one_preopen_commit'] is True)
        check('positive retained pre-open evidence does not recover unknown first-ever time', retained['worker_delivery']['first_committed_at'] is None and retained['worker_delivery']['first_retained_committed_at'] == (OPEN - timedelta(minutes=1)).isoformat())
    finally:
        journal.MAX_EVENTS = previous_cap

    # Interpret a closed snapshot slowly while a real producer commits another receipt.
    store = fresh(directory / 'concurrent.sqlite')
    commit(store, OPEN - timedelta(minutes=2))
    paused, resume = threading.Event(), threading.Event()
    original_receipt = report._receipt
    def blocked_receipt(*args):
        paused.set()
        if not resume.wait(10):
            raise AssertionError('report interpretation did not resume')
        return original_receipt(*args)
    report._receipt = blocked_receipt
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            reader = executor.submit(read, store)
            assert paused.wait(10)
            started = time.monotonic()
            writer = executor.submit(commit, store, OPEN - timedelta(minutes=1))
            try:
                writer.result(timeout=3)
                elapsed = time.monotonic() - started
                check('real Store reserve and commit finish during paused report validation', elapsed < 3 and not resume.is_set())
            finally:
                resume.set()
            old_snapshot = reader.result(timeout=10)
    finally:
        report._receipt = original_receipt
        resume.set()
    check('closed report snapshot remains internally consistent during write', old_snapshot['sessions'][0]['worker_delivery']['retained_commits'] == 1)
    check('subsequent report sees real concurrent commit', row(store)['worker_delivery']['retained_commits'] == 2)
    before_bytes = store.path.read_bytes()
    check('identical journal and as-of yield identical report bytes', report.encode(read(store)) == report.encode(read(store)))
    check('report leaves database bytes untouched', store.path.read_bytes() == before_bytes)

    # Empty and migrated journals preserve unknowns; future calendar is not missing data.
    empty = service.Store(directory / 'empty.sqlite')
    result = read(empty, at='2026-10-18T15:00:00Z', start='2026-10-05', end='2026-10-16')
    check('ten unobserved sessions cannot become successes or outages', result['summary']['worker_commit_states'] == {'unobserved': 10})
    result = read(empty, start='2026-11-25', end='2026-11-30')
    check('exchange holiday and weekend are excluded', [r['session'] for r in result['sessions']] == ['2026-11-25', '2026-11-27', '2026-11-30'])
    check('future windows are not yet due and totals are unknown', all(r['worker_delivery']['state'] == 'not_yet_due' and r['provider_attempts']['per_feed']['iex']['reserved_attempts_as_of'] is None for r in result['sessions']))
    check('Chicago winter open and shortened session are preserved', result['sessions'][1]['schedule']['opens_chicago'] == '2026-11-27T08:30:00-06:00' and result['sessions'][1]['schedule']['closes_chicago'] == '2026-11-27T12:00:00-06:00')
    samples['future_calendar'] = result
    with sqlite3.connect(store.path) as db:
        for name in ('morning_journal_refs', 'morning_journal_events', 'morning_journal_blobs', 'morning_journal_meta'):
            db.execute('DROP TABLE ' + name)
    legacy = service.Store(store.path)
    result = read(legacy)
    check('migration never backfills committed legacy current state', result['journal']['migration_without_backfill'] and result['sessions'][0]['latest_receipt'] is None)
    check('migration gap remains unobserved', result['sessions'][0]['worker_delivery']['state'] == 'unobserved' and 'legacy_history_not_backfilled' in result['sessions'][0]['evidence']['gaps'])

    replay = service.Store(directory / 'replay.sqlite', mode='replay')
    try:
        read(replay)
    except ValueError:
        check('replay store is refused as live writer evidence', True)
    else:
        check('replay store is refused as live writer evidence', False)
    cli = subprocess.run([sys.executable, '-m', 'src.morning_service_report', '--database', str(directory / 'PRIVATE-MISSING.sqlite'), '--start', '2026-09-11', '--end', '2026-09-11', '--as-of', OPEN.isoformat()], cwd=ROOT, capture_output=True, text=True, timeout=10)
    check('CLI refuses missing database without creating it or exposing path', cli.returncode == 1 and json.loads(cli.stdout)['status'] == 'refused' and 'PRIVATE-MISSING' not in cli.stdout + cli.stderr and not (directory / 'PRIVATE-MISSING.sqlite').exists())


failure = None
try:
    with tempfile.TemporaryDirectory(prefix='spicystock-report-independent-') as tmp:
        run(Path(tmp))
except Exception as exc:
    failure = {'type': type(exc).__name__, 'message': str(exc)}
finally:
    for name, value in samples.items():
        (OUT / (name + '.json')).write_bytes(report.encode(value))
    summary = {'scope': 'synthetic actual Store/journal/report controls; no live provider or public arrival',
               'runtime': sys.version, 'root': str(ROOT),
               'hashes': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in ('src/morning_service.py', 'src/morning_service_worker.py', 'src/morning_service_journal.py', 'src/morning_service_report.py')},
               'passed': sum(c['passed'] for c in checks), 'total': len(checks),
               'checks': checks, 'failure': failure}
    (OUT / 'independent-controls.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'passed': summary['passed'], 'total': summary['total'], 'failure': failure}))
if failure:
    raise SystemExit(1)
