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
    html = fake_resend.sent[0]["html"]
    assert 'src="cid:chart_AAA"' in html
    # And the row whose file is not there does NOT reference an attachment
    # nobody made. It used to, so a candidate whose chart failed to render
    # showed a broken-image icon in the one cell that should have said why.
    assert "cid:chart_BBB" not in html
    assert "no chart — none was rendered for this candidate" in html


def test_a_row_that_says_why_it_has_no_chart_says_that_instead(fake_resend):
    """The morning pass carries its own reason (src.pipeline's
    MORNING_CHART_NOTE) rather than the generic one."""
    rows = [make_result("AAA", chart=None, chart_note="no chart — this pass cannot date it")]

    send_email(rows, "morning", STATS)

    html = fake_resend.sent[0]["html"]
    assert fake_resend.sent[0]["attachments"] == []
    assert "no chart — this pass cannot date it" in html
    assert "cid:chart_AAA" not in html


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


# --- step 10: the session, and whether this name is a repeat ---------------
# The mode was a label over a session the wall clock picked, so "Evening
# candidates" could be yesterday's market and nothing in the inbox showed it.
# And every night's list arrived as if it were the first time: a name that
# burst on Monday and again on Tuesday looked like two new ideas.

DATED = dict(STATS, session="2026-08-31")


def _with_streak(**streak):
    base = {"day": 1, "unknown_reason": None, "first_seen": "2026-08-31",
            "last_seen": None, "last_score": None, "last_verdict": None,
            "last_outcome": None, "seen_before": 0}
    return [make_result("AAA", streak=dict(base, **streak))]


def test_the_subject_names_the_session_that_was_scanned(results):
    """The only half of the fix a phone shows."""
    assert subject_for(results, "evening", DATED).startswith(
        "[4% Burst] Evening candidates 2026-08-31: AAA")
    assert subject_for(results, "morning", DATED).startswith(
        "[4% Burst] Morning follow-through 2026-08-31: AAA")


def test_a_subject_with_no_session_to_name_does_not_invent_one(results):
    """The precondition: the date in the subject above comes from the caller,
    not from a clock this module reads for itself."""
    assert subject_for(results, "evening", STATS) == (
        "[4% Burst] Evening candidates: AAA, BBB, CCC, DDD")


def test_the_body_names_the_session_above_the_table(results):
    assert "Session scanned: 2026-08-31" in build_html(results, "evening", DATED)


def test_the_price_says_which_session_closed_at_it(results):
    """Under a heading reading "follow-through watchlist for TODAY", an
    unlabelled $44.8 is read as this morning's price. It is last night's close.
    The session was in the subject and the funnel line and not on the number
    the eye lands on."""
    assert "$44.8 (close 2026-08-31)" in build_html(results, "morning", DATED)
    assert "$44.8 (close 2026-08-31)" in build_html(results, "evening", DATED)


def test_a_price_with_no_session_to_name_is_not_given_a_made_up_one(results):
    """The precondition: the date comes from the caller, not from a clock this
    module reads for itself."""
    html = build_html(results, "evening", STATS)
    assert "$44.8<" in html and "close 20" not in html


def test_a_morning_body_reports_the_run_it_is_following_not_a_scan(results):
    """It scanned no universe at all, so printing one would describe a funnel
    it never walked."""
    html = build_html(results, "morning", DATED)

    assert "Following through on the session of: 2026-08-31" in html
    assert "Universe" not in html and "Shortlisted" not in html
    assert "Watching: 4" in html


def test_a_repeat_says_which_day_of_the_setup_it_is():
    """THE thing step 10 added to this email."""
    html = build_html(_with_streak(day=3, first_seen="2026-08-27",
                                   last_seen="2026-08-28", last_score=7.5,
                                   last_verdict="B", seen_before=2),
                      "evening", DATED)

    assert "day 3 of this setup, since 2026-08-27" in html
    assert "last seen 2026-08-28, scored 7.5/10 B" in html


def test_a_first_sighting_says_that_rather_than_saying_nothing():
    """Absence is not a readable signal: a row with no marker would be
    indistinguishable from a run that could not read its history."""
    assert "day 1 — new setup" in build_html(_with_streak(), "evening", DATED)


def test_a_name_seen_before_but_not_recently_is_day_one_with_a_note():
    """A ticker reappearing after a full base is day 1 of something new, and
    when it was last seen is still worth knowing."""
    html = build_html(_with_streak(last_seen="2026-08-14", last_score=5.2,
                                   last_verdict="skip", seen_before=1),
                      "evening", DATED)

    assert "day 1 — new setup · last seen 2026-08-14, scored 5.2/10 skip" in html


def test_a_repeat_the_gate_rejected_last_time_says_it_was_rejected():
    """"not scored" covered this and the model-outage case with one phrase,
    and they are opposite facts: here the pipeline looked at the name and threw
    it out at the quality gate. Beside "day 2 of this setup", which reads as a
    second night of agreement, that is worth money."""
    html = build_html(_with_streak(day=2, first_seen="2026-08-28",
                                   last_seen="2026-08-28", last_outcome="lynch_gate",
                                   seen_before=1),
                      "evening", DATED)

    assert "last seen 2026-08-28, rejected at the 2LYNCH gate" in html
    assert "not scored" not in html


