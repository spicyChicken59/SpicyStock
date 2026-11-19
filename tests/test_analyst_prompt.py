"""The outside analyst's standing instructions (``docs/analyst/``) are true
for the code as it stands.

The prompt is read by a bot with no other context, so a number it states
must be the module's own. Three holds, each built from the constant and
never from the document:

* every row of the prompt's constants table (Appendix A) is the named
  constant, and the table carries the ones the method turns on;
* the sentences of the rule sheet, the sizing section and the position
  section that state a number are rebuilt here from the constants and must
  appear word for word;
* a repeat of a number anywhere else in the file (every "+N%", every
  "N of 6,500", every "first N minutes" ...) must be one of the constants'.

Beside the numbers: the URLs are the repository's own, the brief's section
names are the fourteen the brief writes, the bootstrap note stays under its
bound, and nothing in the three public files is an email address, an account
number, the owner's name or a dollar figure that is not the model's or a
labelled synthetic example.

A sentence can also be wrong with every number in it right: two steps in the
wrong order, "or" where the code asks "and", "the limit" for "the trigger",
"down" for "up". The last part of this file holds those by execution: it runs
the rule's own function on cases built to decide the word, reads what the code
did, and only then says which sentence the prompt must carry."""
from __future__ import annotations

import copy
import datetime as dt
import functools
import importlib
import itertools
import json
import re
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

import pytest

from src import (admission, breadth, delivery, event_risk, funnel, grader, intraday, morning, pipeline, plan, quality,
                 reader_coverage, record, report, review_selection, scans, sessions, timing, universe, watchlist)

ROOT = Path(__file__).resolve().parent.parent
ANALYST = ROOT / "docs" / "analyst"
PROMPT_RAW = (ANALYST / "prompt.md").read_text()
BOOTSTRAP_RAW = (ANALYST / "bootstrap.md").read_text()
README_RAW = (ANALYST / "README.md").read_text()
FILES = {"prompt.md": PROMPT_RAW, "bootstrap.md": BOOTSTRAP_RAW, "README.md": README_RAW}


def prose(text: str) -> str:
    """The text with its line wraps collapsed, so a sentence is matched as a
    sentence and not as the width it happened to be wrapped at."""
    return re.sub(r"\s+", " ", text)


PROMPT = prose(PROMPT_RAW)

#: The bootstrap note is pasted into a bot's instruction box; the task's bound.
BOOTSTRAP_MAX_CHARS = 2000
#: The brief's sections, in order, as section 6 of the prompt lists them.
SECTION_NAMES = (
    "Identity and binding", "Service state", "Market regime", "Model account", "Published model tickets",
    "Admitted trade-band candidates", "Research tail", "Setting up", "Open model plans", "Model record",
    "Event registry and coverage", "Rules", "Bounds", "What this file does not establish",
)
#: The seventeen parts the instructions are made of, by a word of each heading.
PARTS = ("Role", "has and has not shown", "Inputs", "First step", "rule sheet", "read the brief",
         "decision framework", "Research for one candidate", "Sizing and cash", "Fidelity order entry",
         "open position", "Cadence", "Message templates", "ledger", "report back", "private profile", "Glossary")
#: The quote page the owner's own rubric asks the analyst to open. Not a
#: repository constant: it is his check, and the only outside host allowed.
OWNER_QUOTE_CHECK = "https://www.cnn.com/markets/stocks/"
WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
         "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen")
#: The day the prompt is dated. Only the offset between New York and Chicago
#: is read off it, and the two change their clocks on the same nights.
DATED = dt.date(2026, 11, 19)
CHICAGO = ZoneInfo("America/Chicago")


# ------------------------------------------------------------ helpers -----
def g(value: float) -> str:
    """4.0 -> '4', 0.5 -> '0.5', 1.04 -> '1.04'."""
    return f"{value:g}"


def n(value: float) -> str:
    """100000 -> '100,000'."""
    assert float(value).is_integer(), value
    return f"{int(value):,}"


def usd(value: float) -> str:
    return f"${value:,.0f}" if float(value).is_integer() else f"${value:,.2f}"


def clock(moment: dt.time) -> str:
    """09:30 -> '9:30 AM'."""
    return f"{moment.hour % 12 or 12}:{moment.minute:02d} {'AM' if moment.hour < 12 else 'PM'}"


def bare(moment: dt.time) -> str:
    return clock(moment).rsplit(" ", 1)[0]


def eastern(moment: dt.time, minutes: int = 0) -> dt.time:
    return (dt.datetime.combine(DATED, moment) + dt.timedelta(minutes=minutes)).time()


def chicago(moment: dt.time, minutes: int = 0) -> dt.time:
    there = dt.datetime.combine(DATED, moment, tzinfo=sessions.MARKET_TZ) + dt.timedelta(minutes=minutes)
    return there.astimezone(CHICAGO).time()


def stated(*phrases: str, text: str = PROMPT) -> None:
    missing = [phrase for phrase in phrases if phrase not in text]
    assert not missing, missing


def every(pattern: str, text: str = PROMPT) -> list[str]:
    found = re.findall(pattern, text)
    assert found, pattern
    return found


def between(start: str, end: str | None, text: str = PROMPT_RAW) -> str:
    assert text.count(start) == 1, start
    rest = text.split(start, 1)[1]
    if end is None:
        return rest
    assert end in rest, end
    return rest.split(end, 1)[0]


def paragraphs(text: str) -> list[str]:
    return [block for block in re.split(r"\n\s*\n", text) if block.strip()]


def sentences(block: str) -> list[str]:
    return re.split(r"(?<=[.:;?!])\s+", prose(block))


# -------------------------------------------- Appendix A: the constants ---
REFERENCE = re.compile(r"^(?P<module>[a-z_]+)\.(?P<name>[A-Z][A-Z0-9_]*)(?P<index>(?:\[[A-Za-z0-9_]+\])*)$")
NUMBER = re.compile(r"^\d[\d,]*(?:\.\d+)?$")
#: What the task names: the table may grow, and may not lose one of these.
REQUIRED_ROWS = {
    "plan.DEFAULT_RISK_PCT", "plan.DEFAULT_MAX_OPEN_POSITIONS", "plan.DEFAULT_MAX_POSITION_PCT",
    "plan.MAX_STOP_PCT", "plan.SELL_HALF_PCT", "plan.ENTRY_WINDOW_MINUTES",
    "plan.ENTRY_DAY", "plan.SELL_HALF_DAY", "plan.NO_PROGRESS_DAY", "plan.TRAIL_FROM_DAY", "plan.FINAL_EXIT_DAY",
    "plan.NO_BREAKEVEN_BEFORE_DAY", "plan.ENTRY_ABOVE_PCT", "plan.ABNORMAL_DAY_PCT", "plan.GAP_EXIT_PCT",
    "scans.BURST_RATIO", "scans.MIN_VOLUME", "scans.DOLLAR_MOVE",
    "breadth.REFERENCE_UNIVERSE", "breadth.DOWN4_ALARM", "breadth.UP50_MONTH_HOT", "breadth.RED_RATIO_10D",
    "breadth.RED_RATIO_5D", "breadth.YELLOW_RATIO_10D", "breadth.SIZE_MULTIPLIER[green]",
    "breadth.SIZE_MULTIPLIER[yellow]", "breadth.SIZE_MULTIPLIER[red]",
    "grader.GRADE_BANDS[0][0]", "grader.GRADE_BANDS[1][0]", "grader.GRADE_BANDS[2][0]", "grader.GRADE_BANDS[3][0]",
    "pipeline.TRADE_GRADES", "pipeline.YELLOW_GRADES", "pipeline.MAX_READS", "review_selection.RESEARCH_MAX",
}


def constants_table(text: str = PROMPT_RAW) -> list[tuple[str, str, str]]:
    """Every row of the table under its header, as (what, value, reference).
    A row that names no constant is refused: it would be a number nobody holds."""
    lines = [line for line in between("## Appendix A.", "\n## ", text).splitlines() if line.startswith("|")]
    assert lines[0] == "| What | Value | Constant |" and set(lines[1]) <= set("|-"), lines[:2]
    rows = []
    for line in lines[2:]:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        assert len(cells) == 3 and cells[2].startswith("`") and cells[2].endswith("`"), f"no constant named: {line}"
        rows.append((cells[0], cells[1], cells[2].strip("`")))
    return rows


def resolve(reference: str):
    match = REFERENCE.match(reference)
    assert match, f"not a constant reference: {reference}"
    value = getattr(importlib.import_module(f"src.{match['module']}"), match["name"])
    for key in re.findall(r"\[([A-Za-z0-9_]+)\]", match["index"]):
        value = value[int(key)] if key.isdigit() else value[key]
    return value


def row_problem(what: str, cell: str, reference: str) -> str | None:
    """Why a table row is not its constant, or None when it is."""
    value = resolve(reference)
    if isinstance(value, dt.time):
        return None if cell == f"{value.hour:02d}:{value.minute:02d}" else f"{what}: {cell} is not {value}"
    if isinstance(value, str):
        return None if cell == value else f"{what}: {cell} is not {value}"
    if isinstance(value, (tuple, list)):
        return None if cell == ", ".join(str(item) for item in value) else f"{what}: {cell} is not {value}"
    assert isinstance(value, (int, float)) and not isinstance(value, bool), reference
    if not NUMBER.match(cell):
        return f"{what}: {cell} is not a number"
    return None if float(cell.replace(",", "")) == float(value) else f"{what}: {cell} is not {value:g}"


def test_every_row_of_the_constants_table_is_its_modules_constant():
    rows = constants_table()
    problems = [problem for row in rows if (problem := row_problem(*row))]
    assert not problems, problems
    references = [reference for _, _, reference in rows]
    assert len(references) == len(set(references)), "a constant is listed twice"
    assert REQUIRED_ROWS <= set(references), sorted(REQUIRED_ROWS - set(references))


def test_the_tables_grade_rows_name_the_grade_each_band_gives():
    labels = {reference: what for what, _, reference in constants_table()}
    for index, (_, grade) in enumerate(grader.GRADE_BANDS):
        assert labels[f"grader.GRADE_BANDS[{index}][0]"] == f"{grade} from"
    for verdict in breadth.VERDICTS:
        assert labels[f"breadth.SIZE_MULTIPLIER[{verdict}]"] == f"Size multiplier, {verdict.upper()}"


def test_a_drifted_row_is_named():
    """The comparison itself can fail: a value that is not the constant's, a
    cell that is not a number, and a reference that names no constant."""
    assert row_problem("Slots", str(plan.DEFAULT_MAX_OPEN_POSITIONS), "plan.DEFAULT_MAX_OPEN_POSITIONS") is None
    assert row_problem("Slots", str(plan.DEFAULT_MAX_OPEN_POSITIONS + 1), "plan.DEFAULT_MAX_OPEN_POSITIONS")
    assert row_problem("Slots", "four", "plan.DEFAULT_MAX_OPEN_POSITIONS")
    assert row_problem("Limit rule", plan.LIMIT_RULE + "_v2", "plan.LIMIT_RULE")
    assert row_problem("The open", "9:30", "timing.REGULAR_OPEN_ET")
    assert row_problem("Grades", "A+", "pipeline.TRADE_GRADES")
    for nothing in ("plan.NOT_A_CONSTANT", "nothing.DEFAULT_RISK_PCT"):
        try:
            resolve(nothing)
        except (AttributeError, ImportError):
            continue
        raise AssertionError(nothing)


