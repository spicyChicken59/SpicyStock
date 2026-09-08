"""Fail if the fixture has drifted from the generator that produces it — or if
docs/data.json claims to BE that fixture and is not a copy of it.

The batch-1 audit found the fixture describing a 4,783-symbol Alpaca universe
while the scanner had been changed to read a 230-name checked-in file, and four
rows that could not have survived detect_setup's own floors. Neither the smoke
test nor the Python suite could see it: one checks the page against the data,
the other never opens the data. This closes that gap.

TWO FIXTURES, AND A COPY. The canonical one-night fixture is
tests/fixtures/data.json, guarded here against tools/make_fixture.py; the
thirty-run history is tests/fixtures/history/, guarded against
tools/make_history.py, which drives the real pipeline and is byte-deterministic
for exactly this reason. docs/data.json is whatever the last run wrote: a copy
of the canonical fixture, byte for byte, only while nothing has published, and
the run evening.yml last committed back after that -- which here it has, since
6 Sep 2026. Until 3.1 this
script compared docs/data.json itself to the generator, which made the first
successful commit-back turn CI red on the next push, permanently, for the crime
of the pipeline working. A guard that has to be defeated to ship is worse than
none. So a docs/data.json that says `run.fixture: true` must be the canonical
file, and one that says false is a run and none of this script's business.
"""
import json, pathlib, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
CANONICAL = ROOT / "tests" / "fixtures" / "data.json"
HISTORY = ROOT / "tests" / "fixtures" / "history"
LIVE = ROOT / "docs" / "data.json"
REGENERATE = "python3 tools/make_fixture.py tests/fixtures/data.json"
REGENERATE_HISTORY = "python3 tools/make_history.py tests/fixtures/history"


def _generator_failed(proc: subprocess.CompletedProcess) -> bool:
    """Surface the generator's own error. capture_output + check=True hides
    it behind an opaque CalledProcessError in the CI log."""
    if proc.returncode == 0:
        return False
    print(proc.stdout, end="")
    print(proc.stderr, end="", file=sys.stderr)
    return True


def _first_difference(stored, generated, path="$", *, limit=180) -> str | None:
    """Name the first differing value without dumping an entire fixture."""
    if stored == generated:
        return None
    if isinstance(stored, dict) and isinstance(generated, dict):
        for key in sorted(stored.keys() | generated.keys()):
            child = f"{path}[{json.dumps(key)}]"
            if key not in stored:
                return f"{child}: missing from committed fixture"
            if key not in generated:
                return f"{child}: absent from regenerated fixture"
            difference = _first_difference(stored[key], generated[key], child, limit=limit)
            if difference:
                return difference
    if isinstance(stored, list) and isinstance(generated, list):
        if len(stored) != len(generated):
            return f"{path}: committed length {len(stored)}, regenerated length {len(generated)}"
        for index, (left, right) in enumerate(zip(stored, generated)):
            difference = _first_difference(left, right, f"{path}[{index}]", limit=limit)
            if difference:
                return difference
    return f"{path}: committed {repr(stored)[:limit]}, regenerated {repr(generated)[:limit]}"


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / "regenerated.json"
        proc = subprocess.run([sys.executable, str(ROOT / "tools" / "make_fixture.py"), str(out)],
                              capture_output=True, text=True)
        if _generator_failed(proc):
            return proc.returncode
        fresh = json.loads(out.read_text())
        hist_out = pathlib.Path(tmp) / "history"
        proc = subprocess.run([sys.executable, str(ROOT / "tools" / "make_history.py"), str(hist_out)],
                              capture_output=True, text=True)
        if _generator_failed(proc):
            return proc.returncode
        fresh_history = {name: json.loads((hist_out / name).read_text())
                         for name in ("data.json", "ledger.json")}
    if not CANONICAL.exists():
        print(f"{CANONICAL.relative_to(ROOT)} is missing — re-run: {REGENERATE}")
        return 1
    canonical = json.loads(CANONICAL.read_text())
    if canonical != fresh:
        print(f"{CANONICAL.relative_to(ROOT)} is stale — re-run: {REGENERATE}")
        print("First difference:", _first_difference(canonical, fresh))
        return 1
    for name, regenerated in fresh_history.items():
        path = HISTORY / name
        if not path.exists() or json.loads(path.read_text()) != regenerated:
            print(f"{path.relative_to(ROOT)} is {'missing' if not path.exists() else 'stale'} "
                  f"— re-run: {REGENERATE_HISTORY}")
            if path.exists():
                print("First difference:", _first_difference(json.loads(path.read_text()), regenerated))
            return 1
    runs = len(fresh_history["ledger.json"]["runs"])

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
          f"history fixture is current: {runs} runs; {state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
