"""
Layer 6 — Email delivery via Resend (https://resend.com).

Builds an HTML table of the top candidates and sends it through Resend's API
using an API key — no OAuth, no refresh tokens, no consent screens. The
evening email carries the chart PNGs the same run just rendered, inline; the
morning email carries none and prints why in the cell where the picture would
be, because the only image it could reach is one no file says the session of
(src.pipeline's CHARTS_DIR has the whole argument).

THE EMAIL IS THE MONITOR. GitHub Actions is checked when something is already
suspected; this arrives every evening whether or not anyone is watching. So a
run that could not do its job must not produce the same cheerful table as one
that could: `scan_stats["errors"]` — the `{stage, message}` list src.pipeline
builds, and the shape docs/data.json's `run.errors` takes — puts a red band at
the top of the body and a word in the subject line. An operator can tell a
degraded run from a clean one in the inbox, without opening a log.

Two things step 10 added, for the same reason. `scan_stats["session"]` names
the session that was actually read, in the subject and above the table: the run
type was a label over a session the wall clock picked, so "Evening candidates"
could be yesterday's market with nothing in the inbox showing it. And each row
carries its streak — see _streak_note() — because a name that burst on Monday
and again on Tuesday used to arrive as two brand-new ideas. A streak whose
`day` is null says so in words rather than rendering nothing: unknown is not
day 1, and it was the one state no surface showed.

THE MODE CHANGES WHAT IS TRUE, so every sentence that could be false in one of
them branches on it. _funnel_line() and the empty-shortlist cell already did;
_headline() and _title() did not, and each said something false in every
degraded morning email — "the list below is incomplete, do not read it as a
full scan of the universe" over last night's complete shortlist, under a
heading promising a watchlist for TODAY over rows that could be fifteen
sessions old. Both branch now, and the heading carries the session the rows
came from so it cannot drift from them.

AND HOW STALE IS NOT THE SAME AS DEGRADED. `scan_stats["stale_sessions"]` is
how many sessions behind the snapshot is; src.pipeline sets it and
stale_snapshot_note() holds the reasoning. At two or more no market closure can
explain the gap, so _prefix() escalates the subject and _headline() the band —
the three emails rendered at 1, 3 and 15 sessions used to be byte-identical but
for a date, and a phone shows the subject and nothing else.

Environment variables:

  RESEND_API_KEY   — from https://resend.com/api-keys
  RESEND_FROM      — sender address (e.g. "onboarding@resend.dev" for
                      testing, or an address on your verified domain)
  EMAIL_TO         — recipient address(es), comma-separated

Free tier: 3,000 emails/month, 100/day.

Install:
    pip install resend
"""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path

import resend

log = logging.getLogger(__name__)

#: Environment this layer cannot run without, collected by src.pipeline's
#: preflight. Both were read with os.environ[...] on the LAST line of a run
#: that had already paid for the scan and every Claude call; the preflight
#: reads them before the first one. Empty counts as missing, which the direct
#: subscript never did: an unset GitHub secret arrives as '', so RESEND_API_KEY
#: sailed past that check and failed as a 401 from Resend instead.
REQUIRED_ENV: tuple[str, ...] = ("RESEND_API_KEY", "EMAIL_TO")

#: `scan_stats["status"]`, and what each one does to the subject line.
STATUS_PREFIXES = {"ok": "", "degraded": "DEGRADED — ", "failed": "FAILED — "}


