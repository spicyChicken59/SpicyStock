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

import pytest

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
    # README and CLAUDE.md both. The opening line -- "a checked-in universe of
    # 230 US common stocks", the first number a reader meets -- matched none of
    # the four phrasings this used to hold, so it could say 999 with the suite
    # green while the diagram three lines under it was guarded. CLAUDE.md's
    # falsification table quotes the figure as "230 curated names".
    readme = _read("README.md") + "\n" + _read("CLAUDE.md")
    patterns = [
        r"\b(\d{2,5})-name\b",
        r"\b(\d{2,5})-symbol\b",
        r"data/symbols\.txt,\s*(\d{2,5})\s*names",
        r"\b(\d{2,5})\s+checked-in\b",
        r"universe of (\d{2,5}) US common stocks",
        r"\b(\d{2,5}) curated names",
    ]
    claimed = {int(n) for p in patterns for n in re.findall(p, readme)}
    # ScanConfig.batch_size is a DIFFERENT real quantity that legitimately takes
    # the same suffix — "a 100-symbol batch" is a true sentence about the bars
    # request, not a stale claim about the universe — and this guard flagged it
    # the first time anyone wrote one down. Exempted by VALUE read off the real
    # config, not by pattern, so it stops exempting the moment the two numbers
    # coincide and the phrase really would be ambiguous.
    from src.scanner import ScanConfig
    batch = ScanConfig().batch_size
    if batch != actual:
        claimed.discard(batch)
    wrong = sorted(n for n in claimed if n != actual)
    assert not wrong, f"README quotes {wrong} for the universe; data/symbols.txt has {actual}"


def test_env_example_lists_the_feeds_the_sdk_accepts_and_the_default_the_scan_uses():
    """.env.example enumerates SCAN_FEED's values and names its default.

    This replaced a guard that could no longer fire: it was conditioned on a
    sentence ("no feed= is set anywhere") that step 3 swept out of the file,
    so it has passed vacuously ever since. The list and the default are facts
    about alpaca-py's DataFeed and src.scanner.DEFAULT_FEED, so they are read
    from there -- the prose audit changed the list to three feeds and the
    default to iex and the suite stayed green.
    """
    from alpaca.data.enums import DataFeed
    from src.scanner import DEFAULT_FEED

    env = _read(".env.example")
    listed = re.search(r"Which Alpaca feed to read: ([a-z_, ]+)\.", env)
    assert listed, ".env.example no longer lists SCAN_FEED's values -- did the wording change?"
    assert [f.strip() for f in listed.group(1).split(",")] == [e.value for e in DataFeed], (
        f".env.example lists {listed.group(1)!r}; alpaca-py's DataFeed has "
        f"{[e.value for e in DataFeed]}"
    )
    stated = re.search(r"Defaults to (\w+)\.", env)
    assert stated and stated.group(1) == DEFAULT_FEED.value, (
        f".env.example says the feed defaults to {stated and stated.group(1)!r}; "
        f"src.scanner.DEFAULT_FEED is {DEFAULT_FEED.value!r}"
    )


def test_the_documented_sip_hold_back_is_the_one_the_scanner_applies():
    """README and .env.example quote the hold-back as a number in words, and
    until this test nothing read it back: SIP_HOLDBACK_MINUTES = 45 left this
    file green. Read off the constant, the way the feed list and the default
    beside it are. Both files say "no later than" / "when the session's day
    would run past that" rather than an unconditional "holds it back",
    because the code caps the window rather than always moving it."""
    from src.scanner import SIP_HOLDBACK_MINUTES

    words = {10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen",
             15: "fifteen", 16: "sixteen", 17: "seventeen", 18: "eighteen",
             19: "nineteen", 20: "twenty"}
    assert SIP_HOLDBACK_MINUTES in words, "widen the table, or write the number in digits"
    word = words[SIP_HOLDBACK_MINUTES]

    readme = re.search(r"no later than (\w+) minutes behind the\s+clock", _read("README.md"))
    assert readme, "README no longer states the hold-back -- did the wording change?"
    assert readme.group(1) == word, (
        f"README says the window ends {readme.group(1)} minutes behind the clock; "
        f"src.scanner.SIP_HOLDBACK_MINUTES is {SIP_HOLDBACK_MINUTES}")
    env = re.search(r"ends its own window (\w+) minutes behind", _read(".env.example"))
    assert env, ".env.example no longer states the hold-back -- did the wording change?"
    assert env.group(1) == word, (
        f".env.example says {env.group(1)} minutes; SIP_HOLDBACK_MINUTES is {SIP_HOLDBACK_MINUTES}")


