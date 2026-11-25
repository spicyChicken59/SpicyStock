"""Capture one SEC Archives document's identity for a review of the event registry.

The registry (``knowledge/event-risk.json``) ends an entry only with a
resolution that carries the SHA-256 of captured bytes
(``event_risk.validate_registry()``), and a review made from a network that
cannot reach sec.gov has none to give: a search excerpt is not a source. A
runner reaches SEC. This fetches ONE document a dispatch names, through the
issuer collector's own transport (its User-Agent, spacing, deadline, refused
redirects and size bound), and prints what a reviewer needs to cite it:

* the URL as asked, the outcome, the HTTP status when SEC refused, the byte
  count, the SHA-256 of the bytes and the instant they were read;
* for each phrase asked for, how many times the document's own text carries it
  and bounded excerpts around the first occurrences, in the document's words
  (the text ``issuer_evidence.parse_primary()`` reads: tags dropped, whitespace
  collapsed, the declared encoding decoded strictly).

It decides nothing and resolves nothing: a person or an agent reads the
excerpts, and the registry edit is a reviewed change of its own with a dated
manifest. It carries no publication binding, candidate or order, writes
nothing under ``docs/``, never replaces a file, and never logs a raw exception
or the transport's contact address. With ``--save-bytes`` the exact bytes are
kept beside the result for the run's artifact, so the digest can be checked
again by anyone who downloads it.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from src import issuer_evidence

SCHEMA = "spicystock-sec-capture-v1"
PUBLIC_ROOT = Path(__file__).resolve().parents[1] / "docs"
#: Only a filing document: the mapping and the submissions files are the probe's.
ARCHIVES_PREFIX = "/Archives/edgar/data/"
#: The phrases one dispatch may ask for, and the shape of each.
MAX_PHRASES = 6
PHRASE = re.compile(r"[A-Za-z0-9$][A-Za-z0-9 $.,%'\-]{2,79}\Z")
#: The excerpts printed for one phrase; every occurrence is counted whatever this is.
MAX_EXCERPTS = 3
#: The characters of the document's text printed on each side of an occurrence.
EXCERPT_SIDE_CHARS = 240
ADDRESS = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
LIMITS = ["one_document_identity_only", "resolves_no_registry_entry", "not_news_or_event_clearance",
          "never_publish_to_site"]


def phrases_from(text):
    """The phrases a dispatch named, split on ``|``; refused whole if any is malformed."""
    words = [w.strip() for w in (text or "").split("|") if w.strip()]
    if len(words) > MAX_PHRASES or len(set(w.lower() for w in words)) != len(words) \
            or not all(PHRASE.fullmatch(w) for w in words):
        raise ValueError("phrases must be at most %d distinct phrases of 3 to 80 plain characters, "
                         "separated by |" % MAX_PHRASES)
    return tuple(words)


def archives_url(url):
    """``url`` when it is one the collector's transport fetches and names a filing document."""
    try:
        parsed = issuer_evidence._sec_url(url)
    except (ValueError, TypeError):
        raise ValueError("the URL is not an SEC document the collector's transport fetches") from None
    if parsed.hostname != "www.sec.gov" or not parsed.path.startswith(ARCHIVES_PREFIX):
        raise ValueError("the URL is not a document under www.sec.gov" + ARCHIVES_PREFIX)
    return url


def finds(text, phrases):
    """Each phrase's count in ``text`` (case ignored, occurrences not
    overlapping) and excerpts around its first occurrences. The positions are
    the text's own: a case-folded copy can be longer than the text (``ß``
    folds to ``ss``), so it is never sliced by a folded index."""
    out = []
    for phrase in phrases:
        spans = [m.span() for m in re.finditer(re.escape(phrase), text, re.IGNORECASE)]
        excerpts = [text[max(0, start - EXCERPT_SIDE_CHARS): end + EXCERPT_SIDE_CHARS]
                    for start, end in spans[:MAX_EXCERPTS]]
        out.append({"phrase": phrase, "count": len(spans), "excerpts": excerpts})
    return out


