"""The texts a reader learns the strategy from say what the code does.

An outside audit found the strategy page (the Method view's walkthrough,
``knowledge/method.md``, the help terms and the evidence paragraph) describing
the stops loosely, leaving out the admission gate and two exit rules, quoting
the market light's thresholds unscaled, and presenting a third party's
backtest of a different setup as part of the method. These tests hold the
corrected sentences to the modules:

* ``knowledge/method.md`` names every step of ``plan.EXIT_RULES`` and each of
  the five rules ``breadth.regime()`` reads, with the modules' own numbers;
* the walkthrough narrates every exit step, the admission gate, the five
  regime rules with their scaling, and what a fill at the open assumes;
* the help terms and the two static paragraphs carry the corrected claims and
  no longer carry the ones that were wrong.

``knowledge/rules.md``, the rule sheet, is held by ``tests/test_rule_sheet.py``.
"""
from __future__ import annotations

import re
from pathlib import Path

from src import admission, breadth, grader, plan, quality, record, scans, watchlist

ROOT = Path(__file__).resolve().parent.parent


def prose(path: Path) -> str:
    """A document with its line wrapping removed, so a phrase is read as a
    sentence and not as the width it was wrapped at."""
    return re.sub(r"\s+", " ", path.read_text())


METHOD = prose(ROOT / "knowledge" / "method.md")
WALK_SOURCE = (ROOT / "docs" / "app-method.js").read_text()
READING = (ROOT / "docs" / "app-reading.js").read_text()
PAGE = (ROOT / "docs" / "index.html").read_text()
BREADTH_RULES = ("DOWN4_ALARM", "RED_RATIO_10D", "RED_RATIO_5D", "YELLOW_RATIO_10D", "UP50_MONTH_HOT")


def captions(source: str = WALK_SOURCE) -> str:
    """The walkthrough's captions with adjacent string literals joined, so a
    sentence the source breaks across lines is read whole. A number a caption
    takes from RULES stays a call and breaks the sentence there."""
    steps = source.split("const STEPS = [", 1)[1].split("// the stop in force", 1)[0]
    return re.sub(r"'\s*\+\s*'", "", steps)


def section(text: str, heading: str) -> str:
    """One ``## heading`` section of the method note, unwrapped."""
    raw = (ROOT / "knowledge" / "method.md").read_text() if text is METHOD else text
    body = raw.split(f"## {heading}", 1)[1].split("\n## ", 1)[0]
    return re.sub(r"\s+", " ", body)


def term(name: str, source: str = READING) -> str:
    found = re.search(rf"\n    {name}: \['[^']*', '([^']*)'\]", source)
    assert found, f"docs/app-reading.js defines no term {name}"
    return found.group(1)


# --------------------------------------------------------- the method note ----
def test_the_method_note_names_every_exit_step_the_ticket_prints():
    exits = section(METHOD, "The plan")
    for rule in plan.EXIT_RULES:
        assert f"`{rule['key']}`" in exits, f"knowledge/method.md names no exit step {rule['key']}"
    # with the modules' own numbers
    for phrase in (
        f"+{plan.SELL_HALF_PCT:g}% same or next day",
        f"{plan.TRAIL_CENTS * 100:g}–{plan.TRAIL_CENTS_MAX * 100:g} cents under that day's high",
        f"The model uses {plan.TRAIL_CENTS * 100:g} cents",
        f"until day {plan.SELL_HALF_DAY}'s close has sold a half",
        f"a close {plan.ABNORMAL_DAY_PCT:g}% or more over the entry",
        f"an open {plan.GAP_EXIT_PCT:g}% or more over the entry",
        f"close of day {plan.ENTRY_DAY} → the stop rises to the entry day's low",
        f"day {plan.SELL_HALF_DAY} close → sell at least half",
        f"a day-{plan.NO_PROGRESS_DAY} close at or under the entry → out",
        f"from the close of day {plan.TRAIL_FROM_DAY} the stop rises to each day's low",
        f"day {plan.FINAL_EXIT_DAY} close → out",
        f"before day {plan.NO_BREAKEVEN_BEFORE_DAY} just because it is green",
    ):
        assert phrase in exits, phrase
    # what the model does where the ticket's words say more, and whose the caution is
    for phrase in ("The model books no sale for it", "In the model an open at or under the stop is out at that open",
                   "a low at or under it is out at the stop price", "which the model does not walk",
                   "a different setup (EP 9M)", "unvalidated on bursts", "the model moves no stop for it",
                   'gains "sell into any strength; do not add"'):
        assert phrase in exits, phrase
    assert "No break-even move before day 5 (E)." not in METHOD
    assert plan.RED_CLAUSE == "Breadth is red: sell into any strength; do not add."
    assert {rule["key"]: rule["source"] for rule in plan.EXIT_RULES}["no_breakeven"] == "T"


