"""Native workflow semantics and the actual early/later Bash path contract.

Broken expression controls are temporary files outside .github/workflows. No
test dispatches a workflow, runs an installer, or calls a provider.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import yaml

from tools import install_actionlint

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/historical-input-proof.yml"
VALID_CONTROL = ROOT / "tests/fixtures/workflow-validation/valid-step-context.yml"
ORIGINAL_PREFLIGHT = ROOT / "tests/fixtures/workflow-validation/native5-original-preflight.sh"
ORIGINAL_PREFLIGHT_SHA256 = "62f19a890100170a23c1290d5de83d2b81f4f9c45f1fe7b83f05622a3c5b4e4a"


def workflow():
    return yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


@pytest.fixture(scope="module")
def actionlint():
    binary = os.environ.get("ACTIONLINT_BINARY") or shutil.which("actionlint")
    if not binary:
        if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
            pytest.fail("normal CI must install the pinned semantic workflow validator")
        pytest.skip("actionlint NOT RUN: set ACTIONLINT_BINARY to verified v1.7.12")
    version = subprocess.run([binary, "-version"], capture_output=True, text=True, check=False)
    assert version.returncode == 0 and version.stdout.splitlines()[0] == install_actionlint.VERSION
    return binary


def lint(binary, paths):
    # These switches disable only optional external tools. Native workflow
    # syntax, expression and context-availability checks remain unsuppressed.
    return subprocess.run([binary, "-no-color", "-shellcheck=", "-pyflakes=", *map(str, paths)],
                          cwd=ROOT, capture_output=True, text=True, check=False)


def test_corrected_changed_workflows_and_unchanged_valid_control_pass_actionlint(actionlint):
    control_hash = hashlib.sha256(VALID_CONTROL.read_bytes()).hexdigest()
    result = lint(actionlint, [WORKFLOW, ROOT / ".github/workflows/tests.yml", VALID_CONTROL])
    assert result.returncode == 0, result.stdout + result.stderr
    assert not result.stdout and not result.stderr
    assert hashlib.sha256(VALID_CONTROL.read_bytes()).hexdigest() == control_hash


@pytest.mark.parametrize("name,value", [
    ("HISTORICAL_ROOT", "${{ runner.temp }}/historical-input-${{ github.run_id }}-${{ github.run_attempt }}"),
    ("MPLCONFIGDIR", "${{ runner.temp }}/historical-matplotlib"),
])
def test_each_restored_job_context_defect_fails_independently(actionlint, tmp_path, name, value):
    source = WORKFLOW.read_text(encoding="utf-8")
    assert source.count("\n    env:\n") == 1
    broken = source.replace("\n    env:\n", "\n    env:\n      " + name + ": " + value + "\n", 1)
    path = tmp_path / ("restored-" + name.lower() + ".yml")
    path.write_text(broken, encoding="utf-8")
    before = VALID_CONTROL.read_bytes()
    result = lint(actionlint, [path, VALID_CONTROL])
    assert result.returncode != 0
    diagnostics = result.stdout + result.stderr
    assert diagnostics.count('context "runner" is not allowed here') == 1
    assert "[expression]" in diagnostics and name in diagnostics
    assert "valid-step-context.yml:" not in diagnostics
    assert VALID_CONTROL.read_bytes() == before


def test_both_restored_contexts_reproduce_the_original_failure(actionlint, tmp_path):
    source = WORKFLOW.read_text(encoding="utf-8").replace("\n    env:\n", "\n    env:\n"
        "      HISTORICAL_ROOT: ${{ runner.temp }}/historical-input-${{ github.run_id }}-${{ github.run_attempt }}\n"
        "      MPLCONFIGDIR: ${{ runner.temp }}/historical-matplotlib\n", 1)
    path = tmp_path / "restored-both.yml"
    path.write_text(source, encoding="utf-8")
    result = lint(actionlint, [path])
    assert result.returncode != 0
    assert (result.stdout + result.stderr).count('context "runner" is not allowed here') == 2


@pytest.fixture
def bash():
    binary = os.environ.get("BASH_BINARY") or shutil.which("bash")
    if not binary and os.name == "nt":
        candidate = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe"
        if candidate.is_file():
            binary = str(candidate)
    if not binary:
        pytest.fail("Bash is required to execute the workflow path regression")
    return binary


def shell_path(bash, path):
    if os.name != "nt":
        return str(path)
    result = subprocess.run([bash, "--noprofile", "--norc", "-c", '/usr/bin/cygpath.exe -u -- "$1"', "convert", str(path)],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.fixture
def path_runtime(tmp_path, bash):
    temporary = tmp_path / "runner temp with spaces"
    workspace = tmp_path / "checkout with spaces"
    temporary.mkdir()
    workspace.mkdir()
    environment_file = tmp_path / "github-env"
    environment_file.write_text("")
    output_file = tmp_path / "github-output"
    output_file.write_text("")
    capture = tmp_path / "same-step"
    env = {k: v for k, v in os.environ.items() if k not in {
        "HISTORICAL_ROOT", "MPLCONFIGDIR", "READINESS_COMMENT_ID", "RAW_READINESS_COMMENT_ID",
        "ALPACA_API_KEY", "ALPACA_SECRET_KEY", "ANTHROPIC_API_KEY"}}
    if os.name == "nt":
        # No login profile or mutable user aliases: Git Bash's packaged POSIX
        # utilities are the local equivalent of the Linux runner's coreutils.
        env = {k: v for k, v in env.items() if k.lower() != "path"}
        env["PATH"] = "/usr/bin:/bin"
    env.update(GITHUB_REPOSITORY="spicyChicken59/SpicyStock", GITHUB_REPOSITORY_ID="1352997802",
               GITHUB_REF="refs/heads/main", GITHUB_EVENT_NAME="workflow_dispatch", GITHUB_RUN_ATTEMPT="1",
               GITHUB_RUN_NUMBER="6", GITHUB_RUN_ID="123456", RAW_READINESS_COMMENT_ID="999", MODE="real",
               RUNNER_TEMP=shell_path(bash, temporary), GITHUB_WORKSPACE=shell_path(bash, workspace),
               GITHUB_ENV=shell_path(bash, environment_file), PATH_CAPTURE=shell_path(bash, capture),
               GITHUB_OUTPUT=shell_path(bash, output_file),
               MANIFEST="docs/input-truthfulness/2026-09-28-historical-input-evidence/acquisition-manifest.json",
               POLICY="tools/historical-execution-policy.json")
    return temporary, workspace, environment_file, capture, env


def boundary_outputs(path_runtime):
    output = path_runtime[1].parent / "github-output"
    return dict(line.split("=", 1) for line in output.read_text().splitlines())


def run_shell(bash, script, env, workspace):
    return subprocess.run([bash, "--noprofile", "--norc", "-e", "-c", script], env=env,
                          cwd=workspace, capture_output=True, text=True, check=False)


def initialize(bash, path_runtime, script=None):
    temporary, workspace, env_file, capture, env = path_runtime
    script = script if script is not None else workflow()["jobs"]["execution"]["steps"][0]["run"]
    # Child shell proves exports work within this step, before GITHUB_ENV is
    # consumed by a later step. Merely appending that file cannot satisfy this.
    script += '\nbash -c \'test -d "$HISTORICAL_ROOT" && test -d "$MPLCONFIGDIR" && printf "%s\\n%s\\n" "$HISTORICAL_ROOT" "$MPLCONFIGDIR" > "$PATH_CAPTURE"\'\n'
    return run_shell(bash, script, env, workspace)


def test_actual_initialization_exports_same_step_and_later_consumers_keep_one_external_tree(path_runtime, bash, tmp_path):
    temporary, workspace, env_file, capture, env = path_runtime
    result = initialize(bash, path_runtime)
    assert result.returncode == 0, result.stderr
    shared = dict(line.split("=", 1) for line in env_file.read_text().splitlines())
    assert set(shared) == {"HISTORICAL_ROOT", "MPLCONFIGDIR"}
    assert capture.read_text().splitlines() == [shared["HISTORICAL_ROOT"], shared["MPLCONFIGDIR"]]
    assert boundary_outputs(path_runtime) == {"readiness_comment_id": "999"}
    expected = temporary / "historical-input-123456-1"
    assert expected.is_dir() and (expected / "matplotlib").is_dir()
    assert workspace not in expected.parents
    if os.name != "nt":
        assert expected.stat().st_mode & 0o777 == 0o700
        assert (expected / "matplotlib").stat().st_mode & 0o777 == 0o700
    env.update(shared)
    calls = tmp_path / "python-arguments"
    env["PATH_CALLS"] = shell_path(bash, calls)
    spy = 'python() { printf "%s\\0" "$@" >> "$PATH_CALLS"; printf "\\0" >> "$PATH_CALLS"; }; export -f python\n'
    checks = 0
    for step in workflow()["jobs"]["execution"]["steps"][1:]:
        if step.get("uses", "").startswith("actions/checkout@"):
            checks += 1
            # Both checkout actions operate in this workspace. A replacement
            # of its contents cannot touch the separately created scratch tree.
            marker = workspace / "checkout-marker"
            marker.write_text(str(checks))
            assert expected.is_dir()
        elif "run" in step and step["name"] != "Bind public receipt to the immutable artifact identity":
            step_env = dict(env)
            if step.get("id") == "guard":
                assert step["env"]["READINESS_COMMENT_ID"] == "${{ steps.boundary.outputs.readiness_comment_id }}"
                step_env["READINESS_COMMENT_ID"] = boundary_outputs(path_runtime)["readiness_comment_id"]
            result = run_shell(bash, spy + step["run"], step_env, workspace)
            assert result.returncode == 0, step["name"] + ": " + result.stderr
    assert checks == 2
    arguments = [[v.decode() for v in call.split(b"\0")] for call in calls.read_bytes().split(b"\0\0") if call]
    tools = {args[0] for args in arguments}
    assert {"tools/install_historical_age.py", "tools/historical_execution_guard.py",
            "tools/historical_execution.py", "tools/historical_package.py"} <= tools
    guard_args = next(args for args in arguments if args[0] == "tools/historical_execution_guard.py")
    assert guard_args[guard_args.index("--readiness-comment-id") + 1] == "999"
    expected_paths = {"--destination": "/age", "--storage-root": "/data", "--output-dir": "/guard",
                      "--storage": "/data", "--execution": "/guard/execution.json",
                      "--approval": "/guard/approval.json", "--age": "/age/age",
                      "--delivery": "/delivery", "--scratch": ""}
    for args in arguments:
        for flag, suffix in expected_paths.items():
            if flag in args:
                value = args[args.index(flag) + 1]
                assert value == shared["HISTORICAL_ROOT"] + suffix
    uploads = [s for s in workflow()["jobs"]["execution"]["steps"] if s.get("id") == "artifact"]
    resolved = uploads[0]["with"]["path"].replace("${{ env.HISTORICAL_ROOT }}", shared["HISTORICAL_ROOT"]).splitlines()
    assert resolved == [shared["HISTORICAL_ROOT"] + "/delivery/evidence.tar.zst.age",
                        shared["HISTORICAL_ROOT"] + "/delivery/receipt.json"]
    # Execute the actual final receipt consumer too, using only synthetic data.
    # Git Bash represents the same Windows directory as /c/...; native Python
    # needs its native spelling locally. Linux CI uses the exact exported value.
    receipt_step = workflow()["jobs"]["execution"]["steps"][-1]["run"]
    assert receipt_step.startswith("python - <<'PY'\n") and receipt_step.endswith("\nPY\n")
    body = receipt_step[len("python - <<'PY'\n"):-len("\nPY\n")]
    delivery = expected / "delivery"
    delivery.mkdir()
    (delivery / "receipt.json").write_text('{"fixture": "synthetic"}')
    summary = tmp_path / "step-summary"
    receipt_env = dict(env, ARTIFACT_ID="123", ARTIFACT_DIGEST="a" * 64,
                       GITHUB_STEP_SUMMARY=str(summary))
    if os.name == "nt":
        receipt_env["HISTORICAL_ROOT"] = str(expected)
    receipt_result = subprocess.run([sys.executable, "-c", body], cwd=workspace, env=receipt_env,
                                    capture_output=True, text=True, check=False)
    assert receipt_result.returncode == 0, receipt_result.stderr
    assert json.loads((expected / "artifact-receipt.json").read_text()) == {
        "fixture": "synthetic", "artifact_id": 123, "github_artifact_digest": "a" * 64}
    assert "Local recovery is NOT RUN" in summary.read_text()
    assert not (workspace / "artifact-receipt.json").exists()


def test_same_step_child_refuses_the_restored_missing_export_defect(path_runtime, bash):
    script = workflow()["jobs"]["execution"]["steps"][0]["run"]
    assert script.count("export HISTORICAL_ROOT MPLCONFIGDIR") == 1
    result = initialize(bash, path_runtime, script.replace("export HISTORICAL_ROOT MPLCONFIGDIR", ": # removed exports"))
    assert result.returncode != 0
    assert not path_runtime[3].exists()


def original_preflight():
    # Exact extracted first-step bytes from the incident's workflow revision
    # 6979904ad872d8d648c93537c77ead5fda909481, not a duplicate approximation.
    value = ORIGINAL_PREFLIGHT.read_bytes()
    assert hashlib.sha256(value).hexdigest() == ORIGINAL_PREFLIGHT_SHA256
    return value.decode("utf-8")


def test_pinned_original_fails_logged_four_spaces_before_any_path_work(path_runtime, bash):
    env = path_runtime[4]
    env.update(GITHUB_RUN_NUMBER="5", READINESS_COMMENT_ID="    5920107119")
    result = initialize(bash, path_runtime, original_preflight())
    assert result.returncode != 0
    assert not path_runtime[3].exists()
    assert not list(path_runtime[0].glob("historical-input-*"))
    assert not path_runtime[2].read_bytes()
    assert not boundary_outputs(path_runtime)


def test_pinned_original_clean_input_and_root_walk_remain_passing_control(path_runtime, bash):
    env = path_runtime[4]
    env.update(GITHUB_RUN_NUMBER="5", READINESS_COMMENT_ID="5920107119")
    assert initialize(bash, path_runtime, original_preflight()).returncode == 0
    assert path_runtime[3].exists()


def test_native5_repair_does_not_change_the_existing_path_or_root_checks():
    def paths(script):
        return script[script.index('[[ "$RUNNER_TEMP" == /*'):script.index('HISTORICAL_ROOT=')]
    assert paths(workflow()["jobs"]["execution"]["steps"][0]["run"]) == paths(original_preflight())


@pytest.mark.parametrize("raw", ["5920107119", "    5920107119", "5920107119    ",
    "\t5920107119\t", " \t 5920107119 \t "])
def test_actual_boundary_normalizes_only_edges_and_guard_gets_canonical_output(path_runtime, bash, tmp_path, raw):
    env = path_runtime[4]
    env["RAW_READINESS_COMMENT_ID"] = raw
    result = initialize(bash, path_runtime)
    assert result.returncode == 0, result.stderr
    assert boundary_outputs(path_runtime) == {"readiness_comment_id": "5920107119"}
    definition = workflow()["jobs"]["execution"]
    assert "READINESS_COMMENT_ID" not in definition["env"]
    assert "RAW_READINESS_COMMENT_ID" not in definition["env"]
    boundary = definition["steps"][0]
    assert boundary["id"] == "boundary"
    assert boundary["env"] == {"RAW_READINESS_COMMENT_ID": "${{ inputs.readiness_comment_id }}"}
    guard = next(step for step in definition["steps"] if step.get("id") == "guard")
    assert guard["env"]["READINESS_COMMENT_ID"] == "${{ steps.boundary.outputs.readiness_comment_id }}"
    shared = dict(line.split("=", 1) for line in path_runtime[2].read_text().splitlines())
    calls = tmp_path / "canonical-guard-arguments"
    # Actions resolves this declared step environment from the first step's
    # output. Execute the actual guard command with a provider-free argv spy.
    downstream = dict(env, **shared, READINESS_COMMENT_ID=boundary_outputs(path_runtime)["readiness_comment_id"],
                      PATH_CALLS=shell_path(bash, calls))
    downstream.pop("RAW_READINESS_COMMENT_ID")
    spy = 'python() { printf "%s\\0" "$@" > "$PATH_CALLS"; }; export -f python\n'
    result = run_shell(bash, spy + guard["run"], downstream, path_runtime[1])
    assert result.returncode == 0, result.stderr
    args = [arg.decode() for arg in calls.read_bytes().split(b"\0")[:-1]]
    assert args[0] == "tools/historical_execution_guard.py"
    assert args[args.index("--readiness-comment-id") + 1] == "5920107119"
    assert "${{ inputs.readiness_comment_id }}" not in guard["run"]
    assert not (set(downstream) & {"ALPACA_API_KEY", "ALPACA_SECRET_KEY", "ANTHROPIC_API_KEY"})


@pytest.mark.parametrize("raw", ["", " \t ", "0", "00", "0123", "+123", "-123", "1.0", "1e3",
    "1 23", "1\t23", "123\n", "\r123", "1\n23", "123\r\n", "\v123", "123\f",
    "\u00a0123", "123\u00a0", "\u2003123", "\u0661\u0662\u0663", "\uff11\uff12\uff13",
    "https://github.com/example/123", "'123'", '"123"', "$(touch must-not-exist)", "`touch must-not-exist`"])
def test_actual_boundary_refuses_malformed_without_echo_or_path_side_effects(path_runtime, bash, raw):
    path_runtime[4]["RAW_READINESS_COMMENT_ID"] = raw
    result = initialize(bash, path_runtime)
    assert result.returncode != 0
    assert result.stdout == ""
    assert result.stderr == ("Invalid readiness comment ID: expected positive ASCII decimal digits, "
                             "with only optional edge spaces/tabs.\n")
    assert not path_runtime[3].exists()
    assert not path_runtime[2].read_bytes()
    assert not boundary_outputs(path_runtime)
    assert not list(path_runtime[0].glob("historical-input-*"))
    assert not (path_runtime[1] / "must-not-exist").exists()


def test_restored_missing_normalization_defect_fails_logged_input(path_runtime, bash):
    script = workflow()["jobs"]["execution"]["steps"][0]["run"]
    start = script.index('while [[ "$READINESS_COMMENT_ID"')
    end = script.index('if [[ ! "$READINESS_COMMENT_ID"', start)
    broken = script[:start] + script[end:]
    path_runtime[4]["RAW_READINESS_COMMENT_ID"] = "    5920107119"
    result = initialize(bash, path_runtime, broken)
    assert result.returncode != 0
    assert not boundary_outputs(path_runtime)
    assert not path_runtime[3].exists()


@pytest.mark.parametrize("mode,native,attempt", [("rehearsal", "4", "1"), ("real", "5", "1"),
    ("real", "5", "2"), ("real", "6", "2"), ("real", "7", "1"), ("rehearsal", "6", "1")])
def test_actual_boundary_keeps_consumed_and_unreviewed_slots_closed(path_runtime, bash, mode, native, attempt):
    path_runtime[4].update(MODE=mode, GITHUB_RUN_NUMBER=native, GITHUB_RUN_ATTEMPT=attempt)
    assert initialize(bash, path_runtime).returncode != 0
    assert not path_runtime[3].exists()
    assert not boundary_outputs(path_runtime)


def test_provider_credentials_exist_only_after_guard_and_recipient_preflight():
    definition = workflow()["jobs"]["execution"]
    assert not any("secrets." in value for value in definition["env"].values())
    steps = definition["steps"]
    guard = next(i for i, step in enumerate(steps) if step.get("id") == "guard")
    preflight = next(i for i, step in enumerate(steps) if step.get("id") == "preflight")
    acquisition = next(i for i, step in enumerate(steps) if step.get("id") == "acquisition")
    assert guard < preflight < acquisition
    for index, step in enumerate(steps):
        secrets = {key: value for key, value in step.get("env", {}).items() if "secrets." in value}
        if index == acquisition:
            assert secrets == {"ALPACA_API_KEY": "${{ secrets.ALPACA_API_KEY }}",
                               "ALPACA_SECRET_KEY": "${{ secrets.ALPACA_SECRET_KEY }}"}
            assert step["if"] == "inputs.mode == 'real'"
        else:
            assert not secrets


@pytest.mark.parametrize("field,value", [("MODE", "unexpected"), ("GITHUB_RUN_NUMBER", "1"),
    ("GITHUB_RUN_NUMBER", "2"), ("GITHUB_RUN_ATTEMPT", "2"), ("RUNNER_TEMP", "relative/temp"), ("RUNNER_TEMP", "/"),
    ("RUNNER_TEMP", "/tmp/newline\ninjection")])
def test_actual_initialization_rejects_unreviewed_identity_and_unsafe_paths(path_runtime, bash, field, value):
    path_runtime[4][field] = value
    result = initialize(bash, path_runtime)
    assert result.returncode != 0
    assert not path_runtime[3].exists()
    assert not list(path_runtime[0].glob("historical-input-*"))


def test_actual_initialization_rejects_temp_inside_checkout(path_runtime, bash):
    env = path_runtime[4]
    env["RUNNER_TEMP"] = env["GITHUB_WORKSPACE"]
    assert initialize(bash, path_runtime).returncode != 0
    assert not list(path_runtime[1].glob("historical-input-*"))


def test_actual_initialization_rejects_any_git_ancestor_before_install(path_runtime, bash):
    (path_runtime[0].parent / ".git").mkdir()
    assert initialize(bash, path_runtime).returncode != 0
    assert not list(path_runtime[0].glob("historical-input-*"))


def test_actual_initialization_never_reuses_existing_execution_directory(path_runtime, bash):
    assert initialize(bash, path_runtime).returncode == 0
    preserved = path_runtime[0] / "historical-input-123456-1" / "preserved-evidence"
    preserved.write_bytes(b"do not reset")
    environment_before = path_runtime[2].read_bytes()
    assert initialize(bash, path_runtime).returncode != 0
    assert preserved.read_bytes() == b"do not reset"
    assert path_runtime[2].read_bytes() == environment_before


def test_semantic_gate_runs_before_pytest_without_ignored_context_diagnostics():
    normal = yaml.load((ROOT / ".github/workflows/tests.yml").read_text(), Loader=yaml.BaseLoader)
    steps = normal["jobs"]["pytest"]["steps"]
    install = next(i for i, step in enumerate(steps) if "install_actionlint.py" in step.get("run", ""))
    check = next(i for i, step in enumerate(steps) if step.get("name") == "Validate changed workflow contexts and syntax")
    tests = next(i for i, step in enumerate(steps) if step.get("run") == "pytest tests/ -q")
    assert install < check < tests
    command = steps[check]["run"]
    assert "-ignore" not in command
    assert ".github/workflows/historical-input-proof.yml" in command
    assert ".github/workflows/tests.yml" in command
    assert steps[tests]["env"]["ACTIONLINT_BINARY"].endswith("/actionlint/actionlint")


def test_actionlint_installer_rejects_changed_archive_before_creating_destination(tmp_path, monkeypatch):
    monkeypatch.setattr(install_actionlint.platform, "system", lambda: "Linux")
    monkeypatch.setattr(install_actionlint.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(install_actionlint, "urlopen", lambda *a, **k: io.BytesIO(b"untrusted bytes"))
    destination = tmp_path / "tool"
    with pytest.raises(ValueError, match="actionlint_release_digest_mismatch"):
        install_actionlint.install(destination)
    assert not destination.exists()


def test_actionlint_installer_will_not_replace_existing_tools(tmp_path, monkeypatch):
    destination = tmp_path / "tool"
    destination.mkdir()
    monkeypatch.setattr(install_actionlint, "urlopen", lambda *a, **k: pytest.fail("must not download"))
    with pytest.raises(ValueError, match="actionlint_destination_must_be_fresh"):
        install_actionlint.install(destination)
