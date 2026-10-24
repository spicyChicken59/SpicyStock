"""The evidence archive keeps what a served file names, and makes room before
its capacity check: the cap would otherwise refuse every publication from the
night the archive filled. On 23 October it held 86.2 MB of its 134.2 MB
(128 MiB) and grew about 3 MB a publication.
"""
import gzip
import hashlib
import json
import os
from pathlib import Path

import logging

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
    # named like objects, named by nothing, and not regular files: they stay
    os.symlink(tmp_path / "nowhere.png", folder / (name("link") + ".png"))
    (folder / (name("folder") + ".json.gz")).mkdir()
    result = provenance.prune_objects(docs)
    assert sorted(p.name for p in folder.iterdir()) == sorted(
        [*unknown, "nested", name("link") + ".png", name("folder") + ".json.gz"])
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
                                  "file one byte over the bound", "gzip expanding one byte over the bound",
                                  "gzip members over the bound together", "not a regular file",
                                  "folder that cannot be listed", "archive is a file", "archive is a link"])
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
    elif case == "file one byte over the bound":
        (docs / "plain.json").write_bytes(b" " * 1025)
        monkeypatch.setattr(provenance, "RETENTION_SCAN_BYTES", 1024)
        match = "bound"
    elif case == "gzip expanding one byte over the bound":
        (docs / "ledger.json.gz").write_bytes(gzip.compress(b" " * 1025))
        monkeypatch.setattr(provenance, "RETENTION_SCAN_BYTES", 1024)
        match = "bound"
    elif case == "gzip members over the bound together":
        (docs / "ledger.json.gz").write_bytes(gzip.compress(b" " * 600) + gzip.compress(b" " * 600))
        monkeypatch.setattr(provenance, "RETENTION_SCAN_BYTES", 1024)
        match = "bound"
    elif case == "not a regular file":
        os.mkfifo(docs / "pipe.json")
        match = "not a regular file"
    elif case == "folder that cannot be listed":
        (docs / "history" / "rec").mkdir(parents=True)
        (docs / "history" / "rec" / "burst-X.json").write_text(name("orphan"))
        real = os.scandir
        def scandir(path="."):
            if Path(path) == docs / "history" / "rec":
                raise PermissionError(13, "Permission denied", str(path))
            return real(path)
        monkeypatch.setattr(os, "scandir", scandir)
        match = "cannot list"
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


def test_any_gz_file_is_read_expanded_not_only_json(tmp_path):
    docs = tmp_path / "docs"
    archive(docs, "table", "orphan")
    (docs / "candidates.csv.gz").write_bytes(gzip.compress(f"ticker,chart\nCRL,{name('table')}\n".encode()))
    provenance.prune_objects(docs)
    assert present(docs) == {name("table")}


