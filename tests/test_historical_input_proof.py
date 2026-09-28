"""Retained identity and truthful scope regressions; no external requests."""
from copy import deepcopy
from datetime import datetime
import gzip
import json
import socket

import pytest

from tools import historical_input_proof as proof


def exact_fixture_bytes(raw, expected_sha256):
    if proof.sha(raw) != expected_sha256:
        raise ValueError("offline historical fixture byte hash mismatch")
    return raw


def fixture_git_bytes(revision, path):
    """Only known, hash-proven fixtures substitute for old Git blobs in CI.

    Default Actions checkouts are shallow. The actual audit runner still
    requires and reads the original Git commits; this boundary is tests only.
    """
    publication_fixtures = {
        "2026-09-24": "tests/fixtures/chart-keyboard/2026-09-24.json.gz",
        "2026-09-25": "tests/fixtures/wait-explanations/2026-09-25.json.gz",
    }
    for day, reference in proof.REFERENCES.items():
        if path == "docs/data.json" and revision == reference["publication_commit"]:
            raw = gzip.decompress((proof.ROOT / publication_fixtures[day]).read_bytes())
            return exact_fixture_bytes(raw, reference["publication_sha256"])
        if path == "data/symbols.txt" and revision == reference["execution_revision"]:
            frozen = json.loads((proof.ROOT / "docs/input-truthfulness/2026-09-28-historical-input-evidence/acquisition-manifest.json").read_bytes())
            raw = (proof.ROOT / path).read_bytes().replace(b"\r\n", b"\n")
            return exact_fixture_bytes(raw, frozen["populations"][day]["price_exempt_source_sha256"])
    raise ValueError("undeclared historical revision/path in offline fixture boundary")


@pytest.fixture(scope="module")
def originals():
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(proof, "git_bytes", fixture_git_bytes)
        with proof.network_blocked():
            values = proof.load_originals()
        yield values


def test_fixture_boundary_rejects_wrong_bytes_and_undeclared_git_objects():
    with pytest.raises(ValueError, match="byte hash mismatch"):
        exact_fixture_bytes(b"changed publication", proof.REFERENCES["2026-09-24"]["publication_sha256"])
    with pytest.raises(ValueError, match="undeclared historical revision/path"):
        fixture_git_bytes("HEAD", "docs/data.json")
    with pytest.raises(ValueError, match="undeclared historical revision/path"):
        fixture_git_bytes(proof.REFERENCES["2026-09-24"]["execution_revision"], "src/pipeline.py")


def test_sample_cannot_be_promoted_to_full_membership():
    names = ["AAA", "BBB", "CCC"]
    identity = proof.sha("\n".join(names).encode())[:16]
    with pytest.raises(ValueError, match="complete sorted population"):
        proof.full_population({"count": 3, "identity": identity, "sample": names[:2]})
    with pytest.raises(ValueError, match="complete sorted population"):
        proof.full_population({"count": 3, "identity": identity, "symbols": names[:2]})
    with pytest.raises(ValueError, match="identity mismatch"):
        proof.full_population({"count": 3, "identity": identity, "symbols": ["AAA", "BBB", "DDD"]})


def test_retained_full_populations_and_all_stale_names(originals):
    stale = set()
    for day, (package, publication, ids) in originals.items():
        assert ids["publication_sha256"] == proof.REFERENCES[day]["publication_sha256"]
        assert package["run"]["execution_revision"] == proof.REFERENCES[day]["execution_revision"]
        assert proof.full_population(package["intended_stocks"]) == package["universe_membership"]["symbols"]
        stale.update(proof.full_population(package["exceptions"]["stale"]))
        rows = proof.exception_rows(day, package)
        assert len(rows) == proof.REFERENCES[day]["stale"]
        assert all(x["original_last_observation_session"] == package["capture"]["prior_session"] for x in rows)
        assert all(x["new_target_prior_comparison"] == "BLOCKED" for x in rows)
    assert len(stale) == 31


def test_manifest_preserves_mapping_and_complete_population_across_chunks(originals):
    manifest = proof.make_manifest(originals)
    assert manifest["limits"]["requests"] == 400
    assert manifest["normalization"]["identity"] == "historical-normalization-v1"
    assert len(manifest["queries"]) == 97
    assert len([q for q in manifest["queries"] if q["scope"] == "probe"]) == 1
    assert manifest["additional_spend_ceiling_usd"] == 0
    for day, population in manifest["populations"].items():
        chunks = [q for q in manifest["queries"] if q["target_session"] == day and q["scope"] == "bulk"]
        names = [s for q in chunks for s in q["symbols"]]
        assert len(names) == len(set(names))
        assert sorted(names) == sorted(population["symbols"] + ["SPY"])
        assert population["sha256"] == proof.symbol_hash(population["symbols"])
        assert set(population["price_exempt"]) <= set(population["symbols"])
        assert population["price_exempt"]
        assert population["original_final_mask_complete"] is False
        for q in chunks:
            assert len(q["symbols"]) <= 100
            assert q["asof"] == originals[day][0]["basis"]["fetch_arguments"]["now"][:10]
            assert q["asof"] != day  # Original overnight run dates, not target dates.
            assert datetime.fromisoformat(q["start"]).tzinfo is not None
            assert datetime.fromisoformat(q["end"]).tzinfo is not None
            assert q["required_sessions_ref"] == day
        assert len(manifest["required_sessions"][day]) >= 252


