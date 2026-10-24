# The signal-outcome study over thirty-seven publications: the confirmatory figure, read again after 23 October

**What was run.** The frozen study, `tools/signal_outcomes.py` as PR #100
merged it (blob `39d4f25a…`, unchanged on `main` at `f466932f`), re-run on
24 October 2026 in the sandbox over thirty-seven publications: the thirty-one
the 17 October extension named and the six published since -- run 2026-10-19
(`a34a2978`, and its revision `d179f206`), 2026-10-20 (`0d8494fc`), 2026-10-21
(`2eb0e0be`), 2026-10-22 (`fb70e706`) and 2026-10-23 (`cd239b20`). Five of
them are the first publication of their session and contribute signals; the
one later one, the second 19 October publication, is a revision and
contributes bars. The spec it read,
[`2026-10-24-signal-outcomes-spec-extended.json`](2026-10-24-signal-outcomes-spec-extended.json)
(SHA-256 `ae700f197805…`), is the frozen file (SHA-256 `d93ad856b69a…`) with
twenty entries appended in its own layout -- the fourteen the 17 October
extension carried and these six: a byte-level `diff` against the frozen file
shows the comma that joins them and the added lines and nothing else, and that
diff is retained as
[`spec-diff.txt`](2026-10-24-signal-outcomes-confirmatory-evidence/spec-diff.txt).
Every rule, threshold, estimand and the freeze date are the frozen ones, and the
frozen file is untouched. Python 3.12.3, pandas 3.1.0, exit 0, 15.4 seconds of
wall time, no provider, model or network call; the command, interpreter, exit
code and timing are in
[`run-record.txt`](2026-10-24-signal-outcomes-confirmatory-evidence/run-record.txt).
The same command under Python 3.13.17 and pandas 3.0.5 wrote the same bytes,
exit 0 in 17.0 seconds, its record and the two outputs' digests in
[`run-record-second-interpreter.txt`](2026-10-24-signal-outcomes-confirmatory-evidence/run-record-second-interpreter.txt).
The summary is
[verbatim](2026-10-24-signal-outcomes-confirmatory-evidence/summary.txt) and
every row is in
[`signal-outcomes.json.gz`](2026-10-24-signal-outcomes-confirmatory-evidence/signal-outcomes.json.gz)
(uncompressed SHA-256 `310a2fdecb3f…`).

## What changed, and what is new

| | 17 Oct | This run, 24 Oct |
| --- | ---: | ---: |
| Publications / first-of-session | 31 / 26 | 37 / 31 |
| Bars / symbols | 95,675 / 2,572 | 113,394 / 2,840 |
| Rows | 11,323 | 14,552 |
| Nights with a settled ticket (all rows / exploratory admitted) | 25 / 15 | 30 / 15 |
| Exploratory admitted: settled | 301 | 301 |
| Exploratory admitted: wins / losses / even | 73 / 219 / 9 | 73 / 219 / 9 |
| Exploratory admitted: mean R, median R | −0.119, −0.33 | −0.119, −0.33 |
| Exploratory admitted: mean of night means, 95% CI | −0.180 [−0.347, −0.014] | −0.180 [−0.347, −0.014] |
| Confirmatory admitted: rows / settled | 856 / 209 | 1370 / 316 |

Every one of the 11,323 rows of the 17 October run is in this one under the same
session, ticker and publication; no settled ticket changed its R, and the
exploratory admitted stratum's settled figures did not move. **Forty rows of the
two oldest nights did move between buckets, none of them settled before**: 19 of
11 September and 21 of 14 September, 13 of them settling for the first time (6
vetoed, 4 C, 2 B and 1 skip, none admitted). The mechanism is the frozen rule
that the newest publication wins each bar, and it worked two ways, depending on
whether a later publication charted the symbol. The study reads bars from the
bursts' 120-session series and from the `observations` block and nothing else,
and each of the six publications lists 335 to 988 bursts but charts only its
tickets, its cut names, its closest miss and its top 24 bursts by rank
(`pipeline.SERIES_TOP`). Twenty-eight of the forty rows, over twenty-three
symbols (five of them on both nights), belong to symbols one of the six
publications charted: the series begins between 29 April and 5 May, so a
September signal whose later bars no earlier publication had carried now has
them and is walked (13 settled, 9 uncertain and 6 not filled). The other twelve
rows, twelve symbols, gained no series: eleven were listed as bursts again
between 19 and 23 October below the charted ones and one, EDHL, was only
observed, so their `observations` block supplies two to five bars of 19 to 23
October and nothing earlier, and a signal that had no later bar at all
(`unmeasured`) now has later bars without its own session among them and is set
aside (`basis_mismatch`). Of the forty, three are admitted rows -- TWFG and VRDN
of 14 September the second way, from `unmeasured` to `basis_mismatch`, and ROKU
of 14 September the first, from `basis_mismatch` to `not_filled` -- so the
exploratory admitted stratum's non-settled buckets read 106 not filled, 1
unmeasured and 50 set aside where the 17 October run read 105, 3 and 49. The exploratory stratum is still negative and
its interval still excludes zero.

