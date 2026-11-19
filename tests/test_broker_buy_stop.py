"""Fidelity's buy-stop rule beside a burst ticket, and the band a ticket fills in.

A burst ticket's buy stop is the burst session's close, and Fidelity's stated
rule (knowledge/broker-fidelity.md, item 2: read off a search excerpt) is that
a buy stop is entered above the current market price. One text says so,
labelled as Fidelity's rule and SpicyStock's advice, in three equal copies --
``report.BROKER_BUY_STOP``, ``docs/app.js`` and ``docs/app-handoff-ui.js`` --
printed directly after the part-fill text beside a BURST ticket's order and
never beside a setting-up ticket's, whose trigger sits above its last close.
The mail's facts line names the buy stop, the limit and the skip line as three
prices: it was one "buy zone" whose lower part the order cannot buy.

The page's placement is held in the browser by tools/buy_stop_cases.mjs and
the smoke's notePlaces(); this file holds the text, the code it rests on and
the mail.
"""
from __future__ import annotations

import datetime as dt
import re
from html.parser import HTMLParser
from pathlib import Path

from src import plan, record, report
from src.plan import Account
from src.report import build, digest_html
from tests.test_docs import _js_code
from tests.test_report import ORDER_LINE, _burst, _miss, _night, _plan, _run

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "docs" / "app.js").read_text(encoding="utf-8")
HANDOFF = (ROOT / "docs" / "app-handoff-ui.js").read_text(encoding="utf-8")
NOTE = (ROOT / "knowledge" / "broker-fidelity.md").read_text(encoding="utf-8")

#: a burst bar whose stop, skip line, buy stop and limit are four prices
BAR = dict(ticker="XYZ", close=20.00, low=19.85, high=20.10, open_=19.90, prev_close=19.00, gain_pct=5.26)
QUIET = {"top": [], "also_quiet": [], "counts": {"top": 0, "also_quiet": 0}}
ALERT = {"top": [{"ticker": "WCH", "setups": ["TI65"], "trigger": 20.05, "stop": 18.9, "shares": 40,
                  "plan": {"order_line": "Buy 40 WCH stop 20.05 limit 20.30; OTO sell stop 18.90"}}],
         "also_quiet": [], "counts": {"top": 1, "also_quiet": 0}}


def _real_plan(**over) -> dict:
    return plan.burst_plan(**{**BAR, "account": Account(), **over})


# --- the text and what it rests on ---------------------------------------------------

def test_the_buy_stop_text_keeps_its_two_labels_and_says_no_number():
    rule, advice = report.BROKER_BUY_STOP.split(" SpicyStock’s advice: ")
    assert rule == ("Fidelity’s rule: a buy stop or buy stop-limit order must be entered at a stop price "
                    "above the current market price."), rule
    for claim in ("a burst ticket’s buy stop is the burst day’s close",
                  "entered as written only while the stock trades under that price",
                  "which price Fidelity compares it with before the open (the close or a pre-market quote) is unconfirmed",
                  "Once the stock trades at or over the buy stop the ticket cannot be entered as written",
                  "SpicyStock offers no other order",
                  "the model’s ‘filled at the open’ assumes the order was already resting before the open"):
        assert claim in advice, claim
    # a number here would be a rule's, and the text quotes none; plain words
    assert not re.search(r"\d", report.BROKER_BUY_STOP) and "—" not in report.BROKER_BUY_STOP
    assert report.BROKER_BUY_STOP != report.BROKER_PART_FILL


def test_the_text_says_what_the_plan_and_the_model_do():
    """Each claim of the advice, held to the code it is about."""
    burst = _real_plan()
    # the buy stop IS the burst close, and it is the order's stop price
    assert burst["entry_ref"] == BAR["close"] == burst["order_json"]["stop_price"]
    assert burst["skip_if_open_below"] == burst["entry_low"] < burst["entry_ref"] < burst["limit"] == burst["entry_high"]
    # a close with a fraction of a cent: the buy stop is that close to the cent
    odd = _real_plan(close=62.105, low=61.60, high=62.30, open_=61.70, prev_close=59.0, gain_pct=5.26)
    assert odd["entry_ref"] == odd["order_json"]["stop_price"] == 62.1 and abs(odd["entry_ref"] - 62.105) <= 0.005
    # the plan writes one order type and no other: a stop-limit with its stop riding on it
    assert burst["order_json"]["order_type"] == "stop_limit" and burst["order_json"]["conditional"] == plan.OTO
    assert "There is no plain-limit fallback" in plan.fidelity_orders.__doc__
    # the model books an open at or over the buy stop and at or under the limit as filled at that open
    pick = {"kind": "burst", "entry_ref": burst["entry_ref"], "entry_high": burst["entry_high"],
            "entry_low": burst["entry_low"], "stop": burst["stop"]}
    at = burst["entry_ref"]
    for open_ in (at, round((at + burst["limit"]) / 2, 2), burst["limit"]):
        status, price, note, reason = record.fill(pick, {"o": open_, "h": open_ + 0.3, "l": open_ - 0.01, "c": open_})
        assert (status, price, reason) == ("filled", open_, None) and note.startswith("filled at the open"), (open_, status, note)
    # and an open under it as no known fill
    status, price, _, reason = record.fill(pick, {"o": at - 0.05, "h": at + 0.3, "l": at - 0.06, "c": at})
    assert status == record.UNCERTAIN and price is None and reason == "trigger_timing"
    # an anticipation ticket's trigger sits above its last close: the text is not about it
    coil = plan.anticipation_plan(ticker="ABC", close=5.00, box_high=5.10, box_low=4.90,
                                  lows_last3=[5.00, 5.02, 5.05], account=Account())
    assert coil["trigger"] > 5.00 and coil["order_json"]["stop_price"] == coil["trigger"]
    # the plan's own words stay broker-neutral: provenance replays them
    for term in burst["order_terms"] + [burst["pre_open_check"], burst["order_line"]]:
        assert "Fidelity" not in term, term


