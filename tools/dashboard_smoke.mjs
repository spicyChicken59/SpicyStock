// Does the dashboard still work? The one check that opens it.
//
//   node tools/dashboard_smoke.mjs [design-system-checkout] [--shots <dir>]
//
// docs/index.html is a static shell: the Python pipeline writes docs/data.json
// and the page fetches it in the browser. Nothing in the Python suite can fail
// on the page, and nothing in the page can fail on the pipeline — so without
// this, a typo in the render path ships green and the reader finds it.
//
// It drives the real page in headless Chromium and asserts what the page
// PROMISES, not how it is built. The promises are about honesty, so most of
// these are arithmetic a reader could redo by hand: the table holds EVERY
// candidate the run scored and not a shortlist of them, the scored rows plus
// the not-scored rows account for every burst the scan found, and every score
// the offline checklist produced is labelled as one everywhere it appears —
// including when it outranks a real score and lands on the shortlist.
//
// Offline by construction, so CI has nothing new to reach for: docs/ is served
// from a local http server (the page fetches data.json, which file:// blocks),
// every cdn.jsdelivr.net request is answered from a design-system checkout on
// disk, and every other host is answered with an empty body.
//
// THREE DATA SOURCES, ONE PAGE. docs/data.json is whatever the last run wrote
// -- the fixture on a fresh clone, last night's real run once evening.yml has
// committed one back -- so the checks that know the fixture's contents (25
// scored, a fallback on the shortlist, chart paths that 404) cannot run against
// it: the first real run would have failed a dozen of them and thrown in two.
// They run against the canonical fixture instead, served under /f/fixture/;
// the thirty-run history tools/make_history.py writes is served under
// /f/history/, for the states one night cannot hold; and docs/ itself is
// opened last, under /, with only the checks that hold for ANY run -- it opens,
// it adds up, it says whether it is a fixture, and it logs no error. Mutated
// copies of the fixture are served under /v/<name>/ as before.
//
// Needs playwright's chromium. It is not a repo dependency: `npm install
// --no-save playwright@1.56` next to the repo, or have it installed globally
// with PLAYWRIGHT_BROWSERS_PATH pointing at the browsers. If chromium is
// missing the script says so and exits 0 — a machine without a browser is not
// a failing dashboard.
import { createServer } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { extname, join, resolve, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, '..');
const ROOT = join(REPO, 'docs');
const FIXTURES = join(REPO, 'tests', 'fixtures');
// Where /f/<source>/data.json and /f/<source>/ledger.json are answered from;
// everything else under /f/<source>/ is docs/, so the same index.html renders
// each one.
const SOURCES = { fixture: FIXTURES, history: join(FIXTURES, 'history') };
const argv = process.argv.slice(2);
const SHOTS = argv.includes('--shots') ? argv[argv.indexOf('--shots') + 1] : null;

// The checkout the page's pinned CDN requests are answered from. CI passes the
// clone it already made for the linter; locally the first of these that has
// sc.css in it wins.
const DS = [
  argv.find((a) => !a.startsWith('--') && a !== SHOTS),
  process.env.SC_DESIGN_SYSTEM,
  '/tmp/design-system',
  resolve(REPO, '..', 'design-system'),
  join(REPO, 'design-system')
].filter(Boolean).find((d) => existsSync(join(d, 'sc.css')));
if (!DS) {
  console.error('usage: node tools/dashboard_smoke.mjs [design-system-checkout] [--shots <dir>]');
  console.error('       no checkout with sc.css found — pass one, or set SC_DESIGN_SYSTEM');
  process.exit(2);
}

// playwright is not a dependency of this repo. Try a local install first, then
// a global one (npm's standard prefix layout beside the running node binary).
async function loadChromium() {
  const tries = [
    () => import('playwright'),
    ...[...(process.env.NODE_PATH || '').split(':'), resolve(dirname(process.execPath), '..', 'lib', 'node_modules')]
      .filter(Boolean)
      .map((root) => () => import(pathToFileURL(join(root, 'playwright', 'index.js')).href))
  ];
  for (const t of tries) {
    try { const m = await t(); const c = m.chromium || (m.default && m.default.chromium); if (c) return c; }
    catch { /* next */ }
  }
  return null;
}
const chromium = await loadChromium();
if (!chromium) { console.log('  skip  playwright is not installed — the dashboard was not opened'); process.exit(0); }

// --- the server ------------------------------------------------------------
// /            the real docs/, exactly as GitHub Pages would serve it
// /f/<src>/    the same index.html against a fixture's data.json (and
//              ledger.json, where the fixture has one) — see SOURCES
// /v/<name>/   the same index.html against a mutated copy of the canonical
//              fixture, for the states a single day's fixture cannot hold
const REAL = JSON.parse(await readFile(join(FIXTURES, 'data.json'), 'utf8'));
const HIST = JSON.parse(await readFile(join(SOURCES.history, 'data.json'), 'utf8'));
const LIVE = JSON.parse(await readFile(join(ROOT, 'data.json'), 'utf8'));
const clone = () => JSON.parse(JSON.stringify(REAL));
const VARIANTS = {
  // What the page must look like once step 9 starts recording forward returns.
  // 22 of the 25 land; the last three stay null, because a session closing for
  // some names and not others is the normal state and the score/outcome plot
  // must not quietly drop the pending ones or draw them at zero. The shortlist
  // does better than the rest here, so the page has a real gap to describe —
  // and, being one session, a real reason to refuse to call it evidence.
  forward() {
    const d = clone();
    const vals = [
      [2.41, 3.02, -0.87], [-1.16, 0.44, 1.98], [0.73, 4.12, 5.6], [3.05, 2.2, 2.9], [-2.4, -3.11, -1.05],
      [1.42, 2.18, 1.04], [-0.88, -1.42, 0.36], [0.31, 1.07, 1.85], [-1.95, -0.62, -2.4], [2.1, 3.44, 2.06],
      [-0.44, 0.19, 0.77], [0.67, -0.35, 1.29], [-2.63, -3.9, -2.18], [1.08, 0.52, -0.44], [-0.19, 1.66, 2.31],
      [-1.37, -2.05, -0.93], [0.52, 0.88, 1.4], [-3.02, -1.74, -3.61], [0.94, 2.37, 0.18], [-0.71, -1.11, 0.62],
      [-1.84, -2.48, -1.29], [0.26, 0.73, 1.02]
    ];
    d.candidates.slice(0, vals.length).forEach((c, i) => {
      // The open basis a fixed step below the close basis, so a check can
      // tell which one a cell is showing without knowing which row it is.
      c.forward_returns = { d1: vals[i][0], d3: vals[i][1], d5: vals[i][2], as_of: '2026-09-08',
        from_open: { d1: +(vals[i][0] - 0.5).toFixed(2), d3: +(vals[i][1] - 0.5).toFixed(2), d5: +(vals[i][2] - 0.5).toFixed(2) } };
    });
    d.runs[0].forward_returns = { d1: 0.52, d3: 1.33, d5: 1.71, n: d.candidates.length,
      from_open: { d1: 0.02, d3: 0.83, d5: 1.21, n: d.candidates.length } };
    return d;
  },
  // A file that recorded a checklist only for the candidates it scored — which
  // is what step 9 will produce if it forgets the gated ones. Every row left
  // has already cleared the gate, so a per-check pass rate over them describes
  // survivors and nothing else. The page has to say that, not print the number.
  nodetail() {
    const d = clone();
    d.gated_out.forEach((g) => { delete g.lynch_detail; delete g.lynch_total; });
    return d;
  },
  // The same run over a full-market universe — where the rebuild is heading,
  // and where the shortlist is a thousandth of what was scanned. On one shared
  // linear scale that bar is under a pixel, and a funnel that lets it round
  // away has quietly stopped showing the last stage at all.
  wide() {
    const d = clone();
    d.run.universe = { label: 'every US common stock', size: 5000 };
    return d;
  },
  // Enough closed sessions for ONE horizon to clear the page's own bar, so the
  // "not enough data" verdict is a judgement the page can change its mind
  // about rather than a string it always prints.
  history() {
    const d = clone();
    for (let i = 0; i < 24; i++) {
      d.runs.push({
        date: `2026-07-${String((i % 28) + 1).padStart(2, '0')}`, type: 'evening',
        bursts: 40, passed_gate: 22, scored: 20, shortlist_size: 5, top_score: 8.0, fallbacks: 0,
        forward_returns: { d1: ((i % 7) - 3) * 0.4, d3: null, d5: null, n: 20 }
      });
    }
    return d;
  },
  // Every run's rows collapse 1:1 into setups -- no name burst twice inside a
  // window, so nothing was folded. The tile used to print the row count only
  // when the two numbers DIFFERED, so the reader could not see the ratio in
  // the one case where it is settled, and could not tell "nothing collapsed"
  // from "the file does not say".
  norepeats() {
    const d = clone();
    d.runs.forEach((r) => {
      if (r.forward_returns && r.forward_returns.n) r.forward_returns.rows = r.forward_returns.n;
    });
    return d;
  },
  // A run that got part way and lost something on the way.
  degraded() {
    const d = clone();
    d.run.errors = [{ stage: 'scanner', message: 'Alpaca returned no bars for 214 symbols; those were skipped.' }];
    return d;
  },
  // A REAL run on a quiet night: one burst, rejected at the gate, nothing
  // scored. This is the shape that breaks a check written against a 47-burst
  // fixture -- a headline whose plural is hard-coded, and a scores table whose
  // "Nothing to show." placeholder counts as a candidate row -- and it is a
  // shape production will produce within its first month. It exists so the
  // claim that the docs/-facing checks hold for ANY run is something CI
  // exercises rather than something this file asserts about itself.
  quietnight() {
    const d = clone();
    d.run.fixture = false;
    d.run.bursts = 1;
    d.run.scored = 0;
    d.run.passed_gate = 0;
    d.run.shortlist_size = 0;
    d.candidates = [];
    d.gated_out = d.gated_out.slice(0, 1);
    return d;
  },
  // A snapshot published before the pipeline learned to write an evidence
  // block. The page must say which kind of nothing that is rather than
  // hiding the card, the same rule the streak line follows.
  noevidence() {
    const d = clone();
    delete d.evidence;
    return d;
  },
  // A snapshot written by a pipeline that had no absolute rules: no
  // gate.vetoes, and every unscored burst carries one of the two older reason
  // words. The page must not tell that run's reader an absolute rule could
  // have cut a name, which is the confidently-false sentence the funnel's own
  // guard exists to prevent -- and until this variant existed, deleting that
  // guard was invisible to every check here.
  novetoes() {
    const d = clone();
    delete d.run.gate.vetoes;
    for (const g of d.gated_out) {
      if (String(g.reason).startsWith('veto_')) g.reason = 'lynch_gate';
    }
    return d;
  },
  // The quietest real night there is: the scan ran clean and found no 4%
  // burst at all. Every candidate-facing card has nothing to hold, and the
  // question is whether the page SAYS that or just goes blank -- the email's
  // version of this said "No candidates passed the quality gate today" under
  // a funnel reading "4% bursts found: 0", blaming the checklist for an
  // outcome it had no part in.
  quietmarket() {
    const d = clone();
    d.run.fixture = false;
    d.run.bursts = 0;
    d.run.passed_gate = 0;
    d.run.scored = 0;
    d.run.shortlist_size = 0;
    d.run.scored_by = { claude: 0, fallback: 0 };
    d.run.gate.total_checks = null;   // nothing measured a checklist either
    d.candidates = [];
    d.gated_out = [];
    return d;
  },
  // The control ladder's other two sentences. The history source has 74
  // scored setups closed and 14 refused, which is the "only one side can be
  // read" branch; a direction may only be stated when BOTH clear min_setups,
  // and "no comparison yet" when neither does. Neither state exists in any
  // real source yet, so both are built from the history's own block with the
  // n's moved and the means kept -- the sentence is what is under test, not
  // the arithmetic behind the numbers, which tests/test_ledger.py pins.
  thincontrol() {
    const d = clone();
    d.evidence = JSON.parse(JSON.stringify(HIST.evidence));
    for (const block of [d.evidence.overall, d.evidence.refused]) {
      block.outcomes.forEach((o) => { if (o.n) o.n = 5; });
      block.enough = false;
    }
    return d;
  },
  fullcontrol() {
    const d = clone();
    d.evidence = JSON.parse(JSON.stringify(HIST.evidence));
    const h = d.evidence.horizons[d.evidence.horizons.length - 1];
    const picks = d.evidence.overall.outcomes.find((o) => o.horizon === h);
    const ref = d.evidence.refused.outcomes.find((o) => o.horizon === h);
    // DIFFERENT n's on the two sides. With both at 40 a verdict that printed
    // the picks' n for the refused side too read identically, and the check
    // that was meant to catch that passed with it in place.
    picks.n = 40; picks.mean = 6.0;
    ref.n = 45; ref.mean = 3.0;              // three points worse than the picks
    d.evidence.refused.enough = true;
    return d;
  },
  // A run entry whose date will not parse. The pipeline KEEPS such an entry
  // (load_history degrades on it rather than refusing the file), the email
  // says the history holds runs none of which carry a date, and the page
  // printed "NaN undefined not" into the runs table's session column.
  undated() {
    const d = clone();
    d.runs = [{ ...d.runs[0], date: 'not-a-date' }].concat(d.runs.slice(1));
    return d;
  },
  // A snapshot written before the gate block, the cap, the provenance count
  // or the shortlist size existed. The nogatetotal round guarded a null total
  // and stopped one field short of a missing block: "under undefined checks
  // passed" and "outside the undefined-call cap" reached the funnel.
  oldsnap() {
    const d = clone();
    delete d.run.gate; delete d.run.score_cap; delete d.run.scored_by; delete d.run.shortlist_size;
    return d;
  },
  // A day number with no first_seen beside it. src.ledger never writes the
  // pair, so it is an off-disk shape -- and "day 2 of this setup, since —"
  // is what the page made of it, the email "since " with nothing after.
  nosince() {
    const d = clone();
    d.candidates[0].streak = { ...(d.candidates[0].streak || {}), day: 2, first_seen: null, seen_before: 1 };
    return d;
  },
  // A run whose gate block never learned how many checks the checklist has.
  // The producer emits null there when NOTHING measured a checklist that
  // night, and every surface that mentions the gate concatenates the number
  // into prose -- so the page published "rejected at the ≥3/null 2LYNCH gate"
  // and "under 3 of null checks" over a run that had cleared everything, with
  // the whole suite and every check here green. A null is not a state the
  // canonical fixture can hold, so it needed its own source.
  nogatetotal() {
    const d = clone();
    d.run.gate.total_checks = null;
    return d;
  },
  // The pipeline has never run, or the write failed.
  // A snapshot from before round 5: no run.liquidity, no liquidity_floor
  // rows, no evidence.illiquid. The page must not tell that run it enforced
  // a floor it never recorded, on the funnel, the gated hint or the ladder.
  noliquidity() {
    const d = clone(REAL);
    delete d.run.liquidity;
    d.gated_out = d.gated_out.filter((g) => g.reason !== 'liquidity_floor');
    d.run.bursts -= REAL.gated_out.filter((g) => g.reason === 'liquidity_floor').length;
    delete d.evidence.illiquid;
    return d;
  },
  // The one key of run.stopped_printing the page indexes and the load check
  // never read. src/ledger.py's snapshot_problem() refuses this block now, but
  // that guard runs on the MORNING EMAIL's path and the page reads whatever
  // docs/ holds -- so a hand-edited file printed "for more than undefined
  // sessions" and nothing said so. The names are still worth showing; the
  // threshold is simply not stated.
  nothreshold() {
    const d = clone(REAL);
    delete d.run.stopped_printing.after_sessions;
    return d;
  },
  // A snapshot from before the open basis existed: no from_open on any row,
  // any run mean or any evidence outcome. The open tab must say the record
  // predates it, and no close-basis number may appear under the open label.
  noopen() {
    const d = clone(REAL);
    const strip = (fr) => { if (fr && typeof fr === 'object') delete fr.from_open; };
    d.candidates.forEach((c) => strip(c.forward_returns));
    d.gated_out.forEach((g) => strip(g.forward_returns));
    d.runs.forEach((r) => strip(r.forward_returns));
    const stripBlock = (b) => {
      if (!b) return;
      (b.outcomes || []).forEach((o) => delete o.from_open);
      delete b.enough_from_open;
    };
    const ev = d.evidence;
    ['overall', 'shortlist', 'rest', 'refused', 'crowded_out', 'illiquid', 'universe'].forEach((k) => stripBlock(ev[k]));
    ['by_score', 'by_day', 'by_month', 'by_ticker'].forEach((k) => (ev[k] || []).forEach(stripBlock));
    (ev.by_check || []).forEach((c) => { stripBlock(c.passed); stripBlock(c.failed); delete c.enough_from_open; });
    return d;
  },
  // The common night on a 230-name universe: the call cap did not bite, so
  // the liquidity clause is the LAST clause of the gated hint. And the night
  // whose only unscored bursts are rule 6's, one clause alone. Both hid a
  // joiner that rewrote the clause's own comma.
  nocap() {
    const d = clone(REAL);
    const capped = d.gated_out.filter((g) => g.reason === 'score_cap').length;
    d.gated_out = d.gated_out.filter((g) => g.reason !== 'score_cap');
    d.run.bursts -= capped;
    return d;
  },
  onlyfloor() {
    const d = clone(REAL);
    const kept = d.gated_out.filter((g) => g.reason === 'liquidity_floor');
    d.run.bursts -= d.gated_out.length - kept.length;
    d.run.passed_gate = d.run.scored;
    d.gated_out = kept;
    return d;
  },
  // The ladder half of the pre-round-5 state, on a source whose ladder
  // renders: the one-night fixture shows no ladder at all (nothing has an
  // outcome), so a check that read its rows could not fail.
  noliquidityladder() {
    const d = VARIANTS.fullcontrol();
    delete d.evidence.illiquid;
    return d;
  },
  // A reason word from a newer writer than this page. It used to render as
  // "rejected at the 2LYNCH gate" -- the one collapse the contract forbids by
  // name, silent, on every such row.
  newreason() {
    const d = clone(REAL);
    d.gated_out[0].reason = 'veto_gap_too_wide';
    return d;
  },
  // A record from before the benchmark: no runs[].benchmark, no evidence.universe.
  nobenchmark() {
    const d = VARIANTS.fullcontrol();
    delete d.evidence.universe;
    d.runs.forEach((r) => delete r.benchmark);
    return d;
  },
  // And one with enough paired setups to say something: the picks +6.00% at
  // +5d over 40 (fullcontrol's numbers), the universe +2.00% over 40 from the
  // close and +0.50% over 39 from the next open, so the two bases cannot be
  // read as one and the sentence has to name the one it is on.
  fullbenchmark() {
    const d = VARIANTS.fullcontrol();
    const h = d.evidence.horizons[d.evidence.horizons.length - 1];
    const bench = d.evidence.universe.outcomes.find((o) => o.horizon === h);
    bench.n = 40; bench.mean = 2.0;
    bench.from_open = { mean: 0.5, n: 39, best: 9, worst: -9, in_band: 0 };
    d.evidence.universe.setups = 40;
    d.evidence.universe.enough = true;
    d.evidence.universe.enough_from_open = true;
    // The picks and the refusals are complete on BOTH bases here, because a
    // verdict is only reached when both sides clear the floor on the basis
    // being read: without this the open tab fell to "no comparison yet" and
    // the sentence under test was never rendered at all.
    const picks = d.evidence.overall.outcomes.find((o) => o.horizon === h);
    const ref = d.evidence.refused.outcomes.find((o) => o.horizon === h);
    picks.from_open = { mean: 5.0, n: 38, best: 30, worst: -20, in_band: 0 };
    ref.from_open = { mean: 2.5, n: 43, best: 25, worst: -22, in_band: 0 };
    d.evidence.refused.enough_from_open = true;
    d.evidence.overall.enough_from_open = true;
    // Forty measured pairings, every one benchmarked over its night's floor.
    // A measured pairing is floored or unfloored and never neither; the
    // one-night fixture has neither because all of its pairings are pending.
    d.evidence.universe.floored = 40;
    d.evidence.universe.unfloored = 0;
    return d;
  },
  // The rung over pairings benchmarked before the floor reached the
  // benchmark: every name that traded, the thin ones in. The sentence and
  // the row's own label both have to say so, because the row's label is a
  // sentence about the rule and this record did not apply it.
  unflooredbenchmark() {
    const d = VARIANTS.fullbenchmark();
    d.evidence.universe.floored = 0;
    d.evidence.universe.unfloored = 40;
    return d;
  },
  // And the record that straddles the change, which every real ledger
  // spanning round 9 will be for as long as it holds a run benchmarked
  // before it: a measured horizon keeps its value, so those pairings are
  // never re-measured, and only MAX_RUNS retention ends the straddle.
  mixedfloor() {
    const d = VARIANTS.fullbenchmark();
    d.evidence.universe.floored = 30;
    d.evidence.universe.unfloored = 10;
    return d;
  },
  // A benchmark with a mean and too few setups behind it. The rung still
  // shows the number, marked; the verdict must NOT read it as a rate. Every
  // other block on this page carries that rule and nothing checked it here.
  thinbenchmark() {
    const d = VARIANTS.fullbenchmark();
    const h = d.evidence.horizons[d.evidence.horizons.length - 1];
    const bench = d.evidence.universe.outcomes.find((o) => o.horizon === h);
    bench.n = 4;
    d.evidence.universe.setups = 4;
    d.evidence.universe.enough = false;
    d.evidence.universe.enough_from_open = false;
    return d;
  },
  // A record written under two screeners: the gate moved. Every mean on the
  // page then averages both, and the page has to say which key moved rather
  // than only that something did.
  rulesdrift() {
    const d = clone(REAL);
    const ev = d.evidence;
    const current = JSON.parse(JSON.stringify(ev.rules.current));
    const older = JSON.parse(JSON.stringify(current));
    older['gate.min_lynch_passes'] = 4;
    older['scan.min_gain_pct'] = 5.0;
    ev.rules = { current, sets: 2, differ: ['gate.min_lynch_passes', 'scan.min_gain_pct'], runs_without: 0 };
    d.runs[0].rules = current;
    d.runs.slice(1).forEach((r) => { r.rules = older; });
    return d;
  },
  // And one whose runs predate the fingerprint: not knowing which rules made
  // a row is a different sentence from knowing they were these.
  norules() {
    const d = clone(REAL);
    d.evidence.rules = { current: null, sets: 0, differ: [], runs_without: d.runs.length };
    d.runs.forEach((r) => delete r.rules);
    return d;
  },
  // The state the FIRST real ledger spanning round 6 produces: rows written
  // before the open basis existed sit beside new ones, so a block clears the
  // floor on the close basis and not on the open one. No source had it, which
  // is how three cards shipped reading the close basis's licence for both.
  halfmeasured() {
    const d = clone(REAL);
    d.evidence = JSON.parse(JSON.stringify(HIST.evidence));
    const thin = (block) => {
      if (!block) return;
      block.enough = true;
      block.enough_from_open = false;
      (block.outcomes || []).forEach((o) => { if (o.from_open) o.from_open.n = 5; });
    };
    (d.evidence.by_check || []).forEach((c) => { thin(c); });
    (d.evidence.by_day || []).forEach(thin);
    (d.evidence.by_month || []).forEach(thin);
    return d;
  },
  // A band whose CLOSE mean runs past the claimed band and whose open mean
  // does not. The chart's x-scale is otherwise pinned by 0 and band.high,
  // which dwarf every real mean -- so a chart reading the wrong basis for
  // its scale is invisible until one basis leaves the band. That is exactly
  // the state a single huge winner produces.
  widemean() {
    const d = clone(REAL);
    d.evidence = JSON.parse(JSON.stringify(HIST.evidence));
    const h = d.evidence.horizons[d.evidence.horizons.length - 1];
    const band = d.evidence.by_score.find((b) => b.outcomes.some((o) => o.horizon === h && o.mean !== null));
    const cell = band.outcomes.find((o) => o.horizon === h);
    cell.mean = 45.0;
    cell.from_open = Object.assign({}, cell.from_open, { mean: 5.0 });
    return d;
  },
  // Rows and a run from before the open basis, beside rows measured on it:
  // the row-level state of the first ledger spanning round 6. On the open
  // basis those rows are not "pending" -- their sessions closed long ago and
  // were never measured this way -- and the words have to say which.
  prebasisrows() {
    const d = VARIANTS.forward();
    delete d.candidates[1].forward_returns.from_open;
    d.runs[1].forward_returns = { d1: 0.4, d3: 0.9, d5: 1.3, n: 20 };
    return d;
  },
  // A row refused an entry -- no usable open on the next session, or an open
  // outside its own bar -- carries a measured close basis and an open basis
  // null throughout; its sessions happened, and "pending" was the word it
  // wore. And a row with no forward_returns at all, which no writer produces
  // and a hand-edited file can: one word for it on the card and both tables.
  noentry() {
    const d = VARIANTS.forward();
    d.candidates[2].forward_returns.from_open = { d1: null, d3: null, d5: null };
    d.runs[1].forward_returns = { d1: 0.4, d3: 0.9, d5: 1.3, n: 20, from_open: { d1: null, d3: null, d5: null, n: 0 } };
    delete d.candidates[3].forward_returns;
    return d;
  },
  // A data.json written before round 9: no separation_from_open on any
  // check, no floored/unfloored on the rung. The open tab must say the
  // column is unmeasured there rather than that no check has enough setups,
  // and the rung must not claim a floor the record never applied.
  oldevidence() {
    const d = clone(REAL);
    d.evidence = JSON.parse(JSON.stringify(HIST.evidence));
    d.evidence.by_check.forEach((c) => delete c.separation_from_open);
    delete d.evidence.universe.floored;
    delete d.evidence.universe.unfloored;
    return d;
  },
  nodata() { return null; }
};

