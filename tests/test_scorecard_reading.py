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
import re
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


def published_of(record: dict) -> dict:
    return record["scorecard_reading"]["breadth_revisions"]["published"]


def row_of(record: dict, session: str) -> dict:
    return next(h for h in record["breadth"]["history"] if h["date"] == session)


def test_each_session_is_held_to_its_own_first_publication_not_to_a_later_re_reading():
    before, after = page("full"), page("next")
    session = before["run"]["session"]
    # the previous record's own session as it printed it (its history's own last row)
    assert before["breadth"]["history"][-1]["date"] == session
    out = sr.breadth_revisions(before, after)
    assert session in out["published"] and out["compared"] >= 1
    assert out["published"][session] == {f: row_of(before, session)[f] for f in sr.REVISION_FIELDS}
    # an older session the previous record re-read differently from its first publication: the
    # carried first-published figures are what tonight is held to, not the previous re-reading
    older = sorted(d for d in published_of(before) if d != session)
    if not older:
        older = [before["breadth"]["history"][-2]["date"]]
    first = copy.deepcopy(before)
    first["scorecard_reading"]["breadth_revisions"]["published"][older[0]] = {
        **{f: row_of(after, older[0])[f] for f in sr.REVISION_FIELDS}, "up4": row_of(after, older[0])["up4"] - 5}
    held = sr.breadth_revisions(first, after)
    hit = next(r for r in held["differ"] if r["session"] == older[0])
    assert hit["published"]["up4"] == row_of(after, older[0])["up4"] - 5 and hit["revised"]["up4"] == row_of(after, older[0])["up4"]
    assert f"{older[0]} up4 {row_of(after, older[0])['up4'] - 5} to {row_of(after, older[0])['up4']}" in held["sentence"]


def test_revisions_are_named_newest_first_and_the_previous_session_is_never_folded_away():
    before, after = page("full"), copy.deepcopy(page("next"))
    session = before["run"]["session"]
    seeded = copy.deepcopy(before)
    seeded["scorecard_reading"]["breadth_revisions"]["published"] = {
        h["date"]: {f: h[f] for f in sr.REVISION_FIELDS} for h in after["breadth"]["history"]}
    for h in after["breadth"]["history"]:
        h["down4"] += 1
    out = sr.breadth_revisions(seeded, after)
    assert out["differ_count"] > sr.MAX_REVISIONS and len(out["differ"]) == sr.MAX_REVISIONS
    sessions = [r["session"] for r in out["differ"]]
    assert sessions == sorted(sessions, reverse=True)
    assert sessions[0] == max(published_of(seeded)) and session in sessions     # the previous session is named
    assert f"; and {out['differ_count'] - sr.MAX_REVISIONS} more." in out["sentence"]
    assert len(re.findall(r"\d{4}-\d{2}-\d{2} (?:up4|down4|ratio_10d) ", out["sentence"])) == sr.MAX_REVISIONS


def test_a_same_session_revision_names_tonights_own_session_and_the_rest_are_counted():
    first, revised = page("next"), page("revised")
    assert first["run"]["session"] == revised["run"]["session"]
    session = first["run"]["session"]
    out = sr.breadth_revisions(first, revised)
    assert session in out["published"]
    assert out["not_retained"] == sum(1 for h in revised["breadth"]["history"]
                                      if h["date"] not in published_of(first) and h["date"] != session)
    changed = copy.deepcopy(revised)
    row_of(changed, session)["up4"] += 2
    hit = sr.breadth_revisions(first, changed)
    assert any(r["session"] == session for r in hit["differ"])


def test_the_first_published_figures_are_carried_forward_and_bounded_to_tonights_history():
    before, after = page("full"), page("next")
    out = sr.breadth_revisions(before, after)
    tonight = after["run"]["session"]
    assert out["published"][tonight] == {f: row_of(after, tonight)[f] for f in sr.REVISION_FIELDS}
    assert set(out["published"]) <= {h["date"] for h in after["breadth"]["history"]}
    stale = copy.deepcopy(before)
    stale["scorecard_reading"]["breadth_revisions"]["published"]["1999-01-04"] = {"up4": 1, "down4": 1, "ratio_10d": 1.0}
    assert "1999-01-04" not in sr.breadth_revisions(stale, after)["published"]
    assert sr.breadth_revisions(None, after)["sentence"] == "There is no earlier publication's breadth to compare."
    # the block the evening wrote is what the rule writes over the two records
    assert after["scorecard_reading"]["breadth_revisions"] == sr.breadth_revisions(before, after)


