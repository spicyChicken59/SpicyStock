"""Actual CLI boundary checks using a synthetic historical Store, without network."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve()
sys.path.insert(0, str(root))
from src import morning_service as service

checks = []
with tempfile.TemporaryDirectory(prefix='spicystock-report-cli-') as tmp:
    database = Path(tmp) / 'synthetic.sqlite'
    store = service.Store(database)
    raw = (root / 'tests/fixtures/morning/full-publication.json').read_bytes()
    assert store.ingest(raw, now='2026-09-11T12:50:00Z') == 'ingested'
    now = datetime.now(timezone.utc)
    command = [sys.executable, '-m', 'src.morning_service_report', '--database', str(database),
               '--start', '2026-09-11', '--end', '2026-09-11', '--as-of']
    historical = subprocess.run(command + ['2026-09-11T13:30:00Z'], cwd=root, capture_output=True, text=True, timeout=10)
    value = json.loads(historical.stdout)
    checks.append({'name': 'actual subprocess CLI accepts historical as-of', 'passed': historical.returncode == 0 and value['as_of'] == '2026-09-11T13:30:00+00:00'})
    future = subprocess.run(command + [(now + timedelta(days=1)).isoformat()], cwd=root, capture_output=True, text=True, timeout=10)
    value = json.loads(future.stdout)
    checks.append({'name': 'actual subprocess CLI refuses future as-of with no operational evidence', 'passed': future.returncode == 1 and value == {'status': 'refused', 'reason': 'report_future_as_of_refused', 'operational_evidence': None}})
    checks.append({'name': 'CLI refusals and valid output have no diagnostics', 'passed': historical.stderr == future.stderr == ''})
result = {'scope': 'actual wall-clock CLI boundary over a synthetic historical Store; no provider or public arrival measurement',
          'checked_at': now.isoformat(), 'checks': checks,
          'source_sha256': hashlib.sha256((root / 'src/morning_service_report.py').read_bytes()).hexdigest(),
          'passed': sum(c['passed'] for c in checks), 'total': len(checks)}
output.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'passed': result['passed'], 'total': result['total']}))
if not all(c['passed'] for c in checks):
    raise SystemExit(1)
