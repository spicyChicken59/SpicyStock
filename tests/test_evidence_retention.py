"""The evidence archive keeps what a served file names, and makes room before
its capacity check: the cap would otherwise refuse every publication from the
night the archive filled, which the 23 October store reached at 86 of 128 MiB.
"""
import gzip
import hashlib
import json
import os
from pathlib import Path

import pytest

from src import history, pipeline, provenance, record
from tools.make_fixture import run_variant

ROOT = Path(__file__).resolve().parents[1]


def name(tag):
    return hashlib.sha256(tag.encode()).hexdigest()


def archive(docs, *tags, suffix=".json.gz", size=10):
    folder = docs / provenance.OBJECT_DIR
    folder.mkdir(parents=True, exist_ok=True)
    for tag in tags:
        (folder / (name(tag) + suffix)).write_bytes(b"x" * size)
    return folder


def present(docs):
    return {p.name.split(".")[0] for p in (docs / provenance.OBJECT_DIR).iterdir()}


def test_an_object_no_other_file_names_is_removed_and_every_named_one_stays(tmp_path):
    docs = tmp_path / "docs"
    folder = archive(docs, "data", "history", "ledger", "report", "tonight", "inside", "orphan", "upper")
    archive(docs, "png", suffix=".png")
    (docs / "data.json").write_text(json.dumps({"bursts": [{"evidence": {"source": {"sha256": name("data")}}}]}))
    (docs / "history" / "f").mkdir(parents=True)
    (docs / "history" / "f" / "burst-X.json").write_text(json.dumps({"row": name("history")}))
    ledger = docs / "quality-ledger" / "v1"
    ledger.mkdir(parents=True)
    (ledger / "entry.json.gz").write_bytes(gzip.compress(json.dumps({"chart": name("ledger")}).encode(), mtime=0))
    report = docs / "input-truthfulness" / "a" / "b"
    report.mkdir(parents=True)
    (report / "notes.md").write_text(f"read docs/evidence/{name('report')}.json.gz and evidence/{name('png')}.png\n")
    # A name inside a longer hex run is kept: a reference is never missed for its spelling.
    (docs / "reader.json").write_text('"' + "ab" + name("inside") + "cd" + '"')
    # Names are lowercase; an upper-case spelling names nothing.
    (docs / "other.txt").write_text(name("upper").upper())
    # An object does not keep another: the archive itself names nothing.
    (folder / (name("data") + ".json.gz")).write_bytes(gzip.compress(name("orphan").encode().ljust(10)))
    result = provenance.prune_objects(docs, keep={name("tonight"): {}})
    assert present(docs) == {name(t) for t in ("data", "history", "ledger", "report", "tonight", "inside", "png")}
    assert result == {"objects": 7, "bytes": sum(p.stat().st_size for p in folder.iterdir()),
                      "cap": provenance.MAX_ARCHIVE_BYTES, "removed": 2, "removed_bytes": 20}
    assert not (folder / (name("orphan") + ".json.gz")).exists()


def test_unknown_entries_in_the_archive_stay_and_count_against_the_cap(tmp_path):
    docs = tmp_path / "docs"
    folder = archive(docs, "orphan")
    unknown = {"README.md": b"r", "tmpabc123": b"stage", name("plain") + ".json": b"j",
               name("caps").upper() + ".png": b"p"}
    for file, body in unknown.items():
        (folder / file).write_bytes(body)
    (folder / "nested").mkdir()
    (folder / "nested" / (name("deep") + ".json.gz")).write_bytes(b"d")
    result = provenance.prune_objects(docs)
    assert sorted(p.name for p in folder.iterdir()) == sorted([*unknown, "nested"])
    assert (result["objects"], result["removed"], result["removed_bytes"]) == (0, 1, 10)
    assert result["bytes"] == sum(map(len, unknown.values()))


