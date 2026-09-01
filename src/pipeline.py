"""
Orchestrator — ties all layers together. Two modes:

  evening : scan today's completed session → candidates to watch TOMORROW
  morning : re-scan the most recent completed session (yesterday) →
            follow-through watchlist for TODAY

Both modes are stateless and fully automated:
  scan → 2LYNCH gate → chart render → Claude scoring → email → CSV archive

Usage:  python -m src.pipeline morning|evening [--dry-run] [--tickers AAPL,MSFT]
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from .lynch import evaluate_2lynch, extra_context
from .scanner import ScanConfig, run_scan
from .scorer import render_chart, score_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("pipeline")

TOP_N = 5
MIN_LYNCH_PASSES = 3
MAX_TO_SCORE = 25  # cap Claude calls per run


def archive(results: list[dict], run_type: str) -> Path:
    out = Path("results")
    out.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = out / f"{stamp}_{run_type}.csv"
    cols = ["ticker", "date", "close", "gain_pct", "volume_ratio",
            "lynch", "score", "verdict", "reason", "key_risk"]
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(results)
    return path


def run(run_type: str, dry_run: bool = False, tickers: list[str] | None = None) -> list[dict]:
    cfg = ScanConfig()
    log.info("=== %s run starting ===", run_type)

    # Layer 1: scan (yfinance always returns the most recent COMPLETED bar,
    # so evening runs see today's close and morning runs see yesterday's).
    candidates = run_scan(cfg, universe=tickers)
    n_bursts = len(candidates)

    # Layer 2: 2LYNCH checklist + context, hard gate, keep the best
    prepared = []
    for cand in candidates:
        lynch = evaluate_2lynch(cand.history)
        ctx = extra_context(cand.history)
        prepared.append((cand, lynch, ctx))

    prepared.sort(key=lambda x: (x[1]["passes"], x[0].gain_pct), reverse=True)
    gated = [p for p in prepared if p[1]["passes"] >= MIN_LYNCH_PASSES][:MAX_TO_SCORE]
    log.info("%d bursts → %d passed 2LYNCH gate (scoring top %d)",
             n_bursts, sum(1 for p in prepared if p[1]["passes"] >= MIN_LYNCH_PASSES), len(gated))

    # Layers 3-5: charts + Claude scoring
    scored_inputs = []
    for cand, lynch, ctx in gated:
        chart = None
        try:
            chart = render_chart(cand.ticker, cand.history)
        except Exception as e:  # noqa: BLE001
            log.warning("Chart render failed for %s: %s", cand.ticker, e)
        scored_inputs.append((cand, lynch, ctx, chart))

    results = score_all(scored_inputs, top_n=TOP_N, min_lynch=MIN_LYNCH_PASSES)

    stats = {"universe": "US common stocks", "bursts": n_bursts, "gated": len(gated)}
    path = archive(results, run_type)
    log.info("Archived shortlist to %s", path)

    # Layer 6: email
    if dry_run:
        log.info("DRY RUN — skipping email. Shortlist:")
        for r in results:
            log.info("  %s  %s/10 (%s) %s", r["ticker"], r["score"], r["verdict"], r["reason"])
    else:
        from .emailer import send_email
        send_email(results, run_type, stats)

    log.info("=== %s run complete ===", run_type)
    return results


def main() -> None:
    p = argparse.ArgumentParser(description="4% Momentum Burst pipeline")
    p.add_argument("run_type", choices=["morning", "evening"])
    p.add_argument("--dry-run", action="store_true", help="skip sending email")
    p.add_argument("--tickers", help="comma-separated tickers (testing only)")
    args = p.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(",")] if args.tickers else None
    try:
        run(args.run_type, dry_run=args.dry_run, tickers=tickers)
    except Exception:
        log.exception("Pipeline failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
