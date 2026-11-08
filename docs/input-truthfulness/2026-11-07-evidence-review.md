# The evidence review before any strategy change is promoted — 7 November 2026

The second dated evidence review, superseding
[the 12 October one](2026-10-12-evidence-review.md), which stays frozen as
written. It is written by `python tools/evidence_review.py` into
[`review.json`](2026-11-07-evidence-review-evidence/review.json) and
[`review.md`](2026-11-07-evidence-review-evidence/review.md) beside this file,
with `--check` holding both as `make_fixture.py --check` holds the fixtures, and
`tests/test_evidence_review.py` re-deriving every number from the files it
names. It reads; it decides nothing. No threshold, rule, record or account is
changed by it, and the verdicts below are readings of evidence sufficiency
under criteria the tool states and archives, never a recommendation to trade.
Two of the six changes it reads were promoted on 4 November, by the owner's
decision and without an outcome reading; this is that reading, after the fact.

## What was read

| source | what it is | through |
|---|---|---|
| the signal-outcome study ([7 Nov re-read](2026-11-07-signal-outcomes-confirmatory.md)) | every burst of forty-seven publications ticketed without reader, gate or slot and walked on the records' own bars; 32 RED nights and 9 YELLOW | newest session 2026-11-06, frozen through 2026-10-01 |
| the owner's backtest ([6 Oct](2026-10-06-backtest-results.md)) | 158 sessions of the run-6 archive through the run's own stages, reader not run, pasted as two summaries | 2026-09-25 |
| the candidate funnel ([reading](2026-11-07-candidate-funnel-evidence/history.md)) | where every discovered candidate of 47 publications stopped, the discovery route among the stages since 4 November | 41 sessions to 2026-11-06 |
| the whole-share feasibility reading ([archived accounts](2026-11-07-whole-share-feasibility-evidence/history-archived.md), [$30,000](2026-11-07-whole-share-feasibility-evidence/history-account-30000.md)) | every archived candidate sized again at the archived account and at $30,000 / 0.5% | the same 47 publications |
| the registered stop-width research ([retained cohort](2026-11-07-evidence-review-evidence/inputs/stop-research.json), [retained journal](2026-11-07-evidence-review-evidence/inputs/research-outcomes.json)) | exact copies of the prospective 4% → 5% anticipation cohort and journal as commit `af21693ce5cd5e0df91fb23ac58972ee542af5ed` carried them | the registered period ended 2026-11-06 |
| the live policy's own scorecard ([retained extract](2026-11-07-evidence-review-evidence/inputs/scorecard.json)) | the 6 November publication's model scorecard, account and open plans, extracted from `docs/data.json` at the same commit | 2026-11-06 |
| the discovery admission ([retained join](2026-11-07-evidence-review-evidence/inputs/admission-join.json.gz)) | every study row joined to `src/admission.py`'s block, re-derived from each publication's own rows off git | the study's 47 publications |

Each file's SHA-256 is in `review.json`; the retained inputs name their
original commit and paths, and their exact bytes are checked before reading.
The rolling findings file, companions and record can advance without revising
this dated review. A findings file built over a different study, a journal
that follows another cohort, a join that misses a study row or disagrees with
its scan, an extract of another record, or a study whose summary is not its
own rows is refused rather than read. The funnel and feasibility readings were
written by their own tools pinned to that commit (`--ref af21693c…`).

## The criteria

Unchanged from 12 October, with one scope added. A rate is read at 20 settled
tickets or more, the record's own `SCORECARD_MIN_PLANS`; below it a population
is a count. A population establishes a **negative** or **positive** sign when
the 95% night-bootstrap interval of its mean of night means lies wholly below
or above zero, is **unresolved** when the interval straddles zero or no
interval can be drawn (the owner's pasted summaries and the scorecard's counts
carry no rows; the study's interval needs two nights with settled tickets, and
its night count is printed beside it), and **unreadable** under twenty settled.
A change is **supported** when every direct source establishes a positive sign
and every evaluation period agrees; **not_supported** when a direct source
establishes a negative sign and none a positive one; **mixed** when both signs
are established; **insufficient** when no direct source establishes a sign. A
source whose population is a neighbouring one is shown as *adjacent*; the
population a change stops trading is shown as *removed*; neither is counted.

