"""Same-session source recovery: a publication's own named missing or stale stocks
asked for again, once, before the next session opens. Never a scan, never a ticket.

A publication names the stocks whose session bar it did not get (the stale
tail in ``run.input_tolerance.names``, every exception population in the
quality ledger's entry for that publication). This companion freezes the
publication's own basis -- its universe identity and snapshot digest, feed,
adjustment, session and rules identity -- and re-requests exactly those names
in one bounded batch, then records which of them now carry a bar for that
session. The original publication, its measurements, grades, plans and
tickets are never touched; original and recovered coverage are reported as
two separate readings and never added together; why a bar was absent is not
established by its arrival. The prior-session follow-up (src/followup.py) reads
the same stocks the NEXT evening from that run's own fetch; this is the other
reading, before that evening, from a request of its own.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from src import delivery, followup, input_diagnostics, market_data, morning, provenance, quality_ledger, sessions, universe

VERSION = 1
RECEIPT_FILE = "source-recovery.json"
MAX_RECEIPT_BYTES = 64 * 1024
#: one SDK bars batch per publication (P): the recovery is a re-request of a
#: named tail, never a second scan of the universe
MAX_BATCHES = 1
#: that batch plus download_bars' one retry after RETRY_WAIT_SECONDS (P)
MAX_BATCH_ATTEMPTS = 2
#: the names one batch carries, so a record's full stale list (STALE_NAMES_MAX)
#: always fits; a larger named deficit is refused whole, never a prefix
MAX_NAMES = MAX_BATCHES * market_data.DEFAULT_BATCH_SIZE
#: two attempts over three SDK pages of 100 names x 260 bars, each under the
#: connect and read timeouts, plus the retry wait, is 213 seconds (plumbing)
MAX_COLLECTION_SECONDS = 300
MAX_FUTURE_SKEW_SECONDS = morning.POLICY["max_future_skew_seconds"]
#: the evening guard's own rule, the one word the record archives for it
RECOVERY_UNTIL = delivery.RECOVERY_NEXT_OPEN
#: the coverage populations a later request could change: a frame the feed
#: did not return, dropped, never attempted, stale, gapped or unreadable.
#: ``price_excluded`` is a reading of a bar that arrived, ``refused`` never
#: sits on a published record, ``duplicate_repaired`` is a diagnostic
CATEGORIES = ("stale", "no_bars", "dropped", "unfetched_budget", "unfetched_failure", "gapped", "unreadable")
RULES = {
    "version": VERSION, "max_batches": MAX_BATCHES, "max_batch_attempts": MAX_BATCH_ATTEMPTS,
    "max_names": MAX_NAMES, "max_collection_seconds": MAX_COLLECTION_SECONDS,
    "max_future_skew_seconds": MAX_FUTURE_SKEW_SECONDS, "recovery_until": RECOVERY_UNTIL,
    "categories": list(CATEGORIES), "selection": "named_missing_or_stale_stocks_of_the_bound_publication",
    "benchmark_requested": False, "basis": "the publication's own feed, adjustment, session and lookback",
}
LIMITS = ["original_publication_immutable", "no_combined_coverage_figure", "not_a_fixed_cohort_improvement",
          "ready_names_not_refetched", "arrival_time_unknown", "wire_requests_by_arithmetic_only",
          "one_bounded_attempt_per_publication", "second_slot_may_spend_once_more_after_a_refused_persist",
          "rides_the_morning_collectors_success", "prior_session_followup_is_separate"]
COVERAGE = {"scan": "not_run", "grades": "unchanged", "plans": "unchanged", "tickets": "unchanged",
            "scorecard": "unchanged", "cause_of_absence": "not_established"}
STATUSES = ("recovered", "partial", "nothing_recovered", "provider_unavailable", "inapplicable")
REASONS = (None, "future_publication", "stale_publication", "recovery_window_ended", "basis_differs",
           "membership_mismatch", "no_coverage_deficit", "deficit_not_named", "deficit_over_budget", "already_attempted")
REASON_WORDS = {
    "future_publication": "the publication is dated after this check's clock",
    "stale_publication": "a later session has completed since the publication's",
    "recovery_window_ended": "the next session opened before this check ran",
    "basis_differs": "the publication's own input basis cannot be frozen",
    "membership_mismatch": "a named population does not match the publication's own count and identity",
    "no_coverage_deficit": "every intended stock's session bar arrived",
    "deficit_not_named": "the publication records a coverage deficit but names none of its stocks",
    "deficit_over_budget": "the named deficit exceeds the one-batch request budget",
    "already_attempted": "this publication's one bounded recovery was already made",
}
OUTCOMES = ("recovered", "arrived_not_ready", "still_stale", "still_missing", "not_returned")
ARRIVED = ("recovered", "arrived_not_ready")
READY_FAULTS = (None, "gapped", "unreadable")
SOURCE_STATUSES = ("not_requested", "ok", "unavailable")
ENVELOPE_KEYS = {"schema_version", "collection_started_at", "generated_at", "observation_run_id",
                 "previous_observation_sha256", "dry_run", "publication", "frozen", "window", "original",
                 "deficits", "policy", "status", "reason", "requested", "source", "rows", "recovered",
                 "coverage", "limits", "sentence"}
FROZEN_KEYS = {"session", "expected_session", "feed", "adjustment", "timeframe", "lookback_days", "stale_names_max",
               "universe_identity", "universe_snapshot_sha256", "universe_size", "intended_identity",
               "coverage_sha256", "rules_version"}
ROW_KEYS = {"ticker", "category", "original_ending", "outcome", "ending", "ready_fault", "volume", "flat"}
SOURCE_KEYS = {"provider", "feed", "adjustment", "timeframe", "status", "error_kind", "checked_at",
               "batch_attempts", "symbols_requested", "window"}
TALLY_KEYS = ("requested", "arrived", "session_ready", "arrived_not_ready", "still_stale", "still_missing",
              "not_returned", "zero_volume", "flat")
COHORT_FIELDS = ("universe_identity", "universe_snapshot_sha256", "feed", "adjustment", "session", "rules_version")
HEX = re.compile(r"[0-9a-f]{64}\Z")
TIMEFRAME = "1Day"


def _require(condition, message):
    if not condition:
        raise ValueError("source recovery: " + message)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _benchmark(run):
    tol = run.get("input_tolerance")
    if isinstance(tol, dict) and isinstance(tol.get("benchmark"), str):
        return tol["benchmark"]
    from src import pipeline
    return pipeline.BENCHMARK_SYMBOL


# ------------------------------------------------------------------ frozen ----

def frozen_basis(data, binding):
    """The publication's own input basis, copied off the record field by field
    so the request and the receipt can be held to it."""
    run = data["run"]
    basis = run.get("input_basis") if isinstance(run.get("input_basis"), dict) else {}
    uni = run.get("universe") if isinstance(run.get("universe"), dict) else {}
    cov = run.get("coverage") if isinstance(run.get("coverage"), dict) else {}
    rules = (data.get("rules") or {}).get("pipeline") if isinstance(data.get("rules"), dict) else {}
    rules = rules if isinstance(rules, dict) else {}
    return {"session": run.get("session"), "expected_session": run.get("expected_session"), "feed": run.get("feed"),
            "adjustment": basis.get("adjustment"), "timeframe": basis.get("timeframe"),
            "lookback_days": rules.get("lookback_days"), "stale_names_max": rules.get("stale_names_max"),
            "universe_identity": uni.get("identity"), "universe_snapshot_sha256": uni.get("snapshot_sha256"),
            "universe_size": uni.get("size"), "intended_identity": cov.get("intended_identity"),
            "coverage_sha256": provenance.digest(cov) if cov else None, "rules_version": binding["rules_version"]}


def basis_ok(frozen, data):
    """Whether the frozen basis is one a request can be made under."""
    from alpaca.data.enums import DataFeed
    run = data["run"]
    basis = run.get("input_basis") if isinstance(run.get("input_basis"), dict) else {}
    try:
        session = date.fromisoformat(frozen["session"])
        sessions.require_session(session)
        DataFeed(frozen["feed"])
    except (TypeError, ValueError):
        return False
    return (frozen["feed"] == basis.get("feed") and frozen["adjustment"] == market_data.BAR_ADJUSTMENT.value
            and frozen["timeframe"] == TIMEFRAME and type(frozen["lookback_days"]) is int and frozen["lookback_days"] > 0
            and isinstance(frozen["universe_identity"], str) and isinstance(frozen["intended_identity"], str)
            and frozen["coverage_sha256"] is not None)


def window_of(frozen, started):
    """The next session and its open: the instant the evening guard stops
    publishing the measured session, and so the instant this recovery stops."""
    try:
        session = date.fromisoformat(frozen["session"])
        following = sessions.next_sessions(session, 1)[0]
        opens = sessions.hours(following)[0]
    except (TypeError, ValueError):
        return {"next_session": None, "next_open_at": None, "before_next_open": None}
    return {"next_session": following.isoformat(), "next_open_at": opens.isoformat(), "before_next_open": started < opens}


def original_facts(run):
    """The publication's own coverage facts, copied and never recomputed; its
    run status beside them, labelled as what this recovery does not read."""
    cov = run.get("coverage") if isinstance(run.get("coverage"), dict) else {}
    acc = cov.get("acceptance") if isinstance(cov.get("acceptance"), dict) else {}
    tol = run.get("input_tolerance") if isinstance(run.get("input_tolerance"), dict) else {}
    problems = run.get("problems") if isinstance(run.get("problems"), list) else []
    kinds = sorted({p.get("kind") if isinstance(p, dict) else p for p in problems if isinstance(p, (dict, str))}, key=str)
    return {"acceptance_status": acc.get("status"), "intended_stocks": acc.get("intended_stocks"),
            "ready_stocks": acc.get("ready_stocks"), "fraction": acc.get("fraction"),
            "complete_intended": acc.get("complete_intended"), "capacity_excluded": acc.get("capacity_excluded"),
            "stale": cov.get("stale"), "stale_stocks": tol.get("stale_stocks"), "tolerance_verdict": tol.get("verdict"),
            "tolerance_reasons": deepcopy(tol.get("reasons")), "gaps": {c: cov.get(c) for c in CATEGORIES},
            "run_status": run.get("status"), "problem_kinds": kinds, "gate_read_run_status": False}


# ---------------------------------------------------------------- deficits ----

def ledger_entry(ledger_raw, data_sha256):
    """The quality ledger's entry for THIS publication, or None; another
    publication's entry, or a malformed one, is refused rather than read."""
    if ledger_raw is None:
        return None
    _require(isinstance(ledger_raw, bytes) and 0 < len(ledger_raw) <= quality_ledger.MAX_ENTRY_BYTES,
             "ledger entry exceeds size bound")
    try:
        entry = json.loads(gzip.decompress(ledger_raw).decode("utf-8"))
    except (OSError, EOFError, ValueError, UnicodeDecodeError):
        raise ValueError("source recovery: ledger entry is unreadable") from None
    _require(isinstance(entry, dict) and entry.get("schema_version") == quality_ledger.VERSION, "ledger entry is unsupported")
    publication = entry.get("publication")
    _require(isinstance(publication, dict) and publication.get("sha256") == data_sha256, "ledger entry is another publication's")
    return entry


