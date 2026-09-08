#!/usr/bin/env python3
"""Project docs/ledger.json after a full year using the normalized history fixture.

README quotes this number, the page's "load every burst of every name" button
is justified by it, and it is exactly the kind of fact this repo has watched
rot three times: it was 8.8 MB raw and 0.59 MB gzipped, and by the time the
3.3 audit had added `context` to both row types it was 11 MB and 0.66. Nobody
re-measured, because re-measuring meant building an eleven-megabyte file by
hand.

So this builds one. Real rows, drawn from the history `tools/make_history.py`
generates by driving the real pipeline offline; real row COUNTS, taken from the
canonical one-night fixture; and the real `src.ledger._write_json`, because
`indent=2` is most of the raw size and a compact estimate is not the file the
browser fetches. This is a fixture-based projection; production precision and optional metadata can change the actual size.

    python tools/measure_ledger.py

The rows carry no model prose -- `slim_row()` drops `reason` and `key_risk` --
so synthetic rows exercise the same schema. Derived Stockbee fixture metrics
are normalized to eight decimals for reproducibility; production precision
and optional learning observation dates can make real rows somewhat larger.
"""
from __future__ import annotations

import copy
import gzip
import json
import pathlib
import random
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import ledger  # noqa: E402

HISTORY = ROOT / "tests" / "fixtures" / "history" / "ledger.json"
ONE_NIGHT = ROOT / "tests" / "fixtures" / "data.json"


def measure(runs_wanted: int = ledger.MAX_RUNS) -> dict:
    history = json.loads(HISTORY.read_text())["runs"]
    night = json.loads(ONE_NIGHT.read_text())
    n_scored = night["run"]["scored"]
    n_gated = len(night["gated_out"])

    scored_rows = [c for r in history for c in (r.get("candidates") or [])]
    gated_rows = [g for r in history for g in (r.get("gated") or [])]
    if not scored_rows or not gated_rows:
        raise SystemExit(f"{HISTORY} holds no rows to draw from")

    # Seeded, so two runs of this script report the same number and a change in
    # it is a change in the data rather than in the dice.
    rng = random.Random(0)
    runs = []
    for i in range(runs_wanted):
        run = copy.deepcopy(history[i % len(history)])
        run["date"] = f"20{25 + i // 252:02d}-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}"
        run["candidates"] = [copy.deepcopy(rng.choice(scored_rows)) for _ in range(n_scored)]
        run["gated"] = [copy.deepcopy(rng.choice(gated_rows)) for _ in range(n_gated)]
        runs.append(run)

    out = pathlib.Path(tempfile.mkdtemp()) / ledger.LEDGER_NAME
    ledger._write_json(out, {"schema_version": ledger.SCHEMA_VERSION, "app": "SpicyStock",
                             "generated": "2026-01-01T00:00:00Z", "runs": runs})
    raw = out.read_bytes()
    return {"runs": runs_wanted, "scored_per_run": n_scored, "gated_per_run": n_gated,
            "rows": runs_wanted * (n_scored + n_gated),
            "raw_mb": len(raw) / 1e6, "gzip_mb": len(gzip.compress(raw, 9)) / 1e6}


if __name__ == "__main__":
    m = measure()
    print(f"{m['runs']} runs x ({m['scored_per_run']} scored + {m['gated_per_run']} gated) "
          f"= {m['rows']:,} rows")
    print(f"  raw      {m['raw_mb']:6.2f} MB")
    print(f"  gzipped  {m['gzip_mb']:6.2f} MB")
    print("\nREADME quotes these two numbers; if they have moved, sweep it.")
