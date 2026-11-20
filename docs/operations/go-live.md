# The go-live gate

`orders.json` is **paper only** until the record's own gate (`run.go_live`,
`src/go_live.py`) says every condition below holds. Its `mode` is then
`live` and `live_ready.value` is true; until then `mode` is `paper` and
`live_ready.reasons` names each condition not met. The Record view prints
the gate's sentence and each condition, met or not. An execution agent
reads `live_ready` and places nothing live while it is false.

The gate decides nothing about a trade. It says whether the owner's own
conditions for trusting the nightly handoff have been met; every order is
still the owner's.

## The conditions

| condition | met when | read from |
|---|---|---|
| `fidelity_protocol` | the owner has recorded the one-sitting protocol (`knowledge/broker-fidelity-protocol.md`) as passed | `knowledge/go-live/fidelity-protocol.json`, a committed file |
| `on_time_sessions` | the consecutive XNYS sessions ending on the one before tonight's, as many as `go_live.ON_TIME_SESSIONS`, were each published by `go_live.PUBLISH_BY_ET` New York time on the session's own date, started automatically, and checked by a morning check that ran, bound to that publication, generated inside its collection window and by `go_live.MORNING_DUE_CT` Chicago time on the session its plans were for | the record's `run.go_live.ledger`, one row per closed session |
| `settled_forward_plans` | at least `go_live.MIN_SETTLED_FORWARD` model plans in the scorecard's window have settled, each a forward plan picked on or after `run.go_live.strategy.since` | the night's own walk of the pick ledger over that night's bars (the scorecard's rows, which the record summarises and does not carry) |
| `ablation_report` | the pre-registered ablation's results are committed, computed under the committed spec they name | `docs/input-truthfulness/2026-11-19-ablation/ablation.json` |

The protocol record, the ledger and the ablation's results are read from
committed bytes. The settled count is taken each evening from the bars that
run fetched; the record keeps the
count, and its validator holds it to no more than the scorecard's own
settled total.

### Published on time

A session's publication is on time when its run **finished** at or before
`go_live.PUBLISH_BY_ET` New York time on the session's own date. The finish
is the record's start clock (`run.published_at`, set when the run starts)
plus `run.finish_seconds`, which the run stamps at the record's final write,
after the mail. The workflow commits within seconds of that write, and Pages
serves the site later still, so a run that finishes at the line reaches the
site just after it. `run.elapsed_seconds` is not the
finish: it stops where the run block is first composed, before the SEC
reads, the cross-check and the install. A record with no finish stamped
(the record first installed, when its final write was refused) closes as
not shown on time.

### Started automatically

