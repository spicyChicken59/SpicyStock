# Fidelity: the one-sitting check, the order-entry tables and the cash rules

Dated 19 November 2026. A working note beside
[`broker-fidelity.md`](broker-fidelity.md), written for the outside analyst to
walk the owner through, one step at a time, and to record the answers. It has
three parts:

1. a verification protocol that closes, in one morning at the owner's Fidelity
   screen, every point `broker-fidelity.md` still lists as unconfirmed;
2. order-entry tables that say what to do with a burst ticket and an
   anticipation ticket in each price state, before and after the open;
3. the working rules for a cash account that holds a position three to five
   sessions.

**Who does what.** The owner clicks and decides. The analyst reads the step,
asks for the screen, and records the answer. SpicyStock places, changes and
cancels nothing and reads no account; nothing in this note is an instruction
from SpicyStock to trade.

**What this note is built on.** Nothing here has been run at Fidelity. The
protocol was designed on 19 November 2026 from `broker-fidelity.md` and from
the plan and fill rules in `src/plan.py`, `src/record.py` and `src/morning.py`,
which were read and run for it. The labels are those of `broker-fidelity.md`
(Fidelity's words, a regulator's words, inferred, unconfirmed, SpicyStock's
advice, the owner's words, Fidelity's screen, the owner's practice), and a
number in square brackets is a source in that note's list. One more label is
used in the tables: **the analyst's judgement**, for a row no SpicyStock rule
and no Fidelity source covers.

**This places real orders.** Several steps place a real one-share order and
cancel it. An order that fills is a real position bought with real money.
Whether to run any step is the owner's decision.

## Part 1. The verification protocol

### What to capture at every step

- the date and the time in Central Time;
- the platform: web, mobile app, Fidelity Trader+ or Active Trader Pro;
- an account label of the owner's choosing (for example "IRA 1"), never the
  account number;
- the symbol, and every field exactly as entered;
- the screen at Preview and the screen at Place;
- the exact words of any message Fidelity shows;
- a screenshot file name the ledger row can point to
  ([`trade-ledger.md`](trade-ledger.md), `evidence_file`).

The owner's quantities, prices, balances and account numbers stay with the
owner and the analyst. They are never written into this repository.

### Rules of the sitting

- One share a test, in a liquid stock, paid for with settled cash.
- Preview first. If Preview shows a refusal, that is the answer: copy the
  message. If Preview shows no refusal, press Place: the answer is what Place
  does. Then cancel at once, unless the step says to keep the order.
- Before the open a resting stop or stop limit does nothing (inferred from
  Fidelity's words [8, 9]), so an order placed and cancelled before 8:30 AM CT
  should not fill. Record it if one does.
- Confirm every cancel reads Cancelled. Fidelity's words [2]: an order pending
  cancel can still fill.
- A result is what the screen showed that day on that platform. Record it as
  such; do not generalise from one stock to a rule.

### Step 0, no order: the 5 November orders

Ask the owner how the two orders of 5 November 2026 on ticketed burst names
were entered: the order type, the time, whether an OTO was tried, and any
message Fidelity showed. Read them off Activity & Orders if the screen still
lists them. One of those names opened over its buy stop and the other under it
(`broker-fidelity.md`), so the answer may settle U5 and U7 before anything is
placed. Record it in the ledger as two positions with their order rows.

### Step 1, no order: balances and account features

| step | what to read | what the outcome changes |
|---|---|---|
| U12 | In each IRA, under account features: is margin or limited margin on or off? | Off: the settled-cash rules of Part 3 apply strictly. On: Fidelity's words (read 19 November 2026, to confirm) say unsettled funds can be traded without good faith violations; record it and still read Settled cash before a buy. |
| U14 | In each IRA, on Balances: "Settled cash" and "Cash available to trade". Read both again right after the sitting's test buy and right after its sale. Open Fidelity's trading-restrictions page [11] on the owner's own screen and copy its example of a same-day sale. | Confirms or corrects the two search-summary facts of item 9: that a buy paid for with settled cash and sold the same day is not a good faith violation, and that the gap between the two balances is unsettled money. |
| U17 | On Activity & Orders, the expiry date Fidelity shows on an open Good 'til Canceled stop. | How long a protective stop lives before it must be entered again (a search summary says 180 days). |
| U16 | In Fidelity's help or from Fidelity support: what happens to a Good 'til Canceled sell stop on an ex-dividend date. | Whether a stop near the price needs checking before an ex-dividend date ([`event-coverage.md`](event-coverage.md), item 9). |

### Part A, before the open (7:30 to 8:25 AM CT)

| step | what to do | outcomes and what each changes |
|---|---|---|
| U3 | Find the conditional trade ticket and its type selector. | Found: record the path, per platform. Not found on a platform: orders as written are placed from the platform that has it. |
| U1 | In it choose One-Triggers-the-Other. Do it on the web and on the mobile app. | Missing on mobile: an OTO is placed from the web only. No OTO anywhere: every ticket uses the separate-order path (the buy alone, then a Good 'til Canceled stop after the fill; rule (a) of Part 2). |
| U2 | Primary: Buy 1, Stop Limit. Secondary: Sell 1, Stop Loss. | A Stop Limit is not offered as the primary: the separate-order path. |
| U4 | Primary Time in Force Day, secondary Good 'til Canceled. Preview, then Place. | Accepted: the ticket's form works as written. Refused: `broker-fidelity.md` item 6 applies: the buy alone as the Day stop limit, a separate Good 'til Canceled stop after the fill; never a Day stop, never a Good 'til Canceled buy. |
| U6 | On the primary, look for an expiration time and set 10:00 AM ET (9:00 AM CT). | Offered: set it on every ticket. Not offered: an alarm at 8:59 AM CT and a manual cancel. |
| U19 | The same OTO with a plain Limit buy as the primary. | Accepted: the owner's own practice between the buy stop and the limit can carry its stop from the fill. Refused: that practice keeps its gap between the fill and the stop's entry. |
| U5 | The price a buy stop is compared with before the open. Five one-share Buy Stop Limit orders, each with its limit 1% over its stop, on two stocks chosen that morning from Fidelity's own pre-market quotes: stock X is quoted above its last close C by more than a cent, stock Y below its last close. **A1** on X, stop exactly C. **A2** on X, stop C plus one cent. **A3** on X, stop five cents over the pre-market ask. **B1** on Y, stop exactly C. **B2** on Y, stop between the pre-market ask and C. | Read the five answers against the table below. |
| U13 | Note, for each test above, whether the refusal came at Preview or only at Place. | Preview refuses: later checks need no order. Only Place refuses: a check needs a one-share order, cancelled at once. |

How to read U5. A burst ticket's buy stop is its last close, so it is test A1
when the stock is quoted above its close and test B1 when it is quoted below.

| A1 | A2 | A3 | B1 | B2 | what Fidelity compares the stop with | what it means for a burst ticket before the open |
|---|---|---|---|---|---|---|
| accepted | accepted | accepted | accepted | accepted | nothing, before the open | It can be entered as written. Keep A1 through the open (U7) to see what an open over the stop does. |
| accepted | accepted | accepted | accepted | refused | the last close, and "at or above" is allowed | It can be entered as written whatever the pre-market quote. Keep A1 through the open (U7). |
| refused | accepted | accepted | refused | refused | the last close, and the stop must be strictly above it | It cannot be entered before the open as written. It can be entered only after the open, while the stock trades under its last close (Part 2). |
| refused | refused | accepted | accepted | accepted | the pre-market quote | It can be entered before the open only while the stock is quoted under its last close. |
| any other pattern | | | | | not established | Record the five answers and the messages exactly. Change nothing on one sitting's evidence. |

Cancel every test order before 8:25 AM CT except the one kept for U7: A1 if
it was accepted, since it is the burst ticket's own case, and otherwise A3.
Keep it as an OTO with its sell stop if U4 was accepted.

### Part B, the entry window (8:30 to 9:00 AM CT)

| step | what to do | outcomes and what each changes |
|---|---|---|
| U5b | On any liquid stock, preview Buy 1, Stop Limit, with the stop ten cents under the current ask. | A refusal is expected (Fidelity's words [4]). Copy the message: it is what the owner will see when a burst ticket is entered after its stock has opened over the buy stop. If it is accepted, record that: item 2 of `broker-fidelity.md` would need a correction. |
| U7 | Watch the order kept from Part A at the open: its status, the time it triggered, the fill price, and whether the OTO's sell stop then shows as an open order. | Triggered and filled at or near the open: a resting stop limit is live from the open, and the model's "filled at the open" can be taken by an order entered before it. Not live, or refused at the open: record the message. Then keep the share with its stop or sell it, as the owner decides. |
| U8 | Only if it happens: an order that triggered and did not fill at its limit. Does it show as an open limit order for the rest of the day? | Yes: the ticket's own terms hold, and an unfilled order must be cancelled by hand at 9:00 AM CT (or by U6). |
| U9 | Done. Fidelity's screen, 4 November 2026: a separate Good 'til Canceled Stop Loss on shares bought the same day was accepted. | Keep the screenshot with the ledger. |
| U18 | With a real position of two or more shares and its open Good 'til Canceled stop for all of them: preview Sell half, Limit, at the plan's sell-half price. If the sitting leaves no such position, do this on the next real one. | Accepted: the sell-half can rest beside the stop, and the stop's quantity must be cut when it fills. Refused: the sell-half is worked by a price alert and a manual order. Whether an order-cancels-the-other pair does it is untested. |
| U10 | Read the fee lines on the first sale's confirmation. | The fee figures to enter in the ledger and in the site's private report. |
| U11 | After any deposit, read both balances each day until they are equal. | How long a deposit takes to clear in this account. |
| U15 | On the morning after the sitting's sale, note the time its proceeds read as settled. | The earliest hour a next buy can be funded by them. |

### After the sitting

Write each confirmed fact into `broker-fidelity.md` as a dated revision, with
the date, the platform and the screen it was read on, and move it off that
note's unconfirmed list. What each answer decides:

- **U5** decides whether a burst ticket is entered before the open, in which
  case the model's fill at the open can be reproduced, or only after it by the
  burst table of Part 2.
- **U1, U2 and U4** decide between the OTO as written and two separate orders.
- **U6** decides how the 9:00 AM CT cancel is done.
- **U18** decides how the sell-half at +8% is worked.
- **U12 and U14** decide how strictly the settled-cash rules of Part 3 bind.

## Part 2. Order entry by price state

The state words are the ones the morning receipt prints for a ticket
(`docs/morning.json`, `rows[].price_checks`, from `price_state()` in
`src/morning.py`) and the daily brief lists with each ticket's own boundaries
(`order_entry.price_states`). A state says where a recent price sits against
the ticket's lines. It is never an entry or a cancellation instruction by
itself. `unknown` means no recent price was read: look at the quote on
Fidelity's screen.

The entry window is the first 30 minutes of the session, 8:30 to 9:00 AM CT on
a full session (`run.timing.opens_at` and `cutoff_at` in the record; the brief's
`identity.entry_window`). The share figures are the first-day opens of the
13,599 counterfactual burst tickets described in `broker-fidelity.md` item 2:
opens on daily bars, 40 nights, not published tickets.

### A burst ticket

Its lines, from the plan: the stop; the skip line (2% under the close,
`skip_if_open_below`); the trigger, which is the buy stop and equals the last
close; the limit; the day-2 line (4% over the close, `day2_spent_above`); and
8% over the close (`extended_above`). On a tight burst the stop can sit above the skip
line (it does on about a third of the counterfactual tickets), and then no
price is in `below_entry_floor`.

| price state | where the price is | before the open | in the entry window | what the model books | share of first-day opens |
|---|---|---|---|---|---|
| `below_stop`, `below_entry_floor` | at or under the stop, or over it and under the skip line | Do not place the order. Cancel one that is resting: it would still trigger if the price recovered. (The plan's own terms.) | The same. | Not filled. Uncertain (`open_below_skip`) if the day later recovered through the trigger. | 7.9% (6.1% `below_stop`, 1.8% `below_entry_floor`) |
| `below_trigger` | over the stop and at or over the skip line, under the trigger | The buy stop is above the quote. Whether Fidelity takes it before the open is U5. | Enter the ticket as written: Buy, Stop Limit, stop at the trigger, limit at the limit, Day; OTO Sell, Stop Loss at the stop, Good 'til Canceled. It buys nothing until a trade at the trigger. (SpicyStock's ticket, and the owner's practice.) | Not filled when the day never reached the trigger. When it did: filled at the trigger, or at the crossing minute's open over it, if the retained minute bars show the cross inside the first 30 minutes, and not filled if they show it later. Uncertain (`trigger_timing`, or `stop_sequence` when the day's low also reached the stop) when no minute bars were retained. | 37.3% |
| `within_published_band` | from the trigger through the limit | The buy stop is not above the quote. Expect a refusal unless U5 showed otherwise. An order already accepted and resting triggers at the open. | The ticket cannot be entered as written (inferred from Fidelity's words [4]). SpicyStock offers no other order. The owner's practice, a deviation: Buy, Limit at the ticket's limit, Day; then at once a separate Sell, Stop Loss at the stop, Good 'til Canceled. | Filled at the open, at the open's price. This assumes an order resting before the open. | 40.4% (3.4% exactly at the trigger, 37.0% over it) |
| `above_limit` | over the limit, up to the day-2 line | Do not place it. | Skip. A resting order has triggered and is now a live limit order at the limit: cancel it rather than let it fill on a pullback. (The plan's own terms.) | Not filled. Uncertain (`open_above_limit`) if the day traded back to the limit. | 12.7% |
| `above_day2_extension` | over the day-2 line | Do not place it: day 2 is spent, and more than 8% over the close the plan says he would be selling. | Skip. Cancel a resting order. | As the row above. | 1.7% |

### An anticipation ticket

Its lines: the stop (the lowest low of the last three sessions,
`plan.STOP_LOOKBACK_SESSIONS`); the trigger, a few cents over the top of the
box and above the last close; the limit, 1% over the trigger
(`plan.TRIGGER_LIMIT_PCT`); and the gap line, 2% over the close
(`gap_ok_above`). It has no skip line and no day-2 line, so `below_trigger` and
`above_day2_extension` never apply to it. No counterfactual shares exist for
it. Of the 19 anticipation tickets published through 17 November 2026, 16 were
not filled, 2 were filled inside the window (their minute bars put the cross at
9:33 and 9:40 AM ET) and 1 is uncertain (it opened over its limit).

| price state | where the price is | before the open | in the entry window | what the model books |
|---|---|---|---|---|
| `below_stop` | at or under the stop | The plan has no rule for it. The analyst's judgement: the box has broken down, do not place the order. | The same. | The model does not read this state: it reads only whether and when the trigger was reached, as in the next row. |
| `below_entry_floor` | over the stop, under the trigger (the usual state) | Enter the ticket as written: the buy stop is above both the quote and the last close, so either reading of Fidelity's rule accepts it. | Enter it as written. Cancel it at 9:00 AM CT if it has not filled: two of the 16 unfilled tickets reached their triggers later that morning (10:05 and 11:00 AM ET), after the window. | Filled at the trigger, or at the crossing minute's open, when the minute bars show the cross inside the window. Not filled otherwise. |
| `within_published_band` | from the trigger through the limit | A resting order triggers at the open and fills up to the limit. If the quote is over the gap line the plan says "gapped: catalyst check before buying": do the check before 8:28 AM CT and cancel the resting order if it does not come out clean. | Not resting: the stop is not above the market, so the ticket cannot be entered as written. The owner's practice, a deviation: a Day Limit buy at the limit, then a separate Good 'til Canceled stop. | Filled at the open when it opened in the band. |
| `above_limit` | over the limit | Do not place it. | Skip. Cancel a resting order: it has triggered and is a live limit order. | Not filled. Uncertain (`open_above_limit`) if the day traded back to the limit. |

### Rules for every ticket

a. **No OTO, or the Day and Good 'til Canceled pair refused.** SpicyStock's
   advice (`broker-fidelity.md` item 6): the buy alone, then a separate Sell,
   Stop Loss, Good 'til Canceled order for the filled shares as soon as it
   fills. Inferred by symmetry with Fidelity's words [4], and not read for
   the sell side: if the price is already at or under the stop, a sell stop
   there is on the wrong side of the market and is likely to be refused. Then
   the choice is to sell or to hold without a stop, and it is the owner's.
b. **A part fill.** Fidelity's words [1, 2]: the OTO's stop is not released.
   SpicyStock's advice: place a separate Good 'til Canceled stop for the
   filled shares. If the rest of the buy fills later, the OTO's own stop is
   released for the whole quantity: cancel one of the two so the open sell
   quantity equals the shares held.
c. **9:00 AM CT.** Cancel any unfilled remainder and confirm it reads
   Cancelled. Fidelity's words [2]: an order pending cancel can still fill and
   release its secondary.
d. **The close of day 1.** The plan raises the stop to the entry day's low
   when that is higher than the stop (`plan.follow()`). At Fidelity that is a
   cancel and replace of the Good 'til Canceled stop.
e. **Notes that are not the ticket.** The chart reader's entry note and an
   anticipation plan's `open_entry` sentence (a market-on-open note for the
   top names) sit beside the ticket in the record. They are not the ticket.
   The brief prints them under `not_the_ticket`.
f. **Every departure is logged.** An order that is not the ticket as written
   (a plain limit, a separate stop, another quantity, another stop price, an
   entry after the window, a name with no ticket) is a deviation in the ledger,
   with its kind ([`trade-ledger.md`](trade-ledger.md)).

## Part 3. A cash account holding three to five sessions

The facts, each with its label, are in `broker-fidelity.md` items 7 to 10.
In short:

| fact | label and source |
|---|---|
| US stock trades settle one business day after the trade (T+1). | a regulator's words [16] |
| A good faith violation is a security bought without sufficient settled funds and sold before it is fully paid for, even if payment arrives before settlement. | Fidelity's words [11, 12] |
| Three good faith violations in 12 months restrict the account for 90 calendar days to buying with settled cash only. | Fidelity's words [11] |
| Settled cash is the part of core cash that can buy and sell without a good faith violation; an uncollected deposit may be left out, usually for four business days. | Fidelity's words [19, 20] |
| Limit and reserve orders are the only order types available before the open and after the close, and Good 'til Canceled orders are not available there. | Fidelity's words [8, 9] |
| Fractional and dollar-amount orders are market or limit orders, day only, so a ticket is whole shares. | Fidelity's words [10]; inferred |
| $0 commission; an activity fee of $0.01 to $0.03 per $1,000 sold; the SEC's Section 31 fee of $20.60 per million sold; FINRA's trading activity fee $0 until 31 December 2026. | Fidelity's words [13, 10]; a regulator's words [15, 17] |
| A buy paid for with settled cash and sold the same day is not a good faith violation. | inferred from [11, 12]; Fidelity's words read 19 November 2026, to confirm (U14) |
| "Cash available to trade" includes unsettled sale proceeds and can exceed "Settled cash". | Fidelity's words read 19 November 2026, to confirm (U14) |
| Three cash liquidation violations or one free riding violation in 12 months restrict the account the same way. | Fidelity's words read 19 November 2026, to confirm |
| Whether either IRA has limited margin; the hour proceeds read as settled; whether any day-trade count reaches a cash IRA. | unconfirmed (U12, U15) |

The working rules. Each is SpicyStock's advice unless it says otherwise.

1. Before every buy, read Settled cash in the IRA that will hold the trade and
   write it in the ledger row (`settled_cash_before`).
2. Never fund a buy from the proceeds of a sale made that day. Mark each buy's
   funding in the ledger (`funded_by`).
3. A stop-out on day 1 is a loss. It is not a violation when the buy used
   settled cash (inferred; U14 confirms it).
4. The model sizes one $30,000 account. The money is in two IRAs (the owner's
   words) and SpicyStock does not know the split. A ticket's cost (the plan's
   `position_usd`, the brief's `cost`) has to fit the settled cash of the one
   IRA that holds it; if it does not, the smaller whole number of shares that
   fits is a deviation of kind `smaller_quantity`.
5. Proceeds of a sale settle on the next business day (a regulator's words
   [16]) and are settled cash from then (inferred); the hour is unconfirmed
   (U15). A position sold on day 3 or day 5 therefore funds a buy no earlier
   than the next session.
6. A ticket is whole shares; do not turn it into a dollar-amount order.
7. A 90-day restriction would impose exactly rules 1 and 2, so following them
   costs nothing that a restriction would not.
