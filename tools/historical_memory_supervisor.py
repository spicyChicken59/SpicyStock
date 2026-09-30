"""Linux-only memory boundary for the provider-free historical CI benchmark.

The small supervisor stays outside the workload cgroup to preserve an OOM
receipt. The benchmark and every descendant run as the ordinary runner user.
Only this supervisor needs root for a fresh cgroup; it never imports science,
package, credential or provider code. There is no RLIMIT_AS fallback.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

MEMORY_BYTES = 12 * 1024 ** 3
CONTROL_BYTES = 256 * 1024 ** 2
TOTAL_SECONDS = 4500
FINAL_RECEIPT_RESERVE_SECONDS = 30
CGROUP_ROOT = Path('/sys/fs/cgroup')
CGROUP_ENV = 'SPICYSTOCK_MEMORY_CGROUP'
SCRIPT_ROOT = Path(__file__).resolve().parents[1]


def require(value, reason):
    if not value:
        raise ValueError(reason)


def counters(path):
    rows = [line.split() for line in path.read_text(encoding='ascii').splitlines()]
    require(all(len(row) == 2 and row[1].isdigit() for row in rows), 'invalid_memory_events')
    result = {key: int(value) for key, value in rows}
    require(len(result) == len(rows) and {'oom', 'oom_kill', 'max'} <= result.keys(), 'incomplete_memory_events')
    return result


def snapshot(group):
    values = {name: int((group / name).read_text(encoding='ascii').strip())
              for name in ('memory.max', 'memory.swap.max', 'memory.oom.group', 'memory.peak')}
    require(all(value >= 0 for value in values.values()), 'invalid_memory_counter')
    return {**values, 'memory.events': counters(group / 'memory.events')}


def accepted(snapshot_value, limit, returncode=0):
    events = snapshot_value['memory.events']
    return (returncode == 0 and snapshot_value['memory.max'] == limit
            and snapshot_value['memory.swap.max'] == 0 and snapshot_value['memory.oom.group'] == 1
            and 0 < snapshot_value['memory.peak'] <= limit
            and events['oom'] == events['oom_kill'] == 0)


def current_envelope():
    """Verify the actual workload membership, not an environment-only assertion."""
    raw = os.environ.get(CGROUP_ENV, '')
    group = Path(raw)
    require(group.is_absolute() and group.parent == CGROUP_ROOT
            and group.name.startswith('spicystock-memory-') and not group.is_symlink(), 'memory_scope_unestablished')
    membership = Path('/proc/self/cgroup').read_text(encoding='ascii').splitlines()
    require('0::/' + group.name in membership, 'memory_scope_membership_mismatch')
    values = snapshot(group)
    require(values['memory.max'] == MEMORY_BYTES and values['memory.swap.max'] == 0
            and values['memory.oom.group'] == 1, 'memory_scope_limit_mismatch')
    require(accepted(values, MEMORY_BYTES), 'memory_scope_limit_exceeded')
    return {'status': 'PASS', 'mechanism': 'linux-cgroup-v2', 'limit_bytes': MEMORY_BYTES,
            'swap_limit_bytes': 0, 'observed': values,
            'scope': 'Benchmark process tree including descendants and charged cache/kernel memory. Supervisor and Actions runner are outside this workload group; final supervisor receipt is authoritative.'}


class MemoryGroup:
    def __init__(self, limit, *, root=CGROUP_ROOT):
        self.root, self.limit = root, limit
        self.path = root / ('spicystock-memory-' + uuid.uuid4().hex)

    def __enter__(self):
        require('memory' in (self.root / 'cgroup.subtree_control').read_text().split(), 'memory_controller_unavailable')
        self.path.mkdir(mode=0o755)
        try:
            # CI's umask077 also applies to root's mkdir. The dropped-UID
            # worker must be able to read its counters, never change limits.
            self.path.chmod(0o755)
            require(self.path.stat().st_mode & 0o777 == 0o755, 'memory_group_not_readable')
            require((self.path / 'cgroup.kill').is_file(), 'memory_group_kill_unavailable')
            for name, value in (('memory.max', self.limit), ('memory.swap.max', 0), ('memory.oom.group', 1)):
                (self.path / name).write_text(str(value), encoding='ascii')
            values = snapshot(self.path)
            require(values['memory.max'] == self.limit and values['memory.swap.max'] == 0
                    and values['memory.oom.group'] == 1, 'memory_limit_readback_mismatch')
            require(values['memory.peak'] == 0 and not any(values['memory.events'].values()), 'memory_group_not_fresh')
            return self
        except BaseException:
            self.path.rmdir()
            raise

    def __exit__(self, *_):
        # All children are ours. A failure must not leave descendants consuming
        # memory after their supervisor returned. Never touch another cgroup.
        if (self.path / 'cgroup.procs').read_text().strip():
            (self.path / 'cgroup.kill').write_text('1', encoding='ascii')
        for _ in range(100):
            if not (self.path / 'cgroup.procs').read_text().strip():
                break
            time.sleep(0.01)
        self.path.rmdir()


def enter_worker(group, uid, gid):
    (group / 'cgroup.procs').write_text(str(os.getpid()), encoding='ascii')
    Path('/proc/self/oom_score_adj').write_text('0', encoding='ascii')
    os.setgroups([])
    os.setgid(gid)
    os.setuid(uid)
    require(os.geteuid() == uid and os.getegid() == gid and uid != 0, 'worker_identity_not_dropped')


def run_group(command, limit, uid, gid, seconds, *, cwd, environment):
    require(seconds > 0, 'total_job_budget_exhausted')
    started = time.monotonic()
    with MemoryGroup(limit) as group:
        child_environment = {**environment, CGROUP_ENV: str(group.path)}
        with subprocess.Popen(command, cwd=cwd, env=child_environment,
                              preexec_fn=lambda: enter_worker(group.path, uid, gid)) as process:
            timed_out = False
            try:
                returncode = process.wait(timeout=seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                (group.path / 'cgroup.kill').write_text('1', encoding='ascii')
                returncode = process.wait(timeout=10)
            values = snapshot(group.path)
        result = {'status': 'PASS' if accepted(values, limit, returncode) and not timed_out else 'FAIL',
                  'limit_bytes': limit, 'returncode': returncode, 'timed_out': timed_out,
                  'seconds': round(time.monotonic() - started, 6), 'observed': values}
        if result['status'] != 'PASS':
            result['reason'] = ('total_job_deadline_exceeded' if timed_out else
                                'workload_memory_or_child_failure')
        return result


def native_controls(uid, gid, *, environment):
    """Small real kernel controls; no scientific data, encryption or provider."""
    touch = 'import time; x=bytearray(160*1024**2); x[::4096]=b"x"*(len(x)//4096); time.sleep(3)'
    aggregate = ('import subprocess,sys; c=' + repr(touch) + '; '
                 'p=[subprocess.Popen([sys.executable,"-I","-B","-c",c]) for _ in range(2)]; '
                 'sys.exit(max(x.wait() for x in p))')
    readable = ('import os; from pathlib import Path; '
                f'assert os.geteuid()=={uid} and os.geteuid()!=0; '
                'g=Path(os.environ["SPICYSTOCK_MEMORY_CGROUP"]); '
                f'assert int((g/"memory.max").read_text())=={CONTROL_BYTES}; '
                'assert int((g/"memory.swap.max").read_text())==0; '
                'assert int((g/"memory.oom.group").read_text())==1; '
                'assert int((g/"memory.peak").read_text())>0; '
                '(g/"memory.events").read_text(); '
                'assert "0::/"+g.name in Path("/proc/self/cgroup").read_text().splitlines(); '
                'x=bytearray(8*1024**2); x[0]=1')
    low = run_group([sys.executable, '-I', '-B', '-c', readable],
                    CONTROL_BYTES, uid, gid, 20, cwd=SCRIPT_ROOT, environment=environment)
    high = run_group([sys.executable, '-I', '-B', '-c', aggregate], CONTROL_BYTES, uid, gid, 20,
                     cwd=SCRIPT_ROOT, environment=environment)
    require(low['status'] == 'PASS', 'native_below_limit_control_failed')
    require(high['status'] == 'FAIL' and not high['timed_out'] and high['returncode'] != 0
            and high['observed']['memory.events']['oom_kill'] > 0, 'native_process_tree_limit_control_failed')
    return {'status': 'PASS', 'below_limit': low, 'aggregate_over_limit': high,
            'below_limit_counter_read_as_worker': True,
            'scope': 'Two160MiB children each fit256MiB individually; concurrent aggregate must OOM the256MiB group. No full benchmark or provider input.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('central', 'stress'), required=True)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--age', type=Path, required=True)
    parser.add_argument('--uid', type=int, required=True)
    parser.add_argument('--gid', type=int, required=True)
    parser.add_argument('--setup-start', type=int, required=True)
    args = parser.parse_args(argv)
    parent = args.workspace.absolute().parent
    receipt = {'schema': 'historical-memory-supervisor-v1', 'status': 'FAIL', 'case': args.case,
               'memory_limit_bytes': MEMORY_BYTES, 'swap_limit_bytes': 0,
               'provider_requests': 0, 'release_authorized': False,
               'scope': 'Kernel cgroup accounting for benchmark and descendants, including charged page cache/kernel memory; supervisor/Actions runner excluded.',
               'supervisor_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    # Keep the original descriptor, avoiding a privileged follow of a replaced
    # output pathname after the unprivileged workload has started.
    with (parent / 'memory-envelope.json').open('x', encoding='utf-8') as output:
        try:
            require(sys.platform == 'linux' and sys.version_info[:3] == (3, 12, 14), 'pinned_linux_runtime_required')
            require(os.geteuid() == 0 and args.uid > 0 and args.gid >= 0, 'root_setup_and_nonroot_worker_required')
            os.fchmod(output.fileno(), 0o600)
            os.fchown(output.fileno(), args.uid, args.gid)
            require(args.workspace.is_absolute() and not args.workspace.exists()
                    and args.workspace.name == 'synthetic-compaction-' + args.case, 'fresh_synthetic_workspace_required')
            require(args.age.is_absolute() and args.age.is_file(), 'verified_test_age_required')
            import pwd
            environment = dict(os.environ)
            environment['HOME'] = pwd.getpwuid(args.uid).pw_dir
            cache = parent / 'runtime-cache'
            cache.mkdir(mode=0o700)
            os.chown(cache, args.uid, args.gid)
            environment.update(MPLCONFIGDIR=str(cache / 'matplotlib'), XDG_CACHE_HOME=str(cache / 'xdg'))
            setup = time.time() - args.setup_start
            require(0 <= setup < TOTAL_SECONDS - FINAL_RECEIPT_RESERVE_SECONDS - 40, 'invalid_setup_clock')
            receipt['native_controls'] = native_controls(args.uid, args.gid, environment=environment)
            setup = time.time() - args.setup_start
            command = [sys.executable, '-I', '-B', str(SCRIPT_ROOT / 'tools/historical_projection_benchmark.py'),
                       '--case', args.case, '--workspace', str(args.workspace), '--age', str(args.age),
                       '--representative', '--setup-seconds', str(setup)]
            receipt['workload'] = run_group(command, MEMORY_BYTES, args.uid, args.gid,
                TOTAL_SECONDS - FINAL_RECEIPT_RESERVE_SECONDS - setup, cwd=SCRIPT_ROOT, environment=environment)
            receipt['status'] = receipt['workload']['status']
            receipt['setup_seconds_including_controls'] = round(setup, 6)
            result_path = args.workspace / 'benchmark-result.json'
            if result_path.is_file() and not result_path.is_symlink():
                with result_path.open('rb') as stream:
                    result_bytes = stream.read(1024 ** 2 + 1)
                require(len(result_bytes) <= 1024 ** 2, 'benchmark_result_exceeds_receipt_bound')
                result = json.loads(result_bytes)
                receipt.update(benchmark_result_sha256=hashlib.sha256(result_bytes).hexdigest(),
                               benchmark_checkout_sha=result.get('checkout_sha'))
                require(result.get('status') == 'PASS' and result.get('case') == args.case,
                        'benchmark_result_not_complete')
            else:
                raise ValueError('benchmark_result_missing')
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            receipt['status'] = 'FAIL'
            receipt['reason'] = str(error) if isinstance(error, ValueError) else type(error).__name__
        finally:
            output.write(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
            output.flush()
    print(json.dumps({'memory_supervisor_status': receipt['status'], 'case': args.case}), flush=True)
    return 0 if receipt['status'] == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
