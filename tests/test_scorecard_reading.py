"""The scorecard read honestly (src/scorecard_reading.py) and the private real-
against-model reader (tools/positions_compare.py).

These hold the block to the model record it copies and never to the
scorecard's own arithmetic, which must not move; the breadth revisions to the
two records they compare; the block's shape to the validator under the rules
that write it; the page, the mail and orders.json to its sentences; and the
real R to hand-computed trades."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src import orders, pipeline, record, report, scorecard_reading as sr

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "tests" / "fixtures" / "page"


def page(name: str) -> dict:
    return json.loads((PAGE / f"{name}.json").read_text())


BLOCK = {
    "status": "computed", "reason": None, "tickets": 5, "distinct_setups": 4, "reissued_tickets": 1,
    "buckets": {"settled": 2}, "buckets_by_setup": {"settled": 2}, "sum_r": -0.5,
    "eras": [{"label": "$2,000 at 0.5% risk", "issued_equity": 2000.0, "risk_pct": 0.5, "from": "2026-10-01",
              "through": "2026-10-20", "tickets": 3, "setups": 2, "settled": 1, "wins": 0, "losses": 1,
              "breakeven": 0, "sum_r": -1.0},
             {"label": "$30,000 at 0.5% risk", "issued_equity": 30000.0, "risk_pct": 0.5, "from": "2026-11-04",
              "through": "2026-11-18", "tickets": 1, "setups": 1, "settled": 1, "wins": 1, "losses": 0,
              "breakeven": 0, "sum_r": 0.5},
             {"label": "account not recorded", "issued_equity": None, "risk_pct": None, "from": "2026-09-10",
              "through": "2026-09-10", "tickets": 1, "setups": 1, "settled": 0, "wins": 0, "losses": 0,
              "breakeven": 0, "sum_r": None}],
    "stops": {"count": 2, "unexamined": 0, "sum_r": {"booked": -2.0, "at_close": -2.6, "at_low": -3.1},
              "settled_sum_r": {"booked": -0.5, "at_close": -1.1, "at_low": -1.6}},
    "sentences": ["The model record's own words."],
}


# --------------------------------------------------------------- the block --
def test_the_block_copies_the_model_records_figures_and_says_them():
    out = sr.build(BLOCK, None, page("full"))
    assert out["status"] == "computed" and out["model_record"]["distinct_setups"] == 4
    assert out["model_record"]["stops"]["sum_r"] == BLOCK["stops"]["sum_r"]
    said = out["sentences"]
    assert said[0] == "5 tickets in the scorecard's window are 4 distinct setups."
    assert said[1].startswith("By model account: $2,000 at 0.5% risk, 3 tickets from 2026-10-01 through 2026-10-20, "
                              "1 settled, -1.00R; $30,000 at 0.5% risk, 1 ticket")
    assert said[1].endswith("No model account is recorded for 1 more ticket.")
    assert said[2] == ("The 2 stopped tickets booked at the stop sum to -2.00R; read at that session's close, -2.60R; "
                       "at its low, -3.10R.")
    assert said[-1] == sr.REAL_VS_MODEL and out["real_vs_model"]["status"] == "private"


@pytest.mark.parametrize("block, status", [(None, "not_computed"),
                                           ({"status": "unreconciled", "reason": "two rows differ"}, "unreconciled"),
                                           ({"status": "nonsense"}, "not_computed")])
def test_a_model_record_that_was_not_computed_or_does_not_reconcile_says_so_and_quotes_nothing(block, status):
    out = sr.build(block, None, page("full"))
    assert out["status"] == status and out["model_record"]["status"] == status
    assert out["sentences"][0].startswith(f"The model record is {status.replace('_', ' ')}: ")
    assert "distinct setups" not in " ".join(out["sentences"])


def test_breadth_revisions_name_each_session_two_records_read_differently():
    before, after = page("full"), page("next")
    same = sr.breadth_revisions(before, after)
    assert same["differ_count"] == 0 and same["compared"] > 0 and "read the same breadth figures" in same["sentence"]
    revised = copy.deepcopy(after)
    target = next(h for h in revised["breadth"]["history"] if h["date"] in {x["date"] for x in before["breadth"]["history"]})
    target["up4"] += 3
    out = sr.breadth_revisions(before, revised)
    assert out["differ_count"] == 1 and out["differ"][0]["session"] == target["date"]
    assert out["differ"][0]["revised"]["up4"] == out["differ"][0]["published"]["up4"] + 3
    assert f"{target['date']} up4 {target['up4'] - 3} to {target['up4']}" in out["sentence"]
    assert sr.breadth_revisions(None, after)["sentence"] == "There is no earlier publication's breadth history to compare."


def test_more_revisions_than_the_bound_are_counted_not_named():
    before, after = page("full"), copy.deepcopy(page("next"))
    shared = {x["date"] for x in before["breadth"]["history"]}
    for h in after["breadth"]["history"]:
        if h["date"] in shared:
            h["down4"] += 1
    out = sr.breadth_revisions(before, after)
    assert out["differ_count"] > sr.MAX_REVISIONS and len(out["differ"]) == sr.MAX_REVISIONS
    assert f"; and {out['differ_count'] - sr.MAX_REVISIONS} more." in out["sentence"]
    import re
    assert len(re.findall(r"\d{4}-\d{2}-\d{2} (?:up4|down4|ratio_10d) ", out["sentence"])) == sr.MAX_REVISIONS


# ----------------------------------------------------------- the validator --
def test_the_validator_asks_for_the_block_only_under_rules_that_write_it_and_holds_its_shape():
    data = page("full")
    assert data["rules"]["pipeline"]["scorecard_reading_version"] == sr.VERSION
    assert sr.faults(data) == []
    older = copy.deepcopy(data)
    del older["rules"]["pipeline"]["scorecard_reading_version"]
    del older["scorecard_reading"]
    assert sr.faults(older) == []
    for change, words in ((lambda d: d.pop("scorecard_reading"), "missing"),
                          (lambda d: d["scorecard_reading"].update(sentences=[1]), "sentences"),
                          (lambda d: d["scorecard_reading"].update(status="fine"), "status"),
                          (lambda d: d["scorecard_reading"]["real_vs_model"].update(sentence="x"), "real_vs_model"),
                          (lambda d: d["scorecard_reading"].update(breadth_revisions=None), "breadth_revisions")):
        forged = copy.deepcopy(data)
        change(forged)
        assert any(words in f for f in sr.faults(forged)), words
        with pytest.raises(ValueError):
            report.validate(forged)
    stray = copy.deepcopy(older)
    stray["scorecard_reading"] = data["scorecard_reading"]
    assert sr.faults(stray) == ["scorecard_reading present under rules that do not write it"]


def test_the_scorecards_own_numbers_do_not_move():
    data = page("next")
    assert set(data["scorecard"]) and "scorecard_reading" not in json.dumps(data["scorecard"])
    assert record.scorecard.__module__ == "src.record"


def test_the_evening_composes_the_block_from_the_model_record_and_the_previous_record():
    data = page("next")
    block = data["scorecard_reading"]
    assert block["status"] == "computed" and block["model_record"]["tickets"] >= 1
    assert block["breadth_revisions"]["previous_session"] == page("full")["run"]["session"]
    body = (ROOT / "src" / "pipeline.py").read_text().split("def run_evening", 1)[1].split("\ndef ", 1)[0]
    assert body.index("report.build(") < body.index("read_scorecard(") < body.index("provenance.publish_bundle(")
    assert body.index("read_scorecard(") < body.index("report.send_digest(")


def test_a_model_record_that_raises_leaves_the_night_publishing_and_says_so(monkeypatch):
    from src import model_record

    def boom(*args, **kwargs):
        raise RuntimeError("no bars")

    monkeypatch.setattr(model_record, "build", boom)
    out = pipeline.read_scorecard({"picks": []}, {}, {}, page("full"), ROOT / "docs", None)
    assert out["status"] == "not_computed" and "RuntimeError" in out["sentences"][0]


# ------------------------------------------------- page, mail, orders.json --
def test_the_mail_and_orders_print_the_blocks_own_sentences():
    data = page("next")
    html = report.digest_html(data)
    assert "// the scorecard, read honestly" in html
    for s in data["scorecard_reading"]["sentences"]:
        assert report.esc(s) in html
    doc = orders.build((PAGE / "next.json").read_bytes())
    assert doc["scorecard"]["sentences"] == data["scorecard_reading"]["sentences"]
    assert doc["scorecard"]["plans"] == data["scorecard"].get("plans")
    assert doc["scorecard"]["distinct_setups"] == data["scorecard_reading"]["model_record"]["distinct_setups"]
    assert orders.problems(doc) == []


def test_the_page_prints_the_sentences_verbatim_and_names_an_absent_or_unreadable_block():
    js = (ROOT / "docs" / "app.js").read_text()
    body = js.split("function scorecardReading(data)", 1)[1].split("\n  function ", 1)[0]
    assert "block.sentences" in body and "text: s" in body
    assert "'absent'" in body and "'unreadable'" in body
    assert "card.appendChild(scorecardReading(data));" in js


# ----------------------------------------------------- real against model --
def test_real_r_is_the_models_convention_on_the_real_fills():
    from tools import positions_compare as pc
    position = {"planned": {"protective_stop": 98.0}, "fees_usd": 1.0,
                "fills": [{"at": "x", "shares": 2, "price": 100.0}, {"at": "y", "shares": 2, "price": 101.0}],
                "exits": [{"at": "z", "shares": 2, "price": 106.5, "reason": "sell_half_8pct"},
                          {"at": "w", "shares": 2, "price": 102.0, "reason": "day5_exit"}]}
    out = pc.real(position)
    # average fill 100.50; risk 4 x 2.50 = 10.00; result 2 x 6.00 + 2 x 1.50 = 15.00 -> +1.50R
    assert (out["state"], out["average_fill"], out["usd"], out["r"]) == ("closed", 100.5, 15.0, 1.5)
    assert out["fees_usd"] == 1.0
    assert pc.real({**position, "exits": position["exits"][:1]})["state"] == "open"
    assert pc.real({**position, "fills": [], "exits": []})["state"] == "not_filled"


def test_the_comparison_joins_by_ticket_and_never_adds_the_two(tmp_path):
    from tools import positions_compare as pc
    template = json.loads((ROOT / "tests" / "fixtures" / "orders" / "full" / "positions-template.json").read_text())
    position = template["positions"][0]
    position["fills"] = [{"at": "2026-09-11T09:31:00-04:00", "shares": 2, "price": position["planned"]["stop_price"]}]
    model = {"plans": [{"ticker": position["symbol"], "kind": "burst", "picked": position["ticket_id"].split(":")[0],
                        "bucket": "pending", "r": None, "status": "pending"}]}
    rows = pc.compare(template, model)
    assert rows[0]["model"]["bucket"] == "pending" and rows[0]["real"]["state"] == "open"
    assert pc.lines(rows)[0].endswith("; model pending.")
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({**template, "positions": [{**position, "status": "rumoured"}]}))
    assert pc.main(["--positions", str(bad), "--docs", str(ROOT / "docs")]) == 2


def test_the_comparison_writes_nothing_inside_the_repository(tmp_path):
    from tools import positions_compare as pc
    template = ROOT / "tests" / "fixtures" / "orders" / "full" / "positions-template.json"
    docs = tmp_path / "docs"
    docs.mkdir()
    for name in ("full.json", "full-picks.json"):
        (docs / ("data.json" if name == "full.json" else "picks.json")).write_bytes((PAGE / name).read_bytes())
    assert pc.main(["--positions", str(template), "--docs", str(docs), "--json", str(ROOT / "x.json")]) == 2
    assert not (ROOT / "x.json").exists()
    assert pc.main(["--positions", str(template), "--docs", str(docs), "--json", str(tmp_path / "out.json")]) == 0
    assert json.loads((tmp_path / "out.json").read_text())[0]["real"]["state"] == "not_filled"
