"""Offline request compatibility; never claims a measured API success rate."""
import inspect
import gzip
import json
from pathlib import Path
import pytest
from src import grader, reader_authority


@pytest.mark.parametrize('model', ['claude-sonnet-4-6', 'claude-sonnet-4-5', 'claude-opus-4-6'])
def test_documented_direct_api_models_send_the_authoritative_schema(model):
    request = grader.request_kwargs('frozen rulebook', [{'type': 'text', 'text': 'frozen evidence'}], model)
    assert request['output_config']['format'] == {'type': 'json_schema', 'schema': grader.SCORE_SCHEMA}
    assert request['max_tokens'] == 4096
    assert request['extra_body'] == {'temperature': 0}
    assert grader.ATTEMPTS == 2
    assert grader.GRADING_IO_TIMEOUT_SECONDS == 30


def test_sdk_payload_uses_direct_endpoint_without_network(monkeypatch):
    import anthropic
    client = anthropic.Anthropic(api_key='offline-test-only')
    request = grader.request_kwargs('sys', [{'type': 'text', 'text': 't'}], 'claude-sonnet-4-6')
    inspect.signature(client.messages.create).bind(**request)
    calls = []
    monkeypatch.setattr(client.messages, 'create', lambda **kwargs: calls.append(kwargs))
    client.messages.create(**request)
    assert calls[0]['output_config']['format']['schema'] is grader.SCORE_SCHEMA


@pytest.mark.parametrize('model', ['claude-opus-4-1', 'claude-unknown-9'])
def test_unverified_structured_output_combinations_do_not_get_schema(model):
    assert 'output_config' not in grader.request_kwargs('sys', [], model)


def test_schema_valid_negative_reply_still_needs_correct_authority():
    metrics = {'quality_grade': 'A', 'reader_evidence': {'version': 1, 'checks': {
        'Y': {'status': 'PASS', 'values': {'gain_since_move_start_pct': 35.3}}}}}
    reply = {'grade': 'B', 'score': 7, 'reason': 'unsupported supply citation', 'findings': [{
        'criterion': 'overhead_supply', 'source': 'strategy.chart.supply',
        'observation': 'prior_trading_above_signal',
        'evidence': [{'path': 'checks.Y.values.gain_since_move_start_pct', 'value': 35.3}]}]}
    with pytest.raises(reader_authority.ReaderAuthorityError, match='outside criterion'):
        reader_authority.validate(reply, metrics, chart_seen=True)


@pytest.mark.parametrize('ticker,accepted', [('NIC',False),('BIO',False),('RVTY',False),('CRL',True),('IQV',True),('MSFT',False)])
def test_original_retained_authority_decisions_are_not_repaired(ticker,accepted):
    root=Path(__file__).resolve().parents[1]
    if ticker=='MSFT':
        study=json.loads((root/'docs/historical-validation.json').read_bytes())
        case=next(c for c in study['cases'] if c['ticker']==ticker)
        b=json.loads((root/'docs/history'/case['entry']['path']).read_bytes())['row']
    else:
        data=json.loads(gzip.decompress((root/'tests/fixtures/chart-keyboard/2026-09-24.json.gz').read_bytes()))
        b=next(b for b in data['bursts'] if b['ticker']==ticker)
    raw=b['claude']['attempts'][-1]['response']['text']
    reply=grader._validated(grader._extract_json(raw))
    metrics={'quality_grade':b['grade_mechanical'],'reader_evidence':{'version':1,'checks':{
        c['letter']:{'status':c['status'],'values':c['values']} for c in b['quality']['checks']}}}
    if accepted:
        reader_authority.validate(reply,metrics,chart_seen=True)
    else:
        with pytest.raises(reader_authority.ReaderAuthorityError):
            reader_authority.validate(reply,metrics,chart_seen=True)
