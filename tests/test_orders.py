"""The execution handoff (src/orders.py): orders.json, orders-morning.json and
positions-template.json.

These hold the schema to the module's own words, every file to the schema and
to its own hash, every ticket to the rows the morning receipt quotes and to
the plan's prices and constants, every no-trade reason and every morning
cancel to the case that gives it, the evening's install and removal, the
publication gate and the morning's one-file commit."""
from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
import tomllib
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from src import morning, orders, plan, schema_check
from tests.fixtures.orders import generate

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "tests" / "fixtures" / "page"
MORNING = ROOT / "tests" / "fixtures" / "morning"
GOLDEN = ROOT / "tests" / "fixtures" / "orders"
PUBLICATION = (MORNING / "full-publication.json").read_bytes()


def page(name: str) -> bytes:
    return (PAGE / f"{name}.json").read_bytes()


def built(name: str = "full") -> dict:
    return orders.build(page(name))


def resealed(doc: dict, **changes) -> bytes:
    """``doc`` changed and sealed again, as a forged but self-consistent file."""
    return orders.encode(orders.sealed({**{k: v for k, v in doc.items() if k != "content_sha256"}, **changes}))


# ------------------------------------------------------------- the schema --
def enum(defs: dict, *path: str) -> list:
    node = defs
    for key in path:
        node = node[key]
    return node["enum"]