# ------------------------------------------------- the rule sheet's words -
def test_the_rule_sheet_states_when_the_run_and_the_window_are():
    opens, window = timing.REGULAR_OPEN_ET, plan.ENTRY_WINDOW_MINUTES
    stated(
        f"scheduled for {clock(delivery.EVENING_PRIMARY_ET)} ET ({clock(chicago(delivery.EVENING_PRIMARY_ET))} CT), "
        f"with a retry at {clock(delivery.EVENING_RETRY_ET)} ET ({clock(chicago(delivery.EVENING_RETRY_ET))} CT)",
        f"the first {window} minutes after the {clock(opens)} ET open, which is {bare(chicago(opens))} to "
        f"{clock(chicago(opens, window))} CT",
        f"ready by {clock(timing.PREPARE_BEFORE_ET)} ET ({clock(chicago(timing.PREPARE_BEFORE_ET))} CT)",
        f"an unfilled buy is still open after {clock(chicago(opens, window))} CT",
        f"the open is {clock(chicago(opens))} CT ({clock(opens)} ET)",
        f"Cancel it at {clock(chicago(opens, window))} CT if it has not filled.",
        f"**The {clock(chicago(opens, window))} CT cancel.**",
        f"At {clock(chicago(opens, window))} CT ({clock(eastern(opens, window))} ET) he cancels",
        f"An expiry time ({clock(chicago(opens, window))} CT) can be set on the buy.",
        f"Look for an expiry time on the primary. Set {clock(eastern(opens, window))} ET.",
        f"At {clock(chicago(opens, window))} CT: cancel whatever has not filled.",
    )
    assert {int(found) for found in every(r"first (\d+) minutes")} == {window}
    # Every "8:30 to 9:00 AM CT (9:30 to 10:00 AM ET)" in the file is the window.
    spans = every(r"(\d{1,2}:\d{2}) to (\d{1,2}:\d{2} [AP]M) CT \((\d{1,2}:\d{2}) to (\d{1,2}:\d{2} [AP]M) ET\)")
    assert set(spans) == {(bare(chicago(opens)), clock(chicago(opens, window)),
                           bare(opens), clock(eastern(opens, window)))}
    # And every span that starts at the open, in either zone, ends at the cutoff.
    for zone in (chicago, eastern):
        ends = every(re.escape(bare(zone(opens))) + r" to (\d{1,2}:\d{2} [AP]M)")
        assert set(ends) == {clock(zone(opens, window))}, ends


def test_the_times_at_a_glance_are_the_modules_times():
    opens, close, window = timing.REGULAR_OPEN_ET, timing.REGULAR_CLOSE_ET, plan.ENTRY_WINDOW_MINUTES
    before, buffer = morning.POLICY["preopen_minutes"], sessions.COMPLETION_BUFFER_MINUTES
    rows = {
        "Morning collection may start": (opens, -before),
        "Orders ready by": (timing.PREPARE_BEFORE_ET, 0),
        "The open, and the entry window opens": (opens, 0),
        "The entry window ends: cancel unfilled buys": (opens, window),
        "The close": (close, 0),
        "The session counts as complete": (close, buffer),
        "Evening slot": (delivery.EVENING_PRIMARY_ET, 0),
        "Evening retry slot": (delivery.EVENING_RETRY_ET, 0),
    }
    table = between("## Appendix B.", "\n## ")
    stated(*(f"| {what} | {clock(chicago(moment, shift))} | {clock(eastern(moment, shift))} |"
             for what, (moment, shift) in rows.items()), text=table)


def test_the_rule_sheet_states_which_stocks_and_bars_are_read():
    stated(
        f"only if its close that session is at least ${g(universe.MIN_PRICE)}",
        f"{pipeline.LOOKBACK_DAYS} sessions back",
    )


def test_the_rule_sheet_states_the_market_lights_rules():
    reference, short, long = n(breadth.REFERENCE_UNIVERSE), breadth.RATIO_SHORT_SESSIONS, breadth.RATIO_LONG_SESSIONS
    size = breadth.SIZE_MULTIPLIER
    stated(
        f"at least {g(breadth.BURST_PCT)}% over the previous close, on at least {n(breadth.MIN_VOLUME)} shares "
        "and more than the previous session's volume",
        f"across the last {short} sessions and across the last {long} sessions",
        f"multiplied by N and divided by {reference}",
        f"the count of names down {g(breadth.BURST_PCT)}% today is at or over {n(breadth.DOWN4_ALARM)} of "
        f"{reference}, scaled",
        f"| RED | the {long}-session ratio is under {g(breadth.RED_RATIO_10D)} |",
        f"| RED | the {short}-session ratio is under {g(breadth.RED_RATIO_5D)} and more names are down",
        f"| YELLOW | the {long}-session ratio is under {g(breadth.YELLOW_RATIO_10D)} |",
        f"the count of names up {g(breadth.MONTH_BIG_MOVE_PCT)}% in a month is over {n(breadth.UP50_MONTH_HOT)} of "
        f"{reference}, scaled",
        f"full size on GREEN (multiplier {g(size['green'])}), half on YELLOW ({g(size['yellow'])}) and none on RED "
        f"({g(size['red'])})",
        f"GREEN admits bursts graded {' or '.join(pipeline.TRADE_GRADES)}. YELLOW admits "
        f"{' or '.join(pipeline.YELLOW_GRADES)} only.",
        f"A count of fewer than {n(breadth.DOWN25_QUARTER_OVERSOLD)} of {reference} names, scaled, down "
        f"{g(breadth.QUARTER_MOVE_PCT)}% in a quarter",
    )
    assert size["yellow"] == size["green"] / 2, "the sheet says half on YELLOW"
    # A second mention anywhere else in the file is the same number.
    assert set(every(r"\b(\d,\d{3})\b(?= stocks| names|, scaled| before)")) == {reference}
    assert set(every(r"(\d[\d,]*) of " + re.escape(reference))) == {
        n(breadth.DOWN4_ALARM), n(breadth.UP50_MONTH_HOT), n(breadth.DOWN25_QUARTER_OVERSOLD)}
    assert {int(found) for found in every(r"(\d+)-session ratio")} == {short, long}


def test_the_rule_sheet_states_the_two_scans():
    stated(
        f"the close is at least {g(scans.BURST_RATIO)} times the previous close, on more volume than the previous "
        f"session and at least {n(scans.MIN_VOLUME)} shares",
        f"the close is at least ${scans.DOLLAR_MOVE:.2f} over the same session's open, on more than "
        f"{n(scans.MIN_VOLUME)} shares",
    )
    assert {float(found) for found in every(r"([\d.]+) times the previous close")} == {scans.BURST_RATIO}
    assert {float(found) for found in every(r"\$([\d.]+) over the same session's open")} == {scans.DOLLAR_MOVE}


def test_the_rule_sheet_states_the_checklist_and_the_grade():
    weights, extra = quality.WEIGHTS, quality.EXTRA_CHECKS
    table = between("### 5.6 ", "\n### ")
    stated(*(f"| {letter} | {g(weights[letter])} |" for letter in quality.LETTERS), text=table)
    stated(*(f"| {check} | 0 |" for check in extra), text=table)
    checks = len(quality.LETTERS) + len(extra)
    bands = ", ".join(f"{grade} from {g(floor)}" for floor, grade in grader.GRADE_BANDS)
    stated(
        f"Every candidate gets {WORDS[checks]} checks. {WORDS[len(quality.LETTERS)].capitalize()} carry points.",
        f"the {WORDS[len(quality.LETTERS)]} weights sum to {g(sum(weights.values()))}",
        f"at most {quality.MAX_UP_RUN} day above +{g(quality.UP_DAY_PCT)}% in the run of up days",
        f"at most {quality.MAX_PRIOR_BREAKOUTS} earlier breakout since the move began",
        f"its range was under {g(quality.NARROW_RANGE_PCT)}%",
        f"a base of {quality.BASE_MIN} to {quality.BASE_MAX} sessions, at most {quality.MAX_BREAKDOWNS} breakdown day",
        f"at least the largest of the prior {quality.RE_WINDOW} sessions'",
        f"{WORDS[quality.VETO_UP_DAYS]} or more rising closes in a row",
        f"**Grade bands**: {bands}, and \"skip\" below that",
        f"at least {quality.MIN_A_PLUS_LETTERS} of the {WORDS[checks]} checks",
        f"need the letters {' and '.join(quality.GRADE_GATE_LETTERS)} passed outright, or the grade is capped at "
        f"{quality.GATE_CAP}",
    )
    assert quality.MIN_CLOSE_POS == 0.8 and "in the top fifth of the day's range" in PROMPT
    assert set(quality.VETO_NAMES) == {"up_days", "not_linear"}
    stated(*(f"`{name}`" for name in quality.VETO_NAMES))


def test_the_rule_sheet_states_the_review_cap_and_the_reader_states():
    stated(
        f"At most {pipeline.MAX_READS} chart reads a night",
        f"at most {review_selection.RESEARCH_MAX} research reads",
    )
    assert {int(found) for found in every(r"(\d+) chart reads")} == {pipeline.MAX_READS}
    assert {int(found) for found in every(r"(\d+) research reads")} == {review_selection.RESEARCH_MAX}
    stated(*(f"`{state}`" for state in reader_coverage.STATES), text=prose(between("### 6.3 ", "\n---")))
    kinds = report.PROBLEM_KINDS
    stated("The problem words are " + ", ".join(f"`{kind}`" for kind in kinds[:-1]) + f" and `{kinds[-1]}`.")


def test_the_rule_sheet_states_the_four_prices_of_a_burst_ticket():
    stated(
        f"the close plus {g(plan.ENTRY_ABOVE_PCT)}%, and the highest price that keeps the stop within "
        f"{g(plan.MAX_STOP_PCT)}% of the limit",
        f"| **Day-2 line** | The close plus {g(plan.ENTRY_ABOVE_PCT)}%.",
        f"The **skip-below line** is the close minus {g(plan.ENTRY_BELOW_PCT)}%",
        f"The **+{g(plan.SKIP_GAP_PCT)}% line** is the close plus {g(plan.SKIP_GAP_PCT)}%",
        f"An \"indicative entry\" (the close plus {g(plan.ASSUMED_SLIPPAGE_PCT)}%, capped at the limit)",
        f"**Day-2 line**: the burst close plus {g(plan.ENTRY_ABOVE_PCT)}%.",
    )
    # Every "close plus N%" and "close minus N%" in the file is one of the plan's lines.
    assert set(every(r"close plus (\d+(?:\.\d+)?)%")) == {
        g(plan.ENTRY_ABOVE_PCT), g(plan.SKIP_GAP_PCT), g(plan.ASSUMED_SLIPPAGE_PCT)}
    assert set(every(r"close minus (\d+(?:\.\d+)?)%")) == {g(plan.ENTRY_BELOW_PCT)}


def test_the_rule_sheet_states_the_sizing_rules():
    stated(
        f"risk {g(plan.DEFAULT_RISK_PCT)}% of the model equity a trade, at most {g(plan.DEFAULT_MAX_POSITION_PCT)}% "
        f"of the model equity in one name, and {plan.DEFAULT_MAX_OPEN_POSITIONS} slots",
        f"a risk band of {g(plan.RISK_PCT_BAND_LOW)}% to {g(plan.RISK_PCT_BAND_HIGH)}%",
        f"when the stop is more than {g(plan.IDEAL_STOP_PCT)}% and at most {g(plan.MAX_STOP_PCT)}% under the limit, "
        "the budget is halved",
        f"a burst day of +{g(plan.GAIN_CEILING_PCT)}% or more, or a close more than {g(plan.EXTENSION_HAZARD_PCT)}% "
        f"above its {quality.EXTENSION_SMA_SESSIONS}-session average, halves the budget once",
        f"There are {plan.DEFAULT_MAX_OPEN_POSITIONS} slots.",
        # Section 9 sizes the owner's own account by the same rule.
        f"his own equity figure times {g(plan.DEFAULT_RISK_PCT)}%",
        f"times {g(plan.STOP_RISK_MULTIPLIER)} when the stop is more than {g(plan.IDEAL_STOP_PCT)}% under the limit",
        f"times {g(plan.HAZARD_MULTIPLIER)} again if the row carries a hazard flag",
        f"never more than {g(plan.DEFAULT_MAX_POSITION_PCT)}% of his equity in one name",
    )
    assert plan.STOP_RISK_MULTIPLIER == 0.5 and plan.HAZARD_MULTIPLIER == 0.5, "the sheet says halved"
    assert {int(found) for found in every(r"(\d+) slots")} == {plan.DEFAULT_MAX_OPEN_POSITIONS}


