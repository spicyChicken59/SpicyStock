"""knowledge/rules.md is the corrected strategy page: every rule the evening
run applies, in pipeline order, each with its constant and its provenance
class. This file holds it to the code, so the sheet can fall behind a module
only by turning this suite red:

* every backticked CONSTANT resolves in a module its section heading names
  (or in the module it is qualified with), and every value printed beside one
  (``NAME`` = value) equals the constant;
* every numeric constant the sheet names carries its value, and no rule
  sentence carries a number with no constant beside it;
* every backticked function exists, every path exists;
* every step of ``plan.EXIT_RULES``, the five breadth rules and the three
  policy strings appear where the sheet says they do;
* a row's provenance class agrees with the mark the module's own comment
  gives each constant in it;
* what the sheet says of the model that no constant states is run: every
  burst ticket's risk is halved, what the walk books at a stop (each sentence
  of that section held beside the case that runs it), where the half sale is
  booked, what a later run of one session replaces, and the arithmetic of the
  dated examples; the dated stop example is read off the permanent quality
  ledger;
* the two broker rules the ticket section states are the broker note's own
  headings, and the setting-up pool's volume test carries each scan's own
  operator.

``parse()`` and ``problems()`` take the sheet's text, so the last tests drive
them over a sheet with one number drifted, one rule un-named and one class
changed, and show each is refused for its own reason.
"""
from __future__ import annotations

import ast
import gzip
import importlib
import json
import re
from datetime import date, time
from pathlib import Path

from src import (admission, allocation, breadth, grader, intraday, pipeline, plan, quality, reader_coverage,
                 record, review_selection, scans, universe, watchlist)

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "knowledge" / "rules.md"
SHEET = PATH.read_text()

# ---------------------------------------------------------------- grammar ----
SPAN = re.compile(r"`([^`\n]+)`")
CONST = re.compile(r"^(?:([a-z_]+)\.)?([A-Z][A-Z0-9_]*[A-Z0-9])$")
FUNC = re.compile(r"^(?:([a-z_]+)\.)?([a-z_][a-z0-9_]*)\(\)$")
FILE = re.compile(r"^[\w./-]+\.(?:py|md|json|yml|txt)$")
FIELD = re.compile(r"^[a-z_][a-z0-9_]*(?:\[\])?(?:\.[a-z_][a-z0-9_]*(?:\[\])?)*$")
NUMBER = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")
CLOCK = re.compile(r"\d{2}:\d{2}")
#: the spans the "How to read" section uses to show the notation itself
PLACEHOLDERS = {"NAME", "module.NAME", "name()"}
HOW_TO_READ = "How to read this sheet"
#: the eight classes, as the sheet's own table defines them
CLASSES = ("PRIMARY", "LATER BONDE", "B*", "V", "SECONDARY", "DERIVED", "P", "R")
CLASS_TOKEN = re.compile(r"PRIMARY|LATER BONDE|B\*|SECONDARY|DERIVED|\bV\b|\bP\b|\bR\b")
#: a class cell that names no class: the verdict that fires on no rule, a scan nothing trades
UNCLASSED = ("", "not traded")
#: columns whose cells are labels, not rule sentences
LABEL_COLUMNS = ("Class", "Order", "Letter", "Verdict", "Step")
#: what a rule sentence may carry that is not a rule number: a date, a year, a
#: cross-reference, and the checklist letter that is a digit
MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
NOT_A_RULE_NUMBER = re.compile(
    rf"\b\d{{1,2}} (?:{MONTHS})[a-z]*(?: \d{{4}})?\b|\b20[0-2]\d(?:-\d{{2}}-\d{{2}})?\b|\bsections? \d+\b|\bletter 2\b|2LYNCH")
#: the module comment's mark for a constant, and the classes the sheet may give it
MARK_CLASSES = {"B": {"B*", "PRIMARY", "LATER BONDE", "V"}, "P": {"P", "DERIVED"}, "T": {"SECONDARY"}, "R": {"R"}}
MARKED_MODULES = ("plan", "watchlist", "record", "pipeline")
BREADTH_RULES = ("DOWN4_ALARM", "RED_RATIO_10D", "RED_RATIO_5D", "YELLOW_RATIO_10D", "UP50_MONTH_HOT")


def module(name: str):
    return importlib.import_module(f"src.{name}")


def parse(text: str) -> list[dict]:
    """The sheet as sections: the text before the first ``##`` heading, then
    one per heading, each with the modules its heading names and its lines."""
    out = [{"title": "", "modules": [], "lines": []}]
    for raw in text.splitlines():
        if raw.startswith("## "):
            out.append({"title": raw[3:].strip(), "modules": re.findall(r"`src/([a-z_]+)\.py`", raw), "lines": []})
        else:
            out[-1]["lines"].append(raw)
    return out


