# Historical inputs and market permission: September 24–25

**Verdict: RED agrees with the retained original aggregates. RED on a complete
later-retrieved stock-by-stock basis is still not established (BLOCKED).**
This milestone executed the available original-data investigation and built the
bounded acquisition/reconciliation path. No Alpaca request was made: neither
the sandbox nor host process exposes the existing Alpaca credential variables;
current zero-additional-cost entitlement and authorized private retention with
a reviewer retrieval path have not been established. These are execution
blockers, not a provider refusal or a software finding.

Base main is `0d702940814af05e9b8d2a4c887aee00939e46fc`, re-resolved from GitHub.
No open PR existed at start. The reviewed PR #92 tree remains intact. The one
new PR records the submitted head and normal CI. Guidance owns independent
review and merge; this work does not dispatch production or merge itself.

## What the retained observations establish

The [machine report](2026-09-28-historical-input-evidence/original-reconciliation.json)
checks both publication hashes, complete intended/requested/ready populations,
source object identities, original code identities and every recorded regime
predicate. The GitHub artifact metadata was re-read during this investigation;
both execution revisions match the supplied identities. Existing package hashes
match the reported artifact hashes. The existing workflow retains publications,
candidate evidence, history, charts and exception diagnostics, not the complete
raw daily-bar responses. No matching complete input object was found in these
SpicyStock packages or the accessible checkout. Unrelated storage was not used.

| Recorded quantity | September 24 | September 25 |
| --- | ---: | ---: |
| Intended stocks, excluding SPY | 4,779 | 4,780 |
| Ready stocks | 4,763 | 4,758 |
| Original stale stocks | 16 | 22 |
| Target-price exclusions | 1,047 | 1,058 |
| Final breadth population | 3,716 | 3,700 |
| Five-session up / down totals | 546 / 696 | 482 / 609 |
| Rounded five-session ratio | 0.78 | 0.79 |
| Ten-session up / down totals | 1,323 / 1,414 | 1,254 / 1,410 |
| Rounded ten-session ratio | 0.94 | 0.89 |
| Today's up / down events | 92 / 141 | 84 / 67 |
| Scaled down-event alarm | 400.2 | 398.5 |
| Up-50%-month count / hot threshold | 16 / 11.4 | 12 / 11.4 |

Only the ten-session ratio forces RED. The five-session fast-selling condition
and current down-event alarm do not fire. Both the ten-session YELLOW predicate
and monthly hot-count YELLOW predicate fire; RED takes precedence. Oversold is
informational and does not change permission. Ratio-of-sums and the producer's
rounding order reconcile. This validates algebra over retained counts, not the
missing underlying observations.

There is a newly explicit original-mask limit. The complete readiness masks
survive, but the price-exclusion record retains a count, short hash and eight
sample names. Surviving candidate/watch sources prove inclusion for 423 and 460
names. Final original membership is unknown for 4,332 and 4,290 ready names.
Those sets contain both included and price-excluded names; they are not counts
of missing bars. Recomputing prices from later data cannot silently fill this
original mask. The earlier report's statement that full intended universes were
not retained is too broad: full intended membership survives in the exception
packages; complete original values and the final eligibility mask do not.

The independent scalar reference agrees with production on all available
selected-source comparisons: 4,230 and 4,600 stock/session cells, respectively.
These are selected populations, not the original full breadth. Separate
original-event availability files enumerate every intended stock for the ten
target rolling sessions, with unknown values and membership kept explicit.
No candidate-only count is labeled full-market breadth. Coupled bounds permit
at most one up/down event for each unknown stock/session; adjacent events share
prices and volumes, so reported ranges are conservative relaxations, not claims
that all endpoints are jointly attainable.

## Frozen acquisition and comparison

The [acquisition manifest](2026-09-28-historical-input-evidence/acquisition-manifest.json)
contains canonical full symbol lists/hashes, the 4,780-stock union plus SPY,
original observations versus reconstructed parameters, per-session mapping
bases, explicit instants, calendars, warm-up and predeclared comparisons.
Only HUCK differs between the intended lists. The 228 seed price exemptions
come from the execution-revision seed file, checked against retained intended membership, with
the derivation identified. Original request spans begin August 4 and 5, 2025;
preserving those prefixes covers 252-session discovery and the quality run
counter that can inspect the whole prefix. This is not a historical-universe
backtest. The 110-session quality warm-up alone would be insufficient to claim
every original feature unchanged.

