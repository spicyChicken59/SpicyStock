#!/usr/bin/env node
// Checks docs/app-chart.js, the annotated candlestick chart, in two halves.
//
// 1. Geometry, in Node with no browser: SCStock.chartGeometry() is a pure
//    function, so its scales, candle rects and annotation positions are
//    asserted directly against a synthetic 120-bar series.
// 2. Rendering, in playwright's chromium: a minimal page that links the
//    vendored design system and docs/app-chart.js, opened at 360px and 1280px
//    in both themes. Asserts no page errors, the host contract, the table
//    twin, the tooltip on hover / keyboard / tap, and that every text and
//    mark wears a token the theme resolves. Screenshots go to --shots <dir>
//    (default: the session scratchpad's chart/shots).
//
// Chromium is not a repo dependency: a global playwright install beside the
// node binary is found the way tools/dashboard_smoke.mjs finds it, and the
// browsers under PLAYWRIGHT_BROWSERS_PATH (default /opt/pw-browsers). Without
// a browser the geometry half still runs and the render half is skipped.
import { createServer } from 'node:http';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { extname, join, resolve, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import vm from 'node:vm';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, '..');
const ROOT = join(REPO, 'docs');
const DS = join(ROOT, 'design-system');
const argv = process.argv.slice(2);
const SCRATCH = process.env.CLAUDE_SCRATCHPAD || '/tmp/claude-0/-home-user/edc6f11d-ce23-5094-b116-41a165a13e91/scratchpad';
const SHOTS = argv.includes('--shots') ? argv[argv.indexOf('--shots') + 1] : join(SCRATCH, 'chart', 'shots');
const NO_BROWSER = argv.includes('--no-browser');
if (!process.env.PLAYWRIGHT_BROWSERS_PATH && existsSync('/opt/pw-browsers')) process.env.PLAYWRIGHT_BROWSERS_PATH = '/opt/pw-browsers';

const results = [];
const ok = (name, pass, detail = '') => { results.push({ name, pass: !!pass, detail }); if (!pass) console.log('  FAIL  ' + name + (detail ? ' -- ' + detail : '')); };

