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
    assert "Fewer than half the names answering" in README and pipeline.MIN_COVERAGE_FRACTION == 0.5
    assert f"{market_holdback()} minutes behind the clock" in README


def market_holdback() -> str:
    from src import market_data
    return {16: "sixteen"}[market_data.SIP_HOLDBACK_MINUTES]


def test_the_readme_quotes_the_scans_and_the_universe_floors():
    assert f"c/c1 >= {scans.BURST_RATIO} and v > v1 and v >= {scans.MIN_VOLUME}" in README
    assert f"c - o >= {scans.DOLLAR_MOVE:.2f} and v > {scans.MIN_VOLUME}" in README
    assert f"${universe.MIN_PRICE:g} and {universe.MIN_VOLUME:,} shares" in README
    assert "228-name seed" in README
    seed = [l for l in (ROOT / "data" / "symbols.txt").read_text().splitlines() if l and not l.startswith("#")]
    assert len(seed) == 228


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


def test_the_readme_lists_the_fixture_variants_the_generator_makes():
    listed = re.search(r"\(`(.*?)`\)", README.split("one per state the page can be in")[1]).group(1)
    assert tuple(listed.split("`, `")) == make_fixture.VARIANTS
    for variant in make_fixture.VARIANTS:
        assert (ROOT / "tests" / "fixtures" / "page" / f"{variant}.json").exists(), variant


def test_the_readme_layout_names_files_that_exist():
    block = README_RAW.split("## Layout")[1].split("```")[1]
    names = re.findall(r"[\w.-]+\.(?:py|json|js|css|html|md|yml)", block)
    missing = [n for n in names if not list(ROOT.rglob(n))]
    assert not missing, missing
    assert set(re.findall(r"(\w+)\.py", block.split("src/")[1].split("docs/")[0])) == \
        {p.stem for p in (ROOT / "src").glob("*.py") if p.stem != "__init__"}


def test_the_readme_names_the_six_cover_sentences():
    for h1 in (report.H1_STAND_ASIDE, report.H1_KEEP_CASH, report.H1_CLOSED):
        assert h1 in README, h1
    assert "Trade tomorrow. N A-quality" in README and "Trade small. N A+" in README and "No verdict for" in README


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
    assert f"${universe.MIN_PRICE:g} and {universe.MIN_VOLUME:,} shares" in ENV
    assert f"data/symbols.txt ({228} names)" in ENV
    assert f"$10,000, {plan.DEFAULT_RISK_PCT:g}% risk a trade" in ENV and plan.DEFAULT_EQUITY == 10_000
    assert "0.25-1%" in ENV and (plan.RISK_PCT_BAND_LOW, plan.RISK_PCT_BAND_HIGH) == (0.25, 1.0)
    assert "sixteen minutes behind the clock" in ENV
    assert "'directory'" in ENV and universe.DEFAULT_MODE == "directory"
    assert "seven days" in ENV and universe.DIRECTORY_MAX_AGE.days == 7


def test_the_env_example_names_no_file_the_run_no_longer_writes():
    for stale in ("ledger.json", "results/", "morning.yml", "scorer.py", "ScanConfig", "min_dollar_volume_pctile", "2LYNCH"):
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
    assert f"over {['six'][0]} fixtures" in CLAUDE_MD and len(make_fixture.VARIANTS) == 6


# ------------------------------------------------------------ rulebook ----
def test_the_rulebook_bands_are_the_graders():
    bands = {g: s for s, g in grader.GRADE_BANDS}
    for grade, floor in bands.items():
        assert re.search(rf"{re.escape(grade)}[^\n]*\b{floor:g}\b", STRATEGY), (grade, floor)
    assert "may only lower" in STRATEGY.lower() or "never raise" in STRATEGY.lower()


def test_the_method_file_names_every_module_that_holds_a_rule():
    for module in ("universe", "scans", "quality", "breadth", "watchlist", "plan", "record"):
        assert f"src/{module}.py" in METHOD, module


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
        assert report.PROBLEM_SENTENCES[kind] == sentence, kind


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
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.html").write_text('<link rel="stylesheet" href="ghost.css">')
    for name in publish_dashboard.RECORD_FILES:
        (docs / name).write_text("{}")
    with pytest.raises(RuntimeError, match="ghost.css"):
        publish_dashboard.public_files(tmp_path)
    (docs / "ghost.css").write_text("/* published now */")
    assert "ghost.css" in publish_dashboard.public_files(tmp_path)


def test_the_publication_gate_skips_what_it_cannot_publish(tmp_path):
    """A CDN font, an absolute URL and a bare fragment are not files in docs/;
    reading them off the page must not turn publication red."""
    from tools import publish_dashboard
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.html").write_text(
        '<link href="https://fonts.googleapis.com/css2?family=X" rel="stylesheet">'
        '<link href="//cdn.example/x.css" rel="stylesheet">'
        '<a href="https://github.com/spicyChicken59">src</a>'
        '<a href="#method">skip</a><a href="/absolute.js">skip</a>'
        '<script src="../outside.js"></script>')
    for name in publish_dashboard.RECORD_FILES:
        (docs / name).write_text("{}")
    assert publish_dashboard.public_files(tmp_path) == ("index.html", *publish_dashboard.RECORD_FILES)
