# Input truthfulness milestone

[23 September 2026: production reader compatibility](2026-09-23-reader-authority-production-compatibility.md)
reconstructs all twelve September 22 request/fallback identities. Raw replies
were discarded, so finding-level classification remains BLOCKED. The bounded
prospective correction exposes the exact nested schema and retains returned text.

[22 September 2026: reader downgrade/source authority](2026-09-22-reader-downgrade-audit.md)
audits all 108 retained completed reads and individually records all 14 mechanical
A+ assessments. Historical decisions remain unchanged.

For the later retained production audit and prospective evidence ledger, see
[22 September 2026: input quality and A+](2026-09-22-retained-quality-audit.md).
Its derived inventory separates legacy/modern populations and UNKNOWN fields;
the new ledger preserves publication facts without modifying this input contract.

Base: `7e6d056672079e2ac46b6e5a84ae9589f1648e80` (merged PR #68).
Scope: universe selection, bar-input populations, publication acceptance and
input basis. Discovery contract v1, grading, annotations, ticket/breadth rules
and design-system v2.13.0 are preserved. No historical published record is edited.

## Executed baseline negatives

An untouched archive of the base failed five assertions at the intended checks:

- A valid common stock with directory volume 50,000 was excluded although its
  actual bar rose 5% on 150,000 shares, above the prior 50,000 shares.
- Directory last sale $2.90 excluded an actual $3.05 reaction breakout.
- With a two-name fetch chunk and three intended names, forcing budget expiry
  after the chunk produced `requested = 3` despite only two attempted names.
- A successfully published run lacked the intended-population ledger.
- A September 10 scan using a September 15 directory did not record that
  the snapshot was later than its scan session.

The preserved partial draft already fixed those five cases. This milestone
finishes conservation, failure accounting, record validation, page wording,
recovery basis, boundary tests and documentation around it.

## Population and acceptance contract

`run.universe.selection` accounts for directory rows (including duplicates and
malformed rows), security admissions/exclusions, seed overrides/additions,
manual selections, capacity cuts and intended stocks. The source, UTC timestamp,
canonical directory-field SHA-256 and selection identity are archived. The first
row for a duplicate symbol wins, with duplicates counted separately.

`run.coverage` extends `DownloadStats`; it is not a second transport monitor.
Its exclusive equations are enforced before publication and in `report.validate`:

- intended = requested + budget-unfetched + failure-unfetched;
- requested = returned + no bars + failed after retry + permanently refused;
- returned = stale + on-session;
- on-session = gapped + unreadable + session-ready;
- session-ready = ready benchmark + current-price excluded + scan-ready + closed/not-scanned;
- scan-ready = measured + scan errors + scan-unattempted;
- measured = burst-only + dollar-only + both + neither;
- reaction matches = quality success + quality errors.

Repaired duplicate timestamps overlap returned frames and are explicitly
separate diagnostics. Counts, bounded reason samples and stable membership
identities replace unbounded public ticker lists. A no-bar response establishes
no delisting. A permanent refusal stops immediately and retains earlier results
and all unrequested names on the failure report and in the structured run log.

The unchanged minimum is **50% of intended stocks with usable session bars**,
excluding SPY, before current-session price eligibility. Below it, or on a
permanent refusal, publication fails before model grading and preserves the last
published record. Partial coverage at/above it, capacity truncation, and scan or
quality errors are degraded. Complete means the explicitly selected population,
not exact TC2000 membership or every listed security. Failed runs retain pending
scan counts; pending evaluations cannot be published.

The directory no longer gates on quotes. The existing $3 policy reads actual
cent-rounded session closes; seed/explicit exceptions remain. Scan-specific
volume conditions stay in `scans.py`, including its inclusive 100,000-share
reaction threshold and strict dollar-scan threshold. The 8,000-name capacity
bound and 900-second fetch budget are unchanged. The capacity rank can exclude
a breakout if it binds: every cut is counted and the result is degraded. It cuts
zero names in the measured archived directory; no broader false-negative rate
is claimed.

## Bar and historical basis

The actual `StockBarsRequest` still uses `Adjustment.SPLIT`, with explicit feed
and daily timeframe. `run.input_basis`, archived recovery context, Method,
stock provenance and newly saved originals carry that basis. Split-adjusted
never means raw or dividend-adjusted. Old publications and saved originals
without evidence stay unknown; their bytes are not rewritten.

Current and cached Nasdaq directories approximate security classification and
do not establish historical point-in-time membership. The capture timestamp and
before/same-date/after-session relation are explicit, including pinned sessions.
No historical-security-master or survivorship-bias-free backtest is claimed.

## Measured offline impact

`measurements.json` is generated by `python tools/input_impact.py --output
 docs/input-truthfulness/measurements.json`, with network connections blocked.
It uses the base's archived September 15 directory and the actual base classifier.

| Measurement | Before | After |
| --- | ---: | ---: |
| Directory rows | 7,141 | 7,141 |
| Intended stocks | 3,039 | 4,797 |
| Fetch names including SPY | 3,040 | 4,798 |
| Initial SDK batches / mocked requests | 31 | 48 |
| Returned bars, uniform 260-bar fixture | 790,400 | 1,247,480 |
| Median classification, ms | 33.204 | 35.776 |
| Mock fetch wall time, seconds | 13.260 | 20.186 |
| Full record, raw bytes | 228,193 | 231,724 |
| Full record, gzip bytes | 27,159 | 28,034 |

The stock population rises 57.85%; initial batches rise 54.84%. Pagination,
retries, real provider timing and dollar cost are not measured by this fixture.
The chart-reader cap remains twelve; actual future calls depend on candidates
within that cap. Provider requests and paid model calls made here: **zero**.

## Verification evidence

`tests/test_inputs.py` exercises the real scanners, offline pipeline, request
objects, mixed populations, both price/volume boundaries, capacity, fetch budget,
permanent refusal, historical dates, recovered basis, publication validation and
complete/incomplete zero-candidate results. Existing market-data tests keep the
transport/session rules covered. `empty` and `partial` page fixtures are made by
the real pipeline with doubles.

Six targeted mutations were killed: restoring the directory volume gate,
restoring the price gate, inflating requested counts, requesting raw bars,
skipping publication validation, and suppressing the page's adjustment basis.
Each Python mutation also ran unaffected volume controls; those controls passed.
The page mutation failed its six basis checks while the other 73 checks passed.
All source changes made by the mutation harness were restored.

Final verification results are recorded in the PR and the final CLAUDE.md
checkpoint. Browser screenshots are generated by `tools/page_smoke.mjs --shots`;
the partial-result and Method layouts were inspected at desktop and mobile sizes.

KEEP discovery v1, chart-reader separation, historical audit, continuity and
browser-local annotations. FIX this input boundary only. DEFER holiday timing,
full measurement-to-publication provenance, dollar-formula primary-source work,
real qualifying-ticket evidence and profitability. OMIT paid/provider replay,
manual deployment, secret changes, repository settings and sibling changes.

## September 18 retained stale-input investigation

The [dated report and primary-source index](2026-09-18-stale-inputs.md) reconcile
4,774/4,793 ready stocks, preserve the eight-name sample and 11 unidentified
members, and distinguish classifier behavior from unresolved provider causes.
The [offline results](2026-09-18-stale-inputs-results.json) pin original evidence
hashes. Production selection, coverage and historical records are unchanged.

## Input-exception artifact v1

The retention milestone starts from `2b44d227829e6859d7f65358534022fa8cc8553a`
(tree `72071ad648b3183fbe63c19a3bd927b10ac1c04e`). Existing post-merge Tests
[35468881024](https://github.com/spicyChicken59/SpicyStock/actions/runs/35468881024)
passed before implementation. Main had not advanced; no open PR or duplicate
assignment branch was present. No check or evening workflow was dispatched.

`src/input_diagnostics.py` captures already available frames/stats immediately
after session classification, before price eligibility, coverage refusal, scans,
grading or publication. The permanent-refusal path captures the same boundary
from the exception's exposed earlier successful batches and complete unrequested
tail. It does not intercept SDK transport or recover partial response pages.

The existing evening workflow uploads `input-exceptions-<run-id>-<attempt>`
separately for 30 days. Its root contains `input-exceptions.json` and, only when
verified as actually used, the existing `universe-directory.json.gz` bytes.
The original evening artifact's name, paths, retention and ZIP root are unchanged.
No schedule, dispatch input, permissions, retry, persistence or publication guard
changes. Upload runs on success/failure only when this invocation returned an
artifact path. Diagnostics cannot reach the `git add docs` persistence step.

Local paths are `<docs-parent>/input-diagnostics/<run-or-local>-<attempt-or-unknown>-<unique-invocation>/`.
Tests and fixture generators use temporary output trees. There is no reused
`latest` file: healthy runs get their own record with empty exception membership;
known non-session/incomplete-session and preflight exits produce no snapshot and
attempt no fetch. `RunReport.input_diagnostic` distinguishes `not_attempted`,
`unavailable_before_classification`, `retained`, and `failed`. A classification
that never completed cannot supply a complete snapshot. A process killed before
the pipeline returns may have local files but no emitted upload path.

The versioned JSON contains:

- Allowlisted run ID, attempt, unique invocation, actual checkout revision read
  with Git, and separately the workflow revision. Unavailable identifiers stay
  null. Capture time is UTC; expected/evaluated/prior sessions are explicit.
- Complete intended, intended-stock, original universe, returned and ready
  memberships, each with the existing count/sample/identity convention. SPY's
  benchmark role is explicit. Universe source kind, capture timestamp, selection
  identity and canonical directory hash preserve the selection basis.
- Complete stale, gapped, unreadable, no-bar, failed-after-retry (`dropped`),
  permanently refused, budget-unrequested and failure-unrequested lists.
  Repaired duplicates remain overlapping diagnostics with extra-row counts;
  discarded duplicate copies are unavailable. A repair reported during an
  interrupted batch need not imply an exposed completed frame.
- Only input-boundary counts: intended/requested/returned, exception categories,
  on-session/ready/benchmark and transport diagnostics. `evaluation=not_started`
  excludes final scan, quality, grade and plan counters. The validator compares
  these unchanged boundaries and membership digests with an optional final
  public ledger; later price exclusions and measurement outcomes are not claimed
  to have occurred at capture time.
- Feed, split adjustment, daily timeframe, full symbol argument order, session,
  lookback, supplied `now`, chunk and budget arguments. The start/end window is
  explicitly **reconstructed from application arguments, not an observed wire
  request**. SDK attempt count is not HTTP request/page count; no wire count is
  invented. Default SDK batch size is labelled as a default.

### Observation bounds and meaning

Only exception/duplicate symbols carry observations. Each available frame keeps
the last eight positions plus the last expected-session and prior-session
positions if outside that tail: at most ten rows. Original frame order is kept.
If several timestamps share an anchor date, its present/retained counts expose
omissions. Dated anchors have priority if the global 80,010-row budget binds.
Every affected name remains listed, including explicit selections larger than
the ordinary 8,000-stock directory capacity; only bar payloads are bounded, never
membership. Omitted row counts, per-symbol partial flags and a payload summary
make truncation explicit. A missing frame has no observations and never becomes
an all-zero bar. Healthy returned frames are enumerated but not archived here.

OHLCV plus available `vwap`/`trade_count` are the only value fields, with meanings
included. Timestamps retain timezone and nanosecond precision; finite numeric
scalars are not rounded. Column-wise access preserves integer volume precision.
Null, pandas missing, NaN, positive/negative infinity, invalid values, absent
fields, NaT and unreadable timestamps have distinct states. Arbitrary invalid
strings/objects are labelled rather than serialized; their original text is not
retained. Extra columns, frame attributes, labels, clients, environment dumps,
headers, accounts, recipients and exception text are excluded.

These are **application-normalized observations**: sorted, de-duplicated,
renamed frames after the existing all-null-row removal. Original raw HTTP pages,
condition-coded trades, SDK-internal partial pages and provider entity mappings
remain unavailable. Observed absence does not identify a provider cause.

An existing directory is copied only for a directory-backed run when both its
capture timestamp and canonical field hash match the run's universe. Its bytes
and SHA-256 are preserved; mismatched/unavailable files are labelled. Seed and
explicit runs never attach a leftover cache. The existing 10 MiB compressed and
expanded directory limits apply. No directory refresh is added.

Serialization and writes are isolated from acceptance and retry machinery.
Temporary files close before atomic replacement. Failure logs the separate
`input_diagnostic_capture_failed` outcome without exception text, returns no
upload path, and leaves the existing coverage, original error and exit code
unchanged. Partial failed packages cannot be mistaken for a prior successful run.

### Offline verification and readiness

After extracting one artifact, use the run's independently observed identity:

```text
python tools/verify_input_diagnostics.py /path/to/extracted-artifact --run-id RUN_ID --attempt ATTEMPT --revision EXECUTION_SHA
```

Optionally add `--publication /path/to/same-run/data.json`. Complete memberships,
digests, disjoint accounting, overlapping repairs, observation counts and
directory bytes are validated. A changed membership or mismatched run/attempt/
revision is rejected. SHA-256 checks integrity, not authenticity against an
attacker able to rewrite both the file and its digest; compare the independently
expected Actions identity. The verifier reads files only.

`tests/test_input_retention.py` drives the unchanged transport/session/pipeline
through existing provider doubles. The nineteen-stale fixture failed on the
unmodified release base specifically because the diagnostic file was absent;
with capture it preserves all 19 names/observations while the public sample
remains eight and coverage remains degraded. These synthetic names do not fill
the eleven unknown historical identities. Frozen-clock enabled/disabled tests
compare publication bytes, coverage, calls and exit codes; the candidate test
also compares full prepared publications, picks, source objects, plans, grades
and rule digests. At the retention milestone, Windows exposed the source-object
rename failure documented in the dated CLAUDE.md checkpoints. The subsequent
Windows publication correction closes source-object staging handles before
replacement and cleanup. The candidate regression now requires successful
publication on every platform, with the real writer and no Windows exception.
Current native Windows and exact-head Linux results are recorded in the latest
handoff and its PR; the historical failures remain part of the evidence.

`python tools/input_diagnostic_size.py` builds an extreme deterministic fixture:
8,001 affected symbols, all 80,010 allowed rows, seven populated numeric fields,
nanosecond timestamps, and 260-row input frames. It uses intentionally invalid
prices and out-of-window dates to fill every payload slot, not provider evidence.
The raw JSON is approximately **45.56 MB**, deterministic gzip approximately
**0.40 MB**, plus at most **10 MiB** for an optional already-used directory.
Tests enforce ceilings of 60 MiB JSON and 2 MiB gzip for that fixture. Repeated
values compress unusually well; ZIP size for a real run is not predicted.
Membership metadata scales with explicit population size; the row ceiling is
global even beyond the ordinary directory population.

Software/fixture readiness and exact-head CI results belong in the PR and latest
CLAUDE.md checkpoint. **Production artifact verification: NOT RUN.** Only an
existing authorized evening run after normal guidance review/merge can establish
that. The historical report, source pins and original evidence remain unchanged.
