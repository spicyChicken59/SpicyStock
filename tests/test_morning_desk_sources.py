"""The Morning desk reads two published files and says what a price beside a
burst's trigger means for its buy stop.

The browser behaviour is held by the page smoke (`tools/morning_service_reader_cases.mjs`
and `tools/observation_cases.mjs`). What is held here is what a browser suite
cannot see: that the page's two state lists are the collector's own states on
each side of the trigger, that its Fidelity sentence is the broker note's, and
that the operations documents state the rule the page now follows and not the
one it replaced."""
import json
import re
from pathlib import Path

from src import morning

ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / "docs" / "app-observations.js").read_text(encoding="utf-8")
#: publications whose admitted burst tickets the sweep below prices
PUBLICATIONS = ("tests/fixtures/morning/full-publication.json", "tests/fixtures/cash-preview/publication-multiple.json")
#: one cent, the sweep's step, and how far past each end of the levels it runs
CENT = 0.01
MARGIN_CENTS = 50


def prose(path):
    return " ".join(path.read_text(encoding="utf-8").split())


def page_list(name):
    listed = re.search(r"\b%s = \[([^\]]*)\]" % name, PAGE)
    assert listed, f"the page no longer names {name}"
    return re.findall(r"'(\w+)'", listed.group(1))


def burst_levels():
    found = []
    for relative in PUBLICATIONS:
        data = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        found += [(relative, row["ticker"], row["levels"]) for row in morning.admitted_rows(data) if row["kind"] == "burst"]
    return found


def sweep(levels):
    """Every cent from under the stop to past the day-2 line, with its state."""
    low = min(levels["stop"], levels["entry_low"])
    high = max(levels["limit"], levels["day2_spent_above"] or levels["limit"])
    cents = range(round(low / CENT) - MARGIN_CENTS, round(high / CENT) + MARGIN_CENTS + 1)
    return [(round(c * CENT, 2), morning.price_state(round(c * CENT, 2), levels, "recent")) for c in cents]


def test_the_fixtures_carry_burst_tickets_to_sweep():
    levels = burst_levels()
    assert {relative for relative, _, _ in levels} == set(PUBLICATIONS), levels
    for _, _, one in levels:
        # a burst ticket's own geometry, which the words below lean on
        assert one["stop"] < one["entry_low"] < one["trigger"] < one["limit"] <= one["day2_spent_above"], one


def test_the_pages_over_and_under_lists_are_the_collectors_states_on_each_side_of_the_trigger():
    """`price_state()` orders its states; the page says "at or over the trigger"
    for some and "under the trigger" for one. Swept a cent at a time over real
    burst levels: every state the collector gives a price at or over the
    trigger is on the page's over list and none of them is given under it; the
    page's under list is given only between the entry floor and the trigger."""
    over, under = page_list("OVER_TRIGGER"), page_list("UNDER_TRIGGER")
    assert over and under and not set(over) & set(under)
    seen_over, seen_under = set(), set()
    for relative, ticker, levels in burst_levels():
        for price, state in sweep(levels):
            where = f"{relative} {ticker} {price} {state}"
            if price >= levels["trigger"]:
                assert state in over, where
                seen_over.add(state)
            else:
                assert state not in over, where
                if state in under:
                    assert levels["entry_low"] <= price, where
                    seen_under.add(state)
                else:
                    # under the trigger and without words: the skip line or the stop decides there
                    assert state in ("below_entry_floor", "below_stop"), where
    # the sweep reached every state the page names, so a list entry the
    # collector never gives would fail here and not pass unseen
    assert seen_over == set(over) and seen_under == set(under), (seen_over, seen_under)


def test_an_unread_price_gets_no_buy_stop_words():
    """The collector gives `unknown` for a price that is not recent; the page
    names it on neither list."""
    for _, _, levels in burst_levels():
        assert morning.price_state(levels["trigger"], levels, "stale") == "unknown"
    assert "unknown" not in page_list("OVER_TRIGGER") + page_list("UNDER_TRIGGER")


