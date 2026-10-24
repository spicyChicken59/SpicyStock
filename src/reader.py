"""Lossless browser projection of a complete canonical publication.

Derivation is pure: source bytes, recommendation receipts and historical
observations are never changed. Transport hashes bind exact UTF-8 bytes.
Immutable observation objects retain a bounded old-tab grace window; past the
archive's capacity, the oldest owned objects inside it give way before a
publication is refused. Only objects tracked by this transport's ownership
manifest are pruned; canonical records, histories, and unrelated evidence are
never deleted.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date, timedelta
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import tempfile


VERSION = 1
READER_FILE = "reader.json"
OBSERVATION_DIR = "reader-observations"
# The canonical record, which the browser never downloads: above the record
# the scan-ready population makes when every scan-ready stock bursts beside a
# full observation window (42,926,403 bytes built from 22 October's record,
# tests/test_publication_ceiling.py), and under the 50 MiB above which a push
# is warned (100 MiB is refused) -- GitHub's documentation, read as search
# excerpts on 24 October 2026; docs.github.com does not resolve from the sandbox.
MAX_PUBLICATION_BYTES = 48 * 1024 * 1024
# reader.json, the file the browser does download: its own bound, which a
# night reaches first whenever its observations are under 16 MiB (27,351,450
# bytes at that design point).
MAX_READER_BYTES = 32 * 1024 * 1024
MAX_OBSERVATION_BYTES = 32 * 1024 * 1024
MAX_SIDECARS = 84
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
RETENTION_FILE = f"{OBSERVATION_DIR}/retention.json"
RETENTION_DAYS = 21
MAX_RETENTION_BYTES = 64 * 1024
HEX = re.compile(r"[a-f0-9]{64}\Z")
RETENTION_WARN_FRACTION = 0.8  # of the cap, after tonight's removals: the run log warns
PUBLICATION_WARN_FRACTION = 0.8  # of MAX_PUBLICATION_BYTES and of MAX_READER_BYTES: the run log warns past it

log = logging.getLogger("spicystock.reader")


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
    reader_raw, observations_raw = _project(canonical_raw)
    _reader_bound(reader_raw)
    return reader_raw, observations_raw


def _reader_bound(reader_raw):
    if len(reader_raw) > MAX_READER_BYTES:
        raise ValueError(f"reader projection is {len(reader_raw)} bytes, "
                         f"over its {MAX_READER_BYTES}-byte bound")


def _project(canonical_raw):
    """The projection before its own bound is asked: the canonical record's
    bound and the observations' are held here, the reader's by the caller."""
    if isinstance(canonical_raw, bytes) and len(canonical_raw) > MAX_PUBLICATION_BYTES:
        raise ValueError(f"canonical publication is {len(canonical_raw)} bytes, "
                         f"over its {MAX_PUBLICATION_BYTES}-byte bound")
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
    return _encode(envelope), observations_raw


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


def _level(size, bound):
    return (logging.ERROR if size > bound else
            logging.WARNING if size > bound * PUBLICATION_WARN_FRACTION else logging.INFO)


def _over(after_delivery):
    return ("; over its bound, so this write is refused and the record first installed stays"
            if after_delivery else "; over its bound, so the night is refused before anything is installed")


def log_publication(size: int, data, *, after_delivery: bool = False) -> None:
    """State the canonical record's bytes against its bound; never raises.

    Called twice a night: as the record is first staged (past the bound
    `derive()` refuses the night before anything is installed) and as the
    restamp after delivery writes it again (past the bound that write is
    refused and the record first installed stays). The size line is written
    even when the record's counts cannot be read."""
    name = "Canonical record after delivery" if after_delivery else "Canonical record"
    try:
        bound = MAX_PUBLICATION_BYTES
        over = size > bound
        level = _level(size, bound)
        try:
            bursts = len(data["bursts"])
            observations = len(_encode(data["observations"]))
            counts = f", with {bursts} {'burst' if bursts == 1 else 'bursts'} and {observations} bytes of observations"
        except Exception as exc:  # noqa: BLE001 -- the size is still stated
            counts = f", its burst and observation counts unreadable ({type(exc).__name__})"
        tail = _over(after_delivery) if over else ""
        log.log(level, "%s: %d of %d bytes%s%s.", name, size, bound, counts, tail)
    except Exception as exc:  # noqa: BLE001 -- a log line never fails the night
        log.warning("%s could not be measured (%s).", name, type(exc).__name__)


