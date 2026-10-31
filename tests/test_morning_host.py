"""Offline runtime boundaries; real subprocesses never invoke provider code."""
import json
import os
from pathlib import Path
import signal
import sqlite3
import stat
import subprocess
import sys
import threading
import time

import pytest

from src import morning_host as host
from src import morning_host_wsgi as wsgi


def environment(**extra):
    return {
        'PORT': '8080', 'ALPACA_API_KEY': 'test-public-marker',
        'ALPACA_SECRET_KEY': 'test-private-marker', 'RAILWAY_TOKEN': 'test-platform-marker',
        'OPENAI_API_KEY': 'test-unrelated-marker', 'PYTHONPATH': '/untrusted',
        'PYTHONSTARTUP': '/untrusted', 'GUNICORN_CMD_ARGS': '--daemon',
        'HTTP_PROXY': 'http://proxy.invalid', 'HTTPS_PROXY': 'http://proxy.invalid',
        'NO_PROXY': 'localhost', 'REQUESTS_CA_BUNDLE': '/test/ca.pem',
        'SSL_CERT_FILE': '/test/ca.pem', **extra,
    }


@pytest.mark.parametrize('port', ['', '0', '65536', '-1', '8080x', ' 8080', '1\n', '８０８０', '1' * 1000])
def test_invalid_port_refused_without_echo(port):
    with pytest.raises(host.HostError, match='^invalid_port$'):
        host.configuration(environment(PORT=port))


def test_explicit_enable_and_complete_credential_pair():
    assert host.configuration(environment()) == (8080, False)
    assert host.configuration(environment(MORNING_WORKER_ENABLED='true')) == (8080, True)
    for enabled in ('TRUE', '1', '', 'yes'):
        with pytest.raises(host.HostError, match='invalid_worker_enable_flag'):
            host.configuration(environment(MORNING_WORKER_ENABLED=enabled))
    for missing in host.CREDENTIALS:
        for value in ('', ' \t'):
            with pytest.raises(host.HostError, match='worker_credentials_missing'):
                host.configuration(environment(MORNING_WORKER_ENABLED='true', **{missing: value}))


def test_only_worker_inherits_provider_pair_and_network_configuration():
    source = environment(MORNING_WORKER_ENABLED='true')
    specifications = host.jobs(8080, True, source)
    assert [(job.name, job.uid, job.interval) for job in specifications] == [
        ('http', 10002, None), ('sync', 10001, 300), ('worker', 10001, 30)]
    for job in specifications:
        for key in ('RAILWAY_TOKEN', 'OPENAI_API_KEY', 'PYTHONPATH', 'PYTHONSTARTUP', 'GUNICORN_CMD_ARGS'):
            assert key not in job.environment
        for key in host.NETWORK_ENV:
            if key in source:
                assert job.environment[key] == source[key]
        for key in host.CREDENTIALS:
            assert (key in job.environment) == (job.name == 'worker')
    assert [job.name for job in host.jobs(8080, False, source)] == ['http', 'sync']
    assert specifications[0].command[-1] == 'src.morning_host_wsgi:app'
    assert specifications[1].command[-1] == '/srv/spicystock/morning.sqlite'
    assert specifications[2].command[-1] == '/srv/spicystock/morning.sqlite'


def test_launch_drops_supplementary_groups_and_all_inherited_streams(monkeypatch):
    seen = {}
    def popen(command, **kwargs):
        seen.update(command=command, **kwargs)
        return 'child'
    monkeypatch.setattr(host.subprocess, 'Popen', popen)
    job = host.jobs(8080, False, environment())[0]
    assert host.launch(job) == 'child'
    assert seen['user'] == 10002 and seen['group'] == 10000
    assert seen['extra_groups'] == []
    assert seen['umask'] == 0o027 and seen['start_new_session'] is True
    assert seen['close_fds'] is True
    assert seen['stdin'] == seen['stdout'] == seen['stderr'] == subprocess.DEVNULL
    assert seen['env'] == job.environment


def invoke(app, path='/healthz', **changes):
    seen = {}
    env = {'REQUEST_METHOD': 'GET', 'PATH_INFO': path, 'QUERY_STRING': '', 'CONTENT_LENGTH': '', **changes}
    def start(status, headers):
        seen.update(status=status, headers=dict(headers))
    seen['body'] = b''.join(app(env, start))
    return seen


def test_health_is_only_liveness_and_never_reads_database_or_collects():
    def forbidden(*_):
        pytest.fail('health request touched receipt reader')
    response = invoke(wsgi.create_app(forbidden))
    assert response['status'] == '200 OK'
    assert json.loads(response['body']) == {'status': 'alive', 'scope': 'process_liveness_only'}
    assert response['headers']['Cache-Control'] == 'no-store'
    assert int(response['headers']['Content-Length']) == len(response['body'])


