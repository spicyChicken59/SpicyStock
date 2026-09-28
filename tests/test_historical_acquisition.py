"""Synthetic HTTP boundary tests; conftest additionally disables real sockets."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

import pytest

from tools import historical_acquisition as acquisition


class Clock:
    def __init__(self):
        self.now = datetime(2026, 9, 28, tzinfo=timezone.utc).timestamp()
        self.waits = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.now += seconds


class Transport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, params, limit):
        self.calls.append((dict(params), limit))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def bar(day="2026-09-24", **changes):
    return {"t": day + "T04:00:00Z", "o": 10, "h": 12, "l": 9, "c": 11,
            "v": 1000, **changes}


def response(bars=None, token=None, status=200, headers=None):
    return acquisition.HTTPResult(status, headers or {}, acquisition.encode({
        "bars": {"AAA": [bar()]} if bars is None else bars, "next_page_token": token}))


@pytest.fixture
def setup(tmp_path):
    populations = {day: {"symbols": ["AAA", "BBB"],
                         "sha256": acquisition.symbols_digest(["AAA", "BBB"])}
                   for day in ("2026-09-24", "2026-09-25")}
    manifest = {
        "schema": acquisition.SCHEMA, "assignment_id": acquisition.ASSIGNMENT,
        "populations": populations,
        "queries": [{"id": "canonical", "symbols": ["AAA", "BBB", "SPY"],
            "start": "2026-09-24T04:00:00Z", "end": "2026-09-25T23:59:59Z",
            "asof": "2026-09-26", "feed": "sip", "timeframe": "1Day",
            "adjustment": "split", "currency": "USD", "limit": 10000,
            "sort": "asc", "purpose": "canonical", "scope": "probe",
            "required_sessions": ["2026-09-24", "2026-09-25"]}],
        "limits": {"requests": 400, "retained_bytes": 1024 ** 3,
                   "requests_per_minute": 20, "page_bytes": 1024 * 1024},
        "documentation": {"verified_at": "2026-09-28T12:00:00Z",
            "stockbars_url": "https://docs.alpaca.markets/us/reference/stockbars",
            "faq_url": "https://docs.alpaca.markets/us/docs/market-data-faq"}}
    root = tmp_path / "private-synthetic-storage"
    approval = {"assignment_id": acquisition.ASSIGNMENT,
        "manifest_sha256": acquisition.digest(acquisition.encode(manifest)),
        "storage_root": str(root), "zero_additional_cost": True,
        "cost_basis": "synthetic offline test; no provider usage",
        "sip_daily_entitlement_basis": "synthetic test only",
        "non_public_storage": True, "retention_rights_basis": "invented synthetic rows",
        "reviewer_retrieval_path": "test fixture regenerated locally",
        "approved_by": "synthetic test", "provider_requests_per_minute": 20}
    clock = Clock()

    def build(responses, **kwargs):
        approval["manifest_sha256"] = acquisition.digest(acquisition.encode(manifest))
        transport = Transport(responses)
        runner = acquisition.Acquisition(manifest, approval, root, transport=transport,
                                          clock=clock, sleep=clock.sleep, **kwargs)
        return runner, transport

    return manifest, approval, root, clock, build


def ledger(root):
    with sqlite3.connect(root / "ledger.sqlite3") as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute("SELECT * FROM attempts ORDER BY id")]


def test_terminal_pages_resume_without_requests_and_offline_export(setup, monkeypatch):
    manifest, approval, root, clock, build = setup
    runner, transport = build([response(token="page-two"), response({"AAA": [bar("2026-09-25")], "SPY": [bar()]})])
    report = runner.run("canonical")
    assert report["pagination_complete"] is True
    assert report["symbols"]["AAA"]["state"] == "returned_with_bars"
    assert report["symbols"]["BBB"]["state"] == "absent"
    assert report["symbols"]["SPY"]["state"] == "partial"
    assert transport.calls[1][0]["page_token"] == "page-two"
    assert all(call[0]["asof"] == "2026-09-26" for call in transport.calls)
    assert report["ledger"]["request_slots_charged"] == 2
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    replay = acquisition.Acquisition(manifest, approval, root).run("canonical")
    assert replay == report
    exported = acquisition.cached_pages(manifest, root, "canonical")
    assert exported["terminal"] is True
    assert len(exported["pages"]) == 2
    assert exported["pages"][0]["query"]["adjustment"] == "split"
    assert acquisition.digest(exported["pages"][0]["raw"]) == exported["pages"][0]["sha256"]


@pytest.mark.parametrize("changes,reason", [
    ({"feed": "iex"}, "noncanonical"), ({"timeframe": "1Min"}, "noncanonical"),
    ({"currency": "EUR"}, "noncanonical"), ({"asof": None}, "asof"),
    ({"symbols": ["AAA", "ZZZ"]}, "outside_retained_union"),
    ({"start": "2025-07-31T04:00:00Z"}, "date_envelope"),
    ({"end": "2026-09-26T04:00:00Z"}, "date_envelope"),
    ({"adjustment": "all"}, "adjustment"),
    ({"adjustment": "raw"}, "undeclared_raw"),
    ({"purpose": "alternate_asof_discrepancy"}, "concrete_discrepancy"),
])
def test_manifest_rejects_scope_expansion_before_transport(setup, changes, reason):
    manifest, _, root, _, build = setup
    manifest["queries"][0].update(changes)
    with pytest.raises(acquisition.AcquisitionError, match=reason):
        build([response()])
    assert not root.exists()


@pytest.mark.parametrize("field,value,reason", [
    ("requests", 401, "request_cap"), ("retained_bytes", 1024 ** 3 + 1, "byte_cap"),
    ("requests_per_minute", 21, "rate_out"), ("requests", True, "request_cap"),
])
def test_hard_ceilings_cannot_be_raised(setup, field, value, reason):
    manifest, _, _, _, build = setup
    manifest["limits"][field] = value
    with pytest.raises(acquisition.AcquisitionError, match=reason):
        build([])


def test_population_hash_tampering_blocks(setup):
    manifest, _, _, _, build = setup
    manifest["populations"]["2026-09-24"]["symbols"].append("ZZZ")
    with pytest.raises(acquisition.AcquisitionError, match="population_hash"):
        build([])


@pytest.mark.parametrize("field,value", [
    ("zero_additional_cost", False), ("non_public_storage", False),
    ("cost_basis", ""), ("sip_daily_entitlement_basis", ""),
    ("retention_rights_basis", ""), ("reviewer_retrieval_path", ""),
    ("approved_by", ""), ("provider_requests_per_minute", None),
])
def test_unestablished_rights_cost_entitlement_and_storage_stop_offline(setup, field, value):
    _, approval, root, _, build = setup
    approval[field] = value
    with pytest.raises(acquisition.AcquisitionError):
        build([])
    assert not root.exists()


def test_raw_storage_inside_git_rejected(setup):
    manifest, approval, _, _, _ = setup
    approval["storage_root"] = str(acquisition.REPO / "work")
    with pytest.raises(acquisition.AcquisitionError, match="outside_git"):
        acquisition.Acquisition(manifest, approval, approval["storage_root"])


def test_one_transient_retry_respects_retry_after_and_shared_ledger(setup):
    _, _, root, clock, build = setup
    runner, transport = build([response(status=429, headers={"Retry-After": "12"}), response()])
    report = runner.run("canonical")
    assert len(transport.calls) == 2
    assert sum(clock.waits) == 12
    rows = ledger(root)
    assert [row["attempt"] for row in rows] == [1, 2]
    assert rows[0]["retained"] == 0
    assert report["ledger"]["request_slots_charged"] == 2


def test_second_transient_failure_is_terminal_across_restarts(setup):
    _, _, root, _, build = setup
    runner, transport = build([response(status=503), response(status=503), response()])
    with pytest.raises(acquisition.AcquisitionError, match="transient_http"):
        runner.run("canonical")
    resumed, later = build([response()])
    with pytest.raises(acquisition.AcquisitionError, match="transient_http"):
        resumed.run("canonical")
    assert len(transport.calls) == 2
    assert not later.calls
    assert len(ledger(root)) == 2


@pytest.mark.parametrize("status", [301, 302, 307, 400, 401, 403, 404, 422])
def test_auth_entitlement_invalid_parameter_redirect_are_not_retried(setup, status):
    _, _, root, _, build = setup
    runner, transport = build([response(status=status), response()])
    with pytest.raises(acquisition.AcquisitionError, match="terminal_http"):
        runner.run("canonical")
    assert len(transport.calls) == 1
    assert ledger(root)[0]["http_status"] == status
    assert not list((root / "pages").iterdir())


def test_request_cap_shared_by_queries_and_restarts(setup):
    manifest, _, root, _, build = setup
    manifest["limits"]["requests"] = 2
    query = deepcopy(manifest["queries"][0])
    query["id"] = "other_mapping"
    query["scope"] = "bulk"
    query["asof"] = "2026-09-25"
    manifest["queries"].append(query)
    complete_probe = response({s: [bar(), bar("2026-09-25")] for s in query["symbols"]})
    runner, transport = build([complete_probe, response(status=503), response()])
    runner.run("canonical")
    with pytest.raises(acquisition.AcquisitionError, match="request_cap"):
        runner.run("other_mapping")
    resumed, later = build([response()])
    with pytest.raises(acquisition.AcquisitionError, match="request_cap"):
        resumed.run("other_mapping")
    assert len(transport.calls) == len(ledger(root)) == 2
    assert not later.calls
    export = acquisition.cached_pages(manifest, root, "other_mapping")
    assert export["terminal"] is False
    assert len(export["pages"]) == 0


def test_shared_uncompressed_byte_cap_never_overretains(setup):
    manifest, _, root, _, build = setup
    first = response(token="next")
    manifest["limits"]["retained_bytes"] = len(first.body) + 5
    runner, transport = build([first, response({"BBB": [bar()]})])
    with pytest.raises(acquisition.AcquisitionError, match="byte_limit"):
        runner.run("canonical")
    assert transport.calls[1][1] == 5
    assert sum(p.stat().st_size for p in (root / "pages").iterdir()) == len(first.body)
    assert sum(row["retained"] + row["reservation"] for row in ledger(root)) <= manifest["limits"]["retained_bytes"]


def test_crash_reservation_persists_and_prevents_ambiguous_redownload(setup):
    manifest, _, root, _, build = setup
    runner, transport = build([KeyboardInterrupt()])
    with pytest.raises(KeyboardInterrupt):
        runner.run("canonical")
    rows = ledger(root)
    assert rows[0]["status"] == "reserved"
    assert rows[0]["reservation"] == manifest["limits"]["page_bytes"]
    resumed, later = build([response()])
    with pytest.raises(acquisition.AcquisitionError, match="ambiguous_interrupted"):
        resumed.run("canonical")
    assert not later.calls
    assert len(ledger(root)) == 1


def test_cached_first_page_reused_after_transient_interruption(setup):
    manifest, _, root, _, build = setup
    runner, transport = build([response(token="next"), KeyboardInterrupt()])
    with pytest.raises(KeyboardInterrupt):
        runner.run("canonical")
    export = acquisition.cached_pages(manifest, root, "canonical")
    assert export["terminal"] is False
    assert len(export["pages"]) == 1
    assert export["failures"][0]["status"] == "reserved"
    assert export["ledger"]["request_slots_charged"] == 2


def test_same_manifest_identity_required_across_restarts(setup):
    manifest, _, _, _, build = setup
    runner, _ = build([response()])
    runner.run("canonical")
    manifest["queries"][0]["asof"] = "2026-09-25"
    resumed, transport = build([response()])
    with pytest.raises(acquisition.AcquisitionError, match="frozen_manifest_changed"):
        resumed.run("canonical")
    assert not transport.calls


def test_lower_provider_rate_applies_to_retry_and_persists(setup):
    manifest, approval, root, clock, build = setup
    runner, _ = build([response(status=429, headers={"X-RateLimit-Limit": "1"}), response()])
    runner.run("canonical")
    assert sum(clock.waits) >= 60
    assert ledger(root)[1]["timestamp"] - ledger(root)[0]["timestamp"] >= 60


@pytest.mark.parametrize("responses,reason", [
    ([response(token="x"), response({"BBB": [bar()]}, token="x")], "pagination_cycle"),
    ([response(token="x"), response(token="y")], "duplicate_page"),
    ([acquisition.HTTPResult(200, {}, b'{"bars":{}}')], "missing_terminal_token"),
])
def test_partial_cycle_duplicate_pages_never_report_complete(setup, responses, reason):
    manifest, _, root, _, build = setup
    runner, transport = build(responses)
    with pytest.raises(acquisition.AcquisitionError, match=reason):
        runner.run("canonical")
    assert not (root / "canonical-manifest.json").exists()
    exported = acquisition.cached_pages(manifest, root, "canonical")
    assert exported["terminal"] is False
    assert reason in exported["pagination_problem"]


@pytest.mark.parametrize("bars,reason", [
    ({"ZZZ": [bar()]}, "unexpected_symbol"),
    ({"AAA": [bar(t="2026-09-24T05:00:00Z")]}, "wrong_daily_session"),
    ({"AAA": [bar(t="2026-09-23T04:00:00Z")]}, "wrong_daily_session"),
    ({"AAA": [bar(v=-1)]}, "invalid_price_or_volume"),
    ({"AAA": [bar(c=0)]}, "invalid_price_or_volume"),
    ({"AAA": [bar(h=8)]}, "invalid_ohlc_geometry"),
    ({"AAA": [bar(c="11")]}, "malformed_numeric"),
    ({"AAA": [bar(v=True)]}, "malformed_numeric"),
])
def test_wrong_symbol_session_numeric_values_retained_but_quarantined(setup, bars, reason):
    manifest, _, root, _, build = setup
    original = response(bars)
    runner, _ = build([original])
    with pytest.raises(acquisition.AcquisitionError, match=reason):
        runner.run("canonical")
    rows = ledger(root)
    assert rows[0]["status"] == "failed"
    assert (root / "pages" / (rows[0]["body_hash"] + ".json")).read_bytes() == original.body
    assert acquisition.cached_pages(manifest, root, "canonical")["terminal"] is False


def test_duplicate_rows_preserve_raw_and_record_deterministic_last_selection(setup):
    _, _, root, _, build = setup
    original = response({"AAA": [bar(), bar(v=1500), bar("2026-09-25")]})
    runner, _ = build([original])
    report = runner.run("canonical")
    assert report["symbols"]["AAA"]["rows"] == 3
    assert len(report["duplicate_operations"]) == 1
    operation = report["duplicate_operations"][0]
    assert operation["previous"]["row_index"] == 0
    assert operation["selected"]["row_index"] == 1
    assert (root / "pages" / (report["pages"][0]["sha256"] + ".json")).read_bytes() == original.body


def test_cached_body_tampering_blocks_without_http(setup):
    manifest, _, root, _, build = setup
    runner, _ = build([response()])
    report = runner.run("canonical")
    (root / "pages" / (report["pages"][0]["sha256"] + ".json")).write_bytes(b"changed")
    resumed, transport = build([])
    with pytest.raises(acquisition.AcquisitionError, match="cached_page_hash"):
        resumed.run("canonical")
    with pytest.raises(acquisition.AcquisitionError, match="cached_page_hash"):
        acquisition.cached_pages(manifest, root, "canonical")
    assert not transport.calls


def test_single_process_lock_blocks_second_acquisition(setup):
    _, _, root, _, build = setup
    root.mkdir()
    with acquisition.exclusive_lock(root / "acquisition.lock"):
        runner, transport = build([response()])
        with pytest.raises(acquisition.AcquisitionError, match="another_acquisition"):
            runner.run("canonical")
        assert not transport.calls


def test_transport_exception_details_and_nonallowlisted_headers_never_persist(setup):
    _, _, root, _, build = setup
    secret = "SYNTHETIC_DO_NOT_LOG"
    runner, _ = build([RuntimeError("URL?secret=" + secret), response(headers={
        "Set-Cookie": secret, "Authorization": secret, "X-Request-ID": "safe-request"})])
    runner.run("canonical")
    assert secret.encode() not in (root / "ledger.sqlite3").read_bytes()
    headers = json.loads(ledger(root)[1]["headers"])
    assert headers == {"x-request-id": "safe-request"}
    assert acquisition.safe_headers({"X-Request-ID": secret, "Set-Cookie": secret}, (secret,)) == {
        "x-request-id": "[redacted]"}


def test_missing_secure_runtime_credentials_blocks_before_request_reservation(setup, monkeypatch):
    manifest, approval, root, _, _ = setup
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    with pytest.raises(acquisition.AcquisitionError, match="secure_runtime_credentials"):
        acquisition.Acquisition(manifest, approval, root).run("canonical")
    assert ledger(root) == []


def test_cli_defaults_to_offline_and_never_uses_credentials(setup, tmp_path, monkeypatch, capsys):
    manifest, _, root, _, _ = setup
    path = tmp_path / "manifest.json"
    path.write_bytes(acquisition.encode(manifest))
    monkeypatch.setattr(acquisition, "AlpacaTransport", lambda: pytest.fail("offline CLI reached transport"))
    assert acquisition.main(["--manifest", str(path)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["provider_requests"] == 0
    assert output["acquisition"] == "NOT RUN"
    assert output["validation"] == "PASS"
    assert not root.exists()


def test_exhausted_shared_provider_quota_waits_for_reset(setup):
    _, _, root, clock, build = setup
    reset = clock.now + 90
    runner, _ = build([response(token="next", headers={
        "X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(int(reset))}),
        response({"BBB": [bar()]})])
    runner.run("canonical")
    assert sum(clock.waits) >= 90
    assert ledger(root)[1]["timestamp"] >= reset


@pytest.mark.parametrize("headers,reason", [
    ({"Retry-After": "invalid"}, "invalid_retry_after"),
    ({"X-RateLimit-Remaining": "0"}, "invalid_rate_limit_reset"),
    ({"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "invalid"}, "invalid_rate_limit_reset"),
])
def test_bad_rate_metadata_stops_even_successful_page(setup, headers, reason):
    _, _, root, _, build = setup
    runner, transport = build([response(token="next", headers=headers), response()])
    with pytest.raises(acquisition.AcquisitionError, match=reason):
        runner.run("canonical")
    assert len(transport.calls) == 1
    assert ledger(root)[0]["status"] == "failed"


def test_frozen_shared_session_reference_is_resolved_without_hash_changes(setup):
    manifest, _, root, _, build = setup
    query = manifest["queries"][0]
    manifest["required_sessions"] = {"target": query.pop("required_sessions")}
    query["required_sessions_ref"] = "target"
    identity = acquisition.digest(acquisition.encode(manifest))
    runner, _ = build([response()])
    runner.run("canonical")
    exported = acquisition.cached_pages(manifest, root, "canonical")
    assert exported["pages"][0]["query"]["required_sessions"] == ["2026-09-24", "2026-09-25"]
    assert exported["manifest_sha256"] == identity
    assert acquisition.digest(acquisition.encode(manifest)) == identity


def test_omitted_frozen_exchange_sessions_rejected(setup):
    manifest, _, _, _, build = setup
    del manifest["queries"][0]["required_sessions"]
    with pytest.raises(acquisition.AcquisitionError, match="invalid_required_sessions"):
        build([])


def test_real_transport_fixed_endpoint_identity_encoding_and_credential_echo_block(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "synthetic-runtime-id")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "synthetic-runtime-secret")
    seen = []

    class HTTPResponse:
        status = 200

        def getheaders(self):
            return [("X-Request-ID", "safe"), ("Set-Cookie", "private")]

        def getheader(self, name, default):
            return default

        def read(self, limit):
            return b'{"echo":"synthetic-runtime-secret"}'

    class HTTPSConnection:
        def __init__(self, host, **kwargs):
            assert host == "data.alpaca.markets"

        def request(self, method, path, headers):
            seen.append((method, path, headers))

        def getresponse(self):
            return HTTPResponse()

        def close(self):
            pass

    monkeypatch.setattr(acquisition.http.client, "HTTPSConnection", HTTPSConnection)
    transport = acquisition.AlpacaTransport()
    with pytest.raises(acquisition.AcquisitionError, match="credential_echo_detected"):
        transport({"symbols": "AAA", "asof": "2026-09-26"}, 1000)
    assert len(seen) == 1
    assert seen[0][0] == "GET"
    assert seen[0][1].startswith("/v2/stocks/bars?")
    assert seen[0][2]["Accept-Encoding"] == "identity"


def test_credential_echo_is_terminal_and_body_never_retained(setup):
    _, _, root, _, build = setup
    runner, transport = build([acquisition.AcquisitionError("credential_echo_detected"), response()])
    with pytest.raises(acquisition.AcquisitionError, match="credential_echo_detected"):
        runner.run("canonical")
    assert len(transport.calls) == 1
    assert not list((root / "pages").iterdir())
    assert ledger(root)[0]["retained"] == 0


@pytest.mark.parametrize("probe_present", [False, True])
def test_bulk_requires_successful_small_probe_with_required_bars(setup, probe_present):
    manifest, _, root, _, build = setup
    bulk = deepcopy(manifest["queries"][0])
    bulk.update(id="bulk", scope="bulk")
    manifest["queries"].append(bulk)
    runner, transport = build([response(), response()])
    if probe_present:
        runner.run("canonical")
    with pytest.raises(acquisition.AcquisitionError, match="access_probe"):
        runner.run("bulk")
    assert len(transport.calls) == int(probe_present)


def test_complete_probe_allows_bulk_and_counts_against_shared_cap(setup):
    manifest, _, root, _, build = setup
    bulk = deepcopy(manifest["queries"][0])
    bulk.update(id="bulk", scope="bulk")
    manifest["queries"].append(bulk)
    rows = {s: [bar(), bar("2026-09-25")] for s in bulk["symbols"]}
    runner, transport = build([response(rows), response(rows)])
    runner.run("canonical")
    result = runner.run("bulk")
    assert result["ledger"]["request_slots_charged"] == 2
    assert len(transport.calls) == 2


@pytest.mark.parametrize("status", [401, 403])
def test_auth_and_entitlement_failures_stop_other_queries_across_restarts(setup, status):
    manifest, _, _, _, build = setup
    bulk = deepcopy(manifest["queries"][0])
    bulk.update(id="bulk", scope="bulk")
    manifest["queries"].append(bulk)
    complete = {s: [bar(), bar("2026-09-25")] for s in bulk["symbols"]}
    runner, transport = build([response(complete), response(status=status)])
    runner.run("canonical")
    with pytest.raises(acquisition.AcquisitionError, match="terminal_http"):
        runner.run("bulk")
    resumed, later = build([response()])
    with pytest.raises(acquisition.AcquisitionError, match="authentication_or_entitlement"):
        resumed.run("canonical")
    assert not later.calls


def test_duplicate_json_object_members_are_quarantined_not_silently_discarded(setup):
    _, _, root, _, build = setup
    raw = b'{"bars":{"AAA":[],"AAA":[]},"next_page_token":null}'
    runner, transport = build([acquisition.HTTPResult(200, {}, raw)])
    with pytest.raises(acquisition.AcquisitionError, match="malformed_json"):
        runner.run("canonical")
    assert len(transport.calls) == 1
    assert (root / "pages" / (acquisition.digest(raw) + ".json")).read_bytes() == raw


def test_run_all_holds_one_lock_runs_manifest_order_and_resumes_cache(setup, monkeypatch):
    manifest, _, root, _, build = setup
    bulk = deepcopy(manifest["queries"][0])
    bulk.update(id="bulk", scope="bulk")
    manifest["queries"].append(bulk)
    rows = {s: [bar(), bar("2026-09-25")] for s in bulk["symbols"]}
    runner, transport = build([response(rows), response(rows)])
    seen = []
    original = runner._run_query

    def locked_query(query):
        with pytest.raises(acquisition.AcquisitionError, match="another_acquisition"):
            with acquisition.exclusive_lock(root / "acquisition.lock"):
                pytest.fail("whole-process lock was released between queries")
        seen.append(query["id"])
        return original(query)

    monkeypatch.setattr(runner, "_run_query", locked_query)
    reports = runner.run_all()
    assert seen == ["canonical", "bulk"]
    assert reports[-1]["ledger"]["request_slots_charged"] == 2
    runner.run_all()
    assert len(transport.calls) == 2


def test_run_all_stops_first_failure_without_later_query_request(setup):
    manifest, _, root, _, build = setup
    bulk = deepcopy(manifest["queries"][0])
    bulk.update(id="bulk", scope="bulk")
    manifest["queries"].append(bulk)
    runner, transport = build([response(status=403), response()])
    with pytest.raises(acquisition.AcquisitionError, match="terminal_http"):
        runner.run_all()
    assert len(transport.calls) == 1
    assert len(ledger(root)) == 1


def test_cli_all_and_query_are_mutually_exclusive(setup, tmp_path):
    manifest, _, _, _, _ = setup
    path = tmp_path / "manifest.json"
    path.write_bytes(acquisition.encode(manifest))
    with pytest.raises(SystemExit) as error:
        acquisition.main(["--manifest", str(path), "--all", "--query", "canonical"])
    assert error.value.code == 2


def test_cli_all_uses_shared_runner_without_live_transport(setup, tmp_path, monkeypatch, capsys):
    manifest, approval, _, _, _ = setup
    manifest_path, approval_path = tmp_path / "manifest.json", tmp_path / "approval.json"
    manifest_path.write_bytes(acquisition.encode(manifest))
    approval_path.write_bytes(acquisition.encode(approval))
    called = []

    class Runner:
        def __init__(self, supplied_manifest, supplied_approval, root):
            assert supplied_manifest == manifest
            assert supplied_approval == approval

        def run_all(self):
            called.append("all")
            return [{"query_id": "canonical", "ledger": {"request_slots_charged": 1}}]

    monkeypatch.setattr(acquisition, "Acquisition", Runner)
    assert acquisition.main(["--manifest", str(manifest_path), "--approval", str(approval_path),
                             "--acquire", "--all"]) == 0
    assert called == ["all"]
    assert json.loads(capsys.readouterr().out)["request_slots_charged"] == 1
