"""Bounded dated SEC documents; neither news clearance nor entry authority.

Receipt/bundle parsing is stdlib-only. Collection verifies the unchanged
production publication through the existing morning binder. Source downloads
remain inert bytes and cannot classify events or change orders.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import signal
import tempfile
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

VERSION = 1
MAX_RECEIPT_BYTES = 64 * 1024
MAX_BUNDLE_BYTES = 2 * 1024 * 1024
MAX_PUBLICATION_BYTES = 32 * 1024 * 1024
MAX_CANDIDATES = 128
MAX_ISSUERS = 8
LOOKBACK_DAYS = 365
MAX_REPORTS = 3
MAX_EXHIBITS = 2
MAX_HISTORY_FILES = 1
MAX_METADATA_ROWS = 2000
MAX_LISTED_FILINGS = 12
MAX_EXCERPT_BYTES = 16 * 1024
MAX_REQUESTS = 96
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_DOWNLOAD_BYTES = 32 * 1024 * 1024
MAX_CAPTURE_BYTES = 32 * 1024 * 1024
MAX_COLLECTION_SECONDS = 240
FINALIZATION_SECONDS = 5
MIN_REQUEST_INTERVAL_SECONDS = 1
RECEIPT_TTL_SECONDS = 24 * 60 * 60
MAX_FUTURE_SKEW_SECONDS = 5
MAPPING_CACHE_SECONDS = 7 * 24 * 60 * 60
DOCUMENT_CACHE_SECONDS = 24 * 60 * 60
MAX_CACHE_ENTRIES = 256
MAX_CACHE_BYTES = 128 * 1024 * 1024
MAPPING_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
USER_AGENT = "SpicyStock issuer evidence (https://github.com/spicyChicken59/SpicyStock)"
HEX = re.compile(r"[a-f0-9]{64}\Z")
SYMBOL = re.compile(r"[A-Z][A-Z0-9.\-]{0,31}\Z")
ACCESSION = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}\Z")
BASENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.\-]{0,199}\Z")
FORMS = {"8-K", "8-K/A", "6-K", "6-K/A"}
ERRORS = {"rate_limit", "http_error", "timeout", "network_error", "redirect_refused",
          "size_limit", "request_budget", "time_budget", "invalid_response",
          "identity_unverified", "metadata_invalid", "document_invalid", "history_incomplete"}
POLICY = {"version": VERSION, "max_issuers": MAX_ISSUERS, "lookback_days": LOOKBACK_DAYS,
          "max_reports": MAX_REPORTS, "max_exhibits_per_report": MAX_EXHIBITS,
          "max_history_files": MAX_HISTORY_FILES, "max_metadata_rows": MAX_METADATA_ROWS,
          "max_listed_filings": MAX_LISTED_FILINGS, "max_excerpt_bytes": MAX_EXCERPT_BYTES,
          "receipt_ttl_seconds": RECEIPT_TTL_SECONDS, "max_future_skew_seconds": MAX_FUTURE_SKEW_SECONDS,
          "max_requests": MAX_REQUESTS, "max_response_bytes": MAX_RESPONSE_BYTES,
          "max_download_bytes": MAX_DOWNLOAD_BYTES, "max_collection_seconds": MAX_COLLECTION_SECONDS,
          "min_request_interval_seconds": MIN_REQUEST_INTERVAL_SECONDS}
COVERAGE = {"issuer_news": {"status": "not_cleared", "reason": "Bounded SEC documents are not comprehensive issuer news or event clearance."},
            "earnings": {"status": "not_checked", "reason": "The future earnings calendar has not been checked."}}


class SourceError(ValueError):
    def __init__(self, code, *, http_status=None):
        if code not in ERRORS:
            code = "invalid_response"
        if http_status is not None and not _http_failure(code, http_status):
            raise ValueError("issuer HTTP status does not match its error code")
        self.code = code
        self.http_status = http_status
        super().__init__(code)


def _http_failure(code, status):
    if type(status) is not int or not 300 <= status <= 599:
        return False
    expected = "redirect_refused" if status < 400 else "rate_limit" if status == 429 else "http_error"
    return code == expected


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _decode(raw, maximum):
    _require(isinstance(raw, bytes) and 0 < len(raw) <= maximum, "issuer JSON byte bound")
    def pairs(items):
        out = {}
        for key, value in items:
            _require(key not in out, "duplicate issuer JSON key")
            out[key] = value
        return out
    def invalid(_):
        raise ValueError("nonfinite issuer JSON")
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    except (UnicodeError, RecursionError) as error:
        raise ValueError("issuer JSON decoding failed") from error


def _keys(value, required, optional=()):
    _require(isinstance(value, dict) and set(required) <= set(value)
             and set(value) <= set(required) | set(optional), "issuer object keys")


def _text(value, maximum=2000, empty=False):
    return isinstance(value, str) and len(value) <= maximum and (empty or bool(value.strip()))


def _count(value, maximum):
    return type(value) is int and 0 <= value <= maximum


def _instant(value):
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        raise ValueError("issuer clock requires an offset") from None
    _require(parsed.tzinfo is not None and parsed.utcoffset() is not None, "issuer clock requires an offset")
    return parsed.astimezone(timezone.utc)


def _iso(value):
    return _instant(value).isoformat()


def _day(value):
    _require(isinstance(value, str), "issuer date shape")
    parsed = date.fromisoformat(value)
    _require(parsed.isoformat() == value, "issuer date shape")
    return parsed


def _https(value):
    _require(_text(value, 2048), "issuer URL shape")
    parsed = urlsplit(value)
    _require(parsed.scheme == "https" and parsed.hostname and not parsed.username
             and not parsed.password and parsed.port in (None, 443), "issuer URL security")
    return parsed


def _sec_url(value):
    parsed = _https(value)
    _require(not parsed.query and not parsed.fragment and "%" not in parsed.path
             and "\\" not in value and not any(p in (".", "..") for p in parsed.path.split("/")), "issuer SEC URL security")
    allowed = value == MAPPING_URL
    allowed |= parsed.hostname == "data.sec.gov" and bool(re.fullmatch(r"/submissions/CIK[0-9]{10}(?:-submissions-[0-9]{3})?\.json", parsed.path))
    allowed |= parsed.hostname == "www.sec.gov" and bool(re.fullmatch(r"/Archives/edgar/data/[1-9][0-9]{0,9}/[0-9]{18}/[A-Za-z0-9][A-Za-z0-9_.\-]{0,199}", parsed.path))
    _require(allowed, "issuer SEC URL outside fixed sources")
    return parsed


def _basename(value):
    return isinstance(value, str) and bool(BASENAME.fullmatch(value)) and ".." not in value


def _publication(raw):
    from src import reader
    data = _decode(raw, MAX_PUBLICATION_BYTES)
    _require(isinstance(data, dict) and data.get("schema_version") == 2, "issuer publication schema")
    run = data["run"]
    binding = {"data_sha256": _sha(raw), "context_sha256": run["evidence"]["context_sha256"],
               "run_id": run["run_id"], "rules_version": data["app"]["rules_version"],
               "measured_session": run["session"], "applicable_session": run["timing"]["applicable_session"],
               "published_at": run["published_at"], **reader.binding(raw)}
    return data, binding


def _binding(value):
    _keys(value, ("data_sha256", "context_sha256", "run_id", "rules_version", "measured_session",
                  "applicable_session", "published_at", "reader_projection_version", "reader_sha256"))
    for key in ("data_sha256", "context_sha256", "reader_sha256"):
        _require(isinstance(value[key], str) and HEX.fullmatch(value[key]), "issuer binding digest")
    _require(isinstance(value["rules_version"], str) and re.fullmatch(r"[a-f0-9]{12}", value["rules_version"]), "issuer rules identity")
    _require(value["run_id"] is None or _text(value["run_id"], 128), "issuer publication run")
    _require(type(value["reader_projection_version"]) is int and value["reader_projection_version"] == 1, "issuer reader version")
    _day(value["measured_session"])
    _day(value["applicable_session"])
    _instant(value["published_at"])


def _candidates(data):
    admitted, excluded = [], []
    rows = [("burst", row) for row in data.get("bursts", [])]
    rows += [("anticipation", row) for row in data.get("watchlist", {}).get("top", [])]
    seen = set()
    for kind, row in rows:
        p, evidence = row.get("plan"), row.get("evidence") or {}
        if not isinstance(p, dict):
            continue
        known = p.get("event_risk", {}).get("blocked") is True
        ticket = evidence.get("gate", {}).get("ticket") is True
        if not (known or ticket):
            continue
        identity = (kind, row["ticker"])
        _require(identity not in seen and p.get("ticker") == row["ticker"] and p.get("kind") == kind, "issuer candidate identity")
        seen.add(identity)
        item = {"ticker": row["ticker"], "kind": kind, "evidence_id": evidence["id"],
                "plan_sha256": p["evidence_ref"]["plan_sha256"],
                "admission": "known_event_excluded" if known else "admitted", "selected": False,
                "anchors": deepcopy(p.get("event_risk", {}).get("matches", []))}
        (excluded if known else admitted).append(item)
    out = admitted + excluded
    _require(len(out) <= MAX_CANDIDATES, "issuer candidate bound")
    return out


def _source(value, completion):
    _keys(value, ("url", "raw_sha256", "bytes", "fetched_at", "checked_at", "cache_status"))
    _sec_url(value["url"])
    _require(isinstance(value["raw_sha256"], str) and HEX.fullmatch(value["raw_sha256"]), "issuer source digest")
    _require(_count(value["bytes"], MAX_RESPONSE_BYTES) and value["bytes"] > 0, "issuer source bytes")
    fetched, checked = _instant(value["fetched_at"]), _instant(value["checked_at"])
    _require(fetched <= checked <= completion + timedelta(seconds=MAX_FUTURE_SKEW_SECONDS), "issuer source clocks")
    _require(value["cache_status"] in ("network", "verified_cache"), "issuer source cache status")
    _require(fetched == checked, "issuer source check must be last network clock")
    if value["cache_status"] == "verified_cache":
        _require("/submissions/" not in value["url"], "issuer submissions cannot use cached check")
        ttl = MAPPING_CACHE_SECONDS if value["url"] == MAPPING_URL else DOCUMENT_CACHE_SECONDS
        _require((completion - fetched).total_seconds() <= ttl, "issuer source cache TTL")


def _filing(value, as_of):
    _keys(value, ("accession", "form", "filing_date", "report_date", "accepted_at", "primary_document", "items"))
    _require(isinstance(value["accession"], str) and ACCESSION.fullmatch(value["accession"]), "issuer accession")
    _require(_text(value["form"], 32) and _basename(value["primary_document"]) and _text(value["items"], 256, True), "issuer filing fields")
    _day(value["filing_date"])
    if value["report_date"] is not None:
        _day(value["report_date"])
    _require(_instant(value["accepted_at"]) <= as_of + timedelta(seconds=MAX_FUTURE_SKEW_SECONDS), "issuer future acceptance")


def _anchor(value, ticker):
    required = ("id", "symbol", "issuer", "kind", "announced_on", "active_from", "evidence_as_of", "reviewed_on", "review_due", "reason", "sources")
    _keys(value, required, ("active_until", "resolution", "review_overdue"))
    _require(value["symbol"] == ticker and value["kind"] == "cash_acquisition", "issuer anchor identity")
    for field in ("id", "issuer", "reason"):
        _require(_text(value[field]), "issuer anchor text")
    for field in ("announced_on", "active_from", "evidence_as_of", "reviewed_on", "review_due"):
        _day(value[field])
    if value.get("active_until") is not None:
        _day(value["active_until"])
    _require("review_overdue" not in value or type(value["review_overdue"]) is bool, "issuer anchor review flag")
    _require(isinstance(value["sources"], list) and 0 < len(value["sources"]) <= 8, "issuer anchor source bound")
    for source in value["sources"] + ([value["resolution"]] if value.get("resolution") else []):
        _keys(source, ("title", "published_on", "url", "sha256", "quote"))
        _https(source["url"])
        _day(source["published_on"])
        _require(all(_text(source[key]) for key in ("title", "quote")) and isinstance(source["sha256"], str) and HEX.fullmatch(source["sha256"]), "issuer anchor source")


def parse_receipt(raw):
    value = _decode(raw, MAX_RECEIPT_BYTES)
    _keys(value, ("schema_version", "status", "dry_run", "collection_run_id", "collection_started_at", "generated_at",
                  "expires_at", "publication", "previous_receipt_sha256", "policy", "selection", "bundle", "coverage"))
    _require(type(value["schema_version"]) is int and value["schema_version"] == VERSION, "issuer receipt version")
    _require(value["status"] in ("collected", "partial", "unavailable", "no_candidates", "inapplicable")
             and type(value["dry_run"]) is bool and _text(value["collection_run_id"], 128), "issuer receipt status")
    started, completed, expires = map(_instant, (value["collection_started_at"], value["generated_at"], value["expires_at"]))
    _require(started <= completed <= started + timedelta(seconds=MAX_COLLECTION_SECONDS)
             and expires == completed + timedelta(seconds=RECEIPT_TTL_SECONDS), "issuer receipt clocks")
    _binding(value["publication"])
    prior = value["previous_receipt_sha256"]
    _require(prior is None or isinstance(prior, str) and HEX.fullmatch(prior), "issuer previous receipt digest")
    _require(value["policy"] == POLICY and all(type(value["policy"][k]) is type(v) for k, v in POLICY.items())
             and value["coverage"] == COVERAGE, "issuer receipt policy")
    sel = value["selection"]
    _keys(sel, ("candidate_count", "issuer_count", "selected_issuer_count", "omitted_issuer_count", "selected_tickers"))
    _require(all(_count(sel[k], MAX_CANDIDATES) for k in ("candidate_count", "issuer_count", "selected_issuer_count", "omitted_issuer_count")), "issuer selection counts")
    tickers = sel["selected_tickers"]
    _require(isinstance(tickers, list) and len(tickers) <= MAX_ISSUERS and len(set(tickers)) == len(tickers)
             and all(isinstance(s, str) and SYMBOL.fullmatch(s) for s in tickers), "issuer selected symbols")
    _require(sel["selected_issuer_count"] == len(tickers) and sel["issuer_count"] == len(tickers) + sel["omitted_issuer_count"], "issuer selection count relationship")
    desc = value["bundle"]
    _keys(desc, ("sha256", "bytes", "path"))
    _require(isinstance(desc["sha256"], str) and HEX.fullmatch(desc["sha256"])
             and _count(desc["bytes"], MAX_BUNDLE_BYTES) and desc["bytes"] > 0
             and desc["path"] == f'issuer-evidence/{desc["sha256"]}.json', "issuer bundle descriptor")
    return value


def _reconcile_row(row):
    """Reconcile trust labels with already shape-validated visible evidence."""
    identity, index = row["identity"], row["index"]
    if identity["status"] == "unverified":
        empty_fields = ("metadata_count", "eligible_current_report_count", "not_selected_count",
                        "history_files_advertised", "history_files_fetched", "history_sources",
                        "selected_accessions", "listed_filings", "exhibit_links_observed",
                        "exhibit_links_not_fetched")
        _require(index["coverage_status"] == "unknown" and index["range_start"] is None
                 and not any(index[key] for key in empty_fields), "issuer unverified index must remain unknown")
        _require(row["status"] in ("unavailable", "identity_unverified") and not row["documents"]
                 and identity["submissions_source"] is None, "issuer unverified row cannot claim collection")
        return
    prefix = f'https://data.sec.gov/submissions/CIK{identity["cik"]:010d}'
    index_errors = any(error["code"] in ("history_incomplete", "metadata_invalid")
                       or error["source_url"] in (MAPPING_URL, prefix + ".json")
                       or isinstance(error["source_url"], str)
                       and re.fullmatch(re.escape(prefix) + r"-submissions-[0-9]{3}\.json", error["source_url"])
                       for error in row["errors"])
    full_window = index["range_start"] is not None and index["range_start"] <= index["window_start"]
    coverage = "observed_window" if full_window and not index_errors else "partial"
    _require(index["coverage_status"] == coverage, "issuer index label contradicts observed coverage")
    _require(len(index["listed_filings"]) == min(index["eligible_current_report_count"], MAX_LISTED_FILINGS),
             "issuer listed metadata count must reconcile")
    primaries = {doc["accession"] for doc in row["documents"] if doc["role"] == "primary"}
    incomplete = (coverage != "observed_window" or row["errors"] or index["not_selected_count"]
                  or index["exhibit_links_not_fetched"] or any(doc["excerpt"]["truncated"] for doc in row["documents"])
                  or not set(index["selected_accessions"]) <= primaries)
    _require(row["status"] == ("partial" if incomplete else "collected"),
             "issuer row label contradicts visible completeness")


def _reconcile_budget(issuers, stats):
    """Visible sources prove lower bounds, never all attempts or raw captures."""
    network, captures, failures = {}, {}, set()
    for row in issuers:
        identity = row["identity"]
        sources = [identity["mapping_source"], identity["submissions_source"], *row["index"]["history_sources"],
                   *(doc["source"] for doc in row["documents"])]
        for source in sources:
            if source is None:
                continue
            digest, size = source["raw_sha256"], source["bytes"]
            _require(digest not in captures or captures[digest] == size, "issuer source digest has conflicting byte sizes")
            captures[digest] = size
            if source["cache_status"] == "network":
                event = (source["url"], digest, size, _instant(source["fetched_at"]), _instant(source["checked_at"]))
                network[event] = size
        for error in row["errors"]:
            if "http_status" in error:
                failures.add((error["source_url"], error["code"], error["http_status"], error["source_phase"]))
    _require(stats["request_count"] >= len(network) + len(failures), "issuer request count below visible evidence")
    _require(stats["downloaded_bytes"] >= sum(network.values()), "issuer downloaded bytes below visible evidence")
    _require(stats["capture_bytes"] >= sum(captures.values()), "issuer capture bytes below visible evidence")
    _require(not stats["downloaded_bytes"] or stats["request_count"] > 0, "issuer download requires a request")


def validate_bundle(receipt_raw, bundle_raw):
    receipt = parse_receipt(receipt_raw)
    _require(isinstance(bundle_raw, bytes) and len(bundle_raw) == receipt["bundle"]["bytes"]
             and _sha(bundle_raw) == receipt["bundle"]["sha256"], "issuer bundle exact bytes")
    bundle = _decode(bundle_raw, MAX_BUNDLE_BYTES)
    _keys(bundle, ("schema_version", "publication", "collection_started_at", "generated_at", "as_of", "window_start", "candidates", "issuers", "stats"))
    for key in ("schema_version", "publication", "collection_started_at", "generated_at"):
        _require(bundle[key] == receipt[key] and type(bundle[key]) is type(receipt[key]), "issuer bundle receipt relationship")
    as_of, completion = _instant(bundle["as_of"]), _instant(bundle["generated_at"])
    _require(as_of == _instant(bundle["collection_started_at"]) and _day(bundle["window_start"]) == as_of.date() - timedelta(days=LOOKBACK_DAYS), "issuer fixed selection window")
    candidates = bundle["candidates"]
    _require(isinstance(candidates, list) and len(candidates) == receipt["selection"]["candidate_count"] and len(candidates) <= MAX_CANDIDATES, "issuer candidate count")
    seen, all_tickers, selected = set(), [], receipt["selection"]["selected_tickers"]
    for candidate in candidates:
        _keys(candidate, ("ticker", "kind", "evidence_id", "plan_sha256", "admission", "selected", "anchors"))
        ticker = candidate["ticker"]
        _require(isinstance(ticker, str) and SYMBOL.fullmatch(ticker) and candidate["kind"] in ("burst", "anticipation")
                 and _text(candidate["evidence_id"], 128) and isinstance(candidate["plan_sha256"], str) and HEX.fullmatch(candidate["plan_sha256"]), "issuer candidate fields")
        identity = (candidate["kind"], ticker)
        _require(identity not in seen, "issuer duplicate candidate")
        seen.add(identity)
        if ticker not in all_tickers:
            all_tickers.append(ticker)
        _require(candidate["admission"] in ("admitted", "known_event_excluded") and type(candidate["selected"]) is bool
                 and candidate["selected"] == (ticker in selected), "issuer candidate selection")
        _require(isinstance(candidate["anchors"], list) and len(candidate["anchors"]) <= 128, "issuer candidate anchors")
        for anchor in candidate["anchors"]:
            _anchor(anchor, ticker)
        _require(candidate["admission"] != "known_event_excluded" or candidate["anchors"], "issuer excluded candidate needs anchors")
    _require(len(all_tickers) == receipt["selection"]["issuer_count"] and selected == all_tickers[:len(selected)], "issuer deterministic selection")
    issuers = bundle["issuers"]
    _require(isinstance(issuers, list) and [row.get("ticker") for row in issuers] == selected, "issuer rows differ from selection")
    for row in issuers:
        _keys(row, ("ticker", "status", "reason", "identity", "index", "documents", "errors"))
        _require(row["status"] in ("collected", "partial", "unavailable", "identity_unverified") and (row["reason"] is None or _text(row["reason"])), "issuer row status")
        identity = row["identity"]
        _keys(identity, ("status", "cik", "name", "mapping_source", "submissions_source"))
        _require(identity["status"] in ("verified", "unverified") and (identity["cik"] is None or type(identity["cik"]) is int and 0 < identity["cik"] < 10**10)
                 and (identity["name"] is None or _text(identity["name"])), "issuer identity fields")
        for key in ("mapping_source", "submissions_source"):
            if identity[key] is not None:
                _source(identity[key], completion)
        _require(identity["mapping_source"] is None or identity["mapping_source"]["url"] == MAPPING_URL, "issuer mapping source URL")
        _require(identity["submissions_source"] is None or identity["submissions_source"]["url"] == f'https://data.sec.gov/submissions/CIK{identity["cik"]:010d}.json', "issuer submissions source URL")
        if identity["status"] == "verified":
            _require(identity["cik"] is not None and identity["name"] is not None and identity["mapping_source"] is not None and identity["submissions_source"] is not None, "issuer verified identity sources")
        index = row["index"]
        _keys(index, ("window_start", "window_end", "coverage_status", "reason", "range_start", "range_end", "metadata_count", "eligible_current_report_count", "not_selected_count", "history_files_advertised", "history_files_fetched", "history_sources", "selected_accessions", "listed_filings", "exhibit_links_observed", "exhibit_links_not_fetched"))
        _require(index["window_start"] == bundle["window_start"] and index["window_end"] == as_of.date().isoformat()
                 and index["coverage_status"] in ("observed_window", "partial", "unknown") and (index["reason"] is None or _text(index["reason"])), "issuer index coverage")
        for key in ("range_start", "range_end"):
            if index[key] is not None:
                _day(index[key])
        _require((index["range_start"] is None) == (index["range_end"] is None)
                 and (index["range_start"] is None or index["range_start"] <= index["range_end"]), "issuer observed index range")
        for key in ("metadata_count", "eligible_current_report_count", "not_selected_count", "history_files_advertised", "history_files_fetched", "exhibit_links_observed", "exhibit_links_not_fetched"):
            _require(_count(index[key], MAX_METADATA_ROWS * 2), "issuer index count")
        accessions = index["selected_accessions"]
        _require(isinstance(accessions, list) and len(accessions) <= MAX_REPORTS and len(set(accessions)) == len(accessions) and all(isinstance(s, str) and ACCESSION.fullmatch(s) for s in accessions), "issuer selected accessions")
        _require(index["not_selected_count"] == index["eligible_current_report_count"] - len(accessions)
                 and index["history_files_fetched"] <= MAX_HISTORY_FILES
                 and index["history_files_fetched"] <= index["history_files_advertised"]
                 and index["exhibit_links_not_fetched"] <= index["exhibit_links_observed"], "issuer index relationships")
        _require(index["eligible_current_report_count"] <= index["metadata_count"], "issuer metadata count relationship")
        _require(isinstance(index["history_sources"], list) and len(index["history_sources"]) == index["history_files_fetched"], "issuer history source count")
        for source in index["history_sources"]:
            _source(source, completion)
            _require(identity["status"] == "verified" and re.fullmatch(r"https://data.sec.gov/submissions/CIK" + f'{identity["cik"]:010d}' + r"-submissions-[0-9]{3}\.json", source["url"]), "issuer history source URL")
        _require(isinstance(index["listed_filings"], list) and len(index["listed_filings"]) <= MAX_LISTED_FILINGS, "issuer listed metadata bound")
        metadata = {}
        for filing in index["listed_filings"]:
            _filing(filing, as_of)
            _require(filing["form"] in FORMS and index["window_start"] <= filing["filing_date"] <= index["window_end"]
                     and filing["accession"] not in metadata, "issuer listed current-report identity")
            metadata[filing["accession"]] = filing
        _require(index["listed_filings"] == sorted(index["listed_filings"], key=lambda f: (f["accepted_at"], f["accession"]), reverse=True)
                 and len(metadata) <= index["eligible_current_report_count"]
                 and accessions == [f["accession"] for f in index["listed_filings"][:MAX_REPORTS]], "issuer latest report selection")
        _require(isinstance(row["errors"], list) and len(row["errors"]) <= MAX_REQUESTS, "issuer errors bound")
        for error in row["errors"]:
            _keys(error, ("code", "source_url"), ("http_status", "source_phase"))
            _require(error["code"] in ERRORS, "issuer source error")
            if error["source_url"] is not None:
                _sec_url(error["source_url"])
            _require(("http_status" in error) == ("source_phase" in error), "issuer HTTP diagnostic pair")
            if "http_status" in error:
                _require(_http_failure(error["code"], error["http_status"]), "issuer HTTP status and code")
                _http_phase(error["source_phase"], error["source_url"], identity, metadata, accessions)
        docs = row["documents"]
        _require(isinstance(docs, list) and len(docs) <= MAX_REPORTS * (1 + MAX_EXHIBITS), "issuer document bound")
        doc_urls, primary_counts, exhibit_counts = set(), {}, {}
        for document in docs:
            _keys(document, ("accession", "form", "role", "source", "filing_date", "report_date", "accepted_at", "release_date", "excerpt"))
            _require(document["accession"] in accessions and document["form"] in FORMS and document["role"] in ("primary", "exhibit"), "issuer document selection")
            _source(document["source"], completion)
            url = document["source"]["url"]
            prefix = f'https://www.sec.gov/Archives/edgar/data/{identity["cik"]}/{document["accession"].replace("-", "")}/'
            _require(identity["status"] == "verified" and url.startswith(prefix) and url not in doc_urls, "issuer document path identity")
            doc_urls.add(url)
            filing = metadata[document["accession"]]
            _require(all(document[key] == filing[key] for key in ("form", "filing_date", "report_date", "accepted_at"))
                     and (document["role"] != "primary" or url == prefix + filing["primary_document"]), "issuer document metadata differs from index")
            counts = primary_counts if document["role"] == "primary" else exhibit_counts
            counts[document["accession"]] = counts.get(document["accession"], 0) + 1
            _require(counts[document["accession"]] <= (1 if document["role"] == "primary" else MAX_EXHIBITS), "issuer document role cap")
            _day(document["filing_date"])
            if document["report_date"] is not None:
                _day(document["report_date"])
            _require(_instant(document["accepted_at"]) <= as_of + timedelta(seconds=MAX_FUTURE_SKEW_SECONDS)
                     and document["release_date"] is None, "issuer document clocks")
            excerpt = document["excerpt"]
            _keys(excerpt, ("text", "normalization", "start", "characters", "normalized_characters", "truncated", "sha256"))
            _require(isinstance(excerpt["text"], str) and len(excerpt["text"].encode("utf-8")) <= MAX_EXCERPT_BYTES
                     and excerpt["normalization"] == "html_text_v1" and type(excerpt["start"]) is int and excerpt["start"] == 0
                     and type(excerpt["characters"]) is int and excerpt["characters"] == len(excerpt["text"])
                     and _count(excerpt["normalized_characters"], MAX_RESPONSE_BYTES)
                     and excerpt["normalized_characters"] >= excerpt["characters"]
                     and type(excerpt["truncated"]) is bool and excerpt["truncated"] == (excerpt["normalized_characters"] > excerpt["characters"])
                     and excerpt["sha256"] == _sha(excerpt["text"].encode("utf-8")), "issuer excerpt integrity")
        _require(all(accession in primary_counts for accession in exhibit_counts), "issuer exhibit needs primary document")
        _require(index["exhibit_links_observed"] - index["exhibit_links_not_fetched"] == sum(exhibit_counts.values()), "issuer exact exhibit remainder")
        _reconcile_row(row)
    stats = bundle["stats"]
    _keys(stats, ("request_count", "downloaded_bytes", "capture_bytes", "budget_stop"))
    _require(_count(stats["request_count"], MAX_REQUESTS) and _count(stats["downloaded_bytes"], MAX_DOWNLOAD_BYTES + MAX_RESPONSE_BYTES)
             and _count(stats["capture_bytes"], MAX_CAPTURE_BYTES)
             and (stats["budget_stop"] is None or stats["budget_stop"] in ERRORS), "issuer collection budget")
    _require(stats["downloaded_bytes"] <= MAX_DOWNLOAD_BYTES or stats["budget_stop"] == "size_limit", "issuer exceeded download budget must stop")
    _reconcile_budget(issuers, stats)
    if receipt["status"] in ("no_candidates", "inapplicable"):
        _require(not issuers and stats["request_count"] == 0 and not stats["downloaded_bytes"] and not stats["capture_bytes"], "issuer no-fetch receipt")
    _require(receipt["status"] != "no_candidates" or not candidates, "issuer no-candidate receipt")
    if receipt["status"] not in ("no_candidates", "inapplicable"):
        expected_status = ("unavailable" if all(row["status"] in ("unavailable", "identity_unverified") for row in issuers)
                           else "partial" if receipt["selection"]["omitted_issuer_count"] or any(row["status"] != "collected" for row in issuers)
                           else "collected")
        _require(receipt["status"] == expected_status, "issuer aggregate status differs")
    return bundle


def validate_for_publication(canonical_raw, receipt_raw, bundle_raw, *, allow_fixture=False):
    bundle = validate_bundle(receipt_raw, bundle_raw)
    data, binding = _publication(canonical_raw)
    _require(allow_fixture or not data.get("fixture") and data.get("run", {}).get("dry_run") is False, "issuer requires production publication")
    _require(binding == bundle["publication"], "issuer exact publication binding differs")
    expected = _candidates(data)
    selected = {row["ticker"] for row in bundle["issuers"]}
    for candidate in expected:
        candidate["selected"] = candidate["ticker"] in selected
    _require(expected == bundle["candidates"], "issuer exact candidate/anchor binding differs")
    return bundle


def parse_mapping(raw, ticker):
    try:
        value = _decode(raw, MAX_RESPONSE_BYTES)
        _require(isinstance(ticker, str) and SYMBOL.fullmatch(ticker), "invalid ticker")
        fields, rows = value["fields"], value["data"]
        _require(isinstance(fields, list) and len(set(fields)) == len(fields)
                 and all(key in fields for key in ("cik", "name", "ticker"))
                 and isinstance(rows, list) and len(rows) <= 50000, "mapping shape")
        found = []
        for row in rows:
            _require(isinstance(row, list) and len(row) == len(fields), "mapping columns")
            item = dict(zip(fields, row))
            if item["ticker"] == ticker:
                _require(type(item["cik"]) is int and 0 < item["cik"] < 10**10 and _text(item["name"]), "mapping identity")
                pair = {"cik": item["cik"], "name": item["name"]}
                if pair not in found:
                    found.append(pair)
        if len(found) != 1:
            raise SourceError("identity_unverified")
        return found[0]
    except SourceError:
        raise
    except (KeyError, TypeError, ValueError):
        raise SourceError("identity_unverified") from None


def _parse_rows(columns, as_of):
    required = ("accessionNumber", "filingDate", "reportDate", "acceptanceDateTime", "form", "items", "primaryDocument")
    _require(isinstance(columns, dict) and all(isinstance(columns.get(key), list) for key in required), "submissions columns")
    count = len(columns[required[0]])
    _require(count <= MAX_METADATA_ROWS and all(len(columns[key]) == count for key in required), "submissions column lengths")
    # Other SEC columns are parallel too; accepting a shifted description or
    # document-size column would make later extensions silently misassociate it.
    _require(all(not isinstance(values, list) or len(values) == count for values in columns.values()), "submissions extra column lengths")
    out, invalid, dates = [], 0, []
    window = as_of.date() - timedelta(days=LOOKBACK_DAYS)
    seen = {}
    for i in range(count):
        item = {"accession": columns["accessionNumber"][i], "form": columns["form"][i],
                "filing_date": columns["filingDate"][i], "report_date": columns["reportDate"][i] or None,
                "accepted_at": columns["acceptanceDateTime"][i], "primary_document": columns["primaryDocument"][i],
                "items": columns["items"][i]}
        try:
            item["accepted_at"] = _iso(item["accepted_at"])
            _filing(item, as_of)
            filing_day = _day(item["filing_date"])
            _require(filing_day <= as_of.date(), "future filing date")
        except (ValueError, TypeError):
            invalid += 1
            continue
        if item["accession"] in seen:
            _require(item == seen[item["accession"]], "conflicting duplicate accession")
            continue
        seen[item["accession"]] = item
        dates.append(item["filing_date"])
        if filing_day >= window:
            out.append(item)
    return {"filings": out, "invalid_count": invalid,
            "range_start": min(dates) if dates else None, "range_end": max(dates) if dates else None}


def parse_submissions(raw, cik, ticker, as_of):
    try:
        value = _decode(raw, MAX_RESPONSE_BYTES)
        _require(type(cik) is int and 0 < cik < 10**10 and isinstance(value, dict), "submissions identity")
        if (type(value.get("cik")) not in (int, str) or str(value["cik"]).lstrip("0") != str(cik)
                or not isinstance(value.get("tickers"), list) or ticker not in value["tickers"]):
            raise SourceError("identity_unverified")
        parsed = _parse_rows(value["filings"]["recent"], _instant(as_of))
        history = value["filings"].get("files", [])
        _require(isinstance(history, list) and len(history) <= MAX_METADATA_ROWS, "history descriptor bound")
        parsed["history"] = []
        seen = set()
        for descriptor in history:
            name = descriptor["name"]
            _require(isinstance(name, str) and re.fullmatch(r"CIK" + f"{cik:010d}" + r"-submissions-[0-9]{3}\.json", name)
                     and name not in seen and _count(descriptor["filingCount"], 1000000), "history descriptor")
            seen.add(name)
            start, end = _day(descriptor["filingFrom"]), _day(descriptor["filingTo"])
            _require(start <= end, "history dates")
            parsed["history"].append({"name": name, "filing_count": descriptor["filingCount"],
                                      "filing_from": start.isoformat(), "filing_to": end.isoformat()})
        return parsed
    except SourceError:
        raise
    except (KeyError, TypeError, ValueError):
        raise SourceError("metadata_invalid") from None


class _DocumentParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.parts = []
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head"):
            self.hidden += 1
        if not self.hidden:
            if tag == "a":
                self.hrefs.extend(value for key, value in attrs if key == "href" and isinstance(value, str))
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head") and self.hidden:
            self.hidden -= 1
        if not self.hidden:
            self.parts.append(" ")

    def handle_data(self, value):
        if not self.hidden:
            self.parts.append(value)


def parse_primary(raw, url):
    try:
        parsed_url = _sec_url(url)
        _require(parsed_url.path.startswith("/Archives/edgar/data/") and isinstance(raw, bytes)
                 and 0 < len(raw) <= MAX_RESPONSE_BYTES, "document shape")
        # SEC filings commonly declare legacy encodings. Lossy UTF-8 decoding
        # would make quoted text silently differ; use only a declared bounded
        # supported encoding, with strict decoding.
        encoding = "utf-8"
        declared = re.search(br"charset\s*=\s*[\"']?([A-Za-z0-9_\-]+)", raw[:4096], re.I)
        if declared:
            label = declared.group(1).decode("ascii").lower()
            encoding = {"utf-8": "utf-8", "utf8": "utf-8", "windows-1252": "cp1252", "iso-8859-1": "latin-1", "us-ascii": "ascii"}.get(label)
            _require(encoding is not None, "unsupported filing encoding")
        text = raw.decode(encoding)
        parser = _DocumentParser()
        parser.feed(text)
        parser.close()
        normalized = re.sub(r"\s+", " ", "".join(parser.parts)).strip()
        _require(not any(ord(c) < 32 for c in normalized), "filing control character")
        prefix = url.rsplit("/", 1)[0] + "/"
        links, rejected = [], 0
        for href in parser.hrefs:
            if not href or href.startswith("#"):
                continue
            try:
                candidate = urljoin(url, href)
                _sec_url(candidate)
                _require(candidate.startswith(prefix) and _basename(candidate[len(prefix):])
                         and candidate.lower().endswith((".htm", ".html")), "exhibit outside accession")
                if candidate != url and candidate not in links:
                    links.append(candidate)
            except (ValueError, TypeError):
                rejected += 1
        return {"text": normalized, "links": links, "rejected_links": rejected}
    except (ValueError, TypeError, UnicodeError):
        raise SourceError("document_invalid") from None


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        try:
            if fp is not None:
                fp.close()
        finally:
            # urllib closes only after redirect_request returns; refusal must
            # release the original response without reading or following it.
            raise SourceError("redirect_refused", http_status=code) from None


class _RequestDeadline:
    """An absolute alarm also interrupts slow HTTP headers/chunk headers.

    The production adapter runs in the main thread of Linux Actions. Pure
    parsers and injected transports have no POSIX dependency. Refuse an
    unsupported runtime or an already-owned alarm rather than weaken bounds.
    """
    def __init__(self, seconds, budget):
        self.seconds, self.budget = seconds, budget

    def __enter__(self):
        if (threading.current_thread() is not threading.main_thread()
                or not hasattr(signal, "SIGALRM") or signal.getitimer(signal.ITIMER_REAL)[0]):
            raise SourceError("invalid_response")
        self.previous = signal.getsignal(signal.SIGALRM)
        def expired(signum, frame):
            if self.budget.remaining() <= 0:
                self.budget.stop = "time_budget"
                raise SourceError("time_budget")
            raise SourceError("timeout")
        signal.signal(signal.SIGALRM, expired)
        signal.setitimer(signal.ITIMER_REAL, self.seconds)
        return self

    def __exit__(self, *args):
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, self.previous)


def validate_cache(cache_dir, *, now=None, prune=False):
    """Bound only owned SEC cache pairs; never delete unknown files.

    A rejected cache may be bypassed for network collection but must not be
    uploaded as an Actions cache. Pruning occurs only after every pair has
    validated. Metadata/body hash equality establishes this cache's ownership.
    """
    root = Path(cache_dir)
    at = _instant(now or datetime.now(timezone.utc))
    _require(not root.is_symlink(), "issuer cache directory symlink")
    if not root.exists():
        return {"entries": 0, "bytes": 0, "objects": {}}
    _require(root.is_dir(), "issuer cache directory shape")
    pairs, total = {}, 0
    for path in root.iterdir():
        _require(len(pairs) <= MAX_CACHE_ENTRIES and not path.is_symlink() and path.is_file(), "issuer cache file shape")
        match = re.fullmatch(r"([a-f0-9]{64})\.(json|bin)", path.name)
        _require(match is not None, "issuer cache contains unknown file")
        key, kind = match.groups()
        size = path.stat().st_size
        _require(0 < size <= (4096 if kind == "json" else MAX_RESPONSE_BYTES), "issuer cache file bound")
        total += size
        _require(total <= MAX_CACHE_BYTES, "issuer cache total byte bound")
        pairs.setdefault(key, {})[kind] = (path, size)
    _require(len(pairs) <= MAX_CACHE_ENTRIES, "issuer cache entry bound")
    owned, expired = {}, []
    for key, pair in pairs.items():
        _require(set(pair) == {"json", "bin"}, "issuer cache orphan file")
        with pair["json"][0].open("rb") as handle:
            meta = _decode(handle.read(4097), 4096)
        _keys(meta, ("url", "sha256", "bytes", "fetched_at"))
        _sec_url(meta["url"])
        _require("/submissions/" not in meta["url"] and _sha(meta["url"].encode("utf-8")) == key
                 and isinstance(meta["sha256"], str) and HEX.fullmatch(meta["sha256"])
                 and type(meta["bytes"]) is int and meta["bytes"] == pair["bin"][1], "issuer cache source identity")
        with pair["bin"][0].open("rb") as handle:
            body = handle.read(MAX_RESPONSE_BYTES + 1)
        _require(len(body) == meta["bytes"] and _sha(body) == meta["sha256"], "issuer cache raw digest")
        fetched = _instant(meta["fetched_at"])
        age = (at - fetched).total_seconds()
        _require(age >= 0, "issuer cache future source")
        ttl = MAPPING_CACHE_SECONDS if meta["url"] == MAPPING_URL else DOCUMENT_CACHE_SECONDS
        size = pair["json"][1] + pair["bin"][1]
        owned[key] = {"bytes": size, "url": meta["url"]}
        if age > ttl:
            expired.append(key)
    if prune:
        for key in expired:
            for path, _ in pairs[key].values():
                path.unlink()
            total -= owned.pop(key)["bytes"]
    return {"entries": len(owned), "bytes": total, "objects": owned}


class _Transport:
    def __init__(self, cache_dir=None):
        self.opener = build_opener(_NoRedirect())
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        self.last_request = None
        self.cache_usable = True
        if self.cache_dir is not None:
            try:
                validate_cache(self.cache_dir, prune=True)
            except (OSError, ValueError, TypeError):
                self.cache_usable = False

    def _cached(self, url, now):
        if self.cache_dir is None or not self.cache_usable or self.cache_dir.is_symlink():
            return None
        ttl = MAPPING_CACHE_SECONDS if url == MAPPING_URL else DOCUMENT_CACHE_SECONDS if "/Archives/" in url else 0
        if not ttl:
            return None
        key = _sha(url.encode("utf-8"))
        meta_path, body_path = self.cache_dir / f"{key}.json", self.cache_dir / f"{key}.bin"
        try:
            if meta_path.is_symlink() or body_path.is_symlink() or not meta_path.is_file() or not body_path.is_file():
                return None
            with meta_path.open("rb") as handle:
                meta = _decode(handle.read(4097), 4096)
            _keys(meta, ("url", "sha256", "bytes", "fetched_at"))
            _require(meta["url"] == url and _count(meta["bytes"], MAX_RESPONSE_BYTES), "cache source identity")
            fetched = _instant(meta["fetched_at"])
            _require(0 <= (now - fetched).total_seconds() <= ttl - MAX_COLLECTION_SECONDS, "cache source age")
            with body_path.open("rb") as handle:
                body = handle.read(MAX_RESPONSE_BYTES + 1)
            _require(body and len(body) == meta["bytes"] and _sha(body) == meta["sha256"], "cache body integrity")
            return {"body": body, "observed_at": fetched, "fetched_at": fetched, "cache_status": "verified_cache"}
        except (OSError, TypeError, ValueError):
            return None

    def _save(self, url, body, now):
        if self.cache_dir is None or not self.cache_usable or self.cache_dir.is_symlink() or "/submissions/" in url:
            return
        key = _sha(url.encode("utf-8"))
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            state = validate_cache(self.cache_dir, now=now, prune=True)
            meta_raw = _encode({"url": url, "sha256": _sha(body), "bytes": len(body), "fetched_at": _iso(now)})
            old_bytes = state["objects"].get(key, {}).get("bytes", 0)
            if (state["entries"] + (key not in state["objects"]) > MAX_CACHE_ENTRIES
                    or state["bytes"] - old_bytes + len(body) + len(meta_raw) > MAX_CACHE_BYTES):
                return
            for suffix, raw in (("bin", body), ("json", meta_raw)):
                path = self.cache_dir / f"{key}.{suffix}"
                if path.is_symlink():
                    return
                with tempfile.NamedTemporaryFile(dir=self.cache_dir, delete=False) as handle:
                    temp = Path(handle.name)
                    handle.write(raw)
                try:
                    os.replace(temp, path)
                finally:
                    temp.unlink(missing_ok=True)
        except (OSError, ValueError, TypeError):
            # Cache availability is an optimization, never source success.
            self.cache_usable = False
            return

    def fetch(self, url, budget):
        budget.check_time()
        _sec_url(url)
        now = datetime.now(timezone.utc)
        cached = self._cached(url, now)
        if cached is not None:
            budget.check_time()
            return cached
        budget.check_time()
        if budget.requests >= MAX_REQUESTS:
            budget.begin_request()
        if self.last_request is not None:
            wait = MIN_REQUEST_INTERVAL_SECONDS - (time.monotonic() - self.last_request)
            if wait > 0:
                _require(wait < MAX_COLLECTION_SECONDS, "issuer request spacing")
                if budget.remaining() <= wait:
                    budget.stop = "time_budget"
                    raise SourceError("time_budget")
                time.sleep(wait)
        timeout = min(10, budget.remaining())
        if timeout <= 0:
            budget.stop = "time_budget"
            raise SourceError("time_budget")
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity", "Accept": "application/json,text/html;q=0.9"})
        budget.begin_request()
        self.last_request = time.monotonic()
        try:
            with _RequestDeadline(timeout, budget), self.opener.open(request, timeout=timeout) as response:
                if response.status != 200 or response.headers.get("Content-Encoding", "identity").lower() not in ("identity", ""):
                    raise SourceError("invalid_response")
                chunks, size = [], 0
                request_deadline = self.last_request + timeout
                while True:
                    remaining = min(budget.remaining(), request_deadline - time.monotonic())
                    if remaining <= 0:
                        if budget.remaining() <= 0:
                            budget.stop = "time_budget"
                        raise SourceError("time_budget")
                    if budget.bytes >= MAX_DOWNLOAD_BYTES:
                        budget.stop = "size_limit"
                        raise SourceError("size_limit")
                    sock = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
                    if sock is not None:
                        sock.settimeout(remaining)
                    read = getattr(response, "read1", response.read)
                    chunk = read(min(65536, MAX_RESPONSE_BYTES + 1 - size, MAX_DOWNLOAD_BYTES - budget.bytes))
                    if not chunk:
                        break
                    size += len(chunk)
                    budget.add_bytes(len(chunk))
                    if size > MAX_RESPONSE_BYTES:
                        raise SourceError("size_limit")
                    chunks.append(chunk)
                body = b"".join(chunks)
                if not body:
                    raise SourceError("invalid_response")
        except HTTPError as error:
            status = error.code
            try:
                error.close()  # Never read or persist an arbitrary error body.
            finally:
                if type(status) is not int or not 300 <= status <= 599:
                    raise SourceError("invalid_response") from None
                code = "redirect_refused" if status < 400 else "rate_limit" if status == 429 else "http_error"
                raise SourceError(code, http_status=status) from None
        except (TimeoutError, URLError, OSError) as error:
            code = "timeout" if isinstance(error, TimeoutError) or isinstance(getattr(error, "reason", None), TimeoutError) else "network_error"
            raise SourceError(code) from None
        now = datetime.now(timezone.utc)
        self._save(url, body, now)
        return {"body": body, "observed_at": now}


class _Budget:
    def __init__(self, started=None):
        self.started = time.monotonic() if started is None else started
        self.requests = 0
        self.bytes = 0
        self.stop = None

    def remaining(self):
        return MAX_COLLECTION_SECONDS - FINALIZATION_SECONDS - (time.monotonic() - self.started)

    def check_time(self):
        if self.remaining() <= 0:
            self.stop = "time_budget"
            raise SourceError(self.stop)

    def begin_request(self):
        self.check_time()
        if self.requests >= MAX_REQUESTS:
            self.stop = "request_budget"
            raise SourceError(self.stop)
        self.requests += 1

    def add_bytes(self, count):
        self.bytes += count
        if self.bytes > MAX_DOWNLOAD_BYTES:
            self.stop = "size_limit"
            raise SourceError(self.stop)


class _Fetcher:
    def __init__(self, fetch, cache_dir, start, deadline_started=None):
        self.budget = _Budget(deadline_started)
        self.transport = _Transport(cache_dir) if fetch is None else None
        self.fetch = fetch
        self.start = start
        self.captures = {}
        self.capture_bytes = 0

    def get(self, url):
        self.budget.check_time()
        _sec_url(url)
        if self.transport:
            received = self.transport.fetch(url, self.budget)
        else:
            self.budget.begin_request()
            try:
                received = self.fetch(url)
            except SourceError:
                raise
            except TimeoutError:
                raise SourceError("timeout") from None
            except (OSError, ValueError):
                raise SourceError("network_error") from None
            if isinstance(received, dict) and received.get("cache_status") == "verified_cache":
                self.budget.requests -= 1
            elif isinstance(received, dict) and isinstance(received.get("body"), bytes):
                self.budget.add_bytes(len(received["body"]))
        self.budget.check_time()
        try:
            body = received["body"]
            if isinstance(body, bytes) and len(body) > MAX_RESPONSE_BYTES:
                raise SourceError("size_limit")
            _require(isinstance(body, bytes) and 0 < len(body) <= MAX_RESPONSE_BYTES, "source bytes")
            checked = _instant(received["observed_at"])
            fetched = _instant(received.get("fetched_at", checked))
            _require(fetched <= checked, "source response clocks")
            source = {"url": url, "raw_sha256": _sha(body), "bytes": len(body), "fetched_at": _iso(fetched),
                      "checked_at": _iso(checked), "cache_status": received.get("cache_status", "network")}
            if source["raw_sha256"] not in self.captures:
                if self.capture_bytes + len(body) > MAX_CAPTURE_BYTES:
                    self.budget.stop = "size_limit"
                    raise SourceError("size_limit")
                self.captures[source["raw_sha256"]] = body
                self.capture_bytes += len(body)
            return body, source
        except SourceError:
            raise
        except (KeyError, TypeError, ValueError):
            raise SourceError("invalid_response") from None


def _empty_index(start):
    return {"window_start": (start.date() - timedelta(days=LOOKBACK_DAYS)).isoformat(),
            "window_end": start.date().isoformat(), "coverage_status": "unknown", "reason": "SEC index coverage has not been established.",
            "range_start": None, "range_end": None, "metadata_count": 0, "eligible_current_report_count": 0,
            "not_selected_count": 0, "history_files_advertised": 0, "history_files_fetched": 0,
            "history_sources": [], "selected_accessions": [], "listed_filings": [], "exhibit_links_observed": 0, "exhibit_links_not_fetched": 0}


def _empty_issuer(ticker, start):
    return {"ticker": ticker, "status": "unavailable", "reason": "SEC source retrieval is unavailable.",
            "identity": {"status": "unverified", "cik": None, "name": None, "mapping_source": None, "submissions_source": None},
            "index": _empty_index(start), "documents": [], "errors": []}


def _http_phase(phase, url, identity, metadata, accessions):
    """Bind diagnostics to an existing collection stage and requested source.

    A response cannot supply this path, phase, a redirect destination or text.
    Old two-field errors remain readable without inventing missing diagnostics.
    """
    _require(isinstance(phase, str) and phase in ("mapping", "submissions", "history", "primary", "exhibit"), "issuer HTTP source phase")
    _require(isinstance(url, str), "issuer HTTP source URL")
    if phase == "mapping":
        _require(url == MAPPING_URL, "issuer HTTP mapping URL")
        return
    cik = identity["cik"]
    _require(type(cik) is int and 0 < cik < 10**10, "issuer HTTP source identity")
    if phase == "submissions":
        allowed = url == f"https://data.sec.gov/submissions/CIK{cik:010d}.json"
    elif phase == "history":
        allowed = bool(re.fullmatch(r"https://data.sec.gov/submissions/CIK" + f"{cik:010d}" + r"-submissions-[0-9]{3}\.json", url))
    else:
        allowed = False
        for accession in accessions:
            prefix = f'https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace("-", "")}/'
            primary_url = prefix + metadata[accession]["primary_document"]
            if phase == "primary":
                allowed |= url == primary_url
            else:
                allowed |= (url.startswith(prefix) and _basename(url[len(prefix):])
                            and url.lower().endswith((".htm", ".html")) and url != primary_url)
    _require(allowed, "issuer HTTP phase and requested URL")


def _error(row, code, url=None, *, http_status=None, phase=None):
    item = {"code": code, "source_url": url}
    if http_status is not None:
        _require(_http_failure(code, http_status), "issuer HTTP status and code")
        item.update(http_status=http_status, source_phase=phase)
    row["errors"].append(item)


def _excerpt(text):
    excerpt = text.encode("utf-8")[:MAX_EXCERPT_BYTES].decode("utf-8", errors="ignore")
    return {"text": excerpt, "normalization": "html_text_v1", "start": 0, "characters": len(excerpt),
            "normalized_characters": len(text), "truncated": len(excerpt) < len(text), "sha256": _sha(excerpt.encode("utf-8"))}


def _document(filing, role, source, parsed):
    return {"accession": filing["accession"], "form": filing["form"], "role": role, "source": source,
            "filing_date": filing["filing_date"], "report_date": filing["report_date"], "accepted_at": filing["accepted_at"],
            "release_date": None, "excerpt": _excerpt(parsed["text"])}


def _collect_issuer(row, mapping_body, mapping_source, fetcher, start):
    ticker = row["ticker"]
    try:
        fetcher.budget.check_time()
        mapped = parse_mapping(mapping_body, ticker)
        fetcher.budget.check_time()
    except SourceError as error:
        row.update(status="identity_unverified", reason="SEC ticker mapping does not establish one issuer identity.")
        row["identity"]["mapping_source"] = mapping_source
        _error(row, error.code, MAPPING_URL, http_status=error.http_status, phase="mapping")
        return
    row["identity"].update(cik=mapped["cik"], name=mapped["name"], mapping_source=mapping_source)
    cik = mapped["cik"]
    url = f"https://data.sec.gov/submissions/CIK{cik:010d}.json"
    try:
        body, source = fetcher.get(url)
        parsed = parse_submissions(body, cik, ticker, start)
        fetcher.budget.check_time()
    except SourceError as error:
        row.update(status="identity_unverified" if error.code == "identity_unverified" else "unavailable",
                   reason="SEC submissions could not establish current issuer metadata.")
        _error(row, error.code, url, http_status=error.http_status, phase="submissions")
        return
    row["identity"].update(status="verified", submissions_source=source)
    index = row["index"]
    index.update(range_start=parsed["range_start"], range_end=parsed["range_end"], history_files_advertised=len(parsed["history"]))
    filings = {filing["accession"]: filing for filing in parsed["filings"]}
    if parsed["invalid_count"]:
        _error(row, "metadata_invalid", url)
    history = [h for h in parsed["history"] if _day(h["filing_to"]) >= _day(index["window_start"])
               and _day(h["filing_from"]) <= start.date()]
    history.sort(key=lambda h: (h["filing_to"], h["name"]), reverse=True)
    needs_history = index["range_start"] is None or index["range_start"] > index["window_start"]
    if needs_history:
        for descriptor in history[:MAX_HISTORY_FILES]:
            history_url = f'https://data.sec.gov/submissions/{descriptor["name"]}'
            try:
                raw, history_source = fetcher.get(history_url)
                old = _parse_rows(_decode(raw, MAX_RESPONSE_BYTES), start)
                fetcher.budget.check_time()
                for filing in old["filings"]:
                    _require(filing["accession"] not in filings or filings[filing["accession"]] == filing, "conflicting history accession")
                for filing in old["filings"]:
                    filings[filing["accession"]] = filing
                index["history_files_fetched"] += 1
                index["history_sources"].append(history_source)
                if old["range_start"] is not None:
                    index["range_start"] = min(filter(None, (index["range_start"], old["range_start"])))
                    index["range_end"] = max(filter(None, (index["range_end"], old["range_end"])))
                if old["invalid_count"]:
                    _error(row, "metadata_invalid", history_url)
            except (SourceError, ValueError, KeyError, TypeError) as error:
                _error(row, error.code if isinstance(error, SourceError) else "metadata_invalid", history_url,
                       http_status=error.http_status if isinstance(error, SourceError) else None, phase="history")
    full_window = index["range_start"] is not None and index["range_start"] <= index["window_start"]
    index["coverage_status"] = "observed_window" if full_window and not row["errors"] else "partial"
    index["reason"] = None if index["coverage_status"] == "observed_window" else "The full requested index history has not been established; older content is not cleared."
    if not full_window:
        _error(row, "history_incomplete")
    ordered = sorted(filings.values(), key=lambda f: (f["accepted_at"], f["accession"]), reverse=True)
    reports = [filing for filing in ordered if filing["form"] in FORMS]
    selected = reports[:MAX_REPORTS]
    index.update(metadata_count=len(ordered), eligible_current_report_count=len(reports),
                 not_selected_count=len(reports) - len(selected), selected_accessions=[f["accession"] for f in selected],
                 listed_filings=reports[:MAX_LISTED_FILINGS])
    for filing in selected:
        document_url = f'https://www.sec.gov/Archives/edgar/data/{cik}/{filing["accession"].replace("-", "")}/{filing["primary_document"]}'
        try:
            raw, source = fetcher.get(document_url)
            primary = parse_primary(raw, document_url)
            fetcher.budget.check_time()
            row["documents"].append(_document(filing, "primary", source, primary))
        except SourceError as error:
            _error(row, error.code, document_url, http_status=error.http_status, phase="primary")
            continue
        index["exhibit_links_observed"] += len(primary["links"])
        fetched_exhibits = 0
        for exhibit_url in primary["links"][:MAX_EXHIBITS]:
            try:
                raw, source = fetcher.get(exhibit_url)
                exhibit = parse_primary(raw, exhibit_url)
                fetcher.budget.check_time()
                row["documents"].append(_document(filing, "exhibit", source, exhibit))
                fetched_exhibits += 1
            except SourceError as error:
                _error(row, error.code, exhibit_url, http_status=error.http_status, phase="exhibit")
        index["exhibit_links_not_fetched"] += len(primary["links"]) - fetched_exhibits
    partial = bool(row["errors"] or index["not_selected_count"] or index["exhibit_links_not_fetched"]
                   or any(d["excerpt"]["truncated"] for d in row["documents"]))
    row.update(status="partial" if partial else "collected", reason="Retrieval is bounded; unreviewed and unfetched content remains." if partial else None)


def collect(canonical_raw, *, fetch=None, now=None, finished_at=None, run_id, dry_run=True,
            previous_raw=None, allow_fixture=False, cache_dir=None):
    deadline_started = time.monotonic()
    from src import morning, sessions
    pinned = now is not None
    start = _instant(now if pinned else datetime.now(timezone.utc))
    binding = morning.bind_record(canonical_raw, allow_fixture=allow_fixture)
    data = _decode(canonical_raw, MAX_PUBLICATION_BYTES)
    morning.admitted_rows(data)
    candidates = _candidates(data)
    tickers = list(dict.fromkeys(row["ticker"] for row in candidates))
    applicable = True
    if not allow_fixture:
        expected = sessions.completed_session(start)
        applicable = binding["measured_session"] == str(expected)
    selected = tickers[:MAX_ISSUERS] if applicable else []
    for candidate in candidates:
        candidate["selected"] = candidate["ticker"] in selected
    fetcher = _Fetcher(fetch, cache_dir, start, deadline_started)
    issuers = [_empty_issuer(ticker, start) for ticker in selected]
    if issuers:
        try:
            mapping_body, mapping_source = fetcher.get(MAPPING_URL)
            for row in issuers:
                _collect_issuer(row, mapping_body, mapping_source, fetcher, start)
        except SourceError as error:
            for row in issuers:
                _error(row, error.code, MAPPING_URL, http_status=error.http_status, phase="mapping")
    completion = _instant(finished_at if finished_at is not None else start if pinned else datetime.now(timezone.utc))
    bundle = {"schema_version": VERSION, "publication": binding, "collection_started_at": _iso(start),
              "generated_at": _iso(completion), "as_of": _iso(start),
              "window_start": (start.date() - timedelta(days=LOOKBACK_DAYS)).isoformat(),
              "candidates": candidates, "issuers": issuers,
              "stats": {"request_count": fetcher.budget.requests,
                        "downloaded_bytes": fetcher.budget.bytes, "capture_bytes": fetcher.capture_bytes, "budget_stop": fetcher.budget.stop}}
    status = ("inapplicable" if not applicable else "no_candidates" if not candidates
              else "unavailable" if all(row["status"] in ("unavailable", "identity_unverified") for row in issuers)
              else "partial" if len(selected) < len(tickers) or any(row["status"] != "collected" for row in issuers) else "collected")
    bundle_raw = _encode(bundle)
    receipt = {"schema_version": VERSION, "status": status, "dry_run": dry_run, "collection_run_id": run_id,
               "collection_started_at": _iso(start), "generated_at": _iso(completion),
               "expires_at": _iso(completion + timedelta(seconds=RECEIPT_TTL_SECONDS)), "publication": binding,
               "previous_receipt_sha256": _sha(previous_raw) if previous_raw is not None else None,
               "policy": deepcopy(POLICY), "selection": {"candidate_count": len(candidates), "issuer_count": len(tickers),
                   "selected_issuer_count": len(selected), "omitted_issuer_count": len(tickers) - len(selected), "selected_tickers": selected},
               "bundle": {"sha256": _sha(bundle_raw), "bytes": len(bundle_raw), "path": f"issuer-evidence/{_sha(bundle_raw)}.json"},
               "coverage": deepcopy(COVERAGE)}
    receipt_raw = _encode(receipt)
    validate_for_publication(canonical_raw, receipt_raw, bundle_raw, allow_fixture=allow_fixture)
    return {"receipt": receipt, "receipt_bytes": receipt_raw, "bundle": bundle, "bundle_bytes": bundle_raw,
            "captures": fetcher.captures}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, default=Path("docs/data.json"))
    parser.add_argument("--previous", type=Path, default=Path("docs/issuer-evidence.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", ""))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--cache-dir", type=Path)
    args = parser.parse_args()
    try:
        _require(args.record.is_file() and not args.record.is_symlink(), "issuer canonical file")
        with args.record.open("rb") as handle:
            raw = handle.read(MAX_PUBLICATION_BYTES + 1)
        previous = None
        if args.previous.exists():
            _require(args.previous.is_file() and not args.previous.is_symlink(), "issuer previous file")
            with args.previous.open("rb") as handle:
                previous = handle.read(MAX_RECEIPT_BYTES + 1)
            parse_receipt(previous)
        result = collect(raw, run_id=args.run_id, dry_run=args.dry_run, previous_raw=previous, cache_dir=args.cache_dir)
        _require(not args.output.is_symlink(), "issuer output directory")
        args.output.mkdir(parents=True, exist_ok=True)
        def output(relative, body):
            target = args.output / relative
            _require(not target.is_symlink(), "issuer output file symlink")
            _require(not target.parent.is_symlink(), "issuer output parent symlink")
            target.parent.mkdir(exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(body)
            try:
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
        bundle_path = args.output / result["receipt"]["bundle"]["path"]
        _require(not bundle_path.parent.is_symlink(), "issuer bundle directory symlink")
        bundle_path.parent.mkdir(exist_ok=True)
        output(result["receipt"]["bundle"]["path"], result["bundle_bytes"])
        captures_dir = args.output / "captures"
        _require(not captures_dir.is_symlink(), "issuer captures directory symlink")
        captures_dir.mkdir(exist_ok=True)
        manifest = []
        for sha, body in result["captures"].items():
            output(f"captures/{sha}.bin", body)
            manifest.append({"sha256": sha, "bytes": len(body), "path": f"captures/{sha}.bin"})
        output("manifest.json", _encode({"schema_version": 1, "raw_capture_retention_days": 30,
            "raw_capture_bytes": result["bundle"]["stats"]["capture_bytes"], "captures": manifest}))
        output("issuer-evidence.json", result["receipt_bytes"])
        print(f'Issuer evidence: {result["receipt"]["status"]}; {len(result["bundle"]["issuers"])} selected issuers; no entry authority.')
        return 0
    except (OSError, ValueError, KeyError, TypeError):
        print("Issuer evidence collection failed; no raw response was logged.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
