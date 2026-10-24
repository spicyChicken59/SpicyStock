"""The docs are true for the code as it stands: every number README and
.env.example quote is read off the module that owns it, the inventories
(workflows, fixtures, layout, problem words) are the ones that exist, and
the rulebook's bands are the grader's. Prose still needs a human; this is
the mechanically checkable part of the standing doc-sweep rule."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from src import breadth, grader, pipeline, plan, quality, record, report, scans, universe
from tools import make_fixture

ROOT = Path(__file__).resolve().parent.parent
def prose(path: Path) -> str:
    """The file with its line wraps collapsed, so a sentence is matched as a
    sentence and not as the width it happened to be wrapped at."""
    return re.sub(r"[ \t]*\n[ \t]*", " ", path.read_text())


README_RAW = (ROOT / "README.md").read_text()
README = prose(ROOT / "README.md")
ENV = prose(ROOT / ".env.example")
CLAUDE_MD = prose(ROOT / "CLAUDE.md")
STRATEGY = prose(ROOT / "knowledge" / "strategy.md")
METHOD = prose(ROOT / "knowledge" / "method.md")


def every(text: str, pattern: str) -> list[str]:
    return re.findall(pattern, text)


# ------------------------------------------------------------- README -----
def test_the_readme_quotes_the_pipelines_own_numbers():
    assert f"up to {['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve'][pipeline.MAX_READS]}" in README
    assert f"{pipeline.LOOKBACK_DAYS} sessions of daily bars" in README
    assert f"{int(pipeline.FETCH_BUDGET_SECONDS)}-second budget" in README
    assert "Fewer than half the intended stocks with usable" in README and pipeline.MIN_COVERAGE_FRACTION == 0.5
    assert f"{market_holdback()} minutes behind the clock" in README


def market_holdback() -> str:
    from src import market_data
    return {16: "sixteen"}[market_data.SIP_HOLDBACK_MINUTES]


def test_the_readme_quotes_the_scans_and_the_universe_floors():
    assert f"c/c1 >= {scans.BURST_RATIO} and v > v1 and v >= {scans.MIN_VOLUME}" in README
    assert f"c - o >= {scans.DOLLAR_MOVE:.2f} and v > {scans.MIN_VOLUME}" in README
    assert f"${universe.MIN_PRICE:g} session-close policy" in README
    assert "227-name seed" in README
    seed = [l for l in (ROOT / "data" / "symbols.txt").read_text().splitlines() if l and not l.startswith("#")]
    assert len(seed) == 227


def test_the_readme_quotes_the_account_defaults_and_the_regime_sizes():
    assert f"default ${plan.DEFAULT_EQUITY:,.0f}, {plan.DEFAULT_RISK_PCT:g}% risk, {plan.DEFAULT_MAX_POSITION_PCT:g}% cap, four slots" in README
    assert plan.DEFAULT_MAX_OPEN_POSITIONS == 4
    # the four prices the plan keeps apart, each quoted from its own constant
    assert f"still inside his {plan.MAX_STOP_PCT:g}% line" in README
    assert (f"`min(close +{plan.ENTRY_ABOVE_PCT:g}%, floor_to_cents(stop / "
            f"(1 - plan.MAX_STOP_PCT/100)))`") in README
    assert f"(`day2_spent_above`, the close +{plan.ENTRY_ABOVE_PCT:g}%)" in README
    assert f"(`planned_entry`), the close +{plan.ASSUMED_SLIPPAGE_PCT:g}% capped at that limit" in README
    assert f"`stop < trigger < limit`" in README
    assert breadth.SIZE_MULTIPLIER == {"green": 1.0, "yellow": 0.5, "red": 0.0}
    assert "yellow (half size, A+ only)" in README and pipeline.YELLOW_GRADES == ("A+",)
    assert "red (no new longs" in README


def test_the_readme_quotes_the_scorecards_rules():
    assert f"rates only from {['twenty'][0]} settled" in README and record.SCORECARD_MIN_PLANS == 20
    assert "everything settles by day 5" in README and plan.FINAL_EXIT_DAY == 5
    assert f"a half sold at +{plan.SELL_HALF_PCT:g}% or at day {plan.SELL_HALF_DAY}" in README
    assert "every pick from the last five sessions" in README and record.OPEN_PLAN_SESSIONS == 5


def test_the_readme_names_the_exit_codes_and_every_problem_word():
    assert "**0** clean, **1** failed before" in README and "**2** degraded but published" in README \
        and "**3** published but the email failed" in README
    for kind in report.PROBLEM_KINDS:
        assert f"`{kind}`" in README, kind
    assert f"one of {['seven'][0]} words" in README and len(report.PROBLEM_KINDS) == 7


def test_the_readme_names_the_crons_and_the_bonde_median():
    assert "6:16 PM ET" in README and "8:16 PM ET" in README
    assert "Bonde's median night is 239" in README
    page = (ROOT / "docs" / "app.js").read_text()
    assert "const BONDE_MEDIAN_NIGHT = 239;" in page


def test_the_page_reads_pending_against_stale_off_the_record_and_keeps_one_sentence_per_recovery_policy():
    """No fixed hour on the page decides pending against stale: the boundary is
    the record's calendar (the next session's open) and the slot words are its
    archived policy's (src/delivery.py). The page keeps one sentence per
    recovery-policy key, as it does per timing limit, and the two lists are
    held equal here; the README says the same in words."""
    from src import delivery
    page = (ROOT / "docs" / "app.js").read_text()
    assert "PENDING_UNTIL_HOUR" not in page
    block = re.search(r"const RECOVERY_WORDS = \{\n(.*?)\n  \};", page, re.S).group(1)
    keys = re.findall(r"^\s*(\w+): '", block, re.M)
    assert tuple(keys) == delivery.RECOVERY_POLICIES
    assert "`run.delivery`" in README and "until the next session opens" in README
    for slot in (delivery.EVENING_PRIMARY_ET, delivery.EVENING_RETRY_ET):
        assert f"{slot.hour - 12}:{slot.minute:02d} PM ET" in README
    assert "run pending · past both slots" in README and "delivery.py (" in README
    assert "run.delivery" in ENV and "until the next session opens" in ENV


def test_the_readme_lists_the_fixture_variants_the_generator_makes():
    listed = re.search(r"\(`(.*?)`\)", README.split("one per state the page can be in")[1]).group(1)
    assert tuple(listed.split("`, `")) == make_fixture.VARIANTS
    sequels = re.search(r"sequels of the `full` night \(`(.*?)`\)", README).group(1)
    assert tuple(sequels.split("`, `")) == make_fixture.SEQUELS
    for variant in make_fixture.VARIANTS + make_fixture.SEQUELS:
        assert (ROOT / "tests" / "fixtures" / "page" / f"{variant}.json").exists(), variant


def test_the_readme_layout_names_files_that_exist():
    block = README_RAW.split("## Layout")[1].split("```")[1]
    names = re.findall(r"[\w.-]+\.(?:py|json|js|css|html|md|yml)", block)
    missing = [n for n in names if not list(ROOT.rglob(n))]
    assert not missing, missing
    # and the reverse for the page's own modules: a docs/app-*.js the layout
    # does not name is a module that shipped undocumented
    for module in (ROOT / "docs").glob("app*.js"):
        assert module.name in block, f"README's layout does not name docs/{module.name}"
    assert set(re.findall(r"(\w+)\.py", block.split("src/")[1].split("docs/")[0])) == \
        {p.stem for p in (ROOT / "src").glob("*.py") if p.stem != "__init__"}


def test_the_readme_names_the_six_cover_sentences():
    for h1 in (report.H1_STAND_ASIDE, report.H1_KEEP_CASH, report.H1_CLOSED):
        assert h1 in README, h1
    assert "Trade next session. N A-quality" in README and "Trade small. N A+" in README and "No verdict for" in README


def test_the_readme_and_the_env_example_name_every_required_variable():
    from src import market_data
    required = set(market_data.REQUIRED_ENV) | set(grader.REQUIRED_ENV) | set(report.REQUIRED_ENV) | {"RESEND_FROM"}
    for name in required:
        assert f"`{name}`" in README, name
        assert name in ENV, name
    for name in ("SCAN_FEED", "SCAN_UNIVERSE", "ACCOUNT_EQUITY", "RISK_PCT", "SCAN_SESSION_DATE", "SCAN_SEND_EMAIL",
                 "CLAUDE_MODEL", "MAX_POSITION_PCT", "MAX_OPEN_POSITIONS"):
        assert name in ENV, name


# -------------------------------------------------------- .env.example ----
def test_the_env_example_quotes_the_read_cap_and_the_universe_floors():
    assert f"MAX_READS ({pipeline.MAX_READS})" in ENV
    assert f"${universe.MIN_PRICE:g} session-close policy" in ENV
    assert f"data/symbols.txt ({227} names)" in ENV
    assert f"$10,000, {plan.DEFAULT_RISK_PCT:g}% risk a trade" in ENV and plan.DEFAULT_EQUITY == 10_000
    assert "0.25-1%" in ENV and (plan.RISK_PCT_BAND_LOW, plan.RISK_PCT_BAND_HIGH) == (0.25, 1.0)
    assert "sixteen minutes behind the clock" in ENV
    assert "'directory'" in ENV and universe.DEFAULT_MODE == "directory"
    assert "seven days" in ENV and universe.DIRECTORY_MAX_AGE.days == 7


def test_the_env_example_names_no_file_the_run_no_longer_writes():
    for stale in ("ledger.json", "results/", "scorer.py", "ScanConfig", "min_dollar_volume_pctile", "2LYNCH"):
        assert stale not in ENV, stale
        assert stale not in README, stale


# ------------------------------------------------------------ CLAUDE.md ---
def test_claude_md_counts_the_suite():
    n = int(re.search(r"(\d+) tests, the chart check", CLAUDE_MD).group(1))
    collected = collected_tests()
    assert n == collected, f"CLAUDE.md says {n} tests, the suite collects {collected}"


def collected_tests() -> int:
    import subprocess, sys
    out = subprocess.run([sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q", "-p", "no:cacheprovider"],
                         cwd=ROOT, capture_output=True, text=True, timeout=300).stdout
    return int(re.search(r"(\d+) tests? collected", out).group(1))


def test_claude_md_is_short_and_names_the_fixture_count():
    assert len(CLAUDE_MD.splitlines()) <= 150
    every = make_fixture.VARIANTS + make_fixture.SEQUELS
    # the current count is the sentence that names the suite's own; the
    # historical measurement beside it keeps the count it was made over
    assert "the page smoke walks twelve fixtures" in CLAUDE_MD and len(every) == 12


# --------------------------------------------- the page's chart anchors ----
# --------------------------------------------- the sequential fixtures ----
# `next` and `revised` exist so a setup followed on the `full` night can be
# read against a genuinely newer record. What makes them useful is exactly
# what is asserted here: a LATER session that INHERITED the full night (not a
# second first night), two followed symbols gone from the candidates, a newer
# signal for one that stayed, one that has moved stage -- and, for `revised`,
# the SAME session at a different close, which is a correction and never
# another trading day. A regeneration that lost any of these would leave the
# page suite asserting nothing, because the two records would be the same.
SEQUELS = {name: json.loads((ROOT / "tests" / "fixtures" / "page" / f"{name}.json").read_text())
           for name in make_fixture.SEQUELS}


def test_the_sequels_are_a_later_session_that_inherited_the_full_night():
    full = json.loads((ROOT / "tests" / "fixtures" / "page" / "full.json").read_text())
    for name, data in SEQUELS.items():
        assert data["run"]["session"] > full["run"]["session"], name
        # inherited, not seeded afresh: the full night's picks are its open
        # model plans, and its own observations are carried with their `since`
        picked = {p["picked"] for p in data["open_plans"]}
        assert full["run"]["session"] in picked, (name, sorted(picked))
        for sym in ("AAPL", "TSLA"):
            obs = data["observations"]["symbols"][sym]
            assert obs["date"] == data["run"]["session"], (name, sym, obs)
            assert obs["since"] == full["run"]["session"], (name, sym, obs)


def test_the_sequels_move_the_symbols_a_follow_through_reading_needs():
    full = json.loads((ROOT / "tests" / "fixtures" / "page" / "full.json").read_text())
    was_coil = {r["ticker"] for r in full["watchlist"]["top"]}
    for name, data in SEQUELS.items():
        bursts = {b["ticker"] for b in data["bursts"]}
        coils = {r["ticker"] for r in data["watchlist"]["top"] + data["watchlist"]["also_quiet"]}
        # the ticket and the withheld setup have left the record altogether
        assert not ({full["trades"][0], "TSLA"} & (bursts | coils)), (name, sorted(bursts | coils))
        # one burst has burst again: a newer signal for a symbol already followed
        assert "NVDA" in bursts and "NVDA" in {b["ticker"] for b in full["bursts"]}, name
        # and the coil has broken out: a newer signal in the OTHER stage
        assert was_coil and was_coil <= bursts and not (was_coil & coils), (name, sorted(was_coil))


def test_the_revised_fixture_is_a_correction_and_not_another_day():
    a, b = SEQUELS["next"], SEQUELS["revised"]
    assert a["run"]["session"] == b["run"]["session"]
    moved = {sym: (a["observations"]["symbols"][sym]["c"], obs["c"])
             for sym, obs in b["observations"]["symbols"].items()
             if obs["c"] != a["observations"]["symbols"][sym]["c"]}
    assert set(moved) == {"AAPL"}, moved
    was, now = moved["AAPL"]
    assert round(abs(now - was) * 100) == make_fixture.REVISION_CENTS, moved
    assert a["observations"]["symbols"]["AAPL"]["date"] == b["observations"]["symbols"]["AAPL"]["date"]


def test_the_declining_ticket_closes_under_the_stop_its_plan_named():
    """The `next` night's AAPL is under the stop the `full` night's plan named,
    so the page has a real price to speak about there -- and a price below a
    stop reference is a statement about a price, never a fill or a stop-out."""
    full = json.loads((ROOT / "tests" / "fixtures" / "page" / "full.json").read_text())
    plan = next(b["plan"] for b in full["bursts"] if b["ticker"] == "AAPL")
    for name, data in SEQUELS.items():
        assert data["observations"]["symbols"]["AAPL"]["c"] < plan["stop"], (name, plan["stop"])


# The evidence row marks a stretch of chart for a recorded check. Every anchor
# is resolved against a field the run wrote, so the two failures worth pinning
# are a key the grader does not write (a control that would mark nothing) and
# a record that stopped carrying the dates the anchor is resolved against --
# the shape-one-level-in class this repository keeps producing.
PAGE_JS = (ROOT / "docs" / "app.js").read_text()
FULL_FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "page" / "full.json").read_text())


def page_anchors() -> dict[str, str]:
    block = re.search(r"const CHECK_ANCHOR = \{(.*?)\};", PAGE_JS, re.S).group(1)
    return dict(re.findall(r"(\w+):\s*'(\w+)'", block))


def test_the_pages_chart_anchors_name_checks_the_grader_writes():
    anchored = page_anchors()
    assert anchored, "docs/app.js anchors no check to the chart"
    written = {c["key"] for b in FULL_FIXTURE["bursts"] for c in b["quality"]["checks"]}
    assert set(anchored) <= written, (
        f"the page anchors {sorted(set(anchored) - written)}, which quality.py does not write; "
        "the tile would be a button that marks nothing")
    # a check the record dates no range for is shown in words and never drawn:
    # linearity, the trend's age and the run of up days have measurements but
    # no start and end, so anchoring one would mean inventing a region
    undated = {"linearity", "young_trend", "two_days"}
    assert not (set(anchored) & undated), (
        f"{sorted(set(anchored) & undated)} carries no recorded date range; "
        "show its evidence in words instead of drawing a region for it")


def test_the_record_carries_every_field_the_chart_anchors_resolve_against():
    run = FULL_FIXTURE["run"]
    assert run.get("session"), "the record names no session, so no burst day can be found"
    for b in FULL_FIXTURE["bursts"]:
        base = b["quality"]["base"]
        assert {"start", "end", "low", "high"} <= set(base), f"{b['ticker']}'s base carries {sorted(base)}"
        series = b.get("series") or []
        if series:
            dates = [x["date"] for x in series]
            assert run["session"] in dates, f"{b['ticker']}'s archived frame stops before the session it was picked on"
            # the day before the signal is the previous ARCHIVED bar, so there
            # has to be one: a frame that begins at the signal has no prior day
            assert dates.index(run["session"]) > 0, f"{b['ticker']}'s frame begins at the signal"


# ------------------------------------------------------------ rulebook ----
def test_the_rulebook_bands_are_the_graders():
    bands = {g: s for s, g in grader.GRADE_BANDS}
    for grade, floor in bands.items():
        assert re.search(rf"{re.escape(grade)}[^\n]*\b{floor:g}\b", STRATEGY), (grade, floor)
    assert "may only lower" in STRATEGY.lower() or "never raise" in STRATEGY.lower()


def test_the_pinned_floor_is_quoted_from_the_watchlist():
    """The floor under which a price is pinned rather than coiled is one
    constant; the README and the method file quote it from the module."""
    from src import watchlist
    floor = f"{watchlist.MIN_COMPRESS:.2f}"
    assert f"under {floor} of its sixty-session base is pinned" in re.sub(r"\s+", " ", README), floor
    assert f"\u2265 {floor} of it (under that the price is pinned" in re.sub(r"\s+", " ", METHOD), floor


def test_the_method_file_names_every_module_that_holds_a_rule():
    for module in ("universe", "scans", "quality", "breadth", "watchlist", "plan", "record"):
        assert f"src/{module}.py" in METHOD, module


def test_the_walkthroughs_evidence_line_is_the_method_files():
    """The one number the walkthrough's evidence paragraph carries is the
    study's sample, and knowledge/method.md is where it is sourced."""
    page = (ROOT / "docs" / "index.html").read_text()
    assert "n = 10,947" in page and "n=10,947" in METHOD
    assert "gates remove the losing half" in page and "remove the losing half" in METHOD


