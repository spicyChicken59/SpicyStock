"""Offline audit of every retained model plan; no provider or model transport.

Frames are a JSON mapping from ticker to provenance v1 normalized frame objects.
Optional original publications supply verified attribution, never replacement
prices or outcomes. Missing attribution remains unknown in every partition.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src import provenance, record  # noqa: E402


def identity(ref):
    return tuple((ref or {}).get(k) for k in ("id", "context_sha256", "plan_sha256", "pick_sha256"))


def analyze(rec, frames, session, publications=()):
    for pick in rec.get("picks", []):
        problem = record.pick_problem(pick)
        if problem:
            raise ValueError(problem)
    metadata, sources = {}, []
    for data in publications:
        verified = provenance.verify(data, require_sources=False)
        sources.append({"session": data.get("run", {}).get("session"), "verification": verified})
        if verified["status"] == "FAIL":
            raise ValueError("publication integrity failed: " + "; ".join(verified["breaks"]))
        if verified["status"] != "PASS":
            continue
        for candidate in data.get("bursts", []) + data.get("watchlist", {}).get("top", []):
            e = candidate["evidence"]
            if not e["gate"]["ticket"]:
                continue
            metadata[identity(provenance.reference(e))] = {
                "rules_version": e["rules_version"],
                "scan": {"burst": "burst", "dollar": "dollar", "both": "both"}.get(candidate.get("scan"), "anticipation" if e["kind"] == "anticipation" else "unknown"),
                "reader_source": e.get("reader_source", "not_applicable"),
                "grade": e["gate"]["final_grade"], "regime": e["gate"]["regime"],
                "ticker": e["ticker"], "picked": e["session"], "kind": e["kind"]}
    rows = record.scorecard_rows(rec, frames, session)
    for row in rows:
        meta = metadata.get(identity(row["evidence_ref"]), {})
        if meta and any(row[k] != meta[k] for k in ("ticker", "picked", "kind", "grade", "regime")):
            raise ValueError("pick attribution disagrees with exact publication")
        for key in ("rules_version", "scan", "reader_source"):
            row[key] = meta.get(key, "unknown")
    dimensions = ("rules_version", "scan", "grade", "regime", "kind", "reader_source")
    groups = {key: {value: record.summarize_scorecard([r for r in rows if (r.get(key) or "unknown") == value])
                    for value in sorted({r.get(key) or "unknown" for r in rows})} for key in dimensions}
    return {"scorecard": record.scorecard(rec, frames, session), "rows": rows, "partitions": groups,
            "sources": sources, "attribution_check": "publication integrity only; source-frame replay not requested",
            "basis": "Caller-supplied offline bars; original price-basis compatibility must be established separately.",
            "interpretation": "All plans remain in the aggregate. Partitions are descriptive, not strategy selection or evidence of profitability."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--picks", required=True, type=Path)
    parser.add_argument("--frames", required=True, type=Path)
    parser.add_argument("--session", required=True)
    parser.add_argument("--publication", action="append", type=Path, default=[])
    args = parser.parse_args(argv)
    try:
        rec = json.loads(args.picks.read_bytes())
        if rec.get("fixture"):
            raise ValueError("placeholder picks are not published history")
        frames = {ticker: provenance.frame_of(obj) for ticker, obj in json.loads(args.frames.read_bytes()).items()}
        result = analyze(rec, frames, args.session, [json.loads(p.read_bytes()) for p in args.publication])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, str(exc) + "\n")
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
