# What SpicyStock checks about events, and what it leaves to the analyst

Dated 19 November 2026. A burst or a coil can be caused by an event the bars
do not show: a takeover, an earnings report, an offering, a trial result.
SpicyStock checks very little of that, and only for a few stocks. This note
says exactly what it checks and for whom, each statement read off the code on
that date, and then gives the outside analyst a ten-item check to run on every
candidate before a trade.

One rule holds throughout: **"not established" is never "clear".** A check
that did not run, could not read its source or found nothing in a bounded
window has cleared nothing.

## 1. What SpicyStock checks, and for whom

**What SpicyStock checks about events, and for whom.** (1) A manual registry
of known cash acquisitions blocks a ticket; it is reviewed by hand, and a
passed review date never clears an entry. (2) For published tickets only: an
earnings ESTIMATE from SEC results filings (a warning, never a refusal) and
the 8-K item codes of the last 14 days. (3) For tickets and registry-blocked
plans only: up to three recent SEC current reports and the merger and tender
forms on file. (4) On the morning of a ticket, if a morning check runs:
Nasdaq's halt feed. Nothing reads company press releases, news wires,
announced earnings dates, offerings, FDA dates, index changes, lockups or
dividends, and on a night with no ticket and no registry-blocked plan (more
than half of the nights so far) checks 2 to 4 run for no stock at all. Every
candidate needs the outside analyst's event check before a trade.

The same, check by check:

| check | which stocks | what it reads | what it does | where |
|---|---|---|---|---|
| Event registry | every row the run builds a plan for: a burst that passed the grade, veto, admission and reader gates, and each listed setting-up name. The daily brief also reads the registry the record archived against every listed row. | `knowledge/event-risk.json`, a hand-kept list of known cash acquisitions, each entry with dated sources | An entry withholds the ticket: the plan is `refused` and carries no order. A passed review date changes the status word from `known_event` to `review_required` and nothing else: the stock stays blocked. | `src/event_risk.py` (`classify()`, `apply()`) |
| Earnings estimate | published tickets only, at most 8 a night | SEC's filing list for the issuer: its quarterly-results reports (Form 8-K, item 2.02) | A warning beside the ticket. Last year's report date moved forward 364 days, give or take 7, is placed against the ticket's five-session hold. It is an estimate, never an announced date; `unknown` is never clear. The policy is `warn_only`: it never refuses, sizes or cuts a ticket. | `src/earnings_risk.py` |
| Recent 8-K items | the same tickets, from the same filing list | the item codes of each Form 8-K filed in the 14 days before the signal or since | A warning. It names the report when one carries item 1.01, 1.03, 2.01, 3.01 or 5.01 (a material agreement, a bankruptcy, a completed acquisition or disposition, a delisting notice, a change in control). An item names a kind of event, not what the filing says. | `src/earnings_risk.py` (`MATERIAL_ITEMS`) |
| Issuer documents | tickets and registry-blocked plans, at most 8 issuers | SEC only: up to 3 current reports (8-K, 6-K and their amendments) from the last 365 days with up to 2 exhibits each, and the merger and tender forms on file (PREM14A, DEFM14A, SC TO-T, SC 14D9 and their amendments) | Excerpts and a list on the Morning desk. The receipt's own coverage block says issuer news is `not_cleared` and the earnings calendar `not_checked`. | `src/issuer_evidence.py` |
| Halts | admitted tickets, on the morning the check runs | Nasdaq Trader's trading-halt feed | A halt reported with no trading resumption marks the ticket as blocked for entry, and the page withholds its order-copy control. Nothing is read when no morning check runs inside its window. | `src/morning_halts.py` |
| Directory flags | every stock in the universe | the exchange directory's sector, industry and country | Two warnings, `biotech` and `foreign`. `biotech` is set for the whole Health Care sector and is not a classification of the company. Neither refuses anything. | `src/universe.py` (`flags_for()`) |

**What no code here reads.** The outside sources the code under `src/` reads
are SEC (`data.sec.gov`, `www.sec.gov`), Nasdaq Trader (the halt feed,
`www.nasdaqtrader.com`), Nasdaq (the stock directory, `api.nasdaq.com`), the
market-data provider (`data.alpaca.markets`), the chart reader's model API and
the mail provider. The only other addresses it names are this project's own
pages and repository. There is no news wire, no press-release feed and no
earnings calendar. So nothing reads:

- company news and press releases;
- announced earnings dates (the earnings row is an estimate from past filings);
- offerings and shelf takedowns;
- FDA decisions and trial readouts;
- halts, outside the morning check;
- delisting notices, beyond 8-K item 3.01 on a ticket;
- index additions and deletions;
- lockup expiries;
- ex-dividend dates.

**How often the checks have anything to read.** The earnings, 8-K and halt
checks read tickets only, and the issuer check reads tickets and
registry-blocked plans. Of the 48 sessions published from 11 September to 17
November 2026 (54 publications), 11 carried a ticket and 15 carried a plan the
registry blocked (4 sessions carried both). On 26 sessions there was neither,
and those four checks had no stock to read. The earnings block exists from the 2 November session: in
the 12 publications that carry it, 6 say `not_applicable` and the other 6 hold
13 ticket rows between them, against 6,600 listed burst rows.

**How old the registry is.** The registry is a file a person edits. Each entry
carries the date it was last reviewed (`reviewed_on`) and the date its next
review is due (`review_due`), and the file carries the date of its last review.
A record archives the registry it ran under, and the daily brief's section 11
(`events`) says, for that record, how old the review is, which entries are past
their review date and how many listed rows are in the registry. Read it there
and not here. As a dated example: the record of 17 November 2026 archived 7
entries, last reviewed 20 October, all 7 past their review date and all 7 still
blocked, and none of its 174 listed rows was in the registry.

