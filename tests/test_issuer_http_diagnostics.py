"""HTTP refusal diagnostics retain bounded facts without reading error bodies."""
from copy import deepcopy
import json
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest

from src import issuer_evidence as issuer
from tests.test_issuer_evidence import Clock, Response, packet, producer, repack, wire_transport


class UnreadBody:
    def __init__(self):
        self.closed = False
    def read(self, *args):
        pytest.fail('an HTTP error body was read')
    def close(self):
        self.closed = True


@pytest.mark.parametrize('status', [300, 301, 302, 307, 308, 400, 401, 403, 404, 408, 429, 500, 503, 599])
def test_real_http_error_retains_only_status_and_counts_one_attempt(monkeypatch, status):
    transport, budget = wire_transport(monkeypatch, Response(b'', Clock()))
    body = UnreadBody()
    calls = []
    def denied(request, timeout):
        calls.append((request.full_url, request.get_header('User-agent'), timeout))
        raise HTTPError('https://untrusted.invalid/response-supplied', status,
                        'private diagnostic text', {'Set-Cookie': 'private header'}, body)
    transport.opener.open = denied
    with pytest.raises(issuer.SourceError) as failed:
        transport.fetch(issuer.MAPPING_URL, budget)
    code = 'redirect_refused' if status < 400 else 'rate_limit' if status == 429 else 'http_error'
    assert (failed.value.code, failed.value.http_status, str(failed.value)) == (code, status, code)
    assert calls == [(issuer.MAPPING_URL, issuer.USER_AGENT, 10)]
    assert body.closed and budget.requests == 1 and budget.bytes == 0


@pytest.mark.parametrize('status', [True, False, '403', 403.0, None, 0, 299, 600])
def test_malformed_http_error_never_fabricates_a_status(monkeypatch, status):
    transport, budget = wire_transport(monkeypatch, Response(b'', Clock()))
    body = UnreadBody()
    def denied(request, timeout):
        raise HTTPError(issuer.MAPPING_URL, status, 'private diagnostic', {}, body)
    transport.opener.open = denied
    with pytest.raises(issuer.SourceError) as failed:
        transport.fetch(issuer.MAPPING_URL, budget)
    assert failed.value.code == 'invalid_response' and failed.value.http_status is None
    assert budget.requests == 1 and budget.bytes == 0 and body.closed


@pytest.mark.parametrize('problem,code', [(TimeoutError(), 'timeout'), (URLError('private transport text'), 'network_error')])
def test_no_http_response_keeps_status_unknown(monkeypatch, problem, code):
    transport, budget = wire_transport(monkeypatch, Response(b'', Clock()))
    def failed(request, timeout):
        raise problem
    transport.opener.open = failed
    with pytest.raises(issuer.SourceError) as failure:
        transport.fetch(issuer.MAPPING_URL, budget)
    assert failure.value.code == code and failure.value.http_status is None


def test_redirect_handler_keeps_original_status_without_following_destination():
    with pytest.raises(issuer.SourceError) as failure:
        issuer._NoRedirect().redirect_request(None, None, 302, 'private message',
                                              {'Location': 'private header'}, 'https://untrusted.invalid/private')
    assert failure.value.code == 'redirect_refused' and failure.value.http_status == 302
    assert str(failure.value) == 'redirect_refused'


def test_collector_serializes_actual_http_error_with_fixed_mapping_phase(packet, producer, monkeypatch):
    canonical, _ = packet
    original = issuer._Transport.__init__
    requests, bodies = [], []
    def init(self, *args, **kwargs):
        original(self, *args, **kwargs)
        def denied(request, timeout):
            requests.append(request.full_url)
            body = UnreadBody(); bodies.append(body)
            raise HTTPError('https://untrusted.invalid/response-supplied', 403,
                            'private diagnostic text', {'Set-Cookie': 'private header'}, body)
        self.opener = SimpleNamespace(open=denied)
    monkeypatch.setattr(issuer._Transport, '__init__', init)
    result = issuer.collect(canonical, now=producer.NOW, run_id='offline-http-control', allow_fixture=True)
    assert result['receipt']['status'] == 'unavailable'
    expected = {'code': 'http_error', 'source_url': issuer.MAPPING_URL,
                'http_status': 403, 'source_phase': 'mapping'}
    assert all(row['errors'] == [expected] for row in result['bundle']['issuers'])
    assert requests == [issuer.MAPPING_URL] and all(body.closed for body in bodies)
    assert result['bundle']['stats'] == {'request_count': 1, 'downloaded_bytes': 0, 'capture_bytes': 0, 'budget_stop': None}
    assert result['captures'] == {} and result['receipt']['coverage'] == issuer.COVERAGE
    assert b'private' not in result['bundle_bytes'] and b'untrusted.invalid' not in result['bundle_bytes']
    issuer.validate_for_publication(canonical, result['receipt_bytes'], result['bundle_bytes'], allow_fixture=True)


