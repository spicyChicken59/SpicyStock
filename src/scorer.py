"""
Layers 3-5 — Chart rendering + Claude scoring engine.

For each surviving candidate, we render a 4-month daily candlestick chart,
send it to Claude together with the numeric metrics and the 2LYNCH results,
and get back a structured score (0-10), a one-sentence reason, and a verdict.

The knowledge base (knowledge/strategy.md) is injected as the system prompt,
so the model is scoring against Stockbee/Qullamaggie rules — not vibes.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
KNOWLEDGE_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "strategy.md"


# ---------------------------------------------------------------- charts ----
def render_chart(ticker: str, df: pd.DataFrame, out_dir: str = "charts") -> str:
    """Render a daily candlestick + volume chart (last ~85 sessions) to PNG."""
    import mplfinance as mpf

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    path = str(Path(out_dir) / f"{ticker}.png")
    plot_df = df.iloc[-85:].copy()
    plot_df.index = pd.to_datetime(plot_df.index)

    mpf.plot(
        plot_df,
        type="candle",
        volume=True,
        mav=(10, 20, 50),
        style="yahoo",
        title=f"{ticker} — daily",
        savefig=dict(fname=path, dpi=110, bbox_inches="tight"),
        figsize=(10, 6),
    )
    return path


# ---------------------------------------------------------------- claude ----
def _client():
    import anthropic

    return anthropic.Anthropic()  # ANTHROPIC_API_KEY from env


def _b64(path: str) -> str:
    return base64.standard_b64encode(Path(path).read_bytes()).decode()


def _extract_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?|```", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start : end + 1])


def score_candidate(cand, lynch_result: dict, context: dict, chart_path: str | None) -> dict:
    """Ask Claude to score one candidate. Returns dict with score/reason/verdict."""
    system = KNOWLEDGE_PATH.read_text()

    metrics = {
        "ticker": cand.ticker,
        "burst_date": cand.date,
        "close": cand.close,
        "gain_pct": cand.gain_pct,
        "volume_ratio_vs_50d_avg": cand.volume_ratio,
        "dollar_volume": cand.dollar_volume,
        **context,
        "2lynch_summary": lynch_result["summary"],
        "2lynch_detail": lynch_result["detail_lines"],
    }

    user_text = (
        "Score this 4% Momentum Burst candidate strictly according to the "
        "strategy rules in your instructions.\n\n"
        f"METRICS:\n{json.dumps(metrics, indent=2)}\n\n"
        "Respond with ONLY a JSON object, no markdown fences, in this exact shape:\n"
        '{"score": <0-10 number, one decimal allowed>, '
        '"reason": "<one sentence, max 25 words>", '
        '"verdict": "<A+|A|B+|B|C|skip>", '
        '"key_risk": "<one short phrase>"}'
    )

    content: list[dict] = []
    if chart_path and Path(chart_path).exists():
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": _b64(chart_path)},
        })
    content.append({"type": "text", "text": user_text})

    try:
        resp = _client().messages.create(
            model=MODEL,
            max_tokens=400,
            system=system,
            messages=[{"role": "user", "content": content}],
        )
        raw = "".join(b.text for b in resp.content if b.type == "text")
        parsed = _extract_json(raw)
        parsed["score"] = float(parsed.get("score", 0))
        return parsed
    except Exception as e:  # noqa: BLE001
        log.warning("Claude scoring failed for %s: %s — using checklist fallback", cand.ticker, e)
        # Deterministic fallback so the pipeline never dies on an API hiccup
        fallback = round(lynch_result["passes"] / lynch_result["total"] * 10, 1)
        return {
            "score": fallback,
            "reason": f"AI unavailable; checklist score {lynch_result['summary']}.",
            "verdict": "B" if fallback >= 6 else "skip",
            "key_risk": "not AI-reviewed",
        }


def score_all(scored_inputs: list[tuple], top_n: int = 5, min_lynch: int = 3) -> list[dict]:
    """scored_inputs: list of (candidate, lynch_result, context, chart_path).

    Applies the hard checklist gate, has Claude score survivors, and returns
    the top N as plain dicts ready for the email layer.
    """
    results = []
    for cand, lynch_result, context, chart_path in scored_inputs:
        if lynch_result["passes"] < min_lynch:
            log.info("%s gated out (2LYNCH %s)", cand.ticker, lynch_result["summary"])
            continue
        ai = score_candidate(cand, lynch_result, context, chart_path)
        results.append({
            "ticker": cand.ticker,
            "date": cand.date,
            "close": cand.close,
            "gain_pct": cand.gain_pct,
            "volume_ratio": cand.volume_ratio,
            "lynch": lynch_result["summary"],
            "lynch_detail": lynch_result["detail_lines"],
            "score": ai["score"],
            "verdict": ai.get("verdict", "?"),
            "reason": ai.get("reason", ""),
            "key_risk": ai.get("key_risk", ""),
            "chart": chart_path,
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_n]
