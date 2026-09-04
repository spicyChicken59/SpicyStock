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
      c.forward_returns = { d1: vals[i][0], d3: vals[i][1], d5: vals[i][2], as_of: '2026-09-08' };
    });
    d.runs[0].forward_returns = { d1: 0.52, d3: 1.33, d5: 1.71, n: d.candidates.length };
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
  // The pipeline has never run, or the write failed.
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
page.on('requestfailed', (r) => errors.push('request failed: ' + r.url().slice(0, 90)));

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
ok('and the sentence above the gated table gives the veto its own clause',
  vetoedRows === 0
  || (hint.includes(`${vetoedRows} refused by an absolute rule`) && !/\d+ refused at the/.test(hint)),
  hint);
ok('and that clause does not fold the vetoed rows into the checklist count',
  vetoedRows === 0
  || hint.includes(`${REAL.gated_out.filter((g) => g.reason === 'lynch_gate').length} rejected at the`),
  hint);

const caption = (await page.$$eval('#funnel-table tbody tr', (rows) => rows.map((r) => r.textContent))).join(' ');
ok('the funnel says an absolute rule can cut a name at the gate stage, when the run applied one',
  ((REAL.run.gate || {}).vetoes || []).length && caption.includes('refused by an absolute rule'),
  `gate.vetoes = ${JSON.stringify((REAL.run.gate || {}).vetoes)}`);
// And the other side of that guard, which is the side it exists for. Run
// against a snapshot carrying no gate.vetoes at all: naming a rule that run
// never applied is the confidently-false sentence, and asserting only the
// positive branch left the guard deletable with everything green.
await open('/v/novetoes/');
const oldCaption = (await page.$$eval('#funnel-table tbody tr', (rows) => rows.map((r) => r.textContent))).join(' ');
const oldHint = await page.textContent('#gated-hint');
ok('and says nothing of the kind about a run that had no absolute rule to apply',
  !oldCaption.includes('refused by an absolute rule')
  && !oldHint.includes('refused by an absolute rule'),
  oldCaption.replace(/\s+/g, ' ').slice(0, 90));
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
ok('and it is the checklist that splits them, not the gate a veto also guards',
  Number.isFinite(clearedShown)
  && clearedShown - run.passed_gate
     === REAL.gated_out.filter((g) => String(g.reason).startsWith('veto_')).length,
  `page shows ${clearedShown} cleared the checklist, run.passed_gate is ${run.passed_gate}`);
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
ok('a burst the record cannot place is a row of its own, never a day 1',
  (await page.locator('#streak-table tbody tr', { hasText: 'not known' }).count())
    === HEV.by_day.filter((d) => d.day === null).length);
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
let refusedOnScreen = 0, gatedOnScreen = 0;
for (const rows of byTicker.values()) {
  rows.sort((a, b) => String(b.date).localeCompare(String(a.date)));
  for (const r of rows.slice(0, 6)) {
    if (r.score !== null && r.score !== undefined) continue;
    if (String(r.reason || '').startsWith('veto_')) refusedOnScreen++;
    else if (r.reason === 'lynch_gate') gatedOnScreen++;
  }
}
const perName = await page.textContent('#ticker-table');
const saidRefused = (perName.match(/refused by an absolute rule/g) || []).length;
const saidGated = (perName.match(/rejected at the gate/g) || []).length;
ok('a burst an absolute rule refused says so in the per-name record too',
  refusedOnScreen > 0 && saidRefused === refusedOnScreen && saidGated === gatedOnScreen,
  `${refusedOnScreen} refusals and ${gatedOnScreen} gate rejections reachable; ` +
  `page said ${saidRefused} and ${saidGated}`);
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
await checksForAnyRun(LIVE, 'docs/');
await shot('live-desktop-dark');

// The same checks over a run that is NOT the fixture, so "holds for any run"
// is exercised rather than asserted.
await open('/v/quietnight/');
await setTheme('dark');
await page.waitForTimeout(200);
await checksForAnyRun(VARIANTS.quietnight(), 'a one-burst night');
await shot('quiet-night-dark');

await browser.close();
server.close();

// README says how many checks this is. The number is the kind of fact that
// rots silently -- three doc claims in this repo already did, which is why
// tests/test_docs_are_true.py exists -- so it is checked here, where the real
// number is. Counted after every other check has run, and counting itself.
const claimed = (await readFile(join(ROOT, '..', 'README.md'), 'utf8')).match(/It runs (\d+) checks/);
ok("README's count of these checks is the real one",
  !!claimed && Number(claimed[1]) === results.length + 1,
  `README says ${claimed ? claimed[1] : 'nothing'}, this run has ${results.length + 1}`);

for (const r of results) console.log(`  ${r.pass ? 'ok  ' : 'FAIL'}  ${r.name}${r.detail ? '  — ' + r.detail : ''}`);
// The no-data pass deliberately serves a 500, so its own console noise is not
// a defect; everything else is.
const noise = [...new Set(errors)].filter((e) => !/HTTP 500|the pipeline has not written this|\/v\/nodata\//.test(e));
if (noise.length) { console.log('\n  the page logged errors:'); for (const e of noise) console.log('      - ' + e); }
const failed = results.filter((r) => !r.pass).length;
console.log(`\ndashboard smoke: ${results.length - failed}/${results.length} checks, ${noise.length} page error${noise.length === 1 ? '' : 's'}`);
if (SHOTS) console.log(`screenshots: ${SHOTS}`);
process.exit(failed || noise.length ? 1 : 0);
