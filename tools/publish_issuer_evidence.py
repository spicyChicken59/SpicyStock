"""Bound SEC evidence publication to current main without changing model history.

Collection is read-only. This writer admits only a validated receipt and its
digest-addressed bundle, using an isolated Git index and ordinary pushes. A
rejected push repeats the source/prior-receipt checks; it never rebases stale
evidence. Raw SEC captures remain separate, expiring Actions artifacts.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import urlencode

from tools.publish_morning import git, instant

RECEIPT_PATH = 'docs/issuer-evidence.json'
RECORD_PATH = 'docs/data.json'
DIRECTORY = 'docs/issuer-evidence'
MANIFEST_PATH = DIRECTORY + '/retention.json'
MAX_RECEIPT_BYTES = 64 * 1024
MAX_BUNDLE_BYTES = 2 * 1024 * 1024
MAX_RECORD_BYTES = 32 * 1024 * 1024
MAX_MANIFEST_BYTES = 64 * 1024
MAX_OBJECTS = 256
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
RETENTION_DAYS = 21
PUSH_ATTEMPTS = 3
FUTURE_SKEW_SECONDS = 5
MAX_DAILY_COLLECTIONS = 3
MAX_HISTORY_RUNS = 500
MAX_RUN_ATTEMPTS = 20
# GitHub limits one workflow run's lifetime (including waiting) to 35 days.
# Read the whole bounded window, not just runs created since today's midnight.
MAX_WORKFLOW_DAYS = 35
PRODUCTION_STEP = 'Collect issuer evidence (production)'
SHA = re.compile(r'[a-f0-9]{64}\Z')
EVENING_NAME = 'Evening scan (6:16 PM ET)'
MORNING_NAME = 'Morning observation (best effort)'


def encode(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def digest(raw: bytes | None) -> str | None:
    return hashlib.sha256(raw).hexdigest() if raw is not None else None


def bounded_file(path: Path, maximum: int) -> bytes:
    if path.is_symlink() or not path.is_file() or any(p.is_symlink() for p in path.parents):
        raise ValueError('issuer_asset_must_be_regular_file')
    with path.open('rb') as handle:
        raw = handle.read(maximum + 1)
    if not raw or len(raw) > maximum:
        raise ValueError('issuer_asset_size_invalid')
    return raw


def tree_file(root: Path, tip: str, path: str, maximum: int, *, optional=False) -> bytes | None:
    entry = git(root, 'ls-tree', tip, '--', path).stdout.decode().splitlines()
    if not entry and optional:
        return None
    if len(entry) != 1:
        raise ValueError('issuer_git_asset_missing')
    metadata, actual = entry[0].split('\t', 1)
    mode, kind, blob = metadata.split()
    if actual != path or mode != '100644' or kind != 'blob':
        raise ValueError('issuer_git_asset_must_be_regular_file')
    size = int(git(root, 'cat-file', '-s', blob).stdout)
    if not 0 < size <= maximum:
        raise ValueError('issuer_git_asset_size_invalid')
    return git(root, 'cat-file', 'blob', blob).stdout


def read_candidate(directory: Path) -> tuple[bytes, bytes]:
    from src.issuer_evidence import parse_receipt, validate_bundle
    receipt_raw = bounded_file(directory / 'issuer-evidence.json', MAX_RECEIPT_BYTES)
    receipt = parse_receipt(receipt_raw)
    bundle_raw = bounded_file(directory / receipt['bundle']['path'], MAX_BUNDLE_BYTES)
    validate_bundle(receipt_raw, bundle_raw)
    return receipt_raw, bundle_raw


def publication_check(canonical_raw: bytes, receipt_raw: bytes, bundle_raw: bytes,
                      previous_raw: bytes | None, *, now: datetime) -> str | None:
    from src.issuer_evidence import parse_receipt, validate_for_publication
    receipt = parse_receipt(receipt_raw)
    if receipt['dry_run'] is not False:
        raise ValueError('issuer_rehearsal_cannot_publish')
    if receipt['publication']['data_sha256'] != digest(canonical_raw):
        return 'source_record_changed'
    if receipt['previous_receipt_sha256'] != digest(previous_raw):
        return 'previous_receipt_changed'
    validate_for_publication(canonical_raw, receipt_raw, bundle_raw)
    latest = now + timedelta(seconds=FUTURE_SKEW_SECONDS)
    if any(instant(receipt[field]) > latest for field in ('collection_started_at', 'generated_at')):
        raise ValueError('issuer_collection_is_in_future')
    if previous_raw is not None:
        previous = parse_receipt(previous_raw)
        if any(instant(previous[field]) >= instant(receipt[field])
               for field in ('collection_started_at', 'generated_at')):
            return 'newer_or_equal_receipt_exists'
    return None


def retention_plan(root: Path, tip: str, receipt: dict, bundle_raw: bytes,
                   previous: dict | None, *, now: datetime) -> tuple[bytes, list[str]]:
    """Delete only manifest-owned expired hashes; a new current hash is protected."""
    raw = tree_file(root, tip, MANIFEST_PATH, MAX_MANIFEST_BYTES, optional=True)
    manifest = json.loads(raw) if raw is not None else {'schema_version': 1, 'objects': {}}
    if (not isinstance(manifest, dict) or set(manifest) != {'schema_version', 'objects'}
            or type(manifest['schema_version']) is not int or manifest['schema_version'] != 1
            or not isinstance(manifest['objects'], dict) or len(manifest['objects']) > MAX_OBJECTS):
        raise ValueError('issuer_retention_manifest_invalid')
    objects = manifest['objects']
    current = receipt['bundle']['sha256']
    prior = previous['bundle']['sha256'] if previous is not None else None
    stamp = now.astimezone(timezone.utc).isoformat()
    for sha, item in objects.items():
        if (not isinstance(sha, str) or not SHA.fullmatch(sha) or not isinstance(item, dict)
                or set(item) != {'bytes', 'first_seen_at', 'superseded_at'}
                or type(item['bytes']) is not int or not 0 < item['bytes'] <= MAX_BUNDLE_BYTES):
            raise ValueError('issuer_retention_object_invalid')
        first = instant(item['first_seen_at'])
        ended = instant(item['superseded_at']) if item['superseded_at'] is not None else None
        if (first > now or (ended is not None and not first <= ended <= now)
                or (ended is None and sha != prior)):
            raise ValueError('issuer_retention_clock_invalid')
        old = tree_file(root, tip, f'{DIRECTORY}/{sha}.json', MAX_BUNDLE_BYTES)
        if digest(old) != sha or len(old) != item['bytes']:
            raise ValueError('issuer_retained_object_changed')
    # An existing valid fixed receipt can establish ownership of its own
    # referenced bundle during migration; no unrelated object is adopted.
    if prior and prior not in objects:
        objects[prior] = {'bytes': previous['bundle']['bytes'], 'first_seen_at': stamp, 'superseded_at': None}
    for sha, item in objects.items():
        if sha != current and item['superseded_at'] is None:
            item['superseded_at'] = stamp
    if current in objects:
        if objects[current]['bytes'] != len(bundle_raw):
            raise ValueError('issuer_current_object_changed')
        objects[current]['superseded_at'] = None
    else:
        objects[current] = {'bytes': len(bundle_raw), 'first_seen_at': stamp, 'superseded_at': None}
    expired = [sha for sha, item in objects.items() if sha != current
               and item['superseded_at'] is not None
               and now - instant(item['superseded_at']) > timedelta(days=RETENTION_DAYS)]
    deleted = [f'{DIRECTORY}/{sha}.json' for sha in expired]
    for sha in expired:
        del objects[sha]
    # Unknown files are preserved and count against capacity, so a populated
    # unowned directory cannot silently evade the archival bound.
    retained_sizes = {}
    for line in git(root, 'ls-tree', '-r', '--long', tip, '--', DIRECTORY).stdout.decode().splitlines():
        metadata, path = line.split('\t', 1)
        mode, kind, _, size = metadata.split()
        if path == MANIFEST_PATH or path in deleted:
            continue
        if mode != '100644' or kind != 'blob':
            raise ValueError('issuer_archive_asset_must_be_regular_file')
        retained_sizes[path] = int(size)
    retained_sizes[f'{DIRECTORY}/{current}.json'] = len(bundle_raw)
    if len(retained_sizes) > MAX_OBJECTS or sum(retained_sizes.values()) > MAX_ARCHIVE_BYTES:
        raise ValueError('issuer_retention_capacity_exceeded')
    encoded = encode(manifest)
    if len(encoded) > MAX_MANIFEST_BYTES:
        raise ValueError('issuer_retention_manifest_too_large')
    return encoded, deleted


def publish(root: Path, receipt_raw: bytes, bundle_raw: bytes, *, ref: str,
            run_id: str, now: datetime | None = None) -> str:
    from src.issuer_evidence import parse_receipt, validate_bundle
    if ref != 'refs/heads/main':
        raise ValueError('issuer_publication_requires_main')
    receipt = parse_receipt(receipt_raw)
    validate_bundle(receipt_raw, bundle_raw)
    if receipt['dry_run'] is not False:
        raise ValueError('issuer_rehearsal_cannot_publish')
    if not run_id or receipt['collection_run_id'] != run_id:
        raise ValueError('issuer_collection_run_mismatch')
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('issuer_publication_clock_missing_offset')
    bundle_path = 'docs/' + receipt['bundle']['path']
    for _ in range(PUSH_ATTEMPTS):
        git(root, 'fetch', '--no-tags', 'origin', '+refs/heads/main:refs/remotes/origin/main')
        tip = git(root, 'rev-parse', 'refs/remotes/origin/main').stdout.decode().strip()
        canonical_raw = tree_file(root, tip, RECORD_PATH, MAX_RECORD_BYTES)
        previous_raw = tree_file(root, tip, RECEIPT_PATH, MAX_RECEIPT_BYTES, optional=True)
        refusal = publication_check(canonical_raw, receipt_raw, bundle_raw, previous_raw, now=now)
        if refusal:
            return refusal
        previous = parse_receipt(previous_raw) if previous_raw is not None else None
        if previous is not None:
            old_bundle = tree_file(root, tip, 'docs/' + previous['bundle']['path'], MAX_BUNDLE_BYTES)
            validate_bundle(previous_raw, old_bundle)
        existing = tree_file(root, tip, bundle_path, MAX_BUNDLE_BYTES, optional=True)
        if existing is not None and existing != bundle_raw:
            raise ValueError('issuer_immutable_bundle_changed')
        manifest_raw, deleted = retention_plan(root, tip, receipt, bundle_raw, previous, now=now)
        writes = {bundle_path: bundle_raw, MANIFEST_PATH: manifest_raw, RECEIPT_PATH: receipt_raw}
        with tempfile.TemporaryDirectory(prefix='spicystock-issuer-index-') as temporary:
            env = dict(os.environ, GIT_INDEX_FILE=str(Path(temporary) / 'index'),
                       GIT_AUTHOR_NAME='spicystock', GIT_AUTHOR_EMAIL='actions@github.com',
                       GIT_COMMITTER_NAME='spicystock', GIT_COMMITTER_EMAIL='actions@github.com')
            git(root, 'read-tree', tip, env=env)
            for path, raw in writes.items():
                blob = git(root, 'hash-object', '-w', '--stdin', input=raw).stdout.decode().strip()
                git(root, 'update-index', '--add', '--cacheinfo', f'100644,{blob},{path}', env=env)
            for path in deleted:
                git(root, 'update-index', '--force-remove', '--', path, env=env)
            tree = git(root, 'write-tree', env=env).stdout.decode().strip()
            commit = git(root, 'commit-tree', tree, '-p', tip,
                         input=b'Publish bound issuer evidence\n', env=env).stdout.decode().strip()
        changed = set(git(root, 'diff-tree', '--no-commit-id', '--name-only', '-r', commit).stdout.decode().splitlines())
        if RECEIPT_PATH not in changed or not changed <= set(writes) | set(deleted):
            raise RuntimeError('issuer_commit_paths_invalid')
        if git(root, 'push', 'origin', f'{commit}:refs/heads/main', check=False).returncode == 0:
            return 'published'
    raise RuntimeError('issuer_publication_race_retry_exhausted')


def api(repository: str, endpoint: str) -> dict:
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('issuer_repository_invalid')
    result = subprocess.run(['gh', 'api', '--method', 'GET', f'repos/{repository}/{endpoint}'],
                            capture_output=True, timeout=30)
    if result.returncode or len(result.stdout) > 8 * 1024 * 1024:
        raise RuntimeError('issuer_actions_metadata_unavailable')
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise ValueError('issuer_actions_metadata_invalid')
    return value


def daily_collections(repository: str, now: datetime, *, fetch=api) -> int:
    """Count started production steps, including failures and rerun attempts.

    The workflow serializes the entire guard/collect/persist sequence. An
    in-progress collection consumes a slot; a skipped/inactive parent does not.
    Any incomplete metadata, pagination or attempt history refuses collection.
    """
    start = now.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    runs, total = {}, None
    for page in range(1, MAX_HISTORY_RUNS // 100 + 1):
        query = urlencode({'branch': 'main', 'created': '>=' + (start - timedelta(days=MAX_WORKFLOW_DAYS)).isoformat(),
                           'per_page': 100, 'page': page})
        response = fetch(repository, 'actions/workflows/issuer-evidence.yml/runs?' + query)
        expected = response.get('total_count')
        rows = response.get('workflow_runs')
        if (type(expected) is not int or not 0 <= expected <= MAX_HISTORY_RUNS
                or not isinstance(rows, list) or (total is not None and expected != total)):
            raise ValueError('issuer_actions_history_incomplete')
        total = expected
        for row in rows:
            if not isinstance(row, dict) or type(row.get('id')) is not int or row['id'] in runs:
                raise ValueError('issuer_actions_history_invalid')
            runs[row['id']] = row
        if len(runs) == total:
            break
        if len(rows) != 100 or len(runs) > total:
            raise ValueError('issuer_actions_history_incomplete')
    if len(runs) != total:
        raise ValueError('issuer_actions_history_incomplete')
    count = 0
    for run in runs.values():
        if run.get('head_branch') != 'main':
            raise ValueError('issuer_actions_branch_history_incomplete')
        if not isinstance(run.get('updated_at'), str):
            raise ValueError('issuer_actions_clock_history_incomplete')
        if instant(run['updated_at']) < start:
            continue
        attempts = run.get('run_attempt')
        if type(attempts) is not int or not 1 <= attempts <= MAX_RUN_ATTEMPTS:
            raise ValueError('issuer_actions_attempt_history_incomplete')
        for attempt in range(1, attempts + 1):
            response = fetch(repository, f"actions/runs/{run['id']}/attempts/{attempt}/jobs?per_page=100")
            jobs = response.get('jobs')
            if (not isinstance(jobs, list) or type(response.get('total_count')) is not int
                    or len(jobs) != response['total_count'] or len(jobs) > 100):
                raise ValueError('issuer_actions_job_history_incomplete')
            for job in jobs:
                steps = job.get('steps') if isinstance(job, dict) else None
                if not isinstance(steps, list):
                    raise ValueError('issuer_actions_step_history_incomplete')
                for step in steps:
                    if not isinstance(step, dict) or not isinstance(step.get('name'), str):
                        raise ValueError('issuer_actions_step_history_invalid')
                    if step.get('name') != PRODUCTION_STEP or step.get('conclusion') == 'skipped':
                        continue
                    if step.get('status') not in {'queued', 'pending', 'in_progress', 'completed'}:
                        raise ValueError('issuer_actions_step_history_invalid')
                    if step.get('status') in {'in_progress', 'completed'}:
                        if not isinstance(step.get('started_at'), str) or not step['started_at']:
                            raise ValueError('issuer_actions_start_history_incomplete')
                        began = instant(step['started_at'])
                        if began > now + timedelta(seconds=FUTURE_SKEW_SECONDS):
                            raise ValueError('issuer_actions_start_is_in_future')
                        if start <= began < end:
                            count += 1
    return count


def collection_guard(canonical_raw: bytes, morning_raw: bytes | None, event: dict, *,
                     event_name: str, ref: str, repository: str, now: datetime,
                     fetch=api) -> tuple[bool, str]:
    inputs = event.get('inputs') or {}
    dry = inputs.get('dry_run') in (True, 'true')
    if event_name == 'workflow_dispatch' and dry:
        return True, 'manual_rehearsal'
    if ref != 'refs/heads/main':
        return False, 'publication_requires_main'
    if event_name == 'workflow_run':
        parent = event.get('workflow_run') or {}
        if ((parent.get('head_repository') or {}).get('full_name') != repository
                or parent.get('head_branch') != 'main' or parent.get('status') != 'completed'
                or type(parent.get('id')) is not int or parent['id'] < 1):
            return False, 'untrusted_parent'
        if parent.get('name') == EVENING_NAME:
            if parent.get('conclusion') != 'success':
                return False, 'evening_not_successful'
            if str(json.loads(canonical_raw)['run'].get('run_id')) != str(parent.get('id')):
                return False, 'evening_did_not_publish_current_record'
        elif parent.get('name') == MORNING_NAME:
            if morning_raw is None or str(json.loads(morning_raw).get('observation_run_id')) != str(parent.get('id')):
                return False, 'morning_did_not_publish_current_observation'
            if json.loads(morning_raw).get('publication', {}).get('data_sha256') != digest(canonical_raw):
                return False, 'morning_source_record_changed'
        else:
            return False, 'unknown_parent'
    elif event_name != 'workflow_dispatch' or inputs.get('dry_run') not in (False, 'false'):
        return False, 'unknown_trigger'
    if daily_collections(repository, now, fetch=fetch) >= MAX_DAILY_COLLECTIONS:
        return False, 'daily_collection_limit'
    return True, 'production_collection'


def cache_saveable(path: Path) -> bool:
    """A rejected cache does not fail collection and is never saved again."""
    from src.issuer_evidence import validate_cache
    try:
        state = validate_cache(path, prune=True)
        return state['entries'] > 0
    except (KeyError, OSError, TypeError, ValueError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    guard = commands.add_parser('guard')
    guard.add_argument('--docs', type=Path, default=Path('docs'))
    cache = commands.add_parser('cache-check')
    cache.add_argument('--path', type=Path, required=True)
    commit = commands.add_parser('publish')
    commit.add_argument('--input', type=Path, required=True)
    commit.add_argument('--root', type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        if args.command == 'guard':
            event = json.loads(bounded_file(Path(os.environ['GITHUB_EVENT_PATH']), 1024 * 1024))
            morning_path = args.docs / 'morning.json'
            go, reason = collection_guard(bounded_file(args.docs / 'data.json', MAX_RECORD_BYTES),
                bounded_file(morning_path, 1024 * 1024) if morning_path.exists() else None, event,
                event_name=os.environ['GITHUB_EVENT_NAME'], ref=os.environ['GITHUB_REF'],
                repository=os.environ['GITHUB_REPOSITORY'], now=datetime.now(timezone.utc))
            print(f'Issuer evidence guard: {reason}')
            with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
                output.write(f'go={str(go).lower()}\n')
        elif args.command == 'cache-check':
            valid = cache_saveable(args.path)
            with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
                output.write(f'valid={str(valid).lower()}\n')
            print('Issuer source cache: eligible for bounded reuse.' if valid else 'Issuer source cache: not saved.')
        else:
            receipt, bundle = read_candidate(args.input)
            result = publish(args.root, receipt, bundle, ref=os.environ.get('GITHUB_REF', ''),
                             run_id=os.environ.get('GITHUB_RUN_ID', ''))
            print(f'Issuer evidence publication: {result}')
        return 0
    except (KeyError, TypeError, OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
        print('::error::Issuer evidence guard or publication failed; no raw response was logged.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
