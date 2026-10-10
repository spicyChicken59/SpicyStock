"""The GitHub Actions workflows, asserted on their PARSED structure: what
went wrong in this repository's history was a property of an `if:`
condition and of a cron pair, never a spelling. PyYAML reads `on:` as the
boolean True, so the trigger block is looked up under both keys."""
from __future__ import annotations

import datetime as datetime_module
import json
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


def scheduled_guard() -> dict:
    return next(step for step in load('evening.yml')['jobs']['scan']['steps'] if step.get('id') == 'guard')


def run_scheduled_guard(monkeypatch, tmp_path, at, cron='16 0 * * 2-6', previous=None,
                        event='schedule', requested=''):
    """Execute the workflow's actual Python body with a pinned UTC clock."""
    instant = datetime_module.datetime.fromisoformat(at)

    class FrozenDateTime(datetime_module.datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

    code = scheduled_guard()['run'].split("python - <<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
    output = tmp_path / 'guard-output'
    (tmp_path / 'docs').mkdir(exist_ok=True)
    if previous is not None:
        (tmp_path / 'docs' / 'data.json').write_text(json.dumps(previous))
    with monkeypatch.context() as patch:
        patch.chdir(tmp_path)
        patch.setattr(datetime_module, 'datetime', FrozenDateTime)
        patch.setenv('SCAN_EVENT_NAME', event)
        patch.setenv('SCAN_EVENT_SCHEDULE', cron)
        patch.setenv('SCAN_REQUESTED_SESSION', requested)
        patch.setenv('GITHUB_OUTPUT', str(output))
        exec(compile(code, 'evening.yml scheduled guard', 'exec'), {})
    return dict(line.split('=', 1) for line in output.read_text().splitlines())


def test_the_workflow_inventory_is_exactly_the_seven_the_docs_name():
    assert sorted(p.name for p in WORKFLOWS.glob("*.yml")) == \
        ["evening.yml", "historical-input-proof.yml", "intraday.yml", "morning.yml", "publish-dashboard.yml", "secret-scan.yml", "tests.yml"]


# ----------------------------------------------------------- evening -----
def test_the_evening_crons_are_the_two_pairs_and_the_guard_names_them():
    wf = load("evening.yml")
    crons = [c["cron"] for c in triggers(wf)["schedule"]]
    assert crons == ["16 22 * * 1-5", "16 23 * * 1-5", "16 0 * * 2-6", "16 1 * * 2-6"]
    guard = scheduled_guard()['run']
    for cron in crons:
        assert cron in guard, cron
    assert 'sessions.is_session(target)' in guard


@pytest.mark.parametrize('at,cron,target', [
    ('2026-10-08T22:24:00+00:00', '16 22 * * 1-5', '2026-10-08'),
    ('2026-10-09T02:06:21+00:00', '16 22 * * 1-5', '2026-10-08'),
    ('2026-10-09T06:03:02+00:00', '16 0 * * 2-6', '2026-10-08'),
    ('2026-10-10T06:03:02+00:00', '16 0 * * 2-6', '2026-10-09'),
    ('2026-11-03T23:24:00+00:00', '16 23 * * 1-5', '2026-11-03'),
    ('2026-11-04T07:03:02+00:00', '16 1 * * 2-6', '2026-11-03'),
])
def test_delayed_slots_keep_the_nominal_evenings_session(monkeypatch, tmp_path, at, cron, target):
    assert run_scheduled_guard(monkeypatch, tmp_path, at, cron) == {'go': 'true', 'session': target}


@pytest.mark.parametrize('at,cron', [
    ('2026-10-09T07:26:25+00:00', '16 1 * * 2-6'),  # inactive EST slot
    ('2026-11-04T06:03:00+00:00', '16 0 * * 2-6'),  # inactive EDT slot
    ('2026-10-09T13:30:00+00:00', '16 0 * * 2-6'),  # next market open
    ('2026-10-09T15:00:00+00:00', '16 22 * * 1-5'),
    ('2026-10-11T06:03:00+00:00', '16 0 * * 2-6'),  # no Saturday-evening slot
    ('2026-11-26T23:24:00+00:00', '16 23 * * 1-5'),  # Thanksgiving
    ('2026-10-09T06:03:00+00:00', 'not a scheduled cron'),
])
def test_inactive_holiday_and_expired_slots_never_run(monkeypatch, tmp_path, at, cron):
    assert run_scheduled_guard(monkeypatch, tmp_path, at, cron) == {'go': 'false', 'session': ''}


@pytest.mark.parametrize('status', ['ok', 'degraded'])
@pytest.mark.parametrize('cron', ['16 22 * * 1-5', '16 0 * * 2-6'])
def test_both_slots_skip_a_real_published_session(monkeypatch, tmp_path, status, cron):
    previous = {'run': {'session': '2026-10-08', 'status': status, 'dry_run': False}}
    assert run_scheduled_guard(monkeypatch, tmp_path, '2026-10-09T06:03:00+00:00', cron,
                               previous) == {'go': 'false', 'session': ''}


@pytest.mark.parametrize('previous', [
    {'run': {'session': '2026-10-08', 'status': 'failed', 'dry_run': False}},
    {'run': {'session': '2026-10-08', 'status': 'ok', 'dry_run': True}},
    {'fixture': True, 'run': {'session': '2026-10-08', 'status': 'ok', 'dry_run': False}},
    {'run': {'session': '2026-10-07', 'expected_session': '2026-10-08', 'status': 'ok', 'dry_run': False}},
    {'run': {'session': 'not a date', 'status': 'ok', 'dry_run': False}},
    {'run': {'session': '2026-10-08', 'status': [], 'dry_run': False}},
    {'run': []},
    [],
])
def test_failed_rehearsal_expected_only_and_malformed_records_do_not_hide_a_missing_session(monkeypatch, tmp_path, previous):
    assert run_scheduled_guard(monkeypatch, tmp_path, '2026-10-09T06:03:00+00:00',
                               previous=previous) == {'go': 'true', 'session': '2026-10-08'}


def test_delayed_event_never_replaces_a_newer_session(monkeypatch, tmp_path):
    previous = {'run': {'session': '2026-10-09', 'status': 'ok', 'dry_run': False}}
    assert run_scheduled_guard(monkeypatch, tmp_path, '2026-10-09T06:03:00+00:00',
                               previous=previous) == {'go': 'false', 'session': ''}


def test_unreadable_publication_does_not_suppress_recovery(monkeypatch, tmp_path):
    (tmp_path / 'docs').mkdir()
    (tmp_path / 'docs' / 'data.json').write_text('{incomplete')
    assert run_scheduled_guard(monkeypatch, tmp_path, '2026-10-09T06:03:00+00:00') == {
        'go': 'true', 'session': '2026-10-08'}


@pytest.mark.parametrize('requested', ['', '2026-09-15'])
def test_manual_dispatch_keeps_its_explicit_or_unset_session(monkeypatch, tmp_path, requested):
    previous = {'run': {'session': '2026-10-08', 'status': 'ok', 'dry_run': False}}
    assert run_scheduled_guard(monkeypatch, tmp_path, '2026-10-09T15:00:00+00:00',
                               previous=previous, event='workflow_dispatch', requested=requested) == {
                                   'go': 'true', 'session': requested}


def test_the_dispatch_form_has_the_three_boxes_and_forwards_each():
    wf = load("evening.yml")
    inputs = triggers(wf)["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"session", "dry_run", "skip_email"}
    env = steps(wf, "scan")["Run evening pipeline"]["env"]
    assert env["SCAN_SESSION_DATE"] == "${{ steps.guard.outputs.session }}"
    assert scheduled_guard()['env']['SCAN_REQUESTED_SESSION'] == '${{ inputs.session }}'
    assert "inputs.dry_run" in env["DRY_RUN_FLAG"] and "--dry-run" in env["DRY_RUN_FLAG"]
    assert "inputs.skip_email" in env["SCAN_SEND_EMAIL"]
    for secret in ("ANTHROPIC_API_KEY", "RESEND_API_KEY", "RESEND_FROM", "EMAIL_TO", "ALPACA_API_KEY", "ALPACA_SECRET_KEY"):
        assert env[secret] == f"${{{{ secrets.{secret} }}}}"
    for var in ("SCAN_FEED", "SCAN_UNIVERSE"):
        assert env[var] == f"${{{{ vars.{var} }}}}"
    assert env['ACCOUNT_EQUITY'] == '2000'
    assert env['RISK_PCT'] == '0.5'
    assert env["GITHUB_RUN_ID_FOR_RECORD"] == "${{ github.run_id }}"


def test_the_persist_step_keeps_every_code_that_published_and_never_a_rehearsal():
    wf = load("evening.yml")
    persist = steps(wf, "scan")["Persist the run"]
    cond = persist["if"]
    for code in (pipeline.EXIT_OK, pipeline.EXIT_DEGRADED, pipeline.EXIT_FAILED_AFTER_PUBLISH):
        assert f"steps.pipeline.outputs.code == '{code}'" in cond
    assert f"steps.pipeline.outputs.code == '{pipeline.EXIT_FAILED}'" not in cond
    assert "inputs.dry_run != true" in cond
    assert "steps.pipeline.outputs.published == 'true'" in cond
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


def test_the_artifact_keeps_records_charts_and_retained_evidence():
    wf = load("evening.yml")
    art = steps(wf, "scan")["Keep the run's artifacts"]
    assert art["if"].startswith("(success() || failure())")
    assert "!= 'no_session'" in art["if"] and "!= 'session_incomplete'" in art["if"]
    assert set(art["with"]["path"].split()) == {"docs/data.json", "docs/reader.json", "docs/reader-observations/",
                                             "docs/picks.json", "docs/charts/", "docs/evidence/", "docs/history/"}


def test_input_diagnostics_upload_separately_only_from_this_invocation():
    wf = load("evening.yml")
    current = steps(wf, "scan")
    legacy = current["Keep the run's artifacts"]
    diagnostic = current["Keep input exception diagnostics"]
    assert diagnostic["if"] == "(success() || failure()) && steps.guard.outputs.go == 'true' && steps.pipeline.outputs.input_diagnostics != ''"
    assert diagnostic["uses"] == "actions/upload-artifact@v4"
    assert diagnostic["with"] == {"name": "input-exceptions-${{ github.run_id }}-${{ github.run_attempt }}",
                                  "path": "${{ steps.pipeline.outputs.input_diagnostics }}/",
                                  "if-no-files-found": "error", "retention-days": 30}
    assert legacy["with"]["retention-days"] == 30
    assert legacy["with"]["name"] == "${{ inputs.dry_run == true && format('evening-dryrun-{0}', github.run_id) || ((steps.pipeline.outputs.code == '0' || steps.pipeline.outputs.code == '2' || steps.pipeline.outputs.code == '3') && steps.pipeline.outputs.session != '' && format('evening-{0}-{1}', steps.pipeline.outputs.session, github.run_id) || format('evening-failed-{0}', github.run_id)) }}"
    # The legacy upload's common ancestor is still docs/, so its ZIP root is unchanged.
    assert all(path.startswith("docs/") for path in legacy["with"]["path"].split())


def test_the_evening_job_can_write_and_runs_alone():
    wf = load("evening.yml")
    assert wf["permissions"] == {"contents": "write", "actions": "read"}
    assert wf["concurrency"] == {"group": "evening-scan", "cancel-in-progress": False}
    checkout = steps(wf, 'scan')['actions/checkout@v4']
    assert checkout['with']['ref'] == '${{ github.ref }}'


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
    env = steps(wf, "check")["Run the intraday check"]["env"]
    assert env['SCAN_SEND_EMAIL'] == 'false'
    assert set(env) == {'ALPACA_API_KEY', 'ALPACA_SECRET_KEY', 'SCAN_SEND_EMAIL'}


def test_legacy_workflow_delivery_setting_needs_no_resend_and_never_mails_confirmed_rows(monkeypatch, tmp_path):
    env = steps(load('intraday.yml'), 'check')['Run the intraday check']['env']
    monkeypatch.setenv('SCAN_SEND_EMAIL', env['SCAN_SEND_EMAIL'])
    for name in ('ALPACA_API_KEY', 'ALPACA_SECRET_KEY'):
        monkeypatch.setenv(name, 'offline-test-placeholder')
    for name in ('RESEND_API_KEY', 'RESEND_FROM', 'EMAIL_TO'):
        monkeypatch.delenv(name, raising=False)
    assert pipeline.missing_env('intraday') == []
    monkeypatch.setattr(pipeline, 'load_previous', lambda docs: {'trades': ['TEST']})
    monkeypatch.setattr(pipeline, 'snapshot_rows', lambda client, symbols: {})
    monkeypatch.setattr(pipeline, 'intraday_rows', lambda data, rows: [
        {'ticker': 'TEST', 'above_level': True, 'volume_state': 'confirmed'}])

    def forbidden(*args, **kwargs):
        raise AssertionError('Legacy research must never send a notice')

    monkeypatch.setattr(pipeline.report, 'deliver', forbidden)
    now = datetime_module.datetime(2026, 10, 9, 19, 30, tzinfo=datetime_module.timezone.utc)
    result = pipeline.run_intraday(docs=tmp_path, client=object(), now=now)
    assert result.published and result.exit_code() == 0
    assert json.loads((tmp_path / 'live.json').read_text())['rows'][0]['volume_state'] == 'confirmed'


# ---------------------------------------------------------- morning -----
def test_morning_has_only_two_active_daily_slots_and_an_explicit_rehearsal():
    from tools import publish_morning
    wf = load('morning.yml')
    on = triggers(wf)
    assert [row['cron'] for row in on['schedule']] == list(publish_morning.SCHEDULES)
    assert on['workflow_dispatch']['inputs']['dry_run']['default'] is True
    assert on['workflow_dispatch']['inputs']['probe_sources']['default'] is False
    assert wf['concurrency'] == {'group': 'morning-observation', 'cancel-in-progress': False}
    assert steps(wf, 'collect')['Guard the scheduled morning']['run'] == 'python -m tools.publish_morning guard'


def test_morning_collector_cannot_write_and_has_no_delivery_credentials():
    wf = load('morning.yml')
    assert wf['permissions'] == {'contents': 'read'}
    collect = wf['jobs']['collect']
    assert 'permissions' not in collect
    assert "inputs.dry_run == true" in collect['if']
    current = steps(wf, 'collect')
    assert current['actions/checkout@v4']['with'] == {'ref': '${{ github.ref }}', 'persist-credentials': False}
    step = current['Collect a bound morning observation']
    assert step['if'] == "steps.guard.outputs.go == 'true'"
    assert step['env']['SCAN_SEND_EMAIL'] == 'false'
    assert {k for k, value in step['env'].items() if 'secrets.' in value} == {'ALPACA_API_KEY', 'ALPACA_SECRET_KEY'}
    assert 'python -m src.morning --docs docs --output "$RUNNER_TEMP/morning.json"' in step['run']
    assert 'git ' not in step['run']


def test_morning_persistence_is_main_only_never_rehearsal_and_uses_current_run_artifact():
    wf = load('morning.yml')
    job = wf['jobs']['persist']
    assert job['permissions'] == {'contents': 'write'}
    assert job['needs'] == 'collect'
    assert "github.ref == 'refs/heads/main'" in job['if']
    assert "inputs.dry_run == false" in job['if'] and "github.event_name == 'schedule'" in job['if']
    assert 'inputs.probe_sources != true' in job['if']
    current = steps(wf, 'persist')
    assert current['actions/checkout@v4']['with']['ref'] == 'main'
    artifact = current['actions/download-artifact@v4']['with']
    assert artifact == {'name': 'morning-${{ github.run_id }}-${{ github.run_attempt }}',
                        'path': '${{ runner.temp }}/morning-observation'}
    assert current['Publish only against the unchanged source record']['run'] == \
        'python -m tools.publish_morning publish --snapshot "$RUNNER_TEMP/morning-observation/morning.json"'
    assert not any('secrets.' in str(step.get('env', {})) for step in job['steps'])


def test_source_probe_is_opt_in_rehearsal_only_and_separately_retained():
    wf = load('morning.yml')
    current = steps(wf, 'collect')
    probe = current['Rehearse actual source transports']
    artifact = current['Retain source diagnostic separately']
    assert probe['if'] == artifact['if'] == \
        "github.event_name == 'workflow_dispatch' && inputs.dry_run == true && inputs.probe_sources == true"
    assert set(probe['env']) == {'ALPACA_API_KEY', 'ALPACA_SECRET_KEY', 'SCAN_SEND_EMAIL'}
    assert probe['env']['SCAN_SEND_EMAIL'] == 'false'
    assert probe['run'] == 'python -m tools.probe_morning_sources --output "$RUNNER_TEMP/morning-source-probe.json"'
    assert artifact['with']['path'] == '${{ runner.temp }}/morning-source-probe.json'
    assert artifact['with']['name'].startswith('morning-source-probe-')
    assert 'inputs.probe_sources != true || inputs.dry_run == true' in wf['jobs']['collect']['if']


# ------------------------------------------------------------- tests -----
def test_ci_runs_the_suite_the_fixture_check_the_chart_check_and_the_page_smoke():
    wf = load("tests.yml")
    assert steps(wf, "pytest")["Run tests"]["run"].strip() == "pytest tests/ -q"
    assert steps(wf, "pytest")["The fixtures are what the pipeline writes"]["run"].strip().splitlines() == [
        'python tools/make_fixture.py --check', 'python tests/fixtures/morning/generate.py --check']
    page = steps(wf, "page")["Open the page against every fixture and read it back"]["run"]
    assert "node --test tools/handoff_model_cases.mjs" in page
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
    assert on["workflow_run"]["workflows"] == [load("evening.yml")["name"], load('morning.yml')['name']]
    assert on["workflow_run"]["branches"] == ["main"]
    checkout = [s for s in wf["jobs"]["publish"]["steps"] if str(s.get("uses", "")).startswith("actions/checkout")][0]
    assert checkout["with"] == {"ref": "main", "persist-credentials": False}
    assert wf["permissions"] == {"contents": "read", "pages": "write"}
