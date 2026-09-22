"""Offline verifier for an extracted publication and its own historical source.

Usage: python tools/verify_retained_publication.py SOURCE_ROOT DATA_JSON OBJECTS
Extract SOURCE_ROOT/src and SOURCE_ROOT/knowledge from the publication commit;
DATA_JSON must have the original picks.json beside it. No provider/model calls.
"""
import json
import sys
import socket
from pathlib import Path

def blocked(*args, **kwargs):
    raise RuntimeError('offline audit: network forbidden')
socket.socket.connect = socket.socket.connect_ex = socket.create_connection = blocked
source, publication, objects = map(Path, sys.argv[1:4])
sys.path.insert(0, str(source))
data = json.loads(publication.read_bytes())
from src import report, quality, grader

result = {'source': str(source.parent.name), 'publication_shape': 'NOT RUN',
          'mechanical_algebra': 'NOT RUN', 'source_replay': 'BLOCKED',
          'reader_down_only': 'NOT RUN'}
try:
    report.validate(data)
    result['publication_shape'] = 'PASS'
except Exception as exc:
    result['publication_shape'] = 'FAIL'
    result['shape_error'] = str(exc)
errors = []
reader_errors = []
for row in data['bursts']:
    q = row['quality']
    checks = [quality.Check(c['key'], c['letter'], c['label'], c['values'], c['threshold'],
                           c['passed'], c['a_plus'], c['note'], c['partial']) for c in q['checks']]
    score, passes, plus = quality.score_of(checks)
    gates = all(c.passed for c in checks if c.letter in quality.GRADE_GATE_LETTERS)
    grade = quality.grade_of(score, plus, bool(q['vetoes']) or q['unreadable'] is not None, gates)
    if [score, passes, plus, grade] != [q['score'], q['passes'], q['a_plus_count'], q['grade']]:
        errors.append(row['ticker'])
    cl = row.get('claude')
    expected = row['grade_mechanical']
    if cl and cl.get('source') == 'claude':
        returned = grader.grade_for(cl['score'])
        expected = max([expected, returned], key=grader.GRADES.index)
    if expected != row['grade']:
        reader_errors.append(row['ticker'])
result.update(mechanical_algebra='FAIL' if errors else 'PASS', mechanical_errors=errors,
              assessed=len(data['bursts']), reader_down_only='FAIL' if reader_errors else 'PASS',
              reader_errors=reader_errors)
if data['run'].get('evidence'):
    from src import provenance
    picks = json.loads(publication.with_name('picks.json').read_bytes())
    v = provenance.verify(data, picks, objects, require_picks=True)
    result['source_replay'] = 'BLOCKED' if v['status'] == 'PARTIAL' else v['status']
    result['provenance'] = {k: v[k] for k in ['status', 'breaks', 'missing']}
    result['source_checked'] = len(v['checked'])
else:
    result['source_limit'] = 'Pre-provenance: complete exact source frames not retained for all candidates.'
print(json.dumps(result))
