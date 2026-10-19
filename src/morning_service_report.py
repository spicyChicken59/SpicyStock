"""Read-only, as-of operational evidence; local commits are not public arrival.

This report reads retained writer facts. It does not contact any source, rerun
strategy, establish a trading result, or infer scheduler uptime from silence.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import json
import math
from pathlib import Path
import re
import sqlite3
from zoneinfo import ZoneInfo

from src import morning, sessions

VERSION = 1
MAX_RANGE_DAYS = 62
MAX_READ_BYTES = 256 * 1024 * 1024
MAX_REPORT_BYTES = 8 * 1024 * 1024
CHICAGO = ZoneInfo('America/Chicago')
FEEDS = ('iex', 'delayed_sip', 'nasdaq')
QUOTE_STATES = {'recent', 'stale', 'missing', 'invalid', 'unavailable'}


def utcnow():
    return datetime.now(timezone.utc)


def _require(condition):
    if not condition:
        raise ValueError('report_journal_evidence_invalid')


def _instant(value):
    at = morning._instant(value)
    if at is None:
        raise ValueError('report_offset_clock_required')
    return at.astimezone(timezone.utc)


def _iso(value):
    return _instant(value).isoformat() if value is not None else None


def _day(value):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('report_date_invalid')
    return date.fromisoformat(value)


def _bounds(start, end, as_of):
    first, last, at = _day(start), _day(end), _instant(as_of)
    if not 0 <= (last - first).days < MAX_RANGE_DAYS:
        raise ValueError('report_range_outside_bounds')
    if not sessions.SUPPORTED_START <= first <= last <= sessions.SUPPORTED_END:
        raise ValueError('report_calendar_range_unsupported')
    return first, last, at


def _integer(value, minimum=0):
    return type(value) is int and value >= minimum


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _json_blob(snapshot, digest, kind):
    blob = snapshot['blobs'][digest]
    _require(blob['kind'] == kind)
    value = json.loads(blob['raw'])
    _require(isinstance(value, dict))
    return value


def _metadata(meta, at):
    _require(meta['version'] == 1 and meta['mode'] == 'prepared')
    _require(type(meta['migrated']) is int and meta['migrated'] in (0, 1))
    _require(_integer(meta['pruned_events']))
    started = _instant(meta['started_at']) if meta['started_at'] is not None else None
    last = _instant(meta['last_at']) if meta['last_at'] is not None else None
    pruned = _instant(meta['pruned_through_at']) if meta['pruned_through_at'] is not None else None
    _require((started is None) == (last is None))
    _require(started is None or started <= last)
    _require((meta['pruned_events'] == 0) == (pruned is None))
    _require(pruned is None or started is not None and started <= pruned <= last)
    _require(meta['pruned_through_id'] is None if pruned is None else _integer(meta['pruned_through_id'], 1))
    # The report's as-of boundary applies to metadata as well as event payloads.
    # A later retention pass can remove older evidence; disclose that gap without
    # exposing a later event's time or claiming the missing history was observed.
    return {
        'version': meta['version'],
        'mode': 'prepared',
        'capture_started_at': _iso(started) if started is not None and started <= at else None,
        'capture_state': 'not_started_as_of' if started is None or started > at else 'started',
        'migration_without_backfill': bool(meta['migrated']),
        'retention_days': meta['retention_days'],
        'retention_limits': {'events': meta['max_events'], 'logical_bytes': meta['max_bytes']},
        'pruned_events': meta['pruned_events'] if last is None or last <= at else None,
        'history_removed_through_as_of': _iso(min(pruned, at)) if pruned is not None else None,
        'no_scheduler_heartbeat': True,
    }, started, pruned


def _quote_row(row, generated, at):
    _require(isinstance(row, dict) and isinstance(row.get('ticker'), str)
             and re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,31}', row['ticker']) is not None)
    result = {'ticker': row['ticker']}
    for name in ('quote', 'trade'):
        value = row[name]
        _require(isinstance(value, dict) and value['status'] in QUOTE_STATES)
        stamp = _instant(value['timestamp']) if value['timestamp'] is not None else None
        age = value['age_seconds']
        _require(age is None or _number(age))
        _require((stamp is None) == (age is None))
        result[name] = {
            'status_at_generation': value['status'],
            'timestamp': _iso(stamp),
            'age_seconds_at_generation': age,
            'age_seconds_as_of': round((at - stamp).total_seconds(), 6) if stamp else None,
        }
    volume = row['delayed_volume']
    _require(isinstance(volume, dict) and isinstance(volume.get('status'), str))
    result['delayed_volume_status'] = volume['status']
    return result


def _receipt(snapshot, event, at):
    digest = event['payload']['receipt_sha256']
    value = _json_blob(snapshot, digest, 'receipt')
    committed = _instant(event['recorded_at'])
    _require(value.get('schema_version') == morning.VERSION and value.get('dry_run') is False)
    _require(value['publication']['data_sha256'] == event['source_sha256']
             and value['publication']['applicable_session'] == event['applicable_session'])
    generated, started, expires = (_instant(value[key]) for key in ('generated_at', 'collection_started_at', 'expires_at'))
    _require(started <= generated <= committed <= at and generated < expires)
    _require(value['status'] in morning.STATUSES and isinstance(value['rows'], list)
             and len(value['rows']) <= morning.MAX_ROWS)
    sources = value['sources']
    _require(isinstance(sources, dict) and set(sources) == {'iex', 'delayed_sip'})
    feeds = {}
    for feed, source in sources.items():
        _require(isinstance(source, dict) and source['status'] in ('ok', 'unavailable', 'not_requested')
                 and source['error_kind'] in morning.SOURCE_ERRORS)
        checked = _instant(source['checked_at']) if source['checked_at'] is not None else None
        _require(checked is None or started <= checked <= generated)
        feeds[feed] = {key: source[key] for key in ('status', 'scope', 'entitlement', 'error_kind', 'minimum_delay_seconds')}
        feeds[feed]['checked_at'] = _iso(checked)
    coverage = value['coverage']
    _require(isinstance(coverage, dict) and set(coverage) == {'halts', 'issuer_news', 'earnings'})
    halts = coverage['halts']
    _require(isinstance(halts, dict) and halts['status'] in ('fresh', 'stale', 'unavailable', 'not_requested'))
    selected_coverage = {'halts': {key: halts[key] for key in ('status', 'checked_at', 'fetched_at', 'source_published_at', 'expires_at', 'source_age_seconds', 'receipt_age_seconds')},
                         'issuer_news': {'status': coverage['issuer_news']['status']},
                         'earnings': {'status': coverage['earnings']['status']}}
    rows = [_quote_row(row, generated, at) for row in value['rows']]
    return {
        'receipt_sha256': digest, 'source_sha256': event['source_sha256'],
        'committed_at': _iso(committed), 'generated_at': _iso(generated),
        'collection_started_at': _iso(started), 'expires_at': _iso(expires),
        'commit_after_generation_seconds': round((committed - generated).total_seconds(), 6),
        'expired_as_of': at >= expires, 'status': value['status'],
        'row_count': len(rows), 'feeds': feeds, 'coverage': selected_coverage,
        'quote_status_counts_at_generation': dict(sorted(Counter(row['quote']['status_at_generation'] for row in rows).items())),
        'trade_status_counts_at_generation': dict(sorted(Counter(row['trade']['status_at_generation'] for row in rows).items())),
        'rows': rows,
    }


def _requests(events, complete):
    by_feed = {}
    for feed in FEEDS:
        reserved = [e for e in events if e['kind'] == 'provider_reserved' and e['payload']['feed'] == feed]
        finished = [e for e in events if e['kind'] == 'provider_finished' and e['payload']['feed'] == feed]
        key = lambda e: (e['generation'], e['fence'], e['payload']['attempt'])
        starts, finishes = {key(e) for e in reserved}, {key(e) for e in finished}
        _require(len(starts) == len(reserved) and len(finishes) == len(finished))
        codes = Counter(str(e['payload']['status_code']) for e in finished if e['payload']['status_code'] is not None)
        by_feed[feed] = {
            'retained_reserved_attempts': len(reserved), 'retained_finished_attempts': len(finished),
            'reserved_attempts_as_of': len(reserved) if complete else None,
            'http_response_status_counts': dict(sorted(codes.items())),
            'finished_without_http_status': sum(e['payload']['status_code'] is None for e in finished),
            'reserved_without_retained_finish': len(starts - finishes),
            'finished_without_retained_reservation': len(finishes - starts),
            'first_reserved_at': _iso(reserved[0]['recorded_at']) if reserved else None,
            'latest_finished_at': _iso(finished[-1]['recorded_at']) if finished else None,
        }
    return {'basis': 'durable charged reservations and separately recorded responses; no monetary cost inferred',
            'actual_socket_requests': None, 'per_feed': by_feed}


def _session(snapshot, day, events, at, started, pruned):
    opens, closes, shortened = sessions.hours(day)
    opens, closes = opens.astimezone(timezone.utc), closes.astimezone(timezone.utc)
    collection_start = opens - timedelta(minutes=morning.POLICY['preopen_minutes'])
    gaps = []
    if at < collection_start:
        gaps.append('collection_window_not_started_as_of')
    if started is None or started > at:
        gaps.append('journal_not_started_as_of')
    elif started > collection_start:
        gaps.append('collection_window_precedes_instrumentation')
    if pruned is not None and pruned >= collection_start:
        gaps.append('retention_removed_all_or_part_of_window')
    if snapshot['meta']['migrated'] and (started is None or collection_start < started):
        gaps.append('legacy_history_not_backfilled')
    complete = not gaps
    ingested = [e for e in events if e['kind'] == 'source_ingested']
    latest_source = events[-1]['source_sha256'] if events else None
    # source changes fence earlier workers. Source ingestion remains the latest
    # generation even when an older worker later records its failed outcome.
    if events:
        latest_source = max(events, key=lambda e: (e['generation'], e['id']))['source_sha256']
    current_ingests = [e for e in ingested if e['source_sha256'] == latest_source]
    source = None
    if latest_source:
        raw = _json_blob(snapshot, latest_source, 'publication')
        run = raw['run']
        _require(run['timing']['applicable_session'] == day.isoformat())
        _require(_day(run['session']) < day)
        _require(_instant(run['timing']['opens_at']) == opens)
        ingestion = current_ingests[-1] if current_ingests else None
        admitted = ingestion['payload']['admitted_count'] if ingestion else None
        _require(admitted is None or _integer(admitted))
        source = {'sha256': latest_source, 'measured_session': run['session'],
                  'applicable_session': day.isoformat(), 'published_at': _iso(run['published_at']),
                  'first_ingested_at': _iso(ingested[0]['recorded_at']) if ingested else None,
                  'latest_source_ingested_at': _iso(ingestion['recorded_at']) if ingestion else None,
                  'retained_ingestion_count': len(ingested), 'admitted_plans': admitted,
                  'git_commit': ingestion['payload']['git_commit'] if ingestion else None,
                  'recorded_entry_cutoff_at': _iso(run['timing']['cutoff_at'])}
        if not ingestion:
            gaps.append('latest_source_ingestion_not_retained')
    else:
        gaps.append('source_not_observed')
    complete = not gaps
    finished = [e for e in events if e['kind'] == 'collection_finished']
    committed = [e for e in finished if e['payload']['outcome'] == 'committed']
    receipts = [_receipt(snapshot, event, at) for event in committed]
    first = receipts[0] if receipts else None
    latest = receipts[-1] if receipts else None
    current = next((receipt for receipt in reversed(receipts) if receipt['source_sha256'] == latest_source), None)
    if first and _instant(first['committed_at']) < opens:
        state = 'before_open'
    elif first:
        state = 'late' if complete else 'unobserved'
    elif at < opens:
        state = 'not_yet_due'
    elif complete and source is not None:
        state = 'missing_recorded_receipt'
    else:
        state = 'unobserved'
    plan_state = ('no_admitted_plans' if source and source['admitted_plans'] == 0 else
                  'admitted_plans' if source and source['admitted_plans'] is not None else
                  'no_admitted_plans' if current and current['status'] == 'no_tickets' else 'unknown')
    return {
        'session': day.isoformat(),
        'schedule': {'exchange': sessions.EXCHANGE, 'opens_at': _iso(opens), 'closes_at': _iso(closes),
                     'opens_chicago': opens.astimezone(CHICAGO).isoformat(),
                     'closes_chicago': closes.astimezone(CHICAGO).isoformat(),
                     'shortened': bool(shortened), 'collection_window_starts_at': _iso(collection_start)},
        'evidence': {'window_capture': 'retained_through_as_of' if complete else 'partial_or_unobserved', 'gaps': gaps,
                     'first_recorded_event_at': _iso(events[0]['recorded_at']) if events else None,
                     'last_recorded_event_at': _iso(events[-1]['recorded_at']) if events else None},
        'source': source,
        'source_revisions': [{'source_sha256': e['source_sha256'], 'recorded_at': _iso(e['recorded_at']),
                              'generation': e['generation'], **e['payload']} for e in ingested],
        'plan_state': plan_state,
        'worker_delivery': {'state': state, 'basis': 'local validated commit time; not public HTTPS arrival',
                            'retained_commits': len(receipts), 'first_committed_at': first['committed_at'] if first and complete else None,
                            'first_generated_at': first['generated_at'] if first and complete else None,
                            'first_receipt_sha256': first['receipt_sha256'] if first and complete else None,
                            'first_commit_seconds_from_open': round((_instant(first['committed_at']) - opens).total_seconds(), 6) if first and complete else None,
                            'first_retained_committed_at': first['committed_at'] if first else None,
                            'first_retained_generated_at': first['generated_at'] if first else None,
                            'first_retained_commit_timing': ('before_open' if _instant(first['committed_at']) < opens else 'late') if first else None,
                            'at_least_one_preopen_commit': (True if any(_instant(r['committed_at']) < opens for r in receipts)
                                                          else False if complete and at >= opens else None),
                            'latest_receipt_matches_latest_source': bool(current and latest and current['receipt_sha256'] == latest['receipt_sha256']) if latest else None,
                            'collection_outcomes': dict(sorted(Counter(e['payload']['outcome'] for e in finished).items()))},
        'latest_receipt': latest, 'latest_source_receipt': current,
        'retained_observation_summary': {
            'receipt_status_counts': dict(sorted(Counter(r['status'] for r in receipts).items())),
            'feed_status_counts': {feed: dict(sorted(Counter(r['feeds'][feed]['status'] for r in receipts).items()))
                                   for feed in ('iex', 'delayed_sip')},
            'feed_error_counts': {feed: dict(sorted(Counter(r['feeds'][feed]['error_kind'] for r in receipts
                                    if r['feeds'][feed]['error_kind'] is not None).items())) for feed in ('iex', 'delayed_sip')},
            'quote_row_status_counts': dict(sorted(Counter(row['quote']['status_at_generation']
                                           for r in receipts for row in r['rows']).items())),
        },
        'provider_attempts': _requests(events, complete),
        'public_https_arrival': {'observed_at': None, 'before_open': None, 'status': 'not_recorded_by_writer_journal'},
    }


def _build(snapshot, first, last, at):
    meta, started, pruned = _metadata(snapshot['meta'], at)
    events = snapshot['events']
    previous_id, previous_at = 0, None
    by_session = {}
    for event in events:
        recorded = _instant(event['recorded_at'])
        _require(_integer(event['id'], 1) and event['id'] > previous_id)
        _require(previous_at is None or previous_at <= recorded)
        _require(started is not None and started <= recorded <= _instant(snapshot['meta']['last_at']))
        _require(recorded <= at and first <= _day(event['applicable_session']) <= last)
        _require(sessions.is_session(_day(event['applicable_session'])))
        previous_id, previous_at = event['id'], recorded
        by_session.setdefault(event['applicable_session'], []).append(event)
    rows = [_session(snapshot, day, by_session.get(day.isoformat(), []), at, started, pruned)
            for day in sessions.dates(first, last)]
    counts = dict(sorted(Counter(row['worker_delivery']['state'] for row in rows).items()))
    value = {
        'version': VERSION, 'mode': 'prepared_writer_evidence', 'as_of': _iso(at),
        'range': {'start': first.isoformat(), 'end': last.isoformat(), 'maximum_calendar_days': MAX_RANGE_DAYS},
        'calendar': sessions.authority(), 'display_timezone': 'America/Chicago', 'journal': meta,
        'sessions': rows,
        'summary': {'expected_sessions': len(rows), 'worker_commit_states': counts,
                    'sessions_with_no_admitted_plans': sum(row['plan_state'] == 'no_admitted_plans' for row in rows),
                    'public_https_arrivals': None, 'quote_health_pass': None,
                    'ten_session_acceptance': 'not_established_by_writer_evidence'},
        'limitations': ['Local commit time does not establish browser or public HTTPS arrival.',
                        'No heartbeat is recorded; missing recorded receipts do not establish scheduler outage.',
                        'HTTP status and charged request reservations do not establish usable quotes or monetary cost.',
                        'Quote ages and provider coverage are measured separately from plan availability.',
                        'Source/provider timestamps do not admit writer events recorded after the requested as-of instant.',
                        'Retention and migration gaps cannot be counted as observed failures or successful sessions.'],
    }
    _require(len(encode(value)) <= MAX_REPORT_BYTES)
    return value


def build_report(database, *, start, end, as_of):
    """Build a deterministic report from a released read-only SQLite snapshot."""
    from src import morning_service_journal as journal
    first, last, at = _bounds(start, end, as_of)
    try:
        snapshot = journal.read_journal(database, start=first, end=last, as_of=at, max_read_bytes=MAX_READ_BYTES)
        # read_journal has closed its SQLite connection before JSON/receipt
        # interpretation; reporting holds no transaction across this work.
        return _build(snapshot, first, last, at)
    except (KeyError, TypeError, AttributeError, UnicodeError, OverflowError) as exc:
        raise ValueError('report_journal_evidence_invalid') from None


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode() + b'\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--database', required=True, type=Path)
    parser.add_argument('--start', required=True)
    parser.add_argument('--end', required=True)
    parser.add_argument('--as-of', required=True)
    args = parser.parse_args(argv)
    try:
        if _instant(args.as_of) > utcnow():
            raise ValueError('report_future_as_of_refused')
        value = build_report(args.database, start=args.start, end=args.end, as_of=args.as_of)
        print(encode(value).decode(), end='')
        return 0
    except ValueError as exc:
        # Only fixed module-owned refusal codes may leave this boundary; an
        # arbitrary decoder/date error can include input content and is hidden.
        safe = {'report_future_as_of_refused', 'report_offset_clock_required', 'report_date_invalid', 'report_range_outside_bounds',
                'report_calendar_range_unsupported', 'report_journal_evidence_invalid',
                'journal_mode_or_version_refused', 'journal_read_exceeds_bound',
                'journal_payload_invalid', 'journal_blob_missing', 'journal_blob_invalid',
                'journal_blob_references_invalid', 'journal_identity_invalid', 'journal_policy_invalid',
                'journal_event_bound_invalid', 'journal_database_invalid'}
        reason = str(exc) if str(exc) in safe else 'report_evidence_or_arguments_invalid'
        print(encode({'status': 'refused', 'reason': reason, 'operational_evidence': None}).decode(), end='')
        return 1
    except (OSError, sqlite3.Error):
        print(encode({'status': 'refused', 'reason': 'journal_unavailable', 'operational_evidence': None}).decode(), end='')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