@pytest.mark.parametrize('changes,status', [
    ({'REQUEST_METHOD': 'POST'}, '405'),
    ({'REQUEST_METHOD': 'HEAD'}, '405'),
    ({'QUERY_STRING': 'collect=true'}, '400'),
    ({'CONTENT_LENGTH': '1'}, '400'),
    ({'CONTENT_LENGTH': '00'}, '400'),
    ({'HTTP_TRANSFER_ENCODING': 'chunked'}, '400'),
])
def test_health_refuses_methods_query_and_body(changes, status):
    assert invoke(wsgi.create_app(lambda *_: pytest.fail('reader called')), **changes)['status'].startswith(status)


def test_missing_receipt_is_503_while_health_is_200_and_origin_is_fixed(tmp_path):
    from src.morning_service import application
    database = tmp_path / 'absent.sqlite'
    app = wsgi.create_app(application(database, allowed_origin=wsgi.ALLOWED_ORIGIN))
    assert invoke(app)['status'] == '200 OK'
    receipt = invoke(app, '/morning.json', HTTP_ORIGIN='https://spicychicken59.github.io')
    assert receipt['status'].startswith('503')
    assert receipt['headers']['Access-Control-Allow-Origin'] == 'https://spicychicken59.github.io'
    assert 'Access-Control-Allow-Origin' not in invoke(app, '/morning.json', HTTP_ORIGIN='https://wrong.invalid')['headers']
    assert not database.exists()


def mount_line(path):
    return '123 1 0:42 / ' + str(path).replace('\\', r'\134').replace(' ', r'\040') + ' rw - ext4 /dev/volume rw\n'


def test_mount_check_requires_exact_kernel_mount_including_bind_or_escaped_path(tmp_path):
    path = tmp_path / 'with space'
    assert host._mounted(path, mount_line(path))
    assert not host._mounted(path / 'child', mount_line(path))
    assert not host._mounted(path, mount_line(tmp_path))
    assert not host._mounted(path, str(path))


@pytest.mark.parametrize('filesystem', ['tmpfs', 'ramfs', 'overlay', 'nfs', 'nfs4', 'cifs', 'unknown'])
def test_ephemeral_or_network_filesystem_refused(tmp_path, filesystem):
    assert not host._mounted(tmp_path, mount_line(tmp_path).replace('ext4', filesystem))


def test_symlink_in_directory_chain_refused(tmp_path):
    real = tmp_path / 'real'
    real.mkdir()
    alias = tmp_path / 'alias'
    alias.symlink_to(real, target_is_directory=True)
    with pytest.raises(OSError):
        host._directory(alias)
    with pytest.raises(OSError):
        host._directory(alias / 'nested')


def test_mount_and_root_refusal_precede_database_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(host.os, 'geteuid', lambda: 0)
    with pytest.raises(host.HostError, match='durable_mount_required'):
        host.prepare_volume(tmp_path, mountinfo='')
    assert list(tmp_path.iterdir()) == []
    monkeypatch.setattr(host.os, 'geteuid', lambda: 1000)
    with pytest.raises(host.HostError, match='root_launcher_required'):
        host.prepare_volume(tmp_path, mountinfo=mount_line(tmp_path))
    assert list(tmp_path.iterdir()) == []


