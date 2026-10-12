# The evidence review before any strategy change is promoted — 12 October 2026

The last acceptance line of #109 asks for "an explicit evidence review before
promoting strategy changes". This is it: a reading over the evidence this
repository has committed, written by `python tools/evidence_review.py` into
[`review.json`](2026-10-12-evidence-review-evidence/review.json) and
[`review.md`](2026-10-12-evidence-review-evidence/review.md) beside this file,
with `--check` holding both as `make_fixture.py --check` holds the fixtures, and
`tests/test_evidence_review.py` re-deriving every number from the files it
names. It reads; it decides nothing. No threshold, rule, record or account is
changed by it, and the verdicts below are readings of evidence sufficiency
under criteria the tool states and archives, never a recommendation to trade.

## What was read

| source | what it is | through |
|---|---|---|
| the signal-outcome study ([2 Oct](2026-10-02-signal-outcomes.md), [6 Oct](2026-10-06-signal-outcomes-confirmatory.md)) | every burst of nineteen publications ticketed without reader, gate or slot and walked on the records' own bars; every night RED | newest session 2026-10-05, frozen through 2026-10-01 |
| the owner's backtest ([6 Oct](2026-10-06-backtest-results.md)) | 158 sessions of the run-6 archive through the run's own stages, reader not run, pasted as two summaries | 2026-09-25 |
| the candidate funnel ([11 Oct](2026-10-11-candidate-funnel.md)) | where every discovered candidate of 26 publications stopped | 21 sessions to 2026-10-09 |
| the whole-share feasibility reading ([11 Oct](2026-10-11-whole-share-feasibility.md)) | every archived candidate sized again at the archived account and at $2,000 | the same 26 publications |
| the registered stop-width research (`docs/stop-research.json`, `docs/research-outcomes.json`) | the prospective 4% → 5% anticipation cohort and its frozen journal | applicable session 2026-10-12 |

Each file's SHA-256 is in `review.json`; a findings file built over a
different study, a journal that follows another cohort, or a study whose
summary is not its own rows is refused rather than read.

## The criteria

A rate is read at 20 settled tickets or more, the record's own
`SCORECARD_MIN_PLANS`; below it a population is a count. A population
establishes a **negative** or **positive** sign when the 95% night-bootstrap
interval of its mean of night means lies wholly below or above zero, is
**unresolved** when the interval straddles zero or no interval can be drawn (the
owner's pasted summaries carry counts and sums, no rows), and **unreadable**
under twenty settled. A change is **supported** when every direct source
establishes a positive sign and every evaluation period agrees;
**not_supported** when a direct source establishes a negative sign and none a
positive one; **mixed** when both signs are established; **insufficient** when
no direct source establishes a sign. A source whose population is a
neighbouring one (another regime, mixed regimes, the reader not run) is shown
as *adjacent* and never counted.

## What the evidence says

**The study's admitted stratum, exploratory phase**: 267 settled, 50 wins,
208 losses, 9 even; mean -0.189R, median -0.40R; the mean of night means
-0.237R with a 95% night-bootstrap interval of [-0.431, -0.049]. Split by
calendar month the September nights are negative on their interval and the one
October night is a single night; split by halves of its nights the first eight
straddle zero ([-0.400, +0.041]) and the last seven are negative; split by
mechanical grade the 261 A-grade tickets are negative and the six A+ are a
count. Every stratum lost at every cost assumption the spec names. The
cumulative-R path of the admitted stratum's 272 settled tickets, in the study's
own order, ends at -55.56R with a deepest fall of 62.31R from 11 September to
2 October; the night-means path falls 5.05R over 16 nights. The confirmatory
phase is five settled tickets, all -1.00R on their first session, and a count.

**The owner's backtest**: the production policy (YELLOW A+, reader not run)
wrote 99 tickets over 158 sessions; 44 settled, 16 wins and 27 losses, net
+3.72R, mean +0.085R, median -0.09R, SPY +0.37% over the same windows. The
counterfactual without the market gate: 69 settled, +17.40R; its RED nights 25
settled, +1.14R; its A grade 23 settled, +10.22R. No per-row file was pasted,
so no interval can be drawn from any of these: each is unresolved under the
criteria, a point with no dispersion.

**The funnel and the feasibility reading** say where the live policy's
candidates stopped and what the account can buy: 8,618 of 11,513 at the
market, 2,887 at the YELLOW band's A+ gate, 8 potentially usable, 0 tickets;
under YELLOW at $2,000, 5 of 40 in-band names size to a whole share.

## The ledger

| change | verdict | why |
|---|---|---|
| Admit mechanical A under YELLOW beside A+ | **insufficient** | no direct source: the study's A-grade tickets are RED-night tickets (negative), the backtest's A grade is not split by regime (23 settled, no interval); 2,887 YELLOW candidates stopped at the band unreviewed |
| Trade on RED nights | **not_supported** | the study's RED nights establish a negative sign at 267 and at 1,741 settled; the backtest's RED counterfactual (25 settled, +1.14R) has no interval |
| Widen the anticipation stop cap to 5% | **insufficient** | the registered journal has 0 resolved rows; its first can exist five sessions after 12 October |
| Write an A+ ticket on the checklist alone when the reader refuses | **insufficient** | the backtest's production policy (44 settled, +0.085R) has no interval; the live policy's own reader-accepted admissions have 0 settled; the retained HAE reply is the case this would admit |
| Raise the base risk or the account | **insufficient** | a sizing change: the ceiling decides which names can be bought, not whether they win; no outcome evidence exists at either size |

No change earns **supported** today, and nothing is promoted by this file.

## The retained HAE reply

#109 named one reply to keep rejected: HAE on 8 October, a mechanical A+ (10 of
10) whose reply attempted C/5.5 with citations outside the authority contract.
Both publications of that session carried it (the first at $10,000 scored it
B/6.5, the corrected at $2,000 C/5.5), and both replies cited `burst.gap_pct`,
`burst.bar_range_pct` and their kin: measurements the model read, none a path
under `checks.<letter>` of the reader-evidence contract. The rows are frozen
under `tests/fixtures/grading/reader-hae/` with their publications' digests,
and `tests/test_reader_hae_retained.py` parses the retained text through the
grader's own parser, replays it into the recorded fallback through the scripted
transport, and holds the planner to no ticket under synthetic YELLOW and GREEN
regimes. Its one control copies the same two findings' citations from the row's
own reader evidence and shows them admissible: the refusal is the paths, not a
corrected grade for HAE.

## What this does not establish

- Every study night was RED: its tickets are ones the market gate refused,
  walked on daily bars with the reader not consulted. It says nothing about a
  YELLOW or GREEN night.
- The backtest's universe is the archive's later membership, its fills are
  daily-bar, its reader not run, and it was pasted as a summary.
- GREEN has never been published, nor observed in 158 backtest sessions.
- The registered research is a design until its rows resolve.
- A verdict reads evidence sufficiency under the criteria above. It is not a
  recommendation, and no change is promoted by this review. Re-run the tool as
  publications and the journal mature; a change in any verdict is a change in
  these two files, which `--check` will show.
