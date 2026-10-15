/* Stock finder over the pipeline's full fixture. The one rendered name-only
   collision is an explicitly synthetic chooser boundary: symbols, recorded
   prices, plans and evidence retain the generator's values. No market or
   publication receipt is fabricated. Cross-tab removal uses the real store. */
import { readFile, mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');
const FIXTURE = '/tests/fixtures/page/full.json', NOW = '2026-09-10T22:31:00Z';
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
const payloadDigest = page => page.evaluate(async () => {
  const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(JSON.stringify(SCStock.data)));
  return [...new Uint8Array(hash)].map(byte => byte.toString(16).padStart(2, '0')).join('');
});
const rendered = page => page.waitForFunction(() => window.SCStock?.model && document.documentElement.hasAttribute('data-ss-rendered'));
const outcome = (page, wanted) => page.waitForFunction(value => document.querySelector('#refresh-said')?.dataset.outcome === value, wanted);
const settled = page => page.evaluate(async () => { await document.fonts.ready; await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))); });
const chooserOpen = page => page.locator('#chooser').evaluate(node => node.open);
const facts = page => page.evaluate(() => ({
  hash: location.hash, query: document.querySelector('#search').value,
  detail: document.querySelector('#detail-h2')?.textContent || null,
  lens: document.querySelector('#lens [data-lens][aria-pressed="true"]')?.dataset.lens,
  cards: [...document.querySelectorAll('#pick-list .ss-pick')].map(node => node.dataset.id),
  status: document.querySelector('#picks-status').textContent,
  savedLens: localStorage.getItem('spicystock:lens:v1'),
  tickets: SCStock.model.tickets, cash: document.querySelector('#morning-cash')?.value || '',
  brokerReports: localStorage.getItem(SCStock.handoff.KEY),
}));
async function openFinder(page) {
  await page.locator('#find-stock').click();
  await page.waitForFunction(() => document.querySelector('#chooser').open && document.activeElement === document.querySelector('#chooser-search'));
}
async function closeFinder(page) {
  await page.locator('#chooser-close').click();
  await page.waitForFunction(() => !document.querySelector('#chooser').open);
}
async function choose(page, ticker, ready) {
  if (!(await ready(page))) return false;
  await page.locator('#chooser-search').fill(ticker);
  await page.locator('#chooser-search').press('Enter');
  await page.waitForFunction(() => !document.querySelector('#chooser').open);
  await settled(page);
  return true;
}
async function restrict(context, base, routed) {
  await context.route('**/*', route => {
    const url = new URL(route.request().url());
    if (url.origin === base) return routed ? routed(route, url) : route.continue();
    if (['fonts.googleapis.com', 'fonts.gstatic.com'].includes(url.hostname)) return route.continue();
    return route.fulfill({ status: 200, contentType: 'text/plain', body: '' });
  });
}

