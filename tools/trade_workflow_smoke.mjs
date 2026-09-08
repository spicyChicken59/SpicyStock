// Offline browser checks for plans, confirmed executions and broker receipts.
// Only this checkout and same-origin route doubles are reachable; no account,
// broker order, quote service or credential is used by this test.
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { mkdir, readFile } from 'node:fs/promises';
import { dirname, extname, join, resolve, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const repo = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const docs = join(repo, 'docs');
const data = JSON.parse(await readFile(join(repo, 'tests/fixtures/data.json'), 'utf8'));
assert.equal(data.run.fixture, true);
const args = process.argv.slice(2), shotIndex = args.indexOf('--shots');
const shots = shotIndex < 0 ? null : resolve(args[shotIndex + 1]);
if (shots) await mkdir(shots, { recursive: true });
const types = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript',
  '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon' };
const server = createServer(async (request, response) => {
  try {
    const pathname = decodeURIComponent(new URL(request.url, 'http://trade.local').pathname);
    const path = resolve(docs, '.' + (pathname === '/' ? '/index.html' : pathname));
    if (!path.startsWith(docs + sep)) { response.writeHead(403).end(); return; }
    const body = await readFile(path);
    response.writeHead(200, { 'content-type': types[extname(path)] || 'application/octet-stream' }).end(body);
  } catch { response.writeHead(404).end(); }
});
async function chromiumTool() {
  for (const root of ['', ...(process.env.NODE_PATH || '').split(':').filter(Boolean)]) {
    try {
      const module = await import(root ? pathToFileURL(join(root, 'playwright/index.js')).href : 'playwright');
      if (module.chromium || module.default?.chromium) return module.chromium || module.default.chromium;
    } catch { /* Try another installed runtime location. */ }
  }
  throw new Error('Playwright Chromium is required; trade workflow checks cannot be skipped.');
}
const errors = [];
let checks = 0, browser;
const pass = name => { checks++; console.log('PASS ' + name); };
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const origin = `http://127.0.0.1:${server.address().port}`;

async function screenshot(page, selector, name) {
  if (!shots) return;
  await page.locator(selector).evaluate(node => node.scrollIntoView({ block: 'start', behavior: 'auto' }));
  await page.screenshot({ path: join(shots, name + '.png') });
}