def test_the_schema_uses_only_what_the_checker_reads_and_names_the_modules_words():
    root = orders.schema()
    defs = root["$defs"]
    assert root["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert enum(defs, "night_check", "properties", "key") == list(orders.NIGHT_CHECKS)
    assert enum(defs, "ticket_check", "properties", "key") == list(orders.TICKET_CHECKS)
    for name in ("night_check", "ticket_check"):
        assert enum(defs, name, "properties", "status") == list(orders.CHECK_STATUSES)
        assert enum(defs, name, "properties", "reason") == sorted(orders.REASONS) + [None]
    assert enum(defs, "reason", "properties", "code") == sorted(orders.REASONS)
    assert enum(defs, "ticket", "properties", "status") == list(orders.TICKET_STATUSES)
    assert defs["ticket"]["properties"]["reasons"]["items"]["enum"] == sorted(orders.REASONS)
    assert enum(defs, "morning_ticket", "properties", "decision") == list(orders.DECISIONS)
    assert defs["morning_ticket"]["properties"]["reasons"]["items"]["enum"] == sorted(orders.MORNING_REASONS)
    assert enum(defs, "orders_morning", "properties", "morning_status") == list(morning.STATUSES) + [None]
    assert enum(defs, "position", "properties", "status") == list(orders.POSITION_STATUSES)
    assert enum(defs, "exit", "properties", "reason") == list(orders.EXIT_REASONS)
    assert root["properties"]["night_checks"]["minItems"] == len(orders.NIGHT_CHECKS)
    assert defs["ticket"]["properties"]["checks"]["maxItems"] == len(orders.TICKET_CHECKS)
    assert root["properties"]["version"]["const"] == orders.VERSION
    # every exit reason but `manual` is a rule the exit plan carries
    rules = {r["key"] for r in orders.exit_plan(100.0, 3, ["2026-11-20"] * 5)["rules"]}
    assert set(orders.EXIT_REASONS) - {"manual"} <= rules


def test_the_checker_refuses_a_keyword_it_does_not_read():
    with pytest.raises(schema_check.SchemaError, match="unsupported schema keywords"):
        schema_check.errors(1, {"type": "integer", "multipleOf": 2})
    with pytest.raises(schema_check.SchemaError, match="unsupported"):
        schema_check.check_definitions({"$defs": {"x": {"oneOf": []}}})
    with pytest.raises(schema_check.SchemaError, match="missing definition"):
        schema_check.errors(1, {"$ref": "#/$defs/nowhere"}, {"$defs": {}})


@pytest.mark.parametrize("value, schema, wrong", [
    (True, {"type": "integer"}, True), (1, {"type": "integer"}, False), (1.5, {"type": "integer"}, True),
    ("x", {"enum": ["x", "y"]}, False), ("z", {"enum": ["x", "y"]}, True), (1, {"enum": [True]}, True),
    (0, {"type": "number", "exclusiveMinimum": 0}, True), ({"a": 1}, {"type": "object", "required": ["b"]}, True),
    ({"a": 1}, {"type": "object", "properties": {}, "additionalProperties": False}, True),
    ([1, 2], {"type": "array", "maxItems": 1}, True), ("ab", {"type": "string", "pattern": "^a"}, False),
])
def test_the_checker_reads_each_keyword(value, schema, wrong):
    assert bool(schema_check.errors(value, schema)) is wrong


# --------------------------------------------------------- the golden files --
def test_the_golden_files_are_what_the_module_writes_and_meet_the_schema():
    files = generate.outputs()
    assert files and all((GOLDEN / name).read_bytes() == raw for name, raw in files.items())
    for name, raw in files.items():
        kind = "orders" if name.endswith("orders.json") else \
            "positions" if name.endswith(orders.POSITIONS_FILE) else "orders_morning"
        assert orders.problems(json.loads(raw), kind) == [], name


def test_the_bytes_and_the_hashes_are_stable_and_any_change_moves_them():
    first, second = orders.encode(built()), orders.encode(built())
    assert first == second
    doc = json.loads(first)
    assert orders.seal_holds(doc) and all(orders.seal_holds(t) for t in doc["tickets"])
    ticket = doc["tickets"][0]
    moved = {**ticket, "shares": ticket["shares"] + 1}
    assert not orders.seal_holds(moved) and orders.sealed(moved)["content_sha256"] != ticket["content_sha256"]
    tampered = copy.deepcopy(doc)
    tampered["tickets"][0]["entry"]["limit_price"] += 0.01
    with pytest.raises(ValueError, match="content_sha256"):
        orders.validate(orders.encode(tampered))
    with pytest.raises(ValueError, match="fails its schema"):
        orders.validate(resealed(doc, mode="live_by_accident"))


# ------------------------------------------------------------- the tickets --
@pytest.mark.parametrize("name", ["full", "next", "notrade", "degraded"])
def test_the_tickets_are_the_rows_the_morning_receipt_quotes_and_the_plans_own_order(name):
    raw = page(name)
    data = json.loads(raw)
    doc = orders.build(raw)
    admitted = morning.admitted_rows(data)
    assert [(t["setup_type"], t["symbol"]) for t in doc["tickets"]] == [(a["kind"], a["ticker"]) for a in admitted]
    for t, a in zip(doc["tickets"], admitted):
        rows = data["bursts"] if a["kind"] == "burst" else data["watchlist"]["top"]
        p = next(r for r in rows if r["ticker"] == a["ticker"])["plan"]
        assert t["order_as_written"] == p["order_json"]
        assert (t["entry"]["stop_price"], t["entry"]["limit_price"], t["protective_stop"]["stop_price"]) == \
            (a["levels"]["trigger"], a["levels"]["limit"], a["levels"]["stop"])
        assert t["shares"] == p["shares"] == t["protective_stop"]["quantity"] == p["order_json"]["quantity"]
        assert t["entry"]["valid_from"] == data["run"]["timing"]["opens_at"]
        assert t["entry"]["valid_until"] == t["entry"]["cancel_if_unfilled_at"] == data["run"]["timing"]["cutoff_at"]
        assert t["evidence"] == {"evidence_id": a["evidence_id"], "plan_sha256": a["plan_sha256"]}
        assert t["risk"]["r_per_share"] == plan._money(t["entry"]["limit_price"] - t["protective_stop"]["stop_price"])
        assert t["risk"]["risk_usd"] == plan._money(t["shares"] * t["risk"]["r_per_share"])
        assert t["risk"]["position_usd"] == plan._money(t["shares"] * t["entry"]["limit_price"])
        if a["kind"] == "burst":
            assert t["entry"]["trigger_rule"] == p.get("trigger_rule", plan.LEGACY_BURST_TRIGGER_RULE)
    assert doc["summary"]["tickets"] == len(admitted)


def test_the_exit_plan_is_followes_order_with_the_plans_numbers():
    days = [d.isoformat() for d in plan.next_sessions(date(2026, 9, 10), plan.FINAL_EXIT_DAY)]
    out = orders.exit_plan(124.33, 5, days)
    rules = {r["key"]: r for r in out["rules"]}
    assert [r["sequence"] for r in out["rules"]] == list(range(1, len(out["rules"]) + 1))
    # the order within a session that plan.follow() applies
    order = [r["key"] for r in out["rules"]]
    assert order.index("stopped_at_open") < order.index("gap_20pct") < order.index("protective_stop") \
        < order.index("sell_half_8pct") < order.index("abnormal_10pct") < order.index("day3_no_progress") \
        < order.index("day3_sell_half") < order.index("entry_day_low") < order.index("trail_after_day3") \
        < order.index("day5_exit")
    levels = plan.exit_levels(124.33)
    assert rules["sell_half_8pct"]["when"]["pct"] == plan.SELL_HALF_PCT
    assert rules["sell_half_8pct"]["when"]["price_at_trigger"] == levels["sell_half"]
    assert rules["abnormal_10pct"]["when"]["price_at_trigger"] == levels["abnormal"]
    assert rules["gap_20pct"]["when"]["pct"] == plan.GAP_EXIT_PCT and \
        rules["gap_20pct"]["when"]["price_at_trigger"] == levels["gap_exit"]
    assert (rules["sell_half_8pct"]["then"]["cents"], rules["sell_half_8pct"]["then"]["cents_max"]) == \
        (plan.TRAIL_CENTS, plan.TRAIL_CENTS_MAX)
    assert out["half_shares"] == rules["sell_half_8pct"]["then"]["shares"] == 3       # at least half of 5
    assert orders.exit_plan(124.33, 1, days)["half_shares"] == 1
    assert rules["day5_exit"]["from_day"] == plan.FINAL_EXIT_DAY and rules["day5_exit"]["to_date"] == days[-1]
    assert rules["day3_sell_half"]["from_day"] == plan.SELL_HALF_DAY
    assert rules["trail_after_day3"]["from_day"] == plan.TRAIL_FROM_DAY
    assert rules["entry_day_low"]["to_day"] == plan.ENTRY_DAY
    assert rules["no_breakeven"]["to_day"] == plan.NO_BREAKEVEN_BEFORE_DAY - 1
    sources = {r["key"]: r["source"] for r in plan.EXIT_RULES}
    assert all(rules[k]["source"] == sources[k] for k in rules if k in sources)


def test_the_secret_scan_allows_the_one_exit_key_it_reads_and_only_at_the_handoffs_paths():
    """The detector reads `abnormal_10pct` as a key and none of the other exit
    keys (tests/secret_scan_controls.py runs the engine on each); the handoff
    writes it, and the allowlist names it and nothing else."""
    config = tomllib.loads((ROOT / ".gitleaks.toml").read_text())
    entry = next(a for a in config["rules"][0]["allowlists"] if "execution handoff" in a["description"])
    keys = {r["key"] for r in orders.exit_plan(100.0, 2, ["2026-11-20"] * 5)["rules"]}
    assert "abnormal_10pct" in keys and entry["regexes"] == ["^(abnormal_10pct)$"]
    assert entry["condition"] == "AND" and entry["regexTarget"] == "secret"
    for path in ("docs/orders.json", "docs/operations/orders-schema.json", "tests/fixtures/orders/full/orders.json"):
        assert re.search(entry["paths"][0], path)
    for path in ("docs/data2.json", "copied/docs/orders.json", "docs/orders.json.bak"):
        assert not re.search(entry["paths"][0], path)


# ------------------------------------------------------- the night's reasons --
def night(data: dict) -> dict:
    return {c["key"]: c for c in orders._night(data, [])}


def test_the_light_the_status_and_the_publication_time_each_give_their_reason():
    full = json.loads(page("full"))
    checks = night(full)
    assert [c["status"] for c in checks.values()] == ["pass", "pass", "pass", "pass", "pass"]
    red = night(json.loads(page("red")))
    assert (red["light"]["status"], red["light"]["reason"]) == ("fail", "light_red")
    # a night degraded only on its chart reader stops no ticket by itself: the run's status word is
    # never the check, and the reader is read on the ticket it concerns (tests/test_orders_inputs.py)
    degraded = json.loads(page("degraded"))
    assert degraded["run"]["status"] == "degraded" and "data" not in night(degraded)
    assert (night(degraded)["market_inputs"]["status"], night(degraded)["market_inputs"]["reason"]) == ("pass", None)
    late = copy.deepcopy(full)
    late["run"]["delivery"]["before_next_open"] = False
    assert (night(late)["publication_time"]["status"], night(late)["publication_time"]["reason"]) == \
        ("fail", "late_publish")
    unknown = copy.deepcopy(full)
    del unknown["run"]["delivery"]
    assert (night(unknown)["publication_time"]["status"], night(unknown)["publication_time"]["reason"]) == \
        ("not_evaluated", "publication_time_unknown")
    unlit = copy.deepcopy(full)
    unlit["breadth"]["regime"]["verdict"] = None
    assert (night(unlit)["light"]["status"], night(unlit)["light"]["reason"]) == ("not_evaluated", "light_unknown")


def test_the_account_check_reads_the_records_slots_and_commitments():
    full = json.loads(page("full"))
    over = copy.deepcopy(full)
    over["cash_budget"]["slots_used"] = over["cash_budget"]["slots_max"] + 1
    assert (night(over)["account"]["status"], night(over)["account"]["reason"]) == ("fail", "account_limit")
    spent = copy.deepcopy(full)
    spent["cash_budget"]["committed_usd"] = spent["account"]["equity"]
    assert night(spent)["account"]["status"] == "fail"
    missing = copy.deepcopy(full)
    del missing["cash_budget"]
    assert night(missing)["account"]["status"] == "not_evaluated"


def test_the_cross_check_is_not_evaluated_until_it_is_run_and_so_trade_is_not_allowed():
    doc = built("next")
    # NVDA's filings read clear and both feeds agree; COIL is in no SEC mapping, so it is held
    assert [(t["symbol"], t["status"], t["reasons"]) for t in doc["tickets"]] == [
        ("NVDA", "go", []), ("COIL", "human_review", ["sec_unknown"])]
    assert night_reasons(doc) == [] and doc["trade_allowed"] is True
    data = json.loads(page("next"))
    del data["run"]["cross_check"]
    older = orders.build(json.dumps(data).encode())
    assert night_reasons(older) == ["cross_check_not_run"] and older["trade_allowed"] is False
    assert {t["status"] for t in older["tickets"]} == {"human_review"}


def night_reasons(doc: dict) -> list:
    return [r["code"] for r in doc["reasons"] if r["scope"] == "night"]


def test_trade_is_allowed_only_when_every_night_check_passes_and_a_ticket_is_go(monkeypatch):
    real = orders._night

    def passing(data, tickets):
        return [{**c, "status": "pass", "reason": None} for c in real(data, tickets)]

    monkeypatch.setattr(orders, "_night", passing)
    assert orders.build(page("next"))["trade_allowed"] is True
    assert orders.build(page("full"))["trade_allowed"] is False          # its one ticket is held for review
    red = orders.build(page("red"))
    assert red["trade_allowed"] is False and "no_tickets" in night_reasons(red)


def test_each_ticket_check_gives_its_reason_and_its_status():
    data = json.loads(page("next"))
    days = ["2026-09-14"] * 5
    admitted = morning.admitted_rows(data)[0]

    def ticket_after(change):
        forged = copy.deepcopy(data)
        rows = forged["bursts"] if admitted["kind"] == "burst" else forged["watchlist"]["top"]
        change(next(r for r in rows if r["ticker"] == admitted["ticker"]), forged)
        return orders._ticket(forged, admitted, days)

    assert ticket_after(lambda row, d: None)["status"] == "go"
    blocked = ticket_after(lambda row, d: row["plan"]["event_risk"].update(blocked=True))
    assert (blocked["status"], blocked["reasons"]) == ("blocked", ["event_blocked"])
    capped = ticket_after(lambda row, d: d["account"].update(max_position_pct=0.01))
    assert capped["status"] == "blocked" and "position_cap" in capped["reasons"]
    # a cap between the shares at the stop and the shares at the limit: the position is priced at the limit
    shares, levels = ticket_after(lambda row, d: None)["shares"], admitted["levels"]
    between = shares * (levels["stop"] + levels["limit"]) / 2 / data["account"]["equity"] * 100
    tight = ticket_after(lambda row, d: d["account"].update(max_position_pct=between))
    assert "position_cap" in tight["reasons"]
    risky = ticket_after(lambda row, d: d["account"].update(risk_pct=0.0001))
    assert risky["status"] == "blocked" and "risk_budget" in risky["reasons"]

    def flag(row, d):
        own = next(r for r in d["run"]["earnings"]["rows"] if r["ticker"] == admitted["ticker"])
        own["items"] = {"status": "material", "sentence": "item 1.01"}
    held = ticket_after(flag)
    assert (held["status"], held["reasons"]) == ("human_review", ["sec_flag"])


def test_the_full_fixtures_ticket_is_held_for_review_by_its_material_8k_item():
    doc = built("full")
    assert doc["tickets"][0]["status"] == "human_review" and doc["tickets"][0]["reasons"] == ["sec_flag"]
    assert {"scope": "AAPL", "code": "sec_flag"} in doc["reasons"]


def test_the_mode_is_paper_while_the_records_gate_names_an_unmet_condition():
    # the fixture records its own go-live gate, which the owner has not passed;
    # a record from before the gate (the pinned publication) cannot be read live
    doc, data = built(), json.loads(page("full"))
    assert doc["mode"] == orders.MODE == "paper"
    assert doc["live_ready"] == {"value": False, "reasons": data["run"]["go_live"]["reasons"]}
    assert "fidelity_protocol" in doc["live_ready"]["reasons"]
    old = orders.build(PUBLICATION)
    assert old["mode"] == "paper" and old["live_ready"] == {"value": False, "reasons": [orders.LIVE_READY_REASON]}


# ------------------------------------------------------------- the morning --
def golden_orders() -> bytes:
    return orders.encode(orders.build(PUBLICATION))


# the pinned morning publication predates the cross-check, so its one ticket is
# held for review (cross_check_not_run) and every morning reads it as not go
@pytest.mark.parametrize("receipt, decision, reasons", [
    ("observed", "cancel", ["night_not_allowed", "ticket_not_go", "trigger_crossed"]),
    ("halted", "cancel", ["night_not_allowed", "ticket_not_go", "halted", "trigger_crossed"]),
    ("corporate-excluded", "cancel", ["night_not_allowed", "ticket_not_go", "news_or_sec_flag", "trigger_crossed"]),
    # a provider outage quoted nothing: bound to the record, it is not a check that ran
    ("outage", "cancel", ["night_not_allowed", "ticket_not_go", "no_morning_check"]),
    ("no-tickets", "cancel", ["night_not_allowed", "ticket_not_go", "no_morning_check"]),
])
def test_each_committed_morning_receipt_gives_its_cancel_reasons(receipt, decision, reasons):
    raw = golden_orders()
    out = orders.build_morning(raw, (MORNING / f"{receipt}.json").read_bytes(), PUBLICATION)
    assert [(t["decision"], t["reasons"]) for t in out["tickets"]] == [(decision, reasons)]
    assert out["orders_sha256"] == hashlib.sha256(raw).hexdigest()
    assert out["morning_bound"] is (receipt != "no-tickets")


def passing_night(doc: dict) -> dict:
    """``doc`` with every night check passed and its decisions made again from its own checks, so
    that the validator's consistency rules hold: the morning's own rules can then be read alone."""
    doc = copy.deepcopy(doc)
    doc["night_checks"] = [{**c, "status": "pass", "reason": None} for c in doc["night_checks"]]
    doc["reasons"] = [{"scope": t["symbol"], "code": code} for t in doc["tickets"] for code in t["reasons"]]
    doc["trade_allowed"] = any(t["status"] == "go" for t in doc["tickets"])
    doc["summary"] = {"tickets": len(doc["tickets"]), **{s: sum(t["status"] == s for t in doc["tickets"])
                                                          for s in ("go", "human_review", "blocked")}}
    return doc


def allowed_orders() -> tuple[bytes, dict]:
    """The golden orders with every night check and every ticket check passed, sealed again:
    the morning's own rules can then be read alone. The pinned publication predates the
    cross-check, so its one ticket is held for review until its checks are passed here."""
    doc = json.loads(golden_orders())
    assert [t["reasons"] for t in doc["tickets"]] == [["cross_check_not_run"]]
    doc["tickets"] = [orders.sealed({**{k: v for k, v in t.items() if k != "content_sha256"},
                                     "checks": [{**c, "status": "pass", "reason": None} for c in t["checks"]],
                                     "status": "go", "reasons": []}) for t in doc["tickets"]]
    doc = passing_night(doc)
    assert doc["trade_allowed"] is True
    return resealed(doc), doc


@pytest.mark.parametrize("state, reasons", [
    ("below_trigger", []), ("within_published_band", ["trigger_crossed"]),
    ("above_limit", ["gap_above_limit"]), ("above_day2_extension", ["gap_above_limit"]),
    ("below_entry_floor", ["gap_below_floor"]), ("below_stop", ["gap_below_floor"]),
])
def test_a_recent_price_in_each_state_gives_go_or_its_cancel(state, reasons):
    raw, _ = allowed_orders()
    receipt = json.loads((MORNING / "observed.json").read_bytes())
    receipt["rows"][0]["price_checks"] = {"trade": state, "ask": state}
    out = orders.build_morning(raw, json.dumps(receipt).encode())
    assert (out["tickets"][0]["decision"], out["tickets"][0]["reasons"]) == ("go" if not reasons else "cancel", reasons)
    assert out["summary"]["go"] == (0 if reasons else 1)


def test_a_stale_price_cancels_and_a_missing_row_is_not_checked():
    raw, _ = allowed_orders()
    receipt = json.loads((MORNING / "observed.json").read_bytes())
    receipt["rows"][0]["price_checks"] = {"trade": "below_trigger", "ask": "below_trigger"}
    receipt["rows"][0]["trade"]["status"] = receipt["rows"][0]["quote"]["status"] = "stale"
    assert orders.build_morning(raw, json.dumps(receipt).encode())["tickets"][0]["reasons"] == ["stale_data"]
    receipt["rows"] = []
    assert orders.build_morning(raw, json.dumps(receipt).encode())["tickets"][0]["reasons"] == ["not_checked"]
    assert orders.build_morning(raw, None)["tickets"][0]["reasons"] == ["no_morning_check"]


def test_a_ticket_orders_json_did_not_mark_go_never_goes_in_the_morning():
    raw, doc = allowed_orders()
    for check, check_status, failed, reason in (
            ("sec_flags", "fail", "sec_flag", "news_or_sec_flag"),
            ("sec_flags", "fail", "sec_unknown", "news_or_sec_flag"),
            ("cross_check", "not_evaluated", "cross_check_unknown", "ticket_not_go"),
            ("cross_check", "fail", "cross_check_failed", "ticket_not_go"),
            ("event_registry", "fail", "event_blocked", "ticket_not_go")):
        forged = copy.deepcopy(doc)
        ticket = forged["tickets"][0]
        ticket["checks"] = [{**c, "status": check_status, "reason": failed} if c["key"] == check else c
                            for c in ticket["checks"]]
        ticket["reasons"] = [failed]
        ticket["status"] = orders.ticket_status([failed])
        forged["tickets"][0] = orders.sealed({k: v for k, v in ticket.items() if k != "content_sha256"})
        forged = passing_night(forged)
        assert forged["trade_allowed"] is False         # the night has no go ticket left
        forged_raw = resealed(forged)
        receipt = json.loads((MORNING / "observed.json").read_bytes())
        receipt["rows"][0]["price_checks"] = {"trade": "below_trigger", "ask": "below_trigger"}
        out = orders.build_morning(forged_raw, json.dumps(receipt).encode())
        assert out["tickets"][0]["decision"] == "cancel" and reason in out["tickets"][0]["reasons"]
        assert ({"news_or_sec_flag", "ticket_not_go"} - {reason}).isdisjoint(out["tickets"][0]["reasons"])


def test_with_the_record_a_tampered_receipt_or_unbound_orders_are_refused():
    raw = golden_orders()
    receipt = json.loads((MORNING / "observed.json").read_bytes())
    receipt["rows"][0]["trade"]["price"] = 1.0
    with pytest.raises(ValueError):
        orders.build_morning(raw, json.dumps(receipt).encode(), PUBLICATION)
    with pytest.raises(ValueError, match="not bound"):
        orders.build_morning(raw, (MORNING / "observed.json").read_bytes(), page("full"))


def test_the_morning_file_reads_no_clock_so_the_same_files_give_the_same_bytes():
    raw = golden_orders()
    receipt = (MORNING / "observed.json").read_bytes()
    assert orders.encode(orders.build_morning(raw, receipt, PUBLICATION)) == \
        orders.encode(orders.build_morning(raw, receipt, PUBLICATION))


# ------------------------------------------------------------ the template --
def test_the_positions_template_is_blank_bound_and_says_it_is_private():
    raw = orders.encode(built())
    template = orders.positions_template(json.loads(raw), raw)
    assert template["orders_sha256"] == hashlib.sha256(raw).hexdigest()
    assert "never commit it" in template["privacy"]
    position = template["positions"][0]
    assert position["status"] == "not_submitted" and position["fills"] == [] and position["exits"] == []
    assert all(v is None for v in position["broker"].values())
    assert orders.problems(template, "positions") == []
    filled = copy.deepcopy(template)
    filled["positions"][0]["fills"] = [{"at": "2026-09-11T09:31:00-04:00", "shares": 2, "price": 124.4}]
    filled["positions"][0]["exits"] = [{"at": "2026-09-11T10:31:00-04:00", "shares": 2, "price": 121.42,
                                        "reason": "protective_stop", "broker_order_id": None}]
    assert orders.problems(orders.sealed(filled), "positions") == []
    bad = copy.deepcopy(filled)
    bad["positions"][0]["exits"][0]["reason"] = "felt_like_it"
    assert orders.problems(orders.sealed(bad), "positions")


# ------------------------------------------------- installing and removing --
def docs_with(tmp_path: Path, name: str = "full") -> Path:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "data.json").write_bytes(page(name))
    return docs


