"""Layers 3-5 -- chart rendering and the Anthropic boundary.

The scoring rubric itself lives in knowledge/strategy.md and is the model's
business, so nothing here asserts what a score should be. What is asserted is
that a chart is really rendered, that the request Claude receives carries the
metrics and the image, that the reply is parsed, and that an API failure
degrades to the checklist fallback instead of killing the run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.scanner import Candidate, ScanConfig, detect_setup
from src.scorer import render_chart, score_all, score_candidate

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def candidate(ohlcv):
    df = ohlcv("burst")
    metrics = detect_setup(df, ScanConfig())
    assert metrics, "the burst fixture must produce a candidate for this test"
    return Candidate(ticker="AAA", history=df, **metrics)


def make_lynch(passes: int = 5) -> dict:
    """A checklist result of a given strength, built by hand.

    Hand-built on purpose: this file must keep working when step 7 changes
    what a real frame scores.
    """
    return {
        "checks": {},
        "passes": passes,
        "total": 6,
        "summary": f"{passes}/6",
        "detail_lines": [f"PASS  check_{i}: measured" for i in range(passes)],
    }


CONTEXT = {
    "pct_off_52w_high": -2.0,
    "pct_above_52w_low": 40.0,
    "perf_3mo_pct": 12.0,
    "perf_6mo_pct": 18.0,
}


# ------------------------------------------------------------------ charts --


def test_render_chart_writes_a_real_png(ohlcv, tmp_path):
    out = tmp_path / "charts"
    path = Path(render_chart("AAA", ohlcv("burst"), out_dir=str(out)))
    assert path == out / "AAA.png"
    data = path.read_bytes()
    assert data.startswith(PNG_MAGIC)
    assert len(data) > 20_000, "a chart this small is probably an empty canvas"


def test_render_chart_defaults_into_the_working_directory(ohlcv, tmp_path):
    """The default out_dir is relative, which is why the whole suite runs
    inside tmp_path -- see the _isolated_cwd fixture."""
    render_chart("AAA", ohlcv("burst"))
    assert (tmp_path / "charts" / "AAA.png").exists()


# ------------------------------------------------------------- scoring one --


def test_score_candidate_parses_the_model_reply(candidate, fake_anthropic):
    fake_anthropic.set_payload(
        {"score": 8.4, "reason": "tight base", "verdict": "A", "key_risk": "breadth"}
    )
    result = score_candidate(candidate, make_lynch(), CONTEXT, None)
    assert result["score"] == 8.4
    assert result["verdict"] == "A"
    assert result["reason"] == "tight base"
    assert result["key_risk"] == "breadth"
    assert len(fake_anthropic.calls) == 1


def test_score_candidate_parses_a_fenced_reply(candidate, fake_anthropic):
    """The model sometimes wraps JSON in a markdown fence; _extract_json is
    what makes that survivable."""
    fake_anthropic.set_raw(
        'Here you go:\n```json\n'
        '{"score": 6, "reason": "ok", "verdict": "B", "key_risk": "gap"}\n```'
    )
    result = score_candidate(candidate, make_lynch(), CONTEXT, None)
    assert isinstance(result["score"], float)
    assert result["score"] == 6.0
    assert result["verdict"] == "B"


def test_the_request_carries_the_metrics_and_the_checklist(candidate, fake_anthropic):
    lynch = make_lynch(4)
    score_candidate(candidate, lynch, CONTEXT, None)
    call = fake_anthropic.calls[0]

    assert call["model"]
    assert call["system"], "the strategy knowledge base is the system prompt"
    blocks = call["messages"][0]["content"]
    text = "".join(b["text"] for b in blocks if b["type"] == "text")
    assert candidate.ticker in text
    assert lynch["summary"] in text
    for line in lynch["detail_lines"]:
        assert line in text
    assert "pct_off_52w_high" in text


def test_the_chart_is_attached_as_an_image_block(candidate, fake_anthropic, ohlcv):
    chart = render_chart("AAA", ohlcv("burst"))
    score_candidate(candidate, make_lynch(), CONTEXT, chart)
    blocks = fake_anthropic.calls[0]["messages"][0]["content"]
    images = [b for b in blocks if b["type"] == "image"]
    assert len(images) == 1
    assert images[0]["source"]["media_type"] == "image/png"
    assert images[0]["source"]["data"], "the PNG was not base64-encoded into the request"


def test_a_missing_chart_is_simply_not_attached(candidate, fake_anthropic):
    score_candidate(candidate, make_lynch(), CONTEXT, "charts/does-not-exist.png")
    blocks = fake_anthropic.calls[0]["messages"][0]["content"]
    assert [b["type"] for b in blocks] == ["text"]


def test_api_failure_falls_back_to_the_checklist(candidate, fake_anthropic):
    """The fallback's arithmetic is 2LYNCH maths and step 7 will change it, so
    only its shape and range are asserted."""
    fake_anthropic.set_error(RuntimeError("503 overloaded"))
    result = score_candidate(candidate, make_lynch(4), CONTEXT, None)
    assert set(result) == {"score", "reason", "verdict", "key_risk"}
    assert isinstance(result["score"], float)
    assert 0.0 <= result["score"] <= 10.0
    assert result["reason"] and result["verdict"] and result["key_risk"]


# ------------------------------------------------------------- scoring all --


def _inputs(*passes: int) -> list[tuple]:
    from tests.synthetic import make_ohlcv

    out = []
    for i, p in enumerate(passes):
        df = make_ohlcv("burst", seed=[1000 + i])
        metrics = detect_setup(df, ScanConfig())
        cand = Candidate(ticker=f"T{i}", history=df, **metrics)
        out.append((cand, make_lynch(p), CONTEXT, None))
    return out


def test_score_all_drops_candidates_below_the_gate(fake_anthropic):
    results = score_all(_inputs(6, 4, 1), top_n=5, min_lynch=3)
    assert [r["ticker"] for r in results] == ["T0", "T1"]
    assert len(fake_anthropic.calls) == 2, "a gated-out candidate must not cost an API call"


def test_score_all_truncates_to_top_n(fake_anthropic):
    results = score_all(_inputs(6, 6, 6, 6), top_n=2, min_lynch=3)
    assert len(results) == 2


def test_score_all_rows_carry_everything_the_email_needs(fake_anthropic):
    (result,) = score_all(_inputs(5), top_n=5, min_lynch=3)
    assert set(result) == {
        "ticker", "date", "close", "gain_pct", "volume_ratio",
        "lynch", "lynch_detail", "score", "verdict", "reason", "key_risk", "chart",
    }
