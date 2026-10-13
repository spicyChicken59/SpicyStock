# 12 October 2026 — the publication's own missing stocks, asked for once more

**What this is.** `src/source_recovery.py` is a morning companion of the kind
`src/morning.py` and `src/research_observations.py` already are: a dated,
read-only receipt (`docs/source-recovery.json`) bound to the exact canonical
publication and its compact reader, written by `morning.yml` beside the morning
observation, persisted as a one-file commit on `main`
(`tools/publish_morning.py --target recovery`) and verified served by the
publication gate (`OPTIONAL_RECORD_FILES`). It answers one question #111 left
open: when the evening's record says a stock's bars were missing or a session
behind, does asking the provider once more, the next morning, return the bar?
It is a reading of the provider's late arrival; it changes nothing the evening
wrote and it decides nothing.

**What it reads, and in what order.** The frozen basis is the record's own:
universe identity, feed (`sip`), split adjustment, lookback, measured session and
rules digest (`frozen_basis()`). The names come from the record FIRST --
`run.input_tolerance.names`, the stale frames the tolerance named in full, each
with its recorded ending -- and from the publication's quality-ledger entry
SECOND (`docs/quality-ledger/v1/<data_sha256>.json.gz`, read through
`quality_ledger`, whose `input.exception_membership` carries the complete
exception membership per category and is held to the ledger's own
`coverage.reasons` counts). Nothing is guessed: a deficit the record counted but
named nowhere is `deficit_not_named`, and the request stays unspent. The
benchmark is counted beside the stocks and never requested.

**What it may spend.** One request (`MAX_BATCHES = 1`) of at most
`MAX_BATCH_ATTEMPTS = 2` attempts over at most `MAX_NAMES = 100` names -- one
provider batch, `market_data.DEFAULT_BATCH_SIZE`, which is also the stale
tolerance's `STALE_NAMES_MAX`, so every tolerated night fits in one request --
within `MAX_COLLECTION_SECONDS = 300`, through `market_data.download_bars` with
the record's own feed, adjustment and lookback, the call itself under a
main-thread timer `FETCH_RESERVE_SECONDS = 10` short of that bound (the SDK
retries a 429 or 504 on its own, so no per-request timeout bounds it; a call
the timer stops is kept as `timeout` with its attempts counted, so a slow
answer still binds the next slot), and only while the next session
has not opened (`recovery_until: next_session_open`, the window the evening
guard and the page already use). More named deficits than the budget is
`deficit_over_budget` whole, never a prefix. A publication whose one request was
spent is `already_attempted`; an inapplicable receipt (`future_publication`,
`stale_publication`, `recovery_window_ended`, `basis_differs`,
`membership_mismatch`, `no_coverage_deficit`, `benchmark_only` (the only
counted frame is the benchmark's, which is never requested), `deficit_not_named`,
`deficit_over_budget`) spends nothing and may be replaced by a later one. The
morning workflow's second slot (13:28 UTC) therefore spends at most once more
after a first slot whose persist was refused, which `LIMITS` says in so many
words. Credentials absent is `provider_unavailable / missing_credentials` with
zero attempts.

**Two reads, kept apart.** `original` copies the record's acceptance facts
(`ready_stocks`, `intended_stocks`, status, the tolerance verdict, the gaps per
category); `recovered` counts what came back (`requested`, `arrived`,
`session_ready`, and the outcomes `recovered`, `arrived_not_ready`,
`still_stale`, `still_missing`, `not_returned`). The sentence names both and
combines them nowhere: "The publication stays 4774 of 4775 intended stocks
ready; its measurements, grades, plans and tickets are unchanged, and why a bar
was absent is not established." A bar that arrives is a fact about the provider
on the morning it was asked; it is never a signal, a plan, a ticket or a changed
coverage figure, and `tests/test_source_recovery.py` holds the next evening's
record byte-identical with and without a committed receipt.

**The arrival evidence that motivated it**, read from git rather than inferred.
The 9 October session was published three times under one universe identity
(`ea8f2d4b68e1ebd8`): run `38014333381` at 01:44:58 UTC on 10 October with 22
stale stocks (4,753 of 4,775 ready), then run `38033614291` at 07:12:55 UTC with
one (4,774 of 4,775), then run `38034610157` at 07:30:15 UTC with the same one
(WBD, ending 5 October). The same provider, asked again five and a half hours
later over the same selection, returned 21 of the 22. The 8 October pair is NOT
that evidence: `1e1ffe9c` (4,755 of 4,777, identity `ded8b0a93cffbafe`) and
`e67f8cba` (4,774 of 4,775, identity `ea8f2d4b68e1ebd8`) were measured over
different universes, so their difference is membership as much as arrival, and
`same_cohort()` would refuse to compare them. Those are two publications on one
night; this companion measures the same thing on purpose, once, with the names
and the basis frozen, so the count is a fact about the provider and not about
the directory.

**What the first live receipt is expected to say.** The publication on `main`
when this was written is `f5cbe38e…` (run `38034610157`, session 9 October,
plans for 12 October): `run.input_tolerance.names` is `["WBD"]` with its frame
ending 5 October, four sessions before the measured one. A frame a week behind
is far more likely `still_stale` than `recovered`, and that is a reading the
receipt is built to make without softening: one stock requested, one row,
`still_stale` with the unchanged ending, status `nothing_recovered`. The record's
`coverage.scan_ready` (3,675) is the price-eligible subset the scan measured and
is not the readiness denominator the recovery reads (`acceptance.ready_stocks`
4,774 of `intended_stocks` 4,775); the two are not to be compared.

**The receipt is re-derived before it is accepted.** `validate_receipt()`
replays the publication binding, the frozen basis, the window from the
publication's own calendar, the original facts, the deficit accounting (names
off the record, the ledger's membership and its digest), the request budget
against the source state, every row's rule (an arrived bar carries a session
ending, a volume and its flat flag; a bar that did not arrive carries none), the
tallies, the status against the rows and the source, the sentence, the prior
receipt's bytes and the 64 KiB bound; a forged field is refused by name. The
publisher adds the compare-and-swap on the record, the ledger entry on `main`
and the prior receipt; a receipt that spent its request is never replaced. The
page (`docs/app.js`, the Method view) prints the sentence only after hashing
the loaded publication's bytes against the receipt's binding, and prints
nothing else of it.

**What is NOT RUN.** A live receipt. The morning workflow's slots are 13:20 and
13:28 UTC; the first live receipt can exist on the first morning after the merge
whose publication's next open has not passed -- 12 October over the 9 October
publication (WBD) if the merge lands before 13:20 UTC, else 13 October over the
12 October publication -- and only if the Alpaca pair the morning collector
already reads is present. Its status, reason, rows, request count and the
page's sentence are to be read and recorded in `CLAUDE.md`. Nothing here is a
change to the stale tolerance, the coverage denominators, the scan, the grades
or any strategy number; `pipeline.build_rules()` does not nest this module's
`RULES`, so `rules_version` does not move.

Reproduce: `python -m src.source_recovery --docs docs --output <path> --dry-run`
over a checkout (a fixture publication is admitted in a dry run and refused by
the publisher); `python tests/fixtures/source-recovery/generate.py --check`
holds the nineteen committed variants to the collector; `node
tools/page_smoke.mjs --only recovery` reads the Method line in Chromium.