def test_the_evening_writes_its_three_files_bound_to_the_installed_record(tmp_path):
    docs = docs_with(tmp_path)
    result = orders.write_publication(docs)
    assert result["tickets"] == 1 and result["trade_allowed"] is False and result["morning"] == "pending"
    assert orders.check(docs) == []
    doc = json.loads((docs / orders.FILE).read_bytes())
    assert doc["source"]["data_sha256"] == hashlib.sha256(page("full")).hexdigest()
    assert sorted(p.name for p in docs.iterdir()) == sorted(
        ["data.json", orders.FILE, orders.POSITIONS_FILE, orders.MORNING_FILE])


def test_the_evening_replaces_a_morning_file_bound_to_earlier_tickets_with_a_pending_one(tmp_path):
    docs = docs_with(tmp_path)
    (docs / orders.MORNING_FILE).write_text('{"orders_sha256": "' + "0" * 64 + '"}')
    assert orders.write_publication(docs)["morning"] == "pending"
    orders_raw = (docs / orders.FILE).read_bytes()
    assert (docs / orders.MORNING_FILE).read_bytes() == orders.encode(orders.pending_morning(orders_raw))


def test_an_unbound_handoff_is_removed_and_a_bound_one_is_kept(tmp_path):
    docs = docs_with(tmp_path)
    orders.write_publication(docs)
    assert orders.discard_unbound(docs) == []
    (docs / "data.json").write_bytes(page("next"))
    assert orders.check(docs) == ["orders.json is not bound to data.json"]
    assert orders.discard_unbound(docs) == [orders.FILE, orders.POSITIONS_FILE, orders.MORNING_FILE]
    assert not any((docs / n).exists() for n in (orders.FILE, orders.POSITIONS_FILE, orders.MORNING_FILE))


