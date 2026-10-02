"""Dry run of the ACTUAL historical execution guard against LIVE GitHub data.

Only three GitHub resources are synthesized (the prospective readiness comment,
the prospective native-6 run in the workflow listing / its detail, and its
attempt-1 jobs). Every other response is the real live API response (or, for the
explicitly labelled replay scenarios, a byte-for-byte copy of a live response
recorded earlier in this same process). GitHub access is GET-only through the
guard's own GitHub client. No provider is contacted. No repository file is
written; outputs go only under this scratch directory.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import os
import re
import sys
import traceback
from datetime import date
from pathlib import Path

sys.dont_write_bytecode = True
REPO = Path("/home/user/SpicyStock")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
from tools import historical_execution_guard as guard  # noqa: E402

LIVE = HERE / "live"
ROOT = Path(os.environ["DRY_HISTORICAL_ROOT"])          # mirrors $HISTORICAL_ROOT (mode 700)
LOGDIR = HERE / "logs"
LOGDIR.mkdir(exist_ok=True)

SYNTH_COMMENT = 5999999999
SYNTH_RUN = 36999999999
SYNTH_JOB = 111111111111
CREATED = "2026-10-01T00:05:00Z"
WF = guard.WORKFLOW_ID
RUNS_RE = re.compile(r"^/actions/workflows/%d/runs\?per_page=100&page=(\d+)$" % WF)
JOBS_RE = re.compile(r"^/actions/runs/%d/attempts/1/jobs\?per_page=100&page=(\d+)$" % SYNTH_RUN)

RealGitHub = guard.GitHub
LIVE_CALLS = {"total": 0}
RECORD: dict[str, object] = {}


class Live:
    """Real network via the guard's own GitHub class; records responses."""

    def __init__(self, token, log):
        self.gh = RealGitHub(token)
        self.log = log
        self.count = 0

    def __call__(self, path):
        self.count += 1
        LIVE_CALLS["total"] += 1
        self.log.append(("LIVE", path))
        result = self.gh(path)
        RECORD[path] = copy.deepcopy(result)
        return result


class Replay:
    """Returns an exact copy of a live response recorded earlier in this process."""

    def __init__(self, token, log):
        self.live = Live(token, log)
        self.log = log

    @property
    def count(self):
        return self.live.count

    def __call__(self, path):
        if path in RECORD:
            self.log.append(("REPLAY", path))
            return copy.deepcopy(RECORD[path])
        return self.live(path)


def load(name):
    return json.loads((LIVE / name).read_text())


RUN5 = load("run5.json")
JOB5 = load("run5-jobs.json")["jobs"][0]
COMMENT_TEMPLATE = load("comment-5921715962.json")
PROSE = COMMENT_TEMPLATE["body"]
FENCED = re.findall(r"```json\n(.*?)\n```", PROSE, re.S)
assert len(FENCED) == 1, "expected exactly one fenced json block"
CANDIDATE_TEXT = FENCED[0]
CANDIDATE = json.loads(CANDIDATE_TEXT)
CANDIDATE_SHA = hashlib.sha256(guard.encode(CANDIDATE)).hexdigest()
assert CANDIDATE_TEXT.count('"authorized_on": "2026-09-30"') == 1
OPERATIVE_TEXT = CANDIDATE_TEXT.replace('"authorized_on": "2026-09-30"', '"authorized_on": "2026-10-01"')
_diff = {k for k in set(CANDIDATE) | set(json.loads(OPERATIVE_TEXT))
         if CANDIDATE.get(k) != json.loads(OPERATIVE_TEXT).get(k)}
assert _diff == {"authorized_on"}, _diff


def synth_comment(body, created=CREATED, login=guard.OWNER, issue=98):
    c = copy.deepcopy(COMMENT_TEMPLATE)
    c["id"] = SYNTH_COMMENT
    c["node_id"] = "IC_synthetic_dry_run"
    c["url"] = guard.API_ROOT + "/issues/comments/%d" % SYNTH_COMMENT
    c["html_url"] = "https://github.com/%s/pull/%d#issuecomment-%d" % (guard.REPOSITORY, issue, SYNTH_COMMENT)
    c["issue_url"] = guard.API_ROOT + "/issues/%d" % issue
    c["user"]["login"] = login
    c["created_at"] = created
    c["updated_at"] = created
    c["body"] = body
    return c


