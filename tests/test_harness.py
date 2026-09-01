"""The harness's own guarantees: no network, no keys, no writes to the repo.

Every other test in this suite is only trustworthy if these hold, so they are
asserted rather than assumed.
"""

from __future__ import annotations

import os
import socket
from pathlib import Path

import pytest


def test_outbound_connections_are_blocked():
    """A test that reaches a real API must fail here, not silently pass on a
    machine that happens to have credentials."""
    with pytest.raises(RuntimeError, match="network access is not allowed"):
        socket.create_connection(("example.com", 443))
    with pytest.raises(RuntimeError, match="network access is not allowed"):
        socket.socket().connect(("example.com", 443))


def test_each_test_runs_in_its_own_temporary_directory(tmp_path):
    assert Path.cwd() == tmp_path
    assert not any(tmp_path.iterdir()), "each test starts with an empty directory"


def test_writes_land_in_the_temporary_directory(tmp_path):
    Path("results").mkdir()
    (Path("results") / "scratch.csv").write_text("ticker\n")
    assert (tmp_path / "results" / "scratch.csv").exists()


def test_the_boundaries_need_no_credentials(monkeypatch, fake_alpaca, fake_anthropic, fake_resend):
    """The three doubles stand in for clients that all raise without a key."""
    import anthropic

    from src.scanner import get_clients

    for var in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(var, raising=False)
        assert var not in os.environ

    get_clients()
    anthropic.Anthropic()
    assert len(fake_alpaca.data_clients) == 1