def _ledger_names(entry, category):
    """The ledger's full membership for a category, or None when it holds none."""
    if entry is None:
        return None
    membership = (entry.get("input") or {}).get("exception_membership")
    if not isinstance(membership, dict) or not isinstance(membership.get(category), list):
        return None
    names = membership[category]
    return names if all(isinstance(n, str) for n in names) else None


def deficits(run, benchmark, entry, ledger_raw):
    """Where the publication's own session bars were missing, named where the
    publication or its ledger entry names them, each population held to the
    publication's own count and identity; a name never guessed."""
    cov = run.get("coverage") if isinstance(run.get("coverage"), dict) else {}
    reasons = cov.get("reasons") if isinstance(cov.get("reasons"), dict) else {}
    out, mismatch, used = {}, False, False
    stale_reason, stale_stocks, endings = followup._membership(run, benchmark)
    for category in CATEGORIES:
        pop = reasons.get(category) if isinstance(reasons.get(category), dict) else {}
        count = pop.get("count") if type(pop.get("count")) is int and pop.get("count") >= 0 else None
        block = {"count": count, "identity": pop.get("identity"), "named": False, "source": None, "names": None,
                 "benchmark_in_population": None}
        if count is None:
            mismatch = True
        elif count == 0:
            block.update(named=True, names=[], benchmark_in_population=False)
        else:
            names = None
            if category == "stale" and stale_reason in (None, "none_missing"):
                names, source = stale_stocks, "record"
                block["benchmark_in_population"] = len(stale_stocks) < count
            elif category == "stale" and stale_reason == "membership_mismatch":
                mismatch = True
            if names is None and not mismatch:
                ledger = _ledger_names(entry, category)
                if ledger is not None:
                    if universe.population(ledger) != pop:
                        mismatch = True
                    else:
                        names, source, used = sorted(set(ledger) - {benchmark}), "ledger", True
                        block["benchmark_in_population"] = benchmark in ledger
            if names is not None and not mismatch:
                block.update(named=True, source=source, names=list(names))
        out[category] = block
    named = sorted({n for b in out.values() if b["names"] for n in b["names"]})
    unnamed = sum(b["count"] for b in out.values() if b["count"] and not b["named"])
    ledger = None
    if ledger_raw is not None:
        ledger = {"path": f"{quality_ledger.DIRECTORY}/{entry['publication']['sha256']}.json.gz",
                  "sha256": _sha(ledger_raw), "used": used}
    return {"categories": out, "named_stocks": len(named), "unnamed_frames": unnamed, "mismatch": mismatch,
            "stale_endings": {t: (d.isoformat() if d is not None else None) for t, d in endings.items()},
            "ledger": ledger}