def synth_run(main_sha, main_tree, **overrides):
    r = copy.deepcopy(RUN5)
    r.update(id=SYNTH_RUN, run_number=6, run_attempt=1, status="in_progress", conclusion=None,
             event="workflow_dispatch", head_branch="main", head_sha=main_sha,
             display_title="historical-input-real", name="historical-input-real",
             created_at=CREATED, updated_at="2026-10-01T00:05:30Z", run_started_at=CREATED,
             node_id="WFR_synthetic_dry_run", check_suite_id=99999999999)
    for key in ("url", "html_url", "jobs_url", "logs_url", "artifacts_url", "cancel_url", "rerun_url"):
        if isinstance(r.get(key), str):
            r[key] = r[key].replace(str(RUN5["id"]), str(SYNTH_RUN))
    r["previous_attempt_url"] = None
    r["head_commit"] = dict(r["head_commit"], id=main_sha, tree_id=main_tree,
                            message="Merge pull request #98 (synthetic dry-run head_commit)")
    r.update(overrides)
    return r


def synth_job(run):
    j = copy.deepcopy(JOB5)
    j.update(id=SYNTH_JOB, run_id=run["id"], run_attempt=1, head_sha=run["head_sha"], head_branch="main",
             workflow_name=run["display_title"], status="in_progress", conclusion=None,
             created_at="2026-10-01T00:04:58Z", started_at=CREATED, completed_at=None,
             node_id="CR_synthetic_dry_run")
    for key in ("run_url", "url", "html_url", "check_run_url"):
        j[key] = j[key].replace(str(RUN5["id"]), str(run["id"])).replace(str(JOB5["id"]), str(SYNTH_JOB))
    steps = []
    for s in j["steps"]:
        s = dict(s)
        if s["number"] <= 5:
            s.update(status="completed", conclusion="success")
        elif s["number"] == 6:
            s.update(status="in_progress", conclusion=None, completed_at=None)
        else:
            s.update(status="queued", conclusion=None, started_at=None, completed_at=None)
        steps.append(s)
    j["steps"] = steps
    return j


class Intercept:
    def __init__(self, base, log, *, body=None, created=CREATED, login=guard.OWNER, issue=98,
                 run=None, include_run=True):
        self.base, self.log = base, log
        self.comment = synth_comment(OPERATIVE_TEXT if body is None else body, created, login, issue)
        self.run = run
        self.include_run = include_run

    def __call__(self, path):
        if path == "/issues/comments/%d" % SYNTH_COMMENT:
            self.log.append(("SYNTH", path))
            return copy.deepcopy(self.comment)
        m = RUNS_RE.match(path)
        if m:
            real = self.base(path)
            out = copy.deepcopy(real)
            if self.include_run:
                out["total_count"] = real["total_count"] + 1
                if int(m.group(1)) == 1:
                    out["workflow_runs"] = [copy.deepcopy(self.run)] + out["workflow_runs"]
            self.log.append(("SYNTH-MERGE", path))
            return out
        if path == "/actions/runs/%d" % SYNTH_RUN:
            self.log.append(("SYNTH", path))
            return copy.deepcopy(self.run)
        m = JOBS_RE.match(path)
        if m:
            self.log.append(("SYNTH", path))
            page = int(m.group(1))
            return {"total_count": 1, "jobs": [synth_job(self.run)] if page == 1 else []}
        if str(SYNTH_RUN) in path or str(SYNTH_COMMENT) in path:
            raise AssertionError("unexpected synthetic path " + path)
        return self.base(path)


TOKEN = os.environ["GITHUB_TOKEN"]
_boot_log = []
_boot = Live(TOKEN, _boot_log)
MAIN = _boot("/commits/main")
MAIN_SHA, MAIN_TREE = MAIN["sha"], MAIN["commit"]["tree"]["sha"]

BASE_ENV = {
    "GITHUB_ACTIONS": "true",
    "GITHUB_REPOSITORY": "spicyChicken59/SpicyStock",
    "GITHUB_REPOSITORY_ID": "1352997802",
    "GITHUB_EVENT_NAME": "workflow_dispatch",
    "GITHUB_REF": "refs/heads/main",
    "GITHUB_WORKFLOW_REF": "spicyChicken59/SpicyStock/.github/workflows/historical-input-proof.yml@refs/heads/main",
    "GITHUB_JOB": "execution",
    "GITHUB_RUN_ID": str(SYNTH_RUN),
    "GITHUB_RUN_NUMBER": "6",
    "GITHUB_RUN_ATTEMPT": "1",
    "GITHUB_SHA": MAIN_SHA,
    "GITHUB_WORKFLOW_SHA": MAIN_SHA,
    "GITHUB_OUTPUT": str(ROOT / "github_output_guard_step"),
}
TODAY = date(2026, 10, 1)
POLICY = guard.load_policy(REPO / "tools/historical-execution-policy.json")
RESULTS = []