def test_the_workflow_inventory_the_readme_names_is_the_one_that_exists():
    named = set(re.findall(r"([\w-]+\.yml)", README_RAW.split("## Layout")[1]))
    assert named == {p.name for p in (ROOT / ".github" / "workflows").glob("*.yml")}


def test_the_page_smoke_reads_the_same_problem_sentences_the_page_prints():
    page = (ROOT / "docs" / "app.js").read_text()
    smoke = (ROOT / "tools" / "page_smoke.mjs").read_text()
    for kind in report.PROBLEM_KINDS:
        sentence = json.loads(re.search(rf"    {kind}: (\"[^\n]+\"),?\n", page).group(1))
        head = re.search(rf"{kind}: '([^']+)'", smoke).group(1)
        assert sentence.startswith(head), (kind, sentence, head)
        # the page and the mail print one sentence per kind, the same one
        assert report.PROBLEM_SENTENCES[kind] == sentence, kind
    # and neither guesses why a frame was missing or stale: "the fetch ran out
    # of time" was the mail's sentence on nights whose fetch took a minute; and
    # the one sentence is true of every path that raises the word -- stocks
    # without session bars, scan or checklist errors, and a late bar that the
    # previous publication would have listed (src.followup)
    page_thin = json.loads(re.search(r"    coverage_thin: (\"[^\n]+\"),?\n", page).group(1))
    for sentence in (page_thin, report.PROBLEM_SENTENCES["coverage_thin"]):
        assert all(w in sentence for w in ("missing", "could not be evaluated", "arrived late",
                                           "unknown, not a measured non-match")), sentence
        assert "ran out of time" not in sentence and "answered late" not in sentence
        assert "lack usable session bars" not in sentence, "not true of a late bar or a scan error"


