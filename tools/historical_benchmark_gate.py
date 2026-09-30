"""Skip only observed docs-only pushes; material changes require measurement.

A skip is NOT RUN, never evidence of a passing benchmark for another checkout.
The existing pytest/browser jobs remain independent of this optional-cost gate.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess


_SHA = re.compile(r"[0-9a-f]{40}\Z")
DOCUMENTATION = {"README.md", ".env.example", "CLAUDE.md",
                 "docs/input-truthfulness/2026-09-29-historical-execution.md",
                 "docs/input-truthfulness/2026-09-30-delivery-readiness.md",
                 "docs/input-truthfulness/historical-delivery-release-evidence.json"}
NEW_EVIDENCE = "docs/input-truthfulness/2026-09-30-delivery-readiness-evidence/"
def _changed_paths(run, before, head):
    changed = run(["diff", "--name-only", "-z", "--no-renames", before, head])
    if changed.returncode != 0:
        raise ValueError("diff_unavailable")
    paths = [p.decode("utf-8", "strict") for p in changed.stdout.split(b"\0") if p]
    if not paths or any("\n" in p or "\r" in p or p.startswith("/") or ".." in p.split("/") for p in paths):
        raise ValueError("empty_or_ambiguous_diff")
    return paths


def relevant(path):
    # Unknown files are material. In particular, prior inventories, attributes,
    # dependencies, actions and fixtures cannot quietly become a docs-only push.
    return path not in DOCUMENTATION and not path.startswith(NEW_EVIDENCE)


def decide(event, *, git=None):
    result = {"schema": "historical-runtime-pr-gate-v1", "status": "NOT RUN", "run_required": True,
              "reason": "unverified_event_range", "claim": "This decision is not a benchmark result or execution release."}
    if event.get("action") != "synchronize":
        result["reason"] = "initial_or_reopened_review_requires_measurement"
        return result
    before, head = event.get("before"), event.get("pull_request", {}).get("head", {}).get("sha")
    if not all(isinstance(value, str) and _SHA.fullmatch(value) for value in (before, head)) or before == head:
        return result
    result.update(observed_before=before, observed_head=head)
    run = git or (lambda arguments: subprocess.run(["git", *arguments], capture_output=True, check=False))
    try:
        if run(["merge-base", "--is-ancestor", before, head]).returncode != 0:
            result["reason"] = "range_unavailable_or_not_ancestor"
            return result
        paths = _changed_paths(run, before, head)
        material = [p for p in paths if relevant(p)]
        result.update(run_required=bool(material), changed_file_count=len(paths), relevant_changed_paths=material,
                      reason="runtime_or_validation_inputs_changed" if material else "observed_docs_only_push_no_runtime_change")
    except (OSError, UnicodeError, ValueError, TypeError, AttributeError):
        return result
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = decide(json.loads(args.event.read_bytes()))
    except (OSError, ValueError, TypeError, AttributeError):
        result = {"schema": "historical-runtime-pr-gate-v1", "status": "NOT RUN", "run_required": True,
                  "reason": "event_unavailable"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes((json.dumps(result, sort_keys=True, indent=2) + "\n").encode())
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
            stream.write("run_required=" + str(result["run_required"]).lower() + "\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
