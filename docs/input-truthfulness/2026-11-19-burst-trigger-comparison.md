# The burst trigger rule, read both ways (19 November 2026)

A reading, not a check and not a rule. On 19 November 2026 the owner decided
that a burst ticket's buy stop is the close plus the anticipation ticket's own
cushion, the larger of $0.02 and 0.1% of the close (`plan.burst_trigger()`,
the `close_plus_cushion` rule a record archives as `plan.burst_trigger_rule`).
Every record before it was made with the buy stop AT the close (`close`).
This reading asks what the change does to the tickets the mechanics write and
to how they come out on daily bars.

`tools/burst_trigger_comparison.py --ref b1192f3a` wrote
`2026-11-19-burst-trigger-comparison/comparison.json`. It runs the frozen
signal-outcome study's own walk (`tools/signal_outcomes.py`) twice over one
population, once per rule, and changes nothing else.

- **The study's own steps.** Each publication is held to its blob, the newest
  publication's bar wins, the signal's own close must reproduce, and every
  ticket is walked with `record.replay()` over the next five sessions.
- **The population.** The 7 November extension's 47 publications, plus every
  later publication through `b1192f3a`: 55 publications, the first of each of
  49 sessions ticketed (11 September to 18 November 2026).
- **What is removed.** Nothing is gated: there is no market gate, no slot cap
  and no chart reader, as in the study.

`tests/test_burst_trigger_comparison.py` holds every figure below to the file.

## What moved

| | `close` | `close_plus_cushion` |
|---|---|---|
| tickets written (every stratum) | 17,887 | 17,704 |
| withheld by the 4% stop rule | 1,949 | 2,138 |
| first day opened under the buy stop | 6,491 | 7,483 |
| first day opened at or over the buy stop | 9,191 of 17,249 (53.3%) | 8,013 of 17,075 (46.9%) |
| admitted (A+/A, no veto): settled | 1,090 | 927 |
| admitted: mean R / median R | −0.151 / −0.39 | −0.16 / −0.39 |
| admitted: 95% night-bootstrap interval of the mean of night means | [−0.217, 0.062] | [−0.236, 0.054] |
| admitted: uncertain on daily bars | 1,063 | 1,141 |
| admitted: not filled | 431 | 489 |

The cushion does what it is for: an open just over the close is now under
the buy stop, so a resting order is above the market before the open and can
be entered as written there. It costs tickets in two places:

- **The stop rule.** The 4% line is judged at a trigger a few cents higher,
  so 189 more setups have no limit above their buy stop that keeps a stop
  inside the line, and their tickets are withheld.
- **Daily bars.** A first day that opens under the buy stop and reaches it
  later can only be placed by its one-minute bars. The records retain those
  only for published tickets, so more of these counterfactual tickets read
  uncertain.

## What it does not show

- **No sign either way.** The admitted stratum's interval includes zero under
  both rules, and the two means differ by less than either interval's width.
  This is not an edge claim for either rule.
- **Not the live policy.** Every ticket here is counterfactual: no reader,
  no market gate and no slot cap. Most of these nights were RED.
- **Not intraday.** Fills are the daily-bar model's. Where the minute bars
  would place a first day the daily bar cannot, this reading leaves it
  uncertain.
- **Not the private archive.** The owner's backtest
  (`tools/historical_backtest.py`, now with `--burst-trigger-rule`) reads the
  run-6 acquisition archive on his own computer. That run is his:
  `--burst-trigger-rule close` and `--burst-trigger-rule close_plus_cushion`
  over the same `--lookback`.
