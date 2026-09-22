# September 22, 2026: bounded acquisition-corporation classification

Base: `49e2724c94b60963d914d55a2bf98598ac6507ad`.
Branch: `fix/blank-check-universe-classification`.
Scope: `src/universe.py::classify()` and its offline evidence, tests and handoff.
The exact implementation head is in the final CLAUDE.md checkpoint; the final
review head and required check runs are pinned in the PR description.

## Contract and evidence limits

The classifier previously depended too heavily on Nasdaq's exact `blank checks`
industry label. The retained September 18 investigation copies BKHA, EGHA and
HCMA rows whose names identify acquisition corporations but whose industry
labels look operational. Its dated issuer evidence describes blank-check
companies. Those rows reproduce the classification defect, not the cause of
any missing provider bar.

The correction reuses `blank check company`. After the unchanged symbol,
security-type, seed and unknown-industry checks, a case-insensitive legal-name
rule recognizes `Acquisition Corp`, `Acquisition Corp.`, or
`Acquisition Corporation`, optionally followed by a Roman-number suffix using
I/V/X, then an optional Class A/B/C label and `Common Stock` or
`Ordinary Share[s]` at the end of the name. Whitespace variation and a trailing
period on the corporate abbreviation do not change the form. Retained names
support unpunctuated Corp and suffixes I, II, III and V. No Ltd, LLC, generic
shell vocabulary, ticker blacklist or fuzzy-name rule is added. A longer issuer
name such as `Acquisition Corporate Services Inc.` does not match.

Generic acquisition, holdings, capital and investment words do not exclude a
company. Price, volume, bar absence, stale status and provider behavior are not
classification inputs. Unknown-industry precedence and seed overrides remain
exactly as before; foreign and biotech remain warnings. This is still a
security-name approximation, not a current issuer-status service or a dated
security master. Names outside the supported form remain subject to existing
rules, not a claim that every blank-check company is identified.

**Historical September 18 and September 21 publications remain unchanged.**
Their intended/stale denominators are not rewritten. The new exclusions do not
establish why historical provider bars were absent, and the correction does
not claim to explain all 20 September 21 stale inputs. Any admitted stock
without its expected-session bar remains stale/unknown or unavailable, never
automatically excluded and never a measured non-match. Coverage remains degraded
when the existing ledger requires it.

`pipeline.build_rules()` already incorporates universe membership identity into
`app.rules_version`. No hand-edited version or new version contract is added.
A selection that loses these names receives a changed identity/digest through
that existing contract; unchanged synthetic fixture populations retain their
existing rules and bytes. Discovery, grading, thresholds, ticket/plan logic and
entry timing are unchanged.
On the base's latest retained directory, the existing identity changes from
`cb87e6a42a1e01e0` to `03203b6a9c4be6e1` and the computed rules digest from
`d5d62f525e0f` to `b4afcde9e058`. An executed comparison confirms that
`universe.identity` is the only differing entry in `build_rules()`.

## Failing before and passing after

The new regression was run while HEAD was the exact base above and
`git diff --exit-code BASE -- src` confirmed no production-source changes.
The final baseline run of `tests/test_universe.py` plus the new pipeline journey
produced **11 failed, 108 passed**. BKHA, EGHA and HCMA each failed because
`classify()` returned `None` rather than `blank check company`; the pipeline
regression independently observed all three in mocked SDK bar requests.
Additional failures covered legal suffixes and the new exclusion ledger.
The identical selection after correction produced **119 passed**.

The 108 controls passed before and after: ordinary Class A common stock;
generic capital/holdings/investment/acquisition names; exact blank-check industry;
seed admission and flags; foreign/biotech warnings; existing duplicates/capacity;
and the operating-only pipeline with one stale and one no-bar response. The new
combined ledger case proves the new family also conserves exclusions, a seed
override, a seed addition, duplicate rows and capacity cuts.

In the corrected pipeline journey, the real classifier feeds the real pipeline
through existing provider/model doubles. The three excluded names appear in
`run.universe.selection.exclusions` and never reach an SDK request. Thirteen
ready operating stocks, one stale operating stock and one no-bar operating
stock are still requested (plus SPY). Only thirteen stocks are measured; both
missing inputs remain in the intended denominator and the run is degraded.
`inputs.record_faults()` reports no faults. Email is skipped in this journey.

