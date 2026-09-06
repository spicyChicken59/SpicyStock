// Standalone design verification. The original dashboard suite stays unchanged.
// node tools/matrix_navigation_smoke.mjs [--shots <directory>]
// Uses the real page with the canonical, explicitly labelled test fixture.
import { createServer } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { dirname, extname, join, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const DOCS = join(REPO, 'docs');
const FIXTURE = JSON.parse(await readFile(join(REPO, 'tests/fixtures/data.json'), 'utf8'));
const args = process.argv.slice(2);
const SHOTS = args.includes('--shots') ? resolve(args[args.indexOf('--shots') + 1]) : null;
if (SHOTS) await mkdir(SHOTS, { recursive: true });
const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css',
  '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon' };
const server = createServer(async (request, response) => {
  try {
    const path = decodeURIComponent(new URL(request.url, 'http://fixture.local').pathname);
    if (path === '/data.json') {
      response.writeHead(200, { 'content-type': types['.json'] }).end(JSON.stringify(FIXTURE));
      return;
    }
    const file = resolve(DOCS, '.' + (path === '/' ? '/index.html' : path));
    if (!file.startsWith(DOCS + sep)) { response.writeHead(403).end(); return; }
    const body = await readFile(file);
    response.writeHead(200, { 'content-type': types[extname(file)] || 'application/octet-stream' }).end(body);
  } catch { response.writeHead(404).end('Not present in the design fixture'); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const base = `http://127.0.0.1:${server.address().port}`;
let browser;
const checks = [];
const errors = [];
const ok = (name, pass, detail = '') => checks.push({ name, pass: !!pass, detail });
try {
  browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1280, height: 1000 } });
  // No network, live quotes or third-party fonts are needed for this recipe.
  await context.route(/^https?:\/\/(?!127\.0\.0\.1)/, route => route.fulfill({ status: 200, body: '' }));
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => {
    if (message.type() !== 'error') return;
    // Missing committed charts are an explained, existing dashboard state.
    if (/\/charts\/[^/]+\.png$/.test(message.location()?.url || '')) return;
    errors.push(message.text());
  });
  async function open() {
    await page.goto(base, { waitUntil: 'load' });
    await page.waitForFunction(() => document.querySelector('#shortlist .pick'));
    await page.waitForFunction(() => [...document.querySelectorAll('#shortlist img.shot')]
      .every(image => image.complete));
  }
  const details = page.locator('#shortlist .pick').first().locator('.sc-details');
  const region = details.locator('.sc-table-scroll');
  const controls = details.locator('[data-sc-matrix-controls]');
  const button = name => controls.getByRole('button', { name, exact: true });
  async function openChecklist() {
    await details.locator('summary').click();
    await page.waitForFunction(() => {
      const scroll = document.querySelector('#shortlist .pick .sc-details .sc-table-scroll');
      const group = document.querySelector('#shortlist .pick [data-sc-matrix-controls]');
      return scroll && group && !group.hidden === (scroll.scrollWidth > scroll.clientWidth + 1);
    }, null, { timeout: 3000 });
  }
  for (const width of [390, 820, 1280]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const theme of ['light', 'dark']) {
      await open();
      await page.click(`.sc-theme-toggle button[data-theme="${theme}"]`);
      await openChecklist();
      const state = await details.evaluate(node => {
        const scroll = node.querySelector('.sc-table-scroll');
        const group = node.querySelector('[data-sc-matrix-controls]');
        return {
          overflow: scroll.scrollWidth > scroll.clientWidth + 1,
          visible: !group.hidden,
          buttons: [...group.querySelectorAll('button')].map(button => ({
            text: button.textContent, height: button.getBoundingClientRect().height,
            target: button.getAttribute('aria-controls') === scroll.id
          })),
          pageOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          native: node.querySelector('table').tagName === 'TABLE'
            && [...node.querySelectorAll('tbody th')].every(th => th.scope === 'row')
        };
      });
      ok(`criterion navigation fits ${width}px ${theme}`, state.native
        && state.visible === state.overflow && state.pageOverflow <= 1
        && state.buttons.map(button => button.text).join('|') === 'check|result|measured'
        && state.buttons.every(button => button.target && (!state.visible || button.height >= 44)), JSON.stringify(state));
      if (SHOTS) await details.screenshot({ path: join(SHOTS, `matrix-${width}-${theme}.png`) });
    }
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await open();
  await openChecklist();
  await details.locator('summary').click();
  await page.waitForFunction(() => document.querySelector('#shortlist .pick [data-sc-matrix-controls]').hidden);
  ok('closing a checklist hides its controls until reopened', (await controls.getAttribute('hidden')) !== null);
  await openChecklist();
  const rows = FIXTURE.candidates[0].lynch_detail;
  ok('all check labels, results and measured values match the source',
    JSON.stringify(await details.locator('tbody tr').evaluateAll(rows => rows.map(row => ({
      label: row.children[1].textContent, result: row.querySelector('.sc-signal__label').textContent,
      value: row.children[3].textContent
    })))) === JSON.stringify(rows.map(row => ({ label: row.label, result: row.pass ? 'pass' : 'fail', value: row.value }))));
  await button('measured').click();
  await page.waitForTimeout(350);
  const jumped = await region.evaluate(scroll => {
    const port = scroll.getBoundingClientRect();
    const identity = scroll.querySelector('tbody th').getBoundingClientRect();
    const measured = scroll.querySelector('thead th:last-child').getBoundingClientRect();
    return { left: scroll.scrollLeft, sticky: Math.abs(identity.left - port.left) < 2,
      measuredVisible: measured.right > identity.right && measured.left < port.right };
  });
  ok('Measured reveals evidence while the check code remains pinned', jumped.left > 0 && jumped.sticky && jumped.measuredVisible, JSON.stringify(jumped));
  await button('check').focus();
  await page.keyboard.press('Enter');
  await page.waitForTimeout(350);
  const keyState = await button('check').evaluate(button => ({ focused: document.activeElement === button,
    outline: parseFloat(getComputedStyle(button).outlineWidth), style: getComputedStyle(button).outlineStyle,
    left: document.getElementById(button.getAttribute('aria-controls')).scrollLeft }));
  ok('keyboard activation returns to the check with visible focus', keyState.focused && keyState.outline >= 2
    && keyState.style !== 'none' && keyState.left < jumped.left, JSON.stringify(keyState));
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await button('measured').click();
  const instant = await region.evaluate(scroll => ({ left: scroll.scrollLeft,
    codeRight: scroll.querySelector('thead th').getBoundingClientRect().right,
    measuredLeft: scroll.querySelector('thead th:last-child').getBoundingClientRect().left }));
  ok('reduced motion reaches the evidence without animation', instant.left > 0
    && Math.abs(instant.measuredLeft - instant.codeRight) < 2, JSON.stringify(instant));
  await page.emulateMedia({ reducedMotion: 'no-preference', forcedColors: 'active' });
  const forced = await button('check').evaluate(button => ({ border: getComputedStyle(button).borderStyle,
    color: getComputedStyle(button).color, background: getComputedStyle(button).backgroundColor }));
  ok('forced colors preserve a visible control boundary', forced.border !== 'none' && forced.color !== forced.background, JSON.stringify(forced));
  await page.emulateMedia({ forcedColors: 'none' });
  await page.click('#basis-tabs [data-basis="open"]');
  await openChecklist();
  ok('return-basis rerender attaches one controller per new checklist',
    (await page.locator('#shortlist [data-sc-matrix-controls]').count()) === FIXTURE.run.shortlist_size
    && (await controls.getByRole('button').count()) === 3);
  const second = page.locator('#shortlist .pick').nth(1).locator('.sc-details');
  await second.locator('summary').click();
  await button('measured').click();
  await page.waitForTimeout(350);
  ok('each navigator scrolls only its own candidate checklist',
    (await region.evaluate(scroll => scroll.scrollLeft)) > 0
    && (await second.locator('.sc-table-scroll').evaluate(scroll => scroll.scrollLeft)) === 0);
  // Keep the original chart core while omitting the optional presentation
  // bundle. The marker is authored by the design-system bundle generator.
  const bundle = await readFile(join(DOCS, 'design-system/sc-charts.js'), 'utf8');
  const marker = '/* Optional signal-matrix criterion navigation */';
  if (!bundle.includes(marker)) throw new Error('Missing documented optional bundle boundary');
  const core = bundle.slice(0, bundle.indexOf(marker));
  await page.route('**/design-system/sc-charts.js', route => route.fulfill({ status: 200, contentType: 'text/javascript', body: core }));
  await open();
  await details.locator('summary').click();
  await region.focus();
  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(200);
  ok('without the optional navigator the native checklist remains keyboard scrollable',
    (await controls.count()) === 0 && (await region.evaluate(scroll => scroll.scrollLeft)) > 0
    && (await details.locator('tbody tr').count()) === rows.length);
} finally {
  if (browser) await browser.close();
  await new Promise(resolve => server.close(resolve));
}
for (const check of checks) console.log(`${check.pass ? 'ok' : 'FAIL'} ${check.name}${check.detail ? ' — ' + check.detail : ''}`);
for (const error of errors) console.error(error);
const failed = checks.filter(check => !check.pass).length;
console.log(`matrix navigation: ${checks.length - failed}/${checks.length} checks, ${errors.length} page errors`);
if (checks.length !== 15 || failed || errors.length) process.exitCode = 1;
