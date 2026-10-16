"""tools.freeze_validation_cases: the validation study's case files, frozen
byte for byte under docs/historical-validation/ and held to the digests the
study recorded, so the Record view's frozen decisions do not depend on which
records the rolling 21-day archive still carries. The committed copies are
held here by digest alone -- never compared with docs/history, whose contents
depend on the date -- and every refusal is driven on a synthetic study."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools import freeze_validation_cases as fz

ROOT = Path(__file__).resolve().parents[1]
STUDY = json.loads((ROOT / "docs" / fz.STUDY).read_bytes())
RECORD = "a" * 40


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def synthetic(context=b'{"run": {"session": "2026-09-24"}}', evidence=None, commit=None):
    """A two-case study over one record, and the archive bytes it names."""
    evidence = evidence if evidence is not None else {"CRL": b'{"row": {"ticker": "CRL"}}', "IQV": b'{"row": {"ticker": "IQV"}}'}
    cases = [{"ticker": t, "session": "2026-09-24",
              "entry": {"ticker": t, "kind": "burst", "source": RECORD, "path": f"{RECORD}/burst-{t}.json", "sha256": sha(raw)},
              "source": {"record_id": RECORD, "commit": commit, "context_sha256": sha(context)}}
             for t, raw in evidence.items()]
    archive = {f"{RECORD}/record.json": context, **{f"{RECORD}/burst-{t}.json": raw for t, raw in evidence.items()}}
    return {"version": "historical-validation-v1", "cases": cases}, archive


def write_root(tmp_path, study, archive=None):
    docs = tmp_path / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / fz.STUDY).write_bytes(json.dumps(study).encode())
    for rel, raw in (archive or {}).items():
        target = docs / fz.ARCHIVE_DIR / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    return tmp_path


def frozen_bytes(root):
    frozen = root / "docs" / fz.FROZEN_DIR
    return {p.relative_to(frozen).as_posix(): p.read_bytes() for p in frozen.rglob("*") if p.is_file()} if frozen.is_dir() else {}


# -- the committed copies ---------------------------------------------------

def test_the_committed_copies_are_the_studys_bytes_and_nothing_else():
    files = fz.case_files(STUDY)
    assert len(files) == 5 and len({rel.split("/")[0] for rel in files}) == 2
    assert fz.check(ROOT) == []
    committed = frozen_bytes(ROOT)
    assert set(committed) == set(files)
    for rel, meta in files.items():
        assert sha(committed[rel]) == meta["sha256"], rel
    # every case's own context and evidence are among them
    for case in STUDY["cases"]:
        assert case["entry"]["path"] in files and f"{case['entry']['source']}/record.json" in files
        assert files[case["entry"]["path"]]["sha256"] == case["entry"]["sha256"]
        assert files[f"{case['entry']['source']}/record.json"]["sha256"] == case["source"]["context_sha256"]


def test_the_committed_copies_are_what_the_cases_describe():
    """The frozen evidence is the case's own row and the context is the case's
    own session under the rules the study names, so a copy of the right bytes
    under the wrong name could not pass."""
    for case in STUDY["cases"]:
        evidence = json.loads((ROOT / "docs" / fz.FROZEN_DIR / case["entry"]["path"]).read_bytes())
        context = json.loads((ROOT / "docs" / fz.FROZEN_DIR / case["entry"]["source"] / "record.json").read_bytes())
        assert evidence["source"] == case["entry"]["source"] and evidence["row"]["ticker"] == case["ticker"]
        assert context["run"]["session"] == case["session"]
        assert context["app"]["rules_version"] == case["source"]["rules_version"]


def test_the_page_reads_a_case_from_the_frozen_directory_and_never_the_archive():
    """Source-text pins for what the browser suite proves in Chromium: the
    study loader reads both files of a case through studyJSON, which fetches
    historical-validation/ under a required digest; the archive reader is left
    to the recovery search; and the historical suite serves the case records'
    archive directories 404 while it inspects a case."""
    app = (ROOT / "docs" / "app.js").read_text(encoding="utf-8")
    assert "studyJSON(e.source + '/record.json', s.context_sha256), studyJSON(e.path, e.sha256)" in app
    assert "verifiedJSON('historical-validation/' + path, 256 * 1024, digest, STUDY_WORDS)" in app
    assert "publicJSON(e.source" not in app and "publicJSON(e.path" not in app
    study_reader = app[app.index("function studyJSON"):app.index("function studyJSON") + 600]
    assert "/^[a-f0-9]{64}$/.test(digest || '')" in study_reader, "a case file without a digest must not be read"
    suite = (ROOT / "tools" / "historical_cases.mjs").read_text(encoding="utf-8")
    assert "gone from the rolling archive" in suite and "no request to the rolling archive for a case" in suite


# -- the study's shape --------------------------------------------------------

def test_case_files_names_each_file_once_with_its_digest():
    study, archive = synthetic()
    files = fz.case_files(study)
    assert set(files) == set(archive)
    for rel, raw in archive.items():
        assert files[rel]["sha256"] == sha(raw) and files[rel]["commit"] is None
    assert files[f"{RECORD}/burst-CRL.json"]["ticker"] == "CRL"


def mutate(study, change):
    study = copy.deepcopy(study)
    change(study)
    return study


@pytest.mark.parametrize("label,change,message", [
    ("version", lambda s: s.update(version="historical-validation-v2"), "unknown study version"),
    ("no cases", lambda s: s.update(cases=[]), "names no cases"),
    ("cases not a list", lambda s: s.update(cases={}), "names no cases"),
    ("no entry", lambda s: s["cases"][0].pop("entry"), "lacks its entry"),
    ("no ticker", lambda s: s["cases"][0].pop("ticker"), "lacks its entry"),
    ("record id disagrees", lambda s: s["cases"][0]["source"].update(record_id="b" * 40), "disagrees with its source"),
    ("malformed record id", lambda s: (s["cases"][0]["entry"].update(source="A" * 40), s["cases"][0]["source"].update(record_id="A" * 40)), "malformed"),
    ("path in another record", lambda s: s["cases"][0]["entry"].update(path="b" * 40 + "/burst-CRL.json"), "not inside"),
    ("anticipation path", lambda s: s["cases"][0]["entry"].update(path=f"{RECORD}/anticipation-CRL.json"), "not inside"),
    ("path names another ticker", lambda s: s["cases"][0]["entry"].update(path=f"{RECORD}/burst-IQV.json"), "does not name the case's ticker"),
    ("short digest", lambda s: s["cases"][0]["entry"].update(sha256="ab" * 31), "digest is missing or malformed"),
    ("upper-case digest", lambda s: s["cases"][0]["source"].update(context_sha256="AB" * 32), "digest is missing or malformed"),
    ("no context digest", lambda s: s["cases"][0]["source"].pop("context_sha256"), "digest is missing or malformed"),
    ("malformed commit", lambda s: s["cases"][0]["source"].update(commit="main"), "source commit is malformed"),
    ("two context digests for one record", lambda s: s["cases"][1]["source"].update(context_sha256="c" * 64), "two cases name different digests"),
])
def test_a_malformed_study_is_refused_whole(label, change, message):
    study, _ = synthetic()
    with pytest.raises(fz.FreezeError, match=message):
        fz.case_files(mutate(study, change))


# -- freezing -----------------------------------------------------------------

def test_freeze_writes_missing_copies_from_the_archive_and_keeps_them_after(tmp_path):
    study, archive = synthetic()
    root = write_root(tmp_path, study, archive)
    before = (root / "docs" / fz.STUDY).read_bytes()
    assert fz.freeze(root) == {rel: "written" for rel in archive}
    assert frozen_bytes(root) == archive
    assert fz.check(root) == []
    assert fz.freeze(root) == {rel: "kept" for rel in archive}
    assert frozen_bytes(root) == archive
    assert (root / "docs" / fz.STUDY).read_bytes() == before, "the study file is never rewritten"
    assert not list((root / "docs" / fz.FROZEN_DIR).rglob("*.tmp"))


def test_freeze_refuses_an_existing_copy_that_is_not_the_studys_bytes_and_leaves_it(tmp_path):
    study, archive = synthetic()
    root = write_root(tmp_path, study, archive)
    target = root / "docs" / fz.FROZEN_DIR / f"{RECORD}/burst-CRL.json"
    target.parent.mkdir(parents=True)
    target.write_bytes(b'{"row": {"ticker": "CRL", "edited": true}}')
    with pytest.raises(fz.FreezeError, match="not the study's bytes; left in place"):
        fz.freeze(root)
    assert target.read_bytes() == b'{"row": {"ticker": "CRL", "edited": true}}'


def test_freeze_refuses_a_source_whose_bytes_are_not_the_digest_and_writes_nothing(tmp_path):
    study, archive = synthetic()
    archive[f"{RECORD}/burst-IQV.json"] = b'{"row": {"ticker": "IQV", "repriced": true}}'
    root = write_root(tmp_path, study, archive)
    with pytest.raises(fz.FreezeError, match="burst-IQV.json: source bytes are not the study's digest"):
        fz.freeze(root)
    # sorted order wrote CRL before reaching IQV; IQV and nothing after it
    assert set(frozen_bytes(root)) == {f"{RECORD}/burst-CRL.json"}


def test_freeze_refuses_a_source_over_the_archives_file_bound(tmp_path):
    big = b'{"row": {"ticker": "CRL", "pad": "' + b"a" * fz.FILE_BOUND + b'"}}'
    study, archive = synthetic(evidence={"CRL": big})
    root = write_root(tmp_path, study, archive)
    with pytest.raises(fz.FreezeError, match="exceeds the archive's file bound"):
        fz.freeze(root)
    assert f"{RECORD}/burst-CRL.json" not in frozen_bytes(root)
    exact = b'{"row": {"ticker": "CRL", "pad": "' + b"a" * (fz.FILE_BOUND - len(b'{"row": {"ticker": "CRL", "pad": ""}}')) + b'"}}'
    assert len(exact) == fz.FILE_BOUND
    study, archive = synthetic(evidence={"CRL": exact})
    root = write_root(tmp_path / "exact", study, archive)
    assert fz.freeze(root)[f"{RECORD}/burst-CRL.json"] == "written"


def git(root, *args):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"}
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True, env=env).stdout.strip()


def test_freeze_reads_git_at_the_cases_commit_once_the_archive_no_longer_carries_the_record(tmp_path):
    """The archive prunes a record after 21 days; a case whose source names the
    publication commit is read from git at that commit, and one that names
    none is refused rather than guessed."""
    study, archive = synthetic()
    root = write_root(tmp_path, study, archive)
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "the publication")
    commit = git(root, "rev-parse", "HEAD")
    for rel in archive:
        (root / "docs" / fz.ARCHIVE_DIR / rel).unlink()
    with pytest.raises(fz.FreezeError, match="not in the archive and the case names no commit"):
        fz.freeze(root)
    assert frozen_bytes(root) == {}
    for case in study["cases"]:
        case["source"]["commit"] = commit
    (root / "docs" / fz.STUDY).write_bytes(json.dumps(study).encode())
    assert fz.freeze(root) == {rel: "written" for rel in archive}
    assert frozen_bytes(root) == archive
    # a commit that never carried the file is refused by name
    for rel in archive:
        (root / "docs" / fz.FROZEN_DIR / rel).unlink()
    git(root, "rm", "-q", "-r", "docs/history")
    git(root, "commit", "-q", "-m", "pruned")
    for case in study["cases"]:
        case["source"]["commit"] = git(root, "rev-parse", "HEAD")
    (root / "docs" / fz.STUDY).write_bytes(json.dumps(study).encode())
    with pytest.raises(fz.FreezeError, match="not in the archive and not readable at"):
        fz.freeze(root)


# -- checking -----------------------------------------------------------------

def test_check_names_a_missing_copy_a_drifted_copy_and_a_file_the_study_does_not_name(tmp_path):
    study, archive = synthetic()
    root = write_root(tmp_path, study, archive)
    fz.freeze(root)
    frozen = root / "docs" / fz.FROZEN_DIR
    (frozen / f"{RECORD}/burst-CRL.json").unlink()
    (frozen / f"{RECORD}/burst-IQV.json").write_bytes(b'{"row": {"ticker": "IQV"}} ')
    (frozen / f"{RECORD}/notes.json").write_bytes(b"{}")
    (frozen / ("b" * 40)).mkdir()
    (frozen / ("b" * 40) / "record.json").write_bytes(archive[f"{RECORD}/record.json"])
    assert fz.check(root) == [
        f"{fz.FROZEN_DIR}/{RECORD}/burst-CRL.json: missing",
        f"{fz.FROZEN_DIR}/{RECORD}/burst-IQV.json: not the study's bytes",
        f"{fz.FROZEN_DIR}/{RECORD}/notes.json: not named by the study",
        f"{fz.FROZEN_DIR}/{'b' * 40}/record.json: not named by the study",
    ]


def test_check_refuses_a_malformed_study_rather_than_passing_an_empty_directory(tmp_path):
    study, _ = synthetic()
    study["cases"][0]["entry"]["sha256"] = "nope"
    root = write_root(tmp_path, study)
    with pytest.raises(fz.FreezeError):
        fz.check(root)
    with pytest.raises(fz.FreezeError, match=fz.STUDY):
        fz.check(tmp_path / "nowhere")


# -- the command line ----------------------------------------------------------

def test_the_command_line_writes_checks_and_exits_two_on_a_problem_or_a_refusal(tmp_path, capsys):
    study, archive = synthetic()
    root = write_root(tmp_path, study, archive)
    assert fz.main(["--root", str(root)]) == 0
    out = capsys.readouterr().out
    assert out.splitlines() == [f"written {fz.FROZEN_DIR}/{rel}" for rel in sorted(archive)]
    assert fz.main(["--check", "--root", str(root)]) == 0
    assert capsys.readouterr().out.strip() == "3 frozen case files current"
    (root / "docs" / fz.FROZEN_DIR / f"{RECORD}/record.json").write_bytes(b"{}")
    assert fz.main(["--check", "--root", str(root)]) == 2
    assert capsys.readouterr().out.strip() == f"{fz.FROZEN_DIR}/{RECORD}/record.json: not the study's bytes"
    assert fz.main(["--root", str(root)]) == 2
    assert capsys.readouterr().err.startswith("refused: ")
    (root / "docs" / fz.STUDY).write_bytes(b"not json")
    assert fz.main(["--check", "--root", str(root)]) == 2
    assert capsys.readouterr().err.startswith(f"refused: docs/{fz.STUDY}:")


def test_the_check_over_the_checkout_needs_only_the_standard_library():
    result = subprocess.run([sys.executable, "-I", "-S", str(ROOT / "tools" / "freeze_validation_cases.py"), "--check"],
                            capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "5 frozen case files current"
