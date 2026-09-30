"""Ciphertext-only delivery of the existing historical cache, with safe recovery.

The caller verifies runner identity and permission evidence before acquisition.
This module does not grant rights, acquire data, or establish receipt provenance.
Recovery requires execution metadata independently checked against GitHub.
"""
from __future__ import annotations

from datetime import datetime
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import stat
import subprocess
import tarfile
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.historical_acquisition import ASSIGNMENT, encode, exclusive_lock, validate_manifest
from tools import historical_execution_guard as execution_guard
from tools import historical_archive_codec as codec

SCHEMA = "historical-encrypted-receipt-v4"
INDEX_SCHEMA = "historical-private-package-v4"
DELIVERY_ENVELOPE = "historical-delivery-envelope-v1"
PREVIOUS_SCHEMA = "historical-encrypted-receipt-v3"
PREVIOUS_INDEX_SCHEMA = "historical-private-package-v3"
PREVIOUS_COMPATIBILITY_CONTRACT_SHA256 = "61ccac3fc27e9a62ccadee73ec0c069536994fedefd76a272aac129fbd7a484d"
LEGACY_SCHEMA = "historical-encrypted-receipt-v2"
LEGACY_INDEX_SCHEMA = "historical-private-package-v2"
REPOSITORY = "spicyChicken59/SpicyStock"
MAX_ARCHIVE_BYTES = 250 * 1024 ** 2
MAX_CIPHERTEXT_OVERHEAD_BYTES = 1024 ** 2
MAX_CIPHERTEXT_BYTES = MAX_ARCHIVE_BYTES + MAX_CIPHERTEXT_OVERHEAD_BYTES
LEGACY_MAX_ARCHIVE_BYTES = 199 * 1024 ** 2
LEGACY_MAX_CIPHERTEXT_BYTES = 200 * 1024 ** 2
MAX_PLAINTEXT_BYTES = 2 * 1024 ** 3
MAX_MEMBERS = 4096
MAX_INDEX_BYTES = 4 * 1024 ** 2
CIPHERTEXT_NAME = "evidence.tar.zst.age"
LEGACY_CIPHERTEXT_NAME = "evidence.tar.gz.age"
AGE_HEADER = b"age-encryption.org/v1\n"
RECEIPT_NAME = "receipt.json"
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_RECIPIENT = re.compile(r"age1[023456789acdefghjklmnpqrstuvwxyz]{58}\Z")
_LEGACY_EXECUTION_KEYS = {"repository", "repository_id", "assignment_id", "manifest_sha256",
                   "workflow_id", "workflow_path", "recipient_sha256", "run_id",
                   "run_number", "run_attempt", "assignment_phase", "mode", "checkout_sha",
                   "workflow_sha", "implementation_pr", "readiness_comment_id",
                   "recovery_contract_sha256", "status"}
_EXECUTION_KEYS = _LEGACY_EXECUTION_KEYS | {"compatibility_contract_sha256", "release_evidence_sha256"}
_INTERNAL = {"_package/manifest.json", "_package/execution.json", "_package/diagnostics.json"}


class PackageError(RuntimeError):
    """Constant reason codes only; never attach paths, values or subprocess output."""


def _fail(reason):
    raise PackageError(reason)


def _limits(schema):
    # Enlarging the new envelope must never reinterpret an old receipt's caps.
    if schema == SCHEMA:
        return MAX_ARCHIVE_BYTES, MAX_CIPHERTEXT_BYTES
    if schema in (PREVIOUS_SCHEMA, LEGACY_SCHEMA):
        return LEGACY_MAX_ARCHIVE_BYTES, LEGACY_MAX_CIPHERTEXT_BYTES
    _fail("invalid_receipt")


def _ciphertext_size(size, schema, archive_bytes=None):
    _, limit = _limits(schema)
    if type(size) is not int or not 22 < size <= limit:
        _fail("ciphertext_size_limit")
    if schema == SCHEMA and not 0 < size - archive_bytes <= MAX_CIPHERTEXT_OVERHEAD_BYTES:
        _fail("ciphertext_overhead_limit")


