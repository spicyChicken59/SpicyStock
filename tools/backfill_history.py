#!/usr/bin/env python3
"""Recover published v2 originals from Git, without scanning the market."""
from pathlib import Path
import argparse
import json
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import history


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('docs/history'))
    args = parser.parse_args()
    commits = subprocess.check_output(['git', 'log', '--format=%H', '--', 'docs/data.json'], text=True).splitlines()
    candidates, seen = [], set()
    for commit in commits:
        raw = subprocess.check_output(['git', 'show', commit + ':docs/data.json'])
        blob = history.git_blob(raw)
        if blob in seen:
            continue
        seen.add(blob)
        record = json.loads(raw)
        if record.get('fixture') or (record.get('app') if isinstance(record.get('app'), dict) else {}).get('version') != '2.0':
            continue
        candidates.append((record['run']['session'], commit, raw, record))
    newest = max(x[0] for x in candidates)
    cutoff = (history.date.fromisoformat(newest) - history.timedelta(days=history.DAYS)).isoformat()
    audit = []
    for day, commit, raw, record in sorted(candidates, key=lambda x: (x[0], x[3]['run'].get('published_at', ''))):
        if day < cutoff:
            continue
        history.publish(raw, args.output, source_commit=commit)
        audit.append({'session': day, 'commit': commit, 'blob': history.git_blob(raw),
                      'cases': {r['ticker']: {'grade': r.get('grade'), 'bars': len(r.get('series', []))}
                                for r in record.get('bursts', []) if r['ticker'] in ['ATEC', 'VICR']}})
    print(json.dumps(audit, indent=2))

if __name__ == '__main__':
    main()