def test_the_pipeline_derives_the_handoff_after_the_brief_and_never_fails_the_night(tmp_path, monkeypatch, caplog):
    from src import pipeline
    body = (ROOT / "src" / "pipeline.py").read_text().split("def finish_publication", 1)[1].split("\ndef ", 1)[0]
    assert body.index("publish_brief(") < body.index("publish_orders(") < body.index("retain_publication(")
    docs = docs_with(tmp_path)
    pipeline.publish_orders(docs)
    assert orders.check(docs) == []
    (docs / "data.json").write_bytes(b'{"not": "a record"}')
    pipeline.publish_orders(docs)                                   # raises nothing
    assert not (docs / orders.FILE).exists() and "Execution handoff unavailable" in caplog.text


def test_the_publication_gate_holds_the_handoff_to_the_record(tmp_path):
    from tools import publish_dashboard
    root = tmp_path
    docs = docs_with(root)
    assert publish_dashboard.orders_files(root) == ()
    orders.write_publication(docs)
    assert publish_dashboard.orders_files(root) == (orders.FILE, orders.POSITIONS_FILE, orders.MORNING_FILE)
    (docs / orders.MORNING_FILE).unlink()                       # no file to read a go from: the site is not served
    with pytest.raises(RuntimeError, match="orders-morning.json is missing beside orders.json"):
        publish_dashboard.orders_files(root)
    orders.write_publication(docs)
    (docs / "data.json").write_bytes(page("next"))
    with pytest.raises(RuntimeError, match="execution handoff"):
        publish_dashboard.orders_files(root)


