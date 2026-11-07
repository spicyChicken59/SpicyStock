# The signal-outcome study over forty-seven publications: the confirmatory figure, read again after 6 November

**What was run.** The frozen study, `tools/signal_outcomes.py` as PR #100
merged it (blob `39d4f25a…`, unchanged on `main` at `959c2445`), re-run on
7 November 2026 in the sandbox over forty-seven publications: the thirty-seven
the 24 October extension named and the ten published since -- run 2026-10-26
(`adaf1b1a`), 2026-10-27 (`36ce7ef9`), 2026-10-28 (`dbb8358c`), 2026-10-29
(`cd6418f1`), 2026-10-30 (`e4063d25`), 2026-11-02 (`3cd890ec`), 2026-11-03
(`ef855d6d`), 2026-11-04 (`a0d9172e`), 2026-11-05 (`29d9474f`) and 2026-11-06
(`f1feb636`). Every one of the ten is the first publication of its session and
contributes signals; none is a revision. The spec it read,
[`2026-11-07-signal-outcomes-spec-extended.json`](2026-11-07-signal-outcomes-spec-extended.json)
(SHA-256 `ccc303bb3f00…`), is the frozen file (SHA-256 `d93ad856b69a…`) with
thirty entries appended in its own layout -- the twenty the 24 October
extension carried and these ten: a byte-level `diff` against the frozen file
shows the comma that joins them and the added lines and nothing else, and that
diff is retained as
[`spec-diff.txt`](2026-11-07-signal-outcomes-confirmatory-evidence/spec-diff.txt).
Every rule, threshold, estimand and the freeze date are the frozen ones, and the
frozen file is untouched. Python 3.12.3, pandas 3.1.0, exit 0, 20.4 seconds of
wall time, no provider, model or network call; the command, interpreter, exit
code and timing are in
[`run-record.txt`](2026-11-07-signal-outcomes-confirmatory-evidence/run-record.txt).
The same command under Python 3.13.17 and pandas 3.0.5 wrote the same bytes,
exit 0 in 19.2 seconds, its record and the two outputs' digests in
[`run-record-second-interpreter.txt`](2026-11-07-signal-outcomes-confirmatory-evidence/run-record-second-interpreter.txt).
The summary is
[verbatim](2026-11-07-signal-outcomes-confirmatory-evidence/summary.txt) and
every row is in
[`signal-outcomes.json.gz`](2026-11-07-signal-outcomes-confirmatory-evidence/signal-outcomes.json.gz)
(uncompressed SHA-256 `eac24c37757f…`).

## What changed, and what is new

| | 24 Oct | This run, 7 Nov |
| --- | ---: | ---: |
| Publications / first-of-session | 37 / 31 | 47 / 41 |
| Bars / symbols | 113,394 / 2,840 | 152,156 / 3,145 |
| Rows | 14,552 | 20,676 |
| Nights with a settled ticket (all rows / exploratory admitted) | 30 / 15 | 40 / 15 |
| Exploratory admitted: settled | 301 | 303 |
| Exploratory admitted: wins / losses / even | 73 / 219 / 9 | 73 / 221 / 9 |
| Exploratory admitted: mean R, median R | −0.119, −0.33 | −0.123, −0.33 |
| Exploratory admitted: mean of night means, 95% CI | −0.180 [−0.347, −0.014] | −0.189 [−0.354, −0.022] |
| Confirmatory admitted: rows / settled | 1370 / 316 | 2203 / 575 |

