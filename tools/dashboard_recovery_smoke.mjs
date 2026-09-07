// Recovery contracts for the actual dashboard. All responses are local fixtures;
// a hung body, rejected refresh and a late ledger response are exercised in-browser.
// node tools/dashboard_recovery_smoke.mjs [--shots <directory>]
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { dirname, extname, join, resolve, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
const REPO = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const ROOT = join(REPO, 'docs');
const fixture = JSON.parse(await readFile(join(REPO, 'tests/fixtures/data.json'), 'utf8'));
const ledger = JSON.parse(await readFile(join(REPO, 'tests/fixtures/history/ledger.json'), 'utf8'));
const args = process.argv.slice(2);
const shots = args.includes('--shots') ? resolve(args[args.indexOf('--shots') + 1]) : null;
if (shots) await mkdir(shots, { recursive: true });
let chromium;
for (const root of ['', ...(process.env.NODE_PATH || '').split(':')]) {
  try { const module = await import(root ? pathToFileURL(join(root, 'playwright/index.js')).href : 'playwright'); chromium = module.chromium || module.default?.chromium; if (chromium) break; } catch {}
}
assert.ok(chromium, 'Playwright is required; recovery cannot pass without opening the dashboard.');
const types = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon' };
let dataMode = 'ok', ledgerMode = 'ok', data = fixture, ledgerRequests = 0;
const held = [];
const server = createServer(async (request, response) => {
  const path = new URL(request.url, 'http://local').pathname;
  if (path === '/data.json' || path === '/ledger.json') {
    const isLedger = path === '/ledger.json';
    if (isLedger) ledgerRequests++;
    const mode = isLedger ? ledgerMode : dataMode;
    if (mode === 'failed') { response.writeHead(503).end('Temporary failure'); return; }
    if (mode === 'held') { held.push(response); return; }
    if (mode === 'body-stall') { response.writeHead(200, { 'content-type': 'application/json' }); response.write('{'); held.push(response); return; }
    response.writeHead(200, { 'content-type': 'application/json' }).end(JSON.stringify(isLedger ? ledger : data)); return;
  }
  try {
    const file = resolve(ROOT, '.' + (path === '/' ? '/index.html' : path));
    if (!file.startsWith(ROOT + sep)) { response.writeHead(403).end(); return; }
    const body = await readFile(file);
    response.writeHead(200, { 'content-type': types[extname(file)] || 'application/octet-stream' }).end(body);
  } catch { response.writeHead(404).end(); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
let browser;
const checks = [];
const check = (name, condition) => { assert.ok(condition, name); checks.push(name); console.log('pass  ' + name); };
try {
  browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1280, height: 1000 }, reducedMotion: 'reduce' });
  await context.route(/^https?:\/\/(?!127\.0\.0\.1)/, route => route.fulfill({ status: 200, body: '' }));
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const open = async () => page.goto(`http://127.0.0.1:${server.address().port}/`, { waitUntil: 'load' });
  const ready = async () => page.waitForFunction(() => !document.querySelector('#run-strip').hidden && !document.querySelector('#snapshot-refresh').disabled);
  const status = () => page.locator('#snapshot-status').innerText();
  dataMode = 'failed';
  await open();
  await page.waitForFunction(() => document.querySelector('#h1').textContent === 'Snapshot unavailable');
  check('initial HTTP failure leaves a usable retry action', await page.getByRole('button', { name: 'Retry snapshot' }).count() === 1);
  dataMode = 'ok';
  await page.getByRole('button', { name: 'Retry snapshot' }).click();
  await ready();
  check('retry renders the real snapshot instead of requiring a reload', (await page.locator('#h1').innerText()).includes('25 scored'));
  check('session date and check time are separate facts', /recorded session 1 Sep 2026/i.test(await status()) && /Checked/.test(await status()));
  check('loading the page does not fetch the full ledger', ledgerRequests === 0);

  const before = await page.locator('#h1').innerText();
  dataMode = 'failed';
  await page.getByRole('button', { name: 'Check for updates' }).click();
  await page.waitForFunction(() => document.querySelector('#snapshot-status').textContent.includes('Update check failed'));
  check('failed refresh retains the previously loaded report and identifies it', before === await page.locator('#h1').innerText() && /Still showing recorded session/.test(await status()));
  check('failed refresh does not relabel retained data as unavailable', !await page.locator('#run-strip').isHidden() && !await page.locator('#snapshot-refresh').isDisabled());
  dataMode = 'ok';
  await page.locator('#snapshot-refresh').click();
  await ready();
  await page.getByRole('button', { name: "from the next session's open", exact: true }).click();
  await page.locator('.pick details').first().evaluate(node => node.open = true);
  await page.locator('.pick').first().evaluate(node => node.dataset.recoveryIdentity = 'keep');
  await page.locator('#snapshot-refresh').click();
  await ready();
  check('unchanged refresh preserves the selected basis and open details', await page.getByRole('button', { name: "from the next session's open", exact: true }).getAttribute('aria-pressed') === 'true' && await page.locator('.pick details').first().evaluate(node => node.open));
  check('unchanged refresh keeps the current report nodes', await page.locator('.pick').first().getAttribute('data-recovery-identity') === 'keep');

  ledgerMode = 'failed';
  await page.getByRole('button', { name: 'Load every burst of every name' }).click();
  await page.waitForFunction(() => document.querySelector('#ticker-more').textContent.includes('could not be loaded'));
  check('a failed full-record request can be retried', await page.getByRole('button', { name: 'Retry full record' }).count() === 1);
  ledgerMode = 'ok';
  await page.getByRole('button', { name: 'Retry full record' }).click();
  await page.waitForFunction(() => document.querySelector('#ticker-more').textContent.includes('Showing all'));
  check('full-record retry restores detail without discarding the summary', (await page.locator('#ticker-table tbody tr').count()) > 15);

  ledgerMode = 'held';
  await open(); await ready();
  await page.getByRole('button', { name: 'Load every burst of every name' }).click();
  data = structuredClone(fixture); data.generated = '2026-09-08T22:20:00Z';
  await page.locator('#snapshot-refresh').click(); await ready();
  for (const response of held.splice(0)) response.end(JSON.stringify(ledger));
  await page.waitForTimeout(100);
  check('a late ledger response cannot attach to a newer snapshot', await page.getByRole('button', { name: 'Load every burst of every name' }).count() === 1 && (await page.locator('#ticker-table tbody tr').count()) === 15);
  ledgerMode = 'ok';

  data = { run: null };
  await page.locator('#snapshot-refresh').click();
  await page.waitForFunction(() => document.querySelector('#snapshot-status').textContent.includes('Update check failed'));
  check('malformed refresh cannot replace recorded counts with a fabricated zero run', before === await page.locator('#h1').innerText() && /snapshot has no recorded run/i.test(await status()));
  data = { run: {} };
  await page.locator('#snapshot-refresh').click();
  await page.waitForFunction(() => document.querySelector('#snapshot-status').textContent.includes('no valid recorded session date'));
  check('an empty run block is not interpreted as a quiet market', before === await page.locator('#h1').innerText());
  data = structuredClone(fixture); data.run.scored = null;
  await page.locator('#snapshot-refresh').click();
  await page.waitForFunction(() => document.querySelector('#snapshot-status').textContent.includes('invalid scored count'));
  check('a missing count is not silently shown as zero', before === await page.locator('#h1').innerText());
  data = structuredClone(fixture); data.candidates = [null];
  await page.locator('#snapshot-refresh').click();
  await page.waitForFunction(() => document.querySelector('#snapshot-status').textContent.includes('Update check failed'));
  check('a render failure restores the last complete report', before === await page.locator('#h1').innerText() && (await page.locator('#scores-table tbody tr').count()) === 25);
  await open();
  await page.waitForFunction(() => document.querySelector('#h1').textContent === 'Snapshot unavailable');
  check('an initial render failure cannot leave partial counts or results visible', await page.locator('#run-strip').isHidden() && await page.locator('#scores-card').isHidden() && await page.locator('#page-index').isHidden());
  data = fixture;

  dataMode = 'body-stall';
  await open();
  await page.waitForFunction(() => document.querySelector('#h1').textContent === 'Snapshot unavailable', null, { timeout: 18000 });
  check('a stalled JSON body times out and leaves retry available', /timed out after 15 seconds/.test(await status()) && !await page.locator('#snapshot-refresh').isDisabled());
  dataMode = 'ok';
  await page.locator('#snapshot-refresh').click(); await ready();
  check('a timeout does not poison the next successful request', before === await page.locator('#h1').innerText());

  for (const width of [390, 820, 1280]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const theme of ['light', 'dark']) {
      await page.locator('.sc-theme-toggle button[data-theme="' + theme + '"]').click();
      const box = await page.locator('#snapshot-panel').evaluate(node => ({ width: node.getBoundingClientRect().width, overflow: document.documentElement.scrollWidth > innerWidth + 1 }));
      check(`${width}px ${theme}: snapshot controls stay within the page`, box.width > 0 && !box.overflow);
    }
    if (shots) await page.screenshot({ path: join(shots, `recovery-${width}.png`), fullPage: false });
  }
  await page.keyboard.press('Tab');
  await page.locator('#snapshot-refresh').focus();
  check('refresh has a visible keyboard focus indicator', await page.locator('#snapshot-refresh').evaluate(node => document.activeElement === node && getComputedStyle(node).outlineStyle !== 'none'));
  check('snapshot status is announced without moving keyboard focus', await page.locator('#snapshot-status').getAttribute('role') === 'status');
  check('recovery scenarios produce no page errors', errors.length === 0);
  console.log(`${checks.length} dashboard recovery checks passed.`);
} finally {
  for (const response of held) response.destroy();
  await browser?.close();
  server.closeAllConnections();
  await new Promise(resolve => server.close(resolve));
}
