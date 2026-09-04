"""Layer 6 -- the rendered email and the Resend boundary.

The suite must never send mail, so resend.Emails.send is replaced with a
double that captures its payload, and the delivery env vars are set inside
the test rather than read from the machine.
"""

from __future__ import annotations

import base64

import pytest

from src import pipeline
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


def results_for(_run_type: str) -> list[dict]:
    """Rows for a test that is not using the `results` fixture."""
    return [make_result(t) for t in ("AAA", "BBB")]


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
    assert "candidates for TOMORROW" in evening
    assert "follow-through" in morning and "TOMORROW" not in morning
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
    # ... and says which of the two silences this is. The row NAMES a file, so
    # something rendered one; "none was rendered for this candidate" asserted a
    # cause nothing had checked, and pointed the reader at the wrong repair.
    assert "charts/missing.png is not there now" in html
    assert "none was rendered for this candidate" not in html


def test_a_row_that_never_had_a_chart_says_that_and_not_the_other_one(fake_resend):
    """The inverse of the row above, and the reason the two are separate
    sentences: `chart` is null when render_chart() raised (src.pipeline records
    the exception itself), and that IS "none was rendered". The message only
    means something if the other case does not also produce it."""
    send_email([make_result("AAA", chart=None)], "evening", STATS)

    html = fake_resend.sent[0]["html"]
    assert "no chart — none was rendered for this candidate" in html
    assert "is not there now" not in html


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


# --- the band and the heading branch on the MODE, like everything else -----
# _banner() keyed on `failed` alone and had no morning branch, unlike
# _funnel_line(), the empty-shortlist cell and the whole pipeline behind them.
# So the most prominent sentence in a degraded morning email said "the list
# below is incomplete, do not read it as a full scan of the universe" over last
# night's COMPLETE shortlist, in a pass that scans no universe -- and its failed
# twin said "no scan was completed", which is true of every morning run by
# design. Of the three lines a phone skimmer reads, two were false.

from src.emailer import _plural  # noqa: E402 -- the band's own pluraliser

STALE = dict(DEGRADED, session="2026-08-10", stale_sessions=15,
             errors=[{"stage": "session", "message": "nothing has published since"}])


def test_a_degraded_morning_email_does_not_call_last_nights_shortlist_incomplete():
    morning = build_html(results_for("morning"), "morning", dict(DEGRADED, session="2026-08-31"))

    assert "the rows below are an earlier evening run's shortlist" in morning
    assert "Do not read it as a full scan of the universe" not in morning, (
        "a morning pass scans no universe, so it cannot have scanned part of one")


def test_a_degraded_evening_email_still_says_the_scan_is_partial(results):
    """The precondition for the test above: the evening sentence is right for
    the evening run and must not have been traded away for the morning one."""
    evening = build_html(results, "evening", DEGRADED)

    assert "the list below is incomplete" in evening
    assert "Do not read it as a full scan of the universe" in evening
    assert "an earlier evening run's shortlist" not in evening


def test_a_failed_morning_email_does_not_report_a_scan_it_never_makes():
    """"no scan was completed" is true of every morning run ever, including
    every clean one, so as the headline of a failure it says nothing."""
    failed = dict(DEGRADED, status="failed", session="2026-08-31")
    morning = build_html([], "morning", failed)

    assert "there is no watchlist below" in morning
    assert "no scan was completed" not in morning
    assert "no scan was completed" in build_html([], "evening", failed), (
        "and the evening headline keeps the sentence that is true of it")


def test_a_stale_morning_email_leads_with_the_gap_not_with_degraded():
    """One session late and fifteen sessions dead used to render the same
    words. The headline is what a phone shows after the subject."""
    band = build_html(results_for("morning"), "morning", STALE)

    assert "NOTHING HAS PUBLISHED FOR 15 SESSIONS" in band
    assert "no market holiday is that long" in band
    assert "THIS FOLLOW-THROUGH IS DEGRADED" not in band


def test_the_heading_cannot_promise_today_over_rows_from_another_session():
    """It read "follow-through watchlist for TODAY" over every morning row
    unconditionally, including a snapshot fifteen sessions old, directly above
    a red band saying so. The session the rows are FROM is what goes in it."""
    stale = build_html(results_for("morning"), "morning", STALE)
    fresh = build_html(results_for("morning"), "morning", dict(DATED, status="ok"))

    assert "2026-08-10&rsquo;s shortlist, at today&rsquo;s open" in stale
    assert "2026-08-31&rsquo;s shortlist, at today&rsquo;s open" in fresh
    assert "watchlist for TODAY" not in stale and "watchlist for TODAY" not in fresh