def _requested(defs):
    return sorted({n for b in defs["categories"].values() if b["names"] for n in b["names"]})


def _category_of(defs, ticker):
    for category in CATEGORIES:
        names = defs["categories"][category]["names"]
        if names and ticker in names:
            return category
    return None


# ------------------------------------------------------------------ reason ----

def _previous(previous_raw):
    if previous_raw is None:
        return None
    _require(isinstance(previous_raw, bytes) and 0 < len(previous_raw) <= MAX_RECEIPT_BYTES, "prior receipt exceeds size bound")
    previous = morning._json(previous_raw)
    _require(isinstance(previous, dict) and previous.get("schema_version") == VERSION, "prior receipt is unsupported")
    return previous


def attempted(previous, data_sha256):
    """Whether a prior receipt spent this publication's one bounded request."""
    if not isinstance(previous, dict):
        return False
    binding = previous.get("publication")
    source = previous.get("source")
    return (isinstance(binding, dict) and binding.get("data_sha256") == data_sha256 and isinstance(source, dict)
            and type(source.get("batch_attempts")) is int and source["batch_attempts"] >= 1)


def _reason(data, binding, frozen, window, started, defs, previous):
    run = data["run"]
    if morning._instant(run["published_at"]) > started + timedelta(seconds=MAX_FUTURE_SKEW_SECONDS):
        return "future_publication"
    if run["session"] != sessions.completed_session(started).isoformat():
        return "stale_publication"
    if window["next_open_at"] is None or not window["before_next_open"]:
        return "recovery_window_ended"
    if not basis_ok(frozen, data):
        return "basis_differs"
    if defs["mismatch"]:
        return "membership_mismatch"
    if not any(b["count"] for b in defs["categories"].values()):
        return "no_coverage_deficit"
    if defs["named_stocks"] == 0:
        return "deficit_not_named"
    if defs["named_stocks"] > MAX_NAMES:
        return "deficit_over_budget"
    if attempted(previous, binding["data_sha256"]):
        return "already_attempted"
    return None


