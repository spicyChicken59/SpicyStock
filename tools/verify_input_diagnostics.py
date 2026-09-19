"""Read an extracted input artifact offline; verify its membership and identity."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import input_diagnostics as diag


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--run-id", required=True, help="independently expected Actions run ID")
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--revision", required=True, help="actual execution checkout from the run log")
    parser.add_argument("--publication", type=Path, help="optional same-run data.json to reconcile input boundaries")
    args = parser.parse_args(argv)
    record = json.loads((args.directory / diag.RECORD_NAME).read_bytes())
    expected = {**record["run"], "run_id": args.run_id, "attempt": args.attempt, "execution_revision": args.revision}
    directory = args.directory / diag.DIRECTORY_NAME
    raw = directory.read_bytes() if directory.exists() else None
    publication = json.loads(args.publication.read_bytes())["run"] if args.publication else None
    if publication and (publication["run_id"] != args.run_id
                        or publication["session"] != record["capture"]["evaluated_session"]
                        or publication["expected_session"] != record["capture"]["expected_session"]):
        raise ValueError("publication and diagnostic run/session differ")
    diag.validate(record, expected_run=expected, ledger=publication["coverage"] if publication else None,
                  directory_bytes=raw)
    print(json.dumps({"validated": True, "run": record["run"], "capture": record["capture"],
                      "exceptions": {k: v["count"] for k, v in record["exceptions"].items()},
                      "payload": record["payload"], "directory": record["directory"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
