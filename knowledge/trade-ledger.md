# The trade ledger the outside analyst keeps

Dated 19 November 2026. SpicyStock reads no brokerage account, so it records
no real order, fill, stop or result. The site's Morning desk can keep the
owner's own reports, but only in his browser and only as one summary per
position. Until 19 November 2026 nothing held the real trades in a form that
can be audited against the model. This note defines the ledger that does: the
rows, the columns that bind a row to a SpicyStock publication, how the real
result in R and the model's R are computed and set side by side, the weekly
reconciliation with the site's private backup, and what that backup cannot
hold.

**Where it lives.** With the outside analyst and the owner, outside this
repository. This repository is public: the owner's quantities, prices,
balances, account numbers and fills are never written into it, and the one
worked example below is synthetic. SpicyStock never reads the ledger.

**What it is not.** It is not a SpicyStock record and changes nothing
SpicyStock publishes. The model scorecard counts model plans walked on bars
(`docs/scorecard-contract.md`); the ledger counts what actually happened at
the broker. The two are compared and never added.

## 1. The rules of the ledger

1. One row is one event: a decision, an order, a fill, a stop, an exit or a
   cash reading. The file is JSON Lines, one object a line.
2. A fact about an order or a fill is copied from Fidelity's Activity & Orders
   screen or a trade confirmation, and the row says which (`fact_source`). A
   fact the owner states from memory is recorded as `owner_statement` and is
   not treated as confirmed.
3. A fact about the SpicyStock side is copied from the publication the
   decision was made on, never from a later one, and is bound to it by the
   publication's SHA-256.
4. Rows are appended and never edited. A correction is a new row that names
   the row it corrects (`corrects`).
5. An account is named by a label of the owner's choosing, never by its
   number.
6. Unknown is written as null. A missing fill time, fee or stop is never
   guessed, and a result that needs it is not computed.

## 2. The row

Every row carries:

| column | meaning |
|---|---|
| `event_id` | unique in the file |
| `position_id` | one id for all rows of one position (one name in one account, from the decision to the last exit) |
| `event_type` | `decision`, `order_placed`, `order_rejected`, `order_cancelled`, `order_expired`, `fill`, `stop_placed`, `stop_changed`, `stop_cancelled`, `exit_fill` or `cash_snapshot` |
| `event_at` | when it happened, ISO 8601 with its UTC offset, as Activity & Orders shows it |
| `recorded_at` | when the row was written |
| `account_label` | the owner's label for the account |
| `ticker` | the symbol |
| `fact_source` | `fidelity_activity`, `fidelity_confirmation` or `owner_statement` |
| `evidence_file` | the screenshot or confirmation the row was read from |
| `corrects` | the `event_id` this row corrects, else null |

An order row (`order_placed`, `order_rejected`, `order_cancelled`,
`order_expired`) adds:

