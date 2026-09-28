"""Entire synthetic HTTP -> frozen cache -> offline normalization/oracle chain."""
from datetime import date
from copy import deepcopy
import json
import socket

import pytest

from src import sessions
from tests.test_historical_acquisition import setup, response, bar
from tools.historical_acquisition import encode
from tools.historical_reconcile import network_blocked, reconcile


def prepare(manifest):
    query = deepcopy(manifest["queries"][0])
    query["id"] = "bulk"
    query["scope"] = "bulk"
    query["target_session"] = "2026-09-25"
    query["start"] = "2026-06-01T04:00:00Z"
    query["required_sessions"] = [str(x) for x in sessions.dates(date(2026,6,1), date(2026,9,25))]
    manifest["queries"].append(query)
    return query


def probe_response():
    return response({s: [bar("2026-09-24"), bar("2026-09-25")] for s in ("AAA", "BBB", "SPY")})


def test_complete_synthetic_chain_does_not_authorize_reader_or_publish(setup):
    manifest, approval, root, clock, build = setup
    query = prepare(manifest)
    rows = [bar(d, c=10, h=11) for d in query["required_sessions"]]
    runner, transport = build([probe_response(), response({"AAA": rows, "BBB": rows, "SPY": rows})])
    runner.run("canonical")
    runner.run("bulk")
    acquired_calls = len(transport.calls)
    result = reconcile(manifest, root, "2026-09-25")
    assert result["status"] == "PASS"
    assert result["complete_required_input_windows"]
    assert result["new_provider_requests"] == 0 and len(transport.calls) == acquired_calls
    output = json.loads((root / "reconciliation-2026-09-25.json").read_bytes())
    assert output["B"]["status"] == "BLOCKED"
    assert output["C"]["status"] == output["D"]["status"] == "PASS"
    assert not output["publication_allowed"] and output["reader_actionability"] == "unknown"
    assert output["C"]["reference"]["intended"] == ["AAA", "BBB"]
    assert len(output["C"]["reference"]["events"]) == 20


def test_interrupted_chain_is_blocked_not_a_smaller_population(setup):
    manifest, approval, root, clock, build = setup
    query = prepare(manifest)
    runner, transport = build([probe_response(), response(token="next"), response(status=403)])
    runner.run("canonical")
    with pytest.raises(Exception, match="terminal_http_failure"):
        runner.run("bulk")
    result = reconcile(manifest, root, "2026-09-25")
    assert result["status"] == "BLOCKED"
    output = json.loads((root / "reconciliation-2026-09-25.json").read_bytes())
    assert output["C"]["status"] == output["D"]["status"] == "BLOCKED"
    assert output["symbol_manifest"]["BBB"]["status"] == "failed"


def test_changed_manifest_or_wire_page_cannot_replay_as_original(setup):
    manifest, approval, root, clock, build = setup
    prepare(manifest)
    runner, _ = build([probe_response(), response()]); runner.run("canonical"); runner.run("bulk")
    for page_path in (root / "pages").glob("*.json"):
        page_path.write_bytes(page_path.read_bytes() + b" ")
    with pytest.raises(Exception, match="cached_page_hash_mismatch"):
        reconcile(manifest, root, "2026-09-25")


def test_network_guard_blocks_socket_attempt_and_restores_outer_guard():
    previous = socket.create_connection
    with network_blocked():
        with pytest.raises(RuntimeError, match="reconciliation network"):
            socket.create_connection(("example.invalid", 443))
    assert socket.create_connection is previous