def log_projection(size: int, *, after_delivery: bool = False) -> None:
    """State reader.json, the file the browser downloads, against its own
    bound; never raises. Called as each projection is made, before that bound
    is asked, so a refused one is stated too."""
    name = "Reader projection after delivery" if after_delivery else "Reader projection"
    try:
        bound = MAX_READER_BYTES
        log.log(_level(size, bound), "%s: %d of %d bytes%s.", name, size, bound,
                _over(after_delivery) if size > bound else "")
    except Exception as exc:  # noqa: BLE001 -- a log line never fails the night
        log.warning("%s could not be measured (%s).", name, type(exc).__name__)


def stage_assets(stage: Path, *, after_delivery: bool = False) -> dict:
    """Prepare companions beside the already serialized canonical record."""
    stage = Path(stage)
    reader_raw, observations_raw = _project((stage / "data.json").read_bytes())
    log_projection(len(reader_raw), after_delivery=after_delivery)
    _reader_bound(reader_raw)
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
        _require(len(previous["objects"]) <= MAX_SIDECARS + 2, "reader retention manifest exceeds bound")
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
    superseded = False
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
        superseded = True
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
    # A prior cleanup may have removed files before its manifest rename failed,
    # expired ones or ones the capacity chose inside their grace. Retire every
    # owned entry whose file is already gone before growing the index; only
    # tonight's object may be absent here, since it is written after this plan.
    absent = {sha for sha in objects
              if sha != ref["sha256"] and not (archive / (sha + ".json")).exists()}
    for sha in absent:
        del objects[sha]
    expired -= absent
    raw = _regular(stage / ref["path"], MAX_OBSERVATION_BYTES)
    if target.exists() or target.is_symlink():
        _require(_regular(target, MAX_OBSERVATION_BYTES) == raw,
                 "existing reader observation object differs; publication withheld")
    additions = 0 if target.exists() else 1
    added_bytes = 0 if not additions else len(raw)
    object_files = [p for p in files if p.name != "retention.json"]
    retained = [p for p in object_files if p not in removable]

    def fits():
        return (len(retained) + additions <= MAX_SIDECARS
                and sum(path.stat().st_size for path in retained) + added_bytes <= MAX_ARCHIVE_BYTES)

    # Past the capacity, an old tab's copy gives way before tonight's
    # publication does: the owned objects inside their grace leave oldest
    # first, never the object served now or the one it replaces, and never a
    # file whose bytes are not the object the manifest owns.
    protected = {ref["sha256"]} | ({old_ref["sha256"]} if superseded else set())
    evicted = []
    for sha in sorted((sha for sha in objects if sha not in expired and sha not in protected),
                      key=lambda sha: (objects[sha]["last_session"], sha)):
        if fits():
            break
        path = archive / (sha + ".json")
        body = _regular(path, MAX_OBSERVATION_BYTES)
        _require(_hash(body) == sha and len(body) == objects[sha]["bytes"],
                 "reader object ownership differs; nothing was removed")
        removable.append(path)
        retained.remove(path)
        evicted.append(sha)
    expired |= set(evicted)
    _require(fits(), "reader observation archive capacity exceeded; explicit retention decision required")

    def working_set_fits():
        return (len(object_files) + additions <= MAX_SIDECARS + 1
                and sum(path.stat().st_size for path in object_files) + added_bytes
                <= MAX_ARCHIVE_BYTES + MAX_OBSERVATION_BYTES)

    # One new object may coexist with tonight's planned removals until the
    # fixed files commit. Removals wait for that commit unless the working set
    # is already past its bound, from a cleanup that failed on an earlier
    # night or a file the archive does not own: then the planned removals,
    # verified above, go first, so one failure is not every later night's
    # refusal, and a rollback keeps only what had not gone yet. A cleanup that
    # fails again leaves the bound to refuse.
    if not working_set_fits():
        try:
            for path in removable:
                path.unlink()
        except OSError:
            pass
        object_files = [p for p in object_files if p.exists()]
    _require(working_set_fits(), "reader retention cleanup is required before another publication")
    index = {"schema_version": VERSION, "as_of": as_of.isoformat(), "objects": objects}
    # Kept entries fit the cap; the rest are tonight's planned removals, each a
    # file the archive held, which the working set holds to one past the cap,
    # beside tonight's object. A failed cleanup leaves this index as written.
    _require(len(objects) - len(expired) <= MAX_SIDECARS and len(objects) <= MAX_SIDECARS + 2,
             "reader retention ownership exceeds bound; explicit retention decision required")
    index_raw = _encode(index)
    _require(len(index_raw) <= MAX_RETENTION_BYTES, "reader retention manifest bytes exceed bound")
    _write(stage / RETENTION_FILE, index_raw)
    return index, expired, additions, evicted


