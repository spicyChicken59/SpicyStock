# Fixtures

Nothing in this directory is a signal. Every file here is invented data in
the pipeline's own shape, kept so that the page, the morning run and the test
suite can be exercised against states the repository cannot otherwise hold —
and every one of them says so in its own `run.fixture: true`.

| file | made by | what it holds |
|---|---|---|
| `data.json` | `python3 tools/make_fixture.py tests/fixtures/data.json` | One hand-authored evening run over 50 bursts: 25 scored, 25 gated, a fallback score that outranks a real one, a chart that failed to render, and the streak states one night can hold at once — day numbers from 1 up, repeats whose last appearance was scored, gate-rejected or crowded out, and unknowns whose reason is `window_not_covered`. The states it does NOT hold (an empty, undated or unreadable history, a missing streak block, a last appearance the veto or the liquidity floor refused) are the smoke test's `/v/<name>/` variants, except the last: a repeat whose previous appearance rule 6 refused is held by neither fixture, and the words for it are pinned on the page and in the email rather than rendered from a file. The 25 are four different reasons, not two — 16 the checklist rejected, 6 the call cap crowded out, 1 a 6/6 setup an absolute rule refused outright (the row that stops any surface calling a veto a gate rejection), and 2 that rule 6 refused for dollar volume below the session's $12.4M floor before the checklist saw them, which `run.liquidity` records and the evidence block keeps in a population of its own. One of its eight run entries (2026-08-25) carries a HOLE: 21 setups behind its +1d mean and 18 behind its +5d, so the file can tell a page weighting each horizon by its own count from one weighting all three by the run's `n` -- a state no generated file here holds, since the synthetic market's frames are contiguous. Its `run.settled` is the scorecard the mails print under the funnel -- three entries, derived from the runs above it rather than typed: the horizons that land on this session are exactly the ones whose run means are filled up there (2026-08-31 at +1d, 2026-08-27 at +3d, 2026-08-25 at +5d), and each universe figure is read off that session's own benchmark, so the block cannot contradict the record it ships with. It belongs to the hand-authored history half of this file, like the streak blocks, which is why `evidence.overall` is still every-n-zero beside it. Three names no burst uses are listed under `run.stopped_printing`, through the pipeline's own function: two that stopped printing, 57 and 21 sessions behind, and one the feed returned no bar for at all, which is dateless and first. `docs/data.json` is seeded from it and stays a byte-for-byte copy only until `evening.yml` commits a real run back. |
| `history/data.json`, `history/ledger.json` | `python3 tools/make_history.py tests/fixtures/history` | Thirty consecutive evening runs over a synthetic market, **written by the real pipeline** through the test doubles: every row by `candidate_record()`, every forward return by `forward_returns()` on both bases — from the burst-day close and from the next session's open — along the calendar of every frame the run fetched, every streak by `streaks()`, every mean by `mean_returns()` with its own count per horizon, every run entry's universe benchmark by `fill_benchmarks()` from a genuine universe scan (not `--tickers`, which offers none) over the names at or above that night's liquidity floor, and every run entry's rules fingerprint by `rules_fingerprint()`, so `evidence.rules` reports one screener. A session the scorer was down for, a chart that would not render, repeats on consecutive sessions, eight rows rule 6 refused, a session that scored nothing at all — no rows, so its run entry's three horizon cells can never be filled by anything and the page says so rather than calling them pending — a session (19 Aug) every one of whose scored names was already counted on an earlier one, which the page names as its own state for the same reason (`rows == scored` with `n == 0`: nothing left to measure, and nothing among it that counts) — and the last week's outcomes and benchmarks still pending. Every run entry also carries `fills_closed`, `src.ledger`'s own answer for which runs a later run still fetches bars for; the twenty oldest here are past that window, and none of them has a horizon left empty, which is why the page's fourth never-fills state needs a smoke variant rather than this file. Its `run.settled` is EMPTY, and correctly: the synthetic frames are static, so each night's fill measures every horizon its own frames already carry, and the last session in the file has no bar after it for anything to settle on. The non-empty state is the canonical fixture's, and the live one is a two-night end-to-end test in `tests/test_pipeline.py`. |