def test_the_method_note_states_the_five_regime_rules_with_their_scaling():
    monitor = section(METHOD, "Market Monitor")
    for name in BREADTH_RULES:
        assert f"`{name}`" in monitor, f"knowledge/method.md names no {name}"
    assert "five rules over the stocks measured that night" in monitor
    for phrase in (
        f"at or over the scaled {breadth.DOWN4_ALARM}",
        f"a {breadth.RATIO_LONG_SESSIONS}-day ratio below {breadth.RED_RATIO_10D:g} (`RED_RATIO_10D`",
        f"a {breadth.RATIO_SHORT_SESSIONS}-day ratio below {breadth.RED_RATIO_5D:g} with more names down",
        f"a {breadth.RATIO_LONG_SESSIONS}-day ratio below {breadth.YELLOW_RATIO_10D:g} (`YELLOW_RATIO_10D`",
        f"than the scaled {breadth.UP50_MONTH_HOT} (`UP50_MONTH_HOT`",
        f"than the scaled {breadth.DOWN25_QUARTER_OVERSOLD} is an oversold flag",
        f"threshold × N ÷ {breadth.REFERENCE_UNIVERSE:,}",
        "none of the five fires",
        "The ratios are never scaled",
    ):
        assert phrase in monitor, phrase
    # the dated example is the module's own arithmetic at that night's count
    scaled = [breadth.scaled_threshold(getattr(breadth, name), 3513)
              for name in ("DOWN4_ALARM", "UP50_MONTH_HOT", "DOWN25_QUARTER_OVERSOLD")]
    assert "at N = 3,513 (the 17 November 2026 record) 700 becomes {:g}, 20 becomes {:g} and 200 becomes {:g}".format(*scaled) in monitor
    assert breadth.SIZE_MULTIPLIER == {"green": 1.0, "yellow": 0.5, "red": 0.0}
    # the unscaled sentence the audit read is gone
    assert "700+ names down 4% in a day" not in METHOD


def test_the_method_note_states_the_ticket_the_stop_and_the_weights_as_the_code_has_them():
    body = section(METHOD, "The plan")
    for phrase in (
        "the burst day's low, else the bar's midpoint",
        f"at most {plan.MAX_STOP_PCT:g}% under the ticket's LIMIT",
        f"replaces it at the close of day {plan.ENTRY_DAY} when it is higher",
        f"Between {plan.IDEAL_STOP_PCT:g}% and {plan.MAX_STOP_PCT:g}% the risk is halved (P), which is every burst ticket",
        f"a buy stop AT the burst close with a limit at most {plan.ENTRY_ABOVE_PCT:g}% above it",
        f"an open more than {plan.ENTRY_BELOW_PCT:g}% under the close is the burst failing",
        f"+{plan.SKIP_GAP_PCT:g}% is the level at which he sells half",
    ):
        assert phrase in body, phrase
    # the halving on a half-percent risk: a quarter on green, an eighth on yellow
    quarter = plan.DEFAULT_RISK_PCT * plan.STOP_RISK_MULTIPLIER
    assert f"{quarter:g}% of equity on green, {quarter * breadth.SIZE_MULTIPLIER['yellow']:g}% on yellow" in body
    assert "a buy zone from 2% under the burst close to 4% above it" not in METHOD and "else half its range" not in METHOD
    checklist = section(METHOD, "The A-quality checklist (`src/quality.py`) — Bonde's letters")
    w = quality.WEIGHTS
    assert (w["L"], w["C"], {w[k] for k in "2YNH"}) == (2.0, 2.0, {1.5})
    assert "L 2, C 2, and 1.5 each for 2, Y, N and H, ten in all" in checklist and sum(w.values()) == 10
    floors = {grade: floor for floor, grade in grader.GRADE_BANDS}
    assert (f"A+ from {floors['A+']} with at least four of the eight checks at their A+ standard (else A), "
            f"A from {floors['A']}, B from {floors['B']}, C from {floors['C']}, skip below") in checklist
    assert quality.MIN_A_PLUS_LETTERS == 4 and len(quality.LETTERS + quality.EXTRA_CHECKS) == 8
    assert f"three or more consecutive rising closes ending the session before the burst, of any size" in checklist
    assert quality.VETO_UP_DAYS == 3


