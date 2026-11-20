#!/usr/bin/env python3
"""Write, or check, ``docs/strategy.html`` from the code and the committed record.

    python tools/build_strategy_page.py            # write it beside docs/data.json
    python tools/build_strategy_page.py --check    # refuse unless the committed page is current

The page is ``src/strategy_page.build()`` over ``docs/data.json``'s bytes; the
evening writes it after every publication, and CI runs ``--check`` so a change
to a constant the page prints cannot land without the page that prints it.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import strategy_page  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--docs", type=Path, default=ROOT / "docs")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.check:
        found = strategy_page.check(args.docs)
        if found:
            print("stale: " + "; ".join(found), file=sys.stderr)
            return 1
        print(f"current: {strategy_page.FILE} is what the code and the committed record write")
        return 0
    path = strategy_page.write(args.docs)
    print(f"wrote {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