**How the registry learns of a deal.** Only when someone reads the news and
adds it. In the layered setup that is the analyst: a pending deal found by the
check below is reported to the owner with its primary source, so it can be
added. The registry's own rules need, for each source, a title, the date it was
published, an https address, a sentence quoted from it and a SHA-256 digest
(`validate_registry()`). The code checks the digest's form and not what it is
a digest of.

## 2. Words that are not clearance

| word | where | what it means |
|---|---|---|
| `known_event` | the registry status of a row | in the registry and blocked for a SpicyStock ticket; the manual review is current |
| `review_required` | the same | in the registry and blocked; the manual review is overdue. Still blocked. The record does not establish the deal's present status |
| `not_in_registry` | the same | no entry applies. Not a clearance: nothing was checked |
| earnings verdict `unknown` | `run.earnings.rows[]` | the estimate could not be made, for the reason given. Never clear |
| items status `none` | the same rows | no Form 8-K in the 14-day window. It says nothing about news the company did not file on Form 8-K |
| issuer coverage `not_cleared`, `not_checked` | `docs/issuer-evidence.json` | the collector's own statement of what it did not do |
| no earnings row at all | a candidate without a ticket | no check ran |

The analyst answers each item of the check below with one of three words:
**clear** (a primary source was read and shows no event inside the hold),
**hit** (a primary source shows one), or **not established** (no primary
source could be read, or it does not settle the question). "Not established"
is reported as such and never rounded to "clear".

## 3. The check for every candidate

Run it for each candidate the analyst may recommend, ticket or not. For each
item record the answer, the source's address, the date of the document, the
sentence relied on and when it was read. A social-media post, a forum or an
aggregator's calendar is a pointer to look for the source; it is never the
source. The hold is five sessions and day 1 is the session after the signal
(`plan.FINAL_EXIT_DAY`).

"What a hit means" is the analyst's default handling. It is not a SpicyStock
rule: SpicyStock's only event rule is the registry block, and its earnings and
8-K rows are warnings.

| # | question | primary source to prefer | what SpicyStock already says | what a hit means |
|---|---|---|---|---|
| 1 | Is there a pending acquisition, tender offer or going-private deal? | The issuer's SEC filings: Form 8-K items 1.01, 2.01 and 5.01; the merger proxy (PREM14A, DEFM14A); tender documents (SC TO-T, SC 14D9); SC 13E3. Then the issuer's own release. | The registry status of the row; for a ticket, the 8-K items and the merger and tender forms listed. For any other candidate: nothing. | No momentum trade: a deal price pins the stock and a broken deal gaps through any stop. Report it to the owner with its source so the registry can add it. Two patterns to look into, neither of them proof: a price flat just under a round number for days, and a one-day gap on very large volume. |
| 2 | Does the company report earnings inside the five-session hold? | The company's own announcement of the date (its investor-relations release, often furnished on Form 8-K). | For a ticket only: an estimate from last year's filing. For any other candidate: nothing. | Skip, or plan to be out before the report. If the date cannot be established for a company that has not yet reported this quarter, say so: that is "not established". If the earnings report itself caused the burst, say so: it is a different setup. |
| 3 | Is there a new share offering or a shelf takedown? | SEC filings: 424B5, 424B3, FWP, S-1, S-3, and Form 8-K items 1.01 and 3.02; the words "at-the-market" in any of them. | Nothing. | An offering priced or announced in the last five sessions, or tonight: skip. An at-the-market programme in use on a small company: say so, and reduce or skip. |
| 4 | Is an FDA decision or a trial readout due inside the hold? | The company's releases; ClinicalTrials.gov completion dates; the FDA's advisory-committee calendar. | The `biotech` flag, which marks the whole Health Care sector and establishes nothing about a date. | A binary event inside the hold: skip. |
| 5 | Is the stock halted? | Nasdaq Trader's halt list and the NYSE's, on the morning of the trade. | For a ticket, when a morning check ran in its window: the receipt's halt row. | No entry until trading has resumed and the plan has been looked at again. |
| 6 | Is there a delisting or deficiency notice? | Form 8-K item 3.01; a late-filing notice (NT 10-Q, NT 10-K); a bid price under $1. | For a ticket: item 3.01 among the 14-day 8-K items. | Skip. |
| 7 | Is the stock being added to or removed from an index? | The index provider's own announcement (S&P Dow Jones Indices, FTSE Russell). | Nothing. | Note the effective date and that index funds must trade on it. Do not buy a deletion. |
| 8 | Does an IPO lockup expire inside the hold? | The IPO date and the lock-up period in the final prospectus (424B4), often 180 days. | Nothing. | Skip, or reduce. |
| 9 | Is there an ex-dividend date inside the hold? | The company's dividend declaration. | Nothing. | The price falls by about the dividend on that date: check the stop against it. What Fidelity does to a resting stop on that date is unconfirmed (`broker-fidelity.md`, U16). A large special dividend: skip. |
| 10 | What does the registry say, and is it still true? | The registry entry's own sources, then the issuer's newest SEC filings. | `known_event` or `review_required`: blocked either way. | Treat as blocked. When asked to review an entry, report the deal as closed, terminated or still pending, with a primary source and its date; a review date alone establishes nothing. |

**What to hand back.** For each candidate: the ten answers, each with its
source, and one line that says which items are "not established". A candidate
with an item not established is reported that way to the owner, who decides.
