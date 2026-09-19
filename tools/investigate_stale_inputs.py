"""Read-only verification of the retained 2026-09-18 evidence; never fetch data.

Use the original Actions ZIP and the directory blob from publication 8387cce.
Hashes deliberately pin this investigation, not a general provider diagnostic.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import io
import json
from pathlib import Path
import socket
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ZIP_SHA = "d95f9f2c852bb5901ee7a022ef606f30745d785350665dbc2edadb93a27e2352"
DATA_SHA = "aae64bbd1be0c0126f9c24c6ad5b4b5be1434a51e7351e5085c2f00862215567"
RECORD_SHA = "f97c1cf83e120e8d694e4bcbc704744cebbadccd76f2bdea93f785564847ef80"
DIRECTORY_SHA = "a58e9d566751bb95a600d0fc723746fa04ddad719e9c51f34c09b5790bd30df9"
ARCHIVE_ID = "bf36144ea45d7c74eee724d2557964e5e8e0bfc5"
SAMPLE = ["ANTA", "BKHA", "BLIV", "BMHL", "EGHA", "GDEV", "HCMA", "INTJ"]
SOURCE_BLOBS = {
    "data/symbols.txt": "61fa0d913d509fa3c00d383490028af3cab640f8",
    "src/inputs.py": "bb0d10d584bd177c401b23661378acf86e955d72",
    "src/market_data.py": "a34ba5b80c337b9746ca574164b5c2bcc6212110",
    "src/universe.py": "a65066d6d93212b7a87066236e0131696b10df8e",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def checked(raw, expected, label):
    actual = hashlib.sha256(raw).hexdigest()
    require(actual == expected, f"{label}: SHA-256 mismatch ({actual})")
    return actual


def git_blob(raw):
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()


def no_network(*args, **kwargs):
    raise RuntimeError("network disabled for retained-evidence investigation")


def diagnose(artifact: Path, directory: Path):
    import zipfile

    # Verify identity before parsing or importing the classification code.
    original_zip, original_directory = artifact.read_bytes(), directory.read_bytes()
    checked(original_zip, ZIP_SHA, "artifact ZIP")
    checked(original_directory, DIRECTORY_SHA, "directory gzip")
    for path, sha in SOURCE_BLOBS.items():
        require(git_blob((ROOT / path).read_bytes()) == sha, f"source changed: {path}")
    from src import inputs, universe

    with zipfile.ZipFile(io.BytesIO(original_zip)) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "duplicate ZIP entry names")
        raw = archive.read("data.json")
        raw_record = archive.read(f"history/{ARCHIVE_ID}/record.json")
        checked(raw, DATA_SHA, "original data.json")
        checked(raw_record, RECORD_SHA, "historical record.json")
        require(git_blob(raw) == ARCHIVE_ID, "archive ID differs from data Git blob")
        data, record = json.loads(raw), json.loads(raw_record)
        require(data["run"] == record["run"], "run contexts differ")
        catalog = json.loads(archive.read("history/index.json"))
        sample_entries = [e for e in catalog["entries"] if e["ticker"] in SAMPLE]
        require(not sample_entries, "sample has catalog evidence; inspect it")
        inventory = dict(sorted(Counter(n.split('/')[0] if '/' in n else n for n in names).items()))
        manifest = "\n".join(f"{n}\t{hashlib.sha256(archive.read(n)).hexdigest()}" for n in sorted(names))

    run = data["run"]
    require(run["session"] == "2026-09-18" and run["run_id"] == "35401227388", "wrong run")
    require(inputs.record_faults(run) == [], "coverage/selection conservation failed")
    snapshot = json.loads(gzip.decompress(original_directory))
    rows = snapshot["rows"]
    canonical = [{k: row.get(k) for k in universe.DIRECTORY_FIELDS} for row in rows]
    fingerprint = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    require(fingerprint == run["universe"]["snapshot_sha256"], "directory fingerprint differs")
    require(snapshot["fetched_at"] == run["universe"]["fetched_at"], "directory timestamp differs")
    ledger = {}
    seeds = universe.read_seed()
    symbols, _, _, counts = universe.admit(rows, seeds, ledger=ledger)
    require(ledger == run["universe"]["selection"], "reproduced selection differs")
    require(counts == run["universe"]["counts"], "reproduced classification counts differ")
    require(universe.identity(symbols) == run["universe"]["identity"], "intended identity differs")
    require(universe.identity(sorted(set(symbols) | {"SPY"})) == run["coverage"]["intended_identity"], "fetch identity differs")
    stale = run["coverage"]["reasons"]["stale"]
    require(stale == {"count": 19, "identity": "c0c17644c58c108f", "sample": SAMPLE}, "stale receipt differs")
    sampled_rows = []
    controls = {}
    for symbol in SAMPLE:
        row = next(r for r in rows if r.get("symbol") == symbol)
        require(symbol in symbols and symbol not in seeds, f"unexpected admission: {symbol}")
        require(universe.classify(row, set()) is None, f"classification differs: {symbol}")
        sampled_rows.append({k: row.get(k) for k in universe.DIRECTORY_FIELDS})
        if symbol in {"BKHA", "EGHA", "HCMA"}:
            copied = dict(row, industry="Blank Checks")
            controls[symbol] = universe.classify(copied, set())
            require(controls[symbol] == "blank check company", "counterfactual classification differs")
    checked(artifact.read_bytes(), ZIP_SHA, "artifact after investigation")
    checked(directory.read_bytes(), DIRECTORY_SHA, "directory after investigation")
    return {
        "integrity": "PASS", "conservation_and_selection_replay": "PASS",
        "artifact_entries": len(names), "artifact_inventory": inventory,
        "member_manifest_sha256": hashlib.sha256(manifest.encode()).hexdigest(),
        "data_sha256": DATA_SHA, "record_sha256": RECORD_SHA,
        "directory_gzip_sha256": DIRECTORY_SHA, "directory_canonical_sha256": fingerprint,
        "input_basis": run["input_basis"], "coverage": run["coverage"], "reads": run["reads"],
        "sample_directory_rows": sampled_rows,
        "counterfactual_industry_only_fixture": controls,
        "sample_catalog_entries": len(sample_entries),
        "full_stale_membership_recovery": "BLOCKED",
        "unidentified_stale_members": stale["count"] - len(SAMPLE),
        "provider_cause": "BLOCKED",
        "limit": "Dates and counts are retained observations; original stale frames and HTTP pages are absent. The fixture establishes classifier behavior, not provider behavior.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args(argv)
    socket.socket.connect = no_network
    socket.socket.connect_ex = no_network
    socket.create_connection = no_network
    try:
        result = diagnose(args.artifact, args.directory)
    except (ValueError, OSError) as exc:
        print(json.dumps({"check": "FAIL", "error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