def test_the_readme_and_the_env_example_quote_the_two_tolerances_from_the_modules():
    """The stale tolerance and the reader's refusal limit are each one constant;
    the prose that tells a reader what keeps a night green quotes them."""
    stale = f"at most {pipeline.STALE_TOLERANCE_FRACTION:.0%} of the intended stocks"
    assert stale in README, stale
    # the sessions BEFORE the one evaluated: "the last five" would count tonight's
    bound = f"within the {pipeline.STALE_SESSIONS_MAX} sessions before the session evaluated"
    assert bound in re.sub(r"\s+", " ", README), bound
    quarter = {0.25: "a quarter"}[pipeline.READER_REFUSAL_FRACTION] + " of the night's reads"
    refusal = "more than both " + quarter + " and " + {1: "one"}[pipeline.READER_REFUSAL_MIN]
    assert refusal in README, refusal
    env = re.sub(r"\s*#\s*", " ", (ROOT / ".env.example").read_text())
    assert "credit balance is too low" in env and refusal in env
    assert f"{pipeline.STALE_TOLERANCE_FRACTION:.0%} of the intended stocks" in env and bound in env
    method = re.sub(r"\s+", " ", (ROOT / "knowledge" / "method.md").read_text())
    assert bound in method and "every session" in method
    assert quarter + ", or within " + {1: "one"}[pipeline.READER_REFUSAL_MIN] + " if that is more" in method


