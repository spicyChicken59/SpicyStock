"""Offline payload and verification measurements; never scans or calls a model."""
from __future__ import annotations
import argparse
from copy import deepcopy
import gzip
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import history, provenance  # noqa: E402


def encoded(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def sizes(raw):
    return {"raw": len(raw), "gzip": len(gzip.compress(raw, mtime=0))}


def archive(data):
    data = deepcopy(data); data.pop("fixture", None)
    with tempfile.TemporaryDirectory() as tmp:
        history.publish(encoded(data), Path(tmp))
        files = list(Path(tmp).rglob("*.json"))
        return {"files": len(files), "raw": sum(p.stat().st_size for p in files),
                "gzip_individual": sum(sizes(p.read_bytes())["gzip"] for p in files)}


def measure(base):
    old_raw = subprocess.check_output(["git", "show", base + ":tests/fixtures/page/full.json"], cwd=ROOT)
    old_picks = subprocess.check_output(["git", "show", base + ":tests/fixtures/page/full-picks.json"], cwd=ROOT)
    raw = (ROOT / "tests/fixtures/page/full.json").read_bytes()
    picks_raw = (ROOT / "tests/fixtures/page/full-picks.json").read_bytes()
    old, data, picks = json.loads(old_raw), json.loads(raw), json.loads(picks_raw)
    objects = ROOT / "tests/fixtures/provenance/objects"
    started = perf_counter()
    result = provenance.verify(data, picks, objects, require_picks=True)
    cold = (perf_counter() - started) * 1000
    assert result["status"] == "PASS", result
    timings = []
    for _ in range(20):
        started = perf_counter()
        assert provenance.verify(data, picks, objects, require_picks=True)["status"] == "PASS"
        timings.append((perf_counter() - started) * 1000)
    rows = data["bursts"] + data["watchlist"]["top"]
    old_rows = {r["ticker"]: r for r in old["bursts"] + old["watchlist"]["top"]}
    receipts = {r["evidence"]["kind"] + ":" + r["ticker"]: sizes(encoded(r["evidence"])) for r in rows}
    refs = {r["ticker"]: sizes(encoded(r["plan"]["evidence_ref"])) for r in rows if r.get("plan")}
    candidates = {r["ticker"]: {"before": sizes(encoded(old_rows[r["ticker"]])), "after": sizes(encoded(r))} for r in rows}
    plans = {r["ticker"]: {"before": sizes(encoded(old_rows[r["ticker"]]["plan"])), "after": sizes(encoded(r["plan"]))} for r in rows if r.get("plan")}
    keys = set()
    for r in rows:
        e = r["evidence"]; keys.add(e["source"]["sha256"] + ".json.gz")
        ri = e.get("reader_input", {})
        if ri:
            keys.add(ri["system_object"] + ".json.gz")
            if ri["chart_sha256"]: keys.add(ri["chart_sha256"] + ".png")
    retained = [objects / name for name in keys]
    return {"base": base, "schema": provenance.VERSION,
        "full_fixture": {"before": sizes(old_raw), "after": sizes(raw)},
        "full_picks": {"before": sizes(old_picks), "after": sizes(picks_raw)},
        "receipts_compact": receipts, "plan_references_compact": refs,
        "candidate_payloads_compact": candidates, "plan_payloads_compact": plans,
        "recovery_snapshot": {"before": archive(old), "after": archive(data)},
        "source_archive_full_fixture": {"objects": len(retained), "stored_bytes": sum(p.stat().st_size for p in retained),
            "expanded_json_bytes": sum(len(gzip.decompress(p.read_bytes())) for p in retained if p.name.endswith(".gz")),
            "note": "separate lazy objects; fixture image is a fixed PNG double, not a real chart-size estimate"},
        "verification": {"candidates": len(rows), "first_ms": round(cold, 3), "warm_mean_ms": round(statistics.mean(timings), 3),
            "warm_p95_ms": round(sorted(timings)[18], 3), "samples": len(timings), "scope": "full chain, retained source/reader inputs and persisted picks"},
        "production_records_changed": False, "provider_calls": 0, "model_calls": 0, "initial_browser_requests_added": 0}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", default="f744b88a6117b933310f370b8f9ab4cd1d03a3c8")
    p.add_argument("--json", type=Path)
    args = p.parse_args()
    result = measure(args.base)
    text = json.dumps(result, indent=2) + "\n"
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
