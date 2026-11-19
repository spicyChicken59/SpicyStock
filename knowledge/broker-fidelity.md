# Placing a SpicyStock ticket at Fidelity

Dated 17 October 2026. Revised 4 November 2026 (the first actual orders) and
19 November 2026 (what the open does to a burst ticket's buy stop, the owner's
own practice labelled, the same-day sell stop moved from unconfirmed to
observed, the cash rules completed, the 5 November orders named as unrecorded,
the unconfirmed list updated). The owner named Fidelity as the broker on 17
October 2026. This note maps a published SpicyStock ticket onto Fidelity's
order entry and says what Fidelity does with each part of it. SpicyStock
places, changes and cancels nothing; it reads no account and no fill.

Two sibling notes carry what follows from this one:
[`broker-fidelity-protocol.md`](broker-fidelity-protocol.md) is the one-sitting
check of everything still unconfirmed here, the order-entry tables by price
state and the cash-account working rules;
[`trade-ledger.md`](trade-ledger.md) is the ledger of real orders and fills
the outside analyst keeps. A fact confirmed by the protocol is written back
here in a dated revision.

**How this was read.** The machine that wrote this note could not open
fidelity.com, sec.gov or finra.org (its proxy refuses them), so every fact below
was read off search-result excerpts of those pages, not the pages themselves.
Each fact carries one label, and a fact in Fidelity's or a regulator's words
names the source it was read from by its number under **Sources**:

- **Fidelity's words** — the excerpt quotes or summarises a fidelity.com page;
- **a regulator's words** — the excerpt quotes or summarises an SEC, SEC staff
  or FINRA page;
- **inferred** — it follows from Fidelity's words, but no excerpt says it;
- **unconfirmed** — no source read here says it;
- **SpicyStock's advice** — what this note asks the reader to do, which is not
  Fidelity's.

Three more labels mark what came from the owner and not from a source:

- **the owner's words**: what the owner told this project; nothing here
  checks it;
- **Fidelity's screen**: observed on the owner's own Fidelity screen as he
  showed it, with the date; SpicyStock reads no account;
- **the owner's practice**: what the owner does himself. It is his rule. It is
  not a SpicyStock ticket and not SpicyStock's advice.

**When each fact was read.** A fact labelled Fidelity's words or a regulator's
words was read on 17 or 18 October 2026, when this note was first written,
unless its sentence gives another date. A fact marked *read 19 November 2026*
comes from a search summary over fidelity.com pages that a read-only verifier of
this project ran that day; the writer of this revision did not repeat the
searches. A summary names several pages and not which page carries which
sentence, so each of those facts is also marked *to confirm*. Fidelity's screen
was read on 4 November 2026. Nothing has been read on Fidelity's own pages or
in its ticket by this project.

Confirm each in Fidelity's own ticket before the first order. A fact confirmed
there belongs in a later dated revision of this note, with the date and the
screen it was read on.

## The ticket, field by field

A stock's plan disclosure prints a SpicyStock ticket in Fidelity's field order
with a copy button and reads it back in one line:
`Buy N SYM stop-limit: stop TRIGGER limit LIMIT, day · OTO sell N SYM stop-loss STOP GTC`.
The tickets sheet lists every offered burst ticket, the symbol first, with no
copy control; each row's ticker opens that stock. An offered setting-up ticket
is not on the sheet: it is printed on its own stock's plan and action bar. A
Burst's action card carries the same ticket with its own **Copy order**. The
Morning desk's private handoff is different: it copies a personal readback at
the quantity you chose, with the protective sell listed as a separate line, and
it is not in Fidelity's order-entry format; at Fidelity that sell is the OTO's
secondary order.

