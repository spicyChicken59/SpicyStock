"""Actual synthetic Acquisition -> cache -> normalization -> replay, no HTTP."""
from copy import deepcopy
from datetime import date
import json
import os
from pathlib import Path
import sqlite3
import subprocess

import pytest

from src import sessions
from tools import historical_acquisition as acquisition
from tools import historical_execution as execution


@pytest.fixture
def run_setup(tmp_path, monkeypatch):
    for name in execution.SECRETS:
        monkeypatch.delenv(name, raising=False)
    population = ["AAA", "BBB"]
    queries = [{"id": "probe", "symbols": ["SPY"], "scope": "probe",
                "start": "2026-09-24T04:00:00Z", "end": "2026-09-25T23:59:59Z",
                "required_sessions": ["2026-09-24", "2026-09-25"], "asof": "2026-09-26"}]
    for target in ("2026-09-24", "2026-09-25"):
        queries.append({"id": "bulk-" + target, "symbols": population + ["SPY"],
                        "scope": "bulk", "target_session": target,
                        "start": "2026-05-01T04:00:00Z", "end": target + "T23:59:59Z",
                        "required_sessions": [str(day) for day in sessions.dates(date(2026, 5, 1), date.fromisoformat(target))],
                        "asof": "2026-09-26"})
    for query in queries:
        query.update(feed="sip", timeframe="1Day", adjustment="split", currency="USD",
                     limit=100, sort="asc", purpose="canonical")
    manifest = {"schema": acquisition.SCHEMA, "assignment_id": acquisition.ASSIGNMENT,
                "populations": {day: {"symbols": population, "sha256": acquisition.symbols_digest(population)}
                                for day in ("2026-09-24", "2026-09-25")}, "queries": queries,
                "limits": {"requests": 400, "retained_bytes": 1024 ** 3,
                           "requests_per_minute": 20, "page_bytes": 1024 * 1024},
                "documentation": {"verified_at": "2026-09-28",
                                  "stockbars_url": "https://docs.alpaca.markets/us/reference/stockbars",
                                  "faq_url": "https://docs.alpaca.markets/us/docs/market-data-faq"}}
    identity = acquisition.validate_manifest(manifest)
    monkeypatch.setattr(execution, "MANIFEST_SHA256", identity)
    monkeypatch.setattr(execution, "_checkout_sha", lambda: "a" * 40)
    storage = tmp_path / "storage"
    record = {"schema": "historical-execution-v1", "status": "PASS", "mode": "rehearsal",
              "assignment_id": acquisition.ASSIGNMENT, "manifest_sha256": identity,
              "repository": execution.REPOSITORY, "repository_id": 123, "workflow_id": 456,
              "run_id": 789, "run_number": 1, "run_attempt": 1, "readiness_comment_id": 567,
              "implementation_pr": 94, "checkout_sha": "a" * 40, "workflow_sha": "b" * 40,
              "recipient_sha256": "c" * 64, "readiness_status": "PASS", "lifetime_status": "PASS"}
    approval = {"assignment_id": acquisition.ASSIGNMENT, "manifest_sha256": identity,
                "storage_root": str(storage), "zero_additional_cost": True,
                "cost_basis": "invented offline test data", "sip_daily_entitlement_basis": "synthetic only",
                "non_public_storage": True, "retention_rights_basis": "invented test data",
                "reviewer_retrieval_path": "synthetic local fixture", "approved_by": "synthetic test",
                "provider_requests_per_minute": 20}
    for name, value in {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "workflow_dispatch",
                        "GITHUB_REPOSITORY": execution.REPOSITORY, "GITHUB_REF": "refs/heads/main",
                        "GITHUB_REPOSITORY_ID": "123", "GITHUB_RUN_ID": "789", "GITHUB_RUN_NUMBER": "1",
                        "GITHUB_RUN_ATTEMPT": "1", "GITHUB_WORKFLOW_SHA": "b" * 40}.items():
        monkeypatch.setenv(name, value)
    return manifest, storage, record, approval