## What the evidence says

**The study's admitted stratum** (mechanical A or A+ without a veto): the
exploratory phase, every night RED, is 303 settled, 73 wins, 221 losses, 9
even; mean -0.123R, median -0.33R; the mean of night means -0.189R with a 95%
night-bootstrap interval of [-0.354, -0.022], negative as it was on 12 October
at 267 settled. The confirmatory phase, signalled after the freeze, is 575
settled over 24 nights with settled tickets: mean -0.218R, the mean of night
means -0.003R, interval [-0.232, +0.220], unresolved. Split by regime, its 17
RED nights are 270 settled at +0.015R, interval [-0.103, +0.430], and its 9
YELLOW nights 305 settled at -0.424R, interval [-0.617, +0.095]: both
unresolved. The confirmatory mechanical A are 550 settled at -0.205R, interval
[-0.203, +0.244]; the confirmatory mechanical A+ 25 settled at -0.498R,
interval [-1.378, -0.017] over 10 nights, negative, 18 of them on YELLOW nights
and 7 on RED. Split by calendar month, September (14 nights) is negative,
October (22 nights, 513 settled, +0.005R) straddles zero, and November's three
settled nights (143 settled, 2 wins) read negative on an interval of three
nights, one over the two the criteria require. The cumulative-R path of the
admitted stratum's 878 settled tickets ends at -162.34R with a deepest fall of
169.09R from 11 September to 4 November; the night-means path falls 3.74R over
39 nights. Every stratum lost at every cost assumption the spec names.

**The 4 November night** is the stratum's largest loss and sits in every
confirmatory figure above: the first night on which the live policy published
burst tickets, every admitted ticket that settled stopped into the 5 November
alarm, 112 of the YELLOW A tickets' 287 settled at -1.029R a ticket. Without it
the other eight YELLOW nights' 175 settled read -0.039R a ticket, interval
[-0.442, +0.223], still unresolved.

**The discovery admission**, re-derived over every publication: of the
study's 20676 rows, 6458 came through the 4% route, 991 through a dollar day
with both expansion checks, and 13227 through the dollar scan alone without
one, which the rule in force since 4 November stops. Inside the admitted
stratum the kept population is 268 settled at -0.356R a ticket, mean of night
means -0.088R, interval [-0.335, +0.171]; the stopped population 610 settled at
-0.110R, interval [-0.218, +0.086]; on YELLOW nights 131 settled at -0.667R
against 174 at -0.241R; on RED nights 137 at -0.058R against 436 at -0.058R.
Every interval straddles zero. The kept population's worse mean a ticket is
the 4 November burst-route tickets' doing; the rule stops a name before its
chart is read, so the reader's effect on the kept names is NOT RUN and these
rows are not the rule's own population.

**The live policy's own scorecard**, the first the record has had with real
burst plans: the 6 November publication's 13 model plans over its window,
5 settled (2 wins, 3 losses, +0.43R in sum), 7 not filled, 1 uncertain, under
its floor of 20. Its open plans are ESRT (anticipation, not filled) and HQY,
RCBC and VIK (burst, each stopped). The record's R is the fill against the
planned risk, not a fixed -1R, and it is not split by account.

**The owner's backtest** is unchanged: the production policy (YELLOW A+,
reader not run) 44 settled, +0.085R, no interval; the counterfactual without
the gate 69 settled, +17.40R; its RED nights 25 settled, +1.14R; its A grade 23
settled, +10.22R. Unresolved, each a point with no dispersion.

