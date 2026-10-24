"""Print where every discovered candidate stopped, for one or many publications.

A reading, not a check and not a rule: it runs ``funnel.build`` -- the same
function the evening run writes into every record -- over publications given
as files, as ``<commit>`` objects of this repository, or as every retained
publication of a ref's history, and prints the stage counts. It changes no
record, decides nothing and fetches nothing. A publication made under older
rules is read for what it recorded; a stage its fields cannot establish is
``unknown`` and printed as such.

    python tools/candidate_funnel.py docs/data.json
    python tools/candidate_funnel.py --git 43dcb8d7 e67f8cba
    python tools/candidate_funnel.py --history --ref origin/main --limit 64 --markdown out.md --json out.json
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import funnel  # noqa: E402

RECORD_PATH = "docs/data.json"
HISTORY_LIMIT = 64
#: the columns a reading prints, the reaction stages first, then the anticipation's
REACTION_COLUMNS = tuple(s for s in funnel.REACTION_STAGES)
ANTICIPATION_COLUMNS = tuple(s for s in funnel.ANTICIPATION_STAGES)


class FunnelError(RuntimeError):
    """The reading could not be made; nothing was printed as if it had."""


def _git(*args: str) -> bytes:
    done = subprocess.run(["git", *args], cwd=ROOT, capture_output=True)
    if done.returncode != 0:
        raise FunnelError("git could not produce " + " ".join(args))
    return done.stdout


def read_file(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    if path.suffix == ".gz":
        raw = gzip.decompress(raw)
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def read_commit(commit: str) -> tuple[dict, str, str]:
    """The record a commit carries, its blob identity and the full commit id."""
    full = _git("rev-parse", "--verify", f"{commit}^{{commit}}").decode().strip()
    blob = _git("rev-parse", f"{full}:{RECORD_PATH}").decode().strip()
    raw = _git("cat-file", "-p", f"{full}:{RECORD_PATH}")
    return json.loads(raw), blob, full


def history_commits(ref: str, limit: int) -> list[str]:
    """The commits that changed the record on ``ref``, newest first, bounded."""
    if limit < 1:
        raise FunnelError("limit must be at least 1")
    out = _git("log", "--format=%H", f"--max-count={limit}", ref, "--", RECORD_PATH).decode().split()
    return out


def reading(data: dict, *, source: str, identity: str) -> dict:
    """One publication's funnel beside the facts that place it."""
    if (not isinstance(data, dict) or data.get("fixture") or data.get("schema_version") != 2
            or not isinstance(data.get("run"), dict) or not isinstance(data.get("app"), dict)):
        raise FunnelError(f"{source}: not a real schema-2 publication")
    run = data["run"]
    block = funnel.build(data)
    return {
        "source": source, "identity": identity,
        "session": run.get("session"), "session_state": run.get("session_state"),
        "published_at": run.get("published_at"), "rules_version": data["app"].get("rules_version"),
        "archived": isinstance((data.get("rules") or {}).get("funnel"), dict),
        "built_under": block["version"],   # the archived funnel version, or the current one for a record from before the rule
        "regime": block["regime"], "admitted_grades": block["admitted_grades"],
        "reaction": {k: block["reaction"][k] for k in ("discovered", "potentially_usable", "by_mechanical_grade", "stages")},
        "anticipation": {k: block["anticipation"][k] for k in ("listed", "counts", "stages")},
        "sentence": block["sentence"],
    }


def _nonzero(stages: dict) -> str:
    return ", ".join(f"{s} {n}" for s, n in stages.items() if n) or "—"