def invoke(setup, mode="rehearsal"):
    manifest, storage, record, approval = setup
    return execution.execute(mode, manifest, storage, record, approval)


def rows(storage):
    with sqlite3.connect((storage / "ledger.sqlite3").as_uri() + "?mode=ro", uri=True) as db:
        return db.execute("SELECT query_id,token,status,retained,reservation FROM attempts ORDER BY id").fetchall()


def test_actual_paginated_rehearsal_and_offline_replay_preserve_incomplete_history(run_setup, monkeypatch):
    manifest, storage, _, _ = run_setup
    monkeypatch.setattr(acquisition, "AlpacaTransport", lambda: pytest.fail("real transport constructed"))
    assert invoke(run_setup)["status"] == "PASS"
    before = rows(storage)
    assert len(before) == 7  # One probe plus three real pagination pages per target.
    assert {row[0] for row in before} == {query["id"] for query in manifest["queries"]}
    assert all(row[2] == "complete" and row[3] > 0 and row[4] == 0 for row in before)
    page = acquisition.cached_pages(manifest, storage, "bulk-2026-09-25")
    assert page["terminal"] is True
    report = json.loads((storage / "bulk-2026-09-25-manifest.json").read_bytes())
    assert report["symbols"]["AAA"]["state"] == "partial"
    assert report["symbols"]["AAA"]["missing_sessions"]
    result = invoke(run_setup, "offline")
    assert result["status"] == "PASS"
    assert rows(storage) == before
    for day in manifest["populations"]:
        detail = json.loads((storage / ("reconciliation-" + day + ".json")).read_bytes())
        assert detail["new_provider_requests"] == 0
        assert detail["normalizations"] and detail["C"]["status"] != "NOT RUN"
        assert detail["complete_required_input_windows"] is False
        assert detail["B"]["status"] == "BLOCKED"
    diagnostic = json.loads((storage / "execution-diagnostics.json").read_bytes())
    assert diagnostic["prior_acquisition"]["synthetic_transport_calls"] == 7
    assert diagnostic["new_provider_requests"] == 0


def test_frozen_manifest_synthetic_transport_covers_all_97_queries_without_provider():
    manifest = execution._json(execution.MANIFEST)
    transport = execution.SyntheticTransport(manifest)
    assert len(transport.queries) == len(manifest["queries"]) == 97
    for query in manifest["queries"]:
        resolved = acquisition.resolved_query(manifest, query["id"])
        params = {field: resolved[field] for field in transport.fields if field != "symbols"}
        params["symbols"] = ",".join(query["symbols"])
        response = transport(params, manifest["limits"]["page_bytes"])
        payload, _ = acquisition._page(response.body, resolved)
        assert set(payload["bars"]) == set(query["symbols"])
        assert all(len(bars) == min(80, len(resolved["required_sessions"])) for bars in payload["bars"].values())


@pytest.mark.parametrize("field,value", [("run_attempt", 2), ("run_number", 2),
                                         ("lifetime_status", "BLOCKED"), ("readiness_status", "NOT RUN"),
                                         ("checkout_sha", "d" * 40), ("manifest_sha256", "e" * 64)])
def test_wrong_revision_manifest_or_unapproved_repeat_stops_before_storage(run_setup, field, value):
    _, storage, record, _ = run_setup
    record[field] = value
    with pytest.raises(execution.ExecutionError):
        invoke(run_setup)
    assert not storage.exists()


@pytest.mark.parametrize("name,value", [("GITHUB_EVENT_NAME", "push"), ("GITHUB_REF", "refs/heads/other"),
                                       ("GITHUB_RUN_ATTEMPT", "2"), ("GITHUB_REPOSITORY", "other/repo")])
