# The analyst's instructions

SpicyStock is now one layer of three. SpicyStock is the view and the daily
output. An outside analyst, a bot you run, researches the candidates, looks
at your Fidelity account and recommends. You decide and you place every
order. These files are the analyst's instructions.

## The files

| File | What it is |
|---|---|
| [`prompt.md`](prompt.md) | The full standing instructions. Long on purpose: a bot with no other context should be able to do the job from it. |
| [`bootstrap.md`](bootstrap.md) | A short version, under 2,000 characters, for a bot whose instruction box is small. It states the hard limits and tells the bot to fetch `prompt.md` and the daily brief at the start of every session. |
| this file | How to use them. |

Both are public, like the rest of this repository. They hold no account
data, and neither should anything you add to this folder.

## How to give them to the bot

Pick the first that your bot allows.

1. **Paste `prompt.md` whole** into the bot's custom instructions, project
   instructions or system prompt.
2. **If the box is too small**, paste `bootstrap.md` there. The bot then
   fetches the full instructions itself from
   `https://raw.githubusercontent.com/spicyChicken59/SpicyStock/main/docs/analyst/prompt.md`
   at the start of each session.
3. **If the bot cannot fetch pages**, paste `bootstrap.md` into its
   instructions and attach or paste `prompt.md` at the start of each
   conversation.

The instructions are written for a bot that may or may not be able to
browse, read images, run code, remember or run on a schedule. It is told to
say which it can do at the start of each session, and what to ask you for
when it cannot.

When this file changes, give the bot the new version. The prompt carries
its own version and date in its first line.

## What to fill in privately

Section 16 of `prompt.md` is a profile with blanks. Fill it in **in your
private chat with the bot or in its private memory**, never in this
repository:

- a label for each account ("Roth", "Rollover"), never an account number;
- which account trades;
- the dollars you risk on one trade, your cap on one position and your cap
  on open positions;
- the policy switches: whether the bot follows the model's gates, whether
  RED means no new longs, whether a name without a ticket may ever be
  traded and at what size;
- your kill rule: when new entries stop until you have reviewed the ledger;
- which messages you want, and when;
- the Fidelity facts you have confirmed so far.

Until you fill a line in, the bot uses the safe default the prompt names
and says that it did.

## What to send it each day

| When (Chicago time) | What |
|---|---|
| Evening, once the record has landed (from 2 to 17 November 2026: between 8:53 PM and 11:08 PM CT) | Nothing, if the bot can fetch. Otherwise paste `brief.md` from `https://spicychicken59.github.io/SpicyStock/brief.md`. |
| Before the open, by about 8:00 AM | Your three Fidelity screens for each account that may trade: **Positions**; **Balances** with "Settled cash" and "Cash available to trade"; **Activity & Orders**. Paste the text, send screenshots, or export a file. Never a password or a code. |
| 8:30 to 9:00 AM, if you are entering an order | The bid, the ask and the last price from Fidelity; Fidelity's preview screen; then what happened: accepted, refused (the exact message), filled, part filled. |
| When anything fills, and at each close while you hold a position | The fill or the order as Activity & Orders shows it, and the day's high and low if the bot cannot look them up. |
| Once a week | A fresh Activity & Orders view for the week and, if you record trades on the page, the file from its "Download private backup" button. |

## The first three things to do with it

1. **The freshness check.** Ask the bot: "Fetch the brief and tell me
   whether it is fresh and what day its plans are for." It should answer
   with one status line: the measured day, the day the plans are for, one
   of `newest`, `not_due`, `pending`, `late` or `missing`, whether the run
   was ok, the colour of the light and how many tickets there are. If it
   starts with anything else, its instructions did not take.
2. **The Fidelity verification sitting.** No SpicyStock ticket has been
   placed at Fidelity as written, and several things about the order form
   are not confirmed. Section 10.8 of the prompt is a one-morning check,
   with one-share orders you cancel at once, that settles them. The bot
   reads out each step and records the answer. You click. Some steps place
   a real order, so run it only when you choose to. Start with step 0,
   which needs no order: tell the bot how any buy you have already made
   of a ticketed name was entered.
3. **Start the ledger.** Ask the bot to open the ledger of section 14 and
   enter every real order and fill you have made so far, each with its
   source. From then on, every order, refusal, fill, stop change and exit
   gets a row. The weekly review compares your real results with the
   model's, and that comparison is the only evidence of an edge you will
   ever have.

## What these instructions are held to

`tests/test_analyst_prompt.py` holds every strategy number the prompt
states to the code's own constants, its addresses to the repository's own,
the names of the brief's sections to the brief, the bootstrap to its length
bound, and all three files to carrying no email address, no account number
and no balance outside a labelled synthetic example. A rule that changes in
the code turns that test red until the prompt is corrected.

The dated figures in section 2 of the prompt (the model record, the
schedule, the market light) are as of 19 November 2026 and will age. The
bot is told to prefer the live brief.