def test_a_failed_removal_stops_there_and_says_how_far_it_got(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    archive(docs, "a", "b", "c", "named")
    (docs / "data.json").write_text(name("named"))
    real, calls = Path.unlink, []
    def unlink(self, missing_ok=False):
        calls.append(self.name)
        if len(calls) == 2:
            raise PermissionError(1, "Operation not permitted", str(self))
        return real(self, missing_ok)
    monkeypatch.setattr(Path, "unlink", unlink)
    result = provenance.prune_objects(docs)
    assert result["removed"] == 1 and result["removed_bytes"] == 10
    assert result["error"].startswith("PermissionError")
    assert len(present(docs)) == 3 and name("named") in present(docs)
    assert (result["objects"], result["bytes"]) == (3, 30)


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


def test_every_frozen_copy_is_its_own_name():
    """The tests read these through provenance._object(), which refuses a
    changed byte; this holds the ones a test happens not to read as well."""
    frozen = ROOT / "tests/fixtures/retained-evidence"
    files = [p for p in frozen.iterdir() if p.name != "README.md"]
    assert len(files) == 497
    for path in files:
        key, _, suffix = path.name.partition(".")
        assert suffix in ("json.gz", "png"), path.name
        provenance._object(frozen, key, binary=suffix == "png")


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


def test_an_unreadable_file_leaves_the_archive_and_still_publishes(tmp_path, monkeypatch):
    data, picks, objects = fixture(), fixture("full-picks"), objects_of()
    docs = tmp_path / "docs"
    archive(docs, "orphan", size=4096)
    (docs / "notes.json").write_text("{}")
    real = Path.read_bytes
    def read_bytes(self):
        if self.name == "notes.json":
            raise PermissionError(13, "Permission denied", str(self))
        return real(self)
    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    result = provenance.publish_bundle(data, picks, docs, objects)
    assert result["error"].startswith("PermissionError") and result["removed"] == 0
    assert name("orphan") in present(docs) and set(objects) <= present(docs)
    assert json.loads(real(docs / "data.json"))["run"] == data["run"]


@pytest.mark.parametrize("retention, level, words", [
    ({"objects": 3, "bytes": 81, "cap": 100, "removed": 2, "removed_bytes": 20}, logging.WARNING, "Evidence archive: 3 objects, 81 of 100"),
    ({"objects": 3, "bytes": 80, "cap": 100, "removed": 2, "removed_bytes": 20}, logging.INFO, "Evidence archive: 3 objects, 80 of 100"),
    ({"error": "ValueError: retention scan refuses the link x", "removed": 0, "removed_bytes": 0},
     logging.WARNING, "Evidence archive left as it was (ValueError: retention scan refuses the link x)"),
    ({"objects": 3, "bytes": 30, "cap": 100, "removed": 1, "removed_bytes": 10, "error": "PermissionError: no"},
     logging.WARNING, "Evidence retention removed 1 objects (10 bytes) and stopped at an error (PermissionError: no)"),
])
def test_the_run_log_says_what_was_left_what_went_and_warns_near_the_cap(retention, level, words, caplog):
    with caplog.at_level(logging.INFO, logger="spicystock.pipeline"):
        pipeline.log_retention(retention)
    first = caplog.records[0]
    assert (first.levelno, first.getMessage().startswith(words)) == (level, True), first.getMessage()


def test_an_evening_whose_scan_refuses_still_publishes_and_says_so(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(pipeline.time, "monotonic", lambda: 100.0)
    docs = tmp_path / "docs"
    run_variant("full", docs)
    first = present(docs)
    os.symlink(tmp_path, docs / "linked")
    with caplog.at_level(logging.INFO, logger="spicystock.pipeline"):
        run_variant("next", docs)
    assert json.loads((docs / "data.json").read_bytes())["run"]["session"] != fixture()["run"]["session"]
    assert first <= present(docs)
    assert any(r.levelno == logging.WARNING and "Evidence archive left as it was (ValueError: retention scan "
               "refuses the link" in r.getMessage() for r in caplog.records)


def test_the_evening_removes_a_night_once_recovery_no_longer_carries_it(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(pipeline.time, "monotonic", lambda: 100.0)
    docs = tmp_path / "docs"
    run_variant("full", docs)
    first = present(docs)
    run_variant("next", docs)
    run_variant("revised", docs)
    # Two publications later the record names none of the first night's frames;
    # only the recovery catalog does, and they stay.
    current = json.loads((docs / "data.json").read_bytes())
    only_catalog = {o for o in first if o not in json.dumps(current) and o not in (docs / "reader.json").read_text()}
    assert only_catalog and only_catalog <= present(docs), "the recovery catalog's own names were removed"
    monkeypatch.setattr(history, "DAYS", 0)
    run_variant("revised", docs)   # writes a catalog that no longer carries the first night
    assert only_catalog <= present(docs), "the archive is read before tonight's catalog drops a night"
    caplog.clear()
    with caplog.at_level("INFO", logger="spicystock.pipeline"):
        run_variant("revised", docs)
    assert not only_catalog & present(docs), "the first night stayed after nothing named it"
    named, runs = provenance.named_objects(docs)
    tonight = json.loads((docs / "data.json").read_bytes())
    unnamed = {o for o in present(docs) if o not in named and not any(o in r for r in runs)}
    assert not unnamed, "an object nothing names was left behind"
    picks = record.load(docs)
    assert provenance.verify(tonight, picks, docs / provenance.OBJECT_DIR, require_picks=True)["status"] == "PASS"
    assert any("Evidence archive:" in r.getMessage() for r in caplog.records)
