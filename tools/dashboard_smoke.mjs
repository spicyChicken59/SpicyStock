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
// disk, and every other host is answered with an empty body. Two mutated
// copies of data.json are served alongside the real one, so the states the
// fixture cannot be in — forward returns that exist, a run that failed part
// way — are exercised too.
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
// /v/<name>/   the same index.html against a mutated data.json, for the states
//              a single day's fixture cannot hold at once
const REAL = JSON.parse(await readFile(join(ROOT, 'data.json'), 'utf8'));
const clone = () => JSON.parse(JSON.stringify(REAL));
const VARIANTS = {
  // What the page must look like once step 9 starts recording forward returns.
  forward() {
    const d = clone();
    const vals = [[2.41, 3.02, -0.87], [-1.16, 0.44, 1.98], [0.73, 4.12, 5.6], [3.05, 2.2, 2.9], [-2.4, -3.11, -1.05]];
    d.candidates.slice(0, 5).forEach((c, i) => {
      c.forward_returns = { d1: vals[i][0], d3: vals[i][1], d5: vals[i][2], as_of: '2026-09-08' };
    });
    d.runs[0].forward_returns = { d1: 0.52, d3: 1.33, d5: 1.71, n: d.candidates.length };
    return d;
  },
  // A run that got part way and lost something on the way.
  degraded() {
    const d = clone();
    d.run.errors = [{ stage: 'scanner', message: 'Alpaca returned no bars for 214 symbols; those were skipped.' }];
    return d;
  },
  // The pipeline has never run, or the write failed.
  nodata() { return null; }
};

const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
                '.png': 'image/png', '.svg': 'image/svg+xml', '.ico': 'image/x-icon' };
const server = createServer(async (req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0]);
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
  // The fixture names chart PNGs the repo does not ship, because the pipeline
  // writes them and it has not run here. Every one 404s and the page swaps in
  // an explained frame — that is the state under test, so these are counted
  // and asserted on below rather than treated as page errors.
  if (/\/charts\/[^/]+\.png$/.test(url)) { chart404.add(url); return; }
  errors.push('console: ' + m.text() + (url ? ' @ ' + url : ''));
});
page.on('requestfailed', (r) => errors.push('request failed: ' + r.url().slice(0, 90)));

const results = [];
const ok = (name, pass, detail = '') => results.push({ name, pass: !!pass, detail });
const shot = async (n) => { if (SHOTS) await page.screenshot({ path: join(SHOTS, n + '.png'), fullPage: true }); };
async function open(path = '/index.html') {
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

// --- the run opens ---------------------------------------------------------
// "auto" follows the runner's OS, which in headless Chromium is light, so each
// theme is pinned explicitly rather than assumed.
await open();
await setTheme('dark');
await page.waitForTimeout(200);
ok('the run opens', (await page.textContent('#h1')) !== 'Snapshot unavailable', await page.textContent('#h1'));
ok('the headline states the funnel',
  (await page.textContent('#h1')) === `${run.bursts} bursts, ${run.scored} scored, ${run.shortlist_size} on the shortlist`,
  await page.textContent('#h1'));
ok('four tiles', (await page.locator('#kpis .sc-tile').count()) === 4);

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
ok('the reason a burst went unscored is on its row',
  (await page.locator('#gated-table tbody tr', { hasText: 'over the call cap' }).count())
    === REAL.gated_out.filter((g) => g.reason === 'score_cap').length);

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

// --- the charts the pipeline has not written yet ---------------------------
// Until the pipeline publishes PNGs into docs/, every chart path 404s. That is
// the normal state and the reader must get a frame that explains it, not a
// broken image icon.
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
    chip: cr(getComputedStyle(chip).color, getComputedStyle(chip).backgroundColor),
    marks: [...document.querySelectorAll('#shortlist .sc-frame__mark')]
      .filter((m) => getComputedStyle(m).display !== 'none').length
  };
});
ok('light mode is actually light', !light.dark, light.bg);
ok('the headline is readable in light mode', light.h1 >= 4.5, light.h1.toFixed(2) + ':1');
ok('the fallback label is readable in light mode', light.chip >= 4.5, light.chip.toFixed(2) + ':1');
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
await shot('forward-returns');

await open('/v/degraded/');
ok('a run that lost something says so at the top', !(await page.locator('#notice').isHidden()));
ok('and names what it lost', (await page.textContent('#notice')).includes('214 symbols'), await page.textContent('#notice'));
ok('the rest of the run still renders', (await page.locator('#scores-table tbody tr').count()) === run.scored);

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

await browser.close();
server.close();

for (const r of results) console.log(`  ${r.pass ? 'ok  ' : 'FAIL'}  ${r.name}${r.detail ? '  — ' + r.detail : ''}`);
// The no-data pass deliberately serves a 500, so its own console noise is not
// a defect; everything else is.
const noise = [...new Set(errors)].filter((e) => !/HTTP 500|the pipeline has not written this|\/v\/nodata\//.test(e));
if (noise.length) { console.log('\n  the page logged errors:'); for (const e of noise) console.log('      - ' + e); }
const failed = results.filter((r) => !r.pass).length;
console.log(`\ndashboard smoke: ${results.length - failed}/${results.length} checks, ${noise.length} page error${noise.length === 1 ? '' : 's'}`);
if (SHOTS) console.log(`screenshots: ${SHOTS}`);
process.exit(failed || noise.length ? 1 : 0);
