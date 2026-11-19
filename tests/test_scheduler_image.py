"""The dispatcher's Railway target, and the workflows' Node 24 action pins.

What these hold: the scheduler's Dockerfile carries nothing Railway's builder
is known to refuse (the host Dockerfile's own rules), builds from the host's
pinned base, installs the one requirement under the constraints, copies only
the two files the dispatcher reads -- and those two import nothing else of
the repository -- and runs unprivileged as ``dispatch_schedule.py loop``;
``railway.json`` points at it with one replica, restarted always. And every
workflow's checkout and setup-python is the pinned Node 24 release. They do
not show that Railway builds it; only a deployment does.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from tests.test_host_dockerfile import has_directive, instructions, text_of

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "deploy" / "scheduler" / "Dockerfile"
RAILWAY = ROOT / "deploy" / "scheduler" / "railway.json"
#: the pinned releases, each read on 19 November 2026 to run on node24 (their action.yml `using:`)
CHECKOUT = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1"
SETUP_PYTHON = "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0"


def steps():
    return instructions(text_of(DOCKERFILE))


def test_the_scheduler_image_carries_nothing_railway_refuses():
    text = text_of(DOCKERFILE)
    assert not has_directive(text) and "/run/secrets" not in text
    assert not [i for i in steps() if "--mount" in i]
    assert not [i for i in steps() if i.split()[0].upper() == "VOLUME"]


def test_it_builds_from_the_hosts_pinned_base_and_installs_one_requirement_under_the_constraints():
    host_base = next(i for i in instructions(text_of()) if i.startswith("FROM "))
    assert steps()[0] == host_base and "@sha256:" in host_base
    assert "RUN python -m pip install --no-cache-dir -r requirements-scheduler.txt -c constraints.txt" in steps()
    wanted = [line for line in (ROOT / "requirements-scheduler.txt").read_text().splitlines()
              if line.strip() and not line.startswith("#")]
    pinned = (ROOT / "constraints.txt").read_text().splitlines()
    assert wanted == ["exchange_calendars==4.13.2"] and wanted[0] in pinned
    assert wanted[0] in (ROOT / "requirements.txt").read_text().splitlines()


def test_it_copies_only_what_the_dispatcher_imports_and_runs_unprivileged():
    copies = [i.split()[1:] for i in steps() if i.startswith("COPY ")]
    assert copies == [["requirements-scheduler.txt", "constraints.txt", "./"],
                      ["src/sessions.py", "./src/sessions.py"],
                      ["tools/dispatch_schedule.py", "./tools/dispatch_schedule.py"]]
    for source in ("src/sessions.py", "tools/dispatch_schedule.py"):
        tree = ast.parse((ROOT / source).read_text())
        local = {(n.module or "") for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | \
                {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        ours = {m for m in local if m.split(".")[0] in ("src", "tools")}
        imported = {f"src.{a.name}" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module == "src"
                    for a in n.names}
        assert ours <= {"src"} and imported <= {"src.sessions"}, (source, ours, imported)
    assert "USER dispatcher" in steps() and steps().index("USER dispatcher") < len(steps()) - 1
    assert steps()[-1] == 'ENTRYPOINT ["python", "tools/dispatch_schedule.py", "loop"]'


def test_railway_builds_that_file_with_one_replica_restarted_always():
    config = json.loads(RAILWAY.read_text())
    assert config["build"] == {"builder": "DOCKERFILE", "dockerfilePath": "deploy/scheduler/Dockerfile"}
    assert config["deploy"] == {"numReplicas": 1, "restartPolicyType": "ALWAYS"}
    assert (ROOT / config["build"]["dockerfilePath"]).is_file()


#: the one workflow whose bytes retained evidence pins (the native-5 secret-scan
#: disposition holds it to its public git blob), so it keeps its checkout until a
#: dated disposition moves it
PINNED_BYTES = {"secret-scan.yml": "actions/checkout@v4"}


def test_every_workflow_checks_out_and_sets_up_python_on_the_pinned_node24_release():
    uses = []
    for workflow in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        for line in workflow.read_text().splitlines():
            m = re.match(r"\s*(?:-\s*)?uses:\s*(actions/(?:checkout|setup-python)@.*)$", line)
            if m:
                uses.append((workflow.name, m.group(1).strip()))
    moved = {u for name, u in uses if name not in PINNED_BYTES}
    assert uses and moved == {CHECKOUT, SETUP_PYTHON}, sorted(moved)
    assert {(name, u) for name, u in uses if name in PINNED_BYTES} == set(PINNED_BYTES.items())


def test_the_workflow_kept_on_its_old_checkout_is_the_one_retained_evidence_pins():
    from tests import secret_scan_controls as controls
    assert set(PINNED_BYTES) == {Path(controls.NATIVE5_WORKFLOW).name}
    controls.native5_public_preservation()      # raises unless the file is still the retained blob


def test_the_operations_note_names_the_slots_the_tool_runs():
    from tools import dispatch_schedule as ds
    note = re.sub(r"\s+", " ", (ROOT / "docs" / "operations" / "external-scheduler.md").read_text())
    for workflow, inputs, zone, times in ds.SLOTS:
        when = ", ".join(times[:-1]) + (" and " if len(times) > 1 else "") + times[-1]
        assert f"| `{workflow}` | {when} {zone.key} |" in note, workflow
    assert f"for {ds.DUE_MINUTES} minutes (`DUE_MINUTES`)" in note
    assert "**Actions: Read and write**" in note and "`deploy/scheduler/railway.json`" in note
