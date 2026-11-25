# SpicyStock

The active [product goal and milestones](PRODUCT_GOAL.md) are a usable morning
trading workspace for one Fidelity model account ($30,000 across two IRAs from 4 November 2026; $2,000 before it) in Chicago time: trustworthy data,
clear conditional setups, bounded sizing and an explained wait when nothing
qualifies. Milestone 1 is live with morning preparation, combined cash
allocation, known corporate-action exclusions and dependable session handling.
Verified morning observations and the compact reader are deployed; reliable
on-time delivery and broader event coverage remain open. The
[implementation tickets](https://github.com/spicyChicken59/SpicyStock/milestone/1)
track this work and the practical first-trade workflow. The original October 9
evening publication exposed a missing ZIM takeover exclusion; the source-backed
correction and its production verification are tracked in
[PR #115](https://github.com/spicyChicken59/SpicyStock/pull/115). A successful
real-money trade has not yet been recorded. Mo authorizes continued
milestone releases with tests, independent review and public verification. The
hourly **Build SpicyStock milestones** ChatGPT task supports resuming that work;
see the goal's continuation contract.

One evening run over an explicitly selected US-stock universe, one page that says what
to do next session and why, one email that says the same in fewer words. The
method is Pradeep Bonde's (Stockbee) momentum burst: reaction candidates
discovered by either the 4% or Dollar route, admitted to the trade band when
the 4% scan found them or the dollar scan found them on a range-expansion,
higher-volume day (`src/admission.py`), then judged for expansion out of
a quiet base, bought the next session through a buy stop a cushion over the burst close
(`plan.trigger_cushion()`; at the close itself in a record made before
`plan.burst_trigger_rule`),
up to a limit set from the stop, with the stop at the burst bar's low or its
midpoint and every such ticket at half risk, sold into strength over three to
five days, and only when breadth allows it. `knowledge/method.md` says whose
number every rule is; `knowledge/rules.md` states every rule the evening run
applies, in pipeline order, each with its constant and its provenance class,
and says what is Bonde's and what is this project's (`tests/test_rule_sheet.py`
holds its numbers to the modules); this file says what the software does with
them. The dated
[reaction discovery source contract](knowledge/reaction-discovery.md) pins
the primary 2015 4% and 2017 Dollar formulas, their differing volume
boundaries, and the repository's separate precision/universe choices.

The page is the product. It is generated and static: `docs/data.json` supplies
the latest decision, with separate read-only historical evidence and optional
browser-local saved research. It displays recorded gate counts and entry timing.
The regime, the grades, the
share counts, the order tickets, the exits, the record — is written by the
run and printed verbatim. It is an implementation of the method with
explicit assumptions (the archived rules, and `knowledge/method.md` on whose
number each is), not a proven edge, and it knows nothing about what anyone
holds: every plan it follows is a model of the published ticket.

**Historical validation.** The retained rebuild sample contains 13 publications
across 11 sessions, with no published reaction ticket or settled plan. It does
not establish an executable trading edge or a timetable for funding an account.
The $10,000 / 0.5% / 25% / four-slot account is a model assumption. Twenty settled
plans would make a rate readable, not certify an edge. Read the
[versioned evidence and blocked claims](docs/input-truthfulness/2026-09-28-validation-review.md)
and [selected operating contract](docs/input-truthfulness/2026-09-28-operating-contract.md).
October 2026 added the first outcomes on real bars, none of them an edge
claim. Run 6 reproduced the red reading of 24 and 25 September on a later
retrieval of every intended stock (10-session ratios 0.93 and 0.89 against
the published 0.94 and 0.89); the signal-outcome study, which runs the
production plan rules over every archived burst with the regime gate, the
slot cap and the reader removed (and, outside the admitted stratum, the
grade's or the veto's own refusal), found every stratum losing on the red
nights -- the admitted stratum's exploratory rows −0.235R per settled ticket
over 202 on 2 October, −0.189R over 267 on the 6 October re-read and −0.119R
over 301 on the 17 and 24 October ones and −0.123R over 303 on the 7 November
one; a night read before its tickets' fifth session leans toward losses. Its
first readable confirmatory figure, 17 October, was −0.157R over 209 settled on
ten nights, three of them YELLOW, with a night-bootstrap interval of −0.431 to
+0.129; read again on 24 October over fifteen nights it is −0.081R over 316, the
interval −0.319 to +0.251; read again on 7 November over twenty-four nights,
nine of them YELLOW, it is −0.218R over 575 (−0.003R a night, the interval
−0.232 to +0.220), 119 of the losses one night's, 4 November, every settled ticket
of which stopped into the 5 November alarm: none establishes a sign --
and the owner's backtest over 158 archive sessions (100
yellow, 58 red, no green) wrote 99 half-size A+ tickets, of which 44
settled, 16 won, 27 lost and 1 was even, +3.72R net, the reader not run. The
same replay with every night treated as green (grades A and A+ at full size; a
counterfactual, not a policy) summed +17.40R over 69 settled; +1.14R of that
came from the red nights (25 settled, 7 won, 18 lost) and +16.26R from the
yellow nights, where it also admits grade A, so the gap to +3.72R is mostly the
yellow band and not the red refusal, and neither figure has an interval. No
published night has been green: 35 red and 13 yellow over the 48 sessions from
11 September to 17 November 2026. The
Record view replays those nights one at a time from
`docs/historical-findings.json`, which `tools/build_historical_findings.py`
builds from the committed evidence files and binds to their digests; the
page prints its figures as the file writes them and adds no figure of its own.

## What the page says

**Morning desk.** The masthead's preparation button opens the published session's entry
window in America/Chicago, publication and market state, separate reaction and
setting-up ticket counts, and the account assumptions beside the next step.
The personal reference is read by the session a publication measured
(`docs/app-morning.js` `REFERENCES`): from the 4 November 2026 session, two
Fidelity IRAs read as one $30,000 model account, $150 base planned risk and a
$7,500 per-name cap before existing strategy reductions; before it, the $2,000
cash account, $10 risk and $500 cap every earlier publication was sized at. The
current reference and `evening.yml`'s versioned sizing are held to one number by
`tests/test_workflows.py`. A publication sized for another account than its
session's reference says so; the published tickets retain their quantities.
Optional settled cash begins unknown and stays in this tab. A separate cash-aware
preview uses that entered cash, an explicit fees buffer, and an optional smaller
whole-share quantity. It caps the calculation at the published shares and the
cash affordable at the entry limit, then shows principal, total cash, planned
limit-to-stop risk and remaining cash. Decimal amounts are calculated in integer
cents. Unknown or invalid inputs, unavailable plans, event restrictions and
mismatched account assumptions cannot produce a current personal preview.

Each preview considers one plan independently and reserves no cash. Account for
other orders and broker holds before entering available settled cash. Changing
plans clears the fees and quantity inputs and the four manual preparation
checks: a quote, cash, stop or event check made for one stock says nothing
about another. Editing the same plan's inputs, or the clock repainting the
desk on the same publication, keeps them. A new session clears cash too, and a
reload clears these preview inputs. Published copy controls still copy the original model
quantity, clearly identified beside the preview. The calculation does not submit
an order or verify a balance. Preparation checks do not establish live quotes,
news coverage, broker buying power or execution, and cannot turn an unavailable
setup into an order. Planned price-to-stop risk excludes fees, gaps and slippage.

**Private broker handoff.** A calculated preview can be explicitly saved as a
separate personal draft for broker review. Its chosen whole-share quantity stays
within the admitted published quantity and entered cash; trigger, limit, stop and
dated exit instructions retain the published terms. The draft keeps the exact
publication and plan identities, selected terms, cash and fees on this device.
Its personal readback uses the chosen quantity for entry and planned protection.
The original published ticket remains separate. Copying is only a clipboard
operation, not a broker order format or a confirmation of execution.

The dated exit schedule is labelled as archived model wording. A separate
whole-share reference applies the existing model's at-least-half convention to
the personal draft, or to explicitly reported remaining holdings after reporting
begins. It rounds up: one of one share or two of three. A one-share position
cannot be partly exited in whole shares. Unknown fills or exits leave holdings
unknown; zero reported remaining shares leaves the schedule as history. This
reference arithmetic does not decide whether another exit is due, infer broker
fractional-share support or resize the saved schedule. Review prior exits and
choose feasible quantities at the broker before acting.

New preparation and copying recheck the current publication, account, entry
window and event restrictions. A superseded or expired draft remains readable.
Manual broker reports remain editable afterward: submitted quantity, cumulative
entry fills and average price/time, cancelled remainder, cumulative exits and
average exit price/time, actual entry/exit fees, and the broker-reported
protective quantity. Actual submissions, prices and
times can differ from the draft and are labeled as deviations. They do not
rewrite the strategy or the original terms. Copying, saving and market prices
never create a reported fill.

Blank values mean unknown. Remaining holdings require both entry fills and
exits, including an explicit zero when no exit has occurred. Filled plus
cancelled shares cannot exceed the quantity reported submitted; exits cannot
exceed reported fills. The protective quantity is compared with reported shares
remaining, not cumulative purchases. A quantity match does not verify an active
broker stop. Once reporting has begun, clearing fields to unknown cannot revive
the draft as a new entry to copy. Corrections are explicit; stale revisions
cannot overwrite a newer report. Dates require an explicit time-zone offset
and are displayed in Chicago time.

Each event-time field also offers **Enter Chicago time**. This optional helper
converts an explicitly entered date and time in America/Chicago to a preview
with its UTC offset and UTC instant, independent of the device's time zone.
It starts blank, refuses a time skipped by the spring clock change, and asks
which occurrence the broker reported when the autumn hour repeats. Applying
changes only that unsaved event field; the report still needs an explicit save.
Cancel keeps the event field and other entries. Apply or cancel the open helper
before saving or switching reports; **Load saved report** explicitly discards
it along with other unsaved corrections. The existing explicit-offset field
remains available for a broker time shown in another zone. **Use current time**
still supplies only the device's current instant, never an observed broker event.
The helper makes no request, saves no private record and changes no timestamp,
quantity, chronology or account validation rule.

The private store holds at most 100 records and 1 MiB, never silently evicts
records, and serializes writes with browser Web Locks. Unavailable, unreadable
or future-version storage is preserved and reported; it does not imply no
holdings. Saved drafts and reports persist across reloads, but clearing this
site's browser data removes them. They are not uploaded, backed up in the cloud,
added to model performance, or used to infer buying power. The handoff creates
no broker connection, reserves no cash, and neither places nor cancels a
protective order.

**Independently executed research trade.** A verified retained research row also
offers **Record an already executed trade**. This opens a blank private report
without saving anything. The first explicit save requires a positive quantity
reported filled and the corresponding submitted quantity; prices, fees, times,
exits and protection remain unknown until entered. Research quantities and
prices are never filled in as actual broker facts.

The record preserves its original publication, cohort, evidence and baseline
admission status. Both admitted and withheld comparison rows can be recorded
after the entry window, including a trade for which no personal draft was saved.
Reported quantities may differ from the hypothetical allocation. An existing
record for the same publication and evidence cannot be duplicated or overwritten
by this creation path; its existing correction form remains available.

This report-only kind contains no draft, cash assumption or order payload, and
never gains entry-copy or preparation authority. It shows actual reported
holdings/protection and, when reconciled, the same personal result described
below. No original model exit schedule is inferred for an independent execution.
Initial creation rechecks the verified source inside the save operation. Later
corrections retain the frozen original evidence even after publication replacement
or expiry. Modal close/reopen preserves unsaved input; cancelling the new unsaved
report is an explicit action. Reports remain private on this device.

The verified research journal also offers this blank report for an original
cohort retained after a newer scan arrives. The loaded journal must match the
current publication, and the selected row must match its exact original cohort
and evidence. A refreshed journal requires an explicit reopen before the first
save; reopening the same verified original preserves unsaved broker inputs.
Different cohort revisions sharing an original publication/evidence identity
open the same private record. Conditional model outcomes never supply fill facts.

**Your own trade on a listed name.** A stock the record lists without a ticket
(a burst below the admitted band, a withheld setup, a quiet coil) offers
**Record a trade I made on this name** in its action area; a ticketed name does
not, since its draft and broker report are the ticket's own. The button opens the
Morning desk on a blank version-4 record of kind `owner_trade`: every field
starts blank, nothing is written until an explicit save, and a save needs a
positive quantity actually filled with its submitted quantity. The record
freezes the publication (its SHA-256, session, publish time and rules digest)
and the row as the page read it (rank, mechanical grade and score, the scan that
found it, the discovery admission, the recorded status and reason, the evidence
identity when the record carries one; a setting-up name is ranked after the
whole top list when it is an also-quiet coil, and carries no grade, score, scan
or admission), the archived exit rules
(`rules.plan.sell_half_pct`, `sell_half_day`, `final_exit_day`, `entry_day`) and
the day-3 and day-5 sessions `run.calendar` places after the applicable session,
or null when it places none. Its identity is the publication, the stage and the
ticker, so one name in one record has one such record; opening the button again
chooses it. Two report fields are the owner's alone: a broker account label (at
most 40 printable characters) and the protective stop price actually placed.
Beside the facts the desk prints a **model exit reference**: the sell-half level
(the reported average fill plus `sell_half_pct`, rounded to the cent half up),
the record's day-3 and day-5 sessions counted from the applicable session as day
1, the reported stop, and, when the reported fill's New York date is not that
session, a sentence saying the dates are the record's and not the trade's. It is
reference arithmetic from the record's own rules; it does not decide that an exit
is due, grants no entry permission, changes nothing published, and never reads a
quote. A practice record (a page fixture) refuses the button by name, as does a
publication the page has not verified or a name the current record does not
list. The reported stop, not a published one, is what the completed result's gap
line is measured against.

**Personal completed-trade result.** A separate, user-reported result requires
positive entry fills, all filled shares exited, and submitted shares fully
reconciled as filled or cancelled (including an explicit zero cancellation).
Both average prices, actual entry/exit fees and latest entry/exit times must be
reported. Blank costs remain unknown; explicit zero fees means no reported fee.
The draft's estimated fee buffer is never substituted for actual costs.
Partial exits retain their facts without estimating a realized cost basis.

Gross result is filled shares multiplied by the difference between average
exit and entry prices; net subtracts the reported entry and exit fees. Prices use at most six
decimal places and actual fees use cents. Integer arithmetic retains exact
microdollars, rounding only the displayed amount to cents; a nonzero sub-cent
gain or loss is named explicitly. Corrections recompute this personal result.
It is not broker-verified, tax accounting, settlement confirmation, model
performance or evidence of a strategy's future returns.

When a planned handoff's completed result has an average exit under the
protective stop its published plan froze, one more line names the gap: how far
under the stop the average exit was, and how much less the reported shares
exited for than they would have at the stop (a gap or slippage). It is read
from reported averages, so it cannot say which shares went past the stop or how
far each did, and a gap on part of a position can sit inside an average at or
above the stop, which names nothing. An independent research report has no
frozen stop and no such line; an owner trade's line is measured against the
stop the owner reported, and is absent while none is.

Existing version-1, version-2 and version-3 private records remain readable.
Missing version-1 result fields stay unknown; recorded version-2 prices and
costs retain their validation and values; a version-3 record reads with its
account label and reported stop unknown. Reading adapts them in memory without
rewriting storage. An explicit successful save writes version 4, retaining the
original identities and previously reported facts and distinguishing planned
handoffs, independent research reports and owner trades (version 3 named the
first two; an owner trade under a version-3 envelope is refused). Failed writes
retain prior and proposed recovery bytes; unknown versions remain untouched.
Upgrading does not expand the shared 100-record / 1 MiB limit.

**Local private backup.** In Private broker handoffs and reports, **Download
private backup** saves the exact supported store bytes to a file on this device.
It includes private broker facts; keep the file private. Downloading does not
change the saved records, migrate older versions or upload anything. Unsaved
form edits are not included. This is separate from the emergency recovery file
containing prior/proposed payloads after a failed write.

**Restore private backup** reads a bounded local file and previews its validated
record count, kinds and original dates. Only a separate explicit restore click
writes it, and only into an empty, readable destination. Existing, unreadable
or concurrently changed storage is refused without overwrite. Choosing,
previewing, cancelling or rejecting a file preserves the mounted editor and
unsaved input; restore cannot replace a dirty or new unsaved report.

Supported legacy bytes, unknown broker facts, decimal strings and original
source references are preserved. Restore grants no new order-copy authority;
independent reports remain report-only, and planned handoffs retain all ordinary
current-publication checks. The shared 100-record / 1 MiB limit, Web Lock,
readback and failure recovery still apply. There is no cloud backup or sync,
and public data need not be available to access this local recovery path.

**Reproducing a reported result from the backup.** `tools/private_results.py`
reads the downloaded file on the owner's own machine (it is never committed)
and, for each record, re-derives the completed result by the page's own rules in
exact integer millionths of a dollar; refuses, by name, a record the page's own
validation would refuse; traces the record to the publication it was prepared
from -- the record whose bytes hash to the SHA-256 it froze, among
`--publication` files or this checkout's history of `docs/data.json` (`--git`),
and in it the plan whose evidence reference, order, entry window and exit
schedule are the frozen ones (an independent report: the setting-up row whose
evidence it names; an owner trade: the listed row's rank, grade, score, scan,
admission and evidence identity, the archived exit rules and the calendar's
day-3 and day-5 sessions, re-derived from the publication -- a setting-up row
from `watchlist.top` or the also-quiet coils after it, whose four graded fields
must be null); and prints the
model's own daily-bar replay of the same plan beside it, read off the newest
supplied publication after the plan's session, never added to the reported
figure (an owner trade has no model plan and says so; its reference exits are
re-derived the page's way instead). Each trace names what it did not compare:
a planned handoff's draft (the owner's own choice), an owner trade's status
word and reason (the page's own reading of the row), and an independent report's
reader digest, cohort, inputs digest and baseline admission, none of which
`docs/data.json` carries. It writes nothing but an explicit `--json` and makes
no network request. Exit 0 when every record re-derived and, where a
publication source was given, traced; 1 when a publication was not found or a
frozen plan is not the one it carries; 2 when the backup is refused; 3 when a
file or the checkout's history cannot be read, named in one line.
`tests/fixtures/first-trade/parity.json.gz` is the page's own verdict on 109
backups -- `tools/private_results_parity.mjs` runs `app-handoff.js` over each,
and CI holds the file to the page with `--check` -- and
`tests/test_private_results.py` holds the tool to every one: the same accept or
refuse, and for an accepted store the same figures and displays. A stored field
the page checks by pattern must be a string: an array holding one matching
string, which `RegExp.test()` would read as that string, is refused (the page
never writes one).

**The first-trade rehearsal.** `tools/first_trade_cases.mjs` (the page smoke's
`firsttrade` suite) drives the real page over the run_evening-produced $2,000
cash fixture, on one clock it moves for the page and the private store alike
(the page is opened unpinned, so the desk's window and the store's stamps read
the same instant): unconfirmed, unreadable, zero and short cash each refused; two
drafts prepared; after the cutoff no draft and no cash preview; a partial fill,
the remainder cancelled at the cutoff, a partial
exit and then the last share, and a gap through a protective stop, each
reported; the backup downloaded. Run at 390 and 1280 px, the two journeys must
write the same bytes. `tests/fixtures/first-trade/` holds the backup and the
amounts the page printed, and `tests/test_private_results.py` holds the tool to
both. Every broker fact in it is synthetic. When the cash-preview publication
moves, `SCSTOCK_FIRST_TRADE_WRITE=1 node tools/page_smoke.mjs --only firsttrade`
writes it again, and then `node tools/private_results_parity.mjs` the corpus
built from it.

The next-action message counts the same published reaction and anticipation
tickets as the desk, including tickets retained for inspection after cutoff.
The wait explanation separates the reaction review gates from the original
anticipation decisions. Each retained top anticipation row keeps its recorded
ticket status and refusal reason; an absent reason stays unknown rather than
being reconstructed from the experimental policy.
Retained planner errors remain visible even when they produced no plan.
On a weekend or holiday, the next-action message names the closed viewing date
and the next session from the recorded calendar; it does not relabel the last
measured open session as closed. In recovery notices, the latest evening
workflow is reported separately: a successful scheduled check may skip
publication and does not refresh the record.

The page is a small application over one record: five views behind the
masthead, the state kept in the hash (`#/explore/bursts/AAPL`,
`#/explore/setting-up/COIL`, `#/record`, `#/market`, `#/method`) so a link
reloads to the same stock and the Back button works; the old one-page
anchors (`#hold`, `#orders`, `#trade-X`, `#burst-X`, `#closest-miss`) still
land where they used to. Choosing a stock fetches nothing, grades nothing
and sizes nothing; a route the page does not know, or a symbol the record
does not carry, falls back to Explore and says so.
The full scan's count is available immediately; its criterion table is built
when the disclosure opens, from the record already loaded. Reopening keeps its
sort and expanded evidence; loading a new record replaces the old scan rows.

1. **The two clocks.** A record carries two different facts about time and
   the page keeps them apart, because freshness is not permission.
   **Publication** is the one thing the page computes: from the record's
   session and the browser's clock in ET it says *fresh*, *tonight's run
   pending*, *run pending · past both slots*, *STALE · 1 session behind* or
   *STALE · N sessions behind* (the versioned XNYS schedule expected
   sessions), *market closed* or *degraded*, with one fixed sentence per
   problem kind. Pending against stale is the service's own recovery
   window, read off the record: the evening guard admits a delayed or retried
   run for a missed session until the next session opens, so until that open
   the page says pending -- naming which of the two scheduled slots the clock
   has passed, in the words the record archived (`run.delivery`,
   `src/delivery.py`) -- and after it the page says stale and that the
   session will not be published. No fixed hour on the page decides it. A
   pending page past both slots and a stale page both say *Do not place these
   orders*, point at the run log, and withhold every ticket from the action
   area, the plan and the order sheet, keeping the setups.
   **Action timing** is the run's own (`run.timing`, `src/timing.py`): the
   session the published plans are FOR and the instants its entry window is
   scheduled between, offset and all, so the page compares rather than
   derives and never writes a UTC offset of its own. The window is
   *upcoming*, *in progress* or *ended*; a record published before the field
   existed, or one whose block is half written, is *entry timing
   unavailable — research only*. One calculation answers both
   (`availability(data, now)`) and every surface that offers an action asks
   it: the compact area, a stock's action bar, the plan disclosure and its
   copy control, the ticket sheet, the comparison's ticket row and the next
   action. Timing narrows and never widens — a red night still leads with
   *no new longs*, a stale page is refused under a window that is open, and
   a window that ended leaves the setup, its evidence and the ticket the
   record published readable while offering none of it to place. The clock
   is re-read when the tab comes back, the window takes focus, the browser
   restores the page and on a bounded tick while visible, repainting only
   the words that changed — the chart, the lens, the comparison, an open
   disclosure and the reader's focus all stay where they were — and a copy
   asks again immediately before it writes.
2. **Explore**, the default view. The market in a line: the verdict, one
   of six sentences — *Trade next session. N A-quality bursts.* · *Trade small.
   N A+ bursts.* (a yellow regime) · *Stand aside.* (red) · *Nothing
   qualifies. Keep cash.* · *Market closed. Plans unchanged.* · *No verdict
   for <session>.* (the run failed before it published) — with the dek's
   breadth numbers, the regime chip and the size rule, the session, and the
   record's own call to action. Then two stage cards, **Bursts · N** (the
   range-expansion days the scan graded) and **Setting up · N** (the
   anticipation list: quiet, coiled names inside established momentum; a
   name whose last seven sessions range under 0.30 of its sixty-session
   base is pinned, not coiled -- a pending cash takeover looks exactly like
   that -- and is kept off it, and off the near misses beside it),
   each under its count saying how many of them carry a ticket — the line
   a phone keeps, because that is the stage's own action state —
   and inside the chosen stage one selectable card per stock with its grade
   and its status in the record's words — *ticket*, *ticket
   withheld*, *beyond the slot cap*, *beyond the configured equity*, *no
   whole share*, *no new longs*, *vetoed*, *no ticket*, *watch* — a search
   that finds a ticker in either stage and says when it switched, and on a
   phone a rail of cards with a *Choose stock* dialog. **Find a stock** opens
   that same dialog from the first screen once a publication is loaded; a
   failed refresh keeps it available for the retained record. Enter selects an
   exact ticker before a company-name match. An explicit choice clears an
   incompatible search and reveals a stock outside the current lens without
   changing the saved lens. The dialog reaches every stock in the record, so
   it says which of
   them the lens in front of the reader holds and which it hides: two
   counted groups, the hidden ones marked and listed second, and one line
   saying that choosing one of those widens the lens for that stock without
   changing the lens kept for next time. The first load shows
   Bursts when the scan found any, Setting up otherwise, and a chosen stage
   is never switched away from: an empty one says why it is empty. Each
   stage remembers its last chosen stock.
   Desktop **Cards** uses two matching, viewport-height panes. Search, counts,
   filters and sorting stay above the scrolling card list; the selected stock's
   full details scroll alongside it, including the normal-size chart and every
   disclosure. Wheel scrolling stays in its pane. Arrow/Home/End move card focus;
   Enter selects. A different stock starts at its identity; selecting the same
   stock through ordinary navigation or repainting it keeps the reader's detail
   position. Explicit dialog choices and validated research **Inspect** actions
   start at the selected stock's identity and chart, including when it was
   already selected or Method had remembered a lower reading position.
   Invalid research identity, evidence or browser navigation leaves the prior
   reading state intact. Selection, search, Previous/Next and Back reveal the
   selected card only when needed, without
   snapping back during browse-only focus movement. The surrounding page remains
   scrollable, Map stays full width, and phones retain the horizontal rail,
   chooser and stacked details. Scroll positions are not persisted. When the
   detail pane is constrained, identity, badges and navigation use separate
   rows. The pane's own width controls this, so tools cannot squeeze the summary
   into a sliver. Narrow panes also keep ticket levels in two columns.
   A **lens** narrows the stage, each option a question asked of a field the
   run wrote and each wearing the count it will show: *A-quality* (the A and
   A+ grades this record archived whose discovery is admitted: the 4% scan,
   or the dollar scan on a range-expansion, higher-volume day -- a record
   from before the admission rule reads every A as admitted, and a block the
   page cannot read hides nothing), *All bursts*, *With ticket* (a ticket
   written into the published record) and *Following* (tonight's candidates
   already on this browser's shelf); Setting up has the last three. The
   first visit opens on A-quality when the record archived an admitted A or
   A+ burst and on every burst otherwise, so the first screen is never empty
   — on the published 401-burst night that is 52 stocks rather than 401. A
   name the admission stopped wears the chip *dollar scan alone* on its card;
   its action area and decision summary print the record's own reason, and
   its Discovery sentence carries the admission in the record's words. A lens the
   reader chooses is remembered in this browser and never widened behind
   their back: an empty one stays empty, explains itself and offers one
   click out. *With ticket* is a reading of the record and never a
   permission — a stale, pending, failed or sample page still withholds
   every order, and says so beside the list. The heading keeps the stage's
   own total beside the subset (*bursts · 52 of 401*), the lens combines
   with the ticker search, and a search that matches a stock the lens is
   hiding says which lens is hiding it and offers to inspect it rather than
   claiming it does not exist. An optional sort offers the run's rank (the
   default), the session's gain and volume against the previous session;
   it changes the order only, every card keeps its published rank as its
   own label, and a stock the record has no measurement for sorts last
   rather than as a zero. One visible-candidate list feeds the cards, the
   map, the counts and the previous/next stepper beside the chosen stock.
   The bursts have a second view of the same list, a **map** of the
   session's gain against its volume relative to the previous session:
   every point the same selection as its card, the unmeasured listed
   beside it, position a measurement and not a return (the ratio is the
   scan's own for every burst, the dollar scan's days included; a record
   from before 12 Sep 2026 holds it for those days only in the checklist's
   block, and the page reads that copy and says so). The gain axis is
   linear; the volume axis is compressed, because the ratio has no upper
   bound and one name at 169× laid four hundred at about 1× on the pane
   floor. Every tick is labelled with the ratio it stands for, every burst
   is plotted at its own recorded ratio, the largest is never clipped, 0×
   sits on the axis line, and the map says so in words. Points still
   overlap, so a tap is resolved by distance from the tap and not by which
   marker was drawn last: when more than one is within a finger, a compact
   **nearby chooser** lists them nearest-first with their measurements and
   chooses nothing until you do. It is the design system's own `.sc-pick`,
   which was written from this page's panel and two others like it, so the
   page keeps the behaviour and the sheet supplies the look: a finger's 44px
   a row, the stock's name, what else the record knows about it, and the
   session's gain as the row's figure. It is a labelled popover, not a modal: the
   arrows move inside it, Escape closes it and hands the focus back to the
   stock you meant — never to the marker the browser happened to hit-test —
   tabbing out of it closes it, any selection made elsewhere closes it, and
   a *Nearby stocks* button beside the selection opens it from the keyboard.
   A tap on a point standing alone chooses it outright, and the keyboard's
   Enter takes the point it has focused. A table under the map carries every
   burst, plotted or not, and both the chosen point and every table row
   carry the same *Compare* toggle the cards carry, so two candidates can be
   pinned from the map without going back to the cards to find them again. On a four-hundred-burst night almost every point
   has a neighbour within a finger, so almost every tap asks: the cards, the
   search and the table are the one-step path to a stock you can name.
