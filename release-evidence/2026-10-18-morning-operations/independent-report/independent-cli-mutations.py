"""Challenge the CLI future-clock test using isolated report source copies."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

root, output = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
source = (root / 'src/morning_service_report.py').read_text()
guard = "        if _instant(args.as_of) > utcnow():\n            raise ValueError('report_future_as_of_refused')\n"
age = "round((at - stamp).total_seconds(), 6) if stamp else None"
assert source.count(guard) == source.count(age) == 1
mutations = [
    ('future_guard_deleted', source.replace(guard, ''), 1),
    ('unrelated_quote_asof_age_flattened', source.replace(age, '0 if stamp else None'), 0),
]
test = 'tests/test_morning_service_report.py::test_cli_future_asof_is_refused_before_database_read'
runner = """import importlib.util, os, sys
from pathlib import Path
root, source = sys.argv[1:]
os.chdir(root)
sys.path.insert(0, root)
import src
spec = importlib.util.spec_from_file_location('src.morning_service_report', source)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
src.morning_service_report = module
import pytest
raise SystemExit(pytest.main(['tests/test_morning_service_report.py::test_cli_future_asof_is_refused_before_database_read', '-q']))
"""
results = []
with tempfile.TemporaryDirectory(prefix='spicystock-report-cli-mutants-') as tmp:
    base = Path(tmp)
    (base / 'runner.py').write_text(runner)
    for name, changed, expected in mutations:
        target = base / (name + '.py')
        target.write_text(changed)
        run = subprocess.run([sys.executable, str(base / 'runner.py'), str(root), str(target)], capture_output=True, text=True, timeout=30)
        results.append({'name': name, 'expected_exit': expected, 'exit_code': run.returncode,
                        'source_sha256': hashlib.sha256(changed.encode()).hexdigest(),
                        'expected_result_observed': run.returncode == expected,
                        'output': run.stdout, 'stderr': run.stderr})
value = {'scope': 'isolated source-copy mutation; no checkout edits or provider calls',
         'source_sha256': hashlib.sha256(source.encode()).hexdigest(), 'test': test, 'results': results}
output.write_text(json.dumps(value, indent=2) + '\n')
print(json.dumps({'target_killed': results[0]['exit_code'] == 1, 'unrelated_control_passed': results[1]['exit_code'] == 0}))
if not all(r['expected_result_observed'] for r in results):
    raise SystemExit(1)