| SpicyStock | Fidelity field | Value |
|---|---|---|
| action | Action | Buy |
| shares | Quantity | the ticket's whole shares, or the smaller whole number the Morning desk's cash preview names |
| ticker | Symbol | the ticker |
| order type | Order Type | Stop Limit |
| trigger | Stop Price | the ticket's trigger |
| limit | Limit Price | the ticket's limit |
| day | Time in Force | Day |
| OTO | Trade Type, on the conditional trade ticket | One-Triggers-the-Other (OTO) |
| then: sell | secondary Action | Sell, the same quantity |
| then: stop-loss | secondary Order Type | Stop Loss (SpicyStock's advice: a stop-market order, never a stop limit, because a gap through a limit would leave it unfilled) |
| stop | secondary Stop Price | the ticket's stop |
| GTC | secondary Time in Force | Good 'til Canceled |

The field names are **unconfirmed**: no excerpt read here gives the current
web or mobile ticket's field names. The values are SpicyStock's ticket.
Fidelity's words, from a search summary over about ten fidelity.com links that
names no single page (among them [7] and the Active Trader Pro user guide
[21]): the conditional trade ticket defaults to a Contingent order and its
Trade Type drop-down selects another type, so OTO is looked for there. Where
the conditional ticket is on the current web and mobile screens is
unconfirmed. The Day buy beside a Good 'til Canceled sell stop is
item 6 below, on which the sources disagree.

The record's own word for an eligible burst ticket is `plan.action`
`buy_at_open`, and for an anticipation ticket `place_buy_stop`
(`plan.ORDER_ACTIONS`). Neither names an order type. `buy_at_open` is a legacy
word and never means a market-on-open order: the order is the buy stop-limit
in `plan.order_json`, which the daily brief carries as `order_as_written` under
the order kind `buy_stop_limit_oto`. An anticipation plan's `open_entry`
sentence (a market-on-open note for the top names) and the chart reader's
entry note are research notes beside the ticket; they are not the ticket.

## What Fidelity does with it

1. **The OTO's sell stop is released only when the buy fills in full.**
   Fidelity's words [2]: when the primary order executes in full, the secondary
   order is released to the marketplace, and "a partial fill of your primary
   order will not release your secondary order"; the conditional-orders
   overview [1] says the same of OTO orders. Fidelity's words [2]: if the
   primary order is canceled, the secondary order is also canceled, and a
   primary order pending cancel may still fill after a delay and release the
   secondary. Inferred: a buy that fills in part leaves the shares that did fill
   with no stop, and if the rest of the buy fills later the secondary is
   released for the whole quantity. SpicyStock's advice: wherever a ticket, a
   plan or its dated schedule says the sell stop is attached at or live from
   the fill, that assumes a full fill of an accepted OTO; if the buy fills in
   part, place a separate Sell, Stop Loss, Good 'til Canceled order for the
   filled shares at the ticket's stop, and check that no second sell stop
   remains for shares you do not hold (a late fill of the rest releases the
   OTO's own stop beside yours). Fidelity's screen, 4 November 2026: a separate
   Good 'til Canceled sell stop on shares bought the same day was accepted (the
   first-orders section below). The text the page and the mail print beside
   every order (`report.BROKER_PART_FILL`) was written before that and still
   says to confirm it. The page prints this rule and this advice, each
   labelled, beside every order it prints: the plan disclosure's ticket and its
   recorded copy after the window, the tickets sheet, a Burst's action card, a
   setting-up stock's action bar, the comparison, the decision summary's entry
   (a setting-up stock's only while its action bar, on the same screen, does
   not offer the order), the model
   exits, a saved setup's archived order and an archived original's status.
   The private handoff prints it in its readback, and the mail after each block
   of orders. Beside a burst ticket's order (never a setting-up ticket's) the
   same places print a second labelled note from item 2 below, Fidelity's
   buy-stop rule with SpicyStock's advice (`report.BROKER_BUY_STOP`); the mail
   prints it once, after the burst orders. On a Burst's action card and in the
   decision summary's entry the two notes sit under one closed **Broker notes**
   disclosure, so neither shows until the reader opens it.