def test_the_method_note_states_the_watchlist_and_the_record_as_the_code_has_them():
    coil = section(METHOD, "Anticipation watchlist")
    for phrase in (
        f"three tight days in a row, each under {watchlist.TIGHT_FRACTION:.0%} of the {watchlist.ADR_SESSIONS}-day average range",
        "or three such days in the last ten",
        f"≤ {watchlist.MAX_BREAKDOWNS} breakdown in the last ten sessions",
        "not up three days in a row",
        f"a close at most {watchlist.MAX_EXTENSION:.2f} times its {watchlist.EXTENSION_SESSIONS}-session average",
        f"a box of {watchlist.BOX_MIN}–{watchlist.BOX_MAX} sessions",
        "Dry volume is measured and decides nothing",
        f"the lowest low of the last {plan.STOP_LOOKBACK_SESSIONS} sessions",
        f"more than {plan.MAX_STOP_PCT:g}% under the ticket's limit, the trigger +{plan.TRIGGER_LIMIT_PCT:g}%",
    ):
        assert phrase in coil, phrase
    assert (watchlist.TTT_SESSIONS, watchlist.MIN_TIGHT, watchlist.TIGHT_LOOKBACK, watchlist.BREAKDOWN_LOOKBACK) == (3, 3, 10, 10)
    assert watchlist.MAX_UP_RUN == 2, "the list fails at three rising closes in a row"
    assert "vol_dry" not in watchlist.STAGE_C
    kept = section(METHOD, "The record")
    assert "`src/intraday.py`" in kept and f"`{record.INTRADAY_FILL}`" in kept
    assert f"the first minute of the first {plan.ENTRY_WINDOW_MINUTES} whose high reaches the trigger" in kept
    assert "replayed from daily bars alone" not in METHOD
    assert "it is booked out at the stop, one R lost" in kept
    assert "A fill at the open assumes the order was already resting at the broker before the open" in kept
    assert "[rules.md](rules.md)" in METHOD and (ROOT / "knowledge" / "rules.md").exists()
    # the anticipation scans' own volume operators: one inclusive, two strict
    assert scans.RULES["dt.min_prior_volume"] == scans.RULES["ti65.min_prior_volume_exclusive"] == scans.MIN_VOLUME
    assert "at least for Double Trouble, more than for the other two" in METHOD


# ---------------------------------------------------------- the walkthrough ----
#: the words a caption narrates each printed exit step in
EXIT_STEP_WORDS = {
    "sell_half_8pct": "sell half and raise the stop to ",
    "abnormal_10pct": "% or more over the entry is an abnormal day",
    "gap_20pct": "% or more at an open after entry: sell at the open",
    "entry_day_low": " the stop rises to the entry day’s low when that is higher",
    "day3_sell_half": "’s close, sell at least half then, in whole shares",
    "day3_no_progress": " is no follow-through: out entirely",
    "trail_after_day3": " the stop trails each day’s low and never moves down",
    "day5_exit": " is the exit, at the close",
    "stop": "a low at or under the stop is out at the stop price",
    "no_breakeven": "caution against moving the stop to break-even before day ",
}


