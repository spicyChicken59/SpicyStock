"""Real Alpaca SDK requests carry timeouts, through pagination and retries.

Only HTTPAdapter.send is replaced. Everything above that network boundary is
the actual SDK and Requests session; no socket or real credentials are used.
"""

import json
from datetime import date
from urllib.parse import parse_qs, urlsplit

import pytest
import requests

from src import pipeline, scanner
from tests.test_sdk_contract import _raw_bars


@pytest.fixture
def credentials(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "test-not-a-real-secret")


def _response(request, payload, status=200):
    response = requests.Response()
    response.status_code = status
    response.request = request
    response.url = request.url
    response._content = json.dumps(payload).encode()
    response.headers["Content-Type"] = "application/json"
    return response


def test_real_sdk_bounds_every_page_and_preserves_the_request(credentials, monkeypatch, ohlcv):
    calls = []
    session = date(2026, 9, 8)
    bars = _raw_bars(ohlcv("burst"), session)

    def send(adapter, request, **kwargs):
        calls.append((request, kwargs))
        payload = ({"bars": {"BURST": bars[:-1]}, "next_page_token": "page-two"}
                   if len(calls) == 1 else {"bars": {"BURST": bars[-1:]}})
        return _response(request, payload)

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    frames = scanner._download_batch(scanner.get_clients(), ["BURST"],
                                     scanner.ScanConfig(), session)

    assert len(calls) == 2 and len(frames["BURST"]) == len(bars)
    assert all(options["timeout"] == (5, 30) for _, options in calls)
    first, second = [parse_qs(urlsplit(request.url).query) for request, _ in calls]
    assert first["adjustment"] == ["split"] and first["feed"] == ["sip"]
    assert first["timeframe"] == ["1Day"] and first["symbols"] == ["BURST"]
    assert "page_token" not in first and second["page_token"] == ["page-two"]
    assert all(request.headers["APCA-API-KEY-ID"] == "test-not-a-real-key"
               for request, _ in calls)


def test_timeout_is_client_scoped_and_explicit_overrides_are_preserved(credentials, monkeypatch):
    seen = []

    def send(adapter, request, **kwargs):
        seen.append(kwargs["timeout"])
        return _response(request, {})

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    client = scanner.get_clients()
    client._session.get("https://example.test/data")
    client._session.get("http://example.test/data", timeout=(2, 4))
    client._session.get("http://example.test/data", timeout=None)
    with requests.Session() as unrelated:
        unrelated.get("https://example.test/unrelated")

    assert seen == [(5, 30), (2, 4), (5, 30), None]


def test_a_timeout_uses_the_scanners_existing_single_batch_retry(credentials, monkeypatch, ohlcv):
    calls, sleeps = [], []
    session = date(2026, 9, 8)
    bars = _raw_bars(ohlcv("burst"), session)

    def send(adapter, request, **kwargs):
        calls.append(kwargs["timeout"])
        if len(calls) == 1:
            raise requests.ReadTimeout("synthetic stalled market-data response")
        return _response(request, {"bars": {"BURST": bars}})

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    monkeypatch.setattr(scanner.time, "sleep", sleeps.append)
    stats = {}
    found = scanner.run_scan(scanner.ScanConfig(session_date=session),
                             universe=["BURST"], stats=stats)

    assert [row.ticker for row in found] == ["BURST"]
    assert calls == [(5, 30), (5, 30)] and sleeps == [3]
    assert stats["dropped"] == 0


def test_repeated_timeouts_fail_coverage_after_two_attempts(credentials, monkeypatch):
    calls = []

    def send(adapter, request, **kwargs):
        calls.append(kwargs["timeout"])
        raise requests.ConnectTimeout("synthetic stalled connection")

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    monkeypatch.setattr(scanner.time, "sleep", lambda seconds: None)
    stats = {}
    with pytest.raises(scanner.IncompleteScanError, match="failed twice"):
        scanner.run_scan(scanner.ScanConfig(session_date=date(2026, 9, 8)),
                         universe=[f"Q{letter}" for letter in "ABCDEFGHIJ"], stats=stats)

    assert calls == [(5, 30), (5, 30)]
    assert stats["dropped"] == 10


def test_sdk_rate_limit_retry_keeps_its_own_policy_and_timeout(credentials, monkeypatch):
    calls, sleeps = [], []

    def send(adapter, request, **kwargs):
        calls.append(kwargs["timeout"])
        if len(calls) == 1:
            return _response(request, {"message": "synthetic rate limit"}, status=429)
        return _response(request, {"bars": {}})

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    monkeypatch.setattr(scanner.time, "sleep", sleeps.append)
    client = scanner.get_clients()
    frames = scanner._download_batch(client, ["BURST"], scanner.ScanConfig(), date(2026, 9, 8))

    assert frames == {}
    assert calls == [(5, 30), (5, 30)]
    assert sleeps == [client._retry_wait]


def test_forward_return_fetches_use_the_same_bounded_transport(credentials, monkeypatch):
    calls = []

    def send(adapter, request, **kwargs):
        calls.append(kwargs["timeout"])
        return _response(request, {"bars": {}})

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    assert pipeline.forward_bars(scanner.ScanConfig(), ["BURST"], date(2026, 9, 8)) == {}
    assert calls == [(5, 30)]