def test_the_documented_thresholds_are_the_ones_the_code_applies(ohlcv):
    """README's pipeline diagram and schedule quote the numbers the code runs
    on; .env.example quotes the close it keys the session on.

    The prose audit mutated nine of them at once -- the gate to 4/6, the cap
    to 99, the retention to 999 runs, the fill window to two, the shortlist
    to 7, the evening to 7:16 PM, the volume ratio to 9.5x, the price floor to
    $40, the close to 17:15 -- and the suite stayed green. Each is read off
    the constant it describes; the times are derived from the workflow crons
    the way the README derives them (UTC under EDT, minus four hours).
    """
    import yaml
    from src import ledger, lynch, pipeline, scanner

    readme = _read("README.md")
    cfg = scanner.ScanConfig()

    def one(pattern, text=readme):
        found = re.search(pattern, text, re.S)
        assert found, f"README no longer says {pattern!r} -- did the wording change?"
        return found.groups()

    (gain,) = one(r"≥(\d+)% gain")
    assert float(gain) == cfg.min_gain_pct
    rvol, lookback = one(r"≥([\d.]+)x its own\D+?(\d+)-session average")
    assert (float(rvol), int(lookback)) == (cfg.min_rvol, cfg.rvol_lookback)
    (price,) = one(r"price > \$(\d+)")
    assert float(price) == cfg.min_price
    (kept,) = one(r"top (\d+)% of the day's dollar volume")
    assert int(kept) == 100 - cfg.min_dollar_volume_pctile
    need, of, cap = one(r"hard gate: ≥(\d)/(\d) passes, top (\d+) kept")
    assert (int(need), int(of), int(cap)) == (
        pipeline.MIN_LYNCH_PASSES, lynch.evaluate_2lynch(ohlcv("burst"))["total"],
        pipeline.MAX_TO_SCORE)
    (up_days,) = one(r"never after (\d)\+ consecutive up days")
    assert int(up_days) == lynch.MAX_CONSECUTIVE_UP_DAYS + 1
    (top,) = one(r"HTML table, top (\d+),")
    assert int(top) == pipeline.TOP_N
    (runs,) = one(r"kept for the last (\d+) runs")
    assert int(runs) == ledger.MAX_RUNS
    (window,) = one(r"retried for (\w+) runs")
    words = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
             "eight": 8, "nine": 9, "ten": 10, "twelve": 12, "twenty": 20}
    assert words.get(window, window) == ledger.FILL_WINDOW_RUNS, (
        f"README says forward returns are retried for {window} runs; "
        f"ledger.FILL_WINDOW_RUNS is {ledger.FILL_WINDOW_RUNS}")

    def cron_utc(name):
        doc = yaml.safe_load(_read(f".github/workflows/{name}"))
        crons = [c["cron"].split() for c in doc[True]["schedule"]]
        return sorted((int(hour), int(minute)) for minute, hour, *_rest in crons)

    (edt_h, m), (est_h, m2) = cron_utc("evening.yml")
    assert m == m2 and est_h == edt_h + 1, "evening.yml's two crons are not an EDT/EST pair"
    evening_et = f"{(edt_h - 4) % 12 or 12}:{m:02d} PM ET"
    assert f"{edt_h:02d}:{m:02d} UTC under EDT, {est_h:02d}:{m:02d} UTC under EST" in readme
    (edt_h, m), (est_h, m2) = cron_utc("morning.yml")
    assert m == m2 and est_h == edt_h + 1, "morning.yml's two crons are not an EDT/EST pair"
    morning_et = f"{edt_h - 4}:{m:02d} AM ET"
    assert f"({edt_h:02d}:{m:02d} / {est_h:02d}:{m:02d} UTC)" in readme
    # EVERY clock time README prints, not "at least one that is right": the
    # first version of this asserted `in`, and changing one of the two "8:30
    # AM ET" mentions left the other to satisfy it -- a mutation survived.
    mentioned = set(re.findall(r"\b\d{1,2}:\d{2} [AP]M ET\b", readme))
    assert mentioned == {evening_et, morning_et}, (
        f"README mentions {sorted(mentioned)}; the crons say {evening_et} and {morning_et}")

    close = scanner.SESSION_COMPLETE_ET
    assert f"{close.hour}:{close.minute:02d} ET" in _read(".env.example"), (
        f".env.example does not name the {close.hour}:{close.minute:02d} ET close "
        "the session arithmetic keys on")


