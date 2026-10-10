# Journal producer controls

Run `python tests/fixtures/research-outcomes/generate.py --check` to reproduce
all 40 files. The generator drives the real evening pipeline with the existing
offline market/model doubles, then the real frozen-cohort and journal
producers. Optional publication side effects are disabled only inside this
generator; each companion is derived explicitly with a stated clock.

`pending` is the actual immutable October 9 publication (`f5cbe38e...650ef0d`)
and October 10 pre-entry cohort (`249b60c0...db788f0`). Its research ideas are
KE one hypothetical share and PSNL three; all retained bars end October 9.
Both are pending, day zero, no R. MG/ZIM/SN remain excluded. This is retained
production evidence, not a fresh provider request.

Every other publication is **production-shaped synthetic test data**, sealed
by the actual pipeline. They are not real market observations or executions.
The standard external fixture marker is removed after generation; run telemetry
normalization follows `tools.make_fixture`. No canonical plan is hand-edited.

- `synthetic-pending`: frozen October 9 priority cohort, generated October 10
  at 13:00 UTC. COIL/RONE/RTHR fit the unchanged baseline-first model budget.
- `observed`: October 12 source publication at 22:30 UTC, journal at 23:00.
  COIL's declared daily example resolves one whole share at 2.26 gross R;
  RONE has uncertain trigger timing, RTHR remains conditionally open.
- `revised`: the same session and close, but COIL's low is revised before the
  producer sees it. Stop-first replay is -1 R; full OHLC revision identity
  links the earlier clip without replacing it.
- `missing`: October 13 at the same daily clocks; the fake provider omits the
  entry-session bars. Later bars cannot invent entry fills.
- `basis-conflict`: genuine alternate-feed pipeline input; no prior split/SIP
  origin is silently relabelled as the newer basis.
- `not-filled`: never-triggered, open-above-limit and trigger/stop-order cases.
- `empty` and `red`: empty and market-refused original cohorts stay recorded.
- `cohort-revisions`: preserves the earlier before-entry cohort and a declared
  late derivation at October 12 15:00 UTC; journal at 15:00:01. Its observation
  publication still ends October 9, so the producer clock creates no bars.

Each variant has exact gzip canonical/reader bytes plus raw receipt/bundle.
Gzip uses a zero modification time. Embedded cohort `raw` strings preserve
their original exact bytes. The scanner must inspect decompressed source JSON
as well as repository bytes; compression is for size, not secret exclusion.
No private owner balances, reports, orders or provider credentials are used.
