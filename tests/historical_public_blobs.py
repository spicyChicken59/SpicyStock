"""Exact public source bytes used by offline historical API/Git doubles.

These three captured blobs belong to the prior releases under test. Reading
today's workflow or scanner config would silently change that synthetic past.
The production contracts still independently assert their original hashes.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "tests/fixtures/historical-public-blobs"
FROZEN = {".github/workflows/tests.yml": "tests-pr97.yml",
          ".gitleaks.toml": "gitleaks-native6.toml"}


def public_git_bytes(path, *, scanner_before=False):
    name = "gitleaks-before-native6.toml" if scanner_before else FROZEN.get(path)
    if scanner_before:
        assert path == ".gitleaks.toml"
    # API/Git doubles use LF blobs even in a Windows working checkout.
    raw = ((CAPTURE / name) if name else (ROOT / path)).read_bytes().replace(b"\r\n", b"\n")
    if name:
        source = json.loads((CAPTURE / "sources.json").read_bytes())[name]
        assert source["path"] == path
        assert hashlib.sha256(raw).hexdigest() == source["sha256"]
    return raw
