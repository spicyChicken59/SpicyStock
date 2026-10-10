/* Publication recovery over actual local HTTP stalls and producer fixtures.
   Private seeds are saved through the real handoff UI; legacy/corrupt stores
   and non-cooperative transports are explicitly isolated boundary controls. */
import { createServer } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..'), NOW = '2026-09-11T13:35:00Z';
const KEY = 'spicystock:handoff:v1', DEADLINE = 15000;
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const mime = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.woff2': 'font/woff2' };
const field = (page, key) => page.locator('[data-handoff-field="' + key + '"]');
const waitOutcome = (page, state) => page.waitForFunction(want => document.querySelector('#refresh-said')?.dataset.outcome === want, state, { timeout: DEADLINE + 6000 });
const stored = page => page.evaluate(key => localStorage.getItem(key), KEY);
async function closed(request) {
  let timer;
  try {
    return await Promise.race([request.whenClosed.then(() => true), new Promise(resolve => { timer = setTimeout(() => resolve(false), 1000); })]);
  } finally { clearTimeout(timer); }
}

export async function checkPublicationRecovery({ browser, check, eq, shotsDir }) {
  console.log('-- publication recovery: bounded real HTTP reads, latest attempt and private report continuity');
  const raw = await readFile(path.join(ROOT, 'tests/fixtures/cash-preview/publication.json'));
  const morning = await readFile(path.join(ROOT, 'tests/fixtures/cash-preview/observed.json'));
  const next = await readFile(path.join(ROOT, 'tests/fixtures/page/next.json'));
  const cases = new Map(), held = new Set(), tabs = new Set();
  let serial = 0;
  const server = createServer(async (req, res) => {
    const url = new URL(req.url, 'http://local');
    try {
      if (url.pathname.startsWith('/recovery-publication/')) {
        const control = cases.get(url.pathname), step = control.steps.shift() || { kind: 'good' };
        const request = { kind: step.kind, at: performance.now(), closed: false };
        control.requests.push(request);
        request.whenClosed = new Promise(resolve => res.once('close', () => { request.closed = true; held.delete(res); resolve(); }));
        if (step.kind === 'headers' || step.kind === 'body') {
          held.add(res);
          if (step.kind === 'body') { res.writeHead(200, { 'content-type': 'application/json' }); res.write(raw.subarray(0, 100)); }
          return;
        }
        if (step.kind === 'http') { res.writeHead(503); res.end('Controlled unavailable publication.'); return; }
        const body = step.kind === 'malformed' ? Buffer.from('{') : step.kind === 'shape' ? Buffer.from(JSON.stringify({ ...JSON.parse(raw), bursts: {} })) : step.kind === 'utf8' ? Buffer.from([0xff])
          : step.kind === 'bom' ? Buffer.concat([Buffer.from([0xef, 0xbb, 0xbf]), raw])
          : step.kind === 'oversize' ? Buffer.alloc(32 * 1024 * 1024 + 1, 32) : step.body || raw;
        res.writeHead(200, { 'content-type': 'application/json', 'content-length': body.length }); res.end(body); return;
      }
      if (url.pathname === '/docs/morning.json') { res.writeHead(200, { 'content-type': 'application/json' }); res.end(morning); return; }
      if (url.pathname === '/docs/issuer-evidence.json') { res.writeHead(404); res.end('No issuer observation in this recovery control.'); return; }
      const override = url.pathname === '/docs/app.js' ? process.env.SCSTOCK_APP
        : url.pathname === '/docs/app-morning.js' ? process.env.SCSTOCK_MORNING : null;
      const file = path.join(ROOT, decodeURIComponent(url.pathname)), body = await readFile(override || file);
      res.writeHead(200, { 'content-type': mime[path.extname(file)] || 'application/octet-stream' }); res.end(body);
    } catch { res.writeHead(404); res.end('not found'); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = 'http://127.0.0.1:' + server.address().port;
  async function launch(steps, options = {}) {
    const source = '/recovery-publication/' + (++serial) + '.json', control = { steps, requests: [] };
    cases.set(source, control);
    const context = await browser.newContext({ viewport: { width: options.width || 1280, height: 900 }, reducedMotion: 'reduce', colorScheme: 'dark' });
    const page = await context.newPage(), errors = [], resourceErrors = [], expected = [];
    tabs.add(context);
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') resourceErrors.push(message.text()); });
    const allowed = url => url === base + source || url.startsWith(base + source + '?') || /\/charts\/[A-Z.]+\.png$|\/issuer-evidence\.json$/.test(url);
    page.on('response', response => { if (response.status() >= 400 && allowed(response.url())) expected.push(response.url()); });
    page.on('requestfailed', request => { if (allowed(request.url())) expected.push(request.url()); else errors.push(request.url() + ' ' + request.failure()?.errorText); });
    await page.route('**/*', route => new URL(route.request().url()).origin === base ? route.continue() : route.fulfill({ status: 200, contentType: 'text/plain', body: '' }));
    await page.addInitScript(({ source, seed, storageMode }) => {
      window.SCStock = { dataUrl: source, now: '2026-09-11T13:35:00Z' };
      if (seed !== undefined) localStorage.setItem('spicystock:handoff:v1', seed);
      const realSet = Storage.prototype.setItem, realGet = Storage.prototype.getItem;
      window.__privateWrites = 0;
      Storage.prototype.setItem = function(key, value) { if (key === 'spicystock:handoff:v1') window.__privateWrites++; return realSet.call(this, key, value); };
      if (storageMode === 'blocked') Storage.prototype.getItem = function(key) { if (key === 'spicystock:handoff:v1') throw Error('Controlled private storage failure.'); return realGet.call(this, key); };
      if (storageMode === 'no-locks') Object.defineProperty(navigator, 'locks', { value: undefined });
    }, { source, seed: options.seed, storageMode: options.storageMode });
    if (options.beforeLoad) await options.beforeLoad(page, source);
    await page.goto(base + '/docs/index.html#/explore/setting-up/COIL', { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => !!document.querySelector('#check-updates') && !document.querySelector('#morning-open').disabled);
    return { page, context, control, source, errors: () => {
      let budget = expected.length;
      return errors.concat(resourceErrors.filter(error => { if (budget && /^Failed to load resource/.test(error)) { budget--; return false; } return true; }));
    } };
  }
  const close = async tab => { tabs.delete(tab.context); await tab.context.close(); };
  const desk = async page => { await page.locator('#morning-open').click(); };
  const reports = async page => {
    await desk(page);
    await page.locator('#morning-handoffs').evaluate(node => { node.open = true; });
    await page.locator('[data-handoff-report]').evaluate(node => { node.open = true; });
  };
  const noAuthority = page => page.evaluate(() => !SCStock.data && !SCStock.model && !SCStock.avail &&
    document.querySelector('#morning-desk').dataset.morningOffered === 'false' &&
    document.querySelector('[data-morning="next"]').disabled &&
    !document.querySelector('[data-copy], [data-handoff-copy]:not(:disabled), [data-handoff-prepare]:not(:disabled)'));
  const unchanged = async (page, seed) => {
    eq('recovery performs no automatic private write', await page.evaluate(() => window.__privateWrites), 0);
    eq('recovery retains exact private storage bytes', await stored(page), seed);
  };
  try {
    // Real producer publication plus ordinary UI preparation supplies every
    // saved plan/reference field. No invented handoff record is a valid seed.
    const good = await launch([{ kind: 'good' }]);
    await waitOutcome(good.page, 'loaded');
    await good.page.waitForFunction(() => SCStock.observations.facts().state === 'loaded');
    eq('publication deadline is the named fifteen-second bound', await good.page.evaluate(() => SCStock.PUBLICATION_TIMEOUT_MS), DEADLINE);
    await desk(good.page); await good.page.locator('.ss-morning__prep > summary').click();
    await good.page.locator('#morning-cash').fill('2000'); await good.page.locator('#morning-preview-fees').fill('1'); await good.page.locator('#morning-preview-quantity').fill('2');
    await good.page.locator('[data-handoff-prepare]').click();
    await good.page.waitForFunction(() => SCStock.handoff.list().length === 1);
    const seed = await stored(good.page);
    await close(good);

    // Both real socket faults start together. Neither response is fulfilled
    // by a fetch mock: the server must observe the application close it.
    await Promise.all(['headers', 'body'].map(async (kind, index) => {
      const tab = await launch([{ kind }], { seed, width: index ? 1280 : 390 }), { page, control } = tab;
      await reports(page);
      check(kind + ': private broker facts accessible while publication loads', await field(page, 'average_price').isVisible());
      check(kind + ': pending startup cannot prepare or copy an entry', await noAuthority(page));
      await field(page, 'average_price').fill('111.');
      await page.evaluate(() => { window.__heldReport = document.querySelector('[data-handoff-field="average_price"]'); window.__heldReport.setSelectionRange(2, 2); });
      await waitOutcome(page, 'timeout');
      const elapsed = performance.now() - control.requests[0].at;
      check(kind + ': timeout covers headers and entire body within deadline allowance', elapsed >= DEADLINE - 300 && elapsed <= DEADLINE + 5000, elapsed);
      check(kind + ': timeout closes the actual server connection', await closed(control.requests[0]));
      check(kind + ': timed-out startup has no entry authority', await noAuthority(page));
      eq(kind + ': private input, caret and dirty state survive timeout', await field(page, 'average_price').evaluate(node => [node === window.__heldReport, node.value, node.selectionStart, /Unsaved correction/.test(document.querySelector('[data-handoff-editor-status]').textContent)]), [true, '111.', 2, true]);
      await unchanged(page, seed);
      if (shotsDir) { await mkdir(shotsDir, { recursive: true }); await field(page, 'average_price').scrollIntoViewIfNeeded(); await page.locator('#morning-desk').screenshot({ path: path.join(shotsDir, 'recovery-private-' + (index ? 1280 : 390) + '.png') }); }
      await page.locator('#morning-desk').evaluate(dialog => {
        window.__recoveryDeskClosed = false;
        dialog.addEventListener('close', () => { window.__recoveryDeskClosed = true; }, { once: true });
      });
      await page.locator('#morning-close').click();
      // Native close and the app's queued close listener both restore focus.
      // Wait for the actual event before moving to Retry with the keyboard.
      await page.waitForFunction(() => window.__recoveryDeskClosed && !document.querySelector('#morning-desk').open && document.activeElement.id === 'morning-open');
      await page.locator('#check-updates').focus();
      eq(kind + ': retry is keyboard reachable', await page.evaluate(() => document.activeElement.id), 'check-updates');
      if (shotsDir) await page.screenshot({ path: path.join(shotsDir, 'recovery-timeout-' + (index ? 1280 : 390) + '.png') });
      await page.keyboard.press('Enter'); await waitOutcome(page, 'loaded');
      await page.waitForFunction(() => !!SCStock.observations.facts().recordHash);
      eq(kind + ': successful retry binds original publication bytes', await page.evaluate(() => SCStock.observations.facts().recordHash), sha(raw));
      eq(kind + ': recovery keeps one private editor and its exact unsaved node/value', await field(page, 'average_price').evaluate(node => [document.querySelectorAll('#morning-handoffs').length, node === window.__heldReport, node.value]), [1, true, '111.']);
      await unchanged(page, seed); eq(kind + ': browser errors', tab.errors(), []);
      await close(tab);
    }));

    for (const kind of ['http', 'malformed', 'shape', 'render-fault', 'utf8', 'bom', 'oversize']) {
      const tab = await launch([{ kind }], { seed, beforeLoad: kind === 'render-fault' ? async page => {
        const source = await readFile(path.join(ROOT, 'docs/app-morning.js'), 'utf8');
        await page.route('**/app-morning.js', route => route.fulfill({ contentType: 'text/javascript', body: source + '\n' +
          '{ const render = SCStock.morning.render; SCStock.morning.render = function(...args) { SCStock.morning.render = render; throw Error("Controlled initial renderer failure."); }; }' }));
      } : undefined }), { page } = tab;
      await waitOutcome(page, 'failed');
      eq(kind + ': initial failure is explicitly unavailable, including a partial render', await page.getAttribute('html', 'data-ss-rendered'), 'error');
      check(kind + ': startup refusal retains usable retry', await page.locator('#check-updates').isVisible() && !(await page.locator('#check-updates').isDisabled()));
      check(kind + ': startup refusal has no current entry authority', await noAuthority(page));
      if (kind === 'render-fault') {
        await page.evaluate(() => new Promise(resolve => {
          window.addEventListener('hashchange', () => resolve(), { once: true });
          window.location.hash = '#/explore/bursts';
        }));
        // The unavailable page hides this control; its handler must also
        // refuse the partial model if an already-queued click reaches it.
        await page.locator('#choose-open').evaluate(node => node.click());
        eq('partial initial render cannot reveal stale candidates through navigation or chooser', await page.evaluate(() => [document.querySelectorAll('#pick-list .ss-pick').length, document.querySelector('#chooser').open, document.querySelector('#detail').textContent.startsWith('No record.')]), [0, false, true]);
      }
      await page.locator('#check-updates').click(); await waitOutcome(page, 'loaded');
      await page.waitForFunction(() => !!SCStock.observations.facts().recordHash);
      eq(kind + ': retry uses exact accepted bytes', await page.evaluate(() => SCStock.observations.facts().recordHash), sha(raw));
      await unchanged(page, seed); eq(kind + ': refused-read browser errors', tab.errors(), []);
      await close(tab);
    }

    const revision = Buffer.concat([Buffer.from(' '), raw]);
    const refresh = await launch([{ kind: 'good' }, { kind: 'body' }, { kind: 'headers' }, { kind: 'good' }, { kind: 'good', body: revision }, { kind: 'good', body: next }, { kind: 'good' }], { seed });
    const p = refresh.page;
    await waitOutcome(p, 'loaded'); await reports(p);
    await field(p, 'average_price').fill('111.');
    await p.locator('.ss-morning__prep').evaluate(node => { node.open = true; });
    await p.locator('#morning-cash').fill('123.');
    await p.evaluate(() => { window.__refreshReport = document.querySelector('[data-handoff-field="average_price"]'); window.__selected = document.querySelector('#detail').dataset.selected; window.__oldData = SCStock.data; SCStock.checkUpdates(); });
    await field(p, 'average_price').focus();
    await waitOutcome(p, 'timeout');
    check('refresh timeout closes its stalled body', await closed(refresh.control.requests[1]));
    eq('refresh timeout preserves record, selection, dirty node/value/focus and entered cash', await p.evaluate(() => [SCStock.data === window.__oldData, document.querySelector('#detail').dataset.selected === window.__selected, document.querySelector('[data-handoff-field="average_price"]') === window.__refreshReport, window.__refreshReport.value, document.activeElement === window.__refreshReport, document.querySelector('#morning-cash').value]), [true, true, true, '111.', true, '123.']);
    await p.evaluate(() => SCStock.checkUpdates());
    await p.waitForTimeout(150); await p.evaluate(() => SCStock.checkUpdates()); await waitOutcome(p, 'unchanged');
    check('new refresh aborts the superseded headers request', await closed(refresh.control.requests[2]));
    await unchanged(p, seed);
    await p.evaluate(() => SCStock.checkUpdates()); await waitOutcome(p, 'revised');
    await p.waitForFunction(want => SCStock.observations.facts().recordHash === want, sha(revision));
    eq('same-session revision preserves dirty editor node and cash', await p.evaluate(() => [document.querySelector('[data-handoff-field="average_price"]') === window.__refreshReport, window.__refreshReport.value, document.querySelector('#morning-cash').value]), [true, '111.', '123.']);
    await p.evaluate(() => SCStock.checkUpdates()); await waitOutcome(p, 'newer');
    await p.evaluate(() => SCStock.checkUpdates()); await waitOutcome(p, 'older');
    eq('older retry retains the accepted newer producer session', await p.evaluate(() => SCStock.data.run.session), JSON.parse(next).run.session);
    await unchanged(p, seed); eq('refresh browser errors', refresh.errors(), []);
    await close(refresh);

    // Abort-ignoring promises isolate latest-attempt guards from cancellation.
    // Real abort/cancellation is established separately by the socket cases.
    for (const late of ['success', 'failure']) {
      const tab = await launch([{ kind: 'good' }], { seed, beforeLoad: async (page, source) => {
        await page.addInitScript(({ source, raw }) => {
          const native = window.fetch; let first = true;
          window.fetch = function(url, options) {
            if (String(url).startsWith(source) && first) {
              first = false; window.__lateSignal = options.signal;
              return new Promise((resolve, reject) => { window.__lateSuccess = () => resolve(new Response('  ' + raw, { status: 200 })); window.__lateFailure = () => reject(Error('Controlled late failure.')); });
            }
            return native.apply(this, arguments);
          };
        }, { source, raw: raw.toString('utf8') });
      } });
      await tab.page.locator('#check-updates').click(); await waitOutcome(tab.page, 'loaded');
      await tab.page.waitForFunction(() => !!SCStock.observations.facts().recordHash);
      eq(late + ': newer startup attempt aborts old signal', await tab.page.evaluate(() => window.__lateSignal.aborted), true);
      await tab.page.evaluate(kind => kind === 'success' ? window.__lateSuccess() : window.__lateFailure(), late);
      await tab.page.waitForTimeout(200);
      eq(late + ': late startup outcome cannot replace successful retry', await tab.page.evaluate(() => [SCStock.observations.facts().recordHash, document.querySelector('#refresh-said').dataset.outcome]), [sha(raw), 'loaded']);
      await unchanged(tab.page, seed); eq(late + ': late-outcome browser errors', tab.errors(), []);
      await close(tab);
    }

    const legacy = JSON.parse(seed); legacy.version = 1;
    legacy.items.forEach(item => { item.version = 1; for (const key of ['average_exit_price', 'entry_fees', 'exit_fees']) delete item.report[key]; });
    for (const [name, privateRaw, storageMode] of [['legacy', JSON.stringify(legacy), null], ['future', '{"version":99,"items":[]}', null], ['malformed', '{', null], ['blocked', seed, 'blocked'], ['no-locks', seed, 'no-locks']]) {
      const tab = await launch([{ kind: 'http' }], { seed: privateRaw, storageMode }), { page } = tab;
      await waitOutcome(page, 'failed'); await desk(page); await page.locator('#morning-handoffs').evaluate(node => { node.open = true; });
      if (name === 'legacy' || name === 'no-locks') {
        eq(name + ': saved private record is readable without a publication', await page.evaluate(() => SCStock.handoff.list().length), 1);
        eq(name + ': missing publication keeps saved entry copy disabled', await page.locator('[data-handoff-copy]').isDisabled(), true);
        if (name === 'no-locks') eq('missing write locks keep report saving disabled', await page.locator('[data-handoff-save]').isDisabled(), true);
      } else check(name + ': unavailable storage is explicit, not empty holdings', /unavailable|unreadable/.test(await page.locator('[data-handoff-storage]').textContent()) && /not a claim that you hold no position/.test(await page.locator('[data-handoff-empty]').textContent()));
      await page.evaluate(() => SCStock.checkUpdates()); await waitOutcome(page, 'loaded');
      eq(name + ': no migration/save occurs during recovery', await page.evaluate(() => window.__privateWrites), 0);
      if (storageMode !== 'blocked') eq(name + ': original storage bytes retained', await stored(page), privateRaw);
      eq(name + ': storage-boundary browser errors', tab.errors(), []);
      await close(tab);
    }

    for (const mode of ['pending-save', 'failed-save']) {
      const tab = await launch([{ kind: 'http' }], { seed }), { page } = tab;
      await waitOutcome(page, 'failed'); await reports(page);
      await field(page, 'submitted_quantity').fill('2'); await field(page, 'filled_quantity').fill('1'); await field(page, 'average_price').fill('111.23');
      await page.evaluate(mode => {
        window.__savingInput = document.querySelector('[data-handoff-field="average_price"]');
        if (mode === 'pending-save') {
          const request = navigator.locks.request.bind(navigator.locks);
          navigator.locks.request = (...args) => new Promise((resolve, reject) => { window.__releaseSave = () => request(...args).then(resolve, reject); });
        } else {
          window.__workingSet = Storage.prototype.setItem;
          Storage.prototype.setItem = function(key, value) { if (key === 'spicystock:handoff:v1') throw Error('Controlled quota failure.'); return window.__workingSet.call(this, key, value); };
        }
      }, mode);
      await page.locator('[data-handoff-save]').click();
      if (mode === 'pending-save') await page.waitForFunction(() => !!window.__releaseSave);
      else await page.waitForFunction(() => /could not be confirmed/.test(document.querySelector('[data-handoff-message]').textContent));
      await page.evaluate(() => SCStock.checkUpdates()); await waitOutcome(page, 'loaded');
      eq(mode + ': retry preserves the exact entered report node and value', await field(page, 'average_price').evaluate(node => [node === window.__savingInput, node.value]), [true, '111.23']);
      eq(mode + ': retry cannot commit the pending/failed report', await stored(page), seed);
      if (mode === 'pending-save') {
        eq('pending save remains busy after publication recovery', await field(page, 'average_price').isDisabled(), true);
        await page.evaluate(() => window.__releaseSave());
      } else {
        check('failed save keeps the proposed recovery payload visible', await page.locator('[data-handoff-recovery]').isVisible() && await page.evaluate(() => !!SCStock.handoff.recovery().proposed));
        await page.evaluate(() => { Storage.prototype.setItem = window.__workingSet; });
        await page.locator('[data-handoff-save]').click();
      }
      await page.waitForFunction(() => SCStock.handoff.list()[0].report.average_price === '111.23');
      eq(mode + ': only the explicit report save writes private storage', await page.evaluate(() => window.__privateWrites), 1);
      eq(mode + ': private report browser errors', tab.errors(), []);
      await close(tab);
    }
  } finally {
    for (const context of tabs) await context.close();
    for (const response of held) response.destroy();
    server.closeAllConnections(); await new Promise(resolve => server.close(resolve));
  }
}
