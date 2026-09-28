"""Network-blocked replay from the bounded acquisition's private frozen cache.

python tools/historical_reconcile.py --manifest <frozen.json> --storage <approved-dir> --session 2026-09-24

All detailed outputs remain beside the approved private inputs. This command
does not publish, create orders, reuse reader replies, or contact any service.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import date
import hashlib
import json
from pathlib import Path
import socket
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.historical_acquisition import cached_pages, validate_manifest, encode
from tools.historical_breadth_reference import compare_replay
from tools.historical_normalization import normalize_pages, frames_for_replay, decimal_event_audit


@contextmanager
def network_blocked():
    def refused(*args, **kwargs):
        raise RuntimeError("historical reconciliation network is blocked")
    original = socket.socket.connect, socket.socket.connect_ex, socket.create_connection
    socket.socket.connect = socket.socket.connect_ex = socket.create_connection = refused
    try:
        yield
    finally:
        socket.socket.connect, socket.socket.connect_ex, socket.create_connection = original


def reconcile(manifest, storage, session):
    """Public callers receive metadata; per-event values are private artifacts."""
    identity = validate_manifest(manifest)
    storage = Path(storage).resolve()
    if storage == ROOT or ROOT in storage.parents or any((p / ".git").exists() for p in [storage, *storage.parents]):
        raise ValueError("reconciliation storage must stay outside Git")
    if session not in manifest["populations"]:
        raise ValueError("unknown target session")
    queries = [q for q in manifest["queries"] if q.get("purpose") == "canonical" and
               q.get("target_session") == session and q.get("scope") != "probe"]
    if not queries:
        raise ValueError("no frozen canonical queries for target session")
    mapping = {(q["asof"], q["adjustment"], q["feed"], q["currency"], q["start"], q["end"]) for q in queries}
    if len(mapping) != 1:
        raise ValueError("different security mapping/data bases cannot be merged")
    requested = [s for q in queries for s in q["symbols"]]
    intended = manifest["populations"][session]["symbols"]
    if set(requested) != set(intended) | {"SPY"} or len(requested) != len(set(requested)):
        raise ValueError("query coverage does not exactly partition original intended population plus benchmark")
    details = {"schema": "historical-reconciliation-v1", "manifest_sha256": identity,
               "session": session, "network_blocked": True, "new_provider_requests": 0,
               "reader_actionability": "unknown", "publication_allowed": False,
               "A": {"status": "NOT RUN", "basis": "separate original-reconciliation.json must be verified by historical_input_proof.py"},
               "B": {"status": "BLOCKED", "reason": "complete original final price-exclusion mask was not retained"},
               "normalizations": [], "symbol_manifest": {}, "failures": []}
    frames, page_hashes, retrievals, projections = {}, [], [], []
    with network_blocked():
        for q in queries:
            cached = cached_pages(manifest, storage, q["id"])
            # Expansion is bound to the same frozen manifest as the page cache.
            from tools.historical_acquisition import resolved_query
            q = resolved_query(manifest, q["id"])
            normalized = normalize_pages(cached["pages"], query=q, terminal=cached["terminal"],
                                         target_session=session, required_sessions=q.get("required_sessions"))
            details["normalizations"].append(normalized)
            normalized["decimal_event_audit"] = decimal_event_audit(normalized)
            details["failures"].extend({"query": q["id"], **failure} for failure in cached["failures"])
            details["ledger"] = cached["ledger"]
            subset, projection = frames_for_replay(normalized)
            frames.update(subset)
            projections.append({"query": q["id"], **projection})
            for s, record in normalized["symbols"].items():
                status = record["status"]
                if cached["failures"] and status == "requested":
                    status = "failed"
                details["symbol_manifest"][s] = {"status": status, "query": q["id"],
                     "rows": record["selected_rows"], "missing_anchors": record["missing_anchors"],
                     "missing_required_sessions": record["missing_required_sessions"],
                     "complete_required_window": record["complete_required_window"]}
            page_hashes.extend(normalized["page_sha256"])
            retrievals.extend(p["retrieved_at"] for p in cached["pages"])
        source = {"kind": "later_retrieval", "manifest_sha256": identity, "page_sha256": page_hashes,
                  "retrieved_at": sorted(set(retrievals)), "asof": queries[0]["asof"],
                  "feed": "sip", "timeframe": "1Day", "adjustment": "split", "currency": "USD",
                  "normalization": "historical-normalization-v1", "reader_reuse": False}
        details["float64_projection"] = projections
        details["complete_required_input_windows"] = all(r["complete_required_window"] for r in details["symbol_manifest"].values())
        if all(n["terminal"] for n in details["normalizations"]):
            for mode in ("C", "D"):
                details[mode] = compare_replay(frames, date.fromisoformat(session), intended=intended,
                    source_identity=source, mode=mode, price_exempt=manifest["populations"][session].get("price_exempt", []))
        else:
            for mode in ("C", "D"):
                details[mode] = {"status": "BLOCKED", "reason": "incomplete pagination cannot establish an eligible population"}
        # Scan/quality here is diagnostic: no grader, model, pipeline or planner.
        from src import quality, scans
        mechanical = {}
        if "reference" in details["C"]:
            included = details["C"]["reference"]["masks"][-1]["included"]
            for symbol in included:
                frame = frames.get(symbol)
                if frame is None:
                    continue
                matched = {k: bool(v) for k, v in scans.scan_all(frame).items()}
                if matched.get("burst") or matched.get("dollar"):
                    mechanical[symbol] = {"scans": matched, "quality": quality.assess(frame).to_dict(),
                                          "reader_actionability": "unknown", "publication_allowed": False}
        details["mechanical_candidates"] = mechanical
        details["same_input_formula_status"] = ("FAIL" if any(details[m]["status"] == "FAIL" for m in ("C", "D")) else
                             "BLOCKED" if any(details[m]["status"] == "BLOCKED" for m in ("C", "D")) else "PASS")
        details["reconstructed_regime_established"] = (
            details["C"].get("reference", {}).get("underlying_regime_established", False) and
            not any(r["status"] in ("failed", "unresolved", "requested") for r in details["symbol_manifest"].values()))
        details["status"] = details["same_input_formula_status"]
        if details["status"] == "PASS" and not details["reconstructed_regime_established"]:
            details["status"] = "BLOCKED"
        destination = storage / ("reconciliation-" + session + ".json")
        if destination.is_symlink():
            raise ValueError("reconciliation output symlink forbidden")
        raw = encode(details)
        destination.write_bytes(raw)
    return {"status": details["status"], "session": session, "manifest_sha256": identity,
            "output_sha256": hashlib.sha256(raw).hexdigest(), "new_provider_requests": 0,
            "population_states": dict(Counter(r["status"] for r in details["symbol_manifest"].values())),
            "complete_required_input_windows": details["complete_required_input_windows"],
            "same_input_formula_status": details["same_input_formula_status"],
            "reconstructed_regime_established": details["reconstructed_regime_established"],
            "regime_scope": "later target-day eligible population, with explicit omissions; not the original information set or all intended stocks",
            "reconstructed_regime": details.get("C", {}).get("reference", {}).get("regime"),
            "original_information_set_reproduced": False, "reader_actionability": "unknown"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--storage", type=Path, required=True)
    parser.add_argument("--session", choices=["2026-09-24", "2026-09-25"], required=True)
    args = parser.parse_args(argv)
    try:
        result = reconcile(json.loads(args.manifest.read_bytes()), args.storage, args.session)
    except Exception:
        print(json.dumps({"status": "BLOCKED", "reason": "frozen_input_or_identity_validation_failed"}))
        return 2
    print(json.dumps(result))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
