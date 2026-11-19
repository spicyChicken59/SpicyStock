"""The notes written for the outside analyst say what the code does.

`knowledge/broker-fidelity.md`, `broker-fidelity-protocol.md`,
`trade-ledger.md`, `event-coverage.md` and `docs/scorecard-contract.md` quote
numbers, field names, state words and rules that live in modules. Each test
reads the quoted thing off the module that owns it, so a changed constant or a
mistyped number in a note is a failure and not a stale sentence. Dated counts
measured over the publication history (the first-day opens, the session
counts) are held only to their own arithmetic: no test here reads the rolling
record."""
from __future__ import annotations

import json
import re
from pathlib import Path

from src import (earnings_risk, event_risk, issuer_evidence, morning, plan, record, universe)
from tools import private_results

ROOT = Path(__file__).resolve().parent.parent


def prose(path: Path) -> str:
    """The file with its whitespace collapsed, so a sentence is matched as a
    sentence and not as the width it was wrapped at."""
    return re.sub(r"\s+", " ", path.read_text())


BROKER = prose(ROOT / "knowledge" / "broker-fidelity.md")
PROTOCOL = prose(ROOT / "knowledge" / "broker-fidelity-protocol.md")
LEDGER = prose(ROOT / "knowledge" / "trade-ledger.md")
EVENTS = prose(ROOT / "knowledge" / "event-coverage.md")
CONTRACT = prose(ROOT / "docs" / "scorecard-contract.md")
NUMBER_WORDS = {3: "three", 5: "five"}
ACCOUNT = plan.Account(equity=30_000.0, risk_pct=0.5, max_position_pct=25.0, max_open_positions=4)


def table_rows(path: Path, first_cell: str) -> list[list[str]]:
    """The body rows of the one markdown table whose header starts with ``first_cell``."""
    rows, inside = [], False
    for line in path.read_text().splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")] if line.strip().startswith("|") else None
        if cells is None:
            if inside:
                break
            continue
        if not inside:
            inside = cells[0] == first_cell
            continue
        if set(cells[0]) <= {"-", ":"}:
            continue
        rows.append(cells)
    assert rows, f"no table whose header starts with {first_cell!r} in {path.name}"
    return rows


def burst_plan(low: float):
    return plan.burst_plan(ticker="XMPL", close=100.0, low=low, high=100.4, open_=max(low, 96.0) + 0.1,
                           prev_close=95.0, gain_pct=5.26, account=ACCOUNT, size_multiplier=1.0, scan="4pct",
                           extension_pct=None)


def states(levels: dict, prices) -> list[str]:
    seen = []
    for price in prices:
        state = morning.price_state(price, levels, "recent")
        if state not in seen:
            seen.append(state)
    return seen


def grid(low: float, high: float) -> list[float]:
    cents = range(int(round(low * 100)), int(round(high * 100)) + 1)
    return [cent / 100 for cent in cents]


# ------------------------------------------------------- the broker note ---
def test_the_broker_note_keeps_the_items_other_texts_cite_by_number():
    """Code comments, the protocol and the page's notes cite the broker note's
    items by number and its unconfirmed list by its first words."""
    for heading in ("1. **The OTO's sell stop is released only when the buy fills in full.**",
                    "2. **A buy stop must be priced above the current market.**",
                    "6. **A Day buy with a Good 'til Canceled sell stop: the sources disagree.**",
                    "9. **Settled cash.**"):
        assert heading in BROKER, heading
    assert "buy stop loss and buy stop limit orders must be entered at a price above the current market price" in BROKER
    assert "A burst ticket's trigger IS the burst session's close" in BROKER
    assert "- The price Fidelity compares a buy stop against before the open." in BROKER
    # the sentence the note leans on: a burst's trigger is its close, an anticipation trigger sits above the close
    assert plan.burst_limit(100.0, 97.0, 100.5)["trigger"] == 100.0
    made = plan.anticipation_plan(ticker="XMPL", close=50.0, box_high=50.4, box_low=49.0, lows_last3=[49.3, 49.5, 49.6],
                                  account=ACCOUNT)
    assert made["trigger"] > made["close"] and made["action"] == "place_buy_stop"
    assert f"the larger of ${plan.TRIGGER_CENTS:.2f} and {100 * plan.TRIGGER_FRACTION:g}% of the close" in BROKER
    # the record's action words, and that neither is an order type
    assert plan.ORDER_ACTIONS == ("buy_at_open", "place_buy_stop")
    assert "`plan.action` `buy_at_open`, and for an anticipation ticket `place_buy_stop`" in BROKER
    assert burst_plan(97.0)["action"] == "buy_at_open" and burst_plan(97.0)["order_json"]["order_type"] == "stop_limit"
    assert "no plain-limit fallback" in plan.fidelity_orders.__doc__ and "has no plain-limit fallback" in BROKER


