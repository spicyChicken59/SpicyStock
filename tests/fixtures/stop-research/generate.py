"""Exact retained publication plus offline pipeline controls; no provider calls."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from datetime import date, datetime, timezone
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from src import provenance, reader, stop_research
from tools import make_fixture

TARGET = Path(__file__).parent
NOW = "2026-10-10T12:00:00+00:00"
CURRENT_SHA = "f5cbe38eaa38647364f4994bb867bbb7da4354e6a8f7f28315fb96e9b650ef0d"
VARIANTS = ("current", "priority", "empty", "red", "outside")


def encoded(data):
    # Preserve quality-check insertion order, as canonical pipeline transport does.
    return json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()


def source_publication(name, docs, *, ledger_factory=None, account_equity="2000"):
    original = make_fixture.register
    def register(fake, variant):
        names = original(fake, variant)
        if name in ("priority", "red"):
            narrow = fake.history["COIL"].copy()
            # The later-ranked unchanged baseline remains under 4%, but one
            # wider-range bar removes its TTT flag. No published row is edited.
            narrow.iloc[-3, narrow.columns.get_loc("High")] = 112.0
            fake.add_history("ZBASE", narrow)
            names.append("ZBASE")
            wide = fake.history["COIL"].copy()
            for i in range(-70, -10):
                wide.iloc[i, wide.columns.get_loc("High")] = wide.Close.iloc[i] + 4.5
                wide.iloc[i, wide.columns.get_loc("Low")] = wide.Close.iloc[i] - 4.5
            for column, value in {"Open": 110.0, "High": 110.5, "Low": 106.7, "Close": 110.0}.items():
                wide.iloc[-10:, wide.columns.get_loc(column)] = value
            for column in ("Open", "High", "Low", "Close"):
                wide[column] *= .5
            fake.history["COIL"] = wide
            for symbol in ("RONE", "RTWO", "RTHR"):
                fake.add_history(symbol, wide.copy())
                names.append(symbol)
        return names
    env = {"ACCOUNT_EQUITY": account_equity, "RISK_PCT": ".5", "MAX_POSITION_PCT": "25",
           "MAX_OPEN_POSITIONS": "4", "GITHUB_RUN_ID_FOR_RECORD": "synthetic-stop-research-" + name}
    session = date(2026, 9, 10) if name == "outside" else date(2026, 10, 9)
    clock = datetime.combine(session, datetime.min.time(), timezone.utc).replace(hour=22, minute=30)
    variant = "empty" if name == "empty" else "red" if name == "red" else "full"
    with mock.patch.dict(os.environ, env), mock.patch.object(make_fixture, "SESSION", session), \
            mock.patch.object(make_fixture, "EVENING", clock), \
            mock.patch.object(make_fixture, "prior_picks", side_effect=ledger_factory or (lambda *_: {"schema_version": 1, "picks": []})), \
            mock.patch.object(make_fixture, "register", register):
        data = make_fixture.run_variant(variant, docs)
    # Established production-shaped offline fixture convention. Market/model
    # doubles supply inputs; the real pipeline seals every plan/context.
    data.pop("fixture")
    raw = encoded(data)
    assert provenance.verify(json.loads(raw), objects=docs / "evidence", require_sources=True)["status"] == "PASS"
    return raw


def artifacts(name, raw, objects):
    result = stop_research.build(raw, objects=objects, generated_at=NOW)
    projected, _ = reader.derive(raw)
    return {name + "-publication.json.gz": gzip.compress(raw, mtime=0),
            name + "-reader.json.gz": gzip.compress(projected, mtime=0),
            name + "-receipt.json": result["receipt_bytes"],
            name + "-bundle.json": result["bundle_bytes"]}


def build():
    raw = gzip.decompress((TARGET / "current-publication.json.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == CURRENT_SHA, "fixed actual publication changed"
    files = artifacts("current", raw, ROOT / "docs/evidence")
    late = stop_research.build(raw, objects=ROOT / "docs/evidence", generated_at="2026-10-12T15:00:00+00:00")
    files.update({"current-late-receipt.json": late["receipt_bytes"], "current-late-bundle.json": late["bundle_bytes"]})
    for name in VARIANTS[1:]:
        with tempfile.TemporaryDirectory(prefix="stop-research-fixture-") as tmp:
            docs = Path(tmp)
            generated = source_publication(name, docs)
            files.update(artifacts(name, generated, docs / "evidence"))
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = build()
    stale = []
    for name, raw in files.items():
        target = TARGET / name
        if args.check:
            if not target.is_file() or target.read_bytes() != raw: stale.append(name)
        else:
            target.write_bytes(raw)
    if stale:
        print("Stale stop-research controls: " + ", ".join(stale)); return 1
    print(f"{len(files)} stop-research fixture files " + ("current" if args.check else "written"))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
