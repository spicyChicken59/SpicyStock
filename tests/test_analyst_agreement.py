"""The outside analyst's files agree with each other and with what the code and the page say.

Each test holds one place where two documents name the same thing: the price-state shares in the
analyst prompt and in the Fidelity protocol against the broker note's dated table, the ledger's
column names, the session's capability list, the page's view names and the guarded dispatch's slot.
"""
from __future__ import annotations

import re
from pathlib import Path

from src import delivery

ROOT = Path(__file__).resolve().parents[1]
PROMPT = (ROOT / "docs" / "analyst" / "prompt.md").read_text()
BOOTSTRAP = (ROOT / "docs" / "analyst" / "bootstrap.md").read_text()
BROKER = ROOT / "knowledge" / "broker-fidelity.md"
PROTOCOL = ROOT / "knowledge" / "broker-fidelity-protocol.md"
LEDGER = (ROOT / "knowledge" / "trade-ledger.md").read_text()


def table(text: str, first_cell: str) -> list[list[str]]:
    """The body rows of the one markdown table in ``text`` whose header starts with ``first_cell``."""
    rows, inside = [], False
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.strip().startswith("|") else None
        if cells is None:
            if inside:
                break
            continue
        if not inside:
            inside = cells[0] == first_cell
            continue
        if not set(cells[0]) <= {"-", ":"}:
            rows.append(cells)
    assert rows, f"no table whose header starts with {first_cell!r}"
    return rows


def section(text: str, start: str, end: str) -> str:
    return text[text.index(start):text.index(end)]


def test_the_state_table_is_the_range_table_regrouped_by_the_crossings_it_names():
    """The broker note's price-range table and its price-state table count the same tickets. They differ
    only where a stop sits at or over the skip line, and the note names both crossings; the arithmetic
    between the two tables is held here."""
    text = BROKER.read_text()
    ranges = {row[0]: int(row[1].replace(",", "")) for row in table(text, "first-day open")}
    states = {row[0]: int(row[1].replace(",", "")) for row in table(text, "price state")}
    total = sum(ranges.values())
    assert sum(states.values()) == total
    over_skip_at_stop = int(re.search(r"`below_stop` \(([\d,]+) of the tickets\)", text).group(1).replace(",", ""))
    under_skip_at_stop = int(re.search(r"at or under the stop \(([\d,]+)\)", text).group(1).replace(",", ""))
    under_skip = ranges["under the skip line (2% under the close)"]
    skip_to_trigger = ranges["at or over the skip line, under the buy stop"]
    assert states["`below_stop`"] == over_skip_at_stop + under_skip_at_stop
    assert states["`below_entry_floor`"] == under_skip - under_skip_at_stop
    assert states["`below_trigger`"] == skip_to_trigger - over_skip_at_stop
    assert states["`within_published_band`"] == (ranges["exactly at the buy stop"]
                                                 + ranges["over the buy stop, at or under the limit"])
    assert states["`above_limit`"] == ranges["over the limit, at or under the day-2 line (4% over the close)"]
    assert states["`above_day2_extension`"] == ranges["over the day-2 line"]
    for row in table(text, "price state"):
        assert row[2] == f"{100 * int(row[1].replace(',', '')) / total:.1f}%", row


def test_the_prompt_and_the_protocol_quote_each_states_share_from_the_state_table():
    states = {row[0]: row[2] for row in table(BROKER.read_text(), "price state")}
    pct = lambda share: float(share.rstrip("%"))
    under = f"{pct(states['`below_stop`']) + pct(states['`below_entry_floor`']):.1f}%"
    prompt = {row[0]: row[-1] for row in table(section(PROMPT, "### 10.4", "### 10.5"), "State")}
    assert prompt["`below_stop`, `below_entry_floor`"] == f"{under} ({states['`below_stop`']} and {states['`below_entry_floor`']})"
    protocol = {row[0]: row[-1] for row in table(PROTOCOL.read_text(), "price state")}
    assert protocol["`below_stop`, `below_entry_floor`"] == (
        f"{under} ({states['`below_stop`']} `below_stop`, {states['`below_entry_floor`']} `below_entry_floor`)")
    for state in ("`below_trigger`", "`above_limit`", "`above_day2_extension`"):
        assert prompt[state] == states[state], state
        assert protocol[state] == states[state], state
    assert prompt["`within_published_band`"].startswith(states["`within_published_band`"])
    assert protocol["`within_published_band`"].startswith(states["`within_published_band`"])
    # the prompt says its column is by state, and it is
    assert "how often the first day opened in that state" in section(PROMPT, "### 10.4", "### 10.5")


def test_every_ledger_column_the_prompt_names_is_a_column_of_the_ledger_note():
    """Section 14 tells the analyst to use the ledger note's words when the two differ, so every
    identity column it names must be one the note defines."""
    named = set(re.findall(r"`(ss_[a-z0-9_]+)`", section(PROMPT, "## 14. The ledger", "## 15.")))
    defined = set(re.findall(r"`(ss_[a-z0-9_]+)`", LEDGER))
    assert named and named <= defined, sorted(named - defined)


def test_the_session_capabilities_are_counted_and_listed_alike():
    start = PROMPT.index("### 1.3")
    caps = PROMPT[start:PROMPT.index("\n#", start + 1)]
    rows = [row[0] for row in table(caps, "Capability")]
    words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight"}
    assert f"state which of the {words[len(rows)]} you can do" in " ".join(caps.split())
    listed = " ".join(BOOTSTRAP.split())
    for phrase in ("fetch pages", "search the web", "read images", "run code", "remember", "run on a schedule"):
        assert phrase in listed, phrase
    assert any("search" in row.lower() for row in rows)


def test_the_views_the_prompt_names_are_the_pages_own():
    html = (ROOT / "docs" / "index.html").read_text()
    sentence = re.search(r"same record: ([^.]+)\. It needs", " ".join(PROMPT.split())).group(1)
    for view in [v.strip() for v in re.split(r",| and ", sentence) if v.strip()]:
        assert view in html, view


def test_env_example_names_the_guarded_dispatchs_primary_slot():
    slot = delivery.EVENING_PRIMARY_ET
    words = f"{slot.hour % 12 or 12}:{slot.minute:02d} {'PM' if slot.hour >= 12 else 'AM'} ET"
    text = " ".join((ROOT / ".env.example").read_text().replace("#", " ").split())
    assert f"only after its primary slot ({words}) has passed" in text
    assert f"one that fires before {words} does nothing" in text