2. **A buy stop must be priced above the current market.** Fidelity's words
   [4]: buy stop loss and buy stop limit orders must be entered at a price
   above the current market price. An anticipation ticket's trigger is a few
   cents over the top of its box (the larger of $0.02 and 0.1% of the close,
   `plan.TRIGGER_CENTS` and `plan.TRIGGER_FRACTION`), above its last close. A
   burst ticket's trigger IS the burst session's close: its buy stop is never
   above the last close.

   *Before the open* (revised 19 November 2026). Unconfirmed: which price
   Fidelity compares the stop with before the open, the last close or a
   pre-market quote. If it is the close, Fidelity refuses every burst ticket
   as written. SpicyStock has not been able to say where a burst name trades
   before the open either: on 5 November 2026, the only morning with burst
   tickets so far, the morning check ran about seven minutes before the open
   (`docs/morning.json` at commit `30963c2d`) and read every price check of all
   three tickets as `unknown`, because the feed's last trade and quote for each
   were stale.

   *After the open* (revised 19 November 2026). Inferred from Fidelity's words
   [4], and not in doubt: once the stock trades at or over the last close, the
   buy stop is no longer above the market, and the ticket cannot be entered as
   written. How often that happens was measured on 19 November 2026 from the
   records' own published bars. The population: every burst row in the first
   publication of each session, among the 47 publications of the 7 November
   2026 study spec, for which `plan.burst_plan()` writes a ticket of at least
   one share at the record's archived account and full size, with the market
   gate, the grade, the vetoes, the admission rule, the chart reader and the
   slot cap all removed (`tools/signal_outcomes.py`'s `ticket()`), and whose
   signal-day bar and a later bar are in those publications' bars: 13,599
   counterfactual tickets on 40 nights (signal sessions 11 September to 5
   November 2026; 31 RED nights, 9 YELLOW). They are not published tickets:
   only three burst tickets have ever been published. Day 1, the next bar after
   the signal session, opened:

   | first-day open | tickets | share |
   |---|---|---|
   | under the skip line (2% under the close) | 885 | 6.5% |
   | at or over the skip line, under the buy stop | 5,264 | 38.7% |
   | exactly at the buy stop | 465 | 3.4% |
   | over the buy stop, at or under the limit | 5,030 | 37.0% |
   | over the limit, at or under the day-2 line (4% over the close) | 1,725 | 12.7% |
   | over the day-2 line | 230 | 1.7% |

   Those are price ranges, and the ranges are not the price states the morning
   check prints (`morning.price_state()`): on 4,567 of the tickets the stop
   sits at or over the skip line, so an open at or over the skip line and at
   or under the stop is `below_stop` (193 of the tickets), and an open under
   the skip line is `below_stop` when it is at or under the stop (635) and
   `below_entry_floor` only over it. By state:

   | price state | tickets | share |
   |---|---|---|
   | `below_stop` | 828 | 6.1% |
   | `below_entry_floor` | 250 | 1.8% |
   | `below_trigger` | 5,071 | 37.3% |
   | `within_published_band` | 5,495 | 40.4% |
   | `above_limit` | 1,725 | 12.7% |
   | `above_day2_extension` | 230 | 1.7% |

   So day 1 opened at or over the buy stop on 7,450 of the 13,599, 54.8% (among
   the mechanical A+ and A rows without a veto, 1,154 of 2,090, 55.2%). On the
   5,495 that opened at the buy stop or over it and at or under the limit
   (40.4%), the model books "filled at the open" (`record.fill()`). Only an
   order already resting at the broker before the open can take that fill, and
   whether Fidelity accepts that order before the open is the unconfirmed point
   above. Of the three published burst tickets (4 November 2026), HQY and RCBC
   opened over their buy stops on 5 November and the model books both as filled
   at the open; VIK opened under its buy stop and reached it in the first
   minute. The figures are opens on daily bars: of the 5,264 that opened under
   the buy stop, 4,017 reached it later that day, and how many did so inside
   the first 30 minutes the daily bars cannot say.

   SpicyStock's ticket has no plain-limit fallback, and no other order type is
   placed on its authority (`plan.fidelity_orders()`). What the owner does in
   that case is his own practice, labelled in its own section below.

3. **What triggers a stop.** Fidelity's words [4]: an equity stop placed with
   Fidelity is triggered by a round-lot trade of 100 shares or more, or a print
   in the security. Fidelity's words [1]: the market centers stop orders are
   routed to may apply price bands around the best bid and offer.

4. **A stop limit becomes a limit when it triggers.** Fidelity's words [4]: it
   then fills in whole, in part, or not at all. The ticket's own terms say the
   rest: an open above the limit does not fill at the open, but the resting
   order stays live and can fill on a pullback later in the day (unconfirmed at
   Fidelity, below). Fidelity's words, read 19 November 2026, to confirm:
   Fidelity can also refuse a triggered order whose stop or limit is on the
   wrong side of the market.

5. **A day order and the entry window.** Fidelity's words [6]: a day order
   entered outside market hours is subject to the conditions at the reopen.
   Fidelity's words [4, 7]: a day order expires at 4:00 PM ET (3:00 PM CT) by
   default, and an earlier expiration from 10:00 AM ET (9:00 AM CT) to 4:00 PM
   ET can be chosen in 30-minute steps. The plan's entry window is 8:30 to
   9:00 AM CT, so a 10:00 AM ET expiration would end the buy with the window.
   Unconfirmed: that the web or mobile ticket offers that expiration on an OTO's
   primary, and that a day stop limit entered before the open is live from the
   9:30 AM ET (8:30 AM CT) open. SpicyStock's advice: if the buy has not filled
   by 9:00 AM CT, cancel it, unless its expiration was set to 10:00 AM ET.

6. **A Day buy with a Good 'til Canceled sell stop: the sources disagree.**
   Unconfirmed, because two search summaries read here say opposite things,
   and each covers about ten links without naming which page carries which
   sentence. The first, over fidelity.com links only (among them [4], [7], [18]
   and [21]), says each order of an OTO can have its own time in force (an
   OCO's two must match), and that a GTC OTO is good for 180 days in all, so
   the secondary's life is shortened by the time the primary took to fill. The
   second, over fidelity.com links (among them [1], [3] and [18]) and pages of
   three other sites not listed here (two other brokers' help pages and a
   trading forum), attributes to "Fidelity's OTO guidance" that
   an OTO's two orders must share one time in force. [18] is among the links of
   both, so neither statement can be tied to one page. A fidelity.com-only
   search summary read 19 November 2026 shows the same disagreement, the newer
   Fidelity pages saying the two orders may differ and the older ones that they
   must match: still unconfirmed. SpicyStock's advice: if the
   ticket refuses a Day buy with a GTC sell stop, do not make the stop Day (it
   would expire at the close and leave the shares without a stop overnight)
   and do not make the buy GTC (it would outlive the entry window). Place the
   buy alone, as the ticket's Day stop limit, and once it fills place a
   separate Sell, Stop Loss, Good 'til Canceled order at the ticket's stop for
   the shares that filled, as for a part fill (item 1).

7. **Stops do nothing in extended hours.** Fidelity's words [8, 9]: limit and
   reserve orders are the only order types available in the pre-market and
   after-hours sessions, and good 'til canceled orders are not available in
   them. Inferred: neither leg of a ticket acts before the open or after the
   close.

8. **Whole shares.** Fidelity's words [10]: fractional-share and dollar-amount
   orders are market or limit orders, day only. Inferred: a stop limit with an
   OTO secondary needs a whole number of shares. A SpicyStock ticket is always
   a whole number of shares.

9. **Settled cash.** Fidelity's words [11, 12]: a security bought without
   sufficient settled funds and sold before it is fully paid for is a good faith
   violation, even if payment arrives before settlement; three good faith
   violations in a 12-month period restrict the account to "purchasing
   securities only when the customer has sufficient settled cash ... at the
   time of purchase", for 90 calendar days [11]. Fidelity's words [19, 20]:
   settled cash is the part of core cash that can buy and sell securities in a
   cash account without a good faith violation, and uncollected deposits may be
   left out "until the bank collection process clears, which is usually four
   business days". A regulator's words [16], the SEC staff's investor
   bulletin: most US stock trades settle one business day after the trade
   (T+1), for trades on or after 28 May 2024. A ticket's stop can sell on the day the buy fills, so
   SpicyStock's advice is to buy with settled cash only: the Morning desk asks
   for settled cash and never reads it from the account. How long a given
   deposit takes to clear in the owner's account is unconfirmed: read the
   account's settled-cash figure.

   Completed 19 November 2026, each fact with its label:

   - Inferred from the definition above [11, 12]: a position bought with
     settled cash and stopped out the same day is a loss, not a good faith
     violation, because the purchase was fully paid for when it was made. The
     violation needs a purchase made with unsettled funds and then sold before
     those funds settle.
   - Fidelity's words, read 19 November 2026, to confirm: Fidelity's own worked
     example on its trading-restrictions page [11] says the same, that a buy
     paid for with settled cash and sold the same day is not a good faith
     violation, and that the violation is buying with unsettled sale proceeds
     and selling that purchase before the proceeds settle.
   - Fidelity's words, read 19 November 2026, to confirm: three cash
     liquidation violations, or one free riding violation, in a 12-month period
     restrict the account for 90 days in the same way; free riding is paying
     for a purchase with the proceeds of selling that same purchase.
   - Fidelity's words, read 19 November 2026, to confirm: the balance called
     "Cash available to trade" includes the day's activity and unsettled sale
     proceeds, so in an unrestricted cash account it can be larger than
     "Settled cash". Inferred from that: the difference between the two is the
     money a purchase could spend into a good faith violation.
   - Fidelity's words, read 19 November 2026, to confirm: an IRA with limited
     margin can trade unsettled funds without good faith violations. The
     minimum balance the summary gave for it is not relied on here. Whether
     either of the owner's IRAs has limited margin is unconfirmed.
   - Unconfirmed: the hour on the day after a sale at which its proceeds read
     as settled.
   - A regulator's rule as `src/plan.py` records it (`PDT_RULE_DELETED_ON`,
     `PDT_PHASE_IN_ENDS`, `PDT_EQUITY_USD`): FINRA deleted the
     pattern-day-trader count rule on 4 June 2026 and lets a member firm keep
     applying it per account until 20 October 2027; the count is of a margin
     account. Unconfirmed: that Fidelity applies none of it to a cash IRA.
   - The owner's words: the money sits in two IRAs. The model reads them as
     one $30,000 account with a $7,500 cap per name; SpicyStock does not know
     how the money is split between them. Inferred: a ticket's cost
     (`position_usd`) has to fit the settled cash of the one IRA that will hold
     it.
   - SpicyStock's advice: read Settled cash in the IRA that will hold the
     trade before every buy; never fund a buy from the proceeds of a sale made
     that day. A 90-day restriction would impose exactly this.

10. **Costs.** Fidelity's words [13]: $0 online commission on US stocks.
   Fidelity's words [10]: a sale carries an additional assessment fee of $0.01
   to $0.03 per $1,000 of principal (read on the fractional-shares page; the
   commissions page's own fee line was not read). A regulator's
   words [15], the SEC's: the Section 31 fee on sales is $20.60 per million
   dollars from 4 April 2026. A regulator's words [17], FINRA's filing: the
   trading activity fee is $0 from 1 October to 31 December 2026 and the
   previous rates resume in January 2027.
   Enter the fees your confirmation shows in the private report's fee fields;
   SpicyStock never computes them.

11. **Where.** Fidelity's words [14]: Active Trader Pro begins to be retired in
    2027, Fidelity Trader+ replacing it. Whether the web ticket and the mobile
    app both offer a Stop Limit with an OTO secondary is unconfirmed.

## The first actual orders, 4 November 2026 (the owner's words and screen)

Mo placed his first real trades on 4 November 2026 and showed the Fidelity
activity screen. What it establishes, labelled as this note labels everything:

- **The owner's words** — the trades sit in two Fidelity IRAs, read together
  as one $30,000 model account from that date.
  The quantities, prices and amounts are Mo's own and are recorded nowhere in
  this repository: the page's **Record a trade I made on this name** keeps them
  in his browser alone.
- **Fidelity's screen** — each position was entered as a separate **Limit**
  buy (Day) and a separate **Stop Loss** sell (Good 'til Canceled), not as the
  OTO ticket the plan disclosure prints; one limit buy was cancelled and
  re-entered at a higher limit before it filled; two plain limit buys filled
  under their limit price. The orders show as filled, cancelled and open on the
  same screen with their fill prices.
- **Fidelity's screen** (moved here from the unconfirmed list on 19 November
  2026; this note first labelled it inferred): a separate Good 'til Canceled
  Stop Loss sell on shares bought the same day was accepted on each of the
  three names. The trades sit in two IRAs, so it was accepted in each. It is
  not a confirmation of the OTO form's behaviour.
- **Inferred**: the stops were separate orders, so nothing was attached to
  the buys: between each fill and the entry of its stop the shares had no
  stop. The record's sentences "attached the moment the buy fills" and "live
  from the fill" describe a full fill of an accepted OTO, which these orders
  were not.
- **SpicyStock's advice** — none of the three names carried a SpicyStock
  ticket (the 3 November publication listed each as mechanical grade A under a
  YELLOW market that admits A+ alone, unreviewed); recording a trade on a
  listed name grants no entry permission and changes nothing published, and the
  model's sell-half level and day-3/day-5 sessions beside it are reference
  arithmetic from the record's own rules, not a decision that an exit is due.

Still unconfirmed after this: everything in the unconfirmed list below about
the OTO ticket itself, since no OTO was placed.

## The 5 November 2026 orders: not recorded

The 4 November 2026 publication carried the first three burst tickets, for the
5 November session. The owner's words, as this project's working notes kept
them (`CLAUDE.md`, the 7 November 2026 checkpoint): he bought two of the three
ticketed names on 5 November with the record's stops. That sentence is the
only record of it. How those orders were entered is recorded nowhere in this
repository: the order type (a stop limit, a plain limit or a market order),
whether an OTO was tried, the time, and any message Fidelity gave. Unconfirmed,
and the first thing to ask: one of the two names opened over its buy stop that
morning and the other under it, so what Fidelity did with those two orders may
answer the before-the-open and after-the-open questions of item 2 directly. The
protocol starts there.

## The owner's own practice (recorded 19 November 2026)

The owner described how he enters an order when a ticket's stock is already
trading. Each part is labelled by what supports it. None of it is a SpicyStock
ticket, and where it departs from the ticket the ledger records it as a
deviation (`trade-ledger.md`).

- **Price under the buy stop: the Stop Limit as written.** The owner's
  practice, and SpicyStock's ticket. Consistent with Fidelity's words [4].
  Never observed in his account: the 4 November screen shows Limit buys only,
  so its acceptance as an OTO primary, and before the open, is unconfirmed.
  For a burst ticket it leaves out the plan's lower bound: under the skip line
  the plan says do not place the order.
- **Price between the buy stop and the limit: a Day Limit buy at the ticket's
  limit, then a separate Good 'til Canceled Stop Loss.** The owner's practice.
  It is not a SpicyStock ticket: `plan.fidelity_orders()` has no plain-limit
  fallback, and a limit order has no trigger. Its mechanics are on Fidelity's
  screen (4 November 2026: Day Limit buys accepted, two filled under their
  limit). After the open it is the only way to take the entry the model books
  as "filled at the open". Recorded as a deviation.
- **Price over the limit: skip.** SpicyStock's own plan (the ticket's terms
  and `record.fill()`), and the owner's practice.
- **A separate Day Limit buy and a separate Good 'til Canceled Stop Loss.**
  The owner's practice; Fidelity's screen, 4 November 2026. The stop is not
  attached to the buy: the shares have no stop between the fill and the stop's
  entry.
- **Settled cash falls by the whole purchase as soon as a buy fills.** The
  owner's words. Fidelity's words, read 19 November 2026, to confirm: settled
  cash is reduced by purchases that have not settled yet. To confirm on his
  Balances screen.
- **"A stop that fires before the buy settles risks a good faith violation."**
  The owner's words, and not correct as stated. By Fidelity's definition
  [11, 12] a stop-out is not a violation when the shares were bought with
  settled cash; buying with unsettled proceeds and being stopped out before
  they settle is (item 9).
- **"Three in 12 months restricts the account."** The owner's words;
  Fidelity's words [11] say the same: 90 calendar days of buying with settled
  cash only.

## Unconfirmed, to check in Fidelity's ticket before the first order

No order written as a SpicyStock ticket (a stop limit with an OTO sell stop)
is recorded as placed: the 4 November orders were not, and how the 5 November
orders were entered is not recorded. The protocol in
[`broker-fidelity-protocol.md`](broker-fidelity-protocol.md) checks every item
below in one sitting; the step that checks an item is named in brackets.

- The web ticket and the mobile app each offer Stop Limit with a conditional
  OTO secondary. [U1]
- A Stop Limit is accepted as an OTO's primary order. [U2]
- Where the conditional trade ticket is, and that its type selector is the
  Trade Type drop-down. [U3]
- An OTO accepts a Day primary with a Good 'til Canceled secondary (the
  sources read here disagree; item 6 says what to do if it does not). [U4]