# ----------------------------------------------------------- the validator --
def record_of(name: str) -> dict:
    """A page fixture as the run wrote it, without the label a fixture carries."""
    data = page(name)
    data.pop("fixture", None)
    return data


def test_the_validator_asks_for_the_block_only_under_rules_that_write_it_and_holds_its_shape():
    data = record_of("next")
    assert data["rules"]["pipeline"]["scorecard_reading_version"] == sr.VERSION
    assert sr.faults(data) == []
    report.validate(data)                       # the record as written passes
    older = copy.deepcopy(data)
    del older["rules"]["pipeline"]["scorecard_reading_version"]
    del older["scorecard_reading"]
    assert sr.faults(older) == []
    for change, words in ((lambda d: d.pop("scorecard_reading"), "missing"),
                          (lambda d: d["scorecard_reading"].update(sentences=[1]), "sentences"),
                          (lambda d: d["scorecard_reading"].update(status="fine"), "status"),
                          (lambda d: d["scorecard_reading"]["real_vs_model"].update(sentence="x"), "real_vs_model"),
                          (lambda d: d["scorecard_reading"].update(breadth_revisions=None), "breadth_revisions"),
                          (lambda d: d["scorecard_reading"]["sentences"].__setitem__(0, "999 tickets are 1 setup."),
                           "not its own figures"),
                          (lambda d: d["scorecard_reading"]["breadth_revisions"].update(differ_count=12),
                           "does not count its own sessions"),
                          (lambda d: d["scorecard_reading"]["breadth_revisions"].update(
                              sentence=d["scorecard_reading"]["breadth_revisions"]["sentence"] + " Also."),
                           "not its own figures"),
                          (lambda d: d["scorecard_reading"]["model_record"].update(
                              distinct_setups=d["scorecard_reading"]["model_record"]["tickets"] + 1),
                           "does not count its tickets")):
        forged = copy.deepcopy(data)
        change(forged)
        assert any(words in f for f in sr.faults(forged)), (words, sr.faults(forged))
        with pytest.raises(ValueError, match="scorecard_reading"):
            report.validate(forged)
    stray = copy.deepcopy(older)
    stray["scorecard_reading"] = data["scorecard_reading"]
    assert sr.faults(stray) == ["scorecard_reading present under rules that do not write it"]


def test_the_scorecards_own_numbers_do_not_move(monkeypatch):
    # composing the block reads the record and writes nothing into it: the scorecard the run
    # wrote before it is the scorecard after it, number for number
    from src import model_record
    data = record_of("next")
    before = json.dumps(data, sort_keys=True)
    monkeypatch.setattr(model_record, "build", lambda *a, **k: copy.deepcopy(BLOCK))
    block = pipeline.read_scorecard({}, {}, {}, data, ROOT / "docs", page("full"))
    assert json.dumps(data, sort_keys=True) == before
    assert block["model_record"]["tickets"] == BLOCK["tickets"] and "scorecard_reading" not in json.dumps(data["scorecard"])
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


def test_a_position_whose_exits_outnumber_its_fills_is_inconsistent_not_open():
    from tools import positions_compare as pc
    planned = {"protective_stop": 98.0}
    over = pc.real({"planned": planned, "fills": [{"shares": 2, "price": 100.0}],
                    "exits": [{"shares": 3, "price": 101.0}]})
    assert (over["state"], over["r"], over["detail"]) == ("inconsistent", None, "3 shares exited of 2 filled")
    ghost = pc.real({"planned": planned, "fills": [], "exits": [{"shares": 1, "price": 101.0}]})
    assert (ghost["state"], ghost["detail"]) == ("inconsistent", "1 shares exited with no fill")
    row = {"ticket_id": "2026-11-04:burst:HQY", "status": "closed", "real": over, "model": None, "refused": None}
    assert pc.lines([row]) == ["2026-11-04:burst:HQY: real inconsistent: 3 shares exited of 2 filled, so no R; "
                               "model ticket not in the published window."]


