// Check painted chart labels, not only the document's scroll width.
// All data and assets come from this checkout; external requests are blocked.
// node tools/mobile_layout_smoke.mjs [--shots /tmp/mobile-shots]
// node tools/mobile_layout_smoke.mjs --baseline c765880 --expect-layout-failure
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createServer } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { dirname, extname, join, resolve, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const DOCS = join(REPO, 'docs');
const args = process.argv.slice(2);
function option(name) {
  const index = args.indexOf(name);
  if (index < 0) return null;
  assert.ok(args[index + 1] && !args[index + 1].startsWith('--'), `${name} requires a value`);
  return args[index + 1];
}
const shots = option('--shots');
const baseline = option('--baseline');
const expectFailure = args.includes('--expect-layout-failure');
assert.ok(!expectFailure || baseline, '--expect-layout-failure requires --baseline');
assert.ok(!baseline || /^[a-f0-9]{7,40}$/i.test(baseline), '--baseline must be a commit hash');
if (shots) await mkdir(resolve(shots), { recursive: true });

const [recorded, fixture, history] = await Promise.all([
  'docs/data.json', 'tests/fixtures/data.json', 'tests/fixtures/history/data.json'
].map(async path => JSON.parse(await readFile(join(REPO, path), 'utf8'))));
// The history fixture's newest candidates are pending. Synthetic fills expose
// the outcome chart too, including a long percentage label. They remain in a
// labelled test fixture and are never written to docs/ or presented as a run.
assert.equal(history.run.fixture, true, 'Synthetic fills must stay in fixture data');
const returns = [120, -18, 7, -2.5, 0.4, 23.25];
history.candidates.forEach((candidate, index) => {
  const value = returns[index % returns.length];
  candidate.forward_returns = {
    d1: value, d3: value, d5: value,
    from_open: { d1: value - 0.5, d3: value - 0.5, d5: value - 0.5 }
  };
});
const sources = { recorded, fixture, history };
const previousFiles = new Map();
if (baseline) {
  for (const name of ['index.html', 'stock.css']) {
    previousFiles.set('/' + name, execFileSync('git', ['show', `${baseline}:docs/${name}`],
      { cwd: REPO, encoding: 'utf8', maxBuffer: 4 * 1024 * 1024 }));
  }
  // Pin the reproduction's input too: tomorrow's real run must not alter
  // which historical failure this negative control is proving.
  sources.recorded = JSON.parse(execFileSync('git', ['show', `${baseline}:docs/data.json`],
    { cwd: REPO, encoding: 'utf8', maxBuffer: 4 * 1024 * 1024 }));
}
const types = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript',
  '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon' };
const server = createServer(async (request, response) => {
  try {
    const path = decodeURIComponent(new URL(request.url, 'http://layout.local').pathname);
    const match = path.match(/^\/(recorded|fixture|history)(\/.*)$/);
    if (!match) { response.writeHead(404).end(); return; }
    const [, source, relative] = match;
    if (relative === '/data.json') {
      response.writeHead(200, { 'content-type': types['.json'] }).end(JSON.stringify(sources[source]));
      return;
    }
    const name = relative === '/' ? '/index.html' : relative;
    const file = resolve(DOCS, '.' + name);
    if (!file.startsWith(DOCS + sep)) { response.writeHead(403).end(); return; }
    const body = previousFiles.has(name) ? previousFiles.get(name) : await readFile(file);
    response.writeHead(200, { 'content-type': types[extname(file)] || 'application/octet-stream' }).end(body);
  } catch { response.writeHead(404).end(); }
});

async function chromiumTool() {
  for (const root of ['', ...(process.env.NODE_PATH || '').split(':').filter(Boolean)]) {
    try {
      const module = await import(root ? pathToFileURL(join(root, 'playwright/index.js')).href : 'playwright');
      const chromium = module.chromium || module.default?.chromium;
      if (chromium) return chromium;
    } catch { /* Try another installed runtime location. */ }
  }
  throw new Error('Playwright Chromium is required; layout checks cannot be skipped.');
}

// Executed in the page. A <text> and all its <tspan> children form one label:
// comparing the parent with its own spans would manufacture overlap failures.
function inspectLayout({ enlarged }) {
  const issues = [];
  const tolerance = 1.5;
  const visible = node => !node.closest('[hidden]') && node.getClientRects().length > 0
    && getComputedStyle(node).visibility !== 'hidden' && getComputedStyle(node).display !== 'none';
  const bounds = node => {
    const r = node.getBoundingClientRect();
    return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height };
  };
  const contained = (inner, outer) => inner.left >= outer.left - tolerance
    && inner.right <= outer.right + tolerance && inner.top >= outer.top - tolerance
    && inner.bottom <= outer.bottom + tolerance;
  const hosts = [...document.querySelectorAll('.sc-chart, .signal-surface')].filter(visible);
  let labels = 0;
  for (const host of hosts) {
    const outer = bounds(host);
    const chart = host.id || 'signal-map';
    const texts = [...host.querySelectorAll('svg text')].filter(visible).map(node => ({
      node, box: bounds(node), label: node.textContent.trim().replace(/\s+/g, ' ')
    })).filter(item => item.label && item.box.width > 0 && item.box.height > 0);
    labels += texts.length;
    for (const { node, box, label } of texts) {
      if (!contained(box, outer)) issues.push({ kind: 'outside', chart, label, box, host: outer });
      // Check every span's own type size too, since shares can use a smaller
      // font than their parent. Screen CTM catches a fixed viewBox shrinking it.
      for (const part of [node, ...node.querySelectorAll('tspan')]) {
        const matrix = part.getScreenCTM();
        if (!matrix) continue;
        const scale = Math.hypot(matrix.a, matrix.b);
        const pixels = parseFloat(getComputedStyle(part).fontSize) * scale;
        const minimum = enlarged && host.matches('.sc-chart') ? 22 : 11;
        if (pixels < minimum - 0.15) {
          issues.push({ kind: 'small-type', chart, label, pixels, minimum });
          break;
        }
      }
    }
    for (let i = 0; i < texts.length; i++) {
      for (let j = i + 1; j < texts.length; j++) {
        const first = texts[i], second = texts[j];
        const width = Math.min(first.box.right, second.box.right) - Math.max(first.box.left, second.box.left);
        const height = Math.min(first.box.bottom, second.box.bottom) - Math.max(first.box.top, second.box.top);
        if (width > tolerance && height > tolerance) {
          issues.push({ kind: 'overlap', chart, labels: [first.label, second.label], width, height });
        }
      }
    }
  }
  const overflow = document.documentElement.scrollWidth - document.documentElement.clientWidth;
  if (overflow > 1) issues.push({ kind: 'page-overflow', pixels: overflow });
  // Wide table content is allowed inside its own scrolling region. The
  // region itself must fit the phone; hiding overflow on body is not a fix.
  for (const region of [...document.querySelectorAll('.sc-table-scroll')].filter(visible)) {
    const box = bounds(region);
    if (box.left < -tolerance || box.right > innerWidth + tolerance) {
      issues.push({ kind: 'scroll-region-outside', region: region.id, box });
    }
  }
  return { issues, labels, charts: hosts.filter(host => host.querySelector('svg text')).length };
}

