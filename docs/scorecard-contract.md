# Published model-plan scorecard · reporting contract 2

Effective with the September 16, 2026 product campaign. This is a SpicyStock
**IMPLEMENTATION** reporting contract, not a new Bonde rule or a profitability
finding. `src/record.py` is the calculation authority; `record.replay()` and
`plan.follow()` remain the only fill/exit engine. Personal selection has no role.

## Population and coverage

Every valid retained pick in `docs/picks.json` whose signal session is within
the prior 60 XNYS sessions or the current publication is included. Both published
Burst tickets and eligible Anticipation tickets are counted; non-ticket setups,
slot cuts, dry-run proposals and local saves/selections are excluded. Existing
append semantics replace a rerun of the same kind/ticker/session. This counts
retained plans, not every superseded publication revision. The file retains up
to 260 picks, so it can truncate the window in a busy period. Capacity and load
problems are disclosed; invalid picks cannot be scored and are named as a
coverage limitation. Outside-window retained picks have an explicit count.

The following disjoint buckets sum to **published plans**:

| Bucket | Meaning | Enters return/rate denominator? |
| --- | --- | --- |
| Resolved (`settled`) | Model walk ended and sales reconcile to a defined R | Yes |
| Open | Established fill, unfinished walk, bars current through the evaluation session | No |
| Pending | Current-session publication awaiting its first entry session | No |
| Uncertain | Daily bars cannot establish trigger timing or fill/stop sequence | No |
| Not filled | Entry-day order could not fill, including expiry without reaching trigger | No |
| Unmeasured | Missing bars or a stale unfinished observation | No |
| Unreadable | Inconsistent or noncontiguous required bars | No |
| Unscored | Ended/expired walk without fully reconciled sales | No |

`filled` is a separate overlapping diagnostic count, never a denominator.
Missing evidence is not delisting, a no-fill, zero R or proof that a position
remains open. Only bars through the five-session model horizon are supplied;
gaps beyond it are irrelevant. Known earlier terminal results remain usable
without later bars; ambiguous or malformed required observations stay unscored.

## Model assumptions and metrics

The existing fill model books only the next session's open inside the recorded
trigger/limit zone. Other potential fills remain UNCERTAIN with their original
reason. Stop-market gaps use the open; otherwise the stop takes precedence over
same-bar profit-taking. Whole-share partial sales, stop raises and dated exits
are exactly `plan.follow()`'s existing rules. All shares must reconcile before
R exists. There is no second fill inference in the browser or analysis tool.

R is the whole-share-weighted result divided by initial model risk from the
established open fill to the published protective stop. Existing two-decimal R
rounding is retained: positive = win, negative = loss, zero = breakeven. Those
three counts sum to resolved. Win rate = wins / resolved, including breakeven;
mean and median R use exactly that denominator. Rates and mean/median are hidden
below 20 resolved plans. This display threshold is not statistical validation.

SPY is the average percent-price move from each resolved plan's entry-day open
to its final sale day's close, using only matched pairs. Its pair count is
separate; it is neither an investable portfolio benchmark nor an R comparison.
There is no equity curve, compounding, execution P&L, fee/spread/tax model or
claim of profitability. No optimization or favorable subgroup selection occurs.

## Prices, regime and versions

Publication records the replay input basis (currently Alpaca split-adjusted daily
bars/feed) and current replay rules digest. Frozen original levels are not
automatically rebased after subsequent splits. Missing original basis or
corporate-action reconciliation limits interpretation; old levels plus a newly
adjusted bar series do not establish brokerage returns.

Original entry regime is retained on each pick. The existing scorecard replay
uses green for instruction wording; red-regime clauses change advice text, not
the numerical walk. This is not a simulated day-by-day discretionary regime exit.
Original rules version and discovery route require the exact original publication.
They must never be inferred from today's rules or from a ticker's later signal.

`contract_version: 2` versions accounting and presentation. Trading constants,
`rules_version`, discovery v1, provenance v1 and pick projections are unchanged.
No historical grade, receipt, pick or September 11/14 publication is rewritten.
Older published scorecards retain their recorded values and display a warning
that missing-observation accounting was incomplete.

## Offline audit

```sh
python tools/scorecard_analysis.py --picks saved-picks.json --frames frames.json --session 2026-09-16 --publication original-data.json
```

`frames.json` maps ticker to a provenance v1 normalized frame object. Inputs must
already be local; no provider/model transport runs. Repeat `--publication` for
other originals. `tools/verify_provenance.py` can reconstruct retained recovery
archives via its `archived()` helper if the original data file is unavailable.

The tool emits the aggregate, one audit row per included plan, and complete
partitions by rules version, burst/dollar/both (Anticipation separately), grade,
entry regime, kind and reader source. Every partition retains unknowns and uses
the same summary/threshold. Exact evidence/context/plan/pick receipts must match
an integrity-verified publication. Tampered publications fail; legacy or
incompatible verification remains unknown. This metadata check is explicitly
integrity-only, not a fresh source-frame replay. Supplied observation bars and
their price-basis compatibility require their own provenance; they are never
silently described as the original source evidence.
