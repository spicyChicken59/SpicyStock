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
        │                              top 70% of the day's dollar volume —
        │                              the bottom 30% are ARCHIVED as refused,
        │                              not dropped (round 5)
        ▼  (a handful on a 230-name universe)
Layer 2  2LYNCH checklist (code) ..... 2 first/second burst · L linear prior move
        │                              Y young trend · N narrow consolidation
        │                              C calm pre-burst day · H close near high
        │                              hard gate: ≥3/6 passes, top 25 kept
        │                              plus one veto, which outranks the count:
        │                              never after 3+ consecutive up days
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
| costs | ~25 Claude calls, ~$0.15 | nothing |
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

**Then, before the first scheduled night, rehearse the boundaries once from
your own machine:**

```bash
set -a; . ./.env; set +a
python tools/live_check.py            # ~$0.02 and one test email
python tools/live_check.py --no-spend # the free checks only
```

It asks each boundary exactly one question through the pipeline's OWN code —
`_download_batch()` for Alpaca, `score_candidate()` over a chart `render_chart()`
drew for Claude, `deliver()` for Resend — so a pass means the nightly run's own
calls work. It tells a wrong key from a wrong feed (401 vs 403, the way
`run_scan()` does), reports whether the feed carries today's session, whether
Claude honours `cache_control` and whether the cache actually hits on a second
call, and whether Resend accepts `RESEND_FROM`. Every check is exercised offline
in `tests/test_live_check.py`, including the one where `--no-spend` must NOT
print READY over boundaries it never tried. The one thing it cannot try is the
commit-back push, which only Actions can run: watch the first evening run's
"Persist the run" step for that.

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
pytest tests/                   # 916 tests, no network or API keys needed
```

Every **evening** run — `--dry-run` included, since `--dry-run` skips only the
email — rewrites `docs/data.json`, updates `docs/ledger.json` and writes PNGs
into `docs/charts/`. A four-ticker smoke test therefore replaces whatever
`docs/data.json` held with a four-ticker run — the hand-authored fixture on a
fresh clone, last night's real run once `evening.yml` has committed one back.
`docs/ledger.json` gains a run too — one row per named ticker, marked with the
universe it scanned (`runs[].universe` says `named on the command line`) so the
record can tell it from a real night, but a row all the same: the next evening
run on another session reads it as history, and `git add docs` would commit it.
Put both files back with

```bash
rm -f docs/ledger.json && git checkout -- docs/
```

— the ledger is removed first because on a fresh clone it is untracked, so
`git checkout` would leave it, and the first `git pull` after `evening.yml`
commits a real one then refuses to overwrite it. A **morning** run writes
nothing at all, so it cannot disturb either file — but it will refuse to read
the fixture, which is what you will see if you run one before an evening run
has published anything.

## The dashboard

`docs/index.html` is a static page served by GitHub Pages from `docs/`. It fetches
`docs/data.json` in the browser and renders it — no server, no build step, no
framework. **An evening run writes that file at the end of every run** (step 9,
`src/ledger.py`), together with `docs/ledger.json` and the chart PNGs — which
are **not** committed (`.gitignore` blocks `/docs/charts/`), so the published
page has no images and every chart slot explains that instead. Open the page
from a checkout that has just run the pipeline and the same slots fill in. A
chart is ~57 KB and a night renders up to 25 of them: committing them is about
360 MB a year of history that does not delta-compress and cannot be taken back
out, and one file per ticker with no session in it cannot prove which run drew
it anyway. `docs/data.json` is whatever the last run wrote. On a fresh clone
that is the hand-authored fixture — a byte-for-byte copy of
`tests/fixtures/data.json`, which `tools/make_fixture.py` generates — and it
says so in its own `run.fixture: true`, which is what raises the "sample data"
banner at the top of the page. The first evening run `evening.yml` commits back
replaces it with a real run, `run.fixture` goes `false`, and the banner
disappears; nothing in CI expects the file to stay a fixture, because a guard
that has to be defeated to ship is worse than none. The canonical fixture stays
at `tests/fixtures/data.json`, where `tools/check_fixture_fresh.py` guards it
against its generator — and, for as long as `docs/data.json` still claims to be
the fixture, guards that copy against the canonical one.

It shows the run's funnel (universe → bursts → 2LYNCH gate → scored → shortlist),
**every candidate the run scored** rather than the five that went out by email, each
one's 2LYNCH checklist with its measured values, which day of its setup it is
(or that the record cannot say, and why — never a silent blank), what was done
with the name the last time it was seen, and — for every score — whether
Claude produced it or the offline checklist fallback did. A fallback score can no
longer outrank a real one: `score_all` sorts on provenance before score, so every
Claude score ranks above every fallback whatever the numbers say. It is labelled
everywhere it appears and called out at the top of the page.

### What the page answers, and what it refuses to answer

Until step 11 this page rendered one night. `docs/ledger.json` had been
accumulating every scored and gated candidate since step 9, and none of it
reached the only public surface this project has — so the question the whole
thing exists for, *does a higher score earn a higher forward return*, could not
be asked here at all.

It leads the page now, above the funnel, with four more views under it:

| the question | where | counted over |
|---|---|---|
| Does a higher score earn a higher return? | `evidence.by_score`, banded by the rubric's own verdicts | setups |
| Which 2LYNCH check predicts anything? | `evidence.by_check`, passed against failed | setups, every burst the scan found |
| Does a streak pay — is day 3 worth more than day 1? | `evidence.by_day` | **appearances** |
| Is it getting better or worse? | `evidence.by_month` | setups |
| What happened the last times this name burst? | `evidence.by_ticker`, plus `docs/ledger.json` on request | setups |
| **Did the picks beat what the strategy refused?** | `evidence.refused` against `evidence.overall`, under the score-band table | setups |

The last row is the north star's own question — "proven from its own record
that its picks beat the alternative" — and until it existed the page measured
the picks against the claimed band and against each other, never against the
names the strategy said no to, which the ledger has archived with the same
forward returns since 3.3. The page states a direction only when BOTH sides
clear `min_setups` at the longest horizon, and always prints both n's.

Alongside those six, the block carries what a reader needs to interpret them:
`evidence.record` (how many runs, sessions and setups are behind everything
here), `evidence.overall` (the same measurement over every scored setup), five
disjoint populations — `evidence.shortlist` and `evidence.rest` (the names that
went out by email against the scored ones that did not), `evidence.refused`
(what the checklist or an absolute rule rejected), `evidence.crowded_out`
(cleared the gate, never scored because the call budget filled — kept apart
from the refusals so a full night cannot pad the control with names the
screener liked) and `evidence.illiquid` (what rule 6 refused for dollar volume
below the session's floor — kept apart from the refusals for the opposite
reason: those forward returns are bar prices on names the rule says are too
thin to be bought at them, so they are shown beside the control and never in
it) — plus `evidence.universe`, the benchmark rung (not a population of
setups but the whole universe's move paired with each of them) and
`evidence.rules`, which says how many distinct sets of rules the record spans,
which keys differ between them, and how many runs predate the fingerprint
entirely: **a mean across runs is a mean over one strategy only while `sets`
is 1**, and a run carrying no fingerprint is not a run that agrees with this
one — `evidence.horizons` (which sessions after the
burst were measured) and `evidence.band` (the range the strategy claims).

**`+3d` and `+5d` are the horizons that matter, and the page says so on every
number.** They are what this strategy trades — the burst is entered on day 1,
held three to five sessions and exited — so `+1d` is an early read and never
the result. Every mean carries the `n` of *its own* horizon, because a burst
three sessions old has a `+3d` and no `+5d`, and one row count beside all three
would attach a `+1d`-sized sample to a `+5d`-sized answer.

**Below `evidence.min_setups` setups the page refuses the rate.** The number is
still printed — hiding it would be its own dishonesty — but it is marked *not
enough data*, and the sentence a reader takes away leans only on bands that
clear the floor. Thirty is not calibrated from this project's own numbers,
which would be circular: it comes from the claim being tested. Bonde says a
burst runs 8–20% over three to five sessions, so the difference that matters is
the ~8 points between "nothing happened" and the bottom of that band, and at
n=30 the interval around a mean is comfortably narrower than that gap for any
dispersion this strategy plausibly has. It is a floor on *arithmetic*, not a
claim of significance — thirty overlapping momentum bursts in one market regime
are not thirty independent draws, and the page says so where it prints the
number.

**One view counts appearances rather than setups, and has to.** Everything else
is per setup, which is `mean_returns()`'s rule: a name that bursts on five
consecutive sessions is one move measured five times. But a setup's *leading*
row is day 1 by construction, so grouping setups by day number would put every
row in one bucket and answer nothing. "Does a streak pay" therefore counts each
appearance, its windows overlap, and the page discloses that rather than hiding
it.

**Why the aggregation is Python and not JavaScript.** Every number above is an
average over setups, and that rule is a definition that lives in
`src/ledger.py`. A second implementation of it in the browser is precisely the
defect this project has already shipped twice — a checklist whose two copies
disagreed, and a fixture promising a contract the pipeline did not write. So
`evidence()` computes it at write time and `docs/index.html` renders it. The
cost, named: the page can only ask what the run answered. A reader who wants a
cut nobody anticipated reads `docs/ledger.json`, which is published beside it.

**The page fetches that file only when asked.** `docs/data.json` carries the
summary; the per-name detail — every session a ticker burst on, with the score
and what followed — needs the whole record, which projects to about 14.03 MB raw
and **1.08 MB gzipped** after a full year. That is not a thing to spend on every
visit for a view most readers never open, so the "load every burst of every
name" button is the only second request this page makes.

Those two numbers were 8.8 and 0.59, and they were stale: the 3.3 audit added
`context` to both row types and nobody re-measured, because re-measuring meant
building an eleven-megabyte file by hand. `python tools/measure_ledger.py` builds
one now — real rows from the generated history, real row counts from the
canonical one-night fixture, and `src.ledger`'s own writer, since `indent=2` is
most of the raw size and a compact estimate is not the file a browser fetches.
`tests/test_docs_are_true.py` checks that what it prints is what this paragraph
says, so the next person to grow a row does not have to remember. A 404 there is the normal state until `evening.yml`
has committed a run back, and it is reported as a fact about the file.

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
  A burst that went unscored carries `reason`: `liquidity_floor` (rule 6
  refused it in the scan, for dollar volume below the session's percentile
  floor, before the checklist saw it), `veto_up_days` (an absolute rule
  refused it, whatever the checklist said), `lynch_gate` (it failed the
  checklist) or `score_cap` (it passed and fell outside `MAX_TO_SCORE`). The
  four are different facts and no surface may collapse two of them: a vetoed
  burst may have passed 6/6, so calling it a gate rejection states the
  opposite of what happened, and a name below the floor was never measured
  against the checklist at all. `run.gate.vetoes` names the absolute rules that
  run applied, and `run.liquidity` records the floor (`pctile`, `floor` in
  dollars, `refused`), so a snapshot written before either existed is not
  described as having enforced it. The liquidity refusals were the one class
  the record did not hold until round 5: `apply_liquidity_gate()` logged them
  and dropped them, so on the documented four-name smoke test the thinnest
  name vanished and the funnel counted the other three as everything found.
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
  `scored`, or the reason it never was (`liquidity_floor` — rule 6 refused it
  before the checklist saw it; `veto_up_days` — an absolute rule
  refused it; `lynch_gate` — the checklist rejected it; `score_cap` — it passed
  and the run had already sent its limit of candidates to Claude). A
  streak counts every session the scan found a burst on, gate rejections
  included, which is why that field exists: "not scored" covered a rejection
  and a model outage with one phrase. The email and the dashboard print one
  vocabulary for these: the gated table's "why" cell reads the same map as the
  streak line and as `src/emailer.py`'s `LAST_OUTCOME`, because it used to say
  "passed, over the call cap" beside a line on the same page naming a "scoring
  cap" — two names for one mechanism, neither explained anywhere.
- `evidence` is the whole **record's** view rather than this run's: every block
  in it is computed over `docs/ledger.json` by `src/ledger.py`'s `evidence()`.
  Every mean is over setups except `evidence.by_day`, which counts appearances
  and says so. Every mean carries the `n` of its own horizon, and `enough` is
  that `n` against `evidence.min_setups` — a page must not decide for itself
  whether a number may be read as a rate.
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

Regenerate the fixture with `python3 tools/make_fixture.py tests/fixtures/data.json`,
and copy it over `docs/data.json` only while that file is still the fixture.
The generator reads `data/symbols.txt`, `ScanConfig` and — since step 9 — the
invariant list itself from `src/ledger.py`, so it cannot emit a run this scanner
could not produce, nor promise a contract different from the one the pipeline
writes; `tools/check_fixture_fresh.py` regenerates it and fails the build if the
canonical file has drifted. The chart PNGs the fixture names do not exist, so the
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
- `runs[].rules` is **every number this screener's rules turned on when that
  run was made**: the scan's strategy thresholds, every threshold and window
  the checklist names, the vetoes in force and the gate. It is derived rather
  than listed — `src.pipeline.rules_fingerprint()` walks what `src.lynch`
  names, its `WINDOWS`, and the `ScanConfig` fields that config itself marks
  as strategy — so a threshold added later is recorded the moment it is named.
  The trap it exists to avoid is a fingerprint that misses a number and so
  reports "same rules" across a change that altered them, which is worse than
  no fingerprint; the six checklist windows were bare literals until round 8
  named them for that reason. `MAX_TO_SCORE`, `TOP_N`, the feed and the
  universe are deliberately not in it: each is already a fact of the run block
  and none of them changes what a burst is. A run from before the fingerprint
  carries no `rules` key at all — absent, never null, because the contract
  distinguishes "this run had none" from a shape no writer produces.
- `runs[].benchmark` is the **whole universe's equal-weight return from that
  session** — `d1`, `d3`, `d5` from the close and `from_open` from the next
  open, with `n1`/`n3`/`n5` the number of symbols behind each — filled by a
  later run from the frames its own scan already read, at no extra request.
  `evidence.universe` pairs every scored setup with its own session's
  benchmark, so its outcomes are the alternative "buy anything in the universe
  that day" over the same sessions in the same proportions as the picks. It is
  a curated large-cap list as it stands today, so the comparison carries
  survivorship bias in the benchmark's favour, and the page's rung says so.
- `forward_returns.from_open` is the **same three closes divided by the next
  session's open** — the earliest price a reader of the 18:16 ET email could
  have paid. The two bases answer two questions about one move: what the
  setup did, and what acting on it could have had. Measured, not argued: burst
  close 100, next open 110, next close 111 records `d1` +11.0% and
  `from_open.d1` +0.91%. Both are paper prices from one venue's official
  prints with no slippage, so the open basis is a better upper bound and not a
  fill. Every run mean and every evidence outcome carries both, the open basis
  nested under `from_open` with its own `n` and its own `enough_from_open`; the
  page shows one basis at a time, chosen by one control, and names it in every
  heading that carries a return. A row or a run from before this basis existed
  has no `from_open`, which the page reads as "not measured", never as zero and
  never as the close-basis number under an open-basis label.
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

Locally, yes: `docs/ledger.json` is written by every EVENING run and kept for
260 runs. A morning run writes nothing at all — it is a follow-through pass, as
the table above says — so "every run" here and in the dashboard section meant
every discovering run, and now says so.

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

**Which nights get kept is the exit code, and 1 was hiding two of them.** A
`run:` step fails on any non-zero code, and an `if:` with no status function has
`success()` ANDed into it — so the persist step originally ran on clean nights
only. Exit 2 is a run that WORKED and noted a problem: it scanned, rendered,
paid for up to 25 Claude calls, wrote both files complete and mailed the
shortlist. One chart that will not render is enough to earn it, as is one Claude
fallback, a mode/clock disagreement or >10% stale symbols — this repo's own
30-session fixture is 2 degraded in 30. Every one of those nights was thrown
away. And the record is written *before* the email, so a run that dies
delivering — an unverified `RESEND_FROM` domain is the likely one — is in the
same position and exited 1 for it, the same code as a preflight that spent
nothing. It exits 3 now. The step captures the code and re-raises it last, after
the persist and the artifact upload, so the job's colour is unchanged: 2 and 3
are still red. Only the record is rescued.

That retry only started existing in this round. `git pull --rebase` sat bare in
the loop, and under Actions' `bash -e` a failing pull ends the step — so the
first rejected push aborted it and iterations 2 and 3 never ran. It is `if !
git pull --rebase ...` now, with a conflicting rebase aborted and named rather
than left half-applied. Traced with `bash -ex` against a stub `git`, which is
how the `git add` bug below was found too.

**Nothing has ever exercised it, and not for the reason this paragraph used
to give.** The `git add` fix is real and a test now guards it. But no run has
reached the push, or the add, or the commit-back step at all: `evening.yml`
has fired six times, every one of them scheduled — three no-ops from the DST
guard and three that died in preflight for want of secrets — and a failed
pipeline step skips the persist step entirely. This said "every run before it
aborted at the add", which describes something that has never happened once.
The bug was real in the code and it was fixed before that code was ever the
tip of `main`; the nightly failure it supposedly caused is invented. Streaks
and the whole input of the morning run rest on this step working, so the first
evening run that gets past preflight is worth watching in the Actions log.

Since step 10 that commit-back carries a second job: it is what the 8:30 AM
follow-through reads, and it is what makes a streak possible at all. Remove it
and both features fail quietly in the same way — every night's candidates would
be day 1 of a setup, forever, because the file that knows otherwise would never
survive a container.

**It would not have worked until step 10, and nothing said so.** The step ran
`git add docs results`, and `results/` is gitignored on purpose — `git add` on
an ignored path exits 1, which under Actions' `bash -e` would have aborted the
step before the commit. Would have: that version lived only on the rebuild
branch and was fixed before the branch merged, so no scheduled run ever checked
it out, and none has reached this step under any version. The defect is real
and the test guarding it earns its place; what is not real is the nightly
silent failure an earlier draft of this paragraph described, in which `docs/`
was staged and died with the container on every run while the workflow's own
comment claimed the history was being kept. It is
`git add docs` now, and `tests/test_docs_are_true.py` checks that no path this
workflow stages is one `.gitignore` blocks, because reading the two files side
by side is exactly what missed it the first time. The `results/` artifact upload
now runs on every scan that finished, pass or fail, rather than only on a failed
push — which is what the note below has always claimed. Finished, not `always()`:
a cancelled run would otherwise upload an artifact too, and a cancelled run did
not happen.

**The backup-cron guard counts published sessions, not uploads.** It used to
count any `evening-*` artifact created on today's UTC date, and both halves of
that were wrong: the artifact step uploads on failure too, so a preflight
failure — or a Run-workflow click at lunch to test the secrets — silenced that
night's cron (read off the Actions API: both failed 4 Sep runs left one); and
an EST night starts at 23:16 UTC, so a run over ~44 minutes uploaded under
tomorrow's UTC date and silenced the following night. A run that published
names its artifact `evening-<session>-<id>`, a run that did not is
`evening-failed-<id>`, and the guard counts only the first shape against the
session a run tonight would scan. Traced through the guard's own shell against
a stub `gh` running its real `jq` filter, six scenarios, in
`tests/test_docs_are_true.py`.


### Checking it

```bash
git clone --branch v2.4.0 https://github.com/spicyChicken59/design-system /tmp/design-system
node tools/dashboard_smoke.mjs        # /tmp/design-system is on its search path
```

Opens the real page in headless Chromium and asserts what it promises. Offline by
construction: `docs/` is served locally and every CDN request is answered from a
design-system checkout on disk. Needs playwright's chromium; it is not a repo
dependency, and the script exits 0 with a note if chromium is missing.

**Three data sources, one page.** It runs 190 checks, and which file each one
reads is the point:

- **`tests/fixtures/data.json`** — the canonical one-night fixture, served
  under `/f/fixture/`. Most of the checks live here, because they know the
  fixture's contents: 25 scored and 5 shown, a fallback that outranks a real
  score, chart paths that 404, a non-empty gated list, the streak states one
  night can hold at once. 29 mutated copies of it are served
  under `/v/<name>/` for the states one night cannot hold at once, beside one
  more name, `nodata`, that serves no document at all. This said six, then
  eight, while `VARIANTS` in the smoke test grew past both, so the script now
  checks that number the way it checks its own count of checks.
- **`tests/fixtures/history/`** — thirty consecutive runs written by the real
  pipeline (`tools/make_history.py`, see `tests/fixtures/README.md`): forward
  returns filled in by later runs, a night the scorer was down, a chart that
  would not render, repeats on consecutive sessions, the last week still
  pending. Every expectation is computed from the file the page is reading.
- **`docs/`** — whatever the last run wrote, exactly as GitHub Pages serves it,
  opened last with only the checks that hold for any run: it opens, its rows
  add up to its own funnel, it says whether it is sample data, and it logs no
  error. The fixture until the first commit-back, a real run after it — and
  the script no longer has an opinion about which.

The record-wide views are checked on both fixtures, which hold opposite
states: the one-night fixture's evidence block is entirely pending, so the page
must say the view is *correct and empty* rather than draw a flat line at zero;
the thirty-run one is populated, so the bands, the refusals, the two-colour
legend and the lazy record fetch all have something to assert against. A third
variant, `/v/noevidence/`, serves a snapshot with the block removed — a file
written before the pipeline published one — and the page has to say which kind
of nothing that is instead of hiding the question.

That split is what closed the note this section used to carry: the script was
pinned to the fixture's contents *and* read `docs/data.json`, so the first real
run committed back would have failed a dozen checks and thrown in two
(`money(null)` on a history with no closed session; a light-mode contrast
measurement on a fallback chip a fully-scored run does not have). Both are
null-safe now, and neither runs against `docs/` at all.

**It does check the streak line**, on the states the one-night fixture carries:
that a shortlisted pick states its streak whatever the streak is, that a null
`day` reports the record it is unknown *over* rather than the word "unknown",
that it never renders as day 1, that a scored last appearance keeps its
verdict, and that a repeat says which *setup* it is day N of. Those five are the
wordings the email and the page had drifted apart on, so they are asserted here
rather than watched in a browser once. The gated table's "why" cell is asserted
the same way, against the sentence `src/emailer.py` prints for that outcome —
scoped to the cell, because a row's streak line says what happened to the name
*last* time in those same words, and a row-level match counts the wrong thing.
The history pass adds the repeat the ledger really computed — "day 2 of this
setup" on a name that burst two sessions running — rather than one typed into
a fixture.

What is still not checked is any streak state neither fixture holds —
`history_unreadable`, `history_undated`, a row with no `streak` field at all.
Those are covered on the email side in `tests/test_emailer.py` and in
`src/ledger.py`'s own tests; on the page they were read back from the DOM
against a hand-made `data.json` and agree, but that check is not committed.

## Tuning

- Scan universe: `data/symbols.txt` — a hand-curated starter list, not the whole market
- Thresholds (price floor, gain %, relative-volume floor and its lookback, the
  dollar-volume percentile gate), the data `feed`, and a `session_date`
  override: `ScanConfig` in `src/scanner.py`. There is no share-volume floor;
  step 4 deleted it, and this bullet named the deleted knob and none of the
  three that replaced it
- 2LYNCH pass criteria: `src/lynch.py`
- The two rules that are not checks, and the note beside them saying why not:
  `MAX_CONSECUTIVE_UP_DAYS` (an absolute veto) and `BREAKDOWN_PCT` /
  `BREAKDOWN_LOOKBACK` (measured, sent to the model, rejecting nothing), also
  in `src/lynch.py`. Neither is a seventh checklist item on purpose — the gate
  is 3 of 6, so adding to the six would quietly make it 3 of 8 and weaken it
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
  named error rather than returning an empty shortlist. A 230-symbol scan is
  seconds, not minutes, and is nowhere near the 55-min timeout — but "under a
  second", which this said, is not supported: 0.97s is what the scan costs
  driven through the offline doubles, and those do strictly LESS work than
  alpaca-py, with no HTTP, no JSON decode and no BarSet construction. That is a
  floor on the real cost, measured, and the real path adds a network round trip
  and the SDK's own decode on top of it. Step 9 adds one more bars request per
  100 candidates still waiting on a forward return — in practice one or two a
  run, on the same free feed.
- **One bars request per 100 names is wrong, and already is.** alpaca-py sends
  `page_size=10_000` and loops on `next_page_token`, so the request count is set
  by TOTAL BARS rather than by `batch_size`: a 100-symbol batch over the scan's
  own 297-session window is ~28,600 bars and three GETs. Counted through a fake
  transport, not read. The practical consequence is that raising `batch_size`
  to cut requests — the obvious move when the universe widens — buys almost
  nothing at this window.
- Claude: ≤25 scoring calls/run with one chart image each — **about $0.15 a
  run, so roughly $37 a year** at 252 sessions, and only on the evening run.
  This said "a few cents/day", which is out by about 5x. Measured rather than
  guessed: a real `render_chart()` PNG is 869x622, which is 721 image tokens by
  Anthropic's documented (w x h) / 750 rule; `knowledge/strategy.md` is ~1,590
  tokens of system prompt and the metrics block ~390, so ~2,700 input tokens
  and ~120 out per call, at claude-sonnet-4-6's $3/$15 per Mtok. The text
  halves are chars/4 estimates — `count_tokens` needs a network call this
  sandbox cannot make — so treat the figure as ±30%, which does not rescue "a
  few cents".

  **The system prompt is 59% of every request and is byte-identical on all 25
  calls**, so it is sent with `cache_control` and read from cache after the
  first. A cache write costs 1.25x and a read 0.1x — so the first call pays
  0.25x more than it would have and every call after saves 0.9x, which makes
  break-even the second call (1.28 calls) and a full night 41% cheaper: the
  $0.25 this paragraph used to quote against the $0.15 above. (This said 1.4
  calls, 43% and $0.13: 1.4 is 1.25 over 0.9, which charges the whole write
  against the reads as if the first call were otherwise free, and the two
  money figures were rounded from different token counts. A test now does the
  paragraph's arithmetic from the numbers it states.) It needs no configuration: the
  default 5-minute window is the cheap one, and every read resets it, so a
  run's sequential calls hold the entry. `score_all()` logs what the cache
  actually did, because the saving is otherwise invisible from inside the run.

  The cap is what keeps this flat: it does NOT grow when the universe widens,
  because MAX_TO_SCORE bounds the calls and not the scan.
  The morning follow-through makes no model call and no data request at all.
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