# ------------------------------------------------------- the morning commit --
def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True).stdout


@pytest.fixture
def handoff_repository(tmp_path):
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    root = tmp_path / "checkout"
    subprocess.run(["git", "clone", str(remote), str(root)], check=True, capture_output=True)
    git(root, "checkout", "-b", "main")
    git(root, "config", "user.name", "test")
    git(root, "config", "user.email", "test@example.invalid")
    (root / "docs").mkdir()
    (root / "docs" / "data.json").write_bytes(PUBLICATION)
    (root / "docs" / "orders.json").write_bytes(golden_orders())
    (root / "docs" / "morning.json").write_bytes((MORNING / "observed.json").read_bytes())
    git(root, "add", ".")
    git(root, "commit", "-m", "baseline")
    git(root, "push", "-u", "origin", "main")
    return root


def test_the_morning_commits_only_its_go_cancel_file_and_a_repeat_changes_nothing(handoff_repository):
    from tools import publish_morning
    root = handoff_repository
    assert publish_morning.publish_orders(root, ref="refs/heads/main", run_id="synthetic-observed") == "published"
    changed = git(root, "fetch", "origin") or git(root, "diff", "--name-only", "HEAD", "origin/main").decode().split()
    assert changed == ["docs/orders-morning.json"]
    committed = git(root, "show", "origin/main:docs/orders-morning.json")
    assert committed == orders.encode(orders.build_morning(golden_orders(),
                                                           (MORNING / "observed.json").read_bytes(), PUBLICATION))
    assert publish_morning.publish_orders(root, ref="refs/heads/main", run_id="synthetic-observed") == "unchanged"


def test_the_morning_commit_reads_mains_own_receipt_whichever_run_published_it(handoff_repository):
    # the receipt on main is the evidence; which run is asking does not change what it says
    from tools import publish_morning
    assert publish_morning.publish_orders(handoff_repository, ref="refs/heads/main", run_id="another-run") == \
        "published"
    committed = json.loads(git(handoff_repository, "show", "origin/main:docs/orders-morning.json"))
    assert (committed["status"], committed["observation_run_id"]) == ("checked", "synthetic-observed")


def test_the_morning_commit_needs_main_and_a_run(handoff_repository):
    from tools import publish_morning
    with pytest.raises(ValueError, match="requires_main"):
        publish_morning.publish_orders(handoff_repository, ref="refs/heads/other", run_id="synthetic-observed")
    with pytest.raises(ValueError):
        publish_morning.publish_orders(handoff_repository, ref="refs/heads/main", run_id="")


def test_the_morning_check_refuses_only_what_leaves_nothing_to_write():
    from tools import publish_morning
    assert publish_morning.orders_check(PUBLICATION, None) == "no_orders_on_main"
    assert publish_morning.orders_check(page("full"), golden_orders()) == "orders_not_bound_to_record"
    assert publish_morning.orders_check(PUBLICATION, golden_orders()) is None


def test_the_morning_workflow_publishes_the_go_cancel_after_the_receipt():
    import yaml
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "morning.yml").read_text())
    steps = wf["jobs"]["persist"]["steps"]
    names = [s.get("name") for s in steps]
    step = next(s for s in steps if s.get("name") == "Publish the morning go/cancel for the execution handoff")
    assert step["run"] == "python -m tools.publish_morning orders"
    assert names.index("Publish only against the unchanged source record") < names.index(step["name"])


