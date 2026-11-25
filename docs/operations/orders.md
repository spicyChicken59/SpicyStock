# The execution handoff

SpicyStock decides nothing and places no order. A separate execution agent
decides and places the owner's trades at Fidelity. These three files are
what it reads:

| file | written by | when |
|---|---|---|
| `docs/orders.json` | the evening run (`src/orders.py`, `pipeline.publish_orders()`) | after the brief, each published night |
| `docs/positions-template.json` | the evening run, beside `orders.json` | the same |
| `docs/orders-morning.json` | the evening run, with `orders.json` (every ticket cancelled, `pending`); then the morning (`python -m tools.publish_morning orders`) | with `orders.json`; again after the morning receipt lands, or after the entry window when no check ran |

Their schema is `docs/operations/orders-schema.json` (JSON Schema, draft
2020-12): `orders.json` is the root, `orders-morning.json` is
`#/$defs/orders_morning`, `positions-template.json` is `#/$defs/positions`.
Any JSON Schema validator reads it; the repository checks its own files with
`src/schema_check.py` (`python -m src.orders check --docs docs`).

## Before reading a ticket

1. **Bind it.** `orders.json`'s `source.data_sha256` is the SHA-256 of the
   `docs/data.json` it was derived from; `orders-morning.json`'s
   `orders_sha256` is the SHA-256 of that exact `orders.json`. A file that
   does not match the one beside it belongs to another night.
2. **Hold the hashes.** Every file, and every ticket of `orders.json`, carries
   `content_sha256`: the SHA-256 of the bytes Python's
   `json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`
   writes for it without that field, UTF-8 encoded. A whole-number float is
   written as Python writes it (`25.0`, not `25`), so a serializer that drops
   the `.0`, as JavaScript's does, gives other bytes: recompute with that call,
   or run `python -m src.orders check --docs <dir>`. A morning ticket carries
   `ticket_sha256`, the hash of the `orders.json` ticket it re-reads. A file or
   ticket whose hash does not hold was changed after it was written.
3. **Read `trade_allowed` before any ticket.** A ticket's `status` is its own
   checks only; on a night whose checks fail, a ticket can still read `go`
   while `trade_allowed` is false, and nothing on that night is to be entered.
   The checker also refuses a file whose `trade_allowed`, `reasons`, ticket
   statuses, summary or mode are not what its own checks give.
4. **Read the mode.** `mode` is `paper` and `live_ready.value` is false until
   the record's go-live gate holds ([`go-live.md`](go-live.md): the owner's
   Fidelity protocol record and ten on-time sessions, and nothing about
   results); then `mode` is `live` and `live_ready.reasons` is empty. A paper ticket is a
   rehearsal: it is never an order to place. `live_ready.reasons` names each
   condition not met, in the words `go-live.md` lists; `live` says the
   owner's conditions for trusting the file hold, and `trade_allowed` and
   each ticket's `status` still decide the night.
5. **Read the version.** The schema names one `version`. A merge that moves
   it leaves the files on `main` as the earlier code wrote them until the next
   evening rewrites them; such a file is still bound to its record, but it is
   not this schema's, no ticket of it is read, and nothing is entered from it:
   the morning writes a go/cancel file bound to it that lists no ticket and
   cancels every one (`cancel_all_reason` `orders_earlier_version`). Wait for
   the evening's file of the schema's version.
6. **Read `orders-morning.json` before any entry, and cancel everything
   without it.** `orders.json` states the rule in `morning_rule`: a ticket is
   entered only while `orders-morning.json` is bound to that exact
   `orders.json` (`orders_sha256`), its `status` is `checked`, the ticket's
   `decision` there is `go`, and the clock is before the ticket's
   `valid_until`. In every other case every ticket is cancelled: the file is
   missing, cannot be read, does not hold its hash, is bound to other bytes,
   says `pending` or `no_check`, or does not list the ticket. `cancel_all`
   says the same in one field: it is true unless the status is `checked`.
   The evening writes the file with `orders.json`, so a missing one is a
   fault and never a go.

## What `orders.json` says