def _launch_local(job):
    return subprocess.Popen(job.command, env=job.environment, start_new_session=True,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _local_job(name, source, interval=None):
    return host.Job(name, (sys.executable, '-c', source), os.getuid(),
                    {'PATH': os.environ.get('PATH', '/usr/bin:/bin')}, interval)


def _until(predicate, seconds=4):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    pytest.fail('bounded local subprocess did not reach expected state')


def _written_pid(path):
    """The pid a child wrote to `path`, once it is there: write_text() creates
    the file before it writes, so a file that merely exists can still read
    empty (CI, 31 Oct 2026: int('') on a loaded runner)."""
    _until(lambda: path.exists() and path.read_text().strip().isdigit())
    return int(path.read_text())


def _cleanup(supervisor):
    if supervisor.active:
        def clean():
            supervisor.step(stopping=True)
            return not supervisor.active
        _until(clean)


def test_independent_schedules_skip_catchup_and_do_not_overlap(tmp_path, monkeypatch):
    monkeypatch.setattr(host, 'KILL_GRACE_SECONDS', 0.03)
    now = [0.0]
    starts = []
    def launch(job):
        starts.append((job.name, now[0]))
        return _launch_local(job)
    supervisor = host.Supervisor([
        _local_job('sync', 'import time; time.sleep(60)', 300),
        _local_job('worker', 'import time; time.sleep(60)', 30),
    ], launcher=launch, clock=lambda: now[0], reporter=lambda *_: None)
    try:
        supervisor.step()
        now[0] = 31
        supervisor.step()
        assert starts == [('sync', 0), ('worker', 0)]
        # Finishing a late worker permits one next run while the sync stays up.
        active = supervisor.active['worker']
        os.killpg(active.process.pid, signal.SIGTERM)
        active.process.wait(timeout=2)
        supervisor.step()
        assert starts == [('sync', 0), ('worker', 0), ('worker', 31)]
        now[0] = 1000
        supervisor.step()
        assert len(starts) == 3  # late running groups stop before any restart
        for active in supervisor.active.values():
            active.process.wait(timeout=2)
        now[0] = 1001
        _until(lambda: (supervisor.step(), len(starts) == 5)[1])
        supervisor.step()
        assert starts[-2:] == [('sync', 1001), ('worker', 1001)]
        assert len(starts) == 5
    finally:
        _cleanup(supervisor)


def test_deadline_kills_and_reaps_ignoring_parent_and_child(tmp_path, monkeypatch):
    host.enable_subreaper()
    monkeypatch.setattr(host, 'COMMAND_SECONDS', 0.2)
    monkeypatch.setattr(host, 'KILL_GRACE_SECONDS', 0.08)
    ready = tmp_path / 'ready'
    source = (
        "import os,signal,time; from pathlib import Path;"
        "signal.signal(signal.SIGTERM,signal.SIG_IGN); child=os.fork();"
        f"Path({str(ready)!r}).write_text(str(os.getpid())) if child==0 else None;"
        "time.sleep(60)"
    )
    events = []
    supervisor = host.Supervisor([_local_job('worker', source, 30)],
                                 launcher=_launch_local, reporter=lambda *event: events.append(event))
    started = time.monotonic()
    try:
        supervisor.step()
        process = supervisor.active['worker'].process
        descendant = _written_pid(ready)
        _until(lambda: (supervisor.step(), not supervisor.active)[1])
        assert process.returncode == -signal.SIGKILL
        assert not Path(f'/proc/{descendant}').exists()
        assert not host._group_exists(process)
        assert time.monotonic() - started < 2
        assert ('worker', 'deadline', None) in events
    finally:
        _cleanup(supervisor)


def test_normal_parent_exit_cannot_leave_descendant_or_start_overlap(tmp_path, monkeypatch):
    host.enable_subreaper()
    monkeypatch.setattr(host, 'KILL_GRACE_SECONDS', 0.05)
    ready = tmp_path / 'orphan'
    source = (
        "import os,signal,time; from pathlib import Path; child=os.fork();"
        f"Path({str(ready)!r}).write_text(str(os.getpid())) if child==0 else None;"
        "time.sleep(60) if child==0 else None"
    )
    supervisor = host.Supervisor([_local_job('sync', source, 300)],
                                 launcher=_launch_local, reporter=lambda *_: None)
    try:
        supervisor.step()
        process = supervisor.active['sync'].process
        descendant = _written_pid(ready)
        _until(lambda: (supervisor.step(), not supervisor.active)[1])
        assert process.returncode == 0
        assert not host._group_exists(process)
        assert not Path(f'/proc/{descendant}').exists()
    finally:
        _cleanup(supervisor)


def test_http_exit_fails_host_and_reaps_other_roles(monkeypatch):
    monkeypatch.setattr(host, 'KILL_GRACE_SECONDS', 0.03)
    supervisor = host.Supervisor([
        _local_job('http', 'raise SystemExit(0)'),
        _local_job('sync', 'import time; time.sleep(60)', 300),
    ], launcher=_launch_local, reporter=lambda *_: None)
    assert supervisor.run(threading.Event()) == 1
    assert supervisor.active == {}


def test_shutdown_reaps_groups_without_starting_another_job(tmp_path, monkeypatch):
    monkeypatch.setattr(host, 'KILL_GRACE_SECONDS', 0.03)
    stop = threading.Event()
    launched = []
    def launcher(job):
        process = _launch_local(job)
        launched.append(process)
        stop.set()
        return process
    supervisor = host.Supervisor([_local_job('http', 'import time; time.sleep(60)')],
                                 launcher=launcher, reporter=lambda *_: None)
    assert supervisor.run(stop) == 0
    assert len(launched) == 1
    assert launched[0].poll() is not None
    assert not host._group_exists(launched[0])


@pytest.mark.skipif(os.geteuid() != 0, reason='real UID boundary requires the root container launcher')
def test_root_volume_lock_preserves_database_and_reader_cannot_write(tmp_path):
    # Parent paths need traversal for both dropped UIDs inside the test image.
    for path in (tmp_path.parent.parent, tmp_path.parent, tmp_path):
        path.chmod(0o755)
    volume = tmp_path / 'volume'
    volume.mkdir()
    database = volume / 'morning.sqlite'
    with sqlite3.connect(database) as db:
        db.execute('CREATE TABLE sentinel(value TEXT)')
        db.execute("INSERT INTO sentinel VALUES ('preserved')")
    database.chmod(0o600)
    before = database.read_bytes()
    lock = host.prepare_volume(volume, mountinfo=mount_line(volume))
    try:
        assert database.read_bytes() == before
        assert (database.stat().st_uid, database.stat().st_gid, stat.S_IMODE(database.stat().st_mode)) == (10001, 10000, 0o640)
        assert (volume.stat().st_uid, volume.stat().st_gid, stat.S_IMODE(volume.stat().st_mode)) == (10001, 10000, 0o750)
        with pytest.raises(host.HostError, match='volume_already_in_use'):
            host.prepare_volume(volume, mountinfo=mount_line(volume))
        source = (
            "import os,sqlite3; from pathlib import Path;"
            f"p=Path({str(database)!r});"
            "db=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True);"
            "assert db.execute('select value from sentinel').fetchone()[0]=='preserved';"
            "assert os.getgroups()==[];"
            "\ntry: p.write_bytes(b'wrong')\nexcept PermissionError: pass\nelse: raise AssertionError('reader wrote database')"
            f"\ntry: Path({str(volume / 'new')!r}).touch()\nexcept PermissionError: pass\nelse: raise AssertionError('reader wrote directory')"
        )
        result = subprocess.run([sys.executable, '-c', source], user=10002, group=10000, extra_groups=[],
                                env=host.child_environment(environment()), capture_output=True, timeout=5)
        assert result.returncode == 0, 'actual reader UID boundary failed'
        assert database.read_bytes() == before
    finally:
        os.close(lock)
    lock = host.prepare_volume(volume, mountinfo=mount_line(volume))
    os.close(lock)
    assert database.read_bytes() == before


@pytest.mark.skipif(os.geteuid() != 0, reason='actual child UID and umask require container')
def test_actual_children_receive_only_role_environment_and_write_with_safe_umask(tmp_path):
    for path in (tmp_path.parent.parent, tmp_path.parent, tmp_path):
        path.chmod(0o755)
    exchange = tmp_path / 'exchange'
    exchange.mkdir(mode=0o777)
    exchange.chmod(0o777)
    source = environment(MORNING_WORKER_ENABLED='true')
    for original in host.jobs(8080, True, source):
        output = exchange / original.name
        script = (
            "import json,os; from pathlib import Path;"
            f"Path({str(output)!r}).write_text(json.dumps("
            "{'uid':os.getuid(),'gid':os.getgid(),'groups':os.getgroups(),'environment':dict(os.environ)}))"
        )
        job = host.Job(original.name, (sys.executable, '-c', script), original.uid, original.environment)
        process = host.launch(job)
        assert process.wait(timeout=5) == 0
        observed = json.loads(output.read_text())
        assert observed['uid'] == (10002 if original.name == 'http' else 10001)
        assert observed['gid'] == 10000 and observed['groups'] == []
        assert stat.S_IMODE(output.stat().st_mode) == 0o640
        assert output.stat().st_uid == observed['uid']
        for credential in host.CREDENTIALS:
            assert (credential in observed['environment']) == (original.name == 'worker')
        for excluded in ('RAILWAY_TOKEN', 'OPENAI_API_KEY', 'PYTHONPATH', 'PYTHONSTARTUP', 'GUNICORN_CMD_ARGS'):
            assert excluded not in observed['environment']
        assert observed['environment']['HTTPS_PROXY'] == source['HTTPS_PROXY']
        assert observed['environment']['REQUESTS_CA_BUNDLE'] == source['REQUESTS_CA_BUNDLE']


@pytest.mark.skipif(os.geteuid() != 0, reason='real root-owned volume validation requires container')
@pytest.mark.parametrize('kind', ['symlink', 'hardlink', 'world_readable', 'foreign_file', 'bad_lock', 'writable_directory'])
def test_root_volume_refuses_unsafe_entries(tmp_path, kind):
    volume = tmp_path / 'volume'
    volume.mkdir()
    other = tmp_path / 'other'
    other.write_bytes(b'preserve')
    other.chmod(0o600)
    database = volume / 'morning.sqlite'
    if kind == 'symlink':
        database.symlink_to(other)
    elif kind == 'hardlink':
        os.link(other, database)
    elif kind == 'world_readable':
        database.write_bytes(b'preserve')
        database.chmod(0o644)
    elif kind == 'foreign_file':
        (volume / 'foreign').write_bytes(b'preserve')
    elif kind == 'bad_lock':
        (volume / '.runtime.lock').symlink_to(other)
    else:
        volume.chmod(0o777)
    with pytest.raises((host.HostError, OSError)):
        host.prepare_volume(volume, mountinfo=mount_line(volume))
    assert other.read_bytes() == b'preserve'
