# The mechanical backtest's first real result: 158 sessions of the run-6 archive

**What this is.** On 6 October 2026 the owner ran `tools/historical_backtest.py`
over the run-6 archive recovered on his own Windows machine -- 288 sessions of
4,780 names acquired on 1 October, the only real full-market bars this project
has -- through the helper `run-backtest.ps1` described in the
[backtest report](2026-10-02-mechanical-backtest.md), and pasted the two
price-free `summary.txt` files it names. They are recorded under
[`2026-10-06-backtest-results-evidence/`](2026-10-06-backtest-results-evidence/):
`lookback-260-summary.txt` as pasted, including the tool's six per-session
progress lines that preceded it and the helper's "3/4" line that followed, with
the owner's local folder in that line redacted to `<private folder>`;
`lookback-130-summary.txt` with its two em dashes restored, which the Windows
clipboard had delivered as `â€”`. Nothing else in either file was changed; as
committed they are SHA-256 `19c6adaaea5b…` and `24fe6ebfbbfb…`. The owner's
checkout was `main` at `788aa092`, pulled after the merge of #100
(owner-reported: both helper paths present); the helper enforces Python 3.12
and installs `tools/requirements-historical.txt`, and the pandas and NumPy
versions were not reported. The per-row `backtest.json` files carry prices and
stay on the owner's machine. Nothing here can be re-run in this repository,
where the archive does not exist; the numbers are recorded as received.

**Both summaries report completion.** The exact-lookback pass evaluated 28
sessions in 511.7 seconds. The 130-session pass evaluated 158 sessions in
3,813.5 seconds, and its own equivalence line reads **PASS**: on all 28
sessions both lookbacks can read, the regime, every candidate's grade, score
and vetoes, and every plan's prices and shares were identical, 0 differences.
Exit codes and logs were not pasted; the helper's closing line for the first
pass is retained. Both passes report the rules digest `17da26751760`, which is
`build_rules()`'s digest over every module's `RULES` and the archive's own
membership identity: it says the same modules and the same archive made both
passes, it cannot match any publication's `rules_version`, and it does not see
the `--lookback` argument, which is what the equivalence check is for.

**The six progress lines reconcile with the record.** They are the only
per-session readings the summaries carry. 18 to 25 September read 0.85, 0.83,
0.91, 0.85, 0.93 and 0.89 against the nights' own publications' 0.85, 0.82,
0.91, 0.85, 0.94 and 0.89, and 24 and 25 September equal run 6's
later-retrieval 0.93 and 0.89 exactly. The exact pass's regime counts, 15
YELLOW and 13 RED, are the counts the published records' own breadth history
implied (YELLOW through 8 September, RED from 9 September), which the backtest
report noted before the run; the summary gives counts, not their order, and
its six RED progress lines are consistent with that turn.

## The archive and what was evaluated

| | |
| --- | --- |
| Archive | 4,781 symbols with bars of 4,780 intended (the extra symbol is SPY, per the acquisition manifest), 288 sessions, 5 Aug 2025 to 25 Sep 2026; 4,518 `returned_with_bars`, 263 `partial` |
| Exact lookback | 28 sessions, 18 Aug to 25 Sep 2026: 15 YELLOW, 13 RED; the 10-session ratio defined on every session, 0.76 / 1.06 / 1.56 (min / median / max) |
| 130-session lookback | 158 sessions, 10 Feb to 25 Sep 2026: 100 YELLOW, 58 RED, **0 GREEN**; defined on every session, 0.55 / 1.13 / 3.26 |
| Candidates | 90,787 burst rows over the 158 sessions; mechanical grades 558 A+, 11,931 A, 22,089 B, 16,034 C, 40,175 skip |
| Account | the configured one, not a balance: $10,000, 0.5% risk, 25% position cap, 4 slots |
| Reader | NOT RUN: a name's mechanical grade is the ceiling of what the reader could have admitted |

## The production policy

Every ticket is A+ at the YELLOW multiplier, because YELLOW admits nothing
lower and no night was GREEN.

| | 28 sessions | 158 sessions |
| --- | ---: | ---: |
| Tickets | 16 | 99 |
| Nights' regime | all YELLOW | all YELLOW |
| Settled | 6 | 44 |
| Wins / losses / even | 3 / 3 / 0 | 16 / 27 / 1 |
| Win rate | not read (under 20 settled) | 0.36 |
| Net R | +1.94 | +3.72 |
| Mean R per settled ticket | not read | +0.08 |
| Median R | not read | −0.09 |
| Uncertain on daily bars | 6 (4 trigger timing, 2 stop sequence) | 42 (33 trigger timing, 5 stop sequence, 4 open above the limit) |
| Not filled | 4 | 13 |
| Open / pending at the archive's end | 0 / 0 | 0 / 0 |
| SPY over the same windows | not read | +0.37% mean over 44 pairs |

## The counterfactual, regime gate removed (not a policy)

Without the gate every night is treated as GREEN: A and A+ admitted at full
size into four slots. Its ticket set differs from the production set even on
YELLOW nights: its own earlier RED-night and A-grade tickets hold slots that
production's do not, and full-size sizing changes which plans come to a whole
share.