def test_the_broker_notes_cash_numbers_are_the_plans():
    assert (f"{NUMBER_WORDS[plan.GFV_LIMIT]} good faith violations in a {plan.GFV_WINDOW_MONTHS}-month period" in BROKER
            and f"for {plan.GFV_RESTRICTION_DAYS} calendar days" in BROKER)
    assert plan.SETTLEMENT_DAYS == 1 and "settle one business day after the trade (T+1)" in BROKER
    assert plan.PDT_RULE_DELETED_ON == "2026-06-04" and "count rule on 4 June 2026" in BROKER
    assert plan.PDT_PHASE_IN_ENDS == "2027-10-20" and "until 20 October 2027" in BROKER
    assert f"{NUMBER_WORDS[plan.GFV_LIMIT].capitalize()} good faith violations in {plan.GFV_WINDOW_MONTHS} months" in PROTOCOL
    assert f"for {plan.GFV_RESTRICTION_DAYS} calendar days to buying with settled cash only" in PROTOCOL
    cap = ACCOUNT.equity * ACCOUNT.max_position_pct / 100
    assert f"one ${ACCOUNT.equity:,.0f} account with a ${cap:,.0f} cap per name" in BROKER


def test_the_first_day_open_table_adds_up():
    """The measured table is a dated reading over the publication history; the
    test holds its arithmetic and every sentence that quotes it."""
    rows = table_rows(ROOT / "knowledge" / "broker-fidelity.md", "first-day open")
    counts = [int(row[1].replace(",", "")) for row in rows]
    total = sum(counts)
    assert f"{total:,} counterfactual tickets on 40 nights" in BROKER
    for row, count in zip(rows, counts):
        assert row[2] == f"{100 * count / total:.1f}%", row
    names = [row[0] for row in rows]
    at_stop, in_band = names.index("exactly at the buy stop"), names.index("over the buy stop, at or under the limit")
    at_or_over = sum(counts[at_stop:])
    assert f"at or over the buy stop on {at_or_over:,} of the {total:,}, {100 * at_or_over / total:.1f}%" in BROKER
    booked = counts[at_stop] + counts[in_band]
    assert (f"On the {booked:,} that opened at the buy stop or over it and at or under the limit "
            f"({100 * booked / total:.1f}%), the model books \"filled at the open\"") in BROKER
    # the protocol's burst table quotes the same shares, state by state
    burst = table_rows(ROOT / "knowledge" / "broker-fidelity-protocol.md", "price state")
    share = {row[0]: row[-1] for row in burst}
    pct = lambda count: f"{100 * count / total:.1f}%"
    assert share["`below_stop`, `below_entry_floor`"] == f"{pct(counts[0])} opened under the skip line"
    assert share["`below_trigger`"] == pct(counts[1])
    assert share["`within_published_band`"] == (f"{pct(booked)} ({pct(counts[at_stop])} exactly at the trigger, "
                                                f"{pct(counts[in_band])} over it)")
    assert share["`above_limit`"] == pct(counts[4]) and share["`above_day2_extension`"] == pct(counts[5])
    assert f"13,599 counterfactual burst tickets" in PROTOCOL and total == 13_599
    # what the model books in each of those opens: record.fill()
    pick = {"ticker": "XMPL", "date": "2026-01-05", "kind": "burst", "entry_ref": 100.0, "entry_low": 98.0,
            "entry_high": 101.6, "stop": 97.6, "shares": 10}
    bar = lambda o, h, l: {"date": "2026-01-06", "o": o, "h": h, "l": l, "c": o, "v": 1}
    assert record.fill(pick, bar(100.0, 100.5, 99.0))[:2] == ("filled", 100.0)      # exactly at the buy stop
    assert record.fill(pick, bar(101.6, 101.9, 100.0))[:2] == ("filled", 101.6)     # at the limit
    assert record.fill(pick, bar(99.0, 99.9, 98.5))[0] == record.NOT_FILLED         # under it, never reached
    assert record.fill(pick, bar(99.0, 100.5, 98.5))[3] == "trigger_timing"
    assert record.fill(pick, bar(99.0, 100.5, 97.5))[3] == "stop_sequence"
    assert record.fill(pick, bar(102.0, 102.5, 101.0))[3] == "open_above_limit"
    assert record.fill(pick, bar(102.0, 103.5, 101.7))[0] == record.NOT_FILLED
    assert record.fill(pick, bar(97.0, 100.5, 96.5))[3] == "open_below_skip"
    for word in ("trigger_timing", "stop_sequence", "open_above_limit", "open_below_skip"):
        assert f"`{word}`" in PROTOCOL, word