# ------------------------------------------------------------------- fetch ----

def _source(frozen):
    return {"provider": "Alpaca", "feed": frozen["feed"], "adjustment": frozen["adjustment"],
            "timeframe": frozen["timeframe"], "status": "not_requested", "error_kind": None, "checked_at": None,
            "batch_attempts": 0, "symbols_requested": 0, "window": None}


def _window(requested, frozen, stats, started):
    session = date.fromisoformat(frozen["session"])
    basis = input_diagnostics.request_basis(requested, stats, session, started, frozen["lookback_days"], MAX_NAMES, None)
    return basis["window"]


def _error_kind(exc):
    """The scan transport's own refusal classes first (it wraps the provider's
    status in a sentence), then the morning transport's status reading."""
    if isinstance(exc, market_data.CredentialsRejectedError):
        return "authentication"
    if isinstance(exc, market_data.FeedNotAuthorizedError):
        return "entitlement"
    return morning._error(exc)


def _fetch(client, requested, frozen, started, clock):
    """One bounded batch through the scan's own transport; what came back, the
    counts behind it and the failure kind, never the failure's text."""
    from alpaca.data.enums import DataFeed
    feed = DataFeed(frozen["feed"])
    session = date.fromisoformat(frozen["session"])
    frames, stats, error_kind = {}, None, None
    try:
        frames, stats = market_data.download_bars(client, requested, session, lookback_days=frozen["lookback_days"],
                                                  feed=feed, batch_size=MAX_NAMES, now=started)
    except Exception as exc:  # noqa: BLE001 -- classified, never quoted
        stats = getattr(exc, "download_stats", None)
        frames = getattr(exc, "frames", None) or {}
        error_kind = _error_kind(exc)
    if stats is None:
        stats = market_data.DownloadStats(session=session, feed=feed.value)
        stats.batch_attempts = 1
    if error_kind is None and (stats.dropped_symbols or stats.refused or stats.unrequested):
        error_kind = "provider_error"
    ready = market_data.apply_session_rules(dict(frames), session, stats) if frames else {}
    return frames, ready, stats, error_kind, clock()


