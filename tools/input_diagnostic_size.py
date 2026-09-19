"""Deterministic offline upper-shape fixture; no provider or model execution."""
import gzip
import itertools
import json
import string
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
from src import input_diagnostics as diag, inputs, market_data, universe


def fixture():
    """All 8,001 fetch names affected, all ten slots and seven fields populated.

    Deliberately extreme, invalid prices and dates beyond the requested session
    exercise the payload bound; this is not simulated provider quality or history.
    """
    now = datetime(2026, 9, 18, 22, 30, tzinfo=timezone.utc)
    names = ["X" + "".join(s) for s in itertools.islice(itertools.product(string.ascii_uppercase, repeat=4), 8000)]
    symbols = names + ["SPY"]
    index = pd.date_range("2026-09-01T00:00:00.123456789+00:00", periods=260)
    frame = pd.DataFrame({field: [-1.7976931348623157e308] * len(index) for field in diag.FIELDS}, index=index)
    frames = {symbol: frame for symbol in symbols}
    stats = market_data.DownloadStats(now.date(), "sip", requested=len(symbols), with_bars=len(symbols))
    ready = market_data.apply_session_rules(frames, now.date(), stats)
    uni = universe._explicit_universe(names)
    cov = inputs.build(uni, symbols, frames, stats, ready, now.date(), now.date(),
                       closed=False, minimum=.5, benchmark="SPY")
    record = diag.build(identity={"run_id": "1" * 20, "attempt": "1" * 10,
                                 "execution_revision": "a" * 40, "workflow_revision": "b" * 40,
                                 "invocation": "c" * 32},
                        captured_at=now, uni=uni, symbols=symbols, frames=frames, stats=stats, ready=ready,
                        coverage=cov, expected=now.date(), session=now.date(), now=now,
                        lookback=260, chunk_size=500, budget=900)
    record["directory"] = {"status": "not_used"}
    record["record_sha256"] = diag.digest(record)
    diag.validate(record, expected_run=record["run"], ledger=cov)
    return record


def measure(record):
    raw = diag.canonical(record)
    return {"fixture": "extreme_synthetic_not_provider_evidence", "symbols": record["intended"]["count"],
            "rows_retained": sum(len(o["rows"]) for o in record["observations"].values()),
            "json_bytes": len(raw), "gzip_bytes": len(gzip.compress(raw, mtime=0)),
            "optional_directory_max_bytes": universe.DIRECTORY_MAX_BYTES}


if __name__ == "__main__":
    print(json.dumps(measure(fixture()), sort_keys=True, indent=2))