# ---------------------------------------------------------- the protocol ---
def test_the_price_state_words_and_their_bounds_are_the_morning_receipts():
    words = [word for word in morning.PRICE_STATES if word != "unknown"]
    burst = table_rows(ROOT / "knowledge" / "broker-fidelity-protocol.md", "price state")
    assert [word for row in burst for word in re.findall(r"`(\w+)`", row[0])] == words
    # the burst table's bounds, on a plan whose stop sits under its skip line
    wide = burst_plan(95.5)
    levels = {"stop": wide["stop"], "entry_low": wide["entry_low"], "trigger": wide["entry_ref"],
              "limit": wide["limit"], "day2_spent_above": wide["day2_spent_above"]}
    assert wide["stop"] < wide["skip_if_open_below"] < wide["entry_ref"] < wide["limit"] <= wide["day2_spent_above"]
    assert states(levels, grid(wide["stop"] - 1, wide["extended_above"] + 1)) == words
    assert morning.price_state(wide["stop"], levels, "recent") == "below_stop"                      # at or under the stop
    assert morning.price_state(wide["skip_if_open_below"], levels, "recent") == "below_trigger"     # from the skip line
    assert morning.price_state(wide["entry_ref"], levels, "recent") == "within_published_band"      # from the trigger
    assert morning.price_state(wide["limit"], levels, "recent") == "within_published_band"          # through the limit
    assert morning.price_state(wide["day2_spent_above"], levels, "recent") == "above_limit"         # up to the day-2 line
    assert morning.price_state(wide["entry_ref"], levels, "stale") == "unknown"
    # a tight burst: the stop above the skip line, and no price in below_entry_floor
    tight = burst_plan(99.2)
    assert tight["stop"] > tight["skip_if_open_below"]
    tight_levels = {"stop": tight["stop"], "entry_low": tight["entry_low"], "trigger": tight["entry_ref"],
                    "limit": tight["limit"], "day2_spent_above": tight["day2_spent_above"]}
    assert "below_entry_floor" not in states(tight_levels, grid(95.0, 110.0))
    assert "then no price is in `below_entry_floor`" in PROTOCOL
    # an anticipation ticket: its entry floor is its trigger and it has no day-2 line
    made = plan.anticipation_plan(ticker="XMPL", close=50.0, box_high=50.4, box_low=49.0, lows_last3=[49.3, 49.5, 49.6],
                                  account=ACCOUNT)
    coil = {"stop": made["stop"], "entry_low": made["trigger"], "trigger": made["trigger"], "limit": made["limit"],
            "day2_spent_above": None}
    second = (ROOT / "knowledge" / "broker-fidelity-protocol.md").read_text().split("### An anticipation ticket", 1)[1]
    listed = re.findall(r"^\| `(\w+)` \|", second.split("### Rules for every ticket", 1)[0], flags=re.M)
    assert listed == states(coil, grid(made["stop"] - 1, made["limit"] + 5)) == ["below_stop", "below_entry_floor",
                                                                                 "within_published_band", "above_limit"]
    assert "so `below_trigger` and `above_day2_extension` never apply to it" in PROTOCOL


