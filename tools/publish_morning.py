"""Publish one morning observation without changing or racing its source record.

The collector runs with read-only repository permissions. This helper receives
only that run's observation, validates it against the current main record, and
creates a one-file commit. Ordinary fast-forward pushes provide the compare and
swap: every rejected push starts again from main and repeats all validations.
No working-tree reset, rebase, force push, provider call or email is involved.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from src import sessions

SNAPSHOT_PATH = 'docs/morning.json'
RECORD_PATH = 'docs/data.json'
MAX_SNAPSHOT_BYTES = 1024 * 1024
PUSH_ATTEMPTS = 3
MAX_FUTURE_SKEW_SECONDS = 5
SCHEDULES = {
    '20 13 * * 1-5': (13, 20, '-0400'),
    '28 13 * * 1-5': (13, 28, '-0400'),
    '20 14 * * 1-5': (14, 20, '-0500'),
    '28 14 * * 1-5': (14, 28, '-0500'),
}


def instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError('observation_clock_missing_offset')
    return parsed


def schedule_guard(data_raw: bytes, event: str, cron: str,
                   now: datetime | None = None) -> tuple[bool, str]:
    """A late cron cannot silently become a different day's morning check.

    A manual check always reaches the collector: it can produce an honest
    inapplicable receipt after the cutoff without making provider requests.
    """
    if event == 'workflow_dispatch':
        return True, 'manual_dispatch'
    if event != 'schedule' or cron not in SCHEDULES:
        return False, 'unknown_schedule'
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('schedule_clock_missing_offset')
    now = now.astimezone(timezone.utc)
    hour, minute, offset = SCHEDULES[cron]
    nominal = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if nominal > now:
        nominal -= timedelta(days=1)
    intended = nominal.astimezone(sessions.MARKET_TZ)
    target = intended.date()
    if nominal.weekday() >= 5 or intended.strftime('%z') != offset:
        return False, 'inactive_schedule'
    if now.astimezone(sessions.MARKET_TZ).date() != target:
        return False, 'scheduled_day_expired'
    if not sessions.is_session(target):
        return False, 'not_exchange_session'
    try:
        from src.morning import bind_record
        binding = bind_record(data_raw)
        if binding['applicable_session'] != str(target):
            return False, 'record_for_another_session'
        data = json.loads(data_raw)
        if now >= instant(data['run']['timing']['cutoff_at']):
            return False, 'entry_window_ended'
    except (KeyError, TypeError, ValueError):
        return False, 'invalid_publication'
    return True, 'scheduled_morning'


def git(root: Path, *args: str, input: bytes | None = None,
        env: dict | None = None, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(['git', '-C', str(root), *args], input=input,
                            capture_output=True, timeout=60, env=env)
    if check and result.returncode:
        # Raw transport responses can contain authentication material.
        raise RuntimeError('morning_git_operation_failed')
    return result


def read_snapshot(raw: bytes) -> dict:
    if not raw or len(raw) > MAX_SNAPSHOT_BYTES:
        raise ValueError('morning_snapshot_size_invalid')
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError('morning_snapshot_shape_invalid')
    return value


def snapshot_file(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError('morning_snapshot_must_be_regular_file')
    with path.open('rb') as handle:
        raw = handle.read(MAX_SNAPSHOT_BYTES + 1)
    read_snapshot(raw)
    return raw


def publication_check(observation: dict, data_raw: bytes,
                      previous_raw: bytes | None, now: datetime | None = None) -> str | None:
    """Return a normal race refusal; malformed or rehearsal input raises."""
    from src.morning import validate_observation

    if observation.get('dry_run') is not False:
        raise ValueError('morning_rehearsal_cannot_publish')
    binding = observation.get('publication', {})
    if (not isinstance(binding, dict)
            or binding.get('data_sha256') != hashlib.sha256(data_raw).hexdigest()):
        return 'source_record_changed'
    if 'previous_observation_sha256' not in observation:
        raise ValueError('morning_previous_observation_binding_missing')
    previous_hash = hashlib.sha256(previous_raw).hexdigest() if previous_raw is not None else None
    if observation['previous_observation_sha256'] != previous_hash:
        return 'previous_observation_changed'
    validate_observation(observation, data_raw, previous_raw=previous_raw, require_continuity=True)
    now = now or datetime.now(timezone.utc)
    if instant(observation['generated_at']) > now + timedelta(seconds=MAX_FUTURE_SKEW_SECONDS):
        raise ValueError('morning_completion_is_in_future')
    if observation.get('status') == 'invalid_publication':
        raise ValueError('invalid_publication_cannot_publish')
    if previous_raw is not None:
        previous = read_snapshot(previous_raw)
        previous_binding = previous.get('publication')
        if not isinstance(previous_binding, dict):
            raise ValueError('existing_morning_binding_invalid')
        # A previous record's receipt is naturally superseded by the first
        # check over the current record. For the same record, collection
        # completion is monotonic; provider event times remain separate.
        if previous_binding.get('data_sha256') == binding['data_sha256']:
            validate_observation(previous, data_raw)
            if (instant(previous['generated_at']) >= instant(observation['generated_at'])
                    or instant(previous['collection_started_at']) >= instant(observation['collection_started_at'])):
                return 'newer_or_equal_observation_exists'
    return None


def publish(root: Path, snapshot_raw: bytes, *, ref: str, run_id: str) -> str:
    if ref != 'refs/heads/main':
        raise ValueError('morning_publication_requires_main')
    observation = read_snapshot(snapshot_raw)
    if observation.get('dry_run') is not False:
        raise ValueError('morning_rehearsal_cannot_publish')
    if not run_id or observation.get('observation_run_id') != run_id:
        raise ValueError('morning_observation_run_mismatch')
    for _ in range(PUSH_ATTEMPTS):
        git(root, 'fetch', '--no-tags', 'origin',
            '+refs/heads/main:refs/remotes/origin/main')
        tip = git(root, 'rev-parse', 'refs/remotes/origin/main').stdout.decode().strip()
        data_raw = git(root, 'show', f'{tip}:{RECORD_PATH}').stdout
        prior = git(root, 'ls-tree', tip, '--', SNAPSHOT_PATH).stdout
        if prior and int(git(root, 'cat-file', '-s', f'{tip}:{SNAPSHOT_PATH}').stdout) > MAX_SNAPSHOT_BYTES:
            raise ValueError('existing_morning_snapshot_too_large')
        previous_raw = git(root, 'show', f'{tip}:{SNAPSHOT_PATH}').stdout if prior else None
        refusal = publication_check(observation, data_raw, previous_raw)
        if refusal:
            return refusal
        blob = git(root, 'hash-object', '-w', '--stdin', input=snapshot_raw).stdout.decode().strip()
        with tempfile.TemporaryDirectory(prefix='spicystock-morning-index-') as temporary:
            env = dict(os.environ, GIT_INDEX_FILE=str(Path(temporary) / 'index'),
                       GIT_AUTHOR_NAME='spicystock', GIT_AUTHOR_EMAIL='actions@github.com',
                       GIT_COMMITTER_NAME='spicystock', GIT_COMMITTER_EMAIL='actions@github.com')
            git(root, 'read-tree', tip, env=env)
            git(root, 'update-index', '--add', '--cacheinfo', f'100644,{blob},{SNAPSHOT_PATH}', env=env)
            tree = git(root, 'write-tree', env=env).stdout.decode().strip()
            commit = git(root, 'commit-tree', tree, '-p', tip,
                         input=b'Publish bound morning observation\n', env=env).stdout.decode().strip()
        changed = git(root, 'diff-tree', '--no-commit-id', '--name-only', '-r', commit).stdout.decode().splitlines()
        if changed != [SNAPSHOT_PATH]:
            raise RuntimeError('morning_commit_must_change_only_observation')
        if git(root, 'push', 'origin', f'{commit}:refs/heads/main', check=False).returncode == 0:
            return 'published'
    raise RuntimeError('morning_publication_race_retry_exhausted')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    guard = commands.add_parser('guard')
    guard.add_argument('--record', type=Path, default=Path(RECORD_PATH))
    commit = commands.add_parser('publish')
    commit.add_argument('--snapshot', type=Path, required=True)
    commit.add_argument('--root', type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        if args.command == 'guard':
            raw = args.record.read_bytes() if args.record.is_file() else b''
            go, reason = schedule_guard(raw, os.environ.get('GITHUB_EVENT_NAME', ''),
                                        os.environ.get('MORNING_EVENT_SCHEDULE', ''))
            print(f'Morning guard: {reason}')
            with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
                output.write(f'go={str(go).lower()}\n')
        else:
            outcome = publish(args.root, snapshot_file(args.snapshot),
                              ref=os.environ.get('GITHUB_REF', ''), run_id=os.environ.get('GITHUB_RUN_ID', ''))
            print(f'Morning publication: {outcome}')
        return 0
    except (KeyError, OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
        # Provider/authentication values and arbitrary JSON never enter logs.
        print('::error::Morning publication or guard failed; no raw response was logged.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
