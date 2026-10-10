"""Private cash previews use complete producer-sized, exactly bound controls."""
import importlib.util
import json
from pathlib import Path

import pytest

from src import morning, provenance, reader

FIXTURES = Path(__file__).parent / "fixtures" / "cash-preview"
spec = importlib.util.spec_from_file_location("cash_preview_fixture_generator", FIXTURES / "generate.py")
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


def test_cash_preview_controls_reproduce_exact_offline_producer_bytes():
    produced = generator.build()
    assert set(produced) == {"publication.json", "observed.json", "halted.json", "corporate-excluded.json",
                             "publication-multiple.json", "observed-multiple.json"}
    for name, body in produced.items():
        assert (FIXTURES / name).read_bytes() == body, name


def test_cash_preview_generator_rejects_tampered_producer_evidence(monkeypatch):
    original = generator.make_fixture.run_variant

    def tampered(*args, **kwargs):
        data = original(*args, **kwargs)
        decision = data["bursts"][0]["review_selection"]
        decision["selected"] = not decision["selected"]
        return data

    monkeypatch.setattr(generator.make_fixture, "run_variant", tampered)
    with pytest.raises(AssertionError, match="cash-preview fixture integrity failed:.*review selection evidence mismatch"):
        generator.publication()


@pytest.mark.parametrize("name,tickets,committed", [
    ("publication", [("anticipation", "COIL")], 446.88),
    ("publication-multiple", [("burst", "AAPL"), ("anticipation", "COIL")], 510.10),
])
def test_cash_preview_publications_preserve_account_allocation_and_provenance(name, tickets, committed):
    raw = (FIXTURES / (name + ".json")).read_bytes()
    data = json.loads(raw)
    assert data.get("fixture") is None and data["run"]["run_id"].startswith("synthetic-cash-preview")
    assert {key: data["account"][key] for key in generator.ACCOUNT_FIELDS} == {
        "equity": 2000, "risk_pct": 0.5, "max_position_pct": 25, "max_open_positions": 4}
    assert [(row["kind"], row["ticker"]) for row in morning.admitted_rows(data)] == tickets
    assert data["cash_budget"]["committed_usd"] == committed
    assert data["cash_budget"]["reserved_usd"] == 0
    # These fixtures retain publication evidence, not the temporary source
    # objects; require an integrity pass without claiming a source audit.
    integrity = provenance.verify(data, require_sources=False)
    assert integrity["status"] == "PASS", integrity
    projected, retained = reader.derive(raw)
    reader.validate_bundle(raw, projected, retained)


@pytest.mark.parametrize("name,source", [
    ("observed", "publication"), ("halted", "publication"),
    ("corporate-excluded", "publication"), ("observed-multiple", "publication-multiple"),
])
def test_cash_preview_receipts_pass_persistence_binding_and_positive_event_controls(name, source):
    raw = (FIXTURES / (source + ".json")).read_bytes()
    receipt = json.loads((FIXTURES / (name + ".json")).read_bytes())
    assert receipt["publication"] == morning.bind_record(raw)
    assert receipt["generated_at"] == "2026-09-11T13:35:00+00:00"
    morning.validate_observation(receipt, raw, previous_raw=None, require_continuity=True)
    row = next(row for row in receipt["rows"] if row["ticker"] == "COIL")
    # An empty RSS response is unknown coverage, never a trading clearance.
    assert row["events"]["halt"]["blocks_entry"] is (True if name == "halted" else None)
    assert row["events"]["corporate_action"]["blocked"] is (name == "corporate-excluded")
    if name == "halted":
        assert receipt["halt_memory"]["COIL"]["halt"]["blocks_entry"] is True
    if name == "corporate-excluded":
        assert receipt["corporate_memory"]["COIL"][0]["event"]["id"] == "synthetic_coil_cash_event"
