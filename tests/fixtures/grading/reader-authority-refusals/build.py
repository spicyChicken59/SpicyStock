"""Freeze every retained reply reader authority refused, from the publications on main.

Read-only over git: each schema-2 publication commit that changed
docs/data.json, each burst attempt whose recorded error is a
ReaderAuthorityError and whose reply text was retained (#88 on). One entry
for each distinct (session, ticker, reply text); revisions that carried the
same reply keep the first commit that did. The reader evidence is the
record's own checklist, copied as quality.metrics_for_model() hands it to
the reader. `--ref` is resolved to a whole commit id and recorded as
`through`; `--check` rebuilds through that same commit, so a later
publication never makes the file stale. It needs the full history; the
tests hold each entry to its own commit instead.

    python tests/fixtures/grading/reader-authority-refusals/build.py [--check] [--ref origin/main]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().with_name("refusals.json")


def git(*args, text=True):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=text, check=True).stdout


def build(ref):
    ref = git("rev-parse", f"{ref}^{{commit}}").strip()
    commits = git("log", "--reverse", "--format=%H", ref, "--", "docs/data.json").split()
    seen, entries = set(), []
    for commit in commits:
        try:
            record = json.loads(git("show", f"{commit}:docs/data.json", text=False))
        except (subprocess.CalledProcessError, ValueError):
            continue
        if record.get("schema_version") != 2:
            continue
        for burst in record.get("bursts", []):
            claude = burst.get("claude") or {}
            for attempt in claude.get("attempts") or []:
                response = attempt.get("response") if isinstance(attempt.get("response"), dict) else {}
                text = response.get("text")
                if "ReaderAuthorityError" not in (attempt.get("error") or "") or not isinstance(text, str):
                    continue
                key = (record["run"]["session"], burst["ticker"], response.get("text_sha256"))
                if key in seen:
                    continue
                seen.add(key)
                entries.append({
                    "commit": commit, "session": record["run"]["session"], "ticker": burst["ticker"],
                    "mechanical_grade": burst["quality"]["grade"], "error": attempt["error"],
                    "message_id": response.get("message_id"), "text_sha256": response["text_sha256"],
                    "text": text,
                    "reader_evidence": {"version": 1, "checks": {
                        c["letter"]: {"status": c["status"], "values": c["values"]}
                        for c in burst["quality"]["checks"]}},
                })
    entries.sort(key=lambda e: (e["session"], e["ticker"], e["text_sha256"]))
    return {"source": "every schema-2 docs/data.json in the history of the commit named through",
            "through": ref, "refusals": entries}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--ref", default="origin/main")
    args = parser.parse_args(argv)
    current = OUT.read_text(encoding="utf-8") if OUT.exists() else None
    ref = json.loads(current)["through"] if args.check and current else args.ref
    payload = json.dumps(build(ref), indent=1, sort_keys=True) + "\n"
    if args.check:
        print("current" if current == payload else "stale")
        return 0 if current == payload else 1
    OUT.write_text(payload, encoding="utf-8")
    print(f"{len(json.loads(payload)['refusals'])} refusals written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
