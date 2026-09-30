"""Actual age recovery plus fail-closed packaging of the actual acquisition cache."""
from copy import deepcopy
import hashlib
import gzip
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tarfile

import pytest

from tests.test_historical_acquisition import setup, response
from tests.test_historical_execution import run_setup
from tools import historical_package as package
from tools import historical_execution as execution_runner
from tools import historical_execution_guard as execution_guard
from tools.historical_acquisition import cached_pages, encode, validate_manifest


RECIPIENT = "age1ql3z7hjy54pw3hyww5ayyfg7zqgvc7w3j2elw8zmrj2kg5sfn9aqmcac8p"
SENTINEL = "PRIVATE_SYNTHETIC_SENTINEL_54e9aa1f"


@pytest.fixture
def execution(source):
    # Explicit synthetic GitHub metadata; not a recorded or authorized run.
    return {"repository": package.REPOSITORY, "assignment_id": package.ASSIGNMENT,
            "repository_id": execution_guard.REPOSITORY_ID,
            "workflow_id": execution_guard.WORKFLOW_ID, "workflow_path": execution_guard.WORKFLOW,
            "run_id": 123456, "run_attempt": 1, "run_number": 4, "assignment_phase": 1,
            "implementation_pr": 123, "readiness_comment_id": 654321,
            "manifest_sha256": validate_manifest(source[0]),
            "recipient_sha256": package.recipient_fingerprint(RECIPIENT),
            "recovery_contract_sha256": execution_guard.RECOVERY_CONTRACT_SHA256,
            "compatibility_contract_sha256": execution_guard.COMPATIBILITY_CONTRACT_SHA256,
            "release_evidence_sha256": "c" * 64,
            "workflow_sha": "1" * 40,
            "checkout_sha": "2" * 40, "mode": "rehearsal", "status": "PASS",
            "started_at": "2026-09-28T17:00:00Z"}


@pytest.fixture
def source(setup):
    manifest, approval, root, clock, build = setup
    runner, transport = build([response()])
    runner.run("canonical")
    os.chmod(root, 0o700)
    (root / "execution-diagnostics.json").write_bytes(encode({"sentinel": SENTINEL}))
    return manifest, root


@pytest.fixture
def age(tmp_path):
    configured = os.environ.get("AGE_BINARY")
    if not configured:
        pytest.skip("cryptographic tests NOT RUN: set AGE_BINARY to a verified age executable")
    binary = Path(configured)
    keygen = binary.with_name("age-keygen" + binary.suffix)
    if not binary.is_file() or not keygen.is_file():
        pytest.fail("AGE_BINARY and neighboring age-keygen must exist")
    keys = []
    for count in range(2):
        key = tmp_path / ("ephemeral-synthetic-identity-" + str(count))
        result = subprocess.run([str(keygen), "-o", str(key)], stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                env=package._age_environment(), check=False)
        assert result.returncode == 0
        os.chmod(key, 0o600)
        public = subprocess.run([str(keygen), "-y", str(key)], stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                env=package._age_environment(), check=False)
        assert public.returncode == 0
        keys.append((key, public.stdout.decode("ascii").strip()))
    return binary, keys


def seal(source, execution, age, tmp_path):
    manifest, storage = source
    binary, keys = age
    delivery = tmp_path / "delivery"
    execution["recipient_sha256"] = package.recipient_fingerprint(keys[0][1])
    receipt = package.package_evidence(storage, manifest, delivery, age_binary=binary,
                                       recipient=keys[0][1], execution=execution)
    return delivery, receipt


def test_real_age_roundtrip_preserves_exact_cache_and_private_sentinel(source, execution, age, tmp_path, capsys):
    manifest, storage = source
    before = {str(p.relative_to(storage)): p.read_bytes() for p in storage.rglob("*")
              if p.is_file() and p.name != "acquisition.lock"}
    delivery, receipt = seal(source, execution, age, tmp_path)
    recovered = tmp_path / "recovered"
    index = package.recover_package(delivery / package.CIPHERTEXT_NAME, receipt, recovered,
                age_binary=age[0], identity=age[1][0][0], manifest=manifest, expected_execution=execution)
    assert all((recovered / name).read_bytes() == raw for name, raw in before.items())
    assert cached_pages(manifest, recovered, "canonical") == cached_pages(manifest, storage, "canonical")
    assert json.loads((recovered / "execution-diagnostics.json").read_bytes())["sentinel"] == SENTINEL
    assert index["recipient_sha256"] == hashlib.sha256((age[1][0][1] + "\n").encode()).hexdigest()
    assert receipt["schema"] == "historical-encrypted-receipt-v4"
    assert index["schema"] == "historical-private-package-v4"
    assert receipt["delivery_envelope"] == index["delivery_envelope"] == "historical-delivery-envelope-v1"
    assert 0 < receipt["ciphertext_bytes"] - receipt["archive_bytes"] <= 1024 ** 2
    assert set(p.name for p in delivery.iterdir()) == {package.CIPHERTEXT_NAME, package.RECEIPT_NAME}
    assert all(SENTINEL.encode() not in p.read_bytes() for p in delivery.iterdir())
    assert "AGE-SECRET-KEY-" not in (delivery / package.RECEIPT_NAME).read_text()
    assert SENTINEL not in capsys.readouterr().out


@pytest.mark.parametrize("fault", ["wrong_key", "tampered", "truncated"])
def test_real_age_rejects_wrong_key_tampering_and_truncation(source, execution, age, tmp_path, fault):
    manifest, _ = source
    delivery, receipt = seal(source, execution, age, tmp_path)
    cipher = delivery / package.CIPHERTEXT_NAME
    identity = age[1][1 if fault == "wrong_key" else 0][0]
    if fault != "wrong_key":
        raw = bytearray(cipher.read_bytes())
        if fault == "tampered":
            raw[-1] ^= 1
        else:
            raw = raw[:-17]
        cipher.write_bytes(raw)
        # Even a caller that changes an untrusted outer checksum cannot bypass
        # age authentication. Normal recovery rejects its checksum even sooner.
        receipt["ciphertext_sha256"] = hashlib.sha256(raw).hexdigest()
        receipt["ciphertext_bytes"] = len(raw)
    destination = tmp_path / "recovered"
    with pytest.raises(package.PackageError, match="decryption_failed"):
        package.recover_package(cipher, receipt, destination, age_binary=age[0], identity=identity,
                                manifest=manifest, expected_execution=execution)
    assert not destination.exists()
    assert not list(tmp_path.glob(".recovery-*"))


