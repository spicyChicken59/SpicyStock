"""The analyst's daily brief over the page's `full` fixture: one golden pair.

``brief.json`` and ``brief.md`` here are ``src.brief.derive()`` over
``tests/fixtures/page/full.json`` and ``full-picks.json``, byte for byte, with
no model-record block carried (the pair says it was not computed). They are
what a reader of the brief sees, kept so a change to a sentence, a field or a
bound shows up as a diff a reviewer can read. ``--check`` holds the committed
pair to the code and the fixture, and runs in CI beside the other fixture
checks. The page fixtures are regenerated first when the record's shape or
the rules digest moves; this pair is regenerated after them."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src import brief

TARGET = Path(__file__).parent
PAGE = ROOT / "tests" / "fixtures" / "page"
SOURCE, PICKS = PAGE / "full.json", PAGE / "full-picks.json"


def outputs() -> dict:
    canonical_raw, picks_raw = SOURCE.read_bytes(), PICKS.read_bytes()
    json_raw, md_raw = brief.derive(canonical_raw, picks_raw)
    brief.validate(canonical_raw, picks_raw, json_raw, md_raw)
    return {brief.JSON_FILE: json_raw, brief.MD_FILE: md_raw}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare the committed pair; write nothing")
    args = parser.parse_args(argv)
    files = outputs()
    if args.check:
        stale = [name for name, raw in files.items()
                 if not (TARGET / name).is_file() or (TARGET / name).read_bytes() != raw]
        if stale:
            print("Stale brief fixtures: " + ", ".join(stale))
            return 1
    else:
        for name, raw in files.items():
            (TARGET / name).write_bytes(raw)
    print(f"{len(files)} brief fixture files " + ("current" if args.check else "written"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