export async function checkStockFinder({ browser, base, open, check, eq, shotsDir }) {
  console.log('-- stock finder: opening access, exact choice and filter recovery');
  const finder = async page => {
    const button = page.locator('#find-stock');
    const available = await button.count() === 1 && await button.isEnabled();
    check('stock finder is present and enabled before an explicit open action', available);
    if (!available) return false;
    await openFinder(page);
    return true;
  };
  const raw = await readFile(path.join(ROOT, FIXTURE)), full = JSON.parse(raw);
  const target = full.bursts[2], other = full.bursts[1], coil = full.watchlist.top[0];
  check('stock finder fixture supplies distinct burst and setup choices', !!target && !!other && !!coil && target.ticker !== other.ticker);
  if (!target || !other || !coil) return;
  const launch = (width, options = {}) => open(browser, base, FIXTURE, NOW, width, {
    height: 844, theme: width < 400 ? 'light' : 'dark', reducedMotion: 'reduce', lens: 'all',
    beforeLoad: (_, context) => restrict(context, base), ...options,
  });

  // Actual opening geometry, including either side of the responsive boundary.
  for (const width of [320, 390, 721, 768, 820, 960, 1000, 1001, 1280]) {
    const { page, context, errors } = await launch(width);
    try {
      await settled(page);
      const layout = await page.evaluate(() => {
        const button = document.querySelector('#find-stock');
        const boxes = [...document.querySelectorAll('.ss-orientation p, .ss-orientation button')].map(node => {
          const r = node.getBoundingClientRect();
          return { x: r.x, y: r.y, right: r.right, bottom: r.bottom, width: r.width, height: r.height, client: node.clientWidth, scroll: node.scrollWidth };
        });
        const rect = button?.getBoundingClientRect();
        return { enabled: !!button && !button.disabled, label: button?.textContent, role: button?.getAttribute('aria-haspopup'), controls: button?.getAttribute('aria-controls'),
          button: rect ? { x: rect.x, y: rect.y, right: rect.right, bottom: rect.bottom, height: rect.height } : null,
          width: innerWidth, height: innerHeight, pageWidth: document.documentElement.scrollWidth,
          noOverlap: boxes.every((a, i) => boxes.every((b, j) => i === j || a.right <= b.x || b.right <= a.x || a.bottom <= b.y || b.bottom <= a.y)),
          noClipping: boxes.every(b => b.scroll <= b.client + 1 && b.x >= 0 && b.right <= innerWidth),
          sizes: [...document.querySelectorAll('.ss-orientation p')].map(node => parseFloat(getComputedStyle(node).fontSize)),
        };
      });
      check(width + ': opening finder is enabled after the publication renders', layout.enabled);
      eq(width + ': finder names its existing accessible dialog', [layout.label, layout.role, layout.controls], ['Find a stock', 'dialog', 'chooser']);
      check(width + ': finder is within the first viewport with a 44px target', layout.button && layout.button.height >= 44 && layout.button.y >= 0 && layout.button.bottom <= layout.height && layout.button.x >= 0 && layout.button.right <= layout.width, JSON.stringify(layout.button));
      check(width + ': opening guidance and finder do not overlap or clip', layout.noOverlap && layout.noClipping && layout.pageWidth <= layout.width + 1, JSON.stringify(layout));
      check(width + ': opening guidance retains readable text size', layout.sizes.every(size => size >= 13), JSON.stringify(layout.sizes));
      if (shotsDir && [320, 390, 1280].includes(width)) { await mkdir(shotsDir, { recursive: true }); await page.screenshot({ path: path.join(shotsDir, 'stock-finder-opening-' + width + '.png') }); }
      if (!(await finder(page))) return;
      eq(width + ': dialog lists every recorded burst and setup', await page.locator('#chooser-list .ss-chooser__item').count(), full.bursts.length + full.watchlist.top.length + full.watchlist.also_quiet.length);
      await page.keyboard.press('Escape');
      await page.waitForFunction(() => !document.querySelector('#chooser').open);
      check(width + ': blank-search Escape returns focus to opening finder', await page.locator('#find-stock').evaluate(node => node === document.activeElement));
      eq(width + ': finder layout produces no browser errors', [...errors], []);
    } finally { await context.close(); }
  }

  // The existing record lacks a name/ticker collision. Only the first burst's
  // descriptive name is replaced; NVDA's producer-authored row stays intact.
  const collision = structuredClone(full);
  collision.bursts[0].name = 'Synthetic chooser company containing ' + target.ticker;
  const collisionTab = await launch(390, { hash: '#/explore/bursts/' + other.ticker });
  try {
    const { page } = collisionTab;
    // The fixture is rendered directly for this labelled UI boundary. No
    // generated provenance or observation receipt is asserted for the copy.
    await page.evaluate(data => SCStock.render(data, new Date('2026-09-10T22:31:00Z')), collision);
    if (!(await finder(page))) return;
    await page.locator('#chooser-search').fill('  ' + target.ticker.toLowerCase() + '  ');
    eq('synthetic collision visibly places the company-name result before exact ticker', await page.locator('#chooser-list .ss-chooser__item').first().getAttribute('data-id'), 'bursts:' + full.bursts[0].ticker);
    check('exact chooser query announces the ticker Enter will open', (await page.locator('#chooser-status').innerText()).includes('Enter opens ' + target.ticker + '.'));
    await page.locator('#chooser-search').press('Enter');
    await page.waitForFunction(() => !document.querySelector('#chooser').open); await settled(page);
    eq('Enter opens the exact ticker instead of the earlier company-name match', await page.locator('#detail-h2').textContent(), target.ticker);
    eq('exact choice uses the selected ticker route', await page.evaluate(() => location.hash), '#/explore/bursts/' + target.ticker);
    eq('synthetic name-only chooser control produces no browser errors', [...collisionTab.errors], []);
  } finally { await collisionTab.context.close(); }

  const tab = await launch(390, { hash: '#/explore/setting-up/' + coil.ticker });
  try {
    const { page } = tab, before = await facts(page);
    await page.locator('#search').fill('ZZZZ_NO_MATCH');
    const filtered = await facts(page);
    eq('incompatible page query hides cards before reselecting the same stock', filtered.cards, []);
    if (!(await finder(page))) return; await page.locator('#chooser-search').fill(other.ticker);
    // Chromium's native search field consumes the first Escape to clear text.
    await page.keyboard.press('Escape');
    eq('first Escape clears a nonempty native search field', await page.locator('#chooser-search').inputValue(), '');
    check('first Escape with text leaves the chooser open', await chooserOpen(page));
    await page.keyboard.press('Escape'); await page.waitForFunction(() => !document.querySelector('#chooser').open);
    const cancelled = await facts(page);
    eq('cancelling preserves page query and original stock route', [cancelled.query, cancelled.hash, cancelled.detail], [filtered.query, filtered.hash, filtered.detail]);
    check('cancelling returns focus to finder', await page.locator('#find-stock').evaluate(node => node === document.activeElement));
    if (!(await finder(page))) return; await page.locator('#chooser-search').fill('ZZZZ_NO_MATCH');
    await page.locator('#chooser-search').press('Enter');
    check('unmatched Enter keeps the chooser open without choosing another stock', await chooserOpen(page));
    eq('unmatched chooser query lists no false result', await page.locator('#chooser-list .ss-chooser__item').count(), 0);
    check('unmatched chooser query explicitly explains absence', (await page.locator('#chooser-status').innerText()).includes('No stock matching'));
    await closeFinder(page);
    if (!(await choose(page, coil.ticker, finder))) return;
    const selected = await facts(page);
    eq('reselecting a remembered ticker clears an incompatible page query', selected.query, '');
    eq('reselecting a remembered ticker restores its recorded card and detail', [selected.cards.includes('setting-up:' + coil.ticker), selected.detail], [true, coil.ticker]);
    eq('chooser does not alter recorded tickets or private account facts', [selected.tickets, selected.cash, selected.brokerReports], [before.tickets, before.cash, before.brokerReports]);
    eq('chooser query and cancellation controls produce no browser errors', [...tab.errors], []);
  } finally { await tab.context.close(); }

  // A real storage event, not internal selection injection: another tab can
  // remove a followed stock while the first tab still has its detail selected.
  const cross = await launch(390, { hash: '#/explore/setting-up/' + coil.ticker });
  try {
    const { page, context } = cross;
    await page.locator('#detail [data-follow-action="add"]').click();
    await page.waitForFunction(ticker => SCStock.follow.list().some(row => row.ticker === ticker), coil.ticker);
    await page.locator('#lens [data-lens="following"]').click();
    const before = await facts(page);
    await page.evaluate(() => {
      window.__stockFinderStorage = [];
      addEventListener('storage', event => { if (event.key === SCStock.follow.DEMO_KEY) window.__stockFinderStorage.push(event.key); });
    });
    const second = await context.newPage(), secondErrors = [];
    second.on('pageerror', error => secondErrors.push(error.message));
    await second.addInitScript(({ dataUrl, now }) => { window.SCStock = { dataUrl, now }; }, { dataUrl: FIXTURE, now: NOW });
    await second.goto(base + '/docs/index.html#/explore/setting-up/' + coil.ticker, { waitUntil: 'load' }); await rendered(second);
    const removed = await second.evaluate(async ticker => {
      const saved = SCStock.follow.list().find(row => row.ticker === ticker);
      return saved ? SCStock.follow.remove(saved.id) : { ok: false, error: 'Fixture setup not found in shared store.' };
    }, coil.ticker);
    check('second tab removes the real saved fixture setup', removed.ok, JSON.stringify(removed));
    await page.waitForFunction(() => window.__stockFinderStorage.length > 0 && SCStock.follow.list().length === 0 && !document.querySelector('#pick-list .ss-pick'));
    const background = await facts(page);
    eq('background unfollow preserves runtime and stored Following lens', [background.lens, background.savedLens], ['following', before.savedLens]);
    eq('background unfollow leaves selected detail but removes its Following card', [background.detail, background.cards], [coil.ticker, []]);
    await page.bringToFront(); if (!(await finder(page))) return; await page.locator('#chooser-search').fill(coil.ticker); await closeFinder(page);
    const cancelled = await facts(page);
    eq('cancelling a hidden choice does not widen Following', [cancelled.lens, cancelled.savedLens, cancelled.hash], [background.lens, background.savedLens, background.hash]);
    if (!(await choose(page, coil.ticker, finder))) return;
    const selected = await facts(page);
    eq('explicit choice recovers the remembered stock hidden by background unfollow', [selected.detail, selected.cards.includes('setting-up:' + coil.ticker), selected.lens], [coil.ticker, true, 'all']);
    check('explicit hidden choice explains the temporary lens widening', selected.status.includes(coil.ticker + ' is outside the following lens; showing every setup so it can be inspected.'), selected.status);
    eq('explicit hidden choice leaves the saved Following preference intact', selected.savedLens, before.savedLens);
    eq('cross-tab chooser recovery preserves private account and ticket facts', [selected.tickets, selected.cash, selected.brokerReports], [before.tickets, before.cash, before.brokerReports]);
    eq('cross-tab chooser recovery produces no page exceptions', [[...cross.errors], secondErrors], [[], []]);
    if (shotsDir) { await mkdir(shotsDir, { recursive: true }); await page.screenshot({ path: path.join(shotsDir, 'stock-finder-recovered-following-390.png') }); }
  } finally { await cross.context.close(); }

  // A cached shell can predate this optional shortcut while requesting newer
  // JavaScript. Removing only the shortcut must not break the existing reader.
  const olderShell = (await readFile(path.join(ROOT, 'docs/index.html'), 'utf8'))
    .replace(/<button[^>]*id="find-stock"[^>]*>Find a stock<\/button>/, '');
  const oldContext = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' });
  try {
    const page = await oldContext.newPage(), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await restrict(oldContext, base, (route, url) => url.pathname === '/docs/index.html'
      ? route.fulfill({ contentType: 'text/html', body: olderShell }) : route.continue());
    await page.addInitScript(({ dataUrl, now }) => { window.SCStock = { dataUrl, now }; }, { dataUrl: FIXTURE, now: NOW });
    await page.goto(base + '/docs/index.html', { waitUntil: 'load' });
    const usable = await page.waitForFunction(() => window.SCStock?.model && document.querySelector('#detail-h2'), null, { timeout: 5000 }).then(() => true, () => false);
    check('an older shell without optional finder still loads the stock reader', usable);
    eq('older-shell control actually excludes only the new finder', await page.locator('#find-stock').count(), 0);
    if (usable) {
      await page.locator('#choose-open').click();
      check('older shell retains its existing chooser control', await chooserOpen(page));
      await closeFinder(page);
    }
    eq('optional finder absence produces no uncaught page exceptions', errors, []);
  } finally { await oldContext.close(); }

  // Route responses only control delivery of the unchanged producer bytes.
  // A pending initial read and a failed initial read cannot expose a chooser;
  // a failed refresh must keep the already loaded record accessible.
  for (const firstMode of ['hold', 'failure', 'render-failure']) {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' });
    const page = await context.newPage(), errors = [];
    let mode = firstMode === 'render-failure' ? 'good' : firstMode, pending = null, requestCount = 0;
    const renderer = firstMode === 'render-failure' ? await readFile(path.join(ROOT, 'docs/app-morning.js'), 'utf8') : null;
    const source = '/stock-finder-lifecycle-' + firstMode + '.json';
    page.on('pageerror', error => errors.push(error.message));
    await restrict(context, base, (route, url) => {
      if (renderer && url.pathname === '/docs/app-morning.js') return route.fulfill({ contentType: 'text/javascript',
        body: renderer + '\n{ const render = SCStock.morning.render; SCStock.morning.render = function (...args) { SCStock.morning.render = render; throw Error("Controlled first-render failure"); }; }' });
      if (url.pathname !== source) return route.continue();
      requestCount++;
      const next = mode; mode = 'good';
      if (next === 'hold') { pending = route; return; }
      return next === 'failure' ? route.fulfill({ status: 503, body: 'Controlled unavailable publication.' })
        : route.fulfill({ contentType: 'application/json', body: raw });
    });
    await page.addInitScript(({ source, now }) => { window.SCStock = { dataUrl: source, now }; }, { source, now: NOW });
    try {
      await page.goto(base + '/docs/index.html', { waitUntil: 'domcontentloaded' });
      await page.waitForFunction(() => window.SCStock?.checkUpdates && !document.querySelector('#morning-open').disabled);
      await outcome(page, firstMode === 'hold' ? 'checking' : 'failed');
      check(firstMode + ': finder remains disabled before a usable publication', await page.locator('#find-stock').isDisabled());
      await page.locator('#find-stock').evaluate(node => node.click());
      check(firstMode + ': an unready click cannot open the chooser', !(await chooserOpen(page)));
      if (firstMode === 'hold') { await pending.fulfill({ contentType: 'application/json', body: raw }); pending = null; }
      else await page.locator('#check-updates').click();
      await outcome(page, 'loaded');
      await rendered(page);
      check(firstMode + ': successful load or Retry enables the finder', await page.locator('#find-stock').isEnabled());
      eq(firstMode + ': recovered publication retains the complete producer fixture payload', await payloadDigest(page), digest(JSON.stringify(full)));
      eq(firstMode + ': fixture remains practice without a claimed public receipt', await page.evaluate(() => [SCStock.observations.facts().state, SCStock.observations.facts().recordHash]), ['practice', null]);
      if (!(await finder(page))) return; await closeFinder(page);
      const before = await facts(page), originalPayload = await payloadDigest(page);
      await page.evaluate(() => { window.__stockFinderOriginal = SCStock.data; });
      mode = 'hold'; await page.evaluate(() => SCStock.checkUpdates()); await outcome(page, 'checking');
      check(firstMode + ': pending refresh retains usable stock finder', await page.locator('#find-stock').isEnabled());
      if (!(await finder(page))) return;
      eq(firstMode + ': pending refresh still lists the loaded fixture stocks', await page.locator('#chooser-list .ss-chooser__item').count(), full.bursts.length + full.watchlist.top.length);
      await closeFinder(page); await pending.fulfill({ status: 503, body: 'Controlled unavailable refresh.' }); pending = null;
      await outcome(page, 'failed');
      check(firstMode + ': failed refresh retains enabled finder', await page.locator('#find-stock').isEnabled());
      eq(firstMode + ': failed refresh preserves original record payload', await payloadDigest(page), originalPayload);
      check(firstMode + ': failed refresh keeps the same loaded record object', await page.evaluate(() => SCStock.data === window.__stockFinderOriginal));
      eq(firstMode + ': failed refresh preserves selected stock, query and account facts', await facts(page), before);
      if (!(await finder(page))) return; await closeFinder(page);
      eq(firstMode + ': lifecycle uses one startup, optional retry and one refresh', requestCount, firstMode === 'hold' ? 2 : 3);
      eq(firstMode + ': lifecycle causes no uncaught page exceptions', errors, []);
    } finally { if (pending) await pending.abort().catch(() => {}); await context.close(); }
  }
}
