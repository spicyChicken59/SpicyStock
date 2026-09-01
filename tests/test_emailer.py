"""Layer 6 -- the rendered email and the Resend boundary.

The suite must never send mail, so resend.Emails.send is replaced with a
double that captures its payload, and the delivery env vars are set inside
the test rather than read from the machine.
"""

from __future__ import annotations

import base64

import pytest

from src.emailer import build_html, send_email, send_failure_notice, subject_for
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


# --- a degraded run must not look like a clean one -------------------------
# The email is the only monitor anyone actually reads. Everything below is
# about the difference a reader sees between a run that did its job and one
# that could not -- in the subject line, which is all a phone shows, and above
# the table, which is the first thing a body shows.

DEGRADED = dict(
    STATS,
    status="degraded",
    errors=[{"stage": "scan", "message": "138 of 230 symbols had no bar for 2026-09-01"},
            {"stage": "score", "message": "4 of 12 candidates were not scored by Claude"}],
    scored_by={"claude": 8, "fallback": 4},
)


def test_a_clean_run_carries_no_banner_and_no_marker(results):
    """The precondition for every test below: without errors nothing changes,
    so a banner in one of them cannot be the template's default state."""
    html = build_html(results, "evening", STATS)
    assert "DEGRADED" not in html and "FAILED" not in html
    assert subject_for(results, "evening", STATS) == "[4% Burst] Evening candidates: AAA, BBB, CCC, DDD"


def test_a_degraded_run_says_so_above_the_table_and_names_every_reason(results):
    html = build_html(results, "evening", DEGRADED)
    assert "THIS RUN WAS DEGRADED" in html
    for problem in DEGRADED["errors"]:
        assert problem["message"] in html, "the reason, not just the word"
        assert problem["stage"] in html
    assert html.index("THIS RUN WAS DEGRADED") < html.index(results[0]["ticker"]), (
        "the warning has to come before the list it is about"
    )


def test_a_degraded_run_says_so_in_the_subject_line(results):
    subject = subject_for(results, "evening", DEGRADED)
    assert subject.startswith("[4% Burst] DEGRADED — "), subject
    assert "AAA" in subject, "still says what it found"


def test_a_failed_run_says_that_instead(results):
    assert subject_for([], "evening", dict(DEGRADED, status="failed")).startswith(
        "[4% Burst] FAILED — ")
    assert "THIS RUN FAILED" in build_html([], "evening", dict(DEGRADED, status="failed"))


def test_an_empty_shortlist_does_not_claim_a_quiet_market_when_the_run_broke():
    """Both are empty tables. Only one of them is a statement about stocks."""
    clean = build_html([], "evening", STATS)
    broken = build_html([], "evening", DEGRADED)
    assert "No candidates passed the quality gate" in clean
    assert "No candidates passed the quality gate" not in broken
    assert "not a statement about the market" in broken


def test_the_body_counts_how_many_scores_are_not_ai_scores(results):
    assert "Scored by Claude: 8 of 12" in build_html(results, "evening", DEGRADED)
    assert "Scored by Claude" not in build_html(results, "evening", STATS), (
        "nothing is claimed when the caller did not say"
    )


def test_the_failure_notice_is_the_same_email_with_the_reason_and_no_rows(fake_resend):
    send_failure_notice("evening", [{"stage": "scan", "message": "StaleDataError: no bar"}])

    (params,) = fake_resend.sent
    assert params["subject"].startswith("[4% Burst] FAILED — ")
    assert "StaleDataError: no bar" in params["html"]
    assert "<table" in params["html"], "the same artifact, so the daily habit still reads it"


# --- delivery credentials --------------------------------------------------


@pytest.mark.parametrize("var", ["RESEND_API_KEY", "EMAIL_TO"])
def test_an_empty_delivery_variable_is_missing_not_present(monkeypatch, fake_resend, var):
    """GitHub Actions passes an unset secret as '', which os.environ[...] --
    what this used to do -- accepts happily and fails later as somebody
    else's 401."""
    monkeypatch.setenv(var, "")
    with pytest.raises(KeyError, match=var):
        send_email([], "evening", STATS)
    assert fake_resend.sent == [], "nothing may be sent on the way to failing"
