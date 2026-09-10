# Closing the loop — a brokerage account as the missing input

*A design, not a shipped feature. Everything below is unbuilt unless it says
otherwise, and the two facts the whole design rests on were checked rather
than remembered.*

## The loop is open, and that is the largest thing wrong with this project

The screener scans, scores, mails a shortlist and archives every burst with
forward returns. What it has never known is **what happened next in a real
account**. `forward_returns()` divides later closes by the burst close and by
the next open; both are paper prices off one venue's prints, with no
slippage, no partial fill, no position size and no exit rule. The contract
says so honestly. But it means the north star — *do its picks beat the
alternative* — is answered about a portfolio nobody holds.

There is a second, quieter gap. The record cannot distinguish three different
failures, and they need three different fixes:

| what went wrong | what it looks like in the record today |
|---|---|
| **Screener error** — the picks were bad | picks underperform the control |
| **Execution error** — good picks, bad entries or exits | picks underperform the control |
| **Selection error** — the human took the bad ones and skipped the good ones | picks *outperform* the control, and the account still loses |

The third is invisible. On a night when the shortlist is right and the reader
buys something else, the ledger records a success. An account balance is the
only thing that tells those three apart, and it is the one input this system
has never had.

## What Fidelity can and cannot do

Checked, not assumed:

- **Fidelity publishes no retail order-placement API.** Third-party
  aggregators that do reach Fidelity — SnapTrade, and Akoya, which Fidelity
  itself co-founded — carry *consumer-permissioned, read-only* account data.
  SnapTrade's own integration page states it cannot place trades at Fidelity.
- **Read-only is enough for everything in this document.** Nothing here needs
  to send an order to Fidelity. Orders stay where they are: placed by hand, or
  through the Alpaca adapter this repo already has in `src/broker_bridge/`,
  which is built around a preview the user must confirm.

So the shape is fixed by the constraint, and it is a better shape anyway:

```
Fidelity  --(read-only OAuth: positions, cash, transactions)-->  SpicyStock
SpicyStock  --(a ranked plan a human executes)-->  Fidelity
```

The system proposes. It never disposes. That is the same boundary
`knowledge/strategy.md` already draws for the scoring model, extended to the
account.

## What arrives, and what each field unlocks

An aggregator's brokerage endpoints give roughly: account balances and buying
power; open positions with quantity and cost basis; and a transaction history
of fills with date, side, quantity and price.

| input | what it makes possible |
|---|---|
| open positions | the scan stops proposing a name already held, and starts *managing* it |
| cost basis and fill price | the paper entry in the ledger gains a real one beside it |
| transaction history | every past pick can be marked taken or skipped, which is what separates selection error from screener error |
| cash and buying power | position size stops being hypothetical, so the ranking can be by expected contribution rather than by score |

## The three things it changes

### 1. The morning run becomes an exit desk

Today `morning` re-presents what the evening published and scans nothing. It
is the least valuable of the two runs, and with positions it becomes the most
valuable, because **this strategy's edge is mostly an exit rule**. A momentum
burst is a 3-to-5 session move; the entry is the easy half and the review
window is the half that decides the outcome.

With positions in hand the morning mail becomes, before the open:

> You hold four. AMBA is session 4 of its burst, +6.2% from your fill, inside
> the claimed band. ASO is session 7, past the window, +0.4% — the burst is
> over whatever the chart says. GME is −3.1% and below the burst bar's low,
> which is where the stop was.

Every one of those sentences is computable from data the system already
fetches, plus a fill price. None of it exists today.

### 2. Position sizing from the strategy's own rules

`src/broker_bridge/config.py` already carries the risk frame — a position
cap, a per-trade risk percent, a notional ceiling, a spread limit. What it
lacks is the account to apply them to. With buying power and a stop derived
from the burst bar's low, a shortlist row stops being "score 7.5" and becomes
"score 7.5, risk 1% of the account, 84 shares, stop at $46.10, $310 at risk".

That also fixes a ranking defect. The shortlist is ordered by score, which
implicitly assumes every position is the same size. Under a fixed-risk rule a
tight stop buys a larger position, so two names with the same score can
contribute very differently. Ranking by expected contribution is only possible
once the account is known.

### 3. The record learns what a fill costs

Every ledger row gains an `executed` block: whether this pick was taken, at
what price, in what size, and when it was closed. The evidence views then
publish two lines instead of one — what the setup did, and what the account
did — and the difference between them is the execution cost this project has
never measured. `src/learning.py` already fits a shadow model on outcomes; it
would finally have the target variable that matters.

## What must never happen

- **No credentials.** Consumer-permissioned OAuth only, and the token lives in
  the private service, never in `docs/`, which GitHub Pages serves.
- **No account data in the public record.** Balances, sizes and fill prices are
  the user's. The public ledger keeps paper returns; the executed block lives
  in the private store beside the broker session. The page can publish
  *differences* (a slippage distribution) without ever publishing a position.
- **No order placement at Fidelity**, because there is no API, and no silent
  order anywhere: the existing bridge's preview-then-confirm boundary stands.
- **Nothing auto-trades.** Every sentence above ends at a human.

## The order to build it

1. **A portfolio port with no provider behind it.** `src/portfolio.py` reading
   a hand-written positions file. It costs nothing and immediately delivers
   the morning exit desk, which is the largest single win here and needs no
   aggregator at all. Everything downstream can be built and tested against it.
2. **The `executed` block in the record**, filled from that same file, so the
   paper-versus-real comparison starts accumulating before any integration
   exists. This project's own history says the expensive part of an evidence
   change is waiting for the record, so start the clock early.
3. **Position-aware ranking and sizing**, using the risk frame already in the
   bridge config.
4. **Only then, an aggregator.** SnapTrade is the shorter path; Akoya is the
   one Fidelity co-owns. Either is a provider behind the port built in step 1,
   which is why the port comes first.

The honest note to end on: steps 1 to 3 are worth doing whether or not step 4
ever happens, and step 4 is worth nothing without them.
