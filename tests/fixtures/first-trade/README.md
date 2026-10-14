# First-trade rehearsal

Every broker fact here is **synthetic**: no broker, provider or real trade was
involved, and nothing here is a recommendation or anyone's result. Never copy
these files into `docs/`.

`backup.json` is the exact file the real page downloaded at the end of the
`firsttrade` page-smoke suite (`tools/first_trade_cases.mjs`), run over
`tests/fixtures/cash-preview/publication-multiple.json` -- the run_evening
publication at the $2,000 / 0.5% cash account that admits one AAPL burst share
($62.10 trigger, $63.22 limit, $60.70 stop) and four COIL anticipation shares
($110.61, $111.72, $109.50). `page-results.json` is what the page printed for each
record: the draft's cash and price-to-stop risk, and the completed result.
`parity.json.gz` is the page's own verdict on 109 backups built from this one
(`tools/private_results_parity.mjs` runs `app-handoff.js` over each): accepted or
refused, and every accepted record's figures.

The journey, on one clock the suite moves for the page and the private store
alike (Chicago times):

- 11 Sep 8:35: settled cash blank, unreadable, $0 and $300 each refused for three
  COIL shares; $2,000 previews and drafts three COIL and one AAPL.
- 8:41: AAPL reported filled at $62.40 and protected; COIL two of three filled at
  $111.05 and protected.
- 9:02, after the cutoff: no new draft and no cash preview; COIL's third share
  reported cancelled at 9:00.
- 14 Sep: AAPL opens under its stop and the stop fills at $59.85, $0.85 past it
  (gross -$2.55, fees $0.01, net -$2.56); COIL sells one at $113.20 (no
  completed result: one share remains).
- 15 Sep: COIL's last share at $114.00, averaging $113.60 (gross $5.10, fees
  $0.02, net $5.08). The backup is downloaded.

The suite runs the journey at 390 and 1280 px and requires both to write the same
bytes, then holds them to these files. `tests/test_private_results.py` holds
`tools/private_results.py` to both: every record traced to that publication, and
every amount re-derived as the page printed it.

When the cash-preview publication moves (its generator regenerates it whenever the
record's rules move), regenerate these with
`SCSTOCK_FIRST_TRADE_WRITE=1 node tools/page_smoke.mjs --only firsttrade`, and
then the corpus built from the backup with `node tools/private_results_parity.mjs`.
