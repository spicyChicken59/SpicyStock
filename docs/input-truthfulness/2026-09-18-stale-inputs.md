# September 18, 2026: retained stale-input investigation

Investigated September 19, 2026. Scope: evidence, a read-only diagnostic, and its failure controls. Production behavior is unchanged. This is a bounded diagnosis, not a trading-edge assessment or a new provider investigation.

**Verdict:** the run classified 19 normalized frames as stale because their latest date was September 17 rather than the expected September 18 session. They remained unmeasured. The original reason for their absent September 18 bars is **unresolved**. A separate, reproducible classification limitation admits three sampled acquisition companies when the directory supplies operating-industry labels. This does not establish that classification caused their missing bars.

## Evidence chain and integrity

| Object | Verified identity and relationship |
|---|---|
| Investigation base/current main | `3f4b3312c136104f0c187dd495e4c8e035bd48e1`; tree `c1a4b329eca236b60cbf896403278c2f5e765eab`. Zero open PRs and no existing stale-investigation branch at initial check. |
| Historical execution | [Run 35401227388](https://github.com/spicyChicken59/SpicyStock/actions/runs/35401227388), scheduled attempt 1; [scan job 105781334731](https://github.com/spicyChicken59/SpicyStock/actions/runs/35401227388/job/105781334731). Actual checkout log at 22:22:14.217 UTC confirms `ebcdea34464b9090e7734ca543be8733d39fc20a`, matching workflow metadata. |
| Historical publication | [Commit 8387ccedae22fbf30ddebdb6f52e1e42326a7ec5](https://github.com/spicyChicken59/SpicyStock/commit/8387ccedae22fbf30ddebdb6f52e1e42326a7ec5), parent `ebcdea34464b9090e7734ca543be8733d39fc20a`. Commit at 22:26:07 UTC, push recorded 22:26:11 UTC. |
| Original artifact | [evening-2026-09-18-35401227388](https://github.com/spicyChicken59/SpicyStock/actions/runs/35401227388/artifacts/10570901548), ID 10570901548, 15,642,262 bytes. Created 22:26:15 UTC; listed unexpired, expires October 18 at 22:26:12 UTC. Downloaded ZIP hash agrees with artifact metadata and upload log. |
| Raw publication | ZIP member `data.json`, 5,122,264 bytes. Its SHA-256 exactly matches Tahir's supplied value below. It was read as bytes, not reserialized. |
| Recovery context | ZIP member `history/bf36144ea45d7c74eee724d2557964e5e8e0bfc5/record.json`, 37,223 bytes. Its parsed `run` equals the publication's `run`. It is a context subset, not another serialization of the full publication. |
| Archive identifier | `bf36144ea45d7c74eee724d2557964e5e8e0bfc5` is SHA-1 of the Git blob header plus original `data.json` bytes. It is not the workflow head or a publication commit. Recovery provenance's commit field is null. |
| Directory | [docs/universe-directory.json.gz at publication](https://github.com/spicyChicken59/SpicyStock/blob/8387ccedae22fbf30ddebdb6f52e1e42326a7ec5/docs/universe-directory.json.gz), 204,562 bytes, Git blob `67f56c55c733786d49b8c7c4b22542390f262944`; identical blob on investigation base. It is **outside the ZIP**. Schema 1, 7,136 rows, timestamp `2026-09-18T22:22:34.176134+00:00`; recorded canonical fingerprint matches. This timestamp is assigned from the run's pinned clock, not an independently timed completed response. |

SHA-256 pins:

- Artifact ZIP: `d95f9f2c852bb5901ee7a022ef606f30745d785350665dbc2edadb93a27e2352`.
- Original data.json: `aae64bbd1be0c0126f9c24c6ad5b4b5be1434a51e7351e5085c2f00862215567`.
- Historical record.json: `f97c1cf83e120e8d694e4bcbc704744cebbadccd76f2bdea93f785564847ef80`.
- Directory gzip bytes: `a58e9d566751bb95a600d0fc723746fa04ddad719e9c51f34c09b5790bd30df9`.
- Canonical directory fields: `c091d29f6be7b2833cc3b017b655470ebd187507ab59adde597e450d8d20488f`.

**PASS:** hashes before and after offline investigation agree. The ZIP has 3,687 entries: data.json and picks.json; 12 charts; 1,134 evidence objects (1,097 frame JSON gzip objects, one system-text gzip object, 36 PNGs); 2,539 history files. The diagnostic hashes every member into a sorted manifest fingerprint. Large evidence files are referenced, not committed again.

The artifact preserves publication/recovery ledgers, candidate receipts and selected normalized source frames. It does not contain the directory, raw HTTP pages, wire request parameters, provider symbol-master responses, a complete returned-frame map, or a full stale-name list. Content-addressed frame objects do not themselves identify tickers. No sampled symbol has an entry in the retained history catalog, and publication inspection found no attributable OHLCV for these eight. Candidate-only capture is downstream of readiness and matching; it is not a whole-universe bar archive.

**BLOCKED — full stale membership:** the other 11 are not individually identified. `universe.population` sorts unique names and retains count, `identity`, and first eight names. `identity` is the first 16 hexadecimal characters of SHA-256 over newline-joined sorted symbols. The retained stale identity `c0c17644c58c108f` cannot recover missing names; it has not been independently recomputed from all 19. No names were guessed.

**PASS — intended selection replay:** the retained directory and unchanged seed reproduce 4,793 intended stocks, the complete recorded selection ledger/counts, and stock identity `8ffa5412211516cc`. Adding SPY reproduces fetch identity `7a482668c029577e`. This reconstructs intended membership, not individual stale/ready membership.

## Recorded populations

| Accounting boundary | Retained observation |
|---|---|
| Stock coverage | 4,774 usable / 4,793 intended; 19 stale; 99.6036% ready; degraded |
| Fetch including SPY | 4,794 intended = requested = with bars; 19 stale + 4,775 on-session |
| Current/prior validation | 4,775 session-ready; zero gapped/unreadable; previous XNYS session September 17 |
| Before scans | 4,775 = one benchmark + 1,043 actual-session-price exclusions + 3,731 scan-ready |
| Measurement | 3,731 measured; 78 burst-only + 218 dollar-only + 64 both + 3,371 neither |
| Matched/quality | 360 matches; 360 quality successes, zero quality errors |
| Reader | 12 requested / 12 completed, according to retained ledger and workflow |
| Other omissions | Zero fetch-budget/failure omissions, capacity cuts, no-bar histories, permanent refusals, scan errors, unattempted scans, or repaired duplicates |
| Transport diagnostics | 1,343,073 normalized returned bars; 48 SDK batch attempts, **not** 48 HTTP pages |

The last-date distribution is 19 frames on September 17 and 4,775 on September 18. The job warning at 22:23:28.336 UTC explicitly names all eight sampled symbols and their September 17 last dates. The initial and final coverage logs occur at 22:23:42.636 and 22:25:43.914 UTC.

`inputs.record_faults(run)` returns no faults. Complete evaluation of 3,731 scan-ready names coexists with incomplete intended coverage. Nineteen stale stocks do not belong in 3,371 measured non-matches. The unchanged publication minimum is 50% of intended stocks, excluding SPY; exceeding it permits degraded publication, not complete coverage.

## Historical code path and comparison

These links pin the code that actually ran. Recursive Git-tree comparison against investigation base confirms all `src/`, `knowledge/`, workflows, requirements and seed bytes unchanged. Of the relevant existing tests, `tests/test_pipeline.py` changed only to give a Saturday-sensitive fixture its intended session clock. Later website work does not alter this diagnosis.

1. [universe.py](https://github.com/spicyChicken59/SpicyStock/blob/ebcdea34464b9090e7734ca543be8733d39fc20a/src/universe.py): `build` uses the live directory here; cache/seed fallbacks were not used. `classify` checks symbol format, common/ordinary-share wording, rejected security wording, nonempty sector/industry and exact lowercased industry `blank checks`. Seed membership bypasses classification. `admit` keeps the first duplicate row, records exceptions and applies a capacity rank only above 8,000. No directory price/volume gate applies. All eight were ordinary admissions, none seed exceptions; capacity did not bind.
2. [pipeline.py](https://github.com/spicyChicken59/SpicyStock/blob/ebcdea34464b9090e7734ca543be8733d39fc20a/src/pipeline.py): `run_evening` pins its clock, resolves September 18, passes the sorted intended symbols and SPY to `fetch_universe`. Application mapping is identity: ANTA→ANTA, BKHA→BKHA, BLIV→BLIV, BMHL→BMHL, EGHA→EGHA, GDEV→GDEV, HCMA→HCMA, INTJ→INTJ. This is established from replay and code, not a retained wire payload or provider entity mapping.
3. [market_data.py](https://github.com/spicyChicken59/SpicyStock/blob/ebcdea34464b9090e7734ca543be8733d39fc20a/src/market_data.py): `fetch_universe` uses 500-symbol chunks and a 900-second budget; `download_bars` uses 100-symbol SDK batches with one retry after three seconds. `_download_batch` requests daily SIP, split adjustment, and a 260-session target converted to a 416-calendar-day lookback. Reconstructed start is July 29, 2025 00:00 UTC. End is the lesser of September 18 23:59:59 UTC and pinned now minus 16 minutes: September 18 22:06:34.176134 UTC (18:06:34 Eastern). Exact on-wire timestamps were not retained.
4. The installed run log identifies alpaca-py 0.44.0. Offline inspection of the same installed version shows `StockHistoricalDataClient.get_stock_bars` calling `_get_marketdata` with 10,000-bar pages, appending symbol lists while `next_page_token` remains. Application requests set no explicit `asof`, `sort` or `limit`. The documented endpoint has symbol-first results, a total-per-page limit, and server-side historical symbol mapping by as-of date. Neither page sequence nor provider mapping registry is retained. SDK support is not proof of the historical HTTP exchange. [Provider endpoint documentation][P2]
5. `_download_batch` selects exact requested labels from `BarSet.df`, sorts timestamps stably, keeps the last duplicate timestamp, removes wholly null rows, and renames OHLCV fields. `last_bar_date` reads the last normalized timestamp's date. `drop_stale` removes a frame unless that date equals the expected session. `drop_gapped`/`readable_pair` then require current and prior XNYS bars with finite positive OHLC, nonnegative volume and valid geometry. The ledger reports no duplicate repair, gap or unreadable-current-pair issue; it does not preserve raw timestamps/null rows for the stale eight.
6. [inputs.py](https://github.com/spicyChicken59/SpicyStock/blob/ebcdea34464b9090e7734ca543be8733d39fc20a/src/inputs.py): `build` separates stock readiness from benchmark transport. The pipeline then applies `universe.session_eligible` to actual cent-rounded closes (ordinary $3 floor with existing exceptions), scans, grades and reconciles `faults`/`evaluated`/`record_faults`. BLIV/INTJ directory quotes below $3 do not retroactively remove either from the intended denominator.
7. [provenance.py](https://github.com/spicyChicken59/SpicyStock/blob/ebcdea34464b9090e7734ca543be8733d39fc20a/src/provenance.py) captures matched/selected ready candidates, not stale frames. Publication validation enforces conservation. [history.py](https://github.com/spicyChicken59/SpicyStock/blob/ebcdea34464b9090e7734ca543be8733d39fc20a/src/history.py), `git_blob`/`publish`, explains the archive identifier and context subset.

## Eight-security dated evidence table

Identity below is the September 18 directory identity, cross-checked against the cited dated issuer/exchange filings. It is not certification of a complete point-in-time security master through September 18. No sampled row has independently verified September 18 provider entity/status evidence.

Common to **every row**: exact application request symbol equals the first column; last normalized date is **2026-09-17, as recorded in the workflow warning**. Original sampled frames are absent, so **OHLC in USD/share, volume in shares and raw timestamps are unavailable**. Directory last-sale strings are USD/share; the volume column below is a raw directory field whose reporting interval and trade-condition basis were not retained. Neither is a replacement for the Alpaca bar.

| Symbol; retained issuer/security name | Retained country; sector / industry; quote fields | Dated identity, venue and transitions | Conclusion and missing evidence |
|---|---|---|---|
| ANTA — Antalpha Platform Holding Company Class A Ordinary Shares | Singapore; Finance / Investment Bankers/Brokers/Service; $3.31; volume 426 | July 29, 2026 F-3/A describes Class A ordinary shares, $0.001 par, ANTA on Nasdaq Global Market [A1]. May 14, 2025 IPO notice expected trading that day [A2]. Nasdaq tier wording differs in the April annual report; do not infer a tier-transition date. | **Unresolved cause.** Identity is corroborated; no dated September 18 halt, inactive state or aggregation failure is established. Need M1/M2/M3 below for ANTA. |
| BKHA — Black Hawk Acquisition Corporation Class A Ordinary Shares | United States; Health Care / Biotechnology: Biological Products (No Diagnostic Substances); $11.99; volume 162 | July 15, 2026 10-Q for May 31 describes a blank-check company; cover says ordinary shares BKHA, with units/rights separately identified. A March 31 listing-value deficiency had a September 28 cure deadline and did not immediately delist the securities [B1]. September 4 S-4/A index identifies Black Hawk and Vesicor; full filing retrieval was blocked [B2]. | **Supported classification lead; unresolved bar cause.** Directory's Class A label is not independently settled by the 10-Q cover's less specific label. Need M1/M2 plus completed-transaction and effective-security mapping evidence through September 18 (M3); a proposed deal/deficiency proves neither halt nor completed transition. |
| BLIV — BeLive Holdings Ordinary Share | Singapore; Technology / EDP Services; $2.21; volume 91 | May 15, 2026 20-F identifies ordinary shares, $0.0005 par, Nasdaq Capital Market, trading beginning April 7, 2025, CUSIP G09675102 [L1]. | **Unresolved cause.** Small directory volume is only a lead; it cannot distinguish no eligible trades from absent provider data. Need BLIV M1/M2/M3. |
| BMHL — Bluemount Holdings Limited Class B Ordinary Shares | Hong Kong; Finance / Finance: Consumer Services; $5.53; volume 794 | June 29, 2026 20-F for March 31 identifies Class B ordinary shares, $0.0001 par, Nasdaq Capital Market; trading began July 11, 2025 [M1]. | **Unresolved cause.** No established September 18 halt/transition or absent-trade explanation. Need BMHL M1/M2/M3. |
| EGHA — EGH Acquisition Corp. Class A Ordinary Shares | United States; Finance / Finance/Investors Services; $10.40; volume 132 | August 12, 2026 10-Q describes a blank-check company [E1]. September 2 8-K (report date August 28) distinguishes Class A EGHA from EGHAU units and EGHAR rights on Nasdaq, and still discusses a proposed Hecate combination [E2]. | **Supported classification lead; unresolved bar cause.** Announced transaction is not completed symbol conversion. Need M1/M2 and any effective closing/listing transition after these filings through September 18 (M3). |
| GDEV — GDEV Inc. Ordinary Shares | Cyprus; Technology / EDP Services; $11.47; volume 749 | Nasdaq's August 27, 2024 notice made a 1-for-10 reverse split effective August 29, CUSIP G6529J209 [G1]. August 31, 2026 issuer tender filing identifies no-par ordinary GDEV on Nasdaq Global Market; offer scheduled to expire September 28, continued listing expected. It separately reports **GDEVW warrants** expired/delisted August 26 [G2]. | **Unresolved cause.** Warrant delisting does not establish ordinary-share delisting; tender offer does not establish a halt. Need GDEV ordinary-share M1/M2/M3, including provider corporate-action mapping. |
| HCMA — HCM III Acquisition Corp. Class A Ordinary Share | United States; Consumer Discretionary / Hotels/Resorts; $10.32; volume 127 | August 14, 2026 10-Q identifies HCM **III**, incorporated April 15, 2025, Class A HCMA on Nasdaq, separate HCMAU units/HCMAW warrants, blank-check status and no operating business as of June 30. Unit IPO closed August 4, 2025 [H1]. Separate-share trading commencement was not independently pinned. | **Supported classification lead; unresolved bar cause.** Do not substitute a previous issuer associated with this ticker. Need M1/M2 and HCM III security identifiers/effective separate-trading or later combination events through September 18 (M3). |
| INTJ — Intelligent Group Limited Class A Ordinary Shares | Hong Kong; Consumer Discretionary / Professional Services; $2.66; volume 181 | February 9, 2026 6-K gives final 1-for-20 reverse split effective February 17 at 00:01 Eastern, trading on split basis that morning; Class A, Nasdaq Capital Market, symbol INTJ unchanged, new CUSIP G48047115 [I1]. Earlier anticipated February 4 timing is superseded. | **Unresolved cause.** The dated split is a mapping/adjustment lead, not evidence it caused a September gap. Need INTJ M1/M2/M3 covering that action and any subsequent effective transition. |

Every row was admitted because its security wording matched, sector/industry were populated, and industry was not exactly `blank checks`. No row used a seed exception. All remain in this historical run's denominator.

Missing-evidence keys (these are evidence requirements, **not permission or a plan to make new calls**):

- **M1 — original transport and normalization:** the September 18 run's exact request symbols/parameters, all responses and pagination tokens through completion, and before/after normalization frames with timezone-aware timestamps for the named security. This distinguishes an absent server bar, an incomplete page/label mapping, and an application normalization loss. A new historical response could be revised and cannot recreate the original response.
- **M2 — aggregation eligibility:** condition-coded September 18 SIP trades/corrections and provider aggregation disposition at the original cutoff, for the exact class/entity. This distinguishes no trades, trades that do not establish OHLC, and provider omission. Directory volume alone cannot do so.
- **M3 — security state:** dated exchange/corporate-action notices and provider asset/entity mapping effective September 18, including halt/resumption or conversion times, if any. The eight securities' current identities alone are insufficient.
- For the unnamed eleven, the original full stale-membership list or complete frame map is needed before symbol-specific investigation. The digest is only a consistency check after such evidence is recovered.

## Provider mechanisms and bounded verdict

Alpaca documents daily aggregation on the New York day. Trade conditions affect open/close, high/low and volume separately; odd lots can update volume without establishing OHLC. The provider describes cases with no emitted bar when no trades occur or eligible OHLC values are absent. This allows an exchange-listed security with reported activity to lack a usable daily bar. It does not prove that occurred here. SIP is a consolidated feed, not IEX-only coverage. [Official FAQ][P1]

Split adjustment changes price and volume history; it does not authorize filling missing sessions. The historical endpoint supports as-of entity mapping, and defaults can matter when symbols change. This run did not explicitly pin `asof`; without the original response and provider entity mapping, a mapping defect is neither demonstrated nor excluded. [Endpoint reference][P2]

**Established application explanation:** the retained ledger and per-symbol warning agree with `drop_stale`. No historical ingestion, pagination, timezone, adjustment or measurement-accounting defect is demonstrated. Legitimate absent-bar circumstances remain possible; they are not proven for any sampled security. Unknowns stay unknown.

**Concrete classification limitation:** using the exact retained BKHA/EGHA/HCMA rows, `universe.classify(row, set())` returns admission. Changing only a copied row's industry to `Blank Checks` returns `blank check company`. These are deterministic offline results in [the diagnostic output](2026-09-18-stale-inputs-results.json), not observations of provider behavior. Dated filings conflict with the economic interpretation of the directory's operating-industry labels. The code implements its documented approximation; relying on that label alone cannot enforce a real-world blank-check exclusion.

A narrowly proposed future correction is a separately reviewed, dated security-classification exception/identity contract for confirmed shells, with evidence effective dates, seed precedence and completed-combination handling. Validate any September 18-effective identities before choosing exclusions. Do not blacklist every name containing “Acquisition,” change the historical denominator, or claim such a correction would supply the missing bars. No production correction is included.

## Reproduction and checks

From the PR checkout with existing development dependencies installed, point only to the **already retained** original files:

```text
python tools/investigate_stale_inputs.py --artifact /path/to/evening-2026-09-18-35401227388.zip --directory /path/to/universe-directory.json.gz
python -m pytest tests/test_stale_investigation.py tests/test_universe.py tests/test_market_data.py -q
python -m pytest tests/test_inputs.py tests/test_pipeline.py -q
```

The diagnostic disables socket connections, opens files read-only, extracts nothing, validates original-byte hashes and pinned source blobs, replays classification, reconciles the ledger and rechecks input hashes. It prints JSON. [Committed results](2026-09-18-stale-inputs-results.json) came from these original files, not regenerated market data. The new tests deliberately reject a wrong artifact and equivalent-but-reserialized JSON and verify unchanged failure-control inputs.

| Check | Result and limit |
|---|---|
| Original ZIP/data/record/directory hashes, all-member manifest, before/after integrity | **PASS**, on investigation base plus this diagnostic. No evidence bytes rewritten. |
| Selection replay and recorded coverage conservation | **PASS**; original retained data and unchanged historical/current classifiers. Does not validate each underlying trade. |
| New failure controls plus existing universe/market-data suites | **PASS**, 210 tests (4 new + 206 existing), Windows Python 3.12.14. |
| Existing input/pipeline suites | **FAIL**, 25 failed / 49 passed on unchanged base source. `provenance.write_objects` replaces a still-open `NamedTemporaryFile`; Windows raises WinError 32 during fixture publication, causing downstream missing-record failures. No source/test weakening or portability fix made. |
| Local runtime parity | **BLOCKED** for exact replication: alpaca-py 0.44.0 and exchange-calendars 4.13.2 match the run; local pandas 3.0.1/numpy 2.3.5 differ from run 3.0.6/2.5.3. Pytest 9.1.1; all external boundaries doubled/socket-blocked. |
| Full Linux/PR gates | **NOT RUN** when this report was committed; exact-head results belong in the PR description. Existing gates remain required. |
| New live provider/scan/model execution | **NOT RUN**; not authorized or needed for this bounded deliverable. |
| Real browser, visual screenshots, human usability | **NOT RUN**; production UI unchanged, no new visual acceptance claimed. |
| Production publication after this change | **NOT RUN**; this PR must stop for independent guidance review without merge. |

The initial local attempt also lacked some snapshot dependencies and used a GUI plotting backend. Missing reference files were fetched and Agg was selected before the reported final runs; the remaining 25 failures are the Windows publication issue above.

Workflow inspection: branch pushes run Secret Scan; PRs run existing offline Python, fixture/clean-tree and browser checks. Evening scan is schedule/dispatch only; intraday is dispatch only. This branch/PR does not trigger them. A later authorized merge touching this documentation under `docs/` can trigger the established committed-dashboard publication workflow; no manual dispatch or merge is performed here.

README and .env.example were reviewed; configuration is unchanged. Shared design remains installed at v2.13.0 / commit `14a752dd0269bd6ebbb7080eb0d9e1922cd1ef2c`; recursive Git-tree comparison shows no relevant installed-design drift between execution and investigation base. No upstream release, re-vendoring, UI or strategy work occurred. The supplied field guide was read as secondary synthesis alongside repository method/reaction contracts; it is not substituted for primary Stockbee source evidence.

## Source index

All public sources below were accessed September 19, 2026. Filing/report/effective dates are distinguished in the table. They support dated disclosures, not proof of original Alpaca responses or an exhaustive subsequent-event search.

- [A1 — Antalpha July 29, 2026 F-3/A][A1]; [A2 — issuer May 14, 2025 IPO announcement][A2].
- [B1 — Black Hawk July 15, 2026 10-Q, period May 31][B1]; [B2 — September 4 S-4/A filing index][B2]. **BLOCKED:** full S-4/A body retrieval; no closing conclusion inferred.
- [L1 — BeLive May 15, 2026 annual report][L1].
- [M1 — Bluemount June 29, 2026 annual report, period March 31][M1].
- [E1 — EGH August 12, 2026 quarterly report][E1]; [E2 — September 2 8-K, report date August 28][E2].
- [G1 — Nasdaq August 27, 2024 corporate-action notice][G1]; [G2 — August 31, 2026 GDEV tender offer][G2]; [filing date index](https://www.sec.gov/Archives/edgar/data/1848739/000110465926103543/0001104659-26-103543-index.htm). A large 2026 annual-report fetch and issuer PDF were unavailable; they are not relied on.
- [H1 — HCM III August 14, 2026 10-Q, period June 30][H1].
- [I1 — Intelligent Group February 9, 2026 final split notice][I1].
- [P1 — official Alpaca market-data FAQ][P1]; [P2 — official historical-stock-bars endpoint reference][P2]. Current documentation, not an archived September 18 provider contract.

[A1]: https://www.sec.gov/Archives/edgar/data/2044255/000121390026082852/ea0298675-f3a1_antalpha.htm
[A2]: https://ir.antalpha.com/news-releases/news-release-details/antalpha-announces-pricing-initial-public-offering
[B1]: https://www.sec.gov/Archives/edgar/data/2000775/000182912626007603/blackhawk_10q.htm
[B2]: https://www.sec.gov/Archives/edgar/data/2000775/000182912626009732/0001829126-26-009732-index.htm
[L1]: https://www.sec.gov/Archives/edgar/data/1982448/000149315226023306/form20-f.htm
[M1]: https://www.sec.gov/Archives/edgar/data/2027815/000117184326004360/f20f_062926.htm
[E1]: https://www.sec.gov/Archives/edgar/data/2052547/000110465926094861/egha-20260630x10q.htm
[E2]: https://www.sec.gov/Archives/edgar/data/2052547/000110465926104740/tm2624704d1_8k.htm
[G1]: https://www.nasdaqtrader.com/TraderNews.aspx?id=ECA2024-404
[G2]: https://www.sec.gov/Archives/edgar/data/1848739/000110465926103543/tm2624191d1_ex99-a1a.htm
[H1]: https://www.sec.gov/Archives/edgar/data/2069856/000121390026089673/ea0301529-10q_hcm3.htm
[I1]: https://www.sec.gov/Archives/edgar/data/1916416/000121390026013468/ea0276107-6k_intelligent.htm
[P1]: https://docs.alpaca.markets/us/docs/market-data-faq
[P2]: https://docs.alpaca.markets/us/reference/stockbars