def _prefix(scan_stats: dict) -> str:
    """The word before the label — and, for a stale follow-through, how stale.

    Every staleness used to read DEGRADED. Rendered at one, three and fifteen
    sessions the three emails were byte-identical but for a date, so a screener
    dead for three weeks arrived in an inbox looking exactly like the Tuesday
    after Presidents' Day. `stale_sessions` is set by src.pipeline only when
    nothing has published for the session this run expected, and at two or more
    the holiday reading is dead on arithmetic (see stale_snapshot_note): the
    subject says so, because triage on a phone never gets past this line.

    FAILED still outranks it. A run with no rows at all is the worse state, and
    a stale count would be describing rows that are not there.
    """
    status = scan_stats.get("status", "ok")
    stale = scan_stats.get("stale_sessions") or 0
    if status == "degraded" and stale >= 2:
        return f"NOTHING PUBLISHED IN {_plural(stale, 'SESSION').upper()} — "
    return STATUS_PREFIXES.get(status, "")


#: The only stage whose problems make the shortlist SHORTER than the session
#: deserved. Everything else -- a chart that would not render, a history that
#: could not be read, a clock disagreement, a forward-return backfill, even
#: Claude refusing every candidate -- leaves the list itself whole and spoils
#: something about it. Saying "incomplete" over a complete 3-of-3 scan spends
#: the reader's trust on a true problem described falsely, and the next real
#: one is read past.
SHORTENING_STAGES = frozenset({"scan"})


def _shortened(scan_stats: dict) -> bool:
    """Did anything actually cut the list, as opposed to spoiling it?"""
    return any(
        (e.get("stage") if isinstance(e, dict) else None) in SHORTENING_STAGES
        for e in (scan_stats.get("errors") or [])
    )


def _headline(scan_stats: dict, run_type: str, results: list[dict] | None = None) -> str:
    """The one sentence in the band a phone skimmer actually reads.

    It was written for the evening run and keyed on nothing but `failed`, while
    _funnel_line(), the empty-shortlist cell and (since step 10) the whole
    pipeline all branch on the mode. So the most prominent sentence in a
    degraded MORNING email said "the list below is incomplete, do not read it
    as a full scan of the universe" over last night's COMPLETE shortlist, in a
    pass that scans no universe at all — and its failed twin said "no scan was
    completed", which is true of every morning run by design. Two of the three
    lines a skimmer reads were false for the state the band exists to flag.

    A stale morning run gets a third headline, because "degraded" is the same
    word for "one session late, possibly a holiday" and "nothing has published
    for three weeks". See src.pipeline's stale_snapshot_note() for why the
    second is knowable without a holiday calendar.

    Two more things it has to know, both found by rendering it rather than
    reading it. WHETHER THERE ARE ROWS: every sentence here said "the rows
    below" or "the list below", and the morning run that refuses the fixture
    says it directly above `No shortlist.` -- which is not a corner case but
    the guaranteed state of the first production morning run, and of every one
    until evening.yml's commit-back succeeds. AND WHICH STAGE BROKE: only a
    `scan` problem shortens the list (see SHORTENING_STAGES); a chart that
    failed to render printed "the list below is incomplete" over a complete
    scan of every symbol asked for. _title() already branches on the first of
    these; the band, which sits above it and is read first, did not.
    """
    morning = run_type == "morning"
    rows = bool(results) if results is not None else True
    if scan_stats.get("status") == "failed":
        return ("THIS RUN FAILED — there is no watchlist below. A morning run "
                "re-presents what the last evening run published, and this pass "
                "could not get that far."
                if morning else
                "THIS RUN FAILED — there is no shortlist below, and no scan was "
                "completed.")
    stale = scan_stats.get("stale_sessions") or 0
    if morning and stale >= 2:
        # "no market HOLIDAY is that long" and not "closure": none of the
        # market's scheduled holidays are adjacent, so this is true at every
        # gap of two or more, while unscheduled closures have run to
        # consecutive sessions and the band below names them.
        published = scan_stats.get("session") or "an older session"
        where = (f"the rows below are {published}'s" if rows
                 else f"the newest run anything published is {published}'s")
        return (f"NOTHING HAS PUBLISHED FOR {_plural(stale, 'SESSION').upper()} — {where}, "
                "and no market holiday is that long. The evening run has stopped "
                "publishing.")
    if morning:
        if not rows:
            return ("THIS FOLLOW-THROUGH IS DEGRADED — there is no watchlist below. A "
                    "morning run re-presents what the last evening run published, and "
                    "there was nothing it could show.")
        return ("THIS FOLLOW-THROUGH IS DEGRADED — the rows below are an earlier evening "
                "run's shortlist, re-presented before the open. This pass scanned "
                "nothing itself, so read every reason below before acting on them.")
    if not rows:
        return ("THIS RUN WAS DEGRADED — there is no shortlist below, and the run that "
                "produced none is not one to trust for that.")
    if _shortened(scan_stats):
        return ("THIS RUN WAS DEGRADED — the list below is incomplete. Do not read it as "
                "a full scan of the universe.")
    return ("THIS RUN WAS DEGRADED — the scan below is complete, but something in the run "
            "that judged it was not. Read every reason below before acting on the rows.")


