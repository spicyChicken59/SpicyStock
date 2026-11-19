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

## The four conditions

| condition | met when | read from |
|---|---|---|
| `fidelity_protocol` | the owner has recorded the one-sitting protocol (`knowledge/broker-fidelity-protocol.md`) as passed | `knowledge/go-live/fidelity-protocol.json`: `passed` true, `recorded_on` a date, `recorded_by` `"owner"` |
| `on_time_sessions` | the consecutive XNYS sessions ending on the one before tonight's, as many as `go_live.ON_TIME_SESSIONS`, were each published by `go_live.PUBLISH_BY_ET` New York time on the session's own date (at the run's finish), started automatically, and checked by a morning check that ran (a status of `go_live.MORNING_RAN`, not a rehearsal) bound to that publication, generated inside its collection window and by `go_live.MORNING_DUE_CT` Chicago time on the session its plans were for | the record's `run.go_live.ledger`, one entry per closed session |
| `settled_forward_plans` | at least `go_live.MIN_SETTLED_FORWARD` model plans in the scorecard's window settled, each picked on or after `run.go_live.strategy.since` | the record's scorecard rows |
| `ablation_report` | the pre-registered ablation's results are committed | `docs/input-truthfulness/2026-11-19-ablation/ablation.json` |

**Started automatically** means a scheduled run, or the external
dispatcher's dispatch with `only_if_unpublished` ticked
(`tools/dispatch_schedule.py`); a hand-run publish is not. The record
archives how its run was started as `run.trigger` (the workflow's event
name and the input); a record without it closes no counted session. A
person could tick the input by hand, and the record cannot tell that
dispatch from the dispatcher's: the condition reads the input, as the
guard does.

**Published by** is read at the run's finish: the record's own start clock
(`run.published_at`, set when the run starts) plus its elapsed seconds
(`run.elapsed_seconds`), the instant the record is installed. The commit
lands on `main` a few minutes after it and Pages later still, so a run that
finishes at the line is published to the site just after it; a record with
no elapsed seconds closes no counted session.

**The ledger** closes a session the evening after it: by then the morning
file for that publication exists on `main` (`docs/morning.json`, bound by
the publication's SHA-256). A missed session, a late one, a hand-run one or
one whose morning check came late, quoted nothing (an inapplicable or
unavailable receipt) or not at all ends the run of counted sessions, and it
starts again at zero. A session never published leaves no row at all, so the
run must end on the XNYS session before tonight's: a ledger whose newest
session is older counts nothing, however long the run before it. The ledger
keeps the newest `go_live.LEDGER_MAX` sessions.

**The standing rules** are the record's rules digest without what is not a
strategy rule (`go_live.NON_STRATEGY_RULES`): the night's universe
membership, which moves every night, and the event registry (its entries,
their review dates and notes, and its digest), which the CI review check
makes the owner revisit every week or two. A registry review therefore does
not restart the count; a change to any strategy rule does. When the digest
changes, `since` moves to the session it changed on and the settled count
starts again: plans made under earlier rules do not count. A change first
seen on a backfill of an older session stands from the session after the
newest one already published, so a backfill's picks never count as forward
plans. A plan that leaves the scorecard's window leaves the count, so the
condition can go from met to not met.

## Recording the Fidelity protocol

Run every step of `knowledge/broker-fidelity-protocol.md` at Fidelity. If
every one passed, edit `knowledge/go-live/fidelity-protocol.json`:

```json
{
 "passed": true,
 "recorded_on": "YYYY-MM-DD",
 "recorded_by": "owner"
}
```

keeping its other fields, and commit it. The file is public: record no
account number, balance, order id or anything else private in it. Nothing
in this repository sets it, and the next evening's record reads it.

## What it does not establish

That the strategy has an edge, that a ticket will fill, or that Fidelity
accepts a given order on a given morning. The ablation's results are a
condition because they must be committed before money moves, not because
any of them recommends a change; the settled count is a sample size, not a
result.