def _rows(requested, defs, frames, ready, stats, available, session):
    rows = []
    for ticker in requested:
        category = _category_of(defs, ticker)
        row = {"ticker": ticker, "category": category, "original_ending": defs["stale_endings"].get(ticker),
               "outcome": None, "ending": None, "ready_fault": None, "volume": None, "flat": None}
        if not available:
            row["outcome"] = "not_returned"
        elif ticker in ready:
            row.update(outcome="recovered", ending=session.isoformat())
            row["volume"], row["flat"] = followup._bar_facts(ready[ticker])
        elif ticker in frames:
            last = market_data.last_bar_date(frames[ticker])
            if last == session:
                fault = "gapped" if ticker in stats.gapped else "unreadable"
                row.update(outcome="arrived_not_ready", ending=session.isoformat(), ready_fault=fault)
                row["volume"], row["flat"] = followup._bar_facts(frames[ticker])
            else:
                row.update(outcome="still_stale", ending=last.isoformat() if last is not None else None)
        else:
            row["outcome"] = "still_missing"
        rows.append(row)
    return rows


def tallies(rows):
    arrived = [r for r in rows if r["outcome"] in ARRIVED]
    return {"requested": len(rows), "arrived": len(arrived),
            "session_ready": sum(1 for r in rows if r["outcome"] == "recovered"),
            "arrived_not_ready": sum(1 for r in rows if r["outcome"] == "arrived_not_ready"),
            "still_stale": sum(1 for r in rows if r["outcome"] == "still_stale"),
            "still_missing": sum(1 for r in rows if r["outcome"] == "still_missing"),
            "not_returned": sum(1 for r in rows if r["outcome"] == "not_returned"),
            "zero_volume": sum(1 for r in arrived if r["volume"] == 0),
            "flat": sum(1 for r in arrived if r["flat"] is True)}


def _status(rows, source, reason):
    if reason:
        return "inapplicable"
    if source["status"] == "unavailable":
        return "provider_unavailable"
    ready = sum(1 for r in rows if r["outcome"] == "recovered")
    return "recovered" if ready == len(rows) else "nothing_recovered" if ready == 0 else "partial"


# ---------------------------------------------------------------- sentence ----

def _when(iso):
    at = sessions.market_time(morning._instant(iso))
    return at.strftime("%I:%M %p").lstrip("0") + " ET on " + at.strftime("%a") + " " + str(at.day) + at.strftime(" %b")


def _n(count, one, many):
    return f"{count} {one if count == 1 else many}"


def _verb(count, one, many):
    return one if count == 1 else many


def _names(rows, outcome, limit=3):
    names = [r["ticker"] for r in rows if r["outcome"] == outcome]
    if not names:
        return ""
    shown = ", ".join(names[:limit]) + (f" and {len(names) - limit} more" if len(names) > limit else "")
    return f" ({shown})"


def sentence_of(out):
    """Facts only: what was asked for, when, what came back; no verdict."""
    session, started = out["frozen"]["session"], out["collection_started_at"]
    if out["reason"]:
        return (f"No source recovery for the {session} publication at {_when(started)}: "
                f"{REASON_WORDS[out['reason']]}; nothing was fetched.")
    rows, t, original = out["rows"], out["recovered"], out["original"]
    source = out["source"]
    opened = "before" if out["window"]["before_next_open"] else "after"
    head = (f"Source recovery for the {session} publication: its {_n(t['requested'], 'stock', 'stocks')} without a "
            f"usable {session} bar, named in full, {'was' if t['requested'] == 1 else 'were'} asked for again at "
            f"{_when(started)}, {opened} the {out['window']['next_session']} open, in "
            f"{_n(source['batch_attempts'], 'request', 'requests')}")
    if source["status"] == "unavailable":
        cause = "no credentials were present" if source["error_kind"] == "missing_credentials" else f"the provider request failed ({source['error_kind']})"
        body = f"; nothing was returned: {cause}"
    else:
        parts = [f"{t['session_ready']} now {_verb(t['session_ready'], 'carries', 'carry')} a {session} bar that passes the session rules"
                 + (f" ({t['zero_volume']} with zero volume)" if t["zero_volume"] else "")]
        if t["arrived_not_ready"]:
            parts.append(f"{t['arrived_not_ready']} {_verb(t['arrived_not_ready'], 'carries', 'carry')} it but not the session before{_names(rows, 'arrived_not_ready')}")
        if t["still_stale"]:
            parts.append(f"{t['still_stale']} still {_verb(t['still_stale'], 'ends', 'end')} before it{_names(rows, 'still_stale')}")
        if t["still_missing"]:
            parts.append(f"{t['still_missing']} returned nothing{_names(rows, 'still_missing')}")
        body = "; " + "; ".join(parts)
    tail = (f". The publication stays {original['ready_stocks']} of {original['intended_stocks']} intended stocks ready; "
            "its measurements, grades, plans and tickets are unchanged, and why a bar was absent is not established.")
    return head + body + tail