// --- the synthetic series ----------------------------------------------------
// Deterministic (mulberry32), so a screenshot and a geometry number can be
// compared across runs. Shape: a 65-session advance, a pullback, a 17-session
// tight base, a +7% burst on 3x volume at index 111, then follow-through.
// Index 30 is a GAP bar (null o/h/l, close kept); index 31 has no bar at all.
function rng(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function sessions(n, last) {
  const out = []; const d = new Date(last + 'T12:00:00Z');
  while (out.length < n) { const wd = d.getUTCDay(); if (wd !== 0 && wd !== 6) out.unshift(d.toISOString().slice(0, 10)); d.setUTCDate(d.getUTCDate() - 1); }
  return out;
}
export function synthetic() {
  const r = rng(20260909), dates = sessions(120, '2026-09-09'), bars = [];
  const BURST = 111; let close = 62, base = { start: 94, end: 110 };
  for (let i = 0; i < 120; i++) {
    let drift, noise, volBase = 1.4e6;
    if (i < 65) { drift = 0.0075; noise = 0.014; }                       // advance
    else if (i < base.start) { drift = -0.004; noise = 0.012; }          // pullback
    else if (i <= base.end) { drift = 0.0005; noise = 0.007; volBase = 0.8e6; } // tight base, volume dries up
    else if (i === BURST) { drift = 0.07; noise = 0.002; volBase = 4.2e6; } // burst
    else { drift = 0.006; noise = 0.012; volBase = 2.2e6; }              // follow-through
    const o = i === BURST ? close * 1.003 : close * (1 + (r() - 0.5) * noise);
    const c = i === BURST ? close * 1.07 : close * (1 + drift + (r() - 0.5) * noise * 2);
    const h = Math.max(o, c) * (1 + r() * noise * 0.8), l = i === BURST ? o * 0.994 : Math.min(o, c) * (1 - r() * noise * 0.8);
    const v = Math.round(volBase * (0.7 + r() * 0.6));
    const round = (x) => Math.round(x * 100) / 100;
    bars.push({ date: dates[i], o: round(o), h: round(h), l: round(l), c: round(c), v });
    close = c;
  }
  bars[30] = { date: bars[30].date, o: null, h: null, l: null, c: bars[30].c, v: bars[30].v };
  bars[31] = { date: bars[31].date, o: null, h: null, l: null, c: null, v: null };
  const inBase = bars.slice(base.start, base.end + 1);
  const boxLow = Math.min(...inBase.map((b) => b.l)), boxHigh = Math.max(...inBase.map((b) => b.h));
  const trigger = Math.round(boxHigh * 100) / 100, entryLow = trigger, entryHigh = Math.round(trigger * 1.02 * 100) / 100;
  const options = {
    ticker: 'SPCY', title: 'daily · 120 sessions · 4% burst out of a 17-session base',
    burstIndex: BURST, box: { start: base.start, end: base.end, low: boxLow, high: boxHigh },
    stop: bars[BURST].l, entryLow, entryHigh, trigger,
    targetLow: Math.round(entryHigh * 1.08 * 100) / 100, targetHigh: Math.round(entryHigh * 1.20 * 100) / 100,
    ma: [10, 20, 50], height: 320
  };
  return { bars, options, BURST };
}

// --- 1. geometry, no DOM ------------------------------------------------------
const SRC_CHARTS = await readFile(join(DS, 'sc-charts.js'), 'utf8');
// SCSTOCK_CHART=<path> checks a copy of the module instead of docs/app-chart.js,
// which is how a mutant is run without editing the tree; the browser half
// serves the same bytes at /app-chart.js.
const APP = process.env.SCSTOCK_CHART ? resolve(process.env.SCSTOCK_CHART) : join(ROOT, 'app-chart.js');
const SRC_APP = await readFile(APP, 'utf8');
function loadInSandbox() {
  const sb = { console }; sb.window = sb; vm.createContext(sb);
  vm.runInContext(SRC_CHARTS, sb, { filename: 'sc-charts.js' });
  vm.runInContext(SRC_APP, sb, { filename: 'app-chart.js' });
  return sb.SCStock;
}
const SCStock = loadInSandbox();
const { bars, options, BURST } = synthetic();
const g = SCStock.chartGeometry(bars, options, 1280, 320);
const g360 = SCStock.chartGeometry(bars, options, 360, 320);

{
  // the source names no colour: every mark is painted through a token
  const code = SRC_APP.replace(/\/\*[\s\S]*?\*\//g, '');
  ok('source names no raw colour (hex, rgb, hsl)', !/#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(/.test(code));
  ok('source paints through the --sc-tone channel', /--sc-tone:var\(--sc-/.test(code) && !/stroke:\s*['"]?#/.test(code));
  ok('source is an IIFE on window with no ES2015 syntax', /^\(function \(w\)/m.test(SRC_APP) && !/=>|\bconst\b|\blet\b|`/.test(code));

  // x is monotonic in the index, y monotonic decreasing in price, on both widths
  for (const [name, gg] of [['1280', g], ['360', g360]]) {
    let xs = true, ys = true;
    for (let i = 1; i < gg.n; i++) if (!(gg.x(i) > gg.x(i - 1))) xs = false;
    const step = (gg.domain.hi - gg.domain.lo) / 50;   // y rounds to 0.1px, so step by 2% of the span, not by a cent
    for (let p = gg.domain.lo; p + step <= gg.domain.hi; p += step) if (!(gg.y(p + step) < gg.y(p))) ys = false;
    ok(`scales are monotonic at ${name}px`, xs && ys);
    ok(`price pane sits above the volume pane at ${name}px`, gg.plot.bottom < gg.vol.top && gg.vol.bottom < gg.height && gg.plot.top > 0);
    ok(`every candle sits inside the price pane at ${name}px`, gg.bars.every((b) => !b.candle || (b.candle.wickTop >= gg.plot.top - 0.5 && b.candle.wickBottom <= gg.plot.bottom + 0.5)));
    ok(`every volume bar sits inside the volume pane at ${name}px`, gg.bars.every((b) => !b.volume || (b.volume.y >= gg.vol.top - 0.5 && b.volume.y + b.volume.h <= gg.vol.bottom + 0.5)));
    ok(`body width is at least 1px and the bars fill the plot at ${name}px`, gg.bodyWidth >= 1 && Math.abs(gg.x(gg.n - 1) + gg.slot / 2 - gg.plot.right) < 1);
    const gutterTexts = gg.rightLabels.map((l) => l.text.length);
    ok(`the right gutter fits its widest label at ${name}px`, gg.gutter >= Math.max(...gutterTexts) * 6.6 + 10);
    const sorted = gg.rightLabels.slice().sort((a, b) => a.y - b.y);
    ok(`right-edge labels never overlap at ${name}px`, sorted.every((l, i) => !i || l.y - sorted[i - 1].y >= 12.9) && sorted.every((l) => l.y >= gg.plot.top && l.y <= gg.plot.bottom));
    const leftSorted = gg.leftLabels.slice().sort((a, b) => a.y - b.y);
    ok(`left-edge level labels never overlap at ${name}px`, leftSorted.every((l, i) => !i || l.y - leftSorted[i - 1].y >= 14.9));
  }

  // a gap bar draws nothing; its neighbours draw
  ok('a null-open bar yields no candle rect', g.bars[30].candle === null && g.bars[31].candle === null && g.bars[29].candle !== null && g.bars[32].candle !== null);
  ok('a bar with no volume yields no volume rect', g.bars[31].volume === null && g.bars[30].volume !== null);
  ok('a gap bar keeps its slot (nothing is spliced)', g.n === 120 && g.bars[32].x - g.bars[29].x > 2.5 * g.slot);

  // levels
  const highs = bars.filter((b) => b.h !== null).map((b) => b.h), lows = bars.filter((b) => b.l !== null).map((b) => b.l);
  const yMax = g.y(Math.max(...highs)), yMin = g.y(Math.min(...lows));
  ok('the stop line y is between the price extremes', g.stop && g.stop.y > yMax && g.stop.y < yMin && g.stop.y >= g.plot.top && g.stop.y <= g.plot.bottom);
  ok('the stop sits below the burst bar', g.stop.y >= g.burst.yLow - 0.5);
  ok('the stop is under the trigger, which is under the buy zone', g.stop.y > g.trigger.y && g.trigger.y >= g.entry.y2 - 0.6);
  ok('a level label the collision pass moved carries a leader back to its line', g.leftLabels.filter((l) => Math.abs(l.y - l.yTrue) > 2).every((l) => l.leader && Math.abs(l.leader.y1 - (l.kind === 'stop' ? g.stop.y : l.kind === 'trigger' ? g.trigger.y : g.entry.y1)) < 0.6) && g.leftLabels.filter((l) => Math.abs(l.y - l.yTrue) <= 2).every((l) => !l.leader));
  ok('the burst column spans both panes over the burst slot', g.burst.column && g.burst.column.y === g.plot.top && Math.abs(g.burst.column.y + g.burst.column.h - g.vol.bottom) < 0.2 && g.burst.column.x <= g.burst.x && g.burst.column.x + g.burst.column.w >= g.burst.x);
  ok('at 360px the base label does not sit on a level label', g360.leftLabels.every((l) => Math.abs(l.y - g360.box.label.y) >= 14 || g360.box.label.x >= l.x + l.text.length * 6.6 + 8));
  ok('the target band is above the entry zone', g.target && g.entry && g.target.y2 <= g.entry.y1 && g.target.y1 < g.target.y2);
  ok('the target label reads +8% … +20% off the entry reference', g.target.text === '+8% … +20%' && g.target.pctLow === 8 && g.target.pctHigh === 20);
  ok('the entry zone is inside the pane and its label names both bounds', g.entry.y1 >= g.plot.top && g.entry.y2 <= g.plot.bottom && /^buy zone \$[\d.,]+–\$[\d.,]+$/.test(g.entry.label.text));
  ok('the trigger line carries a labelled price', g.trigger && /^trigger \$/.test(g.trigger.label.text) && Math.abs(g.trigger.y - g.entry.y2) < 0.6);
  ok('the stop label names its price', /^stop \$[\d.,]+$/.test(g.stop.label.text));

  // base box and burst
  ok('the base box spans its sessions and its price range', g.box && g.box.sessions === 17 && Math.abs(g.box.x - (g.plot.left + 94 * g.slot)) < 0.6 && Math.abs(g.box.y - g.y(options.box.high)) < 0.6 && Math.abs(g.box.y + g.box.h - g.y(options.box.low)) < 0.6);
  ok('the base label says base · 17 sessions and sits on the box', g.box.label.text === 'base · 17 sessions' && (g.box.label.y < g.box.y || g.box.label.y > g.box.y + g.box.h) && g.box.label.x >= g.box.x);
  ok('the burst candle is marked and labelled above its high', g.burst && g.burst.index === BURST && /^burst \+\d+\.\d%$/.test(g.burst.label.text) && g.burst.label.y < g.burst.yHigh && g.burst.marker.y > g.burst.yLow);
  ok('the burst percentage is measured off the previous close', Math.abs(g.burst.pct - (bars[BURST].c / bars[BURST - 1].c - 1) * 100) < 1e-9);
  ok('the burst volume bar is the emphasised one', g.bars[BURST].volume.burst === true && g.bars[BURST - 1].volume.burst === false);
  ok('the burst candle is hollow (an up bar) and the down bars are filled', g.bars[BURST].candle.up && !g.bars[BURST].candle.filled && g.bars.some((b) => b.candle && b.candle.filled && !b.candle.up));

  // moving averages
  const closes = bars.map((b) => b.c), s20 = SCStock.sma(closes, 20);
  ok('sma(…, 20) has 19 leading nulls', s20.slice(0, 19).every((v) => v === null) && typeof s20[19] === 'number');
  ok('sma steps over a gap bar rather than splicing it', s20[31] === null && s20[50] === null && typeof s20[51] === 'number');
  ok('sma(…, 20) is the mean of the window', Math.abs(s20[19] - closes.slice(0, 20).reduce((a, b) => a + b, 0) / 20) < 1e-9);
  ok('three averages are drawn and the 20 is heavier', g.ma.length === 3 && g.ma.map((m) => m.n).join() === '10,20,50' && g.ma[1].weight > g.ma[0].weight && g.ma[1].weight > g.ma[2].weight);
  ok('an average has no point where it has no value', g.ma.every((m) => m.points.every((p, i) => (p === null) === (SCStock.sma(closes, m.n)[i] === null))));

  // axis and the degenerate inputs
  ok('date ticks fall on month boundaries, spaced apart', g.dateTicks.length >= 4 && g.dateTicks.every((t) => bars[t.index].date.slice(8, 10) <= '03') && g.dateTicks.every((t, i) => !i || t.x - g.dateTicks[i - 1].x >= 30));
  ok('gridlines lie inside the domain', g.grid.length >= 3 && g.grid.every((t) => t.value > g.domain.lo && t.value < g.domain.hi));
  ok('the domain includes every level, padded', g.domain.lo < options.stop && g.domain.hi > options.targetHigh && g.domain.lo < Math.min(...lows));
  {
    // a level OUTSIDE the price range must stretch the domain, or the line is drawn off the pane
    const tail = bars.slice(90), tLow = Math.min(...tail.map((b) => b.l)), tHigh = Math.max(...tail.map((b) => b.h));
    const far = SCStock.chartGeometry(tail, { stop: tLow * 0.8, targetLow: tHigh * 1.15, targetHigh: tHigh * 1.3, trigger: tHigh * 1.05, entryLow: tHigh * 1.05, entryHigh: tHigh * 1.07 }, 640, 320);
    ok('a stop far below the bars still lands inside the pane', far.stop.y <= far.plot.bottom && far.stop.y > far.y(tLow));
    ok('a target far above the bars still lands inside the pane', far.target.y1 >= far.plot.top && far.target.y2 < far.y(tHigh));
    ok('a trigger and buy zone above every bar still land inside the pane', far.trigger.y >= far.plot.top && far.entry.y1 >= far.plot.top);
  }
  let threw = null;
  try {
    const empty = SCStock.chartGeometry([], {}, 400, 200);
    const bare = SCStock.chartGeometry(bars, { burstIndex: null, box: null, stop: null, ma: [] }, 400, 200);
    const short = SCStock.chartGeometry(bars.slice(0, 12), { burstIndex: 5, box: { start: 0, end: 4, low: 60, high: 65 } }, 360, 180);
    const junk = SCStock.chartGeometry([{ date: 'x' }, null, { o: 'a', h: 1, l: 2, c: 3 }], { burstIndex: 2, box: { start: 9, end: 1 } }, 400, 200);
    ok('an empty series, a bare chart, a short series and junk rows all compute', empty.n === 0 && bare.burst === null && bare.ma.length === 0 && short.dateTicks.length >= 2 && short.burst && junk.burst === null && junk.box === null);
    ok('a burst index that names a gap bar is not a burst', SCStock.chartGeometry(bars, { burstIndex: 30 }, 400, 200).burst === null);
    ok('an inverted entry zone is put the right way up', SCStock.chartGeometry(bars, { entryLow: 100, entryHigh: 90 }, 400, 200).entry.low === 90);
  } catch (e) { threw = e; }
  ok('degenerate inputs do not throw', !threw, threw && threw.message);
}

// --- 2. rendering ---------------------------------------------------------------
async function loadChromium() {
  if (NO_BROWSER) return null;
  const tries = [
    () => import('playwright'),
    ...[...(process.env.NODE_PATH || '').split(':'), resolve(dirname(process.execPath), '..', 'lib', 'node_modules')]
      .filter(Boolean)
      .map((root) => () => import(pathToFileURL(join(root, 'playwright', 'index.js')).href))
  ];
  for (const t of tries) { try { const m = await t(); const c = m.chromium || (m.default && m.default.chromium); if (c) return c; } catch { /* next */ } }
  return null;
}
const chromium = await loadChromium();
if (!chromium) {
  console.log('  skip  playwright is not installed — the chart was not rendered');
} else {
  const HARNESS = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>SCStock chart harness</title>
<link rel="stylesheet" href="design-system/sc.css">
<script src="design-system/sc-theme.js"></script>
<script src="design-system/sc-charts.js"></script>
<script src="app-chart.js"></script>
<script>(function(){var t=new URLSearchParams(location.search).get('theme');if(t)document.documentElement.setAttribute('data-theme',t);})();</script>
</head><body>
<main class="sc-wrap sc-wrap--wide" style="padding-block:24px">
<div class="sc-card"><div class="sc-card__head"><h2>SPCY</h2><p class="sc-hint">annotated daily chart</p></div><div id="full"></div></div>
<div class="sc-card" style="margin-top:16px"><div class="sc-card__head"><h3>compact</h3></div><div id="compact"></div></div>
</main>
<script>
  window.__data = ${JSON.stringify({ bars, options })};
  var full = SCStock.chart(window.__data.bars, window.__data.options);
  full.id = 'chart-full';
  document.getElementById('full').appendChild(full);
  var c = SCStock.chart(window.__data.bars.slice(60), Object.assign({}, window.__data.options, { compact: true, height: 200, burstIndex: 51, box: { start: 34, end: 50, low: window.__data.options.box.low, high: window.__data.options.box.high } }));
  c.id = 'chart-compact';
  document.getElementById('compact').appendChild(c);
</script></body></html>`;
  await mkdir(SHOTS, { recursive: true });
  await writeFile(join(SHOTS, '..', 'harness.html'), HARNESS);

  const TYPES = { '.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon', '.woff2': 'font/woff2' };
  const server = createServer(async (req, res) => {
    const p = decodeURIComponent(new URL(req.url, 'http://x').pathname);
    if (p === '/chart-harness.html') { res.writeHead(200, { 'content-type': TYPES['.html'] }).end(HARNESS); return; }
    if (p === '/app-chart.js') { res.writeHead(200, { 'content-type': TYPES['.js'] }).end(SRC_APP); return; }
    const file = resolve(join(ROOT, p));
    if (!file.startsWith(ROOT)) { res.writeHead(403).end(); return; }
    let body;
    try { body = await readFile(file); } catch { res.writeHead(404).end('not found'); return; }
    res.writeHead(200, { 'content-type': TYPES[extname(file)] || 'application/octet-stream' }).end(body);
  });
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  const BASE = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch();

  async function session({ width, height, theme, touch }) {
    const ctx = await browser.newContext({ viewport: { width, height }, colorScheme: theme, hasTouch: !!touch, reducedMotion: 'reduce' });
    // the sheet @imports Google Fonts; offline, every external request is answered empty
    await ctx.route(/^https?:\/\/(?!127\.0\.0\.1)/, (r) => r.fulfill({ status: 200, contentType: 'text/plain', body: '' }));
    const page = await ctx.newPage(), errors = [];
    page.on('pageerror', (e) => errors.push('uncaught: ' + e.message));
    page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
    page.on('requestfailed', (r) => errors.push('request failed: ' + r.url()));
    await page.goto(`${BASE}/chart-harness.html?theme=${theme}`, { waitUntil: 'load' });
    await page.waitForSelector('#chart-full .sc-chart__stage > svg');
    return { ctx, page, errors };
  }

  for (const theme of ['dark', 'light']) {
    for (const width of [360, 1280]) {
      const tag = `${theme}-${width}`;
      const { ctx, page, errors } = await session({ width, height: width === 360 ? 800 : 900, theme });
      await page.waitForTimeout(150);
      ok(`${tag}: no page errors`, errors.length === 0, errors.join(' | '));
      const host = page.locator('#chart-full');
      ok(`${tag}: host is .sc-chart[role=group][tabindex=0] with an aria-label`, await host.evaluate((h) => h.classList.contains('sc-chart') && h.getAttribute('role') === 'group' && h.getAttribute('tabindex') === '0' && /SPCY daily candlestick chart, 120 sessions/.test(h.getAttribute('aria-label') || '')));
      ok(`${tag}: the SVG is aria-hidden and as wide as its host`, await host.evaluate((h) => { const s = h.querySelector('.sc-chart__stage > svg'); const r = s.getBoundingClientRect(); return s.getAttribute('aria-hidden') === 'true' && Math.abs(r.width - h.clientWidth) < 2 && s.getAttribute('viewBox').split(' ')[2] === String(Math.round(h.clientWidth)); }));
      ok(`${tag}: the table twin holds the last 10 bars and the levels`, await host.evaluate((h) => h.querySelectorAll('.sc-details [data-sc-twin=bars] tbody tr').length === 10 && h.querySelectorAll('.sc-details [data-sc-twin=levels] tbody tr').length === 7 && h.querySelector('.sc-details summary') !== null));
      ok(`${tag}: the table twin's newest row is the last session and names the burst row`, await host.evaluate((h) => { const rows = [...h.querySelectorAll('[data-sc-twin=bars] tbody tr')].map((r) => r.firstChild.textContent); return rows[0] === '2026-09-09' && rows.some((t) => /▲ burst$/.test(t)); }));
      ok(`${tag}: every annotation label is drawn`, await host.evaluate((h) => { const t = [...h.querySelectorAll('svg text')].map((x) => x.textContent); return ['base · 17 sessions', '+8% … +20%'].every((s) => t.includes(s)) && t.some((s) => /^burst \+/.test(s)) && t.some((s) => /^stop \$/.test(s)) && t.some((s) => /^buy zone \$/.test(s)) && t.some((s) => /^trigger \$/.test(s)); }));
      // text wears text tokens, never a series colour; marks wear chart tokens
      const paint = await host.evaluate((h) => {
        const cs = getComputedStyle(document.documentElement);
        const probe = document.createElement('i'); h.appendChild(probe);
        const res = (t) => { probe.style.color = 'var(' + t + ')'; return getComputedStyle(probe).color; };
        const textTokens = ['--sc-heading', '--sc-text', '--sc-text-2', '--sc-text-3'].map(res);
        const marks = { emphasis: res('--sc-chart-emphasis'), context: res('--sc-chart-context'), accent: res('--sc-accent'), danger: res('--sc-danger'), warn: res('--sc-warn'), good: res('--sc-good') };
        const texts = [...h.querySelectorAll('svg text')].map((t) => getComputedStyle(t).fill);
        const badText = texts.filter((f) => !textTokens.includes(f));
        const st = h.querySelector('.sc-chart__stage'); const up = st.querySelector('.sc-chart__candle:not(.is-filled):not(.sc-chart__candle--burst)'), down = st.querySelector('.sc-chart__candle.is-filled'), burst = st.querySelector('.sc-chart__candle--burst');
        const stop = h.querySelector('.sc-chart__level--dashed'), trig = h.querySelector('.sc-chart__level--dotted'), strip = h.querySelector('.sc-chart__strip'), flag = h.querySelector('.sc-chart__flag');
        const out = {
          badText: badText.length, nText: texts.length,
          up: getComputedStyle(up).stroke === marks.emphasis && getComputedStyle(up).fill === 'none',
          down: getComputedStyle(down).fill === marks.context && getComputedStyle(down).stroke === marks.context,
          burst: getComputedStyle(burst).stroke === marks.accent && getComputedStyle(flag).fill === marks.accent,
          stop: getComputedStyle(stop).stroke === marks.danger, trigger: getComputedStyle(trig).stroke === marks.warn, target: getComputedStyle(strip).fill === marks.good,
          emphasis: marks.emphasis, fontPx: getComputedStyle(st.querySelector('text')).fontSize,
          inlineHex: [...h.querySelectorAll('svg *')].some((e) => /#[0-9a-f]{3,8}|rgb\(/i.test(e.getAttribute('style') || '') || /#[0-9a-f]{3,8}/i.test(e.getAttribute('fill') || '') || /#[0-9a-f]{3,8}/i.test(e.getAttribute('stroke') || ''))
        };
        probe.remove(); return out;
      });
      ok(`${tag}: every SVG text wears a text token`, paint.badText === 0 && paint.nText > 10, `${paint.badText} of ${paint.nText}`);
      ok(`${tag}: up candles are hollow emphasis, down candles filled context, the burst wears the accent`, paint.up && paint.down && paint.burst);
      ok(`${tag}: stop, trigger and target resolve to danger, warn and good`, paint.stop && paint.trigger && paint.target);
      ok(`${tag}: no mark carries an inline colour and text is 11px`, !paint.inlineHex && paint.fontPx === '11px', paint.fontPx);
      if (width === 1280) ok(`${tag}: the emphasis token resolves differently per theme`, theme === 'dark' ? paint.emphasis === 'rgb(113, 161, 223)' : paint.emphasis === 'rgb(39, 102, 177)', paint.emphasis);

      // hover: the tooltip lists the hovered bar
      const hit = await host.locator('.sc-chart__hit').boundingBox();
      const geo = await host.evaluate((h, B) => { const d = window.__data; const gg = SCStock.chartGeometry(d.bars, d.options, h.clientWidth, d.options.height); return { xb: gg.x(B), top: gg.plot.top }; }, BURST);
      const svgBox = await host.locator('.sc-chart__stage > svg').boundingBox();
      await page.mouse.move(svgBox.x + geo.xb, svgBox.y + geo.top + 40);
      await page.waitForTimeout(80);
      const tipHover = await host.evaluate((h) => { const t = h.querySelector('.sc-tooltip'); return { on: t.classList.contains('is-on'), date: (t.querySelector('.sc-tooltip__date') || {}).textContent, rows: t.querySelectorAll('.sc-tooltip__row').length, meta: (t.querySelector('.sc-tooltip__meta') || {}).textContent, cross: h.querySelector('.sc-chart__cross').getAttribute('visibility') }; });
      ok(`${tag}: hovering the burst bar shows the tooltip for it`, tipHover.on && /2026-09-0[0-9]|2026-09-1[0-9]|2026-08/.test(tipHover.date || '') && tipHover.rows === 6 && /burst day/.test(tipHover.meta || '') && tipHover.cross === 'visible', JSON.stringify(tipHover));
      await page.mouse.move(5, 5);
      await page.waitForTimeout(60);
      ok(`${tag}: leaving hides the tooltip`, await host.evaluate((h) => !h.querySelector('.sc-tooltip').classList.contains('is-on')));
      // keyboard: the first arrow reveals the cursor on the burst, the next moves it
      await host.focus();
      await page.keyboard.press('ArrowLeft');
      const k1 = await host.evaluate((h) => h.querySelector('.sc-tooltip__date').textContent);
      await page.keyboard.press('ArrowLeft');
      const k2 = await host.evaluate((h) => h.querySelector('.sc-tooltip__date').textContent);
      await page.keyboard.press('ArrowRight');
      const k3 = await host.evaluate((h) => ({ date: h.querySelector('.sc-tooltip__date').textContent, on: h.querySelector('.sc-tooltip').classList.contains('is-on'), live: h.querySelector('.sc-tooltip').getAttribute('aria-live') }));
      ok(`${tag}: arrow keys step the focused bar and update the tooltip`, k1.endsWith(bars[BURST].date) && k2.endsWith(bars[BURST - 1].date) && k3.date.endsWith(bars[BURST].date) && k3.on && k3.live === 'polite', `${k1} / ${k2} / ${k3.date}`);
      await page.keyboard.press('Escape');
      ok(`${tag}: escape hides it`, await host.evaluate((h) => !h.querySelector('.sc-tooltip').classList.contains('is-on')));
      await page.keyboard.press('End');
      ok(`${tag}: End goes to the last session`, (await host.evaluate((h) => h.querySelector('.sc-tooltip__date').textContent)).endsWith(bars[119].date));
      await host.evaluate((h) => h.blur());
      await page.waitForTimeout(60);
      ok(`${tag}: no page errors after interaction`, errors.length === 0, errors.join(' | '));
      await page.screenshot({ path: join(SHOTS, `${tag}.png`), fullPage: true });
      await host.screenshot({ path: join(SHOTS, `${tag}-chart.png`) });
      await ctx.close();
    }
  }

  // touch: a tap opens a pinned tooltip, a second tap on the same bar closes it
  {
    const { ctx, page, errors } = await session({ width: 360, height: 800, theme: 'dark', touch: true });
    const host = page.locator('#chart-full');
    const svgBox = await host.locator('.sc-chart__stage > svg').boundingBox();
    const geo = await host.evaluate((h, B) => { const d = window.__data; const gg = SCStock.chartGeometry(d.bars, d.options, h.clientWidth, d.options.height); return { xb: gg.x(B), top: gg.plot.top, bottom: gg.plot.bottom }; }, BURST);
    await page.touchscreen.tap(svgBox.x + geo.xb, svgBox.y + (geo.top + geo.bottom) / 2);
    await page.waitForTimeout(80);
    const t1 = await host.evaluate((h) => { const t = h.querySelector('.sc-tooltip'); return { on: t.classList.contains('is-on'), tap: t.classList.contains('sc-tooltip--tap'), date: (t.querySelector('.sc-tooltip__date') || {}).textContent }; });
    ok('touch: a tap opens the tooltip for the tapped bar, pinned', t1.on && t1.tap && (t1.date || '').endsWith(bars[BURST].date), JSON.stringify(t1));
    await page.screenshot({ path: join(SHOTS, 'dark-360-tap.png'), fullPage: false });
    await page.touchscreen.tap(svgBox.x + geo.xb, svgBox.y + (geo.top + geo.bottom) / 2);
    await page.waitForTimeout(80);
    ok('touch: tapping the same bar again closes it', await host.evaluate((h) => !h.querySelector('.sc-tooltip').classList.contains('is-on')));
    ok('touch: no page errors', errors.length === 0, errors.join(' | '));
    // compact chart on the same page
    ok('compact: renders with no legend row and its own twin', await page.evaluate(() => { const c = document.getElementById('chart-compact'); return !!c.querySelector('svg') && !c.querySelector('.sc-chart__head') && c.querySelectorAll('[data-sc-twin=bars] tbody tr').length === 10; }));
    await ctx.close();
  }
  await browser.close();
  server.close();
}

const failed = results.filter((r) => !r.pass);
console.log(`\n${results.length - failed.length}/${results.length} chart checks passed` + (chromium ? `; screenshots in ${SHOTS}` : ''));
process.exit(failed.length ? 1 : 0);
