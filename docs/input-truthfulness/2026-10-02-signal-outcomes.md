# The signal-outcome study: every archived burst, ticketed and walked

**What it answers.** No real night since 11 September 2026 has published a
ticket, because every one was RED, so the public scorecard has never settled a
plan. The records those nights wrote still hold every burst the scan found, its
checklist grade, and -- from 16 September -- the later bars of every public
signal. `tools/signal_outcomes.py` asks the narrower question those records can
answer: IF the ticket the rules write for a burst had been placed on each of
those nights, with the regime gate, the slot cap and the reader removed, what
would the fill rule and the five-session walk have done? It is the first R the
strategy's mechanics have ever had on real bars, and it is a counterfactual.

**The spec came first.** [`2026-10-02-signal-outcomes-spec.json`](2026-10-02-signal-outcomes-spec.json)
(SHA-256 `d93ad856b69a…`) was committed in `70dba340` before the study ran. It
names the 17 publication commits and their record blobs, the population, the
strata, the ticket, the bars, the walk, the estimands, the bootstrap and the
freeze. Every signal in it is **exploratory**: its next closes were public
before the spec was written, and nothing below may be read as a confirmed
prediction. Signals published after 1 October are confirmatory, and none has
matured yet.

## What was read

| | |
| --- | --- |
| Publications | 17 real records, 15 first-of-session (11 and 21 September were each published twice; the second is a revision and contributes bars only) |
| Bars | 53,452 over 2,053 symbols, from the observation histories, the latest observations and the candidate series; 2 revisions, both a day's low re-priced in a later publication (USLM 28 Sep, S 30 Sep) |
| Rows | 6,064 burst rows: 818 `admitted` (A+ or A, no veto), 1,480 B, 1,045 C, 475 skip, 2,246 vetoed |
| Nights | 14 with a settled ticket (11–30 September); 1 October's 579 tickets are pending their first session |
| Account | each record's own: $10,000, 0.5% risk, 25% cap, 4 slots; sized at the GREEN multiplier |

## What it found

Every stratum lost. The admitted stratum lost least.

| Stratum | Rows | Settled | Wins / losses / even | Mean R | Median R | Nights | Mean of night means, 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| **admitted** (A+/A, no veto) | 818 | 202 | 37 / 159 / 6 | **−0.235** | −0.47 | 14 | −0.291 [−0.486, −0.109] |
| B | 1,480 | 380 | 59 / 319 / 2 | −0.445 | −0.74 | 14 | −0.442 [−0.568, −0.330] |
| C | 1,045 | 263 | 45 / 213 / 5 | −0.368 | −0.79 | 14 | −0.419 [−0.552, −0.296] |
| skip | 475 | 92 | 14 / 78 / 0 | −0.386 | −1.00 | 12 | −0.408 [−0.688, −0.088] |
| vetoed | 2,246 | 541 | 90 / 445 / 6 | −0.425 | −0.70 | 14 | −0.477 [−0.658, −0.298] |
| all | 6,064 | 1,478 | 245 / 1,214 / 19 | −0.392 | −0.72 | 14 | −0.413 [−0.559, −0.280] |

The admitted stratum's buckets: 202 settled (183 stopped, 19 exited on the
rules), 17 open, 149 pending, **234 uncertain**, 94 not filled, 7 unmeasured,
62 no ticket (29 the account could not size to a whole share, 33 withheld at
the stop line), 53 basis mismatches. Its settled R by decile: −1.00, −1.00,
−0.87, −0.63, −0.47, −0.37, −0.24, 0.00, +1.07 -- seven of ten tickets lost,
and the losses were full-stop losses more often than not. Costs make it worse:
5 bps a side −0.276, 20 bps −0.400. The uncertain bound does not change the
sign: had every uncertain day filled at its trigger, the pooled mean would be
−0.332. Within the admitted stratum, the five settled A+ tickets all lost
(mean −0.42); dollar-only signals (175 settled) ran −0.204 with 32 wins, 4%
bursts (11) −0.116, signals on both scans (16) −0.651. The night means swing
from +0.42 (11 September, nine settled) to −1.00 (30 September, two).

