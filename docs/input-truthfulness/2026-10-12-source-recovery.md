# 12 October 2026 — the publication's own missing stocks, asked for once more

**What this is.** `src/source_recovery.py` is a companion of the kind
`src/morning.py` and `src/research_observations.py` already are: a dated,
read-only receipt (`docs/source-recovery.json`) bound to the exact canonical
publication and its compact reader, written by its own workflow
(`.github/workflows/source-recovery.yml`), persisted as a one-file commit on
`main` (`tools/publish_morning.py --target recovery`) and verified served by
the publication gate (`OPTIONAL_RECORD_FILES`), which runs after the workflow
completes. It answers one question #111 left open: when the evening's record
says a stock's bars were missing or behind, does asking the provider once more,
before the next session opens, return the bar? It is a reading of the
provider's late arrival; it changes nothing the evening wrote and it decides
nothing.

**When it runs.** Two daily slots, 07:37 and 09:37 UTC: after the hour by
which the 9 October late bars had arrived (07:12 UTC, below), and hours before
either open (13:30 UTC in summer, 14:30 in winter). The first draft rode the
morning workflow as its third collector, which left it about ten minutes
between the 13:20 UTC slot and the open, behind two collectors bounded at 180
seconds each and that workflow's guard; GitHub started both 12 October morning
crons 8 h 24 m late (runs `38312550090` and `38312772384`, created 21:44:56
and 21:47:04 UTC), and their guard refused them as `entry_window_ended`. Its
own workflow lets no other collector decide whether it runs or whether its
receipt is kept, and its slots leave hours of slack. They are still best
effort: a slot that starts after the next open records `recovery_window_ended`
and asks nothing. A manual dispatch is a real collection, recorded like a
scheduled one; the workflow has no rehearsal input, so no dispatch spends a
request it cannot record.

**What it reads, and in what order.** The frozen basis is the record's own:
universe identity, feed (`sip`), split adjustment, lookback, measured session and
rules digest (`frozen_basis()`). The names come from the record FIRST --
`run.input_tolerance.names`, the stale frames the tolerance named in full, each
with its recorded ending -- and from the publication's quality-ledger entry
SECOND (`docs/quality-ledger/v1/<data_sha256>.json.gz`, read through
`quality_ledger`, whose `input.exception_membership` carries the complete
exception membership per category), each population held to the publication's
own count and identity for its category (`run.coverage.reasons`); a membership
that does not re-derive it is `membership_mismatch`. Nothing is guessed. When
no counted stock is named anywhere the receipt is `deficit_not_named` and the
request stays unspent; when only some are named, the named ones are asked for
and the rest are counted in `deficits.unnamed_frames` and in the sentence ("N
more counted frames are named nowhere"). The benchmark is counted beside the
stocks and never requested.

**What it may spend.** One request (`MAX_BATCHES = 1`) of at most
`MAX_BATCH_ATTEMPTS = 2` attempts over at most `MAX_NAMES = 100` names -- one
provider batch, `market_data.DEFAULT_BATCH_SIZE`, which is also the stale
tolerance's `STALE_NAMES_MAX`, so every tolerated night fits in one request --
within `MAX_COLLECTION_SECONDS = 300`, through `market_data.download_bars` with
the record's own feed, adjustment and lookback. The call runs under a
main-thread timer set to the earlier of `FETCH_RESERVE_SECONDS = 10` short of
that bound and the next session's open (`recovery_until: next_session_open`,
the window the evening guard and the page already use). A call the timer stops
is kept as `timeout` with its attempts counted, so a request that was sent
still binds the next slot; an answer that lands after the open is not kept and
is said as not answered before it; a bound that expires before any call is sent
is a zero-attempt receipt that says the stocks were not asked for, spends
nothing and leaves the next slot free to ask. The receipt counts calls to the
bars endpoint: a retry the SDK makes inside one call (it retries a 429 or 504
on its own) and a page it follows are not counted, which `LIMITS` names
(`sdk_retries_and_pages_not_counted`). More named deficits than the budget is
`deficit_over_budget` whole, never a prefix. A publication whose one request
was spent is `already_attempted`; an inapplicable receipt
(`future_publication`, `stale_publication`, `recovery_window_ended`,
`basis_differs`, `membership_mismatch`, `no_coverage_deficit`,
`benchmark_only` (the only counted frame is the benchmark's, which is never
requested), `deficit_not_named`, `deficit_over_budget`) spends nothing and may
be replaced by a later one that says something else; a later inapplicable
receipt for the same publication and reason is refused as unchanged, so the
daily schedule commits at most one receipt per publication and reason. The
second slot spends at most once more after a first slot whose persist was
refused, which `LIMITS` says in so many words. Credentials absent is
`provider_unavailable / missing_credentials` with zero attempts, and the
sentence says the stocks were not asked for.