- **`tickets`**: every ticket the record published, the same rows the morning
  receipt quotes (`morning.admitted_rows()`): the record's own evidence gate,
  never a ticket made here. Each carries:
  - `entry`: a day buy stop-limit, `stop_price` (the trigger) and
    `limit_price`, valid from `valid_from` to `valid_until` (the record's
    entry window, `run.timing`), to cancel if unfilled at
    `cancel_if_unfilled_at`; for a burst ticket the skip lines and the
    trigger rule the record archived;
  - `protective_stop`: the GTC sell stop the OTO attaches, with Fidelity's
    rule that an OTO releases it only on a full fill;
  - `order_as_written`: the record's own order, field for field;
  - `exit_plan`: the hold as rules, in the order `plan.follow()` applies them
    within a session (the open, then the low against the stop, then the high,
    then the close). Each rule names its days and dates, its condition
    (`when`) and its action (`then`); percentage levels are of the average
    fill. Each carries its price for a fill at the trigger only: the model's
    own walk (`record.replay()`) prices them from the fill it books, the open
    when the session opens inside the ticket, the trigger when it crosses
    later. `sessions` gives each hold day's scheduled close (`close_at`, and
    `early_close` on a shortened session), where a rule says "at the close";
  - `risk`: one R per share is the limit less the stop (the highest fill the
    ticket permits, the price the plan is sized at), `risk_usd` is shares
    times that, beside the night's risk budget and the position cap;
  - `checks` and `status`: `go`; `human_review` when an SEC filing flag
    names the ticket (`run.sec_flags`, or a material 8-K item the earnings
    warning read), when SEC could not be read for it, when the second-source
    cross-check could not be made for it, when the record does not show the
    ticket's own frame through the session and the session before it
    (`inputs_unknown`), or when a burst's chart review was accepted without
    its chart (`reader_chart_missing`); `blocked` when the event registry
    refuses it, its iex signal-day bar differs from the record's past the
    archived tolerance, the record names its stock among the stocks without
    a usable session frame or among the frames held under an open model plan
    (`inputs_exception`), a burst has no accepted chart review
    (`reader_not_accepted`), or the position cap or the risk budget is
    exceeded. Every reason is listed.

    The `inputs` check passes only on the row's own facts: its sealed source
    frame was evaluated at the run's session with the session before it, and
    the last two bars the row archives are dated those two sessions and are
    readable. The record's lists of stocks without usable bars are samples, so
    a stock's absence from one is never read as evidence; the check's `detail`
    names any list that was sampled short. A setting-up ticket's `reader`
    check passes as not applicable: it is measured and never chart-read.
- **`night_checks`**: the light; the market's inputs (below); whether the
  record was
  published in time (the run's own clock, `run.published_at`, before the
  entry window's `prepare_by` instant and before the applicable session
  opened; the run's clock is set near its start, so this measures when the
  run began, not when its commit landed), whether the second-source
  cross-check ran (`run.cross_check`; each ticket carries its own result),
  and the account's slots and commitments. Each is `pass`, `fail` or
  `not_evaluated`, with a reason code.

  `market_inputs` is the one data check that stops a whole night, because the
  light is computed over every stock that printed and each ticket was ranked
  and given its slot among all of them. It reads the record's own input
  ledger and never the run's status word: it fails
  (`market_inputs_incomplete`) when more intended stocks were without usable
  bars than the limit the record archived for its stale tolerance, when the
  selection was cut at its capacity, or when the stock directory failed and
  the seed list stood in; it is `not_evaluated` (`market_inputs_unknown`) when
  the ledger, the archived limit, the run status or a problem word is not one
  this file reads. A run that is `degraded` for any other cause (a refused or
  unreadable chart review, a chart that did not render, a mail that failed, a
  cached directory, a late bar found by the follow-up) passes this check, and
  that cause is read on the ticket it concerns or not at all.
  `source.run_status` and `source.run_problems` carry the run's own words for
  reference; no decision reads them.
- **`trade_allowed`**: true only when every night check passes and at least
  one ticket is `go`. **`reasons`** lists every code that kept it false, for
  the night and for each ticket.

Every reason code and its meaning is `src/orders.REASONS`.

## What `orders-morning.json` says

It is always there beside `orders.json`, and its `status` says how it came
to be:

