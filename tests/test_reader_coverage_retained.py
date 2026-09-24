"""Retained Sep 23 states; regime changes below are synthetic, never a rescan."""
from collections import Counter
from datetime import date
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from src import pipeline, plan

FIXTURE = Path(__file__).parent / "fixtures/grading/reader-coverage"
UNREVIEWED = {"NDSN", "OPY", "RRR", "STE", "TTE", "WLY"}
DOWNGRADES = {**dict.fromkeys(["MET", "DOCU", "MEOH", "RDVT", "IEX"], "C"),
              **dict.fromkeys(["CHDN", "CMI", "DCO", "IR", "LTH", "MSM"], "skip")}


def retained():
    return json.loads(gzip.decompress((FIXTURE / "2026-09-23.json.gz").read_bytes()))


def replay(verdict):
    data = retained()
    regime = {**data["breadth"]["regime"], "verdict": verdict,
              "size_multiplier": {"red": 0, "yellow": 0.5, "green": 1}[verdict]}
    account = plan.Account(**{k: data["account"][k] for k in plan.Account.__dataclass_fields__})
    result = pipeline.make_plans(data["bursts"], {}, account, regime, 0, date(2026, 9, 23))
    return data, result


def test_retained_incident_identity_and_reader_distribution():
    raw = gzip.decompress((FIXTURE / "2026-09-23.json.gz").read_bytes())
    meta = json.loads((FIXTURE / "source.json").read_text())
    assert hashlib.sha256(raw).hexdigest() == meta["sha256"]
    data = json.loads(raw)
    assert data["run"]["run_id"] == "35938584554"
    assert data["run"]["session"] == "2026-09-23"
    assert Counter(b["grade_mechanical"] for b in data["bursts"]) == {"A": 18, "B": 77, "C": 35, "skip": 152}
    selected = sorted(data["bursts"], key=lambda b: (pipeline.GRADE_ORDER[b["grade_mechanical"]], -b["score"], b["ticker"]))[:12]
    assert pipeline.MAX_READS == data["rules"]["pipeline"]["max_reads"] == 12
    assert {b["ticker"] for b in selected} == set(DOWNGRADES) | {"VEEV"}
    assert {b["ticker"]: b["grade"] for b in selected if b["claude"]["source"] == "claude"} == DOWNGRADES
    assert {b["ticker"] for b in data["bursts"] if b["grade_mechanical"] == "A" and b["claude"] is None} == UNREVIEWED
    veev = next(b for b in selected if b["ticker"] == "VEEV")
    assert veev["grade"] == veev["grade_mechanical"] == "A"
    assert veev["claude"]["source"] == "fallback"
    assert veev["claude"]["error"] == "src.ReaderAuthorityError: evidence outside criterion authority"
    response = veev["claude"]["attempts"][0]["response"]
    assert response["retention"] == "complete"
    assert hashlib.sha256(response["text"].encode()).hexdigest() == response["text_sha256"]


def test_retained_green_budget_candidates_cannot_reach_plan_eligibility():
    data, (trades, _, _) = replay("green")
    rows = [b for b in data["bursts"] if b["ticker"] in UNREVIEWED]
    assert len(rows) == 6 and all(b["grade"] == "A" for b in rows)
    leaked = [b["ticker"] for b in rows if b["plan"] and b["plan"]["eligible"]]
    assert leaked == [], f"unreviewed mechanical A became plan eligible: {leaked}"
    assert not UNREVIEWED.intersection(trades)
    assert all(b["plan"] is None for b in rows)
    # The coverage gate, not an incidental sizing failure, refuses these names.
    for row in rows:
        control = plan.burst_plan(ticker=row["ticker"], close=row["close"], low=row["low"], high=row["high"],
            open_=row["open"], prev_close=row["prev_close"], gain_pct=row["gain_pct"],
            account=plan.Account(), scan="dollar", extension_pct=row["extension_pct"])
        assert control["eligible"] and control["order_json"]


def test_retained_green_fallback_is_research_only():
    data, (trades, _, _) = replay("green")
    veev = next(b for b in data["bursts"] if b["ticker"] == "VEEV")
    assert veev["grade"] == "A" and veev["claude"]["source"] == "fallback"
    assert veev["plan"] is None and "VEEV" not in trades


@pytest.mark.parametrize("verdict", ["red", "green", "yellow"])
def test_retained_downgrades_stay_ineligible_and_evidence_stays_unchanged(verdict):
    before = retained()
    data, (trades, _, _) = replay(verdict)
    for original, row in zip(before["bursts"], data["bursts"]):
        for key in ("quality", "grade_mechanical", "score", "grade", "claude", "series", "evidence"):
            assert row.get(key) == original.get(key), (row["ticker"], key)
        if row["ticker"] in DOWNGRADES:
            assert row["plan"] is None and row["ticker"] not in trades
    if verdict == "red":
        assert before["breadth"]["ratio_10d"] == 0.85
        assert before["breadth"]["regime"]["verdict"] == "red"
        assert trades == before["trades"] == []
        assert [b["plan"] for b in data["bursts"]] == [b["plan"] for b in before["bursts"]]
