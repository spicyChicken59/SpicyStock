"""Observation evidence cannot manufacture a ticket or a current market quote."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import pytest

from src import morning, morning_halts, reader

NOW = datetime(2026, 9, 11, 13, 35, tzinfo=timezone.utc)
SESSION = "2026-09-11"
PREVIOUS = "2026-09-10"
FIXTURES = Path(__file__).parent / "fixtures" / "page"
MORNING_FIXTURES = Path(__file__).parent / "fixtures" / "morning"


def publication(name="full"):
    return (FIXTURES / f"{name}.json").read_bytes()


def event_outage(symbols, clock, *, previous=None):
    def fetch():
        raise ValueError("private provider failure must not escape")
    return morning_halts.observe(symbols, clock, fetcher=fetch, previous=previous)


def trade(at=NOW, price=125):
    return {"timestamp": at, "price": price, "exchange": "V", "conditions": ["@"]}


def quote(at=NOW, bid=125, ask=125.02):
    return {"timestamp": at, "bid_price": bid, "ask_price": ask, "bid_size": 100, "ask_size": 200,
            "bid_exchange": "V", "ask_exchange": "V", "conditions": ["R"]}


def snapshot(at=NOW):
    return {"latest_trade": trade(at), "latest_quote": quote(at),
            "daily_bar": {"timestamp": datetime(2026, 9, 11, 4, tzinfo=timezone.utc), "volume": 200},
            "previous_daily_bar": {"timestamp": datetime(2026, 9, 10, 4, tzinfo=timezone.utc), "volume": 100}}


class Client:
    def __init__(self, *, errors=(), edit=None):
        self.requests, self.errors, self.edit = [], errors, edit

    def get_stock_snapshot(self, request):
        self.requests.append(request)
        feed = request.feed.value
        if feed in self.errors:
            raise RuntimeError("private credential api-key-secret")
        result = {symbol: snapshot(NOW if feed == "iex" else NOW - timedelta(minutes=15))
                  for symbol in request.symbol_or_symbols}
        if self.edit:
            self.edit(feed, result)
        return result


def collect(name="full", **kwargs):
    defaults = {"client": Client(), "clock": lambda: NOW, "event_observer": event_outage, "dry_run": True}
    return morning.collect(publication(name), **(defaults | kwargs))


def test_admitted_order_only_and_exact_published_limit_separate_from_day2():
    client = Client()
    out = collect(client=client)
    assert out["status"] == "observed" and [r["ticker"] for r in out["rows"]] == ["AAPL"]
    assert [r.feed.value for r in client.requests] == ["iex", "delayed_sip"]
    assert all(r.symbol_or_symbols == ["AAPL"] for r in client.requests)
    row = out["rows"][0]
    assert row["levels"]["limit"] == 126.47 and row["levels"]["day2_spent_above"] == 129.18
    assert row["price_checks"] == {"trade": "within_published_band", "ask": "within_published_band"}
    assert out["sources"]["iex"]["scope"] == "single_venue"
    assert out["sources"]["delayed_sip"]["minimum_delay_seconds"] == 900
    assert row["delayed_volume"]["comparison"] == "above_prior_total"
    assert row["delayed_volume"]["data_through"] is None
    assert out["coverage"]["issuer_news"]["status"] == "not_checked"
    assert "COIL" not in [r["ticker"] for r in out["rows"]]  # Slot-refused watch is not fetched.


def test_anticipation_identity_and_levels_are_the_original_order():
    out = collect("notrade")
    row = out["rows"][0]
    planned = json.loads(publication("notrade"))["watchlist"]["top"][0]["plan"]
    assert row["kind"] == "anticipation" and row["ticker"] == "COIL"
    assert row["levels"]["trigger"] == planned["trigger"]
    assert row["levels"]["limit"] == planned["limit"]
    assert row["evidence_id"] == planned["evidence_ref"]["id"]
    assert row["plan_sha256"] == planned["evidence_ref"]["plan_sha256"]


@pytest.mark.parametrize("price,state", [(121.42, "below_stop"), (121.43, "below_entry_floor"),
                                          (121.73, "below_trigger"), (124.21, "within_published_band"),
                                          (126.47, "within_published_band"), (126.48, "above_limit"),
                                          (129.18, "above_limit"), (129.19, "above_day2_extension")])
def test_comparisons_preserve_exact_trigger_limit_stop_and_extension_boundaries(price, state):
    levels = morning.admitted_rows(json.loads(publication()))[0]["levels"]
    assert morning.price_state(price, levels, "recent") == state
    assert morning.price_state(price, levels, "stale") == "unknown"


@pytest.mark.parametrize("seconds,state", [(60, "recent"), (60.001, "stale"), (-5, "recent"), (-5.001, "invalid")])
def test_trade_freshness_is_provider_time_not_receipt_time(seconds, state):
    measured = morning.trade_observation(trade(NOW - timedelta(seconds=seconds)), NOW, SESSION)
    assert measured["status"] == state
    assert measured["age_seconds"] == pytest.approx(seconds)


@pytest.mark.parametrize("at", [NOW.replace(tzinfo=None), "not-a-time", None])
def test_naive_missing_and_invalid_provider_timestamps_do_not_become_recent(at):
    assert morning.trade_observation(trade(at), NOW, SESSION)["status"] == "invalid"


def test_wrong_session_quote_is_stale_even_if_seconds_age_is_small():
    assert morning.quote_observation(quote(), NOW, "2026-09-10")["status"] == "stale"


@pytest.mark.parametrize("field,value", [("bid_price", 0), ("ask_price", -1), ("bid_size", 0),
                                        ("ask_size", True), ("ask_price", 124), ("bid_price", float("nan")),
                                        ("ask_price", float("inf")), ("bid_price", "125"),
                                        ("conditions", "R"), ("conditions", [7]), ("ask_price", 1e308)])
def test_invalid_quote_shape_does_not_produce_price_checks(field, value):
    raw = quote()
    raw[field] = value
    out = morning.quote_observation(raw, NOW, SESSION)
    assert out["status"] == "invalid"
    json.dumps(out, allow_nan=False)


def test_normalization_preserves_provider_price_precision():
    out = morning.quote_observation(quote(bid=125.0017, ask=125.0198), NOW, SESSION)
    assert out["bid"] == 125.0017 and out["ask"] == 125.0198
    assert out["spread_usd"] == 0.0181


def test_delayed_volume_dates_are_not_live_observation_times():
    raw = snapshot(NOW - timedelta(minutes=15))
    out = morning.volume_observation(raw, NOW, SESSION, PREVIOUS)
    assert out["status"] == "delayed" and out["data_through"] is None
    assert out["daily_timestamp"] == "2026-09-11T04:00:00+00:00"
    raw["daily_bar"]["timestamp"] -= timedelta(days=1)
    prior = morning.volume_observation(raw, NOW, SESSION, PREVIOUS)
    assert prior["status"] == "prior_session" and prior["comparison"] == "unknown"
    raw["latest_trade"]["timestamp"] = NOW
    assert morning.volume_observation(raw, NOW, SESSION, PREVIOUS)["status"] == "invalid"


def test_feed_failures_are_isolated_sanitized_and_never_keep_prices():
    out = collect(client=Client(errors=("iex",)))
    assert out["status"] == "partial"
    assert out["rows"][0]["trade"]["status"] == "unavailable"
    assert out["rows"][0]["quote"]["status"] == "unavailable"
    assert out["rows"][0]["price_checks"] == {"trade": "unknown", "ask": "unknown"}
    assert out["rows"][0]["delayed_volume"]["status"] == "delayed"
    assert "api-key-secret" not in json.dumps(out)
    assert collect(client=Client(errors=("iex", "delayed_sip")))["status"] == "provider_unavailable"


def test_no_tickets_and_outside_collection_window_spend_no_provider_calls():
    client = Client()
    assert collect("red", client=client)["status"] == "no_tickets"
    for at, reason in [(NOW.replace(hour=14), "entry_window_ended"),
                       (NOW.replace(hour=12), "before_collection_window"),
                       (NOW + timedelta(days=1), "wrong_session")]:
        out = collect(client=client, clock=lambda: at)
        assert out["status"] == "inapplicable" and out["reason"] == reason and out["rows"] == []
    assert client.requests == []


def test_provider_completion_clock_is_recorded_and_can_end_the_window():
    times = iter([NOW, NOW + timedelta(seconds=10), NOW + timedelta(seconds=20), NOW + timedelta(seconds=30),
                  NOW + timedelta(seconds=40), NOW + timedelta(seconds=40)])
    out = collect(clock=lambda: next(times))
    assert out["collection_started_at"] == NOW.isoformat()
    assert out["generated_at"] == (NOW + timedelta(seconds=40)).isoformat()
    assert out["rows"][0]["trade"]["age_seconds"] == 40


def test_a_quote_after_its_provider_receipt_is_invalid_even_before_final_completion():
    measured = morning.quote_observation(quote(NOW + timedelta(seconds=10)), NOW + timedelta(seconds=40), SESSION,
                                         observed_at=NOW)
    assert measured["status"] == "invalid"


@pytest.mark.parametrize("change", [
    lambda out: out["rows"].append(deepcopy(out["rows"][0])),
    lambda out: out["rows"].clear(),
    lambda out: out["rows"][0].update(kind="anticipation"),
    lambda out: out["rows"][0].update(ticker="COIL"),
    lambda out: out["rows"][0].update(plan_sha256="0" * 64),
    lambda out: out["rows"][0]["levels"].update(limit=129.18),
    lambda out: out["rows"][0]["price_checks"].update(ask="ready"),
    lambda out: out.update(status="no_tickets"),
    lambda out: out["sources"]["iex"].update(status="unavailable", entitlement="unavailable", error_kind="provider_error"),
    lambda out: out["sources"]["delayed_sip"].update(status="unavailable", entitlement="unavailable", error_kind="provider_error"),
    lambda out: out["coverage"]["issuer_news"].update(status="cleared"),
])
def test_publisher_validator_rejects_forged_membership_authority_and_source_claims(change):
    out = collect()
    change(out)
    with pytest.raises(ValueError):
        morning.validate_observation(out, publication())


def test_exact_record_bytes_bind_even_same_session_and_rules():
    out = collect()
    whitespace_changed = publication() + b"\n"
    assert json.loads(whitespace_changed) == json.loads(publication())
    with pytest.raises(ValueError, match="binding"):
        morning.validate_observation(out, whitespace_changed)


def test_reader_binding_is_derived_from_exact_canonical_bytes():
    raw = publication()
    out = collect()
    projected, _ = reader.derive(raw)
    assert out["publication"]["data_sha256"] == hashlib.sha256(raw).hexdigest()
    assert out["publication"]["reader_projection_version"] == 1
    assert out["publication"]["reader_sha256"] == hashlib.sha256(projected).hexdigest()
    changed = morning.bind_record(raw + b"\n", allow_fixture=True)
    assert changed["context_sha256"] == out["publication"]["context_sha256"]
    assert changed["reader_sha256"] != out["publication"]["reader_sha256"]
    # A copied canonical claim cannot bind altered projected candidates.
    altered = json.loads(projected)
    altered["data"]["bursts"][0]["plan"]["limit"] += 1
    out["publication"]["reader_sha256"] = hashlib.sha256(json.dumps(altered).encode()).hexdigest()
    with pytest.raises(ValueError, match="binding"):
        morning.validate_observation(out, raw)


@pytest.mark.parametrize("change", [
    lambda binding: binding.pop("reader_sha256"),
    lambda binding: binding.pop("reader_projection_version"),
    lambda binding: binding.update(reader_projection_version=True),
    lambda binding: binding.update(reader_projection_version=2),
    lambda binding: binding.update(reader_sha256="0" * 64),
    lambda binding: binding.update(reader_sha256=None),
    lambda binding: binding.update(reader_bytes=123),
])
def test_reader_binding_rejects_partial_unknown_and_forged_extensions(change):
    out = collect()
    change(out["publication"])
    with pytest.raises(ValueError, match="binding"):
        morning.validate_observation(out, publication())


@pytest.mark.parametrize("name,digest", [
    ("observed", "efb553ccd84fbc0eafcff7f13ec1d45449310a179471f349ce89341b84f0d9f8"),
    ("halted", "4e118271a3938a31713973b785d64d7ee42b499cd57eff926daf6084e4fa64df"),
    ("corporate-excluded", "1863d7be06a135ee9c0373422bcf7bb81124353d1378eaf1f5f615a4a75da413"),
    ("corporate-resolved", "ca42e825c6efc53fc92710cc772b03c2e94b0db9685a7bc96c66d08ed72c19e9"),
])
def test_original_legacy_controls_keep_exact_bytes_and_canonical_validation(name, digest):
    previous = (MORNING_FIXTURES / f"{name}.json").read_bytes()
    assert hashlib.sha256(previous).hexdigest() == digest
    out = json.loads(previous)
    assert "reader_sha256" not in out["publication"]
    assert "reader_projection_version" not in out["publication"]
    morning.validate_observation(out, (MORNING_FIXTURES / "full-publication.json").read_bytes())


def test_archived_morning_generator_refuses_changed_input_before_collecting(tmp_path, monkeypatch):
    from tests.fixtures.morning import generate
    for name in generate.ARCHIVED_PUBLICATIONS:
        raw = (MORNING_FIXTURES / (name + "-publication.json")).read_bytes()
        (tmp_path / (name + "-publication.json")).write_bytes(raw + (b"\n" if name == "full" else b""))
    monkeypatch.setattr(generate, "TARGET", tmp_path)
    monkeypatch.setattr(generate.morning, "collect", lambda *a, **kw: pytest.fail("altered archive reached collector"))
    with pytest.raises(ValueError, match="Archived morning publication bytes changed: full"):
        generate.build()


def test_legacy_halt_migration_keeps_exclusion_through_outage_until_sourced_resumption():
    from tests.fixtures.morning.generate import events
    raw = (MORNING_FIXTURES / "full-publication.json").read_bytes()
    previous = (MORNING_FIXTURES / "halted.json").read_bytes()
    later = NOW + timedelta(seconds=30)
    out = morning.collect(raw, previous_raw=previous, client=Client(errors=("iex", "delayed_sip")),
                          clock=lambda: later, event_observer=event_outage)
    assert out["previous_observation_sha256"] == hashlib.sha256(previous).hexdigest()
    assert out["publication"]["reader_sha256"] == reader.binding(raw)["reader_sha256"]
    assert out["status"] == "provider_unavailable"
    assert out["halt_memory"] == json.loads(previous)["halt_memory"]
    assert out["rows"][0]["events"]["halt"]["blocks_entry"] is True
    damaged = deepcopy(out)
    damaged["halt_memory"] = {}
    with pytest.raises(ValueError):
        morning.validate_observation(damaged, raw, previous_raw=previous, require_continuity=True)
    resumed_at = NOW + timedelta(seconds=45)
    outage_raw = json.dumps(out).encode()
    resumed = morning.collect(raw, previous_raw=outage_raw, client=Client(), clock=lambda: resumed_at,
                              event_observer=events("resumed", resumed_at))
    assert resumed["halt_memory"] == {}
    assert resumed["rows"][0]["events"]["halt"]["status"] == "resumption_reported"
    assert resumed["rows"][0]["events"]["halt"]["blocks_entry"] is None
    assert resumed["previous_observation_sha256"] == hashlib.sha256(outage_raw).hexdigest()
    assert resumed["rows"][0]["plan_sha256"] == json.loads(previous)["rows"][0]["plan_sha256"]


def test_fixture_is_refused_for_production_before_any_provider_calls():
    client = Client()
    with pytest.raises(ValueError, match="real publication"):
        morning.collect(publication(), client=client, clock=lambda: NOW)
    assert client.requests == []


def test_publication_change_during_collection_does_not_replace_receipt(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "data.json").write_bytes(publication())
    def edit(feed, _):
        if feed == "iex":
            (docs / "data.json").write_bytes(publication() + b"\n")
    output = tmp_path / "result.json"
    output.write_text("prior receipt")
    with pytest.raises(ValueError, match="changed during collection"):
        morning.run(docs=docs, output=output, dry_run=True, client=Client(edit=edit), clock=lambda: NOW,
                    event_observer=event_outage)
    assert output.read_text() == "prior receipt"


def test_prior_receipt_is_bound_and_corruption_is_not_overwritten(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    raw = publication()
    (docs / "data.json").write_bytes(raw)
    initial = morning.run(docs=docs, dry_run=True, client=Client(), clock=lambda: NOW, event_observer=event_outage)
    prior_raw = (docs / "morning.json").read_bytes()
    out = morning.run(docs=docs, output=tmp_path / "artifact.json", dry_run=True, client=Client(), clock=lambda: NOW,
                      event_observer=event_outage)
    assert out["previous_observation_sha256"] == hashlib.sha256(prior_raw).hexdigest()
    assert (docs / "morning.json").read_bytes() == prior_raw
    initial["rows"][0]["plan_sha256"] = "0" * 64
    (docs / "morning.json").write_text(json.dumps(initial))
    client = Client()
    with pytest.raises(ValueError):
        morning.run(docs=docs, dry_run=True, client=client, clock=lambda: NOW, event_observer=event_outage)
    assert client.requests == []


def test_collection_does_not_write_over_the_publication(tmp_path):
    (tmp_path / "data.json").write_bytes(publication())
    with pytest.raises(ValueError, match="overwrite publication"):
        morning.run(docs=tmp_path, output=tmp_path / "data.json", dry_run=True, client=Client(), clock=lambda: NOW)
    assert (tmp_path / "data.json").read_bytes() == publication()


def test_missing_credentials_become_explicit_feed_outages_without_client_creation(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    monkeypatch.setattr(morning.market_data, "get_clients", lambda: pytest.fail("client should not be constructed"))
    out = collect(client=None)
    assert out["status"] == "provider_unavailable"
    assert {s["error_kind"] for s in out["sources"].values()} == {"missing_credentials"}


def test_duration_and_continuity_hash_are_validated_independently():
    out = collect()
    out["generated_at"] = (NOW + timedelta(seconds=181)).isoformat()
    out["expires_at"] = (NOW + timedelta(seconds=481)).isoformat()
    with pytest.raises(ValueError, match="duration"):
        morning.validate_observation(out, publication())
    out = collect()
    out["previous_observation_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="prior observation bytes"):
        morning.validate_observation(out, publication(), require_continuity=True)


def test_retained_corporate_exclusion_survives_registry_omission_and_no_ticket_receipts():
    raw = (MORNING_FIXTURES / "full-publication.json").read_bytes()
    previous = (MORNING_FIXTURES / "corporate-excluded.json").read_bytes()
    later = NOW + timedelta(seconds=30)
    out = morning.collect(raw, previous_raw=previous, client=Client(), clock=lambda: later,
                          event_observer=event_outage)
    current = out["rows"][0]["events"]["corporate_action"]
    retained = out["rows"][0]["events"]["retained_corporate_actions"]
    assert current["blocked"] is False and current["matches"] == []
    assert retained and retained[0]["event"]["id"] == "synthetic_cash_event"
    assert retained[0]["registry_sha256"] != current["registry_sha256"]
    assert "reader_sha256" not in json.loads(previous)["publication"]
    assert out["publication"]["reader_sha256"] == reader.binding(raw)["reader_sha256"]
    assert out["previous_observation_sha256"] == hashlib.sha256(previous).hexdigest()
    damaged = deepcopy(out)
    damaged["corporate_memory"] = {}
    damaged["rows"][0]["events"]["retained_corporate_actions"] = []
    with pytest.raises(ValueError, match="continuity"):
        morning.validate_observation(damaged, raw, previous_raw=previous, require_continuity=True)
    for next_raw, at, status in [((MORNING_FIXTURES / "red-publication.json").read_bytes(), later, "no_tickets"),
                                  (raw, NOW.replace(hour=14), "inapplicable")]:
        kept = morning.collect(next_raw, previous_raw=previous, client=Client(), clock=lambda: at,
                               event_observer=event_outage)
        assert kept["status"] == status and kept["rows"] == []
        assert kept["corporate_memory"] == out["corporate_memory"]


def test_only_explicit_source_backed_resolution_removes_retained_corporate_exclusion(monkeypatch):
    raw = (MORNING_FIXTURES / "full-publication.json").read_bytes()
    previous = (MORNING_FIXTURES / "corporate-excluded.json").read_bytes()
    prior = json.loads(previous)
    event = deepcopy(prior["corporate_memory"]["AAPL"][0]["event"])
    event.pop("review_overdue")
    resolution = {**event["sources"][0], "title": "Synthetic sourced resolution",
                  "published_on": "2026-09-11", "quote": "Synthetic deal explicitly ended; test only."}
    resolution["sha256"] = hashlib.sha256(resolution["quote"].encode()).hexdigest()
    event.update(active_until="2026-09-11", resolution=resolution)
    registry = {"version": 1, "coverage": morning.event_risk.COVERAGE,
                "reviewed_on": "2026-09-11", "coverage_note": "Synthetic explicit resolution fixture.", "events": [event]}
    morning.event_risk.validate_registry(registry)
    monkeypatch.setattr(morning.event_risk, "REGISTRY", registry)
    out = morning.collect(raw, previous_raw=previous, client=Client(), clock=lambda: NOW + timedelta(seconds=30),
                          event_observer=event_outage)
    assert out["corporate_memory"] == {} and out["rows"][0]["events"]["retained_corporate_actions"] == []
    assert out["rows"][0]["events"]["corporate_action"]["blocked"] is False
    assert out["rows"][0]["plan_sha256"] == prior["rows"][0]["plan_sha256"]
    proof = out["corporate_resolutions"][0]
    assert (proof["event_id"], proof["symbol"], proof["active_from"], proof["active_until"]) == (
        "synthetic_cash_event", "AAPL", "2026-09-10", "2026-09-11")
    assert proof["resolution"] == resolution and proof["observed_at"] == (NOW + timedelta(seconds=30)).isoformat()
    damaged = deepcopy(out)
    damaged["corporate_resolutions"] = []
    with pytest.raises(ValueError, match="resolution continuity"):
        morning.validate_observation(damaged, raw, previous_raw=previous, require_continuity=True)


def test_halt_memory_survives_inapplicable_receipt_and_continuity_rejects_erasure():
    raw = (MORNING_FIXTURES / "full-publication.json").read_bytes()
    previous = (MORNING_FIXTURES / "halted.json").read_bytes()
    out = morning.collect(raw, previous_raw=previous, client=Client(), clock=lambda: NOW.replace(hour=14),
                          event_observer=event_outage)
    assert out["status"] == "inapplicable" and out["rows"] == []
    assert out["halt_memory"]["AAPL"]["halt"]["blocks_entry"] is True
    out["halt_memory"] = {}
    with pytest.raises(ValueError):
        morning.validate_observation(out, raw, previous_raw=previous, require_continuity=True)


@pytest.mark.parametrize("prefix", ["", "reader-"])
def test_generated_browser_receipts_pass_the_same_persistence_validator(prefix):
    full = (MORNING_FIXTURES / "full-publication.json").read_bytes()
    red = (MORNING_FIXTURES / "red-publication.json").read_bytes()
    for name in ("observed", "outage", "halted", "corporate-excluded", "no-tickets", "resumed", "corporate-retained", "corporate-resolution-carried"):
        out = json.loads((MORNING_FIXTURES / f"{prefix}{name}.json").read_bytes())
        prior_name = {"resumed": "halted", "corporate-retained": "corporate-excluded", "corporate-resolution-carried": "corporate-resolved"}.get(name)
        previous = (MORNING_FIXTURES / f"{prefix}{prior_name}.json").read_bytes() if prior_name else None
        morning.validate_observation(out, red if name == "no-tickets" else full, previous_raw=previous,
                                     require_continuity=True)


def test_corporate_resolution_proof_survives_later_receipts_for_a_browser_that_missed_it():
    raw = (MORNING_FIXTURES / "full-publication.json").read_bytes()
    previous = (MORNING_FIXTURES / "corporate-resolved.json").read_bytes()
    out = morning.collect(raw, previous_raw=previous, client=Client(), clock=lambda: NOW + timedelta(seconds=45),
                          event_observer=event_outage)
    assert out["corporate_memory"] == {}
    assert out["corporate_resolutions"] == json.loads(previous)["corporate_resolutions"]
    assert "reader_sha256" not in json.loads(previous)["publication"]
    assert out["publication"]["reader_sha256"] == reader.binding(raw)["reader_sha256"]
    assert out["previous_observation_sha256"] == hashlib.sha256(previous).hexdigest()
    assert out["corporate_resolutions"][0]["resolution"]["url"] == "https://example.invalid/synthetic-event"
    for field, value in (("event_id", "other_event"), ("active_until", "2026-09-12"), ("observed_at", "2026-09-11T13:34:00Z")):
        damaged = deepcopy(out)
        damaged["corporate_resolutions"][0][field] = value
        with pytest.raises(ValueError):
            morning.validate_observation(damaged, raw, previous_raw=previous, require_continuity=True)


@pytest.mark.parametrize("mutate", [lambda out: out.update(rows=None),
                                     lambda out: out["rows"][0].update(events=None),
                                     lambda out: out["rows"][0]["events"]["corporate_action"].update(matches=[7], blocked=True),
                                     lambda out: out.update(coverage=[]),
                                     lambda out: out.update(corporate_memory={"AAPL": [False]})])
def test_malformed_nested_observation_types_raise_a_public_validation_error(mutate):
    out = collect()
    mutate(out)
    with pytest.raises(ValueError):
        morning.validate_observation(out, publication())
