"""The analyst's daily brief (``src/brief.py``): a function of the canonical
record's bytes, the pick ledger's bytes and one optional carried block. These
tests hold it to the page fixtures the pipeline writes: the same bytes twice,
both byte bounds, every burst accounted for once, a ticket's levels equal to
the record's plan, a research row never carrying an order, the binding the
publication gate checks and the two forgeries only re-derivation catches, and
each block the brief adds to what the record says. No clock is read."""
from __future__ import annotations

import copy
import functools
import hashlib
import json
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

from src import admission, breadth, brief, event_risk, freshness, morning, plan, reader, record, report

ROOT = Path(__file__).parent.parent
PAGE = Path(__file__).parent / "fixtures" / "page"
GOLDEN = Path(__file__).parent / "fixtures" / "brief"
VARIANTS = ("full", "degraded", "notrade", "yellow", "red", "closed", "empty", "partial", "early", "thin", "next",
            "revised")
FULL_RAW = (PAGE / "full.json").read_bytes()
PICKS_RAW = (PAGE / "full-picks.json").read_bytes()
MODULES = {"plan": plan, "event_risk": event_risk, "admission": admission}


def encoded(data: dict) -> bytes:
    return (json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


@functools.lru_cache(maxsize=None)
def derived(variant: str) -> tuple:
    raw = (PAGE / f"{variant}.json").read_bytes()
    picks_raw = PICKS_RAW if variant == "full" else None
    json_raw, md_raw, why = brief.compose(raw, picks_raw)
    assert why is None, why
    return raw, picks_raw, json_raw, md_raw


def changed(change, picks_raw=PICKS_RAW, model_record=None) -> tuple:
    """(record, brief, markdown, why) for the `full` fixture after ``change(record)``."""
    data = json.loads(FULL_RAW)
    change(data)
    raw = encoded(data)
    json_raw, md_raw, why = brief.compose(raw, picks_raw, model_record)
    return data, json.loads(json_raw), md_raw.decode("utf-8"), why


def changed_in(variant: str, change) -> tuple:
    """(record, brief, markdown, why) for any page fixture after ``change(record)``, without a pick ledger."""
    data = json.loads((PAGE / f"{variant}.json").read_bytes())
    change(data)
    json_raw, md_raw, why = brief.compose(encoded(data), None)
    return data, json.loads(json_raw), md_raw.decode("utf-8"), why


def burst(data: dict, ticker: str) -> dict:
    return next(row for row in data["bursts"] if row["ticker"] == ticker)


def detailed(out: dict, ticker: str) -> dict:
    return next(row for row in out["candidates"]["detailed"] if row["ticker"] == ticker)


def section(md: str, number: int) -> str:
    start = md.index(f"## {number}. ")
    end = md.find(f"## {number + 1}. ", start)
    return md[start:end if end != -1 else None]


def agreeing_block(data: dict, **extra) -> dict:
    """SYNTHETIC model-record block that agrees with the record's own scorecard."""
    card = data["scorecard"]
    return {"version": 1, "status": "computed", "tickets": card["plans"],
            "buckets": {name: card[name] for name in record.SCORECARD_BUCKETS}, "sum_r": card["sum_r"],
            "sentences": ["SYNTHETIC: the test's own model record."], **extra}


# ------------------------------------------------- every fixture the pipeline writes
@pytest.mark.parametrize("variant", VARIANTS)
def test_the_same_bytes_twice_within_both_bounds_and_validating(variant):
    raw, picks_raw, json_raw, md_raw = derived(variant)
    assert brief.compose(raw, picks_raw)[:2] == (json_raw, md_raw)
    assert len(json_raw) <= brief.MAX_JSON_BYTES and len(md_raw) <= brief.MAX_MD_BYTES
    out = brief.validate(raw, picks_raw, json_raw, md_raw)
    assert out["status"] == "derived" and out["schema"] == brief.SCHEMA and out["version"] == brief.VERSION
    assert json_raw.endswith(b"\n") and b"\n" not in json_raw[:-1]            # one compact line
    assert out["identity"]["canonical"] == {"path": "data.json", "sha256": hashlib.sha256(raw).hexdigest(),
                                            "bytes": len(raw)}


@pytest.mark.parametrize("variant", VARIANTS)
def test_every_burst_is_accounted_for_exactly_once(variant):
    raw, _, json_raw, _ = derived(variant)
    data, out = json.loads(raw), json.loads(json_raw)
    tail = [name.split(" (")[0] for group in out["research_tail"]["groups"] for name in group["tickers"]]
    seen = [r["ticker"] for r in out["candidates"]["detailed"]] + [r["ticker"] for r in out["candidates"]["compact"]] + tail
    assert sorted(seen) == sorted(row["ticker"] for row in data["bursts"])
    assert out["research_tail"]["left_out"] == 0 and out["bounds"]["research_tail_left_out"] == 0
    assert out["research_tail"]["total"] == len(tail) == sum(g["count"] for g in out["research_tail"]["groups"])
    counts, bounds = out["candidates"]["counts"], out["bounds"]
    assert counts["discovered"] == len(data["bursts"])
    assert bounds["candidates_detailed"] + bounds["candidates_compact"] + bounds["candidates_moved_to_tail"] == counts["listed_here"]


@pytest.mark.parametrize("variant", VARIANTS)
def test_the_tickets_are_the_records_orders_and_nothing_else_carries_one(variant):
    raw, _, json_raw, md_raw = derived(variant)
    data, out, md = json.loads(raw), json.loads(json_raw), md_raw.decode()
    listed = [r["ticker"] for r in (data.get("watchlist") or {}).get("top") or []
              if (r.get("plan") or {}).get("order_json") and r.get("ticket", True)]
    burst_tickets = [t["ticker"] for t in out["tickets"] if t["stage"] == "burst"]
    assert burst_tickets == [t for t in data["trades"] if any(b["ticker"] == t for b in data["bursts"])]
    assert set(t["ticker"] for t in out["tickets"] if t["stage"] == "anticipation") <= set(listed) | set(data["trades"])
    for ticket in out["tickets"]:
        assert ticket["model_status"] == brief.TICKET and ticket["order"] and ticket["order_entry"]["order_as_written"]
        assert {s["date"] for s in ticket["schedule"] if s["day"] == 1} == {out["identity"]["applicable_session"]}
    ticketed = {(t["stage"], t["ticker"]) for t in out["tickets"]}
    for row in out["candidates"]["detailed"]:
        is_ticket = ("burst", row["ticker"]) in ticketed
        assert row["model_status"] == (brief.TICKET if is_ticket else brief.RESEARCH_ONLY)
        assert ("levels" in row) == is_ticket or "levels" not in row
        assert not any(name.startswith("order") for name in row), row["ticker"]
        if not is_ticket and "research_levels" in row:
            assert row["research_levels_label"] == brief.RESEARCH_LEVELS_LABEL
            assert "action" not in row["research_levels"]
    for row in out["candidates"]["compact"]:
        assert row["model_status"] == brief.RESEARCH_SHORT and not any(name.startswith("order") for name in row)
    for row in out["setting_up"]["listed"]:
        if ("anticipation", row["ticker"]) not in ticketed:
            assert row["model_status"] == brief.RESEARCH_ONLY and not any(name.startswith("order") for name in row)
    # the Markdown prints an order line in section 5 only, once a ticket
    assert md.count("- Order as the record wrote it: ") == len(out["tickets"])
    assert "Order as the record wrote it" not in md.replace(section(md, 5), "")
    assert not re.search(r"`Buy \d+ ", md.replace(section(md, 5), ""))


@pytest.mark.parametrize("variant", VARIANTS)
def test_the_fixed_text_the_sections_and_no_credential_shaped_name(variant):
    _, _, json_raw, md_raw = derived(variant)
    out, md = json.loads(json_raw), md_raw.decode()
    assert out["limits"] == list(brief.LIMITS) and out["read_first"] == list(brief.READ_FIRST)
    assert all(f"- {limit}" in section(md, 14) for limit in brief.LIMITS)
    lines = md.splitlines()
    assert lines[0].startswith("# SpicyStock daily brief: measured ")
    assert [line[2:] for line in lines[2:2 + len(brief.READ_FIRST)]] == list(brief.READ_FIRST)
    headings = [line for line in lines if line.startswith("## ")]
    assert len(headings) == len(brief.SECTIONS) == 14
    assert all(h.startswith(f"## {n}. {name}") for n, (h, name) in enumerate(zip(headings, brief.SECTIONS), 1))
    assert brief.scanner_names(out) == []
    assert "—" not in "".join(brief.LIMITS + brief.READ_FIRST + freshness.RULE + (brief.GATE_NOTE, brief.SCALING_NOTE))


def test_the_opening_lines_say_what_the_file_is_how_to_check_it_and_what_is_not_a_ticket():
    first = " ".join(brief.READ_FIRST)
    assert "daily brief" in first and "derived from that publication's record" in first
    assert "`status` must be `derived`" in first and "freshness rule" in first and "your own clock" in first
    assert "Only the rows in section 5 (`tickets`) are published model tickets" in first
    assert "research only" in first and "offers no order" in first
    assert "places, cancels and observes no order" in first


def test_the_committed_golden_pair_is_this_derivation():
    raw, picks_raw, json_raw, md_raw = derived("full")
    assert (GOLDEN / brief.JSON_FILE).read_bytes() == json_raw, "run tests/fixtures/brief/generate.py"
    assert (GOLDEN / brief.MD_FILE).read_bytes() == md_raw, "run tests/fixtures/brief/generate.py"
    sys.path.insert(0, str(GOLDEN))
    try:
        import generate
        assert generate.main(["--check"]) == 0
    finally:
        sys.path.remove(str(GOLDEN))
        sys.modules.pop("generate", None)


# ------------------------------------------------------------------ levels
PRICE_NAMES = {"trigger": "entry_ref", "limit": "limit", "stop": "stop", "day2_line": "day2_spent_above",
               "skip_if_open_below": "skip_if_open_below", "planned_entry": "planned_entry",
               "selling_above": "extended_above", "stop_pct_at_limit": "stop_pct", "risk_per_share_at_limit": "risk_per_share"}


def test_a_tickets_levels_are_the_records_plan_to_the_cent():
    raw, _, json_raw, _ = derived("full")
    data, out = json.loads(raw), json.loads(json_raw)
    recorded, ticket = burst(data, "AAPL")["plan"], out["tickets"][0]
    assert ticket["ticker"] == "AAPL" and ticket["levels"]["source"] == "record"
    assert {name: ticket["levels"][name] for name in PRICE_NAMES} == {name: recorded[key] for name, key in PRICE_NAMES.items()}
    assert (ticket["levels"]["shares"], ticket["levels"]["cost"], ticket["levels"]["risk"], ticket["levels"]["multiplier"]) == \
        (recorded["shares"], recorded["position_usd"], recorded["risk_usd"], recorded["size_multiplier"])
    assert (ticket["levels"]["sell_half"], ticket["levels"]["target_high"]) == (recorded["targets"]["low"], recorded["targets"]["high"])
    assert ticket["order"] == recorded["order_line"] and ticket["order_entry"]["order_as_written"] == recorded["order_json"]
    assert detailed(out, "AAPL")["levels"] == ticket["levels"]


@pytest.mark.parametrize("ticker", ["AAPL", "AMD", "NVDA", "TSLA"])
def test_the_plan_rule_run_again_gives_the_plan_the_record_carries(ticker):
    """Where the record carries a plan, the brief copies it; where it does not, the brief runs the record's plan
    rule over the row's own bar. Take the plan away and the two must agree, or a research level is not the rule's."""
    raw, _, json_raw, _ = derived("full")
    with_plan = detailed(json.loads(json_raw), ticker)
    from_record = with_plan.get("levels") or with_plan["research_levels"]

    def drop(data):
        burst(data, ticker)["plan"] = None
        data["trades"] = [t for t in data["trades"] if t != ticker]
    _, out, _, why = changed(drop)
    assert why is None
    again = detailed(out, ticker)["research_levels"]
    assert from_record["source"] == "record" and again["source"] == "derived"
    assert {k: v for k, v in again.items() if k != "source"} == {k: v for k, v in from_record.items() if k != "source"}


def test_a_withheld_burst_prints_its_refusal_and_no_stop_limit_or_share_count():
    _, _, json_raw, md_raw = derived("full")
    row = detailed(json.loads(json_raw), "TSLA")
    levels = row["research_levels"]
    assert levels["plan_rule_eligible"] is False and levels["refusal"].startswith("ticket withheld: no limit above")
    assert not {"stop", "limit", "shares", "cost", "risk", "at_yellow_size", "at_full_size"} & set(levels)
    # the setup stands: its trigger is still the record's own, a cushion over the close
    assert levels["trigger"] == burst(json.loads(derived("full")[0]), "TSLA")["plan"]["entry_ref"] == 124.33
    block = md_raw.decode().split("### TSLA ")[1].split("\n### ")[0]
    assert "ticket withheld: no limit above" in block and "model size" not in block and "shares" not in block


def sized_by_hand(account: dict, limit: float, stop: float, *multipliers: float) -> dict:
    """``plan.size()``'s arithmetic written out for one research size: the risk budget (equity, the risk percent
    and every multiplier) over the risk a share at the limit, in whole cents, floored to a whole share and never
    more than the position cap buys."""
    total = 1.0
    for multiplier in multipliers:
        total *= multiplier
    budget_cents = round(account["equity"] * account["risk_pct"] / 100 * total * 100)
    risk_cents, limit_cents = round((limit - stop) * 100), round(limit * 100)
    cap_cents = round(account["equity"] * account["max_position_pct"] / 100 * 100)
    shares = min(budget_cents // risk_cents, cap_cents // limit_cents)
    return {"shares": shares, "cost": round(shares * limit_cents / 100, 2), "risk": round(shares * risk_cents / 100, 2),
            "multiplier": total}


def own_multipliers(levels: dict) -> list:
    """The multipliers a plan carries whatever the regime, read off its own flags: the stop-risk halving (every
    stop between the ideal and the maximum under the limit) and one hazard halving."""
    hazards = {h["kind"] for h in plan.hazards(plan.GAIN_CEILING_PCT, plan.EXTENSION_HAZARD_PCT + 1)}
    flags = set(levels["flags"])
    assert ("risk_halved" in flags) == (plan.IDEAL_STOP_PCT < levels["stop_pct_at_limit"] <= plan.MAX_STOP_PCT)
    return ([plan.STOP_RISK_MULTIPLIER] if "risk_halved" in flags else []) + \
        ([plan.HAZARD_MULTIPLIER] if flags & hazards else [])


@pytest.mark.parametrize("variant, labels", [("full", {"at_yellow_size"}), ("yellow", {"at_full_size"}),
                                             ("red", {"at_full_size", "at_yellow_size"})])
def test_a_size_at_another_regime_keeps_the_plans_own_stop_risk_multiplier(variant, labels):
    """`at_full_size` and `at_yellow_size` are the SAME plan at another light's multiplier: the stop-risk halving
    every burst ticket carries stays. Each is worked by hand from the record's account and the row's own limit and
    stop: a $50 budget halved to $25 buys 4 AAPL at $5.05 a share of risk, and 2 at the YELLOW half of that."""
    raw, _, json_raw, _ = derived(variant)
    data, out = json.loads(raw), json.loads(json_raw)
    factor = {"at_full_size": 1.0, "at_yellow_size": data["breadth"]["rules"]["size_multiplier"]["yellow"]}
    assert factor["at_yellow_size"] == breadth.SIZE_MULTIPLIER["yellow"] and data["account"]["risk_pct"] == 0.5
    sized = {}
    for row in out["candidates"]["detailed"]:
        levels = row.get("levels") or row["research_levels"]
        if levels["plan_rule_eligible"] is not True:
            assert not set(factor) & set(levels)            # a refused plan states no size at any light
            continue
        own = own_multipliers(levels)
        assert own == [plan.STOP_RISK_MULTIPLIER] and set(factor) & set(levels) == labels, row["ticker"]
        for label in labels:
            assert levels[label] == sized_by_hand(data["account"], levels["limit"], levels["stop"], *own, factor[label])
            # and it is not the size the bare light would give: the plan's own halving is in it
            assert levels[label]["shares"] < sized_by_hand(data["account"], levels["limit"], levels["stop"],
                                                           factor[label])["shares"]
            sized[row["ticker"], label] = levels[label]["shares"]
    assert {ticker for ticker, _ in sized} == {"AAPL", "AMD", "NVDA"}
    if "at_full_size" in labels:
        assert sized["AAPL", "at_full_size"] == 4            # 2500 cents over 505 cents a share
    if "at_yellow_size" in labels:
        assert sized["AAPL", "at_yellow_size"] == 2          # 1250 cents over 505


def test_a_size_at_another_regime_keeps_the_plans_own_hazard_multiplier():
    """A burst day of +16% is a hazard: the plan's budget is halved once more, at every light. AMD on the RED
    fixture night (a derived plan: $5.10 a share of risk at its limit) reads 2 shares at full size ($50 x 0.5 x 0.5 =
    $12.50) and 1 at the YELLOW size ($6.25), where the same bar without the hazard reads 4 and 2."""
    def hazard(data):
        burst(data, "AMD")["gain_pct"] = plan.GAIN_CEILING_PCT + 1.0
    plain = detailed(json.loads(derived("red")[2]), "AMD")["research_levels"]
    data, out, _, why = changed_in("red", hazard)
    assert why is None
    levels = detailed(out, "AMD")["research_levels"]
    assert levels["source"] == "derived" and "gain_over_15" in levels["flags"] and "gain_over_15" not in plain["flags"]
    assert own_multipliers(levels) == [plan.STOP_RISK_MULTIPLIER, plan.HAZARD_MULTIPLIER]
    assert (levels["limit"], levels["stop"], levels["risk_per_share_at_limit"]) == (128.2, 123.1, 5.1)
    for label, light in (("at_full_size", 1.0), ("at_yellow_size", breadth.SIZE_MULTIPLIER["yellow"])):
        assert levels[label] == sized_by_hand(data["account"], 128.2, 123.1, 0.5, 0.5, light)
    assert (levels["at_full_size"]["shares"], levels["at_yellow_size"]["shares"]) == (2, 1)
    assert (plain["at_full_size"]["shares"], plain["at_yellow_size"]["shares"]) == (4, 2)
    assert (levels["at_full_size"]["multiplier"], levels["at_yellow_size"]["multiplier"]) == (0.25, 0.125)


def synthetic_event(symbol: str, announced: str = "2026-09-01", reviewed: str = "2026-09-08",
                    due: str = "2026-09-30") -> dict:
    """SYNTHETIC registry entry, in the registry's own shape and with dates its validator accepts."""
    return {"id": f"synthetic-{symbol.lower()}", "symbol": symbol, "issuer": "SYNTHETIC issuer", "kind": "cash_acquisition",
            "announced_on": announced, "active_from": announced, "active_until": None, "evidence_as_of": announced,
            "reviewed_on": reviewed, "review_due": due, "reason": "SYNTHETIC: a pending cash acquisition, for a test.",
            "sources": [{"title": "SYNTHETIC source", "published_on": announced, "url": "https://example.invalid/synthetic",
                         "sha256": "0" * 64, "quote": "SYNTHETIC quote."}]}


def synthetic_registry(data: dict, events: list, reviewed: str = "2026-09-09") -> None:
    """Replace the archived registry with SYNTHETIC entries the registry's own validator accepts."""
    registry = data["rules"]["event_risk"]["registry"]
    registry.update(events=events, reviewed_on=reviewed)
    event_risk.validate_registry(registry)


def test_a_plan_the_registry_refuses_prints_its_refusal_and_no_share_count():
    def refuse(data):
        burst(data, "AMD")["plan"] = None
        synthetic_registry(data, [synthetic_event("AMD")])
    _, out, md, why = changed(refuse)
    assert why is None
    row = detailed(out, "AMD")
    levels = row["research_levels"]
    assert levels["source"] == "derived" and levels["plan_rule_eligible"] is False
    assert "SYNTHETIC: a pending cash acquisition" in levels["refusal"]
    assert not {"shares", "cost", "risk", "at_yellow_size", "at_full_size"} & set(levels)
    assert row["event"]["status"] == "known_event" and row["event"]["blocked"] is True
    block = md.split("### AMD ")[1].split("\n### ")[0]
    assert "- Plan rule refusal: Known cash-acquisition event: SYNTHETIC: a pending cash acquisition, for a test." in block
    assert "no model size is stated" in block and not re.search(r"model size \d", block) and ".." not in block


def test_a_row_the_plan_rule_cannot_run_on_says_so_by_the_failures_type_and_never_its_text():
    def broken(data):
        row = burst(data, "AMD")
        row["plan"] = None
        del row["open"]
    _, out, md, why = changed(broken)
    assert why is None
    row = detailed(out, "AMD")
    assert row["levels_unavailable"] == "the record's plan rule could not be run on this row (KeyError)"
    assert "research_levels" not in row and "'open'" not in json.dumps(row)
    assert "- research levels: not available (the record's plan rule could not be run on this row (KeyError))." in md


def test_levels_are_unavailable_and_said_so_when_the_archived_plan_rules_are_not_this_codes():
    def older(data):
        data["rules"]["plan"]["entry_above_pct"] = 3.0
        burst(data, "AMD")["plan"] = None
    _, out, md, why = changed(older)
    assert why is None
    row = detailed(out, "AMD")
    assert "research_levels" not in row and "levels" not in row
    assert "entry_above_pct" in row["levels_unavailable"]
    assert out["candidates"]["counts"]["levels_unavailable"] == 1


# ------------------------------------------------------------------ the binding and its forgeries
def test_the_binding_refuses_another_record_another_ledger_and_a_changed_byte():
    raw, picks_raw, json_raw, md_raw = derived("full")
    other_raw, _, other_json, other_md = derived("yellow")
    assert brief.validate_binding(raw, picks_raw, json_raw, md_raw)["status"] == "derived"
    with pytest.raises(ValueError, match="bound to another canonical publication"):
        brief.validate_binding(other_raw, picks_raw, json_raw, md_raw)
    with pytest.raises(ValueError, match="bound to another canonical publication"):
        brief.validate_binding(raw + b" ", picks_raw, json_raw, md_raw)
    with pytest.raises(ValueError, match="bound to another picks.json"):
        brief.validate_binding(raw, picks_raw + b" ", json_raw, md_raw)
    with pytest.raises(ValueError, match="disagree about picks"):
        brief.validate_binding(raw, None, json_raw, md_raw)
    with pytest.raises(ValueError, match="does not render this brief.json"):
        brief.validate_binding(raw, picks_raw, json_raw, other_md)
    flipped = json_raw.replace(b'"trigger":124.33', b'"trigger":124.34', 1)
    assert flipped != json_raw
    with pytest.raises(ValueError, match="does not render this brief.json"):
        brief.validate_binding(raw, picks_raw, flipped, md_raw)
    with pytest.raises(ValueError, match="not in its canonical encoding"):
        spaced = json.dumps(json.loads(json_raw), indent=1).encode() + b"\n"
        brief.validate_binding(raw, picks_raw, spaced, md_raw)
    with pytest.raises(ValueError, match="unsupported brief"):
        brief.validate_binding(raw, picks_raw, brief._encode({**json.loads(json_raw), "status": "fresh"}), md_raw)


def test_a_file_over_its_bound_is_refused(monkeypatch):
    raw, picks_raw, json_raw, md_raw = derived("full")
    monkeypatch.setattr(brief, "MAX_JSON_BYTES", len(json_raw) - 1)
    with pytest.raises(ValueError, match="brief.json exceeds its byte bound"):
        brief.validate_binding(raw, picks_raw, json_raw, md_raw)
    monkeypatch.setattr(brief, "MAX_JSON_BYTES", len(json_raw))
    monkeypatch.setattr(brief, "MAX_MD_BYTES", len(md_raw) - 1)
    with pytest.raises(ValueError, match="brief.md exceeds its byte bound"):
        brief.validate_binding(raw, picks_raw, json_raw, md_raw)
    monkeypatch.setattr(brief, "MAX_MD_BYTES", len(md_raw))
    assert brief.validate_binding(raw, picks_raw, json_raw, md_raw)


def test_two_forgeries_pass_the_binding_and_only_re_derivation_catches_them():
    raw, picks_raw, json_raw, md_raw = derived("full")
    # 1. a level edited in brief.json, re-encoded canonically, and a Markdown rendered for the forged file
    forged = json.loads(json_raw)
    forged["tickets"][0]["levels"]["stop"] = 100.0
    forged_json = brief._encode(forged)
    forged_md = brief.fit_md(forged, forged_json)
    assert brief.validate_binding(raw, picks_raw, forged_json, forged_md)["tickets"][0]["levels"]["stop"] == 100.0
    with pytest.raises(ValueError, match="brief.json differs from its derivation"):
        brief.validate(raw, picks_raw, forged_json, forged_md)
    # 2. a sentence changed in brief.md, its two binding lines left as they were
    reworded = md_raw.replace(b"RESEARCH ONLY: no SpicyStock ticket", b"TICKET", 1)
    assert reworded != md_raw and brief.validate_binding(raw, picks_raw, json_raw, reworded)
    with pytest.raises(ValueError, match="brief.md differs from its derivation"):
        brief.validate(raw, picks_raw, json_raw, reworded)


def test_a_record_the_brief_cannot_read_gets_the_unavailable_pair_bound_to_its_bytes():
    raw = encoded({"schema_version": 1, "bursts": []})
    json_raw, md_raw, why = brief.compose(raw, None)
    assert why == "the publication is not a schema-2 record this brief can read"
    out = brief.validate(raw, None, json_raw, md_raw)
    assert out["status"] == "unavailable" and why in out["reason"] and "tickets" not in out
    assert out["identity"]["canonical"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert md_raw.startswith(b"# SpicyStock daily brief: unavailable") and b"Nothing in this file is a ticket" in md_raw
    for junk in (b"", b"not json", b"[]", b'{"schema_version":2}'):
        json_raw, md_raw, why = brief.compose(junk + b"\n", None)
        assert why and brief.validate_binding(junk + b"\n", None, json_raw, md_raw)["status"] == "unavailable"


def test_a_failure_is_named_by_its_type_and_never_by_its_text(monkeypatch):
    def boom(*args, **kwargs):
        raise KeyError("a sentence that must not be published")
    monkeypatch.setattr(brief, "build", boom)
    json_raw, md_raw, why = brief.compose(FULL_RAW, PICKS_RAW)
    assert why == "KeyError" and b"must not be published" not in json_raw + md_raw
    assert json.loads(json_raw)["status"] == "unavailable"


# ------------------------------------------------------------------ bounds on a large night
def large_night(extra: int) -> bytes:
    """SYNTHETIC: the `full` record with ``extra`` more admitted A+ candidates, clones of its AMD row."""
    data = json.loads(FULL_RAW)
    model = burst(data, "AMD")
    for n in range(extra):
        row = copy.deepcopy(model)
        row["ticker"] = f"SY{n:04d}"
        row["rank"] = len(data["bursts"]) + 1
        row["claude"] = None
        row["plan"] = None
        row.pop("review_selection", None)
        data["bursts"].append(row)
    return encoded(data)


def test_a_large_night_stays_inside_both_bounds_and_says_what_it_left_out():
    raw = large_night(2400)
    json_raw, md_raw, why = brief.compose(raw, PICKS_RAW)
    assert why is None
    assert len(json_raw) <= brief.MAX_JSON_BYTES and len(md_raw) <= brief.MAX_MD_BYTES
    out = brief.validate(raw, PICKS_RAW, json_raw, md_raw)
    bounds, counts = out["bounds"], out["candidates"]["counts"]
    assert counts["listed_here"] == 2404 and counts["discovered"] == 2407
    assert bounds["candidates_detailed"] == 4               # the ticket and the three reviewed names, always
    assert bounds["candidates_compact"] % brief.COMPACT_STEP == 0 and bounds["candidates_compact"] > 0
    assert bounds["candidates_moved_to_tail"] == 2400 - bounds["candidates_compact"] > 0
    moved = next(g for g in out["research_tail"]["groups"] if "left out for size" in g["reason"])
    assert moved["count"] == bounds["candidates_moved_to_tail"]
    # nothing is silently dropped: detailed, compact and the tail's names are every burst, once
    tail = [name.split(" (")[0] for g in out["research_tail"]["groups"] for name in g["tickers"]]
    seen = [r["ticker"] for r in out["candidates"]["detailed"]] + [r["ticker"] for r in out["candidates"]["compact"]] + tail
    assert len(seen) == len(set(seen)) == 2407
    # one more compact step would not have fitted
    full = brief.build(json.loads(raw), json.loads(PICKS_RAW), raw, PICKS_RAW, MODULES)
    over = brief._encode(brief.shape(full, 0, bounds["candidates_compact"] + brief.COMPACT_STEP))
    assert len(over) > brief.MAX_JSON_BYTES
    md = md_raw.decode()
    assert re.search(r"- This file: 4 in detail, \d+ compact rows, \d+ compact rows left out", md)


def test_detail_is_given_up_before_compact_rows_and_in_steps():
    raw = large_night(200)
    json_raw, md_raw, why = brief.compose(raw, PICKS_RAW)
    assert why is None
    bounds = brief.validate(raw, PICKS_RAW, json_raw, md_raw)["bounds"]
    others = bounds["candidates_detailed"] - 4
    assert others > 0 and others % brief.DETAIL_STEP == 0 and bounds["candidates_moved_to_tail"] == 0
    assert bounds["candidates_detailed"] + bounds["candidates_compact"] == 204
    full = brief.build(json.loads(raw), json.loads(PICKS_RAW), raw, PICKS_RAW, MODULES)
    assert len(brief._encode(brief.shape(full, others + brief.DETAIL_STEP, None))) > brief.MAX_JSON_BYTES
    # a compact row is a research row: marked so, with reference levels and never an order
    out, md = json.loads(json_raw), md_raw.decode()
    assert len(out["candidates"]["compact"]) == bounds["candidates_compact"] > 0
    for row in out["candidates"]["compact"]:
        assert row["model_status"] == brief.RESEARCH_SHORT and not any(name.startswith("order") for name in row)
        # derived under the record's own trigger rule: AMD's close plus the cushion
        assert row["trigger"] == plan.burst_trigger(123.27, plan.BURST_TRIGGER_RULE) == 123.39 and "refusal" not in row
    assert "every row RESEARCH ONLY" in section(md, 6) or "RESEARCH ONLY" in md.split("### 6b.")[1].split("\n## ")[0]


def test_the_largest_fitting_step_is_found_and_none_when_nothing_fits():
    assert brief._largest(10, 4, lambda n: True) == 10
    assert brief._largest(10, 4, lambda n: n <= 9) == 8
    assert brief._largest(10, 4, lambda n: n <= 3) == 0
    assert brief._largest(10, 4, lambda n: False) is None
    assert brief._largest(0, 4, lambda n: False) is None
    assert [brief._largest(41, 4, lambda n, cap=cap: n <= cap) for cap in (40, 39, 5, 4)] == [40, 36, 4, 4]


# ------------------------------------------------------------------ (a) service
def test_the_service_block_carries_the_next_publication_and_the_freshness_rule():
    raw, _, json_raw, md_raw = derived("full")
    data, out = json.loads(raw), json.loads(json_raw)
    service = out["service"]
    assert service["expected"] == freshness.expected(data) and service["expected"]["unknown"] == {}
    assert service["freshness_rule"] == list(freshness.RULE) and service["freshness_states"] == list(freshness.STATES)
    window = freshness.morning_window(data)
    assert {k: service["morning"][k] for k in window} == window
    sha = out["identity"]["canonical"]["sha256"]
    assert service["morning"]["receipt"]["must_carry"] == {"publication.data_sha256": sha}
    assert service["morning"]["receipt"]["url"] == brief.SITE_URL + "morning.json"
    assert "`publication.data_sha256` equals `identity.canonical.sha256`" in service["morning"]["receipt"]["rule"]
    # the brief itself carries no "built at" or "is newest": freshness is the reader's computation
    assert not {"built_at", "generated_at", "is_newest", "fresh"} & (set(out) | set(service) | set(out["identity"]))
    md = section(md_raw.decode(), 2)
    assert all(step in md for step in freshness.RULE) and service["expected"]["recovery_until"] in md


def test_the_receipt_binding_is_the_field_the_morning_collector_writes():
    # the receipt names the record's bytes under publication.data_sha256 (morning.bind_record)
    import inspect
    assert '"data_sha256"' in inspect.getsource(morning)
    raw, _, json_raw, _ = derived("full")
    assert json.loads(json_raw)["identity"]["canonical"]["sha256"] == hashlib.sha256(raw).hexdigest()


def test_the_inputs_say_what_they_do_not_establish():
    raw, _, json_raw, md_raw = derived("thin")
    data, out = json.loads(raw), json.loads(json_raw)
    inputs = out["service"]["inputs"]
    assert inputs["unknown"] == brief.input_unknowns(data) and len(inputs["unknown"]) == 4
    assert inputs["price_sources"] == brief.PRICE_SOURCES == 1
    text = " ".join(inputs["unknown"])
    assert "is not established" in text and "One price source" in text and "can be revised afterwards" in text
    assert "does not establish which stocks were listed" in text
    assert inputs["tolerance"]["verdict"] == data["run"]["input_tolerance"]["verdict"]
    assert inputs["tolerance"]["names"] == data["run"]["input_tolerance"]["names"][:brief.STALE_NAMES_MAX]
    assert all(sentence in section(md_raw.decode(), 2) for sentence in inputs["unknown"])


# ------------------------------------------------------------------ (b) the regime rules
RULE_NAMES = ["down4_alarm", "ratio_10d_red", "ratio_5d_red", "ratio_10d_yellow", "up50_month_hot"]


@pytest.mark.parametrize("variant, verdict", [("full", "green"), ("yellow", "yellow"), ("red", "red"), ("thin", "red")])
def test_all_five_regime_rules_are_printed_in_the_order_they_are_asked(variant, verdict):
    raw, _, json_raw, md_raw = derived(variant)
    data, out = json.loads(raw), json.loads(json_raw)
    market, regime = out["market"], data["breadth"]["regime"]
    assert market["verdict"] == verdict == regime["verdict"]
    rules = market["rules"]
    assert [r["rule"] for r in rules] == RULE_NAMES and [r["tier"] for r in rules] == ["red"] * 3 + ["yellow"] * 2
    assert [r["threshold_tonight"] for r in rules] == [regime["thresholds"][name] for name in RULE_NAMES]
    assert [r["scaled"] for r in rules] == [True, False, False, False, True]
    assert rules[0]["reference"] == breadth.DOWN4_ALARM and rules[4]["reference"] == breadth.UP50_MONTH_HOT
    assert rules[0]["reference_universe"] == breadth.REFERENCE_UNIVERSE and rules[1]["reference_universe"] is None
    fired = [r for r in rules if r["fired"]]
    assert all(r["decides"] == (r["tier"] == verdict) and r["masked"] == (r["tier"] != verdict) for r in fired)
    assert not any(r["decides"] or r["masked"] for r in rules if not r["fired"])
    assert (verdict == "green") == (not fired) and (verdict == "green" or any(r["decides"] for r in rules))
    assert market["gate_note"] == brief.GATE_NOTE and "an input to weigh, not an instruction" in brief.GATE_NOTE
    assert "that scaling is this project's own" in brief.SCALING_NOTE
    md = section(md_raw.decode(), 3)
    assert all(f"| {name} |" in md for name in RULE_NAMES) and brief.GATE_NOTE in md and brief.SCALING_NOTE in md
    assert market["green_needs"] in md and market["green_needs"].startswith("GREEN needs all five rules quiet")


def regime_of(data: dict, **inputs) -> None:
    data["breadth"]["regime"]["inputs"].update(inputs)


def test_a_fired_yellow_rule_under_a_red_night_is_masked_and_the_raw_sums_are_printed():
    def red(data):
        regime_of(data, ratio_10d=0.86, up4_10d=86, down4_10d=100, up50_month=5)
        data["breadth"]["regime"]["verdict"] = "red"
    _, out, md, why = changed(red)
    assert why is None
    rules = {r["rule"]: r for r in out["market"]["rules"]}
    assert (rules["ratio_10d_red"]["fired"], rules["ratio_10d_red"]["decides"], rules["ratio_10d_red"]["masked"]) == (True, True, False)
    assert (rules["ratio_10d_yellow"]["fired"], rules["ratio_10d_yellow"]["decides"], rules["ratio_10d_yellow"]["masked"]) == (True, False, True)
    assert (rules["up50_month_hot"]["fired"], rules["up50_month_hot"]["masked"]) == (True, True)
    assert rules["down4_alarm"]["fired"] is False
    sums = out["market"]["sums"]
    assert (sums["up4_10d"], sums["down4_10d"], sums["ratio_10d_published"], sums["ratio_10d_unrounded"]) == (86, 100, 0.86, 0.86)
    assert out["market"]["flags"]["yellow_by_rounding"] is False       # red by its ratio, which rounding did not rescue


def test_each_rule_fires_exactly_at_its_boundary_as_the_breadth_module_compares():
    def night(**inputs):
        def apply(data):
            regime_of(data, **inputs)
            th = data["breadth"]["regime"]["thresholds"]
            i = data["breadth"]["regime"]["inputs"]
            red = (i["down4"] >= th["down4_alarm"] or (i["ratio_10d"] is not None and i["ratio_10d"] < th["ratio_10d_red"])
                   or (i["ratio_5d"] is not None and i["ratio_5d"] < th["ratio_5d_red"] and i["down4"] > i["up4"]))
            data["breadth"]["regime"]["verdict"] = "red" if red else "yellow"      # every case below is at least yellow
        _, out, _, why = changed(apply)
        assert why is None, why
        return [r["rule"] for r in out["market"]["rules"] if r["fired"]], out["market"]["verdict"]
    th = json.loads(FULL_RAW)["breadth"]["regime"]["thresholds"]
    assert th["ratio_10d_red"] == breadth.RED_RATIO_10D and th["ratio_10d_yellow"] == breadth.YELLOW_RATIO_10D
    assert th["ratio_5d_red"] == breadth.RED_RATIO_5D
    assert night(ratio_10d=th["ratio_10d_yellow"] - 0.01) == (["ratio_10d_yellow"], "yellow")
    assert night(ratio_10d=th["ratio_10d_red"]) == (["ratio_10d_yellow"], "yellow")          # at the red line: not under it
    assert night(ratio_10d=th["ratio_10d_red"] - 0.01) == (["ratio_10d_red", "ratio_10d_yellow"], "red")
    assert night(down4=th["down4_alarm"], ratio_10d=1.5) == (["down4_alarm", "ratio_10d_yellow"], "red")    # at the alarm: fired
    assert night(up50_month=th["up50_month_hot"] + 1, ratio_10d=1.5) == (["ratio_10d_yellow", "up50_month_hot"], "yellow")
    assert night(up50_month=th["up50_month_hot"], ratio_10d=1.5) == (["ratio_10d_yellow"], "yellow")     # at the hot mark: not over it
    assert night(down4=th["down4_alarm"] - 0.1, ratio_10d=1.5) == (["ratio_10d_yellow"], "yellow")       # just under the alarm
    # the 5-session rule needs both halves: a low ratio and more names down than up today
    assert night(ratio_5d=0.4, ratio_10d=1.5, down4=1, up4=0) == (["ratio_5d_red", "ratio_10d_yellow"], "red")
    assert night(ratio_5d=0.4, ratio_10d=1.5, down4=1, up4=1) == (["ratio_10d_yellow"], "yellow")
    assert night(ratio_10d=None, ratio_5d=None, up50_month=th["up50_month_hot"] + 1) == (["up50_month_hot"], "yellow")


def test_a_record_whose_verdict_is_not_what_its_own_inputs_give_is_refused():
    def forge(data):
        data["breadth"]["regime"]["verdict"] = "red"
    data, out, md, why = changed(forge)
    assert why == "the regime rules re-derived from the record's own inputs give green, and the record says red"
    assert out["status"] == "unavailable" and why in out["reason"] and "market" not in out
    assert "unavailable" in md.splitlines()[0]


def test_yellow_by_rounding_and_near_a_line_are_flagged_and_gate_nothing():
    def rounding(data):
        regime_of(data, ratio_10d=1.0, up4_10d=399, down4_10d=400)        # 0.9975 unrounded: more breakdowns than breakouts
        data["breadth"]["regime"]["verdict"] = "yellow"
    _, out, md, why = changed(rounding)
    assert why is None
    flags, sums = out["market"]["flags"], out["market"]["sums"]
    assert flags["yellow_by_rounding"] is True and sums["ratio_10d_unrounded"] == 0.9975 and sums["ratio_10d_published"] == 1.0
    assert flags["near_line"]["inside_band"] is True and flags["near_line"]["to_red_line"] == 0.0
    assert flags["near_line"]["band"] == brief.NEAR_LINE_BAND and "it is not a rule and gates nothing" in flags["near_line"]["note"]
    assert "Yellow by rounding" in section(md, 3) and ": yes." in section(md, 3)
    _, plain, _, _ = changed(lambda data: None)
    assert plain["market"]["flags"]["yellow_by_rounding"] is False and plain["market"]["flags"]["near_line"]["inside_band"] is False

    def edge(data):
        regime_of(data, ratio_10d=round(2.0 + brief.NEAR_LINE_BAND + 0.01, 2))
    _, outside, _, _ = changed(edge)
    assert outside["market"]["flags"]["near_line"]["inside_band"] is False

    def inside(data):
        regime_of(data, ratio_10d=round(2.0 + brief.NEAR_LINE_BAND, 2))
    _, at_band, _, _ = changed(inside)
    assert at_band["market"]["flags"]["near_line"]["inside_band"] is True


def test_a_record_without_the_regimes_inputs_gets_no_rules_and_the_reason():
    def older(data):
        data["breadth"]["regime"].pop("inputs")
    _, out, md, why = changed(older)
    assert why is None and out["market"]["rules"] is None
    assert "does not carry the regime's inputs" in out["market"]["rules_unavailable"]
    assert out["market"]["rules_unavailable"] in section(md, 3)


# ------------------------------------------------------------------ (c) events
def test_the_registry_is_read_as_archived_with_its_age_and_overdue_reviews():
    def overdue(data):
        synthetic_registry(data, [synthetic_event("SYNA", "2026-08-10", "2026-08-20", "2026-09-01"),   # due nine days before
                                  synthetic_event("SYNB", "2026-08-11", "2026-08-31", "2026-09-10"),   # due on the session
                                  synthetic_event("SYNC", "2026-08-12", "2026-08-31", "2026-09-20")],
                           reviewed="2026-08-31")
    data, out, md, why = changed(overdue)
    assert why is None
    registry = out["events"]["registry"]
    assert registry["reviewed_on"] == "2026-08-31" and registry["age_days"] == 10
    assert registry["overdue"] == [{"symbol": "SYNA", "review_due": "2026-09-01", "days_overdue": 9}]
    assert registry["entries"] == 3 == len(registry["events"]) and registry["next_review_due"] == "2026-09-10"
    assert "1 of 3 unresolved entries are past their review date: SYNA 9 days" in out["events"]["sentence"]
    assert "last reviewed 2026-08-31, 10 days before the measured session 2026-09-10." in out["events"]["sentence"]
    assert "this record does not establish its current status" in out["events"]["sentence"]
    assert out["events"]["sentence"] in section(md, 11)
    # today's registry file is never consulted: the entries the working tree's file names are not in the brief
    today = json.loads((ROOT / "knowledge" / "event-risk.json").read_text())["events"]
    assert today and not {e["symbol"] for e in today} & {e["symbol"] for e in registry["events"]}


def test_a_listed_name_the_registry_matches_is_named_even_when_its_row_was_not_flagged():
    def late_entry(data):
        synthetic_registry(data, [synthetic_event("AMD"), synthetic_event("COIL", "2026-09-02"),
                                  synthetic_event("PLUG", "2026-09-11", "2026-09-12")], reviewed="2026-09-12")
    data, out, md, why = changed(late_entry)
    assert why is None
    matches = {(m["stage"], m["ticker"]): m for m in out["events"]["listed_matches"]}
    assert set(matches) == {("bursts", "AMD"), ("setting_up", "COIL")}       # PLUG's entry starts after the session
    amd = matches[("bursts", "AMD")]
    assert amd["status"] == "known_event" and amd["flagged_in_the_record"] is False and amd["has_plan"] is True
    assert "SYNTHETIC: a pending cash acquisition" in amd["reason"]
    assert amd["sources"] == [{"title": "SYNTHETIC source", "published_on": "2026-09-01", "url": "https://example.invalid/synthetic"}]
    assert "2 of the 8 listed rows" in out["events"]["sentence"]
    assert "AMD (bursts, known_event, not flagged on its row in the record)" in out["events"]["sentence"]
    assert "**AMD**" in section(md, 11) and "not flagged on its row in the record" in section(md, 11)
    expected = event_risk.classify("AMD", date(2026, 9, 10), registry=data["rules"]["event_risk"]["registry"])
    assert amd["status"] == expected["status"] and expected["blocked"] is True


def test_an_also_quiet_name_the_registry_matches_is_named():
    """An also-quiet coil has no plan, so its row carries no event block at all: this is the only place a reader
    learns it is a known deal. (In the real record: ZIM, also quiet and in the registry, on 2 November 2026.)
    The `next` fixture night lists one also-quiet row, VRT, which is in no other list."""
    def deal(data):
        synthetic_registry(data, [synthetic_event("VRT"), synthetic_event("ZZZZ")])
    data, out, md, why = changed_in("next", deal)
    assert why is None
    assert [(r["ticker"], bool(r.get("plan"))) for r in data["watchlist"]["also_quiet"]] == [("VRT", False)]
    assert "VRT" not in {r["ticker"] for r in data["bursts"] + data["watchlist"]["top"]}
    events = out["events"]
    assert events["listed"]["also_quiet"] == 1
    assert [(m["stage"], m["ticker"]) for m in events["listed_matches"]] == [("also_quiet", "VRT")]   # ZZZZ is listed nowhere
    match = events["listed_matches"][0]
    assert (match["status"], match["has_plan"], match["flagged_in_the_record"]) == ("known_event", False, False)
    assert "SYNTHETIC: a pending cash acquisition" in match["reason"]
    total = sum(events["listed"].values())
    assert (f"1 of the {total} listed rows ({events['listed']['bursts']} bursts, {events['listed']['setting_up']} "
            "setting up, 1 also quiet) are in the registry: VRT (also quiet, known_event, not flagged on its row in "
            "the record).") in events["sentence"]
    assert "**VRT**" in section(md, 11)
    quiet = next(r for r in out["setting_up"]["also_quiet"] if r["ticker"] == "VRT")
    assert "event" not in quiet                                # the row itself says nothing: the events block does
    expected = event_risk.classify("VRT", date.fromisoformat(data["run"]["session"]),
                                   registry=data["rules"]["event_risk"]["registry"])
    assert expected["blocked"] is True and match["status"] == expected["status"]
    # the control: the same night with the registry naming no listed stock matches nothing
    _, clean, _, why = changed_in("next", lambda d: synthetic_registry(d, [synthetic_event("ZZZZ")]))
    assert why is None and clean["events"]["listed_matches"] == []
    assert f"None of the {total} listed rows" in clean["events"]["sentence"]


def test_coverage_is_counted_and_no_name_is_ever_called_clear():
    raw, _, json_raw, md_raw = derived("full")
    out, md = json.loads(json_raw), md_raw.decode()
    events = out["events"]
    assert events["listed"] == {"bursts": 7, "setting_up": 1, "also_quiet": 0}
    assert events["earnings"]["listed_names"] == 8 and events["earnings"]["listed_names_not_checked"] == 7
    assert events["earnings"]["ticket_rows"] == 1 and events["earnings"]["status"] == "checked"
    assert events["not_checked"] == list(brief.NOT_CHECKED) and len(brief.NOT_CHECKED) == 9
    assert events["status_words"] == brief.EVENT_STATUS_WORDS
    assert "NOT a clearance" in brief.EVENT_STATUS_WORDS["not_in_registry"]
    assert "has not been cleared" in events["sentence"]
    lowered = (json_raw.decode() + md).lower()
    assert not re.search(r"\b(is|are|was|were|reads?) clear\b", lowered.replace("never clear", "").replace("not clear", ""))
    assert "cleared for" not in lowered and '"clear"' not in lowered
    _, older, md_older, why = changed(lambda data: data["rules"].pop("event_risk"))
    assert why is None and older["events"]["registry"] is None and older["events"]["listed_matches"] is None
    assert "This record predates the event registry: no listed row was read against one." in older["events"]["sentence"]


def test_an_archived_registry_this_code_cannot_validate_matches_no_row_and_says_so():
    def broken(data):
        synthetic_registry(data, [synthetic_event("AMD")])
        data["rules"]["event_risk"]["registry"]["events"][0]["evidence_as_of"] = "2026-09-05"     # no source says so
    data, out, md, why = changed(broken)
    assert why is None
    with pytest.raises(ValueError):
        event_risk.classify("AMD", date(2026, 9, 10), registry=data["rules"]["event_risk"]["registry"])
    assert out["events"]["listed_matches"] is None
    assert "does not validate under this code" in out["events"]["sentence"]
    assert "treat every listed name as unchecked" in out["events"]["sentence"]


# ------------------------------------------------------------------ (d) rules and the volume boundary
def test_the_rules_digest_and_the_digest_without_the_membership_identity():
    raw, _, json_raw, _ = derived("full")
    data, rules = json.loads(raw), json.loads(json_raw)["rules"]
    assert rules["digest"] == data["app"]["rules_version"] == report.rules_version(data["rules"]) == brief.rules_digest(data["rules"])
    stripped = copy.deepcopy(data["rules"])
    identity = stripped["universe"].pop("identity")
    assert rules["membership_identity"] == identity
    assert rules["digest_without_membership"] == report.rules_version(stripped) != rules["digest"]
    # the membership moves and only the first digest follows it
    moved = copy.deepcopy(data)
    moved["rules"]["universe"]["identity"] = "0" * len(identity)
    assert report.rules_version(moved["rules"]) != rules["digest"]
    assert brief.rules_block(moved)["digest_without_membership"] == rules["digest_without_membership"]


@pytest.mark.parametrize("ratio, expected", [(1.0, True), (1.05, True), (0.95, True), (1.06, False), (0.94, False),
                                             (5.0, False), (None, None), ("1.0", None), (True, None)])
def test_a_volume_within_the_band_of_the_previous_sessions_is_marked(ratio, expected):
    assert brief.near_volume_boundary({"volume_vs_prior": ratio}) is expected


def test_the_near_volume_mark_is_on_the_row_and_counted_and_labelled_the_projects_own():
    def near(data):
        burst(data, "NVDA")["volume_vs_prior"] = 1.03
        burst(data, "PLUG")["volume_vs_prior"] = 0.98
    _, out, md, why = changed(near)
    assert why is None
    assert detailed(out, "NVDA")["bar"]["near_volume_boundary"] is True
    assert detailed(out, "AMD")["bar"]["near_volume_boundary"] is False
    block = out["candidates"]["near_volume_boundary"]
    assert block["band"] == brief.NEAR_VOLUME_BAND == 0.05 and block["bursts_inside"] == 2
    assert "this project's own label, not a rule" in block["meaning"]
    assert "2 of the discovered bursts have a volume within 0.05" in section(md, 6)


# ------------------------------------------------------------------ (e) the order-entry block
def test_a_burst_tickets_order_entry_block_states_the_order_and_what_is_not_the_ticket():
    raw, _, json_raw, md_raw = derived("full")
    data, out = json.loads(raw), json.loads(json_raw)
    recorded, entry = burst(data, "AAPL")["plan"], out["tickets"][0]["order_entry"]
    assert entry["order_kind"] == brief.ORDER_KIND == "buy_stop_limit_oto"
    assert recorded["order_json"]["order_type"] == "stop_limit" and recorded["order_json"]["conditional"] == plan.OTO
    assert entry["lines"] == {"stop": recorded["stop"], "skip_below": recorded["skip_if_open_below"],
                              "trigger": recorded["entry_ref"], "limit": recorded["limit"],
                              "day2_line": recorded["day2_spent_above"], "extended_above": recorded["extended_above"]}
    # a ticket made under the production trigger rule: its buy stop sits a cushion over the last close
    assert entry["last_close"] == burst(data, "AAPL")["close"] < entry["lines"]["trigger"]
    assert entry["lines"]["trigger"] == plan.burst_trigger(entry["last_close"], plan.BURST_TRIGGER_RULE)
    assert entry["buy_stop_vs_last_close"] == "above" and "buy_stop_note" not in entry
    assert entry["record_action_word"] == recorded["action"] == "buy_at_open"
    assert "legacy word" in entry["record_action_note"] and "never means a market-on-open order" in entry["record_action_note"]
    assert entry["shares"] == recorded["shares"] and entry["entry_window"]["opens_at"] == data["run"]["timing"]["opens_at"]
    assert entry["not_the_ticket"]["label"].startswith("not the ticket")
    assert entry["not_the_ticket"]["reader_entry_note"] == burst(data, "AAPL")["claude"]["entry_note"]
    md = section(md_raw.decode(), 5)
    assert "the buy stop is `above` the last close" in md and "record action word `buy_at_open` (legacy)" in md
    assert "Reader's entry note (not the ticket)" in md


def test_a_setting_up_tickets_buy_stop_is_above_the_last_close_and_its_open_entry_note_is_not_the_ticket():
    raw, _, json_raw, md_raw = derived("notrade")
    data, out = json.loads(raw), json.loads(json_raw)
    ticket = next(t for t in out["tickets"] if t["stage"] == "anticipation")
    row = next(r for r in data["watchlist"]["top"] if r["ticker"] == ticket["ticker"])
    entry = ticket["order_entry"]
    assert entry["buy_stop_vs_last_close"] == "above" and entry["lines"]["trigger"] > entry["last_close"] == row["close"]
    assert "above_day2_extension" not in [s["state"] for s in entry["price_states"] if s["applies"]]
    assert entry["not_the_ticket"]["open_entry"] == row["plan"]["open_entry"]
    assert "Open-entry note (not the ticket)" in section(md_raw.decode(), 5)


def test_the_buy_stop_note_is_a_burst_tickets_and_never_on_a_buy_stop_over_the_close():
    """The note says a broker takes a buy stop only above the current price. It belongs to a ticket whose buy stop
    IS its last close: a burst ticket made before plan.burst_trigger_rule. A burst ticket made under
    close_plus_cushion, like an anticipation ticket, has its buy stop above its last close, the right side of the
    market, and carries no note."""
    for variant in ("full", "yellow", "next"):
        raw, _, json_raw, _ = derived(variant)
        data, bursts = json.loads(raw), [t for t in json.loads(json_raw)["tickets"] if t["stage"] == "burst"]
        assert bursts
        for ticket in bursts:
            entry = ticket["order_entry"]
            assert entry["buy_stop_vs_last_close"] == "above" and "buy_stop_note" not in entry
        # the same ticket as a record made before the rule carries it: its buy stop back at its close
        row = burst(data, bursts[0]["ticker"])
        legacy = {**row["plan"], "entry_ref": row["plan"]["burst"]["close"]}
        entry = brief.order_entry("burst", row, legacy, data)
        assert entry["buy_stop_vs_last_close"] == "equal" and entry["buy_stop_note"] == brief.BUY_STOP_NOTE
    for variant in ("notrade", "degraded"):
        raw, _, json_raw, _ = derived(variant)
        data, out = json.loads(raw), json.loads(json_raw)
        coils = [t for t in out["tickets"] if t["stage"] == "anticipation"]
        assert coils and len(coils) == len(out["tickets"])
        for ticket in coils:
            entry = ticket["order_entry"]
            assert entry["buy_stop_vs_last_close"] == "above" and entry["lines"]["trigger"] > entry["last_close"]
            assert "buy_stop_note" not in entry, "an anticipation ticket's buy stop is over its close: no note"
    # the block alone, the same ticket with its last close moved: the note is the `equal` case's and no other's
    row = next(r for r in data["watchlist"]["top"] if r["ticker"] == coils[0]["ticker"])
    trigger = row["plan"]["trigger"]
    for close, word in ((trigger, "equal"), (round(trigger - 0.5, 2), "above"), (round(trigger + 0.5, 2), "below")):
        entry = brief.order_entry("anticipation", row, {**row["plan"], "close": close}, data)
        assert entry["buy_stop_vs_last_close"] == word
        assert entry.get("buy_stop_note") == (brief.BUY_STOP_NOTE if word == "equal" else None)


# `next` is the one fixture whose burst ticket has its stop OVER its skip-under line (131.38 against 131.31), the
# shape a third of counterfactual burst tickets have: there no price is `below_entry_floor`.
@pytest.mark.parametrize("variant, stage", [("full", "burst"), ("notrade", "anticipation"), ("next", "burst")])
def test_the_price_states_are_the_morning_receipts_words_at_every_boundary(variant, stage):
    raw, _, json_raw, _ = derived(variant)
    data, out = json.loads(raw), json.loads(json_raw)
    ticket = next(t for t in out["tickets"] if t["stage"] == stage)
    rows = data["bursts"] if stage == "burst" else data["watchlist"]["top"]
    recorded = next(r for r in rows if r["ticker"] == ticket["ticker"])["plan"]
    # the morning collector's own mapping of a plan onto its levels (morning.bind_record)
    levels = {"trigger": recorded["entry_ref"] if stage == "burst" else recorded["trigger"],
              "limit": recorded["limit"], "stop": recorded["stop"],
              "entry_low": recorded.get("entry_low") if stage == "burst" else recorded["trigger"],
              "day2_spent_above": recorded.get("day2_spent_above") if stage == "burst" else None}
    states = [s for s in ticket["order_entry"]["price_states"] if s["applies"]]
    assert [s["state"] for s in ticket["order_entry"]["price_states"]] == list(brief.PRICE_STATES)
    assert set(brief.PRICE_STATES) | {"unknown"} == set(morning.PRICE_STATES)

    def word(price):
        inside = [s["state"] for s in states
                  if (s["from"] is None or price > s["from"] or (s["from_inclusive"] and price == s["from"]))
                  and (s["to"] is None or price < s["to"] or (s["to_inclusive"] and price == s["to"]))]
        assert len(inside) == 1, (price, inside)             # the ranges tile the line: no gap, no overlap
        return inside[0]
    edges = sorted({v for v in levels.values() if v is not None})
    prices = sorted({round(edge + step, 2) for edge in edges for step in (-0.01, 0.0, 0.01)} | {0.01, edges[-1] * 3})
    assert [word(p) for p in prices] == [morning.price_state(p, levels, "recent") for p in prices]
    assert len({word(p) for p in prices}) == len(states)      # every applicable word was reached


def test_a_stop_over_the_skip_line_leaves_no_entry_floor_state_and_says_so():
    states = {s["state"]: s for s in brief.price_states(131.38, 131.31, 133.99, 136.85, 139.35)}
    assert states["below_entry_floor"]["applies"] is False
    assert states["below_entry_floor"]["note"] == brief.STOP_OVER_FLOOR_NOTE
    assert (states["below_trigger"]["from"], states["below_trigger"]["from_inclusive"]) == (131.38, False)
    assert states["below_stop"]["to"] == 131.38 and states["below_stop"]["to_inclusive"] is True
    # the usual shape, and a stop exactly on the line (no price lies strictly between them either)
    usual = {s["state"]: s for s in brief.price_states(120.0, 122.0, 125.0, 127.0, 130.0)}
    assert usual["below_entry_floor"]["applies"] is True
    assert (usual["below_trigger"]["from"], usual["below_trigger"]["from_inclusive"]) == (122.0, True)
    on_line = {s["state"]: s for s in brief.price_states(122.0, 122.0, 125.0, 127.0, 130.0)}
    assert on_line["below_entry_floor"]["applies"] is False and on_line["below_trigger"]["from_inclusive"] is False
    _, _, json_raw, md_raw = derived("next")
    over = [t for t in json.loads(json_raw)["tickets"]
            if t["stage"] == "burst" and t["levels"]["stop"] >= t["order_entry"]["lines"]["skip_below"]]
    assert over, "the `next` fixture carries a burst ticket whose stop is over its skip-under line"
    line = next(l for l in section(md_raw.decode(), 5).split("### " + over[0]["ticker"])[1].splitlines()
                if l.startswith("- Price states:"))
    assert "`below_entry_floor`" not in line and "`below_trigger` over $" in line   # an inapplicable state is not a range


def test_an_anticipation_tickets_gap_line_says_what_the_record_says():
    """The plan's field is named ``gap_ok_above``; the record's rule is that an open OVER that price is gapped and
    needs a catalyst check. The brief prints the rule, never the humanised field name."""
    raw, _, json_raw, md_raw = derived("notrade")
    data, out = json.loads(raw), json.loads(json_raw)
    ticket = next(t for t in out["tickets"] if t["stage"] == "anticipation")
    recorded = next(r for r in data["watchlist"]["top"] if r["ticker"] == ticket["ticker"])["plan"]
    entry = ticket["order_entry"]
    assert entry["gap_rule"] == recorded["gap_rule"] and "catalyst check" in entry["gap_rule"]
    assert entry["lines"]["gap_check_above"] == recorded["gap_ok_above"] and "gap_ok_above" not in entry["lines"]
    md = section(md_raw.decode(), 5)
    assert "gap ok above" not in md_raw.decode()
    assert f"an open over ${recorded['gap_ok_above']:,.2f} is gapped and the plan asks for a catalyst check" in md
    assert f"The record's gap rule: \"{recorded['gap_rule']}\"" in md
    burst = next(t for t in json.loads(derived("full")[2])["tickets"] if t["stage"] == "burst")
    assert "gap_rule" not in burst["order_entry"] and "gap_check_above" not in burst["order_entry"]["lines"]


def test_the_bars_instant_is_the_runs_start_and_the_directorys_capture_is_named_as_its_own():
    """``run.universe.fetched_at`` is when the stock directory was captured, which on a cached-directory night is
    days before the session. The bars were read by the run, whose start is ``run.published_at``."""
    data = json.loads(FULL_RAW)
    data["run"]["universe"]["fetched_at"] = "2026-01-01T00:00:00+00:00"     # SYNTHETIC: an old directory snapshot
    raw = (json.dumps(data, indent=1) + "\n").encode()
    json_raw, md_raw, why = brief.compose(raw, PICKS_RAW)
    assert why is None
    out = json.loads(json_raw)
    started = data["run"]["published_at"]
    assert out["service"]["inputs"]["run_started_at"] == started and "fetched_at" not in out["service"]["inputs"]
    assert out["service"]["universe"]["directory_captured_at"] == "2026-01-01T00:00:00+00:00"
    md = md_raw.decode()
    assert f"read by the run that began {started}" in md
    assert any(f"as read by the run that began at {started}" in s for s in out["service"]["inputs"]["unknown"])
    inputs_line = next(l for l in md.splitlines() if l.startswith("- Inputs:"))
    assert "2026-01-01T00:00:00" not in inputs_line and "read by the run that began" in inputs_line


def test_the_fixed_sentences_say_what_the_file_does():
    assert "model-record block" in brief.READ_FIRST[0] and "from nothing else" in brief.READ_FIRST[0]
    limits = " ".join(brief.LIMITS)
    assert "No price here is a live quote" in limits and "Every price is the measured session's bar" not in limits
    assert "Research levels are never tickets" in limits and "`plan_rule_eligible` false" in limits
    assert "can still be published again" in freshness.RULE[1] and "`identity.canonical.sha256`" in freshness.RULE[1]
    assert "`identity.entry_window.opens_at`" in freshness.RULE[-1] and "`cutoff_at`" in freshness.RULE[-1]
    out = json.loads(derived("full")[2])
    assert out["identity"]["entry_window"]["opens_at"] and out["identity"]["entry_window"]["cutoff_at"]
    bounds = out["bounds"]
    assert bounds["breadth_history_sessions"] == len(out["market"]["history"]) <= brief.HISTORY_DAYS
    assert all(bounds[name] for name in ("stale_names_rule", "also_quiet_rule", "breadth_history_rule"))
    md = derived("full")[3].decode()
    assert "not an instruction to the reader" in section(md, 9)


def test_the_tail_names_the_rows_moved_out_for_size_first_so_the_cap_cuts_the_lowest_ranks():
    moved_reason = "in the trade band and admitted; its row was left out for size"
    probe = {"candidates": {"_rows": [{"class": "candidate", "ticker": f"MOV{i}", "grade_mechanical": "A", "grade": "A"}
                                      for i in range(3)]},
             "_tail": [("a grade below the band", f"LOW{i}", "B", "B") for i in range(brief.TAIL_MAX)],
             "open_plans": {"rows_left_out": 0}, "pick_ledger": {}, "service": {"inputs": {}},
             "setting_up": {"also_quiet_left_out": 0}, "market": {"history": []}, "model_record": {}}
    shaped = brief.shape(probe, 0, 0)
    groups = shaped["research_tail"]["groups"]
    assert groups[0]["reason"] == moved_reason and groups[0]["tickers"] == ["MOV0", "MOV1", "MOV2"]
    assert shaped["research_tail"]["left_out"] == 3
    assert shaped["research_tail"]["left_out_by_reason"] == {"a grade below the band": 3}
    assert groups[1]["tickers"][-1] == f"LOW{brief.TAIL_MAX - 4}"      # the three lowest ranks are the ones cut


# ------------------------------------------------------------------ (f) model status and the later gates
def test_a_red_night_does_not_hide_which_names_would_pass_the_later_gates():
    raw, _, json_raw, md_raw = derived("red")
    data, out = json.loads(raw), json.loads(json_raw)
    assert out["tickets"] == [] and out["market"]["admits_grades"] == []
    rows = {r["ticker"]: r for r in out["candidates"]["detailed"]}
    aapl = rows["AAPL"]["would_pass"]
    assert rows["AAPL"]["model_status"] == brief.RESEARCH_ONLY
    assert aapl["grade_band_green"] is True and aapl["no_veto"] is True and aapl["admission"] is True
    assert aapl["every_later_gate_green"] == (aapl["grade_band_green"] and aapl["no_veto"] and aapl["admission"]
                                              and aapl["reader_accepted"])
    assert "passing them is not a ticket" in out["candidates"]["would_pass_note"]
    assert "RESEARCH ONLY: no SpicyStock ticket" in section(md_raw.decode(), 6)
    assert "TICKET (order and schedule in section 5)" not in md_raw.decode()


@pytest.mark.parametrize("variant", VARIANTS)
def test_the_hold_days_start_on_the_applicable_session_and_never_on_the_measured_one(variant):
    """Day 1 is the entry day: the session after the measured one, which is the applicable session the record's
    timing names and the day 1 every ticket's own schedule is dated. The measured session is in no hold day."""
    raw, _, json_raw, md_raw = derived(variant)
    data, out = json.loads(raw), json.loads(json_raw)
    measured, days = data["run"]["session"], out["candidates"]["schedule_days"]
    dates = [day["date"] for day in days]
    assert [day["day"] for day in days] == list(range(plan.ENTRY_DAY, plan.FINAL_EXIT_DAY + 1))
    assert dates[0] == out["identity"]["applicable_session"] == data["run"]["timing"]["applicable_session"]
    assert measured not in dates and dates == sorted(dates) and dates[0] > measured
    # the exchange's own sessions after the measured one, as plan.dated_schedule() dates a ticket
    assert dates == [str(day) for day in plan.next_sessions(date.fromisoformat(measured), plan.FINAL_EXIT_DAY)]
    assert f"Hold days for a plan entered on the applicable session: day 1 = {dates[0]}, day 2 = {dates[1]}" in md_raw.decode()
    for ticket in out["tickets"]:
        dated = {step["day"]: step["date"] for step in ticket["schedule"]}
        assert all(dates[day - 1] == when for day, when in dated.items()), ticket["ticker"]


def test_the_hold_days_are_the_calendars_sessions_strictly_after_the_measured_one():
    sessions = [{"session": day} for day in ("2026-09-09", "2026-09-10", "2026-09-11", "2026-09-14", "2026-09-15")]
    data = {"run": {"session": "2026-09-10", "calendar": {"schedule": {"sessions": sessions}}}}
    assert brief.schedule_days(data, 5) == [{"day": 1, "date": "2026-09-11"}, {"day": 2, "date": "2026-09-14"},
                                            {"day": 3, "date": "2026-09-15"}]
    assert brief.schedule_days(data, 2) == [{"day": 1, "date": "2026-09-11"}, {"day": 2, "date": "2026-09-14"}]
    assert brief.schedule_days({"run": {"session": "2026-09-10"}}, 5) == []          # no calendar: no day is guessed


def test_the_later_gates_are_the_planners_own_readings():
    trade, yellow = ["A+", "A"], ["A+"]
    base = {"grade": "A", "vetoes": [], "admission": {"admitted": True}, "reader_coverage": "accepted"}
    out = brief.would_pass(base, trade, yellow, admission)
    assert (out["grade_band_green"], out["grade_band_yellow"], out["no_veto"], out["admission"], out["reader_accepted"]) == \
        (True, False, True, True, True)
    assert out["every_later_gate_green"] is True and out["every_later_gate_yellow"] is False
    assert brief.would_pass({**base, "vetoes": ["up_run"]}, trade, yellow, admission)["every_later_gate_green"] is False
    assert brief.would_pass({**base, "admission": {"admitted": False}}, trade, yellow, admission)["every_later_gate_green"] is False
    assert brief.would_pass({**base, "reader_coverage": "fallback"}, trade, yellow, admission)["every_later_gate_green"] is False
    assert brief.would_pass({**base, "grade": "B"}, trade, yellow, admission)["every_later_gate_green"] is False
    plus = brief.would_pass({**base, "grade": "A+"}, trade, yellow, admission)
    assert plus["every_later_gate_green"] is True and plus["every_later_gate_yellow"] is True
    assert brief.would_pass(base, trade, yellow, admission)["admission"] is admission.admitted(base)


def test_a_setting_up_row_without_a_ticket_is_research_only_with_labelled_levels():
    raw, _, json_raw, md_raw = derived("full")
    row = json.loads(json_raw)["setting_up"]["listed"][0]
    assert row["ticker"] == "COIL" and row["model_status"] == brief.RESEARCH_ONLY and row["ticket"] is False
    assert row["research_levels_label"] == "the record's own plan for this setup; SpicyStock offers no order at these levels"
    assert row["research_levels"]["trigger"] == 110.61 and row["research_levels"]["source"] == "record"
    assert row["why_no_ticket"].startswith("the 4-slot model cap") and row["stage"] == "allocation_slot"
    md = section(md_raw.decode(), 8)
    assert "### COIL · listed 1 · RESEARCH ONLY: no SpicyStock ticket" in md
    assert "research levels (record; no order is offered at them)" in md and "Open-entry note (not the ticket)" in md


# ------------------------------------------------------------------ (g) the carried model record
def test_the_pick_ledger_reconciles_only_when_its_window_holds_what_the_scorecard_counted():
    """`reconciles` is a comparison: the picks dated inside the scorecard's own window against the plans the
    scorecard counted. It is true on the fixture night (48 and 48) and false three ways."""
    raw, picks_raw, json_raw, _ = derived("full")
    data, picks = json.loads(raw), json.loads(picks_raw)
    window, ledger = data["scorecard"]["population"], json.loads(json_raw)["pick_ledger"]
    assert (ledger["retained"], ledger["in_scorecard_window"], ledger["scorecard_plans"], ledger["reconciles"]) == \
        (len(picks["picks"]), 48, data["scorecard"]["plans"], True)

    def with_picks(rows) -> dict:
        json_out, _, why = brief.compose(raw, encoded({**picks, "picks": rows}))
        assert why is None
        return json.loads(json_out)["pick_ledger"]
    # a pick the scorecard counted is gone from the file
    fewer = with_picks(picks["picks"][1:])
    assert (fewer["retained"], fewer["in_scorecard_window"], fewer["scorecard_plans"], fewer["reconciles"]) == (47, 47, 48, False)
    # every pick is retained, and one is dated the day before the window opens
    before = (date.fromisoformat(window["from"]) - timedelta(days=1)).isoformat()
    moved = with_picks([{**picks["picks"][0], "date": before}, *picks["picks"][1:]])
    assert (moved["retained"], moved["in_scorecard_window"], moved["scorecard_plans"], moved["reconciles"]) == (48, 47, 48, False)
    # the file is whole and the scorecard says it counted one more
    _, out, _, why = changed(lambda d: d["scorecard"].update(plans=d["scorecard"]["plans"] + 1))
    assert why is None
    more = out["pick_ledger"]
    assert (more["in_scorecard_window"], more["scorecard_plans"], more["reconciles"]) == (48, 49, False)
    # the function alone: a window that holds two picks against a scorecard that counted two, then three
    two = {"picks": [{"ticker": "AAA", "date": "2026-09-01"}, {"ticker": "BBB", "date": "2026-09-02"},
                     {"ticker": "CCC", "date": "2026-08-01"}]}
    card = {"plans": 2, "population": {"from": "2026-09-01", "through": "2026-09-10"}}
    assert brief.ledger(two, card)["reconciles"] is True and brief.ledger(two, {**card, "plans": 3})["reconciles"] is False
    assert brief.ledger(two, {"plans": 0})["reconciles"] is True and brief.ledger(two, {"plans": 3})["reconciles"] is False


def test_no_block_supplied_says_it_is_computed_only_inside_an_evening_run():
    _, _, json_raw, md_raw = derived("full")
    assert json.loads(json_raw)["model_record"] == {
        "status": "not_computed", "reason": "computed only inside an evening run, from that run's fetched bars"}
    assert json.loads(json_raw)["bounds"]["model_record_carried"] is False
    assert "- Model-record block: not computed (computed only inside an evening run" in section(md_raw.decode(), 10)


def test_a_computed_block_is_carried_verbatim_and_rendered_without_knowing_its_tables():
    data = json.loads(FULL_RAW)
    block = agreeing_block(
        data, plans=[{"ticker": "SYNA", "picked": "2026-09-01", "bucket": "settled", "r": -1.0, "evidence_id": "e" * 64,
                      "sales": [{"shares": 2}]}],
        eras=[{"label": "SYNTHETIC account", "tickets": 48, "sum_r": -1.75}],
        stops={"labels": {"booked": "SYNTHETIC label for the booked stop."}, "count": 1,
               "rows": [{"ticker": "SYNA", "r_at_low": -1.4}]},
        limits=["SYNTHETIC limit sentence."], other_table=[{"unprinted": 1}])
    json_raw, md_raw, why = brief.compose(FULL_RAW, PICKS_RAW, block)
    assert why is None
    out = brief.validate(FULL_RAW, PICKS_RAW, json_raw, md_raw)
    assert out["model_record"] == block and out["bounds"]["model_record_carried"] is True
    md = section(md_raw.decode(), 10)
    assert "- SYNTHETIC: the test's own model record." in md and "- Model record, limits: SYNTHETIC limit sentence." in md
    assert "Model record, plans (1 of 1 rows; brief.json carries every one):" in md
    assert "| picked | ticker | bucket | r | evidence_id | sales |" in md             # known columns first, then the rest
    assert "| 2026-09-01 | SYNA | settled | -1 |" in md and "Model record, eras (1 of 1 rows" in md
    assert "- stops.labels.booked: SYNTHETIC label for the booked stop." not in md      # short entries stay on one line
    assert "- stops.labels: booked SYNTHETIC label for the booked stop." in md and "- stops.count: 1" in md
    assert "other_table" not in md and "held to the record's scorecard" in md
    assert brief.validate(FULL_RAW, PICKS_RAW, json_raw, md_raw)["model_record"]["plans"][0]["sales"] == [{"shares": 2}]


def test_the_block_is_held_to_the_scorecard_on_its_counts_and_its_sum():
    data = json.loads(FULL_RAW)
    card = data["scorecard"]
    assert (card["plans"], card["settled"], card["sum_r"]) == (48, 20, -1.75)
    good = agreeing_block(data)
    assert brief.model_record_faults(good, data) == []
    assert brief.model_record_faults({**good, "sum_r": -1.7549}, data) == []          # rounds to the scorecard's two places
    assert brief.model_record_faults({**good, "sum_r": -1.74}, data) == ["sum_r -1.74 does not round to the scorecard's -1.75"]
    assert brief.model_record_faults({**good, "tickets": 47}, data) == ["tickets 47 is not the scorecard's 48 plans"]
    assert brief.model_record_faults({**good, "tickets": 48.0}, data)[0].startswith("tickets 48.0")
    one_moved = {**good["buckets"], "settled": 19, "open": card["open"] + 1}
    assert brief.model_record_faults({**good, "buckets": one_moved}, data) == [
        "bucket settled 19 is not the scorecard's 20", f"bucket open {card['open'] + 1} is not the scorecard's {card['open']}"]
    assert brief.model_record_faults({**good, "buckets": {**good["buckets"], "invented": 1}}, data) == [
        "bucket invented 1 is not the scorecard's 0"]
    assert brief.model_record_faults({**good, "buckets": []}, data) == ["buckets is not an object"]
    assert brief.model_record_faults({**good, "sentences": "one"}, data) == ["sentences is not a list of sentences"]
    assert brief.model_record_faults({**good, "version": "1"}, data) == ["version is not a whole number"]
    assert brief.model_record_faults({**good, "sum_r": True}, data)
    empty = {"scorecard": {name: 0 for name in record.SCORECARD_BUCKETS} | {"plans": 0, "sum_r": None}}
    none_settled = {**good, "tickets": 0, "buckets": {name: 0 for name in record.SCORECARD_BUCKETS}, "sum_r": None}
    assert brief.model_record_faults(none_settled, empty) == []
    assert brief.model_record_faults({**none_settled, "sum_r": 0.5}, empty) == ["sum_r 0.5 beside a scorecard with no settled plan"]
    assert brief.model_record_faults({"status": "not_computed"}, data) == [] == brief.model_record_faults(None, data)
    assert brief.SCORECARD_BUCKETS == record.SCORECARD_BUCKETS


@pytest.mark.parametrize("block, reason", [
    ("not an object", brief.NOT_CARRIED_UNREADABLE),
    ({"status": "finished"}, brief.NOT_CARRIED_UNREADABLE),
    ({"status": "not_computed", "reason": "a reason nobody fixed"}, brief.NOT_CARRIED_UNREADABLE),
    ({"status": "not_computed", "reason": brief.NOT_COMPUTED_FAILED}, brief.NOT_COMPUTED_FAILED),
    ("NAMES", brief.NOT_CARRIED_NAMES), ("SIZE", brief.NOT_CARRIED_SIZE), ("DISAGREES", brief.NOT_CARRIED_DISAGREES),
    ("NAN", brief.NOT_CARRIED_UNREADABLE),
])
def test_a_block_that_cannot_be_carried_is_replaced_by_its_fixed_reason_and_the_night_keeps_its_brief(block, reason):
    data = json.loads(FULL_RAW)
    good = agreeing_block(data)
    block = {"NAMES": {**good, "plans": [{"api_key": "abc123"}]},
             # the bulk sits where the reduction keeps it, so the reduced block is over the bound too
             "SIZE": {**good, "limits": ["x" * brief.MODEL_RECORD_MAX_BYTES]},
             "DISAGREES": {**good, "tickets": 1},
             "NAN": {**good, "sum_r": float("nan")}}.get(block, block) if isinstance(block, str) else block
    json_raw, md_raw, why = brief.compose(FULL_RAW, PICKS_RAW, block)
    assert why is None
    out = brief.validate(FULL_RAW, PICKS_RAW, json_raw, md_raw)
    assert out["model_record"] == {"status": "not_computed", "reason": reason} and reason in brief.NOT_COMPUTED_REASONS
    assert f"- Model-record block: not computed ({reason})." in md_raw.decode()
    assert b"abc123" not in json_raw and out["status"] == "derived"


def test_a_forged_pair_carrying_a_block_that_disagrees_does_not_survive_re_derivation():
    data = json.loads(FULL_RAW)
    json_raw, md_raw, _ = brief.compose(FULL_RAW, PICKS_RAW, agreeing_block(data))
    forged = json.loads(json_raw)
    forged["model_record"]["sum_r"] = 12.5                  # a better record than the scorecard's
    forged_json = brief._encode(forged)
    forged_md = brief.fit_md(forged, forged_json)
    assert brief.validate_binding(FULL_RAW, PICKS_RAW, forged_json, forged_md)["model_record"]["sum_r"] == 12.5
    with pytest.raises(ValueError, match="brief.json differs from its derivation"):
        brief.validate(FULL_RAW, PICKS_RAW, forged_json, forged_md)


def test_a_block_exactly_at_its_bound_is_carried_whole_and_one_byte_over_is_carried_reduced():
    data = json.loads(FULL_RAW)
    row = {"ticker": "SYNA", "kind": "burst", "picked": "2026-01-05", "evidence_id": "e" * 64, "bucket": "settled",
           "r": 1.5, "shares": 3, "model_usd": 4.5, "issued_equity": 30000.0, "risk_pct": 0.5,
           "account_basis": "record", "setup": "burst:SYNA:2026-01-05", "withdrawn": False}

    def sized(extra):
        block = agreeing_block(data, plans=[{**row, "note": ""}], setups=[{"setup": row["setup"]}])
        block["plans"][0]["note"] = "x" * (brief.MODEL_RECORD_MAX_BYTES - len(brief._encode(block)) + extra)
        return block
    assert len(brief._encode(sized(0))) == brief.MODEL_RECORD_MAX_BYTES
    whole = brief.model_block(sized(0), data)
    assert whole["status"] == "computed" and "reduced" not in whole and "note" in whole["plans"][0]
    reduced = brief.model_block(sized(1), data)
    assert reduced["status"] == "computed" and reduced["plans"] == [row] and "setups" not in reduced
    assert reduced["reduced"] == {"reason": brief.MODEL_REDUCED_REASON, "setups_left_out": 1,
                                  "plan_fields": list(brief.MODEL_REDUCED_PLAN_FIELDS)}
    assert reduced["tickets"] == sized(1)["tickets"] and reduced["sentences"] == sized(1)["sentences"]
    assert brief.model_block(reduced, data) == reduced        # re-derivation carries the reduced block as it is
    # a block that is over its bound even reduced is not carried, and the file says why
    fat = {**sized(1), "limits": ["x" * brief.MODEL_RECORD_MAX_BYTES]}
    assert brief.model_block(fat, data) == {"status": "not_computed", "reason": brief.NOT_CARRIED_SIZE}


def test_a_reduced_block_still_gives_the_next_night_every_tickets_account(tmp_path):
    """What the reduction exists for: ``model_record.carried_accounts()`` reads a ticket's account from the
    previous brief's plan rows, so the rows a reduced block keeps must be the ones it reads."""
    from src import model_record
    data = json.loads(FULL_RAW)
    rows = [{"ticker": f"SYN{i}", "kind": "burst", "picked": "2026-01-05", "evidence_id": f"{i:064x}",
             "bucket": "settled", "r": 0.0, "shares": 1, "issued_equity": 2000.0 + i, "risk_pct": 0.5,
             "account_basis": "record", "trigger": 10.0, "limit": 10.4, "stop": 9.99,
             "sales": [{"note": "x" * 2000}]} for i in range(1, 41)]
    block = agreeing_block(data, plans=rows)
    assert len(brief._encode(block)) > brief.MODEL_RECORD_MAX_BYTES
    json_raw, md_raw, why = brief.compose(FULL_RAW, PICKS_RAW, block)
    assert why is None
    out = brief.validate(FULL_RAW, PICKS_RAW, json_raw, md_raw)
    assert out["bounds"]["model_record_carried"] is True and out["bounds"]["model_record_reduced"] is True
    assert "carried reduced" in section(md_raw.decode(), 10)
    (tmp_path / model_record.BRIEF_FILE).write_bytes(json_raw)
    carried, why_not = model_record.carried_accounts(tmp_path)
    assert why_not is None and len(carried) == 40
    assert carried[f"{7:064x}"] == (2007.0, 0.5, model_record.CARRIED)


def test_a_block_that_says_it_does_not_reconcile_is_carried_as_it_is_and_no_figure_of_it_is_printed():
    block = {"version": 1, "status": "unreconciled", "reason": "SYNTHETIC: plans is 3 here and 48 in the published scorecard",
             "tickets": 3, "buckets": {"settled": 3}, "sum_r": 9.99,
             "sentences": ["SYNTHETIC: the figures do not reconcile and are not to be quoted."],
             "plans": [{"ticker": "SYNA", "r": 9.99}]}
    json_raw, md_raw, why = brief.compose(FULL_RAW, PICKS_RAW, block)
    assert why is None
    out = brief.validate(FULL_RAW, PICKS_RAW, json_raw, md_raw)
    assert out["model_record"] == block and out["bounds"]["model_record_carried"] is True
    md = section(md_raw.decode(), 10)
    assert "SYNTHETIC: the figures do not reconcile" in md and "with the status `unreconciled`" in md
    assert "9.99" not in md and "Model record, plans" not in md


def test_a_block_that_would_cost_the_night_its_brief_is_left_out_and_said_so(monkeypatch):
    data = json.loads(FULL_RAW)
    block = agreeing_block(data, plans=[{"note": "x" * 30_000}])
    without = len(brief.compose(FULL_RAW, PICKS_RAW)[0])
    monkeypatch.setattr(brief, "MAX_JSON_BYTES", without + 2_000)           # room for the brief, not for the block
    json_raw, md_raw, why = brief.compose(FULL_RAW, PICKS_RAW, block)
    assert why is None
    out = brief.validate(FULL_RAW, PICKS_RAW, json_raw, md_raw)
    assert out["model_record"] == {"status": "not_computed", "reason": brief.NOT_CARRIED_ROOM}
    assert out["tickets"] and len(json_raw) <= brief.MAX_JSON_BYTES
    # with no block to give up, a record that cannot fit is refused and the pair says so
    monkeypatch.setattr(brief, "MAX_JSON_BYTES", 10_000)
    json_raw, md_raw, why = brief.compose(FULL_RAW, PICKS_RAW)
    assert why == "brief.json does not fit 10000 bytes at its smallest row bounds"
    assert json.loads(json_raw)["status"] == "unavailable"


def test_the_markdown_gives_up_the_model_records_tables_before_any_candidates_detail(monkeypatch):
    data = json.loads(FULL_RAW)
    rows = [{"ticker": f"SY{n:03d}", "bucket": "settled", "r": -1.0, "note": "SYNTHETIC row"} for n in range(30)]
    block = agreeing_block(data, plans=rows)
    json_raw, md_raw, _ = brief.compose(FULL_RAW, PICKS_RAW, block)
    assert "Model record, plans (30 of 30 rows" in md_raw.decode()
    assert "model-record tables printed: yes" in md_raw.decode()
    monkeypatch.setattr(brief, "MAX_MD_BYTES", len(md_raw) - 1)
    json_raw, tight, why = brief.compose(FULL_RAW, PICKS_RAW, block)
    assert why is None and len(tight) <= brief.MAX_MD_BYTES
    text = tight.decode()
    assert "Model record, plans" not in text and "- Model-record tables: not printed here" in text
    assert "model-record tables printed: no" in text and "4 in detail" in text
    assert "- SYNTHETIC: the test's own model record." in text                # its sentences stay
    brief.validate(FULL_RAW, PICKS_RAW, json_raw, tight)


# ------------------------------------------------------------------ (h) limits, and what the module is held to
def test_the_limits_are_fixed_timeless_sentences():
    text = " ".join(brief.LIMITS)
    for needed in ("The model record establishes no edge", "A model fill at the open assumes a buy stop-limit order already "
                   "resting at the broker", "booked at exactly the stop price", "SpicyStock reads no company news",
                   "This brief places and observes no order"):
        assert needed in text, needed
    assert not re.search(r"\b20\d\d\b", text), "a limit names a date and will go stale"
    assert len(brief.LIMITS) == len(set(brief.LIMITS)) == 15


def test_the_constants_are_the_modules_own():
    assert brief.SITE_URL == report.PAGE_URL
    assert brief.MAX_SOURCE_BYTES == reader.MAX_PUBLICATION_BYTES
    assert brief.ORDER_ACTIONS == plan.ORDER_ACTIONS
    assert (brief.DATA_FILE, brief.PICKS_FILE) == ("data.json", record.PICKS_FILE)
    assert brief.NOT_COMPUTED == "computed only inside an evening run, from that run's fetched bars"
    assert brief.MODEL_TABLES == ("plans", "setups", "eras", "stops")
    assert set(brief.EVENT_STATUS_WORDS) == {"known_event", "review_required", "not_in_registry"}
    assert brief.MAX_JSON_BYTES == 250_000 and brief.MAX_MD_BYTES == 80_000


def test_a_property_name_the_secret_scan_would_read_is_named():
    assert brief.scanner_names({"a": [{"api_key": 1}, {"fine": {"AccessToken": 2}}], "monkey": 3}) == ["api_key", "AccessToken", "monkey"]
    assert brief.scanner_names({"evidence_id": "x", "plan_sha256": "y", "ticker": "KEY"}) == []


def test_the_gate_can_import_the_module_without_the_repositorys_dependencies():
    code = ("import sys; sys.path.insert(0, sys.argv[1]); from src import brief, freshness; "
            "import tools.publish_dashboard as gate; "
            "bad = [m for m in ('pandas', 'numpy', 'exchange_calendars', 'anthropic', 'resend', 'alpaca') if m in sys.modules]; "
            "print(bad); sys.exit(1 if bad else 0)")
    done = subprocess.run([sys.executable, "-S", "-c", code, str(ROOT)], capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr


def test_the_module_reads_no_clock_no_network_and_no_other_file():
    source = Path(brief.__file__).read_text()
    for banned in ("datetime.now", "time.time(", "utcnow", "urlopen", "import requests", "import socket", "os.environ",
                   "subprocess", "http.client"):
        assert banned not in source, banned
    assert "from src import report" not in source and "import src.report" not in source


# ------------------------------------------------------------------ the command and the installed pair
def test_the_command_writes_checks_and_refuses_a_stale_pair(tmp_path, capsys):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "data.json").write_bytes(FULL_RAW)
    (docs / "picks.json").write_bytes(PICKS_RAW)
    assert brief.main(["--docs", str(docs)]) == 0
    said = capsys.readouterr().out
    assert said.startswith(f"brief: brief.json {len(derived('full')[2])} of 250000 bytes, brief.md ")
    assert "4 candidates in detail, 0 compact, 0 moved to the tail; model record not_computed" in said
    assert (docs / "brief.json").read_bytes() == derived("full")[2] and (docs / "brief.md").read_bytes() == derived("full")[3]
    assert brief.main(["--docs", str(docs), "--check"]) == 0
    (docs / "data.json").write_bytes(FULL_RAW + b" ")
    assert brief.main(["--docs", str(docs), "--check"]) == 1
    assert "bound to another canonical publication" in capsys.readouterr().err
    (docs / "data.json").write_bytes(encoded({"schema_version": 1}))
    assert brief.main(["--docs", str(docs)]) == 2                       # the unavailable pair, and the exit code says so
    assert json.loads((docs / "brief.json").read_text())["status"] == "unavailable"
    assert brief.main(["--docs", str(docs), "--check"]) == 0
    assert brief.main(["--docs", str(tmp_path / "nowhere")]) == 1


def test_a_symlinked_target_is_refused_and_nothing_is_written_through_it(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    elsewhere = tmp_path / "elsewhere.json"
    elsewhere.write_text("kept")
    (docs / "brief.json").symlink_to(elsewhere)
    with pytest.raises(ValueError, match="must not be a symlink"):
        brief.write_publication(FULL_RAW, PICKS_RAW, docs)
    assert elsewhere.read_text() == "kept" and not (docs / "brief.md").exists()