| column | meaning |
|---|---|
| `order_ref` | Fidelity's order number, or the analyst's own reference |
| `side` | `buy` or `sell` |
| `order_type` | `stop_limit`, `limit`, `market` or `stop_loss` |
| `conditional` | `none`, `oto` or `oco` |
| `quantity`, `stop_price`, `limit_price`, `time_in_force` | as entered |
| `then_stop_price` | an OTO's secondary stop price, else null |
| `as_written` | true only when the order is the SpicyStock ticket field for field |
| `deviation` | when it is not: `limit_at_limit` (a plain limit at the ticket's limit), `separate_stop` (the stop entered as its own order), `smaller_quantity`, `different_stop`, `late_entry` (after the entry window) or `no_ticket_name` (a name with no SpicyStock ticket); several may apply |
| `entry_state` | the price-state word when the order was entered (`below_stop`, `below_entry_floor`, `below_trigger`, `within_published_band`, `above_limit`, `above_day2_extension`), with the bid, ask and last price read on Fidelity's screen |
| `result` | `accepted`, `rejected`, `cancelled` or `expired` |
| `reject_message` | Fidelity's words, exactly |

A fill row (`fill`) adds `quantity`, `price`, `fees_usd`, `settlement_date`,
`funded_by` (`settled_cash`, `unsettled_proceeds` or `unknown`),
`settled_cash_before` and `available_to_trade_before`.

A stop row (`stop_placed`, `stop_changed`, `stop_cancelled`) adds `old_stop`,
`new_stop`, `quantity` and `rule`, the plan rule the change follows:
`entry_day_low`, `sell_half_8pct`, `trail_after_day3` (the names in
`plan.EXIT_RULES`) or `manual`.

An exit row (`exit_fill`) adds `quantity`, `price`, `fees_usd`, `day_number`
(day 1 is the entry session) and `exit_reason`: `stop`, `sell_half_8pct`,
`abnormal_10pct`, `gap_20pct`, `day3_sell_half`, `day3_no_progress`,
`day5_exit` (the names in `plan.EXIT_RULES`) or `discretionary`.

A `cash_snapshot` row adds `settled_cash` and `available_to_trade` for one
account label.

## 3. The SpicyStock identity columns

They go on the position's `decision` row and bind the trade to one publication
and one row of it. Each is copied from the publication the decision was made
on. The first source named is the canonical record `docs/data.json`; the
daily brief (`docs/brief.json`) carries the same value where a brief field is
named.

| column | read from |
|---|---|
| `ss_canonical_sha256` | the SHA-256 of the bytes of `docs/data.json`; the brief's `identity.canonical.sha256`; also `docs/reader.json` `canonical.sha256` and `docs/morning.json` `publication.data_sha256` |
| `ss_session` | `run.session`; the brief's `identity.measured_session` |
| `ss_applicable_session` | `run.timing.applicable_session`; the brief's `identity.applicable_session` |
| `ss_rules_version` | `app.rules_version`; the brief's `identity.rules_version` |
| `ss_rules_digest_without_membership` | the brief's `rules.digest_without_membership`: the rules digest without the universe membership identity, which moves every night; the digest the weekly review compares |
| `ss_regime` | `breadth.regime.verdict`; the brief's `market.verdict` |
| `ss_stage` | `bursts` or `setting-up`, the page's two lists (the backup's `stage`) |
| `ss_kind` | `burst` or `anticipation`, the plan's `kind` |
| `ss_ticket` | true only when the row's plan carries an order (`plan.order_json`); the brief lists such a row under `tickets` |
| `ss_evidence_id` | a ticket's `plan.evidence_ref.id` (the brief's `order_entry.evidence.evidence_id`); a row without a plan, the row's `evidence.id` |
| `ss_plan_sha256` | `plan.evidence_ref.plan_sha256`, for a ticket |
| `ss_status` | whether the record published a ticket for the row and, if not, why not, in the record's own words; the brief's `model_status` and `why_no_ticket` |
| `ss_rank`, `ss_grade_mechanical`, `ss_grade`, `ss_scan`, `ss_admitted` | a burst row's `rank`, `grade_mechanical`, `grade`, `scan` and `admission.admitted` |
| `ss_trigger`, `ss_limit`, `ss_stop` | a burst plan's `entry_ref`, `limit` and `stop`; an anticipation plan's `trigger`, `limit` and `stop` |
| `ss_skip_below`, `ss_day2_line` | a burst plan's `skip_if_open_below` and `day2_spent_above`; null for an anticipation plan |
| `ss_shares`, `ss_planned_risk_usd` | the plan's `shares` and `risk_usd` (the planned price-to-stop risk at the limit, not a maximum loss) |

A trade on a name the record listed without a ticket still gets its identity
row, with `ss_ticket` false and the deviation `no_ticket_name`. A trade on a
name the record did not list has no SpicyStock identity: the `ss_` columns are
null and the ledger says so.

## 4. Real R, the model's R and their comparison

