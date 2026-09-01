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


def _banner(scan_stats: dict) -> str:
    """The red band. Empty string when the run had nothing to report.

    First thing in the body, above the title, because the failure mode this
    exists for is a person skimming a familiar-looking table on a phone. The
    problems are printed in full rather than summarised into a status word:
    "138 of 230 symbols had no bar" tells an operator where to look, "degraded"
    does not.
    """
    errors = scan_stats.get("errors") or []
    if not errors:
        return ""
    failed = scan_stats.get("status") == "failed"
    headline = (
        "THIS RUN FAILED — there is no shortlist below, and no scan was completed."
        if failed else
        "THIS RUN WAS DEGRADED — the list below is incomplete. Do not read it as "
        "a full scan of the universe."
    )
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


#: What a streak's `unknown_reason` says to a reader. `day: null` is the state
#: this whole mechanism cares most about — UNKNOWN, which is not day 1 — and
#: it used to render here as nothing at all, so a run that could not read its
#: history produced rows a reader could not tell from first sightings. The
#: dashboard says the same words for the same reasons; if you change one,
#: change docs/index.html's streakText().
STREAK_UNKNOWN = {
    "no_history": "streak unknown — no history has been recorded yet",
    "history_unreadable": "streak unknown — the run could not read its history",
    "window_not_covered": "streak unknown — the history does not reach back this far",
}
UNKNOWN_FALLBACK = "streak unknown — no reason was recorded"

#: What happened to this name the LAST time it was seen. "not scored" used to
#: cover both of these and they are close to opposites: score_cap means the
#: checklist passed it and better names filled the call budget, lynch_gate
#: means the pipeline looked at it and threw it out at the quality gate. Read
#: beside "day 2 of this setup", which looks like accumulating confirmation,
#: the ambiguity is worth money.
LAST_OUTCOME = {
    "scored": None,  # rendered with the score itself, below
    "lynch_gate": "rejected at the 2LYNCH gate",
    "score_cap": "passed the gate, but the scoring cap was already full",
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


def _streak_note(row: dict) -> str:
    """"day 3 of this setup, since 2026-08-27 · last seen…", under the ticker.

    THE thing step 10 added to this email. A name that burst on Monday and
    again on Tuesday used to arrive as a brand-new idea both nights, with
    nothing saying the reader had already looked at it and passed. src.ledger's
    MAX_STREAK_GAP_SESSIONS holds what "the same setup" means.

    A null `day` is NOT day 1 and is no longer silent. It means nothing is
    known — the history could not be read, or does not reach this far back —
    and saying nothing left the two surfaces that render a streak disagreeing
    about the one state that matters most. It never becomes "new setup":
    that would turn a file error into a claim about the market.
    """
    streak = _streak_of(row)
    day = streak.get("day")
    if day is None:
        text = STREAK_UNKNOWN.get(streak.get("unknown_reason"), UNKNOWN_FALLBACK)
        colour = "#666"
    elif day > 1:
        text = f"day {day} of this setup, since {streak.get('first_seen')}"
        colour = "#a5281b"
    else:
        text = "day 1 — new setup"
        colour = "#666"
    if streak.get("last_seen"):
        text += f" · last seen {streak['last_seen']}, {_last_appearance(streak)}"
    return f'<br><span style="color:{colour};font-size:12px;">{text}</span>'


def _streak_footnote(results: list[dict]) -> str:
    """What "day N" counts, said once under the table.

    A streak counts every session the scan found a burst on, INCLUDING the
    ones the 2LYNCH gate rejected — the right call, because the setup was
    running whether or not the checklist let it through to a score, and one no
    reader can infer from "day 2 of this setup", which reads as two nights of
    agreement. Disclosed here rather than in every row, and only when a row
    actually shows a multi-day streak.
    """
    days = [_streak_of(row).get("day") for row in results]
    if not any((day or 0) > 1 for day in days):
        return ""
    return (
        '<p style="color:#666;font-size:11px;margin:8px 0 0;">'
        "&ldquo;day N of this setup&rdquo; counts every session the scan found a burst "
        "on for that name, including bursts the 2LYNCH gate rejected. It is not N "
        "nights of confirmation."
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
    """
    session = scan_stats.get("session") or "not recorded"
    if run_type == "morning":
        parts = [("Following through on the session of", session),
                 ("4% bursts that session", scan_stats.get("bursts", "?")),
                 ("Passed 2LYNCH gate", scan_stats.get("gated", "?")),
                 ("Watching", len(results))]
    else:
        parts = [("Session scanned", session),
                 ("Universe", scan_stats.get("universe", "?")),
                 ("4% bursts found", scan_stats.get("bursts", "?")),
                 ("Passed 2LYNCH gate", scan_stats.get("gated", "?")),
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


#: Printed where the picture would be when there is no attachable PNG and the
#: caller did not say why. A morning row carries its own reason.
NO_CHART = "no chart — none was rendered for this candidate"


def _chart_cell(row: dict) -> str:
    if _chart_file(row):
        return (f'<img src="cid:chart_{row["ticker"]}" width="280" '
                f'alt="{row["ticker"]} chart">')
    return (f'<span style="color:#666;font-size:12px;">'
            f'{row.get("chart_note") or NO_CHART}</span>')


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


def build_html(results: list[dict], run_type: str, scan_stats: dict) -> str:
    title = (
        "Momentum Bursts — follow-through watchlist for TODAY"
        if run_type == "morning"
        else "Momentum Bursts — candidates for TOMORROW"
    )
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
    {_banner(scan_stats)}
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
    end, so what a reader must not miss goes first.
    """
    label = "Morning follow-through" if run_type == "morning" else "Evening candidates"
    prefix = STATUS_PREFIXES.get(scan_stats.get("status", "ok"), "")
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