def test_real_age_invalid_recipient_leaves_no_delivery(source, execution, age, tmp_path):
    manifest, storage = source
    # Correct alphabet and length, deliberately invalid Bech32 checksum.
    recipient = age[1][0][1][:-1] + ("q" if age[1][0][1][-1] != "q" else "p")
    execution["recipient_sha256"] = package.recipient_fingerprint(recipient)
    with pytest.raises(package.PackageError, match="invalid_encryption_recipient"):
        package.validate_recipient(age[0], recipient, storage)
    delivery = tmp_path / "delivery"
    with pytest.raises(package.PackageError, match="encryption_failed"):
        package.package_evidence(storage, manifest, delivery, age_binary=age[0],
                                 recipient=recipient, execution=execution)
    assert not delivery.exists()
    assert not list(storage.glob(".package-*"))


def test_real_age_partial_ledger_and_reserved_budget_remain_recoverable(source, execution, age, tmp_path):
    manifest, storage = source
    with sqlite3.connect(storage / "ledger.sqlite3") as db:
        db.execute("INSERT INTO attempts(query_id,attempt,timestamp,reservation,status) VALUES('canonical',0,0,12345,'reserved')")
    execution["status"] = "BLOCKED"
    original = (storage / "ledger.sqlite3").read_bytes()
    delivery, receipt = seal(source, execution, age, tmp_path)
    recovered = tmp_path / "recovered"
    package.recover_package(delivery / package.CIPHERTEXT_NAME, receipt, recovered,
                age_binary=age[0], identity=age[1][0][0], manifest=manifest, expected_execution=execution)
    assert (recovered / "ledger.sqlite3").read_bytes() == original
    with sqlite3.connect(recovered / "ledger.sqlite3") as db:
        assert db.execute("SELECT SUM(reservation) FROM attempts").fetchone()[0] == 12345


@pytest.mark.parametrize("name", ["api-key.txt", "unexpected.json", "ledger.sqlite3-wal", "unapproved/nested.json"])
def test_unapproved_plaintext_blocks_packaging_before_encryption(source, execution, tmp_path, monkeypatch, name):
    manifest, storage = source
    path = storage / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(SENTINEL)
    monkeypatch.setattr(package, "_age", lambda *a, **k: pytest.fail("encryption must not run"))
    with pytest.raises(package.PackageError, match="unapproved_plaintext_file"):
        package.package_evidence(storage, manifest, tmp_path / "delivery", age_binary="unused",
                                 recipient=RECIPIENT, execution=execution)
    assert not (tmp_path / "delivery").exists()


def test_missing_ledger_cannot_be_packaged_as_recovery(source, execution, tmp_path):
    manifest, storage = source
    (storage / "ledger.sqlite3").unlink()
    with pytest.raises(package.PackageError, match="missing_package_file"):
        package.package_evidence(storage, manifest, tmp_path / "delivery", age_binary="unused",
                                 recipient=RECIPIENT, execution=execution)


def test_raw_page_filename_must_bind_exact_retained_bytes(source, execution, tmp_path):
    manifest, storage = source
    page = next((storage / "pages").iterdir())
    page.write_bytes(page.read_bytes() + b" ")
    with pytest.raises(package.PackageError, match="raw_page_hash_mismatch"):
        package.package_evidence(storage, manifest, tmp_path / "delivery", age_binary="unused",
                                 recipient=RECIPIENT, execution=execution)


def test_failed_encryption_cannot_promote_or_log_source(source, execution, tmp_path, monkeypatch, capsys):
    manifest, storage = source
    def fail(binary, arguments, output, **kwargs):
        output.write_bytes(SENTINEL.encode())
        raise package.PackageError("encryption_failed")
    monkeypatch.setattr(package, "_age", fail)
    with pytest.raises(package.PackageError, match="encryption_failed"):
        package.package_evidence(storage, manifest, tmp_path / "delivery", age_binary="unused",
                                 recipient=RECIPIENT, execution=execution)
    assert not (tmp_path / "delivery").exists()
    assert not list(storage.glob(".package-*"))
    assert SENTINEL not in capsys.readouterr().out


def test_provider_and_github_secrets_never_enter_age_environment(monkeypatch):
    for key in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY", "GH_TOKEN", "GITHUB_TOKEN", "ANTHROPIC_API_KEY", "AGE_PLUGIN_PATH"):
        monkeypatch.setenv(key, SENTINEL)
    assert SENTINEL not in package._age_environment().values()


@pytest.mark.parametrize("recipient", ["", RECIPIENT + "\n", RECIPIENT + " " + RECIPIENT, "ssh-ed25519 AAAA", "age1plugin1qqqq"])
def test_non_native_or_multiple_recipient_forms_rejected(recipient):
    with pytest.raises(package.PackageError, match="invalid_encryption_recipient"):
        package.recipient_fingerprint(recipient)


def test_public_metadata_disallows_sensitive_extra_fields(execution):
    execution["api_key"] = SENTINEL
    with pytest.raises(package.PackageError, match="invalid_execution_metadata"):
        package._execution(execution)


@pytest.mark.parametrize("field,value", [("run_number", 1), ("assignment_phase", 2),
                                         ("run_attempt", 2), ("implementation_pr", 94),
                                         ("recovery_contract_sha256", "f" * 64)])
def test_native_phase_and_recovery_binding_reject_before_encryption(source, execution, tmp_path, monkeypatch, field, value):
    execution[field] = value
    monkeypatch.setattr(package, "_age", lambda *a, **k: pytest.fail("encryption must not run"))
    with pytest.raises(package.PackageError, match="invalid_execution_identity"):
        package.package_evidence(source[1], source[0], tmp_path / "delivery", age_binary="unused",
                                 recipient=RECIPIENT, execution=execution)
    assert not (tmp_path / "delivery").exists()


@pytest.mark.parametrize("field", ["manifest_sha256", "recipient_sha256"])
def test_package_cannot_overwrite_a_disagreeing_execution_identity(source, execution, tmp_path, monkeypatch, field):
    execution[field] = "f" * 64
    monkeypatch.setattr(package, "_age", lambda *a, **k: pytest.fail("encryption must not run"))
    with pytest.raises(package.PackageError, match="package_execution_binding_mismatch"):
        package.package_evidence(source[1], source[0], tmp_path / "delivery", age_binary="unused",
                                 recipient=RECIPIENT, execution=execution)
    assert not (tmp_path / "delivery").exists()


def test_old_receipt_is_not_reinterpreted_under_recovery_contract(source, execution, age, tmp_path, monkeypatch):
    delivery, receipt = seal(source, execution, age, tmp_path)
    receipt["schema"] = "historical-encrypted-receipt-v1"
    monkeypatch.setattr(package, "_age", lambda *a, **k: pytest.fail("decryption must not run"))
    with pytest.raises(package.PackageError, match="invalid_receipt"):
        package.recover_package(delivery / package.CIPHERTEXT_NAME, receipt, tmp_path / "recovered",
                                age_binary=age[0], identity=age[1][0][0], manifest=source[0],
                                expected_execution=execution)
    assert not (tmp_path / "recovered").exists()