# ----------------------------------------------------------------- collect ----

def collect(canonical_raw, ledger_raw=None, *, client=None, clock=None, dry_run=False, observation_run_id=None,
            previous_raw=None):
    """One bounded recovery; an injectable clock and provider make it a pure function."""
    clock = clock or (lambda: datetime.now(timezone.utc))
    started = clock()
    _require(morning._instant(started) is not None, "collection requires an aware clock")
    data, binding = morning._publication(canonical_raw, allow_fixture=dry_run)
    run = data["run"]
    entry = ledger_entry(ledger_raw, binding["data_sha256"])
    frozen = frozen_basis(data, binding)
    window = window_of(frozen, started)
    original = original_facts(run)
    defs = deficits(run, _benchmark(run), entry, ledger_raw)
    previous = _previous(previous_raw)
    reason = _reason(data, binding, frozen, window, started, defs, previous)
    requested = [] if reason else _requested(defs)
    source, rows = _source(frozen), []
    if requested:
        session = date.fromisoformat(frozen["session"])
        if client is None and any(not os.environ.get(k, "").strip() for k in market_data.REQUIRED_ENV):
            source.update(status="unavailable", error_kind="missing_credentials", checked_at=clock().isoformat(),
                          symbols_requested=len(requested))
            rows = _rows(requested, defs, {}, {}, None, False, session)
        else:
            client = client or market_data.get_clients()
            frames, ready, stats, error_kind, checked = _fetch(client, requested, frozen, started, clock)
            source.update(status="ok" if error_kind is None else "unavailable", error_kind=error_kind,
                          checked_at=checked.isoformat(), batch_attempts=stats.batch_attempts,
                          symbols_requested=len(requested), window=_window(requested, frozen, stats, started))
            rows = _rows(requested, defs, frames, ready, stats, error_kind is None, session)
    completed = clock()
    _require(morning._instant(completed) is not None and completed >= started, "collection clock moved backwards")
    public = {k: v for k, v in defs.items() if k not in ("mismatch", "stale_endings")}
    out = {"schema_version": VERSION, "collection_started_at": started.isoformat(), "generated_at": completed.isoformat(),
           "observation_run_id": str(observation_run_id or os.environ.get("GITHUB_RUN_ID") or "local"),
           "previous_observation_sha256": _sha(previous_raw) if previous_raw is not None else None,
           "dry_run": bool(dry_run), "publication": binding, "frozen": frozen, "window": window, "original": original,
           "deficits": public, "policy": deepcopy(RULES), "status": _status(rows, source, reason), "reason": reason,
           "requested": requested, "source": source, "rows": rows, "recovered": tallies(rows),
           "coverage": dict(COVERAGE), "limits": list(LIMITS), "sentence": None}
    out["sentence"] = sentence_of(out)
    validate_receipt(out, canonical_raw, ledger_raw, previous_raw=previous_raw, require_continuity=True)
    return out


# ---------------------------------------------------------------- validate ----

def validate_receipt(out, canonical_raw, ledger_raw=None, *, previous_raw=None, require_continuity=False):
    """Strict offline gate: every field is re-derived from the bound inputs."""
    try:
        _validate(out, canonical_raw, ledger_raw, previous_raw, require_continuity)
    except (KeyError, TypeError, AttributeError, IndexError, OverflowError):
        raise ValueError("source recovery: malformed receipt structure") from None