The reader-accepted stratum -- the live policy's own admissions -- holds one
row, DAC on 1 October, pending. No confirmatory signal exists yet.

## What it means, and what it does not

1. **On these fourteen nights the gate was right, by its own tickets.** The
   regime said stand aside every night, and the tickets it refused would have
   lost in every stratum, A+ and A included. This is the first real-bar
   evidence that the RED refusal had value on the nights it was applied. It
   is not evidence that the gate is right in general: it has never said
   anything but RED in the record.
2. **The mechanical grade ordered the strata the right way, weakly.** Admitted
   lost least (−0.24), vetoed and B most (−0.43, −0.45); the intervals overlap,
   and no stratum is positive. On RED nights the checklist's grade did not find
   a group that made money. Whether it does on GREEN or YELLOW nights is
   unknown: no such night exists in the record.
3. **A third of the tickets are unknowable from daily bars.** 1,828 of 6,064
   rows are uncertain (759 trigger crossed after the open, 557 a fill-day low
   under the stop, 439 an open over the limit that traded back, 73 an open
   under the skip line that recovered). The public scorecard will carry the
   same share. The bound reported beside each stratum is the only thing this
   study can say about them.
4. **619 rows were set aside, not scored.** Every one is an 11 or 14 September
   signal whose own session's bar is in no publication: the observation
   histories begin on 16 September and a repeated ticker's window starts at its
   newer signal, so those rows' later bars cannot be tied to the signal's own
   close. The study refuses to walk them rather than assume the basis.
5. **It is a counterfactual, exploratory, dependent, three-week sample.** The
   reader -- which has accepted one of 183 usable judgements -- is not run, so
   these are tickets the live policy would mostly never have written. The 202
   admitted outcomes sit on 14 nights of one falling market, and tickets on one
   night move together, which is why the interval is over nights. Every next
   close was public before the spec. Nothing here is an edge claim, nothing
   changes a rule, and nothing it prints is actionable: every ticket is in the
   past.

## How it was run

- `tools/signal_outcomes.py --spec docs/input-truthfulness/2026-10-02-signal-outcomes-spec.json`
  at `70dba340`, Python 3.12, pandas 2.2.3, in this sandbox; no provider, model
  or network call. Exit 0.
- The results: [`summary.txt`](2026-10-02-signal-outcomes-evidence/summary.txt)
  verbatim, and every row with its ticket, bucket, events and R in
  [`signal-outcomes.json.gz`](2026-10-02-signal-outcomes-evidence/signal-outcomes.json.gz)
  (the uncompressed file's SHA-256 is recorded in the checkpoint). The records
  are public, so the tickers are too.
- Thirteen tests over synthetic publications with hand-computed R
  (`tests/test_signal_outcomes.py`); eight in-memory mutants all killed with
  the unmutated controls green: the gate not removed, the oldest publication
  winning a bar, a re-publication adding signals, costs charged on one side,
  uncertain tickets pooled into the result, the basis unchecked, vetoes
  ignored, the freeze ignored.

## Next

The study re-runs unchanged as nights mature: every publication after
1 October adds confirmatory signals, and the first ones settle five sessions
after they are published. The code and the spec stay frozen; a change to
either is a new spec. The owner's run of `tools/historical_backtest.py` over
the run-6 archive is the complementary reading: the portfolio-capped decision
over a year of bars, including the YELLOW stretch of August 2026 that no
public record carries as signals.

## Addendum, 6 October 2026

The [re-read over nineteen publications](2026-10-06-signal-outcomes-confirmatory.md)
found a bias this report did not name: a night read before its tickets' fifth
session leans toward losses, because a stop settles on its first bad day and a
winner at its exit or its horizon. The 25 to 30 September nights above had not
reached their fifth session when this was written; the 29 September night read
−0.425R over 27 settled here and −0.038R over 39 four sessions later. Every
stratum is still negative at the re-read, and the admitted stratum still loses
least; the night-level numbers above are the ones to re-read as nights complete.
