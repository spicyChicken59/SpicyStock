// Standalone design review of the real page and its recorded run.
// node tools/instrument_deck_smoke.mjs [--shots <directory>]
// No market calls, application edits, or alterations to the original smoke suite.
import { createServer } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { dirname, extname, join, resolve, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const DOCS = join(REPO, 'docs');
const RECORDED = JSON.parse(await readFile(join(DOCS, 'data.json'), 'utf8'));
const FIXTURE = JSON.parse(await readFile(join(REPO, 'tests/fixtures/data.json'), 'utf8'));
const args = process.argv.slice(2);
const SHOTS = args.includes('--shots') ? resolve(args[args.indexOf('--shots') + 1]) : null;
if (SHOTS) await mkdir(SHOTS, { recursive: true });
async function loadChromium() {
  const paths = [...(process.env.NODE_PATH || '').split(':'),
    resolve(dirname(process.execPath), '..', 'lib', 'node_modules')].filter(Boolean);
  for (const get of [() => import('playwright'), ...paths.map(root =>
    () => import(pathToFileURL(join(root, 'playwright/index.js')).href))]) {
    try { const p = await get(); if (p.chromium || p.default?.chromium) return p.chromium || p.default.chromium; }
    catch { /* Try the next installed runtime location. */ }
  }
  throw new Error('Playwright Chromium is required for the instrument design review.');
}
const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css',
  '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon' };