def test_the_pages_state_lists_are_states_its_own_validator_accepts():
    accepted = re.search(r"\['trade', 'ask'\]\.every\(key => \[([^\]]*)\]\.includes\(row\.price_checks\[key\]\)\)", PAGE)
    assert accepted, "the page's price-check membership list moved"
    known = re.findall(r"'(\w+)'", accepted.group(1))
    assert set(page_list("OVER_TRIGGER") + page_list("UNDER_TRIGGER")) <= set(known)


def test_the_buy_stop_sentence_is_the_broker_notes_rule_and_only_for_a_burst_row():
    note = prose(ROOT / "knowledge" / "broker-fidelity.md")
    # the note's words for the rule, and the page's sentence quoting them
    assert "buy stop loss and buy stop limit orders must be entered at a price above the current market price" in note
    assert "A burst ticket's trigger IS the burst session's close" in note
    assert "Fidelity’s words say a buy stop must be entered above the current market price" in PAGE
    # words appended to the comparison line, for a burst row alone, before the sentence that keeps it no instruction
    assert "(row.kind === 'burst' ? buyStopWords(checks) : '') + ' These dated comparisons are not an entry or cancellation instruction.'" in PAGE
    assert PAGE.count("buyStopWords(") == 2, "one definition and one call"


def test_the_page_names_both_published_files_and_keeps_an_invalid_endpoint_silent():
    """With a configured host the page reads the host and the same-origin static
    file; with none, the static file alone; and an invalid endpoint still makes
    no request, because the refusal is thrown before any file is read."""
    listed = re.search(r"const sources = \(\) => endpoint\.service\s*\? \[(.*?)\]\s*: \[(.*?)\];", PAGE, re.S)
    assert listed, "sources() moved"
    both, alone = (re.findall(r"id: '(\w+)', url: ([^,]+), mode: '([\w-]+)'", part) for part in listed.groups())
    assert both == [("host", "endpoint.url", "cors"), ("static", "'morning.json'", "same-origin")]
    assert alone == [("static", "'morning.json'", "same-origin")]
    read = PAGE[PAGE.index("async function reload("):PAGE.index("function reset(")]
    assert read.index("if (endpoint.error) throw Error(endpoint.error);") < read.index("sources().map(")
    # each file is held to the loaded publication by the one validator
    assert read.count("validate(result.parsed)") == 1 and "validate(" not in PAGE[PAGE.index("async function readSource("):PAGE.index("function unverified(")]


def test_the_operations_documents_state_the_two_file_rule_and_not_the_retired_one():
    runbook = prose(ROOT / "docs" / "operations" / "morning-railway.md")
    deployment = prose(ROOT / "docs" / "operations" / "morning-deployment.md")
    for text in (runbook, deployment):
        assert "static fallback" not in text
        assert "do not silently redirect it to an older static receipt" not in text
        assert "A failed dynamic read shows nothing of its own" in text
    assert "reads the same-origin static `morning.json` the morning workflow commits, on every read" in runbook
    assert "shows the newest verified receipt (the host's on a tie), naming which file it came from" in runbook
    assert "offered only when the host's answer shows it does not hold the loaded publication" in runbook
    assert "never when it is older than a receipt already verified" in deployment
    assert "the read is refused and the restriction stays" in deployment
    # and the page's own words for the same rule
    assert "Reload reads the morning host’s receipt and the static morning file the morning workflow publishes, shows the newest one verified for this record" in PAGE
    assert "if (endpoint.service && hostHolds !== false) return null;" in PAGE


def test_the_readme_states_the_two_file_rule():
    """README is swept with the other documents: it must stop saying the page
    has no static file beside a configured host, and say what it reads."""
    readme = prose(ROOT / "README.md")
    assert "There is no automatic static-file fallback" not in readme
    assert "the page reads the same-origin static `morning.json` the morning workflow commits, on every read" in readme
    assert "the newest verified receipt is shown (the host's on a tie)" in readme
    assert "the offer is made only when that host's answer shows it does not hold the loaded publication" in readme
