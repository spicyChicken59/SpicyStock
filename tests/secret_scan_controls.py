"""Offline regression of the exact public-hash disposition with gitleaks 8.24.3.

Run explicitly with an installed, verified binary; this never downloads tools.
Only invented canaries and retained public evidence enter scratch.
No provider credentials, network calls, Git writes or broad scanner exclusions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OBSERVATION = "docs/input-truthfulness/2026-09-30-delivery-readiness-evidence/candidate-final-ci/secret_scan-api.json"
PUBLIC_VALUES = (
    "f5d4b3ca6e7b8b3d1af734970650a8a06b7ba7b564abadfeda221528461f9ef2",
    "c10038851e257ac00a9966242e290a1436d8e6d6c5151807e1e8d7cf3338ec62",
)
BOUNDED_BASE = "docs/input-truthfulness/2026-09-30-delivery-readiness-evidence/bounded-correction/"
BOUNDED_PATHS = tuple(BOUNDED_BASE + name for name in (
    "window31-supervisor.json", "window31-supervisor.py", "focused-tests.json",
))
# Historical public file identities verified at 65cd32ba; these are not the
# fingerprints of the evolving test/support files in the current checkout.
BOUNDED_VALUES = (
    "1549c7049be32695594bedd09bbd352a94b6013a9d5c43364f3c6cd7a09ab61c",
    "a464d9f76c8eb0567a4a1e7aaad6b1ef18cdcc90a03177426dd678fb74999a6e",
    "cf38490f275becfe955beac6fb98bc0081201ccaaff18cc8ae6478b26da7cb5d",
)
NATIVE5_PRESERVATION = "docs/input-truthfulness/2026-09-30-delivery-readiness-evidence/native5-recovery/preservation.json"
NATIVE5_WORKFLOW = ".github/workflows/secret-scan.yml"
NATIVE5_PUBLIC_BLOB = "f568689c3789a53835708b676ef6c2dcc418fd6f"
PUBLIC_SITE_CAPTURE = "release-evidence/2026-10-10-zim/ir-merger-announcement.html"
PUBLIC_SITE_CAPTURE_SHA256 = "32b3411f00b61f712fff475a3b69d63a5de1f8589c71fee4afb6adfc8637a519"


def public_site_capture():
    """Read the pinned public HTML; never log its client identifier."""
    raw = (ROOT / PUBLIC_SITE_CAPTURE).read_bytes()
    manifest = json.loads((ROOT / PUBLIC_SITE_CAPTURE).with_name("manifest.json").read_bytes())
    capture = next(row for row in manifest["captures"] if row["file"] == Path(PUBLIC_SITE_CAPTURE).name)
    if (hashlib.sha256(raw).hexdigest() != PUBLIC_SITE_CAPTURE_SHA256
            or capture["sha256"] != PUBLIC_SITE_CAPTURE_SHA256
            or capture["bytes"] != len(raw)):
        raise ValueError("public_site_capture_changed")
    matches = re.findall(rb"grecaptcha\.render\('[^']+',\s*\{\s*'sitekey':\s*'([^']+)'", raw)
    if len(matches) != 1:
        raise ValueError("public_site_client_context_changed")
    return raw, matches[0].decode("ascii")


def native5_public_preservation():
    raw = (ROOT / NATIVE5_PRESERVATION).read_bytes()
    document = json.loads(raw)
    # Git blob identity uses the object header and SHA-1, not content SHA-256.
    # LF represents the public Git object, including on a CRLF Windows checkout.
    source = (ROOT / NATIVE5_WORKFLOW).read_bytes().replace(b"\r\n", b"\n")
    blob = hashlib.sha1(b"blob " + str(len(source)).encode() + b"\0" + source).hexdigest()
    if (document["protected_git_objects"][NATIVE5_WORKFLOW] != NATIVE5_PUBLIC_BLOB
            or blob != NATIVE5_PUBLIC_BLOB):
        raise ValueError("retained_public_workflow_blob_changed")
    return raw


def retained_documents():
    documents = [(ROOT / path).read_bytes() for path in BOUNDED_PATHS]
    report = json.loads(documents[0])
    focused = json.loads(documents[2])
    expected = (
        report["age_keygen_binary_sha256"] == BOUNDED_VALUES[0],
        f'KEYGEN_SHA = "{BOUNDED_VALUES[0]}"' in documents[1].decode("utf-8"),
        focused["source_sha256"]["tests/secret_scan_controls.py"] == BOUNDED_VALUES[1],
        focused["source_sha256"]["tests/test_secret_scan.py"] == BOUNDED_VALUES[2],
    )
    if not all(expected):
        raise ValueError("retained_public_file_identity_changed")
    return documents


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def scan(binary, config, workspace, path, raw):
    source = workspace / "scan"
    source.mkdir(parents=True)
    target = source / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    empty_ignore = workspace / "empty.ignore"
    empty_ignore.write_bytes(b"")
    report = workspace / "findings.json"
    # Relative '.' yields the same anchored repository-relative paths as git
    # mode. Absolute dir arguments report an absolute path on Windows/Linux.
    command = [str(binary), "dir", "--no-banner", "--no-color", "--redact=100",
               "--ignore-gitleaks-allow", "--gitleaks-ignore-path", str(empty_ignore),
               "--config", str(config), "--report-format", "json", "--report-path",
               str(report), "--exit-code", "2", "."]
    env = {key: value for key, value in os.environ.items()
           if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}}
    result = subprocess.run(command, cwd=source, env=env, capture_output=True, timeout=30)
    findings = json.loads(report.read_bytes()) if report.is_file() else None
    return {"exit_code": result.returncode, "rule_ids": sorted(row["RuleID"] for row in findings) if isinstance(findings, list) else None,
            "finding_paths": sorted({row["File"] for row in findings}) if isinstance(findings, list) else None,
            "report_sha256": sha(report.read_bytes()) if report.is_file() else None,
            "diagnostic_sha256": sha(result.stdout + result.stderr)}


def run_controls(binary: Path, workspace: Path):
    binary = binary.resolve(strict=True)
    workspace = workspace.resolve()
    if workspace.exists() or workspace.is_relative_to(ROOT):
        raise ValueError("fresh_scratch_outside_repository_required")
    version = subprocess.run([str(binary), "version"], capture_output=True, check=True, timeout=10).stdout.decode().strip()
    if version != "8.24.3":
        raise ValueError("gitleaks_8_24_3_required")
    observation = (ROOT / OBSERVATION).read_bytes()
    document = json.loads(observation)
    if tuple(document["retained_response_sha256"].values()) != PUBLIC_VALUES:
        raise ValueError("public_observation_identity_changed")
    workspace.mkdir(parents=True, exist_ok=False)
    baseline = workspace / "defaults.toml"
    baseline.write_bytes(b"[extend]\nuseDefault = true\n")
    config = ROOT / ".gitleaks.toml"
    canary = hashlib.sha256(b"unrelated invented scanner regression value").hexdigest()
    other_value = encode({"api_key": canary})
    token = "gh" + "p_" + hashlib.sha256(b"invented default-detector regression").hexdigest()[:36]
    default_detector = encode({"value": token})
    cases = [
        ("without_disposition", baseline, OBSERVATION, observation, 2, ["generic-api-key"] * 2),
        ("exact_public_observation", config, OBSERVATION, observation, 0, []),
        ("unrelated_value_same_path", config, OBSERVATION, other_value, 2, ["generic-api-key"]),
        ("same_values_other_file", config, OBSERVATION.replace("secret_scan-api.json", "another.json"), observation, 2, ["generic-api-key"] * 2),
        ("same_values_path_suffix", config, OBSERVATION + ".backup", observation, 2, ["generic-api-key"] * 2),
        ("same_values_path_prefix", config, "copied/" + OBSERVATION, observation, 2, ["generic-api-key"] * 2),
        ("different_default_detector", config, OBSERVATION, default_detector, 2, ["github-pat"]),
    ]
    documents = retained_documents()
    for index, (path, raw) in enumerate(zip(BOUNDED_PATHS, documents)):
        label = ("supervisor_receipt", "supervisor_source", "focused_receipt")[index]
        detected = ["generic-api-key"] * (2 if index == 2 else 1)
        crossed = BOUNDED_VALUES[0] if index == 2 else BOUNDED_VALUES[1]
        cases.extend([
            (label + "_defaults", baseline, path, raw, 2, detected),
            (label + "_exact", config, path, raw, 0, []),
            (label + "_unrelated", config, path, other_value, 2, ["generic-api-key"]),
            (label + "_elsewhere", config, path + ".backup", raw, 2, detected),
            (label + "_crossed", config, path, encode({"api_key": crossed}), 2, ["generic-api-key"]),
            (label + "_default_detector", config, path, default_detector, 2, ["github-pat"]),
        ])
    preservation = native5_public_preservation()
    cases.extend([
        ("native5_preservation_defaults", baseline, NATIVE5_PRESERVATION, preservation, 2, ["generic-api-key"]),
        ("native5_preservation_exact", config, NATIVE5_PRESERVATION, preservation, 0, []),
        ("native5_unrelated_same_path", config, NATIVE5_PRESERVATION, other_value, 2, ["generic-api-key"]),
        ("native5_original_other_path", config, NATIVE5_PRESERVATION.replace("preservation.json", "another.json"), preservation, 2, ["generic-api-key"]),
        ("native5_original_path_suffix", config, NATIVE5_PRESERVATION + ".backup", preservation, 2, ["generic-api-key"]),
        ("native5_original_path_prefix", config, "copied/" + NATIVE5_PRESERVATION, preservation, 2, ["generic-api-key"]),
        ("native5_default_detector", config, NATIVE5_PRESERVATION, default_detector, 2, ["github-pat"]),
    ])
    site_capture, public_identifier = public_site_capture()
    changed_identifier = ("A" if public_identifier[0] != "A" else "B") + public_identifier[1:]
    cases.extend([
        ("public_site_defaults", baseline, PUBLIC_SITE_CAPTURE, site_capture, 2, ["generic-api-key"]),
        ("public_site_exact", config, PUBLIC_SITE_CAPTURE, site_capture, 0, []),
        ("public_site_unrelated_same_path", config, PUBLIC_SITE_CAPTURE, other_value, 2, ["generic-api-key"]),
        ("public_site_altered_value", config, PUBLIC_SITE_CAPTURE,
         site_capture.replace(public_identifier.encode(), changed_identifier.encode()), 2, ["generic-api-key"]),
        ("public_site_other_path", config, PUBLIC_SITE_CAPTURE.replace("ir-merger-announcement.html", "another.html"),
         site_capture, 2, ["generic-api-key"]),
        ("public_site_path_suffix", config, PUBLIC_SITE_CAPTURE + ".backup", site_capture, 2, ["generic-api-key"]),
        ("public_site_path_prefix", config, "copied/" + PUBLIC_SITE_CAPTURE, site_capture, 2, ["generic-api-key"]),
        ("public_site_default_detector", config, PUBLIC_SITE_CAPTURE, default_detector, 2, ["github-pat"]),
    ])
    results = []
    for index, (name, selected_config, path, raw, code, rules) in enumerate(cases):
        # Keep scratch prefixes short for the existing deeply nested evidence
        # paths on Windows. Human-readable case names remain in the receipt.
        actual = scan(binary, selected_config, workspace / str(index), path, raw)
        success = actual["exit_code"] == code and actual["rule_ids"] == rules
        if rules:
            success = success and actual["finding_paths"] == [path]
        results.append({"case": name, "status": "PASS" if success else "FAIL", "expected_exit_code": code,
                        "expected_rule_ids": rules, **actual})
    return {"schema": "historical-exact-disposition-controls-v3", "status": "PASS" if all(r["status"] == "PASS" for r in results) else "FAIL",
            "scope": "Actual offline gitleaks 8.24.3 on isolated public evidence and invented canaries; not a credential or provider test.",
            "version": version, "binary_sha256": sha(binary.read_bytes()), "config_sha256": sha(config.read_bytes()),
            "observation_path": OBSERVATION, "observation_sha256": sha(observation), "results": results,
            "retained_documents": [{"path": path, "sha256": sha(raw)} for path, raw in zip(BOUNDED_PATHS, documents)],
            "native5_preservation": {"path": NATIVE5_PRESERVATION, "sha256": sha(preservation),
                                     "public_workflow_path": NATIVE5_WORKFLOW, "public_git_blob": NATIVE5_PUBLIC_BLOB},
            "public_site_capture": {"path": PUBLIC_SITE_CAPTURE, "sha256": sha(site_capture)},
            "network_requests": 0, "provider_requests": 0, "repository_writes": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gitleaks", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    receipt = args.receipt.resolve()
    if receipt.exists() or receipt.is_relative_to(ROOT):
        parser.error("receipt must be fresh and outside the repository")
    result = run_controls(args.gitleaks, args.workspace)
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_bytes(encode(result))
    print(json.dumps({"status": result["status"], "cases": len(result["results"]), "version": result["version"]}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
