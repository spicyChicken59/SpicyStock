# PR #92 — pending evaluation and planning evidence correction

This is the focused response to Guidance review `5338408980`, on the existing
`fix/historical-validation-usable-plans` branch. No merge is authorized here.

Reviewed head: `2e4d0eca42d4df099069d4ca1d791402d58825d5`.
Re-resolved base/main: `8be007f68deaa417b85a512d2e16a37899d27011`.
Corrected implementation commit: `c0e9d9b445a18782e39d5aa2f50b292ee08acca1`.
The subsequent handoff commit changes documentation/evidence only; PR #92 records
its exact submitted head and the normal CI results for that head.

## Two corrections

`evaluationExplanation()` uses the existing `status()`, `calendarOf()` and clock
and the loaded publication timestamp. The archived completion buffer is a
market-data boundary, not a run or publication completion time. September 28
remains the outstanding evaluation at 20:15 UTC and 21:00 UTC when the loaded
record is September 25. The copy distinguishes an upcoming/in-progress market
session, a just-closed session inside the buffer, an unpublished evening
evaluation, stale/missing publication, an explicit failed run, an arrived record,
and missing/malformed/out-of-range calendar or publication timing evidence.
Delayed/missing/failed causes are possibilities unless the record explicitly
reports failure. No cron, exact future publication promise or workflow changes.

`reclock()` updates just the explanation's text node, including when the close
changes the explanation without changing action availability. Focus, visibility,
page restoration and the existing bounded tick use that path. A publication
refresh preserves the wait disclosure through the existing `repaint()` helper.
Same-byte refresh leaves charts and focus intact; arrival of the genuine September
25 record after the genuine September 24 record preserves the selected stock and
refresh focus while updating the publication explanation.

`planningWaitReasons()` reads the published plan, receipt, gate, policy and cash
cut. A known early-gate skip requires the explicit unattempted receipt and a
matching recorded gate; the reader skip additionally requires the archived
accepted-review policy. A recorded error is a failure, including `gate.reason = plan_error` without
detail text; recorded inputs without
a recoverable outcome mean an attempted but unknown outcome. Legacy/missing
stage evidence stays unknown. Produced ineligible/withheld plans, recorded whole
shares and allocation cuts remain distinguishable. Other independent market,
quality and review blockers remain visible. No new order levels or copy controls
are created, and no historical policy is upgraded by inference from null.

## Normal gate and frozen evidence

The original 85 historical/save/isolation assertions now live in
`tools/historical_cases.mjs`, called by the normal unfiltered `page_smoke.mjs`.
The existing `historical_journeys.mjs` command delegates to that same suite and
retains its isolated source-control options. The new 721-check
`wait_explanation_cases.mjs` also runs in the normal page gate. No workflow,
schedule, dependency declaration, detector or required-check configuration changed.

Both suites load the byte-pinned genuine September 25 publication from
`tests/fixtures/wait-explanations/2026-09-25.json.gz`, not moving `docs/data.json`.
Its uncompressed SHA-256 is
`37255a5457472d47452ea326e6b6b84cec2d6bd1da07ab391e173daf73a62ce5`;
its reviewed Git blob is `6fce465edd51badead8ad0c38b111819ee69c884`.
Arrival also uses the existing frozen September 24 publication. Holiday controls
project the publication date over the unchanged archived XNYS schedule, which
omits September 7 and includes September 8; they are synthetic date controls,
not claimed historical publications. Repeated stage/clock renders narrow the
candidate list and omit unrelated saved observations for speed. The full genuine
publication is separately exercised at the failure clock in every viewport/theme
and in the retained screenshots.

Planner error, attempted/unknown outcome, absent evidence, known reader skip,
unknown/legacy reader policy and overlapping blocker controls are explicitly
synthetic. Structural refusal, slot refusal and eligible-plan controls use the
existing producer-generated synthetic fixture. None is a genuine historical
ticket or a new observed planner failure. Assertions verify absent levels/copy
controls and preserve the ordinary eligible fixture's exact published plan.

## Executed evidence

| Check | Result |
| --- | --- |
| Exact reviewed application, final 721 assertions | FAIL — 276 intended explanation/continuity failures; 445 controls PASS |
| Corrected explanations and controls | PASS — 721/721 |
| Prior correction with detail-free `plan_error` | FAIL — 6/721; other 715 controls PASS |
| Restore only old evaluation selector | FAIL — 186/721; planning and independent controls PASS |
| Restore only old planning explanation | FAIL — 84/721; evaluation and independent controls PASS |
| Unrelated document-title control | PASS — 721/721 |
| Shared historical journey, including standalone entry point | PASS — 85/85 |
| Python suite, JUnit-confirmed | PASS — 1,541/1,541 |
| Producer fixture currency | PASS — 12 |
| DOM/store continuity | PASS — 127 |
| Chart/component browser checks | PASS — 378 |
| First full page run, before capture isolation | FAIL — 9,190/9,191; the screenshot-dependent map focus assertion described below |
| Corrected map capture sequence | PASS — 94/94; all original assertions retained |
| Existing historical/source/design/workflow bytes | PASS — 8,822 unchanged files |
| Local committed-range secret scan | PASS — no leaks |
| Exact submitted-head normal PR CI | NOT RUN at this checkpoint's creation — final results and links are recorded in PR #92 |

