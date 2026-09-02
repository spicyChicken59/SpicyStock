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
        # Both patterns require the word "tests" next to the number. The
        # looser `runs (\d+)` this used to carry matched "runs 80/80 with no
        # page errors" in a note about the dashboard smoke test and failed a
        # document that was true -- the same crying-wolf failure this file
        # already had once, arriving through the regex instead of the count.
        claims += [(doc, int(n)) for n in re.findall(r"(\d+)\s+tests\b", text)]
        claims += [(doc, int(n)) for n in re.findall(r"runs\s+(\d+)\s+tests\b", text)]
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


def test_the_documented_streak_fields_are_the_ones_the_block_carries():
    """README lists the streak block's fields by name, and a reader uses that
    list to know what a row can tell them.

    It went stale the moment the block grew a field, and the only guard was
    somebody remembering -- the failure mode this file exists for. Checked
    against the block src.ledger actually publishes rather than against a
    second list kept here, so there is nothing to keep in step.
    """
    from src import ledger

    block = ledger.unknown_streak(ledger.NO_HISTORY)
    readme = _read("README.md")
    missing = sorted(field for field in block if f"`{field}`" not in readme)

    assert not missing, (
        f"README's dashboard contract does not name {missing} in the streak "
        "block. Add them to the 'Every burst carries `streak`' bullet: "
        "`history_from` is the session of the oldest run the ledger holds and "
        "`history_sessions` how many distinct sessions that is, so a reader "
        "can be told what an unknown `day` is unknown over."
    )


def test_every_reason_a_streak_can_carry_has_words_on_every_surface():
    """A `day: null` renders as a sentence, and there are three places that
    write one: README, the email, and the dashboard.

    src.emailer's STREAK_UNKNOWN says in its own comment that docs/index.html
    holds the same map and that changing one means changing the other. A
    reason with no entry falls through to "no reason was recorded" -- which is
    a true sentence about the renderer and a useless one to the reader, and it
    is silent, so nobody finds out. That is the state history_undated shipped
    in until this test.
    """
    from src import emailer, ledger

    reasons = {ledger.NO_HISTORY, ledger.HISTORY_UNDATED,
               ledger.HISTORY_UNREADABLE, ledger.WINDOW_NOT_COVERED}
    page = _read("docs/index.html")

    assert reasons <= set(emailer.STREAK_UNKNOWN), (
        f"src.emailer.STREAK_UNKNOWN has no words for "
        f"{sorted(reasons - set(emailer.STREAK_UNKNOWN))}; those rows render as "
        '"no reason was recorded"'
    )
    assert not [r for r in reasons if r not in page], (
        f"docs/index.html's STREAK_UNKNOWN has no words for "
        f"{sorted(r for r in reasons if r not in page)}, so the page and the "
        "email say different things about one row"
    )
    assert not [r for r in reasons if f"`{r}`" not in _read("README.md")], (
        "README's streak bullet does not name every reason a null `day` can carry"
    )


def _gitignore_blocks(path: str) -> bool | None:
    """Does .gitignore block `path`? None when git DID NOT ANSWER.

    `git check-ignore -q` exits 0 for ignored, 1 for not ignored -- and 128 for
    "not a git repository", which is not an answer at all. Reading 128 as
    "not ignored" is how the caller below stopped being able to fail: in a
    `git archive` tree the whole suite went green with the exact `git add docs
    results` bug reinstated in evening.yml, and only `git init` killed it.
    That is the same shape as the version of this test that passed on the very
    workflow line that broke -- through a different door.

    Both spellings are asked, because `/results/` in .gitignore has a trailing
    slash and so matches directories only: `git check-ignore results` on a
    path that does not exist in this checkout cannot tell that it is one, and
    answers "not ignored".
    """
    import subprocess

    answers = []
    for spelling in (path, path.rstrip("/") + "/"):
        try:
            done = subprocess.run(["git", "check-ignore", "-q", spelling],
                                  cwd=ROOT, capture_output=True, text=True)
        except OSError:
            return None                      # no git on this machine
        if done.returncode not in (0, 1):
            return None                      # not a checkout; 128 is not a "no"
        answers.append(done.returncode == 0)
    return any(answers)


def test_no_workflow_stages_a_path_gitignore_blocks():
    """`git add <ignored path>` exits 1, and Actions runs every `run:` block
    under `bash -e`.

    evening.yml staged `docs results` for a whole step. results/ is gitignored
    on purpose, so the add failed, the step aborted before its commit, and the
    docs/ it had just staged died with the container -- on every single run,
    while the workflow's own comment said the history was being kept and README
    said it accumulated. Reading the two files side by side is exactly what
    missed it; this reads them together.

    Where git cannot answer, this SKIPS rather than passing. A guard over the
    bug that silently voided the whole rebuild's history is worth nothing if
    it reports safety it is not providing, and a skip is the one outcome that
    says so out loud -- see _gitignore_blocks().
    """
    import pytest

    unanswered = []
    for workflow in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        for line in workflow.read_text().splitlines():
            stripped = line.strip()
            if not stripped.startswith("git add "):
                continue
            for path in stripped[len("git add "):].split():
                if path.startswith("-"):
                    continue
                blocked = _gitignore_blocks(path)
                if blocked is None:
                    unanswered.append(f"{workflow.name}: git add {path}")
                    continue
                assert not blocked, (
                    f"{workflow.name} runs `git add {path}`, and .gitignore blocks it. "
                    "git exits 1 there, and under Actions' `bash -e` that aborts the "
                    "step before whatever comes after the add."
                )
    if unanswered:
        pytest.skip(
            "git check-ignore could not answer here (no repository, or no git), so "
            f"these were NOT checked: {unanswered}. This guard only runs inside a "
            "checkout -- CI has one."
        )


