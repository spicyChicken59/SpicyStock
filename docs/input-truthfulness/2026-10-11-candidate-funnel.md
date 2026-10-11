# The candidate funnel over every retained publication — 11 October 2026

A reading, not a check and not a rule. `tools/candidate_funnel.py --history
--ref origin/main --limit 64` ran `src/funnel.py`'s `build()` -- the function
the evening run now writes into every record as `funnel` -- over every commit
on `main` that changed `docs/data.json`, in this checkout, with no provider,
model or network call. The table it printed is beside this file
([history.md](2026-10-11-candidate-funnel-evidence/history.md)); the readings,
the commits it skipped and the totals are in
[history.json](2026-10-11-candidate-funnel-evidence/history.json), each reading
bound to the blob `docs/data.json` had at its commit. Nothing below is a
judgement of any setup, a measurement of edge, or an entry.

## What was read

Sixty-four commits changed the record. Thirty-eight of them are the first
build's schema-1 records or committed fixtures and are named as skipped, never
read. The other **26 publications cover 21 sessions, 11 September to
9 October 2026**: 21 publications RED and 5 YELLOW; GREEN has never been
published. Three sessions were published more than once (11 and 21 September on
later bars, 8 and 9 October under corrected rules), and every revision is its
own row.

None of these publications was made under rules that write the block, so every
one is read for what it recorded: the regime and its archived admitted band,
the mechanical grade, the veto, the reader's state and the plan's own
allocation or cut. A field a record lacks is `unknown`; none was.

## What the funnel says

| | reaction candidates | listed anticipation setups |
|---|---:|---:|
| discovered / listed | 11,513 | 128 |
| stopped at the market gate (RED admits no new longs) | 8,618 | 105 |
| stopped at the mechanical grade (YELLOW admits A+ only) | 2,887 | — |
| potentially usable (grade in the admitted band, no veto) | 8 | — |
| review refused by reader authority | 2 | — |
| review lowered the grade below the band | 6 | — |
| known corporate event | 0 | 6 |
| ticket withheld: stop rule at the limit | 0 | 13 |
| no whole share | 0 | 1 |
| tickets | **0** | 3 |

Read it as:

- On the 21 RED publications every one of the 8,618 reaction candidates and
  all 105 listed setups stopped at the market gate. No later gate was reached,
  so nothing below the market line is observed on those nights: the funnel
  says where they stopped, not what they would have done.
- On the 5 YELLOW publications (8 and 9 October) the band is A+ alone. The
  8 October record carried 4 mechanical A+ among 730 discovered; all four were
  reviewed, one refused by reader authority (HAE) and three lowered below the
  band, so the 8 potentially usable candidates across the two 8 October
  publications ended at the review and none reached a plan. The three
  9 October publications carried no mechanical A+ at all (53 A, 112 B, 89 C,
  225 skip), so all 479 stopped at the grade gate before any review could
  matter, as the `account_feasible_first_research_v1` receipt already said.
- The three anticipation tickets are the ones the record published: MG and SN
  on the first 8 October publication under the $10,000 account, and ZIM on the
  first 9 October publication, each superseded by the corrected publication
  that followed (MG and ZIM under their cash-acquisition sources, SN at the
  stop rule). The funnel reads each publication as it was, so the superseded
  tickets stay in their own rows.
- Zero reaction tickets, in 26 publications. The gates that cost them are the
  market (RED) and, on YELLOW nights, the A+ band and the reader. Entry
  geometry, whole-share sizing and the combined allocation have refused no
  reaction candidate yet, because no reaction candidate has reached them.

## What this does not establish

The funnel is accounting over the record's own gates. It does not say whether
a candidate stopped at a gate would have made money, whether the gate was
right, or how many of the 2,887 grade-stopped names under YELLOW would have
passed review had they been reviewed. The pre-review preview stages
(`preview_event`, `preview_geometry`, `preview_sizing`) appear only in
publications made under the selection policy and are zero in every retained
one because the grade gate came first. Nothing here changes a threshold, a
rule or a record.
