"""Every direct requirement a run installs is held below its next major, or
pinned, and constraints.txt pins the whole resolution under them: every
workflow step that installs requirements.txt installs `-r requirements.txt -c
constraints.txt`, and requirements-dev.txt carries the same -c line, so the
suite runs against the runtime set the evening installs. Every other pip
install a workflow runs reads a file this test accounts for: the historical
jobs' tools/requirements-historical*.txt, which pin their direct requirements
and leave the rest to float. requirements-host.txt pins the morning host's own.

PyPI is part of the environment: anthropic 2.0.0, published on 21 Oct 2026,
changed the API version the SDK sends and every chart read of two nights failed
with no change in this repository, and a package underneath one of these
(python-dateutil 3.0.0 under pandas) can arrive the same way. A bound or a pin
moves in its own change, with the suite run against it.
"""
import contextlib
from importlib import metadata
import io
import os
from pathlib import Path
import posixpath
import re
import shlex

import pytest
import yaml
from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]
LINE = re.compile(r"(?P<name>[A-Za-z0-9_.\-]+)\s*(?P<spec>.*)\Z")
PIN = re.compile(r"(?P<name>[A-Za-z0-9][A-Za-z0-9_.\-]*)==(?P<version>[0-9][A-Za-z0-9.+!\-]*)\Z")
# Every requirements file a workflow's pip install may read, and nothing else:
# the runtime set (with the constraints), the suite's (which carries them), and
# the historical jobs' own two, which this change leaves alone.
INSTALLABLE = {"requirements.txt", "requirements-dev.txt", "tools/requirements-historical.txt",
               "tools/requirements-historical-archive.txt"}
# The platform the pins were resolved for and every workflow step that installs
# them runs on: CPython 3.12 on Linux (held to the workflows below). Markers are
# read in it on any machine, so a dependency only Windows asks for (colorama
# under pytest) is never demanded of the file.
RUNNER = dict(default_environment(), sys_platform="linux", platform_system="Linux", os_name="posix",
              platform_machine="x86_64", implementation_name="cpython", platform_python_implementation="CPython",
              python_version="3.12", python_full_version="3.12.15", implementation_version="3.12.15")


def requirements(name):
    """The requirement lines of a requirements file: every spelling of an -r or
    -c option line is left to the install test; any other option line is read
    as a requirement, and the bounds test refuses it."""
    out = []
    for raw in (ROOT / name).read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if line and not line.startswith(("-r", "--requirement", "-c", "--constraint")):
            out.append(LINE.fullmatch(line).groupdict())
    return out