def scenario(name, *, mode="live", comment_id=SYNTH_COMMENT, env=None, run_overrides=None,
             include_run=True, expect, run_mode="real", **intercept):
    log = []
    base = (Live if mode == "live" else Replay)(TOKEN, log)
    run = synth_run(MAIN_SHA, MAIN_TREE, **(run_overrides or {}))
    api = Intercept(base, log, run=run, include_run=include_run, **intercept)
    e = dict(BASE_ENV, **(env or {}))
    outcome, reason, result = None, None, None
    try:
        result = guard.verify(api, POLICY, e, run_mode, comment_id, TODAY)
        outcome = "PASS"
    except guard.GuardError as error:
        outcome, reason = "REFUSED", str(error)
    except Exception as error:  # harness defect, not a guard refusal
        outcome, reason = "HARNESS_ERROR", repr(error)
        traceback.print_exc()
    ok = (outcome == "PASS") if expect == "PASS" else (outcome == "REFUSED" and reason == expect)
    record = {"scenario": name, "source": mode, "expect": expect, "outcome": outcome, "reason": reason,
              "matches_expectation": ok, "live_api_calls": base.count,
              "replayed_calls": sum(1 for t, _ in log if t == "REPLAY"),
              "synthetic_responses": sum(1 for t, _ in log if t.startswith("SYNTH"))}
    RESULTS.append(record)
    (LOGDIR / (name + ".paths.json")).write_text(json.dumps(log, indent=1))
    print(json.dumps(record), flush=True)
    return result