def test_retained_price_exclusion_sample_does_not_become_complete_mask(originals):
    package, publication, _ = originals["2026-09-24"]
    # One known included candidate is enough to establish the contract; no raw
    # values need to be repeated to test the unknown-membership safeguard.
    mask = proof.population_mask(package, publication, {"CRL": object()})
    assert mask["recorded_final_population_count"] == 3716
    assert len(mask["known_price_excluded"]) == 8
    assert mask["recorded_price_excluded"]["count"] == 1047
    assert mask["exact_original_final_mask"] == "BLOCKED"
    assert mask["final_price_mask_unknown_count"] == 4763 - 8 - 1
    with pytest.raises(ValueError, match="contradictory"):
        proof.population_mask(package, publication, {"ARBB": object()})


def test_every_original_permission_predicate_is_reconciled(originals):
    for _, publication, _ in originals.values():
        check = proof.reconcile_aggregate(publication["breadth"])
        assert check["status"] == "PASS"
        assert check["verdict"] == "red"
        assert len(check["predicates"]) == 5
        active = {p["id"] for p in check["predicates"] if p["active"]}
        assert active == {"red_ratio_10d", "yellow_ratio_10d", "yellow_up50_month"}


def test_changed_aggregate_is_a_failure_not_later_data_proof(originals):
    block = deepcopy(originals["2026-09-24"][1]["breadth"])
    block["up4_10d"] += 1
    result = proof.reconcile_aggregate(block)
    assert result["status"] == "FAIL"
    assert "up4_10d" in result["mismatches"]


@pytest.mark.parametrize("change", ["duplicate", "missing"])
def test_aggregate_history_must_be_consecutive_exchange_sessions(originals, change):
    block = deepcopy(originals["2026-09-24"][1]["breadth"])
    if change == "duplicate":
        block["history"][-2]["date"] = block["history"][-3]["date"]
    else:
        del block["history"][-2]
    result = proof.reconcile_aggregate(block)
    assert result["status"] == "FAIL"
    assert "history.last10_dates" in result["mismatches"]


@pytest.mark.parametrize("field", ["inputs", "thresholds", "size_multiplier", "oversold_extreme"])
def test_every_archived_regime_field_must_match_independent_reconstruction(originals, field):
    block = deepcopy(originals["2026-09-24"][1]["breadth"])
    if field == "inputs":
        block["regime"][field]["up4_10d"] += 1
    elif field == "thresholds":
        block["regime"][field]["down4_alarm"] += 1
    elif field == "size_multiplier":
        block["regime"][field] = 1
    else:
        block["regime"][field] = not block["regime"][field]
    result = proof.reconcile_aggregate(block)
    assert result["status"] == "FAIL"
    assert f"regime.{field}" in result["mismatches"]


def test_zero_denominators_remain_unknown(originals):
    block = deepcopy(originals["2026-09-24"][1]["breadth"])
    for row in block["history"]:
        row["down4"] = 0
    check = proof.reconcile_aggregate(block)
    assert check["sums"]["ratio_10d"] is None
    assert check["sums"]["ratio_5d"] is None
    assert all(not p["active"] for p in check["predicates"] if p["id"] in {"red_ratio_10d", "red_fast_selling", "yellow_ratio_10d"})


def test_offline_runner_blocks_sockets_and_restores_them():
    prior = socket.create_connection
    with proof.network_blocked():
        with pytest.raises(RuntimeError, match="network forbidden"):
            socket.create_connection(("example.invalid", 443))
        with socket.socket() as sock:
            with pytest.raises(RuntimeError, match="network forbidden"):
                sock.connect(("127.0.0.1", 9))
    assert socket.create_connection is prior


def test_crl_volume_boundary_keeps_dollar_and_iqv_control(originals):
    with proof.network_blocked():
        rows = {x["ticker"]: x for x in proof.volume_sensitivity(originals)}
    crl, iqv = rows["CRL"], rows["IQV"]
    assert crl["public_observation_date"] == iqv["public_observation_date"] == "2026-09-28"
    assert crl["cases"][0]["discovery_routes"] == ["dollar"]
    assert crl["cases"][1]["discovery_routes"] == ["burst", "dollar"]
    assert [c["mechanical_grade"] for c in crl["cases"]] == ["A", "A+"]
    assert crl["ten_session_event_deltas"] == {"up4": 1, "down4": 0}
    assert crl["all_affected_events_ratio_10d"] == .94
    assert iqv["ten_session_event_deltas"] == {"up4": 0, "down4": 0}
    assert [c["mechanical_grade"] for c in iqv["cases"]] == ["A", "A"]
    assert crl["new_reader_judgment"] == iqv["new_reader_judgment"] == "unknown"