For a closed position (every share sold) the ledger derives:

| derived | how |
|---|---|
| `shares` | the sum of the fill rows' quantities |
| `avg_entry`, `avg_exit` | share-weighted averages of the fill rows and of the exit rows |
| `gross_usd` | the sum over exit rows of quantity × (price - `avg_entry`) |
| `fees_usd` | every `fees_usd` of the position |
| `net_usd` | `gross_usd` - `fees_usd` |
| `initial_stop` | the first stop that protected the position: an accepted OTO's `then_stop_price`, else the first `stop_placed` row's `new_stop`. If no stop was ever placed, null, and no real R is computed |
| `real_r` | `gross_usd` ÷ (`shares` × (`avg_entry` - `initial_stop`)), to two decimals. This is `record.r_multiple()`'s formula with the real fills in place of the model's: the initial stop is one R on the whole position and every sale is weighted by the shares it sold |
| `real_r_on_plan` | `net_usd` ÷ (`ss_planned_risk_usd` × `shares` ÷ `ss_shares`): the real result against the risk the ticket planned for the shares actually bought. Null without a ticket |
| `beyond_stop_usd` | for exit rows filled under the stop in force: quantity × (that stop - price) |

The model's side is copied, never computed by the analyst:

| derived | read from |
|---|---|
| `model_status`, `model_fill`, `model_exit`, `model_r` | the row of the brief's `model_record.plans` whose `evidence_id` is `ss_evidence_id` (`status`, `entry`, `exit_price`, `r`); or the row of `outcome.rows` in `docs/quality-ledger/v1/<SHA-256 of the newest data.json>.json.gz` whose `evidence_ref.id` is `ss_evidence_id` (`status`, `r`); while the plan is inside its five sessions, also the row of `open_plans` in `docs/data.json` with that `evidence_ref.id` (`status`, `entry_ref`, `exit_price`) |
| `model_source` | which of the three it was read from, and the SHA-256 of that publication |
| `delta_r` | `real_r` - `model_r`, only when both exist |
| `delta_reason` | why they differ: `entry_price`, `exit_price`, `quantity`, `timing`, or `no_model_fill` |

How to compare them:

- The model's R is a walk of the published ticket on bars. A fill at the open
  assumes the order was resting at the broker before the open, and a stop first
  reached inside a session is booked at exactly the stop price
  (`docs/scorecard-contract.md`). A real stop order fills at the next
  available price. So a real stop-out is usually a little worse than the
  model's -1.00R, and `beyond_stop_usd` says by how much.
- When the model books the ticket not filled or uncertain and the owner has a
  real position, `model_r` is null, `delta_r` is null and `delta_reason` is
  `no_model_fill`. The real R still stands.
- A trade on a name with no ticket has no model plan. `model_r` is null. It is
  never guessed.
- `real_r` is gross of fees, as the model's R is. `real_r_on_plan` is net of
  fees.
- A sum of R is not a sum of dollars. Report dollars (`net_usd`) beside any R.
- Real R and model R are compared side by side. They are never added.

**A worked example. Every number in it is synthetic: the stock, the ticket
and the fills are invented.** A burst ticket for XMPL: trigger $50.00, limit
$50.80, stop $48.80, 12 shares, planned risk $24.00. The stock opens at $50.40,
over the trigger, so the order as written cannot be entered; the owner enters
a Day Limit at $50.80 (deviation `limit_at_limit`) and then a separate stop at
$48.80 (deviation `separate_stop`).