def _banner(scan_stats: dict, run_type: str = "evening",
            results: list[dict] | None = None) -> str:
    """The red band. Empty string when the run had nothing to report.

    First thing in the body, above the title, because the failure mode this
    exists for is a person skimming a familiar-looking table on a phone. The
    problems are printed in full rather than summarised into a status word:
    "138 of 230 symbols had no bar" tells an operator where to look, "degraded"
    does not. Which sentence leads it is _headline()'s decision, and it depends
    on the mode: this function's own docstring argued for a reader skimming a
    familiar-looking table, and then said the wrong thing to every one of them
    who opened a morning email.
    """
    errors = scan_stats.get("errors") or []
    if not errors:
        return ""
    headline = _headline(scan_stats, run_type, results)
    items = "".join(
        f'<li style="margin:2px 0;"><b>{e.get("stage", "?")}</b>: {e.get("message", "")}</li>'
        for e in errors
    )
    return (
        '<div style="border-left:6px solid #c0392b;background:#fdf3f2;'
        'padding:12px 16px;margin:0 0 18px;">'
        f'<div style="color:#a5281b;font-weight:bold;font-size:15px;">{headline}</div>'
        f'<ul style="margin:8px 0 0;padding-left:20px;color:#7b2018;font-size:13px;">{items}</ul>'
        "</div>"
    )


def _provenance_line(scan_stats: dict) -> str:
    """"Scored by Claude: 8 of 12" — or nothing, when the caller did not say.

    The per-row `verdict: unscored` already tells the truth about one candidate.
    This is the count, next to the other funnel numbers, so a reader sees how
    much of the shortlist nobody looked at without reading every row.
    """
    scored_by = scan_stats.get("scored_by") or {}
    claude, fallback = scored_by.get("claude"), scored_by.get("fallback")
    if claude is None or fallback is None:
        return ""
    total = claude + fallback
    if not total:
        return ""
    colour = "#666" if not fallback else "#a5281b"
    return (f' &nbsp;|&nbsp; <span style="color:{colour};">Scored by Claude: '
            f"{claude} of {total}</span>")


#: What a streak's `unknown_reason` says to a reader when the record can say
#: nothing narrower. `day: null` is the state this whole mechanism cares most
#: about — UNKNOWN, which is not day 1 — and it used to render here as nothing
#: at all, so a run that could not read its history produced rows a reader
#: could not tell from first sightings. The dashboard says the same words for
#: the same reasons; if you change one, change docs/index.html's streakText().
#:
#: `no_history` says how it RESOLVES, because that is the state a fresh install
#: is permanently in until the first commit-back succeeds: every row on the
#: page and in the email says this, and the only thing that used to suggest it
#: was temporary was the word "yet".
STREAK_UNKNOWN = {
    "no_history": "streak unknown — no history has been recorded yet; a day number "
                  "appears once the record reaches back past the burst",
    "history_undated": "streak unknown — the history holds runs, but none of them "
                       "carry a date to count from",
    "history_unreadable": "streak unknown — the run could not read its history",
    "window_not_covered": "streak unknown — the history does not reach back this far",
}
UNKNOWN_FALLBACK = "streak unknown — no reason was recorded"
#: A row with no `streak` field at all, which is not the same as a block that
#: could not answer: nothing computed one. docs/index.html's streakText() says
#: this in the same words for the same row.
NO_STREAK_BLOCK = "streak unknown — this run recorded none"