try {
  browser = await (await chromiumTool()).launch();
  async function open(mode = 'manual') {
    const context = await browser.newContext({ viewport: { width: 390, height: 900 }, reducedMotion: 'reduce', timezoneId: 'UTC' });
    const page = await context.newPage();
    page.setDefaultTimeout(5000);
    page.on('pageerror', error => errors.push(error.message));
    const state = { mode, api: [], orders: [], previews: [], receipt: null, unexpected: [] };
    const account = { id: 'ci-paper-account', label: 'CI paper account', cash: 10000, equity: 10000, buying_power: 10000, currency: 'USD', trading_blocked: false };
    await context.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url());
      const json = value => route.fulfill({ contentType: 'application/json', body: JSON.stringify(value) });
      if (url.origin !== origin) { await route.fulfill({ status: 200, body: '' }); return; }
      if (url.pathname === '/data.json') { await json(data); return; }
      if (url.pathname === '/trading-config.json') {
        await json({ version: 1, enabled: mode !== 'manual', api_base: mode === 'manual' ? null : '/api', broker: 'alpaca' }); return;
      }
      if (url.pathname.startsWith('/api/')) {
        state.api.push({ method: request.method(), path: url.pathname });
        const now = new Date().toISOString();
        if (url.pathname === '/api/status') {
          await json({ version: 1, configured: true, connected: true,
            state: state.receipt?.state === 'reconciliation_needed' ? 'reconciliation_needed' : 'paper',
            mode: 'paper', live_enabled: false, csrf_token: 'ci-csrf-token',
            limits: { max_risk_percent: 2, max_position_percent: 100, max_notional: 10000 } }); return;
        }
        if (url.pathname === '/api/portfolio') {
          await json({ state: 'paper', mode: 'paper', as_of: now, account,
            clock: { timestamp: now, is_open: true, next_open: now, next_close: now },
            positions: [], pending_orders: state.receipt?.order ? [state.receipt.order] : [],
            fills: [], fills_truncated: false, fills_complete_since: null, unresolved: [] }); return;
        }
        if (url.pathname === '/api/quote') {
          await json({ symbol: url.searchParams.get('symbol') || 'TESTBEE', bid: 19.99, ask: 20,
            timestamp: now, feed: 'iex', age_seconds: 0, fresh: true }); return;
        }
        if (url.pathname === '/api/preview' && request.method() === 'POST') {
          const payload = request.postDataJSON(); state.previews.push(payload);
          await json({ preview_id: 'ci-preview-' + state.previews.length,
            expires_at: new Date(Date.now() + 120000).toISOString(),
            account_label: account.label, account_id: account.id, mode: 'paper',
            symbol: payload.symbol || 'TESTBEE', qty: 30, limit_price: 20, stop_price: 18,
            risk_percent: 1, risk_dollars: 60, risk_budget: 100, position_dollars: 600, cash_cap: 600,
            source_session: data.run.date, source_sha256: 'f'.repeat(64),
            quote: { symbol: payload.symbol || 'TESTBEE', bid: 19.99, ask: 20, timestamp: now, feed: 'iex', age_seconds: 0, fresh: true },
            order_type: 'limit + protective stop', time_in_force: 'gtc',
            protection_note: 'Synthetic CI preview; no order reaches a broker.' }); return;
        }
        if (url.pathname === '/api/orders' && request.method() === 'POST') {
          const payload = request.postDataJSON(); state.orders.push(payload);
          const order = { id: 'ci-order-1', client_order_id: 'ci-client-1', symbol: 'TESTBEE',
            status: 'accepted', side: 'buy', qty: 30, filled_qty: 0, limit_price: 20,
            type: 'limit', order_class: 'oto', time_in_force: 'gtc', legs: [] };
          state.receipt = { state: mode === 'unknown' ? 'reconciliation_needed' : 'accepted',
            preview_id: payload.preview_id, client_order_id: 'ci-client-1',
            order: mode === 'unknown' ? null : order,
            message: mode === 'unknown' ? 'Submission outcome unknown. Reconcile before another submission.' : 'Broker accepted the order. No execution is confirmed.' };
          if (mode === 'unknown') { await route.abort('failed'); return; }
          await json(state.receipt); return;
        }
        state.unexpected.push(request.method() + ' ' + url.pathname);
        await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ error: { code: 'unexpected_ci_request', message: 'Unexpected bridge request in CI.' } }) }); return;
      }
      await route.continue();
    });
    await page.goto(origin, { waitUntil: 'load' });
    await page.locator('#trade-workspace').waitFor({ state: 'visible' });
    return { page, context, state };
  }
  const records = page => page.evaluate(() => window.SCTradeState.getState());
  const holdings = page => page.evaluate(() => window.SCTradeState.derive());
  async function setProfile(page, throughAccount = false) {
    if (throughAccount) {
      await page.locator('.tw-account summary').filter({ hasText: 'Limits & connection' }).click();
      await page.locator('#trade-account-profile').click();
    } else await page.locator('#trade-next-action').click();
    for (const [id, value] of [['trade-capital', '10000'], ['trade-risk', '1'], ['trade-cash-cap', '600'], ['trade-max-positions', '4']]) {
      await page.locator('#' + id).fill(value);
    }
    await page.locator('#trade-save-profile').click();
    assert.deepEqual((await records(page)).profile, { capital: 10000, risk_percent: 1, cash_cap: 600, max_positions: 4 });
  }
  async function fillPlan(page) {
    await page.locator('#trade-plan-manual').click();
    await page.locator('#trade-symbol').fill('TESTBEE');
    await page.locator('#trade-entry').fill('20');
    await page.locator('#trade-stop').fill('18');
    await page.locator('#trade-plan-qty').waitFor();
    assert.equal(await page.locator('#trade-plan-qty').textContent(), '30 shares');
  }
  async function prepareFill(page, side, qty, price, execution, timestamp) {
    await page.locator('#trade-tab-positions').click();
    await page.locator('#trade-record-fill').click();
    await page.locator('#trade-fill-symbol').fill('TESTBEE');
    await page.locator('#trade-fill-side').selectOption(side);
    await page.locator('#trade-fill-qty').fill(String(qty));
    await page.locator('#trade-fill-price').fill(String(price));
    await page.locator('#trade-fill-time').fill(timestamp);
    await page.locator('#trade-fill-fees').fill('0');
    if (side === 'buy') await page.locator('#trade-fill-stop').fill('18');
    await page.locator('#trade-fill-environment').selectOption('paper');
    await page.locator('#trade-fill-execution').fill(execution);
  }
  const manual = await open(), page = manual.page;
  assert.equal(await page.locator('#research-report').getAttribute('open'), null, 'The detailed report starts collapsed.');
  assert.equal(await page.locator('#trade-account-status').textContent(), 'Not connected');
  assert.equal((await records(page)).fills.length, 0);
  assert.equal((await holdings(page)).positions.length, 0);
  await page.locator('#trade-tab-positions').click();
  await setProfile(page);
  assert.equal(await page.locator('#trade-tab-today').getAttribute('aria-selected'), 'true',
    'Setting limits from the Positions hero must return to the Today profile form.');
  assert.equal((await records(page)).fills.length, 0, 'Saving limits cannot create an execution.');
  assert.equal(manual.state.api.length, 0, 'Manual mode must not reach broker endpoints.');
  pass('the daily desk opens with a collapsed report and private manual limits without a broker connection');

  await fillPlan(page);
  assert.match(await page.locator('#trade-calculation').textContent(), /\$60\.00.*\$600\.00/);
  await page.locator('#trade-stop').fill('20');
  assert.equal(await page.locator('#trade-save-plan').isDisabled(), true);
  assert.equal(await page.locator('#trade-plan-qty').count(), 0);
  await page.locator('#trade-stop').fill('18');
  await page.locator('#trade-save-plan').click();
  let book = await records(page);
  assert.equal(book.plans.length, 1);
  assert.equal(book.plans[0].qty, 30);
  assert.equal(book.plans[0].status, 'prepared');
  assert.equal(book.fills.length, 0);
  assert.equal((await holdings(page)).positions.length, 0);
  await screenshot(page, '#trade-plan-title', 'trade-plan-phone');
  pass('risk and cash limits size a saved plan while invalid stops are blocked and no holding is invented');

  await prepareFill(page, 'buy', 10, 20, 'ci-manual-buy', '2026-08-31T14:00');
  assert.equal((await records(page)).fills.length, 0);
  assert.equal(await page.locator('#trade-fill-confirm').isChecked(), false);
  await page.locator('#trade-fill-confirm').check();
  await page.locator('#trade-save-fill').click();
  book = await records(page);
  let view = await holdings(page);
  assert.equal(book.fills.length, 1);
  assert.equal(book.fills[0].execution_id, 'ci-manual-buy');
  assert.equal(book.fills[0].qty, 10, 'Actual shares come from the confirmed fill, not the 30-share plan.');
  assert.equal(view.positions.length, 1);
  assert.equal(view.positions[0].qty, 10);
  assert.equal(view.positions[0].cost_basis, 200);
  assert.equal(view.positions[0].initial_risk, 20);
  assert.match(await page.locator('[data-trade-position="TESTBEE"]').textContent(), /Recorded shares10.*Average entry\$20\.00/);
  await prepareFill(page, 'sell', 4, 24, 'ci-manual-sell', '2026-09-01T14:00');
  await page.locator('#trade-fill-confirm').check();
  await page.locator('#trade-save-fill').click();
  view = await holdings(page);
  assert.equal(view.positions[0].qty, 6);
  assert.equal(view.closed.length, 1);
  assert.equal(view.closed[0].profit, 16);
  assert.equal(view.closed[0].r, 2);
  assert.equal(view.totals.live.open_positions, 0, 'Paper fills cannot become live positions.');
  assert.match(await page.locator('[data-trade-position="TESTBEE"]').textContent(), /Recorded shares6/);
  await page.locator('#trade-tab-activity').click();
  assert.equal(await page.locator('[data-trade-execution]').count(), 2);
  assert.match(await page.locator('#trade-closed-exits').textContent(), /TESTBEE.*\$16\.00 gross.*2\.00R on original risk/);
  await screenshot(page, '#trade-panel', 'trade-activity-phone');
  pass('confirmed buys and partial sells create actual positions and realized results independently of the plan');

  // Existing export rows give the preview real execution identities to dedupe.
  const originalCSV = await page.evaluate(() => window.SCTradeState.exportCSV());
  const existingFill = (await records(page)).fills[0];
  const extraCSV = ['ci-import-buy', 'TESTBEE', 'buy', '2', '21', '2026-09-01T15:00:00Z', '0', '18', 'manual', 'paper', existingFill.account_id, '', ''].join(',');
  const csv = originalCSV + extraCSV + '\r\n';
  await page.locator('#trade-tab-positions').click();
  await page.locator('#trade-import-open').click();
  await page.locator('#trade-import-file').setInputFiles({ name: 'ci-confirmed-fills.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) });
  await page.locator('#trade-import-confirm').waitFor({ state: 'visible' });
  assert.equal((await records(page)).fills.length, 2, 'Reading a CSV is a preview, not an import.');
  assert.match(await page.locator('#trade-import-preview').textContent(), /1 new fills.*2 duplicate executions skipped/);
  await page.locator('#trade-import-confirm').click();
  assert.equal((await records(page)).fills.length, 3);
  assert.equal((await holdings(page)).positions[0].qty, 8);
  await page.locator('#trade-import-open').click();
  await page.locator('#trade-import-file').setInputFiles({ name: 'ci-confirmed-fills-again.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) });
  await page.locator('#trade-import-confirm').waitFor({ state: 'visible' });
  assert.match(await page.locator('#trade-import-preview').textContent(), /3.*duplicate|duplicate.*3/i);
  const confirmImport = page.locator('#trade-import-confirm');
  if (await confirmImport.isEnabled()) await confirmImport.click();
  assert.equal((await records(page)).fills.length, 3, 'Reimporting executions must not duplicate them.');
  await page.reload({ waitUntil: 'load' });
  assert.equal((await records(page)).fills.length, 3);
  assert.equal((await records(page)).plans.length, 1);
  assert.equal((await holdings(page)).positions[0].qty, 8);
  assert.equal((await records(page)).profile.capital, 10000);
  pass('CSV previews require confirmation, repeated execution IDs dedupe and positions and limits survive reload');

  async function geometry(page) {
    const issues = await page.evaluate(() => {
      const problems = [], host = document.querySelector('#trade-workspace');
      const outer = host.getBoundingClientRect();
      if (document.documentElement.scrollWidth > innerWidth + 1) problems.push('page overflow');
      if (outer.left < -2 || outer.right > innerWidth + 2) problems.push('trading desk outside viewport');
      for (const control of host.querySelectorAll('button,input,select,textarea,summary,svg')) {
        if (!control.getClientRects().length || control.closest('[hidden]')) continue;
        const box = control.getBoundingClientRect();
        if (box.left < outer.left - 2 || box.right > outer.right + 2) problems.push((control.id || control.tagName) + ' outside desk');
        if (!control.matches('svg,input[type="checkbox"],input[type="file"]') && box.height < 43.5) problems.push((control.id || control.tagName) + ' below 44px touch height');
      }
      return problems;
    });
    assert.deepEqual(issues, [], 'The daily trading controls must fit the viewport with usable targets.');
  }
  for (const width of [320, 390, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    for (const theme of ['light', 'dark']) {
      await page.locator(`.sc-theme-toggle [data-theme="${theme}"]`).click();
      await page.locator('#trade-tab-today').click();
      await fillPlan(page);
      await geometry(page);
      await screenshot(page, '#trade-plan-title', `trade-plan-${width}-${theme}`);
      for (const tab of ['positions', 'activity']) {
        if (tab === 'activity') await page.locator('#trade-tab-today').click();
        await page.locator('#trade-save-plan').evaluate(node => node.scrollIntoView({ block: 'start', behavior: 'auto' }));
        await page.locator('#trade-tab-' + tab).click();
        if (width <= 390) {
          const location = await page.evaluate(() => ({
            headingTop: document.querySelector('#trade-panel h3').getBoundingClientRect().top,
            tabsBottom: document.querySelector('#trade-workspace .tw-tabs').getBoundingClientRect().bottom
          }));
          assert.ok(location.headingTop >= location.tabsBottom - 1,
            `${width}px ${theme} ${tab}: its heading must clear the sticky tabs after leaving a deep plan (${JSON.stringify(location)}).`);
        }
        await geometry(page);
        await screenshot(page, '#trade-panel', `trade-${tab}-${width}-${theme}`);
      }
    }
  }
  assert.deepEqual(manual.state.unexpected, []);
  await manual.context.close();
  pass('plans, holdings and activity fit 320px, 390px and desktop layouts in both themes');

  for (const mode of ['accepted', 'unknown']) {
    const app = await open(mode), p = app.page;
    await p.waitForFunction(() => document.querySelector('#trade-account-status')?.textContent === 'Paper connected');
    await p.waitForFunction(() => window.SCTradeState.getState().broker_snapshots.length === 1);
    await setProfile(p, true);
    await fillPlan(p);
    await p.locator('#trade-preview-order').click();
    await p.locator('#trade-submit-order').waitFor({ state: 'visible' });
    assert.equal(app.state.previews.length, 1);
    assert.equal(app.state.orders.length, 0, 'Previewing cannot submit an order.');
    assert.equal((await records(p)).fills.length, 0);
    assert.equal((await holdings(p)).positions.length, 0);
    assert.match(await p.locator('#trade-order-preview').textContent(), /CI paper account/);
    assert.match(await p.locator('#trade-order-preview').textContent(), /30/);
    assert.match(await p.locator('#trade-order-preview').textContent(), /\$20\.00/);
    assert.match(await p.locator('#trade-order-preview').textContent(), /\$18\.00/);
    const orderFinished = mode === 'unknown'
      ? p.waitForEvent('requestfailed', { predicate: request => new URL(request.url()).pathname === '/api/orders' })
      : p.waitForResponse(response => new URL(response.url()).pathname === '/api/orders');
    await p.locator('#trade-submit-order').click();
    await orderFinished;
    await p.waitForFunction(expected => {
      const text = document.querySelector('.tw-order-receipt')?.textContent || '';
      return expected === 'accepted' ? /Order accepted/.test(text) : /Order result unknown/.test(text);
    }, mode);
    assert.equal(app.state.orders.length, 1);
    assert.deepEqual(app.state.orders[0], { preview_id: 'ci-preview-1', confirmation: 'submit' });
    assert.equal((await records(p)).fills.length, 0);
    assert.equal((await holdings(p)).positions.length, 0, 'An order receipt cannot stand in for a confirmed execution.');
    if (mode === 'accepted') {
      assert.match(await p.locator('.tw-order-receipt').textContent(), /accepted.*Waiting for confirmed fills/i);
      assert.equal((await records(p)).plans.at(-1).status, 'submitted');
    } else {
      const submit = p.locator('#trade-submit-order');
      assert.equal(await submit.count() === 0 || await submit.isDisabled(), true, 'An uncertain submission cannot leave an enabled submit button.');
      await p.locator('#trade-tab-today').click();
      const refreshed = p.waitForResponse(response => new URL(response.url()).pathname === '/api/portfolio');
      await p.locator('#trade-refresh-account').click();
      await refreshed;
      await p.waitForFunction(() => /Account refreshed/.test(document.querySelector('#trade-notice')?.textContent || ''));
      assert.equal(app.state.orders.length, 1, 'Refreshing an ambiguous order must not retry the submission.');
      const newPreview = p.locator('#trade-preview-order');
      assert.equal(await newPreview.count() === 0 || await newPreview.isDisabled(), true);
    }
    await screenshot(p, '.tw-order-receipt', `trade-broker-${mode}-phone`);
    assert.deepEqual(app.state.unexpected, []);
    await app.context.close();
    pass(mode === 'accepted' ? 'broker order preview requires explicit submission and acceptance creates no fill or position'
      : 'a lost submit response stays unresolved and account refresh cannot repeat the order');
  }
  assert.deepEqual(errors, [], 'No application exceptions during trade workflow interactions.');
} finally {
  if (browser) await browser.close();
  await new Promise(resolve => server.close(resolve));
}
console.log(`${checks} trade workflow checks passed`);
