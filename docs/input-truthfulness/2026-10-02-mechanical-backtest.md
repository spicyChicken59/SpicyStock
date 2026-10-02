# The mechanical backtest: the run's own stages over the run-6 archive

**What this is.** `tools/historical_backtest.py` replays SpicyStock's nightly
decision over the bars a recovered historical acquisition package holds, one
session at a time, by calling the functions the pipeline calls. It exists
because the one real year of full-market daily bars the project owns -- run 6's
package, 288 sessions of 4,780 names, acquired on 1 October and recovered on the
owner's computer -- was read for two sessions' breadth and nothing else. Every
published night since 11 September has been RED, so no real ticket has ever
existed and the public scorecard has never had a plan to settle. This tool is the
first way to see what the rules would have decided, and what those decisions
would have done, on real bars.

**What it is not.** It is not proof of an edge, and it cannot become one:

| Limit | What it means for a reading |
| --- | --- |
| The reader is NOT RUN | The chart reader only lowers a mechanical grade, so the mechanical grade is the CEILING of what the live run could have admitted. Every ticket here is one the reader could still have refused; none the reader could have added is missing. |
| The universe is the archive's | The package carries the names the acquisition was frozen over, a September 2026 directory. A name that left the market earlier in the year is absent. Survivorship flatters the regime (its decliners are under-counted) and the candidates. Neither bias is measured, only named. |
| A later retrieval | The bars are the provider's September 2026 view, not what any night saw; 263 names per session were partial in the reconciliation and stay partial here. |
| A daily-bar model | A fill is booked only at the next open inside the ticket; a day the bar cannot read is `uncertain` and scored nowhere; no fee, spread or slippage. This is the published scorecard's own model, unchanged. |
| The counterfactual block | A second block removes the regime gate to show what the gate refused. It is labelled, and it is not a policy. |
| Counts, not rates | The summary reads no rate under the scorecard's own minimum (`record.SCORECARD_MIN_PLANS`), and twenty settled plans do not establish an edge. |

## What it replays, and with what

| Stage | The function the tool calls | What the live run does |
| --- | --- | --- |
| The frames a night would have fetched | `as_of()`: the `pipeline.LOOKBACK_DAYS` sessions before the session and the session itself, nothing later | `fetch_universe()` over the same lookback |
| Session rules | `market_data.apply_session_rules()` | the same |
| Price policy | `universe.session_eligible()`, the archive's `price_exempt` seeds | the same |
| Market Monitor and regime | `breadth.snapshot()` over the names that printed | the same |
| Scans, checklist, rank | `pipeline.scan_frames()`, `pipeline.rank()` | the same, then the reader |
| Reader | NOT RUN; `grade = grade_mechanical` | `read_charts_and_grade()`, down-only |
| Plans, slots, budget | `pipeline._make_plans(require_reader=False)` with `pipeline.slots_held(record.open_plans())` of the sessions before | `make_plans()` with the same slot count |
| The record | `pipeline.pick_of()`, `record.append()` | the same |
| Fills, exits, R | `record.scorecard_rows(window_sessions=<the archive's length>)`, `record.summarize_scorecard()` | the same two functions over their sixty-session window |

The one change to `src/` is the `window_sessions` keyword on
`record.scorecard_rows()`, default unchanged, so the one walk reads every plan
the replay made rather than the last sixty sessions'. `tests/test_record.py`'s
`test_the_scorecard_window_can_fail` still passes: the default is read at call
time, so the published window is still the module's constant.

## The lookback and its equivalence check

Every evaluated session needs `pipeline.LOOKBACK_DAYS` sessions of history
before it, as a live frame carries. Over a 288-session archive that leaves 28
evaluable sessions (17 August to 25 September 2026), a stretch the published
record already knows was RED. `--lookback 130` reaches 158 sessions back to
February 2026. A shortened lookback is admitted only with its check: on every
evaluated session that also carries the full lookback, both are measured and
compared -- the regime and its ratios, every candidate's mechanical grade, score
and vetoes, every plan's trigger, limit, stop, shares and action -- and a single
difference is a FAIL printed first and exit code 2. On the synthetic archive the
check passes at 130 and fails at 20, where the checklist's windows run out of
history and the grades move, so the check can fail for the reason it names.

## How the owner runs it

The helper beside this report,
[`run-backtest.ps1`](2026-10-02-mechanical-backtest-evidence/run-backtest.ps1),
takes the repository path, finds the recovered folder `open-run6.ps1` wrote,
installs the same `tools/requirements-historical.txt` that recovery used, and runs
two passes into two private folders: the exact lookback, then `--lookback 130`
with its check. Each pass writes `backtest.json` (every row, with prices: keep it
private) and `summary.txt` (counts, verdicts and R only; no price, no ticker:
paste it). One session cost about thirty seconds in this sandbox at the
archive's scale on a burst-heavy synthetic market (4,779 names, 683 bursts), so
the exact pass is minutes and the long pass an hour or two. Nothing is fetched,
nothing is sent, and the key is not read.

## How to read `summary.txt`

- **regimes** -- how many evaluated sessions were GREEN, YELLOW and RED, and the
  10-session ratio's range. If the ratio never reaches `breadth.RED_RATIO_10D`,
  the production block cannot hold a ticket, and that is itself the finding.
- **PRODUCTION POLICY** -- tickets by the night's regime, every plan's bucket
  (settled, open, pending, uncertain by reason, not filled, unmeasured,
  unreadable, unscored), then wins, losses, breakeven, sum R, and the rates the
  scorecard reads only at its minimum. The partitions by grade and by regime use
  the same denominators.
- **COUNTERFACTUAL** -- the same market with the regime gate removed and the
  full size multiplier. Its `by regime red` line is what the gate refused.
- **lookback equivalence** -- PASS, FAIL or not required. A FAIL means the long
  pass is not the run's own answer; the exact pass still is.

## Verification here

`tests/test_historical_backtest.py` builds a synthetic archive the way a real
one is built -- a frozen manifest the acquisition's own `validate_manifest()`
accepts, the acquisition ledger and raw pages the real `Acquisition` wrote
through a synthetic transport -- and reads it back through `cached_pages()`,
`normalize_pages()` and `frames_for_replay()`, the owner's recovery path. The
market is ten names over 289 sessions: the field guide's textbook A+ bar four
times (one on a RED night, one too far back for the exact lookback), four flat
names, three of which break down on the RED night, a $2.50 name the price policy
excludes, and SPY. Every expected R is computed by hand from the scripted bars
(+1.68 and +1.10 settled under production, -0.81 for the ticket the gate
refused, one `not_filled` for an open over the limit). Fourteen tests; seven
in-memory mutants all killed with the unmutated controls green: the production
block ignoring the gate, `as_of()` leaking later bars (two checks), picks never
recorded, slots never held, the equivalence fingerprint ignoring grades, and the
outcomes read only over the published window. The last one SURVIVED its first
pass -- every pick sat inside the sixty-session window, an incidental fact of the
fixture -- and was killed by the fourth burst, 138 sessions before the archive's
end. Nothing here is a real-data result: the owner's run is NOT RUN in this
repository, and its summary will be recorded when pasted.
