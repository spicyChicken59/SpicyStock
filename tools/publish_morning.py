"""Publish one morning observation without changing or racing its source record.

The collector runs with read-only repository permissions. This helper receives
only that run's observation, validates it against the current main record, and
creates a one-file commit. Ordinary fast-forward pushes provide the compare and
swap: every rejected push starts again from main and repeats all validations.
No working-tree reset, rebase, force push, provider call or email is involved.

The same path publishes the bound source recovery (``--target recovery``): one
file, ``docs/source-recovery.json``, validated against the current main record,
the quality ledger's entry for it and the prior receipt.

The same path publishes the dated research observation (``--target research``):
one file, ``docs/research-observations.json``, validated against the current
main record AND the research cohort receipt and bundle committed beside it.
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
RESEARCH_SNAPSHOT_PATH = 'docs/research-observations.json'
RECOVERY_SNAPSHOT_PATH = 'docs/source-recovery.json'
COHORT_RECEIPT_PATH = 'docs/stop-research.json'
RECORD_PATH = 'docs/data.json'
MAX_SNAPSHOT_BYTES = 1024 * 1024
# One snapshot file per target; a commit may change that file and nothing else.
TARGETS = {
    'morning': {'snapshot': SNAPSHOT_PATH, 'message': b'Publish bound morning observation\n'},
    'research': {'snapshot': RESEARCH_SNAPSHOT_PATH, 'message': b'Publish bound research observation\n'},
    'recovery': {'snapshot': RECOVERY_SNAPSHOT_PATH, 'message': b'Publish bound source recovery\n'},
}
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


def research_check(observation: dict, data_raw: bytes, receipt_raw: bytes | None, bundle_raw: bytes | None,
                   previous_raw: bytes | None, now: datetime | None = None) -> str | None:
    """The research observation's race refusals; malformed or rehearsal input raises.

    Beside the record and the prior observation, the cohort receipt committed
    on main is part of the compare and swap: an observation collected over a
    cohort that main has since replaced describes nothing main publishes.
    """
    from src.research_observations import validate_observation

    if observation.get('dry_run') is not False:
        raise ValueError('research_rehearsal_cannot_publish')
    binding = observation.get('publication', {})
    if (not isinstance(binding, dict)
            or binding.get('data_sha256') != hashlib.sha256(data_raw).hexdigest()):
        return 'source_record_changed'
    if 'previous_observation_sha256' not in observation:
        raise ValueError('research_previous_observation_binding_missing')
    previous_hash = hashlib.sha256(previous_raw).hexdigest() if previous_raw is not None else None
    if observation['previous_observation_sha256'] != previous_hash:
        return 'previous_observation_changed'
    cohort = observation.get('cohort')
    receipt_hash = hashlib.sha256(receipt_raw).hexdigest() if receipt_raw is not None else None
    if (cohort.get('receipt_sha256') if isinstance(cohort, dict) else cohort) != receipt_hash:
        return 'research_cohort_changed'
    validate_observation(observation, data_raw, receipt_raw, bundle_raw, previous_raw=previous_raw,
                         require_continuity=True)
    now = now or datetime.now(timezone.utc)
    if instant(observation['generated_at']) > now + timedelta(seconds=MAX_FUTURE_SKEW_SECONDS):
        raise ValueError('research_completion_is_in_future')
    if previous_raw is not None:
        previous = read_snapshot(previous_raw)
        previous_binding = previous.get('publication')
        if not isinstance(previous_binding, dict):
            raise ValueError('existing_research_binding_invalid')
        # The prior observation may have been bound to an older cohort, so only
        # its clocks are read here; its own validation happened when it landed.
        if previous_binding.get('data_sha256') == binding['data_sha256']:
            if (instant(previous['generated_at']) >= instant(observation['generated_at'])
                    or instant(previous['collection_started_at']) >= instant(observation['collection_started_at'])):
                return 'newer_or_equal_observation_exists'
    return None


def recovery_check(observation: dict, data_raw: bytes, ledger_raw: bytes | None, previous_raw: bytes | None,
                   now: datetime | None = None) -> str | None:
    """The source recovery's race refusals; malformed or rehearsal input raises.

    The compare and swap covers the record, the prior receipt AND the quality
    ledger's entry for the record on main: a receipt whose deficits were named
    off an entry main no longer carries (or carries differently) describes
    nothing main publishes. A receipt that spent the publication's one bounded
    request is never replaced; an inapplicable one may be, by a newer one that
    says something else (a later inapplicable receipt for the same publication
    and the same reason is refused as unchanged, so a daily schedule commits at
    most one receipt per publication and reason).
    """
    from src.source_recovery import attempted, validate_receipt

    if observation.get('dry_run') is not False:
        raise ValueError('recovery_rehearsal_cannot_publish')
    binding = observation.get('publication', {})
    if (not isinstance(binding, dict)
            or binding.get('data_sha256') != hashlib.sha256(data_raw).hexdigest()):
        return 'source_record_changed'
    if 'previous_observation_sha256' not in observation:
        raise ValueError('recovery_previous_observation_binding_missing')
    previous_hash = hashlib.sha256(previous_raw).hexdigest() if previous_raw is not None else None
    if observation['previous_observation_sha256'] != previous_hash:
        return 'previous_observation_changed'
    deficits = observation.get('deficits')
    ledger = deficits.get('ledger') if isinstance(deficits, dict) else None
    ledger_hash = hashlib.sha256(ledger_raw).hexdigest() if ledger_raw is not None else None
    if (ledger.get('sha256') if isinstance(ledger, dict) else ledger) != ledger_hash:
        return 'ledger_entry_changed'
    validate_receipt(observation, data_raw, ledger_raw, previous_raw=previous_raw, require_continuity=True)
    now = now or datetime.now(timezone.utc)
    if instant(observation['generated_at']) > now + timedelta(seconds=MAX_FUTURE_SKEW_SECONDS):
        raise ValueError('recovery_completion_is_in_future')
    if previous_raw is not None:
        try:
            previous = json.loads(previous_raw)
        except ValueError:
            previous = None
        previous_binding = previous.get('publication') if isinstance(previous, dict) else None
        # a prior receipt of another publication, of any schema, binds nothing
        # here beyond the bytes' hash the receipt already carries
        if isinstance(previous_binding, dict) and previous_binding.get('data_sha256') == binding['data_sha256']:
            if attempted(previous, binding['data_sha256']):
                return 'recovery_already_published'
            if (instant(previous['generated_at']) >= instant(observation['generated_at'])
                    or instant(previous['collection_started_at']) >= instant(observation['collection_started_at'])):
                return 'newer_or_equal_observation_exists'
            if (observation['status'] == previous.get('status') == 'inapplicable'
                    and observation.get('reason') == previous.get('reason')):
                # the same publication declined for the same reason: nothing to commit
                return 'recovery_unchanged'
    return None


def _ledger_on_main(root: Path, tip: str, observation: dict) -> bytes | None:
    """The quality ledger's entry for the receipt's publication as main carries
    it; None when main has none (or the receipt names no readable publication,
    which recovery_check then refuses as a changed record)."""
    from src import quality_ledger
    from src.source_recovery import HEX
    binding = observation.get('publication')
    digest = binding.get('data_sha256') if isinstance(binding, dict) else None
    if not isinstance(digest, str) or not HEX.fullmatch(digest):
        return None
    return _tip_blob(root, tip, f'docs/{quality_ledger.DIRECTORY}/{digest}.json.gz',
                     quality_ledger.MAX_ENTRY_BYTES, 'quality_ledger_entry')


def _tip_blob(root: Path, tip: str, path: str, maximum: int, label: str) -> bytes | None:
    if not git(root, 'ls-tree', tip, '--', path).stdout:
        return None
    if int(git(root, 'cat-file', '-s', f'{tip}:{path}').stdout) > maximum:
        raise ValueError(f'existing_{label}_too_large')
    return git(root, 'show', f'{tip}:{path}').stdout


def _cohort_on_main(root: Path, tip: str) -> tuple[bytes | None, bytes | None]:
    from src.stop_research import MAX_BUNDLE_BYTES, MAX_RECEIPT_BYTES, parse_receipt
    receipt_raw = _tip_blob(root, tip, COHORT_RECEIPT_PATH, MAX_RECEIPT_BYTES, 'cohort_receipt')
    if receipt_raw is None:
        return None, None
    bundle_path = 'docs/' + parse_receipt(receipt_raw)['bundle']['path']
    bundle_raw = _tip_blob(root, tip, bundle_path, MAX_BUNDLE_BYTES, 'cohort_bundle')
    if bundle_raw is None:
        raise ValueError('cohort_bundle_missing_from_main')
    return receipt_raw, bundle_raw


def publish(root: Path, snapshot_raw: bytes, *, ref: str, run_id: str, target: str = 'morning') -> str:
    if target not in TARGETS:
        raise ValueError('unknown_publication_target')
    snapshot_path, message = TARGETS[target]['snapshot'], TARGETS[target]['message']
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
        previous_raw = _tip_blob(root, tip, snapshot_path, MAX_SNAPSHOT_BYTES, 'morning_snapshot')
        if target == 'morning':
            refusal = publication_check(observation, data_raw, previous_raw)
        elif target == 'recovery':
            refusal = recovery_check(observation, data_raw, _ledger_on_main(root, tip, observation), previous_raw)
        else:
            receipt_raw, bundle_raw = _cohort_on_main(root, tip)
            refusal = research_check(observation, data_raw, receipt_raw, bundle_raw, previous_raw)
        if refusal:
            return refusal
        blob = git(root, 'hash-object', '-w', '--stdin', input=snapshot_raw).stdout.decode().strip()
        with tempfile.TemporaryDirectory(prefix='spicystock-morning-index-') as temporary:
            env = dict(os.environ, GIT_INDEX_FILE=str(Path(temporary) / 'index'),
                       GIT_AUTHOR_NAME='spicystock', GIT_AUTHOR_EMAIL='actions@github.com',
                       GIT_COMMITTER_NAME='spicystock', GIT_COMMITTER_EMAIL='actions@github.com')
            git(root, 'read-tree', tip, env=env)
            git(root, 'update-index', '--add', '--cacheinfo', f'100644,{blob},{snapshot_path}', env=env)
            tree = git(root, 'write-tree', env=env).stdout.decode().strip()
            commit = git(root, 'commit-tree', tree, '-p', tip, input=message, env=env).stdout.decode().strip()
        changed = git(root, 'diff-tree', '--no-commit-id', '--name-only', '-r', commit).stdout.decode().splitlines()
        if changed != [snapshot_path]:
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
    commit.add_argument('--target', choices=sorted(TARGETS), default='morning')
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
            outcome = publish(args.root, snapshot_file(args.snapshot), target=args.target,
                              ref=os.environ.get('GITHUB_REF', ''), run_id=os.environ.get('GITHUB_RUN_ID', ''))
            print(f'{args.target.capitalize()} publication: {outcome}')
        return 0
    except (KeyError, OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
        # Provider/authentication values and arbitrary JSON never enter logs.
        print('::error::Morning publication or guard failed; no raw response was logged.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
