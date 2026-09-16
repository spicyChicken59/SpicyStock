# Reaction discovery: dated source contract

Contract revision: **reaction-discovery-sources-v1**, inspected **2026-09-16**.
Implementation baseline: `660e9beefd1125203628f8a162ddae4d6f3c3549`.
This is the source contract for reaction discovery; `src/scans.py` executes
the rules and `src/discovery.py` records their admission decision.

## Decision and source hierarchy

**Outcome A: primary Dollar formula verified; no formula change.** The public
text of Bonde's dated posts was inspected, not just search snippets. The
existing Dollar predicate matches his July 13, 2017 version. The field guide's
community table did not establish this attribution; the primary posts do.

Use this hierarchy: **PRIMARY** (Bonde's own publication), **LATER BONDE**
(a later dated statement by him, still primary authorship), **COMMUNITY**
(someone else's translation), **IMPLEMENTATION** (SpicyStock's operational
choice), then **EMPIRICAL** (outcome evidence). No empirical result selects
either formula here. A later date alone does not establish a universal
replacement for every earlier scan.

## Selected formula mapping

These are exact source predicates, before SpicyStock's numeric normalization.
Dates identify the inspected publication, not a claimed first invention date
or a guarantee of today's member-only practice. `c` is the evaluated bar's
close/current price, `o` its open, `c1` the previous session's close, `v` its
volume in shares, and `v1` the previous session's volume.

| Route | Classification | Source date | Source predicate | Evidence |
| --- | --- | --- | --- | --- |
| burst | PRIMARY | 2015-05-21 | `c/c1>=1.04 and v>v1 and v>=100000` | [P15] |
| dollar | PRIMARY | 2017-07-13 | `c-o>=.90 and v>100000` | [L17] |

**PRIMARY — Dollar details:** [L17]'s reference is the open, the minimum
body is $0.90 inclusive, and current volume must exceed 100,000 shares.
Neither prior/average volume, a close-near-high test, a +4% test nor a price
floor is in that predicate. Its above-$40 discussion is context, not another
term. The near-high criterion follows discovery in its setup review.

**LATER BONDE — dated variants, not a timeless formula:** [P16]'s bullish
Dollar PCF uses `c-o>=.90 and v>=100000`; [L17] changes the printed volume
comparison to strict `>`. The posts establish that difference, not its
motivation or a formal deprecation policy. [P16] also prints an optional
bullish/bearish combination with `c>=30`; it is not a universal bullish floor.
[P16] mentions an optional prior-negative-day restriction and says he does
not use it. None is imported here. For 4%, [P16] repeats [P15]'s inclusive
floor, while [L17] prints `v>100000`. SpicyStock retains the selected 2015
burst version and 2017 Dollar version; it does not silently unify them.

## Exact SpicyStock operation

**IMPLEMENTATION — normalization:** `_bars()` rounds prices to two decimal
places and volume to whole shares using NumPy rounding. `_close_to_close()`
rounds the close/prior-close ratio to four places before comparing it with
1.04; it compares current and prior whole-share volumes. `_dollar()` rounds
the difference of the already rounded close and open to cents, then checks
`move >= 0.90 and volume > 100000`. Python `round` rounds the difference and
ratio. These precision choices are not specified by the primary PCFs. Thus
a raw $0.8999 body can qualify after normalization; this is not a claim of
bit-for-bit TC2000 equivalence. Unreadable required inputs cannot admit a row.

**IMPLEMENTATION — measurements and admission:** `volume_vs_prior` and
`close_pos_in_range` are recorded Dollar context, not extra admission tests.
The scanner itself has no $30/$40 floor. The separate universe policy uses
the cent-rounded session close >= $3, with seed/explicit exceptions and the
existing coverage/capacity ledger. It is not a term in either selected PCF.
Provider split adjustment, completed-session timing and data validity remain
the input contract from #69–#70. Bonde describes intraday scanning; this
repository evaluates completed daily bars. It does not reproduce his timing.

**IMPLEMENTATION — identity:** a burst-only match is `burst`, a Dollar-only
match is `dollar`, and a match on both is `both`. Discovery v1 retains the
applicable and inapplicable rules and measured inputs. A Dollar candidate
below +4% remains legitimate; its route alone cannot improve or lower quality.

## Layers after discovery

| Layer | Classification and boundary |
| --- | --- |
| A-quality | PRIMARY concept: [Q14] reviews candidates after either scan. Near-high close, range/volume context and consolidation belong here. IMPLEMENTATION: numeric proxies, score weights, mechanical grade and down-only chart-reader handling stay in `quality.py`/`grader.py`; this research does not re-certify every quality threshold. |
| Breadth | IMPLEMENTATION action gate in `breadth.py`/`pipeline.py`, separately source-discussed in [method.md](method.md). It can withhold a ticket without undoing discovery or rewriting a grade. No breadth threshold is validated or changed by this milestone. |
| Entry/plan | IMPLEMENTATION execution model in `plan.py`, separately source-discussed in [method.md](method.md). Entry timing, risk, stops and ticket limits are not discovery conditions. |
| Anticipation / EP / EP9M | Separate setup families, outside this reaction contract. Neither their admission rules nor EP9M outcome studies establish reaction admission or profitability. |

## Community discrepancy

**COMMUNITY:** [C22]'s author description uses prior-close dollar change
strictly greater than $0.90, a close within 30% of the high, and no volume
test. The public description was inspected; the underlying Pine source was
not retrieved. It differs from the selected primary predicate on reference,
boundary and filters. The field guide reports the same family of ports.
Neither that table nor the script's title is authority to replace Bonde's
dated formula. No TradingView/GitHub threshold was promoted to PRIMARY.

## Evidence register and limits

All access statuses below refer to 2026-09-16. The links and section names
let a reviewer inspect each claim independently; no inaccessible text is
treated as inspected.

- **PRIMARY [P15]:** Pradeep Bonde, May 21, 2015, [How do stock move on 3 to
  5 day time frame][P15]. Text inspected, especially the 4% scan section and
  the explanation of dollar-based expansion in higher-priced names.
- **PRIMARY [P16]:** Bonde, September 20, 2016, [How I scan for swing trade
  ideas][P16]. Text inspected: Telechart/PCF definitions, bullish 4%, bullish
  Dollar, and separately labelled combination/price-filter variants.
- **LATER BONDE [L17]:** Bonde, July 13, 2017, [My process loop to trade 4%
  b/o and $ b/o][L17]. Text inspected: both scan sections and their subsequent
  setup lists. This is the selected primary Dollar version.
- **PRIMARY [Q14]:** Bonde, January 14, 2014, [How to identify the A quality
  setup][Q14]. Text inspected; example chart images not inspected.
- **PRIMARY, supporting concept only:** Bonde, January 4, 2014,
  [How to Identify good momentum burst and make millions][P14]. Article text
  inspected. No exact Dollar formula attribution is based on search snippets
  or reader comments associated with this page.
- **COMMUNITY [C22]:** lukebrod, May 29, 2022, [StockBee MB Bullish][C22].
  Description inspected; not Bonde authorship and not a Pine-code audit.
- **SECONDARY research aid:** the supplied *Stockbee AQuality Setup and
  Momentum Burst Method: A Complete Field Guide*, 16 pages, especially the
  scan table/platform discrepancies and access caveats. Consulted, not used
  as primary proof or empirical evidence for these rules.

Unavailable or only partially inspected:

- Bonde's [November 18, 2015 4% post][U15]: search excerpt retrieved; full
  page open returned an error. Not needed for the selected mapping.
- Bonde's [July 5, 2017 video post][V17]: dated landing page inspected;
  embedded video/transcript not inspected. No formula inferred from its title.
- [Bonde's X thread][X24] supplied by the field guide: fetch returned 403.
  Later replies/clarifications remain unverified; none changes this contract.
- [The Trend Intensity Breakout Setup][W12], Wiley chapter 26: publisher
  metadata and public summary inspected (publication date January 2, 2012).
  Full chapter not retrieved. No exact Dollar rule inferred from the summary.
- [Official Stockbee membership][MEMBERS]: member formulas, bootcamp/model
  books and current refinements not accessed; no login or purchase attempted.
  No claim that the selected 2017 formula is his latest or only version.

## Versioning and historical immutability

**IMPLEMENTATION:** this revision adds source documentation and corrects
presentation only. No executable predicate, constant, grader prompt, serialized
discovery field or provenance payload changes. `rules_version`, discovery v1,
provenance v1 and existing evidence IDs therefore stay unchanged for identical
inputs. The source-contract revision is a documentation identity, not a new
runtime rules version; it is not backfilled into old publications.

A future formula change must change archived `RULES` and hence `rules_version`
and evidence identity, update this dated mapping, and retain a compatible
verifier for older rules. A future attribution-only revision must explicitly
state whether it changes runtime metadata. Neither permits rewriting historical
grades. September 11/14 publications, audit fixtures, picks, recovery and
retained provenance objects remain byte-for-byte immutable here.

[P14]: https://stockbee.blogspot.com/2014/01/how-to-identify-good-momentum-burst-and.html
[Q14]: https://stockbee.blogspot.com/2014/01/how-to-identify-a-quality-setup.html
[P15]: https://stockbee.blogspot.com/2015/05/how-do-stock-move-on-3-to-5-day-time.html
[P16]: https://stockbee.blogspot.com/2016/09/how-i-scan-for-swing-trade-ideas.html
[L17]: https://stockbee.blogspot.com/2017/07/my-process-loop-to-trade-4-bo-and-bo.html
[C22]: https://www.tradingview.com/script/Rf67M40u-StockBee-MB-Bullish/
[U15]: https://stockbee.blogspot.com/2015/11/how-to-use-4-breakout-scan-to-make-money.html
[V17]: https://stockbee.blogspot.com/2017/07/how-to-use-4-and-bo-scan-to-make-money.html
[X24]: https://x.com/PradeepBonde/status/1839255631363965192
[W12]: https://onlinelibrary.wiley.com/doi/10.1002/9781119202516.ch26
[MEMBERS]: https://stockbee.biz/
