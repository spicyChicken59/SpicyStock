"""Normal-collected failing-before and isolated restored-rule sensitivity proof.

Only child-process function objects change; no repository file is ever mutated.
The inner regressions must fail at the named behavior and an unrelated control
must pass. Fresh synthetic fixture data is the only input.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap

import pytest

ROOT = Path(__file__).resolve().parents[1]
CASES = ("untouched_base", "fixed", "omit_inexact", "wrong_float", "wrong_ordinal", "unbound_query", "reused_source")


def run_control(mode, output):
    output.mkdir(parents=True, exist_ok=True)
    script = textwrap.dedent('''
        import ast, inspect, math, pathlib, sys
        from decimal import Decimal
        import pytest
        from tools import historical_normalization as n
        from tools import historical_reconcile as r
        mode, temp = sys.argv[1:]
        target = 'tests/test_historical_projection.py::test_compact_all_field_combinations_equal_untouched_adapter[31]'
        control = 'tests/test_historical_projection.py::test_legacy_explicit_contract_is_untouched_adapter_control'
        if mode == 'untouched_base':
            path = pathlib.Path('tests/fixtures/projection-compaction/legacy_reconcile.py')
            namespace = vars(r).copy()
            adapter_path = pathlib.Path('tests/fixtures/projection-compaction/legacy_adapter.py')
            adapter = {'Decimal': Decimal, 'math': math}
            exec(compile(adapter_path.read_bytes(), str(adapter_path), 'exec'), adapter)
            namespace['frames_for_replay'] = adapter['frames_for_replay']
            exec(compile(path.read_bytes(), str(path), 'exec'), namespace)
            r.reconcile = namespace['reconcile']
            target = 'tests/test_historical_projection_reconcile.py::test_compact_default_reconciliation_has_no_expanded_float_record_list'
        elif mode in ('omit_inexact', 'wrong_float'):
            source = inspect.getsource(n._projection_row_values)
            before, after = (('if Decimal.from_float(float_value) != Decimal(value):', 'if False:')
                             if mode == 'omit_inexact' else
                             ('hex_values.append(float_value.hex())', 'hex_values.append("0x1.0p+0")'))
            assert source.count(before) == 1
            exec(compile(source.replace(before, after), '<isolated restored projection defect>', 'exec'), vars(n))
        elif mode == 'wrong_ordinal':
            source = inspect.getsource(n._compact_projection)
            before = 'rows.append([ordinal, mask, values])'
            assert source.count(before) == 1
            exec(compile(source.replace(before, 'rows.append([0, mask, values])'), '<isolated ordinal defect>', 'exec'), vars(n))
        elif mode in ('unbound_query', 'reused_source'):
            function = n.iter_projection_conversions if mode == 'unbound_query' else n._projection_rows
            source = ast.parse(inspect.getsource(function))
            message = ('projection query or normalization binding differs' if mode == 'unbound_query'
                       else 'projection selected source identity is ambiguous')
            matches = []
            for node in ast.walk(source):
                if isinstance(node, ast.If) and any(isinstance(child, ast.Raise) and
                   isinstance(child.exc, ast.Call) and child.exc.args and
                   isinstance(child.exc.args[0], ast.Constant) and child.exc.args[0].value == message
                   for child in node.body):
                    matches.append(node)
            assert len(matches) == 1
            matches[0].test = ast.Constant(False)
            ast.fix_missing_locations(source)
            exec(compile(source, '<isolated omitted binding rule>', 'exec'), vars(n))
            target = ('tests/test_historical_projection.py::test_compact_does_not_reuse_projection_for_repeated_ticker_session_query'
                      if mode == 'unbound_query' else
                      'tests/test_historical_projection.py::test_compact_recomputed_context_rejects_one_raw_source_used_for_two_sessions')
            if mode == 'reused_source':
                control = 'tests/test_historical_projection.py::test_compact_same_page_and_row_index_for_different_symbols_is_valid_control'
        elif mode != 'fixed':
            raise AssertionError('unknown control')
        sys.exit(pytest.main([target, control, '-q', '--basetemp', temp]))
    ''')
    # Keep the nested synthetic raw-page filenames below Windows' path ceiling.
    with tempfile.TemporaryDirectory(prefix="pc-", dir=ROOT.parent) as temporary:
        command = [sys.executable, "-c", script, mode, temporary]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60)
    log = result.stdout + result.stderr
    log_path = output / "pytest.log"
    log_path.write_text(log, encoding="utf-8")
    metadata = {"case": mode, "exit_code": result.returncode,
                "expected_exit_code": 0 if mode == "fixed" else 1,
                "source_edits": False, "network_requests": 0, "synthetic_only": True,
                "normalization_sha256": hashlib.sha256((ROOT / "tools/historical_normalization.py").read_bytes()).hexdigest(),
                "reconcile_sha256": hashlib.sha256((ROOT / "tools/historical_reconcile.py").read_bytes()).hexdigest(),
                "controls_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "child_script_sha256": hashlib.sha256(script.encode()).hexdigest(),
                "untouched_adapter_sha256": hashlib.sha256((ROOT / "tests/fixtures/projection-compaction/legacy_adapter.py").read_bytes()).hexdigest(),
                "untouched_reconcile_sha256": hashlib.sha256((ROOT / "tests/fixtures/projection-compaction/legacy_reconcile.py").read_bytes()).hexdigest(),
                "log_sha256": hashlib.sha256(log_path.read_bytes()).hexdigest(),
                "reproduction": "python -m pytest tests/test_historical_projection_controls.py -q --basetemp <outside-git>"}
    (output / "result.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result.returncode, log, metadata


@pytest.mark.parametrize("mode", CASES)
def test_compact_normal_regressions_detect_untouched_and_restored_defects(mode, tmp_path):
    output = tmp_path / mode
    code, log, metadata = run_control(mode, output)
    saved_digest = hashlib.sha256((output / "pytest.log").read_bytes()).hexdigest()
    assert metadata["log_sha256"] == saved_digest
    assert json.loads((output / "result.json").read_bytes())["log_sha256"] == saved_digest
    if mode == "fixed":
        assert code == 0 and "2 passed" in log, log
    else:
        assert code == 1 and "1 failed, 1 passed" in log, log
        assert "ERROR collecting" not in log and "SyntaxError" not in log
        expected_failure = {
            "untouched_base": "default projection must be compact",
            "omit_inexact": "conversion facts differ from untouched adapter",
            "wrong_float": "conversion facts differ from untouched adapter",
            "wrong_ordinal": "selected row reference",
            "unbound_query": "DID NOT RAISE",
            "reused_source": "DID NOT RAISE",
        }[mode]
        assert expected_failure in log, log
