"""The brief and the model record together, as the tree ships them: after
``run_evening()`` through the doubles the brief carries the block
``src/model_record.py`` computed from that run's own bars, the block agrees
with the record's scorecard, and the pair still validates. The two modules
were built apart; this is the one place both are real. Every night here is
pinned to an instant."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from src import brief, model_record, record
from tests.test_brief_pipeline import pair
from tests.test_pipeline import claude, evening, market  # noqa: F401  (fixtures)


def test_the_evenings_brief_carries_the_model_record_the_run_computed(market, claude, fake_resend, tmp_path):
    rep, data, docs = evening(tmp_path, market)
    assert rep.exit_code() == 0 and rep.published
    data_raw, picks_raw, json_raw, md_raw = pair(docs)
    out = brief.validate(data_raw, picks_raw, json_raw, md_raw)
    block = out["model_record"]
    card = data["scorecard"]
    # computed, not the stub the pipeline writes when the module is missing or raises
    assert block["status"] == model_record.COMPUTED == "computed", block.get("reason")
    assert block["version"] == model_record.VERSION
    assert out["bounds"]["model_record_carried"] is True
    # held to the record's own scorecard: the same tickets, the same buckets, the same sum of R
    assert block["tickets"] == card["plans"] > 0
    assert block["buckets"] == {name: card[name] for name in record.SCORECARD_BUCKETS}
    assert block["sum_r"] == card["sum_r"]
    assert brief.model_record_faults(block, json.loads(data_raw)) == []
    # the night's own tickets are read off the record, sized against the account the record archived
    assert {row["ticker"] for row in block["plans"]} >= {t["ticker"] for t in out["tickets"]}
    assert {era["issued_equity"] for era in block["eras"]} == {data["account"]["equity"]}
    assert {row["account_basis"] for row in block["plans"]} == {model_record.RECORD}
    # and the Markdown says so in the model record's own section
    text = md_raw.decode("utf-8")
    number = brief.SECTIONS.index("Model record") + 1
    section = text.split(f"\n## {number}. Model record", 1)[1].split("\n## ", 1)[0]
    assert block["sentences"] and block["sentences"][0] in section


def test_the_second_night_carries_the_first_nights_accounts_forward(market, claude, fake_resend, tmp_path):
    """A ticket's model account is the record's own on the night it is issued and
    the previous brief's carried one after that: the chain the block documents,
    exercised over two real evenings rather than a synthetic previous brief."""
    first, data, docs = evening(tmp_path, market)
    assert first.published
    issued = {row["evidence_id"]: row["issued_equity"]
              for row in json.loads((docs / brief.JSON_FILE).read_bytes())["model_record"]["plans"]}
    assert issued and all(value == data["account"]["equity"] for value in issued.values())
    second, later, _ = evening(tmp_path, market, now=datetime(2026, 9, 11, 22, 30, tzinfo=timezone.utc))
    assert second.published and later["run"]["session"] != data["run"]["session"]
    out = brief.validate(*pair(docs))
    block = out["model_record"]
    assert block["status"] == "computed", block.get("reason")
    carried = [row for row in block["plans"] if row["evidence_id"] in issued]
    assert carried, "the first night's tickets are still inside the window"
    for row in carried:
        assert row["issued_equity"] == issued[row["evidence_id"]]
        assert row["account_basis"] == model_record.CARRIED
