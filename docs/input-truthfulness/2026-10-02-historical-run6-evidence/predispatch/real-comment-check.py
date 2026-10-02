"""Guard dry run with the REAL readiness comment 5924734477 (not intercepted).
Only the prospective native-6 run, its detail and its jobs are synthetic."""
import contextlib, io, json, os, sys, hashlib
from datetime import date
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, "/tmp/claude-0/-home-user/be741bed-fa94-5c2e-96dd-d4c8505bc631/scratchpad/native6/guard-dry-run")
import harness as h
guard = h.guard
REAL = 5924734477
OUT = Path(os.environ["DRY_HISTORICAL_ROOT"])
print(json.dumps({"main_sha": h.MAIN_SHA}))
for today in (date(2026, 10, 1), date(2026, 10, 2)):
    h.TODAY = today
    r = h.scenario(f"REAL_comment_{REAL}_today_{today}", comment_id=REAL, expect="PASS")
    if r is not None and today == date(2026, 10, 1):
        (OUT / "verify-real.json").write_bytes(guard.encode(r))
h.TODAY = date(2026, 10, 1)
# Controls: same real comment with wrong mode / consumed slot / run 7 queued.
h.scenario("REAL_ctrl_mode_rehearsal", comment_id=REAL, run_mode="rehearsal", expect="rehearsal_slot_closed")
h.scenario("REAL_ctrl_env_run_7", comment_id=REAL, env={"GITHUB_RUN_NUMBER": "7"}, expect="execution_slot_consumed")
h.scenario("REAL_ctrl_today_before_authorization", comment_id=REAL, expect="invalid_authorization_date") if False else None
# guard.main() end to end with the real comment id.
saved, captured = dict(os.environ), {}
rv = guard.verify
def tv(*a, **k):
    try: return rv(*a, **k)
    except guard.GuardError as e: captured["reason"] = str(e); raise
log = []
def pg(token): return h.Intercept(h.Live(token, log), log, run=h.synth_run(h.MAIN_SHA, h.MAIN_TREE))
outp = OUT / "gh_output"; outp.write_text("")
env = dict(h.BASE_ENV, GITHUB_OUTPUT=str(outp))
os.environ.update(env); guard.GitHub, guard.verify = pg, tv
buf = io.StringIO()
try:
    with contextlib.redirect_stdout(buf):
        code = guard.main(["--policy", str(h.REPO / "tools/historical-execution-policy.json"), "--readiness-comment-id", str(REAL),
                           "--mode", "real", "--output-dir", str(OUT / "guard"), "--storage-root", str(OUT / "data")])
finally:
    guard.GitHub, guard.verify = h.RealGitHub, rv; os.environ.clear(); os.environ.update(saved)
ex = json.loads((OUT / "guard/execution.json").read_text()) if (OUT / "guard/execution.json").exists() else {}
print(json.dumps({"scenario": "REAL_guard_main", "exit": code, "stdout": buf.getvalue().strip(), "reason": captured.get("reason"),
                  "gh_output": outp.read_text(), "readiness_comment_id": ex.get("readiness_comment_id"),
                  "run_number": ex.get("run_number"), "checkout_sha": ex.get("checkout_sha"), "workflow_sha": ex.get("workflow_sha"),
                  "live_calls": sum(1 for t, _ in log if t == "LIVE"), "synthetic": sum(1 for t, _ in log if t.startswith("SYNTH"))}))
print(json.dumps({"all_match": all(r["matches_expectation"] for r in h.RESULTS)}))
