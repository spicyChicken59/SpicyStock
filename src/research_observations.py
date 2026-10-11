"""Dated IEX observations of the current registered research cohort. Never an order.

The cohort's allocation-fit rows are hypothetical model research, not tickets.
This companion binds the exact publication, the exact cohort receipt and
bundle and each row's original evidence, then records one bounded single-venue
IEX snapshot per run through the morning transport. Halts, delayed volume,
issuer news and earnings are explicitly not checked here, and nothing in the
receipt is a ready label, a personal size or an entry permission.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from src import market_data, morning, provenance, stop_research, timing

VERSION = 1
RECEIPT_FILE = "research-observations.json"
MAX_OBSERVATION_BYTES = 64 * 1024
MAX_REQUESTS = 1
FEED = "iex"
POLICY = {
    "version": VERSION, "feed": FEED, "max_requests_per_run": MAX_REQUESTS,
    "selection": "allocation_fit_rows_of_the_bound_registered_cohort",
    "cohort_policy_id": stop_research.POLICY_ID, "cohort_schema_version": stop_research.VERSION,
    "quote_max_age_seconds": morning.POLICY["quote_max_age_seconds"],
    "trade_max_age_seconds": morning.POLICY["trade_max_age_seconds"],
    "snapshot_max_age_seconds": morning.POLICY["snapshot_max_age_seconds"],
    "max_future_skew_seconds": morning.POLICY["max_future_skew_seconds"],
    "preopen_minutes": morning.POLICY["preopen_minutes"],
    "max_collection_seconds": morning.POLICY["max_collection_seconds"],
    "market_timezone": morning.POLICY["market_timezone"],
}
LIMITS = ["dated_best_effort_snapshot", "iex_single_venue_not_consolidated", "no_delayed_volume_request",
          "halts_news_earnings_not_checked", "research_rows_are_not_tickets",
          "no_ready_label_or_entry_authority", "no_personal_sizing_or_cash", "broker_verification_required"]
COVERAGE = {"halts": "not_checked", "delayed_volume": "not_requested", "issuer_news": "not_checked",
            "earnings": "not_checked", "corporate_action": "archived_cohort_registry_only"}
STATUSES = ("observed", "partial", "provider_unavailable", "no_research_rows", "inapplicable")
REASONS = (None, "wrong_session", "entry_window_ended", "before_collection_window", "stale_publication",
           "future_publication", "cohort_missing", "cohort_not_current")
ENVELOPE_KEYS = {"schema_version", "collection_started_at", "generated_at", "expires_at", "observation_run_id",
                 "previous_observation_sha256", "dry_run", "publication", "cohort", "policy", "status", "reason",
                 "entry_phase", "source", "coverage", "rows", "limits"}
COHORT_KEYS = {"receipt_sha256", "bundle_sha256", "bundle_path", "bundle_bytes", "policy_id", "generated_at",
               "status", "applicable_session", "bound"}
ROW_KEYS = {"rank", "ticker", "kind", "evidence", "projection_sha256", "levels", "event"}
HEX = re.compile(r"[0-9a-f]{64}\Z")


def _require(condition, message):
    if not condition:
        raise ValueError("research observation: " + message)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def cohort_identity(binding, receipt_raw, bundle_raw):
    """The exact cohort this observation can describe, or None when none is published.

    The receipt and bundle are validated by the research producer's own
    strict reader; `bound` says whether that cohort is the current
    publication's, which is the only state that can select a row.
    """
    if receipt_raw is None:
        _require(bundle_raw is None, "a cohort bundle without its receipt")
        return None, None
    bundle = stop_research.validate_bundle(receipt_raw, bundle_raw)
    receipt = stop_research.parse_receipt(receipt_raw)
    cohort = {"receipt_sha256": _sha(receipt_raw), "bundle_sha256": receipt["bundle"]["sha256"],
              "bundle_path": receipt["bundle"]["path"], "bundle_bytes": receipt["bundle"]["bytes"],
              "policy_id": receipt["policy"]["id"], "generated_at": receipt["timing"]["generated_at"],
              "status": receipt["status"], "applicable_session": receipt["publication"]["applicable_session"],
              "bound": receipt["publication"] == binding}
    return cohort, bundle


def research_rows(bundle, cohort):
    """Only the bound cohort's allocation-fit rows, with the producer's own levels."""
    if cohort is None or not cohort["bound"] or bundle["status"] != "recorded":
        return []
    rows = []
    for row in bundle["rows"]:
        if not row["research"]["allocation_fit"]:
            continue
        levels = row["levels"]
        _require(levels is not None and not row["event"]["blocked"], "allocation fit contradicts its cohort")
        rows.append({"rank": row["rank"], "ticker": row["ticker"], "kind": "anticipation",
                     "evidence": dict(row["evidence"]), "projection_sha256": row["research"]["projection_sha256"],
                     "levels": {"trigger": levels["trigger"], "limit": levels["limit"], "stop": levels["stop"],
                                "entry_low": levels["trigger"], "day2_spent_above": None},
                     "event": deepcopy(row["event"])})
    return rows


def _reason(data, now, cohort):
    reason = morning._reason(data, now)
    if reason:
        return reason
    if cohort is None:
        return "cohort_missing"
    if not cohort["bound"]:
        return "cohort_not_current"
    return None


def _source():
    return {**morning._source(FEED), "requests": 0}


def _status(rows, source, reason):
    if reason:
        return "inapplicable"
    if not rows:
        return "no_research_rows"
    if source["status"] == "unavailable":
        return "provider_unavailable"
    return "observed" if all(r["trade"]["status"] == r["quote"]["status"] == "recent" for r in rows) else "partial"


def _previous(previous_raw):
    if previous_raw is None:
        return None
    _require(isinstance(previous_raw, bytes) and 0 < len(previous_raw) <= MAX_OBSERVATION_BYTES,
             "prior receipt exceeds size bound")
    previous = morning._json(previous_raw)
    _require(isinstance(previous, dict) and previous.get("schema_version") == VERSION, "prior receipt is unsupported")
    return previous


def collect(canonical_raw, receipt_raw=None, bundle_raw=None, *, client=None, clock=None, dry_run=False,
            observation_run_id=None, previous_raw=None):
    """One bounded observation; an injectable clock and provider make it a pure function."""
    clock = clock or (lambda: datetime.now(timezone.utc))
    started = clock()
    _require(morning._instant(started) is not None, "collection requires an aware clock")
    data, binding = morning._publication(canonical_raw, allow_fixture=dry_run)
    cohort, bundle = cohort_identity(binding, receipt_raw, bundle_raw)
    _previous(previous_raw)
    reason = _reason(data, started, cohort)
    base_rows = research_rows(bundle, cohort)
    requested = [] if reason else sorted({r["ticker"] for r in base_rows})
    source, response = _source(), {}
    if requested:
        if client is None and any(not os.environ.get(k, "").strip() for k in market_data.REQUIRED_ENV):
            source.update(status="unavailable", entitlement="unavailable", checked_at=clock().isoformat(),
                          error_kind="missing_credentials")
        else:
            client = client or market_data.get_clients()
            response, fetched = morning._fetch(client, requested, FEED, clock)
            source = {**fetched, "requests": 1}
    completed = clock()
    _require(morning._instant(completed) is not None and completed >= started, "collection clock moved backwards")
    session, ok = binding["applicable_session"], source["status"] == "ok"
    observed_at = morning._instant(source["checked_at"])
    rows = []
    for base in base_rows if requested else []:
        live = response.get(base["ticker"])
        trade = morning.trade_observation(morning._get(live, "latest_trade"), completed, session, ok, observed_at=observed_at)
        quote = morning.quote_observation(morning._get(live, "latest_quote"), completed, session, ok, observed_at=observed_at)
        rows.append({**base, "trade": trade, "quote": quote,
                     "price_checks": {"trade": morning.price_state(trade["price"], base["levels"], trade["status"]),
                                      "ask": morning.price_state(quote["ask"], base["levels"], quote["status"])}})
    out = {"schema_version": VERSION, "collection_started_at": started.isoformat(),
           "generated_at": completed.isoformat(),
           "expires_at": (completed + timedelta(seconds=POLICY["snapshot_max_age_seconds"])).isoformat(),
           "observation_run_id": str(observation_run_id or os.environ.get("GITHUB_RUN_ID") or "local"),
           "previous_observation_sha256": _sha(previous_raw) if previous_raw is not None else None,
           "dry_run": bool(dry_run), "publication": binding, "cohort": cohort, "policy": deepcopy(POLICY),
           "status": _status(rows, source, reason), "reason": reason,
           "entry_phase": timing.phase(data["run"]["timing"], completed),
           "source": source, "coverage": dict(COVERAGE), "rows": rows, "limits": list(LIMITS)}
    validate_observation(out, canonical_raw, receipt_raw, bundle_raw, previous_raw=previous_raw, require_continuity=True)
    return out


def validate_observation(out, canonical_raw, receipt_raw=None, bundle_raw=None, *, previous_raw=None,
                         require_continuity=False):
    """Strict offline gate: every field is re-derived from the bound inputs."""
    try:
        _validate(out, canonical_raw, receipt_raw, bundle_raw, previous_raw, require_continuity)
    except (KeyError, TypeError, AttributeError, IndexError, OverflowError):
        raise ValueError("research observation: malformed observation structure") from None


def _validate(out, canonical_raw, receipt_raw, bundle_raw, previous_raw, require_continuity):
    _require(isinstance(out, dict) and type(out.get("schema_version")) is int and out["schema_version"] == VERSION
             and type(out.get("dry_run")) is bool, "unsupported observation envelope")
    _require(set(out) == ENVELOPE_KEYS, "observation envelope fields differ")
    previous_sha = out["previous_observation_sha256"]
    _require(previous_sha is None or isinstance(previous_sha, str) and HEX.fullmatch(previous_sha), "invalid prior receipt binding")
    data, binding = morning._publication(canonical_raw, allow_fixture=out["dry_run"])
    _require(out["publication"] == binding and set(out["publication"]) == set(binding), "publication binding differs")
    cohort, bundle = cohort_identity(binding, receipt_raw, bundle_raw)
    _require(out["cohort"] == cohort and (cohort is None or set(out["cohort"]) == COHORT_KEYS), "cohort binding differs")
    _require(provenance.digest(out["policy"]) == provenance.digest(POLICY) and out["limits"] == LIMITS
             and out["coverage"] == COVERAGE, "observation policy differs")
    _require(morning._text(out["observation_run_id"], 128) is not None, "invalid observation run identity")
    started, generated, expires = (morning._instant(out[k]) for k in ("collection_started_at", "generated_at", "expires_at"))
    _require(all((started, generated, expires)) and started <= generated
             and expires == generated + timedelta(seconds=POLICY["snapshot_max_age_seconds"]), "invalid collection time ordering")
    _require((generated - started).total_seconds() <= POLICY["max_collection_seconds"], "collection exceeded duration bound")
    _require(out["reason"] in REASONS and out["reason"] == _reason(data, started, cohort), "observation reason differs")
    _require(out["status"] in STATUSES, "unknown observation status")
    _require(out["entry_phase"] == timing.phase(data["run"]["timing"], generated), "observation phase differs")
    expected = [] if out["reason"] else research_rows(bundle, cohort)
    rows = out["rows"]
    _require(isinstance(rows, list) and len(rows) == len(expected), "observation row membership differs")
    source, reference = out["source"], _source()
    _require(isinstance(source, dict) and set(source) == set(reference), "invalid source metadata")
    for key in ("feed", "scope", "minimum_delay_seconds"):
        _require(source[key] == reference[key], "source scope differs")
    _require(source["error_kind"] in morning.SOURCE_ERRORS, "unknown provider error")
    _require(type(source["requests"]) is int and 0 <= source["requests"] <= MAX_REQUESTS, "request budget exceeded")
    if not expected:
        _require(source == reference, "an inapplicable observation requested a provider")
    else:
        checked = morning._instant(source["checked_at"])
        _require(checked is not None and started <= checked <= generated, "invalid provider check time")
        _require((source["status"], source["entitlement"]) in (("ok", "request_succeeded"), ("unavailable", "unavailable")),
                 "invalid entitlement observation")
        _require((source["error_kind"] is None) == (source["status"] == "ok"), "provider status contradicts error")
        _require(source["requests"] == (0 if source["error_kind"] == "missing_credentials" else 1), "request count differs")
    session, ok = binding["applicable_session"], source["status"] == "ok"
    observed_at = morning._instant(source["checked_at"])
    for row, base in zip(rows, expected, strict=True):
        _require(isinstance(row, dict) and set(row) == ROW_KEYS | {"trade", "quote", "price_checks"}
                 and all(row[k] == v for k, v in base.items()), "row identity, evidence or levels differ")
        trade, quote = row["trade"], row["quote"]
        _require(isinstance(trade, dict) and isinstance(quote, dict), "missing quote observations")
        for datum in (trade, quote):
            _require(datum.get("status") in ("recent", "stale", "missing", "invalid", "unavailable"), "unknown quote state")
            _require(datum.get("conditions") is None or morning._conditions(datum["conditions"]) is not None, "invalid quote conditions")
        replay_trade = morning.trade_observation(trade if trade["status"] not in ("missing", "unavailable") else None,
                                                 generated, session, ok, observed_at=observed_at)
        quote_raw = {**quote, "bid_price": quote.get("bid"), "ask_price": quote.get("ask")}
        replay_quote = morning.quote_observation(quote_raw if quote["status"] not in ("missing", "unavailable") else None,
                                                 generated, session, ok, observed_at=observed_at)
        _require(trade == replay_trade and quote == replay_quote, "quote observation cannot be reproduced")
        _require(row["price_checks"] == {"trade": morning.price_state(trade["price"], base["levels"], trade["status"]),
                                         "ask": morning.price_state(quote["ask"], base["levels"], quote["status"])},
                 "price comparison differs")
    _require(out["status"] == _status(rows, source, out["reason"]), "observation status contradicts its measurements")
    if require_continuity or previous_raw is not None:
        prior_sha = _sha(previous_raw) if previous_raw is not None else None
        _require(previous_sha == prior_sha, "prior observation bytes differ")
        _previous(previous_raw)
    encoded = json.dumps(out, allow_nan=False, separators=(",", ":")).encode()
    _require(len(encoded) <= MAX_OBSERVATION_BYTES, "observation exceeds size bound")


def read_cohort(docs):
    """The published cohort receipt and bundle beside the record, or (None, None)."""
    docs = Path(docs)
    receipt_path = docs / stop_research.RECEIPT_FILE
    if not receipt_path.exists() and not receipt_path.is_symlink():
        return None, None
    receipt_raw = stop_research._safe_read(docs, stop_research.RECEIPT_FILE, stop_research.MAX_RECEIPT_BYTES)
    receipt = stop_research.parse_receipt(receipt_raw)
    bundle_raw = stop_research._safe_read(docs, receipt["bundle"]["path"], stop_research.MAX_BUNDLE_BYTES)
    return receipt_raw, bundle_raw


def run(*, docs=Path("docs"), output=None, dry_run=False, client=None, clock=None):
    docs = Path(docs)
    output = Path(output) if output is not None else docs / RECEIPT_FILE
    _require(output.resolve() == (docs / RECEIPT_FILE).resolve()
             or not output.resolve().is_relative_to(docs.resolve()), "output must not overwrite publication files")
    raw = (docs / "data.json").read_bytes()
    receipt_raw, bundle_raw = read_cohort(docs)
    previous_path = docs / RECEIPT_FILE
    previous_raw = previous_path.read_bytes() if previous_path.exists() else None
    observation = collect(raw, receipt_raw, bundle_raw, client=client, clock=clock, dry_run=dry_run, previous_raw=previous_raw)
    _require((docs / "data.json").read_bytes() == raw, "publication changed during collection")
    _require(read_cohort(docs) == (receipt_raw, bundle_raw), "research cohort changed during collection")
    _require((previous_path.read_bytes() if previous_path.exists() else None) == previous_raw,
             "previous observation changed during collection")
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(observation, allow_nan=False, indent=2).encode() + b"\n"
    with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".research-observations-", delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            os.replace(temporary, output)
        finally:
            temporary.unlink(missing_ok=True)
    return observation


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--docs", type=Path, default=Path("docs"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = run(docs=args.docs, output=args.output, dry_run=args.dry_run)
    except Exception:
        print("Research observation refused: invalid publication, cohort or collection; no receipt replaced.")
        return 1
    print(json.dumps({"status": result["status"], "reason": result["reason"], "rows": len(result["rows"]),
                      "requests": result["source"]["requests"], "generated_at": result["generated_at"],
                      "data_sha256": result["publication"]["data_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
