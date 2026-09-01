# 4% Momentum Burst — Fully Automated Scanner

Scans the entire US stock market twice every trading day, applies the
Stockbee/Qullamaggie 4% Momentum Burst strategy with the 2LYNCH quality
checklist, has Claude score the survivors (numbers + chart image), and
emails a ranked top-5 shortlist. **Zero manual steps** — no DeepVue paste,
no Google Sheet, no n8n.

## How it differs from the original spec

| Original plan | This build | Why |
|---|---|---|
| DeepVue scan, pasted by hand daily | Built-in scanner over the full US universe (yfinance + NASDAQ symbol directory) | The one manual step is eliminated — full automation was the requirement |
| n8n + Airtable + Google Sheets | Single Python pipeline + GitHub Actions cron | Fewer moving parts, zero hosting cost, versioned results in-repo artifacts |
| GPT-5 API | Claude API (vision + text) | One model handles chart reading and checklist reasoning in a single call |
| NotebookLM knowledge base | `knowledge/strategy.md` injected as the system prompt | Deterministic, versioned, auditable — you can see exactly what rules the AI scores against |

## Pipeline

```
NASDAQ+NYSE universe (~5,500 common stocks)
        │  yfinance daily OHLCV, batched
        ▼
Layer 1  4% burst filter ............. ≥4% gain, vol > yesterday, ≥1.5x 50d avg,
        │                              price ≥ $3, ≥ $3M dollar volume
        ▼  (~30–120 names on a normal day)
Layer 2  2LYNCH checklist (code) ..... 2 first/second burst · L linear prior move
        │                              Y young trend · N narrow consolidation
        │                              C calm pre-burst day · H close near high
        │                              hard gate: ≥3/6 passes, top 25 kept
        ▼
Layer 3  Chart render ................ 4-month candlestick + volume PNG per name
        ▼
Layer 4  Claude scoring .............. metrics + 2LYNCH detail + chart image →
        │                              score /10, verdict (A+…skip), 1-sentence
        │                              reason, key risk (strategy.md = rulebook)
        ▼
Layer 5  Email ....................... HTML table with inline charts, top 5
                                       + CSV archived to results/
```

**Evening run (5:30 PM ET):** scans today's completed session → candidates for tomorrow.
**Morning run (8:30 AM ET):** scans the latest completed session (yesterday) → follow-through watchlist for today.

## One-time setup

See the step-by-step guide in SETUP.md. Summary: create a Google Cloud OAuth
client ("Sign in with Google", gmail.send scope only), run
`scripts/setup_gmail_oauth.py` once locally to get a refresh token, push this
repo to GitHub, and add six repository secrets:

`ANTHROPIC_API_KEY`, `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`,
`RESEND_API_KEY`, `RESEND_FROM`, `EMAIL_TO`

> **Note:** the surrounding prose in this section is out of date — it describes
> a Gmail OAuth flow the code no longer uses, and `scripts/setup_gmail_oauth.py`
> does not exist. The six secret names above are correct and match
> `.github/workflows/evening.yml`. See `.env.example` for what each one is.

The two workflows in `.github/workflows/` then fire automatically on
weekdays at 8:30 AM and 5:30 PM Eastern (DST-safe), and can be triggered
manually from the Actions tab.

## Run locally

```bash
pip install -r requirements.txt
cp .env.example .env             # fill it in, then load it:
set -a; . ./.env; set +a

# Full evening run without sending email:
python -m src.pipeline evening --dry-run

# Smoke-test on a few tickers:
python -m src.pipeline evening --dry-run --tickers NVDA,PLTR,SMCI,CRWD

# Offline logic tests (no network / API key needed):
python -m tests.test_pipeline
```

## Tuning

- Thresholds (price floor, volume ratios, dollar volume): `ScanConfig` in `src/scanner.py`
- 2LYNCH pass criteria: `src/lynch.py`
- Gate strictness / shortlist size / Claude-call cap: constants at the top of `src/pipeline.py`
- Scoring rubric the AI follows: `knowledge/strategy.md` — edit this file to change how Claude judges setups; no code changes needed
- Model: set `CLAUDE_MODEL` env var (default `claude-sonnet-4-6`)

## Costs and limits

- Market data: free (yfinance). A full-universe scan takes ~10–20 min inside
  the Actions runner; well within the 55-min timeout.
- Claude: ≤25 scoring calls/run with one chart image each — a few cents/day
  on Sonnet.
- GitHub Actions: free tier covers 2 runs/day comfortably (private repos get
  2,000 min/month; ~40 min/day used).

## Notes

- yfinance is unofficial Yahoo data; if it ever degrades, swap
  `_download_batch` in `src/scanner.py` for Polygon.io or Alpaca (both have
  free tiers) — the rest of the pipeline is unchanged.
- Every run archives its shortlist to `results/*.csv` and uploads charts as
  workflow artifacts, giving you a growing dataset to backtest the AI
  rankings (the Phase-2 item in the original doc).
- Output is screening for human review, not trading advice.