def test_wrong_runtime_identity_stops_before_storage(run_setup, monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(execution.ExecutionError, match="runtime_identity"):
        invoke(run_setup)
    assert not run_setup[1].exists()


def test_changed_manifest_and_missing_approval_fail_closed(run_setup):
    manifest, storage, _, approval = run_setup
    manifest["queries"][0]["limit"] = 101
    with pytest.raises(execution.ExecutionError, match="frozen_manifest"):
        invoke(run_setup)
    manifest["queries"][0]["limit"] = 100
    approval["retention_rights_basis"] = ""
    with pytest.raises(acquisition.AcquisitionError):
        invoke(run_setup)
    assert not storage.exists()


@pytest.mark.parametrize("mode", ["rehearsal", "offline"])
def test_provider_environment_forbidden_outside_real(run_setup, monkeypatch, mode):
    if mode == "offline":
        invoke(run_setup)
    monkeypatch.setenv("ALPACA_API_KEY", "sensitive-sentinel")
    with pytest.raises(execution.ExecutionError, match="provider_environment_forbidden"):
        invoke(run_setup, mode)


def test_absent_real_secret_creates_no_new_ledger(run_setup, monkeypatch):
    _, storage, record, _ = run_setup
    record.update(mode="real", run_number=2)
    monkeypatch.setenv("GITHUB_RUN_NUMBER", "2")
    monkeypatch.setattr(execution.signal, "SIGALRM", 14, raising=False)
    monkeypatch.setattr(acquisition, "AlpacaTransport", lambda: pytest.fail("provider touched"))
    with pytest.raises(execution.ExecutionError, match="provider_credentials_unavailable"):
        invoke(run_setup, "real")
    assert not storage.exists()


def test_preflight_without_secrets_is_non_mutating_and_offline_needs_no_new_approval(run_setup, monkeypatch):
    manifest, storage, record, approval = run_setup
    record.update(mode="real", run_number=2)
    monkeypatch.setenv("GITHUB_RUN_NUMBER", "2")
    monkeypatch.setattr(execution.signal, "SIGALRM", 14, raising=False)
    assert execution.preflight("real", manifest, storage, record, approval)[0] == storage
    assert not storage.exists()
    record.update(mode="rehearsal", run_number=1)
    monkeypatch.setenv("GITHUB_RUN_NUMBER", "1")
    invoke(run_setup)
    assert execution.execute("offline", manifest, storage, record)["status"] == "PASS"


def test_existing_or_recovered_storage_cannot_receive_fresh_allowance(run_setup):
    invoke(run_setup)
    before = rows(run_setup[1])
    with pytest.raises(execution.ExecutionError, match="cannot_resume_or_reset"):
        invoke(run_setup)
    assert rows(run_setup[1]) == before


def test_offline_missing_ledger_does_not_create_sqlite(run_setup):
    run_setup[1].mkdir()
    with pytest.raises(execution.ExecutionError, match="original_ledger_required"):
        invoke(run_setup, "offline")
    assert list(run_setup[1].iterdir()) == []


def test_offline_wrong_ledger_identity_is_read_only(run_setup):
    invoke(run_setup)
    with sqlite3.connect(run_setup[1] / "ledger.sqlite3") as db:
        db.execute("UPDATE metadata SET value='wrong' WHERE name='manifest_sha256'")
    before = (run_setup[1] / "ledger.sqlite3").read_bytes()
    with pytest.raises(execution.ExecutionError, match="original_ledger_identity"):
        invoke(run_setup, "offline")
    assert (run_setup[1] / "ledger.sqlite3").read_bytes() == before


@pytest.mark.parametrize("kind", ["git", "relative", "parent", "existing_empty"])
def test_unsafe_or_existing_storage_refused(tmp_path, kind):
    storage = tmp_path / "data"
    if kind == "git":
        (tmp_path / ".git").mkdir()
    elif kind == "relative":
        storage = Path("relative")
    elif kind == "parent":
        storage = tmp_path / "child" / ".." / "data"
    else:
        storage.mkdir()
    with pytest.raises(execution.ExecutionError):
        execution.validate_storage(storage, fresh=True)


def test_handled_transport_failure_retains_charged_partial_ledger_without_exception_leak(run_setup, monkeypatch, capsys):
    def failure(*_):
        print("sensitive-sentinel-stdout")
        raise RuntimeError("sensitive-sentinel-exception")
    monkeypatch.setattr(execution.SyntheticTransport, "__call__", failure)
    assert invoke(run_setup)["status"] == "BLOCKED"
    assert len(rows(run_setup[1])) == 2  # Existing one-retry policy remains charged.
    assert capsys.readouterr().out == ""
    diagnostic = (run_setup[1] / "execution-diagnostics.json").read_text()
    assert "sentinel" not in diagnostic
    assert json.loads(diagnostic)["ledger"]["request_slots_charged"] == 2
    assert invoke(run_setup, "offline")["status"] == "BLOCKED"
    assert len(rows(run_setup[1])) == 2


def test_deadline_during_reserved_transport_preserves_ambiguous_charge(run_setup, monkeypatch):
    def interrupted(*_):
        raise execution.ExecutionDeadline()
    monkeypatch.setattr(execution.SyntheticTransport, "__call__", interrupted)
    assert invoke(run_setup)["status"] == "BLOCKED"
    attempts = rows(run_setup[1])
    assert len(attempts) == 1 and attempts[0][2] == "reserved" and attempts[0][4] > 0
    with pytest.raises(execution.ExecutionError, match="cannot_resume_or_reset"):
        invoke(run_setup)


def test_cli_default_is_rehearsal_and_public_errors_are_constant(run_setup, tmp_path, monkeypatch, capsys):
    manifest, storage, record, approval = run_setup
    paths = []
    for name, value in (("manifest", manifest), ("execution", record), ("approval", approval)):
        path = tmp_path / (name + ".json")
        path.write_bytes(acquisition.encode(value))
        paths.extend(["--" + name, str(path)])
    paths.extend(["--storage", str(storage)])
    assert execution.main(paths) == 0
    assert json.loads(capsys.readouterr().out)["phase"] == "rehearsal"
    def failed(*_):
        raise RuntimeError("sensitive-sentinel")
    monkeypatch.setattr(execution, "execute", failed)
    assert execution.main(paths) == 2
    assert "sentinel" not in capsys.readouterr().out


def test_unknown_mode_never_creates_storage(run_setup):
    with pytest.raises(execution.ExecutionError, match="unsupported_mode"):
        invoke(run_setup, "resume")
    assert not run_setup[1].exists()


def test_duplicate_json_keys_are_rejected(tmp_path):
    path = tmp_path / "record.json"
    path.write_text('{"status":"PASS","status":"BLOCKED"}')
    with pytest.raises(execution.ExecutionError, match="invalid_document"):
        execution._json(path)


def test_junction_paths_are_rejected_before_resolution_and_offline_traversal(tmp_path, monkeypatch):
    target, junction = tmp_path / "outside", tmp_path / "junction"
    target.mkdir()
    if os.name == "nt":
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(target)],
                                capture_output=True, check=False)
        assert result.returncode == 0
    else:
        # Junction is a Windows-only filesystem type; keep its check executable
        # in Linux CI rather than silently skipping this platform boundary.
        junction.mkdir()
        monkeypatch.setattr(Path, "is_junction", lambda path: path == junction, raising=False)
    try:
        with pytest.raises(execution.ExecutionError, match="unsafe_storage"):
            execution.validate_storage(junction / "new", fresh=True)
        storage = tmp_path / "recovered"
        storage.mkdir()
        (storage / "ledger.sqlite3").touch()
        if os.name == "nt":
            child = storage / "pages"
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(child), str(target)],
                                    capture_output=True, check=False)
            assert result.returncode == 0
        else:
            child = junction
            storage = tmp_path
            (storage / "ledger.sqlite3").touch()
        try:
            with pytest.raises(execution.ExecutionError, match="unsafe_storage"):
                execution.validate_storage(storage, fresh=False)
        finally:
            if os.name == "nt":
                child.rmdir()
    finally:
        junction.rmdir()
