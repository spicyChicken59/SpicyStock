"""Private same-origin application. No broker action runs until a user confirms a preview."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import secrets
import time
from urllib.parse import urlencode, urlsplit

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.concurrency import run_in_threadpool

from .alpaca import Alpaca, BrokerError
from .config import Config
from .domain import (Rejected, require, number, symbol, broker_symbol, timestamp, iso, checked_account, checked_quote,
                     source_setup, previous_session, size_order, clean_order, clean_position,
                     clean_fill, TERMINAL, PROTECTION_NOTE)
from .store import Store

COOKIE = "__Host-spicy-session"
OAUTH_COOKIE = "__Host-spicy-oauth"


def create_app(config=None, adapter=None, now=None):
    config = config or Config.from_env()
    now = now or time.time
    store = Store(config.database, config.encryption_key) if config.configured else None
    broker = adapter or Alpaca(config)
    app = FastAPI(title="SpicyStock private broker bridge", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store, app.state.broker, app.state.config = store, broker, config
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[urlsplit(config.origin).hostname])

    @app.middleware("http")
    async def security_headers(request, call_next):
        if request.method not in {"GET", "HEAD"}:
            if request.headers.get("origin") != config.origin:
                return JSONResponse({"error": {"code": "origin_rejected", "message": "Use the private app's own origin."}}, status_code=403)
            if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
                return JSONResponse({"error": {"code": "json_required", "message": "A JSON request is required."}}, status_code=415)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
        response.headers["Content-Security-Policy"] = "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response

    @app.exception_handler(Rejected)
    async def rejection(request, exc):
        return JSONResponse({"error": {"code": exc.code, "message": exc.message}}, status_code=exc.status)

    @app.exception_handler(BrokerError)
    async def broker_failure(request, exc):
        return JSONResponse({"error": {"code": exc.code, "message": "The broker could not confirm this request. Refresh the account before continuing."}}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_failure(request, exc):
        return JSONResponse({"error": {"code": "invalid_request", "message": "The request is incomplete or invalid."}}, status_code=422)

    def auth(request, mutate=False):
        require(store is not None, "unconfigured", "The private broker service has not been configured.", 503)
        session = store.session(request.cookies.get(COOKIE), now())
        require(session is not None, "not_connected", "Connect your broker account to continue.", 401)
        if mutate:
            csrf = request.headers.get("x-csrf-token", "")
            require(bool(csrf) and secrets.compare_digest(csrf, session["csrf"]), "csrf_rejected", "Refresh the private app before trying again.", 403)
        return session

    async def body(request, keys, required):
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            require(len(raw) <= 8192, "request_too_large", "This request is too large.", 413)
        try:
            values = json.loads(raw)
        except ValueError:
            raise Rejected("invalid_json", "A valid JSON request is required.", 422) from None
        require(isinstance(values, dict) and set(values) <= set(keys) and set(required) <= set(values),
                "invalid_request", "The request contains missing or unsupported fields.", 422)
        return values

    def account_summary(raw):
        require(isinstance(raw, dict) and isinstance(raw.get("id"), str), "account_invalid", "The broker account response is incomplete.")
        return {"id": raw["id"], "label": "Alpaca · " + raw["id"][-4:],
                "cash": float(number(raw.get("cash"), "cash", False)), "equity": float(number(raw.get("equity"), "equity", False)),
                "currency": raw.get("currency"), "trading_blocked": raw.get("trading_blocked") is not False or raw.get("account_blocked") is not False}

    def get_quote(session, sym):
        raw, feed = broker.quote(session, sym)
        return checked_quote(raw, feed, sym, now())

    def receipt(record, message=None):
        status = "reconciliation_needed" if record["state"] in {"sending", "unknown"} else "rejected" if record["state"] in {"rejected", "expired", "canceled"} else "accepted"
        order_status = (record["result"] or {}).get("status")
        if status != "reconciliation_needed" and order_status in {"canceled", "expired", "filled", "partially_filled", "rejected"}:
            status = order_status
        messages = {
            "reconciliation_needed": "Submission is not yet confirmed. Refresh to reconcile; do not place a replacement order.",
            "accepted": "Broker order receipt received. Only confirmed execution activities appear as fills.",
            "filled": "The broker reports the order filled. Refresh the account to sync its confirmed execution activities.",
            "partially_filled": "The broker reports a partial fill. Review the remaining order and protective stop at the broker; refresh for confirmed executions.",
            "canceled": "The broker reports this order canceled. Earlier partial executions, if any, are retained in confirmed fills.",
            "expired": "The broker reports this order expired. Earlier partial executions, if any, are retained in confirmed fills.",
            "rejected": "This preview was not placed. Prepare a fresh order after reviewing the reason.",
        }
        return {"state": status, "preview_id": record["id"], "client_order_id": record["client_order_id"],
                "order": record["result"], "message": message or messages[status]}

    def verified_receipt(raw, record):
        p = record["payload"]
        require(isinstance(raw, dict) and raw.get("client_order_id") == record["client_order_id"]
                and raw.get("symbol") == p["symbol"] and raw.get("side") == "buy"
                and raw.get("type") == "limit" and raw.get("order_class") == "oto"
                and raw.get("time_in_force") == "gtc" and raw.get("extended_hours") is False
                and number(raw.get("qty")) == number(p["qty"])
                and number(raw.get("limit_price")) == number(p["limit_price"]),
                "order_identity_invalid", "The broker receipt could not be matched to the confirmed order.")
        clean = clean_order(raw)
        if clean["status"] in {"rejected", "canceled", "expired"} and (clean["filled_qty"] or 0) == 0:
            clean["protection_status"] = "not_needed_no_fill"
            return clean
        legs = clean["legs"]
        protected = len(legs) == 1 and legs[0]["symbol"] == p["symbol"] and legs[0]["side"] == "sell" and legs[0]["type"] == "stop" and legs[0]["qty"] == p["qty"] and legs[0]["stop_price"] == p["stop_price"] and legs[0]["time_in_force"] == "gtc" and legs[0]["status"] not in {"canceled", "expired", "rejected", "replaced"}
        clean["protection_status"] = "broker_stop_verified" if protected else "unverified"
        return clean

    def reconcile(session, record):
        if record["state"] not in {"sending", "unknown", "accepted"}:
            return record
        try:
            raw = broker.order_by_client_id(session, record["client_order_id"])
            if raw is not None:
                order = verified_receipt(raw, record)
                state = "unknown" if order["protection_status"] == "unverified" else "rejected" if order["status"] == "rejected" else "confirmed" if order["status"] in TERMINAL else "accepted"
                store.update(record["id"], state, order)
                return {**record, "state": state, "result": order}
        except (BrokerError, Rejected):
            pass
        # A GET 404 after a timeout is not proof that the POST failed. Keep the lock.
        if record["state"] in {"sending", "unknown"}:
            store.update(record["id"], "unknown", record["result"])
            return {**record, "state": "unknown"}
        return record

    def trade_inputs(session, values, ignore_preview=None):
        sym = symbol(values.get("symbol"))
        max_positions = values.get("max_positions", config.max_positions)
        require(isinstance(max_positions, int) and not isinstance(max_positions, bool) and 1 <= max_positions <= config.max_positions,
                "position_cap_invalid", "Choose a position cap within this account's configured limit.", 422)
        require(sym in config.common_stock_symbols, "common_stock_verification_required", "This symbol is outside the curated common-stock trading scope.")
        account = broker.account(session)
        cash, equity = checked_account(account, session, config)
        clock = broker.clock(session)
        end = datetime.fromtimestamp(now(), timezone.utc).date()
        calendar = broker.calendar(session, (end - timedelta(days=14)).isoformat(), end.isoformat())
        prior = previous_session(calendar, clock, now())
        source = source_setup(config.docs / "data.json", sym, prior)
        asset = broker.asset(session, sym)
        require(isinstance(asset, dict) and asset.get("symbol") == sym and asset.get("class") == "us_equity"
                and asset.get("status") == "active" and asset.get("tradable") is True
                and asset.get("exchange") in {"NYSE", "NASDAQ", "AMEX", "ARCA", "BATS", "NYSEARCA"},
                "asset_unavailable", "This asset is not an active tradable US-listed stock.")
        positions, orders = broker.positions(session), broker.orders(session)
        require(isinstance(positions, list) and isinstance(orders, list) and all(isinstance(p, dict) for p in positions + orders) and len(orders) < 500, "portfolio_incomplete", "The complete portfolio and open order list could not be verified.")
        require(not any(p.get("symbol") == sym and number(p.get("qty"), "position quantity", False) != 0 for p in positions),
                "position_exists", "This account already holds this stock. Review the existing position.")
        require(not any(o.get("symbol") == sym for o in orders), "order_exists", "This account already has an open order for this stock.")
        # Cash is not the same as margin buying power. Reserve other pending buy limits.
        reserved = Decimal(0)
        occupied_symbols = {broker_symbol(p["symbol"]) for p in positions if number(p.get("qty"), "position quantity", False) != 0}
        seen_ids = set()
        for order in orders:
            require(isinstance(order, dict) and isinstance(order.get("id"), str), "portfolio_incomplete", "An open order cannot be verified.")
            if order["id"] in seen_ids:
                continue
            seen_ids.add(order["id"])
            if order.get("side") == "buy":
                require(order.get("asset_class", "us_equity") == "us_equity", "unsupported_pending_order", "Resolve the pending non-stock buy before preparing a stock entry; its cash reservation cannot be verified here.")
                occupied_symbols.add(broker_symbol(order.get("symbol")))
                require(order.get("limit_price") is not None, "pending_market_order", "Wait for the pending market order to settle before preparing another entry.")
                remaining = max(Decimal(0), number(order.get("qty"), "order quantity") - number(order.get("filled_qty", 0), "filled quantity", False))
                reserved += remaining * number(order["limit_price"], "pending limit")
        for p in store.pending(session):
            if p["id"] == ignore_preview:
                continue
            require(p["state"] not in {"sending", "unknown"}, "reconciliation_needed", "Resolve the previous broker submission before preparing another order.")
            if p["state"] == "accepted":
                occupied_symbols.add(p["symbol"])
            if p["state"] == "accepted" and not any(o.get("client_order_id") == p["client_order_id"] for o in orders):
                require(p["symbol"] != sym, "order_exists", "An accepted order for this stock still needs reconciliation.")
                reserved += number(p["payload"]["position_dollars"])
        require(len(occupied_symbols) < max_positions, "position_cap_reached", "The account has reached its position limit, including pending entries.")
        quote = get_quote(session, sym)
        require(quote["fresh"], "quote_stale", "A quote no older than 30 seconds is required. Refresh before trading.")
        require(session["mode"] != "live" or quote["feed"] == "sip", "live_feed_required", "Live trading requires a fresh consolidated SIP quote.")
        sized = size_order(values, config, max(Decimal(0), cash - reserved), equity, quote)
        return {"symbol": sym, "mode": session["mode"], "account_label": account_summary(account)["label"],
                "account_id": session["account_id"], "max_positions": max_positions, **sized, "quote": quote,
                "source_session": source["session"], "source_sha256": source["snapshot_sha256"],
                "order_type": "limit + protective stop", "time_in_force": "gtc", "protection_note": PROTECTION_NOTE}

    @app.get("/trading-config.json")
    def trading_config():
        return {"version": 1, "enabled": True, "api_base": "/api", "broker": "alpaca"}

    @app.get("/api/status")
    def status(request: Request):
        session = store.session(request.cookies.get(COOKIE), now()) if store else None
        unresolved = [p for p in store.pending(session) if p["state"] in {"sending", "unknown"}] if session else []
        result = {"version": 1, "configured": config.configured, "connected": bool(session),
                  "state": "unconfigured" if not store else "not_connected" if not session else "reconciliation_needed" if unresolved else session["mode"],
                  "mode": session["mode"] if session else None, "live_enabled": config.live_enabled,
                  "limits": {"max_positions": config.max_positions, "max_risk_percent": float(config.max_risk_percent), "max_position_percent": float(config.max_position_percent), "max_notional": float(config.max_notional)}}
        if session:
            result["csrf_token"] = session["csrf"]
        return result

    @app.get("/api/connect")
    def connect(request: Request, mode: str = "paper"):
        require(store is not None, "unconfigured", "Broker connection is not configured on this private app.", 503)
        require(mode in {"paper", "live"}, "invalid_mode", "Choose paper or live trading.", 422)
        require(mode != "live" or config.live_enabled, "live_disabled", "Live account connection is disabled on this app.", 403)
        require(request.headers.get("sec-fetch-site") != "cross-site", "origin_rejected", "Start the connection from the private app.", 403)
        state, binding = store.oauth_begin(mode, now())
        response = RedirectResponse("https://app.alpaca.markets/oauth/authorize?" + urlencode({
            "response_type": "code", "client_id": config.client_id, "redirect_uri": config.redirect_uri,
            "state": state, "scope": "trading data", "env": mode,
        }), status_code=302)
        response.set_cookie(OAUTH_COOKIE, binding, max_age=300, secure=True, httponly=True, samesite="lax", path="/")
        return response

    @app.get("/api/oauth/callback")
    def callback(request: Request, state: str = "", code: str = "", error: str = ""):
        require(store is not None, "unconfigured", "Broker connection is not configured.", 503)
        mode = store.oauth_consume(state, request.cookies.get(OAUTH_COOKIE, ""), now())
        require(mode is not None, "oauth_state_invalid", "The connection expired or belongs to a different browser. Start again.", 403)
        require(not error and bool(code) and len(code) <= 4096, "oauth_denied", "The broker connection was not approved.", 403)
        token = broker.exchange(code)
        raw = broker.account({"token": token, "mode": mode})
        require(isinstance(raw, dict) and isinstance(raw.get("id"), str) and bool(raw["id"]), "account_invalid", "The broker account could not be verified.")
        require(mode != "live" or raw["id"] in config.live_account_ids, "live_account_denied", "This live account is not enabled on this private app.", 403)
        sid, _ = store.session_create(mode, token, raw["id"], now(), config.session_seconds)
        old = store.session(request.cookies.get(COOKIE), now())
        if old:
            # Rotate the browser identity without destroying a newly created session for the same account.
            with store.db() as db:
                db.execute("DELETE FROM sessions WHERE id=?", (old["id"],))
        response = RedirectResponse("/#trade-workspace", status_code=303)
        response.delete_cookie(OAUTH_COOKIE, path="/", secure=True, httponly=True, samesite="lax")
        response.set_cookie(COOKIE, sid, max_age=config.session_seconds, secure=True, httponly=True, samesite="lax", path="/")
        return response

    @app.post("/api/disconnect")
    async def disconnect(request: Request):
        session = auth(request, True)
        await body(request, (), ())
        store.disconnect(session)
        response = JSONResponse({"state": "not_connected", "connected": False,
                                 "message": "This app's stored connection was removed. Broker orders remain active; revoke the app at Alpaca to remove broker-side authorization."})
        response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="lax")
        return response

    @app.get("/api/quote")
    def quote(request: Request, symbol: str):
        session = auth(request)
        from .domain import symbol as validate_symbol
        return get_quote(session, validate_symbol(symbol))

    @app.get("/api/portfolio")
    def portfolio(request: Request):
        session = auth(request)
        account, clock = broker.account(session), broker.clock(session)
        require(isinstance(account, dict) and account.get("id") == session["account_id"], "account_changed", "The connected account changed. Reconnect.")
        require(isinstance(clock, dict) and abs(now() - timestamp(clock.get("timestamp")).timestamp()) <= 30, "clock_stale", "The broker account clock is stale. Refresh before continuing.")
        positions, orders = broker.positions(session), broker.orders(session)
        require(isinstance(positions, list) and isinstance(orders, list) and all(isinstance(p, dict) for p in positions + orders), "portfolio_invalid", "The broker portfolio is incomplete.")
        pending = [reconcile(session, p) for p in store.pending(session)]
        unresolved = [{"preview_id": p["id"], "client_order_id": p["client_order_id"], "state": p["state"]}
                      for p in pending if p["state"] in {"sending", "unknown"}]
        token, fills, complete, seen = None, [], False, {}
        for _ in range(5):
            page = broker.fill_page(session, token)
            require(isinstance(page, list) and len(page) <= 100, "fills_invalid", "The broker fill history is incomplete.")
            for raw in page:
                f = clean_fill(raw, session["mode"])
                require(timestamp(f["transaction_time"]).timestamp() <= now() + 5, "fill_invalid", "The broker returned an execution timestamp in the future.")
                require(f["id"] not in seen or seen[f["id"]] == f, "fill_reconciliation_needed", "The broker returned conflicting versions of one execution. Reconcile with the broker statement.")
                if f["id"] not in seen:
                    fills.append(f)
                    seen[f["id"]] = f
            if len(page) < 100:
                complete = True
                break
            next_token = page[-1]["id"]
            require(next_token != token, "fill_pagination_stalled", "Broker fill pagination stalled. Refresh before continuing.")
            token = next_token
        try:
            store.save_fills(session, fills)
        except ValueError:
            raise Rejected("fill_reconciliation_needed", "A previously recorded broker activity changed. Reconcile it with your broker statement.") from None
        saved, truncated = store.fills(session)
        return {"version": 1, "state": "reconciliation_needed" if unresolved else "degraded" if len(orders) >= 500 else session["mode"],
                "mode": session["mode"], "as_of": iso(now()), "account": account_summary(account),
                "clock": {k: clock.get(k) for k in ("timestamp", "is_open", "next_open", "next_close")},
                "positions": [clean_position(p) for p in positions], "pending_orders": [clean_order(o) for o in orders],
                "fills": saved, "fills_truncated": truncated or not complete, "fills_complete_since": None,
                "fills_window": "Latest 500 execution activities checked per refresh; up to 2,000 stored activities shown. Not a complete account statement.",
                "unresolved": unresolved}

    @app.post("/api/preview")
    async def preview(request: Request):
        session = auth(request, True)
        values = await body(request, ("symbol", "limit_price", "stop_price", "risk_percent", "cash_cap", "max_positions"),
                            ("symbol", "limit_price", "stop_price", "risk_percent"))
        payload = await run_in_threadpool(trade_inputs, session, values)
        record = store.preview_create(session, payload, now(), config.preview_seconds)
        return {**payload, "preview_id": record["id"], "expires_at": iso(record["expires"])}

    @app.post("/api/orders")
    async def submit(request: Request):
        session = auth(request, True)
        values = await body(request, ("preview_id", "confirmation"), ("preview_id", "confirmation"))
        require(values["confirmation"] == "submit" and isinstance(values["preview_id"], str), "confirmation_required", "Review and explicitly confirm this exact order.", 422)
        state, record = store.claim(session, values["preview_id"], now())
        require(state != "missing", "preview_missing", "This preview does not belong to the connected browser account.", 404)
        require(state != "expired", "preview_expired", "The 30-second preview expired. Refresh the quote and prepare again.")
        require(state != "unresolved", "reconciliation_needed", "A previous submission is unresolved. Refresh the account before continuing.")
        if state == "existing":
            return receipt(await run_in_threadpool(reconcile, session, record))
        p = record["payload"]
        try:
            fresh = await run_in_threadpool(trade_inputs, session, p, ignore_preview=record["id"])
            require(now() < record["expires"], "preview_expired", "The preview expired while rechecking the account. Prepare again.")
            require(fresh["account_id"] == p["account_id"] and fresh["mode"] == p["mode"]
                    and fresh["source_sha256"] == p["source_sha256"], "preview_changed", "The account or source scan changed. Prepare a new preview.")
            require(fresh["qty"] >= p["qty"] and fresh["risk_budget"] >= p["risk_dollars"], "funds_changed", "Cash or risk capacity changed. Prepare a new preview.")
        except (Rejected, BrokerError):
            store.update(record["id"], "rejected")
            raise
        order = {"symbol": p["symbol"], "qty": str(p["qty"]), "side": "buy", "type": "limit",
                 "limit_price": str(p["limit_price"]), "time_in_force": "gtc", "extended_hours": False,
                 "order_class": "oto", "stop_loss": {"stop_price": str(p["stop_price"])},
                 "client_order_id": record["client_order_id"]}
        try:
            raw = await run_in_threadpool(broker.submit, session, order)
            clean = verified_receipt(raw, record)
            accepted_state = "unknown" if clean["protection_status"] == "unverified" else "rejected" if clean["status"] == "rejected" else "confirmed" if clean["status"] in TERMINAL else "accepted"
            store.update(record["id"], accepted_state, clean)
            saved = {**record, "state": accepted_state, "result": clean}
            if accepted_state == "unknown":
                saved = await run_in_threadpool(reconcile, session, saved)
            return receipt(saved)
        except BrokerError as exc:
            if not exc.uncertain:
                store.update(record["id"], "rejected")
                return receipt({**record, "state": "rejected", "result": None}, "The broker rejected the order. Review your account before preparing another.")
        except Rejected:
            pass
        store.update(record["id"], "unknown")
        return receipt(await run_in_threadpool(reconcile, session, {**record, "state": "unknown", "result": None}))

    # Mount last so API/config routes always win. This serves only the checked-in public assets.
    app.mount("/", StaticFiles(directory=config.docs, html=True, check_dir=False), name="dashboard")
    return app