#: What happened to this name the LAST time it was seen. "not scored" used to
#: cover both of these and they are close to opposites: score_cap means the
#: checklist passed it and better names filled the call budget, lynch_gate
#: means the pipeline looked at it and threw it out at the quality gate. Read
#: beside "day 2 of this setup", which looks like accumulating confirmation,
#: the ambiguity is worth money.
#:
#: `score_cap` used to name "the scoring cap", which this email never explains
#: and the dashboard called "the call cap" two words away. One mechanism, one
#: name, and the name is the mechanism itself: a run sends a fixed number of
#: candidates to Claude (src.pipeline's MAX_TO_SCORE) and the ones that rank
#: below it are not scored. docs/index.html uses this map for its streak line
#: AND for the gated table's "why" cell, which is where the second name was.
LAST_OUTCOME = {
    "scored": None,  # rendered with the score itself, below
    "lynch_gate": "rejected at the 2LYNCH gate",
    "score_cap": "passed the gate, but the run had already sent its limit of "
                 "candidates to Claude",
}


def _streak_of(row: dict) -> dict:
    """The row's streak block, or {} for anything that is not one.

    A morning row comes off disk (docs/data.json read back), so this is not a
    hypothetical shape: a truncated or hand-edited snapshot must not take the
    8:30 email down with it. The email is the monitor, and an email that does
    not arrive is the failure step 5 exists to end. Anything unreadable renders
    as an unknown streak, which is exactly what it is.
    """
    streak = row.get("streak")
    return streak if isinstance(streak, dict) else {}


def _last_appearance(streak: dict) -> str:
    """What was done with this name the last time it appeared.

    `last_outcome` is the authority. A row from before that field existed
    carries only `last_score`, so a score present still reads as scored and a
    score absent says exactly that and no more — "not scored then", the old
    wording for every case, read as an absence of judgement when the truth was
    usually a rejection.

    A number is required for the scored sentence, not just the word: a row
    marked "scored" with no score in it would otherwise print "scored None/10",
    and the honest answer to a missing number is that there is no number.
    """
    outcome, score = streak.get("last_outcome"), streak.get("last_score")
    if score is not None and outcome in (None, "scored"):
        return f"scored {score}/10 {streak.get('last_verdict') or ''}".rstrip()
    return LAST_OUTCOME.get(outcome) or "no score was recorded then"


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def _no_day_note(streak: dict) -> str:
    """What to say when `day` is null — the narrowest true answer, not "unknown".

    A day number needs the record to reach back past where the chain starts
    (src.ledger's _why_no_day), and an UNBROKEN chain pins its own start at the
    oldest run in the file, so the window is never covered: a name bursting on
    every one of the eight sessions the ledger holds got "streak unknown", while
    a name that took a week off and burst twice got "day 2 of this setup". The
    arithmetic is right — you cannot prove a chain did not start before your
    record did — but "unknown" was the wrong thing to SAY, because the record
    already answers a narrower question truthfully: how many earlier sessions it
    holds a burst for, and how far back it goes at all.

    So the span of the record is reported — src.ledger's `history_from` and
    `history_sessions`, both facts about the FILE — beside how many of those
    sessions this name burst on, and the only claim dropped is the one they are
    short of: where the setup began. A block written before those fields
    existed simply falls back to the flat sentence.
    """
    reason, begins = streak.get("unknown_reason"), streak.get("history_from")
    sessions, seen = streak.get("history_sessions") or 0, streak.get("seen_before") or 0
    if reason == "window_not_covered" and begins and sessions:
        span = f"the {_plural(sessions, 'session')} in the record, which begins {begins}"
        if seen:
            return (f"day unknown — burst on {seen} of {span}; this setup may have "
                    f"started before it")
        return (f"day unknown — no earlier burst in {span}; an earlier one would fall "
                f"outside it")
    return STREAK_UNKNOWN.get(reason, UNKNOWN_FALLBACK)


