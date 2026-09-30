"""Offline shape/refusal controls; small actual kernel controls run in CI wrapper."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from tools import historical_memory_supervisor as memory


def values(limit=memory.MEMORY_BYTES):
    return {'memory.max': limit, 'memory.swap.max': 0, 'memory.oom.group': 1,
            'memory.peak': 8 * 1024 ** 2, 'memory.events': {'max': 0, 'oom': 0, 'oom_kill': 0}}


def files(root, measurements=None):
    root.mkdir()
    for name, value in (measurements or values()).items():
        text = '\n'.join(f'{k} {v}' for k, v in value.items()) if isinstance(value, dict) else str(value)
        (root / name).write_text(text, encoding='ascii')
    (root / 'cgroup.procs').write_text('')
    (root / 'cgroup.kill').write_text('')
    return root


def test_snapshot_reads_exact_kernel_limit_peak_and_events(tmp_path):
    measured = values()
    measured['memory.events']['high'] = 3
    assert memory.snapshot(files(tmp_path / 'group', measured)) == measured


@pytest.mark.parametrize('event_text', ['oom 0\noom_kill 0', 'max 0\noom 0\noom 0\noom_kill 0',
    'max 0\noom invalid\noom_kill 0', 'max 0\noom -1\noom_kill 0'])
def test_incomplete_duplicate_or_malformed_events_refuse(tmp_path, event_text):
    path = tmp_path / 'events'
    path.write_text(event_text)
    with pytest.raises(ValueError):
        memory.counters(path)


@pytest.mark.parametrize('key,value', [('memory.max', memory.MEMORY_BYTES + 1), ('memory.swap.max', 1),
    ('memory.oom.group', 0), ('memory.peak', 0), ('memory.peak', memory.MEMORY_BYTES + 1),
    ('oom', 1), ('oom_kill', 1)])
def test_limit_peak_and_oom_are_independent_fail_closed_checks(key, value):
    measured = values()
    if key in ('oom', 'oom_kill'):
        measured['memory.events'][key] = value
    else:
        measured[key] = value
    assert memory.accepted(measured, memory.MEMORY_BYTES) is False
    assert memory.accepted(values(), memory.MEMORY_BYTES) is True


def test_nonzero_workload_exit_never_becomes_memory_pass():
    assert not memory.accepted(values(), memory.MEMORY_BYTES, -9)
    assert not memory.accepted(values(), memory.MEMORY_BYTES, 2)


def membership(monkeypatch, tmp_path, *, actual=None, measured=None):
    root = tmp_path / 'root'
    root.mkdir()
    group = files(root / 'spicystock-memory-test', measured)
    monkeypatch.setattr(memory, 'CGROUP_ROOT', root)
    monkeypatch.setenv(memory.CGROUP_ENV, str(group))
    original = Path.read_text
    def read(path, *args, **kwargs):
        return ('0::/' + (actual or group.name)) if str(path).replace('\\', '/') == '/proc/self/cgroup' else original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', read)
    return group


def test_membership_and_limit_are_verified_from_kernel_not_environment(monkeypatch, tmp_path):
    membership(monkeypatch, tmp_path)
    result = memory.current_envelope()
    assert result['status'] == 'PASS' and result['limit_bytes'] == 12 * 1024 ** 3
    assert result['observed']['memory.peak'] == 8 * 1024 ** 2


def test_wrong_actual_group_refuses_even_with_valid_environment_and_counters(monkeypatch, tmp_path):
    membership(monkeypatch, tmp_path, actual='other-group')
    with pytest.raises(ValueError, match='membership_mismatch'):
        memory.current_envelope()


def test_missing_scope_never_falls_back_to_per_process_rlimit(monkeypatch):
    monkeypatch.delenv(memory.CGROUP_ENV, raising=False)
    with pytest.raises(ValueError, match='unestablished'):
        memory.current_envelope()


def test_missing_memory_controller_stops_before_creating_workload_group(tmp_path):
    (tmp_path / 'cgroup.subtree_control').write_text('cpu pids')
    group = memory.MemoryGroup(memory.MEMORY_BYTES, root=tmp_path)
    with pytest.raises(ValueError, match='controller_unavailable'):
        with group:
            pytest.fail('workload launched without a controller')
    assert not group.path.exists()


def test_new_group_explicitly_restores_worker_readability_after_restrictive_umask(tmp_path, monkeypatch):
    (tmp_path / 'cgroup.subtree_control').write_text('memory')
    group = memory.MemoryGroup(memory.MEMORY_BYTES, root=tmp_path)
    original_mkdir, original_stat = Path.mkdir, Path.stat
    modes, removed = [], []
    def mkdir(path, *args, **kwargs):
        original_mkdir(path, *args, **kwargs)
        if path == group.path:
            for name in ('memory.max', 'memory.swap.max', 'memory.oom.group', 'memory.peak'):
                (path / name).write_text('0')
            (path / 'memory.events').write_text('max 0\noom 0\noom_kill 0')
            (path / 'cgroup.kill').write_text('')
            (path / 'cgroup.procs').write_text('')
    monkeypatch.setattr(Path, 'mkdir', mkdir)
    monkeypatch.setattr(Path, 'chmod', lambda path, mode: modes.append((path, mode)))
    def stat(path, *args, **kwargs):
        if path == group.path:
            return SimpleNamespace(st_mode=0o40755 if modes == [(path, 0o755)] else 0o40700)
        return original_stat(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'stat', stat)
    monkeypatch.setattr(Path, 'rmdir', lambda path: removed.append(path))
    with group:
        assert modes == [(group.path, 0o755)]
        assert memory.snapshot(group.path)['memory.max'] == memory.MEMORY_BYTES
    assert removed == [group.path]


def test_worker_enters_group_before_dropping_privileges(monkeypatch, tmp_path):
    group = tmp_path / 'group'
    group.mkdir()
    calls = []
    original = Path.write_text
    def write(path, value, *args, **kwargs):
        calls.append((path.name, value))
        if str(path).replace('\\', '/') == '/proc/self/oom_score_adj':
            return 1
        return original(path, value, *args, **kwargs)
    monkeypatch.setattr(Path, 'write_text', write)
    for name in ('setgroups', 'setgid', 'setuid'):
        monkeypatch.setattr(memory.os, name, lambda value, name=name: calls.append((name, value)), raising=False)
    monkeypatch.setattr(memory.os, 'geteuid', lambda: 1234, raising=False)
    monkeypatch.setattr(memory.os, 'getegid', lambda: 1235, raising=False)
    memory.enter_worker(group, 1234, 1235)
    assert [call[0] for call in calls] == ['cgroup.procs', 'oom_score_adj', 'setgroups', 'setgid', 'setuid']
    assert calls[-3:] == [('setgroups', []), ('setgid', 1235), ('setuid', 1234)]


@pytest.mark.parametrize('timeout,exit_code,oom', [(False, 0, 0), (False, -9, 1), (True, -9, 0)])
def test_supervisor_preserves_actual_kernel_outcome_and_timeout(tmp_path, monkeypatch, timeout, exit_code, oom):
    measured = values()
    measured['memory.events']['oom_kill'] = oom
    group_path = files(tmp_path / 'group', measured)
    closed = []
    class Group:
        path = group_path
        def __init__(self, limit):
            assert limit == memory.MEMORY_BYTES
        def __enter__(self):
            return self
        def __exit__(self, *_):
            closed.append(True)
    class Process:
        calls = 0
        def __init__(self, command, **kwargs):
            assert command == ['synthetic-command']
            assert kwargs['env'][memory.CGROUP_ENV] == str(group_path)
            kwargs['preexec_fn']()
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def wait(self, **kwargs):
            self.calls += 1
            if timeout and self.calls == 1:
                raise memory.subprocess.TimeoutExpired('synthetic', 1)
            return exit_code
    joined = []
    monkeypatch.setattr(memory, 'MemoryGroup', Group)
    monkeypatch.setattr(memory, 'enter_worker', lambda *args: joined.append(args))
    monkeypatch.setattr(memory.subprocess, 'Popen', Process)
    result = memory.run_group(['synthetic-command'], memory.MEMORY_BYTES, 1234, 1235, 1,
                              cwd=tmp_path, environment={})
    assert result['status'] == ('PASS' if not timeout and not oom else 'FAIL')
    assert result['returncode'] == exit_code and result['timed_out'] == timeout
    assert result['observed'] == measured and closed == [True]
    assert joined == [(group_path, 1234, 1235)]
    assert (group_path / 'cgroup.kill').read_text() == ('1' if timeout else '')


@pytest.mark.parametrize('fault', ['clean_exit', 'no_oom', 'timeout'])
def test_native_over_limit_control_requires_actual_oom_evidence(monkeypatch, fault):
    low = {'status': 'PASS'}
    high = {'status': 'FAIL', 'timed_out': False, 'returncode': -9,
            'observed': {'memory.events': {'oom_kill': 1}}}
    if fault == 'clean_exit':
        high['returncode'] = 0
    elif fault == 'no_oom':
        high['observed']['memory.events']['oom_kill'] = 0
    else:
        high['timed_out'] = True
    responses = iter([low, high])
    monkeypatch.setattr(memory, 'run_group', lambda *args, **kwargs: next(responses))
    with pytest.raises(ValueError, match='process_tree_limit_control_failed'):
        memory.native_controls(1234, 1235, environment={})


def test_restored_accept_all_defect_fails_peak_control_and_unrelated_membership_still_refuses(monkeypatch, tmp_path):
    with monkeypatch.context() as changed:
        changed.setattr(memory, 'accepted', lambda *args: True)
        with pytest.raises(AssertionError):
            test_limit_peak_and_oom_are_independent_fail_closed_checks('memory.peak', memory.MEMORY_BYTES + 1)
        test_wrong_actual_group_refuses_even_with_valid_environment_and_counters(changed, tmp_path)
    test_limit_peak_and_oom_are_independent_fail_closed_checks('memory.peak', memory.MEMORY_BYTES + 1)


@pytest.mark.parametrize('outcome', ['pass', 'oom', 'incomplete', 'missing'])
def test_main_keeps_outside_receipt_and_requires_bound_complete_benchmark(tmp_path, monkeypatch, outcome):
    workspace = tmp_path / 'synthetic-compaction-stress'
    age = tmp_path / 'age'
    age.write_bytes(b'public test executable placeholder; never executed')
    monkeypatch.setattr(memory.sys, 'platform', 'linux')
    monkeypatch.setattr(memory.sys, 'version_info', (3, 12, 14))
    monkeypatch.setattr(memory.os, 'geteuid', lambda: 0, raising=False)
    monkeypatch.setattr(memory.os, 'fchmod', lambda *_: None, raising=False)
    ownership = []
    monkeypatch.setattr(memory.os, 'fchown', lambda *args: ownership.append(args[1:]), raising=False)
    monkeypatch.setattr(memory.os, 'chown', lambda *args: ownership.append(args[1:]), raising=False)
    monkeypatch.setitem(sys.modules, 'pwd', SimpleNamespace(getpwuid=lambda _: SimpleNamespace(pw_dir='/home/runner')))
    monkeypatch.setattr(memory.time, 'time', lambda: 2000)
    monkeypatch.setattr(memory, 'native_controls', lambda *args, **kwargs: {'status': 'PASS'})
    def run(command, limit, uid, gid, seconds, **kwargs):
        assert limit == memory.MEMORY_BYTES and (uid, gid) == (1234, 1235)
        assert '--representative' in command and '--setup-seconds' in command
        assert seconds == 4500 - 30 - 10
        env = kwargs['environment']
        assert env['HOME'] == '/home/runner'
        assert Path(env['MPLCONFIGDIR']).parent == tmp_path / 'runtime-cache'
        assert Path(env['XDG_CACHE_HOME']).parent == tmp_path / 'runtime-cache'
        workspace.mkdir()
        if outcome != 'missing':
            status = 'FAIL' if outcome == 'incomplete' else 'PASS'
            (workspace / 'benchmark-result.json').write_bytes(json.dumps({
                'status': status, 'case': 'stress', 'checkout_sha': 'a' * 40}).encode())
        return {'status': 'FAIL' if outcome == 'oom' else 'PASS', 'reason': 'synthetic_oom'}
    monkeypatch.setattr(memory, 'run_group', run)
    code = memory.main(['--case', 'stress', '--workspace', str(workspace), '--age', str(age),
                        '--uid', '1234', '--gid', '1235', '--setup-start', '1990'])
    receipt = json.loads((tmp_path / 'memory-envelope.json').read_bytes())
    assert code == (0 if outcome == 'pass' else 2)
    assert receipt['status'] == ('PASS' if outcome == 'pass' else 'FAIL')
    assert ownership == [(1234, 1235), (1234, 1235)]
    if outcome != 'missing':
        import hashlib
        assert receipt['benchmark_result_sha256'] == hashlib.sha256((workspace / 'benchmark-result.json').read_bytes()).hexdigest()
        assert receipt['benchmark_checkout_sha'] == 'a' * 40
    assert receipt['provider_requests'] == 0 and not receipt['release_authorized']
