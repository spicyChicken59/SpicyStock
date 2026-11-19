"""The execution handoff over committed fixtures: golden files a reviewer and an
execution agent can read.

``full/`` is ``src.orders`` over the page's ``full`` fixture and its picks:
``orders.json`` and ``positions-template.json``. ``morning/`` is the morning
go/cancel file over the morning fixtures' own publication
(``tests/fixtures/morning/full-publication.json``), one per committed morning
receipt, each validated against that publication as the persist job
validates it. ``--check`` holds every file to the code and runs in CI beside
the other fixture checks; regenerate this after the page and morning
fixtures."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src import orders

TARGET = Path(__file__).parent
PAGE = ROOT / "tests" / "fixtures" / "page"
MORNING = ROOT / "tests" / "fixtures" / "morning"
RECEIPTS = ("observed", "halted", "corporate-excluded", "outage", "no-tickets")


def outputs() -> dict:
    files = {}
    raw = PAGE.joinpath("full.json").read_bytes()
    full = orders.encode(orders.build(raw, PAGE.joinpath("full-picks.json").read_bytes()))
    files["full/" + orders.FILE] = full
    files["full/" + orders.POSITIONS_FILE] = orders.encode(orders.positions_template(orders.validate(full), full))
    publication = MORNING.joinpath("full-publication.json").read_bytes()
    base = orders.encode(orders.build(publication))
    files["morning/" + orders.FILE] = base
    for name in RECEIPTS:
        receipt = MORNING.joinpath(f"{name}.json").read_bytes()
        files[f"morning/{name}.json"] = orders.encode(orders.build_morning(base, receipt, publication))
    for path, raw_out in files.items():
        kind = ("orders" if path.endswith(orders.FILE) else
                "positions" if path.endswith(orders.POSITIONS_FILE) else "orders_morning")
        orders.validate(raw_out, kind)
    return files


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare the committed files; write nothing")
    args = parser.parse_args(argv)
    files = outputs()
    if args.check:
        stale = [name for name, raw in files.items()
                 if not (TARGET / name).is_file() or (TARGET / name).read_bytes() != raw]
        if stale:
            print("stale: " + ", ".join(stale))
            return 1
        print(f"{len(files)} execution handoff files current")
        return 0
    for name, raw in files.items():
        (TARGET / name).parent.mkdir(parents=True, exist_ok=True)
        (TARGET / name).write_bytes(raw)
    print(f"wrote {len(files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