def test_the_dated_model_account_is_the_evening_workflows():
    """The one place the prompt prints the model account's dollars: the
    workflow's own equity and risk, through the plan's multipliers."""
    workflow = (ROOT / ".github" / "workflows" / "evening.yml").read_text()
    equity = float(re.search(r"ACCOUNT_EQUITY: '(\d+)'", workflow).group(1))
    risk_pct = float(re.search(r"RISK_PCT: '([\d.]+)'", workflow).group(1))
    assert risk_pct == plan.DEFAULT_RISK_PCT
    full = equity * risk_pct / 100
    burst = full * plan.STOP_RISK_MULTIPLIER
    stated(
        f"the model account has been {usd(equity)} since the session of 4 November 2026. The full budget is "
        f"{usd(full)}. A burst ticket risks {usd(burst * breadth.SIZE_MULTIPLIER['green'])} on a GREEN night and "
        f"{usd(burst * breadth.SIZE_MULTIPLIER['yellow'])} on a YELLOW night, and half of that again with a hazard. "
        f"The position cap is {usd(equity * plan.DEFAULT_MAX_POSITION_PCT / 100)}.",
        f"The model reads them as one {usd(equity)} account.",
    )


def test_the_rule_sheet_states_the_anticipation_ticket():
    stated(
        f"\"box\" of {watchlist.BOX_MIN} to {watchlist.BOX_MAX} sessions",
        f"At most {watchlist.TOP_N} are listed.",
        f"the larger of ${plan.TRIGGER_CENTS:.2f} and {g(plan.TRIGGER_FRACTION * 100)}% of the close",
        f"**Limit**: the trigger plus {g(plan.TRIGGER_LIMIT_PCT)}%.",
        f"**Stop**: the lowest low of the last {plan.STOP_LOOKBACK_SESSIONS} sessions.",
        f"The ticket is withheld when the stop is more than {g(plan.MAX_STOP_PCT)}% under the limit.",
        f"An open more than {g(plan.GAP_OK_PCT)}% above the last close is \"gapped\"",
    )


def test_the_exit_ladder_is_the_plans_own_days_and_levels():
    half, abnormal, gap = plan.SELL_HALF_PCT, plan.ABNORMAL_DAY_PCT, plan.GAP_EXIT_PCT
    trail = f"${plan.TRAIL_CENTS:.2f} under that day's high"
    stated(
        f"| 1 | After day {plan.FINAL_EXIT_DAY} the plan is over.",
        f"The open is +{g(gap)}% or more over the fill: out at the open.",
        f"The high is +{g(half)}% or more over the fill and no half has been sold: sell half (rounded up to whole "
        f"shares) and raise the stop to {trail}.",
        f"The close is +{g(abnormal)}% or more over the fill: the ticket says take at least part profit. The model "
        f"sells nothing and only raises the stop to {trail}.",
        f"At the close of day {plan.NO_PROGRESS_DAY}, if the close is at or under the fill: out at the close.",
        f"At the close of day {plan.SELL_HALF_DAY}, if no half has been sold: sell half at the close.",
        f"At the close of day {plan.ENTRY_DAY}, the stop rises to the entry day's low if that is higher.",
        f"From the close of day {plan.TRAIL_FROM_DAY}, the stop rises to each day's low.",
        f"| 11 | At the close of day {plan.FINAL_EXIT_DAY}: out.",
        f"\"Do not move the stop to break-even before day {plan.NO_BREAKEVEN_BEFORE_DAY} just because it is green.\"",
        # Section 11 works the same levels from the owner's real fill.
        f"| Sell-half level | F times {1 + half / 100:.2f} | When the price reaches +{g(half)}% over the fill and no "
        f"half has been sold: sell half, and raise the stop to {plan.TRAIL_CENTS * 100:g} to "
        f"{plan.TRAIL_CENTS_MAX * 100:g} cents under that day's high.",
        f"| Abnormal-close level | F times {1 + abnormal / 100:.2f} | A close at or over +{g(abnormal)}%",
        f"| Gap-exit level | F times {1 + gap / 100:.2f} | An open at or over +{g(gap)}%",
        f"| Day-{plan.ENTRY_DAY} stop | the higher of S and day {plan.ENTRY_DAY}'s low | Set at the close of day "
        f"{plan.ENTRY_DAY}. |",
        f"| Day-{plan.NO_PROGRESS_DAY} test | the close of day {plan.NO_PROGRESS_DAY} against F |",
        f"| Trailing stop | the higher of the current stop and that day's low | From the close of day "
        f"{plan.TRAIL_FROM_DAY}, each day.",
        f"| Final exit | the close of day {plan.FINAL_EXIT_DAY} |",
    )
    # Every "+N%" the file prints is one of the plan's or the checklist's.
    assert set(every(r"\+(\d+(?:\.\d+)?)%")) == {
        g(half), g(abnormal), g(gap), g(plan.GAIN_CEILING_PCT), g(quality.UP_DAY_PCT)}
    assert {float(found) for found in every(r"F times ([\d.]+)")} == {
        1 + half / 100, 1 + abnormal / 100, 1 + gap / 100}


def test_the_scorecard_and_the_cash_rule_are_the_modules():
    stated(
        f"tickets picked in the last {record.SCORECARD_SESSIONS} sessions",
        f"only from {record.SCORECARD_MIN_PLANS} settled tickets",
        f"{WORDS[plan.GFV_LIMIT]} in a {WORDS[plan.GFV_WINDOW_MONTHS]}-month period restrict the account for "
        f"{plan.GFV_RESTRICTION_DAYS} days",
    )
    assert record.OPEN_PLAN_SESSIONS == plan.FINAL_EXIT_DAY == 5 and "The hold is five sessions" in PROMPT


def test_the_dated_holiday_example_is_the_exchange_calendars():
    """Section 11.1's dated example, read off the calendar the run uses."""
    early = dt.time(13, 0)
    closed = (dt.date(2026, 11, 26), dt.date(2026, 12, 25), dt.date(2027, 1, 1))
    short = (dt.date(2026, 11, 27), dt.date(2026, 12, 24))
    assert not any(sessions.is_session(day) for day in closed)
    for day in short:
        _, close, shortened = sessions.hours(day)
        assert shortened and close.astimezone(sessions.MARKET_TZ).time() == early
    entered = dt.date(2026, 11, 23)
    days = [entered] + sessions.next_sessions(entered, plan.FINAL_EXIT_DAY - 1)
    third, fifth = days[plan.SELL_HALF_DAY - 1], days[plan.FINAL_EXIT_DAY - 1]

    def named(day: dt.date) -> str:
        return f"{day:%A} {day.day} {day:%B}"

    stated(
        f"{named(closed[0])} {closed[0].year} is a market holiday.",
        f"{named(short[0])} and {named(short[1])} {short[1].year} close at {clock(chicago(early)).replace('12:00 PM', '12:00 noon')} CT "
        f"({clock(early)} ET).",
        f"{named(closed[1])} {closed[1].year} and {named(closed[2])} {closed[2].year} are holidays.",
        f"A position entered on {named(entered)} has day {plan.SELL_HALF_DAY} on {named(third)} and day "
        f"{plan.FINAL_EXIT_DAY} on {named(fifth)}.",
    )


# --------------------------------------------------------------- URLs -----
def repository() -> str:
    """The repository the page itself names (``REPO`` in ``docs/app.js``)."""
    return re.search(r"const REPO = '([^']+)';", (ROOT / "docs" / "app.js").read_text()).group(1)


def morning_endpoint() -> str:
    page = (ROOT / "docs" / "index.html").read_text()
    return re.search(r'<meta name="spicystock-morning-endpoint" content="([^"]*)">', page).group(1)


def urls(text: str) -> list[str]:
    return [found.rstrip(".,;:") for found in re.findall(r"https?://[^\s)`>\"']+", text)]


def url_problems(text: str) -> list[str]:
    """Every URL that is not the page's, the repository's, the morning
    host's or the owner's quote check."""
    page, repo, endpoint = report.PAGE_URL, repository(), morning_endpoint()
    own = (page, f"https://github.com/{repo}", f"https://raw.githubusercontent.com/{repo}/main/", OWNER_QUOTE_CHECK)
    return [url for url in urls(text) if not (url == endpoint or url.startswith(own))]


def test_every_url_is_the_repositorys_own():
    page, raw = report.PAGE_URL, f"https://raw.githubusercontent.com/{repository()}/main/"
    assert morning_endpoint().startswith("https://")
    for name, text in FILES.items():
        assert urls(text), name
        assert not url_problems(text), (name, url_problems(text))
    stated(
        f"{page}brief.md", f"{page}brief.json", f"{raw}docs/brief.md", f"{raw}docs/brief.json",
        f"{page}morning.json", morning_endpoint(), f"https://github.com/{repository()}/issues",
    )
    for text in (BOOTSTRAP_RAW, README_RAW):
        stated(f"{raw}docs/analyst/prompt.md", f"{page}brief.md", text=text)
    assert url_problems("see https://example.com/brief.md") == ["https://example.com/brief.md"]
    assert url_problems(f"see {page.replace('SpicyStock', 'spicystock')}brief.md")


def test_the_repository_files_the_prompt_names_exist():
    named = set()
    for text in FILES.values():
        named.update(re.findall(r"`((?:knowledge|src|tools|tests|docs/analyst|\.github/workflows)/[\w./-]+)`", text))
    assert {"knowledge/method.md", "knowledge/broker-fidelity.md", "tests/test_analyst_prompt.py"} <= named
    missing = sorted(path for path in named if not (ROOT / path).is_file())
    assert not missing, missing
    stated(*(f"`{path.name}`" for path in ANALYST.glob("*.md") if path.name != "README.md"), text=README_RAW)


# ------------------------------------------------------- the brief's map --
def numbered(block: str, pattern: str) -> list[str]:
    found = re.findall(pattern, block, flags=re.M)
    assert [int(number) for number, _ in found] == list(range(1, len(found) + 1)), found
    return [name for _, name in found]


def test_section_six_lists_the_briefs_sections_by_name_and_in_order():
    assert numbered(between("### 6.2 ", "\n### "), r"^(\d+)\. \*\*(.+?)\*\*") == list(SECTION_NAMES)
    assert numbered(between("## Appendix C.", None), r"^(\d+)\. (.+?)\s*$") == list(SECTION_NAMES)
    stated(f"The brief has {WORDS[len(SECTION_NAMES)]} numbered sections, in this order.")
    assert set(every(r'section "([^"]+)"')) <= set(SECTION_NAMES)


def test_the_brief_the_prompt_describes_is_the_one_the_code_writes():
    from src import brief, freshness

    assert brief.SECTIONS == SECTION_NAMES
    assert brief.SITE_URL == report.PAGE_URL and brief.REPO_URL == f"https://github.com/{repository()}"
    stated(
        brief.SITE_URL + brief.MD_FILE, brief.SITE_URL + brief.JSON_FILE,
        brief.RAW_URL + brief.MD_FILE, brief.RAW_URL + brief.JSON_FILE,
        f"The Markdown is at most {n(brief.MAX_MD_BYTES)} bytes and the JSON at most {n(brief.MAX_JSON_BYTES)} bytes",
        f"`{brief.TICKET}`", f"`{brief.RESEARCH_ONLY}`",
        f"is within {g(brief.NEAR_VOLUME_BAND * 100)}% of the previous day's",
    )
    table = between("### 4.2 ", "\n### ")
    states = re.findall(r"^\| [^|]+ \| `(\w+)` \|", table, flags=re.M)
    assert states == [*freshness.STATES, freshness.UNKNOWN]


def has(node, path: list[str]) -> bool:
    """Whether a dotted field path (``a.b[].c``) exists in a JSON value."""
    if not path:
        return True
    if isinstance(node, list):
        return any(has(item, path) for item in node)
    name = path[0].removesuffix("[]")
    return isinstance(node, dict) and name in node and has(node[name], path[1:])