Commands, using the repository root and an external evidence directory:

```bash
node tools/page_smoke.mjs --shots "$EVIDENCE/full-page"
node tools/historical_journeys.mjs --output "$EVIDENCE/historical"
node tools/wait_explanation_controls.mjs --output "$EVIDENCE/controls"
node tools/continuity_check.mjs
node tools/chart_check.mjs --shots "$EVIDENCE/chart-shots"
MPLBACKEND=Agg python -m pytest tests/ -q --junitxml="$EVIDENCE/pytest-results.xml"
MPLBACKEND=Agg python tools/make_fixture.py --check
git diff --check
```

The control runner uses disposable source copies: the exact reviewed application,
the corrected application with only the old evaluation selector restored, the
corrected application with only the old planning explanations restored, and an
unrelated document-title change. It invokes the same 721 assertions and requires
both intended failures and independent passing controls. It never edits the
working tree. Source hashes and the complete assertion results are retained in
[the correction evidence](2026-09-28-correction-evidence/).

Agent-operated Chromium journeys cover 390 × 844, 320 × 844 and 1280 × 844 in
both themes. Existing #91 checks also cover 360 × 800, 390 × 844 and 1280 × 900,
including chart-host/table keyboard ownership and comparison/saved consumers.
Inspected screenshots and measured geometry show wrapped, unclipped explanations
without horizontal document overflow. Native focus/pageshow/visibility/tick,
unchanged refresh, and a newer genuine record exercise continuity. Physical
hardware and assistive-technology testing remain NOT RUN.

The first unfiltered local run returned 9,190/9,191: the phone map chooser lost
keyboard focus around an element screenshot. The same 93/94 result reproduced on
the untouched reviewed application with screenshots; both applications passed
94/94 without screenshots. The open-panel artifact is now captured after the
unchanged keyboard sequence, reopening through the real control for that capture.
The corrected sequence passed 94/94. A restored-capture attempt also passed
94/94, documenting that the original interference is intermittent; it is not
claimed as a deterministic negative control. No map/keyboard application code or
assertion was relaxed. Normal unfiltered CI remains required. This narrow test
capture adjustment preserves the user-input checks while keeping the inspected
open-panel screenshot.

A final receipt audit added a detail-free `plan_error` control: the preceding
implementation failed six assertions, and the final implementation passed all 721.
The attempted/unknown fixture now has no recorded outcome, rather than an explicit
error gate. A second local full run overlapped that late source edit and returned
9,190/9,191; it is excluded from acceptance because the server read different
application versions during the run. The final implementation was then sealed,
and all four isolated controls plus the corrected 721-check suite ran unchanged.
The final exact-head unfiltered acceptance result is the normal PR CI recorded in
PR #92; no workflow timeout, schedule or manual rerun was changed.

The first local Python attempt failed five offline SDK tests because this fresh
runtime lacked `socksio` for its proxy configuration. Installing `socksio==1.0.0`
in the disposable test environment fixed that environment issue; no repository
dependency or production setting changed. Initial harness development also found
an incomplete synthetic receipt, a duplicate-surface copy-control count, and an
over-broad assertion that confused uncertainty about skipping with a claim of
skipping. Those attempts are not counted as acceptance. The final assertions run
unchanged against reviewed, corrected and isolated-control sources. The original
85 assertions and all pre-existing acceptance expectations remain in force.

## Preserved scope and proof limits

PASS — all 8,822 existing files outside the five intended edit paths match their
reviewed Git blob identities. This includes every prior POC/source/evidence file,
publication, history, quality ledger, Python producer file, workflow, and the
complete design-system snapshot. README and `.env.example` were reviewed;
`.env.example` remains unchanged. The original analysis was not regenerated.

| Proof or action | Result |
| --- | --- |
| Genuine historical qualified-plan demonstration | BLOCKED |
| Independent full-population market data and breadth correctness | BLOCKED |
| Cost-adjusted executable performance or trading edge | BLOCKED |
| Improved live reader acceptance/judgment | NOT RUN |
| Health or output of a future normal production run | NOT RUN |
| Full historical POC rerun for this correction | NOT RUN — no inputs or analyses were invalidated |
| Physical-device / assistive-technology testing | NOT RUN |
| Merge / manual production validation | NOT RUN |

The website and original report retain their explicit historical proof limits.
Passing corrective CI does not complete the larger validation milestone.
Numeric strategy, accepted-review prerequisite and reader authority, ranking,
account assumptions, provider/model budgets, recorded decisions and upstream
assets remain unchanged. No new provider/model call, live scan, workflow dispatch
or rerun, schedule/secret/settings/feed/model change, brokerage action, upstream
edit or sibling work occurred. Guidance owns independent re-review and the normal
protected merge. Stop at this same PR; no additional milestone is authorized.
