"""A fixed-issuer SEC access diagnostic, never a publication or an event check.

The issuer collector asks SEC only for a night's candidates, and a night with
no admitted plan and no known-event exclusion has none, so a red week can pass
without one request that would show whether SEC answers. This asks for the
ticker mapping and for each fixed issuer's submissions, through the
collector's own transport: its User-Agent, its spacing, its deadline, its
refused redirects and its size bounds. The result carries no publication
binding, candidate, filing excerpt or order; it is printed to the job log and
retained outside docs/. The User-Agent is described, never copied: the
diagnostic names whether it carries a sender and an address, not the address.

For each issuer it also says which rows of SEC's recent index the collector's
row rules refused and by which rule (``rejected_rows``), with the refused
field's value -- a form name, a document name, a date -- spelled only in the
characters such a field carries. A refused row makes a collection ``partial``
(``metadata_invalid``), so this is how a reader without the raw index can see
whether the rule or the index is at fault.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re

from src import issuer_evidence

SCHEMA = "spicystock-sec-probe-v2"
#: AAPL: a large, long-listed domestic filer. ZIM: a foreign private issuer,
#: the first issuer whose collection reached SEC (24 October 2026) and read
#: partial on refused index rows. The mapping must name each exactly once.
TICKERS = ("AAPL", "ZIM")
#: A dispatch may name other issuers instead (``--tickers``): at most this many,
#: each an exchange ticker in SEC's spelling.
MAX_TICKERS = 4
TICKER = re.compile(r"[A-Z]{1,5}(?:[.-][A-Z]{1,2})?\Z")
#: The rejected rows printed per issuer; every one is counted whatever this is.
MAX_REJECTED_ROWS = 24
#: A refused field's value is printed at most this long, in these characters.
MAX_VALUE_CHARS = 96
SAFE_VALUE = re.compile(r"[^A-Za-z0-9 _.:/+\-]")
PUBLIC_ROOT = Path(__file__).resolve().parents[1] / "docs"
ADDRESS = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
LIMITS = ["not_a_candidate_or_event_check", "not_news_or_earnings_coverage", "never_publish_to_site"]
#: The collector's row rules in the order ``issuer_evidence._parse_rows`` asks them.
ROW_RULES = ("accepted_at", "accession", "form", "primary_document", "items", "filing_date",
             "report_date", "future_acceptance", "future_filing_date")


def user_agent_shape(value=None):
    value = issuer_evidence.USER_AGENT if value is None else value
    words = value.split()
    return {"names_sender": bool(words) and not ADDRESS.fullmatch(words[0]),
            "names_contact": any(ADDRESS.fullmatch(word) for word in words)}


def shown(value):
    """A refused field's value in printable characters only, and bounded."""
    if value is None:
        return "<null>"
    if not isinstance(value, str):
        return f"<{type(value).__name__}>"
    text = SAFE_VALUE.sub("?", value)
    return text if len(text) <= MAX_VALUE_CHARS else text[:MAX_VALUE_CHARS] + "..."


def row_problem(columns, i, as_of):
    """The first of the collector's row rules row ``i`` fails, and the value it failed on.

    Asked in ``_parse_rows``' own order through its own validators, so the
    count of problems found here is the collector's ``invalid_count``.
    """
    accepted = columns["acceptanceDateTime"][i]
    try:
        instant = issuer_evidence._instant(issuer_evidence._iso(accepted))
    except (ValueError, TypeError):
        return "accepted_at", accepted
    accession = columns["accessionNumber"][i]
    if not (isinstance(accession, str) and issuer_evidence.ACCESSION.fullmatch(accession)):
        return "accession", accession
    form = columns["form"][i]
    if not issuer_evidence._text(form, 32):
        return "form", form
    document = columns["primaryDocument"][i]
    if not (issuer_evidence._basename(document) or issuer_evidence._rendered(form, document)):
        return "primary_document", document
    items = columns["items"][i]
    if not issuer_evidence._text(items, 256, True):
        return "items", items
    filed = columns["filingDate"][i]
    try:
        filing_day = issuer_evidence._day(filed)
    except (ValueError, TypeError):
        return "filing_date", filed
    report = columns["reportDate"][i] or None
    if report is not None:
        try:
            issuer_evidence._day(report)
        except (ValueError, TypeError):
            return "report_date", report
    if instant > as_of + timedelta(seconds=issuer_evidence.MAX_FUTURE_SKEW_SECONDS):
        return "future_acceptance", accepted
    if filing_day > as_of.date():
        return "future_filing_date", filed
    return None


