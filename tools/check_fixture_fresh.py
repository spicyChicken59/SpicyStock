"""Fail if the fixture has drifted from the generator that produces it — or if
docs/data.json claims to BE that fixture and is not a copy of it.

The batch-1 audit found the fixture describing a 4,783-symbol Alpaca universe
while the scanner had been changed to read a 230-name checked-in file, and four
rows that could not have survived detect_setup's own floors. Neither the smoke
test nor the Python suite could see it: one checks the page against the data,
the other never opens the data. This closes that gap.

TWO FILES, ONE FIXTURE. The canonical copy is tests/fixtures/data.json, and it
is what this guards against tools/make_fixture.py. docs/data.json is whatever
the last run wrote: the same fixture, byte for byte, on a fresh clone -- and
last night's real run once evening.yml has committed one back. Until 3.1 this
script compared docs/data.json itself to the generator, which made the first
successful commit-back turn CI red on the next push, permanently, for the crime
of the pipeline working. A guard that has to be defeated to ship is worse than
none. So a docs/data.json that says `run.fixture: true` must be the canonical
file, and one that says false is a run and none of this script's business.
"""
import json, pathlib, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
CANONICAL = ROOT / "tests" / "fixtures" / "data.json"
LIVE = ROOT / "docs" / "data.json"
REGENERATE = "python3 tools/make_fixture.py tests/fixtures/data.json"


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / "regenerated.json"
        proc = subprocess.run([sys.executable, str(ROOT / "tools" / "make_fixture.py"), str(out)],
                              capture_output=True, text=True)
        if proc.returncode != 0:
            # Surface the generator's own error. capture_output + check=True
            # hides it behind an opaque CalledProcessError in the CI log.
            print(proc.stdout, end="")
            print(proc.stderr, end="", file=sys.stderr)
            return proc.returncode
        fresh = json.loads(out.read_text())
    if not CANONICAL.exists():
        print(f"{CANONICAL.relative_to(ROOT)} is missing — re-run: {REGENERATE}")
        return 1
    canonical = json.loads(CANONICAL.read_text())
    if canonical != fresh:
        print(f"{CANONICAL.relative_to(ROOT)} is stale — re-run: {REGENERATE}")
        return 1

    if not LIVE.exists():
        # The page fetches this file and renders "Snapshot unavailable" without
        # it. A clone that cannot render the dashboard is a broken clone.
        print(f"{LIVE.relative_to(ROOT)} is missing — the page needs it; "
              f"`cp tests/fixtures/data.json docs/data.json` seeds it with the fixture")
        return 1
    live = json.loads(LIVE.read_text())
    run = live.get("run") if isinstance(live.get("run"), dict) else {}
    if run.get("fixture"):
        if LIVE.read_bytes() != CANONICAL.read_bytes():
            print(f"{LIVE.relative_to(ROOT)} says it is the fixture (run.fixture is true) but "
                  f"is not a copy of {CANONICAL.relative_to(ROOT)} — "
                  "`cp tests/fixtures/data.json docs/data.json`, or let a real run replace it")
            return 1
        state = "docs/data.json is that fixture, byte for byte"
    else:
        state = (f"docs/data.json is the {run.get('type', '?')} run of {run.get('date', '?')}, "
                 "not the fixture — not this guard's business")
    print(f"fixture is current: {len(canonical['candidates'])} scored, "
          f"{len(canonical['gated_out'])} gated, universe {canonical['run']['universe']['size']}; "
          f"{state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