def test_the_heading_does_not_promise_a_shortlist_that_is_not_there():
    """A failed morning run still knows the session it was going for, and the
    heading used that to announce "2026-08-31's shortlist" over an empty table
    saying there is none."""
    failed = dict(DATED, status="failed",
                  errors=[{"stage": "history", "message": "unreadable"}])
    html = build_html([], "morning", failed)

    assert "following through on 2026-08-31, at today&rsquo;s open" in html
    assert "shortlist, at today" not in html


def test_a_heading_with_no_session_to_name_does_not_invent_one():
    """The precondition: the date in the heading comes from the caller. With
    no published run at all there is no session, and the heading says that
    rather than falling back to a promise about today."""
    html = build_html([], "morning", dict(STATS, status="degraded",
                                          errors=[{"stage": "history", "message": "none"}]))

    assert "follow-through, with nothing to follow" in html
    assert "close 20" not in html


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
            "last_outcome": None, "seen_before": 0,
            "history_from": "2026-08-03", "history_sessions": 20}
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


@pytest.mark.parametrize("gap,prefix", [
    (1, "[4% Burst] DEGRADED — Morning follow-through"),
    (2, "[4% Burst] NOTHING PUBLISHED IN 2 SESSIONS — Morning follow-through"),
    (3, "[4% Burst] NOTHING PUBLISHED IN 3 SESSIONS — Morning follow-through"),
    (15, "[4% Burst] NOTHING PUBLISHED IN 15 SESSIONS — Morning follow-through"),
])
def test_the_subject_escalates_once_a_holiday_cannot_explain_the_gap(gap, prefix, results):
    """Rendered at 1, 3 and 15 sessions the three emails were byte-identical
    but for a date -- and a phone shows the subject and nothing else, so a
    screener dead for three weeks arrived looking like the Tuesday after
    Presidents' Day. The boundary is 2 and it is arithmetic, not a calendar:
    the US market has no two adjacent holidays. src.pipeline's
    stale_snapshot_note() makes the same cut in the same place."""
    stats = dict(DATED, status="degraded", stale_sessions=gap,
                 errors=[{"stage": "session", "message": "nothing has published since"}])

    assert subject_for(results, "morning", stats).startswith(prefix)


def test_a_failed_run_outranks_a_stale_one_in_the_subject(results):
    """A run with no rows at all is the worse state, and a stale count would be
    describing rows that are not there."""
    stats = dict(DATED, status="failed", stale_sessions=15, errors=[{"stage": "x", "message": "y"}])

    assert subject_for([], "morning", stats).startswith("[4% Burst] FAILED — ")


def test_a_run_that_is_not_stale_carries_no_stale_count(results):
    """The precondition: the escalation comes from the caller's count, not from
    the word "morning" or from the status."""
    assert subject_for(results, "morning", dict(DATED, status="degraded",
                                                errors=[{"stage": "x", "message": "y"}])
                       ).startswith("[4% Burst] DEGRADED — ")
    assert subject_for(results, "morning", dict(DATED, stale_sessions=15)).startswith(
        "[4% Burst] Morning follow-through")


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

    assert ("last seen 2026-08-28, passed the gate, but the run had already sent its "
            "limit of candidates to Claude") in html
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


def test_a_repeat_an_absolute_rule_refused_says_neither_of_the_other_two():
    """The third outcome, and the one that reads worst if it borrows either
    other phrase. "rejected at the 2LYNCH gate" is false -- the checklist may
    have passed it 6/6 -- and "passed the gate, but..." says the run merely ran
    out of calls. The reader has to be able to tell that a rule refused it."""
    html = build_html(_with_streak(day=2, first_seen="2026-08-28",
                                   last_seen="2026-08-28",
                                   last_outcome=pipeline.VETO_REASONS["up_days"],
                                   seen_before=1),
                      "evening", DATED)

    assert ("last seen 2026-08-28, refused outright — it burst after three or more "
            "consecutive up days") in html
    assert "rejected at the 2LYNCH gate" not in html
    assert "passed the gate" not in html


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
    ("history_undated", "streak unknown — the history holds runs, but none of them "
                        "carry a date to count from"),
    ("no_history", "streak unknown — no history has been recorded yet; a day number "
                   "appears once the record reaches back past the burst"),
    ("something_new", "streak unknown — no reason was recorded"),
])
def test_an_unknown_streak_says_which_kind_of_unknown_it_is(reason, said):
    """`day: null` is the state this whole mechanism cares most about — unknown,
    which is NOT day 1 — and this surface used to render it as nothing at all,
    while the dashboard's pick card printed a sentence and its two tables
    printed nothing. Three surfaces, three answers, for the one state where a
    reader filling in the blank himself gets it wrong."""
    html = build_html(_with_streak(day=None, unknown_reason=reason, first_seen=None,
                                   history_from=None, history_sessions=0),
                      "evening", DATED)

    assert said in html
    assert "day 1" not in html and "new setup" not in html