def literal_after(line: str, at: int):
    """The value printed after ``\\`NAME\\` = `` starting at ``at``: (value, end).
    A string in double quotes, a clock time, a bracketed Python literal, or a
    number with thousands separators; anything else is refused."""
    rest = line[at:]
    if rest.startswith('"'):
        end = rest.index('"', 1)
        return rest[1:end], at + end + 1
    if rest[:1] in "({[":
        depth = 0
        for i, ch in enumerate(rest):
            depth += ch in "({["
            depth -= ch in ")}]"
            if depth == 0:
                return ast.literal_eval(rest[:i + 1]), at + i + 1
        raise ValueError(f"unbalanced literal in {line!r}")
    clock = CLOCK.match(rest)
    if clock:
        hour, minute = clock.group().split(":")
        return time(int(hour), int(minute)), at + clock.end()
    number = NUMBER.match(rest)
    if number:
        return float(number.group().replace(",", "")), at + number.end()
    raise ValueError(f"no readable value after '=' in {line!r}")


def resolve(qualifier: str | None, name: str, section: dict):
    """(module name, value) for a constant, or a sentence saying why not."""
    if qualifier:
        try:
            mod = module(qualifier)
        except ModuleNotFoundError:
            return f"`{qualifier}.{name}`: there is no src/{qualifier}.py"
        if not hasattr(mod, name):
            return f"`{qualifier}.{name}`: src/{qualifier}.py names no {name}"
        return qualifier, getattr(mod, name)
    found = [(m, getattr(module(m), name)) for m in section["modules"] if hasattr(module(m), name)]
    if not found:
        if name in plan.ENV_VARS and "plan" in section["modules"]:
            return "setting", None          # a run setting plan.Account.from_env reads, not a module constant
        named = ", ".join(f"src/{m}.py" for m in section["modules"]) or "no module"
        return f"`{name}` in \"{section['title']}\": {named} names no {name}"
    if any(value != found[0][1] for _, value in found[1:]):
        return f"`{name}` in \"{section['title']}\": {[m for m, _ in found]} disagree on it; qualify it"
    return found[0]