def _retain_object(stage, docs, ref, additions):
    if additions:
        archive = docs / OBSERVATION_DIR
        archive.mkdir(parents=True, exist_ok=True)
        os.replace(stage / ref["path"], docs / ref["path"])


def _prune_owned(stage, docs, index, expired):
    """Prune owned cache files after successful fixed publication: expired
    ones, and any the capacity required inside their grace.

    Cleanup failure keeps ownership metadata for retry and is announced. The
    already verified publication remains usable; working-set bounds prevent
    repeated cleanup failures from growing the transport archive indefinitely.
    """
    if not expired:
        return True
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
        print("Reader retention cleanup failed; verified publication is intact and owned cleanup "
              "will retry at the next publication.")
        return False
    return True


def install_publication(stage: Path, docs: Path, names: tuple[str, ...] | list[str]) -> None:
    """Retain immutable bytes, then install reader and the verified fixed files.

    Canonical data is installed last. Ordinary rename failures roll fixed files
    back byte-for-byte. Process death between renames remains the existing
    multi-file publication limitation. Only owned transport objects are
    removed, after successful installation: those outside the grace window,
    and the oldest inside it when the capacity requires.
    """
    stage, docs = Path(stage), Path(docs)
    _require(list(names) in (["data.json"], ["picks.json", "data.json"], []),
             "unsupported reader publication installation")
    canonical_raw = _regular(stage / "data.json", MAX_PUBLICATION_BYTES)
    reader_raw = _regular(stage / READER_FILE, MAX_READER_BYTES)
    ref = parse_reader(reader_raw)["retained_observations"]
    observations_raw = _regular(stage / ref["path"], MAX_OBSERVATION_BYTES)
    validate_bundle(canonical_raw, reader_raw, observations_raw)
    index, expired, additions, evicted = _retention(stage, docs, ref, canonical_raw)
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
        # Tonight's object came in with this install and no restored manifest
        # owns it: it leaves too, or it would sit in the archive as nobody's.
        if additions:
            try:
                (docs / ref["path"]).unlink()
            except OSError:
                pass
        raise
    cleaned = _prune_owned(stage, docs, index, expired)
    _log_archive(docs, evicted, index, cleaned)


def _log_archive(docs, evicted, index, cleaned):
    """What the run log says of the archive once tonight's removals are done.
    It describes an installed publication and never fails it."""
    try:
        files = [path for path in (docs / OBSERVATION_DIR).iterdir()
                 if path.name != "retention.json" and path.is_file() and not path.is_symlink()]
        held = sum(path.stat().st_size for path in files)
    except OSError as exc:
        log.warning("Reader observation archive could not be measured (%s).", exc)
        return
    if evicted:
        one = len(evicted) == 1
        what = (f"{len(evicted)} {'object' if one else 'objects'} inside {'its' if one else 'their'} "
                f"{RETENTION_DAYS}-day grace")
        cap = f"the cap of {MAX_SIDECARS} objects and {MAX_ARCHIVE_BYTES} bytes"
        removed = sum(index["objects"][sha]["bytes"] for sha in evicted)
        left = [sha for sha in evicted if (docs / OBSERVATION_DIR / (sha + ".json")).exists()]
        if not left:
            log.warning("Reader observation archive: %s %s removed, oldest first, so the publication "
                        "fits %s (%d bytes; git keeps %s).%s", what, "was" if one else "were", cap,
                        removed, "it" if one else "them",
                        "" if cleaned else " The manifest update failed; the next publication retires "
                        + ("it." if one else "them."))
        else:
            log.warning("Reader observation archive: %s %s chosen for removal, oldest first, to fit %s "
                        "(%d bytes); %d could not be removed and the next publication retries.",
                        what, "was" if one else "were", cap, removed, len(left))
    full = (held > MAX_ARCHIVE_BYTES * RETENTION_WARN_FRACTION
            or len(files) > MAX_SIDECARS * RETENTION_WARN_FRACTION)
    log.log(logging.WARNING if full else logging.INFO,
            "Reader observation archive: %d of %d objects, %d of %d bytes.",
            len(files), MAX_SIDECARS, held, MAX_ARCHIVE_BYTES)


def write_publication(data: dict, docs: Path) -> None:
    """Serialize a final/restamped canonical record and publish its companions.

    Past the canonical or the reader bound the projection is refused before
    anything is installed, so the record already installed stays."""
    from src import report
    docs = Path(docs)
    docs.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".reader-publication-", dir=docs) as tmp:
        stage = Path(tmp)
        report.write(data, stage / "data.json")
        log_publication((stage / "data.json").stat().st_size, data, after_delivery=True)
        stage_assets(stage, after_delivery=True)
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