# ------------------------------------------- the morning, read fail-closed --
def receipt_for(doc: dict, ticket: dict, *, state="below_trigger", halt="not_listed", blocks=None,
                retained=(), phase="open", generated_at=None, blocked=False) -> bytes:
    """A receipt bound to ``doc`` with one row for ``ticket``, read as given (no record): the
    morning's decision rules alone."""
    until = datetime.fromisoformat(ticket["entry"]["valid_until"])
    return json.dumps({
        "publication": {"data_sha256": doc["source"]["data_sha256"]}, "status": "observed",
        "entry_phase": phase, "observation_run_id": "run-1",
        "generated_at": generated_at or (until - timedelta(minutes=30)).isoformat(),
        "rows": [{"kind": ticket["setup_type"], "ticker": ticket["symbol"],
                  "evidence_id": ticket["evidence"]["evidence_id"], "plan_sha256": ticket["evidence"]["plan_sha256"],
                  "trade": {"status": "recent", "price": 1.0, "timestamp": None},
                  "quote": {"status": "recent", "bid": 1.0, "ask": 1.0, "timestamp": None},
                  "price_checks": {"trade": state, "ask": state},
                  "events": {"halt": {"status": halt, "blocks_entry": blocks},
                             "corporate_action": {"blocked": blocked},
                             "retained_corporate_actions": list(retained)}}],
    }).encode()


def decided(raw: bytes, receipt: bytes) -> tuple:
    t = orders.build_morning(raw, receipt)["tickets"][0]
    return t["decision"], t["reasons"]


def anticipation_orders() -> tuple[bytes, dict, dict]:
    # the fixture's run carries no SEC read and no cross-check of its own, so its ticket is
    # held for review until its checks are passed here, as allowed_orders() passes them
    doc = json.loads(orders.encode(orders.build(page("notrade"))))
    doc["tickets"] = [orders.sealed({**{k: v for k, v in t.items() if k != "content_sha256"},
                                     "checks": [{**c, "status": "pass", "reason": None} for c in t["checks"]],
                                     "status": "go", "reasons": []}) for t in doc["tickets"]]
    doc = passing_night(doc)
    ticket = next(t for t in doc["tickets"] if t["setup_type"] == "anticipation")
    assert ticket["status"] == "go" and doc["trade_allowed"] is True
    return resealed(doc), doc, ticket


@pytest.mark.parametrize("state, reasons", [
    # a setting-up ticket has no skip-under line: under its trigger and over its stop it is waiting
    ("below_trigger", []), ("below_entry_floor", []),
    ("below_stop", ["gap_below_floor"]), ("within_published_band", ["trigger_crossed"]),
    ("above_limit", ["gap_above_limit"]),
    ("unknown", ["price_unknown"]), ("a_word_the_receipt_never_writes", ["price_unknown"]),
])
def test_a_setting_up_ticket_reads_its_own_go_states(state, reasons):
    raw, doc, ticket = anticipation_orders()
    assert decided(raw, receipt_for(doc, ticket, state=state)) == ("go" if not reasons else "cancel", reasons)


def test_a_burst_ticket_reads_a_price_under_its_skip_line_as_a_gap_and_an_unknown_state_as_unknown():
    raw, doc = allowed_orders()
    ticket = doc["tickets"][0]
    assert decided(raw, receipt_for(doc, ticket, state="below_entry_floor")) == ("cancel", ["gap_below_floor"])
    assert decided(raw, receipt_for(doc, ticket, state="unknown")) == ("cancel", ["price_unknown"])


@pytest.mark.parametrize("halt, blocks, reasons", [
    ("not_listed", None, []), ("resumption_reported", None, []),
    ("halt_reported", True, ["halted"]), ("security_deleted", True, ["halted"]),
    ("resumption_scheduled", True, ["halted"]),
    # the source could not be read, was stale, or named a code it does not know: not a clearance
    ("unknown", None, ["halt_unknown"]), ("a_state_never_written", None, ["halt_unknown"]), (None, None, ["halt_unknown"]),
])
def test_a_halt_source_that_cannot_say_cancels_like_a_halt(halt, blocks, reasons):
    raw, doc = allowed_orders()
    ticket = doc["tickets"][0]
    assert decided(raw, receipt_for(doc, ticket, halt=halt, blocks=blocks)) == \
        ("go" if not reasons else "cancel", reasons)


def test_a_halt_outage_from_the_real_collector_cancels():
    # the committed outage receipt with its prices moved under the trigger and its halt coverage gone: a
    # receipt that quoted the ticket is partial, not provider_unavailable, which checks nothing
    raw, doc = allowed_orders()
    receipt = json.loads((MORNING / "outage.json").read_bytes())
    assert decided(raw, json.dumps(receipt).encode()) == ("cancel", ["no_morning_check"])
    receipt["status"] = "partial"
    row = receipt["rows"][0]
    row["trade"]["status"] = row["quote"]["status"] = "recent"
    row["price_checks"] = {"trade": "below_trigger", "ask": "below_trigger"}
    assert decided(raw, json.dumps(receipt).encode()) == ("go", [])
    row["events"]["halt"] = {"status": "unknown", "blocks_entry": None,
                             "reason": "Current halt coverage is unavailable or stale; verify with the broker and exchange."}
    assert decided(raw, json.dumps(receipt).encode()) == ("cancel", ["halt_unknown"])


def test_a_retained_corporate_exclusion_cancels_though_tonights_registry_no_longer_lists_it():
    raw, doc = allowed_orders()
    ticket = doc["tickets"][0]
    assert decided(raw, receipt_for(doc, ticket, blocked=True)) == ("cancel", ["news_or_sec_flag"])
    assert decided(raw, receipt_for(doc, ticket, retained=[{"event_id": "x"}])) == ("cancel", ["news_or_sec_flag"])
    # the committed corporate-retained receipt, its prices under the trigger
    receipt = json.loads((MORNING / "corporate-retained.json").read_bytes())
    assert receipt["rows"][0]["events"]["retained_corporate_actions"]
    receipt["rows"][0]["price_checks"] = {"trade": "below_trigger", "ask": "below_trigger"}
    receipt["rows"][0]["trade"]["status"] = receipt["rows"][0]["quote"]["status"] = "recent"
    out = orders.build_morning(raw, json.dumps(receipt).encode())["tickets"][0]
    assert out["decision"] == "cancel" and "news_or_sec_flag" in out["reasons"]