def _validate(out, canonical_raw, ledger_raw, previous_raw, require_continuity):
    _require(isinstance(out, dict) and type(out.get("schema_version")) is int and out["schema_version"] == VERSION
             and type(out.get("dry_run")) is bool, "unsupported receipt envelope")
    _require(set(out) == ENVELOPE_KEYS, "receipt envelope fields differ")
    previous_sha = out["previous_observation_sha256"]
    _require(previous_sha is None or isinstance(previous_sha, str) and HEX.fullmatch(previous_sha), "invalid prior receipt binding")
    data, binding = morning._publication(canonical_raw, allow_fixture=out["dry_run"])
    run = data["run"]
    _require(out["publication"] == binding and set(out["publication"]) == set(binding), "publication binding differs")
    frozen = frozen_basis(data, binding)
    _require(out["frozen"] == frozen and set(out["frozen"]) == FROZEN_KEYS, "frozen basis differs")
    started, generated = (morning._instant(out[k]) for k in ("collection_started_at", "generated_at"))
    _require(started is not None and generated is not None and started <= generated, "invalid collection time ordering")
    _require((generated - started).total_seconds() <= MAX_COLLECTION_SECONDS, "collection exceeded duration bound")
    window = window_of(frozen, started)
    _require(out["window"] == window, "recovery window differs")
    archived = run.get("delivery")
    if isinstance(archived, dict) and isinstance(archived.get("next_session"), str) and window["next_session"] is not None:
        _require(archived["next_session"] == window["next_session"], "recovery window disagrees with the archived delivery block")
    _require(out["original"] == original_facts(run), "original coverage facts differ")
    entry = ledger_entry(ledger_raw, binding["data_sha256"])
    defs = deficits(run, _benchmark(run), entry, ledger_raw)
    public = {k: v for k, v in defs.items() if k not in ("mismatch", "stale_endings")}
    _require(out["deficits"] == public, "deficit accounting differs")
    _require(provenance.digest(out["policy"]) == provenance.digest(RULES) and out["limits"] == LIMITS
             and out["coverage"] == COVERAGE, "recovery policy differs")
    _require(morning._text(out["observation_run_id"], 128) is not None, "invalid observation run identity")
    previous = _previous(previous_raw) if previous_raw is not None else None
    _require(out["reason"] in REASONS and out["reason"] == _reason(data, binding, frozen, window, started, defs, previous),
             "recovery reason differs")
    _require(out["status"] in STATUSES, "unknown recovery status")
    requested = [] if out["reason"] else _requested(defs)
    _require(out["requested"] == requested, "requested names differ")
    _require(len(requested) <= MAX_NAMES, "request budget exceeded")
    source, reference = out["source"], _source(frozen)
    _require(isinstance(source, dict) and set(source) == SOURCE_KEYS, "invalid source metadata")
    for key in ("provider", "feed", "adjustment", "timeframe"):
        _require(source[key] == reference[key], "source basis differs")
    _require(source["status"] in SOURCE_STATUSES and source["error_kind"] in morning.SOURCE_ERRORS, "unknown source state")
    _require(type(source["batch_attempts"]) is int and 0 <= source["batch_attempts"] <= MAX_BATCH_ATTEMPTS, "batch attempts exceed budget")
    rows = out["rows"]
    _require(isinstance(rows, list) and [r["ticker"] for r in rows] == requested, "row membership differs")
    if not requested:
        _require(source == reference and rows == [], "an inapplicable recovery requested a provider")
    else:
        _require(source["status"] != "not_requested" and source["symbols_requested"] == len(requested), "request not recorded")
        checked = morning._instant(source["checked_at"])
        _require(checked is not None and started <= checked <= generated, "invalid provider check time")
        _require((source["error_kind"] is None) == (source["status"] == "ok"), "provider status contradicts error")
        if source["error_kind"] == "missing_credentials":
            _require(source["batch_attempts"] == 0 and source["window"] is None, "credentials absent yet a request counted")
        else:
            _require(source["batch_attempts"] >= 1, "a request without an attempt")
            stats = market_data.DownloadStats(session=date.fromisoformat(frozen["session"]), feed=frozen["feed"])
            stats.batch_attempts = source["batch_attempts"]
            _require(source["window"] == _window(requested, frozen, stats, started), "request window differs")
    session = frozen["session"]
    for row in rows:
        _require(isinstance(row, dict) and set(row) == ROW_KEYS, "row fields differ")
        _require(row["category"] == _category_of(defs, row["ticker"]), "row category differs")
        _require(row["original_ending"] == defs["stale_endings"].get(row["ticker"]), "row original ending differs")
        _require(row["outcome"] in OUTCOMES and row["ready_fault"] in READY_FAULTS, "unknown row outcome")
        _require((row["outcome"] == "not_returned") == (source["status"] == "unavailable"), "row outcome contradicts the source")
        if row["outcome"] in ARRIVED:
            _require(row["ending"] == session, "an arrived row does not end on the session")
            _require((row["ready_fault"] is not None) == (row["outcome"] == "arrived_not_ready"), "ready fault contradicts the outcome")
            _require(row["volume"] is None or (type(row["volume"]) is int and row["volume"] >= 0), "invalid volume")
            _require(row["flat"] in (None, True, False), "invalid flat flag")
        else:
            _require(row["ready_fault"] is None and row["volume"] is None and row["flat"] is None, "facts on a bar that did not arrive")
            if row["outcome"] == "still_stale":
                _require(row["ending"] is None or (isinstance(row["ending"], str) and row["ending"] < session), "a still-stale row ends on or after the session")
            else:
                _require(row["ending"] is None, "a missing row carries an ending")
    _require(out["recovered"] == tallies(rows), "recovered tallies differ")
    _require(out["status"] == _status(rows, source, out["reason"]), "recovery status contradicts its rows")
    _require(out["sentence"] == sentence_of(out), "recovery sentence differs")
    if require_continuity or previous_raw is not None:
        _require(previous_sha == (_sha(previous_raw) if previous_raw is not None else None), "prior receipt bytes differ")
    encoded = json.dumps(out, allow_nan=False, separators=(",", ":")).encode()
    _require(len(encoded) <= MAX_RECEIPT_BYTES, "receipt exceeds size bound")