const cases = baseline ? [{ source: 'recorded', width: 390, theme: 'dark', enlarged: false }]
  : [320, 375, 390, 430, 768, 1280].flatMap(width => Object.keys(sources).map(source =>
    ({ source, width, theme: 'dark', enlarged: false })))
    .concat(Object.keys(sources).map(source => ({ source, width: 390, theme: 'light', enlarged: false })))
    .concat([320, 390].flatMap(width => Object.keys(sources).map(source =>
      ({ source, width, theme: 'dark', enlarged: true }))));

let browser;
let listening = false;
const failures = [];
const pageErrors = [];
try {
  const chromium = await chromiumTool();
  browser = await chromium.launch({ headless: true });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  listening = true;
  const origin = `http://127.0.0.1:${server.address().port}`;
  const context = await browser.newContext({ viewport: { width: 390, height: 844 },
    isMobile: true, hasTouch: true, deviceScaleFactor: 2, reducedMotion: 'reduce' });
  await context.route('**/*', route => route.request().url().startsWith(origin + '/')
    ? route.continue() : route.fulfill({ status: 200, body: '' }));
  const page = await context.newPage();
  page.on('pageerror', error => pageErrors.push(error.message));
  for (const scenario of cases) {
    const { source, width, theme, enlarged } = scenario;
    const label = `${source}/${width}px/${theme}/${enlarged ? '200%' : '100%'}`;
    await page.setViewportSize({ width, height: 844 });
    await page.goto(`${origin}/${source}/#research-report`, { waitUntil: 'load' });
    await page.waitForFunction(() => document.querySelector('#snapshot-refresh').getAttribute('aria-disabled') === 'false');
    assert.equal(await page.locator('#run-strip').isVisible(), true, `${label}: snapshot must load`);
    assert.equal(await page.locator('.signal-card').count(), sources[source].candidates.length,
      `${label}: layout checks must preserve every candidate`);
    await page.locator(`.sc-theme-toggle [data-theme="${theme}"]`).click();
    await page.evaluate(async enlarged => {
      await document.fonts.ready;
      if (enlarged) document.documentElement.style.fontSize = '200%';
      window.dispatchEvent(new Event('resize'));
    }, enlarged);
    await page.waitForTimeout(300); // Wait for the page's 120ms resize debounce and paint.
    const result = await page.evaluate(inspectLayout, { enlarged });
    assert.ok(result.labels > 0 && result.charts > 0, `${label}: no visible chart labels were inspected`);
    if (result.issues.length) failures.push({ scenario: label, ...result });
    console.log(`${result.issues.length ? 'FAIL' : 'pass'} ${label}: ${result.charts} charts, ${result.labels} labels, ${result.issues.length} layout issues`);
    if (shots && width === 390 && theme === 'dark') {
      const targets = source === 'recorded' ? ['funnel-card']
        : source === 'fixture' ? ['funnel-card', 'scores-card', 'checks-card']
          : ['evidence-card', 'outcome-card'];
      for (const target of targets) {
        const section = page.locator('#' + target);
        if (await section.isVisible()) await section.screenshot({
          path: join(resolve(shots), `layout-${source}-${target}-${enlarged ? '200' : '100'}.png`)
        });
      }
    }
  }
  assert.deepEqual(pageErrors, [], 'The layout suite must not conceal page runtime errors');
  for (const failure of failures) {
    console.log(JSON.stringify({ scenario: failure.scenario, issues: failure.issues.slice(0, 8), total: failure.issues.length }));
  }
  if (expectFailure) {
    assert.ok(failures.some(failure => failure.issues.some(issue => issue.kind === 'outside' && issue.chart === 'funnel-chart')),
      'The baseline must reproduce painted funnel-label overflow; a launch error, small type, or unrelated failure is not proof');
    console.log(`Baseline ${baseline}: confirmed the old funnel paints text outside its chart.`);
  } else {
    assert.equal(failures.length, 0, `${failures.length} of ${cases.length} mobile layout scenarios failed`);
    console.log(`Mobile layout: ${cases.length} viewport/theme/text-size scenarios passed.`);
  }
} finally {
  await browser?.close();
  if (listening) {
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
  }
}
