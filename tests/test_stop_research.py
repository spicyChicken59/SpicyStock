"""Registered sensitivity over actual producer records, never order authority."""
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest
from src import plan, provenance, reader, stop_research as research

FIXTURES = Path(__file__).parent / "fixtures/stop-research"
ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-10-10T12:00:00+00:00"


def raw(name="current"):
    return gzip.decompress((FIXTURES / (name + "-publication.json.gz")).read_bytes())


def result(name="current"):
    return ((FIXTURES / (name + "-receipt.json")).read_bytes(),
            (FIXTURES / (name + "-bundle.json")).read_bytes())


def reseal(bundle):
    for row in bundle["rows"]:
        row["research"]["projection_sha256"] = research._sha(research._encode(research._projection(row)))
    body = research._encode(bundle)
    receipt = {k: bundle[k] for k in research.COMMON_KEYS}
    receipt["bundle"] = {"path": "stop-research/" + research._sha(body) + ".json", "sha256": research._sha(body), "bytes": len(body)}
    return research._encode(receipt), body


@pytest.fixture(scope="module")
def current():
    return research.build(raw(), objects=ROOT / "docs/evidence", generated_at=NOW)


@pytest.fixture(scope="module")
def produced(tmp_path_factory):
    spec = importlib.util.spec_from_file_location("stop_fixture", FIXTURES / "generate.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    docs = tmp_path_factory.mktemp("stop-producer")
    publication = module.source_publication("priority", docs)
    return publication, docs / "evidence"


def test_actual_current_amounts_and_independent_exclusions(current):
    assert current["receipt_bytes"] == result()[0] and current["bundle_bytes"] == result()[1]
    rows = {row["ticker"]: row for row in current["bundle"]["rows"]}
    assert list(rows) == ["MG", "KE", "ZIM", "SN", "PSNL"]
    for symbol, expected in {"KE": (1,29.52,1.27), "PSNL": (3,49.26,2.22)}.items():
        p = rows[symbol]["research"]
        assert (p["shares"], p["principal_usd"], p["risk_usd"]) == expected
        assert p["allocation_fit"] and p["effective_risk_budget_usd"] == 2.5
        assert p["multipliers"] == {"regime":.5,"hazard":1.,"stop_risk":.5,"total":.25}
    assert rows["SN"]["research"]["shares"] == 0
    assert rows["SN"]["research"]["blockers"] == ["no_whole_share", "occupied_model_symbol"]
    for symbol in ("MG", "ZIM"):
        assert rows[symbol]["event"]["blocked"] and "known_event" in rows[symbol]["research"]["blockers"]
    r = current["bundle"]["reservations"]
    assert (r["open_model_principal_usd"], r["research_principal_usd"], r["research_risk_usd"], r["slots_used"]) == (188.37,78.78,3.49,3)
    assert current["bundle"]["counts"]["in_band"] == 3
    assert current["bundle"]["counts"]["mechanical_fit"] == 2


def test_source_geometry_original_tickets_and_reader_bytes_are_unchanged(current):
    original = raw(); data = json.loads(original)
    for row, old in zip(current["bundle"]["rows"], data["watchlist"]["top"]):
        assert row["ticker"] == old["ticker"]
        assert row["levels"] == {k: old["plan"][k] for k in ("trigger","limit","stop","stop_pct")}
        assert row["evidence"]["plan_sha256"] == old["evidence"]["planning"]["output_sha256"]
        assert row["evidence"]["inputs_sha256"] == provenance.digest(old["evidence"]["planning"]["inputs"])
        assert row["baseline"]["shares"] == old["plan"]["shares"]
    assert data["cash_budget"]["admitted"] == []
    projected, _ = reader.derive(original)
    assert hashlib.sha256(projected).hexdigest() == current["receipt"]["publication"]["reader_sha256"]
    assert raw() == original and plan.MAX_STOP_PCT == 4
    forbidden = {"order_json","order_line","order_readback","order_terms"}
    def scan(value):
        if isinstance(value, dict):
            assert not forbidden & value.keys()
            for v in value.values(): scan(v)
        elif isinstance(value, list):
            for v in value: scan(v)
    scan(current["bundle"])


def test_later_ranked_baseline_reserves_before_research():
    receipt, body = result("priority"); bundle = research.validate_bundle(receipt, body)
    rows = bundle["rows"]
    assert rows[-1]["ticker"] == "ZBASE" and rows[-1]["baseline"]["admitted"]
    assert [r["ticker"] for r in rows if r["research"]["allocation_fit"]] == ["COIL", "RONE", "RTHR"]
    assert "slot_cap" in rows[3]["research"]["blockers"]
    assert bundle["counts"]["mechanical_fit"] == 4 and bundle["counts"]["allocation_fit"] == 3
    assert bundle["reservations"]["baseline_symbols"] == ["ZBASE"]
    assert bundle["reservations"]["baseline_slots"] == 1 and bundle["reservations"]["slots_used"] == 4
    research.validate_for_publication(raw("priority"), receipt, body)


@pytest.mark.parametrize("name", ["empty", "red", "outside"])
def test_empty_refused_and_outside_cohorts_remain_visible(name):
    receipt, body = result(name); bundle = research.validate_for_publication(raw(name), receipt, body)
    assert bundle["counts"]["allocation_fit"] == 0
    if name == "empty": assert bundle["counts"]["top_count"] == 0 and bundle["status"] == "recorded"
    if name == "red":
        assert bundle["counts"]["considered"] > 0
        assert all("market_gate" in row["research"]["blockers"] for row in bundle["rows"])
    if name == "outside": assert bundle["status"] == "outside_period" and bundle["rows"] == []


def test_actual_generated_clock_labels_backfill(current):
    receipt, body = result("current-late")
    late = research.validate_for_publication(raw(), receipt, body)
    assert current["bundle"]["timing"]["classification"] == "before_entry"
    assert late["timing"]["classification"] == "after_entry"
    assert late["publication"] == current["bundle"]["publication"]
    assert late["rows"] == current["bundle"]["rows"]


@pytest.mark.parametrize("clock,phase", [("2026-10-12T13:30:00Z","during_entry"),("2026-10-12T14:00:00Z","after_entry")])
def test_entry_clock_boundary(produced, clock, phase):
    publication, objects = produced
    assert research.build(publication, objects=objects, generated_at=clock)["receipt"]["timing"]["classification"] == phase


@pytest.mark.parametrize("clock", ["2026-10-09T20:00:00Z","2026-10-10T12:00:00", "broken", "", False])
def test_invalid_or_prepublication_clock_refused(produced, clock):
    with pytest.raises(ValueError): research.build(produced[0], objects=produced[1], generated_at=clock)


def test_missing_source_and_altered_canonical_refused(produced, tmp_path):
    with pytest.raises(ValueError, match="sources or provenance"): research.build(produced[0], objects=tmp_path, generated_at=NOW)
    data = json.loads(produced[0]); data["watchlist"]["top"][0]["plan"]["stop"] += .01
    with pytest.raises(ValueError): research.build(json.dumps(data).encode(), objects=produced[1], generated_at=NOW)


def test_wrong_publication_binding_refused(produced):
    with pytest.raises(ValueError, match="differs from actual publication"):
        research.validate_for_publication(produced[0], *result(), objects=produced[1])


@pytest.mark.parametrize("change", [
    lambda b: b["rows"][1]["research"].__setitem__("shares", 2),
    lambda b: b["rows"][1]["research"].__setitem__("risk_usd", 1.26),
    lambda b: b["rows"][1]["research"].__setitem__("effective_risk_budget_usd", 5),
    lambda b: b["rows"][1]["research"]["multipliers"].__setitem__("hazard", .5),
    lambda b: b["rows"][0]["event"].__setitem__("blocked", False),
    lambda b: b["rows"][0]["research"].__setitem__("allocation_fit", True),
    lambda b: b["counts"].__setitem__("allocation_fit", 3),
    lambda b: b["reservations"].__setitem__("research_principal_usd", 78.79),
    lambda b: b["reservations"].__setitem__("remaining_model_principal_usd", 2000),
    lambda b: b["reservations"].__setitem__("slots_used", 4),
    lambda b: b["policy"].__setitem__("research_stop_pct", 6),
    lambda b: b["timing"].__setitem__("classification", "during_entry"),
    lambda b: b["rows"][1].__setitem__("order_json", {"buy":1}),
    lambda b: b["rows"][1]["research"].__setitem__("blockers", [[]]),
])
def test_resealed_contradictions_do_not_gain_trust(current, change):
    bundle = deepcopy(current["bundle"]); change(bundle)
    with pytest.raises(ValueError): research.validate_bundle(*reseal(bundle))


def test_strict_bytes_schema_and_stdlib_parser(current):
    receipt, bundle = result()
    for changed in (receipt + b' ', receipt.replace(b'"schema_version":1', b'"schema_version":1,"schema_version":1'), b'\xef\xbb\xbf' + receipt):
        # Whitespace alone is a valid receipt: it is the bundle identity that is hashed.
        if changed == receipt + b' ': assert research.parse_receipt(changed)
        else:
            with pytest.raises(ValueError): research.parse_receipt(changed)
    with pytest.raises(ValueError): research.validate_bundle(receipt, bundle + b' ')
    with pytest.raises(ValueError): research.parse_receipt(b' ' * (research.MAX_RECEIPT_BYTES+1))
    code = f"import sys; sys.path.insert(0,{str(ROOT)!r}); from src import stop_research as s; from pathlib import Path; s.validate_bundle(Path({str(FIXTURES/'current-receipt.json')!r}).read_bytes(),Path({str(FIXTURES/'current-bundle.json')!r}).read_bytes())"
    assert subprocess.run([sys.executable,"-I","-S","-c",code],capture_output=True).returncode == 0


def test_writer_retains_first_clock_old_cohorts_and_source_bytes(produced, tmp_path):
    publication, objects = produced
    before = {p.name:p.read_bytes() for p in objects.iterdir() if p.is_file()}
    first = research.write_publication(publication,tmp_path,objects=objects,generated_at=NOW)
    first_raw = (tmp_path / research.RECEIPT_FILE).read_bytes()
    assert research.write_publication(publication,tmp_path,objects=objects,generated_at="2026-10-12T15:00:00Z") == first
    assert (tmp_path / research.RECEIPT_FILE).read_bytes() == first_raw
    current = research.write_publication(raw(),tmp_path,objects=ROOT / "docs/evidence",generated_at=NOW)
    assert current != first and (tmp_path / first["bundle"]["path"]).is_file()
    restored = research.write_publication(publication,tmp_path,objects=objects,generated_at="2026-10-12T15:00:00Z")
    assert restored == first and len(json.loads((tmp_path/research.INDEX_FILE).read_bytes())["objects"]) == 2
    assert {p.name:p.read_bytes() for p in objects.iterdir() if p.is_file()} == before


@pytest.mark.parametrize("failure", ["index", "bundle", "symlink", "capacity", "unknown"])
def test_invalid_archive_preserves_every_prior_byte(produced, tmp_path, monkeypatch, failure):
    publication, objects = produced
    receipt = research.write_publication(publication,tmp_path,objects=objects,generated_at=NOW)
    if failure == "index": (tmp_path / research.INDEX_FILE).write_bytes(b'{}')
    elif failure == "bundle": (tmp_path / receipt["bundle"]["path"]).write_bytes(b'{}')
    elif failure == "symlink":
        p=tmp_path/research.RECEIPT_FILE; saved=p.read_bytes(); p.unlink(); target=tmp_path/'external'; target.write_bytes(saved); p.symlink_to(target)
    elif failure == "capacity": monkeypatch.setattr(research,"MAX_BUNDLES",0)
    else: (tmp_path / research.BUNDLE_DIR / "unknown.txt").write_bytes(b'preserve')
    before = {str(p.relative_to(tmp_path)):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    with pytest.raises(ValueError): research.write_publication(publication,tmp_path,objects=objects,generated_at=NOW)
    assert {str(p.relative_to(tmp_path)):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()} == before


def test_optional_write_failure_keeps_previous_receipt(produced,tmp_path,monkeypatch):
    publication,objects=produced
    first=research.write_publication(publication,tmp_path,objects=objects,generated_at=NOW)
    previous=(tmp_path/research.RECEIPT_FILE).read_bytes(); actual=research._atomic
    def refuse_latest(path, body):
        if path.name == research.RECEIPT_FILE: raise OSError("synthetic full disk")
        return actual(path,body)
    monkeypatch.setattr(research,"_atomic",refuse_latest)
    with pytest.raises(OSError): research.write_publication(raw(),tmp_path,objects=ROOT/'docs/evidence',generated_at=NOW)
    assert (tmp_path/research.RECEIPT_FILE).read_bytes()==previous
    assert (tmp_path/first['bundle']['path']).is_file()
    monkeypatch.setattr(research,"_atomic",actual)
    final=research.write_publication(raw(),tmp_path,objects=ROOT/'docs/evidence',generated_at=NOW)
    assert final['publication']['data_sha256']==hashlib.sha256(raw()).hexdigest()


def test_real_open_model_reservations_keep_all_four_slots(tmp_path):
    from tools import make_fixture
    spec = importlib.util.spec_from_file_location("stop_fixture", FIXTURES / "generate.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    publication = module.source_publication("priority", tmp_path, ledger_factory=make_fixture.prior_picks)
    bundle = research.build(publication, objects=tmp_path / "evidence", generated_at=NOW)["bundle"]
    assert bundle["reservations"]["open_model_slots"] == 3
    assert bundle["reservations"]["open_model_principal_usd"] == 1762.98
    assert bundle["reservations"]["baseline_symbols"] == ["ZBASE"]
    assert bundle["reservations"]["slots_used"] == 4
    assert bundle["counts"]["mechanical_fit"] == 4 and bundle["counts"]["allocation_fit"] == 0
    assert all("slot_cap" in row["research"]["blockers"] for row in bundle["rows"][:4])


def test_other_account_and_unsupported_planner_are_refused(tmp_path, produced, monkeypatch):
    spec = importlib.util.spec_from_file_location("stop_fixture", FIXTURES / "generate.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    publication = module.source_publication("outside", tmp_path, account_equity="10000")
    with pytest.raises(ValueError, match="unsupported account"):
        research.build(publication, objects=tmp_path / "evidence", generated_at=NOW)
    monkeypatch.setitem(plan.RULES, "plan.max_stop_pct", 6.)
    with pytest.raises(ValueError): research.build(produced[0], objects=produced[1], generated_at=NOW)


def test_fixture_regeneration_is_required_in_ci():
    import yaml
    workflow = yaml.safe_load((ROOT / ".github/workflows/tests.yml").read_text())
    commands = "\n".join(step.get("run", "") for step in workflow["jobs"]["pytest"]["steps"])
    assert "python tests/fixtures/stop-research/generate.py --check" in commands