## The confirmatory figure

**Admitted, confirmatory: 316 settled** over fifteen nights (2 to 22 October), 92
wins, 221 losses and 3 even, sum −25.53R, mean −0.081R, median −0.37R; the mean
of the fifteen night means is −0.051R with a 95% night-bootstrap interval of
**[−0.319, +0.251]**. It clears the scorecard's twenty-settled minimum, so it is
readable, and the spec's E2 makes it the one figure that can be read as
evidence. **The interval includes zero: the confirmatory nights do not establish
whether the mechanical admitted tickets lose or win.** Beside it, as the spec
labels them and never pooled: 371 uncertain tickets, 305 of them with a bound --
the R each would have reached had its uncertain day filled at its trigger --
summing to +0.68R, so that pooled with the 316 settled the mean would be
−0.040R, and 66 with no bound; and the cost lines, −0.118R at 5 basis points a
side and −0.229R at 20.

| Session | Regime | Admitted rows | Settled | W / L / E | Sum R | Mean R | Still moving |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: |
| 2 Oct | red | 45 | 20 | 5 / 15 / 0 | −1.18 | −0.059 | 0 |
| 5 Oct | red | 87 | 40 | 7 / 33 / 0 | −16.52 | −0.413 | 0 |
| 6 Oct | red | 43 | 10 | 6 / 4 / 0 | +4.37 | +0.437 | 0 |
| 7 Oct | red | 29 | 6 | 4 / 2 / 0 | +3.30 | +0.550 | 0 |
| 8 Oct | yellow | 188 | 73 | 25 / 48 / 0 | +2.58 | +0.035 | 0 |
| 9 Oct | yellow | 53 | 12 | 1 / 11 / 0 | −5.17 | −0.431 | 0 |
| 12 Oct | yellow | 52 | 20 | 10 / 10 / 0 | +2.49 | +0.125 | 0 |
| 13 Oct | red | 59 | 5 | 2 / 3 / 0 | +0.29 | +0.058 | 0 |
| 14 Oct | red | 85 | 21 | 11 / 9 / 1 | +5.60 | +0.267 | 0 |
| 15 Oct | red | 187 | 61 | 9 / 51 / 1 | −28.22 | −0.463 | 0 |
| 16 Oct | red | 28 | 3 | 0 / 3 / 0 | −1.23 | −0.410 | 0 |
| 19 Oct | red | 45 | 14 | 8 / 5 / 1 | +19.75 | +1.411 | 6 |
| 20 Oct | red | 112 | 24 | 4 / 20 / 0 | −6.12 | −0.255 | 5 |
| 21 Oct | red | 35 | 4 | 0 / 4 / 0 | −2.47 | −0.618 | 2 |
| 22 Oct | red | 257 | 3 | 0 / 3 / 0 | −3.00 | −1.000 | 15 |
| 23 Oct | red | 65 | 0 | — | — | — | 37 |

"Still moving" counts the rows open or pending on 23 October, the newest
session; a night's horizon is its fifth session, 23 October for 16 October and
26 to 30 October for 19 to 23 October. The eleven nights through 16 October are
complete: every one of their rows has reached its horizon, and only a bar a
later publication revises could move one. The five nights since carry 65 rows
still open or pending, 37 of them the 23 October night's tickets, whose entry
session is Monday 26 October. Nine of the sixteen nights hold fewer than twenty
settled tickets each, so their means are not rates; only 2, 5, 8, 12, 14, 15 and
20 October reach twenty.

## What settled since 17 October

Of the 78 confirmatory admitted rows still open or pending on 17 October, 62
have settled -- 1 of 12 October, 1 of 13 October, 14 of 14 October, 43 of 15
October and 3 of 16 October -- at 22 wins, 39 losses and 1 even, −0.97R in sum;
12 became uncertain and 4 were not filled. The 14 October night read −0.450R
over 7 settled on 17 October and reads +0.267R over 21 now, 11 of its 14 late
settlers winners. **The 15 October night's 61 settled are its 18 first-session
stops and the 43 that settled after 17 October** (9 wins, 33 losses and 1 even,
−10.22R): read whole it is −0.463R a ticket where its first-session stops alone
read −1.000R, the early-read bias the 17 October report named, measured a second
time -- and this time the night ends clearly negative, the largest single loss in
the stratum. The 16 October night settled its three at three losses.