def test_the_readme_and_the_env_example_quote_the_reader_archives_bounds_from_the_module():
    """The reader archive's grace, caps and warning are four constants; the
    prose that says when an old tab's copy gives way quotes them."""
    from src import reader
    text = re.sub(r"\s+", " ", README)
    mib = reader.MAX_ARCHIVE_BYTES // (1024 * 1024)
    assert f"{reader.RETENTION_DAYS}-calendar-day retention window" in text
    assert f"capped at {reader.MAX_SIDECARS} objects and {mib} MiB" in text
    assert f"{reader.MAX_OBSERVATION_BYTES // (1024 * 1024)} MiB over the byte cap" in text
    assert f"warns past {reader.RETENTION_WARN_FRACTION:.0%} of either" in text
    env = re.sub(r"\s*#\s*", " ", (ROOT / ".env.example").read_text())
    assert f"keep a {reader.RETENTION_DAYS}-day grace for open tabs; past the {mib} MiB cap" in env


def test_the_readme_and_the_env_example_quote_the_recovery_catalogs_bounds_from_the_module():
    """The recovery catalog's window, caps and warning are constants; the prose
    that says when its oldest records give way quotes them."""
    from src import history
    text = re.sub(r"\s+", " ", README)
    mib = history.CATALOG_BYTES_MAX // (1024 * 1024)
    assert (f"It retains {history.DAYS} calendar days, up to {history.RECORDS_MAX} distinct publications "
            f"and {history.SIGNALS_MAX:,} signals per publication, within {mib} MiB.") in text
    assert f"warns past {history.CATALOG_WARN_FRACTION:.0%} of either" in text
    env = re.sub(r"\s*#\s*", " ", (ROOT / ".env.example").read_text())
    assert (f"the {history.DAYS}-day recovery catalog; past its {history.RECORDS_MAX}-record or "
            f"{mib} MiB cap its oldest records give way") in env
    continuity = re.sub(r"\s+", " ", (ROOT / "docs/continuity/README.md").read_text())
    assert (f"Limits: {history.RECORDS_MAX} publications; {history.SIGNALS_MAX:,} signals per publication; "
            f"256 KiB per lazy file; {mib} MiB catalog. Past the publication or byte cap the records still "
            f"inside their window give way, oldest first") in continuity