def test_the_walkthrough_narrates_every_exit_step_the_ticket_prints():
    assert set(EXIT_STEP_WORDS) == {rule["key"] for rule in plan.EXIT_RULES}, "an exit step the walkthrough does not narrate"
    text = captions()
    for step, words in EXIT_STEP_WORDS.items():
        assert words in text, f"the walkthrough does not narrate {step}"
    # the two the audit found missing, and what the model does that the ticket's words do not say
    for phrase in ("A later open at or under the stop is out at that open, which can be well under the stop",
                   "even when the same bar’s high reached a sale level",
                   "an abnormal close books no sale and only raises the stop to ",
                   "the model moves no stop for it, and the raises above can still lift the stop over the entry sooner",
                   "theStrat Lab’s backtest of a different setup, the episodic pivot",
                   "not measured on bursts"):
        assert phrase in text, phrase
    assert "There is no break-even move before day" not in text and "no break-even E" not in text


def test_the_walkthrough_states_the_stop_the_admission_and_the_scaled_light():
    text = captions()
    by_id = {found.group(1): found.group(0) for found in re.finditer(r"\{ id: '(\w+)'.*?\n      who: .*?\}(?=,\n|\n)", text, re.S)}
    assert list(by_id) == ["thesis", "leg", "base", "quiet", "signal", "breadth", "plan", "fill", "third", "trail", "record"]
    # the thesis: his entry is the burst day; this build's is the next session, with a stand-in stop
    assert "Bonde enters on the burst day itself, with his stop at that day’s low" in by_id["thesis"]
    assert "it enters the next session through a buy stop at the burst close" in by_id["thesis"]
    assert "standing in as the stop" in by_id["thesis"] and "stop under the burst" not in text
    assert "a stand-in for his entry-day low, which replaces it at the close of day " in by_id["plan"]
    assert "and every burst ticket is halved this way" in by_id["plan"]
    # the admission gate, which blocks a name the dollar scan alone found
    assert "which can admit a day under" not in text
    assert "Being found is not being admitted" in by_id["signal"]
    assert ("a name only the Dollar scan found can only when its day also passed RE and VOL. Otherwise it keeps its "
            "grade as research, with no ticket and no chart read") in by_id["signal"]
    assert [name for _, name in admission.DOLLAR_CHECKS] == ["range_expansion", "higher_volume"]
    assert "a burst gets a ticket only after an accepted chart review" in by_id["signal"]
    assert "RE and VOL add nothing to the score" in by_id["signal"] and set(quality.WEIGHTS) == set(quality.LETTERS)
    # the light: five rules, the count thresholds scaled, green needing all five quiet
    light = by_id["breadth"]
    assert "Five rules set the regime, three red and two yellow" in light
    assert "so each is scaled before it is compared: threshold × stocks measured that night ÷ " in light
    assert "The ratios are never scaled" in light
    assert "none of the five rules below fires (a ' + LONG + ' ratio at or over '" in light and "alone is not enough): full size, A+ and A" in light
    assert ", scaled: half size, A+ only" in light and ", scaled; or a ' + SHORT + ' ratio under '" in light
    assert "whether it improves outcomes is not established" in light
    assert "ratio at or over ' + g(N('breadth.yellow_ratio_10d')) + ': full size'" not in text, "green is not the ratio alone"
    # the rule names it scales are the two regime() scales
    source = (ROOT / "src" / "breadth.py").read_text().split("def regime(", 1)[1].split("\ndef ", 1)[0]
    assert re.findall(r"scaled_threshold\((\w+),", source) == ["DOWN4_ALARM", "UP50_MONTH_HOT", "DOWN25_QUARTER_OVERSOLD"]
    # the fill at the open, and the record's minute bars
    assert "the model’s fill at the open assumes the buy stop-limit was already resting at the broker before the open" in by_id["fill"]
    assert ("Fidelity’s stated rule is that a buy stop is entered above the current price, so while the stock trades at or "
            "over the buy stop this order cannot be entered as written") in by_id["fill"]
    assert "is read again from that session’s one-minute bars" in by_id["record"]
    assert "replayed from daily bars alone" not in text and "a fill-day low under the stop is uncertain" not in text


