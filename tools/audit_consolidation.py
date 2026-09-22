"""Offline C audit of the frozen nine-publication population from #85.

No scans, reader/provider calls, future returns, publication writes or rule
changes. Counterfactual boundaries/windows are diagnostics, never corrections.
Reads existing content-addressed frames; writes derived summaries and cases.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tarfile
import tempfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import provenance, quality as q  # noqa: E402
from src.pipeline import base_block  # noqa: E402

BASE = '6533e616bd14ebfebeeccb4c9b1b0d463b47dbb4'
INVENTORY = 'docs/input-truthfulness/2026-09-22-quality-audit.json'
CONDITIONS = ('length', 'giveback', 'tightness', 'breakdowns')
FIELDS = ('base_sessions', 'giveback', 'tightness', 'breakdowns',
          'bursts_in_base', 'base_volume_vs_leg', 'base_volume_vs_avg')
STATES = ('PASS', 'PARTIAL', 'FAIL', 'UNMEASURED')


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def mechanical_ast(raw):
    # #86 added reader evidence in metrics_for_model only. Compare every
    # other definition/constant, not just the particular functions audited.
    tree = ast.parse(raw)
    if isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
        tree.body.pop(0)  # Attribution-only module docstring is not a rule.
    tree.body = [n for n in tree.body if not isinstance(n, ast.FunctionDef)
                 or n.name != 'metrics_for_model']
    return ast.dump(tree, include_attributes=False)


def blockers(v):
    return [k for k, failed in (
        ('length', not q.BASE_MIN <= v['base_sessions'] <= q.BASE_MAX),
        ('giveback', v['giveback'] > q.MAX_GIVEBACK),
        ('tightness', v['tightness'] > q.MAX_TIGHTNESS),
        ('breakdowns', v['breakdowns'] > q.MAX_BREAKDOWNS)) if failed]


def status_with_length(v, minimum, maximum):
    # OFFLINE COUNTERFACTUAL: only the pass interval changes; current partial
    # fallback, giveback, tightness and breakdown requirements are frozen.
    core = not any(k != 'length' for k in blockers(v))
    if not core:
        return 'FAIL'
    if minimum <= v['base_sessions'] <= maximum:
        return 'PASS'
    return 'PARTIAL' if v['base_sessions'] >= q.PARTIAL_BASE_MIN else 'FAIL'


def histogram(values):
    return {str(k): v for k, v in sorted(Counter(values).items())}


def summary(rows):
    failures = [r for r in rows if r['status'] == 'FAIL']
    numeric = {}
    for field in FIELDS:
        values = [r['values'][field] for r in rows if r['values'][field] is not None]
        numeric[field] = {
            'measured': len(values), 'unknown': len(rows) - len(values),
            'histogram': histogram(values),
            'quantiles_linear': dict(zip(('min', 'p10', 'p25', 'p50', 'p75', 'p90', 'p95', 'max'),
                [round(float(v), 6) for v in np.quantile(values, [0, .1, .25, .5, .75, .9, .95, 1])], strict=True))}
    sole = lambda population: {k: sum(r['blockers'] == [k] for r in population) for k in CONDITIONS}
    overlap = lambda population: {a: {b: sum(a in r['blockers'] and b in r['blockers'] for r in population)
                                     for b in CONDITIONS} for a in CONDITIONS}
    around = {}
    for field, threshold in [('giveback', .25), ('giveback', .34), ('tightness', .70), ('tightness', 1.0),
                              ('base_volume_vs_leg', 1.0), ('base_volume_vs_avg', 1.0)]:
        around[f'{field}@{threshold}'] = {
            str(round(threshold + step / 100, 2)): sum(r['values'][field] == round(threshold + step / 100, 2) for r in rows)
            for step in (-2, -1, 0, 1, 2)}
    return {
        'rows': len(rows), 'C_status': {k: sum(r['status'] == k for r in rows) for k in STATES},
        'C_A_plus': sum(r['a_plus'] for r in rows),
        'mechanical_grades': dict(sorted(Counter(r['grade'] for r in rows).items())),
        'unsatisfied_subconditions_all_rows': {k: sum(k in r['blockers'] for r in rows) for k in CONDITIONS},
        'unsatisfied_subconditions_C_FAIL_only': {k: sum(k in r['blockers'] for r in failures) for k in CONDITIONS},
        'sole_unsatisfied_subcondition_all_rows': sole(rows), 'sole_subcondition_C_FAIL_only': sole(failures),
        'overlap_all_rows': overlap(rows), 'overlap_C_FAIL_only': overlap(failures),
        'combination_counts': dict(sorted(Counter('|'.join(r['blockers']) or 'none' for r in rows).items())),
        'numeric': numeric, 'boundary_neighborhoods': around,
        'C_FAIL_other_five_letters_PASS': sum(r['status'] == 'FAIL' and r['other_letters_pass'] for r in rows),
        'C_nonPASS_other_five_letters_PASS': sum(r['status'] != 'PASS' and r['other_letters_pass'] for r in rows),
        'C_PASS_not_A_plus_blockers': dict(Counter(k for r in rows if r['status'] == 'PASS' for k in r['a_plus_blockers'])),
        'length_only_counterfactuals': {
            f'{lo}-{hi}': {'classification': 'OFFLINE COUNTERFACTUAL, other current rules frozen',
                'C_status': dict(sorted(Counter(status_with_length(r['values'], lo, hi) for r in rows).items())),
                'transitions': dict(sorted(Counter(r['status'] + '->' + status_with_length(r['values'], lo, hi) for r in rows).items()))}
            for lo, hi in [(3, 10), (5, 40)]}}


def geometry(b, base, leg, dates):
    s, e = base['start'], base['end']
    daily = q._range_pcts(b, s, e)
    norm = q._range_pcts(b, s - q.TIGHTNESS_NORM_SESSIONS, s - 1)
    breakdowns = [i for i in range(s, e + 1) if q._is_breakdown_day(b, i)]
    return {
        'peak_index': base['peak'], 'peak_date': dates[base['peak']],
        'base_start_date': dates[s], 'base_end_date': dates[e],
        'leg_start_date': dates[leg['start']], 'leg_end_date': dates[leg['end']],
        'actual_base_high': float(max(b.h[s:e + 1])),
        'giveback_numerator': float(base['high'] - base['low']),
        'giveback_denominator': float(base['high'] - leg['low']),
        'base_mean_daily_range_pct': q._mean(daily), 'norm_mean_daily_range_pct': q._mean(norm),
        'base_max_daily_range_pct': max(daily), 'norm_sessions': len(norm),
        'base_mean_volume': q._mean(b.v[s:e + 1]),
        'leg_mean_volume': q._mean(b.v[leg['start']:leg['end'] + 1]),
        'average_volume': q._mean(b.v[max(b.t - q.VOLUME_AVG_SESSIONS, 0):b.t]),
        'breakdown_dates': [dates[i] for i in breakdowns],
        'price_only_breakdowns_also_meeting_scan_volume': sum(
            b.v[i] > b.v[i - 1] and b.v[i] >= 100000 for i in breakdowns),
        'base_return_close_pct': q._pct_of(b.c[e] - b.c[s], b.c[s]),
        'base_close_extrema': [float(min(b.c[s:e + 1])), float(max(b.c[s:e + 1]))]}


def alternatives(b, base, dates):
    # Deterministic, defined before inspecting scores. This is NOT a competing
    # trading algorithm: even a containing local peak can hide a prior decline.
    peaks = [i for i in range(max(1, b.t - 21), b.t - 3)
             if b.h[i] >= b.h[i - 1] and b.h[i] > b.h[i + 1]
             and b.h[i] >= max(b.h[i + 1:b.t])]
    selected = [('one_session_earlier', base['peak'] - 1), ('one_session_later', base['peak'] + 1),
                ('latest_containing_peak_3_20', max(peaks) if peaks else None)]
    result = {}
    for label, peak in selected:
        if peak is None or not 0 <= peak < b.t - 1:
            continue
        ab = {'peak': peak, 'start': peak + 1, 'end': b.t - 1, 'length': b.t - peak - 1,
              'high': float(b.h[peak]), 'low': float(min(b.l[peak + 1:b.t]))}
        al = q._find_leg(b, ab)
        ac = q._check_c(b, ab, al)
        result[label] = {'peak_date': dates[peak], 'base_start': dates[peak + 1], 'base_end': dates[b.t - 1],
            'base_high': ab['high'], 'base_low': ab['low'], 'leg_start': dates[al['start']],
            'leg_end': dates[al['end']], 'leg_low': al['low'], 'leg_sessions': al['length'],
            'leg_gain_pct': al['gain_pct'], 'status': ac.status, 'a_plus': ac.a_plus,
            'values': ac.value, 'same_peak': peak == base['peak']}
    return result


def reconstruct():
    raw_inventory = git('show', BASE + ':' + INVENTORY)
    inventory = json.loads(raw_inventory)
    current_source = (ROOT / 'src/quality.py').read_bytes()
    signature = mechanical_ast(current_source)
    assert signature == mechanical_ast(git('show', BASE + ':src/quality.py')), 'Mechanical code changed'
    rows, publications = [], []
    for pub in inventory['publications']:
        if pub['version'] != 'v2':
            continue
        raw = git('show', pub['commit'] + ':docs/data.json')
        assert digest(raw) == pub['sha256']
        assert mechanical_ast(git('show', pub['commit'] + ':src/quality.py')) == signature
        data = json.loads(raw)
        assert not data.get('fixture') and not data['run'].get('dry_run')
        publications.append({k: pub[k] for k in ('commit', 'blob', 'sha256', 'session', 'rules_version')})
        for row in data['bursts']:
            quality = row['quality']
            cs = {c['letter']: c for c in quality['checks']}
            c, v = cs['C'], cs['C']['values']
            assert all(v[k] is not None for k in ('base_sessions', 'giveback', 'tightness', 'breakdowns'))
            assert status_with_length(v, q.BASE_MIN, q.BASE_MAX) == c['status']
            checks = [q.Check(x['key'], x['letter'], x['label'], x['values'], x['threshold'],
                              x['passed'], x['a_plus'], x['note'], x['partial']) for x in quality['checks']]
            score, passes, plus = q.score_of(checks)
            grade = q.grade_of(score, plus, bool(quality['vetoes']) or quality['unreadable'] is not None,
                               all(cs[k]['passed'] for k in q.GRADE_GATE_LETTERS))
            assert (score, passes, plus, grade) == (quality['score'], quality['passes'], quality['a_plus_count'], row['grade_mechanical'])
            r = {'id': pub['commit'][:7] + '/' + row['ticker'], 'session': pub['session'], 'ticker': row['ticker'],
                 'commit': pub['commit'], 'publication_blob': pub['blob'], 'rules_version': pub['rules_version'],
                 'status': c['status'], 'a_plus': c['a_plus'], 'values': v, 'blockers': blockers(v),
                 'grade': grade, 'score': score,
                 'other_letters_pass': all(cs[k]['status'] == 'PASS' for k in q.LETTERS if k != 'C'),
                 'check_statuses': {k: x['status'] for k, x in cs.items()},
                 'base': quality['base'], 'leg': quality['leg']}
            r['a_plus_blockers'] = [k for k, fail in (
                ('ordinary_C_not_PASS', c['status'] != 'PASS'), ('breakdowns_nonzero', v['breakdowns'] != 0),
                ('bursts_nonzero', v['bursts_in_base'] != 0), ('giveback_above_0.25', v['giveback'] > .25),
                ('tightness_above_0.70', v['tightness'] > .7),
                ('volume_not_below_leg', v['base_volume_vs_leg'] is None or v['base_volume_vs_leg'] >= 1),
                ('volume_not_below_average', v['base_volume_vs_avg'] is None or v['base_volume_vs_avg'] >= 1)) if fail]
            assert (not r['a_plus_blockers']) == c['a_plus']
            evidence = row.get('evidence') or {}
            r['frame_replay'] = 'BLOCKED'
            if evidence.get('source'):
                obj = provenance._object(ROOT / 'docs/evidence', evidence['source']['sha256'])
                df = provenance.frame_of(obj)
                assert obj['dates'][-1] == pub['session']
                assert provenance.source_ref(df, obj) == evidence['source']
                assessment = q.assess(df)
                assert {**assessment.to_dict(), 'base': base_block(assessment.base, df)} == quality, r['id']
                b = q._arrays(df, -1)
                base = q._find_base(b)
                leg = q._find_leg(b, base)
                r.update(source_sha256=evidence['source']['sha256'], frame_replay='PASS',
                         geometry=geometry(b, base, leg, obj['dates']),
                         counterfactual=alternatives(b, base, obj['dates']))
            rows.append(r)
    assert len(rows) == 3547 and len(publications) == 9
    assert Counter(r['status'] for r in rows) == {'PASS': 304, 'PARTIAL': 67, 'FAIL': 3176}
    assert sum(r['a_plus'] for r in rows) == 32
    return rows, publications, digest(raw_inventory), digest(current_source)


def select_sample(rows):
    pool = sorted((r for r in rows if r['frame_replay'] == 'PASS'), key=lambda r: (r['session'], r['commit'], r['ticker']))
    picked = {}
    def choose(reason, predicate):
        match = next(r for r in pool if predicate(r))
        picked.setdefault(match['id'], {'row': match, 'strata': []})['strata'].append(reason)
    for status in ('PASS', 'PARTIAL', 'FAIL'):
        choose('C ' + status, lambda r, s=status: r['status'] == s)
    choose('C A+ flag', lambda r: r['a_plus'])
    choose('C alone fails among weighted letters', lambda r: r['status'] == 'FAIL' and r['other_letters_pass'])
    choose('Mechanical A+ with C PASS but no C A+', lambda r: r['grade'] == 'A+' and r['status'] == 'PASS' and not r['a_plus'])
    for n in (1, 2, 3, 4, 5, 10, 11, 19, 20, 21, 22, 39):
        choose(f'Length = {n}', lambda r, n=n: r['values']['base_sessions'] == n)
    for field, targets in [('giveback', (.25, .26, .34, .35)), ('tightness', (.70, .71, 1.0, 1.01)), ('breakdowns', (1, 2))]:
        for v in targets:
            choose(f'{field} = {v}', lambda r, f=field, v=v: r['values'][f] == v)
    # Explicit, reproducible geometry studies; selected for source/measurement
    # questions. Nothing in this selection reads a subsequent price or return.
    for identity, reason in {
        '5808054/CTAS': '33-session outer box versus an 11-session recent pause',
        '5808054/PLTR': 'Breakdown count changes with the selected boundary',
        '8387cce/IDT': 'Two-session high reset despite nearby earlier range',
        '8387cce/NFG': 'Small absolute daily range versus an even smaller norm',
        '49e2724/WBD': 'Mechanical A+ without the C A+ giveback flag',
        '49e2724/MRK': 'Mechanical A+ with C PASS; original volume facts',
        '49e2724/PTGX': '21-session C PARTIAL and mechanical A+',
        '5808054/INSW': 'Ordinary C PASS despite both volume ratios above one',
        '5808054/CDNA': 'Prior-day high outside the stored peak anchor',
    }.items():
        choose(reason, lambda r, identity=identity: r['id'] == identity)
    return [{**v['row'], 'selection_strata': v['strata']} for v in picked.values()]


def segmentation_summary(rows):
    frames = [r for r in rows if r['frame_replay'] == 'PASS']
    results = {}
    for name in ('one_session_earlier', 'one_session_later', 'latest_containing_peak_3_20'):
        eligible = [r for r in frames if name in r['counterfactual']]
        changed = [r for r in eligible if r['status'] != r['counterfactual'][name]['status']]
        results[name] = {'classification': 'OFFLINE COUNTERFACTUAL, not a source-labelled true base',
            'eligible': len(eligible), 'C_status_changes': len(changed), 'changed_ids': [r['id'] for r in changed],
            'changed_over_all_frame_rows_pct': round(100 * len(changed) / len(frames), 4),
            'transitions': dict(sorted(Counter(r['status'] + '->' + r['counterfactual'][name]['status'] for r in eligible).items())),
            'changed_boundaries': sum(not r['counterfactual'][name]['same_peak'] for r in eligible)}
    perturbation_union = [r['id'] for r in frames if any(
        r['status'] != a['status'] for k, a in r['counterfactual'].items() if k != 'latest_containing_peak_3_20')]
    return {'frame_rows': len(frames), 'counterfactuals': results,
        'one_session_either_direction_status_change_ids': perturbation_union,
        'one_session_either_direction_status_change_count': len(perturbation_union),
        'prior_day_high_exceeds_anchor': sum(r['geometry']['actual_base_high'] > r['base']['high'] for r in frames),
        'negative_giveback': sum(r['values']['giveback'] < 0 for r in frames),
        'tightness_fails_with_mean_daily_range_under_2pct': sum(
            r['values']['tightness'] > 1 and r['geometry']['base_mean_daily_range_pct'] < 2 for r in frames),
        'price_only_count_differs_from_volume_qualified_count': sum(
            r['values']['breakdowns'] != r['geometry']['price_only_breakdowns_also_meeting_scan_volume'] for r in frames),
        'breakdown_gate_differs_if_scan_volume_wrongly_required': sum(
            (r['values']['breakdowns'] <= 1) != (r['geometry']['price_only_breakdowns_also_meeting_scan_volume'] <= 1) for r in frames)}


def render_cases(samples):
    lines = ['# Retained C geometry cases — 22 September 2026', '',
        'Generated by `tools/audit_consolidation.py`; deterministic reconstruction, not a human visual test.',
        'Only source bars at or before the publication session are consumed. All selected frames replay exactly.',
        'Publication prefixes and typed source hashes resolve against the dated audit JSON. No raw bars are duplicated.', '',
        'Every base/leg boundary, ratio, rounding decision and A+ conjunction is SpicyStock DERIVED.',
        'The 3–20 length has the selected 2014 PRIMARY basis; the breakdown maximum has the later 2020 Bonde basis.',
        'Shallow/narrow/orderly/lower-volume are source concepts; exact giveback, tightness and averaging windows are DERIVED.',
        'See `knowledge/consolidation-quality.md` and the parent audit for source versions and limits.', '']
    for r in samples:
        v, b, g, leg = r['values'], r['base'], r['geometry'], r['leg']
        lines += [f"## {r['id']} · {r['session']}", '',
            '**Selection:** ' + '; '.join(r['selection_strata']) + '.', '',
            f"C **{r['status']}**, C A+ **{r['a_plus']}**; mechanical **{r['grade']}**, score **{r['score']}**.",
            f"Source `{r['source_sha256']}`; frame replay **PASS**.", '',
            '| Measurement | Deterministic reconstruction |', '|---|---|',
            f"| Base | {b['start']} → {b['end']}; {v['base_sessions']} sessions; indices {b['start_index']}..{b['end_index']} |",
            f"| Peak / box | {g['peak_date']}; anchor high {b['high']}; actual base high {g['actual_base_high']}; low {b['low']} |",
            f"| Prior leg | {g['leg_start_date']} → {g['leg_end_date']}; {leg['length']} sessions; high {leg['high']}; low {leg['low']} |",
            f"| Giveback | {g['giveback_numerator']:.6f} / {g['giveback_denominator']:.6f} → {v['giveback']} |",
            f"| Tightness | mean daily range {g['base_mean_daily_range_pct']:.6f}% / {g['norm_mean_daily_range_pct']:.6f}% over {g['norm_sessions']} prior sessions → {v['tightness']} |",
            f"| Breakdowns / bursts | {v['breakdowns']} / {v['bursts_in_base']}; breakdown dates {', '.join(g['breakdown_dates']) or 'none'} |",
            f"| Base / leg / prior-50 volume means | {g['base_mean_volume']:.6f} / {g['leg_mean_volume']:.6f} / {g['average_volume']:.6f} shares |",
            f"| Base volume ratios | vs leg {v['base_volume_vs_leg']}; vs average {v['base_volume_vs_avg']} |",
            f"| Ordinary unsatisfied clauses | {', '.join(r['blockers']) or 'none'} |",
            f"| C A+ unsatisfied clauses | {', '.join(r['a_plus_blockers']) or 'none'} |", '',
            'All other original check statuses: ' + ', '.join(f'{k} {v}' for k, v in r['check_statuses'].items() if k != 'C') + '.', '']
        a = r['counterfactual'].get('latest_containing_peak_3_20')
        if a and not a['same_peak']:
            av = a['values']
            lines += ['**OFFLINE COUNTERFACTUAL — latest containing local peak, not an adjudicated replacement:**',
                f"peak {a['peak_date']}; base {a['base_start']} → {a['base_end']}, {av['base_sessions']} sessions, "
                f"high/low {a['base_high']}/{a['base_low']}; leg {a['leg_start']} → {a['leg_end']}, low {a['leg_low']}. "
                f"Breakdowns {av['breakdowns']}, giveback {av['giveback']}, tightness {av['tightness']}, "
                f"volume vs leg/average {av['base_volume_vs_leg']}/{av['base_volume_vs_avg']}; C {a['status']}, C A+ {a['a_plus']}.", '']
    return '\n'.join(lines) + '\n'


def verify_historical(publications):
    """Use each publication's own source and prompt with the existing verifier.

    Only extracted source and original JSON are temporary; retained raw-bar
    objects stay in place. The verifier independently blocks network calls.
    """
    results = {}
    with tempfile.TemporaryDirectory(prefix='spicystock-c-audit-') as temp:
        for p in publications:
            folder = Path(temp) / p['commit']
            source = folder / 'source'
            source.mkdir(parents=True)
            archive = git('archive', p['commit'], 'src', 'knowledge')
            with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
                tar.extractall(source, filter='data')
            for name in ('data.json', 'picks.json'):
                (folder / name).write_bytes(git('show', p['commit'] + ':docs/' + name))
            result = json.loads(subprocess.check_output([
                sys.executable, str(ROOT / 'tools/verify_retained_publication.py'),
                str(source), str(folder / 'data.json'), str(ROOT / 'docs/evidence')]))
            assert result['publication_shape'] == result['mechanical_algebra'] == result['reader_down_only'] == 'PASS'
            assert result['source_replay'] in ('PASS', 'BLOCKED')
            results[p['commit']] = result
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cases', type=Path, required=True)
    args = parser.parse_args()
    def blocked(*a, **kw):
        raise RuntimeError('Consolidation audit forbids network execution')
    socket.socket.connect = socket.socket.connect_ex = socket.create_connection = blocked
    rows, publications, inventory_hash, quality_hash = reconstruct()
    latest = {p['session']: p['commit'] for p in publications}
    all_summary = summary(rows)
    samples = select_sample(rows)
    historical = verify_historical(publications)
    result = {'audit_version': 1, 'base': BASE, 'inventory_sha256': inventory_hash,
        'quality_source_sha256': quality_hash, 'publications': publications,
        'basis': 'RETAINED PRODUCTION EVIDENCE + DETERMINISTIC RECONSTRUCTION; counterfactuals explicitly separated.',
        'limits': ['Candidate-publication rows include same-session revisions; not independent observations.',
                   'No source-labelled human base boundaries are available.',
                   'Earlier 1701 complete frames unavailable; stored checks are not raw replays.',
                   'One-session perturbations need not contain all highs and are stress diagnostics only.',
                   'A later local peak can erase adverse context; no counterfactual selects production rules.'],
        'all_revisions': all_summary,
        'latest_per_session': summary([r for r in rows if r['commit'] == latest[r['session']]]),
        'by_publication': {p['commit']: {k: v for k, v in summary([r for r in rows if r['commit'] == p['commit']]).items()
            if k in ('rows', 'C_status', 'C_A_plus', 'mechanical_grades', 'unsatisfied_subconditions_all_rows')}
            for p in publications},
        'segmentation': segmentation_summary(rows), 'sample': samples,
        'historical_source_verification': historical,
        'mechanical_A_plus_rows': [{k: r[k] for k in ('id', 'session', 'status', 'a_plus', 'values', 'a_plus_blockers', 'frame_replay')} for r in rows if r['grade'] == 'A+'],
        'verification': {'publication_identities': 'PASS', 'historical_mechanical_AST': 'PASS',
            'mechanical_algebra_3547': 'PASS', 'retained_reaction_frame_replay_1846': 'PASS',
            'earlier_frame_replay_1701': 'BLOCKED', 'reader_or_provider_execution': 'NOT RUN'},
        'before_after_attribution_correction': {
            'basis': 'No deterministic quality code or rule changes. Earlier checks reconciled, later frames replayed; no new reader grades.',
            'before_C': all_summary['C_status'], 'after_C': all_summary['C_status'],
            'before_mechanical_grades': all_summary['mechanical_grades'],
            'after_mechanical_grades': all_summary['mechanical_grades'],
            'mechanical_grade_changed_candidates': [], 'mechanical_A_plus_count_change': 0}}
    def numeric(value):
        if isinstance(value, np.integer): return int(value)
        if isinstance(value, np.bool_): return bool(value)
        if isinstance(value, np.floating): return float(value)
        raise TypeError(type(value).__name__)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False, default=numeric) + '\n')
    args.cases.write_text(render_cases(samples))
    print(json.dumps({'rows': len(rows), 'samples': len(samples), 'C': all_summary['C_status'],
                      'frame_replay': 1846, 'mechanical_grade_changes': 0}))


if __name__ == '__main__':
    main()