def test_the_readme_and_the_env_example_quote_the_source_recovery_bounds_from_the_module():
    """The recovery's budget is four constants; the prose that tells a reader
    what one receipt may cost quotes them, and the names bound is one batch."""
    from src import market_data, source_recovery
    text = re.sub(r"\s+", " ", README)
    assert f"`MAX_NAMES` ({source_recovery.MAX_NAMES}, one provider batch)" in text
    assert f"`MAX_BATCHES` ({source_recovery.MAX_BATCHES}) request" in text
    assert f"`MAX_BATCH_ATTEMPTS` ({source_recovery.MAX_BATCH_ATTEMPTS}) attempts" in text
    assert f"`MAX_COLLECTION_SECONDS` ({source_recovery.MAX_COLLECTION_SECONDS})" in text
    assert f"`FETCH_RESERVE_SECONDS` ({source_recovery.FETCH_RESERVE_SECONDS}) short of that bound" in text
    assert f"`recovery_until: {source_recovery.RECOVERY_UNTIL}`" in text
    assert source_recovery.MAX_NAMES == market_data.DEFAULT_BATCH_SIZE * source_recovery.MAX_BATCHES
    env = re.sub(r"\s*#\s*", " ", (ROOT / ".env.example").read_text())
    assert (f"({source_recovery.MAX_NAMES} names, {source_recovery.MAX_BATCH_ATTEMPTS} attempts, "
            f"{source_recovery.MAX_COLLECTION_SECONDS} seconds)") in env


def test_the_page_reads_the_recovery_statuses_the_collector_writes():
    """The Method line prints a receipt only in a status the collector writes;
    the page's list is a copy, held to the module's here."""
    from src import source_recovery
    page = (ROOT / "docs" / "app.js").read_text()
    listed = re.search(r"const RECOVERY_STATUSES = \[(.*?)\];", page).group(1)
    assert tuple(re.findall(r"'(\w+)'", listed)) == source_recovery.STATUSES


_REGEX_AFTER = set("(,=:[!&|?{};+-*%<>~^")