def test_the_walkthroughs_source_lines_agree_with_the_modules_marks():
    text = captions()
    # the admission rule is this build's, the down-day allowance a later statement of his,
    # and the base's ratios have no primary source: knowledge/consolidation-quality.md
    assert "the admission rule P (this build’s, November 2026)" in text
    assert "later Bonde (2LYNCH, 2020)" in text and "dry volume B (2016)" not in text and "one webinar port" not in text
    contract = (ROOT / "knowledge" / "consolidation-quality.md").read_text()
    assert "| At most one 4% down day | LATER BONDE, 2020-12-08" in contract and "| Giveback | DERIVED" in contract
    assert "H V; RE B; the long-base volume rule E" in text and "H and RE V" not in text
    assert "entering the next session is a route he describes and this build selected" in text
    assert "the entry-day low is his stop B" in text
    assert "the scaling, firing the '" in text and "on a single day, the two red ratio rules, the sizes and A+ only on yellow P" in text


# ------------------------------------------------- the help terms, the page ----
def test_the_help_terms_say_what_discovery_the_light_and_a_trigger_are():
    discovery = term("discovery")
    assert "Either can admit a candidate" not in READING
    assert "Either can find a candidate" in discovery and "separate admission rule" in discovery
    assert "a candidate only the Dollar scan found also needs a range-expansion, higher-volume day" in discovery
    market = term("market")
    assert "GREEN permits normal model sizing, YELLOW reduces it" not in READING
    assert "Three red rules and two yellow rules decide the regime, and GREEN needs all five quiet" in market
    assert "the count thresholds are scaled to the number of stocks measured, the ratios are not" in market
    assert "GREEN sizes A+ and A bursts in full, YELLOW halves the size and admits A+ bursts only, and RED refuses new longs" in market
    assert "the record does not establish that it improves outcomes" in market
    assert "cannot create a ticket or reopen an expired window" in market, "tools/reading_cases.mjs reads this phrase"
    trigger = term("trigger")
    assert "it can fill only from the trigger up to the limit" in trigger
    assert "Fidelity’s stated rule is that a buy stop is entered above the current price" in trigger
    assert "whether Fidelity accepts it before the open is unconfirmed" in trigger
    # the broker note is where both halves of that sentence are sourced
    note = prose(ROOT / "knowledge" / "broker-fidelity.md")
    assert "must be entered at a price above the current market price" in note
    assert "The price Fidelity compares a buy stop against before the open" in note


def test_the_evidence_paragraph_and_the_record_header_say_whose_evidence_and_what_a_fill_assumes():
    evidence = PAGE.split('id="walkthrough-evidence"', 1)[1].split("</details>", 1)[0]
    assert "Third-party evidence, none of it SpicyStock’s own" in evidence
    assert "The edge, if there is one, sits in the low-of-day stop" not in PAGE
    assert "A separate backtest of a different setup" in evidence and "has not been measured on bursts" in evidence
    assert "SpicyStock’s own record does not establish an edge" in evidence
    assert "n = 10,947" in evidence and "gates remove the losing half" in evidence, "tests/test_docs.py holds both"
    header = PAGE.split('id="record-h2"', 1)[1].split("</header>", 1)[0]
    assert ("A model fill at the open assumes the buy stop-limit was already resting at the broker before the open; "
            "for a burst ticket, whose buy stop is the last close, Fidelity’s acceptance of that order is unconfirmed") in header
    # a burst ticket's buy stop is its signal close: plan.burst_limit()
    made = plan.burst_limit(19.28, 18.79, 19.38)
    assert made["trigger"] == 19.28 and record.KNOWN_FILL == "open_inside_zone"
