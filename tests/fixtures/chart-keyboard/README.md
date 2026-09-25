# Chart table keyboard regression

`2026-09-24.json.gz` decompresses to the exact published `docs/data.json`
from `6822dddd14d0a541083e7caaecca9c945b451af2` (evening run `36077970591`,
attempt 1; execution revision `470c358c06bc9c997184d829c63845c4db0dc4f5`).
Uncompressed SHA-256:
`97da76d4f0eae671a5168760b79852c2eb6c4539bef3a144df6ef6bfe20c93f4`.

This immutable test copy preserves the reported NIC journey when automatic
publication advances the live record. No measurements or decisions are changed.
`tools/chart_keyboard_cases.mjs` runs it through the existing page gate with
ordinary browser keys and settled column bounds. Comparison and saved-chart
checks use the existing synthetic `page/full.json` and disposable contexts.

Run `node tools/page_smoke.mjs --only chart-keyboard --shots <directory>`;
the suite also runs in the normal unfiltered page gate. Component coverage
lives in `tools/chart_check.mjs`. Fonts and external requests are blocked in
this offline regression; viewport emulation is not physical-device evidence.