def phase_result(producer, raw, phase):
    index = producer.aapl_submissions()
    recent = index['filings']['recent']
    prefix = 'https://www.sec.gov/Archives/edgar/data/320193/' + recent['accessionNumber'][0].replace('-', '') + '/'
    urls = {'mapping': issuer.MAPPING_URL, 'submissions': producer.AAPL_SUBMISSIONS,
            'history': 'https://data.sec.gov/submissions/CIK0000320193-submissions-001.json',
            'primary': prefix + recent['primaryDocument'][0], 'exhibit': prefix + 'synthetic-ex99.htm'}
    edits = {}
    if phase == 'history':
        index['filings']['recent'] = {key: values[:4] for key, values in recent.items()}
        index['filings']['files'] = [{'name': 'CIK0000320193-submissions-001.json', 'filingCount': 1,
                                     'filingFrom': '2025-10-01', 'filingTo': '2026-10-08'}]
        edits[producer.AAPL_SUBMISSIONS] = producer.json_bytes(index)
    edits[urls[phase]] = issuer.SourceError('http_error', http_status=503)
    result = producer.collect(raw, fetch=producer.transport(edits=edits))
    return result, urls[phase]


@pytest.mark.parametrize('phase', ['mapping', 'submissions', 'history', 'primary', 'exhibit'])
def test_diagnostic_phase_comes_from_current_collector_stage(packet, producer, phase):
    canonical, _ = packet
    result, url = phase_result(producer, canonical, phase)
    row = next(row for row in result['bundle']['issuers'] if row['ticker'] == 'AAPL')
    assert {'code': 'http_error', 'source_url': url, 'http_status': 503, 'source_phase': phase} in row['errors']
    assert result['receipt']['coverage'] == issuer.COVERAGE
    issuer.validate_for_publication(canonical, result['receipt_bytes'], result['bundle_bytes'], allow_fixture=True)


@pytest.mark.parametrize('change', [
    {'http_status': True}, {'http_status': False}, {'http_status': '403'}, {'http_status': 403.0},
    {'http_status': None}, {'http_status': 299}, {'http_status': 600}, {'http_status': 429},
    {'http_status': 302}, {'code': 'timeout'}, {'source_phase': 'unknown'}, {'source_phase': 'primary'},
    {'source_url': None}, {'source_url': 'https://www.sec.gov/files/company_tickers_exchange.json?private=yes'},
    {'source_url': 'https://data.sec.gov/submissions/CIK0000320193.json'},
    {'body': 'private diagnostic'}, {'headers': {}}, {'message': 'private diagnostic'},
])
def test_repacked_diagnostic_shape_cannot_bypass_strict_validation(packet, producer, change):
    result = producer.collect(packet[0], 'http-denied')
    def edit(receipt, bundle):
        bundle['issuers'][0]['errors'][0].update(change)
    receipt, bundle = repack(result, edit)
    with pytest.raises((ValueError, TypeError, KeyError)):
        issuer.validate_bundle(receipt, bundle)


@pytest.mark.parametrize('removed', ['http_status', 'source_phase'])
def test_new_diagnostics_require_both_fields(packet, producer, removed):
    result = producer.collect(packet[0], 'http-denied')
    receipt, bundle = repack(result, lambda r, b: b['issuers'][0]['errors'][0].pop(removed))
    with pytest.raises(ValueError, match='diagnostic pair'):
        issuer.validate_bundle(receipt, bundle)


@pytest.mark.parametrize('phase', ['submissions', 'history', 'primary', 'exhibit'])
def test_current_issuer_and_selected_filing_bind_diagnostic_url(packet, producer, phase):
    result, url = phase_result(producer, packet[0], phase)
    def wrong_issuer(receipt, bundle):
        row = next(row for row in bundle['issuers'] if row['ticker'] == 'AAPL')
        error = next(error for error in row['errors'] if error.get('source_phase') == phase)
        error['source_url'] = url.replace('0000320193', '0001045810') if phase in ('submissions', 'history') else url.replace('/320193/', '/1045810/')
    receipt, bundle = repack(result, wrong_issuer)
    with pytest.raises(ValueError, match='phase and requested URL'):
        issuer.validate_bundle(receipt, bundle)


@pytest.mark.parametrize('phase,replacement', [('primary', 'other.htm'), ('exhibit', 'synthetic-9001.htm'), ('exhibit', 'private.json')])
def test_document_phase_refuses_mislabelled_or_unselected_paths(packet, producer, phase, replacement):
    result, url = phase_result(producer, packet[0], phase)
    def alter(receipt, bundle):
        row = next(row for row in bundle['issuers'] if row['ticker'] == 'AAPL')
        error = next(error for error in row['errors'] if error.get('source_phase') == phase)
        error['source_url'] = url.rsplit('/', 1)[0] + '/' + replacement
    receipt, bundle = repack(result, alter)
    with pytest.raises(ValueError, match='phase and requested URL'):
        issuer.validate_bundle(receipt, bundle)


def test_legacy_errors_remain_exact_and_optional_status_is_not_fabricated(packet, producer):
    for variant in ('outage', 'metadata-only', 'identity-unverified'):
        result = producer.collect(packet[0], variant)
        errors = [error for row in result['bundle']['issuers'] for error in row['errors']]
        assert errors and all(set(error) == {'code', 'source_url'} for error in errors)
        before = deepcopy(result)
        issuer.validate_bundle(result['receipt_bytes'], result['bundle_bytes'])
        assert result == before