A scheduled run, or the external dispatcher's dispatch with
`only_if_unpublished` ticked (`tools/dispatch_schedule.py`); a hand-run
publish is not. The record archives how its run was started as
`run.trigger` (the workflow's event name and the input); a record without
it closes no counted session.

Two things the gate cannot read, recorded here as limits:

- A person could tick `only_if_unpublished` by hand. The record cannot tell
  that dispatch from the dispatcher's.
- **How the morning check was started is not read at all.** Every morning
  check that lands inside its window today is a dispatch (the dispatcher's,
  the owner's scheduled routine's, or a hand's), because GitHub's own morning
  crons arrive hours late, and the receipt carries no word of which. A
  hand-started morning check inside the window counts.

### Checked by a morning check

The gate reads the one morning receipt on `main` the evening after
(`docs/morning.json`), and counts it when all of these hold:

- it is bound to that publication by the record's SHA-256;
- it ran: its status is one of `go_live.MORNING_RAN` and it says it was no
  rehearsal (`dry_run` false);
- it was generated inside the collection window, on the session the plans
  were for, at or before `go_live.MORNING_DUE_CT` Chicago time.

A later morning run for the same publication replaces the earlier receipt.
So a check that ran on time is no longer counted once a later one lands
after `go_live.MORNING_DUE_CT`, or a hand-started one after the window writes
an `inapplicable` receipt over it: the gate judges the newest receipt, not
the first.

### The ledger

The ledger closes a session the evening after it, from the record that run
replaces. It closes only a real publication: not a rehearsal, and only a
status the evening guard reads as published (`go_live.PUBLISHED_STATUSES`).
When a session was published more than once, the row is the newest
publication's.

A session that was late, hand-run, unchecked or checked late is a row that
is not counted, and it ends the run of counted sessions. A session never
published leaves no row at all, so the run must end on the XNYS session
before tonight's: a ledger whose newest session is older counts nothing,
however long the run before it. The ledger keeps the newest
`go_live.LEDGER_MAX` sessions.

The first row is the last record made before the gate, closed as not
counted because it archives no `run.trigger`. The first session that can
count is the first whose record archives it.

### The standing rules, and forward plans

`run.go_live.strategy` keeps a digest of the record's archived rules, the
session those rules have stood since (`since`), the newest session any
record has published (`newest`) and the sessions whose publication was not
forward (`not_forward`).

**What restarts the count.** The digest covers every archived rule except
those named in `go_live.NON_STRATEGY_RULES`: the night's universe
membership, which moves every night, and the event registry's entries and
its digest, which the CI review check makes the owner revisit on a
calendar. A change to
any other archived rule moves the digest and restarts the count. That
includes rules that decide no ticket: a reporting block's version, the
delivery slots, and this gate's own thresholds. So most merges that archive
or move a rule restart the count. The model account's size and the chart
reader's model are not archived rules, and a change to either does not.

**What counts as forward.** A publication is forward when it is of a session
no older than the newest already published, and was made before the open
its plans are for. A backfill of an older session, and a run made at or
after that open, write their picks after the fact:

- their session is kept in `not_forward`, and no pick dated that session
  counts, whatever the rules did;
- a rule change first seen on such a run stands from the session after the
  newest one published, not from the run's own session.

The retry slot's re-run of the same session the same evening is forward.

**What is counted.** One for each settled ticket, as the scorecard counts
them: a setup ticketed on more than one night is one plan a ticket. A plan that leaves the
scorecard's window leaves the count, so the condition can go from met to
not met.

## Recording the Fidelity protocol

The protocol (`knowledge/broker-fidelity-protocol.md`) is a list of checks
with outcomes, and several outcomes are adverse. Completing the sitting is
not passing it. For this gate the sitting **passed** when all of these were
seen on Fidelity's own screens, on the platform the orders will be placed
from:

1. **U1, U2 and U4:** a One-Triggers-the-Other order with a Day stop-limit
   buy and a Good 'til Canceled sell stop was accepted. That is the form
   every ticket in `orders.json` is written in.
2. **U5:** test A2 was accepted, so a burst ticket (its buy stop a cushion
   over the last close) can be entered before the open as written.
3. **U7:** the order kept through the open was seen to trigger and fill, and
   its sell stop then showed as an open order.
4. Each answer is written into `knowledge/broker-fidelity.md` as a dated
   revision, as the protocol's last section asks.

If any of these went another way, the sitting did not pass. Leave
`passed` false and record what the screen showed in the broker note. The
handoff changes first (the order's form, or what the execution agent is
told to do), in a reviewed change, and the sitting is run again.

When it passed, edit `knowledge/go-live/fidelity-protocol.json`:

```json
{
 "passed": true,
 "recorded_on": "YYYY-MM-DD",
 "recorded_by": "owner"
}
```

keeping its other fields (`version`, `protocol`, `note`), and commit it.
`recorded_on` is the date of the sitting; a date after the evening's session
does not pass. The file is public: record no account number, balance, order
id or anything else private in it. Nothing in this repository sets it, and
the next evening's record reads it.

The publication check holds a live `orders.json` to this file and to the
ablation's results again, so a file that says `live` while the committed
record is not passed is refused.

## The reasons `live_ready` can name

| reason | what it says |
|---|---|
| `fidelity_protocol` | the owner has not recorded the Fidelity protocol as passed |
| `on_time_sessions` | fewer consecutive sessions than the gate needs were published and checked on time |
| `settled_forward_plans` | fewer model plans than the gate needs have settled under the standing rules |
| `ablation_report` | the pre-registered ablation's results are not committed |
| `go_live_gate_not_evaluated` | the record carries no gate this file can read: a record from before the gate, or one whose gate block is not this version's |

## What it does not establish

That the strategy has an edge, that a ticket will fill, or that Fidelity
accepts a given order on a given morning. The ablation's results are a
condition because they must be committed before money moves, not because
any of them recommends a change; the settled count is a sample size, not a
result.
