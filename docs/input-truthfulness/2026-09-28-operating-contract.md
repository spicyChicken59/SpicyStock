# Selected operating contract · historical-validation-v1 / reader request v2

This describes the implemented after-close reaction / next-session variant.
It is not an intraday day-one backtest, anticipation backtest or EP9M backtest.
Numeric discovery, quality, breadth, sizing, allocation and exit rules remain
those at `8be007f68deaa417b85a512d2e16a37899d27011`. The proposed request version
changes schema delivery, image coverage and instruction clarity; it does not
reuse historical replies as reviews of new requests. Each publication's full
rules digest and input/response hashes remain authoritative for that record.

## Information and decisions

| Step | Operational meaning | Attribution |
| --- | --- | --- |
| Reaction discovery | Completed split-adjusted daily bars: 4% close/previous-close gain, at least 100,000 shares and volume above prior; or Dollar close minus open ≥ $0.90 and volume > 100,000. Routes are alternatives. | PRIMARY Stockbee, dated 2015/2017; exact rounding and universe handling SPICYSTOCK DERIVED |
| Decision time | After the signal session is complete. Final high, low, close and volume are unavailable at that morning's open. | EMPIRICAL observation / temporal constraint |
| Selected entry | Next applicable XNYS session, first 30 minutes. Prepare a conditional buy stop-limit at the signal close, only within its recorded limit and conditions. | Next-morning route PRIMARY Stockbee 2015; exact ticket implementation SPICYSTOCK DERIVED |
| Quality | 2/L/Y/N/C/H weighted 1.5/2/1.5/1.5/2/1.5; partial gets half. RE/VOL have zero score weight but contribute to A+ count. Composite A+ also requires four A+ checks; 2 and H must pass for A/A+. Vetoes override the score. Missing measurements remain distinct. | Concepts PRIMARY Stockbee and LATER BONDE; weights, grade banding, proxies and necessary conditions SPICYSTOCK DERIVED |
| Ordinary C / A+ C | Ordinary C does not require both base volume ratios below one. Tighter ratios and lower-volume preferences are additional A+ criteria, not automatic ordinary-C failures. | See dated consolidation contract: primary length, LATER BONDE down-day allowance, SPICYSTOCK DERIVED ratios |
| Reader | Twelve candidates, mechanical grade then descending score then ticker; model default Sonnet 4.6, two application attempts, 4096 output tokens, 30-second timeout unchanged. Accepted evidence can only lower the mechanical grade. Missing or rejected review cannot authorize a reaction plan. | SPICYSTOCK DERIVED; no claim that ranking or judgments add edge |
| Market | Production breadth and recorded regime determine admission and size. RED prevents new longs; YELLOW admits only A+ at reduced size. | Source thresholds and local scaling identified in knowledge/method.md; implementation SPICYSTOCK DERIVED |
| Anticipation | Separate quiet/consolidating setup and trigger. Actual breakout timing and comparable intraday cumulative volume pace must be checked by the visitor against a timely source. | PRIMARY / LATER BONDE concepts; exact measurement proxies SPICYSTOCK DERIVED |

An A/A+ composite can coexist with RE/VOL failures. C partial credit can also
coexist with an A score. Neither the model prompt nor the product may call an
A label “all criteria passed.” A qualitative chart concern may disagree with
a proxy only within the versioned authority contract. Schema conformance checks
structure, not the truth of subjective chart judgments or alleged catalysts.

## Conditional ticket, sizing and cancellation

The stop candidates are the completed signal low and then the cent-rounded
signal midpoint. The maximum entry is the lesser of the outer close × 1.04
ceiling and floor-to-cents(stop / 0.96). A valid band requires stop < trigger <
limit; there must be executable cent-grid room. No invented maximum-width stop
rescues an infeasible bar. The indicative close-plus-1% entry is capped by the
limit and is neither a fill nor the sizing price. Production uses Python's
binary-float cent-rounding convention at price/midpoint boundaries; the POC's
independent Decimal equations preserve that established convention.

The fixed model defaults are $10,000 equity, 0.5% risk, 25% position cap and
four slots. Size is the smaller whole-share count allowed by worst-limit
price-to-stop risk and the position cap, then capacity/cash allocation applies.
Regime, hazard and stop-width multipliers reduce the budget. A zero-share
candidate is not executable. These assumptions are not Tahir's holdings or
personal capital. A stop-market price does not guarantee maximum loss.

The visitor must verify pre-open conditions, place any chosen order independently,
cancel an unfilled order at the recorded first-30-minute cutoff and cancel on
the recorded invalidating conditions. DAY duration does not itself implement
that early cancellation. A gap above the actual limit cannot fill at an allowed
price; the outer +4% extension ceiling is not permission to exceed a narrowed
limit. An open below the skip line invalidates entry even if price later rallies.
The site neither monitors these events nor places/cancels brokerage orders.
An expired, stale or invalid publication cannot supply current order-copy action.

