"""Words the page prints that restate a rule of the modules, held to the modules.

`docs/app.js` prints a veto as the checklist measured it, mirrors the event
registry's interval rule for a listed row that carries no plan, names whose
rule each exit is, reads the five regime rules off a record's own inputs and
names the one-minute bars that place a first-day fill. Each of those is a
copy of something `src/` owns; this file holds the copies, and the browser
suite (`tools/page_text_cases.mjs`) holds what is rendered."""
import importlib.util
import json
import re
from pathlib import Path

import pytest

from src import breadth, event_risk, intraday, plan, quality, record

ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / "docs" / "app.js").read_text(encoding="utf-8")
FULL = json.loads((ROOT / "tests" / "fixtures" / "page" / "full.json").read_text())
DIR = ROOT / "tests" / "fixtures" / "event-registry"
CORPUS = json.loads((DIR / "classify-parity.json").read_text())
NUMBER_WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")


def _const(name):
    """The string a `const NAME = '...';` line of the page assigns."""
    return re.search(rf"const {name} = '([^']*)';", PAGE).group(1)


def _generator():
    spec = importlib.util.spec_from_file_location("classify_parity", DIR / "classify_parity.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------- the veto
def test_the_page_names_the_up_days_veto_as_the_checklist_measures_it():
    """`up_days` is VETO_UP_DAYS or more consecutive rising closes of any size
    (quality.assess()), not days above +1%: the page's fallback threshold is
    the module's, its number words spell it, and the old words are gone."""
    assert int(re.search(r"const VETO_UP_DAYS = (\d+);", PAGE).group(1)) == quality.VETO_UP_DAYS
    spelled = re.findall(r"'(\w+)'", re.search(r"const COUNT_WORDS = \[([^\]]*)\];", PAGE).group(1))
    assert tuple(spelled) == NUMBER_WORDS
    assert spelled[quality.VETO_UP_DAYS] == NUMBER_WORDS[quality.VETO_UP_DAYS]
    assert "three up days in a row" not in PAGE
    assert "' rising closes in a row before the burst ('" in PAGE
    assert "' or more rising closes in a row before the burst, of any size'" in PAGE
    assert "' or more of any size refuse a setup)'" in PAGE


def test_the_record_archives_the_threshold_and_the_count_the_page_reads():
    """The page reads rules.quality.veto_up_days and the two_days check's
    values.up_closes: both are what the run writes."""
    assert FULL["rules"]["quality"]["veto_up_days"] == quality.VETO_UP_DAYS
    assert "rules || {}).quality || {}).veto_up_days" in PAGE
    for burst in FULL["bursts"]:
        two = next(c for c in burst["quality"]["checks"] if c["key"] == "two_days")
        assert isinstance(two["values"]["up_closes"], int)
    assert "x.key === 'two_days'" in PAGE and "two.values.up_closes" in PAGE


# ---------------------------------------------------------------- the event registry
def test_the_parity_corpus_is_its_generator_s_output():
    assert (DIR / "classify-parity.json").read_text() == _generator().render()


def test_every_case_carries_classify_s_own_reading():
    generator = _generator()
    assert CORPUS["registry"] == generator.REGISTRY
    for case in CORPUS["cases"]:
        result = event_risk.classify(case["symbol"], case["session"], registry=CORPUS["registry"])
        expect = case["expect"]
        assert (result["symbol"], result["status"], result["blocked"], result["reason"]) == (
            expect["symbol"], expect["status"], expect["blocked"], expect["reason"]), case
        assert [m["id"] for m in result["matches"]] == [m["id"] for m in expect["matches"]], case
        for got, want in zip(result["matches"], expect["matches"]):
            assert (got["review_overdue"], got["evidence_as_of"], got.get("active_until"),
                    [s["published_on"] for s in got["sources"]], bool(got.get("resolution"))) == (
                want["review_overdue"], want["evidence_as_of"], want["active_until"], want["sources"],
                want["resolution"]), case


def test_the_corpus_reaches_every_boundary_of_the_interval_rule():
    """Each rule of classify() has a case on its day and on the day either
    side, or a mirror that moved a boundary by one day would agree with it."""
    by = {(c["symbol"], c["session"]): c["expect"] for c in CORPUS["cases"]}
    events = {e["id"]: e for e in CORPUS["registry"]["events"]}
    open_entry, resolved = events["synthetic-open"], events["synthetic-resolved"]
    # the interval includes active_from
    assert by[("AAA", "2026-03-01")]["status"] == "not_in_registry"
    assert by[("AAA", open_entry["active_from"])]["status"] == "known_event"
    # an entry that starts after its announcement is not matched in between
    assert by[("BBB", "2026-03-04")]["blocked"] is False and by[("BBB", "2026-03-05")]["blocked"] is True
    # a review due today is not overdue; the day after it is, and stays blocked
    assert by[("AAA", open_entry["review_due"])]["status"] == "known_event"
    after = by[("AAA", "2026-03-21")]
    assert (after["status"], after["blocked"], after["matches"][0]["review_overdue"]) == ("review_required", True, True)
    assert after["reason"].endswith("pending a source review.")
    # the interval excludes active_until
    assert by[("CCC", "2026-03-24")]["blocked"] is True and by[("CCC", resolved["active_until"])]["blocked"] is False
    # a resolution published after the session is not shown, and one on it is
    before = by[("CCC", "2026-03-23")]["matches"][0]
    assert (before["resolution"], before["active_until"]) == (False, None)
    on = by[("CCC", "2026-03-24")]["matches"][0]
    assert (on["resolution"], on["active_until"]) == (True, resolved["active_until"])
    # a source published after the session is not evidence available on it
    assert by[("AAA", "2026-03-09")]["matches"][0]["sources"] == ["2026-03-02"]
    assert by[("AAA", "2026-03-10")]["matches"][0]["evidence_as_of"] == "2026-03-10"
    # two entries for one symbol: both reasons, in the registry's order
    twin = by[("DDD", "2026-03-12")]
    assert [m["id"] for m in twin["matches"]] == ["synthetic-twin-first", "synthetic-twin-second"]
    assert twin["reason"].count("Synthetic entry") == 2
    # one overdue entry of two makes the whole reading review_required
    mixed = by[("DDD", "2026-03-17")]
    assert mixed["status"] == "review_required"
    assert [m["review_overdue"] for m in mixed["matches"]] == [True, False]
    # a symbol as a record could spell it, and ones that are not the entry's
    assert by[("aaa", "2026-03-02")]["symbol"] == "AAA" and by[(" AAA ", "2026-03-02")]["blocked"] is True
    assert by[("AAAA", "2026-03-02")]["blocked"] is False and by[("EE-F", "2026-03-09")]["blocked"] is False
    assert by[("ee.f", "2026-03-09")]["blocked"] is True
    assert {c["expect"]["status"] for c in CORPUS["cases"]} == {"not_in_registry", "known_event", "review_required"}


def test_the_page_composes_the_reason_in_classify_s_words():
    """The page prints the registry's own reason between the module's fixed
    lead and its overdue sentence; the three are copies, held here."""
    registry = CORPUS["registry"]
    current = event_risk.classify("AAA", "2026-03-02", registry=registry)
    overdue = event_risk.classify("AAA", "2026-03-21", registry=registry)
    absent = event_risk.classify("ZZZ", "2026-03-02", registry=registry)
    reason = registry["events"][0]["reason"]
    assert current["reason"] == _const("REGISTRY_LEAD") + reason
    assert overdue["reason"] == _const("REGISTRY_LEAD") + reason + _const("REGISTRY_OVERDUE")
    assert absent["reason"] == _const("REGISTRY_NONE")
    assert re.search(r"const REGISTRY_SYMBOL = /\^\[A-Z\]\[A-Z0-9\.\\-\]\*\$/;", PAGE)
    # the page reads the ARCHIVED registry, where the run nests it
    assert FULL["rules"]["event_risk"]["registry"]["events"]
    assert "rules.event_risk.registry" in PAGE


# ---------------------------------------------------------------- the exits and the regime
def test_the_page_has_words_for_every_source_mark_an_exit_rule_carries():
    block = re.search(r"const EXIT_SOURCES = \{(.*?)\};", PAGE).group(1)
    marks = set(re.findall(r"(\w): '", block))
    assert {rule["source"] for rule in plan.EXIT_RULES} <= marks
    by_rule = re.search(r"const EXIT_SOURCE_BY_RULE = \{(.*?)\};", PAGE).group(1)
    named = re.findall(r"(\w+): '", by_rule)
    rules = {rule["key"]: rule for rule in plan.EXIT_RULES}
    assert named == ["no_breakeven"] and rules["no_breakeven"]["source"] == "T"
    # the one exit that is a third party's test of ANOTHER setup says so itself
    assert "EP9M" in rules["no_breakeven"]["rule"]
    assert "a third party’s test of another setup, not measured on bursts" in by_rule


def test_the_page_reads_the_five_regime_rules_off_fields_the_run_writes():
    regime = FULL["breadth"]["regime"]
    listed = re.findall(r"\['(red|yellow)', '(\w+)', ", PAGE)
    assert listed == [("red", "down4_alarm"), ("red", "ratio_10d_red"), ("red", "ratio_5d_red"),
                      ("yellow", "ratio_10d_yellow"), ("yellow", "up50_month_hot")]
    for _, name in listed:
        assert name in regime["thresholds"], name
    for name in ("down4", "up4", "up50_month", "ratio_10d", "ratio_5d", "up4_10d", "down4_10d", "up4_5d", "down4_5d"):
        assert name in regime["inputs"], name
    # the two scaled counts, and the readings they were scaled from
    scaled = dict(re.findall(r"(\w+): \['(\w+)', '", re.search(r"const SCALED_NOTES = \{(.*?)\};", PAGE, re.S).group(1)))
    assert scaled == {"up50_month": "up50_month_hot", "down25_quarter": "down25_quarter_oversold"}
    assert FULL["breadth"]["rules"]["up50_month_hot"] == breadth.UP50_MONTH_HOT
    assert FULL["breadth"]["rules"]["down25_quarter_oversold"] == breadth.DOWN25_QUARTER_OVERSOLD
    assert FULL["breadth"]["rules"]["down4_alarm"] == breadth.DOWN4_ALARM
    assert regime["thresholds"]["reference_universe"] == breadth.REFERENCE_UNIVERSE
    assert {n["key"] for n in FULL["breadth"]["notes"]} >= set(scaled)


def test_the_record_archives_the_minute_bar_rule_the_record_view_names():
    assert FULL["rules"]["record"]["intraday_fill"] == intraday.POLICY == record.RULES["record.intraday_fill"]
    assert FULL["rules"]["intraday"]["window_minutes"] == plan.ENTRY_WINDOW_MINUTES
    # the Record view's two sentences each read the archived rule: the replay-prices line and the model-plans hint
    words = re.search(r"function minuteBarWords\(data\) \{(.*?)\n  \}", PAGE, re.S).group(1)
    assert "(rules.record || {}).intraday_fill" in words and "(rules.intraday || {}).window_minutes" in words
    assert "if (!policy) return '';" in words
    hint = re.search(r"if \(hint\) hint\.textContent = (.*?);\n", PAGE).group(1)
    assert "text((rules.record || {}).intraday_fill) ? ', and from retained one-minute bars where a first day needs them,' : ''" in hint


# ---------------------------------------------------------------- the brief's links
def test_the_footer_links_the_brief_at_run_time_and_the_shell_names_neither_file():
    """The publication gate reads every href off docs/index.html and refuses a
    file the checkout lacks, so the pair is linked by the script alone."""
    shell = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    assert "brief.md" not in shell and "brief.json" not in shell
    files = re.findall(r"\['([\w.]+)', '([^']+)'\]", re.search(r"const BRIEF_FILES = \[(.*?)\];", PAGE).group(1))
    assert files == [("brief.md", "analyst brief"), ("brief.json", "brief.json")]
    brief = pytest.importorskip("src.brief")
    assert (brief.MD_FILE, brief.JSON_FILE) == (files[0][0], files[1][0])


def test_the_method_view_links_the_rule_sheet_beside_the_method_links():
    assert "const RULE_SHEET_URL = 'https://github.com/' + REPO + '/blob/main/knowledge/rules.md';" in PAGE
    assert "'Every rule the run applies, in order (knowledge/rules.md)'" in PAGE
