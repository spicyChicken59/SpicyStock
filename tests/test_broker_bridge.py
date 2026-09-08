"""Offline end-to-end checks of the private broker boundary; never places a real order."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import json
from urllib.parse import parse_qs, urlsplit

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
import httpx
import pytest

from src.broker_bridge.alpaca import Alpaca, BrokerError
from src.broker_bridge.app import create_app, COOKIE, OAUTH_COOKIE
from src.broker_bridge.config import Config
from src.broker_bridge.domain import iso
from src.broker_bridge.store import Store, digest

NOW = datetime(2026, 9, 8, 14, 0, tzinfo=timezone.utc).timestamp()


class BrokerDouble:
    def __init__(self, clock):
        self.time = clock
        self.account_data = {"id": "account-1234", "cash": "10000", "equity": "10000", "currency": "USD",
                             "status": "ACTIVE", "trading_blocked": False, "account_blocked": False}
        self.position_data = []
        self.order_data = []
        self.fill_data = []
        self.receipts = {}
        self.submissions = []
        self.quote_offset = -1
        self.clock_offset = 0
        self.open = True
        self.feed = None
        self.asset_data = {"symbol": "AAPL", "class": "us_equity", "status": "active", "tradable": True, "exchange": "NASDAQ"}
        self.submit_failure = None
        self.accept_before_timeout = False
        self.lookups = 0
        self.exchange_codes = []

    def exchange(self, code):
        self.exchange_codes.append(code)
        return "private-broker-token"

    def account(self, session):
        return deepcopy(self.account_data)

    def clock(self, session):
        return {"timestamp": iso(self.time[0] + self.clock_offset), "is_open": self.open,
                "next_open": "2026-09-09T13:30:00Z", "next_close": "2026-09-08T20:00:00Z"}

    def calendar(self, session, start, end):
        return [{"date": "2026-09-03"}, {"date": "2026-09-04"}, {"date": "2026-09-08"}]

    def positions(self, session):
        return deepcopy(self.position_data)

    def orders(self, session):
        return deepcopy(self.order_data)

    def asset(self, session, sym):
        return deepcopy(self.asset_data)

    def quote(self, session, sym):
        return {"symbol": sym, "quote": {"bp": 103.90, "ap": 104, "t": iso(self.time[0] + self.quote_offset)}}, self.feed or ("sip" if session["mode"] == "live" else "iex")

    def fill_page(self, session, token=None):
        return deepcopy(self.fill_data) if not token else []

    def order_by_client_id(self, session, cid):
        self.lookups += 1
        return deepcopy(self.receipts.get(cid))

    def submit(self, session, order):
        self.submissions.append(deepcopy(order))
        response = {"id": "order-1", "status": "accepted", "filled_qty": "0", **order,
                    "legs": [{"id": "stop-1", "symbol": order["symbol"], "side": "sell", "type": "stop", "qty": order["qty"],
                              "stop_price": order["stop_loss"]["stop_price"], "status": "held", "time_in_force": "gtc"}]}
        if self.accept_before_timeout or not self.submit_failure:
            self.receipts[order["client_order_id"]] = response
        if self.submit_failure:
            raise self.submit_failure
        return response


def source():
    return {"run": {"date": "2026-09-04", "type": "evening", "status": "ok", "fixture": False, "dry_run": False,
                    "stockbee": {"version": 1, "date": "2026-09-04", "scan": {"rows": [
                        {"ticker": "AAPL", "date": "2026-09-04", "close": 104, "prev_close": 100, "volume": 150000, "prev_volume": 120000}
                    ]}}}}


def make_config(tmp_path, **overrides):
    docs = tmp_path / "public"
    docs.mkdir(exist_ok=True)
    (docs / "index.html").write_text("<h1>SpicyStock</h1>")
    (docs / "trading-config.json").write_text('{"enabled":false}')
    (docs / "data.json").write_text(json.dumps(source()))
    return Config(origin="https://stock.test", client_id="private-client", client_secret="private-secret",
                  encryption_key=Fernet.generate_key().decode(), database=tmp_path / "private" / "broker.sqlite3",
                  docs=docs, common_stock_symbols=frozenset({"AAPL", "MSFT"}), max_position_percent=__import__("decimal").Decimal("100"),
                  max_notional=__import__("decimal").Decimal("100000"), **overrides)


def login(client, app, mode="paper", account_id="account-1234"):
    sid, csrf = app.state.store.session_create(mode, "private-broker-token", account_id, NOW, 28800)
    client.cookies.set(COOKIE, sid, domain="stock.test", path="/")
    client.headers.update({"Origin": "https://stock.test", "X-CSRF-Token": csrf})
    return sid, csrf


@pytest.fixture
def bridge(tmp_path):
    now = [NOW]
    config = make_config(tmp_path)
    broker = BrokerDouble(now)
    app = create_app(config, broker, lambda: now[0])
    with TestClient(app, base_url="https://stock.test") as client:
        sid, csrf = login(client, app)
        yield client, app, broker, now, config, sid


def preview(client, **values):
    return client.post("/api/preview", json={"symbol": "AAPL", "limit_price": 104, "stop_price": 100, "risk_percent": 1, **values})


def submit(client, pid):
    return client.post("/api/orders", json={"preview_id": pid, "confirmation": "submit"})


def fill(id="fill-1", **values):
    return {"activity_type": "FILL", "id": id, "order_id": "order-1", "symbol": "AAPL", "side": "buy",
            "qty": "2", "price": "103.95", "transaction_time": "2026-09-08T13:45:00Z", **values}


def test_unconfigured_is_truthful_and_static_override_wins(tmp_path):
    cfg = replace(make_config(tmp_path), client_secret="")
    with TestClient(create_app(cfg), base_url=cfg.origin) as c:
        assert c.get("/api/status").json()["state"] == "unconfigured"
        assert c.get("/trading-config.json").json()["api_base"] == "/api"
        assert c.get("/").status_code == 200
        assert c.get("/api/connect").status_code == 503
    assert not cfg.database.exists()


def test_tokens_and_session_ids_are_not_persisted_in_plaintext(bridge):
    client, app, broker, now, cfg, sid = bridge
    with app.state.store.db() as db:
        row = db.execute("SELECT * FROM sessions").fetchone()
        assert row["id"] == digest(sid)
        assert row["id"] != sid
        assert b"private-broker-token" not in row["secret"]
        assert b"account-1234" not in row["secret"]
    assert cfg.database.stat().st_mode & 0o777 == 0o600
    result = client.get("/api/status")
    assert result.json()["state"] == "paper"
    assert "private-broker-token" not in result.text
    assert result.headers["cache-control"] == "no-store"


def test_oauth_state_is_browser_bound_single_use_and_cookie_secure(bridge):
    client, app, broker, now, cfg, sid = bridge
    response = client.get("/api/connect", follow_redirects=False)
    args = parse_qs(urlsplit(response.headers["location"]).query)
    assert args["env"] == ["paper"] and args["scope"] == ["trading data"]
    state = args["state"][0]
    assert len(state) >= 40
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=lax" in cookie
    with TestClient(app, base_url=cfg.origin) as thief:
        assert thief.get("/api/oauth/callback", params={"state": state, "code": "owned-code"}).status_code == 403
    callback = client.get("/api/oauth/callback", params={"state": state, "code": "owned-code"}, follow_redirects=False)
    assert callback.status_code == 303 and callback.headers["location"] == "/#trade-workspace"
    assert broker.exchange_codes == ["owned-code"]
    assert client.get("/api/oauth/callback", params={"state": state, "code": "owned-code"}).status_code == 403


@pytest.mark.parametrize("origin,csrf,code", [("https://attacker.test", "valid", "origin_rejected"), ("https://stock.test", "wrong", "csrf_rejected"), (None, "valid", "origin_rejected")])
def test_mutations_require_exact_origin_and_csrf(bridge, origin, csrf, code):
    client, app, broker, now, cfg, sid = bridge
    if origin is None:
        del client.headers["Origin"]
    else:
        client.headers["Origin"] = origin
    if csrf != "valid":
        client.headers["X-CSRF-Token"] = csrf
    result = preview(client)
    assert result.status_code == 403 and result.json()["error"]["code"] == code
    assert not broker.submissions


def test_preview_sizes_whole_cash_funded_shares_and_never_submits(bridge):
    client, app, broker, now, cfg, sid = bridge
    p = preview(client).json()
    assert p["qty"] == 25 and p["risk_dollars"] == 100 and p["position_dollars"] == 2600
    assert p["source_session"] == "2026-09-04"
    assert p["quote"]["feed"] == "iex" and p["expires_at"] == "2026-09-08T14:00:30Z"
    assert "partial fills may remain unprotected" in p["protection_note"]
    assert not broker.submissions
    p = preview(client, cash_cap=1000).json()
    assert p["qty"] == 9 and p["position_dollars"] == 936


@pytest.mark.parametrize("values,code", [({"stop_price": 104}, "stop_invalid"), ({"risk_percent": 1.01}, "risk_limit"),
                                          ({"limit_price": 120}, "limit_far_from_quote"), ({"limit_price": "NaN"}, "invalid_number"),
                                          ({"limit_price": True}, "invalid_number"), ({"limit_price": 104.001}, "price_precision"),
                                          ({"symbol": "SPY"}, "common_stock_verification_required"), ({"symbol": "../account"}, "invalid_symbol"),
                                          ({"qty": 1000}, "invalid_request")])
def test_each_invalid_trade_is_rejected_before_any_order(bridge, values, code):
    client, app, broker, now, cfg, sid = bridge
    result = preview(client, **values)
    assert result.status_code in (409, 422) and result.json()["error"]["code"] == code
    assert broker.submissions == []


@pytest.mark.parametrize("offset", [-30.01, 5.01])
def test_stale_or_future_quotes_block_preview(bridge, offset):
    client, app, broker, now, cfg, sid = bridge
    broker.quote_offset = offset
    assert preview(client).json()["error"]["code"] == "quote_stale"


def test_market_closed_and_clock_stale_are_separate_guards(bridge):
    client, app, broker, now, cfg, sid = bridge
    broker.open = False
    assert preview(client).json()["error"]["code"] == "market_closed"
    broker.open = True
    broker.clock_offset = -31
    assert preview(client).json()["error"]["code"] == "clock_stale"


@pytest.mark.parametrize("change,code", [("old", "source_stale"), ("fixture", "source_degraded"), ("missing", "source_missing"), ("not4", "setup_invalid")])
def test_trusted_source_must_be_real_complete_and_previous_market_session(bridge, change, code):
    client, app, broker, now, cfg, sid = bridge
    data = source()
    if change == "old":
        data["run"]["date"] = "2026-09-03"
    elif change == "fixture":
        data["run"]["fixture"] = True
    elif change == "missing":
        del data["run"]["stockbee"]
    else:
        data["run"]["stockbee"]["scan"]["rows"][0]["close"] = 103.99
    (cfg.docs / "data.json").write_text(json.dumps(data))
    assert preview(client).json()["error"]["code"] == code


def test_blocked_asset_or_account_cannot_preview(bridge):
    client, app, broker, now, cfg, sid = bridge
    broker.account_data["trading_blocked"] = True
    assert preview(client).json()["error"]["code"] == "account_blocked"
    broker.account_data["trading_blocked"] = False
    broker.asset_data["tradable"] = False
    assert preview(client).json()["error"]["code"] == "asset_unavailable"


def test_existing_position_and_pending_order_block_duplicate_symbol(bridge):
    client, app, broker, now, cfg, sid = bridge
    broker.position_data = [{"symbol": "AAPL", "qty": "1"}]
    assert preview(client).json()["error"]["code"] == "position_exists"
    broker.position_data = []
    broker.order_data = [{"id": "other", "symbol": "AAPL"}]
    assert preview(client).json()["error"]["code"] == "order_exists"


def test_other_pending_limit_cash_is_reserved_without_using_margin(bridge):
    client, app, broker, now, cfg, sid = bridge
    broker.account_data["buying_power"] = "40000"
    broker.order_data = [{"id": "other", "symbol": "MSFT", "side": "buy", "qty": "100", "filled_qty": "0", "limit_price": "95"}]
    assert preview(client).json()["qty"] == 4


def test_submit_uses_server_owned_values_and_is_idempotent(bridge):
    client, app, broker, now, cfg, sid = bridge
    p = preview(client).json()
    assert submit(client, p["preview_id"]).json()["state"] == "accepted"
    sent = broker.submissions[0]
    assert sent["qty"] == "25" and sent["side"] == "buy" and sent["order_class"] == "oto"
    assert sent["stop_loss"] == {"stop_price": "100.0"}
    assert sent["time_in_force"] == "gtc" and sent["extended_hours"] is False
    for _ in range(3):
        assert submit(client, p["preview_id"]).json()["state"] == "accepted"
    assert len(broker.submissions) == 1 and broker.lookups == 3
    portfolio = client.get("/api/portfolio").json()
    assert portfolio["fills"] == [] and portfolio["positions"] == []


def test_expiry_and_cash_are_revalidated_at_submission(bridge):
    client, app, broker, now, cfg, sid = bridge
    p = preview(client).json()
    now[0] += 30
    assert submit(client, p["preview_id"]).json()["error"]["code"] == "preview_expired"
    p = preview(client).json()
    broker.account_data["cash"] = "104"
    assert submit(client, p["preview_id"]).json()["error"]["code"] == "funds_changed"
    assert not broker.submissions


def test_source_change_after_preview_blocks_submission(bridge):
    client, app, broker, now, cfg, sid = bridge
    p = preview(client).json()
    data = source()
    data["run"]["note"] = "new trusted revision"
    (cfg.docs / "data.json").write_text(json.dumps(data))
    assert submit(client, p["preview_id"]).json()["error"]["code"] == "preview_changed"
    assert not broker.submissions


def test_timeout_after_accept_reconciles_same_id_without_second_post(bridge):
    client, app, broker, now, cfg, sid = bridge
    p = preview(client).json()
    broker.submit_failure = BrokerError(uncertain=True)
    broker.accept_before_timeout = True
    result = submit(client, p["preview_id"]).json()
    assert result["state"] == "accepted"
    assert result["order"]["client_order_id"] == broker.submissions[0]["client_order_id"]
    assert submit(client, p["preview_id"]).json()["state"] == "accepted"
    assert len(broker.submissions) == 1


def test_unknown_submission_survives_restart_and_blocks_new_orders(bridge):
    client, app, broker, now, cfg, sid = bridge
    p = preview(client).json()
    broker.submit_failure = BrokerError(uncertain=True)
    first = submit(client, p["preview_id"]).json()
    assert first["state"] == "reconciliation_needed" and first["order"] is None
    assert preview(client).json()["error"]["code"] == "reconciliation_needed"
    restart = create_app(cfg, broker, lambda: now[0])
    with TestClient(restart, base_url=cfg.origin) as second:
        second.cookies.set(COOKIE, sid, domain="stock.test", path="/")
        second.headers.update(client.headers)
        assert second.get("/api/status").json()["state"] == "reconciliation_needed"
        assert submit(second, p["preview_id"]).json()["state"] == "reconciliation_needed"
    assert len(broker.submissions) == 1


def test_cross_account_and_new_session_cannot_consume_preview(bridge):
    client, app, broker, now, cfg, sid = bridge
    p = preview(client).json()
    login(client, app, account_id="another-account")
    assert submit(client, p["preview_id"]).status_code == 404
    login(client, app)
    assert submit(client, p["preview_id"]).status_code == 404
    assert not broker.submissions


def test_fills_are_deduped_persistent_and_account_scoped(bridge):
    client, app, broker, now, cfg, sid = bridge
    broker.fill_data = [fill(), fill()]
    one = client.get("/api/portfolio").json()
    assert len(one["fills"]) == 1 and one["fills"][0]["qty"] == 2
    assert one["fills"][0]["source"] == "alpaca" and one["fills_complete_since"] is None
    broker.fill_data = []
    assert len(client.get("/api/portfolio").json()["fills"]) == 1
    login(client, app, account_id="account-5678")
    broker.account_data["id"] = "account-5678"
    assert client.get("/api/portfolio").json()["fills"] == []


def test_changed_execution_id_is_not_silently_overwritten(bridge):
    client, app, broker, now, cfg, sid = bridge
    broker.fill_data = [fill()]
    assert client.get("/api/portfolio").status_code == 200
    broker.fill_data = [fill(price="102")]
    response = client.get("/api/portfolio")
    assert response.status_code == 409 and response.json()["error"]["code"] == "fill_reconciliation_needed"


def test_disconnect_removes_all_tokens_but_keeps_receipt_lock(bridge):
    client, app, broker, now, cfg, sid = bridge
    p = preview(client).json()
    broker.submit_failure = BrokerError(uncertain=True)
    submit(client, p["preview_id"])
    assert client.post("/api/disconnect", json={}).status_code == 200
    assert app.state.store.session(sid, now[0]) is None
    login(client, app)
    assert client.get("/api/status").json()["state"] == "reconciliation_needed"


def test_live_mode_requires_enabled_account_and_sip(bridge):
    client, app, broker, now, cfg, sid = bridge
    login(client, app, mode="live")
    assert preview(client).json()["error"]["code"] == "live_disabled"
    live_cfg = replace(cfg, live_enabled=True, live_account_ids=frozenset({"account-1234"}))
    live_app = create_app(live_cfg, broker, lambda: now[0])
    with TestClient(live_app, base_url=cfg.origin) as live:
        login(live, live_app, mode="live")
        broker.feed = "iex"
        assert preview(live).json()["error"]["code"] == "live_feed_required"
        broker.feed = "sip"
        assert preview(live).json()["mode"] == "live"


def test_adapter_uses_fixed_roots_scope_and_single_post(tmp_path):
    calls = []
    cfg = make_config(tmp_path)
    def transport(request):
        calls.append(request)
        if request.url.path == "/oauth/token":
            assert request.headers["content-type"].startswith("application/x-www-form-urlencoded")
            return httpx.Response(200, json={"access_token": "owned", "scope": "trading data"})
        raise httpx.ReadTimeout("socket uncertainty", request=request)
    adapter = Alpaca(cfg, transport=httpx.MockTransport(transport))
    assert adapter.exchange("code") == "owned"
    with pytest.raises(BrokerError) as failed:
        adapter.submit({"mode": "paper", "token": "owned"}, {"client_order_id": "fixed"})
    assert failed.value.uncertain and len(calls) == 2
    assert str(calls[-1].url) == "https://paper-api.alpaca.markets/v2/orders"
    with pytest.raises(ValueError):
        adapter.request("GET", "https://attacker.test", "/anything", "owned")


def test_config_refuses_public_database_and_unbounded_live(tmp_path):
    cfg = make_config(tmp_path)
    with pytest.raises(ValueError):
        replace(cfg, database=cfg.docs / "tokens.sqlite3")
    with pytest.raises(ValueError):
        replace(cfg, live_enabled=True)
    with pytest.raises(ValueError):
        replace(cfg, origin="http://stock.test")


def test_position_cap_includes_holdings_and_pending_buys_and_freezes_user_limit(bridge):
    client, app, broker, now, cfg, sid = bridge
    assert client.get("/api/status").json()["limits"]["max_positions"] == 5
    broker.position_data = [{"symbol": "MSFT", "qty": "3"}]
    assert preview(client, max_positions=1).json()["error"]["code"] == "position_cap_reached"
    p = preview(client, max_positions=2).json()
    assert p["max_positions"] == 2
    broker.order_data = [{"id": "entry-2", "symbol": "NVDA", "side": "buy", "qty": "1", "filled_qty": "0", "limit_price": "100"}]
    assert submit(client, p["preview_id"]).json()["error"]["code"] == "position_cap_reached"
    assert not broker.submissions
    assert preview(client, max_positions=6).json()["error"]["code"] == "position_cap_invalid"


@pytest.mark.parametrize("broker_status", ["rejected", "canceled", "expired", "filled", "partially_filled"])
def test_receipt_terminal_status_never_becomes_a_fake_execution(bridge, broker_status):
    client, app, broker, now, cfg, sid = bridge
    p = preview(client).json()
    first = submit(client, p["preview_id"]).json()
    broker.receipts[first["client_order_id"]]["status"] = broker_status
    result = submit(client, p["preview_id"]).json()
    assert result["state"] == broker_status
    assert result["order"]["status"] == broker_status
    assert client.get("/api/portfolio").json()["fills"] == []


@pytest.mark.parametrize("defect", ["missing_stop", "wrong_stop", "wrong_tif", "extended_hours"])
def test_unverified_protection_or_parent_terms_preserve_submission_lock(bridge, defect):
    client, app, broker, now, cfg, sid = bridge
    p = preview(client).json()
    original = broker.submit
    def wrong(session, order):
        response = original(session, order)
        if defect == "missing_stop":
            response["legs"] = []
        elif defect == "wrong_stop":
            response["legs"][0]["stop_price"] = "99"
        elif defect == "wrong_tif":
            response["time_in_force"] = "day"
        else:
            response["extended_hours"] = True
        broker.receipts[order["client_order_id"]] = response
        return response
    broker.submit = wrong
    result = submit(client, p["preview_id"]).json()
    assert result["state"] == "reconciliation_needed"
    if defect in {"missing_stop", "wrong_stop"}:
        assert result["order"]["protection_status"] == "unverified"
    assert preview(client).json()["error"]["code"] == "reconciliation_needed"
    assert len(broker.submissions) == 1


def test_conflicting_duplicate_fill_in_one_refresh_persists_nothing(bridge):
    client, app, broker, now, cfg, sid = bridge
    broker.fill_data = [fill(), fill(price="50")]
    result = client.get("/api/portfolio")
    assert result.status_code == 409 and result.json()["error"]["code"] == "fill_reconciliation_needed"
    session = app.state.store.session(sid, now[0])
    assert app.state.store.fills(session)[0] == []


def test_nested_order_lookup_requests_verified_broker_id_only(tmp_path):
    cfg = make_config(tmp_path)
    calls = []
    broker_id = "39c489ad-fcb1-42b3-9f62-e14c11c62157"
    def transport(request):
        calls.append(request)
        if request.url.path.endswith("by_client_order_id"):
            return httpx.Response(200, json={"id": broker_id, "order_class": "oto", "legs": None})
        assert request.url.path == "/v2/orders/" + broker_id
        assert request.url.params["nested"] == "true"
        return httpx.Response(200, json={"id": broker_id, "legs": [{"id": "stop"}]})
    adapter = Alpaca(cfg, transport=httpx.MockTransport(transport))
    result = adapter.order_by_client_id({"mode": "paper", "token": "owned"}, "spicy-example")
    assert result["legs"] and len(calls) == 2


def test_non_stock_account_is_explicit_and_pending_option_cash_is_not_guessed(bridge):
    client, app, broker, now, cfg, sid = bridge
    broker.fill_data = [fill(symbol="AAPL261001C00100000")]
    assert client.get("/api/portfolio").json()["error"]["code"] == "supported_stock_account_required"
    broker.order_data = [{"id": "option", "symbol": "AAPL261001C00100000", "asset_class": "us_option", "side": "buy", "qty": "1", "filled_qty": "0", "limit_price": "5"}]
    assert preview(client).json()["error"]["code"] == "unsupported_pending_order"


def test_portfolio_does_not_stamp_stale_clock_or_future_execution_as_fresh(bridge):
    client, app, broker, now, cfg, sid = bridge
    broker.clock_offset = -31
    assert client.get("/api/portfolio").json()["error"]["code"] == "clock_stale"
    broker.clock_offset = 0
    broker.fill_data = [fill(transaction_time="2026-09-08T14:01:00Z")]
    assert client.get("/api/portfolio").json()["error"]["code"] == "fill_invalid"
