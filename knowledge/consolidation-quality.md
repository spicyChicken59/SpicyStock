# Consolidation quality: selected sources and DERIVED implementation

Verified 22 September 2026 against the blog text below, the supplied Stockbee
field guide, and `src/quality.py`. This contract covers reaction C only. It
supersedes older C comments/attributions in `method.md`; it does not certify
unrelated strategy numbers. The [retained audit][audit] records empirical
consequences separately from source authority.

## Source hierarchy and historical variants

PRIMARY means a directly inspected Bonde statement. LATER BONDE means a dated
later statement, not automatic authority to silently replace an earlier rule.
COMMUNITY means someone else's interpretation. DERIVED means SpicyStock's
operational choice. Retained production evidence establishes what executed,
not what Bonde intended or whether a trade had an edge.

| Window / concept | Classification | Inspected statement and scope | Current selection |
|---|---|---|---|
| 3–20 | PRIMARY, 2014-01-04 [P14a] | Consolidation before a momentum-burst expansion; narrow bars and an orderly prior move | Ordinary C pass interval |
| Three or more days | PRIMARY, 2014-01-14 [P14b] | No momentum burst during that pause; a 17-day example illustrates a quiet setup | Qualitative context; zero internal price bursts is used for C A+ |
| 3–10 | LATER BONDE, 2015-02-19 [L15] | **Anticipation** selection, low volatility/volume and no 4% breakdowns | Not the reaction C pass interval |
| 5–40 | LATER BONDE, 2018-01-16 [L18] | Reaction pullback/base before 4% or Dollar breakout; no 4% breakdowns | Distinct historical variant, not the selected complete rule |
| At most one 4% down day | LATER BONDE, 2020-12-08 [L20] | 2LYNCH describes shallow, orderly, compact/narrow, low-volume consolidation and “no more than one 4% b/d in consolidation” | Selected ordinary C allowance; earlier zero-breakdown ideal informs A+ |
| Two sessions / 21–39 | DERIVED | Partial credit when all other ordinary C clauses pass | Product policy, not a Bonde partial classification |

This is an explicit blend of selected historical components plus DERIVED
measurements. It is not one fully sourced, timeless Bonde formula. In
particular the 2018 window and its zero-breakdown requirement must not be
split apart and presented as execution of the whole 2018 variant. A future
choice to implement another variant must specify its complete scope and
preserve the existing rules digest/version mechanism.

The supplied field guide is a secondary research aid: it supports orderly,
shallow, compact, narrow and lower-volume concepts and points to primary
sources. It does not establish the exact ratios below. The older repository
comment attributes one-third to an unidentified secondary webinar port. Its
author, original statement and denominator were not verified; it cannot be
promoted to PRIMARY or a verified named COMMUNITY rule. No directly inspected
primary source here establishes exact one-third or quarter giveback limits.
The linked 2024 X thread was unavailable, and the embedded 2018 video was not
re-listened to in this audit. Those gaps remain gaps.

## What the deterministic measurements mean

Indices refer to retained sessions, not calendar days. `t` is the signal
session. Prices are rounded to cents; quality percentages to one decimal;
quality ratios to two decimals before comparisons. Close ratios use the scan's
four-decimal grid. These normalization choices are DERIVED.

`_find_base` takes the **first highest High** from `max(t-40, 0)` through
`t-2`, inclusive. The base starts the next session and ends at `t-1`.
Its available lengths are 1–39; a 40-session search is not a 40-session base.
No quietness, volume, intervening burst, breakdown or contraction test chooses
the start. A retest at exactly the same rounded high keeps the older peak;
a higher peak resets it. A later pause below the older high does not reset it.
The rolling search can evict an old peak. The final pre-signal session is
deliberately excluded as a peak so that at least one base bar exists.

The stored `base.high` is that **peak anchor outside the base**, not necessarily
the maximum high of base bars. The final pre-signal high can exceed it.
`base.low` is the minimum intraday low from start through end. `_find_leg`
starts at the last occurrence of the lowest **close** in the up-to-60-session
window ending at the peak, and includes the peak. Its `low` is the minimum
intraday low inside the selected leg. Neither boundary algorithm is supplied
by the primary sources. An orderly advance/pause is the source concept;
these are reproducible proxies, not source-certified chart segmentation.

