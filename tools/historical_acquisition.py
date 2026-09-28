"""Fail-closed acquisition for the ONE authorized historical daily-bar study.

No production client or pipeline is imported. The CLI defaults to offline
manifest validation; --acquire additionally needs an external approval document
and the existing ALPACA_API_KEY/ALPACA_SECRET_KEY runtime variables. Approval is
evidence supplied by the operator, not something inferred from credentials.

SQLite commits a request slot and a worst-case body reservation BEFORE HTTP.
A crash during that boundary is charged conservatively and blocks automatic
repetition of the ambiguous request. The OS lock covers the entire acquisition.
Never delete/reset the ledger to resume: the same approved storage directory
and frozen manifest must be reused for this assignment's shared lifetime caps.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from email.utils import parsedate_to_datetime
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import sqlite3
import ssl
import sys
import time
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

SCHEMA = "historical-acquisition-v1"
ASSIGNMENT = "spicystock-historical-input-2026-09-28"
HOST = "data.alpaca.markets"
ENDPOINT = "/v2/stocks/bars"
MAX_REQUESTS = 400
MAX_BYTES = 1024 ** 3
MAX_RATE = 20
DEFAULT_PAGE_BYTES = 8 * 1024 ** 2
TRANSIENT = {408, 429, 500, 502, 503, 504}
SAFE_HEADERS = {"date", "content-type", "content-length", "x-request-id",
                "request-id", "retry-after", "x-ratelimit-limit",
                "x-ratelimit-remaining", "x-ratelimit-reset"}
NY = ZoneInfo("America/New_York")
REPO = Path(__file__).resolve().parents[1]


class AcquisitionError(RuntimeError):
    """Only constant reason codes reach logs; never raw transport exceptions."""


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def symbols_digest(symbols):
    return digest(("\n".join(symbols) + "\n").encode())


def instant(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError
        return result
    except (AttributeError, ValueError, TypeError):
        raise AcquisitionError("invalid_explicit_instant") from None


def _integer(value, low, high, reason):
    if type(value) is not int or not low <= value <= high:
        raise AcquisitionError(reason)
    return value


def _symbols(value):
    if (not isinstance(value, list) or not value or
            any(not isinstance(s, str) or not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-/]{0,19}", s)
                for s in value) or value != sorted(set(value))):
        raise AcquisitionError("invalid_canonical_symbols")
    return value


def validate_manifest(manifest):
    """Validate the frozen scope without inspecting credentials or using HTTP."""
    if manifest.get("schema") != SCHEMA or manifest.get("assignment_id") != ASSIGNMENT:
        raise AcquisitionError("wrong_assignment_or_schema")
    populations = manifest.get("populations", {})
    if set(populations) != {"2026-09-24", "2026-09-25"}:
        raise AcquisitionError("missing_original_populations")
    allowed = {"SPY"}
    for population in populations.values():
        symbols = _symbols(population.get("symbols"))
        if population.get("sha256") != symbols_digest(symbols):
            raise AcquisitionError("population_hash_mismatch")
        allowed.update(symbols)
    limits = manifest.get("limits", {})
    _integer(limits.get("requests"), 1, MAX_REQUESTS, "request_cap_out_of_scope")
    _integer(limits.get("retained_bytes"), 1, MAX_BYTES, "byte_cap_out_of_scope")
    _integer(limits.get("requests_per_minute"), 1, MAX_RATE, "rate_out_of_scope")
    _integer(limits.get("page_bytes"), 1, MAX_BYTES, "page_cap_out_of_scope")
    docs = manifest.get("documentation", {})
    try:
        date.fromisoformat(docs.get("verified_at", ""))
    except (TypeError, ValueError):
        instant(docs.get("verified_at"))
    if (docs.get("stockbars_url") != "https://docs.alpaca.markets/us/reference/stockbars" or
            docs.get("faq_url") != "https://docs.alpaca.markets/us/docs/market-data-faq"):
        raise AcquisitionError("documentation_verification_missing")
    queries = manifest.get("queries")
    if not isinstance(queries, list) or not queries:
        raise AcquisitionError("queries_missing")
    ids = set()
    for query in queries:
        query_id = query.get("id")
        if not isinstance(query_id, str) or not re.fullmatch(r"[a-z0-9_-]{1,80}", query_id) or query_id in ids:
            raise AcquisitionError("invalid_query_identity")
        ids.add(query_id)
        if not set(_symbols(query.get("symbols"))) <= allowed:
            raise AcquisitionError("symbol_outside_retained_union")
        if len(query["symbols"]) > 100:
            raise AcquisitionError("query_symbol_batch_exceeds_100")
        if any(query.get(k) != v for k, v in
               {"feed": "sip", "timeframe": "1Day", "currency": "USD", "sort": "asc"}.items()):
            raise AcquisitionError("noncanonical_request")
        purpose = query.get("purpose")
        if query.get("adjustment") == "split":
            if purpose not in {"canonical", "alternate_asof_discrepancy"}:
                raise AcquisitionError("undeclared_comparison")
        elif query.get("adjustment") == "raw":
            if purpose != "raw_split_discrepancy":
                raise AcquisitionError("undeclared_raw_comparison")
        else:
            raise AcquisitionError("adjustment_out_of_scope")
        if purpose != "canonical" and not query.get("discrepancy_basis"):
            raise AcquisitionError("concrete_discrepancy_required")
        start, end = instant(query.get("start")), instant(query.get("end"))
        if (start > end or start.astimezone(NY).date() < date(2025, 8, 1) or
                end.astimezone(NY).date() > date(2026, 9, 25)):
            raise AcquisitionError("date_envelope_exceeded")
        try:
            mapping_date = date.fromisoformat(query.get("asof", ""))
            if query["asof"] != mapping_date.isoformat():
                raise ValueError
        except (TypeError, ValueError):
            raise AcquisitionError("explicit_asof_required") from None
        _integer(query.get("limit"), 1, 10000, "invalid_page_limit")
        sessions = query.get("required_sessions", manifest.get("required_sessions", {}).get(query.get("required_sessions_ref")))
        if not isinstance(sessions, list) or not sessions or sessions != sorted(set(sessions)):
            raise AcquisitionError("invalid_required_sessions")
        for session in sessions:
            try:
                day = date.fromisoformat(session)
                if (day.isoformat() != session or day.weekday() >= 5 or
                        not start.astimezone(NY).date() <= day <= end.astimezone(NY).date()):
                    raise ValueError
            except (TypeError, ValueError):
                raise AcquisitionError("invalid_required_sessions") from None
        if query.get("scope") not in {"probe", "bulk"}:
            raise AcquisitionError("explicit_probe_or_bulk_scope_required")
        if query["scope"] == "probe" and (
                purpose != "canonical" or len(query["symbols"]) > 3 or
                len(sessions) > 2 or (end - start).total_seconds() > 7 * 86400):
            raise AcquisitionError("access_probe_must_be_small_and_canonical")
    if sum(q["scope"] == "probe" for q in queries) != 1:
        raise AcquisitionError("one_declared_access_probe_required")
    return digest(encode(manifest))


def resolved_query(manifest, query_id):
    """Expand a frozen shared calendar reference without modifying the manifest."""
    query = next((q for q in manifest["queries"] if q["id"] == query_id), None)
    if query is None:
        raise AcquisitionError("unknown_query")
    query = json.loads(encode(query))
    if "required_sessions" not in query:
        query["required_sessions"] = manifest["required_sessions"][query["required_sessions_ref"]]
    return query


def validate_approval(manifest, approval, root):
    """Proof references are mandatory; a path or a credential alone proves none."""
    identity = validate_manifest(manifest)
    if (approval.get("assignment_id") != ASSIGNMENT or
            approval.get("manifest_sha256") != identity):
        raise AcquisitionError("approval_identity_mismatch")
    if approval.get("zero_additional_cost") is not True:
        raise AcquisitionError("zero_additional_cost_unestablished")
    if approval.get("non_public_storage") is not True:
        raise AcquisitionError("private_storage_unestablished")
    for name in ("cost_basis", "sip_daily_entitlement_basis", "retention_rights_basis",
                 "reviewer_retrieval_path", "approved_by"):
        if not isinstance(approval.get(name), str) or not approval[name].strip():
            raise AcquisitionError(name + "_unestablished")
    _integer(approval.get("provider_requests_per_minute"), 1, 1000000,
             "provider_rate_unestablished")
    root = Path(root).resolve()
    if not approval.get("storage_root") or Path(approval["storage_root"]).resolve() != root:
        raise AcquisitionError("storage_approval_mismatch")
    if root == REPO or REPO in root.parents or any((p / ".git").exists() for p in [root, *root.parents]):
        raise AcquisitionError("raw_storage_must_be_outside_git")
    # A symlink within the approved tree must never redirect ledger/raw writes.
    for path in (root, root / "pages", root / "ledger.sqlite3", root / "acquisition.lock"):
        if path.is_symlink():
            raise AcquisitionError("storage_symlink_forbidden")
    return identity


def safe_headers(headers, sensitive=()):
    result = {}
    for key, value in headers.items():
        name = key.lower()
        if name in SAFE_HEADERS:
            clean = str(value)
            for secret in sensitive:
                if secret:
                    clean = clean.replace(secret, "[redacted]")
            if len(clean) <= 256 and all(32 <= ord(c) <= 126 for c in clean):
                result[name] = clean
    return result


@dataclass
class HTTPResult:
    status: int
    headers: dict
    body: bytes


class AlpacaTransport:
    """Exactly one GET, no redirects/proxies/SDK retries/broker endpoint access."""

    def __init__(self):
        key, secret = os.environ.get("ALPACA_API_KEY"), os.environ.get("ALPACA_SECRET_KEY")
        if not key or not secret:
            raise AcquisitionError("secure_runtime_credentials_unavailable")
        self._credentials = (key, secret)

    def __call__(self, params, byte_limit):
        key, secret = self._credentials
        connection = http.client.HTTPSConnection(HOST, timeout=60, context=ssl.create_default_context())
        try:
            connection.request("GET", ENDPOINT + "?" + urlencode(params), headers={
                "APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret,
                "Accept": "application/json", "Accept-Encoding": "identity"})
            response = connection.getresponse()
            headers = safe_headers(dict(response.getheaders()), self._credentials)
            if response.getheader("Content-Encoding", "identity").lower() != "identity":
                raise AcquisitionError("unexpected_content_encoding")
            # Error bodies may echo credentials or sensitive transport details.
            body = response.read(byte_limit + 1) if response.status == 200 else b""
            if len(body) > byte_limit:
                raise AcquisitionError("response_byte_limit_exceeded")
            # Recognize escaped ASCII too; never redact a raw evidence body.
            unescaped = re.sub(rb"\\u00([0-9a-fA-F]{2})", lambda m: bytes([int(m[1], 16)]), body)
            if any(credential.encode() in unescaped for credential in self._credentials):
                raise AcquisitionError("credential_echo_detected")
            return HTTPResult(response.status, headers, body)
        except AcquisitionError:
            raise
        except Exception:
            raise AcquisitionError("transient_transport_failure") from None
        finally:
            connection.close()


@contextmanager
def exclusive_lock(path):
    """Crash-released OS lock, held through HTTP and all pages."""
    handle = path.open("a+b")
    if os.fstat(handle.fileno()).st_size == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise AcquisitionError("another_acquisition_process_holds_lock") from None
    try:
        yield
    finally:
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _strict_object(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("duplicate_json_member")
        result[name] = value
    return result


def _page(body, query):
    """Validate, retaining exact raw bytes; never fill, round or silently repair."""
    try:
        payload = json.loads(body, parse_float=Decimal, object_pairs_hook=_strict_object,
                             parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError):
        raise AcquisitionError("malformed_json") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("bars"), dict) or "next_page_token" not in payload:
        raise AcquisitionError("malformed_page_or_missing_terminal_token")
    token = payload["next_page_token"]
    if token is not None and (not isinstance(token, str) or not token or len(token) > 8192):
        raise AcquisitionError("malformed_page_token")
    bars = payload["bars"]
    if not set(bars) <= set(query["symbols"]):
        raise AcquisitionError("unexpected_symbol")
    count = 0
    for symbol, rows in bars.items():
        if not isinstance(rows, list):
            raise AcquisitionError("malformed_bars")
        for row in rows:
            if not isinstance(row, dict):
                raise AcquisitionError("malformed_bar")
            stamp = instant(row.get("t"))
            local = stamp.astimezone(NY)
            if (not instant(query["start"]) <= stamp <= instant(query["end"]) or
                    local.weekday() >= 5 or (local.hour, local.minute, local.second, local.microsecond) != (0, 0, 0, 0)):
                raise AcquisitionError("wrong_daily_session")
            if "required_sessions" in query and local.date().isoformat() not in query["required_sessions"]:
                raise AcquisitionError("unexpected_exchange_session")
            values = {}
            for field in ("o", "h", "l", "c", "v"):
                value = row.get(field)
                if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
                    raise AcquisitionError("malformed_numeric_value")
                value = Decimal(value)
                if not value.is_finite() or value < 0 or (field != "v" and value == 0):
                    raise AcquisitionError("invalid_price_or_volume")
                values[field] = value
            if not (values["l"] <= min(values["o"], values["c"]) <=
                    max(values["o"], values["c"]) <= values["h"]):
                raise AcquisitionError("invalid_ohlc_geometry")
            count += 1
    if count > query["limit"]:
        raise AcquisitionError("response_exceeds_total_page_limit")
    fingerprint = digest(json.dumps(bars, sort_keys=True, separators=(",", ":"), default=str).encode())
    return payload, fingerprint


class Acquisition:
    def __init__(self, manifest, approval, root, *, transport=None, clock=time.time, sleep=time.sleep):
        self.manifest = json.loads(encode(manifest))
        self.approval = dict(approval)
        self.root = Path(root).resolve()
        self.identity = validate_approval(self.manifest, approval, self.root)
        self.transport = transport
        self.clock, self.sleep = clock, sleep
        self.db = None

    def _open(self):
        self.db = sqlite3.connect(self.root / "ledger.sqlite3")
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY, query_id TEXT, token TEXT, attempt INTEGER,
                timestamp REAL, reservation INTEGER, retained INTEGER DEFAULT 0,
                status TEXT, http_status INTEGER, reason TEXT, headers TEXT,
                body_hash TEXT, fingerprint TEXT, next_token TEXT);
        """)
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('manifest_sha256', ?)", (self.identity,))
            self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('not_before', '0')")
            self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('provider_rate', ?)",
                            (str(min(MAX_RATE, self.approval["provider_requests_per_minute"])),))
        identity = self.db.execute("SELECT value FROM metadata WHERE name='manifest_sha256'").fetchone()[0]
        if identity != self.identity:
            raise AcquisitionError("frozen_manifest_changed")
        # A body written just before a crash remains covered by its reservation.
        if self.db.execute("SELECT 1 FROM attempts WHERE status='reserved'").fetchone():
            raise AcquisitionError("ambiguous_interrupted_request_manual_resolution_required")
        if self.db.execute("SELECT 1 FROM attempts WHERE http_status IN (401,403)").fetchone():
            raise AcquisitionError("authentication_or_entitlement_failed")

    def _throttle(self):
        rate = min(self.manifest["limits"]["requests_per_minute"],
                   self.approval["provider_requests_per_minute"],
                   int(self.db.execute("SELECT value FROM metadata WHERE name='provider_rate'").fetchone()[0]))
        while True:
            now = self.clock()
            not_before = float(self.db.execute("SELECT value FROM metadata WHERE name='not_before'").fetchone()[0])
            recent = self.db.execute("SELECT timestamp FROM attempts WHERE timestamp>? ORDER BY timestamp", (now - 60,)).fetchall()
            delay = max(0, not_before - now)
            if len(recent) >= rate:
                delay = max(delay, recent[-rate][0] + 60.001 - now)
            if delay <= 0:
                return
            self.sleep(min(delay, 60))

    def _reserve(self, query, token, attempt):
        self._throttle()
        limits = self.manifest["limits"]
        with self.db:
            count, retained = self.db.execute("SELECT COUNT(*), COALESCE(SUM(reservation + retained),0) FROM attempts").fetchone()
            if count >= limits["requests"]:
                raise AcquisitionError("shared_request_cap_exhausted")
            available = limits["retained_bytes"] - retained
            if available <= 0:
                raise AcquisitionError("shared_byte_cap_exhausted")
            reservation = min(limits["page_bytes"], available)
            cursor = self.db.execute("INSERT INTO attempts(query_id,token,attempt,timestamp,reservation,status) VALUES(?,?,?,?,?,'reserved')",
                                     (query["id"], token, attempt, self.clock(), reservation))
        return cursor.lastrowid, reservation

    def _finish(self, request_id, status, *, response=None, body_hash=None, fingerprint=None, next_token=None, reason=None):
        retained = len(response.body) if body_hash else 0
        headers = safe_headers(response.headers) if response else {}
        with self.db:
            self.db.execute("UPDATE attempts SET status=?, reservation=0, retained=?, http_status=?, reason=?, headers=?, body_hash=?, fingerprint=?, next_token=? WHERE id=?",
                            (status, retained, response.status if response else None, reason,
                             json.dumps(headers), body_hash, fingerprint, next_token, request_id))
            if response:
                wait = headers.get("retry-after")
                not_before = self.clock()
                if wait:
                    try:
                        if re.fullmatch(r"\d+", wait):
                            not_before += int(wait)
                        else:
                            parsed = parsedate_to_datetime(wait)
                            if parsed.tzinfo is None:
                                raise ValueError
                            not_before = max(not_before, parsed.timestamp())
                    except (ValueError, TypeError, OverflowError):
                        # No guess about a malformed provider wait instruction.
                        self.db.execute("UPDATE attempts SET status='failed',reason='invalid_retry_after' WHERE id=?", (request_id,))
                remaining = headers.get("x-ratelimit-remaining")
                if remaining is not None:
                    try:
                        if not re.fullmatch(r"\d+", remaining):
                            raise ValueError
                        if int(remaining) == 0:
                            reset = headers.get("x-ratelimit-reset", "")
                            if not re.fullmatch(r"\d+", reset):
                                raise ValueError
                            not_before = max(not_before, float(reset))
                            if not_before == float("inf"):
                                raise ValueError
                    except (ValueError, OverflowError):
                        self.db.execute("UPDATE attempts SET status='failed',reason='invalid_rate_limit_reset' WHERE id=?", (request_id,))
                self.db.execute("UPDATE metadata SET value=? WHERE name='not_before' AND CAST(value AS REAL)<?",
                                (str(not_before), not_before))
                reported = headers.get("x-ratelimit-limit", "")
                if reported.isdigit() and int(reported) > 0:
                    old = int(self.db.execute("SELECT value FROM metadata WHERE name='provider_rate'").fetchone()[0])
                    self.db.execute("UPDATE metadata SET value=? WHERE name='provider_rate'", (str(min(old, int(reported))),))

    def _fetch(self, query, token):
        prior = self.db.execute("SELECT * FROM attempts WHERE query_id=? AND token=? ORDER BY id", (query["id"], token)).fetchall()
        if prior:
            last = prior[-1]
            if last["status"] == "complete":
                raw = (self.root / "pages" / (last["body_hash"] + ".json")).read_bytes()
                if digest(raw) != last["body_hash"]:
                    raise AcquisitionError("cached_page_hash_mismatch")
                payload, fingerprint = _page(raw, query)
                if fingerprint != last["fingerprint"] or payload["next_page_token"] != last["next_token"]:
                    raise AcquisitionError("cached_page_lineage_mismatch")
                return payload, last["body_hash"], fingerprint
            if last["status"] != "transient" or len(prior) >= 2:
                raise AcquisitionError(last["reason"] or "terminal_acquisition_failure")
        params = {field: query[field] for field in
                  ("start", "end", "feed", "timeframe", "adjustment", "currency", "asof", "limit", "sort")}
        params["symbols"] = ",".join(query["symbols"])
        if token:
            params["page_token"] = token
        for attempt in range(len(prior) + 1, 3):
            if self.transport is None:
                self.transport = AlpacaTransport()
            request_id, budget = self._reserve(query, token, attempt)
            try:
                response = self.transport(params, budget)
            except Exception as error:
                # Transport exceptions may contain URLs/headers/keys. Only the
                # two codes created by our transport are selectively retained.
                reason = str(error) if type(error) is AcquisitionError and str(error) in {
                    "response_byte_limit_exceeded", "unexpected_content_encoding",
                    "credential_echo_detected"} else "transient_transport_failure"
                status = "transient" if reason == "transient_transport_failure" and attempt == 1 else "failed"
                self._finish(request_id, status, reason=reason)
                if status == "transient":
                    continue
                raise AcquisitionError(reason) from None
            if response.status != 200:
                retry = response.status in TRANSIENT and attempt == 1
                reason = "transient_http_failure" if response.status in TRANSIENT else "terminal_http_failure"
                self._finish(request_id, "transient" if retry else "failed", response=response, reason=reason)
                saved = self.db.execute("SELECT status,reason FROM attempts WHERE id=?", (request_id,)).fetchone()
                if retry and saved["status"] == "transient":
                    continue
                raise AcquisitionError(saved["reason"]) from None
            if not isinstance(response.body, bytes) or len(response.body) > budget:
                self._finish(request_id, "failed", reason="response_byte_limit_exceeded")
                raise AcquisitionError("response_byte_limit_exceeded")
            body_hash = digest(response.body)
            destination = self.root / "pages" / (body_hash + ".json")
            if destination.is_symlink():
                raise AcquisitionError("storage_symlink_forbidden")
            # fsync raw before committing its reference; after a crash the
            # still-reserved slot covers even a partially written body.
            with destination.open("wb") as handle:
                handle.write(response.body)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                payload, fingerprint = _page(response.body, query)
            except AcquisitionError as error:
                self._finish(request_id, "failed", response=response, body_hash=body_hash, reason=str(error))
                raise
            self._finish(request_id, "complete", response=response, body_hash=body_hash,
                         fingerprint=fingerprint, next_token=payload["next_page_token"])
            saved = self.db.execute("SELECT status,reason FROM attempts WHERE id=?", (request_id,)).fetchone()
            if saved["status"] != "complete":
                raise AcquisitionError(saved["reason"])
            return payload, body_hash, fingerprint
        raise AcquisitionError("retry_cap_exhausted")

    def run(self, query_id):
        """Resume one frozen query; all queries share this directory's ledger."""
        return self._run_many([query_id])[0]

    def run_all(self):
        """Run manifest order under one process lock, stopping on any failure."""
        return self._run_many([query["id"] for query in self.manifest["queries"]])

    def _run_many(self, query_ids):
        validate_approval(self.manifest, self.approval, self.root)
        queries = [resolved_query(self.manifest, query_id) for query_id in query_ids]
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "pages").mkdir(exist_ok=True)
        with exclusive_lock(self.root / "acquisition.lock"):
            try:
                self._open()
                return [self._run_query(query) for query in queries]
            finally:
                if self.db is not None:
                    self.db.close()
                    self.db = None

    def _run_query(self, query):
        """Retain page-local raw coordinates, including both duplicate arrivals.

        raw-page-symbol-row-v1 resolves a reference as
        json.loads(raw_page)["bars"][symbol][row_index]. page_sha256 identifies
        the unchanged raw bytes; page_index is the zero-based query page order;
        row_index is zero-based within that page's own symbol array, never a
        cumulative arrival count. Stable last arrival still selects duplicates.
        """
        query_id = query["id"]
        if query["scope"] == "bulk":
            probe = next(q for q in self.manifest["queries"] if q["scope"] == "probe")
            evidence = cached_pages(self.manifest, self.root, probe["id"])
            if not evidence["terminal"]:
                raise AcquisitionError("access_probe_not_complete")
            probe = resolved_query(self.manifest, probe["id"])
            observed = {symbol: set() for symbol in probe["symbols"]}
            for page in evidence["pages"]:
                payload, _ = _page(page["raw"], probe)
                for symbol, rows in payload["bars"].items():
                    observed[symbol].update(instant(r["t"]).astimezone(NY).date().isoformat() for r in rows)
            if any(not set(probe["required_sessions"]) <= days for days in observed.values()):
                raise AcquisitionError("access_probe_required_bars_unresolved")
        token, visited, fingerprints = "", set(), set()
        pages, by_symbol, duplicate_rows = [], {s: [] for s in query["symbols"]}, []
        selected = {}
        while True:
            if token in visited:
                raise AcquisitionError("pagination_cycle")
            visited.add(token)
            payload, body_hash, fingerprint = self._fetch(query, token)
            if fingerprint in fingerprints:
                raise AcquisitionError("duplicate_page")
            fingerprints.add(fingerprint)
            pages.append({"sha256": body_hash, "request_token": token,
                          "next_page_token": payload["next_page_token"]})
            for symbol, rows in payload["bars"].items():
                for row_index, row in enumerate(rows):
                    row_id = (symbol, row["t"])
                    source = {"page_sha256": body_hash, "page_index": len(pages) - 1,
                              "symbol": symbol, "row_index": row_index}
                    if row_id in selected:
                        duplicate_rows.append({"symbol": symbol, "timestamp": row["t"],
                            "previous": selected[row_id], "selected": source,
                            "operation": "stable_last_row_in_page_order"})
                    selected[row_id] = source
                    by_symbol[symbol].append(row)
            token = payload["next_page_token"]
            if token is None:
                break
        symbol_manifest = {}
        required = set(query.get("required_sessions", []))
        for symbol, rows in by_symbol.items():
            returned = {instant(r["t"]).astimezone(NY).date().isoformat() for r in rows}
            missing = sorted(required - returned)
            state = "absent" if not rows else "partial" if missing else "returned_with_bars"
            symbol_manifest[symbol] = {"state": state, "rows": len(rows), "missing_sessions": missing,
                "lookback_completeness": "checked_against_declared_sessions" if required else "unresolved"}
        report = {"schema": SCHEMA, "manifest_sha256": self.identity, "query_id": query_id,
                  "pagination_complete": True, "pages": pages, "symbols": symbol_manifest,
                  "source_coordinate_contract": "raw-page-symbol-row-v1",
                  "duplicate_operations": duplicate_rows,
                  "vintage": "later_retrieval_not_original_information_set",
                  "mapping_note": "asof_is_symbol_mapping_not_observation_vintage",
                  "ledger": self.ledger()}
        (self.root / (query_id + "-manifest.json")).write_bytes(encode(report))
        return report

    def ledger(self):
        count, retained, reserved = self.db.execute("SELECT COUNT(*),COALESCE(SUM(retained),0),COALESCE(SUM(reservation),0) FROM attempts").fetchone()
        return {"request_slots_charged": count, "uncompressed_retained_bytes_charged": retained,
                "unresolved_byte_reservations": reserved, "additional_spend_authorized": 0,
                "cost_basis": self.approval["cost_basis"],
                "accounting": "reserved_before_http; ambiguous_crashes_remain_charged_and_blocked"}


