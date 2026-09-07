"""The scorer sees only prior appearances, with the ledger's episode meaning."""

import json
from types import SimpleNamespace

import pytest

from src import ledger, scorer


SESSION = "2026-09-01"
RECORD_FIELDS = (
    "setup_day", "setup_unknown_reason", "seen_before", "last_seen",
    "last_score", "last_outcome",
)


def _run(session, *, ticker=None, score=7.0):
    rows = [] if ticker is None else [{
        "ticker": ticker, "date": session, "score": score, "verdict": "B",
    }]
    return {"date": session, "type": "evening", "candidates": rows, "gated": []}


def _request_record(runs, fake_anthropic):
    """Read the real request after score_all passes the ledger block onward."""
    candidate = SimpleNamespace(
        ticker="AAA", date=SESSION, close=100.0, gain_pct=4.5,
        volume=100_000, prev_volume=50_000, volume_ratio=2.0,
        dollar_volume=10_000_000,
    )
    checklist = {
        "passes": 5, "total": 6, "summary": "5/6", "detail_lines": [],
    }
    rows = scorer.score_all(
        [(candidate, checklist, {}, None)],
        streaks=ledger.streaks(runs, ["AAA"], SESSION),
    )
    assert rows[0]["provenance"]["source"] == "claude"
    blocks = fake_anthropic.calls[-1]["messages"][0]["content"]
    text = "".join(block["text"] for block in blocks if block["type"] == "text")
    metrics, _ = json.JSONDecoder().raw_decode(text.split("METRICS:\n", 1)[1])
    return {name: metrics[name] for name in RECORD_FIELDS}


@pytest.mark.parametrize("extra_session", [SESSION, "2026-09-02"],
                         ids=["same-session-rerun", "future-session-backfill"])
def test_current_and_future_appearances_cannot_change_the_scoring_request(
    fake_anthropic, extra_session,
):
    """A rerun cannot count itself; a backfill cannot borrow a later judgement."""
    prior = [_run("2026-08-03"), _run("2026-08-31", ticker="AAA", score=6.0)]
    baseline = _request_record(prior, fake_anthropic)
    assert baseline == {
        "setup_day": 2, "setup_unknown_reason": None, "seen_before": 1,
        "last_seen": "2026-08-31", "last_score": 6, "last_outcome": "scored",
    }

    with_later_row = _request_record(
        prior + [_run(extra_session, ticker="AAA", score=9.9)], fake_anthropic,
    )
    assert with_later_row == baseline


def test_a_new_episode_keeps_older_appearances_in_the_scoring_request(fake_anthropic):
    """Day 1 resets after the episode gap; it cannot mean never seen before."""
    payload = _request_record(
        [_run("2026-08-03"), _run("2026-08-17", ticker="AAA", score=7.0)],
        fake_anthropic,
    )

    assert payload == {
        "setup_day": 1, "setup_unknown_reason": None, "seen_before": 1,
        "last_seen": "2026-08-17", "last_score": 7, "last_outcome": "scored",
    }
