# Whole-share feasibility over every retained publication — 11 October 2026

A reading, not a check and not a rule. `tools/whole_share_feasibility.py
--history --ref origin/main --limit 64` sized every reaction candidate every
retained publication archived through `plan.burst_plan` -- the cascade the
evening run writes its tickets with, reached through
`entry_limit_study.current_plan` -- at two accounts, in this checkout, with no
provider, model or network call:

- at the account each record archived
  ([history-archived.md](2026-10-11-whole-share-feasibility-evidence/history-archived.md),
  [history-archived.json](2026-10-11-whole-share-feasibility-evidence/history-archived.json)):
  the $10,000 / 0.5% model account of the 22 publications before the
  $2,000 release, and the $2,000 / 0.5% cash-account reference of the four
  since (8 and 9 October);
- at Mo's $2,000 / 0.5% reference for every publication
  ([history-account-2000.md](2026-10-11-whole-share-feasibility-evidence/history-account-2000.md),
  [history-account-2000.json](2026-10-11-whole-share-feasibility-evidence/history-account-2000.json)),
  `--equity 2000 --risk-pct 0.5`, which the tool labels a counterfactual
  because it is not what those records were sized at.

Each publication is read under three regimes: its own (`tonight`), YELLOW and
GREEN, each with the grade band that regime admits -- read off the record's
archived `pipeline.trade_grades` and `pipeline.yellow_grades`, the same rule the
planner and the funnel use -- and the size multiplier it applies. "In band" is
the funnel's potentially usable: a mechanical A-band grade and no veto. The
reader is not consulted: a candidate's final grade can only be lower than its
mechanical one, so the in-band count is an upper bound on what any review could
have admitted. Nothing below is a ticket, a fill, a return or an edge.

## What was read

Sixty-four commits changed `docs/data.json`; thirty-eight are the first build's
records or committed fixtures and are named as skipped. The other **26
publications cover 21 sessions, 11 September to 9 October 2026**: 21 RED and
5 YELLOW, GREEN never published. All 11,513 archived reaction candidates had a
usable bar; none was set aside.

## The one-share ceilings

A ticket's shares are `floor(equity x risk% x multiplier / (limit - stop))`,
no more than the position cap buys (`plan.size`). Every stop-constrained ticket
-- `limit_basis` was `stop_line` for 528 of 528 on the first real-data night --
puts its stop just inside his 4% line, so the stop-risk rule halves the risk
budget. One whole share therefore fits only under a limit price of:

| account | risk a trade | YELLOW (half size), stop on the line | GREEN (full size), stop on the line | GREEN, a 2% stop (no halving) |
|---|---:|---:|---:|---:|
| $10,000 / 0.5% | $50 | $312.50 | $625.00 | $2,500 (the $2,500 position cap binds first) |
| $2,000 / 0.5% | $10 | **$62.50** | **$125.00** | $500 (the $500 position cap) |

`tests/test_whole_share_feasibility.py` holds these to `plan.size` at the
boundary: at the ceiling one share fits, a dollar over it none does.

## What the reading says

| | at the archived accounts | at $2,000 for every night |
|---|---:|---:|
| candidates sized | 11,513 | 11,513 |
| tonight: in band / past the stop rule / a whole share | 8 / 8 / **5** | 8 / 8 / **2** |
| YELLOW (A+): in band / stop rule / whole share | 40 / 40 / 35 | 40 / 40 / **5** |
| GREEN (A+ and A): in band / stop rule / whole share | 1,666 / 1,598 / 1,409 | 1,666 / 1,598 / **846** |
| anticipation setups listed / eligible / a whole share (as recorded) | 128 / 82 / 3 | 128 / 82 / 3 |

Read it as:

- **The stop rule is not the bottleneck; the price is.** Under GREEN, 1,598 of
  the 1,666 in-band names (96%) pass the stop rule at every account. At the
  archived $10,000, 1,409 of those (88%) size to a whole share; at $2,000, 846
  (53%). Under YELLOW at $2,000 -- the only regime the record has ever
  published a ticket under -- 5 of 40 (12.5%) do: a half-size $5 risk budget
  halved again by the stop rule buys one share only under $62.50.
- **Tonight, as published:** the 8 potentially usable candidates (the four
  mechanical A+ in each of the two 8 October publications) all pass the stop
  rule; at the $10,000 account the first publication archived all 4 size to a
  share, at the $2,000 account the corrected publication archived 1 of 4 does.
  None reached a plan: the reader refused one and lowered three below the band
  ([the funnel](2026-10-11-candidate-funnel.md)). The three 9 October
  publications carry no mechanical A+, so their YELLOW band is empty at any
  account.
- **By mechanical grade at $2,000 under GREEN** (candidates / stop rule /
  whole share): A+ 40 / 40 / 13, A 1,626 / 1,558 / 833, B 2,753 / 2,612 /
  1,329, C 1,866 / 1,725 / 953, skip 5,228 / 4,866 / 2,526. The price
  ceiling cuts every grade alike; it is a property of the account, not of
  the setup.
- **Anticipation**, read off the recorded plans only: 82 of 128 listed setups
  were eligible and 3 carried a whole share at the account and regime they
  were recorded under -- MG and SN on 8 October at $10,000 and ZIM on
  9 October at $2,000, each superseded by the corrected publication that
  followed. The recorded plans are not re-sized here.

## What this does not establish

Whether a candidate the account could size would have made money (the
[signal-outcome study](2026-10-02-signal-outcomes.md) walks that question over
RED nights and finds every stratum lost); whether the reader would have
admitted it (every retained accepted review of a mechanical A-band name lowered
it); or what a GREEN night looks like, which no publication has shown. A
whole-share count is an accounting of the sizing arithmetic at a price, and the
tool prints the arithmetic beside the count. Nothing here changes a threshold,
a rule, a record or the account.
