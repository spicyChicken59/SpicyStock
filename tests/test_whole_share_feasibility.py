"""The whole-share feasibility reading, held to hand-sized rows: a reading
over the production cascade at an account, never a rule, a ticket or an edge."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from src import breadth, pipeline, plan
from tests.test_funnel import production  # noqa: F401  -- the retained 9 October publication, out of git by commit
from tools import whole_share_feasibility as ws

ROOT = Path(__file__).resolve().parent.parent
FULL = ROOT / "tests/fixtures/page/full.json"
ACCOUNT = {"equity": 2000.0, "risk_pct": 0.5, "max_position_pct": 25.0, "max_open_positions": 4}


def bar(ticker, close, low, high, open_, prev_close, grade, vetoes=()):
    return {"ticker": ticker, "close": close, "low": low, "high": high, "open": open_, "prev_close": prev_close,
            "gain_pct": round(100 * (close / prev_close - 1), 2), "scan": "burst", "extension_pct": None,
            "grade_mechanical": grade, "grade": grade, "vetoes": list(vetoes)}


def record(verdict="yellow", account=ACCOUNT, bursts=None, watchlist=None):
    return {"schema_version": 2, "app": {"rules_version": "test"}, "fixture": False,
            "run": {"session": "2026-10-09", "session_state": "open", "published_at": "2026-10-10T00:00:00Z"},
            "account": dict(account) if account else None,
            "rules": {"pipeline": {"trade_grades": list(pipeline.TRADE_GRADES), "yellow_grades": list(pipeline.YELLOW_GRADES)}},
            "breadth": {"regime": {"verdict": verdict, "size_multiplier": breadth.SIZE_MULTIPLIER[verdict]}},
            "bursts": bursts if bursts is not None else [],
            "watchlist": {"top": watchlist or []}}


# LOW: stop at the burst low 19.40, the stop-line ceiling 19.40/0.96 = 20.208 floored
# to 20.20 under the +4% line 20.80, so the limit is 20.20 and the stop sits 3.96%
# under it: the risk is halved. GREEN budget $10 x 0.5 = $5.00 over $0.80 a share
# = 6 shares; YELLOW $2.50 -> 3; RED 0. HIGH: the same shape at ten times the
# price: $8.08 a share against $5.00 -> no whole share at any regime.
LOW = bar("LOW", 20.00, 19.40, 20.30, 19.50, 19.20, "A+")
HIGH = bar("HIGH", 200.00, 194.00, 203.00, 195.00, 192.00, "A")
VETOED = {**bar("VETO", 20.00, 19.40, 20.30, 19.50, 19.20, "A+"), "vetoes": ["up_days"]}
BGRADE = bar("BGR", 10.00, 9.70, 10.15, 9.75, 9.60, "B")


def test_hand_sized_rows_by_band():
    r = ws.reading(record("yellow", bursts=[LOW, HIGH, VETOED, BGRADE]), source="t", identity="i")
    assert r["candidates"] == 4 and r["missing_inputs"] == [] and r["account"]["source"] == "archived"
    tonight, yellow, green = (r["bands"][b] for b in ("tonight", "yellow", "green"))
    assert (tonight["verdict"], tonight["admitted"], tonight["multiplier"]) == ("yellow", ["A+"], 0.5)
    assert (green["verdict"], green["admitted"], green["multiplier"]) == ("green", ["A+", "A"], 1.0)
    # YELLOW admits A+ alone: LOW is in band (3 shares at $2.50), VETO is kept out by its veto
    assert tonight["in_band"] == yellow["in_band"] == {"candidates": 1, "eligible": 1, "whole_share": 1, "no_share": 0}
    # GREEN admits A too: HIGH passes the stop rule and sizes to no whole share
    assert green["in_band"] == {"candidates": 2, "eligible": 2, "whole_share": 1, "no_share": 1}
    # by mechanical grade, whatever the band admits: both A+ bars size at green
    assert green["by_mechanical_grade"]["A+"] == {"candidates": 2, "eligible": 2, "whole_share": 2, "no_share": 0}
    assert green["by_mechanical_grade"]["A"] == {"candidates": 1, "eligible": 1, "whole_share": 0, "no_share": 1}
    assert green["by_mechanical_grade"]["B"]["candidates"] == 1 and green["by_mechanical_grade"]["skip"]["candidates"] == 0


def test_the_hand_arithmetic_is_the_cascade_s_own():
    acct = plan.Account(**ACCOUNT)
    low = {m: ws.study.current_plan(LOW, m, acct) for m in (0.0, 0.5, 1.0)}
    assert low[1.0]["limit"] == 20.20 and low[1.0]["stop"] == 19.40 and low[1.0]["stop_pct"] == 3.96
    assert low[1.0]["multipliers"]["stop_risk"] == 0.5 and low[1.0]["risk_per_share"] == 0.80
    assert [low[m]["shares"] for m in (0.0, 0.5, 1.0)] == [0, 3, 6]
    high = ws.study.current_plan(HIGH, 1.0, acct)
    assert high["eligible"] and high["limit"] == 202.08 and high["risk_per_share"] == 8.08 and high["shares"] == 0


def test_a_red_night_reads_nothing_tonight_and_the_counterfactuals_beside_it():
    r = ws.reading(record("red", bursts=[LOW, HIGH]), source="t", identity="i")
    t = r["bands"]["tonight"]
    assert (t["verdict"], t["admitted"], t["multiplier"]) == ("red", [], 0.0)
    assert t["in_band"] == {"candidates": 0, "eligible": 0, "whole_share": 0, "no_share": 0}
    # the row is still sized at the RED multiplier by grade: eligible, no share
    assert t["by_mechanical_grade"]["A+"] == {"candidates": 1, "eligible": 1, "whole_share": 0, "no_share": 1}
    assert r["bands"]["green"]["in_band"]["whole_share"] == 1 and r["bands"]["yellow"]["in_band"]["whole_share"] == 1


@pytest.mark.parametrize("multiplier,line,ideal", [(1.0, 125.00, 500.00), (0.5, 62.50, 250.00), (0.0, 0.0, 0.0)])
def test_one_share_ceilings_against_the_sizing_function(multiplier, line, ideal):
    acct = plan.Account(**ACCOUNT)
    c = ws.one_share_ceilings(acct, multiplier)
    assert (c["stop_line"], c["ideal_stop"]) == (line, ideal)
    assert c["risk_budget"] == round(10.0 * multiplier, 2) and c["risk_budget_at_stop_line"] == round(5.0 * multiplier, 2)
    if multiplier:
        # at the ceiling a stop on his 4% line buys one share; a dollar over it buys none
        assert plan.size(line, round(line * 0.96, 2), acct, multiplier * plan.STOP_RISK_MULTIPLIER).shares == 1
        assert plan.size(line + 1.00, round((line + 1.00) * 0.96, 2), acct, multiplier * plan.STOP_RISK_MULTIPLIER).shares == 0
        # the position cap, not the risk, binds the ideal-stop ceiling at this account: one share still fits under it
        assert plan.size(min(ideal, acct.max_position_usd), round(min(ideal, acct.max_position_usd) * 0.98, 2), acct, multiplier).shares == 1


def test_a_counterfactual_account_is_labelled_and_moves_the_count():
    r = ws.reading(record("yellow", bursts=[LOW, HIGH]), source="t", identity="i", overrides={"equity": 10000.0})
    assert r["account"]["source"] == "counterfactual" and r["account"]["used"]["equity"] == 10000.0
    assert r["account"]["archived"] == ACCOUNT, "the record's own account travels beside the one used"
    # $25 at green over $8.08 a share: HIGH sizes to 3
    assert r["bands"]["green"]["in_band"] == {"candidates": 2, "eligible": 2, "whole_share": 2, "no_share": 0}
    assert r["bands"]["green"]["ceilings"]["stop_line"] == 625.00


def test_a_record_without_an_archived_account_is_sized_at_the_library_defaults_and_says_so():
    r = ws.reading(record("yellow", account=None, bursts=[LOW]), source="t", identity="i")
    assert r["account"]["source"] == "library_defaults" and r["account"]["archived"] is None
    assert r["account"]["used"] == plan.Account().to_dict()


def test_unusable_rows_are_named_and_counted_apart():
    broken = {**LOW, "ticker": "BAD", "low": 25.0}
    r = ws.reading(record("yellow", bursts=[LOW, broken, "not a row"]), source="t", identity="i")
    assert r["candidates"] == 1
    assert [m["ticker"] for m in r["missing_inputs"]] == ["BAD", None]
    assert r["bands"]["green"]["in_band"]["candidates"] == 1


def test_anticipation_is_read_off_the_recorded_plans_only():
    top = [{"ticker": "KE", "plan": {"eligible": True, "shares": 1}}, {"ticker": "SN", "plan": {"eligible": True, "shares": 0}},
           {"ticker": "MG", "plan": {"eligible": False, "shares": 3}}, {"ticker": "ZZ", "plan": None}]
    r = ws.reading(record("yellow", watchlist=top), source="t", identity="i", overrides={"equity": 1.0e6})
    assert r["anticipation"] == {"listed": 4, "eligible": 2, "whole_share": 1, "unreadable": 1,
                                 "basis": "recorded plans at the record's own account and regime"}


@pytest.mark.parametrize("spoil", [lambda d: d.update(fixture="full"), lambda d: d.update(schema_version=1),
                                   lambda d: d.pop("bursts"), lambda d: d.update(run=None)])
def test_a_non_publication_is_refused(spoil):
    data = record("yellow", bursts=[LOW])
    spoil(data)
    with pytest.raises(ws.FeasibilityError, match="not a real schema-2 publication"):
        ws.reading(data, source="t", identity="i")


def test_an_override_the_account_does_not_have_is_refused():
    with pytest.raises(ws.FeasibilityError):
        ws.reading(record("yellow", bursts=[LOW]), source="t", identity="i", overrides={"leverage": 2})
    with pytest.raises(ws.FeasibilityError, match="account"):
        ws.reading(record("yellow", bursts=[LOW]), source="t", identity="i", overrides={"equity": -1.0})


def test_the_full_fixture_reconciles():
    data = json.loads(FULL.read_text())
    data["fixture"] = False   # the fixture is what the pipeline writes; the reading refuses a marked one
    r = ws.reading(data, source="full", identity="i")
    usable = sum(1 for b in data["bursts"] if ws.study.usable_bar(b) is None)
    assert r["candidates"] == usable == len(data["bursts"]) - len(r["missing_inputs"])
    for band in r["bands"].values():
        i = band["in_band"]
        assert i["whole_share"] + i["no_share"] == i["eligible"] <= i["candidates"] <= r["candidates"]
        assert sum(g["candidates"] for g in band["by_mechanical_grade"].values()) == r["candidates"]
    assert r["account"]["source"] == "archived"
    assert r["account"]["used"] == {k: data["account"][k] for k in ws.ACCOUNT_FIELDS}


def test_totals_sum_the_readings_and_the_summary_says_so():
    a = ws.reading(record("yellow", bursts=[LOW, HIGH]), source="a", identity="i")
    b = ws.reading(record("red", bursts=[LOW]), source="b", identity="j")
    t = ws.totals([a, b])
    assert (t["publications"], t["sessions"], t["regimes"]) == (2, 1, {"yellow": 1, "red": 1})
    assert t["bands"]["green"]["in_band"] == {"candidates": 3, "eligible": 3, "whole_share": 2, "no_share": 1}
    assert t["bands"]["tonight"]["in_band"] == {"candidates": 1, "eligible": 1, "whole_share": 1, "no_share": 0}
    text = ws.summary_text(t)
    assert "green: 3 in band, 3 past the stop rule, 2 sizing to a whole share" in text
    assert "2 publications over 1 sessions" in text and "Anticipation: 0 listed" in text
    assert ws.table([a, b]).count("\n") == 3 and "$62.50 / $125.00" in ws.table([a, b])


def test_cli_reads_a_file_and_writes_its_outputs(tmp_path, capsys):
    data = json.loads(FULL.read_text())
    data["fixture"] = False
    src = tmp_path / "rec.json"
    src.write_text(json.dumps(data))
    out_json, out_md = tmp_path / "o.json", tmp_path / "o.md"
    assert ws.main([str(src), "--json", str(out_json), "--markdown", str(out_md), "--equity", "2000"]) == 0
    written = json.loads(out_json.read_text())
    assert (written["version"], written["policy"], written["overrides"]) == (ws.VERSION, ws.POLICY, {"equity": 2000.0})
    assert len(written["readings"]) == 1 and written["readings"][0]["account"]["source"] == "counterfactual"
    assert out_md.read_text().startswith("| session |")
    assert "publications over 1 sessions" in capsys.readouterr().out
    assert ws.main([str(FULL)]) == 2, "a marked fixture is refused"
    assert "refused" in capsys.readouterr().err


def test_the_retained_9_october_publication_at_its_archived_account(production):
    """The publication Mo's loop measured on 9 October, sized again at the
    $2,000 account it archived: the yellow band admits A+ alone and the
    record has none, so tonight and yellow read zero; the green band is the
    counterfactual the owner asked for, and its counts are the cascade's."""
    r = ws.reading(deepcopy(production), source="9oct", identity="i")
    assert r["account"] == {"used": ACCOUNT, "source": "archived", "archived": ACCOUNT} and r["regime"] == "yellow"
    assert r["bands"]["tonight"]["in_band"] == r["bands"]["yellow"]["in_band"] == {"candidates": 0, "eligible": 0, "whole_share": 0, "no_share": 0}
    in_band = [b for b in production["bursts"] if b["grade_mechanical"] in pipeline.TRADE_GRADES and not b["vetoes"]]
    g = r["bands"]["green"]["in_band"]
    assert g["candidates"] == len(in_band) == 53
    # independently: the whole-share names are those whose green-sized ticket has a share
    acct = plan.Account(**ACCOUNT)
    sized = [ws.study.current_plan(b, 1.0, acct) for b in in_band]
    assert g["eligible"] == sum(1 for p in sized if p["eligible"]) == 48
    assert g["whole_share"] == sum(1 for p in sized if p["eligible"] and p["shares"] >= 1) == 26
    assert r["bands"]["green"]["ceilings"]["stop_line"] == 125.00 and r["anticipation"]["listed"] == 5