A separate in-memory mutation disabled only the old industry rule: all three
new retained-row regressions still passed, while the two exact-industry tests
failed (**24 passed, 2 expected failures**). This proves the name regression
does not pass accidentally through the old industry rule. No mutant was written
to disk or committed; no test was weakened or removed.

## Retained-directory sweep

Run `python tools/check_blank_check_universe.py` from this checkout. The tool
blocks sockets, loads the actual base classifier from Git, and compares it to
the corrected classifier using the unchanged base seed list. It reads all
13 unique directory snapshots retained in Git through the base, plus the
already committed eight-row September 18 investigation sample. It prints each
snapshot's full revision, compressed-byte SHA-256, membership identities,
complete new-exclusion list, row names, industry labels and count deltas.
It performs no provider call, refresh, scan or publication.

Both sides of this table use the **starting classifier contract**, not the
older classifiers that originally published the earlier snapshots. These are
offline selection comparisons, not backfilled production denominators.

| Retained snapshot revision | Capture time (UTC) | Rows | Base intended | Corrected intended |
|---|---|---:|---:|---:|
| `49e2724c94b60963d914d55a2bf98598ac6507ad` | 2026-09-22T00:48:42.004722+00:00 | 7,132 | 4,796 | 4,780 |
| `25eb5b2688a3ba1ceecc01083a7cb6046cc62aea` | 2026-09-21T23:54:25.319255+00:00 | 7,132 | 4,796 | 4,780 |
| `8387ccedae22fbf30ddebdb6f52e1e42326a7ec5` | 2026-09-18T22:22:34.176134+00:00 | 7,136 | 4,793 | 4,777 |
| `ebcdea34464b9090e7734ca543be8733d39fc20a` | 2026-09-17T22:21:57.200360+00:00 | 7,135 | 4,794 | 4,778 |
| `580805487b22006c6f2fa35490c3edc8a5760d73` | 2026-09-16T22:23:02.757794+00:00 | 7,125 | 4,795 | 4,779 |
| `442db489342660d7588d16dcc18e6c126187c1e6` | 2026-09-15T22:23:17.742823+00:00 | 7,141 | 4,797 | 4,781 |
| `fbaed5cdc43a84755f61840ba9e1fc74379c797d` | 2026-09-14T22:24:50.953914+00:00 | 7,137 | 4,795 | 4,779 |
| `ece47f1e34ab4b795a79be7674355409ce5aaf8e` | 2026-09-11T22:22:44.126598+00:00 | 7,163 | 4,795 | 4,779 |
| `7380a97605c7f16eb902421486c491a95b957cd7` | 2026-09-11T21:08:04.147700+00:00 | 7,163 | 4,795 | 4,779 |
| `20e75f3ced2a0b71ade6f9c9cfe81de709365321` | 2026-09-11T05:28:43.908552+00:00 | 7,166 | 4,793 | 4,777 |
| `e6bbab7153d3abfb7c31d1ca91edd0888e6b53f4` | 2026-09-10T22:22:06.760496+00:00 | 7,166 | 4,793 | 4,777 |
| `a7474d5b6731c7d833e34035e9244556901c3e2b` | 2026-09-10T04:16:12.067354+00:00 | 7,139 | 4,793 | 4,777 |
| `8601f59f4c1d85f70b41484f4f228b0933027801` | 2026-09-09T03:03:31.963823+00:00 | 7,128 | 4,795 | 4,779 |

Every snapshot has exactly the same 16 new exclusions. `admitted` decreases by
16 and `blank check company` increases by 16; every other count is unchanged.
There are no added admissions, seed losses, capacity cuts or reclassified
preexisting exclusions. Every before/after selection ledger conserves membership.
All old admitted symbols outside this named set remain admitted.

Each newly excluded name was inspected. Every one has an explicit acquisition
corporation legal ending followed by its share label; none relies on its
operating-industry label or its generic capital/investment vocabulary. The exact
name/industry pairs below are identical in all 13 retained snapshots. No
ambiguous operating-company name is included under this bounded contract; no
broader current-security-status claim is made.

