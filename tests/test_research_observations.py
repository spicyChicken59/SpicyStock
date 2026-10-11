"""A dated research observation can describe a cohort row; it can never size, admit or quote it as current."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from src import morning, research_observations as observations, stop_research

ROOT = Path(__file__).resolve().parents[1]
STOP = ROOT / "tests/fixtures/stop-research"
FIXTURES = ROOT / "tests/fixtures/research-observations"
spec = importlib.util.spec_from_file_location("research_observation_fixture", FIXTURES / "generate.py")
generate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generate)
NOW, Client = generate.NOW, generate.Client


def source(name="current"):
    publication = gzip.decompress((STOP / (name + "-publication.json.gz")).read_bytes())
    return publication, (STOP / (name + "-receipt.json")).read_bytes(), (STOP / (name + "-bundle.json")).read_bytes()


def fixture(name):
    return json.loads((FIXTURES / (name + ".json")).read_bytes())


DEFAULT = object()


def collect(name="current", *, client=DEFAULT, clock=None, **kwargs):
    publication, receipt, bundle = source(name)
    return observations.collect(publication, kwargs.pop("receipt", receipt), kwargs.pop("bundle", bundle),
                                client=Client() if client is DEFAULT else client, clock=clock or (lambda: NOW),
                                observation_run_id=kwargs.pop("observation_run_id", "test"), **kwargs)


def test_only_the_bound_cohorts_allocation_fits_get_one_iex_request():
    client = Client()
    out = collect(client=client)
    assert out["status"] == "observed" and out["reason"] is None
    assert [(r["ticker"], r["rank"]) for r in out["rows"]] == [("KE", 2), ("PSNL", 5)]
    assert [(r.feed.value, list(r.symbol_or_symbols)) for r in client.requests] == [("iex", ["KE", "PSNL"])]
    assert out["source"]["requests"] == 1 == observations.MAX_REQUESTS and out["source"]["scope"] == "single_venue"
    bundle = json.loads(source()[2])
    by_ticker = {row["ticker"]: row for row in bundle["rows"]}
    for row in out["rows"]:
        original = by_ticker[row["ticker"]]
        assert original["research"]["allocation_fit"] and row["evidence"] == original["evidence"]
        assert row["projection_sha256"] == original["research"]["projection_sha256"]
        assert row["levels"] == {"trigger": original["levels"]["trigger"], "limit": original["levels"]["limit"],
                                 "stop": original["levels"]["stop"], "entry_low": original["levels"]["trigger"], "day2_spent_above": None}
        assert row["kind"] == "anticipation" and row["event"] == original["event"]
    assert {r["ticker"] for r in out["rows"]}.isdisjoint({"MG", "ZIM", "SN"})
    assert out["rows"][0]["price_checks"] == {"trade": "below_entry_floor", "ask": "below_entry_floor"}
    assert out["rows"][1]["price_checks"] == {"trade": "within_published_band", "ask": "within_published_band"}
    assert out["rows"][0]["quote"]["spread_usd"] == 0.04 and out["coverage"]["halts"] == "not_checked"
    assert out["cohort"]["bound"] is True and out["cohort"]["receipt_sha256"] == hashlib.sha256(source()[1]).hexdigest()
    forbidden = {"shares", "principal_usd", "risk_usd", "order_json", "order_line", "quantity", "ready"}
    def scan(value):
        if isinstance(value, dict):
            assert not forbidden & value.keys(), value.keys()
            for v in value.values(): scan(v)
        elif isinstance(value, list):
            for v in value: scan(v)
    scan(out)


def test_the_fixtures_are_the_collectors_own_output():
    for name, body in generate.build().items():
        assert (FIXTURES / name).read_bytes() == body, name
    assert fixture("observed") == collect(observation_run_id="synthetic-observed")


@pytest.mark.parametrize("name,clock,status,reason", [
    ("current", NOW.replace(hour=12, minute=30), "inapplicable", "before_collection_window"),
    ("current", NOW.replace(hour=14), "inapplicable", "entry_window_ended"),
    ("current", NOW + timedelta(days=1), "inapplicable", "wrong_session"),
    ("red", NOW, "no_research_rows", None),
    ("empty", NOW, "no_research_rows", None),
    ("outside", datetime(2026, 9, 11, 13, 20, tzinfo=timezone.utc), "no_research_rows", None),
])
def test_guards_and_fit_free_cohorts_spend_no_provider_call(name, clock, status, reason):
    client = Client()
    out = collect(name, client=client, clock=lambda: clock)
    assert (out["status"], out["reason"], out["rows"]) == (status, reason, [])
    assert client.requests == [] and out["source"] == observations._source()


def test_a_missing_or_foreign_cohort_is_named_and_spends_nothing():
    client = Client()
    missing = collect(client=client, receipt=None, bundle=None)
    assert (missing["status"], missing["reason"], missing["cohort"]) == ("inapplicable", "cohort_missing", None)
    _, red_receipt, red_bundle = source("red")
    foreign = collect(client=client, receipt=red_receipt, bundle=red_bundle)
    assert (foreign["status"], foreign["reason"], foreign["cohort"]["bound"]) == ("inapplicable", "cohort_not_current", False)
    assert foreign["cohort"]["receipt_sha256"] == hashlib.sha256(red_receipt).hexdigest()
    assert client.requests == []
    with pytest.raises(ValueError, match="without its receipt"):
        collect(receipt=None, bundle=red_bundle)


def test_stale_crossed_future_and_wrong_session_prints_cannot_read_as_current():
    out = collect(client=Client(edit=generate.stale_and_crossed))
    rows = {r["ticker"]: r for r in out["rows"]}
    assert out["status"] == "partial"
    assert rows["KE"]["quote"]["status"] == "invalid" and rows["KE"]["price_checks"]["ask"] == "unknown"
    assert rows["PSNL"]["trade"]["status"] == "stale" and rows["PSNL"]["price_checks"]["trade"] == "unknown"
    def future(result):
        result["KE"]["latest_quote"]["timestamp"] = NOW + timedelta(seconds=10)
    assert {r["ticker"]: r["quote"]["status"] for r in collect(client=Client(edit=future))["rows"]}["KE"] == "invalid"
    def yesterday(result):
        for symbol in result:
            result[symbol]["latest_quote"]["timestamp"] -= timedelta(days=1)
            result[symbol]["latest_trade"]["timestamp"] -= timedelta(days=1)
    stale = collect(client=Client(edit=yesterday))
    assert stale["status"] == "partial" and all(r["price_checks"] == {"trade": "unknown", "ask": "unknown"} for r in stale["rows"])


def test_one_current_row_beside_a_stale_one_is_partial_not_observed():
    # Only PSNL's print is a minute old; KE's quote and trade are both recent. The status reads
    # every row, so one fully recent row cannot carry the whole observation to "observed".
    def stale_psnl_only(result):
        result["PSNL"]["latest_trade"]["timestamp"] = NOW - timedelta(seconds=61)
    out = collect(client=Client(edit=stale_psnl_only))
    rows = {r["ticker"]: r for r in out["rows"]}
    assert rows["KE"]["trade"]["status"] == rows["KE"]["quote"]["status"] == "recent"
    assert rows["PSNL"]["trade"]["status"] == "stale" and rows["PSNL"]["quote"]["status"] == "recent"
    assert out["status"] == "partial"
    observations.validate_observation(out, *source())


def test_outage_and_missing_credentials_keep_no_price_and_leak_nothing(monkeypatch):
    client = Client(errors=("iex",))
    out = collect(client=client)
    assert out["status"] == "provider_unavailable" and out["source"]["requests"] == 1 and len(client.requests) == 1
    assert all(r["quote"]["status"] == r["trade"]["status"] == "unavailable" for r in out["rows"])
    assert "api-key-secret" not in json.dumps(out)
    monkeypatch.setenv("ALPACA_API_KEY", "")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "")
    monkeypatch.setattr(observations.market_data, "get_clients", lambda: pytest.fail("client should not be constructed"))
    none = collect(client=None)
    assert none["status"] == "provider_unavailable" and none["source"]["error_kind"] == "missing_credentials"
    assert none["source"]["requests"] == 0


def test_the_request_budget_is_one_snapshot_per_run():
    assert observations.POLICY["max_requests_per_run"] == observations.MAX_REQUESTS == 1
    out = collect()
    out["source"]["requests"] = 2
    with pytest.raises(ValueError, match="request budget"):
        observations.validate_observation(out, *source())


@pytest.mark.parametrize("change", [
    lambda out: out["rows"].append(deepcopy(out["rows"][0])),
    lambda out: out["rows"].pop(),
    lambda out: out["rows"][0].update(ticker="MG"),
    lambda out: out["rows"][0]["levels"].update(limit=29.53),
    lambda out: out["rows"][0]["levels"].update(entry_low=29.00),
    lambda out: out["rows"][0]["evidence"].update(id="0" * 64),
    lambda out: out["rows"][0].update(projection_sha256="0" * 64),
    lambda out: out["rows"][0]["price_checks"].update(ask="within_published_band"),
    lambda out: out["rows"][0]["price_checks"].update(ask="ready"),
    lambda out: out["rows"][0]["quote"].update(status="stale"),
    lambda out: out["rows"][0]["quote"].update(ask=29.50),
    lambda out: out["rows"][0]["trade"].update(timestamp=(NOW - timedelta(seconds=120)).isoformat()),
    lambda out: out["rows"][0].update(research_shares=1),
    lambda out: out.update(status="partial"),
    lambda out: out.update(reason="wrong_session"),
    lambda out: out["source"].update(status="unavailable", entitlement="unavailable", error_kind="provider_error"),
    lambda out: out["source"].update(feed="sip"),
    lambda out: out["source"].update(requests=0),
    lambda out: out["cohort"].update(bundle_sha256="0" * 64),
    lambda out: out["cohort"].update(bound=False),
    lambda out: out["coverage"].update(halts="checked"),
    lambda out: out["policy"].update(max_requests_per_run=2),
    lambda out: out.update(limits=[]),
    lambda out: out.update(entry_phase="open"),
    lambda out: out.update(expires_at=(NOW + timedelta(seconds=600)).isoformat()),
    lambda out: out["publication"].update(reader_sha256="0" * 64),
])
def test_the_validator_rejects_forged_rows_prices_sources_cohort_and_status(change):
    out = collect()
    change(out)
    with pytest.raises(ValueError):
        observations.validate_observation(out, *source())


def test_exact_publication_cohort_and_prior_bytes_bind():
    publication, receipt, bundle = source()
    out = collect()
    assert json.loads(publication + b"\n") == json.loads(publication)
    with pytest.raises(ValueError, match="binding"):
        observations.validate_observation(out, publication + b"\n", receipt, bundle)
    # The producer's reader accepts trailing whitespace on a receipt; the
    # observation binds the exact bytes beside the record, so it does not.
    assert stop_research.parse_receipt(receipt + b" ")
    with pytest.raises(ValueError, match="cohort binding"):
        observations.validate_observation(out, publication, receipt + b" ", bundle)
    with pytest.raises(ValueError):
        observations.validate_observation(out, publication, receipt, bundle + b" ")
    out["previous_observation_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="prior observation bytes"):
        observations.validate_observation(out, publication, receipt, bundle, require_continuity=True)
    previous = (FIXTURES / "observed.json").read_bytes()
    follow = fixture("followup")
    assert follow["previous_observation_sha256"] == hashlib.sha256(previous).hexdigest()
    observations.validate_observation(follow, publication, receipt, bundle, previous_raw=previous, require_continuity=True)
    with pytest.raises(ValueError, match="prior observation bytes"):
        observations.validate_observation(follow, publication, receipt, bundle, previous_raw=previous + b"\n", require_continuity=True)
    with pytest.raises(ValueError, match="unsupported"):
        collect(previous_raw=b'{"schema_version": 2}')


def test_a_resealed_cohort_that_promotes_a_row_cannot_select_it():
    publication, receipt, bundle = source()
    forged = json.loads(bundle)
    forged["rows"][3]["research"]["allocation_fit"] = True
    body = stop_research._encode(forged)
    receipt_value = json.loads(receipt)
    receipt_value["bundle"] = {"path": "stop-research/" + stop_research._sha(body) + ".json", "sha256": stop_research._sha(body), "bytes": len(body)}
    with pytest.raises(ValueError):
        observations.collect(publication, stop_research._encode(receipt_value), body, client=Client(), clock=lambda: NOW)


def test_fixture_publications_need_dry_run_and_production_refuses_them():
    page = (ROOT / "tests/fixtures/page/full.json").read_bytes()
    client = Client()
    with pytest.raises(ValueError, match="real publication"):
        observations.collect(page, None, None, client=client, clock=lambda: NOW)
    assert client.requests == []
    out = observations.collect(page, None, None, client=client, clock=lambda: datetime(2026, 9, 11, 13, 20, tzinfo=timezone.utc), dry_run=True)
    assert out["dry_run"] is True and out["reason"] == "cohort_missing" and client.requests == []


def docs_with(tmp_path, name="current"):
    publication, receipt, bundle = source(name)
    docs = tmp_path / "docs"
    (docs / "stop-research").mkdir(parents=True)
    (docs / "data.json").write_bytes(publication)
    (docs / "stop-research.json").write_bytes(receipt)
    (docs / json.loads(receipt)["bundle"]["path"]).write_bytes(bundle)
    return docs


def test_run_writes_atomically_binds_the_prior_receipt_and_refuses_publication_paths(tmp_path):
    docs = docs_with(tmp_path)
    first = observations.run(docs=docs, client=Client(), clock=lambda: NOW)
    first_raw = (docs / observations.RECEIPT_FILE).read_bytes()
    assert json.loads(first_raw) == first and first["previous_observation_sha256"] is None
    later = NOW + timedelta(seconds=30)
    second = observations.run(docs=docs, output=tmp_path / "artifact.json", client=Client(later), clock=lambda: later)
    assert second["previous_observation_sha256"] == hashlib.sha256(first_raw).hexdigest()
    assert (docs / observations.RECEIPT_FILE).read_bytes() == first_raw
    for target in ("data.json", "stop-research.json", "reader.json"):
        with pytest.raises(ValueError, match="overwrite publication"):
            observations.run(docs=docs, output=docs / target, client=Client(), clock=lambda: NOW)
    assert (docs / "data.json").read_bytes() == source()[0]
    assert not list(docs.glob(".research-observations-*"))


@pytest.mark.parametrize("victim", ["data.json", "stop-research.json", observations.RECEIPT_FILE])
def test_an_input_changed_during_collection_does_not_replace_the_receipt(tmp_path, victim):
    docs = docs_with(tmp_path)
    output = tmp_path / "result.json"
    output.write_text("prior receipt")
    (docs / observations.RECEIPT_FILE).write_bytes((FIXTURES / "observed.json").read_bytes())
    def edit(_result):
        path = docs / victim
        path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="changed during collection"):
        observations.run(docs=docs, output=output, client=Client(edit=edit), clock=lambda: NOW)
    assert output.read_text() == "prior receipt"


def test_a_corrupt_prior_receipt_or_cohort_is_refused_before_any_provider_call(tmp_path):
    docs = docs_with(tmp_path)
    (docs / observations.RECEIPT_FILE).write_bytes(b'{"schema_version": 1, "status": "observed"')
    client = Client()
    with pytest.raises(ValueError):
        observations.run(docs=docs, client=client, clock=lambda: NOW)
    (docs / observations.RECEIPT_FILE).unlink()
    (docs / "stop-research.json").write_bytes(b"{}")
    with pytest.raises(ValueError):
        observations.run(docs=docs, client=client, clock=lambda: NOW)
    assert client.requests == []


def test_cli_prints_a_summary_and_never_a_raw_response(tmp_path, capsys, monkeypatch):
    docs = docs_with(tmp_path)
    monkeypatch.setattr(observations, "run", lambda **kwargs: fixture("observed"))
    assert observations.main(["--docs", str(docs)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed == {"status": "observed", "reason": None, "rows": 2, "requests": 1,
                       "generated_at": NOW.isoformat(), "data_sha256": fixture("observed")["publication"]["data_sha256"]}
    def broken(**kwargs):
        raise ValueError("private detail that must not print")
    monkeypatch.setattr(observations, "run", broken)
    assert observations.main(["--docs", str(docs)]) == 1
    assert "private detail" not in capsys.readouterr().out


def test_the_observation_stays_within_its_public_size_bound():
    out = collect()
    assert len(json.dumps(out, separators=(",", ":")).encode()) <= observations.MAX_OBSERVATION_BYTES
    assert observations.MAX_OBSERVATION_BYTES <= morning.MAX_OBSERVATION_BYTES


def test_fixture_regeneration_is_required_in_ci():
    import yaml
    workflow = yaml.safe_load((ROOT / ".github/workflows/tests.yml").read_text())
    commands = "\n".join(step.get("run", "") for step in workflow["jobs"]["pytest"]["steps"])
    assert "python tests/fixtures/research-observations/generate.py --check" in commands
