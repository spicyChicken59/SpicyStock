# The signal-outcome study over nineteen publications: the confirmatory phase begins

**What was run.** The frozen study, `tools/signal_outcomes.py` at the code PR
#100 merged to `main` as `788aa092`, re-run on 6 October 2026 in the sandbox
over nineteen publications: the seventeen the frozen
[spec](2026-10-02-signal-outcomes-spec.json) names and the two published since
-- run 2026-10-02 (`58e0f384`, record blob `bb2edad5…`) and run 2026-10-05
(`178956b4`, blob `1064e69b…`). The spec it read,
[`2026-10-06-signal-outcomes-spec-extended.json`](2026-10-06-signal-outcomes-spec-extended.json)
(SHA-256 `58b6d84ef97a…`), differs from the frozen file (SHA-256
`d93ad856b69a…`) by exactly the two appended publication entries: `diff` shows
ten added lines and nothing removed, so every rule, threshold, estimand and the
freeze date are the frozen ones. The frozen file is untouched. Python 3.12,
exit 0, 22 seconds, no provider, model or network call. The summary is
[verbatim](2026-10-06-signal-outcomes-confirmatory-evidence/summary.txt) and
every row is in
[`signal-outcomes.json.gz`](2026-10-06-signal-outcomes-confirmatory-evidence/signal-outcomes.json.gz)
(uncompressed SHA-256 `be195dc04b21…`).

Both new nights were RED (10-session ratios 0.91 and 0.97) with no ticket, so
their signals enter as counterfactual tickets like every night before them,
and as **confirmatory** ones: their sessions follow the freeze date of
1 October.

## What changed, and what is new

| | First run, 2 Oct | This run, 6 Oct |
| --- | ---: | ---: |
| Publications / first-of-session | 17 / 15 | 19 / 17 |
| Bars / symbols | 53,452 / 2,053 | 60,964 / 2,221 |
| Rows | 6,064 | 7,128 |
| Nights with a settled ticket | 14 | 16 |
| Exploratory admitted: settled | 202 | 267 |
| Exploratory admitted: wins / losses / even | 37 / 159 / 6 | 50 / 208 / 9 |
| Exploratory admitted: mean R, median R | −0.235, −0.47 | −0.189, −0.40 |
| Exploratory admitted: mean of night means, 95% CI | −0.291 [−0.486, −0.109] | −0.237 [−0.431, −0.049] |

The exploratory numbers moved because the 1 October signals, all 579 pending
on 2 October, now have two sessions of bars: the night's 50 settled admitted
tickets are 0 wins, 47 losses and 3 even, mean −0.364R, and its 31 open ones
are still walking. Every exploratory stratum is still negative, and the
admitted stratum still loses least.

**Confirmatory admitted stratum: 132 rows**, 45 from 2 October and 87 from
5 October. Five are settled, all at −1.00R: RRGB, STEM, TSQ, ALMR and AWK, each
a 2 October signal stopped on 5 October, its first session. Fifteen are open,
81 pending (every 5 October ticket, whose first session is 6 October), 17
uncertain, 4 not filled, 10 without a ticket. Nothing here is readable under
the scorecard's twenty-settled minimum, and nothing is read.

**The reader's own admissions** -- the live policy's A or A+ acceptances --
are two rows, both DAC: the 1 October signal, whose fill is uncertain on daily
bars, and the 2 October signal, filled on 5 October and holding.

## How to read it

Nothing confirmatory is readable yet. The 2 October tickets reach their fifth
session on 9 October and the 5 October ones on 12 October; the 1 October
exploratory tickets settle on 8 October. The first confirmatory number worth a
sentence arrives with the 9 October publication.

The method of extension is the one this report uses: the frozen spec's rules
stay byte-identical, publications are appended as they are published, each
extension is committed with its own hash and its diff against the frozen file,
and the code stays the merged one. A change to anything but the publication
list is a new spec with a new freeze.
