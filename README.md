# 4% Momentum Burst — Fully Automated Scanner

Scans a checked-in universe of 230 US common stocks each trading day, applies the
Stockbee/Qullamaggie 4% Momentum Burst strategy with the 2LYNCH quality
checklist, has Claude score the survivors (numbers + chart image), and
emails a ranked top-5 shortlist. **Zero manual steps** — no DeepVue paste,
no Google Sheet, no n8n.

## How it differs from the original spec

| Original plan | This build | Why |
|---|---|---|
| DeepVue scan, pasted by hand daily | Built-in scanner over a checked-in symbol list (`data/symbols.txt`) | The one manual step is eliminated — full automation was the requirement |
| n8n + Airtable + Google Sheets | Single Python pipeline + GitHub Actions cron | Fewer moving parts, zero hosting cost |
| GPT-5 API | Claude API (vision + text) | One model handles chart reading and checklist reasoning in a single call |
| NotebookLM knowledge base | `knowledge/strategy.md` injected as the system prompt | Deterministic, versioned, auditable — you can see exactly what rules the AI scores against |

## Pipeline

```
checked-in universe (data/symbols.txt, 230 names)
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

> **Note:** `evening.yml` is the only *pipeline* workflow — `secret-scan.yml`
> and `tests.yml` are the other two files in that directory. It fires at
> 6:16 PM ET — 22:16 UTC
> under EDT, 23:16 UTC under EST — not the 5:30 PM this README claims
> elsewhere. Both crons are registered and the guard no-ops the wrong one. It is
> labelled backup-only for an external trigger you should not set up. The
> 8:30 AM morning run has no workflow file at all; `morning.yml` does not
> exist, and `src/pipeline.py` treats `morning` and `evening` identically
> apart from the email subject, the body heading, and the CSV filename.
>
> An older `SETUP.md` walked through a Gmail OAuth flow this code no longer
> uses; it was removed rather than annotated, since following it minted
> credentials nothing reads. It is in git history if you want it.

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
pip install -r requirements-dev.txt
pytest tests/                   # 69 tests, no network or API keys needed
```

## The dashboard

`docs/index.html` is a static page served by GitHub Pages from `docs/`. It fetches
`docs/data.json` in the browser and renders it — no server, no build step, no
framework. **`docs/data.json` is currently a hand-authored fixture** — the
pipeline does not write it yet (step 9), and the page says so at the top of
itself. Wiring it up is what makes the rest of this section true.

It shows the run's funnel (universe → bursts → 2LYNCH gate → scored → shortlist),
**every candidate the run scored** rather than the five that went out by email, each
one's 2LYNCH checklist with its measured values, and — for every score — whether
Claude produced it or the offline checklist fallback did. A fallback score can and
does outrank real ones, so it is labelled everywhere it appears and called out at the
top of the page.

### The data contract

`docs/data.json` is `schema_version: 1`, and carries its own `_contract` block so the
invariants live in the file rather than only here. The load-bearing ones:

- `candidates` must hold **every** scored candidate, ranked, never truncated:
  `len(candidates) == run.scored`. Today `score_all()` returns `results[:TOP_N]`
  and `archive()` writes exactly that, so `TOP_N` currently cuts the archive as
  well as the email — making the archive unevaluable. Moving that cut into the
  emailer is step 9's job, and this invariant is what it has to satisfy.
- `run.scored + len(gated_out) == run.bursts`. Nothing a scan found may vanish.
- Every candidate carries `provenance.source` (`"claude"` or `"fallback"`), and
  `provenance.chart_seen` is true only when the model actually received the chart.
- `chart` is a path relative to `docs/`, or `null` with a `chart_error` saying why.
- Numbers are numbers or `null` — never `0` for "unknown", never the string `"n/a"`.
- `forward_returns` are `null` until those sessions have happened.

Regenerate it with `python3 tools/make_fixture.py docs/data.json`. The generator
reads `data/symbols.txt` and `ScanConfig`, so it cannot emit a run this scanner
could not produce; `tools/check_fixture_fresh.py` regenerates it and fails the
build if the committed file has drifted. The chart PNGs it references are absent until step 9, so the
page degrades to an explained empty frame — that is the expected state.

### Checking it

```bash
git clone --branch v2.4.0 https://github.com/spicyChicken59/design-system /tmp/design-system
node tools/dashboard_smoke.mjs        # /tmp/design-system is on its search path
```

Opens the real page in headless Chromium and asserts what it promises. Offline by
construction: `docs/` is served locally and every CDN request is answered from a
design-system checkout on disk. Needs playwright's chromium; it is not a repo
dependency, and the script exits 0 with a note if chromium is missing.

## Tuning

- Scan universe: `data/symbols.txt` — a hand-curated starter list, not the whole market
- Thresholds (price floor, gain %, share-volume floor): `ScanConfig` in `src/scanner.py`
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
  threshold is made relative. A 230-symbol scan takes under a second inside
  the Actions runner; well within the 55-min timeout.
- Claude: ≤25 scoring calls/run with one chart image each — a few cents/day
  on Sonnet.
- GitHub Actions: free tier covers 2 runs/day comfortably (private repos get
  2,000 min/month; ~40 min/day used).

## Notes

- The data layer is Alpaca (`_download_batch` in `src/scanner.py`). If the free
  IEX feed proves too thin once the volume threshold is relative, swapping that
  one function for another provider leaves the rest of the pipeline unchanged.
- Every run archives its shortlist to `results/*.csv` and uploads charts as
  workflow artifacts (retained 30 days, and `results/` is gitignored so
  nothing accumulates in the repo), giving you a partial dataset for the AI
  rankings (the Phase-2 item in the original doc).
- Output is screening for human review, not trading advice.
