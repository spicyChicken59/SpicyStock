"""Single-host production launcher; HTTP never starts collection.

The root launcher owns the volume lock and process groups. Fixed writer commands
run as a different UID from the public reader. No command or path is supplied by
an HTTP request or environment variable.
"""
from __future__ import annotations

from dataclasses import dataclass
import ctypes
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import threading
import time

VOLUME = Path('/srv/spicystock')
DATABASE = VOLUME / 'morning.sqlite'
APP_ROOT = Path(__file__).resolve().parents[1]
WRITER_UID = 10001
READER_UID = 10002
READ_GID = 10000
SYNC_SECONDS = 300
WORKER_SECONDS = 30
COMMAND_SECONDS = 45
KILL_GRACE_SECONDS = 5
POLL_SECONDS = 0.1
LOCAL_FILESYSTEMS = frozenset(('ext2', 'ext3', 'ext4', 'xfs', 'btrfs', 'zfs'))
NETWORK_ENV = (
    'HTTP_PROXY', 'HTTPS_PROXY', 'NO_PROXY',
    'http_proxy', 'https_proxy', 'no_proxy',
    'REQUESTS_CA_BUNDLE', 'SSL_CERT_FILE',
)
CREDENTIALS = ('ALPACA_API_KEY', 'ALPACA_SECRET_KEY')


class HostError(ValueError):
    """A fixed, credential-free refusal reason."""


def configuration(environ):
    port = environ.get('PORT', '')
    if not re.fullmatch(r'[0-9]{1,5}', port) or not 1 <= int(port) <= 65535:
        raise HostError('invalid_port')
    enabled = environ.get('MORNING_WORKER_ENABLED', 'false')
    if enabled not in ('true', 'false'):
        raise HostError('invalid_worker_enable_flag')
    if enabled == 'true' and any(not environ.get(name, '').strip() for name in CREDENTIALS):
        raise HostError('worker_credentials_missing')
    return int(port), enabled == 'true'


def child_environment(environ, *, worker=False):
    # Construct, never inherit: Python/gunicorn injection options and unrelated
    # application/provider credentials must not reach public or sync processes.
    result = {
        'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': '/tmp', 'LANG': 'C.UTF-8',
        'TZ': 'UTC', 'PYTHONUNBUFFERED': '1', 'PYTHONDONTWRITEBYTECODE': '1',
    }
    result.update({name: environ[name] for name in NETWORK_ENV if name in environ})
    if worker:
        result.update({name: environ[name] for name in CREDENTIALS})
    return result


def _mounted(path, mountinfo):
    # mountinfo includes bind mounts, unlike st_dev comparisons. Mount point
    # fields escape spaces, tabs, newlines and backslashes with octal sequences.
    for line in mountinfo.splitlines():
        fields = line.split()
        if len(fields) >= 10 and ' - ' in line:
            point = re.sub(r'\\([0-7]{3})', lambda match: chr(int(match[1], 8)), fields[4])
            filesystem = line.split(' - ', 1)[1].split()[0]
            if point == str(path) and filesystem in LOCAL_FILESYSTEMS:
                return True
    return False


def _directory(path):
    """Open each absolute component without following a symlink."""
    if not path.is_absolute() or '..' in path.parts:
        raise HostError('invalid_volume_path')
    descriptor = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for component in path.parts[1:]:
            following = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                dir_fd=descriptor)
            os.close(descriptor)
            descriptor = following
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def prepare_volume(path=VOLUME, *, mountinfo=None):
    """Validate a mounted volume and hold its lock; never recreate a database.

    Optional inputs are local test seams. The production launcher always uses
    the fixed mount and the kernel's actual mount table.
    """
    if os.geteuid() != 0:
        raise HostError('root_launcher_required')
    path = Path(path)
    if mountinfo is None:
        mountinfo = Path('/proc/self/mountinfo').read_text()
    if not _mounted(path, mountinfo):
        raise HostError('durable_mount_required')
    directory = _directory(path)
    lock = None
    try:
        info = os.fstat(directory)
        if info.st_uid not in (0, WRITER_UID) or info.st_gid not in (0, READ_GID):
            raise HostError('volume_owner_invalid')
        if stat.S_IMODE(info.st_mode) not in (0o700, 0o750, 0o755):
            raise HostError('volume_permissions_invalid')
        flags = os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW
        try:
            lock = os.open('.runtime.lock', flags | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=directory)
            os.fchmod(lock, 0o600)
        except FileExistsError:
            lock = os.open('.runtime.lock', flags, dir_fd=directory)
        info = os.fstat(lock)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != 0
                or info.st_gid != 0 or stat.S_IMODE(info.st_mode) != 0o600):
            raise HostError('volume_lock_invalid')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise HostError('volume_already_in_use') from None
        files = []
        for name in os.listdir(directory):
            if name == '.runtime.lock':
                continue
            info = os.stat(name, dir_fd=directory, follow_symlinks=False)
            if name == 'lost+found' and stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and stat.S_IMODE(info.st_mode) == 0o700:
                continue
            if (name not in ('morning.sqlite', 'morning.sqlite-journal', 'morning.sqlite-wal', 'morning.sqlite-shm')
                    or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or info.st_uid not in (0, WRITER_UID) or info.st_gid not in (0, READ_GID)
                    or stat.S_IMODE(info.st_mode) not in (0o600, 0o640)):
                raise HostError('volume_entry_invalid')
            files.append(name)
        # Validate the entire directory before changing existing file metadata.
        for name in files:
            descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory)
            try:
                os.fchown(descriptor, WRITER_UID, READ_GID)
                os.fchmod(descriptor, 0o640)
            finally:
                os.close(descriptor)
        os.fchown(directory, WRITER_UID, READ_GID)
        os.fchmod(directory, 0o750)
        return lock
    except BaseException:
        if lock is not None:
            os.close(lock)
        raise
    finally:
        os.close(directory)


