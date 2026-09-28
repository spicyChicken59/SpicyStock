"""Lossless decimal lineage for frozen historical pages; never fetches data.

Raw pages remain the authority. Invalid rows are retained by page/row identity
and make that symbol unresolved. Stable last-arrival duplicate selection matches
the producer, but every original row remains reachable. No session is invented.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import hashlib
import json
import math
from zoneinfo import ZoneInfo

from src import sessions

VERSION = "historical-normalization-v1"
FIELDS = {"o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume"}
BASIS = ("symbols", "start", "end", "asof", "feed", "timeframe", "adjustment", "currency", "sort", "limit")


def _decimal(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError("missing or boolean number")
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("nonfinite number")
    return result


def _stamp(value):
    if not isinstance(value, str):
        raise ValueError("timestamp is not a string")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timestamp has no timezone")
    return result


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def normalize_pages(pages, *, query, terminal, target_session, required_sessions=None):
    """Return auditable rows/status; no agreement or completeness from HTTP 200.

    Each page supplies raw bytes, sha256, query, query_id and page_index. The
    acquisition ledger, not the caller's HTTP status, establishes terminal.
    Query parameters must stay identical across a pagination chain.
    """
    if (query.get("feed"), query.get("timeframe"), query.get("adjustment"), query.get("currency")) != (
            "sip", "1Day", "split", "USD"):
        raise ValueError("canonical SIP/1Day/split/USD basis required")
    date.fromisoformat(query["asof"])
    symbols = query["symbols"]
    if isinstance(symbols, str):
        symbols = symbols.split(",")
    if symbols != sorted(set(symbols)) or not symbols:
        raise ValueError("symbols must be canonical and nonempty")
    target = date.fromisoformat(target_session)
    if not sessions.is_session(target):
        raise ValueError("target is not an exchange session")
    start, end = _stamp(query["start"]), _stamp(query["end"])
    calendar = sessions.dates(start.date(), target)
    required = [date.fromisoformat(str(d)) for d in (required_sessions or calendar)]
    if required != sorted(set(required)) or any(d > target or not sessions.is_session(d) for d in required):
        raise ValueError("invalid required session window")
    records = {symbol: [] for symbol in symbols}
    issues = {symbol: [] for symbol in symbols}
    seen_pages, page_hashes, chain_id = set(), [], None
    previous_token = None
    seen_tokens = set()
    for page_number, page in enumerate(pages):
        if page["page_index"] != page_number:
            raise ValueError("interrupted or reordered pagination")
        if chain_id is None:
            chain_id = page["query_id"]
        if chain_id != page["query_id"] or any(page["query"].get(k) != query.get(k) for k in BASIS):
            raise ValueError("mixed query or symbol/asof/adjustment basis")
        if "request_token" in page and page["request_token"] != (previous_token or ""):
            raise ValueError("pagination request token does not follow prior response")
        raw = page["raw"]
        digest = hashlib.sha256(raw).hexdigest()
        if digest != page["sha256"] or digest in seen_pages:
            raise ValueError("changed or duplicated raw page")
        seen_pages.add(digest)
        page_hashes.append(digest)
        body = json.loads(raw, parse_float=Decimal, parse_int=Decimal,
                          object_pairs_hook=_unique_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
        if not isinstance(body, dict) or not isinstance(body.get("bars"), dict) or "next_page_token" not in body:
            raise ValueError("malformed page envelope")
        if page_number and previous_token is None:
            raise ValueError("page follows terminal token")
        token = body["next_page_token"]
        if token is not None and (not isinstance(token, str) or not token or token in seen_tokens):
            raise ValueError("invalid or cyclic pagination token")
        if token is not None:
            seen_tokens.add(token)
        previous_token = token
        for symbol, rows in body["bars"].items():
            if symbol not in records or not isinstance(rows, list):
                raise ValueError("unexpected symbol or malformed bars")
            for row_number, row in enumerate(rows):
                identity = {"page_sha256": digest, "page_index": page_number, "row_index": row_number,
                            "symbol": symbol}
                try:
                    stamp = _stamp(row["t"])
                    local = stamp.astimezone(ZoneInfo("America/New_York"))
                    if not start <= stamp <= end or local.time().isoformat() != "00:00:00":
                        raise ValueError("timestamp outside request or not NY daily midnight")
                    day = local.date()
                    if day > target or not sessions.is_session(day):
                        raise ValueError("unexpected session")
                    values = {name: _decimal(row[field]) for field, name in FIELDS.items()}
                    o, h, l, c, v = (values[name] for name in FIELDS.values())
                    if min(o, h, l, c) <= 0 or v < 0 or not l <= min(o, c) <= max(o, c) <= h:
                        raise ValueError("invalid price/volume or OHLC geometry")
                    # Distinct raw timestamps for one local session are not folded.
                    records[symbol].append({"session": str(day), "timestamp": row["t"],
                                            "values": {k: str(v) for k, v in values.items()},
                                            "source": identity})
                except (KeyError, TypeError, ValueError, InvalidOperation):
                    issues[symbol].append({"source": identity, "reason": "invalid value, OHLC geometry, or session timestamp"})
    if terminal and (not pages or previous_token is not None):
        raise ValueError("terminal claim conflicts with retained pagination")
    result = {}
    for symbol, rows in records.items():
        selected, duplicates = {}, []
        for row in rows:
            stamp = _stamp(row["timestamp"])
            if stamp in selected:
                duplicates.append({"discarded": selected[stamp]["source"], "selected": row["source"],
                                   "rule": "stable last arrival, exact timestamp"})
            selected[stamp] = row
        normalized = [selected[k] for k in sorted(selected)]
        observed = {date.fromisoformat(r["session"]) for r in normalized}
        missing = [str(d) for d in required if d not in observed]
        anchors = [sessions.previous_session(target), target]
        missing_anchors = [str(d) for d in anchors if d not in observed]
        status = ("unresolved" if issues[symbol] else "partial" if not terminal and rows else
                  "requested" if not terminal else "absent" if not rows else
                  "partial" if missing else "returned_with_bars")
        result[symbol] = {"status": status, "returned_rows": len(rows), "selected_rows": len(normalized),
                          "rows": normalized, "duplicates": duplicates, "invalid_rows": issues[symbol],
                          "missing_required_sessions": missing, "missing_anchors": missing_anchors,
                          "complete_required_window": terminal and bool(rows) and not missing and not issues[symbol]}
    return {"version": VERSION, "query_id": chain_id, "query": query, "terminal": terminal,
            "target_session": target_session, "page_sha256": page_hashes, "symbols": result,
            "normalization": ["JSON numeric lexemes to Decimal", "validate NY daily timestamp and XNYS session",
                              "validate OHLC geometry and finite positive prices/nonnegative share volume",
                              "stable sort exact timestamps; select last duplicate and retain both identities",
                              "no forward fill, no rounding, no fabricated bars"],
            "original_information_set": False, "reader_reviews_reusable": False,
            "publication_allowed": False}


def frames_for_replay(normalized):
    """Explicit float64 adapter; decimal strings and wire hashes remain retained.

    Invalid symbols cannot enter the replay. Partial histories may enter with
    real holes; the reference then emits unknown, matching measured denominators.
    """
    import pandas as pd
    frames, conversions = {}, []
    for symbol, record in normalized["symbols"].items():
        if record["invalid_rows"]:
            continue
        rows = record["rows"]
        if not rows:
            continue
        for row in rows:
            for field, value in row["values"].items():
                float_value = float(value)
                if not math.isfinite(float_value) or (field != "Volume" and float_value <= 0):
                    raise ValueError("decimal value cannot be represented safely in production float64")
                if Decimal.from_float(float_value) != Decimal(value):
                    conversions.append({"symbol": symbol, "session": row["session"], "field": field,
                                        "decimal": value, "float64_hex": float_value.hex()})
        frames[symbol] = pd.DataFrame([{k: float(v) for k, v in r["values"].items()} for r in rows],
                                     index=pd.to_datetime([r["timestamp"] for r in rows], utc=True))
    return frames, {"operation": "explicit production float64 projection; never claim wire precision",
                    "inexact_conversions": conversions}


def decimal_event_audit(normalized):
    """Compare exact-decimal event boundaries against the declared float adapter.

    A disagreement is a representation observation, not automatically a producer
    defect. The selected production formula deliberately uses binary floats.
    """
    target = date.fromisoformat(normalized["target_session"])
    days = sessions.sessions_before(target, 9) + [target]
    differences, compared, unknown = [], 0, 0
    for symbol, record in normalized["symbols"].items():
        rows = {r["session"]: r["values"] for r in record["rows"]}
        for day in days:
            current, prior = rows.get(str(day)), rows.get(str(sessions.previous_session(day)))
            if not current or not prior or record["invalid_rows"]:
                unknown += 1
                continue
            c, c1, v, v1 = (Decimal(x) for x in (current["Close"], prior["Close"], current["Volume"], prior["Volume"]))
            # Multiplication compares exact ratios without finite decimal division.
            pc, pp = Fraction(c), Fraction(c1)
            exact = {"up4": 100*(pc-pp) >= 4*pp and v >= 100000 and v > v1,
                     "down4": 100*(pc-pp) <= -4*pp and v >= 100000 and v > v1}
            cf, pf, vf, pvf = map(float, (c, c1, v, v1))
            floating = {"up4": 100*(cf-pf)/pf >= 4 and vf >= 100000 and vf > pvf,
                        "down4": 100*(cf-pf)/pf <= -4 and vf >= 100000 and vf > pvf}
            compared += 1
            if exact != floating:
                differences.append({"symbol": symbol, "session": str(day), "wire_decimal": exact,
                                    "production_float64": floating,
                                    "values": {"close": str(c), "prior_close": str(c1),
                                               "volume_shares": str(v), "prior_volume_shares": str(v1)}})
    return {"status": "PASS", "comparison": "exact-decimal versus production-float64 event boundaries",
            "compared_cells": compared, "unknown_cells": unknown, "differences": differences,
            "scope": "last ten-session up/down events; representation differences are observations, not software verdicts"}
