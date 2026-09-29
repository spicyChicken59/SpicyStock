"""Ciphertext-only delivery of the existing historical cache, with safe recovery.

The caller verifies runner identity and permission evidence before acquisition.
This module does not grant rights, acquire data, or establish receipt provenance.
Recovery requires execution metadata independently checked against GitHub.
"""
from __future__ import annotations

from datetime import datetime
import argparse
import gzip
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

SCHEMA = "historical-encrypted-receipt-v2"
INDEX_SCHEMA = "historical-private-package-v2"
REPOSITORY = "spicyChicken59/SpicyStock"
MAX_CIPHERTEXT_BYTES = 200 * 1024 ** 2
MAX_ARCHIVE_BYTES = MAX_CIPHERTEXT_BYTES - 1024 ** 2
MAX_PLAINTEXT_BYTES = 2 * 1024 ** 3
MAX_MEMBERS = 4096
MAX_INDEX_BYTES = 4 * 1024 ** 2
CIPHERTEXT_NAME = "evidence.tar.gz.age"
AGE_HEADER = b"age-encryption.org/v1\n"
RECEIPT_NAME = "receipt.json"
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_RECIPIENT = re.compile(r"age1[023456789acdefghjklmnpqrstuvwxyz]{58}\Z")
_EXECUTION_KEYS = {"repository", "repository_id", "assignment_id", "manifest_sha256",
                   "workflow_id", "workflow_path", "recipient_sha256", "run_id",
                   "run_number", "run_attempt", "assignment_phase", "mode", "checkout_sha",
                   "workflow_sha", "implementation_pr", "readiness_comment_id",
                   "recovery_contract_sha256", "status"}
_INTERNAL = {"_package/manifest.json", "_package/execution.json", "_package/diagnostics.json"}


class PackageError(RuntimeError):
    """Constant reason codes only; never attach paths, values or subprocess output."""


def _fail(reason):
    raise PackageError(reason)


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
    except (ValueError, UnicodeError):
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


def _execution(value):
    if not isinstance(value, dict) or set(value) not in (_EXECUTION_KEYS, _EXECUTION_KEYS | {"started_at"}):
        _fail("invalid_execution_metadata")
    try:
        execution_guard.validate_phase_binding(value)
    except (execution_guard.GuardError, OSError, ValueError, TypeError, KeyError):
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


def execution_metadata(record, *, status=None):
    """Explicit public projection; guard approval documents remain private."""
    if not isinstance(record, dict):
        _fail("invalid_execution_metadata")
    if record.get("schema") == "historical-execution-v2":
        if any(record.get(k) != "PASS" for k in ("status", "readiness_status", "lifetime_status")):
            _fail("execution_guard_not_passed")
        result = {k: record[k] for k in _EXECUTION_KEYS}
    else:
        result = dict(record)
    if status is not None:
        result["status"] = status
    return _execution(result)


def _age_environment():
    # No provider credentials, GitHub tokens, plugin configuration or arbitrary
    # inherited settings reach encryption/decryption subprocesses.
    allowed = {"SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG", "LC_ALL"}
    return {**{k: v for k, v in os.environ.items() if k.upper() in allowed}, "NO_COLOR": "1"}