| | real, case 1 | real, case 2 | model |
|---|---|---|---|
| entry | 12 at $50.42 | 12 at $50.42 | filled at the open, $50.40 |
| exits | 12 at $48.61, the stop hit on day 1 | 6 at $54.50 on day 2, 6 at $53.10 at the day-5 close | case 1's bar: stopped at $48.80 |
| `gross_usd` | -$21.72 | $40.56 | |
| `fees_usd` | $0.02 | $0.04 | |
| `net_usd` | -$21.74 | $40.52 | |
| `real_r` | -21.72 ÷ (12 × 1.62) = -1.12 | 40.56 ÷ (12 × 1.62) = 2.09 | -1.00 |
| `real_r_on_plan` | -21.74 ÷ 24.00 = -0.91 | 40.52 ÷ 24.00 = 1.69 | |
| `beyond_stop_usd` | 12 × (48.80 - 48.61) = $2.28 | none | |
| `delta_r` | -0.12 (`entry_price`, `exit_price`) | | |

## 5. The weekly reconciliation with the site's private backup

The Morning desk keeps the owner's own reports in his browser (the store
`spicystock:handoff:v1`, version 4). **Download private backup** writes the
stored bytes to `spicystock-private-backup.json`. Once a week:

1. The owner downloads the backup. It stays on his machine and is never
   committed.
2. In a checkout of this repository, on that machine:

   ```sh
   python tools/private_results.py spicystock-private-backup.json --git --json reading.json
   ```

   The tool re-derives each completed result as the page does, traces each
   record to the publication it froze by that publication's SHA-256, searching
   the history of `docs/data.json` (`--git`, the newest 256 commits unless
   `--limit` says otherwise; `--publication FILE` adds a file), and prints the
   model's replay beside it. It makes no network request and writes nothing
   but `reading.json`. Its exit code: 0, every record re-derived and traced;
   1, a record's publication was not found or its frozen plan is not the
   publication's; 2, the file is not a backup the page would accept; 3, a file
   or the history could not be read.
3. Require `trace.status` `traced` on every record of `reading.json`. A
   `mismatch` or a `publication_not_found` is investigated before anything
   else is compared.
4. For each record, the ledger's totals must equal the backup's facts:

   | backup field (`records[].facts`) | ledger |
   |---|---|
   | `submitted_quantity`, `cancelled_quantity` | the buy order rows |
   | `filled_quantity`, `average_price` | the sum and the share-weighted average of the fill rows |
   | `exited_quantity`, `average_exit_price` | the sum and the share-weighted average of the exit rows |
   | `entry_fees`, `exit_fees` | the fees of the fill rows and of the exit rows |
   | `stop_price` | the newest stop row's `new_stop` |
   | `account_label` | the position's `account_label` |
   | `reported.net` (the tool's figure) | `net_usd` |

5. A difference is settled from Fidelity's screen, and the side that was wrong
   is corrected: the ledger by a new row, the site's report by the owner in the
   Morning desk. Neither is changed silently.

How a backup record maps onto the identity columns: a `planned_handoff` record
carries `publication.sha256`, `session` and `rules_version`,
`plan.reference.id` and `plan_sha256`, `plan.ticker` and `stage`, and the
frozen order (`plan.order.quantity`, `stop_price` for the trigger,
`limit_price`, `then.stop_price` for the stop). An `owner_trade` record
carries `source.publication`, `source.ticker` and `stage`, the row as the page
read it (`source.row`: `rank`, `grade`, `score`, `scan`, `admitted`, `status`,
`reason`) and `source.evidence_id`.

## 6. What the backup cannot hold

The ledger is the primary record and the backup is the cross-check, because
the browser store keeps one summary per position:

- no row per order, so no order type, time in force or conditional form, and
  no refused or expired order;
- one cumulative average for the entry and one for the exit, so a two-step
  exit is one blended figure;
- one current stop (`stop_price`), so no stop history and no initial stop for
  an owner trade whose stop was later moved;
- one record per publication and name with one account label, so the same
  name bought in two accounts cannot be held as two positions;
- a result only for a position that is fully exited and reconciled: a partly
  exited position has none;
- dollars and no R: the tool's reading (version 1) prints gross, costs, net
  and the part of a loss past the stop, and the model's replay beside them,
  kept apart;
- nothing a second device or a cleared browser did not keep: the store lives
  in one browser.
