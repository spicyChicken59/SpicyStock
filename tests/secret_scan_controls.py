"""Offline regression of the exact public-hash disposition with gitleaks 8.24.3.

Run explicitly with an installed, verified binary; this never downloads tools.
Only invented canaries and the existing public CI observation enter scratch.
No provider credentials, network calls, Git writes or broad scanner exclusions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OBSERVATION = "docs/input-truthfulness/2026-09-30-delivery-readiness-evidence/candidate-final-ci/secret_scan-api.json"
PUBLIC_VALUES = (
    "f5d4b3ca6e7b8b3d1af734970650a8a06b7ba7b564abadfeda221528461f9ef2",
    "c10038851e257ac00a9966242e290a1436d8e6d6c5151807e1e8d7cf3338ec62",
)


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
    results = []
    for name, selected_config, path, raw, code, rules in cases:
        actual = scan(binary, selected_config, workspace / name, path, raw)
        success = actual["exit_code"] == code and actual["rule_ids"] == rules
        if rules:
            success = success and actual["finding_paths"] == [path]
        results.append({"case": name, "status": "PASS" if success else "FAIL", "expected_exit_code": code,
                        "expected_rule_ids": rules, **actual})
    return {"schema": "historical-exact-disposition-controls-v1", "status": "PASS" if all(r["status"] == "PASS" for r in results) else "FAIL",
            "scope": "Actual offline gitleaks 8.24.3 on isolated public evidence and invented canaries; not a credential or provider test.",
            "version": version, "binary_sha256": sha(binary.read_bytes()), "config_sha256": sha(config.read_bytes()),
            "observation_path": OBSERVATION, "observation_sha256": sha(observation), "results": results,
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