def cached_pages(manifest, root, query_id):
    """Offline verified raw export for normalization; never accesses credentials.

    Incomplete pages remain useful evidence, but terminal=False prevents them
    from masquerading as a complete dataset. Query/asof/adjustment identity is
    bound to the frozen manifest in SQLite, not reconstructed from file names.
    """
    identity = validate_manifest(manifest)
    root = Path(root).resolve()
    query = resolved_query(manifest, query_id)
    db = sqlite3.connect((root / "ledger.sqlite3").as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        if db.execute("SELECT value FROM metadata WHERE name='manifest_sha256'").fetchone()[0] != identity:
            raise AcquisitionError("frozen_manifest_changed")
        token, visited, fingerprints, pages, terminal = "", set(), set(), [], False
        pagination_problem = None
        while token not in visited:
            visited.add(token)
            row = db.execute("SELECT * FROM attempts WHERE query_id=? AND token=? ORDER BY id DESC LIMIT 1",
                             (query_id, token)).fetchone()
            if row is None or row["status"] != "complete":
                pagination_problem = "page_not_acquired" if row is None else (row["reason"] or "unresolved_request")
                break
            raw = (root / "pages" / (row["body_hash"] + ".json")).read_bytes()
            if digest(raw) != row["body_hash"]:
                raise AcquisitionError("cached_page_hash_mismatch")
            payload, fingerprint = _page(raw, query)
            if fingerprint != row["fingerprint"] or payload["next_page_token"] != row["next_token"]:
                raise AcquisitionError("cached_page_lineage_mismatch")
            if fingerprint in fingerprints:
                pagination_problem = "duplicate_page"
                break
            fingerprints.add(fingerprint)
            pages.append({"raw": raw, "sha256": row["body_hash"], "query": dict(query),
                          "query_id": query_id, "page_index": len(pages),
                          "retrieved_at": datetime.fromtimestamp(row["timestamp"], timezone.utc).isoformat(),
                          "safe_response_headers": json.loads(row["headers"]),
                          "request_token": token, "next_page_token": payload["next_page_token"]})
            token = payload["next_page_token"]
            if token is None:
                terminal = True
                break
        if not terminal and pagination_problem is None:
            pagination_problem = "pagination_cycle"
        count, retained, reserved = db.execute("SELECT COUNT(*),COALESCE(SUM(retained),0),COALESCE(SUM(reservation),0) FROM attempts").fetchone()
        failures = [{"attempt": r["attempt"], "status": r["status"], "reason": r["reason"],
                     "http_status": r["http_status"]} for r in
                    db.execute("SELECT * FROM attempts WHERE query_id=? AND status!='complete' ORDER BY id", (query_id,))]
        return {"pages": pages, "terminal": terminal, "manifest_sha256": identity,
                "query_id": query_id, "failures": failures, "pagination_problem": pagination_problem,
                "ledger": {"request_slots_charged": count, "uncompressed_retained_bytes_charged": retained,
                           "unresolved_byte_reservations": reserved}}
    finally:
        db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--approval", type=Path)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--query")
    selection.add_argument("--all", dest="all_queries", action="store_true")
    parser.add_argument("--acquire", action="store_true")
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_bytes())
        identity = validate_manifest(manifest)
        if not args.acquire:
            print(json.dumps({"manifest_sha256": identity, "validation": "PASS",
                              "provider_requests": 0, "acquisition": "NOT RUN"}))
            return 0
        if args.approval is None or not (args.query or args.all_queries):
            raise AcquisitionError("private_approval_and_query_or_all_required")
        approval = json.loads(args.approval.read_bytes())
        runner = Acquisition(manifest, approval, approval.get("storage_root", ""))
        results = runner.run_all() if args.all_queries else [runner.run(args.query)]
        print(json.dumps({"query_ids": [result["query_id"] for result in results],
                          "pagination_complete": True,
                          "request_slots_charged": results[-1]["ledger"]["request_slots_charged"]}))
        return 0
    except AcquisitionError as error:
        print(json.dumps({"status": "BLOCKED", "reason": str(error)}))
        return 2
    except Exception:
        print(json.dumps({"status": "BLOCKED", "reason": "invalid_manifest_approval_or_storage"}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
