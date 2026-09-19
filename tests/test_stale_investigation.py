"""Failure controls for the read-only, pinned evidence diagnostic."""
import hashlib

import pytest

from tools.investigate_stale_inputs import checked, diagnose, git_blob, no_network


def test_checks_original_bytes_and_rejects_reserialization():
    raw = b'{"value": 1}\n'
    expected = hashlib.sha256(raw).hexdigest()
    assert checked(raw, expected, "fixture") == expected
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        checked(b'{"value":1}', expected, "fixture")


def test_incorrect_artifact_rejected_before_zip_parsing_without_writes(tmp_path):
    artifact, directory = tmp_path / "bad.zip", tmp_path / "directory.gz"
    artifact.write_bytes(b"deliberately incorrect artifact")
    directory.write_bytes(b"not inspected until ZIP identity passes")
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(ValueError, match="artifact ZIP: SHA-256 mismatch"):
        diagnose(artifact, directory)
    assert {p: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_git_blob_identity_is_not_plain_sha1():
    assert git_blob(b"hello\n") == "ce013625030ba8dba906f756967f9e9ca394464a"
    assert git_blob(b"hello\n") != hashlib.sha1(b"hello\n").hexdigest()


def test_diagnostic_network_guard():
    with pytest.raises(RuntimeError, match="network disabled"):
        no_network(("example.invalid", 443))