def test_an_unknown_streak_still_reports_what_the_record_did_hold():
    """`day` is a claim about what came before; `last_seen` is a fact off the
    file. Losing the second with the first would throw away what was known."""
    html = build_html(_with_streak(day=None, unknown_reason="window_not_covered",
                                   first_seen=None, last_seen="2026-08-14",
                                   last_score=5.2, last_verdict="skip",
                                   last_outcome="scored", seen_before=1,
                                   history_from="2026-08-12", history_sessions=3),
                      "evening", DATED)

    assert "day unknown — burst on 1 of the 3 sessions in the record, which begins " \
           "2026-08-12; this setup may have started before it · " \
           "last seen 2026-08-14, scored 5.2/10 skip" in html


def test_an_unbroken_run_reports_the_record_instead_of_saying_unknown():
    """THE inversion this replaces: a day number needs the record to reach back
    past where the chain starts, and an UNBROKEN chain pins its start at the
    oldest run in the file -- so a name that burst on all eight sessions the
    ledger holds read "streak unknown", while a name that took a week off and
    burst twice read "day 2 of this setup". The arithmetic is right and stays.
    What changes is that the record's own answer to the narrower question gets
    said, instead of nothing."""
    html = build_html(_with_streak(day=None, unknown_reason="window_not_covered",
                                   first_seen=None, seen_before=8,
                                   history_from="2026-08-20", history_sessions=8),
                      "evening", DATED)

    assert ("day unknown — burst on 8 of the 8 sessions in the record, which begins "
            "2026-08-20; this setup may have started before it") in html
    assert "the history does not reach back this far" not in html
    assert "day 1" not in html and "new setup" not in html


def test_a_shallow_record_with_no_earlier_burst_says_how_shallow():
    """The other half: nothing was seen, but the record has barely looked, and
    the reader needs both halves to weigh the absence."""
    html = build_html(_with_streak(day=None, unknown_reason="window_not_covered",
                                   first_seen=None, seen_before=0,
                                   history_from="2026-08-27", history_sessions=3),
                      "evening", DATED)

    assert ("day unknown — no earlier burst in the 3 sessions in the record, which "
            "begins 2026-08-27; an earlier one would fall outside it") in html


def test_a_block_with_no_span_to_report_falls_back_to_the_flat_sentence():
    """A row published before src.ledger carried history_from/history_sessions.
    The richer sentence is built from the file's span; with no span there is
    nothing to build it out of, and inventing one would be worse than the
    sentence it replaced."""
    html = build_html(_with_streak(day=None, unknown_reason="window_not_covered",
                                   first_seen=None, seen_before=4,
                                   history_from=None, history_sessions=0),
                      "evening", DATED)

    assert "streak unknown — the history does not reach back this far" in html
    assert "in the record" not in html


def test_a_fresh_install_says_the_unknown_resolves():
    """The deployed product's permanent state until the first commit-back
    succeeds: every row on every surface says no_history. The only thing that
    used to suggest it was temporary was the word "yet"."""
    html = build_html(_with_streak(day=None, unknown_reason="no_history",
                                   first_seen=None, history_from=None,
                                   history_sessions=0),
                      "evening", DATED)

    assert "a day number appears once the record reaches back past the burst" in html


def test_a_streak_that_is_not_a_block_does_not_take_the_email_down(fake_resend):
    """A morning row comes off disk. A truncated or hand-edited snapshot must
    cost a streak, not the 8:30 email -- the email is the monitor, and one that
    does not arrive is the failure step 5 exists to end."""
    send_email([make_result("AAA", streak="day 2 probably")], "morning", DATED)

    assert "streak unknown — this run recorded none" in fake_resend.sent[0]["html"]


def test_a_row_carrying_no_streak_field_at_all_is_unknown_too(results):
    """A row from before the field existed is not a first sighting either.
    Absence and "day 1 — new setup" must never render the same."""
    html = build_html(results, "evening", DATED)

    assert html.count("streak unknown — this run recorded none") == len(results)
    assert "new setup" not in html