- The price Fidelity compares a buy stop against before the open. A burst
  ticket's buy stop equals its last close, so if Fidelity compares against the
  close it refuses every burst ticket as written, and the ticket is not placed.
  After the open there is nothing to confirm: at or over the last close the buy
  stop is not above the market (item 2). [U5]
- A 10:00 AM ET expiration can be chosen on an OTO's primary order. [U6]
- A day stop limit entered before the open is live from 9:30 AM ET. [U7]
- A triggered buy stop limit that cannot fill at its limit rests for the rest
  of the day (the ticket's own terms assume so). [U8]
- The exact activity assessment fee on a given sale. [U10]
- How long a given deposit takes to clear in the owner's account (Fidelity's
  words say usually four business days). [U11]

Added 19 November 2026:

- Whether either IRA carries limited margin. [U12]
- Whether Fidelity checks a stop price when an order is previewed or only when
  it is placed. [U13]
- That a buy paid for with settled cash and sold the same day is not a good
  faith violation, and what "Cash available to trade" and "Settled cash" each
  include (item 9; read 19 November 2026 off a search summary). [U14]
- The hour at which the proceeds of yesterday's sale read as settled. [U15]
- What Fidelity does to a Good 'til Canceled sell stop on an ex-dividend date.
  [U16]
- How long a Good 'til Canceled order lives (a search summary says 180 days).
  [U17]
