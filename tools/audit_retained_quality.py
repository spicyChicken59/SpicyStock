"""Read retained Git publications offline; report facts, never regrade or publish.

Output is derived audit evidence, not a raw-artifact copy. V1 and v2 populations
remain separate. Missing fields are null, not zero. No network transport runs.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from contextlib import ExitStack
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import quality, grader  # noqa: E402

CHECKS = (*quality.LETTERS, *quality.EXTRA_CHECKS)


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def blocked_clauses(row):
    """Unsatisfied logical A+ predicates, not independent edits to a stock.

    Only used after equality of the historical quality source has been checked.
    Correlated score/gate/veto predicates are deliberately not called a distance
    in price space, a prediction, or a recommendation to change any threshold.
    """
    q = row['quality']
    checks = {c['letter']: c for c in q['checks']}
    blocks = []
    if q['score'] < grader.GRADE_BANDS[0][0]:
        blocks.append('score_below_A_plus_band')
    if q['a_plus_count'] < quality.MIN_A_PLUS_LETTERS:
        blocks.append('insufficient_A_plus_checks')
    for letter in quality.GRADE_GATE_LETTERS:
        if checks[letter]['status'] != quality.STATUS_PASS:
            blocks.append(letter + '_gate_not_PASS')
    blocks.extend('veto_' + veto for veto in q['vetoes'])
    if q['unreadable'] is not None:
        blocks.append('unreadable')
    return blocks


def distribution(rows):
    counts = lambda field: dict(sorted(Counter(r.get(field, 'UNKNOWN') for r in rows).items()))
    checks = {k: {s: sum(r[k + '_status'] == s for r in rows)
                  for s in ('PASS', 'PARTIAL', 'FAIL', 'UNMEASURED')} for k in CHECKS}
    return {
        'candidate_publications': len(rows), 'final_grades': counts('final_grade'),
        'mechanical_grades': counts('mechanical_grade'), 'A_plus_check_tally': counts('A_plus_checks'),
        'checks': checks,
        'A_plus_flags': {k: sum(r[k + '_A_plus'] is True for r in rows) for k in CHECKS},
        'vetoes': dict(Counter(v for r in rows for v in r['vetoes'])),
        'vetoed_candidates': sum(bool(r['vetoes']) for r in rows),
        'cap_causes': dict(Counter(v for r in rows for v in r['cap_causes'])),
        'capped_candidates': sum(bool(r['cap_causes']) for r in rows),
        'blocking_clauses': dict(Counter(v for r in rows for v in r['blocking_clauses'])),
        'blocking_combinations': dict(Counter('|'.join(r['blocking_clauses']) or 'none' for r in rows)),
        'unsatisfied_clause_counts': dict(sorted(Counter(len(r['blocking_clauses']) for r in rows).items())),
        'C_failures_including_overlap': dict(Counter(v for r in rows for v in r['C_blockers'])),
        'reader_attempted': sum(r['reader_source'] not in ('not_attempted', None) for r in rows),
        'reader_completed': sum(r['reader_source'] == 'claude' for r in rows),
        'reader_downgraded': sum(r['reader_downgraded'] for r in rows),
        'reader_transitions': dict(Counter(r['mechanical_grade'] + '->' + r['final_grade']
                                          for r in rows if r['reader_source'] == 'claude')),
    }


def candidate(item, data, row):
    q = row['quality']
    cs = {c['letter']: c for c in q['checks']}
    caps = []
    # A cap means the score/tally would otherwise earn A or A+, absent vetoes.
    pre_gate = quality.grade_of(q['score'], q['a_plus_count'], bool(q['vetoes']) or q['unreadable'] is not None)
    if pre_gate in quality.GATED_GRADES:
        caps = [k + ':' + cs[k]['status'] for k in quality.GRADE_GATE_LETTERS if cs[k]['status'] != 'PASS']
    if grader.grade_for(q['score']) == 'A+' and q['a_plus_count'] < quality.MIN_A_PLUS_LETTERS and not q['vetoes']:
        caps.append('A_plus_tally')
    c = cs['C']['values']
    conditions = {'giveback': (c.get('giveback'), lambda v: v > quality.MAX_GIVEBACK),
                  'tightness': (c.get('tightness'), lambda v: v > quality.MAX_TIGHTNESS),
                  'base_sessions': (c.get('base_sessions'), lambda v: not quality.BASE_MIN <= v <= quality.BASE_MAX),
                  'breakdowns': (c.get('breakdowns'), lambda v: v > quality.MAX_BREAKDOWNS)}
    cl, p = row.get('claude'), row.get('plan')
    run = data['run']
    return {
        'commit': item['commit'], 'publication_blob': item['blob'], 'session': item['session'],
        'run_id': run.get('run_id'), 'rules_version': data['app']['rules_version'],
        'universe_identity': run['universe'].get('identity'),
        'ticker': row['ticker'], 'discovery': row.get('scan'),
        'assessment': 'unreadable' if q['unreadable'] is not None else 'assessed',
        'mechanical_score': q['score'], 'mechanical_grade': row['grade_mechanical'],
        'A_plus_checks': q['a_plus_count'],
        **{k + '_status': cs[k]['status'] for k in CHECKS},
        **{k + '_A_plus': cs[k]['a_plus'] for k in CHECKS},
        'vetoes': q['vetoes'], 'cap_causes': caps, 'blocking_clauses': blocked_clauses(row),
        'C_blockers': [k + ('_UNKNOWN' if v is None else '') for k, (v, test) in conditions.items() if v is None or test(v)],
        'reader_source': cl.get('source') if cl else 'not_attempted',
        'reader_model': (cl or {}).get('model') or (run.get('model') if cl else None),
        'reader_model_basis': 'candidate' if (cl or {}).get('model') else 'publication' if cl else None,
        'reader_score': (cl or {}).get('score'), 'reader_returned_grade': (cl or {}).get('returned_grade'),
        'reader_clamped_grade': (cl or {}).get('grade'),
        'reader_reason': (cl or {}).get('reason'),
        'reader_key_risk': (cl or {}).get('key_risk'),
        'reader_entry_note': (cl or {}).get('entry_note'),
        'reader_downgraded': row['grade'] != row['grade_mechanical'],
        'final_grade': row['grade'], 'plan_present': p is not None,
        'plan_eligible': p.get('eligible') if p else None, 'plan_action': p.get('action') if p else None,
        'published_ticket': row['ticker'] in data['trades'],
        'regime': data['breadth']['regime']['verdict'],
        'withholding': (row.get('evidence') or {}).get('gate', {}).get('reason'),
        **{'entry_' + k: (run.get('timing') or {}).get(k)
           for k in ('applicable_session', 'opens_at', 'cutoff_at', 'basis')},
        'entry_available_now': None,
    }


def inventory(ref):
    publications, excluded, seen = [], [], set()
    # --full-history includes a last v1 publication on a merged side of v2's
    # replacement. Default path simplification silently omits that real run.
    lines = git('log', '--full-history', '--reverse', '--format=%H|%s', ref, '--', 'docs/data.json').decode().splitlines()
    for line in lines:
        commit, message = line.split('|', 1)
        raw = git('show', commit + ':docs/data.json')
        blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        if blob in seen:
            continue
        seen.add(blob)
        d = json.loads(raw)
        r = d.get('run', {})
        if d.get('fixture') or r.get('fixture') or r.get('dry_run'):
            excluded.append({'commit': commit, 'blob': blob, 'reason': 'fixture_or_dry_run'})
            continue
        v2 = isinstance(d.get('app'), dict) and d['app'].get('version') == '2.0'
        if not v2 and r.get('fixture') is not False:
            excluded.append({'commit': commit, 'blob': blob, 'reason': 'real_identity_unestablished'})
            continue
        item = {'commit': commit, 'blob': blob, 'sha256': hashlib.sha256(raw).hexdigest(),
                'bytes': len(raw), 'source_message': message, 'version': 'v2' if v2 else 'v1',
                'session': r.get('session', r.get('date')), 'published_at': r.get('published_at', d.get('generated'))}
        publications.append((item, d))
    return publications, excluded


def input_funnel(item, data):
    r = data['run']; c = r.get('coverage') or {}; a = c.get('acceptance') or {}; v2 = item['version'] == 'v2'
    u = r.get('universe') or {}
    universe = {k: u.get(k) for k in ('label', 'size', 'identity', 'source', 'classification',
                                    'source_kind', 'fetched_at', 'snapshot_sha256', 'snapshot_relation',
                                    'scan_session', 'point_in_time_membership', 'membership_limit')}
    universe['audit_membership_sha256'] = sha(sorted(u['tickers'])) if 'tickers' in u else None
    native_problems = r.get('problems', r.get('errors'))
    # Stage names suffice for legacy operational errors; do not duplicate old
    # delivery addresses, provider payloads or unrelated account information.
    problems = ([p.get('stage') if isinstance(p, dict) else p for p in native_problems]
                if isinstance(native_problems, list) else native_problems)
    discovery = Counter(b['scan'] for b in data.get('bursts', [])) if v2 else None
    secondary = r.get('stockbee') or {}
    # Modern denominator explicitly excludes SPY. Legacy on_session/fresh counts
    # retain their native meaning, not a reconstructed modern usable denominator.
    return {**item, 'run_id': r.get('run_id'), 'status': r.get('status'),
            'problems': problems,
            'rules_version': data['app'].get('rules_version') if v2 else None,
            'recorded_rules_sha256': sha(data['rules'] if v2 else r.get('rules')),
            'universe': universe, 'input_basis': r.get('input_basis'), 'feed': r.get('feed'),
            'intended_stocks': a.get('intended_stocks', (r.get('universe') or {}).get('size')),
            'ready_stocks': a.get('ready_stocks'),
            'coverage_percentage': 100 * a['fraction'] if 'fraction' in a else None,
            'native_coverage': c or None, 'reader': r.get('reads', r.get('scored_by')), 'model': r.get('model'),
            'legacy_stopped_printing': r.get('stopped_printing') if not v2 else None,
            'recorded_timing': r.get('timing'),
            'reaction_rows': len(data.get('bursts', [])) if v2 else None,
            'derived_matched_families': dict(discovery) if v2 else None,
            'derived_measured_nonmatches': c['measured'] - len(data['bursts'])
                if v2 and c.get('errors') == 0 and 'measured' in c else None,
            'legacy_funnel': None if v2 else {k: r.get(k) for k in
                ('bursts', 'passed_gate', 'scored', 'score_cap', 'shortlist_size', 'scored_by')},
            'legacy_secondary_discovery': None if v2 or not secondary else {
                'limit': 'Separate legacy measurement; bounded rows cannot establish a complete overlap population.',
                **{k: {f: (secondary.get(k) or {}).get(f) for f in ('matched', 'shown')}
                   for k in ('scan', 'dollar')}},
            'legacy_candidate_rows': None if v2 else len(data.get('candidates', [])),
            'scorecard': data.get('scorecard') if v2 else None}


def legacy_assessment(item, data):
    """Use the stored historical band table, never today's v2 checklist."""
    source = git('show', item['commit'] + ':src/scorer.py').decode()
    tree = ast.parse(source)
    bands = next(ast.literal_eval(n.value) for n in tree.body
                 if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
                 and n.target.id == 'VERDICT_BANDS')
    rows = data.get('candidates', [])
    errors = [r['ticker'] for r in rows
              if r['provenance']['source'] == 'claude' and r['verdict'] !=
              next((label for floor, label in bands if r['score'] >= floor), 'skip')]
    # Search other retained sections for literal A+ labels as well. A hit here
    # needs its own dated lineage, and is never counted as a current candidate.
    def labels(value, path=''):
        if isinstance(value, dict):
            return [hit for k, v in value.items() for hit in labels(v, path + '/' + str(k))]
        if isinstance(value, list):
            return [hit for i, v in enumerate(value) for hit in labels(v, path + '/' + str(i))]
        return [path] if value == 'A+' else []
    return {**item, 'final_verdicts': dict(Counter(r.get('verdict', 'UNKNOWN') for r in rows)),
            'historical_bands': bands, 'score_band_check': 'FAIL' if errors else 'PASS',
            'score_band_errors': errors, 'literal_A_plus_paths': labels(data),
            'A_plus_legacy_bucket_setups': [b.get('setups') for b in data.get('evidence', {}).get('by_score', [])
                                           if b.get('verdict') == 'A+'],
            'mechanical_contract': None,
            'limit': 'Legacy scorer and different letter meanings; no v2 A+ checklist or full source-frame replay.'}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ref', required=True, help='Pinned local Git revision; never fetched')
    p.add_argument('--output', type=Path, required=True, help='Derived JSON summary')
    p.add_argument('--candidates', type=Path, required=True, help='Derived candidate matrix CSV or deterministic CSV.gz')
    args = p.parse_args(argv)
    def no_network(*a, **kw):
        raise RuntimeError('retained quality audit forbids network')
    socket.socket.connect = socket.socket.connect_ex = socket.create_connection = no_network
    pubs, excluded = inventory(args.ref)
    rows, funnels, plus, legacy = [], [], [], []
    latest = {}
    source = git('hash-object', str(ROOT / 'src/quality.py')).decode().strip()
    for item, d in pubs:
        funnels.append(input_funnel(item, d))
        if item['version'] == 'v1':
            legacy.append(legacy_assessment(item, d))
            continue
        if git('rev-parse', item['commit'] + ':src/quality.py').decode().strip() != source:
            raise ValueError('historical quality source differs; compatible analysis required')
        these = [candidate(item, d, b) for b in d['bursts']]
        latest[item['session']] = item['blob']
        rows.extend(these)
        for row, original in zip(these, d['bursts'], strict=True):
            if row['mechanical_grade'] == 'A+' or row['final_grade'] == 'A+':
                plus.append({**row, 'reader_recorded_result': original.get('claude'),
                             'quality_values': {c['letter']: c['values'] for c in original['quality']['checks']}})
    selected = [r for r in rows if latest[r['session']] == r['publication_blob']]
    summaries = {f['blob']: distribution([r for r in rows if r['publication_blob'] == f['blob']])
                 for f in funnels if f['version'] == 'v2'}
    result = {'audit_version': 1, 'base': args.ref, 'quality_source_blob': source,
              'basis': 'Retained production records; counts reconstructed offline; no new provider/model execution.',
              'limits': ['All-revision counts include repeated same-session publications.',
                         'Latest-per-session is a descriptive view, not identical populations across universe/rules boundaries.',
                         'Logical blocked clauses are correlated and are not independent changes to a stock.',
                         'Pre-provenance source-frame replay and historical current-entry availability may be unknown.'],
              'excluded': excluded, 'publications': funnels, 'legacy': legacy,
              'v2_all_revisions': distribution(rows), 'v2_latest_per_session': distribution(selected),
              'v2_by_publication': summaries, 'mechanical_or_final_A_plus': plus}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    with ExitStack() as stack:
        if args.candidates.suffix == '.gz':
            raw = stack.enter_context(args.candidates.open('wb'))
            archive = stack.enter_context(gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0))
            handle = stack.enter_context(io.TextIOWrapper(archive, encoding='utf-8', newline=''))
        else:
            handle = stack.enter_context(args.candidates.open('w', newline='', encoding='utf-8'))
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, separators=(',', ':')) if isinstance(v, (dict, list))
                             else 'UNKNOWN' if v is None else v for k, v in row.items()})
    print(json.dumps({'publications': len(funnels), 'v2_candidates': len(rows),
                      'v2_latest_per_session_candidates': len(selected), 'mechanical_A_plus': len(plus),
                      'final_A_plus': sum(r['final_grade'] == 'A+' for r in rows)}))


if __name__ == '__main__':
    main()