def _age(age_binary, arguments, output, *, reason, limit=MAX_CIPHERTEXT_BYTES):
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
            db.execute("SELECT id,reservation,retained,status,body_hash FROM attempts").fetchall()
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
        members = [{"path": name, "bytes": size, "sha256": _hash(path)}
                   for name, (path, size) in sorted(sources.items())]
        members.extend({"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
                       for name, raw in sorted(extras.items()))
        index = {"schema": INDEX_SCHEMA, "manifest_sha256": identity, "execution": execution,
                 "recipient_sha256": fingerprint, "members": sorted(members, key=lambda x: x["path"])}
        index_raw = encode(index)
        if len(index_raw) > MAX_INDEX_BYTES or sum(e["bytes"] for e in members) + len(index_raw) > MAX_PLAINTEXT_BYTES:
            _fail("package_index_too_large")
        with tempfile.TemporaryDirectory(prefix=".package-", dir=storage) as name:
            temp = Path(name)
            archive = temp / "evidence.tar.gz"
            with archive.open("xb") as out:
                os.chmod(archive, 0o600)
                with gzip.GzipFile(fileobj=out, mode="wb", mtime=0, filename="") as zipped:
                    with tarfile.open(fileobj=zipped, mode="w", format=tarfile.USTAR_FORMAT) as tar:
                        _entry(tar, "_package/index.json", io.BytesIO(index_raw), len(index_raw))
                        for entry in index["members"]:
                            path = entry["path"]
                            if path in extras:
                                _entry(tar, path, io.BytesIO(extras[path]), entry["bytes"])
                            else:
                                with sources[path][0].open("rb") as source:
                                    _entry(tar, path, source, entry["bytes"])
            if archive.stat().st_size > MAX_ARCHIVE_BYTES:
                _fail("package_size_or_member_limit")
            # Recheck after reading: concurrent edits must not create an index
            # which describes different raw bytes than the delivered archive.
            if any(_hash(sources[e["path"]][0]) != e["sha256"] for e in members if e["path"] in sources):
                _fail("package_source_changed")
            ciphertext = temp / "ciphertext.part"
            _age(age_binary, ["--encrypt", "--recipient", recipient, archive], ciphertext,
                 reason="encryption_failed")
            with ciphertext.open("rb") as stream:
                if stream.read(len(AGE_HEADER)) != AGE_HEADER:
                    _fail("invalid_ciphertext_header")
            receipt = {"schema": SCHEMA, **execution, "manifest_sha256": identity,
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
    execution_keys = _EXECUTION_KEYS | ({"started_at"} if "started_at" in receipt else set())
    extra = {"schema", "manifest_sha256", "recipient_sha256", "ciphertext_sha256", "ciphertext_bytes", "artifact_name"}
    if set(receipt) != execution_keys | extra or receipt["schema"] != SCHEMA:
        _fail("invalid_receipt")
    execution = _execution({k: receipt[k] for k in execution_keys})
    if expected_execution is not None and execution != _execution(expected_execution):
        _fail("receipt_execution_mismatch")
    if any(not isinstance(receipt[k], str) or not _HEX.fullmatch(receipt[k])
           for k in ("manifest_sha256", "recipient_sha256", "ciphertext_sha256")):
        _fail("invalid_receipt")
    if type(receipt["ciphertext_bytes"]) is not int or not 22 < receipt["ciphertext_bytes"] <= MAX_CIPHERTEXT_BYTES:
        _fail("ciphertext_size_limit")
    if receipt["artifact_name"] != "historical-evidence-" + "-".join(str(execution[k]) for k in ("run_id", "run_attempt", "mode")):
        _fail("invalid_artifact_identity")
    return execution


def validate_delivery(delivery, receipt):
    """Fail closed immediately before uploading these two exact files."""
    delivery = _private_path(delivery)
    _receipt(receipt)
    if {p.name for p in delivery.iterdir()} != {CIPHERTEXT_NAME, RECEIPT_NAME}:
        _fail("plaintext_or_unapproved_delivery_file")
    ciphertext = delivery / CIPHERTEXT_NAME
    if _regular(ciphertext).st_size != receipt["ciphertext_bytes"] or _hash(ciphertext) != receipt["ciphertext_sha256"]:
        _fail("ciphertext_receipt_mismatch")
    _regular(delivery / RECEIPT_NAME)
    if _json((delivery / RECEIPT_NAME).read_bytes()) != receipt:
        _fail("receipt_file_mismatch")
    with ciphertext.open("rb") as stream:
        if stream.read(len(AGE_HEADER)) != AGE_HEADER:
            _fail("invalid_ciphertext_header")
    return receipt


def _unpack(archive, destination, manifest, receipt, execution):
    allowed = _allowed(manifest) | _INTERNAL
    seen, total = set(), 0
    try:
        with tarfile.open(archive, "r:gz") as tar:
            first = tar.next()
            if (first is None or first.name != "_package/index.json" or not first.isreg() or
                first.linkname or not 0 <= first.size <= MAX_INDEX_BYTES):
                _fail("invalid_package_index")
            index = _json(tar.extractfile(first).read())
            if (set(index) != {"schema", "manifest_sha256", "execution", "recipient_sha256", "members"} or
                index["schema"] != INDEX_SCHEMA or index["manifest_sha256"] != receipt["manifest_sha256"] or
                index["execution"] != execution or index["recipient_sha256"] != receipt["recipient_sha256"] or
                not isinstance(index["members"], list) or len(index["members"]) >= MAX_MEMBERS):
                _fail("package_identity_mismatch")
            expected = {}
            for entry in index["members"]:
                if (not isinstance(entry, dict) or set(entry) != {"path", "bytes", "sha256"} or
                    not isinstance(entry["path"], str) or entry["path"] in expected or
                    type(entry["bytes"]) is not int or not 0 <= entry["bytes"] <= MAX_PLAINTEXT_BYTES or
                    not isinstance(entry["sha256"], str) or not _HEX.fullmatch(entry["sha256"])):
                    _fail("invalid_package_index")
                expected[entry["path"]] = entry
            if not {"ledger.sqlite3", *_INTERNAL} <= set(expected):
                _fail("missing_recovery_member")
            for member in tar:
                if member.name == first.name and not seen:
                    # TarFile iteration yields its already-read first member.
                    seen.add(first.name)
                    continue
                name = member.name
                normalized = PurePosixPath(name)
                if (name in seen or name not in expected or not member.isreg() or member.linkname or
                    normalized.is_absolute() or ".." in normalized.parts or "\\" in name or
                    (name not in allowed and not re.fullmatch(r"pages/[0-9a-f]{64}\.json", name))):
                    _fail("unsafe_archive_member")
                seen.add(name)
                total += member.size
                if member.size != expected[name]["bytes"] or total > MAX_PLAINTEXT_BYTES:
                    _fail("package_size_or_member_limit")
                target = destination.joinpath(*normalized.parts)
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                hasher = hashlib.sha256()
                with tar.extractfile(member) as source, target.open("xb") as output:
                    os.chmod(target, 0o600)
                    for block in iter(lambda: source.read(1024 * 1024), b""):
                        hasher.update(block)
                        output.write(block)
                if hasher.hexdigest() != expected[name]["sha256"]:
                    _fail("package_member_hash_mismatch")
                if name.startswith("pages/") and target.stem != hasher.hexdigest():
                    _fail("raw_page_hash_mismatch")
            if seen != set(expected) | {first.name}:
                _fail("missing_recovery_member")
    except (tarfile.TarError, OSError, EOFError, KeyError, TypeError, AttributeError):
        _fail("invalid_package_archive")
    if _json((destination / "_package/manifest.json").read_bytes()) != manifest:
        _fail("package_manifest_mismatch")
    if _json((destination / "_package/execution.json").read_bytes()) != execution:
        _fail("package_execution_mismatch")
    _json((destination / "_package/diagnostics.json").read_bytes())
    _ledger(destination, receipt["manifest_sha256"])
    (destination / "_package/index.json").write_bytes(encode(index))
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
            if (guard.get("schema") != "historical-execution-v2" or
                guard.get("manifest_sha256") != validate_manifest(manifest) or
                guard.get("recipient_sha256") != policy["recipient_sha256"]):
                _fail("package_guard_identity_mismatch")
            diagnostics = _json((args.storage / "execution-diagnostics.json").read_bytes())
            metadata = execution_metadata(guard, status=diagnostics["status"])
            if (diagnostics.get("schema") != "historical-execution-diagnostics-v2" or
                    diagnostics.get("execution_binding") != execution_guard.validate_phase_binding(metadata)):
                _fail("package_retained_execution_mismatch")
            package_evidence(args.storage, manifest, args.delivery, age_binary=args.age,
                             recipient=recipient, execution=metadata,
                             diagnostics={"execution_guard": guard})
        else:
            receipt = _json(args.receipt.read_bytes())
            expected = _json(args.expected_execution.read_bytes())
            if expected.get("schema") == "historical-execution-v2":
                if (expected.get("manifest_sha256") != receipt.get("manifest_sha256") or
                    expected.get("recipient_sha256") != receipt.get("recipient_sha256")):
                    _fail("recovery_guard_identity_mismatch")
                expected = execution_metadata(expected, status=receipt.get("status"))
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
        _age(age_binary, ["--decrypt", "--identity", identity, ciphertext], archive, reason="decryption_failed")
        if archive.stat().st_size > MAX_ARCHIVE_BYTES:
            _fail("package_size_or_member_limit")
        recovered = temp / "verified"
        recovered.mkdir(mode=0o700)
        index = _unpack(archive, recovered, manifest, receipt, execution)
        recovered.rename(destination)
    return index


if __name__ == "__main__":
    sys.exit(main())
