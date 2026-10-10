"""Optional local follow-through cannot alter plans or weaken served-byte checks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

import pytest

from src import pipeline
from tools import publish_dashboard as publisher
from tests.test_pipeline import claude, evening, market
from tests.test_publish_dashboard import publication


@pytest.mark.parametrize('delivery', ['delivered', 'skipped', 'failed', 'dry_run'])
@pytest.mark.parametrize('cohort_refused', [False, True])
def test_outcomes_follow_final_bytes_and_the_optional_cohort_attempt(
        market, claude, fake_resend, tmp_path, monkeypatch, delivery, cohort_refused):
    from src import research_outcomes, stop_research
    calls = []

    def capture_cohort(raw, docs, **kwargs):
        calls.append(('cohort', raw))
        if cohort_refused:
            raise ValueError('offline optional cohort refusal')
        return {}

    def capture(raw, docs, *, objects, picks=None, allow_fixture=False):
        calls.append(('outcomes', raw, docs, objects, json.loads(json.dumps(picks)), allow_fixture))
        return {}

    monkeypatch.setattr(stop_research, 'write_publication', capture_cohort)
    monkeypatch.setattr(research_outcomes, 'write_publication', capture)
    if delivery == 'failed':
        fake_resend.raises = RuntimeError('offline delivery refusal')
    elif delivery == 'skipped':
        monkeypatch.setenv('SCAN_SEND_EMAIL', 'false')
    rep, data, docs = evening(tmp_path, market, dry_run=delivery == 'dry_run')
    assert [call[0] for call in calls] == ['cohort', 'outcomes']
    _, raw, output, objects, picks, allow_fixture = calls[1]
    assert calls[0][1] == raw == (docs / 'data.json').read_bytes()
    assert output == docs and objects == docs / 'evidence' and objects.is_dir()
    assert allow_fixture is False
    assert data['run']['email'] == ('skipped' if delivery == 'dry_run' else delivery)
    assert rep.exit_code() == (pipeline.EXIT_FAILED_AFTER_PUBLISH if delivery == 'failed' else 0)
    if delivery == 'dry_run':
        assert not (docs / 'picks.json').exists()
    else:
        assert picks == json.loads((docs / 'picks.json').read_bytes())


def test_optional_outcomes_failure_preserves_record_original_cohorts_and_journal(
        market, claude, fake_resend, tmp_path, monkeypatch, caplog):
    from src import research_outcomes, stop_research
    docs = tmp_path / 'docs'
    retained = {
        'research-outcomes.json': b'older-receipt-transport-control',
        'research-outcomes/index.json': b'append-only-journal-control',
        'research-outcomes/' + 'a' * 64 + '.json': b'older-snapshot-control',
        'stop-research/index.json': b'original-cohort-index-control',
        'stop-research/' + 'b' * 64 + '.json': b'original-cohort-control',
    }
    for name, raw in retained.items():
        path = docs / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    captured = []

    def refuse(raw, *args, **kwargs):
        captured.append(raw)
        raise ValueError('private diagnostic must not enter publication or logs')

    monkeypatch.setattr(stop_research, 'write_publication', lambda *args, **kwargs: {})
    monkeypatch.setattr(research_outcomes, 'write_publication', refuse)
    rep, data, _ = evening(tmp_path, market)
    assert rep.exit_code() == 0 and data['run']['status'] == 'ok'
    assert data['run']['email'] == 'delivered' and data['run']['problems'] == []
    assert captured == [(docs / 'data.json').read_bytes()]
    assert (docs / 'picks.json').is_file() and (docs / 'history/index.json').is_file()
    assert {name: (docs / name).read_bytes() for name in retained} == retained
    assert 'Research outcomes publication unavailable (ValueError)' in caplog.text
    assert 'private diagnostic' not in caplog.text


def account(monkeypatch):
    for name, value in {'ACCOUNT_EQUITY': '2000', 'RISK_PCT': '.5',
                        'MAX_POSITION_PCT': '25', 'MAX_OPEN_POSITIONS': '4',
                        'GITHUB_RUN_ID_FOR_RECORD': 'offline-producer-control'}.items():
        monkeypatch.setenv(name, value)


def test_actual_evening_produces_self_valid_outcomes_from_frozen_local_cohorts(
        market, claude, fake_resend, tmp_path, monkeypatch):
    from src import research_outcomes
    account(monkeypatch)
    rep, data, docs = evening(tmp_path, market)
    assert rep.exit_code() == 0
    canonical = (docs / 'data.json').read_bytes()
    receipt_raw = (docs / 'research-outcomes.json').read_bytes()
    receipt = research_outcomes.parse_receipt(receipt_raw)
    bundle_raw = (docs / receipt['bundle']['path']).read_bytes()
    bundle = research_outcomes.validate_bundle(receipt_raw, bundle_raw)
    assert receipt['publication']['data_sha256'] == hashlib.sha256(canonical).hexdigest()
    assert bundle['cohorts']
    for cohort in bundle['cohorts']:
        assert (docs / 'stop-research' / (cohort['source']['sha256'] + '.json')).read_bytes() == cohort['source']['raw'].encode()
    assert (docs / 'data.json').read_bytes() == canonical
    assert json.loads(canonical) == data


@pytest.fixture
def outcomes_publication(publication, market, claude, fake_resend, tmp_path, monkeypatch):
    """A real prior receipt beside a deliberately different current reader."""
    from src import research_outcomes
    account(monkeypatch)
    root, _ = publication
    rep, _, source = evening(tmp_path / 'prior-source', market)
    assert rep.exit_code() == 0
    raw = (source / 'research-outcomes.json').read_bytes()
    ref = research_outcomes.parse_receipt(raw)['bundle']['path']
    (root / 'docs/research-outcomes').mkdir()
    (root / 'docs/research-outcomes.json').write_bytes(raw)
    (root / 'docs' / ref).write_bytes((source / ref).read_bytes())
    return root, ref


def test_absent_optional_outcomes_do_not_block_evening(publication):
    root, _ = publication
    assert publisher.research_outcomes_files(root) == ()
    assert 'research-outcomes.json' not in publisher.public_files(root)


def test_only_current_snapshot_is_verified_and_old_binding_remains_deployable(outcomes_publication):
    root, ref = outcomes_publication
    docs = root / 'docs'
    (docs / 'research-outcomes' / ('0' * 64 + '.json')).write_bytes(b'older-snapshot-control')
    (docs / 'research-outcomes/index.json').write_bytes(b'append-only-index-control')
    before = {path: path.read_bytes() for path in docs.rglob('*') if path.is_file()}
    files = publisher.public_files(root)
    assert 'research-outcomes.json' in files
    assert [name for name in files if name.startswith('research-outcomes/')] == [ref]
    assert {path: path.read_bytes() for path in docs.rglob('*') if path.is_file()} == before


@pytest.mark.parametrize('fault', ['missing', 'changed', 'bundle_symlink', 'receipt_symlink',
                                 'directory_symlink', 'broken_receipt_symlink', 'oversize'])
def test_present_outcomes_assets_fail_closed(outcomes_publication, fault):
    root, ref = outcomes_publication
    receipt = root / 'docs/research-outcomes.json'
    bundle = root / 'docs' / ref
    if fault == 'missing':
        bundle.unlink()
    elif fault == 'changed':
        raw = bundle.read_bytes()
        altered = raw.replace(b'"schema_version":1', b'"schema_version":2', 1)
        assert len(altered) == len(raw) and altered != raw
        bundle.write_bytes(altered)
    elif fault == 'oversize':
        receipt.write_bytes(b' ' * (16 * 1024 + 1))
    elif fault == 'broken_receipt_symlink':
        receipt.unlink()
        receipt.symlink_to(root / 'missing')
    else:
        path = {'bundle_symlink': bundle, 'receipt_symlink': receipt,
                'directory_symlink': bundle.parent}[fault]
        elsewhere = root / 'elsewhere'
        path.rename(elsewhere)
        path.symlink_to(elsewhere, target_is_directory=elsewhere.is_dir())
    with pytest.raises(RuntimeError, match='Research outcomes companion'):
        publisher.public_files(root)


@pytest.mark.parametrize('path', ['../private.json', '/etc/passwd', 'https://example.invalid/private.json',
                                 'research-outcomes/' + 'a' * 64 + '.json?private=1'])
def test_outcomes_reference_is_validated_before_any_companion_read(outcomes_publication, monkeypatch, path):
    root, _ = outcomes_publication
    document = root / 'docs/research-outcomes.json'
    receipt = json.loads(document.read_bytes())
    receipt['bundle']['path'] = path
    document.write_text(json.dumps(receipt))
    read = []
    actual = publisher.reader_asset

    def recorded(docs, name, maximum):
        read.append(name)
        return actual(docs, name, maximum)

    monkeypatch.setattr(publisher, 'reader_asset', recorded)
    with pytest.raises(RuntimeError, match='Research outcomes companion'):
        publisher.research_outcomes_files(root)
    assert read == ['research-outcomes.json']


def test_outcomes_public_inventory_needs_only_standard_library(outcomes_publication):
    root, ref = outcomes_publication
    source = Path(__file__).resolve().parent.parent
    code = ('import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); '
            'from tools.publish_dashboard import public_files; print(public_files(Path(sys.argv[2])))')
    result = subprocess.run([sys.executable, '-I', '-S', '-c', code, str(source), str(root)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert 'research-outcomes.json' in result.stdout and ref in result.stdout


def test_public_byte_verification_fetches_receipt_and_exact_snapshot(outcomes_publication, monkeypatch):
    root, ref = outcomes_publication
    requested = []

    def api(repository, endpoint, method='GET'):
        if endpoint == 'pages':
            return {'build_type': 'legacy', 'source': {'branch': 'main', 'path': '/docs'},
                    'html_url': 'https://example.invalid/SpicyStock/'}
        assert (endpoint, method) == ('pages/builds', 'POST')
        return {'status': 'queued'}

    def fetch(url, timeout):
        name = urlsplit(url).path.removeprefix('/SpicyStock/')
        requested.append(name)
        return (root / 'docs' / name).read_bytes()

    monkeypatch.setattr(publisher, 'github_api', api)
    monkeypatch.setattr(publisher, 'public_bytes', fetch)
    publisher.publish('owner/repository', root)
    assert requested.count('research-outcomes.json') == requested.count(ref) == 1
