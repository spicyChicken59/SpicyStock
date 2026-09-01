"""
Layer 6 — Email delivery via Resend (https://resend.com).

Builds an HTML table of the top candidates (with inline chart thumbnails)
and sends it through Resend's API using an API key — no OAuth, no refresh
tokens, no consent screens.

THE EMAIL IS THE MONITOR. GitHub Actions is checked when something is already
suspected; this arrives every evening whether or not anyone is watching. So a
run that could not do its job must not produce the same cheerful table as one
that could: `scan_stats["errors"]` — the `{stage, message}` list src.pipeline
builds, and the shape docs/data.json's `run.errors` takes — puts a red band at
the top of the body and a word in the subject line. An operator can tell a
degraded run from a clean one in the inbox, without opening a log.

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
              <span style="color:#666;font-size:12px;">${r['close']}</span></td>
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
              <img src="cid:chart_{r['ticker']}" width="280" alt="{r['ticker']} chart"></td>
        </tr>"""

    if not results:
        # An empty shortlist means two completely different things, and the
        # cell used to state the innocent one either way.
        empty = ("No candidates passed the quality gate today."
                 if not scan_stats.get("errors")
                 else "No shortlist. See the failures listed above — this is not "
                      "a statement about the market.")
        rows = f'<tr><td colspan="7" style="padding:16px;color:#666;">{empty}</td></tr>'


    return f"""
    <html><body style="font-family:Arial,Helvetica,sans-serif;color:#222;">
    {_banner(scan_stats)}
    <h2 style="margin-bottom:4px;">{title}</h2>
    <p style="color:#666;margin-top:0;">
      Universe scanned: {scan_stats.get('universe', '?')} &nbsp;|&nbsp;
      4% bursts found: {scan_stats.get('bursts', '?')} &nbsp;|&nbsp;
      Passed 2LYNCH gate: {scan_stats.get('gated', '?')} &nbsp;|&nbsp;
      Shortlisted: {len(results)}{_provenance_line(scan_stats)}
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
    <p style="color:#999;font-size:11px;margin-top:16px;">
      Automated screening output for human review — not trading advice.
      Verify charts and news before acting.</p>
    </body></html>"""


def _build_attachments(results: list[dict]) -> list[dict]:
    """Attach chart PNGs inline, referenced via cid:chart_<ticker> in the HTML."""
    attachments = []
    for r in results:
        chart = r.get("chart")
        if chart and Path(chart).exists():
            content_b64 = base64.b64encode(Path(chart).read_bytes()).decode()
            attachments.append(
                {
                    "filename": f"{r['ticker']}.png",
                    "content": content_b64,
                    "content_id": f"chart_{r['ticker']}",
                }
            )
    return attachments


def subject_for(results: list[dict], run_type: str, scan_stats: dict) -> str:
    """The one line that shows in a notification, so the status goes in it.

    Before the ticker list, not after: a phone truncates the end.
    """
    label = "Morning watchlist" if run_type == "morning" else "Evening candidates"
    prefix = STATUS_PREFIXES.get(scan_stats.get("status", "ok"), "")
    top = ", ".join(r["ticker"] for r in results) or "none"
    return f"[4% Burst] {prefix}{label}: {top}"


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