Every one of the 14,552 rows of the 24 October run is in this one under the same
session, ticker and publication, and no settled ticket changed its R. **453 rows
moved between buckets.** 393 are the 19 to 23 October nights completing: 135 open
and 126 pending rows settled, 110 pending rows became uncertain and 22 were not
filled. Four are rows set aside because a later publication re-priced their
symbol's bars, the frozen rule that the newest publication wins each bar read
the re-priced history, and the signal's own close no longer matched
(`basis_mismatch`): BUUU of 13 October, a grade-C row settled at −1.00R, and
BUUU of 23 October, a skip row still pending, its history divided by ten in the
26 October publication; and SUPN of 19 and 20 October, two vetoed rows settled
at +2.09R and −0.25R, its history divided by about 1.18 in the 4 November
publication. So three tickets that were settled on 24 October are settled no
longer; none is admitted, and the R of every ticket settled in both runs is the
same. **The remaining fifty-six are rows of the two oldest nights -- 21 of 11
September and 35 of 14 September -- moved the way the 24 October report
described**, by the bars the ten publications carry: the study reads bars from
the bursts' 120-session series and from the `observations` block and nothing
else, and each of the ten publications lists 133 to 1104 bursts but charts only
its tickets, its cut names, its closest miss and its top 24 bursts by rank
(`pipeline.SERIES_TOP`). Fifty-one of the fifty-six rows, over forty-five
symbols (six of them on both nights), belong to symbols one of the ten
publications charted: the series begins between 6 May and 19 May for
forty-three of them and, for BLSM and LYNX, each a 56-session series for a
name listed more recently, on 7 August and 19 August, still before its
September signal, so a September signal whose own-session bar no earlier
publication had carried now has it and is walked (16 settled, 22 uncertain
and 13 not filled). The other five
rows, five symbols, gained no series: every one was listed as a burst again
between 26 October and 6 November below the charted ones, so its `observations`
block supplies bars of those sessions and nothing earlier, and a signal that had
no later bar at all (`unmeasured`) now has later bars without its own session
among them and is set aside (`basis_mismatch`). Sixteen of the fifty-six settled
for the first time (5 C, 4 vetoed, 3 B, 2 admitted and 2 skip). Of the
fifty-six, five are admitted rows, all walked: TRV of 11 September settled, IBM
of 11 September uncertain, EPAM of 11 September not filled, TBBB of 14 September
not filled and WSM of 14 September settled -- so, unlike on 24 October, the
exploratory admitted stratum's settled figures moved: 303 settled where the 24
October run read 301, −0.123R a ticket, the mean of its fifteen night means
−0.189R with an interval of [−0.354, −0.022]. The exploratory stratum is still
negative and its interval still excludes zero.

## The confirmatory figure

**Admitted, confirmatory: 575 settled** over twenty-four nights (2 October to
4 November), 153 wins, 418 losses and 4 even, sum −125.15R, mean −0.218R,
median −0.52R; the mean of the twenty-four night means is −0.003R with a 95%
night-bootstrap interval of **[−0.232, +0.220]**. It clears the scorecard's
twenty-settled minimum, so it is readable, and the spec's E2 makes it the one
figure that can be read as evidence. **The interval includes zero: the
confirmatory nights do not establish whether the mechanical admitted tickets
lose or win.** The two estimands moved apart: the mean R a ticket fell from
−0.081R to −0.218R while the mean of night means rose from −0.051R to −0.003R,
because one weights tickets and the other nights, and the 4 November night
below is a fifth of the stratum's settled tickets and one of its twenty-four
nights. Beside the figure, as the spec labels them and never pooled: 567
uncertain tickets, 558 of them with a bound -- the R each would have reached had
its uncertain day filled at its trigger -- summing to −35.98R, so that pooled
with the 575 settled the mean would be −0.142R, and 9 with no bound; and the
cost lines, −0.254R at 5 basis points a side and −0.360R at 20.

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
| 19 Oct | red | 45 | 20 | 14 / 5 / 1 | +29.01 | +1.450 | 0 |
| 20 Oct | red | 112 | 29 | 9 / 20 / 0 | −1.69 | −0.058 | 0 |
| 21 Oct | red | 35 | 6 | 1 / 5 / 0 | −2.75 | −0.458 | 0 |
| 22 Oct | red | 257 | 18 | 4 / 14 / 0 | −1.90 | −0.106 | 0 |
| 23 Oct | red | 65 | 17 | 9 / 7 / 1 | +10.79 | +0.635 | 0 |
| 26 Oct | red | 50 | 11 | 6 / 5 / 0 | +2.33 | +0.212 | 0 |
| 27 Oct | yellow | 78 | 11 | 2 / 9 / 0 | −8.41 | −0.765 | 0 |
| 28 Oct | yellow | 51 | 15 | 9 / 6 / 0 | +10.78 | +0.719 | 0 |
| 29 Oct | yellow | 117 | 31 | 15 / 16 / 0 | +3.33 | +0.107 | 0 |
| 30 Oct | red | 24 | 3 | 2 / 1 / 0 | +1.91 | +0.637 | 0 |
| 2 Nov | yellow | 82 | 14 | 2 / 12 / 0 | −4.43 | −0.316 | 0 |
| 3 Nov | yellow | 53 | 10 | 0 / 10 / 0 | −8.02 | −0.802 | 0 |
| 4 Nov | yellow | 245 | 119 | 0 / 119 / 0 | −122.41 | −1.029 | 4 |
| 5 Nov | red | 4 | 0 | — | — | — | 0 |
| 6 Nov | red | 129 | 0 | — | — | — | 101 |