def main():
    print(json.dumps({"python": sys.version.split()[0], "main_sha": MAIN_SHA, "main_tree": MAIN_TREE,
                      "candidate_canonical_sha256": CANDIDATE_SHA,
                      "operative_body_sha256": hashlib.sha256(OPERATIVE_TEXT.encode()).hexdigest()}), flush=True)
    (HERE / "synthetic-operative-comment-body.json").write_text(OPERATIVE_TEXT)

    # 1. Positive path, fully live except the three synthetic resources.
    result = scenario("P1_positive_verify_live", expect="PASS")
    if result is not None:
        (HERE / "verify-execution.json").write_bytes(guard.encode(result))

    # 2. guard.main() end to end, GitHub class monkeypatched to the intercepting wrapper.
    captured = {}
    real_verify = guard.verify

    def transparent_verify(*a, **k):  # records a refusal reason, behaviour unchanged
        try:
            return real_verify(*a, **k)
        except guard.GuardError as error:
            captured["reason"] = str(error)
            raise

    main_log = []
    main_base = {}

    def patched_github(token):
        base = Live(token, main_log)
        main_base["b"] = base
        return Intercept(base, main_log, run=synth_run(MAIN_SHA, MAIN_TREE))

    saved_env = dict(os.environ)
    out_dir, storage = ROOT / "guard", ROOT / "data"
    Path(BASE_ENV["GITHUB_OUTPUT"]).write_text("")
    os.environ.update(BASE_ENV)
    guard.GitHub, guard.verify = patched_github, transparent_verify
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            code = guard.main(["--policy", str(REPO / "tools/historical-execution-policy.json"),
                               "--readiness-comment-id", str(SYNTH_COMMENT), "--mode", "real",
                               "--output-dir", str(out_dir), "--storage-root", str(storage)])
    finally:
        guard.GitHub, guard.verify = RealGitHub, real_verify
        os.environ.clear()
        os.environ.update(saved_env)
    stdout = buf.getvalue()
    gh_output = Path(BASE_ENV["GITHUB_OUTPUT"]).read_text()
    files = sorted(p.name for p in out_dir.iterdir()) if out_dir.exists() else []
    record = {"scenario": "P2_guard_main_end_to_end_live", "exit_code": code, "stdout": stdout,
              "refusal_reason": captured.get("reason"), "output_files": files,
              "github_output": gh_output, "live_api_calls": main_base["b"].count if "b" in main_base else 0,
              "output_dir_mode": oct(out_dir.stat().st_mode & 0o777) if out_dir.exists() else None,
              "execution_json_sha256": hashlib.sha256((out_dir / "execution.json").read_bytes()).hexdigest() if (out_dir / "execution.json").exists() else None,
              "approval_json_sha256": hashlib.sha256((out_dir / "approval.json").read_bytes()).hexdigest() if (out_dir / "approval.json").exists() else None}
    record["matches_expectation"] = (code == 0 and stdout.strip() == '{"status":"PASS"}' and
                                     files == ["approval.json", "execution.json"] and
                                     gh_output == "checkout_sha=" + guard.parse(OPERATIVE_TEXT)["checkout_sha"] + "\n")
    if (out_dir / "execution.json").exists() and result is not None:
        main_exec = json.loads((out_dir / "execution.json").read_text())
        p1 = json.loads(guard.encode(result))
        diff = sorted(k for k in set(main_exec) | set(p1) if main_exec.get(k) != p1.get(k))
        record["execution_json_differs_from_P1_in"] = diff
        hv_diff = sorted(k for k in set(main_exec["history_verification"]) | set(p1["history_verification"])
                         if main_exec["history_verification"].get(k) != p1["history_verification"].get(k))
        record["history_verification_differs_in"] = hv_diff
    (LOGDIR / "P2_guard_main_end_to_end_live.paths.json").write_text(json.dumps(main_log, indent=1))
    RESULTS.append(record)
    print(json.dumps(record), flush=True)

    # 3. Negative controls. Early-failing ones run live; late-failing ones replay
    #    the live responses recorded above (labelled "replay").
    scenario("N1_authorized_on_2026-09-30_unchanged_candidate", mode="live",
             body=CANDIDATE_TEXT, expect="execution_release_not_after_merge")
    scenario("N2_full_prose_body_of_5921715962", mode="live", body=PROSE, expect="invalid_json")
    scenario("N2b_real_comment_5921715962_unintercepted", mode="live", comment_id=5921715962,
             expect="invalid_json")
    scenario("N3_json_wrapped_in_json_fence", mode="live",
             body="```json\n" + OPERATIVE_TEXT + "\n```", expect="invalid_json")
    scenario("N3b_json_fence_with_crlf", mode="replay",
             body=("```json\n" + OPERATIVE_TEXT + "\n```").replace("\n", "\r\n"), expect="invalid_json")
    scenario("N4a_synthetic_run_display_title_rehearsal", mode="replay",
             run_overrides={"display_title": "historical-input-rehearsal", "name": "historical-input-rehearsal"},
             expect="wrong_historical_phase")
    scenario("N4b_synthetic_run_number_7_env_6", mode="replay", run_overrides={"run_number": 7},
             expect="incomplete_or_consumed_history")
    scenario("N4c_env_run_number_7", mode="replay", env={"GITHUB_RUN_NUMBER": "7"},
             run_overrides={"run_number": 7}, expect="execution_slot_consumed")
    scenario("N4d_mode_rehearsal", mode="replay", run_mode="rehearsal", expect="rehearsal_slot_closed")
    scenario("N5_consumed_comment_5920107119", mode="live", comment_id=5920107119,
             expect="consumed_readiness_comment")
    scenario("N6_comment_by_other_user", mode="replay", login="someone-else",
             expect="untrusted_readiness_comment")
    scenario("N7_comment_before_merge_authorized_same_day", mode="replay", created="2026-09-30T23:00:00Z",
             body=CANDIDATE_TEXT, expect="execution_release_not_after_merge")
    scenario("N8_history_without_current_native6_run", mode="replay", include_run=False,
             expect="incomplete_or_consumed_history")
    scenario("N9_run_head_sha_not_GITHUB_SHA", mode="replay",
             run_overrides={"head_sha": "d6d774346015c3d2abfe7b7318316292daab57cb"},
             expect="current_run_not_durable")
    scenario("N10_run_attempt_2", mode="replay", run_overrides={"run_attempt": 2},
             expect="unaccounted_or_retried_run")
    scenario("N11_comment_on_other_issue", mode="replay", issue=97, expect="untrusted_readiness_comment")

    # 4. Unaffected controls that must still pass.
    scenario("U1_trailing_newline_body", mode="live", body=OPERATIVE_TEXT + "\n", expect="PASS")
    scenario("U2_crlf_body", mode="replay", body=OPERATIVE_TEXT.replace("\n", "\r\n") + "\r\n", expect="PASS")
    scenario("U3_compact_canonical_body", mode="replay",
             body=guard.encode(json.loads(OPERATIVE_TEXT)).decode(), expect="PASS")

    summary = {"live_github_api_calls_total": LIVE_CALLS["total"],
               "all_match": all(r["matches_expectation"] for r in RESULTS), "results": RESULTS}
    (HERE / "results.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps({"live_github_api_calls_total": LIVE_CALLS["total"], "all_match": summary["all_match"]}))


if __name__ == "__main__":
    main()