def test_the_protocols_lines_are_the_plans_fields_and_percentages():
    made = burst_plan(95.5)
    for name in ("skip_if_open_below", "day2_spent_above", "extended_above", "position_usd", "risk_usd"):
        assert name in made, name
    assert made["skip_if_open_below"] == plan._at_pct(100.0, -plan.ENTRY_BELOW_PCT)
    assert made["day2_spent_above"] == plan._at_pct(100.0, plan.ENTRY_ABOVE_PCT)
    assert made["extended_above"] == plan._at_pct(100.0, plan.SKIP_GAP_PCT)
    assert (f"the skip line ({plan.ENTRY_BELOW_PCT:g}% under the close, `skip_if_open_below`)" in PROTOCOL
            and f"the day-2 line ({plan.ENTRY_ABOVE_PCT:g}% over the close, `day2_spent_above`)" in PROTOCOL
            and f"{plan.SKIP_GAP_PCT:g}% over the close (`extended_above`)" in PROTOCOL)
    coil = plan.anticipation_plan(ticker="XMPL", close=50.0, box_high=50.4, box_low=49.0, lows_last3=[49.3, 49.5, 49.6],
                                  account=ACCOUNT)
    assert coil["limit"] == plan._at_pct(coil["trigger"], plan.TRIGGER_LIMIT_PCT)
    assert coil["gap_ok_above"] == plan._at_pct(50.0, plan.GAP_OK_PCT) and coil["stop"] == 49.3
    assert (f"the lowest low of the last {NUMBER_WORDS[plan.STOP_LOOKBACK_SESSIONS]} sessions, `plan.STOP_LOOKBACK_SESSIONS`" in PROTOCOL
            and f"the limit, {plan.TRIGGER_LIMIT_PCT:g}% over the trigger (`plan.TRIGGER_LIMIT_PCT`)" in PROTOCOL
            and f"the gap line, {plan.GAP_OK_PCT:g}% over the close (`gap_ok_above`)" in PROTOCOL)
    assert "catalyst check before buying" in coil["gap_rule"] and "\"gapped: catalyst check before buying\"" in PROTOCOL
    assert f"The entry window is the first {plan.ENTRY_WINDOW_MINUTES} minutes of the session" in PROTOCOL
    assert f"{plan.ENTRY_BELOW_PCT:g}% under the close" in BROKER and f"{plan.ENTRY_ABOVE_PCT:g}% over the close" in BROKER
    # the stop rises to the entry day's low at the close of day 1: rule (d)
    assert any(rule["key"] == "entry_day_low" for rule in plan.EXIT_RULES) and "(`plan.follow()`)" in PROTOCOL


def test_the_u5_table_is_what_each_reading_of_the_rule_predicts():
    """Five test orders tell four readings of Fidelity's buy-stop rule apart.
    The table is derived here from the readings; the note must print it."""
    close, quote_x, quote_y = 20.00, 20.30, 19.60     # X quoted above its last close, Y below
    orders = {"A1": (close, quote_x), "A2": (close + 0.01, quote_x), "A3": (quote_x + 0.05, quote_x),
              "B1": (close, quote_y), "B2": ((quote_y + close) / 2, quote_y)}
    readings = {
        "nothing, before the open": lambda stop, quote: True,
        "the last close, and \"at or above\" is allowed": lambda stop, quote: stop >= close,
        "the last close, and the stop must be strictly above it": lambda stop, quote: stop > close,
        "the pre-market quote": lambda stop, quote: stop > quote,
    }
    rows = table_rows(ROOT / "knowledge" / "broker-fidelity-protocol.md", "A1")
    printed = {row[5]: row[:5] for row in rows if row[0] in ("accepted", "refused")}
    assert set(printed) == set(readings)
    for reading, accepts in readings.items():
        expected = ["accepted" if accepts(*orders[name]) else "refused" for name in ("A1", "A2", "A3", "B1", "B2")]
        assert printed[reading] == expected, reading
    assert len({tuple(cells) for cells in printed.values()}) == len(readings), "two readings predict one pattern"
    assert rows[-1][0] == "any other pattern" and rows[-1][5] == "not established"