def test_every_brief_field_the_prompt_names_is_in_the_brief_the_code_writes():
    """Against the golden brief the generator holds to ``src/brief.py``. The
    model record is computed only inside an evening run, so the golden brief
    carries none: its fields are held to the keys the module writes. Section
    4.4 names the morning receipt's fields, which the test above holds."""
    import inspect
    import json

    from src import brief, model_record

    golden = json.loads((ROOT / "tests" / "fixtures" / "brief" / brief.JSON_FILE).read_text())
    assert golden["schema"] == brief.SCHEMA and golden["status"] == "derived"
    about_the_brief = PROMPT_RAW.replace(between("### 4.4 ", "\n### "), "")
    named = {token for token in re.findall(r"`([a-z_]+(?:\[\])?(?:\.[a-z_0-9]+(?:\[\])?)*)`", about_the_brief)
             if token.split(".")[0].removesuffix("[]") in golden}
    assert len(named) > 30 and {"identity.canonical.sha256", "service.expected", "tickets[].order_entry"} <= named
    written = inspect.getsource(model_record)
    missing = sorted(
        path for path in named
        if not has(golden, path.split("."))
        and not (path.startswith("model_record.") and f'"{path.split(".", 1)[1]}":' in written))
    assert not missing, missing
    # The bare names the prompt quotes beside a section it has just named.
    instants = set(re.findall(r"^\| (?:before|at or after) `(\w+)` \|", between("### 4.2 ", "\n### "), flags=re.M))
    assert len(instants) == len(freshness_instants()) and instants <= set(golden["service"]["expected"])
    stated("`identity.entry_window.opens_at` and `cutoff_at`", "(`would_pass`)", "`green_needs`",
           "`digest_without_membership`", "(`order_entry.price_states`)", "`candidates.schedule_days`")
    assert {"opens_at", "cutoff_at"} <= set(golden["identity"]["entry_window"])
    assert "would_pass" in golden["candidates"]["detailed"][0] and "green_needs" in golden["market"]
    assert "digest_without_membership" in golden["rules"] and "schedule_days" in golden["candidates"]
    assert golden["tickets"]
    for ticket in golden["tickets"]:
        states = [row["state"] for row in ticket["order_entry"]["price_states"]]
        assert set(states) | {"unknown"} == set(morning.PRICE_STATES)
        stated(f"the order-entry block with the {WORDS[len(states)]} price states and their boundaries")
    stated(*(f"`{word}`" for word in golden["events"]["status_words"]),
           text=prose(between("### 6.2 ", "\n### ")))


def freshness_instants() -> tuple[str, ...]:
    """The four instants section 4.2 compares the clock with, in order."""
    return ("completion_at", "primary_slot_at", "retry_slot_at", "recovery_until")


def test_the_morning_receipt_the_prompt_describes_is_the_collectors():
    """Sections 3.3, 4.4 and 10.3 name the receipt's fields and words: each
    is in a receipt the collector wrote, or in its own list of states."""
    import json

    receipt = json.loads((ROOT / "tests" / "fixtures" / "morning" / "observed.json").read_text())
    row = receipt["rows"][0]
    assert isinstance(receipt["publication"]["data_sha256"], str)
    assert {"generated_at", "expires_at"} <= set(receipt)
    assert {"status"} <= set(row["trade"]) and {"status"} <= set(row["quote"])
    assert set(row["price_checks"].values()) <= set(morning.PRICE_STATES)
    assert row["events"]["halt"]["status"] == "not_listed"
    check = prose(between("### 4.4 ", "\n### "))
    stated("`publication.data_sha256`", "`generated_at`", "`expires_at`", "`trade.status`", "`quote.status`",
           "`price_checks`", "`events.halt`", "`not_listed`", "`recent`", "`stale`", text=check)
    seconds = morning.POLICY["snapshot_max_age_seconds"]
    assert seconds % 60 == 0
    stated(f"A receipt is good for about {WORDS[seconds // 60]} minutes.", text=check)
    states = prose(between("## 10. ", "\n## 11. "))
    stated(*(f"`{state}`" for state in morning.PRICE_STATES), text=states)
    quoted = set(re.findall(r"`((?:below|above|within)_[a-z0-9_]+)`", PROMPT))
    assert quoted == set(morning.PRICE_STATES) - {"unknown"}, quoted ^ set(morning.PRICE_STATES)


# ---------------------------------------------------------- the shape -----
def test_the_prompt_has_its_seventeen_parts_in_order():
    headings = re.findall(r"^## (\d+)\. (.+)$", PROMPT_RAW, flags=re.M)
    assert [int(number) for number, _ in headings] == list(range(1, len(PARTS) + 1))
    for (_, title), part in zip(headings, PARTS):
        assert part.lower() in title.lower(), (title, part)
    gaps = re.findall(r"^### 2\.(\d+) (.+)$", PROMPT_RAW, flags=re.M)
    assert [int(number) for number, _ in gaps] == list(range(1, len(gaps) + 1))
    stated(f"An outside audit listed {WORDS[len(gaps)]} gaps.")
    assert len(gaps) == 11
    assert "no demonstrated edge" in gaps[0][1] and "placed at Fidelity as written" in gaps[1][1]
    assert re.findall(r"^## Appendix ([A-Z])\.", PROMPT_RAW, flags=re.M) == ["A", "B", "C"]


def test_every_section_the_prompt_points_at_exists():
    headings = {number for number, _ in re.findall(r"^## (\d+)\. (.+)$", PROMPT_RAW, flags=re.M)}
    headings.update(re.findall(r"^### (\d+\.\d+) ", PROMPT_RAW, flags=re.M))
    pointed = set()
    for mention in every(r"[Ss]ections? ((?:\d+(?:\.\d+)?)(?:(?:, | and | or | to )\d+(?:\.\d+)?)*)"):
        pointed.update(re.findall(r"\d+(?:\.\d+)?", mention))
    assert len(pointed) > 20 and pointed <= headings, sorted(pointed - headings)


def test_the_bootstrap_note_fits_its_bound():
    assert len(BOOTSTRAP_RAW) < BOOTSTRAP_MAX_CHARS, len(BOOTSTRAP_RAW)
    assert f"under {n(BOOTSTRAP_MAX_CHARS)} characters" in prose(README_RAW)


def test_the_files_keep_the_house_style():
    for name, text in FILES.items():
        assert "\u2014" not in text, f"{name} has an em dash"
        assert not re.search(r"\.(?:py|js|mjs|yml):\d+", text), f"{name} cites a line number"
        # Written for any bot: none is named, so nothing is assumed of one.
        assert not re.search(r"\b(?:Grok|Muse|ChatGPT|Claude|Gemini|Copilot)\b", text), f"{name} names a bot"
        assert not wrapped_into_a_list(text), (name, wrapped_into_a_list(text))


def wrapped_into_a_list(text: str) -> list[str]:
    """Lines a paragraph was wrapped onto that Markdown would read as a new
    list item or heading (a sum wrapped before its minus sign, say)."""
    found, fenced, before = [], False, ""
    for line in text.split("\n"):
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced:
            inside_a_paragraph = bool(before.strip()) and not before.startswith(("- ", "|", "#", "  ")) \
                and not re.match(r"(?:\d+|[a-g])\. ", before)
            if inside_a_paragraph and re.match(r"(?:- |\+ |\* |\d+\. |# )", line):
                found.append(line)
        before = line
    return found


# ------------------------------------------------------------ privacy -----
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
#: A brokerage account number: a run of eight or more digits, with or
#: without one leading letter, or the dashed three-and-six form.
ACCOUNT_NUMBER = re.compile(r"\b[A-Za-z]?\d{8,}\b|\b\d{3}-\d{6}\b")
DOLLARS = re.compile(r"\$(\d[\d,]*(?:\.\d+)?)")
BALANCE_WORDS = re.compile(r"balance|settled cash|cash available|available to trade|buying power|account value",
                           re.I)
OWNER_NAMES = re.compile(r"\b(?:Mo|Tahir)\b")


def model_dollars() -> set[float]:
    """Every dollar figure the files may print outside a labelled synthetic
    example: a constant's, or the model account's (the plan's default, the
    page's dated references and the evening workflow's, with the budgets and
    the cap that follow from them)."""
    desk = (ROOT / "docs" / "app-morning.js").read_text()
    workflow = (ROOT / ".github" / "workflows" / "evening.yml").read_text()
    accounts = {plan.DEFAULT_EQUITY, float(re.search(r"ACCOUNT_EQUITY: '(\d+)'", workflow).group(1))}
    accounts.update(float(found) for found in re.findall(r"since: (?:null|'[\d-]+'), equity: (\d+)", desk))
    assert len(accounts) >= 3, accounts
    current = max(accounts)
    full = current * plan.DEFAULT_RISK_PCT / 100
    burst = full * plan.STOP_RISK_MULTIPLIER
    return accounts | {
        plan.TRIGGER_CENTS, plan.TRAIL_CENTS, plan.TRAIL_CENTS_MAX, scans.DOLLAR_MOVE, universe.MIN_PRICE,
        full, burst * breadth.SIZE_MULTIPLIER["green"], burst * breadth.SIZE_MULTIPLIER["yellow"],
        current * plan.DEFAULT_MAX_POSITION_PCT / 100,
    }


def synthetic(block: str) -> bool:
    return "synthetic" in block.lower()


def privacy_problems(text: str) -> list[str]:
    problems = [f"email address: {found}" for found in EMAIL.findall(text)]
    problems += [f"account number pattern: {found}" for found in ACCOUNT_NUMBER.findall(text)]
    problems += [f"the owner's name: {found}" for found in OWNER_NAMES.findall(text)]
    allowed = model_dollars()
    for block in paragraphs(text):
        if synthetic(block):
            continue
        for sentence in sentences(block):
            amounts = [float(found.replace(",", "")) for found in DOLLARS.findall(sentence)]
            if amounts and BALANCE_WORDS.search(sentence):
                problems.append(f"a dollar balance outside a labelled synthetic example: {sentence}")
            problems += [f"a dollar figure that is no constant's and not the model's: ${amount:g} in: {sentence}"
                         for amount in amounts if amount not in allowed]
    return problems


def test_the_public_files_carry_nothing_private():
    for name, text in FILES.items():
        assert not privacy_problems(text), (name, privacy_problems(text))
    # The example the rule exists for is in the file, and is labelled.
    labelled = [block for block in paragraphs(PROMPT_RAW) if synthetic(block) and DOLLARS.search(block)]
    assert labelled and all("SYNTHETIC" in block for block in labelled)


def test_the_privacy_check_names_what_it_refuses():
    assert privacy_problems("Write to the owner at owner@example.com about it.")
    assert privacy_problems("The account is Z12345678 at the broker.")
    assert privacy_problems("The account is 123-456789 at the broker.")
    assert privacy_problems("His settled cash is $12,345.67 this morning.")
    assert privacy_problems("He bought 40 shares for $4,321.00 on Monday.")
    assert privacy_problems(f"Settled cash of {usd(max(model_dollars()))} is in the account.")
    assert privacy_problems("Mo decides and places every order.")
    assert not privacy_problems("Worked example, SYNTHETIC: settled cash of $12,345.67 in an account labelled Roth.")
    assert not privacy_problems(f"The model account has been {usd(max(model_dollars()))} since November.")
    assert not privacy_problems("Ask for settled cash before every buy. The session of 2026-11-04 was the first.")


# ============================================ the rule sheet, by execution ==
# Every hold below is a function of the prompt's text that returns what it
# finds wrong, so the same hold can be run over an edited copy: the last test
# makes each edit a reviewer showed the file once survived and requires the
# hold that names the rule, and no other, to report it.
PAGE_FIXTURES = ROOT / "tests" / "fixtures" / "page"


def lacking(text: str, *phrases: str) -> list[str]:
    """The sentences a text does not carry, its line wraps collapsed."""
    flat = prose(text)
    return [f"not stated: {phrase}" for phrase in phrases if phrase not in flat]


def cents(low: float, high: float) -> list[float]:
    """Every price from low to high, a cent apart."""
    return [number / 100 for number in range(round(low * 100), round(high * 100) + 1)]


def ordered(decided) -> set[tuple[str, str]]:
    """Every (earlier, later) pair a set of decisions settles, one decision following from two others included."""
    before = set(decided)
    while True:
        more = {(a, d) for a, b in before for c, d in before if b == c} - before
        if not more:
            assert not any(a == b for a, b in before), "the decisions contradict each other"
            return before
        before |= more