def test_the_cost_paragraph_does_its_own_arithmetic():
    """README's Costs section states its inputs -- image size, token counts,
    prices, the call cap, the cache multipliers -- and then four conclusions:
    the break-even, the saving, and the two nightly figures.

    Two of the four were wrong from the day they were written, and CLAUDE.md
    quoted a third figure for one of them: break-even was given as 1.25/0.9
    = 1.4 calls, which charges the whole cache write against the reads as if
    the first call were otherwise free (it is 1 + 0.25/0.9 = 1.28), and the
    cached night was $0.13 in one file and rounded from a different token
    count than the $0.24 beside it in the other. Every conclusion is
    recomputed here from the inputs the paragraph itself states, so the
    numbers can only be wrong together.
    """
    from src import pipeline

    readme = _read("README.md")
    costs = readme[readme.index("## Costs"):]

    def num(pattern):
        found = re.search(pattern, costs, re.S)
        assert found, f"README's Costs section no longer states {pattern!r}"
        return float(found.group(1).replace(",", ""))

    width, height = re.search(r"PNG is (\d+)x(\d+)", costs).groups()
    image = round(int(width) * int(height) / 750)
    assert image == num(r"which is (\d+) image tokens")
    system = num(r"~([\d,]+)\s+tokens of system prompt")
    metrics = num(r"metrics block ~([\d,]+)")
    per_call = system + metrics + image
    assert abs(per_call - num(r"so ~([\d,]+) input tokens")) <= 50
    out = num(r"~(\d+) out per call")
    price_in, price_out = (float(x) for x in re.search(r"\$(\d+)/\$(\d+) per Mtok", costs).groups())
    calls = num(r"≤(\d+) scoring calls/run")
    assert calls == pipeline.MAX_TO_SCORE
    write, read = num(r"cache write costs ([\d.]+)x"), num(r"a read ([\d.]+)x")

    uncached = calls * (per_call * price_in + out * price_out) / 1e6
    cached = ((system * write + (per_call - system)) * price_in + out * price_out
              + (calls - 1) * ((system * read + (per_call - system)) * price_in + out * price_out)) / 1e6
    break_even = 1 + (write - 1) / (1 - read)

    assert num(r"break-even the second call \(([\d.]+) calls\)") == round(break_even, 2)
    assert num(r"a full night (\d+)% cheaper") == round(100 * (1 - cached / uncached))
    assert num(r"\$([\d.]+) this\s+paragraph used to quote") == round(uncached, 2)
    assert num(r"about \$([\d.]+) a\s+run") == round(cached, 2)
    assert num(r"roughly \$(\d+) a year") == round(cached * 252)
    assert readme.count(f"~${round(cached, 2):.2f}") == 1, "the summary table quotes a different nightly figure"
    for doc in ("CLAUDE.md", "src/scorer.py"):
        # Comment markers and line wraps are not words: the scorer's copy
        # wraps between the percentage and "cheaper".
        text = " ".join(_read(doc).replace("#", " ").split())
        assert f"{round(break_even, 2)} calls" in text, f"{doc} quotes a different break-even"
        assert f"{round(100 * (1 - cached / uncached))}% cheaper" in text, f"{doc} quotes a different saving"


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


def test_the_documented_return_bases_are_the_ones_the_ledger_writes():
    """README's data-contract bullets name both bases and the example the
    second one was measured on. The example is recomputed here from the
    ledger's own function, so the sentence cannot drift from the code."""
    import pandas as pd
    from src import ledger

    readme = _read("README.md")
    bullet = readme[readme.index("- `forward_returns.from_open`"):]
    bullet = bullet[:bullet.index("\n\n")]
    example = re.search(r"burst\s+close (\d+), next open (\d+), next close (\d+) records `d1` ([+-][\d.]+)% and\s+`from_open.d1` ([+-][\d.]+)%", bullet)
    assert example, "README no longer states the worked example"
    close0, open1, close1, d1, o1 = example.groups()
    index = pd.bdate_range(end="2026-08-31", periods=2, name="timestamp")
    df = pd.DataFrame({"Open": [float(close0), float(open1)], "Close": [float(close0), float(close1)],
                       "Volume": [1, 1]}, index=index)
    got = ledger.forward_returns(df, index[0].date().isoformat())
    assert (got["d1"], got["from_open"]["d1"]) == (float(d1), float(o1)), (got, example.groups())
    assert "enough_from_open" in bullet and "one basis at a time" in bullet
    contract = "\n".join(ledger.CONTRACT_INVARIANTS)
    assert "from_open" in contract and "enough_from_open" in contract