def constraints(text=None):
    """{canonical name: (name as written, version)} off constraints.txt (or
    `text`), every line a bare `name==version` -- no range, extra, marker or
    option."""
    pins = {}
    for number, raw in enumerate((text if text is not None else (ROOT / "constraints.txt").read_text()).splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        pin = PIN.fullmatch(line)
        assert pin, f"constraints.txt line {number} is not a bare name==version: {raw!r}"
        key = canonicalize_name(pin["name"])
        assert key not in pins, f"constraints.txt pins {pin['name']} twice"
        pins[key] = (pin["name"], pin["version"])
    assert pins, "constraints.txt pins nothing"
    return pins


def test_requirement_lines_leave_every_spelling_of_r_and_c_to_the_install_test(tmp_path, monkeypatch):
    (tmp_path / "x.txt").write_text("-r requirements.txt\n--requirement=other.txt\n-c constraints.txt\n"
                                    "--constraint=constraints.txt\n-cconstraints.txt  # joined\n"
                                    "pandas>=2.0,<4  # a comment\n-e .\n")
    monkeypatch.setitem(globals(), "ROOT", tmp_path)
    # an editable or any other option line is read as a requirement, and the bounds test refuses it
    assert requirements("x.txt") == [{"name": "pandas", "spec": ">=2.0,<4"}, {"name": "-e", "spec": "."}]


@pytest.mark.parametrize("name", ["requirements.txt", "requirements-dev.txt", "requirements-host.txt"])
def test_each_requirement_is_bounded_above_or_pinned(name):
    found = requirements(name)
    assert found, name
    for req in found:
        clauses = [c.strip() for c in req["spec"].split(",") if c.strip()]
        pinned = len(clauses) == 1 and clauses[0].startswith("==")
        bounded = any(c.startswith(">=") for c in clauses) and any(re.fullmatch(r"<\s*[0-9][0-9.]*", c) for c in clauses)
        assert pinned or bounded, f"{name}: {req['name']}{req['spec']} has no upper bound"


def test_the_bounds_name_the_majors_the_suite_was_run_against():
    bounds = {r["name"].lower(): r["spec"].replace(" ", "") for r in requirements("requirements.txt") + requirements("requirements-dev.txt")}
    assert bounds == {
        "pandas": ">=2.0,<4", "numpy": ">=1.24,<3", "requests": ">=2.31,<3", "mplfinance": ">=0.12.10b0,<0.13",
        "anthropic": ">=1.15,<2", "resend": ">=2.0,<3", "alpaca-py": ">=0.21,<1", "exchange_calendars": "==4.13.2",
        "pytest": ">=8.0,<10", "httpx2": ">=2.12,<3", "pyyaml": ">=6.0,<7"}


# --- constraints.txt -----------------------------------------------------------
def test_the_constraints_pin_each_package_once_in_name_order():
    pins = constraints()
    assert list(pins) == sorted(pins)


@pytest.mark.parametrize("line", ["six>=1.17.0", "six~=1.17.0", "six===1.17.0", "six[extra]==1.17.0",
                                  'six==1.17.0; sys_platform == "linux"', "-r requirements.txt", "six == 1.17.0", "six"])
def test_a_constraint_line_that_is_not_a_bare_pin_is_refused(line):
    assert constraints("alpaca-py==0.44.0\n# a comment\n\nsix==1.17.0\n") == {
        "alpaca-py": ("alpaca-py", "0.44.0"), "six": ("six", "1.17.0")}
    with pytest.raises(AssertionError, match="line 2 is not a bare name==version"):
        constraints(f"alpaca-py==0.44.0\n{line}\n")


def roots():
    return [Requirement(r["name"] + r["spec"]) for r in requirements("requirements.txt") + requirements("requirements-dev.txt")]


def test_every_direct_requirement_is_pinned_inside_its_own_bound():
    pins = constraints()
    for req in roots():
        key = canonicalize_name(req.name)
        assert key in pins, f"{req.name} is a requirement constraints.txt does not pin"
        version = pins[key][1]
        # mplfinance's only 0.12.10 release is a beta, so the bound admits a pre-release.
        assert req.specifier.contains(version, prereleases=True), f"{req.name}=={version} is outside {req.specifier}"


def test_the_suite_runs_against_the_pinned_versions():
    """What this interpreter has installed is the pinned set, so the closure
    test below reads the pins' own metadata and a machine set up some other way
    says so. Today an unconstrained install resolves the same set; after the
    next release it holds in CI because requirements-dev.txt carries the -c
    line, which the install test at the end holds."""
    wrong = {}
    for key, (name, version) in constraints().items():
        try:
            installed = metadata.version(name)
        except metadata.PackageNotFoundError:
            installed = None
        if installed is None or Version(installed) != Version(version):
            wrong[name] = (version, installed)
    assert not wrong, ("installed versions differ from constraints.txt (pinned, installed); "
                       f"reinstall with `pip install -r requirements-dev.txt`: {wrong}")


def closure_problems(pins, roots, requires):
    """What keeps `pins` from being one resolution of `roots`: walking each
    package's own requirements (`requires(name)`, Requires-Dist lines) down
    from the roots, with their markers read on the runners' platform and their
    extras followed, a dependency with no pin, a pin outside the range a root
    or a dependent asks, and a pin nothing reaches (left over from an older
    one)."""
    problems, reached = [], set()
    for root in roots:
        key = canonicalize_name(root.name)
        if key in pins and not root.specifier.contains(pins[key][1], prereleases=True):
            problems.append(f"the requirements ask {root.name}{root.specifier}; constraints.txt pins {pins[key][1]}")
    queue = [(canonicalize_name(r.name), frozenset(r.extras)) for r in roots]
    while queue:
        key, extras = queue.pop()
        if (key, extras) in reached:
            continue
        reached.add((key, extras))
        if key not in pins:
            problems.append(f"{key} is required and not pinned")
            continue
        for line in requires(pins[key][0]) or []:
            dep = Requirement(line)
            if dep.marker and not any(dep.marker.evaluate(dict(RUNNER, extra=e)) for e in (extras or {""})):
                continue
            dep_key = canonicalize_name(dep.name)
            if dep_key in pins and not dep.specifier.contains(pins[dep_key][1], prereleases=True):
                problems.append(f"{pins[key][0]} asks {dep.name}{dep.specifier}; constraints.txt pins {pins[dep_key][1]}")
            queue.append((dep_key, frozenset(dep.extras)))
    stale = sorted(set(pins) - {key for key, _ in reached})
    if stale:
        problems.append(f"pinned and required by nothing: {stale}")
    return problems


def test_the_pins_are_closed_under_their_own_dependencies():
    """Read off the installed metadata, which the test above holds to the pins:
    the file is one resolution, with no package missing and none left over."""
    assert closure_problems(constraints(), roots(), lambda name: metadata.distribution(name).requires) == []


def test_the_closure_names_each_way_a_set_of_pins_is_not_one_resolution():
    def pins(*pairs):
        return {canonicalize_name(n): (n, v) for n, v in pairs}
    tree = {"app": ["lib>=1,<2", "tool[extra]>=3", 'winonly>=1; sys_platform == "win32"'],
            "lib": ["base>=2"], "tool": ['plugin>=1; extra == "extra"', 'unused>=1; extra == "other"'],
            "base": [], "plugin": []}
    roots_ = [Requirement("app>=1")]
    good = pins(("app", "1.0"), ("lib", "1.5"), ("tool", "3.1"), ("base", "2.0"), ("plugin", "1.2"))
    assert closure_problems(good, roots_, tree.get) == []    # winonly and unused are not asked on the runners
    assert closure_problems({k: v for k, v in good.items() if k != "base"}, roots_, tree.get) == [
        "base is required and not pinned"]
    assert closure_problems({k: v for k, v in good.items() if k != "plugin"}, roots_, tree.get) == [
        "plugin is required and not pinned"]                 # an extra a dependency asks for is followed
    assert closure_problems({**good, **pins(("lib", "2.0"))}, roots_, tree.get) == [
        "app asks lib<2,>=1; constraints.txt pins 2.0"]
    assert closure_problems({**good, **pins(("Left_Over", "9"))}, roots_, tree.get) == [
        "pinned and required by nothing: ['left-over']"]
    assert closure_problems({**good, **pins(("app", "0.9"))}, roots_, tree.get) == [
        "the requirements ask app>=1; constraints.txt pins 0.9"]


def test_markers_are_read_on_the_runners_platform_not_this_machines(monkeypatch):
    """A dependency asked only on another platform is never demanded of the
    file, and one asked only on the runners always is, whatever machine runs
    the suite: the walk reads RUNNER, never this interpreter's environment."""
    def pins(*pairs):
        return {canonicalize_name(n): (n, v) for n, v in pairs}
    tree = {"app": ['linuxonly>=1; sys_platform == "linux"', 'winonly>=1; sys_platform == "win32"'],
            "linuxonly": [], "winonly": []}
    roots_ = [Requirement("app>=1")]
    assert closure_problems(pins(("app", "1.0")), roots_, tree.get) == ["linuxonly is required and not pinned"]
    monkeypatch.setitem(globals(), "RUNNER", dict(RUNNER, sys_platform="win32"))   # the module global the walk reads
    assert closure_problems(pins(("app", "1.0")), roots_, tree.get) == ["winonly is required and not pinned"]


def workflow_jobs():
    for path in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        for job_name, job in (yaml.safe_load(path.read_text()).get("jobs") or {}).items():
            yield path.name, job_name, job


def test_the_marker_platform_is_the_one_the_workflows_install_on():
    """Every job that installs the runtime set or the suite's runs on Ubuntu
    under setup-python at RUNNER's Python version."""
    jobs = 0
    for name, job_name, job in workflow_jobs():
        installed = {r for words in job_installs(job) for r in (pip_args(words) or ([],))[0]}   # a refusal is the install test's
        if not installed & {"requirements.txt", "requirements-dev.txt"}:
            continue
        jobs += 1
        assert str(job.get("runs-on", "")).startswith("ubuntu-"), (name, job_name, job.get("runs-on"))
        versions = [str(s["with"]["python-version"]) for s in job.get("steps") or []
                    if "actions/setup-python" in str(s.get("uses", "")) and "python-version" in (s.get("with") or {})]
        assert versions == [RUNNER["python_version"]], (name, job_name, versions)
    assert RUNNER["sys_platform"] == "linux" and jobs >= 9   # the five workflows' eight jobs and tests.yml's pytest


@contextlib.contextmanager
def pip_isolated():
    """pip's parsers with no pip.conf of this machine's (PIP_CONFIG_FILE set to
    os.devnull, which pip reads as "load no configuration file") and what they
    print on a refusal kept off the test's output; the install command is made
    isolated, so no PIP_* variable is read either."""
    saved = os.environ.get("PIP_CONFIG_FILE")
    os.environ["PIP_CONFIG_FILE"] = os.devnull
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            yield
    finally:
        if saved is None:
            os.environ.pop("PIP_CONFIG_FILE", None)
        else:
            os.environ["PIP_CONFIG_FILE"] = saved


def pip_args(words):
    """(requirements files, constraint files, packages named) of one pip
    invocation's words after `pip`, read by pip's own option parsers -- the
    general options, the subcommand, then install's options -- so every
    spelling pip accepts is read as pip reads it: separate or joined, `=` or
    not, clustered (`-qr`), abbreviated (`--constr`), and the value of an
    option that takes one (`--only-binary :all:`). Paths are read as written,
    from the repository root, where every step runs. None for words pip would
    refuse; ([], [], []) for a subcommand that is not install."""
    from pip._internal.cli.main_parser import parse_command
    from pip._internal.commands import create_command
    with pip_isolated():
        try:
            name, rest = parse_command(list(words))
            if name != "install":
                return [], [], []
            options, packages = create_command(name, isolated=True).parse_args(rest)
        except (SystemExit, Exception):  # noqa: BLE001 -- pip's own refusal of the words
            return None
    return ([posixpath.normpath(p) for p in options.requirements], [posixpath.normpath(p) for p in options.constraints],
            list(packages) + list(options.editables))


OPERATORS = {"&&", "||", ";", "|", "&", "(", ")", ";;"}
REDIRECTS = re.compile(r"\d*(>>?|<<?|>&|<&|&>>?|>\|)\Z")


def shell_commands(script):
    """The words of each simple command in a run: block that names pip and
    install: backslash continuations joined, cut at && || ; | & and ( ),
    comments dropped, each redirection and its target dropped."""
    for line in re.sub(r"\\\n", " ", script).splitlines():
        if not (re.search(r"\bpip(3(\.\d+)?)?\b", line) and re.search(r"\binstall\b", line)):
            continue
        lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        words, tokens = [], iter(list(lexer))
        for token in tokens:
            if token in OPERATORS:
                yield words
                words = []
            elif REDIRECTS.fullmatch(token):
                if words and words[-1].isdigit():
                    words.pop()           # the descriptor of `2>&1`
                next(tokens, None)        # and the redirection's target
            else:
                words.append(token)
        yield words


def pip_invocations(script):
    """The words after `pip` of every pip invocation a script runs (pip, pip3,
    pip3.12, a path to one, `python -m pip`), install or not, and of every
    script handed to another shell as one word (`bash -c '...'`)."""
    for words in shell_commands(script):
        for word in words:
            if re.search(r"\s", word):
                yield from pip_invocations(word)
        for i, word in enumerate(words):
            if re.fullmatch(r"pip(3(\.\d+)?)?", posixpath.basename(word)):
                yield words[i + 1:]
                break


def job_installs(job):
    return [words for step in job.get("steps") or [] for words in pip_invocations(str(step.get("run") or ""))]


def readme_commands():
    """The README's own setup commands: the lines of its fenced code blocks."""
    lines, fenced = [], False
    for line in (ROOT / "README.md").read_text().splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif fenced:
            lines.append(line)
    return "\n".join(lines)


def installs():
    """(where, words after pip) for every pip invocation a workflow job runs
    and the README's code blocks name."""
    out = [(f"{name}:{job_name}", words) for name, job_name, job in workflow_jobs() for words in job_installs(job)]
    return out + [("README.md", words) for words in job_installs({"steps": [{"run": readme_commands()}]})]


def constraint_lines(name):
    """The constraint files a requirements file names on its own option lines."""
    cons = []
    for raw in (ROOT / name).read_text().splitlines():
        words = shlex.split(raw, comments=True)
        if words and words[0].startswith("-"):
            cons += pip_args(["install", *words])[1]
    return cons


def install_problems(found):
    """(problems, where requirements.txt is installed) over (where, words after
    pip): words pip would refuse, an install that names a package or an
    editable on the command line, one that reads a file this test does not
    account for, and requirements.txt read without constraints.txt."""
    problems, runtime = [], set()
    for where, words in found:
        read = pip_args(words)
        if read is None:
            problems.append(f"{where}: pip {shlex.join(words)} is refused by pip's own parser")
            continue
        reqs, cons, packages = read
        if packages:
            problems.append(f"{where}: pip {shlex.join(words)} installs what no requirements file names")
        for req in reqs:
            if req not in INSTALLABLE:
                problems.append(f"{where}: pip {shlex.join(words)} reads {req}, which this test does not account for")
            elif req == "requirements.txt":
                runtime.add(where)
                if "constraints.txt" not in cons:
                    problems.append(f"{where}: pip {shlex.join(words)} installs requirements.txt without the constraints")
    return problems, runtime


def scripted(*commands):
    return [(f"job{i}", words) for i, command in enumerate(commands) for words in job_installs({"steps": [{"run": command}]})]


def test_the_install_check_names_each_way_an_install_escapes_the_pins():
    ok = ("pip install -r requirements.txt -c constraints.txt", "python -m pip install -r requirements-dev.txt",
          "pip install --require-hashes -r tools/requirements-historical-archive.txt", "pip --version", "pip freeze")
    assert install_problems(scripted(*ok)) == ([], {"job0"})
    assert install_problems(scripted("pip install pandas"))[0] == ["job0: pip install pandas installs what no requirements file names"]
    assert install_problems(scripted("pip install -e ."))[0] == ["job0: pip install -e . installs what no requirements file names"]
    assert install_problems(scripted("pip install -r requirements-host.txt"))[0] == [
        "job0: pip install -r requirements-host.txt reads requirements-host.txt, which this test does not account for"]
    assert install_problems(scripted("pip install --requirement requirements.txt")) == (
        ["job0: pip install --requirement requirements.txt installs requirements.txt without the constraints"], {"job0"})
    assert install_problems(scripted("pip install -r requirements.txt --bogus"))[0] == [
        "job0: pip install -r requirements.txt --bogus is refused by pip's own parser"]


def test_every_pip_install_a_workflow_runs_reads_a_file_this_test_accounts_for():
    found = installs()
    problems, runtime = install_problems(found)
    assert problems == []
    assert runtime >= {"evening.yml:scan", "intraday.yml:check", "issuer-evidence.yml:collect", "issuer-evidence.yml:persist",
                       "morning.yml:collect", "morning.yml:persist", "source-recovery.yml:collect",
                       "source-recovery.yml:persist", "README.md"}
    assert any(where == "tests.yml:pytest" and "requirements-dev.txt" in pip_args(words)[0] for where, words in found)
    # requirements-dev.txt carries the constraints itself (tests.yml and the README install it bare) ...
    assert "constraints.txt" in constraint_lines("requirements-dev.txt")
    # ... and requirements.txt does not: requirements-host.txt reads it and pins the host's own set.
    assert constraint_lines("requirements.txt") == []


@pytest.mark.parametrize("command,read", [
    ("python -m pip install -r requirements.txt -c constraints.txt", (["requirements.txt"], ["constraints.txt"], [])),
    ("pip3 install --requirement=./requirements.txt --constraint constraints.txt", (["requirements.txt"], ["constraints.txt"], [])),
    ("pip install -r ./requirements.txt -c ./constraints.txt", (["requirements.txt"], ["constraints.txt"], [])),
    ("pip install -rrequirements.txt -cconstraints.txt", (["requirements.txt"], ["constraints.txt"], [])),
    ("pip install -qr requirements.txt --constr constraints.txt", (["requirements.txt"], ["constraints.txt"], [])),
    ("/opt/venv/bin/pip3.12 --disable-pip-version-check install --only-binary :all: --timeout 60 -r requirements.txt",
     (["requirements.txt"], [], [])),
    ("pip install -r requirements.txt -c constraints.txt 2>&1 | tee pip.log", (["requirements.txt"], ["constraints.txt"], [])),
    ("pip install -r requirements.txt > pip.log  # a comment -c constraints.txt", (["requirements.txt"], [], [])),
    ("bash -c 'pip install -r requirements.txt -c constraints.txt'", (["requirements.txt"], ["constraints.txt"], [])),
    ("pip install requests==2.34.2", ([], [], ["requests==2.34.2"])),
])
def test_the_install_reader_reads_every_spelling_pip_accepts(command, read):
    [words] = job_installs({"steps": [{"run": command}]})
    assert pip_args(words) == read


def test_the_install_reader_reads_the_words_and_not_this_machines_pip_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("PIP_CONSTRAINT", "constraints.txt")
    monkeypatch.setenv("PIP_REQUIREMENT", "requirements-host.txt")
    assert pip_args(["install", "-r", "requirements.txt"]) == (["requirements.txt"], [], [])
    conf = tmp_path / "pip.conf"
    conf.write_text("[install]\nconstraint = constraints.txt\nrequirement = requirements-host.txt\n")
    monkeypatch.setenv("PIP_CONFIG_FILE", str(conf))
    assert pip_args(["install", "-r", "requirements.txt"]) == (["requirements.txt"], [], [])
    assert os.environ["PIP_CONFIG_FILE"] == str(conf)        # put back as it was


def test_the_install_reader_follows_continuations_and_command_lists():
    script = ("set -e\npython -m pip install \\\n  -r requirements.txt && pip install -r requirements-dev.txt; echo done\n"
              "( cd . && pip install -r tools/requirements-historical.txt ) || exit 1\n")
    assert [pip_args(w)[0] for w in job_installs({"steps": [{"run": script}]})] == [
        ["requirements.txt"], ["requirements-dev.txt"], ["tools/requirements-historical.txt"]]


def test_the_readme_is_read_from_its_code_blocks(tmp_path, monkeypatch):
    (tmp_path / "README.md").write_text("Install with pip install pandas, says the prose.\n```bash\n"
                                        "python -m pip install -r requirements.txt\n```\npip install -r x.txt\n")
    monkeypatch.setitem(globals(), "ROOT", tmp_path)
    assert readme_commands() == "python -m pip install -r requirements.txt"