# ------------------------------------------------------------ the ledger ---
def test_the_ledgers_words_are_the_modules(tmp_path, capsys):
    keys = {rule["key"] for rule in plan.EXIT_RULES}
    raw = (ROOT / "knowledge" / "trade-ledger.md").read_text()
    exit_reasons = re.search(r"`exit_reason`: (.*?) \(the names in `plan.EXIT_RULES`\) or `discretionary`", LEDGER).group(1)
    assert set(re.findall(r"`(\w+)`", exit_reasons)) <= keys and "`stop`" in exit_reasons
    stop_rules = re.search(r"the plan rule the change follows: (.*?) \(the names in `plan.EXIT_RULES`\) or `manual`", LEDGER).group(1)
    assert set(re.findall(r"`(\w+)`", stop_rules)) == {"entry_day_low", "sell_half_8pct", "trail_after_day3"} <= keys
    states_cell = next(line for line in raw.splitlines() if line.startswith("| `entry_state` |"))
    assert re.findall(r"`(\w+)`", states_cell.split("|")[2])[0:6] == [w for w in morning.PRICE_STATES if w != "unknown"]
    # the browser store and its backup file, read off the page's own modules
    store = (ROOT / "docs" / "app-handoff.js").read_text()
    version = int(re.search(r"const VERSION = (\d+), KEY = 'spicystock:handoff:v1'", store).group(1))
    assert f"(the store `spicystock:handoff:v1`, version {version})" in LEDGER and version in private_results.STORE_VERSIONS
    assert "download: 'spicystock-private-backup.json'" in (ROOT / "docs" / "app-handoff-ui.js").read_text()
    assert "`spicystock-private-backup.json`" in LEDGER
    assert f"the newest {private_results.GIT_LIMIT} commits unless `--limit` says otherwise" in LEDGER
    fields = set(private_results.LEGACY_FIELDS + private_results.RESULT_FIELDS + private_results.OWNER_FIELDS)
    reconciled = table_rows(ROOT / "knowledge" / "trade-ledger.md", "backup field (`records[].facts`)")
    named = {name for row in reconciled[:-1] for name in re.findall(r"`(\w+)`", row[0])}
    assert named <= fields and {"filled_quantity", "average_exit_price", "stop_price", "account_label"} <= named
    assert set(private_results.KINDS) >= {"planned_handoff", "owner_trade"} and "`planned_handoff`" in LEDGER and "`owner_trade`" in LEDGER
    for code, words in ((0, "every record re-derived and traced"), (1, "a record's publication was not found"),
                        (2, "the file is not a backup the page would accept"), (3, "a file or the history could not be read")):
        assert f"{code}, {words}" in LEDGER and f"Exit {code}" in private_results.__doc__, code
    # the four exit codes, by running the tool on the committed synthetic backup
    backup = ROOT / "tests" / "fixtures" / "first-trade" / "backup.json"
    own = ROOT / "tests" / "fixtures" / "cash-preview" / "publication-multiple.json"
    other = ROOT / "tests" / "fixtures" / "page" / "red.json"
    reading = tmp_path / "reading.json"
    assert private_results.main([str(backup), "--publication", str(own), "--json", str(reading)]) == 0
    traced = json.loads(reading.read_text())
    assert {record_["trace"]["status"] for record_ in traced["records"]} == {"traced"} and "net" in traced["records"][0]["reported"]
    assert private_results.main([str(backup), "--publication", str(other)]) == 1
    (tmp_path / "not-a-backup.json").write_text("{}")
    assert private_results.main([str(tmp_path / "not-a-backup.json")]) == 2
    assert private_results.main([str(tmp_path / "missing.json")]) == 3
    capsys.readouterr()
    assert f"reading (version {private_results.VERSION})" in LEDGER
    # the quality ledger's outcome row carries what the note says it does
    assert "`evidence_ref.id`" in LEDGER and "`model_record.plans`" in LEDGER


