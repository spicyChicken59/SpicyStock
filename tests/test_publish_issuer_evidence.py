"""Execute issuer CAS, retention and daily budgeting without providers."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.parse import parse_qs, urlsplit

import pytest

from src import issuer_evidence as issuer
from tools import publish_issuer_evidence as publisher

NOW = datetime(2026, 10, 10, 8, tzinfo=timezone.utc)


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True).stdout


def candidate(raw, *, previous=None, now=NOW, run_id='42', dry_run=False, marker='source'):
    bundle = publisher.encode({'synthetic_transport': marker, 'generated_at': now.isoformat()})
    sha = hashlib.sha256(bundle).hexdigest()
    receipt = publisher.encode({'dry_run': dry_run, 'collection_run_id': run_id,
        'collection_started_at': (now - timedelta(seconds=1)).isoformat(), 'generated_at': now.isoformat(),
        'publication': {'data_sha256': publisher.digest(raw)},
        'previous_receipt_sha256': publisher.digest(previous),
        'bundle': {'sha256': sha, 'bytes': len(bundle), 'path': f'issuer-evidence/{sha}.json'}})
    return receipt, bundle


@pytest.fixture
def transport_schema(monkeypatch):
    # Full source/candidate/provenance validation belongs to the backend suite;
    # these small controls exercise actual Git transport and filesystem races.
    monkeypatch.setattr(issuer, 'parse_receipt', json.loads)

    def validate(raw, bundle):
        ref = json.loads(raw)['bundle']
        assert ref == {'path': 'issuer-evidence/' + publisher.digest(bundle) + '.json',
                       'sha256': publisher.digest(bundle), 'bytes': len(bundle)}
        return json.loads(bundle)

    monkeypatch.setattr(issuer, 'validate_bundle', validate)
    monkeypatch.setattr(issuer, 'validate_for_publication', lambda source, raw, bundle: validate(raw, bundle))


@pytest.fixture
def repository(tmp_path):
    remote = tmp_path / 'remote.git'
    subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
    root = tmp_path / 'checkout'
    subprocess.run(['git', 'clone', str(remote), str(root)], check=True, capture_output=True)
    git(root, 'checkout', '-b', 'main')
    git(root, 'config', 'user.name', 'test'); git(root, 'config', 'user.email', 'test@example.invalid')
    (root / 'docs/evidence').mkdir(parents=True)
    (root / 'docs/history').mkdir()
    raw = b'{"run":{"run_id":"previous-evening"}}\n'
    (root / 'docs/data.json').write_bytes(raw)
    (root / 'docs/picks.json').write_text('{"model_history":"preserved"}\n')
    (root / 'docs/evidence/old.json').write_text('immutable evidence')
    (root / 'docs/history/old.json').write_text('immutable history')
    (root / 'notes.txt').write_text('original')
    git(root, 'add', '.'); git(root, 'commit', '-m', 'baseline'); git(root, 'push', '-u', 'origin', 'main')
    return root, remote, raw


def publish(root, pair, now=NOW, **options):
    return publisher.publish(root, *pair, ref='refs/heads/main', run_id='42', now=now, **options)


def other_checkout(tmp_path, remote):
    root = tmp_path / 'other'
    subprocess.run(['git', 'clone', '--branch', 'main', str(remote), str(root)], check=True, capture_output=True)
    git(root, 'config', 'user.name', 'other'); git(root, 'config', 'user.email', 'other@example.invalid')
    return root


def race_once(monkeypatch, advance):
    real = publisher.git
    pushes = []
    def raced(root, *args, **kwargs):
        if args[0] == 'push':
            pushes.append(args)
            if len(pushes) == 1:
                advance()
        return real(root, *args, **kwargs)
    monkeypatch.setattr(publisher, 'git', raced)
    return pushes


def test_atomic_fixed_paths_preserve_model_history_and_private_index(repository, transport_schema):
    root, remote, raw = repository
    before = git(remote, 'rev-parse', 'main').strip()
    (root / 'notes.txt').write_text('private staged work'); git(root, 'add', 'notes.txt')
    pair = candidate(raw)
    assert publish(root, pair) == 'published'
    receipt = json.loads(pair[0])
    assert git(remote, 'show', 'main:docs/issuer-evidence.json') == pair[0]
    assert git(remote, 'show', 'main:docs/' + receipt['bundle']['path']) == pair[1]
    assert git(remote, 'show', 'main:docs/data.json') == raw
    assert git(remote, 'show', 'main:docs/picks.json') == b'{"model_history":"preserved"}\n'
    for name in ('evidence', 'history'):
        assert git(remote, 'show', f'main:docs/{name}/old.json') == f'immutable {name}'.encode()
    assert git(remote, 'show', 'main:notes.txt') == b'original'
    assert git(remote, 'rev-parse', 'main^').strip() == before
    assert git(root, 'diff', '--cached', '--name-only') == b'notes.txt\n'
    assert set(git(remote, 'diff-tree', '--no-commit-id', '--name-only', '-r', 'main').decode().splitlines()) == {
        publisher.RECEIPT_PATH, publisher.MANIFEST_PATH, 'docs/' + receipt['bundle']['path']}


@pytest.mark.parametrize('changed,expected', [('source', 'source_record_changed'), ('receipt', 'previous_receipt_changed')])
def test_concurrent_source_or_receipt_change_aborts(tmp_path, repository, transport_schema, monkeypatch, changed, expected):
    root, remote, raw = repository
    other = other_checkout(tmp_path, remote)
    def advance():
        path = 'data.json' if changed == 'source' else 'issuer-evidence.json'
        if changed == 'source':
            (other / 'docs' / path).write_bytes(raw + b' ')
        else:
            prior_receipt, prior_bundle = candidate(raw, marker='other')
            (other / 'docs' / path).write_bytes(prior_receipt)
            bundle_path = other / 'docs' / json.loads(prior_receipt)['bundle']['path']
            bundle_path.parent.mkdir(); bundle_path.write_bytes(prior_bundle)
        git(other, 'add', 'docs'); git(other, 'commit', '-m', 'concurrent'); git(other, 'push', 'origin', 'main')
    pushes = race_once(monkeypatch, advance)
    later = NOW + timedelta(seconds=2)
    assert publish(root, candidate(raw, now=later), now=later) == expected
    assert len(pushes) == 1
    assert git(remote, 'ls-tree', 'main', '--', publisher.MANIFEST_PATH) == b''
    if changed == 'receipt':
        assert git(remote, 'show', 'main:' + publisher.RECEIPT_PATH) == candidate(raw, marker='other')[0]


def test_unrelated_commit_retries_without_rebase_or_lost_work(tmp_path, repository, transport_schema, monkeypatch):
    root, remote, raw = repository
    other = other_checkout(tmp_path, remote)
    def advance():
        (other / 'independent.txt').write_text('keep me')
        git(other, 'add', 'independent.txt'); git(other, 'commit', '-m', 'unrelated'); git(other, 'push', 'origin', 'main')
    pushes = race_once(monkeypatch, advance)
    assert publish(root, candidate(raw)) == 'published'
    assert len(pushes) == 2 and all('--force' not in args for args in pushes)
    assert git(remote, 'show', 'main:independent.txt') == b'keep me'


def test_retries_stop_after_three_rejections(repository, transport_schema, monkeypatch):
    root, remote, raw = repository
    real = publisher.git; pushes = []
    def refused(root, *args, **kwargs):
        if args[0] == 'push':
            pushes.append(args)
            return subprocess.CompletedProcess(args, 1, b'', b'private response')
        return real(root, *args, **kwargs)
    monkeypatch.setattr(publisher, 'git', refused)
    with pytest.raises(RuntimeError, match='retry_exhausted'):
        publish(root, candidate(raw))
    assert len(pushes) == 3
    assert not git(remote, 'ls-tree', 'main', '--', publisher.RECEIPT_PATH)


@pytest.mark.parametrize('option,value', [('ref', 'refs/heads/review'), ('run_id', 'other')])
def test_wrong_branch_or_run_cannot_publish(repository, transport_schema, option, value):
    root, remote, raw = repository
    args = {'ref': 'refs/heads/main', 'run_id': '42', 'now': NOW, option: value}
    with pytest.raises(ValueError):
        publisher.publish(root, *candidate(raw), **args)
    assert not git(remote, 'ls-tree', 'main', '--', publisher.RECEIPT_PATH)


def test_rehearsal_future_clock_and_validator_refusal_cannot_publish(repository, transport_schema, monkeypatch):
    root, remote, raw = repository
    with pytest.raises(ValueError, match='rehearsal'):
        publish(root, candidate(raw, dry_run=True))
    with pytest.raises(ValueError, match='future'):
        publish(root, candidate(raw, now=NOW + timedelta(seconds=6)))
    def refuse(*args):
        raise ValueError('strict source validation refused')
    monkeypatch.setattr(issuer, 'validate_for_publication', refuse)
    with pytest.raises(ValueError, match='strict source'):
        publish(root, candidate(raw))
    assert not git(remote, 'ls-tree', 'main', '--', publisher.RECEIPT_PATH)


def test_receipt_times_must_advance_even_when_source_is_same(transport_schema):
    raw = b'{}'; first = candidate(raw)
    for at in (NOW - timedelta(seconds=1), NOW):
        receipt, bundle = candidate(raw, previous=first[0], now=at)
        assert publisher.publication_check(raw, receipt, bundle, first[0], now=NOW) == 'newer_or_equal_receipt_exists'


def test_previous_receipt_removal_is_a_cas_change(transport_schema):
    raw = b'{}'; first = candidate(raw)
    receipt, bundle = candidate(raw, previous=first[0], now=NOW + timedelta(seconds=1))
    assert publisher.publication_check(raw, receipt, bundle, None, now=NOW) == 'previous_receipt_changed'


def test_retention_uses_actual_supersession_time_and_preserves_unknowns(tmp_path, repository, transport_schema):
    root, remote, raw = repository
    first = candidate(raw, now=NOW - timedelta(days=100))
    assert publish(root, first, now=NOW - timedelta(days=100)) == 'published'
    # Superseding a very old current object starts a NEW 21-day grace clock.
    second = candidate(raw, previous=first[0], now=NOW)
    assert publish(root, second) == 'published'
    first_path = 'docs/' + json.loads(first[0])['bundle']['path']
    assert git(remote, 'show', 'main:' + first_path) == first[1]
    other = other_checkout(tmp_path, remote)
    (other / publisher.DIRECTORY / 'unowned.json').write_bytes(b'keep unknown file')
    git(other, 'add', publisher.DIRECTORY); git(other, 'commit', '-m', 'unknown'); git(other, 'push', 'origin', 'main')
    third = candidate(raw, previous=second[0], now=NOW + timedelta(days=21))
    assert publish(root, third, now=NOW + timedelta(days=21)) == 'published'
    assert git(remote, 'show', 'main:' + first_path) == first[1]  # boundary is inclusive
    fourth = candidate(raw, previous=third[0], now=NOW + timedelta(days=21, seconds=1))
    assert publish(root, fourth, now=NOW + timedelta(days=21, seconds=1)) == 'published'
    assert not git(remote, 'ls-tree', 'main', '--', first_path)
    assert git(remote, 'show', 'main:' + publisher.DIRECTORY + '/unowned.json') == b'keep unknown file'
    for pair in (second, third, fourth):
        assert git(remote, 'show', 'main:docs/' + json.loads(pair[0])['bundle']['path']) == pair[1]


def test_capacity_refusal_never_deletes_unowned_files(repository, transport_schema, monkeypatch):
    root, remote, raw = repository
    directory = root / publisher.DIRECTORY; directory.mkdir()
    (directory / 'one.json').write_text('one'); (directory / 'two.json').write_text('two')
    git(root, 'add', publisher.DIRECTORY); git(root, 'commit', '-m', 'unknowns'); git(root, 'push', 'origin', 'main')
    before = git(remote, 'rev-parse', 'main')
    monkeypatch.setattr(publisher, 'MAX_OBJECTS', 2)
    with pytest.raises(ValueError, match='capacity'):
        publish(root, candidate(raw))
    assert git(remote, 'rev-parse', 'main') == before


def test_tampered_owned_object_is_refused(tmp_path, repository, transport_schema):
    root, remote, raw = repository
    first = candidate(raw)
    assert publish(root, first) == 'published'
    other = other_checkout(tmp_path, remote)
    (other / 'docs' / json.loads(first[0])['bundle']['path']).write_bytes(b'tampered')
    git(other, 'add', publisher.DIRECTORY); git(other, 'commit', '-m', 'tamper'); git(other, 'push', 'origin', 'main')
    with pytest.raises((ValueError, AssertionError)):
        publish(root, candidate(raw, previous=first[0], now=NOW + timedelta(seconds=2)), now=NOW + timedelta(seconds=2))


def test_bounded_input_refuses_symlink_and_oversize(tmp_path):
    path = tmp_path / 'source'; path.write_bytes(b'123')
    with pytest.raises(ValueError, match='size'):
        publisher.bounded_file(path, 2)
    link = tmp_path / 'link'; link.symlink_to(path)
    with pytest.raises(ValueError, match='regular'):
        publisher.bounded_file(link, 10)


def history_api(runs, attempts):
    def fetch(repo, endpoint):
        if '/workflows/' in endpoint:
            page = int(parse_qs(urlsplit(endpoint).query)['page'][0])
            return {'total_count': len(runs), 'workflow_runs': runs[(page - 1) * 100:page * 100]}
        parts = endpoint.split('/')
        jobs = attempts[(int(parts[2]), int(parts[4]))]
        return {'total_count': len(jobs), 'jobs': jobs}
    return fetch


def run(number=1, attempts=1, updated=NOW):
    return {'id': number, 'head_branch': 'main', 'updated_at': updated.isoformat(), 'run_attempt': attempts}


def job(status='completed', conclusion='success', at=NOW, name=publisher.PRODUCTION_STEP):
    return {'steps': [{'name': name, 'status': status, 'conclusion': conclusion,
                       'started_at': at.isoformat() if at is not None else None}]}


def test_daily_budget_counts_started_failed_and_in_progress_attempts_only():
    jobs = [job(conclusion='failure'), job(status='in_progress', conclusion=None),
            job(conclusion='skipped'), job(status='pending', conclusion=None, at=None),
            job(name='Collect issuer evidence (rehearsal)'), job(at=NOW - timedelta(days=1))]
    fetch = history_api([run(attempts=2)], {(1, 1): jobs, (1, 2): [job()]})
    assert publisher.daily_collections('owner/repo', NOW, fetch=fetch) == 3


def test_daily_budget_paginates_and_includes_old_created_recently_updated_runs():
    rows = [run(i, updated=NOW - timedelta(days=1)) for i in range(100)] + [run(100)]
    assert publisher.daily_collections('owner/repo', NOW,
            fetch=history_api(rows, {(100, 1): [job()]})) == 1


@pytest.mark.parametrize('response', [
    {'total_count': 501, 'workflow_runs': []}, {'total_count': 1, 'workflow_runs': []},
    {'total_count': 2, 'workflow_runs': [run(), run()]}, {'workflow_runs': []},
])
def test_incomplete_or_oversize_history_refuses_collection(response):
    with pytest.raises(ValueError, match='history'):
        publisher.daily_collections('owner/repo', NOW, fetch=lambda *args: response)


@pytest.mark.parametrize('bad', [None, [], {'unexpected': 'shape'}])
def test_missing_job_step_metadata_cannot_be_assumed_to_cost_zero(bad):
    fetch = history_api([run()], {(1, 1): [{'steps': bad}]})
    if bad == []:  # a newly queued job can honestly have no started steps
        assert publisher.daily_collections('owner/repo', NOW, fetch=fetch) == 0
    else:
        with pytest.raises(ValueError, match='step_history'):
            publisher.daily_collections('owner/repo', NOW, fetch=fetch)


def parent(name=publisher.EVENING_NAME, number=99, conclusion='success'):
    return {'workflow_run': {'head_repository': {'full_name': 'owner/repo'}, 'head_branch': 'main',
            'name': name, 'id': number, 'status': 'completed', 'conclusion': conclusion}}


def guard(event, *, raw=b'{"run":{"run_id":"99"}}', morning=None, name='workflow_run',
          ref='refs/heads/main', fetch=None):
    return publisher.collection_guard(raw, morning, event, event_name=name, ref=ref,
        repository='owner/repo', now=NOW, fetch=fetch or history_api([], {}))


def test_inactive_or_unpublished_parents_spend_no_collection_budget():
    def unexpected(*args):
        pytest.fail('ineligible parent queried collection history')
    assert guard(parent(number=98), fetch=unexpected)[0] is False
    assert guard(parent(conclusion='failure'), fetch=unexpected)[0] is False
    assert guard(parent(publisher.MORNING_NAME), fetch=unexpected)[0] is False
    assert guard(parent('Publish committed dashboard'), fetch=unexpected)[0] is False
    assert guard(parent(), ref='refs/heads/branch', fetch=unexpected)[0] is False
    missing_id = parent(); del missing_id['workflow_run']['id']
    assert guard(missing_id, fetch=unexpected)[0] is False
    assert guard({'inputs': {'dry_run': True}}, name='workflow_dispatch', ref='refs/heads/branch', fetch=unexpected) == (True, 'manual_rehearsal')


def test_current_publication_and_bound_morning_trigger_production():
    raw = b'{"run":{"run_id":"99"}}'
    morning = publisher.encode({'observation_run_id': '100', 'publication': {'data_sha256': publisher.digest(raw)}})
    assert guard(parent()) == (True, 'production_collection')
    assert guard(parent(publisher.MORNING_NAME, number=100), morning=morning) == (True, 'production_collection')
    assert guard(parent(publisher.MORNING_NAME, number=100), raw=raw + b' ', morning=morning)[0] is False


def test_main_manual_real_collection_shares_production_daily_limit():
    fetch = history_api([run()], {(1, 1): [job(), job(), job()]})
    event = {'inputs': {'dry_run': 'false'}}
    assert guard(event, name='workflow_dispatch', fetch=fetch) == (False, 'daily_collection_limit')
    assert guard(event, name='workflow_dispatch') == (True, 'production_collection')


def test_missing_branch_and_future_start_metadata_fail_closed():
    incomplete = run(); incomplete.pop('head_branch')
    with pytest.raises(ValueError, match='branch_history'):
        publisher.daily_collections('owner/repo', NOW, fetch=history_api([incomplete], {}))
    with pytest.raises(ValueError, match='future'):
        publisher.daily_collections('owner/repo', NOW,
            fetch=history_api([run()], {(1, 1): [job(at=NOW + timedelta(seconds=6))]}))
    for jobs in ([None], [{'steps': [None]}], [{'steps': [{'unexpected': 'shape'}]}]):
        with pytest.raises(ValueError, match='step_history'):
            publisher.daily_collections('owner/repo', NOW, fetch=history_api([run()], {(1, 1): jobs}))


def test_real_collector_contract_publishes_with_strict_current_binding(repository):
    root, remote, _ = repository
    raw = (Path(__file__).parent / 'fixtures/morning/full-publication.json').read_bytes()
    (root / 'docs/data.json').write_bytes(raw)
    git(root, 'add', 'docs/data.json'); git(root, 'commit', '-m', 'verified fixture source'); git(root, 'push', 'origin', 'main')
    def no_provider(url):
        raise AssertionError('inapplicable receipt must not call provider')
    output = issuer.collect(raw, fetch=no_provider, now=NOW, run_id='42', dry_run=False)
    assert publish(root, (output['receipt_bytes'], output['bundle_bytes'])) == 'published'
    saved = git(remote, 'show', 'main:docs/issuer-evidence.json')
    assert saved == output['receipt_bytes']
    issuer.validate_for_publication(raw, saved, output['bundle_bytes'])


def test_real_schema_rejects_rebound_reader_identity(repository):
    root, remote, _ = repository
    raw = (Path(__file__).parent / 'fixtures/morning/full-publication.json').read_bytes()
    (root / 'docs/data.json').write_bytes(raw)
    git(root, 'add', 'docs/data.json'); git(root, 'commit', '-m', 'verified fixture source'); git(root, 'push', 'origin', 'main')
    output = issuer.collect(raw, fetch=lambda url: pytest.fail('unexpected provider'), now=NOW, run_id='42', dry_run=False)
    receipt, bundle = output['receipt'], output['bundle']
    for value in (receipt, bundle):
        value['publication']['reader_sha256'] = '0' * 64
    bundle_raw = publisher.encode(bundle)
    receipt['bundle'] = {'sha256': publisher.digest(bundle_raw), 'bytes': len(bundle_raw),
                         'path': 'issuer-evidence/' + publisher.digest(bundle_raw) + '.json'}
    receipt_raw = publisher.encode(receipt)
    issuer.validate_bundle(receipt_raw, bundle_raw)  # self-integrity alone is insufficient
    with pytest.raises(ValueError, match='publication binding'):
        publish(root, (receipt_raw, bundle_raw))
    assert not git(remote, 'ls-tree', 'main', '--', publisher.RECEIPT_PATH)


def test_unknown_cache_file_is_preserved_and_cannot_be_saved(tmp_path):
    cache = tmp_path / 'cache'; cache.mkdir()
    unknown = cache / 'unknown.json'; unknown.write_bytes(b'not owned')
    assert publisher.cache_saveable(cache) is False
    assert unknown.read_bytes() == b'not owned'
    assert publisher.cache_saveable(tmp_path / 'missing') is False


def test_cache_gate_requires_full_validation_and_owned_expiry_cleanup(tmp_path, monkeypatch):
    calls = []
    def valid(path, *, prune):
        calls.append((path, prune))
        return {'entries': 1}
    monkeypatch.setattr(issuer, 'validate_cache', valid)
    assert publisher.cache_saveable(tmp_path) is True
    assert calls == [(tmp_path, True)]
    def rejected(*args, **kwargs):
        raise ValueError('private diagnostic must not be printed')
    monkeypatch.setattr(issuer, 'validate_cache', rejected)
    assert publisher.cache_saveable(tmp_path) is False
