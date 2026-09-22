"""Publication-time facts survive rotation; retention never decides a trade."""
import gzip
import hashlib
import json
import string

import pytest

from src import history, pipeline, report
from tools.make_fixture import run_variant


def entries(docs):
    return sorted((docs / 'quality-ledger' / 'v1').glob('*.json.gz'))


def test_publication_facts_survive_recovery_expiry_and_same_session_revision(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.time, 'monotonic', lambda: 100.0)
    docs = tmp_path / 'docs'
    run_variant('full', docs)
    original = (docs / 'data.json').read_bytes()
    publication = json.loads(original)
    files = entries(docs)
    assert len(files) == 1, 'publication discards longitudinal input/grade/outcome facts'
    first_bytes = files[0].read_bytes()
    saved = json.loads(gzip.decompress(first_bytes))
    assert saved['publication']['sha256'] == hashlib.sha256(original).hexdigest()
    assert saved['input']['coverage'] == publication['run']['coverage']
    assert saved['publication']['model'] == publication['run']['model']
    assert saved['signal']['candidates'][0]['checks']
    assert saved['signal']['candidates'][0]['assessment']['score'] == publication['bursts'][0]['quality']['score']
    assert saved['outcome']['summary'] == publication['scorecard']
    assert len(saved['outcome']['rows']) == publication['scorecard']['plans']
    assert {r['bucket'] for r in saved['outcome']['rows']} >= {'settled', 'pending', 'uncertain'}
    assert all('grade' in r for r in saved['outcome']['rows'])
    # Recovery's legitimate expiry must not expire the separate quality ledger.
    monkeypatch.setattr(history, 'DAYS', 0)
    run_variant('next', docs)
    run_variant('revised', docs)
    assert len(entries(docs)) == 3
    assert files[0].read_bytes() == first_bytes
    index = json.loads((docs / 'history' / 'index.json').read_bytes())
    assert '2026-09-10' not in index['dates']
    assert len({json.loads(gzip.decompress(p.read_bytes()))['publication']['sha256'] for p in entries(docs)}) == 3


def test_unaffected_actionable_publication_control(tmp_path):
    docs = tmp_path / 'docs'
    run_variant('full', docs)
    data = json.loads((docs / 'data.json').read_bytes())
    report.validate(data)
    assert 'AAPL' in data['trades']
    aapl = next(r for r in data['bursts'] if r['ticker'] == 'AAPL')
    assert aapl['grade'] == 'A+' and aapl['evidence']['gate']['ticket']
    assert any(p['ticker'] == 'AAPL' and p['date'] == data['run']['session']
               for p in json.loads((docs / 'picks.json').read_bytes())['picks'])


@pytest.mark.parametrize('failure', ['none', 'write', 'capacity'])
def test_retention_never_changes_complete_actionable_publication(failure, tmp_path, monkeypatch):
    from src import quality_ledger as ledger
    monkeypatch.setattr(pipeline.time, 'monotonic', lambda: 100.0)
    outputs = []
    for enabled in (False, True):
        docs = tmp_path / str(enabled)
        with monkeypatch.context() as m:
            if not enabled:
                m.setattr(ledger, 'capture', lambda **kw: {'status': 'disabled', 'path': None})
            elif failure == 'write':
                m.setattr(ledger.os, 'link', lambda *a: (_ for _ in ()).throw(OSError('disk unavailable')))
            elif failure == 'capacity':
                m.setattr(ledger, 'MAX_ENTRIES', 0)
            run_variant('full', docs)
        outputs.append({p.relative_to(docs).as_posix(): p.read_bytes()
                        for p in docs.rglob('*') if p.is_file() and 'quality-ledger' not in p.parts})
        assert bool(entries(docs)) == (enabled and failure == 'none')
    # Full data/picks/recovery/source bytes, not a comparison of a few grades.
    assert outputs[0] == outputs[1]


def test_complete_exception_membership_outlives_bounded_public_sample(
        mocked_boundaries, fake_alpaca, tmp_path):
    from tests.test_input_retention import flat, NOW
    stale = ['STA' + c for c in string.ascii_uppercase[:19]]
    healthy = ['OKA' + c for c in string.ascii_uppercase[:20]]
    for sym in stale + healthy + ['SPY']:
        fake_alpaca.add_history(sym, flat(), stale_sessions=int(sym in stale))
    rep = pipeline.run_evening(docs=tmp_path / 'docs', tickers=stale + healthy, now=NOW)
    assert rep.exit_code() == 2 and rep.quality_ledger['status'] == 'retained'
    saved = json.loads(gzip.decompress(entries(tmp_path / 'docs')[0].read_bytes()))
    assert len(saved['input']['coverage']['reasons']['stale']['sample']) == 8
    assert saved['input']['exception_membership']['stale'] == stale
    assert saved['input']['exception_membership']['no_bars'] == []
    assert saved['input']['coverage']['measured'] == 20
    assert len(fake_alpaca.bar_requests) == 1


