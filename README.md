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
        │                              written to docs/charts/ — gitignored, so
        ▼                              they stay on the machine that ran
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
Layer 6  Email ....................... HTML table, top 5, with the charts this
                                       run just rendered attached inline —
                                       the ONLY place TOP_N cuts anything
```

## The two runs

| | `evening` (6:16 PM ET) | `morning` (8:30 AM ET) |
|---|---|---|
| what it does | **discovery** — scans the session that closed today | **follow-through** — re-presents the evening run before the open |
| scans | yes, every layer above | no |
| costs | ~25 Claude calls, a few cents | nothing |
| writes | `docs/data.json`, `docs/ledger.json`, `docs/charts/` (gitignored), `results/*.csv` | nothing |
| charts | attached inline — the PNGs it just rendered | none, and the email says why |
| workflow | `.github/workflows/evening.yml` | `.github/workflows/morning.yml` |

**Why the morning run does not scan.** Before the open it has no market data
the evening run did not have — the daily bar it would read is the same daily
bar — so a "morning scan" is the evening scan repeated at a different hour, for
the identical answer, at the same cost. What it can honestly add is these names
in front of you at the hour you might act on them, each with what the record
says about it. It reads the run `docs/data.json` already holds; it does not
write to `docs/ledger.json`, because that file is the record of what was
*scanned* and a second entry for one session would count that burst twice in
every average across runs.

**And it carries no chart.** `docs/charts/` holds one PNG per ticker,
overwritten by every evening run, with the session recorded nowhere in it —
while `docs/data.json` is only rewritten at the end of a run. An evening run
that rendered its charts and then died before publishing leaves the two a
session apart, and the morning pass, which resolved its image by bare path,
then paired last night's numbers with tonight's picture and said nothing. The
model is told to trust the chart over the numbers and a reader will do the
same, so the picture is dropped and the cell says why. The evening email is
unaffected: it attaches the PNGs it rendered moments earlier, in the same
process.

**A morning run that has nothing fresh to show says how stale it is, in the
subject line.** Its whole input is the snapshot the last evening run published,
so the interesting failure is that nothing published — and "nothing published
last night" and "nothing has published for three weeks" must not arrive looking
the same. There is no holiday calendar here, deliberately (an approximate one
used to make a confident claim is a worse defect than the one it replaces), and
none is needed: **none of the market's scheduled holidays are adjacent.** So a
gap of one session is genuinely ambiguous and the red band names both
explanations; from two sessions up, at least one of those days was a scheduled
session and a holiday cannot account for the silence, so the band says so
plainly — keeping one clause for an *unscheduled* closure, which has run to
consecutive sessions (9/11, Sandy, the 2007 day of mourning after New Year's
Day) and is news the reader already has — and the subject escalates
from `DEGRADED — ` to `NOTHING PUBLISHED IN 15 SESSIONS — `. The heading names
the session the rows are actually from, for the same reason: it used to read
"follow-through watchlist for TODAY" over a snapshot fifteen sessions old.

**The mode is a promise about the clock, and it is checked.** An evening run
declares that today's session has closed; a morning run declares that it has
not. When the clock disagrees — `evening` before 16:15 ET, `morning` after it —
the run is **degraded**, not refused: it still does its work and still mails,
with the reason in the red band, in `docs/data.json`'s `run.errors`, and in exit
code 2. Not in `docs/ledger.json` — `add_run()` records a status word per run
and not the sentences behind it, and this paragraph claimed otherwise for a
whole step. A morning run writes neither file, so for that mode the email and
the exit code are the whole record.
Refusing would trade a mislabelled email for no email, and no email is
indistinguishable from a market holiday. Whatever the clock says, the session
that was actually read is named in the subject line and above the table — and,
on the evening run, which is the only one that writes a CSV, in that file's
name too. The label cannot quietly become a different day.
`SCAN_SESSION_DATE` is exempt: a pinned session is you overruling the clock on
purpose, and a deliberate backfill is not a mistake.

**Day N of this setup.** Every burst the evening run reports carries a
`streak`: whether this name has appeared before, when it last did, what it
scored then, and which session its current run of appearances started on. Two
appearances belong to the **same setup** when the second lands within
`MAX_STREAK_GAP_SESSIONS` (= `max(HORIZONS)` = 5) sessions of the first — the
window this pipeline already commits to as the one a burst's outcome is decided
over, so a second burst inside it happens while the first is still being judged.
A ticker reappearing a fortnight later is day 1 of something new, not day 12 of
something finished. Sessions, not calendar days, and weekends-only arithmetic:
a holiday makes a gap look one session longer, which can only *break* a streak,
never invent one. The rule and its reasoning are in `src/ledger.py`.

Reading that history can never kill a run. An unreadable `docs/ledger.json`
degrades the run and publishes, on every row, a `streak` whose `day` is null
and whose `unknown_reason` is `history_unreadable` — never `streak: null`,
which is a fourth state meaning the run recorded nothing at all, and never a
day number. "We have never seen this name" and "we could not read the file
that would know" are different sentences, only one is a claim about the
market, and the email and the dashboard say different words for each.

## One-time setup

Push this repo to GitHub and add six repository secrets — these are exactly
what `.github/workflows/evening.yml` reads, and `.env.example` explains each:

`ANTHROPIC_API_KEY`, `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`,
`RESEND_API_KEY`, `RESEND_FROM`, `EMAIL_TO`

Both pipeline workflows then fire on weekdays and can be triggered manually
from the Actions tab. `morning.yml` is passed only the three delivery secrets,
because the follow-through pass runs neither the scanner nor the scorer and
`preflight()` asks the mode which layers it will use before demanding a key.

> **Note:** the four files in `.github/workflows/` are `evening.yml`,
> `morning.yml`, `secret-scan.yml` and `tests.yml`. The evening scan fires at
> 6:16 PM ET — 22:16 UTC under EDT, 23:16 UTC under EST — and the morning
> follow-through at 8:30 AM ET (12:30 / 13:30 UTC). Both crons of each pair are
> registered and a guard no-ops the one that does not match today's ET offset,
> because GitHub crons are UTC and do not follow US daylight saving.
> `evening.yml`'s crons are labelled backup-only for an external trigger you
> should not set up; the guard works standalone.
>
> `morning.yml` depends on `evening.yml` having committed `docs/` back — see
> "Does the history actually accumulate?" below. On a repo where that has never
> happened it finds the hand-authored fixture, refuses it by name and mails a
> degraded notice rather than a watchlist of invented tickers.
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

# Re-present the run above, the way the 8:30 AM job would. Scans nothing,
# reads docs/data.json, needs no Alpaca or Anthropic key. --tickers is
# refused here rather than ignored, because this mode does not scan:
python -m src.pipeline morning --dry-run

# Seed the history from a past session (its forward returns resolve at once):
SCAN_SESSION_DATE=2026-08-24 python -m src.pipeline evening --dry-run

# Offline logic tests (no network / API key needed):
pip install -r requirements-dev.txt
pytest tests/                   # 645 tests, no network or API keys needed
```

Every **evening** run — `--dry-run` included, since `--dry-run` skips only the
email — rewrites `docs/data.json`, updates `docs/ledger.json` and writes PNGs
into `docs/charts/`. A four-ticker smoke test therefore replaces the committed
fixture with a four-ticker run. `git checkout docs/data.json` puts it back;
`tools/check_fixture_fresh.py` tells you whether it needs putting back. A
**morning** run writes nothing at all, so it cannot disturb the fixture — but
it will refuse to read it, which is what you will see if you run one before an
evening run has published anything.

## The dashboard

`docs/index.html` is a static page served by GitHub Pages from `docs/`. It fetches
`docs/data.json` in the browser and renders it — no server, no build step, no
framework. **The pipeline writes that file at the end of every run** (step 9,
`src/ledger.py`), together with `docs/ledger.json` and the chart PNGs — which
are **not** committed (`.gitignore` blocks `/docs/charts/`), so the published
page has no images and every chart slot explains that instead. Open the page
from a checkout that has just run the pipeline and the same slots fill in. A
chart is ~57 KB and a night renders up to 25 of them: committing them is about
360 MB a year of history that does not delta-compress and cannot be taken back
out, and one file per ticker with no session in it cannot prove which run drew
it anyway. The copy committed here is still the hand-authored fixture from
`tools/make_fixture.py`, and it says so in its own `run.fixture: true`, which is
what raises the "sample data" banner at the top of the page; a real run writes
`false` and the banner disappears. The first run whose output is committed
replaces it.

It shows the run's funnel (universe → bursts → 2LYNCH gate → scored → shortlist),
**every candidate the run scored** rather than the five that went out by email, each
one's 2LYNCH checklist with its measured values, which day of its setup it is
(or that the record cannot say, and why — never a silent blank), what was done
with the name the last time it was seen, and — for every score — whether
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
- Every burst carries `streak` — `day`, `unknown_reason`, `first_seen`,
  `last_seen`, `last_score`, `last_verdict`, `last_outcome`, `seen_before`,
  `history_from`, `history_sessions`.
  `day` is 1 exactly when `first_seen` is the burst's own session, and
  `last_seen` is `null` exactly when `seen_before` is 0. **A null `day` is not
  day 1**: it means the record cannot say, and `unknown_reason` says which of
  `no_history`, `history_undated`, `history_unreadable` and
  `window_not_covered` left it null.
  Every surface prints that state in words — the email row, both dashboard
  tables and the pick card — because a row that renders nothing is read as a
  first sighting, which was the state of two of those three.
  `history_from` is the session of the oldest run the ledger holds and
  `history_sessions` is how many distinct sessions it holds runs for: both are
  facts about the *record*, the same on every row of a run, and they are what
  an unknown `day` is unknown **over**. Without them the commonest unknown was
  an inversion — a day number is withheld whenever the chain of appearances
  reaches the oldest run in the file, which is exactly what an unbroken streak
  does, so a name that burst on all eight sessions the ledger holds read
  "streak unknown" while a name that took a week off and burst twice read
  "day 2". The arithmetic is right and stays; with the pair, the surfaces say
  *"burst on 8 of the 8 sessions in the record, which begins 2026-08-20 — this
  setup may have started before it"* instead of "unknown".
  `last_outcome` is what happened to the appearance `last_seen` names:
  `scored`, or the reason it never was (`lynch_gate` — the checklist rejected
  it; `score_cap` — it passed and the run had already sent its limit of
  candidates to Claude). A
  streak counts every session the scan found a burst on, gate rejections
  included, which is why that field exists: "not scored" covered a rejection
  and a model outage with one phrase. The email and the dashboard print one
  vocabulary for these: the gated table's "why" cell reads the same map as the
  streak line and as `src/emailer.py`'s `LAST_OUTCOME`, because it used to say
  "passed, over the call cap" beside a line on the same page naming a "scoring
  cap" — two names for one mechanism, neither explained anywhere.
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
page degrades to an explained empty frame — and that is the expected state for
the published page whether the file is a fixture or a real run, because the PNGs
are not committed. A real run writes them next to the file that names them, for
whoever is at that machine.

### Forward returns, and where the history lives

`docs/data.json` describes one run — the newest — so it can never hold the
outcome of the scores in it: the burst closed at tonight's close and no later
session exists yet. The record that accumulates is **`docs/ledger.json`**: one
slim row per candidate per run (score, verdict, provenance, the six checks, the
burst's own numbers), kept for the last 260 runs, with the forward returns filled
in by later runs. `data.json`'s `runs[]` history is the per-run mean of the same
rows, which is what the dashboard's "has any of this made money yet" panel reads.
That mean is taken over **setups**, not rows: a name that bursts on five
consecutive sessions is one move measured five times, and counting it five times
weights that one move against every other name in the file. `forward_returns.n`
is the setup count the mean was taken over — the weight the dashboard averages
sessions by — and `forward_returns.rows` is what those setups were collapsed
from. The page prints both, and calls neither of them "names".

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
`contents: write` and a `concurrency` group for that reason, and retries a
rejected push by rebasing onto whatever landed during the run — three attempts,
then it fails the step loudly rather than pretending. Market data is live-only,
so a discarded snapshot cannot be re-fetched; the run's 30-day artifact holds a
copy of `docs/data.json` and `docs/ledger.json` either way.

That retry only started existing in this round. `git pull --rebase` sat bare in
the loop, and under Actions' `bash -e` a failing pull ends the step — so the
first rejected push aborted it and iterations 2 and 3 never ran. It is `if !
git pull --rebase ...` now, with a conflicting rebase aborted and named rather
than left half-applied. Traced with `bash -ex` against a stub `git`, which is
how the `git add` bug below was found too.

**Nothing has ever exercised it.** The `git add` fix is real and a test now
guards it, but no run of this workflow has yet reached the push at all: every
run before it aborted at the add. Streaks and the whole input of the morning
run rest on this step working, so the first evening run after this lands is
worth watching in the Actions log.

Since step 10 that commit-back carries a second job: it is what the 8:30 AM
follow-through reads, and it is what makes a streak possible at all. Remove it
and both features fail quietly in the same way — every night's candidates would
be day 1 of a setup, forever, because the file that knows otherwise would never
survive a container.

**It did not work until step 10, and nothing said so.** The step ran
`git add docs results`, and `results/` is gitignored on purpose — `git add` on
an ignored path exits 1, which under Actions' `bash -e` aborted the step before
the commit. `docs/` was staged and then died with the container on every run,
while the workflow's own comment said the history was being kept. It is
`git add docs` now, and `tests/test_docs_are_true.py` checks that no path this
workflow stages is one `.gitignore` blocks, because reading the two files side
by side is exactly what missed it the first time. The `results/` artifact upload
now runs on every scan that finished, pass or fail, rather than only on a failed
push — which is what the note below has always claimed, and which is also the
signal the workflow's own duplicate-run guard reads. Finished, not `always()`:
a cancelled run would otherwise upload the same artifact and tell that guard an
evening run had already happened today, so cancelling one run would silently
suppress the backup cron that exists to catch a missing one.


### Checking it

```bash
git clone --branch v2.4.0 https://github.com/spicyChicken59/design-system /tmp/design-system
node tools/dashboard_smoke.mjs        # /tmp/design-system is on its search path
```

Opens the real page in headless Chromium and asserts what it promises. Offline by
construction: `docs/` is served locally and every CDN request is answered from a
design-system checkout on disk. Needs playwright's chromium; it is not a repo
dependency, and the script exits 0 with a note if chromium is missing.

**It is pinned to the fixture.** It runs 91 checks against the committed
`docs/data.json`. Run against a real six-session run instead, it drops about a
dozen of them with no page errors — the page renders pipeline output fine —
because those are assertions about the fixture's particular contents (25 scored
and 5 shown, chart paths that 404, a non-empty gated list, a fallback row), and
two of them *throw* on a first-ever run rather than failing: a history with no
forward returns yet reaches `money(null)`, and a run where Claude scored
everything has no `.sc-chip--warn` to measure. Whoever commits a real run over
the fixture has to reckon with that first; it is a change to
`tools/dashboard_smoke.mjs`, which step 9 deliberately did not touch.

**It does check the streak line**, on the states this fixture carries: that a
shortlisted pick states its streak whatever the streak is, that a null `day`
reports the record it is unknown *over* rather than the word "unknown", that it
never renders as day 1, that a scored last appearance keeps its verdict, and
that a repeat says which *setup* it is day N of. Those five are the wordings the
email and the page had drifted apart on, so they are asserted here rather than
watched in a browser once. The gated table's "why" cell is asserted the same
way, against the sentence `src/emailer.py` prints for that outcome — scoped to
the cell, because a row's streak line says what happened to the name *last*
time in those same words, and a row-level match counts the wrong thing.

What is still not checked is any streak state this fixture does not hold —
`history_unreadable`, `history_undated`, an empty record, a row with no `streak`
field at all. Those are covered on the email side in `tests/test_emailer.py` and
in `src/ledger.py`'s own tests; on the page they were read back from the DOM
against a hand-made `data.json` and agree, but that check is not committed.

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
- What counts as one setup, for the "day N" a repeat carries:
  `MAX_STREAK_GAP_SESSIONS` in `src/ledger.py`, with the reasoning beside it
- What each run mode promises about the clock: `MODES` in `src/pipeline.py`
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
  on Sonnet, and only on the evening run. The morning follow-through makes no
  model call and no data request at all.
- GitHub Actions: free tier covers both daily runs comfortably (private repos
  get 2,000 min/month). The evening scan is the long one; the morning job is a
  file read and an email.

## Notes

- The data layer is Alpaca (`_download_batch` in `src/scanner.py`). If the free
  chosen feed proves too thin once the volume threshold is relative, swapping that
  one function for another provider leaves the rest of the pipeline unchanged.
- Every *evening* run archives **every scored candidate** — not the five that went out —
  three times over: `results/*.csv` (gitignored, uploaded as a 30-day workflow
  artifact), `docs/data.json` (the dashboard's snapshot of that run) and
  `docs/ledger.json` (the record, with forward returns filled in by later runs).
  The ledger is the dataset the AI rankings were always meant to be checked
  against — the Phase-2 item in the original doc — and reading it is how you
  find out whether the score predicts anything. See "Does the history actually
  accumulate?" above for how it survives a CI container — and for the one thing
  about that step nothing has ever exercised.
- Output is screening for human review, not trading advice.
