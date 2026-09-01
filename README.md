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
| n8n + Airtable + Google Sheets | Single Python pipeline + GitHub Actions cron | Fewer moving parts, zero hosting cost |
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

Push this repo to GitHub and add six repository secrets — these are exactly
what `.github/workflows/evening.yml` reads, and `.env.example` explains each:

`ANTHROPIC_API_KEY`, `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`,
`RESEND_API_KEY`, `RESEND_FROM`, `EMAIL_TO`

`.github/workflows/evening.yml` then fires on weekdays and can be triggered
manually from the Actions tab.

> **Note:** there is only one *pipeline* workflow (`secret-scan.yml` is the
> other file in that directory), and it fires at 6:16 PM ET — 22:16 UTC
> under EDT, 23:16 UTC under EST — not the 5:30 PM this README claims
> elsewhere. Both crons are registered and the guard no-ops the wrong one. It is
> labelled backup-only for an external trigger you should not set up. The
> 8:30 AM morning run has no workflow file at all; `morning.yml` does not
> exist, and `src/pipeline.py` treats `morning` and `evening` identically
> apart from the email subject, the body heading, and the CSV filename.
>
> `SETUP.md` is kept only as a record of the original build — do not follow it.

**Credential safety.** `.gitignore` blocks the credential filenames we can
predict, and `.github/workflows/secret-scan.yml` runs gitleaks on every push
and a full-history sweep weekly — that catches a key pasted into an arbitrary
file or a log committed by accident. It scans patch content, so a secret in a
commit *message* is not covered. Turning on GitHub secret
scanning with push protection (Settings → Code security) adds a second layer
that rejects the push before it lands; it is free on public repos and part of
paid Secret Protection on private ones.

## Run locally

```bash
pip install -r requirements.txt
cp .env.example .env             # fill it in, single-quoting every value:
set -a; . ./.env; set +a         # this runs .env as a shell script

# Full evening run without sending email:
python -m src.pipeline evening --dry-run

# Smoke-test on a few tickers:
python -m src.pipeline evening --dry-run --tickers NVDA,PLTR,SMCI,CRWD

# Offline logic tests (no network / API key needed):
python -m tests.test_pipeline   # currently fails: imports detect_burst,
                                # which src/scanner.py does not define
```

## Tuning

- Thresholds (price floor, volume ratios, dollar volume): `ScanConfig` in `src/scanner.py`
- 2LYNCH pass criteria: `src/lynch.py`
- Gate strictness / shortlist size / Claude-call cap: constants at the top of `src/pipeline.py`
- Scoring rubric the AI follows: `knowledge/strategy.md` — edit this file to change how Claude judges setups; no code changes needed
- Model: set `CLAUDE_MODEL` env var (default `claude-sonnet-4-6`)

## Costs and limits

> **Note:** the pipeline diagram above, and most of this section, still
> describe the original yfinance build (the data-source and retention bullets
> below have been corrected; the rest have not). The real Layer-1
> filter is `≥4% gain · today's volume ≥ yesterday's · volume > 5,000,000
> shares · close > $4.00` — there is no 50-day-average or dollar-volume gate,
> and `ScanConfig` exposes only `min_price`, `min_gain_pct`, `min_today_volume`,
> `lookback_days` and `batch_size`. Rewriting this is a later step.

- Market data: free (Alpaca) — but see `.env.example`: the free plan serves
  IEX data, a small fraction of consolidated volume, which the current
  5,000,000-share floor will almost never clear. Free is viable only once that
  threshold is made relative. A full-universe scan takes ~10–20 min inside
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
  workflow artifacts (retained 30 days, and `results/` is gitignored so
  nothing accumulates in the repo), giving you a partial dataset for the AI
  rankings (the Phase-2 item in the original doc).
- Output is screening for human review, not trading advice.
