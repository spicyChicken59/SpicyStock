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
from datetime import date
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
    assert [c["status"] for c in checks.values()] == ["pass", "pass", "pass", "not_evaluated", "pass"]
    red = night(json.loads(page("red")))
    assert (red["light"]["status"], red["light"]["reason"]) == ("fail", "light_red")
    degraded = night(json.loads(page("degraded")))
    assert (degraded["data"]["status"], degraded["data"]["reason"]) == ("fail", "data_degraded")
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
    assert doc["summary"]["go"] == 2
    assert night_reasons(doc) == ["cross_check_not_run"] and doc["trade_allowed"] is False


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
        d["run"]["earnings"]["rows"].append({"stage": admitted["kind"], "ticker": admitted["ticker"],
                                             "items": {"status": "material", "sentence": "item 1.01"}})
    held = ticket_after(flag)
    assert (held["status"], held["reasons"]) == ("human_review", ["sec_flag"])


def test_the_full_fixtures_ticket_is_held_for_review_by_its_material_8k_item():
    doc = built("full")
    assert doc["tickets"][0]["status"] == "human_review" and doc["tickets"][0]["reasons"] == ["sec_flag"]
    assert {"scope": "AAPL", "code": "sec_flag"} in doc["reasons"]


def test_the_mode_is_paper_and_live_ready_is_not_yet_evaluated():
    doc = built()
    assert doc["mode"] == orders.MODE == "paper"
    assert doc["live_ready"] == {"value": False, "reasons": [orders.LIVE_READY_REASON]}


# ------------------------------------------------------------- the morning --
def golden_orders() -> bytes:
    return orders.encode(orders.build(PUBLICATION))


@pytest.mark.parametrize("receipt, decision, reasons", [
    ("observed", "cancel", ["night_not_allowed", "trigger_crossed"]),
    ("halted", "cancel", ["night_not_allowed", "halted", "trigger_crossed"]),
    ("corporate-excluded", "cancel", ["night_not_allowed", "news_or_sec_flag", "trigger_crossed"]),
    ("outage", "cancel", ["night_not_allowed", "stale_data"]),
    ("no-tickets", "cancel", ["night_not_allowed", "no_morning_check"]),
])
def test_each_committed_morning_receipt_gives_its_cancel_reasons(receipt, decision, reasons):
    raw = golden_orders()
    out = orders.build_morning(raw, (MORNING / f"{receipt}.json").read_bytes(), PUBLICATION)
    assert [(t["decision"], t["reasons"]) for t in out["tickets"]] == [(decision, reasons)]
    assert out["orders_sha256"] == hashlib.sha256(raw).hexdigest()
    assert out["morning_bound"] is (receipt != "no-tickets")


def allowed_orders() -> tuple[bytes, dict]:
    """The golden orders with trade allowed, sealed again: the morning's own rules can then be read alone."""
    doc = json.loads(golden_orders())
    return resealed(doc, trade_allowed=True, reasons=[]), doc


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
    for status, reason in (("human_review", "news_or_sec_flag"), ("blocked", "ticket_not_go")):
        forged = copy.deepcopy(doc)
        forged["tickets"][0] = orders.sealed({**forged["tickets"][0], "status": status})
        forged_raw = resealed(forged, trade_allowed=True, reasons=[])
        receipt = json.loads((MORNING / "observed.json").read_bytes())
        receipt["rows"][0]["price_checks"] = {"trade": "below_trigger", "ask": "below_trigger"}
        out = orders.build_morning(forged_raw, json.dumps(receipt).encode())
        assert out["tickets"][0]["decision"] == "cancel" and reason in out["tickets"][0]["reasons"]


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


def test_the_evening_writes_both_files_bound_to_the_installed_record(tmp_path):
    docs = docs_with(tmp_path)
    result = orders.write_publication(docs)
    assert result["tickets"] == 1 and result["trade_allowed"] is False
    assert orders.check(docs) == []
    doc = json.loads((docs / orders.FILE).read_bytes())
    assert doc["source"]["data_sha256"] == hashlib.sha256(page("full")).hexdigest()


def test_the_evening_removes_a_morning_file_bound_to_earlier_tickets(tmp_path):
    docs = docs_with(tmp_path)
    (docs / orders.MORNING_FILE).write_text('{"orders_sha256": "' + "0" * 64 + '"}')
    orders.write_publication(docs)
    assert not (docs / orders.MORNING_FILE).exists()


def test_an_unbound_handoff_is_removed_and_a_bound_one_is_kept(tmp_path):
    docs = docs_with(tmp_path)
    orders.write_publication(docs)
    assert orders.discard_unbound(docs) == []
    (docs / "data.json").write_bytes(page("next"))
    assert orders.check(docs) == ["orders.json is not bound to data.json"]
    assert orders.discard_unbound(docs) == [orders.FILE, orders.POSITIONS_FILE]
    assert not (docs / orders.FILE).exists()


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
    assert publish_dashboard.orders_files(root) == (orders.FILE, orders.POSITIONS_FILE)
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


@pytest.mark.parametrize("run_id, ref, outcome", [
    ("another-run", "refs/heads/main", "morning_receipt_not_this_run"),
])
def test_the_morning_commit_refuses_a_receipt_another_run_published(handoff_repository, run_id, ref, outcome):
    from tools import publish_morning
    assert publish_morning.publish_orders(handoff_repository, ref=ref, run_id=run_id) == outcome


def test_the_morning_commit_needs_main_and_a_run(handoff_repository):
    from tools import publish_morning
    with pytest.raises(ValueError, match="requires_main"):
        publish_morning.publish_orders(handoff_repository, ref="refs/heads/other", run_id="synthetic-observed")
    with pytest.raises(ValueError):
        publish_morning.publish_orders(handoff_repository, ref="refs/heads/main", run_id="")


def test_the_morning_check_names_each_missing_file():
    from tools import publish_morning
    receipt = (MORNING / "observed.json").read_bytes()
    assert publish_morning.orders_check(PUBLICATION, None, receipt, "x") == "no_orders_on_main"
    assert publish_morning.orders_check(PUBLICATION, golden_orders(), None, "x") == "no_morning_receipt_on_main"
    assert publish_morning.orders_check(page("full"), golden_orders(), receipt, "synthetic-observed") == \
        "orders_not_bound_to_record"
    assert publish_morning.orders_check(PUBLICATION, golden_orders(), receipt, "synthetic-observed") is None


def test_the_morning_workflow_publishes_the_go_cancel_after_the_receipt():
    import yaml
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "morning.yml").read_text())
    steps = wf["jobs"]["persist"]["steps"]
    names = [s.get("name") for s in steps]
    step = next(s for s in steps if s.get("name") == "Publish the morning go/cancel for the execution handoff")
    assert step["run"] == "python -m tools.publish_morning orders"
    assert names.index("Publish only against the unchanged source record") < names.index(step["name"])
