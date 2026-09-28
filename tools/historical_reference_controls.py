"""Isolated arithmetic mutation adequacy checks; never edits repository files."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'tools/historical_breadth_reference.py'
BOOTSTRAP = r'''
import hashlib, json, socket, sys, types
from datetime import date
from pathlib import Path
sys.dont_write_bytecode = True
def offline(*a, **kw):
    raise RuntimeError('mutation control network blocked')
socket.socket.connect = socket.socket.connect_ex = socket.create_connection = offline
source_path, variant = Path(sys.argv[1]), sys.argv[2]
sys.path.insert(0, str(source_path.parents[1]))
source = source_path.read_text(encoding='utf-8')
changes = {
    'mean_of_daily_ratios': (
        'round(up / down, 2) if down else None',
        "round(sum(d['up4']/d['down4'] for d in days[-n:] if d['down4']) / sum(bool(d['down4']) for d in days[-n:]), 2) if down else None"),
    'unknown_as_false': (
        'return None if any(v is None for v in values) else bool(test())',
        'return False if any(v is None for v in values) else bool(test())'),
    'strict_up_boundary': ('move >= 4.0 and v >= 100_000 and v > v1',
                           'move > 4.0 and v >= 100_000 and v > v1'),
    'uncoupled_ratio_upper': ('upper = float(up_max - lost_up)', 'upper = float(up_max)'),
}
if variant != 'baseline':
    old, new = changes[variant]
    assert source.count(old) == 1, (variant, source.count(old))
    source = source.replace(old, new)
module = types.ModuleType('isolated_historical_reference')
module.__file__ = str(source_path)
exec(compile(source, str(source_path), 'exec'), module.__dict__)
from src import sessions
import pandas as pd
target = date(2026, 9, 25)
calendar = sessions.sessions_before(target, 79) + [target]
def frame():
    return pd.DataFrame({'Open': 25., 'High': 25., 'Low': 25., 'Close': 25., 'Volume': 200_000.},
                        index=pd.DatetimeIndex(calendar))
def replay(data):
    return module.reference_replay({'A': data}, target, intended=['A'],
                                   source_identity={'kind': 'synthetic mutation control'})
def last(data):
    return replay(data)['events'][-1]
def check_ratio():
    days = [{'date': str(day), 'up4': 9 if i < 5 else 1,
             'down4': 1 if i < 5 else 9, 'universe': 6500,
             'up50_month': 0, 'down25_quarter': 0}
            for i, day in enumerate(calendar[-10:])]
    actual = module.reference_regime(days)['inputs']['ratio_10d']
    assert actual == 1.0, f'ratio-of-sums expected 1.0; got {actual}'
def check_unknown():
    data = frame().drop(pd.Timestamp(sessions.previous_session(target)))
    actual = last(data)['events']['up4']
    assert actual is None, f'missing prior must be unknown; got {actual}'
def check_boundary():
    data = frame()
    data.loc[data.index[-1], ['Open', 'High', 'Low', 'Close', 'Volume']] = [26., 26., 26., 26., 300_000.]
    actual = last(data)['events']['up4']
    assert actual is True, f'exact +4% event must count; got {actual}'
def check_coupled():
    actual = module.coupled_ratio_bounds([{'possible_up_down': [[0,0], [1,0], [0,1]]}])['finite_ratio']
    assert actual == [0., 0.], f'one contributor cannot be both up and down; got {actual}'
def control():
    data = frame()
    data.loc[data.index[-1], ['Open', 'High', 'Low', 'Close']] = [26.] * 4
    observed = last(data)
    assert observed['measured_4'] and observed['included']
    assert observed['events']['up4'] is False and observed['events']['down4'] is False, 'equal prior volume must suppress the event'
checks = {'mean_of_daily_ratios': check_ratio, 'unknown_as_false': check_unknown,
          'strict_up_boundary': check_boundary, 'uncoupled_ratio_upper': check_coupled,
          'unaffected_equal_volume_control': control}
results = {}
for name, test in checks.items():
    try:
        test()
        results[name] = {'status': 'PASS'}
    except AssertionError as exc:
        results[name] = {'status': 'FAIL', 'assertion': str(exc)}
print(json.dumps({'variant': variant, 'tests': results, 'network_blocked': True,
                  'mutated_module_sha256': hashlib.sha256(source.encode()).hexdigest()}))
'''


def main():
    before = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    variants = ['baseline', 'mean_of_daily_ratios', 'unknown_as_false',
                'strict_up_boundary', 'uncoupled_ratio_upper']
    results = []
    for name in variants:
        completed = subprocess.run([sys.executable, '-c', BOOTSTRAP, str(SOURCE), name],
                                   cwd=ROOT, capture_output=True, text=True)
        if completed.returncode:
            raise RuntimeError('mutation subprocess runtime failure: ' + completed.stderr)
        results.append(json.loads(completed.stdout))
    unchanged = before == hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    baseline = all(v['status'] == 'PASS' for v in results[0]['tests'].values())
    detected = all(r['tests'][r['variant']]['status'] == 'FAIL' for r in results[1:])
    controls = all(r['tests']['unaffected_equal_volume_control']['status'] == 'PASS' for r in results)
    report = {'status': 'PASS' if unchanged and baseline and detected and controls else 'FAIL',
              'scope': 'Synthetic mutation adequacy of independent reference, not a demonstrated production defect.',
              'execution': 'Each variant compiles a changed source string in its own socket-blocked subprocess; no repository edits.',
              'source_sha256': before, 'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'source_file_unchanged': unchanged, 'baseline_all_pass': baseline,
              'all_mutations_detected': detected, 'unaffected_control_all_pass': controls,
              'variants': results}
    destination = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / 'reference-mutations.json'
    destination.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'variants'}))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
