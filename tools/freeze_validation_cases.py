"""Freeze the validation study's case files outside the rolling public archive.

``docs/historical-validation.json`` names three historical wait cases, each by
the public archive record that carried it (``entry.source``, a 40-hex record
id), its evidence file (``entry.path``) and the SHA-256 of both (``entry.sha256``
and ``source.context_sha256``). The Record view inspects a case by reading those
two files. The public archive under ``docs/history`` keeps ``history.DAYS``
calendar days and deletes a record's directory when it leaves the window, so a
case read from the archive stops being inspectable on a date the study never
chose: the 24 September record leaves with the 16 October 2026 publication, the
25 September record with the next.

This tool copies each case's context and evidence, byte for byte, to
``docs/historical-validation/<record>/...`` -- the same relative paths, a
directory nothing prunes -- and holds every copy to the study's own digest. It
never overwrites different bytes, never writes a file the study does not name,
and refuses a source whose bytes are not the digest's. The study file itself is
not changed: the frozen copies are what the page reads for its cases, and the
digests the study recorded are what verify them.

Run: ``python tools/freeze_validation_cases.py`` writes what is missing;
``--check`` holds the committed copies (exit 2 on a missing file, a drifted
byte or a file the study does not name). Sources: ``docs/history`` when the
archive still carries the record, else git at the case's ``source.commit``.
The committed copies were written on 16 October 2026 from the archive, which
still carried both records that morning; the study's cases name no commit, so
a copy lost after the prune would need the publication commit written into
its case before ``freeze`` could read it from git. ``--check`` needs no source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STUDY = "historical-validation.json"
FROZEN_DIR = "historical-validation"
ARCHIVE_DIR = "history"
RECORD_ID = re.compile(r"^[a-f0-9]{40}$")
EVIDENCE_PATH = re.compile(r"^[a-f0-9]{40}/burst-[A-Z0-9][A-Z0-9.-]{0,15}\.json$")
DIGEST = re.compile(r"^[a-f0-9]{64}$")
COMMIT = re.compile(r"^[a-f0-9]{40}$")
FILE_BOUND = 256 * 1024  # history.publish()'s own bound on a context or evidence file


class FreezeError(ValueError):
    """A study, source or frozen copy the tool refuses to act on."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def case_files(study: dict) -> dict[str, dict]:
    """Every file the study's cases read, by relative path, with its digest.

    A context file two cases share must carry one digest; a case naming a path
    outside its own record, a malformed id, path or digest is refused whole.
    """
    if not isinstance(study, dict) or study.get("version") != "historical-validation-v1":
        raise FreezeError("unknown study version")
    cases = study.get("cases")
    if not isinstance(cases, list) or not cases:
        raise FreezeError("the study names no cases")
    files: dict[str, dict] = {}

    def claim(path: str, digest: str, commit: str | None, ticker: str) -> None:
        if path in files and files[path]["sha256"] != digest:
            raise FreezeError(f"{path}: two cases name different digests")
        files.setdefault(path, {"sha256": digest, "commit": commit, "ticker": ticker})

    for case in cases:
        entry, source = case.get("entry"), case.get("source")
        ticker = case.get("ticker")
        if not isinstance(entry, dict) or not isinstance(source, dict) or not isinstance(ticker, str):
            raise FreezeError("a case lacks its entry, source or ticker")
        record = entry.get("source")
        path = entry.get("path")
        if not isinstance(record, str) or not RECORD_ID.match(record) or record != source.get("record_id"):
            raise FreezeError(f"{ticker}: the case's record id is malformed or disagrees with its source")
        if not isinstance(path, str) or not EVIDENCE_PATH.match(path) or not path.startswith(record + "/"):
            raise FreezeError(f"{ticker}: evidence path is not inside the case's own record")
        if path != f"{record}/burst-{ticker}.json":
            raise FreezeError(f"{ticker}: evidence path does not name the case's ticker")
        for digest in (entry.get("sha256"), source.get("context_sha256")):
            if not isinstance(digest, str) or not DIGEST.match(digest):
                raise FreezeError(f"{ticker}: a digest is missing or malformed")
        commit = source.get("commit")
        if commit is not None and (not isinstance(commit, str) or not COMMIT.match(commit)):
            raise FreezeError(f"{ticker}: the source commit is malformed")
        claim(path, entry["sha256"], commit, ticker)
        claim(f"{record}/record.json", source["context_sha256"], commit, ticker)
    return files


def load_study(root: Path) -> dict:
    try:
        return json.loads((root / "docs" / STUDY).read_bytes())
    except (OSError, ValueError) as exc:
        raise FreezeError(f"docs/{STUDY}: {exc}") from exc


