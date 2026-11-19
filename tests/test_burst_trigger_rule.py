"""The burst ticket's buy stop, as a versioned plan rule (``plan.burst_trigger_rule``).

The owner's decision of 19 November 2026: a burst ticket's buy stop is the
close plus the anticipation ticket's own cushion (``close_plus_cushion``),
where every record before it was made with the buy stop AT the close
(``close``). The limit and the 4% stop line are judged at the new trigger;
a record is replayed under the rule it archived, and one that archived none
under ``close``. These tests hold the three halves: the trigger over the
close, the stop rule at that trigger, and the old nights unchanged.
"""
from __future__ import annotations

import json
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest

from src import plan, provenance, record

ROOT = Path(__file__).resolve().parents[1]
ACCOUNT = plan.Account(equity=30_000, risk_pct=0.5, max_position_pct=25, max_open_positions=4)
#: the merge of #220, the last commit whose page fixtures were made under ``close``
LEGACY_COMMIT = "b1192f3a581790df599b37524ca97b71084fce96"
LEGACY_BLOB = "9545ec1d5260054c3fcce5a821b93cba7ae92da1"


def bar(**over):
    args = dict(ticker="XMPL", close=100.0, low=96.05, high=104.2, open_=96.5, prev_close=95.0,
                gain_pct=5.26, account=ACCOUNT)
    return {**args, **over}


# ------------------------------------------------------------ the trigger --
@pytest.mark.parametrize("close, cushion", [(5.0, plan.TRIGGER_CENTS), (19.28, plan.TRIGGER_CENTS),
                                            (124.21, 0.12), (250.0, 0.25)])
def test_the_production_trigger_is_the_close_plus_the_anticipation_cushion(close, cushion):
    assert plan.BURST_TRIGGER_RULE == "close_plus_cushion" and plan.BURST_TRIGGER_RULE in plan.BURST_TRIGGER_RULES
    assert plan.trigger_cushion(close) == max(plan.TRIGGER_CENTS, round(plan.TRIGGER_FRACTION * close, 2)) == cushion
    trigger = plan.burst_trigger(close, plan.BURST_TRIGGER_RULE)
    assert trigger == round(close + cushion, 2) > close
    assert plan.burst_trigger(close) == plan.burst_trigger(close, plan.LEGACY_BURST_TRIGGER_RULE) == close


def test_a_ticket_under_the_rule_is_bought_from_its_trigger_and_says_so():
    p = plan.burst_plan(**bar(low=97.0, high=100.5, open_=97.5), trigger_rule=plan.BURST_TRIGGER_RULE)
    trigger = round(100.0 + plan.trigger_cushion(100.0), 2)
    assert p["eligible"] and p["action"] == "buy_at_open"
    assert p["entry_ref"] == trigger == p["order_json"]["stop_price"] > p["burst"]["close"]
    assert p["trigger_rule"] == plan.BURST_TRIGGER_RULE and p["trigger_cushion"] == plan.trigger_cushion(100.0)
    assert f"stop ${trigger:.2f} limit ${p['limit']:.2f}" in p["order_line"]
    assert f"stop limit {trigger:.2f} / {p['limit']:.2f}" in p["order_readback"]
    assert any(f"the buy stop at ${trigger:.2f} would still trigger" in t for t in p["order_terms"])
    assert p["trigger_note"].startswith(f"the buy stop ${trigger:.2f} is the $100.00 close plus ${plan.trigger_cushion(100.0):.2f}")
    # the skip lines stay measured from the close: the trigger moved, the bar did not
    assert p["entry_low"] == round(100.0 * (1 - plan.ENTRY_BELOW_PCT / 100), 2)
    assert p["day2_spent_above"] == round(100.0 * (1 + plan.ENTRY_ABOVE_PCT / 100), 2)
    # an indicative entry is never under the buy stop
    assert p["planned_entry"] >= p["entry_ref"]


def test_an_unknown_rule_is_a_refusal_never_a_guess():
    with pytest.raises(ValueError):
        plan.burst_trigger(100.0, "close_plus_a_lot")
    with pytest.raises(ValueError):
        plan.burst_plan(**bar(), trigger_rule="close_plus_a_lot")
    with pytest.raises(ValueError):
        plan.archived_burst_trigger_rule({"plan": {"burst_trigger_rule": "close_plus_a_lot"}})
    assert plan.archived_burst_trigger_rule({"plan": {}}) == plan.archived_burst_trigger_rule(None) == "close"
    assert plan.archived_burst_trigger_rule({"plan": {"burst_trigger_rule": "close_plus_cushion"}}) == "close_plus_cushion"
    assert not plan.replayable_burst_trigger_rule("close_plus_a_lot") and not plan.replayable_burst_trigger_rule(1)
    assert all(plan.replayable_burst_trigger_rule(r) for r in (None, *plan.BURST_TRIGGER_RULES))


