"""A fixed-issuer SEC access diagnostic, never a publication or an event check.

The issuer collector asks SEC only for a night's candidates, and a night with
no admitted plan and no known-event exclusion has none, so a red week can pass
without one request that would show whether SEC answers. This asks twice, for
the ticker mapping and for one fixed issuer's submissions, through the
collector's own transport: its User-Agent, its spacing, its deadline, its
refused redirects and its size bounds. The result carries no publication
binding, candidate, filing excerpt or order; it is printed to the job log and
retained outside docs/. The User-Agent is described, never copied: the
diagnostic names whether it carries a sender and an address, not the address.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from src import issuer_evidence

SCHEMA = "spicystock-sec-probe-v1"
#: A large, long-listed issuer whose ticker the mapping must name exactly once.
TICKER = "AAPL"
PUBLIC_ROOT = Path(__file__).resolve().parents[1] / "docs"
ADDRESS = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
LIMITS = ["not_a_candidate_or_event_check", "not_news_or_earnings_coverage", "never_publish_to_site"]


def user_agent_shape(value=None):
    value = issuer_evidence.USER_AGENT if value is None else value
    words = value.split()
    return {"names_sender": bool(words) and not ADDRESS.fullmatch(words[0]),
            "names_contact": any(ADDRESS.fullmatch(word) for word in words)}


def _request(transport, budget, phase, url):
    """One request through the collector's transport, its outcome and nothing of its body."""
    item = {"phase": phase, "url": url, "outcome": None, "http_status": None,
            "bytes": None, "sha256": None, "checked_at": None}
    try:
        received = transport.fetch(url, budget)
        body = received["body"]
        if not isinstance(body, bytes) or not body:
            raise issuer_evidence.SourceError("invalid_response")
        item.update(outcome="ok", bytes=len(body), sha256=issuer_evidence._sha(body),
                    checked_at=issuer_evidence._iso(received["observed_at"]))
        return item, body
    except issuer_evidence.SourceError as error:
        item.update(outcome=error.code, http_status=error.http_status)
    except (KeyError, TypeError, ValueError):
        item.update(outcome="invalid_response")
    return item, None


def probe(*, transport=None, budget=None, clock=None):
    clock = clock or (lambda: datetime.now(timezone.utc))
    started = clock()
    transport = transport or issuer_evidence._Transport(cache_dir=None)
    budget = budget or issuer_evidence._Budget()
    requests = []
    identity = {"status": "not_reached", "cik": None, "name": None, "reason": None}
    submissions = {"status": "not_reached", "filings_in_window": None, "history_files_advertised": None}
    mapping, body = _request(transport, budget, "mapping", issuer_evidence.MAPPING_URL)
    requests.append(mapping)
    if body is not None:
        try:
            found = issuer_evidence.parse_mapping(body, TICKER)
            identity.update(status="verified", cik=found["cik"], name=found["name"])
        except issuer_evidence.SourceError as error:
            identity.update(status="unverified", reason=error.code)
    if identity["status"] == "verified":
        url = f"https://data.sec.gov/submissions/CIK{identity['cik']:010d}.json"
        item, raw = _request(transport, budget, "submissions", url)
        requests.append(item)
        if raw is not None:
            try:
                parsed = issuer_evidence.parse_submissions(raw, identity["cik"], TICKER, item["checked_at"])
                submissions.update(status="parsed", filings_in_window=len(parsed["filings"]),
                                   history_files_advertised=len(parsed["history"]))
            except (issuer_evidence.SourceError, ValueError, KeyError, TypeError):
                submissions.update(status="invalid")
        else:
            submissions.update(status="unavailable")
    completed = clock()
    if completed < started:
        raise ValueError("diagnostic clock moved backwards")
    answered = (all(r["outcome"] == "ok" for r in requests) and identity["status"] == "verified"
                and submissions["status"] == "parsed")
    refused = sorted({r["http_status"] for r in requests if r["http_status"] is not None})
    return {
        "schema": SCHEMA, "purpose": "transport_diagnostic_only", "ticker": TICKER,
        "collection_started_at": started.isoformat(), "generated_at": completed.isoformat(),
        "user_agent": user_agent_shape(), "requests": requests, "request_count": budget.requests,
        "identity": identity, "submissions": submissions,
        "answered": answered, "refused_statuses": refused,
        "sentence": sentence(answered, requests),
        "limits": list(LIMITS),
    }


def sentence(answered, requests):
    if answered:
        return f"SEC answered all {len(requests)} requests from this runner."
    failed = next(r for r in requests if r["outcome"] != "ok") if any(r["outcome"] != "ok" for r in requests) else None
    if failed is None:
        return "SEC answered, and the answer did not establish the fixed issuer."
    status = f"HTTP {failed['http_status']}" if failed["http_status"] is not None else failed["outcome"]
    return f"SEC did not answer the {failed['phase']} request from this runner: {status}."


def write_probe(output: Path, result: dict):
    output = output.resolve()
    if output == PUBLIC_ROOT or PUBLIC_ROOT in output.parents:
        raise ValueError("diagnostics cannot be written into public docs")
    payload = json.dumps(result, allow_nan=False, indent=2) + "\n"
    if issuer_evidence.USER_AGENT in payload or ADDRESS.search(payload):
        raise ValueError("diagnostic would carry the contact address")
    # A diagnostic must not replace an existing observation or user file.
    with output.open("x", encoding="utf-8") as handle:
        handle.write(payload)
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        payload = write_probe(args.output, probe())
    except Exception:
        # Never log a raw exception: it can carry a request detail.
        print("SEC access diagnostic failed; no raw error was logged.")
        return 1
    # The job log is the record a reader without the artifact can read.
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