def test_a_position_is_joined_to_the_model_only_on_its_ticket_id_and_its_planned_stop():
    from tools import positions_compare as pc
    template = json.loads((ROOT / "tests" / "fixtures" / "orders" / "full" / "positions-template.json").read_text())
    position = template["positions"][0]
    session = position["ticket_id"].split(":")[0]
    model = {"status": "computed", "plans": [{"ticker": position["symbol"], "kind": "burst", "picked": session,
                                              "bucket": "pending", "r": None, "status": "pending",
                                              "stop": position["planned"]["protective_stop"]}]}
    assert pc.compare(template, model)[0]["model"]["bucket"] == "pending"
    moved = copy.deepcopy(model)
    moved["plans"][0]["stop"] = position["planned"]["protective_stop"] - 1.0
    row = pc.compare(template, moved)[0]
    assert row["model"] is None and "is not the model's" in row["refused"]
    assert "not compared: its planned stop" in pc.lines([row])[0]
    odd = copy.deepcopy(template)
    odd["positions"][0]["ticket_id"] = "AAPL"
    row = pc.compare(odd, model)[0]                       # named, never a ValueError
    assert row["refused"] == "its ticket id is not session:kind:symbol" and row["model"] is None
    assert pc.lines([row], "unreconciled")[0] == \
        "The model record is unreconciled: its rows below are not reconciled."


@pytest.mark.parametrize("change", [{"tickets": None}, {"distinct_setups": "4"}, {"tickets": True},
                                    {"distinct_setups": 9}, {"tickets": 2.0}])
def test_a_computed_model_block_whose_counts_cannot_be_read_is_unreconciled_and_never_refused(change):
    block = sr.build({**BLOCK, **change}, page("full"), record_of("next"))
    assert block["status"] == "unreconciled" and block["model_record"]["sentences"] == []
    data = record_of("next")
    data["scorecard_reading"] = block
    assert sr.faults(data) == []                 # the night it lands in validates


def test_a_previous_record_from_before_the_rule_seeds_its_own_session_and_the_first_publication_wins():
    before, after = page("full"), page("next")
    session = before["run"]["session"]
    bare = copy.deepcopy(before)
    bare.pop("scorecard_reading")                     # a record from before the reading: no map to carry
    assert sr.breadth_revisions(bare, after)["published"][session] == \
        {f: row_of(before, session)[f] for f in sr.REVISION_FIELDS}
    # the session was published once before, with other figures: that first publication stands
    first = copy.deepcopy(before)
    first["scorecard_reading"]["breadth_revisions"]["published"][session] = {
        **{f: row_of(before, session)[f] for f in sr.REVISION_FIELDS}, "down4": row_of(before, session)["down4"] + 7}
    out = sr.breadth_revisions(first, after)
    assert out["published"][session]["down4"] == row_of(before, session)["down4"] + 7


def test_the_validator_counts_the_sessions_whatever_the_sentences_say():
    data = record_of("next")
    forged = copy.deepcopy(data)
    rev = forged["scorecard_reading"]["breadth_revisions"]
    row = {"session": "2026-09-01", "published": {"up4": 1, "down4": 1, "ratio_10d": 1.0},
           "revised": {"up4": 2, "down4": 1, "ratio_10d": 1.0}}
    # two revised of one compared, the named list as long as the count: only the count rule can see it
    rev.update(compared=1, differ_count=2, differ=[row, {**row, "session": "2026-09-02"}])
    rev["sentence"] = sr.revision_sentence(rev)
    forged["scorecard_reading"]["sentences"] = sr.sentences_of(forged["scorecard_reading"]["model_record"], rev)
    assert sr.faults(forged) == ["scorecard_reading breadth_revisions does not count its own sessions"]


@pytest.mark.parametrize("count, unexamined, words", [
    (2, 1, "3 settled tickets ended on a stop; 1 of them ended on a stop whose bars this record does not carry"),
    (0, 3, "3 settled tickets ended on a stop; 3 of them ended on a stop whose bars this record does not carry"),
    (1, 0, "The 1 stopped ticket booked at the stop sums to"),
])
def test_the_stop_sentence_names_the_tickets_whose_bars_are_gone_and_withholds_the_sum(count, unexamined, words):
    sums = {n: (None if unexamined else -1.0) for n in sr.STOP_NAMES}
    sentence = sr.stop_sentence({"status": "computed", "stops": {"count": count, "unexamined": unexamined, "sum_r": sums}})
    assert words in sentence and ("not given" not in sentence)
    partial = sr.stop_sentence({"status": "computed", "stops": {"count": 2, "unexamined": 0,
                                                                "sum_r": {"booked": -2.0, "at_close": None, "at_low": None}}})
    assert partial == ("2 settled tickets ended on a stop; not every one could be read at the session's close and "
                       "low, so no sum of the three readings is given.")