def test_the_broker_note_carries_the_rule_the_text_quotes():
    """The text's first sentence is the note's item 2, in Fidelity's words as
    the note read them, and the note labels the pre-open comparison unconfirmed."""
    flat = " ".join(NOTE.split())
    assert "**A buy stop must be priced above the current market.**" in flat
    assert "buy stop loss and buy stop limit orders must be entered at a price above the current market price" in flat
    assert "Unconfirmed: which price Fidelity compares the stop with before the open, the last close or a pre-market quote" in flat
    assert "the ticket cannot be entered as written" in flat
    assert "SpicyStock's ticket has no plain-limit fallback" in flat


def test_the_mail_the_page_and_the_handoff_print_the_buy_stop_rule_as_one_text():
    """Defined once in each file and equal to the mail's. The page prints it
    through one helper, buyStopNote(), called once under the Broker notes
    disclosure (the Burst's card and the decision summary's entry) and once
    at each other place a burst ticket's order is printed: the order block,
    the recorded ticket, the comparison, the tickets sheet, the model exits,
    a saved setup's archived order and an archived original's status. The
    handoff prints it in its readback, hidden unless the draft is a burst's."""
    calls = re.compile(r"(?<![\w.])buyStopNote\(\)")
    for name, source in (("app.js", APP), ("app-handoff-ui.js", HANDOFF)):
        code = _js_code(source)
        assert len(re.findall(r"(?<![\w.])BROKER_BUY_STOP\s*=", code)) == 1, name
        assert re.findall(r"const BROKER_BUY_STOP = '([^']+)';", code) == [report.BROKER_BUY_STOP], name
        # the definition and its one use: nothing else reads the name
        assert len(re.findall(r"(?<![\w.])BROKER_BUY_STOP\b", code)) == 2, name
        if name == "app.js":
            assert len(re.findall(r"const buyStopNote = \(\) => el\('p', \{ [^}]*'data-broker-buy-stop': '', text: BROKER_BUY_STOP \}\);", code)) == 1
            assert len(calls.findall(code)) == 8, calls.findall(code)
            # one disclosure helper, holding one of each note, used at the card and the entry
            fold = re.findall(r"const brokerNotesFold = \(\) => el\('details', \{[^}]*'data-broker-notes': ''[^}]*\}, \[(.*?)\n  \]\);", code, re.S)
            assert len(fold) == 1 and fold[0].count("partFillNote()") == 1 and fold[0].count("buyStopNote()") == 1, fold
            assert fold[0].index("partFillNote()") < fold[0].index("buyStopNote()")
            assert len(re.findall(r"(?<![\w.])brokerNotesFold\(\)", code)) == 2, name
        else:
            assert len(re.findall(r"node\('p', \{ class: 'sc-hint', 'data-broker-buy-stop': '', hidden: '' \}, BROKER_BUY_STOP\)", code)) == 1, name
            # shown for a bursts-stage draft only, hidden for every other record
            assert "host.querySelector('[data-broker-buy-stop]').hidden = noDraft || item.plan.stage !== 'bursts';" in code
            assert "host.querySelector('[data-broker-buy-stop]').hidden = true;" in code


