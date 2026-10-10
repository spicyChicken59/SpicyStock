"""Real offline pipeline publications and real journal producer; no provider calls."""
import argparse
from datetime import date, datetime, timezone
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from src import pipeline, provenance, reader, research_outcomes as journal, stop_research
from tools import make_fixture

TARGET = Path(__file__).parent
STOP = TARGET.parent / "stop-research"
ACTUAL_COHORT_SHA = "249b60c01b702eabc05bba17b0160c7664177e34cfdf26e217c5dbbd1db788f0"
ACTUAL_PUBLICATION_SHA = "f5cbe38eaa38647364f4994bb867bbb7da4354e6a8f7f28315fb96e9b650ef0d"
PENDING_CLOCK = "2026-10-10T13:00:00+00:00"
VARIANTS = ("observed", "revised", "missing", "basis-conflict", "not-filled")


def encoded(data):
    return json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()


def stop_generator():
    spec = importlib.util.spec_from_file_location("stop_source_generator", STOP / "generate.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def artifact(name, publication, result):
    projected, _ = reader.derive(publication)
    return {name + "-publication.json.gz": gzip.compress(publication, mtime=0),
            name + "-reader.json.gz": gzip.compress(projected, mtime=0),
            name + "-receipt.json": result["receipt_bytes"], name + "-bundle.json": result["bundle_bytes"]}


def base_source(docs):
    # These optional output hooks do not participate in canonical decisions.
    # Journal controls call the actual producers explicitly with pinned clocks.
    with mock.patch.object(pipeline, "publish_stop_research"), mock.patch.object(pipeline, "publish_research_outcomes"):
        raw = stop_generator().source_publication("priority", docs)
    reader.write_publication(json.loads(raw), docs)
    cohort = stop_research.build(raw, objects=docs / "evidence", generated_at=PENDING_CLOCK)
    return raw, cohort["bundle_bytes"]


def follow_source(docs, original, variant):
    """Inject dated market inputs before the real pipeline seals the publication."""
    data = json.loads(original)
    frames = {r["ticker"]: provenance.frame_of(provenance._object(docs / "evidence", r["evidence"]["source"]["sha256"])) for r in data["watchlist"]["top"]}
    prior_register = make_fixture.register
    # COIL resolves one whole share, RONE has unknown intraday trigger timing,
    # RTHR opens within the zone and stays open. These are declared examples.
    tails = {"COIL": [55.31, 60.0, 55.1, 59.0, 1000000],
             "RONE": [55.0, 56.0, 54.9, 55.5, 1000000],
             "RTHR": [55.4, 56.0, 55.2, 55.8, 1000000],
             "RTWO": [55.4, 56.0, 55.2, 55.8, 1000000],
             "ZBASE": [112.2, 113.0, 111.5, 112.5, 1000000]}
    if variant == "revised": tails["COIL"][2] = 53.0  # same close; different low changes the stop-first result
    if variant == "not-filled":
        tails["COIL"] = [55.0,55.1,54.8,55.0,1000000]
        tails["RONE"] = [56.0,56.5,55.5,56.2,1000000]  # opened past limit, then under it
        tails["RTHR"] = [55.0,56.0,53.0,55.5,1000000]  # trigger/stop sequence unknown
    session = date(2026, 10, 13) if variant == "missing" else date(2026, 10, 12)
    def register(fake, kind):
        names = prior_register(fake, kind)
        for symbol, frame in frames.items():
            frame = make_fixture.append_bar(frame, tails[symbol])
            if variant == "missing":
                frame = make_fixture.append_bar(frame, tails[symbol])
            fake.add_history(symbol, frame, gap_before_session=variant == "missing")
            if symbol not in names: names.append(symbol)
        return names
    env = {"ACCOUNT_EQUITY":"2000", "RISK_PCT":".5", "MAX_POSITION_PCT":"25", "MAX_OPEN_POSITIONS":"4",
           "GITHUB_RUN_ID_FOR_RECORD":"synthetic-journal-" + variant, "SCAN_FEED":"iex" if variant == "basis-conflict" else "sip"}
    clock = datetime.combine(session, datetime.min.time(), timezone.utc).replace(hour=22, minute=30)
    reader.write_publication(json.loads(original), docs)
    with mock.patch.dict(os.environ, env), mock.patch.object(make_fixture, "SESSION", session), \
            mock.patch.object(make_fixture, "EVENING", clock), mock.patch.object(make_fixture, "register", register), \
            mock.patch.object(make_fixture, "prior_picks", return_value={"schema_version":1,"picks":[]}), \
            mock.patch.object(pipeline, "publish_stop_research"), mock.patch.object(pipeline, "publish_research_outcomes"):
        publication = make_fixture.run_variant("full", docs)
    publication.pop("fixture")
    raw = encoded(publication)
    assert provenance.verify(json.loads(raw), objects=docs / "evidence", require_sources=True)["status"] == "PASS"
    return raw, session.isoformat() + "T23:00:00+00:00"


def build():
    files = {}
    current = gzip.decompress((STOP / "current-publication.json.gz").read_bytes())
    assert hashlib.sha256(current).hexdigest() == ACTUAL_PUBLICATION_SHA
    actual = (ROOT / "docs/stop-research" / (ACTUAL_COHORT_SHA + ".json")).read_bytes()
    assert hashlib.sha256(actual).hexdigest() == ACTUAL_COHORT_SHA
    pending = journal.build(current, cohorts=[actual], objects=ROOT / "docs/evidence", generated_at=PENDING_CLOCK)
    files.update(artifact("pending", current, pending))
    with tempfile.TemporaryDirectory(prefix="journal-fixture-") as tmp:
        root = Path(tmp); initial_dir = root / "initial"
        original, source = base_source(initial_dir)
        seed = journal.build(original, cohorts=[source], objects=initial_dir / "evidence", generated_at=PENDING_CLOCK)
        files.update(artifact("synthetic-pending", original, seed))
        observed = None
        for variant in VARIANTS:
            docs = root / variant
            shutil.copytree(initial_dir, docs)
            publication, clock = follow_source(docs, original, variant)
            previous = observed if variant == "revised" else seed
            result = journal.build(publication, cohorts=[source], objects=docs / "evidence", previous=(previous["receipt_bytes"], previous["bundle_bytes"]), generated_at=clock)
            if variant == "observed": observed = result
            files.update(artifact(variant, publication, result))
        # A later derivation of the same canonical is a deliberately late source
        # control; the archive writer separately preserves one first capture.
        late = stop_research.build(original, objects=initial_dir / "evidence", generated_at="2026-10-12T15:00:00+00:00")
        revisions = journal.build(original, cohorts=[late["bundle_bytes"], source], objects=initial_dir / "evidence", generated_at="2026-10-12T15:00:01+00:00")
        files.update(artifact("cohort-revisions", original, revisions))
        for name in ("empty", "red"):
            docs = root / name
            with mock.patch.object(pipeline, "publish_stop_research"), mock.patch.object(pipeline, "publish_research_outcomes"):
                raw = stop_generator().source_publication(name, docs)
            frozen = stop_research.build(raw, objects=docs / "evidence", generated_at=PENDING_CLOCK)
            result = journal.build(raw, cohorts=[frozen["bundle_bytes"]], objects=docs / "evidence", generated_at=PENDING_CLOCK)
            files.update(artifact(name, raw, result))
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--check", action="store_true")
    args = parser.parse_args(); files = build(); stale = []
    for name, raw in files.items():
        path = TARGET / name
        if args.check:
            if not path.is_file() or path.read_bytes() != raw: stale.append(name)
        else: path.write_bytes(raw)
    if stale:
        print("Stale journal fixtures: " + ", ".join(stale)); return 1
    print(f"{len(files)} research-outcomes fixture files " + ("current" if args.check else "written")); return 0


if __name__ == "__main__":
    raise SystemExit(main())