def _js_code(source: str) -> str:
    """The page's script without its comments: line and block comments are
    dropped, while strings, template literals and regex literals -- in which a
    '//' or a quote is text, not a comment or a string -- are kept whole. A
    regex literal starts at a '/' after an operator, an opening bracket, a
    comma, the start of a line or the words return/typeof."""
    out, i, n, last = [], 0, len(source), ""
    while i < n:
        c, nxt = source[i], source[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            j = source.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and nxt == "*":
            j = source.find("*/", i + 2)
            i = n if j < 0 else j + 2
            out.append(" ")
            continue
        if c in "'\"`":
            j = i + 1
            while j < n and source[j] != c:
                j += 2 if source[j] == "\\" else 1
            out.append(source[i:j + 1]); i, last = j + 1, c
            continue
        word = re.search(r"\b(?:return|typeof)\s*$", "".join(out[-12:]))
        if c == "/" and (last in _REGEX_AFTER or last in ("", "\n") or word):
            j, klass = i + 1, False
            while j < n and (klass or source[j] != "/") and source[j] != "\n":
                if source[j] == "\\":
                    j += 1
                elif source[j] == "[":
                    klass = True
                elif source[j] == "]":
                    klass = False
                j += 1
            out.append(source[i:j + 1]); i, last = j + 1, "/"
            continue
        out.append(c)
        if not c.isspace() or c == "\n":
            last = c if not c.isspace() else ("\n" if last in _REGEX_AFTER or last == "" else last)
        i += 1
    return "".join(out)


def test_the_comment_stripper_keeps_strings_regexes_and_templates_and_drops_comments():
    """The count below is only as good as this: a call in a comment of either
    kind is not a call, and a '//' or a quote inside a string, a template or a
    regex literal does not start a comment or a string."""
    src = ("a(); // b()\n/* c() */ d('//e()'); f(/['\"]+\\/\\//g, x); g(`//${h()}`);\n"
           "const k = 1 / 2; m(); /*\n n() */ return /\\/* o()/.test(s);")
    code = _js_code(src)
    for kept in ("a()", "d('//e()')", "/['\"]+\\/\\//g", "g(`//${h()}`)", "m()", "/\\/* o()/"):
        assert kept in code, (kept, code)
    for dropped in ("b()", "c()", "n()"):
        assert dropped not in code, (dropped, code)


def test_the_page_the_handoff_and_the_mail_print_fidelitys_rule_and_the_advice_as_one_text():
    """Fidelity's OTO releases the sell stop only on a full fill, so a part
    fill needs a separate stop. The text labels the two apart -- Fidelity's
    rule, then SpicyStock's advice -- and says that wherever the record's own
    words put the stop at the fill (the ticket's terms, the plan's entry
    instruction, its dated schedule) they assume a full fill. The mail, the
    page and the private handoff's readback print it, defined once in each
    file: the page through one helper, partFillNote(), called at each of its
    ten places (the order block, the recorded ticket, the comparison, the
    Burst card, the setting-up action bar, the tickets sheet, the decision
    summary's need, the model exits, the saved setup's archived order and an
    archived original's status), the handoff at its readback. The plan's own
    words, which provenance replays, stay broker-neutral."""
    rule, advice = report.BROKER_PART_FILL.split(" SpicyStock’s advice: ")
    assert rule.startswith("Fidelity’s rule: ") and "in full" in rule, rule
    assert "attached at or live from the fill, that assumes a full fill" in advice, advice
    assert "Sell Stop Loss" in advice and "confirm Fidelity accepts it" in advice, advice
    assert any("is live from the fill" in c for c in plan.dated_schedule.__code__.co_consts if isinstance(c, str))
    assert "attached the moment the buy fills" in plan.ORDER_TERM_STOP
    calls = re.compile(r"(?<![\w.])partFillNote\((?:'[\w-]+')?\)")
    for name, sites in (("app.js", 10), ("app-handoff-ui.js", 1)):
        page = (ROOT / "docs" / name).read_text(encoding="utf-8")
        code = _js_code(page)
        assert len(re.findall(r"(?<![\w.])BROKER_PART_FILL\s*=", code)) == 1, name
        assert re.findall(r"const BROKER_PART_FILL = '([^']+)';", code) == [report.BROKER_PART_FILL], name
        # the definition and its one use, nothing else reads the name
        assert len(re.findall(r"(?<![\w.])BROKER_PART_FILL\b", code)) == 2, name
        if name == "app.js":
            assert len(re.findall(r"const partFillNote = \(extra\) => el\('p', \{ [^}]*text: BROKER_PART_FILL \}\);", code)) == 1
            assert len(calls.findall(code)) == sites, calls.findall(code)
        else:
            assert len(re.findall(r"\}, BROKER_PART_FILL\)", code)) == sites, name
    for term in (plan.ORDER_TERM_STOP, plan.ORDER_TERM_DAY, plan.ORDER_TERM_ABOVE_LIMIT, plan.ORDER_TERM_BELOW_SKIP):
        assert "Fidelity" not in term and "in full" not in term, term


def test_the_page_and_the_mail_refuse_to_say_no_ticket_twice_by_the_same_rule():
    """The budget's reason for a withheld plan opens with "ticket withheld",
    so a line that introduces it with "No ticket" says it twice. Both
    consumers drop the lead, and by the same list of words."""
    page = (ROOT / "docs" / "app.js").read_text()
    leads = set(re.findall(r"s\.indexOf\((NO_TICKET|CUT_WORDS\.withheld)\) === 0", page))
    assert leads == {"NO_TICKET", "CUT_WORDS.withheld"}, leads
    assert re.search(r"const NO_TICKET = '([^']+)'", page).group(1) == report.NO_TICKET_LEADS[0]
    assert re.search(r"withheld: '([^']+)'", page).group(1) == report.NO_TICKET_LEADS[1]
    for reason, doubled in ((f"{report.NO_TICKET_LEADS[1]}: at the $1.00 limit", True),
                            (f"{report.NO_TICKET_LEADS[0]} tonight", True),
                            ("beyond the slot cap", False)):
        assert report.says_no_ticket(reason) is doubled, reason
    # and the mail's own line drops the lead exactly there
    data = {"beyond_cap": ["TSLA", "AAPL"],
            "cash_budget": {"cut": [{"ticker": "TSLA", "reason": f"{report.NO_TICKET_LEADS[1]}: at the $129.18 limit"},
                                    {"ticker": "AAPL", "reason": "beyond the slot cap"}]}}
    lines = report._no_ticket_lines(data)
    assert "No ticket for TSLA" not in lines[0] and "ticket withheld" in lines[0], lines[0]
    assert lines[0].count("ticket withheld") == 1, lines[0]
    assert "No ticket for AAPL: beyond the slot cap" in lines[1], lines[1]


def test_the_page_prints_the_same_plan_status_words_the_mail_does():
    page = (ROOT / "docs" / "app.js").read_text()
    block = re.search(r"const PLAN_STATUS = \{\n(.*?)\n  \};", page, re.S).group(1)
    words = dict(re.findall(r"(\w+): \['([^']+)'", block))
    assert words == report.PLAN_STATUS_WORDS
    for status in ("hold", "sell_half", "sell_into_strength", "exit", "stopped", "expired", "pending",
                   record.NOT_FILLED, record.UNCERTAIN, record.UNREADABLE, "unmeasured"):
        assert status in words, status


# ------------------------------------ the four prices, kept apart -----------


def test_only_the_plan_module_knows_the_day_two_percentage():
    """``ENTRY_ABOVE_PCT`` is the OUTER extension threshold and nothing else
    derives a price from it: any other module that wants that line reads the
    field the plan publishes, so the two prices cannot drift apart in one
    consumer while staying together in the next."""
    readers = sorted(p.name for p in (ROOT / "src").glob("*.py")
                     if "ENTRY_ABOVE_PCT" in p.read_text())
    assert readers == ["plan.py"], readers
    tools = sorted(p.name for p in (ROOT / "tools").glob("*.py")
                   if "ENTRY_ABOVE_PCT" in p.read_text())
    assert tools == ["entry_limit_study.py"], tools     # the retired ceiling lives there alone


def test_no_consumer_reads_the_ticket_limit_as_the_day_two_line():
    """Every module and the page agree on which field is which: ``limit`` and
    ``entry_high`` are the ticket's executable limit, ``day2_spent_above``
    and ``skip_if_open_above`` are the outer threshold. The fixture proves it
    with a plan where the two prices differ."""
    data = json.loads((ROOT / "tests" / "fixtures" / "page" / "full.json").read_text())
    plans = [b["plan"] for b in data["bursts"] if b.get("plan")]
    narrowed = [p for p in plans if p["limit"] != p["day2_spent_above"]]
    assert narrowed, "the full fixture should carry a narrowed ticket"
    for p in plans:
        assert p["limit"] == p["entry_high"] <= p["day2_spent_above"] == p["skip_if_open_above"]
        assert p["planned_entry"] <= p["limit"]
        if p["order_json"]:
            assert p["order_json"]["limit_price"] == p["limit"]
            assert p["order_json"]["stop_price"] == p["entry_ref"] < p["limit"]
    page = (ROOT / "docs" / "app.js").read_text()
    # the page's order sheet prints the ticket's own limit and the day-2 line
    # in two columns, and names the second for the rule rather than the action
    assert "'too extended over'" in page and "plan.skip_if_open_above" in page
    # the Following snapshot saves both, so a saved setup cannot be read back
    # with the extension threshold standing in for the limit
    assert "day2_spent_above: burst && isNum(plan.day2_spent_above)" in page


def test_the_mail_names_the_day_two_line_only_when_it_is_not_the_limit():
    """The digest prints the ticket's zone; where the record carries a
    separate extension threshold it says so, and where the two are one price
    it does not print it twice."""
    burst = {"ticker": "AAA", "grade": "A+", "score": 9.1, "summary": "AAA: a burst.",
             "plan": {"entry_low": 98.0, "entry_high": 103.64, "day2_spent_above": 104.0,
                      "stop": 99.5, "shares": 6, "position_usd": 621.84}}
    html = report._trade_block(burst, None)
    assert "Buy zone 98.00–103.64" in html and "Too extended over 104.00" in html
    same = json.loads(json.dumps(burst))
    same["plan"]["entry_high"] = same["plan"]["day2_spent_above"] = 104.0
    assert "Too extended over" not in report._trade_block(same, None)
    older = json.loads(json.dumps(burst))
    older["plan"].pop("day2_spent_above")             # a record from before the split
    assert "Too extended over" not in report._trade_block(older, None)


# --------------------------------- the publication gate's own reach ---------
# tools/publish_dashboard.py is the only check that reads what a reader is
# actually served. It kept its list of files in a tuple beside the page, and
# the tuple named six of the seventeen: the design system's own sc.css -- where
# the v2.11.0 action bar and field group live -- the burst map and the Following
# shelf were never fetched, while the gate printed "Verified". It reads the list
# off docs/index.html now, and these hold it to the page.
def test_the_publication_gate_fetches_every_asset_the_page_cannot_work_without():
    from tools import publish_dashboard
    verified = set(publish_dashboard.public_files(ROOT))
    for name in ("index.html", "data.json", "picks.json",
                 "app.js", "app.css", "app-chart.js", "app-map.js", "app-follow.js",
                 "design-system/sc.css", "design-system/sc-charts.js",
                 "design-system/sc-theme.js", "design-system/sc-motion.js"):
        assert name in verified, f"publication never fetches {name}; readers could get a stale one"


def test_the_publication_gate_covers_every_local_reference_the_page_makes():
    """Read the page a different way from the tool, so this cannot pass by
    agreeing with the tool's own parse: whatever index.html grows next is
    verified without being listed anywhere."""
    from tools import publish_dashboard
    verified = set(publish_dashboard.public_files(ROOT))
    page = (ROOT / "docs" / "index.html").read_text()
    referenced = {token for token in re.findall(r"[\"']([\w./-]+\.(?:js|css|json|png|svg|ico))[\"']", page)
                  if "://" not in token and not token.startswith("/")}
    assert referenced, "no local asset was found in docs/index.html at all"
    assert referenced <= verified, sorted(referenced - verified)


def test_the_publication_gate_refuses_a_reference_the_checkout_does_not_carry(tmp_path):
    """A page asking for a file main does not publish is a 404 for every
    reader. The gate names it and stops, rather than verifying the rest and
    reporting success."""
    from tools import publish_dashboard
    from tests.test_publish_dashboard import write_reader_records
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.html").write_text('<link rel="stylesheet" href="ghost.css">')
    write_reader_records(docs)
    with pytest.raises(RuntimeError, match="ghost.css"):
        publish_dashboard.public_files(tmp_path)
    (docs / "ghost.css").write_text("/* published now */")
    assert "ghost.css" in publish_dashboard.public_files(tmp_path)


def test_the_publication_gate_skips_what_it_cannot_publish(tmp_path):
    """A CDN font, an absolute URL and a bare fragment are not files in docs/;
    reading them off the page must not turn publication red."""
    from tools import publish_dashboard
    from tests.test_publish_dashboard import write_reader_records
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.html").write_text(
        '<link href="https://fonts.googleapis.com/css2?family=X" rel="stylesheet">'
        '<link href="//cdn.example/x.css" rel="stylesheet">'
        '<a href="https://github.com/spicyChicken59">src</a>'
        '<a href="#method">skip</a><a href="/absolute.js">skip</a>'
        '<script src="../outside.js"></script>')
    sidecar = write_reader_records(docs)
    assert publish_dashboard.public_files(tmp_path) == ("index.html", *publish_dashboard.RECORD_FILES, sidecar)