def _streak_note(row: dict) -> str:
    """"day 3 of this setup, since 2026-08-27 · last seen…", under the ticker.

    THE thing step 10 added to this email. A name that burst on Monday and
    again on Tuesday used to arrive as a brand-new idea both nights, with
    nothing saying the reader had already looked at it and passed. src.ledger's
    MAX_STREAK_GAP_SESSIONS holds what "the same setup" means.

    A null `day` is NOT day 1 and is no longer silent. It means the day number
    is not knowable — see _no_day_note() for how much else still is — and
    saying nothing left the two surfaces that render a streak disagreeing about
    the one state that matters most. It never becomes "new setup": that would
    turn a file error into a claim about the market.
    """
    if not isinstance(row.get("streak"), dict):
        return _streak_span(NO_STREAK_BLOCK, "#666")
    streak = _streak_of(row)
    day = streak.get("day")
    if day is None:
        text = _no_day_note(streak)
        # Earlier bursts on record are the same news as day > 1 — the name has
        # run before — so they get the same colour. A grey line under a name
        # the record has eight bursts for reads as an absence of history.
        colour = "#a5281b" if streak.get("seen_before") else "#666"
    elif day > 1:
        text = f"day {day} of this setup, since {streak.get('first_seen')}"
        colour = "#a5281b"
    else:
        text = "day 1 — new setup"
        colour = "#666"
    if streak.get("last_seen"):
        text += f" · last seen {streak['last_seen']}, {_last_appearance(streak)}"
    return _streak_span(text, colour)


def _streak_span(text: str, colour: str) -> str:
    return f'<br><span style="color:{colour};font-size:12px;">{text}</span>'


def _streak_footnote(results: list[dict]) -> str:
    """What "day N" counts, said once under the table.

    A streak counts every session the scan found a burst on, INCLUDING the
    ones the 2LYNCH gate rejected — the right call, because the setup was
    running whether or not the checklist let it through to a score, and one no
    reader can infer from "day 2 of this setup", which reads as two nights of
    agreement. Disclosed here rather than in every row, and only when a row
    actually makes a count that needs it.

    That is TWO shapes of row, not one. "day 3 of this setup" is the obvious
    one; "burst on 8 of the 8 sessions in the record" is the other, and it is
    the same count over the same bursts — an unknown `day` withholds the day
    number, not the appearances behind it.
    """
    counted = [_streak_of(row) for row in results]
    if not any((s.get("day") or 0) > 1
               or (s.get("day") is None and (s.get("seen_before") or 0) > 0)
               for s in counted):
        return ""
    # Set as a note rather than as fine print. It was 11px grey at the foot of
    # a seven-column table, under rows whose own streak line is red and 12px:
    # the disclosure was quieter than the claim it qualifies.
    return (
        '<p style="border-left:4px solid #ddd;padding:6px 0 6px 10px;color:#555;'
        'font-size:12px;margin:10px 0 0;max-width:70ch;">'
        "&ldquo;day N of this setup&rdquo;, and the earlier bursts a row with no day "
        "number counts, are every session the scan found a burst on for that name — "
        "including the ones the 2LYNCH gate rejected. Neither is N nights of "
        "confirmation."
        "</p>"
    )


