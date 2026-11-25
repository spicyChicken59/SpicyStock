"""Freeze three records made under version 1 of the go-live gate.

Version 1 (19 to 24 November 2026) asked four conditions; the gate is
version 2 now and nothing writes version 1. A record made under version 1 is
still read, and ``src/go_live.py`` holds it by version 1's own validator
(``_faults_v1()``). The tests that keep that validator honest need real
version-1 records that no later change can move, so this script copies the
parts of three of them that the validator reads into ``v1-records.json``:

* the publication of the 20 November 2026 session (``docs/data.json``),
* the publication of the 23 November 2026 session (``docs/data.json``),
* the ``next`` page fixture as the version-1 pipeline last wrote it, whose
  ``settled_forward_plans`` count is one.

Each entry is ``{"source": {"commit", "path", "sha256"}, "record": {...}}``.
``source.sha256`` is the SHA-256 of the whole file's bytes at that commit;
``record`` keeps the file's ``rules`` whole (the validator digests them), and
of ``run`` and ``scorecard`` only what the validator reads: the session, the
gate's block and the count of settled plans.

Run it with no argument to write the file, or with ``--check`` to compare
the committed file with what git holds. Both read the three commits out of
git by their whole ids; the tests themselves read only the committed JSON.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().with_name("v1-records.json")
#: (name, whole commit id, path): the three version-1 records, oldest publication first
SOURCES = (
    ("2026-11-20", "f969d2f7cdbb8a613bae0d2ad3d22e3a34eb5979", "docs/data.json"),
    ("2026-11-23", "f82801e750e54ca7cc9a4fbb054cba9e6022877b", "docs/data.json"),
    ("next", "a00d3a30d2da7a5d9b1427c80cbc62d00a43d7ac", "tests/fixtures/page/next.json"),
)
ABOUT = ("Three records made under version 1 of the go-live gate, frozen as git holds them. "
         "tests/fixtures/go-live/build_v1.py writes this file and nothing else may edit it.")


def read_at(commit: str, path: str) -> bytes:
    """The file's bytes at that commit, or a ValueError that names what is missing."""
    done = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT, capture_output=True)
    if done.returncode != 0:
        raise ValueError(f"git cannot read {path} at {commit}: {done.stderr.decode(errors='replace').strip()}")
    return done.stdout


def extract(name: str, commit: str, path: str) -> dict:
    """The parts of one version-1 record that version 1's validator reads."""
    raw = read_at(commit, path)
    data = json.loads(raw)
    record = {"rules": data["rules"],
              "run": {"session": data["run"]["session"], "go_live": data["run"]["go_live"]},
              "scorecard": {"settled": data["scorecard"]["settled"]}}
    if data["rules"]["go_live"]["version"] != 1 or record["run"]["go_live"]["version"] != 1:
        raise ValueError(f"{path} at {commit} was not made under version 1 of the gate")
    return {"name": name, "source": {"commit": commit, "path": path, "sha256": hashlib.sha256(raw).hexdigest()},
            "record": record}


def build() -> bytes:
    document = {"about": ABOUT, "records": [extract(*source) for source in SOURCES]}
    return (json.dumps(document, indent=1) + "\n").encode()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="compare the committed file with git, and write nothing")
    args = parser.parse_args(argv)
    try:
        wanted = build()
    except ValueError as exc:
        print(f"go-live v1 records: {exc}", file=sys.stderr)
        return 1
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_bytes() != wanted:
            print("go-live v1 records: v1-records.json is not what git holds; run build_v1.py", file=sys.stderr)
            return 1
        print(f"go-live v1 records: {len(SOURCES)} records current")
        return 0
    OUTPUT.write_bytes(wanted)
    print(f"go-live v1 records: wrote {len(SOURCES)} records, {len(wanted)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