# ------------------------------------------------- 5.15: the exit ladder ---
FILL, STOP_AT, HELD = 100.0, 96.0, 10
#: Days 1 and 2 of a walk on which nothing happens but the day-1 stop raise
#: (to 99.50), a day 3 that only sells its half at the close and trails, and
#: a day 4 that only trails. (open, high, low, close)
QUIET_DAYS = ((100.0, 101.0, 99.5, 100.5), (100.5, 102.0, 100.0, 101.0))
HALF_AT_CLOSE, TRAILED = (101.0, 103.0, 100.5, 102.0), (102.0, 104.0, 101.5, 103.0)
#: Two steps of the ladder and the sessions that set them against each other:
#: on the LAST session the condition of each is met (`step_is_due()` checks
#: it), so which one `plan.follow()` books first is the walk's own order and
#: no third rule's. The order of each pair here means nothing; it is derived.
LADDER_CASES = (
    ("expired", "stopped_at_open", (*QUIET_DAYS, HALF_AT_CLOSE, TRAILED, (103.0, 105.0, 102.5, 104.0),
                                    (95.0, 96.0, 94.0, 95.5))),
    # day 1 runs +30%: the half is sold and the stop is 25 cents under 130. Day 2 opens over the
    # +20% gap level and under that stop.
    ("stopped_at_open", "gap_exit", ((100.0, 130.0, 99.5, 128.0), (125.0, 126.0, 124.0, 125.5))),
    ("gap_exit", "stopped", ((121.0, 122.0, 95.0, 121.5),)),
    ("stopped", "sell_half_at_level", ((100.0, 109.0, 95.5, 100.0),)),
    ("sell_half_at_level", "abnormal_day", ((100.0, 112.0, 99.5, 111.0),)),
    # a narrow day over +10%: its low is over "the high minus 25 cents", so the stop can still rise to it
    ("abnormal_day", "stop_raised_to_entry_low", ((111.0, 111.1, 110.95, 111.05),)),
    ("abnormal_day", "stop_trailed", (*QUIET_DAYS, (111.0, 111.1, 110.95, 111.05))),
    ("abnormal_day", "day5_exit", (*QUIET_DAYS, HALF_AT_CLOSE, TRAILED, (104.0, 112.0, 103.0, 111.0))),
    ("sell_half_at_level", "no_progress", (*QUIET_DAYS, (100.5, 108.5, 99.6, 99.8))),
    ("sell_half_at_level", "sell_half_at_close", (*QUIET_DAYS, (101.0, 108.5, 100.5, 105.0))),
    ("no_progress", "sell_half_at_close", (*QUIET_DAYS, (100.5, 101.0, 99.6, 99.9))),
    ("no_progress", "stop_trailed", (*QUIET_DAYS, (100.5, 101.0, 99.6, 99.9))),
    ("sell_half_at_close", "stop_trailed", (*QUIET_DAYS, HALF_AT_CLOSE)),
    ("stop_trailed", "day5_exit", (*QUIET_DAYS, HALF_AT_CLOSE, TRAILED, (103.0, 105.0, 102.5, 104.0))),
)


def ladder_words() -> dict[str, str]:
    """Everything plan.follow() can book on one session, each by the words its
    row of the 5.15 table starts with."""
    return {
        "expired": f"After day {plan.FINAL_EXIT_DAY} the plan is over.",
        "stopped_at_open": "The open is at or under the stop:",
        "gap_exit": f"The open is +{g(plan.GAP_EXIT_PCT)}% or more over the fill:",
        "stopped": "The low is at or under the stop:",
        "sell_half_at_level": f"The high is +{g(plan.SELL_HALF_PCT)}% or more over the fill and no half has been sold:",
        "abnormal_day": f"The close is +{g(plan.ABNORMAL_DAY_PCT)}% or more over the fill:",
        "no_progress": f"At the close of day {plan.NO_PROGRESS_DAY}, if the close is at or under the fill:",
        "sell_half_at_close": f"At the close of day {plan.SELL_HALF_DAY}, if no half has been sold:",
        "stop_raised_to_entry_low": f"At the close of day {plan.ENTRY_DAY}, the stop rises",
        "stop_trailed": f"From the close of day {plan.TRAIL_FROM_DAY}, the stop rises",
        "day5_exit": f"At the close of day {plan.FINAL_EXIT_DAY}: out.",
    }


def walk(days, shares: int = HELD) -> dict:
    """plan.follow() from a fill at 100 with the stop at 96, over hand-built sessions."""
    pick = {"ticker": "AAA", "date": "2026-09-01", "kind": "burst", "entry_ref": FILL, "stop": STOP_AT,
            "shares": shares}
    return plan.follow(pick, [{"date": f"day {number}", "o": o, "h": h, "l": low, "c": c}
                              for number, (o, h, low, c) in enumerate(days, 1)])


def step_is_due(step: str, days) -> bool:
    """Whether a step's condition, as its row of the table states it, is met
    on the last of these sessions, against the stop and the half sale the walk
    carried INTO that session."""
    before, level = walk(days[:-1]), plan.exit_levels(FILL)
    day, (o, h, low, c) = len(days), days[-1]
    stop, sold = before["current_stop"], before["half_sold"]
    return {
        "expired": day > plan.FINAL_EXIT_DAY,
        "stopped_at_open": o <= stop,
        "gap_exit": o >= level["gap_exit"],
        "stopped": low <= stop,
        "sell_half_at_level": h >= level["sell_half"] and not sold,
        "abnormal_day": c >= level["abnormal"],
        "no_progress": day == plan.NO_PROGRESS_DAY and c <= FILL,
        "sell_half_at_close": day == plan.SELL_HALF_DAY and not sold,
        "stop_raised_to_entry_low": day == plan.ENTRY_DAY and low > stop,
        "stop_trailed": day >= plan.TRAIL_FROM_DAY and low > stop,
        "day5_exit": day == plan.FINAL_EXIT_DAY,
    }[step]


def booked(days) -> list[str]:
    """What the walk did on the LAST of these sessions, in the order it did
    it: its events there by name, a half sale told apart by its price (the
    level's, or that day's close), and `expired` for a session it booked
    nothing on because the plan was over."""
    result, close = walk(days), days[-1][3]
    assert close != max(days[-1][0], plan.exit_levels(FILL)["sell_half"]), "a half at the level would read as one at the close"
    steps = [("sell_half_at_close" if event["price"] == close else "sell_half_at_level")
             if event["event"] == "sell_half" else event["event"]
             for event in result["events"] if event["day"] == len(days)]
    return steps or (["expired"] if result["status"] == "expired" else [])


@functools.lru_cache(maxsize=None)
def ladder_decisions() -> tuple[tuple[str, str], ...]:
    """(first, second) for every pair of steps a session can set against each
    other: the one the walk applied first, and the one it applied after it or,
    the position being over by then, never."""
    decided = []
    for a, b, days in LADDER_CASES:
        assert {a, b} <= set(ladder_words()) and step_is_due(a, days) and step_is_due(b, days), (a, b)
        applied = [step for step in booked(days) if step in (a, b)]
        assert applied and len(applied) == len(set(applied)), (a, b, booked(days))
        decided.append((applied[0], b if applied[0] == a else a))
    return tuple(decided)


def ladder_table(text: str) -> dict[str, int]:
    """The place of each step in the table of section 5.15: its rows numbered
    from 1 with no gap, every row one step of the walk and every step one row."""
    rows = re.findall(r"^\| (\d+) \| (.+) \| [A-Z] \|$", between("### 5.15 ", "\n### ", text), flags=re.M)
    assert [int(number) for number, _ in rows] == list(range(1, len(rows) + 1)), "the table's rows are not numbered 1, 2, 3"
    words, order = ladder_words(), {}
    for number, step in rows:
        named = [key for key, start in words.items() if step.startswith(start)]
        assert len(named) == 1 and named[0] not in order, f"row {number} is not one step of the walk: {step}"
        order[named[0]] = int(number)
    assert set(order) == set(words), f"no row for {sorted(set(words) - set(order))}"
    return order


def ladder_list(text: str) -> dict[str, tuple[int, int]]:
    """Section 11.3 gives the same order as a list: each step's item, and its
    place inside the item (the last item names four rules of the close in one
    sentence). Steps the list names together share a place."""
    items = re.findall(r"^(\d+)\. (.+?)(?=^\d+\. |\Z)", between("### 11.3 ", "\n### ", text), flags=re.M | re.S)
    assert [int(number) for number, _ in items] == list(range(1, len(items) + 1)), "the list is not numbered 1, 2, 3"
    assert plan.NO_PROGRESS_DAY == plan.SELL_HALF_DAY, "the list says 'the day-3 rules' of both"
    raises = f"the stop raises of day {plan.ENTRY_DAY} and of day {plan.TRAIL_FROM_DAY} onward"
    words = {
        "stopped_at_open": "The open is at or under the stop:",
        "gap_exit": "The open is at or over the gap-exit level:",
        "stopped": "The price falls to the stop:",
        "sell_half_at_level": "The price reaches the sell-half level:",
        "abnormal_day": "the abnormal-close rule",
        "no_progress": f"the day-{plan.NO_PROGRESS_DAY} rules", "sell_half_at_close": f"the day-{plan.SELL_HALF_DAY} rules",
        "stop_raised_to_entry_low": raises, "stop_trailed": raises,
        "day5_exit": f"the day-{plan.FINAL_EXIT_DAY} exit",
    }
    place = {}
    for step, phrase in words.items():
        found = [(int(number), prose(item).index(phrase)) for number, item in items if phrase in prose(item)]
        assert len(found) == 1, f"the list names {phrase!r} {len(found)} times"
        place[step] = found[0]
    return place


def ladder_problems(text: str = PROMPT_RAW) -> list[str]:
    try:
        table, listed = ladder_table(text), ladder_list(text)
    except AssertionError as exc:
        return [f"the exit ladder cannot be read: {exc}"]
    problems = []
    for first, second in ladder_decisions():
        if table[first] > table[second]:
            problems.append(f"5.15 lists step {table[second]} ({second}) before step {table[first]} ({first}); "
                            f"the walk applies {first} first")
        if first in listed and second in listed and listed[first] > listed[second]:
            problems.append(f"11.3 puts {second} before {first}; the walk applies {first} first")
    return problems


def test_the_exit_ladder_is_listed_in_the_order_the_walk_applies_it():
    """Fourteen sessions on which two steps are both due, each walked through
    plan.follow(): the step it books first must be the earlier row of 5.15,
    and the earlier item of 11.3's list.

    Of the 55 pairs of steps the decisions settle 49. The six they leave are
    pairs no session can set against each other, so the walk has no order
    between them for this test to read and the table may list them either
    way: the +10% close against either day-3 rule (a close is not both +10%
    and at or under the fill, and a +10% day has sold its half at the +8%
    level before the close), and the day-1 stop raise against each rule of
    day 3 and day 5 (another day). Three of the six are neighbours in the
    table as it stands: rows 6 and 7, 8 and 9, 9 and 10."""
    assert not ladder_problems(), ladder_problems()
    decided, steps = ordered(ladder_decisions()), sorted(ladder_words())
    assert len(set(ladder_decisions())) == len(LADDER_CASES)
    unsettled = {frozenset(pair) for pair in itertools.combinations(steps, 2)
                 if pair not in decided and pair[::-1] not in decided}
    first_day_raise = "stop_raised_to_entry_low"
    assert unsettled == {frozenset(pair) for pair in (
        ("abnormal_day", "no_progress"), ("abnormal_day", "sell_half_at_close"),
        (first_day_raise, "no_progress"), (first_day_raise, "sell_half_at_close"),
        (first_day_raise, "stop_trailed"), (first_day_raise, "day5_exit"))}
    # why those six are never due together, each from the plan's own numbers
    assert plan.exit_levels(FILL)["abnormal"] > FILL and plan.ABNORMAL_DAY_PCT >= plan.SELL_HALF_PCT
    assert plan.ENTRY_DAY < min(plan.NO_PROGRESS_DAY, plan.SELL_HALF_DAY, plan.TRAIL_FROM_DAY, plan.FINAL_EXIT_DAY)
    # what two of the rows add in words is what the walk did
    gap_down = walk(((95.0, 95.5, 94.0, 95.2),))
    assert gap_down["status"] == "stopped" and gap_down["exit_price"] == 95.0 < STOP_AT
    assert not lacking(PROMPT_RAW, "out at that open, which can be well under the stop.")
    both = walk(((100.0, 109.0, 95.5, 100.0),))
    assert both["exit_price"] == STOP_AT and not both["half_sold"]
    assert not lacking(PROMPT_RAW, "out at the stop price. The stop wins even if the same day's high reached a sale level.",
                       "In the model the stop wins even if the same day also reached the sell-half level")