def test_a_missing_archive_is_empty_and_is_not_created(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    assert provenance.prune_objects(docs) == {"objects": 0, "bytes": 0, "cap": provenance.MAX_ARCHIVE_BYTES,
                                              "removed": 0, "removed_bytes": 0}
    assert not (docs / provenance.OBJECT_DIR).exists()


@pytest.mark.parametrize("case", ["file link", "folder link", "not gzip", "truncated gzip",
                                  "file over the bound", "gzip expanding over the bound",
                                  "archive is a file", "archive is a link"])
def test_a_scan_that_cannot_read_everything_removes_nothing(case, tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    folder = archive(docs, "orphan", "named")
    (docs / "data.json").write_text(name("named"))
    outside = tmp_path / "outside.json"
    outside.write_text("{}")
    if case == "file link":
        os.symlink(outside, docs / "linked.json")
        match = "link"
    elif case == "folder link":
        os.symlink(tmp_path, docs / "linked")
        match = "link"
    elif case == "not gzip":
        (docs / "ledger.json.gz").write_bytes(b"not a gzip stream")
        match = "cannot expand"
    elif case == "truncated gzip":
        (docs / "ledger.json.gz").write_bytes(gzip.compress(b"x" * 4096)[:-12])
        match = "cannot expand"
    elif case == "file over the bound":
        monkeypatch.setattr(provenance, "RETENTION_SCAN_BYTES", 16)
        match = "bound"
    elif case == "gzip expanding over the bound":
        (docs / "ledger.json.gz").write_bytes(gzip.compress(b"0" * 4096))
        monkeypatch.setattr(provenance, "RETENTION_SCAN_BYTES", 1024)
        match = "bound"
    else:
        moved = tmp_path / "moved"
        folder.rename(moved)
        if case == "archive is a file":
            (docs / provenance.OBJECT_DIR).write_bytes(b"")
        else:
            os.symlink(moved, docs / provenance.OBJECT_DIR)
        match = "not a directory"
        folder = moved
    before = sorted(p.name for p in folder.iterdir())
    with pytest.raises(ValueError, match=match):
        provenance.prune_objects(docs)
    assert sorted(p.name for p in folder.iterdir()) == before


def test_a_multi_member_gzip_is_read_in_full(tmp_path):
    docs = tmp_path / "docs"
    archive(docs, "first", "second", "orphan")
    (docs / "ledger.json.gz").write_bytes(gzip.compress(name("first").encode()) + gzip.compress(name("second").encode()))
    provenance.prune_objects(docs)
    assert present(docs) == {name("first"), name("second")}


def test_the_largest_file_the_bound_admits_is_read(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    archive(docs, "plain", "packed", "orphan")
    bound = 512
    monkeypatch.setattr(provenance, "RETENTION_SCAN_BYTES", bound)
    # each exactly at the bound: the plain file on disk, the packed one expanded
    (docs / "plain.json").write_bytes(name("plain").encode().ljust(bound))
    (docs / "packed.json.gz").write_bytes(gzip.compress(name("packed").encode().ljust(bound)))
    provenance.prune_objects(docs)
    assert present(docs) == {name("plain"), name("packed")}


def objects_of(fixture="full"):
    out = {}
    for path in (ROOT / "tests/fixtures/provenance/objects").iterdir():
        key = path.name.split(".")[0]
        out[key] = path.read_bytes() if path.suffix == ".png" else json.loads(gzip.decompress(path.read_bytes()))
    return out


def fixture(name="full"):
    return json.loads((ROOT / f"tests/fixtures/page/{name}.json").read_text())


def tonight_bytes(objects, tmp_path):
    probe = tmp_path / "probe"
    provenance.write_objects(objects, probe)
    return sum(p.stat().st_size for p in probe.iterdir())


def test_a_full_archive_makes_room_before_its_capacity_check(tmp_path, monkeypatch):
    data, picks, objects = fixture(), fixture("full-picks"), objects_of()
    docs = tmp_path / "docs"
    archive(docs, "orphan", size=4096)
    archive(docs, "recovery", size=4096)
    (docs / "history").mkdir()
    (docs / "history" / "index.json").write_text(name("recovery"))
    # Tonight plus the object the recovery catalog names fit; the orphan as well would not.
    monkeypatch.setattr(provenance, "MAX_ARCHIVE_BYTES", tonight_bytes(objects, tmp_path) + 4096 + 100)
    result = provenance.publish_bundle(data, picks, docs, objects)
    assert result["removed"] == 1 and result["removed_bytes"] == 4096
    assert present(docs) == set(objects) | {name("recovery")}
    assert provenance.verify(json.loads((docs / "data.json").read_bytes()), objects=docs / provenance.OBJECT_DIR)["status"] == "PASS"


def test_a_scan_refusal_leaves_the_archive_and_the_capacity_check_decides(tmp_path, monkeypatch):
    data, picks, objects = fixture(), fixture("full-picks"), objects_of()
    docs = tmp_path / "docs"
    archive(docs, "orphan", size=4096)
    os.symlink(tmp_path, docs / "linked")
    result = provenance.publish_bundle(data, picks, docs, objects)
    assert result["error"].startswith("ValueError: retention scan refuses the link")
    assert name("orphan") in present(docs) and set(objects) <= present(docs)
    # The same refusal beside an archive with no room still withholds the publication.
    again = tmp_path / "again"
    archive(again, "orphan", size=4096)
    os.symlink(tmp_path, again / "linked")
    (again / "data.json").write_bytes(b"previous data")
    monkeypatch.setattr(provenance, "MAX_ARCHIVE_BYTES", tonight_bytes(objects, tmp_path) + 100)
    with pytest.raises(ValueError, match="capacity"):
        provenance.publish_bundle(data, picks, again, objects)
    assert (again / "data.json").read_bytes() == b"previous data"


def test_the_evening_removes_a_night_once_recovery_no_longer_carries_it(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(pipeline.time, "monotonic", lambda: 100.0)
    docs = tmp_path / "docs"
    run_variant("full", docs)
    first = present(docs)
    run_variant("next", docs)
    kept = present(docs)
    assert first <= kept, "the next night removed what the recovery catalog still names"
    monkeypatch.setattr(history, "DAYS", 0)
    run_variant("revised", docs)   # writes a catalog that no longer carries the first night
    assert kept <= present(docs), "the archive is read before tonight's catalog drops a night"
    caplog.clear()
    with caplog.at_level("INFO", logger="spicystock.pipeline"):
        run_variant("revised", docs)
    gone = kept - present(docs)
    assert gone and gone <= first, "nothing of the first night left once nothing named it"
    named, runs = provenance.named_objects(docs)
    assert not gone & named and not any(g in r for g in gone for r in runs)
    current = json.loads((docs / "data.json").read_bytes())
    picks = record.load(docs)
    assert provenance.verify(current, picks, docs / provenance.OBJECT_DIR, require_picks=True)["status"] == "PASS"
    assert any("Evidence archive:" in r.getMessage() for r in caplog.records)
