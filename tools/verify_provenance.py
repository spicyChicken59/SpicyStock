"""Verify a publication or retained recovery archive, completely offline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src import provenance  # noqa: E402


def archived(directory):
    directory = Path(directory)
    data = json.loads((directory / "record.json").read_bytes())
    data["bursts"] = []
    data["watchlist"] = {"top": [], "also_quiet": []}
    order = data.get("evidence_candidates")
    if order is None:
        order = [(item["kind"], item["row"]["ticker"], item.get("quiet", False))
                 for path in sorted(directory.glob("*.json")) if path.name != "record.json"
                 for item in [json.loads(path.read_bytes())]]
    for kind, ticker, quiet in order:
        item = json.loads((directory / f"{kind}-{ticker}.json").read_bytes())
        target = data["bursts"] if kind == "burst" else data["watchlist"]["also_quiet" if quiet else "top"]
        target.append(item["row"])
    return data


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--record", type=Path)
    source.add_argument("--archive", type=Path, help="one docs/history/<source> directory")
    p.add_argument("--picks", type=Path, help="also verify persisted plan agreement")
    p.add_argument("--objects", type=Path, help="content-addressed evidence directory")
    args = p.parse_args(argv)
    try:
        data = archived(args.archive) if args.archive else json.loads(args.record.read_bytes())
        picks = json.loads(args.picks.read_bytes()) if args.picks else None
        objects = args.objects or ((args.archive.parent.parent if args.archive else args.record.parent) / provenance.OBJECT_DIR)
        result = provenance.verify(data, picks, objects, require_picks=args.picks is not None)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        result = {"status": "FAIL", "breaks": [str(exc)], "missing": [], "checked": []}
    print(json.dumps(result, indent=2))
    return {"PASS": 0, "FAIL": 1, "PARTIAL": 2}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