**Neither file holds a blind night, and that is deliberate.** Both carry
`run.coverage` -- how much of the session was actually READ -- and neither has
`measured: 0`. They are not the same night otherwise: `history/` is clean (77
asked, 77 answered, 77 measured, so the page captions the first cut "no 4%
gain on the day" and nothing more), while `data.json` is THIN -- 228 asked,
227 answered, 225 measured, because its two stopped-printing names are stale
-- so every surface derived from it appends the clause, and the page reads "no
4% gain on the day; 3 of the 228 asked could not be measured for this
session". That is a fine thing for it to be, and it is what the file renders;
the paragraph used to say the opposite. A night whose `measured` is 0
says the opposite on four surfaces (the funnel's caption, the null floor's
sentence, the streak's fifth unknown, and a benchmark that stays pending),
and a fixture cannot hold a state and its inverse: it is the smoke test's
`blindscan` variant, beside `quietmarket`, so each of the two can fail.

**The burst bar's geometry is authored in one and measured in the other.**
Since round 11 every row of both files carries `gap_pct`, `bar_range_pct` and
`range_expansion` in its `context`. `history/` gets them the way it gets
everything else — `src.lynch` measuring the synthetic frames the run really
scanned. `data.json` holds measurements and never slices a frame, so its
three are DERIVED from the row's own numbers rather than invented beside
them: the share of the day's gain that happened overnight fixes the open, the
low sits a little under it, and the `H` line's own close position fixes the
high, so `make_fixture.py` can assert that the open is inside its own bar.
Three numbers chosen independently would describe a bar no session can print,
which is the class `check_fixture_fresh.py` exists to close. That generator's
own assertion -- the expansion is the width over the `N` line's printed
pre-burst range -- is the pipeline's arithmetic since round 11's audit and
was not when it was written: `burst_bar_shape()` divided by the mean of the
per-bar widths each ROUNDED, so 8 of the 9 rows in `history/` disagreed with
the `N` line in their own row while this fixture asserted the identity 50
times. `tests/test_docs_are_true.py` holds every row of BOTH files to it now,
which is the check comparing a fixture to its generator cannot make.

What neither file holds is a null one. Three shapes produce one on a live
run, and none of them is a missing field: `src.scanner._session_bar_problem()`
refuses a session bar whose open, high, low, close or volume is not a finite
positive number before the checklist ever sees it, and it does not look at
whether the high is above the low -- so an INVERTED session bar nulls all
three (executed, not argued: it passes the scan's refusal and
`detect_setup()`), an open printed outside its own bar nulls the gap alone,
and a name that printed high == low for seven sessions leaves the expansion
with no width to expand against. No fixture has been given any of those
shapes; `tests/test_lynch.py` builds each of them.

Both carry an `evidence` block computed by the real `src/ledger.py`, and they
hold opposite states of it: `data.json`'s is entirely pending, because the
only run it holds rows for is one session old and nothing can have a
five-session outcome yet — the page on its first day. `history/data.json`'s is
populated.

**`data.json` describes two records at once, by design.** Its `runs[]` and
its streak blocks are a hand-authored seven-session history — eight entries
in the runs table, five of them with resolved means, and day numbers that
count back to 2026-08-21 — so the runs table and the streak line have
something to show. Its `evidence` is the real code's view of the one run the
file holds rows for, so `evidence.record` says one run and one session beside
a runs table of eight. A file a real run writes never disagrees with itself
this way, because both come off the same ledger; the history fixture is where
the two agree.

`tools/check_fixture_fresh.py` regenerates both and fails CI if either has
drifted from its generator. `tools/dashboard_smoke.mjs` opens the page against
both, and separately against whatever `docs/` holds.

The history generator serializes Stockbee measurements and synthetic OHLC
prices (including each row's previous close and chart series) at eight decimal
places. It does this only after the real pipeline has finished classifying,
ordering and measuring the runs; input frames and production output retain
their original precision. This removes insignificant CPU-dependent floating
point differences while the freshness guard still compares the complete JSON
exactly, including prices, dates, queue membership and fixture markers.

**The history fixture has a built-in relation between score and outcome.**
Each planted burst carries a hidden quality that shapes how quiet the week
before it was, what the stand-in scorer says, and how the next five sessions
drift — noisily, and deliberately weakest at one session out. That is so the
views that report whether a higher score earns a higher return have something
to render and something to refuse. It is evidence of nothing about the
strategy, the scorer or the market, which is why the ledger copy is never
committed to `docs/`: `Ledger.load()` would read it as history, and a real
run must never carry invented outcomes forward as its own.