def _funnel_line(results: list[dict], run_type: str, scan_stats: dict) -> str:
    """The counts under the title — and, since step 10, the SESSION.

    Naming the session is what stops a mode from lying. The clock decides
    which session gets scanned and the mode was only ever a label on top of
    it, so an evening run started before the close mailed yesterday's market
    as tonight's and no one reading this could tell. Now the run says which
    session it read, in the artifact a person actually opens.

    A morning run counts different things because it did different things: it
    scanned no universe at all, so it reports the run it is following through
    on rather than a funnel it did not walk.

    A FAILED run relabels the session, because it did not read it. The failure
    notice knows which session it was going for — the clock says so even when
    the run died on its first line — and printing that under "Session scanned"
    would be the same silent relabelling the session was added here to end.
    """
    session = scan_stats.get("session") or "not recorded"
    failed = scan_stats.get("status") == "failed"
    unknown = "not recorded"
    if run_type == "morning":
        parts = [("Session it should have followed" if failed
                  else "Following through on the session of", session),
                 ("4% bursts that session", scan_stats.get("bursts", unknown)),
                 ("Passed 2LYNCH gate", scan_stats.get("gated", unknown)),
                 ("Watching", len(results))]
    else:
        parts = [("Session it was scanning" if failed else "Session scanned", session),
                 ("Universe", scan_stats.get("universe", unknown)),
                 ("4% bursts found", scan_stats.get("bursts", unknown)),
                 ("Passed 2LYNCH gate", scan_stats.get("gated", unknown)),
                 ("Shortlisted", len(results))]
    return " &nbsp;|&nbsp;\n      ".join(f"{label}: {value}" for label, value in parts)


def _chart_file(row: dict) -> Path | None:
    """The chart PNG this row can really attach, or None. One rule, two callers.

    _build_attachments() must not attach a file that is not there, and
    build_html() must not print an <img> for an attachment that was never
    made. They used to answer that separately — the HTML emitted
    `cid:chart_TICKER` unconditionally — so a candidate whose chart failed to
    render showed a broken-image icon where the picture belonged, which says
    nothing about why. Since step 10 that is every morning row as well, by
    design: see src.pipeline's MORNING_CHART_NOTE.
    """
    chart = row.get("chart")
    if not chart:
        return None
    path = Path(chart)
    return path if path.exists() else None


#: Printed where the picture would be when the row names no chart at all and
#: the caller did not say why. A morning row carries its own reason.
NO_CHART = "no chart — none was rendered for this candidate"


def _no_chart_note(row: dict) -> str:
    """Why this cell holds words instead of a picture — checked, not assumed.

    NO_CHART used to cover both branches of _chart_file(), so a chart that
    rendered and was then deleted before the email went out reported "none was
    rendered for this candidate" — a cause nothing had looked at. The row says
    which of the two it is: `chart` is null when the render failed (src.pipeline
    records the exception separately), and a path that is not on disk any more
    is a different fact with a different fix.
    """
    if row.get("chart_note"):
        return row["chart_note"]
    if row.get("chart"):
        return (f'no chart — one was rendered for this candidate, but {row["chart"]} '
                f"is not there now, so there was nothing to attach")
    return NO_CHART


def _chart_cell(row: dict) -> str:
    if _chart_file(row):
        return (f'<img src="cid:chart_{row["ticker"]}" width="280" '
                f'alt="{row["ticker"]} chart">')
    return (f'<span style="color:#666;font-size:12px;">'
            f'{_no_chart_note(row)}</span>')


def _close_cell(row: dict, scan_stats: dict) -> str:
    """"$44.8 (close 2026-08-31)" — the price, and which session printed it.

    The session is in the subject line and the funnel line, so it was
    disclosed; it was not disclosed on the number the eye lands on. Under a
    heading that reads "follow-through watchlist for TODAY", an unlabelled
    price is read as this morning's, and it is last night's close.
    """
    session = scan_stats.get("session")
    stamped = f" (close {session})" if session else ""
    return f'<span style="color:#666;font-size:12px;">${row["close"]}{stamped}</span>'


