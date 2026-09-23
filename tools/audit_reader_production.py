"""Reconstruct Sep 22 request identities offline; never invent missing replies.

Use --implementation with an untouched checkout of the execution revision.
The publication is read from Git, and its immutable evidence objects from docs.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EXECUTION = "6533e616bd14ebfebeeccb4c9b1b0d463b47dbb4"
PUBLICATION = "e2dee988ad5d36876b7c73090502720e995c65f4"
PUBLICATION_SHA256 = "507127d7a6e07f2d1120290c96cd717e1ef72529be8053218d317bb9b9ee3c36"
TICKERS = ["IOSP", "KYMR", "HSIC", "IDCC", "CLMB", "CRVL", "MEDP", "NEM", "PYPD", "WPM", "AG", "AIT"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--implementation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=args.implementation, text=True).strip()
    if revision != EXECUTION:
        raise ValueError("use the exact production execution checkout")
    dirty = subprocess.check_output(["git", "diff", "HEAD", "--", "src"], cwd=args.implementation)
    if dirty:
        raise ValueError("execution implementation must be untouched")
    sys.path.insert(0, str(args.implementation.resolve()))
    from src import grader, provenance, quality

    raw = subprocess.check_output(["git", "show", PUBLICATION + ":docs/data.json"], cwd=ROOT)
    assert hashlib.sha256(raw).hexdigest() == PUBLICATION_SHA256
    data = json.loads(raw)
    ledger_path = ROOT / "docs/quality-ledger/v1" / (PUBLICATION_SHA256 + ".json.gz")
    ledger = json.loads(gzip.decompress(ledger_path.read_bytes()))
    assert ledger["publication"]["execution_revision"] == EXECUTION
    objects = ROOT / "docs/evidence"
    decisions = []
    for ticker in TICKERS:
        row = next(r for r in data["bursts"] if r["ticker"] == ticker)
        saved = next(r for r in ledger["signal"]["candidates"] if r["ticker"] == ticker)
        cl, ri = row["claude"], row["evidence"]["reader_input"]
        assert saved["reader"] == cl
        assert len(cl["attempts"]) == 1
        source = provenance._object(objects, row["evidence"]["source"]["sha256"])
        df = provenance.frame_of(source)
        assessment = quality.assess(df)
        assert (assessment.grade, assessment.score) == (row["grade_mechanical"], row["score"])
        extra = {k: row[k] for k in ("scan", "discovery", "flags", "gain_pct", "volume_vs_prior", "dollar_volume")}
        metrics = quality.metrics_for_model(assessment, ticker, row["close"], extra)
        assert provenance.digest(metrics) == ri["metrics_sha256"]
        system = provenance._object(objects, ri["system_object"])["text"]
        assert hashlib.sha256(system.encode()).hexdigest() == ri["system_sha256"]
        chart = provenance._object(objects, ri["chart_sha256"], binary=True)
        user = grader.user_text(metrics)
        request_text = hashlib.sha256(json.dumps({"system": system, "user": user}, sort_keys=True).encode()).hexdigest()
        assert request_text == ri["request_text_sha256"] == cl["request_text_sha256"]
        kwargs = grader.request_kwargs(system, [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(chart).decode()}},
            {"type": "text", "text": user}], model=cl["attempted_model"])
        assert provenance.digest(kwargs) == cl["attempts"][0]["request_sha256"]
        assert "output_config" not in kwargs
        assert cl["source"] == "fallback" and row["grade"] == row["grade_mechanical"]
        decisions.append({
            "ticker": ticker, "mechanical_grade": assessment.grade, "mechanical_score": assessment.score,
            "final_grade": row["grade"], "reader": cl, "reader_input": ri,
            "metrics": metrics, "user_text_sha256": hashlib.sha256(user.encode()).hexdigest(),
            "fallback_transport": grader._fallback(metrics, cl["error"]),
            "raw_response": None, "raw_response_sha256": None, "parsed_score": None,
            "parsed_grade": None, "findings": None, "otherwise_valid_finding": None,
            "structural_subclass": None, "semantic_authority": None,
            "response_reconstruction": "BLOCKED", "request_reconstruction": "PASS",
        })
    result = {
        "evidence_kind": "real production records plus deterministic offline request reconstruction",
        "run": "35802203679", "attempt": 1, "session": "2026-09-22",
        "execution_revision": EXECUTION, "publication_commit": PUBLICATION,
        "publication_sha256": PUBLICATION_SHA256, "ledger_path": ledger_path.relative_to(ROOT).as_posix(),
        "ledger_sha256": hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
        "coverage": data["run"]["coverage"], "decisions": decisions,
        "limits": ["No raw response, response digest, parsed score/grade or findings were retained.",
                   "The shared error cannot distinguish a non-object finding from missing/extra fields.",
                   "No real response acceptance or semantic finding classification can be replayed."],
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"request_reconstruction": "PASS", "count": len(decisions),
                      "response_reconstruction": "BLOCKED", "output": str(args.output)}))


if __name__ == "__main__":
    main()
