"""Compact immutable publication facts, separate from decisions and recovery.

No backfill, regrading, provider calls, user execution or raw bar copies. Failure
is observable on RunReport and in the log; it cannot change the public record.
"""
from __future__ import annotations

from copy import deepcopy
import gzip
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import subprocess
import tempfile

from src import input_diagnostics, record, universe

VERSION = 1
DIRECTORY = 'quality-ledger/v1'
MAX_ENTRY_BYTES = 8 * 1024 * 1024
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_ENTRIES = 4096
log = logging.getLogger(__name__)


def project(value, keys):
    """Absent fields stay null, including legacy grade, basis and counts."""
    return {key: deepcopy((value or {}).get(key)) for key in keys}


def candidate(row, trades):
    q = row.get('quality')
    checks = None if q is None else {
        c['letter']: project(c, ('status', 'a_plus', 'values')) for c in q.get('checks', [])}
    p = row.get('plan')
    return {
        **project(row, ('ticker', 'scan', 'grade_mechanical', 'grade', 'score', 'vetoes', 'reclass')),
        'assessment': None if q is None else project(q, ('score', 'grade', 'vetoes', 'unreadable',
                                                        'a_plus_count', 'passes', 'of', 'notes')),
        'checks': checks, 'reader': deepcopy(row.get('claude')),
        'plan_present': p is not None,
        'plan': None if p is None else project(p, ('eligible', 'action', 'reason', 'exit_schedule')),
        'published_ticket': row['ticker'] in trades,
        'evidence_id': (row.get('evidence') or {}).get('id'),
        'gate': deepcopy((row.get('evidence') or {}).get('gate')),
    }


def build(data, publication_sha256, outcome_rows, *, exceptions=None, revision=None):
    """Pure projection of facts already measured under this publication's rules."""
    run = data['run']
    return {
        'schema_version': VERSION,
        'publication': {**project(run, ('session', 'expected_session', 'session_state', 'published_at',
                                        'run_id', 'type', 'status', 'problems', 'dry_run', 'email', 'timing', 'model')),
                        'sha256': publication_sha256, 'execution_revision': revision,
                        'rules_version': data.get('app', {}).get('rules_version')},
        'rules': deepcopy(data.get('rules')),
        'input': {'universe': deepcopy(run.get('universe')), 'basis': deepcopy(run.get('input_basis')),
                  'coverage': deepcopy(run.get('coverage')),
                  'exception_membership': deepcopy(exceptions)},
        'signal': {'reads': deepcopy(run.get('reads')), 'final_grade_counts': deepcopy(run.get('graded')),
                   'regime': deepcopy(data.get('breadth', {}).get('regime')),
                   'candidates': [candidate(row, data['trades']) for row in data['bursts']],
                   'anticipation': [{**project(row, ('ticker',)),
                                     'evidence_id': (row.get('evidence') or {}).get('id'),
                                     'gate': deepcopy((row.get('evidence') or {}).get('gate'))}
                                    for row in data.get('watchlist', {}).get('top', [])]},
        'outcome': {'summary': deepcopy(data.get('scorecard')), 'rows': deepcopy(outcome_rows)},
    }


def encoded(entry):
    return (json.dumps(entry, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                       allow_nan=False) + '\n').encode('utf-8')


def append(entry, docs):
    """Write once per original publication hash; refuse conflicts and capacity.

    Existing entries are never migrated, pruned or overwritten. A bound failure
    requires an explicit future retention decision, not silent history deletion.
    """
    raw = encoded(entry)
    if entry.get('schema_version') != VERSION:
        raise ValueError('unsupported quality ledger schema')
    if len(raw) > MAX_ENTRY_BYTES:
        raise ValueError('quality ledger entry capacity exceeded')
    # Canonical JSON inside a deterministic gzip container. GzipFile uses a
    # neutral OS header; no local filename, clock or platform enters the bytes.
    buffer = io.BytesIO()
    with gzip.GzipFile(filename='', mode='wb', fileobj=buffer, mtime=0) as handle:
        handle.write(raw)
    raw = buffer.getvalue()
    source = entry['publication']['sha256']
    if len(source) != 64 or any(c not in '0123456789abcdef' for c in source):
        raise ValueError('invalid publication identity')
    directory = Path(docs) / DIRECTORY
    path = directory / (source + '.json.gz')
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError('existing quality ledger entry differs; preserved')
        return path
    files = list(directory.glob('*.json.gz'))
    if len(files) >= MAX_ENTRIES or sum(p.stat().st_size for p in files) + len(raw) > MAX_ARCHIVE_BYTES:
        raise ValueError('quality ledger archive capacity exceeded')
    directory.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(raw)
            handle.flush()
        # Atomic creation without overwriting another writer's existing entry.
        # Close the staging handle first, including on Windows.
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != raw:
                raise ValueError('existing quality ledger entry differs; preserved')
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path


def execution_revision():
    try:
        result = subprocess.run(['git', 'rev-parse', '--verify', 'HEAD'],
            cwd=Path(__file__).resolve().parent.parent, capture_output=True, text=True, timeout=5, check=True)
        value = result.stdout.strip()
        return value if len(value) == 40 and all(c in '0123456789abcdef' for c in value) else None
    except (OSError, subprocess.SubprocessError):
        return None


def capture(*, docs, rec, frames, stats):
    """After the final public write; isolated from grading, delivery and status.

    Only already-published real runs are eligible. A process interrupted before
    this call can leave a publication without an entry; no completeness is
    inferred from the ledger alone. Explicit status exposes capture failures.
    """
    try:
        raw = (Path(docs) / 'data.json').read_bytes()
        data = json.loads(raw)
        if data.get('fixture') or data['run'].get('dry_run'):
            return {'status': 'not_applicable', 'path': None}
        exceptions = None
        if stats is not None:
            exceptions = {key: sorted(set(getattr(stats, attr)))
                          for key, attr in input_diagnostics.REASONS.items()}
            for key, names in exceptions.items():
                if universe.population(names) != data['run']['coverage']['reasons'][key]:
                    raise ValueError('quality ledger exception membership mismatch')
        rows = record.scorecard_rows(rec, frames, data['run']['session'])
        summary = record.summarize_scorecard(rows)
        if summary != {k: data['scorecard'][k] for k in summary}:
            raise ValueError('quality ledger outcomes disagree with published scorecard')
        entry = build(data, hashlib.sha256(raw).hexdigest(), rows,
                      exceptions=exceptions, revision=execution_revision())
        path = append(entry, docs)
        log.info('Quality ledger retained: %s', path)
        return {'status': 'retained', 'path': str(path)}
    except Exception:
        log.error('quality_ledger_capture_failed; publication unchanged; evidence unavailable')
        return {'status': 'failed', 'path': None, 'failure': 'quality_ledger_capture_failed'}