"Still moving" counts the rows open or pending on 6 November, the newest
session; a night's horizon is its fifth session, 6 November for 30 October and
9 to 13 November for 2 to 6 November. Twenty-four of the twenty-six nights are
complete: every one of their rows has reached its horizon or can no longer move
on later bars, and only a bar a later publication revises could move one. The
two nights that are not carry 105 rows still open or pending: the 4 November
night's four open rows, which reach their horizon on 11 November, and the 101
pending rows of the 6 November night, whose entry session is Monday 9 November.
Sixteen of the twenty-six nights hold fewer than twenty settled tickets each, so
their means are not rates; only 2, 5, 8, 12, 14, 15, 19, 20 and 29 October and 4
November reach twenty.

## The 4 November night

**The 4 November night is the largest single loss in the stratum, and the
night with the most settled tickets: 245 admitted rows, 119 settled, 0 wins and
119 losses, −122.41R.** Its entry session was 5 November, the session the record
then measured RED with the alarm fired -- 91 stocks up 4% against 844 down, over
the scaled alarm of 380.5 -- and every settled ticket of the night stopped: 72
on the entry day itself, 47 after holding through it with the stop raised to the
entry day's low, 43 of them at the next open and 4 later in that session;
twenty-five lost more than 1R, the deepest −3.94R, where a stop filled under its
price. It was the same for every stratum: of the night's 1,104 rows 451 settled,
2 wins and 449 losses, −451.01R. Without it the other twenty-three confirmatory
nights hold 456 settled at −2.74R in sum, −0.006R a ticket. It is the first
night of the study on which the live policy published burst tickets -- HQY, RCBC
and VIK, each A+ under an accepted review -- and all three are among its
losses, as the record's own model plans are. One night is one night: nothing
here reads it as a rate, and the regime's turn the next session is the market's
and not the method's.

## What settled since 24 October

Of the 65 confirmatory admitted rows still open or pending on 24 October, 45
have settled -- 6 of 19 October, 5 of 20 October, 2 of 21 October, 15 of 22
October and 17 of 23 October -- at 25 wins, 19 losses and 1 even, +25.30R in
sum; 16 became uncertain and 4 were not filled. The 19 October night read
+1.411R over 14 settled on 24 October and reads +1.450R over 20 now, all 6 of
its late settlers winners; it stays the best night in the stratum by mean and
by sum. The 20 October night read −0.255R over 24 and reads −0.058R over 29, its
5 late settlers all winners. The 22 October night read −1.000R over its 3
first-session stops and reads −0.106R over 18, the 15 that settled after 24
October at 4 wins, 11 losses, +1.10R. The 23 October night, which had no settled
ticket on 24 October, settled 17 at 9 wins, 7 losses and 1 even, +10.79R.

## The ten new nights

Of the ten nights appended, six were YELLOW and four RED. 26 October (RED)
settled 11 at +2.33R; 27 October (YELLOW) 11 at −8.41R; 28 October (YELLOW) 15
at +10.78R, 9 of them wins; 29 October (YELLOW), with 117 admitted rows, 31 at
+3.33R; 30 October (RED) 3 at +1.91R; 2 November (YELLOW) 14 at −4.43R; 3
November (YELLOW) 10 at −8.02R, every one a loss; 4 November (YELLOW) as above.
The 5 November night has 4 admitted rows, 3 of them withheld by the stop rule
and 1 uncertain. The 6 November night has 129 admitted rows, 101 of them
pending Monday's open and 28 withheld by the stop rule.

## The regimes, the account and the frozen sentences