@pytest.mark.parametrize("phase, minutes, reasons", [
    ("upcoming", -60, []), ("open", -1, []),
    ("open", 0, ["outside_entry_window"]), ("ended", 1, ["outside_entry_window"]),
    ("ended", -1, ["outside_entry_window"]), ("unknown", -30, ["outside_entry_window"]),
])
def test_a_receipt_completed_at_or_after_the_cutoff_never_says_go(phase, minutes, reasons):
    raw, doc = allowed_orders()
    ticket = doc["tickets"][0]
    at = (datetime.fromisoformat(ticket["entry"]["valid_until"]) + timedelta(minutes=minutes)).isoformat()
    out = orders.build_morning(raw, receipt_for(doc, ticket, phase=phase, generated_at=at))["tickets"][0]
    assert (out["decision"], out["reasons"]) == ("go" if not reasons else "cancel", reasons)
    assert out["valid_until"] == ticket["entry"]["valid_until"]


# ------------------------------------------- a file whose verdicts are its own --
@pytest.mark.parametrize("change", [
    {"trade_allowed": True},                                      # on a red night with no ticket
    {"mode": "live"},
    {"live_ready": {"value": True, "reasons": []}},
    {"reasons": []},
    {"summary": {"tickets": 0, "go": 1, "human_review": 0, "blocked": 0}},
])
def test_a_resealed_file_whose_verdict_is_not_its_checks_is_refused(change, tmp_path):
    doc = built("red")
    forged = resealed(doc, **change)
    with pytest.raises(ValueError, match="fails its schema"):
        orders.validate(forged)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "data.json").write_bytes(page("red"))
    (docs / "orders.json").write_bytes(forged)
    assert orders.check(docs) and orders.check(docs)[0].startswith("orders.json:")


def test_a_resealed_ticket_whose_status_is_not_its_checks_is_refused():
    doc = built("full")                     # its one ticket is held for review by its material 8-K item
    forged = copy.deepcopy(doc)
    ticket = next(t for t in forged["tickets"] if t["status"] != "go")
    forged["tickets"][forged["tickets"].index(ticket)] = orders.sealed({**ticket, "status": "go", "reasons": []})
    with pytest.raises(ValueError, match="status and reasons are not its checks'"):
        orders.validate(resealed(forged))


@pytest.mark.parametrize("raw", [b"[]", b"null", b'"x"', b"1"])
def test_a_file_that_is_not_an_object_is_named_not_raised(raw, tmp_path):
    with pytest.raises(ValueError, match="not a JSON object"):
        orders.validate(raw)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "data.json").write_bytes(page("full"))
    (docs / "orders.json").write_bytes(raw)
    assert orders.check(docs) == ["orders.json: orders is not a JSON object"]
    assert orders.problems(json.loads(raw)) and all(isinstance(p, str) for p in orders.problems(json.loads(raw)))
    from tools import publish_morning
    assert publish_morning.orders_check(page("full"), raw) == "orders_not_bound_to_record"


def test_a_morning_file_that_does_not_carry_orders_modes_is_named(tmp_path):
    docs = docs_with(tmp_path)
    orders.write_publication(docs)
    raw = (docs / "orders.json").read_bytes()
    morning_doc = orders.build_morning(raw, None)
    (docs / "orders-morning.json").write_bytes(orders.encode(orders.sealed({**morning_doc, "mode": "live"})))
    assert "orders-morning.json does not carry orders.json's mode" in orders.check(docs)


def test_the_morning_command_reads_the_receipt_against_the_record(tmp_path):
    with pytest.raises(SystemExit):
        orders.main(["morning", "--orders", "x", "--output", str(tmp_path / "o.json")])
    raw = golden_orders()
    (tmp_path / "orders.json").write_bytes(raw)
    (tmp_path / "data.json").write_bytes(PUBLICATION)
    receipt = json.loads((MORNING / "observed.json").read_bytes())
    receipt["rows"][0]["trade"]["price"] = 1.0                  # tampered: the record refuses it
    (tmp_path / "morning.json").write_bytes(json.dumps(receipt).encode())
    with pytest.raises(ValueError):
        orders.main(["morning", "--orders", str(tmp_path / "orders.json"), "--receipt", str(tmp_path / "morning.json"),
                     "--data", str(tmp_path / "data.json"), "--output", str(tmp_path / "o.json")])
    (tmp_path / "morning.json").write_bytes((MORNING / "observed.json").read_bytes())
    assert orders.main(["morning", "--orders", str(tmp_path / "orders.json"), "--receipt",
                        str(tmp_path / "morning.json"), "--data", str(tmp_path / "data.json"),
                        "--output", str(tmp_path / "o.json")]) == 0


# ---------------------------------------------------- the night and the hold --
def test_a_run_whose_clock_is_at_or_after_the_prepare_by_instant_is_late():
    full = json.loads(page("full"))
    prepare_by = datetime.fromisoformat(full["run"]["timing"]["prepare_by"])
    assert night(full)["publication_time"]["status"] == "pass"
    for minutes, status in ((-1, "pass"), (0, "fail"), (30, "fail")):
        late = copy.deepcopy(full)
        late["run"]["published_at"] = (prepare_by + timedelta(minutes=minutes)).isoformat()
        check = night(late)["publication_time"]
        assert (check["status"], check["reason"]) == (status, None if status == "pass" else "late_publish")
    naive = copy.deepcopy(full)
    naive["run"]["published_at"] = "2026-09-11T22:00:00"
    assert night(naive)["publication_time"]["status"] == "not_evaluated"


def test_each_hold_day_carries_its_scheduled_close_and_an_early_close_says_so():
    from src import sessions
    days = [d.isoformat() for d in plan.next_sessions(date(2026, 11, 23), plan.FINAL_EXIT_DAY)]
    hold = orders.exit_plan(100.0, 4, days)["sessions"]
    assert [h["date"] for h in hold] == days and [h["day"] for h in hold] == list(range(1, len(days) + 1))
    for h in hold:
        _, close, shortened = sessions.hours(date.fromisoformat(h["date"]))
        assert (h["close_at"], h["early_close"]) == (close.isoformat(), shortened)
    friday = next(h for h in hold if h["date"] == "2026-11-27")
    assert friday["early_close"] is True and friday["close_at"].startswith("2026-11-27T13:00")
    assert all(not h["early_close"] for h in hold if h["date"] != "2026-11-27")