**Two reads, kept apart.** `original` copies the record's acceptance facts
(`ready_stocks`, `intended_stocks`, status, the tolerance verdict, the gaps per
category); `recovered` counts what came back (`requested`, `arrived`,
`session_ready`, and the outcomes `recovered`, `arrived_not_ready`,
`still_stale`, `still_missing`, `not_returned`). The sentence names both and
combines them nowhere: "The publication stays 4774 of 4775 intended stocks
ready; its measurements, grades, plans and tickets are unchanged, and why a bar
was absent is not established." A zero-volume bar is said beside the clause
that holds it, so a placeholder that arrived without the session before it is
never counted among the bars that pass the session rules. A bar that arrives is
a fact about the provider on the morning it was asked; it is never a signal, a
plan, a ticket or a changed coverage figure. `tests/test_source_recovery.py`
runs the next evening with and without a committed receipt and holds the record
equal after removing its wall-clock fields and the prompt cache's split, and
`picks.json` byte-identical.

**The arrival evidence that motivated it**, read from git rather than inferred.
The 9 October session was published three times under one universe identity
(`ea8f2d4b68e1ebd8`): run `38014333381` at 01:44:58 UTC on 10 October with 22
stale stocks (4,753 of 4,775 ready), then run `38033614291` at 07:12:55 UTC with
one (4,774 of 4,775), then run `38034610157` at 07:30:15 UTC with the same one
(WBD, ending 5 October). The three share the universe, its snapshot, the feed,
the adjustment and the session, but not the rules digest (`8e9ea8528b31`,
`4f69dc967d7a`, `c9dc7d6d1d87`): the rules merged between the runs (the ZIM
event-registry entry, #115, and the review-selection policy, #121) moved it,
and the bars request does not read it, so `same_cohort()`
refuses each pair on `rules_version` while the arrival comparison holds on the
request's own fields. The same provider, asked again five and a half hours
later over the same selection, returned 21 of the 22. The 8 October pair is
weaker still: `1e1ffe9c` (4,755 of 4,777, identity `ded8b0a93cffbafe`) and
`e67f8cba` (4,774 of 4,775, identity `ea8f2d4b68e1ebd8`) were measured over
different universes, so their difference is membership as much as arrival.
Those are publications re-run on one night; this companion measures the same
thing on purpose, once, with the names and the basis frozen, so the count is a
fact about the provider and not about the directory.

**What the first live receipt asks for.** Every name in its publication's
`run.input_tolerance.names` (or, failing those, its ledger membership). The
publication on `main` when this was revised is run `38339720035` for 12
October (published 03:02 UTC on 13 October, 407 minutes after completion), the
first live night whose status is `ok` beside a degraded acceptance: eleven
stale stocks named in full -- BEBE, ELLO, HFBL, MDRR, MGRT, NCEW, PFX, RAND,
ROMA and TCBS ending 9 October, WBD ending 5 October -- within its limit of 47,
and 4,767 of 4,778 ready. Its next open (13 October) has passed, so its window
is closed; the first live receipt is over the first publication whose next open
is still ahead when the first scheduled slot after the merge runs. An offline
collection over the 12 October record at a 13:20 UTC clock asks for those
eleven in one call and, through the suite's double, writes
`nothing_recovered`; the live answer is the provider's to give. The record's
`coverage.scan_ready` is the price-eligible subset the scan measured and is not
the readiness denominator the recovery reads; the two are not to be compared.

**The receipt is checked before it is accepted.** `validate_receipt()`
re-derives every field the bound inputs determine -- the publication binding,
the frozen basis, the window from the publication's own calendar, the original
facts, the deficit accounting (names off the record, the ledger's membership and
its digest), the reason, the requested names, the request window, the tallies,
the status, the sentence, the prior receipt's bytes and the 64 KiB bound on the
bytes written -- comparing them as JSON, so `True` is not `1` and `4774.0` is
not `4774`. What only the provider's answer determines (each row's outcome,
ending and volume; the source's status, error kind, attempts and check time) is
held to its shape and to every other field it implies: an arrived bar carries a
session ending, a volume and a flat flag, a bar that did not arrive carries
none, an answer that was kept is dated at or before the open, an inapplicable
receipt spent nothing, and a zero-attempt receipt has no request window. Each
check has a forgery refused by its own message
(`test_each_validator_check_refuses_its_own_forgery`). The publisher adds the
compare-and-swap on the record, the ledger entry on `main` and the prior
receipt; a prior receipt of another publication, of any schema or size, binds
nothing beyond its bytes' hash, and a receipt that spent its request is never
replaced. The page (`docs/app.js`, the Method view) prints the sentence only
after hashing the loaded publication's bytes against the receipt's binding --
the canonical digest and, on a compact-reader load, the reader's -- reads the
receipt past the HTTP cache, says that no receipt was published only on a 404,
reads it again when an update check finds the record unchanged while Method is
shown, and prints nothing else of it.

**What is NOT RUN.** A live receipt: the first can exist on the first
scheduled slot after the merge whose publication's next open is still ahead,
only if GitHub starts that slot before the open, and only with the Alpaca pair
the morning collector already reads. Its status, reason, rows, call count and
the page's sentence are to be read and recorded in `CLAUDE.md`. Nothing here is
a change to the stale tolerance, the coverage denominators, the scan, the grades
or any strategy number; `pipeline.build_rules()` does not nest this module's
`RULES`, so `rules_version` does not move.

Reproduce: `python -m src.source_recovery --docs docs --output <path> --dry-run`
over a checkout (a fixture publication is admitted in a dry run and refused by
the publisher); `python tests/fixtures/source-recovery/generate.py --check`
holds every committed variant to the collector; `node tools/page_smoke.mjs
--only recovery` reads the Method line in Chromium.
