"""Actual age recovery plus fail-closed packaging of the actual acquisition cache."""
from copy import deepcopy
import hashlib
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
from tools.historical_acquisition import cached_pages, encode, validate_manifest


RECIPIENT = "age1ql3z7hjy54pw3hyww5ayyfg7zqgvc7w3j2elw8zmrj2kg5sfn9aqmcac8p"
SENTINEL = "PRIVATE_SYNTHETIC_SENTINEL_54e9aa1f"


@pytest.fixture
def execution():
    return {"repository": package.REPOSITORY, "assignment_id": package.ASSIGNMENT,
            "run_id": "123456", "run_attempt": "1", "workflow_sha": "1" * 40,
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


def test_ciphertext_limit_is_fixed_and_separate_from_response_budget():
    assert package.MAX_CIPHERTEXT_BYTES == 200 * 1024 ** 2
    assert package.MAX_PLAINTEXT_BYTES == 2 * 1024 ** 3


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
    wrong = {**execution, "run_id": "9999"}
    with pytest.raises(package.PackageError, match="receipt_execution_mismatch"):
        package.recover_package(delivery / package.CIPHERTEXT_NAME, receipt, tmp_path / "recovered",
                    age_binary=age[0], identity=age[1][0][0], manifest=source[0], expected_execution=wrong)


def archive_with_fault(tmp_path, source, execution, fault):
    """Exercise recovery format directly, without needing an encryption stub."""
    manifest, storage = source
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
    index = {"schema": package.INDEX_SCHEMA, "manifest_sha256": identity, "execution": execution,
             "recipient_sha256": package.recipient_fingerprint(RECIPIENT),
             "members": [{"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
                         for name, raw in payloads.items()]}
    archive = tmp_path / "malicious.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
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
    receipt = {"manifest_sha256": identity, "recipient_sha256": index["recipient_sha256"]}
    return archive, receipt


@pytest.mark.parametrize("fault", ["traversal", "symlink", "hardlink", "unapproved", "duplicate", "missing_ledger", "hash"])
def test_safe_archive_recovery_rejects_unsafe_members(tmp_path, source, execution, fault):
    archive, receipt = archive_with_fault(tmp_path, source, execution, fault)
    destination = tmp_path / "candidate"
    destination.mkdir()
    with pytest.raises(package.PackageError):
        package._unpack(archive, destination, source[0], receipt, execution)
    assert not (tmp_path / "escaped").exists()


def test_hardlinked_source_is_not_permitted(source, execution, tmp_path):
    manifest, storage = source
    os.link(storage / "ledger.sqlite3", tmp_path / "second-ledger-link")
    with pytest.raises(package.PackageError, match="nonregular_package_file"):
        package.package_evidence(storage, manifest, tmp_path / "delivery", age_binary="unused",
                                 recipient=RECIPIENT, execution=execution)


def test_guard_projection_keeps_approval_text_out_of_public_metadata(execution):
    guard = {**execution, "schema": "historical-execution-v1", "run_id": 123456, "run_attempt": 1,
             "readiness_status": "PASS", "lifetime_status": "PASS", "evidence": {"private": SENTINEL}}
    projected = package.execution_metadata(guard, status="BLOCKED")
    assert SENTINEL not in json.dumps(projected)
    assert projected["status"] == "BLOCKED"
    assert projected["run_id"] == "123456"


def test_real_age_cli_path_packages_and_recovers_actual_cache(source, execution, age, tmp_path):
    manifest, storage = source
    (storage / "execution-diagnostics.json").write_bytes(encode({"status": "PASS", "sentinel": SENTINEL}))
    guard = {**execution, "schema": "historical-execution-v1", "run_id": 123456, "run_attempt": 1,
             "readiness_status": "PASS", "lifetime_status": "PASS",
             "manifest_sha256": validate_manifest(manifest),
             "recipient_sha256": package.recipient_fingerprint(age[1][0][1]),
             "evidence": {"private": SENTINEL}}
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