def test_ciphertext_limit_is_fixed_and_separate_from_response_budget():
    assert package.MAX_ARCHIVE_BYTES == 250 * 1024 ** 2
    assert package.MAX_CIPHERTEXT_BYTES == 251 * 1024 ** 2
    assert package.MAX_CIPHERTEXT_OVERHEAD_BYTES == 1024 ** 2
    assert package.LEGACY_MAX_ARCHIVE_BYTES == 199 * 1024 ** 2
    assert package.LEGACY_MAX_CIPHERTEXT_BYTES == 200 * 1024 ** 2
    assert package.MAX_PLAINTEXT_BYTES == 2 * 1024 ** 3
    assert package.MAX_MEMBERS == 4096 and package.MAX_INDEX_BYTES == 4 * 1024 ** 2
    assert package.codec.WINDOW_BYTES == 1024 ** 3


def test_current_envelope_matches_immutable_release_compatibility():
    declared = execution_guard.compatibility_contract()["delivery_envelope"]
    assert declared["schema"] == package.DELIVERY_ENVELOPE
    assert declared["receipt_schema"] == package.SCHEMA and declared["index_schema"] == package.INDEX_SCHEMA
    assert declared["archive_format"] == package.codec.FORMAT
    assert declared["max_archive_bytes"] == package.MAX_ARCHIVE_BYTES
    assert declared["max_ciphertext_bytes"] == package.MAX_CIPHERTEXT_BYTES
    assert declared["max_encryption_overhead_bytes"] == package.MAX_CIPHERTEXT_OVERHEAD_BYTES
    assert declared["max_expanded_bytes"] == package.MAX_PLAINTEXT_BYTES
    assert package.PREVIOUS_COMPATIBILITY_CONTRACT_SHA256 == execution_guard.PREVIOUS_COMPATIBILITY_CONTRACT_SHA256


def test_compressed_size_limit_blocks_before_encryption(source, execution, tmp_path, monkeypatch):
    manifest, storage = source
    monkeypatch.setattr(package, "MAX_ARCHIVE_BYTES", 1)
    monkeypatch.setattr(package, "_age", lambda *a, **k: pytest.fail("encryption must not run"))
    with pytest.raises(package.PackageError, match="package_size_or_member_limit"):
        package.package_evidence(storage, manifest, tmp_path / "delivery", age_binary="unused",
                                 recipient=RECIPIENT, execution=execution)


def test_delivery_allows_no_plaintext_sentinel(source, execution, age, tmp_path):
    delivery, receipt = seal(source, execution, age, tmp_path)
    (delivery / "plaintext.json").write_text(SENTINEL)
    with pytest.raises(package.PackageError, match="plaintext_or_unapproved_delivery_file"):
        package.validate_delivery(delivery, receipt)


def test_receipt_must_match_independently_verified_run(source, execution, age, tmp_path):
    delivery, receipt = seal(source, execution, age, tmp_path)
    wrong = {**execution, "run_id": 9999}
    with pytest.raises(package.PackageError, match="receipt_execution_mismatch"):
        package.recover_package(delivery / package.CIPHERTEXT_NAME, receipt, tmp_path / "recovered",
                    age_binary=age[0], identity=age[1][0][0], manifest=source[0], expected_execution=wrong)


