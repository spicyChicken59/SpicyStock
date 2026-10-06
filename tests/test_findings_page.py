"""The page side of the historical findings: ``docs/app-findings.js`` is
held to the file it prints and to the rules this repository keeps for a
page module -- it reads nothing itself, it types no number a caption
quotes, it writes no colour, every class it uses exists in the sheet,
and the harnesses that evaluate the page's modules name it.

The builder and the JSON are held to their evidence in
``tests/test_historical_findings.py``; this file holds the module."""
from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import build_historical_findings as bf  # noqa: E402
from tools import publish_dashboard  # noqa: E402

MODULE = ROOT / "docs" / "app-findings.js"
SOURCE = MODULE.read_text(encoding="utf-8")
BODY = SOURCE.split("(function (w) {", 1)[1]
APP = (ROOT / "docs" / "app.js").read_text(encoding="utf-8")
INDEX = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "docs" / "app.css").read_text(encoding="utf-8")
README = re.sub(r"\s+", " ", (ROOT / "README.md").read_text(encoding="utf-8"))

# What a string literal in the module may carry a digit for: a class, id,
# attribute value or tag name (an identifier, no spaces), the version the
# builder owns, and the one noon-UTC suffix the date helper appends so a
# session's weekday is the exchange's. Everything else with a digit in it
# is a number typed into the page, which the file is supposed to supply.
IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_:-]*(?: [A-Za-z][A-Za-z0-9_-]*)*$")
ALLOWED = {bf.VERSION, "T12:00:00Z"}
# the one digit-bearing WORD a caption may carry: the name of the digest
# algorithm beside a digest the file supplies
WORDS = re.compile(r"SHA-256")


def stray(literals) -> list[str]:
    return [s for s in literals
            if re.search(r"\d", WORDS.sub("", s)) and s not in ALLOWED and not IDENTIFIER.match(s)]


def string_literals(source: str) -> list[str]:
    """Every string literal in a JavaScript source, read by a small scanner
    that knows comments, the three quote kinds, escapes and regex literals
    (a slash where an operand may start), so an apostrophe in a comment
    cannot open a string the way a naive regex would read it."""
    out, i, n = [], 0, len(source)
    last = ""   # the last significant character before the current position
    while i < n:
        c = source[i]
        if c == "/" and source.startswith("//", i):
            i = source.find("\n", i)
            i = n if i < 0 else i
            continue
        if c == "/" and source.startswith("/*", i):
            i = source.find("*/", i) + 2
            continue
        if c in "'\"`":
            j = i + 1
            while j < n and source[j] != c:
                j += 2 if source[j] == "\\" else 1
            out.append(source[i + 1:j])
            i = j + 1
            last = c
            continue
        if c == "/" and (last == "" or last in "(,=:[!&|?{};+-*%<>~^"):
            j = i + 1
            while j < n and source[j] != "/":
                if source[j] == "\\":
                    j += 1
                elif source[j] == "[":
                    j = source.find("]", j)
                j += 1
            i = j + 1
            while i < n and source[i].isalpha():
                i += 1
            last = "/"
            continue
        if not c.isspace():
            last = c
        i += 1
    return out


def test_the_scanner_reads_strings_and_not_comments_or_regexes():
    sample = "const a = 'x1'; // it's 2\nconst r = /\\d{3}/g; const b = \"y2\"; /* 3's */ const c = `z4`; const d = s.replace(/_/g, ' ');"
    assert string_literals(sample) == ["x1", "y2", "z4", " "]


def test_the_module_quotes_no_number_it_does_not_print_from_the_file():
    assert not stray(string_literals(BODY)), stray(string_literals(BODY))
    # the guard can fail: a typed number in a caption is what it exists for
    assert stray(string_literals("el('p', { text: 'Run 6 as a table', 'aria-label': 'SHA-256 of 2 files' })")) == ["Run 6 as a table", "SHA-256 of 2 files"]


def test_the_module_reads_nothing_itself_and_tells_no_time():
    for forbidden in ("fetch(", "SCStock.data", "S.data", "SCStock.model", "S.model", "localStorage",
                      "picks.json", "data.json", "Date.now", "new Date()"):
        assert forbidden not in BODY, forbidden