const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
                '.png': 'image/png', '.svg': 'image/svg+xml', '.ico': 'image/x-icon' };
const server = createServer(async (req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0]);
  const f = p.match(/^\/f\/([a-z]+)(\/.*)?$/);
  if (f && SOURCES[f[1]]) {
    const rest = f[2] && f[2] !== '/' ? f[2] : '/index.html';
    if (rest === '/data.json' || rest === '/ledger.json') {
      let body;
      try { body = await readFile(join(SOURCES[f[1]], rest.slice(1))); }
      catch { res.writeHead(404).end('this fixture has no ' + rest.slice(1)); return; }
      res.writeHead(200, { 'content-type': 'application/json' }).end(body);
      return;
    }
    p = rest;
  }
  const v = p.match(/^\/v\/([a-z]+)(\/.*)?$/);
  if (v && VARIANTS[v[1]]) {
    const rest = v[2] && v[2] !== '/' ? v[2] : '/index.html';
    if (rest === '/data.json') {
      const body = VARIANTS[v[1]]();
      if (body === null) { res.writeHead(500).end('the pipeline has not written this'); return; }
      res.writeHead(200, { 'content-type': 'application/json' }).end(JSON.stringify(body));
      return;
    }
    p = rest;
  }
  const file = resolve(join(ROOT, p === '/' ? '/index.html' : p));
  if (!file.startsWith(ROOT)) { res.writeHead(403).end(); return; }
  // Read first, then write the head: a 404 after writeHead(200) is an
  // ERR_HTTP_HEADERS_SENT that takes the whole run down instead of the request.
  let body;
  try { body = await readFile(file); } catch { res.writeHead(404).end('not found'); return; }
  res.writeHead(200, { 'content-type': TYPES[extname(file)] || 'application/octet-stream' }).end(body);
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const BASE = `http://127.0.0.1:${server.address().port}`;
if (SHOTS) await mkdir(SHOTS, { recursive: true });

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 1000 } });
const PIXEL = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=', 'base64');
// Order matters: playwright matches the LAST registered route first, so the
// catch-all goes down before the specific one.
await ctx.route(/^https?:\/\/(?!127\.0\.0\.1)/, (r) => (/\.(png|jpe?g|webp|gif|svg)/i.test(r.request().url())
  ? r.fulfill({ status: 200, contentType: 'image/png', body: PIXEL })
  : r.fulfill({ status: 200, contentType: 'text/plain', body: '' })));
