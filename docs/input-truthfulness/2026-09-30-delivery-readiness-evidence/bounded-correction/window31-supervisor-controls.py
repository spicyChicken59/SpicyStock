"""Three non-compression controls for the external Windows supervisor."""
import ctypes as C
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

work = Path(__file__).resolve().parent
path = work / "window31_comparison_supervisor.py"
spec = importlib.util.spec_from_file_location("supervisor", path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
out = work / "window31-supervisor-controls"
out.mkdir(mode=0o700)
before = hashlib.sha256(path.read_bytes()).hexdigest()
k, ps = m.winapi()
cap = 64 * 1024 ** 2
cases = [
    ("smoke", "from pathlib import Path;import sys;Path(sys.argv[1]).write_text('PASS')", 5, 0),
    ("memory", "from pathlib import Path\nimport sys\ntry:\n x=bytearray(256*1024**2)\nexcept MemoryError:\n Path(sys.argv[1]).write_text('allocation_refused')\nelse:\n sys.exit(3)", 5, 0),
    ("watchdog", "import time;time.sleep(5)", 0.25, 124),
]
rows = []
for name, code, limit, expected in cases:
    job = process = None
    pi = m.ProcessInformation()
    row = {"name": name, "status": "FAIL"}
    try:
        job = k.CreateJobObjectW(None, None)
        m.check(job, "create_job")
        limits = m.ExtendedLimit()
        limits.basic.flags, limits.basic.active_processes = m.LIMIT_FLAGS, 2
        limits.process_memory = limits.job_memory = cap
        m.check(k.SetInformationJobObject(job, 9, C.byref(limits), C.sizeof(limits)), "set_limits")
        readback = m.ExtendedLimit()
        m.check(k.QueryInformationJobObject(job, 9, C.byref(readback), C.sizeof(readback), None), "readback")
        m.require(readback.basic.flags == m.LIMIT_FLAGS and readback.process_memory == cap and readback.job_memory == cap,
                  "limit_readback_mismatch")
        si = m.Startup(); si.cb = C.sizeof(si)
        command = C.create_unicode_buffer(subprocess.list2cmdline([sys._base_executable, "-I", "-S", "-B", "-c", code, str(out / (name + '.txt'))]))
        env = C.create_unicode_buffer('SYSTEMROOT=C:\\Windows\0NO_COLOR=1\0\0')
        m.check(k.CreateProcessW(sys._base_executable, command, None, None, False, 4|0x400|0x08000000,
                                env, str(out), C.byref(si), C.byref(pi)), "create_suspended")
        process = pi.process
        m.check(k.AssignProcessToJobObject(job, process), "assign")
        inside=m.W.BOOL()
        m.check(k.IsProcessInJob(process, job, C.byref(inside)), "verify_assignment")
        m.require(inside.value, "assignment_missing")
        start = time.monotonic()
        m.require(k.ResumeThread(pi.thread) == 1, "resume_failed")
        while k.WaitForSingleObject(process, 10) != 0:
            if time.monotonic() - start >= limit:
                m.check(k.TerminateJobObject(job, 124), "watchdog_terminate")
                m.require(k.WaitForSingleObject(process, 5000) == 0, "termination_failed")
                break
        exit_code=m.W.DWORD()
        m.check(k.GetExitCodeProcess(process, C.byref(exit_code)), "exit_code")
        final=m.ExtendedLimit()
        m.check(k.QueryInformationJobObject(job, 9, C.byref(final), C.sizeof(final), None), "final_accounting")
        mem=m.MemoryCounters();mem.cb=C.sizeof(mem)
        queried=bool(ps.GetProcessMemoryInfo(process, C.byref(mem), C.sizeof(mem)))
        row.update(exit_code=exit_code.value, expected_exit=expected, wall_seconds=time.monotonic()-start,
                   process_commit_limit_bytes=cap, job_commit_limit_bytes=cap,
                   peak_process_commit_bytes=final.peak_process_memory, peak_job_commit_bytes=final.peak_job_memory,
                   native_peak_rss_bytes=mem.peak_rss if queried else None, final_memory_query_succeeded=queried,
                   assignment_before_resume=True)
        m.require(exit_code.value == expected and max(final.peak_process_memory,final.peak_job_memory) <= cap,
                  "control_result_mismatch")
        if name != 'watchdog':
            m.require((out/(name+'.txt')).read_text() == ('allocation_refused' if name=='memory' else 'PASS'), 'control_output_mismatch')
        row['status']='PASS'
    except BaseException as error:
        row['reason']=str(error) if isinstance(error,m.Refused) else type(error).__name__
    finally:
        if job:
            k.TerminateJobObject(job, 125)
        for handle in (pi.thread, process, job):
            if handle: k.CloseHandle(handle)
    rows.append(row)
after=hashlib.sha256(path.read_bytes()).hexdigest()
receipt={'schema':'historical-window31-supervisor-controls-v1','status':'PASS' if before==after and all(r['status']=='PASS' for r in rows) else 'FAIL',
         'supervisor_sha256_before':before,'supervisor_sha256_after':after,'controls':rows,'compression':'NOT RUN','keys':'NOT RUN','provider_requests':0,
         'documentation':m.DOCS}
(out/'controls.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
print(json.dumps(receipt,sort_keys=True))
raise SystemExit(0 if receipt['status']=='PASS' else 1)
