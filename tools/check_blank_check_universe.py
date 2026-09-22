"""Compare classifiers on every directory retained in Git through the pinned base.

Offline and read-only: no refresh, bars, models or publication. Prints complete
new exclusions, ledger deltas and byte identities; names require human review.
Run: python tools/check_blank_check_universe.py
"""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import types
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import universe  # noqa: E402

BASE = "49e2724c94b60963d914d55a2bf98598ac6507ad"
DIRECTORY = "docs/universe-directory.json.gz"


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def baseline_module():
    module = types.ModuleType("blank_check_baseline")
    module.__file__ = str(ROOT / "src/universe.py")
    sys.modules[module.__name__] = module
    exec(compile(git("show", f"{BASE}:src/universe.py"), module.__file__, "exec"), module.__dict__)
    return module


def compare(before, rows, seeds):
    old_ledger, new_ledger = {}, {}
    old, _, _, old_counts = before.admit(rows, seeds, ledger=old_ledger)
    new, _, _, new_counts = universe.admit(rows, seeds, ledger=new_ledger)
    assert not before.selection_faults(old_ledger)
    assert not universe.selection_faults(new_ledger)
    removed = sorted(set(old) - set(new))
    assert not set(new) - set(old), "unexpected new admission"
    assert not set(seeds) & set(removed), "seed membership lost"
    first = {}
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("symbol"), str):
            first.setdefault(row["symbol"], row)
    changed = []
    for symbol, row in sorted(first.items()):
        old_reason, new_reason = before.classify(row, set()), universe.classify(row, set())
        if old_reason != new_reason:
            assert old_reason is None and new_reason == "blank check company", (symbol, old_reason, new_reason)
            changed.append({"symbol": symbol, "name": row["name"], "industry": row["industry"],
                            "seed_override": symbol in seeds, "before": old_reason, "after": new_reason})
    assert removed == [row["symbol"] for row in changed if not row["seed_override"]]
    assert old_ledger["capacity_excluded"]["count"] == new_ledger["capacity_excluded"]["count"] == 0
    count_delta = {key: new_counts.get(key, 0) - old_counts.get(key, 0)
                   for key in sorted(set(old_counts) | set(new_counts))
                   if new_counts.get(key, 0) != old_counts.get(key, 0)}
    assert count_delta == {"admitted": -len(removed), "blank check company": len(removed)}
    return {"before_intended": len(old), "after_intended": len(new), "newly_excluded": removed,
            "count_delta": count_delta, "before_identity": before.identity(old),
            "after_identity": universe.identity(new), "conservation": "PASS", "changed_rows": changed}


def sweep():
    before = baseline_module()
    seed_raw = git("show", f"{BASE}:data/symbols.txt")
    assert (ROOT / "data/symbols.txt").read_bytes() == seed_raw, "review changed seeds separately"
    seeds = universe.read_seed()
    snapshots, seen = [], set()
    for revision in git("log", "--format=%H", BASE, "--", DIRECTORY).decode().splitlines():
        raw = git("show", f"{revision}:{DIRECTORY}")
        digest = hashlib.sha256(raw).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        snapshot = json.loads(gzip.decompress(raw))
        snapshots.append({"revision": revision, "fetched_at": snapshot["fetched_at"],
                          "directory_sha256": digest, "rows": len(snapshot["rows"]),
                          **compare(before, snapshot["rows"], seeds)})
    retained = json.loads((ROOT / "docs/input-truthfulness/2026-09-18-stale-inputs-results.json").read_text())
    return {"base": BASE, "classifier_sha256": hashlib.sha256((ROOT / "src/universe.py").read_bytes()).hexdigest(),
            "seed_sha256": hashlib.sha256(seed_raw).hexdigest(), "snapshots": snapshots,
            "retained_sample": compare(before, retained["sample_directory_rows"], []),
            "limits": "Directory classification only; no point-in-time security certification or missing-bar cause."}


def no_network(*args, **kwargs):
    raise RuntimeError("network disabled for retained-directory sweep")


if __name__ == "__main__":
    with patch.object(socket.socket, "connect", no_network), patch.object(socket.socket, "connect_ex", no_network), \
            patch.object(socket, "create_connection", no_network):
        print(json.dumps(sweep(), indent=2))
