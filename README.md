# 4% Momentum Burst — Fully Automated Scanner

Scans a checked-in universe of 228 US common stocks each trading day, applies the
Stockbee/Qullamaggie 4% Momentum Burst strategy with the 2LYNCH quality
checklist, has Claude score the survivors (numbers, the checklist detail, what the
record already knows about the name, and a chart image), and
emails a ranked top-5 shortlist. **Zero manual steps** — no DeepVue paste,
no Google Sheet, no n8n.

See the [Tuesday readiness review](READINESS-2026-09-08.md) for the verified
operational fixes, the September 8 schedule, and the current universe/evidence limits.

## How it differs from the original spec

| Original plan | This build | Why |
|---|---|---|
| DeepVue scan, pasted by hand daily | Built-in scanner over a checked-in symbol list (`data/symbols.txt`) | The one manual step is eliminated — full automation was the requirement |
| n8n + Airtable + Google Sheets | Single Python pipeline + GitHub Actions cron | Fewer moving parts, zero hosting cost |
| GPT-5 API | Claude API (vision + text) | One model handles chart reading and checklist reasoning in a single call |
| NotebookLM knowledge base | `knowledge/strategy.md` injected as the system prompt | Deterministic, versioned, auditable — you can see exactly what rules the AI scores against |

## Pipeline

```
checked-in universe (data/symbols.txt, 228 names)
        │  Alpaca daily OHLCV, split-adjusted, SIP, batched
        ▼
Layer 1  4% burst filter ............. ≥4% gain, vol ≥ yesterday, ≥1.5x its own
        │                              50-session average, price > $4, and in the
        │                              top 70% of the day's dollar volume —
        │                              the bottom 30% are ARCHIVED as refused,
        │                              not dropped (round 5)
        ▼  (a handful on a 228-name universe)
Layer 2  2LYNCH checklist (code) ..... 2 first/second burst · L linear prior move
        │                              Y young trend · N narrow consolidation
        │                              C calm pre-burst day · H close near high
        │                              hard gate: ≥3/6 passes, top 25 kept
        │                              plus one veto, which outranks the count:
        │                              never after 3+ consecutive up days
        ▼
Layer 3  Chart render ................ 4-month candlestick + volume PNG per name,
        │                              written to docs/charts/ — gitignored, so
        │                              they stay on the machine that ran;
        ▼                              a bar with a hole in it is drawn as a
                                       gap — blanked, never spliced out —
                                       not a candidate scored blind
Layer 4  Claude scoring .............. metrics (the burst bar's own gap and
        │                              range included) + 2LYNCH detail + chart
        │                              image + what the RECORD says about this
        │                              name → score /10, verdict (A+…skip),
        │                              1-sentence reason, key risk
        │                              (strategy.md = rulebook)
        ▼
Layer 5  Archive ..................... EVERY scored candidate, plus every burst
        │                              that was not scored and why:
        │                              docs/data.json (the dashboard's snapshot),
        │                              docs/ledger.json (the record, with the
        ▼                              forward returns a later run fills in),
                                       results/*.csv (a 30-day artifact)
Layer 6  Email ....................... HTML table, top 5, with the charts this
                                       run just rendered attached inline —
                                       the ONLY place TOP_N cuts anything —
                                       and, under the funnel, what the picks
                                       of EARLIER runs returned at whatever
                                       horizons tonight's fill just measured
```

## The two runs

| | `evening` (6:16 PM ET) | `morning` (8:30 AM ET) |
|---|---|---|
| what it does | **discovery** — scans the session that closed today | **follow-through** — re-presents the evening run before the open |
| scans | yes, every layer above | no |
| costs | ~25 Claude calls, ~$0.17 | nothing |
| writes | `docs/data.json`, `docs/ledger.json`, `docs/charts/` (gitignored), `results/*.csv` | nothing |
| charts | attached inline — the PNGs it just rendered, except on a retry after a failed send | none, and the email says why |
| an empty table | says what its own scan found, unless that scan was cut short | says what the run it follows found, unless *its* scan was |
| what earlier picks did | the scorecard its own fill just measured (`run.settled`), or no such table at all | the same block, off the run it follows |
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
process — except when it is the retry of a send that failed, which drops them
and says so in the same cell, and only for the rows that really had a picture
to drop.

