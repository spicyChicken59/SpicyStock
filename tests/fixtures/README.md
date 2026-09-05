# Fixtures

Nothing in this directory is a signal. Every file here is invented data in
the pipeline's own shape, kept so that the page, the morning run and the test
suite can be exercised against states the repository cannot otherwise hold —
and every one of them says so in its own `run.fixture: true`.

| file | made by | what it holds |
|---|---|---|
| `data.json` | `python3 tools/make_fixture.py tests/fixtures/data.json` | One hand-authored evening run over 48 bursts: 25 scored, 23 gated, a fallback score that outranks a real one, a chart that failed to render, and the streak states one night can hold at once — day numbers from 1 up, repeats whose last appearance was scored, gate-rejected or crowded out, and unknowns whose reason is `window_not_covered`. The states it does NOT hold (an empty, undated or unreadable history, a missing streak block, a last appearance the veto refused) are the smoke test's `/v/<name>/` variants. The 23 are three different reasons, not two — 16 the checklist rejected, 6 the call cap crowded out, and 1 a 6/6 setup an absolute rule refused outright, which is the row that stops any surface calling a veto a gate rejection. `docs/data.json` is seeded from it and stays a byte-for-byte copy only until `evening.yml` commits a real run back. |
| `history/data.json`, `history/ledger.json` | `python3 tools/make_history.py tests/fixtures/history` | Thirty consecutive evening runs over a synthetic market, **written by the real pipeline** through the test doubles: every row by `candidate_record()`, every forward return by `forward_returns()`, every streak by `streaks()`, every mean by `mean_returns()`. A session the scorer was down for, a chart that would not render, repeats on consecutive sessions, and the last week's outcomes still pending. |

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

**The history fixture has a built-in relation between score and outcome.**
Each planted burst carries a hidden quality that shapes how quiet the week
before it was, what the stand-in scorer says, and how the next five sessions
drift — noisily, and deliberately weakest at one session out. That is so the
views that report whether a higher score earns a higher return have something
to render and something to refuse. It is evidence of nothing about the
strategy, the scorer or the market, which is why the ledger copy is never
committed to `docs/`: `Ledger.load()` would read it as history, and a real
run must never carry invented outcomes forward as its own.