| `status` | written by | `cancel_all` | what it says |
|---|---|---|---|
| `pending` | the evening, with `orders.json` | true | no morning check has run for this record: every ticket `cancel` (`morning_check_pending`) |
| `checked` | a morning run that found a receipt on `main` bound to the record | false | each ticket `go` or `cancel` with its reasons, below |
| `no_check` | a morning run that found no such receipt (`no_morning_check`), or an `orders.json` an earlier version wrote (`orders_earlier_version`) | true | every ticket `cancel` |

A scheduled morning slot that starts after the entry window has ended
collects nothing; it still writes this file as `main`'s own files give it, so
a morning on which no check ran inside the window ends as `no_check`. A
morning on which nothing ran at all leaves the evening's `pending` file,
which cancels every ticket the same way.

Under `checked`, each ticket is re-read against the morning receipt on `main`
(`docs/morning.json`), whichever run published it: `go`, or `cancel` with
every reason that applies (`src/orders.MORNING_REASONS`):

- the night did not allow trading, or `orders.json` did not mark the ticket
  `go` (`news_or_sec_flag` when an SEC flag or an unread SEC filing list held
  it, `ticket_not_go` for any other hold or block);
- the receipt is not bound to this record, or has no row for the ticket;
- the receipt was completed outside the ticket's entry window: at or after its
  cutoff (`valid_until`, carried on each morning ticket), or in a phase that is
  neither before nor inside the window (`outside_entry_window`);
- the halt source reports a halt (`halted`), or could not say: its coverage
  was unavailable or stale, or it named a halt code it does not know
  (`halt_unknown`); no halt seen on a fresh snapshot is the only clear;
- the manual registry refuses the ticket, or the receipt still carries a
  retained corporate-event exclusion that no sourced resolution has cleared
  (`news_or_sec_flag`);
- no recent price was observed (`stale_data`);
- a recent price is over the limit (`gap_above_limit`), at or under the skip
  line or the stop (`gap_below_floor`), or at or over the buy stop, where the
  stop-limit as written cannot be entered (`trigger_crossed`); a price the
  receipt names in a state this file does not know cancels too
  (`price_unknown`). A setting-up ticket has no skip line: under its trigger
  and over its stop it is still waiting, and stays `go`.

It reads no clock of its own: the same `orders.json` and receipt always give
the same bytes. A morning check made before the open usually finds no recent
price, and says so as `stale_data`.

## Applying the rule

`python -m src.orders decide --docs <dir> [--now <instant with its offset>]`
applies step 6 to the files in a directory and prints, for each ticket of
`orders.json`, `go` or `cancel` with the first reason that applies
(`src/orders.entry_decisions()`, `src/orders.ENTRY_REASONS`). It is the rule
written once, for an agent to run or to port; it reads no account and places
nothing, and under `mode` `paper` a `go` is a rehearsal's.

| reason | every ticket? | when |
|---|---|---|
| `morning_file_missing` | yes | there is no `orders-morning.json` in the directory |
| `morning_file_unreadable` | yes | it does not meet its schema, hold its hash or follow from its own fields |
| `morning_file_unbound` | yes | its `orders_sha256` is not this `orders.json`'s |
| `morning_not_checked` | yes | its `status` is `pending` or `no_check` |
| `ticket_not_listed` | this ticket | it does not list the ticket, or lists other bytes of it (`ticket_sha256`) |
| `ticket_cancelled` | this ticket | its `decision` for the ticket is `cancel` |
| `past_valid_until` | this ticket | the clock is at or after the ticket's `valid_until`, or cannot be compared with it |

Binding `orders.json` to `data.json` (step 1) comes first and is not part of
this command: run `python -m src.orders check --docs <dir>` for that.

## The positions template

`positions-template.json` holds one blank position per ticket: the planned
shares and prices, empty broker order ids, fills and exits, and a status. The
execution agent fills a **private** copy with the real orders, fills, exits
and fees. A filled copy holds the owner's real trades and is never committed
to this public repository.

## What it does not do

It reads no account, no quote and no news of its own: the SEC flags name a
filing's form or item and never what it says, and the cross-check compares two
of the provider's own feeds. It does not size from
the owner's cash, does not confirm Fidelity accepts an order, and does not
know whether a fill happened. A ticket here is the record's model plan.