def test_the_worked_example_is_the_records_own_arithmetic():
    """Synthetic numbers, computed here by ``record.r_multiple()`` and
    ``record.replay()`` and held to the figures the note prints."""
    shares, trigger, limit, stop, entry = 12, 50.00, 50.80, 48.80, 50.42
    planned = round(shares * (limit - stop), 2)
    assert f"trigger ${trigger:.2f}, limit ${limit:.2f}, stop ${stop:.2f}, {shares} shares, planned risk ${planned:.2f}" in LEDGER

    def real(exits, fees):
        gross = round(sum(quantity * (price - entry) for quantity, price in exits), 2)
        row = {"entry_ref": entry, "shares": shares, "events": [{"shares": q, "price": p} for q, p in exits]}
        return gross, round(gross - fees, 2), record.r_multiple(row, stop)

    gross, net, r = real([(12, 48.61)], 0.02)
    assert (gross, net, r) == (-21.72, -21.74, -1.12)
    assert f"-21.72 ÷ (12 × 1.62) = {r:.2f}" in LEDGER and f"-21.74 ÷ 24.00 = {net / planned:.2f}" in LEDGER
    assert f"12 × (48.80 - 48.61) = ${shares * (stop - 48.61):.2f}" in LEDGER
    gross2, net2, r2 = real([(6, 54.50), (6, 53.10)], 0.04)
    assert (gross2, net2, r2) == (40.56, 40.52, 2.09)
    assert f"40.56 ÷ (12 × 1.62) = {r2:.2f}" in LEDGER and f"40.52 ÷ 24.00 = {net2 / planned:.2f}" in LEDGER
    assert round(entry - stop, 2) == 1.62
    # the model's column: the same synthetic bar through the record's own walk
    pick = {"ticker": "XMPL", "date": "2026-01-05", "kind": "burst", "entry_ref": trigger, "entry_low": 49.0,
            "entry_high": limit, "stop": stop, "shares": shares}
    walk = record.replay(pick, [{"date": "2026-01-06", "o": 50.40, "h": 50.60, "l": 48.20, "c": 48.50, "v": 1}])
    model_r = record.r_multiple(walk, stop)
    assert (walk["status"], walk["entry_ref"], walk["exit_price"], model_r) == ("stopped", 50.40, stop, -1.0)
    assert f"| `delta_r` | {r - model_r:.2f} (`entry_price`, `exit_price`) |" in LEDGER
    assert "Every number in it is synthetic" in LEDGER


# --------------------------------------------------------- event coverage ---
def test_event_coverage_quotes_the_modules_own_bounds():
    assert earnings_risk.POLICY == "warn_only" and "The policy is `warn_only`: it never refuses, sizes or cuts a ticket" in EVENTS
    assert f"published tickets only, at most {earnings_risk.MAX_TICKETS} a night" in EVENTS
    assert earnings_risk.RESULTS_FORM == "8-K" and earnings_risk.RESULTS_ITEM == "2.02" and "(Form 8-K, item 2.02)" in EVENTS
    assert (f"moved forward {earnings_risk.PROJECTION_DAYS} days, give or take {earnings_risk.ESTIMATE_SLACK_DAYS}" in EVENTS
            and f"{NUMBER_WORDS[plan.FINAL_EXIT_DAY]}-session hold" in EVENTS)
    assert f"filed in the {earnings_risk.RECENT_REPORT_DAYS} days before the signal or since" in EVENTS
    assert f"the 8-K item codes of the last {earnings_risk.RECENT_REPORT_DAYS} days" in EVENTS
    items = earnings_risk.MATERIAL_ITEMS
    assert "item " + ", ".join(items[:-1]) + " or " + items[-1] in EVENTS
    words = [earnings_risk.MATERIAL_WORDS[item] for item in items]
    assert "(" + ", ".join(words) + ")" in EVENTS
    assert (f"at most {issuer_evidence.MAX_ISSUERS} issuers" in EVENTS
            and f"up to {issuer_evidence.MAX_REPORTS} current reports (8-K, 6-K and their amendments) from the last "
                f"{issuer_evidence.LOOKBACK_DAYS} days with up to {issuer_evidence.MAX_EXHIBITS} exhibits each" in EVENTS)
    assert issuer_evidence.FORMS == {"8-K", "8-K/A", "6-K", "6-K/A"}
    base = sorted(form for form in issuer_evidence.ACQUISITION_FORMS if not form.endswith("/A"))
    assert base == ["DEFM14A", "PREM14A", "SC 14D9", "SC TO-T"] and "(PREM14A, DEFM14A, SC TO-T, SC 14D9 and their amendments)" in EVENTS
    assert {form + "/A" for form in base} | set(base) == issuer_evidence.ACQUISITION_FORMS
    assert issuer_evidence.COVERAGE["issuer_news"]["status"] == "not_cleared" and issuer_evidence.COVERAGE["earnings"]["status"] == "not_checked"
    assert "issuer news is `not_cleared` and the earnings calendar `not_checked`" in EVENTS
    assert "nasdaqtrader.com" in morning_halts_url() and "`www.nasdaqtrader.com`" in EVENTS
    # the biotech flag marks the whole Health Care sector
    assert universe.flags_for({"sector": universe.HEALTH_CARE_SECTOR, "industry": "Medical Specialities", "country": "United States"}) == {universe.BIOTECH_FLAG}
    assert "`biotech` is set for the whole Health Care sector" in EVENTS
    assert f"The hold is {NUMBER_WORDS[plan.FINAL_EXIT_DAY]} sessions and day 1 is the session after the signal" in EVENTS
    assert len(table_rows(ROOT / "knowledge" / "event-coverage.md", "#")) == 10
    assert "\"not established\" is never \"clear\"" in EVENTS


