"""Hold the provider/ciphertext boundary in the actual dispatched workflow."""
from pathlib import Path
import re

import yaml

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / ".github/workflows/historical-input-proof.yml"


def workflow():
    # BaseLoader preserves YAML's 'on' rather than interpreting it as a boolean.
    return yaml.load(PATH.read_text(), Loader=yaml.BaseLoader)


def test_provider_workflow_has_only_the_reviewed_manual_inputs_and_two_slots():
    value = workflow()
    assert set(value["on"]) == {"workflow_dispatch"}
    inputs = value["on"]["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"mode", "readiness_comment_id"}
    assert inputs["mode"]["default"] == "rehearsal"
    assert inputs["mode"]["options"] == ["rehearsal", "real"]
    assert value["concurrency"] == {"group": "spicystock-historical-input-2026-09-28", "cancel-in-progress": "false"}
    assert value["permissions"] == {"contents": "read", "actions": "read", "pull-requests": "read"}
    assert set(value["jobs"]) == {"execution"}


def test_only_the_guarded_real_acquisition_step_receives_the_alpaca_pair():
    steps = workflow()["jobs"]["execution"]["steps"]
    secrets = [(index, step) for index, step in enumerate(steps) if "secrets." in str(step)]
    assert len(secrets) == 1
    index, real = secrets[0]
    assert real["if"] == "inputs.mode == 'real'"
    assert real["env"] == {"ALPACA_API_KEY": "${{ secrets.ALPACA_API_KEY }}", "ALPACA_SECRET_KEY": "${{ secrets.ALPACA_SECRET_KEY }}"}
    assert "--mode real" in real["run"] and "src.pipeline" not in PATH.read_text()
    assert next(i for i, s in enumerate(steps) if s.get("id") == "guard") < index
    assert next(i for i, s in enumerate(steps) if s.get("id") == "preflight") < index
    assert int(real["timeout-minutes"]) < int(workflow()["jobs"]["execution"]["timeout-minutes"])


def test_upload_is_a_literal_ciphertext_allowlist_after_successful_packaging():
    steps = workflow()["jobs"]["execution"]["steps"]
    uploads = [s for s in steps if s.get("uses", "").startswith("actions/upload-artifact@")]
    assert len(uploads) == 1
    upload = uploads[0]
    assert upload["if"] == "always() && steps.package.outcome == 'success'"
    assert upload["with"]["path"].splitlines() == [
        "${{ env.HISTORICAL_ROOT }}/delivery/evidence.tar.zst.age",
        "${{ env.HISTORICAL_ROOT }}/delivery/receipt.json",
    ]
    assert upload["with"]["retention-days"] == "7"
    assert upload["with"]["overwrite"] == "false"
    assert upload["with"]["if-no-files-found"] == "error"


def test_actions_are_immutable_and_inputs_are_never_interpolated_into_shell():
    value = workflow()
    assert value["jobs"]["execution"]["runs-on"] == "ubuntu-24.04"
    for step in value["jobs"]["execution"]["steps"]:
        if "uses" in step:
            assert re.fullmatch(r"actions/[a-z-]+@[0-9a-f]{40}", step["uses"])
        assert "${{ inputs." not in step.get("run", "")
        if step.get("uses", "").startswith("actions/checkout@"):
            assert step["with"]["persist-credentials"] == "false"


def test_normal_ci_requires_real_age_crypto_controls_without_provider_secrets():
    normal = yaml.load((ROOT / ".github/workflows/tests.yml").read_text(), Loader=yaml.BaseLoader)
    steps = normal["jobs"]["pytest"]["steps"]
    install = next(i for i, s in enumerate(steps) if "install_historical_age.py" in s.get("run", ""))
    check = next(i for i, s in enumerate(steps) if s.get("run") == "pytest tests/ -q")
    assert install < check
    assert steps[check]["env"]["AGE_BINARY"].endswith("/historical-age/age")
    assert "secrets." not in str(normal)
