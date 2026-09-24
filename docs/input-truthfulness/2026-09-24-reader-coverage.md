# Reader coverage and burst actionability

Starting main: `456edb836cc42c908c50330b723dbfd97be5d506` (Guidance merge of #89).
The remote main and zero open PRs were checked before branching. The exact
submitted head and CI results are pinned in the one implementation PR.

## Reproduced defect

Normal run `35938584554` evaluated September 23 on execution checkout
`9357a2791b8440af4b397dec57dee94a14551a0b`, publishing commit
`6ff292d7971570d809a2bdd4d476a1f88d3c4234`.

The retained file has 18 mechanical A, 77 B, 35 C and 152 skip, with zero A+.
The unchanged twelve-read budget selected the top twelve mechanical As. Eleven
accepted replies downgraded: MET/DOCU/MEOH/RDVT/IEX to C and
CHDN/CMI/DCO/IR/LTH/MSM to skip. VEEV fell back after
`src.ReaderAuthorityError: evidence outside criterion authority`; its exact
rejected response remains retained. NDSN/OPY/RRR/STE/TTE/WLY had no reader row.

The final retained regression executed on an isolated, untouched starting main
produces **2 failures, 4 passing controls**. Under synthetic GREEN, all six
unreviewed mechanical As become plan-eligible, and VEEV also gets a plan.
This is the same retained candidate state, with only regime permission changed.
The corrected regression passes; low-level plan controls demonstrate that the
new coverage gate, rather than an unrelated sizing refusal, blocks the six.
An unrelated report-heading mutation leaves the retained regression passing.

## Prospective policy

| Reader state | Grade retained | Final burst planning |
| --- | --- | --- |
| `accepted` | Down-only reader-reviewed final grade | Existing grade, veto, market, stop, sizing and budget rules still apply |
| `fallback` | Mechanical grade | Research only; selected review yielded no accepted judgement |
| `not_selected_budget` | Mechanical grade | Research only; no review selected within the call budget |
| `unknown` | Available recorded grade | Absence of coverage does not grant permission |

New records archive `pipeline.reader_policy = accepted_required_v1` and a
`reader_coverage` field on every reaction candidate and its decision receipt.
The final planner requires the accepted reader result itself, not merely a
coverage label. The receipt verifies coverage and independently refuses a plan
without an accepted reader result. Existing historical receipts retain their
archived policy and are never rewritten.

GREEN still admits final A+/A, YELLOW final A+ only, and RED no new burst plans.
The same default account and existing price/risk rules apply. A private
pre-review plan pass continues to supply exactly the same stop to the reader's
chart. Its outputs are discarded before final planning. It cannot publish a
ticket; the final pass always applies the reader requirement. Anticipation
watchlists retain their existing measured, ungraded contract.

The website distinguishes accepted review, fallback, budget exclusions and
unknown legacy coverage in detail, comparison, provenance and saved limitations.
Cards flag missing coverage; accepted review is named in detail without adding
a redundant card row that pushes the first stock below the desktop viewport.
Missing coverage is neutral and explicitly not a measured setup
failure. Mechanical and reviewed final grades are named separately. The
prospective no-ticket cover and next action explain missing review rather than
claiming that mechanical A candidates failed quality. No new UI workflow or
design-system change is introduced.

## Verification and preservation

- 47 focused coverage tests, including the retained failing-before regression,
  regime/reader combinations, forged-label refusal, offline pipeline budget,
  reader chart-stop continuity, publication integrity and cover wording.
- Normal Python suite: 1,513 tests. It includes reader authority, compatibility,
  grader, pipeline, planning, reporting and provenance tests with sockets blocked.
- All twelve synthetic pipeline fixtures regenerated; accepted-reader plans,
  candidate inputs, mechanical checks, grades and reader results are unchanged.
  Four fallback burst plans disappear only from the synthetic degraded fixture.
- 127 continuity checks and 182 chart checks passed. The first continuity run
  raced its short asynchronous archive wait while other suites were running;
  an unchanged rerun passed. No application change was made for that timing.
- The focused retained browser journey passed 227 checks at 1440 and 390 px,
  both themes, comparison and keyboard disclosure; screenshots inspected.
  Full page gate and final-head CI results are recorded in the PR. The quota
  regression now places its limit between measured with-chart/without-chart
  payload sizes and verifies exact snapshot preservation; the added coverage
  receipt crossed the former incidental 4,000-character test limit.
- All 6,797 protected files from starting main are byte-identical, including
  source frames, raw reader responses, accepted findings, history, data/picks,
  quality ledger, design system, knowledge and workflows. All 46 synthetic
  candidate input/quality/reader projections match the base.
- Original-code replay: September 22 passes 513 mechanical assessments and
  all 518 receipts; September 23 passes 282 assessments and all 287 receipts.
  Both have no replay breaks or missing evidence. September 23 remains RED,
  with ratio 0.85 and no published burst plan or ticket.

Publication SHA-256 values:

- September 22: `507127d7a6e07f2d1120290c96cd717e1ef72529be8053218d317bb9b9ee3c36`
- September 23: `30a3d44a10e789cf2cc66369476acb82d8943a477335b0c94d2a149ce644b240`

Runtime: Python 3.12.14, pandas 2.2.3, NumPy 2.3.5; Node 24.19.0,
Playwright 1.56.1. README and `.env.example` reviewed; no configuration change.
No production rerun, provider/model call, schedule/secret/setting change,
manual publication, account change, scorecard-history mutation, strategy tuning,
sibling modification or merge. Guidance owns independent review and merge.