def test_a_repeat_that_ran_out_of_calls_says_that_instead():
    """The other half of the pair: it passed the checklist and better names
    filled the night's call budget. Nothing rejected it."""
    html = build_html(_with_streak(day=2, first_seen="2026-08-28",
                                   last_seen="2026-08-28", last_outcome="score_cap",
                                   seen_before=1),
                      "evening", DATED)

    assert "last seen 2026-08-28, passed the gate, but the scoring cap was already full" in html
    assert "last seen 2026-08-28, rejected" not in html


def test_a_row_from_before_last_outcome_existed_claims_neither():
    """A snapshot published by an older pipeline carries last_score and no
    last_outcome. Guessing a reason for it would be inventing one."""
    html = build_html(_with_streak(day=2, first_seen="2026-08-28",
                                   last_seen="2026-08-28", seen_before=1),
                      "evening", DATED)

    assert "last seen 2026-08-28, no score was recorded then" in html
    assert "last seen 2026-08-28, rejected" not in html
    assert "last seen 2026-08-28, passed the gate" not in html


def test_last_outcome_outranks_a_score_that_contradicts_it():
    """The docstring says last_outcome is the authority, so a row carrying both
    has to prove it. src.ledger never writes a gated appearance with a score --
    but this row comes off disk, and the reading rule must not depend on the
    writer being the version that wrote this file."""
    html = build_html(_with_streak(day=2, first_seen="2026-08-28",
                                   last_seen="2026-08-28", last_score=7.5,
                                   last_verdict="B", last_outcome="lynch_gate",
                                   seen_before=1),
                      "evening", DATED)

    assert "last seen 2026-08-28, rejected at the 2LYNCH gate" in html
    assert "7.5/10" not in html


@pytest.mark.parametrize("reason,said", [
    ("history_unreadable", "streak unknown — the run could not read its history"),
    ("no_history", "streak unknown — no history has been recorded yet"),
    ("window_not_covered", "streak unknown — the history does not reach back this far"),
    ("something_new", "streak unknown — no reason was recorded"),
])
def test_an_unknown_streak_says_which_kind_of_unknown_it_is(reason, said):
    """`day: null` is the state this whole mechanism cares most about — unknown,
    which is NOT day 1 — and this surface used to render it as nothing at all,
    while the dashboard's pick card printed a sentence and its two tables
    printed nothing. Three surfaces, three answers, for the one state where a
    reader filling in the blank himself gets it wrong."""
    html = build_html(_with_streak(day=None, unknown_reason=reason, first_seen=None),
                      "evening", DATED)

    assert said in html
    assert "day 1" not in html and "new setup" not in html


def test_an_unknown_streak_still_reports_what_the_record_did_hold():
    """`day` is a claim about what came before; `last_seen` is a fact off the
    file. Losing the second with the first would throw away what was known."""
    html = build_html(_with_streak(day=None, unknown_reason="window_not_covered",
                                   first_seen=None, last_seen="2026-08-14",
                                   last_score=5.2, last_verdict="skip",
                                   last_outcome="scored", seen_before=1),
                      "evening", DATED)

    assert "streak unknown — the history does not reach back this far · " \
           "last seen 2026-08-14, scored 5.2/10 skip" in html


def test_a_streak_that_is_not_a_block_does_not_take_the_email_down(fake_resend):
    """A morning row comes off disk. A truncated or hand-edited snapshot must
    cost a streak, not the 8:30 email -- the email is the monitor, and one that
    does not arrive is the failure step 5 exists to end."""
    send_email([make_result("AAA", streak="day 2 probably")], "morning", DATED)

    assert "streak unknown — no reason was recorded" in fake_resend.sent[0]["html"]


def test_a_row_carrying_no_streak_field_at_all_is_unknown_too(results):
    """A row from before the field existed is not a first sighting either.
    Absence and "day 1 — new setup" must never render the same."""
    html = build_html(results, "evening", DATED)

    assert html.count("streak unknown — no reason was recorded") == len(results)
    assert "new setup" not in html


def test_what_day_n_counts_is_disclosed_once_under_the_table():
    """A streak counts every session the scan found a burst on, gate rejections
    included — the right call, and one no reader can infer from "day 2 of this
    setup"."""
    counted = build_html(_with_streak(day=2, first_seen="2026-08-28"), "evening", DATED)
    single = build_html(_with_streak(), "evening", DATED)

    assert "including bursts the 2LYNCH gate rejected" in counted
    assert "including bursts the 2LYNCH gate rejected" not in single, (
        "and it is not printed under a table with no streak to explain")


def test_a_morning_run_with_nothing_to_show_does_not_blame_the_market():
    """Three empty tables now, and only one of them is a statement about
    stocks: a morning pass has nothing of its own to find."""
    assert "The run this follows through on scored no candidates." in build_html(
        [], "morning", DATED)
    assert "No candidates passed the quality gate" in build_html([], "evening", DATED)