def test_unknowns_and_unmeasured_checks_are_not_zero_or_fail():
    from src import quality_ledger as ledger
    d = {'run': {'session': '2026-09-10'}, 'bursts': [
        {'ticker': 'AAA', 'quality': {'checks': [{'letter': 'L', 'status': 'UNMEASURED',
                                                'a_plus': False, 'values': {'er': None}}]}}],
         'trades': []}
    saved = ledger.build(d, 'a' * 64, None)
    assert saved['input'] == {'universe': None, 'basis': None, 'coverage': None, 'exception_membership': None}
    assert saved['outcome'] == {'summary': None, 'rows': None}
    c = saved['signal']['candidates'][0]
    assert c['score'] is None and c['grade'] is None
    assert c['checks']['L'] == {'status': 'UNMEASURED', 'a_plus': False, 'values': {'er': None}}


def test_immutable_idempotent_bounded_writes_and_corruption(tmp_path, monkeypatch):
    from src import quality_ledger as ledger
    d = {'run': {'session': '2026-09-10'}, 'bursts': [], 'trades': []}
    entry = ledger.build(d, 'a' * 64, None)
    p = ledger.append(entry, tmp_path)
    raw = p.read_bytes()
    assert ledger.append(entry, tmp_path) == p
    assert p.read_bytes() == raw
    changed = ledger.build(d, 'a' * 64, [])
    with pytest.raises(ValueError, match='differs'):
        ledger.append(changed, tmp_path)
    assert p.read_bytes() == raw
    for field in ('MAX_ENTRY_BYTES', 'MAX_ARCHIVE_BYTES', 'MAX_ENTRIES'):
        with monkeypatch.context() as m:
            m.setattr(ledger, field, 0)
            with pytest.raises(ValueError, match='capacity'):
                ledger.append(ledger.build(d, 'b' * 64, []), tmp_path)
        assert p.read_bytes() == raw and len(entries(tmp_path)) == 1
    p.write_bytes(b'corrupt original')
    with pytest.raises(ValueError, match='differs'):
        ledger.append(entry, tmp_path)
    assert p.read_bytes() == b'corrupt original'
    with pytest.raises(ValueError, match='schema'):
        ledger.append({**entry, 'schema_version': 2}, tmp_path)


@pytest.mark.parametrize('outcome', ['email_failure', 'capture_failure', 'publish_failure', 'dry_run'])
def test_terminal_status_and_external_calls_unchanged(
        outcome, mocked_boundaries, fake_alpaca, fake_anthropic, fake_resend, tmp_path, monkeypatch, caplog):
    from src import quality_ledger as ledger, provenance
    from tests.test_input_retention import flat, NOW
    monkeypatch.setattr(pipeline.time, 'monotonic', lambda: 100.0)
    for sym in ['AAA', 'SPY']:
        fake_alpaca.add_history(sym, flat())
    def fail(*a, **k):
        raise OSError('fixture failure')
    if outcome == 'email_failure':
        monkeypatch.setattr(report, 'send_digest', fail)
    if outcome == 'publish_failure':
        monkeypatch.setattr(provenance, 'publish_bundle', fail)
    results = []
    for enabled in (False, True):
        fake_alpaca.bar_requests.clear()
        fake_anthropic.calls.clear()
        fake_resend.sent.clear()
        docs = tmp_path / str(enabled)
        with monkeypatch.context() as m:
            if not enabled:
                m.setattr(ledger, 'capture', lambda **kw: {'status': 'disabled', 'path': None})
            elif outcome == 'capture_failure':
                m.setattr(ledger, 'append', fail)
            rep = pipeline.run_evening(docs=docs, tickers=['AAA'], now=NOW, dry_run=outcome == 'dry_run')
        results.append((rep.exit_code(), rep.status, rep.problems, rep.input_coverage,
                        len(fake_alpaca.bar_requests), len(fake_anthropic.calls), len(fake_resend.sent),
                        {p.name: p.read_bytes() for p in docs.glob('*.json')}))
        if enabled:
            expected = {'email_failure': 'retained', 'capture_failure': 'failed',
                        'publish_failure': 'not_attempted', 'dry_run': 'not_applicable'}[outcome]
            assert rep.quality_ledger['status'] == expected
            with monkeypatch.context() as m:
                output = tmp_path / 'outputs'
                m.setenv('GITHUB_OUTPUT', str(output))
                m.setattr(pipeline, 'run_evening', lambda **kw: rep)
                assert pipeline.main(['evening']) == rep.exit_code()
                lines = output.read_text().splitlines()
                assert (f'quality_ledger_status={expected}' in lines) == (expected != 'not_attempted')
            if outcome == 'email_failure':
                saved = json.loads(gzip.decompress(entries(docs)[0].read_bytes()))
                assert saved['publication']['email'] == 'failed'
                assert saved['publication']['status'] == 'degraded'
            if outcome == 'capture_failure':
                assert 'quality_ledger_capture_failed' in caplog.text
    assert results[0] == results[1]
