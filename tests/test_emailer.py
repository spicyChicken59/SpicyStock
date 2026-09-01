"""Layer 6 -- the rendered email and the Resend boundary.

The suite must never send mail, so resend.Emails.send is replaced with a
double that captures its payload, and the delivery env vars are set inside
the test rather than read from the machine.
"""

from __future__ import annotations

import base64

import pytest

from src.emailer import build_html, send_email
from src.scorer import render_chart

STATS = {"universe": "230 checked-in US common stocks", "bursts": 42, "gated": 12}


def make_result(ticker: str, **overrides) -> dict:
    row = {
        "ticker": ticker,
        "date": "2026-07-01",
        "close": 44.8,
        "gain_pct": 12.0,
        "volume_ratio": 8.3,
        "lynch": "5/6",
        "lynch_detail": [f"PASS  {ticker}_check_{i}: measured" for i in range(3)],
        "score": 8.4,
        "verdict": "A",
        "reason": f"{ticker} broke out of a tight base.",
        "key_risk": f"{ticker} market breadth",
        "chart": None,
    }
    row.update(overrides)
    return row


@pytest.fixture
def results() -> list[dict]:
    return [make_result(t) for t in ("AAA", "BBB", "CCC", "DDD")]


def test_html_contains_every_candidate_it_was_given(results):
    html = build_html(results, "evening", STATS)
    for row in results:
        assert row["ticker"] in html
        assert row["reason"] in html
        assert row["key_risk"] in html
        assert str(row["score"]) in html
        assert row["lynch"] in html
        for line in row["lynch_detail"]:
            assert line in html


def test_html_reports_the_scan_stats_and_the_run_type(results):
    evening = build_html(results, "evening", STATS)
    morning = build_html(results, "morning", STATS)
    assert "TOMORROW" in evening and "TODAY" in morning
    assert str(STATS["bursts"]) in evening
    assert str(STATS["gated"]) in evening


def test_html_survives_an_empty_shortlist():
    html = build_html([], "evening", STATS)
    assert "No candidates" in html
    assert "<table" in html


def test_send_email_goes_through_the_mocked_transport(results, fake_resend):
    import resend

    send_email(results, "evening", STATS)

    assert len(fake_resend.sent) == 1
    params = fake_resend.sent[0]
    assert params["to"] == ["one@example.invalid", "two@example.invalid"]
    assert params["from"] == "tests@example.invalid"
    assert resend.api_key == "test-not-a-real-key"
    for row in results:
        assert row["ticker"] in params["subject"]
        assert row["ticker"] in params["html"]


def test_send_email_with_no_candidates_still_sends(fake_resend):
    send_email([], "morning", STATS)
    assert len(fake_resend.sent) == 1
    assert "none" in fake_resend.sent[0]["subject"]


def test_charts_are_attached_inline_and_missing_ones_are_skipped(ohlcv, fake_resend):
    chart = render_chart("AAA", ohlcv("burst"))
    rows = [make_result("AAA", chart=chart), make_result("BBB", chart="charts/missing.png")]

    send_email(rows, "evening", STATS)

    attachments = fake_resend.sent[0]["attachments"]
    assert [a["filename"] for a in attachments] == ["AAA.png"]
    assert attachments[0]["content_id"] == "chart_AAA"
    assert base64.b64decode(attachments[0]["content"]).startswith(b"\x89PNG")
    # The HTML references the attachment by content id, for both rows.
    assert 'src="cid:chart_AAA"' in fake_resend.sent[0]["html"]