def test_the_funnel_does_not_tell_a_vetoed_six_of_six_it_failed_the_checklist():
    """`gated` counts what cleared the checklist AND survived every veto.

    It is printed under the label "Passed 2LYNCH gate", so on a night with a
    refusal the label described a number the checklist did not produce — and
    the burst it excluded may have passed 6/6, which is the collapse this
    project forbids by name. The refusals get their own line.
    """
    stats = dict(DATED, bursts=4, vetoed=1, gated=2)

    html = build_html([make_result("AAA")], "evening", stats)

    assert "Refused by an absolute rule: 1" in html
    assert "Passed 2LYNCH gate: 2" in html
    assert "4% bursts found: 4" in html


def test_a_run_with_no_refusals_reads_exactly_as_it_did_before():
    """The line is conditional on there being one, and 0 is not one. A snapshot
    written before the rule existed reports 0 and must say nothing at all —
    naming a rule a run never applied is the confidently-false sentence."""
    for vetoed in (0, None):
        stats = dict(DATED, bursts=4, gated=3)
        if vetoed is not None:
            stats["vetoed"] = vetoed
        html = build_html([make_result("AAA")], "evening", stats)
        assert "absolute rule" not in html, vetoed
        assert "Passed 2LYNCH gate: 3" in html


def test_a_night_every_burst_was_refused_does_not_blame_the_checklist():
    """"No candidates passed the quality gate today" states the opposite of
    what happened when the checklist passed them and a rule refused them."""
    stats = dict(DATED, bursts=3, vetoed=3, gated=0)

    html = build_html([], "evening", stats)

    assert "refused outright by an absolute rule" in html
    assert "No candidates passed the quality gate" not in html


def test_what_day_n_counts_is_disclosed_once_under_the_table():
    """A streak counts every session the scan found a burst on, every unscored
    one included — the right call, and one no reader can infer from "day 2 of
    this setup".

    The disclosure named the 2LYNCH gate alone while a third reason existed and
    while a row three lines above printed that third reason's own words, so the
    phrase asserted here covers all three ways a burst goes unscored.
    """
    counted = build_html(_with_streak(day=2, first_seen="2026-08-28"), "evening", DATED)
    # The same count, on a row that cannot put a day number on it: "burst on 8
    # of the 8 sessions in the record" is over the same bursts and needs the
    # same disclosure. It used to be gated on `day > 1` alone, so this row --
    # which makes the LARGER claim -- carried none.
    no_day = build_html(_with_streak(day=None, unknown_reason="window_not_covered",
                                     first_seen=None, seen_before=8,
                                     history_from="2026-08-20", history_sessions=8),
                        "evening", DATED)
    single = build_html(_with_streak(), "evening", DATED)

    disclosure = "including the ones that were never scored"
    assert disclosure in counted
    assert disclosure in no_day
    assert disclosure not in single, (
        "and it is not printed under a table with no streak to explain")
    # All three reasons, named. A disclosure that lists two of them tells the
    # reader the count is smaller than it is.
    for reason in ("the checklist rejected", "an absolute rule refused",
                   "the call cap crowded"):
        assert reason in counted, reason


def test_a_morning_run_with_nothing_to_show_does_not_blame_the_market():
    """Three empty tables now, and only one of them is a statement about
    stocks: a morning pass has nothing of its own to find."""
    assert "The run this follows through on scored no candidates." in build_html(
        [], "morning", DATED)
    assert "No candidates passed the quality gate" in build_html([], "evening", DATED)


# _headline() knew the mode and the staleness, and neither of the two other
# things it asserts: whether there are rows, and whether anything actually
# shortened the list. Every sentence it produced said "the rows below" or "the
# list below". Both gaps were found by rendering the band and reading it, not
# by reading the function.

def _band(stage: str, run_type: str, results, **stats) -> str:
    from src.emailer import _headline
    return _headline(
        {"errors": [{"stage": stage, "message": "m"}], **stats}, run_type, results)


def test_a_degraded_run_with_no_rows_does_not_point_at_rows():
    """The morning run that refuses the fixture renders this directly above
    `No shortlist.` -- and that is not a corner case. docs/data.json ships as
    the fixture, so it is the state of the first production morning run and of
    every one until evening.yml's commit-back succeeds.
    """
    for run_type in ("morning", "evening"):
        headline = _band("history", run_type, [])
        assert "rows below" not in headline, headline
        assert "list below is incomplete" not in headline, headline
        assert "no watchlist below" in headline or "no shortlist below" in headline