def test_the_email_and_the_page_print_one_figure_for_one_floor():
    """The email said "$12,400,000/day" beside a page saying "$12.4M/day" for
    the same run.liquidity.floor. Both true, and the shape this project counts
    as a defect. The page's big() and ordinal() are cut out of docs/index.html
    and executed through node against the same values src.emailer formats, so
    the two rules cannot drift apart silently."""
    import json
    import shutil
    import subprocess
    from src import emailer

    if not shutil.which("node"):
        pytest.skip("node is not on this machine; the smoke test runs the page")
    page = _read("docs/index.html")
    fns = []
    for name in ("big", "ordinal"):
        start = page.index(f"function {name}(")
        end = page.index("\n  }\n", start) + 4
        fns.append(page[start:end])
    values = [12_400_000, 190_247_596.4, 4.5e9, 850_000, 999, 1e6, 359_000_000.0]
    pctiles = [30, 1, 2, 3, 11, 12, 13, 21, 22, 23, 30.0]
    script = "\n".join(fns) + f"""
    console.log(JSON.stringify({{
      dollars: {json.dumps(values)}.map((v) => '$' + big(v)),
      ordinals: {json.dumps(pctiles)}.map(ordinal),
    }}));"""
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    assert out["dollars"] == [emailer.compact_dollars(v) for v in values]
    assert out["ordinals"] == [emailer.ordinal(p) for p in pctiles]
    assert emailer.ordinal(1) == "1st" and emailer.ordinal(22) == "22nd" and emailer.ordinal(13) == "13th"


def test_the_published_contract_names_every_outcome_a_row_can_carry():
    """docs/data.json carries its own `_contract`, and README says its
    `last_outcome` bullet is what that block documents.

    The block named three outcomes and README four: `veto_up_days`, the word
    that exists so a 6/6 name refused by an absolute rule is never called a
    gate rejection, was absent from the file's own documentation of the field
    -- the collapse README forbids, in the contract itself. Every word the
    email and the page can render is checked against the published sentences,
    on both the last_outcome field and gated_out[].reason, and README's own
    bullet is held to the same set.
    """
    from src import emailer, ledger, pipeline

    words = set(emailer.LAST_OUTCOME) | set(pipeline.VETO_REASONS.values()) | {ledger.LIQUIDITY_REASON}
    contract = "\n".join(ledger.CONTRACT_INVARIANTS)
    missing = sorted(w for w in words if f"'{w}'" not in contract)
    assert not missing, (
        f"src.ledger.CONTRACT_INVARIANTS never names {missing}, so the file's own "
        "documentation of last_outcome / gated_out[].reason is missing a word every "
        "surface can render")
    readme = _read("README.md")
    bullet = readme[readme.index("`last_outcome` is what happened"):]
    bullet = bullet[:bullet.index("\n\n")]
    assert not [w for w in words if f"`{w}`" not in bullet], (
        "README's last_outcome bullet does not name every outcome word")
    # And the two renderers: a reason word no surface has words for is a row
    # the reader is told nothing about, which is how rule 6's refusals were
    # lost for a round. The page holds the same map twice (a long and a
    # short form) and both are read as text, since a key present in one and
    # missing from the other renders the fallback phrase for the other.
    unscored = words - {"scored"}
    assert unscored <= set(emailer.LAST_OUTCOME), (
        f"src.emailer.LAST_OUTCOME has no words for {sorted(unscored - set(emailer.LAST_OUTCOME))}")
    page = _read("docs/index.html")
    for table in ("LAST_OUTCOME", "OUTCOME_SHORT"):
        block = page[page.index(f"var {table} = {{"):]
        block = block[:block.index("};")]
        assert not [w for w in unscored if f"{w}:" not in block], (
            f"docs/index.html's {table} has no words for "
            f"{sorted(w for w in unscored if f'{w}:' not in block)}")


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


def test_the_feed_override_reaches_the_scheduled_run():
    """src.scanner supports SCAN_FEED precisely so a refused feed can be
    switched without a code change, and the evening workflow did not pass it --
    so the escape hatch existed everywhere except the one place that needs it.
    A variable, not a secret: it is not a credential, and an unset one expands
    to '' which _feed_from_env() reads as "use the default"."""
    evening = _read(".github/workflows/evening.yml")

    assert "SCAN_FEED: ${{ vars.SCAN_FEED }}" in evening, (
        "evening.yml does not forward SCAN_FEED; a refused data feed could "
        "then only be fixed by editing the workflow"
    )
    assert "SCAN_FEED" in _read(".env.example")


