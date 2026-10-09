"""Committed-main publication verifies the compact reader's actual bytes."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

import pytest

from src import reader
from tools import publish_dashboard as publisher


def write_reader_records(docs: Path) -> str:
    """A small complete transport control, unrelated to any live recommendation."""
    data = {'schema_version': 2, 'run': {'session': '2026-10-08'},
            'bursts': [{'ticker': 'PUBLIC', 'plan': {'limit': 12.3}}],
            'observations': {'as_of': '2026-10-08', 'days': 3, 'history_max': 30,
                             'symbols': {'PUBLIC': {'close': 12.1}}, 'signals': {}}}
    canonical = json.dumps(data, indent=1).encode() + b'\n'
    projected, observations = reader.derive(canonical)
    descriptor = json.loads(projected)['retained_observations']
    (docs / 'data.json').write_bytes(canonical)
    (docs / 'reader.json').write_bytes(projected)
    (docs / 'reader-observations').mkdir(exist_ok=True)
    (docs / descriptor['path']).write_bytes(observations)
    for name in ('picks.json', 'historical-validation.json', 'historical-findings.json'):
        (docs / name).write_bytes(b'{}')
    return descriptor['path']


@pytest.fixture
def publication(tmp_path):
    docs = tmp_path / 'docs'
    docs.mkdir()
    (docs / 'index.html').write_text('<script src="app.js"></script>')
    (docs / 'app.js').write_text('// static asset')
    return tmp_path, write_reader_records(docs)


def test_verified_reader_and_only_current_sidecar_are_required(publication):
    root, sidecar = publication
    (root / 'docs/reader-observations' / ('0' * 64 + '.json')).write_text('older retained object')
    files = publisher.public_files(root)
    assert 'reader.json' in files and sidecar in files
    assert [name for name in files if name.startswith('reader-observations/')] == [sidecar]
    assert 'data.json' in files and 'app.js' in files


@pytest.mark.parametrize('missing', ['reader.json', 'sidecar'])
def test_missing_companion_cannot_pass_publication(publication, missing):
    root, sidecar = publication
    (root / 'docs' / (sidecar if missing == 'sidecar' else missing)).unlink()
    with pytest.raises(RuntimeError):
        publisher.public_files(root)


@pytest.mark.parametrize('changed', ['canonical', 'candidate', 'sidecar', 'declared_bytes'])
def test_reader_source_candidate_and_deferred_bytes_must_match(publication, changed):
    root, sidecar = publication
    docs = root / 'docs'
    if changed == 'canonical':
        with (docs / 'data.json').open('ab') as handle:
            handle.write(b' ')
    elif changed == 'sidecar':
        with (docs / sidecar).open('ab') as handle:
            handle.write(b' ')
    else:
        envelope = json.loads((docs / 'reader.json').read_bytes())
        if changed == 'candidate':
            envelope['data']['bursts'][0]['plan']['limit'] = 99.0
        else:
            envelope['retained_observations']['bytes'] -= 1
        (docs / 'reader.json').write_text(json.dumps(envelope, separators=(',', ':')))
    with pytest.raises(RuntimeError, match='Reader companions'):
        publisher.public_files(root)


@pytest.mark.parametrize('path', ['../private.json', '/etc/passwd', 'https://example.invalid/private.json',
                                 '//example.invalid/remote.json', 'reader-observations/OTHER.json',
                                 'reader-observations/' + '0' * 64 + '.json?private=1'])
def test_reference_is_rejected_before_any_untrusted_file_read(publication, monkeypatch, path):
    root, sidecar = publication
    document = root / 'docs/reader.json'
    envelope = json.loads(document.read_bytes())
    envelope['retained_observations']['path'] = path
    document.write_text(json.dumps(envelope))
    actual = publisher.reader_asset
    read_names = []

    def recording(docs, name, maximum):
        read_names.append(name)
        return actual(docs, name, maximum)

    monkeypatch.setattr(publisher, 'reader_asset', recording)
    with pytest.raises(RuntimeError, match='Reader companions'):
        publisher.public_files(root)
    assert read_names == ['data.json', 'reader.json']


@pytest.mark.parametrize('target', ['data.json', 'reader.json', 'sidecar', 'archive', 'docs'])
def test_reader_file_and_directory_symlinks_are_refused(publication, target):
    root, sidecar = publication
    relative = {'sidecar': 'docs/' + sidecar, 'archive': 'docs/reader-observations',
                'docs': 'docs'}.get(target, 'docs/' + target)
    path = root / relative
    retained = root / 'outside'
    path.rename(retained)
    path.symlink_to(retained, target_is_directory=retained.is_dir())
    with pytest.raises(RuntimeError):
        publisher.public_files(root)


def test_reader_file_reads_have_explicit_bounds(publication):
    root, _ = publication
    with pytest.raises(ValueError, match='bytes exceed bound'):
        publisher.reader_asset(root / 'docs', 'reader.json', 1)


def test_invalid_bundle_makes_no_github_or_public_request(publication, monkeypatch):
    root, sidecar = publication
    (root / 'docs' / sidecar).write_bytes(b'{}')

    def forbidden(*args, **kwargs):
        raise AssertionError('Network must not start before local bundle validation')

    monkeypatch.setattr(publisher, 'github_api', forbidden)
    monkeypatch.setattr(publisher, 'public_bytes', forbidden)
    with pytest.raises(RuntimeError, match='Reader companions'):
        publisher.publish('owner/repository', root)


def test_page_byte_verification_fetches_reader_and_exact_sidecar(publication, monkeypatch):
    root, sidecar = publication
    requests = []

    def api(repository, endpoint, method='GET'):
        if endpoint == 'pages':
            return {'build_type': 'legacy', 'source': {'branch': 'main', 'path': '/docs'},
                    'html_url': 'https://example.invalid/SpicyStock/'}
        assert (endpoint, method) == ('pages/builds', 'POST')
        return {'status': 'queued'}

    def fetch(url, timeout):
        name = urlsplit(url).path.removeprefix('/SpicyStock/')
        requests.append(name)
        return (root / 'docs' / name).read_bytes()

    monkeypatch.setattr(publisher, 'github_api', api)
    monkeypatch.setattr(publisher, 'public_bytes', fetch)
    publisher.publish('owner/repository', root)
    assert requests.count('reader.json') == requests.count(sidecar) == 1


def test_direct_script_import_keeps_standard_library_only(tmp_path):
    tool = Path(__file__).resolve().parent.parent / 'tools/publish_dashboard.py'
    code = 'import runpy; runpy.run_path(' + repr(str(tool)) + ', run_name="import_only")'
    result = subprocess.run([sys.executable, '-I', '-S', '-c', code], cwd=tmp_path,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