Canonical queries use SIP, 1Day, split, USD, ascending order and 100-symbol
chunks. A small SPY probe shares the same ledger and caps. The query bases use
September 25 and 26 as mapping dates, reconstructed from the original UTC run
dates because original wire `asof` was not recorded. These dates are not
observation-vintage timestamps. Different bases are never merged by ticker.
The explicit query endpoints are inclusive; daily timestamps are checked as
New York midnight on an XNYS session. The documented limit is per response,
not per security. A projected page count is planning only: terminal pagination
and the hard shared cap determine whether acquisition actually completes.
[Alpaca endpoint documentation](https://docs.alpaca.markets/us/reference/stockbars)
and [Market Data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq) were
checked September 28, 2026. The FAQ permits sufficiently delayed historical SIP
without a real-time subscription; that does not certify this account's current
terms or storage/redistribution rights.

The four comparisons remain separate:

| Comparison | Executed scope / status |
| --- | --- |
| A Original publication | PASS: identities, population conservation, retained source calculations and aggregate algebra. Full original underlying values remain BLOCKED. |
| B Pinned original population | BLOCKED: original final price mask is incomplete, even if later values become available. Known inclusion/exclusion witnesses remain explicit. |
| C Later retrieval, re-evaluated target eligibility | BLOCKED: no acquired dataset. Reusable private-cache replay and synthetic end-to-end controls are implemented. |
| D Per-observation-day eligibility | BLOCKED on real complete inputs; synthetic/reference controls execute. This is a counterfactual policy, not a production change. |

`historical_acquisition.py` charges request slots before HTTP in a persistent
SQLite ledger, holds one OS process lock, follows one request at a time, caches
successful pages and verifies their hashes on resume. The lifetime limits are
400 requests and 1 GiB uncompressed retained bodies, including probe/retries.
The lower of 20 requests/minute and the established provider limit applies;
Retry-After and provider quota reset affect the persistent wait boundary. There
is at most one transient retry. Permanent failures and ambiguous interrupted
requests stop; restarting does not clear charges. Do not delete or relocate the
ledger to obtain another budget. A page whose size exceeds the remaining
allowance is refused; a crash reservation conservatively consumes capacity.

The default transport is a direct GET to the fixed stock-bars host/path, with
no SDK retry, redirects, feed substitution or brokerage access. It reads only
the existing runtime credential pair after entitlement/storage gates. Error
messages use constant codes; response headers are allowlisted; credentials,
cookies and unsafe bodies are excluded. Approval proof is an external private
document, not a new environment setting or a claim inferred from a login.

`historical_normalization.py` keeps raw hashes and row identities before any
conversion. It validates finite positive OHLC, nonnegative share volume,
geometry, symbols, mapping basis, sessions and lookbacks. Stable duplicate
selection preserves discarded/selected row references. No missing session is
filled. Decimal strings survive alongside an explicit float64 conversion audit;
an exact-decimal event-boundary comparison reports representation differences
before they can be rounded away. Formula agreement on the selected float64
basis is distinct from wire-value agreement. Invalid, absent, partial, failed
and unresolved populations remain distinguishable.

## Exceptions, CRL/IQV, and plans

[Complete exceptions](2026-09-28-historical-input-evidence/complete-exceptions.json)
contains all 31 distinct stale securities and all 38 dated occurrences, their
original last observation/anchors and source identities. New target/prior bars
and provider explanations remain BLOCKED for every row. Staleness establishes
neither inactivity nor delisting; a future returned bar would establish current
availability only, not availability at the original acquisition time.

[Volume materiality](2026-09-28-historical-input-evidence/volume-materiality.json)
reuses the dated September 28 corroboration without inventing an earlier capture.
CRL retained September 24/23 shares are 1,590,887 / 1,594,208; the public page
observations are 1,574,098 / 1,474,124. IQV is 1,893,479 / 1,116,832 versus
1,891,777 / 1,104,252. Sources are the dated existing
[CRL](https://stockanalysis.com/stocks/crl/history/) and
[IQV](https://stockanalysis.com/stocks/iqv/history/) observations, not a fresh
provider download in this assignment. Session/condition/adjustment comparability
remains unresolved, and neither source is selected as the truth.

The reproducible CRL chain changes above-prior volume, adds the 4% route and
changes mechanical A to A+; the independent Dollar route survives. Rechecking
all ten event cells, including the affected prior date, changes one up event
and no down events. Holding all other original observations fixed still gives
a rounded ten-session ratio of 0.94 and RED. This is a narrowly conditioned
materiality calculation, not a bound on all missing inputs. IQV is the unchanged
control. Retained original final grades are B. An accepted reader/final A or A+
is a separate requirement: a new permissible regime would not create one.
Changed metrics cannot inherit old reader approval; no reader calls are made.

The existing report retains structural feasibility under explicitly substituted
market conditions. New diagnostic replay may evaluate mechanical candidates,
but provides no accepted review, order-copy action, settlement or publication.
No picks, portfolio returns or edge claims are created. Trade-condition
adjudication would require a separate, narrowly approved condition-coded
CRL/IQV September 23–24 trade sample and applicable aggregation/adjustment rules;
trade/quote downloads are outside this authorization.

## Source fidelity is a separate question

The [PRIMARY Stockbee MM page](https://stockbee.blogspot.com/p/mm.html), inspected
September 28, supports ratio-of-sums through Bonde's 2017/2018 replies. Its
deterioration discussion refers to a series of large down-event days. Treating
one scaled day as an automatic RED gate is a SpicyStock policy. The
[2010 primary explanation](https://stockbee.blogspot.com/2010/05/if-you-want-to-avoid-market-surprises.html)
discusses a ten-day ratio crossing two and falling below one-half in context;
it does not establish the repository's exact automatic RED-at-one and
five-day conjunction as a verbatim primary formula. The 2022 scans page was
identified, but its formula images were not independently verified here.
The existing broad `(B)` labels do not settle these differences. PRIMARY,
LATER BONDE, COMMUNITY field-guide interpretation, SPICYSTOCK DERIVED gates
and EMPIRICAL arithmetic are distinct. No threshold was changed to resolve an
attribution uncertainty or create buys. A materially different policy needs review.

## Reproduction and the precise blocked step

Use a clean clone at the PR head, Python 3.12 and the existing pinned historical
test requirements. Dependency installation is environment preparation; the
commands below block sockets during all data replay. Output directories must
be outside the repository. The original proof reads original blobs using Git;
do not substitute today's live publication for its fixed hashes.

```sh
python -m pip install -r tools/requirements-historical.txt
python tools/historical_input_proof.py --output /private/review/original-proof
python tools/historical_acquisition.py --manifest docs/input-truthfulness/2026-09-28-historical-input-evidence/acquisition-manifest.json
python tools/historical_reference_controls.py /private/review/reference-controls.json
python tools/historical_acquisition_controls.py --output /private/review/acquisition-controls
MPLBACKEND=Agg python -m pytest tests/ -q
MPLBACKEND=Agg python tools/make_fixture.py --check
node tools/continuity_check.mjs
node tools/chart_check.mjs
node tools/page_smoke.mjs --shots /private/review/page-shots
```

Acquisition is **NOT RUN**: actual new HTTP requests **0**, new retained response
bytes **0**, additional spend **$0**. No private acquired object or approved
storage path exists to hand off, and no placeholder public artifact is offered
as one. The access probe is also NOT RUN. The raw-cache replay below is BLOCKED
until an authorized frozen cache exists; it is not presented as executed on real
new inputs:

```sh
python tools/historical_reconcile.py --manifest docs/input-truthfulness/2026-09-28-historical-input-evidence/acquisition-manifest.json --storage /approved/private/spicystock-historical-input --session 2026-09-24
python tools/historical_reconcile.py --manifest docs/input-truthfulness/2026-09-28-historical-input-evidence/acquisition-manifest.json --storage /approved/private/spicystock-historical-input --session 2026-09-25
```

The smallest next execution decision for Guidance is an existing secret-capable
runtime plus an existing private destination with authorized reviewer access,
documented daily SIP $0 entitlement and retention rights. If only GitHub Actions
has the credentials, a dedicated manual historical-only job with encrypted
transfer to that approved destination would require a separately reviewed
execution arrangement. It must use the frozen acquisition identity and shared
ledger, never the production workflow or public Actions artifacts. No new
workflow, secret, storage service or schedule is created here. Tahir need not
collect screenshots, run commands or paste credentials.

## Repairs, verification and handoff

### PR #93 correction: resolvable duplicate raw-row references

Guidance review `5342729066` identified an acquisition-tool lineage defect on
`a9ed0ec3b64399e1f9d80ac3ce27d921c289f9b1`. Re-resolved base/main remains
`0d702940814af05e9b8d2a4c887aee00939e46fc`. The correction stays on PR #93;
its final submitted head and normal CI results are recorded in that PR.

The old reference paired the current page hash with the symbol's cumulative
arrival count. Through the actual `Acquisition` class and synthetic transport,
September 23's replacement (1,500 shares at page 2 / AAA row 0) incorrectly
pointed to September 24 (2,000 shares at row 1); a one-row later page produced
an out-of-range reference. Terminal pagination still reported true. These are
synthetic observations, not a new provider acquisition or a production finding.

The output contract is now `raw-page-symbol-row-v1`. Every previous/discarded
and selected reference carries `page_sha256`, `page_index`, `symbol`, and
`row_index`. Verify the raw bytes against the SHA-256, then resolve
`json.loads(raw_page)["bars"][symbol][row_index]`. Both indices are zero-based:
`page_index` is query pagination order; `row_index` is within that page's own
symbol array, never an accumulated arrival count. This is the same raw-row
identity emitted by the unchanged normalizer. Stable last-arrival selection,
original raw bytes/hashes/order, pagination and persistent budgets are unchanged.
Cached resume re-derives the output manifest from the same verified raw pages;
the frozen acquisition request manifest and ledger identity are not rewritten.

- FAIL — reviewed source: 6 raw-pointer regressions fail, 3 unaffected controls
  pass. The first execution used the unchanged working-tree acquisition module,
  before applying the repair; its transcript and JUnit are retained.
- PASS — corrected source: all 9 focused regressions pass. They dereference both
  references and check symbol, timestamp, complete OHLCV values and agreement with
  the normalizer. Cases cover two/three pages, later-page internal duplicates,
  multiple symbols, one-row later pages and repeated replacements, plus unchanged
  same-page/no-duplicate controls.
- FAIL — restoring only the cumulative-index assignment in an isolated process
  produces the same 6 raw-pointer failures; the 3 controls still pass. The durable
  runner also loads the exact reviewed source without changing the checkout.
- PASS — cached-resume cases reproduce the full manifest and both raw references
  with zero further transport calls, unchanged attempt rows and raw page bytes,
  and unchanged request/byte charges even when both synthetic budgets are exhausted.

See [correction evidence](2026-09-28-historical-input-evidence/lineage-correction/README.md).
Use a full-history clone at the correction head with the existing pinned test
environment; the reviewed parent commit must be present for the source control.
All test/replay sockets are blocked, and all transport responses are synthetic:

```sh
python tools/historical_lineage_controls.py --output /tmp/spicystock-lineage-controls
MPLBACKEND=Agg python -m pytest tests/test_historical_acquisition.py tests/test_historical_normalization.py tests/test_historical_reconcile.py -q
MPLBACKEND=Agg python -m pytest tests/ -q
```

Real acquisition and its access probe remain NOT RUN: zero requests, zero new
raw-response bytes and zero additional spend. Runtime/access/retention/private
storage prerequisites remain BLOCKED; the 400-request / 1-GiB / $0 authorization
is unchanged. Corrected synthetic lineage establishes none of the missing
original membership, later-retrieval, provider-truth, reader or trading-edge proof.
No production, UI, workflow or previous historical analysis is changed or rerun.

### Original investigation verification

No production data/calculation defect has been demonstrated. The scope therefore
adds investigation tooling and focused regressions; it does not manufacture a
production patch. Initial new-tool test failures and their corrections are
engineering results, not before/after evidence against the historical producer.
Verification counts, isolated negative controls, protected hashes and final CI
are recorded in the evidence directory and PR. Full original POC work was reused,
not regenerated. No UI change was made, so no new UI result is claimed; the normal
page gate still includes #91 keyboard and #92 historical/wait assertions.

PASS — final local Python suite: 1,677 tests, no skips. PASS — 8,867 protected
existing files match the original checkout and Git blob identities. The Windows
runtime uses UTF-8 and an external import adapter for Unix-only resource telemetry;
the adapter raises if telemetry is requested and fabricates no measurement.
FAIL — the Windows fixture byte check reports 24 differing gzip objects, which
remain unchanged. The exact cause was not independently adjudicated in this run;
normal Linux CI supplies the native fixture/browser result. Earlier harness and
test-count failures are retained in `verification.json`, separate from acceptance.

KEEP existing thresholds, ranking, `accepted_required_v1`, reader/model budgets,
account assumptions, stop-constrained planning, publication safeguards and
design-system 2.13.0 at `14a752dd0269bd6ebbb7080eb0d9e1922cd1ef2c`.
FIX NOW the bounded acquisition, explicit missing-mask accounting, independent
reference and reproducible retained-data materiality analysis in this PR.
DEFER the precisely blocked secure acquisition, complete original-value proof,
source-policy adjudication, new reader judgments and trade-condition evidence.
OMIT invented plans, provider blame, profitability claims, redesign, dispatch,
automatic retention and a second milestone. Stop at one PR for Guidance review.