def table(readings: list[dict]) -> str:
    head = ("| session | state | regime | admitted | archived | discovered | usable | reaction stages | listed | anticipation stages |",
            "|---|---|---|---|---|---:|---:|---|---:|---|")
    rows = []
    for r in readings:
        rows.append("| {session} | {state} | {regime} | {admitted} | {archived} | {discovered} | {usable} | {rs} | {listed} | {as_} |".format(
            session=r["session"], state=r["session_state"] or "—", regime=r["regime"] or "unknown",
            admitted="/".join(r["admitted_grades"]) if r["admitted_grades"] else ("none" if r["admitted_grades"] == [] else "unknown"),
            archived="yes" if r["archived"] else "no", discovered=r["reaction"]["discovered"],
            usable=r["reaction"]["potentially_usable"], rs=_nonzero(r["reaction"]["stages"]),
            listed=r["anticipation"]["listed"], as_=_nonzero(r["anticipation"]["stages"])))
    return "\n".join(head + tuple(rows))


def totals(readings: list[dict]) -> dict:
    out = {"publications": len(readings), "sessions": len({r["session"] for r in readings}),
           "regimes": {}, "reaction": {s: 0 for s in REACTION_COLUMNS}, "anticipation": {s: 0 for s in ANTICIPATION_COLUMNS},
           "discovered": 0, "potentially_usable": 0, "listed": 0}
    for r in readings:
        out["regimes"][r["regime"] or "unknown"] = out["regimes"].get(r["regime"] or "unknown", 0) + 1
        out["discovered"] += r["reaction"]["discovered"]
        out["potentially_usable"] += r["reaction"]["potentially_usable"]
        out["listed"] += r["anticipation"]["listed"]
        for s, n in r["reaction"]["stages"].items():
            out["reaction"][s] += n
        for s, n in r["anticipation"]["stages"].items():
            out["anticipation"][s] += n
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("records", nargs="*", type=Path, help="publication files (.json or .json.gz)")
    parser.add_argument("--git", nargs="+", default=[], metavar="COMMIT", help="read docs/data.json at these commits")
    parser.add_argument("--history", action="store_true", help="every commit on --ref that changed docs/data.json")
    parser.add_argument("--ref", default="origin/main")
    parser.add_argument("--limit", type=int, default=HISTORY_LIMIT)
    parser.add_argument("--json", type=Path, help="write the readings and totals here")
    parser.add_argument("--markdown", type=Path, help="write the table here")
    args = parser.parse_args(argv)
    try:
        readings = []
        for path in args.records:
            data, sha = read_file(path)
            readings.append(reading(data, source=str(path), identity=f"sha256:{sha}"))
        for commit in args.git:
            data, blob, full = read_commit(commit)
            readings.append(reading(data, source=f"{full[:8]}:{RECORD_PATH}", identity=f"blob:{blob}"))
        # a ref's history carries the first build's records and committed fixtures
        # beside the real publications: those are named and left out, never read
        skipped = []
        for commit in (history_commits(args.ref, args.limit) if args.history else []):
            try:
                data, blob, full = read_commit(commit)
                readings.append(reading(data, source=f"{full[:8]}:{RECORD_PATH}", identity=f"blob:{blob}"))
            except (ValueError, KeyError, TypeError, AttributeError, FunnelError) as exc:
                skipped.append({"commit": commit, "reason": str(exc)})
    except (OSError, ValueError, KeyError, TypeError, FunnelError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    if not readings:
        parser.error("give a record, --git commits or --history")
    readings.sort(key=lambda r: ((r["session"] or ""), (r["published_at"] or "")))
    summary = totals(readings)
    print(table(readings))
    print()
    print(f"{summary['publications']} publications over {summary['sessions']} sessions; regimes {summary['regimes']}; "
          f"discovered {summary['discovered']}, potentially usable {summary['potentially_usable']}, "
          f"reaction tickets {summary['reaction']['ticket']}; listed {summary['listed']}, anticipation tickets {summary['anticipation']['ticket']}.")
    for row in skipped:
        print(f"skipped {row['commit'][:8]}: {row['reason']}")
    if args.markdown:
        args.markdown.write_text(table(readings) + "\n")
    if args.json:
        args.json.write_text(json.dumps({"version": funnel.VERSION, "policy": funnel.POLICY, "ref": args.ref if args.history else None,
                                         "readings": readings, "skipped": skipped, "totals": summary}, indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
