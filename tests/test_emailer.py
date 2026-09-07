"""Layer 6 -- the rendered email and the Resend boundary.

The suite must never send mail, so resend.Emails.send is replaced with a
double that captures its payload, and the delivery env vars are set inside
the test rather than read from the machine.
"""

from __future__ import annotations

import logging
import base64

import pytest

from src import emailer, pipeline
from src.emailer import build_html, deliver, send_email, send_failure_notice, subject_for
from src.scorer import render_chart

STATS = {"universe": "230 checked-in US common stocks", "bursts": 42, "gated": 12}

#: Every way a burst goes unscored, in the footnote's own words. ONE tuple for
#: the two tests that pin the footnote on both surfaces, derived from the
#: reason vocabulary so a fifth reason cannot arrive without a phrase.
STREAK_REASON_PHRASES = ("the checklist rejected", "an absolute rule refused",
                         "the liquidity floor refused", "the call cap crowded")


def _visible_text(html: str) -> str:
    """What a mail client shows, through a real parser -- the only honest
    reading of an escaping claim.

    The typographic apostrophe &rsquo; renders as a curly one and is folded to
    a plain one here, so an assertion that a sentence is GONE cannot pass
    merely by having been typed with the other quote. Nothing in this file
    asserts a curly one.
    """
    from html.parser import HTMLParser

    class Reader(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []

        def handle_data(self, data):
            self.parts.append(data)

    reader = Reader()
    reader.feed(html)
    text = " ".join(" ".join(reader.parts).split())
    return text.replace("\u2019", "'").replace("\u2018", "'")


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
    # STATS says 12 bursts CLEARED the checklist, so the note may not say the
    # checklist rejected them -- it is the sentence for the opposite outcome.
    assert "cleared the 2LYNCH checklist and none produced a score" in html
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
    """Both are empty tables. Only one of them is a statement about stocks.

    DEGRADED's first problem is a `scan` one -- 138 of 230 symbols with no bar
    -- which is the only stage that makes the list shorter than the session
    deserved, and the precondition below says so, because the whole point of
    the test beneath this one is that the OTHER stages must not reach here.
    """
    assert any(e["stage"] in emailer.SHORTENING_STAGES for e in DEGRADED["errors"]), (
        "the precondition: this run's scan really was cut short")
    clean = build_html([], "evening", STATS)
    broken = build_html([], "evening", DEGRADED)
    assert "cleared the 2LYNCH checklist" in clean
    assert "cleared the 2LYNCH checklist" not in broken
    assert "not a statement about the market" in broken


#: A complete evening scan of a quiet session that carries a problem which did
#: NOT cut it short. The shape of the first mail this project ever delivered:
#: run 34018706843, a Sunday dispatch, the mode/clock disagreement alone, 0
#: bursts, exit 2.
@pytest.mark.parametrize("stage, message", [
    ("session", "this evening run was started before the 16:15 ET close"),
    ("history", "the history could not be read and was set aside"),
    ("chart", "1 of 3 charts failed to render"),
    ("score", "4 of 12 candidates were not scored by Claude"),
])
def test_an_evening_scan_that_completed_says_what_it_found_whatever_else_broke(
    stage, message
):
    """The evening half of the same defect, and the discriminator is the one
    the band two inches above already applies: SHORTENING_STAGES. Testing
    `errors` sent every one of these to "this is not a statement about the
    market" over a scan that read every symbol asked for and found no burst --
    while _headline() told the same reader, in the band, that "the scan below
    is complete". One email, two answers, on one screen."""
    stats = dict(STATS, status="degraded", session="2026-09-04", bursts=0, gated=0,
                 errors=[{"stage": stage, "message": message}])

    text = _visible_text(build_html([], "evening", stats))

    assert "No 4% burst anywhere in the universe today" in text
    assert "this is a quiet market, not a rejection" in text
    assert "not a statement about the market" not in text, (
        f"a {stage} problem spoils the run; it does not shorten the scan")
    assert message in text, "and the reason is still in the band"


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


@pytest.mark.parametrize("field,text", [
    ("reason", "Breakout above <resistance> on 3x volume, clean base."),
    ("reason", "Volume <avg since the gap, so demand is unproven."),
    ("key_risk", "earnings <5 sessions> away"),
    ("ticker", "A<B"),
    ("verdict", "B<+"),
])
def test_what_the_model_said_reaches_the_reader_whole(field, text):
    """The email interpolated model output straight into HTML, unescaped.

    A reason of "Breakout above <resistance> on 3x volume, clean base." renders
    in a mail client as "Breakout above" — the parser takes `<resistance>` for
    a tag and swallows the rest of the sentence. Silently: nothing marks the
    truncation, and the page renders the same row intact, so the two surfaces
    disagree about what the model said. `<` followed by a letter is enough, and
    a model writing about levels, ranges or comparisons produces one unprompted.

    These fields are not this module's words. `reason` and `key_risk` are the
    scoring model's, `ticker` comes off the feed, and on the morning path all
    of them are read back out of a docs/data.json a previous run wrote.

    Asserted through a REAL HTML PARSER rather than by substring: the bug is
    precisely that the text is present in the source and absent from the render,
    so `text in html` passes while the reader sees nothing.
    """
    from html.parser import HTMLParser

    class Rendered(HTMLParser):
        def __init__(self):
            super().__init__()
            self.text = []

        def handle_data(self, data):
            self.text.append(data)

    row = dict(make_result("AAA"), **{field: text})
    parser = Rendered()
    parser.feed(build_html([row], "evening", DATED))
    rendered = " ".join(parser.text)

    assert text in rendered, (
        f"{field} was truncated by the HTML parser; the reader sees "
        f"{[t for t in parser.text if text.split('<')[0].strip()[:12] in t]}")


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


@pytest.mark.parametrize("stats, label", [
    (dict(illiquid=2, liquidity_floor=359_000_000.0, liquidity_pctile=30.0),
     "Below the liquidity floor ($359.0M/day, the 30th percentile): 2"),
    (dict(illiquid=1, liquidity_floor=12_400_000), "Below the liquidity floor ($12.4M/day): 1"),
    (dict(illiquid=1, liquidity_floor=4.5e9, liquidity_pctile=1), "Below the liquidity floor ($4.5B/day, the 1st percentile): 1"),
    (dict(illiquid=1, liquidity_floor=850_000, liquidity_pctile=22), "Below the liquidity floor ($850k/day, the 22nd percentile): 1"),
    (dict(illiquid=1, liquidity_floor=1e6, liquidity_pctile=13), "Below the liquidity floor ($1.0M/day, the 13th percentile): 1"),
    (dict(illiquid=3), "Below the liquidity floor: 3"),
])
def test_the_funnel_names_the_floor_it_applied_when_the_run_recorded_one(stats, label):
    """Rule 6's refusals get a funnel line only when there were some, and it
    carries the floor in dollars and the percentile when the run recorded
    them -- "below the liquidity floor: 3" is not readable without the bar. A
    snapshot from before run.liquidity existed carries neither, and the label
    then says only what is known rather than inventing a figure."""
    html = _visible_text(build_html([make_result("AAA")], "evening", dict(DATED, bursts=6, gated=3, **stats)))
    assert label in html
    assert html.index("4% bursts found") < html.index("Below the liquidity floor") < html.index("Passed 2LYNCH gate")


def test_a_count_that_is_not_a_count_reaches_no_sentence():
    """A negative count is not a count and a float is not the int the
    pipeline writes. Unclamped, illiquid=-2 printed "Below the liquidity
    floor: -2" in the funnel and "-2 below the liquidity floor and 7 rejected"
    in the note -- seven of five bursts -- and vetoed=2.0 printed "Refused by
    an absolute rule: 2.0" over a note that counted it as 0. Every count goes
    through one clamp now and the funnel and the note read one number."""
    html = _visible_text(build_html([], "evening",
                                     dict(DATED, bursts=5, vetoed=0, illiquid=-2, gated=0,
                                          by_checklist=5)))
    assert "liquidity floor" not in html and "5 bursts measured, none cleared it" in html
    html = _visible_text(build_html([], "evening",
                                     dict(DATED, bursts=5, vetoed=2.0, illiquid=0, gated=0,
                                          by_checklist=5)))
    assert "absolute rule" not in html and "5 bursts measured, none cleared it" in html
    html = _visible_text(build_html([], "evening",
                                     dict(DATED, bursts=5, vetoed=-1, illiquid=0, gated=0,
                                          by_checklist=5)))
    assert "-1" not in html and "6 rejected" not in html


def test_the_funnel_says_nothing_about_a_floor_on_a_night_nothing_sat_below_it():
    html = build_html([make_result("AAA")], "evening",
                      dict(DATED, bursts=3, gated=3, illiquid=0, liquidity_floor=1e8, liquidity_pctile=30.0))
    assert "liquidity floor" not in html


def _funnel_counts(html: str) -> dict:
    """The funnel as a reader adds it up: every "label: N" pair in the line,
    read back off the RENDERED mail rather than off the stats that built it.

    A funnel that does not close is only visible from the numbers a person
    sees, which is how this defect survived: every count on the line was
    right and one stage had no line at all.
    """
    import re

    return {label: int(n) for label, n in
            re.findall(r"([A-Za-z0-9%][^:|]*?): (\d+)", _visible_text(html))}


def test_the_funnel_prints_the_stage_the_checklist_itself_rejected():
    """"4% bursts found: 6 | Refused by an absolute rule: 2 | Passed 2LYNCH
    gate: 3 | Shortlisted: 3" — six minus two minus three is one, and that one
    burst, rejected by the checklist itself, appeared on no line of the mail.

    The refusals and the crowded-out got their own lines in earlier rounds for
    exactly this reason: a count that vanishes reads as a count that never
    existed. The checklist's own rejection was the last stage that still did,
    and it is the stage the product is named after.

    The assertion is the reader's arithmetic over the rendered numbers, not
    over the inputs: what has to be true is that the mail closes.
    """
    stats = dict(DATED, bursts=6, vetoed=2, illiquid=0, gated=3, by_checklist=1)

    counts = _funnel_counts(build_html([make_result("AAA")], "evening", stats))

    assert counts["Rejected by the 2LYNCH checklist"] == 1
    assert (counts["4% bursts found"] - counts["Refused by an absolute rule"]
            - counts["Rejected by the 2LYNCH checklist"]) == counts["Passed 2LYNCH gate"]


def test_the_checklist_line_is_a_count_of_rows_and_never_what_is_left_over():
    """The number is the run's own count of the bursts the CHECKLIST refused —
    one per archived row carrying that reason word — and not the remainder
    when the other cuts are taken off the total.

    A remainder attributes every burst the funnel cannot otherwise account
    for to whichever cut does the subtracting. A refusal the stats block does
    not report — a reason word this mail has never heard of, a `vetoed` that
    is not a count, a record whose rows lost their reason — was then not
    omitted from the mail, it was REASSIGNED to the checklist: a positive
    false statement about which rule refused a name, and the collapse
    CLAUDE.md forbids by name whenever the reason word is a veto.

    Both halves are asserted, because "prints 0" and "prints nothing" are
    different mails and only one of them is honest here.
    """
    stats = dict(DATED, bursts=4, vetoed=1, illiquid=1, gated=1, by_checklist=0)
    assert stats["bursts"] - stats["vetoed"] - stats["illiquid"] - stats["gated"] == 1, (
        "PRECONDITION: the night needs a burst the funnel cannot account for, "
        "or a remainder and a count agree and this test cannot fail")

    text = _visible_text(build_html([make_result("AAA")], "evening", stats))

    assert "4% bursts found: 4" in text and "Passed 2LYNCH gate: 1" in text
    assert "Rejected by the 2LYNCH checklist" not in text
    assert "rejected by the 2LYNCH checklist" not in text, "nor in the empty cell's clause"


def test_a_night_the_checklist_rejected_nothing_reads_exactly_as_it_did_before():
    """The same rule the refusal and cap lines follow: printed only when the
    count is not zero. A night whose every burst got through says nothing
    about a stage that cut nobody."""
    html = build_html([make_result("AAA")], "evening",
                      dict(DATED, bursts=6, vetoed=2, illiquid=0, gated=4, by_checklist=0))

    assert "Rejected by the 2LYNCH checklist" not in _visible_text(html)


def test_a_record_that_does_not_report_the_cut_says_nothing_about_it_anywhere():
    """A run that did not count this stage has no number for it, and BOTH
    surfaces that render it have to fall silent together.

    The funnel and the empty-table cell answer the same question three inches
    apart, and the guard was written on one of them: the funnel refused to
    state a number it could not know while the cell below it stated one
    anyway — "Passed 2LYNCH gate: not recorded" over "2 bursts refused
    outright by an absolute rule and 4 rejected by the 2LYNCH checklist". One
    mail, two answers, and the invented one was the confident one.
    """
    stats = dict(DATED, bursts=6, vetoed=2, illiquid=0)
    stats.pop("gated", None)

    text = _visible_text(build_html([], "evening", stats))

    assert "Passed 2LYNCH gate: not recorded" in text
    assert "4% bursts found: 6" in text, "what the run DID count is still printed"
    assert "checklist" not in text.lower(), (
        "a mail that cannot say how many the checklist rejected must not say it")


def test_the_cell_states_the_cuts_it_has_and_says_the_rest_is_unattributed():
    """A run whose counted cuts do not cover its own burst total.

    Every "all of them" sentence this cell can print was true only because
    the checklist's count used to be the REMAINDER, which made the three cuts
    add up to the total by construction. Counted off the reason word they can
    fall short -- a row the record does not name, a reason word the mail has
    no line for -- and the cell then said "All 6 bursts the scan found were
    refused outright by an absolute rule" about a night that vetoed two. The
    shortfall is stated, and the clauses the run DID report are still stated
    with it: a sentence that drops them answers a narrower question than the
    reader asked.
    """
    two_of_six = _visible_text(build_html([], "evening",
                                          dict(DATED, bursts=6, vetoed=2, gated=0)))
    assert "2 bursts refused outright by an absolute rule." in two_of_six
    assert "This run recorded no reason for the other 4 bursts." in two_of_six
    assert "All 6 bursts" not in two_of_six, (
        "two of six were refused outright, and the sentence used to say six")

    nothing_named = _visible_text(build_html([], "evening", dict(DATED, bursts=6, gated=0)))
    assert ("6 bursts measured and none scored, and this run recorded no reason "
            "for any of them.") in nothing_named


def test_the_morning_funnel_counts_the_checklist_rejections_the_same_way():
    """The follow-through reports the run it is following, so the same
    snapshot must produce the same number on both mails. One fact rebuilt on
    two paths is how one name's checklist line came to read two ways in two
    mails a night apart, and the fix there was the fix here: one function,
    one number."""
    stats = dict(DATED, bursts=7, vetoed=2, illiquid=1, gated=3, by_checklist=1)

    evening = _funnel_counts(build_html([make_result("AAA")], "evening", stats))
    morning = _funnel_counts(build_html([make_result("AAA")], "morning", stats))

    assert morning["Rejected by the 2LYNCH checklist"] == 1
    assert (morning["Rejected by the 2LYNCH checklist"]
            == evening["Rejected by the 2LYNCH checklist"])


def test_the_call_cap_and_the_checklist_are_counted_apart():
    """The crowded-out names are INSIDE the gate's own count by construction —
    `to_score = passed_gate[:MAX_TO_SCORE]` — so a checklist count that
    borrowed the cap's number, or subtracted it, prints a wrong figure under a
    funnel that no longer closes.

    The night needs both cuts in different non-zero numbers: with the cap
    quiet, or with the two equal, either count stands in for the other and
    the test cannot tell them apart. That is the same shaped-test hole the
    score_cap line was found to have one round ago.
    """
    stats = dict(DATED, bursts=10, vetoed=1, illiquid=1, gated=5,
                 crowded_out=2, score_cap=3, by_checklist=3)
    assert stats["crowded_out"] and stats["crowded_out"] != stats["by_checklist"], (
        "PRECONDITION: the cap has to have bitten, in a different number from "
        "the checklist's own rejections, or one count can stand in for the other")

    counts = _funnel_counts(build_html([make_result("AAA")], "evening", stats))

    assert counts["Rejected by the 2LYNCH checklist"] == 3
    assert counts["Crowded out by the 3-call cap"] == 2
    assert (counts["4% bursts found"] - counts["Refused by an absolute rule"]
            - counts["Below the liquidity floor"]
            - counts["Rejected by the 2LYNCH checklist"]) == counts["Passed 2LYNCH gate"]


def test_the_funnel_reads_top_to_bottom_as_the_subtraction_a_reader_does():
    """Every cut is printed ABOVE the count it was taken off.

    A refusal count printed after the survivors' line reads as a further cut
    applied to the names that passed — "Passed 2LYNCH gate: 2 | Rejected by
    the 2LYNCH checklist: 1" says one of the two survivors was then rejected,
    when that name never passed. The order is the whole reason the numbers
    read as an arithmetic, and it is stated in README and in the funnel's own
    comment; every other assertion in this file reads the line into a dict or
    tests membership, both of which are blind to it.
    """
    text = _visible_text(build_html([make_result("AAA")], "evening",
                                    dict(DATED, bursts=9, vetoed=2, illiquid=1, gated=3,
                                         by_checklist=3, crowded_out=1, score_cap=3)))
    order = ["4% bursts found", "Refused by an absolute rule",
             "Below the liquidity floor", "Rejected by the 2LYNCH checklist",
             "Passed 2LYNCH gate", "Crowded out by the 3-call cap", "Shortlisted"]
    at = [text.index(label) for label in order]

    assert at == sorted(at), (
        "the funnel's stages are out of order: " + " | ".join(sorted(order, key=text.index)))


def test_one_mail_names_the_rule_that_rejected_these_names_with_one_word():
    """The funnel's line and the footnote under the table describe the same
    population, in one mail, and they are one word or they are two
    vocabularies for one mechanism side by side on one screen.

    The word is CHECKLIST, which is what the footnote has said since round 5
    ("whether the checklist rejected them"), what src.ledger's own contract
    says `lynch_gate` means, and what README's `last_outcome` bullet says. The
    streak line names the STAGE instead — LAST_OUTCOME's "rejected at the
    2LYNCH gate", which the page carries with the threshold in it ("rejected
    at the ≥3/6 2LYNCH gate") — and that register predates this line on both
    surfaces; what must not drift is the RULE's name, which the funnel and
    the footnote both print, and the reason word underneath all three, which
    the docs test pins across the email and the page.

    Rendered with a row on the table, because the earlier version of this test
    ran on an empty mail: with no rows there is no footnote and no streak
    line, so the phrases it forbade could not appear and it could not fail.
    """
    html = build_html(_with_streak(day=2, first_seen="2026-08-28", last_seen="2026-08-28",
                                   last_outcome="lynch_gate", seen_before=1),
                      "evening", dict(DATED, bursts=6, vetoed=2, illiquid=0,
                                      gated=3, by_checklist=1))
    text = _visible_text(html)

    assert "Rejected by the 2LYNCH checklist: 1" in text, "the funnel's line"
    assert "whether the checklist rejected them" in text, "the footnote's clause"
    assert "last seen 2026-08-28, rejected at the 2LYNCH gate" in text, (
        "the streak line names the stage, with the page's own words for the "
        "same reason word")
    assert "Rejected at the 2LYNCH gate:" not in text, (
        "the funnel line took the streak line's register, leaving the footnote "
        "below it naming a rule no line of the mail counts")

def test_a_night_every_burst_was_refused_does_not_blame_the_checklist():
    """"No candidates passed the quality gate today" states the opposite of
    what happened when the checklist passed them and a rule refused them."""
    stats = dict(DATED, bursts=3, vetoed=3, gated=0)

    html = build_html([], "evening", stats)

    assert "refused outright by an absolute rule" in html
    assert "No candidates passed the quality gate" not in html


# The empty-shortlist note used to be a two-way flag, and NEITHER way was
# reliably true. `refused_all` read `vetoed and not gated` -- but `gated` is
# how many PASSED, not how many the checklist rejected. Every case below was
# rendered and read before it was written down; three of the five were wrong.
@pytest.mark.parametrize("label, stats, must_say, must_not_say", [
    # The one that made the email contradict itself on a single screen: the
    # funnel two lines above said "Refused by an absolute rule: 1" while the
    # cell said EVERY burst had been.
    ("one veto among nine checklist rejections",
     dict(bursts=10, vetoed=1, gated=0, by_checklist=9),
     ["1 burst refused outright by an absolute rule", "9 rejected by the 2LYNCH checklist"],
     ["Every burst", "All 10 bursts"]),
    ("nine vetoes and one checklist rejection",
     dict(bursts=10, vetoed=9, gated=0, by_checklist=1),
     ["9 bursts refused outright", "1 rejected by the 2LYNCH checklist"],
     ["Every burst", "All 10 bursts"]),
    # Nothing was measured against the checklist, so nothing failed it. This
    # printed "No candidates passed the quality gate today" directly under a
    # funnel line reading "4% bursts found: 0" -- the project's named collapse,
    # arriving from the other direction: the gate blamed for an outcome it had
    # no part in.
    ("a quiet market with no burst at all",
     dict(bursts=0, vetoed=0, gated=0),
     ["No 4% burst anywhere in the universe today", "quiet market, not a rejection"],
     ["passed the quality gate", "2LYNCH checklist", "absolute rule"]),
    ("every burst refused outright",
     dict(bursts=4, vetoed=4, gated=0),
     ["All 4 bursts the scan found were refused outright"],
     ["rejected by the 2LYNCH checklist"]),
    # The fourth verdict, on every shape the other three can take: alone,
    # beside one of them, and beside both. Rule 6 never consulted the
    # checklist, so its clause must never read as a checklist rejection.
    ("every burst below the liquidity floor",
     dict(bursts=3, vetoed=0, illiquid=3, gated=0),
     ["All 3 bursts the scan found were below the liquidity floor", "never got a say"],
     ["rejected by the 2LYNCH checklist", "absolute rule"]),
    ("the one burst, below the floor",
     dict(bursts=1, vetoed=0, illiquid=1, gated=0),
     ["The one burst the scan found was below the liquidity floor"],
     ["All 1", "rejected by the 2LYNCH checklist"]),
    ("two below the floor among eight the checklist rejected",
     dict(bursts=10, vetoed=0, illiquid=2, gated=0, by_checklist=8),
     ["2 below the liquidity floor and 8 rejected by the 2LYNCH checklist", "Two different verdicts"],
     ["absolute rule", "All 10 bursts"]),
    ("a veto, two below the floor, and seven the checklist rejected",
     dict(bursts=10, vetoed=1, illiquid=2, gated=0, by_checklist=7),
     ["1 burst refused outright by an absolute rule, 2 below the liquidity floor and 7 rejected by the 2LYNCH checklist",
      "Three different verdicts, and none is another"],
     ["Two different verdicts", "All 10 bursts"]),
    ("a veto and two below the floor, nothing for the checklist",
     dict(bursts=3, vetoed=1, illiquid=2, gated=0),
     ["1 burst refused outright by an absolute rule and 2 below the liquidity floor", "Two different verdicts"],
     ["rejected by the 2LYNCH checklist", "All 3 bursts"]),
    ("the single-burst night, which reads wrong in the plural",
     dict(bursts=1, vetoed=1, gated=0),
     ["The one burst the scan found was refused outright"],
     ["All 1", "1 bursts"]),
    ("nothing vetoed: the checklist really did reject them",
     dict(bursts=7, vetoed=0, gated=0, by_checklist=7),
     ["No candidate passed the 2LYNCH checklist today", "7 bursts measured"],
     ["absolute rule"]),
])
def test_the_empty_shortlist_note_says_what_actually_happened(
    label, stats, must_say, must_not_say
):
    html = build_html([], "evening", dict(DATED, **stats))

    for phrase in must_say:
        assert phrase in html, f"{label}: missing {phrase!r}"
    for phrase in must_not_say:
        assert phrase not in html, f"{label}: should not say {phrase!r}"


def test_the_empty_shortlist_note_never_prints_a_negative_count():
    """Every count in this sentence is a number a caller supplies, and a
    stats block that does not add up must not produce "-3 rejected by the
    2LYNCH checklist" or "-2 below the liquidity floor and 7 rejected", seven
    of five bursts. Clamped, and a value that is not a count reads as zero
    rather than reaching the sentence at all."""
    for stats in [dict(bursts=2, vetoed=9, gated=0, by_checklist=-3),
                  dict(bursts=2, vetoed=0, gated=9, illiquid=-2, by_checklist=7),
                  dict(bursts="10", vetoed=None, gated=True, by_checklist="4")]:
        html = build_html([], "evening", dict(DATED, **stats))
        assert "-" not in html.split("colspan=\"7\"")[1].split("</td>")[0], stats


def test_the_email_and_the_page_disclose_what_a_streak_counts_the_same_way():
    """One disclosure, two surfaces, and a reader gets both.

    The page's version named the 2LYNCH gate ALONE -- under a comment saying
    "same disclosure the email prints, same words". That stopped being true
    when the veto arrived: a 6/6 name refused by an absolute rule is counted in
    `seen_before`, and the tooltip told the reader it was not. The email was
    swept for exactly this in the 3.3 audit and the page was not.

    Asserted on both files, because a comment claiming they match is what
    carried the drift for a whole round.
    """
    import pathlib

    html = build_html(_with_streak(day=2, first_seen="2026-08-28"), "evening", DATED)
    page = pathlib.Path(__file__).resolve().parents[1].joinpath("docs/index.html").read_text()

    for reason in STREAK_REASON_PHRASES:
        assert reason in html, f"the email dropped {reason!r}"
        assert reason in page, f"the page dropped {reason!r}"
    # And the wording it drifted TO is gone from both, not merely joined.
    assert "including the ones the 2LYNCH gate rejected" not in page
    assert "including the ones the 2LYNCH gate rejected" not in html


def test_the_email_and_the_page_name_the_call_cap_the_same_way():
    """One mechanism, two surfaces, and a reader gets both. The page's funnel
    has said "outside the 25-call cap" since step 9; the email's funnel had no
    such stage at all until this round, and when it got one the phrase had to
    be the page's rather than a second wording for the same cut.

    Asserted against docs/index.html's own source, because that is where the
    other half lives and a comment claiming they match is exactly what this
    project has been caught by before.
    """
    import pathlib

    html = build_html([], "evening", dict(DATED, bursts=40, gated=30, crowded_out=5,
                                          score_cap=25))
    page = pathlib.Path(__file__).resolve().parents[1].joinpath("docs/index.html").read_text()

    assert "the 25-call cap" in html
    assert "'-call cap'" in page, (
        "the page stopped building the same phrase; the two surfaces have drifted")


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
    # All four reasons, named. A disclosure that lists three of them tells the
    # reader the count is smaller than it is -- and this loop listed three for
    # a round after the fourth arrived, so the clause could be deleted green.
    for reason in STREAK_REASON_PHRASES:
        assert reason in counted, reason


def test_a_morning_run_with_nothing_to_show_does_not_blame_the_market():
    """Three empty tables now, and only one of them is a statement about
    stocks: a morning pass has nothing of its own to find. The sentence names
    the session it is about, because the run it follows through on is not
    today's and every other surface of this mode says which one it is."""
    assert "The 2026-08-31 run this follows through on scored no candidates." in build_html(
        [], "morning", DATED)
    assert "scored no candidates" not in build_html(
        [], "evening", DATED), "and an evening run says what its own scan found"


# --- the morning empty cell reads the run it follows, not this pass's band ---
#
# THE MAIL THE TUESDAY CRON WOULD HAVE SENT. build_html() tested `errors`
# before the mode, so any problem at all -- including the staleness band, which
# is a fact about publishing and not about the market -- printed "See the
# failures listed above" over a source run that was clean and simply found
# nothing. Reproduced over main's real docs/data.json (0 bursts, status ok)
# with the clock at 2026-09-08 12:30 UTC: "this is not a statement about the
# market" three lines under "4% bursts that session: 0", which IS one.

#: The stale morning run over main's real 4 Sep record, as of Tuesday 8 Sep.
FOLLOWED_CLEAN = dict(
    STATS, status="degraded", session="2026-09-04", bursts=0, gated=0,
    stale_sessions=1, followed_status="ok",
    errors=[{"stage": "session", "message":
             "the newest published run is the evening run of 2026-09-04, and nothing "
             "has published a later session — that is 1 session ago"}],
)


def test_a_morning_over_a_clean_run_that_found_nothing_says_what_that_run_found():
    text = _visible_text(build_html([], "morning", FOLLOWED_CLEAN))

    assert "The 2026-09-04 run this follows through on found no 4% burst" in text
    assert "not a statement about the market" not in text, (
        "the source run WAS a statement about the market: it scanned the session "
        "cleanly and found no burst. The staleness is the band's business")


#: One name the feed stopped answering for, as a run recorded it.
STOPPED = {"after_sessions": 5, "count": 1,
           "names": [{"ticker": "EA", "last": "2026-08-04", "sessions_behind": 23}]}


def test_the_stopped_printing_line_is_scoped_to_the_run_that_read_the_file():
    """A fact about data/symbols.txt AS THAT RUN READ IT, which is not a fact
    about the file now. The evening sentence was written for the run that had
    just read the file and ends in "check the list"; the morning renders a
    record hours or days old, and acting on the line is exactly what changes
    the file underneath it. This repo did that between its own two runs -- the
    4 Sep record names FI, BK and EA and all three were retired the next day --
    so the first morning cron would have told its reader that three names it no
    longer holds are in it, in the present tense, with an instruction to act."""
    stats = dict(DATED, stopped_printing=STOPPED)

    evening = _visible_text(build_html([], "evening", stats))
    morning = _visible_text(build_html([], "morning", stats))

    assert "1 name in the symbol file with no bar" in evening
    assert evening.rstrip().count("check the list.") == 1
    assert "1 name in the symbol file as the 2026-08-31 run read it" in morning
    assert "check the list if they are still in it" in morning
    assert "in the symbol file with no bar" not in morning, (
        "the morning cannot say what the file holds now: it never read one")


def test_a_morning_with_no_published_run_to_read_still_defers_to_the_failures():
    """The state every morning is in until evening.yml's commit-back succeeds:
    no counts were read, so there is nothing to say about the market."""
    text = _visible_text(build_html([], "morning", dict(
        status="degraded",
        errors=[{"stage": "history", "message": "there is nothing to follow through on"}])))

    assert "See the failures listed above" in text, (
        "and it points at the band, which is the half the no-band twin drops")
    assert "not a statement about the market" in text
    assert "found no 4% burst" not in text


@pytest.mark.parametrize("bursts", [True, -3, "0"])
def test_the_funnel_prints_not_recorded_for_the_same_values_the_cell_refuses(bursts):
    """ONE RULE FOR ONE FIELD. The cell refused a bool, a string and a negative
    and explained that the bursts could not be counted; the funnel three lines
    above it printed the same value raw -- "4% bursts that session: -3" over a
    sentence saying it could not be read, and "Below the liquidity floor: -2"
    is the same defect round 5 fixed one column over. Both go through
    is_count() now."""
    stats = dict(STATS, status="degraded", session="2026-09-04", bursts=bursts,
                 gated=bursts, errors=[{"stage": "history", "message": "unreadable"}])

    text = _visible_text(build_html([], "morning", stats))

    assert "4% bursts that session: not recorded" in text
    assert "Passed 2LYNCH gate: not recorded" in text
    assert f"4% bursts that session: {bursts}" not in text
    evening = _visible_text(build_html([], "evening", dict(stats, universe="2 names")))
    assert "4% bursts found: not recorded" in evening, "and the evening funnel too"


@pytest.mark.parametrize("bursts", [None, True, -3, "0"])
def test_a_morning_whose_burst_count_is_not_a_count_says_nothing_about_the_market(bursts):
    """`bursts` is the same fact the funnel reads to decide whether there was
    a run to read at all, and it is not shape-checked at load: absent is the
    morning that read nothing, and a bool, a negative or a string is a file no
    writer produces. One branch for all four -- a cell that cannot count the
    bursts cannot report what the session held."""
    stats = dict(status="degraded", session="2026-09-04",
                 errors=[{"stage": "history", "message": "unreadable"}])
    if bursts is not None:
        stats["bursts"] = bursts

    text = _visible_text(build_html([], "morning", stats))

    assert "not a statement about the market" in text
    assert "See the failures listed above" in text, "there IS a band here"
    assert "found no 4% burst" not in text and "scored no candidates" not in text


def test_a_morning_over_a_run_whose_scan_was_cut_short_refuses_to_trust_its_counts():
    """A source run that could not finish its SCAN still published counts, and
    they are not a reading of the session. Both facts, in one sentence."""
    text = _visible_text(build_html([], "morning", dict(
        FOLLOWED_CLEAN, followed_stages=["scan"])))

    assert "The 2026-09-04 run this follows through on found no 4% burst" in text
    assert "that run's own scan was cut short" in text
    assert "not a statement about the market" in text
    assert "4% bursts that session: 0" in text, "and the funnel still reports what it read"


@pytest.mark.parametrize("stage", ["session", "history", "chart", "score", "email"])
def test_a_morning_over_a_run_degraded_after_a_complete_scan_reads_its_counts(stage):
    """THE SAME FALSE SENTENCE, ONE BRANCH OVER. The first version of this rule
    deferred on the source run's STATUS word, and "degraded" is one word for
    reasons that do and do not compromise a scan: of the five ways an evening
    run degrades, only the scan guards cut it short. main's own 4 Sep record is
    two of the others -- the Sunday clock disagreement and the Resend refusal --
    over a clean scan of 228 names that found no burst, and the morning after
    it retracted that count.

    The source run's reasons are still carried into the band by
    src.pipeline's carried_problems(), and the band still says the run it
    follows was DEGRADED. What must not happen is the COUNT being withdrawn."""
    text = _visible_text(build_html([], "morning", dict(
        FOLLOWED_CLEAN, followed_stages=[stage])))

    assert "The 2026-09-04 run this follows through on found no 4% burst" in text
    assert "not a statement about the market" not in text, (
        f"a {stage} problem in that run did not stop it reading the session")
    assert "cut short" not in text


def test_a_morning_over_a_named_ticker_run_says_what_that_run_scanned():
    """The cell makes a claim about the MARKET, and a --tickers run writes
    docs/data.json like any other: over a two-name smoke record it said no 4%
    burst reached the checklist, with nothing anywhere on the mail saying the
    scan was two names. The morning funnel carries no universe line, by
    design -- THIS pass scanned none -- so the scope goes in the sentence that
    needs it."""
    named = _visible_text(build_html([], "morning", dict(
        FOLLOWED_CLEAN, followed_universe="2 named on the command line (--tickers)")))
    whole_file = _visible_text(build_html([], "morning", FOLLOWED_CLEAN))

    assert ("That run scanned 2 named on the command line (--tickers), not the "
            "checked-in universe.") in named
    assert "That run scanned" not in whole_file, (
        "and a scan of the checked-in file needs no clause: it is the ordinary case")


def test_a_morning_that_cannot_count_the_bursts_does_not_point_at_a_band_that_is_absent():
    """The pointer and the band are two halves of one mechanism. A snapshot
    whose `bursts` cannot be read is refused at load by snapshot_problem() and
    refused here, and neither state requires the run to have a problem of its
    own -- so the cell sent a reader to "the failures listed above" over a mail
    with no red band at all."""
    stats = dict(STATS, status="ok", session="2026-09-04", bursts="0", errors=[])

    text = _visible_text(build_html([], "morning", stats))

    assert "See the failures listed above" not in text
    assert "no failures to point at" in text
    assert "not a statement about the market" in text


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



def test_the_whole_monitor_survives_a_malformed_error_entry_not_just_its_headline():
    """The test above is named for the monitor and exercised only _headline();
    build_html() -- the entry point the name promises -- crashed on the very
    same input, because _banner() called .get() on every entry with no guard.
    Not reachable from the pipeline today, which is exactly why it reported
    safety that was not there."""
    stats = {"status": "degraded", "errors": ["not a dict", None, {"no_stage": True},
                                               {"stage": "scan", "message": "a real one"}]}
    html = build_html([], "evening", stats)
    assert "a real one" in html
    assert html.count("<li") == 2, "the two objects render; the two non-objects are skipped"


@pytest.mark.parametrize("where, stats, must_read", [
    # The one leaf that carries free text from OUTSIDE the codebase on the
    # first real night: anthropic's SDK sets the exception message to the raw
    # response body when it is not JSON, so an edge 5xx HTML page lands in
    # _check_scoring()'s sentence, and the band interpolated it raw. The
    # operator read "502 Bad Gateway 502 Bad Gateway cloudflare" with the
    # tags swallowed as nested markup inside the <li>.
    ("the red band", {"status": "degraded", "session": "2026-09-04", "bursts": 1, "gated": 1,
                      "errors": [{"stage": "score", "message":
                                  "First failures: BURST (anthropic.InternalServerError: Error code: 502 - "
                                  "<html><head><title>502 Bad Gateway</title></head></html>)"}]},
     "<html><head><title>502 Bad Gateway</title></head></html>"),
    # A session string is read off docs/data.json by the morning run; a
    # hand-edited file must not be able to inject markup into the title.
    ("the session in the title and funnel", {"status": "ok", "session": "2026-09-04<b>x</b>",
                                             "bursts": 1, "gated": 1}, "2026-09-04<b>x</b>"),
])
def test_every_free_text_leaf_reaches_the_reader_whole(where, stats, must_read):
    html = build_html([], "evening", stats)
    assert must_read in _visible_text(html), where
    assert must_read not in html, f"{where}: the raw text is in the source, so it was not escaped"


#: The same claim over the leaves that need a ROW or the morning mode to
#: render at all -- which is why the sweep above missed all five. Each is read
#: off docs/data.json by the morning pass, so a hand-edited or truncated
#: snapshot is the shape that reaches them.
@pytest.mark.parametrize("where, rows, run_type, stats, must_read", [
    ("the last score in a streak line",
     _with_streak(last_seen="2026-08-31", last_score="8<b>x</b>", last_outcome="scored"),
     "evening", DATED, "8<b>x</b>"),
    ("the last verdict in a streak line",
     _with_streak(last_seen="2026-08-31", last_score=8.4, last_verdict="A<i>y</i>",
                  last_outcome="scored"),
     "evening", DATED, "A<i>y</i>"),
    ("the session the record begins on, in a streak with no day number",
     _with_streak(day=None, first_seen=None, unknown_reason="window_not_covered",
                  history_from="2026-08-20<b>x</b>", history_sessions=8, seen_before=3),
     "evening", DATED, "2026-08-20<b>x</b>"),
    ("the row's own reason for carrying no chart",
     [make_result("AAA", chart=None, chart_note="no chart — <b>this pass</b> cannot date it")],
     "morning", DATED, "no chart — <b>this pass</b> cannot date it"),
    # The leaves here that were already escaped and pinned nowhere: a mutant
    # dropping esc() from each survived the sweep above, because every one of
    # them needs the morning mode, or a row, or both -- which is one level
    # further in than "needs a row" and is why the round that added the half
    # above still left four. Both stale-headline branches, because they are
    # two sentences and only one of them renders without rows.
    ("the session in the stale headline, with nothing to show", [], "morning",
     dict(STATS, status="degraded", session="2026-09-04<b>x</b>", stale_sessions=3,
          errors=[{"stage": "session", "message": "nothing has published"}]),
     "2026-09-04<b>x</b>"),
    ("the session in the stale headline, over rows",
     [make_result("AAA")], "morning",
     dict(STATS, status="degraded", session="2026-09-04<i>y</i>", stale_sessions=3,
          errors=[{"stage": "session", "message": "nothing has published"}]),
     "2026-09-04<i>y</i>"),
    ("the session stamped on the close cell", [make_result("AAA")], "morning",
     dict(STATS, session="2026-08-31<b>z</b>"), "2026-08-31<b>z</b>"),
    ("the close price itself", [make_result("AAA", close="44.8<b>q</b>")], "morning",
     DATED, "44.8<b>q</b>"),
    # _title()'s morning shortlist branch, which needs rows AND a session;
    # its no-rows twin is the case two rows above.
    ("the session in the morning shortlist heading", [make_result("AAA")], "morning",
     dict(STATS, session="2026-08-31<em>t</em>"), "2026-08-31<em>t</em>"),
])
def test_every_free_text_leaf_a_row_carries_reaches_the_reader_whole(
    where, rows, run_type, stats, must_read
):
    html = build_html(rows, run_type, stats)
    assert must_read in _visible_text(html), where
    assert must_read not in html, f"{where}: the raw text is in the source, so it was not escaped"


def test_the_checklist_lines_are_escaped_line_by_line():
    row = make_result("AAA", lynch_detail=["PASS  2_first: 0 prior bursts <tight base>"])
    html = build_html([row], "evening", DATED)
    assert "0 prior bursts <tight base>" in _visible_text(html)
    assert "<tight base>" not in html


def test_a_day_number_with_no_first_seen_drops_the_since_clause():
    """src.ledger never writes the pair, so it is an off-disk shape -- and
    "day 2 of this setup, since " with nothing after it is what the email
    made of it (the page printed "since —")."""
    html = build_html(_with_streak(day=2, first_seen=None), "evening", DATED)
    text = _visible_text(html)
    assert "day 2 of this setup" in text
    assert "since" not in text.split("day 2 of this setup")[1][:20]


@pytest.mark.parametrize("value, gain, ratio, score", [
    (12.0, "+12.0%", "12.00x", "12.0"),
    (12, "+12.0%", "12.00x", "12.0"),      # what ledger._num() hands the morning path
    (8.39, "+8.4%", "8.39x", "8.4"),
    (-0.5, "-0.5%", "-0.50x", "-0.5"),
    ("n/a", "n/a", "n/a", "n/a"),           # a value that is not a number passes through
])
def test_the_three_numbers_read_the_same_on_both_paths(value, gain, ratio, score):
    """The evening path hands floats and the morning path hands values that
    came off disk through ledger._num(), which turns 12.0 into 12 -- so one
    burst read "+12.0% | 8.39x | 7.0/10" at 6:30pm and "+12% | 8x | 7/10" at
    8:30am. One rule, both paths."""
    from src.emailer import fmt_gain, fmt_ratio, fmt_score

    assert (fmt_gain(value), fmt_ratio(value), fmt_score(value)) == (gain, ratio, score)


# --- Resend's test-mode refusal says which of three settings it is ----------

_TEST_MODE_REFUSAL = (
    "You can only send testing emails to your own email address (owner@example.invalid). "
    "To send emails to other recipients, please verify a domain at resend.com/domains, "
    "and change the `from` address to an email using this domain."
)


def _resend_refuses(monkeypatch, sentence: str) -> None:
    import resend

    def refuse(params, options=None):
        raise RuntimeError(sentence)
    monkeypatch.setattr(resend.Emails, "send", refuse)


@pytest.mark.parametrize("email_to, expected", [
    ("someone.else@example.test",
     "1 recipient(s): a different address, at example.test"),
    ("owner@example.invalid, someone.else@example.test",
     "2 recipient(s): the address Resend named, at example.invalid; a different address, at example.test"),
    # A case-only mismatch ALONE is respelt and resent before it can be
    # diagnosed (see the test below); beside a wrong address it cannot be.
    ("Owner@Example.invalid, someone.else@example.test",
     "2 recipient(s): the address Resend named in different capitalisation, at example.invalid; "
     "a different address, at example.test"),
])
def test_a_test_mode_refusal_says_how_the_recipients_compare_to_the_address_resend_named(
    fake_resend, monkeypatch, caplog, email_to, expected
):
    """The first live account went through three runs of one identical Resend
    sentence -- a second recipient, a typo and a secret saved where the
    workflow does not read it all produce it -- before anything said which.
    The count and the domains say which; no recipient is printed."""
    monkeypatch.setenv("EMAIL_TO", email_to)
    _resend_refuses(monkeypatch, _TEST_MODE_REFUSAL)

    with caplog.at_level(logging.ERROR, logger="src.emailer"), pytest.raises(RuntimeError):
        deliver("subject", "<p>body</p>")

    said = " ".join(r.getMessage() for r in caplog.records)
    assert expected in said, said
    assert "REPOSITORY secret" in said


def test_the_refusal_diagnosis_never_prints_a_recipient(fake_resend, monkeypatch, caplog):
    monkeypatch.setenv("EMAIL_TO", "someone.else@example.test, owner@example.invalid")
    _resend_refuses(monkeypatch, _TEST_MODE_REFUSAL)

    with caplog.at_level(logging.ERROR, logger="src.emailer"), pytest.raises(RuntimeError):
        deliver("subject", "<p>body</p>")

    said = " ".join(r.getMessage() for r in caplog.records)
    assert "2 recipient(s)" in said
    assert "someone.else@" not in said and "owner@" not in said, said


def test_any_other_resend_refusal_is_left_to_speak_for_itself(fake_resend, monkeypatch, caplog):
    """The diagnosis is for one sentence. An unverified sender domain, a bad
    key or a 5xx says its own thing, and a paragraph about recipients under
    it would send the operator to the wrong setting."""
    _resend_refuses(monkeypatch, "The example.invalid domain is not verified. Please add "
                                 "and verify your domain on https://resend.com/domains")

    with caplog.at_level(logging.ERROR, logger="src.emailer"), pytest.raises(RuntimeError):
        deliver("subject", "<p>body</p>")

    assert "recipient(s)" not in " ".join(r.getMessage() for r in caplog.records)


def test_a_case_only_mismatch_is_resent_in_resends_own_spelling(fake_resend, monkeypatch, caplog):
    """The first live account: EMAIL_TO was the account's address with a
    capital letter, Resend's test-mode check is an exact string match, and
    three dispatches drew the same refusal. Sent again as Resend spells it --
    the same mailbox, since providers treat the local part case-insensitively
    in practice -- once, on this refusal only, and said out loud."""
    import resend

    monkeypatch.setenv("EMAIL_TO", "Owner@Example.invalid")
    calls: list[list[str]] = []

    def send(params, options=None):
        calls.append(list(params["to"]))
        if len(calls) == 1:
            raise RuntimeError(_TEST_MODE_REFUSAL)
        return {"id": "resent-id"}
    monkeypatch.setattr(resend.Emails, "send", send)

    with caplog.at_level(logging.WARNING, logger="src.emailer"):
        response = deliver("subject", "<p>body</p>")

    assert response == {"id": "resent-id"}
    assert calls == [["Owner@Example.invalid"], ["owner@example.invalid"]], calls
    said = " ".join(r.getMessage() for r in caplog.records)
    assert "as Resend spells it" in said and "Re-save EMAIL_TO" in said
    assert "recipient(s)" not in said, "the diagnosis is for the refusals a retry cannot fix"


@pytest.mark.parametrize("email_to", [
    "someone.else@example.test",                      # a different address
    "Owner@Example.invalid, someone.else@example.test",  # the right one beside a wrong one
    "owner@example.invalid",                          # already Resend's spelling: nothing to respell
])
def test_only_a_case_only_mismatch_earns_the_second_send(fake_resend, monkeypatch, caplog, email_to):
    """Everything else is refused once and diagnosed, never sent twice: a
    retry cannot fix a different address, and sending an exact match again
    would pay for the same refusal twice."""
    import resend

    monkeypatch.setenv("EMAIL_TO", email_to)
    calls: list[list[str]] = []

    def send(params, options=None):
        calls.append(list(params["to"]))
        raise RuntimeError(_TEST_MODE_REFUSAL)
    monkeypatch.setattr(resend.Emails, "send", send)

    with caplog.at_level(logging.ERROR, logger="src.emailer"), pytest.raises(RuntimeError):
        deliver("subject", "<p>body</p>")

    assert len(calls) == 1, calls
    assert "recipient(s)" in " ".join(r.getMessage() for r in caplog.records)


def test_a_second_refusal_after_the_respelling_is_raised_like_any_other(fake_resend, monkeypatch):
    import resend

    monkeypatch.setenv("EMAIL_TO", "Owner@Example.invalid")
    calls: list[list[str]] = []

    def send(params, options=None):
        calls.append(list(params["to"]))
        raise RuntimeError(_TEST_MODE_REFUSAL)
    monkeypatch.setattr(resend.Emails, "send", send)

    with pytest.raises(RuntimeError):
        deliver("subject", "<p>body</p>")
    assert len(calls) == 2, "one respelling, then no third attempt"


# --- the names that have stopped printing ------------------------------------


def test_the_email_names_what_stopped_printing_and_says_nothing_when_nothing_did(results):
    block = {"after_sessions": 5, "count": 12,
             "names": [{"ticker": "NO<SUCH", "last": None, "sessions_behind": None},
                       {"ticker": "FI", "last": "2025-11-10", "sessions_behind": 213},
                       {"ticker": "B<K", "last": "2026-05-20", "sessions_behind": 76}]}
    html_out = build_html(results, "evening", {**STATS, "stopped_printing": block})
    text = _visible_text(html_out)
    assert ("Not printing: NO<SUCH (no bar at all), FI (since 2025-11-10), B<K (since 2026-05-20) "
            "and 9 more names") in text
    assert "since None" not in text, "a name the feed returned nothing for has no date to print"
    assert "12 names in the symbol file with no bar for more than 5 sessions" in text
    assert "B&lt;K" in html_out, "a ticker is a string the feed sent, and it is escaped"

    quiet = build_html(results, "evening", {**STATS, "stopped_printing": {"after_sessions": 5, "count": 0, "names": []}})
    assert "Not printing" not in quiet
    older = build_html(results, "evening", STATS)
    assert "Not printing" not in older, "a snapshot from before the block existed says nothing, not 0"


# --- what a dead scan had reached, and when a follow-through is being read ---


@pytest.mark.parametrize("coverage,expected", [
    # Every clause, in the shape the Monday-after-a-holiday scan produces.
    ({"requested": 228, "with_bars": 228, "fresh": 0, "session": "2026-09-07",
      "newest_seen": "2026-09-04"},
     "228 asked, 228 answered, none with a bar for 2026-09-07, "
     "the newest bar among the names that missed the session is 2026-09-04"),
    # A partial scan: some names did print for the session.
    ({"requested": 228, "with_bars": 220, "fresh": 30, "session": "2026-09-07"},
     "228 asked, 220 answered, 30 with a bar for 2026-09-07"),
    # HALF-WRITTEN COUNTS PRINT WHAT THEY HAVE. `with_bars` absent is not
    # `with_bars` 0: one is a scan that did not get that far, the other is a
    # scan that asked and heard nothing, and they have different fixes.
    ({"requested": 228}, "228 asked"),
    ({"requested": 228, "with_bars": 0}, "228 asked, 0 answered"),
    # No `requested` at all -- a preflight failure asked nothing.
    ({}, "not recorded"),
    ({"with_bars": 12, "fresh": 0, "session": "2026-09-07"}, "not recorded"),
    # And a shape no writer produces still says nothing rather than crashing.
    ({"requested": "many"}, "not recorded"),
    ({"requested": True}, "not recorded"),
    # The tail clauses, each conditional on its own non-zero count.
    ({"requested": 12, "with_bars": 8, "fresh": 0, "session": "2026-09-07", "dropped": 4},
     "12 asked, 8 answered, none with a bar for 2026-09-07, "
     "4 dropped after their batch failed twice"),
    ({"requested": 12, "with_bars": 8, "fresh": 0, "session": "2026-09-07", "dropped": 1},
     "12 asked, 8 answered, none with a bar for 2026-09-07, "
     "1 dropped after its batch failed twice"),
    ({"requested": 12, "with_bars": 10, "fresh": 0, "session": "2026-09-07", "no_bars": 2,
      "dropped": 0},
     "12 asked, 10 answered, none with a bar for 2026-09-07, "
     "2 answered with no bar at all"),
])
def test_the_coverage_phrase_says_what_the_scan_reached_and_no_more(coverage, expected):
    """src.pipeline.scan_coverage() collects whatever run_scan() had filled in
    when it raised; this renders it. The rule under every case: a count that
    is absent prints as absent, never as 0."""
    assert emailer.coverage_phrase({"coverage": coverage}) == expected


def test_a_failed_run_prints_the_coverage_where_the_universe_goes():
    """And a run that published and then failed to deliver keeps its universe
    label, because it read the session and scanned the names."""
    dead = build_html([], "evening", {"status": "failed", "errors": [],
                                      "session": "2026-09-07",
                                      "coverage": {"requested": 228, "with_bars": 228,
                                                   "fresh": 0, "session": "2026-09-07"}})
    assert "Universe: 228 asked, 228 answered, none with a bar for 2026-09-07" in _visible_text(dead)
    assert "Session it was scanning: 2026-09-07" in _visible_text(dead)

    delivered = build_html([], "evening", {"status": "failed", "errors": [], "published": True,
                                           "session": "2026-09-07", **STATS})
    text = _visible_text(delivered)
    assert "Universe: 230 checked-in US common stocks" in text
    assert "Session scanned: 2026-09-07" in text, "it did scan it"
    assert "no scan was completed" not in text


@pytest.mark.parametrize("stats,clause,phrase", [
    # The morning cron, which both sentences were written for.
    ({}, "at today's open", "before the open"),
    ({"after_the_close": False}, "at today's open", "before the open"),
    # A morning dispatch after the close: the open was hours ago.
    ({"after_the_close": True}, "re-presented after today's close", "after today's close"),
    # An evening dispatch that found its session already published. The
    # dispatch outranks the clock, because it is the fact the reader can act
    # on -- and it has to, since round 10 moved that defence out of the
    # clock-disagreement branch: the click made after the 22:16 cron reaches
    # this pass with the mode and the clock in agreement, which is the second
    # row below.
    ({"dispatch": "evening"}, "re-presented by an evening dispatch",
     "by an evening dispatch that found the session already published"),
    ({"dispatch": "evening", "after_the_close": True},
     "re-presented by an evening dispatch",
     "by an evening dispatch that found the session already published"),
    # THE FOURTH OCCASION. `after_the_close` is False on a Saturday by design
    # -- src.scanner.session_has_closed() ANDs is_trading_weekday() -- so a
    # weekend morning dispatch (morning.yml carries a workflow_dispatch box,
    # and CLAUDE.md records the owner making several) fell into the state
    # written for the 8:30 cron and promised an open there is no open for.
    ({"trading_weekday": False}, "re-presented on a day the market does not open",
     "on a day the market does not open"),
    ({"trading_weekday": False, "after_the_close": False},
     "re-presented on a day the market does not open",
     "on a day the market does not open"),
    # A weekend dispatch that asked for an EVENING run still names the click:
    # that is what the reader did, and it is the fact they can act on.
    ({"trading_weekday": False, "dispatch": "evening"},
     "re-presented by an evening dispatch",
     "by an evening dispatch that found the session already published"),
    # And a caller that does not say keeps the wording it had.
    ({"trading_weekday": True}, "at today's open", "before the open"),
])
def test_a_follow_through_says_when_it_is_being_read(results, stats, clause, phrase):
    """One rule for the heading and the band, so the two cannot drift: the
    page and the email have already produced two vocabularies for one
    mechanism twice in this project, and these two sentences sit an inch
    apart."""
    base = {"session": "2026-09-04", **stats}
    heading = _visible_text(build_html(results, "morning", base))
    assert clause in heading

    banded = _visible_text(build_html(results, "morning",
                                      {**base, "status": "degraded",
                                       "errors": [{"stage": "session", "message": "why"}]}))
    assert f"re-presented {phrase}" in banded


# --- the counts a notice carries are about the names they say they are ------
# Three auditors reproduced the same sentence: "(newest seen 2026-09-03)" was
# appended to whatever coverage clause came last, and src.pipeline's
# scan_coverage() fills `newest_seen` from the STALE names alone. Beside "none
# with a bar for X" it read correctly; beside "5 with a bar for X" it told the
# operator the feed had stopped four days ago on the same line as five names
# printing for the session. The failure notice is what an operator diagnoses a
# feed outage from.


@pytest.mark.parametrize("coverage,expected", [
    # The state every earlier case of this phrase was in: nothing printed.
    ({"requested": 228, "with_bars": 228, "fresh": 0, "session": "2026-09-07",
      "newest_seen": "2026-09-04"},
     "228 asked, 228 answered, none with a bar for 2026-09-07, "
     "the newest bar among the names that missed the session is 2026-09-04"),
    # And the one no case built: a stale MINORITY. The majority-stale
    # StaleDataError branch and any failure after a completed scan reach it.
    ({"requested": 12, "with_bars": 12, "fresh": 5, "session": "2026-09-04",
      "newest_seen": "2026-09-03"},
     "12 asked, 12 answered, 5 with a bar for 2026-09-04, "
     "the newest bar among the names that missed the session is 2026-09-03"),
])
def test_the_newest_bar_is_reported_over_the_names_it_was_measured_over(coverage, expected):
    """One wording for both, because the number is the same number: the newest
    date among the names that did NOT carry the session. Glued to the fresh
    clause it contradicted it on one line."""
    assert emailer.coverage_phrase({"coverage": coverage}) == expected


def test_the_coverage_phrase_is_escaped_once_by_the_line_that_prints_it():
    """Two statements of one rule: coverage_phrase() escaped its two leaves
    and _funnel_line() escapes every finished part again, so a hostile session
    would have reached a reader as the literal &amp;amp;. Inert today --
    src.ledger's iso_date() gives a date or None -- and one rule anyway."""
    hostile = {"requested": 3, "with_bars": 3, "fresh": 0, "session": "A&B<x>",
               "newest_seen": "C&D"}
    html = build_html([], "evening", {"status": "failed", "errors": [],
                                      "coverage": hostile})
    text = _visible_text(html)
    assert "A&B<x>" in text and "C&D" in text
    assert "&amp;" not in text and "&lt;" not in text


def test_a_retry_leaves_the_note_of_a_row_that_had_no_chart_to_drop(fake_resend):
    """RETRY_CHART_NOTE ends "The PNG is on disk with the run's record", and it
    was written over EVERY row -- including a morning row, whose own note
    exists because the PNG on disk records no session and cannot be shown to
    belong to the numbers beside it, and an evening row whose chart never
    rendered. The note replaces a picture that was really being attached."""
    morning_note = pipeline.MORNING_CHART_NOTE
    rows = [make_result("AAA", chart=None, chart_note=morning_note),
            make_result("BBB", chart=None),
            make_result("CCC", chart="/no/such/file.png")]

    send_failure_notice("morning", [{"stage": "email", "message": "429"}], {}, results=rows)

    text = _visible_text(fake_resend.sent[-1]["html"])
    assert morning_note in text, "the morning row keeps the reason it has"
    assert "none was rendered for this candidate" in text, "and so does a failed render"
    assert "The PNG is on disk with the run's record" not in text
    assert "is not there now" in text, "the third row's own reason is untouched too"


def test_a_retry_says_where_the_picture_went_for_a_row_that_had_one(fake_resend, tmp_path):
    """The precondition for the test above: a row whose chart really was going
    to be attached gets the retry's note, and nothing is attached."""
    chart = tmp_path / "AAA.png"
    chart.write_bytes(b"\x89PNG\r\n\x1a\n")
    rows = [make_result("AAA", chart=str(chart))]

    send_failure_notice("evening", [{"stage": "email", "message": "429"}], {}, results=rows)

    sent = fake_resend.sent[-1]
    assert "The PNG is on disk with the run's record" in _visible_text(sent["html"])
    assert sent["attachments"] == []


def test_a_morning_notice_carrying_its_rows_does_not_say_it_never_followed_them():
    """`published` was the only thing that turned the failed relabelling off,
    and only an evening run can carry it -- so the morning retry printed
    "Session it should have followed" one line under a headline saying the
    rows below are the follow-through, with every count beside it real."""
    stats = {"status": "failed", "errors": [{"stage": "email", "message": "429"}],
             "session": "2026-09-04", "bursts": 3, "gated": 3, "reached_send": True}
    text = _visible_text(build_html(results_for("morning"), "morning", stats))

    assert "Following through on the session of: 2026-09-04" in text
    assert "should have followed" not in text


def test_a_run_that_died_after_its_scan_does_not_report_a_scan_it_completed(results):
    """A run that scans, scores and dies in publish() carries every count on
    the report the notice is rendered from, and the notice said "no scan was
    completed", "4% bursts found: not recorded" and "this is a quiet market"."""
    stats = {"status": "failed", "errors": [{"stage": "archive", "message": "RuntimeError: disk full"}],
             "session": "2026-09-04", "scanned": True, "universe": "12 named on the command line (--tickers)",
             "bursts": 12, "gated": 12}
    text = _visible_text(build_html([], "evening", stats))

    assert "no scan was completed" not in text
    assert "Session scanned: 2026-09-04" in text
    assert "4% bursts found: 12" in text
    assert "quiet market" not in text
    assert "cleared the 2LYNCH checklist and this mail carries no rows" in text


def test_a_failed_run_that_never_scanned_still_says_so(results):
    """The precondition: the sentences above are for a run that got past the
    scan, and a preflight failure must keep the ones written for it."""
    text = _visible_text(build_html([], "evening", {
        "status": "failed", "errors": [{"stage": "preflight", "message": "no keys"}]}))

    assert "no scan was completed" in text
    assert "quiet market" not in text, "nothing looked for a burst, so nothing is known"


def test_a_run_that_died_between_the_scan_and_the_counts_keeps_its_coverage():
    """The state between the two the round was written for: the scan finished
    and the run broke before it built a funnel -- in the scoring stage, say.
    The universe cell printed the coverage only while the session was being
    RELABELLED, so turning the relabel off for a completed scan took the
    coverage with it: "Universe: not recorded" over 228 asked and 228 answered,
    which is the sentence the coverage line exists to have ended. The label
    when there is one, the coverage when there is not.

    And it must not claim a market either: nothing counted a burst here, so
    "this is a quiet market" is a statement about a scan whose bursts were
    never counted."""
    stats = {"status": "failed", "errors": [{"stage": "score", "message": "RuntimeError: boom"}],
             "session": "2026-09-04", "scanned": True,
             "coverage": {"requested": 228, "with_bars": 228, "fresh": 228,
                          "session": "2026-09-04"}}
    text = _visible_text(build_html([], "evening", stats))

    assert "Universe: 228 asked, 228 answered, 228 with a bar for 2026-09-04" in text
    assert "Session scanned: 2026-09-04" in text, "it did scan it"
    assert "quiet market" not in text
    assert "See the failures listed above" in text