| | 28 sessions | 158 sessions |
| --- | ---: | ---: |
| Tickets | 34 (22 YELLOW, 12 RED) | 153 (95 YELLOW, 58 RED) |
| Settled | 16 | 69 |
| Wins / losses / even | 6 / 9 / 1 | 27 / 40 / 2 |
| Net R | +1.65 | +17.40 |
| Mean R per settled ticket | not read | +0.25 |
| Median R | not read | −0.11 |
| RED nights | 5 settled, 3 / 2, +1.65 | 25 settled, 7 / 18, +1.14 |
| YELLOW nights | 11 settled, 3 / 7, 0.00 | 44 settled, 20 / 22, +16.26 |
| By mechanical grade | A+ 9 settled, +1.18; A 7 settled, +0.47 | A+ 46 settled, +7.18; A 23 settled, +10.22 |
| Uncertain | 10 | 69 |
| Not filled | 5 | 12 |
| Open / pending at the archive's end | 1 / 2 | 1 / 2 |
| SPY over the same windows | not read | +0.31% mean over 69 pairs |

The two pending tickets were written on 25 September, the archive's last
session, so their first session has no bar; the open one was filled but had
not reached its fifth session by then. Only the counterfactual has either,
because only it writes tickets on the RED nights of 21 to 25 September; every
one of the production policy's 99 had resolved by the archive's end.

## Reading

1. **The first readable rate the mechanical policy has had, the reader not
   run.** Forty-four settled tickets clear the scorecard's own minimum of
   twenty. YELLOW nights at the half regime size, over seven and a half months
   of real bars: a 36% win rate, +0.08R per settled ticket, a median of
   −0.09R, net +3.72R. In the configured account's money that is at most about
   $46 before any cost: the YELLOW budget of $25 a ticket is halved again by
   the stop-risk rule, because the stop-constrained limit puts every ticket's
   stop between 2% and 4% under it (`plan.stop_risk()`,
   `plan.STOP_RISK_MULTIPLIER`), so the planned risk is at most $12.50 a ticket
   and whole-share sizing makes it less.
2. **The mean is small against any plausible interval and against costs.** The
   per-row distribution is not here, so the backtest's own dispersion is
   unmeasured. The signal study's admitted stratum, a different population, has
   a standard deviation of 1.03R over 267 settled; at that dispersion the
   standard error of a 44-ticket mean would be about 0.15R. Costs were not
   measured either: the signal study's own tickets cost about 0.04R per settled
   ticket at 5 basis points a side and about 0.16R at 20, and if the backtest's
   tickets cost the same per R the mean would be roughly +0.04 and −0.08. SPY's
   mean move over the same holding windows was +0.37%; 0.08R, with one R the
   fill-to-stop distance and the stop at most 4% under the limit, is at most
   about +0.3% of the position. No comparison with the market is drawn from two
   numbers this close.
3. **On RED nights the counterfactual's tickets summed +1.14R over 25 settled,
   7 wins and 18 losses.** The signal study's admitted stratum -- 267 settled
   RED-night tickets without a slot cap, in the 6 October re-read -- averaged
   −0.19R. Different populations over different windows, not compared row by
   row.
4. **In the counterfactual, A-grade tickets summed +10.22R over 23 settled and
   A+ tickets +7.18R over 46**, on RED and YELLOW nights alike; the summary
   does not split grade by regime. At these counts the difference is not
   readable as a comparison, and it is not a tuning input: this repository's
   standing OMIT of rule changes on these numbers holds. It is recorded, and
   re-read only as more tickets settle.
5. **Forty-two of 99 production tickets are unknowable from daily bars**,
   33 of them because the trigger was crossed after the open. The published
   scorecard uses the same daily-bar fill rule, so its uncertain share is set
   by the same mechanics; only intraday data would resolve it.
6. **GREEN did not occur in 158 sessions.** The policy's full-size state, and
   its admission of A grades, has never been exercised on real bars. The
   10-session ratio reached 3.26, so on any day it cleared 2.0 some other rule
   was firing -- the 50%-in-a-month count over its scaled mark, which is
   YELLOW, or a RED rule, the down-4% alarm or the 5-session ratio -- because
   GREEN requires that none fire; the summary does not say which.

## What it does not establish

- **The reader's judgement.** The live policy requires an accepted reader
  review that leaves the grade at A or A+, which has happened twice in the
  record (both DAC, 1 and 2 October). What the reader would have done with
  these 99 tickets is unknown.
- **A survivorship-free universe.** The archive's membership is the later one;
  names that left the market are absent from both the breadth and the
  candidates, and which way that biases the regime and the outcomes is not
  measured.
- **The original information set.** The bars are a later retrieval, and 263
  names stay partial.
- **Fills inside the day, or costs.** Fills, exits and R are the daily-bar model
  of the published scorecard: a fill only at the next open inside the ticket,
  uncertain days scored nowhere, no fee, spread or slippage.
- **Reproduction here.** The summaries were produced on the owner's machine and
  are recorded as received.
- **An edge.** Nothing above is an edge claim, and nothing changes a rule.

## Beside the signal study

The two readings cover different populations: the backtest takes the
top-ranked tickets under the slot cap and the regime, from February; the signal
study tickets every burst row of every night since 11 September without a slot.
Where they overlap in time (11 to 25 September) and in regime (RED) they were
not compared row by row: the backtest's 25 settled RED-night counterfactual
tickets summed +1.14R, the signal study's 267 averaged −0.19R. The backtest
adds the only numbers from nights that were not RED: YELLOW nights at half
size, mean +0.08R and median −0.09R over 44 settled.

## Next

The archive is fixed and no further acquisition is authorized, so this reading
is complete as it stands; what grows is the live scorecard and the signal
study's confirmatory phase. The per-row files on the owner's machine could give
the backtest's own dispersion and interval if that is wanted. The A/A+ split
in point 4 is recorded; it changes no rule.
