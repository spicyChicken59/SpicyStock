"""Prove the new tests can fail: delete or break the rule each names and watch
the suite go red, then break a rule a test does NOT name and confirm it stays
green for the right reason."""
import pathlib, re, subprocess, sys

MUTANTS = [
  # (label, file, old, new, tests that must fail)
  ("the cutoff is the bell (no window at all)", "src/timing.py",
   "    return opens, opens + timedelta(minutes=window_minutes)",
   "    return opens, opens + timedelta(minutes=window_minutes + 1)",
   None),
  ("the phase is open AT the cutoff too", "src/timing.py",
   "    return PHASE_OPEN if now < cutoff else PHASE_ENDED",
   "    return PHASE_OPEN if now <= cutoff else PHASE_ENDED",
   None),
  ("the offset is hardcoded to EDT", "src/timing.py",
   "    return datetime.combine(session, when, tzinfo=MARKET_TZ)",
   "    from datetime import timezone as _tz\n    return datetime.combine(session, when, tzinfo=_tz(timedelta(hours=-4)))",
   None),
  ("the preparation reminder IS the cutoff", "src/timing.py",
   "PREPARE_BEFORE_ET = time_of_day(9, 28)",
   "PREPARE_BEFORE_ET = time_of_day(10, 0)",
   None),
  ("a closed night reads the day after its own measured session", "src/pipeline.py",
   "    applicable = plan.next_sessions(expected if closed else session, 1)[0]",
   "    applicable = plan.next_sessions(session, 1)[0]",
   None),
  ("the window's phrase stops being written from its number", "src/plan.py",
   'ENTRY_WINDOW = f"first {ENTRY_WINDOW_MINUTES} minutes"',
   'ENTRY_WINDOW = "first 20 minutes"',
   None),
  ("a naive instant is accepted", "src/timing.py",
   "    return parsed if parsed.tzinfo is not None else None",
   "    return parsed",
   None),
  ("the shape check accepts a backwards window", "src/report.py",
   '''    if stamps["opens_at"] and stamps["cutoff_at"] and stamps["cutoff_at"] <= stamps["opens_at"]:
        faults.append("run.timing.cutoff_at is not after its opens_at, so the window has no width")''',
   "    pass"),
  ("timing.RULES is not archived, so the digest does not move", "src/pipeline.py",
   "    for block in (scans.RULES, quality.RULES, plan.RULES, watchlist.RULES, record.RULES, timing.RULES, RULES):",
   "    for block in (scans.RULES, quality.RULES, plan.RULES, watchlist.RULES, record.RULES, RULES):"),
  # a rule NO new test names: the page's own next-action variant word
  ("CONTROL: a rule no timing test names (the market-bar link label)", "docs/app.js",
   "label = offered ? (cover.action_label || 'Open model plans') : 'Open model plans'",
   "label = 'Open model plans'"),
]

def run(paths):
    r = subprocess.run([sys.executable, "-m", "pytest", *paths, "-q", "--no-header", "-p", "no:randomly"],
                       capture_output=True, text=True, cwd=".")
    return r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "(no output)"

# the CLAUDE.md suite-count gate is deliberately red until the checkpoint is
# written, so it is deselected rather than left contaminating every reading
TARGETS = ["tests/test_timing.py", "tests/test_docs.py",
           "--deselect", "tests/test_docs.py::test_claude_md_counts_the_suite"]
base = run(TARGETS)
print(f"baseline: {base}\n")
for row in MUTANTS:
    label, path, old, new = row[0], row[1], row[2], row[3]
    f = pathlib.Path(path); src = f.read_text()
    if src.count(old) != 1:
        print(f"  SKIP  {label}: pattern appears {src.count(old)}x"); continue
    f.write_text(src.replace(old, new))
    try:
        line = run(TARGETS)
    finally:
        f.write_text(src)
    dead = "failed" in line
    mark = "DEAD " if dead else "ALIVE"
    print(f"  {mark} {label}\n        {line}")