**The funnel adds up.** It read "4% bursts found: 6 | Refused by an absolute
rule: 2 | Passed 2LYNCH gate: 3 | Shortlisted: 3" — six minus two minus three
is one, and that one burst, the one the *checklist itself* rejected, was on no
line of the mail while its row sat in the same run's `docs/data.json` under
`reason: lynch_gate`. The absolute rules got their own line, the liquidity
floor got one and the call cap got one, each for exactly this reason: a count
that vanishes reads as a count that never existed. The checklist was the last
cut without one *at the time* — round 11 found an earlier one, between the
universe and the bursts, and gave it a line above this one — and it is the cut
the product is named after. It has one now
— "Rejected by the 2LYNCH checklist: 1", between the floor and the gate, so
the cuts read top to bottom as the subtraction a reader does — printed only
when it is not zero, like the other refusal lines, and **counted, not left
over**: every refused burst has carried its own reason word in `gated_out`
since round 5, so the evening counts the `lynch_gate` rows it is holding and
the morning counts the same rows off the record it follows, the way both mails
already count the vetoes and the floor's refusals. A remainder would have been
an attribution: a burst refused for anything outside those classes — a row
whose reason the record does not name, a reason word added in some later round
— would be reported as a checklist rejection rather than left off, and for a
veto that is the collapse this file forbids by name. A burst neither path can
name is on no line, and the empty-table cell says so in words rather than
absorbing it into a verdict. The email's funnel is where nothing said it: the
page's funnel folds these cuts into one stage caption, though its gated card
has counted them apart since round 5. What still has no line of its own is the
last drop, scored → shortlisted: both ends are printed ("Scored by Claude: 25
of 25" beside "Shortlisted: 3") but the reason, a ranking rather than a
refusal, is named on the page and not in the mail.

**A run that dies mails the same email with the failure in it, and that mail
now says what the run did before it died.** It printed "Universe: not
recorded" over a scan that had asked every symbol and been answered by every
one of them — the counts were in memory, and nothing had attached them to the
report. `run_scan()` fills its stats dict in place, so the notice reports
whatever it had reached: "Universe: 228 asked, 228 answered, none with a bar
for 2026-09-07, the newest bar among the names that missed the session is
2026-09-04", with the dropped and no-bar-at-all counts when there were any.
Every clause is conditional on its own count — an absent number prints as
absent, never as 0, because "0 asked" is a claim about a scan that never
happened. **And the newest bar names the names it is measured over**, because
it is the newest date among the ones that did NOT print: written as
"(newest seen …)" glued to the clause before it, it read correctly beside
"none with a bar for X" and contradicted itself beside "5 with a bar for X",
which is the shape a partly stale feed and every failure after a completed
scan produce.

**A run that dies AFTER its scan says what the scan found.** It scanned,
scored and broke in `publish()` — every count on the report — and was mailed
the sentences written for a run that never started: "there is no shortlist
below, and no scan was completed", "4% bursts found: not recorded", and an
empty-table cell reading "this is a quiet market, not a rejection" over twelve
bursts it had paid Claude for. The notice is rendered from the funnel the run
had already built, the band says the run failed after its scan, and the market
claim is made only by a run whose bursts were actually counted — which a
completed scan that broke before it built a funnel is not. That state keeps
the coverage line, because the universe cell now prints the label when the run
has one and the coverage when it does not, rather than reading whether the
session was being relabelled.

**And a run that published and then failed to deliver is a different email
from a run that never scanned.** The record is written before the send, so
exit 3 is a night that scanned, rendered, paid for every Claude call and wrote
both files — and its notice read "there is no shortlist below, and no scan was
completed", with the one rejection listed twice, once in the email stage's own
sentence and once as the exception that ended the run. The notice is that mail
sent again: the rows are in it, the headline says the record is published and
what failed was the delivery, and the exception is recorded once. The record
says what is known when it is written — *this run's own send failed* — rather
than "the shortlist was not delivered", which is an outcome still open at that
line and false in the record, on the page and in the next morning's band as
soon as the retry goes through. The
attachments are dropped, because a byte-identical resend of what a server just
refused has no reason to go differently, and each row says so where its chart
would be. The morning pass writes no record and can never claim one, but it
can still fail on the send, and its notice is the same retry.

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
A morning run on a holiday — Labor Day Monday at 8:30 AM ET — reads Friday's
evening record like any Monday morning and mails it clean, with nothing in it
saying the market is closed today, because nothing in this project knows that.
That is designed: a calendar approximate enough to be wrong would say more
than the record can support, and the evening cron on the holiday itself is
what finds no bar and says so.

**And when there is nothing to show, the cell asks whether the SCAN was cut
short — not whether anything went wrong.** Only a `scan`-stage problem makes
the list shorter than the session deserved; a clock disagreement, a chart that
would not render, a Claude fallback, an unreadable history and a delivery that
failed all leave the counts a complete reading. The cell asked "were there any
errors?", so every one of those printed "No shortlist. See the failures listed
above — this is not a statement about the market" three lines under a funnel
reading "4% bursts that session: 0", which *is* a statement about the market —
and under a band whose own sentence for those stages is "the scan below is
complete". One email, two answers, on one screen; the first mail this project
ever delivered was that shape, and so was the morning that would have followed
it. Both modes ask the stage now. An evening run with a complete scan says
what it found ("No 4% burst anywhere in the universe today…"), and a morning
one names the session and what that run found ("The 2026-09-04 run this
follows through on found no 4% burst to score", or "…scored no candidates"),
adding what that run scanned when it was not the checked-in file, since the
morning funnel names no universe. The failures sentence is what is left for
three states: a morning that read no published run at all — the state every
morning was in until `evening.yml`'s commit-back first succeeded on 6 Sep
2026, and the state a repo that has never published is in, since a fresh clone
of this one now reads the run that commit-back left — a snapshot whose burst
count cannot be read, which is not a run this pass can report either, and a run whose own scan was cut
short, where the counts are printed and then not read as the session. With no
red band to point at, the sentence does not point at one. The names that
stopped printing are on both emails now — `run.stopped_printing` is a fact
about `data/symbols.txt` **as that run read it**, so the morning scopes it to
the run and softens the instruction: this repo retired `FI`, `BK` and `EA` the
day after the record that names them, and the unscoped sentence would have
sent the next morning's reader to check three names the file no longer holds.

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

An evening dispatch whose session is already published re-presents it rather
than paying for the same answer twice, **whatever the clock says** and
whatever made the dispatch. The clicks are the lunchtime one, whose newest
completed session is yesterday's, and the one made after the 22:16 cron to
watch it work, whose newest completed session is the one that cron published
minutes earlier — but the rule is *whichever evening run gets there first*,
so a click made before 22:16 leaves that night's cron nothing to scan too.
The check sat inside the clock-disagreement branch above, and the mode and
the clock agree after the close — so the second click re-scanned the same
daily bars, paid for every Claude call a second time, mailed the same
shortlist again and replaced the published record with the re-scan, at exit 0
with nothing recorded. It is consulted before the scan now, so a
re-presentation asks the feed nothing and the run is reported and exits 2 the
same way. A rehearsal from the form's `dry_run` box is not exempt either, and
that is worth knowing before using one to try a change against the real feed:
unpinned, after the cron has published, it makes no request at all.

**It reads the basket as well as the session.** The documented `--tickers`
smoke test below publishes a real evening record of the day it ran on, and a
one-name smoke record is not that session published: the cron that follows
still scans the file, or the night would lose its scan, its record and its
mail to a run over a universe a fraction as wide. The reverse is not
symmetric — a published universe scan *is* an answer about a handful of names
typed on the command line, and re-scanning them would replace that night's
record, its universe label and its filled benchmark with the smoke test's —
so a `--tickers` run against a published night re-presents, and is told that,
rather than told the bars are the same bars.
Explicit scans also record their sorted symbol list in `run.universe.tickers`:
two baskets containing the same number of different symbols are different scans,
while reordering the same symbols keeps the published run. Older explicit records
without that list are preserved with an identity-unknown explanation, rather than
claiming the requested symbols were already scanned.
`SCAN_SESSION_DATE` is the one exemption, for the same reason it is exempt
from the clock check: a pinned session is a deliberate re-scan, and it is how
the 4 Sep record was republished. Pin a session **the record does not already
hold**, or put both files back afterwards with the `rm -f docs/ledger.json &&
git checkout -- docs/` below: `Ledger.add_run()` keys on the session and the
run type, so pinning a smoke test to the night the cron just published drops
that night's rows, its universe label and its filled benchmark for the smoke
test's, at exit 0 with nothing reported — and a measured horizon is never
re-measured, so that session's alternative is gone for good. What keeps a
`--tickers` run out of every benchmark is not the pin: it is that it has no
universe to offer, so `Ledger.fill_benchmarks()`, which matches runs on the
label the entry already carries, neither gives it one nor takes one from it.
And the mail it sends used to say
"Morning follow-through" in the subject, "re-presented before the open" in the
band and "at today's open" in the heading, three surfaces describing the 8:30
cron on a message a lunchtime click produced hours after that open. The pass
really is the follow-through; the dispatch is what the reader has to
recognise, so the subject names it and the two open sentences are replaced —
and its failure notice is rendered as the pass that built it, not as the
evening scan the click asked for. A morning dispatch made *after* the close
gets the other half: its subject is untouched (there was no dispatch of
another mode to name), and the heading and the band say it is being read after
today's close, where they used to promise an open the run's own band said had
already happened. A weekend dispatch is the fourth occasion and the newest: it
is told the market does not open today, because
`scanner.session_has_closed()` is false all weekend by design and the pass
therefore took the 8:30 cron's wording, "at today's open", on a Saturday, with
nothing degraded to qualify it — a morning mode and a weekend clock do not
disagree.

**The session before is read off the frames, so the day after a holiday is a
night.** A burst is one session's move against the session before it, and the
scan refuses a name whose bar before the session is not that session — a
full-day halt, or a bar the feed dropped, would otherwise print a two-day move
as the day's 4%. A bar that is *present but unreadable* — a NaN where its close
or volume belongs — is a hole too, and used to pass: the rule read the index
while `detect_setup()` drops exactly those bars before it measures, so the
session was measured against the bar two back and the two-session move was
published under the session's date with status ok. Both now read the same
frame (`_measurable()`).

"The session before" was weekend-only arithmetic, and on the day after every
weekday holiday the arithmetic names the holiday: every frame
lacked it, every name was refused as a hole, and the run published DEGRADED
with 0 bursts, a null floor and a record `evening.yml` would have committed as
the night's — reproduced end to end on Tuesday 8 Sep 2026, the day after Labor
Day and the first scheduled night. The scan reads the session before off the
night's frames now (`observed_previous_session()`). **One name that printed on
the arithmetic's date is the disproof, and it settles it**: every frame the
scan downloaded is searched first, the stale ones included, because a name
that stopped printing *on* that session still printed on it. Without that
clause a bare majority decided against evidence the scan already held — seven
names halted on Tuesday outvoted five that traded it, the five healthy names
became the holes and the seven broken ones were measured across theirs.
Only when nothing printed does the vote decide: when at least
`coverage_guard_min_symbols` (10) fresh frames vote and **more than half share
one business day earlier than the arithmetic's**, that date is the previous
session. Only the *fresh* frames vote — a stale frame's newest bar is not the
bar before this session, so it answers a question about an earlier week.
A majority can only move the answer back, and only onto a weekday, so no
phantom bar can manufacture a session: a Saturday later than the arithmetic
loses on the first clause, and the window of non-session dates *earlier* than
it that the day after a holiday opens loses on the second. A split vote moves
nothing; one name's own hole on the week of a closure is still a hole. No
holiday calendar, still: the frames are the evidence, and this is the same
evidence and the same shape of vote the forward returns read their sessions by
— with one deliberate difference, at a tie: `session_calendar()` admits a date
carried by exactly half its frames, because a session missing from half the
frames is still a session, while moving *this* answer back takes a strict
majority. Below the minimum — the documented `--tickers` smoke test on the day
after a holiday — the arithmetic stands, and the degraded sentence names both
conditions a closure needs and says which of them was not met, rather than
counting the universe as holes; when other names *did* print on that session
it says so and calls these holes. The stated cost: a genuine feed-wide dropped
business day, one no name in the universe printed on, never observed, is read
as a closure and measured across it.
The bar the detector measured must also be the session's: a session bar with
no readable close or volume used to make it measure the bar before and publish
the *previous* session's burst under the session's date with status ok, and
such a name is refused and counted with the ones that could not be measured.

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

**And the scorer is told it before it scores.** The ledger is read above the
chart and the model rather than after them, so `setup_day`, `seen_before`,
`last_seen`, `last_score` and `last_outcome` are in the metrics block Claude
is handed — day 2 of a two-night burst used to be scored as if the file had
never seen the name, on a strategy named after Day 1. `knowledge/strategy.md`
says how to weigh them. The nulls travel unchanged: a record that cannot
answer reaches the model as `setup_day: null` beside the reason word, under a
rulebook sentence saying in as many words that a null day is not day 1.
Reading it earlier does not make it fatal — an unreadable ledger still only
degrades the run, which still charts, scores and publishes.
The model treats this as recorded episode context, not proof of a fresh
breakout: day 1 may follow an older burst outside the five-weekday grouping
window, and missing scans limit the record. Unknown history alone earns
neither a freshness bonus nor a penalty; repeat context is checked against
the chart without double-counting the same move in consecutive up days.

## One-time setup

Push this repo to GitHub and add six repository secrets — these are exactly
what `.github/workflows/evening.yml` reads, and `.env.example` explains each:

`ANTHROPIC_API_KEY`, `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`,
`RESEND_API_KEY`, `RESEND_FROM`, `EMAIL_TO`

Two more things the first live day turned up, both settings rather than code:

- **GitHub Pages serves the `docs/` folder of `main`, and the folder is the
  trap.** Settings → Pages → Build and deployment → "Deploy from a branch" →
  branch `main`, folder `/docs`, Save. With the folder left at `/ (root)` the
  first build published the whole repository and rendered README as the site;
  the `docs/` build serves the dashboard and its checked-in assets. The first
  deploy takes a minute or two to reach the address. The site has been on since
  6 Sep 2026. `publish-dashboard.yml` requests subsequent builds explicitly:
  a commit-back made with Actions' built-in token does not itself trigger Pages.
- **Resend in test mode only delivers to the account's own address, and its
  check is an exact string match.** Until a domain is verified at
  resend.com/domains and `RESEND_FROM` is an address on it, Resend refuses any
  other recipient. Set `EMAIL_TO` to the address the Resend account is
  registered under, alone, in the spelling Resend uses: a capital letter drew
  the same refusal three runs running, so the send path now corrects case on
  the spot and the log says to re-save the secret that way, while a second
  recipient or a stale value is diagnosed in the log by count and domain. A
  refusal that does reach `docs/data.json` has the address it names masked to
  its domain; the Actions log keeps the whole sentence.

**The boundaries were first crossed from Actions on 6 Sep 2026, by dispatching
`evening.yml` (README's round-9 notes in CLAUDE.md say what each crossing
found). To rehearse them again from your own machine:**

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
commit-back push, which only Actions can run — and Actions has, since 6 Sep
2026; see "Does the history actually accumulate?" below.

Both pipeline workflows then fire on weekdays and can be triggered manually
from the Actions tab. `morning.yml` is passed only the three delivery secrets,
because the follow-through pass runs neither the scanner nor the scorer and
`preflight()` asks the mode which layers it will use before demanding a key.

> **Note:** the five files in `.github/workflows/` are `evening.yml`,
> `morning.yml`, `publish-dashboard.yml`, `secret-scan.yml` and `tests.yml`. The evening scan fires at
> 6:16 PM ET — 22:16 UTC under EDT, 23:16 UTC under EST — and the morning
> follow-through at 8:30 AM ET (12:30 / 13:30 UTC). Both crons of each pair are
> registered and a guard no-ops the one that does not match today's ET offset,
> because GitHub crons are UTC and do not follow US daylight saving.
> `evening.yml`'s crons are labelled backup-only for an external trigger you
> should not set up; the guard works standalone.
>
> **Every row in the Actions list says which run it is**, because four
> different things fire the evening workflow and every row used to read
> "Evening scan (6:16 PM ET)": `Evening cron 16 22 * * 1-5, the EDT slot`,
> `Evening cron 16 23 * * 1-5, the EST slot` — whichever of the two the guard
> no-ops still reports success, for a run that did nothing —
> `Evening rehearsal`, `Evening backfill 2026-09-04` and `Evening dispatch`.
> The morning workflow takes no inputs, so its rows are
> `Morning cron 30 12 * * 1-5, the EDT slot`,
> `Morning cron 30 13 * * 1-5, the EST slot` and `Morning dispatch`. A cron the label does not know renders as itself rather
> than borrowing the other slot's name.
>
> **And the run's own page carries the verdict**, not just a tick or a cross:
> the pipeline appends the email's subject line — the same string, byte for
> byte, including its DEGRADED or FAILED prefix and the session it really read
> — the exit code, and every problem the email's red band lists, to
> `$GITHUB_STEP_SUMMARY`. A run that could not mail (the preflight failure
> every scheduled run made until 6 Sep 2026, or a delivery refusal) says on
> its own page what the email would have said. Locally the variable is unset
> and nothing is written.
>
> `morning.yml` depends on `evening.yml` having committed `docs/` back — see
> "Does the history actually accumulate?" below. On a repo where that has never
> happened it finds the hand-authored fixture, refuses it by name and mails a
> degraded notice rather than a watchlist of invented tickers. That is no
> longer this repo's state, and a fork inherits the difference: its first
> morning run reads the last run **this** branch committed — a real scan, so
> nothing refuses it — and follows through on someone else's night until the
> fork's own evening run publishes one. Pin `SCAN_SESSION_DATE` and run an
> evening first if that matters.
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
# (if the session this would scan is already published, it re-presents it
#  and scans nothing -- with or without --tickers, and whatever the clock
#  says. Pin SCAN_SESSION_DATE below, to a session the record does not
#  already hold, to make it scan.)

# Smoke-test on a few tickers:
python -m src.pipeline evening --dry-run --tickers NVDA,PLTR,SMCI,CRWD

# Re-present the run above, the way the 8:30 AM job would. Scans nothing,
# reads docs/data.json, needs no Alpaca or Anthropic key. --tickers is
# refused here rather than ignored, because this mode does not scan:
python -m src.pipeline morning --dry-run

# Seed the history from a past session (its forward returns resolve at once):
SCAN_SESSION_DATE=2026-08-24 python -m src.pipeline evening --dry-run
# From GitHub: Actions -> "Evening scan" -> Run workflow, and fill the "session" box;
# tick "dry_run" to rehearse -- it mails nothing and commits nothing back.

# Offline logic tests (no network / API key needed):
pip install -r requirements-dev.txt
pytest tests/                   # 1439 tests, no network or API keys needed
```

An **evening** run that scans — `--dry-run` included, since `--dry-run` skips
only the email — rewrites `docs/data.json`, updates `docs/ledger.json` and
writes PNGs into `docs/charts/`. One that finds its session already published
(above) scans nothing and writes none of the three, not even a chart. A
four-ticker smoke test therefore replaces whatever `docs/data.json` held with
a four-ticker run — the run `evening.yml` last committed back, which here is
a real one, and the hand-authored fixture only in
a repo that has never published.
`docs/ledger.json` gains a run too — one row per named ticker, marked with the
universe it scanned (`runs[].universe` says `named on the command line`) so the
record can tell it from a real night, but a row all the same: the next evening
run on another session reads it as history, and `git add docs` would commit it.
Put both files back with

```bash
rm -f docs/ledger.json && git checkout -- docs/
```

— `git checkout -- docs/` on its own is enough here, because the first
commit-back tracked `docs/ledger.json` along with `docs/data.json`: checkout
puts both back. The `rm` is kept for a repo that has never published, where
the ledger really is untracked, checkout leaves it, and the first `git pull`
after a real commit-back then refuses to overwrite it. A **morning** run
writes nothing at all, so it cannot disturb either file: it re-presents
whatever `docs/data.json` holds, which here is the last run this branch
committed back. It refuses to present the fixture — which is what a repo that
has never published still holds, and what you would see there.

## The dashboard

`docs/index.html` is a static page served by GitHub Pages from `docs/`. It fetches
`docs/data.json` in the browser and renders it — no server, no build step, no
framework. The SpicyChicken visual system is vendored in `docs/design-system/`,
with its exact source commit and file hashes in `provenance.json`. `docs/stock.css`
arranges the branded cover, run summary, research panels and responsive pick cards;
the shared system supplies the original chick, themes, surfaces and reduced-motion
aware transitions. These design files are checked in directly and the pipeline does
not regenerate them. `stock-home.css` carries SpicyHome's map-and-notes visual
layout into the report. `signal-map.js` plots each scored candidate's recorded
daily gain and relative volume beside linked candidate notes. It reads the same
snapshot, preserves the ranking and score-source labels, and leaves candidates
with missing measurements in the list without inventing a point. It is a signal
plot, not a geographic or sector map. Empty runs stay empty. The existing complete
ranking, shortlist, evidence and history remain below it; selecting a point changes
only the presentation and makes no requests or stored changes.

**An evening run that scans writes that file at the end** (step 9,
`src/ledger.py`) — one that re-presents an already-published session leaves it
as the run that published it wrote it — together with `docs/ledger.json` and
the chart PNGs — which are **not** committed (`.gitignore` blocks `/docs/charts/`), so the published
page has no images and every chart slot explains that instead. Open the page
from a checkout that has just run the pipeline and the same slots fill in. A
chart is ~57 KB and a night renders up to 25 of them: committing them is about
360 MB a year of history that does not delta-compress and cannot be taken back
out, and one file per ticker with no session in it cannot prove which run drew
it anyway. `docs/data.json` is whatever the last run wrote, and on a fresh clone
of this repo that is the run `evening.yml` last committed back — a real run,
no banner. (Which session that is moves with every commit-back, so this
sentence does not name one; `run.date` in the file does.) In a repo that has
never published it is instead the hand-authored fixture the tree shipped with, a byte-for-byte copy of
`tests/fixtures/data.json`, which `tools/make_fixture.py` generates, and it says
so in its own `run.fixture: true`, which is what raises the "sample data" banner
at the top of the page. The first evening run `evening.yml` commits back
replaces it, `run.fixture` goes `false`, and the banner disappears; nothing in
CI expects the file to stay a fixture, because a guard that has to be defeated
to ship is worse than none. The canonical fixture stays at
`tests/fixtures/data.json`, where `tools/check_fixture_fresh.py` guards it
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

The snapshot-status panel separates the **recorded session** from the time the
browser last checked for an update. **Check for updates** reads the published
snapshot again; it does not dispatch a scan or claim that the recorded prices
are live. If the check fails, the last successfully loaded report stays visible
with an explicit failure message. A changed snapshot replaces the report and
invalidates any full-record request from the previous snapshot; an unchanged one
keeps the selected return basis and expanded details. Both snapshot and full-record
requests time out after 15 seconds, including a stalled response body, and offer
a retry. The **Scan activity** link opens the evening workflow's actual run history.
These controls need no credentials and do not change pipeline or email behavior.

### What the page answers, and what it refuses to answer

Until step 11 this page rendered one night. `docs/ledger.json` had been
accumulating every scored and gated candidate since step 9, and none of it
reached the only public surface this project has — so the question the whole
thing exists for, *does a higher score earn a higher forward return*, could not
be asked here at all.

It leads the historical evidence section below the signal explorer and above
the funnel, with four more views under it:

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
setups but the universe's move, over the names at or above that night's
liquidity floor, paired with each of them) and
`evidence.rules`, which says how many distinct sets of rules the record spans,
which keys differ between them, and how many runs predate the fingerprint
entirely: **a mean across runs is a mean over one strategy only while `sets`
is 1**, and a run carrying no fingerprint is not a run that agrees with this
one. `differ` names only the keys every set records, whose value moved; a key
some set does not carry at all is `unshared`, since a rule that did not exist
then and a rule that was merely not recorded then are the same silence and
neither is a number that changed — `evidence.horizons` (which sessions after the
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
and what followed — needs the whole record, which projects to about 15.51 MB raw
and **1.25 MB gzipped** after a full year. That is not a thing to spend on every
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
  dollars, `over` -- how many names the percentile was drawn from -- and
  `refused`), so a snapshot written before either existed is not described as
  having enforced it. `over` is the population the FLOOR was drawn from -- the
  names whose session bar carried a readable, positive dollar volume -- and
  not what the scan measured, which is `run.coverage.measured` and can differ
  from it in both directions. A null `floor` has three readings: `pctile <= 0`
  is the rule switched off whatever `over` says, `over: 0` under a live rule
  is a night no name's dollar volume could be ranked, and no `over` at all is
  a run from before the count existed. Both of the first two wrote the same
  null, and every surface printed one sentence -- "nothing traded" -- over a
  night the feed had answered in full. (The published contract read "a
  positive `over` under a null floor cannot happen" for a round; the rule
  switched off writes exactly that, and rule 6 can draw a floor on a night the
  scan measured nothing, because a name the detector raised on contributed its
  dollar volume before it raised.) The liquidity refusals were the one class
  the record did not hold until round 5: `apply_liquidity_gate()` logged them
  and dropped them, so on the documented four-name smoke test the thinnest
  name vanished and the funnel counted the other three as everything found.
- `run.coverage` is how much of the night was actually READ: `requested`,
  `with_bars` (answered with any bar), `fresh`, `measured`, `stale`, `gapped`,
  `no_bars`, `dropped` and `duplicate_bars`, plus the `session` and the
  `newest_seen` bar among the names that missed it. `measured` is the
  population a burst could have come from -- the names whose session bar the
  detector read and answered about -- so `with_bars - measured` is what could
  not be measured for the session, in the five ways `run_scan()` subtracts
  (behind it, holed on the session before it, unreadable, measured onto an
  earlier session, or one the detector raised on), and **`measured: 0` under a
  positive `with_bars` is a BLIND night**: the feed answered and not one
  answer could be read, which is not a quiet market and no surface may report
  it as one. `measured: 0` beside `with_bars: 0` is a scan nothing answered,
  which is what a dead run's notice carries and is a different sentence.
  `requested - with_bars` is the OTHER half of the same cut -- the names the
  feed answered with nothing, plus any dropped after their batch failed twice
  -- and it is not the burst filter either: a run with 20 asked, 18 answered
  and 18 measured exits 0, and its mail used to say "No 4% burst anywhere in
  the universe today". Every count is
  conditional on the scan having reached it -- a run that died earlier carries
  fewer of them, and absent is never 0 -- and the same block is what the
  failure notice renders, so a dead run and a published one describe their
  coverage in one shape. The email's funnel carries the cut when it bit, on
  the widest denominator the block has ("Measured for the session: 216 of 228
  asked, 216 of 227 that answered"), the page captions the first stage with
  it, the empty-table cell names the population it is talking about instead of
  the whole universe, and the morning prints the same line and the same clause
  for the run it follows, because that run's coverage is a fact about it
  exactly as its `bursts` is. The ledger entry keeps
  `measured` alone (`runs[].measured`): `docs/data.json` is rewritten every
  night and both readers of the number are LATER runs -- a streak, which may
  not claim "nothing preceded this setup" across a night nobody read, and the
  benchmark fill, which leaves a blind night pending rather than stamping its
  rung as measured under no floor.
- `run.stopped_printing` is a fact about the symbol FILE rather than the
  market: the names in it with no bar for more than 5 sessions -- a halt is
  a day or two, a delisting never comes back -- as `after_sessions`, an exact
  `count`, and `names[]` of `ticker`, `last` and `sessions_behind`, most-behind
  first, at most 10 named. A name the feed returned no bar for at all in the
  window the scan asked for -- one it does not know, or the old symbol of a
  rename once purged -- comes first, with `last` and `sessions_behind` null;
  below the fraction that degrades a run, such a name used to reach no
  surface, the log included. The email and the page print it; the ledger entry
  does not carry it. It is a fact about the file **as that run read it**, which
  is why the morning mail scopes the sentence to the run rather than repeating
  the evening's "check the list": acting on the line is what changes the file,
  and this repo retired all three names the first live scan found -- the list
  held 230 then and 228 since.
- `run.duplicate_bars` is how many bars that night's scan dropped as
  duplicates, across every symbol -- **the extra copies**, so a bar sent three
  times counts 2, which is what every line printing this number says. A
  duplicate here is a bar carrying **a timestamp the response had already
  sent**, because the index is all the de-dup can see: the same session sent
  under two different timestamps is a different shape, and this neither counts
  nor drops it (`detect_setup` then reads the two as one session and finds no
  gain, which is the way a same-timestamp repeat used to hide a burst --
  measured through the real downloader, and pinned by a test rather than
  answered with a session-level de-dup for a wire nobody has seen). The
  scanner sorts what came back with a STABLE sort and keeps the copy that
  arrived last, so a preliminary bar followed by a corrected one resolves to
  the corrected one whatever order the response came in -- and the frame that
  comes out cannot show it ever chose, which is why the count is published. It
  is a sentinel and not a rule: it degrades nothing, because no live duplicate
  has been seen yet and the count is what makes reading the first one
  possible. It reaches every surface `run.stopped_printing` reaches, and the
  record twice: the scan's log line, this run block, **the ledger entry** --
  `docs/data.json` is rewritten by the next run, so the entry is where the
  first live one has to survive to be read -- the failure notice's coverage
  sentence, one line under the funnel of both the evening and the morning
  mail, and the page's universe row, the last two in one shared sentence. The
  forward-returns fetch uses the same downloader and warns in the log rather
  than adding to this number, which counts the scan; so does
  `tools/live_check.py`, the third caller, on the OK line it prints for the
  live feed.
- `run.settled` is what THIS run's fill made knowable about picks EARLIER runs
  made: one entry per (scored row, horizon) whose measurement stopped being
  pending tonight, carrying the pick's `ticker`, its burst `session`, the
  `score` and `verdict` it was given then, the `horizon`, its return on both
  bases (`ret`, `ret_from_open`) and that session's universe benchmark on both
  (`universe`, `universe_from_open`). Every number in it restates a row the
  record already holds rather than being recomputed, so the block cannot
  disagree with `runs[]`. A horizon is filled once, so a pick appears under a
  horizon in exactly one run's block and never twice with two numbers — which
  is why the block is per `(row, horizon)` and not per row. **It is the picks
  alone**: a refusal has no score to report and belongs to the control,
  `evidence.refused`. Both mails print it as a table under the funnel — the
  evening its own, the morning the same block off the run it follows — and
  print NOTHING when the list is empty, because the first four nights of any
  record settle nothing and "no picks settled" is a line a reader learns to
  skip. An absent key is a run from before the block existed and is not a
  night on which the earlier picks returned zero. It is not in the ledger
  entry: every number in it is already in that file, and this block's one
  irreproducible fact — WHICH night measured a horizon — is what the mail
  needs and the record does not. The page does not print it either: the page
  fetches the whole ledger and shows every row's outcome on its own card,
  which is the thing an email cannot do.
- `context` is what was measured beside the burst and voted on by nothing:
  where the close sits against its own year (`pct_off_52w_high`,
  `pct_above_52w_low`), how the name ran into it (`perf_3mo_pct`,
  `perf_6mo_pct`) — each of those four over the bars that carry the field it
  reads, since two of them are one close over another and two are a high and
  a low, so a bar whose Volume alone the feed dropped no longer slides all
  four windows a session back — the two Bonde measurements (`consecutive_up_days`,
  `worst_base_day_pct`) and the burst bar's own geometry — `gap_pct` (the
  open against the previous close, off the same two closes as `gain_pct`:
  both are measured after the scan's own cleaning, so a bar with an
  unreadable volume is a session neither is measured against),
  `bar_range_pct` (high minus low over the close) and `range_expansion`
  (that width over the mean width of the last seven sessions before it whose
  range can be read — `N`'s own consolidation window, deliberately not a
  second one, holding the bars `N` holds, and averaged the way `N` averages
  it, so the ratio is
  `bar_range_pct` over the %/day the `N` line in the same row prints). It is
  on every burst row, scored or refused, and it survives into
  `docs/ledger.json` beside the forward returns, which is the only place the
  question "did the gapped bursts pay worse?" can ever be asked. Each is
  `null` — never `0` — where the bar could not supply it, and which one goes
  null depends on what is missing: the gap alone for no readable open or an
  open printed outside its own bar, which is not a price anybody paid; the
  width and the expansion for an envelope that cannot be read; the expansion
  alone when no readable session before the burst had any width to expand
  against; and all three when the LAST bar of the frame handed over is missing
  a field the checklist needs, which is the rule and no longer a state this
  block reaches — the metrics are anchored on the bar the checklist grades, so
  these three step back onto it with `H` rather than describing the session
  after. None of them is in `run.rules`: no rule reads
  them, and a measurement that refuses nothing does not make a run a
  different screener. The rulebook the model reads DOES change when their
  instructions do, and that is in the fingerprint through `score.prompt`.
  The three burst-bar numbers are model- and record-only by decision: the
  page shows `consecutive_up_days` and `worst_base_day_pct` on a candidate
  card and no view reads the other three, which is what the record is for
  when there are enough rows to ask.
  Until round 11 the block held no measurement of the burst bar itself, and
  two bullets of `knowledge/strategy.md` asked the model to judge a bar it
  was sent no number for: a +7.5% gap into a bar 0.9% wide and a flat open
  with a 9.4% range, on the same close, gain, volume and `H`, produced
  byte-identical requests.
- Every candidate carries `provenance.source` (`"claude"` or `"fallback"`), and
  `provenance.chart_seen` is true only when the model actually received the chart.
- `chart` is a path relative to `docs/`, or `null` with a `chart_error` saying why.
- Every burst carries `streak` — `day`, `unknown_reason`, `first_seen`,
  `last_seen`, `last_score`, `last_verdict`, `last_outcome`, `seen_before`,
  `history_from`, `history_sessions`.
  `day` is 1 exactly when `first_seen` is the burst's own session, and
  `last_seen` is `null` exactly when `seen_before` is 0. **A null `day` is not
  day 1**: it means the record cannot say, and `unknown_reason` says which of
  `no_history`, `history_undated`, `history_unreadable`,
  `window_not_covered` and `blind_session` left it null. The last is the only
  one that is not about how far back the record reaches: it reaches, and one
  of the sessions inside the window measured no name at all (`runs[].measured`
  0), so an earlier burst would have been invisible to it -- and unlike
  `window_not_covered`, waiting for the record to fill up never resolves it.
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
- `forward_returns` are `null` until those sessions have happened — with
  three exceptions no session can end, which the page names rather than
  calling them pending: a run that scored nothing has no rows for a later run
  to fill; a run every one of whose scored rows repeats a setup counted
  earlier has no setup of its own to average (`rows == scored` with `n == 0`,
  and a lead only ever moves earlier); and a run past the fill window is one
  `runs[].fills_closed` marks true, after which nothing is re-requested for
  it and a horizon still `null` there is `null` for good. `fills_closed` is
  an answer about the record as it stands tonight rather than a fact about
  the run, so it is in `data.json`'s view and not in the ledger.

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
is how many setups the run contributed at any horizon and `forward_returns.rows`
is what those setups were collapsed from. The page prints both, and calls
neither of them "names".

**The weight is per horizon**, not per run: `forward_returns.n1`, `n3` and `n5`
are the setups behind `d1`, `d3` and `d5` separately, on both bases, and the
dashboard multiplies each horizon's mean by its own. A frame with a hole two
sessions after the burst measures `d1` and nothing after it — the fill refuses
a horizon it cannot reach across every session on the way — so that setup is in
`n` and out of `n5`, and one `n` for three horizons weighted a +5d mean by
setups that have no +5d. `nH` is `0` exactly when `dH` is `null`, and they are
not ordered `n1 >= n3 >= n5`: a bar that is there and prints a non-finite close
leaves its own horizon null with a later one measured. A run entry written
before these counts carries only `n`, which is what that file claims about its
own weights, and the page uses it there.

- `d1`, `d3`, `d5` are the percentage change from the burst-day close to the
  close 1, 3 and 5 **sessions** later — sessions read off the calendar the
  run's frames agree on (the bullet below says how), not calendar days and
  not positions in one frame, so neither a holiday nor a hole can quietly
  shift a horizon. This bullet said "positions in the frame" for a round
  after round 9 made that false.
- `runs[].rules` is **what this screener was when that run was made**: every
  number its rules turned on — the scan's strategy thresholds, every threshold
  and window the checklist names, the vetoes in force and the gate — and, since
  round 11, what produced the SCORE as well as what produced the burst:
  `score.prompt` is a digest of `knowledge/strategy.md`, the system prompt
  itself, and `score.record_keys` names the record block the scoring request
  carries. Every mean this page keys on a score averages the scorer as surely
  as the gate, and the commit that rewrote the rulebook and added six payload
  keys left this fingerprint byte-identical until those two arrived. It is
  derived rather than listed — `src.pipeline.rules_fingerprint()` walks what
  `src.lynch` names, its `WINDOWS`, the `ScanConfig` fields that config itself
  marks as strategy, and `src.scorer`'s own `RECORD_KEYS` and knowledge file —
  so a threshold added later is recorded the moment it is named.
  The trap it exists to avoid is a fingerprint that misses a number and so
  reports "same rules" across a change that altered them, which is worse than
  no fingerprint; the checklist's windows were bare literals until round 8
  named six of them, round 11 the seventh — `C`'s volume norm, whose 50
  could be changed to 30 with this fingerprint byte-identical — and the same
  round the four inside `extra_context()`, the 52-week, six-month and
  three-month windows the model's relative-strength numbers are measured over,
  which a guard scoped to `evaluate_2lynch` alone could not see. A number left
  as a literal anywhere in `src.lynch` is refused by a test that reads every
  one of its functions' own numeric constants, and a threshold spelled out at
  its own value by a second test asserting each named threshold is read. `MAX_TO_SCORE`, `TOP_N`, the feed, the model and
  the universe are deliberately not in it: each is already a fact of the run
  block. What it still cannot see is a measurement key added to the metrics
  payload with the rulebook left untouched — the rulebook has to explain a key
  for the model to use it, and a docs test holds it to that for the record
  keys, but that is a convention rather than a proof. A run from before the fingerprint
  carries no `rules` key at all — absent, never null, because the contract
  distinguishes "this run had none" from a shape no writer produces.
- `runs[].benchmark` is the **universe's equal-weight return from that
  session** — `d1`, `d3`, `d5` from the close and `from_open` from the next
  open, with `n1`/`n3`/`n5` the number of symbols behind each — filled by a
  later run from the frames its own scan already read, at no extra request,
  over every name whose frame carries the session **at or above the run's own
  liquidity floor**: rule 6's bar that night, kept in `run.liquidity.floor`, so
  the names the rule says cannot be bought at those prints are out of the
  alternative the way `evidence.illiquid` is out of the control. Before that
  the rung averaged every name that traded, the refused ones included — 30% of
  them by construction, since the floor IS the 30th percentile of the
  session's dollar volume. `benchmark.liquidity_floor` is the floor applied
  (null for a run recorded without one, when every name that traded counts)
  and `benchmark.below_floor` how many names it left out. The frames are
  handed over before the scan's stale and gap rules, which are about tonight's
  session, so a name halted tonight still benchmarks the session it traded.
  `evidence.universe` pairs every scored setup with its own session's
  benchmark, so its outcomes are the alternative "buy anything in the universe
  that day" over the same sessions in the same proportions as the picks, and
  `evidence.universe.floored` / `unfloored` say how many measured pairings
  applied a floor and how many were measured with none — recorded before the
  floor reached the benchmark, or on a night rule 6 was off, which the block
  cannot tell apart, so every surface names both. It is a curated large-cap list as
  it stands today, so the comparison carries survivorship bias in the
  benchmark's favour, and the page's rung says so.
- A horizon is the bar of the session 1, 3 or 5 sessions after the burst, the
  sessions read **across every frame the run fetched** (`session_calendar()`)
  rather than counted along one frame's bars, and measured only while the
  frame carries every session from the burst to it: a bar the feed dropped,
  or a full-day halt, leaves that horizon and every later one null on that
  row instead of sliding them onto the next bar the frame has. Reproduced
  before it was fixed: with the 27 Aug bar missing, `d3` printed the 28 Aug
  close and `as_of` dated it a session late. A date is a session when at
  least half of the frames spanning it carry a bar on it, so one frame's hole
  removes nothing and one frame's phantom bar adds nothing -- and a phantom a
  few frames voted in ends the measurement for the frames that lack it, the
  same way a hole does, rather than sliding their later horizons. Fewer than
  two frames is no calendar: the documented `--tickers BURST` smoke test
  fetches one frame, and alone a frame is walked from the burst and stops at
  the first step that is not the next business day, since it cannot tell its
  own hole from a holiday; the next universe scan, with a calendar, measures
  what that left open. The open basis's entry must also lie within its own
  bar's low and high, the standard the checklist holds a close to; an open
  outside its range, or on a bar whose high or low cannot be read, is null on
  that row, and the close basis is untouched.
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
  answer for a delisting -- and so is a row whose horizon bar the feed never
  carried, or whose entry open sat outside its own bar: that horizon, or the
  open basis, stays null, and the row is asked for again on each of those
  ten runs in case a later fetch carries what the last one did not.
- Filling costs one extra bars request per 100 pending names, on the same free
  feed and through the same `_download_batch` the scan uses. If it fails, the
  run is marked **degraded** rather than quietly stopping to accumulate.

**Seeding a history without waiting a year.** A run pinned to an old session
resolves its own outcomes, because everything after that burst has already
happened:

```bash
SCAN_SESSION_DATE=2026-08-24 python -m src.pipeline evening --dry-run
```

A pin on the session after a holiday works the same way, because the session
before it is read off the frames and not off a calendar (see "The session
before is read off the frames" above); a pin on the holiday itself still finds
no bar carrying it and stops with `StaleDataError`, by design.

From GitHub, the same backfill is the evening workflow's **Run workflow**
button with the `session` box filled: the run is exempt from the clock check,
replaces that session's entry in the record if one exists, mails, and commits
back like any night. The same form has a `dry_run` box: ticked, the run still
scans, scores and writes its record — into the run's artifact, named
`evening-dryrun-<id>` so the backup cron does not count it as the night's run
— but mails nothing and commits nothing back, which is what makes it safe to
click at lunch, and how a request whose window reaches past the clock was
tried before the first scheduled evening asked for one.

A backfill is also how the dashboard's score-against-outcome bands gain
resolved points before a week has passed: on a normal evening run tonight's
candidates are pending by construction, and it is the NEXT runs that fill their
horizons in. The bands themselves need no backfill and no change to the page —
`evidence()` computes `by_score` at write time over the first SCORED
appearance of every setup in `docs/ledger.json` — resolved or not, so a
pending setup is counted in its band with an n of zero — and the bursts the
gate refused are the control beside those bands, never in them. The page draws
what the file carries, fetching `ledger.json` itself only for the per-name
view. This paragraph told a reader the opposite for two rounds — that a backfill was the only way a point could ever appear,
and that plotting outcomes across runs would take a change to the page nobody
had made. Step 11 was that change, and the guard on this sentence reads both
halves off the code rather than trusting the next reader to notice.

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

**A committed run and an updated website are separate boundaries.** GitHub's
[built-in token does not trigger Pages builds when it pushes a commit](https://docs.github.com/en/actions/concepts/security/github_token).
`publish-dashboard.yml` therefore starts when the evening workflow completes on
`main`, including a failed job that already persisted an exit-2/3 record, and
when a dashboard change is pushed to `main`. It checks out current `main` and
uses the built-in token's `pages: write` permission to
[request the branch-based Pages build](https://docs.github.com/en/rest/pages/pages#request-a-github-pages-build).
It never downloads the scan's artifacts, so a rehearsal's unpublished record
cannot become the public dashboard. A failed scan may refresh the last committed
record; it cannot manufacture a new one. Cancelled runs and other branches do
not trigger publication.

The publication job then fetches public `index.html`, `data.json` and
`ledger.json` without credentials, bypasses stale cache entries, and compares
their bytes with the checkout. It retries for up to eight minutes and fails
visibly if any file remains stale or unreachable. The record is still safe in
`main` even when delivery to Pages fails. To retry just this boundary, run
**Publish committed dashboard** from Actions on `main`: it scans nothing, sends
no email and makes no paid API calls. The existing Pages setting stays
**Deploy from a branch → main → /docs**; this workflow checks it and does not
change hosting settings.

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
are still red. Only the record is rescued — and the mail that goes out on that
path says so, rather than reporting a scan that never happened (see "The two
runs").

That retry only started existing in this round. `git pull --rebase` sat bare in
the loop, and under Actions' `bash -e` a failing pull ends the step — so the
first rejected push aborted it and iterations 2 and 3 never ran. It is `if !
git pull --rebase ...` now, with a conflicting rebase aborted and named rather
than left half-applied. Traced with `bash -ex` against a stub `git`, which is
how the `git add` bug below was found too.

**It has run, and this paragraph said for ten rounds that it never had.**
The first time was 6 Sep 2026 — Actions run 34014332161, commit `f0780c7`,
message `run 2026-09-04` — and two more landed the same day, `932ec58` and
`369c695`; `git log --author=spicystock` is the list, and a docs test reads it
back against these sentences, on any checkout that carries the history (CI
asks for all of it, for exactly this reason).

What was true when
this was written, and stayed true for ten rounds, is that nothing had reached
the add, the commit or the push: `evening.yml` had fired six times, every one
of them scheduled — three no-ops from the DST guard and three that died in
preflight for want of secrets — and a failed pipeline step skips the persist
step entirely. An earlier version of the same paragraph said instead that
"every run before it aborted at the `git add`", which described something that
had never happened once: the bug was real in the code and was fixed before that
code was ever the tip of `main`, and the nightly failure it supposedly caused
was invented. **One half of the step is still only traced against a stub**: no
push has been rejected yet, so the rebase-and-retry loop below has never run for
real.

**A dispatch that gets past preflight does not always leave a commit**, and
the same day showed it: run 34018706843 re-presented the already-published
4 Sep session, mailed it and exited 2, and the persist step ran, found `docs/`
byte-identical to what was already on the branch, and exited 0 at
`git diff --staged --quiet` with nothing to commit. The sentence this replaces
made that claim of all of them, which is the same universal shape as the "it
has never executed" sentence before THAT, and it was false seventeen hours
before it was written. A docs test reads that short-circuit out of the
workflow and refuses the claim while the step still has it.

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
session a run tonight would scan, from **this branch**. Even that is not enough:
an artifact survives a rejected commit-back push, so the freshly checked-out
`docs/data.json` must also record a real evening scan of the session over the
checked-in universe. A rehearsal branch's artifact, an unpublished record, a
fixture or a `--tickers` smoke snapshot cannot suppress the production cron.
If either receipt is missing, the pipeline runs; its own duplicate-session
guard still avoids scoring a universe run that the record already holds.
Traced through the actual guard shell and its `jq` filters in
`tests/test_docs_are_true.py` and `tests/test_workflow_guard.py`.


### Checking it

```bash
node tools/dashboard_smoke.mjs
```

Opens the real page in headless Chromium and asserts what it promises. Offline by
construction: `docs/` and its exact design-system snapshot are served locally,
and external requests are blocked. Needs playwright's chromium; it is not a repo
dependency, and the script exits 0 with a note if chromium is missing.

**Three data sources, one page.** It runs 255 checks, and which file each one
reads is the point:

- **`tests/fixtures/data.json`** — the canonical one-night fixture, served
  under `/f/fixture/`. Most of the checks live here, because they know the
  fixture's contents: 25 scored and 5 shown, a fallback that outranks a real
  score, chart paths that 404, a non-empty gated list, the streak states one
  night can hold at once. 44 mutated copies of it are served
  under `/v/<name>/` for the states one night cannot hold at once, beside one
  more name, `nodata`, that serves no document at all. This said six, then
  eight, while `VARIANTS` in the smoke test grew past both, so the script now
  checks that number the way it checks its own count of checks.
- **`tests/fixtures/history/`** — thirty consecutive runs written by the real
  pipeline (`tools/make_history.py`, see `tests/fixtures/README.md`): forward
  returns filled in by later runs, a night the scorer was down, a chart that
  would not render, repeats on consecutive sessions, a session that scored
  nothing at all and one whose every scored name was a repeat of a setup
  counted earlier — neither has three horizon cells any later run can fill,
  and both read "pending" from the day the runs table existed until round 10
  — and the last week still pending. Every expectation is computed from the
  file the page is reading.
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

The separate recovery check requires Chromium and fails if the browser is
unavailable; it never reports a skipped audit as a pass:

```bash
node tools/dashboard_recovery_smoke.mjs
```

It opens the same dashboard against failed requests, a stalled JSON body,
malformed snapshots, and a ledger response arriving after the snapshot changed.
It also checks retained data, retry controls, unchanged-refresh state, phone,
tablet and desktop layouts in both themes, and keyboard focus. All data is local
test fixtures. It dispatches no scan and calls no market or email service.

## Tuning

- Scan universe: `data/symbols.txt` — a hand-curated starter list, not the whole market
- Thresholds (price floor, gain %, relative-volume floor and its lookback, the
  dollar-volume percentile gate), the data `feed`, and a `session_date`
  override: `ScanConfig` in `src/scanner.py`. There is no share-volume floor;
  step 4 deleted it, and this bullet named the deleted knob and none of the
  three that replaced it
- 2LYNCH pass criteria: `src/lynch.py` — which BARS a MEASUREMENT counts is
  decided by the fields that measurement reads and by nothing else. Per
  measurement, not per check, because two checks are on both sides of the
  split: the closes (`2`, `L`, `Y`, `C`'s prior-day move, the up-days veto and
  the base breakdown) count every bar carrying a close, the ranges (`N`, and
  `C`'s own width) count every bar carrying a high, a low and a close, and all
  five fields are needed only to BE the bar graded — the burst `H` judges, and
  the prior day `C` judges, which is the session before it in the closes and
  not "whatever bar the prune left". All of it read one five-field frame until
  round 11; that arrangement merged the two sessions either side of every
  hole, which was reproduced on check 2 reporting two prior 4% bursts that
  never happened. The thresholds a measurement is
  compared against are module constants, and `WINDOWS` holds how much history
  each check reads, plus the four windows `extra_context()` measures the
  model's relative-strength numbers over. Both kinds are in the rules
  fingerprint, and `RULES_REVISION` is there for the change neither kind can
  express — which bars a check counts, which bar it is anchored on — bumped by
  hand in the same commit as such a change, since a walk of numbers cannot see
  one. A number left as a literal in ANY of that module's functions is
  not in the fingerprint, and a threshold spelled out at its own value is a
  third state that
  looks like neither — two tests refuse them, one reading every function's
  numeric constants and one asserting every named threshold is read by the
  module's own code (`2.0` for `MAX_D1_MOVE` passed the first and not the
  second, because `2.0 == 2`)
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

- Market data: free (Alpaca). The scan asks for `sip` rather than taking the
  plan default, so it reads consolidated volume instead of IEX's single-venue
  slice, and ends the request window no later than sixteen minutes behind the
  clock, which is what a plan without a real-time subscription needs for SIP
  (an older session's window ends earlier on its own and is untouched) — see
  `.env.example`. Both halves are observed, not documented: the feed on the
  first run past preflight, and the hold-back on a rehearsal from the form's
  `dry_run` box, session pinned to a Sunday, whose window reached past the
  clock and was served every symbol's bars through the Friday before. It
  asked for `delayed_sip` for nine rounds, and the first
  run past preflight (6 Sep 2026) showed the bars endpoint refuses that name
  outright; a feed the endpoint or the plan refuses aborts the run with a
  named error on the first batch rather than returning an empty shortlist,
  and `SCAN_FEED=iex` is the fallback. A 228-symbol scan is
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
- Claude: ≤25 scoring calls/run with one chart image each — **about $0.17 a
  run, so roughly $42 a year** at 252 sessions, and only on the evening run.
  This said "a few cents/day", which is out by about 5x. Measured rather than
  guessed: a real `render_chart()` PNG is 869x622, which is 721 image tokens by
  Anthropic's documented (w x h) / 750 rule; `knowledge/strategy.md` is ~3,120
  tokens of system prompt and the metrics block ~460, so ~4,300 input tokens
  and ~120 out per call, at claude-sonnet-4-6's $3/$15 per Mtok. The text
  halves are chars/4 estimates — `count_tokens` needs a network call this
  sandbox cannot make — so treat the figure as ±30%, which does not rescue "a
  few cents".

  **The system prompt is 73% of every request and is byte-identical on all 25
  calls**, so it is sent with `cache_control` and read from cache after the
  first. A cache write costs 1.25x and a read 0.1x — so the first call pays
  0.25x more than it would have and every call after saves 0.9x, which makes
  break-even the second call (1.28 calls) and a full night 54% cheaper: the
  $0.37 an uncached night would cost against the $0.17 above. (This said 1.4
  calls, 43% and $0.13: 1.4 is 1.25 over 0.9, which charges the whole write
  against the reads as if the first call were otherwise free, and the two
  money figures were rounded from different token counts. A test now does the
  paragraph's arithmetic from the numbers it states.) It needs no configuration: the
  default 5-minute window is the cheap one, and every read resets it, so a
  run's sequential calls hold the entry. `score_all()` logs what the cache
  actually did, because the saving is otherwise invisible from inside the run.

  The cap is what keeps this flat: it does NOT grow when the universe widens,
  because MAX_TO_SCORE bounds the calls and not the scan.

  Scoring uses a 5-second connection timeout and 30-second read/write/pool
  timeouts. The SDK's hidden retries are disabled; the application makes at
  most two attempts per candidate before recording its existing, clearly
  marked checklist fallback. This keeps a silent scoring outage from spending
  ten minutes per read, six requests per candidate, until the 55-minute
  workflow kills the run before publication. These are network inactivity
  limits, not a claim that every complete response takes at most 30 seconds.
  The morning follow-through makes no model call and no data request at all.
  Alpaca requests use a client-scoped 5-second connection and 30-second read
  inactivity timeout, including pagination and forward-return fills. The SDK's
  rate-limit retry and the scanner's existing batch retry are unchanged. These
  limits prevent a silent socket from waiting indefinitely; they do not impose
  a total deadline on a response that keeps delivering bytes.
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
  accumulate?" above for how it survives a CI container — and for the one half
  of that step nothing has exercised yet.
- Output is screening for human review, not trading advice.

For local design review, run `npm run dev` (Node only, no dependencies) and open the preview address it serves. The production pages remain static.
