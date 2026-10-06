# The mechanical backtest's first real result: 158 sessions of the run-6 archive

**What this is.** On 6 October 2026 the owner ran `tools/historical_backtest.py`
over the run-6 archive recovered on his own machine -- 288 sessions of 4,780
names acquired on 1 October, the only real full-market bars this project has --
through the helper `run-backtest.ps1` described in the
[backtest report](2026-10-02-mechanical-backtest.md), and pasted the two
price-free `summary.txt` files it names. They are recorded under
[`2026-10-06-backtest-results-evidence/`](2026-10-06-backtest-results-evidence/):
`lookback-260-summary.txt` exactly as pasted, including the tool's six
per-session progress lines that preceded it and the helper's "3/4" line that
followed; `lookback-130-summary.txt` with its two em dashes restored, which the
Windows clipboard had delivered as `â€”`. Nothing else in either file was
changed. The per-row `backtest.json` files carry prices and stay on the owner's
machine. Nothing here can be re-run in this repository, where the archive does
not exist; the numbers are recorded as received.

**Both passes ran clean.** The exact-lookback pass evaluated 28 sessions in
511.7 seconds. The 130-session pass evaluated 158 sessions in 3,813.5 seconds,
and its equivalence check is **PASS**: on all 28 sessions both lookbacks can
read, the regime, every candidate's grade, score and vetoes, and every plan's
prices and shares were identical, 0 differences. Both passes report the rules
digest `17da26751760`, so one set of numbers made them. The exact pass's regime
split -- 15 YELLOW then 13 RED, the turn on 9 September -- is the split the
published records' own breadth history implied, which the backtest report had
noted before the run.

## The archive and what was evaluated

| | |
| --- | --- |
| Archive | 4,781 symbols with bars (the 4,780 intended stocks and SPY), 288 sessions, 5 Aug 2025 to 25 Sep 2026; 4,518 complete, 263 partial |
| Exact lookback | 28 sessions, 18 Aug to 25 Sep 2026: 15 YELLOW, 13 RED; 10-session ratio 0.76 / 1.06 / 1.56 (min / median / max) |
| 130-session lookback | 158 sessions, 10 Feb to 25 Sep 2026: 100 YELLOW, 58 RED, **0 GREEN**; ratio 0.55 / 1.13 / 3.26 |
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
| SPY over the same windows | not read | +0.37% mean over 44 pairs |

## The counterfactual, regime gate removed (not a policy)

Without the gate every night is treated as GREEN: A and A+ admitted at full
size into four slots. Its ticket set therefore differs from the production set
even on YELLOW nights, because A-grade names compete for the slots.

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
| SPY over the same windows | not read | +0.31% mean over 69 pairs |

## Reading

1. **The first readable rate the strategy has had.** Forty-four settled tickets
   clear the scorecard's own minimum of twenty. The mechanical policy at half
   size on YELLOW nights, over seven and a half months of real bars: a 36% win
   rate, +0.08R per settled ticket, a median of −0.09R, net +3.72R. At the
   configured account's half-size risk of $25 a ticket that is about $93 on
   $10,000 before any cost.
2. **It is within noise and within costs of zero.** Forty-four outcomes at a
   dispersion near one R put the standard error of the mean on the order of
   0.15R; the exact interval needs the per-row file, which this repository does
   not have. The signal study measured its tickets' costs at about 0.04R per
   settled ticket at 5 basis points a side and 0.165R at 20; the same mechanics
   carried here take the mean to roughly +0.04 and −0.08. SPY's mean move over
   the same holding windows was +0.37%, and 0.08R at a stop close to 4% under
   the limit is about +0.3%: the tickets did about what the market did over the
   same days.
3. **The gate's RED-night refusals went about nowhere.** Twenty-five settled,
   7 wins, 18 losses, +1.14R. The signal study's 267 admitted RED-night tickets
   without a slot cap averaged −0.19R. Neither population paid on RED nights;
   the top-ranked four a night did no better than break even.
4. **The A-grade tickets the YELLOW rule excludes did better than the A+ it
   admits**, +10.22R over 23 settled against +7.18R over 46. That is a question
   for the method, to be answered prospectively. It is not a tuning input: this
   file's standing OMIT of rule changes on these numbers holds, and 23 settled
   is one trade away from any conclusion.
5. **Forty-two of 99 production tickets are unknowable from daily bars**,
   33 of them because the trigger was crossed after the open. The published
   scorecard will carry the same share; only intraday data would resolve it.
6. **GREEN did not occur in 158 sessions.** The policy's full-size state, and
   its admission of A grades, has never been exercised on real bars. The
   10-session ratio reached 3.26, so on the days it cleared 2.0 another yellow
   rule was still firing, because GREEN requires none.

## What it does not establish

- **The reader's judgement.** The live policy requires an accepted reader
  review, which has happened twice in the record. The live system would have
  written a handful of these 99 tickets at most.
- **A survivorship-free universe.** The archive's membership is the later one;
  names that left the market are absent from both the breadth and the
  candidates, and losers leave more often than winners.
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
Where they overlap, on RED nights, they agree. The backtest adds the only
evidence from nights that were not RED: YELLOW nights at half size, about break
even.

## Next

The archive is fixed and no further acquisition is authorized, so this reading
is complete as it stands; what grows is the live scorecard and the signal
study's confirmatory phase. The per-row files on the owner's machine could give
the exact interval around +0.08R if that is wanted. The A-grade question in
point 4 goes to Astra as a method question.
