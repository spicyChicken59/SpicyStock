"""Lossless browser projection of a complete canonical publication.

Derivation is pure: source bytes, recommendation receipts and historical
observations are never changed. Transport hashes bind exact UTF-8 bytes.
Immutable observation objects retain a bounded old-tab grace window. Only
expired objects tracked by this transport's ownership manifest are pruned;
canonical records, histories, and unrelated evidence are never deleted.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile


VERSION = 1
READER_FILE = "reader.json"
OBSERVATION_DIR = "reader-observations"
MAX_PUBLICATION_BYTES = 32 * 1024 * 1024
MAX_READER_BYTES = 32 * 1024 * 1024
MAX_OBSERVATION_BYTES = 32 * 1024 * 1024
MAX_SIDECARS = 84
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
RETENTION_FILE = f"{OBSERVATION_DIR}/retention.json"
RETENTION_DAYS = 21
MAX_RETENTION_BYTES = 64 * 1024
HEX = re.compile(r"[a-f0-9]{64}\Z")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _decode(raw, maximum):
    _require(isinstance(raw, bytes) and 0 < len(raw) <= maximum,
             "reader transport bytes exceed bound")

    def invalid(_):
        raise ValueError("nonfinite reader JSON")

    return json.loads(raw, parse_constant=invalid)


def _encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _data(value):
    _require(isinstance(value, dict) and type(value.get("schema_version")) is int
             and value["schema_version"] == 2 and isinstance(value.get("run"), dict)
             and isinstance(value.get("bursts"), list), "unsupported reader publication")
    observations = value.get("observations")
    _require(isinstance(observations, dict) and isinstance(observations.get("symbols"), dict),
             "reader publication observations are invalid")
    _require("signals" not in observations or isinstance(observations["signals"], dict),
             "reader publication signals are invalid")


def derive(canonical_raw: bytes) -> tuple[bytes, bytes]:
    """Return compact reader bytes and the complete original observation bytes.

    Source schema/provenance validation remains the canonical publication
    boundary's responsibility. Nothing is derived from provider frames or a
    browser selection. All non-observation values and their ordering survive.
    """
    data = _decode(canonical_raw, MAX_PUBLICATION_BYTES)
    _data(data)
    observations_raw = _encode(data["observations"])
    _require(len(observations_raw) <= MAX_OBSERVATION_BYTES,
             "reader observation bytes exceed bound")
    projected = deepcopy(data)
    projected["observations"]["symbols"] = {}
    if "signals" in projected["observations"]:
        projected["observations"]["signals"] = {}
    observations_sha = _hash(observations_raw)
    envelope = {"schema_version": VERSION, "projection_version": VERSION,
                "canonical": {"sha256": _hash(canonical_raw), "bytes": len(canonical_raw)},
                "data": projected,
                "retained_observations": {"sha256": observations_sha,
                    "bytes": len(observations_raw),
                    "path": f"{OBSERVATION_DIR}/{observations_sha}.json"}}
    reader_raw = _encode(envelope)
    _require(len(reader_raw) <= MAX_READER_BYTES, "reader projection bytes exceed bound")
    return reader_raw, observations_raw


def binding(canonical_raw: bytes) -> dict:
    """Exact reader identity calculated from the canonical source bytes only."""
    return {"reader_projection_version": VERSION,
            "reader_sha256": _hash(derive(canonical_raw)[0])}


def parse_reader(reader_raw: bytes) -> dict:
    """Validate a descriptor before using its strictly local sidecar path."""
    envelope = _decode(reader_raw, MAX_READER_BYTES)
    _require(isinstance(envelope, dict) and set(envelope) == {
        "schema_version", "projection_version", "canonical", "data", "retained_observations"},
        "reader envelope fields differ")
    for key in ("schema_version", "projection_version"):
        _require(type(envelope[key]) is int and envelope[key] == VERSION,
                 "unsupported reader envelope version")
    for key, fields, maximum in (("canonical", {"sha256", "bytes"}, MAX_PUBLICATION_BYTES),
                                 ("retained_observations", {"sha256", "bytes", "path"}, MAX_OBSERVATION_BYTES)):
        ref = envelope[key]
        _require(isinstance(ref, dict) and set(ref) == fields, "reader reference fields differ")
        _require(isinstance(ref["sha256"], str) and HEX.fullmatch(ref["sha256"]),
                 "invalid reader reference digest")
        _require(type(ref["bytes"]) is int and 0 < ref["bytes"] <= maximum,
                 "invalid reader reference byte bound")
    ref = envelope["retained_observations"]
    _require(ref["path"] == f"{OBSERVATION_DIR}/{ref['sha256']}.json",
             "invalid reader observation path")
    _data(envelope["data"])
    observations = envelope["data"]["observations"]
    _require(observations["symbols"] == {} and observations.get("signals", {}) == {},
             "reader bulk observations were not deferred")
    return envelope


def validate_bundle(canonical_raw: bytes, reader_raw: bytes, observations_raw: bytes) -> dict:
    """Replay exact derivation before publishing any supplied companion bytes."""
    envelope = parse_reader(reader_raw)
    _decode(observations_raw, MAX_OBSERVATION_BYTES)
    expected_reader, expected_observations = derive(canonical_raw)
    _require(reader_raw == expected_reader, "reader projection differs from canonical publication")
    _require(observations_raw == expected_observations,
             "reader observations differ from canonical publication")
    return envelope["retained_observations"]


def _write(path, raw):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def stage_assets(stage: Path) -> dict:
    """Prepare companions beside the already serialized canonical record."""
    stage = Path(stage)
    reader_raw, observations_raw = derive((stage / "data.json").read_bytes())
    ref = parse_reader(reader_raw)["retained_observations"]
    _write(stage / READER_FILE, reader_raw)
    _write(stage / ref["path"], observations_raw)
    return ref


def _regular(path, maximum):
    path = Path(path)
    _require(not path.is_symlink() and path.is_file(), "reader asset must be a regular file")
    with path.open("rb") as handle:
        raw = handle.read(maximum + 1)
    _require(len(raw) <= maximum, "reader asset bytes exceed bound")
    return raw


def _session(value):
    _require(isinstance(value, str), "invalid reader retention session")
    parsed = date.fromisoformat(value)
    _require(parsed.isoformat() == value, "invalid reader retention session")
    return parsed


def _retention(stage, docs, ref, canonical_raw):
    """Plan ownership/grace/capacity before any publication file is replaced."""
    archive = docs / OBSERVATION_DIR
    _require(not archive.is_symlink(), "reader observation archive must not be a symlink")
    if archive.exists():
        _require(archive.is_dir(), "reader observation archive must be a directory")
    session = _session(json.loads(canonical_raw)["run"].get("session"))
    index_path = docs / RETENTION_FILE
    previous = {"schema_version": VERSION, "as_of": session.isoformat(), "objects": {}}
    if index_path.exists() or index_path.is_symlink():
        previous = _decode(_regular(index_path, MAX_RETENTION_BYTES), MAX_RETENTION_BYTES)
        _require(isinstance(previous, dict) and set(previous) == {"schema_version", "as_of", "objects"}
                 and type(previous["schema_version"]) is int and previous["schema_version"] == VERSION
                 and isinstance(previous["objects"], dict), "invalid reader retention manifest")
        _session(previous["as_of"])
        _require(len(previous["objects"]) <= MAX_SIDECARS + 1, "reader retention manifest exceeds bound")
        for sha, entry in previous["objects"].items():
            _require(isinstance(sha, str) and HEX.fullmatch(sha) and isinstance(entry, dict)
                     and set(entry) == {"last_session", "bytes"}
                     and type(entry["bytes"]) is int and 0 < entry["bytes"] <= MAX_OBSERVATION_BYTES,
                     "invalid reader retention ownership")
            _require(_session(entry["last_session"]) <= _session(previous["as_of"]),
                     "reader retention session is ahead of manifest")
    as_of = max(session, _session(previous["as_of"]))
    objects = deepcopy(previous["objects"])
    # The formerly current object's grace begins when it is superseded, even
    # after a publication gap. A currently served old object is never expired.
    current = docs / READER_FILE
    if current.exists() or current.is_symlink():
        current_raw = _regular(current, MAX_READER_BYTES)
        expected_current, expected_old_observations = derive(
            _regular(docs / "data.json", MAX_PUBLICATION_BYTES))
        _require(current_raw == expected_current,
                 "current reader differs from canonical publication; ownership was not changed")
        old_ref = parse_reader(current_raw)["retained_observations"]
        old_path = docs / old_ref["path"]
        if old_path.exists() or old_path.is_symlink():
            old_raw = _regular(old_path, MAX_OBSERVATION_BYTES)
            _require(old_raw == expected_old_observations,
                     "current reader observation object is not verified")
        objects[old_ref["sha256"]] = {"last_session": as_of.isoformat(), "bytes": old_ref["bytes"]}
    objects[ref["sha256"]] = {"last_session": as_of.isoformat(), "bytes": ref["bytes"]}
    cutoff = (as_of - timedelta(days=RETENTION_DAYS)).isoformat()
    expired = {sha for sha, entry in objects.items() if entry["last_session"] < cutoff}
    target = docs / ref["path"]
    files = list(archive.iterdir()) if archive.exists() else []
    for path in files:
        _require(not path.is_symlink() and path.is_file(),
                 "unexpected reader observation archive entry; nothing was removed")
    removable = []
    for sha in expired:
        path = archive / (sha + ".json")
        if path.exists():
            raw = _regular(path, MAX_OBSERVATION_BYTES)
            _require(_hash(raw) == sha and len(raw) == objects[sha]["bytes"],
                     "expired reader object ownership differs; nothing was removed")
            removable.append(path)
    # A prior cleanup may have removed files before its manifest rename failed.
    # Retire only those already absent expired entries before growing the index.
    absent_expired = {sha for sha in expired if not (archive / (sha + ".json")).exists()}
    for sha in absent_expired:
        del objects[sha]
    expired -= absent_expired
    raw = _regular(stage / ref["path"], MAX_OBSERVATION_BYTES)
    if target.exists() or target.is_symlink():
        _require(_regular(target, MAX_OBSERVATION_BYTES) == raw,
                 "existing reader observation object differs; publication withheld")
    additions = 0 if target.exists() else 1
    added_bytes = 0 if not additions else len(raw)
    object_files = [p for p in files if p.name != "retention.json"]
    retained = [p for p in object_files if p not in removable]
    _require(len(retained) + additions <= MAX_SIDECARS
             and sum(path.stat().st_size for path in retained) + added_bytes <= MAX_ARCHIVE_BYTES,
             "reader observation archive capacity exceeded; explicit retention decision required")
    # One new object may coexist with expired objects until the fixed files
    # commit. A failed cleanup cannot grow this working set without bound.
    _require(len(object_files) + additions <= MAX_SIDECARS + 1
             and sum(path.stat().st_size for path in object_files) + added_bytes
             <= MAX_ARCHIVE_BYTES + MAX_OBSERVATION_BYTES,
             "reader retention cleanup is required before another publication")
    index = {"schema_version": VERSION, "as_of": as_of.isoformat(), "objects": objects}
    _require(len(objects) <= MAX_SIDECARS + 1,
             "reader retention ownership exceeds bound; explicit retention decision required")
    index_raw = _encode(index)
    _require(len(index_raw) <= MAX_RETENTION_BYTES, "reader retention manifest bytes exceed bound")
    _write(stage / RETENTION_FILE, index_raw)
    return index, expired, additions


def _retain_object(stage, docs, ref, additions):
    if additions:
        archive = docs / OBSERVATION_DIR
        archive.mkdir(parents=True, exist_ok=True)
        os.replace(stage / ref["path"], docs / ref["path"])


def _prune_owned(stage, docs, index, expired):
    """Prune owned expired cache files after successful fixed publication.

    Cleanup failure keeps ownership metadata for retry and is announced. The
    already verified publication remains usable; working-set bounds prevent
    repeated cleanup failures from growing the transport archive indefinitely.
    """
    if not expired:
        return
    try:
        cleaned = deepcopy(index)
        for sha in expired:
            path = docs / OBSERVATION_DIR / (sha + ".json")
            if path.exists():
                path.unlink()
            del cleaned["objects"][sha]
        _write(stage / RETENTION_FILE, _encode(cleaned))
        os.replace(stage / RETENTION_FILE, docs / RETENTION_FILE)
    except OSError:
        print("Reader retention cleanup failed; verified publication is intact and owned cleanup will retry.")


def install_publication(stage: Path, docs: Path, names: tuple[str, ...] | list[str]) -> None:
    """Retain immutable bytes, then install reader and the verified fixed files.

    Canonical data is installed last. Ordinary rename failures roll fixed files
    back byte-for-byte. Process death between renames remains the existing
    multi-file publication limitation. Only owned expired transport objects
    are removed, after successful installation and outside the grace window.
    """
    stage, docs = Path(stage), Path(docs)
    _require(list(names) in (["data.json"], ["picks.json", "data.json"], []),
             "unsupported reader publication installation")
    canonical_raw = _regular(stage / "data.json", MAX_PUBLICATION_BYTES)
    reader_raw = _regular(stage / READER_FILE, MAX_READER_BYTES)
    ref = parse_reader(reader_raw)["retained_observations"]
    observations_raw = _regular(stage / ref["path"], MAX_OBSERVATION_BYTES)
    validate_bundle(canonical_raw, reader_raw, observations_raw)
    index, expired, additions = _retention(stage, docs, ref, canonical_raw)
    fixed_names = [RETENTION_FILE, READER_FILE, *names]
    previous = {}
    for name in fixed_names:
        target = docs / name
        _require(not target.is_symlink(), "reader publication target must not be a symlink")
        previous[name] = target.read_bytes() if target.exists() else None
    _retain_object(stage, docs, ref, additions)
    installed = []
    try:
        for name in fixed_names:
            os.replace(stage / name, docs / name)
            installed.append(name)
    except OSError:
        for name in reversed(installed):
            if previous[name] is None:
                (docs / name).unlink()
            else:
                _write(stage / name, previous[name])
                os.replace(stage / name, docs / name)
        raise
    _prune_owned(stage, docs, index, expired)


def write_publication(data: dict, docs: Path) -> None:
    """Serialize a final/restamped canonical record and publish its companions."""
    from src import report
    docs = Path(docs)
    docs.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".reader-publication-", dir=docs) as tmp:
        stage = Path(tmp)
        report.write(data, stage / "data.json")
        stage_assets(stage)
        install_publication(stage, docs, ["data.json"])


def check_assets(docs: Path) -> dict:
    """Check exact committed companions; no source or asset is repaired."""
    docs = Path(docs)
    canonical_raw = _regular(docs / "data.json", MAX_PUBLICATION_BYTES)
    reader_raw = _regular(docs / READER_FILE, MAX_READER_BYTES)
    ref = parse_reader(reader_raw)["retained_observations"]
    _require(not (docs / OBSERVATION_DIR).is_symlink(), "reader archive must not be a symlink")
    return validate_bundle(canonical_raw, reader_raw,
                          _regular(docs / ref["path"], MAX_OBSERVATION_BYTES))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs", type=Path, default=Path("docs"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.check:
        check_assets(args.docs)
    else:
        raw = _regular(args.docs / "data.json", MAX_PUBLICATION_BYTES)
        with tempfile.TemporaryDirectory(prefix=".reader-assets-", dir=args.docs) as tmp:
            stage = Path(tmp)
            _write(stage / "data.json", raw)
            stage_assets(stage)
            _require(_regular(args.docs / "data.json", MAX_PUBLICATION_BYTES) == raw,
                     "canonical publication changed while preparing reader assets")
            install_publication(stage, args.docs, [])
    print("Reader companions verified against canonical publication.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
