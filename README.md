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
        │  Alpaca daily OHLCV, split-adjusted, delayed SIP, batched
        ▼
Layer 1  4% burst filter ............. ≥4% gain, vol ≥ yesterday, ≥1.5x its own
        │                              50-session average, price > $4, and in the
        │                              top 70% of the day's dollar volume
        ▼  (a handful on a 230-name universe)
Layer 2  2LYNCH checklist (code) ..... 2 first/second burst · L linear prior move
        │                              Y young trend · N narrow consolidation
        │                              C calm pre-burst day · H close near high
        │                              hard gate: ≥3/6 passes, top 25 kept
        ▼
Layer 3  Chart render ................ 4-month candlestick + volume PNG per name,
        │                              written to docs/charts/ so the dashboard
        ▼                              can serve the same image the model saw
Layer 4  Claude scoring .............. metrics + 2LYNCH detail + chart image →
        │                              score /10, verdict (A+…skip), 1-sentence
        │                              reason, key risk (strategy.md = rulebook)
        ▼
Layer 5  Archive ..................... EVERY scored candidate, plus every burst
        │                              that was not scored and why:
        │                              docs/data.json (the dashboard's snapshot),
        │                              docs/ledger.json (the record, with the
        ▼                              forward returns a later run fills in),
                                       results/*.csv (a 30-day artifact)
Layer 6  Email ....................... HTML table with inline charts, top 5 —
                                       the ONLY place TOP_N cuts anything
```

**Evening run (6:16 PM ET):** scans that day's completed session → candidates for tomorrow.
A morning run exists in `src/pipeline.py` but has no workflow and no distinct
behaviour; resolving that is step 10.

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

# Seed the history from a past session (its forward returns resolve at once):
SCAN_SESSION_DATE=2026-08-24 python -m src.pipeline evening --dry-run

# Offline logic tests (no network / API key needed):
pip install -r requirements-dev.txt
pytest tests/                   # 331 tests, no network or API keys needed
```

Every run — `--dry-run` included, since `--dry-run` skips only the email —
rewrites `docs/data.json`, updates `docs/ledger.json` and writes PNGs into
`docs/charts/`. A four-ticker smoke test therefore replaces the committed
fixture with a four-ticker run. `git checkout docs/data.json` puts it back;
`tools/check_fixture_fresh.py` tells you whether it needs putting back.

## The dashboard

`docs/index.html` is a static page served by GitHub Pages from `docs/`. It fetches
`docs/data.json` in the browser and renders it — no server, no build step, no
framework. **The pipeline writes that file at the end of every run** (step 9,
`src/ledger.py`), together with `docs/ledger.json` and the chart PNGs the page
shows. The copy committed here is still the hand-authored fixture from
`tools/make_fixture.py`, and it says so in its own `run.fixture: true`, which is
what raises the "sample data" banner at the top of the page; a real run writes
`false` and the banner disappears. The first run whose output is committed
replaces it.

It shows the run's funnel (universe → bursts → 2LYNCH gate → scored → shortlist),
**every candidate the run scored** rather than the five that went out by email, each
one's 2LYNCH checklist with its measured values, and — for every score — whether
Claude produced it or the offline checklist fallback did. A fallback score can no
longer outrank a real one: `score_all` sorts on provenance before score, so every
Claude score ranks above every fallback whatever the numbers say. It is labelled
everywhere it appears and called out at the top of the page.

### The data contract

`docs/data.json` is `schema_version: 1`, and carries its own `_contract` block so the
invariants live in the file rather than only here. The load-bearing ones:

- `candidates` must hold **every** scored candidate, ranked, never truncated:
  `len(candidates) == run.scored`. Until step 9 `score_all()` returned
  `results[:TOP_N]` and `archive()` wrote exactly that, so the shortlist size
  silently decided how much of each run was ever recorded — which is what made the
  screener unevaluable. The cut now happens once, in `run()`, on the way to the
  email alone.
- `run.scored + len(gated_out) == run.bursts`. Nothing a scan found may vanish.
  A burst that went unscored carries `reason`: `lynch_gate` (it failed the
  checklist) or `score_cap` (it passed and fell outside `MAX_TO_SCORE`).
- Every candidate carries `provenance.source` (`"claude"` or `"fallback"`), and
  `provenance.chart_seen` is true only when the model actually received the chart.
- `chart` is a path relative to `docs/`, or `null` with a `chart_error` saying why.
- Numbers are numbers or `null` — never `0` for "unknown", never the string `"n/a"`.
  `src.ledger` writes every number through one coercion and dumps with
  `allow_nan=False`, because `json.dump` writes a NaN as a bare token no browser
  will parse — one gap would cost the whole page, not one cell.
- `forward_returns` are `null` until those sessions have happened.

One invariant reads slightly stricter than the file can be: `candidates` is
described as "ranked by score descending", while the pipeline ranks on
`(scored_by_claude, score)` — step 8's rule that no fallback may outrank a
reviewed candidate. Within each group it is score order. The wording in the
`_contract` block has been left alone rather than regenerated under a builder
who cannot see the page render.

Regenerate the committed fixture with `python3 tools/make_fixture.py docs/data.json`.
The generator reads `data/symbols.txt`, `ScanConfig` and — since step 9 — the
invariant list itself from `src/ledger.py`, so it cannot emit a run this scanner
could not produce, nor promise a contract different from the one the pipeline
writes; `tools/check_fixture_fresh.py` regenerates it and fails the build if the
committed file has drifted. The chart PNGs the fixture names do not exist, so the
page degrades to an explained empty frame — that is the expected state for it. A
real run writes its charts next to the file that names them.

### Forward returns, and where the history lives

`docs/data.json` describes one run — the newest — so it can never hold the
outcome of the scores in it: the burst closed at tonight's close and no later
session exists yet. The record that accumulates is **`docs/ledger.json`**: one
slim row per candidate per run (score, verdict, provenance, the six checks, the
burst's own numbers), kept for the last 260 runs, with the forward returns filled
in by later runs. `data.json`'s `runs[]` history is the per-run mean of the same
rows, which is what the dashboard's "has any of this made money yet" panel reads.

- `d1`, `d3`, `d5` are the percentage change from the burst-day close to the
  close 1, 3 and 5 **sessions** later — positions in the frame, not calendar
  days, so a holiday cannot quietly shift a horizon.
- Both closes come out of the **same** freshly fetched frame. The archived
  `close` is deliberately not the denominator: a split between the burst and
  today restates every price before its ex-date, and an as-traded close divided
  into a split-adjusted one is a -75% return the market never printed.
- `as_of` is the newest session whose close was actually used, or `null` when
  none was. A row of three nulls says "nothing has happened yet"; it never
  claims data this pipeline does not have.
- A horizon is filled once and never restated. A name that stops trading is
  retried for ten runs and then left pending forever, which is the honest
  answer for a delisting.
- Filling costs one extra bars request per 100 pending names, on the same free
  feed and through the same `_download_batch` the scan uses. If it fails, the
  run is marked **degraded** rather than quietly stopping to accumulate.

**Seeding a history without waiting a year.** A run pinned to an old session
resolves its own outcomes, because everything after that burst has already
happened:

```bash
SCAN_SESSION_DATE=2026-08-24 python -m src.pipeline evening --dry-run
```

That is also the only way the dashboard's score-against-outcome plot can carry a
point today: on a normal evening run, tonight's candidates are pending by
construction, and the next run replaces the snapshot rather than filling it in.
Plotting resolved outcomes across runs needs the page to read `ledger.json`,
which is a change to `docs/index.html` and not part of this step.

### Does the history actually accumulate?

Locally, yes: `docs/ledger.json` is written on every run and kept for 260 runs.

In GitHub Actions it now accumulates too — `evening.yml` commits `docs/` back to
the branch after each run, the way the sibling SpicyCar project does. Without
that step everything written into `docs/` would die with the container and every
CI run would start a fresh history, so the forward returns this exists to
collect could never span more than one session. The workflow holds
`contents: write` and a `concurrency` group for that reason, retries a rejected
push by rebasing, and falls back to an artifact if the push still fails —
market data is live-only, so a discarded snapshot cannot be re-fetched.


### Checking it

```bash
git clone --branch v2.4.0 https://github.com/spicyChicken59/design-system /tmp/design-system
node tools/dashboard_smoke.mjs        # /tmp/design-system is on its search path
```

Opens the real page in headless Chromium and asserts what it promises. Offline by
construction: `docs/` is served locally and every CDN request is answered from a
design-system checkout on disk. Needs playwright's chromium; it is not a repo
dependency, and the script exits 0 with a note if chromium is missing.

**It is pinned to the fixture.** Run against a real six-session run it scores
67/80 with no page errors — the page renders pipeline output fine — but a dozen
of its checks are assertions about the fixture's particular contents (25 scored
and 5 shown, chart paths that 404, a non-empty gated list, a fallback row), and
two of them *throw* on a first-ever run rather than failing: a history with no
forward returns yet reaches `money(null)`, and a run where Claude scored
everything has no `.sc-chip--warn` to measure. Whoever commits a real run over
the fixture has to reckon with that first; it is a change to
`tools/dashboard_smoke.mjs`, which step 9 deliberately did not touch.

## Tuning

- Scan universe: `data/symbols.txt` — a hand-curated starter list, not the whole market
- Thresholds (price floor, gain %, share-volume floor), the data `feed`, and a
  `session_date` override: `ScanConfig` in `src/scanner.py`
- 2LYNCH pass criteria: `src/lynch.py`
- Gate strictness / shortlist size / Claude-call cap: constants at the top of
  `src/pipeline.py`. `TOP_N` is the EMAIL's size and nothing else — every scored
  candidate is archived whatever it says
- How much history the ledger keeps, and how long a pending outcome is chased:
  `MAX_RUNS` and `FILL_WINDOW_RUNS` in `src/ledger.py`
- Scoring rubric the AI follows: `knowledge/strategy.md` — edit this file to change how Claude judges setups; no code changes needed
- Model: set `CLAUDE_MODEL` env var (default `claude-sonnet-4-6`)

## Costs and limits

- Market data: free (Alpaca). The scan now asks for `delayed_sip` rather than
  taking the plan default, so it reads consolidated volume instead of IEX's
  single-venue slice — see `.env.example`, and note this is unconfirmed against
  a live account. If the account cannot serve that feed the run aborts with a
  named error rather than returning an empty shortlist. A 230-symbol scan takes
  under a second inside
  the Actions runner; well within the 55-min timeout. Step 9 adds one more bars
  request per 100 candidates still waiting on a forward return — in practice one
  or two a run, on the same free feed.
- Claude: ≤25 scoring calls/run with one chart image each — a few cents/day
  on Sonnet.
- GitHub Actions: free tier covers 2 runs/day comfortably (private repos get
  2,000 min/month; ~40 min/day used).

## Notes

- The data layer is Alpaca (`_download_batch` in `src/scanner.py`). If the free
  chosen feed proves too thin once the volume threshold is relative, swapping that
  one function for another provider leaves the rest of the pipeline unchanged.
- Every run archives **every scored candidate** — not the five that went out —
  three times over: `results/*.csv` (gitignored, uploaded as a 30-day workflow
  artifact), `docs/data.json` (the dashboard's snapshot of that run) and
  `docs/ledger.json` (the record, with forward returns filled in by later runs).
  The ledger is the dataset the AI rankings were always meant to be checked
  against — the Phase-2 item in the original doc — and reading it is how you
  find out whether the score predicts anything. See "Does the history actually
  accumulate?" above for what CI still has to change before it does.
- Output is screening for human review, not trading advice.