SC_CSS = (ROOT / "docs" / "design-system" / "sc.css").read_text(encoding="utf-8")


def defined(cls: str, sheet: str) -> bool:
    """A class is defined when a selector names it whole: `.ss-find__k` is not
    defined by `.ss-find__key`, which a substring test would have said it was."""
    return re.search(r"\." + re.escape(cls) + r"(?![\w-])", sheet) is not None


def classes_used(source: str) -> set[str]:
    """Every class token the module writes, read off its string literals; a
    token ending in a dash is a prefix the module completes with a tone, and is
    expanded by the tones the module itself declares."""
    tones = re.search(r"const VERDICT_TONE = \{([^}]+)\};", source).group(1)
    suffixes = re.findall(r"'([a-z]+)'", tones)       # a legend key takes a verdict's tone
    chip = suffixes + ["neutral"]                      # a chip falls back to neutral for a verdict it does not know
    used = set()
    for literal in string_literals(source):
        for token in literal.split():
            # a class, never an id: the page's ids are `ss-find-<name>-<n>`, its classes `ss-find__<name>`
            if not re.match(r"^(ss-find(?:__[\w-]*)?|sc-[\w-]+|is-[\w-]+)$", token):
                continue
            if token.endswith("-"):
                used.update(token + t for t in (chip if token.startswith("sc-chip") else suffixes))
            else:
                used.add(token)
    return used


def test_the_module_writes_no_colour_and_the_sheets_know_every_class_it_uses():
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b", SOURCE)
    assert "rgb(" not in SOURCE and "hsl(" not in SOURCE
    rules = [line for line in CSS.splitlines() if "ss-find" in line or "ss-study__h3" in line]
    assert rules, "app.css has no replay rules"
    assert not [line for line in rules if re.search(r"#[0-9a-fA-F]{3,8}\b", line)]
    used = classes_used(BODY)
    assert len(used) > 30 and {"ss-find__key--danger", "sc-pick__item", "is-ghost"} <= used, sorted(used)
    # the page's own classes live in app.css; the design system's in its sheet or in app.css
    missing = sorted(c for c in used if not (defined(c, CSS) if c.startswith("ss-find") else defined(c, SC_CSS) or defined(c, CSS)))
    assert not missing, missing
    # the check can fail: a prefix of a real class is not a class
    assert not defined("ss-find__k", CSS) and defined("ss-find__key", CSS)


def test_the_versions_and_the_strata_are_the_builders():
    assert re.search(r"const VERSION = '([^']+)';", SOURCE).group(1) == bf.VERSION
    strata = re.search(r"const STRATA = \[([^\]]+)\];", SOURCE).group(1)
    assert [s.strip(" '") for s in strata.split(",")] == list(bf.STRATA) + ["all"]
    assert bf.OUTPUT.exists()


def test_the_page_loads_the_findings_before_the_app_and_the_harnesses_name_it():
    assert INDEX.index('src="app-findings.js"') < INDEX.index('src="app.js"')
    assert "engine.mount(" in APP and "evidenceJSON('historical-findings.json'" in APP
    # the module checks the file's shape before anything is drawn, and app.js asks it to
    assert "engine.shapeProblem(F)" in APP and "function shapeProblem(F)" in SOURCE
    # the two historical files load when the Record view is shown, and from nowhere else
    assert APP.count("loadHistoricalEvidence();") == 2
    assert "if (state.view === 'record') loadHistoricalEvidence();" in APP
    for harness in ("tools/continuity_check.mjs", "tools/evidence_focus_cases.mjs"):
        assert "docs/app-findings.js" in (ROOT / harness).read_text(encoding="utf-8"), harness
    assert "checkFindings" in (ROOT / "tools" / "page_smoke.mjs").read_text(encoding="utf-8")
    assert "app-findings.js" in README and "night by night" in README


def test_the_publication_gate_fetches_both_study_files():
    files = publish_dashboard.public_files(ROOT)
    assert "historical-findings.json" in files and "historical-validation.json" in files
    assert "app-findings.js" in files