def test_the_page_counts_the_reads_causes_the_module_writes_by_version():
    """run.reads names a selected name's missing reading by one word a version;
    the page prints those words and re-derives the counts on the Morning desk,
    so its lists are held to reader_coverage's, version by version, and it
    classifies a refused request by the grader's own marker."""
    from src import grader, reader_coverage
    block = re.search(r"const READ_FAILURES_BY_VERSION = \{ (.*?) \};", PAGE_JS).group(1)
    versions = {int(v): re.findall(r"'(\w+)'", lst) for v, lst in re.findall(r"(\d+): \[([^\]]*)\]", block)}
    assert versions == {v: list(f) for v, f in reader_coverage.FAILURES_BY_VERSION.items()}
    causes = re.search(r"const READ_CAUSES = \{ (.*?) \};", PAGE_JS).group(1)
    assert re.findall(r"(\w+): '", causes) == list(reader_coverage.FAILURES)
    labels = re.search(r"const READ_REQUEST_LABELS = \[([^\]]*)\];", PAGE_JS).group(1)
    markers = re.search(r"const READ_REQUEST_MARKERS = \[([^\]]*)\];", PAGE_JS).group(1)
    assert re.findall(r"'([^']+)'", labels) == [*grader.REQUEST_REFUSAL_LABELS, grader.error_label(grader.RequestOutage)]
    assert re.findall(r"'([^']+)'", markers) == list(grader.REQUEST_REFUSAL_MARKERS)
    # the documents say what the second version tells apart and what the run does about it
    assert "`request`" in README and "not asked again" in README
    assert "review_request" in README, "the funnel's stage list in README lacks the new stage"
    assert "refused as invalid" in (ROOT / "knowledge" / "method.md").read_text()


def test_the_readme_counts_the_fields_the_smoke_drops():
    """README says how many fields the page smoke drops in turn; that is the
    length of the list the smoke walks, read off the smoke itself."""
    smoke = (ROOT / "tools" / "page_smoke.mjs").read_text()
    head = smoke.index("console.log('-- a field missing');")
    listed = re.search(r"for \(const field of \[([^\]]*)\]\)", smoke[head:]).group(1)
    fields = re.findall(r"'([^']+)'", listed)
    assert len(fields) == len(set(fields)) and {"run.input_tolerance", "run.stale_followup", "run.reads.causes"} <= set(fields)
    words = {17: "seventeen", 18: "eighteen", 19: "nineteen", 20: "twenty", 21: "twenty-one", 22: "twenty-two"}
    assert f"drops {words[len(fields)]} fields in turn" in README, len(fields)
