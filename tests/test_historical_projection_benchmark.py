"""Fresh invented decimal benchmarks; real encryption only with explicit age."""
from copy import deepcopy
from decimal import Decimal
import json
import hashlib
import os
from pathlib import Path
import sys

import pytest

from tests.test_historical_execution import run_setup
from tools import historical_projection_benchmark as benchmark


@pytest.fixture
def age_binary():
    path = os.environ.get("AGE_BINARY")
    if not path:
        pytest.skip("real benchmark encryption requires explicit AGE_BINARY")
    assert Path(path).is_file()
    return Path(path).absolute()


def short_root(tmp_path):
    # Keep actual hash-named pages below Windows' native path-length boundary.
    return tmp_path.parent / ("b-" + hashlib.sha256(str(tmp_path).encode()).hexdigest()[:12])


@pytest.mark.parametrize("child_peak", [None, 1024])
def test_memory_report_does_not_substitute_zero_for_unmeasured_age(child_peak):
    process = {"process_peak_rss_bytes": 4096, "measurement": "synthetic counter fixture"}
    child = {} if child_peak is None else {"age_process_peak_rss_bytes": child_peak}
    result = benchmark.memory_summary(process, child)
    assert result["python_plus_age_peak_rss_conservative_sum_bytes"] == (None if child_peak is None else 5120)
    assert ("unavailable" in result["scope"]) is (child_peak is None)
    assert "scope" not in process  # Reporting does not mutate measured counters.


@pytest.mark.parametrize("case", benchmark.CASES)
def test_deterministic_decimal_scenarios_vary_and_keep_valid_geometry(case):
    examples = [benchmark.decimal_fields(case, symbol, day)
                for symbol in ("AAA", "BBB") for day in ("2026-09-24", "2026-09-25")]
    assert len({tuple(row) for row in examples}) == 4
    assert examples[0] == benchmark.decimal_fields(case, "AAA", "2026-09-24")
    assert examples[0] != benchmark.decimal_fields(case, "AAA", "2026-09-24", "different-seed")
    for row in examples:
        opening, high, low, close, volume = map(Decimal, row)
        assert high >= max(opening, close) >= min(opening, close) >= low > 0
        assert volume > 0
        if case == "stress":
            assert all(Decimal.from_float(float(value)) != Decimal(value) for value in row)
            assert [len(value.split(".")[1]) for value in row] == [9, 9, 9, 9, 6]
        else:
            assert all(len(value.split(".")[1]) == 2 for value in row[:4])
            assert volume == int(volume)


def test_frozen_shape_is_exact_and_rejects_missing_batch():
    manifest = json.loads(benchmark.MANIFEST.read_bytes())
    benchmark.require_full_shape(manifest)
    assert benchmark.shape(manifest) == {
        "canonical_batches": 96, "sessions_per_bulk_query": [288],
        "bulk_rows": 2_753_568, "probe_rows": 2, "filled_page_requests": 289}
    changed = deepcopy(manifest)
    changed["queries"].pop()
    with pytest.raises((ValueError, benchmark.acquisition.AcquisitionError)):
        benchmark.require_full_shape(changed)


def test_transport_preserves_long_numeric_lexemes_and_full_windows(run_setup):
    manifest = run_setup[0]
    transport = benchmark.SyntheticTransport(manifest, "stress")
    q = benchmark.acquisition.resolved_query(manifest, "bulk-2026-09-24")
    params = {key: ",".join(q[key]) if key == "symbols" else q[key] for key in transport.fields}
    rows = []
    while True:
        response = transport(params, manifest["limits"]["page_bytes"])
        payload = json.loads(response.body, parse_float=Decimal)
        rows.extend(payload["bars"].get("AAA", []))
        if payload["next_page_token"] is None:
            break
        params["page_token"] = payload["next_page_token"]
    assert len(rows) == len(q["required_sessions"]) > 80
    expected = benchmark.decimal_fields("stress", "AAA", q["required_sessions"][0])
    assert [rows[0][key] for key in "ohlcv"] == list(map(Decimal, expected))
    assert rows[0]["n"] > 0 and rows[0]["l"] <= rows[0]["vw"] <= rows[0]["h"]
    assert transport.calls == 4


@pytest.mark.parametrize("case", benchmark.CASES)
def test_actual_small_acquisition_reconciliation_package_recovery(run_setup, tmp_path, monkeypatch, age_binary, case):
    monkeypatch.setattr(benchmark, "MINIMUM_FREE_DISK", 0)
    monkeypatch.setattr(benchmark.acquisition, "AlpacaTransport", lambda: pytest.fail("provider transport constructed"))
    root = short_root(tmp_path)
    result = benchmark.run_case(run_setup[0], case, root, age_binary, full_scale=False)
    assert result["status"] == "PASS", result
    assert result["provider_requests"] == 0
    assert result["runtime_scope"].startswith(f"local {sys.platform} host;")
    assert result["generated_rows"] == result["shape"]["bulk_rows"] + 2
    assert result["recovered_original_member_count"] == 15
    assert result["all_original_members_byte_identical"] and result["ledger_accounting_unchanged"]
    assert result["disposable_test_identity_removed"]
    assert result["projection_measurements"]["replayable_rows"] == result["shape"]["bulk_rows"]
    if case == "stress":
        assert result["projection_measurements"]["inexact_fraction_of_all_five_fields"] == 1
    assert all(row["same_input_formula_status"] == "PASS" for row in result["reconciliation"])
    metrics = result["package_measurements"]
    assert metrics["expanded_payload_bytes"] > result["source_member_payload_bytes"]
    assert metrics["tar_archive_bytes"] > metrics["expanded_payload_bytes"] > metrics["gzip_archive_bytes"]
    assert metrics["ciphertext_bytes"] > metrics["gzip_archive_bytes"]
    assert metrics["index_bytes"] > 0 and metrics["tar_headers_and_padding_bytes"] > 0
    assert result["memory"]["process_peak_rss_bytes"] > 0
    assert result["peak_scratch_bytes_sampled"] >= result["source_member_payload_bytes"] * 2


def test_actual_archive_cap_failure_is_measured_without_encryption_or_delivery(run_setup, tmp_path, monkeypatch, age_binary):
    monkeypatch.setattr(benchmark, "MINIMUM_FREE_DISK", 0)
    monkeypatch.setattr(benchmark.package, "MAX_ARCHIVE_BYTES", 1)
    monkeypatch.setattr(benchmark.package, "_age", lambda *a, **k: pytest.fail("age ran beyond archive cap"))
    root = short_root(tmp_path)
    result = benchmark.run_case(run_setup[0], "central", root, age_binary, full_scale=False)
    assert result["status"] == "FAIL"
    assert result["stopped_at_phase"] == "package"
    assert result["reason"] == "package_size_or_member_limit"
    assert result["package_measurements"]["gzip_archive_bytes"] > 1
    assert result["package_measurements"]["index_bytes"] > 0
    assert "ciphertext_bytes" not in result["package_measurements"]
    assert result["memory"]["python_plus_age_peak_rss_conservative_sum_bytes"] is None
    assert not (root / "delivery").exists() and not (root / "recovered").exists()
    assert result["disposable_test_identity_removed"]
    assert not list((root / "synthetic-storage").glob(".package-*"))
