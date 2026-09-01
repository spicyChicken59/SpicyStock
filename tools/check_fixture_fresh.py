"""Fail if docs/data.json has drifted from the generator that produces it.

The batch-1 audit found the fixture describing a 4,783-symbol Alpaca universe
while the scanner had been changed to read a 230-name checked-in file, and four
rows that could not have survived detect_setup's own floors. Neither the smoke
test nor the Python suite could see it: one checks the page against the data,
the other never opens the data. This closes that gap.
"""
import json, pathlib, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent

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
        live = json.loads((ROOT / "docs" / "data.json").read_text())
        fresh = json.loads(out.read_text())
    if live != fresh:
        print("docs/data.json is stale — re-run: python3 tools/make_fixture.py docs/data.json")
        return 1
    print(f"fixture is current: {len(live['candidates'])} scored, "
          f"{len(live['gated_out'])} gated, universe {live['run']['universe']['size']}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