def archive_with_fault(tmp_path, source, execution, fault, *, legacy=True):
    """Exercise recovery format directly, without needing an encryption stub."""
    manifest, storage = source
    if legacy:
        execution = {k: v for k, v in execution.items() if k not in
                     ("compatibility_contract_sha256", "release_evidence_sha256")}
    identity = validate_manifest(manifest)
    payloads = {"ledger.sqlite3": (storage / "ledger.sqlite3").read_bytes(),
                "_package/manifest.json": encode(manifest), "_package/execution.json": encode(execution),
                "_package/diagnostics.json": b"{}\n"}
    if fault in ("traversal", "symlink", "hardlink", "unapproved", "duplicate"):
        malicious = {"traversal": "../escaped", "symlink": "execution-diagnostics.json",
                     "hardlink": "execution-diagnostics.json", "unapproved": "secret.txt",
                     "duplicate": "execution-diagnostics.json"}[fault]
        payloads[malicious] = b"malicious"
    if fault == "missing_ledger":
        del payloads["ledger.sqlite3"]
    index = {"schema": package.LEGACY_INDEX_SCHEMA if legacy else package.INDEX_SCHEMA,
             "manifest_sha256": identity, "execution": execution,
             "recipient_sha256": package.recipient_fingerprint(RECIPIENT),
             "members": [{"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
                         for name, raw in payloads.items()]}
    if not legacy:
        index["archive_format"] = package.codec.FORMAT
        index["delivery_envelope"] = package.DELIVERY_ENVELOPE
    archive = tmp_path / "malicious.archive"
    body = io.BytesIO()
    with tarfile.open(fileobj=body, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        raw = encode(index)
        package._entry(tar, "_package/index.json", io.BytesIO(raw), len(raw))
        for name, raw in payloads.items():
            if fault in ("symlink", "hardlink") and name == malicious:
                info = tarfile.TarInfo(name)
                info.type = tarfile.SYMTYPE if fault == "symlink" else tarfile.LNKTYPE
                info.linkname = "../../escaped"
                tar.addfile(info)
            else:
                if fault == "hash" and name == "_package/diagnostics.json":
                    raw = b"[]\n"
                package._entry(tar, name, io.BytesIO(raw), len(raw))
                if fault == "duplicate" and name == malicious:
                    package._entry(tar, name, io.BytesIO(raw), len(raw))
    archive.write_bytes(_compressed(body.getvalue(), package.codec.LEGACY_FORMAT if legacy else package.codec.FORMAT))
    receipt = {"schema": package.LEGACY_SCHEMA if legacy else package.SCHEMA, "manifest_sha256": identity,
               "recipient_sha256": index["recipient_sha256"]}
    if not legacy:
        receipt["archive_format"] = package.codec.FORMAT
        receipt["delivery_envelope"] = package.DELIVERY_ENVELOPE
    return archive, receipt


@pytest.mark.parametrize("fault", ["traversal", "symlink", "hardlink", "unapproved", "duplicate", "missing_ledger", "hash"])
@pytest.mark.parametrize("legacy", [True, False])
def test_safe_archive_recovery_rejects_unsafe_members(tmp_path, source, execution, fault, legacy):
    archive, receipt = archive_with_fault(tmp_path, source, execution, fault, legacy=legacy)
    destination = tmp_path / "candidate"
    destination.mkdir()
    with pytest.raises(package.PackageError):
        expected = ({k: v for k, v in execution.items() if k in package._LEGACY_EXECUTION_KEYS | {"started_at"}}
                    if legacy else execution)
        package._unpack(archive, destination, source[0], receipt, expected)
    assert not (tmp_path / "escaped").exists()


def test_hardlinked_source_is_not_permitted(source, execution, tmp_path):
    manifest, storage = source
    os.link(storage / "ledger.sqlite3", tmp_path / "second-ledger-link")
    with pytest.raises(package.PackageError, match="nonregular_package_file"):
        package.package_evidence(storage, manifest, tmp_path / "delivery", age_binary="unused",
                                 recipient=RECIPIENT, execution=execution)


def test_guard_projection_keeps_approval_text_out_of_public_metadata(execution):
    guard = {**execution, "schema": "historical-execution-v3", "run_id": 123456, "run_attempt": 1,
             "readiness_status": "PASS", "lifetime_status": "PASS", "evidence": {"private": SENTINEL}}
    projected = package.execution_metadata(guard, status="BLOCKED")
    assert SENTINEL not in json.dumps(projected)
    assert projected["status"] == "BLOCKED"
    assert projected["run_id"] == 123456
    assert projected["run_number"] == 4 and projected["assignment_phase"] == 1
    assert projected["recovery_contract_sha256"] == execution_guard.RECOVERY_CONTRACT_SHA256


def test_real_age_cli_path_packages_and_recovers_actual_cache(source, execution, age, tmp_path):
    manifest, storage = source
    guard = {**execution, "schema": "historical-execution-v3", "run_id": 123456, "run_attempt": 1,
             "readiness_status": "PASS", "lifetime_status": "PASS",
             "manifest_sha256": validate_manifest(manifest),
             "recipient_sha256": package.recipient_fingerprint(age[1][0][1]),
             "evidence": {"private": SENTINEL}}
    (storage / "execution-diagnostics.json").write_bytes(encode({
        "schema": "historical-execution-diagnostics-v3", "status": "PASS", "sentinel": SENTINEL,
        "execution_binding": execution_guard.validate_phase_binding(guard)}))
    paths = {}
    for name, value in {"manifest": manifest, "execution": guard,
                        "policy": {"recipient": age[1][0][1], "recipient_sha256": guard["recipient_sha256"]}}.items():
        paths[name] = tmp_path / (name + ".json")
        paths[name].write_bytes(encode(value))
    commands = [
        ["validate-recipient", "--policy", paths["policy"], "--age", age[0], "--scratch", storage],
        ["package", "--storage", storage, "--manifest", paths["manifest"], "--execution", paths["execution"],
         "--policy", paths["policy"], "--age", age[0], "--delivery", tmp_path / "delivery"],
        ["recover", "--cipher", tmp_path / "delivery" / package.CIPHERTEXT_NAME,
         "--receipt", tmp_path / "delivery" / package.RECEIPT_NAME, "--identity", age[1][0][0],
         "--age", age[0], "--destination", tmp_path / "recovered", "--expected-execution", paths["execution"],
         "--manifest", paths["manifest"]],
    ]
    for args in commands:
        result = subprocess.run([sys.executable, str(Path(package.__file__)), *map(str, args)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        assert result.returncode == 0, result.stdout
        assert result.stdout.strip() == b'{"status":"PASS"}'
        assert not result.stderr
    assert (tmp_path / "recovered" / "ledger.sqlite3").read_bytes() == (storage / "ledger.sqlite3").read_bytes()
    assert SENTINEL not in (tmp_path / "delivery" / package.RECEIPT_NAME).read_text()


def test_cli_errors_do_not_echo_private_paths_or_values(tmp_path, capsys):
    path = tmp_path / (SENTINEL + ".json")
    path.write_text('{"recipient":"' + SENTINEL + '","recipient_sha256":"bad"}')
    assert package.main(["validate-recipient", "--policy", str(path), "--age", SENTINEL]) == 2
    captured = capsys.readouterr()
    assert captured.out.strip() == '{"status":"BLOCKED","reason":"private_package_operation_refused"}'
    assert not captured.err


def test_actual_runner_reconciliation_encryption_recovery_and_offline_replay(run_setup, age, tmp_path, monkeypatch):
    from tools import historical_acquisition as acquisition
    manifest, storage, record, approval = run_setup
    record["recipient_sha256"] = package.recipient_fingerprint(age[1][0][1])
    policy = execution_guard.load_policy()
    policy.update(recipient=age[1][0][1], recipient_sha256=record["recipient_sha256"])
    monkeypatch.setattr(execution_guard, "RECIPIENT_SHA256", record["recipient_sha256"])
    monkeypatch.setattr(acquisition, "AlpacaTransport", lambda: pytest.fail("real provider transport constructed"))
    assert execution_runner.execute("rehearsal", manifest, storage, record, approval)["status"] == "PASS"
    assert execution_runner.execute("offline", manifest, storage, record, approval)["status"] in ("PASS", "BLOCKED")
    details = {day: (storage / ("reconciliation-" + day + ".json")).read_bytes() for day in manifest["populations"]}
    ledger = (storage / "ledger.sqlite3").read_bytes()
    raw_pages = {p.name: p.read_bytes() for p in (storage / "pages").iterdir()}
    diagnostics = json.loads((storage / "execution-diagnostics.json").read_bytes())
    assert diagnostics["prior_acquisition"]["synthetic_transport_calls"] == 7
    metadata = package.execution_metadata(record, status=diagnostics["status"])
    delivery = tmp_path / "delivery"
    receipt = package.package_evidence(storage, manifest, delivery, age_binary=age[0],
                                       recipient=age[1][0][1], execution=metadata)
    recovered = tmp_path / "recovered"
    package.recover_package(delivery / package.CIPHERTEXT_NAME, receipt, recovered,
                            age_binary=age[0], identity=age[1][0][0], manifest=manifest,
                            expected_execution=metadata)
    assert (recovered / "ledger.sqlite3").read_bytes() == ledger
    assert {p.name: p.read_bytes() for p in (recovered / "pages").iterdir()} == raw_pages
    recovered_approval = {**approval, "storage_root": str(recovered)}
    assert execution_runner.execute("offline", manifest, recovered, record, recovered_approval)["status"] in ("PASS", "BLOCKED")
    assert (recovered / "ledger.sqlite3").read_bytes() == ledger
    for day, original in details.items():
        assert (recovered / ("reconciliation-" + day + ".json")).read_bytes() == original
        detail = json.loads(original)
        assert detail["new_provider_requests"] == 0
        assert detail["normalizations"] and detail["C"]["status"] != "NOT RUN"
        assert detail["B"]["status"] == "BLOCKED"  # Never invent the original filter mask.


def test_real_age_legacy_v2_gzip_recovers_original_members_and_guard(source, execution, age, tmp_path, monkeypatch):
    """Generate the frozen old writer's exact shape, never upgrade its receipt."""
    manifest, storage = source
    legacy = {k: v for k, v in execution.items() if k in package._LEGACY_EXECUTION_KEYS | {"started_at"}}
    legacy["recipient_sha256"] = package.recipient_fingerprint(age[1][0][1])
    sources = package._sources(storage, manifest, validate_manifest(manifest))
    payloads = {name: path.read_bytes() for name, (path, _) in sources.items()}
    payloads.update({"_package/manifest.json": encode(manifest),
                     "_package/execution.json": encode(legacy), "_package/diagnostics.json": b"{}\n"})
    index = {"schema": package.LEGACY_INDEX_SCHEMA, "manifest_sha256": validate_manifest(manifest),
             "execution": legacy, "recipient_sha256": legacy["recipient_sha256"],
             "members": [{"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
                         for name, raw in sorted(payloads.items())]}
    archive = tmp_path / "old.tar.gz"
    with archive.open("wb") as output, gzip.GzipFile(fileobj=output, mode="wb", mtime=0, filename="") as zipped:
        with tarfile.open(fileobj=zipped, mode="w", format=tarfile.USTAR_FORMAT) as tar:
            raw = encode(index)
            package._entry(tar, "_package/index.json", io.BytesIO(raw), len(raw))
            for name, raw in sorted(payloads.items()):
                package._entry(tar, name, io.BytesIO(raw), len(raw))
    delivery = tmp_path / "old-delivery"
    delivery.mkdir(mode=0o700)
    cipher = delivery / package.LEGACY_CIPHERTEXT_NAME
    package._age(age[0], ["--encrypt", "--recipient", age[1][0][1], archive], cipher, reason="test_failed")
    receipt = {"schema": package.LEGACY_SCHEMA, **legacy, "ciphertext_sha256": package._hash(cipher),
               "ciphertext_bytes": cipher.stat().st_size, "artifact_name": "historical-evidence-123456-1-rehearsal"}
    (delivery / package.RECEIPT_NAME).write_bytes(encode(receipt))
    monkeypatch.setattr(package, "MAX_ARCHIVE_BYTES", 1)
    monkeypatch.setattr(package, "MAX_CIPHERTEXT_BYTES", 1)
    package.validate_delivery(delivery, receipt)
    destination = tmp_path / "legacy-recovered"
    recovered_index = package.recover_package(cipher, receipt, destination, age_binary=age[0],
                                             identity=age[1][0][0], manifest=manifest, expected_execution=legacy)
    assert recovered_index == index
    assert all((destination / name).read_bytes() == raw for name, raw in payloads.items())
    assert "archive_format" not in receipt and "compatibility_contract_sha256" not in receipt
    old_guard = {**legacy, "schema": "historical-execution-v2", "readiness_status": "PASS", "lifetime_status": "PASS"}
    assert package.execution_metadata(old_guard, legacy=True) == {
        k: v for k, v in legacy.items() if k != "started_at"}


def test_real_age_previous_v3_zstandard_recovers_exact_old_envelope(source, execution, age, tmp_path, monkeypatch):
    """Build the former v3 shape, with its old binding and no v4 envelope."""
    manifest, storage = source
    previous = {**execution, "compatibility_contract_sha256": package.PREVIOUS_COMPATIBILITY_CONTRACT_SHA256,
                "recipient_sha256": package.recipient_fingerprint(age[1][0][1])}
    sources = package._sources(storage, manifest, validate_manifest(manifest))
    before = {name: path.read_bytes() for name, (path, _) in sources.items()}
    extras = {"_package/manifest.json": encode(manifest), "_package/execution.json": encode(previous),
              "_package/diagnostics.json": b"{}\n"}
    payloads = {**before, **extras}
    index = {"schema": "historical-private-package-v3", "archive_format": "ustar-zstandard-v1",
             "manifest_sha256": validate_manifest(manifest), "execution": previous,
             "recipient_sha256": previous["recipient_sha256"],
             "members": [{"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
                         for name, raw in sorted(payloads.items())]}
    archive = tmp_path / "old.tar.zst"
    metrics = package._write_archive(archive, encode(index), index, sources, extras)
    delivery = tmp_path / "old-delivery"
    delivery.mkdir(mode=0o700)
    cipher = delivery / package.CIPHERTEXT_NAME
    package._age(age[0], ["--encrypt", "--recipient", age[1][0][1], archive], cipher, reason="test_failed")
    receipt = {"schema": "historical-encrypted-receipt-v3", **previous,
               "archive_format": "ustar-zstandard-v1", "ciphertext_name": package.CIPHERTEXT_NAME,
               "archive_bytes": metrics["archive_bytes"], "archive_sha256": metrics["archive_sha256"],
               "ciphertext_sha256": package._hash(cipher), "ciphertext_bytes": cipher.stat().st_size,
               "artifact_name": "historical-evidence-123456-1-rehearsal"}
    (delivery / package.RECEIPT_NAME).write_bytes(encode(receipt))
    old_receipt = (delivery / package.RECEIPT_NAME).read_bytes()
    # Previous readers use their frozen caps, never these current-envelope globals.
    monkeypatch.setattr(package, "MAX_ARCHIVE_BYTES", 1)
    monkeypatch.setattr(package, "MAX_CIPHERTEXT_BYTES", 1)
    package.validate_delivery(delivery, receipt)
    destination = tmp_path / "old-recovered"
    recovered = package.recover_package(cipher, receipt, destination, age_binary=age[0],
                                        identity=age[1][0][0], manifest=manifest, expected_execution=previous)
    assert recovered == index
    assert all((destination / name).read_bytes() == raw for name, raw in payloads.items())
    assert (delivery / package.RECEIPT_NAME).read_bytes() == old_receipt
    assert "delivery_envelope" not in receipt and "delivery_envelope" not in recovered
    old_guard = {**previous, "schema": "historical-execution-v3", "readiness_status": "PASS", "lifetime_status": "PASS"}
    assert package.execution_metadata(old_guard, previous=True) == {k: v for k, v in previous.items() if k != "started_at"}
    monkeypatch.setattr(package.codec, "decode", lambda *a, **kw: pytest.fail("decoder must not start"))
    with pytest.raises(package.PackageError, match="archive_receipt_mismatch"):
        package.recover_package(cipher, {**receipt, "archive_sha256": "0" * 64}, tmp_path / "mismatched",
                                age_binary=age[0], identity=age[1][0][0], manifest=manifest,
                                expected_execution=previous)
    assert not (tmp_path / "mismatched").exists() and not list(tmp_path.glob(".recovery-*"))


def envelope_receipt(execution, schema=package.SCHEMA):
    """Small metadata fixture for exact cap boundaries; no large archive writes."""
    metadata = dict(execution)
    if schema == package.LEGACY_SCHEMA:
        metadata = {k: v for k, v in metadata.items() if k in package._LEGACY_EXECUTION_KEYS | {"started_at"}}
    elif schema == package.PREVIOUS_SCHEMA:
        metadata["compatibility_contract_sha256"] = package.PREVIOUS_COMPATIBILITY_CONTRACT_SHA256
    receipt = {"schema": schema, **metadata, "ciphertext_sha256": "a" * 64,
               "ciphertext_bytes": 200 * 1024 ** 2,
               "artifact_name": "historical-evidence-123456-1-rehearsal"}
    if schema != package.LEGACY_SCHEMA:
        receipt.update(archive_format="ustar-zstandard-v1", ciphertext_name=package.CIPHERTEXT_NAME,
                       archive_bytes=199 * 1024 ** 2, archive_sha256="b" * 64)
    if schema == package.SCHEMA:
        receipt.update(delivery_envelope=package.DELIVERY_ENVELOPE,
                       archive_bytes=250 * 1024 ** 2, ciphertext_bytes=251 * 1024 ** 2)
    return receipt, metadata


@pytest.mark.parametrize("schema", [package.LEGACY_SCHEMA, package.PREVIOUS_SCHEMA, package.SCHEMA])
def test_exact_envelope_boundary_is_admitted_without_reinterpreting_old_receipts(execution, schema):
    receipt, expected = envelope_receipt(execution, schema)
    assert package._receipt(receipt, expected) == expected


@pytest.mark.parametrize("schema", [package.LEGACY_SCHEMA, package.PREVIOUS_SCHEMA, package.SCHEMA])
def test_ciphertext_one_byte_above_its_versioned_cap_refused(execution, schema):
    receipt, expected = envelope_receipt(execution, schema)
    receipt["ciphertext_bytes"] += 1
    with pytest.raises(package.PackageError, match="ciphertext_size_limit"):
        package._receipt(receipt, expected)


@pytest.mark.parametrize("schema", [package.PREVIOUS_SCHEMA, package.SCHEMA])
def test_archive_one_byte_above_its_versioned_cap_refused(execution, schema):
    receipt, expected = envelope_receipt(execution, schema)
    receipt["archive_bytes"] += 1
    with pytest.raises(package.PackageError, match="invalid_archive_receipt"):
        package._receipt(receipt, expected)


@pytest.mark.parametrize("overhead", [-1, 0, 1024 ** 2 + 1])
def test_current_envelope_bounds_actual_overhead_below_total_cipher_cap(execution, overhead):
    receipt, expected = envelope_receipt(execution)
    receipt["archive_bytes"] = 1024 ** 2
    receipt["ciphertext_bytes"] = receipt["archive_bytes"] + overhead
    with pytest.raises(package.PackageError, match="ciphertext_overhead_limit"):
        package._receipt(receipt, expected)


@pytest.mark.parametrize("envelope", [None, False, "historical-delivery-envelope-v0", {}, []])
def test_missing_or_unknown_delivery_envelope_refused(execution, envelope):
    receipt, expected = envelope_receipt(execution)
    if envelope is None:
        del receipt["delivery_envelope"]
        reason = "invalid_receipt"
    else:
        receipt["delivery_envelope"] = envelope
        reason = "invalid_delivery_envelope"
    with pytest.raises(package.PackageError, match=reason):
        package._receipt(receipt, expected)


@pytest.mark.parametrize("schema", [package.LEGACY_SCHEMA, package.PREVIOUS_SCHEMA])
def test_old_receipt_cannot_declare_the_new_envelope(execution, schema):
    receipt, expected = envelope_receipt(execution, schema)
    receipt["delivery_envelope"] = package.DELIVERY_ENVELOPE
    with pytest.raises(package.PackageError, match="invalid_receipt"):
        package._receipt(receipt, expected)


@pytest.mark.parametrize("schema", [package.PREVIOUS_SCHEMA, package.SCHEMA])
def test_receipt_version_requires_its_exact_compatibility_contract(execution, schema):
    receipt, expected = envelope_receipt(execution, schema)
    wrong = (package.PREVIOUS_COMPATIBILITY_CONTRACT_SHA256 if schema == package.SCHEMA
             else execution_guard.COMPATIBILITY_CONTRACT_SHA256)
    assert wrong != receipt["compatibility_contract_sha256"]
    receipt["compatibility_contract_sha256"] = expected["compatibility_contract_sha256"] = wrong
    with pytest.raises(package.PackageError, match="invalid_execution_identity"):
        package._receipt(receipt, expected)


def test_new_writer_refuses_old_compatibility_contract_before_compression(source, execution, tmp_path, monkeypatch):
    execution["compatibility_contract_sha256"] = package.PREVIOUS_COMPATIBILITY_CONTRACT_SHA256
    monkeypatch.setattr(package, "_write_archive", lambda *a: pytest.fail("compression must not start"))
    with pytest.raises(package.PackageError, match="invalid_execution_identity"):
        package.package_evidence(source[1], source[0], tmp_path / "delivery", age_binary="unused",
                                 recipient=RECIPIENT, execution=execution)


@pytest.mark.parametrize("fault", ["missing", "unknown", "receipt_downgrade", "index_downgrade"])
def test_authenticated_index_envelope_and_schema_must_match_receipt(source, execution, tmp_path, fault):
    archive, receipt = archive_with_fault(tmp_path, source, execution, None, legacy=False)
    raw = package.codec._zstandard().ZstdDecompressor().decompress(archive.read_bytes())
    with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
        payloads = {member.name: tar.extractfile(member).read() for member in tar.getmembers()}
    index = json.loads(payloads["_package/index.json"])
    if fault == "missing":
        del index["delivery_envelope"]
    elif fault == "unknown":
        index["delivery_envelope"] = "historical-delivery-envelope-v0"
    elif fault == "receipt_downgrade":
        receipt["schema"] = package.PREVIOUS_SCHEMA
        del receipt["delivery_envelope"]
    else:
        index["schema"] = package.PREVIOUS_INDEX_SCHEMA
        del index["delivery_envelope"]
    payloads["_package/index.json"] = encode(index)
    body = io.BytesIO()
    with tarfile.open(fileobj=body, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for name, payload in payloads.items():
            package._entry(tar, name, io.BytesIO(payload), len(payload))
    archive.write_bytes(_compressed(body.getvalue(), package.codec.FORMAT))
    destination = tmp_path / "candidate"
    destination.mkdir()
    with pytest.raises(package.PackageError, match="package_identity_mismatch"):
        package._unpack(archive, destination, source[0], receipt, execution)
    assert not list(destination.iterdir()) and not list(tmp_path.glob(".tar-*"))


def test_writer_overhead_failure_preserves_sources_and_promotes_nothing(source, execution, tmp_path, monkeypatch):
    before = {p.relative_to(source[1]).as_posix(): p.read_bytes() for p in source[1].rglob("*") if p.is_file()}
    monkeypatch.setattr(package, "MAX_CIPHERTEXT_OVERHEAD_BYTES", 32)
    def oversized(_binary, arguments, output, *, reason, limit):
        archive_bytes = Path(arguments[-1]).stat().st_size
        assert limit == archive_bytes + 32
        output.write_bytes(package.AGE_HEADER + bytes(archive_bytes + 33 - len(package.AGE_HEADER)))
    monkeypatch.setattr(package, "_age", oversized)
    with pytest.raises(package.PackageError, match="ciphertext_overhead_limit"):
        package.package_evidence(source[1], source[0], tmp_path / "delivery", age_binary="unused",
                                 recipient=RECIPIENT, execution=execution)
    assert not (tmp_path / "delivery").exists() and not list(source[1].glob(".package-*"))
    assert all((source[1] / name).read_bytes() == raw for name, raw in before.items())


@pytest.mark.parametrize("field", ["compatibility_contract_sha256", "release_evidence_sha256"])
def test_new_writer_requires_each_new_identity_digest(source, execution, tmp_path, monkeypatch, field):
    execution.pop(field)
    monkeypatch.setattr(package, "_write_archive", lambda *a: pytest.fail("archive must not start"))
    with pytest.raises(package.PackageError, match="invalid_execution_metadata"):
        package.package_evidence(source[1], source[0], tmp_path / "delivery", age_binary="unused",
                                 recipient=RECIPIENT, execution=execution)


@pytest.mark.parametrize("field,value", [("archive_format", "ustar-xz-v1"),
                                        ("ciphertext_name", "../evidence.tar.zst.age"),
                                        ("archive_bytes", package.MAX_ARCHIVE_BYTES + 1),
                                        ("archive_bytes", True), ("archive_sha256", "bad")])
def test_unsupported_receipt_refuses_before_identity_or_decryption(source, execution, age, tmp_path, monkeypatch, field, value):
    delivery, receipt = seal(source, execution, age, tmp_path)
    receipt[field] = value
    monkeypatch.setattr(package, "_age", lambda *a, **kw: pytest.fail("decryption must not start"))
    with pytest.raises(package.PackageError, match="invalid_archive_receipt"):
        package.recover_package(delivery / package.CIPHERTEXT_NAME, receipt, tmp_path / "recovered",
                                age_binary=age[0], identity="does-not-exist", manifest=source[0],
                                expected_execution=execution)


def test_archive_metrics_include_index_and_actual_tar_framing(source, execution, tmp_path, monkeypatch):
    measured = []
    original = package._write_archive
    def observe(*args):
        result = original(*args)
        measured.append(result)
        return result
    monkeypatch.setattr(package, "_write_archive", observe)
    monkeypatch.setattr(package, "MAX_ARCHIVE_BYTES", 1)
    with pytest.raises(package.PackageError, match="package_size_or_member_limit"):
        package.package_evidence(source[1], source[0], tmp_path / "delivery", age_binary="unused",
                                 recipient=RECIPIENT, execution=execution)
    metrics, = measured
    assert metrics["archive_format"] == package.codec.FORMAT
    assert metrics["archive_bytes"] > 1 and len(metrics["archive_sha256"]) == 64
    assert metrics["index_bytes"] > 0
    assert metrics["tar_archive_bytes"] % tarfile.RECORDSIZE == 0
    assert metrics["tar_archive_bytes"] > metrics["expanded_payload_bytes"]
    assert not list(source[1].glob(".package-*"))


def test_writer_refuses_metadata_the_reader_cannot_allocate(source, execution, tmp_path, monkeypatch):
    limit = max(len(encode(source[0])), len(encode(execution)))
    monkeypatch.setattr(package, "MAX_INDEX_BYTES", limit)
    monkeypatch.setattr(package, "_write_archive", lambda *a: pytest.fail("archive must not start"))
    with pytest.raises(package.PackageError, match="package_metadata_too_large"):
        package.package_evidence(source[1], source[0], tmp_path / "delivery", age_binary="unused",
                                 recipient=RECIPIENT, execution=execution, diagnostics={"test": "x" * limit})
    assert not (tmp_path / "delivery").exists()


def test_interrupted_archive_never_creates_delivery_and_retains_sources(source, execution, tmp_path, monkeypatch):
    before = {p.relative_to(source[1]).as_posix(): p.read_bytes() for p in source[1].rglob("*") if p.is_file()}
    def interrupted(archive, *args):
        archive.write_bytes(SENTINEL.encode())
        raise KeyboardInterrupt
    monkeypatch.setattr(package, "_write_archive", interrupted)
    with pytest.raises(KeyboardInterrupt):
        package.package_evidence(source[1], source[0], tmp_path / "delivery", age_binary="unused",
                                 recipient=RECIPIENT, execution=execution)
    assert not list(source[1].glob(".package-*")) and not (tmp_path / "delivery").exists()
    assert all((source[1] / name).read_bytes() == raw for name, raw in before.items())


def test_interrupted_recovery_never_promotes_or_leaves_plaintext(source, execution, age, tmp_path, monkeypatch):
    delivery, receipt = seal(source, execution, age, tmp_path)
    before = {p.name: p.read_bytes() for p in delivery.iterdir()}
    def interrupted(archive, destination, *args, **kwargs):
        destination.write_bytes(SENTINEL.encode())
        raise KeyboardInterrupt
    monkeypatch.setattr(package.codec, "decode", interrupted)
    with pytest.raises(KeyboardInterrupt):
        package.recover_package(delivery / package.CIPHERTEXT_NAME, receipt, tmp_path / "recovered",
                                age_binary=age[0], identity=age[1][0][0], manifest=source[0],
                                expected_execution=execution)
    assert not (tmp_path / "recovered").exists() and not list(tmp_path.glob(".recovery-*"))
    assert {p.name: p.read_bytes() for p in delivery.iterdir()} == before


def test_authenticated_archive_must_match_outer_receipt(source, execution, age, tmp_path, monkeypatch):
    delivery, receipt = seal(source, execution, age, tmp_path)
    receipt["archive_sha256"] = "0" * 64
    monkeypatch.setattr(package, "_unpack", lambda *a: pytest.fail("decoder must not start"))
    with pytest.raises(package.PackageError, match="archive_receipt_mismatch"):
        package.recover_package(delivery / package.CIPHERTEXT_NAME, receipt, tmp_path / "recovered",
                                age_binary=age[0], identity=age[1][0][0], manifest=source[0],
                                expected_execution=execution)
    assert not (tmp_path / "recovered").exists() and not list(tmp_path.glob(".recovery-*"))


def _compressed(raw, archive_format):
    if archive_format == package.codec.LEGACY_FORMAT:
        return gzip.compress(raw, mtime=0)
    return package.codec._zstandard().ZstdCompressor(write_checksum=True).compress(raw)


@pytest.mark.parametrize("archive_format", [package.codec.FORMAT, package.codec.LEGACY_FORMAT])
def test_codec_valid_single_stream_roundtrip(tmp_path, archive_format, monkeypatch):
    raw = b"public invented fixture bytes\n" * 100000
    archive = tmp_path / "archive"
    archive.write_bytes(_compressed(raw, archive_format))
    monkeypatch.setattr(package.codec, "CHUNK_BYTES", 65536)
    if archive_format == package.codec.LEGACY_FORMAT:
        monkeypatch.setattr(package.codec, "_zstandard", lambda: pytest.fail("legacy recovery must not require zstandard"))
    assert package.codec.decode(archive, tmp_path / "decoded", archive_format, max_decoded=len(raw)) == len(raw)
    assert (tmp_path / "decoded").read_bytes() == raw


@pytest.mark.parametrize("archive_format", [package.codec.FORMAT, package.codec.LEGACY_FORMAT])
@pytest.mark.parametrize("fault", ["truncated", "corrupt", "garbage_tail", "second_frame", "zero_tail"])
def test_codec_rejects_incomplete_corrupt_or_trailing_streams(tmp_path, archive_format, fault):
    original = _compressed(b"synthetic\n" * 10000, archive_format)
    damaged = {"truncated": original[:-1], "corrupt": original[:-1] + bytes([original[-1] ^ 128]),
               "garbage_tail": original + b"junk", "second_frame": original + original,
               "zero_tail": original + b"\0" * 512}[fault]
    archive = tmp_path / "archive"
    archive.write_bytes(damaged)
    with pytest.raises(package.codec.CodecError):
        package.codec.decode(archive, tmp_path / "decoded", archive_format, max_decoded=1024 ** 2)


@pytest.mark.parametrize("archive_format", [package.codec.FORMAT, package.codec.LEGACY_FORMAT])
def test_codec_output_allocation_and_spool_are_bounded(tmp_path, archive_format, monkeypatch):
    archive = tmp_path / "archive"
    archive.write_bytes(_compressed(b"x" * 10000, archive_format))
    monkeypatch.setattr(package.codec, "CHUNK_BYTES", 64)
    with pytest.raises(package.codec.CodecError):
        package.codec.decode(archive, tmp_path / "decoded", archive_format, max_decoded=100)
    assert not (tmp_path / "decoded").exists() or (tmp_path / "decoded").stat().st_size <= 100


@pytest.mark.parametrize("fault", ["no_checksum", "unknown_size", "window", "skippable", "reserved_bit", "dict_id"])
def test_zstandard_resources_rejected_before_decoder_allocation(tmp_path, monkeypatch, fault):
    zstd = package.codec._zstandard()
    raw = b"synthetic" * 100
    if fault in ("no_checksum", "unknown_size"):
        frame = zstd.ZstdCompressor(write_checksum=fault != "no_checksum",
                                   write_content_size=fault != "unknown_size").compress(raw)
    else:
        # Non-single-segment header: known four-byte size, checksum, window
        # descriptor. No payload is needed: rejection precedes decoding.
        descriptor = 0x84 | (1 if fault == "dict_id" else 0)
        window = 0xA8 if fault == "window" else 0x00  # 2 GiB vs 1 KiB.
        frame = b"\x28\xb5\x2f\xfd" + bytes([descriptor, window])
        if fault == "dict_id":
            frame += b"\x01"
        frame += len(raw).to_bytes(4, "little") + b"\x01\x00\x00" + bytes(4)
        if fault == "reserved_bit":
            frame = frame[:4] + bytes([frame[4] | 0x08]) + frame[5:]
        if fault == "skippable":
            frame = b"\x50\x2a\x4d\x18" + frame[4:]
    archive = tmp_path / "archive"
    archive.write_bytes(frame)
    monkeypatch.setattr(zstd, "ZstdDecompressor", lambda *a, **kw: pytest.fail("decoder must not allocate"))
    with pytest.raises(package.codec.CodecError):
        package.codec.decode(archive, tmp_path / "decoded", package.codec.FORMAT, max_decoded=10000)
    assert not (tmp_path / "decoded").exists()


def test_zstandard_window_api_receives_bytes_and_actual_stream_decodes(tmp_path, monkeypatch):
    zstd = package.codec._zstandard()
    original, seen = zstd.ZstdDecompressor, []
    def observe(*args, **kwargs):
        seen.append(kwargs["max_window_size"])
        return original(*args, **kwargs)
    archive = tmp_path / "archive"
    raw = b"synthetic" * 1000
    archive.write_bytes(_compressed(raw, package.codec.FORMAT))
    monkeypatch.setattr(zstd, "ZstdDecompressor", observe)
    assert package.codec.decode(archive, tmp_path / "decoded", package.codec.FORMAT, max_decoded=10000) == len(raw)
    assert (tmp_path / "decoded").read_bytes() == raw
    assert seen == [1024 ** 3]


@pytest.mark.parametrize("field,value", [("__version__", "0.24.0"), ("ZSTD_VERSION", (1, 5, 6)), ("backend", "cffi")])
def test_codec_runtime_version_is_pinned(monkeypatch, field, value):
    zstd = package.codec._zstandard()
    monkeypatch.setattr(zstd, field, value)
    with pytest.raises(package.codec.CodecError, match="archive_codec_version_mismatch"):
        package.codec.compressor(io.BytesIO(), 0)


@pytest.mark.parametrize("fault", ["tar_tail", "tar_second", "tar_zero_record", "bad_end", "index_cap", "metadata_cap", "pax"])
def test_tar_framing_and_true_payload_limit_fail_closed(tmp_path, source, execution, monkeypatch, fault):
    archive, receipt = archive_with_fault(tmp_path, source, execution, None)
    raw = gzip.decompress(archive.read_bytes())
    if fault == "tar_tail":
        raw += b"junk"
    elif fault == "tar_second":
        raw += raw
    elif fault == "tar_zero_record":
        raw += bytes(tarfile.RECORDSIZE)
    elif fault == "bad_end":
        raw = raw[:-1] + b"x"
    elif fault == "index_cap":
        with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
            members = tar.getmembers()
        # The old decoder excluded index.size; this bound admits all remaining
        # payload bytes but must reject the true total including the index.
        monkeypatch.setattr(package, "MAX_PLAINTEXT_BYTES", sum(m.size for m in members[1:]))
    elif fault == "metadata_cap":
        # A tiny bound refuses metadata before reading its claimed payload.
        monkeypatch.setattr(package, "MAX_INDEX_BYTES", 1)
    elif fault == "pax":
        info = tarfile.TarInfo("_package/index.json")
        info.type, info.size = tarfile.XHDTYPE, 2 ** 30
        raw = info.tobuf(format=tarfile.USTAR_FORMAT) + bytes(1024)
    archive.write_bytes(gzip.compress(raw))
    destination = tmp_path / "candidate"
    destination.mkdir()
    legacy = {k: v for k, v in execution.items() if k in package._LEGACY_EXECUTION_KEYS | {"started_at"}}
    with pytest.raises(package.PackageError):
        package._unpack(archive, destination, source[0], receipt, legacy)
    assert not list(tmp_path.glob(".tar-*"))