def morning_halts_url() -> str:
    from src import morning_halts
    return morning_halts.SOURCE_URL


def test_a_passed_review_date_never_clears_a_registry_entry():
    """The three status words, driven through ``classify()`` over a registry
    made for the test: the review date changes the word and never the block."""
    source = {"title": "A synthetic announcement", "published_on": "2026-01-05", "url": "https://example.com/release",
              "sha256": "0" * 64, "quote": "A synthetic sentence."}
    registry = {"version": event_risk.VERSION, "coverage": event_risk.COVERAGE, "reviewed_on": "2026-01-06",
                "coverage_note": "A synthetic registry for one test.",
                "events": [{**{key: value for key, value in event_risk.REGISTRY["events"][0].items()},
                            "symbol": "XMPL", "announced_on": "2026-01-05", "active_from": "2026-01-05",
                            "active_until": None, "evidence_as_of": "2026-01-05", "reviewed_on": "2026-01-06",
                            "review_due": "2026-01-13", "sources": [source]}]}
    registry["events"][0].pop("resolution", None)
    event_risk.validate_registry(registry)
    current = event_risk.classify("XMPL", "2026-01-13", registry=registry)
    overdue = event_risk.classify("XMPL", "2026-01-14", registry=registry)
    absent = event_risk.classify("OTHR", "2026-01-14", registry=registry)
    assert (current["status"], current["blocked"]) == ("known_event", True)
    assert (overdue["status"], overdue["blocked"]) == ("review_required", True)
    assert (absent["status"], absent["blocked"]) == ("not_in_registry", False) and "have not been cleared" in absent["reason"]
    blocked = event_risk.apply({"eligible": True, "action": "place_buy_stop", "order_json": {"symbol": "XMPL"}}, "XMPL",
                               "2026-01-14", registry=registry)
    assert blocked["action"] == "refused" and blocked["order_json"] is None and blocked["eligible"] is False
    for word in ("known_event", "review_required", "not_in_registry"):
        assert f"`{word}`" in EVENTS, word
    assert "A passed review date changes the status word from `known_event` to `review_required` and nothing else" in EVENTS
    assert "a passed review date never clears an entry" in EVENTS
    assert event_risk.COVERAGE == "manual_known_events_only"