def test_a_degraded_evening_run_still_commits_the_night_it_paid_for():
    """Exit 2 means the run WORKED and noted a problem. The record must survive.

    A `run:` step fails on any non-zero code, and the persist step's `if:`
    carried no status function — so Actions ANDed success() into it and skipped
    the commit-back on every degraded night. The cost is the whole point of the
    project: exit 2 means the scan ran, the charts rendered, up to MAX_TO_SCORE
    Claude calls were PAID FOR, docs/data.json and docs/ledger.json were written
    complete, and the shortlist was mailed — and then the record died with the
    container. src.pipeline's own contract is that a degraded run publishes;
    there is a test named for it.

    Not a corner case. One chart that will not render is enough, as is one
    Claude fallback, >10% stale symbols, an unreadable history, or a mode/clock
    disagreement. This repo's own 30-session fixture is 2 degraded in 30, and
    its newest run is one of them — so the canonical picture of "what docs/
    holds after a month" contains two nights this workflow could not have kept.

    Asserted on the PARSED yaml rather than on the text, because the thing that
    went wrong is a structural property of the condition, not a spelling.
    """
    import yaml

    workflow = yaml.safe_load(_read(".github/workflows/evening.yml"))
    steps = workflow["jobs"]["scan"]["steps"]
    by_name = {s.get("name"): s for s in steps}

    pipeline = by_name["Run evening pipeline"]
    persist = by_name["Persist the run"]
    verdict = by_name["Report the pipeline's verdict"]

    assert pipeline.get("id") == "pipeline", (
        "the pipeline step needs an id for the persist step to read its code")
    # It must NOT raise: a raising step makes success() false and skips persist.
    assert "$GITHUB_OUTPUT" in pipeline["run"], (
        "the pipeline step must capture its exit code, not raise it")

    condition = " ".join(str(persist["if"]).split())
    assert "steps.pipeline.outputs.code == '2'" in condition, (
        f"the persist step does not run on a DEGRADED night: {condition!r}. "
        "A night that was paid for and published would be thrown away.")
    assert "steps.pipeline.outputs.code == '0'" in condition, condition
    assert "'1'" not in condition, (
        f"a FAILED run has nothing trustworthy to commit: {condition!r}")

    # The same defect one stage later. The record is written BEFORE the email,
    # so a run that dies delivering it has scanned, rendered, paid for every
    # Claude call and written a complete docs/ -- and used to exit 1 for it,
    # the same code as a preflight that spent nothing. Read off src.pipeline's
    # constant rather than written as "3", so renumbering the code cannot make
    # this pass while the workflow keeps the old number.
    from src import pipeline as pipe
    assert f"steps.pipeline.outputs.code == '{pipe.EXIT_FAILED_AFTER_PUBLISH}'" in condition, (
        f"the persist step throws away a night that failed only at the email: "
        f"{condition!r}")

    # And the colour must be unchanged — a job that goes green on a failed run
    # is the opposite of the mistake being fixed.
    assert "steps.pipeline.outputs.code" in str(verdict["run"]), verdict["run"]
    assert list(by_name).index("Report the pipeline's verdict") > \
        list(by_name).index("Keep the run's artifacts"), (
        "the verdict must be raised AFTER the artifact upload, or a degraded "
        "night loses its 30-day backup copy too")