def test_every_page_site_that_prints_the_buy_stop_note_asks_the_stage_first():
    """A setting-up ticket never carries it: each call outside the disclosure
    helper and the two burst-only places (the Burst card's disclosure, the
    tickets sheet, which lists burst tickets alone) sits behind a test of the
    stage the page already knows."""
    code = _js_code(APP)
    guarded = [
        "if (burst) wrap.appendChild(buyStopNote());",                                         # recorded ticket, order block
        "if ([a, b].some((c) => c.stage === 'bursts' && c.status === 'ticket' && text((c.plan || {}).order_line))) wrap.appendChild(buyStopNote());",
        "snap.status === 'ticket' && item.kind === 'burst' ? buyStopNote() : null",
        "if (c.stage === 'bursts') nodes.push(buyStopNote());",
        "if (c.stage === 'bursts') kids.push(buyStopNote());",
        "if (rows.length) { sheet.appendChild(partFillNote()); sheet.appendChild(buyStopNote()); }",
    ]
    counts = [code.count(g) for g in guarded]
    assert counts == [2, 1, 1, 1, 1, 1], dict(zip(guarded, counts))
    # the callers hand the stage over, and the decision summary folds a burst's notes and keeps a coil's one note open
    assert "kids.push(recordedTicket(plan, available, c.stage === 'bursts'));" in code
    assert "kids.push(orderBlock(plan, hint, withheld, c.stage === 'bursts'));" in code
    assert "appendChild(c.stage === 'bursts' ? brokerNotesFold() : partFillNote());" in code
    # the setting-up action bar prints the part-fill note alone
    bar = code[code.index("function actionArea(c)"):code.index("function disclosure(id, title, hint, kids)")]
    assert "partFillNote('ss-action__broker')" in bar and "buyStopNote" not in bar and "brokerNotesFold" not in bar


# --- the mail ------------------------------------------------------------------------

class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text: list[str] = []

    def handle_data(self, data: str) -> None:
        self.text.append(data)


def _rendered(markup: str) -> str:
    parser = _Text()
    parser.feed(markup)
    return " ".join(parser.text)


