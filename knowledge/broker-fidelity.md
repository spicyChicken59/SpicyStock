# Placing a SpicyStock ticket at Fidelity

Dated 17 October 2026. The owner named Fidelity as the broker on 17 October
2026. This note maps a published SpicyStock ticket onto Fidelity's order entry
and says what Fidelity does with each part of it. SpicyStock places, changes and
cancels nothing; it reads no account and no fill.

**How this was read.** The machine that wrote this note could not open
fidelity.com (its name does not resolve there), so every Fidelity fact below was
read off search-result excerpts of fidelity.com pages, not the pages themselves.
Each fact carries one of three labels:

- **Fidelity's words** — the excerpt quotes a fidelity.com page;
- **inferred** — it follows from Fidelity's words, but no excerpt says it;
- **unconfirmed** — no source read here says it.

Confirm each in Fidelity's own ticket before the first order. A fact confirmed
there belongs in a later dated revision of this note, with the date and the
screen it was read on.

## The ticket, field by field

A SpicyStock ticket is printed in Fidelity's field order (the Morning desk and a
stock's plan disclosure carry it, with a copy button):
`Buy N SYM stop-limit: stop TRIGGER limit LIMIT, day · OTO sell N SYM stop-loss STOP GTC`.

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
   Fidelity's words: the secondary order "is released to the market only if
   the primary order executes in full"; its Active Trader Pro help says the same
   of OTOCO. So a buy that fills in part leaves the shares that did fill with no
   stop. If the buy fills in part, place a separate Sell, Stop Loss, Good 'til
   Canceled order for the filled shares at the ticket's stop. What happens to
   the held secondary when the rest of the buy is cancelled or expires is
   unconfirmed; check that no second sell stop remains for shares you do not
   hold.

2. **A buy stop must be priced above the current market.** Fidelity's words:
   buy stop-loss and buy stop-limit orders are priced above the current market.
   An anticipation ticket's trigger is the top of its box, above its last close.
   A burst ticket's trigger is the burst session's close. Which price Fidelity
   takes as the current market before the open (the close, or an
   extended-hours trade) is unconfirmed. If Fidelity refuses the stop because it
   is not above the current price, the ticket cannot be placed as written:
   SpicyStock's ticket has no plain-limit fallback, and no other order type is
   placed on its authority.

3. **What triggers a stop.** Fidelity's words: an equity stop placed with
   Fidelity is triggered by a round-lot trade of 100 shares or more, or a print
   in the security. Market centers may also apply price bands around the best
   bid and offer.

4. **A stop limit becomes a limit when it triggers.** Fidelity's words: it
   then fills in whole, in part, or not at all. The ticket's own terms say the
   rest: an open above the limit does not fill at the open, but the resting
   order stays live and can fill on a pullback later in the day.

5. **A day order and the entry window.** Fidelity's words: a day order entered
   outside market hours is subject to the conditions at the reopen, and day
   orders expire at 4:00 PM ET (3:00 PM CT). Inferred: a stop limit entered
   before the open is live from the 9:30 AM ET (8:30 AM CT) open. The plan's
   entry window is 8:30 to 9:00 AM CT: if the buy has not filled by 9:00, cancel
   it yourself; Fidelity will not.

6. **Stops do nothing in extended hours.** Fidelity's words: only limit
   orders (and, in Active Trader Pro, reserve orders) trade in the pre-market
   and after-hours sessions; every other order type is ineligible there, and
   good 'til canceled orders are not available in them. Neither leg acts before
   the open or after the close.

7. **Whole shares only.** Fidelity's words: fractional-share and dollar-amount
   orders are market or limit orders, day only. A SpicyStock ticket is always a
   whole number of shares.

8. **Settled cash.** Fidelity's words: a security bought without sufficient
   settled funds and sold before it is fully paid for is a good faith
   violation, even if payment arrives before settlement; three good faith
   violations in twelve months restrict the account to buying with funds on
   hand (core balance, received deposits, settled sale proceeds) for 90 days. US stocks settle
   one business day after the trade (T+1 since 28 May 2024, SEC). A ticket's
   stop can sell on the day the buy fills, so buy with settled cash only: the
   Morning desk asks for settled cash and never reads it from the account.
   How long a new deposit takes to count as funds on hand is unconfirmed.

9. **Costs.** Fidelity's words: $0 online commission on US stocks; a sale
   carries an activity assessment fee of $0.01 to $0.03 per $1,000. The SEC's
   Section 31 fee on sales is $20.60 per million dollars from 4 April 2026 (SEC
   fee-rate advisory, read as a search excerpt). FINRA's trading activity fee
   is $0 from 1 October to 31 December 2026 (SR-FINRA-2026-021, read as a
   search excerpt) and resumes on 1 January 2027. Enter the fees your
   confirmation shows in the private report's fee fields; SpicyStock never
   computes them.

10. **Where.** Fidelity's words: Active Trader Pro begins to be retired in
    2027, Fidelity Trader+ replacing it. Whether the web ticket and the mobile
    app both offer a Stop Limit with an OTO secondary is unconfirmed.

## Unconfirmed, to check in Fidelity's ticket before the first order

- The web ticket and the mobile app each offer Stop Limit with a conditional
  OTO secondary.
- A Stop Limit is accepted as an OTO's primary order.
- The price Fidelity compares a buy stop against before the open.
- What happens to the held secondary when the primary fills in part and its
  remainder is cancelled or expires.
- A day stop limit entered before the open is live from 9:30 AM ET.
- A triggered buy stop limit that cannot fill at its limit rests for the rest
  of the day (the ticket's own terms assume so).
- A sell stop on shares bought the same day is accepted.
- The exact activity assessment fee on a given sale.
- How long a new deposit takes to count as settled cash.

## Sources (search-result excerpts; no page was opened)

- Fidelity, conditional orders overview: https://www.fidelity.com/bin-public/060_www_fidelity_com/documents/Conditional_Orders.pdf
- Fidelity, Active Trader Pro conditional trading help: https://fidelity.com/trading/help/active-trader-pro/conditional-trading
- Fidelity, general order types FAQ: https://www.fidelity.com/trading/faqs-order-types
- Fidelity, order types and conditions glossary: https://www.fidelity.com/webcontent/ap002390-mlo-content/19.09/help/learn_order_types_conditions.shtml
- Fidelity, placing orders FAQ: https://www.fidelity.com/trading/faqs-placing-orders
- Fidelity, trading restrictions FAQ: https://www.fidelity.com/trading/faqs-trading-restrictions
- Fidelity, cash account trading restrictions glossary: https://www.fidelity.com/webxpress/help/topics/learn_cash_account_trading_freeride_restrictions.shtml
- Fidelity, Active Trader Pro extended hours help: https://www.fidelity.com/trading/help/active-trader-pro/extended-hours-trading
- Fidelity, fractional shares: https://www.fidelity.com/trading/fractional-shares
- Fidelity, commissions: https://www.fidelity.com/trading/commissions-margin-rates
- SEC, Section 31 fee-rate advisory 2026-2: https://www.sec.gov/rules-regulations/fee-rate-advisories/2026-2
- SEC, T+1 settlement (press release 2024-62): https://www.sec.gov/newsroom/press-releases/2024-62