**Nine of the twenty-six confirmatory nights were YELLOW** -- 8, 9 and 12
October, 27, 28 and 29 October, and 2, 3 and 4 November -- and seventeen RED;
GREEN has still never been published. Under YELLOW the live policy admits A+
alone (half size, an accepted review required); the study's admitted stratum is
A+ and A, ticketed at the GREEN multiplier, without the reader. The nine YELLOW
nights' 305 settled sum to −129.26R (mean −0.424R), −122.41R of it the 4
November night's and the other eight nights' 186 settled −6.85R (mean −0.037R);
the seventeen RED nights' 270 settled sum to +4.11R (mean +0.015R), the split
the findings replay prints. Of the YELLOW nights' 305 settled, 18 are
mechanical A+ (5 wins, 13 losses, −7.18R) and 287 grade A (−122.08R), refused
under YELLOW by the regime's own grade band. Across every confirmatory night the
mechanical A+ tickets that settled are 25: BDX, MMSI and ROKU of 5 October, HAE
and MANH of 8 October, RAL of 13 October, JAKK of 15 October, CSV of 22 October,
RIGL of 26 October, ORLY of 28 October, AEE, BSY, KMB, PNFP, PVH, TTEK and XEL
of 29 October, RDVT of 3 November, and AEP, CCI, CM, HQY, RCBC, RPRX and TD of 4
November -- 6 wins, 19 losses, −12.46R. The study's footer and the spec's own
reading rule still say that every ticket was refused by the RED gate; the 17
October report corrected the sentence for the YELLOW nights, and this run adds
the three rows the live policy published on 4 November, which no gate refused.
The code and the spec stay frozen, so the footer is unchanged.

**The account changed under the study a second time.** The spec tickets each
signal with "the publication's own account block". Every publication from
`e67f8cba`, the second of 8 October, carried $2,000 of model equity at 0.5%
risk, and every publication from `a0d9172e`, the first of 4 November, carries
$30,000 at 0.5%; `a0d9172e` is the first publication of its session, so the
signals ticketed at $30,000 are those of 4 November on. At $150 of risk a
ticket, every admitted setup of the three $30,000 nights that the stop rule let
through sizes to a whole share:
the admitted rows the study marks `no_order` were 24, 28, 26, 51, 5, 30 and 15
a night on 26 October to 3 November and are 0, 0 and 0 on 4 to 6 November, and
across every stratum 120 to 313 a night before against 1, 0 and 0 after. The
confirmatory nights are therefore drawn from three populations -- the $10,000
nights through 8 October, the $2,000 nights from 9 October to 3 November, the
setups a $2,000 account could buy a share of, and the $30,000 nights from 4
November -- and the confirmatory figure mixes them. The study's rule is frozen
and says so; nothing here changes it.

**Admission is not in the frozen study either.** Since 4 November the live
policy admits a name the dollar scan alone discovered only on a
range-expansion, higher-volume day (`src/admission.py`); the study's admitted
stratum is the grade band without a veto and applies no such rule, so 1,566 of
its 2,203 confirmatory rows came through the dollar scan alone, 99 of the 4
November night's 245 among them. The study walks daily bars only. The
minute-bar resolution the evening applies since PR #168 to a first day a daily
bar cannot place is not part of the frozen walk, so the 567 uncertain
confirmatory tickets stay uncertain here.

## The reader's own admissions

The live policy's accepted reviews that left a grade at A or A+ are thirteen
rows now: DAC of 1 October, its fill uncertain on daily bars
(`trigger_timing`); DAC of 2 October, settled at −0.37R; LYB of 30 October and
IBTA and UTL of 2 November, each not filled; and eight of 4 November -- HQY and
RCBC, the published tickets, each stopped at −1.00R; VIK, the third published
ticket, uncertain on daily bars (`stop_sequence`, the record's own minute bars
having placed its fill at the open and its stop the same day); CCI, lowered to
A, stopped at −1.32R; IDT, grade A, stopped at −1.00R; TM not filled; and TRV
and WEST uncertain, each having opened above its limit. Five settled, 0 wins
and 5 losses, −4.69R: under the scorecard's twenty-settled minimum, so nothing is
read from them as a rate.

## How to read it

The confirmatory figure is readable, and it still does not establish a sign:
the mean of night means moved from −0.051R to −0.003R a night as the 19 to 23
October nights completed at +25.30R, while the mean R a ticket moved from
−0.081R to −0.218R as the 4 November night's 119 settled tickets all stopped, −122.41R, and
the interval still spans zero. The two nights not yet complete carry 105 rows still
moving, so the figure will move as they complete, and it should be read again
after 13 November, when the 6 November tickets reach their fifth session. A
YELLOW figure of its own now has nine nights and 305 settled, but one night is
−122.41R of its −129.26R, and the frozen spec has no YELLOW estimand; nothing
here reads it as a rate. Nothing is tuned: no threshold, no rule and no
population is changed in response to these numbers, and no statistic here is an
edge claim.

The method of extension is unchanged: the frozen spec's rules stay
byte-identical, publications are appended in the frozen file's own layout, each
extension is committed with its own hash and its byte-level diff against the
frozen file, and the code stays the merged one. A change to anything but the
publication list is a new spec with a new freeze.
