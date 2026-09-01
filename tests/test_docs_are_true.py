"""The doc-sweep rule, enforced instead of remembered.

CLAUDE.md says a step is not done until README.md and .env.example are true for
the code as it stands. That rule failed on three consecutive commits -- each one
added tests and left the documented count behind -- because it relied on someone
remembering to apply it. These tests make the claims that CAN be checked
mechanically fail the build instead.

Only mechanically-checkable claims belong here. Prose still needs a human.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _read(name: str) -> str:
    return (ROOT / name).read_text()


def test_the_documented_test_count_is_the_real_one(request):
    """README and CLAUDE.md both quote a test count.

    Counts what pytest actually collected rather than `def test_` lines --
    parametrized tests expand, and the regex version undercounted by four.

    Skipped unless this run collected the whole suite. Counting the items of a
    partial run and calling the docs wrong is how a test earns a reputation for
    crying wolf: `pytest tests/test_docs_are_true.py` went red on a repo whose
    docs were correct, which teaches the reader to ignore it on the day it is
    right.
    """
    on_disk = {p.stem for p in (ROOT / "tests").glob("test_*.py")}
    collected = {
        pathlib.Path(str(item.fspath)).stem for item in request.session.items
    }
    missing = sorted(on_disk - collected)
    if missing:
        import pytest

        pytest.skip(
            f"partial run -- {missing} not collected; the documented count is "
            "only checkable against the whole suite (`pytest tests/`)"
        )

    total = len(request.session.items)
    claims: list[tuple[str, int]] = []
    for doc in ("README.md", "CLAUDE.md"):
        text = _read(doc)
        claims += [(doc, int(n)) for n in re.findall(r"(\d+)\s+tests\b", text)]
        claims += [(doc, int(n)) for n in re.findall(r"runs\s+(\d+)\b", text)]
    assert claims, "no documented test count found -- did the wording change?"
    wrong = [(d, n) for d, n in claims if n != total]
    assert not wrong, (
        f"docs claim {wrong} but pytest collected {total}. "
        "Update the count -- the doc-sweep rule has failed again."
    )


def test_the_documented_universe_size_is_the_real_one():
    """README quotes the symbol-file size in several places.

    Matched against the phrasings that really do quote the universe, so the
    pipeline diagram's "~30-120 names on a normal day" -- a candidate count,
    not a universe size -- is not mistaken for one.
    """
    actual = len([
        s for s in (
            line.split("#")[0].strip()
            for line in (ROOT / "data" / "symbols.txt").read_text().splitlines()
        ) if s
    ])
    readme = _read("README.md")
    patterns = [
        r"\b(\d{2,5})-name\b",
        r"\b(\d{2,5})-symbol\b",
        r"data/symbols\.txt,\s*(\d{2,5})\s*names",
        r"\b(\d{2,5})\s+checked-in\b",
    ]
    claimed = {int(n) for p in patterns for n in re.findall(p, readme)}
    wrong = sorted(n for n in claimed if n != actual)
    assert not wrong, f"README quotes {wrong} for the universe; data/symbols.txt has {actual}"


def test_the_email_reports_the_universe_it_actually_scanned():
    """The daily email is the artifact a person reads. It said "US common
    stocks" for a full batch after the scan was narrowed to a checked-in file.
    """
    pipeline = _read("src/pipeline.py")
    assert '"universe": "US common stocks"' not in pipeline, (
        "pipeline hard-codes the pre-step-2 universe string into the email"
    )


def test_env_example_does_not_claim_feed_is_unset_once_it_is_set():
    """.env.example asserts "no feed= is set anywhere". Step 3 sets it. This
    test is here so that step cannot land without sweeping the claim.
    """
    if "no feed= is set anywhere" in _read(".env.example"):
        assert "feed=" not in _read("src/scanner.py"), (
            ".env.example still says no feed= is set, but src/scanner.py sets one -- "
            "sweep .env.example (CLAUDE.md's falsification table lists this)"
        )


def test_the_documented_workflow_files_are_the_ones_that_exist():
    """README lists what is in .github/workflows/ by name.

    It claimed `morning.yml does not exist` for the whole rebuild, which was
    true until step 10 wrote one. The inventory is a fact about the
    filesystem, so it is checked against the filesystem rather than reread by
    a human -- in both directions, because a workflow added and never
    documented is the same failure as one documented and never added.
    """
    on_disk = {p.name for p in (ROOT / ".github" / "workflows").glob("*.yml")}
    named = set(re.findall(r"([a-z-]+\.yml)", _read("README.md")))

    assert not on_disk - named, (
        f"README does not name {sorted(on_disk - named)} in .github/workflows/"
    )
    assert not named - on_disk, (
        f"README names {sorted(named - on_disk)}, which do not exist"
    )


def test_the_documented_run_modes_are_the_ones_the_pipeline_has():
    """README's "The two runs" table names the modes and says which workflow
    runs each. A mode the parser accepts and nothing documents is how `morning`
    spent this rebuild being a label.
    """
    from src.pipeline import MODES

    section = _read("README.md").split("## The two runs", 1)
    assert len(section) == 2, "README's two-runs section is gone -- did the wording change?"
    table = section[1].strip().split("\n\n", 1)[0]

    for name in MODES:
        assert f"`{name}`" in table, f"README's two-runs table does not cover {name}"
        assert f"{name}.yml" in table, (
            f"the {name} mode is documented without the workflow that runs it"
        )
        assert (ROOT / ".github" / "workflows" / f"{name}.yml").exists(), (
            f"README says .github/workflows/{name}.yml runs the {name} mode, "
            "and it is not there"
        )


def test_the_mode_that_does_not_scan_is_the_one_documented_as_costing_nothing():
    """The claim that carries real money: README says the morning run makes no
    model call. That is only true while its Mode says it does not scan.
    """
    from src.pipeline import MODES

    assert [m.name for m in MODES.values() if not m.scans] == ["morning"]
    assert "The morning follow-through makes no" in _read("README.md")


def test_no_workflow_stages_a_path_gitignore_blocks():
    """`git add <ignored path>` exits 1, and Actions runs every `run:` block
    under `bash -e`.

    evening.yml staged `docs results` for a whole step. results/ is gitignored
    on purpose, so the add failed, the step aborted before its commit, and the
    docs/ it had just staged died with the container -- on every single run,
    while the workflow's own comment said the history was being kept and README
    said it accumulated. Reading the two files side by side is exactly what
    missed it; this reads them together.
    """
    import subprocess

    for workflow in (ROOT / ".github" / "workflows").glob("*.yml"):
        for line in workflow.read_text().splitlines():
            stripped = line.strip()
            if not stripped.startswith("git add "):
                continue
            for path in stripped[len("git add "):].split():
                if path.startswith("-"):
                    continue
                # Both spellings. `/results/` in .gitignore has a trailing
                # slash, so it matches directories only -- and `git
                # check-ignore results` on a path that does not exist on this
                # checkout cannot tell that it is one, and answers "not
                # ignored". The first version of this test asked exactly that
                # question and passed on the very workflow line that broke,
                # which is the shape of test this project keeps having to
                # delete.
                blocked = any(
                    subprocess.run(["git", "check-ignore", "-q", spelling],
                                   cwd=ROOT).returncode == 0
                    for spelling in (path, path.rstrip("/") + "/")
                )
                assert not blocked, (
                    f"{workflow.name} runs `git add {path}`, and .gitignore blocks it. "
                    "git exits 1 there, and under Actions' `bash -e` that aborts the "
                    "step before whatever comes after the add."
                )