const server = createServer(async (request, response) => {
  try {
    let path = decodeURIComponent(new URL(request.url, 'http://design.local').pathname);
    const fixture = path.startsWith('/fixture/');
    if (fixture) path = path.slice('/fixture'.length);
    if (path === '/data.json') {
      response.writeHead(200, { 'content-type': types['.json'] })
        .end(JSON.stringify(fixture ? FIXTURE : RECORDED));
      return;
    }
    const file = resolve(DOCS, '.' + (path === '/' ? '/index.html' : path));
    if (!file.startsWith(DOCS + sep)) { response.writeHead(403).end(); return; }
    const body = await readFile(file);
    response.writeHead(200, { 'content-type': types[extname(file)] || 'application/octet-stream' }).end(body);
  } catch { response.writeHead(404).end('No committed design asset at this path'); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const base = `http://127.0.0.1:${server.address().port}`;
const checks = [];
const errors = [];
const ok = (name, pass, detail = '') => checks.push({ name, pass: !!pass, detail });
let browser;
try {
  browser = await (await loadChromium()).launch();
  const context = await browser.newContext({ viewport: { width: 1280, height: 1000 } });
  await context.route(/^https?:\/\/(?!127\.0\.0\.1)/,
    route => route.fulfill({ status: 200, body: '' }));
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  async function open(path = '/') {
    await page.goto(base + path, { waitUntil: 'load' });
    await page.waitForFunction(() => !document.querySelector('#run-strip').hidden);
    await page.emulateMedia({ reducedMotion: 'reduce' });
  }
  async function facts() {
    return page.locator('#run-strip').evaluate(node => ({ tag: node.tagName,
      name: node.getAttribute('aria-label'),
      values: [...node.querySelectorAll('.sc-stat__value')].map(n => n.textContent),
      labels: [...node.querySelectorAll('dt')].map(n => n.textContent),
      notes: [...node.querySelectorAll('.sc-stat__note')].map(n => n.textContent),
      controls: node.querySelectorAll('button,a,input,[tabindex]').length }));
  }
  await page.route('**/stock-studio.css', route => route.fulfill({ contentType: 'text/css', body: '' }));
  await open();
  const originalFacts = await facts();
  const originalEmpty = await page.locator('#evidence-empty').textContent();
  await page.unroute('**/stock-studio.css');
  for (const width of [390, 820, 1280]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const theme of ['light', 'dark']) {
      await open();
      await page.click(`.sc-theme-toggle button[data-theme="${theme}"]`);
      const currentFacts = await facts();
      const layout = await page.locator('#run-strip').evaluate(strip => {
        const stats = [...strip.querySelectorAll('.sc-stat')];
        const bounds = strip.getBoundingClientRect();
        const rects = stats.map(n => n.getBoundingClientRect());
        const rgb = value => (value.match(/[\d.]+/g) || []).slice(0, 3).map(Number);
        const luminance = color => rgb(color).map(v => {
          const n = v / 255; return n <= .04045 ? n / 12.92 : ((n + .055) / 1.055) ** 2.4;
        }).reduce((sum, n, i) => sum + n * [.2126, .7152, .0722][i], 0);
        const contrast = (a, b) => {
          const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
          return (hi + .05) / (lo + .05);
        };
        return {
          overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          contained: rects.every(r => r.left >= bounds.left && r.right <= bounds.right + 1),
          separated: rects.every((r, i) => !i || r.top > rects[i - 1].top || r.left >= rects[i - 1].right - 1),
          columns: new Set(rects.map(r => Math.round(r.left))).size,
          minContrast: Math.min(...stats.flatMap(stat => {
            const bg = getComputedStyle(stat).backgroundColor;
            const background = bg === 'rgba(0, 0, 0, 0)' ? getComputedStyle(strip).backgroundColor : bg;
            return [...stat.querySelectorAll('dt,dd')].map(n => contrast(getComputedStyle(n).color, background));
          })),
          stationCount: stats.filter(n => !['none', 'normal'].includes(getComputedStyle(n, '::after').content)).length,
          connectedPairs: stats.filter(n => !['none', 'normal'].includes(getComputedStyle(n, '::before').content)).length,
          labelFont: getComputedStyle(stats[0].querySelector('dt')).fontSize,
          moving: stats.some(n => ['::before', '::after'].some(p => getComputedStyle(n, p).animationName !== 'none'))
        };
      });
      ok(`recorded counts and native labels preserved ${width}px ${theme}`,
        JSON.stringify(currentFacts) === JSON.stringify(originalFacts)
        && currentFacts.tag === 'DL' && currentFacts.controls === 0);
      ok(`instrument deck readable and contained ${width}px ${theme}`,
        layout.overflow <= 1 && layout.contained && layout.separated && layout.minContrast >= 4.5
        && layout.stationCount === 4 && layout.connectedPairs === (layout.columns === 4 ? 3 : 2)
        && !layout.moving, JSON.stringify(layout));
      if (SHOTS) {
        await page.locator('#run-strip').screenshot({ path: join(SHOTS, `instrument-${width}-${theme}.png`) });
      }
    }
  }
  ok('empty outcome explanation is unchanged', await page.locator('#evidence-empty').textContent() === originalEmpty);
  await page.setViewportSize({ width: 320, height: 844 });
  await open();
  ok('narrow phone retains all four factual stations', await page.evaluate(() =>
    document.documentElement.scrollWidth <= innerWidth + 1
    && [...document.querySelectorAll('#run-strip .sc-stat__value')].every(n => {
      const r = n.getBoundingClientRect(); return r.width > 0 && r.left >= 0 && r.right <= innerWidth;
    })));
  await page.locator('.sc-theme-toggle [data-theme="light"]').focus();
  await page.keyboard.press('Enter');
  ok('keyboard theme control remains visible and operable', await page.evaluate(() => {
    const n = document.activeElement, s = getComputedStyle(n);
    return n.matches('.sc-theme-toggle [data-theme="light"]')
      && document.documentElement.dataset.theme === 'light'
      && parseFloat(s.outlineWidth) >= 2 && s.outlineStyle !== 'none';
  }));
  await page.emulateMedia({ forcedColors: 'active' });
  ok('forced colors preserve the station boundaries and facts', await page.locator('#run-strip').evaluate(n => {
    const s = getComputedStyle(n); return s.borderTopStyle !== 'none'
      && [...n.querySelectorAll('.sc-stat__value')].every(v => getComputedStyle(v).color !== s.backgroundColor);
  }));
  await page.emulateMedia({ forcedColors: 'none', media: 'print' });
  ok('print retains a legible, stationary complete deck', await page.locator('#run-strip').evaluate(n => {
    const s = getComputedStyle(n); return s.display === 'grid' && s.breakInside === 'avoid'
      && [...n.querySelectorAll('.sc-stat__value')].every(v => getComputedStyle(v).fontSize === '28px');
  }));
  await page.emulateMedia({ media: 'screen', reducedMotion: 'no-preference' });
  await open('/fixture/');
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  const fixtureFacts = await facts();
  const comma = n => n.toLocaleString('en-US');
  ok('populated fixture uses the same layout without replacing recorded data',
    fixtureFacts.values.join('|') === [FIXTURE.run.universe.size, FIXTURE.run.bursts,
      FIXTURE.run.scored, FIXTURE.run.shortlist_size].map(comma).join('|')
    && await page.locator('#fixture-banner').isVisible());
  ok('station routes never imply live activity through animation', await page.locator('#run-strip').evaluate(n =>
    [...n.querySelectorAll('.sc-stat')].every(stat => ['::before', '::after'].every(pseudo =>
      getComputedStyle(stat, pseudo).animationName === 'none'))));
  ok('no application exceptions', errors.length === 0, errors.join('\n'));
} finally {
  if (browser) await browser.close();
  await new Promise(resolve => server.close(resolve));
}
for (const check of checks) console.log(`${check.pass ? 'PASS' : 'FAIL'} ${check.name}${check.pass || !check.detail ? '' : '\n' + check.detail}`);
const failures = checks.filter(check => !check.pass);
console.log(`${checks.length - failures.length}/${checks.length} instrument design checks passed`);
if (failures.length) process.exitCode = 1;
