# The execution handoff

SpicyStock decides nothing and places no order. A separate execution agent
decides and places the owner's trades at Fidelity. These three files are
what it reads:

| file | written by | when |
|---|---|---|
| `docs/orders.json` | the evening run (`src/orders.py`, `pipeline.publish_orders()`) | after the brief, each published night |
| `docs/positions-template.json` | the evening run, beside `orders.json` | the same |
| `docs/orders-morning.json` | the morning's persist job (`python -m tools.publish_morning orders`) | after the morning receipt lands |

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
   the record's go-live gate holds ([`go-live.md`](go-live.md)); then `mode`
   is `live` and `live_ready.reasons` is empty. A paper ticket is a
   rehearsal: it is never an order to place. `live_ready.reasons` names each
   condition not met, in the words `go-live.md` lists; `live` says the
   owner's conditions for trusting the file hold, and `trade_allowed` and
   each ticket's `status` still decide the night.
5. **Read the version.** The schema names one `version`. A merge that moves
   it leaves the files on `main` as the earlier code wrote them until the next
   evening rewrites them; such a file is still bound to its record, but it is
   not this schema's, no go/cancel file is derived from it, and nothing is
   entered from it: wait for the evening's file of the schema's version.

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
    warning read), when SEC could not be read for it, or when the
    second-source cross-check could not be made for it; `blocked` when the
    event registry refuses it, its iex signal-day bar differs from the
    record's past the archived tolerance, or the position cap or the risk
    budget is exceeded. Every reason is listed.
- **`night_checks`**: the light, the run's status, whether the record was
  published in time (the run's own clock, `run.published_at`, before the
  entry window's `prepare_by` instant and before the applicable session
  opened; the run's clock is set near its start, so this measures when the
  run began, not when its commit landed), whether the second-source
  cross-check ran (`run.cross_check`; each ticket carries its own result),
  and the account's slots and commitments. Each is `pass`, `fail` or
  `not_evaluated`, with a reason code.
- **`trade_allowed`**: true only when every night check passes and at least
  one ticket is `go`. **`reasons`** lists every code that kept it false, for
  the night and for each ticket.

Every reason code and its meaning is `src/orders.REASONS`.

## What `orders-morning.json` says

Each ticket re-read against the morning receipt on `main`
(`docs/morning.json`): `go`, or `cancel` with every reason that applies
(`src/orders.MORNING_REASONS`):

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