The five new nights are all RED. The 19 October night is the best in the
stratum: 14 settled, 8 wins, +19.75R, mean +1.411R, with 6 rows still open until
26 October. The 20 October night is −6.12R over 24; 21 October −2.47R over 4;
and 22 October, with 257 admitted rows the largest night the study has read, has
3 first-session stops settled, 15 open, 79 uncertain, 60 not filled and 100 rows
without a ticket, 87 of them because the $2,000 account could not size a whole
share and 13 withheld by the stop rule.

## The regimes, the account and the frozen sentences

**Three of the sixteen confirmatory nights were YELLOW** -- 8, 9 and 12 October --
and every night since has been RED. Under YELLOW the live policy admits A+ alone
(half size, an accepted review required); the study's admitted stratum is A+ and
A, ticketed at the GREEN multiplier, without the reader. The three YELLOW nights'
105 settled sum to −0.10R (mean −0.001R); the thirteen RED nights' 211 settled
sum to −25.43R (mean −0.121R), the split the findings replay prints. Of the
yellow nights' 105 settled, 2 are A+ (both 8 October, +2.65R between them: an
accepted review lowered MANH to C, which the band then refused, and reader
authority refused HAE's reply, so the accepted-review requirement withheld its
ticket); the other 103 are grade A, refused under YELLOW by the regime's own
grade band. Across every confirmatory night the mechanical A+ tickets that
settled are 8: BDX, MMSI and ROKU of 5 October, HAE and MANH of 8 October, RAL
of 13 October, JAKK of 15 October and CSV of 22 October -- 2 wins, 6 losses,
−3.18R. The study's footer and the spec's own reading rule still say that every
ticket was refused by the RED gate; the 17 October report corrected the
sentence, and this one carries the correction. The code and the spec stay
frozen, so the footer is unchanged.

**The account changed under the study.** The spec tickets each signal with "the
publication's own account block". Every publication from `e67f8cba`, the second
of 8 October, carries $2,000 of model equity at 0.5% risk, and every earlier one
carried $10,000. That revision contributes bars only, so the signals ticketed at
$2,000 are those of 9 October on. At $10 of risk a ticket, halved again by the
stop-risk rule on a stop-constrained ticket, many admitted setups size to no
whole share: the admitted rows the study marks `no_order` were 0 to 6 a night
through 8 October and are 22, 26, 29, 44, 59, 8, 12, 44, 21, 87 and 23 on 9 to
23 October (375 in all), and across every stratum 5 to 29 a night before against
107 to 336 after. The confirmatory nights before and after 9 October are
therefore drawn from different populations -- after it, the setups whose price
a $2,000 account can buy at least one share of -- and the confirmatory figure
mixes the two. The study's rule is frozen and says so; nothing here changes it.

The study walks daily bars only. The minute-bar resolution the evening applies
since PR #168 to a first day a daily bar cannot place is not part of the frozen
walk, so the 371 uncertain confirmatory tickets stay uncertain here.

## The reader's own admissions

The live policy's accepted reviews that left a grade at A or A+ are still two
rows, both DAC: the 1 October signal, its fill uncertain on daily bars
(`trigger_timing`), and the 2 October signal, settled at −0.37R. No accepted
review since 17 October has left a grade in the band. One settled ticket is not
readable, and nothing is read from it.

## How to read it

The confirmatory figure is readable, it moved from −0.138R to −0.051R a night as
the 12 to 16 October nights completed, and it still does not establish a sign;
its interval widened on the upside because the 19 October night sits far above
every other. The five RED nights since 16 October carry the 65 rows still
moving, so the figure will move as they complete, and it should be read again
after 30 October, when the 23 October tickets reach their fifth session. A
YELLOW figure of its own still needs more YELLOW nights than three, and there has
been none since 12 October. Nothing is tuned: no threshold, no rule and no
population is changed in response to these numbers, and no statistic here is an
edge claim.

The method of extension is unchanged: the frozen spec's rules stay
byte-identical, publications are appended in the frozen file's own layout, each
extension is committed with its own hash and its byte-level diff against the
frozen file, and the code stays the merged one. A change to anything but the
publication list is a new spec with a new freeze.