def test_the_ledgers_projected_size_is_what_measuring_it_says():
    """README quotes a raw and a gzipped megabyte figure for a full year of
    docs/ledger.json, and the page's "load only when asked" design is argued
    from them. They were 8.8 and 0.59 and had been stale since the 3.3 audit
    grew both row types -- the same class as the test count and the dashboard
    check count, and the third number in this repo to rot the same way.

    Re-measured rather than restated: tools/measure_ledger.py builds the file
    with the real writer and the real rows. Tolerant to a hundredth, because
    the assertion is that README is not WRONG, not that a megabyte figure is
    quoted to the byte.
    """
    import importlib.util
    import re

    spec = importlib.util.spec_from_file_location(
        "measure_ledger", ROOT / "tools" / "measure_ledger.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    measured = module.measure()

    readme = _read("README.md")
    raw, gz = re.search(
        r"projects to about ([\d.]+) MB raw\s*\nand \*\*([\d.]+) MB gzipped\*\*", readme
    ).groups()

    assert abs(float(raw) - measured["raw_mb"]) < 0.01, (
        f"README says {raw} MB raw; measuring says {measured['raw_mb']:.2f}. "
        "Run python tools/measure_ledger.py and sweep it.")
    assert abs(float(gz) - measured["gzip_mb"]) < 0.01, (
        f"README says {gz} MB gzipped; measuring says {measured['gzip_mb']:.2f}. "
        "Run python tools/measure_ledger.py and sweep it.")


def _persist_message_fragment() -> str:
    """The lines of evening.yml's persist step that choose the commit message.

    Cut out of the real workflow rather than retyped, so the test runs what
    Actions runs. Bounded by the `SESSION=` assignment and the `fi` that ends
    the branch it feeds.
    """
    import yaml

    workflow = yaml.safe_load(_read(".github/workflows/evening.yml"))
    step = {s.get("name"): s for s in workflow["jobs"]["scan"]["steps"]}["Persist the run"]
    lines = step["run"].splitlines()
    start = next(i for i, line in enumerate(lines) if "SESSION=$(" in line)
    end = next(i for i, line in enumerate(lines) if line.strip() == "fi")
    return "\n".join(lines[start:end + 1])


@pytest.mark.parametrize("snapshot, expected", [
    # The ordinary night. Under EST the evening run starts at 23:16 UTC, so a
    # run over ~44 minutes used to commit under TOMORROW's date.
    ('{"run": {"date": "2026-01-05", "type": "evening"}}', "run 2026-01-05"),
    # The case that made this worth fixing rather than noting: a
    # SCAN_SESSION_DATE backfill scans an old session, and the commit labelled
    # it with today. That is the silent relabelling step 10 exists to end, in
    # the one artifact step 10 did not reach.
    ('{"run": {"date": "2025-11-14", "type": "evening"}}', "run 2025-11-14"),
])
def test_the_commit_back_names_the_session_it_scanned(tmp_path, snapshot, expected):
    """Run the workflow's own lines against a stub `git`, the way this repo
    traced the push loop -- reading them proves nothing about what `sh` does
    with `$(...)` and `[ -n ]`."""
    import subprocess

    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "data.json").write_text(snapshot)
    stub = tmp_path / "bin"
    stub.mkdir()
    (stub / "git").write_text('#!/bin/sh\necho "GIT $*"\n')
    (stub / "git").chmod(0o755)

    out = subprocess.run(["sh", "-c", _persist_message_fragment()], cwd=tmp_path, text=True,
                         capture_output=True,
                         env={"PATH": f"{stub}:/usr/bin:/bin", "HOME": str(tmp_path)})

    assert out.stdout.strip() == f"GIT commit -m {expected}", (out.stdout, out.stderr)


def test_a_snapshot_it_cannot_read_says_the_date_is_a_commit_time(tmp_path):
    """The fallback must not quietly pass a clock off as a session -- which is
    the whole defect, one level down. Exercised on both ways the read fails."""
    import datetime
    import subprocess

    stub = tmp_path / "bin"
    stub.mkdir()
    (stub / "git").write_text('#!/bin/sh\necho "GIT $*"\n')
    (stub / "git").chmod(0o755)
    (tmp_path / "docs").mkdir()
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    for broken in ("not json at all", None):
        if broken is None:
            (tmp_path / "docs" / "data.json").unlink()
        else:
            (tmp_path / "docs" / "data.json").write_text(broken)
        out = subprocess.run(["sh", "-c", _persist_message_fragment()], cwd=tmp_path,
                             text=True, capture_output=True,
                             env={"PATH": f"{stub}:/usr/bin:/bin", "HOME": str(tmp_path)})
        assert out.stdout.strip() == f"GIT commit -m run (session unknown; committed {today})", (
            f"broken={broken!r}: {out.stdout!r}")