**The funnel and the feasibility reading**: 23480 reaction candidates over 47
publications, 15770 stopped at the market, 7666 at the YELLOW band's A+ gate,
3 at the discovery route (every one on 4 November, none read), 13 at the
preview's sizing, 41 potentially usable, 7 refused by reader authority, 18
lowered, 3 tickets; 196 anticipation setups listed, 10 tickets. Under YELLOW,
54 of 97 in-band names size to a whole share at the archived accounts and
92 of 97 at $30,000.

**The registered research** ended with nothing to read: 70 rows over 20
cohorts, 7 eligible, 6 not filled, 1 uncertain, 0 resolved; the cohort for
9 November reads outside its period, and the $30,000 account was refused
inside it, so the last two sessions carried no cohort.

## The ledger

| change | status | verdict | why |
|---|---|---|---|
| Admit mechanical A under YELLOW beside A+ | floated | **insufficient** | the direct population exists now (287 settled YELLOW A, 123 under the admission rule) and straddles zero either way; the one night that dominates it is 4 November; no YELLOW night with a reviewed A name has been published |
| Trade on RED nights | floated | **not_supported** | the exploratory RED nights still establish a negative sign (303 settled); the confirmatory RED nights (270) and the two phases pooled (573) straddle zero; the backtest's RED counterfactual has no interval |
| Widen the anticipation stop cap to 5% | floated; period ended | **insufficient** | the registered journal has 0 resolved rows of 70; the experiment ended with no result, and a new registration would be a new experiment |
| Write an A+ ticket on the checklist alone when the reader refuses | floated | **insufficient** | the rows the change would admit are 11 settled, a count; the backtest's production policy (44 settled, +0.085R) has no interval; the live policy's own admissions are 5 settled, all losses, a count |
| Raise the base risk or the account | promoted in part (the $30,000 account from 4 November) | **insufficient** | one night carries every settled $30,000 ticket (119), so no interval exists; the scorecard's 5 settled are a count; the ceiling decides which names can be bought, not whether they win |
| Admit a dollar-only discovery only on a range-expansion, higher-volume day | promoted 4 November | **insufficient** | the kept population straddles zero on every split and reads worse a ticket than the stopped one (-0.356R over 268 against -0.110R over 610); the gap closes most without 2026-11-04 (-0.052R over 186 against -0.053R over 573); the reader's effect on the kept names is NOT RUN |

No change earns **supported** in this 7 November review, and nothing is
promoted by this file. Two changes were promoted by the owner on 4 November
and are read here after the fact; neither has evidence that would have
supported it under these criteria, and neither has evidence against it.

## What moved since 12 October

The exploratory sign held as the study grew. Three things are new. The
confirmatory phase is readable (575 settled over 24 nights) and straddles zero
by a wide margin, its RED nights near +0.015R a ticket and its YELLOW nights,
the first the study has carried, at -0.424R with one night holding 119 of
their 305 settled tickets. The live policy wrote its first burst tickets, and the
scorecard, 5 settled, cannot yet read them as a rate. And the registered
research, the one prospective experiment, closed with no resolved row.

## What this does not establish

- The study tickets every burst without the reader, the gate or a slot cap
  and walks it on daily bars; its exploratory nights were all RED and every
  next close was public before the spec froze. Its confirmatory nights are
  RED and YELLOW, and nothing here speaks to a GREEN night, which has never
  been published nor observed in 158 backtest sessions.
- The admission join re-derives the rule over rows the study never applied it
  to; the reader's effect on the kept names is NOT RUN.
- The backtest's universe is the archive's later membership, its fills are
  daily-bar, its reader not run, and it was pasted as a summary.
- The live scorecard is the record's own replay of the plans it issued, under
  its own floor; it is a count, never an edge, and the owner's own trades are
  his and are not in it.
- A verdict reads evidence sufficiency under the criteria above. It is not a
  recommendation, and no change is promoted by this review. Re-running the
  tool reproduces these frozen 7 November inputs. As publications mature,
  review the later evidence in a separately dated report; preserve this
  review and its historical verdicts.