# ------------------------------------------------- 11.2: the half ----------
def half_problems(text: str = PROMPT_RAW) -> list[str]:
    """The half plan.follow() sells at the +8% level, at 1, 2, 3 and 5 shares,
    against the two ways of rounding the table could name."""
    sizes, sold = (1, 2, 3, 5), {}
    for size in sizes:
        result = walk(((100.0, 109.0, 99.5, 105.0),), shares=size)     # day 1: the high reaches +8% and nothing else
        (sale,) = [event for event in result["events"] if event["event"] == "sell_half"]
        assert sale["shares"] + sale["remaining"] == size
        sold[size] = sale["shares"]
    inner = [word for word, part in (("down", lambda n: n // 2), ("up", lambda n: -(-n // 2)))
             if all(n - part(n) == sold[n] for n in sizes)]
    outer = [word for word, part in (("down", lambda n: n // 2), ("up", lambda n: -(-n // 2)))
             if all(part(n) == sold[n] for n in sizes)]
    assert len(inner) == 1 and len(outer) == 1, sold
    whole = "With 1 share, \"half\" is the whole position." if sold[1] == 1 else "With 1 share, no half is sold."
    return lacking(
        text,
        f"| The half | N minus (N divided by 2, rounded {inner[0]}) | Half rounded {outer[0]} to a whole share. {whole} |",
        f"sell half (rounded {outer[0]} to whole shares)")


def test_the_half_is_the_walks_own_at_one_two_three_and_five_shares():
    assert not half_problems(), half_problems()
    assert [walk(((100.0, 109.0, 99.5, 105.0),), shares=n)["sold"] for n in (1, 2, 3, 5)] == [1, 1, 2, 3]
    assert walk(((100.0, 109.0, 99.5, 105.0),), shares=1)["status"] == "exit"       # nothing is left to trail


# ------------------------------------------------- 5.9: the gates ----------
#: The gates of section 5.9, each by the words its line starts with.
GATE_WORDS = {
    "grade": "Its final grade is in the band the light admits.",
    "veto": "It has no veto.",
    "route": "It is admitted.",
    "review": "Its chart review was accepted.",
    "ticket_rule": "The ticket rule can write a ticket",
    "event": "The event registry does not block it",
    "allocation": "The allocation has a free slot and the cash",
}
#: The four gates the funnel names by its own group of stages.
FUNNEL_GATES = ("grade", "veto", "route", "review")
BAND = tuple(pipeline.TRADE_GRADES)


def candidate_row(*failing: str) -> dict:
    """A reaction candidate as the funnel reads one: in the band, no veto,
    admitted, its review accepted, its plan a ticket -- except at the gates
    named."""
    assert set(failing) <= set(FUNNEL_GATES), failing
    grade = next(grade for grade in grader.GRADES if grade not in BAND) if "grade" in failing else BAND[0]
    row = {
        "ticker": "AAA", "scan": admission.DOLLAR_ROUTE if "route" in failing else admission.BURST_ROUTES[0],
        "grade_mechanical": grade, "grade": grade,
        "vetoes": [sorted(quality.VETO_NAMES)[0]] if "veto" in failing else [],
        "quality": {"checks": [{"letter": letter, "passed": "route" not in failing}
                               for letter, _ in admission.DOLLAR_CHECKS]},
        "review_selection": {"selected": True, "blockers": []},
        "claude": ({"source": grader.SOURCE_FALLBACK, "grade": grade, "error": "RuntimeError: scripted"}
                   if "review" in failing else {"source": grader.SOURCE_CLAUDE, "grade": grade, "error": None}),
        "plan": {"kind": "burst", "eligible": True, "action": plan.ORDER_ACTIONS[0],
                 "allocation": {"admitted": True, "reason": None}},
    }
    row["admission"] = admission.block(row)
    return row


def funnel_gate(row: dict, band=BAND) -> str:
    """The gate the funnel says a row stopped at (the group of its terminal stage)."""
    return funnel.GROUPS[funnel.reaction_stage(row, band, {}, [])]


def planner_asks(*, reviewed: bool) -> list[str]:
    """The later gates in the order pipeline._make_plans() asks them of the
    `full` fixture night's ticket: the ticket rule (plan.burst_plan), the
    event registry (event_risk.apply), the allocation (plan.cash_budget)."""
    data = json.loads((PAGE_FIXTURES / "full.json").read_text())
    row = copy.deepcopy(next(burst for burst in data["bursts"] if burst["ticker"] in data["trades"]))
    assert reader_coverage.accepted(row) and admission.admitted(row) and not row["vetoes"] and row["grade"] in BAND
    if not reviewed:
        row["claude"] = {**row["claude"], "source": grader.SOURCE_FALLBACK, "error": "RuntimeError: scripted"}
    asked = []

    def recording(name, function):
        def asks(*args, **kwargs):
            asked.append(name)
            return function(*args, **kwargs)
        return asks
    session = dt.date.fromisoformat(data["run"]["session"])
    with mock.patch.object(plan, "burst_plan", recording("ticket_rule", plan.burst_plan)), \
            mock.patch.object(event_risk, "apply", recording("event", event_risk.apply)), \
            mock.patch.object(plan, "cash_budget", recording("allocation", plan.cash_budget)):
        pipeline._make_plans([row], plan.Account(), data["breadth"]["regime"], 0, session, require_reader=True)
    return asked


@functools.lru_cache(maxsize=None)
def gate_decisions() -> tuple[tuple[str, str], ...]:
    """(first, second) for the gates, read two ways. The first four off the
    funnel: a row that fails exactly two of them is named for one, and that
    one is asked first. The last three, and the review against them, off the
    planner itself: the order it calls them in, and whether it calls the
    ticket rule at all for a row whose review was not accepted. (The funnel
    cannot order the last three: it names a plan the ticket rule withheld AND
    the registry blocks `event`, though the planner asks the ticket rule
    first; this hold reads the planner.)"""
    assert funnel_gate(candidate_row()) == "ticket"
    assert [funnel_gate(candidate_row(gate)) for gate in FUNNEL_GATES] == list(FUNNEL_GATES)
    decided = []
    for a, b in itertools.combinations(FUNNEL_GATES, 2):
        named = funnel_gate(candidate_row(a, b))
        assert named in (a, b), (a, b, named)
        decided.append((named, b if named == a else a))
    asked = planner_asks(reviewed=True)
    assert sorted(asked) == ["allocation", "event", "ticket_rule"], asked
    decided += list(itertools.combinations(asked, 2))
    unreviewed = planner_asks(reviewed=False)
    decided += [(("review", later) if later not in unreviewed else (later, "review")) for later in ("ticket_rule", "event")]
    return tuple(decided)


def gate_list(text: str) -> dict[str, int]:
    gates = numbered(between("### 5.9 ", "\n### ", text), r"^(\d+)\. (.+)$")
    order = {}
    for number, gate in enumerate(gates, 1):
        named = [key for key, start in GATE_WORDS.items() if gate.startswith(start)]
        assert len(named) == 1 and named[0] not in order, f"gate {number} is not one of the run's: {gate}"
        order[named[0]] = number
    assert set(order) == set(GATE_WORDS), f"no gate for {sorted(set(GATE_WORDS) - set(order))}"
    return order


def gate_problems(text: str = PROMPT_RAW) -> list[str]:
    from src import brief

    try:
        order = gate_list(text)
    except AssertionError as exc:
        return [f"the gates of 5.9 cannot be read: {exc}"]
    problems = [f"5.9 lists gate {order[second]} ({second}) before gate {order[first]} ({first}); the run asks "
                f"{first} first" for first, second in gate_decisions() if order[first] > order[second]]
    # a RED night admits no grade: the one gate that reads the light stops every row, whatever else it fails
    red = reader_coverage.admitted("red", pipeline.TRADE_GRADES, pipeline.YELLOW_GRADES)
    assert red == () and funnel.reaction_stage(candidate_row("veto", "route", "review"), red, {}, []) == "market"
    problems += lacking(text, f"On a RED night every candidate stops at gate {order['grade']}.")
    # the brief's would_pass block re-derives the gates between the light and the ticket rule
    again = {"no_veto": "veto", "admission": "route", "reader_accepted": "review"}
    assert set(again) <= set(brief.would_pass(candidate_row(), list(BAND), list(pipeline.YELLOW_GRADES), admission))
    numbers = sorted(order[gate] for gate in again.values())
    if numbers != list(range(numbers[0], numbers[0] + len(numbers))):
        problems.append(f"the gates the brief works out again are not neighbours in 5.9: {numbers}")
    return problems + lacking(text, f"The brief works out gates {numbers[0]} to {numbers[-1]} again for each row "
                                    "(`would_pass`)")


def test_the_gates_of_a_burst_are_listed_in_the_order_the_run_asks_them():
    assert not gate_problems(), gate_problems()
    assert planner_asks(reviewed=True) == ["ticket_rule", "event", "allocation"]
    assert "ticket_rule" not in planner_asks(reviewed=False), "an unreviewed burst never reaches the ticket rule"
    # the decisions leave no two of the seven gates unordered
    gates = len(GATE_WORDS)
    assert len(ordered(gate_decisions())) == gates * (gates - 1) // 2


# ------------------------------------------------- 5.14: the fill ----------
#: A burst ticket whose five lines are five prices two dollars apart.
TICKET_LINES = {"stop": 96.0, "skip-below line": 98.0, "trigger": 100.0, "limit": 102.0, "day-2 line": 104.0}
SIGNALLED, ENTERED = "2026-09-01", "2026-09-02"


def burst_ticket() -> dict:
    lines = TICKET_LINES
    return {"ticker": "AAA", "date": SIGNALLED, "kind": "burst", "entry_ref": lines["trigger"],
            "entry_low": lines["skip-below line"], "entry_high": lines["limit"],
            "day2_spent_above": lines["day-2 line"], "stop": lines["stop"], "shares": 10}


def line_at(price: float) -> str:
    """The one line of the ticket that sits at a price."""
    named = [name for name, value in TICKET_LINES.items() if value == price]
    assert len(named) == 1, f"{price} is none of the ticket's lines"
    return named[0]


def first_day(o: float, h: float | None = None, low: float | None = None, c: float | None = None) -> dict:
    """The entry session's daily bar; a price left out is the open."""
    return {"date": ENTERED, "o": o, "h": o if h is None else h, "l": o if low is None else low,
            "c": o if c is None else c}


def minutes_of(*rows) -> dict:
    """The entry session's retained minute object from (offset, o, h, l, c) rows, built as a run builds one."""
    pick = burst_ticket()
    opens, _, _ = sessions.hours(intraday.entry_session(pick))
    return intraday.build(pick, [(opens + dt.timedelta(minutes=offset), o, h, low, c) for offset, o, h, low, c in rows])


@functools.lru_cache(maxsize=None)
def fill_readings() -> dict:
    """Which line of the ticket each fill rule turns on, read off
    record.fill(), record.replay() and intraday.resolve() by moving one price
    a cent at a time across all five lines."""
    pick, lines = burst_ticket(), TICKET_LINES
    floor, top = min(lines.values()) - 1, max(lines.values()) + 1
    # a first day that prints only its open: which opens fill, and at what price
    opens = {o: record.fill(pick, first_day(o)) for o in cents(floor, top)}
    filled = [o for o, (status, *_) in opens.items() if status == "filled"]
    assert filled == cents(filled[0], filled[-1]) and all(opens[o][1] == o for o in filled), "one band, each at its open"
    assert all(opens[o][0] == record.NOT_FILLED for o in opens if o not in filled)
    # an open under the band: how high the day must go before it stops being "not filled"
    under = round(filled[0] - 0.5, 2)
    reach = next(h for h in cents(under, top) if record.fill(pick, first_day(under, h=h))[0] != record.NOT_FILLED)
    # an open over the band and under the day-2 line: how far back it must trade before it stops being "not filled"
    over = round(filled[-1] + 0.5, 2)
    assert over < lines["day-2 line"]
    back = next(low for low in reversed(cents(floor, over))
                if record.fill(pick, first_day(over, low=low))[0] != record.NOT_FILLED)
    # an open under the band on a day that reaches it later: from which open up the minute bars are asked
    later = {o: record.fill(pick, first_day(o, h=filled[0] + 0.5, c=filled[0])) for o in cents(floor, filled[0] - 0.01)}
    assert all(status == record.UNCERTAIN for status, *_ in later.values())
    asked = [o for o, (*_, reason) in later.items() if reason in intraday.RESOLVABLE]
    assert asked == cents(asked[0], filled[0] - 0.01), "the opens the minutes are asked about run up to the band"
    # the same two days read again with their minutes: one is decided, one stays uncertain
    quiet, crossing, after = (0, 99.0, 99.4, 98.9, 99.2), (12, 99.2, 100.3, 99.1, 100.2), (40, 100.2, 100.5, 100.0, 100.2)
    decided_day = first_day(99.0, h=100.5, low=98.9, c=100.2)
    assert record.replay(pick, [decided_day])["status"] == record.UNCERTAIN
    decided = record.replay(pick, [decided_day], minutes=minutes_of(quiet, crossing, after))
    skipped_day = first_day(97.5, h=100.5, low=97.4, c=100.2)
    skipped = record.replay(pick, [skipped_day], minutes=minutes_of((0, 97.5, 98.0, 97.4, 97.9),
                                                                    (12, 97.9, 100.3, 97.8, 100.2), after))
    assert decided["status"] in plan.HELD_STATUSES and decided.get("minute_evidence")
    assert skipped["status"] == record.UNCERTAIN and not skipped.get("minute_evidence")
    assert record.r_multiple(skipped, pick["stop"]) is None and skipped["exit_price"] is None    # no fill, no result
    # the minute rule itself: how high the window's minute must go to fill, at what price, and how long the window is
    levels = record.ticket_levels(pick)

    def minute(high: float, offset: int = 12):
        """A minute that opens at 99.20 and reaches `high`, on a day that runs to 103.90 an hour later."""
        day = first_day(99.0, h=103.9, low=98.9, c=103.5)
        return intraday.resolve(levels, minutes_of(quiet, (offset, 99.2, high, 99.1, 99.3), (60, 99.3, 103.9, 99.2, 103.5)), day)
    highs = {high: minute(high) for high in cents(lines["trigger"] - 0.2, lines["trigger"] + 0.2)}
    crossed = [high for high, (status, *_) in highs.items() if status == intraday.FILLED]
    assert crossed == cents(crossed[0], lines["trigger"] + 0.2) and all(
        status == intraday.NOT_FILLED for high, (status, *_) in highs.items() if high not in crossed)
    prices = {price for high in crossed for price in [highs[high][1]]}
    assert len(prices) == 1, "a minute that opened under the trigger fills at one price however high it went"
    window = next(offset for offset in range(1, 2 * plan.ENTRY_WINDOW_MINUTES)
                  if minute(lines["trigger"] + 0.2, offset)[0] != intraday.FILLED)
    assert minute(lines["trigger"] + 0.2, window)[0] == intraday.NOT_FILLED
    return {"low": line_at(filled[0]), "high": line_at(filled[-1]), "reach": line_at(reach), "back": line_at(back),
            "asked_from": line_at(asked[0]), "minute_reach": line_at(crossed[0]), "minute_price": line_at(prices.pop()),
            "window": window, "decided_at": decided["entry_ref"]}


def fill_problems(text: str = PROMPT_RAW) -> list[str]:
    read = fill_readings()
    assert read["back"] == read["high"], "the sentence says 'trades back to it' of the line the band ends at"
    assert read["decided_at"] == TICKET_LINES[read["minute_price"]]
    return lacking(
        text,
        f"The first day opens at or over the {read['low']} and at or under the {read['high']}: **filled at the open**.",
        f"The first day never reaches the {read['reach']}, or opens over the {read['high']} and never trades back to "
        "it: **not filled**.",
        f"The first day opens under the {read['low']} (but not under the {read['asked_from']}) and reaches it later: "
        "the day's one-minute bars decide.",
        f"An open under the {read['asked_from']} that later recovers is uncertain, whatever the minutes show.",
        f"The first minute of the first {read['window']} minutes whose high reaches the {read['minute_reach']} fills "
        f"at the {read['minute_price']}.",
        "If no minute in the window does, it is not filled, however far the stock goes later.",
        "Anything the bars cannot put in order is **uncertain**: no fill, no result, counted apart.",
        # section 2.2 says the same of the open, calling the trigger the buy stop
        f"it opened at or over the buy stop and at or under the {read['high']}, which is the case the model books as "
        "\"filled at the open\"")


def test_a_ticket_fills_where_the_fill_rule_and_the_minute_rule_put_it():
    assert not fill_problems(), fill_problems()
    read = fill_readings()
    assert read["window"] == plan.ENTRY_WINDOW_MINUTES
    # five lines, three of them named by the readings and two (the stop, the day-2 line) by none: the
    # sweep crossed every one, so a rule that turned on either would have named it
    assert {read[k] for k in ("low", "high", "reach", "back", "asked_from", "minute_reach", "minute_price")} == {
        "trigger", "limit", "skip-below line"}


# ------------------------------------------------- 5.7: admission ----------
def admission_problems(text: str = PROMPT_RAW) -> list[str]:
    """admission.block() over the four ways a dollar-only day's two expansion
    checks can come out, and over the 4% scan's routes with neither passed."""
    letters = [letter for letter, _ in admission.DOLLAR_CHECKS]

    def admitted(route: str, *passed: str) -> bool:
        row = {"scan": route, "quality": {"checks": [{"letter": letter, "passed": letter in passed}
                                                      for letter in letters]}}
        return admission.block(row)["admitted"]
    assert len(letters) == 2 and all(admitted(route) for route in admission.BURST_ROUTES)
    one = [admitted(admission.DOLLAR_ROUTE, letter) for letter in letters]
    assert admitted(admission.DOLLAR_ROUTE, *letters) and not admitted(admission.DOLLAR_ROUTE) and len(set(one)) == 1
    needs = f"{letters[0]} or {letters[1]} passed." if one[0] else f"{letters[0]} and {letters[1]} both passed."
    routes = " or ".join(f"`{route}`" for route in admission.BURST_ROUTES)
    return lacking(text, f"A candidate the 4% scan found (route {routes}) is admitted.",
                   f"A candidate only the dollar scan found is admitted only when {needs}")


def test_a_dollar_only_candidate_is_admitted_as_the_admission_block_admits_it():
    assert not admission_problems(), admission_problems()


# ------------------------------------------------- 5.8: the chart reader ---
def reader_problems(text: str = PROMPT_RAW) -> list[str]:
    """grader.final_grade(), the one adjustment the run applies to a reader's
    reply, over every mechanical grade and every grade a reply can name."""
    rank = grader.GRADES.index                                  # best first
    finals = {(mechanical, returned): grader.final_grade(mechanical, returned)
              for mechanical in grader.GRADES for returned in grader.GRADES}
    confirms = all(finals[grade, grade] == grade for grade in grader.GRADES)
    lowers = any(rank(final) > rank(mechanical) for (mechanical, _), final in finals.items())
    raises = any(rank(final) < rank(mechanical) for (mechanical, _), final in finals.items())
    assert confirms and lowers, finals
    return lacking(text, "The reader may confirm a grade or lower it. "
                         + ("It may raise one." if raises else "It can never raise one."))


def test_the_chart_reader_can_lower_a_grade_and_never_raise_one():
    assert not reader_problems(), reader_problems()
    best, worst = grader.GRADES[0], grader.GRADES[-1]
    assert grader.final_grade(worst, best) == worst and grader.final_grade(best, worst) == worst


# ------------------------------------------------- 5.6: letter H -----------
SHARES_OF_A_RANGE = {2: "half", 3: "third", 4: "quarter", 5: "fifth", 10: "tenth"}


def letter_h_problems(text: str = PROMPT_RAW) -> list[str]:
    """The H row of the checklist table, from quality.MIN_CLOSE_POS (the
    phrase also stands in the owner's own rubric, which is his and not held)."""
    parts = 1 / (1 - quality.MIN_CLOSE_POS)
    assert abs(parts - round(parts)) < 1e-9 and round(parts) in SHARES_OF_A_RANGE, quality.MIN_CLOSE_POS
    row = (f"| H | {g(quality.WEIGHTS['H'])} | the burst closed near its high: above its open and in the top "
           f"{SHARES_OF_A_RANGE[round(parts)]} of the day's range |")
    return lacking(between("### 5.6 ", "\n### ", text), row)


def test_letter_h_states_the_checklists_own_share_of_the_range():
    assert not letter_h_problems(), letter_h_problems()


# ------------------------------------------------- 10.6: the gapped open ---
def gap_problems(text: str = PROMPT_RAW) -> list[str]:
    """The gap line plan.anticipation_plan() writes on a ticket, as a
    percentage of its last close."""
    p = plan.anticipation_plan(ticker="AAA", close=50.0, box_high=50.2, box_low=49.0, lows_last3=[49.2, 49.5, 49.4],
                               account=plan.Account())
    pct = round(100 * (p["gap_ok_above"] / p["close"] - 1), 6)
    assert pct == plan.GAP_OK_PCT and f"more than {g(pct)}% above" in p["gap_rule"]
    problems = lacking(between("### 10.6 ", "\n### ", text),
                       f"If the stock opened more than {g(pct)}% above its last close, the plan asks for a catalyst "
                       "check first")
    stated_gaps = {float(found) for found in re.findall(r"more than (\d+(?:\.\d+)?)% above (?:its|the) last close",
                                                        prose(text))}
    return problems + ([] if stated_gaps == {pct} else [f"a gapped open is stated as {sorted(stated_gaps)}%, not {g(pct)}%"])


def test_a_gapped_open_is_the_anticipation_plans_own_line():
    assert not gap_problems(), gap_problems()


# ------------------------------------------------- 10.3 to 10.6: price states
@functools.lru_cache(maxsize=None)
def published_tickets(kind: str) -> tuple[dict, ...]:
    """Every published ticket of one kind in the page fixtures, as the morning
    collector binds it: its levels (morning.admitted_rows) and its last close."""
    found = []
    for variant in ("full", "next", "notrade"):
        data = json.loads((PAGE_FIXTURES / f"{variant}.json").read_text())
        rows = {("burst", row["ticker"]): row for row in data["bursts"]}
        rows.update({("anticipation", row["ticker"]): row for row in data["watchlist"]["top"]})
        for ticket in morning.admitted_rows(data):
            if ticket["kind"] == kind:
                row = rows[kind, ticket["ticker"]]
                found.append({**ticket["levels"], "last close": row["close"] if kind == "burst" else row["plan"]["close"]})
    assert found, kind
    return tuple(found)


def ticket_lines(levels: dict, kind: str) -> dict[str, float]:
    """A ticket's lines by the names sections 10.3 to 10.6 give them."""
    lines = {"stop": levels["stop"], "trigger": levels["trigger"], "limit": levels["limit"]}
    if kind == "burst":
        lines.update({"skip-below line": levels["entry_low"], "day-2 line": levels["day2_spent_above"]})
    return lines


def where_test(where: str, lines: dict[str, float]):
    """A "Where the price is" cell as a test of a price: clauses joined by
    ", " or " and " must all hold, alternatives by ", or " any one. "up to" a
    line does not say whether the line itself is in, so the test takes
    `strict`: without the line when True, with it when False."""
    def line(name: str) -> float:
        if name not in lines:
            raise ValueError(f"this ticket has no {name!r} (in {where!r})")
        return lines[name]

    def clause(text: str):
        for pattern, test in (
                (r"from the (.+) through the (.+)", lambda price, strict, low, high: low <= price <= high),
                (r"at or under the (.+)", lambda price, strict, at: price <= at),
                (r"at or over the (.+)", lambda price, strict, at: price >= at),
                (r"up to the (.+)", lambda price, strict, at: price < at if strict else price <= at),
                (r"under the (.+)", lambda price, strict, at: price < at),
                (r"over the (.+)", lambda price, strict, at: price > at)):
            match = re.fullmatch(pattern, text)
            if match:
                at = [line(name) for name in match.groups()]
                return lambda price, strict: test(price, strict, *at)
        raise ValueError(f"cannot read {text!r} (in {where!r})")
    plain = re.sub(r"\s*\([^)]*\)", "", where)
    parts = [[clause(text) for text in re.split(r", | and ", part)] for part in plain.split(", or ")]
    return lambda price, strict: any(all(test(price, strict) for test in part) for part in parts)


def state_table(heading: str, text: str) -> list[tuple[tuple[str, ...], str]]:
    """(the state words, where the price is) for each row of a section's state table."""
    rows = []
    for line in between(heading, "\n### ", text).splitlines():
        if line.startswith("| `"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            rows.append((tuple(re.findall(r"`(\w+)`", cells[0])), cells[1]))
    return rows


def state_table_problems(heading: str, kind: str, text: str = PROMPT_RAW) -> list[str]:
    """Each row against morning.price_state(), a cent at a time across every
    line of every published fixture ticket of the kind: a price the row
    describes must be in one of the row's states, every price must be
    described by exactly one row (or, on a line a row runs "up to", by the
    row the state belongs to), and every state a row names must be reached
    inside that row on some ticket."""
    rows = state_table(heading, text)
    if not rows:
        return [f"{heading}: no state table"]
    problems, reached, given = [], set(), set()
    for levels in published_tickets(kind):
        lines = ticket_lines(levels, kind)
        try:
            tests = [where_test(where, lines) for _, where in rows]
        except ValueError as exc:
            return [f"{heading}: {exc}"]
        for price in cents(min(lines.values()) - 1, max(lines.values()) + 1):
            state = morning.price_state(price, levels, "recent")
            given.add(state)
            strict = [index for index, test in enumerate(tests) if test(price, True)]
            loose = [index for index, test in enumerate(tests) if test(price, False)]
            claimed = strict or loose
            right = [index for index in claimed if state in rows[index][0]]
            if len(strict) > 1 or not right or (strict and right != strict):
                problems.append(f"{heading}: a price of {price:.2f} is `{state}` on a ticket with {lines}; the table "
                                f"puts it under {[rows[index][0] for index in claimed] or 'no row'}")
            reached.update((index, state) for index in right)
    problems += [f"{heading}: no ticket's price in the row \"{where}\" is `{state}`"
                 for index, (states, where) in enumerate(rows) for state in states if (index, state) not in reached]
    named = {state for states, _ in rows for state in states}
    if named != given:
        problems.append(f"{heading}: the table names {sorted(named)}; these tickets' prices are in {sorted(given)}")
    return problems[:6]


def burst_state_problems(text: str = PROMPT_RAW) -> list[str]:
    return state_table_problems("### 10.4 ", "burst", text)


def anticipation_state_problems(text: str = PROMPT_RAW) -> list[str]:
    return state_table_problems("### 10.6 ", "anticipation", text)


def state_sentence_problems(text: str = PROMPT_RAW) -> list[str]:
    """What 10.3 and 10.6 say in sentences about the lines and the states,
    from the same tickets."""
    bursts, coils = published_tickets("burst"), published_tickets("anticipation")
    usual = [levels for levels in bursts if levels["stop"] < levels["entry_low"]]
    over = [levels for levels in bursts if levels["stop"] >= levels["entry_low"]]
    assert usual and over, "the fixtures carry a burst ticket of each shape"
    orders = {tuple(sorted(ticket_lines(levels, "burst"), key=ticket_lines(levels, "burst").get)) for levels in usual}
    assert len(orders) == 1 and all(levels["trigger"] == levels["last close"] for levels in bursts)
    run = ", ".join("trigger (the last close)" if name == "trigger" else name for name in orders.pop())
    phrases = [f"For a burst ticket the lines usually run, low to high: {run}."]
    for levels in over:                 # the stop at or over the skip-below line
        prices = cents(levels["entry_low"] - 1, levels["trigger"])
        states = {price: morning.price_state(price, levels, "recent") for price in prices}
        at_stop, just_over = states[levels["stop"]], states[round(levels["stop"] + 0.01, 2)]
        assert {state for price, state in states.items() if price <= levels["stop"]} == {at_stop}
        assert {state for price, state in states.items() if levels["stop"] < price < levels["trigger"]} == {just_over}
        absent = sorted(set(morning.PRICE_STATES) - {"unknown"} - {
            morning.price_state(price, levels, "recent")
            for price in cents(levels["stop"] - 5, levels["day2_spent_above"] + 5)})
        assert len(absent) == 1, absent
        phrases.append(f"Then no price is `{absent[0]}`: a price at or under the stop is `{at_stop}`, and "
                       f"`{just_over}` starts just over the stop.")
    for levels in coils:
        assert levels["entry_low"] == levels["trigger"] and levels["day2_spent_above"] is None
        assert levels["limit"] == round(levels["trigger"] * (1 + plan.TRIGGER_LIMIT_PCT / 100), 2)
        named = {**ticket_lines(levels, "anticipation"), "last close": levels["last close"]}
        phrases.append(f"Its lines run: {', '.join(sorted(named, key=named.get))} (the trigger plus "
                       f"{g(plan.TRIGGER_LIMIT_PCT)}%). It has no skip-below line and no day-2 line. Its trigger is "
                       "above the last close")
    no_price = {morning.price_state(None, bursts[0], "recent"), morning.price_state(bursts[0]["trigger"], bursts[0], "stale")}
    assert len(no_price) == 1
    phrases.append(f"The state `{no_price.pop()}` means no recent price was read")
    return lacking(text, *phrases)


def test_the_burst_state_table_is_what_price_state_gives():
    assert not burst_state_problems(), burst_state_problems()
    assert {state for states, _ in state_table("### 10.4 ", PROMPT_RAW) for state in states} == \
        set(morning.PRICE_STATES) - {"unknown"}


def test_the_anticipation_state_table_is_what_price_state_gives():
    assert not anticipation_state_problems(), anticipation_state_problems()
    # the state a burst ticket has under its trigger is one an anticipation ticket never has
    assert "below_trigger" not in {state for states, _ in state_table("### 10.6 ", PROMPT_RAW) for state in states}


def test_the_sentences_about_the_lines_and_the_states_are_the_tickets_own():
    assert not state_sentence_problems(), state_sentence_problems()


# ------------------------------------------------- the holds can fail ------
HOLDS = (ladder_problems, half_problems, gate_problems, fill_problems, admission_problems, reader_problems,
         letter_h_problems, gap_problems, burst_state_problems, anticipation_state_problems, state_sentence_problems)


def replaced(old: str, new: str):
    def edit(text: str) -> str:
        assert text.count(old) == 1, old
        return text.replace(old, new)
    return edit


def exchanged(heading: str, pattern: str, first: int, second: int):
    """The text with the bodies of two numbered rows or items of one section
    exchanged, their numbers left where they were."""
    def edit(text: str) -> str:
        section = between(heading, "\n### ", text)
        found = {int(match[1]): match for match in re.finditer(pattern, section, flags=re.M)}
        a, b = found[first], found[second]
        swapped = (section[:a.start(2)] + b[2] + section[a.end(2):b.start(2)] + a[2] + section[b.end(2):])
        assert swapped != section
        return text.replace(section, swapped)
    return edit


TABLE_ROW, LIST_ITEM = r"^\| (\d+) \| (.+) \|$", r"^(\d+)\. (.+(?:\n   .+)*)$"
#: Edits to the prompt that left every test green before these holds, and the
#: hold that must name each. A reviewer made nine by execution: steps 4 and 5
#: of the ladder and gates 3 and 4 exchanged, the two 5.14 phrases, "RE or
#: VOL", "rounded up", "may raise", "top quarter", 3%, and the `below_trigger`
#: row of 10.4. The others are the same sentence where the file says it
#: again, and the neighbouring rows and items.
EDITS = {
    "5.15: steps 4 and 5 exchanged, the half sold before the stop": (
        exchanged("### 5.15 ", TABLE_ROW, 4, 5), ladder_problems),
    "5.9: gates 3 and 4 exchanged, the review before the admission": (
        exchanged("### 5.9 ", LIST_ITEM, 3, 4), gate_problems),
    "5.14: a minute's fill at the limit": (
        replaced("high reaches the trigger fills at the trigger.", "high reaches the trigger fills at the limit."),
        fill_problems),
    "5.14: an open fills up to the day-2 line": (
        replaced("opens at or over the trigger and at or under the limit:",
                 "opens at or over the trigger and at or under the day-2 line:"), fill_problems),
    "2.2: an open fills up to the day-2 line": (
        replaced("and at or under the limit, which is the case", "and at or under the day-2 line, which is the case"),
        fill_problems),
    "5.7: RE or VOL": (
        replaced("is admitted only when RE and VOL\n  both passed.", "is admitted only when RE or VOL\n  passed."),
        admission_problems),
    "11.2: the half rounded up twice": (
        replaced("N minus (N divided by 2, rounded down)", "N minus (N divided by 2, rounded up)"), half_problems),
    "5.8: the reader may raise a grade": (replaced("It can never raise one.", "It may raise one."), reader_problems),
    "5.6: H in the top quarter": (
        replaced("above its open and in the top fifth of the day's range |",
                 "above its open and in the top quarter of the day's range |"), letter_h_problems),
    "10.6: gapped at 3%": (
        replaced("opened more than 2% above its last close", "opened more than 3% above its last close"),
        gap_problems),
    "10.4: below_trigger without the stop": (
        replaced("| `below_trigger` | over the stop and at or over the skip-below line, up to the trigger |",
                 "| `below_trigger` | at or over the skip-below line, up to the trigger |"), burst_state_problems),
    "10.4: below_trigger from over the skip-below line": (
        replaced("| `below_trigger` | over the stop and at or over the skip-below line, up to the trigger |",
                 "| `below_trigger` | over the stop and over the skip-below line, up to the trigger |"),
        burst_state_problems),
    "10.4: the below_trigger row named below_entry_floor": (
        replaced("| `below_trigger` | over the stop and", "| `below_entry_floor` | over the stop and"),
        burst_state_problems),
    "10.4: above_limit from over the trigger": (
        replaced("| `above_limit` | over the limit, up to the day-2 line |",
                 "| `above_limit` | over the trigger, up to the day-2 line |"), burst_state_problems),
    "10.6: below_entry_floor from the stop": (
        replaced("| `below_entry_floor` | over the stop, under the trigger (the usual state) |",
                 "| `below_entry_floor` | at or over the stop, under the trigger (the usual state) |"),
        anticipation_state_problems),
    "10.3: below_trigger from the skip-below line when the stop is over it": (
        replaced("`below_trigger` starts just over the stop.", "`below_trigger` starts at the skip-below line."),
        state_sentence_problems),
    "11.3: items 3 and 4 exchanged, the half sale before the stop": (
        exchanged("### 11.3 ", LIST_ITEM, 3, 4), ladder_problems),
    "5.15: steps 2 and 3 exchanged, the gap exit before a stop at the open": (
        exchanged("### 5.15 ", TABLE_ROW, 2, 3), ladder_problems),
    "5.15: steps 7 and 8 exchanged, the day-3 half before the no-progress exit": (
        exchanged("### 5.15 ", TABLE_ROW, 7, 8), ladder_problems),
    "5.9: gates 5 and 6 exchanged, the registry before the ticket rule": (
        exchanged("### 5.9 ", LIST_ITEM, 5, 6), gate_problems),
}


@pytest.mark.parametrize("edit", list(EDITS))
def test_an_edit_that_once_passed_is_named_by_the_hold_of_its_rule(edit):
    change, hold = EDITS[edit]
    edited = change(PROMPT_RAW)
    assert edited != PROMPT_RAW and not hold(PROMPT_RAW)
    assert hold(edited), edit
    # and by that hold alone: no other hold fires on an edit that is not its rule's
    assert not [other.__name__ for other in HOLDS if other is not hold and other(edited)]


def test_an_edit_no_hold_names_passes_every_hold():
    """The control: a sentence none of the holds reads, reworded."""
    edited = replaced("Read the four prices this way:", "Read the four prices like this:")(PROMPT_RAW)
    assert not [hold.__name__ for hold in HOLDS if hold(edited)]