def capture(url, phrases=(), *, transport=None, budget=None, clock=None):
    """(result, bytes or None) for one document; a refusal is a result, never a raise."""
    clock = clock or (lambda: datetime.now(timezone.utc))
    started = clock()
    url = archives_url(url)
    transport = transport or issuer_evidence._Transport(cache_dir=None)
    budget = budget or issuer_evidence._Budget()
    request = {"url": url, "outcome": None, "http_status": None, "bytes": None, "sha256": None, "checked_at": None}
    body, document = None, {"status": "not_read", "normalized_characters": None, "finds": []}
    try:
        received = transport.fetch(url, budget)
        body = received["body"]
        if not isinstance(body, bytes) or not body:
            raise issuer_evidence.SourceError("invalid_response")
        request.update(outcome="ok", bytes=len(body), sha256=issuer_evidence._sha(body),
                       checked_at=issuer_evidence._iso(received["observed_at"]))
    except issuer_evidence.SourceError as error:
        body = None
        request.update(outcome=error.code, http_status=error.http_status)
    except (KeyError, TypeError, ValueError):
        body = None
        request.update(outcome="invalid_response")
    if body is not None:
        try:
            text = issuer_evidence.parse_primary(body, url)["text"]
            document.update(status="read", normalized_characters=len(text), finds=finds(text, phrases))
        except issuer_evidence.SourceError:
            # the bytes and their digest stand; only the text could not be read as the collector reads it
            document.update(status="text_unreadable")
    completed = clock()
    if completed < started:
        raise ValueError("capture clock moved backwards")
    return {
        "schema": SCHEMA, "purpose": "registry_review_source_capture",
        "collection_started_at": started.isoformat(), "generated_at": completed.isoformat(),
        "request_count": budget.requests, "request": request, "document": document,
        "sentence": sentence(request, document), "limits": list(LIMITS),
    }, body


def sentence(request, document):
    if request["outcome"] != "ok":
        status = f"HTTP {request['http_status']}" if request["http_status"] is not None else request["outcome"]
        return f"SEC did not give this document to this runner: {status}."
    found = sum(1 for f in document["finds"] if f["count"])
    text = ("its text could not be read as the collector reads a filing" if document["status"] != "read"
            else f"{found} of {len(document['finds'])} phrases asked for are in its text")
    return f"SEC answered: {request['bytes']} bytes, SHA-256 {request['sha256']}; {text}."


def _outside_docs(path: Path) -> Path:
    path = path.resolve()
    if path == PUBLIC_ROOT or PUBLIC_ROOT in path.parents:
        raise ValueError("a capture cannot be written into public docs")
    return path


def write_capture(output: Path, result: dict, *, body=None, save_bytes: Path | None = None):
    output = _outside_docs(output)
    payload = json.dumps(result, allow_nan=False, indent=2, ensure_ascii=True) + "\n"
    contact = ADDRESS.search(issuer_evidence.USER_AGENT)
    if issuer_evidence.USER_AGENT in payload or (contact and contact.group(0) in payload):
        raise ValueError("capture would carry the contact address")
    # never replace an existing file: a capture is evidence of one request
    if save_bytes is not None and body is not None:
        save_bytes = _outside_docs(save_bytes)
        save_bytes.parent.mkdir(parents=True, exist_ok=True)
        with save_bytes.open("xb") as handle:
            handle.write(body)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        handle.write(payload)
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="one https://www.sec.gov/Archives/edgar/data/... document")
    parser.add_argument("--find", default="", help="phrases to look for in the document's text, separated by |")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--save-bytes", type=Path, default=None, help="keep the exact bytes here, outside docs/")
    args = parser.parse_args(argv)
    try:
        url, phrases = archives_url(args.url.strip()), phrases_from(args.find)
    except ValueError as error:
        print(f"SEC document capture refused: {error}.")
        return 2
    try:
        result, body = capture(url, phrases)
        payload = write_capture(args.output, result, body=body, save_bytes=args.save_bytes)
    except Exception:
        # Never log a raw exception: it can carry a request detail.
        print("SEC document capture failed; no raw error was logged.")
        return 1
    # The job log is the record a reader without the artifact can read.
    print(payload, end="")
    return 0 if result["request"]["outcome"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