def _hash(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def _json(raw):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                _fail("duplicate_json_key")
            out[key] = value
        return out
    try:
        return json.loads(raw, object_pairs_hook=unique)
    except (ValueError, UnicodeError, RecursionError):
        _fail("invalid_package_json")


def _regular(path):
    try:
        info = path.lstat()
    except OSError:
        _fail("missing_package_file")
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        _fail("nonregular_package_file")
    return info


def _private_path(path, *, exists=True):
    path = Path(path).absolute()
    # Inspect unresolved components so resolving a symlink cannot conceal it.
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            _fail("unsafe_storage_path")
        if (part / ".git").exists():
            _fail("storage_inside_git")
    if exists and not path.is_dir():
        _fail("missing_storage_directory")
    if exists and os.name != "nt" and path.stat().st_mode & 0o077:
        _fail("storage_permissions_not_private")
    return path.resolve()


def recipient_fingerprint(recipient):
    """SHA-256 of exactly one native X25519 recipient's ASCII bytes plus LF.

    The standard age executable additionally validates its Bech32 checksum.
    Plugin, SSH, multiple-recipient and passphrase forms are not accepted.
    """
    if not isinstance(recipient, str) or not _RECIPIENT.fullmatch(recipient):
        _fail("invalid_encryption_recipient")
    return hashlib.sha256((recipient + "\n").encode("ascii")).hexdigest()


def _execution(value, *, legacy=False, previous=False):
    keys = _LEGACY_EXECUTION_KEYS if legacy else _EXECUTION_KEYS
    if not isinstance(value, dict) or set(value) not in (keys, keys | {"started_at"}):
        _fail("invalid_execution_metadata")
    try:
        execution_guard.validate_phase_binding(value)
    except (execution_guard.GuardError, OSError, ValueError, TypeError, KeyError):
        _fail("invalid_execution_identity")
    # Reading a PR97 v4 identity does not grant new execution authorization.
    # validate_phase_binding above keeps its old recovery/native-slot pairing;
    # the live guard separately requires the new policy and incident relation.
    allowed = {PREVIOUS_COMPATIBILITY_CONTRACT_SHA256} if previous else {
        execution_guard.COMPATIBILITY_CONTRACT_SHA256,
        execution_guard.PR97_COMPATIBILITY_CONTRACT_SHA256}
    if not legacy and value["compatibility_contract_sha256"] not in allowed:
        _fail("invalid_execution_identity")
    if value["mode"] not in ("rehearsal", "real") or value["status"] not in ("PASS", "FAIL", "BLOCKED", "NOT RUN"):
        _fail("invalid_execution_mode_or_status")
    if "started_at" in value:
        try:
            stamp = datetime.fromisoformat(value["started_at"].replace("Z", "+00:00"))
            if stamp.utcoffset().total_seconds() != 0:
                raise ValueError
        except (ValueError, AttributeError, TypeError):
            _fail("invalid_execution_timestamp")
    return dict(value)


def execution_metadata(record, *, status=None, legacy=False, previous=False):
    """Explicit public projection; guard approval documents remain private."""
    if not isinstance(record, dict):
        _fail("invalid_execution_metadata")
    schema = "historical-execution-v2" if legacy else "historical-execution-v3"
    if record.get("schema") == schema:
        if any(record.get(k) != "PASS" for k in ("status", "readiness_status", "lifetime_status")):
            _fail("execution_guard_not_passed")
        result = {k: record[k] for k in (_LEGACY_EXECUTION_KEYS if legacy else _EXECUTION_KEYS)}
    else:
        result = dict(record)
    if status is not None:
        result["status"] = status
    return _execution(result, legacy=legacy, previous=previous)


def _age_environment():
    # No provider credentials, GitHub tokens, plugin configuration or arbitrary
    # inherited settings reach encryption/decryption subprocesses.
    allowed = {"SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG", "LC_ALL"}
    return {**{k: v for k, v in os.environ.items() if k.upper() in allowed}, "NO_COLOR": "1"}


def _age(age_binary, arguments, output, *, reason, limit=None):
    if limit is None:
        limit = MAX_CIPHERTEXT_BYTES
    binary = Path(age_binary).absolute()
    _regular(binary)
    try:
        with output.open("xb") as stream:
            os.chmod(output, 0o600)
            result = subprocess.run([str(binary), *map(str, arguments)], stdin=subprocess.DEVNULL,
                                    stdout=stream, stderr=subprocess.DEVNULL,
                                    env=_age_environment(), timeout=180, check=False)
            stream.flush()
            os.fsync(stream.fileno())
        if result.returncode != 0 or output.stat().st_size > limit:
            _fail(reason)
    except (OSError, subprocess.SubprocessError):
        _fail(reason)


def validate_recipient(age_binary, recipient, private_scratch):
    """Run age's recipient parser before provider credentials enter a step."""
    fingerprint = recipient_fingerprint(recipient)
    root = _private_path(private_scratch)
    with tempfile.TemporaryDirectory(prefix=".recipient-", dir=root) as name:
        temp = Path(name)
        plain = temp / "empty"
        plain.write_bytes(b"")
        _age(age_binary, ["--encrypt", "--recipient", recipient, plain], temp / "probe.age",
             reason="invalid_encryption_recipient")
    return fingerprint


def _allowed(manifest):
    return {"ledger.sqlite3", "execution-diagnostics.json",
            "reconciliation-2026-09-24.json", "reconciliation-2026-09-25.json",
            *(q["id"] + "-manifest.json" for q in manifest["queries"])}


def _ledger(root, manifest_sha256):
    ledger = root / "ledger.sqlite3"
    _regular(ledger)
    try:
        db = sqlite3.connect(ledger.as_uri() + "?mode=ro&immutable=1", uri=True)
        try:
            if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                _fail("invalid_recovered_ledger")
            row = db.execute("SELECT value FROM metadata WHERE name='manifest_sha256'").fetchone()
            if row != (manifest_sha256,):
                _fail("ledger_manifest_mismatch")
            # Reserved and failed attempts remain evidence, never a fresh budget.
            db.execute("SELECT id,reservation,retained,status,body_hash FROM attempts LIMIT 0")
        finally:
            db.close()
    except sqlite3.Error:
        _fail("invalid_recovered_ledger")


def _sources(storage, manifest, identity):
    allowed = _allowed(manifest)
    files = {}
    for path in storage.iterdir():
        if path.name == "pages":
            if path.is_symlink() or not path.is_dir() or (hasattr(path, "is_junction") and path.is_junction()):
                _fail("unsafe_pages_directory")
            for page in path.iterdir():
                info = _regular(page)
                if not re.fullmatch(r"[0-9a-f]{64}\.json", page.name) or _hash(page) != page.stem:
                    _fail("raw_page_hash_mismatch")
                files["pages/" + page.name] = (page, info.st_size)
        elif path.name == "acquisition.lock":
            _regular(path)  # Process locks are not persistent evidence.
        elif path.name in allowed:
            files[path.name] = (path, _regular(path).st_size)
        else:
            _fail("unapproved_plaintext_file")
    _ledger(storage, identity)
    if len(files) + 4 > MAX_MEMBERS or sum(size for _, size in files.values()) > MAX_PLAINTEXT_BYTES:
        _fail("package_size_or_member_limit")
    return files


def _entry(tar, name, stream, size):
    info = tarfile.TarInfo(name)
    info.size, info.mode, info.mtime = size, 0o600, 0
    tar.addfile(info, stream)


def _write_archive(archive, index_raw, index, sources, extras):
    """Write one checksummed frame and report actual bytes before the cap gate."""
    sizes = [len(index_raw), *(e["bytes"] for e in index["members"])]
    unpadded = sum(512 + ((size + 511) // 512) * 512 for size in sizes) + 1024
    tar_bytes = ((unpadded + tarfile.RECORDSIZE - 1) // tarfile.RECORDSIZE) * tarfile.RECORDSIZE
    try:
        with archive.open("xb") as out:
            os.chmod(archive, 0o600)
            with codec.compressor(out, tar_bytes) as compressed:
                with tarfile.open(fileobj=compressed, mode="w|", format=tarfile.USTAR_FORMAT) as tar:
                    _entry(tar, "_package/index.json", io.BytesIO(index_raw), len(index_raw))
                    for entry in index["members"]:
                        name = entry["path"]
                        if name in extras:
                            _entry(tar, name, io.BytesIO(extras[name]), entry["bytes"])
                        else:
                            with sources[name][0].open("rb") as source:
                                _entry(tar, name, source, entry["bytes"])
    except codec.CodecError:
        _fail("archive_codec_refused")
    return {"archive_format": codec.FORMAT, "archive_bytes": archive.stat().st_size,
            "archive_sha256": _hash(archive), "tar_archive_bytes": tar_bytes,
            "index_bytes": len(index_raw), "expanded_payload_bytes": sum(sizes),
            "indexed_member_count": len(index["members"])}


def package_evidence(storage, manifest, delivery, *, age_binary, recipient, execution, diagnostics=None):
    """Package a closed cache, including partial failures; return a public receipt.

    Delivery must be a new directory. Only its exact ciphertext and receipt are
    uploadable. Windows ACLs must already be restricted by the operator/runner.
    """
    identity = validate_manifest(manifest)
    execution = _execution(execution)
    fingerprint = recipient_fingerprint(recipient)
    if execution["manifest_sha256"] != identity or execution["recipient_sha256"] != fingerprint:
        _fail("package_execution_binding_mismatch")
    storage = _private_path(storage)
    delivery = _private_path(delivery, exists=False)
    if delivery.exists() or storage == delivery or storage in delivery.parents or delivery in storage.parents:
        _fail("unsafe_delivery_directory")
    _private_path(delivery.parent)
    if (storage / "acquisition.lock").exists() or (storage / "acquisition.lock").is_symlink():
        _regular(storage / "acquisition.lock")
    with exclusive_lock(storage / "acquisition.lock"):
        sources = _sources(storage, manifest, identity)
        extras = {"_package/manifest.json": encode(manifest),
                  "_package/execution.json": encode(execution),
                  "_package/diagnostics.json": encode(diagnostics or {})}
        if any(len(raw) > MAX_INDEX_BYTES for raw in extras.values()):
            _fail("package_metadata_too_large")
        members = [{"path": name, "bytes": size, "sha256": _hash(path)}
                   for name, (path, size) in sorted(sources.items())]
        members.extend({"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
                       for name, raw in sorted(extras.items()))
        index = {"schema": INDEX_SCHEMA, "archive_format": codec.FORMAT,
                 "delivery_envelope": DELIVERY_ENVELOPE,
                 "manifest_sha256": identity, "execution": execution,
                 "recipient_sha256": fingerprint, "members": sorted(members, key=lambda x: x["path"])}
        index_raw = encode(index)
        if len(index_raw) > MAX_INDEX_BYTES or sum(e["bytes"] for e in members) + len(index_raw) > MAX_PLAINTEXT_BYTES:
            _fail("package_index_too_large")
        with tempfile.TemporaryDirectory(prefix=".package-", dir=storage) as name:
            temp = Path(name)
            archive = temp / "evidence.tar.zst"
            archive_metrics = _write_archive(archive, index_raw, index, sources, extras)
            if archive.stat().st_size > MAX_ARCHIVE_BYTES:
                _fail("package_size_or_member_limit")
            # Recheck after reading: concurrent edits must not create an index
            # which describes different raw bytes than the delivered archive.
            if any(_hash(sources[e["path"]][0]) != e["sha256"] for e in members if e["path"] in sources):
                _fail("package_source_changed")
            ciphertext = temp / "ciphertext.part"
            _age(age_binary, ["--encrypt", "--recipient", recipient, archive], ciphertext,
                 reason="encryption_failed",
                 limit=min(MAX_CIPHERTEXT_BYTES, archive.stat().st_size + MAX_CIPHERTEXT_OVERHEAD_BYTES))
            _ciphertext_size(ciphertext.stat().st_size, SCHEMA, archive.stat().st_size)
            with ciphertext.open("rb") as stream:
                if stream.read(len(AGE_HEADER)) != AGE_HEADER:
                    _fail("invalid_ciphertext_header")
            receipt = {"schema": SCHEMA, **execution, "manifest_sha256": identity,
                       "delivery_envelope": DELIVERY_ENVELOPE,
                       "archive_format": codec.FORMAT, "ciphertext_name": CIPHERTEXT_NAME,
                       "archive_bytes": archive_metrics["archive_bytes"],
                       "archive_sha256": archive_metrics["archive_sha256"],
                       "recipient_sha256": fingerprint, "ciphertext_sha256": _hash(ciphertext),
                       "ciphertext_bytes": ciphertext.stat().st_size,
                       "artifact_name": "historical-evidence-" + "-".join(str(execution[k]) for k in ("run_id", "run_attempt", "mode"))}
            delivery.mkdir(mode=0o700)
            try:
                shutil.copyfile(ciphertext, delivery / CIPHERTEXT_NAME)
                os.chmod(delivery / CIPHERTEXT_NAME, 0o600)
                (delivery / RECEIPT_NAME).write_bytes(encode(receipt))
                os.chmod(delivery / RECEIPT_NAME, 0o600)
                validate_delivery(delivery, receipt)
            except BaseException:
                shutil.rmtree(delivery)
                raise
    return receipt


def _receipt(receipt, expected_execution=None):
    if not isinstance(receipt, dict):
        _fail("invalid_receipt")
    archive_limit, _ = _limits(receipt.get("schema"))
    legacy = receipt.get("schema") == LEGACY_SCHEMA
    previous = receipt.get("schema") == PREVIOUS_SCHEMA
    current = receipt.get("schema") == SCHEMA
    execution_keys = (_LEGACY_EXECUTION_KEYS if legacy else _EXECUTION_KEYS) | ({"started_at"} if "started_at" in receipt else set())
    extra = {"schema", "manifest_sha256", "recipient_sha256", "ciphertext_sha256", "ciphertext_bytes", "artifact_name"}
    if not legacy:
        extra |= {"archive_format", "ciphertext_name", "archive_bytes", "archive_sha256"}
    if current:
        extra.add("delivery_envelope")
    if set(receipt) != execution_keys | extra:
        _fail("invalid_receipt")
    if current and receipt["delivery_envelope"] != DELIVERY_ENVELOPE:
        _fail("invalid_delivery_envelope")
    if not legacy and (receipt["archive_format"] != codec.FORMAT or receipt["ciphertext_name"] != CIPHERTEXT_NAME or
                       type(receipt["archive_bytes"]) is not int or not 0 < receipt["archive_bytes"] <= archive_limit or
                       not isinstance(receipt["archive_sha256"], str) or not _HEX.fullmatch(receipt["archive_sha256"])):
        _fail("invalid_archive_receipt")
    execution = _execution({k: receipt[k] for k in execution_keys}, legacy=legacy, previous=previous)
    if expected_execution is not None and execution != _execution(expected_execution, legacy=legacy, previous=previous):
        _fail("receipt_execution_mismatch")
    if any(not isinstance(receipt[k], str) or not _HEX.fullmatch(receipt[k])
           for k in ("manifest_sha256", "recipient_sha256", "ciphertext_sha256")):
        _fail("invalid_receipt")
    _ciphertext_size(receipt["ciphertext_bytes"], receipt["schema"], receipt.get("archive_bytes"))
    if receipt["artifact_name"] != "historical-evidence-" + "-".join(str(execution[k]) for k in ("run_id", "run_attempt", "mode")):
        _fail("invalid_artifact_identity")
    return execution


def validate_delivery(delivery, receipt):
    """Fail closed immediately before uploading these two exact files."""
    delivery = _private_path(delivery)
    _receipt(receipt)
    cipher_name = LEGACY_CIPHERTEXT_NAME if receipt["schema"] == LEGACY_SCHEMA else CIPHERTEXT_NAME
    if {p.name for p in delivery.iterdir()} != {cipher_name, RECEIPT_NAME}:
        _fail("plaintext_or_unapproved_delivery_file")
    ciphertext = delivery / cipher_name
    if _regular(ciphertext).st_size != receipt["ciphertext_bytes"] or _hash(ciphertext) != receipt["ciphertext_sha256"]:
        _fail("ciphertext_receipt_mismatch")
    _regular(delivery / RECEIPT_NAME)
    if _json((delivery / RECEIPT_NAME).read_bytes()) != receipt:
        _fail("receipt_file_mismatch")
    with ciphertext.open("rb") as stream:
        if stream.read(len(AGE_HEADER)) != AGE_HEADER:
            _fail("invalid_ciphertext_header")
    return receipt


def _tar_header(stream):
    raw = stream.read(512)
    if raw == bytes(512):
        return None
    if len(raw) != 512 or raw[257:265] != b"ustar\x0000":
        _fail("invalid_package_tar_header")
    # Parse checksum and numeric fields with the stdlib, without tarfile's
    # automatic PAX/GNU extension processing or its unbounded extension reads.
    info = tarfile.TarInfo.frombuf(raw, "utf-8", "strict")
    if info.type != tarfile.REGTYPE or info.linkname or info.size < 0:
        _fail("unsafe_archive_member")
    return info


def _tar_padding(stream, size):
    length = (-size) % 512
    if stream.read(length) != bytes(length):
        _fail("invalid_package_tar_padding")


def _unpack(archive, destination, manifest, receipt, execution):
    allowed = _allowed(manifest) | _INTERNAL
    legacy = receipt.get("schema") == LEGACY_SCHEMA
    current = receipt.get("schema") == SCHEMA
    index_schema = {LEGACY_SCHEMA: LEGACY_INDEX_SCHEMA, PREVIOUS_SCHEMA: PREVIOUS_INDEX_SCHEMA,
                    SCHEMA: INDEX_SCHEMA}.get(receipt.get("schema"))
    if index_schema is None:
        _fail("invalid_receipt")
    archive_format = codec.LEGACY_FORMAT if legacy else receipt.get("archive_format")
    # Payload cap includes the index. Tar framing has a separate finite bound,
    # so zero padding, headers and decoder expansion cannot escape accounting.
    max_tar_bytes = MAX_PLAINTEXT_BYTES + MAX_MEMBERS * 1024 + tarfile.RECORDSIZE
    seen = set()
    try:
        with tempfile.TemporaryDirectory(prefix=".tar-", dir=destination.parent) as temporary:
            spool = Path(temporary) / "decoded.tar"
            codec.decode(archive, spool, archive_format, max_decoded=max_tar_bytes)
            with spool.open("rb") as stream:
                first = _tar_header(stream)
                if first is None or first.name != "_package/index.json" or first.size > MAX_INDEX_BYTES:
                    _fail("invalid_package_index")
                index_raw = stream.read(first.size)
                if len(index_raw) != first.size:
                    _fail("invalid_package_index")
                _tar_padding(stream, first.size)
                index = _json(index_raw)
                index_keys = {"schema", "manifest_sha256", "execution", "recipient_sha256", "members"}
                if not legacy:
                    index_keys.add("archive_format")
                if current:
                    index_keys.add("delivery_envelope")
                if (not isinstance(index, dict) or set(index) != index_keys or
                    index["schema"] != index_schema or
                    (current and index["delivery_envelope"] != receipt.get("delivery_envelope")) or
                    (current and index["delivery_envelope"] != DELIVERY_ENVELOPE) or
                    (not legacy and index["archive_format"] != archive_format) or
                    index["manifest_sha256"] != receipt["manifest_sha256"] or
                    index["execution"] != execution or index["recipient_sha256"] != receipt["recipient_sha256"] or
                    not isinstance(index["members"], list) or len(index["members"]) >= MAX_MEMBERS):
                    _fail("package_identity_mismatch")
                expected, total = {}, first.size
                for entry in index["members"]:
                    if (not isinstance(entry, dict) or set(entry) != {"path", "bytes", "sha256"} or
                        not isinstance(entry["path"], str) or entry["path"] in expected or
                        type(entry["bytes"]) is not int or not 0 <= entry["bytes"] <= MAX_PLAINTEXT_BYTES or
                        not isinstance(entry["sha256"], str) or not _HEX.fullmatch(entry["sha256"])):
                        _fail("invalid_package_index")
                    name = entry["path"]
                    normalized = PurePosixPath(name)
                    if (str(normalized) != name or normalized.is_absolute() or ".." in normalized.parts or
                        "\\" in name or (name not in allowed and not re.fullmatch(r"pages/[0-9a-f]{64}\.json", name))):
                        _fail("unsafe_archive_member")
                    if name in _INTERNAL and entry["bytes"] > MAX_INDEX_BYTES:
                        _fail("package_metadata_too_large")
                    total += entry["bytes"]
                    if total > MAX_PLAINTEXT_BYTES:
                        _fail("package_size_or_member_limit")
                    expected[name] = entry
                if not {"ledger.sqlite3", *_INTERNAL} <= set(expected):
                    _fail("missing_recovery_member")
                while True:
                    member = _tar_header(stream)
                    if member is None:
                        # Exactly the USTAR two end blocks and zero record pad;
                        # no ignored extra tar archive, record or arbitrary tail.
                        if stream.read(512) != bytes(512):
                            _fail("invalid_package_tar_end")
                        padding = (-stream.tell()) % tarfile.RECORDSIZE
                        if stream.read(padding) != bytes(padding) or stream.read(1):
                            _fail("invalid_package_tar_end")
                        break
                    name = member.name
                    if name in seen or name not in expected:
                        _fail("unsafe_archive_member")
                    seen.add(name)
                    if member.size != expected[name]["bytes"]:
                        _fail("package_size_or_member_limit")
                    target = destination.joinpath(*PurePosixPath(name).parts)
                    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                    hasher, remaining = hashlib.sha256(), member.size
                    with target.open("xb") as output:
                        os.chmod(target, 0o600)
                        while remaining:
                            block = stream.read(min(1024 * 1024, remaining))
                            if not block:
                                _fail("truncated_package_member")
                            hasher.update(block)
                            output.write(block)
                            remaining -= len(block)
                    _tar_padding(stream, member.size)
                    if hasher.hexdigest() != expected[name]["sha256"]:
                        _fail("package_member_hash_mismatch")
                    if name.startswith("pages/") and target.stem != hasher.hexdigest():
                        _fail("raw_page_hash_mismatch")
                if seen != set(expected):
                    _fail("missing_recovery_member")
    except (codec.CodecError, tarfile.TarError, OSError, EOFError, KeyError, TypeError, AttributeError, UnicodeError):
        _fail("invalid_package_archive")
    if _json((destination / "_package/manifest.json").read_bytes()) != manifest:
        _fail("package_manifest_mismatch")
    if _json((destination / "_package/execution.json").read_bytes()) != execution:
        _fail("package_execution_mismatch")
    _json((destination / "_package/diagnostics.json").read_bytes())
    _ledger(destination, receipt["manifest_sha256"])
    (destination / "_package/index.json").write_bytes(index_raw)
    os.chmod(destination / "_package/index.json", 0o600)
    return index


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate-recipient")
    validate.add_argument("--policy", type=Path, required=True)
    validate.add_argument("--age", type=Path, required=True)
    validate.add_argument("--scratch", type=Path)
    pack = commands.add_parser("package")
    for name in ("storage", "manifest", "execution", "policy", "age", "delivery"):
        pack.add_argument("--" + name, type=Path, required=True)
    recover = commands.add_parser("recover")
    for name in ("cipher", "receipt", "identity", "age", "destination", "expected-execution"):
        recover.add_argument("--" + name, type=Path, required=True)
    recover.add_argument("--manifest", type=Path, default=ROOT / "docs/input-truthfulness/2026-09-28-historical-input-evidence/acquisition-manifest.json")
    args = parser.parse_args(argv)
    try:
        if args.command in ("validate-recipient", "package"):
            policy = _json(args.policy.read_bytes())
            recipient = policy["recipient"]
            if recipient_fingerprint(recipient) != policy["recipient_sha256"]:
                _fail("recipient_policy_mismatch")
        if args.command == "validate-recipient":
            if args.scratch:
                validate_recipient(args.age, recipient, args.scratch)
            else:
                with tempfile.TemporaryDirectory(prefix="historical-recipient-", dir=os.environ.get("RUNNER_TEMP")) as name:
                    validate_recipient(args.age, recipient, Path(name))
        elif args.command == "package":
            manifest = _json(args.manifest.read_bytes())
            guard = _json(args.execution.read_bytes())
            if (guard.get("schema") != "historical-execution-v3" or
                guard.get("manifest_sha256") != validate_manifest(manifest) or
                guard.get("recipient_sha256") != policy["recipient_sha256"]):
                _fail("package_guard_identity_mismatch")
            diagnostics = _json((args.storage / "execution-diagnostics.json").read_bytes())
            metadata = execution_metadata(guard, status=diagnostics["status"])
            if (diagnostics.get("schema") != "historical-execution-diagnostics-v3" or
                    diagnostics.get("execution_binding") != execution_guard.validate_phase_binding(metadata)):
                _fail("package_retained_execution_mismatch")
            package_evidence(args.storage, manifest, args.delivery, age_binary=args.age,
                             recipient=recipient, execution=metadata,
                             diagnostics={"execution_guard": guard})
        else:
            receipt = _json(args.receipt.read_bytes())
            expected = _json(args.expected_execution.read_bytes())
            if expected.get("schema") in ("historical-execution-v2", "historical-execution-v3"):
                if (expected.get("manifest_sha256") != receipt.get("manifest_sha256") or
                    expected.get("recipient_sha256") != receipt.get("recipient_sha256")):
                    _fail("recovery_guard_identity_mismatch")
                expected = execution_metadata(expected, status=receipt.get("status"),
                                              legacy=receipt.get("schema") == LEGACY_SCHEMA,
                                              previous=receipt.get("schema") == PREVIOUS_SCHEMA)
            recover_package(args.cipher, receipt, args.destination, age_binary=args.age,
                            identity=args.identity, manifest=_json(args.manifest.read_bytes()),
                            expected_execution=expected)
        print('{"status":"PASS"}')
        return 0
    except Exception:
        # Detailed Python/age exceptions can contain private inputs. The runner
        # and CLI expose one fixed reason; plaintext remains in private storage.
        print('{"status":"BLOCKED","reason":"private_package_operation_refused"}')
        return 2


def recover_package(ciphertext, receipt, destination, *, age_binary, identity, manifest, expected_execution):
    """Authenticate, verify and atomically promote private evidence; no networking.

    Receipt provenance is supplied by the operator's independently verified
    expected_execution, not inferred from a successful decryption.
    """
    execution = _receipt(receipt, expected_execution)
    archive_limit, _ = _limits(receipt["schema"])
    if validate_manifest(manifest) != receipt["manifest_sha256"]:
        _fail("receipt_manifest_mismatch")
    ciphertext, identity = Path(ciphertext).absolute(), Path(identity).absolute()
    if _regular(ciphertext).st_size != receipt["ciphertext_bytes"] or _hash(ciphertext) != receipt["ciphertext_sha256"]:
        _fail("ciphertext_receipt_mismatch")
    key_info = _regular(identity)
    _private_path(identity.parent)
    if os.name != "nt" and key_info.st_mode & 0o077:
        _fail("identity_permissions_not_private")
    destination = _private_path(destination, exists=False)
    if destination.exists():
        _fail("recovery_destination_exists")
    _private_path(destination.parent)
    with tempfile.TemporaryDirectory(prefix=".recovery-", dir=destination.parent) as name:
        temp = Path(name)
        archive = temp / "decrypted.part"
        _age(age_binary, ["--decrypt", "--identity", identity, ciphertext], archive, reason="decryption_failed",
             limit=archive_limit)
        if archive.stat().st_size > archive_limit:
            _fail("package_size_or_member_limit")
        if receipt["schema"] != LEGACY_SCHEMA and (archive.stat().st_size != receipt["archive_bytes"] or
                                             _hash(archive) != receipt["archive_sha256"]):
            _fail("archive_receipt_mismatch")
        recovered = temp / "verified"
        recovered.mkdir(mode=0o700)
        index = _unpack(archive, recovered, manifest, receipt, execution)
        recovered.rename(destination)
    return index


if __name__ == "__main__":
    sys.exit(main())
