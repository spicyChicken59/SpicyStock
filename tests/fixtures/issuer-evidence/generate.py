"""Generate issuer browser receipts through the real pipeline and collector.

The market and AAPL SEC responses are explicitly synthetic provider fixtures.
ZIM responses reuse separately manifested captured bytes. Missing captured
documents fail honestly instead of inventing contents for an otherwise real
filing. Run with --check to compare without rewriting committed fixtures.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src import issuer_evidence as issuer, provenance, reader  # noqa: E402
from tools import make_fixture  # noqa: E402

HERE = Path(__file__).resolve().parent
NOW = datetime(2026, 10, 10, 6, 20, tzinfo=timezone.utc)
VARIANTS = ("collected", "metadata-only", "identity-unverified", "outage", "inapplicable")
MAPPING_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
AAPL_SUBMISSIONS = "https://data.sec.gov/submissions/CIK0000320193.json"


def json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def publication():
    original = make_fixture.burst_frames

    def market():
        frames = original()
        frames["ZIM"] = frames.pop("COIL")
        return frames

    with tempfile.TemporaryDirectory(prefix="issuer-source-fixture-") as tmp, \
            mock.patch.object(make_fixture, "burst_frames", market), \
            mock.patch.dict(make_fixture.os.environ, {"GITHUB_RUN_ID_FOR_RECORD": "synthetic-issuer-evidence"}):
        docs = Path(tmp)
        data = make_fixture.run_variant("full", docs)
        # Follow the cash-preview fixture contract: retain the producer's
        # deterministic telemetry, but exercise normal publication binding.
        # Practice pages intentionally bypass the browser's publication hash.
        # These are declared offline controls, not observed production runs.
        data.pop("fixture")
        checked = provenance.verify(data, require_sources=False)
        assert checked["status"] == "PASS", checked
        # Preserve the producer's value order: the checklist includes rendered
        # value text whose order is independently replayed by provenance.
        return (json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()


def aapl_submissions():
    """Small synthetic SEC-shaped index, including one intentionally unread row."""
    filings = []
    for day, number in ((9, 9001), (8, 9002), (7, 9003), (6, 9004)):
        filings.append({
            "accessionNumber": f"0000320193-26-{number:06d}",
            "form": "8-K", "filingDate": f"2026-10-{day:02d}",
            "reportDate": f"2026-10-{day:02d}",
            "acceptanceDateTime": f"2026-10-{day:02d}T16:00:00Z",
            "primaryDocument": f"synthetic-{number}.htm", "items": "8.01,9.01",
        })
    # A quiet older row establishes the requested metadata range, not a
    # comprehensive content review. Its document is outside latest-three.
    filings.append({"accessionNumber": "0000320193-25-009000", "form": "10-K",
        "filingDate": "2025-10-01", "reportDate": "2025-09-30",
        "acceptanceDateTime": "2025-10-01T16:00:00Z", "primaryDocument": "synthetic-old.htm", "items": ""})
    recent = {key: [row[key] for row in filings] for key in filings[0]}
    return {"cik": "0000320193", "name": "Synthetic AAPL issuer fixture",
            "tickers": ["AAPL"], "exchanges": ["Nasdaq"],
            "filings": {"recent": recent, "files": []}}


def responses():
    entries = json.loads((HERE / "manifest.json").read_bytes())["captures"]
    bodies = {entry["url"]: (HERE / entry["file"]).read_bytes() for entry in entries}
    bodies[MAPPING_URL] = json_bytes({"fields": ["cik", "name", "ticker", "exchange"], "data": [
        [320193, "Synthetic AAPL issuer fixture", "AAPL", "Nasdaq"],
        [1654126, "ZIM Integrated Shipping Services Ltd.", "ZIM", "NYSE"],
    ]})
    index = aapl_submissions()
    bodies[AAPL_SUBMISSIONS] = json_bytes(index)
    recent = index["filings"]["recent"]
    for accession, document in zip(recent["accessionNumber"][:3], recent["primaryDocument"][:3]):
        base = "https://www.sec.gov/Archives/edgar/data/320193/" + accession.replace("-", "") + "/"
        bodies[base + document] = (
            '<html><body><p>Synthetic issuer source fixture: &lt;img src=x onerror=alert(1)&gt;.</p>'
            '<script>issuer-script-must-not-run</script><p>This document does not classify a trade.</p>'
            '<a href="synthetic-ex99.htm">Exhibit 99.1</a></body></html>'
        ).encode()
        bodies[base + "synthetic-ex99.htm"] = b"<html><body><p>Synthetic issuer release fixture.</p></body></html>"
    return bodies


def transport(variant="collected", *, edits=None):
    bodies = responses()
    if variant == "identity-unverified":
        altered = aapl_submissions()
        altered["cik"] = "0001045810"
        bodies[AAPL_SUBMISSIONS] = json_bytes(altered)
    if edits:
        bodies.update(edits)
    calls = []

    def fetch(url):
        calls.append(url)
        if variant == "outage":
            raise issuer.SourceError("rate_limit")
        if variant == "metadata-only" and "/Archives/" in url:
            raise issuer.SourceError("http_error")
        if url not in bodies:
            raise issuer.SourceError("http_error")
        value = bodies[url]
        if isinstance(value, Exception):
            raise value
        return {"body": value, "observed_at": NOW}

    fetch.calls = calls
    return fetch


def collect(raw, variant="collected", **kwargs):
    options = {"fetch": transport(variant), "now": NOW, "run_id": "fixture-issuer-" + variant,
               "dry_run": True, "allow_fixture": variant != "inapplicable"}
    options.update(kwargs)
    return issuer.collect(raw, **options)


def build():
    raw = publication()
    projected, _ = reader.derive(raw)
    outputs = {"publication.json": raw, "reader.json": projected}
    for variant in VARIANTS:
        # Exercise the browser's normal receipt path over the declared offline
        # producer controls. No network is available to this injected transport.
        result = collect(raw, variant, dry_run=False)
        issuer.validate_for_publication(raw, result["receipt_bytes"], result["bundle_bytes"], allow_fixture=True)
        outputs[variant + "-receipt.json"] = result["receipt_bytes"]
        outputs[variant + "-bundle.json"] = result["bundle_bytes"]
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    changed = []
    outputs = build()
    for name, body in outputs.items():
        target = HERE / name
        if not target.exists() or target.read_bytes() != body:
            changed.append(name)
            if not args.check:
                target.write_bytes(body)
    if args.check and changed:
        raise SystemExit("Stale issuer fixtures: " + ", ".join(changed))
    print(f"{len(outputs)} issuer producer fixtures {'current' if args.check else 'generated'}")


if __name__ == "__main__":
    main()