def test_readme_does_not_promise_a_null_streak_for_an_unreadable_history():
    """README described the unreadable-history state as `streak: null` on every
    row. It is not: it is a full block with `unknown_reason` set, which renders
    different words to the reader -- and `streak: null` is a separate state
    meaning the run recorded nothing. The paragraph making that exact
    distinction got the shape of it wrong, two hundred lines from the one that
    got it right.

    Checked against the code rather than against a remembered string: whatever
    src/ledger.py actually publishes for an unreadable history is what README
    has to describe.
    """
    from src import ledger

    block = ledger.unknown_streak(ledger.HISTORY_UNREADABLE)
    assert block is not None and block.get("day") is None, (
        "src.ledger no longer publishes a block for an unreadable history -- "
        "re-check what README should say"
    )
    readme = _read("README.md")
    assert "publishes `streak: null` on every row" not in readme, (
        "README says an unreadable history publishes `streak: null`, but "
        "src.ledger publishes a block with unknown_reason="
        f"{block.get('unknown_reason')!r}"
    )
    assert "`history_unreadable`" in readme, (
        "README no longer names the reason src.ledger actually publishes"
    )


# --- where the fixture lives ------------------------------------------------
# docs/data.json used to be the fixture AND the file every run rewrites, guarded
# by a script that compared it to the generator on every push. The first
# successful commit-back would have turned CI red for good. The canonical copy
# is tests/fixtures/data.json now; docs/data.json is whatever the last run
# wrote, seeded from it.

FIXTURE = ROOT / "tests" / "fixtures" / "data.json"


def test_the_canonical_fixture_is_where_the_docs_say_it_is():
    """README names the path and the regenerate command. Both used to point at
    docs/, and the command there would now overwrite a real run."""
    assert FIXTURE.exists(), "tests/fixtures/data.json is the canonical fixture"
    readme = _read("README.md")
    assert "tests/fixtures/data.json" in readme
    assert "make_fixture.py tests/fixtures/data.json" in readme
    assert "make_fixture.py docs/data.json" not in readme, (
        "README still tells the reader to regenerate the fixture over docs/data.json"
    )


def test_a_docs_data_json_that_claims_to_be_the_fixture_is_the_fixture():
    """`run.fixture: true` is what raises the sample-data banner and what makes
    the morning run refuse the file. A docs/data.json making that claim must
    be the canonical fixture, byte for byte -- a hand-edited copy is a third
    thing. Skipped, not passed, once a real run has replaced it: then there is
    nothing to compare and saying so is the honest answer."""
    import json

    import pytest

    live = ROOT / "docs" / "data.json"
    run = json.loads(live.read_text()).get("run") or {}
    if not run.get("fixture"):
        pytest.skip(f"docs/data.json is the {run.get('type')} run of {run.get('date')}, "
                    "not the fixture; nothing to compare")
    assert live.read_bytes() == FIXTURE.read_bytes(), (
        "docs/data.json says it is the fixture but differs from tests/fixtures/data.json"
    )


def test_the_history_fixture_is_where_the_docs_say_it_is():
    """The thirty-run fixture the smoke test's second source reads, and the
    guard regenerates. README names the directory and the generator; a
    fixture nobody can find is a fixture nobody regenerates."""
    history = ROOT / "tests" / "fixtures" / "history"
    assert (history / "data.json").exists() and (history / "ledger.json").exists()
    readme = _read("README.md")
    assert "tests/fixtures/history" in readme and "tools/make_history.py" in readme
    assert (ROOT / "tests" / "fixtures" / "README.md").exists(), (
        "tests/fixtures/README.md is where the fixtures say what they are"
    )


def test_the_documented_evidence_blocks_are_the_ones_published():
    """README's table names what the page can answer, and a reader uses it to
    know which questions the file holds.

    Checked against the block src.ledger actually publishes rather than a
    second list kept here, so a block added to evidence() and never documented
    fails the build instead of quietly existing. The same shape as the streak
    fields test above, and for the same reason: this rule has failed four
    times by being remembered.
    """
    from src import ledger

    published = ledger.evidence([])
    readme = _read("README.md")
    missing = sorted(f"evidence.{key}" for key in published
                     if f"`evidence.{key}`" not in readme and f"`{key}`" not in readme)

    assert not missing, (
        f"README does not name {missing}. Add them to 'What the page answers, "
        "and what it refuses to answer' -- a block nobody documents is a "
        "question nobody knows the page can answer."
    )


def test_the_page_renders_the_record_rather_than_recomputing_it():
    """The whole reason evidence() is Python: mean_returns' setup rule is a
    definition, and a second copy of it in JavaScript is the defect this
    project has shipped twice.

    So the page must take the floor and the per-block verdict FROM THE FILE.
    Two earlier versions of this test were themselves the shapes CLAUDE.md
    warns about: one grepped for "setup_leads" and failed on the comment
    explaining why the page does not do it, and one grepped for the floor's
    digits and matched `max-width: 30ch` in a stylesheet. What is asserted now
    is the property itself -- the page reads `min_setups` and `enough` rather
    than deciding either for itself.
    """
    page = _read("docs/index.html")

    assert "evidence" in page, "the page does not read the evidence block at all"
    assert "min_setups" in page, (
        "the page does not read evidence.min_setups; carrying its own floor "
        "lets the file and the page disagree about whether a number may be "
        "read as a rate"
    )
    assert "b.enough" in page or ".enough" in page, (
        "the page does not read `enough` off the file, so it is deciding for "
        "itself which means are worth printing as rates"
    )
