from datetime import datetime, timezone
import json

import pytest

from tools import probe_morning_sources as probe


def test_probe_only_requests_fixed_symbol_and_sanitizes_provider_failures():
    calls = []

    class Client:
        def get_stock_snapshot(self, request):
            calls.append((request.symbol_or_symbols, request.feed.value))
            raise RuntimeError("sensitive raw response must never reach diagnostic")

    at = datetime(2026, 10, 9, 15, 30, tzinfo=timezone.utc)
    result = probe.probe(client=Client(), clock=lambda: at)
    assert calls == [(["SPY"], "iex"), (["SPY"], "delayed_sip")]
    assert result["schema"] == "spicystock-source-probe-v1"
    assert result["trade"]["status"] == result["quote"]["status"] == "unavailable"
    assert all(v["error_kind"] == "provider_error" for v in result["sources"].values())
    assert "sensitive" not in json.dumps(result)
    assert "publication" not in result and "rows" not in result


def test_probe_cannot_write_public_files_or_overwrite_existing_file(tmp_path, monkeypatch):
    public = tmp_path / "docs"
    public.mkdir()
    monkeypatch.setattr(probe, "PUBLIC_ROOT", public)
    with pytest.raises(ValueError, match="public docs"):
        probe.write_probe(probe.PUBLIC_ROOT / "morning.json", {})
    output = tmp_path / "probe.json"
    output.write_text("keep")
    with pytest.raises(FileExistsError):
        probe.write_probe(output, {})
    assert output.read_text() == "keep"
    safe = tmp_path / "new-probe.json"
    probe.write_probe(safe, {"purpose": "transport_diagnostic_only"})
    assert json.loads(safe.read_text()) == {"purpose": "transport_diagnostic_only"}