def test_the_code_reads_no_source_the_coverage_note_does_not_name():
    """Every address a module under src/ spells is one the note accounts for:
    SEC, Nasdaq Trader, Nasdaq, the market-data provider, a documentation link
    and this project's own pages and repository. A new host fails here, so a
    news or calendar source cannot arrive without the note saying so."""
    named = {"data.sec.gov", "www.sec.gov", "www.nasdaqtrader.com", "api.nasdaq.com", "data.alpaca.markets"}
    own = {"spicychicken59.github.io", "github.com", "raw.githubusercontent.com"}
    documentation = {"platform.claude.com"}
    found = set()
    for path in sorted((ROOT / "src").glob("*.py")):
        found |= set(re.findall(r"https?://([A-Za-z0-9.\-]+)", path.read_text()))
    assert found - named - own - documentation == set(), sorted(found - named - own - documentation)
    assert named <= found
    for host in sorted(named):
        assert f"`{host}`" in EVENTS, host
    assert "There is no news wire, no press-release feed and no earnings calendar" in EVENTS


# ---------------------------------------------------- the scorecard contract ---
def test_the_scorecard_contract_says_what_append_and_follow_do():
    pick = {"ticker": "XMPL", "kind": "burst", "entry_ref": 100.0, "entry_low": 98.0, "entry_high": 101.6,
            "stop": 97.6, "shares": 10}
    first = record.append(record.empty(), "2026-01-05", [dict(pick), dict(pick, ticker="KEPT")])
    rerun = record.append(first, "2026-01-05", [dict(pick, shares=5)])
    assert [(p["ticker"], p["shares"]) for p in rerun["picks"]] == [("KEPT", 10), ("XMPL", 5)]
    later = record.append(rerun, "2026-01-06", [dict(pick)])
    assert len(later["picks"]) == 3                      # a later night is a separate pick
    assert ("A rerun replaces a pick of the same kind, ticker and session (`record.append()`). A pick the rerun no "
            "longer issues is kept") in CONTRACT
    assert "A setup issued again on a later night is a separate pick and is counted again" in CONTRACT
    assert f"The file retains up to {record.MAX_PICKS} picks" in CONTRACT
    assert f"the prior {record.SCORECARD_SESSIONS} XNYS sessions" in CONTRACT
    assert f"below {record.SCORECARD_MIN_PLANS} resolved plans" in CONTRACT
    # a stop inside a session, the fill day included, is booked at exactly the stop: -1.00R
    bar = lambda day, o, h, l, c: {"date": f"2026-01-{day:02d}", "o": o, "h": h, "l": l, "c": c, "v": 1}
    stopped = record.replay(dict(pick, date="2026-01-05"), [bar(6, 101.0, 101.5, 95.0, 96.0)])
    assert (stopped["exit_price"], record.r_multiple(stopped, pick["stop"])) == (97.6, -1.0)
    assert "a stop first reached inside a session is booked at exactly the stop price, with no slippage, the fill day included" in CONTRACT
    assert "A stop on the fill day is therefore always -1.00R" in CONTRACT
    # a session that opens under the stop is booked at its open
    gapped = record.replay(dict(pick, date="2026-01-05"), [bar(6, 101.0, 101.5, 100.5, 101.2), bar(7, 94.0, 95.0, 93.0, 94.5)])
    assert gapped["exit_price"] == 94.0 and gapped["events"][-1]["event"] == "stopped_at_open"
    assert "Stop-market gaps use the open" in CONTRACT
    # whole-share sales make R depend on the share count
    up = [bar(6, 100.5, 101.0, 100.2, 100.8), bar(7, 101.0, 109.5, 100.9, 109.0), bar(8, 109.0, 110.0, 108.5, 109.5),
          bar(9, 109.5, 111.0, 109.0, 110.5), bar(12, 110.5, 112.0, 110.0, 111.5)]
    one = record.replay(dict(pick, date="2026-01-05", shares=1), up)
    three = record.replay(dict(pick, date="2026-01-05", shares=3), up)
    assert one["status"] == "exit" and one["remaining"] == 0 and [e["event"] for e in one["events"] if e.get("shares")] == ["sell_half"]
    assert record.r_multiple(one, pick["stop"]) != record.r_multiple(three, pick["stop"])
    assert "a one-share ticket sells whole at its half-sale step, and a sum of R is not a sum of dollars" in CONTRACT
    assert "fee/spread/slippage/tax model" in CONTRACT