- A sell limit for part of a position is accepted beside an open sell stop for
  the whole of it (the model's sell-half at +8% needs one or the other). [U18]
- An OTO whose primary is a plain Limit buy is accepted (the owner's practice
  between the buy stop and the limit would then carry its stop). [U19]
- How the 5 November 2026 orders were entered and what Fidelity did with
  them. [step 0]

No longer on this list: *a sell stop on shares bought the same day is
accepted* was observed on Fidelity's screen on 4 November 2026, for separate
orders in both IRAs (step U9 of the protocol keeps the record of it).

## Sources (search-result excerpts; no page was opened)

Sources 1 to 21 were read on 17 or 18 October 2026.

1. Fidelity, conditional orders overview: https://www.fidelity.com/bin-public/060_www_fidelity_com/documents/Conditional_Orders.pdf
2. Fidelity, conditional trading help: https://www.fidelity.com/webcontent/ap002390-mlo-content/19.09/help/learn_trading_conditional.shtml
3. Fidelity, Active Trader Pro conditional trading help: https://fidelity.com/trading/help/active-trader-pro/conditional-trading
4. Fidelity, order types FAQ: https://www.fidelity.com/trading/faqs-order-types
5. Fidelity, order types and conditions glossary: https://www.fidelity.com/webcontent/ap002390-mlo-content/19.09/help/learn_order_types_conditions.shtml
6. Fidelity, placing orders FAQ: https://www.fidelity.com/trading/faqs-placing-orders
7. Fidelity, Active Trader Pro trade ticket help: https://www.fidelity.com/products/atbt/help/ActiveTraderTools_Trade_Help.html
8. Fidelity, Active Trader Pro extended hours help: https://www.fidelity.com/trading/help/active-trader-pro/extended-hours-trading
9. Fidelity, trading after hours (transcript): https://www.fidelity.com/bin-public/060_www_fidelity_com/documents/learning-center/trading-after-hours-transcript.pdf
10. Fidelity, fractional shares: https://www.fidelity.com/trading/fractional-shares
11. Fidelity, trading restrictions FAQ: https://www.fidelity.com/trading/faqs-trading-restrictions
12. Fidelity, cash account trading restrictions glossary: https://www.fidelity.com/webxpress/help/topics/learn_cash_account_trading_freeride_restrictions.shtml
13. Fidelity, commissions: https://www.fidelity.com/trading/commissions-margin-rates
14. Fidelity, Active Trader Pro transition: https://www.fidelity.com/investing/trading-platforms/active-trader-pro-transition
15. SEC, Section 31 fee-rate advisory 2026-2: https://www.sec.gov/rules-regulations/fee-rate-advisories/2026-2
16. SEC Office of Investor Education and Advocacy, investor bulletin "New T+1 settlement cycle – what investors need to know" (staff material, not a Commission statement): https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins/new-t1-settlement-cycle-what-investors-need-know-investor-bulletin. The SEC press release https://www.sec.gov/news/press-release/2024-62 was seen as a link only; its text was not read and nothing here cites it.
17. FINRA, rule filing SR-FINRA-2026-021: https://www.finra.org/sites/default/files/2026-09/SR-FINRA-2026-021.pdf
18. Fidelity, conditional order types (learning center): https://www.fidelity.com/learning-center/trading-investing/trading/conditional-order-types
19. Fidelity, account FAQ: https://www.fidelity.com/trading/faqs-about-account
20. Fidelity, Active Trader Pro balances help: https://www.fidelity.com/products/atbt/help/ActiveTraderTools_Balances_Help.html
21. Fidelity, Active Trader Pro user guide: https://www.fidelity.com/products/atbt/pdf/ActiveTraderProUserGuide.pdf

**Read 19 November 2026.** Four searches restricted to fidelity.com, each
answered with a summary over several pages and no page opened. The pages the
summaries listed: sources 1, 2, 4, 11, 18, 19 and 20 above, and two not in the
list above, Fidelity's limited margin page
(https://www.fidelity.com/learning-center/trading-investing/trading/limited-margin-trading-ira)
and its page on avoiding cash trading violations
(https://www.fidelity.com/learning-center/trading-investing/trading/avoiding-cash-trading-violations).
Every fact taken from them is marked *read 19 November 2026* and *to confirm*
where it is used.
