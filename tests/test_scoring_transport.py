"""Real SDK transport limits, with no network or paid requests."""

import anthropic
import httpx2 as httpx

from src import scorer
from tests.test_scorer import CONTEXT, candidate, make_lynch


def test_the_actual_client_has_explicit_timeouts_and_no_hidden_retries(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "offline-transport-test")
    client = scorer._client()
    try:
        assert client.timeout.connect == 5.0
        assert client.timeout.read == 30.0
        assert client.timeout.write == 30.0
        assert client.timeout.pool == 30.0
        assert client.max_retries == 0
    finally:
        client.close()


def test_real_sdk_timeouts_make_only_two_attempts_then_return_a_marked_fallback(
    monkeypatch, candidate
):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "offline-transport-test")
    real_client = anthropic.Anthropic
    clients, requests = [], []

    def timeout(request):
        requests.append(request)
        raise httpx.ReadTimeout("offline simulated read timeout", request=request)

    def client_with_local_transport(**kwargs):
        client = real_client(
            http_client=httpx.Client(transport=httpx.MockTransport(timeout)), **kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr(anthropic, "Anthropic", client_with_local_transport)
    try:
        row = scorer.score_candidate(candidate, make_lynch(), CONTEXT, None)
    finally:
        for client in clients:
            client.close()

    assert len(requests) == 2, "only the application's one retry may repeat a request"
    assert all(request.extensions["timeout"] == {
        "connect": 5.0, "read": 30.0, "write": 30.0, "pool": 30.0,
    } for request in requests)
    assert row["provenance"]["source"] == "fallback"
    assert "timeout" in row["provenance"]["error"].lower()
    assert row["verdict"] == "unscored"
