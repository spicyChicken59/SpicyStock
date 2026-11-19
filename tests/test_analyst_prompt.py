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
labelled synthetic example."""
from __future__ import annotations

import datetime as dt
import importlib
import re
from pathlib import Path
from zoneinfo import ZoneInfo

from src import (breadth, delivery, grader, morning, pipeline, plan, quality, reader_coverage, record,
                 report, review_selection, scans, sessions, timing, universe, watchlist)

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