| Symbol | Newly excluded retained name | Misleading industry label |
|---|---|---|
| AAC | Ares Acquisition Corporation III Class A Ordinary Shares | Metal Fabrications |
| BKHA | Black Hawk Acquisition Corporation Class A Ordinary Shares | Biotechnology: Biological Products (No Diagnostic Substances) |
| EGHA | EGH Acquisition Corp. Class A Ordinary Shares | Finance/Investors Services |
| EMIS | Emmis Acquisition Corp. Class A Ordinary Shares | Biotechnology: Pharmaceutical Preparations |
| EVAC | EQV Ventures Acquisition Corp. II Class A Ordinary Shares | Fluid Controls |
| HCAC | Hall Chadwick Acquisition Corp Class A Ordinary Shares | Auto Parts:O.E.M. |
| HCMA | HCM III Acquisition Corp. Class A Ordinary Share | Hotels/Resorts |
| IPEX | Inflection Point Acquisition Corp. V Class A Ordinary Shares | Biotechnology: Pharmaceutical Preparations |
| KTWO | K2 Capital Acquisition Corporation Class A Ordinary Share | Medical/Dental Instruments |
| MCGA | Yorkville Acquisition Corp. Class A Ordinary Share | Electric Utilities: Central |
| MTAL | Metals Acquisition Corp. II Class A Ordinary Shares | Metal Mining |
| PAAC | Proem Acquisition Corp I Ordinary Shares | Investment Managers |
| SIMA | SIM Acquisition Corp. I Class A Ordinary Shares | Industrial Machinery/Components |
| SOUL | Soulpower Acquisition Corporation Class A Ordinary Shares | Publishing |
| VACI | Viking Acquisition Corp. I Class A Ordinary Shares | Telecommunications Equipment |
| WSTN | Westin Acquisition Corp Class A Ordinary Share | EDP Services |

The eight-row investigation sample changes only BKHA, EGHA and HCMA (8 → 5).
ANTA, BLIV, BMHL, GDEV and INTJ remain admitted under the same contract.
No seed occurs in the 16-name new-exclusion set. The current retained directory
is still SHA-256 `b9f52226e0ad33d77240c6821d5053a5d902af011f3c1cdf04becee9a800ecc4`;
the base seed bytes are SHA-256 `ff905018446fe42b0167c8d728e70bcdc803e1fbb5511a45ee71adfb0ec19971`.
Neither file was rewritten. The sweep is reproducible from retained Git objects;
its output is review evidence, not a production directory refresh.

## Verification and handoff

Local runtime: Linux, Python 3.12.14, pytest 9.1.1, pandas 3.0.6,
NumPy 2.5.3, exchange_calendars 4.13.2, alpaca-py 0.44.0.
All Python test network boundaries are blocked by `tests/conftest.py`.
Fixture generation/checks use the existing pipeline doubles and temporary output.
Final executed test totals and exact-head CI results are recorded in the PR
and CLAUDE.md checkpoint. No fixture population or expectation needs changing;
the only mechanical count update is the handoff's suite count (1,398 → 1,423).

Executed local Python gates: 229 focused universe, stale-investigation,
input-retention, input-conservation and pipeline tests passed; the full normal
suite passed **1,423 tests**; `tools/make_fixture.py --check` reported **12
fixtures current**. `git diff --check` passed. The initial full-suite attempt
had 1,419 passes and four SDK-construction failures because this sandbox's SOCKS
proxy needs the optional `socksio` package. Installing it in the local test
environment resolved all four without changing source, tests or repository
requirements. Browser dependencies likewise belong only to the local environment.

README now states the bounded rule. `.env.example` was reviewed and remains
accurate: no configuration changed. The historical investigation and its JSON
results are unchanged; its pinned diagnostic must still run against its pinned
source revision, not the corrected classifier. No production/history/evidence,
website, mobile/chart/Focus/Restore, email, shared-design, workflow, secret,
setting, schedule, provider transport, fetch window, scan or model change is
included. No live provider/model/scan/publication action occurred.

- **KEEP:** stale/unknown inputs, degraded coverage, complete accounting, seed
  overrides, warnings, existing strategy and interface behavior.
- **FIX NOW:** the exact-industry dependence for narrowly identifiable
  acquisition-corporation legal names, with transparent exclusions before fetch.
- **DEFER:** provider root causes, broader security-master classification and
  observation of any future already-authorized production run.
- **OMIT:** missing-bar suppression, inferred provider causes, retrospective
  record edits, generic shell heuristics, unrelated cleanup, live calls,
  workflow dispatch/rerun, directory refresh, email, manual publication and merge.

Exact next action: guidance independently reviews the one focused PR and its
completed exact-head checks, then owns any normal clean merge. Astra stops.