def numeric(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def cells(line: str) -> list[str] | None:
    """A table row's cells, or None for a line that is not a table row."""
    if not line.startswith("|"):
        return None
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def tables(section: dict) -> list[dict]:
    """Each table of a section: its header cells and its body rows, as cells."""
    out, current = [], None
    for line in section["lines"]:
        row = cells(line)
        if row is None:
            current = None
        elif current is None:
            current = {"head": row, "rows": []}
            out.append(current)
        elif not all(set(cell) <= set("-: ") for cell in row):
            current["rows"].append(row)
    return out


def constants(text: str, section: dict) -> list[tuple]:
    """Every constant a piece of text names: (module, NAME, value, printed or
    None when no value is printed beside it)."""
    out = []
    for span in SPAN.finditer(text):
        hit = CONST.match(span.group(1))
        if not hit or span.group(1) in PLACEHOLDERS:
            continue
        got = resolve(hit.group(1), hit.group(2), section)
        if isinstance(got, str):
            continue
        printed = None
        if text[span.end():span.end() + 3] == " = ":
            printed = literal_after(text, span.end() + 3)[0]
        out.append((got[0], hit.group(2), got[1], printed))
    return out


def marks(name: str) -> dict[str, str]:
    """The provenance mark a module's own comments give each constant. A
    constant with a comment on its own line takes the mark that comment opens
    with or first names -- ``# (P) ...``, ``# ... (B: "his words")`` -- and
    none when it names none; a constant without one takes the ``#: (X)`` that
    opens the comment block above it (a block may introduce several constants
    in a row)."""
    out, mark = {}, None
    for line in (ROOT / "src" / f"{name}.py").read_text().splitlines():
        opened = re.match(r"#: \(([BPTRV])\)", line)
        assigned = re.match(r"([A-Z][A-Z0-9_]*) = ", line)
        if opened:
            mark = opened.group(1)
        elif line.startswith("#"):
            continue
        elif assigned:
            _, sep, comment = line.partition("  #")
            inline = re.search(r"\(([BPTRV])[):]", comment)
            if sep:
                mark = None                      # a commented line stands alone; the block above it is over
                if inline:
                    out[assigned.group(1)] = inline.group(1)
            elif mark:
                out[assigned.group(1)] = mark
        else:
            mark = None
    return out


def problems(text: str) -> list[str]:
    """Everything the sheet says that the code does not: one sentence each."""
    found: list[str] = []
    carried: dict[tuple, bool] = {}
    for section in parse(text):
        how_to = section["title"] == HOW_TO_READ
        for line in section["lines"]:
            for span in SPAN.finditer(line):
                token = span.group(1)
                if how_to and token in PLACEHOLDERS:
                    continue
                const, func = CONST.match(token), FUNC.match(token)
                if const:
                    got = resolve(const.group(1), const.group(2), section)
                    if isinstance(got, str):
                        found.append(got)
                        continue
                    where, value = got
                    has_value = line[span.end():span.end() + 3] == " = "
                    if where != "setting":
                        key = (where, const.group(2))
                        carried[key] = carried.get(key, False) or has_value
                    if has_value:
                        try:
                            printed, _ = literal_after(line, span.end() + 3)
                        except ValueError as exc:
                            found.append(str(exc))
                            continue
                        if isinstance(value, time) and not isinstance(printed, time):
                            found.append(f"`{token}` is a time of day; the sheet prints {printed!r}")
                        elif isinstance(printed, float) and not numeric(value):
                            found.append(f"`{token}` is {value!r}, not a number; the sheet prints {printed:g}")
                        elif printed != value:
                            found.append(f"`{token}` is {value!r} in src/{where}.py; the sheet prints {printed!r}")
                elif func:
                    names = [func.group(1)] if func.group(1) else section["modules"]
                    if func.group(1) and not (ROOT / "src" / f"{func.group(1)}.py").exists():
                        found.append(f"`{token}`: there is no src/{func.group(1)}.py")
                    elif not any(callable(getattr(module(m), func.group(2), None)) for m in names):
                        found.append(f"`{token}` in \"{section['title']}\": no such function in {names or 'any named module'}")
                elif FILE.match(token):
                    if not (ROOT / token).exists():
                        found.append(f"`{token}`: no such file")
                elif not FIELD.match(token):
                    found.append(f"`{token}` in \"{section['title']}\" is not a constant, a function, a file or a record field")
    found += [f"`{where}.{name}` is a number and the sheet never prints its value" for (where, name), has in carried.items()
              if not has and numeric(getattr(module(where), name))]
    return found


def stray_numbers(text: str) -> list[str]:
    """The lines of a rule sentence that carry a digit with no constant
    beside it. A heading, an example and a label column are not rule sentences."""
    out = []
    for section in parse(text):
        head: list[str] | None = None
        for line in section["lines"]:
            row = cells(line)
            if row is None:
                head = None
                if line.startswith(">"):
                    continue
                body = re.sub(r"^\d+\. ", "", line)
            else:
                if head is None:
                    head = row
                    continue
                body = " | ".join(cell for column, cell in zip(head, row) if column not in LABEL_COLUMNS)
            # a held value first (the span and what follows its "="), then every other span
            kept, at = "", 0
            for span in SPAN.finditer(body):
                if span.start() < at:
                    continue
                kept += body[at:span.start()]
                at = span.end()
                if CONST.match(span.group(1)) and body[at:at + 3] == " = ":
                    try:
                        at = literal_after(body, at + 3)[1]
                    except ValueError:
                        pass
            kept = NOT_A_RULE_NUMBER.sub("", kept + body[at:])
            if re.search(r"\d", kept):
                out.append(line.strip())
    return out


# ------------------------------------------------------------- the sheet ----
def test_every_constant_function_and_file_the_sheet_names_is_the_codes_own():
    assert problems(SHEET) == []
    named = {(where, name) for section in parse(SHEET) for line in section["lines"]
             for where, name, _, _ in constants(line, section)}
    assert len(named) >= 120, f"the sheet names {len(named)} constants; it named more"


def test_no_rule_sentence_carries_a_number_without_its_constant():
    assert stray_numbers(SHEET) == []
    # an example is the one place a bare number may stand, and says it is one
    quoted = [line for line in SHEET.splitlines() if line.startswith(">")]
    assert quoted and all(line.startswith("> Example (") for line in quoted), quoted


def test_every_section_that_states_a_rule_names_the_module_that_applies_it():
    sections = parse(SHEET)
    numbered = [s for s in sections if re.match(r"\d+\. ", s["title"])]
    assert [int(s["title"].split(".")[0]) for s in numbered] == list(range(len(numbered))), "sections out of order"
    assert len(numbered) >= 17
    for section in numbered:
        assert section["modules"], f"\"{section['title']}\" names no module"
        for name in section["modules"]:
            assert (ROOT / "src" / f"{name}.py").exists(), name
    # pipeline order: the light before discovery, the checklist before admission, admission
    # before the reads, the ticket before the fill, the fill before the exits
    order = [next(i for i, s in enumerate(numbered) if word in s["title"]) for word in
             ("Universe", "Market light", "Discovery", "Checklist", "Admission", "Chart reads", "Burst ticket",
              "Size", "Allocation", "Fill model", "Exits", "Scorecard")]
    assert order == sorted(order), order


def test_every_exit_step_the_breadth_rules_and_the_policies_are_on_the_sheet():
    by_title = {s["title"].split(" (")[0]: s for s in parse(SHEET)}
    exits = "\n".join(by_title["15. Exits"]["lines"])
    for rule in plan.EXIT_RULES:
        assert f"`{rule['key']}`" in exits, f"the exits section names no step {rule['key']}"
    light = by_title["3. Market light"]
    printed = {name: value for line in light["lines"] for _, name, _, value in constants(line, light)}
    for name in BREADTH_RULES:
        assert printed.get(name) == getattr(breadth, name), (name, printed.get(name))
    # the five are the five regime() reads, and each is stated under the verdict it gives
    verdicts = {row[0] for table in tables(light) if table["head"][0] == "Verdict" for row in table["rows"]}
    assert verdicts == {"RED", "YELLOW", "GREEN"}
    for table in tables(light):
        if table["head"][0] != "Verdict":
            continue
        for row in table["rows"]:
            names = [name for _, name, _, _ in constants(" | ".join(row), light)]
            if row[0] == "RED":
                assert names and set(names) <= {"DOWN4_ALARM", "RED_RATIO_10D", "RED_RATIO_5D"}, row
            if row[0] == "YELLOW":
                assert names and set(names) <= {"YELLOW_RATIO_10D", "UP50_MONTH_HOT"}, row
    for title, mod in (("6. Admission", admission), ("7. Chart reads", review_selection),
                       ("7. Chart reads", reader_coverage), ("13. Allocation", allocation),
                       ("14. Fill model", intraday)):
        section, name = by_title[title], mod.__name__.split(".")[-1]
        stated = [printed for line in section["lines"] for where, const, _, printed in constants(line, section)
                  if (where, const) == (name, "POLICY")]
        assert stated and all(printed == mod.POLICY for printed in stated), (title, name, stated)
    for veto in quality.VETO_NAMES:
        assert f"`{veto}`" in "\n".join(by_title["5. Checklist"]["lines"]), veto
    for route in admission.BURST_ROUTES + (admission.DOLLAR_ROUTE,):
        assert f"`{route}`" in "\n".join(by_title["6. Admission"]["lines"]), route


def test_the_sheet_states_the_checklist_as_the_module_scores_it():
    section = next(s for s in parse(SHEET) if s["title"].startswith("5. Checklist"))
    table = next(t for t in tables(section) if t["head"][0] == "Letter")
    assert [row[0] for row in table["rows"]] == list(quality.LETTERS) + list(quality.EXTRA_CHECKS) or \
        sorted(row[0] for row in table["rows"]) == sorted(quality.LETTERS + quality.EXTRA_CHECKS)
    weights = {row[0]: row[1] for row in table["rows"]}
    for letter in quality.LETTERS:
        assert weights[letter] == f"`WEIGHT_{letter}` = {quality.WEIGHTS[letter]}", (letter, weights[letter])
    for letter in quality.EXTRA_CHECKS:
        assert weights[letter] == "none", "RE and VOL score nothing"
    assert sum(quality.WEIGHTS.values()) == 10 and "The weights sum to ten" in SHEET
    assert quality.GATE_CAP == grader.GRADE_BANDS[2][1] and "capped at the third band" in SHEET


def test_a_rows_class_agrees_with_the_mark_the_module_gives_its_constants():
    """A constant plan.py marks (B) cannot sit in a row the sheet classes as
    this project's alone, nor a (P) one in a row classed as his."""
    by_module = {name: marks(name) for name in MARKED_MODULES}
    assert len(by_module["plan"]) >= 50 and len(by_module["watchlist"]) >= 25, {k: len(v) for k, v in by_module.items()}
    checked = 0
    for section in parse(SHEET):
        for table in tables(section):
            if "Class" not in table["head"]:
                continue
            at = table["head"].index("Class")
            for row in table["rows"]:
                classes = set(CLASS_TOKEN.findall(row[at]))
                assert classes or row[at] in UNCLASSED, f"no class on the row {row}"
                for where, name, _, _ in constants(" | ".join(row), section):
                    mark = by_module.get(where, {}).get(name)
                    if mark is None:
                        continue
                    checked += 1
                    assert classes & MARK_CLASSES[mark], (
                        f"src/{where}.py marks {name} ({mark}); the sheet's row is classed {row[at]!r}")
    assert checked >= 60, checked
    # each printed exit step carries, on at least one of its rows, the class of its own source
    section = next(s for s in parse(SHEET) if s["title"].startswith("15. Exits"))
    rows = [(row[t["head"].index("Step")], set(CLASS_TOKEN.findall(row[t["head"].index("Class")])))
            for t in tables(section) if "Step" in t["head"] for row in t["rows"]]
    for rule in plan.EXIT_RULES:
        given = [classes for step, classes in rows if step == f"`{rule['key']}`"]
        assert any(classes & MARK_CLASSES[rule["source"]] for classes in given), (rule["key"], rule["source"], given)


def test_the_class_table_defines_the_eight_classes_and_no_row_uses_another():
    section = next(s for s in parse(SHEET) if s["title"] == "Provenance classes")
    table = tables(section)[0]
    assert tuple(row[0] for row in table["rows"]) == CLASSES
    for other in parse(SHEET):
        for t in tables(other):
            if "Class" in t["head"] and other is not section:
                at = t["head"].index("Class")
                for row in t["rows"]:
                    words = re.sub(r"`[^`]*`( = \S+)?", "", row[at])
                    shouted = set(re.findall(r"\b[A-Z][A-Z*]+(?: [A-Z]+)?\b\*?", words)) - {"A", "RED"}
                    assert shouted <= set(CLASSES) | {"B"}, (row[at], shouted)


def test_the_sheet_answers_what_is_bondes_and_what_is_this_projects():
    section = next(s for s in parse(SHEET) if s["title"] == "What is Bonde's and what is this project's")
    parts = [row[0] for row in tables(section)[0]["rows"]]
    for part in ("Entering the next session", "The stop before day one closes", "The checklist's weights and bands",
                 "The admission gate", "The chart reader", "The market light's thresholds"):
        assert part in parts, part
    sections = parse(SHEET)
    assert sections.index(section) < next(i for i, s in enumerate(sections) if s["title"].startswith("0. "))


# ------------------------------------------- what no constant states, run ----
def bar(close: float, low_pct: float, range_pct: float) -> dict:
    """A burst bar: its low ``low_pct`` under the close, its high ``range_pct`` over the low."""
    low = round(close * (1 - low_pct / 100), 2)
    high = round(max(close, low * (1 + range_pct / 100)), 2)
    return {"close": close, "low": low, "high": high, "open_": low, "prev_close": round(close / 1.05, 2)}


def test_every_burst_ticket_at_or_over_the_price_floor_has_its_risk_halved():
    """Section 10: the limit is set from the stop, so the stop always sits
    between the ideal line and the maximum, and the stop-risk multiplier is
    the halving on every ticket. A sweep over bar shapes and prices."""
    account = plan.Account()
    eligible = withheld = by_low = by_midpoint = at_ceiling = 0
    closes = [universe.MIN_PRICE + step * 0.01 for step in range(0, 300, 7)] + [7.77, 19.28, 53.1, 124.21, 531.56, 2499.99]
    for close in closes:
        for low_pct in (0.02, 0.1, 0.3, 1.0, 2.5, 3.9, 4.1, 6.0, 12.0):
            for range_pct in (0.5, 2.0, 5.0, 9.0, 20.0):
                shape = bar(round(close, 2), low_pct, range_pct)
                made = plan.burst_plan(ticker="XMPL", gain_pct=5.0, account=account, **shape)
                if not made["eligible"]:
                    withheld += 1
                    continue
                eligible += 1
                by_low += made["stop_basis"] == "burst_low"
                by_midpoint += made["stop_basis"] == "half_range"
                at_ceiling += made["limit_basis"] == "outer_ceiling"
                assert plan.IDEAL_STOP_PCT < made["stop_pct"] <= plan.MAX_STOP_PCT, (shape, made["stop_pct"])
                assert made["stop_risk_multiplier"] == plan.STOP_RISK_MULTIPLIER and "risk_halved" in made["flags"], shape
    # the sweep reached both stand-in stops, both limits and a withheld ticket
    assert min(eligible, withheld, by_low, by_midpoint, at_ceiling) > 0, (eligible, withheld, by_low, by_midpoint, at_ceiling)
    assert "Every burst ticket on a stock at or over the price floor" in SHEET


SIGNAL = date(2026, 8, 20)
PICK = {"ticker": "XMPL", "date": str(SIGNAL), "kind": "burst", "entry_ref": 100.0, "stop": 97.0, "shares": 10,
        "entry_high": 101.0, "entry_low": 98.0}


def walk(*rows, pick=PICK):
    days = [str(d) for d in plan.next_sessions(SIGNAL, len(rows))]
    bars = [{"date": day, "o": o, "h": h, "l": lo, "c": c} for day, (o, h, lo, c) in zip(days, rows)]
    row = record.replay(pick, bars)
    return row, record.r_multiple(row, pick["stop"])


def test_what_the_model_books_at_a_stop_is_what_the_sheet_says():
    """Section 16, each sentence held on the sheet and then run on synthetic
    bars: a 100.00 buy stop filled at a 100.50 open, the published stop 97.00."""
    stated = " ".join(next(s for s in parse(SHEET) if s["title"].startswith("16. "))["lines"])

    def says(sentence: str) -> None:
        assert sentence in stated, f"section 16 no longer says: {sentence}"

    # a low through the stop on the fill day: out at exactly the stop, exactly minus one R
    says("A session whose low reaches the stop, after an open above it, is booked out at exactly the stop price.")
    row, r = walk((100.5, 101.0, 90.0, 91.0))
    assert (row["status"], row["exit_price"], r) == ("stopped", 97.0, -1.0)
    # however far under the stop that day closed: the close does not enter it
    says("always reads exactly minus one R, however far under the stop the day closed")
    assert walk((100.5, 101.0, 60.0, 61.0))[1] == -1.0
    # a later session that opens under the stop is out at that open: more than one R
    says("A session that opens at or under the stop is booked out at that open. The loss is then larger than one R.")
    row, r = walk((100.5, 101.0, 99.0, 100.8), (94.0, 95.0, 93.0, 94.5))
    assert (row["events"][-1]["event"], row["exit_price"]) == ("stopped_at_open", 94.0) and r < -1.0
    # the stop wins inside a bar: this one reached +8% and the (raised) stop, and is booked stopped
    says("The stop wins inside a bar: a bar that reached both the stop and a sale level is booked as stopped.")
    row, r = walk((100.5, 101.0, 100.0, 100.8), (101.0, 109.0, 99.9, 108.0))
    assert row["status"] == "stopped" and not any(e["event"] == "sell_half" for e in row["events"])
    # a raised stop can sit above the fill: "stopped" at a gain
    says('A stop raised by an exit step can sit above the fill, so a plan can be "stopped" at a gain.')
    row, r = walk((100.5, 109.0, 100.2, 108.5), (108.9, 109.0, 108.0, 108.2))
    assert row["status"] == "stopped" and row["exit_price"] > 100.5 and r > 0
    # a stop raised under a day's high can sit above that day's close: the next open under it is booked at that open
    says("can also sit above that day's close, and the next open at or under it is booked out at that open")
    row, r = walk((100.5, 112.0, 100.2, 111.0), (111.7, 112.0, 111.0, 111.5))
    raised = max(e["price"] for e in row["events"] if e["event"] == "stop_raised")
    assert raised > 111.0 and (row["events"][-1]["event"], row["exit_price"]) == ("stopped_at_open", 111.7)
    # one share cannot be halved: the half-sale step sells it all, and the R differs from ten shares on the same bars
    says("a position of one share cannot be halved: the half-sale step sells it all")
    says("The same bars can therefore give a different R at a different size.")
    one, r_one = walk((100.5, 109.0, 100.2, 108.5), (108.9, 109.0, 108.0, 108.2), pick={**PICK, "shares": 1})
    assert one["status"] == "exit" and one["remaining"] == 0 and r_one != r_with_ten()
    # opened under the trigger, reached it and the stop: the daily bar cannot order them
    says("A first day that opened under the trigger, reached it, and also reached the stop is uncertain unless")
    row, r = walk((99.0, 100.5, 96.5, 99.5))
    assert (row["status"], row["uncertainty"], r) == (record.UNCERTAIN, "stop_sequence", None)


#: the permanent quality ledger's entry for the 5 Nov 2026 publication, named by that publication's SHA-256
LEDGER_5_NOV = "fdba3e95ea5e17bd6408c9b0415247b417931d0e82608c90c74a950066a7b812"


def test_the_dated_stop_example_is_what_the_ledger_retained():
    """Section 16's example, first sentence: the burst tickets the 4 Nov 2026
    record published, as the ledger entry of the next night scored them. The
    ledger is the one archive nothing prunes (``quality_ledger.append()``).
    The example's second half, the same exits read at that day's close and at
    its low, was worked from the 5 Nov 2026 publication (each plan's fill and
    stop, and that session's bar in its observations block) and is held by no
    file in this checkout; the arithmetic it claims is ``r_multiple()``'s and
    is run below on a synthetic bar."""
    path = ROOT / "docs" / "quality-ledger" / "v1" / f"{LEDGER_5_NOV}.json.gz"
    entry = json.loads(gzip.decompress(path.read_bytes()))
    assert entry["publication"]["session"] == "2026-11-05"
    rows = [row for row in entry["outcome"]["rows"] if (row["kind"], row["picked"]) == ("burst", "2026-11-04")]
    assert len(rows) == 3, [row["ticker"] for row in rows]
    for row in rows:
        # minus one R exactly is a full exit at the stop: r_multiple() over one sale of every share
        assert (row["status"], row["through"], row["r"]) == ("stopped", "2026-11-05", -1.0), row
    assert ("> Example (the three burst tickets of the 4 Nov 2026 record): each was stopped on day one, 5 Nov 2026, "
            "and each is booked at exactly its stop, minus 1.00 R.") in SHEET
    # the two bounds the example and the brief's model record give are the booked exit moved to the
    # close and to the low: on a 100.50 fill with a 97.00 stop, a 91.00 close and a 90.00 low
    stated = " ".join(next(s for s in parse(SHEET) if s["title"].startswith("16. "))["lines"])
    assert "`booked`, what the rules above book; `at_close`, the same exit at that session's close; and `at_low`" in stated
    row, booked = walk((100.5, 101.0, 90.0, 91.0))
    moved = {name: record.r_multiple({**row, "events": [{**e, "price": price} for e in row["events"] if e.get("shares")]},
                                     PICK["stop"]) for name, price in (("at_close", 91.0), ("at_low", 90.0))}
    assert (booked, moved) == (-1.0, {"at_close": -2.71, "at_low": -3.0})


def r_with_ten() -> float:
    return walk((100.5, 109.0, 100.2, 108.5), (108.9, 109.0, 108.0, 108.2))[1]


def test_the_abnormal_close_books_no_sale_and_the_eight_percent_rule_runs_to_day_three():
    """Section 15, steps 5 and 6: what the model does where the ticket's words say more."""
    # a 10% close with no +8% sale possible is not a case (the high reaches +8% first), so read the events
    row, _ = walk((100.5, 112.0, 100.2, 111.0))
    assert [e["event"] for e in row["events"]] == ["sell_half", "stop_raised", "abnormal_day"]
    assert sum(1 for e in row["events"] if e.get("shares")) == 1, "the abnormal close books no sale of its own"
    # +8% first reached on day 3, not "the same or next day": the model still sells the half there
    row, _ = walk((100.5, 101.0, 100.2, 100.8), (100.9, 102.0, 100.6, 101.5), (101.6, 109.0, 101.2, 108.0))
    assert [(e["day"], e["event"]) for e in row["events"] if e.get("shares")] == [(3, "sell_half")]
    level = round(100.5 * (1 + plan.SELL_HALF_PCT / 100), 2)
    assert row["events"][-2]["price"] == level
    # the half is booked at the level, or at the open when the session opened above it
    assert "The sale is booked at that level, or at the open when the session opened above it." in SHEET
    row, _ = walk((100.5, 101.0, 100.2, 100.8), (110.0, 111.0, 109.9, 110.5))
    sale = next(e for e in row["events"] if e["event"] == "sell_half")
    assert level < sale["price"] == 110.0 < round(100.5 * (1 + plan.GAP_EXIT_PCT / 100), 2)
    # the order the sheet numbers the steps in is the order follow() meets them in
    source = (ROOT / "src" / "plan.py").read_text().split("def follow(", 1)[1].split("\ndef ", 1)[0]
    met = [source.index(marker) for marker in (
        "day > FINAL_EXIT_DAY", "if o <= stop", 'o >= levels["gap_exit"]', "if l <= stop", 'h >= levels["sell_half"]',
        'c >= levels["abnormal"]', "day == NO_PROGRESS_DAY", "day == SELL_HALF_DAY", "day == ENTRY_DAY and entry_low",
        "day >= TRAIL_FROM_DAY", "day >= FINAL_EXIT_DAY", "regime == RED_REGIME")]
    assert met == sorted(met), met
    section = next(s for s in parse(SHEET) if s["title"].startswith("15. Exits"))
    table = next(t for t in tables(section) if t["head"][0] == "Order")
    assert [row[0] for row in table["rows"]] == [str(n) for n in range(1, len(met) + 1)]
    steps = [row[1].strip("`") for row in table["rows"]]
    assert steps == ["", "stop", "gap_20pct", "stop", "sell_half_8pct", "abnormal_10pct", "day3_no_progress",
                     "day3_sell_half", "entry_day_low", "trail_after_day3", "day5_exit", ""], steps


def test_the_dated_examples_are_the_arithmetic_they_claim():
    """An example's numbers are not rules, but the ones that are arithmetic
    over a rule are still the rule's: the scaling, and the production budget."""
    scaled = [breadth.scaled_threshold(getattr(breadth, name), 3513)
              for name in ("DOWN4_ALARM", "UP50_MONTH_HOT", "DOWN25_QUARTER_OVERSOLD")]
    assert "> Example (17 Nov 2026 record, N = 3,513): 700 scales to {:g}, 20 to {:g} and 200 to {:g}.".format(*scaled) in SHEET
    workflow = (ROOT / ".github" / "workflows" / "evening.yml").read_text()
    equity = float(re.search(r"ACCOUNT_EQUITY: '([\d.]+)'", workflow).group(1))
    risk_pct = float(re.search(r"RISK_PCT: '([\d.]+)'", workflow).group(1))
    assert f"`ACCOUNT_EQUITY` {equity:,.0f} and `RISK_PCT` {risk_pct:g}" in SHEET
    budget = equity * risk_pct / 100
    green = budget * breadth.SIZE_MULTIPLIER["green"] * plan.STOP_RISK_MULTIPLIER
    yellow = budget * breadth.SIZE_MULTIPLIER["yellow"] * plan.STOP_RISK_MULTIPLIER
    assert f"the full budget is ${budget:,.0f}. A burst ticket risks ${green:g} on a GREEN night and ${yellow:.2f} on a YELLOW night" in SHEET


def test_the_ticket_section_states_the_two_broker_rules_the_note_sources():
    """Section 9, last row: the two Fidelity rules the ticket leans on are the
    broker note's own headings, and what stays unconfirmed is on its list."""
    section = next(s for s in parse(SHEET) if s["title"].startswith("9. Burst ticket"))
    row = next(row for table in tables(section) for row in table["rows"] if "`OTO`" in row[0])
    assert row[1] == "R"
    assert "release such a stop only when the buy fills in full, and take a buy stop only above the current price" in row[0]
    assert "whether Fidelity accepts this ticket before the open is unconfirmed" in row[0]
    note = re.sub(r"\s+", " ", (ROOT / "knowledge" / "broker-fidelity.md").read_text())
    assert "**The OTO's sell stop is released only when the buy fills in full.**" in note
    assert "**A buy stop must be priced above the current market.**" in note
    assert "- The price Fidelity compares a buy stop against before the open." in note
    assert plan.OTO == "one_triggers_the_other"
    made = plan.fidelity_orders("XMPL", 10, trigger=19.28, limit=19.57, stop=18.79)
    assert made["order_json"]["conditional"] == plan.OTO and made["order_json"]["then"]["order_type"] == "stop"
    # a burst's trigger is its signal close
    assert plan.burst_limit(19.28, 18.79, 19.38)["trigger"] == 19.28


def test_the_setting_up_pool_states_each_scans_own_volume_operator():
    """Section 4: Double Trouble asks at least the volume floor of the prior
    sessions, the other two momentum scans more than it (``scans.RULES`` names
    the two strict ones ``_exclusive``)."""
    assert ("at least `MIN_VOLUME` = 100,000 shares for Double Trouble, and more than that for the other two.") in SHEET
    assert scans.RULES["dt.min_prior_volume"] == scans.RULES["ti65.min_prior_volume_exclusive"] \
        == scans.RULES["mdt.min_prior_volume_exclusive"] == scans.MIN_VOLUME
    assert not any(key in scans.RULES for key in ("dt.min_prior_volume_exclusive", "ti65.min_prior_volume",
                                                  "mdt.min_prior_volume"))


def test_a_rerun_replaces_the_plans_it_issues_again_and_keeps_the_rest():
    """Section 17, last row: ``record.append()`` keys a plan by session, ticker
    and kind, so a later run of one session replaces only what it issues again."""
    assert ("A later run of the same session replaces a plan it issues again (the same session, ticker and kind, "
            "`append()`). A plan the later run no longer issues stays in the record and in the scorecard.") in SHEET
    first = [{**PICK, "ticker": name} for name in ("KEPT", "XMPL")]
    rec = record.append(record.empty(), str(SIGNAL), first)
    again = record.append(rec, str(SIGNAL), [{**PICK, "shares": 7}])
    assert [(p["ticker"], p["shares"]) for p in again["picks"]] == [("KEPT", 10), ("XMPL", 7)]
    # the same setup offered on the next night is a new plan beside the old one
    later = record.append(again, str(plan.next_sessions(SIGNAL, 1)[0]), [dict(PICK)])
    assert [p["ticker"] for p in later["picks"]].count("XMPL") == 2
    assert "Each night's re-offer of the same setup is a new plan and is counted again." in SHEET


# ----------------------------------------------------- the guard can fail ----
def swapped(old: str, new: str) -> str:
    assert SHEET.count(old) == 1, (SHEET.count(old), old)
    return SHEET.replace(old, new)


def test_a_drifted_number_a_missing_constant_and_a_bare_number_are_each_refused():
    drifted = problems(swapped("`DOWN4_ALARM` = 700", "`DOWN4_ALARM` = 710"))
    assert drifted == ["`DOWN4_ALARM` is 700 in src/breadth.py; the sheet prints 710.0"], drifted
    drifted = problems(swapped("`STOP_RISK_MULTIPLIER` = 0.5", "`STOP_RISK_MULTIPLIER` = 0.75"))
    assert drifted == ["`STOP_RISK_MULTIPLIER` is 0.5 in src/plan.py; the sheet prints 0.75"], drifted
    words = problems(swapped('`POLICY` = "burst_route_or_dollar_expansion_v1"', '`POLICY` = "burst_route_only_v1"'))
    assert words == ["`POLICY` is 'burst_route_or_dollar_expansion_v1' in src/admission.py; the sheet prints 'burst_route_only_v1'"]
    clock = problems(swapped("`EVENING_PRIMARY_ET` = 18:16", "`EVENING_PRIMARY_ET` = 18:46"))
    assert len(clock) == 1 and "EVENING_PRIMARY_ET" in clock[0]
    renamed = problems(swapped("`MAX_GIVEBACK` = 0.34", "`MAX_GIVE_BACK` = 0.34"))
    assert renamed == ['`MAX_GIVE_BACK` in "5. Checklist (`src/quality.py`, `src/grader.py`)": src/quality.py, src/grader.py names no MAX_GIVE_BACK'], renamed
    wrong_module = problems(swapped("`pipeline.MAX_READS` = 12", "`plan.MAX_READS` = 12"))
    assert wrong_module == ["`plan.MAX_READS`: src/plan.py names no MAX_READS"], wrong_module
    unprinted = problems(swapped("`RESEARCH_MAX` = 2 research reads", "`RESEARCH_MAX` research reads"))
    assert unprinted == ["`review_selection.RESEARCH_MAX` is a number and the sheet never prints its value"], unprinted
    gone = problems(swapped("(`scaled_threshold()`)", "(`scale_threshold()`)"))
    assert len(gone) == 1 and "no such function" in gone[0]
    # a number typed into a rule sentence with no constant beside it
    bare = stray_numbers(swapped("is the burst failing and is not taken", "is the burst failing and is not taken; 3% is fine"))
    assert len(bare) == 1 and "3% is fine" in bare[0]
    bare = stray_numbers(swapped("at most `MAX_UP_RUN` = 1 day rose", "at most 1 day rose"))
    assert len(bare) == 1 and bare[0].startswith("| 2 |")
    # and the unchanged sheet is clean under the same two readers: the control
    assert problems(SHEET) == [] and stray_numbers(SHEET) == []
    assert problems(swapped("places no order, reads no account", "places no orders, reads no accounts")) == []


def test_the_value_reader_reads_each_kind_of_value_the_sheet_prints():
    assert literal_after('x = 100,000 shares.', 4) == (100000.0, 11)
    assert literal_after('x = 0.90 dollars', 4) == (0.9, 8)
    assert literal_after('x = 4.', 4) == (4.0, 5)
    assert literal_after('x = 18:16 New York', 4)[0] == time(18, 16)
    assert literal_after('x = "order_limit").', 4) == ("order_limit", 17)
    assert literal_after('x = ("A+", "A"). YELLOW', 4)[0] == ("A+", "A")
    assert literal_after('x = {"green": 1.0, "red": 0.0}.', 4)[0] == {"green": 1.0, "red": 0.0}
    for unreadable in ("x = about four", "x = (1, 2"):
        try:
            literal_after(unreadable, 4)
        except ValueError:
            continue
        raise AssertionError(unreadable)
    # the marks the class test reads are the modules' own comments
    found = marks("plan")
    assert (found["MAX_STOP_PCT"], found["STOP_RISK_MULTIPLIER"], found["GAIN_CEILING_PCT"], found["SETTLEMENT_DAYS"],
            found["TARGET_HIGH_PCT"], found["TRAIL_CENTS_MAX"]) == ("B", "P", "T", "R", "B", "B")
    assert (marks("watchlist")["TIGHT_FRACTION"], marks("watchlist")["TTT_SESSIONS"], marks("watchlist")["MIN_COMPRESS"]) == ("P", "B", "P")
    assert (marks("pipeline")["MAX_READS"], marks("pipeline")["TRADE_GRADES"], marks("pipeline")["STALE_SESSIONS_MAX"]) == ("P", "B", "P")
    assert marks("record")["SCORECARD_MIN_PLANS"] == "P" and marks("record")["OPEN_PLAN_SESSIONS"] == "B"
    assert scans.BREAKDOWN_RATIO == 0.96 and pipeline.MAX_READS == 12   # the two qualified constants the drift test moves
