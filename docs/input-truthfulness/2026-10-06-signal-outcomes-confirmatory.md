# The signal-outcome study over nineteen publications: the confirmatory phase begins

**What was run.** The frozen study, `tools/signal_outcomes.py` as PR #100
merged it (blob `39d4f25a…`, unchanged on `main` at `788aa092`), re-run on
6 October 2026 in the sandbox over nineteen publications: the seventeen the
frozen [spec](2026-10-02-signal-outcomes-spec.json) names and the two published
since -- run 2026-10-02 (`58e0f384`, record blob `bb2edad5…`) and run
2026-10-05 (`178956b4`, blob `1064e69b…`). The spec it read,
[`2026-10-06-signal-outcomes-spec-extended.json`](2026-10-06-signal-outcomes-spec-extended.json)
(SHA-256 `688d552fc9dd…`), is the frozen file (SHA-256 `d93ad856b69a…`) with
the two entries appended in its own layout: a byte-level `diff` shows the
comma that joins them and the two added lines and nothing else, and that diff
is retained as
[`spec-diff.txt`](2026-10-06-signal-outcomes-confirmatory-evidence/spec-diff.txt).
Every rule, threshold, estimand and the freeze date are therefore the frozen
ones, and the frozen file is untouched. Python 3.12.3, pandas 2.2.3, exit 0,
10 seconds of wall time, no provider, model or network call; the command,
interpreter, exit code and timing are in
[`run-record.txt`](2026-10-06-signal-outcomes-confirmatory-evidence/run-record.txt). The
summary is
[verbatim](2026-10-06-signal-outcomes-confirmatory-evidence/summary.txt) and
every row is in
[`signal-outcomes.json.gz`](2026-10-06-signal-outcomes-confirmatory-evidence/signal-outcomes.json.gz)
(uncompressed SHA-256 `7255bac73198…`).

Both new nights were RED (10-session ratios 0.91 and 0.97) with no ticket, so
their signals enter as counterfactual tickets like every night before them,
and as **confirmatory** ones: their sessions follow the freeze date of
1 October. The two publications also reach back: their bars resolved fifteen
11 and 14 September rows the first run had set aside (6 settled, 4 not filled,
4 uncertain, and 1 that had been unmeasured) and moved 26 more from
`unmeasured` to `basis_mismatch`, so the all-rows set-aside count reads 631
against 619 while the admitted stratum's falls from 53 to 52.

## What changed, and what is new

| | First run, 2 Oct | This run, 6 Oct |
| --- | ---: | ---: |
| Publications / first-of-session | 17 / 15 | 19 / 17 |
| Bars / symbols | 53,452 / 2,053 | 60,964 / 2,221 |
| Rows | 6,064 | 7,128 |
| Nights with a settled ticket (all rows / exploratory admitted) | 14 / 14 | 16 / 15 |
| Exploratory admitted: settled | 202 | 267 |
| Exploratory admitted: wins / losses / even | 37 / 159 / 6 | 50 / 208 / 9 |
| Exploratory admitted: mean R, median R | −0.235, −0.47 | −0.189, −0.40 |
| Exploratory admitted: mean of night means, 95% CI | −0.291 [−0.486, −0.109] | −0.237 [−0.431, −0.049] |

The exploratory numbers moved for two reasons. The 1 October signals, all 579
pending on 2 October, now have two sessions of bars: the night's 50 settled
admitted tickets are 0 wins, 47 losses and 3 even, mean −0.364R (sum −18.21R),
and its 31 open ones are still walking; on their own they would have taken the
admitted mean DOWN, to about −0.26R. The improvement to −0.189R, and all 13
new wins, came from fifteen late-September tickets that were open or set aside
on 2 October and have settled since -- 2 of 28 September, 12 of 29 September,
and LH of 11 September, whose session bar a later publication supplied -- at
13 wins, 2 losses, +15.10R. No previously settled ticket changed its R.

**A night read before its tickets' fifth session is biased toward losses.** A
stop settles on its first bad day; a winner settles at its rules exit or its
horizon. The 29 September night read −0.425R over 27 settled on 2 October and
reads −0.038R over 39 now, its twelve late settlers 10 winners; the
28 September night went from −0.364R over 9 to +0.053R over 11. The 1 October
night's 50 settled with 0 wins has 31 tickets still open, and the five
confirmatory stops below are the first-session settlers of 45 rows. Neither is
a night's result until its horizon has passed. The first report's reading over
11 to 30 September carried the same bias on its last nights: 25 to
30 September had not reached their fifth session by the 1 October publication.
Every exploratory stratum is still negative at this re-read, and the admitted
stratum still loses least; the night-level numbers are the ones to re-read as
nights complete.

**Confirmatory admitted stratum: 132 rows**, 45 from 2 October and 87 from
5 October. Five are settled, all at −1.00R: RRGB, STEM, TSQ, ALMR and AWK, each
a 2 October signal stopped on 5 October, its first session. Fifteen are open,
81 pending (every 5 October ticket, whose first session is 6 October), 17
uncertain, 4 not filled, 10 without a ticket. Nothing here is readable under
the scorecard's twenty-settled minimum, and nothing is read.

**The reader's own admissions** -- the live policy's accepted reviews that
left the grade at A or A+ (86 rows carry an accepted reader judgement; 84 of
them were lowered to B, C or skip) -- are two rows, both DAC: the 1 October
signal, whose fill is uncertain on daily bars, and the 2 October signal, filled
on 5 October and holding.

## How to read it

Nothing confirmatory is readable yet. The first confirmatory number that could
be readable arrives with the 9 October publication, and only if all fifteen
open 2 October tickets settle by then, because 20 is the scorecard's minimum.
The 5 October tickets reach their fifth session on 12 October; the 1 October
exploratory tickets settle on 8 October.

The method of extension is the one this report uses: the frozen spec's rules
stay byte-identical, publications are appended in the frozen file's own layout
as they are published, each extension is committed with its own hash and its
byte-level diff against the frozen file, and the code stays the merged one. A
change to anything but the publication list is a new spec with a new freeze.