| Measurement | Classification | Current calculation and vote |
|---|---|---|
| Breakdown count | Source concept; DERIVED event normalization | Count each base session with rounded `close / previous_close <= 0.96`, including the first base day's comparison with the peak close. Consecutive days count separately. Ordinary maximum 1; A+ maximum 0. |
| Giveback | DERIVED | `(peak_high - base_low) / (peak_high - leg_low)`, rounded; ordinary `<= 0.34`, A+ `<= 0.25`. Not a ratio of closing-price returns. Nonpositive denominator means unknown; values are not clamped to 0–1. |
| Tightness | DERIVED | Mean of `100*(high-low)/close` for base bars, divided by the mean of the same daily measurement over up to 60 sessions immediately **before the base starts**. Ordinary `<= 1.0`, A+ `<= 0.70`. Neither total box width nor ATR. |
| Volume ratios | DERIVED | Base arithmetic mean / selected-leg arithmetic mean, and base arithmetic mean / up-to-50-session arithmetic mean ending at `t-1`. Both rounded ratios must be `< 1` for A+. Neither is required for ordinary C. |
| Internal bursts | Source-inspired DERIVED A+ condition | Price-only rounded close ratio `>= 1.04`, counted over the base; zero for A+. No ordinary C gate. |

The C breakdown count shares only the **price clause** of
`scans.breakdown_4pct`. The scan also requires volume above the prior day and
at least 100,000 shares. C does not. The inspected C wording does not specify
those volume qualifiers, so importing them would be another implementation
choice, not a demonstrated correction. C counts daily adverse moves, not
crossings below a horizontal support level or cumulative drawdown.

Shallowness and an orderly pullback are primary concepts [P14b], [L17], [L20].
An exact 0.34 limit is not an exact one-third fraction; rounding also affects
the boundary. A quarter is a stricter product flag, **not** a mathematical
translation of the older unsupported “upper third” attribution. The product
rationale is to reserve extra credit for shallower pauses. That establishes
an interpretable preference, not evidence that 0.25 is optimal or Bonde's.

The sources describe narrow bars/low volatility, not the tightness ratio or
its numeric cutoffs. Relative normalization can reject absolutely small bars
when preceding bars were even smaller, and can accept larger bars following
a volatile leg. Segmentation changes both numerator and historical norm.
This is a known limitation of the proxy, not proof of an alternative rule.

Orderly volume appears in [P14b]; low volume in [L20]. Exact averaging windows,
the overlapping prior-50 denominator, strict rounded `< 1` comparisons and
their A+-only role are product choices. C A+ combines ordinary PASS, no internal
price bursts/breakdowns, quarter giveback, 0.70 tightness and both volume tests.
No inspected primary source supplies that exact conjunction.

Ordinary PASS requires the selected length **and** all three ordinary numeric
clauses. With those clauses satisfied, lengths 2 and 21–39 receive PARTIAL;
one session receives FAIL. Otherwise a measured violation receives FAIL.
Missing base/depth/tightness is UNMEASURED, not a fabricated failure. C has
weight two (PARTIAL earns one); it is not a veto. The overall A+ grade does
not require the C A+ flag.

## Operational source fidelity

The implementation is a defensible, explicitly limited approximation; the
available sources do not validate its exact segmentation or thresholds.
Historical variants and numeric policy must remain visible. A passing proxy
can miss a qualitative flaw; #86's bounded reader can identify chart geometry
while keeping recorded facts unchanged. It cannot turn missing C A+ or high
base volume alone into a measured ordinary C failure.

This attribution correction changes the reader's explanatory prompt and
source documentation, not mechanical C, grades or `RULES`. Prompt provenance
captures new prompt bytes normally; old publications keep their own evidence.
No retrospective regrading or new model execution is implied.

## Inspected source register

Blog text was inspected directly; image-only visual correspondence and a
human-labelled base-boundary benchmark were not established.

- [P14a]: *How to identify good Momentum Burst and Anticipation setup*, January 4, 2014.
- [P14b]: *How to identify a quality setup*, January 14, 2014.
- [L15]: *How to find anticipation setups*, February 19, 2015.
- [L17]: *My process loop to trade 4% b/o and $ b/o*, July 13, 2017.
- [L18]: *What to look for in good 4% or $ b/o*, January 16, 2018.
- [L20]: *How to make money using setups: detailed guide*, December 8, 2020.

[P14a]: https://stockbee.blogspot.com/2014/01/how-to-identify-good-momentum-burst-and.html
[P14b]: https://stockbee.blogspot.com/2014/01/how-to-identify-a-quality-setup.html
[L15]: https://stockbee.blogspot.com/2015/02/how-to-find-anticipation-setups.html
[L17]: https://stockbee.blogspot.com/2017/07/my-process-loop-to-trade-4-bo-and-bo.html
[L18]: https://stockbee.blogspot.com/2018/01/what-to-look-for-in-good-4-or-bo.html
[L20]: https://stockbee.blogspot.com/2020/12/how-to-make-money-using-setups-detailed.html
[audit]: ../docs/input-truthfulness/2026-09-22-consolidation-source-fidelity.md
