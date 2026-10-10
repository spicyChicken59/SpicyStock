"""The optional research hook consumes final publication bytes and owns no plans."""
import json

import pytest

from src import pipeline
from tests.test_pipeline import claude, evening, market  # shared real-pipeline doubles


@pytest.mark.parametrize('delivery', ['delivered', 'skipped', 'failed', 'dry_run'])
def test_research_uses_final_bytes_after_every_delivery_outcome(
        market, claude, fake_resend, tmp_path, monkeypatch, delivery):
    from src import stop_research
    calls = []

    def capture(raw, docs, *, objects, picks=None, allow_fixture=False):
        calls.append((raw, docs, objects, json.loads(json.dumps(picks)), allow_fixture))
        return {}

    monkeypatch.setattr(stop_research, 'write_publication', capture)
    if delivery == 'failed':
        fake_resend.raises = RuntimeError('offline delivery refusal')
    elif delivery == 'skipped':
        monkeypatch.setenv('SCAN_SEND_EMAIL', 'false')
    rep, data, docs = evening(tmp_path, market, dry_run=delivery == 'dry_run')
    assert len(calls) == 1
    raw, output, objects, picks, allow_fixture = calls[0]
    assert raw == (docs / 'data.json').read_bytes()
    assert output == docs and objects == docs / 'evidence' and objects.is_dir()
    assert allow_fixture is False
    assert data['run']['email'] == ('skipped' if delivery == 'dry_run' else delivery)
    assert rep.exit_code() == (pipeline.EXIT_FAILED_AFTER_PUBLISH if delivery == 'failed' else 0)
    if delivery == 'dry_run':
        assert not (docs / 'picks.json').exists()
    else:
        assert picks == json.loads((docs / 'picks.json').read_bytes())


def test_optional_research_failure_preserves_evening_record_and_existing_cohorts(
        market, claude, fake_resend, tmp_path, monkeypatch, caplog):
    from src import stop_research
    docs = tmp_path / 'docs'
    cohort = docs / 'stop-research' / ('f' * 64 + '.json')
    cohort.parent.mkdir(parents=True)
    cohort.write_bytes(b'owned-cohort-transport-control')
    latest = docs / 'stop-research.json'
    latest.write_bytes(b'older-receipt-transport-control')
    captured = []

    def refuse(raw, *args, **kwargs):
        captured.append(raw)
        raise ValueError('private diagnostic must not enter the publication or logs')

    monkeypatch.setattr(stop_research, 'write_publication', refuse)
    rep, data, _ = evening(tmp_path, market)
    assert rep.exit_code() == 0 and data['run']['status'] == 'ok'
    assert data['run']['email'] == 'delivered' and data['run']['problems'] == []
    assert captured == [(docs / 'data.json').read_bytes()]
    assert (docs / 'picks.json').is_file() and (docs / 'history/index.json').is_file()
    assert cohort.read_bytes() == b'owned-cohort-transport-control'
    assert latest.read_bytes() == b'older-receipt-transport-control'
    assert 'Stop research publication unavailable (ValueError)' in caplog.text
    assert 'private diagnostic' not in caplog.text


def test_actual_evening_emits_self_valid_research_without_rewriting_canonical(
        market, claude, fake_resend, tmp_path, monkeypatch):
    from src import stop_research
    for name, value in {'ACCOUNT_EQUITY': '2000', 'RISK_PCT': '.5',
                        'MAX_POSITION_PCT': '25', 'MAX_OPEN_POSITIONS': '4',
                        'GITHUB_RUN_ID_FOR_RECORD': 'offline-producer-control'}.items():
        monkeypatch.setenv(name, value)
    rep, data, docs = evening(tmp_path, market)
    assert rep.exit_code() == 0
    canonical = (docs / 'data.json').read_bytes()
    receipt_raw = (docs / 'stop-research.json').read_bytes()
    receipt = stop_research.parse_receipt(receipt_raw)
    bundle_raw = (docs / receipt['bundle']['path']).read_bytes()
    stop_research.validate_bundle(receipt_raw, bundle_raw)
    stop_research.validate_for_publication(canonical, receipt_raw, bundle_raw,
                                           objects=docs / 'evidence')
    assert (docs / 'data.json').read_bytes() == canonical
    assert json.loads(canonical) == data