# ------------------------------------------------- the 4% line at the trigger --
def test_the_stop_line_is_judged_at_the_new_trigger_and_a_ticket_it_cannot_hold_is_withheld():
    """The burst low's ceiling (96.05 / 0.96, floored: $100.05) sits between
    the $100.00 close and the $100.10 trigger, and the midpoint ($100.13) is
    over the trigger: under ``close`` the low buys a narrow ticket, under the
    production rule no limit above the buy stop keeps a stop inside the line."""
    legacy = plan.burst_plan(**bar())
    assert legacy["eligible"] and legacy["stop_basis"] == "burst_low" and legacy["limit"] == 100.05 > legacy["entry_ref"]
    new = plan.burst_plan(**bar(), trigger_rule=plan.BURST_TRIGGER_RULE)
    assert not new["eligible"] and new["action"] == "refused" and new["ticket_refusal"] == "no_room_above_the_trigger"
    assert new["order_json"] is None and new["reason"].startswith("ticket withheld: no limit above the $100.10 buy stop")
    assert "caps the limit at $100.05, at or under that buy stop" in new["reason"]


@pytest.mark.parametrize("close, low, high", [(124.21, 121.42, 124.80), (19.28, 18.79, 19.38), (62.10, 60.70, 62.30),
                                              (8.40, 8.10, 8.55), (310.0, 300.5, 312.0)])
def test_every_admitted_ticket_keeps_its_stop_inside_the_line_at_its_limit_and_under_its_trigger(close, low, high):
    p = plan.burst_plan(**bar(close=close, low=low, high=high, open_=low, prev_close=round(close / 1.05, 2)),
                        trigger_rule=plan.BURST_TRIGGER_RULE)
    if p["eligible"]:
        assert p["stop"] < p["entry_ref"] < p["limit"] <= p["day2_spent_above"]
        assert 100 * (p["limit"] - p["stop"]) / p["limit"] <= plan.MAX_STOP_PCT
        assert p["shares"] * (p["limit"] - p["stop"]) <= p["sizing"]["budget_usd"] + 1e-9
    else:
        assert p["ticket_refusal"] in plan.TICKET_REFUSALS and p["order_json"] is None


# -------------------------------------------------------- old nights ----
def test_a_legacy_plan_keeps_its_exact_shape():
    """A plan under ``close`` -- what every older record carries -- has no
    field the new rule adds, so a replay of an older record is byte for byte."""
    legacy = plan.burst_plan(**bar(low=97.0, high=100.5, open_=97.5))
    assert not {"trigger_rule", "trigger_cushion", "trigger_note"} & set(legacy)
    assert legacy["entry_ref"] == legacy["burst"]["close"] == legacy["order_json"]["stop_price"]


def test_an_old_pick_is_walked_from_the_buy_stop_it_archived():
    """record.replay() reads a pick's own ``entry_ref``: an older pick at the
    close is walked from the close whatever rule is current."""
    pick = {"ticker": "XMPL", "date": "2026-01-05", "kind": "burst", "entry_ref": 100.0, "entry_low": 98.0,
            "entry_high": 101.6, "stop": 97.6, "shares": 10}
    day1 = {"date": "2026-01-06", "o": 100.05, "h": 100.5, "l": 99.0, "c": 100.2, "v": 1}
    assert record.fill(pick, day1)[:2] == ("filled", 100.05)
    # the same day against a pick at the production trigger opens under it
    new = {**pick, "entry_ref": plan.burst_trigger(100.0, plan.BURST_TRIGGER_RULE)}
    assert record.fill(new, day1)[0] != "filled"