## Management and execution evidence

All management instructions are conditional on actually entering. Targets are
reference levels, not forecasts. Production replay anchors targets to the modeled
fill, handles stop gaps at the open, whole-share partial sales and remaining
shares, and uses exchange-session duration. The implemented sequence includes
early strength/abnormal-move partials, the day-three partial/no-progress decision,
later daily-low trailing and final day-five exit. See the plan's dated exit
schedule and `src/plan.py` for its recorded levels and precedence.

There are material limits that this release does not disguise:

- Daily open-in-band fill is a model convention, not brokerage execution.
  Later trigger crossings, the first-30-minute condition, partial fills and
  intraday price order may be unknown. Same-bar ambiguity stays uncertain.
- A no-progress condition determined from the completed day-three candle and
  executed at that same close needs an attainable timing assumption. No historical
  return from this convention is presented here as executable performance.
- The existing intraday probe compares cumulative volume with the prior full
  day's total; that is not a same-time volume-pace comparison. No new probe was
  run. This cannot establish anticipation volume confirmation.
- The inherited no-break-even-before-day-five preference and some exit
  preferences draw on EP9M evidence. Their application to Momentum Burst is a
  SPICYSTOCK DERIVED choice, not a validated transfer of EP9M results. A primary
  2015 description instead mentions earlier break-even management.
- A different exit timing, selection ranking, numeric gate, membership or global
  actionability policy requires explicit decision review. Those alternatives
  remain unimplemented; no threshold was loosened to manufacture a ticket.

## Source register and access limits

| Category | Material source / claim boundary |
| --- | --- |
| PRIMARY Stockbee | [2015-11-18 4% scan](https://stockbee.blogspot.com/2015/11/how-to-use-4-breakout-scan-to-make-money.html) explicitly describes an end-of-day scan and next-day entry. [2017-07-13 process loop](https://stockbee.blogspot.com/2017/07/my-process-loop-to-trade-4-bo-and-bo.html) supplies reaction formulas and a first-30-minute route. [January 2014 quality](https://stockbee.blogspot.com/2014/01/how-to-identify-a-quality-setup.html) supplies qualitative context. Accessed 2026-09-28. None validates this selected implementation. |
| LATER BONDE | Later consolidations and timing changes remain identified in `knowledge/consolidation-quality.md` and `knowledge/method.md`. No fresh access to unavailable videos/private material is asserted. |
| COMMUNITY interpretation | Secondary practitioner summaries and the supplied field guide explain concepts; they are not interchangeable with dated primary evidence or audited returns. |
| SPICYSTOCK DERIVED choice | Exact proxies, grade weights, reviewer authority, membership, stop-constrained ticket, allocation and simulation conventions described above. Source code proves implementation, not source fidelity or edge. |
| EMPIRICAL observation | Retained publication outcomes, input checks and POC counts in the accompanying review. Synthetic controls prove software behavior only. |

The supplied Project brief was read as Library file
`libfile_976214df55588191bdb6bf8356949c3f` (8,013 bytes). The supplied field guide
was read as `libfile_093a7cd52e288191af578071dd800fdd` (174,888 bytes). Its page 5
emphasizes entry-day information; page 8 includes an end-of-day/next-morning
route. Its caveats distinguish unaudited practitioner claims and EP9M-specific
backtests from Momentum Burst evidence. These are source IDs, not invented
original-byte hashes. The user-supplied source files are not redistributed here.

## Reader request repair and prospective evidence

[Anthropic's direct API documentation](https://platform.claude.com/docs/en/build-with-claude/structured-outputs),
checked 2026-09-28, documents `output_config.format` JSON schema. The official
[compatibility table](https://platform.claude.com/docs/pt-BR/build-with-claude/structured-outputs)
retrieved through search lists Sonnet 4.6 and the direct Claude API. The opened
English/Portuguese page renderings omitted that table, an access/rendering gap;
this is documentation evidence, not a successful endpoint call.
The configured client is `anthropic.Anthropic`; installed SDK 1.8.0 accepts that
argument. The previous allowlist incorrectly omitted it. The shared SCORE_SCHEMA
and authority mapping remain authoritative; original NIC/BIO/RVTY/MSFT findings
remain rejected. The grammar does not enforce truthful visual interpretation.

Initial schema compilation can add latency; the provider documents a 24-hour
compiled-grammar cache and additional prompt tokens. Format changes can affect
prompt caching. No token-count, live latency or acceptance-rate improvement was
measured. The same model, attempts, output ceiling, timeouts and review count
remain configured. Extra image history retains the same image dimensions; its
legibility still needs prospective observation. No budget was increased.
The unchanged 30-second client timeout can expire during initial compilation;
offline compatibility does not establish acceptable production latency.