def same_cohort(frozen_a, frozen_b):
    """Raise, naming the first basis field that differs, when two frozen bases
    are not one cohort; the 8 October pair differs in its universe identity."""
    for field in COHORT_FIELDS:
        if frozen_a.get(field) != frozen_b.get(field):
            raise ValueError(f"source recovery: not one cohort: {field} differs")
    return True


# --------------------------------------------------------------------- run ----

def read_ledger(docs, data_sha256):
    """The quality ledger's entry for this publication beside the record, or None."""
    _require(isinstance(data_sha256, str) and HEX.fullmatch(data_sha256), "invalid publication identity")
    path = Path(docs) / quality_ledger.DIRECTORY / f"{data_sha256}.json.gz"
    _require(not path.is_symlink(), "ledger entry must not be a symlink")
    if not path.exists():
        return None
    _require(path.stat().st_size <= quality_ledger.MAX_ENTRY_BYTES, "ledger entry exceeds size bound")
    return path.read_bytes()


def run(*, docs=Path("docs"), output=None, dry_run=False, client=None, clock=None):
    docs = Path(docs)
    output = Path(output) if output is not None else docs / RECEIPT_FILE
    _require(output.resolve() == (docs / RECEIPT_FILE).resolve()
             or not output.resolve().is_relative_to(docs.resolve()), "output must not overwrite publication files")
    raw = (docs / "data.json").read_bytes()
    ledger_raw = read_ledger(docs, _sha(raw))
    previous_path = docs / RECEIPT_FILE
    previous_raw = previous_path.read_bytes() if previous_path.exists() else None
    receipt = collect(raw, ledger_raw, client=client, clock=clock, dry_run=dry_run, previous_raw=previous_raw)
    _require((docs / "data.json").read_bytes() == raw, "publication changed during collection")
    _require(read_ledger(docs, _sha(raw)) == ledger_raw, "ledger entry changed during collection")
    _require((previous_path.read_bytes() if previous_path.exists() else None) == previous_raw,
             "previous receipt changed during collection")
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(receipt, allow_nan=False, indent=2).encode() + b"\n"
    with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".source-recovery-", delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            os.replace(temporary, output)
        finally:
            temporary.unlink(missing_ok=True)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--docs", type=Path, default=Path("docs"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = run(docs=args.docs, output=args.output, dry_run=args.dry_run)
    except Exception:
        print("Source recovery refused: invalid publication, ledger entry or collection; no receipt replaced.")
        return 1
    print(json.dumps({"status": result["status"], "reason": result["reason"], "requested": len(result["requested"]),
                      "arrived": result["recovered"]["arrived"], "session_ready": result["recovered"]["session_ready"],
                      "batch_attempts": result["source"]["batch_attempts"], "generated_at": result["generated_at"],
                      "data_sha256": result["publication"]["data_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