def test_every_module_this_repo_imports_is_a_dependency_it_declares():
    """A test that imports what CI does not have passes here and errors there.

    That is not hypothetical: `import yaml` went into this file's workflow
    checks, this sandbox happens to have PyYAML installed, the runner does not,
    and four tests errored on three consecutive pushes while the suite was
    green locally. Same shape as the CPython 3.11-vs-3.12 difference CLAUDE.md
    records -- what is on this machine is not what CI has -- and the same fix:
    something mechanical, because remembering did not work.

    Walks the AST rather than grepping for "import", so a name inside a string
    or a comment is not a dependency and a conditional import still is. Maps
    each module to the distribution that PROVIDES it -- `yaml` comes from
    PyYAML and `alpaca` from alpaca-py, and neither is guessable from the
    module name.
    """
    import ast
    import importlib.metadata
    import sys

    def normalise(name: str) -> str:
        return re.sub(r"[-_.]+", "-", name).lower()

    declared = set()
    for name in ("requirements.txt", "requirements-dev.txt"):
        for line in _read(name).splitlines():
            line = line.split("#")[0].strip()
            if line and not line.startswith("-"):
                declared.add(normalise(re.split(r"[<>=!\[;]", line)[0].strip()))

    imported = set()
    for path in sorted(ROOT.glob("src/*.py")) + sorted(ROOT.glob("tests/**/*.py")) \
            + sorted(ROOT.glob("tools/*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                imported |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module.split(".")[0])

    provides = importlib.metadata.packages_distributions()
    local = {"src", "tests", "tools", "synthetic", "fakes", "conftest"}
    missing = {}
    for module in sorted(imported):
        if module in sys.stdlib_module_names or module in local:
            continue
        dists = provides.get(module)
        assert dists, (
            f"{module!r} is imported but no installed distribution provides it; "
            "this machine cannot say what to declare for it")
        if not any(normalise(d) in declared for d in dists):
            missing[module] = dists

    assert not missing, (
        f"imported but declared in neither requirements file: {missing}. "
        "CI installs requirements-dev.txt and nothing else, so these error there "
        "while passing here.")


def test_no_module_defines_the_same_name_twice():
    """A shadowed definition is the fourth shape of test that cannot fail, and
    the cheapest to produce: Python keeps the LAST one silently, so a test
    defined twice runs once and a test moved rather than copied stops running
    with nothing to see. It happened twice in this project's rebuild, both
    times while relocating a test near work that was rewriting it, and both
    times the only symptom was a failure message that did not change after an
    edit that should have changed it.

    Walks every top-level def and class in src/, tests/ and tools/, because
    the same shape in a module is a function that silently is not the one its
    callers were written against.
    """
    import ast

    clashes = {}
    for path in sorted(ROOT.glob("src/*.py")) + sorted(ROOT.glob("tests/**/*.py")) \
            + sorted(ROOT.glob("tools/*.py")):
        seen: dict[str, list[int]] = {}
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                seen.setdefault(node.name, []).append(node.lineno)
        for name, at in seen.items():
            if len(at) > 1:
                clashes[f"{path.relative_to(ROOT)}::{name}"] = at

    assert not clashes, (
        f"defined more than once, so only the last one exists: {clashes}")


def _guard_shell() -> str:
    """The backup-cron guard's own lines, cut out of evening.yml, with the three
    Actions expressions it reads turned into environment variables."""
    import yaml

    workflow = yaml.safe_load(_read(".github/workflows/evening.yml"))
    step = next(s for s in workflow["jobs"]["scan"]["steps"] if s.get("id") == "guard")
    return (step["run"]
            .replace("${{ github.event.schedule }}", "$EVENT_SCHEDULE")
            .replace("${{ github.event_name }}", "$EVENT_NAME")
            .replace("${{ github.repository }}", "x/y"))


def _run_guard(tmp_path, *, artifacts: list[dict], event: str, schedule: str,
               today_et: str, offset: str) -> str:
    """Run the real guard under bash with a stub gh (real jq over a canned
    payload) and a stub date, and return the go= line it printed."""
    import json
    import shutil
    import subprocess

    assert shutil.which("jq"), "the guard's own filter needs jq; the runner has it"
    stub = tmp_path / "bin"
    stub.mkdir(exist_ok=True)
    (stub / "gh").write_text(
        "#!/bin/sh\nwhile [ $# -gt 0 ]; do [ \"$1\" = -q ] && { shift; F=\"$1\"; }; shift; done\n"
        "jq -r \"$F\" \"$PAYLOAD\"\n")
    (stub / "date").write_text(
        "#!/bin/sh\ncase \"$*\" in *%z*) echo \"$FAKE_OFFSET\";; *) echo \"$FAKE_TODAY\";; esac\n")
    for f in (stub / "gh", stub / "date"):
        f.chmod(0o755)
    payload = tmp_path / "artifacts.json"
    payload.write_text(json.dumps({"artifacts": artifacts}))
    out = subprocess.run(["bash", "-c", _guard_shell()], cwd=tmp_path, text=True, capture_output=True,
                         env={"PATH": f"{stub}:/usr/bin:/bin", "HOME": str(tmp_path),
                              "PAYLOAD": str(payload), "EVENT_NAME": event, "EVENT_SCHEDULE": schedule,
                              "FAKE_TODAY": today_et, "FAKE_OFFSET": offset,
                              "GITHUB_OUTPUT": str(tmp_path / "out")})
    assert out.returncode == 0, out.stderr
    return (tmp_path / "out").read_text().strip()


EDT_CRON, EST_CRON = "16 22 * * 1-5", "16 23 * * 1-5"


@pytest.mark.parametrize("label, artifacts, schedule, today, offset, expected", [
    ("nothing ran today: the cron fires",
     [], EDT_CRON, "2026-09-04", "-0400", "go=true"),
    # A preflight failure, or a Run-workflow click at lunch to test the
    # secrets, uploads an artifact too. It used to count as "evening run
    # already completed today" and silence that night's cron -- read off the
    # Actions API: both failed 4 Sep runs left an 11,675-byte evening-<id>.
    ("a FAILED run today left an artifact: the cron still fires",
     [{"name": "evening-failed-33927201865", "created_at": "2026-09-04T22:51:27Z"}],
     EDT_CRON, "2026-09-04", "-0400", "go=true"),
    ("a run PUBLISHED today's session: the backup stands down",
     [{"name": "evening-2026-09-04-33927201865", "created_at": "2026-09-04T22:51:27Z"}],
     EDT_CRON, "2026-09-04", "-0400", "go=false"),
    # Under EST the night starts at 23:16 UTC, so a run over ~44 minutes
    # uploads under TOMORROW's UTC date. Keyed on the UTC creation date, that
    # artifact silenced the following night's cron; keyed on the session in
    # its name, it does not.
    ("last night's EST run uploaded after midnight UTC: tonight's cron fires",
     [{"name": "evening-2026-12-01-999", "created_at": "2026-12-02T00:03:11Z"}],
     EST_CRON, "2026-12-02", "-0500", "go=true"),
    ("a manual dispatch always runs, whatever the artifacts say",
     [{"name": "evening-2026-09-04-1"}], "", "2026-09-04", "-0400", "go=true"),
    ("the cron for the OTHER offset is the no-op",
     [], EST_CRON, "2026-09-04", "-0400", "go=false"),
])
def test_the_backup_cron_guard_counts_published_sessions_not_uploads(
    tmp_path, label, artifacts, schedule, today, offset, expected
):
    """Traced through the guard's own shell against a stub gh that runs the
    guard's own jq filter, the way the persist step was traced: reading the
    step proves nothing about what bash and jq do with it."""
    event = "workflow_dispatch" if schedule == "" else "schedule"
    assert _run_guard(tmp_path, artifacts=artifacts, event=event, schedule=schedule,
                      today_et=today, offset=offset) == expected, label


def test_the_artifact_is_named_after_the_session_only_when_the_run_published():
    """The other half of the guard: the name it counts must be one a failed
    run cannot produce. Asserted on the parsed YAML's expression."""
    import yaml

    from src import pipeline as pipe

    workflow = yaml.safe_load(_read(".github/workflows/evening.yml"))
    steps = {s.get("name"): s for s in workflow["jobs"]["scan"]["steps"]}
    name = " ".join(str(steps["Keep the run's artifacts"]["with"]["name"]).split())
    pipeline_step = steps["Run evening pipeline"]["run"]

    assert "steps.pipeline.outputs.session" in name
    assert "evening-failed-" in name
    for code in (pipe.EXIT_OK, pipe.EXIT_DEGRADED, pipe.EXIT_FAILED_AFTER_PUBLISH):
        assert f"steps.pipeline.outputs.code == '{code}'" in name, (
            f"a run that exits {code} published and must be named by its session")
    assert f"steps.pipeline.outputs.code == '{pipe.EXIT_FAILED}'" not in name, (
        "a preflight failure published nothing and must not claim a session")
    assert 'echo "session=$session" >> "$GITHUB_OUTPUT"' in pipeline_step, (
        "the pipeline step must export the session the artifact is named after")


def test_the_pages_fallback_sentence_states_the_scorers_own_map():
    """The page said a fallback score is "passes ÷ checks × 10". The code has
    mapped the pass count to the LOW end of its rubric band since step 8, and
    the fixture was hand-typed to the old arithmetic -- so a real 5/6 fallback
    printed 7.0 directly under a sentence whose formula gives 8.3. The sentence
    now states the map, and this reads its numbers back against the scorer."""
    from src.scorer import _fallback_score

    page = _read("docs/index.html")
    sentence = re.search(r"When a scoring call fails[^;]*?\(([^)]*)\)", page)
    assert sentence, "the fallback sentence is gone from the page"
    stated = dict(re.findall(r"(\d)/6 scores (\d+)", sentence.group(1)))
    assert stated, sentence.group(1)
    for passes, score in stated.items():
        real = _fallback_score({"passes": int(passes), "total": 6, "summary": ""})
        assert float(score) == real, f"{passes}/6: page says {score}, the scorer gives {real}"
    assert "÷" not in page.split("When a scoring call fails")[1][:400]