def test_the_committed_handoff_is_what_this_code_writes_for_the_committed_record():
    """The gate holds the files to their schema, their hashes, their binding and their own checks;
    this re-derives them, so a file whose verdicts were changed and sealed again, or one an older
    rule wrote, is red here. Before the first evening under this code none is committed."""
    docs = ROOT / "docs"
    if not (docs / "orders.json").exists():
        assert not any((docs / n).exists() for n in ("positions-template.json", "orders-morning.json"))
        return
    if orders.earlier_version((docs / "orders.json").read_bytes()) is not None:
        # an earlier code's files, between a merge that moved VERSION and the next evening
        assert orders.check(docs) == []
        return
    data_raw = (docs / "data.json").read_bytes()
    picks_raw = (docs / "picks.json").read_bytes() if (docs / "picks.json").exists() else None
    orders_raw = orders.encode(orders.build(data_raw, picks_raw))
    assert (docs / "orders.json").read_bytes() == orders_raw
    assert (docs / "positions-template.json").read_bytes() == \
        orders.encode(orders.positions_template(json.loads(orders_raw), orders_raw))
    morning_file = docs / "orders-morning.json"
    assert morning_file.exists()                    # the evening writes it with orders.json
    committed = json.loads(morning_file.read_bytes())
    receipt = (docs / "morning.json").read_bytes() if (docs / "morning.json").exists() else None
    if committed["status"] == orders.PENDING:
        assert morning_file.read_bytes() == orders.encode(orders.pending_morning(orders_raw))
    elif committed["morning_sha256"] == (hashlib.sha256(receipt).hexdigest() if receipt is not None else None):
        assert morning_file.read_bytes() == orders.encode(orders.build_morning(orders_raw, receipt, data_raw))


# --------------------------------------- files an earlier version wrote ---
def earlier_docs(tmp_path: Path) -> tuple[Path, bytes]:
    """A record with the handoff an earlier code version wrote for it: bound to
    the record, but not this schema's (its version, and a field it lacked)."""
    docs = docs_with(tmp_path)
    orders.write_publication(docs)
    doc = json.loads((docs / orders.FILE).read_bytes())
    doc["version"] = orders.VERSION - 1
    doc.pop("night_checks")
    raw = orders.encode(orders.sealed(doc))
    (docs / orders.FILE).write_bytes(raw)
    template = json.loads((docs / orders.POSITIONS_FILE).read_bytes())
    template.update(version=orders.VERSION - 1, orders_sha256=hashlib.sha256(raw).hexdigest())
    (docs / orders.POSITIONS_FILE).write_bytes(orders.encode(orders.sealed(template)))
    (docs / orders.MORNING_FILE).unlink()           # this code's pending file, bound to the file just replaced
    return docs, raw


def test_a_handoff_an_earlier_version_wrote_is_held_to_its_binding_not_this_schema(tmp_path):
    docs, raw = earlier_docs(tmp_path)
    assert orders.earlier_version(raw) == orders.VERSION - 1
    with pytest.raises(ValueError, match="schema"):
        orders.validate(raw)
    assert orders.check(docs) == []
    from tools import publish_dashboard
    # an earlier version's evening wrote no morning file, and none is asked of it
    assert publish_dashboard.orders_files(tmp_path) == (orders.FILE, orders.POSITIONS_FILE)
    (docs / orders.MORNING_FILE).write_text('{"version": 1, "orders_sha256": "' + "0" * 64 + '"}')
    assert orders.check(docs) == ["orders-morning.json is not bound to orders.json"]
    # the morning after the merge this code writes its own cancel-all file, bound to that orders.json
    (docs / orders.MORNING_FILE).write_bytes(orders.encode(orders.earlier_version_morning(raw)))
    assert orders.check(docs) == []
    assert publish_dashboard.orders_files(tmp_path) == (orders.FILE, orders.POSITIONS_FILE, orders.MORNING_FILE)
    (docs / orders.MORNING_FILE).unlink()
    (docs / "data.json").write_bytes(page("next"))
    assert orders.check(docs) == ["orders.json is not bound to data.json"]
    with pytest.raises(RuntimeError, match="execution handoff"):
        publish_dashboard.orders_files(tmp_path)


@pytest.mark.parametrize("version", [orders.VERSION + 1, 0, True, "1", None, 1.0])
def test_only_an_earlier_whole_version_is_read_as_one(version):
    assert orders.earlier_version(json.dumps({"version": version}).encode()) is None
    assert orders.earlier_version(b"[1]") is None and orders.earlier_version(b"{") is None


def test_the_morning_cancels_every_ticket_of_an_earlier_versions_handoff(tmp_path, capsys):
    docs, raw = earlier_docs(tmp_path)
    out = tmp_path / "orders-morning.json"
    assert orders.main(["morning", "--orders", str(docs / orders.FILE), "--data", str(docs / "data.json"),
                        "--output", str(out)]) == 0
    assert f"written under version {orders.VERSION - 1}" in capsys.readouterr().out
    written = orders.validate(out.read_bytes(), "orders_morning")
    assert out.read_bytes() == orders.encode(orders.earlier_version_morning(raw))
    # no ticket of the earlier file is read, so none is listed and none can be go: every one is cancelled
    assert (written["status"], written["cancel_all"], written["cancel_all_reason"], written["tickets"]) == \
        ("no_check", True, "orders_earlier_version", [])
    assert written["orders_sha256"] == hashlib.sha256(raw).hexdigest() and written["mode"] == "paper"
    assert written["data_sha256"] == hashlib.sha256((docs / "data.json").read_bytes()).hexdigest()
    assert orders.main(["check", "--docs", str(docs)]) == 0
    assert "held to its binding alone" in capsys.readouterr().out
    with pytest.raises(ValueError, match="not written under an earlier version"):
        orders.earlier_version_morning((ROOT / "tests/fixtures/orders/full/orders.json").read_bytes())


def test_the_morning_publisher_writes_the_cancel_all_file_for_an_earlier_versions_handoff():
    from tools import publish_morning
    receipt = (MORNING / "observed.json").read_bytes()
    doc = json.loads(golden_orders())
    doc["version"] = orders.VERSION - 1
    earlier = orders.encode(orders.sealed(doc))
    assert publish_morning.orders_check(PUBLICATION, earlier) is None
    # the receipt is bound to the record and would give a decision; the earlier file is still not read
    assert publish_morning.derive_orders_morning(PUBLICATION, earlier, receipt) == \
        orders.encode(orders.earlier_version_morning(earlier))
    assert publish_morning.derive_orders_morning(PUBLICATION, golden_orders(), receipt) == \
        orders.encode(orders.build_morning(golden_orders(), receipt, PUBLICATION))


def test_the_readme_and_the_guide_name_the_earlier_version_rule_as_the_code_spells_it():
    readme = " ".join((ROOT / "README.md").read_text().split())
    guide = " ".join((ROOT / "docs" / "operations" / "orders.md").read_text().split())
    assert "(`orders.earlier_version()`)" in readme and hasattr(orders, "earlier_version")
    assert "(`orders_earlier_version`)" in readme and "orders_earlier_version" in orders.MORNING_REASONS
    assert "**Read the version.**" in guide and "nothing is entered from it" in guide
    assert "`orders_earlier_version`" in guide
