# Placing a SpicyStock ticket at Fidelity

Dated 17 October 2026. The owner named Fidelity as the broker on 17 October
2026. This note maps a published SpicyStock ticket onto Fidelity's order entry
and says what Fidelity does with each part of it. SpicyStock places, changes and
cancels nothing; it reads no account and no fill.

**How this was read.** The machine that wrote this note could not open
fidelity.com, sec.gov or finra.org (its proxy refuses them), so every fact below
was read off search-result excerpts of those pages, not the pages themselves.
Each fact carries one label, and a fact in Fidelity's words names the source it
was read from by its number under **Sources**:

- **Fidelity's words** — the excerpt quotes or summarises a fidelity.com page;
- **inferred** — it follows from Fidelity's words, but no excerpt says it;
- **unconfirmed** — no source read here says it;
- **SpicyStock's advice** — what this note asks the reader to do, which is not
  Fidelity's.

Confirm each in Fidelity's own ticket before the first order. A fact confirmed
there belongs in a later dated revision of this note, with the date and the
screen it was read on.

## The ticket, field by field

A stock's plan disclosure and the tickets sheet print a SpicyStock ticket in
Fidelity's field order, with a copy button, and the plan disclosure reads it
back in one line:
`Buy N SYM stop-limit: stop TRIGGER limit LIMIT, day · OTO sell N SYM stop-loss STOP GTC`.
A Burst's action card carries the same ticket with its own **Copy order**. The
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
| OTO | Conditional order | One-Triggers-the-Other (OTO) |
| then: sell | secondary Action | Sell, the same quantity |
| then: stop-loss | secondary Order Type | Stop Loss (a stop-market order, never a stop limit: a gap through a limit would leave it unfilled) |
| stop | secondary Stop Price | the ticket's stop |
| GTC | secondary Time in Force | Good 'til Canceled |

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
   released for the whole quantity. SpicyStock's advice: the ticket's stop
   terms assume a full fill; if the buy fills in part, place a separate Sell,
   Stop Loss, Good 'til Canceled order for the filled shares at the ticket's
   stop, confirm Fidelity accepts it on shares bought that day (unconfirmed,
   below), and check that no second sell stop remains for shares you do not
   hold (a late fill of the rest releases the OTO's own stop beside yours). The page, the private handoff and the mail
   print this rule and this advice beside every order, each labelled as which
   it is.

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

6. **Stops do nothing in extended hours.** Fidelity's words [8, 9]: limit and
   reserve orders are the only order types available in the pre-market and
   after-hours sessions, and good 'til canceled orders are not available in
   them. Inferred: neither leg of a ticket acts before the open or after the
   close.

7. **Whole shares.** Fidelity's words [10]: fractional-share and dollar-amount
   orders are market or limit orders, day only. Inferred: a stop limit with an
   OTO secondary needs a whole number of shares. A SpicyStock ticket is always
   a whole number of shares.

8. **Settled cash.** Fidelity's words [11, 12]: a security bought without
   sufficient settled funds and sold before it is fully paid for is a good faith
   violation, even if payment arrives before settlement; three good faith
   violations in twelve months restrict the account to buying with funds on
   hand (core balance, received deposits, settled sale proceeds) for 90 days.
   The SEC's words [16]: US stocks settle one business day after the trade (T+1
   since 28 May 2024). A ticket's stop can sell on the day the buy fills, so
   SpicyStock's advice is to buy with settled cash only: the Morning desk asks
   for settled cash and never reads it from the account. How long a new deposit
   takes to count as funds on hand is unconfirmed.

9. **Costs.** Fidelity's words [13]: $0 online commission on US stocks; a sale
   carries an activity assessment fee of $0.01 to $0.03 per $1,000. The SEC's
   words [15]: the Section 31 fee on sales is $20.60 per million dollars from
   4 April 2026. FINRA's filing [17]: the trading activity fee is $0 from
   1 October to 31 December 2026 and the previous rates resume in January 2027.
   Enter the fees your confirmation shows in the private report's fee fields;
   SpicyStock never computes them.

10. **Where.** Fidelity's words [14]: Active Trader Pro begins to be retired in
    2027, Fidelity Trader+ replacing it. Whether the web ticket and the mobile
    app both offer a Stop Limit with an OTO secondary is unconfirmed.

## Unconfirmed, to check in Fidelity's ticket before the first order

- The web ticket and the mobile app each offer Stop Limit with a conditional
  OTO secondary.
- A Stop Limit is accepted as an OTO's primary order.
- The price Fidelity compares a buy stop against before the open. A burst
  ticket's buy stop equals its last close, so if Fidelity compares against the
  close it refuses every burst ticket as written, and the ticket is not placed.
- A 10:00 AM ET expiration can be chosen on an OTO's primary order.
- A day stop limit entered before the open is live from 9:30 AM ET.
- A triggered buy stop limit that cannot fill at its limit rests for the rest
  of the day (the ticket's own terms assume so).
- A sell stop on shares bought the same day is accepted.
- The exact activity assessment fee on a given sale.
- How long a new deposit takes to count as settled cash.

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
16. SEC, T+1 settlement (press release 2024-62): https://www.sec.gov/newsroom/press-releases/2024-62
17. FINRA, rule filing SR-FINRA-2026-021: https://www.finra.org/sites/default/files/2026-09/SR-FINRA-2026-021.pdf
