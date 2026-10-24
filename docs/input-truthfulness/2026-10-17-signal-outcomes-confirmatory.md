# The signal-outcome study over thirty-one publications: the first readable confirmatory figure

**Read again on 24 October over thirty-seven publications:**
[the confirmatory figure after 23 October](2026-10-24-signal-outcomes-confirmatory.md).
This report is kept as written.

**What was run.** The frozen study, `tools/signal_outcomes.py` as PR #100
merged it (blob `39d4f25a…`, unchanged on `main` at `2768e467`), re-run on
17 October 2026 in the sandbox over thirty-one publications: the nineteen the
6 October extension named and the twelve published since -- run 2026-10-06
(`b0c6b60e`), 2026-10-07 (`a8f9a36f`), 2026-10-08 (`1e1ffe9c`, `e67f8cba`),
2026-10-09 (`62bce72d`, `dcb12a0b`, `43dcb8d7`), 2026-10-12 (`9936e971`),
2026-10-13 (`8772006f`), 2026-10-14 (`16032f05`), 2026-10-15 (`0f951414`) and
2026-10-16 (`7a1a9e49`). Nine of them are the first publication of their
session and contribute signals; the three later ones are revisions and
contribute bars. The spec it read,
[`2026-10-17-signal-outcomes-spec-extended.json`](2026-10-17-signal-outcomes-spec-extended.json)
(SHA-256 `5598366c9851…`), is the frozen file (SHA-256 `d93ad856b69a…`) with
fourteen entries appended in its own layout -- the 6 October extension's two
and these twelve: a byte-level `diff` against the frozen file shows the comma
that joins them and the added lines and nothing else, and that diff is
retained as
[`spec-diff.txt`](2026-10-17-signal-outcomes-confirmatory-evidence/spec-diff.txt).
Every rule, threshold, estimand and the freeze date are the frozen ones, and the
frozen file is untouched. Python 3.12.3, pandas 2.2.3, exit 0, 13.5 seconds of
wall time, no provider, model or network call; the command, interpreter, exit
code and timing are in
[`run-record.txt`](2026-10-17-signal-outcomes-confirmatory-evidence/run-record.txt).
The same run under Python 3.11.15 and pandas 3.0.6 wrote the same bytes. The
summary is
[verbatim](2026-10-17-signal-outcomes-confirmatory-evidence/summary.txt) and
every row is in
[`signal-outcomes.json.gz`](2026-10-17-signal-outcomes-confirmatory-evidence/signal-outcomes.json.gz)
(uncompressed SHA-256 `95ab5a364411…`).

## What changed, and what is new

| | 6 Oct | This run, 17 Oct |
| --- | ---: | ---: |
| Publications / first-of-session | 19 / 17 | 31 / 26 |
| Bars / symbols | 60,964 / 2,221 | 95,675 / 2,572 |
| Rows | 7,128 | 11,323 |
| Nights with a settled ticket (all rows / exploratory admitted) | 16 / 15 | 25 / 15 |
| Exploratory admitted: settled | 267 | 301 |
| Exploratory admitted: wins / losses / even | 50 / 208 / 9 | 73 / 219 / 9 |
| Exploratory admitted: mean R, median R | −0.189, −0.40 | −0.119, −0.33 |
| Exploratory admitted: mean of night means, 95% CI | −0.237 [−0.431, −0.049] | −0.180 [−0.347, −0.014] |
| Confirmatory admitted: rows / settled | 132 / 5 | 856 / 209 |

Every one of the 7,128 rows of the 6 October run is in this one under the same
session, ticker and publication; no settled ticket changed its R. The
exploratory admitted stratum moved because 34 of its tickets that were open on
6 October have settled since -- 31 of 1 October, 2 of 29 September and 1 of
30 September -- at 23 wins and 11 losses, +14.67R. The 1 October night read
−0.364R over 50 settled with no win on 6 October and reads −0.087R over 81
settled with 20 wins now. That is the bias the 6 October report named, measured
on a whole night: **a night read before its tickets' fifth session leans toward
losses**, because a stop settles on its first bad day and a winner at its rules
exit or its horizon. The exploratory stratum is still negative and its interval
still excludes zero.

## The confirmatory figure

**Admitted, confirmatory: 209 settled** over ten nights (2 to 15 October), 58
wins, 150 losses and 1 even, sum −32.72R, mean −0.157R, median −0.39R; the mean
of the ten night means is −0.138R with a 95% night-bootstrap interval of
**[−0.431, +0.129]**. It clears the scorecard's twenty-settled minimum, so it is
readable, and the spec's E2 makes it the one figure that can be read as
evidence. **The interval includes zero: the confirmatory nights do not establish
whether the mechanical admitted tickets lose or win.** Beside it, as the spec
labels them and never pooled: 241 uncertain tickets, 205 of them with a bound --
the R each would have reached had its uncertain day filled at its trigger --
summing to +4.27R, so that pooled with the 209 settled the mean would be
−0.069R, and 36 with no bound; and the cost lines, −0.195R at 5 basis points a
side and −0.310R at 20.