def _title(run_type: str, scan_stats: dict, results: list[dict]) -> str:
    """The H2, which must not promise a day the rows are not from.

    It read "follow-through watchlist for TODAY" over every morning row,
    unconditionally — including a snapshot fifteen sessions old, where TODAY is
    the one word in it that is false. The session the rows ARE from is what
    goes in, so the heading cannot drift from them however stale they get;
    "today" survives only as the hour the reader is looking, which is true
    whatever the snapshot says.

    The word "shortlist" needs rows under it. A failed morning run still knows
    the session it was going for (src.pipeline's attempted_session), and naming
    a shortlist over the empty-table cell would be the same promise from the
    other direction.
    """
    if run_type != "morning":
        return "Momentum Bursts — candidates for TOMORROW"
    session = scan_stats.get("session")
    if not session:
        return "Momentum Bursts — follow-through, with nothing to follow"
    if not results:
        return f"Momentum Bursts — following through on {session}, at today&rsquo;s open"
    return f"Momentum Bursts — {session}&rsquo;s shortlist, at today&rsquo;s open"


def build_html(results: list[dict], run_type: str, scan_stats: dict) -> str:
    title = _title(run_type, scan_stats, results)
    rows = ""
    for i, r in enumerate(results, 1):
        detail = "<br>".join(r["lynch_detail"])
        rows += f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #ddd;"><b>{i}. {r['ticker']}</b><br>
              {_close_cell(r, scan_stats)}{_streak_note(r)}</td>
          <td style="padding:8px;border-bottom:1px solid #ddd;">+{r['gain_pct']}%</td>
          <td style="padding:8px;border-bottom:1px solid #ddd;">{r['volume_ratio']}x</td>
          <td style="padding:8px;border-bottom:1px solid #ddd;">
              <b>{r['lynch']}</b>
              <details><summary style="cursor:pointer;color:#0066cc;font-size:12px;">detail</summary>
              <div style="font-size:11px;color:#555;font-family:monospace;">{detail}</div></details></td>
          <td style="padding:8px;border-bottom:1px solid #ddd;">{r['reason']}<br>
              <span style="color:#a33;font-size:12px;">Risk: {r['key_risk']}</span></td>
          <td style="padding:8px;border-bottom:1px solid #ddd;text-align:center;">
              <b style="font-size:18px;">{r['score']}</b>/10<br>
              <span style="font-size:12px;">{r['verdict']}</span></td>
          <td style="padding:8px;border-bottom:1px solid #ddd;">
              {_chart_cell(r)}</td>
        </tr>"""

    if not results:
        # An empty shortlist means two completely different things, and the
        # cell used to state the innocent one either way. Three things, since
        # step 10: a morning pass has nothing of its own to find, so "no
        # candidates passed the quality gate" would be a sentence about a scan
        # that never ran.
        if scan_stats.get("errors"):
            empty = ("No shortlist. See the failures listed above — this is not "
                     "a statement about the market.")
        elif run_type == "morning":
            empty = "The run this follows through on scored no candidates."
        else:
            empty = "No candidates passed the quality gate today."
        rows = f'<tr><td colspan="7" style="padding:16px;color:#666;">{empty}</td></tr>'


    return f"""
    <html><body style="font-family:Arial,Helvetica,sans-serif;color:#222;">
    {_banner(scan_stats, run_type, results)}
    <h2 style="margin-bottom:4px;">{title}</h2>
    <p style="color:#666;margin-top:0;">
      {_funnel_line(results, run_type, scan_stats)}{_provenance_line(scan_stats)}
    </p>
    <table style="border-collapse:collapse;width:100%;max-width:1100px;">
      <tr style="background:#1a1a2e;color:#fff;text-align:left;">
        <th style="padding:8px;">Ticker</th><th style="padding:8px;">Gain</th>
        <th style="padding:8px;">Vol ratio</th><th style="padding:8px;">2LYNCH</th>
        <th style="padding:8px;">Claude's take</th><th style="padding:8px;">Score</th>
        <th style="padding:8px;">Chart</th>
      </tr>
      {rows}
    </table>
    {_streak_footnote(results)}
    <p style="color:#999;font-size:11px;margin-top:16px;">
      Automated screening output for human review — not trading advice.
      Verify charts and news before acting.</p>
    </body></html>"""


def _build_attachments(results: list[dict]) -> list[dict]:
    """Attach chart PNGs inline, referenced via cid:chart_<ticker> in the HTML.

    Exactly the rows _chart_cell() drew an <img> for: the same _chart_file()
    decides both, so the body can never reference an attachment that is not
    in this list.
    """
    attachments = []
    for r in results:
        chart = _chart_file(r)
        if chart is not None:
            attachments.append(
                {
                    "filename": f"{r['ticker']}.png",
                    "content": base64.b64encode(chart.read_bytes()).decode(),
                    "content_id": f"chart_{r['ticker']}",
                }
            )
    return attachments


def subject_for(results: list[dict], run_type: str, scan_stats: dict) -> str:
    """The one line that shows in a notification, so the status goes in it.

    And, since step 10, the session. The mode was a label over a session the
    wall clock picked, so "Evening candidates" could be yesterday's market and
    "Morning watchlist" could be a day that had already closed — neither
    visible from the inbox. Naming the session makes the mode unable to lie
    even when the clock and the mode disagree, which is the cheapest half of
    that fix and the only half a phone shows.

    Status and session both come before the ticker list: a phone truncates the
    end, so what a reader must not miss goes first — and _prefix() is why the
    word there escalates rather than reading DEGRADED for both a one-session
    gap and a screener that has been dead for three weeks.
    """
    label = "Morning follow-through" if run_type == "morning" else "Evening candidates"
    prefix = _prefix(scan_stats)
    session = scan_stats.get("session")
    dated = f"{label} {session}" if session else label
    top = ", ".join(r["ticker"] for r in results) or "none"
    return f"[4% Burst] {prefix}{dated}: {top}"


def _required(name: str) -> str:
    """An env var that must be present AND non-empty."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise KeyError(
            f"{name} is unset or empty, so this run cannot deliver its email. "
            "src.pipeline's preflight checks this before the scan spends "
            "anything; reaching it here means send_email() was called directly."
        )
    return value


