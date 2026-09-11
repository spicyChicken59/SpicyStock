"""The GitHub Actions workflows, asserted on their PARSED structure: what
went wrong in this repository's history was a property of an `if:`
condition and of a cron pair, never a spelling. PyYAML reads `on:` as the
boolean True, so the trigger block is looked up under both keys."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src import pipeline

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"


def load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text())


def triggers(wf: dict) -> dict:
    return wf.get("on") or wf.get(True) or {}


def steps(wf: dict, job: str) -> dict[str, dict]:
    return {s.get("name") or s.get("uses") or s.get("id"): s for s in wf["jobs"][job]["steps"]}


def test_the_workflow_inventory_is_exactly_the_five_the_docs_name():
    assert sorted(p.name for p in WORKFLOWS.glob("*.yml")) == \
        ["evening.yml", "intraday.yml", "publish-dashboard.yml", "secret-scan.yml", "tests.yml"]


# ----------------------------------------------------------- evening -----
def test_the_evening_crons_are_the_two_pairs_and_the_guard_names_them():
    wf = load("evening.yml")
    crons = [c["cron"] for c in triggers(wf)["schedule"]]
    assert crons == ["16 22 * * 1-5", "16 23 * * 1-5", "16 0 * * 2-6", "16 1 * * 2-6"]
    guard = steps(wf, "scan")["Guard — the slot for today's UTC offset; the retry only if tonight is unpublished"]["run"]
    for cron in crons:
        assert cron in guard, cron
    assert 'jq -e' in guard and '.run.session == $s' in guard and '.run.expected_session == $s' in guard


def test_the_dispatch_form_has_the_three_boxes_and_forwards_each():
    wf = load("evening.yml")
    inputs = triggers(wf)["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"session", "dry_run", "skip_email"}
    env = steps(wf, "scan")["Run evening pipeline"]["env"]
    assert env["SCAN_SESSION_DATE"] == "${{ inputs.session }}"
    assert "inputs.dry_run" in env["DRY_RUN_FLAG"] and "--dry-run" in env["DRY_RUN_FLAG"]
    assert "inputs.skip_email" in env["SCAN_SEND_EMAIL"]
    for secret in ("ANTHROPIC_API_KEY", "RESEND_API_KEY", "RESEND_FROM", "EMAIL_TO", "ALPACA_API_KEY", "ALPACA_SECRET_KEY"):
        assert env[secret] == f"${{{{ secrets.{secret} }}}}"
    for var in ("SCAN_FEED", "SCAN_UNIVERSE", "ACCOUNT_EQUITY", "RISK_PCT"):
        assert env[var] == f"${{{{ vars.{var} }}}}"
    assert env["GITHUB_RUN_ID_FOR_RECORD"] == "${{ github.run_id }}"


def test_the_persist_step_keeps_every_code_that_published_and_never_a_rehearsal():
    wf = load("evening.yml")
    persist = steps(wf, "scan")["Persist the run"]
    cond = persist["if"]
    for code in (pipeline.EXIT_OK, pipeline.EXIT_DEGRADED, pipeline.EXIT_FAILED_AFTER_PUBLISH):
        assert f"steps.pipeline.outputs.code == '{code}'" in cond
    assert f"steps.pipeline.outputs.code == '{pipeline.EXIT_FAILED}'" not in cond
    assert "inputs.dry_run != true" in cond
    assert "git add docs" in persist["run"] and "git diff --staged --quiet && exit 0" in persist["run"]
    assert persist["run"].count("git push") == 1 and "for attempt in 1 2 3" in persist["run"]


def test_the_pipeline_step_captures_its_code_and_the_verdict_step_raises_it_last():
    wf = load("evening.yml")
    names = list(steps(wf, "scan"))
    assert names.index("Run evening pipeline") < names.index("Persist the run") < names.index("Keep the run's artifacts") < names.index("Report the pipeline's verdict")
    run = steps(wf, "scan")["Run evening pipeline"]["run"]
    assert "set +e" in run and 'echo "code=$code" >> "$GITHUB_OUTPUT"' in run
    verdict = steps(wf, "scan")["Report the pipeline's verdict"]["run"]
    assert f'if [ "$code" = "{pipeline.EXIT_DEGRADED}" ]' in verdict and "::warning::" in verdict and "exit $code" in verdict


def test_the_artifact_keeps_the_record_the_picks_and_the_charts():
    wf = load("evening.yml")
    art = steps(wf, "scan")["Keep the run's artifacts"]
    assert art["if"].startswith("(success() || failure())")
    assert set(art["with"]["path"].split()) == {"docs/data.json", "docs/picks.json", "docs/charts/"}


def test_the_evening_job_can_write_and_runs_alone():
    wf = load("evening.yml")
    assert wf["permissions"] == {"contents": "write", "actions": "read"}
    assert wf["concurrency"] == {"group": "evening-scan", "cancel-in-progress": False}


# ---------------------------------------------------------- intraday -----
def test_the_intraday_check_is_dispatch_only_reads_only_and_never_commits():
    wf = load("intraday.yml")
    assert list(triggers(wf)) == ["workflow_dispatch"]
    assert wf["permissions"] == {"contents": "read"}
    run = steps(wf, "check")["Run the intraday check"]["run"]
    assert run.strip() == "python -m src.pipeline intraday"
    assert not [s for s in wf["jobs"]["check"]["steps"] if "git " in str(s.get("run", ""))]
    art = [s for s in wf["jobs"]["check"]["steps"] if str(s.get("uses", "")).startswith("actions/upload-artifact")][0]
    assert art["with"]["path"] == "docs/live.json"


# ------------------------------------------------------------- tests -----
def test_ci_runs_the_suite_the_chart_check_and_the_page_smoke():
    wf = load("tests.yml")
    assert steps(wf, "pytest")["Run tests"]["run"].strip() == "pytest tests/ -q"
    page = steps(wf, "page")["Open the page against every fixture and read it back"]["run"]
    assert "node tools/chart_check.mjs" in page and "node tools/page_smoke.mjs --shots" in page
    assert "set -o pipefail" in page and "playwright@1.56.1" in page
    assert wf["permissions"] == {"contents": "read"}


def test_the_evening_and_the_tests_run_the_same_python():
    assert steps(load("evening.yml"), "scan")["actions/setup-python@v5"]["with"]["python-version"] == \
        steps(load("tests.yml"), "pytest")["actions/setup-python@v5"]["with"]["python-version"]


# ---------------------------------------------------------- publish -----
def test_the_publisher_only_reads_committed_main_after_the_evening_workflow():
    wf = load("publish-dashboard.yml")
    on = triggers(wf)
    assert on["workflow_run"]["workflows"] == [load("evening.yml")["name"]]
    assert on["workflow_run"]["branches"] == ["main"]
    checkout = [s for s in wf["jobs"]["publish"]["steps"] if str(s.get("uses", "")).startswith("actions/checkout")][0]
    assert checkout["with"] == {"ref": "main", "persist-credentials": False}
    assert wf["permissions"] == {"contents": "read", "pages": "write"}
