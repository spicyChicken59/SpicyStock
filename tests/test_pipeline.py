"""Offline tests: verify burst detection, 2LYNCH logic, charts, and email HTML
using synthetic OHLCV data (no network, no API key required).

Run:  python -m tests.test_pipeline
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.lynch import evaluate_2lynch, extra_context
from src.scanner import Candidate, ScanConfig, detect_burst
from src.scorer import render_chart
from src.emailer import build_html

rng = np.random.default_rng(42)


def make_history(kind: str, n: int = 200) -> pd.DataFrame:
    """Build synthetic daily OHLCV. kind: 'ideal', 'extended', 'no_burst'."""
    dates = pd.bdate_range(end="2026-07-01", periods=n)
    close = np.full(n, 20.0)

    if kind == "ideal":
        # quiet base -> orderly 15% rise -> tight 2-week consolidation -> 4.8% burst
        close[: n - 45] = 20 + np.cumsum(rng.normal(0, 0.05, n - 45))
        rise = np.linspace(close[n - 46], close[n - 46] * 1.15, 30)
        close[n - 45 : n - 15] = rise + rng.normal(0, 0.05, 30)
        base = close[n - 16]
        close[n - 15 : n - 1] = base + rng.normal(0, 0.06, 14)
        close[n - 1] = close[n - 2] * 1.048
    elif kind == "extended":
        # violent 60% ramp with repeated 4-6% days, burst is the 5th push
        close[: n - 25] = 20 + np.cumsum(rng.normal(0, 0.15, n - 25))
        c = close[n - 26]
        for i in range(25):
            jump = 1.05 if i % 4 == 0 else 1.0 + rng.normal(0.01, 0.02)
            c *= jump
            close[n - 25 + i] = c
        close[n - 1] = close[n - 2] * 1.05
    else:  # no_burst
        close = 20 + np.cumsum(rng.normal(0, 0.1, n))
        close[n - 1] = close[n - 2] * 1.01

    close = np.maximum(close, 1.0)
    spread = np.abs(rng.normal(0.01, 0.004, n))
    high = close * (1 + spread)
    low = close * (1 - spread)
    open_ = low + (high - low) * rng.uniform(0.2, 0.8, n)
    vol = rng.integers(400_000, 600_000, n).astype(float)

    if kind == "ideal":
        vol[n - 15 : n - 1] *= 0.7          # dry-up in the base
        vol[n - 1] = 1_400_000              # 2.8x burst volume
        high[n - 1] = close[n - 1] * 1.004  # close near high
        low[n - 1] = close[n - 2] * 0.998
        open_[n - 1] = close[n - 2] * 1.002
    elif kind == "extended":
        vol[n - 1] = 900_000
        high[n - 1] = close[n - 1] * 1.03   # closes mid-range
        low[n - 1] = close[n - 2] * 0.99

    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol},
        index=dates,
    )


def main() -> None:
    cfg = ScanConfig()
    failures = 0

    # 1) burst detection
    ideal = make_history("ideal")
    m = detect_burst(ideal, cfg)
    assert m and m["gain_pct"] >= 4.0 and m["volume_ratio"] >= 1.5, "ideal setup should be detected"
    print(f"[PASS] burst detected: +{m['gain_pct']}% on {m['volume_ratio']}x volume")

    quiet = make_history("no_burst")
    assert detect_burst(quiet, cfg) is None, "1% day must not trigger"
    print("[PASS] non-burst correctly ignored")

    # 2) 2LYNCH discrimination
    good = evaluate_2lynch(ideal)
    bad = evaluate_2lynch(make_history("extended"))
    print(f"[INFO] ideal 2LYNCH {good['summary']}:")
    for line in good["detail_lines"]:
        print("        " + line)
    print(f"[INFO] extended/choppy 2LYNCH {bad['summary']}:")
    for line in bad["detail_lines"]:
        print("        " + line)
    if good["passes"] >= 5 and bad["passes"] <= good["passes"] - 2:
        print(f"[PASS] checklist separates quality ({good['summary']}) from junk ({bad['summary']})")
    else:
        print("[FAIL] checklist did not discriminate"); failures += 1

    # 3) context metrics
    ctx = extra_context(ideal)
    print(f"[PASS] context metrics: {ctx}")

    # 4) chart rendering
    path = render_chart("TEST", ideal, out_dir="charts")
    import os
    assert os.path.getsize(path) > 10_000
    print(f"[PASS] chart rendered: {path} ({os.path.getsize(path)//1024} KB)")

    # 5) email HTML build
    cand = Candidate(ticker="TEST", history=ideal, **m)
    results = [{
        "ticker": cand.ticker, "date": m["date"], "close": m["close"],
        "gain_pct": m["gain_pct"], "volume_ratio": m["volume_ratio"],
        "lynch": good["summary"], "lynch_detail": good["detail_lines"],
        "score": 8.4, "verdict": "A", "reason": "First burst from a tight two-week base on 2.8x volume.",
        "key_risk": "market breadth", "chart": path,
    }]
    html = build_html(results, "evening", {"universe": 5000, "bursts": 42, "gated": 12})
    assert "TEST" in html and "8.4" in html
    with open("results_preview.html", "w") as f:
        f.write(html)
    print("[PASS] email HTML built -> results_preview.html")

    print("\nAll tests passed." if not failures else f"\n{failures} FAILURES")
    raise SystemExit(failures)


if __name__ == "__main__":
    main()
