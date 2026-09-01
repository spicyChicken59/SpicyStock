"""
Layer 6 — Email delivery via Resend (https://resend.com).

Builds an HTML table of the top candidates (with inline chart thumbnails)
and sends it through Resend's API using an API key — no OAuth, no refresh
tokens, no consent screens.

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
        rows = ('<tr><td colspan="7" style="padding:16px;color:#666;">'
                "No candidates passed the quality gate today.</td></tr>")

    return f"""
    <html><body style="font-family:Arial,Helvetica,sans-serif;color:#222;">
    <h2 style="margin-bottom:4px;">{title}</h2>
    <p style="color:#666;margin-top:0;">
      Universe scanned: {scan_stats.get('universe', '?')} &nbsp;|&nbsp;
      4% bursts found: {scan_stats.get('bursts', '?')} &nbsp;|&nbsp;
      Passed 2LYNCH gate: {scan_stats.get('gated', '?')} &nbsp;|&nbsp;
      Shortlisted: {len(results)}
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


def send_email(results: list[dict], run_type: str, scan_stats: dict) -> None:
    to = [addr.strip() for addr in os.environ["EMAIL_TO"].split(",")]
    sender = os.environ.get("RESEND_FROM", "onboarding@resend.dev")
    label = "Morning watchlist" if run_type == "morning" else "Evening candidates"
    top = ", ".join(r["ticker"] for r in results) or "none"

    resend.api_key = os.environ["RESEND_API_KEY"]

    params = {
        "from": sender,
        "to": to,
        "subject": f"[4% Burst] {label}: {top}",
        "html": build_html(results, run_type, scan_stats),
        "attachments": _build_attachments(results),
    }

    response = resend.Emails.send(params)
    log.info("Email sent via Resend to %s (%d candidates), id=%s",
              to, len(results), response.get("id"))