| Session | Regime | Admitted rows | Settled | W / L / E | Sum R | Mean R | Still moving |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: |
| 2 Oct | red | 45 | 20 | 5 / 15 / 0 | −1.18 | −0.059 | 0 |
| 5 Oct | red | 87 | 40 | 7 / 33 / 0 | −16.52 | −0.413 | 0 |
| 6 Oct | red | 43 | 10 | 6 / 4 / 0 | +4.37 | +0.437 | 0 |
| 7 Oct | red | 29 | 6 | 4 / 2 / 0 | +3.30 | +0.550 | 0 |
| 8 Oct | yellow | 188 | 73 | 25 / 48 / 0 | +2.58 | +0.035 | 0 |
| 9 Oct | yellow | 53 | 12 | 1 / 11 / 0 | −5.17 | −0.431 | 0 |
| 12 Oct | yellow | 52 | 19 | 9 / 10 / 0 | +1.59 | +0.084 | 1 |
| 13 Oct | red | 59 | 4 | 1 / 3 / 0 | −0.54 | −0.135 | 1 |
| 14 Oct | red | 85 | 7 | 0 / 6 / 1 | −3.15 | −0.450 | 14 |
| 15 Oct | red | 187 | 18 | 0 / 18 / 0 | −18.00 | −1.000 | 43 |
| 16 Oct | red | 28 | 0 | — | — | — | 19 |

"Still moving" counts the rows open or pending on 16 October, the newest
session; a night's horizon is its fifth session, 19 October for 12 October and
20 to 23 October for 13 to 16 October. The 15 October night's 18 settled are 18
first-session stops beside 43 open tickets: they are the early-read bias of the
paragraph above, not a night's result. The mean and the interval above include
them. Eight of the eleven nights hold fewer than twenty settled tickets each, so
their means are not rates; only 2, 5 and 8 October reach twenty.

## What the frozen sentences no longer say truly

The study's footer and the spec's own reading rule both say that every ticket
was refused by the RED gate. **Three of the eleven confirmatory nights were
YELLOW** -- 8, 9 and 12 October -- the first non-RED nights the study has read.
Under YELLOW the live policy admits A+ alone (half size, an accepted review
required); the study's admitted stratum is A+ and A, ticketed at the GREEN
multiplier, without the reader. Of the 104 admitted tickets settled on those
three nights, 2 are A+ (both 8 October, +2.65R between them); the other 102 are
grade A, refused under YELLOW by the regime's own grade band. The two A+ passed
the band and were refused by the reader: an accepted review lowered MANH to C,
which the band then refused, and reader authority refused HAE's reply, so the
accepted-review requirement withheld its ticket. None of the 104 met a RED gate.
The YELLOW nights' 104 settled sum to −1.00R; the eight RED nights' 105 to
−31.72R (mean −0.302R), the split the findings replay prints. The code and the
spec stay frozen, so the footer is unchanged; this report is where the sentence
is corrected.

**The account changed under the study.** The spec tickets each signal with "the
publication's own account block". Every publication from `e67f8cba`, the second
of 8 October, carries $2,000 of model equity at 0.5% risk, and every earlier one
carried $10,000. That revision contributes bars only, so the signals ticketed at
$2,000 are those of 9 October on. At $10 of risk a ticket, halved again by the
stop-risk rule on a stop-constrained ticket, many admitted setups size to no
whole share: the admitted rows the study marks `no_order` rose from 0 to 6 a
night through 8 October to 22, 26, 29, 44, 59 and 8 on 9 to 16 October (188 in
all), and from 5 to 29 a night across every stratum to 107 to 327. The
confirmatory nights before and after 9 October are therefore drawn from
different populations -- after it, the setups whose price a $2,000 account can
buy at least one share of -- and the confirmatory figure mixes the two. The
study's rule is frozen and says so; nothing here changes it.

The study walks daily bars only. The minute-bar resolution the evening applies
since PR #168 to a first day a daily bar cannot place is not part of the frozen
walk, so the 241 uncertain confirmatory tickets stay uncertain here.

## The reader's own admissions

The live policy's accepted reviews that left a grade at A or A+ are still two
rows, both DAC: the 1 October signal, its fill uncertain on daily bars
(`trigger_timing`), and the 2 October signal, settled at −0.37R. One settled
ticket is not readable, and nothing is read from it.

## How to read it

The first confirmatory figure is readable and it does not establish a sign. The
four RED nights still inside their hold (13 to 16 October) carry 77 of the
stratum's 78 rows still open or pending, so the figure will move as they
complete, and it should be read again after 23 October, when the 16 October
tickets reach their fifth session. A YELLOW figure of its own needs more YELLOW
nights than three. Nothing is tuned: no threshold, no rule and no population is
changed in response to these numbers, and no statistic here is an edge claim.

The method of extension is unchanged: the frozen spec's rules stay
byte-identical, publications are appended in the frozen file's own layout, each
extension is committed with its own hash and its byte-level diff against the
frozen file, and the code stays the merged one. A change to anything but the
publication list is a new spec with a new freeze.