3. **The chosen stock.** A Burst first answers whether SpicyStock offers an
   entry for this exact setup. A usable published ticket shows its applicable
   session, buy-stop trigger, stop-limit limit, protective stop and suggested
   model shares directly, with **Copy order** and **Plan details**. It prints
   the recorded order fields and keeps material sizing explanations, and under
   them one closed native **Broker notes** disclosure holding two labelled
   notes, Fidelity's part-fill rule and Fidelity's buy-stop rule, each with
   SpicyStock's advice (below), which the copied order never carries. A setup
   without a usable ticket says **No SpicyStock entry for this setup** and the
   actual grade, planner, budget, breadth or timing/publication reason. Expired
   plans remain inspectable as recorded history with no actionable levels or
   copy button in this summary. No client-side trading levels are calculated.
   The chart's arrow keys, Home/End and Escape inspect sessions when the
   chart itself has focus. Open its table disclosure and Tab into the named
   table region to scroll horizontally with the arrow keys; Tab/Shift+Tab
   leave the table normally. These table keys do not inspect the chart.
   Then one chart panel with one header (the symbol, its
   last close and session), the controls together above the plot, and every
   price label in a reserved right gutter with a leader back to its exact
   level: the last close, the stop, the trigger, the limit (the highest fill
   the ticket permits) and, for a burst, the zone's floor. Three modes over
   the same bars, levels and dates — *Setup* (the annotated view: the base,
   the trigger and zone, the stop, the burst evidence), *Candles*
   (conventional up/down candles, hollow and filled, with a quiet close-line
   toggle) and *Line* (the recorded closes) — and three ranges: the *Setup
   range* (the base and a short run of context before it, the dates
   disclosed; without base dates it says so and shows 60), 60 and 120
   sessions. Each group of controls carries its own visible caption —
   *view* over the modes, *range* over the ranges — which is also the name
   assistive tech announces for it: *setup* is a mode AND a range, and an
   uncaptioned row of pills cannot be told from the one beside it. The mode
   and the range are remembered in the browser. The aim
   levels are printed beside the chart, and say so when they sit outside
   the visible range; a coil draws its box and its trigger and no burst
   candle; a name without archived bars says *Chart unavailable* and keeps
   its conditions. Four answers, each from the record's own sentences:
   *why this stock?*, *what would need to happen?*, *what invalidates it,
   or makes me wait?*, *principal risk or limitation*. Risk uses accepted reader
   commentary (still explicitly unverified), then plan-derived risk, otherwise
   an explicit unavailable assessment. Recorded screening warnings are separate
   in both detail and comparison; they never fill an absent risk assessment.
   The broad `biotech` flag covers Health Care sector rows as well as matching
   industry text, and does not establish a biotechnology company or event risk.
   `foreign` also includes unstated country. The publication does not carry the
   precise per-stock directory basis, so that limit is stated; raw flags remain
   inspectable in provenance. Anticipation keeps its
   existing action area below those answers. The Burst action summary uses
   the shared `.sc-actionbar` with a compact four-field grid (two columns on
   a phone); browse cards keep their compact form. Four disclosures follow:
   the conditions (one tile per
   criterion with a plain question, local verdict, observed value and reference
   period, this record’s ordinary rule, and method rationale; separate A+
   criteria, formulas and original fields remain in an accessible disclosure.
   Unknown rule formats retain their recorded wording without inferred meaning.
   Then the base, the burst and the grade); the plan, sizing and
   order (for a burst, the *ticket fills* row: the buy stop, which is the
   burst close, up to the ticket's own limit, with the sentence that under
   the buy stop the order waits and buys nothing, or *no ticket* where the
   stop rule withheld the setup; the chart calls the skip line to the limit
   the *entry zone*, labels a card's band by its two prices alone, and says
   in its levels row that a buy stop fills only from its trigger up; the two
   skip lines, of which the upper one is the +4% day-2 threshold and not the
   limit; the stop and its basis; the shares sized at the limit — the
   highest fill the ticket permits, so the fixed quantity keeps the risk
   budget, the position cap and his 4% stop line at every fill it can take
   — the position, the planned price-to-stop risk, the aim, the hazards,
   and the order in Fidelity's field order with a copy button: a buy
   stop-limit with a one-triggers-the-other sell stop riding on it, and
   under it what the ticket enforces and what it leaves to the reader;
   beside those terms, never inside them (the plan's terms are its record,
   name no broker, and provenance replays them), two sentences, each
   labelled: Fidelity's rule, that the OTO sell stop is released only when
   the buy fills in full, and SpicyStock's advice, that wherever a ticket,
   a plan or its dated schedule says the sell stop is attached at or live
   from the fill it assumes a full fill, and a part fill needs one separate
   sell stop for the shares that filled, once Fidelity is confirmed to
   accept it on shares bought that day. Wherever an order is printed or
   copyable the same text is printed beside it and never inside the copied
   lines: the order block, a recorded ticket, the Burst's action card above
   its **Copy order**, the setting-up action bar after its order line, the
   comparison under its facts when a compared ticket prints one, the
   tickets sheet, a ticket's decision summary under its entry (for a
   setting-up stock only while its action bar, which follows the summary on
   the same screen, does not offer the order), the model
   exit guidance under a ticket's dated schedule, a saved setup's archived
   order when it was a ticket, an archived original's status when it was a
   ticket, the private handoff's readback and the mail's order and alert
   blocks (`report.BROKER_PART_FILL`, held equal to the page's two copies
   by `tests/test_docs.py`); a pick card's summary never falls back to a
   ticket's order line; before and during the window the next action says
   the sell stop is written as part of the order (OTO), that Fidelity
   releases an OTO stop only when the buy fills in full, and that whether
   Fidelity's ticket accepts this OTO is unconfirmed; on a night with a burst
   ticket whose buy stop is its own close (one made before
   `plan.burst_trigger_rule`) it adds, before the window, that whether
   Fidelity accepts a burst ticket's buy stop at its last close is
   unconfirmed, and inside it, that a
   burst ticket cannot be entered as written while the stock trades at or
   over its buy stop. Beside a burst ticket's order, directly after that text, a second
   labelled note: Fidelity's rule, that a buy stop or buy stop-limit order
   must be entered at a stop price above the current market price
   (`knowledge/broker-fidelity.md`, item 2, read off a search excerpt), and
   SpicyStock's advice, that a burst ticket's buy stop is the burst day's
   close or a cushion over it (the trigger rule its record archived says
   which), so it can be entered as written only while the stock trades under
   the buy stop; that which price Fidelity compares it with before the open is
   unconfirmed; that once the stock trades at or over the buy stop
   SpicyStock offers no other order; and that the model's *filled at the
   open* assumes an order already resting before the open
   (`report.BROKER_BUY_STOP`, held equal to the page's two copies by
   `tests/test_broker_buy_stop.py`). It is printed at each of those places
   for a burst ticket, in the private handoff's readback for a bursts-stage
   draft, and in the mail once after the burst orders; never beside a
   setting-up ticket, whose trigger sits above its last close. On the
   Burst's action card and in the decision summary's entry the two notes
   ride under one closed native **Broker notes** disclosure, both kept in
   the page: printed open there, the second note pushed the card's **Copy
   order** past the bottom of a 390 px phone's 844 px screen (602 px under
   the card's top with the part-fill note alone); under the disclosure it
   sits 480 px under the card's top.
   `knowledge/broker-fidelity.md` (revised 19 November 2026) maps each field
   onto Fidelity's ticket, the field names labelled unconfirmed, and labels
   each fact as Fidelity's words or a regulator's words with its source,
   inferred, unconfirmed or SpicyStock's advice, and what came from the owner
   as the owner's words, Fidelity's screen with its date, or the owner's
   practice, which is never a SpicyStock ticket. Every Fidelity fact in it is
   a search excerpt; nothing was read on Fidelity's own pages. A burst
   ticket made before `plan.burst_trigger_rule` has its buy stop at its last
   close: before the open it is unconfirmed which price Fidelity compares it
   with, and once the stock trades at or over that close the order cannot be
   entered as written. Over 13,599 counterfactual burst tickets on 40 nights
   (signal sessions 11 September to 5 November 2026), with the buy stop at
   the close, day 1 opened at or over the buy stop on 54.8%. A ticket made
   under `close_plus_cushion` sits a cushion over the close, as a setting-up
   ticket does; `tools/burst_trigger_comparison.py` reads the retained
   publications under both rules.
   `knowledge/broker-fidelity-protocol.md` is the one-sitting check of every
   unconfirmed point, with order entry by price state and the cash-account
   working rules; `knowledge/trade-ledger.md` is the ledger of real orders
   and fills the outside analyst keeps, reconciled weekly with the private
   backup through `tools/private_results.py`); the
   model exit guidance, dated; and the provenance (what Claude saw in the
   chart, the bars, the rules digest). Where the limit is under the day-2
   line the *ticket fills* row says so in the plan's own words, and a burst no limit
   above its buy stop can hold a stop under keeps its card and has its
   ticket withheld, with the reason in the action area. Below the workspace, two more disclosures: **Tomorrow's
   tickets** (the model allocation over the configured sizing assumptions
   and the order sheet, every cut name explained) and **Everything the
   scan found** (every burst against the checklist — the six letters,
   range expansion and volume — sortable by score, each name a way to its
   card, the closest miss named above it).
   A **Show on chart** row under the plot marks the recorded evidence: the
   *Base* (the producer's own archived start, end and bounds), the *Burst
   day* (the session the record was published for, not whichever bar is
   last after a later observation is appended) and the *Prior day* (the
   previous archived observation before that signal, not the previous
   calendar day); a coil offers its *Box*. Choosing one draws a dashed
   column over exactly those sessions — in every mode, with the recorded
   bounds as edges when both already sit inside the drawn scale — and prints
   beside it the recorded measurement, the producer's own threshold and his
   verdict in words (*pass*, *partial*, *fail*, *not measured*). The marker
   is a position and nothing else: it widens no scale, moves no level and
   moves no label, so turning it on leaves every price where it was. The
   checklist criteria the record dated offer separate **Show Base/Burst/Prior
   evidence** buttons using the same mechanism — and a check the record carries no date range for
   (linearity, the trend's age, the run of up days) stays a tile and is
   given an honest unavailable explanation instead of an invented region.
   Evidence outside the range on screen is offered (*Show recorded range*)
   and never taken silently; a name with no archived bars keeps the words
   and says there is no chart to sit on.
   **Focus evidence** explicitly frames the selected marker with nearby actual
   sessions: three context observations on available sides of the whole
   evidence, expanded to at least 21 actual observations where available.
   If that floor or a long base prevents useful horizontal zoom, Focus draws
   the plot 30% taller while retaining its recorded prices and plan levels.
   **Back to setup range** (or the prior 60/120 range) restores the exact normal
   date window and geometry. Normal chart heights remain 400px desktop and
   300px narrow/mobile. Focus never writes the saved Setup/60/120 preference;
   repeats do not compound, and another marker requires an explicit Focus.
   A new provenance-enabled Burst without ordinary browser bars offers
   **Load recorded chart**. Only that explicit press fetches its exact retained
   source object, with bounded decompression, source-hash and reference checks.
   It displays up to 120 sessions from that frame and identifies them as
   recorded source evidence. No eager evidence requests, market providers,
   later observations or fabricated bars are used. Failures leave the setup
   usable and offer a retry; legacy missing sources remain unavailable.
   Saved originals/history recovery keep their existing evidence. A chart loaded
   before a new save can be saved with that original; loading never rewrites an
   already saved chart. Compare can request a missing chart independently.
   [The chart-source contract](docs/actionability/README.md) describes validation
   and request/payload limits.
   A **Compare** toggle sits beside each card's selection button and in the
   chosen stock's own tool row — never inside either, so pinning neither
   chooses the stock nor follows it. Two pinned candidates of one stage and
   one published record open a comparison sheet: two balanced panels, each
   its own chart instance with its own price scale, its own dates and its
   own range sentence (the two are never drawn on one axis), one set of
   view and range controls driving both, and under them an aligned table of
   what the record says — grade and how it was graded, session gain, the
   volume ratio named for what it measures, the base or box, the trigger,
   the ticket limit, the stop and its published distance, the main
   qualifying reason, the principal concern, and the ticket or the exact
   reason there is none. A row the two differ on is marked; nothing
   declares a winner, and a value the record does not carry reads *not
   recorded* rather than as a failure. A third pin asks which of the two it
   replaces; a pin from the other stage is explained rather than refused. A
   pin the reader then narrows the lens past is never dropped: the chip says
   which lens is hiding it, the tray says it stays pinned because the
   comparison reads the record rather than the lens, and one click goes to
   it.
   On a phone an A/B switch shows one chart at a time while both symbols
   and both statuses stay on screen. *Open setup* and the same Follow
   action are offered from each side, and closing returns the reader to the
   stock, the lens, the scroll and the focus they left.
   A veto is printed as measured: "N rising closes in a row before the burst
   (three or more of any size refuse a setup)", the count the row's own and
   the threshold the record's archived `quality.veto_up_days`. The model
   exits name each rule's source in words. A burst ticket's dated timeline is
   preceded by one sentence saying the buy stop triggers at the trigger and
   can fill to its limit, and that the lower figure in the day-1 line is the
   skip line, not a buy price. A listed row with no plan whose ticker is in
   the record's archived event registry wears a "known deal" chip, prints the
   registry's own sentence and sources, and is offered no order
   (`registryMatch()`, held to `event_risk.classify()` by
   `tests/fixtures/event-registry/classify-parity.json`, 119 synthetic
   cases); rows with a plan keep the plan's own `event_risk`, and a saved
   setup freezes the flag in its limitations.
4. **Record.** **Open model plans** is every pick from the last five
   sessions walked from bars alone as a model: *day 3: sell half*,
   *stopped*, *not filled*, *uncertain* (neither the daily bar nor, where
   the run retained them, that session's minute bars can say whether it
   filled), with the stop the rules would have moved it to; SpicyStock
   does not know what you hold. Then the bars-only scorecard (plans, fills,
   win rate, average R, SPY over the same days) and fourteen dots for the
   last fourteen exchange sessions: ok, degraded or missing; older recorded closure outcomes remain readable.
   Last, under the open model plans so that nothing a link lands on moves
   as it loads, **What historical validation establishes** replays the record
   night by night from `docs/historical-findings.json` (`docs/app-findings.js`,
   `SCStock.findings`): a stepper over every published night the study carries, the
   10-session ratio on every session the records know -- the gate's own
   reading on a published night, a later record's history on any other, and a
   later history that reads a night's counts or ratio differently named beside
   it -- with the two thresholds of its ratio rule drawn and named at the axis
   (a key says that green also needs every other breadth rule quiet) and a
   dotted line at the study's freeze; under it every settled R of that night's
   counterfactual tickets by stratum on a compressed axis with the night's
   mean. Each stratum's caption says what its counterfactual removed: the gate
   and the reader for A-quality, and for the graded B, C and skip or vetoed
   bursts the grade's or the veto's own refusal too. A night's mean is printed
   and drawn as a rate only from the record's minimum of settled tickets
   (`record.SCORECARD_MIN_PLANS`, 20); under it the night shows its count and
   its sum and its mark is hollow. A night whose hold is over can still move
   while rows a later record can settle remain, and says so; every hold word
   is dated by the records the study read. Three table twins carry the nights,
   every settled R and the market. Then the owner's backtest, the run-6 check
   of the red reading, the "Read it as" caveats -- the exploratory reading
   pooled over the red nights only, the confirmatory split from the study's own
   figure against its minimum, the nights left out counted -- and the 28
   September frozen cases, each inspected from its frozen copy under
   `docs/historical-validation/` under the study's own digest, never from the
   rolling archive. Every figure it prints is a field of that file at
   the precision the file writes it (a mean at three places, a sum at two);
   its own arithmetic is a night's place in the list, the length of a list the
   file carries, the comparisons that choose a sentence (a count against the
   minimum, every readable stratum under zero, a night's verdict) and the
   drawing. It reads no record, no clock and no storage, checks the file's
   shape before it draws and says in one sentence what it refused; both
   historical files are fetched only when the Record view is first shown, say
   they are loading while in flight and end in a sentence if they stall, and a
   page over a fixture says the replay reads the public findings. On a phone a
   tap within a finger of more than one night asks which, nearest first, and
   stops Play; the list of nights is the precise way to one, and a narrow chart
   shows no tooltip because the caption and the tables carry the values.
   The Record view says every retained ticket is counted once for each night
   it was issued, that a stop first reached inside a session is booked at
   exactly the stop (so a stop on the fill day is exactly minus one R), that
   no fees, spread, slippage or tax are counted, and that a first day the
   daily bar cannot place is read again from retained one-minute bars under
   the archived rule and window. The replay's exploratory sentence says the
   settled counterfactual tickets of the red nights lost in sum and that
   this is not evidence the gate adds value; the backtest block prints the
   summary's own account, risk and rules digest and says a published record
   is sized and ruled by what it archives.
5. **Market.** Bonde's Market Monitor over usable fetched stock frames for the measured session:
   up and down 4% on volume, the 5- and 10-day ratios, the
   25%-in-a-quarter and 25%/50%-in-a-month counts, the share above the
   40-day average, the 10-day ratio over the last thirty sessions with his
   line drawn on it, and the regime verdict with every rule that fired.
   Thresholds are scaled to the measured universe against his ~6,500.
   The stocks counted are those with a usable bar that night and a close of $3
   or more that night (3,513 of 4,756 intended on 17 November 2026). The thirty
   sessions are read again each night over that night's stocks, so an earlier
   session's counts differ from what its own night published: all 47 sessions
   from 11 September to 16 November 2026 moved (a median of 9 names; at most
   0.06 in the ratio). A published verdict is never recomputed, and only one of
   1,048 later readings (5 October, 1.00 against the published 0.97) would have
   changed one. The view lists the five regime rules as the record's own
   inputs and scaled thresholds give them tonight, fired or not
   (`regimeRules()`), and withholds the list when those inputs do not give
   the record's verdict. A scaled count note is introduced as SpicyStock's
   scaling of a quoted reading, not as Bonde's number.
6. **Method: How to read SpicyStock.** The view opens on **The method, one burst at a time**
   (`docs/app-method.js`): an animated walkthrough of Bonde’s burst over one
   synthetic series, eleven steps from the thesis to the record — the
   leg, the base, the day before, the signal, the Market Monitor, the plan, the
   fill, the day-3 close, the trail and the exit, the replay — each captioned
   with this build’s numbers and whose number each is. Every number it prints
   is named for the constant it quotes and held to `src/` by
   `tests/test_walkthrough.py`, which also re-derives the example ticket and its
   five-session replay through `plan.burst_plan()` and `record.replay()`, so the
   walkthrough prints what the code writes. Its captions also say what the model
   does where a ticket's words say more, the admission rule, the five regime rules
   with the scaled counts and what a fill at the open assumes;
   `tests/test_strategy_texts.py` holds those sentences, the method note and the
   help terms. It reads no record and stands on
   the no-record page; `#/method/walkthrough` deep-links to it; the bars have a
   table twin. Then the reading journey and concise definitions
   precede the original scan summary, full publication details and configured
   sizing assumptions. Method names the gates a record archived and no
   others, says the bars come from one provider with no second source,
   counts the archived event registry's entries, its review date and how
   many in force are past their review dates (a manual list, not a news
   screen), says a changed rules digest can reflect membership alone, says
   SpicyStock is a view and a daily output that places no order, and links
   the rule sheet (`knowledge/rules.md`). The footer links the analyst brief
   (`brief.md`, `brief.json`) at run time; `docs/index.html` names neither
   file. The page does not ask whether they exist, so each link's title says
   it answers 404 until the first evening run that writes the pair, and on a
   night the pair could not be written. Nearby help opens on hover, keyboard focus or deliberate
   tap; its interactive disclosure supports Close/Escape and viewport placement,
   including Compare and enlarged text. `#/method/<topic>` routes open the
   relevant definition; **Back to what I was reading** restores selection,
   browsing positions and an open comparison. Route, record and selection changes
   dismiss stale help. Help is never nested inside an interactive stock card.
   The compact first screen names the purpose, first action, measured population
   and dated snapshot, and says the site neither places trades nor knows holdings.
   Discovery, weighted grade, published ticket and current entry availability are
   distinct. Pass/fail/partial/veto/not measured are local checklist verdicts;
   market regime, publication status, timing, saved confirmation and model outcomes
   retain their own words and palette. Candle direction is close versus open;
   headline gain is versus previous close. Map volume uses the existing compressed
   scale, with an explicit unequal-distance warning and selected-symbol exception.
   `app-reading.js` formats recognised recorded expressions and provides reusable
   definitions; it never scores, changes a plan or applies current defaults to an
   older record. Primary rules, later changes, secondary interpretations and
   implementation proxies remain attributed in the existing source documents.
7. **My setups.** A prominent peer to **Latest scan**, reachable even when
   empty. **Save setup** on cards, details and comparison entries freezes the
   exact signal in this browser. Discovery’s **Saved in this scan** lens is
   only a subset; My setups includes every local save regardless of filters,
   grade or membership. Legacy Following links and saved identity links remain.
   **I followed this plan** on a ticketed detail saves the original and records
   a browser-local choice of that exact published plan. It freezes the recorded
   order, dated session/horizon, evidence/plan/pick receipt and selection timestamp. It does not
   establish an order, fill, actual quantity, sale or personal P&L. Original signal,
   dated observed movement, coverage and the public model outcome remain separate.
   Exact receipt matches join the existing Record replay; the newest loaded model
   outcome is cached with its publication date, never replaced by an older record.
   There is no client-side fill/outcome engine. Uncertain remains uncertain.
   If the public five-session model window ends without an outcome loaded here,
   the page says so; it never invents a terminal result. Price observations retain
   their independent public horizon and basis caveats.
   Legacy **I took this setup** notes remain editable only where already present;
   migration never turns them into plan selection or execution evidence. Old saves
   lacking complete plan receipts explicitly cannot join an exact model outcome.
   Optional **Reference amount (USD)** remains a local note. A marking timestamp is
   not a purchase date. Amounts start unknown, use integer cents and clear back to unknown;
   existing suggested/reference whole-share values retain their meanings.
   Schema v4 migrates the existing Following key with preserved backups and
   unknown fields. Page writes use Web Locks on HTTPS to serialize tabs;
   conflicts follow lock acquisition order and removed items are not resurrected
   by stale edits. A save granted after another tab's write has already redrawn
   this tab's detail block finishes on the block the document holds, so the
   block and the shelf show the save the store has. Without Web Locks the saved
   list is readable but writes fail explicitly. No cross-device synchronization
   is provided.
   **Find earlier setup** searches a public, source-addressed catalog on demand.
   It retains 21 calendar days, up to 84 distinct publications and 10,000 signals
   per publication, within 128 MiB. Past the publication or byte cap the records
   still inside their window give way, oldest session first (then the earlier
   publication of a session, then the digest), until the night's own record fits;
   that record never gives way. Of the caps, only a record too large to fit
   alone refuses the catalog; an invalid or unsafe original, a file over 256 KiB
   or more than 10,000 signals refuses as before. Each refusal leaves the old
   catalog. The run log states the catalog against both
   caps, warns past 80% of either, and names the sessions that gave way; the
   catalog is written before the quality ledger, which captures the night
   whatever the catalog did. Originals load only when selected; chart
   evidence is at most the authentic 120 published bars. Absent charts stay
   absent. Revisions keep separate provenance. An unavailable original is never
   reconstructed from a later signal. Local saves do not expire with this window.
   Observed movement uses the dated original research close, not personal P&L;
   neither saving nor marking can create a ticket or change public strategy results.
8. **Sample data.** A record written by `tools/make_fixture.py` says so:
   a *Do not trade sample data* notice under the market bar naming the
   fixture, a *demo data* chip on the chart panel and the burst map, a
   *demo* chip on a followed card, and a chart-reader reply labelled
   simulated. Demo follows are kept under their own browser key.
9. **The next action**, under every view, and it names the session rather
   than saying *tomorrow*: *Review N conditional tickets for Mon 14 Sep*
   before the window, with preparation and protective-stop terms conditional on
   the reader choosing to follow a plan, *The entry window for Mon
   14 Sep is in progress* inside it (with the last observed data timestamp
   kept in view, and live trigger and fill conditions said to be unverified
   here), *The entry window for Mon 14 Sep has ended* after it — where the
   cancellation is conditional, *if you submitted an order that did not
   fill*, and SpicyStock is said to place and cancel nothing. Otherwise
   nothing to place, no new longs, plans unchanged, or do not place these
   orders. 9:28 AM is the desk's own preparation reminder
   (`timing.PREPARE_BEFORE_ET`), never the cutoff.
10. **Check for updates**, one control beside the publication line. It
   re-reads the same static record and nothing else — no rescan, no grading
   call, no paid request, no dispatch, no polling. It reports unchanged (the
   served bytes are identical, so no Following observation is added), a
   newer session, a file for an EARLIER session (refused rather than applied
   backwards), the same session re-published on later bars (a revision of
   that trading day, not a second one), or a file it could not read or
   reach. Startup and manual refresh each have a 15-second deadline covering
   response headers and the complete bounded body. A press aborts the previous
   attempt and only the newest answer can land. Failed startup offers **Retry**;
   saved private reports remain readable and editable in the Morning desk while
   the publication is unavailable. There is no current entry preparation or
   copying in that state. A failed refresh keeps the displayed record and
   unsaved private inputs; a retry never saves or migrates them automatically.
   A load hands back the stage, the stock and the search, keeps the
   theme, the lens, the chart's mode and range, every saved identity with
   its frozen evidence and a half-typed reference size — and closes a
   comparison rather than remapping its pins onto other stocks, saying so.

The email is the same record in fewer words: the verdict, the breadth line,
one block per trade with its buy stop, its limit and the line under which an
open is skipped as three prices, its order line and the day-order term, then
Fidelity's part-fill rule and, after the burst orders only, Fidelity's
buy-stop rule, the plans
without a ticket and why, the open model plans' instructions, the alerts,
the problems and a link. Delivery failing never costs the page.

## How a night runs

`evening.yml` is scheduled at 6:16 PM ET on weekdays (two crons, one per UTC
offset) and again at 8:16 PM ET as a retry. GitHub may deliver either job hours
late. The guard resolves the intended occurrence and exchange session, checks
the offset at that occurrence, skips holidays and refuses a delayed run once
the next session opens. Both scheduled slots skip an already published real
ok/degraded record for that session; a failed or rehearsal record cannot
suppress recovery, and a newer publication cannot be replaced by a late job.
Manual dispatch keeps its explicit session and rehearsal controls, and has a
fourth box, **only_if_unpublished**: ticked, the dispatch is decided by the
scheduled slots' own rule -- the newest completed session is published only if
its primary slot (6:16 PM ET) has passed, it is still unpublished and the
session after it has not opened, and otherwise the run does nothing. It waits
for the slot as the schedule does, because a session's bars still move after
the close, and a record published earlier would make both slots skip. It takes no session. It exists so that a trigger outside
GitHub's scheduler can start the evening on time, every evening and twice,
without ever publishing a session a second time; a plain dispatch (the box
unticked) runs as it always did. Every
publication archives where it fell against that schedule (`run.delivery`,
`src/delivery.py`): its latency after the measured session's completion, the
two slots as instants in the exchange's zone, which of them it followed,
whether it landed before the next session's open, and the policy words -- the
slot times and that a missed session may be recovered until the next session
opens -- that the page and the service-health reading print rather than
re-derive; `report.validate()` holds the block to the slots the record
archived, and a record from before the block is asked for none. The run:

- **universe** — Nasdaq's security-name and industry classifier approximates
  common stock; it is not exact TC2000 membership. Blank-check exclusions use
  the exact industry label or a narrowly bounded `Acquisition Corp[.]` /
  `Acquisition Corporation` legal name, optionally numbered, immediately
  followed by a common/ordinary-share label. Generic acquisition, capital,
  investment and holdings words do not exclude a company. The
  [retained-directory correction](docs/input-truthfulness/2026-09-22-blank-check-classification.md)
  documents every newly excluded name; it does not explain absent provider bars
  or revise the September 18/21 publications. Directory price and volume
  never gate discovery. Broad healthcare/category and domicile warnings remain
  flags (`biotech` / `foreign`), not verified company classifications or
  stock-specific risk assessments. The
  seven-day cache and 227-name seed fallback remain explicit. Seeds can bypass
  classification; overrides and additions are counted. The 8,000-name capacity
  safeguard retains seeds, ranks any remaining tail by directory dollar volume,
  and counts every cut. A capacity cut degrades coverage; it can lose a breakout
  and is not a strategy rule. It does not bind on the archived September 15
  directory: 4,797 selected stocks versus 3,039 under the old quote gates.
- **fetch** — 260 sessions of daily bars from Alpaca's consolidated `sip`
  feed, explicitly split-adjusted, not raw or dividend-adjusted. The request
  remains sixteen minutes behind the clock, in chunks, under a 900-second budget.
  SPY rides along for the scorecard. The archived population expansion changes
  estimated initial SDK batches from 31 to 48, before pagination/retries; it does
  not raise the timeout or the twelve-call chart-reader cap. Actual calls can
  vary with qualifying candidates within that cap; this milestone used none.
- **session and coverage** — XNYS owns expected session dates and hours;
  missing bars on an expected session are outage/coverage evidence, never proof
  of a holiday. Each frame needs the evaluated session and the required previous
  session with readable OHLCV. Fewer than half the intended stocks with usable
  session bars refuses publication before grading; the denominator excludes SPY.
  At least half but less than all leaves the ledger's acceptance degraded, as
  does any capacity cut or scan/quality error. The run itself is degraded too,
  unless the only gap is stale frames each ending within the 5 sessions before
  the session evaluated -- at most 1% of the intended stocks, no stock under an
  open model plan among them (SPY is outside the stock count here, as in
  acceptance) -- which
  `run.input_tolerance` names, with where each frame ends. From the rule's third
  version (`pipeline.input_tolerance_version`, 3) stocks with no bar before the
  session evaluated in the run's request window -- a gapped frame every row of
  which the provider dated that session (`market_data.history_begins_on()`), as
  on an exchange listing's first day -- are counted beside the stale tail
  against the same 1%, named (`first_sessions`, counted and not named past
  `pipeline.STALE_NAMES_MAX`) and never measured. The 19 October 2026 revision
  and the 30 October publication (LCU, NORD) were each degraded by one gapped
  frame alone, a stock new to that night's directory; whether that frame had any
  earlier row the records cannot show, which this version now records. A gapped
  frame with any earlier row -- a real hole, or earlier rows it cannot read -- is
  the gap it always was, and a record whose rules archive no tolerance version
  is held to the second version's rule. The next session's
  run, when it publishes, reads each of them again from its own split-adjusted
  fetch at every session it missed, one reading per stock and session, with no
  extra provider call (`run.stale_followup`, `src/followup.py`), and a late bar
  that the publication for that session would have listed (a 4% or $ scan match, or a setting-up
  name) makes the night that finds it degraded and is named. A late bar is never
  a signal, plan or ticket. `run.seed_stale` says which of the stale stocks the
  seed alone asked for -- a name the directory no longer lists -- read off the
  record's own stale names and the selection ledger's seed additions when
  both are complete (the ledger names at most `universe.SAMPLE_LIMIT`, 8,
  seed additions, archived as `universe.sample_limit`; past that the block
  says they were sampled and names none) and said to be unknown otherwise,
  because a seed name is asked for again every night until a human retires it
  from `data/symbols.txt`; the cover's coverage line, the page's Method and the
  mail print its sentence. A fully evaluated selection can be complete without being the
  complete listed market. The existing $3 session-close policy now reads actual
  cent-rounded bars, with seed/explicit exemptions preserved; actual scan volume
  remains the scanner's rule. Known non-session runs skip before universe/provider work and preserve the prior publication.
  No-bar responses, failed batches, budget-unfetched names, stale frames, gaps,
  unreadable pairs and repaired duplicates are distinct in `run.coverage`.
  Counts reconcile from selection through measured burst/dollar/both/neither and
  quality outcomes; each reason carries a bounded sample and membership digest.
  Below-threshold failures retain their population on `RunReport.input_coverage`
  and in the run log, leaving the last published record intact.
  A separate **input-exceptions** artifact retains every exception name and
  bounded normalized observations before coverage refusal, scans or grading.
  Its run/session/revision identity, complete intended membership and input
  counts reconcile with the compact ledger. Files live under the gitignored
  `input-diagnostics/`, outside `docs/`; the existing evening artifact is unchanged.
  These are input-stage observations, not final measurement counts or raw
  provider evidence. Missing frames stay missing. Capture failures are logged
  separately and do not alter publication decisions or exit codes. See the
  [format and offline verifier](docs/input-truthfulness/README.md#input-exception-artifact-v1).
  `run.universe` records the source, capture timestamp, snapshot hash, selection
  identity, exclusions and the snapshot date's relation to the scan session.
  A contemporary or cached directory never proves historical point-in-time
  membership; pinned sessions carry that limitation. No survivorship-bias-free
  historical backtest is claimed. `run.input_basis` records the feed, split
  adjustment and expected/evaluated sessions; recovery copies the original run.
  Older records without these fields remain explicitly unknown on the page.
  See `docs/input-truthfulness/README.md` for conservation equations and offline impact.
  The [September 18 stale-input investigation](docs/input-truthfulness/2026-09-18-stale-inputs.md)
  pins retained evidence and separates the missing-bar symptom from unresolved causes.
  Method shows the ledger concisely, and incomplete empty results are qualified
  beside the verdict and empty-state text.
- **breadth** — the Market Monitor columns over the stocks measured that
  night and the regime, five rules: red (no new longs; an open plan's
  instruction gains a sell-into-strength clause and no stop is moved) on names
  down 4% at or over 700 scaled, a 10-day ratio under 1, or a 5-day ratio under
  0.5 with more down than up; yellow (half size, A+ only) on a 10-day ratio
  under 2 or more than 20 scaled names up 50% in a month; green (full size)
  otherwise. The two counts are scaled by measured stocks / 6,500 (378.3 and
  10.8 on 17 November 2026); the ratios are not.
- **scan** — the repository's recorded formulas: `c/c1 >= 1.04 and v > v1 and v >= 100000`
  and the dollar breakout `c - o >= 0.90 and v > 100000`, then the
  checklist over every hit: **2** not up two days in a row, **L** a linear
  prior leg, **Y** a young trend, **N** a narrow or negative prior day,
  **C** a tight base with at most one 4% breakdown, **H** a close near the
  high, plus range expansion and volume. A run of three up closes or a
  non-linear leg is a veto. A+ and A need 2 and H. The dated
  [consolidation source contract](knowledge/consolidation-quality.md) separates
  Bonde's historical variants from DERIVED segmentation, ratios and C A+ policy.
  The [retained C audit](docs/input-truthfulness/2026-09-22-consolidation-source-fidelity.md)
  reproduces the measurements and their sensitivity without retuning thresholds.
- **admission** — which discovered candidates the trade band and the chart
  reads may consider (`src/admission.py`, the owner's rule of 4 November 2026):
  a name the 4% scan discovered is admitted; a name the dollar scan alone
  discovered is admitted only when its burst day passed the checklist's RE and
  VOL checks (a range at least the largest of the prior five sessions' and
  volume above the previous session's), the two expansion checks the
  checklist already measures but does not score. The dollar scan's $0.90 body
  asks nothing of a day's gain, range or volume and does not scale with price:
  over the 35 retained sessions to 3 November 2026, 1,913 of 2,473 mechanical
  A-band grades came through it alone, 1,757 of them on a day under +4%, and
  187 of 244 chart reads went to such names. Every reaction row carries
  `admission` (the route, the basis -- `burst_route`, `dollar_expansion` or
  `dollar_no_expansion` -- the two checks as recorded and the reason in the
  record's words) and `run.admission` counts the night by basis and over the
  A-band names without a veto, with one sentence the Method view and the mail
  print verbatim. Admission is never a grade: a stopped name keeps its
  checklist grade as research, earns no plan, no ticket and no chart read, is
  blocked by the review selection as `route_not_admitted`, stops at the
  funnel's `route` stage and is sealed in its plan gate as
  `route_not_admitted`; the headline's reader-wait counts only admitted names.
  `report.validate()` re-derives every block from the row's own route and
  checks and refuses a record whose rules archive the family without them, or
  one that carries them under rules that archive none. A record from before
  the rule reads every graded name as admitted. The scan formulas and the
  checklist are unchanged, and the rules digest moves.
- **grade** — Claude reads the chart and the numbers for up to twelve
  bursts and may only LOWER a grade, never raise it. The versioned
  `account_feasible_first_research_v2` policy prioritizes private pre-review
  plans that satisfy the mechanical grade/regime, veto, discovery admission,
  known-event, entry geometry and whole-share checks. Their existing mechanical
  grade / descending score / ticker order is preserved. All feasible names are
  covered when the twelve-name budget permits; none is displaced for research.
  At most 2 spare reads go to infeasible mechanical A+/A research whose
  discovery is admitted: one by that same rank, then one by the lowest SHA-256
  of policy, measured session and ticker. A name the admission stopped is
  blocked as `route_not_admitted` and is not research either. Version 1 (10
  October to 3 November 2026) had no such blocker and is replayed under its own
  frozen rules (`review_selection.RULES_V1`), so every retained publication
  still verifies. With no
  feasible names this is at most two reads, and an empty research pool makes
  no model calls. This near-admission sample is not an unbiased market sample.
  `bursts[].review_selection` retains each purpose and checked blocker;
  `run.review_selection` reconciles feasibility, research-pool size, selected
  names, accepted/unaccepted/refused results, actual retained attempts and
  unused capacity. Attempts are distinct from requested names and billed cost.
  Method explains reconciled pre-review fit and opportunity/research selection.
  The Morning desk adds selected-batch completion separately from broader
  review coverage only when the supporting counts reconcile. The cover carries
  the same facts only under the reader-wait headline (`report.H1_READER_WAIT`),
  as one collapsed line naming the accepted selected reviews and the mechanical
  A+/A names still unreviewed; every other night's first screen is unchanged.
  A completed research batch does not mean all discovered candidates were
  reviewed or that any plan is admitted. The original published summary remains
  available; missing, unsupported or contradictory completion evidence leaves
  that wording in place without the new completion claim.
  The private preview precedes combined allocation; selection grants no ticket.
  Final accepted-review, grade/regime, sizing, event and allocation guards
  remain unchanged. Archived records without this policy keep their original
  selection contract. A new rules identity also retains the existing
  conservative reservation behavior for open model plans.
  The rulebook it reads is `knowledge/strategy.md`. No reply, or a refused
  key, leaves the checklist's grade standing for research and marks the night
  `claude_unavailable`. Every new reaction row records `reader_coverage`:
  `accepted`, `fallback` (selected but no accepted result), or
  `not_selected_budget`; missing legacy evidence remains `unknown`.
  Rejected/unavailable fallback and budget exclusions are not reader approval
  and do not measure a bad setup. Neither may enter final burst planning.
  Each reaction row archives a versioned `discovery`
  block from those same scan rules and measurements: `burst`, `dollar` or
  both, with applicable and explicitly inapplicable rules kept apart. A
  dollar-only candidate does not require a +4% close-to-close gain to be
  discovered; to be admitted to the trade band and the reads it needs the
  range-expansion, higher-volume day above, so every dollar-only candidate the
  reader sees has one. Quality
  can still be lowered for independent chart/checklist evidence. Recognized
  contradictory replies are rejected whole into mechanical fallback without
  a retry; their score and explanation are not published as chart judgement.
  Reader authority v1 additionally requires a permitted criterion/source/observation
  and exact citations to structured checklist evidence for any downgrade. Missing,
  unknown, contradictory or unauthorized evidence rejects the whole judgement
  without retry and leaves the mechanical grade standing; such refusals, and the
  discovery contract's, degrade the night only once they number more than both
  a quarter of the night's reads and one, when none is accepted, or when the
  refused name would otherwise have been planned. A reply that never arrived
  or could not be read always degrades it, and an empty credit balance stops the
  calls the way a refused key does. `run.reads` counts the shortfall by cause, and
  `run.reader_usage` says what the reads cost in the API's own units -- the calls
  sent, the replies received and the four token classes a reply reports (uncached
  input, written to the cache, read from it, output), under the model the run
  asked -- with no price, because a price is the provider's list and not a fact
  the run observes. The reader's SDK is held below 2.0 in `requirements.txt`:
  anthropic 2.x sends API version 2026-10-21, under which the Messages API
  refuses the `temperature` the grader sends on purpose, and every reply of the
  21 and 22 October 2026 runs was an HTTP 400 that `run.reads` version 1 counted
  as `transport`, the one cause it had for an answer it did not know.
  `grader.API_VERSION` names the validated version and `tests/test_grader.py`
  reads the header off the wire, so a loosened pin fails CI, not the evening.
  The packages underneath are pinned as well: `constraints.txt` holds the 44
  packages the evening's own runner installed on 24 October 2026
  (python-dateutil under pandas, matplotlib under mplfinance, pydantic under
  anthropic) and the five the suite adds. Every workflow step that installs
  `requirements.txt` installs `-r requirements.txt -c constraints.txt`, and
  `requirements-dev.txt` carries the same `-c` line, so CI runs the suite
  against the night's own runtime set; `tests/test_requirements.py` holds the
  file to one resolution of the requirements and to what the suite has
  installed, and every pip install a workflow runs, read by pip's own option
  parser, to a requirements file it accounts for. Two files are not
  constrained by it: `requirements-host.txt` pins the morning host's whole set
  (so the suite does not run against the host's versions), and the historical
  jobs' `tools/requirements-historical*.txt` pin their direct requirements
  only.
  Since 24 October 2026 (`run.reads` version 2, `pipeline.reads_version` in the
  archived rules) a request the API refuses as invalid is its own cause,
  `request`: the SDK's own classes for an HTTP 400 or 413 whatever the body
  (`grader.REQUEST_REFUSAL_LABELS`; the SDK spells a JSON body "Error code: 400 -
  ..." and a text, HTML or empty one without that prefix), or that status prefix
  carried by another wrapper, and never the empty-balance answer, which is read
  first as the account's. The request is not asked again (a transport retry would
  send it unchanged and be refused the same way), and after
  `grader.REQUEST_OUTAGE_AFTER` (two) consecutive names are refused with one
  message -- the API's own, the per-request id removed (`grader.refusal_key()`) --
  the run stops asking: the remaining names fall back without a call, each
  carrying the run's own sentence (`grader.RequestOutage`, the message and no
  request id) rather than another name's answer, counted under `request` and
  under the block's `unasked`, which the sentence says ("N names' requests were
  refused ... ; after 2 refused alike the run stopped asking, and M names went
  unasked"). The rule is message equality, whatever the message names: a
  refusal whose text varies per request (a prompt too long by a count) cannot
  reach two, and two names refused alike for their own content (every chart over
  a size limit) are read as the API's answer to every request. The validator
  holds a record's block to the version its rules archived
  -- version 1 and its five causes for every record from before -- and the page
  reads each version in its own words, folding a refused request into
  `transport` for a version-1 record as that record did. The funnel (version 2,
  `review_request`) is likewise re-derived under the version a record archived,
  so a version-1 publication is still held to its own stages, shape and sentence,
  with the refusal at `review_transport` as it recorded it.
  Every reply that arrived is billed, a reply the checks then
  refuse or cannot read included, and each attempt's own bill is kept beside the
  attempt, so `report.validate()` re-derives the block's totals from the bursts'
  own evidence and refuses a block that is not theirs; a record made before the
  rule is asked for no block. The Method view and the mail print its sentence
  verbatim. `tools/whole_share_feasibility.py` is the reading beside it: every
  reaction candidate a publication archived sized again through `plan.burst_plan`
  at the account the record archived (or one given on the command line, labelled
  a counterfactual) under the record's own regime, YELLOW and GREEN, counting the
  mechanical A-band names without a veto, how many pass the stop rule and how many
  size to a whole share, with the limit under which one share fits a
  stop-constrained ticket at each multiplier; it changes nothing and a YELLOW or
  GREEN column on a RED night is a counterfactual, never a ticket.
  `tools/evidence_review.py` is the explicit evidence review #109 asks for before
  any strategy change is promoted, dated: it writes the 7 November 2026 review
  (`evidence-review-v2`) into
  `docs/input-truthfulness/2026-11-07-evidence-review-evidence/review.{json,md}`,
  and `--check` holds both; the 12 October review it supersedes stays under its
  own directory, frozen to its git blobs by `tests/test_evidence_review.py` and
  never re-derived. It re-derives the frozen signal-outcome study from its own
  rows (refusing a file whose summary is not its rows'), splits the admitted
  stratum by phase, regime, calendar month, halves of each phase's nights,
  mechanical grade, the account each publication archived and the discovery
  admission route, walks each stratum's cumulative-R path for its deepest
  drawdown, copies the backtest, funnel, feasibility, registered-research and
  live-scorecard numbers off their files with each file's digest, and evaluates
  a fixed ledger of the strategy changes this repository has floated -- and the
  two it promoted on 4 November, read after the fact -- against criteria it
  states and archives (a rate at `record.SCORECARD_MIN_PLANS` settled or more;
  a sign only from a night-bootstrap interval clear of zero, which the study
  draws over two or more nights; `supported` only when every direct source is
  positive and every evaluation period agrees; a population a change would stop
  trading shown as `removed` and never counted). Five inputs are retained under
  that directory's `inputs/` as commit `af21693c` carried them -- the findings
  file, the research cohort and journal byte for byte, an extract of the live
  record's own scorecard, and the join of every study row to its publication's
  discovery admission re-derived off git -- each with original commit/path and
  exact SHA-256 provenance checked before reading; missing or changed bytes
  refuse before writing, and `--retain` writes them from git once and refuses
  to overwrite. The one figure it quotes from the 12 October review (the
  exploratory sign and settled count then) is read off that review's frozen
  `review.json` under its own pinned digest, never retyped. The candidate-funnel
  and whole-share-feasibility readings it reads are dated the same day and
  pinned to the same commit. The current
  rolling cohort, journal, findings file and record may advance without
  rewriting this dated review. A later evidence review needs a separately
  dated output. No change is promoted by the 7 November review, and none earns
  `supported` in it.
  `tools/service_health.py` reads the service rather than the signal: it walks
  the commits that put a publication on `main` and the commits that put a
  morning, issuer or research receipt beside it, and prints, per expected XNYS
  session, whether a publication landed, when (its latency after the session's
  completion and after the evening cron's slots, read in the exchange's zone:
  the slots the record's own rules archived (6:16 and 8:16 PM ET so far), or
  the current policy's for a record from before the rule, and the reading
  says which), whether before the next open, how many times, what the
  inputs covered, what the reader did and what it cost, with the regime and the
  ticket counts in a column that makes no service verdict. "Landed" is the
  committer time of the commit that put the record on `main` (the push follows
  it by seconds); the record's own `published_at` is when the run generated it
  and is printed beside every landed fact, never read as one. A session's
  publications are in the history's own order, never a clock's, so its first
  delivery is the first commit on `main`; fresh is what `main` carries -- its
  newest record commit, read or set aside -- for the newest due session. A
  commit whose file it cannot place -- one that is not JSON among them -- is set
  aside by name and never stops the walk; a git store that cannot produce a
  named object is a refusal. A publication whose rules archive the delivery
  rule is read against those slots only once its `run.delivery` re-derives
  from them (`delivery.faults()`); one without its block, or a block beside
  rules that archive no delivery rule, is set aside by name and does not count
  as a publication. A session reads unpublished only when no other readable
  publication exists for it. It
  writes `docs/input-truthfulness/2026-11-07-service-health-evidence/service-health.{json,md}`
  pinned to one commit whose time is its clock; `--check` re-reads the commits
  the file names (fetching them into a shallow checkout) and holds both files.
  The 12, 13 and 17 October readings beside it (the 12th's v2, and v1 under
  its `v1/`) are kept as they were written and no longer re-derived; the tests
  hold their bytes.
  `tools/recovery_rehearsal.py` rehearses what #111 asks the service to survive:
  it drives `pipeline.run_evening()` through the suite's own doubles over one
  synthetic market, one pinned night after another, injecting one failure a
  night -- the bars endpoint refusing every batch, every frame served two
  sessions stale, the reader's account out of credit, the reader's transport
  dead, the mail provider refusing the digest -- and before and after each night
  executes the evening workflow's own guard (the Python body of `evening.yml`'s
  guard step, as written, under a frozen clock) at the primary slot, the retry
  slot, the next session's open and for a delayed event. It records the exit
  code, what was published and for which session, whether the previous
  publication's files survived byte for byte, how many times each boundary was
  asked against the fetch's and the grader's own retry bounds, what was mailed
  and what the guard decided, and writes
  `docs/input-truthfulness/2026-10-12-recovery-rehearsal-evidence/rehearsal.{json,md}`;
  `--check` runs the whole rehearsal again and holds both files. It decides
  nothing and calls no provider: every failure is injected, so it shows what the
  code does under a failure it was told to have, not how a real provider fails.
  `tools/schedule_reliability.py` reads when GitHub started each scheduled run:
  `--fetch` snapshots the public Actions listing of scheduled runs, and of the
  runs a push to `main` triggered as a contrast, keeping only the fields the
  reading uses, beside each scheduled workflow's cron tables as `main` carried
  them version by version. Every run is placed at the slot its run name's cron
  names (or, for a name without one, the nearest preceding slot of the table
  in force). The reading writes the minutes from slot to creation -- the
  scheduler's own delay, before any step of ours runs -- per workflow, cron and
  week; every expected slot with no run; and the first run more than an hour
  late, with the last prompt one before it. It writes
  `docs/input-truthfulness/2026-10-13-schedule-reliability-evidence/schedule-reliability.{json,md}`
  beside the snapshot `runs.json`, and `--check` holds both to the snapshot with
  no network. It decides nothing; the dated report beside it lists the options
  for the morning's delivery without adopting one.
  `tools/stale_inputs.py` reads what became of the stocks a publication could
  not measure: each session's newest publication names its stale
  stock-sessions (`run.input_tolerance`, every session a named stock missed as
  `followup.missed_sessions()` counts them), and the reading joins them to
  every later follow-up reading (`run.stale_followup`, which runs the
  evening's scans on a late bar that arrived, is in that run's selection and
  passes the $3 policy) and every source-recovery receipt's row, then puts
  each stock-session in one class: a late bar a follow-up would have listed,
  one it scanned and would not have, one under the $3 session-close policy,
  one read only for its volume -- under, or at or above, the 100,000-share
  floor the 4%, breakdown and $ scans read on the session itself
  (`scans.MIN_VOLUME`; the setting-up scans read the three sessions before,
  so volume alone does not settle them) -- one that arrived with its volume
  unread, or no later bar at all. A stock-session's verdict is the last
  follow-up reading that gave one, so a later reading without a scan, such as
  a re-run that no longer selected the stock, does not undo it. It writes
  `docs/input-truthfulness/2026-10-17-stale-inputs-evidence/stale-inputs.{json,md}`
  pinned to one commit; `--check` re-reads the commits the file names and holds
  both files. It establishes no cause for a missing bar, changes no record and
  asks no provider anything.
  Visual findings require a supplied chart; recorded FAIL/PARTIAL findings can
  use measurements. Subjective chart truth and free commentary remain unverified.
  Every model receives the same nested findings schema in text; supported models
  also receive it through structured output. Findings and citations remain closed
  objects. From request version 3 (`grader.REQUEST_VERSION`) a citation's path is
  an enum of the paths `reader_evidence` carries (`reader_authority.EVIDENCE_PATHS`,
  over `CHECK_VALUES`, the value fields `quality.assess()` writes), and the
  instruction names the checks each criterion may cite (its `CRITERIA` letters);
  the validator is unchanged and still checks every rule. One schema branch per
  criterion, each with its own paths, was refused by the API on 30 October 2026
  (HTTP 400, "The compiled grammar is too large"; dry run 41120821225), so which
  real check a criterion may cite is the instruction's to say and the validator's
  to hold. Of the 30 replies reader authority refused from 23 September to 29
  October 2026 (`tests/fixtures/grading/reader-authority-refusals/`), 3 cited a
  path `reader_evidence` does not carry (HAE twice, TTEK), which the schema now
  refuses at decoding; 23 cited a real check their criterion does not list -- each
  a visual finding -- which the instruction addresses and the validator refuses;
  4 named a measured_quality defect on a candidate whose eight checks all
  recorded PASS, which the validator refuses and the instruction now addresses
  (no FAIL or PARTIAL means no measured_quality finding). The verifier rebuilds a record's
  reader requests under the request version it archived (2 or 3, byte for byte);
  a record made under another is partial. Returned text is retained before
  parsing/authority checks in each attempt, with its SHA-256, byte count, stop
  reason and message ID. Text above
  64 KiB is explicitly omitted with its digest and size retained. Rejected text is
  diagnostic evidence, never an accepted judgement, and the quality ledger retains
  those attempts unchanged. Authority failures still do not retry; only parser
  failures receive the existing format-correction retry. The September 22 replies
  were discarded before this correction, so their exact fields and semantic
  authority cannot be recovered; see [the incident audit](docs/input-truthfulness/2026-09-23-reader-authority-production-compatibility.md).
  See [the 108-decision audit](docs/input-truthfulness/2026-09-22-reader-downgrade-audit.md). The reader
  result archives the discovery version and a SHA-256 of the initial system
  and user text; transport, cache prefix and down-only clamping remain intact.
  See `tests/fixtures/grading/history-audit.json` for the bounded, manually
  reviewed historical audit. Old published reasons and grades are unchanged.
  The page's primary explanation reports the recorded checklist and grade
  outcome. Original reader reason, risk and entry commentary remain inspectable
  in Provenance and are labelled unverified; recorded checklist criteria govern
  thresholds and only the published plan defines order terms. Saved and recovered
  originals carry the same qualification. This presentation boundary does not
  fact-check arbitrary prose, regrade a result or rewrite a historical receipt.
- **plan** — an accepted reader review is required in addition to the existing
  grade, veto and market gates: GREEN admits final A+/A, YELLOW only final A+,
  RED none. The versioned `pipeline.reader_policy` records this requirement;
  the decision receipt records coverage separately from market permission and
  ticket status. An admitted burst gets a plan sized from the configured
  account (default $10,000, 0.5% risk, 25% cap, four slots). Four prices it
  keeps apart, because they are four rules: the **trigger**, a buy stop at
  the burst close plus `plan.trigger_cushion()`, the larger of
  `plan.TRIGGER_CENTS` and `plan.TRIGGER_FRACTION` of the close, the same
  cushion a setting-up ticket sits over its box (`plan.burst_trigger()`:
  the `close_plus_cushion` rule the record archives as
  `plan.burst_trigger_rule`; a record made before it, which archived none,
  was made and is replayed under `close`, the buy stop AT the burst close); the ticket's **limit** (`plan.burst_limit`), the day-2
  ceiling narrowed to the highest price at which the structural stop is
  still inside his 4% line,
  `min(close +4%, floor_to_cents(stop / (1 - plan.MAX_STOP_PCT/100)))` over
  the burst low then the bar's midpoint; the **day-2 threshold**
  (`day2_spent_above`, the close +4%), above which his follow-through is
  already spent — the skip rule, never the order's limit; and the
  **indicative entry** (`planned_entry`), the close +1% capped at that
  limit, which the exits and the targets are quoted from and which is
  never a fill. The shares are sized at the limit. A trade is a plan with
  an order: a setup no limit above its buy stop can hold a stop under (the
  synthetic 4% level never buys a ticket, and a limit landing ON the
  trigger is a ticket with no band), plans past the free slots or the
  equity, and a plan the account cannot size to a whole share, are listed
  as cut with the kind and the reason. An anticipation ticket is judged
  and sized at its limit the same way. Reaction plans and anticipation plans
  share one allocation, with reactions considered first and anticipation in
  watchlist rank. Existing occupied model plans reserve their original model
  principal even after partial sales; uncertain observations do not create free
  slots or cash. Zero-share refusals show the effective risk budget after size
  reductions and the position cap. This allocation is a model, never the owner's
  observed holdings or settled cash.
  A dated manual corporate-action registry with primary-source links withholds
  known cash-takeover candidates from both kinds of momentum ticket. Its
  evidence is part of the rules identity; a due review does not silently clear
  an exclusion. Unknown names have not passed a comprehensive live news check.
  ZIM was added on 10 October 2026 after reviewing its 16 February $35 cash
  merger announcement, 30 September Israeli approval-process update, and
  6 October guidance release identifying the transaction as pending. The
  guidance increase remains useful research context; it does not remove the
  existing takeover exclusion. This addition does not establish live news or
  earnings-calendar coverage for other candidates. The [captured issuer and
  SEC sources](release-evidence/2026-10-10-zim/README.md) retain the reviewed
  bytes, source dates, retrieval times and digests.
  CCC was added on 20 October 2026 from its issuer's 15 October announcement
  of the pending GTCR/Elliott $7.75-per-share cash acquisition. This uses the
  same unresolved-event exclusion; neither the expected closing quarter nor
  the review date clears it. The [bounded source receipt](release-evidence/2026-10-20-ccc/source-manifest.json)
  records the dated release, short excerpt and response digest. Existing
  published records keep their original evidence; the next verified production
  publication must establish this added exclusion on the site.
  The registry was reviewed again on 19 November 2026. Every review date had
  passed, the oldest on 15 October; a passed date never clears an entry, so
  each stayed blocked. MISTRAS's 28 October release (the go-shop ended with no
  competing proposal; a stockholder vote on 24 November) was added as a source
  for MG from the day it was published, from bytes the issuer-evidence collector
  had itself captured (the collector's text of them and the response's digest
  are kept beside the manifest, since the archive they were published in drops
  a superseded bundle after 21 days; the response bytes were not kept). Six
  review dates were moved (MG to 25 November, ZIM to
  2 December, PRTH, ARX, BWIN and CCC to 17 December). Five of those six
  findings were read as web-search excerpts in a sandbox that reaches neither
  sec.gov nor issuer sites, and say so in the
  [review manifest](release-evidence/2026-11-19-event-review/manifest.json);
  none of them added a source. ACV Auctions, whose acquisition a search excerpt
  says Copart completed on 16 October, stayed listed and blocked until a captured
  source resolved it; its entry carried a `review_note`, dated after its review
  fell due, saying so. On 25 November 2026 Copart's release was captured from a
  runner that reaches sec.gov (`tools/capture_sec_document.py`, one request,
  its digest in the job log), and the entry was resolved with it: its interval
  ends on 16 October, the release's date, and it blocks no session after that
  (the [ACVA manifest](release-evidence/2026-11-25-acva-resolution/manifest.json)
  says how it was read). MG was reviewed again on 25 November 2026, the day its
  review fell due: search results for the company's 24 November release say
  its stockholders approved the merger that day and that it has not closed, so
  the entry stays listed and blocked; its next review is due 17 December. That
  finding is a summary of search results, not a source, and added none (the
  [25 November manifest](release-evidence/2026-11-25-event-review/manifest.json)
  says how it was read). A review date says someone looked that day and how; it
  does not establish that a deal is still pending today. The daily brief and
  the Method view state how old the review is. CI runs
  `tools/check_event_reviews.py` on the real New York date
  (`event_risk.lapsed_reviews()`): the day after an unresolved entry's review
  falls due, it is red until the entry is reviewed again or carries a
  `review_note` dated after the due date. It is the one check whose answer
  moves with the calendar, on purpose. A note never clears a stock, and a
  classification carries no note.
- **record** — the picks go to `docs/picks.json`; the open plans and the
  scorecard are computed from it and the bars. Suggested shares are model
  sizing, never shares bought. New plans carry a versioned evidence reference.
- **publish** — source, discovery, checklist, reader, regime and plan evidence
  must verify before the serialized data/picks pair replaces the previous
  publication. Source-object staging handles close before installation, including
  on Windows; a required evidence write failure withholds publication.
  Contradictions fail closed. Then the email
  goes out. The workflow commits `docs/` back on exit 0, 2 or 3 (never a
  rehearsal), and `publish-dashboard.yml` asks GitHub Pages for a build,
  because a token push does not trigger one. It then fetches every file the
  page loads -- the HTML, both records, each script and stylesheet, the
  vendored design system -- and fails unless the public bytes are the
  commit's; the list is read off `docs/index.html`, not kept beside it.
- **Where every candidate stopped.** `report.build()` composes `funnel` last, off the
  cleaned record (`src/funnel.py`): every discovered reaction candidate and every
  listed anticipation setup is given exactly one terminal stage, in the order the
  run applies its gates -- the regime (RED stops everything at `market`), the
  mechanical grade against the regime's admitted band, the quality veto, from
  funnel version 3 the discovery admission (`route`: the dollar scan alone,
  without a range-expansion, higher-volume day), then for
  a name the review budget never reached the selection's own recorded blockers
  (`preview_event`, `preview_geometry`, `preview_sizing`, `preview_no_order`,
  `review_budget`), for a reviewed name the reader's state (`review_refused`,
  `review_format`, `review_account`, `review_credit`, `review_request`,
  `review_transport`, `review_downgraded`), then the constructed plan's own combined allocation
  (`event`, `geometry`, `sizing`, `allocation_slot`, `allocation_cash`,
  `allocation_occupied`, `ticket`). The stage counts sum to the discovered count
  by construction, `potentially_usable` counts the names that passed the first
  gates (the grade and the veto; from version 3 the admission too, and the
  sentence says which), the labels the page and the mail print travel in the block, and
  `report.validate()` refuses a block the record does not re-derive. A record made
  under older rules is read for what it recorded -- a field it lacks is `unknown`,
  never guessed, as is a regime that is not a verdict the rules name and a row
  without a mechanical grade -- and is asked for no block. The scan disclosure
  prints the table and the sentence, each matrix row says where its name stopped,
  and the mail prints the same sentence; the page prints a block only when every
  field it indexes into has its shape (integer counts, a non-blank sentence,
  string rows) and says the funnel was not archived otherwise. `tools/candidate_funnel.py` reads the funnel of any
  publication, or of every retained one on a ref, and changes nothing.

Exit codes are the workflow's contract: **0** clean, **1** failed before
publishing (the failure notice is mailed instead, when the failure came
after preflight and the delivery keys are there), **2** degraded but
published (a warning, not a red run), **3** published but the email failed.
The failure notice names the stage the run stopped at, one of the words the
code owns (`report.NOTICE_STAGES`), and leaves what the run raised to the
workflow's run log, which the mail never quotes. A run that stopped while
reading the night's inputs (`universe`, `fetch` or `session`) is mailed the
missing-inputs sentence for that failure; a stop after them says those stages
had passed and claims no cause, since a later failure can be the code's or the
data's. Problems the night recorded before it stopped go out as recorded, an
earlier missing input among them.
Preflight checks every variable the run reads, for presence and for a value
the code understands, before anything is fetched or paid for.
A degraded night names its problem with one of seven words —
`universe_cached`, `coverage_thin`, `claude_unavailable`, `claude_partial`,
`chart_missing`, `email_failed`, `push_retried` — and the page has one fixed
sentence for each; the message the run recorded never reaches it.

`intraday.yml` remains a manual legacy research artifact. Its old combined
price/volume fields do not establish entry validity. The workflow sends no
email, forwards no delivery credentials, writes `docs/live.json` and commits
nothing. Use the separate morning-observation path for dated quote checks.

### What is checked about events, and for whom

`knowledge/event-coverage.md` says it check by check. (1) A manual registry of
known cash acquisitions blocks a ticket; it is reviewed by hand, and a passed
review date never clears an entry. (2) For published tickets: an earnings
estimate from SEC results filings (a warning, never a refusal) and the 8-K item
codes of the last 14 days; and, as flags for a reader, the same estimate and
items, the merger, tender and deal filings and the signal-day bar read again
from the iex feed for up to 80 of the night's candidates, whatever the light
(see *Candidate checks* below). (3) For tickets and registry-blocked plans
only: up to three recent SEC current reports and the merger and tender forms
on file. (4) On the morning of a ticket, if a morning check runs: Nasdaq's
halt feed. Nothing reads company press releases, news wires, announced
earnings dates, offerings, FDA dates, index changes, lockups or dividends, and
on a night with no ticket and no registry-blocked plan (26 of the 48 sessions
published from 11 September to 17 November 2026, before the candidate checks)
checks 2 to 4 ran for no stock at all. Every candidate needs the outside
analyst's ten-item event check before a trade; "not established" is never
"clear".

### Earnings warnings

Each ticket the record publishes carries one earnings sentence
(`run.earnings`, `src/earnings_risk.py`, policy `warn_only`). No free source
lets a public page print a company's announced report date, so the evening run
estimates one from SEC EDGAR, whose filings are public: the dates a company
furnished its quarterly results (form 8-K, item 2.02). It reads SEC's ticker
mapping once and each ticket's filing list once, and the older file only when
the recent one does not reach back 416 days: at most one mapping and two
requests a ticket, within a 60-second deadline, through the issuer collector's
own transport and User-Agent. Most companies report in the same week each
year, so last year's results filing put 364 days later, within 7 days either
side, is the estimate, read against the ticket's own hold window (the five
sessions `plan.dated_schedule()` names). Each of this year's results filings
reports at most one of last year's, so a preliminary release does not stand
for the full results still to come. The verdicts: a results 8-K accepted by
the SEC after the signal session's close (an observed fact about the filing;
the release it furnishes may have come earlier, and the sentence says so);
estimated inside the hold; estimated near it (the estimate's range reaches a
day of the hold); overdue (the estimate's range ended before day 1 of the
hold, no more than 45 days before the signal, with no results filing since;
or no results filing has come for longer than any gap between the issuer's
own earlier ones), so a report could come any day; already reported this
quarter; estimated outside the hold; or unknown, with its reason (not in SEC's
ticker list or named there for two companies, no results filings, a foreign
issuer's forms, filings that do not reach back 416 days or an older file that
could not be read, SEC unavailable). Every estimate says it is one and not an
announced date; unknown never reads as clear; and the warning never withholds,
sizes or cuts a ticket: it is printed beside the ticket on the page, the
tickets sheet and in the mail. A record made before the block says no report
date was checked. `report.validate()` re-derives every read row from the
filings it retains, holds each SEC read between the signal session's close
and two hours after the record's own clock and to SEC's own addresses, and
refuses a block whose rows are not the record's tickets. The check is
SpicyStock's, not Bonde's (`knowledge/method.md`).

Version 2 of the block reads one more thing off the same filing list, at no
extra request: each row also keeps the ticket's recent SEC current reports
(form 8-K and its amendments) filed within 14 days before the signal session
or since it, through the day of the read, 8 retained -- those carrying a
material item first, then the newest -- with the window's count and the
material-item reports the bound did not retain beside them, and names the item
codes they carry, each under SEC's Form 8-K heading where the module's table
knows it and bare otherwise. A report carrying item 1.01 (a material
definitive agreement), 1.03 (bankruptcy or receivership), 2.01 (a completed
acquisition or disposition), 3.01 (a delisting notice) or 5.01 (a change in
control) is named with its form, its filing date, its acceptance time and
where that fell against the hold (a report SEC recorded no acceptance for is
placed by its filing date, and one dated the signal session itself says that
before or after its close is not established), because such a filing is the
first a cash acquisition, a delisting or a failure tends to make (SpicyStock's
reading of what the items are for, not a rule of SEC's); every other code is
listed by heading. An item names a kind of event and never what the filing
says, so the sentence says to read the filing before entry; it withholds
nothing (only the manual event registry does). What the words could hide is
said: a report filed after the hold's last close is counted and not read, a
material-item report past the bound is counted, an item token SEC wrote in
another shape is counted and not read, and a report whose every token was
such says that what it names is not established. A foreign issuer with no
8-K in the window says its 6-K reports carry no items; an unread row says the
reports were not checked; SEC filings are not news coverage. The sentence is
printed under the earnings sentence on the page, in the tickets sheet and in
the mail, and the block's own sentence counts the tickets by what their
reports carry. `report.validate()` re-derives every row's items from the
reports it retains and holds a record to the version its rules archived: a
record made under version 1 carries no current reports, is refused none, and
the page says the check predates it. A closed night carries the previous
publication's block only when it validates under the current rules, so the
first closed night after a version change reads SEC again for the carried
tickets rather than carry a shape its own rules do not write.

### Candidate checks

The tickets' own checks read the names the record publishes an order or a
listed setup for. The candidate checks (`candidate_checks`,
`src/candidate_checks.py`, policy `flag_only`) read the same three things for
up to 80 names a night, taken in this order and once each by stage and ticker:
every ticket, every listed setup, every burst the review selected, every burst
whose mechanical grade is in the archived trade band with no quality veto that
the discovery admission admits (each in the record's rank order), then the
also-quiet coils. A name past the bound is counted by role and gets no row.
Each row carries the name's recent merger, tender and deal filings (the SEC
flags' forms, items and window; the newest 4 kept, with the count beside
them), its earnings estimate and recent 8-K items (the earnings warning's own
rule, read against the hold window a next-session entry would have; the first
4 material items kept, with the count), and its signal-day bar read again from
the iex feed (the cross-check's own tolerances). A name a ticket's block
already read carries that block's reading, and the validator holds the two
equal.

The night has ONE SEC reader and ONE iex batch. The reader asks each SEC URL
once and keeps its answer, so the earnings warning, the SEC flags and the
candidate checks read the same filing list and each block counts only the
requests it made (an answer the reader already held is not one). The tickets
are read first; the reader begins no request past 150 seconds from its start
or past the issuer transport's 96 requests for the night, and a name past
either is unknown with its reason, never clear: 80 names cost one mapping and
one filing list each, plus an older file where one is needed. The iex batch is
one request for every distinct name, retried once as every bars request is; a
batch that failed twice reads `iex_unavailable` on every row, never
`no_iex_bar`, and the tickets' own cross-check reads the same batch.

It is a flag and nothing else: it is read once the plans and the allocation are
final, it changes no plan, ticket, funnel stage, cash budget or `orders.json`
field, a collection that fails or that its validator refuses becomes the
block with nothing read for it, and it never fails a night. The block is
bounded at 262144 bytes: past that, rows no ticket's block stands behind are
shed to not checked from the end. Its sentence carries counts and at most 3
names for each kind of flag; the page's Method view and the mail print it
verbatim, and the brief carries each candidate's row beside it. A closed night
carries the previous block while it still holds under tonight's record.
`report.validate()` re-derives the names from the record and holds every row
to its own fields under rules that archive the family; a record from before it
is asked for none.

### Morning observations

`morning.yml` collects a small, read-only `docs/morning.json` beside the
canonical evening publication. Each observation binds the exact publication
bytes, run, rules, applicable session, candidate stage and retained plan.
Only already-admitted tickets can request quotes; a withheld candidate cannot
become a ticket through this refresh. The evening record and its evidence are
unchanged.

The browser shows IEX as a single-venue observation, with bid/ask, spread and
provider timestamps kept separate from collection time. A latest trade is not
a current executable quote. Delayed SIP daily volume remains explicitly
delayed; its daily-bar timestamp is a session label, not a claim about when the
volume was complete. Invalid, crossed, stale, future-dated, missing and failed
observations stay visible as limitations. Quotes and latest trades expire after
60 seconds; the collection receipt expires after 300 seconds. A halt feed is
fresh for at most 180 seconds by its channel publication time. These limits
label measurement age, not permission to trade. Price comparisons use the retained
trigger, limit and stop and do not authorize an order. Check current prices,
spread and order terms at the broker.

For a burst ticket's row the *Against published levels* line also says what the
dated price means for its buy stop. A last trade or ask at or over the trigger
(within the published band, above the limit or above the day-2 line) reads "At
or over the trigger (…): Fidelity’s words say a buy stop must be entered above
the current market price, so this ticket’s stop-limit cannot be entered as
written while the stock trades there." One between the entry floor and the
trigger reads "Under the trigger (…): the stop-limit as written is on the right
side of the market while the stock trades there." The words are built from the
receipt's two recorded comparisons, add no field, and the line still ends "These
dated comparisons are not an entry or cancellation instruction." A setting-up
row carries neither.

Nasdaq's public halt RSS supplies named halt observations. A quote-resumption
time alone does not establish trade resumption; older unresolved halts remain
relevant. A missing symbol or unavailable feed is not a clearance. Issuer news
and earnings remain unchecked, and corporate-action coverage is the bounded
source-backed manual registry. Known event restrictions survive publication
updates and require dated, source-backed resolution evidence to clear. The page
states these coverage limits.

Two best-effort scheduled attempts target 8:20 and 8:28 a.m. Chicago, with
separate daylight/standard UTC slots and XNYS session checks. Delayed scheduled
jobs skip the wrong session and the expired entry window. GitHub Actions and
Pages can deliver late; this is a dated snapshot, not a sub-minute quote
service. The browser recomputes freshness as time passes. Its reload control
only re-reads the public snapshot; it does not call a market-data provider.

The prepared [single-host service](docs/operations/morning-service.md) provides
the separate server path: trusted publication synchronization, a supervised
private collection worker and read-only receipt serving. One durable local
SQLite database preserves source identity, event restrictions, fenced leases,
provider attempt limits and backoff across restarts. Public reads never start
collection. The synchronizer checks this repository's fixed main publication
and downloads its canonical bytes only when the Git blob changes; the worker
uses the existing production session, freshness and event rules.

A bounded [operational journal and read-only session report](docs/operations/morning-service-report.md)
retain source changes, collection outcomes and charged provider attempts across
restarts. Reports keep receipt generation separate from its local commit time,
disclose legacy/pruned history, and distinguish no-ticket mornings from quote
coverage. They measure stored worker observations; public HTTPS delivery and
actual trading outcomes require their own evidence.

The [deployment handoff](docs/operations/morning-deployment.md) describes
300-second synchronization and 30-second worker invocation targets, separate
HTTP serving and worker-only provider credentials. The actual worker has a
25-second collection-child deadline and no provider retries; source synchronization has
a separate 35-second supervisor. These are prepared implementation limits, not
measured live delivery.

The [Railway deployment runbook](docs/operations/morning-railway.md) uses the
root `Dockerfile` and pinned `requirements-host.txt` for a single continuously
running service. Its launcher requires the persistent `/srv/spicystock` mount,
supervises independent synchronization and worker timers, and serves the reader
with Gunicorn under a separate operating-system user. `MORNING_WORKER_ENABLED`
defaults to `false`; enabling it requires both existing Alpaca credentials.
`PORT` defaults to `8080`. The reader and synchronizer receive neither provider
credential. `/healthz` measures reader-process availability, not receipt freshness.
`/status.json` is the host's read-only account of what it did: the synchronizer's
last outcome and the refusal sentence behind it, the publication it last ingested,
a summary of the receipt it serves (and whether that receipt is for the current
publication), and the newest journal events with allowlisted fields; never a
receipt's or a publication's bytes, never a provider request or response. Each
scheduled command's one-line result is also printed in the host's own log line,
so a platform log says what a sync or worker tick did and not only that it exited
`1`. The image verifies every publication with the verifier it was built with,
so it must be redeployed after every merge that changes what the image copies
and the host reads: `src/`, `tools/sync_morning_service.py`,
`tools/publish_morning.py`, `knowledge/event-risk.json` (the collector's
corporate-event registry), `requirements.txt`, `requirements-host.txt` or the
`Dockerfile`. The 31 October 2026 image refused every record published from
4 November on ("publication integrity is not verified"), and nothing it served
said so. An image from before the status route still runs against a volume
this one has touched: the synchronizer's table keeps the seven columns the
first image wrote, and the refusal detail lives in a table of its own.
Host spending controls, the volume, the TLS route and the provider bindings were
configured on Railway on 31 October 2026 ([the Railway runbook](docs/operations/morning-railway.md)
records them); deploying the image establishes no live delivery until a session's
receipt has been read.

An optional deployment adapter reads one fixed public HTTPS `/morning.json`
endpoint from the committed `spicystock-morning-endpoint` meta tag in
`docs/index.html`. It names the Railway service,
`https://spicystock-production.up.railway.app/morning.json` (deployed and read
from outside on 31 October 2026; [the Railway runbook](docs/operations/morning-railway.md)
records what was read); empty, the site reads the same-origin static file and
does not poll; set, it reads the host and that static file and polls both. Every offline check serves a copy of the shell with the tag blanked
(`tools/offline_shell.mjs`), and `tools/morning_endpoint_live.mjs` reads the live
endpoint from the site's own origin, outside every gate; its output names which
file the shown receipt came from (`page.source`), since the page also reads the
checkout's static `docs/morning.json`. Only a reviewed deployment may set
that exact URL; query strings, fragments, credentials, other paths and malformed
configuration are refused. The host answers 200 with the receipt bound to the
publication it holds; 404 `{"publication_sha256":…,"status":"no_receipt"}`,
naming that publication, when it has ingested one and holds no verified check
for it (every evening from ingestion until the window's first cycle, and after a
same-session revision), which the page reads as *No morning check yet for this
record* when the digest is the loaded record's and as the host holding another
publication when it is not; and 503 for a store it cannot read or serve
(nothing ingested, a replay store, a tampered or unbound receipt), which the
page says could not be read. A 404 naming no publication (the static
file absent) reads as no file published. Each is the absence of a check, known
and said, never a quote or a clearance. Browser preferences, local reports, notes and ticker
selections never configure the destination or enter its request. The configured
server must allow the site's origin through CORS. Requests omit credentials and
referrers, refuse redirects, and retain the 15-second timeout and 512 KiB bound.

With that explicit opt-in, visible tabs automatically read at a 30-second
minimum interval only for a current production publication with admitted plans,
from 30 minutes before its recorded exchange open until its entry cutoff.
Hidden tabs, practice/replay records, missing timing, stale publications and
zero-ticket publications do not poll. The manual reload remains available.
An automatic read never overlaps another read; publication changes cancel old
work and recheck the exact source binding. An outage, malformed response or older
receipt preserves the last verified receipt and known event exclusions.
Beside the configured host the page reads the same-origin static `morning.json` the morning workflow commits, on every read;
each file is held to the loaded publication by the same validation,
the newest verified receipt is shown (the host's on a tie) and the summary
names which file it came from (*Receipt source:*); positive halt and event
facts are kept from both files, a receipt bound to another publication is never
shown, and when the newest verified file omits a restriction the tab read from
a file bound to this record, the read is refused and the restriction stays. A
restriction the tab read only from a file bound to another publication (a host
still serving an older receipt) keeps that ticker's entry copying withheld and
is named (*Kept from another publication:*), but no longer refuses this
record's own verified receipt for every other ticker. A failed read is said in
plain words (no answer within the time allowed, an answer that was not JSON or
not UTF-8 text, a file that could not be reached), never in the browser's own
wording. One 15-second limit covers both
reads, so a host that never answers holds a bound static receipt back until
that limit. Reads cannot trigger provider work.
This disabled-by-default adapter establishes no hosting, scheduler, source
coverage or live-session delivery reliability; those remain deployment and
operating acceptance requirements.

Locally deferred collections name why no request was made: `local_interval`
(the feed was polled less than its minimum spacing ago, so the cycle skipped
it and the previous reading stands), `local_budget` (the feed's requests for
the day are spent) or `local_backoff` (backoff after an earlier provider
failure). The service's worker runs a cycle every 30 seconds and reserves a
feed when its request leaves, so each feed's spacing floor (20 seconds for
the IEX and delayed-SIP snapshots, 60 for the halts feed, which is served
from cache between polls) sits below the cycle: an ordinary cycle is never
skipped for spacing. Each feed is bounded to 120 requests a day. They
explicitly say no provider request was made in that collection, keep quote
fields unavailable, and cannot claim a new provider HTTP result or entitlement
observation. Unsupported or
contradictory source failure kinds are refused by the browser receipt validator.
Unavailable feeds must carry empty unavailable price/volume fields and unknown
comparisons; contradictory copied prices or volume are refused as well.

Manual dispatch defaults to a rehearsal artifact. An optional rehearsal-only
source diagnostic requests the fixed SPY symbol through the same feed adapter
and normalizers, even when there are no admitted tickets. Its separate artifact
contains no plan or publication authority and cannot be written into `docs/`.
Production persistence is
restricted to main and rechecks the current canonical record and any newer
observation before a one-file, ordinary fast-forward push. The existing
publisher then verifies the committed public files. Collection receives only
the Alpaca data credentials; it never requests trading, chart-reader or email
credentials, and no provider secret reaches the browser. No new subscription
or environment variable is required. Timely morning delivery and comprehensive
event coverage remain acceptance work for milestone 2.

GitHub's scheduler has started every scheduled run of this repository hours
late since the evening of 21 September (the [13 October schedule reading](docs/input-truthfulness/2026-10-13-schedule-reliability.md)),
and each morning run from 12 to 16 October was created after its entry window
had ended, so the Morning desk offers the owner a hand-started check, the
reading's recommended first step. The summary offers it only where the
collector would take it and it would quote something: on the applicable
session, from the collector's own pre-open minutes (`src/morning.py`'s
`POLICY`, 30) until two minutes before the entry cutoff, because the run reads
its clock after checkout and install (28.8 and 31.7 seconds after two dispatched
runs were created); only after the morning file was read and shown to hold no
current check for this publication (a 404, a receipt bound to another
publication, an inapplicable one, or one past its five-minute life), never
while it is unread or unverifiable; and only when the publication admits a
plan or the opened research comparison names allocation-fit rows. Under a
configured morning host the offer is made only when that host's answer shows it does not hold the loaded publication
(it served a receipt for another publication, or a 404 naming another
publication or none); a host that holds the record checks it itself, and a host
whose answer could not be read leaves that unknown, so nothing is offered. A no-ticket
receipt stays final, and a publication with nothing to quote says so instead.
Earlier that day it names when the window opens. The link goes to `morning.yml`
on GitHub with the steps (main, **dry_run** unticked) and says what a run does:
it publishes a dated morning receipt and a research receipt, starts the SEC
evidence collection that follows every morning run (at most three a UTC day,
the evening's included) and places no order. The page dispatches nothing,
holds no token and sends nothing to any GitHub host; starting the run needs
write access to the repository. Two earlier manual dispatches went from the
run's creation to its committed morning receipt in 64 and 75 seconds; for the
10 October one the Pages deployment finished 55 seconds after the run did, and
publisher 38039664633 verified the served file 130 seconds after the run was
created. Neither asked a market-data provider anything (one on a Saturday, one
after the cutoff); the 10 October run's SEC collection made one request. So
the offer says to press **Reload published observations** a minute or two
after the run finishes. That button re-reads the morning host's receipt and
the static morning file and, once the
research comparison has been opened, its dated research observation; the
comparison's own reload re-reads that observation even when its cohort is
unchanged. A press keeps what was verified until a newer file validates, and
a failed read names itself beside the kept observation.

### SEC issuer evidence

The Morning desk includes an optional filing reader for current admitted plans
and candidates withheld by known corporate events. Opening it loads a small
publication-bound receipt and one verified source bundle. It shows the issuer,
SEC identity, filing and acceptance dates, retrieval time, primary links and
short text excerpts. Private cash, notes and selected symbols are never sent
to a source service. The closed reader makes no additional browser requests.

The collector verifies ticker/CIK identity and lists current-report metadata
from a trailing 365-day window. It selects up to eight issuers, prioritizing
admitted plans, then retrieves at most three recent 8-K/6-K reports per issuer
and two same-accession exhibits per report. One bounded history file may extend
the metadata window. Missing history, omitted issuers, unfetched reports and
truncated excerpts are explicit; a recent-document sample does not establish
complete news coverage. Domestic 8-K and foreign 6-K reports retain their own
dates and document types. An acquisition mentioned by an issuer does not, by
itself, establish that the issuer is a takeover target.

Acquisition-related metadata forms (PREM14A, DEFM14A, SC TO-T and SC 14D9,
each with its `/A` amendment) produce a separate review warning from the same
bounded submissions/history reads, with no additional request. Every new
bundle carries the block (`acquisition_review`, version 2) for every issuer,
so the reader tells four states apart and never guesses: observed, with up to
twelve dated links newest first, the observed and omitted counts, and for
each listed filing the retained SEC index the collector read it from (the
submissions file or the one fetched history file) with its retrieval time,
which the validator holds to one of the row's own retained sources (which
file carried a filing is the collector's own record, replayed against its
captured index bytes only by the tests over the producer fixtures);
none, when a verified index showed no such form, which is said, not left out
(a complete window that held no filing of any form says so, rather than
counting forms among zero rows); unknown, when the issuer's identity or
submissions could not be verified, or when a verified index yielded no
readable metadata row under partial coverage, so nothing was checked; and not
recorded, for a bundle from before the warning existed. A version-1 block
(bare filings, written only when a form was observed) stays readable under the
current form list and its own count, window and order rules. The browser reads JSON numbers, so it cannot tell `2.0`
from `2` where the publisher's validator requires a typed integer; that
validator runs before every publication, so the typed contract is held where
the bytes are written, and the browser holds every other rule of the block. These form names do not establish whether an
acquisition is pending or completed, its terms, or that the issuer is the
target. Their document content remains unreviewed; the latest-three
current-report excerpts do not cover these forms. Neither an empty list nor
an absent block, including in older bundles, is event clearance; a partial
index says so beside its list. This metadata warning does not modify
published tickets, sizing or known-event exclusions.

Each listed filing's SEC item codes are printed under the Form 8-K headings
the evening's earnings block uses (`earnings_risk.ITEM_TITLES`), the five
material kinds (1.01, 1.03, 2.01, 3.01, 5.01) first and marked, and one line
above the list counts the listed current reports that carry one and names the
filing each sits in. The evening's earnings warning names a material item only
when it is filed in the 14 days before a published ticket's signal session or
since; the desk marks every listed filing whatever its date, and says so. The
string is read as the evening reads it: each `N.NN` once, a token SEC wrote in
another shape counted and never read as a code (and a material item among
such tokens never excluded), a code the heading table lacks printed bare, an
empty string said to record none. Codes are read on an 8-K or 8-K/A only; a
6-K's string is not read. `tests/fixtures/issuer-evidence/items-parity.json`
carries `earnings_risk._parse_items`'s own answer for 231 item strings, and the
browser suite holds the page's parser to every one. An item names a kind of
event, never what the filing says; the line is not event clearance, it reads
the listed reports only (never the rows the twelve-report bound left out), and
it changes no ticket, exclusion or order.

Known unresolved events remain separate, source-backed anchors. The collector
does not classify new events or clear an existing exclusion. In the 10 October
2026 source audit, the original ZIM merger report was seventeenth newest among
33 trailing-year current reports, illustrating why a recent-filings panel
cannot replace those anchors.
Future earnings and comprehensive issuer news still require verification.
This reader does not change a ticket, copied quantity or cash preview.

Every request names the project and a contact email in its User-Agent
(`issuer_evidence.USER_AGENT`), as SEC's fair-access policy asks. Until
17 October 2026 it named only the project's URL, and the ticker mapping
answered HTTP 403 on all five collections from 10 to 16 October that
recorded a status.

A night with no admitted plan and no known-event exclusion has no candidate,
so the collector asks SEC nothing, and a red week can pass without showing
whether SEC answers the named contact. A manual dispatch of
`issuer-evidence.yml` with **dry_run** and **probe_sec** ticked runs
`tools/probe_sec_access.py` instead of a collection: one request for the
ticker mapping and one for each issuer's submissions (AAPL, a domestic filer;
ZIM, a foreign private issuer), or for up to four other tickers named in
**probe_tickers**, spelled as SEC's mapping spells them (a class share with a
hyphen, BRK-B, which the collector matches exactly), passed through the
environment and refused whole, before any request, if any is not such a
ticker -- through the collector's own transport --
its User-Agent, spacing, deadline, refused redirects and size bounds, and no
cache, so a cached mapping cannot answer for today. It prints its result to the
job log and keeps it as a 14-day artifact: each request's outcome, HTTP status,
bytes and digest, whether each issuer's identity was established, and whether
the User-Agent names a sender and a contact (never the address). For each
issuer it also names the rows of SEC's recent index the collector's row rules
refuse (a refused row makes a collection `partial` on `metadata_invalid`):
every one counted by rule and by form (an unnamed copy of an accession listed
differently under `unnamed_twin`), and the first 24 with the refused field's
value and the row's filing date, each spelled only in the characters such a
field carries. It binds no
publication, collects no candidate, writes nothing under `docs/` and is never
persisted. Its first run, from a runner on 18 October 2026 (run 39095391329),
got both answers -- the mapping (523,925 bytes) and AAPL's submissions
(163,690 bytes), the identity established -- so the refusal recorded through
16 October is not what SEC gives the named contact. The first collection with
a candidate, for ZIM on 24 October, was answered too: its identity was
verified and its index read, `partial` on `metadata_invalid`. The probe named
why (run 40163306777, 25 October): every refused row -- 78 of ZIM's, 674 of
AAPL's -- failed the document rule, and the forms were XML filings SEC lists
under the directory of the XSL stylesheet that renders each
(`xslF345X06/form4.xml`, `xsl144X01/primary_doc.xml`): Forms 3 and 4 and
their amendments, Form 5, Form 144 and its amendment, 25-NSE, EFFECT notices,
and Schedules 13D and 13G and their amendments.
The row rule reads such a row now for a form the collector never stores or
fetches (`issuer_evidence._rendered()`); a current report or acquisition form
must still name one plain document. On the fixed branch (run 40164017459) the
probe refused no row of either, over the same index bytes the first run read:
both job logs print AAPL's submissions as SHA-256 `5891cf87…` (163,917 bytes)
and ZIM's as `7d822c20…` (39,210 bytes). The first
production collections under it (27 to 30 October) read ZIM, EXEL, OGN and
PSNL `observed_window`; MCS (29 October) and QGEN (30 October) still read
`partial` on `metadata_invalid`. The probe (run 41149821846, 31 October)
named the refused rows in the indexes SEC served then: one of MCS's and six of
QGEN's failed the document rule, every one a Schedule 13G or 13G/A, and each
named no document at all or a name with a doubled dot (`marcus.corp..txt`,
`qiagen.n.v..txt`, `qiagen.nv.reg.shs..txt`). QGEN's index was byte for byte
the one its 30 October collection read (`98c75f54…`); MCS's had changed since
29 October (`54e41963…` then, `e3505edc…` on the probe), so for MCS the cause
is inferred, not observed. The row rule counts such a row now for a form the
collector never stores or fetches (`issuer_evidence._unnamed()`), held to every
other row rule with its document never read, listed, linked or fetched; a
current report or acquisition form must still name one plain document, and a
document with a directory (other than the XSL rendering path above), a leading
dot or any other character is still refused. Where SEC lists one accession
more than once and the copies differ, an unnamed copy is refused wherever it is
read -- in the recent index or its history file -- and the named copy kept; two
differing unnamed copies are both refused, and so is an unnamed copy beside a
copy in its own file that the row rules refuse. A refused copy counts as one
invalid row of its file, and its date is not in the range; it never refuses an
index or drops a history file. A history file refused for two differing named
copies is not read at all, so its copies refuse nothing. Two
differing copies that both name a usable document still refuse the recent
index when both are in it, and the history file when one is in each and both
fall in the window, as before. An index whose range reaches the window and is
partial only on
`metadata_invalid` says so: `issuer_evidence.REFUSED_ROWS_REASON`, not the
missing-history sentence. A branch probe of the change (run 41158793431)
parsed both indexes with no row refused and the same rows in the window (96
and 24), so every row refused before was older than the window. Whether MCS
and QGEN read `observed_window` is for the next collection with them as
candidates to show; it changes an index's coverage, not an issuer's status,
and both left current reports unselected (4 and 9) when last collected.

The same dispatch with **capture_url** set fetches one SEC Archives document
instead of the probe (`tools/capture_sec_document.py`), for a review of the
event registry: a registry entry ends only with a resolution that carries the
SHA-256 of captured bytes, and a review made from a network that cannot reach
sec.gov has none to give. It asks once, through the collector's own
transport, and prints the URL, the outcome, the byte count, the SHA-256 and,
for each of up to 6 phrases in **capture_find** (separated by `|`), how many
times the document's own text carries it with at most 3 excerpts of 240
characters either side. The exact bytes are kept as a 30-day artifact beside
the result. It refuses any URL that is not a filing document the collector's
transport fetches, before any request; it decides nothing, resolves nothing,
writes nothing under `docs/` and is never persisted. The registry edit that
cites it is a reviewed change of its own, with a dated manifest.

`issuer-evidence.yml` follows an actual committed evening or morning publication;
the guard identifies the parent by its exact workflow file path, then checks
its repository, main branch and current publication binding. Dynamic run titles
are display text. It adds no polling schedule. Production collection is capped
at three starts
per UTC day, including failed attempts and reruns, with a serialized guard that
refuses incomplete Actions history. Manual dispatch defaults to a rehearsal.
The SEC-only client uses the public project identity, no provider credential,
and at most one request per second, 96 requests, 2 MiB per response, 32 MiB of
downloads and four minutes per collection. Retained raw captures, including
reused cache bodies, have a separate 32 MiB cap. Cached source bodies retain their
last network-check time. Mapping cache lifetime is seven days and document
cache lifetime is 24 hours; submissions are requested on each collection.
The cache is bounded to 256 entries and 128 MiB.

When an HTTP response refuses a request, the reader shows its observed status
and source stage (mapping, submissions, history, primary report or exhibit).
Older receipts and failures without an HTTP response leave the status unknown.
Diagnostics retain the original requested SEC URL, never a redirect destination,
response body, headers or exception text. Redirects remain refused; refused
responses are closed without reading their bodies. A status explains a failed
source request and does not establish news or earnings coverage.

Coverage labels must reconcile with the retained evidence. Unverified identity
cannot claim an observed index or collected issuer. A complete index can coexist
with a later filing-document failure; that issuer remains partial. Collected
rows require every selected primary and no recorded omissions or truncation.
Request and byte totals must cover the distinct visible source events and
explicit HTTP failures, while preserving valid cached and legacy observations.
These checks establish internal consistency, not comprehensive source truth.

The receipt expires 24 hours after collection; individual source ages remain
visible, and this period is not news clearance. Up to 16 KiB of normalized
text is retained per excerpt, with a separate excerpt digest and original-body
digest. Raw captures are kept in a 30-day Actions artifact, rather than claimed
as a permanent complete archive. The public receipt is limited to 64 KiB and
its digest-addressed bundle to 2 MiB. A main-only publisher revalidates the
source publication, previous receipt and current branch before committing.
It retains superseded bundles for at least 21 days and protects the current
bundle; its owned store is bounded to 256 objects and 256 MiB.
Previously published receipts remain readable as dated evidence but cannot
attach to a different scan. An issuer-source failure does not prevent the
evening record from publishing. See the
[versioned source contract](docs/ISSUER_EVIDENCE_SCHEMA.md) for exact fields.

### Registered anticipation stop-width research

The Morning desk has a closed **Wider-stop anticipation research** disclosure.
It compares the unchanged 4% production stop-width cap with a separate 5%
anticipation calculation for applicable sessions **October 12 through November
6, 2026**. The versioned experiment is `anticipation_stop_width_4_to_5_v1`.
It changes no production ticket, reaction/burst stop selection or model record.
There is no research order-copy or broker-draft action.
An **Inspect recorded chart** action opens the same publication's existing
anticipation chart and baseline decision. It checks the publication and retained
evidence identity again when pressed, including after a same-ticker refresh.
Missing or changed identity leaves an explanation in the research panel.
Inspection preserves private preparation and adds no current quote or order.

The producer uses the actual retained planning inputs and the same pure planner,
changing only the anticipation cap. Original trigger, limit and structural stop
must match; the 4% calculation must reproduce original geometry, sizing and
multipliers before a comparison is accepted. The comparison's reference is the
$2,000, 0.5% base risk, 25% per-name cap and four slots it was registered at
(`stop_research.ACCOUNT`, archived in its policy): inside the registered period
a publication sized at another account is refused by name and the previous
receipt kept, so a changed account is never read as the registered experiment;
outside the period no row is computed, the publication's baseline is reconciled
under its own archived account and the receipt's reservations state that
account, so the outside-period receipt is still written for each later
publication (the owner's account moved to $30,000 from the 4 November 2026
session, two sessions before the registration ends, so the comparison's last two
sessions are refused and its last recorded receipt is the 3 November
publication's). Existing market, watchlist,
known-event, whole-share and shared-allocation rules still apply. A stop beyond
the ideal distance still halves the risk budget; widening the cap does not
increase the configured dollar-risk budget.

All original top anticipation rows are retained, including excluded names,
zero-share results and out-of-band rows. Current baseline tickets and unfinished
model positions reserve their cash and slots first; research cannot displace a
baseline trade. The panel shows the original refusal, fixed levels, hypothetical
quantity, principal, price-to-stop risk, risk multipliers and each remaining
blocker. These amounts exclude actual fees, gaps and slippage. Model reserves
are not broker holdings or available settled cash. A manual event-registry
match is an exclusion; no match is not news or earnings clearance. There is no
new chart review, quote, provider request or inferred trading outcome.

The comparison is bound to the exact canonical publication, compact reader,
archived rules, plans and retained sources. Its actual generation timestamp is
separate from the source publication's run-start timestamp. Collection before,
during or after entry is labelled accordingly; a late backfill cannot claim to
be pre-entry research. The reader labels an elapsed entry window as archived.
Empty/refused cohorts and outside-period status remain visible evidence.

The evening hook runs after final canonical/reader bytes, including delivery
failure restamps. Unsupported account/rules, invalid retained sources or a
research-write refusal leave the authoritative publication unchanged. An older
receipt can remain, but cannot attach to a different current publication.
There is no research environment variable, provider credential or subscription.

Opening the disclosure fetches only the optional `stop-research.json` receipt
(at most 16 KiB) and its exact digest-named bundle (at most 128 KiB), with a
15-second deadline and the existing omitted-credential/no-redirect transport.
Its immutable cohorts and append-only index retain at most 128 cohorts / 16 MiB;
the index is capped at 64 KiB. Capacity exhaustion refuses a new write without
pruning past cohorts. Repeating an exact publication preserves its first
cohort and generation time. These repository/Pages paths are public; they contain
no private reports. The publisher verifies the current referenced bundle;
retained cohorts are not initial page requests. See
[the registered schema](docs/STOP_RESEARCH_SCHEMA.md) for the exact contract.

This is a dated strategy experiment, not evidence of an established edge.
User-reported trades/results remain separate. Promotion or performance claims
require a later explicit strategy review using the retained comparison and
subsequent observations.

### Dated research observations

`morning.yml` also collects a small, read-only `docs/research-observations.json`
for the current registered cohort's allocation-fit rows (`src/research_observations.py`).
It binds the exact canonical publication, the exact `stop-research.json` receipt
and bundle beside it, and each row's original evidence identity, then makes at
most one HTTP attempt to the fixed IEX snapshot endpoint per run, using the
existing server-side Alpaca pair. This research-only transport does not follow
redirects, retry failed requests or paginate. It limits the response body to
256 KiB, connection time to 5 seconds and read inactivity to 30 seconds, within
the 180-second collection deadline. The existing morning guards apply: a wrong
session, an ended or not-yet-open collection window, a
stale or future publication, a missing cohort or a cohort bound to another
publication is an inapplicable receipt with zero provider requests, and a
cohort with no allocation fit is recorded as one. Quotes and prints keep their
provider timestamps and the 60-second freshness rule, including microseconds;
the receipt expires after
300 seconds. Delayed volume is not requested, and halts, issuer news and earnings
are not checked by this companion, which says so beside every row.

The research panel prints the dated bid and ask with sizes, the spread, the last
print, and where each sits against the published trigger, limit and stop, as a
position and never a signal: no ready label, no quantity, no personal sizing,
no order copy and no entry permission. Research rows remain hypothetical model
research, not tickets. An observation collected over another cohort, an older
publication, a forged level, price state, spread or request count is refused in the
browser, and the cohort stays readable without it. Persistence is a second
one-file commit on main (`publish_morning.py --target research`), revalidated
against the record and the committed cohort; a cohort main has since replaced
refuses the push. No new subscription, credential or environment variable is
involved. Local tests do not establish scheduled delivery: a delayed Actions
run can finish successfully after its guard skips every collection step. Check
the dated receipt and collection steps; the workflow conclusion alone does not
establish a morning observation. Actions timing remains best effort.

The production collector installs its wall-clock deadline on the main thread
of the existing Linux Actions runner. A live collection refuses when that
timer is unavailable, preserving the previous receipt; offline injected clients
remain available for deterministic tests. The page prints the recorded request
count, including zero when provider credentials are missing.

### Same-session source recovery

Its own workflow, `source-recovery.yml`, asks the provider once more for the
stocks the night's own record says it could not read (`src/source_recovery.py`,
writing `docs/source-recovery.json`), at 07:37 and 09:37 UTC every day: after
the hour the 9 October late bars had arrived by (07:12 UTC), and hours before
either open. No other collector's guard or publish step decides whether it runs
or whether its receipt is kept. The schedule is best effort -- GitHub started
the 12 October morning crons 8 h 24 m late -- and a slot that starts after the
next open records `recovery_window_ended` and asks nothing; a manual dispatch is
a real collection, recorded like a scheduled one. The receipt binds the exact canonical publication
and its compact reader and freezes the record's own basis -- universe identity,
feed, split adjustment, lookback, measured session and rules digest; a record
whose basis differs is `basis_differs`, and nothing is fetched. The names come
from the record first (`run.input_tolerance.names`, the stale frames the
tolerance named in full) and from the publication's quality-ledger entry second
(its complete exception membership for `stale`, `no_bars`, `dropped`,
`unfetched_budget`, `unfetched_failure`, `gapped` and `unreadable`, each held to
the publication's own count and identity for its category), and never from a
guess: when no counted stock is named anywhere the receipt is
`deficit_not_named`, a count that is the benchmark's frame alone is
`benchmark_only`, and the request stays unspent either way; when only some are
named, the named ones are asked for and the rest are counted as named nowhere.
At most `MAX_NAMES` (100, one provider batch) are asked for in `MAX_BATCHES` (1)
request of at most `MAX_BATCH_ATTEMPTS` (2) attempts, through the same Alpaca
pair the morning collector reads, within `MAX_COLLECTION_SECONDS` (300) and only
before the next session opens (`recovery_until: next_session_open`). The provider
call runs under a main-thread timer set to the earlier of
`FETCH_RESERVE_SECONDS` (10) short of that bound and the next open, because the
SDK retries a 429 or 504 on its own; a call the timer stops is kept as
`provider_unavailable` with error kind `timeout` and its attempts counted, so a
request that was sent still binds the next slot, an answer that lands after the
open is not kept, a bound that expires before any call is sent says the stocks
were not asked for and spends nothing, and where the timer cannot be installed
nothing is asked. The receipt counts calls to the
bars endpoint; a retry the SDK makes inside one call, and a page it follows,
are not counted (`sdk_retries_and_pages_not_counted`). More named
deficits than the budget is `deficit_over_budget` whole, never a prefix, and a
publication whose one request was already spent is `already_attempted`. The
benchmark is never requested. Each row says what came back for its stock --
`recovered` (a bar for the measured session that passes the session rules),
`arrived_not_ready` (a bar that is gapped or unreadable), `still_stale` (an
ending that did not move), `still_missing` or `not_returned` -- with the bar's
volume and whether it was the provider's flat placeholder. The original
publication's coverage facts are copied beside the recovered count and never
combined into one figure: the record stays exactly as published, with its
measurements, grades, plans and tickets, and the receipt establishes neither
why a bar was absent nor when it arrived at the provider. Persistence is a
one-file commit on main (`publish_morning.py --target recovery`), revalidated
against the record, the ledger entry on main and the prior receipt; a spent
receipt is never replaced, and a later inapplicable receipt for the same
publication and the same reason is refused as unchanged, so the daily schedule
commits at most one receipt per publication and reason. A prior receipt of
another publication, of any schema or size, binds nothing beyond its bytes'
hash. The dashboard publisher runs after the workflow completes. The Method view
prints the receipt's one sentence after hashing the loaded publication's bytes
against the receipt's binding -- the canonical digest and, on a compact-reader
load, the reader's -- and nothing else on the page reads it. It reads the
receipt past the HTTP cache, says that no receipt was published only on a 404
(any other failure says the receipt could not be read), and reads it again when
an update check finds the record unchanged while Method is shown, because the
receipt lands the morning after the record it binds.

### Research follow-through

The Morning desk's optional **Research follow-through** view follows every frozen
wider-stop cohort using observations already retained by normal publications.
It makes no new provider or model requests. The first before-entry cohort for
an applicable session is identified as primary; later revisions and late
captures remain visible. Original exclusions, quantities and levels stay frozen.
Each verified original row can open a blank private actual-fill report. Its
explicitly entered broker facts stay separate from these conditional model
outcomes; the journal adds no order or personal entry-draft action.

The companion reports pending, missing, uncertain, not-filled, open or resolved
conditional daily-bar models, plus explicit unsupported-source states. Before
an entry session has a completed observation publication, it remains pending.
The initial October 10 snapshot has October 9 bars and remains pending for
the October 12 entry session; no outcome or R is invented. Missing sessions do not become zero
returns. A daily high/low crossing cannot establish the first thirty minutes
or intraday event order. Only a reconciled resolved model has an R result;
actual fees and slippage remain unspecified. This is not personal execution,
a portfolio return or a win rate. Research positions are not reserved across
separate cohorts as a hypothetical portfolio.

Each evaluated clip identifies its containing observation publication, dates,
bar digest and provider/feed/adjustment/daily-timeframe basis. The original
source anchor and supported fill/follow/R rules must agree. Anchor comparisons
use the pipeline's explicit four-decimal public price format while retaining
the raw source anchor and hash. Unknown or conflicting carried bases remain
unavailable. A prior conclusive clip may remain readable with its original date
when newer coverage is partial; genuinely conflicting new evidence is flagged.
Full OHLCV revisions produce new snapshots, retaining the prior snapshot.

The evening hook runs after final canonical/reader writes and the optional
stop comparison. Its failure preserves the authoritative record and previous
companion. Opening the disclosure fetches the fixed `research-outcomes.json`
receipt (16 KiB maximum) and its exact digest-named bundle (2 MiB maximum),
with a 15-second deadline and no private browser inputs. The original frozen
cohort bytes are embedded, so the browser requests no extra ticker histories.
A differently bound receipt cannot attach to the current observation publication.

The producer accepts at most 128 cohorts / 640 original rows, 16 MiB of cohort
inputs and 128 MiB of sequential original-publication reads within a 60-second
processing deadline. Its append-only store retains up to 128 snapshots / 64 MiB
and a 64 KiB index. Repeating the same publication/cohort set preserves the first
snapshot and generation time. Invalid archives or exhausted bounds refuse a
write without pruning earlier results. These repository/Pages archives are
public and contain no private reports. The publisher verifies the current
receipt and referenced bundle. See the [versioned contract](docs/RESEARCH_OUTCOMES_SCHEMA.md)
for source limits, replay semantics and exact fields.


### Reader payload and saved research

The page initially loads `reader.json`, a compact projection of the complete
canonical `data.json`. Candidate evidence, plans, account assumptions, timing
and embedded charts remain available immediately. The larger retained
observation history loads as one shared, digest-addressed file when saved
research needs it. A morning visit does not download that history or the full
canonical publication. Direct canonical records and old saved originals remain
readable.

The October 9 production record projects from 14,918,679 to 5,606,909 decoded
bytes, including its envelope. The deferred observation file is 5,040,916 bytes.
These are artifact sizes, not measured network transfer or a mobile-device
speed guarantee. Complete hydration reproduces the original parsed publication;
the projection changes no canonical record, picks or historical evidence.

From 24 October 2026 the canonical `data.json` is written compact -- no
indentation or spaces, key order and UTF-8 kept -- so the 23 October record
would be 9,992,325 bytes instead of 14,124,268. Earlier canonical records are
indented, the 14,918,679 above among them; the reader and observation files
were compact already. The record is bounded at 48 MiB
(`reader.MAX_PUBLICATION_BYTES`; every reader that bounds the record as a
publication holds this one number -- the evidence archive's retention scan reads
it whole under its own larger 64 MiB -- and the browser holds it only as the size
`reader.json` may name, since the page never downloads the record): the run log
states each night's record against it, with its bursts and observation bytes,
and warns past 80%; a record over it refuses the night before anything is
installed (exit 1), and the run log and the run's failure name the size and the
bound. `reader.json`, the file the browser does download, has its own bound of
32 MiB (`reader.MAX_READER_BYTES`), as its observation sidecar has: the run log
states each projection against it in a line of its own (*Reader projection:*) and
the sidecar against its bound in another (*Reader observations:*), warns past
80% of either, and a file over its bound refuses the night the same way, the
failure naming that file's size and bound. Both lines are written only for a
record within its own bound, since the projection is made from it after that
bound is asked; when both files are over theirs, the sidecar's is the bound
named. Until 25 October 2026 one 32 MiB
number bounded the record and the projection. The record's was raised because
the record carries the observation window, which its projection defers: built
from the 22 October record, every stock that night measured as scan-ready
(3,581) bursting, each with the observation window's whole history and the
window's signals at that record's own density (1.237 signal identities for
each stock and session that carried one, given to every stock and session of
the window), makes a record of 46,640,227 bytes, past the old bound, and a
projection of 27,351,450. That design point is one chosen night, not the largest
that population can make (a stock and session of that record carries up to four
signal identities). `tests/test_publication_ceiling.py` holds it inside every
bound once it adds the growth the current code writes to an unreviewed,
unplanned burst, a funnel row, each observation entry, the rules and the
ledger's candidate, and to the rest of the record and of its ledger entry as if
that came once a burst; what the code adds to the reviewed and planned bursts
alone, at most twelve a night, is not carried. Grown further from the same
record, the test computing it from the bytes each further burst appends: while
every bursting stock keeps a full window the record's own bound is reached
first, at 3,864 bursts; with 22 October's observation window held, the
projection's is, at 4,403 (the record's at 5,837). The quality ledger's 8 MiB
entry is reached at 4,465 either way (6,732,678 bytes at the design point, with
no scorecard rows or exception membership; a night's entry adds its own). 48 MiB is
under the 50 MiB above which, by GitHub's documentation (read as search
excerpts), a push is warned. The failure notice mailed when the record, the
projection or the sidecar refuses a night names the `publish` stage, not the
size. A ledger entry past its bound refuses only that night's capture: the exit
and the status are unchanged, no notice is mailed, and the run log's
`quality_ledger_capture_failed` line names the sizes. The restamp after delivery
writes the record and its companions once more, a few bytes longer for the
mail's word or its problem, and states the record against its bound and, when
the record is within it, each companion against its own, each in its own line;
should that write alone cross one, the record
first installed stays, is retained in the recovery catalog and the quality
ledger, and the run fails after publication (exit 3) under the stage `restamp`.

New morning receipts derive both canonical and reader hashes from the exact
canonical source bytes. The browser verifies the actual reader bytes before
matching observations. An older receipt can still preserve independently
validated event restrictions, but cannot claim a reader-bound quote check.
Initial loads, refreshes and deferred research preserve the actual response
bytes within the 32 MiB limit. Digests use those bytes directly; malformed UTF-8
and BOM-prefixed JSON are refused instead of being silently normalized. Startup
and refresh share a 15-second header-and-body deadline and cancel superseded
attempts. A failed refresh keeps the displayed publication and private inputs;
failed startup clears partial publication state and offers an explicit retry.
Saved private reports stay available without a publication.
Missing, loading or failed deferred research stays explicitly incomplete.
Saved bars merge only after the sidecar's digest, length, shape and metadata
validate; a stale response cannot overwrite a newer publication. Retry is
available after a fetch failure.

Sidecar requests use only a shared public digest path and send no private saved
symbols, notes or positions. Reads omit credentials and referrers, refuse
redirects and enforce size/time bounds. The publication installs verified
immutable sidecars before replacing fixed records and rolls fixed files back
on installation failure. It refreshes companions after final publication
restamping as well as the initial write. Owned derived transport files have a
21-calendar-day retention window measured against advancing publication-session
dates, with the prior current object's session refreshed when it is superseded.
The currently served file is always retained. This is not a guarantee of 21
elapsed days after a late publication. The archive is capped at 84 objects and
128 MiB. When a new object would pass the cap, owned objects still inside their
window give way, oldest last-served session first: an old tab's deferred
research then reads as unavailable, which it already handles, rather than the
whole evening going unpublished. The object served now and the one it replaces
never give way, an unknown file never does, and an owned file whose bytes are
not the object its manifest names refuses the publication rather than being
removed. Removals wait until the fixed files are installed, so a rollback keeps
them, unless the archive's working set is already past its bound (one object over
the count cap, 32 MiB over the byte cap), from a cleanup that failed on an
earlier night or a file the archive does not own: then the planned removals go
first, a rollback keeps only what had not gone yet, and a cleanup failing again
refuses the publication. A rollback also removes the object it brought in. An
owned entry whose file is already gone is retired from the manifest before
anything is planned. The run log states the archive's objects and bytes against
both caps, warns past 80% of either, and says when objects inside their window
were removed, or could not be, and when the manifest update failed.
Canonical history and evidence are outside this cleanup. The committed-main publisher verifies the reader and
its referenced sidecar before declaring the site updated.

`python -m src.reader --docs docs --check` verifies committed companions without
repairing them. Omitting `--check` derives companions from the existing canonical
bytes; it makes no provider request and does not rewrite the canonical record.

The combined morning/reader release shipped in [PR #114](https://github.com/spicyChicken59/SpicyStock/pull/114).
Its [dated acceptance record](release-evidence/2026-10-09-morning/acceptance.json)
retains hosted test counts, real-feed diagnostics, the production observation,
public asset hashes and phone/desktop browser results. The October 9 production
check is after the entry cutoff, with no quote rows or eligible orders. It is
evidence of correct binding and publication, not pre-open delivery or a trade.

### The analyst's daily brief

The owner's setup is layered (19 November 2026): SpicyStock is the view and the
daily output; an outside analyst, a person or a bot the owner runs, researches
the candidates, looks at the owner's account and recommends; the owner decides
and places every order. The brief is what that analyst reads in place of the
full record.

Each evening the run derives two companions, `docs/brief.json` (at most
250,000 bytes) and `docs/brief.md` (at most 80,000 bytes, rendered
from brief.json and naming its SHA-256). They are a function of the canonical
`data.json` bytes, the `picks.json` bytes and the model-record block the run
computed, and of nothing else: no clock, no network, no other file
(`src/brief.py`, `pipeline.publish_brief()`, after the research companions and
before the retained copies). `python -m src.brief --docs docs --check` holds a
committed pair to its derivation.

- The brief carries no "built at" and no "is newest". Freshness is the reader's
  own computation (`src/freshness.py`): `service.expected` gives the next
  session's completion, the two slot instants and the recovery limit, and
  `service.freshness_rule` says how to compare them with the reader's clock to
  get `newest`, `not_due`, `pending`, `late` or `missing`. `newest` means no
  record of a later session can exist yet; the same session can still be
  published again, and a later run can withdraw a ticket, so the rule tells
  the reader to fetch again and compare the binding before acting. Freshness
  is not permission: a ticket applies only inside `identity.entry_window`.
- Only the rows under `tickets` are published model tickets. Every other row is
  marked `RESEARCH ONLY`: a burst's levels are the record's plan rule over the
  row's own bar at the archived model account, a setting-up row's are the
  record's own plan, no order is printed for either, and a plan the rule or the
  event registry refuses prints its refusal and no share count (a refused
  setting-up plan still prints the record's trigger, limit and stop, marked
  `plan_rule_eligible` false).
- Tickets and names with a selected chart review are always in detail. The rest
  are detailed while the file fits, then written as compact rows, then named in
  the research tail; `bounds` states every count and what was left out.
- The market block prints all five regime rules in the order they are asked,
  fired or not, with the raw sums and the unrounded ratios. The verdict is
  re-derived from the record's own inputs, and a record whose verdict differs
  is refused.
- The event block reads the registry the record archived, never today's file,
  against every listed row, and says how old it is, which reviews are overdue
  and how many listed names had no earnings check. A stock that is not in the
  registry has not been cleared.
- Each ticket carries an order-entry block: the order as written, the buy stop
  against the last close, the six price states the morning check also uses, and
  the note that a broker takes a buy stop only above the current price. A burst
  ticket whose stop is at or over its skip-under line has no price in
  `below_entry_floor`, and the block says so; an anticipation ticket carries
  the record's own gap rule (an open over the gap line is gapped: catalyst
  check before buying).

The model-record block (`src/model_record.py`) is a second reading of the
scorecard's own tickets. It walks every retained ticket as the scorecard does
and refuses to speak when a ticket or a total differs from the scorecard's.
Beside the ticket counts it gives the count of distinct setups (a ticket issued
again inside the open-plan window while the one before has no fill known is the
same setup), the model account each ticket was sized against, and each stop the
model books at exactly the stop price read again at that session's close and at
its low. A sum of R is not a sum of dollars: R counts each ticket as one unit
whatever its size, and the model account has changed inside the window. The
brief carries the block verbatim when its ticket count, bucket counts and sum
of R are the scorecard's, its encoding is within 60,000 bytes, the brief
still fits with it and it uses no property name the secret scan reads as a
credential. A block over that bound is carried reduced: each plan row keeps its
identity, its result and the account it was sized against, which is what the
next night's model record reads back, and the setups table is left out. If
that does not fit either, or the block disagrees, the brief carries one fixed
reason. A ticket's account is read from the record on the night it is issued
and from the previous brief afterwards, so a night with no carried block leaves
later tickets' accounts unknown, said so and never guessed. `python -m
src.model_record --docs docs` prints it from the record's own observations
block without market data; a ticket whose bars the record no longer carries
takes its bucket and R from the publication's quality-ledger row and is marked.

The brief never fails a run: a derivation that fails installs a pair that says
the brief is unavailable for these bytes, and anything else is one warning in
the run log. When tonight's pair cannot be installed at all, the pair left on
disk is an earlier publication's: `publish_brief()` removes it
(`brief.discard_unbound()`), so a reader finds no brief rather than a stale one
that reads as current, and the publication gate serves the record as it did
before the brief existed. The gate holds a committed pair to the committed
record by its hashes (`brief_files()` in `tools/publish_dashboard.py`) and
fetches both files from the served site; a pair bound to another publication is
refused. The gate checks the binding and not the content: a hand-edited
brief.md that keeps its binding line passes it, and only
`python -m src.brief --docs docs --check`, which re-derives the pair, would
name it. No pair is committed with this change: the first evening run
after it writes the first one. After the page fixtures are regenerated,
regenerate the brief's golden pair last (`python tests/fixtures/brief/generate.py`;
CI runs it with `--check`).

### The execution handoff

An execution agent outside this repository decides and places the owner's
trades; SpicyStock still decides nothing. `src/orders.py` writes what it
reads, each a function of committed bytes and no clock:

- **`docs/orders.json`**, after the brief each night (`pipeline.publish_orders()`):
  every ticket the record published (`morning.admitted_rows()`, the rows the
  morning receipt quotes), each with its day buy stop-limit, its entry window,
  its OTO sell stop, the exit plan as machine-readable rules in
  `plan.follow()`'s order, its risk in dollars and in R (the limit less the
  stop), the position cap and the risk budget checked again, its status
  (`go`, `human_review`, `blocked`) and a content hash. Beside them, the
  night's five checks (`light`, `market_inputs`, `publication_time`,
  `cross_check`, `account`), each `pass`, `fail` or `not_evaluated`, and
  `trade_allowed`: true only when every night check passes and a ticket is
  `go`, with every reason that kept it false. `mode` is `paper` and
  `live_ready` false until the record's go-live gate holds (below). A night
  that cannot write it removes the previous night's, so no earlier tickets
  read as tonight's.

  **Data quality is read where it applies, never off the run's status word**
  (the owner's decision of 25 November 2026; before it one `degraded` status
  stopped every ticket of the night). The night's `market_inputs` check reads
  the record's own input ledger: it fails when more intended stocks were
  without usable bars than the limit the record archived for its stale
  tolerance (`inputs.stale_limit()`, applied here to every kind of gap), when
  the selection was cut at its capacity, when the stock directory failed
  and the seed list stood in, or when not every measured stock was scanned
  and checked (`acceptance.complete_evaluation` false); it is
  `not_evaluated` when the ledger, the archived limit, the status or a
  problem word is not one the file reads. The
  light, the ranks and the slots rest on those inputs, so that check stops the
  night. Everything else is read on the ticket it concerns. `inputs` fails
  when the record names the ticket's stock among the stocks without a usable
  session frame or among the frames held under an open model plan, passes
  only when the row's own sealed source frame and its last two archived bars
  are dated the session and the session before it, and is otherwise held for
  a person (the ledger samples its lists, so a stock's absence from one is no
  evidence). `reader` holds a burst ticket to an accepted chart review made
  with its chart; a setting-up ticket is measured and never chart-read. A
  refused chart review, a chart that did not render, a mail that failed, a
  cached directory and a late follow-up bar stop no other ticket.
- **`docs/positions-template.json`**, beside it: one blank position per
  ticket for the agent to fill with real orders, fills and exits in a private
  copy that is never committed here.
- **`docs/orders-morning.json`**, always beside `orders.json`. The evening
  writes it with `orders.json`, `status` `pending`: every ticket `cancel`
  (`morning_check_pending`), because no morning check has run for that record.
  The morning's persist job (`python -m tools.publish_morning orders`)
  replaces it: with a receipt on `main` bound to the record that records a
  check that ran (`observed`, `partial` or `no_tickets`), `status`
  `checked` and each ticket re-read against it, `go` or `cancel` with its
  reasons (the night not allowed, no recent price, a halt or a halt source
  that could not say, the receipt completed after the ticket's cutoff, the
  event registry, a retained corporate exclusion or an SEC flag, a price over
  the limit, under the skip line, or at or over the buy stop, or in a state
  the file does not know); with none, or one that checked nothing
  (`inapplicable`, `provider_unavailable`), `status` `no_check` and every
  ticket `cancel` (`no_morning_check`). A setting-up ticket has no skip line, so
  under its trigger it stays `go`. A scheduled morning slot that starts after
  the entry window has ended collects nothing and still writes the file as
  `main`'s own files give it (the workflow's `close` job, `--window-closed`),
  so a morning with no check ends as `no_check` on `main`. `cancel_all` is
  true unless the status is `checked`. Derived on the spot from `main`'s own
  `orders.json`, receipt and record, and committed alone.

  **The rule an execution agent applies** is stated in `orders.json` itself
  (`morning_rule`, `orders.MORNING_RULE`): a ticket is entered only while
  `orders-morning.json` is bound to that exact `orders.json`
  (`orders_sha256`), its `status` is `checked`, the ticket's `decision` there
  is `go`, the clock is before the ticket's `valid_until`, and `orders.json`
  itself allows the night and marked the ticket `go`; a missing file, one
  bound to other bytes, or a night `orders.json` does not allow cancels every
  ticket, and `python -m src.orders decide` applies the rule
  (`orders.entry_decisions()`).

Two reads stand behind each ticket's checks. **`run.sec_flags`**
(`src/sec_flags.py`) reads each ticket's and each listed setup's SEC filing
list, the earnings warning's own transport and bounds, and names every
tender offer, response, merger proxy (SC TO-T, SC TO-T/A, SC 14D9, SC 14D9/A, DEFM14A, DEFM14A/A, PREM14A, PREM14A/A)
and every 8-K carrying item 1.01, 2.01, 3.01 or 5.01 filed
in the 30 days before the signal session or since it; a flag, or a name SEC
could not be read for, holds that ticket for a person's review and refuses
nothing on the record itself. **`run.cross_check`** (`src/cross_check.py`)
reads each ticket's signal-day bar again from Alpaca's iex feed, at most 20
tickets, in one batch retried once on failure: an open, high, low or close
more than 0.5% from the sip bar, or a volume reading more than 10% off,
compared unrounded, blocks the ticket in `orders.json`; a ticket iex has no
bar for, a bar with a value that is not a finite number, or a previous session
the two feeds do not both carry as the XNYS session before the signal, is
held for review. IEX is one exchange, so its daily volume is a few percent of
the consolidated tape's and an absolute comparison would fail every ticket;
each feed's signal-day volume is read against its own previous session, and
the two ratios are compared (`cross_check.VOLUME_BASIS`, a departure from the
program's literal volume rule that the owner's decision should confirm). Both
are archived in the rules (`sec_flags`, `cross_check`), held by
`report.validate()` under the rules that write them (a cross-check row's
result re-derived from its own differences, a flag's filing held to the
window and the listed forms), and never fail a night.

The schema of all three is `docs/operations/orders-schema.json`, checked by
`src/schema_check.py`; the publication gate holds each file to the committed
record, to that schema and to its own checks (a file whose `trade_allowed`,
reasons, statuses, summary or mode are not what its checks give is refused),
and `tests/test_orders.py` re-derives a committed `docs/orders.json` from the
committed record. A merge that moves `orders.VERSION` leaves the files on
`main` as the earlier code wrote them until the next evening rewrites them:
they keep their own version's meaning, the gate and that test hold them to
their binding alone (`orders.earlier_version()`), and the morning step reads
no ticket of one: it writes a go/cancel file bound to it that lists none and
cancels every one (`orders_earlier_version`).
The agent's guide is `docs/operations/orders.md`.
`tests/fixtures/orders/` holds golden files over the page and morning
fixtures; `generate.py --check` runs in CI.

### The go-live gate

`orders.json` is paper only until the record's own gate says otherwise
(`run.go_live`, `src/go_live.py`, computed each evening; its `mode` is then
`live` and `live_ready.value` true). The gate is operational only (the
owner's decision of 25 November 2026): it reads no outcome, and no
settled-plan count, win rate, expectancy or study is to be made a condition.
Two conditions:

- **The Fidelity protocol.** The owner has recorded it as passed in
  `knowledge/go-live/fidelity-protocol.json`, dated no later than the
  evening's session. `docs/operations/go-live.md` says which answers of the
  sitting count as a pass; nothing here records one.
- **On-time sessions.** The gate needs the newest 10 consecutive sessions published by 19:00 New York time
  on their own date, ending on the session before tonight's. The clock is
  the run's finish: its start plus `run.finish_seconds`, stamped at the
  record's final write (`run.elapsed_seconds` stops earlier, before the SEC
  reads and the install). Each was started automatically (a scheduled run or
  the dispatcher's `only_if_unpublished` dispatch, archived as
  `run.trigger`) and checked by a morning check that ran, bound to that
  publication, inside its collection window and generated by 08:45 Chicago time.
  The gate reads the newest morning receipt on `main`, so a later run for
  the same publication replaces an on-time one. A record that is not itself
  a forward publication (a backfill, or a run made at or after the open its
  plans are for; `run.go_live.publication`) never reads live.

The ledger closes each session the evening after it, and only a real
publication (not a rehearsal, and a status the evening guard reads as
published). Its first row is the last record made before the gate, not
counted because it archives no `run.trigger`, so the count starts at zero.
The Record view prints the gate. The publication check holds a live
`orders.json` to the committed protocol record again.

Version 1 of the gate (19 to 24 November 2026) also asked for twenty settled
model plans under standing rules and for the committed ablation. A record
made under it is still read and held by version 1's own validator
(`go_live._faults_v1()`, over version 1's criteria in
`go_live.CRITERIA_BY_VERSION`), and the handoff never reads such a block as
live; nothing writes it now, and the ablation
stays as research the gate does not read.

Two things the gate cannot read: a hand dispatch with
`only_if_unpublished` ticked, and how a morning check was started.
`docs/operations/go-live.md` records both.

### The strategy page

`docs/strategy.html` is the strategy as the installed record's rules state
it (`src/strategy_page.py`, written by `pipeline.publish_strategy()` after the
handoff each night, linked from the Method view): the market light's five
rules with the night's scaled thresholds and values, the two discovery scans
and the admission gate, the checklist's weights, bands, gate letters and
vetoes (the linearity veto's two conditions, and a leg too short to measure
being none), the chart-reader requirement, the burst ticket (the buy-stop rule
the record was made under, the limit, the stop, the size with its two hazards,
the entry window and the skip lines) and the setting-up ticket, every rule of
`plan.EXIT_RULES` with its source mark and the order the model's walk
(`plan.follow()`) applies them in, and the night's candidate funnel. Every
rule is read from the record's archived `rules`; where the record archives
none the code's constant is printed and named, and a code constant that has
moved since the record is named with both values, so a merge is never
attributed to an older record. The module types no number of its own: no
digit in its text and no number literal but an index and its unit, which a
test reads its source to say. CI runs `tools/build_strategy_page.py --check`;
the publication gate holds the page's own record digest to the committed
`data.json`. A night that cannot write it removes it.

### The scorecard, read honestly

`record.scorecard()` counts tickets and sums R, and its numbers do not move.
Beside it, each record carries `scorecard_reading` (`src/scorecard_reading.py`,
composed by `pipeline.read_scorecard()` after `report.build()` and before the
mail), and the Record view, the mail and `orders.json`'s `scorecard` print its
sentences verbatim:

- **distinct setups**: the tickets in the scorecard's window against the
  setups they are (`model_record.setups()`: a setup issued again on a later
  night is one setup);
- **the model accounts**: the tickets by the account each was sized against,
  with its settled count and R (`model_record.eras()`); tickets with no
  recorded account are counted, not guessed;
- **the stopped tickets read three ways**: as booked at the stop, at that
  session's close and at its low (`model_record.stop_bounds()`), because a
  stop touched inside a session is booked at exactly the stop;
- **published against revised breadth**: the sessions whose up 4%, down 4%
  or 10-session ratio this record computes differently from the figures that
  session's own first publication carried, named newest first. Each record
  carries those first-published figures forward
  (`scorecard_reading.breadth_revisions.published`), so a session is held to
  what its own night printed, never to a later re-reading; a session first
  published before the figures were retained is counted, not compared;
- **real against model**: real trades are not public. An execution agent
  fills a private copy of `docs/positions-template.json`, and
  `tools/positions_compare.py --positions <file> --docs docs` reads it beside
  the published record on the owner's computer: each position's real R (the
  average fill less the planned stop as one R, each exit weighted by its
  shares) beside the model's R for the same ticket, never added, writing
  nothing but an explicit `--json` outside the repository.

A model record that cannot be computed is said so in the block and never fails
the night. The validator asks for the block only under rules that archive
`pipeline.scorecard_reading_version`, so a record from before it is read as it
was written, and it re-derives the block's sentences from the block's own
figures, so a sentence that says other than its figures is refused. Real
against model stays private (`real_vs_model.status` is `private`): the record
never reads a positions file, so the page, the mail and `orders.json` carry
only the sentence that says where it is read.

### The analyst's instructions

`docs/analyst/prompt.md` is the standing instruction file for the outside
analyst: the three layers and the hard limits, what SpicyStock has and has not
shown, the freshness check, the method as a rule sheet, how to read the brief,
the decision tiers, the research checklist, sizing for a cash account, Fidelity
order entry by price state, managing an open position, the message templates
and the ledger. `docs/analyst/bootstrap.md` is a note of under 2,000 characters
that tells a bot to fetch it, and `docs/analyst/README.md` tells the owner how
to use both. `tests/test_analyst_prompt.py` holds every strategy number the
prompt states to its module constant, its URLs to `report.PAGE_URL`, the page's
`REPO` and the morning endpoint, the brief's section names, field names and
bounds to `src/brief.py` and the golden brief, the freshness states to
`src/freshness.py`, the morning receipt's fields to the collector, and all three
files to carrying no email address, no account number, no owner's name and no
dollar figure that is not the model's or inside a labelled synthetic example.
The files are public: the owner's profile block in the prompt is filled in
privately, never in the repository. The dated figures in section 2 of the
prompt are as of 19 November 2026; the bot is told to prefer the live brief.

### Service watch

GitHub starts this repository's scheduled runs hours after their slots, and
until 19 November 2026 nothing said so when a night had not arrived.
`tools/service_watch.py` asks three questions of the files on disk and a clock:

- **Evening.** Has the session after the one `data.json` covers been published?
  The answer is `src/freshness.py`'s. It is flagged only when the publication is
  still absent 6 hours before its recovery limit (the next session's open),
  or, for 12 hours, once it is past it. The limit decides, not the state word: a
  record with no readable delivery policy reads `pending` until its limit and
  is flagged the same way. Late alone is never flagged: read off the landing
  commits, the 23 first publications from 19 October to 18 November 2026 landed
  9.36 hours or more before the next open. A second missed night in a row has
  no `missing` of its own, because the record still names the first, so the
  watch also counts the sessions that have completed since the record
  (`sessions_behind`) and judges the newest of them by the same two bounds.
- **Start.** Did the evening run that wrote the record start within 60
  minutes of its primary slot (6:16 PM ET), read off the record's own
  `run.delivery.after_primary_minutes`? The on-time dispatcher (below) starts
  it at 6:20 PM ET, so a start more than 60 minutes late is GitHub's own cron,
  the backup. Flagged for 14 hours after the run started.
- **Morning.** From 8:45 AM CT on the applicable session (`MORNING_DUE_CT`):
  did a morning check bound to this record's bytes land inside its collection
  window? Flagged, for 12 hours after it was due, on every session, ticket or
  not: the dispatcher starts the check at 8:20 AM CT, so one that is not there
  by 8:45 is the service's, whatever the night published. A receipt whose status says it quoted nothing
  (`provider_unavailable`, `inapplicable`) has not landed. A check that landed
  is said with when it ran and what it priced: every real ticket morning from
  3 to 16 November 2026 reads "generated before the entry window opened, and 0
  of its N ticket rows carried a recent price", which is what a dispatch before
  the 8:30 AM CT open gives, and is reported, not flagged. A receipt bound to
  an earlier publication of the same session (the session was published again
  after the morning) is a check that landed.

It calls no provider and writes nothing. With `--mail` each run mails each
alert it finds through the evening's own transport; it keeps no memory, so one
late night can mail from two runs and a missed one from two or three. It exits
0 with nothing to flag, 1 on an alert and 2 when the record cannot answer, and
with `--mail` a record on `main` that cannot be read at all is mailed too.
`service-watch.yml` runs it on
`main` at 05:07 and 09:07 UTC daily and 16:07 UTC on weekdays, read-only, with
the three mail secrets and no other; an alert turns that run red. The watch is
itself a scheduled run and so itself hours late on most days: the two morning
slots are placed so that one of them lands inside the alert window before the
open while the scheduler is up to 8.3 hours late in daylight time and 9.3 in
standard time (the longest delay the 13 October schedule reading recorded was
8.4 hours), and nothing here can make GitHub's scheduler punctual. A missing
night's alert says what can still publish it: the scheduled slots and a
dispatch with **only_if_unpublished** ticked cannot, and a plain dispatch with
the session box filled can, for an entry window that may have ended. When
more than one session is unpublished it names the first missed one beside
that, and says the newest can still be published by a dispatch with
**only_if_unpublished** ticked while its own limit is ahead (such a dispatch
does nothing before the session's primary slot, 6:16 PM ET). The same
answers are printed for anything else with a clock:
`python tools/service_watch.py --docs docs`.

### On-time starts

`tools/dispatch_schedule.py` starts the runs GitHub's scheduler starts hours
late, by `workflow_dispatch`, on XNYS sessions only (`src/sessions.py`):
`evening.yml` at 18:20, 19:20, 20:20 and 21:20 America/New_York with
**only_if_unpublished** ticked, so the four starts publish the newest session
once; `morning.yml` at 08:20 America/Chicago; `service-watch.yml` at 06:00,
08:45 and 11:00 America/Chicago. A slot is due for 30 minutes from its
instant, and before it asks for a run it reads the workflow's dispatched runs
created since the slot, so a repeat tick, a restart or a second copy starts
nothing twice. It holds one credential, `GITHUB_TOKEN`, a fine-grained token
with Actions read and write on this repository alone, and logs the workflow,
the slot, the run id and an HTTP status, never a token or a body. It runs as
its own Railway service (`deploy/scheduler/Dockerfile`,
`deploy/scheduler/railway.json`); deploying it is the owner's step, in
`docs/operations/external-scheduler.md`. GitHub's crons stay in every
workflow as the backup.

## One-time setup

Six repository secrets: `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`,
`ANTHROPIC_API_KEY`, `RESEND_API_KEY`, `RESEND_FROM`, `EMAIL_TO`. Two
optional repository variables: `SCAN_FEED`, `SCAN_UNIVERSE`. The production
evening workflow explicitly sets `ACCOUNT_EQUITY=30000` and `RISK_PCT=0.5` (`2000` before the 4 November 2026 session);
edit that versioned configuration when the owner's sizing reference changes.
Local `Account.from_env()` defaults remain the historical $10,000 model and
accept local `ACCOUNT_EQUITY` / `RISK_PCT` overrides. GitHub Pages from `main`
`/docs`. Until a
domain is verified at Resend, `EMAIL_TO` has to be the address the Resend
account is registered under, alone. `.env.example` explains each.

Before the first cron: dispatch `evening.yml` with **dry_run** ticked. That
is the one thing this repository cannot rehearse offline — a full-market
fetch from a runner — and its log says how long the fetch took against the
budget, how many names answered, how many bursts the scan found (Bonde's
median night is 239 over 6,500 names), and what the page would have said.
The artifact holds the record and the charts; nothing is committed or mailed.

## Run locally

CPython 3.12, as every workflow runs: the pinned numpy 2.5.4 and contourpy
1.4.0 need 3.12 or later, so the pinned set does not install on 3.11.

```bash
pip install -r requirements.txt -c constraints.txt
cp .env.example .env              # single-quote every value
set -a; . ./.env; set +a
MPLBACKEND=Agg python -m src.pipeline evening --dry-run --tickers AAPL,AMD,NVDA,SPY
```

`--tickers` skips the directory; `--dry-run` mails nothing and records no
pick, but still fetches, grades and writes `docs/data.json`. Then open the
page from the repository root, `python -m http.server`, at
`/docs/index.html`. `git checkout -- docs/` puts the committed record back.

The regression net needs no keys and no network:

```bash
pip install -r requirements-dev.txt
pytest tests/ -q                            # every boundary is a double
node tools/chart_check.mjs                  # the chart's geometry, and a render
node tools/page_smoke.mjs --shots /tmp/shots   # the page against every fixture, read back
node tools/page_smoke.mjs --only reading      # recorded meanings, help and review journey
node tools/page_smoke.mjs --only status       # both ticket families and workflow/publication distinction
node tools/page_smoke.mjs --only decisioninspection # anticipation reasons and exact recorded-chart navigation
node tools/page_smoke.mjs --only findings     # the Record view's replay over the committed findings
node tools/page_smoke.mjs --only funnel       # the scan disclosure's candidate funnel, printed from the record's own block
node tools/page_smoke.mjs --only service      # pending against stale off the record's calendar and archived slots, every phase at every width
node tools/page_smoke.mjs --only recovery     # the Method view's source-recovery line, bound to the loaded publication's bytes
python tools/make_fixture.py --check        # the fixtures are the pipeline's own records
```

The page smoke runs its suites in two lanes over one browser, each line it
prints marked `[A]` or `[B]`: lane A holds every suite that writes the
smoke's own scratch records under `tests/fixtures/page/` or reads the
clipboard (Chromium shares it between contexts), one after another; lane B
holds the self-contained modules beside them. In one line they took 14 m 54 s
of the CI page job's fifteen minutes. `--only` still runs the suites it names.

A browser check is held to a slow runner. It reads the page's state in the
task of the action that changes it (`locator.evaluate()` clicking and reading
in one call, a listener added for one event), or it waits on the condition it
asserts (`waitForFunction` with a bound), never on the clock: the page moves
on its own between two Playwright calls -- a playback tick, the 30-second
re-reading of the clock, an observer delivery, a Web Lock granted before a
store write, a route the test holds -- and on a loaded runner the wall clock
between those calls is unbounded. A fixed `settle()` pause may follow a check;
it never decides one. A check that cannot be written that way is a check that
cannot be trusted, and is rewritten or removed.

One tool is not a check but a reading. `python tools/entry_limit_study.py
[record.json ...]` puts three readings of every burst in an already-written
record beside each other: the **retired** fixed ceiling (the close +4%,
`plan.ENTRY_ABOVE_PCT`, with the stop cascade judged there), which is no
longer in `src/` and lives in the tool alone; **production**, which is
`plan.burst_plan()` itself and which `verify()` reproduces down to the share
count, the action and the money; and an **oracle**, the constrained ceiling
re-derived in the tool from the spec and held against what production wrote,
so a drift in either raises rather than prints. The oracle never reads the
synthetic `max_stop` fallback, so that level can rescue nothing, and it
admits a ticket only where `stop < trigger < limit` holds at the rounded
ceiling — strictly under and strictly over, because a limit at the buy stop
is a ticket with no band. It reports candidate coverage, the retired
ceiling's stop-rule rejections, what production admits and refuses (by
refusal), and what inputs are missing, each kept apart from the regime,
grade, veto, discovery-admission and budget exclusions (a dollar-only name
without a range-expansion, higher-volume day is counted under its own gate and
left out of the green-night population, since it never reaches the stop rule),
and it counts what the narrower limit carried
with it. It changes no rule, writes nothing, reads no forward return, and is
not a backtest or a claim about either ceiling.

The one tool that IS a backtest is `python tools/historical_backtest.py
--manifest <acquisition-manifest.json> --storage <recovered package> --output
<private directory>`. It replays the run's own stages over the bars a recovered
historical acquisition package holds, one session at a time, calling the
functions the pipeline calls: the session rules and the $3 policy over the names
that printed, `breadth.snapshot()` and its regime, `pipeline.scan_frames()` and
`pipeline.rank()`, `pipeline._make_plans()` with the open model plans of the
sessions before counted against the slots, `record.append()`, and the published
scorecard's own `record.scorecard_rows()` and `record.summarize_scorecard()` over
the whole archive instead of their window, with `record.append()` told a
retention its picks cannot reach and the run refusing to score a population it
did not issue. Every number is the module's. The reader is NOT RUN, so every
name's mechanical grade is the ceiling of its final grade (the ticket set is
not a superset of the live run's, because a reader downgrade frees a slot the
next name takes); the universe is the archive's later membership
(survivorship); fills, exits and R are the daily-bar model the scorecard uses. A
second block removes the regime gate and is labelled a counterfactual. Each
evaluated session needs `pipeline.LOOKBACK_DAYS` sessions of history before it,
as a live frame carries; `--lookback` may shorten that to reach more sessions,
and a shortened lookback is admitted only with its equivalence check -- on every
session that also carries the full lookback both are measured and compared
(regime, every candidate's grade, score and vetoes, every plan's prices and
shares), and a single difference is a FAIL and exit code 2. It writes
`backtest.json` (every row, with prices: private) and `summary.txt` (counts and
R only). Both the storage and the output must sit outside any Git checkout. It
makes no provider, model or network call, and it is not an edge claim: the
summary reads no rate under the scorecard's own minimum.
Its first real result -- the owner's run of 6 October 2026 over the run-6
archive, 158 sessions with the equivalence check reported PASS -- is recorded as
pasted, from the two summaries, in
`docs/input-truthfulness/2026-10-06-backtest-results.md`; the per-row files stay
on the owner's machine.

Its sibling over the public records is `python tools/signal_outcomes.py --spec
<spec.json> --output <dir>`: every burst row in the first publication of each
session the spec names, ticketed by `plan.burst_plan()` with the record's own
account at the GREEN multiplier -- the regime gate, the slot cap and the budget
not applied -- and walked by `record.replay()` over `plan.FINAL_EXIT_DAY`
sessions of the records' own published bars (the observation histories, the
latest observations and the candidate series, the newest publication winning
and every changed bar counted as a revision), bucketed as
`record.scorecard_rows()` buckets a plan and summed by
`record.summarize_scorecard()`. The rows are read in strata by the checklist's
verdict -- admitted (`pipeline.TRADE_GRADES` with no veto), B, C, skip, vetoed
-- so the admitted stratum stands against the rest of the same nights, by night
with a night-block bootstrap, with a labelled bound for the uncertain fills
(the same ticket filled at its trigger) and three per-side costs beside it. The
spec is committed before any outcome is computed and names the publication
commits and their record blobs; a commit the checkout cannot produce or a blob
that differs is a refusal, never a smaller population. Signals published up to
the spec's freeze are exploratory, later ones confirmatory. It is a
counterfactual: the live policy published no reaction ticket on any night the
study reads, so every ticket it walks was one the policy refused -- by the RED
gate; on a YELLOW night by YELLOW's A+-only band, which the admitted stratum's
A tickets do not pass, or, for an A+, by the reader, which lowered it below the
band or had its reply refused, so the accepted-review requirement withheld the
ticket -- and the study does not run the reader; it reads no rate under the
scorecard's minimum and is not an edge claim. (The frozen spec's own sentence
says the RED gate alone; the 17 October report corrects it.)
Its confirmatory re-reads, each under a spec that differs from the frozen one
by appended publication entries only, are
`docs/input-truthfulness/2026-10-06-signal-outcomes-confirmatory.md` over
nineteen publications,
`docs/input-truthfulness/2026-10-17-signal-outcomes-confirmatory.md` over
thirty-one,
`docs/input-truthfulness/2026-10-24-signal-outcomes-confirmatory.md` over
thirty-seven and
`docs/input-truthfulness/2026-11-07-signal-outcomes-confirmatory.md` over
forty-seven.
`python tools/build_historical_findings.py --check` holds the committed
`docs/historical-findings.json`, which the Record view replays, to those
evidence files and nothing else: the two study outputs, the publication
records the spec names (read from git by commit and held to the blob), the
owner's two pasted backtest summaries parsed by the exact line grammar
`historical_backtest.summary_text()` emits, and the pasted run-6 summary
with its public receipt. A difference exits 1, as `make_fixture.py --check`
does; a line the grammar does not know is a refusal, never a skipped
number, and so are a missing or repeated line, a line before the block it
belongs to and a printed bool that is not True or False; and a field name the
secret scan would read as a credential is refused before anything is written.

The fixtures under `tests/fixtures/page/` are records the real pipeline wrote
over a synthetic market through the same doubles the tests use, one per
state the page can be in (`full`, `degraded`, `notrade`, `yellow`, `red`,
`closed`, `empty`, `partial`, `early`, `thin`), plus two sequels of the `full` night (`next`, `revised`) run over
the docs that night wrote, so a setup followed then can be read against a
genuinely newer record: `next` is the same market one session on, where the
ticket and the withheld setup have left the record, one burst has burst
again and the coil has broken out; `revised` is that same session re-run on
later bars, one close a few cents off — a correction and not another trading
day. `docs/data.json` on a fresh clone is the `full` one until the
first real night replaces it. A fixture, and that placeholder, is the
pipeline's record labelled `fixture`, its two run clocks zeroed, re-serialized
at indent=1 for reviewable diffs; the pipeline itself writes compact. The page smoke opens each in Chromium and
compares what it reads back with the record it was handed — every stock in
both stages, the search, the chooser and the rail on a phone, the keyboard,
deep links and Back, the old anchors, unknown routes and symbols, rapid
switching — then views the `full` record at three later instants for the
stale states, drops twenty fields in turn (a burst without browser bars must
offer its matching retained source or say *Chart unavailable*), and opens it
once with no record at all.

## The record

`docs/data.json` (schema 2) is one object: `run`, `cover`, `breadth`,
`bursts[]`, `trades[]`, `beyond_cap[]`, `cash_budget`, `watchlist`,
`open_plans[]`, `scorecard`, `nights[]`, `account`, `rules`, `closest_miss`,
`funnel` (where every discovered reaction candidate and every listed anticipation
setup stopped: one terminal stage each, in the order the run applies its gates
-- the admission's `route` stage among them from version 3 --
so the stage counts sum to the discovered count; `src/funnel.py` derives it from
the fields beside it, the validator re-derives it, and its labels travel with it
so the page and the mail print the record's own words -- a stage is the record's
accounting of its gates, never a judgement of the setup or an entry),
`observations` (every saveable published signal's own identity and 21-day
window, plus up to 20 real dated observations per symbol from frames already
fetched; missing frames retain dated real observations),
`app`, and `_contract`, which names every top-level key in a sentence.
`rules` is every module's constants nested by family, and `app.rules_version`
is a digest of that block, so two records produced by different numbers can
never be read as one. The selection's membership identity
(`universe.identity`, the directory's symbols) is nested among them, so the
digest moves on any night the live directory's membership moves, which is most
nights; a record is read under the rules it archived, never by whether its
digest equals another night's. `report.validate()` names the malformed shapes it
checks and raises nothing else through its caller: `tests/test_record_shapes.py`
substitutes a string, a list and an integer for every top-level key, every
child of a top-level object, every grandchild and great-grandchild under
`run`, and the first item of every top-level list with each of its children,
and holds the validator to a named refusal or a pass and nothing else. A
substitution it does not hold is a pass (`closest_miss`, `generated`,
`schema_version` and `scorecard` are read by the page and checked by nothing
here), never an exception. `docs/picks.json` (schema 2 for new writes) is every published plan: ticker,
session, kind, the entry zone or trigger, the stop, the shares, the targets,
the ticket. It holds nothing about what anyone did with them.

New candidates carry provenance v1: a stable evidence ID, exact source/read-view
digests, discovery and mechanical-check digests, chart-reader input/result or
explicit fallback, breadth eligibility and plan inputs/output. The same ID
travels with tickets, persisted picks, immutable recovery and new saved originals.
The detail disclosure says **Evidence recorded** and whether a ticket existed;
technical IDs stay inside a further disclosure. Local annotations do not alter it.

Full frames and exact reader inputs are deduplicated under `docs/evidence/`,
outside the initial page payload. The archive is capped at 128 MiB; before a
night's objects are written, an object no other file under `docs/` names leaves
the working tree (git keeps it). The rolling part -- what the publication and
the 21-day recovery catalog name -- comes and goes; what the dated reports, the
quality ledger, the research cohorts and the frozen cases name stays, and the
ledger's share grows a little each night (see the provenance contract). The chart's optional source reader verifies
one retained frame's identity; it does not replay the recommendation chain.
Full verification calls the existing strategy
functions offline; it never repairs evidence or requests providers/models.
Schema-1 picks retain their original fields; September 11/14 histories are not
rewritten. Missing legacy provenance is explicitly partial/unknown. See
[the provenance contract](docs/provenance/README.md) for canonicalization,
retention bounds, examples and measured impact. To verify a retained publication:

```sh
python tools/verify_provenance.py --record docs/data.json --picks docs/picks.json --objects docs/evidence
```

**The scorecard is the rules' record, not yours.** It counts every retained
published Burst and Anticipation ticket from the prior 60 exchange sessions
plus the current publication. A ticket is one night's order: a setup issued
again on a later night is a new ticket and is counted again, and a ticket a
later run of the same session withdrew stays in the file and in the count. R is
counted per ticket whatever its size, and the model account the tickets were
sized against has changed inside the window ($10,000, then $2,000 from the
second 8 October publication, then $30,000 from 4 November), so a sum of R is
not a sum of dollars. Current plans await their first session. Missing
or stale observations, uncertain fills, unreadable walks and unfilled orders
stay in the total; none is silently converted to a loss, a win or zero R.
Non-ticket setups and browser-local selections never enter that population.
File-capacity and malformed-record limits are disclosed; this is not an
unlimited inception-to-date record.

A daily bar books a ticket filled only at the next open, at or over its trigger
and at or under its limit. A first day that opened under the trigger and reached
it later -- the usual first day of a buy-stop ticket -- is read again from that
session's one-minute bars (`src/intraday.py`, policy `first_window_minute_v1`):
the first minute of the plan's first 30 whose high reaches the trigger fills at
the trigger, or at that minute's open when it opened over it; no such minute in
the window is *not filled*, the plan's day order having been cancelled at the
window's end however far the day went later; a crossing minute whose fill would
be over the limit, or which reached the stop from under the trigger, cannot be
ordered by its own bar and stays *uncertain* (`minute_order`). A fill is walked
from the fill on: the entry day is rebuilt from the crossing minute, the close
and the stop rises at day 1's close to the session's own low. A crossing minute
that opened over the limit is *not filled* when no minute of the window from it
on traded back to the limit. The minutes establish the fill and nothing after
it: the walk from the fill is the daily model's, so a day-1 bar reaching both the
stop and +8% books the stop, as a fill at the open would. Minutes must reproduce
the daily bar to be used: no minute outside its range (at four decimals), a
minute reaching the trigger it reached, and a minute at or under the stop when
its low reached it; minutes that do not are another feed's account of the day.
An open past the limit or under the skip line keeps the daily answer, and a day
with no usable retained minutes stays uncertain. The published stop is
one R on the whole position; a half sold at +8% or at day 3 is at least half in
whole shares, so a one-share ticket sells whole at that step and its R differs
from the same plan at two or more shares, and every sale is weighted by its
quantity. With complete usable
bars, everything settles by day 5. Missing evidence never establishes that exit.
Only those five sessions feed the scorecard; later data gaps cannot erase its
resolved result. A session that opens at or under the stop is booked at its
open, not at the stop price; a stop first reached inside a session, the fill
day included, is booked at exactly the stop price with no slippage, so a stop
on the fill day is always -1.00R whatever that day's low or close.

The evening asks for those minutes itself, once: `record.needs_minutes()` names
the plans in the scorecard window whose first day the daily bar left uncertain on
a reason minutes can read, and `intraday.gather()` requests the `sip`,
split-adjusted one-minute bars of each entry session's regular hours -- one
request per session, at most 8 plans a run (newest first, the plans whose fetch
failed the night before after the rest, so one cannot hold the cap; the others
wait a night), each only once that session's close is behind the feed's 16-minute
hold-back. Each answer is one content-addressed object under `docs/intraday/`,
written once, read back and never replaced (512 objects, 16 MiB, 64 KiB an
object; at capacity nothing new is written and the plan stays uncertain). A plan
two objects claim is set aside by name, used by no walk and never asked for
again. Every walk of the night -- the model slots, the open plans, the scorecard
and the quality ledger's re-derivation -- reads the same evidence: what the
archive retains, and what tonight stored; a row walked from it names its object
in `minute_evidence`. `run.intraday` counts what was needed, set aside, asked for,
fetched and stored, the failures by kind (`no_minutes`, an error's type, never
its text) and archive problems, in a sentence the Method view and the mail
print; `report.validate()` holds it under rules that read minutes (and every
named object to what the walks could read). A failed or empty request leaves the
plan uncertain and never fails the run; a gathering that fails whole is the
block's `failed` status, and every walk still reads what the archive retains. A
dry run reads what it fetched and writes nothing.

It prints counts from the first night and rates only from twenty settled
plans. Wins, losses and breakeven reconcile to that explicit resolved denominator;
mean and median R use the same plans. Breakeven is the existing R rounded to two
decimals equalling zero. SPY is a percent-price comparison over matched entry/exit
dates, with its own pair count, not portfolio performance or excess R. Small
samples remain prominent, and twenty observations alone do not establish an edge.
Fees, spread, slippage, tax, actual executions and subsequent split rebasing are not measured.

[The scorecard contract](docs/scorecard-contract.md) documents all states,
retention, price basis, regime, versioning and the offline analysis command.
`tools/scorecard_analysis.py` uses the same replay and summary for complete
partitions by original rules version, burst/dollar/both, grade, regime, kind and
reader source. Exact original publication receipts establish attribution;
missing metadata stays unknown. `--docs` reads the minute bars a docs directory
retains under `intraday/`, so a first day the published scorecard read from them
is read the same way; without it that day stays as its daily bar leaves it. These partitions do not select a preferred
strategy or change the aggregate. Legacy website summaries retain their recorded
values and explicitly admit incomplete coverage accounting.

## What was cut, and why

The previous version carried a trade journal, a portfolio tracker, a broker
bridge with its own database, a ledger of forward returns on both bases, a
learning pipeline, a fidelity report against the canonical scan, a research
sidecar and a second daily run. All of it was tracking, and tracking was
work the reader was not going to do. What remains is the evening run, the
page, the email, and the one record that needs no hand: the picks file and
what the bars say happened to them.


### Exchange-session basis

`src/sessions.py` is the single authority: **XNYS (New York Stock Exchange)**,
from pinned [`exchange_calendars` 4.13.2](https://pypi.org/project/exchange_calendars/4.13.2/).
It works offline after installation and supplies historical holidays, exceptional
closures and shortened hours. [NYSE hours](https://www.nyse.com/markets/hours-calendars)
are the exchange reference. The calendar range is explicitly 1990–2035; requested sessions also need
their lookback and plan dates inside it. Requests without that context fail instead of substituting weekdays. Future schedules can change.

The newest completed session reaches its **scheduled close plus 15 minutes**;
this policy is separate from the exchange close and does not guarantee extended-hours
bar finality. Plan day 1 and subsequent dated exits enumerate actual sessions.
The entry window remains the strategy's first 30 minutes after the scheduled open.
All instants carry America/New_York offsets; no UTC offset is hard-coded.

A known holiday/weekend evening or intraday run logs `no_session`, publishes
nothing, preserves every previous file and sends no duplicate signal email. An
incomplete evening session logs `session_incomplete`. `SCAN_SESSION_DATE` means
requested exchange session: a pinned non-session is a precise preflight failure.
The workflow's cron slots are unchanged; `published=false` prevents persistence,
and skipped runs do not upload the previous record as a new artifact. The retry
may log the same skip, still without any provider work.

`run.calendar` records calendar schema, exchange/library/version, measured,
previous and next applicable session, scheduled opens/closes, shortened status,
and completion policy. Its ±45-calendar-day schedule lets the browser count real
sessions without independent holiday arithmetic. Beyond that window, or on old
records lacking provenance, freshness is unknown and actions are withheld. Old
records and saved setups retain their original timing and limitations. New saves
freeze their original timing evidence; later observations do not replace it.

The wait explanation uses that same publication/calendar authority. The close
buffer does not end an unpublished evening evaluation: the completed session
remains pending, or is reported as delayed/missing/possibly failed under the
existing freshness policy. A future completion time is not promised. Clock, focus,
visibility and refresh updates preserve the reading state. Planning explanations
distinguish a recorded early-gate skip, an attempted error, a produced refusal,
recorded sizing/allocation and unknown historical evidence; null alone establishes
none of those stages. See the [PR #92 correction and proof limits](docs/input-truthfulness/2026-09-28-pr92-explanation-correction.md).

The normal `page_smoke.mjs` gate includes the shared historical journey and wait
regressions, pinned to retained publications independently of later automatic
`docs/data.json` updates. `--only historical,wait-explanations` runs that focused
selection; `tools/historical_journeys.mjs` remains a standalone entry point to
the same historical assertions.

Deterministic cases include 2024-08-26 (ordinary Monday), Aug 31/Sep 1 (weekend),
Sep 2 (Labor Day), Aug 30→Sep 3 (adjacent sessions), Nov 29 (13:00 ET close),
Dec 2 (the following session), Mar 8→11 and Nov 1→4 (DST offsets). Historical
1992-11-27 closes at 14:00 ET, proving shortened hours are not a fixed 13:00 rule.
The `closed` fixture is an unchanged Sep 4, 2026 publication viewed on Labor Day;
`early` is the Nov 27, 2024 signal for Black Friday. `thin` is two evenings
over one docs directory and a 100-stock selection: on the first, two stocks are
behind -- one by two sessions, one by one -- (over the limit of one, so the
night is degraded and names both, with where each frame ends); on the second,
the first stays a session behind (within the limit, so the night is ok and
names it), the follow-up reads the first evening's two again from the second's
fetch at every session each missed -- three readings over two stocks, each a
flat, zero-volume bar the publication for that session would not have listed --
and the red regime uses only two accepted near-admission research reads. Reader
refusal limits remain covered by pinned offline policy tests. These
are offline fixtures, not historical point-in-time universe or profitability
evidence.

## Layout

```
src/            history.py (public recovery and coverage)
                provenance.py (immutable evidence receipts and offline verification)
                pipeline.py (the run) · inputs.py (population ledger) · universe.py · market_data.py · clock.py
                input_diagnostics.py (run-scoped exception membership and observations)
                followup.py (the next session's read of the previous publication's stale stocks, from its own fetch; never a signal)
                intraday.py (one-minute bars for a plan's first day the daily bar cannot place: fetched once, bounded, retained content-addressed; read again by every walk)
                quality_ledger.py (immutable publication input/grade/model-outcome facts)
                admission.py (which discovered candidates the trade band and the chart reads may consider: the 4% route, or the dollar route on a range-expansion, higher-volume day; read off the recorded route and the checklist's own RE and VOL checks, never a grade, and re-derived by the validator)
                review_selection.py (feasible-first chart review and bounded spare research)
                funnel.py (one terminal stage per discovered candidate, read off the record's own fields and re-derived by the validator; the candidate funnel)
                stop_research.py (registered source-bound anticipation comparison and immutable cohorts)
                research_outcomes.py (frozen cohort follow-through from dated retained observations)
                research_observations.py (dated IEX observation of the bound research cohort's allocation-fit rows; one request a run, never a ticket)
                source_recovery.py (one bounded re-request of the publication's named missing or stale stocks under its own frozen basis; the record unchanged, never a signal)
                earnings_risk.py (each ticket's earnings warning, estimated from SEC results filings a year back against the plan's hold; a warning, never a refusal; unknown never clear)
                scans.py · discovery.py · quality.py · breadth.py · watchlist.py · plan.py
                sessions.py (pinned XNYS sessions, actual hours and timing provenance)
                timing.py (which session a plan is for, and when its window is over)
                delivery.py (where a publication fell against the evening workflow's own slots and the next open; the record archives it, the page and the service-health reading read it)
                freshness.py (what a record says about the next publication: the next session, its completion, the two slots and the recovery limit; state() answers newest, not_due, pending, late or missing for a reader's own clock; standard library only)
                scorecard_reading.py (the scorecard read honestly: distinct setups, model accounts, the stopped tickets at the stop, the close and the low, breadth revisions; copied from the model record, never moving the scorecard's numbers)
                go_live.py (the go-live gate, operational only: the owner's Fidelity protocol record and ten on-time sessions, a ledger of closed sessions, whether tonight's publication is forward, and whether orders.json is live or paper)
                strategy_page.py (strategy.html: the strategy as the installed record's rules state it; every figure a rule the record archived, or a named code constant where it archives none)
                orders.py (the execution handoff: orders.json and its positions template each night, and the morning's go/cancel file, from committed bytes and no clock) · schema_check.py (the JSON Schema subset the handoff's schema uses; any other keyword is refused)
                sec_flags.py (each ticket's and listed setup's recent tender-offer, merger-proxy and deal 8-K filings, named by form and item; a flag that holds a ticket for review in orders.json, never a refusal or a clearance)
                cross_check.py (each ticket's signal-day bar read again from the iex feed; prices within 0.5% and the two feeds' volume ratios within 10%, or the ticket is blocked in orders.json)
                candidate_checks.py (the night's candidates, up to 80, read against SEC filings, the earnings estimate and the iex feed through one shared SEC reader and one iex batch; flags for a reader, never a gate; unknown never clear)
                brief.py (the analyst's daily brief: brief.json and brief.md, a function of the record's bytes, the pick ledger's bytes and the run's model-record block; no clock, no network)
                model_record.py (a reading of the model's own record for the daily brief: tickets against distinct setups, the model account each ticket was sized against, a stop booked at the stop beside its close and its low; held to the scorecard's rows, changes nothing; python -m src.model_record --docs docs)
                grader.py · reader_authority.py · reader_coverage.py · charts.py · record.py · report.py · event_risk.py · allocation.py · morning.py · morning_halts.py · morning_service.py · morning_service_worker.py · morning_service_journal.py · morning_service_report.py · morning_host.py · morning_host_wsgi.py · reader.py · issuer_evidence.py
docs/           index.html · app.js · app.css · app-reading.js · app-method.js · app-chart.js · app-map.js · app-follow.js · app-findings.js · app-morning.js · app-cash-preview.js · app-handoff.js · app-handoff-ui.js · app-observations.js · app-reader.js · app-issuer-evidence.js · app-stop-research.js · app-research-observations.js · app-research-outcomes.js · design-system/
                data.json · picks.json (the record) · charts/ (gitignored)
                reader.json · reader-observations/ (derived browser projection and deferred public history)
                stop-research.json · stop-research/ (registered comparison and immutable cohorts)
                research-outcomes.json · research-outcomes/ (dated conditional follow-through snapshots)
                brief.json · brief.md (the analyst's daily brief, derived each evening and bound to data.json and picks.json by SHA-256; written by the first evening run after this change)
                analyst/ (prompt.md · bootstrap.md · README.md: the outside analyst's standing instructions, the short note that tells a bot to fetch them, and the owner's guide; public, no account data; held to the modules by tests/test_analyst_prompt.py)
                historical-validation.json · historical-findings.json (read-only evidence the Record view fetches; the second built from the evidence files, not written by the run)
                historical-validation/ (the study's case files -- each case's archive context and evidence, byte for byte, under the digests the study recorded; frozen by tools/freeze_validation_cases.py because the archive below prunes, and held by its --check)
                history/ (recovery) · evidence/ (deduplicated source objects)
                intraday/ (minute bars of plans' first days, one content-addressed object per plan, written once)
                quality-ledger/ (versioned publication facts; created by future real publications)
knowledge/      strategy.md (the rulebook the grader reads) · method.md (whose number is whose) · rules.md (every rule the run applies, in pipeline order, each with its constant and class; held by tests/test_rule_sheet.py)
                broker-fidelity.md (the ticket on Fidelity's order entry; each fact labelled Fidelity's words, a regulator's words, inferred, unconfirmed, SpicyStock's advice, the owner's words, Fidelity's screen or the owner's practice) · broker-fidelity-protocol.md (the one-sitting check, order entry by price state, cash working rules) · trade-ledger.md (the outside analyst's ledger of real orders and fills) · event-coverage.md (what is checked about events and for whom; the ten-item check)
tests/          the suite, the doubles (fakes.py), the synthetic frames, fixtures/page/ · fixtures/brief/ (the brief's golden pair from the page fixture full; generate.py --check holds it) · fixtures/model-record/ (the 17 November 2026 record with its bars, frozen from git by its build.py; --check holds it)
tools/          make_fixture.py · page_smoke.mjs · chart_check.mjs · publish_dashboard.py · publish_morning.py · probe_morning_sources.py · sync_morning_service.py
                probe_sec_access.py (a dispatch-only diagnostic: SEC requests for AAPL and ZIM, or up to four named tickers, through the issuer collector's transport, and the index rows its row rules refuse, printed to the log; never published)
                capture_sec_document.py (dispatch-only: one SEC Archives document's byte count, SHA-256 and bounded excerpts through the same transport, for a review of the event registry; resolves nothing, never published)
                verify_provenance.py · provenance_impact.py (offline receipts and measurements)
                entry_limit_study.py (read-only: the retired ceiling, production and an oracle over an archived record)
                historical_backtest.py (offline: the run's own stages replayed over a recovered archive; reader not run; `--burst-trigger-rule` names the burst buy stop's rule)
                burst_trigger_comparison.py (offline: the signal-outcome study's own walk over the retained publications, every burst ticket built under each burst trigger rule)
                build_strategy_page.py (writes docs/strategy.html from the code and docs/data.json; --check in CI)
                ablation.py (offline: the pre-registered ablation, six rule changes each read against the production mechanics with the signal-outcome study's walk; --check holds ablation.json and its report, and tests/test_ablation.py runs it in CI over the population the file records)
                backtest_timeline.py (offline: the owner's private backtest record read into one row per night per gate -- the night's breadth and its tickets' outcomes by scorecard bucket, uncertainty kind and settled R -- every field copied by type from a fixed list; a private key, or a ticker the record names as a whole word in any case in a key or string that is not one of the tool's own words, is a refusal, as are a night or gate whose counts do not reconcile, a malformed file and an --output over the private file)
                signal_outcomes.py (offline: every archived signal ticketed and walked over the records' own bars; a counterfactual)
                build_historical_findings.py (a reader: docs/historical-findings.json from the committed evidence, every number bound to its source digest; --check holds it)
                freeze_validation_cases.py (a copier with --check: the study's case files frozen under docs/historical-validation/ from the archive while it still carries them, or from git at a commit the case names; byte for byte, held to the study's own digests, never a file the study does not name, never a rewrite of the study)
                candidate_funnel.py (a reading: the funnel of one or many publications, from files, commits or a ref's whole retained history; changes nothing)
                whole_share_feasibility.py (a reading: every archived reaction candidate sized again at an account under the record's regime, YELLOW and GREEN -- in band, past the stop rule, a whole share -- with the one-share price ceilings; the archived account unless overridden and labelled; changes nothing)
                evidence_review.py (a reader, dated: the frozen study re-derived from its rows and split by phase, regime, month, halves, grade, account and discovery route, each stratum's cumulative-R drawdown, the backtest, funnel, feasibility, retained research, live-scorecard and admission-join numbers copied off their files with digests and original commit/path provenance, and a ledger of the floated and the promoted strategy changes under stated criteria; writes the 7 November 2026 review, --check holds its two files, --retain writes its inputs from git once; the 12 October review is frozen to its blobs; nothing is promoted by it)
                service_health.py (a reading of the service, not the signal: every retained publication and companion receipt by the commit that landed it, each expected XNYS session, latency against completion and the evening cron's slots (the ones each record's rules archived, else the current policy's) by the landing commit's time with the record's own clock beside it, before-next-open, revisions, inputs, reads and cost, with the regime and tickets in their own column; --check holds its two files; changes nothing)
                recovery_rehearsal.py (a rehearsal, not a reading: run_evening() through the suite's doubles over one synthetic market, one injected failure a night -- the bars endpoint, every frame stale, the reader's credit, the reader's transport, the mail -- with the evening workflow's own guard executed before and after each night under a frozen clock; the exit codes, what was published, whether the previous publication's bytes survived, how often each boundary was asked and what the guard decided; --check runs it again and holds its two files; calls no provider and changes nothing)
                schedule_reliability.py (a reading of GitHub's scheduler, not the service: the public Actions listing of scheduled runs, each placed at its cron slot, the minutes from slot to creation per workflow, cron and week, expected slots with no run, the first run more than an hour late, and push runs on main as the contrast; --fetch is its only network path and --check holds its two files to the committed snapshot; changes nothing)
                dispatch_schedule.py (the on-time dispatcher: a workflow_dispatch of evening.yml, morning.yml and service-watch.yml at their slots on XNYS sessions, idempotent against GitHub's own runs listing; one fine-grained GITHUB_TOKEN; plan needs none)
                service_watch.py (a watch, not a reading: the record on disk and a clock -- is the session after it published, late near its recovery limit or missing, did its evening run start more than an hour after its primary slot, and did a morning check for this record land by 8:45 AM CT inside its collection window; mails through the evening's transport only with --mail and only on an alert; exit 0, 1 an alert, 2 a record that cannot answer)
                stale_inputs.py (a reading of the stale stocks across nights: each session's newest publication's named stock-sessions joined to every later follow-up reading and source-recovery row, each in one class -- would have been listed, scanned and not listed, under the $3 policy, a later bar read for its volume only against the 4%, breakdown and $ scans' floor, a later bar whose volume could not be read, no later bar; --check holds its two files; establishes no cause, changes nothing)
                findings_cases.mjs (the page smoke's findings suite: the Record view's replay over the committed findings)
                page_text_cases.mjs (the page smoke's page-text suite: the page's own words for vetoes, Method, Market, the stock detail, a known deal and the Record view, held to the record and the modules; `--only page-text`, or one part such as `page-text:market`)
                first_trade_cases.mjs (the page smoke's first-trade rehearsal: one journey from refused cash to a downloaded private backup; SCSTOCK_FIRST_TRADE_WRITE=1 writes tests/fixtures/first-trade/)
                private_results_parity.mjs (the page's own verdicts, from app-handoff.js run in a vm, on a corpus of private backups, written gzipped beside the rehearsal's backup; --check in CI)
                check_event_reviews.py (refuses an event registry whose unresolved entry's review has lapsed without a review_note, on the real New York date; CI runs it)
                positions_compare.py (a reader of a filled private positions file: each position's real R beside the model's R for the same ticket, never added; writes nothing but an explicit --json outside the repository)
                private_results.py (a reader of the owner's private backup: each reported result re-derived by the page's rules, traced to its publication by SHA-256 and frozen plan, the model's replay beside it and never added; writes nothing but an explicit --json)
deploy/         scheduler/ (the dispatcher's own Railway service: Dockerfile and railway.json; requirements-scheduler.txt beside the root)
.github/        evening.yml · intraday.yml · morning.yml · source-recovery.yml · issuer-evidence.yml · service-watch.yml · tests.yml · publish-dashboard.yml · secret-scan.yml · historical-input-proof.yml
```

Paper prices, one venue's prints, no slippage. Not investment advice.

## Continuity development

`python tools/backfill_history.py` builds `docs/history/` from existing published
v2 Git records without provider or chart-reader calls. The evening pipeline
maintains the catalog from final published bytes; it does not read local saves.
Initial backfill dates: September 11 and 14, 2026; September 11 has two distinct
publications. Both carry ATEC's original chart and neither carries VICR's.
`npm ci && npm run test:continuity` runs offline DOM/store regressions. This
is not browser or layout acceptance; use the existing Playwright checks too.
The original two records are gzip fixtures under `tests/fixtures/continuity/`,
and so is the public archive the check's recovery journey searches:
`history-2026-10-01.json.gz` is `docs/history/index.json` and the 11 September
record's context and ATEC/VICR rows exactly as published on 1 October, digests
intact, because the live `docs/history` keeps a 21-day window and stopped
carrying those originals on 2 October. The check never reads the checkout's
rolling archive, so its answer does not depend on the date.

The Record view's three frozen decisions (CRL and IQV from the 24 September
record, MSFT from the 25 September one) are read the same way. The study
`docs/historical-validation.json` names each case's archive context
(`<record>/record.json`) and evidence (`<record>/burst-<ticker>.json`) with a
SHA-256 for both, and `docs/historical-validation/` holds byte copies of those
files, written by `python tools/freeze_validation_cases.py` while the archive
still carried them (the 24 September record leaves the 21-day window with the
16 October publication, the 25 September one with the 19 October publication)
and held to the study's digests by `--check` in CI. The page's `studyJSON()` reads
a case from that directory alone, verifies the digest over the served bytes and
refuses a case file the study carries no digest for; it never asks the rolling
archive for a case, and the historical browser suite serves the case records'
archive directories 404 while it inspects one. The publication gate fetches the
five frozen files like every other public file. A later `freeze` writes only a
copy that is missing, from the archive or from git at the commit the case names
(the current study names none, so a copy lost after the prune would need that
commit added to the case first); an existing copy whose bytes are not the
study's is refused and left in place, as is a source whose bytes are not.

## Retained quality evidence

The dedicated manual `historical-input-proof.yml` workflow prepares encrypted
historical evidence under the [execution handoff](docs/input-truthfulness/2026-09-29-historical-execution.md).
The replacement real phase ran once as native 6 / attempt 1 (run 36815689950,
1 October) on the owner's dated readiness-v4 comment, after the repair merged;
no further dispatch is admitted. Its [result](docs/input-truthfulness/2026-10-02-historical-run6-result.md)
is below. Native 5 failed before checkout because its comment-ID
input contained leading spaces. The boundary now trims only edge ASCII spaces
and tabs, then passes the canonical numeric ID to the unchanged authorization
checks. Its failed attempt and consumed readiness remain immutable history.
The original workflow failed GitHub context
validation before any job; the execution handoff records its three preserved
failures and the narrowly reviewed recovery contract. Native run numbers are
not phase numbers. Normal CI checks the changed workflows with pinned actionlint.
The hosted synthetic rehearsal (run 36570997883, native 4 / attempt 1 / phase 1)
and exact source-pinned owner replay were accepted on PR #95. They used the
previous execution checkout; they did not exercise the later conversion-evidence
compaction or archive delivery changes. Guidance's separate execution release was
never posted; the guard does not require one, and the owner dispatched on readiness.
The prior 199 MiB stress failure is preserved. The explicit delivery-envelope
continuation uses a 250 MiB archive / 251 MiB ciphertext ceiling, preserving
the 2 GiB expanded limit and the selected codec. The complete central and stress
synthetic cases passed encryption, recovery of all 390 original members and exact
offline reproduction under that contract on PR #97. The
[dated delivery evidence](docs/input-truthfulness/2026-09-30-delivery-readiness-evidence/envelope-continuation/review.md)
binds those measurements to their actual source and hosted jobs. The versioned delivery relation names only that accepted transport
evidence and requires the new implementation's own capacity/runtime evidence, reviewed head,
current-main source equality and complete native run history. It does not reopen
the rehearsal slot. The personal-use decision on PR #95 ends licensing/outreach
work; the new owner-scope attestation records authorization, not provider consent.
Cost, entitlement, credential and technical safety checks remain separate.
Synthetic fit does not establish real-data fit or market correctness.

The [September 24/25 input and market-permission investigation](docs/input-truthfulness/2026-09-28-historical-input-proof.md)
reconciles retained aggregate RED decisions and the available stock observations.
Complete original final-population masks and full daily-bar inputs remain missing.
`tools/historical_input_proof.py` reproduces the retained-data analysis with sockets
blocked. The separate bounded acquisition tool defaults to offline validation;
live historical retrieval requires the frozen manifest and documented zero-cost,
private-storage authorization. Run 6 performed that one retrieval: all 97 queries
completed, using 289 of 400 request slots. Every intended stock returned
target-day and prior-day bars, and 263 symbols per session are partial. The
owner-decrypted, price-free summary reproduces RED on both sessions under both
later-eligibility policies. Under C the 10-session ratio stays below 1.0 across
the outer bounds over every unknown (0.92–0.95 and 0.88–0.90). Under D it is
exact (0.93 and 0.89). Strict establishment stays BLOCKED by six counted stocks'
missing monthly-test inputs, and the exact original population stays BLOCKED.
`tools/historical_reconcile.py` consumes only that tool's verified private cache,
keeps later observations separate and never publishes plans or reuses reader approval.
Its version-2 output stores lossless float-conversion evidence by selected-row
reference and field mask. Exact normalized decimal strings and raw-page lineage
remain retained; a bounded decoder reconstructs the legacy per-field facts.
The representation changes neither the float DataFrames nor market predicates.

The [22 September quality audit](docs/input-truthfulness/2026-09-22-retained-quality-audit.md)
distinguishes input reliability, mechanical/final grades and model outcomes.
Future real publications append compact immutable facts under
`docs/quality-ledger/v1/`, named by the original publication SHA-256. Original
rules, denominators, UNKNOWN fields, complete exception membership, grading
facts and per-plan scorecard observations survive recovery expiry. This ledger
does not participate in trading decisions or change the existing reliability row.
It retains no raw bars or personal execution. Existing Git persistence includes
it; no new workflow or dashboard is required.

Each deterministic gzip entry is limited to 8 MiB expanded; the archive is
limited to 128 MiB compressed and 4,096 entries, without eviction or historical
rewrites. The run log states each retained entry (expanded) and the archive
against these bounds and warns past 80% of any. Capture failures leave
decisions/publication/exit codes unchanged and emit
`quality_ledger_capture_failed`, RunReport status and an attempted-capture
`quality_ledger_status` output; when a bound refused the capture, the run
log's `quality_ledger_capture_failed` line names the sizes and the bound.
Interrupted, failed or skipped runs can lack an
entry; ledger membership is not proof that every attempted run was captured.
No historical backfill is performed. Capacity and future schema changes require
an explicit retention decision, preserving old entries and their rule basis.