def test_a_stale_morning_with_no_rows_still_names_the_gap_without_promising_rows():
    headline = _band("history", "morning", [], stale_sessions=15, session="2026-08-11")
    assert "NOTHING HAS PUBLISHED FOR 15 SESSIONS" in headline
    assert "rows below" not in headline, headline
    assert "2026-08-11" in headline


@pytest.mark.parametrize("gap, escalates", [(1, False), (2, True), (3, True), (15, True)])
def test_the_headline_escalates_at_two_sessions_not_three(gap, escalates):
    """The boundary itself, from both sides.

    Every band test here used a gap of 15, so `stale >= 2` could be changed to
    `stale >= 3` with the whole suite green -- verified by mutation. The
    subject line's identical boundary was already parametrised over 1/2/3/15
    and killed it; this is the same coverage one surface over.

    Two is where the arithmetic changes, and the reason is the one judgement
    CLAUDE.md records about the calendar: none of the market's SCHEDULED
    holidays are adjacent, so at a gap of one a holiday is still a live
    explanation and the band must stay ambiguous, while from two up at least
    one of those days was a session nothing scanned.
    """
    headline = _band("history", "morning", [], stale_sessions=gap, session="2026-08-11")

    assert ("NOTHING HAS PUBLISHED FOR" in headline) is escalates, headline
    if escalates:
        assert _plural(gap, "SESSION").upper() in headline


def test_only_a_scan_problem_calls_the_list_incomplete():
    """Of the stages an evening run can report, one shortens the list and the
    rest spoil it. A chart that would not render printed "the list below is
    incomplete" over a scan that reached every symbol it asked for -- a true
    problem described falsely, which spends the trust the next real one needs.
    """
    rows = [{"ticker": "AAA"}]
    incomplete = "the list below is incomplete"
    assert incomplete in _band("scan", "evening", rows)
    for stage in ("chart", "score", "history", "session", "archive"):
        headline = _band(stage, "evening", rows)
        assert incomplete not in headline, f"{stage}: {headline}"
        assert "scan below is complete" in headline, f"{stage}: {headline}"


def test_a_scan_problem_beside_another_one_still_says_incomplete():
    """The list is shortened if ANY problem shortened it -- the check is over
    every error, not over the first one."""
    from src.emailer import _headline
    stats = {"errors": [{"stage": "chart", "message": "m"},
                        {"stage": "scan", "message": "m"}]}
    assert "the list below is incomplete" in _headline(stats, "evening", [{"ticker": "A"}])


def test_a_malformed_error_entry_cannot_crash_the_only_monitor():
    """The band is what reports every other failure. It must not become one."""
    from src.emailer import _headline
    stats = {"errors": ["not a dict", None, {"no_stage": True}]}
    assert "DEGRADED" in _headline(stats, "evening", [{"ticker": "A"}])


def test_a_streak_day_that_is_not_a_number_does_not_take_the_email_down(fake_resend):
    """ledger.snapshot_problem() checks a morning row's SHAPE and not its
    content, so a block whose day is the string "3" reaches this module
    well-formed. It was a TypeError out of `day > 1` here, after the band and
    the title had been built and before anything was sent -- the email is the
    monitor, and it must arrive."""
    send_email(_with_streak(day="3", seen_before=2, last_seen="2026-08-28"), "morning", DATED)

    html = fake_resend.sent[0]["html"]
    assert "streak unknown" in html and "day 3" not in html
    assert "day N of this setup" in html, "the footnote path compares the same value"


@pytest.mark.parametrize("value", [None, "", "   "])
def test_an_unset_sender_falls_back_even_when_actions_passes_it_as_empty(
    monkeypatch, fake_resend, results, value
):
    """os.environ.get's default fires only on a MISSING key, and Actions never
    leaves this one missing: evening.yml always sets RESEND_FROM, and GitHub
    expands an unset secret to ''. So the variable arrives present and empty,
    the documented fallback never fired, and the send went out with `from: ''`
    -- which Resend refuses. Setting the other five secrets and leaving this
    one out therefore mailed nothing while the run reported itself clean.

    The same absent-versus-empty distinction as run.status, and the same rule
    src.pipeline's _absent() already applies everywhere else.
    """
    monkeypatch.delenv("RESEND_FROM", raising=False)
    if value is not None:
        monkeypatch.setenv("RESEND_FROM", value)

    send_email(results, "evening", DATED)

    assert fake_resend.sent[0]["from"] == "onboarding@resend.dev"
