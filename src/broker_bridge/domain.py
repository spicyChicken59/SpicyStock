"""Deterministic trade checks; model scores cannot override these checks."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from hashlib import sha256
import json
import re

SYMBOL = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")
TERMINAL = {"filled", "canceled", "expired", "rejected", "replaced"}
PROTECTION_NOTE = ("The broker activates the stop only after the entry fully fills; partial fills may remain "
                   "unprotected. Stops execute during regular market hours and can fill below the stop price. "
                   "The entry and stop are good until canceled; monitor unfilled entries and protection at the broker.")


class Rejected(Exception):
    def __init__(self, code, message, status=409):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


def require(ok, code, message, status=409):
    if not ok:
        raise Rejected(code, message, status)


def number(value, label="number", positive=True):
    try:
        require(not isinstance(value, bool) and value is not None, "invalid_number", f"Invalid {label}.", 422)
        result = Decimal(str(value))
        require(result.is_finite() and abs(result) <= Decimal("1e15") and (not positive or result > 0), "invalid_number", f"Invalid {label}.", 422)
        return result
    except (InvalidOperation, ValueError, TypeError):
        raise Rejected("invalid_number", f"Invalid {label}.", 422) from None


def symbol(value):
    require(isinstance(value, str) and bool(SYMBOL.fullmatch(value)), "invalid_symbol", "Choose one supported US stock symbol.", 422)
    return value


def broker_symbol(value):
    require(isinstance(value, str) and bool(SYMBOL.fullmatch(value)), "supported_stock_account_required", "This connected workflow supports stock accounts. The broker returned an unsupported non-stock symbol.")
    return value


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        require(parsed.tzinfo is not None, "invalid_timestamp", "Broker timestamp has no timezone.")
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError):
        raise Rejected("invalid_timestamp", "Broker timestamp is unavailable.") from None


def iso(now):
    return datetime.fromtimestamp(now, timezone.utc).isoformat().replace("+00:00", "Z")


def checked_account(raw, session, config):
    require(isinstance(raw, dict) and raw.get("id") == session["account_id"], "account_changed", "The connected account changed. Reconnect before trading.")
    require(raw.get("status") == "ACTIVE" and raw.get("trading_blocked") is False
            and raw.get("account_blocked") is False and raw.get("trade_suspended_by_user") is not True,
            "account_blocked", "The broker account is not currently able to trade.")
    require(raw.get("currency") == "USD", "unsupported_currency", "This workflow supports USD stock accounts.")
    if session["mode"] == "live":
        require(config.live_enabled and raw["id"] in config.live_account_ids, "live_disabled", "Live orders are disabled for this account.", 403)
    cash = number(raw.get("cash"), "cash", False)
    equity = number(raw.get("equity"), "equity")
    require(cash >= 0, "no_cash", "The account has no available cash for a cash-funded entry.")
    if raw.get("non_marginable_buying_power") is not None:
        cash = min(cash, number(raw["non_marginable_buying_power"], "cash buying power", False))
    return cash, equity


def checked_quote(raw, feed, sym, now):
    require(isinstance(raw, dict) and raw.get("symbol") == sym and isinstance(raw.get("quote"), dict), "quote_missing", "A current broker quote is unavailable.")
    q = raw["quote"]
    bid, ask = number(q.get("bp"), "bid"), number(q.get("ap"), "ask")
    age = now - timestamp(q.get("t")).timestamp()
    require(ask >= bid, "quote_invalid", "The broker quote is crossed or invalid.")
    return {"symbol": sym, "bid": float(bid), "ask": float(ask), "timestamp": q["t"],
            "feed": feed, "age_seconds": round(age, 3), "fresh": -5 <= age <= 30}


def source_setup(path, sym, previous_session):
    try:
        body = path.read_bytes()
        require(len(body) <= 10_000_000, "source_invalid", "The trusted scan snapshot is too large.")
        data = json.loads(body)
        run = data["run"]
        sb = run["stockbee"]
        require(run.get("type") == "evening" and run.get("status") == "ok"
                and run.get("dry_run") is False and run.get("fixture") is False,
                "source_degraded", "A successful real evening scan is required before placing an entry.")
        require(sb.get("version") == 1 and run["date"] == previous_session and sb["date"] == previous_session,
                "source_stale", "Wait for a successful scan of the previous market session.")
        row = next((r for r in sb["scan"]["rows"] if r["ticker"] == sym and r["date"] == previous_session), None)
        require(row is not None, "setup_missing", "This symbol is not in the trusted current 4% scan queue.")
        close, previous = number(row["close"]), number(row["prev_close"])
        require(close >= previous * Decimal("1.04") and number(row["volume"]) > number(row["prev_volume"])
                and number(row["volume"]) >= 100000,
                "setup_invalid", "The source row does not satisfy the base 4% price-volume scan.")
        return {"session": previous_session, "snapshot_sha256": sha256(body).hexdigest(), "close": float(close)}
    except Rejected:
        raise
    except (OSError, ValueError, KeyError, TypeError):
        raise Rejected("source_missing", "A complete trusted 4% scan snapshot is not available yet.") from None


def previous_session(calendar, clock, now):
    require(isinstance(clock, dict) and clock.get("is_open") is True, "market_closed", "Entry orders are available only while the regular market is open.")
    server_time = timestamp(clock.get("timestamp"))
    require(abs(now - server_time.timestamp()) <= 30, "clock_stale", "The broker market clock is stale.")
    today = server_time.astimezone(__import__("zoneinfo").ZoneInfo("America/New_York")).date().isoformat()
    require(isinstance(calendar, list), "calendar_missing", "The broker session calendar is unavailable.")
    days = sorted({r["date"] for r in calendar if isinstance(r, dict) and isinstance(r.get("date"), str) and r["date"] < today})
    require(bool(days) and any(r.get("date") == today for r in calendar), "calendar_missing", "The previous trading session cannot be verified.")
    # The adapter only requests the prior fourteen calendar days, including holidays.
    return days[-1]


def clean_position(raw):
    return {"symbol": broker_symbol(raw.get("symbol")), "side": raw.get("side"), "asset_class": raw.get("asset_class"),
            **{k: float(number(raw.get(k), k, False)) for k in
               ("qty", "avg_entry_price", "current_price", "market_value", "unrealized_pl")}}


def clean_order(raw, depth=0):
    require(isinstance(raw, dict) and isinstance(raw.get("id"), str), "order_invalid", "The broker order response is incomplete.")
    out = {k: raw.get(k) for k in ("id", "client_order_id", "symbol", "side", "type", "status", "order_class",
                                 "time_in_force", "submitted_at", "filled_at", "canceled_at", "expired_at")}
    for k in ("qty", "filled_qty", "filled_avg_price", "limit_price", "stop_price"):
        out[k] = float(number(raw[k], k, False)) if raw.get(k) is not None else None
    out["legs"] = [clean_order(x, depth + 1) for x in (raw.get("legs") or [])] if depth < 2 else []
    return out


def clean_fill(raw, mode):
    require(isinstance(raw, dict) and raw.get("activity_type") == "FILL"
            and isinstance(raw.get("id"), str) and bool(raw["id"])
            and isinstance(raw.get("order_id"), str) and bool(raw["order_id"])
            and raw.get("side") in {"buy", "sell"}, "fill_invalid", "A broker fill could not be verified.")
    timestamp(raw.get("transaction_time"))
    return {"id": raw["id"], "order_id": raw["order_id"], "symbol": broker_symbol(raw.get("symbol")),
            "side": raw["side"], "qty": float(number(raw.get("qty"), "fill quantity")),
            "price": float(number(raw.get("price"), "fill price")), "transaction_time": raw["transaction_time"],
            "source": "alpaca", "mode": mode}


def size_order(values, config, cash, equity, quote):
    entry = number(values.get("limit_price"), "limit price")
    stop = number(values.get("stop_price"), "stop price")
    risk_percent = number(values.get("risk_percent"), "risk percent")
    require(entry >= 1 and stop >= 1 and entry == entry.quantize(Decimal(".01")) and stop == stop.quantize(Decimal(".01")),
            "price_precision", "Use prices of at least $1 in whole cents.", 422)
    require(stop <= min(entry, number(quote["bid"])) - Decimal(".01"), "stop_invalid", "The stop must be at least one cent below both the entry and the current bid.", 422)
    require(risk_percent <= config.max_risk_percent, "risk_limit", "The selected risk exceeds this account's configured limit.", 422)
    ask, bid = number(quote["ask"]), number(quote["bid"])
    require((ask - bid) / ask * 100 <= config.max_spread_percent, "spread_wide", "The current spread is too wide for this entry.")
    require(abs(entry / ask - 1) * 100 <= config.max_limit_deviation_percent, "limit_far_from_quote", "The entry limit is too far from the fresh ask. Review the current price.")
    cap = number(values["cash_cap"], "cash cap") if values.get("cash_cap") is not None else cash
    cap = min(cap, cash, equity * config.max_position_percent / 100, config.max_notional)
    risk_budget = equity * risk_percent / 100
    qty = int(min(risk_budget / (entry - stop), cap / entry).to_integral_value(rounding=ROUND_FLOOR))
    require(qty >= 1, "no_whole_share", "Cash and risk limits do not permit one whole share.")
    return {"qty": qty, "limit_price": float(entry), "stop_price": float(stop), "risk_percent": float(risk_percent),
            "cash_cap": float(cap), "risk_dollars": float(qty * (entry - stop)),
            "position_dollars": float(qty * entry), "risk_budget": float(risk_budget)}
