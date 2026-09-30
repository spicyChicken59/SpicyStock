"""Full synthetic reconciliation proves the representation-only boundary."""
import hashlib
import json
from pathlib import Path

import pytest

from tests.test_historical_acquisition import setup, response, bar
from tests.test_historical_reconcile import prepare, probe_response
from tests.test_historical_projection import old_adapter
from tools import historical_reconcile as reconciliation
from tools.historical_normalization import COMPACT_PROJECTION, LEGACY_PROJECTION, iter_projection_conversions


def baseline_reconcile(manifest, storage, session):
    path = Path(__file__).parent / "fixtures/projection-compaction/legacy_reconcile.py"
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "b3a2730565fbc078310497174ecc1a695a37f9d6835a8dd70d8b4b756004798f"
    namespace = vars(reconciliation).copy()
    namespace["frames_for_replay"] = old_adapter
    exec(compile(raw, str(path), "exec"), namespace)
    return namespace["reconcile"](manifest, storage, session)


def test_compact_reconciliation_matches_untouched_actual_adapter_and_all_other_fields(setup):
    manifest, approval, root, clock, build = setup
    query = prepare(manifest)
    rows = [bar(d, o=10.1, h=20.2, l=1.1, c=11.3, v=100000.1) for d in query["required_sessions"]]
    runner, transport = build([probe_response(), response({s: rows for s in ("AAA", "BBB", "SPY")})])
    runner.run("canonical")
    runner.run("bulk")
    calls = len(transport.calls)
    destination = root / "reconciliation-2026-09-25.json"
    old_public = baseline_reconcile(manifest, root, "2026-09-25")
    old_bytes = destination.read_bytes()
    old = json.loads(old_bytes)
    legacy_public = reconciliation.reconcile(manifest, root, "2026-09-25", projection_contract=LEGACY_PROJECTION)
    assert destination.read_bytes() == old_bytes
    assert legacy_public == old_public
    new_public = reconciliation.reconcile(manifest, root, "2026-09-25")
    new_bytes = destination.read_bytes()
    new = json.loads(new_bytes)
    assert new["schema"] == "historical-reconciliation-v2"
    assert old["schema"] == "historical-reconciliation-v1"
    assert new_public["output_sha256"] == hashlib.sha256(new_bytes).hexdigest()
    assert {k: v for k, v in old_public.items() if k != "output_sha256"} == {
        k: v for k, v in new_public.items() if k != "output_sha256"}
    assert {k: v for k, v in old.items() if k not in ("schema", "float64_projection")} == {
        k: v for k, v in new.items() if k not in ("schema", "float64_projection")}
    for before, projection, normal in zip(old["float64_projection"], new["float64_projection"], new["normalizations"], strict=True):
        assert before["query"] == projection["query_id"] == normal["query_id"]
        assert projection["schema"] == COMPACT_PROJECTION
        assert list(iter_projection_conversions(projection, normal)) == before["inexact_conversions"]
    again = reconciliation.reconcile(manifest, root, "2026-09-25")
    assert destination.read_bytes() == new_bytes
    assert again == new_public and len(transport.calls) == calls
    assert len(new_bytes) < len(old_bytes)


def test_compact_reconciliation_rejects_unsupported_contract_before_cache_access():
    with pytest.raises(ValueError, match="contract"):
        reconciliation.reconcile({}, "unused", "2026-09-25", projection_contract="future")


def test_compact_default_reconciliation_has_no_expanded_float_record_list(setup):
    manifest, approval, root, clock, build = setup
    prepare(manifest)
    rows = [bar("2026-09-24", o=10.1, h=20.2, l=1.1, c=11.3, v=100000.1),
            bar("2026-09-25", o=10.2, h=20.3, l=1.2, c=11.4, v=100001.1)]
    runner, _ = build([probe_response(), response({s: rows for s in ("AAA", "BBB", "SPY")})])
    runner.run("canonical")
    runner.run("bulk")
    reconciliation.reconcile(manifest, root, "2026-09-25")
    output = json.loads((root / "reconciliation-2026-09-25.json").read_bytes())
    assert all("inexact_conversions" not in p for p in output["float64_projection"]), (
        "default projection must be compact while retaining every original conversion fact")
    assert output["schema"] == "historical-reconciliation-v2"
    assert sum(p["conversion_count"] for p in output["float64_projection"]) == 30