await ctx.route('**://cdn.jsdelivr.net/**', (route) => {
  const path = new URL(route.request().url()).pathname;
  const file = join(DS, path.replace(/^\/gh\/spicyChicken59\/design-system@[^/]+\//, ''));
  return existsSync(file)
    ? route.fulfill({ path: file, contentType: TYPES[extname(file)] })
    : route.fulfill({ status: 404, body: 'not in the checkout: ' + path });
});

const errors = [];
const chart404 = new Set();
const page = await ctx.newPage();
page.on('pageerror', (e) => errors.push('uncaught: ' + e.message));
page.on('console', (m) => {
  if (m.type() !== 'error') return;
  const url = (m.location() && m.location().url) || '';
  // The chart PNGs 404 because .gitignore blocks /docs/charts/ and NOTHING is
  // ever committed there — see src/pipeline.py's CHARTS_DIR. So this is the
  // permanent state of the published page, not a wait for the pipeline to run:
  // locally the PNGs appear when an evening run writes them beside data.json,
  // and in this checkout there are none. The page swaps in an explained frame,
  // which is the state under test, so these are counted and asserted on below
  // rather than treated as page errors.
  if (/\/charts\/[^/]+\.png$/.test(url)) { chart404.add(url.replace(/^.*\/charts\//, '')); return; }
  errors.push('console: ' + m.text() + (url ? ' @ ' + url : ''));
});
// A chart image still loading when the next check navigates away is aborted
// BY the navigation, not by the page -- the cards are rendered after the load
// event, so `open()` cannot wait for them and does not. Round 8 recorded "2
// page errors with 187/187 checks passing" and could not reproduce it; here it
// was three, on the fullbenchmark variant's charts, and it is timing, which is
// why it came and went. Counted apart so the summary still shows them, and so
// that a request the page itself failed -- any other error, or an abort on
// anything but a chart PNG -- is still a page error that fails the run.
const aborted = [];
page.on('requestfailed', (r) => {
  const why = (r.failure() && r.failure().errorText) || '';
  if (why === 'net::ERR_ABORTED' && /\/charts\/[^/]+\.png$/.test(r.url())) { aborted.push(r.url()); return; }
  errors.push('request failed: ' + r.url().slice(0, 90) + (why ? ' (' + why + ')' : ''));
});

const results = [];
const ok = (name, pass, detail = '') => results.push({ name, pass: !!pass, detail });
const shot = async (n) => { if (SHOTS) await page.screenshot({ path: join(SHOTS, n + '.png'), fullPage: true }); };
async function open(path = '/f/fixture/') {
  await page.goto(BASE + path, { waitUntil: 'load' });
  await page.waitForFunction(() => {
    const h = document.getElementById('h1');
    return h && h.textContent.trim() && h.textContent !== 'Loading the latest run…';
  }, null, { timeout: 20000 });
  await page.waitForTimeout(250);
}
const setTheme = (t) => page.click(`.sc-theme-toggle button[data-theme="${t}"]`);

// What the fixture says, so every assertion below is checked against the data
// rather than against a number typed into this file.
const run = REAL.run;
const fallbacks = REAL.candidates.filter((c) => c.provenance.source !== 'claude');

// The four analysis views are all arithmetic over the fixture, so the expected
// answers are computed here from the same data the page reads. Nothing below
// compares the page against a number typed into this file.
const STAGES = [
  ['universe scanned', run.universe.size], ['4% bursts', run.bursts],
  ['passed 2LYNCH', run.passed_gate], ['scored', run.scored], ['shortlist', run.shortlist_size]
];
const everyBurst = REAL.candidates.concat(REAL.gated_out);
const CHECKS = (() => {
  const by = new Map();
  for (const r of everyBurst) {
    const cleared = r.lynch_passes >= run.gate.min_lynch_passes;
    for (const d of r.lynch_detail || []) {
      if (!by.has(d.code)) by.set(d.code, { code: d.code, pass: 0, total: 0, cpass: 0, ctotal: 0, fpass: 0, ftotal: 0 });
      const s = by.get(d.code);
      s.total++; if (d.pass) s.pass++;
      if (cleared) { s.ctotal++; if (d.pass) s.cpass++; } else { s.ftotal++; if (d.pass) s.fpass++; }
    }
  }
  return [...by.values()].map((s) => ({ ...s, rate: s.pass / s.total, gap: s.cpass / s.ctotal - s.fpass / s.ftotal }));
})();
const HARSHEST = [...CHECKS].sort((a, b) => a.rate - b.rate)[0];
const WEAKEST = [...CHECKS].sort((a, b) => a.gap - b.gap)[0];
const horizon = (k) => {
  const have = REAL.runs.filter((r) => (r.forward_returns || {})[k] !== null && (r.forward_returns || {})[k] !== undefined);
  const names = have.reduce((a, r) => a + (r.forward_returns.n || 0), 0);
  const wsum = have.reduce((a, r) => a + r.forward_returns[k] * (r.forward_returns.n || 0), 0);
  const vals = have.map((r) => r.forward_returns[k]);
  const rows = have.reduce((a, r) => a + (r.forward_returns.rows || 0), 0);
  return { sessions: have.length, names, rows, mean: names ? wsum / names : null,
           plain: vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null,
           best: vals.length ? Math.max(...vals) : null, worst: vals.length ? Math.min(...vals) : null };
};
// null-safe, because a run with no closed session reaches this with null and
// README used to say so as a known way for the script to throw.
// The page's own date format ('12 Aug 2026'), for matching a row by its session.
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
// The page prints every funnel count through commas() -> toLocaleString, so a
// comparison against String(n) is identical up to 999 and wrong from 1,000.
// That was a live landmine under the widening this rebuild is heading for:
// verified by setting the fixture's universe to 999 (134/134) and to 1,000
// (133/134). The `wide` variant has set size 5000 since it was written, with
// a comment saying "where the rebuild is heading", and passed throughout —
// because it never compared a printed number. Third instance of the class the
// 3.1 audit named: a docs/-facing check that cannot fail in the state it was
// written for.
const shown = (n) => Number(n).toLocaleString('en-US');
const fmtDay = (iso) => { const p = String(iso).slice(0, 10).split('-'); return `${Number(p[2])} ${MONTHS[Number(p[1]) - 1]} ${p[0]}`; };
const money = (v) => (v === null || v === undefined ? 'pending' : (v > 0 ? '+' : '') + v.toFixed(2) + '%');
const near = (a, b, tol) => Math.abs(a - b) <= tol;
// Mirrors the page's own plural(). A second copy, deliberately: a test has to
// state its expectation in its own terms, and reconstructing the sentence by
// calling the page's own function would assert only that the page agrees with
// itself. The version this replaces hard-coded "bursts" and would have failed
// on the first night the scan found exactly one.
const plural = (n, one, many) => n + ' ' + (n === 1 ? one : (many || one + 's'));
// An evidence block carries one entry per horizon in a list keyed by
// `horizon`, not an object keyed d1/d3/d5 — those names mean "a number, the
// return" on every candidate row in the same file, and one key name over two
// shapes is what the suite's own contract walker rejected.
const at = (outcomes, h) => (outcomes || []).find((e) => e && e.horizon === h)
  || { horizon: h, mean: null, n: 0, best: null, worst: null, in_band: 0 };

// --- the run opens ---------------------------------------------------------
// "auto" follows the runner's OS, which in headless Chromium is light, so each
// theme is pinned explicitly rather than assumed.
await open();
await setTheme('dark');
await page.waitForTimeout(200);
ok('the run opens', (await page.textContent('#h1')) !== 'Snapshot unavailable', await page.textContent('#h1'));
ok('the headline states the funnel',
  (await page.textContent('#h1')) === `${plural(run.bursts, 'burst')}, ${run.scored} scored, ${run.shortlist_size} on the shortlist`,
  await page.textContent('#h1'));

// --- the funnel ------------------------------------------------------------
// Four tiles could state the four numbers but not the shape between them. The
// figure claims a shared linear scale and a named cause for every loss, so the
// checks are that the bars are in proportion to the counts and that the drops
// are the subtractions a reader would do.
const funnel = await page.evaluate(() => ({
  kept: [...document.querySelectorAll('#funnel-chart .seg-kept')].map((r) => +r.getAttribute('width')),
  lost: document.querySelectorAll('#funnel-chart .seg-lost').length,
  rows: [...document.querySelectorAll('#funnel-table tbody tr')].map((r) => [...r.children].map((c) => c.textContent.trim()))
}));
ok('the funnel draws every stage from the universe to the shortlist',
  funnel.kept.length === STAGES.length && funnel.rows.length === STAGES.length && funnel.lost === STAGES.length - 1,
  `${funnel.kept.length} bars, ${funnel.rows.length} rows, ${funnel.lost} drop segments`);
ok('and the stages are the run\'s own numbers, named and in order',
  funnel.rows.every((r, i) => r[0].startsWith(STAGES[i][0]) && r[1] === shown(STAGES[i][1])),
  JSON.stringify(funnel.rows.map((r) => r[1])) + ' vs ' + JSON.stringify(STAGES.map((x) => x[1])));
ok('every drop is the difference between the two stages either side of it',
  funnel.rows.every((r, i) => r[3] === (i === 0 ? '\u2014' : '\u2212' + shown(STAGES[i - 1][1] - STAGES[i][1]))),
  JSON.stringify(funnel.rows.map((r) => r[3])));
// The point of the figure: 5 of 230 has to LOOK like 5 of 230. A per-row
// rescale would draw five near-equal bars and hide the attrition entirely.
const scale = funnel.kept.map((w, i) => w / funnel.kept[0]);
ok('the stages share one scale, so the narrowing is visible and not just stated',
  scale.every((f, i) => i === 0 || f <= scale[i - 1] + 0.001)
  && STAGES.every(([, v], i) => (v / STAGES[0][1]) * funnel.kept[0] < 4 || near(scale[i], v / STAGES[0][1], 0.02)),
  scale.map((f) => f.toFixed(3)).join(' '));
// The universe row's own note names what stopped printing, from the block
// the pipeline wrote: every name the fixture carries, the count and the
// threshold it applied. Read off the DOM, not the fixture twice.
const stopped = REAL.run.stopped_printing;
// The words are src/emailer.py's: a dated name and a dateless one, which is a
// symbol the feed returned no bar for at all.
const stoppedWord = (n) => (typeof n.last === 'string' ? n.ticker + ' (since ' + n.last + ')' : n.ticker + ' (no bar at all)');
ok('the universe row names the symbols that have stopped printing, and the threshold the run applied',
  stopped && stopped.count > 0 && stopped.names.every((n) => funnel.rows[0][4].includes(stoppedWord(n)))
  && funnel.rows[0][4].includes(stopped.count + ' names have not printed for more than ' + stopped.after_sessions + ' sessions'),
  funnel.rows[0][4]);
ok('a name the feed returned no bar for at all is printed without a date, in the email\'s words',
  stopped.names.some((n) => n.last === null && n.sessions_behind === null)
  && funnel.rows[0][4].includes(' (no bar at all)') && !funnel.rows[0][4].includes('since null'),
  funnel.rows[0][4]);
const worstDrop = STAGES.slice(1).map(([name, v], i) => ({ name, lost: STAGES[i][1] - v }))
  .reduce((a, b) => (b.lost > a.lost ? b : a));
ok('the page names where the attrition actually is',
  (await page.textContent('#funnel-hint')).includes(shown(worstDrop.lost))
  && (await page.textContent('#funnel-hint')).includes(worstDrop.name),
  `${worstDrop.lost} at ${worstDrop.name}`);

// The page's honesty about ITSELF. README claims the page "says so at the top of
// itself"; until now nothing asserted it, and a fabricated run rendering as a
// real one is the worst thing this page could do.
const fixtureBanner = await page.evaluate(() => {
  const b = document.getElementById('fixture-banner');
  return { shown: b && !b.hidden, text: ((b && b.textContent) || '').replace(/\s+/g, ' ').trim() };
});
ok('fabricated data is disclosed on the page, not only in the README',
   run.fixture ? (fixtureBanner.shown && /sample data/i.test(fixtureBanner.text))
               : !fixtureBanner.shown,
   fixtureBanner.text.slice(0, 60));
// ...and disclosed WITHOUT the sentence it used to carry: "the pipeline does
// not write docs/data.json yet" has been false since step 9, and README says
// the opposite two sections away. The true half -- this file is a fixture and
// none of it is a signal -- is what the banner is for.
ok('and the disclosure does not deny that the pipeline writes this file',
   !/does not write/i.test(fixtureBanner.text)
   && /trading signal/i.test(fixtureBanner.text),
   fixtureBanner.text.slice(0, 120));

// --- the defect this contract exists to stop -------------------------------
// The pipeline used to archive five names. A page that shows five names cannot
// be used to judge the screener, so the table must hold every scored candidate.
const rows = await page.locator('#scores-table tbody tr').count();
ok('every scored candidate is in the table, not just the shortlist',
  rows === run.scored && rows === REAL.candidates.length && rows > run.shortlist_size,
  `${rows} rows, run.scored=${run.scored}, shortlist=${run.shortlist_size}`);
ok('the shortlist is the shortlist', (await page.locator('#shortlist .pick').count()) === run.shortlist_size);
ok('the page says how many were scored and how many are shown',
  /All 25 of the 25 candidates/.test(await page.textContent('#scores-hint')), await page.textContent('#scores-hint'));

// Nothing the scan found may quietly disappear.
const gatedRows = await page.locator('#gated-table tbody tr').count();
ok('the scored rows and the not-scored rows account for every burst',
  rows + gatedRows === run.bursts, `${rows} + ${gatedRows} = ${rows + gatedRows}, bursts = ${run.bursts}`);
ok('and the page says so in words',
  (await page.textContent('#gated-hint')).includes(`accounts for all ${run.bursts} bursts`),
  await page.textContent('#gated-hint'));
// The words are the EMAIL's words, not this table's own: it used to say
// 'passed, over the call cap' beside a streak line on the same page saying
// 'the scoring cap was already full'. One mechanism, two names, neither
// explained. Asserted as the sentence a reader sees, so a surface drifting
// back to its own vocabulary fails here.
// Scoped to the WHY cell, not the row: a row's streak line says what happened
// to the name LAST time, in these same words, so a row-level match counts the
// wrong thing and reports a number that happens to be right on some fixtures.
const whyCells = await page.$$eval('#gated-table tbody td.col-why', (tds) => tds.map((t) => t.textContent.trim()));
ok('the reason a burst went unscored is on its row, in the words the email uses',
  whyCells.filter((t) => t === 'passed the gate, but the run had already sent its limit of candidates to Claude').length
    === REAL.gated_out.filter((g) => g.reason === 'score_cap').length,
  `${whyCells.length} cells, ${REAL.gated_out.filter((g) => g.reason === 'score_cap').length} capped`);
ok('and the rejected ones say rejected, the same way',
  whyCells.filter((t) => t === 'rejected at the 2LYNCH gate').length
    === REAL.gated_out.filter((g) => g.reason === 'lynch_gate').length);
// A veto is the third reason and must not be counted as either of the other
// two: this check used to read "not score_cap" as "rejected by the checklist",
// which is the opposite of what a veto says about a name that passed 6/6.
ok('and a burst refused by an absolute rule says so, not that the checklist rejected it',
  whyCells.filter((t) => t.startsWith('refused outright')).length
    === REAL.gated_out.filter((g) => String(g.reason).startsWith('veto_')).length);
ok('and the code keeps its casing through a sheet that lowercases chips',
  (await page.$eval('#gated-table tbody td.col-why .sc-chip',
    (el) => getComputedStyle(el).textTransform)) === 'none');

// The commit that added the veto put its vocabulary in FOUR places on this
// page -- LAST_OUTCOME, OUTCOME_SHORT, the gated-hint sentence and the funnel
// caption -- and pinned exactly one of them. An audit made each of the other
// three say "rejected at the gate" about a burst that may have passed 6/6 and
// got a green suite and 129/129 here. These are the other three.
//
// Each asserts the WORDS a reader sees, not that a key exists: the Python
// guard that a reason word is present in both maps passed throughout, because
// a key can be present and say the wrong thing.
const hint = await page.textContent('#gated-hint');
const vetoedRows = REAL.gated_out.filter((g) => String(g.reason).startsWith('veto_')).length;
// The fourth reason, on the same three surfaces the veto was pinned on:
// the why cell, the gated hint (with the floor in dollars, read off
// run.liquidity rather than retyped), and the funnel caption.
const illiquidRows = REAL.gated_out.filter((g) => g.reason === 'liquidity_floor').length;
const floorDollars = '$' + Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(REAL.run.liquidity.floor);
ok('a burst the liquidity floor refused says so in its why cell, not that the gate rejected it',
  illiquidRows > 0 && whyCells.filter((t) => t.startsWith('refused by the liquidity floor')).length === illiquidRows,
  `${illiquidRows} liquidity rows; cells: ${whyCells.filter((t) => t.startsWith('refused by the liquidity')).length}`);
ok('and the sentence above the gated table gives the floor its own clause, with the dollar figure the run recorded',
  hint.includes(`${illiquidRows} below the liquidity floor (${floorDollars}/day`)
  && hint.includes(`the ${REAL.run.liquidity.pctile}th percentile`),
  hint.slice(0, 200));
ok('and that clause does not fold the liquidity rows into the checklist count',
  hint.includes(`${REAL.gated_out.filter((g) => g.reason === 'lynch_gate').length} rejected at the`),
  hint.slice(0, 200));
ok('and the sentence above the gated table gives the veto its own clause',
  vetoedRows === 0
  || (hint.includes(`${vetoedRows} refused by an absolute rule`) && !/\d+ refused at the/.test(hint)),
  hint);
ok('and that clause does not fold the vetoed rows into the checklist count',
  vetoedRows === 0
  || hint.includes(`${REAL.gated_out.filter((g) => g.reason === 'lynch_gate').length} rejected at the`),
  hint);

const caption = (await page.$$eval('#funnel-table tbody tr', (rows) => rows.map((r) => r.textContent))).join(' ');
// The email's funnel gained this cut in the same round -- it went "Passed
// 2LYNCH gate: 54" straight to "Shortlisted: 1" and never said the 29 names
// that cleared the checklist were not looked at. Both surfaces name it "the
// N-call cap" with the run's own number, and neither had that phrase pinned,
// which is how two vocabularies for one mechanism get here in the first place.
ok('the funnel names the call cap with the number the run actually applied',
  caption.includes(REAL.run.score_cap + '-call cap'),
  `score_cap = ${REAL.run.score_cap}`);

ok('the funnel says an absolute rule can cut a name at the gate stage, when the run applied one',
  ((REAL.run.gate || {}).vetoes || []).length && caption.includes('refused by an absolute rule'),
  `gate.vetoes = ${JSON.stringify((REAL.run.gate || {}).vetoes)}`);
// And the other side of that guard, which is the side it exists for. Run
// against a snapshot carrying no gate.vetoes at all: naming a rule that run
// never applied is the confidently-false sentence, and asserting only the
// positive branch left the guard deletable with everything green.
ok('the funnel caption names the floor at the stage it cuts, with the same dollar figure',
  caption.includes(`below the liquidity floor (${floorDollars}/day`),
  caption.slice(0, 200));
await open('/v/nothreshold/');
const noThresholdNote = (await page.$$eval('#funnel-table tbody tr', (rows) => rows.map((r) => r.textContent)))[0];
ok('a stopped-printing block with no threshold names its symbols and states no number',
  stopped.names.every((n) => noThresholdNote.includes(stoppedWord(n)))
  && noThresholdNote.includes(stopped.count + ' names have stopped printing')
  && !/undefined|NaN/.test(noThresholdNote),
  noThresholdNote.slice(0, 200));
await open('/v/noliquidity/');
const noLiqCaption = (await page.$$eval('#funnel-table tbody tr', (rows) => rows.map((r) => r.textContent))).join(' ');
const noLiqHint = await page.textContent('#gated-hint');
const noLiqLadder = await page.$$eval('#control-table tbody tr', (rows) => rows.map((r) => r.textContent));
ok('a snapshot from before rule 6 was archived is not told it enforced a floor',
  !noLiqCaption.includes('liquidity floor') && !noLiqHint.includes('liquidity floor'),
  `caption: ${noLiqCaption.includes('liquidity floor')}, hint: ${noLiqHint.includes('liquidity floor')}`);
await open('/v/noliquidityladder/');
const ladderWithout = await page.$$eval('#control-table tbody tr', (rows) => rows.map((r) => r.textContent));
ok('and its ladder has five rows, not a sixth for a population the file does not hold',
  ladderWithout.length === 5 && !ladderWithout.some((l) => /illiquid/.test(l)) && !noLiqLadder.some((l) => /illiquid/.test(l)),
  `${ladderWithout.length} rows on a rendered ladder`);
await open('/v/nobenchmark/');
const ladderNoBench = await page.$$eval('#control-table tbody tr', (rows) => rows.map((r) => r.textContent));
ok('a record from before the benchmark shows no universe rung and its verdict says nothing about one',
  ladderNoBench.length === 5 && !ladderNoBench.some((l) => /universe/.test(l))
  && !/buying anything in the universe/.test(await page.textContent('#control-verdict')),
  `${ladderNoBench.length} rows`);
await open('/v/fullbenchmark/');
const benchVerdict = await page.textContent('#control-verdict');
ok('with enough paired setups the verdict compares the picks to the universe, over the sessions they came from',
  /Against buying anything in the universe on the same days — \+2\.00% equal-weight, paired with the 40 setups those picks are/.test(benchVerdict)
  && /the picks did better, by 4\.00%/.test(benchVerdict) && /flatters the benchmark/.test(benchVerdict),
  benchVerdict.slice(benchVerdict.indexOf('Against'), benchVerdict.indexOf('Against') + 140));
// The benchmark is on the SAME basis as the picks it is compared with. Its
// open-basis mean is deliberately different here, so a sentence reading the
// close basis under the open label fails rather than merely looking odd.
await page.click('#basis-tabs .sc-tab[data-basis="open"]');
const benchOpen = await page.textContent('#control-verdict');
ok('and it follows the basis switch, naming the benchmark measured the same way as the picks',
  /paired with the 39 setups/.test(benchOpen) && /\+0\.50% equal-weight/.test(benchOpen)
  && !/\+2\.00% equal-weight/.test(benchOpen) && /next session.s open/.test(benchOpen),
  benchOpen.slice(benchOpen.indexOf('Against'), benchOpen.indexOf('Against') + 120));
await page.click('#basis-tabs .sc-tab[data-basis="close"]');
ok('and says the names under each night\u2019s liquidity floor are left out of it',
  /Names under each night\u2019s liquidity floor are left out of it\. The universe is a curated/.test(benchVerdict),
  benchVerdict.slice(benchVerdict.indexOf('Names under'), benchVerdict.indexOf('Names under') + 80) || 'no floor sentence');
await open('/v/unflooredbenchmark/');
const unflooredVerdict = await page.textContent('#control-verdict');
const universeRowOf = async () => page.$$eval('#control-table tbody tr', (rows) => {
  const r = rows.find((x) => x.textContent.startsWith('the universe'));
  return r ? r.textContent.replace(/\s+/g, ' ') : '';
});
const unflooredRow = await universeRowOf();
const unflooredHint = await page.textContent('#control-hint');
ok('a rung measured with no floor says the thin names are in, on the sentence, on the row and in the card\'s own hint',
  /It counts every name that traded, the ones under the liquidity floor included/.test(unflooredVerdict)
  && /measured with no floor/.test(unflooredRow) && !/at or above/.test(unflooredRow)
  // and the hint no longer states the opposite three sentences up: it used
  // to say "left out for the same reason" whatever the record held.
  && /measured with no floor/.test(unflooredHint) && !/left out for the same reason/.test(unflooredHint)
  // both causes, because the block cannot tell them apart
  && /rule 6 was off/.test(unflooredRow) && /rule 6 was off/.test(unflooredVerdict),
  unflooredHint.slice(unflooredHint.indexOf('The universe row'), unflooredHint.indexOf('The universe row') + 150));
await open('/v/mixedfloor/');
const mixedVerdict = await page.textContent('#control-verdict');
const mixedRow = await universeRowOf();
const mixedHint = await page.textContent('#control-hint');
ok('and a record straddling the change says for how many pairings each is true, on the sentence, the row and the hint',
  /left out of it for 30 of the 40 measured pairings; the other 10 were measured with no floor/.test(mixedVerdict)
  && /for the 30 pairings measured with one; the other 10 were measured with no floor/.test(mixedRow)
  && /and in for the 10 measured with none/.test(mixedHint),
  mixedVerdict.slice(mixedVerdict.indexOf('Names under'), mixedVerdict.indexOf('Names under') + 140));
await open('/v/oldevidence/');
const oldEvRow = await universeRowOf();
await page.click('#basis-tabs .sc-tab[data-basis="open"]');
const oldEvHint = await page.textContent('#predict-hint');
const oldEvSep = await page.$$eval('#predict-table tbody tr td:nth-child(6)', (tds) => tds.map((t) => t.textContent.trim()));
ok('a record from before round 9 says its separation is unmeasured on the open basis, not that no check has enough setups',
  /written before the separation was measured from the next session\u2019s open/.test(oldEvHint) && !/No check yet has/.test(oldEvHint)
  && oldEvSep.length > 0 && oldEvSep.every((t) => t === 'not measured'),
  `${oldEvSep.join('|')} :: ${oldEvHint.slice(oldEvHint.indexOf('This record'), oldEvHint.indexOf('This record') + 60)}`);
const oldEvHintControl = await page.textContent('#control-hint');
ok('and its universe rung does not claim a floor the record never applied, on the row or in the hint',
  /predates the floor in the benchmark/.test(oldEvRow) && !/at or above/.test(oldEvRow)
  && /measured with no floor/.test(oldEvHintControl) && !/left out for the same reason/.test(oldEvHintControl),
  oldEvRow.slice(0, 120));
await page.click('#basis-tabs .sc-tab[data-basis="close"]');
await open('/v/thinbenchmark/');
const thinBench = await page.textContent('#control-verdict');
const thinRung = await page.$$eval('#control-table tbody tr', (rows) => {
  const r = rows.find((x) => x.textContent.startsWith('the universe'));
  return r ? r.textContent.replace(/\s+/g, ' ') : '';
});
ok('a benchmark under the floor is shown on the rung and refused as a rate in the verdict',
  !/Against buying anything/.test(thinBench) && /the picks did better/.test(thinBench)
  && /\+2\.00%/.test(thinRung) && /too few to read as a rate|not enough data/.test(thinRung),
  `verdict: ${thinBench.slice(0, 60)} | rung: ${thinRung.slice(0, 90)}`);
// The clause joiner, on the two nights the fixture's own ordering hid.
const floorClause = `(${floorDollars}/day, the ${REAL.run.liquidity.pctile}th percentile)`;
// Round 8. A mean across runs is a mean over one strategy only while the
// record holds one set of rules, and the page says so when it does not.
const restNote = await page.textContent('#rules-note');
// The hidden PROPERTY, not isHidden(): an empty paragraph has no box either
// way, so a note left permanently shown-but-empty passed a visibility check.
const restHidden = await page.$eval('#rules-note', (n) => n.hidden);
ok('a record made under one set of rules says nothing about blended screeners',
  restNote.trim() === '' && restHidden === true,
  `${JSON.stringify(restNote)} hidden=${restHidden}`);
await open('/v/rulesdrift/');
const driftNote = await page.textContent('#rules-note');
ok('a record spanning two sets of rules says so and names the keys that moved',
  /spans 2 sets of rules/.test(driftNote) && driftNote.includes('gate.min_lynch_passes')
  && driftNote.includes('scan.min_gain_pct') && /averages more than one screener/.test(driftNote),
  driftNote.slice(0, 150));
await open('/v/norules/');
const noRulesNote = await page.textContent('#rules-note');
ok('and runs from before the fingerprint are counted apart, not as agreement',
  new RegExp(VARIANTS.norules().runs.length + ' runs in the record predate').test(noRulesNote)
  && !/spans/.test(noRulesNote) && /not the same as knowing it was this one/.test(noRulesNote),
  noRulesNote.slice(0, 150));
await open('/v/newreason/');
const newWhy = await page.$eval('#gated-table tbody tr:first-child td.col-why', (td) => td.textContent.trim());
ok('a reason word this page does not know is said as that, never as a gate rejection',
  /not one this page knows/.test(newWhy) && newWhy.includes('veto_gap_too_wide') && !/2LYNCH gate/.test(newWhy),
  newWhy);
await open('/v/nocap/');
const noCapHint = await page.textContent('#gated-hint');
ok('with no crowded-out rows the liquidity clause is last and keeps its own comma',
  noCapHint.includes(`2 below the liquidity floor ${floorClause} and never measured against it.`)
  && / whatever the checklist said and 2 below/.test(noCapHint),
  noCapHint.slice(0, 220));
await open('/v/onlyfloor/');
const onlyFloorHint = await page.textContent('#gated-hint');
ok('and alone it is one clause, comma and space intact',
  onlyFloorHint.includes(`2 bursts the scan found but no score exists for: 2 below the liquidity floor ${floorClause} and never measured against it.`),
  onlyFloorHint.slice(0, 220));
await open('/f/fixture/');
const streakTitle = await page.$eval('#gated-table .sc-note[title]', (n) => n.getAttribute('title'));
ok('the streak disclosure on the page names all four ways a burst goes unscored',
  ['the checklist rejected', 'an absolute rule refused', 'the liquidity floor refused', 'the call cap crowded']
    .every((phrase) => streakTitle.includes(phrase)),
  streakTitle.slice(0, 160));
const dollarCells = await page.$$eval('#gated-table tbody tr', (rows) => rows.map((r) => [r.querySelector('td .sc-case').textContent, r.querySelectorAll('td')[6].textContent.trim()]));
// The page's big() rule, mirrored: the same rule src/emailer.py's
// compact_dollars() follows, and tests/test_docs_are_true.py holds the two
// to each other by executing the page's own function.
const bigJs = (v) => (v >= 1e9 ? (v / 1e9).toFixed(1) + 'B' : v >= 1e6 ? (v / 1e6).toFixed(1) + 'M' : v >= 1e3 ? (v / 1e3).toFixed(0) + 'k' : String(v));
ok('every gated row prints the dollar volume rule 6 judged, beside the floor the hint names',
  dollarCells.length === REAL.gated_out.length
  && dollarCells.every(([t, cell]) => cell === '$' + bigJs(REAL.gated_out.find((g) => g.ticker === t).dollar_volume)),
  dollarCells.slice(0, 3).map((c) => c.join(' ')).join(' | '));
await open('/v/novetoes/');
const oldCaption = (await page.$$eval('#funnel-table tbody tr', (rows) => rows.map((r) => r.textContent))).join(' ');
const oldHint = await page.textContent('#gated-hint');
ok('and says nothing of the kind about a run that had no absolute rule to apply',
  !oldCaption.includes('refused by an absolute rule')
  && !oldHint.includes('refused by an absolute rule'),
  oldCaption.replace(/\s+/g, ' ').slice(0, 90));

// The same class one field over. `gate.total_checks` is the checklist's SIZE,
// and the page concatenates it into three sentences: the funnel's "why" and
// "note", and the gated table's "rejected at the ≥3/6 2LYNCH gate". The
// producer emits null there when nothing measured a checklist that night, and
// every one of those three read "3/null" and "under 3 of null checks" — a
// threshold against a total that does not exist, stated as fact, with the
// suite and every check here green because no source could hold a null.
await open('/v/nogatetotal/');
const nullTexts = [
  await page.textContent('#funnel-hint'),
  (await page.$$eval('#funnel-table tbody tr', (rows) => rows.map((r) => r.textContent))).join(' '),
  await page.textContent('#gated-hint'),
  await page.textContent('#checks-hint')
];
ok('a run that never measured the checklist prints no gate size at all',
  nullTexts.every((t) => !/null|undefined|NaN/.test(t)),
  nullTexts.find((t) => /null|undefined|NaN/.test(t)) || 'clean');
// And the other half, which is what stops the fix being "delete the sentence":
// the pass threshold IS known on such a run and must survive.
ok('and still names the threshold it does know, which is the pass count',
  nullTexts.slice(1).every((t) => t.includes('≥' + VARIANTS.nogatetotal().run.gate.min_lynch_passes)
                                  || t.includes('under ' + VARIANTS.nogatetotal().run.gate.min_lynch_passes)),
  nullTexts.slice(1).map((t) => t.replace(/\s+/g, ' ').slice(0, 60)).join(' | '));
await open('/f/fixture/');

// --- the streak line, on the one state it used to get wrong -----------------
// A day number is withheld whenever the chain of appearances reaches the
// oldest run in the file, which is exactly what an UNBROKEN streak does. So
// the longer a name has been bursting every session, the more certainly its
// day is null -- and this page said "streak unknown" over it while saying
// "day 2" over a name that had taken a week off. The record's own span is
// what makes the narrower answer sayable; assert the sentence, because the
// email says the same one and a reader gets both.
const unknownDay = REAL.candidates.filter((c) => (c.streak || {}).day === null);
const streakLines = await page.$$eval('#shortlist .facts',
  (ds) => ds.map((d) => [...d.querySelectorAll('div')]
    .filter((x) => x.querySelector('dt') && x.querySelector('dt').textContent === 'this setup')
    .map((x) => x.querySelector('dd').textContent.trim())[0]));
ok('a shortlisted pick states its streak, whatever the streak is',
  streakLines.length === run.shortlist_size && streakLines.every(Boolean),
  streakLines.join(' | ').slice(0, 90));
ok('an unknown day reports the record it is unknown over, not the word unknown',
  unknownDay.length === 0 || (await page.locator('#scores-table tbody tr',
    { hasText: 'sessions in the record, which begins' }).count()) === unknownDay.length,
  `${unknownDay.length} rows carry a null day`);
ok('and never renders as day 1, which is a claim about the market',
  (await page.locator('#scores-table tbody tr', { hasText: 'day unknown' })
    .locator('text=new setup').count()) === 0);
// The two wordings that differed from the email on rows that agreed otherwise:
// this page dropped the verdict off a scored last appearance ("scored 7.5/10"
// against the email's "scored 7.5/10 B+") and said "day 3, since" where the
// email said "day 3 of this setup, since".
const withVerdict = REAL.candidates.filter((c) => {
  const st = c.streak || {};
  return st.last_score !== null && st.last_score !== undefined && st.last_verdict
    && (!st.last_outcome || st.last_outcome === 'scored');
});
ok('a scored last appearance keeps its verdict, the way the email prints it',
  withVerdict.length > 0 && (await Promise.all(withVerdict.map((c) => page.locator(
    '#scores-table tbody tr',
    { hasText: `scored ${c.streak.last_score.toFixed(1)}/10 ${c.streak.last_verdict}` }
  ).count()))).every((n) => n > 0),
  `${withVerdict.length} rows carry a scored last appearance with a verdict`);
const repeats = REAL.candidates.filter((c) => (c.streak || {}).day > 1);
ok('and a repeat says which SETUP it is day N of, in the email\'s words',
  repeats.length > 0 && (await page.locator('#scores-table tbody tr',
    { hasText: 'of this setup, since' }).count()) === repeats.length,
  `${repeats.length} repeats`);

// --- provenance ------------------------------------------------------------
// A fallback score is checklist arithmetic. It can outrank a real score, and
// in this fixture it does, so it must be labelled everywhere it appears.
const chips = await page.locator('#scores-table tbody .sc-chip--warn').count();
ok('every fallback score is labelled in the table', chips === fallbacks.length && chips === run.scored_by.fallback,
  `${chips} labelled, ${fallbacks.length} in the data`);
ok('no Claude score is labelled a fallback',
  (await page.locator('#scores-table tbody tr', { hasText: 'checklist fallback' }).count()) === fallbacks.length);
const inShort = fallbacks.filter((c) => c.rank <= run.shortlist_size);
ok('a fallback on the shortlist is called out above the fold',
  !inShort.length || (!(await page.locator('#fallback-callout').isHidden())
    && (await page.textContent('#fallback-body')).includes(inShort[0].ticker)),
  await page.textContent('#fallback-figure'));
ok('and marked on its own shortlist card',
  (await page.locator('#shortlist .pick', { hasText: 'checklist fallback' }).count()) === inShort.length);
// The checklist is the reason a candidate is here at all, so its six measured
// values have to be reachable — not just the six pass/fail letters.
const first = REAL.candidates[0];
await page.locator('#shortlist .pick').first().locator('.sc-details summary').click();
await page.waitForTimeout(150);
const detail = await page.locator('#shortlist .pick').first().locator('.sc-details tbody tr');
ok('the 2LYNCH checklist opens with a row per check',
  (await detail.count()) === first.lynch_total, `${await detail.count()} rows`);
ok('and each row carries what was actually measured',
  (await detail.first().textContent()).includes(first.lynch_detail[0].value),
  (await detail.first().textContent()).replace(/\s+/g, ' ').trim());
ok('a failed check is not dressed as a passed one',
  (await page.locator('#shortlist .pick').first().locator('.sc-details tbody tr', { hasText: 'fail' }).count())
    === first.lynch_detail.filter((x) => !x.pass).length);

// Bonde's two measurements, on the card rather than only in the prompt. The
// up-day cell is asserted through a row whose value is ZERO: rendered through
// the page's own number formatter it would print an em dash, which is what the
// page says when a run predates the rule — two opposite facts, one glyph.
// Scoped to the SHORTLIST, because that is where the assertion looks. It used
// to search all 25 candidates for a row at zero and then look for the text
// among the 5 picks, so a fixture whose zeros sat outside the top five turned
// CI red while the page was entirely correct -- and said "20 rows at zero".
const shortlistRows = REAL.candidates.filter((c) => c.rank <= run.shortlist_size);
const flatPicks = shortlistRows.filter((c) => (c.context || {}).consecutive_up_days === 0).length;
const cardText = await page.locator('#shortlist .pick').first().textContent();
ok('a scored pick says how many up days it burst after, counting zero as an answer',
  flatPicks > 0
  && (await page.locator('#shortlist .pick', { hasText: '0 up days' }).count()) === flatPicks,
  `${flatPicks} of the ${shortlistRows.length} shortlist picks burst out of a flat base`);
// The VALUE, not the label: this tested /worst base day/i, which is a string
// hard-coded in pick()'s facts array, so the page could print an em dash for
// every row and pass. The number comes out of the data the page was given.
const firstPick = REAL.candidates.find((c) => c.rank === 1);
ok('and what the worst day in its base was, which the screener measures and does not act on',
  cardText.includes(`${firstPick.context.worst_base_day_pct.toFixed(1)}%`),
  `expected ${firstPick.context.worst_base_day_pct}% in the #1 card`);

const blind = REAL.candidates.filter((c) => c.provenance.source === 'claude' && !c.provenance.chart_seen);
ok('a score made without the chart says so',
  (await page.locator('.pick', { hasText: 'scored without the chart' }).count())
    === blind.filter((c) => c.rank <= run.shortlist_size).length, `${blind.length} in the data`);

// --- the chart -------------------------------------------------------------
ok('the chart draws a bar per candidate', (await page.locator('#scores-chart .bar').count()) === run.scored);
ok('it has a legend', (await page.locator('#scores-legend span').count()) === 2);
const tones = await page.evaluate(() => {
  const f = [...document.querySelectorAll('#scores-chart .bar')].map((b) => getComputedStyle(b).fill);
  return { distinct: [...new Set(f)].length, blank: f.filter((c) => !c || c === 'none' || c === 'rgba(0, 0, 0, 0)').length };
});
ok('the two kinds of score are two colours', tones.distinct === 2 && tones.blank === 0, JSON.stringify(tones));
// The chart and the table are the same numbers; a reader compares them.
const agree = await page.evaluate(() => {
  const bars = [...document.querySelectorAll('#scores-chart .bar-value')].map((t) => parseFloat(t.textContent));
  const cells = [...document.querySelectorAll('#scores-table tbody tr')].map((r) => parseFloat(r.children[1].textContent));
  return bars.length === cells.length && bars.every((v, i) => v === cells[i]);
});
ok('the chart and the table say the same thing', agree);

// --- the charts this checkout does not carry -------------------------------
// /docs/charts/ is gitignored and never committed, so on GitHub Pages every
// chart path 404s permanently, and in a fresh checkout it 404s until a local
// evening run writes one. Either way the reader must get a frame that explains
// it, not a broken image icon.
const shortWithPath = REAL.candidates.filter((c) => c.rank <= run.shortlist_size && c.chart).length;
ok('a missing chart PNG degrades to an explained frame, not a broken image',
  (await page.locator('#shortlist .sc-frame--empty').count()) === run.shortlist_size
  && (await page.locator('#shortlist img.shot').count()) === 0,
  `${shortWithPath} of ${run.shortlist_size} picks name a chart file`);
ok('and a chart that failed to render says why',
  (await page.locator('#shortlist .pick', { hasText: 'no chart' }).count()) === run.shortlist_size);
ok('every chart path on the shortlist was really requested and really 404d',
  chart404.size === shortWithPath, `${chart404.size} requested, ${shortWithPath} named`);

// --- what is not known yet reads as not known ------------------------------
ok('forward returns that do not exist read as pending, not as zero or blank',
  (await page.locator('#scores-table tbody tr:first-child td:nth-child(9)').textContent()).trim() === 'pending');
ok('the pinned first column names the row it pins',
  (await page.textContent('#scores-table thead th:first-child')).trim() === 'ticker'
  && (await page.locator('#scores-table tbody tr:first-child td:first-child').textContent()).includes(REAL.candidates[0].ticker));
ok('the notice stays down on a clean run', await page.locator('#notice').isHidden());
ok('the history top row is this run',
  (await page.locator('#runs-table tbody tr:first-child').textContent()).includes('this run'));
const histAgree = await page.evaluate(() => {
  const c = document.querySelectorAll('#runs-table tbody tr')[0].children;
  return { bursts: c[2].textContent.trim(), scored: c[3].textContent.trim() };
});
ok('and it agrees with the tiles above it',
  histAgree.bursts === String(run.bursts) && histAgree.scored === String(run.scored), JSON.stringify(histAgree));

// --- which 2LYNCH check is doing the gating --------------------------------
// The view's whole claim is that it looks at EVERY burst. A rate over the
// scored candidates alone would be survivorship bias with a percentage sign on
// it: all 25 of them cleared the gate, so the names a check rejected are
// exactly the ones missing. These check the denominators, not the picture.
const checks = await page.evaluate(() => ({
  bars: [...document.querySelectorAll('#checks-chart .seg-kept')].map((r) => +r.getAttribute('width')),
  track: [...document.querySelectorAll('#checks-chart .seg-lost')].map((r) => +r.getAttribute('width')),
  rows: [...document.querySelectorAll('#checks-table tbody tr')].map((r) => [...r.children].map((c) => c.textContent.trim())),
  bias: !document.getElementById('checks-bias').hidden
}));
ok('a pass rate for each of the six checks',
  checks.rows.length === CHECKS.length && checks.bars.length === CHECKS.length,
  `${checks.rows.length} rows, ${checks.bars.length} bars, ${CHECKS.length} checks`);
ok('the rates are taken over every burst the scan found, not just the scored',
  checks.rows.every((r, i) => r[2].endsWith(`of ${CHECKS[i].total}`) && CHECKS[i].total === run.bursts),
  JSON.stringify(checks.rows.map((r) => r[2])));
ok('and the checklist split accounts for all of them',
  checks.rows.every((r, i) => r[3].endsWith(`of ${CHECKS[i].ctotal}`) && r[4].endsWith(`of ${CHECKS[i].ftotal}`))
  && CHECKS[0].ctotal + CHECKS[0].ftotal === run.bursts,
  `${CHECKS[0].ctotal} cleared + ${CHECKS[0].ftotal} failed = ${run.bursts}`);
// The split is the CHECKLIST's, not the gate's, and the two are different
// numbers the moment a veto refuses a burst that passed its checks. This used
// to assert they were equal, which is how a 6/6 vetoed row would have been
// counted as evidence that the checks reject -- six passing checks on the
// failed side of a view whose whole subject is what the checks separate.
// Read off the RENDERED cell, not recomputed here. The first version of this
// check compared CHECKS[0].ctotal against run.passed_gate -- both Node-side
// arithmetic over the fixture -- so it was a fixture self-consistency
// assertion counted among the dashboard checks: stubbing checkStats() to
// return nothing failed six checks and left this one green.
// Indexed defensively for the reason the streak checks below already state:
// a page that stops rendering this table must FAIL here, not throw and take
// the remaining checks down with it. Stubbing checkStats() to return nothing
// did exactly that on the first version of this line.
const clearedCell = (checks.rows[0] || [])[3] || '';
const clearedShown = Number((clearedCell.match(/of (\d+)$/) || [])[1]);
// Since round 5 a second kind of row clears the checklist without being in
// run.passed_gate: one rule 6 refused before the gate saw it, whose pass
// count happens to clear the bar. It was never AT the gate, so it is on the
// cleared side of a split about check quality for the same reason a vetoed
// 6/6 is, and the fixture holds one of each kind on purpose.
const clearedButNeverGated = REAL.gated_out.filter((g) =>
  String(g.reason).startsWith('veto_')
  || (g.reason === 'liquidity_floor' && g.lynch_passes >= REAL.run.gate.min_lynch_passes)).length;
ok('and it is the checklist that splits them, not the gate a veto also guards',
  Number.isFinite(clearedShown) && clearedShown - run.passed_gate === clearedButNeverGated,
  `page shows ${clearedShown} cleared the checklist, run.passed_gate is ${run.passed_gate}, ` +
  `${clearedButNeverGated} cleared it without reaching the gate`);
ok('and the column says checklist, so the two are not read as one number',
  (await page.$$eval('#checks-table thead th', (th) => th.map((t) => t.textContent.trim())))
    .includes('cleared the checklist'));
ok('each row is the check it names',
  checks.rows.every((r, i) => r[0] === CHECKS[i].code)
  && checks.rows.every((r, i) => r[2].startsWith(`${Math.round(CHECKS[i].rate * 100)}%`)),
  JSON.stringify(checks.rows.map((r) => r[0] + ' ' + r[2])));
ok('the bars are the rates the table prints',
  checks.bars.every((w, i) => near(w / checks.track[i], CHECKS[i].rate, 0.02)),
  checks.bars.map((w, i) => (w / checks.track[i]).toFixed(2)).join(' '));
// The finding this view exists to produce, in words as well as bars. Looked up
// rather than indexed: a page that stops labelling either extreme must fail
// here, not throw and take the rest of the run down with it.
const weakRow = checks.rows.find((r) => r[6] === 'weakest separator');
// 'hardest check', not 'hardest gate': the chip kept the gate's word after the
// columns beside it were renamed, which was two vocabularies for one mechanism
// inside one table. This assertion is what noticed the rename, so it is doing
// its job -- but it is also the only thing pinning that chip's text.
const hardRow = checks.rows.find((r) => r[6] === 'hardest check');
ok('the check that barely separates is called out by name',
  !!weakRow && weakRow[0] === WEAKEST.code && (await page.textContent('#checks-hint')).includes(WEAKEST.code),
  `${WEAKEST.code} at ${(WEAKEST.gap * 100).toFixed(0)}pts separation, page said ${weakRow ? weakRow[0] : 'nothing'}`);
ok('and so is the one that rejects most',
  !!hardRow && hardRow[0] === HARSHEST.code
  && (await page.textContent('#checks-hint')).includes(`${Math.round(HARSHEST.rate * 100)}%`),
  `${HARSHEST.code} passes ${(HARSHEST.rate * 100).toFixed(0)}%, page said ${hardRow ? hardRow[0] : 'nothing'}`);
ok('no bias warning when the file really does carry every checklist', !checks.bias);

// --- has any of this made money yet ----------------------------------------
// A mean is the easiest number on this page to overstate. Three ways it could:
// counting a session that has not closed, weighting a 5-name session like a
// 25-name one, and calling five sessions a measurement.
const tiles = await page.evaluate(() => [...document.querySelectorAll('#returns-tiles .sc-tile')].map((t) => ({
  label: t.querySelector('.sc-tile__label').textContent.trim(),
  value: t.querySelector('.sc-tile__value').textContent.trim(),
  sub: t.querySelector('.sc-tile__sub').textContent.trim(),
  delta: t.querySelector('.sc-delta').textContent.trim(),
  chip: t.querySelector('.sc-chip').textContent.trim()
})));
const H1 = horizon('d1'), H5 = horizon('d5');
ok('one tile per horizon', tiles.length === 3 && tiles.map((t) => t.label).join('|') === '+1 day|+3 days|+5 days',
  tiles.map((t) => t.label).join('|'));
ok('the mean is weighted by how many names each session contributed',
  tiles[0].value === money(H1.mean),
  `page ${tiles[0].value}, weighted ${money(H1.mean)}, unweighted ${money(H1.plain)}`);
ok('a session that has not closed is not counted as one',
  tiles[0].sub.startsWith(`${H1.sessions} sessions`) && H1.sessions < REAL.runs.length,
  `${tiles[0].sub} — ${REAL.runs.length} runs in the file`);
// A +5d window closes later than a +1d one, so the longest horizon always has
// the fewest sessions in it. Treating the rest as zero would pull the mean
// toward 0.00% — that is the whole failure mode. Asserted against the mean
// over the sessions that DID close, with the count checked to be short of the
// file's runs so the comparison is not vacuous. The exact count was pinned at
// 1 and belonged to one generation of the fixture rather than to the rule.
ok('and the horizons that have not happened are not averaged in as zeros',
  tiles[2].value === money(H5.mean) && H5.sessions > 0 && H5.sessions < REAL.runs.length,
  `${tiles[2].value} from ${H5.sessions} of ${REAL.runs.length} sessions, ${H5.names} names`);
// n IS SETUPS, and the tile says so -- but it used to print what they were
// collapsed FROM only when the two numbers differed, which hid the ratio in
// the 1:1 case and said nothing about the collapse in any file where a run of
// repeats had just been folded into one setup.
ok('a setup count says what it was collapsed from, whatever the ratio',
  tiles.every((t, i) => {
    const h = [H1, horizon('d3'), H5][i];
    return !h.rows || t.sub.includes(`from ${h.rows} row`);
  }),
  tiles.map((t) => t.sub).join(' | '));
// One observation is not a range. It read "ran -0.42% to -0.42%" until it did.
ok('a single session is not dressed up as a spread',
  H5.sessions !== 1 || !/ran .* to /.test(tiles[2].delta), tiles[2].delta);
ok('five sessions is not called a measurement',
  tiles.every((t) => t.chip === 'not enough data')
  && (await page.textContent('#returns-hint')).includes('none of the three'),
  tiles.map((t) => t.chip).join(' | '));

// --- the record's own view, on a record one session long -------------------
// The fixture is one night old, so every horizon in its evidence block is
// null by construction. That is not an edge case: it is the state of the page
// on the first day it publishes anything, and every day after until five
// sessions have closed.
const EV = REAL.evidence;
ok('the page carries the record\'s own view of whether the score works', !!EV && !!EV.by_score,
  EV ? `${EV.by_score.length} score bands, ${EV.record.scored_setups} scored setups` : 'no evidence block');
const evOne = await page.evaluate(() => ({
  hidden: document.getElementById('evidence-card').hidden,
  empty: !document.getElementById('evidence-empty').hidden,
  body: !document.getElementById('evidence-body').hidden,
  text: document.getElementById('evidence-empty').textContent.trim()
}));
ok('with nothing closed yet it says so instead of drawing a flat line at zero',
  !evOne.hidden && evOne.empty && !evOne.body && /correct and empty/.test(evOne.text)
  && /not the same as a flat line at zero/.test(evOne.text), evOne.text.slice(0, 90));
ok('and it says how much is waiting rather than just that it is waiting',
  evOne.text.includes(String(EV.record.scored_setups)) && evOne.text.includes(String(EV.record.sessions)),
  `${EV.record.scored_setups} setups over ${EV.record.sessions} session`);

// --- score against outcome, before there is any outcome --------------------
const outcome = await page.evaluate(() => ({
  plot: !document.getElementById('outcome-plot').hidden,
  empty: !document.getElementById('outcome-empty').hidden,
  text: document.getElementById('outcome-empty').textContent.trim(),
  dots: document.querySelectorAll('#outcome-chart .sc-dot').length
}));
ok('with nothing measured yet the outcome view draws nothing and says why',
  !outcome.plot && outcome.empty && outcome.dots === 0 && /has not closed/.test(outcome.text),
  outcome.text.slice(0, 80));
ok('and does not pass a missing return off as a flat line at zero',
  /not the same as a flat line at zero/.test(outcome.text));

await shot('desktop-dark');

// --- light ------------------------------------------------------------------
await setTheme('light');
await page.waitForTimeout(250);
const light = await page.evaluate(() => {
  const lum = (c) => { const [r, g, b] = c.match(/[\d.]+/g).slice(0, 3).map(Number)
    .map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const cr = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
  const bg = getComputedStyle(document.body).backgroundColor;
  const chip = document.querySelector('#scores-table .sc-chip--warn');
  return {
    bg, dark: lum(bg) < 0.25,
    h1: cr(getComputedStyle(document.getElementById('h1')).color, bg),
    // null when there is no fallback chip to measure -- a run Claude scored
    // in full has none, and README used to list this as the other way the
    // script threw on real output.
    chip: chip ? cr(getComputedStyle(chip).color, getComputedStyle(chip).backgroundColor) : null,
    marks: [...document.querySelectorAll('#shortlist .sc-frame__mark')]
      .filter((m) => getComputedStyle(m).display !== 'none').length
  };
});
ok('light mode is actually light', !light.dark, light.bg);
ok('the headline is readable in light mode', light.h1 >= 4.5, light.h1.toFixed(2) + ':1');
ok('the fallback label is readable in light mode',
  light.chip === null ? fallbacks.length === 0 : light.chip >= 4.5,
  light.chip === null ? 'no fallback chip on this data' : light.chip.toFixed(2) + ':1');
await shot('desktop-light');
await setTheme('dark');
await page.waitForTimeout(200);
const dark = await page.evaluate(() => ({
  bg: getComputedStyle(document.body).backgroundColor,
  // one chick in an empty frame, not two and not none, whatever the theme
  marks: [...document.querySelectorAll('#shortlist .sc-frame__mark')]
    .filter((m) => getComputedStyle(m).display !== 'none').length
}));
ok('the toggle actually changes the page', dark.bg !== light.bg, `${light.bg} -> ${dark.bg}`);
ok('dark mode is actually dark', dark.bg !== light.bg && light.dark === false, dark.bg);
ok('exactly one chick shows in each theme',
  dark.marks === run.shortlist_size && light.marks === run.shortlist_size,
  `dark ${dark.marks}, light ${light.marks}, ${run.shortlist_size} frames`);

// --- the phone -------------------------------------------------------------
await page.setViewportSize({ width: 390, height: 844 });
await open();
await setTheme('dark');
await page.waitForTimeout(200);
const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
ok('the phone does not scroll sideways', overflow <= 1, `${overflow}px of overflow`);
const scrolls = await page.evaluate(() => {
  const s = document.getElementById('scores-scroll');
  return { inside: s.scrollWidth > s.clientWidth, clipped: s.classList.contains('is-clipped') };
});
ok('the wide table scrolls inside its own box and says it is clipped', scrolls.inside && scrolls.clipped, JSON.stringify(scrolls));
ok('the shortlist survives a phone', (await page.locator('#shortlist .pick').count()) === run.shortlist_size);
ok('so does the fallback label', (await page.locator('#shortlist .sc-chip--warn').count()) === inShort.length);
await shot('phone-dark');
await setTheme('light');
await page.waitForTimeout(250);
await shot('phone-light');
await page.setViewportSize({ width: 1280, height: 1000 });

// --- the states one day's data cannot hold ---------------------------------
await open('/v/forward/');
ok('forward returns, once they exist, read as percentages',
  /^[+-]\d+\.\d{2}%$/.test((await page.locator('#scores-table tbody tr:first-child td:nth-child(9)').textContent()).trim()),
  (await page.locator('#scores-table tbody tr:first-child td:nth-child(9)').textContent()).trim());
ok('and reach the shortlist card',
  (await page.locator('#shortlist .pick', { hasText: '+1d' }).count()) > 0);
ok('a run whose returns are in is no longer pending in the history',
  !(await page.locator('#runs-table tbody tr:first-child').textContent()).includes('pending'));

// --- score against outcome, once there IS an outcome -----------------------
// The most over-claimable view on the page. It has to plot only the candidates
// that really have a return, put them where their numbers say, keep the two
// kinds of score apart by shape rather than hue, and refuse to call one
// session's gap a result.
const FWD = VARIANTS.forward();
const fwdDone = FWD.candidates.filter((c) => (c.forward_returns || {}).d1 !== null && (c.forward_returns || {}).d1 !== undefined);
const fwdPending = FWD.candidates.length - fwdDone.length;
const plot = await page.evaluate(() => {
  const zero = document.querySelector('#outcome-chart .sc-chart__crosshair');
  return {
    dots: [...document.querySelectorAll('#outcome-chart .sc-dot')].map((d) => ({
      cx: +d.getAttribute('cx'), cy: +d.getAttribute('cy'), hollow: d.classList.contains('is-hollow')
    })),
    y0: zero ? +zero.getAttribute('y1') : null,
    rows: document.querySelectorAll('#outcome-table tbody tr').length,
    verdict: document.getElementById('outcome-verdict').textContent.trim()
  };
});
ok('a dot for every candidate that has a return, and none for the ones that do not',
  plot.dots.length === fwdDone.length && plot.rows === fwdDone.length && fwdPending > 0,
  `${plot.dots.length} dots, ${fwdDone.length} measured, ${fwdPending} still pending`);
ok('and the page says how many are still pending',
  plot.verdict.includes(`${fwdPending} are still pending`), plot.verdict.slice(0, 110));
// A dot above the zero line made money and a dot below it lost money. An
// inverted or unscaled y would still draw 22 dots.
ok('a dot sits on the side of zero its return says it does',
  plot.y0 !== null && plot.dots.every((d, i) => {
    // Guarded, not indexed blind: a page that plots MORE dots than there are
    // measured candidates must fail here rather than throw on the overrun.
    const c = fwdDone[i];
    return !!c && (c.forward_returns.d1 > 0 ? d.cy < plot.y0 : d.cy > plot.y0);
  }),
  `zero at y=${plot.y0}, ${plot.dots.length} dots for ${fwdDone.length} measured`);
ok('and further right means a higher score',
  plot.dots.every((d, i) => i === 0 || d.cx <= plot.dots[i - 1].cx + 0.001),
  plot.dots.slice(0, 4).map((d) => d.cx.toFixed(1)).join(' '));
// Found by looking at it: the legend drew two identical squares beside the
// words "filled" and "hollow", so the key contradicted the chart it explained.
const keys = await page.evaluate(() => [...document.querySelectorAll('#outcome-legend i')]
  .map((i) => getComputedStyle(i).backgroundColor + '|' + getComputedStyle(i).boxShadow));
ok('the legend keys are the two marks, not two identical squares',
  keys.length === 2 && keys[0] !== keys[1], keys.join('  vs  '));
ok('a fallback score is a hollow dot, so the split is not only a colour',
  plot.dots.filter((d) => d.hollow).length === fwdDone.filter((c) => c.provenance.source !== 'claude').length,
  `${plot.dots.filter((d) => d.hollow).length} hollow of ${plot.dots.length}`);
// THE ALTERNATIVE. The one-night fixture has no closed horizon, so the
// evidence body -- and the control ladder inside it -- must stay hidden
// together: a ladder of four "pending" rows under an empty-state note would
// be the page saying two things about one state. The ladder itself is
// checked on the history source and on two variants built from it below.
ok('and the control ladder is hidden with the body it belongs to, not rendered under the empty note',
  (await page.locator('#control-table tbody tr').count()) === 0
  && await page.locator('#evidence-body').isHidden());

ok('one session is not reported as evidence that the ranking works',
  /one session/.test(plot.verdict) && /not evidence/.test(plot.verdict), plot.verdict.slice(-120));
await shot('forward-returns');

// --- a file that recorded the checklist only for what it scored ------------
await open('/v/nodetail/');
const biased = await page.evaluate(() => ({
  shown: !document.getElementById('checks-bias').hidden,
  body: document.getElementById('checks-bias-body').textContent.trim(),
  hint: document.getElementById('checks-hint').textContent.trim(),
  rows: document.querySelectorAll('#checks-table tbody tr').length
}));
ok('per-check rates over the survivors alone are labelled as overstatements',
  biased.shown && /overstatement/.test(biased.body) && biased.body.includes(`${run.scored} bursts`),
  biased.body.slice(0, 120));
ok('and the view still draws, over the rows it does have',
  biased.rows === CHECKS.length && biased.hint.includes(`${run.scored} bursts`), biased.hint.slice(0, 90));

// --- the funnel when the last stage is a rounding error --------------------
await page.setViewportSize({ width: 390, height: 844 });
await open('/v/wide/');
const wide = await page.evaluate(() => ({
  kept: [...document.querySelectorAll('#funnel-chart .seg-kept')].map((r) => +r.getAttribute('width')),
  last: [...document.querySelectorAll('#funnel-table tbody tr')].pop().textContent.replace(/\s+/g, ' ').trim()
}));
ok('a stage worth a thousandth of the universe is still drawn, not rounded away',
  wide.kept.length === STAGES.length && wide.kept.every((w) => w >= 3),
  wide.kept.map((w) => w.toFixed(2)).join(' '));
ok('and it still says how many names it is',
  wide.last.includes(shown(run.shortlist_size)), wide.last.slice(0, 90));
// The check the `wide` variant existed for and never made: that a FOUR-DIGIT
// universe still reads back as the number the run holds. Comparing String(n)
// here is what broke at 1,000, and nothing noticed because this variant only
// ever measured bar widths.
const wideRows = await page.$$eval('#funnel-table tbody tr',
  (rows) => rows.map((r) => [...r.children].map((c) => c.textContent.trim())));
ok('and a four-digit universe reads back as the number the run holds',
  wideRows.length === STAGES.length && wideRows[0][1] === shown(5000)
  && wideRows[0][1] !== String(5000),
  `${wideRows.length ? wideRows[0][1] : 'no rows'} — and String(5000) is ${String(5000)}`);
await page.setViewportSize({ width: 1280, height: 1000 });

// --- enough sessions for the page to change its mind -----------------------
await open('/v/history/');
const grown = await page.evaluate(() => [...document.querySelectorAll('#returns-tiles .sc-tile')]
  .map((t) => t.querySelector('.sc-chip').textContent.trim()));
ok('a horizon with enough sessions stops saying there is not enough data',
  grown[0] === 'measured' && grown[1] === 'not enough data' && grown[2] === 'not enough data',
  grown.join(' | '));

await open('/v/norepeats/');
const flat = await page.evaluate(() => [...document.querySelectorAll('#returns-tiles .sc-tile')]
  .map((t) => t.querySelector('.sc-tile__sub').textContent.trim()));
ok('a 1:1 collapse still says what the setups were counted from',
  flat.every((t) => /(\d+) setups? from \1 rows?/.test(t)), flat.join(' | '));

await open('/v/degraded/');
ok('a run that lost something says so at the top', !(await page.locator('#notice').isHidden()));
ok('and names what it lost', (await page.textContent('#notice')).includes('214 symbols'), await page.textContent('#notice'));
ok('the rest of the run still renders', (await page.locator('#scores-table tbody tr').count()) === run.scored);

await open('/v/noevidence/');
const gone = await page.evaluate(() => ({
  hidden: document.getElementById('evidence-card').hidden,
  text: document.getElementById('evidence-empty').textContent.trim(),
  predict: document.getElementById('predict-card').hidden
}));
ok('a snapshot with no record in it says so rather than hiding the question',
  !gone.hidden && /written before the pipeline began publishing one/.test(gone.text)
  && /not that the answer is no/.test(gone.text), gone.text.slice(0, 90));
ok('and the views that need a record stay down rather than drawing an empty shell', gone.predict);

await page.goto(BASE + '/v/nodata/', { waitUntil: 'load' });
await page.waitForTimeout(600);
ok('a page with no data.json says so instead of showing an empty shell',
  (await page.textContent('#h1')) === 'Snapshot unavailable'
  && !(await page.locator('#notice').isHidden()), await page.textContent('#h1'));

// --- and the state after the pipeline starts publishing charts -------------
// Same page, same data; the only change is that the PNGs now resolve. The
// empty frames must give way to the images, or the reader never sees a chart.
await ctx.route(/\/charts\/[^/]+\.png$/, (r) => r.fulfill({ status: 200, contentType: 'image/png', body: PIXEL }));
await open();
ok('once the PNGs exist the picks show them instead of the empty frame',
  (await page.locator('#shortlist img.shot').count()) === shortWithPath
  && (await page.locator('#shortlist .sc-frame--empty').count()) === run.shortlist_size - shortWithPath,
  `${await page.locator('#shortlist img.shot').count()} images, ${await page.locator('#shortlist .sc-frame--empty').count()} empty`);
await shot('charts-present');

// --- thirty runs, written by the real pipeline ----------------------------
// tests/fixtures/history is what docs/ looks like after a month of
// commit-backs: forward returns filled in by later runs, a night the scorer
// was down, a chart that would not render, repeats on consecutive sessions,
// and the last week still pending. Nothing about its numbers is typed here;
// every expectation is computed from the file the page is reading.
await open('/f/history/');
await setTheme('dark');
await page.waitForTimeout(200);
const hrun = HIST.run;
ok('the history fixture opens and is disclosed as sample data',
  (await page.textContent('#h1')) === `${plural(hrun.bursts, 'burst')}, ${hrun.scored} scored, ${hrun.shortlist_size} on the shortlist`
  && !(await page.locator('#fixture-banner').isHidden()),
  await page.textContent('#h1'));
ok('its scored and gated rows account for every burst of the newest run',
  (await page.locator('#scores-table tbody tr').count()) === hrun.scored
  && (await page.locator('#scores-table tbody tr').count()) + (await page.locator('#gated-table tbody tr').count()) === hrun.bursts);
ok('every run in the file is in the history table',
  (await page.locator('#runs-table tbody tr').count()) === HIST.runs.length,
  `${HIST.runs.length} runs`);
const hist = HIST.runs;
const withD5 = hist.filter((r) => r.forward_returns && r.forward_returns.d5 !== null);
const pendingD1 = hist.filter((r) => !r.forward_returns || r.forward_returns.d1 === null);
const cells = await page.$$eval('#runs-table tbody tr', (trs) => trs.map((tr) => [...tr.children].map((td) => td.textContent.trim())));
ok('a run whose horizons have closed prints them as percentages, and a pending one says pending',
  withD5.length > 0 && pendingD1.length > 0
  && cells.filter((c) => /^[+-]\d+\.\d{2}%$/.test(c[8])).length === withD5.length
  && cells.filter((c) => c[6] === 'pending').length === pendingD1.length,
  `${withD5.length} runs with +5d, ${pendingD1.length} with +1d pending`);
const down = hist.filter((r) => r.fallbacks > 0);
ok('the night the scorer was down is in the table with its fallback count',
  down.length > 0 && cells.some((c) => c[0].startsWith(fmtDay(down[0].date)) && c[4] === String(down[0].fallbacks)),
  down.length ? `${down[0].date}: ${down[0].fallbacks} fallbacks` : 'no such night in the fixture');
const HH = [horizon('d1'), horizon('d3'), horizon('d5')];
const htiles = await page.evaluate(() => [...document.querySelectorAll('#returns-tiles .sc-tile')].map((t) => ({
  value: t.querySelector('.sc-tile__value').textContent.trim(), chip: t.querySelector('.sc-chip').textContent.trim() })));
// horizon() reads REAL; recompute over HIST for this pass.
const hhorizon = (k) => {
  const have = HIST.runs.filter((r) => (r.forward_returns || {})[k] !== null && (r.forward_returns || {})[k] !== undefined);
  const n = have.reduce((a, r) => a + (r.forward_returns.n || 0), 0);
  return { sessions: have.length, mean: n ? have.reduce((a, r) => a + r.forward_returns[k] * (r.forward_returns.n || 0), 0) / n : null };
};
const hh = [hhorizon('d1'), hhorizon('d3'), hhorizon('d5')];
ok('each horizon tile is the setup-weighted mean over the sessions that closed, and says whether that is enough',
  htiles.length === 3 && htiles.every((t, i) => t.value === money(hh[i].mean)
    && t.chip === (hh[i].sessions >= 20 ? 'measured' : (hh[i].sessions ? 'not enough data' : 'no session closed yet'))),
  htiles.map((t, i) => `${t.value} over ${hh[i].sessions} (${t.chip})`).join(' | '));
const hrepeats = HIST.candidates.filter((c) => (c.streak || {}).day > 1);
ok('a repeat the ledger really computed says which setup it is day N of',
  (await page.locator('#scores-table tbody tr', { hasText: 'of this setup, since' }).count()) === hrepeats.length,
  `${hrepeats.length} repeats in the newest run`);
const hblind = HIST.candidates.filter((c) => c.chart_error);
ok('a chart the pipeline could not render says so on the page',
  hblind.length > 0 && (await Promise.all(hblind.map((c) => page.locator('#scores-table tbody tr', { hasText: c.ticker }).count()))).every((n) => n > 0)
  && (await page.locator('#shortlist .pick', { hasText: 'scored without the chart' }).count())
     === hblind.filter((c) => c.rank <= hrun.shortlist_size && c.provenance.source === 'claude' && !c.provenance.chart_seen).length,
  hblind.map((c) => `${c.ticker}: ${c.chart_error}`).join('; ').slice(0, 90));
// The record's view, populated. Every expectation is computed from the file
// the page is reading, so a change to how the pipeline aggregates fails here
// rather than passing against a number typed into this script.
const HEV = HIST.evidence;
const hev = await page.evaluate(() => ({
  body: !document.getElementById('evidence-body').hidden,
  verdict: document.getElementById('evidence-verdict').textContent.trim(),
  bars: document.querySelectorAll('#evidence-chart .bar').length,
  rows: document.querySelectorAll('#evidence-table tbody tr').length,
  tones: [...new Set([...document.querySelectorAll('#evidence-chart .bar')].map((b) => getComputedStyle(b).fill))].length,
  chips: [...document.querySelectorAll('#evidence-table tbody .sc-chip--warn')].map((c) => c.textContent.trim()),
  legend: document.querySelectorAll('#evidence-legend span').length
}));
// The chart draws the horizons the strategy trades, not +1d — that one is in
// the tiles and the table, and putting the least meaningful number in the most
// prominent place is the opposite of the point.
const drawn = HEV.horizons.filter((h) => h > 1);
const drawable = HEV.by_score.reduce((total, b) =>
  total + drawn.filter((h) => at(b.outcomes, h).mean !== null).length, 0);
ok('a record with outcomes draws a bar per horizon per score band',
  hev.body && hev.bars === drawable && hev.rows === HEV.by_score.length,
  `${hev.bars} bars for ${drawable} measured horizons, ${hev.rows} rows for ${HEV.by_score.length} bands`);
// The legend names two horizons; if both series render in one colour the key
// contradicts its own chart. That shipped once here already, drawn with a
// class whose CSS hard-codes the fill and ignores the tone channel.
ok('and the two horizons are two colours, as the legend says they are',
  hev.tones === 2 && hev.legend >= 2, `${hev.tones} distinct fills across ${hev.bars} bars`);
const short = HEV.by_score.filter((b) => !b.enough).length;
ok('a band with too few setups is refused as a rate rather than printed as one',
  short > 0 && hev.chips.filter((c) => c === 'not enough data').length === short,
  `${short} bands under ${HEV.min_setups} setups, ${hev.chips.length} marked`);
// The verdict is the sentence a reader takes away. It must lean only on bands
// that cleared the floor, and must be able to say there is no answer yet.
const readable = HEV.by_score.filter((b) => b.enough);
ok('the verdict names only what the record can support',
  readable.length
    ? hev.verdict.includes(readable[readable.length - 1].verdict) && /not as a result|cannot show a ranking/.test(hev.verdict)
    : /no answer here yet/.test(hev.verdict),
  hev.verdict.slice(0, 120));

const pred = await page.evaluate(() => ({
  rows: document.querySelectorAll('#predict-table tbody tr').length,
  hint: document.getElementById('predict-hint').textContent.trim()
}));
ok('every 2LYNCH check is measured against what happened next, not just against the gate',
  pred.rows === HEV.by_check.length && /survivors/.test(pred.hint),
  `${pred.rows} checks`);
const streak = await page.evaluate(() => ({
  rows: document.querySelectorAll('#streak-table tbody tr').length,
  hint: document.getElementById('streak-hint').textContent.trim()
}));
// The one block counted per appearance rather than per setup. If the page
// stops saying so, it is quietly reporting overlapping windows as independent.
ok('the streak view says it counts appearances, and why it must',
  streak.rows === HEV.by_day.length && /APPEARANCE/.test(streak.hint) && /overlap/.test(streak.hint),
  streak.hint.slice(0, 100));
// On the history source both sides of the control have closed outcomes, so
// this is where the direction sentence is checked -- against the ledger's own
// numbers, not against a rendered label. Whether it says better or worse is
// the record's business; that it says one of them, with both n's, is this
// check's.
const hv = await page.textContent('#control-verdict');
const hEv = HIST.evidence, hH = hEv.horizons[hEv.horizons.length - 1];
const hPicks = hEv.overall.outcomes.find((o) => o.horizon === hH), hRef = hEv.refused.outcomes.find((o) => o.horizon === hH);
const hLadder = await page.$$eval('#control-table tbody tr', (rows) => rows.map((r) => r.textContent.replace(/\s+/g, ' ')));
// A missing row must FAIL these, not crash the runner: an earlier version
// indexed hLadder[3] unguarded, so a ladder short by one row threw before any
// FAIL line printed and read, to a count of failures, as a pass.
const rowFor = (label) => hLadder.find((l) => l.startsWith(label)) || '';
const countIn = (label) => Number((rowFor(label).match(new RegExp(label + '.*?(\\d+)')) || [])[1]);
ok('the alternative is on the page as five disjoint populations and a benchmark rung, and says which is which',
  hLadder.length === 6 && rowFor('the shortlist') && rowFor('what it refused')
  && /call cap/.test(rowFor('the crowded-out')) && /liquidity floor/.test(rowFor('the illiquid'))
  && /survivorship/.test(rowFor('the universe')),
  hLadder.map((l) => l.slice(0, 36)).join(' | ') || 'no ladder rendered');
// The rung is over the names at or above each night's floor, and the real
// pipeline wrote this record with the floor on every measured pairing: the
// row says the rule and the verdict says it was applied, both read off the
// ledger's own counts rather than assumed.
// And the verdict reads the picks against the universe even while the
// refused side is thin -- which this record's is -- because the benchmark
// is paired with the picks alone.
ok('the universe rung names the floor it is over, and the verdict says the record applied it',
  HIST.evidence.universe.floored > 0 && HIST.evidence.universe.unfloored === 0
  && /at or above that night\u2019s liquidity floor/.test(rowFor('the universe'))
  && /Against buying anything in the universe on the same days/.test(hv)
  && /Names under each night\u2019s liquidity floor are left out of it/.test(hv)
  && /the names under that night\u2019s floor left out for the same reason — paired/.test(await page.textContent('#control-hint'))
  // and the picks' own figure stands before the benchmark, so the paragraph
  // that says a control comparison needs both sides is not followed by a
  // comparison with no first term.
  && hv.includes('Names this screener scored returned ' + (hPicks.mean > 0 ? '+' : '') + hPicks.mean.toFixed(2) + '% at +' + hH + 'd'),
  `floored ${HIST.evidence.universe.floored}, unfloored ${HIST.evidence.universe.unfloored}: ${rowFor('the universe').slice(0, 90)}`);
// The benchmark pairs every scored setup with its session's universe move,
// so its n is bounded by the scored setups and, over thirty runs where every
// session but the last week has a benchmark, is most of them. Read off the
// ledger's own block, and the rung's number must be that block's.
// One formatter for every rendered percentage this file compares against
// the ledger's own numbers; declared before its first use.
const pctOf = (v) => (v === null || v === undefined ? null : (v > 0 ? '+' : '') + v.toFixed(2) + '%');
const hBench = HIST.evidence.universe;
const hBench5 = hBench.outcomes.find((o) => o.horizon === hH);
ok('the universe rung holds a benchmark for most scored setups and prints the ledger\'s own mean',
  hBench.setups > 0 && hBench.setups <= HIST.evidence.overall.setups && hBench5.n > 0
  && countIn('the universe') === hBench.setups && rowFor('the universe').includes(pctOf(hBench5.mean)),
  `${hBench.setups} of ${HIST.evidence.overall.setups} setups paired; +5d ${hBench5.mean} over ${hBench5.n}`);
ok('and the run entries carry the benchmark the rung was built from, pending only for the last week',
  HIST.runs.filter((r) => r.benchmark && r.benchmark.d5 !== null).length >= HIST.runs.length - 6
  && HIST.runs.every((r) => r.benchmark && typeof r.benchmark.n5 === 'number')
  && HIST.runs.filter((r) => r.benchmark && r.benchmark.d5 !== null).every((r) => r.benchmark.n5 > 1),
  `${HIST.runs.filter((r) => r.benchmark && r.benchmark.d5 !== null).length} of ${HIST.runs.length} runs benchmarked`);
ok('and each row prints the setup count the ledger computed for that population',
  countIn('what it refused') === HIST.evidence.refused.setups
  && countIn('the crowded-out') === HIST.evidence.crowded_out.setups
  && countIn('the shortlist') === HIST.evidence.shortlist.setups
  && countIn('the illiquid') === HIST.evidence.illiquid.setups,
  `refused ${HIST.evidence.refused.setups}, crowded ${HIST.evidence.crowded_out.setups}, shortlist ${HIST.evidence.shortlist.setups}, illiquid ${HIST.evidence.illiquid.setups}`);
// Rule 6's refusals are a population of their own and NOT part of the
// control: a thirty-run record with liquidity rows in it must show them on
// the ladder row that names the floor, and the verdict sentence must still
// compare picks against what the STRATEGY refused, whose n is unchanged by
// however many thin names the floor cut.
ok('and the illiquid row holds setups the refused row does not count',
  HIST.evidence.illiquid.setups > 0
  && HIST.evidence.illiquid.setups + HIST.evidence.refused.setups + HIST.evidence.crowded_out.setups
     + HIST.evidence.shortlist.setups + HIST.evidence.rest.setups === HIST.evidence.record.setups,
  `illiquid ${HIST.evidence.illiquid.setups} of ${HIST.evidence.record.setups} setups`);
ok('over thirty runs the control sentence carries both sides\' n and says which did better',
  (hPicks.n >= hEv.min_setups && hEv.refused.enough)
    ? (/did (better|WORSE|no differently)/.test(hv) && hv.includes(`over ${hPicks.n} setup`) && hv.includes(`over ${hRef.n} setup`))
    : (/(No comparison yet|Only one side can be read yet)/.test(hv) && hv.includes(`${hPicks.n} scored setup`) && hv.includes(`${hRef.n} refused one`)),
  hv.slice(0, 120));
await open('/v/thincontrol/');
const thin = await page.textContent('#control-verdict');
ok('with neither side at the floor the control refuses a direction and prints both n\'s',
  /^No comparison yet: 5 scored setups and 5 refused ones have closed/.test(thin)
  && !/did (better|WORSE|no differently)/.test(thin),
  thin.slice(0, 90));
await open('/v/fullcontrol/');
const full = await page.textContent('#control-verdict');
ok('with both sides at the floor it states the direction, by how much, over which n\'s',
  /the picks did better, by 3\.00%/.test(full) && full.includes('+6.00% at +5d from the burst-day close over 40 setups')
  && full.includes('refused returned +3.00% over 45 setups'),
  full.slice(0, 160));
// --- the return basis: one switch, every number, every heading --------------
// Round 6. The record carries two measurements of every return -- from the
// burst-day close (what the setup did) and from the next session's open (what
// a reader of the 18:16 email could have paid) -- and the page shows ONE at a
// time. The checks below read the same block off the ledger's own file for
// each basis and compare, so a cell that showed a close-basis number under the
// open-basis label would fail here.
await open('/f/history/');
const tabs = await page.$$eval('#basis-tabs .sc-tab', (b) => b.map((t) => [t.dataset.basis, t.getAttribute('aria-pressed'), t.textContent.trim()]));
ok('the return basis is one control with two named choices, the burst close pressed by default',
  tabs.length === 2 && tabs[0][0] === 'close' && tabs[0][1] === 'true' && tabs[1][0] === 'open' && tabs[1][1] === 'false'
  && /burst-day close/.test(tabs[0][2]) && /next session/.test(tabs[1][2]),
  JSON.stringify(tabs));
const hRef5 = HEV.refused.outcomes.find((o) => o.horizon === hH);
const ladderCloseRefused = countIn('what it refused');
const cellText = async (sel) => (await page.locator(sel).textContent()).replace(/\s+/g, ' ').trim();
const refusedRowCells = async () => page.$$eval('#control-table tbody tr', (rows) => {
  const r = rows.find((x) => x.textContent.startsWith('what it refused'));
  return r ? [...r.querySelectorAll('td')].map((td) => td.textContent.replace(/\s+/g, ' ').trim()) : [];
});
const closeCells = await refusedRowCells();
await page.click('#basis-tabs .sc-tab[data-basis="open"]');
const openCells = await refusedRowCells();
ok('switching to the open basis changes the ladder to the ledger\'s own from_open means',
  closeCells.length === openCells.length && openCells.length > 0
  && closeCells[4].startsWith(pctOf(hRef5.mean)) && openCells[4].startsWith(pctOf(hRef5.from_open.mean))
  && hRef5.mean !== hRef5.from_open.mean,
  `close ${closeCells[4]} vs open ${openCells[4]}; ledger ${hRef5.mean} / ${hRef5.from_open.mean}`);
// Nine surfaces, not five: the per-check, streak-pay, by-month and per-name
// cards showed returns under no basis at all until round 9.
const openHints = await page.$$eval('#evidence-hint, #control-hint, #runs-hint, #control-verdict, #evidence-verdict, #predict-hint, #streak-hint, #trend-hint, #ticker-hint', (ps) => ps.map((p) => p.textContent));
ok('and every heading that carries a return names the basis it is on',
  openHints.length === 9 &&
  openHints.every((t) => /next session.s open/.test(t)) && !openHints.some((t) => /burst-day close/.test(t)),
  openHints.map((t) => t.slice(0, 60)).join(' | '));
const openRunIndex = HIST.runs.findIndex((r) => r.forward_returns && r.forward_returns.from_open && r.forward_returns.from_open.d5 !== null);
const openRun = HIST.runs[openRunIndex];
// The table lists runs in the file's order, so the row is found by position:
// the session cell prints a formatted day, not the ISO date.
const openRunRow = await page.$$eval('#runs-table tbody tr', (rows, i) => {
  const r = rows[i];
  return r ? [...r.querySelectorAll('td')].map((td) => td.textContent.replace(/\s+/g, ' ').trim()) : [];
}, openRunIndex);
ok('the runs table follows the switch too, reading each run\'s own from_open mean',
  openRunRow.length > 0 && openRunRow[8] === pctOf(openRun.forward_returns.from_open.d5)
  && openRunRow[8] !== pctOf(openRun.forward_returns.d5),
  `row ${openRunRow[8]}; ledger open ${openRun.forward_returns.from_open.d5}, close ${openRun.forward_returns.d5}`);
await page.click('#basis-tabs .sc-tab[data-basis="close"]');
ok('and switching back restores every close-basis number',
  JSON.stringify(await refusedRowCells()) === JSON.stringify(closeCells) && countIn('what it refused') === ladderCloseRefused);
// Round 9. The per-check view's separation column is what its "separates
// most" sentence sorts on, and it read the close basis whichever tab was
// pressed; so did the streak-pay table's in-band count. Both are read off
// the ledger's own per-basis numbers here, on a row where the bases differ.
const sepCheck = HEV.by_check.find((c) => c.separation !== null && c.separation_from_open !== null && c.separation !== c.separation_from_open);
const sepCell = async (code) => page.$$eval('#predict-table tbody tr', (rows, code) => {
  const r = rows.find((x) => x.querySelector('td') && x.querySelector('td').textContent.trim() === code);
  return r ? r.querySelectorAll('td')[5].textContent.trim() : '';
}, code);
const bestOn = (key, licence) => HEV.by_check.filter((c) => c[licence]).slice().sort((a, b) => (b[key] || 0) - (a[key] || 0))[0];
const sepClose = sepCheck ? await sepCell(sepCheck.code) : '';
const hintClose = await page.textContent('#predict-hint');
await page.click('#basis-tabs .sc-tab[data-basis="open"]');
const sepOpen = sepCheck ? await sepCell(sepCheck.code) : '';
const hintOpen = await page.textContent('#predict-hint');
ok('the per-check separation column follows the basis switch, reading the ledger\'s own separation_from_open',
  !!sepCheck && sepClose === pctOf(sepCheck.separation) && sepOpen === pctOf(sepCheck.separation_from_open),
  `${sepCheck ? sepCheck.code : 'no check differs'}: close ${sepClose}, open ${sepOpen}`);
const bestClose = bestOn('separation', 'enough'), bestOpen = bestOn('separation_from_open', 'enough_from_open');
const names = (hint, best, key) => !!best && hint.includes('so far ' + best.code + ' separates most, by ' + pctOf(best[key]).replace('+', ''));
ok('and the "separates most" sentence names the check and the number on the basis being read',
  names(hintClose, bestClose, 'separation') && names(hintOpen, bestOpen, 'separation_from_open')
  && pctOf(bestClose.separation) !== pctOf(bestOpen.separation_from_open),
  `close: ${hintClose.slice(hintClose.indexOf('so far'), hintClose.indexOf('so far') + 40)} | open: ${hintOpen.slice(hintOpen.indexOf('so far'), hintOpen.indexOf('so far') + 40)}`);
const dayRow = HEV.by_day.find((r) => { const o = r.outcomes.find((x) => x.horizon === hH); return o && o.from_open && o.in_band !== o.from_open.in_band; });
const dayLabel = dayRow ? (dayRow.day === null ? 'not known' : 'day ' + dayRow.day) : '';
const inBandCell = async () => page.$$eval('#streak-table tbody tr', (rows, label) => {
  const r = rows.find((x) => x.querySelector('td') && x.querySelector('td').textContent.trim().startsWith(label));
  return r ? r.querySelectorAll('td')[5].textContent.trim() : '';
}, dayLabel);
const inBandOpen = await inBandCell();
await page.click('#basis-tabs .sc-tab[data-basis="close"]');
const inBandClose = await inBandCell();
const dayOut = dayRow ? dayRow.outcomes.find((x) => x.horizon === hH) : null;
ok('the streak-pay table\'s in-band count follows the basis switch too',
  !!dayRow && inBandClose === String(dayOut.in_band) && inBandOpen === String(dayOut.from_open.in_band),
  `${dayLabel || 'no day differs'}: close ${inBandClose}, open ${inBandOpen}; ledger ${dayOut && dayOut.in_band} / ${dayOut && dayOut.from_open.in_band}`);
await open('/v/forward/');
await page.click('#basis-tabs .sc-tab[data-basis="open"]');
const fwdOpenCell = (await page.locator('#scores-table tbody tr:first-child td:nth-child(9)').textContent()).trim();
const FWD0 = VARIANTS.forward().candidates[0].forward_returns;
ok('a candidate row shows its own open-basis return under the open label, not the close one',
  fwdOpenCell === pctOf(FWD0.from_open.d1) && fwdOpenCell !== pctOf(FWD0.d1), `cell ${fwdOpenCell}; open ${FWD0.from_open.d1}, close ${FWD0.d1}`);
// A row from before the basis, beside one measured on it. "Pending" was the
// word for both on the open basis, and it is false of the first: its
// sessions closed long ago and were never measured this way.
await open('/v/prebasisrows/');
await page.click('#basis-tabs .sc-tab[data-basis="open"]');
const preRow = (await page.locator('#scores-table tbody tr:nth-child(2) td:nth-child(9)').textContent()).trim();
const preTitle = await page.locator('#scores-table tbody tr:nth-child(2) td:nth-child(9)').getAttribute('title');
const measuredRow = (await page.locator('#scores-table tbody tr:first-child td:nth-child(9)').textContent()).trim();
const preCard = await page.locator('#shortlist .pick').nth(1).textContent();
const preRun = (await page.locator('#runs-table tbody tr:nth-child(2) td:nth-child(9)').textContent()).trim();
ok('a row from before the open basis reads "not measured" on that basis, beside a measured one, and never "pending"',
  preRow === 'not measured' && /predates the open basis/.test(preTitle || '') && /^[+-]\d+\.\d{2}%$/.test(measuredRow)
  && /not measured — this row predates the open basis/.test(preCard) && !/pending — the sessions/.test(preCard)
  && preRun === 'not measured',
  `table ${preRow} (${preTitle}) beside ${measuredRow}; run row ${preRun}`);
await page.click('#basis-tabs .sc-tab[data-basis="close"]');
ok('and the same row is a number on the close basis, which it does carry',
  /^[+-]\d+\.\d{2}%$/.test((await page.locator('#scores-table tbody tr:nth-child(2) td:nth-child(9)').textContent()).trim())
  && /^[+-]\d+\.\d{2}%$/.test((await page.locator('#runs-table tbody tr:nth-child(2) td:nth-child(9)').textContent()).trim()));
// The fourth state: refused an entry. Its close basis is measured, its
// sessions happened, and on the open basis it is not "pending".
await open('/v/noentry/');
await page.click('#basis-tabs .sc-tab[data-basis="open"]');
const noEntryCell = await page.locator('#scores-table tbody tr:nth-child(3) td:nth-child(9)');
const noEntryCard = await page.locator('#shortlist .pick').nth(2).textContent();
const noEntryRun = await page.locator('#runs-table tbody tr:nth-child(2) td:nth-child(9)');
const unrecordedCell = (await page.locator('#scores-table tbody tr:nth-child(4) td:nth-child(9)').textContent()).trim();
const unrecordedCard = await page.locator('#shortlist .pick').nth(3).textContent();
ok('a row refused an entry reads "not measured" with the reason on the open basis, on the card, the table and the run row',
  (await noEntryCell.textContent()).trim() === 'not measured' && /no usable open/.test(await noEntryCell.getAttribute('title') || '')
  && /not measured — no usable open on the next session/.test(noEntryCard) && !/pending — the sessions/.test(noEntryCard)
  && (await noEntryRun.textContent()).trim() === 'not measured' && /no usable open/.test(await noEntryRun.getAttribute('title') || ''),
  `table ${(await noEntryCell.textContent()).trim()}; run ${(await noEntryRun.textContent()).trim()}`);
ok('and a row with no forward_returns at all is "not recorded" on the card and in the table alike, never "pending"',
  unrecordedCell === 'not recorded' && /not recorded/.test(unrecordedCard) && !/pending/.test(unrecordedCard),
  `table ${unrecordedCell}`);
await page.click('#basis-tabs .sc-tab[data-basis="close"]');
ok('and on the close basis the refused row is a number and the unrecorded one is still "not recorded"',
  /^[+-]\d+\.\d{2}%$/.test((await page.locator('#scores-table tbody tr:nth-child(3) td:nth-child(9)').textContent()).trim())
  && (await page.locator('#scores-table tbody tr:nth-child(4) td:nth-child(9)').textContent()).trim() === 'not recorded');
// Round 6 said one basis at a time, named in every heading. The score-band
// CHART is the most prominent number on the page and read the close basis
// whatever the switch said, so it printed one figure over a table row
// printing another.
await open('/f/history/');
const chartLabels = async () => page.$$eval('#evidence-chart text.s-drop', (t) => t.map((x) => x.textContent.trim()));
// The BARS as well as the labels: reverting only the x-scale read leaves the
// labels right and draws them against a scale built from the other basis,
// which a label-only check cannot see.
const chartBars = async () => page.$$eval('#evidence-chart .sc-bar, #evidence-chart rect', (r) => r.map((x) => x.getAttribute('width')).filter(Boolean));
const chartClose = await chartLabels();
const barsClose = await chartBars();
await page.click('#basis-tabs .sc-tab[data-basis="open"]');
const chartOpen = await chartLabels();
const barsOpen = await chartBars();
// The chart labels one decimal, so the comparison does too.
const one = (v) => (v > 0 ? '+' : '') + v.toFixed(1) + '%';
const chartHz = HIST.evidence.horizons[HIST.evidence.horizons.length - 1];
const bandWithBoth = HIST.evidence.by_score.find((b) => {
  const o = b.outcomes.find((x) => x.horizon === chartHz);
  return o && o.mean !== null && o.from_open && o.from_open.mean !== null && o.mean !== o.from_open.mean;
});
const bandClose = bandWithBoth.outcomes.find((x) => x.horizon === chartHz);
ok('the score-band chart follows the basis switch, like the table under it',
  chartClose.length > 0 && chartOpen.length === chartClose.length
  && JSON.stringify(chartOpen) !== JSON.stringify(chartClose)
  && chartOpen.includes('+' + chartHz + 'd ' + one(bandClose.from_open.mean) + ' (n=' + bandClose.from_open.n + ')')
  && chartClose.includes('+' + chartHz + 'd ' + one(bandClose.mean) + ' (n=' + bandClose.n + ')')
  && barsClose.length > 0 && JSON.stringify(barsOpen) !== JSON.stringify(barsClose),
  `close ${chartClose.slice(0, 2).join(' | ')} :: open ${chartOpen.slice(0, 2).join(' | ')}`);
await page.click('#basis-tabs .sc-tab[data-basis="close"]');
// And three cards read `enough` where the ledger publishes a licence per
// basis, so an open-basis mean was chipped "measured" on the close basis's n.
await open('/v/halfmeasured/');
await page.click('#basis-tabs .sc-tab[data-basis="open"]');
const basisChips = await page.$$eval('#predict-table tbody tr td:last-child, #streak-table tbody tr td:last-child, #trend-table tbody tr td:last-child',
  (tds) => tds.map((t) => t.textContent.trim()));
const rateNotes = await page.$$eval('#predict-table tbody tr, #streak-table tbody tr, #trend-table tbody tr',
  (rows) => rows.map((r) => r.textContent).join(' '));
ok('a card whose open basis is under the floor is not chipped measured on the close basis\'s licence',
  basisChips.length > 0 && basisChips.every((c) => /not enough data/.test(c))
  && /too few to read as a rate/.test(rateNotes),
  `${basisChips.length} chips, first: ${basisChips[0]}`);
await page.click('#basis-tabs .sc-tab[data-basis="close"]');
// The x-scale, not just the labels. On any record whose means all sit inside
// the claimed band the scale is pinned by 0 and band.high and a chart reading
// the wrong basis for it draws identically; this source has one band past the
// band's top on the close basis alone, so the two scales must differ.
await open('/v/widemean/');
const wideClose = await page.$$eval('#evidence-chart text', (t) => t.map((x) => x.textContent.trim()).filter((x) => /^[+-]\d+%$/.test(x)));
await page.click('#basis-tabs .sc-tab[data-basis="open"]');
const wideOpen = await page.$$eval('#evidence-chart text', (t) => t.map((x) => x.textContent.trim()).filter((x) => /^[+-]\d+%$/.test(x)));
ok('and its x-axis is built from the basis being shown, not the other one',
  wideClose.length > 0 && wideOpen.length > 0
  && JSON.stringify(wideOpen) !== JSON.stringify(wideClose)
  && Math.max(...wideClose.map((t) => parseInt(t, 10))) > Math.max(...wideOpen.map((t) => parseInt(t, 10))),
  `close axis ${wideClose.join(' ')} :: open axis ${wideOpen.join(' ')}`);
await page.click('#basis-tabs .sc-tab[data-basis="close"]');
await open('/v/noopen/');
const noOpenTab = await page.$eval('#basis-tabs .sc-tab[data-basis="open"]', (b) => ({ disabled: b.disabled, pressed: b.getAttribute('aria-pressed') }));
const noOpenNote = await page.textContent('#basis-note');
ok('a record from before the open basis greys that choice and says why, rather than showing close numbers under it',
  noOpenTab.disabled && noOpenTab.pressed === 'false' && /predates the open basis/.test(noOpenNote)
  && /burst-day close/.test(await page.textContent('#runs-hint')),
  `disabled ${noOpenTab.disabled}, pressed ${noOpenTab.pressed}; ${noOpenNote.slice(0, 90)}`);
await open('/f/history/');
ok('a burst the record cannot place is a row of its own, never a day 1',
  (await page.locator('#streak-table tbody tr', { hasText: 'not known' }).count())
    === HEV.by_day.filter((d) => d.day === null).length);
// FOUR reasons put a burst in that bucket -- no_history, history_undated,
// history_unreadable and window_not_covered -- and the note under it named
// one: the only one any available source carries. A run whose history could
// not be READ lands every burst here and was told the record did not reach
// back far enough, which is a different fault with a different fix. The row
// notes carry the specific reason; the bucket may only say what is true of
// all four, so the check is that it does NOT pick one.
const bucketNote = await page.locator('#streak-table tbody tr', { hasText: 'not known' })
  .locator('.sc-note').first().textContent();
ok('and the bucket does not blame one of the four reasons it cannot tell apart',
  !/reach back|no history|could not read|undated/i.test(bucketNote)
  && /rows in the ledger carry the specific reason/.test(bucketNote),
  bucketNote);
ok('the record is broken down by month so a change over time is visible',
  (await page.locator('#trend-table tbody tr').count()) === HEV.by_month.length,
  `${HEV.by_month.length} months`);
// The per-name view, and the page's one lazy fetch.
const tick = await page.evaluate(() => ({
  rows: document.querySelectorAll('#ticker-table tbody tr').length,
  more: document.getElementById('ticker-more').textContent.trim(),
  btn: !!document.querySelector('#ticker-more button')
}));
ok('the per-name view starts as a summary and offers the record rather than fetching it',
  tick.rows === Math.min(15, HEV.by_ticker.length) && tick.btn && /fetched only if you ask/.test(tick.more),
  `${tick.rows} of ${HEV.by_ticker.length} names shown`);
await page.click('#ticker-more button');
await page.waitForTimeout(400);
const loaded = await page.evaluate(() => ({
  rows: document.querySelectorAll('#ticker-table tbody tr').length,
  // Scoped to the name cell: every rate cell carries its own .sc-note with
  // the setup count, so a table-wide count is three times the rows and would
  // have passed on any number at all.
  notes: document.querySelectorAll('#ticker-table tbody td:first-child .sc-note').length
}));
ok('and asking for it loads every name, each with the sessions it burst on',
  loaded.rows === HEV.by_ticker.length && loaded.notes === HEV.by_ticker.length,
  `${loaded.rows} names, ${loaded.notes} with per-burst detail`);
// OUTCOME_SHORT's words, asserted HERE and not against the fixture, because
// this is the only source whose ledger holds vetoed appearances -- the same
// check written on the fixture page passed while rendering nothing at all,
// which is the vacuous shape this project keeps producing. The count comes
// out of the ledger, so the assertion is that every refusal in the record
// reaches the reader as a refusal.
const LEDGER = JSON.parse(await readFile(join(SOURCES.history, 'ledger.json'), 'utf8'));
// The page shows a name's six most recent appearances, so the expected count
// is over that slice and not over the whole record -- 52 refusals are stored
// and 51 are reachable, and asserting the stored number failed on a view that
// was rendering correctly. Arithmetic over the same data, not a second copy of
// the wording, which is the thing under test.
const byTicker = new Map();
for (const run of LEDGER.runs) {
  for (const row of [...(run.candidates || []), ...(run.gated || [])]) {
    if (!byTicker.has(row.ticker)) byTicker.set(row.ticker, []);
    byTicker.get(row.ticker).push(row);
  }
}
let refusedOnScreen = 0, gatedOnScreen = 0, illiquidOnScreen = 0;
for (const rows of byTicker.values()) {
  rows.sort((a, b) => String(b.date).localeCompare(String(a.date)));
  for (const r of rows.slice(0, 6)) {
    if (r.score !== null && r.score !== undefined) continue;
    if (String(r.reason || '').startsWith('veto_')) refusedOnScreen++;
    else if (r.reason === 'lynch_gate') gatedOnScreen++;
    else if (r.reason === 'liquidity_floor') illiquidOnScreen++;
  }
}
const perName = await page.textContent('#ticker-table');
const saidRefused = (perName.match(/refused by an absolute rule/g) || []).length;
const saidGated = (perName.match(/rejected at the gate/g) || []).length;
const saidIlliquid = (perName.match(/below the liquidity floor/g) || []).length;
ok('a burst an absolute rule refused says so in the per-name record too',
  refusedOnScreen > 0 && saidRefused === refusedOnScreen && saidGated === gatedOnScreen,
  `${refusedOnScreen} refusals and ${gatedOnScreen} gate rejections reachable; ` +
  `page said ${saidRefused} and ${saidGated}`);
// The fourth word, on the same surface and by the same arithmetic: a burst
// rule 6 refused is neither a veto nor a gate rejection, and the history is
// the one source whose ledger holds them.
ok('and a burst the liquidity floor refused says that, not that the gate rejected it',
  illiquidOnScreen > 0 && saidIlliquid === illiquidOnScreen,
  `${illiquidOnScreen} liquidity refusals reachable; page said ${saidIlliquid}`);
await shot('history-desktop-dark');

// --- the checks that must hold for ANY run ---------------------------------
// docs/data.json is the fixture today and last night's real run once
// evening.yml commits one back, so everything here has to be true of both.
// Written once and run TWICE: against docs/ itself, and against a deliberately
// awkward real run. Two of these were written against the fixture's shape and
// were reproduced failing on a one-burst night before this was fixed -- the
// same class of defect the three-source split exists to close, reintroduced by
// the commit that introduced the split.
//
// Rows the page put DATA in: table() renders a "Nothing to show." placeholder
// row when there are none, and counting that as a candidate is what turned a
// quiet night into a red build.
const dataRows = (sel) => page.locator(`${sel} tbody tr:not(.sc-empty)`).count();

async function checksForAnyRun(data, where) {
  const run = data.run || {};
  const cands = data.candidates || [];
  const gated = data.gated_out || [];
  ok(`${where}: the page opens and its headline describes the run`,
    (await page.textContent('#h1')) ===
      `${plural(run.bursts || 0, 'burst')}, ${run.scored || 0} scored, ${run.shortlist_size || 0} on the shortlist`,
    await page.textContent('#h1'));
  ok(`${where}: it says whether it is sample data`,
    (await page.locator('#fixture-banner').isHidden()) === !run.fixture,
    run.fixture ? 'fixture: banner shown' : 'real run: no banner');
  ok(`${where}: its rows add up to its own funnel`,
    (await dataRows('#scores-table')) === cands.length
    && cands.length + gated.length === (run.bursts || 0)
    && cands.length === (run.scored || 0),
    `${cands.length} scored + ${gated.length} gated = ${plural(run.bursts || 0, 'burst')}`);
  ok(`${where}: a table with no rows says so instead of rendering an empty shell`,
    cands.length > 0 || (await page.locator('#scores-table tbody tr.sc-empty').count()) === 1,
    cands.length ? `${cands.length} scored, nothing to place` : 'nothing scored: placeholder shown');
  ok(`${where}: every fallback in it is labelled`,
    (await page.locator('#scores-table tbody .sc-chip--warn').count())
      === cands.filter((c) => !c.provenance || c.provenance.source !== 'claude').length);
}

await open('/');
await setTheme('dark');
await page.waitForTimeout(200);
// --- the reader lens's smaller findings, each on the state it named --------
await open('/v/undated/');
const runsCol = await page.$$eval('#runs-table tbody tr td:first-child', (tds) => tds.map((t) => t.textContent.trim()));
ok('a run whose date will not parse is shown as it is, never as NaN or undefined',
  runsCol.length > 0 && !runsCol.some((t) => /NaN|undefined/.test(t)) && runsCol.some((t) => t.includes('not-a-date')),
  runsCol.slice(0, 2).join(' | '));
await open('/v/oldsnap/');
const oldFunnel = (await page.textContent('#funnel-hint')) + ' '
  + (await page.$$eval('#funnel-table tbody tr', (rows) => rows.map((r) => r.textContent).join(' ')))
  + ' ' + (await page.textContent('#gated-hint'));
ok('a snapshot with no gate block and no cap prints neither undefined nor a number it does not have',
  !/undefined|NaN|null/.test(oldFunnel) && /the gate/.test(oldFunnel) && /the call cap/.test(oldFunnel),
  oldFunnel.replace(/\s+/g, ' ').slice(0, 120));
await open('/v/nosince/');
const firstStreak = await page.locator('#scores-table tbody tr').first().locator('.sc-note').first().textContent();
ok('a day number with no first_seen beside it drops the "since" clause rather than printing a dash',
  /day 2 of this setup/.test(firstStreak) && !/since/.test(firstStreak),
  firstStreak.slice(0, 80));
await open('/f/fixture/');
ok('the weakest-check sentence names the denominator its number was taken over',
  /of the bursts that failed the checklist/.test(await page.textContent('#checks-hint'))
  && !/of the ones that failed it/.test(await page.textContent('#checks-hint')),
  (await page.textContent('#checks-hint')).slice(0, 100));
await open('/v/quietmarket/');
ok('the empty evidence note states the horizons as they are, not five sessions for all of them',
  /at least one more session to close for \+1d and five for \+5d/.test(await page.textContent('#evidence-empty')),
  (await page.textContent('#evidence-empty')).slice(0, 120));
// Back to the source the any-run checks below were opened on.
await open('/');
await page.waitForTimeout(200);

await checksForAnyRun(LIVE, 'docs/');
await shot('live-desktop-dark');

// The same checks over a run that is NOT the fixture, so "holds for any run"
// is exercised rather than asserted.
await open('/v/quietnight/');
await setTheme('dark');
await page.waitForTimeout(200);
await checksForAnyRun(VARIANTS.quietnight(), 'a one-burst night');
await shot('quiet-night-dark');

// And the quietest real night there is: the scan ran clean and found no 4%
// burst at all. The EMAIL's version of this said "No candidates passed the
// quality gate today" directly under "4% bursts found: 0" -- blaming the
// checklist for an outcome it had no part in, which is this project's named
// collapse arriving from the opposite direction. The page is checked for the
// same sentence rather than assumed clear of it.
await open('/v/quietmarket/');
await setTheme('dark');
await page.waitForTimeout(200);
await checksForAnyRun(VARIANTS.quietmarket(), 'a night with no burst at all');
// innerText, not textContent: this page's <script> lives inside <body>, so
// textContent hands back the source too -- and its comments discuss the very
// sentences being searched for. The first version of this check failed on its
// own commentary, which is the "asserting the page's own source" shape this
// project has already been caught by once.
const quietBody = (await page.evaluate(() => document.body.innerText)).replace(/\s+/g, ' ');
ok('a night with no burst at all blames nothing on the checklist',
  !/passed the (quality|2LYNCH) gate today/i.test(quietBody)
  && !/rejected at the/i.test(quietBody),
  (quietBody.match(/.{0,90}(passed the (quality|2LYNCH) gate today|rejected at the).{0,60}/i) || [''])[0]);
// And it still says what DID happen, in the one place left that can: the
// funnel's widest cut is the burst filter, and it names it.
ok('and says where every name was cut, which is the burst filter itself',
  (await page.textContent('#funnel-hint')).includes('at "4% bursts"'),
  (await page.textContent('#funnel-hint')).replace(/\s+/g, ' '));
await shot('quiet-market-dark');

await browser.close();
server.close();

// README says how many checks this is. The number is the kind of fact that
// rots silently -- three doc claims in this repo already did, which is why
// tests/test_docs_are_true.py exists -- so it is checked here, where the real
// number is. Counted after every other check has run, and counting itself.
const readme = await readFile(join(ROOT, '..', 'README.md'), 'utf8');
// README says how many variants there are too, and that number said six,
// then eight, while VARIANTS grew to sixteen -- the same rot, one paragraph
// up. Counted off the object, excluding the one name that serves no document.
const served = Object.keys(VARIANTS).filter((name) => name !== 'nodata').length;
const variants = readme.match(/(\d+) mutated copies of it/);
ok("README's count of the mutated fixtures is the real one",
  !!variants && Number(variants[1]) === served,
  `README says ${variants ? variants[1] : 'nothing'}, VARIANTS serves ${served}`);
const claimed = readme.match(/It runs (\d+) checks/);
ok("README's count of these checks is the real one",
  !!claimed && Number(claimed[1]) === results.length + 1,
  `README says ${claimed ? claimed[1] : 'nothing'}, this run has ${results.length + 1}`);

for (const r of results) console.log(`  ${r.pass ? 'ok  ' : 'FAIL'}  ${r.name}${r.detail ? '  — ' + r.detail : ''}`);
// The no-data pass deliberately serves a 500, so its own console noise is not
// a defect; everything else is.
const noise = [...new Set(errors)].filter((e) => !/HTTP 500|the pipeline has not written this|\/v\/nodata\//.test(e));
if (noise.length) { console.log('\n  the page logged errors:'); for (const e of noise) console.log('      - ' + e); }
const failed = results.filter((r) => !r.pass).length;
console.log(`\ndashboard smoke: ${results.length - failed}/${results.length} checks, ${noise.length} page error${noise.length === 1 ? '' : 's'}`
  + (aborted.length ? ` (${aborted.length} chart request${aborted.length === 1 ? '' : 's'} aborted by navigation, not counted)` : ''));
if (SHOTS) console.log(`screenshots: ${SHOTS}`);
process.exit(failed || noise.length ? 1 : 0);