def send_email(results: list[dict], run_type: str, scan_stats: dict) -> None:
    to = [addr.strip() for addr in _required("EMAIL_TO").split(",")]
    sender = os.environ.get("RESEND_FROM", "onboarding@resend.dev")

    resend.api_key = _required("RESEND_API_KEY")

    params = {
        "from": sender,
        "to": to,
        "subject": subject_for(results, run_type, scan_stats),
        "html": build_html(results, run_type, scan_stats),
        "attachments": _build_attachments(results),
    }

    response = resend.Emails.send(params)

    # Log the count, not the addresses. EMAIL_TO is a repository secret, and
    # Actions masks only exact occurrences of it. A single-recipient value
    # still matches and is masked, but split() breaks the contiguous string
    # for multi-recipient values, so those printed in plaintext to the run log.
    log.info("Email sent via Resend to %d recipient(s) (%d candidates), id=%s",
              len(to), len(results), response.get("id"))


def send_failure_notice(run_type: str, errors: list[dict], scan_stats: dict | None = None) -> None:
    """Mail the fact that there is nothing to mail.

    A run that dies mid-scan sends nothing at all today, and nothing looks
    exactly like a weekend. The screener could be dead for a fortnight before
    anyone opened the Actions tab. This is the same email with no rows, a
    FAILED subject and the exception in the band — deliberately the same
    artifact, so the daily habit of reading it is the monitor.

    Best effort by construction: the caller is already handling a failure, and
    a second one here must not replace the first in the log.
    """
    stats = dict(scan_stats or {})
    stats.update({"status": "failed", "errors": errors})
    send_email([], run_type, stats)
