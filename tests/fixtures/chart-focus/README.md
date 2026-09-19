# Evidence focus regression excerpts

`excerpt.json` retains BPOP and BNY chart inputs from `docs/data.json` at
`8387ccedae22fbf30ddebdb6f52e1e42326a7ec5`, published September 18, 2026.
Its source metadata pins the production file digest, retained record and
Pages/evening artifact identities supplied with the acceptance failure.
All included field values and 120 observations per symbol are unchanged.
Only fields used by the chart and its evidence descriptions are included;
these are excerpts, not complete production publications or source receipts.

The browser test uses the existing offline pipeline fixture as its report
shell and supplies these retained chart inputs. Its boundary cases deliberately
change the evidence dates in copies over the same actual price observations;
those cases do not claim that the changed bases were published or measured.
Neither fixtures nor geometry assertions establish trading edge or provider
correctness. No mutable production file is needed to run the regression.

Run the full normal-origin browser journey with
`node tools/page_smoke.mjs --only focus --shots /tmp/focus-shots`.
`node tools/evidence_focus_cases.mjs --dom` is a fast geometry-only reproduction;
JSDOM is not browser, screenshot or storage/reload acceptance.
