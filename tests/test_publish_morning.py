"""Execute morning publication against real temporary Git remotes.

The transport tests deliberately stub the separately tested observation schema:
their concern is which committed bytes a concurrent publisher can replace.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from src import morning
from tools import publish_morning as publisher


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True,
                          capture_output=True).stdout


def encode(value):
    return json.dumps(value, sort_keys=True).encode() + b'\n'


def observation(raw, *, previous=None, started='2026-10-09T13:20:00+00:00',
                generated='2026-10-09T13:20:01+00:00', **changes):
    return {'dry_run': False, 'publication': {'data_sha256': hashlib.sha256(raw).hexdigest()},
            'previous_observation_sha256': hashlib.sha256(previous).hexdigest() if previous else None,
            'collection_started_at': started, 'generated_at': generated,
            'observation_run_id': '42', 'status': 'no_tickets', **changes}


@pytest.fixture
def transport_schema(monkeypatch):
    # Backend tests own full provenance/source replay. A real validator failure
    # is also exercised below so this boundary cannot silently stop calling it.
    monkeypatch.setattr(morning, 'validate_observation', lambda value, raw, **kwargs: None)


@pytest.fixture
def repository(tmp_path):
    remote = tmp_path / 'remote.git'
    subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
    root = tmp_path / 'checkout'
    subprocess.run(['git', 'clone', str(remote), str(root)], check=True, capture_output=True)
    git(root, 'checkout', '-b', 'main')
    git(root, 'config', 'user.name', 'test')
    git(root, 'config', 'user.email', 'test@example.invalid')
    (root / 'docs').mkdir()
    raw = b'{"publication":"first"}\n'
    (root / 'docs/data.json').write_bytes(raw)
    (root / 'docs/picks.json').write_text('{"unchanged":true}\n')
    (root / 'notes.txt').write_text('original\n')
    git(root, 'add', '.')
    git(root, 'commit', '-m', 'baseline')
    git(root, 'push', '-u', 'origin', 'main')
    return root, remote, raw


def publish(root, value):
    return publisher.publish(root, encode(value), ref='refs/heads/main', run_id='42')


def test_one_file_commit_preserves_source_and_local_staged_work(repository, transport_schema):
    root, remote, raw = repository
    prior = git(remote, 'rev-parse', 'main').strip()
    (root / 'notes.txt').write_text('private unfinished work\n')
    git(root, 'add', 'notes.txt')
    receipt = observation(raw, generated='2026-01-02T13:20:01+00:00', started='2026-01-02T13:20:00+00:00')
    assert publish(root, receipt) == 'published'
    assert git(remote, 'show', 'main:docs/morning.json') == encode(receipt)
    assert git(remote, 'show', 'main:docs/data.json') == raw
    assert git(remote, 'show', 'main:docs/picks.json') == b'{"unchanged":true}\n'
    assert git(remote, 'show', 'main:notes.txt') == b'original\n'
    assert git(remote, 'rev-parse', 'main^').strip() == prior
    assert git(remote, 'diff-tree', '--no-commit-id', '--name-only', '-r', 'main') == b'docs/morning.json\n'
    assert git(root, 'diff', '--cached', '--name-only') == b'notes.txt\n'
    assert (root / 'notes.txt').read_text() == 'private unfinished work\n'


def competing_checkout(tmp_path, remote):
    other = tmp_path / 'competing'
    subprocess.run(['git', 'clone', '--branch', 'main', str(remote), str(other)],
                   check=True, capture_output=True)
    git(other, 'config', 'user.name', 'competitor')
    git(other, 'config', 'user.email', 'competitor@example.invalid')
    return other


def race_once(monkeypatch, callback):
    original = publisher.git
    pushes = []

    def raced(root, *args, **kwargs):
        if args[0] == 'push':
            pushes.append(args)
            if len(pushes) == 1:
                callback()
        return original(root, *args, **kwargs)

    monkeypatch.setattr(publisher, 'git', raced)
    return pushes


def test_unrelated_main_commit_is_preserved_and_retry_revalidates(tmp_path, repository, transport_schema, monkeypatch):
    root, remote, raw = repository
    other = competing_checkout(tmp_path, remote)

    def advance():
        (other / 'unrelated.txt').write_text('concurrent documentation\n')
        git(other, 'add', 'unrelated.txt')
        git(other, 'commit', '-m', 'unrelated')
        git(other, 'push', 'origin', 'main')

    pushes = race_once(monkeypatch, advance)
    checked = []
    monkeypatch.setattr(morning, 'validate_observation', lambda value, source, **kwargs: checked.append(source))
    receipt = observation(raw, generated='2026-01-02T13:20:01+00:00', started='2026-01-02T13:20:00+00:00')
    assert publish(root, receipt) == 'published'
    assert len(pushes) == 2 and checked == [raw, raw]
    assert all('--force' not in arg and '--force-with-lease' not in arg for args in pushes for arg in args)
    assert git(remote, 'show', 'main:unrelated.txt') == b'concurrent documentation\n'
    assert git(remote, 'show', 'main:docs/data.json') == raw


def test_same_session_record_republication_during_push_aborts(tmp_path, repository, transport_schema, monkeypatch):
    root, remote, raw = repository
    other = competing_checkout(tmp_path, remote)
    revised = b'{"publication":"same session, revised evidence"}\n'

    def advance():
        (other / 'docs/data.json').write_bytes(revised)
        git(other, 'add', 'docs/data.json')
        git(other, 'commit', '-m', 'revised record')
        git(other, 'push', 'origin', 'main')

    pushes = race_once(monkeypatch, advance)
    receipt = observation(raw, generated='2026-01-02T13:20:01+00:00', started='2026-01-02T13:20:00+00:00')
    assert publish(root, receipt) == 'source_record_changed'
    assert len(pushes) == 1
    assert git(remote, 'show', 'main:docs/data.json') == revised
    assert git(remote, 'ls-tree', 'main', '--', 'docs/morning.json') == b''


def test_newly_committed_halt_cannot_be_erased_by_later_completion(tmp_path, repository, transport_schema, monkeypatch):
    root, remote, raw = repository
    other = competing_checkout(tmp_path, remote)
    halted = observation(raw, generated='2026-01-02T13:20:10+00:00',
                         started='2026-01-02T13:20:00+00:00', retained_halt='HALT')

    def advance():
        (other / 'docs/morning.json').write_bytes(encode(halted))
        git(other, 'add', 'docs/morning.json')
        git(other, 'commit', '-m', 'new unresolved halt')
        git(other, 'push', 'origin', 'main')

    pushes = race_once(monkeypatch, advance)
    delayed = observation(raw, generated='2026-01-02T13:21:20+00:00', started='2026-01-02T13:21:00+00:00')
    assert publish(root, delayed) == 'previous_observation_changed'
    assert len(pushes) == 1
    assert git(remote, 'show', 'main:docs/morning.json') == encode(halted)
    assert git(remote, 'show', 'main:docs/data.json') == raw


@pytest.mark.parametrize('started,generated', [
    ('2026-10-09T13:19:00+00:00', '2026-10-09T13:21:00+00:00'),  # old collection finishes last
    ('2026-10-09T13:20:00+00:00', '2026-10-09T13:20:02+00:00'),  # same collection start
    ('2026-10-09T13:20:01+00:00', '2026-10-09T13:20:01+00:00'),  # same completion
])
def test_same_source_collection_times_must_both_advance(transport_schema, started, generated):
    raw = b'{}'
    previous = encode(observation(raw))
    candidate = observation(raw, previous=previous, started=started, generated=generated)
    assert publisher.publication_check(candidate, raw, previous,
            datetime(2026, 10, 9, 14, tzinfo=timezone.utc)) == 'newer_or_equal_observation_exists'


def test_future_receipt_cannot_poison_monotonic_ordering(transport_schema):
    raw = b'{}'
    candidate = observation(raw, generated='2099-10-09T13:20:01+00:00')
    with pytest.raises(ValueError, match='future'):
        publisher.publication_check(candidate, raw, None, datetime(2026, 10, 9, 14, tzinfo=timezone.utc))


@pytest.mark.parametrize('ref,run_id,dry_run,reason', [
    ('refs/heads/rehearsal', '42', False, 'requires_main'),
    ('refs/heads/main', '42', True, 'rehearsal'),
    ('refs/heads/main', '41', False, 'run_mismatch'),
])
def test_wrong_branch_rehearsal_and_foreign_run_never_touch_remote(repository, transport_schema, ref, run_id, dry_run, reason):
    root, remote, raw = repository
    before = git(remote, 'rev-parse', 'main')
    with pytest.raises(ValueError, match=reason):
        publisher.publish(root, encode(observation(raw, dry_run=dry_run,
                generated='2026-01-02T13:20:01+00:00', started='2026-01-02T13:20:00+00:00')), ref=ref, run_id=run_id)
    assert git(remote, 'rev-parse', 'main') == before


def test_schema_validator_failure_prevents_any_commit(repository, monkeypatch):
    root, remote, raw = repository
    before = git(remote, 'rev-parse', 'main')

    def reject(value, source, **kwargs):
        raise ValueError('bound source evidence differs')

    monkeypatch.setattr(morning, 'validate_observation', reject)
    with pytest.raises(ValueError, match='evidence differs'):
        publish(root, observation(raw))
    assert git(remote, 'rev-parse', 'main') == before


def test_push_retries_are_bounded(repository, transport_schema, monkeypatch):
    root, remote, raw = repository
    original = publisher.git
    pushes = []

    def reject(root, *args, **kwargs):
        if args[0] == 'push':
            pushes.append(args)
            return subprocess.CompletedProcess(args, 1, b'', b'private response not printed')
        return original(root, *args, **kwargs)

    monkeypatch.setattr(publisher, 'git', reject)
    with pytest.raises(RuntimeError, match='retry_exhausted'):
        publish(root, observation(raw, generated='2026-01-02T13:20:01+00:00', started='2026-01-02T13:20:00+00:00'))
    assert len(pushes) == 3
    assert git(remote, 'ls-tree', 'main', '--', 'docs/morning.json') == b''


def test_snapshot_file_read_is_bounded_and_refuses_symlinks(tmp_path):
    large = tmp_path / 'large.json'
    large.write_bytes(b' ' * (publisher.MAX_SNAPSHOT_BYTES + 1))
    with pytest.raises(ValueError, match='size_invalid'):
        publisher.snapshot_file(large)
    link = tmp_path / 'link.json'
    link.symlink_to(large)
    with pytest.raises(ValueError, match='regular_file'):
        publisher.snapshot_file(link)


@pytest.fixture
def morning_record(monkeypatch):
    def binding(raw):
        data = json.loads(raw)
        return {'applicable_session': data['run']['timing']['applicable_session']}
    monkeypatch.setattr(morning, 'bind_record', binding)
    return lambda day, cutoff: encode({'run': {'timing': {'applicable_session': day, 'cutoff_at': cutoff}}})


@pytest.mark.parametrize('at,cron,session,cutoff', [
    ('2026-10-09T13:20:00+00:00', '20 13 * * 1-5', '2026-10-09', '2026-10-09T10:00:00-04:00'),
    ('2026-10-09T13:59:59+00:00', '28 13 * * 1-5', '2026-10-09', '2026-10-09T10:00:00-04:00'),
    ('2026-11-02T14:28:00+00:00', '28 14 * * 1-5', '2026-11-02', '2026-11-02T10:00:00-05:00'),
])
def test_active_summer_and_winter_slots_keep_exact_applicable_session(morning_record, at, cron, session, cutoff):
    assert publisher.schedule_guard(morning_record(session, cutoff), 'schedule', cron,
             datetime.fromisoformat(at)) == (True, 'scheduled_morning')


@pytest.mark.parametrize('at,cron,day,cutoff,reason', [
    ('2026-10-09T14:20:00+00:00', '20 14 * * 1-5', '2026-10-09', '2026-10-09T10:00:00-04:00', 'inactive_schedule'),
    ('2026-11-02T13:28:00+00:00', '28 13 * * 1-5', '2026-11-02', '2026-11-02T10:00:00-05:00', 'inactive_schedule'),
    ('2026-10-09T14:00:00+00:00', '20 13 * * 1-5', '2026-10-09', '2026-10-09T10:00:00-04:00', 'entry_window_ended'),
    ('2026-10-10T05:00:00+00:00', '20 13 * * 1-5', '2026-10-09', '2026-10-09T10:00:00-04:00', 'scheduled_day_expired'),
    ('2026-10-10T13:20:00+00:00', '20 13 * * 1-5', '2026-10-09', '2026-10-09T10:00:00-04:00', 'inactive_schedule'),
    ('2026-11-26T14:20:00+00:00', '20 14 * * 1-5', '2026-11-26', '2026-11-26T10:00:00-05:00', 'not_exchange_session'),
    ('2026-10-09T13:20:00+00:00', '20 13 * * 1-5', '2026-10-08', '2026-10-08T10:00:00-04:00', 'record_for_another_session'),
])
def test_inactive_holiday_delayed_foreign_and_expired_slots_skip(morning_record, at, cron, day, cutoff, reason):
    assert publisher.schedule_guard(morning_record(day, cutoff), 'schedule', cron,
             datetime.fromisoformat(at)) == (False, reason)


def test_manual_after_cutoff_reaches_collector_for_honest_inapplicable_receipt():
    assert publisher.schedule_guard(b'{}', 'workflow_dispatch', '',
             datetime(2026, 10, 9, 18, tzinfo=timezone.utc)) == (True, 'manual_dispatch')


def test_unknown_schedule_or_malformed_record_cannot_collect():
    now = datetime(2026, 10, 9, 13, 20, tzinfo=timezone.utc)
    assert publisher.schedule_guard(b'{}', 'schedule', 'not cron', now) == (False, 'unknown_schedule')
    assert publisher.schedule_guard(b'{broken', 'schedule', '20 13 * * 1-5', now) == (False, 'invalid_publication')


def test_dashboard_publication_fetches_optional_morning_once_committed(tmp_path, monkeypatch):
    from tools import publish_dashboard
    from tests.test_publish_dashboard import write_reader_records
    docs = tmp_path / 'docs'
    docs.mkdir()
    (docs / 'index.html').write_text('<html></html>')
    write_reader_records(docs)
    assert 'morning.json' not in publish_dashboard.public_files(tmp_path)
    receipt = b'{"dated":"observation"}\n'
    (docs / 'morning.json').write_bytes(receipt)
    requests = []

    def api(repository, endpoint, method='GET'):
        if endpoint == 'pages':
            return {'build_type': 'legacy', 'source': {'branch': 'main', 'path': '/docs'},
                    'html_url': 'https://example.invalid/SpicyStock/'}
        assert endpoint == 'pages/builds' and method == 'POST'
        return {'status': 'queued'}

    def public_bytes(url, timeout):
        from urllib.parse import urlsplit
        name = urlsplit(url).path.removeprefix('/SpicyStock/')
        requests.append(name)
        return (docs / name).read_bytes()

    monkeypatch.setattr(publish_dashboard, 'github_api', api)
    monkeypatch.setattr(publish_dashboard, 'public_bytes', public_bytes)
    publish_dashboard.publish('owner/repository', tmp_path)
    assert requests.count('morning.json') == 1


def test_real_collector_receipt_passes_publication_validator_without_provider_calls(monkeypatch):
    raw = (Path(__file__).resolve().parent.parent / 'docs/data.json').read_bytes()
    data = json.loads(raw)
    after_cutoff = datetime.fromisoformat(data['run']['timing']['cutoff_at']) + timedelta(seconds=1)

    def forbidden(*args, **kwargs):
        raise AssertionError('An inapplicable receipt must not request a provider')

    monkeypatch.setattr(morning, '_fetch', forbidden)
    receipt = morning.collect(raw, clock=lambda: after_cutoff, observation_run_id='42')
    assert receipt['status'] == 'inapplicable'
    assert receipt['previous_observation_sha256'] is None
    assert publisher.publication_check(receipt, raw, None, now=after_cutoff) is None
    receipt['publication']['run_id'] = 'foreign-publication'
    with pytest.raises(ValueError, match='binding'):
        publisher.publication_check(receipt, raw, None, now=after_cutoff)


# ------------------------------------------------- the research target -----
STOP_FIXTURES = Path(__file__).resolve().parent / 'fixtures/stop-research'
RESEARCH_FIXTURES = Path(__file__).resolve().parent / 'fixtures/research-observations'


def research_observation(raw, receipt_raw, *, previous=None, started='2026-01-02T13:20:00+00:00',
                         generated='2026-01-02T13:20:01+00:00', **changes):
    cohort = {'receipt_sha256': hashlib.sha256(receipt_raw).hexdigest()} if receipt_raw is not None else None
    return {'dry_run': False, 'publication': {'data_sha256': hashlib.sha256(raw).hexdigest()},
            'previous_observation_sha256': hashlib.sha256(previous).hexdigest() if previous else None,
            'collection_started_at': started, 'generated_at': generated, 'cohort': cohort,
            'observation_run_id': '42', 'status': 'observed', **changes}


@pytest.fixture
def research_schema(monkeypatch):
    from src import research_observations
    monkeypatch.setattr(research_observations, 'validate_observation', lambda *args, **kwargs: None)


@pytest.fixture
def research_repository(repository):
    root, remote, raw = repository
    receipt_raw = (STOP_FIXTURES / 'current-receipt.json').read_bytes()
    bundle_raw = (STOP_FIXTURES / 'current-bundle.json').read_bytes()
    (root / 'docs/stop-research').mkdir()
    (root / 'docs/stop-research.json').write_bytes(receipt_raw)
    (root / 'docs' / json.loads(receipt_raw)['bundle']['path']).write_bytes(bundle_raw)
    (root / 'docs/morning.json').write_bytes(b'{"morning":"untouched"}\n')
    git(root, 'add', 'docs')
    git(root, 'commit', '-m', 'cohort beside the record')
    git(root, 'push', 'origin', 'main')
    return root, remote, raw, receipt_raw


def test_research_target_commits_only_its_own_file_beside_the_cohort(research_repository, research_schema):
    root, remote, raw, receipt_raw = research_repository
    prior = git(remote, 'rev-parse', 'main').strip()
    receipt = research_observation(raw, receipt_raw)
    assert publisher.publish(root, encode(receipt), ref='refs/heads/main', run_id='42', target='research') == 'published'
    assert git(remote, 'show', 'main:docs/research-observations.json') == encode(receipt)
    assert git(remote, 'show', 'main:docs/morning.json') == b'{"morning":"untouched"}\n'
    assert git(remote, 'show', 'main:docs/stop-research.json') == receipt_raw
    assert git(remote, 'rev-parse', 'main^').strip() == prior
    assert git(remote, 'diff-tree', '--no-commit-id', '--name-only', '-r', 'main') == b'docs/research-observations.json\n'
    assert git(remote, 'log', '-1', '--format=%s', 'main').strip() == b'Publish bound research observation'


def test_research_target_refuses_when_main_replaced_the_cohort(tmp_path, research_repository, research_schema, monkeypatch):
    root, remote, raw, receipt_raw = research_repository
    other = competing_checkout(tmp_path, remote)
    red_receipt = (STOP_FIXTURES / 'red-receipt.json').read_bytes()
    red_bundle = (STOP_FIXTURES / 'red-bundle.json').read_bytes()

    def advance():
        (other / 'docs/stop-research.json').write_bytes(red_receipt)
        (other / 'docs' / json.loads(red_receipt)['bundle']['path']).write_bytes(red_bundle)
        git(other, 'add', 'docs')
        git(other, 'commit', '-m', 'replaced cohort')
        git(other, 'push', 'origin', 'main')

    pushes = race_once(monkeypatch, advance)
    assert publisher.publish(root, encode(research_observation(raw, receipt_raw)), ref='refs/heads/main',
                             run_id='42', target='research') == 'research_cohort_changed'
    assert len(pushes) == 1
    assert git(remote, 'ls-tree', 'main', '--', 'docs/research-observations.json') == b''


def test_research_check_races_and_ordering(research_schema):
    raw, receipt_raw, bundle_raw = b'{}', b'{"receipt":1}', b'{"bundle":1}'
    now = datetime(2026, 10, 12, 14, tzinfo=timezone.utc)
    check = lambda value, previous=None: publisher.research_check(value, raw, receipt_raw, bundle_raw, previous, now)
    assert check(research_observation(raw, receipt_raw)) is None
    assert check(research_observation(b'other', receipt_raw)) == 'source_record_changed'
    assert check(research_observation(raw, b'other receipt')) == 'research_cohort_changed'
    assert check(research_observation(raw, None)) == 'research_cohort_changed'
    assert publisher.research_check(research_observation(raw, None), raw, None, None, None, now) is None
    previous = encode(research_observation(raw, receipt_raw))
    assert check(research_observation(raw, receipt_raw)) is None  # a prior the observation never saw
    assert check(research_observation(raw, receipt_raw), previous) == 'previous_observation_changed'
    assert check(research_observation(raw, receipt_raw, previous=previous, started='2026-01-02T13:20:00+00:00',
                                      generated='2026-01-02T13:20:02+00:00'), previous) == 'newer_or_equal_observation_exists'
    assert check(research_observation(raw, receipt_raw, previous=previous, started='2026-01-02T13:21:00+00:00',
                                      generated='2026-01-02T13:21:02+00:00'), previous) is None
    with pytest.raises(ValueError, match='future'):
        check(research_observation(raw, receipt_raw, generated='2099-10-12T13:20:01+00:00'))
    with pytest.raises(ValueError, match='rehearsal'):
        check(research_observation(raw, receipt_raw, dry_run=True))
    with pytest.raises(ValueError, match='unknown_publication_target'):
        publisher.publish(Path('.'), encode(research_observation(raw, receipt_raw)), ref='refs/heads/main', run_id='42', target='evening')


def test_research_validator_failure_prevents_any_commit(research_repository, monkeypatch):
    from src import research_observations
    root, remote, raw, receipt_raw = research_repository
    before = git(remote, 'rev-parse', 'main')
    seen = []

    def reject(value, data_raw, cohort_receipt=None, cohort_bundle=None, **kwargs):
        seen.append((data_raw, cohort_receipt, cohort_bundle is not None, kwargs.get('require_continuity')))
        raise ValueError('bound cohort evidence differs')

    monkeypatch.setattr(research_observations, 'validate_observation', reject)
    with pytest.raises(ValueError, match='evidence differs'):
        publisher.publish(root, encode(research_observation(raw, receipt_raw)), ref='refs/heads/main', run_id='42', target='research')
    assert git(remote, 'rev-parse', 'main') == before
    assert seen == [(raw, receipt_raw, True, True)]


def test_real_research_collector_receipt_passes_the_publisher_without_provider_calls(monkeypatch):
    from src import research_observations
    root = Path(__file__).resolve().parent.parent
    raw = (root / 'docs/data.json').read_bytes()
    receipt_raw, bundle_raw = research_observations.read_cohort(root / 'docs')
    data = json.loads(raw)
    after_cutoff = datetime.fromisoformat(data['run']['timing']['cutoff_at']) + timedelta(seconds=1)
    monkeypatch.setattr(morning, '_fetch', lambda *args, **kwargs: pytest.fail('An inapplicable receipt must not request a provider'))
    receipt = research_observations.collect(raw, receipt_raw, bundle_raw, clock=lambda: after_cutoff, observation_run_id='42')
    assert receipt['status'] == 'inapplicable' and receipt['source']['requests'] == 0
    assert publisher.research_check(receipt, raw, receipt_raw, bundle_raw, None, now=after_cutoff) is None
    receipt['publication']['run_id'] = 'foreign-publication'
    with pytest.raises(ValueError, match='binding'):
        publisher.research_check(receipt, raw, receipt_raw, bundle_raw, None, now=after_cutoff)


def test_dashboard_publication_fetches_optional_research_observation_once_committed(tmp_path):
    from tools import publish_dashboard
    from tests.test_publish_dashboard import write_reader_records
    docs = tmp_path / 'docs'
    docs.mkdir()
    (docs / 'index.html').write_text('<html></html>')
    write_reader_records(docs)
    assert 'research-observations.json' not in publish_dashboard.public_files(tmp_path)
    (docs / 'research-observations.json').write_bytes(b'{"dated":"research observation"}\n')
    assert 'research-observations.json' in publish_dashboard.public_files(tmp_path)