class _Paragraphs(HTMLParser):
    """The digest's elements in document order as (tag, style, depth, text)."""

    def __init__(self, html: str) -> None:
        super().__init__()
        self.items: list[list] = []
        self.stack: list[int] = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag in ("br", "img", "hr", "meta"):
            return
        self.items.append([tag, dict(attrs).get("style") or "", len(self.stack), ""])
        self.stack.append(len(self.items) - 1)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.items[self.stack[i]][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        for i in self.stack:
            self.items[i][3] += data


def test_the_mails_facts_name_the_buy_stop_the_limit_and_the_skip_line_as_three_prices():
    """Each price follows its own label, read off its own field of a plan the
    planner wrote: the buy stop is entry_ref, the limit entry_high and the skip
    line entry_low. No "buy zone" from the skip line to the limit."""
    p = _real_plan()
    assert len({p["entry_low"], p["entry_ref"], p["entry_high"], p["stop"], p["day2_spent_above"]}) == 5
    html = report._trade_block({"ticker": "XYZ", "grade": "A+", "score": 9.1, "summary": "XYZ: a burst.", "plan": p}, None)
    facts = (f"Buy stop {p['entry_ref']:.2f} · Limit {p['entry_high']:.2f} · Skip an open under {p['entry_low']:.2f} · "
             f"Stop {p['stop']:.2f} · Shares {p['shares']} · Too extended over {p['day2_spent_above']:.2f} · Position ")
    assert facts in _rendered(html), _rendered(html)
    assert "Buy zone" not in html and f"{p['entry_low']:.2f}–{p['entry_high']:.2f}" not in html.split("<pre")[0]
    # the skip line is said only when the plan carries one; the buy stop and the limit never print None
    bare = {"ticker": "XYZ", "grade": "A+", "score": 9.1, "summary": "XYZ: a burst.", "plan": {"stop": 19.2, "shares": 3}}
    line = _rendered(report._trade_block(bare, None))
    assert "Buy stop — · Limit — · Stop 19.20 · Shares 3" in line and "Skip an open under" not in line and "None" not in line


def test_the_mail_prints_the_buy_stop_rule_once_after_the_burst_orders_and_never_after_the_alerts():
    text = _rendered(digest_html(build(**_night())))
    assert text.count(report.BROKER_BUY_STOP) == 1, text
    at = text.index(report.BROKER_BUY_STOP)
    # after the trade's order and the part-fill rule, before the budget line, the open plans and the alerts
    assert text.index(ORDER_LINE) < text.index(report.BROKER_PART_FILL) < at < text.index("Model allocation") < text.index("Open model plans"), text
    assert at < text.index("Alerts — set these before the open"), text
    # the alerts' own block ends with the part-fill rule alone
    assert text.count(report.BROKER_PART_FILL) == 2 and text.rindex(report.BROKER_PART_FILL) > text.index("Buy 40 WCH") > at, text
    # no burst order, an alert with one: the part-fill rule follows the alert and the buy-stop rule is nowhere
    text = _rendered(digest_html(build(**_night(trades=[], watchlist=ALERT))))
    assert text.count(report.BROKER_PART_FILL) == 1 and report.BROKER_BUY_STOP not in text, text
    # nothing printed at all on a night with no order
    assert report.BROKER_BUY_STOP not in _rendered(digest_html(build(**_night(trades=[], watchlist=QUIET))))


def test_the_mail_prints_the_buy_stop_rule_only_beside_a_burst_order_it_printed():
    # a trade whose plan carries no order line prints no ticket, so neither broker sentence
    text = _rendered(digest_html(build(**_night(bursts=[_burst(plan={**_plan(), "order_line": None}), _miss()], watchlist=QUIET))))
    assert "Buy stop 12.34" in text and report.BROKER_BUY_STOP not in text and report.BROKER_PART_FILL not in text, text
    # two trades, one with an order: one sentence, after both cards
    mixed = _night(bursts=[_burst("XYZ"), _burst("DEF", plan={**_plan(), "order_line": None})], trades=["XYZ", "DEF"], watchlist=QUIET)
    text = _rendered(digest_html(build(**mixed)))
    assert text.count(report.BROKER_BUY_STOP) == 1 and text.index("DEF") < text.index(report.BROKER_BUY_STOP), text
    # two trades, each with an order: still one sentence, after the second card's order, never one a card
    both = _night(bursts=[_burst("XYZ"), _burst("DEF")], trades=["XYZ", "DEF"], watchlist=QUIET)
    text = _rendered(digest_html(build(**both)))
    assert text.count(ORDER_LINE) == 2 and text.count(report.BROKER_BUY_STOP) == 1 and text.count(report.BROKER_PART_FILL) == 1, text
    assert text.rindex(ORDER_LINE) < text.index(report.BROKER_PART_FILL) < text.index(report.BROKER_BUY_STOP), text
    # a closed night carries the standing burst tickets verbatim, and the rule with them
    closed = _night(run=_run(session_state="closed", status="closed"), watchlist=QUIET)
    text = _rendered(digest_html(build(**closed)))
    assert ORDER_LINE in text and text.count(report.BROKER_BUY_STOP) == 1 and text.index(ORDER_LINE) < text.index(report.BROKER_BUY_STOP), text


def test_the_buy_stop_rule_is_a_paragraph_of_the_digests_column_directly_after_the_part_fill_rule():
    """Where a reader sees it: a muted paragraph of the column itself, the
    element directly after the part-fill paragraph, with nothing inside it and
    no wrapper around it -- and never inside a card, its order or its terms."""
    html = digest_html(build(**_night()))
    items = _Paragraphs(html).items
    notes = [i for i, it in enumerate(items) if it[0] == "p" and it[3] == report.BROKER_BUY_STOP]
    assert len(notes) == 1, [it[:3] for it in items if report.BROKER_BUY_STOP in it[3]]
    i = notes[0]
    heading = next(it for it in items if it[0] == "h2" and it[3] == "Next-session orders")
    before = items[i - 1]
    assert before[0] == "p" and before[3] == report.BROKER_PART_FILL and before[2] == items[i][2] == heading[2], (before[:3], items[i][:3], heading[:3])
    assert items[i][1] == before[1] == report._S_MUTED
    # nothing but the page and the column contains it: no card, no <pre>, no other paragraph
    holders = [it[0] for it in items if report.BROKER_BUY_STOP in it[3]]
    assert sorted(holders) == ["div", "p"], holders
    for it in items:
        if it[0] == "pre" or (it[0] == "div" and ORDER_LINE in it[3] and it[2] > heading[2] - 1 and "Next-session orders" not in it[3]):
            assert "Fidelity" not in it[3], it[3][:120]


def test_a_real_planned_burst_reaches_the_digest_with_its_three_prices_and_both_rules():
    """End to end through build(): a plan burst_plan() wrote, its order line
    in the card, the facts line off its own fields, and the two broker rules
    after the card in their order."""
    p = _real_plan()
    night = _night(bursts=[_burst("XYZ", close=BAR["close"], plan=p), _miss()], trades=["XYZ"], watchlist=QUIET)
    text = _rendered(digest_html(build(**night)))
    assert p["order_line"] in text and f"Buy stop {p['entry_ref']:.2f} · Limit {p['limit']:.2f} · Skip an open under {p['entry_low']:.2f}" in text, text
    assert text.index(p["order_line"]) < text.index(report.BROKER_PART_FILL) < text.index(report.BROKER_BUY_STOP), text
    # the ticket's own terms are printed and carry neither rule
    assert p["order_terms"][0] in text and all("Fidelity" not in t for t in p["order_terms"])
    # the dated schedule's day-1 line still reads as the plan wrote it: provenance replays it
    entry = plan.dated_schedule(p, dt.date(2026, 9, 10))[0]["instruction"]
    assert f"inside {plan._usd(p['entry_low'])}–{plan._usd(p['limit'])}" in entry and "Fidelity" not in entry
