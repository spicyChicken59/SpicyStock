# Placing a SpicyStock ticket at Fidelity

Dated 17 October 2026. The owner named Fidelity as the broker on 17 October
2026. This note maps a published SpicyStock ticket onto Fidelity's order entry
and says what Fidelity does with each part of it. SpicyStock places, changes and
cancels nothing; it reads no account and no fill.

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
   the fill, that assumes a full fill; if the buy fills in part, place a
   separate Sell, Stop Loss, Good 'til Canceled order for the filled shares at
   the ticket's stop, confirm Fidelity accepts it on shares bought that day
   (unconfirmed, below), and check that no second sell stop remains for shares
   you do not hold (a late fill of the rest releases the OTO's own stop beside
   yours). The page prints this rule and this advice, each labelled, beside
   every order it prints: the plan disclosure's ticket and its recorded copy
   after the window, the tickets sheet, a Burst's action card, a setting-up
   stock's action bar, the comparison, the decision summary's entry (a
   setting-up stock's only while its action bar, on the same screen, does not
   offer the order), the model
   exits, a saved setup's archived order and an archived original's status.
   The private handoff prints it in its readback, and the mail after each block
   of orders.

2. **A buy stop must be priced above the current market.** Fidelity's words
   [4]: buy stop loss and buy stop limit orders must be entered at a price
   above the current market price. An anticipation ticket's trigger is a few
   cents over the top of its box (the larger of $0.02 and 0.1% of the close,
   `plan.TRIGGER_CENTS` and `plan.TRIGGER_FRACTION`), above its last close. A
   burst ticket's trigger IS the burst session's close: its buy stop is never
   above the last close. Which price Fidelity takes as the current market
   before the open (the close, or an extended-hours trade) is unconfirmed; if it
   is the close, Fidelity refuses every burst ticket as written. If Fidelity
   refuses the stop because it is not above the current price, the ticket
   cannot be placed as written: SpicyStock's ticket has no plain-limit
   fallback, and no other order type is placed on its authority.

3. **What triggers a stop.** Fidelity's words [4]: an equity stop placed with
   Fidelity is triggered by a round-lot trade of 100 shares or more, or a print
   in the security. Fidelity's words [1]: the market centers stop orders are
   routed to may apply price bands around the best bid and offer.

4. **A stop limit becomes a limit when it triggers.** Fidelity's words [4]: it
   then fills in whole, in part, or not at all. The ticket's own terms say the
   rest: an open above the limit does not fill at the open, but the resting
   order stays live and can fill on a pullback later in the day (unconfirmed at
   Fidelity, below).

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
   both, so neither statement can be tied to one page. SpicyStock's advice: if the
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

## Unconfirmed, to check in Fidelity's ticket before the first order

- The web ticket and the mobile app each offer Stop Limit with a conditional
  OTO secondary.
- A Stop Limit is accepted as an OTO's primary order.
- Where the conditional trade ticket is, and that its type selector is the
  Trade Type drop-down.
- An OTO accepts a Day primary with a Good 'til Canceled secondary (the
  sources read here disagree; item 6 says what to do if it does not).
- The price Fidelity compares a buy stop against before the open. A burst
  ticket's buy stop equals its last close, so if Fidelity compares against the
  close it refuses every burst ticket as written, and the ticket is not placed.
- A 10:00 AM ET expiration can be chosen on an OTO's primary order.
- A day stop limit entered before the open is live from 9:30 AM ET.
- A triggered buy stop limit that cannot fill at its limit rests for the rest
  of the day (the ticket's own terms assume so).
- A sell stop on shares bought the same day is accepted.
- The exact activity assessment fee on a given sale.
- How long a given deposit takes to clear in the owner's account (Fidelity's
  words say usually four business days).

## Sources (search-result excerpts; no page was opened)

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