def rejected_rows(raw, as_of):
    """Every recent row the collector's rules refuse, counted by rule and by form."""
    columns = json.loads(raw)["filings"]["recent"]
    as_of = issuer_evidence._instant(as_of)
    by_rule, by_form, rows = {}, {}, []
    for i in range(len(columns["accessionNumber"])):
        problem = row_problem(columns, i, as_of)
        if problem is None:
            continue
        rule, value = problem
        form = shown(columns["form"][i])
        by_rule[rule] = by_rule.get(rule, 0) + 1
        by_form[form] = by_form.get(form, 0) + 1
        if len(rows) < MAX_REJECTED_ROWS:
            rows.append({"form": form, "rule": rule, "value": shown(value)})
    return {"count": sum(by_rule.values()), "by_rule": dict(sorted(by_rule.items())),
            "by_form": dict(sorted(by_form.items())), "rows": rows}


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


def _issuer(ticker, mapping_body, transport, budget, requests):
    identity = {"status": "not_reached", "cik": None, "name": None, "reason": None}
    submissions = {"status": "not_reached", "filings_in_window": None, "history_files_advertised": None,
                   "invalid_count": None, "rejected_rows": None}
    if mapping_body is not None:
        try:
            found = issuer_evidence.parse_mapping(mapping_body, ticker)
            identity.update(status="verified", cik=found["cik"], name=found["name"])
        except issuer_evidence.SourceError as error:
            identity.update(status="unverified", reason=error.code)
    if identity["status"] == "verified":
        url = f"https://data.sec.gov/submissions/CIK{identity['cik']:010d}.json"
        item, raw = _request(transport, budget, f"submissions:{ticker}", url)
        requests.append(item)
        if raw is not None:
            try:
                parsed = issuer_evidence.parse_submissions(raw, identity["cik"], ticker, item["checked_at"])
                rejected = rejected_rows(raw, item["checked_at"])
                submissions.update(status="parsed", filings_in_window=len(parsed["filings"]),
                                   history_files_advertised=len(parsed["history"]),
                                   invalid_count=parsed["invalid_count"], rejected_rows=rejected)
                if rejected["count"] != parsed["invalid_count"]:
                    # The rules here are the collector's, in its order; a
                    # disagreement means they drifted, and says so.
                    submissions["status"] = "classification_mismatch"
            except (issuer_evidence.SourceError, ValueError, KeyError, TypeError):
                submissions.update(status="invalid")
        else:
            submissions.update(status="unavailable")
    return {"ticker": ticker, "identity": identity, "submissions": submissions}


def probe(*, transport=None, budget=None, clock=None, tickers=TICKERS):
    clock = clock or (lambda: datetime.now(timezone.utc))
    started = clock()
    transport = transport or issuer_evidence._Transport(cache_dir=None)
    budget = budget or issuer_evidence._Budget()
    requests = []
    mapping, body = _request(transport, budget, "mapping", issuer_evidence.MAPPING_URL)
    requests.append(mapping)
    issuers = [_issuer(ticker, body, transport, budget, requests) for ticker in tickers]
    completed = clock()
    if completed < started:
        raise ValueError("diagnostic clock moved backwards")
    answered = (all(r["outcome"] == "ok" for r in requests)
                and all(i["identity"]["status"] == "verified" and i["submissions"]["status"] == "parsed"
                        for i in issuers))
    refused = sorted({r["http_status"] for r in requests if r["http_status"] is not None})
    return {
        "schema": SCHEMA, "purpose": "transport_diagnostic_only", "tickers": list(tickers),
        "collection_started_at": started.isoformat(), "generated_at": completed.isoformat(),
        "user_agent": user_agent_shape(), "requests": requests, "request_count": budget.requests,
        "issuers": issuers, "answered": answered, "refused_statuses": refused,
        "sentence": sentence(answered, requests, issuers),
        "limits": list(LIMITS),
    }


def sentence(answered, requests, issuers):
    if answered:
        return f"SEC answered all {len(requests)} requests from this runner."
    failed = next((r for r in requests if r["outcome"] != "ok"), None)
    if failed is None:
        named = ", ".join(i["ticker"] for i in issuers
                          if i["identity"]["status"] != "verified" or i["submissions"]["status"] != "parsed")
        return f"SEC answered, and the answer did not establish every fixed issuer ({named})."
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


def tickers_from(text):
    """The issuers a dispatch named, or the fixed ones when it named none; refused whole if any is malformed."""
    words = [w for w in re.split(r"[\s,]+", text or "") if w]
    if not words:
        return TICKERS
    if len(words) > MAX_TICKERS or len(set(words)) != len(words) \
            or not all(TICKER.fullmatch(w) for w in words):
        raise ValueError("tickers must be at most %d distinct exchange tickers" % MAX_TICKERS)
    return tuple(words)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--tickers", default="", help="issuers to ask for instead of AAPL and ZIM")
    args = parser.parse_args(argv)
    try:
        tickers = tickers_from(args.tickers)
    except ValueError as error:
        print(f"SEC access diagnostic refused: {error}.")
        return 2
    try:
        payload = write_probe(args.output, probe(tickers=tickers))
    except Exception:
        # Never log a raw exception: it can carry a request detail.
        print("SEC access diagnostic failed; no raw error was logged.")
        return 1
    # The job log is the record a reader without the artifact can read.
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