def source_bytes(root: Path, rel: str, commit: str | None) -> bytes:
    """The published bytes of one archive file: the checkout's archive while it
    still carries the record, else git at the case's publication commit."""
    archived = root / "docs" / ARCHIVE_DIR / rel
    if archived.is_symlink():
        raise FreezeError(f"{rel}: the archive entry is a symbolic link, not a file")
    if archived.exists() and not archived.is_file():
        raise FreezeError(f"{rel}: the archive entry is not a regular file")
    if archived.is_file():
        return archived.read_bytes()
    if commit is None:
        raise FreezeError(f"{rel}: not in the archive and the case names no commit")
    try:
        return subprocess.run(["git", "-C", str(root), "show", f"{commit}:docs/{ARCHIVE_DIR}/{rel}"],
                              check=True, capture_output=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise FreezeError(f"{rel}: not in the archive and not readable at {commit[:8]}") from exc


def freeze(root: Path) -> dict[str, str]:
    """Write every missing frozen copy from a digest-verified source.

    Returns ``{path: "written" | "kept"}``. An existing copy whose bytes differ
    from the study's digest is refused, never replaced.
    """
    files = case_files(load_study(root))
    outcome: dict[str, str] = {}
    frozen = root / "docs" / FROZEN_DIR
    if frozen.is_symlink():
        raise FreezeError(f"{FROZEN_DIR}: the frozen directory is a symbolic link; nothing written")
    for rel, meta in sorted(files.items()):
        target = frozen / rel
        # A copy is a regular file in a directory nothing prunes. A link into
        # the archive would pass every byte comparison today and dangle the
        # night the archive drops the record, so a link is never a copy.
        if target.parent.is_symlink() or target.is_symlink():
            raise FreezeError(f"{FROZEN_DIR}/{rel}: a symbolic link, not a copy; left in place")
        if target.exists():
            if not target.is_file():
                raise FreezeError(f"{FROZEN_DIR}/{rel}: not a regular file; left in place")
            if sha256(target.read_bytes()) != meta["sha256"]:
                raise FreezeError(f"{FROZEN_DIR}/{rel}: an existing copy is not the study's bytes; left in place")
            outcome[rel] = "kept"
            continue
        raw = source_bytes(root, rel, meta["commit"])
        if len(raw) > FILE_BOUND:
            raise FreezeError(f"{rel}: source exceeds the archive's file bound")
        if sha256(raw) != meta["sha256"]:
            raise FreezeError(f"{rel}: source bytes are not the study's digest; nothing written")
        # The bytes land under a temporary name and are renamed into place, so
        # a copy either exists whole or not at all; a write that fails on the
        # way is a refusal by name and leaves no temporary file behind.
        temp = target.with_suffix(".tmp")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            temp.write_bytes(raw)
            temp.replace(target)
        except OSError as exc:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass
            raise FreezeError(f"{FROZEN_DIR}/{rel}: could not be written ({exc.strerror or exc}); nothing written") from exc
        outcome[rel] = "written"
    return outcome


def check(root: Path) -> list[str]:
    """Problems with the committed copies: a case file missing or not the
    study's bytes, or a file under the frozen directory the study does not name."""
    files = case_files(load_study(root))
    problems: list[str] = []
    frozen = root / "docs" / FROZEN_DIR
    if frozen.is_symlink():
        return [f"{FROZEN_DIR}: the frozen directory is a symbolic link"]
    for rel, meta in sorted(files.items()):
        target = frozen / rel
        if target.parent.is_symlink() or target.is_symlink():
            problems.append(f"{FROZEN_DIR}/{rel}: a symbolic link, not a copy")
        elif not target.is_file():
            problems.append(f"{FROZEN_DIR}/{rel}: missing")
        else:
            try:
                raw = target.read_bytes()
            except OSError as exc:
                problems.append(f"{FROZEN_DIR}/{rel}: unreadable ({exc.strerror or exc})")
                continue
            if sha256(raw) != meta["sha256"]:
                problems.append(f"{FROZEN_DIR}/{rel}: not the study's bytes")
    # Everything else under the directory is named: a file the study does not
    # name, and any link at all, whether to a file, to a directory or to
    # nothing. The walk never follows a link.
    if frozen.is_dir():
        for dirpath, dirnames, filenames in os.walk(frozen, followlinks=False):
            here = Path(dirpath)
            for name in sorted(dirnames):
                if (here / name).is_symlink():
                    rel = (here / name).relative_to(frozen).as_posix()
                    problems.append(f"{FROZEN_DIR}/{rel}: a symbolic link, not a directory")
            for name in sorted(filenames):
                path = here / name
                rel = path.relative_to(frozen).as_posix()
                if path.is_symlink():
                    if rel not in files:
                        problems.append(f"{FROZEN_DIR}/{rel}: a symbolic link, not a copy")
                elif rel not in files:
                    problems.append(f"{FROZEN_DIR}/{rel}: not named by the study")
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="freeze the validation study's case files outside the rolling archive")
    parser.add_argument("--check", action="store_true", help="hold the committed copies to the study's digests; write nothing")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        if args.check:
            problems = check(args.root)
            if problems:
                for problem in problems:
                    print(problem)
                return 2
            print(f"{len(case_files(load_study(args.root)))} frozen case files current")
            return 0
        outcome = freeze(args.root)
        for rel, what in outcome.items():
            print(f"{what} {FROZEN_DIR}/{rel}")
        return 0
    except FreezeError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
