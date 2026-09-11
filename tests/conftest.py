"""Shared fixtures: offline boundaries, per-test seeds, isolated output.

Three rules this file enforces for every test in the suite:

1. No network. An autouse fixture severs socket connect(), so a test that
   reaches a real API fails loudly instead of quietly needing credentials.
2. No shared randomness. Synthetic frames are seeded from the requesting
   test's node id, so a frame never depends on how many tests ran before it.
3. No writes into the working tree. An autouse fixture puts every test in its
   own tmp_path, so the relative paths the pipeline writes (results/,
   charts/) land in a temporary directory.
"""

from __future__ import annotations

import socket
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.fakes import FakeAlpaca, FakeAnthropic, FakeDataClient, FakeResend  # noqa: E402
from tests.synthetic import make_ohlcv, seed_for  # noqa: E402


# ------------------------------------------------------------- isolation ----


@pytest.fixture(autouse=True)
def _isolated_cwd(monkeypatch, tmp_path):
    """Run every test inside its own tmp_path.

    render_chart() defaults to "charts", relative to the process working
    directory, and the pipeline writes docs/ wherever it is pointed. Without
    this the suite would litter the repo.
    """
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Fail any test that tries to open an outbound connection."""

    def _blocked(*args, **kwargs):
        raise RuntimeError(
            "network access is not allowed in the test suite -- "
            "mock the boundary instead (see tests/conftest.py)"
        )

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)


# ------------------------------------------------------- synthetic frames ----


@pytest.fixture
def seed(request) -> int:
    """A seed derived only from this test's node id."""
    return seed_for(request.node.nodeid)


@pytest.fixture
def ohlcv(seed):
    """Factory for deterministic OHLCV frames.

        df = ohlcv("burst")              # same frame every run, this test only
        other = ohlcv("burst", variant=1)  # a different frame, also stable

    Two tests never share a frame, and a frame never depends on how much
    randomness earlier tests consumed.
    """

    def _make(kind: str = "base", *, variant: int = 0, **kwargs):
        return make_ohlcv(kind, seed=[seed, variant], **kwargs)

    return _make


# ------------------------------------------------------------- boundaries ----


@pytest.fixture
def fake_alpaca(monkeypatch) -> FakeAlpaca:
    """Replace the Alpaca client in src.market_data with an in-memory double.

    Patched where it is looked up (the market_data module's namespace) rather
    than in alpaca-py, so this keeps working if the SDK import style changes.
    Register bars with fake_alpaca.add_history(ticker, frame).

    Throwaway credentials come with the double, the way fake_resend has always
    supplied its own. A double stands in for a client that cannot be built
    without a key, so "this boundary is available" and "its key is present"
    are one fact -- and since step 5 the pipeline refuses to start without it,
    so a test that mocks Alpaca and then fails preflight would be testing the
    fixture rather than the code.
    """
    import src.market_data as market_data

    monkeypatch.setenv("ALPACA_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "test-not-a-real-secret")
    parent = FakeAlpaca()
    monkeypatch.setattr(
        market_data, "StockHistoricalDataClient", lambda *a, **k: FakeDataClient(parent, *a, **k)
    )
    return parent


class _AnthropicControl:
    """Handle on the Anthropic double: inspect calls, choose the reply."""

    def __init__(self, cls: type[FakeAnthropic]) -> None:
        self._cls = cls

    @property
    def calls(self) -> list[dict]:
        return self._cls.calls

    def set_payload(self, payload: dict) -> None:
        self._cls.payload = payload

    def set_raw(self, text: str) -> None:
        """Reply with this exact text, e.g. JSON inside a markdown fence."""
        self._cls.raw = text

    def set_error(self, exc: Exception) -> None:
        self._cls.raises = exc


@pytest.fixture
def fake_anthropic(monkeypatch) -> _AnthropicControl:
    """Replace anthropic.Anthropic with a double that needs no API key.

    src.grader does `import anthropic; anthropic.Anthropic()` inside
    _client(), so the module attribute is the boundary. A fresh subclass per
    test keeps the recorded calls from leaking between tests.

    Supplies ANTHROPIC_API_KEY for the same reason fake_alpaca supplies
    Alpaca's: the real client raises without one, and the pipeline's preflight
    now refuses to start without one.
    """
    import anthropic

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-real-key")

    cls = type(
        "FakeAnthropicForTest",
        (FakeAnthropic,),
        {
            "calls": [],
            "payload": dict(FakeAnthropic.payload),
            "raw": None,
            "raises": None,
        },
    )
    monkeypatch.setattr(anthropic, "Anthropic", cls)
    return _AnthropicControl(cls)


@pytest.fixture
def fake_resend(monkeypatch) -> FakeResend:
    """Replace resend.Emails.send, and supply throwaway delivery env vars.

    send_email() reads EMAIL_TO and RESEND_API_KEY from the environment.
    monkeypatch.setenv keeps those inside the test, so the suite still runs
    with a completely empty environment.
    """
    import resend

    double = FakeResend()
    monkeypatch.setattr(resend.Emails, "send", lambda params, options=None: double.send(params))
    # send_email() assigns resend.api_key as a module global; restore it too.
    monkeypatch.setattr(resend, "api_key", None, raising=False)
    monkeypatch.setenv("RESEND_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("RESEND_FROM", "tests@example.invalid")
    monkeypatch.setenv("EMAIL_TO", "one@example.invalid,two@example.invalid")
    return double


@pytest.fixture
def mocked_boundaries(fake_alpaca, fake_anthropic, fake_resend):
    """All three external boundaries at once, for end-to-end tests."""
    return {"alpaca": fake_alpaca, "anthropic": fake_anthropic, "resend": fake_resend}