@dataclass(frozen=True)
class Job:
    name: str
    command: tuple[str, ...]
    uid: int
    environment: dict
    interval: float | None = None


def jobs(port, enabled, environ):
    public = child_environment(environ)
    python = sys.executable
    result = [
        Job('http', (python, '-m', 'gunicorn', '--config', '/dev/null', '--bind', f'0.0.0.0:{port}',
                     '--workers', '1', '--threads', '2', '--timeout', '30', '--graceful-timeout', '5',
                     '--access-logfile', '/dev/null', '--error-logfile', '/dev/null',
                     'src.morning_host_wsgi:app'), READER_UID, public),
        Job('sync', (python, '-m', 'tools.sync_morning_service', '--database', str(DATABASE)),
            WRITER_UID, public.copy(), SYNC_SECONDS),
    ]
    if enabled:
        result.append(Job('worker', (python, '-m', 'src.morning_service_worker', '--database', str(DATABASE)),
                          WRITER_UID, child_environment(environ, worker=True), WORKER_SECONDS))
    return result


def launch(job):
    return subprocess.Popen(
        job.command, cwd=APP_ROOT, env=job.environment,
        user=job.uid, group=READ_GID, extra_groups=[], umask=0o027,
        start_new_session=True, close_fds=True,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def enable_subreaper():
    # Container PID 1 already adopts orphans; this also makes local subprocess
    # supervision reap orphaned grandchildren rather than leave zombie groups.
    if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) != 0:
        raise HostError('child_subreaper_unavailable')


def _signal_group(process, sig):
    try:
        os.killpg(process.pid, sig)
    except ProcessLookupError:
        pass


def _group_exists(process):
    try:
        os.killpg(process.pid, 0)
        return True
    except ProcessLookupError:
        return False


def _reap(process):
    if process.poll() is None:
        return
    # Only reap this role's adopted descendants. Popen owns the direct child.
    while True:
        try:
            pid, _ = os.waitpid(-process.pid, os.WNOHANG)
        except ChildProcessError:
            return
        if pid == 0:
            return


def emit(role, state, code=None):
    print(json.dumps({'role': role, 'state': state, 'exit_code': code}), flush=True)


@dataclass
class Active:
    process: subprocess.Popen
    started: float
    stopping: float | None = None
    killed: bool = False


class Supervisor:
    """Independent monotonic schedules, with one reaped process group per role."""

    def __init__(self, specifications, *, launcher=launch, clock=time.monotonic, reporter=emit):
        self.jobs = {job.name: job for job in specifications}
        self.launcher, self.clock, self.reporter = launcher, clock, reporter
        self.active = {}
        self.due = {job.name: 0.0 for job in specifications}
        self.failed = False

    def _stop(self, name, active, now, reason):
        if active.stopping is None:
            active.stopping = now
            _signal_group(active.process, signal.SIGTERM)
            self.reporter(name, reason, active.process.poll())

    def step(self, *, stopping=False, stop=None):
        now = self.clock()
        for name, active in list(self.active.items()):
            code = active.process.poll()
            if (code is not None and self.jobs[name].interval is None
                    and not stopping and active.stopping is None):
                self.failed = True
            if stopping or self.failed:
                self._stop(name, active, now, 'stopping')
            elif code is not None:
                self._stop(name, active, now, 'finished')
            elif self.jobs[name].interval is not None and now - active.started >= COMMAND_SECONDS:
                self._stop(name, active, now, 'deadline')
            if active.stopping is not None:
                if now - active.stopping >= KILL_GRACE_SECONDS and not active.killed:
                    _signal_group(active.process, signal.SIGKILL)
                    active.killed = True
                _reap(active.process)
                if active.process.poll() is not None and not _group_exists(active.process):
                    del self.active[name]
                elif now - active.stopping >= 2 * KILL_GRACE_SECONDS:
                    raise HostError('child_cleanup_failed')
        if stopping or self.failed:
            return
        for name, job in self.jobs.items():
            if stop is not None and stop.is_set():
                return
            if name not in self.active and now >= self.due[name]:
                process = self.launcher(job)
                self.active[name] = Active(process, now)
                # A delayed tick starts once, never replays missed invocations.
                self.due[name] = now + (job.interval or 0)
                self.reporter(name, 'started')

    def run(self, stop):
        try:
            while not stop.is_set() and not self.failed:
                self.step(stop=stop)
                stop.wait(POLL_SECONDS)
        finally:
            while self.active:
                self.step(stopping=True)
                stop.wait(POLL_SECONDS) if not stop.is_set() else time.sleep(POLL_SECONDS)
        return 1 if self.failed else 0


def main():
    lock = None
    previous = {}
    stop = threading.Event()
    try:
        port, enabled = configuration(os.environ)
        lock = prepare_volume()
        enable_subreaper()
        for sig in (signal.SIGTERM, signal.SIGINT):
            previous[sig] = signal.signal(sig, lambda *_: stop.set())
        return Supervisor(jobs(port, enabled, os.environ)).run(stop)
    except (HostError, OSError, subprocess.SubprocessError):
        # Never expose exception text: it can contain inherited secrets or paths.
        print('{"status":"refused","reason":"host_configuration_or_process_failure"}', flush=True)
        return 1
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        if lock is not None:
            os.close(lock)


if __name__ == '__main__':
    raise SystemExit(main())