@pytest.fixture(scope="module")
def legacy_record() -> dict:
    """The page fixture ``full`` as the pipeline wrote it before the rule,
    read out of git at #220's merge and held to its blob (fetched by whole id
    on a shallow checkout; never skipped)."""
    def present() -> bool:
        return subprocess.run(["git", "cat-file", "-e", f"{LEGACY_COMMIT}^{{commit}}"],
                              cwd=ROOT, capture_output=True).returncode == 0
    if not present():
        done = subprocess.run(["git", "fetch", "--quiet", "--no-tags", "--depth=1", "origin", LEGACY_COMMIT],
                              cwd=ROOT, capture_output=True, text=True)
        assert done.returncode == 0 and present(), f"the legacy fixture could not be fetched: {done.stderr.strip()}"
    blob = subprocess.run(["git", "rev-parse", f"{LEGACY_COMMIT}:tests/fixtures/page/full.json"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout.strip()
    assert blob == LEGACY_BLOB, blob
    raw = subprocess.run(["git", "cat-file", "-p", f"{LEGACY_COMMIT}:tests/fixtures/page/full.json"], cwd=ROOT,
                         capture_output=True, check=True).stdout
    data = json.loads(raw)
    data.pop("fixture", None)
    return data


def test_a_record_made_before_the_rule_replays_under_close_unchanged(legacy_record):
    data = deepcopy(legacy_record)
    assert "burst_trigger_rule" not in data["rules"]["plan"]
    planned = [b for b in data["bursts"] if b.get("plan")]
    assert planned and all(b["plan"]["entry_ref"] == b["plan"]["burst"]["close"] for b in planned)
    assert all("trigger_rule" not in b["evidence"]["planning"]["inputs"] for b in planned)
    result = provenance.verify(data, objects=ROOT / "tests/fixtures/provenance/objects")
    assert result["status"] == "PASS", result
    assert data == legacy_record, "verification must not repair a record"


def made(tmp_path, monkeypatch, *, sealed=None, archived=None) -> dict:
    """The pipeline's own ``full`` night, its tickets sealed under ``sealed``
    and its rules archiving ``archived`` (each the production rule unless
    named): a record whose evidence identities are its own, so only the rule
    the verifier reads can tell the two apart."""
    from tools import make_fixture
    if sealed is not None:
        monkeypatch.setattr(plan, "BURST_TRIGGER_RULE", sealed)
    if archived is not None:
        monkeypatch.setitem(plan.RULES, "plan.burst_trigger_rule", archived)
    data = make_fixture.run_variant("full", tmp_path)
    data.pop("fixture", None)
    return data


def test_the_verifier_holds_the_sealed_rule_to_the_archived_one(tmp_path, monkeypatch):
    current = json.loads((ROOT / "tests/fixtures/page/full.json").read_text())
    current.pop("fixture", None)
    assert current["rules"]["plan"]["burst_trigger_rule"] == plan.BURST_TRIGGER_RULE
    assert provenance.verify(current, require_sources=False)["status"] == "PASS"
    # tickets sealed at the close under rules that say the cushion: every evidence identity
    # is its own, and the publication gate (provenance.require) refuses the night on the
    # sealed inputs, before anything is installed
    with pytest.raises(SystemExit, match="plan inputs differ from source candidate/account/regime"):
        made(tmp_path / "mixed", monkeypatch, sealed=plan.LEGACY_BURST_TRIGGER_RULE)
    assert not (tmp_path / "mixed" / "data.json").exists()


def test_a_rule_the_planner_does_not_implement_is_refused_before_publication(tmp_path, monkeypatch):
    with pytest.raises(SystemExit, match="provenance refused"):
        made(tmp_path, monkeypatch, archived="close_plus_a_lot")
    assert not (tmp_path / "data.json").exists()


def test_the_evening_names_the_production_rule_and_archives_it(tmp_path, monkeypatch):
    assert plan.RULES["plan.burst_trigger_rule"] == plan.BURST_TRIGGER_RULE
    # a night the pipeline makes now, as well as the committed fixture it made
    for current in (made(tmp_path, monkeypatch), json.loads((ROOT / "tests/fixtures/page/full.json").read_text())):
        assert current["rules"]["plan"]["burst_trigger_rule"] == plan.BURST_TRIGGER_RULE
        planned = [b for b in current["bursts"] if b.get("plan")]
        assert planned and all(b["plan"]["entry_ref"] == plan.burst_trigger(b["plan"]["burst"]["close"], plan.BURST_TRIGGER_RULE)
                               > b["plan"]["burst"]["close"] for b in planned)
        assert all(b["evidence"]["planning"]["inputs"]["trigger_rule"] == plan.BURST_TRIGGER_RULE for b in planned)


def test_the_stop_research_and_brief_read_an_older_plan_family_as_this_planner():
    family = {k.partition(".")[2]: v for k, v in plan.RULES.items()}
    assert plan.archived_rules_differ(family) == []
    older = {k: v for k, v in family.items() if k != "burst_trigger_rule"}
    assert plan.archived_rules_differ(older) == []
    assert plan.archived_rules_differ({**family, "burst_trigger_rule": "x"}) == ["plan.burst_trigger_rule"]
    assert plan.archived_rules_differ({**family, "max_stop_pct": 3.0}) == ["plan.max_stop_pct"]
    assert plan.archived_rules_differ({**family, "extra": 1}) == ["plan.extra"]
